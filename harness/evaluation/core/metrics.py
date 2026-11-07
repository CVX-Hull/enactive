"""Metrics, version 1 (docs/contracts/evaluation.md).

Every row stores `count` and `denominator` (NULL only where the contract's denominator is
"—") and the name of the missing-data rule that applied. A `value` is a plain number where
the metric has one figure, and an object `{"value": ..., "excluded": n, ...}` where
abstentions or missing usage were excluded and counted. Decisions are logical model
completed computer_input operations (see derive.decision_ranks); rates that need a decision
use the last legible step of each decision. Decisions before the first in-play frame are setup: they are
counted separately and excluded from mode, stall, pace and needs rates.
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, Sequence

from .binding import Binding
from .derive import (READER_FRAME, READER_INPUT, STALL_DECISIONS, Timeline, out_of_play_streaks, receipt_uncertain,
    unit_seconds)
from .host import HostFacts, LARGE_REWRITE_CACHE_TOKENS
from .records import EventRow, MetricRow
from .sources import EndFacts, Operation

VERSION = 1
INSUFFICIENT = 5
LOST_REASONS = ('infrastructure', 'custody')


def nearest_rank(values: Sequence[float], fraction: float) -> float | None:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)] if ordered else None


def _row(name: str, value: Any, count: int | None, denominator: float | None, missing: str | None = None,
         key: str = '') -> MetricRow:
    return MetricRow(name, VERSION, value, count, denominator, missing, key)


def censor_reason(died: bool, events: Sequence[EventRow], facts: HostFacts, end: EndFacts) -> str | None:
    """Why a run's survival observation ended. First match wins:

    1. `died`: a death event in the survival episode (or after it).
    2. `owner_pause`: the gateway's `watch-terminal.json` records a forwarded Pause or a pause reason.
    3. `custody`: a `custody_stop` event (partial or unknown delivery, or a custody fence).
    4. `infrastructure`: the last actor's host settled unsuccessfully (a provider error), from the host
       trace or `receipt.json`.
    5. `player_stop`: the last player finish was `cannot_continue` or `task_complete`.
    6. `budget`: an orderly stop was requested (a `control-accepted` host event, or an ending request in
       `receipt.json`), or the last actor settled with a handoff that no successor continued (hosts exhausted).
    Otherwise None: the run is still live, or its end is not recorded."""
    if died:
        return 'died'
    if end.paused:
        return 'owner_pause'
    if any(e.kind == 'custody_stop' for e in events):
        return 'custody'
    last = end.settled[-1] if end.settled else (facts.settles[facts.actors[-1]].fields
        if facts.actors and facts.actors[-1] in facts.settles else None)
    if last is not None and last.get('ok') is False:
        return 'infrastructure'
    finishes = [e.fields.get('disposition') for e in facts.finishes] or [d for d in end.finishes if d]
    if finishes and finishes[-1] in ('cannot_continue', 'task_complete'):
        return 'player_stop'
    if facts.controls or end.ending_trigger:
        return 'budget'
    if last is not None and last.get('reason') == 'handoff':
        return 'budget'
    if finishes:
        return 'player_stop'
    return None


def survival(timeline: Timeline, events: Sequence[EventRow], binding: Binding, facts: HostFacts,
             end: EndFacts) -> tuple[MetricRow, float | None, str | None]:
    """Survival within the last episode that has an accepted in-play clock reading."""
    clock = timeline.clock
    if not any(value is not None for value in clock):
        return _row('survival.game_hours', None, 0, None, 'no_clock_reading'), None, None
    start, episode = timeline.survival_start, timeline.play_episode
    if start is None or episode is None:
        return _row('survival.game_hours', None, sum(v is not None for v in clock), None, 'no_in_play_clock'), None, None
    span = timeline.episode_range(episode)
    readable = [i for i in span if clock[i] is not None]
    hours = (clock[readable[-1]] - clock[start]) * unit_seconds(binding) / 3600
    first_seq = timeline.steps[episode.start].seq
    died = any(e.kind == 'death' and e.seq_start >= first_seq for e in events)
    reason = censor_reason(died, events, facts, end)
    return _row('survival.game_hours', dict(hours=hours, outcome='died' if died else 'censored', censor_reason=reason,
        start_game_time=clock[start], end_game_time=clock[readable[-1]], episode=episode.index,
        episodes=len(timeline.episodes)), len(readable), None), hours, reason


def compute_metrics(timeline: Timeline, operations: Sequence[Operation], events: Sequence[EventRow],
                    facts: HostFacts, binding: Binding, carry: Mapping[str, frozenset[str]],
                    human_rungs: frozenset[str] = frozenset(), external: Mapping[str, Any] | None = None,
                    end: EndFacts | None = None) -> list[MetricRow]:
    """All metric rows for one run. `external` carries plain numbers computed elsewhere from the
    existing host and control summaries: `response_ms` and `first_chunk_ms` (lists) and
    `custody` (`{"receipts": n, "uncertain": n}`). Multi-valued metrics (per reader, percentile, status,
    tool, record kind or handoff) are one row per member, named by `key`."""
    external = external or {}
    end = end or EndFacts()
    steps, frames = timeline.steps, timeline.frames
    factor = unit_seconds(binding)
    rows: list[MetricRow] = []
    survival_row, hours, reason = survival(timeline, events, binding, facts, end)
    rows.append(survival_row)
    lost = int(reason in LOST_REASONS)
    rows.append(_row('run.infrastructure_loss', lost, lost, 1, None if reason is not None else 'end_not_recorded'))
    no_host = None if facts.present else 'no_host_trace'

    # Decisions and setup.
    decision_indices, abstained = timeline.decision_rows()
    play = [i for i in decision_indices if timeline.first_in_play is None or i >= timeline.first_in_play]
    setup = len(decision_indices) - len(play)

    # pace.*
    pairs = []
    last = None
    for index, value in enumerate(timeline.clock):
        if value is None:
            continue
        if last is not None and timeline.episode_of[last] == timeline.episode_of[index] \
                and (timeline.first_in_play is None or last >= timeline.first_in_play):
            seconds = (value - timeline.clock[last]) * factor
            decisions = timeline.ranks[index] - timeline.ranks[last]
            if decisions > 0 and seconds < binding.long_activity_seconds:
                pairs.append(seconds / decisions)
        last = index
    enough = len(pairs) >= INSUFFICIENT
    rows.append(_row('pace.routine_seconds_per_decision', statistics.median(pairs) if enough else None, len(pairs),
        len(pairs), None if enough else 'insufficient_intervals'))
    long_events = [e for e in events if e.kind == 'long_activity']
    rows.append(_row('pace.long_activities', dict(count=len(long_events),
        total_game_seconds=sum(e.payload['seconds'] for e in long_events)), len(long_events), None))
    priced = [r for r in facts.requests if r.dollars is not None]
    dollars = sum(r.dollars for r in priced)
    if not facts.present:
        rows.append(_row('pace.dollars_per_game_hour', None, 0, hours, no_host))
    elif not hours:
        rows.append(_row('pace.dollars_per_game_hour', None, len(priced), hours, 'zero_game_hours'))
    else:
        rows.append(_row('pace.dollars_per_game_hour', dollars / hours, len(priced), hours))

    # mode.*, stall.*
    out = sum(1 for i in play if frames[i].mode != 'in_play')
    rows.append(_row('mode.out_of_play_share', dict(value=out / len(play) if play else None, excluded=abstained,
        setup_decisions=setup), out, len(play), 'abstentions_excluded' if abstained else ('no_mode_readings' if not play else None)))
    streaks = [s for s in out_of_play_streaks(timeline) if not s.setup]
    rows.append(_row('stall.longest', max((s.length for s in streaks), default=0), None, len(play)))
    stalls = sum(1 for s in streaks if s.length >= STALL_DECISIONS)
    rows.append(_row('stall.count', stalls, stalls, len(play)))

    # input.*
    inputs = [i for i, s in enumerate(steps) if s.kind == 'input']
    actions = sum(sum(1 for a in timeline.actions[i] or () if a != 'wait') for i in inputs)
    returned = sum(1 for i in inputs if steps[i].source_id is not None)
    rows.append(_row('input.actions_per_call', actions / len(inputs) if inputs else None, actions, len(inputs),
        None if inputs else 'no_input_operations'))
    rows.append(_row('input.unseen_action_share', 1 - returned / actions if actions else None, max(0, actions - returned),
        actions, None if actions else 'no_actions'))
    comparable = [i for i in inputs if steps[i].frame_changed is not None]
    unchanged = sum(1 for i in comparable if not steps[i].frame_changed)
    skipped = len(inputs) - len(comparable)
    rows.append(_row('input.frame_unchanged_rate', dict(value=unchanged / len(comparable) if comparable else None,
        excluded=skipped), unchanged, len(comparable), 'no_capture_excluded' if skipped else None))
    custody = external.get('custody')
    if custody is None:
        receipts = [r for op in operations for r in op.receipts]
        custody = dict(receipts=len(receipts), uncertain=sum(1 for r in receipts if receipt_uncertain(r)))
    ended = int(any(e.kind == 'custody_stop' for e in events))
    rows.append(_row('input.uncertain_deliveries', dict(value=custody['uncertain'] + ended,
        uncertain_receipts=custody['uncertain'], runs_ended=ended), custody['uncertain'] + ended, custody['receipts']))

    # memory.*, programs.*
    writes = [e for e in events if e.kind == 'memory_write']
    reads = [e for e in events if e.kind == 'memory_read']
    rows.append(_row('memory.writes', len(writes) if facts.present else None, len(writes), None, no_host))
    rows.append(_row('memory.reads', len(reads) if facts.present else None, len(reads), None, no_host))
    previous_actor = {actor: facts.actors[i - 1] for i, actor in enumerate(facts.actors) if i > 0}
    beyond = 0
    for actor in facts.actors:
        returned_ids = {r for e in reads if e.payload['actor'] == actor for r in e.payload['record_ids']}
        beyond += len(returned_ids - carry.get(previous_actor.get(actor, ''), frozenset()))
    rows.append(_row('memory.retrieved_beyond_carry', beyond / len(writes) if writes else None, beyond, len(writes),
        None if writes else ('no_writes' if facts.present else no_host)))
    calls = {actor: sum(1 for c in facts.calls if c.actor == actor and not c.refused) for actor in facts.actors}
    late = sum(1 for e in writes if e.payload['call'] >= calls[e.payload['actor']] - 6)
    rows.append(_row('memory.late_write_share', late / len(writes) if writes else None, late, len(writes),
        None if writes else ('no_writes' if facts.present else no_host)))
    saves = [e for e in events if e.kind == 'program_save']
    runs = [e for e in events if e.kind == 'program_run']
    outcomes: dict[str, int] = {}
    for e in runs:
        outcomes[str(e.payload['status'])] = outcomes.get(str(e.payload['status']), 0) + 1
    rows.append(_row('programs.saved', len(saves) if facts.present else None, len(saves), None, no_host))
    rows.append(_row('programs.run', len(runs) if facts.present else None, len(runs), None, no_host))
    reused = sum(1 for e in runs if e.payload['reused'])
    rows.append(_row('programs.reused', reused if facts.present else None, reused, None, no_host))
    if not facts.present or not outcomes:
        rows.append(_row('programs.outcomes', None if not facts.present else 0, len(runs), None,
            no_host or 'no_program_runs'))
    for status in sorted(outcomes):
        rows.append(_row('programs.outcomes', outcomes[status], outcomes[status], len(runs), key=status))
    kinds: dict[str, int] = {}
    for e in writes:
        kinds[str(e.payload['record_kind'])] = kinds.get(str(e.payload['record_kind']), 0) + 1
    if not kinds:
        rows.append(_row('memory.records', None if not facts.present else 0, 0, 0, no_host or 'no_writes'))
    for kind in sorted(kinds):
        rows.append(_row('memory.records', kinds[kind], kinds[kind], len(writes), key=kind))

    # handoff.*
    index_of = {s.seq: k for k, s in enumerate(steps)}
    handoffs = [(index_of[e.seq_start], e) for e in events if e.kind == 'handoff' and e.seq_start in index_of]
    resume: list[int | None] = []
    for index, _ in handoffs:
        found = next((j for j in range(index + 1, len(steps)) if steps[j].kind == 'input' and steps[j].frame_changed
            and sum(1 for a in timeline.actions[j] or () if a != 'wait') >= 3), None)
        resume.append(None if found is None else timeline.ranks[found] - timeline.ranks[index])
    resolved = [v for v in resume if v is not None]
    rows.append(_row('handoff.decisions_to_resume', dict(value=statistics.median(resolved) if resolved else None,
        excluded=len(resume) - len(resolved)), len(resolved), len(handoffs),
        'unresolved_excluded' if len(resolved) < len(handoffs) else None))
    for k, value in enumerate(resume):
        rows.append(_row('handoff.decisions_to_resume', value, int(value is not None), 1,
            None if value is not None else 'unresolved', key=str(k)))
    ratios: list[float | None] = []
    for _, event in handoffs:
        actor = event.payload['actor']
        position = facts.actors.index(actor) if actor in facts.actors else None
        before = facts.estimates.get(actor) if position is not None else None
        after = facts.estimates.get(facts.actors[position + 1]) if position is not None and position + 1 < len(facts.actors) else None
        ratios.append(after[0] / before[-1] if before and after and before[-1] else None)
    ratio_values = [v for v in ratios if v is not None]
    rows.append(_row('handoff.carry_ratio', dict(value=statistics.median(ratio_values) if ratio_values else None,
        excluded=len(ratios) - len(ratio_values)), len(ratio_values), len(handoffs),
        'unresolved_excluded' if len(ratio_values) < len(handoffs) else None))
    for k, value in enumerate(ratios):
        rows.append(_row('handoff.carry_ratio', value, int(value is not None), 1,
            None if value is not None else 'unresolved', key=str(k)))

    # host.*
    input_count = len(inputs)
    unknown_usage = sum(1 for r in facts.requests if not r.usage_available)
    rows.append(_row('host.dollars_per_decision', dict(value=dollars / input_count if input_count and facts.present else None,
        excluded=unknown_usage), len(priced), input_count, no_host or ('missing_usage_excluded' if unknown_usage else None)))
    cache = sum(r.cache_write_dollars or 0.0 for r in priced)
    rows.append(_row('host.cache_write_share', cache / dollars if dollars else None,
        sum(1 for r in priced if r.cache_write_dollars), dollars, None if dollars else (no_host or 'zero_dollars')))
    large = [r for r in priced if (r.cache_write_tokens or 0) > LARGE_REWRITE_CACHE_TOKENS]
    rows.append(_row('host.large_rewrite_share', sum(r.dollars for r in large) / dollars if dollars else None,
        len(large), dollars, None if dollars else (no_host or 'zero_dollars')))
    response = external.get('response_ms')
    if response is None:
        response = [r.end_ms - r.start_ms for r in facts.requests if r.completed and r.start_ms is not None and r.end_ms >= r.start_ms]
    first = external.get('first_chunk_ms')
    if first is None:
        first = [r.first_ms - r.fetch_ms for r in facts.requests if r.first_ms is not None and r.fetch_ms is not None
            and r.first_ms >= r.fetch_ms]
    figures = lambda values: dict(n=len(values), p50=nearest_rank(values, .5), p95=nearest_rank(values, .95))  # noqa: E731
    for series, values in (('response', response), ('first_chunk', first)):
        stats = figures(values)
        for percentile in ('p50', 'p95'):
            rows.append(_row('host.latency', stats[percentile], len(values), len(facts.requests),
                None if values else (no_host or 'no_samples'), key=f'{series}.{percentile}'))
    flagged = [r for r in facts.requests if r.retry or r.aborted or r.non_tool_stop]
    rows.append(_row('host.retry_share', dict(value=len(flagged) / len(facts.requests) if facts.requests else None,
        retries=sum(r.retry for r in facts.requests), aborts=sum(r.aborted for r in facts.requests),
        non_tool_stops=sum(r.non_tool_stop for r in facts.requests)), len(flagged), len(facts.requests), no_host))

    # needs.*
    in_play = [i for i in play if frames[i].mode == 'in_play']
    with_vitals = [i for i in in_play if frames[i].vitals]
    severe = sum(1 for i in with_vitals if any(v.critical for v in frames[i].vitals))
    rows.append(_row('needs.severe_share', dict(value=severe / len(with_vitals) if with_vitals else None,
        excluded=len(in_play) - len(with_vitals)), severe, len(with_vitals),
        'abstentions_excluded' if len(in_play) > len(with_vitals) else ('no_vital_readings' if not with_vitals else None)))

    # ladder.reached
    reached = {e.payload['rung']: e for e in events if e.kind == 'milestone'}
    rungs, highest, human_missing = [], None, False
    for rung in binding.ladder:
        entry: dict[str, Any] = dict(id=rung.id, evidence=rung.evidence)
        if rung.evidence == 'human':
            entry['status'] = 'confirmed' if rung.id in human_rungs else 'not_assessed'
            human_missing |= rung.id not in human_rungs
        elif rung.id in reached:
            entry.update(status='reached', seq=reached[rung.id].seq_start,
                decisions=reached[rung.id].payload['decisions_to_reach'], clocks=reached[rung.id].payload['clocks'])
        else:
            entry['status'] = 'not_reached'
        if entry['status'] in ('reached', 'confirmed'):
            highest = rung.id
        rungs.append(entry)
    rows.append(_row('ladder.reached', dict(highest=highest, rungs=rungs),
        sum(1 for r in rungs if r['status'] in ('reached', 'confirmed')), len(rungs), 'human_rungs_not_assessed' if human_missing else None))

    # reader.coverage.<reader>
    captured = [s.seq for s in steps if s.source_id is not None]
    names = sorted({r for seq in captured for r in timeline.readings.get(seq, {})} - {READER_INPUT})
    for name in names:
        good = sum(1 for seq in captured if (row := timeline.readings.get(seq, {}).get(name)) is not None and row.abstain is None)
        rows.append(_row('reader.coverage', good / len(captured), good, len(captured), key=name))
    if not names:
        rows.append(_row('reader.coverage', None, 0, 0, 'no_frames', key=READER_FRAME))

    # tools.calls, one row per tool: calls with their refusals and error results
    per_tool: dict[str, dict[str, int]] = {}
    for call in facts.calls:
        entry = per_tool.setdefault(call.tool, dict(calls=0, refused=0, errors=0))
        entry['calls'] += 1
        entry['refused'] += int(call.refused)
        entry['errors'] += int(call.error)
    total_calls = len(facts.calls)
    for tool in sorted(per_tool):
        rows.append(_row('tools.calls', per_tool[tool], per_tool[tool]['calls'], total_calls, key=tool))
    zoomed = sum(1 for c in facts.calls if c.tool == 'player_source' and 'zoom' in c.arguments)
    rows.append(_row('tools.calls', zoomed if facts.present else None, zoomed, per_tool.get('player_source', {}).get('calls', 0),
        no_host, key='player_source+zoom'))
    if not per_tool:
        rows.append(_row('tools.calls', None, 0, 0, no_host or 'no_calls'))
    return rows
