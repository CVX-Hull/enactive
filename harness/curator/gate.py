"""Gate v0: validate a curator submission and publish it (ADR 009's coding-agent curator direction;
docs/design/curator-session.md).

Checks run in the spec's order and the first failing stage rejects, listing every problem in
that stage: well formed, base version, candidate scope/provenance/references. Nothing a submission contains is
executed. Only this module commits to the knowledge repository.
"""
from __future__ import annotations

import json
import argparse
import fcntl
import os
from pathlib import Path
import re
import stat
import uuid

from harness.curator.knowledge import SCHEMA, KnowledgeError, Repository

SUBMISSION = 'curator-submission/1'
FACT = 'curator-fact/4'
TYPE = 'curator-type/2'
VERDICT = 'curator-gate/2'
COVERAGE = 'curator-coverage/2'
MAX_CHANGES = 200
MAX_BYTES = 256 * 1024
_VERSION = re.compile(r'v(0|[1-9][0-9]*)')

_FACT_KEYS = {'schema', 'record', 'id', 'type', 'text', 'known', 'scope', 'citations', 'subject'}
_ARTICLE_KEYS = {'schema', 'record', 'id', 'title', 'lead', 'body', 'links'}
_TYPE_KEYS = {'schema', 'name', 'description', 'fields', 'identity', 'reason'}
_SESSION_KEYS = ('name', 'world', 'lineage', 'admission')
_SEALED_ID = re.compile(r'[0-9a-f]{32}')
_LABEL = re.compile(r'[ -~]{1,40}')
_OPS = {
    'add_fact': {'op', 'fact'}, 'supersede_fact': {'op', 'ids', 'fact'},
    'retire_fact': {'op', 'id', 'reason', 'citations'}, 'add_type': {'op', 'type'},
    'revise_types': {'op', 'action', 'names', 'types', 'assignments'},
    'add_article': {'op', 'article'}, 'revise_article': {'op', 'id', 'article'},
    'retire_article': {'op', 'id', 'reason'},
}
_TOP_KEYS = {'schema', 'base_version', 'summary', 'changes'}
_COVERAGE_KEYS = {'schema', 'session', 'actor', 'last_step'}

_RESULT_KEYS = {'schema', 'operation', 'operation_id', 'status', 'base_version', 'restored_from',
                'version', 'submission', 'session', 'from_drafts', 'diagnostics'}


