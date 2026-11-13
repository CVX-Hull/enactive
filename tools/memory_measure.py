"""The memory screen's measure gate (#386): packets, the known-item list, `judge` events and the statistics.

No game runs, no model is called and nothing is spent. The protocol is docs/design/memory-screen-protocol.md.
RUN is a directory whose parent is named `memory-measure` (`.runtime/memory-measure/<run>`); everything is
written there and nowhere else. ADMISSION is a sealed run directory (it holds `actors/NNN/host.jsonl` and
`sources/`). In the order the lead runs them:

  python -m tools.memory_measure packets annotate RUN --runs ADMISSION... [--every 3] [--frames-per-packet 60]
  python -m tools.memory_measure items RUN --annotators A B --list
  python -m tools.memory_measure items RUN --annotators A B --matches FILE
  python -m tools.memory_measure packets judge RUN --runs ADMISSION... [--stretch 200] [--every 3] [--seed N] [--no-item-frames]
  python -m tools.memory_measure sample RUN [--count 20] [--seed N]
  python -m tools.memory_measure sample RUN --engaged 10 [--seed N]
  python -m tools.memory_measure label-server RUN [--port 8765]
  python -m tools.memory_measure events RUN --judge NAME --model MODEL ANSWER.json...
  python -m tools.memory_measure agreement RUN --judges A B [--third C] [--seed N] [--draws N] [--json]
  python -m tools.memory_measure measure RUN [--seed N] [--draws N] [--json]
  python -m tools.memory_measure simulate [--touched F] [--missed F] [--wrong F] [--ceiling N] [--price USD] [--json]

What RUN holds:
  annotate/packets.json, annotate/<packet>/     frames for the two annotators: manifest.json, instructions.md, frames/
  annotations/<annotator>/<packet>.json         each annotator's answer per packet (the lead saves them)
  items.json, items.json.sha256                 the known-item list, frozen: never overwritten
  judge-packets/<shuffled name>/                one stretch for a judge: manifest.json, instructions.md, items.json,
                                                frames/ and items/ (each item's first frame, unless --no-item-frames)
  private/judge-mapping.json                    shuffled name -> admission, decisions and source IDs; never in a packet
  sample.json, sample-engaged.json, labels.json the random calibration pairs, the engaged supplement (drawn after the
                                                judges have answered) and the owner's labels: a blind label and a checked one
  events/<judge>.jsonl                          judge-events/1 (harness/evaluation/core/judge.py)
  agreement.json, adjudicated.json, measure.json

A frame is "changed" when `harness.trace.images.region_diff` over the whole image finds a pixel whose largest
channel difference from the frame before it exceeds 16 of 255, that function's threshold; a fainter change does not
count. A packet takes every third changed frame, the first included, with every input sent since the packet's
previous frame. `--runs` refuses a path under the held-out lineage's evidence, `522-held-out`. Packets hold frames and inputs only: no store, no player record, no report, no
briefing and no arm name. A judge packet's frames and directory carry shuffled names.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import sys
import threading
from typing import Sequence
import uuid

import numpy as np
from PIL import Image

from harness.evaluation.core import judge
from harness.evaluation.core.host import frame_source
from harness.evaluation.core.records import EvaluationError, loads
from harness.jsonio import file_sha256
from harness.trace import images
from harness.trace.projection import ACTION_FIELDS
from tools.memory_reads import run_dirs
from tools.memory_screen_checks import read_lineage

LABELS = judge.LABELS
#: What the owner's page shows for each label; the page records the label, not this text.
LABEL_TEXT = dict(straight='Went straight to it', missed='Missed it (looked elsewhere or got it another way)',
    not_engaged='Not engaged', cannot_tell='Cannot tell')
#: The protocol's thresholds for using the judge (docs/design/memory-screen-protocol.md#the-judge).
MIN_AGREEMENT, MIN_KAPPA, MIN_OWNER_MATCH, OWNER_PAIRS = 0.80, 0.6, 18, 20
#: The engaged supplement: pairs outside the random draw that a judge called straight, missed or cannot_tell.
ENGAGED_PAIRS = 10
ENGAGED_LABELS = (*judge.TOUCHED, 'cannot_tell')
ENGAGED_FILE = 'sample-engaged.json'
OWNER_LABELS_SCHEMA = 'owner-labels/2'
AGREEMENT_SCHEMA = 'judge-agreement/2'
#: The appendix's rows: starts per arm, items touched per start, the current player's missed share, judge error.
APPENDIX_ROWS = ((12, 5, 0.7, 0.1), (12, 5, 0.7, 0.0), (12, 5, 0.7, 0.2), (12, 5, 0.6, 0.1), (12, 3, 0.7, 0.1),
    (12, 8, 0.7, 0.1), (16, 5, 0.7, 0.1), (8, 5, 0.7, 0.1))
#: A packet of 60 frames is about 50,000 image tokens at 960x640 (about 820 tokens a frame): a quarter of a
#: 200,000-token agent context, which leaves room for the manifest, the instructions and the answer. A judge
#: stretch of 200 decisions comes to about 65 frames, so both kinds of packet are the same size.
FRAMES_PER_PACKET = 60
NAME = re.compile('[a-z0-9][a-z0-9-]{0,39}')
#: With fewer sampled pairs than this that the owner or the judges called touched, the judge's error on touched
#: items is not measured.
MIN_TOUCHED_SAMPLED = 5
#: The held-out lineage's evidence directory; the measure gate never reads it.
HELD_OUT = '522-held-out'
BOOTSTRAP_NOTE = ('the bootstrap resamples pairs as if they were independent, although a judge reads a whole packet and '
    'labels every item of a stretch together; the intervals are narrower than the data supports')


class MeasureError(ValueError):
    """An input that does not fit the measure gate's files, or a write the gate refuses."""


# --- files ------------------------------------------------------------------------------------------------------------

def measure_dir(path: Path) -> Path:
    """The run directory. Its parent must be named `memory-measure`, so nothing is written into a session, a
    player store, a curator workspace or a knowledge repository by a mistyped path."""
    path = Path(path).resolve()
    if path.parent.name != 'memory-measure':
        raise MeasureError(f'{path}: the run directory must sit in a directory named memory-measure')
    return path


def read_json(path: Path) -> object:
    if not Path(path).is_file():
        raise MeasureError(f'{path}: missing')
    return loads(Path(path).read_bytes(), str(path))


