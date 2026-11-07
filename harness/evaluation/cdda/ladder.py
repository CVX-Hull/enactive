"""CDDA milestone ladder, version 1, and the history scans that fire its reader rungs."""
from __future__ import annotations

from typing import Sequence

from harness.evaluation.core.binding import FrameReading, Rung
from harness.evaluation.cdda.readers import YEAR_SECONDS

LADDER = (
    Rung('in_play', 'In play', 'reader'),
    Rung('armed', 'Armed', 'human'),
    Rung('water_obtained', 'Water obtained', 'human'),
    Rung('drank', 'Drank', 'reader'),
    Rung('food_obtained', 'Food obtained', 'human'),
    Rung('ate', 'Ate', 'reader'),
    Rung('shelter', 'Shelter', 'human'),
    Rung('clean_water', 'Clean or boiled water', 'human'),
    Rung('slept', 'Slept', 'reader'),
    Rung('survived_first_night', 'Survived first night', 'reader'),
    Rung('elapsed_24h', 'Day 2 (24 h elapsed)', 'reader'),
    Rung('elapsed_72h', 'Day 3 (72 h elapsed)', 'reader'),
    Rung('elapsed_168h', 'Day 7 (168 h elapsed)', 'reader'),
    Rung('resupplied', 'Resupplied', 'human'),
)
ELAPSED = {'elapsed_24h': 24 * 3600, 'elapsed_72h': 72 * 3600, 'elapsed_168h': 168 * 3600}
IMPROVEMENT = 0.04          # smallest label step that counts as a need improving
SLEEP_GAIN = 0.3            # weariness gain that counts as substantial
SLEEP_SECONDS = 3600        # game time the gain must span
NIGHT_END = 6 * 3600        # 06:00 of the day after the first in-play reading


def _vital(frame: FrameReading, name: str) -> float | None:
    for v in frame.vitals:
        if v.name == name and v.scope == 'whole':
            return v.value
    return None


def _elapsed(history: Sequence[FrameReading]):
    """Yield (index, seconds since the first in-play clock reading) for in-play frames with a clock.

    The only backward step accepted is the year turn (a Winter start reading later in Spring);
    any other backward step is a different world or a misread and is skipped. A reading more
    than three days beyond the last accepted one is skipped as a misread.
    """
    start = last = None
    for i, frame in enumerate(history):
        if frame.mode != 'in_play' or frame.game_time is None:
            continue
        if start is None:
            start, last = frame.game_time, 0
        delta = frame.game_time - start
        if delta < 0 and start >= 3 * YEAR_SECONDS // 4 and frame.game_time < YEAR_SECONDS // 4:
            delta += YEAR_SECONDS
        if 0 <= delta <= last + 3 * 86400:
            last = max(last, delta)
            yield i, delta, start


def _improves(history: Sequence[FrameReading], name: str) -> int | None:
    last = None
    for i, frame in enumerate(history):
        if frame.mode != 'in_play':
            continue
        value = _vital(frame, name)
        if value is None:
            continue
        if last is not None and value - last >= IMPROVEMENT:
            return i
        last = value
    return None


def _slept(history: Sequence[FrameReading]) -> int | None:
    seen: list[tuple[int, float]] = []   # (elapsed, weariness) of earlier in-play readings
    best_before = float('inf')
    pointer = 0
    for i, delta, _ in _elapsed(history):
        value = _vital(history[i], 'weariness')
        if value is None:
            continue
        while pointer < len(seen) and delta - seen[pointer][0] >= SLEEP_SECONDS:
            best_before = min(best_before, seen[pointer][1])
            pointer += 1
        if value - best_before >= SLEEP_GAIN:
            return i
        seen.append((delta, value))
    return None


def rung_reached(rung: Rung, history: Sequence[FrameReading]) -> int | None:
    if rung.evidence == 'human':
        return None
    if rung.id == 'in_play':
        return next((i for i, f in enumerate(history) if f.mode == 'in_play'), None)
    if rung.id == 'drank':
        return _improves(history, 'thirst')
    if rung.id == 'ate':
        return _improves(history, 'hunger')
    if rung.id == 'slept':
        return _slept(history)
    if rung.id in ELAPSED:
        return next((i for i, delta, _ in _elapsed(history) if delta >= ELAPSED[rung.id]), None)
    if rung.id == 'survived_first_night':
        for i, delta, start in _elapsed(history):
            if delta >= 86400 - start % 86400 + NIGHT_END:
                return i
        return None
    raise ValueError(f'unknown rung {rung.id!r}')