def journal(repo: Repository) -> list[dict]:
    """Read the active journal only under the current result contract."""
    path = repo.state / 'gate.jsonl'
    if not path.exists():
        return []
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            if (not isinstance(row, dict) or set(row) != _RESULT_KEYS or row['schema'] != VERDICT
                    or row['operation'] not in ('submission', 'restore')
                    or row['status'] not in ('published', 'rejected', 'unchanged', 'unknown')
                    or not isinstance(row['operation_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', row['operation_id'])
                    or not isinstance(row['diagnostics'], list)
                    or not all(isinstance(d, str) for d in row['diagnostics'])
                    or not isinstance(row['from_drafts'], list)
                    or not all(isinstance(d, str) and DRAFT_ID.fullmatch(d) for d in row['from_drafts'])
                    or any(v is not None and (not isinstance(v, str) or not _VERSION.fullmatch(v))
                           for v in (row['base_version'], row['restored_from'], row['version']))
                    or (row['operation'] == 'restore' and
                        (row['submission'] is not None or row['session'] is not None or row['from_drafts']
                         or row['base_version'] is None or row['restored_from'] is None))
                    or (row['operation'] == 'submission' and
                        (not _text(row['submission']) or not _text(row['session']) or row['restored_from'] is not None))
                    or (row['status'] == 'rejected' and row['version'] is not None)
                    or (row['status'] in ('published', 'unchanged') and row['version'] is None)
                    or (row['status'] == 'published' and row['base_version'] is None)
                    or (row['status'] == 'unchanged' and row['operation'] != 'restore')):
                raise ValueError('unsupported result')
        return rows
    except (OSError, ValueError, RecursionError, UnicodeError) as error:
        raise KnowledgeError('unsupported active gate journal; use fresh state') from error


def _merge_sessions(recorded: dict[str, dict], sessions: dict[str, dict]) -> None:
    """Reserve verified session identities across the tagged history, including restores."""
    names = {row['name']: session_id for session_id, row in recorded.items()}
    worlds = {row['lineage']: row['world'] for row in recorded.values() if row['lineage'] is not None}
    slots = {(row['lineage'], row['admission']): session_id for session_id, row in recorded.items()
             if row['lineage'] is not None}
    for session_id, row in sessions.items():
        if (not isinstance(session_id, str) or not _SEALED_ID.fullmatch(session_id)
                or not isinstance(row, dict) or set(row) != set(_SESSION_KEYS) or not _text(row['name'])):
            raise ValueError('invalid session provenance')
        name, world, lineage, admission = (row[key] for key in _SESSION_KEYS)
        if (any(value is not None and (not isinstance(value, str) or not _LABEL.fullmatch(value))
                for value in (world, lineage))
                or (lineage is None) != (admission is None)
                or (admission is not None and (type(admission) is not int or not 1 <= admission <= 10000))):
            raise ValueError('invalid session labels')
        if session_id in recorded and recorded[session_id] != row:
            raise ValueError(f'session {session_id!r} has different recorded labels or name')
        if name in names and names[name] != session_id:
            raise ValueError(f'session directory {name!r} has two sealed identifiers')
        if lineage is not None:
            slot = (lineage, admission)
            if slot in slots and slots[slot] != session_id:
                raise ValueError(f'lineage {lineage!r} admission {admission} has two sealed identifiers')
            if lineage in worlds and worlds[lineage] != world:
                raise ValueError(f'lineage {lineage!r} has two different worlds')
            slots[slot] = session_id
            worlds[lineage] = world
        names[name] = session_id
        recorded[session_id] = row


def _citation_world(citations: list[str], sessions: dict[str, dict]) -> str:
    worlds = set()
    for citation in citations:
        session_id, _, number = citation.partition('-')
        world = sessions.get(session_id, {}).get('world') if number.isascii() and number.isdecimal() else None
        if world is None:
            raise ValueError(f'citation {citation!r} has no recorded world')
        worlds.add(world)
    if len(worlds) != 1:
        raise ValueError('citations span two worlds')
    return worlds.pop()


def _validate_snapshot(files: dict[str, bytes], game: str, version: str,
                       records_by_version: dict[str, dict[str, dict]],
                       recorded_sessions: dict[str, dict]) -> dict[str, dict]:
    """Validate the snapshot against its version and the previously validated versions."""
    required = {'knowledge.json', 'facts.jsonl', 'ontology/types.json', 'provenance.json',
                'programs/.keep', 'tests/.keep'}
    versions = records_by_version.keys() | {version}
    if set(files) not in (required, required | {'coverage.json'}):
        raise ValueError('unsupported snapshot layout')
    if files['programs/.keep'] or files['tests/.keep']:
        raise ValueError('unsupported program or test content')
    metadata = json.loads(files['knowledge.json'])
    if metadata != {'schema': SCHEMA, 'game': game}:
        raise ValueError('foreign knowledge metadata')
    types = json.loads(files['ontology/types.json'])
    if not isinstance(types, list) or any(_check_stored_type(t, versions) for t in types):
        raise ValueError('unsupported types')
    type_names = {t['name'] for t in types}
    if len(type_names) != len(types):
        raise ValueError('duplicate types')
    provenance = json.loads(files['provenance.json'])
    if (not isinstance(provenance, dict) or set(provenance) - {'frames', 'sessions', 'last_admission'}
            or not isinstance(provenance.get('frames'), dict)
            or not isinstance(provenance.get('sessions'), dict)):
        raise ValueError('invalid provenance')
    sessions = provenance['sessions']
    _merge_sessions(recorded_sessions, sessions)
    for frame, position in provenance['frames'].items():
        if (not _text(frame) or not isinstance(position, dict)
                or set(position) != {'session', 'actor', 'step', 'order'}
                or not _text(position['session']) or not _text(position['actor'])
                or type(position['step']) is not int or not isinstance(position['order'], list)
                or len(position['order']) != 3 or type(position['order'][0]) is not int
                or not isinstance(position['order'][1], str) or type(position['order'][2]) is not int):
            raise ValueError('invalid frame position')
        labels = sessions.get(frame.partition('-')[0])
        if labels is not None and position['session'] != labels['name']:
            raise ValueError('frame position has a different session name from its sealed identifier')
    if 'last_admission' in provenance:
        admission = provenance['last_admission']
        if (not isinstance(admission, dict) or set(admission) != {'coverage', 'citations'}
                or not _strings(admission['citations'], nonempty=False)
                or any(c not in provenance['frames'] for c in admission['citations'])):
            raise ValueError('invalid admission provenance')
        _coverage(admission['coverage'])
    if 'coverage.json' in files:
        _coverage(json.loads(files['coverage.json']))
    records = [json.loads(line) for line in files['facts.jsonl'].decode().splitlines() if line.strip()]
    by_id = {}
    for record in records:
        if not isinstance(record, dict) or record.get('record') not in ('fact', 'article'):
            raise ValueError('unsupported record')
        kind = record['record']
        fields = _FACT_KEYS if kind == 'fact' else _ARTICLE_KEYS
        added = {'published_in', 'session', 'superseded_by', 'retired'} | (
            {'seen', 'retyped'} if kind == 'fact' else {'last_confirmed'})
        if set(record) - fields - added or ('retired' in record and 'superseded_by' in record):
            raise ValueError('unsupported record metadata')
        item = {k: v for k, v in record.items() if k in fields}
        if (_check_stored_fact(item) if kind == 'fact' else _check_article('article', item)):
            raise ValueError('invalid record')
        if record.get('schema') != FACT or not _text(record.get('session')) or not _VERSION.fullmatch(record.get('published_in', '')):
            raise ValueError('invalid record provenance')
        if record['published_in'] not in versions:
            raise ValueError('invalid publication version')
        if record['id'] in by_id:
            raise ValueError('duplicate record identity')
        by_id[record['id']] = record
        if kind == 'fact':
            if record['scope']['game'] != game or any(c not in provenance['frames'] for c in record['citations']):
                raise ValueError('invalid fact scope or citations')
            if record['published_in'] == version and record['type'] not in type_names:
                raise ValueError('unknown type at fact publication')
            if (record['scope']['level'] == 'world'
                    and record['scope']['world'] != _citation_world(record['citations'], sessions)):
                raise ValueError('fact scope world differs from its citations')
            if record.get('seen') != max((provenance['frames'][c] for c in record['citations']),
                                         key=lambda p: p['order']):
                raise ValueError('invalid fact position')
            for change in record.get('retyped', []):
                if (not isinstance(change, dict) or set(change) != {'from', 'to', 'version'}
                        or not _text(change['from']) or not _text(change['to'])
                        or not isinstance(change['version'], str) or change['version'] not in versions):
                    raise ValueError('invalid type history')
        if 'retired' in record:
            retired = record['retired']
            if (not isinstance(retired, dict) or set(retired) != {'reason', 'citations', 'published_in', 'session'}
                    or not _text(retired['reason']) or not _text(retired['session'])
                    or not isinstance(retired['published_in'], str) or retired['published_in'] not in versions
                    or not _strings(retired['citations'], nonempty=kind == 'fact')
                    or any(c not in provenance['frames'] for c in retired['citations'])):
                raise ValueError('invalid retirement')
            if (kind == 'fact' and record['scope']['level'] == 'world'
                    and record['scope']['world'] != _citation_world(retired['citations'], sessions)):
                raise ValueError('retirement citations must belong to the fact\'s world')
    for record in records:
        if 'superseded_by' not in record:
            continue
        replacement = by_id.get(record['superseded_by'])
        if replacement is None or replacement['record'] != record['record']:
            raise ValueError('invalid supersession')
        if record['record'] == 'fact' and replacement['scope'] != record['scope']:
            raise ValueError('supersession requires the same fact scope')
    facts = {i: r for i, r in by_id.items() if r['record'] == 'fact' and current(r)}
    articles = [r for r in records if r['record'] == 'article']
    titles = [r['title'] for r in articles if current(r)]
    if len(titles) != len(set(titles)) or any(f['type'] not in type_names for f in facts.values()):
        raise ValueError('invalid current types or titles')
    for article in articles:
        cited = {i for claim in article['body'] for i in claim['facts']}
        if any(by_id.get(i, {}).get('scope', {}).get('level') != 'game' for i in cited):
            raise ValueError('articles may cite only game facts')
        if not current(article):
            continue
        if (not cited <= facts.keys() or any(t == article['title'] or t not in titles for t in article['links'])
                or article.get('last_confirmed') != max((facts[i]['seen'] for i in cited), key=lambda p: p['order'])):
            raise ValueError('invalid article references')
    for identity, record in by_id.items():
        published_in = record['published_in']
        origin_records = by_id if published_in == version else records_by_version[published_in]
        origin = origin_records.get(identity)
        if (origin is None or origin['published_in'] != published_in
                or origin['record'] != record['record'] or origin['session'] != record['session']):
            raise ValueError('invalid record origin')
    return by_id


def _history(repo: Repository) -> tuple[dict[str, dict[str, bytes]], set[str],
                                       dict[str, dict[str, dict]], dict[str, dict]]:
    """Validate compatible published snapshots and reserve their record and session identities."""
    snapshots, identities, records_by_version, sessions = {}, set(), {}, {}
    for version in sorted(repo._tags(), key=lambda v: int(v[1:])):
        try:
            files = repo.snapshot(version)
            records = _validate_snapshot(files, repo.game, version, records_by_version, sessions)
        except (ValueError, KeyError, TypeError, UnicodeError, RecursionError, KnowledgeError) as error:
            raise KnowledgeError(f'incompatible history at {version}') from error
        snapshots[version] = files
        records_by_version[version] = records
        identities.update(records)
    return snapshots, identities, records_by_version, sessions


def _failed_publication(repo: Repository, version: str) -> tuple[str, str | None]:
    """A failed lookup cannot establish that publication did not happen."""
    try:
        return ('unknown', version) if version in repo._tags() else ('rejected', None)
    except KnowledgeError:
        return 'unknown', None


def current(record: dict) -> bool:
    return 'superseded_by' not in record and 'retired' not in record


def _strings(value: object, *, nonempty: bool = True) -> bool:
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(_text(item) for item in value) and len(set(value)) == len(value))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _extra(label: str, value: dict, allowed: set[str], required: set[str]) -> list[str]:
    found = []
    for key in sorted(set(value) - allowed):
        found.append(f'{label}: unexpected field {key!r}')
    for key in sorted(required - set(value)):
        found.append(f'{label}: missing field {key!r}')
    return found


