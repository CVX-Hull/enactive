#!/usr/bin/env python3
"""Read-only run evaluation and telemetry diagnostics; selected paths only.

The telemetry diagnostics report recorded intervals and counts and give no gameplay
verdict. The evaluator subcommands derive interpretive records and metrics (ADR008,
docs/contracts/evaluation.md): each value carries its source and confidence, and the
evaluator still accepts no run or claim. Acceptance stays with frames, receipts, review
and the issue's decision rule.

host-summary selects current telemetry/2 files, actor directories or campaign
folders (4096 files / 8 GiB; 64 MiB per line; two million events per trace).
control-summary selects 1..32 computer-session/1 databases/directories (512 MiB
per database including SQLite sidecars; 200000 rows per selected table).
evaluate-run reads one run directory read-only and writes an evaluation-record/1 store
under --root with the named game binding; it reuses the host and control summaries for
latency and delivery counts. evaluate-runs does the same for every run directory (one that
holds a manifest.json) below one directory, taking each run's memory store from --memory-dir
(player-memory-<run>.sqlite3) or its manifest, and the operator labels of an archived
campaign-run/4 run from data/evaluation/archive-labels.json. evaluate-compare reads evaluation
records and prints Kaplan-Meier curves, restricted mean survival to --horizon hours, bootstrap
intervals and pairwise log-rank tests by arm (the record's arm metadata, or --arm RECORD=LABEL).
Unsupported historical formats remain inert evidence, available in Git history.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
from typing import Any, Callable, Sequence

from harness.computer.protocol import ControlError

EVALUATION_COMMANDS = ('evaluate-run', 'evaluate-runs', 'evaluate-compare')
# A game binding is imported only when it is named, so the core never depends on one.
BINDINGS: dict[str, tuple[str, str]] = {'cdda': ('harness.evaluation.cdda', 'CddaBinding')}
ARCHIVE_LABELS = Path(__file__).resolve().parents[1] / 'data' / 'evaluation' / 'archive-labels.json'


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


def archive_labels() -> dict[str, dict]:
    """Operator labels of archived runs whose campaign-run/4 manifest has none, by run directory name."""
    if not ARCHIVE_LABELS.is_file():
        return {}
    value = json.loads(ARCHIVE_LABELS.read_text())
    return value.get('runs', {}) if isinstance(value, dict) else {}


def evaluate_one(run: Path, binding: Any, arguments: argparse.Namespace, memory: Path | None, label: str | None = None) -> Path:
    from harness.evaluation.core.pipeline import evaluate
    labels = archive_labels().get(Path(run).resolve().name)
    return evaluate(run, binding, arguments.root, memory_store=memory, replace=arguments.replace,
        arm=label, labels=labels, external=run_external(run))


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


def main(argv: Sequence[str] | None = None, *, binding: Any = None,
         load: Callable[[str], Any] = load_binding) -> int:
    """`binding` and `load` are test hooks; the command line resolves --binding through BINDINGS."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('host-summary', 'control-summary', *EVALUATION_COMMANDS))
    parser.add_argument('paths', type=Path, nargs='+')
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--binding', help='evaluate-run, evaluate-runs: game binding name')
    parser.add_argument('--root', type=Path, help='evaluate-run, evaluate-runs: evaluation record root, e.g. .runtime/evaluations')
    parser.add_argument('--memory', type=Path, help='evaluate-run: player-memory/2 store if the manifest does not name it')
    parser.add_argument('--memory-dir', type=Path, help='evaluate-runs: directory of player-memory-<run>.sqlite3 stores')
    parser.add_argument('--replace', action='store_true', help='evaluate-run, evaluate-runs: rewrite an existing record for these versions')
    parser.add_argument('--horizon', type=float, help='evaluate-compare: restricted mean horizon in game hours')
    parser.add_argument('--arm', action='append',
        help='evaluate-run: arm label stored in the record; evaluate-compare: RECORD=LABEL (repeatable)')
    arguments = parser.parse_args(argv)
    evaluating = arguments.command in EVALUATION_COMMANDS
    if arguments.command in ('evaluate-run', 'evaluate-runs'):
        if len(arguments.paths) != 1 or arguments.root is None or (binding is None and arguments.binding is None):
            parser.error(f'{arguments.command} requires one directory, --root and --binding')
        if arguments.arm is not None and (arguments.command == 'evaluate-runs' or len(arguments.arm) != 1):
            parser.error('evaluate-run takes at most one --arm label; evaluate-runs takes none')
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
                if arguments.command == 'evaluate-compare':
                    result = evaluate_compare(arguments)
                else:
                    chosen = binding if binding is not None else load(arguments.binding)
                    result = (evaluate_run if arguments.command == 'evaluate-run' else evaluate_runs)(arguments, chosen)
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
    except (ControlError, OSError, ValueError, UnicodeError, RecursionError, ImportError) as exc:
        print(f'Trace analysis failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
