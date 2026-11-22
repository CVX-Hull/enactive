"""Read-only, bounded projection of configured curator result journals, and the viewer's bounded file reads."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import stat

from harness.evaluation.core.sources import MAX_JSON_FILE_BYTES
from harness.trace.sidecar import ManifestError, validate
from .catalog import ID_LIMIT, LIST_LIMIT, TEXT_LIMIT, ViewError

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
    path_details = 0
    for key in ('operation_id', 'operation', 'status', 'base_version', 'restored_from', 'version', 'submission', 'session'):
        value = row[key]
        if isinstance(value, str) and ('/' in value or '\\' in value):
            omitted[key] = len(value)
            path_details += 1
            value = None
        elif isinstance(value, str) and len(value) > ID_LIMIT:
            omitted[key] = len(value)
            value = None
        item[key] = value
    item['diagnostics'] = []
    item['diagnostics_omitted'] = max(0, len(row['diagnostics']) - LIST_LIMIT)
    for i, value in enumerate(row['diagnostics'][:LIST_LIMIT]):
        if '/' in value or '\\' in value:
            path_details += 1
            continue
        item['diagnostics'].append(value[:TEXT_LIMIT])
        if len(value) > TEXT_LIMIT:
            omitted[f'diagnostics.{i}'] = len(value) - TEXT_LIMIT
    if path_details:
        item['path_details_omitted'] = path_details
    if omitted:
        item['omitted_characters'] = omitted
    return item


DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW


def contents(fd):
    """(status, snapshot, bytes) of one opened regular file, at most the 16 MiB input limit. Closes `fd`."""
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return 'unreadable', None, None
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(MAX_JSON_FILE_BYTES + 1)
    finally:
        os.close(fd)
    snapshot = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    if len(data) > MAX_JSON_FILE_BYTES:
        return 'too_large', snapshot, None
    if not data:
        return 'empty', snapshot, None
    return 'available', snapshot, data


def attempt(read):
    try:
        return read()
    except FileNotFoundError:
        return 'missing', None, None
    except OSError:
        return 'unreadable', None, None


def read_file(path):
    """One file the operator named: its directories are the operator's choice, and the file is no symlink."""
    return attempt(lambda: contents(os.open(path, FILE)))


