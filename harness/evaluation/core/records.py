"""evaluation-record/1 storage (docs/contracts/evaluation.md).

One SQLite file per run and version pair. Raw rows (steps, binding readings, the
core's own `frame` and `input` readings) are appended once; derived rows (guarded
game time, events and metrics) are rewritten in one transaction on every pass, so a
live run can be evaluated incrementally and a finished run deterministically.
Hand-recorded `human` events are never touched by a pass.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Sequence

SCHEMA = 'evaluation-record/1'
CORE_VERSION = 1
EVENT_SOURCES = ('harness', 'reader', 'player_claim', 'human')
EVENT_KINDS = ('mode_change', 'long_activity', 'stall', 'ineffective_repeat', 'vital_change', 'threat_change',
    'milestone', 'death', 'handoff', 'memory_write', 'memory_read', 'program_save', 'program_run',
    'custody_stop', 'continuity', 'context_eviction', 'tool_refused')
#: Events a pass never rewrites: hand-recorded rows and lineage continuity.
PRESERVED = "source = 'human' OR kind = 'continuity'"


class EvaluationError(Exception):
    """An input or record that cannot be read as the current contract; never guessed around."""


def dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def loads(text: str | None) -> Any:
    return None if text is None else json.loads(text)


@dataclass(frozen=True)
class StepRow:
    seq: int
    operation_id: str
    actor: str
    kind: str
    wall: float
    decision: int | None
    tokens: int | None
    dollars: float | None
    game_time: int | None
    mode: str
    source_id: str | None
    frame_sha256: str | None
    frame_changed: bool | None


@dataclass(frozen=True)
class ReadingRow:
    seq: int
    reader: str
    reader_version: int
    value: object | None
    confidence: float | None
    abstain: str | None


@dataclass(frozen=True)
class EventRow:
    seq_start: int
    seq_end: int
    kind: str
    source: str
    confidence: float | None
    payload: dict

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f'unknown event kind {self.kind!r}')
        if self.source not in EVENT_SOURCES:
            raise ValueError(f'unknown event source {self.source!r}')
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError('event confidence must be within 0..1')

    def sort_key(self) -> tuple:
        return (self.seq_start, self.seq_end, self.kind, dumps(self.payload))


@dataclass(frozen=True)
class MetricRow:
    """`count` and `denominator` are stored for every metric; `denominator` is NULL only where
    the contract's table gives none ("—")."""

    name: str
    version: int
    value: object | None
    count: int | None
    denominator: float | None
    missing: str | None


def number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def record_path(root: Path, session: str, binding_id: str, binding_version: int) -> Path:
    return Path(root) / session / f'{CORE_VERSION}-{binding_id}-{binding_version}.sqlite3'


_DDL = f'''
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE steps(seq INTEGER PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE, actor TEXT NOT NULL,
    kind TEXT NOT NULL, wall REAL NOT NULL, decision INTEGER, tokens INTEGER, dollars REAL, game_time INTEGER,
    mode TEXT NOT NULL, source_id TEXT, frame_sha256 TEXT, frame_changed INTEGER);
CREATE TABLE readings(seq INTEGER NOT NULL REFERENCES steps(seq), reader TEXT NOT NULL,
    reader_version INTEGER NOT NULL, value TEXT, confidence REAL, abstain TEXT,
    PRIMARY KEY(seq, reader), CHECK(abstain IS NULL OR value IS NULL));
CREATE TABLE events(id INTEGER PRIMARY KEY, seq_start INTEGER NOT NULL, seq_end INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ({','.join(repr(k) for k in EVENT_KINDS)})),
    source TEXT NOT NULL CHECK(source IN ({','.join(repr(s) for s in EVENT_SOURCES)})),
    confidence REAL CHECK(confidence IS NULL OR confidence BETWEEN 0 AND 1), payload TEXT NOT NULL);
CREATE INDEX events_by_seq ON events(seq_start, kind);
CREATE TABLE metrics(name TEXT PRIMARY KEY, version INTEGER NOT NULL, value TEXT, count INTEGER,
    denominator REAL, missing TEXT);
PRAGMA user_version=1;
'''


