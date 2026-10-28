"""Pure arithmetic over adapter-projected time, without input authority.

Bindings own units, visibility, source integrity and session identity. Seconds
are projected explicitly; raw game counters never acquire a universal meaning.
"""
from __future__ import annotations
from dataclasses import dataclass
from .contracts import ContractError

MAX_CONTINUITY_LINKS = 16
MAX_TIMELINE_SEGMENTS = 17


@dataclass(frozen=True)
class TimePoint:
    source_id: str
    session: str
    revision: int
    seconds: int

    def __post_init__(self):
        if any(type(value) is not str or not value for value in (self.source_id, self.session)):
            raise ContractError("Observed time requires exact source and session identities")
        if type(self.revision) is not int or self.revision < 0 or type(self.seconds) is not int:
            raise ContractError("Observed time requires an ordered revision and projected integer seconds")


@dataclass(frozen=True)
class TimeContinuity:
    """Exact adjacent endpoints already authenticated by the caller's binding."""
    before: TimePoint
    after: TimePoint


@dataclass(frozen=True)
class Timeline:
    elapsed_seconds: int
    segments: tuple[tuple[TimePoint, TimePoint], ...]


def compose_timeline(points: tuple[TimePoint, ...], links: tuple[TimeContinuity, ...]) -> Timeline | None:
    """Compose session deltas, never infer gap time across a reload/counter reset."""
    if type(points) is not tuple or type(links) is not tuple or len(links) > MAX_CONTINUITY_LINKS:
        raise ContractError("Timeline requires bounded immutable points and links")
    for point in points:
        if type(point) is not TimePoint:
            raise ContractError("Timeline requires projected TimePoint values")
        point.__post_init__()
    for link in links:
        if type(link) is not TimeContinuity or type(link.before) is not TimePoint or type(link.after) is not TimePoint:
            raise ContractError("Timeline requires exact projected continuity endpoints")
    segments = []
    sessions = set()
    source_ids = set()
    for point in points:
        if point.source_id in source_ids:
            raise ContractError("Observed timeline source identities must be unique")
        source_ids.add(point.source_id)
        if not segments or point.session != segments[-1][0].session:
            if point.session in sessions or len(segments) >= MAX_TIMELINE_SEGMENTS:
                raise ContractError("Timeline returned to a prior session or exceeded its segment bound")
            sessions.add(point.session)
            segments.append((point, point))
            continue
        first, previous = segments[-1]
        if point.revision < previous.revision or point.seconds < previous.seconds:
            raise ContractError("Observed session revision or projected time regressed")
        if point.revision == previous.revision and point.seconds != previous.seconds:
            raise ContractError("Same observed revision has contradictory projected time")
        segments[-1] = (first, point)
    if len(links) != max(0, len(segments) - 1):
        raise ContractError("Every adjacent session requires exactly one ordered continuity link")
    if not segments:
        return None
    for index, link in enumerate(links):
        if (link.before, link.after) != (segments[index][1], segments[index + 1][0]):
            raise ContractError("Continuity must equal exact canonical segment endpoints")
    return Timeline(sum(last.seconds - first.seconds for first, last in segments), tuple(segments))
