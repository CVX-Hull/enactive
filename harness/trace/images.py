"""Game-neutral image comparison over sealed PNG frames: perceptual hashes, region diffs, nearest-neighbour lookup.

Pure functions over Pillow and numpy: no global state, no network, no writes. Images are
``uint8`` RGB arrays of shape ``(height, width, 3)``. Hashes are Python ints of ``size * size`` bits.
Nothing here decides what distance means "the same screen"; callers measure that
(see ``tools/phash_measure.py``).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

MAX_PIXELS = 16 * 1000 * 1000
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def load(path) -> np.ndarray:
    """Read a PNG as an RGB ``uint8`` array; reject other formats and images over 16 megapixels."""
    path = Path(path)
    with path.open('rb') as handle:
        if handle.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
            raise ValueError(f'{path}: not a PNG')
    previous = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None  # our own limit below applies before any pixel is decoded
    try:
        with Image.open(path) as image:
            if image.format != 'PNG':
                raise ValueError(f'{path}: not a PNG')
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise ValueError(f'{path}: {width}x{height} exceeds {MAX_PIXELS} pixels')
            return np.asarray(image.convert('RGB'), dtype=np.uint8)
    finally:
        Image.MAX_IMAGE_PIXELS = previous


def _gray(image: np.ndarray, width: int, height: int) -> np.ndarray:
    _check(image)
    resized = Image.fromarray(image).convert('L').resize((width, height), Image.LANCZOS)
    return np.asarray(resized, dtype=np.int16)


def _check(image: np.ndarray) -> None:
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError('image must be a uint8 array of shape (height, width, 3)')
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise ValueError('image is empty')


def _bits(flags: np.ndarray) -> int:
    value = 0
    for flag in flags.ravel():  # row-major, most significant bit first
        value = (value << 1) | int(flag)
    return value


def dhash(image: np.ndarray, size: int = 8) -> int:
    """Difference hash: grayscale, LANCZOS resize to ``size+1`` by ``size``, bit set where a pixel exceeds its right neighbour."""
    small = _gray(image, size + 1, size)
    return _bits(small[:, :-1] > small[:, 1:])


def ahash(image: np.ndarray, size: int = 8) -> int:
    """Average hash: grayscale, LANCZOS resize to ``size`` by ``size``, bit set where a pixel exceeds the mean."""
    small = _gray(image, size, size)
    return _bits(small > small.mean())


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two hashes."""
    return (a ^ b).bit_count()


def region_diff(a: np.ndarray, b: np.ndarray, grid: tuple[int, int] = (4, 4), threshold: int = 16) -> list[dict]:
    """Per-cell change between two same-size images, row-major over a ``(rows, cols)`` grid.

    ``changed_fraction`` is the share of pixels whose largest channel difference exceeds ``threshold``;
    ``mean_abs_diff`` is the mean absolute channel difference. ``box`` is ``[x0, y0, x1, y1]`` (x1, y1 exclusive).
    """
    _check(a)
    _check(b)
    if a.shape != b.shape:
        raise ValueError(f'image sizes differ: {a.shape[:2]} vs {b.shape[:2]}')
    rows, cols = grid
    height, width = a.shape[:2]
    if rows < 1 or cols < 1 or rows > height or cols > width:
        raise ValueError(f'grid {grid} does not fit a {width}x{height} image')
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    cells = []
    for row in range(rows):
        y0, y1 = row * height // rows, (row + 1) * height // rows
        for col in range(cols):
            x0, x1 = col * width // cols, (col + 1) * width // cols
            cell = diff[y0:y1, x0:x1]
            cells.append({
                'row': row, 'col': col, 'box': [x0, y0, x1, y1],
                'changed_fraction': float((cell.max(axis=2) > threshold).mean()),
                'mean_abs_diff': float(cell.mean()),
            })
    return cells


def similar(target_hash: int, index: dict[str, int], k: int = 5, max_distance: int | None = None) -> list[tuple[str, int]]:
    """Up to ``k`` ``(id, distance)`` pairs nearest to ``target_hash``, by distance then id; optionally within ``max_distance``."""
    if k < 0:
        raise ValueError('k must not be negative')
    ranked = sorted(((name, hamming(target_hash, value)) for name, value in index.items()), key=lambda item: (item[1], item[0]))
    if max_distance is not None:
        ranked = [item for item in ranked if item[1] <= max_distance]
    return ranked[:k]


def index(paths) -> dict[str, int]:
    """Map each file stem to the dhash of that PNG; duplicate stems are refused rather than overwritten."""
    result: dict[str, int] = {}
    for path in paths:
        stem = Path(path).stem
        if stem in result:
            raise ValueError(f'duplicate stem {stem!r}')
        result[stem] = dhash(load(path))
    return result