def write_json(path: Path, value: object, *, once: bool = False) -> str:
    """Write indented JSON and return its SHA-256. `once` refuses an existing file."""
    data = (json.dumps(value, indent=1, ensure_ascii=False, allow_nan=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if once:
        with path.open('xb') as stream:
            stream.write(data)
    else:
        partial = path.with_name(f'.{path.name}.{uuid.uuid4().hex[:8]}')
        partial.write_bytes(data)
        os.replace(partial, path)
    return hashlib.sha256(data).hexdigest()


def text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MeasureError(f'{where}: must be a non-empty string')
    return value.strip()


# --- frames -----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Frame:
    """One recorded frame. `inputs` are the input batches sent since the frame before it, oldest first."""

    run: str
    source: str
    decision: int
    path: Path
    inputs: tuple
    changed: bool = True


def recorded_frames(runs: Sequence[Path], min_changed: float = 0.0) -> tuple[dict[str, list[Frame]], dict[str, int]]:
    """Each admission's frames in the order its calls returned them, marked changed or not, and its decision count.
    Only tool calls are read: a frame's source ID, the request that returned it and the inputs of `computer_input`."""
    for directory in runs:
        if HELD_OUT in Path(directory).resolve().parts:
            raise MeasureError(f'{directory}: the held-out lineage is not read for the measure gate')
    lineage, _ = read_lineage(runs)
    frames: dict[str, list[Frame]] = {}
    decisions: dict[str, int] = {}
    for directory, run in zip(runs, lineage):
        if run.name in frames:
            raise MeasureError(f'{run.name}: selected twice')
        found, seen, pending, previous = [], set(), [], None
        for call in run.facts.calls:
            if call.tool == 'computer_input':
                actions = call.arguments.get('actions') if isinstance(call.arguments, dict) else None
                pending.append([{key: action[key] for key in ACTION_FIELDS if key in action}
                    for action in (actions if isinstance(actions, list) else []) if isinstance(action, dict)])
            source = frame_source(call)
            if source is None or call.decision is None or source in seen:
                continue
            path = directory / 'sources' / f'{source}.png'
            if '/' in source or not path.is_file():
                raise MeasureError(f'{run.name}: frame {source} has no file under sources/')
            image = images.load(path)
            changed = previous is None or previous.shape != image.shape or \
                images.region_diff(previous, image, grid=(1, 1))[0]['changed_fraction'] > min_changed
            seen.add(source)
            found.append(Frame(run.name, source, call.decision, path, tuple(pending), bool(changed)))
            pending, previous = [], image
        frames[run.name] = found
        decisions[run.name] = max((request.decision for request in run.facts.requests), default=0)
    return frames, decisions


def every_nth_changed(frames: Sequence[Frame], every: int) -> list[Frame]:
    """Every `every`-th changed frame, the first included. Each kept frame carries every input since the kept one
    before it, so no input is lost with the frames that are left out."""
    kept, pending, count = [], [], 0
    for frame in frames:
        pending.extend(frame.inputs)
        if not frame.changed:
            continue
        if count % every == 0:
            kept.append(replace(frame, inputs=tuple(pending)))
            pending = []
        count += 1
    return kept


def copy_frame(frame: Frame, directory: Path, name: str) -> dict:
    target = directory / 'frames' / f'{name}.png'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(frame.path, target)
    return dict(frame=name, file=f'frames/{name}.png', sha256=file_sha256(target),
        inputs_before=[describe([batch]) for batch in frame.inputs])


def seal_packet(directory: Path, manifest: dict, instructions: str) -> tuple[str, int]:
    """Write the instructions and the manifest, which lists every other file's hash. The packet's hash is the
    manifest's; the second value is the packet's size in bytes. The manifest keeps one frame to a line, so a
    reader spends its context on the frames and not on indentation."""
    (directory / 'instructions.md').write_text(instructions, encoding='utf-8')
    files = {str(path.relative_to(directory)): file_sha256(path) for path in sorted(directory.rglob('*'))
        if path.is_file() and not path.is_relative_to(directory / 'frames')}
    head = json.dumps({key: value for key, value in dict(manifest, files=files).items() if key != 'frames'}, indent=1,
        ensure_ascii=False, allow_nan=False)
    rows = ',\n'.join('  ' + json.dumps(row, ensure_ascii=False, allow_nan=False) for row in manifest['frames'])
    data = (head[:-2] + ',\n "frames": [\n' + rows + '\n ]\n}\n').encode()
    with (directory / 'manifest.json').open('xb') as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest(), sum(path.stat().st_size for path in directory.rglob('*') if path.is_file())


class Building:
    """Build a directory beside its final place and rename it when complete, so a failure leaves nothing."""

    def __init__(self, target: Path) -> None:
        if target.exists():
            raise MeasureError(f'{target}: already written; it is made once')
        self.target, self.partial = target, target.with_name(f'.{target.name}.partial-{uuid.uuid4().hex[:8]}')

    def __enter__(self) -> Path:
        self.partial.mkdir(parents=True)
        return self.partial

    def __exit__(self, kind, *_) -> None:
        if kind is None:
            self.partial.rename(self.target)
        else:
            shutil.rmtree(self.partial, ignore_errors=True)


# --- packets for the annotators -----------------------------------------------------------------------------------------

ANNOTATE_INSTRUCTIONS = '''# Listing the places with goods that these frames show

You are one of two independent annotators. Use only the files in this directory: no other file, no notes from
another session and nothing you may know about this game session from elsewhere.

## What you have

- `manifest.json` lists this packet's frames in the order they were recorded. Each entry has the frame's ID
  (`frame`), its image (`file`) and `inputs_before`: the inputs sent to the game between this packet's previous
  frame and this one, oldest first. Each entry is one batch of inputs: keys by name, typed text in quotes and
  `×N` for a repeat.
- `frames/<frame ID>.png` is the screen as it was captured.

The frames are every third changed screen of one recorded stretch of play, so steps between them are missing.

## What to do

Look at every frame. List every place with goods or useful things that the frames show: anywhere the screen shows
things a player could later come back for, or a source of something useful. One entry per place:

- `place`: the place as the screen shows it. Use the name on the screen when there is one; otherwise the words a
  person looking at the screen would use, with whatever tells it apart from similar places (what it is next to,
  where on the map or in the building it is).
- `what`: what is there, in the screen's own words where you can.
- `frames`: the IDs of the frames that show it. At least one, and only IDs from this packet.

When several frames show the same place, write one entry and list all of those frames. List only what a frame
shows; do not add what you would expect to be there. When you are unsure whether something counts, list it.

## Your answer

One JSON document of this shape, and nothing else:

```json
{"packet": "PACKET", "entries": [{"place": "...", "what": "...", "frames": ["FRAME ID", "FRAME ID"]}]}
```

`packet` is this packet's name from `manifest.json`. An empty `entries` list is a valid answer.
'''


def annotate_packets(run: Path, runs: Sequence[Path], every: int = 3, per_packet: int = FRAMES_PER_PACKET,
                     min_changed: float = 0.0) -> dict:
    if every < 1 or per_packet < 1:
        raise MeasureError('--every and --frames-per-packet must be at least 1')
    frames, _ = recorded_frames(runs, min_changed)
    packets, totals = [], Counter()
    with Building(run / 'annotate') as out:
        for admission, found in frames.items():
            kept = every_nth_changed(found, every)
            totals.update(recorded=len(found), changed=sum(frame.changed for frame in found), kept=len(kept))
            parts = max(1, math.ceil(len(kept) / per_packet))
            size, extra = divmod(len(kept), parts)
            at = 0
            for part in range(parts):
                chunk = kept[at:at + size + (part < extra)]
                at += len(chunk)
                name = f'packet-{len(packets) + 1:02d}'
                rows = [copy_frame(frame, out / name, frame.source) for frame in chunk]
                sha, size_bytes = seal_packet(out / name, dict(schema='annotate-packet/1', packet=name, frames=rows),
                    ANNOTATE_INSTRUCTIONS)
                packets.append(dict(packet=name, admission=admission, frames=[frame.source for frame in chunk],
                    bytes=size_bytes, sha256=sha))
        index = dict(schema='annotate-packets/1', admissions=list(frames), every=every, min_changed=min_changed,
            frames_per_packet=per_packet, frames=dict(totals), packets=packets)
        write_json(out / 'packets.json', index, once=True)
    return index


# --- the known-item list ------------------------------------------------------------------------------------------------

def read_annotations(run: Path, annotator: str, index: dict) -> dict[str, dict]:
    """One annotator's entries over every packet, keyed `<packet>#<number>` with numbers from 1."""
    entries = {}
    for packet in index['packets']:
        path = run / 'annotations' / annotator / f"{packet['packet']}.json"
        if not path.is_file():
            raise MeasureError(f'{path}: missing; {annotator} must answer every packet')
        value = read_json(path)
        if not isinstance(value, dict) or value.get('packet') != packet['packet'] or not isinstance(value.get('entries'), list):
            raise MeasureError(f"{path}: expected {{\"packet\": \"{packet['packet']}\", \"entries\": [...]}}")
        inside = set(packet['frames'])
        for number, entry in enumerate(value['entries'], 1):
            where = f'{path}: entry {number}'
            if not isinstance(entry, dict) or not isinstance(entry.get('frames'), list) or not entry['frames']:
                raise MeasureError(f'{where}: needs place, what and a non-empty frames list')
            outside = [frame for frame in entry['frames'] if not isinstance(frame, str) or frame not in inside]
            if outside:
                raise MeasureError(f'{where}: cites frames outside its packet: {outside}')
            entries[f"{packet['packet']}#{number}"] = dict(place=text(entry.get('place'), f'{where} place'),
                what=text(entry.get('what'), f'{where} what'), frames=list(dict.fromkeys(entry['frames'])))
    return entries


def build_items(run: Path, annotators: Sequence[str], matches: Path) -> dict:
    """The known-item list: an item is a group of entries joined by the lead's matches, and every match pairs an
    entry of the first annotator with one of the second, so an entry only one of them listed is in no item."""
    target = run / 'items.json'
    if target.exists() or (run / 'items.json.sha256').exists():
        raise MeasureError(f'{target}: the known-item list is frozen and is never overwritten')
    first, second = annotators
    if first == second:
        raise MeasureError('The two annotators must differ')
    index = read_json(run / 'annotate' / 'packets.json')
    listed = {name: read_annotations(run, name, index) for name in annotators}
    pairs = read_json(matches)
    pairs = pairs.get('matches') if isinstance(pairs, dict) else None  # any other top-level key is the lead's own and ignored
    if not isinstance(pairs, list) or not pairs:
        raise MeasureError(f'{matches}: expected {{"matches": [["<{first} entry>", "<{second} entry>"], ...]}} with at '
            'least one match')
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def root(node: tuple[str, str]) -> tuple[str, str]:
        while parent.setdefault(node, node) != node:
            node = parent[node]
        return node

    for number, pair in enumerate(pairs, 1):
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(entry, str) for entry in pair) \
                or pair[0] not in listed[first] or pair[1] not in listed[second]:
            raise MeasureError(f'{matches}: match {number} must pair an entry of {first} with an entry of {second}: {pair!r}')
        parent[root((first, pair[0]))] = root((second, pair[1]))
    position = {frame: at for at, frame in enumerate(f for packet in index['packets'] for f in packet['frames'])}
    file_of = {frame: f"annotate/{packet['packet']}/frames/{frame}.png" for packet in index['packets']
        for frame in packet['frames']}
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for node in parent:
        groups.setdefault(root(node), []).append(node)
    items = []
    for members in groups.values():
        by = {name: sorted((identity for owner, identity in members if owner == name),
            key=lambda identity: min(position[frame] for frame in listed[name][identity]['frames'])) for name in annotators}
        frames = sorted({frame for name in annotators for identity in by[name] for frame in listed[name][identity]['frames']},
            key=position.__getitem__)
        lead = listed[first][by[first][0]]
        items.append(dict(place=lead['place'], what=lead['what'], first_frame=frames[0], first_frame_file=file_of[frames[0]],
            frames=frames, listed={name: [dict(entry=identity, place=listed[name][identity]['place'],
                what=listed[name][identity]['what']) for identity in by[name]] for name in annotators}))
    items.sort(key=lambda item: position[item['first_frame']])
    items = [dict(id=f'item-{number:02d}', **item) for number, item in enumerate(items, 1)]
    matched = {name: {entry['entry'] for item in items for entry in item['listed'][name]} for name in annotators}
    value = dict(schema='known-items/1', annotators=list(annotators),
        counts={name: dict(entries=len(listed[name]), in_an_item=len(matched[name]),
            dropped=len(listed[name]) - len(matched[name])) for name in annotators},
        sources=dict(annotate_packets=file_sha256(run / 'annotate' / 'packets.json'), matches=file_sha256(matches),
            annotations={name: {packet['packet']: file_sha256(run / 'annotations' / name / f"{packet['packet']}.json")
                for packet in index['packets']} for name in annotators}),
        items=items)
    sha = write_json(target, value, once=True)
    (run / 'items.json.sha256').write_text(sha + '\n')
    return dict(value, sha256=sha)


def load_items(run: Path) -> tuple[list[dict], str]:
    """The frozen list and its hash; a list that no longer matches its recorded hash is refused."""
    path = run / 'items.json'
    value = read_json(path)
    sha = file_sha256(path)
    recorded = (run / 'items.json.sha256').read_text().strip() if (run / 'items.json.sha256').is_file() else None
    if not isinstance(value, dict) or value.get('schema') != 'known-items/1' or sha != recorded:
        raise MeasureError(f'{path}: not the frozen known-items/1 list its recorded hash names')
    return value['items'], sha


# --- packets for the judges -----------------------------------------------------------------------------------------------

JUDGE_INSTRUCTIONS = '''# One closed question for each known item

Use only the files in this directory: no other file and nothing you may know about this stretch from elsewhere.

## What you have

- `manifest.json` lists the frames of one stretch of recorded play, in order. Each entry has the frame's ID
  (`frame`), its image (`file`), `decision` (which of the stretch's decisions returned it, counted from 1) and
  `inputs_before`: the inputs the player sent between this packet's previous frame and this one, oldest first.
  Each entry is one batch of inputs: keys by name, typed text in quotes and `×N` for a repeat. `decisions` is how
  many decisions the stretch has.
- `frames/<frame ID>.png` is the screen as it was captured. The frames are every third changed screen, so steps
  between them are missing.
- `items.json` lists the known items: places with goods that the player's earlier play had already shown, each
  with an `id`, the `place` as the screen showed it and `what` was there. Nothing in the list is from this stretch.
ITEM_FRAMES
## The question

For each known item, what did the player do about it in this stretch? Answer with exactly one label:

- `straight`: the player went to the known place without first looking elsewhere.
- `missed`: the player looked for the same kind of thing elsewhere, or got it by another route, while the known
  source stayed unused.
- `not_engaged`: the stretch shows the player neither going to the place nor looking for or getting that kind of
  thing.
- `cannot_tell`: the frames do not show enough to choose among the three above.

Cite the frames that show it, by ID, from this packet only. `straight` and `missed` need at least one frame;
the other two may cite none.

## Your answer

One JSON document of this shape, and nothing else. Answer every item in `items.json` exactly once:

```json
{"packet": "PACKET", "answers": [{"item": "ITEM ID", "label": "straight", "frames": ["FRAME ID"], "note": "one sentence"}]}
```

`packet` is this packet's name from `manifest.json`. `note` is optional.
'''


def judge_packets(run: Path, runs: Sequence[Path], stretch: int = 200, every: int = 3, min_changed: float = 0.0,
                  seed: int | None = None, item_frames: bool = True) -> dict:
    """One packet per stretch. Each item's first frame is in the packet unless `item_frames` is off, so the judge
    sees the same evidence for an item as the owner's page shows."""
    if stretch < 1 or every < 1:
        raise MeasureError('--stretch and --every must be at least 1')
    items, items_sha = load_items(run)
    mapping_path = run / 'private' / 'judge-mapping.json'
    if mapping_path.exists():
        raise MeasureError(f'{mapping_path}: already written; judge packets are made once')
    seed = secrets.randbits(32) if seed is None else seed
    rng = random.Random(seed)
    frames, decisions = recorded_frames(runs, min_changed)
    shown = dict(schema='known-items/1', sha256=items_sha,
        items=[dict(id=item['id'], place=item['place'], what=item['what']) for item in items])
    instructions = JUDGE_INSTRUCTIONS.replace('ITEM_FRAMES\n', '- `items/<item id>.png` is the earlier frame that '
        'first showed each item.\n\n' if item_frames else '\n')
    stretches: dict[str, tuple] = {}  # shuffled name -> admission, first and last decision, frames; in lineage order
    for admission, found in frames.items():
        for first in range(1, decisions[admission] + 1, stretch):
            last = min(first + stretch - 1, decisions[admission])
            name = f's{rng.getrandbits(40):010x}'
            while name in stretches:
                name = f's{rng.getrandbits(40):010x}'
            stretches[name] = (admission, first, last,
                every_nth_changed([frame for frame in found if first <= frame.decision <= last], every))
    packets = {}
    with Building(run / 'judge-packets') as out:
        # Written in the order of the shuffled names, so creation times and directory order say nothing of the lineage.
        for name in sorted(stretches):
            admission, first, last, kept = stretches[name]
            directory = out / name
            directory.mkdir()
            rows, sources = [], {}
            for number, frame in enumerate(kept, 1):
                row = copy_frame(frame, directory, f'f{number:03d}')
                rows.append(dict(row, decision=frame.decision - first + 1))
                sources[row['frame']] = frame.source
            write_json(directory / 'items.json', shown, once=True)
            for item in items if item_frames else ():
                (directory / 'items').mkdir(exist_ok=True)
                shutil.copyfile(run / item['first_frame_file'], directory / 'items' / f"{item['id']}.png")
            count = last - first + 1
            sha, size = seal_packet(directory, dict(schema='judge-packet/1', packet=name, decisions=count,
                short=count < stretch, labels=list(LABELS), items_sha256=items_sha, frames=rows), instructions)
            packets[name] = dict(packet=name, start=f'{admission}:{first}-{last}', admission=admission, first=first,
                last=last, decisions=count, short=count < stretch, sha256=sha, bytes=size, frames=sources)
        mapping = dict(schema='judge-mapping/1', seed=seed, stretch=stretch, every=every, min_changed=min_changed,
            item_frames=item_frames, items_sha256=items_sha, packets=[packets[name] for name in stretches])
        write_json(mapping_path, mapping, once=True)
    return mapping


def load_mapping(run: Path) -> dict:
    value = read_json(run / 'private' / 'judge-mapping.json')
    if not isinstance(value, dict) or value.get('schema') != 'judge-mapping/1':
        raise MeasureError(f"{run / 'private' / 'judge-mapping.json'}: not a judge-mapping/1 file")
    return value


def all_pairs(run: Path) -> list[tuple[str, str]]:
    """Every (stretch, item) pair, in stretch then item order."""
    items, _ = load_items(run)
    return [(packet['start'], item['id']) for packet in load_mapping(run)['packets'] for item in items]


# --- judge events -----------------------------------------------------------------------------------------------------

def judge_events(run: Path, name: str, model: str, answers: Sequence[Path]) -> list[judge.JudgeEvent]:
    """Validate one judge's answer files against their packets and write its events once."""
    if NAME.fullmatch(name) is None:
        raise MeasureError(f'{name!r}: a judge name is lowercase letters, digits and hyphens')
    target = run / 'events' / f'{name}.jsonl'
    if target.exists():
        raise MeasureError(f'{target}: already written; a judge\'s events are written once')
    items, _ = load_items(run)
    wanted = [item['id'] for item in items]
    packets = {packet['packet']: packet for packet in load_mapping(run)['packets']}
    events, done = [], set()
    for path in answers:
        value = read_json(path)
        named = value.get('packet') if isinstance(value, dict) else None
        packet = packets.get(named) if isinstance(named, str) else None
        if packet is None or not isinstance(value.get('answers'), list):
            raise MeasureError(f'{path}: expected {{"packet": "<a packet of this run>", "answers": [...]}}')
        if packet['packet'] in done:
            raise MeasureError(f"{path}: packet {packet['packet']} is answered by more than one file")
        done.add(packet['packet'])
        manifest = run / 'judge-packets' / packet['packet'] / 'manifest.json'
        if not manifest.is_file() or file_sha256(manifest) != packet['sha256']:
            raise MeasureError(f"{path}: packet {packet['packet']} is not the packet that was made")
        rows = value['answers']
        if any(not isinstance(row, dict) or not isinstance(row.get('item'), str) for row in rows):
            raise MeasureError(f'{path}: every answer is an object that names its item')
        counts = Counter(row.get('item') for row in rows)
        problems = [f'no answer for {identity}' for identity in wanted if not counts[identity]]
        problems += [f'{identity} answered {count} times' for identity, count in counts.items() if count > 1]
        problems += [f'{identity!r} is not a known item' for identity in counts if identity not in wanted]
        for row in rows:
            frames = row.get('frames', [])
            if row.get('label') not in LABELS:
                problems.append(f"{row.get('item')}: label {row.get('label')!r} is not one of {', '.join(LABELS)}")
            elif not isinstance(frames, list) or any(not isinstance(frame, str) or frame not in packet['frames']
                    for frame in frames):
                problems.append(f"{row.get('item')}: cites a frame outside the packet: {frames!r}")
            elif row['label'] in judge.TOUCHED and not frames:
                problems.append(f"{row.get('item')}: a {row['label']} label must cite a frame")
        if problems:
            raise MeasureError(f'{path}: ' + '; '.join(problems))
        events.extend(judge.JudgeEvent(start=packet['start'], item=row['item'], label=row['label'],
            cited_frames=tuple(packet['frames'][frame] for frame in dict.fromkeys(row.get('frames', []))), judge=name,
            model=text(model, '--model'), packet=packet['packet'], packet_sha256=packet['sha256']) for row in rows)
    if not events:
        raise MeasureError('No answer file selected')
    target.parent.mkdir(parents=True, exist_ok=True)
    judge.write_events(target, events)
    return events


def read_judge(run: Path, name: str) -> dict[tuple[str, str], str]:
    path = run / 'events' / f'{name}.jsonl'
    if not path.is_file():
        raise MeasureError(f'{path}: missing; run `events` for {name} first')
    return {event.pair: event.label for event in judge.read_events(path)}


# --- the calibration sample -------------------------------------------------------------------------------------------------

def draw_sample(run: Path, count: int = OWNER_PAIRS, seed: int | None = None) -> dict:
    """Draw `count` pairs from all pairs. It reads the stretches and the items only, never a verdict."""
    pairs = all_pairs(run)
    if len(pairs) < count:
        raise MeasureError(f'Only {len(pairs)} pairs exist; cannot draw {count}')
    seed = secrets.randbits(32) if seed is None else seed
    chosen = random.Random(seed).sample(pairs, count)
    events = run / 'events'
    value = dict(schema='calibration-sample/1', seed=seed, count=count, population=len(pairs),
        items_sha256=load_items(run)[1], verdicts_existed=events.is_dir() and any(events.iterdir()),
        pairs=[dict(index=index, start=start, item=item) for index, (start, item) in enumerate(chosen)])
    try:
        write_json(run / 'sample.json', value, once=True)
    except FileExistsError:
        raise MeasureError(f"{run / 'sample.json'}: already drawn; the sample is drawn once") from None
    return value


def draw_engaged(run: Path, count: int = ENGAGED_PAIRS, seed: int | None = None) -> dict:
    """Draw `count` further pairs for the owner: pairs outside the random draw that any judge called straight, missed
    or cannot_tell. This reads every judge's events, so it is made after the judges have answered; the random draw
    never reads one. The owner's page serves these pairs after the random ones and does not say which is which."""
    target = run / ENGAGED_FILE
    if target.exists():
        raise MeasureError(f'{target}: already drawn; the engaged supplement is drawn once')
    drawn = read_json(run / 'sample.json')['pairs']
    names = sorted(path.stem for path in (run / 'events').glob('*.jsonl')) if (run / 'events').is_dir() else []
    if not names:
        raise MeasureError(f"{run / 'events'}: no judge events; the engaged supplement needs the judges' verdicts")
    called: dict[tuple[str, str], set[str]] = {}
    for name in names:
        for event in judge.read_events(run / 'events' / f'{name}.jsonl'):
            called.setdefault(event.pair, set()).add(event.label)
    random_pairs = {(pair['start'], pair['item']) for pair in drawn}
    population = all_pairs(run)
    pool = [pair for pair in population if pair not in random_pairs and called.get(pair, set()) & set(ENGAGED_LABELS)]
    if len(pool) < count:
        raise MeasureError(f'Only {len(pool)} pairs outside the random draw were called {", ".join(ENGAGED_LABELS)} by a '
            f'judge; cannot draw {count}')
    seed = secrets.randbits(32) if seed is None else seed
    chosen = random.Random(seed).sample(pool, count)
    value = dict(schema='engaged-sample/1', seed=seed, count=count, population=len(population), eligible=len(pool),
        labels=list(ENGAGED_LABELS), judges=names,
        events_sha256={name: file_sha256(run / 'events' / f'{name}.jsonl') for name in names},
        random_sample_sha256=file_sha256(run / 'sample.json'), items_sha256=load_items(run)[1],
        pairs=[dict(index=len(drawn) + number, start=start, item=item) for number, (start, item) in enumerate(chosen)])
    write_json(target, value, once=True)
    return value


# --- statistics -------------------------------------------------------------------------------------------------------

def cohen_kappa(first: Sequence[int], second: Sequence[int], categories: int = len(LABELS)) -> float | None:
    """Cohen's kappa of two raters' category codes; None when chance agreement is certain."""
    a, b = np.asarray(first), np.asarray(second)
    if a.size == 0:
        return None
    observed = float((a == b).mean())
    chance = float(sum((a == k).mean() * (b == k).mean() for k in range(categories)))
    return None if chance >= 1 else (observed - chance) / (1 - chance)


def percentile_interval(values: np.ndarray) -> list[float] | None:
    """The 2.5th and 97.5th percentiles of the defined bootstrap values."""
    defined = values[~np.isnan(values)]
    return None if defined.size == 0 else [float(v) for v in np.percentile(defined, [2.5, 97.5])]


def _solve(function, target: float, rising: bool, high: float = 1.0) -> float:
    """Where a monotone function of one value in 0..high equals `target`, by bisection."""
    low = 0.0
    for _ in range(80):
        middle = (low + high) / 2
        if (function(middle) < target) == rising:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def binomial_interval(successes: int, trials: int, level: float = 0.95) -> list[float]:
    """The exact (Clopper-Pearson) interval for a binomial share."""
    tail = (1 - level) / 2

    def at_most(count: int, p: float) -> float:
        return sum(math.comb(trials, i) * p ** i * (1 - p) ** (trials - i) for i in range(count + 1))

    lower = 0.0 if successes == 0 else _solve(lambda p: 1 - at_most(successes - 1, p), tail, True)
    upper = 1.0 if successes == trials else _solve(lambda p: at_most(successes, p), tail, False)
    return [lower, upper]


def poisson_interval(count: int, level: float = 0.95) -> list[float]:
    """The exact (Garwood) interval for the mean of a Poisson count."""
    tail = (1 - level) / 2

    def at_most(limit: int, mean: float) -> float:
        return sum(math.exp(i * math.log(mean) - mean - math.lgamma(i + 1)) for i in range(limit + 1)) if mean > 0 else 1.0

    high = count + 10 * math.sqrt(count + 1) + 30
    lower = 0.0 if count == 0 else _solve(lambda mean: 1 - at_most(count - 1, mean), tail, True, high)
    return [lower, _solve(lambda mean: at_most(count, mean), tail, False, high)]


def cannot_tell_of_touched(labels) -> dict:
    """`cannot_tell` among `straight`, `missed` and `cannot_tell`: the share the protocol's decision rule uses."""
    counts = Counter(labels)
    of = counts['straight'] + counts['missed'] + counts['cannot_tell']
    return dict(cannot_tell=counts['cannot_tell'], of=of, value=counts['cannot_tell'] / of if of else None)


def owner_match(matched: int, compared: int) -> dict:
    return dict(compared=compared, matched=matched, interval=binomial_interval(matched, compared) if compared else None)


def pair_statistics(first: Sequence[int], second: Sequence[int], seed: int, draws: int) -> dict:
    """Agreement, kappa and the share of `cannot_tell` over both judges' labels, each with a percentile bootstrap
    interval over pairs."""
    a, b = np.asarray(first), np.asarray(second)
    cannot = LABELS.index('cannot_tell')
    index = np.random.default_rng(seed).integers(0, a.size, (draws, a.size))
    x, y = a[index], b[index]
    observed = (x == y).mean(axis=1)
    chance = sum((x == k).mean(axis=1) * (y == k).mean(axis=1) for k in range(len(LABELS)))
    with np.errstate(divide='ignore', invalid='ignore'):
        kappa = np.where(chance < 1, (observed - chance) / (1 - chance), np.nan)
    share = ((x == cannot).mean(axis=1) + (y == cannot).mean(axis=1)) / 2
    return dict(pairs=int(a.size),
        agreement=dict(value=float((a == b).mean()), interval=percentile_interval(observed)),
        kappa=dict(value=cohen_kappa(a, b), interval=percentile_interval(kappa), undefined_draws=int(np.isnan(kappa).sum())),
        cannot_tell=dict(value=float(((a == cannot).mean() + (b == cannot).mean()) / 2), interval=percentile_interval(share)))


CHECKED_NOTE = ('not the calibration: the owner gave these after the judges\' evidence was shown, so they are not '
    'independent of it')


def read_owner(run: Path) -> tuple[list[dict], list[dict], dict[int, dict]]:
    """The random pairs, the engaged pairs and the owner's entry for each labelled pair, by index. Each entry holds
    `blind` and `checked` (null until the owner has checked the pair). With no labels file there are no entries."""
    random_pairs = read_json(run / 'sample.json')['pairs'] if (run / 'sample.json').is_file() else []
    engaged_pairs = read_json(run / ENGAGED_FILE)['pairs'] if (run / ENGAGED_FILE).is_file() else []
    entries: dict[int, dict] = {}
    if (run / 'labels.json').is_file():
        saved = read_json(run / 'labels.json')
        if saved.get('schema') != OWNER_LABELS_SCHEMA:
            raise MeasureError(f"{run / 'labels.json'}: not {OWNER_LABELS_SCHEMA}; labels of another format are not read")
        entries = {int(index): entry for index, entry in saved['labels'].items()}
    return random_pairs, engaged_pairs, entries


def tally_owner(pairs: Sequence[dict], entries: dict[int, dict], adjudicated: dict, which: str) -> tuple:
    """The owner's `which` label ('blind' or 'checked') against the adjudicated label over `pairs`:
    [matched, compared] over every compared pair, [matched, compared] over those the owner or the judges called
    straight or missed, and the count of pairs the owner called not_engaged that were adjudicated straight or missed."""
    whole, touched, false_engagement = [0, 0], [0, 0], 0
    for pair in pairs:
        given = (entries.get(pair['index']) or {}).get(which)
        verdict = adjudicated[(pair['start'], pair['item'])]
        if given is None or verdict is None:
            continue
        for part in (whole, touched) if given in judge.TOUCHED or verdict in judge.TOUCHED else (whole,):
            part[0] += given == verdict
            part[1] += 1
        false_engagement += given == 'not_engaged' and verdict in judge.TOUCHED
    return whole, touched, false_engagement


def agreement(run: Path, judges: Sequence[str], third: str | None = None, seed: int | None = None,
              draws: int = 10000) -> dict:
    """The two judges' agreement, the adjudicated labels and their match with the owner's labels."""
    pairs = all_pairs(run)
    first, second = (read_judge(run, name) for name in judges)
    missing = [f'{name}: {start} / {item}' for name, labels in zip(judges, (first, second)) for start, item in pairs
        if (start, item) not in labels]
    if missing:
        raise MeasureError(f'{len(missing)} pairs lack a verdict, the first: {missing[0]}')
    tie = read_judge(run, third) if third else {}
    seed = secrets.randbits(32) if seed is None else seed
    code = LABELS.index
    report = pair_statistics([code(first[pair]) for pair in pairs], [code(second[pair]) for pair in pairs], seed, draws)
    packets = {packet['start']: packet['packet'] for packet in load_mapping(run)['packets']}
    rows = []
    for pair in pairs:
        same = first[pair] == second[pair]
        label = first[pair] if same else tie.get(pair)
        # `third_alone`: the third judge chose a label neither of the two gave, so no two judges agree on the pair
        by = 'agreement' if same else None if label is None else 'third' if label in (first[pair], second[pair]) \
            else 'third_alone'
        rows.append(dict(start=pair[0], item=pair[1], label=label, by=by,
            labels={judges[0]: first[pair], judges[1]: second[pair], **({third: tie[pair]} if pair in tie else {})}))
    unresolved = [row for row in rows if row['label'] is None]
    write_json(run / 'adjudicated.json', dict(schema='judge-adjudicated/1', judges=list(judges), third=third,
        unresolved=len(unresolved), third_alone=sum(row['by'] == 'third_alone' for row in rows), pairs=rows))
    adjudicated = {(row['start'], row['item']): row['label'] for row in rows}
    random_pairs, engaged_pairs, owner_entries = read_owner(run)
    # The calibration is the owner's blind labels over the random pairs. The engaged pairs, and the owner's checked
    # labels (given after seeing the judges' evidence), are reported beside it and never counted in it.
    whole, touched, false_engagement = tally_owner(random_pairs, owner_entries, adjudicated, 'blind')
    engaged_whole, engaged_touched, engaged_false = tally_owner(engaged_pairs, owner_entries, adjudicated, 'blind')
    checked_random = tally_owner(random_pairs, owner_entries, adjudicated, 'checked')[0]
    checked_engaged = tally_owner(engaged_pairs, owner_entries, adjudicated, 'checked')[0]
    both = [owner_entries[pair['index']] for pair in random_pairs + engaged_pairs if pair['index'] in owner_entries]
    matched, labelled = whole
    decided = labelled == OWNER_PAIRS
    passes = dict(agreement=report['agreement']['value'] >= MIN_AGREEMENT,
        kappa=report['kappa']['value'] is not None and report['kappa']['value'] >= MIN_KAPPA,
        owner=matched >= MIN_OWNER_MATCH if decided else None)
    report.update(schema=AGREEMENT_SCHEMA, judges=list(judges), third=third,
        bootstrap=dict(seed=seed, draws=draws, note=BOOTSTRAP_NOTE),
        cannot_tell_of_touched={judges[0]: cannot_tell_of_touched(first[pair] for pair in pairs),
            judges[1]: cannot_tell_of_touched(second[pair] for pair in pairs),
            'adjudicated': cannot_tell_of_touched(row['label'] for row in rows if row['label'] is not None)},
        owner=dict(owner_match(matched, labelled), of=OWNER_PAIRS, touched=owner_match(*touched),
            false_engagement=int(false_engagement), basis='blind labels, the first click of each pair',
            engaged=dict(owner_match(*engaged_whole), of=len(engaged_pairs), touched=owner_match(*engaged_touched),
                false_engagement=int(engaged_false)),
            # the error `measure` sizes the comparison with: random and engaged pairs together
            touched_all=owner_match(touched[0] + engaged_touched[0], touched[1] + engaged_touched[1]),
            checked=dict(note=CHECKED_NOTE, labelled=len(both),
                changed=sum(entry.get('checked') not in (None, entry['blind']) for entry in both),
                checked_pairs=sum(entry.get('checked') is not None for entry in both),
                random=owner_match(*checked_random), engaged=owner_match(*checked_engaged))),
        disputed=[dict(start=row['start'], item=row['item'], packet=packets[row['start']], labels=row['labels'],
            adjudicated=row['label'], by=row['by']) for row in rows if row['by'] != 'agreement'],
        third_alone=sum(row['by'] == 'third_alone' for row in rows),
        unresolved=len(unresolved),
        third_judge_packets=sorted({packets[row['start']] for row in unresolved}),
        thresholds=dict(agreement=MIN_AGREEMENT, kappa=MIN_KAPPA, owner_match=MIN_OWNER_MATCH, owner_pairs=OWNER_PAIRS),
        passes=passes, **{'pass': None if passes['owner'] is None and all((passes['agreement'], passes['kappa']))
            else all(passes.values())})
    write_json(run / 'agreement.json', report)
    return report


def measure(run: Path, seed: int | None = None, draws: int = 10000) -> dict:
    """Known items touched per stretch length and the missed share among touched, from the adjudicated labels.
    Items touched carry an exact Poisson interval on the total count over the total decisions. The percentile
    bootstrap over stretches is rough: a handful of stretches from fewer admissions is all there is to resample.
    The judge's error for sizing comes from the owner comparison in `agreement.json`, with its interval: the owner's
    blind labels over every labelled pair, random and engaged, that the owner or the judges called straight or missed."""
    adjudicated = read_json(run / 'adjudicated.json')
    if adjudicated['unresolved']:
        raise MeasureError(f"{adjudicated['unresolved']} pairs are not adjudicated; run `agreement` with --third")
    mapping = load_mapping(run)
    seed = secrets.randbits(32) if seed is None else seed
    per = mapping['stretch']
    by_start: dict[str, Counter] = {packet['start']: Counter() for packet in mapping['packets']}
    for row in adjudicated['pairs']:
        by_start[row['start']][row['label']] += 1
    rows = [dict(start=packet['start'], admission=packet['admission'], decisions=packet['decisions'], short=packet['short'],
        **{label: by_start[packet['start']][label] for label in LABELS}) for packet in mapping['packets']]

    def over(selected: list[dict]) -> dict:
        if not selected:
            return dict(stretches=0, admissions=0)
        decisions = np.array([row['decisions'] for row in selected], dtype=float)
        missed = np.array([row['missed'] for row in selected], dtype=float)
        touched = missed + np.array([row['straight'] for row in selected], dtype=float)
        index = np.random.default_rng(seed).integers(0, len(selected), (draws, len(selected)))
        with np.errstate(divide='ignore', invalid='ignore'):
            rate = per * touched[index].sum(axis=1) / decisions[index].sum(axis=1)
            share = np.where(touched[index].sum(axis=1) > 0, missed[index].sum(axis=1) / touched[index].sum(axis=1), np.nan)
        return dict(stretches=len(selected), admissions=len({row['admission'] for row in selected}),
            decisions=int(decisions.sum()), touched=int(touched.sum()), missed=int(missed.sum()),
            touched_per_stretch=dict(value=float(per * touched.sum() / decisions.sum()),
                exact_poisson_interval=[float(per * end / decisions.sum()) for end in poisson_interval(int(touched.sum()))],
                interval=percentile_interval(rate)),
            missed_share=dict(value=float(missed.sum() / touched.sum()) if touched.sum() else None,
                interval=percentile_interval(share), undefined_draws=int(np.isnan(share).sum())))

    labels = Counter(row['label'] for row in adjudicated['pairs'])
    calibration = error = None
    if (run / 'agreement.json').is_file():
        found = read_json(run / 'agreement.json')
        if found.get('schema') != AGREEMENT_SCHEMA:
            raise MeasureError(f"{run / 'agreement.json'}: not {AGREEMENT_SCHEMA}; run `agreement` again")
        owner = found['owner']
        calibration = {'pass': found['pass'], 'passes': found['passes'], 'agreement': found['agreement']['value'],
            'kappa': found['kappa']['value'], 'owner_matched': owner['matched'], 'owner_compared': owner['compared'],
            'third_alone': found['third_alone']}

        def wrong(part: dict) -> dict | None:
            """The judge's error against the owner over some compared pairs, with the exact interval."""
            if not part['compared']:
                return None
            return dict(compared=part['compared'], differ=part['compared'] - part['matched'],
                value=1 - part['matched'] / part['compared'], interval=[1 - part['interval'][1], 1 - part['interval'][0]])

        # all_pairs is the random draw's blind labels; touched_pairs adds the engaged pairs, also on blind labels
        error = dict(all_pairs=wrong(owner), touched_pairs=wrong(owner['touched_all']),
            touched_measured=owner['touched_all']['compared'] >= MIN_TOUCHED_SAMPLED,
            false_engagement=owner['false_engagement'])
    report = dict(schema='memory-measure/1', per_decisions=per, bootstrap=dict(seed=seed, draws=draws),
        labels={label: labels[label] for label in LABELS}, pairs=len(adjudicated['pairs']),
        cannot_tell_share=labels['cannot_tell'] / len(adjudicated['pairs']) if adjudicated['pairs'] else None,
        cannot_tell_of_touched=cannot_tell_of_touched(row['label'] for row in adjudicated['pairs']),
        all_stretches=over(rows), full_stretches=over([row for row in rows if not row['short']]), stretches=rows,
        calibration=calibration, judge_error=error)
    report['simulate_commands'] = simulate_commands(report)
    write_json(run / 'measure.json', report)
    return report


def simulate_commands(report: dict) -> list[dict]:
    """The `simulate` command lines for the measured numbers: the point values, the judge's error at its interval's
    upper bound, and each interval's ends. The judge's error is the one on touched pairs when enough were sampled,
    otherwise the one over all pairs; with no owner comparison `--wrong` is left as `F`."""
    whole = report['all_stretches']
    share = (whole.get('missed_share') or {}).get('value')
    if not whole.get('touched') or share in (None, 0.0, 1.0):
        return []
    error = report['judge_error']
    source = error and (error['touched_pairs'] if error['touched_measured'] else error['all_pairs'])
    wrong = f"{source['value']:.3f}" if source else 'F'
    rate = whole['touched_per_stretch']

    def line(case: str, touched: float, missed: float, flips: str) -> dict:
        return dict(case=case, command=f'python -m tools.memory_measure simulate --touched {touched:.2f} --missed {missed:.3f} '
            f'--wrong {flips}')

    commands = [line('point values', rate['value'], share, wrong)]
    if source:
        commands.append(line("judge error at its interval's upper bound", rate['value'], share, f"{source['interval'][1]:.3f}"))
    low, high = rate['exact_poisson_interval']
    if low > 0:
        commands.append(line("items touched at the exact interval's lower end", low, share, wrong))
    commands.append(line("items touched at the exact interval's upper end", high, share, wrong))
    for name, end in zip(('lower', 'upper'), whole['missed_share']['interval'] or ()):
        if 0 < end < 1 and f'{end:.3f}' != f'{share:.3f}':
            commands.append(line(f"missed share at the bootstrap interval's {name} end", rate['value'], end, wrong))
    return commands


# --- the protocol's simulation --------------------------------------------------------------------------------------------

def p_values(rng: np.random.Generator, starts: int, touched: float, missed: float, ratio: float, wrong: float,
             rho: float = 0.2, sims: int = 1500, draws: int = 400) -> np.ndarray:
    """One-sided permutation p-values of the appendix's model, `sims` comparisons at once: each start touches a
    Poisson number of known items, each missed with a probability that varies by start (correlation `rho`); the
    judge flips each label with probability `wrong`; the second arm's missed share is `ratio` times the first's.
    The statistic is the difference in missed items per start, compared as integer sums."""
    if not 0 < missed < 1 or not 0 < missed * ratio < 1 or not 0 < rho < 1 or not 0 <= wrong <= 1 or touched <= 0:
        raise MeasureError('The simulation needs items touched above 0, a missed share strictly between 0 and 1, '
            'a judge error within 0..1 and a correlation strictly between 0 and 1')

    def arm(share: float) -> np.ndarray:
        engaged = rng.poisson(touched, (sims, starts))
        lost = rng.binomial(engaged, rng.beta(share * (1 - rho) / rho, (1 - share) * (1 - rho) / rho, (sims, starts)))
        return lost - rng.binomial(lost, wrong) + rng.binomial(engaged - lost, wrong)

    current, treated = arm(missed), arm(missed * ratio)
    both = np.concatenate([current, treated], axis=1)
    seen = current.sum(axis=1) - treated.sum(axis=1)
    total = both.sum(axis=1)
    hits = np.empty(sims, dtype=np.int64)
    batch = max(1, 2_000_000 // (draws * 2 * starts))
    for low in range(0, sims, batch):
        part = both[low:low + batch]
        shuffled = rng.permuted(np.repeat(part[:, None, :], draws, axis=1), axis=2)
        difference = 2 * shuffled[:, :, :starts].sum(axis=2) - total[low:low + batch, None]
        hits[low:low + batch] = (difference >= seen[low:low + batch, None]).sum(axis=1)
    return (hits + 1) / (draws + 1)


def simulate(rows: Sequence[tuple[int, float, float, float]], touched: float, missed: float, wrong: float, *,
             rho: float = 0.2, sims: int = 1500, draws: int = 400, seed: int = 590, target: float = 0.8,
             minimum: int = 4, ceiling: int = 60, price: float = 3.58) -> dict:
    """The appendix's table for `rows`, then the smallest number of starts per arm, from `minimum` to `ceiling`,
    whose simulated chance of detecting a halving reaches `target` at 0.05 and at Holm's first step, 0.025."""
    if not 1 <= minimum <= ceiling:
        raise MeasureError('The search needs 1 <= --min-starts <= --ceiling')
    rng = np.random.default_rng(seed)
    table = []
    for starts, lam, share, error in rows:
        halving = p_values(rng, starts, lam, share, 0.5, error, rho, sims, draws)
        third = p_values(rng, starts, lam, share, 2 / 3, error, rho, sims, draws)
        null = p_values(rng, starts, lam, share, 1.0, error, rho, sims, draws)
        table.append(dict(starts=starts, touched=lam, missed=share, wrong=error, halving=float((halving <= 0.05).mean()),
            halving_holm=float((halving <= 0.025).mean()), third_cut=float((third <= 0.05).mean()),
            false_alarm=float((null <= 0.05).mean())))
    found: dict[str, dict | None] = dict(at_0_05=None, at_0_025=None)
    scanned = []
    for starts in range(minimum, ceiling + 1):
        values = p_values(rng, starts, touched, missed, 0.5, wrong, rho, sims, draws)
        row = dict(starts=starts, at_0_05=float((values <= 0.05).mean()), at_0_025=float((values <= 0.025).mean()))
        scanned.append(row)
        for level in found:
            if found[level] is None and row[level] >= target:
                found[level] = dict(starts=starts, rate=row[level], two_arms_usd=round(2 * starts * price, 2),
                    three_arms_usd=round(3 * starts * price, 2))
        if all(found.values()):
            break
    return dict(schema='memory-measure-simulation/1', seed=seed, sims=sims, draws=draws, rho=rho, table=table,
        search=dict(touched=touched, missed=missed, wrong=wrong, target=target, minimum=minimum, ceiling=ceiling,
            price_per_start_usd=price, smallest=found, scanned=scanned))


# --- the owner's labelling page ---------------------------------------------------------------------------------------------

def describe(batches: Sequence[Sequence[dict]]) -> str:
    """Input batches as one line: keys by name, typed text quoted, repeats counted."""
    words = []
    for batch in batches:
        for action in batch:
            kind = action.get('type')
            if kind == 'key':
                word = '+'.join([*(action.get('modifiers') or []), str(action.get('key'))])
            elif kind == 'text':
                word = json.dumps(action.get('text'), ensure_ascii=False)
            elif kind == 'wait':
                word = f"wait {action.get('seconds')}s"
            elif 'x' in action and 'y' in action:
                word = f"{kind} at {action['x']},{action['y']}"
            else:
                word = str(kind)
            if words and words[-1][0] == word:
                words[-1][1] += 1
            else:
                words.append([word, 1])
    return ' '.join(word if count == 1 else f'{word} ×{count}' for word, count in words)


class LabelConflict(MeasureError):
    """A label step out of order: a second blind label for a pair, or a check before the blind label."""


class LabelStore:
    """The sampled pairs with their frames, and the owner's labels in one JSON file rewritten at every click.

    Each pair is labelled in two steps. The blind label is the owner's first click, made on the item and the
    stretch's frames alone; it is recorded once and never changed. Then the pair's judge evidence is shown, and the
    owner keeps the answer or changes it: that is the checked label. The judges' verdicts, notes and cited frames
    are read when the server starts and are held here; `state` releases a pair's evidence only after its blind label
    is recorded, so nothing reaches the page before. The pairs are the random calibration pairs and then the engaged
    supplement, in one sequence, with nothing in the state to tell the two groups apart."""

    def __init__(self, run: Path) -> None:
        self.run, self.path, self.lock = run, run / 'labels.json', threading.Lock()
        sample = read_json(run / 'sample.json')
        self.sample_sha = file_sha256(run / 'sample.json')
        sampled, self.engaged_sha = list(sample['pairs']), None
        if (run / ENGAGED_FILE).is_file():
            engaged = read_json(run / ENGAGED_FILE)
            self.engaged_sha = file_sha256(run / ENGAGED_FILE)
            if engaged.get('random_sample_sha256') != self.sample_sha:
                raise MeasureError(f'{run / ENGAGED_FILE}: drawn against another random sample')
            sampled += engaged['pairs']
        if [pair['index'] for pair in sampled] != list(range(len(sampled))):
            raise MeasureError(f'{run}: the sampled pairs must be numbered 0, 1, 2, ... in order')
        items = {item['id']: item for item in load_items(run)[0]}
        packets = {packet['start']: packet for packet in load_mapping(run)['packets']}
        self.pairs, self.files = [], {}
        for pair in sampled:
            item, packet = items[pair['item']], packets[pair['start']]
            directory = run / 'judge-packets' / packet['packet']
            index = pair['index']
            self.files[f'/item/{index}.png'] = run / item['first_frame_file']
            frames = []
            for row in read_json(directory / 'manifest.json')['frames']:
                self.files[f"/frame/{index}/{row['frame']}.png"] = directory / row['file']
                frames.append(dict(name=row['frame'], image=f"/frame/{index}/{row['frame']}.png",
                    decision=row['decision'], inputs=' · '.join(row['inputs_before'])))
            with Image.open(self.files[f'/item/{index}.png']) as shown:  # the page reserves each image's space with it
                aspect = f'{shown.width} / {shown.height}'
            self.pairs.append(dict(index=index, start=pair['start'], item=pair['item'], decisions=packet['decisions'],
                short=packet['short'], place=item['place'], what=item['what'], image=f'/item/{index}.png', aspect=aspect,
                frames=frames))
        self.evidence = self.load_evidence(packets)
        self.saved = dict(schema=OWNER_LABELS_SCHEMA, sample_sha256=self.sample_sha, engaged_sha256=self.engaged_sha,
            labels={}, history=[])
        if self.path.is_file():
            saved = read_json(self.path)
            if not isinstance(saved, dict) or saved.get('schema') != OWNER_LABELS_SCHEMA:
                raise MeasureError(f'{self.path}: not {OWNER_LABELS_SCHEMA}; labels of another format are not read')
            if saved.get('sample_sha256') != self.sample_sha or saved.get('engaged_sha256') != self.engaged_sha:
                raise MeasureError(f'{self.path}: holds labels for another sample')
            self.saved = saved

    def load_evidence(self, packets: dict) -> dict[int, dict]:
        """What each pair shows after its blind label: the adjudicated label and each judge's label, note and
        cited screens, by the number the page gives the screen. It comes from the `agreement` command's
        `adjudicated.json`, the judges' events (label and cited frames) and, for the note, the lead's saved answers."""
        path = self.run / 'adjudicated.json'
        if not path.is_file():
            raise MeasureError(f'{path}: missing; run `events` for each judge and `agreement` before the labelling page, '
                'which shows the judges\' evidence after the owner\'s first click on each pair')
        adjudicated = read_json(path)
        if adjudicated.get('schema') != 'judge-adjudicated/1':
            raise MeasureError(f'{path}: not a judge-adjudicated/1 file')
        names = [*adjudicated['judges'], *([adjudicated['third']] if adjudicated.get('third') else [])]
        events = {name: {event.pair: event for event in judge.read_events(self.run / 'events' / f'{name}.jsonl')}
            for name in names}
        rows = {(row['start'], row['item']): row for row in adjudicated['pairs']}
        notes: dict[Path, dict] = {}

        def note(name: str, packet: str, item: str) -> str | None:
            answer = self.run / 'answers' / name / f'{packet}.json'
            if answer not in notes:
                given = read_json(answer)['answers'] if answer.is_file() else []
                notes[answer] = {row['item']: row.get('note') for row in given if isinstance(row, dict)}
            value = notes[answer].get(item)
            return value.strip() if isinstance(value, str) and value.strip() else None

        shown = {}
        for pair in self.pairs:
            key, packet = (pair['start'], pair['item']), packets[pair['start']]
            screen = {packet['frames'][frame['name']]: at for at, frame in enumerate(pair['frames'], 1)}
            judges = [dict(name=name, label=events[name][key].label, note=note(name, packet['packet'], pair['item']),
                screens=sorted(screen[source] for source in events[name][key].cited_frames if source in screen))
                for name in names if key in events[name]]
            shown[pair['index']] = dict(adjudicated=rows[key]['label'], by=rows[key]['by'], judges=judges,
                screens=sorted({number for entry in judges for number in entry['screens']}))
        return shown

    def state(self) -> dict:
        """What the page shows. A pair's evidence is in it only once that pair's blind label is recorded."""
        with self.lock:
            blind = {index: entry['blind'] for index, entry in self.saved['labels'].items()}
            checked = {index: entry['checked'] for index, entry in self.saved['labels'].items() if entry['checked']}
        return dict(total=len(self.pairs), blind=blind, checked=checked,
            reveals={index: self.evidence[int(index)] for index in blind},
            choices=[[label, LABEL_TEXT[label]] for label in LABELS],
            pairs=[{key: pair[key] for key in ('index', 'place', 'what', 'image', 'aspect', 'decisions', 'short', 'frames')}
                for pair in self.pairs])

    def record(self, index: object, step: object, label: object = None, keep: object = False) -> None:
        """Record the blind label (once) or the checked label of a pair. `keep` checks the pair with its blind label.
        A checked label equal to the one already recorded changes nothing, so a repeated click is one action."""
        if type(index) is not int or not 0 <= index < len(self.pairs) or step not in ('blind', 'checked') \
                or type(keep) is not bool or keep and (step != 'checked' or label is not None) \
                or not keep and label not in LABELS:
            raise MeasureError('Unknown pair, step or label')
        pair, now = self.pairs[index], datetime.now(timezone.utc).isoformat(timespec='seconds')
        where = dict(index=index, start=pair['start'], item=pair['item'])
        with self.lock:
            entry = self.saved['labels'].get(str(index))
            if step == 'blind':
                if entry is not None:
                    raise LabelConflict('The first answer is recorded and is not changed')
                self.saved['labels'][str(index)] = dict(where, blind=label, blind_time=now, checked=None, checked_time=None)
                self.saved['history'].append(dict(where, step='blind', label=label, time=now))
            else:
                if entry is None:
                    raise LabelConflict('The first answer comes before the check')
                label = entry['blind'] if keep else label
                if entry['checked'] == label:
                    return
                entry.update(checked=label, checked_time=now)
                self.saved['history'].append(dict(where, step='keep' if label == entry['blind'] else 'change', label=label,
                    time=now))
            write_json(self.path, self.saved)


def label_server(run: Path, port: int = 8765) -> ThreadingHTTPServer:
    """The labelling page's server, bound to the loopback address only."""
    store = LabelStore(run)

    class Handler(BaseHTTPRequestHandler):
        def send(self, status: int, kind: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def json(self, status: int, value: object) -> None:
            self.send(status, 'application/json', json.dumps(value).encode())

        def do_GET(self) -> None:  # noqa: N802 (the base class names it)
            path = self.path.split('?', 1)[0]
            if path == '/':
                self.send(200, 'text/html; charset=utf-8', PAGE.encode())
            elif path == '/api/state':
                self.json(200, store.state())
            elif path in store.files:
                self.send(200, 'image/png', store.files[path].read_bytes())
            else:
                self.json(404, dict(error='not found'))

        def do_POST(self) -> None:  # noqa: N802
            # A JSON content type cannot be sent by another site's page without a preflight this server never answers.
            if self.path != '/api/label' or self.headers.get('Content-Type') != 'application/json':
                return self.json(404, dict(error='not found'))
            # A page reached under another name (DNS rebinding) still sends that name as Host.
            if (self.headers.get('Host') or '').rsplit(':', 1)[0] not in ('127.0.0.1', 'localhost'):
                return self.json(403, dict(error='labels are accepted on 127.0.0.1 or localhost only'))
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get('Content-Length') or 0), 4096)))
                store.record(body.get('index'), body.get('step'), body.get('label'), body.get('keep', False))
            except LabelConflict as error:
                return self.json(409, dict(error=str(error)))
            except (ValueError, AttributeError):
                return self.json(400, dict(error='unknown pair, step or label'))
            self.json(200, store.state())

        def log_message(self, *_) -> None:
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calibration labels</title>
<style>
:root { color-scheme: light dark; --bg: #f5f4f0; --panel: #ffffff; --ink: #1b1a18; --muted: #5c5953; --line: #d5d2ca;
  --accent: #1d5ca6; --on-accent: #ffffff; --chip: #eae8e1; --chosen: #0b6a3d; --warn: #a3260f; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #151617; --panel: #202224; --ink: #eceae5; --muted: #aaa69f; --line: #3b3e41; --accent: #86b7f0;
    --on-accent: #0c1a29; --chip: #2b2e31; --chosen: #74d6a4; --warn: #ff9d87; }
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { background: var(--bg); color: var(--ink); font: 16px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 920px; margin: 0 auto; padding: 12px 16px 0; }
header { display: flex; align-items: center; gap: 12px; }
header h1 { font-size: 18px; margin: 0; flex: 1; font-variant-numeric: tabular-nums; }
progress { width: 100%; height: 8px; margin: 10px 0 14px; accent-color: var(--accent); }
h2 { font-size: 13px; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); margin: 0 0 8px; }
section { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px; margin-bottom: 12px; }
.item { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 220px); gap: 12px; align-items: start; }
.item dl { margin: 0; }
.item dt { color: var(--muted); font-size: 13px; }
.item dd { margin: 0 0 8px; font-size: 18px; overflow-wrap: anywhere; }
figure { margin: 0; }
figcaption, .hint { color: var(--muted); font-size: 13px; }
img { display: block; width: 100%; height: auto; border-radius: 6px; border: 1px solid var(--line); cursor: zoom-in;
  background: var(--chip); }
