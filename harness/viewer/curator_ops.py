"""Run-scoped, read-only views of curator sessions, accounting and lineage records."""
from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass
from decimal import Decimal
import json
import math
from pathlib import Path
import stat
import threading

from . import curator, curator_runner, telemetry
from .catalog import ID_LIMIT, LIST_LIMIT, RunInfo, ViewError
from .curator import read_rooted, rooted_entries, rooted_status
from .frame import FrameSources
from .telemetry import count, usd, usd_sum, usd_text

SESSIONS = ('curator-runner', 'sessions')
MAX_SESSIONS = 500
CACHED_RUNS = 8
SESSION_FILES = ('summary.json', 'proxy-start.json', 'proxy-close.json', 'proxy-ledger.jsonl')
TIERS = ('default', 'priority', 'flex')


def _safe(value):
    return curator._safe(value) if isinstance(value, str) and value else None


def _object(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _scalar(value):
    if isinstance(value, str):
        return _safe(value)
    if type(value) is bool:
        return value
    if type(value) in (int, float) and 0 <= value <= 2**53 - 1 and math.isfinite(value):
        return value
    return None


def _fields(value, names):
    value = _object(value)
    return {key: _scalar(value.get(key)) for key in names}


def _strings(value, limit=LIST_LIMIT):
    return [item for raw in _list(value)[:limit] if (item := _safe(raw)) is not None]


def _money(value):
    amount = usd(value)
    return usd_text(amount) if amount is not None else None


def _stamp(root, *parts):
    status = rooted_status(root, *parts)
    return None if status is None else (status.st_mode, status.st_ino, status.st_mtime_ns, status.st_ctime_ns, status.st_size)


def _entries(root, *parts):
    try:
        return rooted_entries(root, *parts), False
    except FileNotFoundError:
        return [], False
    except OSError:
        return [], True


def _json(root, *parts):
    state, _, data = read_rooted(root, *parts)
    if state == 'available':
        try:
            return _object(json.loads(data))
        except (ValueError, RecursionError):
            pass
    return {}


@dataclass(frozen=True)
class Ledger:
    items: list[dict]
    total: int
    amount: Decimal | None
    unpriced: int
    tiers: Counter


def _ledger(run_dir, parts, *, detail=False):
    state, _, data = read_rooted(run_dir, *parts, 'proxy-ledger.jsonl')
    if state != 'available':
        return Ledger([], 0, Decimal(0) if state == 'empty' else None, 0, Counter())
    amounts, unpriced, total, items, tiers = [], 0, 0, [], Counter()
    for line in data.split(b'\n')[:-1]:
        if not line.strip():
            continue
        try:
            row = _object(json.loads(line))
        except (ValueError, RecursionError):
            row = {}
        amount = usd(row.get('charged'))
        if amount is None:
            unpriced += 1
        else:
            amounts.append(amount)
        tier = row.get('applied_service_tier')
        if tier in TIERS:
            tiers[tier] += 1
        total += 1
        if detail and len(items) < LIST_LIMIT:
            item = _fields(row, ('ts', 'wall', 'model', 'status', 'reserved', 'charged', 'refused', 'usage_missing',
                                 'service_tier', 'applied_service_tier', 'latency_ms', 'tokens'))
            if item['ts'] is None and item['wall'] is None:
                item['wall'] = _scalar(row.get('time'))
            if item['service_tier'] is None:
                item['service_tier'] = _safe(row.get('requested_service_tier'))
            if isinstance(row.get('tokens'), dict):
                item['tokens'] = _fields(row['tokens'], ('prompt', 'completion', 'cached', 'cache_write', 'reasoning',
                                                        'prompt_tokens', 'completion_tokens', 'total_tokens'))
            items.append(item)
    return Ledger(items, total, usd_sum(amounts) if amounts or not unpriced else None, unpriced, tiers)


def _kind(summary):
    value = summary.get('session_kind')
    return value if value in ('admission', 'ingestion', 'hygiene', 'grooming') else None


def _outcomes(summary):
    verdicts = _list(summary.get('verdicts'))
    totals = Counter(row.get('status') for row in verdicts if isinstance(row, dict)
                     and row.get('status') in ('published', 'rejected', 'unchanged'))
    return dict(published=totals['published'], rejected=totals['rejected'], unchanged=totals['unchanged'],
                total=len(verdicts))


def _drafts_summary(summary):
    drafts = _object(summary.get('drafts'))
    return {key: len(_list(drafts.get(key))) for key in ('created', 'renewed', 'refused')}


def _compact(run_dir, group, label):
    parts = (*SESSIONS, group, label)
    summary = _json(run_dir, *parts, 'summary.json')
    closure = _json(run_dir, *parts, 'proxy-close.json')
    ledger = _ledger(run_dir, parts)
    if (closure.get('schema') == 'curator-proxy-close/1' and type(closure.get('settled')) is bool
            and count(closure.get('unsettled_requests')) is not None and usd(closure.get('spent_snapshot_usd')) is not None):
        amount = usd(closure['spent_snapshot_usd'])
        unsettled = closure['unsettled_requests']
        settled = closure['settled'] and unsettled == 0
    else:
        proxy = _object(summary.get('proxy'))
        amount = ledger.amount if ledger.amount is not None else usd(summary.get('cost_usd'))
        unsettled = count(proxy.get('unsettled_requests'))
        unsettled = max(ledger.unpriced, unsettled or 0)
        settled = proxy.get('settled') is True and unsettled == 0 and amount is not None
    start = _json(run_dir, *parts, 'proxy-start.json') if not summary else {}
    session_id = _safe(summary.get('session_id'))
    tiers = {tier for tier in _list(summary.get('applied_service_tiers')) if tier in TIERS} | set(ledger.tiers)
    host_end = _fields(summary['host_end'], ('reason', 'ok')) if isinstance(summary.get('host_end'), dict) else None
    deferrals = count(summary.get('deferrals'))
    close_reason = _object(summary.get('sandbox')).get('stopped')
    if deferrals is None and (close_reason == 'flex-capacity-deferred'
                              or host_end is not None and host_end['reason'] == 'flex-capacity-deferred'):
        deferrals = 1
    row = dict(id=session_id or _safe(f'{group}:{label}') or label, group=group, label=label, session_id=session_id,
        session_kind=_kind(summary), window=_fields(summary['window'], ('session', 'actor', 'first', 'last'))
        if isinstance(summary.get('window'), dict) else None,
        coverage=_fields(summary['coverage'], ('session', 'actor', 'last_step'))
        if isinstance(summary.get('coverage'), dict) else None,
        **_fields(summary, ('started_wall', 'wall_seconds', 'run_state', 'session_state', 'stopped_by_cap',
                            'requested_service_tier', 'requests', 'published_before', 'published_after')),
        cost_usd=None if amount is None else usd_text(amount), cap_usd=_money(summary.get('cap_usd', start.get('cap_usd'))),
        settled=settled, unsettled_requests=unsettled, applied_service_tiers=sorted(tiers), deferrals=deferrals,
        model_status=[v for x in _list(summary.get('model_status'))[:12] if (v := _scalar(x)) is not None],
        verdicts_summary=_outcomes(summary), drafts_summary=_drafts_summary(summary), host_end=host_end)
    return row


@dataclass(frozen=True)
class SessionIndex:
    rows: list[dict]
    groups: list[str]
    spend: dict | None


_lock = threading.Lock()
_cache: OrderedDict[Path, tuple[tuple, SessionIndex]] = OrderedDict()


def _spend(rows, unread):
    if not rows:
        return None
    settled = sum(r['settled'] for r in rows)
    unsettled = sum(r['unsettled_requests'] for r in rows)
    amounts = [n for r in rows if (n := usd(r['cost_usd'])) is not None]
    spent = usd_sum(amounts)
    hygiene = [r for r in rows if r['session_kind'] == 'hygiene']
    ingestion = [r for r in rows if r['session_kind'] in ('admission', 'ingestion')]
    hyg = usd_sum(n for r in hygiene if (n := usd(r['cost_usd'])) is not None)
    ing = usd_sum(n for r in ingestion if (n := usd(r['cost_usd'])) is not None)
    tiers = Counter(tier for r in rows for tier in r['applied_service_tiers'])
    return dict(sessions_total=len(rows), sessions_settled=settled, sessions_unsettled=len(rows) - settled,
        spent_usd=usd_text(spent) if amounts else None, unsettled_requests=unsettled,
        spend_complete=settled == len(rows) and unsettled == 0 and not unread,
        ingestion_usd=usd_text(ing) if any(r['cost_usd'] is not None for r in ingestion) else None,
        hygiene_usd=usd_text(hyg) if any(r['cost_usd'] is not None for r in hygiene) else None,
        hygiene_share=float(hyg / spent) if spent and (hygiene or len(ingestion) == len(rows)) else None,
        ingestion_sessions=len(ingestion), hygiene_sessions=len(hygiene), applied_tiers=dict(tiers),
        deferrals=sum(r['deferrals'] or 0 for r in rows))


def index(info: RunInfo) -> SessionIndex:
    run_dir = info.run_dir
    if run_dir is None:
        return SessionIndex([], [], None)
    with _lock:
        entries, unread = _entries(run_dir, *SESSIONS)
        members, groups = [], []
        for group, status in entries:
            if not (_safe(group) and stat.S_ISDIR(status.st_mode)):
                unread |= stat.S_ISLNK(status.st_mode)
                continue
            groups.append(group)
            found, failed = _entries(run_dir, *SESSIONS, group)
            unread |= failed
            members.extend((group, label) for label, entry in found if _safe(label)
                           and (stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode)))
        stamp = (tuple(groups), unread, tuple((group, label, *(_stamp(run_dir, *SESSIONS, group, label, name)
                  for name in SESSION_FILES)) for group, label in members))
        cached = _cache.get(run_dir)
        if cached is not None and cached[0] == stamp:
            _cache.move_to_end(run_dir)
            return cached[1]
        rows = [_compact(run_dir, group, label) for group, label in members]
        rows.sort(key=lambda row: (row['started_wall'] is None, row['started_wall'] or 0, row['group'], row['label']))
        result = SessionIndex(rows, groups, _spend(rows, unread))
        _cache[run_dir] = stamp, result
        _cache.move_to_end(run_dir)
        if len(_cache) > CACHED_RUNS:
            _cache.popitem(last=False)
        return result


