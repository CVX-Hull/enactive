"""`python -m harness.viewer`: the read-only viewer process, outside supervision.

    python -m harness.viewer --run <live run dir> --root <evaluation root> --runs <archived runs dir> --port <p>

With `--run`, a background thread evaluates the live run incrementally into its `live` store under `--root`
about once a second. Without it, the viewer only reads the stores already under `--root`.
"""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys
from typing import Sequence

import uvicorn

from .app import create_app
from .catalog import Catalog
from .live import LiveEvaluator

BINDINGS = {'cdda': ('harness.evaluation.cdda', 'CddaBinding')}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, help='the live run directory to evaluate incrementally')
    parser.add_argument('--root', type=Path, required=True, help='evaluation record root, e.g. .runtime/evaluations')
    parser.add_argument('--runs', type=Path, action='append', default=[], help='a directory of archived run directories')
    parser.add_argument('--binding', default='cdda', choices=sorted(BINDINGS))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    arguments = parser.parse_args(argv)
    if arguments.host not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('the viewer serves loopback only')
    evaluator = None
    if arguments.run is not None:
        module, attribute = BINDINGS[arguments.binding]
        evaluator = LiveEvaluator(arguments.run, arguments.root, getattr(importlib.import_module(module), attribute)())
        evaluator.start()
    catalog = Catalog(arguments.root, tuple(arguments.runs), arguments.run)
    try:
        uvicorn.run(create_app(catalog, evaluator), host=arguments.host, port=arguments.port, log_level='warning')
    finally:
        if evaluator is not None:
            evaluator.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