class RecordWriter:
    """Create or reopen one record. All writes of one pass share a transaction."""

    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self.path = path
        self.connection = connection

    @classmethod
    def create(cls, path: Path, metadata: dict[str, object], *, replace: bool = False) -> 'RecordWriter':
        path = Path(path)
        if path.exists():
            if not replace:
                raise EvaluationError(f'{path}: an evaluation record for these versions exists; pass replace=True to rewrite it')
            for suffix in ('', '-wal', '-shm'):
                Path(str(path) + suffix).unlink(missing_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=1, isolation_level=None)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA foreign_keys=ON')
        writer = cls(path, connection)
        connection.execute('BEGIN IMMEDIATE')
        try:
            for statement in _DDL.split(';\n'):
                if statement.strip():
                    connection.execute(statement)
            writer.set_metadata({'schema': SCHEMA, **metadata})
            connection.execute('COMMIT')
        except BaseException:
            connection.execute('ROLLBACK')
            connection.close()
            raise
        return writer

    @classmethod
    def open(cls, path: Path) -> 'RecordWriter':
        path = Path(path)
        if not path.is_file():
            raise EvaluationError(f'{path}: no evaluation record to append to')
        connection = sqlite3.connect(path, timeout=1, isolation_level=None)
        _check_record(connection, path)
        connection.execute('PRAGMA foreign_keys=ON')
        return cls(path, connection)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> 'RecordWriter':
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def transaction(self) -> '_Transaction':
        return _Transaction(self.connection)

    def set_metadata(self, values: dict[str, object]) -> None:
        self.connection.executemany('INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            [(key, dumps(value)) for key, value in values.items()])

    def metadata(self) -> dict[str, Any]:
        return {key: loads(value) for key, value in self.connection.execute('SELECT key,value FROM metadata')}

    def append_steps(self, steps: Iterable[StepRow], readings: Iterable[ReadingRow]) -> None:
        self.connection.executemany('INSERT INTO steps VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', [
            (s.seq, s.operation_id, s.actor, s.kind, s.wall, s.decision, s.tokens, s.dollars, s.game_time, s.mode,
             s.source_id, s.frame_sha256, None if s.frame_changed is None else int(s.frame_changed)) for s in steps])
        self.connection.executemany('INSERT INTO readings VALUES(?,?,?,?,?,?)', [
            (r.seq, r.reader, r.reader_version, None if r.value is None else dumps(r.value), r.confidence, r.abstain)
            for r in readings])

    def delete_from(self, seq: int) -> None:
        """Remove steps and their readings from `seq` on, so they can be read again."""
        self.connection.execute('DELETE FROM readings WHERE seq >= ?', (seq,))
        self.connection.execute('DELETE FROM steps WHERE seq >= ?', (seq,))

    def replace_readings(self, reader: str, readings: Sequence[ReadingRow]) -> None:
        self.connection.execute('DELETE FROM readings WHERE reader=?', (reader,))
        self.connection.executemany('INSERT INTO readings VALUES(?,?,?,?,?,?)', [
            (r.seq, r.reader, r.reader_version, None if r.value is None else dumps(r.value), r.confidence, r.abstain)
            for r in readings])

    def set_game_times(self, times: Sequence[tuple[int, int | None]]) -> None:
        self.connection.executemany('UPDATE steps SET game_time=? WHERE seq=?', [(t, seq) for seq, t in times])

    def replace_events(self, events: Sequence[EventRow]) -> None:
        self.connection.execute(f'DELETE FROM events WHERE NOT ({PRESERVED})')
        start = (self.connection.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]) + 1
        ordered = sorted(events, key=EventRow.sort_key)
        self.connection.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?)', [
            (start + index, e.seq_start, e.seq_end, e.kind, e.source, e.confidence, dumps(e.payload))
            for index, e in enumerate(ordered)])

    def replace_continuity(self, events: Sequence[EventRow]) -> None:
        self.connection.execute("DELETE FROM events WHERE kind='continuity'")
        start = (self.connection.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]) + 1
        self.connection.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?)', [
            (start + index, e.seq_start, e.seq_end, e.kind, e.source, e.confidence, dumps(e.payload))
            for index, e in enumerate(sorted(events, key=EventRow.sort_key))])

    def replace_metrics(self, metrics: Sequence[MetricRow], *, keep: Sequence[str] = ()) -> None:
        marks = ','.join('?' * len(keep))
        self.connection.execute(f'DELETE FROM metrics WHERE name NOT IN ({marks})' if keep else 'DELETE FROM metrics', tuple(keep))
        self.connection.executemany('INSERT OR REPLACE INTO metrics VALUES(?,?,?,?,?,?)', [
            (m.name, m.version, None if m.value is None else dumps(m.value), m.count, m.denominator, m.missing)
            for m in metrics])

    def upsert_metrics(self, metrics: Sequence[MetricRow], *, replace: bool = True) -> None:
        verb = 'REPLACE' if replace else 'IGNORE'
        self.connection.executemany(f'INSERT OR {verb} INTO metrics VALUES(?,?,?,?,?,?)', [
            (m.name, m.version, None if m.value is None else dumps(m.value), m.count, m.denominator, m.missing)
            for m in metrics])

    # Reads over the stored record ----------------------------------------------------------

    def steps(self) -> list[StepRow]:
        return read_steps(self.connection)

    def readings(self) -> list[ReadingRow]:
        return read_readings(self.connection)

    def events(self) -> list[dict]:
        return read_events(self.connection)


