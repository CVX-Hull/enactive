"""Bounded read-only diagnostics for one current computer session at a time.

SQLite's read-only connection reads a snapshot; no SessionStore, target, migration
or custody is instantiated. Original receipts and later collections stay separate.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
from typing import Iterator

from harness.computer.protocol import ControlError, closed, decode_json, receipt, source
from tools.host_analysis import delta, distribution, number

MAX_DATABASE_BYTES = 512 * 1024 * 1024
MAX_ROWS = 200_000


def database_path(path: Path) -> Path:
    selected = path / 'session.sqlite3' if path.is_dir() else path
    if selected.is_symlink() or not selected.is_file():
        raise ControlError('Select an existing regular session database')
    selected = selected.resolve()
    total = selected.stat().st_size
    for suffix in ('-wal', '-shm'):
        sidecar = Path(str(selected) + suffix)
        if sidecar.is_symlink():
            raise ControlError('Symlink SQLite sidecar')
        if sidecar.exists():
            total += sidecar.stat().st_size
    if total > MAX_DATABASE_BYTES:
        raise ControlError('Session database exceeds 512 MiB including SQLite sidecars')
    return selected


@contextmanager
def session_database(path: Path) -> Iterator[tuple[sqlite3.Connection, Path, str]]:
    selected = database_path(path)
    connection = None
    try:
        connection = sqlite3.connect(selected.as_uri() + '?mode=ro', uri=True, timeout=.25)
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        if connection.execute('PRAGMA user_version').fetchone()[0] != 2:
            raise ControlError('Unsupported computer session database version')
        metadata = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN ('schema','session')"))
        if decode_json(metadata.get('schema', 'null')) != 'computer-session/2':
            raise ControlError('Unsupported computer session schema')
        session = decode_json(metadata.get('session', 'null'))
        if not isinstance(session, str) or re.fullmatch('[0-9a-f]{32}', session) is None:
            raise ControlError('Invalid computer session identity')
        yield connection, selected, session
    except ControlError:
        raise
    except (sqlite3.Error, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ControlError('Cannot read current computer session database') from exc
    finally:
        if connection is not None:
            connection.close()


def bounded_rows(connection: sqlite3.Connection, query: str) -> Iterator[tuple]:
    for index, row in enumerate(connection.execute(query)):
        if index >= MAX_ROWS:
            raise ControlError('Selected session table exceeds 200000 rows')
        yield row


def sources_in(connection: sqlite3.Connection, session: str) -> list[dict]:
    records = []
    for identity, encoded in bounded_rows(connection, 'SELECT id,metadata FROM sources ORDER BY rowid'):
        value = source(decode_json(encoded))
        if value['source_id'] != identity or value['session'] != session:
            raise ControlError('Source row/session identity differs')
        records.append(value)
    return records


def read_sources(path: Path) -> list[dict]:
    with session_database(path) as (connection, _, session):
        return sources_in(connection, session)


def native_disposition(encoded: str | None, identity: str, session: str) -> str:
    if encoded is None:
        return 'unrecorded'
    value = decode_json(encoded)
    if not isinstance(value, dict):
        raise ControlError('Expected native receipt metadata')
    if value.get('schema') == 'computer-receipt/2':
        return receipt(value, identity=identity, session=session)['disposition']
    closed(value, {'schema', 'id', 'session', 'disposition', 'emitted_events', 'reason', 'frame'})
    if value.get('schema') == 'computer-transport/2':
        if (value.get('id') != identity or value.get('session') != session
                or value.get('disposition') != 'unknown' or value.get('emitted_events') is not None
                or value.get('frame') is not None):
            raise ControlError('Invalid original transport uncertainty')
        return 'transport_unknown'
    # A local refusal is current evidence, not a native delivery ACK.
    if (value.get('schema') != 'computer-local/1' or value.get('id') != identity
            or value.get('session') != session or value.get('disposition') != 'rejected'
            or value.get('emitted_events') != 0 or value.get('frame') is not None):
        raise ControlError('Unsupported local/native receipt')
    return 'local_' + value['disposition']


def analyze_session(path: Path) -> dict:
    with session_database(path) as (connection, selected, session):
        sources = {value['source_id']: value for value in sources_in(connection, session)}
        operations, statuses = {}, Counter()
        for identity, actor, kind, created, final in bounded_rows(connection,
                'SELECT id,actor,kind,created_wall,final_json FROM operations ORDER BY rowid'):
            if kind not in ('input', 'observe', 'handoff') or not number(created):
                raise ControlError('Invalid operation metadata')
            status = 'pending'
            if final is not None:
                value = decode_json(final, 262144)
                if (not isinstance(value, dict) or value.get('schema') != 'computer-operation/1'
                        or value.get('session') != session or value.get('operation_id') != identity
                        or value.get('actor_id') != actor or value.get('kind') != kind
                        or value.get('status') not in ('pending', 'completed', 'sealed', 'partial', 'unknown', 'refused')):
                    raise ControlError('Unsupported terminal operation')
                status = value['status']
            statuses[status] += 1
            operations[identity] = {'operation_id': identity, 'actor_id': actor, 'kind': kind,
                'created_wall': created, 'status': status}
        collections = {}
        for identity, encoded, source_id in bounded_rows(connection, 'SELECT native_id,receipt,source FROM collections'):
            if source_id is not None and source_id not in sources:
                raise ControlError('Collection source is not retained in this session')
            collections[identity] = (native_disposition(encoded, identity, session), source_id)
        rows, original, additional = [], Counter(), Counter()
        metrics = {name: [] for name in ('intent_to_send', 'send', 'send_to_receipt', 'intent_to_receipt')}
        for identity, operation, encoded, source_id, timing in bounded_rows(connection,
                'SELECT id,operation,receipt,source,timing FROM native_intents ORDER BY rowid'):
            if operation not in operations or source_id is not None and source_id not in sources:
                raise ControlError('Native intent lacks its original operation/source')
            stamps = decode_json(timing)
            if not isinstance(stamps, dict):
                raise ControlError('Expected native timing metadata')
            disposition = native_disposition(encoded, identity, session)
            original[disposition] += 1
            collection, later_source = collections.pop(identity, (None, None))
            if collection is not None:
                additional[collection] += 1
            row = dict(native_id=identity, operation_id=operation, disposition=disposition,
                source_id=source_id, additional_collection_disposition=collection, additional_source_id=later_source)
            for name, end, start in (
                    ('intent_to_send', 'send_started_monotonic', 'intent_monotonic'),
                    ('send', 'send_finished_monotonic', 'send_started_monotonic'),
                    ('send_to_receipt', 'receipt_received_monotonic', 'send_started_monotonic'),
                    ('intent_to_receipt', 'receipt_received_monotonic', 'intent_monotonic')):
                seconds = delta(stamps.get(end), stamps.get(start))
                value = seconds * 1000 if seconds is not None else None
                row[name + '_ms'] = value
                metrics[name].append(value)
            row['original_timing'] = {key: value if number(value) else None for key, value in stamps.items()
                if key in {prefix + '_' + clock for prefix in
                    ('intent', 'send_started', 'send_finished', 'receipt_received') for clock in ('wall', 'monotonic')}}
            rows.append(row)
        if collections:
            raise ControlError('Collection lacks its original native intent')
        return {'database': str(selected), 'session': session, 'operation_statuses': dict(statuses),
            'original_native_dispositions': dict(original), 'additional_collection_dispositions': dict(additional),
            'operations': list(operations.values()), 'native_rows': rows, 'source_count': len(sources),
            'timing_ms': {name: distribution(values) for name, values in metrics.items()}}


def control_summary(paths: list[Path]) -> dict:
    if not 1 <= len(paths) <= 32:
        raise ControlError('Select 1..32 explicit session databases or directories')
    selected = [database_path(path) for path in paths]
    if len(set(selected)) != len(selected):
        raise ControlError('Duplicate session database')
    return {'schema': 'control-analysis/1',
        'scope': 'Original mechanical operation/native timing and separate later collections; no game effect, Save, goal quality or useful apparent latency verdict',
        'units': 'milliseconds for intervals; original wall/monotonic timestamps are seconds',
        'sessions': [analyze_session(path) for path in selected]}
