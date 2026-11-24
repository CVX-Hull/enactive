"""CDDA screen readers (version 1): pure functions of one decoded frame.

Layout facts (960x640 frame, 8x16 cells): the main-view sidebar starts at x=616 and is
43 cells wide. Every reader returns `(value, confidence, abstain_reason)`; a reader abstains
when a field it needs is occluded or contains an undecodable glyph, never guesses.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from harness.evaluation.cdda.atlas import Atlas
from harness.evaluation.cdda.screen import CELL_H, CELL_W, FRAME_H, FRAME_W, UNKNOWN, Grid, colour_name, decode_grid, decode_line

READER_VERSION = 1
#: The mode classifier: version 2 reads a game screen the player works in as `ui`, apart from `prompt`.
MODE_READER_VERSION = 2
SIDEBAR_X, SIDEBAR_COLS, SIDEBAR_ROWS = 616, 43, 28
MAP_REGION = (0, 0, 608, 640)

# Season length of the default world. A world with another length shifts only the
# absolute offset between seasons; differences inside one season are unaffected.
SEASON_DAYS = 91
SEASONS = ('Spring', 'Summer', 'Autumn', 'Winter')
YEAR_SECONDS = len(SEASONS) * SEASON_DAYS * 86400

# Label cells that identify the main-view sidebar: (name, row, col).
ANCHORS = (('L ARM', 0, 0), ('L LEG', 1, 0), ('Sound:', 2, 0), ('Str:', 4, 0), ('Weariness:', 6, 0),
           ('Pain:', 8, 0), ('Thirst:', 8, 22), ('Hunger:', 9, 22), ('Date:', 16, 0), ('Time:', 17, 0), ('Wield:', 19, 0))

# Need ladders, worst to best, as drawn by the game (display.cpp strings, matched case-insensitively
# without a trailing '!'). '' is the unlabelled normal state. Values are hand-spaced, 0 worst, 1 best.
THIRST = {'parched': 0.0, 'dehydrated': 0.15, 'very thirsty': 0.3, 'thirsty': 0.5, '': 0.85,
          'slaked': 0.9, 'hydrated': 0.95, 'turgid': 1.0}
THIRST_CRITICAL = {'very thirsty', 'dehydrated', 'parched'}
HUNGER = {'starving': 0.0, 'near starving': 0.1, 'famished': 0.2, 'very hungry': 0.35, 'hungry': 0.5,
          'peckish': 0.7, '': 0.85, 'satisfied': 0.9, 'full': 0.95, 'engorged': 1.0}
HUNGER_CRITICAL = {'very hungry', 'famished', 'near starving', 'starving'}
WEARINESS = {'extreme': 0.0, 'very': 0.2, 'very weary': 0.2, 'weary': 0.45, 'moderate': 0.7, 'light': 0.85, 'fresh': 1.0}
WEARINESS_CRITICAL = {'extreme'}
REST = {'exhausted': 0.0, 'dead tired': 0.2, 'tired': 0.5, '': 1.0}
REST_CRITICAL = {'dead tired', 'exhausted'}
PAIN = {'severe pain': 0.0, 'intense pain': 0.1, 'unmanageable pain': 0.25, 'distressing pain': 0.4,
        'distracting pain': 0.5, 'moderate pain': 0.65, 'mild pain': 0.8, 'minimal pain': 0.9, '': 1.0}
PAIN_CRITICAL = {'severe pain', 'intense pain'}
RED = {0xFF0000, 0xFF9696}

LIMBS = (('head', 0, 23), ('torso', 1, 23), ('l_arm', 0, 8), ('r_arm', 0, 37), ('l_leg', 1, 8), ('r_leg', 1, 37))
LIMB_GLYPH = {'|': 1.0, '\\': 0.5, '.': 0.0}

CLOCK_DATE = re.compile(r'^(?:Year (\d{1,3}), )?(Spring|Summer|Autumn|Winter), day (\d{1,3})$')
# Two-digit hours are drawn without the space ("10:05:14AM"); one-digit hours keep it ("8:00:01 AM").
CLOCK_TIME = re.compile(r'^(\d{1,2}):(\d\d):(\d\d) ?(AM|PM)$')

Result = tuple[object | None, float | None, str | None]


def abstain(reason: str) -> Result:
    return None, None, reason


@dataclass
class Frame:
    """One decoded frame: pixels plus lazily built text grids."""

    arr: np.ndarray
    atlas: Atlas
    _side: Grid | None = None

    @property
    def side(self) -> Grid:
        if self._side is None:
            self._side = decode_grid(self.arr, SIDEBAR_X, 0, SIDEBAR_ROWS, SIDEBAR_COLS, self.atlas)
        return self._side

    def anchors_present(self) -> int:
        return sum(1 for name, row, col in ANCHORS if self.side.text(row, col, col + len(name)) == name)

    def label_ok(self, name: str, row: int, col: int) -> bool:
        return self.side.text(row, col, col + len(name)) == name


def _bare(text: str) -> str:
    return text.strip().lower().rstrip('!').strip()


def parse_clock(date_text: str, time_text: str) -> int | None:
    """Absolute game seconds from the sidebar's date and time strings; None if either is malformed."""
    d = CLOCK_DATE.match(date_text.strip())
    t = CLOCK_TIME.match(time_text.strip())
    if not d or not t:
        return None
    hour, minute, second = int(t[1]), int(t[2]), int(t[3])
    if not (1 <= hour <= 12 and minute < 60 and second < 60):
        return None
    day = int(d[3])
    if not 1 <= day <= 366:
        return None
    hour = hour % 12 + (12 if t[4] == 'PM' else 0)
    year = int(d[1]) - 1 if d[1] else 0
    days = year * len(SEASONS) * SEASON_DAYS + SEASONS.index(d[2]) * SEASON_DAYS + day - 1
    return days * 86400 + hour * 3600 + minute * 60 + second


