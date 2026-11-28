"""Stage a readable snapshot of a session store that is still being written (#837).

The custodian writes `session.sqlite3` in write-ahead-log mode until the run closes. `sealed()`
refuses such a store, and should. `stage` copies its finished rows into a fresh store in one
bounded read transaction on a read-only, non-immutable connection, and stages a session
directory under the run directory's own name beside it, which the projection and windows then
read through `sealed()` unchanged. The reader writes no file beside the live store (its
read-only connection can still update the store's shared-memory file, as any reader does), and
a snapshot that fails or passes its bound is discarded whole.

**Admission against the store's closing** (the names and the hold bound are in `.stores`).
`curator-read.lock` exists in the run directory only when a reader is configured, created before
the custodian starts and never removed or replaced while the session is live. A read opens that
existing file and never creates it (a missing one refuses the read), takes a shared non-blocking
`flock`, then checks that `store-closing.json` does not exist, then opens its connection, and
holds the lock until the connection is really closed. In close-out the custodian writes the
marker, then waits at most `READ_HOLD_BOUND_SECONDS` for an exclusive lock, then closes the
store. A read admitted before the marker is therefore waited for, and none is admitted after it.
Refusals are `ReadRefused`, not failures of a snapshot; a store still being created (an empty
file, or tables or identity not yet committed) is refused as `no-store`.

Both bounds run from the moment the shared lock is taken, since the custodian's wait starts
later, at the marker. The whole hold, to the lock's release, is bounded by
`READ_HOLD_BOUND_SECONDS`. The read transaction is cancelled at `TRANSACTION_BOUND_SECONDS` (a
progress handler, and the busy timeout), which leaves the rest of the hold for cancelling,
finalizing and closing. A read that passes either bound is discarded. An exception raised inside
the progress handler (a `KeyboardInterrupt`, say) cancels the statement and is raised again,
itself, once the connection is closed. "Really closed" matters: a connection closed while a
statement is still mid-result stays open underneath, with its read transaction and file
descriptors, and the custodian's close would then leave a non-empty log. So every statement runs
on its own cursor, closed before the next, and on every path the transaction is ended and the
connection closed before the lock is released.

**The cutoff, per actor, by identity across the store and the host's log.** An actor is
included only when, before the read is admitted, its frozen manifest (`frozen.json`,
`player-host-inputs/5`) is complete and so is every secret-guard input it has. Its frozen prompt
and guide and the custody and route files are copied, each checked against the manifest's
digest where it names one; a guard input the manifest does not bind (`host-process.json`,
`mcp-template.json`) that does not parse yet leaves the actor out of this snapshot. An actor has
*ended* only on evidence that existed before the read transaction began: the store shows it
`quiescent` in that transaction, or its host log, read before admission, holds a whole
`settled` line. Its operations are taken in the projection's order (created wall time, then
operation identity), and the snapshot carries the longest prefix of them in which each operation

- has its terminal row (`final_json`) in the read transaction, and,
- unless the actor has ended, has a matching result in the log (a whole `tool-result` line
  whose allowlisted outcome, read as the projection reads it, names the operation), and no
  collection outstanding (a native intent without a receipt, or with an unknown-transport
  receipt and no collection row).

The first operation that fails stops the prefix, so step numbers equal the sealed trace's
except in three cases this reader cannot see: a wall clock that steps back between two of one
actor's operations; two operations of one actor with identical created wall times, which sort by
identity, so a later one can sort first; and a frame linked to an operation after its terminal
row. The host log is read again after the transaction, for the cut only, as whole lines. When
every operation the transaction holds for an ended actor is included, its whole log is kept.
Otherwise the log is cut after the first result line of the last included operation, and a
`tool-start` left in that cut without its answer is dropped, so no call for an operation the
snapshot does not hold survives and none is attached to a neighbouring step.

**What a snapshot holds:** the fresh store (the live schema; metadata, the included actors and
their included operations, native intents, collections and the sources those name), the frames
those name, hard-linked or copied without overwrite and checked against their recorded digests,
each included actor's frozen inputs, custody and route files and cut host log, and the campaign
manifest and the supervisor's launch record of its digest when they exist. Not the player's
journal, the actors' final reports, handoff packets or receipts. The staged directory holds
custody files, as the run directory does, so it belongs outside any curator workspace; the
projection's guard keeps them out of the trace. The coverage of each actor (`ActorCoverage.steps`)
is the last step the snapshot actually read.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from .projection import SECRET_FILES, _agenda_event, _result
from .stores import CURATOR_READ_LOCK, READ_HOLD_BOUND_SECONDS, STORE_CLOSING_MARKER

TRANSACTION_BOUND_SECONDS = 1.5  # the read transaction is cancelled here, from the lock's taking
STORE = 'session.sqlite3'
STORE_SCHEMA = 'computer-session/1'
STORE_VERSION = 1
FROZEN_SCHEMA = 'player-host-inputs/5'
UNKNOWN_TRANSPORT = 'computer-transport/2'
FROZEN_INPUTS = ('prompt.txt', 'context.txt')
RUN_FILES = ('manifest.json', 'watch-start.json')
TABLES = ('metadata', 'actors', 'operations', 'native_intents', 'collections', 'sources')
PROGRESS_STEPS = 1000


class ReadRefused(Exception):
    """The live store does not admit a read now, and nothing was read. `reason` is `no-read-lock`
    (no reader is configured), `closing` (the custodian is closing the store) or `no-store` (no
    store, or one still being created)."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason


class SnapshotError(ValueError):
    """A snapshot failed and was discarded whole."""


class BoundExceeded(SnapshotError):
    """The read passed its bound and was cancelled; nothing was staged."""


@dataclass(frozen=True)
class ActorCoverage:
    """One included actor: its first `steps` operations, ending at `last_operation`."""

    directory: str
    actor_id: str
    steps: int
    last_operation: str | None
    ended: bool
    held_back: int  # operations in the read transaction not yet finished under the cutoff


@dataclass(frozen=True)
class Snapshot:
    directory: Path
    session_id: str
    actors: tuple[ActorCoverage, ...]
    excluded: tuple[str, ...]  # actors not included, each with why
    hold_seconds: float  # the shared read lock, from its taking to its release
    transaction_seconds: float  # the read transaction alone, BEGIN to COMMIT
    staging_seconds: float  # the whole call


@dataclass(frozen=True)
class _Actor:
    directory: str
    actor_id: str
    session: object
    settled: bool  # a whole `settled` line in its host log before admission
    files: dict[str, bytes]


@contextmanager
def admitted(run: Path):
    """Hold the shared read lock against the store's closing; yields when the lock was taken."""
    try:
        descriptor = os.open(run/CURATOR_READ_LOCK, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError as exc:
        raise ReadRefused('no-read-lock', f'{run}: no {CURATOR_READ_LOCK}, so no reader is configured') from exc
    except OSError as exc:
        raise SnapshotError(f'{run/CURATOR_READ_LOCK}: cannot open the read lock') from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReadRefused('closing', f'{run}: the custodian holds the read lock to close the store') from exc
        taken = time.monotonic()
        if os.path.lexists(run/STORE_CLOSING_MARKER):
            raise ReadRefused('closing', f'{run}: {STORE_CLOSING_MARKER} exists, so the store is closing')
        yield taken
    finally:
        os.close(descriptor)


def _past(deadline: float) -> bool:
    return time.monotonic() >= deadline


def _bounded(db: sqlite3.Connection, deadline: float) -> list[BaseException]:
    """Cancel any statement on `db` still running when `deadline` passes, or when the handler itself
    raises; the returned list receives what it raised, for the caller to raise once the connection is closed."""
    raised: list[BaseException] = []

    def handler() -> bool:
        try:
            return _past(deadline)
        except BaseException as exc:
            raised.append(exc)
            return True

    db.set_progress_handler(handler, PROGRESS_STEPS)
    return raised


def _query(db: sqlite3.Connection, sql: str) -> tuple[list[str], list[tuple]]:
    """Run one statement to its end on its own cursor, closed (its statement reset) on every path."""
    cursor = db.cursor()
    try:
        cursor.execute(sql)
        return [c[0] for c in cursor.description or ()], cursor.fetchall()
    finally:
        cursor.close()


def _rows(db: sqlite3.Connection) -> dict | None:
    """Everything the snapshot may need, read inside the caller's one transaction; None while the
    store's tables are still being created."""
    present = {name for (name,) in _query(db, "SELECT name FROM sqlite_master WHERE type='table'")[1]}
    if not present >= set(TABLES):
        return None
    version = _query(db, 'PRAGMA user_version')[1][0][0]
    schema = [sql for (sql,) in _query(db, 'SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY rowid')[1]]
    tables = {table: _query(db, f'SELECT * FROM {table} ORDER BY rowid') for table in TABLES}
    return dict(version=version, schema=schema, tables=tables)


def _close(db: sqlite3.Connection) -> None:
    """End any transaction and close the connection; no cursor holds a statement by now."""
    try:
        if db.in_transaction:
            db.set_progress_handler(None, 0)  # the rollback runs after the deadline that cancelled the read
            _query(db, 'ROLLBACK')
    finally:
        db.close()


def _read(path: Path, deadline: float) -> tuple[dict | None, float]:
    """One read transaction on a read-only, non-immutable connection, cancelled at `deadline`."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BoundExceeded(f'{path}: the read bound passed before the connection opened')
    raised: list[BaseException] = []
    try:
        db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=remaining,
                             isolation_level=None)
        try:
            raised = _bounded(db, deadline)
            began = time.monotonic()
            _query(db, 'BEGIN')
            rows = _rows(db)
            _query(db, 'COMMIT')
            held = time.monotonic() - began
        finally:
            _close(db)
    except sqlite3.Error as exc:
        if raised:
            raise raised[0] from None
        if time.monotonic() >= deadline:
            raise BoundExceeded(f'{path}: the read passed its bound and was cancelled') from exc
        raise SnapshotError(f'{path}: unreadable live store: {exc}') from exc
    if raised:
        raise raised[0]
    if time.monotonic() >= deadline:
        raise BoundExceeded(f'{path}: the read passed its bound')
    return rows, held


def _json(data: bytes, where: str):
    try:
        return json.loads(data)
    except ValueError as exc:
        raise SnapshotError(f'{where}: unreadable JSON') from exc


def _file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SnapshotError(f'{path}: missing or not a regular file')
    return path.read_bytes()


def _host(path: Path) -> list[tuple[bytes, dict | None]]:
    """The host log's whole lines, each with its event."""
    data = path.read_bytes() if path.is_file() and not path.is_symlink() else b''
    lines = []
    for number, line in enumerate(data[:data.rfind(b'\n') + 1].splitlines(keepends=True), 1):
        event = _json(line, f'{path}:{number}') if line.strip() else None
        if event is not None and not isinstance(event, dict):
            raise SnapshotError(f'{path}:{number}: expected an event object')
        lines.append((line, event))
    return lines


def _settled(lines: list[tuple[bytes, dict | None]]) -> bool:
    return any(event is not None and event.get('type') == 'settled' for _, event in lines)


def _frozen(run: Path) -> tuple[list[_Actor], list[str], set[str]]:
    """Actors whose frozen manifest and guard inputs are complete, with the files the snapshot copies
    for them and whether their host had settled; also why others are left out, and the identities of
    actors left out with a manifest.

    Read before admission: the driver records an actor in the store before it writes the actor's
    files, and writes every file the manifest names before the manifest itself.
    """
    actors, excluded, known = [], [], set()
    root = run/'actors'
    for directory in sorted(root.iterdir()) if root.is_dir() else []:
        where = f'actors/{directory.name}'
        if directory.is_symlink() or not directory.is_dir():
            continue
        path = directory/'frozen.json'
        if not path.is_file() or path.is_symlink():
            excluded.append(f'{where}: no frozen manifest yet')
            continue
        manifest = path.read_bytes()
        try:
            frozen = json.loads(manifest)
        except ValueError:
            excluded.append(f'{where}: frozen manifest not complete yet')  # a prefix of an object never parses
            continue
        if (not isinstance(frozen, dict) or frozen.get('schema') != FROZEN_SCHEMA
                or not isinstance(frozen.get('actor_id'), str) or not isinstance(frozen.get('files'), dict)):
            raise SnapshotError(f'{path}: unsupported frozen manifest; expected {FROZEN_SCHEMA}')
        files, incomplete = {'frozen.json': manifest}, None
        for name in dict.fromkeys((*FROZEN_INPUTS, *SECRET_FILES)):
            digest = frozen['files'].get(name)
            if digest is None and name in FROZEN_INPUTS:
                raise SnapshotError(f'{path}: the frozen manifest does not bind {name}')
            if digest is None and not (directory/name).exists() and not (directory/name).is_symlink():
                continue
            data = _file(directory/name)
            if digest is None:
                try:
                    json.loads(data)
                except ValueError:
                    incomplete = name  # a guard input not yet whole would hide its values
                    break
            elif hashlib.sha256(data).hexdigest() != digest:
                raise SnapshotError(f'{directory/name}: SHA-256 differs from the frozen manifest')
            files[name] = data
        if incomplete is not None:
            excluded.append(f'{where}: {incomplete} not complete yet')
            known.add(frozen['actor_id'])
            continue
        try:
            settled = _settled(_host(directory/'host.jsonl'))
        except OSError as exc:
            raise SnapshotError(f'{where}: unreadable host log: {exc}') from exc
        actors.append(_Actor(directory.name, frozen['actor_id'], frozen.get('session'), settled, files))
    return actors, excluded, known


def _table(rows: dict, name: str) -> list[dict]:
    columns, values = rows['tables'][name]
    return [dict(zip(columns, row, strict=True)) for row in values]


def _receipt_schema(receipt: str) -> object:
    value = _json(receipt.encode(), 'native receipt')
    return value.get('schema') if isinstance(value, dict) else None


def _scrub_agenda_from_delivery(line: bytes, event: dict | None) -> tuple[bytes, dict | None]:
    """Defense-in-depth (#1026): strip any agenda or affects_agenda fields from delivery telemetry."""
    if event is None or event.get('type') not in ('knowledge-delivery', 'knowledge-undelivered'):
        return line, event
    changed = False
    cleaned = dict(event)
    delta = cleaned.get('delta')
    if isinstance(delta, dict):
        new_delta = dict(delta)
        if 'agenda' in new_delta:
            new_delta.pop('agenda')
            changed = True
        if isinstance(new_delta.get('corrections'), list):
            new_corrs = []
            for row in new_delta['corrections']:
                if isinstance(row, dict) and 'affects_agenda' in row:
                    r = dict(row)
                    r.pop('affects_agenda')
                    new_corrs.append(r)
                    changed = True
                else:
                    new_corrs.append(row)
            new_delta['corrections'] = new_corrs
        if changed:
            cleaned['delta'] = new_delta
    text = cleaned.get('text')
    if isinstance(text, str):
        parts = text.split('\n')
        if len(parts) == 3:
            try:
                body = json.loads(parts[1])
            except ValueError:
                body = None
            if isinstance(body, dict):
                body_changed = False
                if 'agenda' in body:
                    body.pop('agenda')
                    body_changed = True
                if isinstance(body.get('corrections'), list):
                    for row in body['corrections']:
                        if isinstance(row, dict) and 'affects_agenda' in row:
                            row.pop('affects_agenda')
                            body_changed = True
                if body_changed:
                    parts[1] = json.dumps(body, separators=(',', ':'), ensure_ascii=False)
                    cleaned['text'] = '\n'.join(parts)
                    changed = True
    if not changed:
        return line, event
    return (json.dumps(cleaned, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8'), cleaned


def _cut(operations: list[dict], natives: dict[str, list[dict]], collected: set[str],
         lines: list[tuple[bytes, dict | None]], ended: bool) -> tuple[list[dict], list[bytes]]:
    """The included prefix of one actor's operations and its host log, by the module's rule."""
    agenda_calls: set[tuple[object, object]] = set()
    lines = [
        _scrub_agenda_from_delivery(line, event)
        for line, event in lines
        if event is None or not _agenda_event(event, agenda_calls)
    ]
    answered: dict[str, int] = {}
    for index, (_, event) in enumerate(lines):
        if event is not None and event.get('type') == 'tool-result':
            named = _result(event.get('result')).get('operation_id')
            if isinstance(named, str):
                answered.setdefault(named, index)

    def outstanding(operation: dict) -> bool:
        return any(n['receipt'] is None or (_receipt_schema(n['receipt']) == UNKNOWN_TRANSPORT
                                            and n['id'] not in collected) for n in natives.get(operation['id'], ()))

    included = []
    for operation in sorted(operations, key=lambda o: (o['created_wall'], o['id'])):
        if operation['final_json'] is None:
            break
        if not ended and (operation['id'] not in answered or outstanding(operation)):
            break
        included.append(operation)
    if ended and len(included) == len(operations):
        return included, [line for line, _ in lines]
    kept = lines[:max((answered[o['id']] for o in included if o['id'] in answered), default=-1) + 1]
    closed_calls = {e.get('tool_call_id') for _, e in kept if e and e.get('type') in ('tool-result', 'tool-refused')}
    return included, [line for line, e in kept
                      if not (e and e.get('type') == 'tool-start' and e.get('tool_call_id') not in closed_calls)]


def _write_store(path: Path, rows: dict, tables: dict[str, list[dict]]) -> None:
    with closing(sqlite3.connect(path)) as db:
        for sql in rows['schema']:
            db.execute(sql)
        db.execute(f"PRAGMA user_version={int(rows['version'])}")
        for name, values in tables.items():
            columns = rows['tables'][name][0]
            db.executemany(f'INSERT INTO {name}({",".join(columns)}) VALUES({",".join("?" * len(columns))})',
                           [tuple(v[c] for c in columns) for v in values])
        db.commit()
    for suffix in ('-wal', '-journal'):
        side = path.with_name(path.name + suffix)
        if side.exists() and side.stat().st_size > 0:
            raise SnapshotError(f'{side}: the fresh store did not close cleanly')


def _place_frame(source: Path, dest: Path, digest: object) -> None:
    """Link or copy one frame, never over an existing file, and check its recorded digest."""
    if source.is_symlink() or not source.is_file():
        raise SnapshotError(f'{source}: frame named by an included operation is missing')
    try:
        os.link(source, dest)
    except FileExistsError:
        raise
    except OSError:
        with source.open('rb') as reading, dest.open('xb') as writing:
            shutil.copyfileobj(reading, writing)
    if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
        raise SnapshotError(f'{source}: SHA-256 differs from the recorded source metadata')


def _write_new(path: Path, data: bytes) -> None:
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(0o600)


def stage(run: Path, parent: Path, *, transaction_bound: float = TRANSACTION_BOUND_SECONDS,
          hold_bound: float = READ_HOLD_BOUND_SECONDS) -> Snapshot:
    """Stage a snapshot of the live run directory `run` as `parent/<run's name>`.

    The target must not exist when the call starts. It is built in a hidden sibling and renamed
    into place: a target that appears meanwhile is replaced by that rename if it is an empty
    directory, and fails the snapshot otherwise. Raises `ReadRefused` when the store does not admit
    a read, `BoundExceeded` when the read passes either bound, and `SnapshotError` for any other
    failure; in each case nothing is staged.
    """
    started = time.monotonic()
    run, parent = Path(run), Path(parent)
    target = parent/run.name
    if target.exists() or target.is_symlink():
        raise SnapshotError(f'{target}: snapshot target must not exist')
    try:
        frozen, excluded, known = _frozen(run)
        captured = {name: _file(run/name) for name in RUN_FILES if (run/name).exists()}
    except OSError as exc:
        raise SnapshotError(f'{run}: unreadable run directory: {exc}') from exc
    with admitted(run) as taken:
        if not (run/STORE).is_file():
            raise ReadRefused('no-store', f'{run}: no {STORE} yet')
        rows, transaction = _read(run/STORE, taken + transaction_bound)
    hold = time.monotonic() - taken  # the lock is released by now
    if hold >= hold_bound:
        raise BoundExceeded(f'{run}: the read lock was held {hold:.3f} s, past its bound')
    if rows is None:
        raise ReadRefused('no-store', f'{run/STORE}: tables still being created')

    metadata = {r['key']: r['value'] for r in _table(rows, 'metadata')}
    if not {'schema', 'session'} <= metadata.keys():
        raise ReadRefused('no-store', f'{run/STORE}: session identity not yet committed')
    try:
        schema, session_id = json.loads(metadata['schema']), json.loads(metadata['session'])
    except ValueError as exc:
        raise SnapshotError(f'{run/STORE}: unreadable session identity') from exc
    if rows['version'] != STORE_VERSION or schema != STORE_SCHEMA:
        raise SnapshotError(f'{run/STORE}: unsupported store {schema!r} (user_version {rows["version"]}); '
                            f'expected {STORE_SCHEMA}')
    actors = {a['id']: a for a in _table(rows, 'actors')}
    operations = _table(rows, 'operations')
    natives: dict[str, list[dict]] = {}
    for native in _table(rows, 'native_intents'):
        natives.setdefault(native['operation'], []).append(native)
    collections = _table(rows, 'collections')
    collected = {c['native_id'] for c in collections}
    sources = {s['id']: s for s in _table(rows, 'sources')}
    known |= {a.actor_id for a in frozen}
    excluded += [f'actor {identity}: in the store with no frozen manifest yet'
                 for identity in actors if identity not in known]

    coverage, logs = [], {}
    kept = dict(metadata=_table(rows, 'metadata'), actors=[], operations=[], native_intents=[], collections=[],
                sources=[])
    for actor in frozen:
        if actor.actor_id not in actors:
            raise SnapshotError(f'actors/{actor.directory}: frozen actor {actor.actor_id} is not in the store')
        if actor.session != session_id:
            raise SnapshotError(f'actors/{actor.directory}: frozen manifest names another session')
        try:
            lines = _host(run/'actors'/actor.directory/'host.jsonl')  # read after the transaction: the cut only
        except OSError as exc:
            raise SnapshotError(f'actors/{actor.directory}: unreadable host log: {exc}') from exc
        ended = actor.settled or actors[actor.actor_id]['stage'] == 'quiescent'
        own = [o for o in operations if o['actor'] == actor.actor_id]
        included, logs[actor.directory] = _cut(own, natives, collected, lines, ended)
        kept['actors'].append(actors[actor.actor_id])
        kept['operations'] += included
        coverage.append(ActorCoverage(actor.directory, actor.actor_id, len(included),
                                      included[-1]['id'] if included else None, ended, len(own) - len(included)))
    included_natives = [n for o in kept['operations'] for n in natives.get(o['id'], ())]
    native_ids = {n['id'] for n in included_natives}
    kept['native_intents'] = included_natives
    kept['collections'] = [c for c in collections if c['native_id'] in native_ids]
    frames = {r['source'] for r in (*kept['native_intents'], *kept['collections']) if r['source'] is not None}
    if frames - sources.keys():
        raise SnapshotError(f'{run/STORE}: included operations name unindexed frames {sorted(frames - sources.keys())}')
    kept['sources'] = [sources[s] for s in sorted(frames)]

    partial = parent/f'.{run.name}.snapshot-{uuid.uuid4().hex[:8]}'
    try:
        partial.mkdir(mode=0o700)
        _write_store(partial/STORE, rows, kept)
        (partial/'sources').mkdir(mode=0o700)
        (partial/'actors').mkdir(mode=0o700)
        for row in kept['sources']:
            digest = _json(row['metadata'].encode(), f'source {row["id"]}').get('sha256')
            _place_frame(run/'sources'/f'{row["id"]}.png', partial/'sources'/f'{row["id"]}.png', digest)
        for actor in frozen:
            directory = partial/'actors'/actor.directory
            directory.mkdir(mode=0o700)
            for name, data in actor.files.items():
                _write_new(directory/name, data)
            _write_new(directory/'host.jsonl', b''.join(logs[actor.directory]))
        for name, data in captured.items():
            _write_new(partial/name, data)
        partial.rename(target)
    except BaseException as exc:
        shutil.rmtree(partial, ignore_errors=True)
        if isinstance(exc, OSError):
            raise SnapshotError(f'{target}: staging failed: {exc}') from exc
        raise
    return Snapshot(target, session_id, tuple(coverage), tuple(excluded), hold, transaction,
                    time.monotonic() - started)
