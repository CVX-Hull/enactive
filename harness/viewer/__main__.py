"""`python -m harness.viewer`: the read-only viewer process, outside supervision.

    python -m harness.viewer --run <live run dir> --root <evaluation root> --runs <archived runs dir> --port <p>

With `--run`, a background thread evaluates the live run incrementally into its `live` store under `--root`
about once a second. Without it, the viewer only reads the stores already under `--root`. With `--curator-runner-status FILE`, the
spectator's Curator view reads the curator runner's `status.json` read-only at each request. With `--curator-grooming
FILE`, the run that receipt names shows what its boundary grooming spent.
"""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys
from typing import Sequence

import uvicorn

from .app import LOOPBACK_HOSTS, create_app
from .curator import parse_sources
from .frame import FrameSources
from .catalog import Catalog
from .live import LiveEvaluator

BINDINGS = {'cdda': ('harness.evaluation.cdda', 'CddaBinding')}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, help='the live run directory to evaluate incrementally')
    parser.add_argument('--recorded-page', action='store_true', help='serve the recorded spectator at /recorded/ without --run')
    parser.add_argument('--root', type=Path, required=True, help='evaluation record root, e.g. .runtime/evaluations')
    parser.add_argument('--runs', type=Path, action='append', default=[], help='a directory of archived run directories')
    parser.add_argument('--binding', default='cdda', choices=sorted(BINDINGS))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--curator-results', action='append', default=[], metavar='LABEL=FILE')
    parser.add_argument('--curator-sessions', action='append', default=[], metavar='LABEL=FILE')
    parser.add_argument('--curator-drafts', action='append', default=[], metavar='LABEL=DIR')
    parser.add_argument('--curator-runner-status', type=Path, default=None, metavar='FILE',
                        help="the curator runner's status.json, read without a lock at each request")
    parser.add_argument('--curator-grooming', type=Path, default=None, metavar='FILE',
                        help="one boundary grooming receipt (grooming-summary.json), shown only for the run it names")
    arguments = parser.parse_args(argv)
    try:
        curator_results = parse_sources(arguments.curator_results)
        curator_sessions = parse_sources(arguments.curator_sessions)
        curator_drafts = parse_sources(arguments.curator_drafts, 'LABEL=DIR')
    except ValueError as exc:
        parser.error(str(exc))
    if arguments.host not in LOOPBACK_HOSTS:
        parser.error('the viewer serves loopback only')
    if arguments.recorded_page and arguments.run is not None:
        parser.error('--recorded-page cannot be combined with --run')
    evaluator = None
    if arguments.run is not None:
        module, attribute = BINDINGS[arguments.binding]
        evaluator = LiveEvaluator(arguments.run, arguments.root, getattr(importlib.import_module(module), attribute)())
        evaluator.start()
    catalog = Catalog(arguments.root, tuple(arguments.runs), arguments.run)
    try:
        app = create_app(catalog, evaluator, frame_sources=FrameSources(curator_results=curator_results,
            curator_sessions=curator_sessions, curator_runner_status=arguments.curator_runner_status,
            curator_grooming=arguments.curator_grooming, curator_drafts=curator_drafts), recorded_page=arguments.recorded_page)
        uvicorn.run(app, host=arguments.host, port=arguments.port, log_level='warning')
    finally:
        if evaluator is not None:
            evaluator.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
