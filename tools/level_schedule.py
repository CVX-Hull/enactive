"""Mechanical wake rules for one actor's subgoal level (ADR-007); no game or semantic trigger.

The driver consults this between passes, so at most one pass is ever in flight. The
same rules replay recorded traces offline, which is why they take counts, not a store.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LevelSchedule:
    inputs_per_pass: int
    budget_fractions: tuple[float, ...]
    allowance: int
    started: bool = False
    last_entries: int = 0
    last_inputs: int = 0
    fired: set[float] = field(default_factory=set)

    def __post_init__(self) -> None:
        if type(self.inputs_per_pass) is not int or not 1 <= self.inputs_per_pass <= 1000:
            raise ValueError('K must be 1..1000 actor inputs')
        if type(self.allowance) is not int or self.allowance < 1:
            raise ValueError('The actor allowance must be a positive attempt count')
        fractions = tuple(self.budget_fractions)
        if (len(fractions) > 8 or any(type(f) is not float or not 0 < f < 1 for f in fractions)
                or list(fractions) != sorted(set(fractions))):
            raise ValueError('Budget fractions are at most 8 increasing values strictly between 0 and 1')

    def due(self, *, entries: int, inputs: int, attempts: int, open_records: int) -> str | None:
        """Return one wake reason and mark it consumed, or None.

        `entries` and `inputs` count the served actor's log and its input operations,
        `attempts` the actor host's charged provider attempts, and `open_records` the
        current Work records. A start pass revalidates open records even before any
        input; every other wake needs log entries the level has not yet been given.
        """
        if not self.started:
            self.started = True
            if open_records:
                return self._launch('start', entries, inputs)
        if entries <= self.last_entries:
            return None
        if inputs - self.last_inputs >= self.inputs_per_pass:
            return self._launch('inputs', entries, inputs)
        crossed = [f for f in self.budget_fractions if f not in self.fired and attempts >= f * self.allowance]
        if crossed:
            # One pass covers every fraction crossed since the last one.
            self.fired.update(crossed)
            return self._launch(f'budget-{crossed[-1]:g}', entries, inputs)
        return None

    def _launch(self, reason: str, entries: int, inputs: int) -> str:
        self.last_entries, self.last_inputs = entries, inputs
        return reason
