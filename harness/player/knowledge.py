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


def _valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA:
        return False
    if not all(isinstance(value[name], list) for name in ('articles', 'facts')):
        return False
    records = value['articles'] + value['facts']
    if not all(isinstance(r, dict) and isinstance(r.get('id'), str) for r in records) \
            or len({r['id'] for r in records}) != len(records):
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