.strip { max-height: 52vh; min-height: 180px; overflow-y: auto; display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; padding-right: 4px; margin-top: 8px; }
.strip figcaption { overflow-wrap: anywhere; }
.strip b { color: var(--ink); font-variant-numeric: tabular-nums; }
button { font: inherit; color: var(--ink); background: var(--chip); border: 1px solid var(--line); border-radius: 10px;
  padding: 8px 14px; cursor: pointer; }
button:disabled { opacity: .45; cursor: default; }
button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
/* The answer bar is fixed to the window, so a button never moves under the pointer while frames load. */
.answers { position: fixed; left: 0; right: 0; bottom: 0; background: var(--bg); padding: 10px 16px 14px;
  border-top: 1px solid var(--line); z-index: 2; }
.answers > div { max-width: 888px; margin: 0 auto; }
.answers p { margin: 0 0 8px; font-weight: 600; }
.choices { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.choices button { min-height: 64px; font-size: 17px; font-weight: 600; background: var(--accent); color: var(--on-accent);
  border-color: var(--accent); }
.choices button.chosen { background: var(--chosen); border-color: var(--chosen); }
.choices button.chosen::after { content: " \\2713"; }
#keep { display: block; width: 100%; min-height: 44px; margin: 0 0 8px; font-size: 17px; font-weight: 600;
  background: var(--chosen); color: var(--on-accent); border-color: var(--chosen); }
