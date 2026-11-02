"""Mechanical wake rules for one actor's subgoal level (ADR-007 level v4); no game or semantic trigger.

The driver consults this between passes, so at most one pass is ever in flight. The level wakes

* at actor start, to revalidate whatever earlier sessions left (an open subgoal or recalled episodes);
* after every episode settles, whatever its outcome (recorded, abstained, failed or dropped);
* at the budget fractions, but only when something has settled since the last pass (the empty-delta rule).

Wakes that arrive while a pass is in flight coalesce: the next `due` call after the pass sees every settle since the
last launch and returns one reason, so one pass covers them all. The rules take counts, not a store, so they replay
recorded timelines offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LevelSchedule:
    budget_fractions: tuple[float, ...]
    allowance: int
    started: bool = False
    last_settled: int = 0
    fired: set[float] = field(default_factory=set)

    def __post_init__(self) -> None:
        if type(self.allowance) is not int or self.allowance < 1:
            raise ValueError('The actor allowance must be a positive attempt count')
        fractions = tuple(self.budget_fractions)
        if (len(fractions) > 8 or any(type(f) is not float or not 0 < f < 1 for f in fractions)
                or list(fractions) != sorted(set(fractions))):
            raise ValueError('Budget fractions are at most 8 increasing values strictly between 0 and 1')

    def due(self, *, settled: int, attempts: int, carried: int) -> str | None:
        """Return one wake reason and mark it consumed, or None.

        `settled` is the number of episodes the served actor has settled this session, `attempts` the actor host's
        charged provider attempts, and `carried` what earlier sessions left to revalidate (current subgoals plus
        recalled episodes). The start wake may run on an empty delta; every other wake needs a settle the level has
        not yet been given. A fraction crossed since the last pass names the wake, and one pass covers every
        fraction crossed.
        """
        if not self.started:
            self.started = True
            if carried:
                self.last_settled = settled
                return 'start'
        if settled <= self.last_settled:
            return None
        self.last_settled = settled
        crossed = [f for f in self.budget_fractions if f not in self.fired and attempts >= f * self.allowance]
        if crossed:
            self.fired.update(crossed)
            return f'budget-{crossed[-1]:g}'
        return 'settle'
