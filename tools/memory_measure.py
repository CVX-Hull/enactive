"""The memory screen's measure gate (#386): packets, the known-item list, `judge` events and the statistics.

No game runs, no model is called and nothing is spent. The protocol is docs/design/memory-screen-protocol.md.
RUN is a directory whose parent is named `memory-measure` (`.runtime/memory-measure/<run>`); everything is
written there and nowhere else. ADMISSION is a sealed run directory (it holds `actors/NNN/host.jsonl` and
`sources/`). In the order the lead runs them:

  python -m tools.memory_measure packets annotate RUN --runs ADMISSION... [--every 3] [--frames-per-packet 60]
  python -m tools.memory_measure items RUN --annotators A B --list
  python -m tools.memory_measure items RUN --annotators A B --matches FILE
  python -m tools.memory_measure packets judge RUN --runs ADMISSION... [--stretch 200] [--every 3] [--seed N] [--item-frames]
  python -m tools.memory_measure sample RUN [--count 20] [--seed N]
  python -m tools.memory_measure label-server RUN [--port 8765]
  python -m tools.memory_measure events RUN --judge NAME --model MODEL ANSWER.json...
  python -m tools.memory_measure agreement RUN --judges A B [--third C] [--seed N] [--draws N] [--json]
  python -m tools.memory_measure measure RUN [--seed N] [--draws N] [--json]
  python -m tools.memory_measure simulate [--touched F] [--missed F] [--wrong F] [--ceiling N] [--price USD] [--json]

What RUN holds:
  annotate/packets.json, annotate/<packet>/     frames for the two annotators: manifest.json, instructions.md, frames/
  annotations/<annotator>/<packet>.json         each annotator's answer per packet (the lead saves them)
  items.json, items.json.sha256                 the known-item list, frozen: never overwritten
  judge-packets/<shuffled name>/                one stretch for a judge: manifest.json, instructions.md, items.json, frames/
  private/judge-mapping.json                    shuffled name -> admission, decisions and source IDs; never in a packet
  sample.json, labels.json                      the calibration pairs and the owner's labels
  events/<judge>.jsonl                          judge-events/1 (harness/evaluation/core/judge.py)
  agreement.json, adjudicated.json, measure.json

A frame is "changed" when `harness.trace.images.region_diff` over the whole image finds a pixel that differs from
the frame before it; a packet takes every third changed frame, the first included, with every input sent since
the packet's previous frame. Packets hold frames and inputs only: no store, no player record, no report, no
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
#: The appendix's rows: starts per arm, items touched per start, the current player's missed share, judge error.
APPENDIX_ROWS = ((12, 5, 0.7, 0.1), (12, 5, 0.7, 0.0), (12, 5, 0.7, 0.2), (12, 5, 0.6, 0.1), (12, 3, 0.7, 0.1),
    (12, 8, 0.7, 0.1), (16, 5, 0.7, 0.1), (8, 5, 0.7, 0.1))
#: A packet of 60 frames is about 50,000 image tokens at 960x640 (about 820 tokens a frame): a quarter of a
#: 200,000-token agent context, which leaves room for the manifest, the instructions and the answer. A judge
#: stretch of 200 decisions comes to about 65 frames, so both kinds of packet are the same size.
FRAMES_PER_PACKET = 60
NAME = re.compile('[a-z0-9][a-z0-9-]{0,39}')


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
    return dict(frame=name, file=f'frames/{name}.png', sha256=file_sha256(target), inputs_before=list(frame.inputs))


def seal_packet(directory: Path, manifest: dict, instructions: str) -> tuple[str, int]:
    """Write the instructions and the manifest, which lists every other file's hash. The packet's hash is the
    manifest's; the second value is the packet's size in bytes."""
    (directory / 'instructions.md').write_text(instructions, encoding='utf-8')
    files = {str(path.relative_to(directory)): file_sha256(path) for path in sorted(directory.rglob('*'))
        if path.is_file() and not path.is_relative_to(directory / 'frames')}
    sha = write_json(directory / 'manifest.json', dict(manifest, files=files), once=True)
    return sha, sum(path.stat().st_size for path in directory.rglob('*') if path.is_file())


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
  frame and this one, oldest first. Each inner list is one batch of inputs.
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
    pairs = pairs.get('matches') if isinstance(pairs, dict) else None
    if not isinstance(pairs, list):
        raise MeasureError(f'{matches}: expected {{"matches": [["<{first} entry>", "<{second} entry>"], ...]}}')
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def root(node: tuple[str, str]) -> tuple[str, str]:
        while parent.setdefault(node, node) != node:
            node = parent[node]
        return node

    for number, pair in enumerate(pairs, 1):
        if not isinstance(pair, list) or len(pair) != 2 or pair[0] not in listed[first] or pair[1] not in listed[second]:
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
  `decisions` is how many decisions the stretch has.
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
                  seed: int | None = None, item_frames: bool = False) -> dict:
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
    packets, names = [], set()
    with Building(run / 'judge-packets') as out:
        for admission, found in frames.items():
            for first in range(1, decisions[admission] + 1, stretch):
                last = min(first + stretch - 1, decisions[admission])
                kept = every_nth_changed([frame for frame in found if first <= frame.decision <= last], every)
                name = f's{rng.getrandbits(40):010x}'
                while name in names:
                    name = f's{rng.getrandbits(40):010x}'
                names.add(name)
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
                packets.append(dict(packet=name, start=f'{admission}:{first}-{last}', admission=admission, first=first,
                    last=last, decisions=count, short=count < stretch, sha256=sha, bytes=size, frames=sources))
        mapping = dict(schema='judge-mapping/1', seed=seed, stretch=stretch, every=every, min_changed=min_changed,
            item_frames=item_frames, items_sha256=items_sha, packets=packets)
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
        packet = packets.get(value.get('packet')) if isinstance(value, dict) else None
        if packet is None or not isinstance(value.get('answers'), list):
            raise MeasureError(f'{path}: expected {{"packet": "<a packet of this run>", "answers": [...]}}')
        if packet['packet'] in done:
            raise MeasureError(f"{path}: packet {packet['packet']} is answered by more than one file")
        done.add(packet['packet'])
        manifest = run / 'judge-packets' / packet['packet'] / 'manifest.json'
        if not manifest.is_file() or file_sha256(manifest) != packet['sha256']:
            raise MeasureError(f"{path}: packet {packet['packet']} is not the packet that was made")
        rows = value['answers']
        if any(not isinstance(row, dict) for row in rows):
            raise MeasureError(f'{path}: every answer is an object')
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


def binomial_interval(successes: int, trials: int, level: float = 0.95) -> list[float]:
    """The exact (Clopper-Pearson) interval for a binomial share."""
    tail = (1 - level) / 2

    def at_most(count: int, p: float) -> float:
        return sum(math.comb(trials, i) * p ** i * (1 - p) ** (trials - i) for i in range(count + 1))

    def solve(function, rising: bool) -> float:
        low, high = 0.0, 1.0
        for _ in range(60):
            middle = (low + high) / 2
            if (function(middle) < tail) == rising:
                low = middle
            else:
                high = middle
        return (low + high) / 2

    lower = 0.0 if successes == 0 else solve(lambda p: 1 - at_most(successes - 1, p), True)
    upper = 1.0 if successes == trials else solve(lambda p: at_most(successes, p), False)
    return [lower, upper]


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
        rows.append(dict(start=pair[0], item=pair[1], label=label, by='agreement' if same else 'third' if label else None,
            labels={judges[0]: first[pair], judges[1]: second[pair], **({third: tie[pair]} if pair in tie else {})}))
    unresolved = [row for row in rows if row['label'] is None]
    write_json(run / 'adjudicated.json', dict(schema='judge-adjudicated/1', judges=list(judges), third=third,
        unresolved=len(unresolved), pairs=rows))
    adjudicated = {(row['start'], row['item']): row['label'] for row in rows}
    labelled = matched = 0
    if (run / 'labels.json').is_file() and (run / 'sample.json').is_file():
        owner = read_json(run / 'labels.json')['labels']
        for pair in read_json(run / 'sample.json')['pairs']:
            given = owner.get(str(pair['index']))
            verdict = adjudicated[(pair['start'], pair['item'])]
            if given is not None and verdict is not None:
                labelled += 1
                matched += given['label'] == verdict
    decided = labelled == OWNER_PAIRS
    passes = dict(agreement=report['agreement']['value'] >= MIN_AGREEMENT,
        kappa=report['kappa']['value'] is not None and report['kappa']['value'] >= MIN_KAPPA,
        owner=matched >= MIN_OWNER_MATCH if decided else None)
    report.update(schema='judge-agreement/1', judges=list(judges), third=third, bootstrap=dict(seed=seed, draws=draws),
        owner=dict(compared=labelled, matched=matched, of=OWNER_PAIRS,
            interval=binomial_interval(matched, labelled) if labelled else None),
        disputed=[dict(start=row['start'], item=row['item'], packet=packets[row['start']], labels=row['labels'],
            adjudicated=row['label']) for row in rows if row['by'] != 'agreement'],
        unresolved=len(unresolved),
        third_judge_packets=sorted({packets[row['start']] for row in unresolved}),
        thresholds=dict(agreement=MIN_AGREEMENT, kappa=MIN_KAPPA, owner_match=MIN_OWNER_MATCH, owner_pairs=OWNER_PAIRS),
        passes=passes, **{'pass': None if passes['owner'] is None and all((passes['agreement'], passes['kappa']))
            else all(passes.values())})
    write_json(run / 'agreement.json', report)
    return report


def measure(run: Path, seed: int | None = None, draws: int = 10000) -> dict:
    """Known items touched per stretch length and the missed share among touched, from the adjudicated labels,
    each with a percentile bootstrap interval over stretches."""
    adjudicated = read_json(run / 'adjudicated.json')
    if adjudicated['unresolved']:
        raise MeasureError(f"{adjudicated['unresolved']} pairs are not adjudicated; run `agreement` with --third")
    mapping = load_mapping(run)
    seed = secrets.randbits(32) if seed is None else seed
    by_start: dict[str, Counter] = {packet['start']: Counter() for packet in mapping['packets']}
    for row in adjudicated['pairs']:
        by_start[row['start']][row['label']] += 1
    rows = [dict(start=packet['start'], decisions=packet['decisions'], short=packet['short'],
        **{label: by_start[packet['start']][label] for label in LABELS}) for packet in mapping['packets']]

    def over(selected: list[dict]) -> dict:
        if not selected:
            return dict(stretches=0)
        decisions = np.array([row['decisions'] for row in selected], dtype=float)
        missed = np.array([row['missed'] for row in selected], dtype=float)
        touched = missed + np.array([row['straight'] for row in selected], dtype=float)
        index = np.random.default_rng(seed).integers(0, len(selected), (draws, len(selected)))
        with np.errstate(divide='ignore', invalid='ignore'):
            rate = mapping['stretch'] * touched[index].sum(axis=1) / decisions[index].sum(axis=1)
            share = np.where(touched[index].sum(axis=1) > 0, missed[index].sum(axis=1) / touched[index].sum(axis=1), np.nan)
        return dict(stretches=len(selected), decisions=int(decisions.sum()), touched=int(touched.sum()), missed=int(missed.sum()),
            touched_per_stretch=dict(value=float(mapping['stretch'] * touched.sum() / decisions.sum()),
                interval=percentile_interval(rate)),
            missed_share=dict(value=float(missed.sum() / touched.sum()) if touched.sum() else None,
                interval=percentile_interval(share), undefined_draws=int(np.isnan(share).sum())))

    labels = Counter(row['label'] for row in adjudicated['pairs'])
    report = dict(schema='memory-measure/1', per_decisions=mapping['stretch'], bootstrap=dict(seed=seed, draws=draws),
        labels={label: labels[label] for label in LABELS}, pairs=len(adjudicated['pairs']),
        cannot_tell_share=labels['cannot_tell'] / len(adjudicated['pairs']) if adjudicated['pairs'] else None,
        all_stretches=over(rows), full_stretches=over([row for row in rows if not row['short']]), stretches=rows,
        judge_error=None)
    if (run / 'agreement.json').is_file():
        owner = read_json(run / 'agreement.json')['owner']
        if owner['compared']:
            report['judge_error'] = dict(value=1 - owner['matched'] / owner['compared'], compared=owner['compared'],
                source='one minus the adjudicated labels\' match with the owner\'s labels')
    write_json(run / 'measure.json', report)
    return report


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


class LabelStore:
    """The sampled pairs with their frames, and the owner's labels in one JSON file rewritten at every click.
    It reads the sample, the item list and the packets; it never opens a judge's answers or events."""

    def __init__(self, run: Path) -> None:
        self.run, self.path, self.lock = run, run / 'labels.json', threading.Lock()
        sample = read_json(run / 'sample.json')
        self.sample_sha = file_sha256(run / 'sample.json')
        items = {item['id']: item for item in load_items(run)[0]}
        packets = {packet['start']: packet for packet in load_mapping(run)['packets']}
        self.pairs, self.files = [], {}
        for pair in sample['pairs']:
            item, packet = items[pair['item']], packets[pair['start']]
            directory = run / 'judge-packets' / packet['packet']
            index = pair['index']
            self.files[f'/item/{index}.png'] = run / item['first_frame_file']
            frames = []
            for row in read_json(directory / 'manifest.json')['frames']:
                self.files[f"/frame/{index}/{row['frame']}.png"] = directory / row['file']
                frames.append(dict(name=row['frame'], image=f"/frame/{index}/{row['frame']}.png",
                    decision=row['decision'], inputs=describe(row['inputs_before'])))
            self.pairs.append(dict(index=index, start=pair['start'], item=pair['item'], decisions=packet['decisions'],
                short=packet['short'], place=item['place'], what=item['what'], image=f'/item/{index}.png', frames=frames))
        self.saved = dict(schema='owner-labels/1', sample_sha256=self.sample_sha, labels={}, history=[])
        if self.path.is_file():
            saved = read_json(self.path)
            if not isinstance(saved, dict) or saved.get('sample_sha256') != self.sample_sha:
                raise MeasureError(f'{self.path}: holds labels for another sample')
            self.saved = saved

    def state(self) -> dict:
        """What the page shows: no admission, packet name or verdict."""
        with self.lock:
            labels = {index: entry['label'] for index, entry in self.saved['labels'].items()}
        return dict(total=len(self.pairs), labels=labels, choices=[[label, LABEL_TEXT[label]] for label in LABELS],
            pairs=[{key: pair[key] for key in ('index', 'place', 'what', 'image', 'decisions', 'short', 'frames')}
                for pair in self.pairs])

    def record(self, index: object, label: object) -> None:
        if type(index) is not int or not 0 <= index < len(self.pairs) or label not in LABELS:
            raise MeasureError('Unknown pair or label')
        pair = self.pairs[index]
        entry = dict(index=index, start=pair['start'], item=pair['item'], label=label,
            time=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        with self.lock:
            self.saved['labels'][str(index)] = entry
            self.saved['history'].append(entry)
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
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get('Content-Length') or 0), 4096)))
                store.record(body.get('index'), body.get('label'))
            except (ValueError, AttributeError):
                return self.json(400, dict(error='unknown pair or label'))
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
.answers { position: sticky; bottom: 0; background: var(--bg); padding: 10px 0 14px; border-top: 1px solid var(--line); }
.answers p { margin: 0 0 8px; font-weight: 600; }
.choices { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.choices button { min-height: 64px; font-size: 17px; font-weight: 600; background: var(--accent); color: var(--on-accent);
  border-color: var(--accent); }
.choices button.chosen { background: var(--chosen); border-color: var(--chosen); }
.choices button.chosen::after { content: " \\2713"; }
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
      <button id="forward" type="button">Keep answer &rarr;</button>
    </header>
    <progress id="progress" value="0" max="1"></progress>
    <section>
      <h2>The known item</h2>
      <div class="item">
        <dl><dt>What</dt><dd id="what"></dd><dt>Where</dt><dd id="place"></dd></dl>
        <figure><img id="item-image" alt="The frame that first shows the item"><figcaption>The frame that first shows it. Click to enlarge.</figcaption></figure>
      </div>
    </section>
    <section>
      <h2>What the player did in this stretch</h2>
      <div class="hint" id="hint"></div>
      <div class="strip" id="strip"></div>
    </section>
    <div class="answers">
      <p>What did the player do about this item?</p>
      <div class="choices" id="choices"></div>
      <div id="error" hidden>Not saved: the label server did not answer. Nothing is lost; click again.</div>
    </div>
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
let state = null, at = 0, zoomed = [], zoomAt = 0;
const el = id => document.getElementById(id);

function firstOpen() {
  for (let i = 0; i < state.total; i++) if (!(i in state.labels)) return i;
  return state.total;
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

function openZoom(list, index) { zoomed = list; zoomAt = index; showZoom(); }

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
  el('progress').value = Object.keys(state.labels).length;
  el('back').disabled = at === 0;
  el('forward').hidden = !(at in state.labels);
  el('what').textContent = pair.what;
  el('place').textContent = pair.place;
  el('item-image').src = pair.image;
  el('item-image').onclick = () => openZoom([{image: pair.image, text: pair.what + ' \\u2014 ' + pair.place}], 0);
  el('hint').textContent = pair.frames.length + ' screens from ' + pair.decisions + ' decisions, oldest first: every third changed screen. '
    + 'Under each screen is what the player pressed before it. Click a screen to enlarge it.';
  const shots = pair.frames.map((frame, i) => ({image: frame.image,
    text: 'Screen ' + (i + 1) + ' of ' + pair.frames.length + (frame.inputs ? ' \\u2014 before it: ' + frame.inputs : '')}));
  const strip = el('strip');
  strip.replaceChildren();
  strip.scrollTop = 0;
  pair.frames.forEach((frame, i) => {
    const figure = document.createElement('figure'), image = document.createElement('img'),
      caption = document.createElement('figcaption'), number = document.createElement('b');
    image.src = frame.image;
    image.loading = 'lazy';
    image.alt = 'Screen ' + (i + 1);
    image.onclick = () => openZoom(shots, i);
    number.textContent = String(i + 1);
    caption.append(number, frame.inputs ? ' \\u00b7 ' + frame.inputs : '');
    figure.append(image, caption);
    strip.append(figure);
  });
  const choices = el('choices');
  choices.replaceChildren();
  for (const [label, words] of state.choices) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = words;
    button.className = state.labels[at] === label ? 'chosen' : '';
    button.onclick = () => choose(label);
    choices.append(button);
  }
}

