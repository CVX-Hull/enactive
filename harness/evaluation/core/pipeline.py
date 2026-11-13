"""One evaluation pass over a run directory (docs/contracts/evaluation.md).

`evaluate` reads the run read-only, reads each new original frame through the binding,
appends the raw rows, and rewrites the derived rows (guarded game time, events, metrics)
from the whole record. A full pass is deterministic: the same run, binding and
`created_wall` give the same record. An incremental pass (`after_seq`, the record's
`last_seq`) continues a record for a live run. An operation whose terminal state
was not yet written is recorded as a step without a frame and listed in `pending_seqs`; when
it settles, the pass rebuilds the record from that step on (its frame, and the change versus
it, were not known before).

A binding that returns a reader name the core uses itself is refused; the core's own
readers are `frame` (the normalised frame reading), `input`, `game_time` and `map_change`.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time
from typing import Any, Mapping

from .binding import Binding
from .derive import (CORE_READERS, CORE_VERSION, NO_FRAME, READER_CLOCK, READER_FRAME, READER_INPUT, READER_MAP,
    build_timeline, clock_readings, core_events, describe_actions, frame_summary, map_change_fraction,
    operation_events)
from .facts import LABEL_KEYS, run_facts
from .host import host_events, host_facts, seq_resolver
from .metrics import compute_metrics
from .lineage import DAY_METRIC, ELAPSED_METRIC, MEMORY_METRIC, METRIC as LINEAGE_METRIC
LINEAGE_METRICS = (LINEAGE_METRIC, ELAPSED_METRIC, DAY_METRIC, MEMORY_METRIC)
from .records import EvaluationError, MetricRow, ReadingRow, RecordWriter, StepRow, record_path
from .sources import MANIFEST_SCHEMA, RunInputs, archive_entry, read_run


def _frame_matches(png: Path, sha256: str | None) -> bool:
    with png.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == sha256


def _read_new_steps(inputs: RunInputs, binding: Binding, known: list[StepRow], facts) -> tuple[list[StepRow], list[ReadingRow]]:
    previous = next((s for s in reversed(known) if s.source_id is not None), None)
    previous_sha = previous.frame_sha256 if previous else None
    previous_png = inputs.run_dir / 'sources' / f'{previous.source_id}.png' if previous else None
    last_seq = known[-1].seq if known else 0
    decisions = known[-1].decision if known and known[-1].decision is not None else 0
    steps, readings = [], []
    for op in inputs.operations:
        if op.seq <= last_seq:
            continue
        frame, frame_abstain = None, None
        if op.source_id is None:
            frame_abstain = 'no_frame'
        elif op.png is None:
            frame_abstain = 'frame_unavailable'
        elif not _frame_matches(op.png, op.sha256):
            frame_abstain = 'frame_integrity'
        else:
            try:
                frame = binding.read_frame(op.png)
            except Exception as exc:  # the binding contract is to abstain, never raise
                raise EvaluationError(f'{op.png}: binding {binding.binding_id} raised {type(exc).__name__}: {exc}') from exc
            for reading in frame.readings:
                if reading.reader in CORE_READERS:
                    raise EvaluationError(f'binding {binding.binding_id} uses the core reader name {reading.reader!r}')
        _, tokens, dollars = facts.accounting(op)
        # A decision is one completed computer_input operation; other operations belong to the latest one.
        if op.kind == 'input' and op.status == 'completed':
            decisions += 1
        decision = decisions
        changed = None if op.sha256 is None or previous_sha is None else op.sha256 != previous_sha
        steps.append(StepRow(op.seq, op.operation_id, op.actor, op.kind, op.created_wall, decision, tokens, dollars,
            None, frame.mode if frame else NO_FRAME.mode, op.source_id, op.sha256, changed))
        readings.append(ReadingRow(op.seq, READER_FRAME, binding.binding_version,
            frame_summary(frame) if frame else None, None, frame_abstain))
        for reading in frame.readings if frame else ():
            readings.append(ReadingRow(op.seq, reading.reader, reading.version, reading.value, reading.confidence, reading.abstain))
        if op.kind == 'input':
            readings.append(ReadingRow(op.seq, READER_INPUT, CORE_VERSION, describe_actions(op.actions), None, None))
            if frame is not None and previous_png is not None and previous_png.is_file():
                fraction = map_change_fraction(previous_png, op.png, binding.map_region)
                readings.append(ReadingRow(op.seq, READER_MAP, CORE_VERSION, fraction, None,
                    None if fraction is not None else 'unreadable'))
            else:
                readings.append(ReadingRow(op.seq, READER_MAP, CORE_VERSION, None, None,
                    'no_frame' if frame is None else 'no_previous_capture'))
        else:
            readings.append(ReadingRow(op.seq, READER_INPUT, CORE_VERSION, None, None, 'not_input'))
            readings.append(ReadingRow(op.seq, READER_MAP, CORE_VERSION, None, None, 'not_input'))
        if op.source_id is not None:
            previous_sha, previous_png = op.sha256, op.png
    return steps, readings


def _derive(writer: RecordWriter, inputs: RunInputs, binding: Binding, facts, external: Mapping[str, Any] | None,
            labels: Mapping[str, object] | None = None) -> dict:
    steps = writer.steps()
    timeline = build_timeline(steps, writer.readings(), binding)
    clock = clock_readings(timeline, binding)
    for row in clock:  # the guarded clock is a reader of its own, replacing any earlier pass's rows
        timeline.readings.setdefault(row.seq, {})[READER_CLOCK] = row
    resolve = seq_resolver([(s.seq, s.wall) for s in steps])
    events = [*core_events(timeline, binding), *operation_events(inputs.operations),
        *host_events(facts, resolve, inputs.memory)]
    human = frozenset(e['payload'].get('rung') for e in writer.events() if e['source'] == 'human' and e['kind'] == 'milestone')
    metrics = compute_metrics(timeline, inputs.operations, events, facts, binding, inputs.carry, human, external, inputs.end)
    run = run_facts(inputs.manifest, inputs.host, inputs.actors, labels)
    writer.replace_run_facts(run)
    writer.replace_host_rows(facts.tool_rows(), facts.request_rows())
    writer.set_metadata(dict(labels=run['labels']))
    writer.replace_readings(READER_CLOCK, clock)
    writer.set_game_times([(row.seq, row.value) for row in clock])
    writer.replace_events(events)
    writer.replace_metrics(metrics, keep=LINEAGE_METRICS)  # stitching owns these; a pass never drops them
    writer.upsert_metrics([MetricRow(LINEAGE_METRIC, 1, [], 0, 0, None)], replace=False)
    return dict(first_in_play_seq=steps[timeline.first_in_play].seq if timeline.first_in_play is not None else None)


def existing_state(path: Path) -> str | None:
    """The `state` of the record at `path` (`live` or `final`), or None when there is none or it is unreadable."""
    from .records import open_readonly, read_metadata
    if not path.is_file():
        return None
    try:
        connection = open_readonly(path)
    except EvaluationError:
        return None
    try:
        return read_metadata(connection).get('state')
    finally:
        connection.close()


def evaluate(run_dir: Path, binding: Binding, root: Path, memory_store: Path | None = None, replace: bool = False,
             after_seq: int | None = None, *, arm: str | None = None, external: Mapping[str, Any] | None = None,
             created_wall: float | None = None, state: str = 'final',
             labels: Mapping[str, object] | None = None) -> Path:
    """Evaluate one run and return its record path.

    `state` is `final` (default: after the run ended; input digests are taken) or `live` (the viewer's
    incremental store; no digests). A `live` store is replaced by any pass of the same versions; a `final`
    store is only rewritten by a `final` pass with `replace=True`. A `live` pass is refused when a `final`
    store of the same versions exists, and an incremental pass (`after_seq`) continues only a record whose
    recorded state is the requested one, so a `final` record is never continued. `labels` stand in for the operator labels that a
    campaign-run/4 manifest lacks (default: the archive's labels for its session). `external` optionally carries numbers computed by the existing host and
    control summaries: `response_ms` and `first_chunk_ms` (lists) and `custody` (`{"receipts": n, "uncertain": n}`).
    `created_wall` defaults to the current time; fix it for byte-identical records.
    """
    if state not in ('live', 'final'):
        raise ValueError(f'state must be live or final, not {state!r}')
    run_dir = Path(run_dir)
    incremental = after_seq is not None
    inputs = read_run(run_dir, memory_path=memory_store, digests=state == 'final')
    final = record_path(Path(root), inputs.session, binding.binding_id, binding.binding_version)
    facts = host_facts(inputs.actors, inputs.host)
    if labels is None and inputs.manifest.get('schema') != MANIFEST_SCHEMA:  # an archived manifest's labels are the index's
        entry = archive_entry(inputs.manifest)
        if entry is not None and entry.labels is not None:
            labels = {key: entry.labels.get(key) for key in LABEL_KEYS}
    if arm is not None and labels is None:
        labels = dict(arm=arm)
    base = dict(core_version=CORE_VERSION, binding_id=binding.binding_id, binding_version=binding.binding_version,
        game_time_unit=binding.game_time_unit, run=run_dir.resolve().name, run_dir=str(run_dir.resolve()),
        session=inputs.session, arm=arm or (labels or {}).get('arm') or (inputs.manifest.get('labels') or {}).get('arm'),
        memory_store=str(memory_store) if memory_store else None, state=state)
    if state == 'live' and existing_state(final) == 'final':
        raise EvaluationError(f'{final}: a final evaluation record for these versions exists; a live pass never touches it')
    if incremental:
        writer = RecordWriter.open(final)
        recorded = writer.metadata()
        if recorded.get('state') != state or state == 'final':
            writer.close()
            raise EvaluationError(f'{final}: the record is {recorded.get("state")!r}; a {state!r} pass cannot continue it')
        if recorded.get('session') != inputs.session or recorded.get('last_seq') != after_seq:
            writer.close()
            raise EvaluationError(f'{final}: after_seq {after_seq} does not continue this record '
                f'(last_seq {recorded.get("last_seq")})')
        target = final
    else:
        if final.exists() and not replace and existing_state(final) != 'live':
            raise EvaluationError(f'{final}: an evaluation record for these versions exists; pass replace=True to rewrite it')
        target = final.with_name(final.name + '.partial')
        writer = RecordWriter.create(target, dict(base, created_wall=created_wall if created_wall is not None else time.time(),
            last_seq=0, first_in_play_seq=None, inputs=inputs.digests if state == 'final' else {}), replace=True)
    try:
        with writer.transaction():
            # An operation recorded while its terminal state was unwritten is re-read once it settles.
            # Its frame and everything compared with it change, so the record is rebuilt from there.
            pending = set(writer.metadata().get('pending_seqs') or ()) if incremental else set()
            settled = [op.seq for op in inputs.operations if op.seq in pending and op.status != 'pending']
            if settled:
                writer.delete_from(min(settled))
            known = writer.steps()
            steps, readings = _read_new_steps(inputs, binding, known, facts)
            writer.append_steps(steps, readings)
            derived = _derive(writer, inputs, binding, facts, external, labels)
            writer.set_metadata(dict(last_seq=inputs.last_seq or 0, inputs=inputs.digests if state == 'final' else {},
                pending_seqs=[op.seq for op in inputs.operations if op.status == 'pending'], **derived))
    except BaseException:
        writer.close()
        if not incremental:
            for suffix in ('', '-wal', '-shm'):
                Path(str(target) + suffix).unlink(missing_ok=True)
        raise
    writer.close()
    if not incremental:
        for suffix in ('-wal', '-shm'):
            Path(str(final) + suffix).unlink(missing_ok=True)
        os.replace(target, final)
        for suffix in ('-wal', '-shm'):
            Path(str(target) + suffix).unlink(missing_ok=True)
    return final


def record_summary(path: Path) -> dict:
    """Metadata and metrics of a record, for the command line and tests."""
    from .records import open_readonly, read_metadata, read_metrics
    connection = open_readonly(path)
    try:
        return dict(metadata=read_metadata(connection),
            metrics={name if not key else f'{name}[{key}]': dict(value=row.value, count=row.count,
                denominator=row.denominator, missing=row.missing) for (name, key), row in read_metrics(connection).items()})
    finally:
        connection.close()
