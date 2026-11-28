"""Ephemeral curator sessions (ADR 009's coding-agent curator direction; #453).

`run_session` builds a fresh workspace (trace window, published knowledge, brief, workbench,
open drafts), runs a coding-agent host in it under the curator sandbox, and always closes out:
it collects submissions and drafts, gates each submission in order (after a clean exit or a validated provider-error prefix),
updates draft lifecycles, seals the session record and deletes the workspace. One session runs
at a time per knowledge repository. See docs/design/curator-session.md.

Everything the curator wrote is examined without following links before it is copied: a
symbolic link or special file in a writable directory, or a writable directory replaced by one,
is refused and never followed.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import time
import uuid

from harness.trace.projection import project
from harness.trace.sidecar import validate

from . import check, hygiene, sandbox, type_usage
from .containers import Drafts, UnsafeTree, read_tree, write_tree
from .gate import _history, gate, journal as gate_journal
from .window import FULL, Window, coverage as window_coverage, restrict, positions, grooming_context
from .knowledge import Repository

TRACE_PACKAGE = Path(__file__).resolve().parents[1]/'trace'
WRITABLE = ('submissions', 'drafts', 'scratch')
WORKBENCH_DEPENDENCIES = ('numpy', 'PIL', 'jsonschema', 'jsonschema_specifications', 'referencing', 'attrs', 'rpds')
PROVIDER_ERROR_EXIT_CODE = 75
FLEX_DEFERRED_EXIT_CODE = 76
MAX_SUBMISSIONS_BYTES = 16 << 20


class SessionError(RuntimeError):
    """A session could not start (another is running, or its inputs are missing)."""


@dataclass(frozen=True)
class SessionConfig:
    """How to run the host. `argv` runs with the workspace as its working directory."""
    argv: tuple[str, ...]
    tools: tuple[Path, ...] = ()
    grooming_brief: Path | None = None
    limits: sandbox.Limits = field(default_factory=lambda: sandbox.Limits(wall_seconds=600))
    proxy: object | None = None  # a started harness.curator.proxy.ModelProxy, or None for scripted hosts
    proxy_port: int | None = None
    extra_env: dict[str, str] = field(default_factory=dict)
    host: dict = field(default_factory=dict)  # recorded identity: name, version, model
    expected_brief_sha256: str | None = None
    expected_trace_manifest_sha256: str | None = None


def _remove(path: Path) -> None:
    """Delete a tree the curator may have made unreadable, read-only or immutable."""
    def unlock(target: str) -> None:
        try:
            chflags = getattr(os, 'chflags', None)
            if chflags is not None:
                chflags(target, 0, follow_symlinks=False)
        except (OSError, NotImplementedError):
            pass

    def fix(function, target, _excinfo):
        parent = os.path.dirname(target)
        unlock(parent)
        os.chmod(parent, stat.S_IRWXU)
        unlock(target)
        if os.path.isdir(target) and not os.path.islink(target):
            os.chmod(target, stat.S_IRWXU)
        function(target)

    def open_up(directory_fd: int) -> None:
        # Make every directory searchable and writable through descriptors, never by path, so a
        # writer that survived the stop cannot redirect the change with a swapped link.
        with os.scandir(directory_fd) as listing:
            children = [entry.name for entry in listing if entry.is_dir(follow_symlinks=False)]
        for name in children:
            try:
                os.chmod(name, stat.S_IRWXU, dir_fd=directory_fd, follow_symlinks=False)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
            except (OSError, NotImplementedError):
                continue
            try:
                open_up(child)
            finally:
                os.close(child)

    if not os.path.lexists(path):
        return
    if os.path.isdir(path) and not os.path.islink(path):
        unlock(str(path))
        try:
            root = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            root = None
        if root is not None:
            try:
                open_up(root)
            except OSError:
                pass
            finally:
                os.close(root)
        # rmtree is descriptor-based; file flags are cleared only for an entry it cannot remove
        # (Python has no descriptor-relative chflags on macOS; recorded as a residual risk).
        shutil.rmtree(path, onexc=fix)
    else:
        os.unlink(path)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependency_roots() -> tuple[Path, ...]:
    """Directories holding the workbench's third-party packages, readable and importable in a session."""
    roots: list[Path] = []
    for name in WORKBENCH_DEPENDENCIES:
        spec = importlib.util.find_spec(name)
        if spec is None or spec.origin is None:
            raise SessionError(f'The workbench needs {name}, which is not installed')
        root = Path(spec.origin).resolve().parents[1]
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def _plain_directory(path: Path) -> bool:
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def _error(exc: BaseException) -> str:
    return f'{type(exc).__name__}: {exc}'


