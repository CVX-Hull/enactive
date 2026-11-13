"""Gate v0: validate a curator submission and publish it (ADR 009's coding-agent curator direction;
docs/design/curator-session.md).

Checks run in the spec's order and the first failing stage rejects, listing every problem in
that stage: well formed, base version, scope, provenance. Nothing a submission contains is
executed. Only this module commits to the knowledge repository.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat

from harness.curator.knowledge import KnowledgeError, Repository

SUBMISSION = 'curator-submission/1'
FACT = 'curator-fact/1'
TYPE = 'curator-type/1'
VERDICT = 'curator-gate/1'
MAX_CHANGES = 200
MAX_BYTES = 256 * 1024
_VERSION = re.compile(r'v(0|[1-9][0-9]*)')

_FACT_KEYS = {'schema', 'id', 'type', 'statement', 'scope', 'citations'}
_TYPE_KEYS = {'schema', 'name', 'description', 'fields'}
_OPS = {'add_fact': {'op', 'fact'}, 'supersede_fact': {'op', 'id', 'fact'},
        'add_type': {'op', 'type'}}
_TOP_KEYS = {'schema', 'base_version', 'summary', 'changes'}


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
    if not isinstance(fact, dict):
        return [f'{label}: must be an object']
    found = _extra(label, fact, _FACT_KEYS, _FACT_KEYS)
    if fact.get('schema', FACT) != FACT:
        found.append(f'{label}: schema must be {FACT!r}')
    for key in ('id', 'type', 'statement'):
        if key in fact and not _text(fact[key]):
            found.append(f'{label}: {key} must be a non-empty string')
    scope = fact.get('scope')
    if 'scope' in fact and not (isinstance(scope, dict) and isinstance(scope.get('game'), str)):
        found.append(f'{label}: scope must be an object with a string "game"')
    citations = fact.get('citations')
    if 'citations' in fact and not (isinstance(citations, list) and citations
                                    and all(_text(item) for item in citations)):
        found.append(f'{label}: citations must be a non-empty list of frame source ids')
    return found


def _check_type(label: str, kind: object) -> list[str]:
    if not isinstance(kind, dict):
        return [f'{label}: must be an object']
    found = _extra(label, kind, _TYPE_KEYS, _TYPE_KEYS)
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
                if not isinstance(change, dict) or change.get('op') not in _OPS:
                    found.append(f'{label}: unknown operation')
                    continue
                op = change['op']
                found.extend(_extra(label, change, _OPS[op], _OPS[op]))
                if op == 'add_type':
                    found.extend(_check_type(f'{label}.type', change.get('type')))
                    continue
                found.extend(_check_fact(f'{label}.fact', change.get('fact')))
                if op == 'supersede_fact' and 'id' in change and not _text(change['id']):
                    found.append(f'{label}: id must be a non-empty string')
    return (None if found else data), found


def _scope(repo: Repository, data: dict) -> list[str]:
    facts = {fact['id']: fact for fact in repo.facts()}
    known = {kind['name'] for kind in repo.types()}
    added: set[str] = set()
    found = []
    for index, change in enumerate(data['changes']):
        if change['op'] == 'add_type':
            name = change['type']['name']
            if name in known or name in added:
                found.append(f'changes[{index}]: type {name!r} already exists')
            added.add(name)
    seen: set[str] = set()
    superseded: set[str] = set()
    for index, change in enumerate(data['changes']):
        if change['op'] == 'add_type':
            continue
        label = f'changes[{index}]'
        fact = change['fact']
        if fact['scope']['game'] != repo.game:
            found.append(f'{label}: scope game {fact["scope"]["game"]!r} is not {repo.game!r}')
        if fact['type'] not in known | added:
            found.append(f'{label}: unknown type {fact["type"]!r}')
        if fact['id'] in facts or fact['id'] in seen:
            found.append(f'{label}: fact id {fact["id"]!r} is not new')
        seen.add(fact['id'])
        if change['op'] == 'supersede_fact':
            target = change['id']
            if target not in facts:
                found.append(f'{label}: superseded fact {target!r} does not exist')
            elif 'superseded_by' in facts[target] or target in superseded:
                found.append(f'{label}: fact {target!r} is already superseded')
            superseded.add(target)
    return found


def _provenance(data: dict, window_frames: set[str]) -> list[str]:
    found = []
    for index, change in enumerate(data['changes']):
        if change['op'] == 'add_type':
            continue
        for citation in change['fact']['citations']:
            if citation not in window_frames:
                found.append(f'changes[{index}]: citation {citation!r} is outside the trace window')
    return found


def _publication(repo: Repository, data: dict, session_id: str, submission: str,
                 version: str) -> dict[str, bytes]:
    facts = repo.facts()
    types = repo.types()
    by_id = {fact['id']: fact for fact in facts}
    for change in data['changes']:
        if change['op'] == 'add_type':
            types.append(dict(change['type']))
            continue
        fact = {**change['fact'], 'published_in': version, 'session': session_id}
        if change['op'] == 'supersede_fact':
            by_id[change['id']]['superseded_by'] = fact['id']
        facts.append(fact)
    lines = ''.join(json.dumps(fact, ensure_ascii=False) + '\n' for fact in facts)
    return {'facts.jsonl': lines.encode('utf-8'),
            'ontology/types.json':
                (json.dumps(types, indent=2, ensure_ascii=False) + '\n').encode('utf-8')}


def gate(repo: Repository, submission_dir: Path, *, session_id: str,
         window_frames: set[str]) -> dict:
    submission_dir = Path(submission_dir)
    data, diagnostics = _well_formed(submission_dir)
    raw = data
    if raw is None:
        parsed, _ = _parse(submission_dir / 'submission.json')
        raw = parsed if isinstance(parsed, dict) else None
    base = raw.get('base_version') if raw else None
    drafts = raw.get('from_drafts') if raw else None
    verdict = {
        'schema': VERDICT, 'submission': submission_dir.name, 'session': session_id,
        'accepted': False, 'base_version': base if isinstance(base, str) and _VERSION.fullmatch(base) else None,
        'version': None,
        'from_drafts': drafts if isinstance(drafts, list)
        and all(isinstance(item, str) and DRAFT_ID.fullmatch(item) for item in drafts) else [],
        'diagnostics': diagnostics,
    }
    try:
        if data is not None:
            current = repo.published()
            if data['base_version'] != current:
                diagnostics.append(f'stale base: submission is based on {data["base_version"]}'
                                   f' but the published version is {current}')
            else:
                diagnostics.extend(_scope(repo, data))
                if not diagnostics:
                    diagnostics.extend(_provenance(data, window_frames))
            if not diagnostics:
                version = f'v{int(current[1:]) + 1}'
                files = _publication(repo, data, session_id, submission_dir.name, version)
                summary = data['summary'].strip().splitlines()[0] if data['summary'].strip() \
                    else 'no summary'
                message = (f'Publish {version}: {summary!r}\n\nsession: {session_id}\n'
                           f'submission: {submission_dir.name!r}')
                published = repo.commit(files, message)
                verdict['accepted'] = True
                verdict['version'] = published
    except (KnowledgeError, OSError, UnicodeError) as error:
        verdict['accepted'] = False
        verdict['version'] = None
        diagnostics.append(f'publication failed: {error}')
    repo.state.mkdir(parents=True, exist_ok=True)
    with (repo.state / 'gate.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(verdict, ensure_ascii=False) + '\n')
    return verdict
