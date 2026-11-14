"""Facts from player-host/5 traces: decisions, cost, tool calls and host-side events.

Dollars here are the configured-rate estimate of each response (`usage.cost.total`), the one figure every run
carries. The cost the provider reported, which the host counts toward the dollar limit, is not read. An archived
player-host/3 trace gives the same facts: no field read here differs between the two versions.

Request ordinals are cumulative over the run's actors in directory order. They only index
the cumulative tokens and dollars of a step (the run's decision count comes from completed
input operations, see pipeline). An operation is attributed to the last operation-creating
tool call that started at or before its creation time on the same actor, which also covers
the child operations of a program run. Nothing here reads a game screen.

The same pass builds the `tool_calls` and `requests` rows of the record (one per tool call and
per HTTP attempt) and the host-side events: memory, program, refusal, eviction, handoff-adjacent
facts, custody stops (partial or unknown delivery only) and `run_end` (an orderly stop or a
player finish, which is not a custody stop).

`memory_reads` lists each memory read with the records it returned and the reading actor's calls before and
after it, for a reviewer who judges whether a delivered record was used. It judges nothing itself.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
import json
import math
import re
from typing import Callable, Sequence

from .records import EventRow, RequestRow, ToolCallRow
from .sources import HostEvent, MemoryFacts, Operation

CREATING_TOOLS = ('computer_input', 'computer_observe', 'player_handoff', 'player_program_run')
MEMORY_READ_TOOLS = ('player_memory_query', 'player_memory_read', 'player_memory_context', 'player_knowledge_read', 'player_knowledge_query')
LARGE_REWRITE_CACHE_TOKENS = 30_000
UNCERTAIN_DELIVERY = ('partial', 'unknown')


def _number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


@dataclass
class Request:
    key: str
    logical: str
    actor: str
    decision: int | None
    start_ms: float | None
    wall: float | None = None
    attempt: int = 1
    fetch_ms: float | None = None
    first_ms: float | None = None
    end_ms: float | None = None
    stop_reason: str | None = None
    usage_available: bool = False
    tokens: int | None = None
    dollars: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: float | None = None
    cache_write_dollars: float | None = None
    retry: bool = False
    retry_class: str | None = None
    aborted: bool = False
    manifest: bool = False

    @property
    def role(self) -> str:
        return 'recall' if self.key.startswith('recall-') else 'player'

    @property
    def completed(self) -> bool:
        return self.role == 'player' and self.end_ms is not None and self.stop_reason in ('stop', 'toolUse') and not self.aborted

    @property
    def non_tool_stop(self) -> bool:
        return self.role == 'player' and self.stop_reason is not None and self.stop_reason != 'toolUse'


@dataclass
class ToolCall:
    actor: str
    index: int
    wall: float | None
    line: int
    decision: int | None
    tool: str
    arguments: dict
    request_id: str | None = None
    tool_call_id: str | None = None
    start_ms: float | None = None
    end_ms: float | None = None
    result: object | None = None
    result_bytes: int | None = None
    error: bool = False
    refused: bool = False
    finished: bool = False

    @property
    def operation_id(self) -> str | None:
        value = self.result.get('operation_id') if isinstance(self.result, dict) else None
        return value if isinstance(value, str) else None


@dataclass
class HostFacts:
    actors: tuple[str, ...]
    requests: list[Request] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    estimates: dict[str, list[int]] = field(default_factory=dict)
    refusals: list[HostEvent] = field(default_factory=list)
    evictions: list[HostEvent] = field(default_factory=list)
    controls: list[HostEvent] = field(default_factory=list)
    finishes: list[HostEvent] = field(default_factory=list)
    settles: dict[str, HostEvent] = field(default_factory=dict)
    manifests: dict[str, list[dict]] = field(default_factory=dict)
    omitted: dict[tuple[str, str], int] = field(default_factory=dict)
    images: dict[tuple[str, str], int] = field(default_factory=dict)  # images the conversation held, kept or omitted
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

    def cumulative(self, decision: int | None) -> tuple[int, float]:
        if decision is None:return 0, 0.0
        if not self._prefix:
            total_tokens, total_dollars = 0, 0.0
            for request in self.requests:
                total_tokens += request.tokens or 0
                total_dollars += request.dollars or 0.0
                if request.decision is not None:
                    self._prefix[request.decision] = (total_tokens, total_dollars)
        keys = sorted(self._prefix) if self._keys is None else self._keys
        self._keys = keys
        at = bisect_right(keys, decision) - 1
        return self._prefix[keys[at]] if at >= 0 else (0, 0.0)

    def tool_rows(self) -> list[ToolCallRow]:
        """One row per tool call: `ok`, `error` (the result flagged an error) or `refused` (never dispatched).
        A call still in flight, or cut off without a result, has no row yet."""
        rows = []
        for call in self.calls:
            if call.request_id is None or call.tool_call_id is None or not (call.finished or call.refused):
                continue
            status = 'refused' if call.refused else 'error' if call.error else 'ok'
            latency = call.end_ms - call.start_ms if call.start_ms is not None and call.end_ms is not None \
                and call.end_ms >= call.start_ms else None
            rows.append(ToolCallRow(call.request_id, call.tool_call_id, call.actor, call.decision, call.tool, status,
                latency, call.result_bytes, call.wall, call.operation_id))
        return rows

    def request_rows(self) -> list[RequestRow]:
        return [RequestRow(r.key, r.actor, r.wall, r.attempt, r.input_tokens, r.cache_read_tokens,
            None if r.cache_write_tokens is None else int(r.cache_write_tokens), r.output_tokens, r.dollars, r.retry_class,
            self.omitted.get((r.actor, r.key)), 'exact' if r.manifest else 'absent') for r in self.requests]


def _text(result: object) -> object | None:
    """The value a tool result carries: its full operation record where the model read a short result (a computer
    observe, input or handoff recorded with `structuredContent`), else the JSON of its first text part (every earlier
    trace, and each result the model reads whole)."""
    if isinstance(result, dict) and isinstance(result.get('structuredContent'), dict):
        return result['structuredContent']
    if not isinstance(result, dict) or not isinstance(result.get('content'), list):
        return None
    for part in result['content']:
        if isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str):
            try:
                return json.loads(part['text'])
            except ValueError:
                return None
    return None


def _result_bytes(result: object) -> int | None:
    """UTF-8 size of the text a tool result adds to the player's context (image references excluded)."""
    if not isinstance(result, dict) or not isinstance(result.get('content'), list):
        return None
    return sum(len(part['text'].encode('utf-8')) for part in result['content']
        if isinstance(part, dict) and isinstance(part.get('text'), str))


