#!/usr/bin/env python3
"""Read-only run evaluation and telemetry diagnostics; selected paths only.

The telemetry diagnostics report recorded intervals and counts and give no gameplay
verdict. The evaluator subcommands derive interpretive records and metrics (ADR008,
docs/contracts/evaluation.md): each value carries its source and confidence, and the
evaluator still accepts no run or claim. Acceptance stays with frames, receipts, review
and the issue's decision rule.

host-summary selects current player-host/3 (telemetry version 3) files, actor directories or campaign
folders (4096 files / 8 GiB; 64 MiB per line; two million lines per trace).
control-summary selects 1..32 computer-session/1 databases/directories (512 MiB
per database including SQLite sidecars; 200000 rows per selected table).
evaluate-run reads one run directory read-only and writes an evaluation-record/1 store
under --root with the named game binding; it reuses the host and control summaries for
latency and delivery counts. evaluate-runs does the same for every run directory (one that
holds a manifest.json) below one directory, taking each run's memory store from --memory-dir
(player-memory-<run>.sqlite3) or its manifest, and the operator labels of an archived
campaign-run/4 run from data/evaluation/archive-labels.json (keyed by session ID, and the only
campaign-run/4 sessions the evaluator reads). evaluate-lineage takes one lineage's admission run
directories in order, scores any without a record as evaluate-run does, and writes the lineage's
continuity rows into each record. evaluate-compare reads evaluation
records and prints Kaplan-Meier curves, restricted mean survival to --horizon hours, bootstrap
intervals and pairwise log-rank tests by arm (the record's arm metadata, or --arm RECORD=LABEL).
evaluate-table prints a Markdown table of headline metrics from evaluation records (files, or
roots holding <session>/<versions>.sqlite3) or run-metrics/1 snapshots (.jsonl) for the development-run
log. --snapshot merges the selected records into the tracked data/evaluation/run-metrics.jsonl;
--write and --check regenerate or verify the `<!-- evaluate-table study=N [lineage=L] core=C
binding=ID:V -->` blocks in documents from that snapshot joined to the dev-run/1 ledger on session.
It never edits a record or a hand-scored table.
Unsupported historical formats remain inert evidence, available in Git history.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Sequence

from harness.computer.protocol import ControlError

EVALUATION_COMMANDS = ('evaluate-run', 'evaluate-runs', 'evaluate-lineage', 'evaluate-compare', 'evaluate-table')
# A game binding is imported only when it is named, so the core never depends on one.
BINDINGS: dict[str, tuple[str, str]] = {'cdda': ('harness.evaluation.cdda', 'CddaBinding')}


def load_binding(name: str) -> Any:
    try:
        module, attribute = BINDINGS[name]
    except KeyError:
        raise ValueError(f'Unknown binding {name!r}; available: {", ".join(sorted(BINDINGS))}') from None
    return getattr(importlib.import_module(module), attribute)()


def run_external(run_dir: Path) -> dict:
    """Plain numbers from the existing host and control summaries, passed into the core."""
    from tools.control_analysis import control_summary
    from tools.host_analysis import delta, host_summary
    external: dict = {}
    if any((run_dir / 'actors').glob('*/host.jsonl')):
        report = host_summary([run_dir])
        traces = report['traces']
        if traces and all(trace['coverage'] == 'player_host' for trace in traces):
            requests = [row for trace in traces for row in trace['requests']]
            external['response_ms'] = [row['observed_ms'] for row in requests
                if not row['censored'] and row['observed_ms'] is not None]
            external['first_chunk_ms'] = [value for row in requests
                if (value := delta(row.get('first_body_ms'), row.get('fetch_ms'))) is not None]
    control = control_summary([run_dir])['sessions'][0]['original_native_dispositions']
    external['custody'] = dict(receipts=sum(control.values()),
        uncertain=sum(control.get(key, 0) for key in ('partial', 'unknown', 'transport_unknown')))
    return external


def evaluate_one(run: Path, binding: Any, arguments: argparse.Namespace, memory: Path | None, label: str | None = None) -> Path:
    from harness.evaluation.core.pipeline import evaluate
    # An archived campaign-run/4 run takes its labels from the archive reader, keyed by session ID.
    return evaluate(run, binding, arguments.root, memory_store=memory, replace=arguments.replace,
        arm=label, external=run_external(run))


def evaluate_run(arguments: argparse.Namespace, binding: Any) -> dict:
    from harness.evaluation.core.pipeline import record_summary
    path = evaluate_one(arguments.paths[0], binding, arguments, arguments.memory,
        arguments.arm[0] if arguments.arm else None)
    summary = record_summary(path)
    return dict(record=str(path), session=summary['metadata']['session'],
        last_seq=summary['metadata']['last_seq'], metrics=sorted(summary['metrics']))


def evaluate_runs(arguments: argparse.Namespace, binding: Any) -> dict:
    from harness.evaluation.core.pipeline import record_summary
    directory = arguments.paths[0]
    runs = sorted(p for p in directory.iterdir() if (p / 'manifest.json').is_file())
    if not runs:
        raise ControlError(f'{directory}: no run directory (one holding a manifest.json) found')
    results = []
    for run in runs:
        memory = None
        if arguments.memory_dir is not None:
            candidate = arguments.memory_dir / f'player-memory-{run.name}.sqlite3'
            memory = candidate if candidate.is_file() else None
        path = evaluate_one(run, binding, arguments, memory)
        survival = record_summary(path)['metrics']['survival.game_hours']['value']
        results.append(dict(run=run.name, record=str(path), hours=None if not survival else survival['hours'],
            outcome=None if not survival else survival['outcome'],
            censor_reason=None if not survival else survival.get('censor_reason')))
    return dict(runs=results)


def evaluate_lineage(arguments: argparse.Namespace, binding: Any) -> dict:
    """Score each admission like evaluate-run (an existing final record is kept unless --replace), then stitch them."""
    from harness.evaluation.core.lineage import stitch
    from harness.evaluation.core.records import record_path
    from harness.evaluation.core.sources import read_operations
    for run in arguments.paths:
        session, _ = read_operations(run, settled_only=True)
        if arguments.replace or not record_path(arguments.root, session, binding.binding_id, binding.binding_version).exists():
            evaluate_one(run, binding, arguments, None)
    return stitch(arguments.paths, binding, arguments.root)


def evaluate_compare(arguments: argparse.Namespace) -> dict:
    from harness.evaluation.core.survival import compare_records
    arms = {}
    for item in arguments.arm or ():
        record, separator, label = item.partition('=')
        if not separator or not label:
            raise ValueError(f'--arm expects RECORD=LABEL, got {item!r}')
        arms[record] = label
    unknown = set(arms) - {str(path) for path in arguments.paths}
    if unknown:
        raise ValueError(f'--arm names a record that is not selected: {sorted(unknown)[0]}')
    return compare_records(arguments.paths, arguments.horizon, arms)


TABLE_COLUMNS = ('Run', 'Arm', 'Start', 'End', 'Game h', 'Decisions', 'Setup', 'Routine pace', 'Long activities',
                 'Out of play', 'Longest stall', '$ / decision', 'Large rewrites')


#: The metrics the table shows, copied verbatim into a run-metrics/1 snapshot row.
HEADLINE_METRICS = ('survival.game_hours', 'mode.out_of_play_share', 'pace.routine_seconds_per_decision',
                    'pace.long_activities', 'stall.longest', 'host.dollars_per_decision', 'host.large_rewrite_share')
SNAPSHOT = Path(__file__).resolve().parents[1] / 'data' / 'evaluation' / 'run-metrics.jsonl'
# Markers are whole lines; a block's content may not contain another opening marker.
BLOCK = re.compile(r'^(<!-- evaluate-table ([^>\n]+) -->\n)((?:(?!^<!-- evaluate-table ).)*?)(^<!-- /evaluate-table -->)$',
                   re.S | re.M)
LOOSE_OPEN = re.compile(r'^\s*<!--\s*evaluate-table\b', re.M)
LOOSE_CLOSE = re.compile(r'^\s*<!--\s*/\s*evaluate-table\b', re.M)


def has_blocks(text: str) -> bool:
    return bool(LOOSE_OPEN.search(text) or LOOSE_CLOSE.search(text))


def headline(path: Path) -> dict:
    """One run-metrics/1 row from an evaluation record: its key, labels and headline metric values."""
    from harness.evaluation.core.records import open_readonly, read_metadata, read_metrics
    connection = open_readonly(path)
    meta, metrics = read_metadata(connection), read_metrics(connection)
    labels = meta.get('labels') or {}
    return dict(schema='run-metrics/1', session=meta['session'], run=meta.get('run', ''),
        core_version=int(meta['core_version']), binding_id=meta['binding_id'], binding_version=int(meta['binding_version']),
        arm=labels.get('arm', meta.get('arm', '')) or '', start=labels.get('start', ''),
        decisions=connection.execute('SELECT COALESCE(MAX(decision), 0) FROM steps').fetchone()[0],
        metrics={name: metrics[(name, '')].value for name in HEADLINE_METRICS if (name, '') in metrics})


def snapshot_errors(row: object) -> list[str]:
    """Schema violations of one run-metrics/1 row (schemas/run-metrics.schema.json)."""
    from jsonschema import Draft202012Validator
    schema = json.loads((SNAPSHOT.parents[2] / 'schemas' / 'run-metrics.schema.json').read_text())
    return [f'{e.json_path}: {e.message}' for e in Draft202012Validator(schema).iter_errors(row)]


def read_snapshot(path: Path) -> list[dict]:
    """Every run-metrics/1 row, schema-validated; any other row is an error naming the line."""
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        row = json.loads(line)
        if not isinstance(row, dict) or row.get('schema') != 'run-metrics/1':
            raise ValueError(f'{path.name}:{number}: not a run-metrics/1 row')
        errors = snapshot_errors(row)
        if errors:
            raise ValueError(f'{path.name}:{number}: {errors[0]}')
        rows.append(row)
    return rows


def table(rows: list[dict]) -> str:
    """The Markdown table of headline metrics, one row per run-metrics/1 row."""
    lines = []
    for row in rows:
        value = row['metrics'].get
        inner = lambda item: item.get('value') if isinstance(item, dict) else item
        survival = value('survival.game_hours') or {}
        setup = (value('mode.out_of_play_share') or {}).get('setup_decisions') if isinstance(value('mode.out_of_play_share'), dict) else None
        long = value('pace.long_activities') or {}
        share = lambda item: '—' if item is None else f'{round(item * 100)}%'
        number = lambda item, digits: '—' if item is None else f'{item:.{digits}f}'
        lines.append((row['run'], row['arm'], row['start'],
            survival.get('censor_reason', '—'), number(survival.get('hours'), 2), str(row['decisions']),
            '—' if setup is None else str(setup), number(value('pace.routine_seconds_per_decision'), 1),
            f"{long.get('count', 0)} · {(long.get('total_game_seconds') or 0) / 3600:.2f} h",
            share(inner(value('mode.out_of_play_share'))), '—' if value('stall.longest') is None else str(value('stall.longest')),
            number(inner(value('host.dollars_per_decision')), 4), share(value('host.large_rewrite_share'))))
    order = {'pilot': 0, 'pre-loop': 1, 'ceiling': 2, 'zoom-aid': 3, 'game-help-aid': 4, 'reflection-aid': 5}
    lines.sort(key=lambda line: (order.get(line[1], 9), str(line[0])))
    header = f'| {" | ".join(TABLE_COLUMNS)} |\n| {" | ".join("---" if k < 4 else "---:" for k in range(len(TABLE_COLUMNS)))} |'
    cell = lambda item: '—' if item is None or item == '' else str(item)
    return '\n'.join([header, *(f'| {" | ".join(cell(item) for item in line)} |' for line in lines)])


def block_rows(selector: str, snapshot: list[dict], ledger: list[dict]) -> list[dict]:
    """The snapshot rows a block selects: `study=N [lineage=L] core=C binding=ID:V`, joined on session."""
    fields = dict(part.split('=', 1) for part in selector.split())
    if set(fields) - {'study', 'lineage', 'core', 'binding'} or not {'study', 'core', 'binding'} <= set(fields):
        raise ValueError(f'evaluate-table block selector {selector!r} needs study, core and binding, and may name lineage')
    binding_id, _, binding_version = fields['binding'].partition(':')
    chosen = [r for r in ledger if str(r['study']) == fields['study']
              and ('lineage' not in fields or r['lineage'] == fields['lineage'])]
    if not chosen:
        raise ValueError(f'evaluate-table block {selector!r} selects no ledger row')
    keyed = {(r['session'], r['core_version'], r['binding_id'], r['binding_version']): r for r in snapshot}
    missing = [r['run'] for r in chosen
               if (r['session'], int(fields['core']), binding_id, int(binding_version)) not in keyed]
    if missing:
        raise ValueError(f'evaluate-table block {selector!r}: no snapshot row for {", ".join(missing)}')
    return [keyed[(r['session'], int(fields['core']), binding_id, int(binding_version))] for r in chosen]


def write_blocks(documents: list[Path], snapshot: list[dict], ledger: list[dict], *, check: bool) -> list[str]:
    """Regenerate every marked block; with check, report stale blocks instead of writing. Every document is read,
    validated and rendered before any is written."""
    planned = []
    for document in documents:
        text = document.read_text()
        opens, closes = len(LOOSE_OPEN.findall(text)), len(LOOSE_CLOSE.findall(text))
        if not opens == closes == len(BLOCK.findall(text)):
            raise ValueError(f'{document}: malformed evaluate-table markers ({opens} opening, {closes} closing, '
                             f'{len(BLOCK.findall(text))} well-formed blocks); fix the markers by hand')
        fresh = BLOCK.sub(lambda m: m.group(1) + table(block_rows(m.group(2), snapshot, ledger)) + '\n' + m.group(4), text)
        if fresh != text:
            planned.append((document, fresh))
    if not check:
        for document, fresh in planned:
            document.write_text(fresh)
    return [str(document) for document, _ in planned] if check else []


def evaluate_table(arguments: argparse.Namespace) -> str:
    """Headline metrics for the run log: print a table from records or snapshots, write a snapshot of records,
    or regenerate or check the marked blocks in documents from the tracked snapshot and ledger.

    Generated from records only; it never edits hand-scored tables (ADR008)."""
    rows: list[dict] = []
    for path in arguments.paths:
        if path.suffix == '.jsonl':
            rows.extend(read_snapshot(path))
        else:
            rows.extend(headline(record) for record in (sorted(path.glob('*/*.sqlite3')) if path.is_dir() else [path]))
    if arguments.snapshot is not None:
        key = lambda r: (r['session'], r['core_version'], r['binding_id'], r['binding_version'])
        merged = {key(r): r for r in (read_snapshot(arguments.snapshot) if arguments.snapshot.is_file() else [])}
        for row in rows:
            if errors := snapshot_errors(row):
                raise ValueError(f'{row.get("run")}: derived snapshot row is invalid: {errors[0]}')
        merged.update((key(r), r) for r in rows)
        ordered = sorted(merged.values(), key=lambda r: (r['run'], *key(r)))
        arguments.snapshot.write_text(''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in ordered))
        return f'{len(rows)} rows written; {arguments.snapshot.name} holds {len(ordered)}'
    if arguments.write or arguments.check:
        from tools.run_ledger import read_ledger
        stale = write_blocks(arguments.write or arguments.check, rows, read_ledger(arguments.ledger), check=bool(arguments.check))
        if stale:
            raise ValueError(f'generated run tables are stale in {", ".join(stale)}; run evaluate-table '
                             f'{SNAPSHOT.relative_to(SNAPSHOT.parents[2])} --write DOCUMENT')
        return 'Generated run tables: current.' if arguments.check else 'Generated run tables: written.'
    return table(rows)


def main(argv: Sequence[str] | None = None, *, binding: Any = None,
         load: Callable[[str], Any] = load_binding) -> int:
    """`binding` and `load` are test hooks; the command line resolves --binding through BINDINGS."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('host-summary', 'control-summary', *EVALUATION_COMMANDS))
    parser.add_argument('paths', type=Path, nargs='+')
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--binding', help='evaluate-run, evaluate-runs, evaluate-lineage: game binding name')
    parser.add_argument('--root', type=Path, help='evaluate-run, evaluate-runs, evaluate-lineage: evaluation record root, e.g. .runtime/evaluations')
    parser.add_argument('--memory', type=Path, help='evaluate-run: player-memory/2 store if the manifest does not name it')
    parser.add_argument('--memory-dir', type=Path, help='evaluate-runs: directory of player-memory-<run>.sqlite3 stores')
    parser.add_argument('--replace', action='store_true', help='evaluate-run, evaluate-runs, evaluate-lineage: rewrite an existing record for these versions')
    parser.add_argument('--horizon', type=float, help='evaluate-compare: restricted mean horizon in game hours')
    parser.add_argument('--arm', action='append',
        help='evaluate-run: arm label stored in the record; evaluate-compare: RECORD=LABEL (repeatable)')
    table_output = parser.add_mutually_exclusive_group()
    table_output.add_argument('--snapshot', type=Path, help='evaluate-table: merge the selected records into this run-metrics/1 file')
    table_output.add_argument('--write', type=Path, nargs='+', help='evaluate-table: regenerate the marked blocks in these documents')
    table_output.add_argument('--check', type=Path, nargs='+', help='evaluate-table: fail if the marked blocks in these documents are stale')
    parser.add_argument('--ledger', type=Path, help='evaluate-table --write/--check: the dev-run/1 ledger (default data/evaluation/runs.jsonl)')
    arguments = parser.parse_args(argv)
    if arguments.command != 'evaluate-table' and any(
            value is not None for value in (arguments.snapshot, arguments.write, arguments.check, arguments.ledger)):
        parser.error('--snapshot, --write, --check and --ledger are supported for evaluate-table only')
    if arguments.ledger is not None and not (arguments.write or arguments.check):
        parser.error('--ledger is used with --write or --check only')
    if arguments.ledger is None:
        from tools.run_ledger import LEDGER
        arguments.ledger = LEDGER
    evaluating = arguments.command in EVALUATION_COMMANDS
    if arguments.command in ('evaluate-run', 'evaluate-runs'):
        if len(arguments.paths) != 1 or arguments.root is None or (binding is None and arguments.binding is None):
            parser.error(f'{arguments.command} requires one directory, --root and --binding')
        if arguments.arm is not None and (arguments.command == 'evaluate-runs' or len(arguments.arm) != 1):
            parser.error('evaluate-run takes at most one --arm label; evaluate-runs takes none')
    if arguments.command == 'evaluate-lineage':
        if arguments.root is None or (binding is None and arguments.binding is None):
            parser.error('evaluate-lineage requires admission run directories in order, --root and --binding')
        if arguments.arm is not None or arguments.memory is not None:
            parser.error('evaluate-lineage takes no --arm or --memory; each admission names its memory store and labels')
    if arguments.command != 'evaluate-runs' and arguments.memory_dir is not None:
        parser.error('--memory-dir is supported for evaluate-runs only')
    if arguments.command == 'evaluate-compare' and (arguments.horizon is None or not arguments.horizon > 0):
        parser.error('evaluate-compare requires --horizon HOURS greater than zero')
    if not evaluating and any(value is not None and value is not False for value in (
            arguments.binding, arguments.root, arguments.memory, arguments.memory_dir, arguments.horizon, arguments.arm,
            arguments.replace or None)):
        parser.error('--binding, --root, --memory, --memory-dir, --replace, --horizon and --arm are supported for the evaluate commands only')
    try:
        from harness.evaluation.core.records import EvaluationError
        if evaluating:
            try:
                if arguments.command == 'evaluate-table':
                    print(evaluate_table(arguments))
                    return 0
                if arguments.command == 'evaluate-compare':
                    result = evaluate_compare(arguments)
                else:
                    chosen = binding if binding is not None else load(arguments.binding)
                    result = {'evaluate-run': evaluate_run, 'evaluate-runs': evaluate_runs,
                              'evaluate-lineage': evaluate_lineage}[arguments.command](arguments, chosen)
            except EvaluationError as exc:
                raise ControlError(str(exc)) from exc
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return 0
        from tools.host_analysis import host_summary, markdown
        from tools.control_analysis import control_summary
        if arguments.format == 'markdown' and arguments.command != 'host-summary':
            raise ControlError('Markdown output is supported for host-summary only')
        result = {'host-summary': host_summary, 'control-summary': control_summary}[arguments.command](arguments.paths)
        print(markdown(result) if arguments.format == 'markdown' else json.dumps(result, allow_nan=False, sort_keys=True))
        return 0 if result.get('complete', True) else 1
    except (ControlError, OSError, ValueError, KeyError, UnicodeError, RecursionError, ImportError) as exc:
        print(f'Trace analysis failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
