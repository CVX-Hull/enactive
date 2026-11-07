"""Lineage across chained admissions of one survivor (docs/contracts/evaluation.md).

A lineage is an ordered list of runs. For each boundary the core reports whether the
survivor is the same (from the binding's legible identity, else `unknown`) and the
game-time gap between the last reading of one admission and the first of the next; a
negative gap means the world was rewound. The result is written to each admission's
record as `continuity` events (on the later admission) and the `lineage.continuity` metric.

Lineage-wide metrics are written to every admission's record as well:
- `lineage.elapsed`: game time from admission 1's first reading to the lineage's last reading;
  a rewind lowers it. Also decisions, overall game seconds per decision and long activities.
- `lineage.day_check`: the first step at or after one game day (`DAY_SECONDS`) with legible
  needs; it passes when no death was read before it and the binding reports no severe need.
- `lineage.memory_reuse`: distinct memory records read in a later admission that an earlier
  admission wrote.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

from .binding import Binding
from .derive import UNIT_SECONDS
from .records import (EvaluationError, EventRow, MetricRow, RecordWriter, loads, open_readonly, read_metadata)

METRIC = 'lineage.continuity'
ELAPSED_METRIC = 'lineage.elapsed'
DAY_METRIC = 'lineage.day_check'
MEMORY_METRIC = 'lineage.memory_reuse'
DAY_SECONDS = 24 * 3600


@dataclass(frozen=True)
class Admission:
    run: str
    first_seq: int | None
    first_game_seconds: int | None
    last_game_seconds: int | None
    first_identity: str | None
    last_identity: str | None


def summarise(record: Path) -> Admission:
    """First and last guarded game time and legible identity of one evaluation record."""
    connection = open_readonly(record)
    try:
        metadata = read_metadata(connection)
        unit = UNIT_SECONDS.get(metadata.get('game_time_unit', ''))
        if unit is None:
            raise EvaluationError(f'{record}: unsupported game time unit {metadata.get("game_time_unit")!r}')
        rows = connection.execute('SELECT s.seq,s.game_time,r.value FROM steps s LEFT JOIN readings r '
            "ON r.seq=s.seq AND r.reader='core.frame' ORDER BY s.seq").fetchall()
    finally:
        connection.close()
    times = [(seq, t * unit) for seq, t, _ in rows if t is not None]
    identities = [v for _, _, raw in rows if raw is not None for v in [json.loads(raw).get('identity')] if v is not None]
    return Admission(str(metadata.get('run')), rows[0][0] if rows else None, times[0][1] if times else None,
        times[-1][1] if times else None, identities[0] if identities else None, identities[-1] if identities else None)


def boundaries(admissions: Sequence[Admission]) -> list[dict]:
    """One entry per boundary between consecutive admissions."""
    result = []
    for index in range(1, len(admissions)):
        before, after = admissions[index - 1], admissions[index]
        gap = None if before.last_game_seconds is None or after.first_game_seconds is None \
            else after.first_game_seconds - before.last_game_seconds
        same: bool | str = 'unknown' if before.last_identity is None or after.first_identity is None \
            else before.last_identity == after.first_identity
        result.append(dict(boundary=index, previous_run=before.run, run=after.run, same_identity=same,
            gap_seconds=gap, rewound=None if gap is None else gap < 0))
    return result


def metric(items: Sequence[dict]) -> MetricRow:
    continuous = sum(1 for b in items if b['same_identity'] is True and b['gap_seconds'] is not None and b['gap_seconds'] >= 0)
    unknown = any(b['same_identity'] == 'unknown' for b in items)
    return MetricRow(METRIC, 1, list(items), continuous, len(items), 'unknown_identity' if unknown else None)


@dataclass(frozen=True)
class Timeline:
    """What the lineage-wide metrics need from one admission's record."""
    record: Path
    run: str
    unit: int
    decisions: int
    long_seconds: float
    points: tuple[tuple[int, int, str], ...]      # (seq, game seconds, mode) for steps with a game time
    deaths: tuple[int, ...]                       # seq of each death event
    written: frozenset[str]
    read: frozenset[str]


def timeline(record: Path) -> Timeline:
    connection = open_readonly(record)
    try:
        metadata = read_metadata(connection)
        unit = UNIT_SECONDS.get(metadata.get('game_time_unit', ''))
        if unit is None:
            raise EvaluationError(f'{record}: unsupported game time unit {metadata.get("game_time_unit")!r}')
        points = tuple((seq, t * unit, mode) for seq, t, mode in connection.execute(
            'SELECT seq,game_time,mode FROM steps WHERE game_time IS NOT NULL ORDER BY seq'))
        decisions = connection.execute('SELECT COALESCE(MAX(decision), 0) FROM steps').fetchone()[0]
        long_row = connection.execute("SELECT value FROM metrics WHERE name='pace.long_activities' AND key=''").fetchone()
        long_value = loads(long_row[0]) if long_row else None
        events = connection.execute(
            "SELECT kind,seq_start,payload FROM events WHERE kind IN ('death','memory_write','memory_read') ORDER BY seq_start")
        deaths, written, read = [], set(), set()
        for kind, seq, payload in events:
            data = loads(payload)
            if kind == 'death':
                deaths.append(seq)
            elif kind == 'memory_write':
                written.add(data['record_id'])
            else:
                read.update(data.get('record_ids') or ())
    finally:
        connection.close()
    long_seconds = float(long_value.get('total_game_seconds') or 0) if isinstance(long_value, dict) else 0.0
    return Timeline(record, str(metadata.get('run')), unit, int(decisions), long_seconds, points, tuple(deaths),
        frozenset(written), frozenset(read))