def host_facts(actors: Sequence[str], host: dict[str, Sequence[HostEvent]]) -> HostFacts:
    facts = HostFacts(tuple(actors))
    offset = 0
    for actor in actors:
        by_key: dict[str, Request] = {}
        by_logical: dict[str, Request] = {}
        attempts: dict[str, int] = {}
        ordinals: dict[str, int] = {}
        open_calls: dict[tuple[object, object], ToolCall] = {}
        retries: set[object] = set()
        classes: dict[object, str] = {}
        calls = 0
        facts._starts[actor] = []
        facts.estimates[actor] = []
        facts.manifests[actor] = []

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
                if not key.startswith('recall-') and logical not in ordinals:
                    ordinals[logical] = len(ordinals) + 1
                attempts[logical] = attempts.get(logical, 0) + 1
                request = Request(key, logical, actor, None if key.startswith('recall-') else offset + ordinals[logical], event.monotonic_ms, event.wall,
                    attempts[logical], retry=key in retries, retry_class=classes.get(key))
                by_key[key] = by_logical[logical] = request
                facts.requests.append(request)
            elif kind == 'provider-retry':
                if fields.get('stage') == 'started':
                    # Emitted just before the retry attempt's own request-start.
                    retries.add(fields.get('request_id'))
                    if request_for(fields.get('request_id')) is not None:
                        request_for(fields.get('request_id')).retry = True
                elif fields.get('stage') == 'eligible' and isinstance(fields.get('retry_class'), str):
                    # The failed attempt carries the class; its own request-start is already recorded.
                    classes[fields.get('request_id')] = fields['retry_class']
                    failed = by_key.get(fields.get('request_id'))
                    if failed is not None:
                        failed.retry_class = fields['retry_class']
            elif kind == 'context-manifest':
                facts.manifests[actor].append(fields)
                request = by_key.get(fields.get('request_id'))
                if request is not None:
                    request.manifest = True
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
                        request.input_tokens = int(usage['input']) if _number(usage.get('input')) else None
                        request.output_tokens = int(usage['output']) if _number(usage.get('output')) else None
                        request.cache_read_tokens = int(usage['cacheRead']) if _number(usage.get('cacheRead')) else None
                        request.cache_write_tokens = usage.get('cacheWrite') if _number(usage.get('cacheWrite')) else None
                        request.cache_write_dollars = float(cost['cacheWrite']) if _number(cost.get('cacheWrite')) else None
            elif kind == 'tool-start':
                request = request_for(fields.get('request_id'))
                call = ToolCall(actor, calls, event.wall, event.line, request.decision if request else None,
                    str(fields.get('tool')), fields.get('arguments') if isinstance(fields.get('arguments'), dict) else {},
                    fields.get('request_id') if isinstance(fields.get('request_id'), str) else None,
                    fields.get('tool_call_id') if isinstance(fields.get('tool_call_id'), str) else None, event.monotonic_ms)
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
                    call.end_ms = event.monotonic_ms
                    call.error = isinstance(result, dict) and result.get('isError') is True
                    call.result = _text(result)
                    call.result_bytes = _result_bytes(result)
            elif kind == 'tool-refused':
                facts.refusals.append(event)
                call = open_calls.pop((fields.get('request_id'), fields.get('tool_call_id')), None)
                request = request_for(fields.get('request_id'))
                if call is None:
                    call = ToolCall(actor, calls, event.wall, event.line, request.decision if request else None,
                        str(fields.get('tool')), {}, fields.get('request_id') if isinstance(fields.get('request_id'), str) else None,
                        fields.get('tool_call_id') if isinstance(fields.get('tool_call_id'), str) else None, event.monotonic_ms)
                    calls += 1
                    facts.calls.append(call)
                call.refused = True
            elif kind == 'context-image-projection':
                if _number(fields.get('omitted_images')) and isinstance(fields.get('request_id'), str):
                    facts.omitted[(actor, fields['request_id'])] = int(fields['omitted_images'])
                if _number(fields.get('input_images')) and isinstance(fields.get('request_id'), str):
                    facts.images[(actor, fields['request_id'])] = int(fields['input_images'])
                if (_number(fields.get('omitted_images')) and fields['omitted_images'] > 0) or fields.get('blocked'):
                    facts.evictions.append(event)
            elif kind == 'context-estimate':
                if _number(fields.get('tokens')):
                    facts.estimates[actor].append(int(fields['tokens']))
            elif kind == 'control-accepted':
                facts.controls.append(event)
            elif kind == 'player-finish':
                facts.finishes.append(event)
            elif kind == 'settled':
                facts.settles[actor] = event
        facts._starts[actor].sort()
        facts._walls[actor] = [wall for wall, _ in facts._starts[actor]]
        offset += len(ordinals)
    return facts


