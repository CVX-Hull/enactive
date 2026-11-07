"""Derived quantities: game-time plausibility guard, decisions and the core event kinds.

Everything here is a pure function of the stored record rows plus the binding's
readings, so a pass can be repeated over a growing run and gives the same answer as one
pass over the finished run. The core keeps three readers of its own beside the
binding's: `frame` (the normalised FrameReading), `input` (what each input operation
asked for) and `map_change` (fraction of changed map pixels versus the previous capture).
`game_time` is the guarded clock and is rewritten on every pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from .binding import DEATH_CAUSES, Binding, FrameReading, Reading, Vital
from .records import CORE_VERSION, EvaluationError, EventRow, ReadingRow, StepRow
from .sources import Operation

READER_FRAME = 'core.frame'
READER_INPUT = 'core.input'
READER_CLOCK = 'core.game_time'
READER_MAP = 'core.map_change'
CORE_READERS = (READER_FRAME, READER_INPUT, READER_CLOCK, READER_MAP)

STALL_DECISIONS = 15
STUCK_INPUTS = 3
STUCK_CHANGE = 0.01
PIXEL_DELTA = 16
VITAL_STEP = 0.25
NO_FRAME = FrameReading('unknown', None, None, (), None, None, False, ())


UNIT_SECONDS = {'second': 1, 'seconds': 1, 'minute': 60, 'minutes': 60, 'hour': 3600, 'hours': 3600}


def unit_seconds(binding: Binding) -> int:
    try:
        return UNIT_SECONDS[binding.game_time_unit]
    except KeyError:
        raise EvaluationError(f'binding {binding.binding_id}: unsupported game time unit {binding.game_time_unit!r}') from None


def max_jump(binding: Binding) -> float:
    """The binding's maximum plausible clock jump, in the binding's own game-time unit."""
    return binding.max_clock_jump_seconds / unit_seconds(binding)


def frame_summary(frame: FrameReading) -> dict:
    return dict(mode=frame.mode, game_time=frame.game_time, identity=frame.identity,
        vitals=[dict(name=v.name, scope=v.scope, value=v.value, critical=v.critical) for v in frame.vitals],
        threat=frame.threat, threat_count=frame.threat_count, death=frame.death)


def frame_from_summary(summary: dict, readings: tuple[Reading, ...] = ()) -> FrameReading:
    return FrameReading(summary['mode'], summary['game_time'], summary['identity'],
        tuple(Vital(v['name'], v['scope'], v['value'], v['critical']) for v in summary['vitals']),
        summary['threat'], summary['threat_count'], summary['death'], readings)


def describe_actions(actions: Sequence[dict] | None) -> list[str]:
    """Compact, game-neutral description of an input operation's actions."""
    result = []
    for action in actions or ():
        kind = action.get('type')
        if kind == 'key':
            mods = '+'.join(action.get('modifiers') or ())
            result.append('key:' + (mods + '+' if mods else '') + str(action.get('key')))
        else:
            result.append(kind if kind in ('text', 'click', 'wait') else 'other')
    return result


def movement_key(descriptors: Sequence[str] | None, binding: Binding) -> str | None:
    keys = [d for d in descriptors or () if d != 'wait']
    if len(keys) == 1 and keys[0].startswith('key:') and keys[0][4:] in binding.movement_keys:
        return keys[0][4:]
    return None


def map_change_fraction(previous: Path, current: Path, region: tuple[int, int, int, int] | None) -> float | None:
    """Fraction of pixels inside `region` (left, top, right, bottom; whole frame if None) that
    differ by more than PIXEL_DELTA in any channel. Frames of different size are fully changed."""
    try:
        with Image.open(previous) as a, Image.open(current) as b:
            if a.size != b.size:
                return 1.0
            box = region if region is not None else (0, 0, a.size[0], a.size[1])
            left = np.asarray(a.convert('RGB').crop(box), dtype=np.int16)
            right = np.asarray(b.convert('RGB').crop(box), dtype=np.int16)
    except OSError:
        return None
    if left.size == 0:
        return None
    changed = (np.abs(left - right).max(axis=2) > PIXEL_DELTA).mean()
    return float(changed)


