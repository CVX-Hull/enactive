"""Payload builders for the per-run `spectator-view/1` routes. Pure reads over one evaluation store.

Each builder takes the catalog, the run's `RunInfo` and an open read-only connection and returns a plain
JSON-able dict (the app adds the schema field and bounds the size). Values keep their provenance:
`recorded` (a mechanical fact), `read` (a game reader), `derived` (computed from other records) or `human`.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sqlite3
import time

from harness.evaluation.core import context as ctx
from harness.evaluation.core.host import host_facts
from harness.evaluation.core.metrics import nearest_rank
from harness.evaluation.core.records import EvaluationError, loads
from harness.evaluation.core.sources import read_carry, read_host, read_json_file, read_manifest, read_memory, run_archive_entry

from .catalog import Catalog, RunInfo, ViewError
from . import pause

SOURCE_ID = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
FINDING_KINDS = ('stall', 'long_activity', 'ineffective_repeat', 'handoff', 'death', 'episode', 'run_end', 'custody_stop',
    'tool_refused', 'memory_write', 'program_save', 'context_eviction')
PROVENANCE = {'survival': 'derived', 'pace': 'derived', 'stall': 'derived', 'lineage': 'derived', 'handoff': 'derived',
    'run': 'derived', 'mode': 'read', 'needs': 'read', 'ladder': 'read', 'reader': 'read'}
DERIVED_NAMES = ('memory.retrieved_beyond_carry', 'memory.late_write_share')
HEADLINE = ('survival.game_hours', 'stall.longest', 'stall.count', 'mode.out_of_play_share',
    'pace.routine_seconds_per_decision', 'host.dollars_per_decision', 'host.large_rewrite_share', 'run.infrastructure_loss')


def provenance(name: str) -> str:
    if name in DERIVED_NAMES:
        return 'derived'
    return PROVENANCE.get(name.split('.')[0], 'recorded')


def scalar(value: object) -> float | None:
    """One comparable number from a stored metric value."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ('hours', 'value', 'count'):
            if isinstance(value.get(key), (int, float)) and not isinstance(value.get(key), bool):
                return float(value[key])
    return None


# The validated readers each metric is derived from. A metric is `validated` only when every one of them has `pass: true`
# in data/evaluation/reader-validation.json; a missing entry or `pass: null` (unmeasured) is unvalidated. Metrics that
# read no frame reader (host, tool, custody, memory, program and handoff facts) are `null`.
NEEDS_READERS = ('hunger', 'thirst', 'weariness', 'pain')
METRIC_READERS = {'survival.game_hours': ('clock', 'mode', 'death'), 'pace.routine_seconds_per_decision': ('clock', 'mode'),
    'pace.long_activities': ('clock',), 'pace.dollars_per_game_hour': ('clock', 'mode'), 'mode.out_of_play_share': ('mode',),
    'stall.longest': ('mode',), 'stall.count': ('mode',), 'needs.severe_share': ('mode', *NEEDS_READERS),
    'ladder.reached': ('clock', 'mode', *NEEDS_READERS), 'lineage.continuity': ('clock', 'identity'),
    'run.infrastructure_loss': ('death',), 'run.provider_loss': ('death',)}


def validated(name: str, validation: dict | None) -> bool | None:
    """`true` when every reader the metric depends on passed held-out validation, `false` when any did not (or none
    is recorded), `null` when the metric depends on no reader."""
    readers = METRIC_READERS.get(name)
    if readers is None:
        return None
    return all((validation or {}).get(reader, {}).get('pass') is True for reader in readers)


def metric_json(row, validation: dict | None = None) -> dict:
    return dict(name=row.name, key=row.key, value=row.value, count=row.count, denominator=row.denominator,
        missing=row.missing, source=provenance(row.name), validated=validated(row.name, validation))


def outcome(info: RunInfo) -> dict:
    value = info.survival
    return dict(hours=None if value is None else value['hours'], died=None if value is None else value['outcome'] == 'died',
        outcome=None if value is None else value['outcome'], censor_reason=None if value is None else value.get('censor_reason'),
        episodes=None if value is None else value.get('episodes'), lost=info.lost)


def headline(info: RunInfo) -> dict:
    return {name: scalar(info.metric(name)) for name in HEADLINE}