def read_clock(frame: Frame) -> Result:
    side = frame.side
    date_ok, time_ok = frame.label_ok('Date:', 16, 0), frame.label_ok('Time:', 17, 0)
    date_text, time_text = side.text(16, 10, SIDEBAR_COLS).rstrip(), side.text(17, 10, SIDEBAR_COLS).rstrip()
    if UNKNOWN in date_text or UNKNOWN in time_text:
        return abstain('unknown_glyph')
    # The value must end before the row's last cell; a popup edge cutting through it leaves a border glyph.
    value = parse_clock(date_text, time_text)
    if value is None:
        return abstain('clock_not_legible')
    return value, 0.99 if date_ok and time_ok else 0.85, None


def _field(frame: Frame, label: tuple[str, int, int], c0: int, c1: int) -> tuple[str | None, int, str | None]:
    name, row, col = label
    if not frame.label_ok(name, row, col):
        return None, 0, 'label_occluded'
    text = frame.side.text(row, c0, c1)
    if UNKNOWN in text:
        # The sidebar ends an over-long label with one truncation glyph ("Distracting p<mark>");
        # a prefix of 12 or more characters still names exactly one label (see _ladder_value).
        stripped = text.rstrip()
        if stripped.endswith(UNKNOWN) and stripped.count(UNKNOWN) == 1 and len(stripped[:-1].strip()) >= 12:
            text = stripped[:-1]
        else:
            return None, 0, 'unknown_glyph'
    return text.strip(), frame.side.colour(row, c0, c1), None


def _ladder_value(text: str, ladder: dict[str, float]) -> tuple[str, float] | None:
    key = _bare(text)
    if key in ladder:
        return key, ladder[key]
    if len(key) >= 12:  # the sidebar truncates long labels at the column edge
        hits = [label for label in ladder if label.startswith(key)]
        if len(hits) == 1:
            return hits[0], ladder[hits[0]]
    return None


def _need(frame: Frame, label, c0, c1, ladder, critical) -> Result:
    text, colour, reason = _field(frame, label, c0, c1)
    if reason:
        return abstain(reason)
    hit = _ladder_value(text, ladder)
    if hit is None:
        return abstain('unknown_label')
    key, value = hit
    return {'label': key, 'level': value, 'critical': key in critical or colour in RED and key != '',
            'colour': colour_name(colour) if colour else None}, 0.97, None


def read_thirst(frame: Frame) -> Result:
    return _need(frame, ('Thirst:', 8, 22), 30, SIDEBAR_COLS, THIRST, THIRST_CRITICAL)


def read_hunger(frame: Frame) -> Result:
    return _need(frame, ('Hunger:', 9, 22), 30, SIDEBAR_COLS, HUNGER, HUNGER_CRITICAL)


def read_pain(frame: Frame) -> Result:
    return _need(frame, ('Pain:', 8, 0), 6, 22, PAIN, PAIN_CRITICAL)


def read_weariness(frame: Frame) -> Result:
    """Weariness is the worse of the 'Weariness:' level and the 'Rest:' tiredness label."""
    wear = _need(frame, ('Weariness:', 6, 0), 11, 22, WEARINESS, WEARINESS_CRITICAL)
    rest = _need(frame, ('Rest:', 9, 0), 6, 22, REST, REST_CRITICAL)
    if wear[2] or rest[2]:
        return abstain(wear[2] or rest[2])
    worse = min((wear[0], rest[0]), key=lambda r: r['level'])
    return {'label': worse['label'], 'level': worse['level'], 'critical': wear[0]['critical'] or rest[0]['critical'],
            'weariness': wear[0]['label'], 'rest': rest[0]['label'], 'colour': worse['colour']}, 0.97, None


