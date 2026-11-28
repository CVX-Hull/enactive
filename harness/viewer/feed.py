"""The story feed: one ordered, paginated list of what the player did and what happened to its context and memory.

Step entries combine the evaluator's steps and tool calls with the run's host traces (`telemetry.py`); milestone
entries are context cuts, newer knowledge versions and the few findings that change how a run reads. A run without
readable traces still has a feed, built from the evaluation record alone.

An entry has an identity (`id`) and a place (`order`, the paging cursor), and they are separate. A step, cut or update is
identified by its anchor: actor and trace line, or the step number without a trace, with room behind each anchor for
the steps and findings attached to it. A finding is identified by what it states, because the evaluator rewrites and
renumbers its events on every pass. A finding added late may therefore move the `order` of others at its anchor, and may
appear behind a cursor, but changes no `id`; the page re-reads the recent part of the list.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
import hashlib
import json
import sqlite3
from typing import Any

from harness.evaluation.core.host import ToolCall
from harness.evaluation.core.records import loads

from .catalog import TEXT_LIMIT, RunInfo
from .telemetry import HostProjection, Step, Steps, count, identifier, read, usd_text
from .views import page
from .knowledge import source_read

#: Findings that are story milestones; the summary lists the rest.
STORY_FINDINGS = ('stall', 'death', 'custody_stop', 'handoff', 'run_end')
#: Findings whose payload grows while they last, so that it is no part of what identifies them.
GROWING_FINDINGS = ('stall',)
PREVIEW_LIMIT = 2048
PAYLOAD_LIMIT = 2048
KEYS_LIMIT = 64
KEY_LIMIT = 128
RECEIPT_LIMIT = 20
#: A page ends early rather than exceed the response ceiling.
PAGE_BYTES = 3 * 1024 * 1024
LINE_BITS, SUB_BITS = 22, 13
FINDING_SUB = 1 << (SUB_BITS - 1)


def entry_id(anchor: int, sub: int = 0) -> int:
    return (anchor << SUB_BITS) + min(sub, (1 << SUB_BITS) - 1)


def trace_anchor(actor_index: int, line: int) -> int:
    return (actor_index << LINE_BITS) + line


def clip(value: object, limit: int = TEXT_LIMIT) -> str | None:
    return value[:limit] if isinstance(value, str) else None


def action_keys(arguments: dict) -> list[str]:
    """What an input call sent, in the evaluator's own words (`key:ENTER`, `text:…`)."""
    actions = arguments.get('actions') if isinstance(arguments.get('actions'), list) else []
    keys = []
    for action in actions[:KEYS_LIMIT]:
        if not isinstance(action, dict) or not isinstance(action.get('type'), str):
            continue
        kind = action['type']
        if kind == 'key':
            modifiers = action.get('modifiers') if isinstance(action.get('modifiers'), list) else []
            value = '+'.join([m for m in modifiers if isinstance(m, str)] + [str(action.get('key'))])
        elif kind == 'text':
            value = str(action.get('text'))
        elif kind == 'wait':
            value = f"{action.get('seconds')}s"
        else:
            value = ''
        keys.append((f'{kind}:{value}' if value else kind)[:KEY_LIMIT])
    return keys


def call_result(call: ToolCall, reason: str | None) -> dict:
    """The mechanical result a tool returned: statuses, dispositions and IDs, never its text or frame."""
    value = call.result if isinstance(call.result, dict) else {}
    receipts = [r for r in value['receipts'] if isinstance(r, dict)] if isinstance(value.get('receipts'), list) else []
    source = value.get('source') if isinstance(value.get('source'), dict) else {}
    return dict(status=clip(value.get('status'), 128), reason=clip(reason if reason is not None else value.get('reason')),
        source_id=identifier(source.get('source_id')) or identifier(value.get('source_id')),
        receipts=[dict(disposition=clip(r.get('disposition'), 128), reason=clip(r.get('reason'), 256),
            emitted_events=count(r.get('emitted_events'))) for r in receipts[:RECEIPT_LIMIT]],
        receipts_omitted=max(0, len(receipts) - RECEIPT_LIMIT), result_bytes=call.result_bytes)


def preview(arguments: dict) -> tuple[str | None, int]:
    """The call's arguments as bounded JSON text, and how many characters were left out."""
    shown = {k: v for k, v in arguments.items() if k != 'intent'}
    if not shown:
        return None, 0
    text = json.dumps(shown, ensure_ascii=False, separators=(',', ':'), default=str)
    return text[:PREVIEW_LIMIT], max(0, len(text) - PREVIEW_LIMIT)


