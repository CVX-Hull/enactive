"""Build the one isolated SDL candidate using already prepared frameworks."""
from __future__ import annotations

from typing import Any

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def build(output: Path) -> dict[str, Any]:
    if sys.platform != 'darwin':
        raise RuntimeError('This candidate is qualified only on the current Mac')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    resources = ROOT / '.runtime/Cataclysm.app/Contents/Resources'
    if not (resources / 'SDL2.framework/Headers/SDL.h').is_file():
        raise RuntimeError('Prepared project-local SDL frameworks unavailable')
    flags = ['/usr/bin/clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-F', str(resources),
             '-framework', 'SDL2', '-framework', 'SDL2_image', '-Wl,-rpath,' + str(resources)]
    commands = [flags + ['-dynamiclib', '-fobjc-arc', '-framework', 'Foundation',
        str(Path(__file__).with_name('bridge.mm')), '-o', str(output / 'bridge.dylib')],
        flags + [str(Path(__file__).with_name('fixture.cpp')), '-o', str(output / 'fixture')]]
    for command in commands:
        subprocess.run(command, check=True, cwd=ROOT)
    inputs = [Path(__file__), Path(__file__).with_name('bridge.mm'), Path(__file__).with_name('fixture.cpp')]
    manifest = dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    source_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
                    inputs={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                    commands=commands, outputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (output / 'bridge.dylib', output / 'fixture')})
    (output / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/computer-control-build')
    options = parser.parse_args()
    print(json.dumps(build(options.output), indent=2))