def versions(info: RunInfo) -> dict:
    return dict(core_version=info.meta.get('core_version'), binding_id=info.meta.get('binding_id'),
        binding_version=info.meta.get('binding_version'), state=info.state, created_wall=info.meta.get('created_wall'))


def run_state(info: RunInfo, live_session: str | None) -> str:
    """`live` only for the run this viewer evaluates. A `live` store of any other run was never finalized (#435)."""
    if info.state != 'live':
        return info.state
    return 'live' if info.session == live_session else 'unfinished'


def run_row(info: RunInfo, live_session: str | None) -> dict:
    facts = info.facts
    return dict(run=info.run, session=info.session, state=run_state(info, live_session), labels=info.labels, outcome=outcome(info),
        decisions=info.decisions, dollars=info.dollars, source_commit=facts.get('source_commit'), model=facts.get('model'),
        effort=facts.get('effort'), headline=headline(info), versions=versions(info))


# Pagination -----------------------------------------------------------------------------------------

def page(rows: list, limit: int, key) -> dict:
    """The first `limit` rows and the cursor to continue from (None at the end). `rows` holds up to limit+1."""
    more = len(rows) > limit
    rows = rows[:limit]
    return dict(items=rows, next=key(rows[-1]) if more and rows else None, limit=limit)


# Summary --------------------------------------------------------------------------------------------

def validation_key(reader: str) -> str:
    if reader == 'game_time':
        return 'clock'
    return reader.split('.', 1)[1] if reader.startswith('vital.') and not reader.startswith('vital.limb') else reader


def game_state(connection: sqlite3.Connection, validation: dict) -> dict | None:
    row = connection.execute("SELECT seq, decision, wall, source_id, frame_sha256 FROM steps WHERE source_id IS NOT NULL "
        "ORDER BY seq DESC LIMIT 1").fetchone()
    if row is None:
        return None
    seq, decision, wall, source_id, sha = row
    readings = {}
    for reader, version, value, confidence, abstain in connection.execute(
            'SELECT reader, reader_version, value, confidence, abstain FROM readings WHERE seq=? ORDER BY reader', (seq,)):
        if reader.startswith('core.'):
            continue
        check = validation.get(validation_key(reader))
        readings[reader] = dict(value=loads(value), confidence=confidence, abstain=abstain, version=version,
            validation=None if check is None else {'pass': check.get('pass'), 'accuracy': check.get('accuracy'),
                'n': check.get('n'), 'floor': check.get('floor')})
    frame = connection.execute("SELECT value FROM readings WHERE seq=? AND reader='core.frame'", (seq,)).fetchone()
    summary = loads(frame[0]) if frame and frame[0] else {}
    return dict(provenance='read', seq=seq, decision=decision, wall=wall, source_id=source_id, frame_sha256=sha,
        mode=summary.get('mode'), game_time=summary.get('game_time'), identity=summary.get('identity'),
        vitals=summary.get('vitals'), threat=summary.get('threat'), threat_count=summary.get('threat_count'), readings=readings)


# Image evictions happen every few requests; they are listed on the requests route, and never crowd
# rarer findings (handoffs, memory writes, stalls) out of the summary window.
ROUTINE_FINDINGS = ('context_eviction',)


def findings(connection: sqlite3.Connection, limit: int = 100) -> list[dict]:
    kinds = [kind for kind in FINDING_KINDS if kind not in ROUTINE_FINDINGS]
    marks = ','.join('?' * len(kinds))
    rows = connection.execute(
        f'SELECT e.id, e.seq_start, e.seq_end, e.kind, e.source, e.confidence, e.payload, s.decision, s.wall FROM events e '
        f'LEFT JOIN steps s ON s.seq=e.seq_start WHERE e.kind IN ({marks}) ORDER BY e.seq_start DESC, e.id DESC LIMIT ?',
        (*kinds, limit)).fetchall()
    return [dict(id=i, seq_start=a, seq_end=b, kind=k, source=src, confidence=c, payload=loads(p), decision=d, wall=w)
        for i, a, b, k, src, c, p, d, w in rows]


def reader_coverage(info: RunInfo, validation: dict) -> list[dict]:
    rows = []
    for (name, key), row in sorted(info.metrics.items()):
        if name != 'reader.coverage':
            continue
        check = validation.get(validation_key(key))
        rows.append(dict(reader=key, coverage=row.value, count=row.count, denominator=row.denominator, missing=row.missing,
            validation=check))
    return rows


