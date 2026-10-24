"""Bounded game-time arithmetic over retained normal-play session spans.

Continuity links are caller-authenticated lifecycle data. This module proves no
character/place identity, imports no coordinates and grants no input authority.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import ContractError, EvidenceRef
from .evidence import EvidenceError, EvidenceStore

MAX_CONTINUITY_LINKS = 16
MAX_TIMELINE_SEGMENTS = 17


def _reference(reference: EvidenceRef) -> None:
    if type(reference) is not EvidenceRef:
        raise ContractError("Timeline endpoints require typed EvidenceRef values")
    reference.__post_init__()


@dataclass(frozen=True)
class SessionContinuity:
    """Exact endpoints supplied by the caller's authenticated lifecycle adapter."""
    before: EvidenceRef
    after: EvidenceRef

    def __post_init__(self) -> None:
        _reference(self.before)
        _reference(self.after)


@dataclass(frozen=True)
class GameTimeline:
    """Observed game seconds and separate chronological coordinate scopes."""
    elapsed_seconds: int
    first_normal: EvidenceRef
    latest_normal: EvidenceRef
    segments: tuple[tuple[EvidenceRef, EvidenceRef], ...]
    coordinate_epoch: int

    def __post_init__(self) -> None:
        if type(self.elapsed_seconds) is not int or self.elapsed_seconds < 0:
            raise ContractError("Elapsed game seconds require a nonnegative integer")
        if type(self.coordinate_epoch) is not int:
            raise ContractError("Coordinate epoch requires an integer")
        if type(self.segments) is not tuple or not 1 <= len(self.segments) <= MAX_TIMELINE_SEGMENTS:
            raise ContractError("Timeline requires one through seventeen immutable segments")
        for segment in self.segments:
            if type(segment) is not tuple or len(segment) != 2:
                raise ContractError("Timeline segments require immutable endpoint pairs")
            for reference in segment:
                _reference(reference)
                if reference.boundary_kind != "normal_play":
                    raise ContractError("Timeline endpoints require normal-play game time")
        _reference(self.first_normal)
        _reference(self.latest_normal)
        if (self.coordinate_epoch != len(self.segments) - 1
                or self.first_normal != self.segments[0][0]
                or self.latest_normal != self.segments[-1][1]):
            raise ContractError("Timeline anchors and epoch must match its chronological segments")


def game_timeline(store: EvidenceStore, links: tuple[SessionContinuity, ...]) -> GameTimeline | None:
    """Compose exact normal-session spans without reanchoring missing continuity.

The archive's insertion order defines chronology, including equal-turn captures.
Historical source verification never promotes current evidence or restores a
lease. The caller must serialize archive mutation and authenticate lifecycle
identity, process ownership and Pause precedence before supplying links.
"""
    if not isinstance(store, EvidenceStore):
        raise ContractError("Timeline requires an EvidenceStore")
    if type(links) is not tuple or len(links) > MAX_CONTINUITY_LINKS:
        raise ContractError("Timeline requires an immutable tuple of at most sixteen links")
    for link in links:
        if type(link) is not SessionContinuity:
            raise ContractError("Timeline links require typed SessionContinuity values")
        _reference(link.before)
        _reference(link.after)

    segments: list[tuple[EvidenceRef, EvidenceRef]] = []
    sessions: set[str] = set()
    for reference in store.historical_references:
        if reference.boundary_kind != "normal_play":
            continue
        if not segments or reference.session != segments[-1][0].session:
            if reference.session in sessions:
                raise EvidenceError("A normal session returned after another normal session")
            if len(segments) >= MAX_TIMELINE_SEGMENTS:
                raise EvidenceError("Timeline exceeds seventeen normal-session segments")
            sessions.add(reference.session)
            segments.append((reference, reference))
            continue
        first, previous = segments[-1]
        if reference.revision < previous.revision or reference.turn < previous.turn:
            raise EvidenceError("Normal-session revision or game time regressed")
        if reference.revision == previous.revision and reference.turn != previous.turn:
            raise EvidenceError("Normal-session game times contradict the same revision")
        segments[-1] = (first, reference)

    if len(links) != max(0, len(segments) - 1):
        raise EvidenceError("Every adjacent normal session requires exactly one ordered continuity link")
    if not segments:
        return None

    for index, link in enumerate(links):
        before, after = segments[index][1], segments[index + 1][0]
        if link.before != before or link.after != after:
            raise EvidenceError("Continuity link must equal the exact canonical segment endpoints")
        if before.observation_id == after.observation_id or before.turn != after.turn:
            raise EvidenceError("Reload continuity requires distinct normal endpoints at exactly the same turn")

    elapsed_seconds = 0
    for first, last in segments:
        # observation(), unlike byte-only verify(), rejects sticky disputes. Use
        # canonical archive values even when a link supplied equal copied values.
        store.observation(first)
        if last != first:
            store.observation(last)
        elapsed_seconds += last.turn - first.turn
    return GameTimeline(elapsed_seconds, segments[0][0], segments[-1][1], tuple(segments), len(segments) - 1)
