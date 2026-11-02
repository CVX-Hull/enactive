"""Game-agnostic statistics for claim-deciding analyses (S-EVIDENCE): standard library only.

Shared by `tools/level_stage_analysis.py`, `tools/intent_audit.py` and `tools/sequence_lenses.py`. Every function
is a pure function of its arguments; seeds and resample counts are arguments, never defaults that a result could
silently depend on. The independent unit is the cluster (a run, or a lineage when runs share memory): resample
whole clusters, never steps or frames.

Definitions (each is an executable statement of what a reported number means):
- `quantile` is nearest-rank: the value at index floor(q*n) of the sorted list, so for n <= 20 the p95 is the maximum.
- `quantile_linear` interpolates linearly between order statistics (the convention of `numpy.quantile`).
- `cluster_bootstrap` is a percentile interval of `statistic` over resamples of whole clusters drawn with
  replacement; a resample whose statistic is None is dropped.
- `cohen_kappa` is chance-corrected agreement for two raters over a closed category list; `gwet_ac1` is the
  prevalence-robust alternative (Gwet 2008); `positive_agreement` is 2a/(2a+b+c) for one category.
"""
from __future__ import annotations

from collections import Counter
import random
from typing import Callable, Hashable, Sequence


def quantile(values: Sequence[float], q: float) -> float | None:
    """Nearest-rank quantile: the value at index floor(q*n) of the sorted list; None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def quantile_linear(values: Sequence[float], q: float) -> float:
    """Quantile with linear interpolation between order statistics (numpy's default method)."""
    if not values:
        raise ValueError('quantile of no values')
    if not 0 <= q <= 1:
        raise ValueError('q must lie in [0, 1]')
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summary(values: Sequence[float]) -> dict:
    """n, median, p95 (nearest-rank) and max; None for each when there are no values."""
    return dict(n=len(values), median=quantile(values, .5), p95=quantile(values, .95), max=max(values, default=None))


def ratio(clusters: Sequence[dict], numerator: Callable[[dict], float], denominator: Callable[[dict], float]) -> float | None:
    """Pooled ratio of two per-cluster counts, or None when the pooled denominator is zero."""
    n = sum(denominator(c) for c in clusters)
    return sum(numerator(c) for c in clusters) / n if n else None


def cluster_bootstrap(clusters: Sequence, statistic: Callable[[Sequence], float | None], *, seed: int | str,
                      resamples: int, level: float = .95) -> list[float] | None:
    """Percentile interval [low, high] of `statistic` over `resamples` resamples of whole clusters.

    `seed` seeds one `random.Random`, so the interval is reproducible from its record. None when there are no
    clusters or no resample has a statistic.
    """
    if not 0 < level < 1 or type(resamples) is not int or resamples < 1:
        raise ValueError('level must be in (0, 1) and resamples a positive integer')
    if not clusters:
        return None
    rng, values = random.Random(seed), []
    for _ in range(resamples):
        value = statistic([rng.choice(clusters) for _ in clusters])
        if value is not None:
            values.append(value)
    if not values:
        return None
    tail = (1 - level) / 2
    return [quantile(values, tail), quantile(values, 1 - tail)]


def percentile_rank(value: float, reference: Sequence[float]) -> float:
    """Share of the reference at or below `value`."""
    if not reference:
        raise ValueError('percentile rank against no reference')
    return sum(r <= value for r in reference) / len(reference)


def beyond(value: float, reference: Sequence[float], *, lower_tail: bool = False, tail: float = .05) -> bool:
    """Whether `value` lies beyond the reference's upper (or, with `lower_tail`, lower) `tail` quantile."""
    if lower_tail:
        return value < quantile_linear(reference, tail)
    return value > quantile_linear(reference, 1 - tail)


def _paired(first: Sequence[Hashable], second: Sequence[Hashable], categories: Sequence[Hashable]) -> int:
    if len(first) != len(second):
        raise ValueError('The two raters must label the same items')
    unknown = (set(first) | set(second)) - set(categories)
    if unknown:
        raise ValueError(f'Labels outside the closed category list: {sorted(map(str, unknown))}')
    return len(first)


def cohen_kappa(first: Sequence[Hashable], second: Sequence[Hashable], categories: Sequence[Hashable]) -> float | None:
    """Cohen's kappa; None for no items, 1.0 when chance agreement is already certain (a single used category)."""
    n = _paired(first, second, categories)
    if not n:
        return None
    observed = sum(x == y for x, y in zip(first, second)) / n
    expected = sum((first.count(c) / n) * (second.count(c) / n) for c in categories)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def gwet_ac1(first: Sequence[Hashable], second: Sequence[Hashable], categories: Sequence[Hashable]) -> float | None:
    """Gwet's AC1 for two raters; None for no items or fewer than two categories."""
    n = _paired(first, second, categories)
    if not n or len(categories) < 2:
        return None
    observed = sum(x == y for x, y in zip(first, second)) / n
    pooled = Counter(first) + Counter(second)
    expected = sum((pooled[c] / (2 * n)) * (1 - pooled[c] / (2 * n)) for c in categories) / (len(categories) - 1)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def positive_agreement(first: Sequence[Hashable], second: Sequence[Hashable], category: Hashable) -> float | None:
    """2a/(2a+b+c) for one category: a = both chose it, b + c = exactly one did; None when neither ever did."""
    if len(first) != len(second):
        raise ValueError('The two raters must label the same items')
    both = sum(x == category and y == category for x, y in zip(first, second))
    only = sum((x == category) != (y == category) for x, y in zip(first, second))
    return 2 * both / (2 * both + only) if both + only else None