def returned_records(call: ToolCall) -> list[dict]:
    """Records a memory read returned, in the order returned: a query's or a context's records, or the one record a
    read named."""
    value = call.result
    if isinstance(value, dict) and isinstance(value.get('records'), list):
        return [n for n in value['records'] if isinstance(n, dict) and isinstance(n.get('id'), str)]
    if isinstance(value, dict) and isinstance(value.get('id'), str):
        return [value]
    return []


def record_ids(call: ToolCall) -> list[str]:
    """IDs a memory read returned: one record, a query's records or a context's records."""
    return [n['id'] for n in returned_records(call)]


def typed_text(call: ToolCall) -> list[str]:
    """What one input call typed: the `text` actions of `computer_input`, in order. Key presses are not text."""
    actions = call.arguments.get('actions') if call.tool == 'computer_input' else None
    return [a['text'] for a in actions if isinstance(a, dict) and a.get('type') == 'text'
        and isinstance(a.get('text'), str)] if isinstance(actions, list) else []


def frame_source(call: ToolCall) -> str | None:
    """The source ID of the frame a computer call returned, for a reader who goes on to view it."""
    source = call.result.get('source') if isinstance(call.result, dict) else None
    return source['source_id'] if isinstance(source, dict) and isinstance(source.get('source_id'), str) else None


