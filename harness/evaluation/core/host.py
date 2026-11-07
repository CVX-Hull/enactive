"""Facts from player-host/3 traces: decisions, cost, tool calls and host-side events.

Request ordinals are cumulative over the run's actors in directory order. They only index
the cumulative tokens and dollars of a step (the run's decision count comes from completed
input operations, see pipeline). An operation is attributed to the last operation-creating
tool call that started at or before its creation time on the same actor, which also covers
the child operations of a program run. Nothing here reads a game screen.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
import json
import math
from typing import Callable, Sequence

from .records import EventRow
from .sources import HostEvent, MemoryFacts, Operation

CREATING_TOOLS = ('computer_input', 'computer_observe', 'player_handoff', 'player_program_run')
MEMORY_READ_TOOLS = ('player_memory_query', 'player_memory_read', 'player_memory_context')
LARGE_REWRITE_CACHE_TOKENS = 30_000


def _number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


@dataclass
class Request:
    key: str
    logical: str
    actor: str
    decision: int
    start_ms: float | None
    fetch_ms: float | None = None
    first_ms: float | None = None
    end_ms: float | None = None
    stop_reason: str | None = None
    usage_available: bool = False
    tokens: int | None = None
    dollars: float | None = None
    cache_write_tokens: float | None = None
    cache_write_dollars: float | None = None
    retry: bool = False
    aborted: bool = False

    @property
    def completed(self) -> bool:
        return self.end_ms is not None and self.stop_reason in ('stop', 'toolUse') and not self.aborted

    @property
    def non_tool_stop(self) -> bool:
        return self.stop_reason is not None and self.stop_reason != 'toolUse'


@dataclass
class ToolCall:
    actor: str
    index: int
    wall: float | None
    line: int
    decision: int | None
    tool: str
    arguments: dict
    result: object | None = None
    error: bool = False
    finished: bool = False


@dataclass
class HostFacts:
    actors: tuple[str, ...]
    requests: list[Request] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    estimates: dict[str, list[int]] = field(default_factory=dict)
    refusals: list[HostEvent] = field(default_factory=list)
    evictions: list[HostEvent] = field(default_factory=list)
    controls: list[HostEvent] = field(default_factory=list)
    _starts: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    _prefix: dict[int, tuple[int, float]] = field(default_factory=dict)
    _keys: list[int] | None = None
    _walls: dict[str, list[float]] = field(default_factory=dict)

    @property
    def present(self) -> bool:
        return bool(self.requests)

    def accounting(self, operation: Operation) -> tuple[int | None, int | None, float | None]:
        """(decision, cumulative tokens, cumulative dollars) of the request that issued `operation`."""
        starts = self._starts.get(operation.actor)
        if not starts:
            return None, None, None
        at = bisect_right(self._walls[operation.actor], operation.created_wall) - 1
        if at < 0:
            return None, None, None
        decision = starts[at][1]
        tokens, dollars = self.cumulative(decision)
        return decision, tokens, dollars

    def cumulative(self, decision: int) -> tuple[int, float]:
        if not self._prefix:
            per: dict[int, tuple[int, float]] = {}
            for request in self.requests:
                tokens, dollars = per.get(request.decision, (0, 0.0))
                per[request.decision] = (tokens + (request.tokens or 0), dollars + (request.dollars or 0.0))
            total_tokens, total_dollars = 0, 0.0
            for key in sorted(per):
                total_tokens += per[key][0]
                total_dollars += per[key][1]
                self._prefix[key] = (total_tokens, total_dollars)
        keys = sorted(self._prefix) if self._keys is None else self._keys
        self._keys = keys
        at = bisect_right(keys, decision) - 1
        return self._prefix[keys[at]] if at >= 0 else (0, 0.0)


def _text(result: object) -> object | None:
    if not isinstance(result, dict) or not isinstance(result.get('content'), list):
        return None
    for part in result['content']:
        if isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str):
            try:
                return json.loads(part['text'])
            except ValueError:
                return None
    return None


def host_facts(actors: Sequence[str], host: dict[str, Sequence[HostEvent]]) -> HostFacts:
    facts = HostFacts(tuple(actors))
    offset = 0
    for actor in actors:
        by_key: dict[str, Request] = {}
        by_logical: dict[str, Request] = {}
        ordinals: dict[str, int] = {}
        open_calls: dict[tuple[object, object], ToolCall] = {}
        retries: set[object] = set()
        calls = 0
        facts._starts[actor] = []
        facts.estimates[actor] = []

        def request_for(key: object) -> Request | None:
            return by_key.get(key) or by_logical.get(key)  # type: ignore[arg-type]

        for event in host.get(actor, ()):
            fields = event.fields
            kind = event.type
            if kind == 'request-start':
                key = fields.get('request_id')
                logical = fields.get('logical_request_id') or key
                if not isinstance(key, str):
                    continue
                if logical not in ordinals:
                    ordinals[logical] = len(ordinals) + 1
                request = Request(key, logical, actor, offset + ordinals[logical], event.monotonic_ms, retry=key in retries)
                by_key[key] = by_logical[logical] = request
                facts.requests.append(request)
            elif kind == 'provider-retry' and fields.get('stage') == 'started':
                # Emitted just before the retry attempt's own request-start.
                retries.add(fields.get('request_id'))
                if request_for(fields.get('request_id')) is not None:
                    request_for(fields.get('request_id')).retry = True
            elif kind in ('request-fetch-start', 'response-first-chunk', 'response-complete', 'abort'):
                request = request_for(fields.get('request_id'))
                if request is None:
                    continue
                if kind == 'request-fetch-start':
                    request.fetch_ms = event.monotonic_ms
                elif kind == 'response-first-chunk':
                    request.first_ms = event.monotonic_ms
                elif kind == 'abort':
                    request.aborted = True
                else:
                    request.end_ms = event.monotonic_ms
                    request.stop_reason = fields.get('stop_reason')
                    usage = fields.get('usage')
                    if fields.get('usage_available') is True and isinstance(usage, dict):
                        request.usage_available = True
                        request.tokens = int(sum(usage[k] for k in ('input', 'output', 'cacheRead', 'cacheWrite')
                            if _number(usage.get(k))))
                        cost = usage.get('cost') if isinstance(usage.get('cost'), dict) else {}
                        request.dollars = float(cost['total']) if _number(cost.get('total')) else None
                        request.cache_write_tokens = usage.get('cacheWrite') if _number(usage.get('cacheWrite')) else None
                        request.cache_write_dollars = float(cost['cacheWrite']) if _number(cost.get('cacheWrite')) else None
            elif kind == 'tool-start':
                request = request_for(fields.get('request_id'))
                call = ToolCall(actor, calls, event.wall, event.line, request.decision if request else None,
                    str(fields.get('tool')), fields.get('arguments') if isinstance(fields.get('arguments'), dict) else {})
                calls += 1
                open_calls[(fields.get('request_id'), fields.get('tool_call_id'))] = call
                facts.calls.append(call)
                if call.tool in CREATING_TOOLS and event.wall is not None and call.decision is not None:
                    facts._starts[actor].append((event.wall, call.decision))
            elif kind == 'tool-result':
                call = open_calls.pop((fields.get('request_id'), fields.get('tool_call_id')), None)
                if call is not None:
                    result = fields.get('result')
                    call.finished = True
                    call.error = isinstance(result, dict) and result.get('isError') is True
                    call.result = _text(result)
            elif kind == 'tool-refused':
                facts.refusals.append(event)
            elif kind == 'context-image-projection':
                if (_number(fields.get('omitted_images')) and fields['omitted_images'] > 0) or fields.get('blocked'):
                    facts.evictions.append(event)
            elif kind == 'context-estimate':
                if _number(fields.get('tokens')):
                    facts.estimates[actor].append(int(fields['tokens']))
            elif kind == 'control-accepted':
                facts.controls.append(event)
        facts._starts[actor].sort()
        facts._walls[actor] = [wall for wall, _ in facts._starts[actor]]
        offset += len(ordinals)
    return facts


def record_ids(call: ToolCall) -> list[str]:
    """IDs a memory read returned: one record, a query's records or a context's records."""
    value = call.result
    if isinstance(value, dict) and isinstance(value.get('records'), list):
        return [n['id'] for n in value['records'] if isinstance(n, dict) and isinstance(n.get('id'), str)]
    if isinstance(value, dict) and isinstance(value.get('id'), str):
        return [value['id']]
    return []


def seq_resolver(walls: Sequence[tuple[int, float]]) -> Callable[[float | None], int]:
    """Map a wall time to the sequence of the last step at or before it (0 before the first)."""
    ordered = sorted(walls, key=lambda pair: pair[1])
    times = [wall for _, wall in ordered]

    def resolve(wall: float | None) -> int:
        if wall is None or not ordered:
            return ordered[0][0] if ordered else 0
        at = bisect_right(times, wall) - 1
        return ordered[at][0] if at >= 0 else ordered[0][0]
    return resolve


def host_events(facts: HostFacts, resolve: Callable[[float | None], int],
                memory: MemoryFacts | None) -> list[EventRow]:
    """Core events that come from the host trace and the memory store."""
    events: list[EventRow] = []
    saved_by: dict[str, str] = {}
    for call in facts.calls:
        if not call.finished or call.error:
            continue
        seq = resolve(call.wall)
        value = call.result if isinstance(call.result, dict) else {}
        if call.tool == 'player_memory_append' and isinstance(value.get('id'), str):
            events.append(EventRow(seq, seq, 'memory_write', 'player_claim', None, dict(actor=call.actor,
                record_id=value['id'], record_kind=value.get('kind'), supports=len(value.get('supports') or ()),
                sources=len(value.get('sources') or ()), call=call.index)))
        elif call.tool in MEMORY_READ_TOOLS:
            events.append(EventRow(seq, seq, 'memory_read', 'harness', None, dict(actor=call.actor, tool=call.tool,
                record_ids=record_ids(call), call=call.index)))
        elif call.tool == 'player_program_save' and isinstance(value.get('id'), str):
            saved_by[value['id']] = call.actor
            events.append(EventRow(seq, seq, 'program_save', 'player_claim', None, dict(actor=call.actor,
                program_id=value['id'], parent_id=value.get('parent_id'), call=call.index)))
    for call in facts.calls:
        if call.tool != 'player_program_run' or not call.finished or call.error:
            continue
        seq = resolve(call.wall)
        value = call.result if isinstance(call.result, dict) else {}
        program_id = value.get('program_id') or call.arguments.get('program_id')
        author = saved_by.get(program_id)
        if author is None and memory is not None and program_id in memory.programs:
            author = memory.programs[program_id].get('actor_id')
        events.append(EventRow(seq, seq, 'program_run', 'harness', None, dict(actor=call.actor, program_id=program_id,
            status=value.get('status'), run_id=value.get('run_id'), author=author,
            reused=None if author is None else author != call.actor, call=call.index)))
    for event in facts.refusals:
        seq = resolve(event.wall)
        events.append(EventRow(seq, seq, 'tool_refused', 'harness', None, dict(actor=event.actor,
            tool=event.fields.get('tool'), reason=event.fields.get('reason'), delivery=event.fields.get('delivery'))))
    for event in facts.evictions:
        seq = resolve(event.wall)
        fields = event.fields
        events.append(EventRow(seq, seq, 'context_eviction', 'harness', None, dict(actor=event.actor,
            omitted_images=fields.get('omitted_images'), retained_images=fields.get('retained_images'),
            blocked=bool(fields.get('blocked')))))
    for event in facts.controls:
        seq = resolve(event.wall)
        events.append(EventRow(seq, seq, 'custody_stop', 'harness', None, dict(actor=event.actor, cause='orderly_stop',
            control_id=event.fields.get('control_id'))))
    return events