#reveal ul { margin: 6px 0; padding-left: 20px; }
#reveal li { margin-bottom: 4px; overflow-wrap: anywhere; }
#reveal .note { color: var(--muted); }
.strip figure.cited img { outline: 4px solid var(--chosen); outline-offset: -2px; }
.strip figure.cited figcaption { color: var(--chosen); font-weight: 600; }
#error { color: var(--warn); font-weight: 600; margin: 8px 0 0; }
#done { text-align: center; padding: 18vh 0; }
#done h1 { font-size: 34px; margin: 0 0 8px; }
#zoom { position: fixed; inset: 0; background: rgba(0, 0, 0, .86); display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 10px; padding: 12px; z-index: 5; }
#zoom img { width: auto; max-width: 100%; max-height: 78vh; cursor: zoom-out; }
#zoom p { color: #f1efea; margin: 0; text-align: center; overflow-wrap: anywhere; max-width: 100%; }
#zoom div { display: flex; gap: 10px; }
[hidden] { display: none !important; }
@media (max-width: 520px) { .item { grid-template-columns: 1fr; } .choices button { font-size: 15px; } }
</style>
</head>
<body>
<main>
  <div id="work" hidden>
    <header>
      <button id="back" type="button">&larr; Back</button>
      <h1 id="count"></h1>
      <button id="forward" type="button">Next &rarr;</button>
    </header>
    <progress id="progress" value="0" max="1"></progress>
    <section>
      <h2>The known item</h2>
      <div class="item">
        <dl><dt>What</dt><dd id="what"></dd><dt>Where</dt><dd id="place"></dd></dl>
        <figure><img id="item-image" alt="The frame that first shows the item"><figcaption>The frame that first shows it. Click to enlarge.</figcaption></figure>
      </div>
    </section>
    <section id="reveal" hidden>
      <h2>What the judges said</h2>
      <p id="reveal-verdict"></p>
      <ul id="reveal-judges"></ul>
      <div class="hint" id="reveal-screens"></div>
    </section>
    <section>
      <h2>What the player did in this stretch</h2>
      <div class="hint" id="hint"></div>
      <div class="strip" id="strip"></div>
    </section>
    <div class="answers" id="answers"><div>
      <p id="prompt"></p>
      <button id="keep" type="button" hidden></button>
      <div class="choices" id="choices"></div>
      <div id="error" hidden>Not saved: the label server did not answer. Nothing is lost; click again.</div>
    </div></div>
  </div>
  <div id="done" hidden>
    <h1 id="done-title"></h1>
    <p>Every label is saved. You can close this page.</p>
    <button id="done-back" type="button">&larr; Back to the last pair</button>
  </div>
