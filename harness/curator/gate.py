"""Validate tagged curator history and publish checked snapshots under the writer lock."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import json
from pathlib import Path
import re
import uuid

from . import check
from .check import DRAFT_ID, FACT as FACT, SUBMISSION as SUBMISSION, VERSION as _VERSION, current as current
from .knowledge import SCHEMA, KnowledgeError, Repository, _knowledge_metadata

VERDICT = 'curator-gate/2'
COVERAGE = 'curator-coverage/2'
_COVERAGE_KEYS = {'schema', 'session', 'actor', 'last_step'}

_RESULT_KEYS = {'schema', 'operation', 'operation_id', 'status', 'base_version', 'restored_from',
                'version', 'submission', 'session', 'from_drafts', 'diagnostics'}


def journal(repo: Repository) -> list[dict]:
    """Read the active journal only under the current result contract."""
    path = repo.state / 'gate.jsonl'
    if not path.exists():
        return []
    try:
        rows = [json.loads(line) for line in path.read_text().split('\n') if line]
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


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _coverage(coverage: object) -> dict:
    if not (isinstance(coverage, dict) and set(coverage) == _COVERAGE_KEYS and coverage['schema'] == COVERAGE
            and _text(coverage['session']) and (coverage['actor'] is None or _text(coverage['actor']))
            and (coverage['last_step'] is None or type(coverage['last_step']) is int)):
        raise KnowledgeError(f'coverage must be a {COVERAGE} stamp from the runner')
    return coverage


def _failed_publication(repo: Repository, version: str) -> tuple[str, str | None]:
    """A failed lookup cannot establish that publication did not happen."""
    try:
        return ('unknown', version) if version in repo._tags() else ('rejected', None)
    except KnowledgeError:
        return 'unknown', None


@dataclass(frozen=True)
class _ValidatedHistory:
    game: str
    commits: dict[str, bytes]
    origins: dict[str, tuple[str, str, str]]
    identities: set[str]
    state_keys: set[str]
    reservations: dict


def _history(repo: Repository) -> tuple[dict[str, dict[str, bytes]], set[str], dict, set[str]]:
    """Verify the tagged objects on every call and validate new snapshots in causal order."""
    required = {'knowledge.json', 'facts.jsonl', 'provenance.json', 'programs/.keep', 'tests/.keep'}
    snapshots, commits = {}, {}
    for version, oid, files in repo._verified_snapshots():
        snapshots[version], commits[version] = files, oid

    cached = repo._validated_history
    if cached is not None and cached.game != repo.game:
        cached = None
    if cached is None:
        origins, identities, keys, reservations = {}, set(), set(), check.empty_reservations()
    else:
        for version, oid in cached.commits.items():
            if commits.get(version) != oid:
                raise KnowledgeError(f'incompatible history at {version}: published commit changed')
        origins, identities, keys = cached.origins.copy(), cached.identities.copy(), cached.state_keys.copy()
        reservations = deepcopy(cached.reservations)

    schema_valid: set[str] = set()
    for version, files in snapshots.items():
        if cached is not None and version in cached.commits:
            continue
        try:
            if set(files) not in (required, required | {'coverage.json'}):
                raise ValueError('unsupported snapshot layout')
            if files['programs/.keep'] or files['tests/.keep']:
                raise ValueError('unsupported program or test content')
            if _knowledge_metadata(files['knowledge.json']) != {'schema': SCHEMA, 'game': repo.game}:
                raise ValueError('foreign knowledge metadata')
            provenance = json.loads(files['provenance.json'])
            raw_lines = [line for line in files['facts.jsonl'].decode().split('\n') if line.strip()]
            rows = [json.loads(line) for line in raw_lines]
            records = check.validate_snapshot(rows, provenance, repo.game, version,
                                              _raw_lines=raw_lines, _schema_valid=schema_valid)
            if 'coverage.json' in files:
                _coverage(json.loads(files['coverage.json']))
            if 'last_admission' in provenance:
                admission = provenance['last_admission']
                citations = admission['citations']
                if (set(admission) != {'coverage', 'citations'} or not isinstance(citations, list)
                        or len(citations) != len(set(citations))
                        or any(frame not in provenance['frames'] for frame in citations)):
                    raise ValueError('invalid admission provenance')
                _coverage(admission['coverage'])
            check._merge_sessions(reservations, provenance)
            for identity, record in records.items():
                claimed = record['published_in'], record['record'], record['session']
                if claimed[0] == version:
                    origins.setdefault(identity, claimed)
                if origins.get(identity) != claimed:
                    raise ValueError('invalid record origin')
        except (ValueError, KeyError, TypeError, RecursionError) as error:
            raise KnowledgeError(f'incompatible history at {version}: {error}') from error
        identities.update(check.owner(record) for record in rows)
        keys.update(check.state_keys(rows))
        if identities & keys:
            raise KnowledgeError(f'incompatible history at {version}: state_key collides with record ID or slug')
    repo._validated_history = _ValidatedHistory(repo.game, commits, origins, identities, keys, reservations)
    return snapshots, identities.copy(), deepcopy(reservations), keys.copy()


def _publication(candidate: check.Candidate, coverage: dict, session_kind: str) -> dict[str, bytes]:
    coverage = _coverage(coverage)
    provenance = candidate.provenance
    if session_kind == 'admission':
        citations = set(candidate.admission_citations)
        previous = provenance.get('last_admission', {})
        if previous.get('coverage', {}).get('session') == coverage['session']:
            citations.update(previous['citations'])
        provenance['last_admission'] = dict(coverage=coverage, citations=sorted(citations))
    return {'facts.jsonl': ''.join(json.dumps(item, ensure_ascii=False) + '\n'
                                   for item in candidate.records).encode(),
            'coverage.json': (json.dumps(coverage, indent=2) + '\n').encode(),
            'provenance.json': (json.dumps(provenance, indent=2) + '\n').encode()}


def gate(repo: Repository, submission_dir: Path, *, session_id: str,
         window_frames: dict[str, dict], coverage: dict, session_kind: str,
         session_labels: dict[str, dict] | None = None) -> dict:
    """Check and publish one submission, with a software-owned coverage stamp."""
    if session_kind not in check.SESSION_KINDS:
        raise KnowledgeError('unknown session kind')
    if session_labels is None:
        session_labels = getattr(window_frames, 'sessions', {})
    journal(repo)
    submission_dir = Path(submission_dir)
    data, diagnostics, _ = check.read_submission(submission_dir)
    base = data.get('base_version') if isinstance(data, dict) else None
    drafts = data.get('from_drafts') if isinstance(data, dict) else None
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
        if not diagnostics:
            base = repo.published()
            diagnostics.extend(check.base_diagnostics(data, base))
        if not diagnostics:
            snapshots, reserved_ids, reserved_sessions, reserved_state_keys = _history(repo)
            snapshot = snapshots[base]
            records = [json.loads(line) for line in snapshot['facts.jsonl'].decode().split('\n') if line.strip()]
            candidate, problems = check.evaluate(
                data, base_records=records, base_provenance=json.loads(snapshot['provenance.json']),
                game=repo.game, base_version=base, reserved_ids=reserved_ids, reserved_sessions=reserved_sessions,
                session_id=session_id, window_frames=window_frames, session_kind=session_kind,
                session_labels=session_labels, declared_axes=check.declared_axes(reserved_sessions, session_labels),
                reserved_state_keys=reserved_state_keys)
            diagnostics.extend(problems)
            if candidate is not None:
                files = _publication(candidate, coverage, session_kind)
                summary = data['summary'].strip().splitlines()[0] if data['summary'].strip() else 'no summary'
                message = (f'Publish {candidate.version}: {summary!r}\n\noperation: {verdict["operation_id"]}\n'
                           f'session: {session_id}\nsubmission: {submission_dir.name!r}')
                repo.reconcile()
                attempted_version = candidate.version
                verdict['version'] = repo.commit(files, message)
                verdict['status'] = 'published'
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