@dataclass(frozen=True)
class Episode:
    """A stretch of one survivor in one world: it starts at step index `start`. Episode 0 starts at the
    first step; later ones start where the clock restarted (backward by more than a day, confirmed by the
    next reading) or the legible identity changed (confirmed by the next legible identity)."""

    index: int
    start: int
    reason: str | None
    identity: str | None = None
    previous_identity: str | None = None
    previous_game_time: int | None = None
    game_time: int | None = None


def guard_episodes(raw: Sequence[int | None], max_jump: int, identities: Sequence[str | None] | None = None,
                   day: int | None = None) -> tuple[list[tuple[int | None, str | None]], list[Episode]]:
    """(game_time, abstain reason) per reading, and the episodes. Within an episode there is no backward
    step; a forward jump beyond `max_jump` is accepted only if the next legible reading confirms it (not
    backward and within `max_jump` of it). The last reading of a growing run stays unconfirmed until the
    next pass supplies its successor. With `day` (the binding's one day, in its game-time unit) a backward
    step of more than a day that the next reading confirms starts a new episode instead of abstaining, and a
    legible identity that differs from the episode's and is confirmed by the next legible identity starts
    one too and resets the clock."""
    names = list(identities) if identities is not None else [None] * len(raw)
    result: list[tuple[int | None, str | None]] = []
    episodes = [Episode(0, 0, None)]
    accepted: int | None = None
    current: str | None = None
    for index, value in enumerate(raw):
        name = names[index]
        if name is not None:
            if current is None:
                current = name
            elif name != current:
                following_name = next((v for v in names[index + 1:] if v is not None), None)
                if following_name == name:
                    episodes.append(Episode(len(episodes), index, 'identity_change', name, current, accepted))
                    current, accepted = name, None
        if value is None:
            result.append((None, 'unreadable'))
        elif accepted is not None and value < accepted:
            following = next((v for v in raw[index + 1:] if v is not None), None)
            if day is not None and accepted - value > day and following is not None and following >= value \
                    and following - value <= max_jump:
                episodes.append(Episode(len(episodes), index, 'clock_backward', current, current, accepted, value))
                accepted = value
                result.append((value, None))
            else:
                result.append((None, 'backward_step'))
        elif accepted is not None and value - accepted > max_jump:
            following = next((v for v in raw[index + 1:] if v is not None), None)
            if following is not None and following >= value and following - value <= max_jump:
                accepted = value
                result.append((value, None))
            else:
                result.append((None, 'implausible_jump'))
        else:
            accepted = value
            result.append((value, None))
    return result, episodes


def guard_clock(raw: Sequence[int | None], max_jump: int) -> list[tuple[int | None, str | None]]:
    """The guarded clock of a single episode (see `guard_episodes`)."""
    return guard_episodes(raw, max_jump)[0]


def frame_confidence(frames: Sequence[FrameReading]) -> float | None:
    values = [r.confidence for f in frames for r in f.readings if r.abstain is None and r.confidence is not None]
    return min(values) if values else None


