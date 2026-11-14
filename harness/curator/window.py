"""A window of decisions: the part of one actor's trace a curator session reads (#460).

A whole-admission session reads every actor of its sealed sessions. A window narrows that to one
actor of one session and a range of its steps (`seq` in `steps.jsonl`, first and last inclusive).
Both run the same path: `harness.trace.projection.project` writes the whole projection, then
`restrict` edits it in place, and with the full window it changes nothing.

What a window keeps: the actor's steps in the range, the tool calls that belong to them and the
frames those steps returned, the actor's received prompt and guide. What it drops, because each
reports on the actor beyond the range: the other actors, sealed handoff packets, the player's memory
store and the actor's final report. A tool call belongs to the step its result names
(`operation_id`); a call that names none (memory and handoff tools, an unanswered call) belongs to
the step of the next call that does, and a call after the last such call belongs to the last step.

The manifest says what the window is under `window`, and lists what it dropped. Frames outside the
range are not in `trace/frames/`, so the gate's provenance check refuses a citation of one.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil

from .gate import COVERAGE

MANIFEST = 'manifest.json'
NAME = re.compile(r'[A-Za-z0-9_-]+')
DROPPED = ('every other actor', 'sealed handoff packets', 'the sealed memory store',
           "the actor's final report", 'steps, tool calls and frames outside the window')


class WindowError(ValueError):
    """The window does not fit the trace it was given."""


@dataclass(frozen=True)
class Window:
    """`Window()` covers everything. A restricted window names a session, an actor directory and
    steps `first` to `last` (inclusive, 1-based)."""

    session: str | None = None
    actor: str | None = None
    first: int = 1
    last: int | None = None

    def __post_init__(self):
        if (self.session is None) != (self.actor is None):
            raise WindowError('a window names both a session and an actor, or neither')
        if self.session is None:
            if (self.first, self.last) != (1, None):
                raise WindowError('the full window takes no range')
            return
        for name, value in (('session', self.session), ('actor', self.actor)):
            if not (isinstance(value, str) and NAME.fullmatch(value)):
                raise WindowError(f'window {name} must match [A-Za-z0-9_-]+: {value!r}')
        if not (isinstance(self.first, int) and not isinstance(self.first, bool) and self.first >= 1):
            raise WindowError('window first step must be an integer of at least 1')
        if not (isinstance(self.last, int) and not isinstance(self.last, bool) and self.last >= self.first):
            raise WindowError('window last step must be an integer not before the first')

    @property
    def full(self) -> bool:
        return self.session is None

    @classmethod
    def read(cls, row: object) -> 'Window':
        if not isinstance(row, dict) or set(row) - {'session', 'actor', 'first', 'last'}:
            raise WindowError(f'a window is an object with session, actor, first and last: {row!r}')
        return cls(**row)

    def record(self) -> dict:
        return {} if self.full else dict(session=self.session, actor=self.actor, first=self.first, last=self.last)


FULL = Window()


def coverage(window: Window, sessions: list[str], manifest: dict) -> dict:
    """What a session read, for the gate to publish with the version it makes: the session, the actor and
    the last step read (the window's, as clamped to the steps the actor has). A whole-admission session has no single actor or last step."""
    if window.full:
        return dict(schema=COVERAGE, session=','.join(sessions), actor=None, last_step=None)
    return dict(schema=COVERAGE, session=window.session, actor=window.actor, last_step=manifest['window']['last'])


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write(path: Path, rows: list[dict]) -> None:
    with path.open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')


def _owners(calls: list[dict], seq_of: dict[str, int], last: int) -> list[int]:
    """The step each tool call belongs to, by the rule in the module's docstring."""
    owners: list[int | None] = [seq_of.get((call.get('outcome') or {}).get('operation_id')) for call in calls]
    following = last
    for index in range(len(calls) - 1, -1, -1):
        if owners[index] is None:
            owners[index] = following
        else:
            following = owners[index]
    return owners


def restrict(out: Path, manifest: dict, window: Window) -> dict:
    """Narrow the projection in `out` to `window` in place; return the rewritten manifest."""
    if window.full:
        return manifest
    out = Path(out)
    sessions = manifest['sessions']
    if [s['name'] for s in sessions] != [window.session]:
        raise WindowError(f'a window needs exactly the one session it names, {window.session!r}')
    entry = sessions[0]
    actor = next((a for a in entry['actors'] if a['directory'] == window.actor), None)
    if actor is None:
        raise WindowError(f'session {window.session!r} has no actor {window.actor!r}')
    directory = out/window.session/window.actor
    steps = _jsonl(directory/'steps.jsonl')
    if window.first > len(steps):
        raise WindowError(f'{window.actor!r} has {len(steps)} steps; the window starts at {window.first}')
    last = min(window.last, len(steps))
    kept = [s for s in steps if window.first <= s['seq'] <= last]
    frames = {s['frame'] for s in kept if s['frame']}
    calls = _jsonl(directory/'tools.jsonl')
    owners = _owners(calls, {s['operation_id']: s['seq'] for s in steps}, len(steps))
    calls = [c for c, owner in zip(calls, owners) if window.first <= owner <= last]
    _write(directory/'steps.jsonl', kept)
    _write(directory/'tools.jsonl', calls)
    for other in (out/window.session).iterdir():
        if other != directory:
            shutil.rmtree(other)
    (directory/'final.txt').unlink(missing_ok=True)
    for frame in (out/'frames').iterdir():
        if frame.stem not in frames:
            frame.unlink()
    (out/'memory.json').unlink(missing_ok=True)
    entry['actors'] = [dict(actor, steps=len(kept), frames=len(frames), tool_calls=len(calls))]
    entry['handoffs'] = []
    manifest['files'] = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(out.rglob('*')) if p.is_file() and p.name != MANIFEST}
    manifest['window'] = dict(window.record(), last=last, steps_available=len(steps))
    manifest['dropped'] = [*manifest['dropped'], *DROPPED]
    (out/MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=1))
    return manifest


