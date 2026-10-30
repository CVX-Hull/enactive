"""Bounded passive views of original session records and public host events.

This is a disposable projection, not another journal or a source of custody.
Computer rows come from a read-only SQLite snapshot; host rows are projected as
the existing driver consumes its original trace. Neither path calls the player.
"""
from __future__ import annotations

from collections import deque
import copy
from datetime import datetime
import json
import math
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from .computer.protocol import canonical, source

ENTRY_LIMIT = 200
BYTE_LIMIT = 256 * 1024
TEXT_LIMIT = 8192
HOST_KINDS = frozenset({'host-start', 'request-start', 'response-complete',
    'assistant-text', 'tool-start', 'tool-result', 'handoff', 'settled', 'abort', 'provider-retry'})


def bounded_text(value: Any, limit: int) -> tuple[str | None, int]:
    if not isinstance(value, str):
        return None, 0
    raw = value.encode('utf-8')
    text = raw[:limit].decode('utf-8', errors='ignore')
    return text, len(raw) - len(text.encode('utf-8'))


def finite(value: Any) -> float | None:
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def tool_value(event: dict) -> dict:
    """Read only an actual MCP text result, never synthesize links from timing."""
    result = event.get('result')
    if not isinstance(result, dict):
        return {}
    for part in result.get('content', [])[:8]:
        if not isinstance(part, dict) or part.get('type') != 'text':
            continue
        text = part.get('text')
        if not isinstance(text, str) or len(text.encode('utf-8')) > 262144:
            continue
        try:
            value = json.loads(text)
        except (ValueError, RecursionError):
            continue
        if isinstance(value, dict):
            return value
    return {}


