"""`judge`-source events: one model judge's answer to one closed question (docs/contracts/evaluation.md, #386).

A judge event uses the contract's event envelope (`kind`, `source`, `confidence`, `payload`). It is kept in a
`judge-events/1` JSON Lines file and never in an `evaluation-record/1` store: `records.EVENT_SOURCES` does not
list `judge`, so a record refuses one, and the viewer, which reads records only, cannot serve one. This module
validates and reads or writes that file. It reads no frame and calls no model; it is game-neutral.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import re

from .records import EvaluationError, dumps
from .sources import read_json_lines

SCHEMA = 'judge-events/1'
SOURCE = 'judge'
KIND = 'known_item_verdict'
#: The closed answers, as docs/design/memory-screen-protocol.md#the-measure defines them.
LABELS = ('straight', 'missed', 'not_engaged', 'cannot_tell')
#: The answers that say the play engaged the item; each must cite a frame.
TOUCHED = ('straight', 'missed')
ENVELOPE_FIELDS = frozenset({'schema', 'kind', 'source', 'confidence', 'payload'})
PAYLOAD_FIELDS = frozenset({'start', 'item', 'label', 'cited_frames', 'judge', 'model', 'packet', 'packet_sha256'})
_SHA256 = re.compile('[0-9a-f]{64}')


@dataclass(frozen=True)
class JudgeEvent:
    """One judge's label for one known item over one start (a stretch of play). `cited_frames` are source IDs;
    `packet` and `packet_sha256` name the packet the judge was given, so the verdict can be traced to its input."""

    start: str
    item: str
    label: str
    cited_frames: tuple[str, ...]
    judge: str
    model: str
    packet: str
    packet_sha256: str

    def __post_init__(self) -> None:
        for name in ('start', 'item', 'judge', 'model', 'packet'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise EvaluationError(f'judge event: {name} must be a non-empty string')
        if self.label not in LABELS:
            raise EvaluationError(f'judge event: label {self.label!r} is not one of {", ".join(LABELS)}')
        frames = self.cited_frames
        if not isinstance(frames, tuple) or any(not isinstance(f, str) or not f for f in frames) \
                or len(set(frames)) != len(frames):
            raise EvaluationError('judge event: cited_frames must be distinct non-empty frame IDs')
        if self.label in TOUCHED and not frames:
            raise EvaluationError(f'judge event: a {self.label!r} label must cite at least one frame')
        if not isinstance(self.packet_sha256, str) or _SHA256.fullmatch(self.packet_sha256) is None:
            raise EvaluationError('judge event: packet_sha256 must be a lowercase SHA-256')

    @property
    def pair(self) -> tuple[str, str]:
        return self.start, self.item

    def envelope(self) -> dict:
        return dict(schema=SCHEMA, kind=KIND, source=SOURCE, confidence=None, payload=dict(start=self.start,
            item=self.item, label=self.label, cited_frames=list(self.cited_frames), judge=self.judge, model=self.model,
            packet=self.packet, packet_sha256=self.packet_sha256))


def parse(value: object, where: str = 'judge event') -> JudgeEvent:
    """One envelope as a `JudgeEvent`; anything else is an `EvaluationError` naming `where`."""
    if not isinstance(value, dict) or set(value) != ENVELOPE_FIELDS:
        raise EvaluationError(f'{where}: a judge event has exactly the fields {", ".join(sorted(ENVELOPE_FIELDS))}')
    if value['schema'] != SCHEMA or value['kind'] != KIND or value['source'] != SOURCE:
        raise EvaluationError(f'{where}: expected schema {SCHEMA}, kind {KIND} and source {SOURCE}')
    if value['confidence'] is not None:
        raise EvaluationError(f'{where}: a judge event carries no confidence; agreement is measured over the file')
    payload = value['payload']
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_FIELDS or not isinstance(payload['cited_frames'], list):
        raise EvaluationError(f'{where}: the payload has exactly the fields {", ".join(sorted(PAYLOAD_FIELDS))}')
    try:
        return JudgeEvent(**dict(payload, cited_frames=tuple(payload['cited_frames'])))
    except (EvaluationError, TypeError) as exc:
        raise EvaluationError(f'{where}: {exc}') from exc


def check(events: Sequence[JudgeEvent], where: str) -> None:
    """One file holds one judge, and each (start, item) pair once."""
    if len({event.judge for event in events}) > 1:
        raise EvaluationError(f'{where}: events of more than one judge')
    seen: set[tuple[str, str]] = set()
    for event in events:
        if event.pair in seen:
            raise EvaluationError(f'{where}: {event.start} / {event.item} is answered more than once')
        seen.add(event.pair)


def read_events(path: Path) -> list[JudgeEvent]:
    events = [parse(value, f'{path}:{number}') for number, value in enumerate(read_json_lines(Path(path)), 1)]
    check(events, str(path))
    return events


def write_events(path: Path, events: Iterable[JudgeEvent]) -> None:
    """Write one judge's events once: an existing file is never replaced."""
    events = list(events)
    check(events, str(path))
    with Path(path).open('x', encoding='utf-8') as stream:
        for event in events:
            stream.write(dumps(event.envelope()) + '\n')