def _check_fact(label: str, fact: object) -> list[str]:
    return _check_fact_fields(label, fact, stored=False)


def _check_stored_fact(fact: object) -> list[str]:
    return _check_fact_fields('fact', fact, stored=True)


def _check_fact_fields(label: str, fact: object, *, stored: bool) -> list[str]:
    if not isinstance(fact, dict):
        return [f'{label}: must be an object']
    found = _extra(label, fact, _FACT_KEYS, _FACT_KEYS - {'subject'})
    if fact.get('schema', FACT) != FACT:
        found.append(f'{label}: schema must be {FACT!r}')
    if fact.get('record', 'fact') != 'fact':
        found.append(f'{label}: record must be fact')
    for key in ('id', 'type', 'text', 'subject'):
        if key in fact and not _text(fact[key]):
            found.append(f'{label}: {key} must be a non-empty string')
    if 'known' in fact and fact['known'] not in ('observed', 'inferred', 'hinted'):
        found.append(f'{label}: known must be observed, inferred or hinted')
    scope = fact.get('scope')
    if 'scope' in fact:
        keys = {'game', 'level'}
        if isinstance(scope, dict) and stored and scope.get('level') == 'world':
            keys.add('world')
        if not (isinstance(scope, dict) and set(scope) == keys and _text(scope['game'])
                and scope['level'] in ('game', 'world')
                and ('world' not in keys or isinstance(scope['world'], str) and _LABEL.fullmatch(scope['world']))):
            found.append(f'{label}: scope must be an object with exactly {", ".join(sorted(keys))}'
                         ' and level must be game or world')
    if 'citations' in fact and not _strings(fact['citations']):
        found.append(f'{label}: citations must be a non-empty list of distinct frame source ids')
    return found


