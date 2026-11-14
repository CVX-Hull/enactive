"""The memory measure (#386): packets for model judges, `judge` events, the standing use measures, the two
checks of a changed judge, and the simulation that sizes withholding.

No game runs, no model is called and nothing is spent: judging is done by host agents the lead starts, and this
tool only builds what they read and counts what they answer. The design is docs/design/general-memory.md,
sections 3 and 4. RUN is a directory whose parent is named `memory-measure` (`.runtime/memory-measure/<run>`);
everything is written there and nowhere else. ADMISSION is a sealed run directory (it holds
`actors/NNN/host.jsonl` and `sources/`). In the order the lead runs them:

  python -m tools.memory_measure packets use RUN --runs ADMISSION... --facts FILE [--budget TOKENS] [--every 3] [--seed N]
  python -m tools.memory_measure packets blind RUN --runs ADMISSION... --facts FILE [--budget TOKENS] [--every 3] [--seed N]
  python -m tools.memory_measure events RUN --judge NAME --model MODEL ANSWER.json...
  python -m tools.memory_measure agreement RUN --judges A B [--third C] [--json]
  python -m tools.memory_measure measure RUN [--seed N] [--draws N] [--json]

  python -m tools.memory_measure packets annotate RUN --runs ADMISSION... [--budget TOKENS] [--every 3]
  python -m tools.memory_measure items RUN --annotators A B --list
  python -m tools.memory_measure items RUN --annotators A B --matches FILE

  python -m tools.memory_measure anchor packets RUN --gate GATE [--dry-run]
  python -m tools.memory_measure anchor events RUN --judge NAME --model MODEL ANSWER.json...
  python -m tools.memory_measure anchor report RUN --judge NAME [--json]
  python -m tools.memory_measure prompt-check packets RUN --before BEFORE
  python -m tools.memory_measure prompt-check report RUN --before BEFORE --judges A B [--seed N] [--draws N] [--json]

  python -m tools.memory_measure simulate-withholding [--seed N] [--sims N] [--json | --render REPORT.json]

What RUN holds:
  judge-packets/<shuffled name>/      one window for a judge: manifest.json, instructions.md, facts.json, frames/
                                      and, in a use packet only, delivered.json
  private/judge-mapping.json          shuffled name -> admission, actor, decisions, source IDs and each fact's
                                      route; never in a packet
  events/<judge>.jsonl                judge-events/2 (harness/evaluation/core/judge.py)
  adjudicated.json, measure.json      the adjudicated labels and the standing use measures
  annotate/, annotations/, annotated-facts.json[.sha256]
                                      packets for two annotators, their answers and the matched list, frozen
  anchor/packets/, private/anchor.json, anchor/events/<judge>.jsonl, anchor/report-<judge>.json
                                      the measure gate's packets re-judged with its frozen prompt
  prompt-check.json                   the first two judges' agreement before and after a prompt change

FILE is the facts to judge, `judged-facts/1`: for each admission and actor, the facts by route (`lead`, `read`,
`index`, `withheld`), each with its id and text, and what was delivered (`briefing`, `reminders`). Delivery
writes it; until then the lead does. A use packet shows the routes, the briefing, the reminders and what the
player stated with its calls (`intent`, `cites`). A blind packet, for the benefit measure, shows frames, inputs
and the facts' text only.

A frame is "changed" when `harness.trace.images.region_diff` over the whole image finds a pixel whose largest
channel difference from the frame before it exceeds 16 of 255, that function's threshold. A packet takes every
third changed frame of its window, the first included, with every input sent since the packet's previous frame.
Windows are cut to a token budget, between decisions. `--runs` refuses a path under the held-out lineage's
evidence, `522-held-out`. A judge packet's frames and directory carry shuffled names.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import sys
from typing import Callable, Sequence
import uuid

import numpy as np

from harness.evaluation.core import judge
from harness.evaluation.core.host import frame_source
from harness.evaluation.core.records import EvaluationError, dumps, loads
from harness.jsonio import file_sha256
from harness.trace import images
from harness.trace.projection import ACTION_FIELDS
from tools.memory_reads import run_dirs
from tools.memory_screen_checks import read_lineage

USE_LABELS, HOLDS, ROUTES = judge.USE_LABELS, judge.HOLDS, judge.ROUTES
ANCHOR_LABELS = judge.ANCHOR_LABELS
FACTS_SCHEMA = 'judged-facts/1'
MAPPING_SCHEMA = 'judge-mapping/2'
OWNER_LABELS_SCHEMA = 'owner-labels/2'
ENGAGED_FILE = 'sample-engaged.json'
NAME = re.compile('[a-z0-9][a-z0-9-]{0,39}')
#: The held-out lineage's evidence directory; the measure never reads it.
HELD_OUT = '522-held-out'
#: The default size of one packet, in estimated tokens, for everything a judge reads: instructions, facts, what
#: was delivered, the manifest and the frames. It is 30% of a 200,000-token host agent context, which leaves the
#: rest for the host's own prompt and tools, the files as the agent re-reads them, and the answer. At 960x640 a
#: frame is about 820 tokens, so with a short fact list a packet holds about 65 frames: every third changed frame
#: of about 200 decisions, the stretch the measure gate's rates were measured on. A window is as long as the
#: budget allows and no longer; a long fact list takes its share from the frames, or is split over packets.
PACKET_TOKENS = 60_000
#: Text is counted at three characters a token. Four is the usual figure for prose; a packet's text is mostly
#: JSON and IDs, which take more tokens per character, and an estimate that runs high only shortens a window.
CHARS_PER_TOKEN = 3
#: The keys, schema line and file hashes of a manifest, beyond its frame rows.
MANIFEST_HEAD_TOKENS = 300
NOT_CORRECTED = ('These rates rest on the adjudicated labels of model judges: two judges on every pair and a third '
    'on the pairs they dispute. They are not corrected against a human truth; by the owner\'s decision of '
    '13 November 2026 the judges stand without owner audits. Read each rate with the first two judges\' agreement '
    'and dispute rate beside it.')
BOOTSTRAP_NOTE = ('a cluster bootstrap over starts: whole starts are drawn with replacement, so the labels of one '
    'start stay together; with few starts the interval is rough, and with one start there is none')


class MeasureError(ValueError):
    """An input that does not fit the measure's files, or a write the measure refuses."""


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


def json_text(value: object) -> str:
    return json.dumps(value, indent=1, ensure_ascii=False, allow_nan=False) + '\n'


def write_json(path: Path, value: object, *, once: bool = False) -> str:
    """Write indented JSON and return its SHA-256. `once` refuses an existing file."""
    data = json_text(value).encode()
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# --- token estimates --------------------------------------------------------------------------------------------------

def image_tokens(width: int, height: int) -> int:
    """An image's tokens from its pixel size: width x height / 750, after an image whose long edge exceeds
    1568 px is scaled down to it. That is the published rule of thumb for the vision models the host agents
    run on; this tool calls no model, so it is an estimate and nothing checks it."""
    scale = min(1.0, 1568 / max(width, height, 1))
    return math.ceil(width * scale * height * scale / 750)


def text_tokens(value: str) -> int:
    return math.ceil(len(value) / CHARS_PER_TOKEN)


# --- frames -----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Frame:
    """One recorded frame. `inputs` are the input batches sent since the frame before it, oldest first; `stated`
    is what the player said with its calls over the same span (`intent`, `cites`); `tokens` estimates the image.
    `input_decisions` keeps each batch's decision through sampling, privately, so a pre-read input cannot count."""

    run: str
    actor: str
    source: str
    decision: int
    path: Path
    inputs: tuple
    stated: tuple = ()
    tokens: int = 0
    changed: bool = True
    input_decisions: tuple[int | None, ...] = ()


def recorded_frames(runs: Sequence[Path], min_changed: float = 0.0) -> tuple[dict[str, list[Frame]], dict[str, dict]]:
    """Each admission's frames in the order its calls returned them, marked changed or not, and each of its
    actors' first and last decision. Only tool calls are read: a frame's source ID, the request that returned it,
    the inputs of `computer_input`, and the `intent` and `cites` a call's arguments carry."""
    for directory in runs:
        if HELD_OUT in Path(directory).resolve().parts:
            raise MeasureError(f'{directory}: the held-out lineage is not read for the memory measure')
    lineage, actors = read_lineage(runs)
    offsets = {run.name: run.offset for run in lineage}
    names = {(actor.run, actor.actor): actor.name for actor in actors}
    frames: dict[str, list[Frame]] = {}
    spans: dict[str, dict[str, tuple[int, int]]] = {}
    for directory, run in zip(runs, lineage):
        if run.name in frames:
            raise MeasureError(f'{run.name}: selected twice')
        spans[run.name] = {actor.name: (actor.first - offsets[run.name], actor.first - offsets[run.name] + actor.requests - 1)
            for actor in actors if actor.run == run.name}
        found, seen, pending, pending_decisions, stated, previous, owner = [], set(), [], [], [], None, None
        for call in run.facts.calls:
            if call.actor != owner:  # what one actor sent or said is never carried into the next actor's frames
                pending, pending_decisions, stated, owner = [], [], [], call.actor
            arguments = call.arguments if isinstance(call.arguments, dict) else {}
            if call.tool == 'computer_input':
                actions = arguments.get('actions')
                pending.append([{key: action[key] for key in ACTION_FIELDS if key in action}
                    for action in (actions if isinstance(actions, list) else []) if isinstance(action, dict)])
                pending_decisions.append(call.decision)
            said = {key: arguments[key] for key in ('intent', 'cites') if key in arguments}
            if said:
                stated.append(dict(tool=call.tool, **said))
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
            found.append(Frame(run.name, names[(run.name, call.actor)], source, call.decision, path, tuple(pending),
                tuple(stated), image_tokens(image.shape[1], image.shape[0]), bool(changed), tuple(pending_decisions)))
            pending, pending_decisions, stated, previous = [], [], [], image
        frames[run.name] = found
    return frames, spans


def every_nth_changed(frames: Sequence[Frame], every: int) -> list[Frame]:
    """Every `every`-th changed frame, the first included. Each kept frame carries every input, and everything
    the player stated, since the kept one before it, so nothing is lost with the frames that are left out."""
    kept, inputs, input_decisions, stated, count = [], [], [], [], 0
    for frame in frames:
        inputs.extend(frame.inputs)
        input_decisions.extend(frame.input_decisions)
        stated.extend(frame.stated)
        if not frame.changed:
            continue
        if count % every == 0:
            kept.append(replace(frame, inputs=tuple(inputs), input_decisions=tuple(input_decisions), stated=tuple(stated)))
            inputs, input_decisions, stated = [], [], []
        count += 1
    return kept


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


def frame_row(frame: Frame, name: str, blind: bool) -> dict:
    """A frame's manifest row before its file is copied. A blind row holds the frame and the inputs only: what
    the player stated can name a fact it was given, so it is left out."""
    row = dict(frame=name, file=f'frames/{name}.png', inputs_before=[describe([batch]) for batch in frame.inputs])
    if not blind and frame.stated:
        row['stated_before'] = list(frame.stated)
    return row


def cut(frames: Sequence[Frame], cost: Callable[[Frame], int], budget: int, *,
        packet_cost: Callable[[Sequence[Frame], int, int], int] | None = None,
        first_decision: int | None = None, last_decision: int | None = None) -> list[list[Frame]]:
    """Cut between decisions, retaining an oversized decision by itself. Additive costs use the even share
    over the fewest possible parts. Complete serialized costs receive the actual inclusive window bounds;
    their greedy fit supplies an average packet target, then a second pass evens the windows toward it where
    decisions and the budget allow, without increasing the number of windows."""
    groups: list[list[Frame]] = []
    for frame in frames:
        if groups and groups[-1][0].decision == frame.decision:
            groups[-1].append(frame)
        else:
            groups.append([frame])
    if not groups:
        return []
    costs = [sum(cost(frame) for frame in group) for group in groups]
    cached: dict[tuple[int, int], int] = {}

    def price(start: int, end: int) -> int:
        key = start, end
        if key not in cached:
            if packet_cost:
                first = (frames[0].decision if first_decision is None else first_decision) if start == 0 else \
                    groups[start - 1][-1].decision + 1
                last = (frames[-1].decision if last_decision is None else last_decision) if end == len(groups) else \
                    groups[end - 1][-1].decision
                cached[key] = packet_cost([frame for group in groups[start:end] for frame in group], first, last)
            else:
                cached[key] = sum(costs[start:end])
        return cached[key]

    def split(target: float) -> list[tuple[int, int]]:
        parts, start = [], 0
        for end in range(2, len(groups) + 1):
            current, extended = price(start, end - 1), price(start, end)
            nearer = packet_cost is not None and target != math.inf and abs(current - target) < abs(extended - target)
            if extended > budget or current >= target or nearer:
                parts.append((start, end - 1))
                start = end - 1
        return [*parts, (start, len(groups))]

    if packet_cost:
        fitted = split(math.inf)
        target = sum(price(start, end) for start, end in fitted) / len(fitted)
        evened = split(target)
        parts = evened if len(evened) <= len(fitted) else fitted
    else:
        target = sum(costs) / max(1, math.ceil(sum(costs) / budget))
        parts = split(target)
    return [[frame for group in groups[start:end] for frame in group] for start, end in parts]


