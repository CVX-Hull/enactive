"""Sequence lenses on small synthetic fixtures: hand-checkable values, planted effects and rejected inputs."""
import math
import random

import pytest

from tools.sequence_lenses import (WittenBell, chains, cross_power, cross_rqa, first_order_surrogate, lempel_ziv_normalised,
                                   lempel_ziv_phrases, loro_bits, mean_bits, memory_depth, paired_gain, pairwise, plant_into,
                                   plant_self, recurrence_threshold, relabel_noise, rqa, usable, within_power)


def cycle(period, length, offset=0):
    return [(offset + i) % period for i in range(length)]


# ---------------------------------------------------------------- memory depth

def test_witten_bell_is_uniform_when_unseen_and_normalised_when_fitted():
    model = WittenBell(3)
    assert model.probability([], 0) == pytest.approx(1 / 3)
    model.fit([([], 0), ([], 0), ([], 1)])
    # The empty context: counts 0:2, 1:1; two kinds of three observations interpolate with the uniform 1/3.
    assert model.probability([], 0) == pytest.approx((2 + 2 / 3) / 5)
    assert sum(model.probability([], y) for y in range(3)) == pytest.approx(1)
    # An unseen longer context backs off to it unchanged.
    assert model.probability([('never',)], 0) == model.probability([], 0)
    with pytest.raises(ValueError):
        WittenBell(0)


def test_chains_pair_each_transition_with_its_longest_context_first():
    samples = chains([([0, 1, 2], [9, 8, 7])], order=2, with_action=False)
    assert samples == [([(0,)], 1), ([(0, 1), (1,)], 2)]
    with_action = chains([([0, 1], [5, 6])], order=1, with_action=True)
    assert with_action == [([(('a', 5), 0), (('a', 5),)], 1)]
    with pytest.raises(ValueError, match='action'):
        chains([([0, 1, 2], [1])], 1, False)


def test_a_deterministic_cycle_is_predicted_by_order_one_but_not_order_zero():
    runs = {f'r{k}': [(cycle(3, 30, k), [0] * 30)] for k in range(4)}
    m0, m1 = loro_bits(runs, 3, 0), loro_bits(runs, 3, 1)
    assert mean_bits(m1) < .5 * mean_bits(m0)
    gain = paired_gain(m0, m1, seed=1, resamples=200)
    assert gain['gain_bits'] > .5 and gain['ci95'][0] > .5
    # Order two adds nothing to a first-order cycle: the next gain is small, so the depth is one.
    m2 = loro_bits(runs, 3, 2)
    steps = [gain, paired_gain(m1, m2, seed=2, resamples=200)]
    assert memory_depth(steps, tolerance=.05) == 1
    assert memory_depth([dict(ci95=[.2, .3])], tolerance=.05) == 1


def test_a_gain_without_an_interval_cannot_decide_the_depth():
    one = {'only': (4.0, 8)}
    gain = paired_gain(one, {'only': (2.0, 8)}, seed=1, resamples=50)
    assert gain['ci95'] is None and gain['runs'] == 1 and gain['gain_bits'] == pytest.approx(.25)
    with pytest.raises(ValueError, match='without an interval'):
        memory_depth([gain], .05)
    assert paired_gain({'a': (4.0, 8), 'b': (4.0, 8)}, {'a': (2.0, 8), 'b': (2.0, 8)}, seed=1, resamples=50)['defined_resamples'] == 50


def test_scores_are_reproducible_and_reject_unpaired_or_tiny_inputs():
    runs = {'a': [([0, 1, 0, 1], [0] * 4)], 'b': [([1, 0, 1, 0], [0] * 4)]}
    assert loro_bits(runs, 2, 1) == loro_bits(runs, 2, 1)
    with pytest.raises(ValueError, match='two runs'):
        loro_bits({'a': runs['a']}, 2, 1)
    with pytest.raises(ValueError, match='No transitions'):
        mean_bits({'a': (0.0, 0)})
    other = {'a': (1.0, 3), 'c': (1.0, 3)}
    with pytest.raises(ValueError, match='same runs'):
        paired_gain(loro_bits(runs, 2, 1), other, seed=1, resamples=10)


def test_first_order_surrogate_keeps_shape_and_noise_respects_its_rate():
    runs = {'a': [([0, 1, 0, 1, 1], [3] * 5)], 'b': [([1, 1, 0], [4] * 3)]}
    sur = first_order_surrogate(runs, 2, random.Random(1))
    assert [len(s) for s, _ in sur['a']] == [5] and sur['a'][0][0][0] == 0 and sur['a'][0][1] == [3] * 5
    assert sur == first_order_surrogate(runs, 2, random.Random(1))
    assert relabel_noise(runs, 2, 0.0, random.Random(1)) == runs
    flipped = relabel_noise({'a': [([0] * 2000, [0] * 2000)]}, 4, .5, random.Random(2))['a'][0][0]
    # Half are redrawn uniformly over four symbols, so about 3/8 end up different from the original.
    assert .30 < sum(v != 0 for v in flipped) / 2000 < .45
    with pytest.raises(ValueError):
        relabel_noise(runs, 2, 1.5, random.Random(1))


