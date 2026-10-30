#!/usr/bin/env python3
"""Read-only current telemetry diagnostics; selected paths only, no gameplay verdict.

host-summary selects current telemetry/2 files, actor directories or campaign
folders (4096 files / 8 GiB; 64 MiB per line; two million events per trace).
witness-summary selects one computer-session/1 database/directory and 1..32
observer-timing/4 exports (64 MiB each / 256 MiB total; 2000 rows per export).
control-summary selects 1..32 computer-session/1 databases/directories (512 MiB
per database including SQLite sidecars; 200000 rows per selected table).
investigation-export selects 1..4 explicitly closed cases and writes a bounded
observer-investigation/1 bundle, optionally with the shared recorded HTML reader.
Unsupported historical formats remain inert evidence, available in Git history.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from harness.computer.protocol import ControlError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('host-summary', 'witness-summary', 'control-summary', 'investigation-export'))
    parser.add_argument('paths', type=Path, nargs='+')
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--html', type=Path)
    arguments = parser.parse_args(argv)
    if arguments.command == 'investigation-export' and (len(arguments.paths) != 1 or arguments.output is None):
        parser.error('investigation-export requires one selection file and --output')
    if arguments.command != 'investigation-export' and (arguments.output is not None or arguments.html is not None):
        parser.error('--output and --html are supported for investigation-export only')
    from tools.host_analysis import host_summary, markdown
    from tools.observer_analysis import witness_summary
    from tools.control_analysis import control_summary
    try:
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
    except (ControlError, OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(f'Trace analysis failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