def summary(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection, live: bool, evaluator: dict | None,
            now: float | None = None) -> dict:
    validation = catalog.validation()
    ladder = info.metric('ladder.reached')
    started = connection.execute('SELECT MIN(wall) FROM steps').fetchone()[0]
    routine = connection.execute(f"SELECT COUNT(*) FROM events WHERE kind IN ({','.join('?' * len(ROUTINE_FINDINGS))})",
        ROUTINE_FINDINGS).fetchone()[0]
    return dict(run=info.run, session=info.session, state=info.state, facts=info.facts, labels=info.labels,
        started_wall=started, routine_findings=dict(context_eviction=routine), outcome=outcome(info), decisions=info.decisions, dollars=info.dollars, versions=versions(info), live=live,
        evaluator=evaluator,
        pause=pause.conditions(connection, info.facts, time.time() if now is None else now) if live else None,
        game_state=game_state(connection, validation), findings=findings(connection), ladder=ladder,
        metrics=[metric_json(row, validation) for _, row in sorted(info.metrics.items())],
        reader_coverage=reader_coverage(info, validation))


# Steps, frames --------------------------------------------------------------------------------------

def steps(connection: sqlite3.Connection, after: int, limit: int) -> dict:
    rows = connection.execute("SELECT s.seq, s.decision, s.wall, s.kind, s.mode, s.game_time, s.source_id, s.frame_changed, "
        "s.dollars, r.value FROM steps s LEFT JOIN readings r ON r.seq=s.seq AND r.reader='core.input' "
        "WHERE s.seq > ? ORDER BY s.seq LIMIT ?", (after, limit + 1)).fetchall()
    items = [dict(seq=a, decision=b, wall=c, kind=d, mode=e, game_time=f, source_id=g,
        frame_changed=None if h is None else bool(h), dollars=i, keys=loads(j) or []) for a, b, c, d, e, f, g, h, i, j in rows]
    return page(items, limit, lambda item: item['seq'])


def frame(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection, source_id: str) -> bytes:
    """The original PNG, only after its SHA-256 matches the one the record holds."""
    if not SOURCE_ID.fullmatch(source_id):
        raise ViewError(400, 'bad_source_id')
    row = connection.execute('SELECT frame_sha256 FROM steps WHERE source_id=? LIMIT 1', (source_id,)).fetchone()
    if row is None or row[0] is None:
        raise ViewError(404, 'unknown_frame', source_id)
    path = catalog.need_run_dir(info) / 'sources' / f'{source_id}.png'
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ViewError(404, 'frame_unavailable', source_id) from exc
    if hashlib.sha256(data).hexdigest() != row[0]:
        raise ViewError(409, 'frame_digest_mismatch', source_id)
    return data


# Tools, calls, requests ----------------------------------------------------------------------------

def tools(connection: sqlite3.Connection) -> dict:
    per: dict[str, dict] = {}
    transitions: dict[tuple[str, str], int] = {}
    previous: dict[str, str] = {}
    for actor, tool, status, latency, size in connection.execute(
            'SELECT actor, tool, status, latency_ms, result_bytes FROM tool_calls ORDER BY wall, rowid'):
        entry = per.setdefault(tool, dict(tool=tool, calls=0, refused=0, errors=0, result_bytes=0, latencies=[]))
        entry['calls'] += 1
        entry['refused'] += status == 'refused'
        entry['errors'] += status == 'error'
        entry['result_bytes'] += size or 0
        if latency is not None:
            entry['latencies'].append(latency)
        if actor in previous:
            transitions[(previous[actor], tool)] = transitions.get((previous[actor], tool), 0) + 1
        previous[actor] = tool
    rows = []
    for tool, entry in sorted(per.items(), key=lambda kv: -kv[1]['calls']):
        latencies = entry.pop('latencies')
        rows.append(dict(entry, p50_ms=nearest_rank(latencies, .5), p95_ms=nearest_rank(latencies, .95)))
    return dict(tools=rows, transitions=[[a, b, n] for (a, b), n in sorted(transitions.items())])