def brief(repo: Repository, version: str, trace_manifest: dict, drafts: list[dict], session_kind: str = 'admission') -> str:
    """Software-written brief: what is new, open and stale drafts, recent gate results, axes and tag usage.

    Names the curator chose (submission and draft directories) are shown `repr`-escaped, so a
    name cannot inject Markdown or lines into a later session's brief.
    """
    lines = ['# Session brief', '', f'Session kind: {session_kind}.', '', f'Published knowledge: `{version}` (read-only copy in `knowledge/`).', '',
             '## Trace window', '']
    for session in trace_manifest['sessions']:
        actors = ', '.join(f"{a['directory']} ({a['steps']} steps, {a['frames']} frames)" for a in session['actors'])
        lines.append(f"- `{session['name']}`: {actors}")
    window = trace_manifest.get('window')
    if window:
        lines += ['', f"This trace is a window: steps {window['first']} to {window['last']} of "
                      f"{window['steps_available']} of actor `{window['actor']}`, and nothing else. Frames outside "
                      'it are not in the trace and cannot be cited. The step numbers are `seq` in `steps.jsonl`.']
    if session_kind in ('grooming', 'hygiene'):
        lines += ['', 'Read `grooming.md` for this session. The trace contains the last admission\'s cited '
                  'frames and the first and last framed operations of each actor.']
    lines += ['', 'Read `knowledge/index.md` and targeted `knowledge/records/<id>.json` files. '
              'Use `run_workbench(["knowledge", "search", "<query>"])` to find records or '
              '`run_workbench(["knowledge", "get", "<id>"])` to fetch a specific record.']
    lines += ['', 'Frames are in `trace/frames/`; `python -m harness.trace.workbench --help` lists tools '
              '(run from `workbench/`).', '', '## Drafts', '']
    lines += [f"- `{d['id']}` ({d['lifecycle']['state']}, untouched for {d['lifecycle'].get('untouched_sessions', 0)} "
              f"sessions) in `drafts/{d['id']}/`" for d in drafts] or ['None.']
    verdicts = gate_journal(repo)[-10:]
    lines += ['', '## Recent gate results', '']
    lines += [f"- {v['operation']} {v['submission']!r} from session `{v['session']}`: "
              + (f"{v['status']} as `{v['version']}`" if v['version'] is not None else v['status'])
              + (': ' + '; '.join(repr(d) for d in v['diagnostics']) if v['diagnostics'] else '')
              for v in verdicts] or ['None.']
    lines += ['', '## Hints', '',
              'Player hints in the selected trace tool calls are fallible public reports, not published facts. '
              'Check their source evidence before proposing knowledge. No additional operator hints.']
    records = repo.records(version)
    lines += ['', *_axes_section(trace_manifest, records), '', *type_usage.section(records)]
    if session_kind in ('grooming', 'hygiene'):
        lines += ['', *_grooming_worklist(records), '', *hygiene.worklist_section(records)]
    lines += ['', '## Close-out', '',
              'Put each proposed change in `submissions/<id>/submission.json`; work to continue later in '
              '`drafts/<id>/`. Everything else is discarded.', '']
    return '\n'.join(lines)


def _axes_section(trace_manifest: dict, records: list[dict]) -> list[str]:
    sessions = trace_manifest['sessions']
    active = sessions[-1].get('context', {}) if sessions else {}
    counts = Counter(key for row in records if check.current(row) for key in row['scope']
                     if key not in ('game', 'world', 'lineage'))
    return ['## Scope axes', '',
            'Active package: ' + (', '.join(f'`{key}` = {value!r}' for key, value in sorted(active.items())) or 'none'),
            'Current usage: ' + (', '.join(f'`{key}` ({n})' for key, n in sorted(counts.items())) or 'none')]