def read_limbs(frame: Frame) -> dict[str, Result]:
    side = frame.side
    out: dict[str, Result] = {}
    if not (frame.label_ok('L ARM', 0, 0) and frame.label_ok('L LEG', 1, 0)):
        return {limb: abstain('label_occluded') for limb, _, _ in LIMBS}
    for limb, row, col in LIMBS:
        cells = side.text(row, col, col + 5)
        if UNKNOWN in cells or any(c not in LIMB_GLYPH for c in cells):
            out[limb] = abstain('bar_not_legible')
            continue
        parts = [LIMB_GLYPH[c] for c in cells]
        if parts != sorted(parts, reverse=True):
            out[limb] = abstain('bar_not_monotone')
            continue
        colour = side.colour(row, col, col + 5)
        value = sum(parts) / 5
        critical = colour in RED if colour else value <= 0.2
        out[limb] = {'level': value, 'critical': critical, 'colour': colour_name(colour) if colour else None}, 0.95, None
    return out


# Threat: parsed from the sidebar creature list (rows 24-26).
ENTRY = re.compile(r'^(\S) (?:(\d+) )?(.+)$')
# Creature names in the list are lower case ("feral human", "fat zombie"); a person's own name
# starts with a capital ("Smokes", "Roseann Romo") and is not a creature to count.
PERSON_NAME = re.compile(r'^[A-Z]')
THREAT_LOW, THREAT_HIGH, THREAT_LETHAL = 1, 3, 10


def threat_bucket(count: int) -> str:
    """Bucket thresholds (weak evidence: see the self-check; deaths came with crowds of ten or more)."""
    if count >= THREAT_LETHAL:
        return 'lethal'
    if count >= THREAT_HIGH:
        return 'high'
    return 'low' if count >= THREAT_LOW else 'none'


def read_threat(frame: Frame) -> Result:
    side = frame.side
    if not frame.label_ok('Weight :', 27, 0) and not frame.label_ok('SW:', 23, 0):
        return abstain('list_occluded')
    count, entries, flagged = 0, 0, False
    full = all(side.rows[r].strip() for r in (24, 25, 26))
    for r in (24, 25, 26):
        line = side.rows[r].rstrip()
        if not line:
            continue
        if UNKNOWN in line:
            flagged = True
            line = line.replace(UNKNOWN, '?')
        for part in re.split(r' {2,}', line.strip()):
            m = ENTRY.match(part)
            if not m:
                flagged = True
                continue
            if PERSON_NAME.match(m[3]) and not m[2]:
                continue  # a named person is not counted as a threat
            entries += 1
            count += int(m[2]) if m[2] else 1
    confidence = 0.5 if flagged else 0.6 if full else 0.8
    return {'count': count, 'entries': entries, 'bucket': threat_bucket(count)}, confidence, None


def _border_gray(arr: np.ndarray) -> np.ndarray:
    """Pixels in a window-border gray (150 or 128)."""
    px = arr.astype(np.int16)
    return (px[..., 0] == px[..., 1]) & (px[..., 1] == px[..., 2]) & ((px[..., 0] == 150) | (px[..., 0] == 128))


def _border_lines(gray: np.ndarray) -> list[tuple[int, int, int]]:
    """Horizontal border runs of 64 or more pixels, as (y, x, length)."""
    lines: list[tuple[int, int, int]] = []
    for y in np.nonzero(gray.sum(axis=1) >= 64)[0].tolist():
        row = np.concatenate(([0], gray[y].astype(np.int8), [0]))
        edges = np.diff(row)
        for a, b in zip(np.nonzero(edges == 1)[0].tolist(), np.nonzero(edges == -1)[0].tolist()):
            if b - a >= 64:
                lines.append((y, a, b - a))
    return lines


def popup_present(arr: np.ndarray) -> bool:
    """A window frame drawn over the screen.

    Windows are bordered with gray (150 or 128) lines. Either one line of 200 or more
    pixels, or a rectangle: two lines of 64 or more pixels with the same start and length at
    least 24 rows apart, joined by a gray side line. Tile art does not draw such rectangles.
    """
    gray = _border_gray(arr)
    lines = _border_lines(gray)
    if any(length >= 200 for _, _, length in lines):
        return True
    for n, (y1, a1, l1) in enumerate(lines):
        for y2, a2, l2 in lines[n + 1:]:
            if y2 - y1 >= 24 and abs(a1 - a2) <= 1 and abs(l1 - l2) <= 2:
                if max(gray[y1:y2 + 1, a1].mean(), gray[y1:y2 + 1, a1 + 1].mean()) >= 0.8:
                    return True
    return False


