#!/usr/bin/env python3
"""Read-only run evaluation and telemetry diagnostics; selected paths only.

The telemetry diagnostics report recorded intervals and counts and give no gameplay
verdict. The evaluator subcommands derive interpretive records and metrics (ADR008,
docs/contracts/evaluation.md): each value carries its source and confidence, and the
evaluator still accepts no run or claim. Acceptance stays with frames, receipts, review
and the issue's decision rule.

host-summary selects current telemetry/2 files, actor directories or campaign
folders (4096 files / 8 GiB; 64 MiB per line; two million events per trace).
witness-summary selects one computer-session/1 database/directory and 1..32
observer-timing/4 exports (64 MiB each / 256 MiB total; 2000 rows per export).
control-summary selects 1..32 computer-session/1 databases/directories (512 MiB
per database including SQLite sidecars; 200000 rows per selected table).
investigation-export selects 1..4 explicitly closed cases and writes a bounded
observer-investigation/1 bundle, optionally with the shared recorded HTML reader.
evaluate-run reads one run directory read-only and writes an evaluation-record/1 store
under --root with the named game binding; it reuses the host and control summaries for
latency and delivery counts. evaluate-compare reads evaluation records and prints
Kaplan-Meier curves, restricted mean survival to --horizon hours, bootstrap intervals
and pairwise log-rank tests by arm (the record's arm metadata, or --arm RECORD=LABEL).
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

EVALUATION_COMMANDS = ('evaluate-run', 'evaluate-compare')
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


def evaluate_run(arguments: argparse.Namespace, binding: Any) -> dict:
    from harness.evaluation.core.pipeline import evaluate, record_summary
    run = arguments.paths[0]
    path = evaluate(run, binding, arguments.root, memory_store=arguments.memory, replace=arguments.replace,
        arm=arguments.arm[0] if arguments.arm else None, external=run_external(run))
    summary = record_summary(path)
    return dict(record=str(path), session=summary['metadata']['session'],
        last_operation_seq=summary['metadata']['last_operation_seq'], metrics=sorted(summary['metrics']))


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
    parser.add_argument('command', choices=('host-summary', 'witness-summary', 'control-summary', 'investigation-export',
        *EVALUATION_COMMANDS))
    parser.add_argument('paths', type=Path, nargs='+')
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--html', type=Path)
    parser.add_argument('--binding', help='evaluate-run: game binding name')
    parser.add_argument('--root', type=Path, help='evaluate-run: evaluation record root, e.g. .runtime/evaluations')
    parser.add_argument('--memory', type=Path, help='evaluate-run: player-memory/2 store if the manifest does not name it')
    parser.add_argument('--replace', action='store_true', help='evaluate-run: rewrite an existing record for these versions')
    parser.add_argument('--horizon', type=float, help='evaluate-compare: restricted mean horizon in game hours')
    parser.add_argument('--arm', action='append',
        help='evaluate-run: arm label stored in the record; evaluate-compare: RECORD=LABEL (repeatable)')
    arguments = parser.parse_args(argv)
    evaluating = arguments.command in EVALUATION_COMMANDS
    if arguments.command == 'investigation-export' and (len(arguments.paths) != 1 or arguments.output is None):
        parser.error('investigation-export requires one selection file and --output')
    if arguments.command != 'investigation-export' and (arguments.output is not None or arguments.html is not None):
        parser.error('--output and --html are supported for investigation-export only')
    if arguments.command == 'evaluate-run':
        if len(arguments.paths) != 1 or arguments.root is None or (binding is None and arguments.binding is None):
            parser.error('evaluate-run requires one run directory, --root and --binding')
        if arguments.arm is not None and len(arguments.arm) != 1:
            parser.error('evaluate-run takes at most one --arm label')
    if arguments.command == 'evaluate-compare' and (arguments.horizon is None or not arguments.horizon > 0):
        parser.error('evaluate-compare requires --horizon HOURS greater than zero')
    if not evaluating and any(value is not None and value is not False for value in (
            arguments.binding, arguments.root, arguments.memory, arguments.horizon, arguments.arm, arguments.replace or None)):
        parser.error('--binding, --root, --memory, --replace, --horizon and --arm are supported for the evaluate commands only')
    try:
        from harness.evaluation.core.records import EvaluationError
        if evaluating:
            try:
                if arguments.command == 'evaluate-run':
                    result = evaluate_run(arguments, binding if binding is not None else load(arguments.binding))
                else:
                    result = evaluate_compare(arguments)
            except EvaluationError as exc:
                raise ControlError(str(exc)) from exc
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return 0
        from tools.host_analysis import host_summary, markdown
        from tools.observer_analysis import witness_summary
        from tools.control_analysis import control_summary
        if arguments.command == 'investigation-export':
            from tools.investigation import write_export
            if arguments.format != 'json':
                raise ControlError('investigation-export supports JSON only')
            write_export(arguments.paths[0], arguments.output, arguments.html)
            return 0
        if arguments.format == 'markdown' and arguments.command != 'host-summary':
            raise ControlError('Markdown output is supported for host-summary only')
        result = {'host-summary': host_summary, 'witness-summary': witness_summary,
            'control-summary': control_summary}[arguments.command](arguments.paths)
        print(markdown(result) if arguments.format == 'markdown' else json.dumps(result, allow_nan=False, sort_keys=True))
        return 0 if result.get('complete', True) else 1
    except (ControlError, OSError, ValueError, UnicodeError, RecursionError, ImportError) as exc:
        print(f'Trace analysis failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
