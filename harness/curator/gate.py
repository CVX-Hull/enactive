"""Gate v0: validate a curator submission and publish it (ADR 009's coding-agent curator direction;
docs/design/curator-session.md).

Checks run in the spec's order and the first failing stage rejects, listing every problem in
that stage: well formed, base version, candidate scope/provenance/references. Nothing a submission contains is
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
FACT = 'curator-fact/3'
TYPE = 'curator-type/1'
VERDICT = 'curator-gate/1'
COVERAGE = 'curator-coverage/2'
MAX_CHANGES = 200
MAX_BYTES = 256 * 1024
_VERSION = re.compile(r'v(0|[1-9][0-9]*)')

_FACT_KEYS = {'schema', 'record', 'id', 'type', 'text', 'scope', 'citations', 'subject'}
_ARTICLE_KEYS = {'schema', 'record', 'id', 'title', 'lead', 'body', 'links'}
_TYPE_KEYS = {'schema', 'name', 'description', 'fields'}
_OPS = {
    'add_fact': {'op', 'fact'}, 'supersede_fact': {'op', 'ids', 'fact'},
    'retire_fact': {'op', 'id', 'reason', 'citations'}, 'add_type': {'op', 'type'},
    'revise_types': {'op', 'action', 'names', 'types', 'assignments'},
    'add_article': {'op', 'article'}, 'revise_article': {'op', 'id', 'article'},
    'retire_article': {'op', 'id', 'reason'},
}
_TOP_KEYS = {'schema', 'base_version', 'summary', 'changes'}
_COVERAGE_KEYS = {'schema', 'session', 'actor', 'last_step'}


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
    scope = fact.get('scope')
    if 'scope' in fact and not (isinstance(scope, dict) and _text(scope.get('game'))):
        found.append(f'{label}: scope must be an object with a non-empty string "game"')
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
           frames: dict[str, dict], session_kind: str) -> tuple[list[dict], list[dict], list[str]]:
    """Build a candidate snapshot; inspect its references only, never the meaning of prose.

    Structural controls address R-GAME-COUPLING and R-REGRESSION without a semantic judge.
    """
    records = repo.records()
    types = {item['name']: item for item in repo.types()}
    by_id = {item['id']: item for item in records}
    found = []
    touched: set[str] = set()
    for index, change in enumerate(data['changes']):
        op = change['op']
        label = f'changes[{index}]'
        if op == 'add_type':
            item = change['type']
            if item['name'] in types:
                found.append(f'{label}: type {item["name"]!r} already exists')
            types[item['name']] = dict(item)
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
                types[item['name']] = dict(item)
            for identity, name in change['assignments'].items():
                target = by_id.get(identity)
                if target is None or target.get('record') != 'fact' or not current(target):
                    found.append(f'{label}: assignment fact {identity!r} is not current')
                else:
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
        for citation in citations:
            if citation not in frames:
                found.append(f'{label}: citation {citation!r} is outside the trace window')
        if op.startswith('retire_'):
            if change['id'] in by_id:
                by_id[change['id']]['retired'] = dict(reason=change['reason'], citations=citations,
                                                     published_in=version, session=session_id)
            continue
        item = dict(change[expected], published_in=version, session=session_id)
        identity = item['id']
        if identity in by_id:
            found.append(f'{label}: {expected} id {identity!r} is not new')
        if expected == 'fact':
            if item['scope']['game'] != repo.game:
                found.append(f'{label}: scope game {item["scope"]["game"]!r} is not {repo.game!r}')
            if all(citation in frames for citation in citations):
                item['seen'] = max((frames[c] for c in citations), key=lambda p: p['order'])
        for target in targets:
            if target in by_id:
                by_id[target]['superseded_by'] = identity
        records.append(item)
        by_id[identity] = item
    if found:
        return records, list(types.values()), found
    facts = {item['id']: item for item in records if item['record'] == 'fact' and current(item)}
    articles = [item for item in records if item['record'] == 'article' and current(item)]
    for item in facts.values():
        if item['type'] not in types:
            found.append(f'fact {item["id"]!r}: unknown type {item["type"]!r}')
    titles = [item['title'] for item in articles]
    if len(titles) != len(set(titles)):
        found.append('articles: current titles must be unique (one article per subject)')
    filed: set[str] = set()
    for article in articles:
        cited = {identity for claim in article['body'] for identity in claim['facts']}
        for identity in sorted(cited):
            if identity not in facts:
                found.append(f'article {article["id"]!r}: fact {identity!r} is not current')
        for title in article['links']:
            if title not in titles:
                found.append(f'article {article["id"]!r}: link {title!r} does not resolve')
        filed.update(cited)
        if cited <= facts.keys():
            article['last_confirmed'] = max((facts[f]['seen'] for f in cited), key=lambda p: p['order'])
    if session_kind == 'grooming' and facts.keys() - filed:
        found.append(f'grooming: unfiled current facts {sorted(facts.keys() - filed)!r}')
    return records, list(types.values()), found


def _coverage(coverage: object) -> dict:
    if not (isinstance(coverage, dict) and set(coverage) == _COVERAGE_KEYS and coverage['schema'] == COVERAGE
            and _text(coverage['session']) and (coverage['actor'] is None or _text(coverage['actor']))
            and (coverage['last_step'] is None or type(coverage['last_step']) is int)):
        raise KnowledgeError(f'coverage must be a {COVERAGE} stamp from the runner')
    return coverage


def _publication(repo: Repository, records: list[dict], types: list[dict], coverage: dict,
                 frames: dict[str, dict], session_kind: str, data: dict) -> dict[str, bytes]:
    coverage = _coverage(coverage)
    provenance = repo.provenance()
    provenance['frames'].update(frames)
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
         window_frames: dict[str, dict], coverage: dict, session_kind: str = 'admission') -> dict:
    """Check and publish one submission. `coverage` is the runner's stamp of what the session read;
    it is written beside the facts with the version, and a submission has no way to set it."""
    if session_kind not in ('admission', 'grooming'):
        raise KnowledgeError('unknown session kind')
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
            foreign = sorted(str(item.get('id')) for item in repo.records() if item.get('schema') != FACT)
            if foreign:
                # One current contract: a store that holds facts of another contract is not published into.
                diagnostics.append(f'publication refused: published facts {foreign[:5]} are not {FACT}; '
                                   'start a new repository')
            elif data['base_version'] != current:
                diagnostics.append(f'stale base: submission is based on {data["base_version"]}'
                                   f' but the published version is {current}')
            else:
                version = f'v{int(current[1:]) + 1}'
                records, types, problems = _apply(repo, data, version, session_id, window_frames, session_kind)
                diagnostics.extend(problems)
            if not diagnostics:
                files = _publication(repo, records, types, coverage, window_frames, session_kind, data)
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
