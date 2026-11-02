"""On-demand finite Analysis snapshots; no collector, credentials or custody."""
from __future__ import annotations

import os
from pathlib import Path
import re
import selectors
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

from harness.computer.protocol import ControlError, decode_json, read_json
from tools.control_analysis import analyze_session, read_sources, session_database
from tools.host_analysis import analyze_trace
from tools.investigation import ACCOUNTING_KEYS, MAX_BUNDLE_BYTES, encoded_bundle, project_case, validate_bundle

ROOT = Path(__file__).resolve().parents[1]
JOB_SECONDS = 8.0
REAP_SECONDS = .25
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_STDOUT_BYTES = MAX_BUNDLE_BYTES + 4096
ERROR = 'Current session investigation is unavailable. Request a fresh snapshot to retry.'


def check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError('Investigation snapshot deadline exceeded')


def trace_prefix(original: Path, destination: Path, deadline: float) -> str:
    """Read exactly one captured byte extent; the analyzer never reopens the producer."""
    check_deadline(deadline)
    if original.is_symlink() or not original.is_file():
        raise ControlError('Selected host trace is not a regular file')
    with original.open('rb') as stream:
        extent = os.fstat(stream.fileno()).st_size
        captured_wall_ms = time.time() * 1000
        if extent > MAX_TRACE_BYTES:
            raise ControlError('Selected host trace exceeds 16 MiB')
        prefix = stream.read(extent)
    if len(prefix) != extent:
        raise ControlError('Selected host trace changed during prefix capture')
    complete = prefix.rfind(b'\n') + 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(prefix[:complete])
    check_deadline(deadline)
    return (f'actors/{original.parent.name} trace cutoff wall_ms={captured_wall_ms:.3f}: '
        f'captured extent={extent} bytes, complete prefix={complete} bytes; '
        f'incomplete final tail omitted={extent - complete} bytes. Both host passes use this identical prefix.')


def snapshot_bundle(directory: Path, profile: dict, snapshot_directory: Path, deadline: float) -> dict:
    """Read only named original inputs into a caller-owned temporary snapshot."""
    directory, snapshot_directory = Path(directory), Path(snapshot_directory)
    check_deadline(deadline)
    manifest = read_json(directory / 'manifest.json', 1024 * 1024)
    if (not isinstance(manifest, dict) or manifest.get('schema') != 'campaign-run/4'
            or manifest.get('session') != profile['session']
            or manifest.get('source_commit') != profile['source_commit']):
        raise ControlError('Selected current manifest identity differs')
    notes = [f'Finite live snapshot requested wall_ms={time.time() * 1000:.3f}; this is recorded evidence, not campaign closure.',
        'Database and host cutoffs are individually captured and are not atomically simultaneous.',
        'Live accounting totals are unknown; no completed driver or receipt is inferred.',
        'No observer DOM witness was selected; image receipt/presentation is not browser display.']
    with session_database(directory) as (connection, _, session):
        if session != profile['session']:
            raise ControlError('Selected current session database identity differs')
        with sqlite3.connect(snapshot_directory / 'session.sqlite3') as destination:
            connection.backup(destination, pages=128,
                progress=lambda status, remaining, total: check_deadline(deadline), sleep=.01)
        notes.append(f'Database snapshot completed wall_ms={time.time() * 1000:.3f}; SQLite read-only backup cutoff is independent of host prefixes.')
    check_deadline(deadline)
    actors, traces, analyses = {}, [], {}
    actor_root = directory / 'actors'
    if actor_root.is_symlink():
        raise ControlError('Selected actors directory is a symlink')
    for index in ('001', '002'):
        actor_directory = actor_root / index
        if actor_directory.is_symlink():
            raise ControlError('Selected actor directory is a symlink')
        frozen_path = actor_directory / 'frozen.json'
        if frozen_path.exists():
            if frozen_path.is_symlink():
                raise ControlError('Selected actor metadata is a symlink')
            frozen = read_json(frozen_path, 1024 * 1024)
            if (not isinstance(frozen, dict) or frozen.get('schema') != 'player-host-inputs/1'
                    or frozen.get('session') != session):
                raise ControlError('Selected original actor/session metadata differs')
            actors[index] = frozen.get('actor_id')
        original = actor_directory / 'host.jsonl'
        if not original.exists():
            continue
        path = snapshot_directory / 'actors' / index / 'host.jsonl'
        notes.append(trace_prefix(original, path, deadline))
        traces.append(path)
        analyses[path] = analyze_trace(path)
        check_deadline(deadline)
    if not traces:
        notes.append('No selected host trace is available.')
    control = analyze_session(snapshot_directory)
    originals = read_sources(snapshot_directory)
    check_deadline(deadline)
    selected = dict(id='current-session', title='Current session recorded snapshot',
        source_ids=[row['source_id'] for row in originals[-3:]])
    case = project_case(selected, snapshot_directory, snapshot_directory, control, actors,
        manifest.get('source_commit'), dict.fromkeys(ACCOUNTING_KEYS), traces=traces, analyses=analyses,
        recent_share=250, notes=notes, image_directory=directory)
    bundle = validate_bundle(dict(schema='observer-investigation/1', cases=[case]))
    check_deadline(deadline)
    return bundle