@dataclass
class Timeline:
    """The record's steps with their frames, input descriptions and guarded clock."""

    steps: list[StepRow]
    frames: list[FrameReading]
    actions: list[list[str] | None]
    map_change: list[float | None]
    clock: list[int | None]
    ranks: list[int]
    first_in_play: int | None
    readings: dict[int, dict[str, ReadingRow]] = field(default_factory=dict)
    episodes: list[Episode] = field(default_factory=lambda: [Episode(0, 0, None)])
    episode_of: list[int] = field(default_factory=list)
    survival_start: int | None = None
    guard_abstain: list[str | None] = field(default_factory=list)

    @property
    def play_episode(self) -> Episode | None:
        """The last episode that has an accepted in-play clock reading: the one survival is measured in."""
        return self.episodes[self.episode_of[self.survival_start]] if self.survival_start is not None else None

    def episode_range(self, episode: Episode) -> range:
        end = self.episodes[episode.index + 1].start if episode.index + 1 < len(self.episodes) else len(self.steps)
        return range(episode.start, end)

    def before_play(self, index: int) -> bool:
        """Whether step `index` precedes the first in-play frame of its own episode (setup)."""
        first = next((i for i in self.episode_range(self.episodes[self.episode_of[index]])
            if self.frames[i].mode == 'in_play'), None)
        return first is not None and index < first

    def decision_rows(self) -> tuple[list[int], int]:
        """One representative step per decision: its last step with a legible mode. Also the
        number of decisions that returned a capture but no legible mode."""
        last: dict[int, int] = {}
        framed: set[int] = set()
        for index, (step, frame) in enumerate(zip(self.steps, self.frames)):
            if step.source_id is not None:
                framed.add(self.ranks[index])
            if frame.mode != 'unknown':
                last[self.ranks[index]] = index
        return [last[rank] for rank in sorted(last)], len(framed - set(last))

    def decisions_since_play(self, index: int) -> int:
        start = self.survival_start if self.survival_start is not None else self.first_in_play
        base = self.ranks[start] if start is not None else self.ranks[0]
        return self.ranks[index] - base


def decision_ranks(steps: Sequence[StepRow]) -> list[int]:
    """Consecutive decision number per step. A step without a decision counter is its own decision."""
    ranks, rank, previous = [], 0, object()
    for step in steps:
        key = ('d', step.decision) if step.decision is not None else ('s', step.seq)
        if key != previous:
            rank += 1
            previous = key
        ranks.append(rank)
    return ranks


def build_timeline(steps: Sequence[StepRow], readings: Sequence[ReadingRow], binding: Binding) -> Timeline:
    by_seq: dict[int, dict[str, ReadingRow]] = {}
    for reading in readings:
        by_seq.setdefault(reading.seq, {})[reading.reader] = reading
    frames, actions, change = [], [], []
    for step in steps:
        rows = by_seq.get(step.seq, {})
        frame_row = rows.get(READER_FRAME)
        if frame_row is None or frame_row.value is None:
            frames.append(NO_FRAME)
        else:
            others = tuple(Reading(r.reader, r.reader_version, r.value, r.confidence, r.abstain)
                for r in rows.values() if r.reader not in CORE_READERS)
            frames.append(frame_from_summary(frame_row.value, others))
        input_row = rows.get(READER_INPUT)
        actions.append(input_row.value if input_row is not None and input_row.value is not None else None)
        map_row = rows.get(READER_MAP)
        change.append(map_row.value if map_row is not None else None)
    guarded, episodes = guard_episodes([f.game_time for f in frames], max_jump(binding), [f.identity for f in frames],
        86400 / unit_seconds(binding))
    clock = [value for value, _ in guarded]
    first = next((i for i, f in enumerate(frames) if f.mode == 'in_play'), None)
    episode_of, at = [], 0
    for index in range(len(steps)):
        while at + 1 < len(episodes) and episodes[at + 1].start <= index:
            at += 1
        episode_of.append(at)
    # Survival is measured in the last episode that has an accepted in-play clock reading.
    survival_start = None
    for episode in reversed(episodes):
        end = episodes[episode.index + 1].start if episode.index + 1 < len(episodes) else len(steps)
        survival_start = next((i for i in range(episode.start, end) if clock[i] is not None and frames[i].mode == 'in_play'), None)
        if survival_start is not None:
            break
    timeline = Timeline(list(steps), frames, actions, change, clock, decision_ranks(steps), first, by_seq, episodes,
        episode_of, survival_start)
    timeline.guard_abstain[:] = [abstain for _, abstain in guarded]
    return timeline