def curator_spend(info: RunInfo) -> dict | None:
    return index(info).spend


def _filtered(sources, ids, *, drafts):
    matched, statuses, total, total_lineage = [], [], 0, 0

    def select(row, sessions):
        return not ids.isdisjoint(sessions) or any(row[key] in ids
            for key in ('created_by_session', 'last_touched_session', 'promoted_by_session'))

    for _, path in sources:
        room = LIST_LIMIT - len(matched)
        if drafts:
            try:
                with curator.opened_directory(path) as root:
                    state, _, rows, count_rows, lineage = curator.read_drafts(root, 0, room, select=select)
            except FileNotFoundError:
                state, rows, count_rows, lineage = 'missing', [], 0, 0
            except OSError:
                state, rows, count_rows, lineage = 'unreadable', [], 0, 0
        else:
            state, _, all_rows = curator.read(path)
            lineage = len(all_rows)
            own = [row for row in all_rows if row['session'] in ids]
            rows, count_rows = own[:room], len(own)
            # The external source route owns full diagnostics. Keep the run list compact.
            rows = [{**row, 'diagnostics': row['diagnostics'][:3],
                     'diagnostics_omitted': row['diagnostics_omitted'] + max(0, len(row['diagnostics']) - 3)} for row in rows]
        statuses.append(state)
        matched.extend(rows)
        total += count_rows
        total_lineage += lineage
    state = 'available' if 'available' in statuses else next((s for s in statuses if s != 'empty'),
                                                             'empty' if statuses else 'not_configured')
    return dict(source_status=state, filtered_to_run=True, total_lineage=total_lineage,
                items=matched, total=total, omitted=total - len(matched))