def envelope(session: str, state: str, *, wall_ms=None, bundle=None, error=None) -> dict:
    return dict(schema='observer-investigation-snapshot/1', session=session, state=state,
        snapshot_wall_ms=wall_ms, bundle=bundle, error=error)


class LiveInvestigationView:
    """One off-path owned child; GET is stable until an explicit refresh."""

    def __init__(self, directory: Path, profile: dict):
        self.directory = Path(directory)
        self.profile = {key: profile[key] for key in ('session', 'source_commit')}
        if (not isinstance(self.profile['session'], str)
                or re.fullmatch('[0-9a-f]{32}', self.profile['session']) is None
                or not isinstance(self.profile['source_commit'], str)
                or len(self.profile['source_commit']) > 256):
            raise ControlError('Invalid current investigation identity')
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread = None
        self._closed = False
        self._result = None

    def snapshot(self, refresh: bool = False) -> dict:
        with self._lock:
            if self._closed:
                return envelope(self.profile['session'], 'unavailable', error=ERROR)
            if self._thread is not None and self._thread.is_alive():
                return self._result.copy()
            if self._result is None or refresh:
                self._result = envelope(self.profile['session'], 'loading')
                self._thread = threading.Thread(target=self._run, name='investigation-snapshot', daemon=True)
                self._thread.start()
            return self._result.copy()

    def _run(self) -> None:
        result = envelope(self.profile['session'], 'unavailable', error=ERROR)
        deadline = time.monotonic() + JOB_SECONDS
        child = None
        try:
            # The parent owns cleanup even if the worker is killed during SQLite backup.
            (ROOT / '.runtime').mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ROOT / '.runtime', prefix='investigation-live-') as owned:
                arguments = [sys.executable, '-I', '-c',
                    'import sys;sys.path.insert(0,sys.argv.pop(1));from tools.investigation_live import child_main;child_main()',
                    str(ROOT), str(self.directory), self.profile['session'], self.profile['source_commit'],
                    owned, str(deadline - REAP_SECONDS)]
                child = subprocess.Popen(arguments, cwd=ROOT, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True,
                    env=dict(PATH='/usr/bin:/bin', LANG='en_US.UTF-8', PYTHONNOUSERSITE='1'))
                try:
                    output = self._read(child, deadline - REAP_SECONDS)
                    child.wait(timeout=max(.001, deadline - time.monotonic() - REAP_SECONDS))
                    if child.returncode == 0 and not self._cancel.is_set():
                        bundle = decode_json(output, MAX_BUNDLE_BYTES)
                        # The owned child runs the strict shared validator before writing.
                        if (not isinstance(bundle, dict) or bundle.get('schema') != 'observer-investigation/1'
                                or len(bundle.get('cases', [])) != 1
                                or bundle['cases'][0].get('session') != self.profile['session']):
                            raise ControlError('Invalid child snapshot identity')
                        check_deadline(deadline)
                        result = envelope(self.profile['session'], 'ready', wall_ms=time.time() * 1000, bundle=bundle)
                finally:
                    if child.poll() is None:
                        child.kill()
                    try:
                        child.wait(timeout=REAP_SECONDS)
                    finally:
                        child.stdout.close()
        except (OSError, ValueError, TypeError, KeyError, ControlError, TimeoutError,
                subprocess.TimeoutExpired, UnicodeError, RecursionError):
            # Errors are deliberately generic: child paths/raw stderr never reach HTTP.
            result = envelope(self.profile['session'], 'unavailable', error=ERROR)
        finally:
            with self._lock:
                if not self._closed:
                    self._result = result

    def _read(self, child: subprocess.Popen, deadline: float) -> bytes:
        chunks, size = [], 0
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while True:
                check_deadline(deadline)
                if self._cancel.is_set():
                    raise TimeoutError('Investigation view closed')
                if not selector.select(min(.05, max(0, deadline - time.monotonic()))):
                    continue
                chunk = os.read(child.stdout.fileno(), min(65536, MAX_STDOUT_BYTES - size + 1))
                if not chunk:
                    return b''.join(chunks)
                size += len(chunk)
                if size > MAX_STDOUT_BYTES:
                    raise ControlError('Investigation child output exceeds bound')
                chunks.append(chunk)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._cancel.set()
            thread = self._thread
        if thread is not None:
            # _read wakes at least every 50ms; cleanup kills/reaps before this join returns.
            thread.join(JOB_SECONDS + REAP_SECONDS)
            if thread.is_alive():
                raise TimeoutError('Investigation child cleanup did not complete')


def child_main() -> None:
    try:
        directory, session, source_commit, owned, deadline = sys.argv[1:]
        bundle = snapshot_bundle(Path(directory), dict(session=session, source_commit=source_commit),
            Path(owned), float(deadline))
        sys.stdout.buffer.write(encoded_bundle(bundle))
        sys.stdout.buffer.flush()
    except (OSError, ValueError, TypeError, KeyError, ControlError, TimeoutError,
            sqlite3.Error, UnicodeError, RecursionError):
        raise SystemExit(1)