</main>
<div id="zoom" hidden>
  <img id="zoom-image" alt="">
  <p id="zoom-text"></p>
  <div><button id="zoom-previous" type="button">&larr; Earlier</button><button id="zoom-close" type="button">Close</button><button id="zoom-next" type="button">Later &rarr;</button></div>
</div>
<script>
'use strict';
let state = null, at = 0, zoomed = [], zoomAt = 0, ready = 0, sending = false;
const el = id => document.getElementById(id);

// A pair is in one of three phases. 'blind': nothing recorded, and the page holds no judge evidence for it.
// 'check': the first click is recorded and the judges' evidence is shown. 'done': the checked label is recorded too.
function phaseOf(i) { return !(i in state.blind) ? 'blind' : !(i in state.checked) ? 'check' : 'done'; }

function firstOpen() {
  for (let i = 0; i < state.total; i++) if (phaseOf(i) !== 'done') return i;
  return state.total;
}

function wordsOf(label) { return state.choices.find(choice => choice[0] === label)[1]; }

const BY = {agreement: 'both judges agree', third: 'settled by the third judge',
  third_alone: 'the third judge chose a label neither of the others gave'};

function showReveal(reveal) {
  el('reveal-verdict').textContent = reveal.adjudicated
    ? 'Adjudicated label: ' + wordsOf(reveal.adjudicated) + ' (' + BY[reveal.by] + ').'
    : 'Not settled: the two judges differ and no third verdict is saved for this pair.';
  const list = el('reveal-judges');
  list.replaceChildren();
  for (const entry of reveal.judges) {
    const item = document.createElement('li'), name = document.createElement('b'), note = document.createElement('span');
    name.textContent = entry.name;
    note.className = 'note';
    note.textContent = entry.note ? ' \\u2014 \\u201c' + entry.note + '\\u201d' : '';
    item.append(name, ': ' + wordsOf(entry.label) + (entry.screens.length ? ', cited screens ' + entry.screens.join(', ') : ''), note);
    list.append(item);
  }
  el('reveal-screens').textContent = reveal.screens.length
    ? 'Screens a judge cited: ' + reveal.screens.join(', ') + '. They are outlined in the strip below.'
    : 'No judge cited a screen for this pair.';
}

