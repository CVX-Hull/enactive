"""Hash-bound, draft-free admission prefixes for an explicitly approved P1 recovery.

This does not authorize a run. Original stopped schedules remain stopped. A new run
may import verified published Git history and exact gate feedback, then execute its
missing suffix on fresh workspaces. No failed workspace or draft history is imported.
Nothing here prints scientific content.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from decimal import Decimal, DecimalException
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from harness.curator.knowledge import KnowledgeError, Repository, _git, _number

SCHEMA = 'p1-retained-prefix/1'
SCHEDULE_SCHEMA = 'p1-schedule/2'
EVIDENCE_SCHEDULE_SCHEMA = 'p1-schedule/1'  # Explicit offline import only, never a live-reader fallback.


class RetainedError(ValueError):
    """Retained state is incomplete, changed, or unsafe to import."""


def _need(condition, reason):
    if not condition:
        raise RetainedError(reason)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise RetainedError('retained JSON is unreadable') from None


def _rows(path: Path) -> list[dict]:
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        raise RetainedError('retained journal is unreadable') from None
    _need(all(isinstance(row, dict) for row in rows), 'retained journal rows must be objects')
    return rows


def _amount(value) -> Decimal:
    try:
        found = Decimal(str(value))
    except (DecimalException, TypeError, ValueError):
        raise RetainedError('invalid retained amount') from None
    _need(found.is_finite() and found >= 0, 'invalid retained amount')
    return found


def _inside(path: Path, root: Path) -> Path:
    path = path.absolute()
    resolved = path.resolve()
    _need(path == resolved and root in resolved.parents, 'retained path leaves its declared root or follows a link')
    return resolved


@contextmanager
def _lock(repo: Repository):
    _need(repo.state.is_dir(), 'retained repository state is absent')
    path = repo.state/'lock'
    _need(path.is_file() and not path.is_symlink(), 'retained repository lock is absent or unsafe')
    with path.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RetainedError('retained repository is busy') from None
        yield


def _refs(repo: Repository) -> dict[str, str]:
    try:
        refs = {name: commit for commit, name in (line.split() for line in
                _git(repo.path, 'show-ref', '--heads', '--tags').decode().splitlines())}
        _need(not _git(repo.path, 'status', '--porcelain', '--untracked-files=all').strip(),
              'retained published working tree is dirty')
        return refs
    except KnowledgeError:
        raise RetainedError('retained Git history could not be verified') from None


@contextmanager
def _validated_seed(spec: dict, runtime: Path):
    root = _inside(runtime/spec['root'], runtime/'knowledge'/'p1')
    repo = Repository(root, spec['game'])
    _inside(repo.path, root)
    _inside(repo.state, root)
    _inside(repo.path/'.git', repo.path)
    _need((repo.path/'.git').is_dir(), 'retained knowledge is not an owned Git directory')
    gate = _inside(runtime/spec['gate'], repo.state)
    _need(gate == repo.state/'gate.jsonl', 'retained gate feedback path differs from its repository')
    with _lock(repo):
        _need(_refs(repo) == spec['refs'] and _hash(gate) == spec['gate_sha256'],
              'retained Git identities or gate feedback changed')
        for directory in ('drafts', 'drafts-archive', 'drafts-staging', 'workspaces'):
            path = _inside(repo.state/directory, repo.state)
            _need(path.is_dir() and not any(path.iterdir()), 'retained state is no longer empty')
        yield repo


def _inspect(schedule_path: Path, runtime: Path, admissions: dict[str, tuple[str, ...]], repeat: int,
             frozen: Path) -> dict:
    """Validate a stopped storage-loss run and fingerprint every reused receipt/state input."""
    runtime = runtime.resolve()
    schedule_path = _inside(schedule_path, runtime/'curator-shadow'/'p1')
    source = _json(schedule_path)
    names = list(admissions)
    _need(isinstance(source, dict) and source.get('schema') == EVIDENCE_SCHEDULE_SCHEMA
          and type(source.get('repeat')) is int and source['repeat'] == repeat
          and source.get('stopped') == 'session-aborted' and source.get('lineage_order') == names,
          'source is not the selected stopped repeat in the declared lineage order')
    _need(set(source.get('lineages', {})) == set(names), 'source lineage coverage differs')
    repositories = {}
    for name in names:
        root = _inside(runtime/source['knowledge']/name, runtime/'knowledge'/'p1')
        repo = repositories[name] = Repository(root, source['game'])
        _inside(repo.path, root)
        _inside(repo.state, root)
        _inside(repo.path/'.git', repo.path)
        _need((repo.path/'.git').is_dir(), 'retained knowledge is not an owned Git directory')
    files = {str(schedule_path.relative_to(runtime)): _hash(schedule_path)}

    def keep(path):
        path = _inside(path, runtime)
        files[str(path.relative_to(runtime))] = _hash(path)
        return path

    prefixes, next_inputs, seeds = {}, {}, {}
    configurations = set()
    host_config = None
    failures = 0
    with ExitStack() as locks:
        for name in names:
            locks.enter_context(_lock(repositories[name]))
        for name, ordered in admissions.items():
            repo = repositories[name]
            entries = source['lineages'][name].get('sessions', [])
            _need(entries and [entry.get('session') for entry in entries] == list(ordered[:len(entries)]),
                  'retained admissions have a hole, duplicate, or unexpected order')
            prefix, feedback, failed = [], [], False
            for index, entry in enumerate(entries):
                summary_path = keep(schedule_path.parent/entry['summary'])
                _need(summary_path.parent == schedule_path.parent/name/entry['session'],
                      'retained summary belongs to another admission')
                summary = _json(summary_path)
                configurations.add((summary.get('model'), summary.get('effort')))
                base_path = keep(schedule_path.parent/'host-config'/f'{summary["arm"]}.json')
                if host_config is None:
                    host_config = str(base_path.relative_to(runtime))
                _need(base_path == runtime/host_config, 'retained source mixes host configurations')
                configured = _json(keep(schedule_path.parent/'host-config'/f'{entry["session"]}.json'))
                _need(configured == dict(_json(base_path), budget_usd=summary['host_budget_usd']),
                      'retained admission configuration has changes beyond its declared budget')
                record_dir = _inside(Path(summary['record']), repo.state/'sessions')
                record = _json(keep(record_dir/'close-out.json'))
                manifest = _json(keep(record_dir/'manifest.json'))
                _need(record['manifest'] == manifest and manifest.get('schema') == 'container-manifest/1'
                      and manifest.get('kind') == 'curator-session', 'retained manifest and close-out differ')
                life = manifest['lifecycle']
                _need(all(summary['sandbox'].get(key) == life.get(key) for key in ('stopped', 'returncode', 'survivors'))
                      and summary.get('errors') == life.get('errors') and summary.get('refused') == life.get('refused')
                      and life.get('errors') == [] and life.get('refused') == [] and life.get('survivors') == []
                      and summary['session_id'] == manifest['id']
                      and summary['published_before'] == manifest['pinned']['knowledge_version']
                      and summary['published_after'] == record['published_after'],
                      'retained summary contradicts authoritative lifecycle or publication evidence')
                _need(_hash(keep(record_dir/'brief.md')) == manifest['pinned']['brief_sha256'],
                      'retained brief changed')
                ledger = _rows(keep(summary_path.parent/'proxy-ledger.jsonl'))
                closure = _json(keep(summary_path.parent/'proxy-close.json'))
                _need(all(summary['proxy'].get(key) == closure.get(key) for key in
                          ('settled', 'unsettled_requests', 'pending_reserved_usd', 'receipt_error', 'revoked', 'breaches')),
                      'retained proxy summary and closure disagree')
                debit = sum((_amount(row.get('charged')) for row in ledger), Decimal(0))
                _need(closure.get('schema') == 'curator-proxy-close/1'
                      and closure.get('settled') is True and type(closure.get('unsettled_requests')) is int
                      and closure['unsettled_requests'] == 0
                      and _amount(closure.get('pending_reserved_usd')) == 0
                      and closure.get('receipt_error') is None and closure.get('revoked') is False
                      and type(closure.get('breaches')) is int and closure['breaches'] == 0
                      and summary.get('stopped_by_cap') is False
                      and summary['sandbox'].get('survivors') == []
                      and not summary.get('errors') and not summary.get('refused'),
                      'retained admission has unsafe closure or cap evidence')
                _need(debit == _amount(summary['cost_usd']) == _amount(entry['cost_usd'])
                      == _amount(closure['spent_snapshot_usd']), 'retained cost receipts disagree')
                _need(not any(row.get('refused') or row.get('breach') or row.get('status') not in (200, 429)
                              or (row.get('usage_missing') and row.get('status') != 429) for row in ledger),
                      'retained admission contains an unsupported failed request')
                _need(not any(record.get('drafts', {}).values()), 'retained admission touched draft state')
                state = entry.get('session_state')
                _need(state == summary.get('session_state') == manifest['lifecycle'].get('state'),
                      'retained session states disagree')
                _need(summary['published_before'] == (prefix[-1]['published_after'] if prefix else 'v0')
                      and entry['published_after'] == summary['published_after'], 'retained publication chain differs')
                if state == 'sealed':
                    _need(not failed and type(summary['sandbox'].get('returncode')) is int
                          and summary['sandbox']['returncode'] == 0
                          and summary['sandbox'].get('stopped') is None, 'sealed prefix has an abnormal host exit')
                    _need(entry['published_after'] is not None, 'retained publication is absent')
                    prefix.append(dict(entry, retained_from=dict(schedule=str(schedule_path.relative_to(runtime)),
                                                               source_schema=EVIDENCE_SCHEDULE_SCHEMA,
                                                               schedule_sha256=_hash(schedule_path),
                                                               summary_sha256=_hash(summary_path))))
                    feedback.extend(record['verdicts'])
                else:
                    _need(state == 'aborted' and not failed and index == len(entries) - 1
                          and name == names[-1] and summary['sandbox'].get('stopped') == 'volume free-space floor'
                          and summary['published_before'] == summary['published_after']
                          and not record['verdicts'], 'source loss is not a clean, unpublished final storage stop')
                    failed = True
                    failures += 1
                    next_inputs[name] = dict(session=entry['session'], memory_until=entry['memory_until'],
                                             brief_sha256=manifest['pinned']['brief_sha256'],
                                             trace_manifest_sha256=manifest['pinned']['trace_manifest_sha256'])
            _need(prefix, 'each selected lineage needs a nonempty sealed prefix')
            _need(failed or len(prefix) == len(ordered), 'source stops before its recorded loss')
            gate = keep(repo.state/'gate.jsonl')
            _need(_rows(gate) == feedback, 'gate feedback includes missing, altered, or failed-admission contributions')
            for directory in ('drafts', 'drafts-archive', 'drafts-staging', 'workspaces'):
                path = repo.state/directory
                _inside(path, repo.state)
                _need(path.is_dir() and not any(path.iterdir()), 'retained draft/workspace state is not empty')
            refs = _refs(repo)
            version = prefix[-1]['published_after']
            expected_tags = {f'refs/tags/v{i}' for i in range(int(version[1:]) + 1)}
            _need(set(refs) == {'refs/heads/main', *expected_tags}
                  and refs['refs/heads/main'] == refs['refs/tags/'+version],
                  'retained refs include extra history or an unpublished tip')
            prefixes[name] = prefix
            seeds[name] = dict(root=str(repo.path.parent.relative_to(runtime)), game=repo.game,
                               refs=refs, gate=str(gate.relative_to(runtime)), gate_sha256=_hash(gate))
    _need(failures == 1, 'retained source needs exactly one recorded storage loss')
    _need(len(configurations) == 1, 'retained source mixes model configurations')
    model, effort = configurations.pop()
    return dict(schema=SCHEMA, repeat=repeat, lineage_order=names, source_schedule=str(schedule_path.relative_to(runtime)),
                source_schedule_sha256=_hash(schedule_path), frozen_sha256=_hash(frozen), files=files,
                model=model, effort=effort, host_config=host_config,
                prefixes=prefixes, next_inputs=next_inputs, seeds=seeds)


def inspect(schedule_path: Path, runtime: Path, admissions: dict[str, tuple[str, ...]], repeat: int,
            frozen: Path) -> dict:
    try:
        return _inspect(schedule_path, runtime, admissions, repeat, frozen)
    except RetainedError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, OSError, ValueError, KnowledgeError):
        raise RetainedError('retained evidence has an invalid structure or unavailable file') from None


def prepare(schedule: Path, runtime: Path, admissions: dict[str, tuple[str, ...]], repeat: int,
            frozen: Path, out: Path) -> dict:
    plan = inspect(schedule, runtime, admissions, repeat, frozen)
    _inside(out, runtime.resolve())
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x') as stream:
        json.dump(plan, stream, indent=1, sort_keys=True)
        stream.write('\n')
    return dict(lineages=len(plan['prefixes']), retained_sessions=sum(map(len, plan['prefixes'].values())),
                remaining_sessions=sum(len(admissions[name]) - len(plan['prefixes'][name]) for name in admissions),
                plan_sha256=_hash(out))


def load(path: Path, digest: str, runtime: Path, admissions: dict[str, tuple[str, ...]], repeat: int,
         frozen: Path) -> dict:
    """Validate the approved current plan and fingerprints, never reparse historical /1."""
    try:
        return _load(path, digest, runtime.resolve(), admissions, repeat, frozen)
    except RetainedError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, OSError, ValueError, KnowledgeError):
        raise RetainedError('approved retained-prefix plan is invalid or unavailable') from None


def _load(path: Path, digest: str, runtime: Path, admissions: dict[str, tuple[str, ...]], repeat: int,
          frozen: Path) -> dict:
    _inside(path, runtime.resolve())
    _need(_hash(path) == digest, 'retained plan changed from its approved digest')
    plan = _json(path)
    _need(isinstance(plan, dict) and plan.get('schema') == SCHEMA
          and set(plan) == {'schema', 'repeat', 'lineage_order', 'source_schedule', 'source_schedule_sha256',
                            'frozen_sha256', 'files', 'model', 'effort', 'host_config', 'prefixes', 'next_inputs', 'seeds'},
          'unsupported retained-prefix plan')
    names = list(admissions)
    _need(type(plan['repeat']) is int and plan['repeat'] == repeat and plan['lineage_order'] == names
          and set(plan['prefixes']) == set(plan['seeds']) == set(names)
          and set(plan['next_inputs']) == {names[-1]}, 'retained plan coverage differs')
    _need(_hash(frozen) == plan['frozen_sha256'], 'retained frozen inputs changed since the plan')
    source = _inside(runtime/plan['source_schedule'], runtime/'curator-shadow'/'p1')
    _need(plan['files'].get(plan['source_schedule']) == plan['source_schedule_sha256']
          and plan['host_config'] in plan['files'], 'retained source fingerprints are missing')
    for relative, sha in plan['files'].items():
        _need(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{64}', sha), 'invalid retained file fingerprint')
        _need(_hash(_inside(runtime/relative, runtime)) == sha, 'retained evidence file changed since the plan')
    for name, ordered in admissions.items():
        prefix = plan['prefixes'][name]
        _need(prefix and [entry['session'] for entry in prefix] == list(ordered[:len(prefix)]),
              'retained plan prefix has a hole, duplicate or unexpected order')
        _need(len(prefix) == len(ordered) if name != names[-1] else len(prefix) < len(ordered),
              'retained plan has unexpected missing admissions')
        for entry in prefix:
            origin = entry['retained_from']
            summary = _inside(source.parent/entry['summary'], source.parent)
            _need(entry['session_state'] == 'sealed' and entry['stopped_by_cap'] is False
                  and origin['source_schema'] == EVIDENCE_SCHEDULE_SCHEMA
                  and origin['schedule'] == plan['source_schedule']
                  and origin['schedule_sha256'] == plan['source_schedule_sha256']
                  and plan['files'].get(str(summary.relative_to(runtime))) == origin['summary_sha256'],
                  'retained plan admission provenance differs')
            _amount(entry['cost_usd'])
        spec = plan['seeds'][name]
        _need(Path(spec['root']).name == name and plan['files'].get(spec['gate']) == spec['gate_sha256'],
              'retained plan seed provenance differs')
        versions = [_number(entry['published_after']) for entry in prefix]
        expected_refs = {'refs/heads/main', *(f'refs/tags/v{i}' for i in range(versions[-1] + 1))}
        _need(versions == sorted(versions) and set(spec['refs']) == expected_refs
              and spec['refs']['refs/heads/main'] == spec['refs']['refs/tags/'+prefix[-1]['published_after']],
              'retained plan published identities differ')
        with _validated_seed(spec, runtime):
            pass
        if name in plan['next_inputs']:
            expected = plan['next_inputs'][name]
            _need(expected['session'] == ordered[len(prefix)]
                  and all(isinstance(expected[key], str) and re.fullmatch(r'[0-9a-f]{64}', expected[key])
                          for key in ('brief_sha256', 'trace_manifest_sha256')),
                  'retained plan next-input assertion differs')
    return plan


def seed(plan: dict, name: str, runtime: Path, target: Repository) -> list[dict]:
    """Clone only eligible published Git state plus byte-identical prefix gate feedback."""
    spec = plan['seeds'][name]
    _inside(target.path.parent, runtime.resolve()/'knowledge'/'p1')
    _need(target.game == spec['game'], 'retained destination belongs to another game')
    _need(not target.path.exists() and not target.state.exists(), 'retained destination already exists')
    with _validated_seed(spec, runtime.resolve()) as source:
        for relative, digest in plan['files'].items():
            _need(_hash(_inside(runtime/relative, runtime.resolve())) == digest, 'retained receipt changed before import')
        target.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _git(target.path.parent, 'clone', '--quiet', '--no-local', '--no-hardlinks', '--single-branch',
                 '--branch', 'main', '--', str(source.path), str(target.path))
            _git(target.path, 'remote', 'remove', 'origin')
            _need(_refs(target) == spec['refs'], 'imported Git identities differ from the retained seed')
        except KnowledgeError:
            raise RetainedError('retained Git seed could not be imported') from None
        target.state.mkdir()
        shutil.copyfile(source.state/'gate.jsonl', target.state/'gate.jsonl')
        _need(_hash(target.state/'gate.jsonl') == spec['gate_sha256'], 'imported gate feedback differs')
    return plan['prefixes'][name]


def validate_schedule(value: dict) -> None:
    """The one current operational schedule contract; historical /1 needs offline migration."""
    _need(isinstance(value, dict) and value.get('schema') == SCHEDULE_SCHEMA
          and type(value.get('repeat')) is int and value['repeat'] in (1, 2)
          and isinstance(value.get('lineages'), dict), f'not a {SCHEDULE_SCHEMA} file')
    try:
        new, old = Decimal(0), Decimal(0)
        for lineage in value['lineages'].values():
            for entry in lineage['sessions']:
                if entry.get('retained_from'):
                    old += _amount(entry['cost_usd'])
                else:
                    new += _amount(entry['cost_usd'])
        _need(_amount(value['retained_cost_usd']) == old and _amount(value['new_cost_usd']) == new
              and _amount(value['total_cost_usd']) == old + new
              and _amount(value['cap_usd']) == old + _amount(value['new_cap_usd']),
              'schedule selection and fresh-execution accounting disagree')
    except (KeyError, TypeError):
        raise RetainedError('current schedule is missing required selection accounting') from None


def _migrate_schedule(source_path: Path, digest: str, runtime: Path,
                      admissions: dict[str, tuple[str, ...]], out: Path) -> dict:
    """Explicit one-time conversion of selected historical /1 evidence; no assurance upgrade."""
    runtime = runtime.resolve()
    source_path = _inside(source_path, runtime/'curator-shadow'/'p1')
    _need(_hash(source_path) == digest, 'historical schedule differs from its frozen source digest')
    source = _json(source_path)
    _need(isinstance(source, dict) and source.get('schema') == EVIDENCE_SCHEDULE_SCHEMA
          and source.get('stopped') is None,
          'historical schedule is unsupported or stopped; it cannot be imported for delivery')
    _inside(out, runtime)
    selected, total = {}, Decimal(0)
    for name, ordered in admissions.items():
        _inside(runtime/source['knowledge']/name, runtime/'knowledge'/'p1')
        entries = source['lineages'][name]['sessions']
        _need([entry.get('session') for entry in entries] == list(ordered), 'historical admission coverage differs')
        imported = []
        for entry in entries:
            _need(entry.get('session_state') == 'sealed' and not entry.get('stopped_by_cap'),
                  'historical selected admission is incomplete or capped')
            summary_path = _inside(source_path.parent/entry['summary'], source_path.parent)
            summary = _json(summary_path)
            _need(summary.get('session_state') == 'sealed' and not summary.get('stopped_by_cap')
                  and summary.get('published_after') == entry['published_after']
                  and _amount(summary['cost_usd']) == _amount(entry['cost_usd']),
                  'historical summary differs from its selected admission')
            total += _amount(entry['cost_usd'])
            imported.append(dict(entry, summary=os.path.relpath(summary_path, out.parent), retained_from=dict(
                source_schema=EVIDENCE_SCHEDULE_SCHEMA, schedule=str(source_path.relative_to(runtime)),
                schedule_sha256=digest, summary_sha256=_hash(summary_path), assurance='original historical evidence')))
        selected[name] = dict(sessions=imported)
    converted = dict(source, schema=SCHEDULE_SCHEMA, lineage_order=list(admissions), lineages=selected,
                     retained_cost_usd=str(total), new_cost_usd='0', new_cap_usd='0',
                     total_cost_usd=str(total), cap_usd=str(total),
                     migration=dict(source=str(source_path.relative_to(runtime)), source_sha256=digest,
                                    note='Offline format conversion only; original runtime and assurance retained.'))
    validate_schedule(converted)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x') as stream:
        json.dump(converted, stream, indent=1, sort_keys=True)
        stream.write('\n')
    return dict(lineages=len(selected), sessions=sum(len(v['sessions']) for v in selected.values()),
                source_sha256=digest, migrated_sha256=_hash(out))


def migrate_schedule(source_path: Path, digest: str, runtime: Path,
                     admissions: dict[str, tuple[str, ...]], out: Path) -> dict:
    try:
        return _migrate_schedule(source_path, digest, runtime, admissions, out)
    except RetainedError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, OSError, ValueError, KnowledgeError):
        raise RetainedError('historical schedule evidence is invalid or unavailable') from None