def clock_readings(timeline: Timeline, binding: Binding) -> list[ReadingRow]:
    rows = []
    for step, value, abstain in zip(timeline.steps, timeline.clock, timeline.guard_abstain):
        if abstain == 'unreadable' and step.source_id is None:
            abstain = 'no_frame'
        rows.append(ReadingRow(step.seq, READER_CLOCK, CORE_VERSION, value, None, abstain))
    return rows


@dataclass(frozen=True)
class Streak:
    start: int
    end: int
    length: int
    setup: bool
    ongoing: bool
    modes: dict


def out_of_play_streaks(timeline: Timeline) -> list[Streak]:
    """Runs of consecutive decisions whose legible mode is neither in_play nor dead."""
    rows, _ = timeline.decision_rows()
    streaks: list[Streak] = []
    current: list[int] = []

    def close(ongoing: bool) -> None:
        if current:
            modes: dict[str, int] = {}
            for i in current:
                modes[timeline.frames[i].mode] = modes.get(timeline.frames[i].mode, 0) + 1
            setup = timeline.before_play(current[-1])
            streaks.append(Streak(current[0], current[-1], len(current), setup, ongoing, modes))
            current.clear()

    for index in rows:
        if timeline.frames[index].mode in ('in_play', 'dead'):
            close(False)
        else:
            current.append(index)
    close(True)
    return streaks