function showZoom() {
  const shot = zoomed[zoomAt];
  el('zoom-image').src = shot.image;
  el('zoom-text').textContent = shot.text;
  el('zoom-previous').disabled = zoomAt === 0;
  el('zoom-next').disabled = zoomAt === zoomed.length - 1;
  el('zoom-previous').hidden = el('zoom-next').hidden = zoomed.length < 2;
  el('zoom').hidden = false;
}

// Guarded like the answers: the second click of a double-click on Close lands on a screen beneath and must not reopen the view.
function openZoom(list, index) { if (Date.now() < ready) return; zoomed = list; zoomAt = index; showZoom(); }

// Every way of closing the enlarged view comes here. The answer buttons lie under it, so the guard is re-armed:
// the second click of a double-click on Close, the backdrop or the image must not record a label.
function closeZoom() { el('zoom').hidden = true; ready = Date.now() + 400; }

function render() {
  const done = at >= state.total;
  el('work').hidden = done;
  el('done').hidden = !done;
  el('zoom').hidden = true;
  el('error').hidden = true;
  if (done) { el('done-title').textContent = 'All ' + state.total + ' done'; return; }
  const pair = state.pairs[at];
  el('count').textContent = 'Pair ' + (at + 1) + ' of ' + state.total;
  el('progress').max = state.total;
  el('progress').value = Object.keys(state.checked).length;
  el('back').disabled = at === 0;
  const phase = phaseOf(at), reveal = state.reveals[at];
  el('forward').hidden = phase !== 'done';
  el('keep').hidden = phase !== 'check';
  el('keep').disabled = false;
  el('reveal').hidden = !reveal;
  if (reveal) showReveal(reveal);
  const citedBy = number => reveal ? reveal.judges.filter(entry => entry.screens.includes(number)).map(entry => entry.name) : [];
  const first = state.blind[at], last = state.checked[at];
  el('prompt').textContent = phase === 'blind' ? 'What did the player do about this item?'
    : phase === 'check' ? 'You answered \\u201c' + wordsOf(first) + '\\u201d. Keep your answer, or change it?'
    : 'Your answer is \\u201c' + wordsOf(last) + '\\u201d' + (last === first ? '' : ' (you first answered \\u201c' + wordsOf(first) + '\\u201d)')
      + '. Click another to change it.';
  el('keep').textContent = phase === 'check' ? 'Keep my answer: ' + wordsOf(first) : '';
  el('keep').onclick = () => submit({index: at, step: 'checked', keep: true});
  el('what').textContent = pair.what;
  el('place').textContent = pair.place;
  el('item-image').src = pair.image;
  el('item-image').style.aspectRatio = pair.aspect;
  el('item-image').onclick = () => openZoom([{image: pair.image, text: pair.what + ' \\u2014 ' + pair.place}], 0);
  el('hint').textContent = pair.frames.length + ' screens from ' + pair.decisions + ' decisions, oldest first: every third changed screen. '
    + 'Under each screen is what the player pressed before it. Click a screen to enlarge it.';
  const shots = pair.frames.map((frame, i) => ({image: frame.image,
    text: 'Screen ' + (i + 1) + ' of ' + pair.frames.length + (citedBy(i + 1).length ? ' \\u2014 cited by ' + citedBy(i + 1).join(', ') : '')
      + (frame.inputs ? ' \\u2014 before it: ' + frame.inputs : '')}));
  const strip = el('strip');
  strip.replaceChildren();
  strip.scrollTop = 0;
  pair.frames.forEach((frame, i) => {
    const figure = document.createElement('figure'), image = document.createElement('img'),
      caption = document.createElement('figcaption'), number = document.createElement('b');
    image.style.aspectRatio = pair.aspect;
    image.loading = 'lazy';
    image.src = frame.image;
    image.alt = 'Screen ' + (i + 1);
    image.onclick = () => openZoom(shots, i);
    number.textContent = String(i + 1);
    const by = citedBy(i + 1);
    figure.className = by.length ? 'cited' : '';
    caption.append(number, (by.length ? ' \\u00b7 cited by ' + by.join(', ') : '') + (frame.inputs ? ' \\u00b7 ' + frame.inputs : ''));
    figure.append(image, caption);
    strip.append(figure);
  });
  const choices = el('choices');
  choices.replaceChildren();
  for (const [label, words] of state.choices) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = words;
    button.className = (phase === 'done' ? last : phase === 'check' ? first : null) === label ? 'chosen' : '';
    button.onclick = () => submit({index: at, step: phase === 'blind' ? 'blind' : 'checked', label: label});
    choices.append(button);
  }
  document.querySelector('main').style.paddingBottom = (el('answers').offsetHeight + 16) + 'px';
  ready = Date.now() + 400;  // a second click of a double-click must not label the pair that has just appeared
}