def _grooming_worklist(records: list[dict]) -> list[str]:
    rows = sorted((row for row in records if check.current(row)), key=check.owner)
    articles = [row for row in rows if row['record'] == 'article']
    filed = set().union(*(check.cited_facts(row) for row in articles))
    worlds = {row['scope'].get('world') for row in articles}
    stale_sources = check.stale_review_sources(rows)
    must_clear, advisory = [], []
    for row in rows:
        stale = row['stale_citations']
        identity, state = check.owner(row), row['lifecycle_state']
        if stale:
            must_clear.append(f'- `{identity}` ({state}): stale {", ".join(stale)}')
        notes = []
        if state == 'contested':
            notes.append('contested')
        elif row['needs_review'] and identity not in stale_sources:
            notes.append('needs review')
        lineages = row.get('lineages', [])
        if len(lineages) > 1 or None in lineages:
            notes.append(f'lineages {lineages!r}')
        world = row['scope'].get('world')
        if row['record'] == 'fact' and identity not in filed and (world is None or world in worlds):
            notes.append('unfiled')
        if notes:
            names = {link['target'] for link in row['links']}
            if row['record'] == 'article':
                names.update(check.cited_facts(row))
            references = f' (references {", ".join(sorted(names))})' if names else ''
            advisory.append(f'- `{identity}` ({state}): {", ".join(notes)}{references}')
    return ['## Grooming worklist', '', '### Must clear', '', *(must_clear or ['None.']),
            '', '### Advisory', '', *(advisory or ['None.'])]


def _stage_knowledge(knowledge: Path, backing: Path, records: list[dict], world: str | None) -> None:
    directory = knowledge / 'records'
    directory.mkdir(parents=True)
    for name in ('knowledge.json', 'provenance.json', 'coverage.json'):
        source = backing / name
        if source.is_file():
            target = knowledge / name
            shutil.copyfile(source, target)
            target.chmod(0o444)

    lines = ['# Knowledge index', '', '## Articles', '']
    for record in sorted(records, key=check.owner):
        identity = check.owner(record)
        (directory / f'{identity}.json').write_text(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n',
                                                    encoding='utf-8')
        if record['record'] == 'article':
            title = ' '.join(record['title'].split())
            lead = ' '.join(record['lead'].split())
            if len(lead) > 160:
                lead = lead[:159].rstrip() + '…'
            lines.append(f'- {identity}: {title} — {lead}')
    lines += ['', *hygiene.state_key_section(records, world=world), '']
    (knowledge / 'index.md').write_text('\n'.join(lines), encoding='utf-8')


def _stage_workbench(workspace: Path) -> None:
    workbench = workspace / 'workbench'
    harness = workbench / 'harness'
    shutil.copytree(TRACE_PACKAGE, harness / 'trace', ignore=shutil.ignore_patterns('__pycache__'))
    (harness / '__init__.py').write_text('')
    curator = harness / 'curator'
    curator.mkdir()
    (curator / '__init__.py').write_text('')
    for name in ('check.py', 'validate.py', 'hygiene.py', 'search.py'):
        shutil.copyfile(Path(__file__).with_name(name), curator / name)
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'jsonio.py', harness / 'jsonio.py')
    schemas = workbench / 'schemas'
    schemas.mkdir()
    for name in ('curator-submission.schema.json', 'curator-fact.schema.json'):
        shutil.copyfile(Path(__file__).resolve().parents[2] / 'schemas' / name, schemas / name)


