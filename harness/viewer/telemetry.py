"""Read-only projections of a run's host traces and curator spend (docs/contracts/spectator-view.md).

`read` parses every `actors/*/host.jsonl` with the one offline trace parser (`harness.evaluation.core.sources`) and
keeps only the bounded values the view routes show; the parse is cached per state of the trace files. Every file is
opened from the run directory down without following a symlink, and read up to the 16 MiB input limit. A run without
readable traces, or with one that is larger, a symlink or damaged, has no projection (`None`): nothing is guessed from a
trace this reader does not support.

Player and recall dollars are the provider's own decimal text and curator dollars its proxy's, each summed exactly. The
configured-rate estimate is a separate field and never stands in for either.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Context, Decimal, InvalidOperation
import io
import json
import math
from pathlib import Path
import sqlite3
import stat
import threading
from typing import Any

from harness.evaluation.core.host import HostFacts, ToolCall, host_facts
from harness.evaluation.core.metrics import nearest_rank
from harness.evaluation.core.records import EvaluationError
from harness.evaluation.core.sources import HostEvent, is_delivered_exposure, read_host, run_archive_entry

from .catalog import ID_LIMIT, RunInfo
from .curator import read_file, read_rooted, rooted_entries, rooted_status

#: Sums are exact: no provider amount here approaches this many digits.
EXACT = Context(prec=200)
LABEL_LIMIT = 128
ENDPOINT_LIMIT = 50
TRIGGER_LIMIT = 10
MAX_POINTS = 2000
MAX_CUTS = 1000
CLOSE_SCHEMA = 'curator-proxy-close/1'
GROOMING_SCHEMA = 'curator-boundary-grooming/2'
GROOMING_STATUSES = ('completed', 'failed', 'skipped')
SESSIONS = ('curator-runner', 'sessions')
UNKNOWN_ENDPOINT = 'unknown'
#: `context-cut` outcomes as the host writes them, and as the view names them.
CUT_OUTCOMES = {'cut': 'applied', 'held-back': 'held_back'}
CUT_RESULTS = ('target', 'best_effort', 'rescue')
CUT_DETAIL_FIELDS = ('cut_result', 'cumulative_removed_turns', 'briefing_tokens', 'source_ids_count')
RESERVE_AMOUNTS = ('spent_usd', 'spend_limit_usd', 'finish_reserve_usd', 'unpriced_bound_usd')
TAIL_NOTICE_KINDS = ('context-capacity', 'host-timeout', 'spend-limit')


def count(value: object) -> int | None:
    """A non-negative count; a whole-valued float is one too (the trace's numbers are JSON)."""
    if type(value) is int and value >= 0:
        return value
    return int(value) if type(value) is float and math.isfinite(value) and value >= 0 and value.is_integer() else None


def identifier(value: object, limit: int = ID_LIMIT) -> str | None:
    """An identifier is whole or absent; it is never shortened into another one."""
    return value if isinstance(value, str) and 0 < len(value) <= limit else None


def usd(value: object) -> Decimal | None:
    """A finite, non-negative decimal written as text, as the host and the proxy write it."""
    if not isinstance(value, str) or len(value) > 128:
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() and amount >= 0 and abs(amount.adjusted()) < 60 else None


def usd_sum(amounts: Iterable[Decimal]) -> Decimal:
    total = Decimal(0)
    for amount in amounts:
        total = EXACT.add(total, amount)
    return total


def usd_text(amount: Decimal) -> str:
    """Plain decimal digits without an exponent or trailing zeros (`0E-7` is `0`)."""
    text = format(amount, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


@dataclass(frozen=True)
class Response:
    actor: str
    line: int
    request_id: str
    wall: float | None
    is_recall: bool
    prompt_tokens: int | None
    input_tokens: int | None
    cache_read: int | None
    cache_write: int | None
    output_tokens: int | None
    reported_provider: str | None
    reported_usd: Decimal | None
    spent_usd: Decimal | None
    estimated_dollars: float | None


@dataclass(frozen=True)
class Mark:
    """A projected trace event with its actor, trace position and wall time."""
    actor: str
    actor_index: int
    line: int
    wall: float | None
    fields: dict


@dataclass
class HostProjection:
    actors: tuple[str, ...] = ()
    directories: dict[str, str] = field(default_factory=dict)  # `actors/NNN` directory name -> actor ID
    lines: dict[str, int] = field(default_factory=dict)        # actor ID -> its index in directory order
    responses: list[Response] = field(default_factory=list)
    by_request: dict[tuple[str, str], Response] = field(default_factory=dict)
    calls: list[ToolCall] = field(default_factory=list)
    refusals: dict[tuple[str, str | None, str | None], str] = field(default_factory=dict)
    cuts: list[Mark] = field(default_factory=list)
    spend_reserves: list[Mark] = field(default_factory=list)
    tail_notice_events: int = 0
    tail_notice_kinds: Counter = field(default_factory=Counter)
    updates: list[Mark] = field(default_factory=list)
    briefings: list[Mark] = field(default_factory=list)
    settled: dict[str, dict] = field(default_factory=dict)
    starts: dict[str, Counter] = field(default_factory=dict)   # actor ID -> request starts by role
    unpriced: dict[str, Counter] = field(default_factory=dict)  # actor ID -> starts without a priced response, by role
    unmatched: dict[str, int] = field(default_factory=dict)    # actor ID -> responses that no start accounts for
    untraced: tuple[str, ...] = ()    # actor directories without a trace
    latest_version: str | None = None
    prices_recorded: bool = False     # some response carries a provider cost field; an older trace has none
    endpoints_recorded: bool = False  # likewise for the answering endpoint's label


def _tokens(usage: dict, key: str) -> int | None:
    return count(usage.get(key))


def _response(actor: str, event: HostEvent) -> Response | None:
    f = event.fields
    request_id = identifier(f.get('request_id'))
    if request_id is None:
        return None
    usage = f.get('usage') if f.get('usage_available') is True and isinstance(f.get('usage'), dict) else {}
    parts = [_tokens(usage, key) for key in ('input', 'cacheRead', 'cacheWrite')]
    cost = usage.get('cost') if isinstance(usage.get('cost'), dict) else {}
    total = cost.get('total')
    return Response(actor, event.line, request_id, event.wall, request_id.startswith('recall-'),
        None if not usage or any(p is None for p in parts) else sum(parts), *parts, _tokens(usage, 'output'),
        identifier(f.get('reported_provider'), LABEL_LIMIT), usd(f.get('reported_cost_usd')), usd(f.get('spent_usd')),
        float(total) if type(total) in (int, float) and math.isfinite(total) and total >= 0 else None)


def cut_fields(f: dict) -> dict:
    triggers = f.get('triggers') if isinstance(f.get('triggers'), list) else []
    result = f.get('cut_result')
    return dict(request_id=identifier(f.get('request_id')), outcome=CUT_OUTCOMES.get(identifier(f.get('outcome')), 'unknown'),
        reason=identifier(f.get('reason')), knowledge_version=identifier(f.get('knowledge_version')),
        triggers=[t for t in (identifier(v, LABEL_LIMIT) for v in triggers[:TRIGGER_LIMIT]) if t is not None],
        cut_result=result if result in CUT_RESULTS else None,
        **{key: count(f.get(key)) for key in ('tokens_before', 'tokens_after', 'images_before', 'images_after', 'removed_turns',
            'cumulative_removed_turns', 'briefing_tokens', 'source_ids_count')})


#: The rows of an update's text that state a difference; from an empty store the host writes `index` in their place.
DIFFERENCE = ('added', 'updated', 'removed')


def update_fields(f: dict) -> dict:
    """One newer version during play. The counts are those of the text the player received; a refused update, or one
    whose text does not parse, has unknown (null) counts, never zero."""
    counts: dict[str, int | None] = dict.fromkeys(DIFFERENCE)
    added_articles = added_facts = None
    text = f.get('text')
    from_empty = False
    if isinstance(text, str):
        try:
            stated = json.loads(text.split('\n')[1])
        except (ValueError, IndexError, RecursionError):
            stated = None
        if isinstance(stated, dict):
            from_empty = isinstance(stated.get('index'), list) and not any(isinstance(stated.get(k), list) for k in DIFFERENCE)
            rows = dict(added=stated['index'], updated=[], removed=[]) if from_empty else stated
            counts = {key: len(rows[key]) if isinstance(rows.get(key), list) else None for key in DIFFERENCE}
            if not from_empty and counts['added'] is not None and isinstance(f.get('article_ids'), list):
                articles = {v for v in f['article_ids'] if isinstance(v, str)}
                added_articles = sum(isinstance(r, dict) and isinstance(r.get('id'), str) and r['id'] in articles for r in rows['added'])
                added_facts = counts['added'] - added_articles
    if from_empty:
        words = [f"first version · {counts['added']} {'entry' if counts['added'] == 1 else 'entries'}"]
    elif added_articles is not None:
        words = [f"+{n} {noun}{'' if n == 1 else 's'}" for n, noun in ((added_articles, 'article'), (added_facts, 'fact')) if n]
    else:
        words = [f"+{counts['added']} added"] if counts['added'] else []
    words += [f'{sign}{counts[key]} {key}' for key, sign in (('updated', '~'), ('removed', '−')) if counts[key]]
    if not words and counts['added'] is not None:
        words = ['no entries changed']
    coverage = f.get('coverage') if isinstance(f.get('coverage'), dict) else {}
    return dict(knowledge_version=identifier(f.get('version')), previous_version=identifier(f.get('previous_version')),
        outcome=identifier(f.get('outcome')), reason=identifier(f.get('reason')),
        request_id=identifier(f.get('receiving_player_request_id')), added_count=counts['added'],
        updated_count=counts['updated'], removed_count=counts['removed'], added_articles=added_articles,
        added_facts=added_facts, covered_step=count(coverage.get('last_step')),
        summary=' · '.join(words) if words else None)


def role(request_id: object) -> str:
    return 'recall' if isinstance(request_id, str) and request_id.startswith('recall-') else 'player'


def project(actors: list[tuple[str, str, tuple[HostEvent, ...]]], untraced: tuple[str, ...] = ()) -> HostProjection:
    """`actors` is (directory name, actor ID, events) in directory order; `untraced` names the directories without any."""
    out = HostProjection(tuple(a for _, a, _ in actors), {d: a for d, a, _ in actors},
        {a: index for index, (_, a, _) in enumerate(actors)}, untraced=untraced)
    facts: HostFacts = host_facts(out.actors, {a: events for _, a, events in actors})
    out.calls = facts.calls
    for index, (_, actor, events) in enumerate(actors):
        host_telemetry = (events[0].fields.get('telemetry_version')
            if events and events[0].type == 'host-start' and type(events[0].fields.get('telemetry_version')) is int else None)
        # By request ID (None: not an identifier): attempts started, answered, and answered with a provider's price.
        started: Counter = Counter()
        answered: Counter = Counter()
        priced: Counter = Counter()
        for event in events:
            f = event.fields
            if event.type == 'request-start':
                started[identifier(f.get('request_id'))] += 1
            elif event.type == 'response-complete':
                out.prices_recorded |= 'reported_cost_usd' in f
                out.endpoints_recorded |= 'reported_provider' in f
                response = _response(actor, event)
                answered[None if response is None else response.request_id] += 1
                if response is not None:
                    priced[response.request_id] += response.reported_usd is not None
                    out.responses.append(response)
                    out.by_request[(actor, response.request_id)] = response
            elif event.type == 'context-cut':
                out.cuts.append(Mark(actor, index, event.line, event.wall, cut_fields(f)))
            elif event.type == 'spend-reserve-reached':
                amounts = {key: usd(f.get(key)) for key in RESERVE_AMOUNTS}
                out.spend_reserves.append(Mark(actor, index, event.line, event.wall, dict(
                    actor_id=identifier(f.get('actor_id')),
                    **{key: None if amount is None else usd_text(amount) for key, amount in amounts.items()})))
            elif event.type == 'tail-notice':
                out.tail_notice_events += 1
                kinds = f.get('kinds')
                if isinstance(kinds, list):
                    out.tail_notice_kinds.update(kind for kind in kinds if kind in TAIL_NOTICE_KINDS)
            elif event.type == 'knowledge-delivery':
                delivered = is_delivered_exposure(f, host_telemetry)
                if f.get('kind') == 'update':
                    out.updates.append(Mark(actor, index, event.line, event.wall, update_fields(f)))
                elif f.get('kind') == 'briefing' and delivered:
                    out.briefings.append(Mark(actor, index, event.line, event.wall, dict(
                        request_id=identifier(f.get('receiving_player_request_id')) or identifier(f.get('request_id')),
                        knowledge_version=identifier(f.get('version')))))
                if delivered and f.get('kind') in ('briefing', 'update'):
                    out.latest_version = identifier(f.get('version')) or out.latest_version
            elif event.type == 'tool-refused':
                reason = identifier(f.get('reason'), 1024)
                if reason is not None:
                    out.refusals[(actor, identifier(f.get('request_id')), identifier(f.get('tool_call_id')))] = reason
            elif event.type == 'settled':
                out.settled[actor] = {key: f.get(key) for key in
                    ('player_requests', 'recall_requests', 'spent_usd', 'unpriced_requests', 'unpriced_recall_requests')}
        out.starts[actor], out.unpriced[actor] = Counter(), Counter()
        for request_id, number in started.items():
            out.starts[actor][role(request_id)] += number
            out.unpriced[actor][role(request_id)] += max(0, number - priced[request_id])
        out.unmatched[actor] = sum(max(0, number - started[request_id]) for request_id, number in answered.items())
    return out


_lock = threading.Lock()
_cache: dict[Path, tuple[tuple, HostProjection | None]] = {}
CACHED_RUNS = 8


class Captured:
    """Bytes already read, in place of the path the trace parser opens."""

    def __init__(self, name: str, data: bytes) -> None:
        self.name, self.data = name, data

    def open(self, mode: str) -> io.BytesIO:
        return io.BytesIO(self.data)

    def __str__(self) -> str:
        return self.name


def _actor_directories(run_dir: Path) -> list[str]:
    """Every actor directory. A symlink counts as one, so that it is read, and refused, rather than passed over."""
    return [name for name, status in rooted_entries(run_dir, 'actors') if stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode)]


def _state(status: Any) -> tuple | None:
    return None if status is None else (status.st_mode, status.st_ino, status.st_mtime_ns, status.st_size)


def _project_run(info: RunInfo, run_dir: Path, directories: list[str]) -> HostProjection | None:
    entry = run_archive_entry(run_dir)
    actors, untraced = [], []
    for name in directories:
        state, _, data = read_rooted(run_dir, 'actors', name, 'host.jsonl')
        if state in ('missing', 'empty'):
            untraced.append(name)
            continue
        if state != 'available':
            raise EvaluationError(f'actors/{name}/host.jsonl: {state}')
        captured: Any = Captured(f'actors/{name}/host.jsonl', data)
        actor, events = read_host(captured, name, entry)
        session = events[0].fields.get('session')
        if session is not None and session != info.session:
            raise EvaluationError(f'{captured}: the trace belongs to another session')
        actors.append((name, actor, events))
    if len({actor for _, actor, _ in actors}) != len(actors):
        raise EvaluationError('an actor appears in two host traces')
    return project(actors, tuple(untraced)) if actors else None


def read(info: RunInfo) -> HostProjection | None:
    """The run's host projection, or None when it has no trace this reader supports. One parse per state of the
    trace files: the page polls several routes that share it."""
    if info.run_dir is None:
        return None
    run_dir = info.run_dir
    with _lock:
        try:
            directories = _actor_directories(run_dir)
        except OSError:
            return None
        stamp = tuple((name, _state(rooted_status(run_dir, 'actors', name, 'host.jsonl'))) for name in directories)
        cached = _cache.get(run_dir)
        if cached is not None and cached[0] == (info.session, stamp):
            return cached[1]
        projection: HostProjection | None
        try:
            projection = _project_run(info, run_dir, directories)
        except (OSError, EvaluationError):
            projection = None
        _cache.pop(run_dir, None)
        _cache[run_dir] = ((info.session, stamp), projection)
        while len(_cache) > CACHED_RUNS:
            _cache.pop(next(iter(_cache)))
        return projection


# Steps as seen from the trace -----------------------------------------------------------------------

@dataclass(frozen=True)
class Step:
    seq: int
    operation_id: str
    actor: str
    wall: float | None
    decision: int | None
    game_time: int | None
    mode: str | None
    source_id: str | None


class Steps:
    """The run's evaluated steps: by operation, by actor-local ordinal, and by nearest wall time."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.rows = [Step(*row) for row in connection.execute(
            'SELECT seq, operation_id, actor, wall, decision, game_time, mode, source_id FROM steps ORDER BY seq')]
        self.by_operation = {s.operation_id: s for s in self.rows}
        self.by_seq = {s.seq: s for s in self.rows}
        placed = sorted((s.wall, s.seq) for s in self.rows if s.wall is not None)
        self._walls, self._seqs = [w for w, _ in placed], [q for _, q in placed]
        self._ordinals: dict[str, list[Step]] = {}

    def nearest(self, wall: float | None) -> Step | None:
        """The latest step at or before `wall`; None before the first, never a step that had not happened yet."""
        at = -1 if wall is None else bisect_right(self._walls, wall) - 1
        return self.by_seq[self._seqs[at]] if at >= 0 else None

    def ordinal(self, actor: str, number: int) -> Step | None:
        """An actor's `number`-th operation, in the order a trace numbers them (creation wall, operation ID)."""
        if actor not in self._ordinals:
            self._ordinals[actor] = sorted((s for s in self.rows if s.actor == actor),
                key=lambda s: (s.wall or 0.0, s.operation_id))
        rows = self._ordinals[actor]
        return rows[number - 1] if 1 <= number <= len(rows) else None


# Summary and telemetry ------------------------------------------------------------------------------

def endpoints(host: HostProjection) -> dict[str, int]:
    if not host.endpoints_recorded:
        return {}
    counts = Counter(r.reported_provider or UNKNOWN_ENDPOINT for r in host.responses)
    return dict(counts.most_common(ENDPOINT_LIMIT))


def latest_provider(host: HostProjection) -> str | None:
    """The endpoint that answered last, by the responses' own times."""
    if not host.responses or not host.endpoints_recorded:
        return None
    last = max(enumerate(host.responses),
        key=lambda item: (-math.inf if item[1].wall is None else item[1].wall, item[0]))[1]
    return last.reported_provider or UNKNOWN_ENDPOINT


def spend(host: HostProjection) -> dict:
    """Provider-reported spend of the player and recall requests. `spend_complete` is true only when every actor
    directory has a trace, every actor has settled, its settlement agrees with the events read here, and every request
    started has a priced response. A settlement that claims fewer unpriced requests than the events show is not
    believed: the larger count stands. A trace that records no provider cost has unknown (null) completeness and
    unpriced counts."""
    reported = [r.reported_usd for r in host.responses if r.reported_usd is not None]
    spent: list[Decimal] = []
    totals: dict[str, Any] = dict(player_requests=0, recall_requests=0, unpriced_requests=0, unpriced_recall_requests=0)
    complete = not host.untraced
    for actor in host.actors:
        mine = [r for r in host.responses if r.actor == actor]
        settled = host.settled.get(actor)
        observed = dict(player_requests=host.starts[actor]['player'], recall_requests=host.starts[actor]['recall'],
            unpriced_requests=host.unpriced[actor]['player'], unpriced_recall_requests=host.unpriced[actor]['recall'])
        total = None if settled is None else usd(settled['spent_usd'])
        stated = {} if settled is None else {key: count(settled[key]) for key in totals}
        if (settled is not None and settled['spent_usd'] is None and not any(host.starts[actor].values())
                and not mine and not any(v for v in stated.values() if v)):
            continue  # a host that settled before it started made no request and states no totals
        own = usd_sum(r.reported_usd for r in mine if r.reported_usd is not None)
        for key in totals:
            value = stated.get(key)
            if value is None or (key.startswith('unpriced') and value < observed[key]):
                value = observed[key]
            totals[key] += value
        if (settled is None or total != own or any(stated[key] != observed[key] for key in totals)
                or any(host.unpriced[actor].values()) or host.unmatched[actor]):
            complete = False
        if total is None:
            total = next((r.spent_usd for r in reversed(mine) if r.spent_usd is not None), None)
        if total is not None:
            spent.append(total)
    if not host.prices_recorded:
        totals.update(unpriced_requests=None, unpriced_recall_requests=None)
    return dict(reported_cost_usd=usd_text(usd_sum(reported)) if reported else None,
        spent_usd=usd_text(usd_sum(spent)) if spent else None, **totals,
        spend_complete=complete if host.prices_recorded else None)


def token_summary(host: HostProjection) -> dict:
    """Prompt sizes are the player's own requests; the cache share is over every response with usage, recall included."""
    prompts = [r.prompt_tokens for r in host.responses if not r.is_recall and r.prompt_tokens is not None]
    used = [r for r in host.responses if r.prompt_tokens is not None]
    total = sum(r.prompt_tokens for r in used)
    return dict(latest_prompt_tokens=prompts[-1] if prompts else None,
        p50_prompt_tokens=int(nearest_rank(prompts, .5)) if prompts else None,
        max_prompt_tokens=max(prompts) if prompts else None,
        cache_hit_share=sum(r.cache_read or 0 for r in used) / total if total else None)


def tail_notice_summary(host: HostProjection | None) -> dict:
    return dict(count=host.tail_notice_events if host is not None else 0,
        by_kind={kind: host.tail_notice_kinds[kind] if host is not None else 0 for kind in TAIL_NOTICE_KINDS})


def summary(host: HostProjection | None) -> dict | None:
    if host is None:
        return None
    applied = [c for c in host.cuts if c.fields['outcome'] == 'applied']
    latest = None
    if applied:
        mark = applied[-1]
        latest = dict({key: mark.fields[key] for key in ('request_id', 'knowledge_version', 'tokens_before', 'tokens_after',
            'images_before', 'images_after', 'removed_turns', 'triggers', *CUT_DETAIL_FIELDS)}, wall_time=mark.wall)
    by_result = Counter(mark.fields['cut_result'] for mark in applied)
    reserve = host.spend_reserves[-1] if host.spend_reserves else None
    return dict(**spend(host), response_by_endpoint=endpoints(host), latest_provider=latest_provider(host),
        context_cuts=dict(applied=len(applied), held_back=sum(c.fields['outcome'] == 'held_back' for c in host.cuts),
            latest=latest, by_result={result: by_result[result] for result in CUT_RESULTS}),
        spend_reserve_reached=dict(count=len(host.spend_reserves),
            latest=None if reserve is None else dict(actor=reserve.actor, wall_time=reserve.wall, **reserve.fields)),
        tail_notices=tail_notice_summary(host),
        knowledge_updates=dict(count=sum(u.fields['outcome'] == 'delivered' for u in host.updates), latest_version=host.latest_version),
        token_summary=token_summary(host))


def _kept(total: int, always: set[int]) -> list[int]:
    """At most `MAX_POINTS` indexes: an even stride, with the points a marker needs and the last one kept."""
    if total <= MAX_POINTS:
        return list(range(total))
    stride = math.ceil(total / (MAX_POINTS // 2))
    chosen = set(range(0, total, stride)) | {total - 1}
    for index in sorted(always):
        if len(chosen) >= MAX_POINTS:
            break
        chosen.add(index)
    return sorted(chosen)


def telemetry(info: RunInfo, connection: sqlite3.Connection) -> dict:
    host = read(info)
    steps = Steps(connection)

    def seq(wall: float | None) -> int | None:
        step = steps.nearest(wall)
        return None if step is None else step.seq

    cuts: list[dict] = []
    reserves = host.spend_reserves if host is not None else []
    if host is not None:
        rows = [dict(request_id=r.request_id, actor=r.actor, seq=seq(r.wall), wall=r.wall, prompt_tokens=r.prompt_tokens,
            cache_read=r.cache_read, cache_write=r.cache_write, output_tokens=r.output_tokens,
            reported_provider=r.reported_provider, reported_cost_usd=None if r.reported_usd is None else usd_text(r.reported_usd),
            estimated_dollars=r.estimated_dollars, is_recall=r.is_recall) for r in host.responses]
        # A request that was retried answers more than once; a cut belongs to its first answer.
        position: dict[tuple[str, str], int] = {}
        for index, r in enumerate(host.responses):
            position.setdefault((r.actor, r.request_id), index)
        cuts = [dict(**mark.fields, index=position.get((mark.actor, mark.fields['request_id'])),
            seq=seq(mark.wall)) for mark in host.cuts]
        money, by_endpoint = spend(host), endpoints(host)
    else:
        rows = []
        for request_id, actor, wall, tokens, cache_read, cache_write, output, dollars in connection.execute(
                'SELECT request_id, actor, wall, input_tokens, cache_read, cache_write, output_tokens, dollars FROM requests ORDER BY rowid'):
            known = [tokens, cache_read, cache_write]
            rows.append(dict(request_id=request_id, actor=actor, seq=seq(wall), wall=wall,
                prompt_tokens=None if any(v is None for v in known) else sum(known), cache_read=cache_read, cache_write=cache_write,
                output_tokens=output, reported_provider=None, reported_cost_usd=None, estimated_dollars=dollars,
                is_recall=request_id.startswith('recall-')))
        money, by_endpoint = {}, {}
    marked = {c['index'] + offset for c in cuts if c['index'] is not None and c['outcome'] == 'applied'
        for offset in (-1, 0) if c['index'] + offset >= 0}
    kept = _kept(len(rows), marked)
    curator = curator_spend(info) or {}
    return dict(source='host_trace' if host is not None else 'evaluation_record',
        requests=[dict(index=i, **rows[i]) for i in kept], requests_total=len(rows), requests_omitted=len(rows) - len(kept),
        cuts=cuts[-MAX_CUTS:], cuts_omitted=max(0, len(cuts) - MAX_CUTS), response_by_endpoint=by_endpoint,
        spend_reserve_reached=[dict(actor=mark.actor, seq=seq(mark.wall), wall=mark.wall, **mark.fields)
            for mark in reserves[-MAX_CUTS:]],
        spend_reserve_reached_omitted=max(0, len(reserves) - MAX_CUTS), tail_notices=tail_notice_summary(host),
        spend=dict(player_reported_usd=money.get('reported_cost_usd'), player_estimated_usd=info.dollars,
            spend_limit_usd=info.facts.get('spend_allowance_usd'), spend_complete=money.get('spend_complete'),
            unpriced_requests=money.get('unpriced_requests'), unpriced_recall_requests=money.get('unpriced_recall_requests'),
            curator_spent_usd=curator.get('spent_usd'), curator_spend_complete=curator.get('spend_complete'),
            curator_sessions_settled=curator.get('sessions_settled'), curator_sessions_total=curator.get('sessions_total')))


# Curator spend ---------------------------------------------------------------------------------------

def _document(read: tuple) -> tuple[str, Any]:
    """(status, the JSON value) of a file read; `malformed` where its bytes are not JSON."""
    state, _, data = read
    if state != 'available':
        return state, None
    try:
        return state, json.loads(data.decode('utf-8'))
    except (ValueError, UnicodeError, RecursionError):
        return 'malformed', None


def _closure(run_dir: Path, session: tuple[str, str]) -> dict | None:
    _, value = _document(read_rooted(run_dir, *SESSIONS, *session, 'proxy-close.json'))
    if (not isinstance(value, dict) or value.get('schema') != CLOSE_SCHEMA or type(value.get('settled')) is not bool
            or count(value.get('unsettled_requests')) is None or usd(value.get('spent_snapshot_usd')) is None):
        return None
    return value


def _ledger(run_dir: Path, session: tuple[str, str]) -> tuple[Decimal | None, int]:
    """(priced charges, rows without one) of a proxy ledger; a partly written last line counts as neither. A ledger that
    cannot be read states no amount (None), which is not a measured zero; an empty one states zero."""
    state, _, data = read_rooted(run_dir, *SESSIONS, *session, 'proxy-ledger.jsonl')
    if state == 'empty':
        return Decimal(0), 0
    if state != 'available':
        return None, 0
    amounts, unpriced = [], 0
    for line in data.split(b'\n')[:-1]:
        try:
            row = json.loads(line.decode('utf-8')) if line.strip() else None
        except (ValueError, UnicodeError, RecursionError):
            row = {}
        if row is None:
            continue
        amount = usd(row.get('charged')) if isinstance(row, dict) else None
        if amount is None:
            unpriced += 1
        else:
            amounts.append(amount)
    if not amounts and unpriced:
        return None, unpriced
    return usd_sum(amounts), unpriced


def _groups(run_dir: Path) -> list[tuple[str, Any]]:
    try:
        return rooted_entries(run_dir, *SESSIONS)
    except OSError:
        return []


def session_groups(info: RunInfo) -> list[str]:
    """The admission names the run's curator runner gave it, one per group of sessions."""
    return [] if info.run_dir is None else [name for name, status in _groups(info.run_dir) if stat.S_ISDIR(status.st_mode)]


def curator_spend(info: RunInfo) -> dict | None:
    """What the run's live curator sessions spent by their proxy's accounting: each session's closing snapshot, or the
    charged rows of its ledger while it has none. None without a session. `spend_complete` needs every session closed
    and settled with nothing left open; `spent_usd` is None when no session states an amount."""
    if info.run_dir is None:
        return None
    sessions: list[tuple[str, str]] = []
    unread = 0     # what may hold a session and could not be listed, or is a symlink
    for group, status in _groups(info.run_dir):
        if stat.S_ISDIR(status.st_mode):
            try:
                members = rooted_entries(info.run_dir, *SESSIONS, group)
            except OSError:
                unread += 1
                continue
            sessions += [(group, name) for name, kind in members if stat.S_ISDIR(kind.st_mode) or stat.S_ISLNK(kind.st_mode)]
        elif stat.S_ISLNK(status.st_mode):
            unread += 1
    if not sessions:
        return None
    settled, open_requests, amounts = 0, 0, []
    for session in sessions:
        closure = _closure(info.run_dir, session)
        if closure is None:
            amount, unpriced = _ledger(info.run_dir, session)
            if amount is not None:
                amounts.append(amount)
            open_requests += unpriced
            continue
        amounts.append(usd(closure['spent_snapshot_usd']) or Decimal(0))
        open_requests += closure['unsettled_requests']
        settled += closure['settled'] and closure['unsettled_requests'] == 0
    return dict(sessions_total=len(sessions), sessions_settled=settled, sessions_unsettled=len(sessions) - settled,
        spent_usd=usd_text(usd_sum(amounts)) if amounts else None, unsettled_requests=open_requests,
        spend_complete=settled == len(sessions) and open_requests == 0 and unread == 0)


def boundary_grooming(info: RunInfo, path: Path | None) -> dict:
    """The configured boundary grooming receipt, for the run it names. Grooming runs after an admission ends and writes
    outside its package, so without a receipt the run's own files say nothing of what it spent."""
    blank = dict(source_status='not_configured', status=None, reason=None, spent_usd=None, spend_complete=None,
        published_before=None, published_after=None)
    if path is None:
        return blank
    state, value = _document(read_file(path))
    if state != 'available':
        return dict(blank, source_status=state)
    if (not isinstance(value, dict) or value.get('schema') != GROOMING_SCHEMA or value.get('status') not in GROOMING_STATUSES
            or identifier(value.get('run')) is None or 'cost_usd' not in value
            or (value['cost_usd'] is not None and usd(value['cost_usd']) is None)):
        return dict(blank, source_status='unsupported')
    # The receipt names the admission as the curator did; a run without curator sessions has only its own names.
    if value['run'] not in {info.session, *(session_groups(info) or [info.run])}:
        return dict(blank, source_status='other_run')
    amount = None if value['cost_usd'] is None else usd(value['cost_usd'])
    proxy = value.get('proxy') if isinstance(value.get('proxy'), dict) else {}
    closed = value['status'] == 'skipped' or (proxy.get('settled') is True and count(proxy.get('unsettled_requests')) == 0)
    return dict(source_status='available', status=value['status'], reason=identifier(value.get('reason')),
        spent_usd=None if amount is None else usd_text(amount), spend_complete=amount is not None and closed,
        published_before=identifier(value.get('published_before'), 64), published_after=identifier(value.get('published_after'), 64))
