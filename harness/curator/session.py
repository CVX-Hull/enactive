"""Ephemeral curator sessions (ADR 009's coding-agent curator direction; #453).

`run_session` builds a fresh workspace (trace window, published knowledge, brief, workbench,
open drafts), runs a coding-agent host in it under the curator sandbox, and always closes out:
it collects submissions and drafts, gates each submission in order (only after a clean exit),
updates draft lifecycles, seals the session record and deletes the workspace. One session runs
at a time per knowledge repository. See docs/design/curator-session.md.

Everything the curator wrote is examined without following links before it is copied: a
symbolic link or special file in a writable directory, or a writable directory replaced by one,
is refused and never followed.
"""
from __future__ import annotations

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

from . import sandbox
from .containers import Drafts, UnsafeTree, read_tree, write_tree
from .gate import gate
from .knowledge import Repository

TRACE_PACKAGE = Path(__file__).resolve().parents[1]/'trace'
WRITABLE = ('submissions', 'drafts', 'scratch')
WORKBENCH_DEPENDENCIES = ('numpy', 'PIL')
MAX_SUBMISSIONS_BYTES = 16 << 20


class SessionError(RuntimeError):
    """A session could not start (another is running, or its inputs are missing)."""


@dataclass(frozen=True)
class SessionConfig:
    """How to run the host. `argv` runs with the workspace as its working directory."""
    argv: tuple[str, ...]
    tools: tuple[Path, ...] = ()
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


def brief(repo: Repository, version: str, trace_manifest: dict, drafts: list[dict]) -> str:
    """Software-written brief: what is new, open and stale drafts, recent gate results.

    Names the curator chose (submission and draft directories) are shown `repr`-escaped, so a
    name cannot inject Markdown or lines into a later session's brief.
    """
    lines = ['# Session brief', '', f'Published knowledge: `{version}` (read-only copy in `knowledge/`).', '',
             '## Trace window', '']
    for session in trace_manifest['sessions']:
        actors = ', '.join(f"{a['directory']} ({a['steps']} steps, {a['frames']} frames)" for a in session['actors'])
        lines.append(f"- `{session['name']}`: {actors}")
    lines += ['', 'Frames are in `trace/frames/`; `python -m harness.trace.workbench --help` lists tools '
              '(run from `workbench/`).', '', '## Drafts', '']
    lines += [f"- `{d['id']}` ({d['lifecycle']['state']}, untouched for {d['lifecycle'].get('untouched_sessions', 0)} "
              f"sessions) in `drafts/{d['id']}/`" for d in drafts] or ['None.']
    log = repo.state/'gate.jsonl'
    verdicts = [json.loads(line) for line in log.read_text().splitlines()][-10:] if log.is_file() else []
    lines += ['', '## Recent gate results', '']
    lines += [f"- {v['submission']!r} from session `{v['session']}`: "
              + (f"accepted as `{v['version']}`" if v['accepted']
                 else 'rejected: ' + '; '.join(repr(d) for d in v['diagnostics']))
              for v in verdicts] or ['None.']
    lines += ['', '## Hints and flagged types', '', 'None.', '', '## Close-out', '',
              'Put each proposed change in `submissions/<id>/submission.json`; work to continue later in '
              '`drafts/<id>/`. Everything else is discarded.', '']
    return '\n'.join(lines)


def run_session(repo: Repository, trace_sessions: list[Path], config: SessionConfig, *,
                memory: Path | None = None, session_id: str | None = None) -> dict:
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
        record_dir.mkdir(parents=True)
        return _run(repo, trace_sessions, config, memory, session_id, record_dir)
    finally:
        for target in (repo.state/'workspaces'/session_id, repo.state/'workspaces'/f'{session_id}.home'):
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