def run_session(repo: Repository, trace_sessions: list[Path], config: SessionConfig, *, window: Window = FULL,
                memory: Path | None = None, journal: Path | None = None, session_id: str | None = None, session_kind: str = 'admission') -> dict:
    if session_kind not in check.SESSION_KINDS:
        raise SessionError('unknown session kind')
    if session_kind in ('grooming', 'hygiene') and not window.full:
        raise SessionError(f'{session_kind} takes the last admission citations, not a window')
    session_id = session_id or uuid.uuid4().hex[:16]
    repo.state.mkdir(parents=True, exist_ok=True)
    lock = (repo.state/'lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock.close()
        raise SessionError('Another curator session holds this repository') from exc
    record_dir = repo.state/'sessions'/session_id
    cleanup: list[str] = []
    try:
        gate_journal(repo)
        record_dir.mkdir(parents=True)
        return _run(repo, trace_sessions, config, memory, journal, window, session_id, record_dir, session_kind)
    finally:
        for name in (session_id, f'{session_id}.home', f'{session_id}.backing'):
            target = repo.state/'workspaces'/name
            try:
                _remove(target)
            except OSError as exc:
                cleanup.append(f'{target.name}: {_error(exc)}')
        if cleanup and record_dir.is_dir():
            try:
                (record_dir/'cleanup-failed.json').write_text(json.dumps(cleanup, indent=1))
            except OSError:
                pass
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
        finally:
            lock.close()


def _run(repo: Repository, trace_sessions: list[Path], config: SessionConfig, memory: Path | None, journal: Path | None, window: Window,
         session_id: str, record_dir: Path, session_kind: str) -> dict:
    """Prepare, run and close out one session. Any failure seals the record `aborted` with its error."""
    manifest: dict | None = None
    result: sandbox.Result | None = None
    errors: list[str] = []
    window_frames: dict[str, dict] = {}
    coverage: dict | None = None
    workspace = repo.state/'workspaces'/session_id
    drafts = before = None
    try:
        repo.ensure()
        (repo.state/'workspaces').mkdir(exist_ok=True)
        workspace.mkdir()
        workspace = workspace.resolve()
        home = repo.state/'workspaces'/f'{session_id}.home'
        home.mkdir()
        home = home.resolve()
        version = repo.published()
        _, reserved_ids, reservations, reserved_state_keys = _history(repo)
        records = repo.records(version)
        backing = (repo.state/'workspaces'/f'{session_id}.backing').resolve()
        repo.export(version, backing)
        trace_manifest = restrict(workspace/'trace', project(trace_sessions, workspace/'trace', memory=memory, journal=journal), window)
        provenance = repo.provenance()
        if session_kind in ('grooming', 'hygiene'):
            last = provenance.get('last_admission')
            if last is None:
                raise SessionError(f'{session_kind} needs a published admission')
            if ','.join(p.name for p in trace_sessions) != last['coverage']['session']:
                raise SessionError(f'{session_kind} trace must be the last admission')
            trace_manifest = grooming_context(workspace/'trace', trace_manifest, set(last['citations']))
            coverage = last['coverage']
        else:
            coverage = window_coverage(window, [p.name for p in trace_sessions], trace_manifest)
        window_frames = positions(workspace/'trace', trace_manifest, provenance['frames'])
        labels = window_frames.sessions
        context = dict(base_version=version, session_id=session_id, reserved_ids=sorted(reserved_ids),
                       reserved_state_keys=sorted(reserved_state_keys),
                       reserved_sessions=reservations, session_kind=session_kind, window_frames=window_frames,
                       session_labels=labels, declared_axes=sorted(check.declared_axes(reservations, labels)))
        validation_context = backing / 'validation-context.json'
        validation_context.write_text(json.dumps(context, ensure_ascii=False), encoding='utf-8')
        validation_context.chmod(0o444)
        # The active trace labels can make an off-timeline end irrelevant on this lineage.
        timeline = deepcopy(provenance)
        try:
            incoming = check._incoming_provenance(labels, reservations)
            check._merge_sessions(timeline, reservations)
            check._merge_sessions(timeline, incoming)
        except ValueError:
            # The shared candidate check reports conflicting labels in its normal stage.
            timeline = provenance
        active_labels = next(reversed(labels.values()), {})
        by_id = {r['id']: r for r in records if r['record'] == 'fact'}
        visible = [record for record in records
                   if check.current(record) or check.ended_still_alive(record, active_labels, timeline, by_id)]
        _stage_knowledge(workspace / 'knowledge', backing, visible, active_labels.get('world'))
        for name in WRITABLE:
            (workspace/name).mkdir()
        drafts = Drafts(repo.state)
        before = drafts.checkout(workspace/'drafts')
        open_drafts = drafts.list()
        (workspace/'brief.md').write_text(brief(repo, version, trace_manifest, open_drafts, session_kind))
        if session_kind in ('grooming', 'hygiene'):
            if config.grooming_brief is None:
                raise SessionError(f'{session_kind} needs a configured grooming brief')
            shutil.copyfile(config.grooming_brief, workspace/'grooming.md')
        if (config.expected_brief_sha256 is not None
                and _sha(workspace/'brief.md') != config.expected_brief_sha256):
            raise SessionError('retained-prefix next brief differs from its frozen input')
        if (config.expected_trace_manifest_sha256 is not None
                and _sha(workspace/'trace'/'manifest.json') != config.expected_trace_manifest_sha256):
            raise SessionError('retained-prefix next trace projection differs from its frozen input')
        _stage_workbench(workspace)
        dependencies = dependency_roots()
        manifest = dict(
            schema='container-manifest/1', id=session_id, kind='curator-session', owner_role='curator',
            inputs=dict(session_kind=session_kind, trace_sessions=[p.name for p in trace_sessions], window_frames=len(window_frames), window=window.record(), coverage=coverage,
                        drafts=[d['id'] for d in open_drafts]),
            pinned=dict(knowledge_version=version, trace_manifest_sha256=_sha(workspace/'trace'/'manifest.json'),
                        brief_sha256=_sha(workspace/'brief.md'), host=config.host),
            budgets=dict(wall_seconds=config.limits.wall_seconds, memory_bytes=config.limits.memory_bytes,
                         disk_bytes=config.limits.disk_bytes,
                         cap_usd=str(getattr(config.proxy, 'cap', None)) if config.proxy else None),
            lifecycle=dict(state='active', started_wall=time.time()),
            provenance=dict(repository=str(repo.path)), retention=dict(policy='session record kept; workspace deleted'))
        if session_kind in ('grooming', 'hygiene'):
            manifest['pinned']['grooming_sha256'] = _sha(workspace/'grooming.md')
            shutil.copyfile(workspace/'grooming.md', record_dir/'grooming.md')
        validate(manifest)
        (record_dir/'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
        shutil.copyfile(workspace/'brief.md', record_dir/'brief.md')
        layout = sandbox.Layout(workspace=workspace, home=home, writable=tuple(workspace/n for n in WRITABLE),
                                tools=(*config.tools, *(r for r in dependencies if r not in config.tools)),
                                readable=(backing,))
        env = dict(PYTHONPATH=os.pathsep.join([str(workspace/'workbench'), *map(str, dependencies)]),
                   **config.extra_env)
        env['CURATOR_KNOWLEDGE_BACKING'] = str(backing)
        with (record_dir/'host-output.log').open('wb') as output:
            result = sandbox.run(list(config.argv), layout, proxy_port=config.proxy_port,
                                 token=getattr(config.proxy, 'token', None), limits=config.limits,
                                 extra_env=env, stdout=output, stderr=output)
    except KeyboardInterrupt as interrupt:
        # sandbox.run's finally has attempted owned process cleanup. Without its Result, exit and
        # survivor observations remain unknown: retain an abort, gate nothing and preserve SIGINT.
        errors.append('session: KeyboardInterrupt')
        errors.extend(note for note in getattr(interrupt, '__notes__', [])
                      if note.startswith('Sandbox cleanup failed: '))
        try:
            _close_out(repo, session_id, record_dir, workspace, manifest, result, errors, window_frames, coverage, drafts, before, session_kind)
        except Exception as exc:  # noqa: BLE001 - the original interruption must remain primary
            interrupt.add_note(f'Interrupted close-out failed: {type(exc).__name__}')
            try:
                (record_dir/'close-out-failed.json').write_text(json.dumps(dict(interrupted=True, error=type(exc).__name__)))
            except OSError as failure:
                interrupt.add_note(f'Could not retain close-out failure: {type(failure).__name__}')
        raise
    except Exception as exc:  # noqa: BLE001 - every failure is sealed into the record
        errors.append(f'session: {_error(exc)}')
    return _close_out(repo, session_id, record_dir, workspace, manifest, result, errors, window_frames, coverage, drafts, before, session_kind)


def _validated_prefix(record_dir: Path, submissions: list[Path]) -> int:
    """Find the longest passing event that names the exact retained submission bytes."""
    expected = []
    for directory in submissions:
        path = directory / 'submission.json'
        if not path.is_file():
            break
        expected.append((path.relative_to(record_dir).as_posix(), _sha(path)))
    longest = 0
    events = record_dir / 'host-output.log'
    if not expected or not events.is_file():
        return longest
    with events.open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            try:
                event = json.loads(line)
                prefix = event.get('prefix') if isinstance(event, dict) and (
                    event.get('type') == 'submission-validated' and event.get('all_passed') is True) else None
                if not isinstance(prefix, list) or not longest < len(prefix) <= len(expected):
                    continue
                actual = [(entry['path'], entry['sha256']) for entry in prefix]
            except (ValueError, TypeError, KeyError, RecursionError):
                continue
            if actual == expected[:len(actual)]:
                longest = len(actual)
    return longest


def _close_out(repo, session_id, record_dir, workspace, manifest, result, errors, window_frames, coverage, drafts, before, session_kind='admission') -> dict:
    """Keep what is safe to keep, gate it after a clean exit, and seal the record."""
    survivors = list(result.survivors) if result is not None else None
    if survivors:
        errors.append(f'close-out: {len(survivors)} host processes survived; nothing was collected')
    provider_error = (result is not None and result.stopped is None
                      and result.returncode == PROVIDER_ERROR_EXIT_CODE)
    flex_deferred = (result is not None and result.stopped is None
                     and result.returncode == FLEX_DEFERRED_EXIT_CODE)
    prefix_closeout = provider_error or flex_deferred
    aborted = bool(errors) or result is None or result.stopped is not None or (result.returncode != 0 and not prefix_closeout)
    collectable = result is not None and not survivors
    refused: list[str] = []
    draft_report: dict = {}
    verdicts: list[dict] = []
    if collectable:
        # Everything below reads the workspace through directory descriptors (containers.read_tree),
        # so a writer that escaped the stop cannot redirect it with a swapped link.
        for name in WRITABLE:
            if not _plain_directory(workspace/name):
                refused.append(f'{name}: replaced by a link or special file; not collected')
        if _plain_directory(workspace/'submissions'):
            try:
                files = read_tree(workspace/'submissions', limit=MAX_SUBMISSIONS_BYTES)
                write_tree(files, record_dir/'submissions')
            except UnsafeTree as exc:
                refused.append(f'submissions: {exc}; none gated')
            except Exception as exc:  # noqa: BLE001 - sealed into the record
                errors.append(f'close-out: submissions: {_error(exc)}')
            if any(r.startswith('submissions:') for r in refused) or errors:
                try:
                    _remove(record_dir/'submissions')
                except Exception as exc:  # noqa: BLE001
                    errors.append(f'close-out: removing partial submissions: {_error(exc)}')
        aborted = aborted or bool(errors)
        try:
            if drafts is not None and _plain_directory(workspace/'drafts'):
                draft_report = drafts.collect(workspace/'drafts', session_id, before or {}, age=not aborted and not prefix_closeout)
        except Exception as exc:  # noqa: BLE001
            errors.append(f'close-out: drafts: {_error(exc)}')
        aborted = aborted or bool(errors)
        gated = record_dir/'submissions'
        if not aborted and gated.is_dir() and not any(r.startswith('submissions:') for r in refused):
            submissions = sorted(path for path in gated.iterdir() if path.is_dir())
            if prefix_closeout:
                try:
                    count = _validated_prefix(record_dir, submissions)
                except OSError as exc:
                    errors.append(f'close-out: validation events: {_error(exc)}')
                    count = 0
                kind_label = 'flex-capacity-deferred' if flex_deferred else 'provider-error'
                refused.extend(f'submission {path.name!r}: outside the validated {kind_label} prefix'
                               for path in submissions[count:])
                submissions = submissions[:count]
            for submission in submissions:
                try:
                    verdict = gate(repo, submission, session_id=session_id, window_frames=window_frames,
                                   coverage=coverage, session_kind=session_kind, session_labels=window_frames.sessions)
                    verdicts.append(verdict)
                    if verdict['status'] == 'published' and verdict['operation'] == 'submission':
                        drafts.promote(verdict.get('from_drafts', []), session_id)
                    if verdict['status'] == 'unknown':
                        break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f'close-out: gate {submission.name!r}: {_error(exc)}')
                    break
    try:
        published_after = repo.published()
    except Exception as exc:  # noqa: BLE001
        published_after = None
        errors.append(f'close-out: published version: {_error(exc)}')
    aborted = aborted or bool(errors)
    if manifest is None:
        manifest = dict(schema='container-manifest/1', id=session_id, kind='curator-session', owner_role='curator',
                        inputs={}, pinned={}, budgets={}, lifecycle=dict(state='aborted'), provenance={},
                        retention=dict(policy='session record kept; workspace deleted'))
    stopped_label = ('provider-error' if provider_error
                     else 'flex-capacity-deferred' if flex_deferred
                     else getattr(result, 'stopped', None))
    manifest['lifecycle'] = dict(manifest['lifecycle'], state='aborted' if aborted else 'sealed', ended_wall=time.time(),
                                 stopped=stopped_label,
                                 returncode=getattr(result, 'returncode', None),
                                 survivors=survivors, errors=errors, refused=refused)
    if result is not None:
        manifest['provenance'].update(peak_memory_bytes=result.peak_memory_bytes,
                                      peak_disk_bytes=result.peak_disk_bytes, seconds=round(result.seconds, 3))
    record = dict(manifest=manifest, verdicts=verdicts, drafts=draft_report, published_after=published_after)
    validate(manifest)
    (record_dir/'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
    (record_dir/'close-out.json').write_text(json.dumps(record, indent=1, sort_keys=True, default=str))
    return record