# ---------------------------------------------------------------- repetition

def test_lempel_ziv_counts_phrases_and_ranks_repetition_below_noise():
    assert lempel_ziv_phrases('') == 0 and lempel_ziv_phrases('a') == 1
    assert lempel_ziv_phrases('aaaa') == 2
    assert lempel_ziv_phrases('abab') == 3
    rng = random.Random(3)
    repetitive, noise = cycle(3, 300), [rng.randrange(3) for _ in range(300)]
    assert lempel_ziv_normalised(repetitive) < .5 * lempel_ziv_normalised(noise)
    assert math.isnan(lempel_ziv_normalised(['x']))


# ---------------------------------------------------------------- recurrence

def line_distances(values):
    return pairwise(values, values, lambda a, b: abs(a - b))


def test_rqa_finds_a_replayed_stretch_and_ignores_the_theiler_window():
    # Frames 0..5 are distinct; 6..11 replay them exactly.
    series = [0, 10, 20, 30, 40, 50, 0, 10, 20, 30, 40, 50]
    result = rqa(line_distances(series), 0.5, theiler=2)
    assert result['Lmax'] == 6 and result['DET'] == 1.0
    # A constant series is recurrent everywhere, but the Theiler window removes the near-diagonal band.
    flat = rqa(line_distances([1.0] * 6), 0.0, theiler=2)
    # Twelve recurrent points; the diagonals of length 3 and 2 hold ten of them, the two of length 1 do not count.
    assert flat['Lmax'] == 3 and flat['DET'] == pytest.approx(10 / 12)
    nothing = rqa(line_distances([0, 10, 20, 30, 40]), 0.5, theiler=2)
    assert nothing == dict(DET=0.0, LAM=0.0, Lmax=0)


def test_rqa_laminarity_counts_vertical_runs():
    # Frame 0 recurs with frames 3, 4 and 5 (a vertical line of three in column 0), nothing else does.
    series = [0, 100, 200, 0, 0, 0, 300]
    result = rqa(line_distances(series), 0.5, theiler=2)
    assert result['LAM'] > 0 and result['Lmax'] >= 1


def test_recurrence_threshold_takes_the_quantile_outside_the_window():
    matrix = line_distances([0, 1, 2, 3, 4, 5])
    off = [abs(i - j) for i in range(6) for j in range(6) if abs(i - j) > 2]
    assert recurrence_threshold(matrix, 0.0, 2) == min(off) == 3
    with pytest.raises(ValueError, match='Theiler'):
        recurrence_threshold(line_distances([0, 1]), .1, 2)


def test_cross_rqa_measures_the_longest_replayed_stretch_between_runs():
    donor = [0, 10, 20, 30, 40, 50]
    host = [99, 0, 10, 20, 30, 77, 88]
    result = cross_rqa(pairwise(donor, host, lambda a, b: abs(a - b)), 0.5)
    assert result['X1'] == 4 and result['X2'] == pytest.approx(4 / 42)
    with pytest.raises(ValueError):
        cross_rqa([], 1.0)


# ---------------------------------------------------------------- planted replay

def test_planting_duplicates_or_inserts_the_segment_ending_at_the_midpoint():
    assert plant_self(list(range(10)), 3) == [0, 1, 2, 3, 4, 2, 3, 4, 5, 6, 7, 8, 9]
    assert plant_into([100, 101, 102, 103], [0, 1, 2, 3, 4, 5], 2) == [100, 101, 1, 2, 102, 103]
    assert plant_self([1, 2], 9) == [1, 1, 2]


def test_a_statistic_that_sees_the_plant_is_usable_and_one_that_does_not_is_not():
    rng = random.Random(5)
    runs = {f'r{k}': [rng.randrange(1000) for _ in range(60)] for k in range(8)}
    longest_repeat = lambda seq: max((len(seq) - len(set(seq))), 0)
    good = within_power(runs, longest_repeat, length=12)
    assert good['detect'] == 1.0 and good['false_positive'] <= .25 and usable(good, min_detection=.8, max_false_positive=.25)
    blind = within_power(runs, lambda seq: 0.0, length=12)
    assert blind['detect'] == 0.0 and not usable(blind, min_detection=.8, max_false_positive=.1)
    shared = lambda a, b: len(set(a) & set(b))
    cross = cross_power(runs, shared, length=12)
    assert cross['pairs'] == 28 and cross['detect'] > .8 and cross['false_positive'] <= .15
    with pytest.raises(ValueError, match='three runs'):
        within_power({'a': [1], 'b': [2]}, len, length=1)
    with pytest.raises(ValueError, match='two pairs'):
        cross_power({'a': [1], 'b': [2]}, shared, length=1)