_WORD = re.compile(r'[^\W\d_]{3,}')


def names_record(text: str, record: dict) -> bool:
    """Whether every word of `text` occurs in the record's text or data. A word is three letters or more; two words
    match when they are equal or share their first five letters ("battery", "batteries"). It is a lexical pointer
    that knows nothing of the game: it finds where to look and decides nothing."""
    def words(value: str) -> set[str]:
        return set(_WORD.findall(value.casefold()))
    wanted = words(text)
    have = words(f"{record.get('text', '')} {json.dumps(record.get('data'), ensure_ascii=False)}")
    return bool(wanted) and all(any(w == h or len(w) >= 5 and w[:5] == h[:5] for h in have) for w in wanted)


@dataclass(frozen=True)
class RecordReference:
    """A later call of the reading actor that points at a returned record.

    `how` is `typed` (the call typed text that `names_record` finds in the record; `detail` is the text), `source`
    (it read a source the record cites; `detail` is the source ID) or `record` (a memory or handoff call named the
    record; `detail` is `supports`, `supersedes`, `read`, `context` or `handoff`). `repeated` says the actor had
    already typed that text, or read that source, before the memory read, so the read cannot be what prompted it.
    A reference is a place to look. It is not a finding that the record was used."""

    call: ToolCall
    record_id: str
    how: str
    detail: str
    repeated: bool


@dataclass(frozen=True)
class MemoryRead:
    """One memory read, what it returned and what its actor did around it.

    `request` is the actor's own request number (the N of its trace's `request-N`), of `actor_requests`. `held` holds
    the returned IDs the actor already had when it read: it wrote them, an earlier read of its own returned them, or
    the handoff context it started from carried them. `before` and `after` are the actor's other tool calls, in
    order; `after` runs to the end of its trace."""

    call: ToolCall
    request: int | None
    actor_requests: int
    records: tuple[dict, ...]
    held: frozenset[str]
    before: tuple[ToolCall, ...]
    after: tuple[ToolCall, ...]
    references: tuple[RecordReference, ...]


def _references(records: Sequence[dict], before: Sequence[ToolCall], after: Sequence[ToolCall]) -> list[RecordReference]:
    typed = {text.casefold() for call in before for text in typed_text(call)}
    sources = {call.arguments.get('source_id') for call in before if call.tool == 'player_source'}
    found = []
    for call in after:
        arguments = call.arguments
        written = arguments.get('record') if isinstance(arguments.get('record'), dict) else {}
        named = {  # how a memory or handoff call can name a record
            'supports': written.get('supports') if call.tool == 'player_memory_append' else None,
            'supersedes': [written.get('supersedes')] if call.tool == 'player_memory_append' else None,
            'read': [arguments.get('record_id')] if call.tool == 'player_memory_read' else None,
            'context': arguments.get('ids') if call.tool == 'player_memory_context' else None,
            'handoff': arguments.get('ids') if call.tool == 'player_handoff' else None}
        for record in records:
            for text in typed_text(call):
                if names_record(text, record):
                    found.append(RecordReference(call, record['id'], 'typed', text, text.casefold() in typed))
            cited = record.get('sources') if isinstance(record.get('sources'), list) else ()
            if call.tool == 'player_source' and arguments.get('source_id') in cited:
                found.append(RecordReference(call, record['id'], 'source', arguments['source_id'],
                    arguments['source_id'] in sources))
            for detail, ids in named.items():
                if isinstance(ids, list) and record['id'] in ids:
                    found.append(RecordReference(call, record['id'], 'record', detail, False))
    return found