def calls(connection: sqlite3.Connection, tool: str | None, status: str | None, after: int, limit: int) -> dict:
    where, arguments = ['c.rowid > ?'], [after]
    if tool:
        where.append('c.tool = ?')
        arguments.append(tool)
    if status:
        where.append('c.status = ?')
        arguments.append(status)
    rows = connection.execute(
        'SELECT c.rowid, c.request_id, c.tool_call_id, c.actor, c.decision, c.tool, c.status, c.latency_ms, c.result_bytes, '
        'c.wall, c.operation_id, s.seq, s.source_id FROM tool_calls c LEFT JOIN steps s ON s.operation_id = c.operation_id '
        f'WHERE {" AND ".join(where)} ORDER BY c.rowid LIMIT ?', (*arguments, limit + 1)).fetchall()
    items = [dict(id=a, request_id=b, tool_call_id=c, actor=d, decision=e, tool=f, status=g, latency_ms=h, result_bytes=i, wall=j,
        operation_id=k, step=None if l is None else dict(seq=l, source_id=m)) for a, b, c, d, e, f, g, h, i, j, k, l, m in rows]
    return page(items, limit, lambda item: item['id'])


def requests(connection: sqlite3.Connection, after: int, limit: int) -> dict:
    rows = connection.execute('SELECT rowid, request_id, actor, wall, attempt, input_tokens, cache_read, cache_write, '
        'output_tokens, dollars, retry_class, omitted_images, manifest FROM requests WHERE rowid > ? ORDER BY rowid LIMIT ?',
        (after, limit + 1)).fetchall()
    items = [dict(id=a, request_id=b, actor=c, wall=d, attempt=e, input_tokens=f, cache_read=g, cache_write=h,
        output_tokens=i, dollars=j, retry_class=k, omitted_images=l, manifest=m) for a, b, c, d, e, f, g, h, i, j, k, l, m in rows]
    result = page(items, limit, lambda item: item['id'])
    markers = [dict(kind=kind, seq=seq, wall=wall, payload=loads(payload)) for kind, seq, wall, payload in connection.execute(
        "SELECT e.kind, e.seq_start, s.wall, e.payload FROM events e LEFT JOIN steps s ON s.seq=e.seq_start "
        "WHERE e.kind IN ('context_eviction','handoff') ORDER BY e.seq_start LIMIT 500")]
    return dict(result, markers=markers)


def host_events(catalog: Catalog, info: RunInfo, actor: str):
    run_dir = catalog.need_run_dir(info)
    directory = ctx._actor_directory(run_dir, actor)
    if directory is None or not (directory / 'host.jsonl').is_file():
        raise ViewError(404, 'unknown_actor', actor)
    return read_host(directory / 'host.jsonl', directory.name, run_archive_entry(run_dir))[1]


def context(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection, request_id: str, actor: str | None) -> dict:
    owners = [a for (a,) in connection.execute('SELECT actor FROM requests WHERE request_id=? ORDER BY rowid', (request_id,))]
    if actor is not None:
        owners = [a for a in owners if a == actor]
    if not owners:
        raise ViewError(404, 'unknown_request', request_id)
    if len(owners) > 1:
        raise ViewError(409, 'ambiguous_request', ','.join(owners))
    events = host_events(catalog, info, owners[0])
    value = ctx.request_context(catalog.need_run_dir(info), owners[0], events, request_id)
    kinds: dict[str, int] = {}
    for part in value['parts']:
        kinds[part['kind']] = kinds.get(part['kind'], 0) + (part.get('bytes') or 0)
    return dict(value, bytes_by_kind=kinds)


# Memory, programs, handoffs ------------------------------------------------------------------------

def memory_store(catalog: Catalog, info: RunInfo):
    path = info.meta.get('memory_store')
    if not path:
        try:
            path = read_manifest(catalog.need_run_dir(info)).get('player_store')
        except EvaluationError as exc:
            raise ViewError(500, 'bad_manifest', str(exc)) from exc
    if not path or not Path(path).is_file():
        return None
    return read_memory(Path(path))