class ActivityView:
    """At most one host tail plus the current session's original operation tail."""

    def __init__(self, session: str, database: Path) -> None:
        self.session, self.database = session, database
        self.lock = threading.Lock()
        self.rows: deque[dict] = deque(maxlen=ENTRY_LIMIT)
        self.host_count = 0
        self.host_coverage = 'not-started'
        self.host_errors = 0
        self.latest_statement: dict | None = None
        self.revision = 0

    def host_event(self, actor_id: str, ordinal: int, event: dict) -> None:
        """Only this projection can fail; original trace/accounting are unchanged."""
        try:
            self._host_event(actor_id, ordinal, event)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
            with self.lock:
                self.host_coverage = 'unavailable:' + type(exc).__name__
                self.host_errors += 1

    def _host_event(self, actor_id: str, ordinal: int, event: dict) -> None:
        kind = event.get('type')
        if kind not in HOST_KINDS:
            return
        row = dict(id=f'host:{actor_id}:{ordinal}', session=self.session, producer='host',
                   actor_id=actor_id, kind=kind, created_wall=None)
        stamp = event.get('wall_time')
        if isinstance(stamp, str):
            try:
                row['created_wall'] = finite(datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp())
            except ValueError:
                pass
        row['monotonic_ms'] = finite(event.get('monotonic_ms'))
        for key in ('request_id', 'tool_call_id', 'tool', 'program_id'):
            text, omitted = bounded_text(event.get(key), 256)
            if text is not None and not omitted:
                row[key] = text
            elif omitted:
                row.setdefault('omitted_fields', []).append(key)
        row['status'], status_omitted = bounded_text(event.get('stop_reason') or event.get('stage'), 128)
        if kind == 'settled':
            row['status'] = 'completed' if event.get('ok') is True else 'failed'
        row['reason'], reason_omitted = bounded_text(event.get('reason'), 512)
        row['omitted_text_bytes'] = status_omitted + reason_omitted
        if kind == 'assistant-text':
            row['text'], row['display_omitted_bytes'] = bounded_text(event.get('text'), TEXT_LIMIT)
            row['omitted_bytes'] = event.get('omitted_bytes', 0)
            if type(row['omitted_bytes']) is not int or row['omitted_bytes'] < 0:
                raise ValueError('Invalid original narration omission count')
        if kind == 'tool-result':
            value = tool_value(event)
            for key in ('operation_id', 'program_id', 'run_id', 'status'):
                text, omitted = bounded_text(value.get(key), 128)
                if text is not None and not omitted:
                    row[key] = text
                elif omitted:
                    row.setdefault('omitted_fields', []).append(key)
            row['reason'], reason_omitted = bounded_text(value.get('reason'), 512)
            row['omitted_text_bytes'] += reason_omitted
            if isinstance(value.get('source'), dict):
                metadata = source(value['source'])
                if metadata['session'] == self.session:
                    row['source'] = metadata
        with self.lock:
            self.rows.append(row)
            self.host_count += 1
            if not self.host_errors:
                self.host_coverage = 'available'
            if kind == 'assistant-text':
                self.latest_statement = row

    def _computer_rows(self) -> tuple[list[dict], int]:
        # Separate read-only connection: no writer/store lock or application
        # executor is acquired. SQLite's deadline bounds busy/large JSON reads.
        connection = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=.1)
        try:
            connection.execute('PRAGMA query_only=ON')
            deadline = time.monotonic() + .2
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            connection.execute('BEGIN')
            total = connection.execute('SELECT COUNT(*) FROM operations').fetchone()[0]
            values = connection.execute('''SELECT id,actor,kind,created_wall,
                json_extract(final_json,'$.status'),json_extract(final_json,'$.reason'),
                json_extract(final_json,'$.source') FROM operations ORDER BY rowid DESC LIMIT ?''',
                (ENTRY_LIMIT,)).fetchall()
            rows = []
            for identity, actor, kind, wall, status, reason, metadata in values:
                row = dict(id='computer:' + identity, session=self.session, producer='computer',
                    actor_id=actor, kind=kind, operation_id=identity, created_wall=wall,
                    status=status or 'pending', reason=bounded_text(reason, 512)[0])
                row['omitted_text_bytes'] = bounded_text(reason, 512)[1]
                if metadata:
                    observed = source(json.loads(metadata))
                    if observed['session'] != self.session:
                        raise ValueError('Activity source belongs to a different session')
                    row['source'] = observed
                # Keep original receipts and later collections separate. They
                # are evidence, not permission to retry an unknown operation.
                for key, query in (
                    ('original_dispositions', 'SELECT json_extract(receipt,\'$.disposition\') '
                        'FROM native_intents WHERE operation=? ORDER BY rowid LIMIT 65'),
                    ('additional_collection_dispositions', 'SELECT json_extract(c.receipt,\'$.disposition\') '
                        'FROM collections c JOIN native_intents n ON n.id=c.native_id '
                        'WHERE n.operation=? ORDER BY c.rowid LIMIT 65')):
                    receipts = [r[0] for r in connection.execute(query, (identity,))]
                    row[key] = receipts[:64]
                    if len(receipts) > 64:
                        row[key + '_omitted'] = True
                rows.append(row)
            return list(reversed(rows)), total
        finally:
            connection.close()

    def snapshot(self) -> dict:
        with self.lock:
            rows = copy.deepcopy(list(self.rows))
            statement = copy.deepcopy(self.latest_statement)
            count, host_coverage, host_errors = self.host_count, self.host_coverage, self.host_errors
        computer_count, computer_coverage = None, 'available'
        computer = []
        try:
            computer, computer_count = self._computer_rows()
        except (sqlite3.Error, OSError, ValueError, TypeError, RecursionError) as exc:
            computer_coverage = 'unavailable:' + type(exc).__name__
        # Compare only the heads of the two original producer sequences. A wall
        # clock can move backward; sorting every row would reverse request/result
        # order and evict genuinely later producer events from the retained tail.
        producers = [deque(rows), deque(computer)]
        rows = []
        while any(producers):
            available = [part for part in producers if part]
            selected = min(available, key=lambda part: part[0].get('created_wall') or 0)
            rows.append(selected.popleft())
        rows = rows[-ENTRY_LIMIT:]
        with self.lock:
            self.revision += 1
            revision = self.revision
        result = dict(schema='observer-activity/1', session=self.session, revision=revision,
            entries=rows, latest_statement=statement, omitted_entries=0,
            coverage=dict(host=host_coverage, computer=computer_coverage,
                host_events=count, host_projection_errors=host_errors, computer_operations=computer_count,
                clock='Original host monotonic clocks are actor-local; cross-process wall order is approximate.'))
        while True:
            result['omitted_entries'] = (max(0, count + computer_count - len(rows))
                if computer_count is not None and not host_errors else None)
            result['omitted_fields'] = sum(len(row.get('omitted_fields', [])) for row in rows)
            result['omitted_text_bytes'] = sum(row.get('omitted_text_bytes', 0)
                + row.get('display_omitted_bytes', 0) for row in rows)
            if len((canonical(result) + '\n').encode('utf-8')) <= BYTE_LIMIT:
                return result
            # Complete entries only. The separately bounded latest statement
            # remains accessible even when it precedes the retained tail.
            rows.pop(0)