class _Transaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> None:
        self.connection.execute('BEGIN IMMEDIATE')

    def __exit__(self, exc_type: object, *_: object) -> None:
        self.connection.execute('ROLLBACK' if exc_type else 'COMMIT')


def read_steps(connection: sqlite3.Connection) -> list[StepRow]:
    return [StepRow(*row[:12], None if row[12] is None else bool(row[12])) for row in connection.execute(
        'SELECT seq,operation_id,actor,kind,wall,decision,tokens,dollars,game_time,mode,source_id,frame_sha256,'
        'frame_changed FROM steps ORDER BY seq')]


def read_readings(connection: sqlite3.Connection) -> list[ReadingRow]:
    return [ReadingRow(r[0], r[1], r[2], loads(r[3]), r[4], r[5]) for r in connection.execute(
        'SELECT seq,reader,reader_version,value,confidence,abstain FROM readings ORDER BY seq, reader')]


def read_events(connection: sqlite3.Connection) -> list[dict]:
    return [dict(id=r[0], seq_start=r[1], seq_end=r[2], kind=r[3], source=r[4], confidence=r[5], payload=loads(r[6]))
        for r in connection.execute('SELECT id,seq_start,seq_end,kind,source,confidence,payload FROM events ORDER BY id')]


def open_readonly(path: Path) -> sqlite3.Connection:
    """Read-only access to a finished or live record for comparison and views."""
    path = Path(path)
    if not path.is_file():
        raise EvaluationError(f'{path}: missing evaluation record')
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
    _check_record(connection, path)
    return connection


def _check_record(connection: sqlite3.Connection, path: Path) -> None:
    """Close the connection and raise unless this is a current evaluation-record/1 file."""
    try:
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        row = connection.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
    except sqlite3.Error as exc:
        connection.close()
        raise EvaluationError(f'{path}: not an evaluation record ({exc})') from exc
    found = loads(row[0]) if row else None
    if version != 1 or found != SCHEMA:
        connection.close()
        raise EvaluationError(f'{path}: unsupported evaluation record version {found!r} (user_version {version}); '
            f'current is {SCHEMA}')


def read_metadata(connection: sqlite3.Connection) -> dict[str, Any]:
    return {key: loads(value) for key, value in connection.execute('SELECT key,value FROM metadata')}


def read_metrics(connection: sqlite3.Connection) -> dict[str, MetricRow]:
    return {r[0]: MetricRow(r[0], r[1], loads(r[2]), r[3], r[4], r[5])
        for r in connection.execute('SELECT name,version,value,count,denominator,missing FROM metrics ORDER BY name')}
