"""Read-only, bounded projection of configured curator result journals."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

from harness.evaluation.core.sources import MAX_JSON_FILE_BYTES
from .catalog import ViewError
from .knowledge import ID_LIMIT, LIST_LIMIT, TEXT_LIMIT

LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
VERSION = re.compile(r'v(0|[1-9][0-9]*)')
DRAFT = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
KEYS = {'schema', 'operation', 'operation_id', 'status', 'base_version', 'restored_from',
        'version', 'submission', 'session', 'from_drafts', 'diagnostics'}


def parse_sources(values: list[str]) -> tuple[tuple[str, Path], ...]:
    sources = []
    seen = set()
    for value in values:
        label, separator, path = value.partition('=')
        if not separator or not LABEL.fullmatch(label) or not path or label in seen:
            raise ValueError('curator results must be unique LABEL=FILE entries')
        seen.add(label)
        sources.append((label, Path(path)))
    return tuple(sources)


def valid(row):
    if not isinstance(row, dict) or set(row) != KEYS or row['schema'] != 'curator-gate/2':
        return False
    op, status = row['operation'], row['status']
    text = lambda v: isinstance(v, str) and bool(v.strip())
    if (op not in ('submission', 'restore') or status not in ('published', 'rejected', 'unchanged', 'unknown')
            or not isinstance(row['operation_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', row['operation_id'])
            or not isinstance(row['diagnostics'], list) or not all(isinstance(d, str) for d in row['diagnostics'])
            or not isinstance(row['from_drafts'], list)
            or not all(isinstance(d, str) and DRAFT.fullmatch(d) for d in row['from_drafts'])
            or any(v is not None and (not isinstance(v, str) or not VERSION.fullmatch(v))
                   for v in (row['base_version'], row['restored_from'], row['version']))):
        return False
    return not ((op == 'restore' and (row['submission'] is not None or row['session'] is not None
                    or row['from_drafts'] or row['base_version'] is None or row['restored_from'] is None))
        or (op == 'submission' and (not text(row['submission']) or not text(row['session']) or row['restored_from'] is not None))
        or (status == 'rejected' and row['version'] is not None)
        or (status in ('published', 'unchanged') and row['version'] is None)
        or (status == 'published' and row['base_version'] is None)
        or (status == 'unchanged' and op != 'restore'))


def project(row, index):
    item = {'index': index}
    omitted = {}
    for key in ('operation_id', 'operation', 'status', 'base_version', 'restored_from', 'version', 'submission', 'session'):
        value = row[key]
        if isinstance(value, str) and len(value) > ID_LIMIT:
            omitted[key] = len(value)
            value = None
        item[key] = value
    item['diagnostics'] = [s[:TEXT_LIMIT] for s in row['diagnostics'][:LIST_LIMIT]]
    item['diagnostics_omitted'] = max(0, len(row['diagnostics']) - LIST_LIMIT)
    for i, value in enumerate(row['diagnostics'][:LIST_LIMIT]):
        if len(value) > TEXT_LIMIT:
            omitted[f'diagnostics.{i}'] = len(value) - TEXT_LIMIT
    if omitted:
        item['omitted_characters'] = omitted
    return item


def read(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return 'unreadable', None, []
            data = stream.read(MAX_JSON_FILE_BYTES + 1)
    except FileNotFoundError:
        return 'missing', None, []
    except OSError:
        return 'unreadable', None, []
    snapshot = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    if len(data) > MAX_JSON_FILE_BYTES:
        return 'too_large', snapshot, []
    if not data:
        return 'empty', snapshot, []
    if not data.endswith(b'\n'):
        return 'malformed', snapshot, []
    try:
        rows = [json.loads(line) for line in data.decode('utf-8').splitlines()]
    except (ValueError, UnicodeError, RecursionError):
        return 'malformed', snapshot, []
    if not all(valid(row) for row in rows):
        return 'unsupported', snapshot, []
    return 'available', snapshot, [project(row, i) for i, row in enumerate(rows)]


def results(sources, label, after, limit, digest):
    path = next ( (path for name, path in sources if name == label), None )
    if path is None:
        raise ViewError(404, 'unknown_source')
    if (digest is not None and not re.fullmatch(r'[0-9a-f]{64}', digest)) or (after > 0 and digest is None):
        raise ViewError(400, 'bad_snapshot')
    status, snapshot, rows = read(path)
    if digest is not None and (snapshot is None or digest != snapshot['sha256']):
        raise ViewError(409, 'source_changed')
    return dict(source=label, source_status=status, snapshot=snapshot, items=rows[after:after + limit],
                total=len(rows), next=after + limit if after + limit < len(rows) else None, limit=limit)
