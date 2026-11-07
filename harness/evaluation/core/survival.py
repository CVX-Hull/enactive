"""Comparison statistics across runs (docs/contracts/evaluation.md): Kaplan-Meier with
Greenwood intervals, restricted mean survival time, the log-rank test and bootstrap
intervals. Censored runs stay censored. Statistics come from scipy; the restricted
mean is the integral of the Kaplan-Meier step function.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence
import warnings

import numpy as np
from scipy import stats

from .records import EvaluationError, open_readonly, read_metadata, read_metrics


@dataclass(frozen=True)
class Observation:
    """One run's survival time in hours; `died` False means right-censored (alive at stop)."""

    time: float
    died: bool


def _censored(observations: Sequence[Observation]) -> stats.CensoredData:
    return stats.CensoredData(uncensored=[o.time for o in observations if o.died],
        right=[o.time for o in observations if not o.died])


def _clean(values: Sequence[float]) -> list[float | None]:
    return [None if math.isnan(v) else float(v) for v in values]


def kaplan_meier(observations: Sequence[Observation], confidence: float = 0.95) -> dict:
    """Step curve `{times, survival, lower, upper}`: survival is 1 before the first time. The
    interval is scipy's Greenwood-based one and is None where it is undefined."""
    if not observations:
        raise ValueError('Kaplan-Meier needs at least one observation')
    sf = stats.ecdf(_censored(observations)).sf
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        interval = sf.confidence_interval(confidence_level=confidence)
    return dict(times=[float(t) for t in sf.quantiles], survival=[float(p) for p in sf.probabilities],
        lower=_clean(interval.low.probabilities), upper=_clean(interval.high.probabilities), confidence=confidence)


def restricted_mean(times: Sequence[float], survival: Sequence[float], horizon: float) -> float:
    """Integral from 0 to `horizon` of the Kaplan-Meier step function (1 before the first time)."""
    if not horizon > 0:
        raise ValueError('The horizon must be positive')
    total, last_time, level = 0.0, 0.0, 1.0
    for time, value in zip(times, survival):
        if time >= horizon:
            break
        total += level * (time - last_time)
        last_time, level = time, value
    return total + level * (horizon - last_time)


def rmst(observations: Sequence[Observation], horizon: float) -> float:
    """Restricted mean survival time; the horizon must lie inside the observed range."""
    if horizon > max(o.time for o in observations):
        raise ValueError('The horizon lies beyond the longest observed time')
    curve = kaplan_meier(observations)
    return restricted_mean(curve['times'], curve['survival'], horizon)


def logrank(first: Sequence[Observation], second: Sequence[Observation]) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)  # undefined when neither group has an event
        result = stats.logrank(_censored(first), _censored(second))
    return dict(statistic=_clean([result.statistic])[0], pvalue=_clean([result.pvalue])[0])


def bootstrap_rmst(observations: Sequence[Observation], horizon: float, *, resamples: int = 1000,
                   confidence: float = 0.95, seed: int = 0) -> dict:
    """Percentile bootstrap over runs for the restricted mean. Deterministic for a seed."""
    if len(observations) < 2:
        return dict(low=None, high=None, resamples=0, confidence=confidence)
    times = np.array([o.time for o in observations], dtype=float)
    died = np.array([o.died for o in observations], dtype=bool)

    def statistic(sample_times: np.ndarray, sample_died: np.ndarray) -> float:
        sample = [Observation(float(t), bool(d)) for t, d in zip(sample_times, sample_died)]
        curve = kaplan_meier(sample)
        return restricted_mean(curve['times'], curve['survival'], horizon)

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result = stats.bootstrap((times, died), statistic, paired=True, vectorized=False, n_resamples=resamples,
            confidence_level=confidence, method='percentile', rng=np.random.default_rng(seed))
    low, high = _clean([result.confidence_interval.low, result.confidence_interval.high])
    return dict(low=low, high=high, resamples=resamples, confidence=confidence)


def compare(groups: Mapping[str, Sequence[Observation]], horizon: float, *, resamples: int = 1000, seed: int = 0) -> dict:
    """Curves, restricted means with bootstrap intervals per arm, and pairwise log-rank tests."""
    arms = {}
    for label in sorted(groups):
        observations = list(groups[label])
        entry: dict = dict(runs=len(observations), deaths=sum(o.died for o in observations),
            censored=sum(not o.died for o in observations), curve=kaplan_meier(observations))
        if horizon <= max(o.time for o in observations):
            entry['rmst'] = dict(horizon=horizon, value=restricted_mean(entry['curve']['times'], entry['curve']['survival'], horizon),
                **bootstrap_rmst(observations, horizon, resamples=resamples, seed=seed))
        else:
            entry['rmst'] = dict(horizon=horizon, value=None, reason='horizon_beyond_observed_range')
        arms[label] = entry
    labels = sorted(groups)
    tests = {f'{a}|{b}': logrank(groups[a], groups[b]) for i, a in enumerate(labels) for b in labels[i + 1:]}
    return dict(horizon_hours=horizon, arms=arms, logrank=tests)


def record_observation(path: Path) -> tuple[Observation | None, str | None, dict]:
    """(observation, arm label, metadata) from one evaluation record's survival metric."""
    connection = open_readonly(path)
    try:
        metadata = read_metadata(connection)
        metric = read_metrics(connection).get(('survival.game_hours', ''))
    finally:
        connection.close()
    if metric is None:
        raise EvaluationError(f'{path}: record has no survival.game_hours metric')
    value = metric.value
    observation = None if not isinstance(value, dict) else Observation(float(value['hours']), value['outcome'] == 'died')
    return observation, metadata.get('arm'), metadata


def compare_records(paths: Sequence[Path], horizon: float, arms: Mapping[str, str] | None = None, *,
                    resamples: int = 1000, seed: int = 0) -> dict:
    """Group evaluation records by arm (the `--arm` override, else the record's `arm` metadata)."""
    arms = arms or {}
    groups: dict[str, list[Observation]] = {}
    skipped = []
    for path in paths:
        observation, arm, metadata = record_observation(Path(path))
        label = arms.get(str(path), arm)
        if label is None:
            raise EvaluationError(f'{path}: no arm label in the record metadata; name one with --arm RECORD=LABEL')
        if observation is None:
            skipped.append(dict(record=str(path), arm=label, reason='no survival time (no in-play clock reading)'))
            continue
        groups.setdefault(label, []).append(observation)
    if not groups:
        raise EvaluationError('No record has a survival time to compare')
    return dict(compare(groups, horizon, resamples=resamples, seed=seed), skipped=skipped)