def placed(step: Step | None, near: Step | None, wall: float | None, decision: int | None) -> dict:
    """Where an entry sits: its own step, else the latest one before it, whose frame was on screen then. `decision` is
    the entry's own recorded one; the step on screen has its own, beside it, and never stands in for it."""
    shown = step or near
    return dict(seq=None if shown is None else shown.seq, exact_step=step is not None,
        decision=decision, step_decision=None if shown is None else shown.decision,
        wall=wall if wall is not None else (None if step is None else step.wall),
        source_id=None if shown is None else shown.source_id, mode=None if shown is None else shown.mode,
        game_time=None if shown is None else shown.game_time)


STEP_FIELDS: dict[str, Any] = dict(tool=None, intent=None, intent_source=None, intent_omitted_characters=0, keys=[], status=None,
    latency_ms=None, request_id=None, tool_call_id=None, operation_id=None, actor=None, reported_provider=None,
    applied_service_tier=None, source_read=None, reported_cost_usd=None, prompt_tokens=None, input_tokens=None, cache_read=None, cache_write=None, output_tokens=None,
    arguments_preview=None, arguments_omitted_characters=0, result=None)


def step_keys(connection: sqlite3.Connection) -> dict[int, list[str]]:
    rows = {}
    for seq, value in connection.execute("SELECT seq, value FROM readings WHERE reader='core.input' AND value IS NOT NULL"):
        keys = loads(value)
        if isinstance(keys, list):
            rows[seq] = [k[:KEY_LIMIT] for k in keys[:KEYS_LIMIT] if isinstance(k, str)]
    return rows


def host_call(call: ToolCall, host: HostProjection, step: Step | None, near: Step | None, keys: dict[int, list[str]]) -> dict:
    refused = host.refusals.get((call.actor, call.request_id, call.tool_call_id))
    response = host.by_request.get((call.actor, call.request_id))
    intent = call.arguments.get('intent')
    text, omitted = preview(call.arguments)
    latency = call.end_ms - call.start_ms if call.start_ms is not None and call.end_ms is not None \
        and call.end_ms >= call.start_ms else None
    result = call_result(call, refused) if call.finished or call.refused else None
    out = dict(STEP_FIELDS, tool=call.tool[:128], intent=clip(intent), intent_source='player_claim' if isinstance(intent, str) else None,
        intent_omitted_characters=max(0, len(intent) - TEXT_LIMIT) if isinstance(intent, str) else 0,
        keys=keys[step.seq] if step is not None and step.seq in keys and 'actions' in call.arguments else action_keys(call.arguments),
        status='refused' if call.refused else 'error' if call.error else 'ok' if call.finished else 'pending', latency_ms=latency,
        request_id=identifier(call.request_id), tool_call_id=identifier(call.tool_call_id), operation_id=identifier(call.operation_id),
        actor=call.actor, source_read=source_read(call), arguments_preview=text, arguments_omitted_characters=omitted, result=result)
    if response is not None:
        out.update(reported_provider=response.reported_provider, applied_service_tier=response.applied_service_tier,
            reported_cost_usd=None if response.reported_usd is None else usd_text(response.reported_usd),
            prompt_tokens=response.prompt_tokens, input_tokens=response.input_tokens, cache_read=response.cache_read,
            cache_write=response.cache_write, output_tokens=response.output_tokens)
    return dict(entry_kind='step', **placed(step, near, call.wall, call.decision), **out)


def recorded_step(step: Step, keys: dict[int, list[str]], call: tuple | None = None) -> dict:
    """A step the evaluation record alone describes, with its tool call where one is joined."""
    out = dict(STEP_FIELDS, keys=keys.get(step.seq, []), operation_id=step.operation_id, actor=step.actor)
    decision = step.decision
    if call is not None:
        decision, request_id, tool_call_id, tool, status, latency, tokens, cache_read, cache_write, output = call
        known = [tokens, cache_read, cache_write]
        out.update(tool=tool, status=status, latency_ms=latency, request_id=request_id, tool_call_id=tool_call_id,
            prompt_tokens=None if any(v is None for v in known) else sum(known), input_tokens=tokens, cache_read=cache_read,
            cache_write=cache_write, output_tokens=output)
    return dict(entry_kind='step', **placed(step, None, step.wall, decision), **out)


