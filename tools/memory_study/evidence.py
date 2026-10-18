"""Suite E: synthetic evidence dependence and a finite-model sensitivity envelope.

The assessor generates hidden labels/model parameters. Candidate functions receive
only visible observations and the public nominal/possible models. No game I/O.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random

from tools.memory_study.common import json_bytes, rng

MODELS = tuple((q, rho) for q in (.6, .8, .9) for rho in (0., .75))
TIE = 1e-12


@dataclass(frozen=True)
class Observation:
    origin_id: str
    observed_bit: int


def unique_signs(observations: tuple[Observation, ...]) -> tuple[int, ...]:
    origins: dict[str, int] = {}
    for observation in observations:
        if observation.observed_bit not in (0, 1):
            raise ValueError("observed bit must be binary")
        if (observation.origin_id in origins
                and origins[observation.origin_id] != observation.observed_bit):
            raise ValueError("same origin has conflicting values")
        origins[observation.origin_id] = observation.observed_bit
    return tuple(origins.values())


def posterior(signs: tuple[int, ...], q: float, rho: float) -> float:
    """Exact likelihood for the protocol's common-cause mixture, prior P(h)=.5."""
    if not signs or not all(x in (0, 1) for x in signs):
        raise ValueError("nonempty binary observations required")
    if not 0 < q < 1 or not 0 <= rho <= 1:
        raise ValueError("invalid model")
    n = len(signs)
    ones = sum(signs)
    likelihoods = []
    for h in (0, 1):
        matches = ones if h else n - ones
        common = q if matches == n else (1 - q if matches == 0 else 0)
        likelihoods.append((1 - rho) * q**matches * (1 - q)**(n-matches)
                           + rho * common)
    total = sum(likelihoods)
    if total == 0:
        raise ValueError("observations impossible under model")
    return likelihoods[1] / total


def forecast(observations: tuple[Observation, ...], *, deduplicate: bool) -> float:
    """Public fixed model, not the assessor's true generating parameters."""
    unique = unique_signs(observations)
    signs = unique if deduplicate else tuple(o.observed_bit for o in observations)
    return posterior(signs, .8, 0.)


def envelope(observations: tuple[Observation, ...]) -> tuple[float, float]:
    signs = unique_signs(observations)
    values = [posterior(signs, q, rho) for q, rho in MODELS]
    return min(values), max(values)


def decision(lower: float, upper: float | None = None) -> int | None:
    """Worst-case decision for a range; a point forecast is a singleton range."""
    if upper is None:
        upper = lower
    if not 0 <= lower <= upper <= 1:
        raise ValueError("invalid probability range")
    if lower > .8 + TIE:
        return 1
    if upper < .2 - TIE:
        return 0
    return None


def expected_utility(choice: int | None, true_p: float) -> float:
    if choice is None:
        return 0.
    return 5 * true_p - 4 if choice else 1 - 5 * true_p


def generate(prng: random.Random, *, n: int, q: float,
             rho: float) -> tuple[tuple[Observation, ...], int]:
    """Assessor-only generation. Return observable origins separately from label."""
    h = prng.randrange(2)
    if prng.random() < rho:
        correct = prng.random() < q
        signs = [h if correct else 1 - h] * n
    else:
        signs = [h if prng.random() < q else 1 - h for _ in range(n)]
    return tuple(Observation(f"o{i}", x) for i, x in enumerate(signs)), h


def point_losses(p: float, outcome: int) -> dict[str, float]:
    """Proper scores; clipping is confined to numerical log-loss evaluation."""
    probability = p if outcome else 1 - p
    return {"brier": (p-outcome)**2,
            "log_loss": -math.log(max(1e-12, min(1-1e-12, probability)))}


def run(seeds: tuple[int, ...]) -> list[dict]:
    rows: list[dict] = []
    for seed in seeds:
        prng = rng(seed, "E")
        for q in (.6, .8, .95):
            for rho in (0., .75):
                for n in (1, 4, 12):
                    base, h = generate(prng, n=n, q=q, rho=rho)
                    true_p = posterior(unique_signs(base), q, rho)
                    best = max(0., expected_utility(0, true_p),
                               expected_utility(1, true_p))
                    base_points = {name: forecast(base, deduplicate=dedup)
                                   for name, dedup in (("naive", False), ("dedup", True))}
                    base_envelope = envelope(base)
                    for copies in (1, 4, 16):
                        visible = tuple(o for o in base for _ in range(copies))
                        if len(visible) > 192 or n > 12:
                            raise ValueError("E input budget exceeded")
                        input_size = json_bytes([asdict(o) for o in visible])
                        condition = f"q={q}:rho={rho}:n={n}:copies={copies}"
                        for method in ("naive", "dedup", "envelope"):
                            metrics: dict[str, float | int] = {
                                "episodes": 1, "origins": n, "visible_copies": len(visible),
                                "input_bytes": input_size,
                                "origin_validation_visits": len(visible),
                                "model_in_class": int((q, rho) in MODELS),
                            }
                            if method == "envelope":
                                lo, hi = envelope(visible)
                                chosen = decision(lo, hi)
                                original_choice = decision(*base_envelope)
                                metrics.update({
                                    "lower": lo, "upper": hi, "width": hi-lo,
                                    "contains_true_model_posterior": int(lo-TIE <= true_p <= hi+TIE),
                                    "replay_forecast_change": max(abs(lo-base_envelope[0]),
                                                                  abs(hi-base_envelope[1])),
                                    "model_evaluations": len(MODELS),
                                    "likelihood_signs": n * len(MODELS),
                                    "extra_state_bytes": json_bytes({
                                        "origins": [asdict(o) for o in base],
                                        "posteriors": [posterior(unique_signs(visible), a, b)
                                                       for a, b in MODELS]}),
                                })
                            else:
                                p = forecast(visible, deduplicate=(method == "dedup"))
                                chosen = decision(p)
                                original_choice = decision(base_points[method])
                                metrics.update(point_losses(p, h))
                                metrics.update({
                                    "forecast": p,
                                    "wrong_high_confidence": int((p >= .95 and h == 0)
                                                                 or (p <= .05 and h == 1)),
                                    "replay_forecast_change": abs(p-base_points[method]),
                                    "model_evaluations": 1,
                                    "likelihood_signs": len(visible) if method == "naive" else n,
                                    "extra_state_bytes": json_bytes(
                                        {"zeros": sum(o.observed_bit == 0 for o in visible),
                                         "ones": sum(o.observed_bit == 1 for o in visible)}
                                        if method == "naive" else
                                        {"origins": [asdict(o) for o in base]}),
                                })
                            metrics.update({
                                "replay_decision_change": int(chosen != original_choice),
                                "abstained": int(chosen is None),
                                "realized_utility": 0 if chosen is None else (1 if chosen == h else -4),
                                "expected_regret": max(0., best-expected_utility(chosen, true_p)),
                            })
                            rows.append({"suite": "E", "seed": seed, "condition": condition,
                                         "method": method, "metrics": metrics})
    return rows
