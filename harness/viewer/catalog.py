"""Read-only discovery and caching of evaluation stores and run directories.

`Catalog` scans `<root>/<session>/<core>-<binding>-<version>.sqlite3` files read-only, keeps the newest binding
version per session, resolves each session to its run directory (the store's recorded path, else a scan of the
`--runs` directories and the live run) and caches one digest per store state (size and modification time of the
file and its WAL). Nothing here writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from harness.evaluation.core.records import (EvaluationError, open_readonly, read_metadata, read_metrics, read_run_facts)

API = 'spectator-view/1'
DATA_DIR = Path(__file__).resolve().parents[2] / 'data' / 'evaluation'


class ViewError(Exception):
    def __init__(self, status: int, code: str, detail: str = '') -> None:
        super().__init__(code)
        self.status, self.code, self.detail = status, code, detail


@dataclass
class RunInfo:
    session: str
    run: str
    path: Path
    run_dir: Path | None
    meta: dict
    facts: dict
    metrics: dict[tuple[str, str], Any]
    decisions: int
    dollars: float

    @property
    def state(self) -> str:
        return self.meta.get('state', 'final')

    @property
    def labels(self) -> dict:
        return self.facts.get('labels') or {}

    def metric(self, name: str, key: str = '') -> Any:
        row = self.metrics.get((name, key))
        return None if row is None else row.value

    @property
    def survival(self) -> dict | None:
        value = self.metric('survival.game_hours')
        return value if isinstance(value, dict) else None

    @property
    def lost(self) -> bool:
        return bool(self.metric('run.infrastructure_loss'))


def stamp(path: Path) -> tuple:
    parts = []
    for suffix in ('', '-wal'):
        try:
            status = Path(str(path) + suffix).stat()
            parts.append((status.st_mtime_ns, status.st_size))
        except OSError:
            parts.append(None)
    return tuple(parts)


class Catalog:
    def __init__(self, root: Path, runs_dirs: tuple[Path, ...] = (), live_run: Path | None = None,
                 data_dir: Path = DATA_DIR) -> None:
        self.root = Path(root)
        self.runs_dirs = tuple(Path(p) for p in runs_dirs)
        self.live_run = Path(live_run) if live_run is not None else None
        self.data_dir = Path(data_dir)
        self._cache: dict[Path, tuple[tuple, RunInfo]] = {}
        self._dirs: dict[str, Path] = {}
        self._lock = threading.Lock()

    # Discovery -----------------------------------------------------------------------------------

    def _directories(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        candidates = [self.live_run] if self.live_run is not None else []
        for directory in self.runs_dirs:
            candidates.extend(sorted(p for p in directory.iterdir() if p.is_dir())) if directory.is_dir() else None
        for candidate in candidates:
            manifest = candidate / 'manifest.json'
            if manifest.is_file():
                try:
                    session = json.loads(manifest.read_text()).get('session')
                except (OSError, ValueError):
                    continue
                if isinstance(session, str):
                    found.setdefault(session, candidate)
        return found

    def run_dir_for(self, session: str, meta: dict) -> Path | None:
        recorded = meta.get('run_dir')
        if isinstance(recorded, str) and Path(recorded).is_dir():
            return Path(recorded)
        with self._lock:
            if session not in self._dirs:
                self._dirs = self._directories()
            return self._dirs.get(session)

    def _load(self, path: Path) -> RunInfo | None:
        state = stamp(path)
        cached = self._cache.get(path)
        if cached is not None and cached[0] == state:
            return cached[1]
        try:
            connection = open_readonly(path)
        except (EvaluationError, sqlite3.Error):
            return None
        try:
            meta, facts, metrics = read_metadata(connection), read_run_facts(connection), read_metrics(connection)
            decisions, dollars = connection.execute('SELECT MAX(decision), MAX(dollars) FROM steps').fetchone()
            spend = connection.execute('SELECT SUM(dollars) FROM requests').fetchone()[0]
        except sqlite3.Error:
            return None
        finally:
            connection.close()
        session = meta.get('session')
        if not isinstance(session, str):
            return None
        info = RunInfo(session, str(meta.get('run') or session), path, self.run_dir_for(session, meta), meta, facts, metrics,
            decisions or 0, float(spend if spend is not None else dollars or 0.0))
        self._cache[path] = (state, info)
        return info

    def runs(self) -> list[RunInfo]:
        """One entry per session: the newest binding version's store, sorted by run name."""
        newest: dict[str, RunInfo] = {}
        for path in sorted(self.root.glob('*/*.sqlite3')) if self.root.is_dir() else ():
            info = self._load(path)
            if info is None:
                continue
            best = newest.get(info.session)
            if best is None or (info.meta.get('binding_version', 0), info.meta.get('core_version', 0)) >= (
                    best.meta.get('binding_version', 0), best.meta.get('core_version', 0)):
                newest[info.session] = info
        return sorted(newest.values(), key=lambda i: (i.run, i.session))

    def find(self, identifier: str) -> RunInfo:
        """A run by session ID, or by its run directory name."""
        runs = self.runs()
        for info in runs:
            if info.session == identifier:
                return info
        for info in runs:
            if info.run == identifier:
                return info
        raise ViewError(404, 'unknown_run', identifier)

    def connect(self, info: RunInfo) -> sqlite3.Connection:
        try:
            return open_readonly(info.path)
        except (EvaluationError, sqlite3.Error) as exc:
            raise ViewError(503, 'record_unavailable', str(exc)) from exc

    def need_run_dir(self, info: RunInfo) -> Path:
        if info.run_dir is None:
            raise ViewError(404, 'run_directory_unavailable', info.run)
        return info.run_dir

    # Human-authored data -------------------------------------------------------------------------

    def data_json(self, name: str, default: Any) -> Any:
        path = self.data_dir / name
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            return default
        except ValueError as exc:
            raise ViewError(500, 'bad_data_file', f'{name}: {exc}') from exc

    def labels(self) -> list[dict]:
        path = self.data_dir / 'labels.jsonl'
        if not path.is_file():
            return []
        rows = []
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError as exc:
                    raise ViewError(500, 'bad_data_file', f'labels.jsonl:{number}: {exc}') from exc
        return rows

    def taxonomy(self) -> dict:
        return self.data_json('taxonomy.json', dict(version=1, codes=[]))

    def changes(self) -> list[dict]:
        return self.data_json('changes.json', [])

    def validation(self) -> dict:
        return self.data_json('reader-validation.json', {})
