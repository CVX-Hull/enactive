"""Suite D: prequential memory updates, retention and a causal negative control.

Predictors see a domain and selected action, then its outcome only after scoring.
Generating probabilities and phase boundaries belong to the assessor.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass

from tools.memory_study.common import json_bytes, rng
from tools.memory_study.evidence import point_losses

REGIMES = ("drift", "context_irrelevant", "no_drift", "hidden_domain")


@dataclass(frozen=True)
class Feedback:
    domain: str
    action: int
    outcome: int


def probability(phase: int, action: int, regime: str) -> float:
    """Assessor-only conditional generating probability."""
    opposite = phase == 1 or (phase == 2 and regime == "no_drift")
    if regime == "context_irrelevant":
        opposite = False
    return (.2, .8)[action] if opposite else (.8, .2)[action]


def generate(seed: int, regime: str) -> tuple[Feedback, ...]:
    if regime not in REGIMES:
        raise ValueError("unknown D regime")
    # Same logger/outcome uniforms across regimes are paired, not new repetitions.
    prng = rng(seed, "D")
    stream = []
    for step in range(256):
        phase = step // 64
        domain = "A" if phase in (0, 3) else "B"
        action = int(prng.random() < .5)
        outcome = int(prng.random() < probability(phase, action, regime))
        stream.append(Feedback("unknown" if regime == "hidden_domain" else domain,
                               action, outcome))
    return tuple(stream)


class Predictor:
    """Count-based baseline. Optional windows retain only their observed feedback."""

    def __init__(self, method: str):
        if method not in ("fixed", "pooled", "scoped", "window8", "window16", "window32"):
            raise ValueError("unknown predictor")
        self.method = method
        self.window = int(method.removeprefix("window")) if method.startswith("window") else 0
        self.counts: dict[tuple[str, int], tuple[int, int]] = {}
        self.windows: dict[tuple[str, int], deque[int]] = {}
        self.seen = 0

    def _key(self, domain: str, action: int) -> tuple[str, int]:
        if action not in (0, 1):
            raise ValueError("binary action required")
        return ("*" if self.method == "pooled" else domain, action)

    def predict(self, domain: str, action: int) -> tuple[float, int]:
        """Pure prediction and logical feedback/count cells consulted; no update."""
        key = self._key(domain, action)
        if self.method == "fixed":
            return .5, 0
        if self.window:
            values = self.windows.get(key, ())
            return (1 + sum(values)) / (2 + len(values)), len(values)
        successes, trials = self.counts.get(key, (0, 0))
        return (1 + successes) / (2 + trials), 2

    def update(self, domain: str, action: int, outcome: int) -> int:
        """Consume only the chosen action's revealed outcome; return state writes."""
        if outcome not in (0, 1):
            raise ValueError("binary outcome required")
        key = self._key(domain, action)
        self.seen += 1
        if self.method == "fixed":
            return 0
        if self.window:
            values = self.windows.setdefault(key, deque())
            writes = 1
            if len(values) == self.window:
                values.popleft()
                writes += 1
            values.append(outcome)
            return writes
        successes, trials = self.counts.get(key, (0, 0))
        self.counts[key] = (successes + outcome, trials + 1)
        return 2

    def state(self) -> dict:
        """Encoded representation, excluding Python heap and scorer archives."""
        return {"method": self.method,
                "counts": [[*key, *value] for key, value in sorted(self.counts.items())],
                "windows": [[*key, list(value)] for key, value in sorted(self.windows.items())]}


def frozen_probe(predictor: Predictor, regime: str) -> tuple[float, int]:
    before = predictor.state()
    domain = "unknown" if regime == "hidden_domain" else "A"
    errors = []
    visits = 0
    for action in (0, 1):
        p, work = predictor.predict(domain, action)
        errors.append((p - (.8, .2)[action])**2)
        visits += work
    if predictor.state() != before:
        raise ValueError("frozen probe mutated learning state")
    return sum(errors) / 2, visits


def causal_control() -> dict:
    """Identical visible logs cannot identify the value of an untried action."""
    worlds = []
    for untried_reward in (0, 1):
        visible = [{"domain": "one", "action": 0, "outcome": 0} for _ in range(16)]
        worlds.append({"visible": visible, "assessor_policy_value": untried_reward})
    if worlds[0]["visible"] != worlds[1]["visible"]:
        raise ValueError("causal negative control leaked world identity")
    return {"visible_logs_identical": True,
            "possible_policy_values": [x["assessor_policy_value"] for x in worlds],
            "identified_range": [0, 1], "observed_actions": [0]}


def run(seeds: tuple[int, ...]) -> list[dict]:
    rows = []
    for seed in seeds:
        for regime in REGIMES:
            stream = generate(seed, regime)
            input_bytes = json_bytes([asdict(x) for x in stream])
            if len(stream) > 256:
                raise ValueError("D observation budget exceeded")
            for method in ("fixed", "pooled", "scoped", "window8", "window16", "window32"):
                predictor = Predictor(method)
                baseline_probe = None
                for phase in range(4):
                    scores = []
                    visits = writes = 0
                    for feedback in stream[64*phase:64*(phase+1)]:
                        p, work = predictor.predict(feedback.domain, feedback.action)
                        scores.append(point_losses(p, feedback.outcome))
                        visits += work
                        writes += predictor.update(feedback.domain, feedback.action, feedback.outcome)
                    metrics: dict[str, float | int] = {
                        "steps": 64, "observations_seen": predictor.seen,
                        "input_archive_records": len(stream), "input_archive_bytes": input_bytes,
                        "state_bytes": json_bytes(predictor.state()),
                        "count_bins": len(predictor.counts),
                        "window_entries": sum(len(x) for x in predictor.windows.values()),
                        "prediction_cells_consulted": visits, "update_state_writes": writes,
                    }
                    for loss in ("brier", "log_loss"):
                        metrics[loss] = sum(x[loss] for x in scores) / 64
                        metrics[f"first16_{loss}"] = sum(x[loss] for x in scores[:16]) / 16
                        metrics[f"last16_{loss}"] = sum(x[loss] for x in scores[-16:]) / 16
                    rows.append({"suite": "D", "seed": seed,
                                 "condition": f"{regime}:phase={phase+1}",
                                 "method": method, "metrics": metrics})
                    if phase in (0, 2):
                        error, work = frozen_probe(predictor, regime)
                        if phase == 0:
                            baseline_probe = error
                        rows.append({"suite": "D", "seed": seed,
                                     "condition": f"{regime}:probe_after_phase={phase+1}",
                                     "method": method, "metrics": {
                                         "probe_actions": 2, "probability_error": error,
                                         "retention_error_change": error-baseline_probe,
                                         "prediction_cells_consulted": work,
                                         "state_bytes": json_bytes(predictor.state()),
                                     }})
    return rows