def available_after(frame: Frame, decision: int) -> bool:
    """A sampled frame whose carried inputs were all chosen after the delivery/read result was available."""
    return frame.decision > decision and len(frame.input_decisions) == len(frame.inputs) and all(
        at is not None and at > decision for at in frame.input_decisions)


def copy_frame(frame: Frame, directory: Path, name: str, blind: bool) -> dict:
    target = directory / 'frames' / f'{name}.png'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(frame.path, target)
    return dict(frame_row(frame, name, blind), sha256=file_sha256(target))


def budget_entry(budget: int, text_estimate: int, frames: Sequence[Frame]) -> dict:
    image_estimate = sum(frame.tokens for frame in frames)
    return dict(tokens=budget, estimated=dict(images=image_estimate, text=text_estimate, total=image_estimate + text_estimate),
        over=image_estimate + text_estimate > budget)


def manifest_text(manifest: dict, contents: dict[str, str], image_files: dict | None = None) -> str:
    """Serialize exactly the text a judge reads, including the estimate's own printed size."""
    manifest['files'] = {**{name: sha256_text(value) for name, value in contents.items()}, **(image_files or {})}

    def render() -> str:
        head = json.dumps({key: value for key, value in manifest.items() if key != 'frames'}, indent=1,
            ensure_ascii=False, allow_nan=False)
        rows = ',\n'.join('  ' + json.dumps(row, ensure_ascii=False, allow_nan=False) for row in manifest['frames'])
        # Keep the boolean's printed width constant: crossing the budget must not shorten the text
        # and flip its own over flag back at a rounding boundary. Both forms are ordinary JSON.
        head = head.replace('"over": true\n', '"over": true \n')
        return head[:-2] + ',\n "frames": [\n' + rows + '\n ]\n}\n'

    if 'budget' in manifest:
        estimate = manifest['budget']
        # Increasing from zero reaches a fixed point even at a printed digit boundary.
        estimate['estimated']['text'] = 0
        estimate['estimated']['total'] = estimate['estimated']['images']
        estimate['over'] = False
        while True:
            before = render()
            estimate['estimated']['text'] = sum(text_tokens(value) for value in contents.values()) + text_tokens(before)
            estimate['estimated']['total'] = estimate['estimated']['images'] + estimate['estimated']['text']
            estimate['over'] = estimate['estimated']['total'] > estimate['tokens']
            if render() == before:
                break
    return render()


def seal_packet(directory: Path, manifest: dict, instructions: str) -> tuple[str, int]:
    """Seal every file and count the actual serialized text plus images before writing the manifest."""
    (directory / 'instructions.md').write_text(instructions, encoding='utf-8')
    contents = {str(path.relative_to(directory)): path.read_text(encoding='utf-8') for path in sorted(directory.rglob('*'))
        if path.is_file() and path.suffix != '.png' and path.name != 'manifest.json'}
    image_files = {str(path.relative_to(directory)): file_sha256(path) for path in sorted(directory.rglob('*.png'))
        if not path.is_relative_to(directory / 'frames')}
    data = manifest_text(manifest, contents, image_files).encode()
    with (directory / 'manifest.json').open('xb') as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest(), sum(path.stat().st_size for path in directory.rglob('*') if path.is_file())


def verify_packet(directory: Path, sha256: str) -> dict:
    """The manifest of a packet that is still, file for file, the packet that was made."""
    path = directory / 'manifest.json'
    if not path.is_file() or file_sha256(path) != sha256:
        raise MeasureError(f'{directory}: not the packet that was made')
    manifest = read_json(path)
    expected = {**manifest['files'], **{row['file']: row['sha256'] for row in manifest['frames']}}
    actual = {str(path.relative_to(directory)) for path in directory.rglob('*') if path.is_file()}
    if actual != {*expected, 'manifest.json'}:
        raise MeasureError(f'{directory}: files changed since the packet was made')
    for name, recorded in expected.items():
        if not (directory / name).is_file() or file_sha256(directory / name) != recorded:
            raise MeasureError(f'{directory / name}: changed since the packet was made')
    return manifest


def stretch_sha256(directory: Path) -> str:
    """What a packet puts before a judge apart from its instructions: its manifest without the instructions'
    hash and without the token estimate, which counts the instructions' length. Two packets with the same value
    hold the same window, frames, inputs, facts and delivered text."""
    manifest = read_json(directory / 'manifest.json')
    kept = {key: value for key, value in manifest.items() if key != 'budget'}
    kept['files'] = {name: value for name, value in manifest['files'].items() if name != 'instructions.md'}
    return sha256_text(dumps(kept))


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

ANNOTATE_INSTRUCTIONS = '''# Listing the facts these frames show

You are one of two independent annotators. Use only the files in this directory: no other file, no notes from
another session and nothing you may know about this session from elsewhere.

## What you have

- `manifest.json` lists this packet's frames in the order they were recorded. Each entry has the frame's ID
  (`frame`), its image (`file`) and `inputs_before`: the inputs sent between this packet's previous frame and
  this one, oldest first. Each entry is one batch of inputs: keys by name, typed text in quotes and `×N` for a
  repeat.
- `frames/<frame ID>.png` is the screen as it was captured.

The frames are a regular sample of the changed screens of one recorded stretch of play, so steps between them
are missing.

## What to do

Look at every frame. List every fact the frames show that a later player of the same session could use:
anything that would let that player skip finding it out again, avoid a mistake or choose better. A fact can be
of any kind: where something is, what something does, a danger, a rule of how things work, a way of doing
something that worked or failed, a state that will still matter later, or something the player set out to do
and has not finished. One entry per fact:

- `fact`: one or two sentences that state it so that a reader who has not seen the frames could act on it. Use
  the screen's own words where it has them, and say what tells this thing apart from similar ones.
- `frames`: the IDs of the frames that show it. At least one, and only IDs from this packet.

When several frames show the same fact, write one entry and list all of those frames. List only what a frame
shows; do not add what you would expect to be true. When you are unsure whether something counts, list it.

## Your answer

One JSON document of this shape, and nothing else:

```json
{"packet": "PACKET", "entries": [{"fact": "...", "frames": ["FRAME ID", "FRAME ID"]}]}
```

`packet` is this packet's name from `manifest.json`. An empty `entries` list is a valid answer.
'''


def annotate_packets(run: Path, runs: Sequence[Path], every: int = 3, budget: int = PACKET_TOKENS,
                     min_changed: float = 0.0) -> dict:
    if every < 1:
        raise MeasureError('--every must be at least 1')
    def candidate(part: Sequence[Frame]) -> dict:
        manifest = dict(schema='annotate-packet/2', packet='packet-00', budget=budget_entry(budget, 0, part),
            frames=[dict(frame_row(frame, frame.source, True), sha256='0' * 64) for frame in part])
        manifest_text(manifest, {'instructions.md': ANNOTATE_INSTRUCTIONS})
        return manifest

    fixed = candidate([])['budget']['estimated']['total']
    if budget <= fixed:
        raise MeasureError(f'--budget {budget} leaves no room for frames beside {fixed} tokens of text')
    frames, _ = recorded_frames(runs, min_changed)
    packets, totals = [], Counter()
    with Building(run / 'annotate') as out:
        for admission, found in frames.items():
            kept = every_nth_changed(found, every)
            totals.update(recorded=len(found), changed=sum(frame.changed for frame in found), kept=len(kept))
            for chunk in cut(kept, lambda frame: 0, budget, packet_cost=lambda part, first, last: candidate(part)['budget']['estimated']['total']):
                name = f'packet-{len(packets) + 1:02d}'
                rows = [copy_frame(frame, out / name, frame.source, True) for frame in chunk]
                estimate = budget_entry(budget, 0, chunk)
                sha, size_bytes = seal_packet(out / name, dict(schema='annotate-packet/2', packet=name, budget=estimate,
                    frames=rows), ANNOTATE_INSTRUCTIONS)
                packets.append(dict(packet=name, admission=admission, frames=[frame.source for frame in chunk],
                    estimated_tokens=estimate['estimated']['total'], over_budget=estimate['over'], bytes=size_bytes, sha256=sha))
        index = dict(schema='annotate-packets/2', admissions=list(frames), every=every, min_changed=min_changed,
            budget_tokens=budget, frames=dict(totals), packets=packets)
        write_json(out / 'packets.json', index, once=True)
    return index


# --- the annotated facts ------------------------------------------------------------------------------------------------

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
                raise MeasureError(f'{where}: needs fact and a non-empty frames list')
            outside = [frame for frame in entry['frames'] if not isinstance(frame, str) or frame not in inside]
            if outside:
                raise MeasureError(f'{where}: cites frames outside its packet: {outside}')
            entries[f"{packet['packet']}#{number}"] = dict(fact=text(entry.get('fact'), f'{where} fact'),
                frames=list(dict.fromkeys(entry['frames'])))
    return entries


def build_items(run: Path, annotators: Sequence[str], matches: Path) -> dict:
    """The annotated facts: one is a group of entries joined by the lead's matches, and every match pairs an
    entry of the first annotator with one of the second, so an entry only one of them listed is in no fact."""
    target = run / 'annotated-facts.json'
    if target.exists() or (run / 'annotated-facts.json.sha256').exists():
        raise MeasureError(f'{target}: the annotated facts are frozen and are never overwritten')
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
        items.append(dict(text=listed[first][by[first][0]]['fact'], first_frame=frames[0], first_frame_file=file_of[frames[0]],
            frames=frames, listed={name: [dict(entry=identity, fact=listed[name][identity]['fact'])
                for identity in by[name]] for name in annotators}))
    items.sort(key=lambda item: position[item['first_frame']])
    items = [dict(id=f'seen-{number:02d}', **item) for number, item in enumerate(items, 1)]
    matched = {name: {entry['entry'] for item in items for entry in item['listed'][name]} for name in annotators}
    value = dict(schema='annotated-facts/1', annotators=list(annotators),
        counts={name: dict(entries=len(listed[name]), in_a_fact=len(matched[name]),
            dropped=len(listed[name]) - len(matched[name])) for name in annotators},
        sources=dict(annotate_packets=file_sha256(run / 'annotate' / 'packets.json'), matches=file_sha256(matches),
            annotations={name: {packet['packet']: file_sha256(run / 'annotations' / name / f"{packet['packet']}.json")
                for packet in index['packets']} for name in annotators}),
        facts=items)
    sha = write_json(target, value, once=True)
    (run / 'annotated-facts.json.sha256').write_text(sha + '\n')
    return dict(value, sha256=sha)


# --- the facts to judge -------------------------------------------------------------------------------------------------

def build_facts(run: Path, runs: Sequence[Path]) -> dict:
    """Build judged-facts from delivered data and the order of actual player exposures."""
    from harness.evaluation.core.host import host_facts, returned_records
    from harness.evaluation.core.sources import read_host, read_manifest
    from tools.knowledge_export import units, delivered_fact_ids
    admissions, recall_events = {}, []
    for directory in runs:
        manifest = read_manifest(directory)
        if manifest.get('schema') != 'campaign-run/7':
            raise MeasureError(f'{directory}: delivery requires campaign-run/7')
        for name, digest in {**manifest['files'], **{'private/'+k:v for k,v in manifest['private_files'].items()}}.items():
            if name in ('delivered-knowledge.json','private/knowledge-full.json','private/units.json') and file_sha256(directory/name) != digest:
                raise MeasureError(f'{directory/name}: frozen knowledge hash differs')
        full, drawn = read_json(directory/'private/knowledge-full.json'), read_json(directory/'private/units.json')
        delivered = read_json(directory/'delivered-knowledge.json')
        if full.get('schema') != 'delivered-knowledge/1' or delivered.get('schema') != full['schema'] \
                or drawn.get('schema') != 'knowledge-units/1' or drawn['version'] != full['version']:
            raise MeasureError(f'{directory}: unsupported frozen knowledge')
        expected = units(full)
        if ([{k:v for k,v in u.items() if k != 'withheld'} for u in drawn['units']] != expected['units']
                or drawn['shared'] != expected['shared']):
            raise MeasureError(f'{directory}: unit record differs from the exported unit rule')
        available = delivered_fact_ids(drawn)
        if available != {f['id'] for f in delivered['facts']}:
            raise MeasureError(f'{directory}: delivered facts differ from the private draw')
        articles = {a['id']:a for a in full['articles']}
        host, names = {}, {}
        for actor_dir in sorted((directory/'actors').iterdir()):
            if not (actor_dir/'host.jsonl').is_file():continue
            actor, events = read_host(actor_dir/'host.jsonl', actor_dir.name)
            host[actor], names[actor] = events, actor_dir.name
        facts = host_facts(tuple(host), host)
        entries = {}
        for actor, events in host.items():
            entry = {route:[] for route in ROUTES}
            entry.update(briefing='', reminders=[])
            exposed, last = {}, 0
            recalls = {}
            calls = {(c.request_id,c.tool_call_id):c for c in facts.calls if c.actor == actor}
            for event in events:
                fields = event.fields
                if event.type == 'knowledge-delivery':
                    kind = fields['kind']
                    source = recalls.get(fields.get('recall_request_id'))
                    if source is not None:source.update(delivered=True,from_decision=last)
                    if kind == 'briefing':entry['briefing'] = fields['text']
                    else:entry['reminders'].append(dict(decision=last,text=fields['text']))
                    for identity in fields['fact_ids']:
                        if identity in available:
                            exposed.setdefault(identity, ('lead', None if kind == 'briefing' or not last else last))
                elif event.type == 'tool-result':
                    call = calls.get((fields.get('request_id'),fields.get('tool_call_id')))
                    if call is not None:
                        # The result completes this player decision before the next request can use it.
                        last = max(last,call.decision or 0)
                        if call.tool in ('player_knowledge_read','player_knowledge_query') and not call.error:
                            for record in returned_records(call):
                                identities = {f for claim in record['body'] for f in claim['facts']} if 'body' in record else {record['id']}
                                for identity in identities & available:
                                    exposed.setdefault(identity,('read',last or None))
                elif event.type == 'knowledge-recall':
                    selected={f for aid in fields.get('article_ids',[]) for claim in articles[aid]['body'] for f in claim['facts']} | set(fields.get('fact_ids',[]))
                    record=dict(start=directory.name,actor=names[actor],decision=last,delivered=False,**{k:v for k,v in fields.items() if k != 'fact_ids'},fact_ids=sorted(selected & available))
                    recall_events.append(record)
                    if fields.get('request_id'):recalls[fields['request_id']]=record
            for fact in full['facts']:
                route, decision = exposed.get(fact['id'], ('index',None)) if fact['id'] in available else ('withheld',None)
                entry[route].append(dict(id=fact['id'],text=fact['text'],**({'from_decision':decision} if decision else {})))
            entries[names[actor]] = entry
        admissions[directory.name] = entries
    value = dict(schema=FACTS_SCHEMA,admissions=admissions)
    write_json(run/'judged-facts.json',value,once=True)
    write_json(run/'private'/'recall.json',dict(schema='recall-measure-inputs/1',events=recall_events),once=True)
    return value


