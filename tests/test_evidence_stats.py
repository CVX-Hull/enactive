"""Shared evidence statistics: definitions fixed by hand-computed values, plus the rejected inputs."""
from fractions import Fraction
import math

import pytest

from tools.evidence_stats import (beyond, cluster_bootstrap, cohen_kappa, gwet_ac1, percentile_rank, positive_agreement, quantile,
                                  quantile_linear, ratio, summary)


def test_nearest_rank_quantile_is_the_value_at_floor_q_n():
    values = list(range(1, 21))
    assert quantile(values, .5) == 11 and quantile(values, .95) == 20 and quantile(values, 0) == 1
    # For n <= 20 the p95 is the maximum, by definition.
    assert quantile([3, 1, 2], .95) == 3
    assert quantile([], .5) is None
    assert summary([4, 1, 9]) == dict(n=3, median=4, p95=9, max=9)
    assert summary([]) == dict(n=0, median=None, p95=None, max=None)


def test_linear_quantile_interpolates_like_numpy_and_rejects_bad_input():
    assert quantile_linear([1, 2, 3, 4], .5) == 2.5
    assert quantile_linear([0, 10], .25) == 2.5
    assert quantile_linear([7], .9) == 7
    with pytest.raises(ValueError):
        quantile_linear([], .5)
    with pytest.raises(ValueError):
        quantile_linear([1, 2], 1.5)


def test_pooled_ratio_is_none_without_a_denominator():
    clusters = [dict(a=1, b=2), dict(a=3, b=2)]
    assert ratio(clusters, lambda c: c['a'], lambda c: c['b']) == 1.0
    assert ratio(clusters, lambda c: c['a'], lambda c: 0) is None


def test_cluster_bootstrap_resamples_whole_clusters_and_is_reproducible():
    clusters = [dict(k=1, n=1)] * 5 + [dict(k=0, n=1)] * 5
    statistic = lambda xs: ratio(xs, lambda c: c['k'], lambda c: c['n'])
    first = cluster_bootstrap(clusters, statistic, seed=7, resamples=500)
    assert first == cluster_bootstrap(clusters, statistic, seed=7, resamples=500)
    mean = lambda xs: sum(xs) / len(xs)
    values = [1.0, 2.0, 4.0, 8.0, 16.0, 3.0]
    assert cluster_bootstrap(values, mean, seed=1, resamples=300) != cluster_bootstrap(values, mean, seed=2, resamples=300)
    low, high = first['interval']
    assert 0 <= low < .5 < high <= 1 and (first['clusters'], first['resamples'], first['defined_resamples']) == (10, 500, 500)
    # Identical clusters have no sampling variance.
    assert cluster_bootstrap([dict(k=1, n=1)] * 4, statistic, seed=1, resamples=50)['interval'] == [1.0, 1.0]
    # Fewer than two clusters have nothing to resample; a statistic that is never defined gives no interval but says so.
    for few in ([], [1]):
        assert cluster_bootstrap(few, mean, seed=1, resamples=50)['interval'] is None
    undefined = cluster_bootstrap([1, 2], lambda xs: None, seed=1, resamples=50)
    assert undefined['interval'] is None and undefined['defined_resamples'] == 0
    half = iter(range(1000))
    sometimes = cluster_bootstrap([1, 2], lambda xs: next(half) if next(half) % 2 else None, seed=1, resamples=40)
    assert 0 < sometimes['defined_resamples'] < 40
    for bad in (dict(resamples=0), dict(resamples=1.5), dict(resamples=10, level=1.0)):
        with pytest.raises(ValueError):
            cluster_bootstrap(clusters, statistic, seed=1, **dict(dict(resamples=10), **bad))


def test_interval_indices_are_exact_not_float_products():
    # (1 - .9) / 2 is 0.04999999999999999 in floats, whose product with 2000 truncates to 99; the exact decimal gives 100.
    assert int(((1 - .9) / 2) * 2000) == 99
    counter = iter(range(2000))
    boot = cluster_bootstrap([1, 2], lambda xs: next(counter), seed=1, resamples=2000, level=.9)
    assert boot['interval'] == [100, 1900]
    assert quantile(list(range(2000)), .95) == 1900 and quantile(list(range(2000)), Fraction(1, 20)) == 100
    # Upper nearest-rank: the index is floor(q*n), unlike the lower rank ceil(q*n)-1 that host_analysis uses.
    assert quantile([10, 20, 30, 40], .5) == 30 and quantile([10, 20, 30, 40], .25) == 20


def test_percentile_rank_and_tail_tests():
    reference = list(range(1, 101))
    assert percentile_rank(50, reference) == .5
    assert beyond(100, reference) and not beyond(90, reference)
    assert beyond(1, reference, lower_tail=True) and not beyond(50, reference, lower_tail=True)
    with pytest.raises(ValueError):
        percentile_rank(1, [])


def test_cohen_kappa_matches_the_hand_computed_value():
    categories = ('x', 'y')
    first = ['x', 'x', 'y', 'y', 'x', 'y', 'x', 'y']
    second = ['x', 'y', 'y', 'y', 'x', 'x', 'x', 'y']
    # observed 6/8; each rater says x 4 times of 8: expected .5; kappa = (.75 - .5) / .5
    assert cohen_kappa(first, second, categories) == pytest.approx(.5)
    assert cohen_kappa(first, first, categories) == 1.0
    assert cohen_kappa(['x'] * 3, ['x'] * 3, categories) == 1.0   # chance agreement already certain
    assert cohen_kappa([], [], categories) is None


def test_gwet_ac1_resists_the_prevalence_paradox_that_depresses_kappa():
    categories = ('x', 'y')
    first = ['x'] * 18 + ['x', 'y']
    second = ['x'] * 18 + ['y', 'x']
    kappa, ac1 = cohen_kappa(first, second, categories), gwet_ac1(first, second, categories)
    # 18 of 20 agree; each rater says x 19 times: kappa = (.9 - .905) / .095, AC1 = (.9 - .095) / (1 - .095).
    assert kappa == pytest.approx(-.005 / .095) and ac1 == pytest.approx(.805 / .905)
    assert gwet_ac1(first, first, categories) == 1.0
    assert gwet_ac1([], [], categories) is None and gwet_ac1(['x'], ['x'], ('x',)) is None


def test_positive_agreement_is_dice_for_one_category():
    first, second = ['a', 'a', 'b', 'a'], ['a', 'b', 'b', 'a']
    assert positive_agreement(first, second, 'a') == pytest.approx(2 * 2 / (2 * 2 + 1))
    assert positive_agreement(first, second, 'c') is None


def test_raters_must_label_the_same_items_from_the_closed_list():
    with pytest.raises(ValueError, match='same items'):
        cohen_kappa(['x'], ['x', 'y'], ('x', 'y'))
    with pytest.raises(ValueError, match='closed category list'):
        cohen_kappa(['x', 'z'], ['x', 'y'], ('x', 'y'))
    with pytest.raises(ValueError, match='same items'):
        positive_agreement(['x'], [], 'x')
    assert not math.isnan(cohen_kappa(['x', 'y'], ['y', 'x'], ('x', 'y')))
