"""Durable public call and hint journal, without control authority."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3
import time
from harness.computer.protocol import source as validate_source
from .contracts import PlayerError, bounded_integer, canonical, identity, json_object, references


class Journal:
    def __init__(self, path: str | Path, max_source_bytes: int = 268435456) -> None:
        self.max_source_bytes = bounded_integer(max_source_bytes, 0, 268435456)
        self._db = sqlite3.connect(path, timeout=1, check_same_thread=False)
        try:
            self._db.execute('PRAGMA foreign_keys=ON')
            tables = {r[0] for r in self._db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = self._db.execute('PRAGMA user_version').fetchone()[0]
            if not tables and version == 0:
                with self._transaction():
                    self._db.execute('CREATE TABLE metadata (schema TEXT NOT NULL)')
                    self._db.execute("INSERT INTO metadata VALUES ('player-journal/1')")
                    self._db.execute('CREATE TABLE sources (id TEXT PRIMARY KEY, metadata TEXT NOT NULL, png BLOB)')
                    self._db.execute('CREATE TABLE calls (id TEXT PRIMARY KEY, actor TEXT NOT NULL, tool TEXT NOT NULL, args TEXT NOT NULL)')
                    self._db.execute('CREATE TABLE hints (id TEXT PRIMARY KEY REFERENCES calls(id), document TEXT NOT NULL)')
                    self._db.execute('PRAGMA user_version=1')
            elif version != 1 or tables != {'metadata', 'sources', 'calls', 'hints'}:
                raise PlayerError('Unsupported player store; select a current player-journal/1 store')
            if self._db.execute('SELECT schema FROM metadata').fetchall() != [('player-journal/1',)]:
                raise PlayerError('Unsupported player store version')
        except (sqlite3.Error, PlayerError) as exc:
            self.close()
            raise PlayerError(f'Cannot open current player journal: {exc}') from exc

    @contextmanager
    def _transaction(self):
        try:
            with self._db:
                self._db.execute('BEGIN IMMEDIATE')
                yield
        except sqlite3.Error as exc:
            raise PlayerError(f'Cannot write journal: {exc}') from exc

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self._db.close()

    def has_source(self, source_id):
        return self._db.execute('SELECT 1 FROM sources WHERE id=?', (source_id,)).fetchone() is not None

    def register_source(self, metadata: dict, png: bytes) -> dict:
        try:
            metadata = json_object(metadata)
            validate_source(metadata)
            if type(png) is not bytes or len(png) > 64 * 1024 * 1024 or hashlib.sha256(png).hexdigest() != metadata['sha256']:
                raise PlayerError('Source bytes differ from their original SHA or exceed 64 MiB')
            if not png.startswith(b'\x89PNG\r\n\x1a\n'):
                raise PlayerError('Source must contain PNG bytes')
        except (ValueError, TypeError, UnicodeError) as exc:
            raise PlayerError(f'Cannot remember source: {exc}') from exc
        with self._transaction():
            prior = self._db.execute('SELECT metadata,png FROM sources WHERE id=?', (metadata['source_id'],)).fetchone()
            if prior is not None:
                if prior != (canonical(metadata), png):
                    raise PlayerError('Immutable source registration differs')
                return metadata
            used = self._db.execute('SELECT COALESCE(SUM(length(png)),0) FROM sources').fetchone()[0]
            if used + len(png) > self.max_source_bytes:
                raise PlayerError('Cannot remember: source capacity exceeded; no images evicted')
            self._db.execute('INSERT INTO sources VALUES (?,?,?)', (metadata['source_id'], canonical(metadata), png))
        return metadata

    def read_source(self, source_id: str) -> tuple[dict, bytes]:
        identity(source_id)
        try:
            row = self._db.execute('SELECT metadata,png FROM sources WHERE id=?', (source_id,)).fetchone()
            if row is None or row[1] is None:
                raise PlayerError(f'Source unavailable: {source_id}')
            metadata = json_object(row[0])
            validate_source(metadata)
            if metadata['source_id'] != source_id or hashlib.sha256(row[1]).hexdigest() != metadata['sha256']:
                raise PlayerError(f'Source SHA/identity differs: {source_id}')
            return metadata, row[1]
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise PlayerError(f'Cannot read source: {exc}') from exc

    def record_call(self, request_id, actor_id, tool, args):
        identity(request_id); identity(actor_id)
        encoded = canonical(args)
        with self._transaction():
            row = self._db.execute('SELECT actor,tool,args FROM calls WHERE id=?', (request_id,)).fetchone()
            if row:
                if row != (actor_id, tool, encoded):
                    raise PlayerError('Original public call identity conflicts')
                return False
            self._db.execute('INSERT INTO calls VALUES (?,?,?,?)', (request_id, actor_id, tool, encoded))
        return True

    def calls(self):
        return [dict(id=i, actor_id=a, tool=t, arguments=json_object(v)) for i,a,t,v in
                self._db.execute('SELECT id,actor,tool,args FROM calls ORDER BY rowid')]

    def hints(self):
        return [json_object(row[0]) for row in self._db.execute('SELECT document FROM hints ORDER BY rowid')]

    def hint_exists(self, request_id, actor_id):
        return self._db.execute('SELECT 1 FROM hints JOIN calls USING(id) WHERE id=? AND actor=?',
                                (request_id,actor_id)).fetchone() is not None

    def hint(self, request_id, actor_id, text, source_ids, intent, cites):
        if type(text) is not str or not 1 <= len(text) <= 8192:
            raise PlayerError('Hint text must be 1..8192 characters')
        references(source_ids)
        with self._transaction():
            row = self._db.execute('SELECT document FROM hints WHERE id=?', (request_id,)).fetchone()
            if row:
                return json_object(row[0])
            for ref in source_ids:
                if not self.has_source(ref):
                    raise PlayerError(f'Missing sources reference: {ref}')
            value = dict(schema='player-hint/1', id=request_id, actor_id=actor_id,
                         created_wall=time.time(), text=text, source_ids=source_ids, intent=intent, cites=cites)
            self._db.execute('INSERT INTO hints VALUES (?,?)', (request_id, canonical(value)))
            return value

    def service_result(self, request_id, actor_id):
        identity(request_id)
        row = self._db.execute('SELECT document FROM hints JOIN calls USING(id) WHERE id=? AND actor=?',
                               (request_id,actor_id)).fetchone()
        if row is None:
            raise PlayerError('Unknown original player-service operation')
        return dict(schema='player-service-result/2', operation_id=request_id, actor_id=actor_id,
                    kind='player_hint', status='completed', value=json_object(row[0]), grants_authority=False)
