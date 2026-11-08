"""Probes and baseline rates from fact-level annotations (probe-protocol/1; #449).

Annotations are JSON Lines per chunk (one actor's span), in lineage order. This module derives,
without judgment of its own:

- probes: for a fact observed in an earlier chunk and needed in chunk c, "at the boundary into
  c, a query about the fact should surface it"; a probe fails when the fact was not carried;
- carry rates per boundary: cumulative ledger coverage (over every live fact), retention (over
  the live facts the predecessor chunk held) and over needed facts;
- rediscovery counts (re-observing a fact known before a boundary);
- agreement statistics for the inter-rater check.

It is game-neutral: facts are opaque statements. See docs/design/probe-protocol.md.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

CATEGORIES = frozenset({'place', 'resource', 'item', 'hazard', 'procedure', 'self', 'plan', 'other'})
EVENTS = frozenset({'used', 'needed', 'rediscovered', 'acted_without', 'invalidated'})
NEED = frozenset({'needed', 'rediscovered', 'acted_without'})
COST = frozenset({'rediscovered', 'acted_without'})
WHERE = frozenset({'prompt', 'packet', 'report'})


class ProbeError(ValueError):
    """An annotation line does not follow probe-protocol/1."""


@dataclass
class Chunk:
    name: str
    facts: dict[str, dict] = field(default_factory=dict)
    carries: dict[str, bool] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    frames_viewed: int | None = None


@dataclass(frozen=True)
class Probe:
    boundary: str
    fact: str
    statement: str
    carried: bool
    costly: bool

    @property
    def failing(self) -> bool:
        return not self.carried


def parse(name: str, lines: Iterable[dict], boundary: str | None) -> Chunk:
    """Validate one chunk's annotation lines."""
    chunk = Chunk(name)
    ended = False
    for number, line in enumerate(lines, 1):
        where = f'{name}:{number}'
        if not isinstance(line, dict) or ended:
            raise ProbeError(f'{where}: a JSON object before the end line is required')
        kind = line.get('type')
        if kind == 'fact':
            fid = line.get('id')
            if not isinstance(fid, str) or not fid.startswith('F') or not fid[1:].isdigit():
                raise ProbeError(f'{where}: fact id must be F<number>')
            if line.get('category') not in CATEGORIES or not isinstance(line.get('statement'), str):
                raise ProbeError(f'{where}: fact needs a statement and a known category')
            if fid in chunk.facts:
                raise ProbeError(f'{where}: duplicate fact {fid}')
            chunk.facts[fid] = line
        elif kind == 'carry':
            if boundary is None or line.get('boundary') != boundary:
                raise ProbeError(f'{where}: carry line for the wrong boundary {line.get("boundary")!r}')
            if not isinstance(line.get('carried'), bool):
                raise ProbeError(f'{where}: carried must be true or false')
            if line['carried'] and line.get('where') not in WHERE:
                raise ProbeError(f'{where}: a carried fact names where it was carried')
            if not isinstance(line.get('fact'), str):
                raise ProbeError(f'{where}: a carry line names its fact')
            if line['fact'] in chunk.carries:
                raise ProbeError(f'{where}: a second carry line for {line["fact"]}')
            chunk.carries[line['fact']] = line['carried']
        elif kind == 'event':
            if line.get('event') not in EVENTS or not isinstance(line.get('fact'), str):
                raise ProbeError(f'{where}: unknown event')
            chunk.events.append(line)
        elif kind == 'end':
            chunk.frames_viewed = line.get('frames_viewed')
            ended = True
        else:
            raise ProbeError(f'{where}: unknown line type {kind!r}')
    if not ended:
        raise ProbeError(f'{name}: missing end line')
    return chunk


def boundaries(names: Sequence[str]) -> list[str]:
    return [f'{a}>{b}' for a, b in zip(names, names[1:])]


def boundary_kind(boundary: str) -> str:
    """`handoff` inside one admission or run, `admission` between admissions."""
    left, right = boundary.split('>')
    return 'handoff' if left.rsplit('-', 1)[0] == right.rsplit('-', 1)[0] else 'admission'