@contextmanager
def opened_directory(root, *parts):
    """A descriptor of `root`/`parts`, opened one component at a time: a symlink at any of them, `root` included, is an
    OSError. Nothing under a run directory can therefore lead a reader out of it."""
    fd = os.open(root, DIRECTORY)
    try:
        for name in parts:
            inner = os.open(component(name), DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = inner
        yield fd
    finally:
        os.close(fd)


def component(name):
    if not name or name in ('.', '..') or '/' in name:
        raise ValueError(f'not one path component: {name!r}')
    return name


def read_rooted(root, *parts):
    """`read_file` for a file of a run package, with no symlink on the way from `root`."""
    def read():
        with opened_directory(root, *parts[:-1]) as directory:
            fd = os.open(component(parts[-1]), FILE, dir_fd=directory)
        return contents(fd)
    return attempt(read)


def rooted_status(root, *parts):
    """The `lstat` of a file of a run package, or None: missing, or behind a symlink."""
    try:
        with opened_directory(root, *parts[:-1]) as directory:
            return os.stat(component(parts[-1]), dir_fd=directory, follow_symlinks=False)
    except OSError:
        return None


def rooted_entries(root, *parts):
    """(name, `lstat`) of each entry of a run package's directory, by name. A missing directory or one behind a symlink
    is an OSError."""
    with opened_directory(root, *parts) as directory:
        return [(name, os.stat(name, dir_fd=directory, follow_symlinks=False)) for name in sorted(os.listdir(directory))]


def read(path):
    status, snapshot, data = read_file(path)
    if status != 'available':
        return status, snapshot, []
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
    path = next((path for name, path in sources if name == label), None)
    if path is None:
        raise ViewError(404, 'unknown_source')
    if (digest is not None and not re.fullmatch(r'[0-9a-f]{64}', digest)) or (after > 0 and digest is None):
        raise ViewError(400, 'bad_snapshot')
    status, snapshot, rows = read(path)
    if digest is not None and (snapshot is None or digest != snapshot['sha256']):
        raise ViewError(409, 'source_changed')
    return dict(source=label, source_status=status, snapshot=snapshot, items=rows[after:after + limit],
                total=len(rows), next=after + limit if after + limit < len(rows) else None, limit=limit)


def _safe(value: str | None) -> str | None:
    """Omit path-like or oversized strings; never expose private path fragments."""
    if value is None:
        return None
    return value if len(value) <= ID_LIMIT and '/' not in value and '\\' not in value else None


def _text_list(values: list[str]) -> dict:
    items = [_safe(v) for v in values[:LIST_LIMIT]]
    return dict(items=items, omitted=max(0, len(values) - LIST_LIMIT), values_omitted=sum(v is None for v in items))


def _number(value: object) -> bool:
    return ((type(value) is int and 0 <= value <= 2**53 - 1) or
            (type(value) is float and math.isfinite(value) and value >= 0))


def _cap(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 128:
        return False
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return False
    return amount.is_finite() and amount >= 0


def _optional(obj: dict, key: str, predicate) -> bool:
    return key not in obj or obj[key] is None or predicate(obj[key])


def session_projection(record: object) -> tuple[dict, dict | None, list]:
    if not isinstance(record, dict) or set(record) != {'manifest', 'verdicts', 'drafts', 'published_after'}:
        raise ValueError('receipt shape')
    m = record['manifest']
    try:
        validate(m)
    except (ManifestError, TypeError, KeyError):
        raise ValueError('manifest') from None
    if m['kind'] != 'curator-session' or m['owner_role'] != 'curator' or m['lifecycle']['state'] not in ('sealed', 'aborted'):
        raise ValueError('manifest kind')
    inputs, pinned, budgets, life, provenance = (m[k] for k in ('inputs', 'pinned', 'budgets', 'lifecycle', 'provenance'))
    if not {'state', 'ended_wall', 'stopped', 'returncode', 'survivors', 'errors', 'refused'} <= life.keys():
        raise ValueError('incomplete close-out')
    if 'started_wall' in life:
        if (not {'session_kind', 'trace_sessions', 'window_frames', 'window', 'coverage', 'drafts'} <= inputs.keys()
                or not {'knowledge_version', 'trace_manifest_sha256', 'brief_sha256'} <= pinned.keys()
                or not {'wall_seconds', 'memory_bytes', 'disk_bytes', 'cap_usd'} <= budgets.keys()
                or (inputs['session_kind'] == 'grooming' and 'grooming_sha256' not in pinned)):
            raise ValueError('incomplete prepared session')
    elif life['state'] != 'aborted' or any((inputs, pinned, budgets, provenance)):
        raise ValueError('incomplete preparation abort')
    resource_keys = {'seconds', 'peak_memory_bytes', 'peak_disk_bytes'}
    if (life['state'] == 'sealed' or resource_keys & provenance.keys()) and not resource_keys <= provenance.keys():
        raise ValueError('incomplete resource report')
    string = lambda v: isinstance(v, str)
    integer = lambda v: type(v) is int and v >= 0
    strings = lambda v: isinstance(v, list) and all(string(x) for x in v)
    checks = [(inputs, 'session_kind', lambda v: v in ('admission', 'grooming')),
              (inputs, 'trace_sessions', strings), (inputs, 'drafts', strings), (inputs, 'window_frames', integer),
              (pinned, 'knowledge_version', lambda v: string(v) and VERSION.fullmatch(v)),
              *[(pinned, k, lambda v: string(v) and re.fullmatch(r'[0-9a-f]{64}', v)) for k in ('trace_manifest_sha256', 'brief_sha256', 'grooming_sha256')],
              *[(budgets, k, _number) for k in ('wall_seconds', 'memory_bytes', 'disk_bytes')],
              (budgets, 'cap_usd', _cap),
              *[(life, k, _number) for k in ('started_wall', 'ended_wall')],
              (life, 'stopped', string), (life, 'returncode', lambda v: type(v) is int),
              (life, 'survivors', lambda v: isinstance(v, list) and all(type(x) is int for x in v)), (life, 'errors', strings), (life, 'refused', strings),
              *[(provenance, k, _number) for k in ('seconds', 'peak_memory_bytes', 'peak_disk_bytes')]]
    nullable = {(id(budgets), 'cap_usd'), (id(life), 'stopped'), (id(life), 'returncode'),
                (id(life), 'survivors')}
    if not all((key not in obj or (obj[key] is None and (id(obj), key) in nullable)
                or (obj[key] is not None and predicate(obj[key]))) for obj, key, predicate in checks):
        raise ValueError('metadata')
    window = inputs.get('window')
    if 'window' in inputs and (not isinstance(window, dict) or set(window) not in (set(), {'session', 'actor', 'first', 'last'}) or
        (window and (not all(string(window[k]) for k in ('session', 'actor'))
                     or not all(integer(window[k]) for k in ('first', 'last'))
                     or window['first'] < 1 or window['last'] < window['first']))):
        raise ValueError('window')
    coverage = inputs.get('coverage')
    if 'coverage' in inputs and (not isinstance(coverage, dict) or set(coverage) != {'schema', 'session', 'actor', 'last_step'} or coverage['schema'] != 'curator-coverage/2' or not string(coverage['session']) or not _optional(coverage, 'actor', string) or not _optional(coverage, 'last_step', integer)):
        raise ValueError('coverage')
    verdicts = record['verdicts']
    drafts = record['drafts']
    if not isinstance(verdicts, list) or not all(valid(v) for v in verdicts):
        raise ValueError('verdicts')
    keys = ('created', 'renewed', 'aged', 'stale', 'abandoned', 'refused')
    if not isinstance(drafts, dict) or (drafts and (set(drafts) != set(keys) or not all(strings(drafts[k]) for k in keys[:-1]) or not isinstance(drafts['refused'], list) or not all(isinstance(v, dict) and set(v) == {'id', 'reason'} and all(string(v[k]) for k in ('id', 'reason')) for v in drafts['refused']))):
        raise ValueError('drafts')
    published = record['published_after']
    if published is not None and (not string(published) or not VERSION.fullmatch(published)):
        raise ValueError('published')
    def fields(obj, names):
        out = {}
        omitted = {}
        for k in names:
            if k not in obj:
                continue
            value = obj[k]
            out[k] = _safe(value) if isinstance(value, str) else value
            if isinstance(value, str) and out[k] is None:
                omitted[k] = len(value)
        if omitted:
            out['omitted_characters'] = omitted
        return out
    header = dict(**fields(dict(id=m['id'], published_after=published), ('id', 'published_after')),
                  inputs=fields(inputs, ('session_kind', 'window_frames')),
                  pinned=fields(pinned, ('knowledge_version', 'trace_manifest_sha256', 'brief_sha256', 'grooming_sha256')),
                  budgets=fields(budgets, ('wall_seconds', 'memory_bytes', 'disk_bytes', 'cap_usd')),
                  lifecycle=fields(life, ('state', 'started_wall', 'ended_wall', 'stopped', 'returncode')),
                  resources=fields(provenance, ('seconds', 'peak_memory_bytes', 'peak_disk_bytes')))
    for k in ('trace_sessions', 'drafts'):
        if k in inputs and inputs[k] is not None: header['inputs'][k] = _text_list(inputs[k])
    for k in ('errors', 'refused'):
        if k in life and life[k] is not None: header['lifecycle'][k] = _text_list(life[k])
    if 'survivors' in life: header['lifecycle']['survivor_count'] = len(life['survivors']) if life['survivors'] is not None else None
    if window is not None: header['inputs']['window'] = fields(window, ('session', 'actor', 'first', 'last'))
    if coverage is not None: header['inputs']['coverage'] = dict(schema='curator-coverage/2', **fields(coverage, ('session', 'actor', 'last_step')))
    report = None if not drafts else {k: _text_list(drafts[k]) for k in keys[:-1]}
    if report is not None:
        report['refused'] = dict(items=[fields(v, ('id', 'reason')) for v in drafts['refused'][:LIST_LIMIT]], omitted=max(0, len(drafts['refused']) - LIST_LIMIT))
    return header, report, verdicts


def session(sources: tuple[tuple[str, Path], ...], label: str | None, after: int, limit: int,
            digest: str | None) -> dict:
    path = next((path for name, path in sources if name == label), None)
    if path is None: raise ViewError(404, 'unknown_source')
    if (digest is not None and not re.fullmatch(r'[0-9a-f]{64}', digest)) or (after > 0 and digest is None):
        raise ViewError(400, 'bad_snapshot')
    status, snapshot, data = read_file(path)
    if digest is not None and (snapshot is None or digest != snapshot['sha256']): raise ViewError(409, 'source_changed')
    header, report, verdicts = None, None, []
    if status == 'available':
        try:
            record = json.loads(data.decode('utf-8'))
        except (ValueError, UnicodeError, RecursionError):
            status = 'malformed'
        else:
            try: header, report, verdicts = session_projection(record)
            except (ValueError, TypeError, KeyError, RecursionError): status = 'unsupported'
    return dict(source=label, source_status=status, snapshot=snapshot, header=header, drafts=report,
                items=[project(v, i) for i, v in enumerate(verdicts[after:after + limit], after)],
                total=len(verdicts), next=after + limit if after + limit < len(verdicts) else None, limit=limit)
