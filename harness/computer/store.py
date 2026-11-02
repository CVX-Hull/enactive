"""Fresh mechanical session records; SQLite owns transactions and constraints."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from .protocol import ControlError, canonical, decode_json, source


class SessionStore:
    """One current store, never a route to reconstruct live custody."""

    def __init__(self, directory: Path, session: str, limits: dict[str, int], deadline: float) -> None:
        self.directory = directory
        self.path = directory / 'session.sqlite3'
        if self.path.exists():
            raise ControlError('Session store exists; no authority restoration')
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(self.path, timeout=.25, check_same_thread=False)
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.executescript('''
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE resources(id INTEGER PRIMARY KEY CHECK(id=1),
                inputs INTEGER NOT NULL DEFAULT 0, requests INTEGER NOT NULL DEFAULT 0,
                frames INTEGER NOT NULL DEFAULT 0, bytes INTEGER NOT NULL DEFAULT 0);
            INSERT INTO resources(id) VALUES(1);
            CREATE TABLE actors(id TEXT PRIMARY KEY,token_hash TEXT NOT NULL UNIQUE,
                stage TEXT NOT NULL CHECK(stage IN ('active','sealed','quiescent','reader')),
                serves TEXT REFERENCES actors(id),
                reader_role TEXT CHECK(reader_role IN ('level','recorder')),
                CHECK((stage='reader')=(serves IS NOT NULL) AND (stage='reader')=(reader_role IS NOT NULL)));
            CREATE UNIQUE INDEX sole_active_actor ON actors(stage) WHERE stage='active';
            CREATE UNIQUE INDEX one_reader_per_actor_role ON actors(serves,reader_role) WHERE serves IS NOT NULL;
            CREATE TABLE operations(id TEXT PRIMARY KEY,actor TEXT NOT NULL REFERENCES actors(id),
                kind TEXT NOT NULL CHECK(kind IN ('input','observe','handoff')),
                created_wall REAL NOT NULL,deadline REAL NOT NULL,input_json TEXT NOT NULL,
                final_json TEXT);
            CREATE TABLE native_intents(id TEXT PRIMARY KEY,operation TEXT NOT NULL REFERENCES operations(id),
                receipt TEXT,source TEXT REFERENCES sources(id),timing TEXT NOT NULL);
            CREATE TABLE sources(id TEXT PRIMARY KEY,metadata TEXT NOT NULL,bytes INTEGER NOT NULL);
            CREATE TABLE issued_sources(actor TEXT NOT NULL REFERENCES actors(id),
                source TEXT NOT NULL REFERENCES sources(id),PRIMARY KEY(actor,source));
            CREATE TABLE collections(native_id TEXT PRIMARY KEY REFERENCES native_intents(id),
                receipt TEXT NOT NULL,source TEXT REFERENCES sources(id));
            PRAGMA user_version=3;
        ''')
        with self.connection:
            self.connection.executemany('INSERT INTO metadata VALUES(?,?)', [
                ('schema', canonical('computer-session/3')),('session', canonical(session)),
                ('limits', canonical(limits)), ('deadline_monotonic', canonical(deadline))])
        (directory / 'sources').mkdir(mode=0o700)
        self.limits = limits.copy()

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def counts(self) -> dict[str, int]:
        with self.lock:
            row = self.connection.execute('SELECT inputs,requests,frames,bytes FROM resources WHERE id=1').fetchone()
            return dict(zip(('inputs', 'requests', 'frames', 'frame_bytes'), row, strict=True))

    def add_actor(self, identity: str, token_hash: str, serves: str | None = None, role: str | None = None) -> None:
        """An actor, or a reader (`serves` and `role`, `level` or `recorder`); one reader per (served actor, role)."""
        with self.lock, self.connection:
            self.connection.execute('INSERT INTO actors VALUES(?,?,?,?,?)',
                                    (identity, token_hash, 'active' if serves is None else 'reader', serves, role))

    def actor_log(self, actor_id: str, after: int, limit: int) -> list[dict[str, Any]]:
        """The served actor's operations in store order; positions are 1-based per actor.

        An in-process projection for the driver and the custodian; no tool serves it.
        """
        with self.lock:
            rows = self.connection.execute('SELECT id,kind,input_json,final_json FROM operations WHERE actor=? '
                'ORDER BY rowid LIMIT ? OFFSET ?', (actor_id, limit, after)).fetchall()
        entries = []
        for position, (identity, kind, actions, final) in enumerate(rows, after + 1):
            result = decode_json(final, 262144) if final is not None else None
            entries.append(dict(position=position, operation_id=identity, kind=kind,
                actions=decode_json(actions) if kind == 'input' else None,
                status=result['status'] if result else 'pending',
                source_id=result['source']['source_id'] if result and result.get('source') else None))
        return entries

    def actor_counts(self, actor_id: str) -> tuple[int, int]:
        """The served actor's log length and its input operations, for mechanical wake rules."""
        with self.lock:
            return self.connection.execute("SELECT COUNT(*),COALESCE(SUM(kind='input'),0) FROM operations WHERE actor=?",
                                           (actor_id,)).fetchone()

    def inputs_after(self, actor_id: str, position: int) -> int:
        with self.lock:
            return self.connection.execute('SELECT COUNT(*) FROM (SELECT kind FROM operations WHERE actor=? '
                'ORDER BY rowid LIMIT -1 OFFSET ?) WHERE kind=?', (actor_id, position, 'input')).fetchone()[0]

    def actor_stage(self, identity: str) -> str | None:
        with self.lock:
            row = self.connection.execute('SELECT stage FROM actors WHERE id=?', (identity,)).fetchone()
            return row[0] if row else None

    def set_actor_stage(self, identity: str, stage: str) -> None:
        with self.lock, self.connection:
            self.connection.execute('UPDATE actors SET stage=? WHERE id=?', (stage, identity))

    def begin(self, operation: dict[str, Any], actions: object, input_count: int) -> bool:
        """False means this exact ID already exists: collect it, never dispatch."""
        with self.lock, self.connection:
            if self.connection.execute('SELECT 1 FROM operations WHERE id=?', (operation['operation_id'],)).fetchone():
                return False
            changed = self.connection.execute('''UPDATE resources SET inputs=inputs+?,requests=requests+1
                WHERE id=1 AND inputs+?<=? AND requests<?''',
                (input_count, input_count, self.limits['max_inputs'], self.limits['max_requests'])).rowcount
            if changed != 1:
                raise ControlError('Original input/request capacity exhausted')
            self.connection.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,NULL)',
                (operation['operation_id'], operation['actor_id'], operation['kind'],
                 operation['created_wall'], operation['deadline_monotonic'], canonical(actions)))
            return True

    def native_intent(self, operation_id: str, native_id: str) -> None:
        with self.lock, self.connection:
            self.connection.execute('INSERT INTO native_intents(id,operation,timing) VALUES(?,?,?)',
                (native_id, operation_id,canonical(dict(intent_wall=time.time(),intent_monotonic=time.monotonic()))))

    def native_result(self, native_id: str, value: dict[str, Any], source_id: str | None,
                      timing: dict[str,float] | None = None) -> None:
        with self.lock, self.connection:
            prior=self.connection.execute('SELECT timing FROM native_intents WHERE id=?',(native_id,)).fetchone()
            stamps=decode_json(prior[0]) if prior else {}
            stamps.update(timing or {})
            changed = self.connection.execute('UPDATE native_intents SET receipt=?,source=?,timing=? WHERE id=? AND receipt IS NULL',
                (canonical(value), source_id, canonical(stamps), native_id)).rowcount
            if changed != 1:
                raise ControlError('Original native receipt cannot be replaced')

    def link_native_source(self, native_id: str, source_id: str) -> None:
        with self.lock, self.connection:
            self.connection.execute('UPDATE native_intents SET source=? WHERE id=? AND source IS NULL',
                                    (source_id, native_id))

    def finish(self, result: dict[str, Any], *, seal_actor: bool = False) -> None:
        with self.lock, self.connection:
            changed = self.connection.execute('UPDATE operations SET final_json=? WHERE id=? AND final_json IS NULL',
                (canonical(result), result['operation_id'])).rowcount
            if changed != 1:
                raise ControlError('Original terminal operation cannot be replaced')
            if seal_actor:
                self.connection.execute("UPDATE actors SET stage='sealed' WHERE id=? AND stage='active'",
                                        (result['actor_id'],))

    def operation(self, identity: str, actor: str | None = None) -> dict[str, Any]:
        with self.lock:
            row = self.connection.execute('SELECT actor,kind,created_wall,deadline,final_json FROM operations WHERE id=?',
                                          (identity,)).fetchone()
            if row is None or actor is not None and row[0] != actor:
                raise ControlError('Unknown original operation for this actor')
            if row[4] is not None:
                result = decode_json(row[4], 262144)
            else:
                session = decode_json(self.connection.execute("SELECT value FROM metadata WHERE key='session'").fetchone()[0])
                result = dict(schema='computer-operation/1', operation_id=identity, session=session,
                    actor_id=row[0], kind=row[1], status='pending', created_wall=row[2],
                    deadline_monotonic=row[3], receipts=[], source=None, remaining={},
                    reason='Original intent retained; delivery not settled', handoff=None)
            original = self.connection.execute('SELECT receipt,source FROM native_intents WHERE operation=? '
                'AND receipt IS NOT NULL ORDER BY rowid', (identity,)).fetchall()
            result['receipts'] = [decode_json(r[0]) for r in original]
            for _, source_id in original:
                if source_id:
                    result['source'] = self.source_metadata(source_id)
            additions = self.connection.execute('SELECT receipt,source FROM collections WHERE native_id IN '
                '(SELECT id FROM native_intents WHERE operation=?) ORDER BY rowid', (identity,)).fetchall()
            if additions:
                # Original terminal status/unknown receipt stays unchanged. Later
                # native receipts are additional evidence, never replay authority.
                result['receipts'] = [*result['receipts'], *(decode_json(r[0]) for r in additions)]
                for _, source_id in additions:
                    if source_id:
                        result['source'] = self.source_metadata(source_id)
            return result

    def operation_exists(self, identity: str, actor: str | None = None) -> bool:
        with self.lock:
            if actor is None:
                return self.connection.execute('SELECT 1 FROM operations WHERE id=?',(identity,)).fetchone() is not None
            return self.connection.execute('SELECT 1 FROM operations WHERE id=? AND actor=?',
                                           (identity, actor)).fetchone() is not None

    def native_records(self, operation_id: str) -> list[tuple[str,dict | None]]:
        with self.lock:
            return [(r[0],decode_json(r[1]) if r[1] is not None else None) for r in self.connection.execute(
                'SELECT id,receipt FROM native_intents WHERE operation=? ORDER BY rowid',(operation_id,))]

    def add_collection(self, native_id: str, value: dict[str, Any], source_id: str | None) -> None:
        with self.lock, self.connection:
            self.connection.execute('INSERT OR IGNORE INTO collections VALUES(?,?,?)',
                                    (native_id, canonical(value), source_id))

    def has_source(self, source_id: str, actor_id: str | None = None) -> bool:
        with self.lock:
            if actor_id is None:
                return self.connection.execute('SELECT 1 FROM sources WHERE id=?', (source_id,)).fetchone() is not None
            return self.connection.execute('SELECT 1 FROM issued_sources WHERE actor=? AND source=?',
                                           (actor_id, source_id)).fetchone() is not None

    def issue_source(self, actor_id: str, source_id: str) -> None:
        with self.lock, self.connection:
            self.connection.execute('INSERT OR IGNORE INTO issued_sources VALUES(?,?)', (actor_id, source_id))

    def put_source(self, metadata: dict[str, Any], png: bytes, actor_id: str) -> dict[str, Any]:
        source(metadata)
        identity = metadata['source_id']
        with self.lock:
            prior = self.connection.execute('SELECT metadata FROM sources WHERE id=?', (identity,)).fetchone()
            if prior:
                stable = decode_json(prior[0])
                # received_wall belongs to the first receipt, not this reread.
                proposed = dict(metadata, received_wall=stable['received_wall'])
                if stable != proposed:
                    raise ControlError('Immutable source identity changed')
                with self.connection:
                    self.connection.execute('INSERT OR IGNORE INTO issued_sources VALUES(?,?)', (actor_id, identity))
                return stable
            counts = self.counts()
            if counts['frames'] >= self.limits['max_frames'] or counts['frame_bytes'] + len(png) > self.limits['max_bytes']:
                raise ControlError('Original retained-frame capacity exhausted')
            path = self.directory / 'sources' / (identity + '.png')
            try:
                with path.open('xb') as stream:
                    stream.write(png)
            except FileExistsError:
                # A failed index transaction may leave this exact owned image.
                # Collection can index its original in-memory packet, never
                # replace other bytes or restore input authority.
                if path.is_symlink() or path.read_bytes() != png:
                    raise ControlError('Unindexed original source differs; retained without replacement')
            with self.connection:
                self.connection.execute('INSERT INTO sources VALUES(?,?,?)', (identity, canonical(metadata), len(png)))
                self.connection.execute('INSERT INTO issued_sources VALUES(?,?)', (actor_id, identity))
                self.connection.execute('UPDATE resources SET frames=frames+1,bytes=bytes+? WHERE id=1', (len(png),))
            return metadata

    def source_metadata(self, identity: str) -> dict[str, Any]:
        with self.lock:
            row = self.connection.execute('SELECT metadata FROM sources WHERE id=?', (identity,)).fetchone()
            if row is None:
                raise ControlError('Unknown retained source')
            value = source(decode_json(row[0]))
            if value['source_id'] != identity:
                raise ControlError('Retained source index identity differs')
            return value

    def read_source(self, identity: str) -> tuple[dict[str, Any], bytes]:
        metadata = self.source_metadata(identity)
        path = self.directory / 'sources' / (identity + '.png')
        if path.is_symlink() or not path.is_file():
            raise ControlError('Retained source unavailable')
        with path.open('rb') as stream:
            png = stream.read(67108865)
        if len(png) > 67108864 or hashlib.sha256(png).hexdigest() != metadata['sha256']:
            raise ControlError('Retained source integrity failed')
        return metadata, png