@dataclass
class Lineage:
    chunks: list[Chunk]

    @classmethod
    def from_lines(cls, ordered: Sequence[tuple[str, Iterable[dict]]]) -> Lineage:
        names = [name for name, _ in ordered]
        into = [None, *boundaries(names)]
        chunks = [parse(name, lines, b) for (name, lines), b in zip(ordered, into)]
        lineage = cls(chunks)
        seen: set[str] = set()
        for index, chunk in enumerate(chunks):
            clash = seen & chunk.facts.keys()
            if clash:
                raise ProbeError(f'{chunk.name}: fact ids reused: {sorted(clash)}')
            for event in chunk.events:
                if event['fact'] not in seen and event['fact'] not in chunk.facts:
                    raise ProbeError(f'{chunk.name}: event for unknown fact {event["fact"]}')
            stray = sorted(set(chunk.carries) - lineage._live_before(index).keys())
            if stray:
                raise ProbeError(f'{chunk.name}: carry lines for facts not live at the boundary: {stray}')
            seen |= chunk.facts.keys()
        return lineage

    def _held_by(self, index: int, live: dict[str, dict]) -> set[str]:
        """Live facts the chunk at `index` held: observed there, received at its own boundary or used there."""
        chunk = self.chunks[index]
        touched = {e['fact'] for e in chunk.events}
        return {f for f in live if f in chunk.facts or chunk.carries.get(f, False) or f in touched}

    def _live_before(self, index: int) -> dict[str, dict]:
        """Facts observed before chunk `index` and not invalidated before it."""
        live: dict[str, dict] = {}
        for chunk in self.chunks[:index]:
            live.update(chunk.facts)
            for event in chunk.events:
                if event['event'] == 'invalidated':
                    live.pop(event['fact'], None)
        return live

    def boundary_rows(self) -> list[dict]:
        rows = []
        for index in range(1, len(self.chunks)):
            chunk = self.chunks[index]
            live = self._live_before(index)
            needed = {e['fact'] for e in chunk.events if e['event'] in NEED and e['fact'] in live}
            held = self._held_by(index - 1, live)
            rows.append(dict(
                boundary=f'{self.chunks[index-1].name}>{chunk.name}',
                kind=boundary_kind(f'{self.chunks[index-1].name}>{chunk.name}'),
                live=len(live), carried=sum(chunk.carries.get(f, False) for f in live),
                unlabelled=sorted(f for f in live if f not in chunk.carries),
                held=len(held), held_carried=sum(chunk.carries.get(f, False) for f in held),
                needed=len(needed), needed_carried=sum(chunk.carries.get(f, False) for f in needed)))
        return rows

    def probes(self) -> list[Probe]:
        out = []
        for index in range(1, len(self.chunks)):
            chunk = self.chunks[index]
            live = self._live_before(index)
            boundary = f'{self.chunks[index-1].name}>{chunk.name}'
            kinds: dict[str, set[str]] = {}
            for event in chunk.events:
                if event['fact'] in live:
                    kinds.setdefault(event['fact'], set()).add(event['event'])
            for fact, events in sorted(kinds.items(), key=lambda kv: int(kv[0][1:])):
                if events & NEED:
                    out.append(Probe(boundary, fact, live[fact]['statement'], chunk.carries.get(fact, False),
                                     bool(events & COST)))
        return out

    def rediscoveries(self) -> int:
        """Re-observations of facts known before the boundary into the chunk."""
        return sum(1 for index in range(1, len(self.chunks)) for e in self.chunks[index].events
                   if e['event'] == 'rediscovered' and e['fact'] in self._live_before(index))

    def frames_viewed(self) -> int:
        return sum(c.frames_viewed or 0 for c in self.chunks)


def rate(numerator: float, denominator: float) -> float | None:
    return None if not denominator else numerator / denominator


BASELINE_SCHEMA = 'probe-baseline/1'


def summary(name: str, lineage: Lineage, game_hours: float) -> dict:
    """The baseline figures for one lineage, all derived from its annotations."""
    rows = lineage.boundary_rows()
    probes = lineage.probes()

    def pooled(kind=None):
        chosen = [r for r in rows if kind is None or r['kind'] == kind]
        return dict(boundaries=len(chosen), live=sum(r['live'] for r in chosen),
                    carried=sum(r['carried'] for r in chosen),
                    carry_rate=rate(sum(r['carried'] for r in chosen), sum(r['live'] for r in chosen)),
                    held=sum(r['held'] for r in chosen), held_carried=sum(r['held_carried'] for r in chosen),
                    retention_rate=rate(sum(r['held_carried'] for r in chosen), sum(r['held'] for r in chosen)),
                    needed=sum(r['needed'] for r in chosen),
                    needed_carried=sum(r['needed_carried'] for r in chosen),
                    needed_carry_rate=rate(sum(r['needed_carried'] for r in chosen), sum(r['needed'] for r in chosen)),
                    unlabelled=sum(len(r['unlabelled']) for r in chosen))

    rediscoveries = lineage.rediscoveries()
    return dict(schema=BASELINE_SCHEMA, lineage=name, chunks=len(lineage.chunks),
                facts=sum(len(c.facts) for c in lineage.chunks), frames_viewed=lineage.frames_viewed(),
                game_hours=game_hours, carry=dict(pooled=pooled(), handoff=pooled('handoff'),
                                                  admission=pooled('admission')),
                probes=dict(total=len(probes), failing=sum(p.failing for p in probes),
                            failing_with_cost=sum(p.failing and p.costly for p in probes)),
                rediscoveries=rediscoveries, rediscoveries_per_game_hour=rate(rediscoveries, game_hours),
                boundaries=rows)


def kappa(pairs: Sequence[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa for two raters' binary labels; None when undefined."""
    n = len(pairs)
    if not n:
        return None
    observed = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def agreement(pairs: Sequence[tuple[bool, bool]]) -> dict:
    return dict(n=len(pairs), percent=rate(sum(a == b for a, b in pairs), len(pairs)), kappa=kappa(pairs))