def recall_measure(run: Path, rows: Sequence[dict]) -> dict:
    """Precision is the applied share of judged windows after actually delivered recall selections; silence is explicit empty reminder selections."""
    path = run/'private'/'recall.json'
    if not path.is_file():return dict(recorded=False)
    events = read_json(path)['events']
    completed = [e for e in events if e['kind'] == 'reminder' and e['status'] in ('silence','selected')]
    leads = [row for event in events if event['status'] == 'selected' and event.get('delivered')
             for row in rows if row['start'] == event['start'] and row['actor'] == event['actor']
             and row['fact'] in event['fact_ids'] and row['last'] > event['from_decision'] and row['label'] != 'cannot_tell']
    applied = sum(r['label'] in judge.APPLIED for r in leads)
    silence = sum(e['status'] == 'silence' for e in completed)
    return dict(recorded=True,precision=dict(numerator=applied,denominator=len(leads),value=applied/len(leads) if leads else None),
        silence=dict(numerator=silence,denominator=len(completed),value=silence/len(completed) if completed else None),
        failed=sum(e['status']=='failure' for e in events),not_made=sum(e['status']=='not-made' for e in events))


def read_facts(path: Path, spans: dict[str, dict]) -> dict[tuple[str, str], dict]:
    """The `judged-facts/1` input as {(admission, actor): {facts, briefing, reminders}}, in the order of the
    selected admissions. Each fact is {id, text, route, from_decision}; an ID names one fact once per actor."""
    value = read_json(path)
    if not isinstance(value, dict) or value.get('schema') != FACTS_SCHEMA or not isinstance(value.get('admissions'), dict):
        raise MeasureError(f'{path}: expected {{"schema": "{FACTS_SCHEMA}", "admissions": {{...}}}}; no other version is read')
    unknown = [name for name in value['admissions'] if name not in spans]
    if unknown:
        raise MeasureError(f'{path}: names admissions that --runs does not select: {", ".join(unknown)}')
    judged = {}
    for admission in spans:
        actors = value['admissions'].get(admission, {})
        if not isinstance(actors, dict) or set(actors) - set(spans[admission]):
            raise MeasureError(f'{path}: {admission} must map its actors ({", ".join(spans[admission])}) to their facts')
        for actor in spans[admission]:
            entry, where = actors.get(actor), f'{path}: {admission}/{actor}'
            if entry is None:
                continue
            if not isinstance(entry, dict) or set(entry) - {*ROUTES, 'briefing', 'reminders'}:
                raise MeasureError(f'{where}: expected the keys {", ".join(ROUTES)}, briefing and reminders only')
            facts, seen = [], set()
            for route in ROUTES:
                listed = entry.get(route, [])
                if not isinstance(listed, list):
                    raise MeasureError(f'{where}: {route} must be a list of facts')
                for fact in listed:
                    if not isinstance(fact, dict) or set(fact) - {'id', 'text', 'from_decision'}:
                        raise MeasureError(f'{where}: a fact is {{"id", "text"}} with an optional "from_decision"')
                    # Without timing the fact was already available before the actor's first request.
                    identity, start = text(fact.get('id'), f'{where} fact id'), fact.get('from_decision', 0)
                    if identity in seen:
                        raise MeasureError(f'{where}: fact {identity} is listed more than once; a fact has one route for an actor')
                    if type(start) is not int or start < (1 if 'from_decision' in fact else 0):
                        raise MeasureError(f'{where}: fact {identity}: from_decision is a decision number from 1')
                    seen.add(identity)
                    facts.append(dict(id=identity, text=text(fact.get('text'), f'{where} fact {identity} text'), route=route,
                        from_decision=start))
            briefing, reminders = entry.get('briefing'), entry.get('reminders', [])
            if briefing is not None and not isinstance(briefing, str) or not isinstance(reminders, list) or any(
                    not isinstance(row, dict) or set(row) != {'decision', 'text'} or type(row['decision']) is not int
                    or not isinstance(row['text'], str) for row in reminders):
                raise MeasureError(f'{where}: briefing is text and reminders are [{{"decision": N, "text": "..."}}]')
            judged[(admission, actor)] = dict(facts=sorted(facts, key=lambda fact: fact['id']), briefing=briefing,
                reminders=sorted(reminders, key=lambda row: row['decision']))
    if not any(entry['facts'] for entry in judged.values()):
        raise MeasureError(f'{path}: names no fact for any selected actor')
    return judged


def fact_groups(facts: Sequence[dict], limit: int) -> list[list[dict]]:
    """The facts in consecutive groups of at most `limit` estimated tokens; a longer single fact is a group."""
    groups: list[list[dict]] = []
    spent = 0
    for fact in facts:
        cost = text_tokens(json.dumps(fact, ensure_ascii=False))
        if not groups or spent + cost > limit:
            groups.append([])
            spent = 0
        groups[-1].append(fact)
        spent += cost
    return groups


# --- packets for the judges -----------------------------------------------------------------------------------------------

_JUDGE_TEMPLATE = '''# One closed question for each fact

Use only the files in this directory: no other file and nothing you may know about this stretch from elsewhere.

## What you have

- `manifest.json` lists the frames of one window of recorded play, in order. Each entry has the frame's ID
  (`frame`), its image (`file`), `decision` (which of the window's decisions returned it, counted from 1) and
  `inputs_before`: the inputs the player sent between this packet's previous frame and this one, oldest first.
  Each entry is one batch of inputs: keys by name, typed text in quotes and `×N` for a repeat. `decisions` is how
  many decisions the window has.
STATED- `frames/<frame ID>.png` is the screen as it was captured. The frames are a regular sample of the changed
  screens, so steps between them are missing.
- `facts.json` lists the facts to judge, each with an `id` and its `text`. FACTS
DELIVERED
## The question

For each fact, what did the player do about it in this window? Judge the window as a whole, not one step.
Answer with exactly one label:

- `in_line`: acted in line with it. The player did what the fact supports.
- `against`: acted against it. The player did what the fact advises against, or went for something the fact
  says is empty or gone.
- `found_again`: found it again. The player discovered by looking what the fact already said.
- `did_not_apply`: did not apply. Nothing in the window shows that the fact could have mattered to what the
  player was doing.
- `cannot_tell`: the frames do not show enough to choose among the four above.

Then say whether the frames show the fact still holding (`holds`):

- `held`: the frames show that what the fact says was true in this window.
- `stale_or_false`: the frames show that what the fact says was no longer true, or never was.
- `cannot_tell`: the frames show neither.

Cite the frames that show it, by ID, from this packet only. `in_line`, `against` and `found_again` need at least
one frame; the other two labels may cite none.

## Your answer

One JSON document of this shape, and nothing else. Answer every fact in `facts.json` exactly once:

```json
{"packet": "PACKET", "answers": [{"fact": "FACT ID", "label": "in_line", "holds": "held", "frames": ["FRAME ID"], "note": "one sentence"}]}
```

`packet` is this packet's name from `manifest.json`. `note` is optional.
'''

_USE_PARTS = dict(
    STATED='''- Some entries also have `stated_before`: what the player itself said with its calls since the previous frame,
  as `intent` and, when it gave them, `cites`: the IDs of the stored facts it said it relied on. What the player
  states is evidence of what it meant, not proof of what it did.
''',
    FACTS='''Each also has a `route`: how it reached
  the player. `lead`: its text was put in front of the player. `read`: the player asked for it and read it.
  `index`: only a one-line title of it was listed. Any fact may be out of date or wrong.
  `available_from` names the first kept frame whose carried inputs were all chosen strictly after the
  decision that returned this fact. The inputs of that decision were chosen before its result was seen.
  Count `in_line`, `against` or
  `found_again` only for action from that frame onward, and cite at least one such frame. Earlier action does
  not count, even when it matches the fact.''',
    DELIVERED='''- `delivered.json` holds what was put in front of the player: the `briefing` it began with and the `reminders`
  added during play, each with the decision of this window at which it arrived (null when it arrived earlier).
''')
_BLIND_PARTS = dict(STATED='', DELIVERED='',
    FACTS='''They were known before this
  window. The player may or may not have had each one in front of it, and you are not told which. Any fact may
  be out of date or wrong.''')


def _instructions(parts: dict) -> str:
    value = _JUDGE_TEMPLATE
    for key in ('STATED', 'FACTS'):
        value = value.replace(key, parts[key])
    value = value.replace('DELIVERED\n', parts['DELIVERED'] + '\n')
    if not parts['STATED']:
        value = value.replace('(`frame`), its image (`file`), `decision` (which of the window\'s decisions returned it, counted from 1) and',
            '(`frame`), numbered by position in this packet, its image (`file`) and')
        value = value.replace(' `decisions` is how\n  many decisions the window has.', '')
    return value


#: The judge's instructions by packet kind. Neither names any kind of thing in a game. The blind one names
#: neither delivery nor decision counts; it shows only frames by position, inputs and facts under opaque IDs.
JUDGE_INSTRUCTIONS = dict(use=_instructions(_USE_PARTS), blind=_instructions(_BLIND_PARTS))