async function choose(label) {
  for (const button of el('choices').children) button.disabled = true;
  try {
    const response = await fetch('/api/label', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({index: at, label: label})});
    if (!response.ok) throw new Error('refused');
    state = await response.json();
  } catch (error) {
    for (const button of el('choices').children) button.disabled = false;
    el('error').hidden = false;
    return;
  }
  at += 1;
  render();
  window.scrollTo(0, 0);
}

function step(by) { at = Math.max(0, Math.min(state.total, at + by)); render(); window.scrollTo(0, 0); }

el('back').onclick = () => step(-1);
el('done-back').onclick = () => step(-1);
el('forward').onclick = () => step(1);
el('zoom-close').onclick = () => { el('zoom').hidden = true; };
el('zoom-image').onclick = () => { el('zoom').hidden = true; };
el('zoom').onclick = event => { if (event.target === el('zoom')) el('zoom').hidden = true; };
el('zoom-previous').onclick = () => { zoomAt -= 1; showZoom(); };
el('zoom-next').onclick = () => { zoomAt += 1; showZoom(); };
document.addEventListener('keydown', event => { if (event.key === 'Escape') el('zoom').hidden = true; });

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
    owner_line = f"{owner['matched']} of {owner['compared']} compared" + (
        f" (exact 95% interval {owner['interval'][0]:.3f} to {owner['interval'][1]:.3f})" if owner['interval'] else '')
    lines = [f"{report['pairs']} pairs; judges {report['judges'][0]} and {report['judges'][1]}; third {report['third'] or 'none'}; "
        f"bootstrap over pairs, seed {report['bootstrap']['seed']}, {report['bootstrap']['draws']} draws",
        f"agreement {_range(report['agreement'])}: {_verdict(passes['agreement'])} against at least {MIN_AGREEMENT}",
        f"Cohen's kappa {_range(report['kappa'])}: {_verdict(passes['kappa'])} against at least {MIN_KAPPA}",
        f"share of cannot_tell over both judges' labels {_range(report['cannot_tell'])}",
        f"adjudicated label against the owner's: {owner_line}: {_verdict(passes['owner'])} against at least "
        f"{MIN_OWNER_MATCH} of {OWNER_PAIRS}" + ('' if owner['compared'] == OWNER_PAIRS else
            f" (needs all {OWNER_PAIRS} labelled and adjudicated)"),
        f"disputed pairs {len(report['disputed'])}, not yet adjudicated {report['unresolved']}"
        + (f"; packets for a third judge: {' '.join(report['third_judge_packets'])}" if report['third_judge_packets'] else ''),
        f"judge calibration: {_verdict(report['pass'])}"]
    return '\n'.join(lines)


