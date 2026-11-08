"""Workbench commands over a projected `trace/` (#452). Read-only; prints JSON lines.

  python -m harness.trace.workbench steps   <trace> [--actor DIR] [--from N] [--to N] [--kind K]
  python -m harness.trace.workbench frames  <trace> [--actor DIR] [--from N] [--to N]
  python -m harness.trace.workbench tools   <trace> [--actor DIR] [--tool NAME]
  python -m harness.trace.workbench diff    <trace> <frame-a> <frame-b> [--grid RxC] [--min-changed F]
  python -m harness.trace.workbench similar <trace> <frame> [--k K] [--max-distance D]

`--actor` is `<session>/<actor directory>` as in the trace layout. Frames are cited by
source ID. Perceptual-hash distances are measurements, not verdicts: on the sealed #397
frames, consecutive and random pairs overlap heavily (docs/design/trace-workbench.md).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import images


def _actors(trace: Path, only: str | None):
    for steps in sorted(trace.glob('*/*/steps.jsonl')):
        name = f'{steps.parent.parent.name}/{steps.parent.name}'
        if only is None or only == name:
            yield name, steps.parent


def _rows(path: Path):
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip():
                yield json.loads(line)


def _frame(trace: Path, source_id: str) -> Path:
    path = trace/'frames'/f'{source_id}.png'
    if '/' in source_id or not path.is_file():
        raise SystemExit(f'Unknown frame: {source_id}')
    return path


def main(argv=None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('steps', 'frames', 'tools'):
        p = sub.add_parser(name)
        p.add_argument('trace', type=Path)
        p.add_argument('--actor')
        if name != 'tools':
            p.add_argument('--from', dest='start', type=int, default=1)
            p.add_argument('--to', dest='end', type=int)
        if name == 'steps':
            p.add_argument('--kind')
        if name == 'tools':
            p.add_argument('--tool')
    d = sub.add_parser('diff')
    d.add_argument('trace', type=Path)
    d.add_argument('a')
    d.add_argument('b')
    d.add_argument('--grid', default='4x4')
    d.add_argument('--min-changed', type=float, default=0.0)
    s = sub.add_parser('similar')
    s.add_argument('trace', type=Path)
    s.add_argument('frame')
    s.add_argument('--k', type=int, default=5)
    s.add_argument('--max-distance', type=int)
    args = parser.parse_args(argv)

    def emit(row):
        out.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')

    if args.command in ('steps', 'frames'):
        for name, directory in _actors(args.trace, args.actor):
            for step in _rows(directory/'steps.jsonl'):
                if step['seq'] < args.start or (args.end is not None and step['seq'] > args.end):
                    continue
                if args.command == 'steps' and (args.kind is None or step['kind'] == args.kind):
                    emit(dict(actor=name, **step))
                elif args.command == 'frames' and step.get('frame'):
                    emit(dict(actor=name, seq=step['seq'], frame=step['frame'],
                              path=str(_frame(args.trace, step['frame']))))
    elif args.command == 'tools':
        for name, directory in _actors(args.trace, args.actor):
            for call in _rows(directory/'tools.jsonl'):
                if args.tool is None or call['tool'] == args.tool:
                    emit(dict(actor=name, **call))
    elif args.command == 'diff':
        rows, cols = (int(v) for v in args.grid.lower().split('x'))
        cells = images.region_diff(images.load(_frame(args.trace, args.a)), images.load(_frame(args.trace, args.b)),
                                   grid=(rows, cols))
        for cell in cells:
            if cell['changed_fraction'] >= args.min_changed:
                emit(cell)
    elif args.command == 'similar':
        index = images.index(sorted((args.trace/'frames').glob('*.png')))
        target = index.get(args.frame)
        if target is None:
            raise SystemExit(f'Unknown frame: {args.frame}')
        for source_id, distance in images.similar(target, {k: v for k, v in index.items() if k != args.frame},
                                                  k=args.k, max_distance=args.max_distance):
            emit(dict(frame=source_id, distance=distance))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