function busy(on) {
  for (const button of [...el('choices').children, el('keep')]) button.disabled = on;
}

// One click is one request: the guard drops the second click of a double-click, and the buttons stay disabled until the
// server has answered. The blind label keeps the owner on the pair to see the evidence; the checked label moves on.
async function submit(body) {
  if (sending || Date.now() < ready) return;
  sending = true;
  busy(true);
  try {
    const response = await fetch('/api/label', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)});
    if (response.status === 409) {  // another request got there first: show what the server holds
      state = await (await fetch('/api/state')).json();
      render();
      return;
    }
    if (!response.ok) throw new Error('refused');
    state = await response.json();
  } catch (error) {
    busy(false);
    el('error').hidden = false;
    return;
  } finally {
    sending = false;
  }
  if (body.step === 'blind') {
    render();
    el('reveal').scrollIntoView({block: 'start'});
  } else {
    at += 1;
    render();
    window.scrollTo(0, 0);
  }
}

function step(by) { at = Math.max(0, Math.min(state.total, at + by)); render(); window.scrollTo(0, 0); }

el('back').onclick = () => step(-1);
el('done-back').onclick = () => step(-1);
el('forward').onclick = () => step(1);
el('zoom-close').onclick = closeZoom;
el('zoom-image').onclick = closeZoom;
el('zoom').onclick = event => { if (event.target === el('zoom')) closeZoom(); };
el('zoom-previous').onclick = () => { zoomAt -= 1; showZoom(); };
el('zoom-next').onclick = () => { zoomAt += 1; showZoom(); };
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeZoom(); });