def elapsed_metric(timelines: Sequence[Timeline]) -> MetricRow:
    first = next((t.points[0][1] for t in timelines if t.points), None)
    last = next((t.points[-1][1] for t in reversed(timelines) if t.points), None)
    decisions = sum(t.decisions for t in timelines)
    long_seconds = sum(t.long_seconds for t in timelines)
    if first is None or last is None:
        return MetricRow(ELAPSED_METRIC, 1, None, decisions, None, 'no_game_time')
    seconds = last - first
    value = dict(game_seconds=seconds, game_hours=round(seconds / 3600, 3), decisions=decisions,
        game_seconds_per_decision=round(seconds / decisions, 2) if decisions else None,
        long_activity_hours=round(long_seconds / 3600, 3),
        long_activity_share=round(long_seconds / seconds, 3) if seconds > 0 else None,
        admissions=len(timelines))
    return MetricRow(ELAPSED_METRIC, 1, value, decisions, seconds, None)


def _step_values(record: Path, seq: int) -> dict[str, object]:
    connection = open_readonly(record)
    try:
        return {reader: loads(value) for reader, value in connection.execute(
            'SELECT reader,value FROM readings WHERE seq=? AND value IS NOT NULL', (seq,))}
    finally:
        connection.close()


def day_check_metric(timelines: Sequence[Timeline], binding: Binding) -> MetricRow:
    """Alive at one game day after admission 1's first reading, with no severe need (binding's rule)."""
    first = next((t.points[0][1] for t in timelines if t.points), None)
    if first is None:
        return MetricRow(DAY_METRIC, 1, None, 0, 1, 'no_game_time')
    for index, line in enumerate(timelines):
        crossing = next((seq for seq, seconds, _ in line.points if seconds - first >= DAY_SECONDS), None)
        if crossing is None:
            continue
        died = any(t.deaths for t in timelines[:index]) or any(seq <= crossing for seq in line.deaths)
        base = dict(run=line.run, crossing_seq=crossing, died_before=died)
        if died:
            return MetricRow(DAY_METRIC, 1, dict(base, passed=False, severe=None), 0, 1, None)
        for seq, seconds, mode in line.points:
            if seq < crossing or mode != 'in_play':
                continue
            severe = binding.severe_needs(_step_values(line.record, seq))
            if severe is None:
                continue
            passed = not severe
            return MetricRow(DAY_METRIC, 1, dict(base, seq=seq, elapsed_hours=round((seconds - first) / 3600, 3),
                passed=passed, severe=list(severe)), int(passed), 1, None)
        return MetricRow(DAY_METRIC, 1, dict(base, passed=None, severe=None), 0, 1, 'needs_not_legible')
    return MetricRow(DAY_METRIC, 1, None, 0, 1, 'not_reached')


def memory_metric(timelines: Sequence[Timeline]) -> MetricRow:
    earlier: set[str] = set()
    reused: set[str] = set()
    per_admission = []
    for line in timelines:
        found = line.read & earlier
        per_admission.append(dict(run=line.run, reused=len(found)))
        reused |= found
        earlier |= line.written
    available = set().union(*(t.written for t in timelines[:-1])) if len(timelines) > 1 else set()
    if not available:
        return MetricRow(MEMORY_METRIC, 1, dict(per_admission=per_admission), len(reused), None, 'no_earlier_writes')
    return MetricRow(MEMORY_METRIC, 1, dict(per_admission=per_admission, reused=len(reused)), len(reused),
        len(available), None)


def apply(records: Sequence[Path], items: Sequence[dict], extra: Sequence[MetricRow] = ()) -> None:
    """Write the continuity events and the lineage metrics into each record of the lineage."""
    for index, record in enumerate(records):
        with RecordWriter.open(record) as writer:
            first = writer.connection.execute('SELECT MIN(seq) FROM steps').fetchone()[0]
            events = []
            if index > 0 and first is not None:
                events.append(EventRow(first, first, 'continuity', 'derived', None, dict(items[index - 1])))
            with writer.transaction():
                writer.replace_continuity(events)
                writer.upsert_metrics([metric(items), *extra])


def stitch(run_dirs: Sequence[Path], binding: Binding, root: Path, *, memory_stores: Mapping[str, Path] | None = None,
           replace: bool = False) -> dict:
    """Evaluate each run (an existing record is reused unless `replace`), then write the lineage."""
    from .pipeline import evaluate
    from .records import record_path
    from .sources import read_operations
    if len(run_dirs) < 1:
        raise EvaluationError('A lineage needs at least one run')
    paths = []
    for run_dir in run_dirs:
        session, _ = read_operations(Path(run_dir), settled_only=True)
        existing = record_path(root, session, binding.binding_id, binding.binding_version)
        if existing.exists() and not replace:
            paths.append(existing)
        else:
            paths.append(evaluate(Path(run_dir), binding, root, memory_store=(memory_stores or {}).get(str(run_dir)),
                replace=replace))
    items = boundaries([summarise(path) for path in paths])
    timelines = [timeline(path) for path in paths]
    extra = [elapsed_metric(timelines), day_check_metric(timelines, binding), memory_metric(timelines)]
    apply(paths, items, extra)
    return dict(records=[str(p) for p in paths], boundaries=items, **{row.name: row.value for row in extra})
