"""`judge`-source events: one model judge's answer to one closed question (docs/contracts/evaluation.md, #386).

A judge event uses the contract's event envelope (`kind`, `source`, `confidence`, `payload`). It is kept in a
`judge-events/2` JSON Lines file and never in an `evaluation-record/1` store: `records.EVENT_SOURCES` does not
list `judge`, so a record refuses one, and the viewer, which reads records only, cannot serve one. This module
validates and reads or writes that file. It reads no frame and calls no model; it is game-neutral.

One kind per file:

- `fact_use_verdict`: what the player did about one fact over one window, a stretch of decisions and never a
  single step, and whether the frames show the fact still holding. The fact's route is set by the tooling that
  made the packet, never by the judge.
- `anchor_verdict`: the measure gate's frozen question about one known item over one stretch. It exists only so a
  new judge model can be compared with the owner's labels of the measure gate (the anchor check).
- `stuck_verdict`, `retry_verdict`, `milestone_verdict`, `claim_verdict`: game-neutral process questions over
  recorded windows or shuffled admission frames, cut by tools/process_measures.py.

`judge-events/1` is not read.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
import re
from typing import ClassVar

from .records import EvaluationError, dumps
from .sources import read_json_lines

SCHEMA = 'judge-events/2'
SOURCE = 'judge'
FACT_USE, ANCHOR = 'fact_use_verdict', 'anchor_verdict'
#: The closed answers about a fact, with the words docs/design/general-memory.md#3-measurement gives them.
USE_LABELS = ('in_line', 'against', 'found_again', 'did_not_apply', 'cannot_tell')
USE_LABEL_TEXT = dict(in_line='acted in line with it', against='acted against it', found_again='found it again',
    did_not_apply='did not apply', cannot_tell='cannot tell')
#: The answers that say the fact mattered to what the player did; each must cite a frame.
APPLIED = ('in_line', 'against', 'found_again')
#: Whether the frames show the fact still holding.
HOLDS = ('held', 'stale_or_false', 'cannot_tell')
#: How the fact reached the player: its article's lead was delivered, the player read it through a link or a
#: search, it was only on the index, or it was withheld (the benefit measure).
ROUTES = ('lead', 'read', 'index', 'withheld')
#: The measure gate's frozen answers (docs/design/memory-screen-protocol.md#the-measure), for the anchor check only.
ANCHOR_LABELS = ('straight', 'missed', 'not_engaged', 'cannot_tell')
ANCHOR_TOUCHED = ('straight', 'missed')
ENVELOPE_FIELDS = frozenset({'schema', 'kind', 'source', 'confidence', 'payload'})
_SHA256 = re.compile('[0-9a-f]{64}')


def _common(event: object, names: Sequence[str], labels: Sequence[str], citing: Sequence[str]) -> None:
    """The shared rules: named strings, a closed label, distinct cited frames and the packet's hash."""
    for name in (*names, 'judge', 'model', 'packet'):
        value = getattr(event, name)
        if not isinstance(value, str) or not value.strip():
            raise EvaluationError(f'judge event: {name} must be a non-empty string')
    if event.label not in labels:
        raise EvaluationError(f'judge event: label {event.label!r} is not one of {", ".join(labels)}')
    frames = event.cited_frames
    if not isinstance(frames, tuple) or any(not isinstance(f, str) or not f for f in frames) \
            or len(set(frames)) != len(frames):
        raise EvaluationError('judge event: cited_frames must be distinct non-empty frame IDs')
    if event.label in citing and not frames:
        raise EvaluationError(f'judge event: a {event.label!r} label must cite at least one frame')
    if not isinstance(event.packet_sha256, str) or _SHA256.fullmatch(event.packet_sha256) is None:
        raise EvaluationError('judge event: packet_sha256 must be a lowercase SHA-256')


@dataclass(frozen=True)
class FactUseVerdict:
    """One judge's label for one fact over one window. `cited_frames` are source IDs; `packet` and `packet_sha256`
    name the packet the judge was given, so the verdict can be traced to its input."""

    kind: ClassVar[str] = FACT_USE
    window: str
    fact: str
    route: str
    label: str
    holds: str
    cited_frames: tuple[str, ...]
    judge: str
    model: str
    packet: str
    packet_sha256: str

    def __post_init__(self) -> None:
        _common(self, ('window', 'fact'), USE_LABELS, APPLIED)
        if self.route not in ROUTES:
            raise EvaluationError(f'judge event: route {self.route!r} is not one of {", ".join(ROUTES)}')
        if self.holds not in HOLDS:
            raise EvaluationError(f'judge event: holds {self.holds!r} is not one of {", ".join(HOLDS)}')

    @property
    def pair(self) -> tuple[str, str]:
        return self.window, self.fact


@dataclass(frozen=True)
class AnchorVerdict:
    """One judge's label, in the measure gate's frozen words, for one known item over one of the gate's stretches."""

    kind: ClassVar[str] = ANCHOR
    start: str
    item: str
    label: str
    cited_frames: tuple[str, ...]
    judge: str
    model: str
    packet: str
    packet_sha256: str

    def __post_init__(self) -> None:
        _common(self, ('start', 'item'), ANCHOR_LABELS, ANCHOR_TOUCHED)

    @property
    def pair(self) -> tuple[str, str]:
        return self.start, self.item