fetch('/api/state').then(response => response.json()).then(value => { state = value; at = firstOpen(); render(); });
</script>
</body>
</html>
'''


# --- rendering and the command line -------------------------------------------------------------------------------------

def _range(entry: dict, digits: int = 3) -> str:
    value, interval = entry.get('value'), entry.get('interval')
    shown = 'undefined' if value is None else f'{value:.{digits}f}'
    return shown + (f' (95% interval {interval[0]:.{digits}f} to {interval[1]:.{digits}f})' if interval else '')


def _verdict(passed: bool | None) -> str:
    return 'not decided' if passed is None else 'pass' if passed else 'fail'


def render_agreement(report: dict) -> str:
    owner, passes = report['owner'], report['passes']
    touched = owner['touched']
    owner_line =f"{owner['matched']} of {owner['compared']} compared" + (
        f" (exact 95% interval {owner['interval'][0]:.3f} to {owner['interval'][1]:.3f})" if owner['interval'] else '')
    lines = [f"{report['pairs']} pairs; judges {report['judges'][0]} and {report['judges'][1]}; third {report['third'] or 'none'}; "
        f"bootstrap over pairs, seed {report['bootstrap']['seed']}, {report['bootstrap']['draws']} draws",
        f"note: {report['bootstrap']['note']}",
        f"agreement {_range(report['agreement'])}: {_verdict(passes['agreement'])} against at least {MIN_AGREEMENT}",
        f"Cohen's kappa {_range(report['kappa'])}: {_verdict(passes['kappa'])} against at least {MIN_KAPPA}",
        f"share of cannot_tell over both judges' labels {_range(report['cannot_tell'])}",
        "cannot_tell among straight, missed and cannot_tell (the decision rule's share; no conclusion above 0.30): "
        + '; '.join(f"{name} {_share(part)}" for name, part in report['cannot_tell_of_touched'].items()),
        f"adjudicated label against the owner's: {owner_line}: {_verdict(passes['owner'])} against at least "
        f"{MIN_OWNER_MATCH} of {OWNER_PAIRS}" + ('' if owner['compared'] == OWNER_PAIRS else
            f" (needs all {OWNER_PAIRS} labelled and adjudicated)"),
        f"  on pairs the owner or the judges called straight or missed: {touched['matched']} of {touched['compared']} compared"
        + (f" (exact 95% interval {touched['interval'][0]:.3f} to {touched['interval'][1]:.3f})" if touched['interval'] else ''),
        f"  pairs the owner called not_engaged that were adjudicated straight or missed (false engagement): "
        f"{owner['false_engagement']}",
        f"  (the calibration uses the owner's blind labels only: the first click on each pair, before any judge's work is shown)",
        f"engaged pairs, not in the calibration ({owner['engaged']['of']} drawn): blind labels against the adjudicated label: "
        f"{_matched(owner['engaged'])}; on pairs the owner or the judges called straight or missed: "
        f"{_matched(owner['engaged']['touched'])}; false engagement {owner['engaged']['false_engagement']}",
        f"touched-items error that `measure` uses, random and engaged pairs together (blind labels): "
        f"{_matched(owner['touched_all'])}",
        f"checked labels, {owner['checked']['note']}: {owner['checked']['changed']} of {owner['checked']['checked_pairs']} "
        f"checked pairs differ from the blind label; checked labels against the adjudicated label: random pairs "
        f"{_matched(owner['checked']['random'])}; engaged pairs {_matched(owner['checked']['engaged'])}",
        f"disputed pairs {len(report['disputed'])}, not yet adjudicated {report['unresolved']}"
        + (f"; packets for a third judge: {' '.join(report['third_judge_packets'])}" if report['third_judge_packets'] else ''),
        f"pairs the third judge settled with a label neither judge gave (third_alone): {report['third_alone']}"]
    lines.extend(f"  {row['start']} / {row['item']}: " + ', '.join(f'{name} {label}' for name, label in row['labels'].items())
        for row in report['disputed'] if row['by'] == 'third_alone')
    lines.append(f"judge calibration: {_verdict(report['pass'])}")
    return '\n'.join(lines)


def _matched(part: dict) -> str:
    return f"{part['matched']} of {part['compared']} match" + (
        f" (exact 95% interval {part['interval'][0]:.3f} to {part['interval'][1]:.3f})" if part['interval'] else '')


def _share(part: dict) -> str:
    return f"{part['cannot_tell']} of {part['of']}" + ('' if part['value'] is None else f" = {part['value']:.3f}")


def _error(part: dict) -> str:
    return (f"{part['differ']} of {part['compared']} differ, error {part['value']:.3f} (exact 95% interval "
        f"{part['interval'][0]:.3f} to {part['interval'][1]:.3f})")


def render_measure(report: dict) -> str:
    lines = [f"{report['pairs']} adjudicated pairs: " + ', '.join(f'{label} {count}' for label, count in report['labels'].items())
        + f"; bootstrap over stretches, seed {report['bootstrap']['seed']}, {report['bootstrap']['draws']} draws",
        "cannot_tell among straight, missed and cannot_tell (the decision rule's share; no conclusion above 0.30): "
        + _share(report['cannot_tell_of_touched'])]
    calibration = report['calibration']
    if calibration is None:
        lines.append('judge calibration: not run (no agreement.json)')
    else:
        kappa = 'undefined' if calibration['kappa'] is None else f"{calibration['kappa']:.3f}"
        lines.append(f"judge calibration: {_verdict(calibration['pass'])}; agreement {calibration['agreement']:.3f}, kappa {kappa}, "
            f"owner match {calibration['owner_matched']} of {calibration['owner_compared']} compared, third judge alone on "
            f"{calibration['third_alone']} pairs")
    for name, title in (('all_stretches', 'all stretches'), ('full_stretches', 'full stretches only')):
        part = report[name]
        if not part['stretches']:
            lines.append(f'{title}: none')
            continue
        basis = f"{part['stretches']} stretches from {part['admissions']} admissions"
        rate, missed = part['touched_per_stretch'], part['missed_share']
        exact, rough = rate['exact_poisson_interval'], rate['interval']
        lines.append(f"{title} ({basis}; {part['decisions']} decisions, {part['touched']} touched, {part['missed']} missed):")
        lines.append(f"  known items touched per {report['per_decisions']} decisions {rate['value']:.2f}; exact Poisson 95% interval "
            f"{exact[0]:.2f} to {exact[1]:.2f} on {part['touched']} touched in {part['decisions']} decisions; rough percentile "
            f"bootstrap over {basis}: {rough[0]:.2f} to {rough[1]:.2f}")
        lines.append('  missed share among touched ' + ('undefined' if missed['value'] is None else f"{missed['value']:.3f}")
            + (f"; rough percentile bootstrap over {basis}: {missed['interval'][0]:.3f} to {missed['interval'][1]:.3f}"
                if missed['interval'] else ''))
    lines.extend(f"  {row['start']}{' (short)' if row['short'] else ''}: {row['decisions']} decisions; "
        + ', '.join(f'{label} {row[label]}' for label in LABELS) for row in report['stretches'])
    error = report['judge_error']
    if error is None or error['all_pairs'] is None:
        lines.append('judge error: no owner comparison yet (run `agreement` after the owner has labelled); --wrong is left as F below')
    else:
        lines.append(f"judge against the owner, all compared pairs: {_error(error['all_pairs'])}")
        if error['touched_pairs']:
            lines.append("  on pairs the owner or the judges called straight or missed, random and engaged pairs together, "
                "blind labels: " + _error(error['touched_pairs']))
        if not error['touched_measured']:
            sampled = error['touched_pairs']['compared'] if error['touched_pairs'] else 0
            lines.append(f"  the judge's error on touched items was not measured: {sampled} touched pairs were sampled, fewer than "
                f"{MIN_TOUCHED_SAMPLED}. The commands below use the error over all pairs, which agreement on not_engaged lowers.")
        lines.append("  pairs the owner called not_engaged that were adjudicated straight or missed (false engagement): "
            f"{error['false_engagement']}")
    if report['simulate_commands']:
        lines.append('simulate with:')
        lines.extend(f"  {entry['case']}: {entry['command']}" for entry in report['simulate_commands'])
    return '\n'.join(lines)


def render_simulation(report: dict) -> str:
    lines = [f"seed {report['seed']}, {report['sims']} simulated comparisons, {report['draws']} permutations each, "
        f"correlation {report['rho']}",
        'starts | touched | baseline missed | judge wrong | halving at 0.05 | halving at 0.025 (Holm, first step) | '
        'one-third cut at 0.05 | false alarm']
    lines.extend(f"{row['starts']} | {row['touched']:g} | {row['missed']:g} | {row['wrong']:g} | {row['halving']:.2f} | "
        f"{row['halving_holm']:.2f} | {row['third_cut']:.2f} | {row['false_alarm']:.3f}" for row in report['table'])
    search = report['search']
    lines.append(f"smallest starts per arm that detect a halving with probability at least {search['target']}, for "
        f"{search['touched']:g} items touched, missed share {search['missed']:g}, judge error {search['wrong']:g}; scanned "
        f"{search['minimum']} to {search['scanned'][-1]['starts']} of a ceiling of {search['ceiling']}; "
        f"${search['price_per_start_usd']:.2f} a start, curator sessions not included; a rate near the target has a "
        f"standard error of about {math.sqrt(search['target'] * (1 - search['target']) / report['sims']):.3f}, and the "
        "first size to reach it can be a start or two early (raise --sims to tighten):")
    for level, title in (('at_0_05', 'at 0.05'), ('at_0_025', "at Holm's first step, 0.025")):
        found = search['smallest'][level]
        if found is None:
            best = max(search['scanned'], key=lambda row: row[level])
            lines.append(f"  {title}: none up to {search['ceiling']} starts per arm (the best was {best[level]:.2f} at {best['starts']})")
        else:
            lines.append(f"  {title}: {found['starts']} starts per arm (rate {found['rate']:.2f}); ${found['two_arms_usd']:.2f} "
                f"for two arms, ${found['three_arms_usd']:.2f} for three")
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    packets = commands.add_parser('packets', help='packets for the annotators or the judges').add_subparsers(dest='kind', required=True)
    for kind in ('annotate', 'judge'):
        command = packets.add_parser(kind)
        command.add_argument('run', type=Path)
        command.add_argument('--runs', nargs='+', type=Path, required=True, help='sealed admission run directories, in order')
        command.add_argument('--every', type=int, default=3)
        command.add_argument('--min-changed', type=float, default=0.0, help='changed-pixel share above which a frame is changed')
        if kind == 'annotate':
            command.add_argument('--frames-per-packet', type=int, default=FRAMES_PER_PACKET)
        else:
            command.add_argument('--stretch', type=int, default=200, help='decisions per stretch')
            command.add_argument('--seed', type=int)
            command.add_argument('--no-item-frames', dest='item_frames', action='store_false',
                help='leave each item\'s first frame out of the packet (by default the judge gets it, as the owner does)')
    items = commands.add_parser('items', help='the known-item list from two annotators and the lead\'s matches')
    items.add_argument('run', type=Path)
    items.add_argument('--annotators', nargs=2, required=True, metavar=('A', 'B'))
    items.add_argument('--matches', type=Path, help='{"matches": [["<A entry>", "<B entry>"], ...]}: at least one match; '
        'an entry may appear in several matches (one place seen in several packets); any other top-level key, such as '
        'the lead\'s own "groups", is accepted and ignored')
    items.add_argument('--list', action='store_true', help='print every entry with its ID and write nothing')
    events = commands.add_parser('events', help='validate one judge\'s answers and write its judge events')
    events.add_argument('run', type=Path)
    events.add_argument('--judge', required=True)
    events.add_argument('--model', required=True)
    events.add_argument('answers', nargs='+', type=Path)
    sample = commands.add_parser('sample', help='draw the calibration pairs, or with --engaged the supplement')
    sample.add_argument('run', type=Path)
    sample.add_argument('--count', type=int, default=OWNER_PAIRS)
    sample.add_argument('--engaged', type=int, metavar='N', help='instead of the random draw, draw N further pairs that a '
        'judge called straight, missed or cannot_tell, outside the random draw, into sample-engaged.json; after `events`')
    sample.add_argument('--seed', type=int)
    server = commands.add_parser('label-server', help='the owner\'s labelling page on 127.0.0.1')
    server.add_argument('run', type=Path)
    server.add_argument('--port', type=int, default=8765)
    agree = commands.add_parser('agreement', help='the judges\' agreement and the owner comparison')
    agree.add_argument('run', type=Path)
    agree.add_argument('--judges', nargs=2, required=True, metavar=('A', 'B'))
    agree.add_argument('--third')
    stats = commands.add_parser('measure', help='items touched and the missed share, from adjudicated labels')
    stats.add_argument('run', type=Path)
    for command in (agree, stats):
        command.add_argument('--seed', type=int)
        command.add_argument('--draws', type=int, default=10000)
        command.add_argument('--json', action='store_true')
    sim = commands.add_parser('simulate', help='the protocol appendix\'s simulation')
    sim.add_argument('--touched', type=float, help='known items touched per start')
    sim.add_argument('--missed', type=float, help='the current player\'s missed share among touched')
    sim.add_argument('--wrong', type=float, help='the share of labels the judge gets wrong')
    sim.add_argument('--starts', type=int, default=12, help='starts per arm of the table row for given numbers')
    sim.add_argument('--rho', type=float, default=0.2)
    sim.add_argument('--sims', type=int, default=1500)
    sim.add_argument('--draws', type=int, default=400)
    sim.add_argument('--seed', type=int, default=590)
    sim.add_argument('--target', type=float, default=0.8)
    sim.add_argument('--min-starts', type=int, default=4)
    sim.add_argument('--ceiling', type=int, default=60, help='the most starts per arm the search tries')
    sim.add_argument('--price', type=float, default=3.58, help='dollars per start')
    sim.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'simulate':
            given = [value is not None for value in (args.touched, args.missed, args.wrong)]
            _, touched, missed, wrong = APPENDIX_ROWS[0]
            touched, missed, wrong = (default if value is None else value
                for value, default in ((args.touched, touched), (args.missed, missed), (args.wrong, wrong)))
            rows = [(args.starts, touched, missed, wrong)] if any(given) else APPENDIX_ROWS
            report = simulate(rows, touched, missed, wrong, rho=args.rho, sims=args.sims, draws=args.draws, seed=args.seed,
                target=args.target, minimum=args.min_starts, ceiling=args.ceiling, price=args.price)
            print(json.dumps(report, indent=1) if args.json else render_simulation(report))
            return 0
        run = measure_dir(args.run)
        if args.command == 'packets' and args.kind == 'annotate':
            index = annotate_packets(run, run_dirs(args.runs), args.every, args.frames_per_packet, args.min_changed)
            print(f"{len(index['packets'])} packets in {run / 'annotate'}; frames recorded {index['frames']['recorded']}, "
                f"changed {index['frames']['changed']}, kept {index['frames']['kept']}")
            for packet in index['packets']:
                print(f"  {packet['packet']}: {packet['admission']}, {len(packet['frames'])} frames, {packet['bytes']} bytes")
        elif args.command == 'packets':
            mapping = judge_packets(run, run_dirs(args.runs), args.stretch, args.every, args.min_changed, args.seed,
                args.item_frames)
            print(f"{len(mapping['packets'])} packets in {run / 'judge-packets'}; seed {mapping['seed']}; the mapping is "
                f"{run / 'private' / 'judge-mapping.json'} and is not for a judge")
            for packet in mapping['packets']:
                print(f"  {packet['packet']}: {packet['start']}{' (short)' if packet['short'] else ''}, "
                    f"{len(packet['frames'])} frames, {packet['bytes']} bytes")
        elif args.command == 'items' and args.list:
            index = read_json(run / 'annotate' / 'packets.json')
            for name in args.annotators:
                for identity, entry in read_annotations(run, name, index).items():
                    print(f"{name} {identity}: {entry['place']} | {entry['what']} | {' '.join(entry['frames'])}")
        elif args.command == 'items':
            if args.matches is None:
                raise MeasureError('items needs --matches FILE, or --list')
            value = build_items(run, args.annotators, args.matches)
            print(f"{len(value['items'])} known items in {run / 'items.json'}, sha256 {value['sha256']}")
            for name, count in value['counts'].items():
                print(f"  {name}: {count['entries']} entries, {count['in_an_item']} in an item, {count['dropped']} dropped")
            for item in value['items']:  # allowed: one place seen in several packets; printed so that it is seen
                for name, entries in item['listed'].items():
                    if len(entries) > 1:
                        print(f"  {item['id']} holds {len(entries)} entries of {name}: "
                            + ' '.join(entry['entry'] for entry in entries))
        elif args.command == 'events':
            written = judge_events(run, args.judge, args.model, args.answers)
            counts = Counter(event.label for event in written)
            print(f"{len(written)} judge events in {run / 'events' / (args.judge + '.jsonl')}: "
                + ', '.join(f'{label} {counts[label]}' for label in LABELS))
        elif args.command == 'sample' and args.engaged is not None:
            value = draw_engaged(run, args.engaged, args.seed)
            print(f"{value['count']} of {value['eligible']} eligible pairs drawn with seed {value['seed']} into "
                f"{run / ENGAGED_FILE}; judges {', '.join(value['judges'])}")
        elif args.command == 'sample':
            value = draw_sample(run, args.count, args.seed)
            print(f"{value['count']} of {value['population']} pairs drawn with seed {value['seed']} into {run / 'sample.json'}")
        elif args.command == 'label-server':
            httpd = label_server(run, args.port)
            print(f'Labelling page: http://127.0.0.1:{httpd.server_address[1]}/  (Ctrl-C stops it; labels are in '
                f"{run / 'labels.json'})", flush=True)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                httpd.server_close()
        elif args.command == 'agreement':
            report = agreement(run, args.judges, args.third, args.seed, args.draws)
            print(json.dumps(report, indent=1) if args.json else render_agreement(report))
        else:
            report = measure(run, args.seed, args.draws)
            print(json.dumps(report, indent=1) if args.json else render_measure(report))
    except (MeasureError, EvaluationError, FileExistsError) as error:
        print(f'memory_measure: {error}', file=sys.stderr)
        return 2
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        # A file of the run directory that is valid JSON of another shape: refuse it by name of the fault, no traceback.
        print(f'memory_measure: a file this command reads does not have the expected shape ({type(error).__name__}: '
            f'{error})', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
