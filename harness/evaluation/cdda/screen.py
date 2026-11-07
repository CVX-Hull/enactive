"""Cell-grid text decoding for the CDDA window (960x640, 8x16 Terminus cells).

CDDA draws text with a fixed bitmap font, so every glyph in a cell is either the
cell's background or one foreground colour. A cell is therefore decoded by exact
lookup of its ink mask in the glyph atlas. A cell whose ink is not one uniform
colour, or whose mask is not in the atlas, decodes to `UNKNOWN`; readers abstain
instead of guessing when a required field contains it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from harness.evaluation.cdda.atlas import Atlas

CELL_W, CELL_H = 8, 16
FRAME_W, FRAME_H = 960, 640
UNKNOWN = '\x00'

# Colours of the default CDDA scheme as drawn by this build (packed 0xRRGGBB).
COLOURS = {
    0xFF0000: 'red',
    0xFF9696: 'light_red',
    0xFFFF00: 'yellow',
    0x006E00: 'green',
    0x00FF00: 'light_green',
    0x969696: 'light_gray',
    0x636363: 'dark_gray',
    0xFFFFFF: 'white',
}


def colour_name(packed: int) -> str:
    return COLOURS.get(packed, f'#{packed:06x}')


@dataclass(frozen=True)
class Grid:
    """Decoded cells: `rows[r]` is a string of `cols` characters (space = empty)."""

    rows: tuple[str, ...]
    colours: tuple[tuple[int, ...], ...]

    def text(self, row: int, c0: int, c1: int) -> str:
        return self.rows[row][c0:c1]

    def colour(self, row: int, c0: int, c1: int) -> int:
        """Most common ink colour in the span (0 when the span is empty)."""
        found: dict[int, int] = {}
        for value in self.colours[row][c0:c1]:
            if value:
                found[value] = found.get(value, 0) + 1
        return max(found, key=found.get) if found else 0


def ink_keys(arr: np.ndarray, cells_xy: list[tuple[int, int]]) -> list[bytes | None]:
    """Packed ink masks (16 bytes) for cells at pixel origins; None for blank cells."""
    out: list[bytes | None] = []
    for x, y in cells_xy:
        cell = arr[y:y + CELL_H, x:x + CELL_W]
        if cell.shape[:2] != (CELL_H, CELL_W):
            out.append(None)
            continue
        flat = cell.reshape(-1, 3)
        mask = (flat != flat[0]).any(axis=1)
        if not mask.any():
            out.append(None)
            continue
        ink = flat[mask]
        if (ink != ink[0]).any():
            out.append(None)  # not one foreground colour: tile art, not text
            continue
        out.append(np.packbits(mask.reshape(CELL_H, CELL_W), axis=1).tobytes())
    return out


def decode_grid(arr: np.ndarray, x0: int, y0: int, rows: int, cols: int, atlas: Atlas) -> Grid:
    """Decode a `rows` x `cols` block of cells whose top-left pixel is (x0, y0)."""
    height, width = arr.shape[0], arr.shape[1]
    if y0 + rows * CELL_H > height or x0 + cols * CELL_W > width:
        raise ValueError('cell block outside the frame')
    sub = arr[y0:y0 + rows * CELL_H, x0:x0 + cols * CELL_W].astype(np.uint32)
    packed = (sub[..., 0] << 16) | (sub[..., 1] << 8) | sub[..., 2]
    cells = packed.reshape(rows, CELL_H, cols, CELL_W).transpose(0, 2, 1, 3).reshape(rows * cols, CELL_H * CELL_W)
    background = cells[:, 0]
    mask = cells != background[:, None]
    inked = mask.any(axis=1)
    first = mask.argmax(axis=1)
    foreground = cells[np.arange(cells.shape[0]), first]
    uniform = ((cells == foreground[:, None]) | ~mask).all(axis=1)
    keys = np.packbits(mask.reshape(-1, CELL_H, CELL_W), axis=2).reshape(-1, CELL_H).tobytes()
    chars = [' '] * (rows * cols)
    colours = [0] * (rows * cols)
    for n in np.nonzero(inked)[0].tolist():
        if not uniform[n]:
            chars[n] = UNKNOWN
            continue
        glyph = atlas.glyphs.get(keys[n * CELL_H:(n + 1) * CELL_H])
        chars[n] = UNKNOWN if glyph is None else glyph
        colours[n] = int(foreground[n])
    return Grid(
        tuple(''.join(chars[r * cols:(r + 1) * cols]) for r in range(rows)),
        tuple(tuple(colours[r * cols:(r + 1) * cols]) for r in range(rows)),
    )


def decode_line(arr: np.ndarray, x: int, y: int, cols: int, atlas: Atlas) -> str:
    """Decode one line of cells at an arbitrary pixel origin (for windows off the cell grid)."""
    if x < 0 or y < 0 or y + CELL_H > arr.shape[0] or x + cols * CELL_W > arr.shape[1]:
        return ''
    return decode_grid(arr, x, y, 1, cols, atlas).rows[0]