def from_host(host: HostProjection, steps: Steps, keys: dict[int, list[str]]) -> tuple[list[dict], list[tuple[float, int]]]:
    """Entries with their IDs, and each call's (wall, anchor) for what is attached by time."""
    items, anchors, shown = [], [], set()
    for call in host.calls:
        step = steps.by_operation.get(call.operation_id) if call.operation_id else None
        anchor = trace_anchor(host.lines[call.actor], call.line)
        if step is not None:
            shown.add(step.seq)
        items.append(dict(id=entry_id(anchor), **host_call(call, host, step, steps.nearest(call.wall), keys)))
        if call.wall is not None:
            anchors.append((call.wall, anchor))
    anchors.sort()
    attached: dict[int, int] = {}
    for step in steps.rows:  # a step no tool call names: a program's child operation, or one before the first call
        if step.seq in shown:
            continue
        anchor = anchor_at(anchors, step.wall)
        attached[anchor] = attached.get(anchor, 0) + 1
        items.append(dict(id=entry_id(anchor, min(attached[anchor], FINDING_SUB - 1)), **recorded_step(step, keys)))
    def logical_key(actor: str, request_id: str | None) -> tuple[str, str] | None:
        if request_id is None:
            return None
        return actor, host.logical_requests.get((actor, request_id), request_id)

    cuts = {key: mark for mark in host.cuts
            if mark.fields['outcome'] == 'applied'
            and (key := logical_key(mark.actor, mark.fields['request_id'])) is not None}
    briefings = {}
    for mark in host.deliveries:
        key = logical_key(mark.actor, mark.fields['receiving_player_request_id'])
        cut = cuts.get(key) if key is not None else None
        joined = cut is not None and mark.fields['delivery_kind'] == 'post_cut_briefing' and mark.fields['outcome'] == 'delivered'
        delivery_id = entry_id(trace_anchor(mark.actor_index, mark.line))
        joined_cut_id = entry_id(trace_anchor(cut.actor_index, cut.line)) if joined else None
        if joined:
            briefing = {name: mark.fields[name] for name in ('knowledge_version', 'leads_count', 'index_count', 'delta_counts', 'summary')}
            briefings.setdefault(joined_cut_id, dict(briefing, delivery_id=delivery_id,
                briefing_tokens=cut.fields['briefing_tokens'], source_ids_count=cut.fields['source_ids_count']))
        items.append(dict(id=delivery_id, entry_kind='knowledge_delivery', joined_cut_id=joined_cut_id,
            **placed(None, steps.nearest(mark.wall), mark.wall, None), actor=mark.actor, **mark.fields))
    for mark in host.cuts:
        if mark.fields['outcome'] != 'applied':
            continue
        identity = entry_id(trace_anchor(mark.actor_index, mark.line))
        items.append(dict(id=identity, entry_kind='context_cut', briefing=briefings.get(identity),
            **placed(None, steps.nearest(mark.wall), mark.wall, None), actor=mark.actor, **mark.fields))
    for wait in host.coverage_waits:
        wall = wait['start_wall']
        items.append(dict(wait, order=entry_id(trace_anchor(wait['actor_index'], wait['line'])), entry_kind='coverage_wait',
            **placed(None, steps.nearest(wall), wall, None)))
    for mark in host.agenda_events:
        items.append(dict(id=entry_id(trace_anchor(mark.actor_index, mark.line)), entry_kind='agenda_change',
            **placed(None, steps.nearest(mark.wall), mark.wall, None), actor=mark.actor, **mark.fields))
    return items, anchors


def from_record(connection: sqlite3.Connection, steps: Steps, keys: dict[int, list[str]]) -> tuple[list[dict], list[tuple[float, int]]]:
    calls: dict[str, tuple] = {}
    loose = []
    for operation, wall, decision, actor, *call in connection.execute(
            'SELECT c.operation_id, c.wall, c.decision, c.actor, c.request_id, c.tool_call_id, c.tool, c.status, c.latency_ms, '
            'r.input_tokens, r.cache_read, r.cache_write, r.output_tokens FROM tool_calls c '
            'LEFT JOIN requests r ON r.actor = c.actor AND r.request_id = c.request_id ORDER BY c.wall, c.rowid'):
        if operation is not None and operation in steps.by_operation:
            calls.setdefault(operation, (decision, *call))
        else:
            loose.append((wall, decision, actor, tuple(call)))
    items = [dict(id=entry_id(s.seq), **recorded_step(s, keys, calls.get(s.operation_id))) for s in steps.rows]
    anchors = sorted((s.wall, s.seq) for s in steps.rows if s.wall is not None)
    attached: dict[int, int] = {}
    for wall, decision, actor, call in loose:  # a call that made no step (a knowledge read, a refusal)
        near = steps.nearest(wall)
        anchor = 0 if near is None else near.seq
        attached[anchor] = attached.get(anchor, 0) + 1
        request_id, tool_call_id, tool, status, latency, tokens, cache_read, cache_write, output = call
        known = [tokens, cache_read, cache_write]
        items.append(dict(id=entry_id(anchor, min(attached[anchor], FINDING_SUB - 1)), entry_kind='step',
            **placed(None, near, wall, decision), **dict(STEP_FIELDS, tool=tool, status=status, latency_ms=latency,
                request_id=request_id, tool_call_id=tool_call_id, actor=actor, input_tokens=tokens, cache_read=cache_read,
                prompt_tokens=None if any(v is None for v in known) else sum(known), cache_write=cache_write, output_tokens=output)))
    return items, anchors


