"""Build the sole macOS SDL mechanical adapter with explicit local resources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build(resources: Path, output: Path) -> dict:
    if sys.platform != 'darwin':
        raise RuntimeError('The current SDL adapter is qualified only on macOS')
    resources, output = resources.resolve(strict=True), output.resolve()
    if not resources.is_relative_to(ROOT) or not output.is_relative_to(ROOT):
        raise ValueError('Build resources and outputs must be project-local')
    if not (resources / 'SDL2.framework/Headers/SDL.h').is_file():
        raise RuntimeError('Prepared local SDL framework unavailable')
    output.mkdir(parents=True, exist_ok=False)
    native = ROOT / 'harness/computer/native'
    flags = ['/usr/bin/clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-F', str(resources),
             '-framework', 'SDL2', '-framework', 'SDL2_image', '-Wl,-rpath,' + str(resources)]
    commands = [flags + ['-dynamiclib', '-fobjc-arc', '-framework', 'Foundation',
        str(native / 'bridge.mm'), '-o', str(output / 'bridge.dylib')],
        flags + [str(native / 'fixture.cpp'), '-o', str(output / 'fixture')]]
    for command in commands:
        subprocess.run(command, check=True, cwd=ROOT)
    inputs = [Path(__file__), native / 'bridge.mm', native / 'fixture.cpp']
    manifest = dict(schema='computer-build/1',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        inputs={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        commands=commands, outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (output / 'bridge.dylib', output / 'fixture')})
    (output / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.resources, args.output), indent=2))