def render_measure(report: dict) -> str:
    lines = [f"{report['pairs']} adjudicated pairs: " + ', '.join(f'{label} {count}' for label, count in report['labels'].items())
        + f"; bootstrap over stretches, seed {report['bootstrap']['seed']}, {report['bootstrap']['draws']} draws"]
    for name, title in (('all_stretches', 'all stretches'), ('full_stretches', 'full stretches only')):
        part = report[name]
        if not part['stretches']:
            lines.append(f'{title}: none')
            continue
        lines.append(f"{title} ({part['stretches']} stretches, {part['decisions']} decisions, {part['touched']} touched, "
            f"{part['missed']} missed): known items touched per {report['per_decisions']} decisions "
            f"{_range(part['touched_per_stretch'], 2)}; missed share among touched {_range(part['missed_share'])}")
    lines.extend(f"  {row['start']}{' (short)' if row['short'] else ''}: {row['decisions']} decisions; "
        + ', '.join(f'{label} {row[label]}' for label in LABELS) for row in report['stretches'])
    whole, error = report['all_stretches'], report['judge_error']
    if whole.get('touched') and whole['missed_share']['value'] not in (None, 0.0, 1.0):
        lines.append(f"simulate with: python -m tools.memory_measure simulate --touched {whole['touched_per_stretch']['value']:.2f} "
            f"--missed {whole['missed_share']['value']:.3f} --wrong "
            + (f"{error['value']:.3f}" if error else 'F  (no owner comparison yet: run `agreement` first)'))
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
        f"${search['price_per_start_usd']:.2f} a start, curator sessions not included:")
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
            command.add_argument('--item-frames', action='store_true', help='also give the judge each item\'s first frame')
    items = commands.add_parser('items', help='the known-item list from two annotators and the lead\'s matches')
    items.add_argument('run', type=Path)
    items.add_argument('--annotators', nargs=2, required=True, metavar=('A', 'B'))
    items.add_argument('--matches', type=Path, help='{"matches": [["<A entry>", "<B entry>"], ...]}')
    items.add_argument('--list', action='store_true', help='print every entry with its ID and write nothing')
    events = commands.add_parser('events', help='validate one judge\'s answers and write its judge events')
    events.add_argument('run', type=Path)
    events.add_argument('--judge', required=True)
    events.add_argument('--model', required=True)
    events.add_argument('answers', nargs='+', type=Path)
    sample = commands.add_parser('sample', help='draw the calibration pairs')
    sample.add_argument('run', type=Path)
    sample.add_argument('--count', type=int, default=OWNER_PAIRS)
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
        elif args.command == 'events':
            written = judge_events(run, args.judge, args.model, args.answers)
            counts = Counter(event.label for event in written)
            print(f"{len(written)} judge events in {run / 'events' / (args.judge + '.jsonl')}: "
                + ', '.join(f'{label} {counts[label]}' for label in LABELS))
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
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