def core_events(timeline: Timeline, binding: Binding) -> list[EventRow]:
    steps, frames = timeline.steps, timeline.frames
    events: list[EventRow] = []
    # mode_change
    previous_mode = None
    for index, frame in enumerate(frames):
        if frame.mode == 'unknown':
            continue
        if previous_mode is not None and frame.mode != previous_mode:
            events.append(EventRow(steps[index].seq, steps[index].seq, 'mode_change', 'reader',
                frame_confidence([frame]), dict(previous=previous_mode, mode=frame.mode)))
        previous_mode = frame.mode
    # long_activity over consecutive guarded clock readings
    last = None
    for index, value in enumerate(timeline.clock):
        if value is None:
            continue
        if last is not None and timeline.episode_of[last] == timeline.episode_of[index] \
                and (value - timeline.clock[last]) * unit_seconds(binding) >= binding.long_activity_seconds:
            events.append(EventRow(steps[last].seq, steps[index].seq, 'long_activity', 'derived',
                frame_confidence([frames[last], frames[index]]), dict(seconds=(value - timeline.clock[last]) * unit_seconds(binding),
                    decisions=timeline.ranks[index] - timeline.ranks[last], unit=binding.game_time_unit,
                    start_game_time=timeline.clock[last], end_game_time=value)))
        last = index
    # stall
    for streak in out_of_play_streaks(timeline):
        if streak.length >= STALL_DECISIONS:
            events.append(EventRow(steps[streak.start].seq, steps[streak.end].seq, 'stall', 'derived', None,
                dict(decisions=streak.length, modes=streak.modes, setup=streak.setup, ongoing=streak.ongoing)))
    # ineffective_repeat: the binding's movement input, three or more times, with the map unchanged
    run: list[int] = []

    def close_run() -> None:
        if len(run) >= STUCK_INPUTS:
            key = movement_key(timeline.actions[run[0]], binding)
            events.append(EventRow(steps[run[0]].seq, steps[run[-1]].seq, 'ineffective_repeat', 'derived', None,
                dict(key=key, inputs=len(run), max_change=max(timeline.map_change[i] for i in run))))
        run.clear()

    for index, step in enumerate(steps):
        if step.kind != 'input':
            continue
        key = movement_key(timeline.actions[index], binding)
        change = timeline.map_change[index]
        if key is None or change is None or change >= STUCK_CHANGE:
            close_run()
            continue
        if run and movement_key(timeline.actions[run[-1]], binding) != key:
            close_run()
        run.append(index)
    close_run()
    # vital_change and threat_change
    baseline: dict[tuple[str, str], Vital] = {}
    previous_threat = None
    for index, frame in enumerate(frames):
        for vital in frame.vitals:
            key = (vital.name, vital.scope)
            before = baseline.get(key)
            if before is None:
                baseline[key] = vital
            elif vital.critical != before.critical or abs(vital.value - before.value) >= VITAL_STEP:
                events.append(EventRow(steps[index].seq, steps[index].seq, 'vital_change', 'reader',
                    frame_confidence([frame]), dict(name=vital.name, scope=vital.scope, value=vital.value,
                        previous=before.value, critical=vital.critical)))
                baseline[key] = vital
        if frame.threat is not None:
            if previous_threat is not None and frame.threat != previous_threat:
                events.append(EventRow(steps[index].seq, steps[index].seq, 'threat_change', 'reader',
                    frame_confidence([frame]), dict(previous=previous_threat, threat=frame.threat, count=frame.threat_count)))
            previous_threat = frame.threat
    # episode: a restarted clock or a different survivor starts a new episode
    for episode in timeline.episodes[1:]:
        step = steps[episode.start]
        events.append(EventRow(step.seq, step.seq, 'episode', 'derived', None, dict(index=episode.index,
            reason=episode.reason, identity=episode.identity, previous_identity=episode.previous_identity,
            previous_game_time=episode.previous_game_time, game_time=episode.game_time, unit=binding.game_time_unit)))
    # death: the first dead frame of each episode
    dead_episodes: set[int] = set()
    for index, frame in enumerate(frames):
        if (frame.death or frame.mode == 'dead') and timeline.episode_of[index] not in dead_episodes:
            dead_episodes.add(timeline.episode_of[index])
            cause = next((r for r in frame.readings if r.reader == 'death_cause' and r.abstain is None), None)
            events.append(EventRow(steps[index].seq, steps[index].seq, 'death', 'reader',
                cause.confidence if cause is not None else None,
                dict(cause=cause.value if cause is not None and cause.value in DEATH_CAUSES else 'unknown',
                    game_time=timeline.clock[index])))
    # milestone per reader rung, over the episode survival is measured in
    offset = timeline.play_episode.start if timeline.play_episode is not None else 0
    history = frames[offset:]
    for position, rung in enumerate(binding.ladder):
        if rung.evidence != 'reader':
            continue
        found = binding.rung_reached(rung, history)
        if type(found) is not int or not 0 <= found < len(history):
            continue
        index = found + offset
        step = steps[index]
        events.append(EventRow(step.seq, step.seq, 'milestone', 'reader', frame_confidence([frames[index]]),
            dict(rung=rung.id, label=rung.label, position=position, clocks=dict(wall=step.wall, decision=step.decision,
                tokens=step.tokens, dollars=step.dollars, game_time=timeline.clock[index]),
                decisions_to_reach=timeline.decisions_since_play(index))))
    return events


def receipt_uncertain(receipt: dict) -> bool:
    return receipt.get('disposition') in ('partial', 'unknown')


def operation_events(operations: Sequence[Operation]) -> list[EventRow]:
    """Handoffs and custody stops, which are recorded mechanical facts."""
    events = []
    for op in operations:
        if op.kind == 'handoff' and op.status == 'sealed' and op.handoff:
            events.append(EventRow(op.seq, op.seq, 'handoff', 'harness', None, dict(actor=op.actor,
                operation_id=op.operation_id, context_id=op.handoff.get('context_id'),
                context_sha256=op.handoff.get('context_sha256'))))
        uncertain = [r for r in op.receipts if receipt_uncertain(r)]
        if op.status in ('partial', 'unknown') or uncertain:
            events.append(EventRow(op.seq, op.seq, 'custody_stop', 'harness', None, dict(actor=op.actor,
                cause=op.status if op.status in ('partial', 'unknown') else uncertain[0]['disposition'],
                operation_id=op.operation_id, reason=op.reason,
                receipts=[r.get('disposition') for r in op.receipts])))
    return events
