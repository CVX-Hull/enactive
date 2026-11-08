"""Measure dhash distances between consecutive sealed frames versus random pairs (ADR 009 R8).

Read-only over ``<dir>/*/sources/*.png``; writes only the JSON report named by ``--out``.
Reports distributions only. It does not propose or imply a similarity threshold.

    python tools/phash_measure.py <computer-sessions dir> --out <json path>
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.trace import images  # noqa: E402

SEED = 452


def frame_number(path: Path):
    """The integer after the last '-' in the stem, or None when the stem has none."""
    tail = path.stem.rsplit('-', 1)[-1] if '-' in path.stem else ''
    return int(tail) if tail.isdigit() else None


def summarise(distances: list[int]) -> dict:
    if not distances:
        return {'count': 0}
    d = np.asarray(distances)
    return {
        'count': int(d.size), 'median': float(np.median(d)),
        'p10': float(np.percentile(d, 10)), 'p90': float(np.percentile(d, 90)),
        'share_le_5': float((d <= 5).mean()), 'share_le_10': float((d <= 10).mean()),
    }


def measure_session(frames: list[Path]) -> dict:
    """Consecutive and random-pair distances for one session's frames, plus pixel-identical consecutive count."""
    hashes, consecutive, identical, skipped = [], [], 0, []
    previous = None
    for path in frames:
        try:
            pixels = images.load(path)
        except (ValueError, OSError) as exc:
            skipped.append({'file': path.name, 'reason': str(exc)})
            continue
        hashes.append(images.dhash(pixels))
        if previous is not None and previous.shape == pixels.shape and np.array_equal(previous, pixels):
            identical += 1
        previous = pixels
    consecutive = [images.hamming(a, b) for a, b in zip(hashes, hashes[1:])]
    rng = random.Random(SEED)
    randoms = []
    if len(hashes) >= 2:
        for _ in consecutive:
            i, j = rng.sample(range(len(hashes)), 2)
            randoms.append(images.hamming(hashes[i], hashes[j]))
    return {
        'frames': len(hashes), 'skipped': skipped, 'identical_consecutive': identical,
        'consecutive': consecutive, 'random': randoms,
    }


def report(root: Path) -> dict:
    sessions, pooled_c, pooled_r, pooled_identical = {}, [], [], 0
    for session in sorted(p for p in root.iterdir() if (p / 'sources').is_dir()):
        numbered = [(frame_number(p), p) for p in (session / 'sources').glob('*.png')]
        unnumbered = sorted(p.name for n, p in numbered if n is None)
        frames = [p for n, p in sorted((n, p) for n, p in numbered if n is not None)]
        result = measure_session(frames)
        pairs = len(result['consecutive'])
        sessions[session.name] = {
            'frames': result['frames'], 'consecutive_pairs': pairs,
            'unnumbered_files_ignored': unnumbered, 'skipped': result['skipped'],
            'pixel_identical_share': result['identical_consecutive'] / pairs if pairs else None,
            'consecutive': summarise(result['consecutive']), 'random': summarise(result['random']),
        }
        pooled_c += result['consecutive']
        pooled_r += result['random']
        pooled_identical += result['identical_consecutive']
    return {
        'source': str(root), 'seed': SEED, 'hash': 'dhash size=8 (64 bit), LANCZOS',
        'note': 'distributions only; no threshold is proposed',
        'pooled': {
            'sessions': len(sessions), 'consecutive_pairs': len(pooled_c),
            'pixel_identical_share': pooled_identical / len(pooled_c) if pooled_c else None,
            'consecutive': summarise(pooled_c), 'random': summarise(pooled_r),
        },
        'sessions': sessions,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('sessions', type=Path, help='directory of <session>/sources/*.png')
    parser.add_argument('--out', type=Path, required=True, help='JSON report path (never inside the sessions directory)')
    args = parser.parse_args(argv)
    root = args.sessions.resolve()
    if not root.is_dir():
        parser.error(f'{root} is not a directory')
    out = args.out.resolve()
    if root in out.parents:
        parser.error('--out must not be inside the evidence directory')
    data = report(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data['pooled'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