STUCK, RETRY, MILESTONE, CLAIM = 'stuck_verdict', 'retry_verdict', 'milestone_verdict', 'claim_verdict'
STUCK_LABELS = ('stuck', 'looping', 'progressing', 'cannot_tell')
RETRY_LABELS = ('repeated_failed_approach', 'no_repeat', 'cannot_tell')
MILESTONE_LABELS = ('reached', 'not_reached', 'cannot_tell')
CLAIM_LABELS = ('supported', 'unsupported', 'not_a_success_claim', 'cannot_tell')


@dataclass(frozen=True)
class StuckVerdict:
    """One actor's window: no observable progress, a returning cycle, progress, or insufficient evidence."""

    kind: ClassVar[str] = STUCK
    window: str
    label: str
    cited_frames: tuple[str, ...]
    judge: str
    model: str
    packet: str
    packet_sha256: str

    def __post_init__(self) -> None:
        _common(self, ('window',), STUCK_LABELS, ('stuck', 'looping'))

    @property
    def pair(self) -> tuple[str, str]:
        return self.window, self.kind


@dataclass(frozen=True)
class RetryVerdict(StuckVerdict):
    """A failed approach followed by the same approach without an observable revision."""

    kind: ClassVar[str] = RETRY

    def __post_init__(self) -> None:
        _common(self, ('window',), RETRY_LABELS, ('repeated_failed_approach',))
        if self.label == 'repeated_failed_approach' and len(self.cited_frames) < 2:
            raise EvaluationError('judge event: repeated_failed_approach must cite at least two frames')


@dataclass(frozen=True)
class MilestoneVerdict:
    """One frozen milestone in one shuffled frame packet."""

    kind: ClassVar[str] = MILESTONE
    milestone: str
    label: str
    cited_frames: tuple[str, ...]
    judge: str
    model: str
    packet: str
    packet_sha256: str

    def __post_init__(self) -> None:
        _common(self, ('milestone',), MILESTONE_LABELS, ('reached',))

    @property
    def pair(self) -> tuple[str, str]:
        return self.packet, self.milestone


@dataclass(frozen=True)
class ClaimVerdict(StuckVerdict):
    """One candidate sentence, classified as a success claim and checked against frames."""

    kind: ClassVar[str] = CLAIM
    claim: str

    def __post_init__(self) -> None:
        _common(self, ('window', 'claim'), CLAIM_LABELS, ('supported', 'unsupported'))

    @property
    def pair(self) -> tuple[str, str]:
        return self.window, self.claim


JudgeEvent = FactUseVerdict | AnchorVerdict | StuckVerdict | RetryVerdict | MilestoneVerdict | ClaimVerdict
KINDS: dict[str, type] = {event.kind: event for event in
    (FactUseVerdict, AnchorVerdict, StuckVerdict, RetryVerdict, MilestoneVerdict, ClaimVerdict)}


def envelope(event: JudgeEvent) -> dict:
    payload = {field.name: getattr(event, field.name) for field in fields(event)}
    return dict(schema=SCHEMA, kind=event.kind, source=SOURCE, confidence=None,
        payload=dict(payload, cited_frames=list(event.cited_frames)))


def parse(value: object, where: str = 'judge event') -> JudgeEvent:
    """One envelope as a judge event of its kind; anything else is an `EvaluationError` naming `where`."""
    if not isinstance(value, dict) or set(value) != ENVELOPE_FIELDS:
        raise EvaluationError(f'{where}: a judge event has exactly the fields {", ".join(sorted(ENVELOPE_FIELDS))}')
    if value['schema'] != SCHEMA or value['source'] != SOURCE or value['kind'] not in KINDS:
        raise EvaluationError(f'{where}: expected schema {SCHEMA}, a kind of {", ".join(KINDS)} and source {SOURCE}; '
            'no other version is read')
    if value['confidence'] is not None:
        raise EvaluationError(f'{where}: a judge event carries no confidence; agreement is measured over the file')
    kind, payload = KINDS[value['kind']], value['payload']
    names = {field.name for field in fields(kind)}
    if not isinstance(payload, dict) or set(payload) != names or not isinstance(payload['cited_frames'], list):
        raise EvaluationError(f'{where}: the payload has exactly the fields {", ".join(sorted(names))}')
    try:
        return kind(**dict(payload, cited_frames=tuple(payload['cited_frames'])))
    except (EvaluationError, TypeError) as exc:
        raise EvaluationError(f'{where}: {exc}') from exc


def check(events: Sequence[JudgeEvent], where: str, kind: str | None = None) -> None:
    """One file holds one judge and one kind (`kind`, when given), and each pair once."""
    if len({event.judge for event in events}) > 1:
        raise EvaluationError(f'{where}: events of more than one judge')
    if len({event.model for event in events}) > 1:
        raise EvaluationError(f'{where}: events of more than one model')
    kinds = {event.kind for event in events}
    if len(kinds) > 1 or kind is not None and kinds - {kind}:
        raise EvaluationError(f'{where}: a file holds events of one kind' + (f', here {kind}' if kind else ''))
    seen: set[tuple[str, str]] = set()
    for event in events:
        if event.pair in seen:
            raise EvaluationError(f'{where}: {" / ".join(event.pair)} is answered more than once')
        seen.add(event.pair)


def read_events(path: Path, kind: str | None = None) -> list[JudgeEvent]:
    events = [parse(value, f'{path}:{number}') for number, value in enumerate(read_json_lines(Path(path)), 1)]
    check(events, str(path), kind)
    return events


def write_events(path: Path, events: Iterable[JudgeEvent]) -> None:
    """Write one judge's events once: an existing file is never replaced."""
    events = list(events)
    check(events, str(path))
    with Path(path).open('x', encoding='utf-8') as stream:
        for event in events:
            stream.write(dumps(envelope(event)) + '\n')