def positions(out: Path, manifest: dict, previous: dict[str, dict]) -> dict[str, dict]:
    """Assign a stable ordered position to each frame, retaining its latest occurrence.

    Session order is the supplied admission order; actor order is directory order;
    step order is seq. The identity and seq are retained beside the ordinal for inspection.
    """
    result = {}
    admissions = {p['session']: p['order'][0] for p in previous.values()}
    next_admission = max(admissions.values(), default=0)
    for session in manifest['sessions']:
        if session['name'] not in admissions:
            next_admission += 1
            admissions[session['name']] = next_admission
        for actor in session['actors']:
            for step in _jsonl(out/session['name']/actor['directory']/'steps.jsonl'):
                frame = step.get('frame')
                if frame:
                    position = dict(session=session['name'], actor=actor['directory'], step=step['seq'],
                                    order=[admissions[session['name']], actor['directory'], step['seq']])
                    candidates = [p for p in (previous.get(frame), result.get(frame), position) if p]
                    result[frame] = max(candidates, key=lambda p: p['order'])
    missing = {Path(name).stem for name in manifest['files'] if name.startswith('frames/')} - result.keys()
    if missing:
        raise WindowError(f'frames without trace positions: {sorted(missing)}')
    return result


def citations_only(out: Path, manifest: dict, citations: set[str]) -> dict:
    """Grooming reads the last admission's cited frames, with their trace positions."""
    available = {Path(name).stem for name in manifest['files'] if name.startswith('frames/')}
    if citations - available:
        raise WindowError(f'last admission citations missing from trace: {sorted(citations - available)}')
    for frame in (out/'frames').iterdir():
        if frame.stem not in citations:
            frame.unlink()
    # Other trace content could disclose uncited observations. Retain only cited steps.
    for session in manifest['sessions']:
        for actor in session['actors']:
            directory = out/session['name']/actor['directory']
            steps = [s for s in _jsonl(directory/'steps.jsonl') if s.get('frame') in citations]
            for path in directory.iterdir():
                if path.name != 'steps.jsonl':
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
            _write(directory/'steps.jsonl', steps)
            actor.update(steps=len(steps), frames=len({s['frame'] for s in steps}), tool_calls=0)
        handoffs = out/session['name']/'handoffs'
        if handoffs.exists():
            shutil.rmtree(handoffs)
        session['handoffs'] = []
    (out/'memory.json').unlink(missing_ok=True)
    manifest['files'] = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(out.rglob('*')) if p.is_file() and p.name != MANIFEST}
    manifest['citations_only'] = sorted(citations)
    (out/MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=1))
    return manifest