def _check_article(label: str, article: object) -> list[str]:
    if not isinstance(article, dict):
        return [f'{label}: must be an object']
    found = _extra(label, article, _ARTICLE_KEYS, _ARTICLE_KEYS)
    if article.get('schema', FACT) != FACT:
        found.append(f'{label}: schema must be {FACT!r}')
    if article.get('record', 'article') != 'article':
        found.append(f'{label}: record must be article')
    for key in ('id', 'title', 'lead'):
        if key in article and not _text(article[key]):
            found.append(f'{label}: {key} must be a non-empty string')
    if 'links' in article and not _strings(article['links'], nonempty=False):
        found.append(f'{label}: links must be a list of distinct article titles')
    body = article.get('body')
    if 'body' in article and not (isinstance(body, list) and body and all(
            isinstance(claim, dict) and set(claim) == {'text', 'facts'}
            and _text(claim['text']) and _strings(claim['facts']) for claim in body)):
        found.append(f'{label}: body must be a non-empty list of {{text, facts: [fact ids]}} claims')
    return found


def _check_type(label: str, kind: object) -> list[str]:
    return _check_type_fields(label, kind, _TYPE_KEYS)


def _check_stored_type(kind: object, versions: set[str]) -> list[str]:
    found = _check_type_fields('type', kind, _TYPE_KEYS | {'published_in'})
    if not found and (not isinstance(kind['published_in'], str) or kind['published_in'] not in versions):
        found.append('type: published_in must name a version no later than the snapshot')
    return found


def _check_type_fields(label: str, kind: object, keys: set[str]) -> list[str]:
    if not isinstance(kind, dict):
        return [f'{label}: must be an object']
    found = _extra(label, kind, keys, keys)
    if kind.get('schema', TYPE) != TYPE:
        found.append(f'{label}: schema must be {TYPE!r}')
    if 'name' in kind and not _text(kind['name']):
        found.append(f'{label}: name must be a non-empty string')
    if 'description' in kind and not isinstance(kind['description'], str):
        found.append(f'{label}: description must be a string')
    fields = kind.get('fields')
    if 'fields' in kind and not (isinstance(fields, list)
                                 and all(isinstance(item, str) for item in fields)):
        found.append(f'{label}: fields must be a list of strings')
    identity = kind.get('identity')
    if 'identity' in kind and not (isinstance(identity, list)
                                   and all(isinstance(item, str) for item in identity)
                                   and len(set(identity)) == len(identity)
                                   and (not identity or isinstance(fields, list) and all(item in fields for item in identity))):
        found.append(f'{label}: identity must be a list of distinct strings from fields')
    if 'reason' in kind and not _text(kind['reason']):
        found.append(f'{label}: reason must be a non-empty string')
    return found


DRAFT_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')