def side_panel_ui(arr: np.ndarray) -> bool:
    """A full-height gray divider: the overmap and look-around screens replace the sidebar with a panel."""
    px = arr[:, 200:900].astype(np.int16)
    gray = (px[..., 0] == px[..., 1]) & (px[..., 1] == px[..., 2]) & ((px[..., 0] == 150) | (px[..., 0] == 128) | (px[..., 0] == 255))
    return bool((gray.sum(axis=0) >= 560).any())


# Window sizes that separate a game screen the player works in from a dialog that interrupts it,
# measured on the 960x640 frames of the eleven #896 admissions. Inventory, crafting, consume, pickup,
# wield, item-info and nearby-items windows are 400 px (50 cells) or wider and have a side border of
# 240 px (15 rows) or more, or span the full width; queries, distraction prompts, direction prompts,
# activity notices and the in-game main menu are smaller. Boxes narrower than 160 px are tabs and
# labels inside a screen. The rule is calibrated on those frames only; it has no held-out validation.
UI_WINDOW_WIDTH, UI_WINDOW_HEIGHT, FULL_WIDTH, DIALOG_MIN_WIDTH, BORDER_MIN_HEIGHT = 400, 240, 900, 160, 24
# The game's item selector (reload, pour into, and the other single-purpose item lists) can be narrower
# than 50 cells; its bottom border always carries its filter and category controls, which no dialog
# draws. Seen at 298 and 386 px wide in #896 A2 frames 1868 (Reload item) and 7485 (Pour ... into).
ITEM_SELECTOR_FOOTER = ('< [/] Filter >', '< [;] categories >')


def _run_span(column: np.ndarray, y: int) -> tuple[int, int] | None:
    """First and last row of the gray run in `column` that contains row `y` (None when that pixel is not gray)."""
    if not column[y]:
        return None
    up, down = np.flatnonzero(~column[y::-1]), np.flatnonzero(~column[y:])
    return y - (int(up[0]) - 1 if up.size else y), y + (int(down[0]) - 1 if down.size else column.size - 1 - y)


