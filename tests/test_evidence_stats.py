"""Shared evidence statistics: definitions fixed by hand-computed values, plus the rejected inputs."""
from fractions import Fraction
import math

import pytest

from tools.evidence_stats import (beyond, cluster_bootstrap, cohen_kappa, gwet_ac1, holm, one_sided_t, percentile_rank,
                                  positive_agreement, quantile, quantile_linear, ratio, summary, t_quantile, t_sf, wilson_upper)


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


# Student-t reference values: the published one-sided 95% critical values (df 1, 2, 5, 6, 14, 30) and the closed forms of
# the t distribution at 1 and 2 degrees of freedom, which need no table.
T95 = {1: 6.313752, 2: 2.919986, 5: 2.015048, 6: 1.943180, 14: 1.761310, 30: 1.697261}


def test_t_survival_matches_closed_forms_and_the_normal_limit():
    assert t_sf(0, 7) == pytest.approx(.5)
    assert t_sf(1, 1) == pytest.approx(.25)                                    # df 1: .5 - atan(t) / pi
    assert t_sf(1, 2) == pytest.approx(.5 - 1 / (2 * math.sqrt(3)))            # df 2: .5 - t / (2 sqrt(2 + t^2))
    assert t_sf(-1, 2) == pytest.approx(.5 + 1 / (2 * math.sqrt(3)))
    assert t_sf(1.6448536, 10 ** 6) == pytest.approx(.05, abs=1e-5)
    assert t_sf(math.inf, 3) == 0.0 and t_sf(-math.inf, 3) == 1.0
    with pytest.raises(ValueError):
        t_sf(1, 0)


@pytest.mark.parametrize('df, critical', sorted(T95.items()))
def test_t_quantile_reproduces_the_published_critical_values(df, critical):
    assert t_quantile(.95, df) == pytest.approx(critical, abs=2e-6)
    assert t_sf(critical, df) == pytest.approx(.05, abs=1e-6)
    assert t_quantile(.05, df) == pytest.approx(-critical, abs=2e-6)


def test_one_sided_t_bounds_and_p_on_hand_computed_values():
    # 1..7: mean 4, sample sd sqrt(28 / 6), se = sd / sqrt(7) = sqrt(4 / 6); t = 4 / se on 6 degrees of freedom.
    result = one_sided_t([1, 2, 3, 4, 5, 6, 7])
    se = math.sqrt(4 / 6)
    assert (result['n'], result['df'], result['mean']) == (7, 6, 4)
    assert result['sd'] == pytest.approx(math.sqrt(28 / 6)) and result['se'] == pytest.approx(se)
    assert result['t'] == pytest.approx(4 / se)
    assert result['lower'] == pytest.approx(4 - 1.943180 * se, abs=2e-6)
    assert result['upper'] == pytest.approx(4 + 1.943180 * se, abs=2e-6)
    assert result['p'] == pytest.approx(t_sf(4 / se, 6)) and result['p'] < .005
    # A symmetric sample about zero: p is one half and the bounds are symmetric.
    zero = one_sided_t([-2, -1, 0, 1, 2])
    assert zero['mean'] == 0 and zero['p'] == pytest.approx(.5) and zero['lower'] == pytest.approx(-zero['upper'])
    assert zero['upper'] == pytest.approx(2.131847 * math.sqrt(2.5) / math.sqrt(5), abs=2e-6)      # df 4 critical value
    # A stricter level widens the bound.
    assert one_sided_t([1, 2, 3], level=.99)['lower'] < one_sided_t([1, 2, 3])['lower']


def test_one_sided_t_edge_cases_never_divide_by_zero():
    assert one_sided_t([]) is None and one_sided_t([3.0]) is None
    positive, negative, flat = one_sided_t([.5, .5, .5]), one_sided_t([-.5, -.5]), one_sided_t([0, 0, 0])
    assert (positive['p'], positive['lower'], positive['upper'], positive['t']) == (0.0, .5, .5, math.inf)
    assert (negative['p'], negative['upper']) == (1.0, -.5)
    assert (flat['p'], flat['t']) == (1.0, 0.0)
    with pytest.raises(ValueError):
        one_sided_t([1, 2], level=.4)


def test_wilson_upper_matches_hand_computed_bounds():
    z2 = 1.959963984540054 ** 2
    assert wilson_upper(0, 200) == pytest.approx(z2 / (200 + z2))              # k = 0: z^2 / (n + z^2)
    assert wilson_upper(10, 200) == pytest.approx(.08958, abs=1e-4)
    assert wilson_upper(200, 200) == pytest.approx(1.0)
    assert wilson_upper(1, 40) == pytest.approx(0.1286, abs=1e-3)
    for bad in ((-1, 5), (6, 5), (1, 0), (1.5, 5)):
        with pytest.raises(ValueError):
            wilson_upper(*bad)


def test_holm_is_a_step_down_in_input_order():
    assert holm([.01, .04, .03], .05) == [True, False, False]                  # .01 <= .05/3; then .03 > .05/2 stops
    assert holm([.02, .001, .01], .05) == [True, True, True]                   # .001 <= .05/3, .01 <= .05/2, .02 <= .05
    assert holm([.04], .05) == [True] and holm([.06], .05) == [False]
    assert holm([.02, .02, .2], .05) == [False, False, False]                  # smallest .02 > .05/3 stops at once
    assert holm([], .05) == []
