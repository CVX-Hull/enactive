"""Append-only player-memory/1, explicitly selected independently of a session."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import math
from pathlib import Path
import sqlite3
import time
import uuid

from harness.computer.protocol import source as validate_source
from .contracts import PlayerError, bounded_integer, canonical, identity, json_object, record


class Memory:
    """Composition serializes use; HTTP calls may arrive on different threads."""
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
                    self._db.execute("INSERT INTO metadata VALUES ('player-memory/1')")
                    self._db.execute('CREATE TABLE sources (id TEXT PRIMARY KEY, metadata TEXT NOT NULL, png BLOB)')
                    self._db.execute('''CREATE TABLE programs (id TEXT PRIMARY KEY, document TEXT NOT NULL,
                        parent_id TEXT REFERENCES programs(id))''')
                    self._db.execute('''CREATE TABLE records (id TEXT PRIMARY KEY, document TEXT NOT NULL,
                        kind TEXT NOT NULL, supersedes TEXT REFERENCES records(id), program_id TEXT REFERENCES programs(id))''')
                    for table, owner, target in (
                        ('record_sources', 'records', 'sources'), ('record_supports', 'records', 'records'),
                        ('program_sources', 'programs', 'sources'), ('program_records', 'programs', 'records')):
                        self._db.execute(f'''CREATE TABLE {table} (owner TEXT NOT NULL REFERENCES {owner}(id),
                            target TEXT NOT NULL REFERENCES {target}(id), PRIMARY KEY(owner,target))''')
                    self._db.execute('CREATE INDEX corrections ON records(supersedes)')
                    self._db.execute('''CREATE TABLE service_operations(id TEXT PRIMARY KEY,actor TEXT NOT NULL,
                        tool TEXT NOT NULL,args TEXT NOT NULL,progress TEXT NOT NULL,result TEXT)''')
                    self._db.execute('PRAGMA user_version=1')
            elif version != 1 or tables != {'metadata', 'sources', 'programs', 'records', 'record_sources',
                                            'record_supports', 'program_sources', 'program_records', 'service_operations'}:
                raise PlayerError('Unsupported player store; select a fresh player-memory/1 store')
            if self._db.execute('SELECT schema FROM metadata').fetchall() != [('player-memory/1',)]:
                raise PlayerError('Unsupported player store version')
        except (sqlite3.Error, PlayerError) as exc:
            self.close()
            raise PlayerError(f'Cannot open current player memory: {exc}') from exc

    @contextmanager
    def _transaction(self):
        try:
            with self._db:
                self._db.execute('BEGIN IMMEDIATE')
                yield
        except sqlite3.Error as exc:
            raise PlayerError(f'Cannot remember: {exc}') from exc

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self._db.close()

    def _document(self, table: str, item_id: str) -> dict:
        identity(item_id)
        try:
            row = self._db.execute(f'SELECT document FROM {table} WHERE id=?', (item_id,)).fetchone()
        except sqlite3.Error as exc:
            raise PlayerError(f'Cannot read player memory: {exc}') from exc
        if row is None:
            raise PlayerError(f'Unknown {table} identity: {item_id}')
        result = json_object(row[0])
        # Consume current stored data without accepting an executable old format.
        assigned = {'id', 'actor_id', 'created_wall'} | ({'sha256'} if table == 'programs' else set())
        if not assigned <= result.keys():
            raise PlayerError('Stored player metadata is incomplete')
        identity(result['actor_id'])
        if (type(result['created_wall']) not in (int, float)
                or not math.isfinite(result['created_wall']) or result['created_wall'] < 0):
            raise PlayerError('Stored creation time is invalid')
        payload = {k:v for k,v in result.items() if k not in assigned}
        if table == 'records':
            record(payload)
        else:
            from .contracts import program
            program(payload)
            if hashlib.sha256(result['code'].encode('utf-8')).hexdigest() != result.get('sha256'):
                raise PlayerError('Stored program source SHA differs')
        if result.get('id') != item_id:
            raise PlayerError('Stored player identity differs')
        return result

    def read(self, item_id: str) -> dict:
        return self._document('records', item_id)

    def _references(self, table: str, refs: list[str]) -> None:
        for ref in refs:
            if self._db.execute(f'SELECT 1 FROM {table} WHERE id=?', (ref,)).fetchone() is None:
                raise PlayerError(f'Missing {table} reference: {ref}')

    def append(self, actor_id: str, value: dict, *, request_id: str | None = None) -> dict:
        identity(actor_id)
        value = record(value)
        stored = dict(value, id=request_id or uuid.uuid4().hex, actor_id=actor_id, created_wall=time.time())
        with self._transaction():
            prior = self._db.execute('SELECT 1 FROM records WHERE id=?',(stored['id'],)).fetchone()
            if prior:
                return self._original(stored['id'], actor_id, value)
            self._insert(stored)
        return stored

    @staticmethod
    def batch_ids(request_id: str, count: int) -> list[str]:
        """Record IDs of one multi-record request, derived so lost responses stay collectible."""
        return [hashlib.sha256(f'{request_id}:{index}'.encode()).hexdigest()[:32] for index in range(count)]

    def append_many(self, actor_id: str, values: list[dict], *, request_id: str,
                    service: tuple[str, dict, dict] | None = None,
                    sources: list[tuple[dict, bytes]] = ()) -> list[dict]:
        """Append 0..16 records in one transaction; a later record may reference an earlier one.

        `service` is `(tool, args, result)`: its correlation row and final result, with
        `records` filled in, commit in the same transaction, so no pending window exists.
        `sources` are exact `(metadata, png)` registrations made in that transaction too.
        """
        identity(actor_id)
        identity(request_id)
        if type(values) is not list or len(values) > 16 or not values and service is None:
            raise PlayerError('A multi-record append holds 1..16 records, or 0 with its service result')
        sources = [(self._valid_source(metadata, png), png) for metadata, png in sources]
        values = [record(value) for value in values]
        now = time.time()
        stored = [dict(value, id=item, actor_id=actor_id, created_wall=now)
                  for value, item in zip(values, self.batch_ids(request_id, len(values)), strict=True)]
        with self._transaction():
            if stored and self._db.execute('SELECT 1 FROM records WHERE id=?', (stored[0]['id'],)).fetchone():
                return [self._original(item['id'], actor_id, value) for item, value in zip(stored, values, strict=True)]
            for metadata, png in sources:
                self._insert_source(metadata, png)
            for item in stored:
                self._insert(item)
            if service is not None:
                tool, args, result = service
                self._db.execute('INSERT INTO service_operations VALUES(?,?,?,?,?,?)', (request_id, actor_id, tool,
                    canonical(args), canonical({'steps': []}), canonical(dict(result, records=stored))))
        return stored

    def _original(self, item_id: str, actor_id: str, value: dict) -> dict:
        original = self.read(item_id)
        if original['actor_id'] != actor_id or {k:v for k,v in original.items() if k not in {'id','actor_id','created_wall'}} != value:
            raise PlayerError('Original memory request identity conflicts')
        return original

    def _insert(self, stored: dict) -> None:
        self._references('sources', stored['sources'])
        self._references('records', stored['supports'] + ([stored['supersedes']] if stored['supersedes'] else []))
        self._references('programs', [stored['program_id']] if stored['program_id'] else [])
        self._db.execute('INSERT INTO records VALUES (?,?,?,?,?)',
                         (stored['id'], canonical(stored), stored['kind'], stored['supersedes'], stored['program_id']))
        for table, field in (('record_sources', 'sources'), ('record_supports', 'supports')):
            self._db.executemany(f'INSERT INTO {table} VALUES (?,?)', [(stored['id'], ref) for ref in stored[field]])

    def current(self, kind: str) -> list[dict]:
        """Every unsuperseded record of one kind, oldest first, without query's 50-record default."""
        try:
            rows = self._db.execute('''SELECT id FROM records r WHERE kind=?
                AND NOT EXISTS (SELECT 1 FROM records c WHERE c.supersedes=r.id) ORDER BY r.rowid''', (kind,)).fetchall()
            return [self.read(row[0]) for row in rows]
        except sqlite3.Error as exc:
            raise PlayerError(f'Cannot query player memory: {exc}') from exc

    def query(self, kind: str | None = None, limit: int = 50, include_superseded: bool = False) -> list[dict]:
        bounded_integer(limit, 1, 50)
        if kind is not None and (type(kind) is not str or kind not in {'claim', 'work', 'decision', 'procedure', 'correction', 'advice'}):
            raise PlayerError('Unknown player record kind')
        if type(include_superseded) is not bool:
            raise PlayerError('include_superseded must be boolean')
        try:
            rows = self._db.execute('''SELECT id FROM records r WHERE (? IS NULL OR kind=?)
                AND (? OR NOT EXISTS (SELECT 1 FROM records c WHERE c.supersedes=r.id))
                ORDER BY r.rowid DESC LIMIT ?''', (kind, kind, include_superseded, limit)).fetchall()
            return [self.read(row[0]) for row in rows]
        except sqlite3.Error as exc:
            raise PlayerError(f'Cannot query player memory: {exc}') from exc

    def register_source(self, metadata: dict, png: bytes) -> dict:
        metadata = self._valid_source(metadata, png)
        with self._transaction():
            self._insert_source(metadata, png)
        return metadata

    @staticmethod
    def _valid_source(metadata: dict, png: bytes) -> dict:
        try:
            metadata = json_object(metadata)
            validate_source(metadata)
            if type(png) is not bytes or len(png) > 64 * 1024 * 1024 or hashlib.sha256(png).hexdigest() != metadata['sha256']:
                raise PlayerError('Source bytes differ from their original SHA or exceed 64 MiB')
            if not png.startswith(b'\x89PNG\r\n\x1a\n'):
                raise PlayerError('Source must contain PNG bytes')
        except (ValueError, TypeError, UnicodeError) as exc:
            raise PlayerError(f'Cannot remember source: {exc}') from exc
        return metadata

    def source_bytes_left(self) -> int:
        used = self._db.execute('SELECT COALESCE(SUM(length(png)),0) FROM sources').fetchone()[0]
        return max(0, self.max_source_bytes - used)

    def _insert_source(self, metadata: dict, png: bytes) -> None:
        prior = self._db.execute('SELECT metadata,png FROM sources WHERE id=?', (metadata['source_id'],)).fetchone()
        if prior is not None:
            if prior != (canonical(metadata), png):
                raise PlayerError('Immutable source registration differs')
            return
        used = self._db.execute('SELECT COALESCE(SUM(length(png)),0) FROM sources').fetchone()[0]
        if used + len(png) > self.max_source_bytes:
            raise PlayerError('Cannot remember: source capacity exceeded; no images evicted')
        self._db.execute('INSERT INTO sources VALUES (?,?,?)', (metadata['source_id'], canonical(metadata), png))

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

    def context(self, ids: list[str], max_bytes: int = 65536) -> dict:
        from .context import build_context
        return build_context(self, ids, max_bytes=max_bytes)

    def begin_service(self, request_id: str, actor_id: str, tool: str, args: dict) -> bool:
        """Original player mutation correlation, never a control recovery log."""
        with self._transaction():
            prior = self._db.execute('SELECT actor,tool,args FROM service_operations WHERE id=?',(request_id,)).fetchone()
            if prior:
                if prior != (actor_id,tool,canonical(args)):
                    raise PlayerError('Original player-service identity conflicts')
                return False
            self._db.execute('INSERT INTO service_operations VALUES(?,?,?,?,?,NULL)',
                             (request_id,actor_id,tool,canonical(args),canonical({'steps':[]})))
            return True

    def service_step(self, request_id: str, step: dict) -> None:
        with self._transaction():
            row = self._db.execute('SELECT progress FROM service_operations WHERE id=?',(request_id,)).fetchone()
            if row is None:
                raise PlayerError('Unknown original player run')
            progress = json_object(row[0])
            if len(progress['steps']) >= 130:
                raise PlayerError('Original player-run step capacity exceeded')
            progress['steps'].append(json_object(step))
            self._db.execute('UPDATE service_operations SET progress=? WHERE id=?',(canonical(progress),request_id))

    def finish_service(self, request_id: str, result: dict) -> None:
        with self._transaction():
            if self._db.execute('UPDATE service_operations SET result=? WHERE id=? AND result IS NULL',
                                (canonical(result),request_id)).rowcount != 1:
                raise PlayerError('Original player-service result cannot be replaced')

    def service_result(self, request_id: str, actor_id: str | None = None) -> dict:
        row = self._db.execute('SELECT tool,progress,result,actor FROM service_operations WHERE id=? '
                               'AND (? IS NULL OR actor=?)',(request_id,actor_id,actor_id)).fetchone()
        if row is None:
            raise PlayerError('Unknown original player-service operation')
        result = json_object(row[2]) if row[2] is not None else None
        # A committed record/program has its preassigned request ID even if its
        # HTTP response was lost. Collection reads it; it never reruns authoring.
        if result is None and row[0] in ('player_memory_append','player_program_save'):
            table = 'records' if row[0] == 'player_memory_append' else 'programs'
            if self._db.execute(f'SELECT 1 FROM {table} WHERE id=?',(request_id,)).fetchone():
                result = self._document(table,request_id)
        return dict(schema='player-service-result/1',operation_id=request_id,actor_id=row[3],kind=row[0],
                    status='completed' if result is not None else 'pending',value=result,
                    progress=json_object(row[1]),grants_authority=False)