def memory(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection) -> dict:
    store = memory_store(catalog, info)
    if store is None:
        return dict(records=[], available=False)
    reads: dict[str, list[dict]] = {}
    for seq, payload in connection.execute("SELECT seq_start, payload FROM events WHERE kind='memory_read' ORDER BY seq_start"):
        value = loads(payload)
        for record_id in value.get('record_ids', ()):
            reads.setdefault(record_id, []).append(dict(seq=seq, actor=value.get('actor'), tool=value.get('tool')))
    carried: dict[str, list[str]] = {}
    for actor, ids in read_carry(catalog.need_run_dir(info)).items():
        for record_id in ids:
            carried.setdefault(record_id, []).append(actor)
    labels = [l for l in catalog.labels() if l.get('session') == info.session]
    items = []
    for record_id, doc in list(store.records.items())[:500]:
        chain = []
        parent = doc.get('supersedes')
        while parent and len(chain) < 20:
            chain.append(parent)
            parent = (store.records.get(parent) or {}).get('supersedes')
        items.append(dict(id=record_id, kind=doc.get('kind'), actor_id=doc.get('actor_id'), created_wall=doc.get('created_wall'),
            text=(doc.get('text') or '')[:4000], data=doc.get('data'), sources=doc.get('sources') or [],
            supports=doc.get('supports') or [], supersedes=doc.get('supersedes'), chain=chain, reads=reads.get(record_id, []),
            carried_by=carried.get(record_id, []), labels=[l for l in labels if l.get('target') == record_id]))
    return dict(records=items, available=True, provenance='player_claim')


def programs(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection) -> dict:
    store = memory_store(catalog, info)
    docs = [] if store is None else [dict(id=pid, parent_id=doc.get('parent_id'), actor_id=doc.get('actor_id'),
        created_wall=doc.get('created_wall'), name=doc.get('name') or doc.get('title'), document=doc)
        for pid, doc in store.programs.items()]
    runs = []
    run_dir = info.run_dir
    if run_dir is not None:
        by_actor = {}
        for (actor,) in connection.execute('SELECT DISTINCT actor FROM tool_calls'):
            try:
                by_actor[actor] = host_events(catalog, info, actor)
            except ViewError:
                continue
        facts = host_facts(tuple(by_actor), by_actor)
        for call in facts.calls:
            if call.tool == 'player_program_run' and call.finished:
                value = call.result if isinstance(call.result, dict) else {}
                steps_done = value.get('steps') if isinstance(value.get('steps'), list) else []
                runs.append(dict(actor=call.actor, program_id=value.get('program_id') or call.arguments.get('program_id'),
                    run_id=value.get('run_id'), status=value.get('status'), steps=len(steps_done),
                    elapsed_seconds=value.get('elapsed_seconds'), reason=value.get('reason'), wall=call.wall))
    saves = [loads(p) for (p,) in connection.execute("SELECT payload FROM events WHERE kind='program_save' ORDER BY seq_start")]
    return dict(programs=docs, runs=runs, saves=saves, provenance='player_claim')


def handoffs(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection) -> dict:
    rows = connection.execute("SELECT e.seq_start, e.payload, s.decision, s.wall FROM events e LEFT JOIN steps s ON s.seq=e.seq_start "
        "WHERE e.kind='handoff' ORDER BY e.seq_start").fetchall()
    labels = [l for l in catalog.labels() if l.get('session') == info.session]
    items = []
    run_dir = info.run_dir
    for index, (seq, payload, decision, wall) in enumerate(rows):
        value = loads(payload)
        carry, text, ids = None, None, []
        context_id = value.get('context_id')
        if run_dir is not None and isinstance(context_id, str) and SOURCE_ID.fullmatch(context_id):
            path = run_dir / 'contexts' / f'{context_id}.json'
            try:
                packet = read_json_file(path)
                text = packet.get('summary')
                knowledge = packet.get('knowledge') or {}
                ids = [n['id'] for k in ('records', 'programs') for n in knowledge.get(k, ()) if isinstance(n, dict) and 'id' in n]
                carry = path.stat().st_size
            except (OSError, EvaluationError):
                pass
        resume = info.metrics.get(('handoff.decisions_to_resume', str(index)))
        ratio = info.metrics.get(('handoff.carry_ratio', str(index)))
        errors = [l for l in labels if l.get('target') in ids and l.get('code') == 'identity_or_world_error'
            and l.get('verdict') == 'confirm']
        items.append(dict(index=index, seq=seq, decision=decision, wall=wall, actor=value.get('actor'), context_id=context_id,
            context_sha256=value.get('context_sha256'), decisions_to_resume=None if resume is None else resume.value,
            carry_ratio=None if ratio is None else ratio.value, carry_bytes=carry, carry_text=text, carried_ids=ids,
            identity_check=dict(provenance='human', errors=errors, checked=bool(errors))))
    return dict(handoffs=items)