def _run(repo: Repository, trace_sessions: list[Path], config: SessionConfig, memory: Path | None,
         session_id: str, record_dir: Path) -> dict:
    """Prepare, run and close out one session. Any failure seals the record `aborted` with its error."""
    manifest: dict | None = None
    result: sandbox.Result | None = None
    errors: list[str] = []
    window: set[str] = set()
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
        repo.export(version, workspace/'knowledge')
        trace_manifest = project(trace_sessions, workspace/'trace', memory=memory)
        window = {Path(name).stem for name in trace_manifest['files'] if name.startswith('frames/')}
        for name in WRITABLE:
            (workspace/name).mkdir()
        drafts = Drafts(repo.state)
        before = drafts.checkout(workspace/'drafts')
        open_drafts = drafts.list()
        (workspace/'brief.md').write_text(brief(repo, version, trace_manifest, open_drafts))
        if (config.expected_brief_sha256 is not None
                and _sha(workspace/'brief.md') != config.expected_brief_sha256):
            raise SessionError('retained-prefix next brief differs from its frozen input')
        if (config.expected_trace_manifest_sha256 is not None
                and _sha(workspace/'trace'/'manifest.json') != config.expected_trace_manifest_sha256):
            raise SessionError('retained-prefix next trace projection differs from its frozen input')
        shutil.copytree(TRACE_PACKAGE, workspace/'workbench'/'harness'/'trace',
                        ignore=shutil.ignore_patterns('__pycache__'))
        (workspace/'workbench'/'harness'/'__init__.py').write_text('')
        dependencies = dependency_roots()
        manifest = dict(
            schema='container-manifest/1', id=session_id, kind='curator-session', owner_role='curator',
            inputs=dict(trace_sessions=[p.name for p in trace_sessions], window_frames=len(window),
                        drafts=[d['id'] for d in open_drafts]),
            pinned=dict(knowledge_version=version, trace_manifest_sha256=_sha(workspace/'trace'/'manifest.json'),
                        brief_sha256=_sha(workspace/'brief.md'), host=config.host),
            budgets=dict(wall_seconds=config.limits.wall_seconds, memory_bytes=config.limits.memory_bytes,
                         disk_bytes=config.limits.disk_bytes,
                         cap_usd=str(getattr(config.proxy, 'cap', None)) if config.proxy else None),
            lifecycle=dict(state='active', started_wall=time.time()),
            provenance=dict(repository=str(repo.path)), retention=dict(policy='session record kept; workspace deleted'))
        validate(manifest)
        (record_dir/'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
        shutil.copyfile(workspace/'brief.md', record_dir/'brief.md')
        layout = sandbox.Layout(workspace=workspace, home=home, writable=tuple(workspace/n for n in WRITABLE),
                                tools=tuple(config.tools) + tuple(r for r in dependencies if r not in config.tools))
        env = dict(PYTHONPATH=os.pathsep.join([str(workspace/'workbench'), *map(str, dependencies)]),
                   **config.extra_env)
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
            _close_out(repo, session_id, record_dir, workspace, manifest, result, errors, window, drafts, before)
        except Exception as exc:  # noqa: BLE001 - the original interruption must remain primary
            interrupt.add_note(f'Interrupted close-out failed: {type(exc).__name__}')
            try:
                (record_dir/'close-out-failed.json').write_text(json.dumps(dict(interrupted=True, error=type(exc).__name__)))
            except OSError as failure:
                interrupt.add_note(f'Could not retain close-out failure: {type(failure).__name__}')
        raise
    except Exception as exc:  # noqa: BLE001 - every failure is sealed into the record
        errors.append(f'session: {_error(exc)}')
    return _close_out(repo, session_id, record_dir, workspace, manifest, result, errors, window, drafts, before)


def _close_out(repo, session_id, record_dir, workspace, manifest, result, errors, window, drafts, before) -> dict:
    """Keep what is safe to keep, gate it after a clean exit, and seal the record."""
    survivors = list(result.survivors) if result is not None else None
    if survivors:
        errors.append(f'close-out: {len(survivors)} host processes survived; nothing was collected')
    aborted = bool(errors) or result is None or result.stopped is not None or result.returncode != 0
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
                draft_report = drafts.collect(workspace/'drafts', session_id, before or {}, age=not aborted)
        except Exception as exc:  # noqa: BLE001
            errors.append(f'close-out: drafts: {_error(exc)}')
        aborted = aborted or bool(errors)
        gated = record_dir/'submissions'
        if not aborted and gated.is_dir() and not any(r.startswith('submissions:') for r in refused):
            for submission in sorted(p for p in gated.iterdir() if p.is_dir()):
                try:
                    verdict = gate(repo, submission, session_id=session_id, window_frames=window)
                    verdicts.append(verdict)
                    if verdict['accepted']:
                        drafts.promote(verdict.get('from_drafts', []), session_id)
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
    manifest['lifecycle'] = dict(manifest['lifecycle'], state='aborted' if aborted else 'sealed', ended_wall=time.time(),
                                 stopped=getattr(result, 'stopped', None), returncode=getattr(result, 'returncode', None),
                                 survivors=survivors, errors=errors, refused=refused)
    if result is not None:
        manifest['provenance'].update(peak_memory_bytes=result.peak_memory_bytes,
                                      peak_disk_bytes=result.peak_disk_bytes, seconds=round(result.seconds, 3))
    record = dict(manifest=manifest, verdicts=verdicts, drafts=draft_report, published_after=published_after)
    validate(manifest)
    (record_dir/'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
    (record_dir/'close-out.json').write_text(json.dumps(record, indent=1, sort_keys=True, default=str))
    return record
