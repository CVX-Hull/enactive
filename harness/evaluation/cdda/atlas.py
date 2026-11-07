"""The glyph atlas (data) and the command that regenerates it.

The atlas maps the 16-byte packed ink mask of an 8x16 cell to one character. It is
data, so another font or game re-learns it with `learn`:

    python -m harness.evaluation.cdda.atlas learn SESSION_DIR... --out atlas.json [--font Terminus.ttf]

A SESSION_DIR holds `sources/*.png`; a directory of sessions expands to its children.

Learning aligns known static strings (`anchors.json`: label text at a known cell of
the sidebar, main menu, creation and death screens) with the recorded frames. The
modal ink mask at each anchor character is that character's glyph. With `--font`,
printable ASCII the anchors do not cover (digits, capitals in names) is added from
the same font rendered at the game's size, after every anchor-learned glyph is
checked to equal its font rendering. Glyphs in the atlas derive from the Terminus
font (SIL OFL 1.1) as rendered by CDDA; see NOTICE.md.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

ATLAS_PATH = Path(__file__).with_name('atlas.json')
ANCHORS_PATH = Path(__file__).with_name('anchors.json')
ATLAS_VERSION = 1
CELL_W, CELL_H = 8, 16


@dataclass(frozen=True)
class Atlas:
    glyphs: dict[bytes, str]

    @classmethod
    def load(cls, path: Path | None = None) -> 'Atlas':
        document = json.loads((path or ATLAS_PATH).read_text())
        if document.get('version') != ATLAS_VERSION or document.get('cell') != [CELL_W, CELL_H]:
            raise ValueError(f'unsupported glyph atlas version or cell size in {path or ATLAS_PATH}')
        glyphs: dict[bytes, str] = {}
        for entry in document['glyphs']:
            key = bytes.fromhex(entry['rows'])
            if len(key) != CELL_H or key in glyphs:
                raise ValueError(f'invalid or duplicate atlas glyph {entry["ch"]!r}')
            glyphs[key] = entry['ch']
        return cls(glyphs)

    def characters(self) -> str:
        return ''.join(sorted(set(self.glyphs.values())))


def expand_sessions(paths: list[Path]) -> list[Path]:
    """A session directory (has `sources/`) stands for itself; any other directory for its session children."""
    found: list[Path] = []
    for path in paths:
        if (path / 'sources').is_dir():
            found.append(path)
        else:
            found.extend(sorted(child for child in path.iterdir() if (child / 'sources').is_dir()))
    return found


def _frame_array(path: Path) -> np.ndarray | None:
    with Image.open(path) as image:
        if image.size != (960, 640):
            return None
        return np.asarray(image.convert('RGB'))


def _render_font(font_path: Path) -> dict[str, bytes]:
    from PIL import ImageDraw, ImageFont
    font = ImageFont.truetype(str(font_path), 16)
    rendered: dict[str, bytes] = {}
    for code in range(33, 127):
        canvas = Image.new('L', (CELL_W, CELL_H), 0)
        drawer = ImageDraw.Draw(canvas)
        drawer.fontmode = '1'
        drawer.text((0, 0), chr(code), font=font, fill=255)
        mask = np.asarray(canvas) > 0
        rendered[chr(code)] = np.packbits(mask, axis=1).tobytes()
    return rendered


def _text_like(key: bytes) -> bool:
    """Reject cells that cannot be a Terminus letter: hatch fills and window-border lines.

    Terminus text keeps its top row clear and never fills a whole 8-pixel row; overmap hatching
    and the window frame do.
    """
    return key[0] == 0 and 0xFF not in key


def learn(sessions: list[Path], out: Path, font_path: Path | None, stride: int = 1) -> dict:
    from harness.evaluation.cdda.screen import ink_keys
    anchors = json.loads(ANCHORS_PATH.read_text())['anchors']
    frames = 0
    # An anchor is learned from the modal appearance of its whole string, not cell by cell, so
    # static tile art that happens to sit under a menu anchor cannot supply a glyph.
    layouts: list[list[tuple[str, tuple[int, int]]]] = []
    for anchor in anchors:
        layouts.append([(char, (anchor['x0'] + (anchor['col'] + offset) * CELL_W, anchor['row'] * CELL_H))
                        for offset, char in enumerate(anchor['text']) if char != ' '])
    appearances: list[collections.Counter] = [collections.Counter() for _ in anchors]
    for session in sessions:
        for path in sorted((session / 'sources').glob('*.png'))[::stride]:
            arr = _frame_array(path)
            if arr is None:
                continue
            frames += 1
            for n, layout in enumerate(layouts):
                keys = ink_keys(arr, [xy for _, xy in layout])
                if all(key is not None and _text_like(key) for key in keys):
                    appearances[n][tuple(keys)] += 1
    # Best-supported anchors first. An anchor that contradicts glyphs already learned (a rare
    # screen whose modal appearance is not the label) is skipped and reported, never merged.
    ranked = sorted((n for n in range(len(layouts)) if appearances[n]),
                    key=lambda n: -appearances[n].most_common(1)[0][1])
    learned: dict[str, tuple[bytes, int]] = {}
    owner: dict[bytes, str] = {}
    skipped: list[str] = []
    for n in ranked:
        keys, count = appearances[n].most_common(1)[0]
        text = anchors[n]['text']
        if count < 5:
            skipped.append(text)
            continue
        pairs = [(char, key) for (char, _), key in zip(layouts[n], keys)]
        if any((char in learned and learned[char][0] != key) or owner.get(key, char) != char for char, key in pairs):
            skipped.append(text)
            continue
        if len({c for c, _ in pairs}) != len({k for _, k in pairs}):
            skipped.append(text)
            continue
        for char, key in pairs:
            learned[char] = (key, learned.get(char, (key, 0))[1] + count)
            owner[key] = char
    entries = {char: {'ch': char, 'rows': key.hex(), 'source': 'frame', 'seen': count} for char, (key, count) in learned.items()}
    mismatches: list[str] = []
    if font_path is not None:
        rendered = _render_font(font_path)
        for char, key in rendered.items():
            if char in entries:
                if entries[char]['rows'] != key.hex():
                    mismatches.append(char)
            elif key not in {bytes.fromhex(e['rows']) for e in entries.values()}:
                entries[char] = {'ch': char, 'rows': key.hex(), 'source': 'font', 'seen': 0}
        if mismatches:
            raise SystemExit(f'font rendering disagrees with frames for {mismatches!r}; refusing to write the atlas')
    document = {
        'version': ATLAS_VERSION,
        'cell': [CELL_W, CELL_H],
        'font': 'Terminus (SIL OFL 1.1) as rendered by CDDA',
        'glyphs': [entries[c] for c in sorted(entries)],
    }
    out.write_text(json.dumps(document, indent=0) + '\n')
    return {
        'frames': frames,
        'anchor_characters': ''.join(sorted(learned)),
        'font_added': ''.join(sorted(c for c, e in entries.items() if e['source'] == 'font')),
        'total': len(entries),
        'skipped_anchors': skipped,
    }


def unknown_cells(sessions: list[Path], atlas: Atlas, stride: int = 3, limit: int = 12) -> list[tuple[int, str]]:
    """Most frequent sidebar cell masks the atlas cannot decode (to review what is missing)."""
    from harness.evaluation.cdda.screen import ink_keys
    cells = [(616 + c * CELL_W, r * CELL_H) for r in range(28) for c in range(43)]
    counter: collections.Counter = collections.Counter()
    for session in sessions:
        for path in sorted((session / 'sources').glob('*.png'))[::stride]:
            arr = _frame_array(path)
            if arr is None:
                continue
            for key in ink_keys(arr, cells):
                if key is not None and key not in atlas.glyphs:
                    counter[key] += 1
    return [(count, key.hex()) for key, count in counter.most_common(limit)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m harness.evaluation.cdda.atlas')
    commands = parser.add_subparsers(dest='command', required=True)
    learn_parser = commands.add_parser('learn', help='learn glyphs from recorded sessions')
    learn_parser.add_argument('sessions', nargs='+', type=Path)
    learn_parser.add_argument('--out', type=Path, required=True)
    learn_parser.add_argument('--font', type=Path, default=None)
    learn_parser.add_argument('--stride', type=int, default=1)
    check_parser = commands.add_parser('unknown', help='list sidebar cells the atlas cannot decode')
    check_parser.add_argument('sessions', nargs='+', type=Path)
    check_parser.add_argument('--atlas', type=Path, default=ATLAS_PATH)
    args = parser.parse_args(argv)
    sessions = expand_sessions(args.sessions)
    if args.command == 'learn':
        print(json.dumps(learn(sessions, args.out, args.font, args.stride), indent=1))
    else:
        for count, rows in unknown_cells(sessions, Atlas.load(args.atlas)):
            print(count, rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