def run_curator(info: RunInfo, sources: FrameSources, now: float, is_live: bool) -> dict:
    found = index(info)
    ids = {r['session_id'] for r in found.rows if r['session_id'] is not None}
    runner = (curator_runner.run_status(info.run_dir, now, examined_ids=ids) if info.run_dir is not None else
              dict(source_status='missing', snapshot=None, read_wall=now, status=None))
    if is_live and runner['source_status'] == 'missing':
        runner = curator_runner.status(sources.curator_runner_status, now, examined_ids=ids)
    return dict(runner=runner, spend=found.spend, sessions=found.rows[-MAX_SESSIONS:],
                sessions_omitted=max(0, len(found.rows) - MAX_SESSIONS),
                grooming=telemetry.boundary_grooming(info, sources.curator_grooming, groups=found.groups),
                gate_verdicts=_filtered(sources.curator_results, ids, drafts=False),
                drafts=_filtered(sources.curator_drafts, ids, drafts=True))


def _detail(summary):
    tokens = _fields(summary.get('tokens'), ('prompt', 'completion', 'cached', 'cache_write', 'reasoning'))
    tools = _fields(summary.get('tool_calls'), ('count', 'failed', 'bytes'))
    tools['by_name'] = {name: n for name, raw in list(_object(_object(summary.get('tool_calls')).get('by_name')).items())[:LIST_LIMIT]
                        if _safe(name) and (n := count(raw)) is not None}
    sandbox = _fields(summary.get('sandbox'), ('stopped', 'seconds', 'peak_memory_bytes'))
    lifecycle = _object(summary.get('sandbox'))
    code = lifecycle.get('returncode')
    sandbox['returncode'] = code if type(code) is int and abs(code) < 2**31 else None
    survivors = lifecycle.get('survivors')
    sandbox['survivors'] = ([pid for raw in survivors[:LIST_LIMIT] if (pid := count(raw)) is not None]
                            if isinstance(survivors, list) else None)
    verdicts = [dict(_fields(v, ('operation', 'status', 'submission', 'version')),
                     diagnostics=_strings(v.get('diagnostics'), 12))
                for v in _list(summary.get('verdicts'))[:LIST_LIMIT] if isinstance(v, dict)]
    drafts = _object(summary.get('drafts'))
    proxy = _fields(summary.get('proxy'), ('entries', 'charged_usd', 'max_reserved_usd', 'refusals', 'forwarded',
        'cap_refused', 'usage_missing', 'settled', 'unsettled_requests', 'pending_reserved_usd', 'revoked', 'breaches', 'receipt_error'))
    proxy['refusal_reasons'] = _strings(_object(summary.get('proxy')).get('refusal_reasons'))
    return dict(tokens=tokens, tool_calls=tools, sandbox=sandbox, errors=_strings(summary.get('errors')),
                refused=_strings(summary.get('refused')), verdicts=verdicts,
                drafts={k: [_fields(v, ('id', 'draft_id', 'reason')) if isinstance(v, dict) else _safe(v)
                            for v in _list(drafts.get(k))[:LIST_LIMIT]] for k in ('created', 'renewed', 'refused')},
                proxy=proxy)


def run_curator_session(info: RunInfo, session_id: str) -> dict:
    if not _safe(session_id) or len(session_id) > ID_LIMIT:
        raise ViewError(400, 'bad_session_id')
    rows = index(info).rows
    found = next((r for r in rows if session_id in (r['session_id'], f"{r['group']}:{r['label']}")), None)
    if found is None:
        found = next((r for r in rows if session_id == r['label']), None)
    if found is None:
        raise ViewError(404, 'unknown_curator_session')
    parts = (*SESSIONS, found['group'], found['label'])
    ledger = _ledger(info.run_dir, parts, detail=True)
    session = dict(found, **_detail(_json(info.run_dir, *parts, 'summary.json')))
    return dict(session=session, ledger=ledger.items, ledger_total=ledger.total, ledger_omitted=ledger.total - len(ledger.items))