def memory_reads(facts: HostFacts, carry: dict[str, frozenset[str]] | None = None) -> list[MemoryRead]:
    """Every finished memory read (`MEMORY_READ_TOOLS`) of a run, in actor and call order.

    `carry` is `sources.read_carry`: the IDs each handing-off actor's context carried. An actor starts holding what
    the actor before it carried. A failed, refused or unfinished read is not listed, as in `host_events`. Nothing
    here reads a game screen or judges use: it lists what a reviewer needs in order to judge it."""
    received = {taker: (carry or {}).get(giver, frozenset()) for giver, taker in zip(facts.actors, facts.actors[1:])}
    spans: dict[str, tuple[int, int]] = {}
    for request in facts.requests:
        if request.role == 'recall':continue
        low, high = spans.get(request.actor, (request.decision, request.decision))
        spans[request.actor] = (min(low, request.decision), max(high, request.decision))
    calls: dict[str, list[ToolCall]] = {}
    for call in facts.calls:
        calls.setdefault(call.actor, []).append(call)
    reads = []
    for actor in facts.actors:
        held = set(received.get(actor, ()))
        first, last = spans.get(actor, (1, 0))
        for position, call in enumerate(calls.get(actor, ())):
            if not call.finished or call.error or call.refused:
                continue
            value = call.result if isinstance(call.result, dict) else {}
            if call.tool == 'player_memory_append' and isinstance(value.get('id'), str):
                held.add(value['id'])
            if call.tool not in MEMORY_READ_TOOLS:
                continue
            records = tuple(returned_records(call))
            ids = {record['id'] for record in records}
            before, after = tuple(calls[actor][:position]), tuple(calls[actor][position + 1:])
            reads.append(MemoryRead(call, None if call.decision is None else call.decision - first + 1,
                last - first + 1, records, frozenset(held & ids), before, after,
                tuple(_references(records, before, after))))
            held |= ids
    return reads


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
        if not call.finished or call.error or call.refused:
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
        if call.tool != 'player_program_run' or not call.finished or call.error or call.refused:
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
        if event.fields.get('delivery') in UNCERTAIN_DELIVERY:  # a custody fence: delivery of the refused call is unknown
            events.append(EventRow(seq, seq, 'custody_stop', 'harness', None, dict(actor=event.actor,
                cause='fence', tool=event.fields.get('tool'), delivery=event.fields.get('delivery'))))
    for event in facts.evictions:
        seq = resolve(event.wall)
        fields = event.fields
        events.append(EventRow(seq, seq, 'context_eviction', 'harness', None, dict(actor=event.actor,
            omitted_images=fields.get('omitted_images'), retained_images=fields.get('retained_images'),
            blocked=bool(fields.get('blocked')))))
    # run_end: a player finish, or an accepted orderly stop the actor never finished. Neither is a custody stop.
    finished = {e.actor for e in facts.finishes}
    for event in facts.finishes:
        seq = resolve(event.wall)
        orderly = any(c.actor == event.actor and c.fields.get('control_id') == event.fields.get('control_id')
            for c in facts.controls) if event.fields.get('control_id') else False
        events.append(EventRow(seq, seq, 'run_end', 'harness', None, dict(actor=event.actor,
            reason=event.fields.get('disposition'), control_id=event.fields.get('control_id'), orderly_stop=orderly)))
    for event in facts.controls:
        if event.actor not in finished:
            seq = resolve(event.wall)
            events.append(EventRow(seq, seq, 'run_end', 'harness', None, dict(actor=event.actor, reason='orderly_stop',
                control_id=event.fields.get('control_id'), orderly_stop=True)))
    return events
