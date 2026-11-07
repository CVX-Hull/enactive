"""The interface a game binding implements for the evaluation core.

The core imports only this module's types. A binding turns one original frame into
typed, fallible readings and owns its milestone ladder; the core owns storage,
derivation, metrics and statistics (docs/contracts/evaluation.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, Sequence

MODES = ('in_play', 'menu', 'prompt', 'loading', 'dead', 'unknown')
THREAT_BUCKETS = ('none', 'low', 'high', 'lethal')
DEATH_CAUSES = ('combat', 'starvation_thirst', 'environment', 'unknown')
SOURCES = ('harness', 'reader', 'derived', 'player_claim', 'human')


@dataclass(frozen=True)
class Reading:
    """One reader's result for one frame. `abstain` holds a reason and then `value` is None."""

    reader: str
    version: int
    value: object | None
    confidence: float | None
    abstain: str | None = None

    def __post_init__(self) -> None:
        if self.abstain is not None and self.value is not None:
            raise ValueError(f'{self.reader}: an abstaining reading carries no value')
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f'{self.reader}: confidence must be within 0..1')


@dataclass(frozen=True)
class Vital:
    """A bounded quantity that matters for survival, normalised so 1.0 is best."""

    name: str
    scope: str
    value: float
    critical: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f'{self.name}: vital value must be within 0..1')
        if self.scope != 'whole' and not self.scope.startswith('part:'):
            raise ValueError(f'{self.name}: scope must be whole or part:<id>')


@dataclass(frozen=True)
class FrameReading:
    """Everything a binding read from one frame. None means not legible on this frame."""

    mode: str
    game_time: int | None
    identity: str | None
    vitals: tuple[Vital, ...]
    threat: str | None
    threat_count: int | None
    death: bool
    readings: tuple[Reading, ...]

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f'unknown mode {self.mode!r}')
        if self.threat is not None and self.threat not in THREAT_BUCKETS:
            raise ValueError(f'unknown threat bucket {self.threat!r}')


@dataclass(frozen=True)
class Rung:
    """One milestone. `human` rungs are reported as not assessed until confirmed."""

    id: str
    label: str
    evidence: Literal['reader', 'human']


class Binding(Protocol):
    """A game binding. Instances are stateless; every method is a pure function of its inputs."""

    binding_id: str
    binding_version: int
    game_time_unit: str
    long_activity_seconds: int
    max_clock_jump_seconds: int
    map_region: tuple[int, int, int, int] | None
    movement_keys: frozenset[str]
    ladder: tuple[Rung, ...]

    def read_frame(self, png: Path) -> FrameReading:
        """Read one original PNG. Must not raise for an unreadable screen: abstain instead."""
        ...

    def rung_reached(self, rung: Rung, history: Sequence[FrameReading]) -> int | None:
        """Index into `history` where `rung` is first reached, or None (always None for human rungs)."""
        ...