def anchor_at(anchors: list[tuple[float, int]], wall: float | None) -> int:
    """The anchor of the latest entry at or before `wall` (0: before the first, or without a time)."""
    if wall is None or not anchors:
        return 0
    at = bisect_right(anchors, (wall, 1 << 62)) - 1
    return anchors[at][1] if at >= 0 else 0


def finding_identity(kind: str, start: int, source: str, payload: str) -> str:
    """What a finding states, and not the row it has now. Only findings that state the same thing share it."""
    stated = '' if kind in GROWING_FINDINGS else ':' + hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f'finding:{kind}:{start}:{source}{stated}'


def story_findings(connection: sqlite3.Connection, steps: Steps, anchors: list[tuple[float, int]]) -> list[dict]:
    """Findings with their identities, and with the places behind their anchors as `order`."""
    marks = ','.join('?' * len(STORY_FINDINGS))
    items: list[dict] = []
    attached: dict[int, int] = {}
    repeats: Counter = Counter()
    for identity, start, end, kind, source, payload in connection.execute(
            f'SELECT id, seq_start, seq_end, kind, source, payload FROM events WHERE kind IN ({marks}) ORDER BY seq_start, id',
            STORY_FINDINGS):
        step = steps.by_seq.get(start)
        near = step or next((s for s in reversed(steps.rows) if s.seq <= start), None)
        anchor = anchor_at(anchors, None if near is None else near.wall)
        attached[anchor] = attached.get(anchor, 0) + 1
        value = loads(payload) if len(payload) <= PAYLOAD_LIMIT else None
        logical = finding_identity(kind, start, source, payload)
        repeats[logical] += 1
        items.append(dict(id=logical if repeats[logical] == 1 else f'{logical}:{repeats[logical]}',
            order=entry_id(anchor, FINDING_SUB + attached[anchor]), entry_kind='finding',
            **placed(step, near, None if near is None else near.wall, None), finding_id=identity, finding_kind=kind,
            seq_end=end, source=source, payload=value if isinstance(value, dict) else {},
            payload_omitted=not isinstance(value, dict)))
    return items


def feed(info: RunInfo, connection: sqlite3.Connection, after: int, limit: int) -> dict:
    host = read(info)
    steps, keys = Steps(connection), step_keys(connection)
    items, anchors = from_host(host, steps, keys) if host is not None else from_record(connection, steps, keys)
    items.sort(key=lambda item: (item.get('order', item['id']), item['entry_kind']))
    # Two entries can only share a number past the room behind one anchor; the later takes the next free one. The IDs
    # are settled before any finding is placed, so no finding can change one.
    previous = -1
    for item in items:
        item['order'] = previous = max(item.get('order', item['id']), previous + 1)
        if isinstance(item['id'], int):
            item['id'] = item['order']
    items += story_findings(connection, steps, anchors)
    items.sort(key=lambda item: (item['order'], item['entry_kind'] == 'finding'))
    previous = -1
    for item in items:
        item['order'] = previous = max(item['order'], previous + 1)
    counts = {kind: 0 for kind in ('step', 'context_cut', 'coverage_wait', 'knowledge_delivery', 'agenda_change', 'finding')}
    for item in items:
        counts[item['entry_kind']] += 1
    rows, size = [], 0
    for item in items:
        if item['order'] <= after:
            continue
        size += len(json.dumps(item, separators=(',', ':'), default=str))
        if len(rows) > limit or (rows and size > PAGE_BYTES):
            break
        rows.append(item)
    result = page(rows, limit, lambda item: item['order'])
    if rows and result['next'] is None and rows[-1]['order'] < items[-1]['order']:
        result['next'] = rows[-1]['order']  # the page ended at its byte bound
    return dict(result, source='host_trace' if host is not None else 'evaluation_record', total=len(items), counts=counts)