def window_borders(arr: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """Each horizontal border run as (x, y, width, side height, side bottom): the side border is the
    longest gray vertical run through either end of the line, so a window's height and its bottom
    border row read from it (side bottom is `y` when no side border runs through the line's ends)."""
    gray = _border_gray(arr)
    out = []
    for y, x, width in _border_lines(gray):
        spans = [span for c in (x, x + 1, x + width - 1, x + width - 2)
                 if 0 <= c < gray.shape[1] and (span := _run_span(gray[:, c], y)) is not None]
        top, bottom = max(spans, key=lambda span: span[1] - span[0], default=(y, y - 1))
        out.append((x, y, width, bottom - top + 1, max(bottom, y)))
    return out


def item_selector(frame: Frame, x: int, width: int, bottom: int) -> bool:
    """Whether the window spanning pixels `x`..`x + width` has the item selector's footer on its bottom border row."""
    line = decode_line(frame.arr, 0, bottom // CELL_H * CELL_H, FRAME_W // CELL_W, frame.atlas)
    inside = line[x // CELL_W:(x + width) // CELL_W + 1]
    return all(control in inside for control in ITEM_SELECTOR_FOOTER)


def game_ui(frame: Frame) -> bool:
    """A game screen the player works in with no dialog over it: a side panel (overmap, look-around,
    nearby items), a large window (inventory, crafting, consume, pickup, wield) or an item selector
    of any width (reload, pour), and no smaller bordered dialog (a query, a distraction or direction
    prompt, an activity notice) drawn on top."""
    borders = window_borders(frame.arr)
    large = [b for b in borders if b[2] >= FULL_WIDTH or (b[2] >= UI_WINDOW_WIDTH and b[3] >= UI_WINDOW_HEIGHT)]
    windows = [b for b in borders if DIALOG_MIN_WIDTH <= b[2] < FULL_WIDTH and b[3] >= BORDER_MIN_HEIGHT and b not in large]
    selectors = [b for b in windows if item_selector(frame, b[0], b[2], b[4])]
    # A dialog floats: its border stays a cell clear of both screen edges. A screen's own border reaching
    # an edge (the crafting screen's tab bar splits its top border) is not a dialog.
    if any(b[3] < UI_WINDOW_HEIGHT and b[0] >= CELL_W and b[0] + b[2] <= FRAME_W - CELL_W
           for b in windows if b not in selectors):
        return False
    # Over a narrow item selector (no full/large screen), any distinct floating bordered window —
    # including a narrow (<160 px) or tall (>=240 px) dialog like the in-game main menu — takes precedence.
    if selectors and not large and any(
            b not in selectors and b[3] >= BORDER_MIN_HEIGHT and b[0] >= CELL_W and b[0] + b[2] <= FRAME_W - CELL_W
            and not any(abs(b[0] - s[0]) <= 2 and abs(b[2] - s[2]) <= 2 for s in selectors)
            for b in borders):
        return False
    return bool(large or selectors) or side_panel_ui(frame.arr)


def loading_screen(arr: np.ndarray) -> bool:
    """The start-up newspaper splash: black margins around a large sepia sheet."""
    left = arr[:, :140]
    if left.mean() > 12:
        return False
    box = arr[100:520, 330:620].astype(np.int16)
    r, g, b = box[..., 0], box[..., 1], box[..., 2]
    paper = (r > 140) & (r > g) & (g > b) & (r - b > 50)
    return paper.mean() > 0.3


MENU_BAR_TOKENS = ('[MOTD]', '[New Game]', '[Load]', '[World]', '[Tutorial Game]', '[Settings]', '[Help]', '[Credits]', 'Quit]')
CREATION_TABS = ('POINTS', 'SCENARIO', 'PROFESSION', 'BACKGROUND', 'STATS', 'TRAITS', 'SKILLS', 'DESCRIPTION')


def menu_screen(frame: Frame) -> bool:
    """Pre-game screens: main menu, world creation or selection, character creation."""
    # A dialog drawn over a menu ("Really quit?", a world list) hides only part of the base screen,
    # so any one surviving marker names the base screen. No game is loaded behind these screens.
    bar = decode_line(frame.arr, 0, 32 * CELL_H, 120, frame.atlas)
    if sum(token in bar for token in MENU_BAR_TOKENS) >= 2:
        return True
    if 'Version:' in decode_line(frame.arr, 0, 23 * CELL_H, 120, frame.atlas) and any(token in bar for token in MENU_BAR_TOKENS):
        return True
    r0 = decode_line(frame.arr, 0, 0, 120, frame.atlas)
    if 'Create World' in r0 or 'World selection' in r0:
        return True
    tabs = decode_line(frame.arr, 0, CELL_H, 120, frame.atlas)
    return sum(tab in tabs for tab in CREATION_TABS) >= 2


def read_death(frame: Frame) -> tuple[bool, str | None]:
    """The memorial dialog ('In memory of: NAME'), drawn on a 3-pixel grid offset. Returns (dead, name)."""
    for dx in range(8):
        line = decode_line(frame.arr, 331 + dx, 15 * CELL_H, 36, frame.atlas)
        pos = line.find('In memory of:')
        if pos >= 0:
            name = re.split(r' {2,}', line[pos + len('In memory of:'):].strip())[0].strip()
            return True, name if name and UNKNOWN not in name else None
    return False, None


def read_creation_name(frame: Frame) -> str | None:
    """'Name: X' on the character description tab, unless it is the random-name placeholder."""
    line = decode_line(frame.arr, 2 * CELL_W, 6 * CELL_H, 40, frame.atlas)
    if not line.startswith('Name:'):
        return None
    name = re.split(r' {2,}', line[5:].strip())[0].strip()
    if not name or UNKNOWN in name or name.startswith('---'):
        return None
    return name


def classify_mode(frame: Frame) -> tuple[str, float | None, str | None, str | None]:
    """(mode, confidence, abstain reason, death-dialog name).

    A loaded game behind a window is `ui` when the window is a game screen the player works in
    (`game_ui`) and `prompt` otherwise."""
    dead, name = read_death(frame)
    if dead:
        return 'dead', 0.95, None, name
    anchors = frame.anchors_present()
    window = lambda: ('ui', 0.7, None, None) if game_ui(frame) else ('prompt', 0.7, None, None)  # noqa: E731
    if anchors == len(ANCHORS):
        return window() if popup_present(frame.arr) or side_panel_ui(frame.arr) else ('in_play', 0.97, None, None)
    if loading_screen(frame.arr):
        return 'loading', 0.8, None, None
    if menu_screen(frame):
        return 'menu', 0.9, None, None
    if anchors >= 3 or popup_present(frame.arr) or side_panel_ui(frame.arr):
        return window()
    return 'unknown', None, 'no_signature', None
