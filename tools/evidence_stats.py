"""Game-agnostic statistics for claim-deciding analyses (S-EVIDENCE): standard library only.

Shared by `tools/level_stage_analysis.py`, `tools/intent_audit.py` and `tools/sequence_lenses.py`. Every function
is a pure function of its arguments; seeds and resample counts are arguments, never defaults that a result could
silently depend on. The independent unit is the cluster (a run, or a lineage when runs share memory): resample
whole clusters, never steps or frames.

Definitions (each is an executable statement of what a reported number means):
- `quantile` is **upper nearest-rank, floor(q*n)**: the value at index floor(q*n) of the sorted list (clamped to the
  last), so for n <= 20 the p95 is the maximum. The index is computed exactly from the decimal text of q, never from a
  float product, so q = .95 and n = 2000 give 1900 and a 90% interval's lower index is 100, not 99. This is not
  `tools/host_analysis.distribution`, which takes index ceil(q*n)-1 (the lower nearest-rank); the two differ by one
  order statistic wherever q*n is an integer.
- `quantile_linear` interpolates linearly between order statistics (the convention of `numpy.quantile`).
- `cluster_bootstrap` is a percentile interval of `statistic` over resamples of whole clusters drawn with
  replacement; a resample whose statistic is None is dropped. It reports how many resamples were defined, and gives
  no interval for fewer than two clusters (a single cluster has no sampling variance to resample).
- `cohen_kappa` is chance-corrected agreement for two raters over a closed category list; `gwet_ac1` is the
  prevalence-robust alternative (Gwet 2008); `positive_agreement` is 2a/(2a+b+c) for one category.
- `one_sided_t` summarises per-cluster values (one value per run) with a Student-t interval: the one-sided
  `level` lower and upper bounds `mean -/+ t_crit * sd / sqrt(n)` (t_crit the `level` quantile with n - 1 degrees
  of freedom) and the one-sided p of "mean <= 0" against "mean > 0". A zero spread gives p = 0 for a positive mean and
  1 otherwise, never a division by zero; fewer than two values give no bound. `t_sf` is P(T > t) and `t_quantile`
  its inverse, both computed from the regularised incomplete beta function with the standard library only.
- `wilson_upper` is the Wilson score upper bound of a proportion k / n (two-sided z = 1.959963984540054 by default);
  `holm` is the Holm step-down rejection list for a family of p-values at level alpha.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import math
import random
from typing import Callable, Hashable, Sequence


def _exact(q) -> Fraction:
    """q as the exact decimal it was written as (a float's shortest repr), or the Fraction it already is."""
    return q if isinstance(q, Fraction) else Fraction(repr(float(q)))


def quantile(values: Sequence[float], q: float | Fraction) -> float | None:
    """Upper nearest-rank quantile: the value at index floor(q*n) of the sorted list, clamped; None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.floor(_exact(q) * len(ordered)))]


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
                      resamples: int, level: float = .95) -> dict:
    """Percentile interval of `statistic` over `resamples` resamples of whole clusters.

    Returns `dict(interval, clusters, resamples, defined_resamples)`. `interval` is [low, high], or None when there
    are fewer than two clusters or no resample has a statistic; `defined_resamples` says how many resamples the
    interval rests on, so a reader can judge a statistic that is often undefined. `seed` seeds one `random.Random`,
    so the interval is reproducible from its record, and the caller fixes the cluster order (sort by name).
    """
    if not 0 < level < 1 or type(resamples) is not int or resamples < 1:
        raise ValueError('level must be in (0, 1) and resamples a positive integer')
    result = dict(interval=None, clusters=len(clusters), resamples=resamples, defined_resamples=0)
    if len(clusters) < 2:
        return result
    rng, values = random.Random(seed), []
    for _ in range(resamples):
        value = statistic([rng.choice(clusters) for _ in clusters])
        if value is not None:
            values.append(value)
    result['defined_resamples'] = len(values)
    if values:
        tail = (1 - Fraction(repr(float(level)))) / 2
        result['interval'] = [quantile(values, tail), quantile(values, 1 - tail)]
    return result


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


# ---------------------------------------------------------------- Student-t bounds, Wilson and Holm

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the regularised incomplete beta function (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        for term in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + term * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + term / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return h


def _ibeta(a: float, b: float, x: float) -> float:
    """The regularised incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_sf(t: float, df: float) -> float:
    """P(T > t) for a Student-t variable with `df` degrees of freedom."""
    if df <= 0:
        raise ValueError('degrees of freedom must be positive')
    if math.isinf(t):
        return 0.0 if t > 0 else 1.0
    tail = 0.5 * _ibeta(df / 2, 0.5, df / (df + t * t))
    return tail if t > 0 else 1 - tail


def t_quantile(p: float, df: float) -> float:
    """The t with P(T <= t) = p, by bisection on `t_sf`; p must lie strictly between 0 and 1."""
    if not 0 < p < 1:
        raise ValueError('p must lie strictly between 0 and 1')
    if p == .5:
        return 0.0
    if p < .5:
        return -t_quantile(1 - p, df)
    target, low, high = 1 - p, 0.0, 1.0
    while t_sf(high, df) > target:
        high *= 2
        if high > 1e12:
            raise ValueError('quantile out of range')
    for _ in range(200):
        mid = (low + high) / 2
        low, high = (mid, high) if t_sf(mid, df) > target else (low, mid)
    return (low + high) / 2


def one_sided_t(values: Sequence[float], *, level: float = .95) -> dict | None:
    """Per-cluster values -> mean, spread, one-sided `level` bounds and the one-sided p of "mean <= 0".

    Returns `dict(n, mean, sd, se, df, t, p, lower, upper, t_crit)`, or None for fewer than two values (a single
    cluster has no spread to bound). `lower` and `upper` are each a one-sided bound at `level`, not the ends of
    one two-sided interval. With a zero spread the bounds equal the mean, `t` is +/-inf (0 for a zero mean) and `p`
    is 0 for a positive mean, 1 otherwise.
    """
    if not 0.5 < level < 1:
        raise ValueError('level must lie in (0.5, 1)')
    n = len(values)
    if n < 2:
        return None
    mean = math.fsum(values) / n
    sd = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n - 1))
    se = sd / math.sqrt(n)
    crit = t_quantile(level, n - 1)
    if se == 0:
        t = 0.0 if mean == 0 else math.copysign(math.inf, mean)
        p = 0.0 if mean > 0 else 1.0
    else:
        t = mean / se
        p = t_sf(t, n - 1)
    return dict(n=n, mean=mean, sd=sd, se=se, df=n - 1, t=t, p=p, lower=mean - crit * se, upper=mean + crit * se, t_crit=crit)


def wilson_upper(k: int, n: int, z: float = 1.959963984540054) -> float:
    """Wilson score upper bound of the proportion k / n."""
    if type(k) is not int or type(n) is not int or n < 1 or not 0 <= k <= n:
        raise ValueError('need integers with 0 <= k <= n and n >= 1')
    p = k / n
    return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def holm(pvalues: Sequence[float], alpha: float) -> list[bool]:
    """Holm step-down: whether each hypothesis (in input order) is rejected at familywise level `alpha`."""
    m = len(pvalues)
    rejected = [False] * m
    for rank, i in enumerate(sorted(range(m), key=lambda j: (pvalues[j], j))):
        if pvalues[i] > alpha / (m - rank):
            break
        rejected[i] = True
    return rejected