def fact_packets(run: Path, runs: Sequence[Path], facts: Path, kind: str, budget: int = PACKET_TOKENS, every: int = 3,
                 min_changed: float = 0.0, seed: int | None = None) -> dict:
    """One packet per window and group of facts, for each actor the facts file names.

    `use` packets carry each fact's route, the briefing, the reminders and what the player stated with its calls,
    and leave out withheld facts, which were never in front of the player. `blind` packets, for the benefit
    measure, carry every fact of the actor under opaque per-packet IDs, in shuffled order and in every window, and nothing of
    what was delivered or stated: a judge of a blind packet cannot tell a delivered fact from a withheld one."""
    if kind not in JUDGE_INSTRUCTIONS or every < 1:
        raise MeasureError('The packet kind is use or blind, and --every must be at least 1')
    blind = kind == 'blind'
    mapping_path = run / 'private' / 'judge-mapping.json'
    if mapping_path.exists():
        raise MeasureError(f'{mapping_path}: already written; judge packets are made once')
    seed = secrets.randbits(32) if seed is None else seed
    rng = random.Random(seed)
    frames, spans = recorded_frames(runs, min_changed)
    judged = read_facts(facts, spans)
    instructions = JUDGE_INSTRUCTIONS[kind]
    planned: dict[str, dict] = {}
    no_frames, not_shown = [], []
    for (admission, actor), entry in judged.items():
        shown = [fact for fact in entry['facts'] if blind or fact['route'] != 'withheld']
        kept = every_nth_changed([frame for frame in frames[admission] if frame.actor == actor], every)
        if entry['facts'] and not kept:
            no_frames.append(f'{admission}/{actor}')
        missing = [fact for fact in shown if not kept or not blind and not any(
            available_after(frame, fact['from_decision']) for frame in kept)]
        not_shown.extend(dict(actor=f'{admission}/{actor}', fact=fact['id']) for fact in missing)
        shown = [fact for fact in shown if fact not in missing]
        if not shown:
            continue
        low, high = spans[admission][actor]
        if blind:
            rng.shuffle(shown)
        # Use equal-length opaque names even while planning, so the final serialization has the same cost.
        identities = {fact['id']: f'q{number:010x}' for number, fact in enumerate(shown)} if blind else {
            fact['id']: fact['id'] for fact in shown}

        def candidate(part: Sequence[Frame], group: Sequence[dict], first: int, last: int, name: str) -> tuple:
            rows = [dict(frame_row(frame, f'f{number:03d}', blind), sha256='0' * 64,
                **({} if blind else dict(decision=frame.decision - first + 1))) for number, frame in enumerate(part, 1)]
            listed, available = [], {}
            for fact in group:
                at = next((number for number, frame in enumerate(part, 1) if available_after(frame, fact['from_decision'])), None)
                if not blind and at is None:
                    continue
                item = dict(id=identities[fact['id']], text=fact['text'])
                if not blind:
                    available[fact['id']] = f'f{at:03d}'
                    item.update(route=fact['route'], available_from=available[fact['id']])
                listed.append(item)
            contents = {'facts.json': json_text(dict(schema='packet-facts/1', facts=listed)), 'instructions.md': instructions}
            delivered = None if blind else dict(briefing=entry['briefing'], reminders=[dict(text=row['text'],
                decision=row['decision'] - first + 1 if row['decision'] >= first else None)
                for row in entry['reminders'] if row['decision'] <= last])
            if delivered is not None:
                contents['delivered.json'] = json_text(delivered)
            estimate = budget_entry(budget, 0, part)
            manifest = dict(schema='judge-packet/2', packet=name, **({} if blind else dict(decisions=last - first + 1)),
                labels=list(USE_LABELS), holds=list(HOLDS), budget=estimate, frames=rows)
            manifest_text(manifest, contents)
            return manifest, listed, available, delivered

        # The fixed payload uses all reminders, including those later omitted from an earlier window.
        fixed = candidate([], [], low, high, 's0000000000')[0]['budget']['estimated']['total']
        remaining = budget - fixed
        if remaining < budget / 4:
            raise MeasureError(f'--budget {budget} leaves less than a quarter for facts after {fixed} fixed tokens; '
                'leaves no room for frames; increase the budget or reduce briefing/reminders')
        groups = fact_groups([dict(id=identities[fact['id']], text=fact['text'],
            **({} if blind else dict(route=fact['route'], available_from='f000'))) for fact in shown], remaining // 2)
        by_id = {identities[fact['id']]: fact for fact in shown}
        groups = [[by_id[fact['id']] for fact in group] for group in groups]

        def cost(part: Sequence[Frame], first: int, last: int) -> int:
            return max(candidate(part, group, first, last, 's0000000000')[0]['budget']['estimated']['total'] for group in groups)

        parts = cut(kept, lambda frame: 0, budget, packet_cost=cost, first_decision=low, last_decision=high)
        for number, part in enumerate(parts):
            first = low if number == 0 else parts[number - 1][-1].decision + 1
            last = high if number == len(parts) - 1 else part[-1].decision
            for group in groups:
                name = f's{rng.getrandbits(40):010x}'
                while name in planned:
                    name = f's{rng.getrandbits(40):010x}'
                if blind:
                    # Names are per packet, shuffled independently of routes and canonical ordering.
                    opaque = rng.sample(range(16 ** 10), len(group))
                    identities.update({fact['id']: f'q{number:010x}' for fact, number in zip(group, opaque)})
                manifest, listed, available, delivered = candidate(part, group, first, last, name)
                if not listed:
                    continue
                canonical = [fact for fact in group if blind or fact['id'] in available]
                planned[name] = dict(admission=admission, actor=actor, first=first, last=last, frames=part, facts=listed,
                    manifest=manifest, available_from=available, from_decision={fact['id']: fact['from_decision'] for fact in canonical},
                    fact_ids={identities[fact['id']]: fact['id'] for fact in canonical},
                    routes={fact['id']: fact['route'] for fact in canonical}, delivered=delivered)
    if not planned and not no_frames and not not_shown:
        raise MeasureError(f'{facts}: no actor it names has both a fact to show and a frame')
    packets = {}
    with Building(run / 'judge-packets') as out:
        for name in sorted(planned):
            plan, directory = planned[name], out / name
            directory.mkdir()
            rows, sources = [], {}
            for number, frame in enumerate(plan['frames'], 1):
                row = copy_frame(frame, directory, f'f{number:03d}', blind)
                rows.append(dict(row, **({} if blind else dict(decision=frame.decision - plan['first'] + 1))))
                sources[row['frame']] = frame.source
            write_json(directory / 'facts.json', dict(schema='packet-facts/1', facts=plan['facts']), once=True)
            if plan['delivered'] is not None:
                write_json(directory / 'delivered.json', plan['delivered'], once=True)
            manifest = dict(plan['manifest'], frames=rows)
            sha, size = seal_packet(directory, manifest, instructions)
            estimate = manifest['budget']
            count = plan['last'] - plan['first'] + 1
            packets[name] = dict(packet=name, window=f"{plan['admission']}/{plan['actor']}:{plan['first']}-{plan['last']}",
                start=plan['admission'], actor=plan['actor'], first=plan['first'], last=plan['last'], decisions=count,
                sha256=sha, stretch_sha256=stretch_sha256(directory), bytes=size,
                estimated_tokens=estimate['estimated']['total'], over_budget=estimate['over'], frames=sources,
                available_from=plan['available_from'], from_decision=plan['from_decision'], fact_ids=plan['fact_ids'],
                facts=plan['routes'])
        mapping = dict(schema=MAPPING_SCHEMA, kind=kind, seed=seed, budget_tokens=budget, every=every, min_changed=min_changed,
            facts_sha256=file_sha256(facts), instructions_sha256=sha256_text(instructions), no_frames=no_frames, not_shown=not_shown,
            not_judged=[f'{admission}/{actor}' for admission in spans for actor in spans[admission]
                if (admission, actor) not in judged], packets=[packets[name] for name in planned])
        write_json(mapping_path, mapping, once=True)
    return mapping


def load_mapping(run: Path) -> dict:
    value = read_json(run / 'private' / 'judge-mapping.json')
    if not isinstance(value, dict) or value.get('schema') != MAPPING_SCHEMA:
        raise MeasureError(f"{run / 'private' / 'judge-mapping.json'}: not a {MAPPING_SCHEMA} file; no other version is read")
    return value


# --- judge events -----------------------------------------------------------------------------------------------------

def checked_answers(path: Path, packets: dict[str, dict], done: set, directory: Path, key: str,
                    wanted: Callable[[dict], Sequence[str]], labels: Sequence[str], citing: Sequence[str],
                    also: Callable[[dict], str | None] | None = None) -> tuple:
    """One answer file against its packet: every `key` the packet wants answered once, a closed label, cited
    frames from the packet, and a frame for every label in `citing`. It returns the packet and the answers."""
    value = read_json(path)
    named = value.get('packet') if isinstance(value, dict) else None
    packet = packets.get(named) if isinstance(named, str) else None
    if packet is None or not isinstance(value.get('answers'), list):
        raise MeasureError(f'{path}: expected {{"packet": "<a packet of this run>", "answers": [...]}}')
    if packet['packet'] in done:
        raise MeasureError(f"{path}: packet {packet['packet']} is answered by more than one file")
    done.add(packet['packet'])
    verify_packet(directory / packet['packet'], packet['sha256'])
    rows = value['answers']
    if any(not isinstance(row, dict) or not isinstance(row.get(key), str) for row in rows):
        raise MeasureError(f'{path}: every answer is an object that names its {key}')
    wanted = wanted(packet)
    counts = Counter(row[key] for row in rows)
    problems = [f'no answer for {identity}' for identity in wanted if not counts[identity]]
    problems += [f'{identity} answered {count} times' for identity, count in counts.items() if count > 1]
    problems += [f'{identity!r} is not a {key} of the packet' for identity in counts if identity not in wanted]
    for row in rows:
        frames = row.get('frames', [])
        if row.get('label') not in labels:
            problems.append(f"{row[key]}: label {row.get('label')!r} is not one of {', '.join(labels)}")
        elif not isinstance(frames, list) or any(not isinstance(frame, str) or frame not in packet['frames'] for frame in frames):
            problems.append(f"{row[key]}: cites a frame outside the packet: {frames!r}")
        elif row['label'] in citing and not frames:
            problems.append(f"{row[key]}: a {row['label']} label must cite a frame")
        elif also and also(row):
            problems.append(f'{row[key]}: {also(row)}')
    if problems:
        raise MeasureError(f'{path}: ' + '; '.join(problems))
    return packet, rows


def events_target(directory: Path, name: str) -> Path:
    if NAME.fullmatch(name) is None:
        raise MeasureError(f'{name!r}: a judge name is lowercase letters, digits and hyphens')
    target = directory / f'{name}.jsonl'
    if target.exists():
        raise MeasureError(f'{target}: already written; a judge\'s events are written once')
    return target


def judge_events(run: Path, name: str, model: str, answers: Sequence[Path]) -> list[judge.FactUseVerdict]:
    """Validate one judge's answer files against their packets and write its events once. The route of each
    fact comes from the mapping the packets were made with, never from the answer."""
    target = events_target(run / 'events', name)
    packets = {packet['packet']: packet for packet in load_mapping(run)['packets']}
    events, done = [], set()
    for path in answers:
        packet, rows = checked_answers(path, packets, done, run / 'judge-packets', 'fact', lambda packet: list(packet['fact_ids']),
            USE_LABELS, judge.APPLIED, lambda row: None if row.get('holds') in HOLDS
                else f"holds {row.get('holds')!r} is not one of {', '.join(HOLDS)}")
        positions = {frame: number for number, frame in enumerate(packet['frames'])}
        for row in rows:
            canonical = packet['fact_ids'][row['fact']]
            available = packet['available_from'].get(canonical)
            if row['label'] in judge.APPLIED and available is not None and not any(
                    positions[frame] >= positions[available] for frame in row['frames']):
                raise MeasureError(f"{path}: {row['fact']}: applied label cites only frames before available_from {available}")
            events.append(judge.FactUseVerdict(window=packet['window'], fact=canonical, route=packet['facts'][canonical],
                label=row['label'], holds=row['holds'],
                cited_frames=tuple(packet['frames'][frame] for frame in dict.fromkeys(row.get('frames', []))), judge=name,
                model=text(model, '--model'), packet=packet['packet'], packet_sha256=packet['sha256']))

    if not events:
        raise MeasureError('No answer file selected')
    target.parent.mkdir(parents=True, exist_ok=True)
    judge.write_events(target, events)
    return events


def read_judge(directory: Path, name: str, kind: str) -> dict[tuple[str, str], judge.JudgeEvent]:
    path = directory / f'{name}.jsonl'
    if not path.is_file():
        raise MeasureError(f'{path}: missing; run `events` for {name} first')
    return {event.pair: event for event in judge.read_events(path, kind)}


# --- statistics -------------------------------------------------------------------------------------------------------

def confusion(first: Sequence[int], second: Sequence[int], categories: int) -> np.ndarray:
    table = np.zeros((categories, categories))
    np.add.at(table, (np.asarray(first, dtype=int), np.asarray(second, dtype=int)), 1)
    return table


def kappa_of(table: np.ndarray) -> np.ndarray:
    """Cohen's kappa of the confusion tables on the last two axes; nan for an empty table and where chance
    agreement is certain."""
    total = table.sum(axis=(-2, -1))
    with np.errstate(divide='ignore', invalid='ignore'):
        observed = np.trace(table, axis1=-2, axis2=-1) / total
        chance = (table.sum(axis=-1) * table.sum(axis=-2)).sum(axis=-1) / total ** 2
        return np.where(chance < 1, (observed - chance) / (1 - chance), np.nan)


def cohen_kappa(first: Sequence[int], second: Sequence[int], categories: int) -> float | None:
    """Cohen's kappa of two raters' category codes; None when chance agreement is certain or nothing is rated."""
    value = float(kappa_of(confusion(first, second, categories)))
    return None if math.isnan(value) else value


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


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(denominator > 0, numerator / denominator, np.nan)


class StartBootstrap:
    """A cluster bootstrap over starts (admissions). Whole starts are drawn with replacement and a statistic is
    recomputed from the drawn starts' sums, so pairs a judge labelled together stay together. With one start
    there is nothing to resample and every interval is None."""

    def __init__(self, starts: Sequence[str], seed: int, draws: int) -> None:
        self.names = list(dict.fromkeys(starts))
        self.at = {name: number for number, name in enumerate(self.names)}
        self.index = np.random.default_rng(seed).integers(0, len(self.names), (draws, len(self.names))) \
            if len(self.names) > 1 else None

    def sums(self, rows: Sequence[dict], value: Callable[[dict], object], shape: tuple = ()) -> np.ndarray:
        """Per start, the sum of `value(row)` over its rows."""
        total = np.zeros((len(self.names), *shape))
        for row in rows:
            total[self.at[row['start']]] += value(row)
        return total

    def interval(self, function: Callable[..., np.ndarray], *per_start: np.ndarray) -> list[float] | None:
        if self.index is None:
            return None
        return percentile_interval(np.asarray(function(*(part[self.index].sum(axis=1) for part in per_start)), dtype=float))


def _number(value: float) -> float | None:
    return None if math.isnan(value) else float(value)


def judges_beside(boot: StartBootstrap, rows: Sequence[dict], judges: Sequence[str], field: str = 'labels') -> dict:
    """The first two judges on `rows`: their agreement and Cohen's kappa on `field` (the labels, or `holds_by`),
    and the dispute rate, the share of rows on which that field differs before adjudication."""
    categories = USE_LABELS if field == 'labels' else HOLDS
    first, second = judges

    def table(row: dict) -> np.ndarray:
        return confusion([categories.index(row[field][first])], [categories.index(row[field][second])], len(categories))

    tables = boot.sums(rows, table, (len(categories), len(categories)))
    disputes = boot.sums(rows, lambda row: float(row[field][first] != row[field][second]))
    count = boot.sums(rows, lambda row: 1.0)
    whole = tables.sum(axis=0)
    return dict(pairs=len(rows), on='label' if field == 'labels' else 'holds',
        agreement=_number(float(_ratio(np.trace(whole), whole.sum()))),
        kappa=dict(value=_number(float(kappa_of(whole))), interval=boot.interval(kappa_of, tables)),
        dispute_rate=dict(value=_number(float(_ratio(disputes.sum(), count.sum()))), interval=boot.interval(_ratio, disputes, count)))


def agreement(run: Path, judges: Sequence[str], third: str | None = None) -> dict:
    """The adjudicated labels: the label both of the first two judges gave, else the third judge's. `by` says
    which: `agreement`, `third` (the third sided with one of them) or `third_alone` (it gave a label neither
    did, so no two judges agree). `holds` is the value both gave, else the third's when it sides with one of
    them, else `cannot_tell`."""
    if judges[0] == judges[1] or third in judges:
        raise MeasureError('The judges must differ')
    mapping = load_mapping(run)
    first, second = (read_judge(run / 'events', name, judge.FACT_USE) for name in judges)
    tie = read_judge(run / 'events', third, judge.FACT_USE) if third else {}
    rows, missing = [], []
    for packet in mapping['packets']:
        for fact, route in packet['facts'].items():
            pair = (packet['window'], fact)
            missing += [f'{name}: {pair[0]} / {fact}' for name, events in zip(judges, (first, second)) if pair not in events]
            if missing:
                continue
            a, b, c = first[pair], second[pair], tie.get(pair)
            same = a.label == b.label
            label = a.label if same else c.label if c else None
            by = 'agreement' if same else None if c is None else 'third' if c.label in (a.label, b.label) else 'third_alone'
            holds = a.holds if a.holds == b.holds else c.holds if c and c.holds in (a.holds, b.holds) else 'cannot_tell'
            rows.append(dict(window=pair[0], fact=fact, route=route, start=packet['start'], actor=packet['actor'],
                packet=packet['packet'], label=label, by=by, holds=holds,
                from_decision=packet['from_decision'][fact], last=packet['last'],
                unresolved=c is None and (not same or a.holds != b.holds),
                labels={judges[0]: a.label, judges[1]: b.label, **({third: c.label} if c else {})},
                holds_by={judges[0]: a.holds, judges[1]: b.holds, **({third: c.holds} if c else {})}))
    if missing:
        raise MeasureError(f'{len(missing)} pairs lack a verdict, the first: {missing[0]}')
    disputed = [row for row in rows if row['labels'][judges[0]] != row['labels'][judges[1]]]
    holds_disputed = sum(row['holds_by'][judges[0]] != row['holds_by'][judges[1]] for row in rows)
    codes = [[USE_LABELS.index(row['labels'][name]) for row in rows] for name in judges]
    holds_codes = [[HOLDS.index(row['holds_by'][name]) for row in rows] for name in judges]
    value = dict(schema='judge-adjudicated/2', kind=mapping['kind'], judges=list(judges), third=third, pairs=len(rows),
        agreement=1 - len(disputed) / len(rows) if rows else None, kappa=cohen_kappa(*codes, len(USE_LABELS)),
        disputed=len(disputed), dispute_rate=len(disputed) / len(rows) if rows else None,
        holds_agreement=1 - holds_disputed / len(rows) if rows else None, holds_kappa=cohen_kappa(*holds_codes, len(HOLDS)),
        holds_disputed=holds_disputed, holds_dispute_rate=holds_disputed / len(rows) if rows else None,
        unresolved=sum(row['unresolved'] for row in rows), third_alone=sum(row['by'] == 'third_alone' for row in rows),
        third_judge_packets=sorted({row['packet'] for row in rows if row['unresolved']}), rows=rows)
    write_json(run / 'adjudicated.json', value)
    return value


def measure(run: Path, seed: int | None = None, draws: int = 10000) -> dict:
    """The standing use measures of one judged run, from its adjudicated labels. Every rate carries the first
    two judges' agreement and dispute rate over the pairs it is taken from, and an interval over starts. A run
    of blind packets gets the label counts and the judges' agreement only: the use measures read what was
    delivered, which a blind packet leaves out."""
    adjudicated = read_json(run / 'adjudicated.json')
    if adjudicated.get('schema') != 'judge-adjudicated/2':
        raise MeasureError(f"{run / 'adjudicated.json'}: not judge-adjudicated/2; run `agreement` again")
    if adjudicated['unresolved']:
        raise MeasureError(f"{adjudicated['unresolved']} pairs are not adjudicated; run `agreement` with --third")
    rows, judges = adjudicated['rows'], adjudicated['judges']
    seed = secrets.randbits(32) if seed is None else seed
    boot = StartBootstrap([row['start'] for row in rows], seed, draws)

    def rate(definition: str, units: Sequence[dict], base: Callable[[dict], bool], hit: Callable[[dict], bool],
             beside: Sequence[dict], field: str = 'labels') -> dict:
        numerator = boot.sums(units, lambda unit: float(base(unit) and hit(unit)))
        denominator = boot.sums(units, lambda unit: float(base(unit)))
        return dict(definition=definition, numerator=int(numerator.sum()), denominator=int(denominator.sum()),
            value=_number(float(_ratio(numerator.sum(), denominator.sum()))),
            interval=boot.interval(_ratio, numerator, denominator) if denominator.sum() else None,
            judges_route=judges_beside(boot, beside, judges, field),
            judges_rate_pairs=judges_beside(boot, [row for row in beside if any(row['labels'][name] in
                (('in_line',) if field == 'holds_by' else judge.APPLIED) for name in judges)], judges, field))

    def applied(row: dict) -> bool:
        return row['label'] in judge.APPLIED

    measures = None
    if adjudicated['kind'] == 'use':
        delivered = [row for row in rows if row['route'] == 'lead']
        known = [row for row in rows if row['route'] != 'withheld']
        read = [row for row in rows if row['route'] == 'read' and row['last'] >= row['from_decision']]
        reads: dict[tuple, dict] = {}
        for row in read:
            unit = reads.setdefault((row['start'], row['actor'], row['fact']), dict(start=row['start'], acted=False))
            unit['acted'] = unit['acted'] or row['label'] == 'in_line'
        measures = dict(
            use_rate_delivered=rate('of the windows in which a fact whose lead was delivered applied (in line, against or '
                'found again), the share in which the player acted in line with it', delivered, applied,
                lambda row: row['label'] == 'in_line', delivered),
            rediscovery=rate('of the windows in which a fact whose lead was delivered applied, the share in which the '
                'player found it again by looking', delivered, applied, lambda row: row['label'] == 'found_again', delivered),
            stale_or_false_acted=rate('of the windows in which the player acted in line with a fact it had (lead, read or '
                'index), the share in which the frames show the fact no longer held or never did', known,
                lambda row: row['label'] == 'in_line', lambda row: row['holds'] == 'stale_or_false', known, 'holds_by'),
            read_then_in_line=rate('of the facts the player read through a link or a search, the share it then acted in line '
                'with in some window; the denominator is how many facts it read', list(reads.values()), lambda unit: True,
                lambda unit: unit['acted'], read))
    mapping = load_mapping(run)
    report = dict(schema='memory-use/1', kind=adjudicated['kind'], judges=judges, third=adjudicated['third'],
        not_corrected=NOT_CORRECTED, bootstrap=dict(seed=seed, draws=draws, starts=len(boot.names), note=BOOTSTRAP_NOTE),
        pairs=len(rows), third_alone=adjudicated['third_alone'], no_frames=mapping['no_frames'], not_shown=mapping['not_shown'],
        labels_by_route={route: dict(pairs=sum(row['route'] == route for row in rows),
            **{label: sum(row['route'] == route and row['label'] == label for row in rows) for label in USE_LABELS})
            for route in ROUTES}, judges_overall=judges_beside(boot, rows, judges), measures=measures)
    report['recall'] = recall_measure(run, rows) if adjudicated['kind'] == 'use' else dict(recorded=False)
    write_json(run / 'measure.json', report)
    return report


# --- the anchor: the measure gate's owner-labelled pairs, re-judged ---------------------------------------------------------

#: The measure gate's judge prompt, frozen: the text of `instructions.md` in every sealed judge packet of
#: the measure gate, sealed as `memory-measure/` of the `memory-screen-gates-460-386` study
#: (`.runtime/evidence/memory-screen-gates-460-386/memory-measure`). It is worded for one kind of fact in one game, as the gate was;
#: it is kept only because the owner's 30 labels answer this question. It is never edited: `anchor packets` refuses
#: a gate whose packets do not hold exactly this text, and a test pins its hash.
ANCHOR_PROMPT_SHA256 = '14c7d5932c044f2ac3e6b6e0a60bbb45ece3598d87a3e60aea4f94ad68c6af24'
ANCHOR_INSTRUCTIONS = '''# One closed question for each known item

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
- `items/<item id>.png` is the earlier frame that first showed each item.

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
SHIFT_NOTE = ('The shift is the new judge\'s matches with the owner minus the gate\'s adjudicated label\'s, in pairs. '
    'The gate\'s adjudicated label is two judges and a third on disputes; one new judge is compared with it and with '
    'each gate judge. Checked labels were given after the owner saw the gate judges\' evidence and are not independent '
    'of them. Thirty pairs give a wide interval: read the shift with the agreement over all re-judged pairs.')


def read_owner_labels(gate: Path) -> list[dict]:
    """The sealed measure gate's owner-labelled pairs: the random draw then the engaged supplement, each with the
    owner's blind label (the first click, before any judge's work was shown) and checked label (after it)."""
    saved = read_json(gate / 'labels.json')
    if not isinstance(saved, dict) or saved.get('schema') != OWNER_LABELS_SCHEMA:
        raise MeasureError(f"{gate / 'labels.json'}: not {OWNER_LABELS_SCHEMA}; labels of another format are not read")
    if saved['sample_sha256'] != file_sha256(gate / 'sample.json') or saved['engaged_sha256'] != file_sha256(gate / ENGAGED_FILE):
        raise MeasureError(f"{gate / 'labels.json'}: holds labels for another sample")
    pairs = []
    for group, name in (('random', 'sample.json'), ('engaged', ENGAGED_FILE)):
        for pair in read_json(gate / name)['pairs']:
            entry = saved['labels'].get(str(pair['index']))
            if entry is None or (entry['start'], entry['item']) != (pair['start'], pair['item']) \
                    or entry['blind'] not in ANCHOR_LABELS or entry['checked'] not in ANCHOR_LABELS:
                raise MeasureError(f"{gate / 'labels.json'}: pair {pair['index']} lacks the owner's blind and checked labels")
            pairs.append(dict(index=pair['index'], group=group, start=pair['start'], item=pair['item'], blind=entry['blind'],
                checked=entry['checked']))
    return pairs


GATE_EVIDENCE_MANIFEST = Path(__file__).resolve().parents[1] / 'data/evidence/memory-screen-gates-460-386.sha256'


def verify_gate_files(gate: Path, paths: Sequence[Path]) -> None:
    """Check gate inputs against the independent sealed evidence inventory, not self-reported hashes."""
    recorded = dict(line.split('  ', 1)[::-1] for line in GATE_EVIDENCE_MANIFEST.read_text().splitlines() if line)
    for path in paths:
        name = 'memory-measure/' + str(path.relative_to(gate))
        if name not in recorded or not path.is_file() or file_sha256(path) != recorded[name]:
            raise MeasureError(f'{path}: differs from the sealed evidence manifest')


def anchor_packets(run: Path, gate: Path, dry_run: bool = False) -> dict:
    """Copy the gate's judge packets that hold an owner-labelled pair, unchanged, for a new judge. Every packet is
    first checked against the hash the gate recorded for it, file by file, and its instructions against the frozen
    prompt. `gate` is only read. With `dry_run` the checks are made and nothing is written."""
    gate = Path(gate).resolve()
    if gate == run or run.is_relative_to(gate):
        raise MeasureError(f'{run}: the anchor is written to a run directory of its own, never into the gate')
    if sha256_text(ANCHOR_INSTRUCTIONS) != ANCHOR_PROMPT_SHA256:
        raise MeasureError('The frozen anchor prompt in this tool was edited: its hash is no longer the recorded one')
    verify_gate_files(gate, [gate / name for name in ('private/judge-mapping.json', 'labels.json', 'adjudicated.json',
        'sample.json', ENGAGED_FILE)])
    mapping = read_json(gate / 'private' / 'judge-mapping.json')
    adjudicated = read_json(gate / 'adjudicated.json')
    if mapping.get('schema') != 'judge-mapping/1' or adjudicated.get('schema') != 'judge-adjudicated/1' or adjudicated['unresolved']:
        raise MeasureError(f'{gate}: not a finished measure gate (judge-mapping/1 and judge-adjudicated/1, all pairs adjudicated)')
    pairs = read_owner_labels(gate)
    wanted = {pair['start'] for pair in pairs}
    packets = []
    for packet in mapping['packets']:
        if packet['start'] not in wanted:
            continue
        directory = gate / 'judge-packets' / packet['packet']
        manifest = verify_packet(directory, packet['sha256'])
        verify_gate_files(gate, [path for path in directory.rglob('*') if path.is_file()])
        found = file_sha256(directory / 'instructions.md')
        if found != ANCHOR_PROMPT_SHA256 or manifest['files'].get('instructions.md') != found:
            raise MeasureError(f"{directory / 'instructions.md'}: sha256 {found} is not the frozen prompt's {ANCHOR_PROMPT_SHA256}")
        packets.append(dict(packet=packet['packet'], start=packet['start'], sha256=packet['sha256'], frames=packet['frames'],
            items=[item['id'] for item in read_json(directory / 'items.json')['items']]))
    if wanted - {packet['start'] for packet in packets}:
        raise MeasureError(f'{gate}: no packet for {", ".join(sorted(wanted - {packet["start"] for packet in packets}))}')
    starts = {packet['start'] for packet in packets}
    value = dict(schema='anchor-set/1', gate=gate.name, prompt_sha256=ANCHOR_PROMPT_SHA256, gate_judges=adjudicated['judges'],
        sources={name: file_sha256(gate / name) for name in ('labels.json', 'sample.json', ENGAGED_FILE, 'adjudicated.json',
            'private/judge-mapping.json')},
        packets=packets, pairs=pairs,
        gate_labels=[dict(start=row['start'], item=row['item'], adjudicated=row['label'],
            labels={name: row['labels'][name] for name in adjudicated['judges']}) for row in adjudicated['pairs']
            if row['start'] in starts])
    if dry_run:
        return value
    if (run / 'private' / 'anchor.json').exists():
        raise MeasureError(f"{run / 'private' / 'anchor.json'}: already written; anchor packets are made once")
    with Building(run / 'anchor') as out:
        for packet in packets:
            shutil.copytree(gate / 'judge-packets' / packet['packet'], out / 'packets' / packet['packet'])
            verify_packet(out / 'packets' / packet['packet'], packet['sha256'])
        write_json(run / 'private' / 'anchor.json', value, once=True)
    return value


def load_anchor(run: Path) -> dict:
    value = read_json(run / 'private' / 'anchor.json')
    if not isinstance(value, dict) or value.get('schema') != 'anchor-set/1':
        raise MeasureError(f"{run / 'private' / 'anchor.json'}: not an anchor-set/1 file")
    return value


def anchor_events(run: Path, name: str, model: str, answers: Sequence[Path]) -> list[judge.AnchorVerdict]:
    """Validate a new judge's answers to the anchor packets and write its `anchor_verdict` events once."""
    target = events_target(run / 'anchor' / 'events', name)
    anchor = load_anchor(run)
    if anchor['prompt_sha256'] != ANCHOR_PROMPT_SHA256 or sha256_text(ANCHOR_INSTRUCTIONS) != ANCHOR_PROMPT_SHA256:
        raise MeasureError('The frozen anchor prompt was edited')
    packets = {packet['packet']: packet for packet in anchor['packets']}
    for packet in packets.values():
        directory = run / 'anchor' / 'packets' / packet['packet']
        verify_packet(directory, packet['sha256'])
        if file_sha256(directory / 'instructions.md') != ANCHOR_PROMPT_SHA256:
            raise MeasureError(f'{directory}: instructions are not the frozen prompt')
    events, done = [], set()
    for path in answers:
        packet, rows = checked_answers(path, packets, done, run / 'anchor' / 'packets', 'item', lambda packet: packet['items'],
            ANCHOR_LABELS, judge.ANCHOR_TOUCHED)
        events.extend(judge.AnchorVerdict(start=packet['start'], item=row['item'], label=row['label'],
            cited_frames=tuple(packet['frames'][frame] for frame in dict.fromkeys(row.get('frames', []))), judge=name,
            model=text(model, '--model'), packet=packet['packet'], packet_sha256=packet['sha256']) for row in rows)
    if not events:
        raise MeasureError('No answer file selected')
    target.parent.mkdir(parents=True, exist_ok=True)
    judge.write_events(target, events)
    return events


def anchor_report(run: Path, name: str) -> dict:
    """A new judge against the owner's blind and checked labels on the gate's owner-labelled pairs, beside the
    same figures for the gate's judges and its adjudicated label, and the shift."""
    anchor = load_anchor(run)
    events = read_judge(run / 'anchor' / 'events', name, judge.ANCHOR)
    pairs = anchor['pairs']
    lacking = [f"{pair['start']} / {pair['item']}" for pair in pairs if (pair['start'], pair['item']) not in events]
    if lacking:
        raise MeasureError(f'{len(lacking)} owner-labelled pairs lack a verdict of {name}, the first: {lacking[0]}')
    gate = {(row['start'], row['item']): row for row in anchor['gate_labels']}

    def against_owner(label_of: Callable[[tuple], str]) -> dict:
        figures = {}
        for which in ('blind', 'checked'):
            for group, chosen in (('all', pairs), ('random', [pair for pair in pairs if pair['group'] == 'random'])):
                matched = sum(label_of((pair['start'], pair['item'])) == pair[which] for pair in chosen)
                figures.setdefault(which, {})[group] = dict(matched=matched, compared=len(chosen),
                    interval=binomial_interval(matched, len(chosen)))
        return figures

    def together(first: Callable[[tuple], str], second: Callable[[tuple], str], keys: Sequence[tuple]) -> dict:
        codes = [[ANCHOR_LABELS.index(label(key)) for key in keys] for label in (first, second)]
        return dict(pairs=len(keys), agreement=sum(a == b for a, b in zip(*codes)) / len(keys),
            kappa=cohen_kappa(*codes, len(ANCHOR_LABELS)))

    new = against_owner(lambda key: events[key].label)
    was = dict(adjudicated=against_owner(lambda key: gate[key]['adjudicated']),
        **{judge_name: against_owner(lambda key, judge_name=judge_name: gate[key]['labels'][judge_name])
            for judge_name in anchor['gate_judges']})
    judged = [key for key in gate if key in events]
    first, second = anchor['gate_judges']
    report = dict(schema='anchor-report/1', judge=name, model=next(iter(events.values())).model, gate=anchor['gate'],
        prompt_sha256=anchor['prompt_sha256'], owner_pairs=len(pairs), against_owner=dict(new=new, gate=was),
        shift={which: {group: new[which][group]['matched'] - was['adjudicated'][which][group]['matched']
            for group in ('all', 'random')} for which in ('blind', 'checked')},
        all_pairs=dict(new_with_adjudicated=together(lambda key: events[key].label, lambda key: gate[key]['adjudicated'], judged),
            **{f'new_with_{judge_name}': together(lambda key: events[key].label,
                lambda key, judge_name=judge_name: gate[key]['labels'][judge_name], judged) for judge_name in anchor['gate_judges']},
            gate_first_two=together(lambda key: gate[key]['labels'][first], lambda key: gate[key]['labels'][second], judged)),
        differing=[dict(start=pair['start'], item=pair['item'], group=pair['group'], new=events[(pair['start'], pair['item'])].label,
            adjudicated=gate[(pair['start'], pair['item'])]['adjudicated'], blind=pair['blind'], checked=pair['checked'])
            for pair in pairs if events[(pair['start'], pair['item'])].label != gate[(pair['start'], pair['item'])]['adjudicated']],
        note=SHIFT_NOTE)
    write_json(run / 'anchor' / f'report-{name}.json', report)
    return report


# --- the prompt-change check ------------------------------------------------------------------------------------------------

def prompt_packets(run: Path, before: Path) -> dict:
    """The packets of `before`, a judged run, again with this tool's current instructions: the same windows,
    frames, inputs, facts and shuffled names, checked file by file against the hashes `before` recorded. The
    frozen set of stretches is `before`'s mapping, whose `stretch_sha256` values leave the instructions out."""
    before = measure_dir(before)
    if before == run:
        raise MeasureError('prompt-check packets writes a second run directory; RUN and --before must differ')
    old = load_mapping(before)
    if (run / 'private' / 'judge-mapping.json').exists():
        raise MeasureError(f"{run / 'private' / 'judge-mapping.json'}: already written; judge packets are made once")
    instructions = JUDGE_INSTRUCTIONS[old['kind']]
    packets, manifests = {}, {}
    for packet in old['packets']:  # every stretch is checked before anything is written
        source = before / 'judge-packets' / packet['packet']
        manifests[packet['packet']] = verify_packet(source, packet['sha256'])
        if stretch_sha256(source) != packet['stretch_sha256']:
            raise MeasureError(f'{source}: not the stretch its mapping froze')
    with Building(run / 'judge-packets') as out:
        for packet in sorted(old['packets'], key=lambda packet: packet['packet']):
            source, manifest = before / 'judge-packets' / packet['packet'], manifests[packet['packet']]
            target = out / packet['packet']
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('manifest.json', 'instructions.md'))
            budget = dict(manifest['budget'], estimated=dict(manifest['budget']['estimated']))
            sha, size = seal_packet(target, {**{key: value for key, value in manifest.items() if key != 'files'}, 'budget': budget},
                instructions)
            if stretch_sha256(target) != packet['stretch_sha256']:
                raise MeasureError(f'{target}: the copy is not the frozen stretch')
            packets[packet['packet']] = dict(packet, sha256=sha, bytes=size, estimated_tokens=budget['estimated']['total'], over_budget=budget['over'])
        mapping = dict(old, instructions_sha256=sha256_text(instructions),
            packets=[packets[packet['packet']] for packet in old['packets']],
            before=dict(run=before.name, mapping_sha256=file_sha256(before / 'private' / 'judge-mapping.json'),
                instructions_sha256=old['instructions_sha256']))
        write_json(run / 'private' / 'judge-mapping.json', mapping, once=True)
    return mapping


def prompt_report(run: Path, before: Path, judges: Sequence[str], seed: int | None = None, draws: int = 10000) -> dict:
    """The first two judges' agreement on one frozen set of stretches, judged with the instructions of `before`
    and again with those of `run`, and the difference. `run` must be the output of `prompt-check packets` from
    `before`; every packet's stretch hash is recomputed on both sides."""
    before = measure_dir(before)
    new, old = load_mapping(run), load_mapping(before)
    link = new.get('before')
    if not link or link['mapping_sha256'] != file_sha256(before / 'private' / 'judge-mapping.json'):
        raise MeasureError(f'{run}: not made from {before} by `prompt-check packets`')
    if len(new['packets']) != len(old['packets']):
        raise MeasureError(f'{run}: not the frozen packet set')
    for mine, theirs in zip(new['packets'], old['packets']):
        if (mine['packet'], mine['window'], mine['facts']) != (theirs['packet'], theirs['window'], theirs['facts']):
            raise MeasureError(f'{run}: not the frozen packet set')
        for directory, packet in ((run, mine), (before, theirs)):
            verify_packet(directory / 'judge-packets' / packet['packet'], packet['sha256'])
            if stretch_sha256(directory / 'judge-packets' / packet['packet']) != theirs['stretch_sha256']:
                raise MeasureError(f"{directory / 'judge-packets' / packet['packet']}: not the frozen stretch")
    seed = secrets.randbits(32) if seed is None else seed
    keys = [(packet['window'], fact, packet['start']) for packet in old['packets'] for fact in packet['facts']]
    boot = StartBootstrap([start for _, _, start in keys], seed, draws)
    sides, tables, events = {}, {}, {}
    for side, directory in (('before', before), ('after', run)):
        first, second = (read_judge(directory / 'events', name, judge.FACT_USE) for name in judges)
        lacking = [f'{window} / {fact}' for window, fact, _ in keys if (window, fact) not in first or (window, fact) not in second]
        if lacking:
            raise MeasureError(f'{directory}: {len(lacking)} pairs lack a verdict of {judges[0]} or {judges[1]}, the first: {lacking[0]}')
        rows = [dict(start=start, labels={judges[0]: first[(window, fact)].label, judges[1]: second[(window, fact)].label},
            holds_by={judges[0]: first[(window, fact)].holds, judges[1]: second[(window, fact)].holds}) for window, fact, start in keys]
        sides[side] = dict(models={name: next(iter(events.values())).model for name, events in zip(judges, (first, second))},
            instructions_sha256=(old if side == 'before' else new)['instructions_sha256'],
            label=judges_beside(boot, rows, judges), holds=judges_beside(boot, rows, judges, 'holds_by'))
        tables[side] = boot.sums(rows, lambda row: confusion([USE_LABELS.index(row['labels'][judges[0]])],
            [USE_LABELS.index(row['labels'][judges[1]])], len(USE_LABELS)), (len(USE_LABELS), len(USE_LABELS)))
        events[side] = (first, second)

    if sides['before']['models'] != sides['after']['models']:
        raise MeasureError('prompt-check requires the same model for each judge before and after')

    def difference(name: str) -> float | None:
        values = [sides[side]['label'][name] for side in ('before', 'after')]
        values = [value['value'] if isinstance(value, dict) else value for value in values]
        return None if None in values else values[1] - values[0]

    report = dict(schema='prompt-check/1', kind=old['kind'], judges=list(judges), before_run=before.name, pairs=len(keys),
        stretches=len(old['packets']), prompt_changed=old['instructions_sha256'] != new['instructions_sha256'],
        bootstrap=dict(seed=seed, draws=draws, starts=len(boot.names), note=BOOTSTRAP_NOTE), before=sides['before'], after=sides['after'],
        shift=dict(agreement=difference('agreement'), dispute_rate=difference('dispute_rate'),
            kappa=dict(value=difference('kappa'), interval=boot.interval(lambda was, now: kappa_of(now) - kappa_of(was),
                tables['before'], tables['after']))),
        # how many of its own labels each judge changed between the two prompts
        relabelled={name: sum(events['before'][number][(window, fact)].label != events['after'][number][(window, fact)].label
            for window, fact, _ in keys) / len(keys) for number, name in enumerate(judges)})
    write_json(run / 'prompt-check.json', report)
    return report


# --- the withholding simulation -------------------------------------------------------------------------------------------

#: The measure gate's numbers (docs/acceptance/2026-11-13-memory-measure-gate.md): known items touched per start
#: of 200 decisions with its exact Poisson interval, the missed share among touched with its bootstrap interval,
#: the judge errors the gate's sizing used, and the price of a start's play.
GATE_TOUCHED, GATE_TOUCHED_ENDS = 8.30, (5.64, 11.78)
GATE_MISSED, GATE_MISSED_ENDS = 0.452, (0.115, 0.690)
GATE_WRONG, GATE_BASE_WRONG = (0.0, 0.1, 0.167, 0.25), 0.1
GATE_PRICE_USD = 3.58
#: docs/design/general-memory.md, "What it costs": the recall model is inferred to add two thirds to about the
#: same again to the cost of play. One first store and one grooming session are bought once.
RECALL_OVERHEAD = (1.67, 2.0)
STORE_USD, GROOMING_USD = 23.0, (1.16, 4.19)
_CRITICAL: dict[Fraction, list[int]] = {}


def critical_counts(limit: int, alpha: float) -> np.ndarray:
    """For each count M of missed units from 0 to `limit`, the smallest number of them that must be withheld
    for the one-sided randomization test to reject at `alpha`; M + 1 when no number does.

    The design withholds each unit with probability one half, by itself, within each start. Re-drawing that
    delivery leaves which units were missed as it is and makes the number of missed units that are withheld
    Binomial(M, 1/2), whatever the starts are. So the randomization distribution of the statistic, missed
    withheld minus missed delivered pooled over starts, is known exactly and no re-draws are sampled. The tail
    is summed in whole numbers."""
    level = Fraction(alpha).limit_denominator(1_000_000)
    known = _CRITICAL.setdefault(level, [])
    for missed in range(len(known), limit + 1):
        term, tail, least = 1, 0, missed + 1  # term is C(missed, count), from count = missed downwards
        for count in range(missed, -1, -1):
            tail += term
            if tail * level.denominator > level.numerator * 2 ** missed:
                break
            least = count
            term = term * count // (missed - count + 1)
        known.append(least)
    return np.asarray(known[:limit + 1])


def withholding_rejections(rng: np.random.Generator, starts: int, touched: float, missed: float, ratio: float, wrong: float,
                           rho: float = 0.2, sims: int = 10000, alpha: float = 0.05) -> np.ndarray:
    """Whether each of `sims` simulated studies of `starts` starts rejects "delivery changes nothing".

    Each start touches a Poisson(`touched`) number of units. Each unit is withheld with probability one half.
    A start has its own miss probability, Beta with mean `missed` and intra-start correlation `rho`; a withheld
    unit is missed (found again, or looked for elsewhere) with it and a delivered one with `ratio` times it.
    The judge flips each label with probability `wrong`. The test is `critical_counts`."""
    if not (touched > 0 and 0 < missed < 1 and 0 < ratio <= 1 and 0 < rho < 1 and 0 <= wrong < 0.5 and starts >= 1):
        raise MeasureError('The simulation needs units touched above 0, a missed share and a correlation strictly between 0 '
            'and 1, a ratio above 0 and at most 1, a judge error from 0 to below 0.5 and at least one start')
    units = rng.poisson(touched, (sims, starts))
    withheld = rng.binomial(units, 0.5)
    share = rng.beta(missed * (1 - rho) / rho, (1 - missed) * (1 - rho) / rho, (sims, starts))

    def seen_missed(count: np.ndarray, probability: np.ndarray) -> np.ndarray:
        lost = rng.binomial(count, probability)
        return (lost - rng.binomial(lost, wrong) + rng.binomial(count - lost, wrong)).sum(axis=1)

    missed_withheld = seen_missed(withheld, share)
    total = missed_withheld + seen_missed(units - withheld, ratio * share)
    return missed_withheld >= critical_counts(int(total.max()), alpha)[total]


def withholding_rows(touched: float = GATE_TOUCHED, touched_ends: Sequence[float] = GATE_TOUCHED_ENDS, missed: float = GATE_MISSED,
                     missed_ends: Sequence[float] = GATE_MISSED_ENDS, wrong: Sequence[float] = GATE_WRONG,
                     base_wrong: float = GATE_BASE_WRONG) -> list[dict]:
    """The cases to size: the point values at each judge error, then each input at each end of its interval and
    the two corners where both are at their favourable or unfavourable end, at the base judge error."""
    rows = [dict(case=f'point values, judge error {error:g}', touched=touched, missed=missed, wrong=error) for error in wrong]
    rows += [dict(case=f"units touched at the interval's {name} end", touched=end, missed=missed, wrong=base_wrong)
        for name, end in zip(('lower', 'upper'), touched_ends)]
    rows += [dict(case=f"missed share at the interval's {name} end", touched=touched, missed=end, wrong=base_wrong)
        for name, end in zip(('lower', 'upper'), missed_ends)]
    rows += [dict(case=f'both at the {name} ends', touched=a, missed=b, wrong=base_wrong)
        for name, a, b in (('unfavourable', touched_ends[0], missed_ends[0]), ('favourable', touched_ends[1], missed_ends[1]))]
    return rows


def simulate_withholding(rows: Sequence[dict], *, rho: float = 0.2, sims: int = 10000, seed: int = 386, target: float = 0.8,
                         alpha: float = 0.05, minimum: int = 2, ceiling: int = 60, price: float = GATE_PRICE_USD) -> dict:
    """For each case, the smallest number of starts, from `minimum` to `ceiling`, at which a halving of the missed
    share by delivery is detected with probability `target`; at that size (the ceiling when none reaches it), the
    chance of detecting a cut of one third and the false-alarm rate when delivery changes nothing; and the price.

    Every rate has its own random stream, seeded by (`seed`, case, starts, effect), so a case's numbers do not
    depend on which other cases are run."""
    if not 1 <= minimum <= ceiling:
        raise MeasureError('The search needs 1 <= --min-starts <= --ceiling')
    cases = []
    for number, row in enumerate(rows):
        def rate(starts: int, effect: int, ratio: float) -> float:
            rng = np.random.default_rng([seed, number, starts, effect])
            return float(withholding_rejections(rng, starts, row['touched'], row['missed'], ratio, row['wrong'], rho, sims, alpha).mean())

        scanned, found = [], None
        for starts in range(minimum, ceiling + 1):
            scanned.append([starts, rate(starts, 0, 0.5)])
            if scanned[-1][1] >= target:
                found = starts
                break
        at = found or ceiling
        play = at * price
        cases.append(dict(row, starts=found, at=at, halving=scanned[-1][1], third_cut=rate(at, 1, 2 / 3), false_alarm=rate(at, 2, 1.0),
            best=max(scanned, key=lambda entry: entry[1]), scanned=scanned,
            price=dict(reached=found is not None, play_usd=round(play, 2),
                play_with_recall_usd=[round(play * factor, 2) for factor in RECALL_OVERHEAD],
                total_usd=[round(play + STORE_USD + GROOMING_USD[0], 2), round(play * RECALL_OVERHEAD[1] + STORE_USD + GROOMING_USD[1], 2)])))
    return dict(schema='withholding-simulation/1', seed=seed, sims=sims, rho=rho, alpha=alpha, target=target, minimum=minimum,
        ceiling=ceiling, withheld_probability=0.5,
        model=('per start: Poisson units touched; each unit withheld with probability 1/2; a start-level miss probability, Beta '
            'with the given mean and intra-start correlation rho; a withheld unit missed with it and a delivered one with ratio '
            'times it; each label flipped by the judge with the given probability'),
        test=('one-sided randomization test that re-draws delivery within each start, exact: given M missed units, the number '
            'withheld is Binomial(M, 1/2); statistic: missed withheld minus missed delivered, pooled over starts'),
        effects=dict(halving=0.5, third_cut=2 / 3, false_alarm=1.0),
        prices=dict(per_start_usd=price, recall_overhead=list(RECALL_OVERHEAD), store_usd=STORE_USD, grooming_usd=list(GROOMING_USD),
            total_usd='play without recall, plus the store and the cheaper grooming session; to play at the higher recall '
                'overhead, plus the store and the dearer grooming session'),
        cases=cases)


# --- rendering and the command line -------------------------------------------------------------------------------------

def _value(value: float | None, digits: int = 3) -> str:
    return 'undefined' if value is None else f'{value:.{digits}f}'


def _range(entry: dict, digits: int = 3) -> str:
    interval = entry.get('interval')
    return _value(entry.get('value'), digits) + (f' (95% interval over starts {interval[0]:.{digits}f} to {interval[1]:.{digits}f})'
        if interval else ' (no interval)')


def _beside(part: dict) -> str:
    return (f"first two judges on {part['pairs']} pairs ({part['on']}): agreement {_value(part['agreement'])}, kappa "
        f"{_range(part['kappa'])}, dispute rate {_range(part['dispute_rate'])}")


def render_agreement(value: dict) -> str:
    lines = [f"{value['pairs']} pairs of {value['kind']} packets; judges {value['judges'][0]} and {value['judges'][1]}; third "
        f"{value['third'] or 'none'}",
        f"label agreement {_value(value['agreement'])}, Cohen's kappa {_value(value['kappa'])}, dispute rate {_value(value['dispute_rate'])} "
        f"({value['disputed']} pairs)",
        f"holds agreement {_value(value['holds_agreement'])}, Cohen's kappa {_value(value['holds_kappa'])}, "
        f"dispute rate {_value(value['holds_dispute_rate'])} ({value['holds_disputed']} pairs)",
        f"not yet adjudicated {value['unresolved']}" + (f"; packets for a third judge: {' '.join(value['third_judge_packets'])}"
            if value['third_judge_packets'] else ''),
        f"pairs the third judge settled with a label neither judge gave (third_alone): {value['third_alone']}"]
    lines.extend(f"  {row['window']} / {row['fact']}: " + ', '.join(f'{name} {label}' for name, label in row['labels'].items())
        for row in value['rows'] if row['by'] == 'third_alone')
    return '\n'.join(lines)


def render_measure(report: dict) -> str:
    lines = [report['not_corrected'],
        f"{report['pairs']} adjudicated pairs of {report['kind']} packets over {report['bootstrap']['starts']} starts; judges "
        f"{' and '.join(report['judges'])}, third {report['third'] or 'none'}; bootstrap seed {report['bootstrap']['seed']}, "
        f"{report['bootstrap']['draws']} draws ({report['bootstrap']['note']})",
        'all pairs: ' + _beside(report['judges_overall']),
        'actors with facts but no kept frames: ' + (', '.join(report['no_frames']) or 'none'),
        'facts without an eligible kept frame: ' + (', '.join(f"{row['actor']} / {row['fact']}"
            for row in report['not_shown']) or 'none')]
    for route, counts in report['labels_by_route'].items():
        if counts['pairs']:
            lines.append(f"  {route}: {counts['pairs']} pairs: " + ', '.join(f'{label} {counts[label]}' for label in USE_LABELS))
    if report['measures'] is None:
        lines.append('the use measures are not taken from blind packets, which leave out what was delivered')
    for name, part in (report['measures'] or {}).items():
        lines.append(f"{name}: {part['numerator']} of {part['denominator']} = {_range(part)}")
        lines.append(f"  {part['definition']}")
        lines.append('  route-wide: ' + _beside(part['judges_route']))
        lines.append('  rate-driving pairs: ' + _beside(part['judges_rate_pairs']))
    return '\n'.join(lines)


def _matched(part: dict) -> str:
    return f"{part['matched']} of {part['compared']} (exact 95% interval {part['interval'][0]:.3f} to {part['interval'][1]:.3f})"


def render_anchor(report: dict) -> str:
    lines = [f"anchor: judge {report['judge']} ({report['model']}) on the {report['owner_pairs']} owner-labelled pairs of "
        f"{report['gate']}, with the gate's prompt, sha256 {report['prompt_sha256']}"]
    for which, title in (('blind', "owner's blind labels"), ('checked', "owner's checked labels")):
        for group, words in (('all', 'all pairs'), ('random', 'the random draw')):
            lines.append(f"matches with the {title}, {words}: new judge {_matched(report['against_owner']['new'][which][group])}; "
                + '; '.join(f"gate {name} {_matched(figures[which][group])}" for name, figures in report['against_owner']['gate'].items())
                + f"; shift {report['shift'][which][group]:+d}")
    for name, part in report['all_pairs'].items():
        lines.append(f"{name.replace('_', ' ')}, {part['pairs']} pairs: agreement {part['agreement']:.3f}, kappa {_value(part['kappa'])}")
    lines.append(f"owner-labelled pairs where the new judge differs from the gate's adjudicated label: {len(report['differing'])}")
    lines.extend(f"  {row['start']} / {row['item']} ({row['group']}): new {row['new']}, adjudicated {row['adjudicated']}, owner blind "
        f"{row['blind']}, checked {row['checked']}" for row in report['differing'])
    lines.append(report['note'])
    return '\n'.join(lines)


def render_prompt_check(report: dict) -> str:
    lines = [f"prompt check on {report['stretches']} frozen stretches, {report['pairs']} pairs, {report['bootstrap']['starts']} starts; "
        f"judges {' and '.join(report['judges'])}; the instructions {'changed' if report['prompt_changed'] else 'did not change'}"]
    for side in ('before', 'after'):
        lines.append(f"{side} (instructions sha256 {report[side]['instructions_sha256'][:12]}): " + _beside(report[side]['label']))
        lines.append('  ' + _beside(report[side]['holds']))
    shift = report['shift']
    lines.append(f"shift, after minus before: agreement {_value(shift['agreement'])}, kappa {_range(shift['kappa'])}, dispute rate "
        f"{_value(shift['dispute_rate'])}")
    lines.append('share of its own labels each judge changed: ' + ', '.join(f'{name} {share:.3f}'
        for name, share in report['relabelled'].items()))
    return '\n'.join(lines)


def render_withholding(report: dict) -> str:
    prices = report['prices']
    lines = ['# Withholding within each start: starts needed and their price', '',
        f"Seed {report['seed']}, {report['sims']} simulated studies a size, intra-start correlation {report['rho']}, "
        f"one-sided test at {report['alpha']}, target power {report['target']}, sizes {report['minimum']} to {report['ceiling']} starts.",
        f"Model: {report['model']}.", f"Test: {report['test']}.",
        f"Play is ${prices['per_start_usd']:.2f} a start; the recall model is inferred to multiply it by "
        f"{prices['recall_overhead'][0]} to {prices['recall_overhead'][1]}; bought once: a store of about ${prices['store_usd']:.0f} and "
        f"one grooming session, ${prices['grooming_usd'][0]:.2f} to ${prices['grooming_usd'][1]:.2f}. Total: {prices['total_usd']}.",
        f"A rate near the target has a standard error of about {math.sqrt(report['target'] * (1 - report['target']) / report['sims']):.3f}, "
        'so the first size to reach it can be a start early.', '',
        '| Case | Touched | Missed | Judge error | Starts | Halving | One-third cut | False alarm | Play | Play with recall | Total |',
        '| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |']
    for case in report['cases']:
        price, over = case['price'], '' if case['price']['reached'] else 'over '
        starts = str(case['starts']) if case['starts'] else f"none up to {report['ceiling']} (best {case['best'][1]:.2f} at {case['best'][0]})"
        lines.append(f"| {case['case']} | {case['touched']:g} | {case['missed']:g} | {case['wrong']:g} | {starts} | {case['halving']:.2f} | "
            f"{case['third_cut']:.2f} | {case['false_alarm']:.3f} | {over}${price['play_usd']:.0f} | "
            f"{over}${price['play_with_recall_usd'][0]:.0f} to ${price['play_with_recall_usd'][1]:.0f} | "
            f"{over}${price['total_usd'][0]:.0f} to ${price['total_usd'][1]:.0f} |")
    lines += ['', 'Halving, one-third cut and false alarm are the chances that the test rejects when delivery halves the missed '
        'share, cuts it by a third, or changes nothing, at the size in the Starts column (the ceiling where none is reached).']
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    facts_command = commands.add_parser('facts', help='build judged-facts/1 from frozen delivery and host events')
    facts_command.add_argument('run',type=Path)
    facts_command.add_argument('--runs',nargs='+',type=Path,required=True)
    packets = commands.add_parser('packets', help='packets for the annotators or the judges').add_subparsers(dest='kind', required=True)
    for kind in ('annotate', 'use', 'blind'):
        command = packets.add_parser(kind)
        command.add_argument('run', type=Path)
        command.add_argument('--runs', nargs='+', type=Path, required=True, help='sealed admission run directories, in order')
        command.add_argument('--every', type=int, default=3)
        command.add_argument('--budget', type=int, default=PACKET_TOKENS, help='estimated tokens one packet may hold')
        command.add_argument('--min-changed', type=float, default=0.0, help='changed-pixel share above which a frame is changed')
        if kind != 'annotate':
            command.add_argument('--facts', type=Path, required=True, help=f'the facts to judge, {FACTS_SCHEMA}')
            command.add_argument('--seed', type=int)
    items = commands.add_parser('items', help='the annotated facts from two annotators and the lead\'s matches')
    items.add_argument('run', type=Path)
    items.add_argument('--annotators', nargs=2, required=True, metavar=('A', 'B'))
    items.add_argument('--matches', type=Path, help='{"matches": [["<A entry>", "<B entry>"], ...]}: at least one match; '
        'an entry may appear in several matches (one fact seen in several packets); any other top-level key is ignored')
    items.add_argument('--list', action='store_true', help='print every entry with its ID and write nothing')
    events = commands.add_parser('events', help='validate one judge\'s answers and write its judge events')
    agree = commands.add_parser('agreement', help='the first two judges\' agreement and the adjudicated labels')
    agree.add_argument('run', type=Path)
    agree.add_argument('--judges', nargs=2, required=True, metavar=('A', 'B'))
    agree.add_argument('--third')
    agree.add_argument('--json', action='store_true')
    stats = commands.add_parser('measure', help='the standing use measures, from adjudicated labels')
    stats.add_argument('run', type=Path)
    anchor = commands.add_parser('anchor', help='the measure gate\'s owner-labelled pairs, re-judged').add_subparsers(dest='step', required=True)
    anchor_make = anchor.add_parser('packets')
    anchor_make.add_argument('run', type=Path)
    anchor_make.add_argument('--gate', type=Path, required=True, help='the sealed measure gate\'s run directory; only read')
    anchor_make.add_argument('--dry-run', action='store_true', help='check the gate\'s hashes and write nothing')
    anchor_events_command = anchor.add_parser('events')
    for command in (events, anchor_events_command):
        command.add_argument('run', type=Path)
        command.add_argument('--judge', required=True)
        command.add_argument('--model', required=True)
        command.add_argument('answers', nargs='+', type=Path)
    anchor_report_command = anchor.add_parser('report')
    anchor_report_command.add_argument('run', type=Path)
    anchor_report_command.add_argument('--judge', required=True)
    anchor_report_command.add_argument('--json', action='store_true')
    prompt = commands.add_parser('prompt-check', help='the first two judges\' agreement before and after a prompt change') \
        .add_subparsers(dest='step', required=True)
    prompt_make = prompt.add_parser('packets')
    prompt_report_command = prompt.add_parser('report')
    for command in (prompt_make, prompt_report_command):
        command.add_argument('run', type=Path)
        command.add_argument('--before', type=Path, required=True, help='the run directory judged with the earlier instructions')
    prompt_report_command.add_argument('--judges', nargs=2, required=True, metavar=('A', 'B'))
    for command in (stats, prompt_report_command):
        command.add_argument('--seed', type=int)
        command.add_argument('--draws', type=int, default=10000)
        command.add_argument('--json', action='store_true')
    sim = commands.add_parser('simulate-withholding', help='starts needed, and their price, to see delivery halve the missed share')
    sim.add_argument('--touched', type=float, default=GATE_TOUCHED, help='units touched per start')
    sim.add_argument('--touched-ends', type=float, nargs=2, default=GATE_TOUCHED_ENDS, metavar=('LOW', 'HIGH'))
    sim.add_argument('--missed', type=float, default=GATE_MISSED, help='the share of touched units missed when withheld')
    sim.add_argument('--missed-ends', type=float, nargs=2, default=GATE_MISSED_ENDS, metavar=('LOW', 'HIGH'))
    sim.add_argument('--wrong', type=float, nargs='+', default=GATE_WRONG, help='the shares of labels the judge gets wrong')
    sim.add_argument('--base-wrong', type=float, default=GATE_BASE_WRONG, help='the judge error at the interval ends')
    sim.add_argument('--rho', type=float, default=0.2)
    sim.add_argument('--sims', type=int, default=10000)
    sim.add_argument('--seed', type=int, default=386)
    sim.add_argument('--target', type=float, default=0.8)
    sim.add_argument('--alpha', type=float, default=0.05)
    sim.add_argument('--min-starts', type=int, default=2)
    sim.add_argument('--ceiling', type=int, default=60, help='the most starts the search tries')
    sim.add_argument('--price', type=float, default=GATE_PRICE_USD, help='dollars of play per start')
    sim.add_argument('--json', action='store_true')
    sim.add_argument('--render', type=Path, metavar='REPORT.json', help='print the table of a saved report and simulate nothing')
    args = parser.parse_args(argv)
    try:
        if args.command == 'simulate-withholding':
            if args.render:
                report = read_json(args.render)
                if not isinstance(report, dict) or report.get('schema') != 'withholding-simulation/1':
                    raise MeasureError(f'{args.render}: not a withholding-simulation/1 report')
            else:
                report = simulate_withholding(withholding_rows(args.touched, args.touched_ends, args.missed, args.missed_ends,
                    args.wrong, args.base_wrong), rho=args.rho, sims=args.sims, seed=args.seed, target=args.target, alpha=args.alpha,
                    minimum=args.min_starts, ceiling=args.ceiling, price=args.price)
            print(json.dumps(report, indent=1) if args.json and not args.render else render_withholding(report))
            return 0
        run = measure_dir(args.run)
        if args.command == 'facts':
            value=build_facts(run,run_dirs(args.runs))
            print(f"judged-facts/1: {len(value['admissions'])} admissions in {run/'judged-facts.json'}")
        elif args.command == 'packets' and args.kind == 'annotate':
            index = annotate_packets(run, run_dirs(args.runs), args.every, args.budget, args.min_changed)
            print(f"{len(index['packets'])} packets in {run / 'annotate'}; frames recorded {index['frames']['recorded']}, "
                f"changed {index['frames']['changed']}, kept {index['frames']['kept']}; budget {index['budget_tokens']} tokens")
            for packet in index['packets']:
                print(f"  {packet['packet']}: {packet['admission']}, {len(packet['frames'])} frames, about "
                    f"{packet['estimated_tokens']} tokens{' (over the budget)' if packet['over_budget'] else ''}, {packet['bytes']} bytes")
        elif args.command == 'packets':
            mapping = fact_packets(run, run_dirs(args.runs), args.facts, args.kind, args.budget, args.every, args.min_changed, args.seed)
            print(f"{len(mapping['packets'])} {mapping['kind']} packets in {run / 'judge-packets'}; seed {mapping['seed']}; budget "
                f"{mapping['budget_tokens']} tokens; the mapping is {run / 'private' / 'judge-mapping.json'} and is not for a judge")
            for packet in mapping['packets']:
                print(f"  {packet['packet']}: {packet['window']}, {len(packet['frames'])} frames, {len(packet['facts'])} facts, about "
                    f"{packet['estimated_tokens']} tokens{' (over the budget)' if packet['over_budget'] else ''}")
        elif args.command == 'items' and args.list:
            index = read_json(run / 'annotate' / 'packets.json')
            for name in args.annotators:
                for identity, entry in read_annotations(run, name, index).items():
                    print(f"{name} {identity}: {entry['fact']} | {' '.join(entry['frames'])}")
        elif args.command == 'items':
            if args.matches is None:
                raise MeasureError('items needs --matches FILE, or --list')
            value = build_items(run, args.annotators, args.matches)
            print(f"{len(value['facts'])} annotated facts in {run / 'annotated-facts.json'}, sha256 {value['sha256']}")
            for name, count in value['counts'].items():
                print(f"  {name}: {count['entries']} entries, {count['in_a_fact']} in a fact, {count['dropped']} dropped")
            for item in value['facts']:  # allowed: one fact seen in several packets; printed so that it is seen
                for name, entries in item['listed'].items():
                    if len(entries) > 1:
                        print(f"  {item['id']} holds {len(entries)} entries of {name}: " + ' '.join(entry['entry'] for entry in entries))
        elif args.command == 'events':
            written = judge_events(run, args.judge, args.model, args.answers)
            counts = Counter(event.label for event in written)
            print(f"{len(written)} judge events in {run / 'events' / (args.judge + '.jsonl')}: "
                + ', '.join(f'{label} {counts[label]}' for label in USE_LABELS))
        elif args.command == 'agreement':
            value = agreement(run, args.judges, args.third)
            print(json.dumps(value, indent=1) if args.json else render_agreement(value))
        elif args.command == 'measure':
            report = measure(run, args.seed, args.draws)
            print(json.dumps(report, indent=1) if args.json else render_measure(report))
        elif args.command == 'anchor' and args.step == 'packets':
            value = anchor_packets(run, args.gate, args.dry_run)
            print(f"{len(value['packets'])} packets of {value['gate']} hold its {len(value['pairs'])} owner-labelled pairs; every "
                f"file matches the hash the gate recorded, and every instructions.md is the frozen prompt, sha256 {value['prompt_sha256']}")
            print('dry run: nothing written' if args.dry_run else f"copied to {run / 'anchor' / 'packets'}; the mapping is "
                f"{run / 'private' / 'anchor.json'} and is not for a judge")
        elif args.command == 'anchor' and args.step == 'events':
            written = anchor_events(run, args.judge, args.model, args.answers)
            counts = Counter(event.label for event in written)
            print(f"{len(written)} anchor events in {run / 'anchor' / 'events' / (args.judge + '.jsonl')}: "
                + ', '.join(f'{label} {counts[label]}' for label in ANCHOR_LABELS))
        elif args.command == 'anchor':
            report = anchor_report(run, args.judge)
            print(json.dumps(report, indent=1) if args.json else render_anchor(report))
        elif args.step == 'packets':
            mapping = prompt_packets(run, args.before)
            print(f"{len(mapping['packets'])} packets in {run / 'judge-packets'}: the frozen stretches of {mapping['before']['run']} "
                f"with instructions sha256 {mapping['instructions_sha256']} (before: {mapping['before']['instructions_sha256']})")
        else:
            report = prompt_report(run, args.before, args.judges, args.seed, args.draws)
            print(json.dumps(report, indent=1) if args.json else render_prompt_check(report))
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
