"""Read only the delivered subset: the frozen file, or a newer version adopted during play. No curator or evaluation dependency."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re

from .contracts import PlayerError

SCHEMA = 'delivered-knowledge/2'
FIELDS = frozenset(('schema', 'version', 'commit', 'repository_id', 'coverage', 'articles', 'facts'))
VERSION = re.compile(r'v(0|[1-9][0-9]*)')
COMMIT = re.compile(r'[0-9a-f]{40}')


def empty() -> dict:
    return dict(schema=SCHEMA, version=None, commit=None, repository_id=None, coverage=None, articles=[], facts=[])


def version_number(version: object) -> int | None:
    """The number N of a published version `vN`, else None."""
    return int(version[1:]) if isinstance(version, str) and VERSION.fullmatch(version) else None


# The public record forms `tools/knowledge_export.py` writes; `tools/player_host/knowledge.mjs` checks the same ones.
COVERAGE_FIELDS = frozenset(('schema', 'session', 'actor', 'last_step'))
ARTICLE_FIELDS = frozenset(('id', 'title', 'lead', 'body', 'links', 'last_confirmed'))
FACT_FIELDS, FACT_REQUIRED = frozenset(('id', 'type', 'text', 'subject', 'seen')), frozenset(('id', 'type', 'text', 'seen'))


def _filled(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _names(value: object, *, nonempty: bool) -> bool:
    return (isinstance(value, list) and (bool(value) or not nonempty) and all(_filled(v) for v in value)
            and len(set(value)) == len(value))


def _coverage(value: object) -> bool:
    return value is None or (
        isinstance(value, dict) and set(value) == COVERAGE_FIELDS and value['schema'] == 'curator-coverage/2'
        and _filled(value['session']) and (value['actor'] is None or _filled(value['actor']))
        and (value['last_step'] is None or type(value['last_step']) is int))


def _article(value: object) -> bool:
    return (isinstance(value, dict) and set(value) == ARTICLE_FIELDS
            and all(_filled(value[k]) for k in ('id', 'title', 'lead')) and _names(value['links'], nonempty=False)
            and isinstance(value['last_confirmed'], dict) and isinstance(value['body'], list) and bool(value['body'])
            and all(isinstance(c, dict) and set(c) == {'text', 'facts'} and _filled(c['text'])
                    and _names(c['facts'], nonempty=True) for c in value['body']))


def _fact(value: object) -> bool:
    return (isinstance(value, dict) and FACT_REQUIRED <= set(value) <= FACT_FIELDS
            and all(_filled(value[k]) for k in ('id', 'type', 'text')) and ('subject' not in value or _filled(value['subject']))
            and isinstance(value['seen'], dict))


def _valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA or not _coverage(value['coverage']):
        return False
    if not all(isinstance(value[name], list) for name in ('articles', 'facts')):
        return False
    if not all(map(_article, value['articles'])) or not all(map(_fact, value['facts'])):
        return False
    records = value['articles'] + value['facts']
    if len({r['id'] for r in records}) != len(records):
        return False
    # A published version names its tag's commit and its repository; the empty file names neither.
    identity = (value['version'], value['commit'], value['repository_id'])
    if value['version'] is None:
        return identity == (None, None, None)
    return version_number(value['version']) is not None and all(
        isinstance(v, str) and COMMIT.fullmatch(v) for v in identity[1:])


class Knowledge:
    """One delivered version. Never changed after it is read; a newer version is another object."""

    def __init__(self, path: Path):
        self._set(json.loads(path.read_text()), str(path))

    @classmethod
    def from_dict(cls, value: object, where: str = 'delivered knowledge') -> 'Knowledge':
        knowledge = cls.__new__(cls)
        knowledge._set(value, where)
        return knowledge

    def _set(self, value: object, where: str) -> None:
        if not _valid(value):
            raise PlayerError(f'{where}: unsupported delivered knowledge')
        self.value = value
        self.records = value['articles'] + value['facts']

    def read(self, identity: str) -> dict:
        found = next((r for r in self.records if r['id'] == identity or r.get('title') == identity), None)
        return dict(schema='player-knowledge/1', version=self.value['version'], grants_authority=False,
                    records=[] if found is None else [copy.deepcopy(found)])

    def query(self, query: str) -> dict:
        words = query.casefold().split()
        records = [copy.deepcopy(r) for r in self.records
                   if all(w in json.dumps(r, ensure_ascii=False).casefold() for w in words)]
        return dict(schema='player-knowledge/1', version=self.value['version'], grants_authority=False, records=records)
