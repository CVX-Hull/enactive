"""Lineage across chained admissions of one survivor (docs/contracts/evaluation.md).

A lineage is an ordered list of runs. For each boundary the core reports whether the
survivor is the same (from the binding's legible identity, else `unknown`) and the
game-time gap between the last reading of one admission and the first of the next; a
negative gap means the world was rewound. The result is written to each admission's
record as `continuity` events (on the later admission) and the `lineage.continuity` metric.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

from .binding import Binding
from .derive import UNIT_SECONDS
from .records import (EvaluationError, EventRow, MetricRow, RecordWriter, open_readonly, read_metadata)

METRIC = 'lineage.continuity'


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


def apply(records: Sequence[Path], items: Sequence[dict]) -> None:
    """Write the continuity events and metric into each record of the lineage."""
    for index, record in enumerate(records):
        with RecordWriter.open(record) as writer:
            first = writer.connection.execute('SELECT MIN(seq) FROM steps').fetchone()[0]
            events = []
            if index > 0 and first is not None:
                events.append(EventRow(first, first, 'continuity', 'reader', None, dict(items[index - 1])))
            with writer.transaction():
                writer.replace_continuity(events)
                writer.upsert_metrics([metric(items)])


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
    apply(paths, items)
    return dict(records=[str(p) for p in paths], boundaries=items)