def _read(path: Path) -> bytes:
    """A submission file's bytes, without following links or blocking on special files."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError('not a regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read(MAX_BYTES + 1)
    finally:
        os.close(fd)


def _parse(path: Path) -> tuple[object | None, list[str]]:
    try:
        raw = _read(path)
    except OSError:
        return None, ['submission.json is missing, unreadable or not a regular file']
    if len(raw) > MAX_BYTES:
        return None, [f'submission.json exceeds the limit of {MAX_BYTES} bytes']
    try:
        data = json.loads(raw.decode('utf-8'))
        json.dumps(data, ensure_ascii=False).encode('utf-8')  # rejects lone surrogates before publication
    except (ValueError, RecursionError, UnicodeError) as error:
        return None, [f'submission.json is not valid JSON: {type(error).__name__}']
    return data, []


def _well_formed(submission_dir: Path) -> tuple[dict | None, list[str]]:
    data, problems = _parse(submission_dir / 'submission.json')
    if problems:
        return None, problems
    if not isinstance(data, dict):
        return None, ['submission.json must be an object']
    found = _extra('submission', data, _TOP_KEYS | {'from_drafts'}, _TOP_KEYS)
    if data.get('schema', SUBMISSION) != SUBMISSION:
        found.append(f'submission: schema must be {SUBMISSION!r}')
    base = data.get('base_version')
    if 'base_version' in data and not (isinstance(base, str) and _VERSION.fullmatch(base)):
        found.append('submission: base_version must look like "v3"')
    if 'summary' in data and not isinstance(data['summary'], str):
        found.append('submission: summary must be a string')
    drafts = data.get('from_drafts', [])
    if not (isinstance(drafts, list) and all(isinstance(item, str) and DRAFT_ID.fullmatch(item) for item in drafts)):
        found.append('submission: from_drafts must be a list of draft ids')
    changes = data.get('changes')
    if 'changes' in data:
        if not isinstance(changes, list) or not changes:
            found.append('submission: changes must be a non-empty list')
        elif len(changes) > MAX_CHANGES:
            found.append(f'submission: {len(changes)} changes; the limit is {MAX_CHANGES}')
        else:
            for index, change in enumerate(changes):
                label = f'changes[{index}]'
                if not isinstance(change, dict) or not isinstance(change.get('op'), str) or change['op'] not in _OPS:
                    found.append(f'{label}: unknown operation')
                    continue
                op = change['op']
                found.extend(_extra(label, change, _OPS[op], _OPS[op]))
                if op == 'add_type':
                    found.extend(_check_type(f'{label}.type', change.get('type')))
                elif op in ('add_fact', 'supersede_fact'):
                    found.extend(_check_fact(f'{label}.fact', change.get('fact')))
                elif op in ('add_article', 'revise_article'):
                    found.extend(_check_article(f'{label}.article', change.get('article')))
                if 'id' in _OPS[op] and not _text(change.get('id')):
                    found.append(f'{label}: id must be a non-empty string')
                if 'reason' in _OPS[op] and not _text(change.get('reason')):
                    found.append(f'{label}: reason must be a non-empty string')
                if op == 'supersede_fact' and not _strings(change.get('ids')):
                    found.append(f'{label}: ids must be a non-empty list of distinct fact ids')
                if op == 'retire_fact' and not _strings(change.get('citations')):
                    found.append(f'{label}: citations must be a non-empty list of distinct frame source ids')
                if op == 'revise_types':
                    action, names, types = change.get('action'), change.get('names'), change.get('types')
                    if action not in ('merge', 'split', 'rename', 'deprecate'):
                        found.append(f'{label}: unknown type revision action')
                    if not _strings(names):
                        found.append(f'{label}: names must be distinct existing type names')
                    if not isinstance(types, list):
                        found.append(f'{label}: types must be a list')
                    else:
                        for number, item in enumerate(types):
                            found.extend(_check_type(f'{label}.types[{number}]', item))
                    assignments = change.get('assignments')
                    if not (isinstance(assignments, dict) and all(_text(k) and _text(v) for k, v in assignments.items())):
                        found.append(f'{label}: assignments must map fact ids to type names')
                    if _strings(names) and isinstance(types, list) and action in ('merge', 'split', 'rename', 'deprecate'):
                        sizes = (len(names), len(types))
                        valid = (sizes[0] >= 2 and sizes[1] == 1 if action == 'merge' else
                                 sizes[0] == 1 and sizes[1] >= 2 if action == 'split' else
                                 sizes == (1, 1) if action == 'rename' else sizes == (1, 0))
                        if not valid:
                            found.append(f'{label}: invalid {action} cardinality')
    if isinstance(changes, list) and sum(isinstance(c, dict) and c.get('op') == 'revise_types' for c in changes) > 1:
        found.append('submission: each type revision needs its own published version')
    return (None if found else data), found


def _apply(repo: Repository, data: dict, version: str, session_id: str,
           frames: dict[str, dict], session_kind: str, reserved: set[str],
           provenance: dict) -> tuple[list[dict], list[dict], list[str]]:
    """Build a candidate snapshot; inspect its references only, never the meaning of prose.

    Structural controls address R-GAME-COUPLING and R-REGRESSION without a semantic judge.
    """
    records = repo.records()
    types = {item['name']: item for item in repo.types()}
    base_types = set(types)
    by_id = {item['id']: item for item in records}
    original = {item['id']: dict(item) for item in records}
    recorded_frames = provenance['frames']
    sessions = provenance['sessions']
    removed = {identity for change in data['changes'] for identity in
               (change['ids'] if change['op'] == 'supersede_fact' else
                [change['id']] if change['op'] == 'retire_fact' else [])}
    found = []
    assigned: set[str] = set()
    touched: set[str] = set()
    for index, change in enumerate(data['changes']):
        op = change['op']
        label = f'changes[{index}]'
        if op == 'add_type':
            item = change['type']
            if item['name'] in types:
                found.append(f'{label}: type {item["name"]!r} already exists')
            types[item['name']] = dict(item, published_in=version)
        elif op == 'revise_types':
            if session_kind != 'grooming':
                found.append(f'{label}: type revisions require a grooming session')
            for name in change['names']:
                if name not in types:
                    found.append(f'{label}: unknown type {name!r}')
                types.pop(name, None)
            for item in change['types']:
                if item['name'] in types:
                    found.append(f'{label}: type {item["name"]!r} already exists')
                types[item['name']] = dict(item, published_in=version)
            for identity, name in change['assignments'].items():
                target = by_id.get(identity)
                if target is None or target.get('record') != 'fact' or not current(target):
                    found.append(f'{label}: assignment fact {identity!r} is not current')
                elif original[identity]['type'] not in change['names']:
                    found.append(f'{label}: assignment fact {identity!r} has a type outside names before the revision')
                elif identity in removed:
                    found.append(f'{label}: assignment fact {identity!r} is retired or superseded in this submission')
                else:
                    assigned.add(identity)
                    target['retyped'] = [*target.get('retyped', []),
                                         {'from': target['type'], 'to': name, 'version': version}]
                    target['type'] = name
    for index, change in enumerate(data['changes']):
        op = change['op']
        label = f'changes[{index}]'
        if op in ('add_type', 'revise_types'):
            continue
        targets = change.get('ids', [change['id']] if 'id' in change else [])
        expected = 'article' if 'article' in op else 'fact'
        for identity in targets:
            target = by_id.get(identity)
            if target is None or target.get('record') != expected:
                found.append(f'{label}: {expected} {identity!r} does not exist')
            elif not current(target) or identity in touched:
                found.append(f'{label}: {expected} {identity!r} is already superseded or retired')
            touched.add(identity)
        citations = change.get('citations', change.get('fact', {}).get('citations', []))
        inherited = set()
        grooming_references = session_kind == 'grooming' and (
            op == 'supersede_fact' or (op == 'retire_fact'
                                      and original.get(change['id'], {}).get('scope', {}).get('level') == 'world'))
        if grooming_references:
            inherited = {citation for identity in targets for citation in
                         original.get(identity, {}).get('citations', [])}
        cited_positions = {}
        for citation in citations:
            if citation in frames:
                cited_positions[citation] = recorded_frames.get(citation, frames[citation])
            elif citation in inherited:
                if citation in recorded_frames:
                    cited_positions[citation] = recorded_frames[citation]
                else:
                    found.append(f'{label}: inherited citation {citation!r} has no recorded provenance')
            else:
                found.append(f'{label}: citation {citation!r} is outside the trace window'
                             + (' and the replaced facts' if grooming_references and op == 'supersede_fact'
                                else ' and the retired fact' if grooming_references else ''))
        if op.startswith('retire_'):
            target = by_id.get(change['id'])
            if target is not None:
                if (target.get('scope', {}).get('level') == 'world' and len(cited_positions) == len(citations)
                        and op == 'retire_fact'):
                    try:
                        if _citation_world(citations, sessions) != target['scope']['world']:
                            raise ValueError('retirement citations must belong to the fact\'s world')
                    except ValueError as error:
                        found.append(f'{label}: {error}')
                target['retired'] = dict(reason=change['reason'], citations=citations,
                                         published_in=version, session=session_id)
            continue
        item = dict(change[expected], published_in=version, session=session_id)
        identity = item['id']
        if identity in by_id or identity in reserved:
            found.append(f'{label}: {expected} id {identity!r} is not new')
        if expected == 'fact':
            if item['scope']['game'] != repo.game:
                found.append(f'{label}: scope game {item["scope"]["game"]!r} is not {repo.game!r}')
            if len(cited_positions) == len(citations):
                item['seen'] = max(cited_positions.values(), key=lambda p: p['order'])
                if item['scope']['level'] == 'world':
                    try:
                        item['scope'] = dict(item['scope'], world=_citation_world(citations, sessions))
                    except ValueError as error:
                        found.append(f'{label}: {error}')
        for target in targets:
            if target in by_id:
                if expected == 'fact' and 'scope' in by_id[target] and item['scope'] != by_id[target]['scope']:
                    found.append(f'{label}: supersession requires the same fact scope')
                by_id[target]['superseded_by'] = identity
        records.append(item)
        by_id[identity] = item
    if found:
        return records, list(types.values()), found
    facts = {item['id']: item for item in records if item['record'] == 'fact' and current(item)}
    game_facts = {identity: item for identity, item in facts.items() if item['scope']['level'] == 'game'}
    articles = [item for item in records if item['record'] == 'article' and current(item)]
    redefined = {name for name in base_types & types.keys() if types[name]['published_in'] == version}
    for item in records:
        if item['record'] != 'fact':
            continue
        identity = item['id']
        if (identity in facts or item['published_in'] == version) and item['type'] not in types:
            found.append(f'fact {item["id"]!r}: unknown type {item["type"]!r}')
        if identity in facts and identity in original and identity not in assigned and original[identity]['type'] in redefined:
            found.append(f'fact {identity!r}: assignment required for redefined type {original[identity]["type"]!r}')
    titles = [item['title'] for item in articles]
    if len(titles) != len(set(titles)):
        found.append('articles: current titles must be unique (one article per subject)')
    filed: set[str] = set()
    for article in (item for item in records if item['record'] == 'article'):
        cited = {identity for claim in article['body'] for identity in claim['facts']}
        if not current(article):
            if any(by_id.get(i, {}).get('scope', {}).get('level') != 'game' for i in cited):
                found.append(f'article {article["id"]!r}: articles may cite only game facts')
            continue
        for identity in sorted(cited):
            if identity not in facts:
                found.append(f'article {article["id"]!r}: fact {identity!r} is not current')
            elif identity not in game_facts:
                found.append(f'article {article["id"]!r}: articles may cite only game facts')
        for title in article['links']:
            if title == article['title']:
                found.append(f'article {article["id"]!r}: link to itself is not allowed')
            elif title not in titles:
                found.append(f'article {article["id"]!r}: link {title!r} does not resolve')
        filed.update(cited)
        if cited <= game_facts.keys():
            article['last_confirmed'] = max((facts[f]['seen'] for f in cited), key=lambda p: p['order'])
    if session_kind == 'grooming' and game_facts.keys() - filed:
        found.append(f'grooming: unfiled current facts {sorted(game_facts.keys() - filed)!r}')
    return records, list(types.values()), found


def _coverage(coverage: object) -> dict:
    if not (isinstance(coverage, dict) and set(coverage) == _COVERAGE_KEYS and coverage['schema'] == COVERAGE
            and _text(coverage['session']) and (coverage['actor'] is None or _text(coverage['actor']))
            and (coverage['last_step'] is None or type(coverage['last_step']) is int)):
        raise KnowledgeError(f'coverage must be a {COVERAGE} stamp from the runner')
    return coverage


def _publication(provenance: dict, records: list[dict], types: list[dict], coverage: dict,
                 frames: dict[str, dict], session_kind: str, data: dict) -> dict[str, bytes]:
    coverage = _coverage(coverage)
    for frame_id, position in frames.items():
        provenance['frames'].setdefault(frame_id, position)
    if session_kind == 'admission':
        citations = {c for change in data['changes'] for c in
                     change.get('citations', change.get('fact', {}).get('citations', []))}
        previous = provenance.get('last_admission', {})
        if previous.get('coverage', {}).get('session') == coverage['session']:
            citations.update(previous['citations'])
        provenance['last_admission'] = dict(coverage=coverage, citations=sorted(citations))
    return {'facts.jsonl': ''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in records).encode(),
            'coverage.json': (json.dumps(coverage, indent=2) + '\n').encode(),
            'provenance.json': (json.dumps(provenance, indent=2) + '\n').encode(),
            'ontology/types.json': (json.dumps(types, indent=2, ensure_ascii=False) + '\n').encode()}


def gate(repo: Repository, submission_dir: Path, *, session_id: str,
         window_frames: dict[str, dict], coverage: dict, session_kind: str,
         session_labels: dict[str, dict] | None = None) -> dict:
    """Check and publish one submission. `coverage` is the runner's stamp of what the session read;
    it is written beside the facts with the version, and a submission has no way to set it."""
    if session_kind not in ('admission', 'grooming'):
        raise KnowledgeError('unknown session kind')
    if session_labels is None:
        session_labels = getattr(window_frames, 'sessions', None)
    journal(repo)
    submission_dir = Path(submission_dir)
    data, diagnostics = _well_formed(submission_dir)
    raw = data
    if raw is None:
        parsed, _ = _parse(submission_dir / 'submission.json')
        raw = parsed if isinstance(parsed, dict) else None
    base = raw.get('base_version') if raw else None
    drafts = raw.get('from_drafts') if raw else None
    verdict = {
        'schema': VERDICT, 'operation': 'submission', 'operation_id': uuid.uuid4().hex,
        'submission': submission_dir.name, 'session': session_id, 'status': 'rejected',
        'base_version': base if isinstance(base, str) and _VERSION.fullmatch(base) else None,
        'restored_from': None, 'version': None,
        'from_drafts': drafts if isinstance(drafts, list)
        and all(isinstance(item, str) and DRAFT_ID.fullmatch(item) for item in drafts) else [],
        'diagnostics': diagnostics,
    }
    attempted_version = None
    try:
        if data is not None:
            current = repo.published()
            snapshots, reserved, records_by_version, recorded_sessions = _history(repo)
            if data['base_version'] != current:
                diagnostics.append(f'stale base: submission is based on {data["base_version"]}'
                                   f' but the published version is {current}')
            else:
                version = f'v{int(current[1:]) + 1}'
                try:
                    provenance = json.loads(snapshots[current]['provenance.json'])
                    sessions = {identity: {field: row[field] for field in _SESSION_KEYS}
                                for identity, row in (session_labels or {}).items()}
                    _merge_sessions(recorded_sessions, sessions)
                    provenance['sessions'].update(sessions)
                    records, types, problems = _apply(repo, data, version, session_id, window_frames,
                                                      session_kind, reserved, provenance)
                    diagnostics.extend(problems)
                    if not problems:
                        files = _publication(provenance, records, types, coverage, window_frames, session_kind, data)
                        _validate_snapshot(snapshots[current] | files, repo.game, version,
                                           records_by_version, recorded_sessions)
                except KnowledgeError:
                    raise
                except (ValueError, KeyError, TypeError, RecursionError) as error:
                    raise KnowledgeError(f'invalid candidate snapshot: {error}') from error
            if not diagnostics:
                summary = data['summary'].strip().splitlines()[0] if data['summary'].strip() \
                    else 'no summary'
                message = (f'Publish {version}: {summary!r}\n\noperation: {verdict["operation_id"]}\nsession: {session_id}\n'
                           f'submission: {submission_dir.name!r}')
                repo.reconcile()
                attempted_version = version
                published = repo.commit(files, message)
                verdict['status'] = 'published'
                verdict['version'] = published
    except (KnowledgeError, OSError, UnicodeError) as error:
        if attempted_version is not None:
            verdict['status'], verdict['version'] = _failed_publication(repo, attempted_version)
        diagnostics.append(f'publication failed: {error}')
    repo.state.mkdir(parents=True, exist_ok=True)
    try:
        with (repo.state / 'gate.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(verdict, ensure_ascii=False) + '\n')
    except OSError:
        verdict['status'] = 'unknown'
        diagnostics.append('result reporting failed')
    return verdict


def restore(repo: Repository, *, expected_base: str, target: str) -> dict:
    """Restore an existing compatible snapshot while holding the session writer lock."""
    if not all(isinstance(v, str) and _VERSION.fullmatch(v) for v in (expected_base, target)):
        raise KnowledgeError('restore versions must be version tags')
    repo.state.mkdir(parents=True, exist_ok=True)
    with (repo.state / 'lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise KnowledgeError('Another curator session holds this repository') from error
        journal(repo)
        result = dict(schema=VERDICT, operation='restore', operation_id=uuid.uuid4().hex,
                      status='rejected', base_version=expected_base, restored_from=target, version=None,
                      submission=None, session=None, from_drafts=[], diagnostics=[])
        next_version = None
        failure = 'incompatible or unavailable history'
        try:
            current = repo.published()
            snapshots, _, _, _ = _history(repo)
            if expected_base != current:
                failure = 'stale base'
                raise KnowledgeError('stale base')
            if target not in snapshots:
                failure = 'unknown target'
                raise KnowledgeError('unknown target')
            failure = 'publication failed'
            repo.reconcile()
            if snapshots[target] == snapshots[current]:
                result['status'], result['version'] = 'unchanged', current
            else:
                next_version = f'v{int(current[1:]) + 1}'
                message = (f'Restore {target} as {next_version}\n\noperation: {result["operation_id"]}\n'
                           f'base: {current}\nrestored-from: {target}')
                result['version'] = repo.commit_snapshot(snapshots[target], message)
                result['status'] = 'published'
        except (KnowledgeError, OSError, UnicodeError) as error:
            if next_version:
                result['status'], result['version'] = _failed_publication(repo, next_version)
            result['diagnostics'].append(failure)
        try:
            with (repo.state / 'gate.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + '\n')
        except OSError:
            result['status'] = 'unknown'
            result['diagnostics'].append('result reporting failed')
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Restore a compatible published knowledge snapshot')
    parser.add_argument('operation', choices=['restore'])
    parser.add_argument('root', type=Path)
    parser.add_argument('--game', required=True)
    parser.add_argument('--expected-base', required=True)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    print(json.dumps(restore(Repository(args.root, args.game), expected_base=args.expected_base, target=args.target)))


if __name__ == '__main__':
    main()
