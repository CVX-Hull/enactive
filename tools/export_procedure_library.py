#!/usr/bin/env python3
"""Export sealed current missions to the single current advisory donor format."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.gameplay.advisory_export import DEFAULT_EXPORT_BYTES, export_current
from harness.gameplay.contracts import json_object


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', required=True, type=Path,
        help='JSON object with sources (new sealed current missions) and dependencies (existing exports) arrays')
    parser.add_argument('--max-bytes', type=int, default=DEFAULT_EXPORT_BYTES,
        help='Prospective total output byte appetite, including all retained PNGs')
    args = parser.parse_args()
    if subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=ROOT, text=True).strip():
        parser.error('Freeze tracked source and new source files in a commit before exporting')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    with args.pins.open('rb') as stream:
        encoded = stream.read(65_537)
    if len(encoded) > 65_536:
        parser.error('Pin file exceeds64KiB')
    specification = json_object(encoded)
    if (set(specification) != {'sources', 'dependencies'} or type(specification['sources']) is not list
            or type(specification['dependencies']) is not list):
        parser.error('Pin file requires exactly sources and dependencies arrays')
    outputs = export_current(ROOT, specification['sources'], dependencies=specification['dependencies'],
                             validator_revision=revision, max_bytes=args.max_bytes)
    for path in outputs:
        print(path.relative_to(ROOT))


if __name__ == '__main__':
    main()
