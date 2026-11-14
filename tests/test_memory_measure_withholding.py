"""The withholding simulation (#386): the model, the exact randomization test, the search for the smallest number
of starts and its price. Seeded; no game, no model and no file of a run is read."""
import json
import math

import numpy as np
import pytest

from tools import memory_measure
from tools.memory_measure import (MeasureError, critical_counts, main, render_withholding, simulate_withholding,
    withholding_rejections, withholding_rows)


def rate(starts: int, ratio: float, wrong: float = 0.1, seed: int = 11, **more) -> float:
    return float(withholding_rejections(np.random.default_rng(seed), starts, 8.3, 0.452, ratio, wrong, sims=20000, **more).mean())


def test_the_critical_count_is_the_exact_binomial_tail_of_redrawing_delivery():
    """Given M missed units, each withheld with probability one half, the count withheld is Binomial(M, 1/2). The
    test rejects from the smallest count whose upper tail is at most alpha."""
    critical = critical_counts(60, 0.05)
    assert list(critical[:6]) == [1, 2, 3, 4, 5, 5]  # five of five has probability 1/32; four of four, 1/16, is too likely
    for missed in range(61):
        tail = lambda count: sum(math.comb(missed, i) for i in range(count, missed + 1)) / 2 ** missed  # noqa: E731
        least = int(critical[missed])
        assert least == missed + 1 or tail(least) <= 0.05
        assert least == 0 or tail(least - 1) > 0.05
    assert list(critical_counts(10, 0.05)) == list(critical[:11]) and int(critical_counts(20, 0.01)[20]) > int(critical[20])


def test_the_false_alarm_rate_is_near_alpha_when_delivery_changes_nothing():
    """At ratio 1 the test must reject about one time in twenty, and never clearly more: it is exact, and a count
    cannot hit 0.05 on the nose, so it sits a little under. Correlated misses and judge errors do not raise it."""
    for starts, wrong, rho in ((12, 0.1, 0.2), (30, 0.1, 0.2), (30, 0.25, 0.2), (30, 0.0, 0.6)):
        false_alarm = rate(starts, 1.0, wrong, rho=rho)
        assert 0.025 < false_alarm < 0.055, (starts, wrong, rho, false_alarm)
    assert rate(30, 1.0, alpha=0.2) > 0.12  # the level is the test's, not a constant


def test_power_rises_with_starts_with_the_effect_and_with_a_better_judge():
    halving = [rate(starts, 0.5) for starts in (5, 10, 20, 40, 60)]
    assert all(low < high for low, high in zip(halving, halving[1:])) and halving[0] < 0.3 and halving[-1] > 0.9
    assert rate(30, 1.0) < rate(30, 2 / 3) < rate(30, 0.5)  # nothing, a cut of one third, a halving
    assert rate(30, 0.5, wrong=0.25) < rate(30, 0.5, wrong=0.1) < rate(30, 0.5, wrong=0.0)
    assert rate(30, 0.5, rho=0.6) < rate(30, 0.5, rho=0.05)  # misses that cluster in a start carry less information


def test_the_model_draws_what_the_design_says():
    """Checked on its expected counts: a start touches Poisson(touched) units, half of them withheld; a withheld
    unit is missed with the missed share and a delivered one with ratio times it; the judge flips labels."""
    calls = []

    class Recorder(np.random.Generator):
        def binomial(self, n, p, size=None):
            drawn = super().binomial(n, p, size)
            calls.append((np.mean(n), float(np.mean(p)), float(np.mean(drawn))))
            return drawn

    rng = Recorder(np.random.PCG64(5))
    withholding_rejections(rng, 40, 8.0, 0.4, 0.5, 0.1, sims=4000)
    withheld, lost_withheld, flipped_off, flipped_on, lost_delivered = calls[0], calls[1], calls[2], calls[3], calls[4]
    assert withheld[0] == pytest.approx(8.0, abs=0.05) and withheld[1] == 0.5 and withheld[2] == pytest.approx(4.0, abs=0.05)
    assert lost_withheld[1] == pytest.approx(0.4, abs=0.01) and lost_withheld[2] == pytest.approx(1.6, abs=0.05)
    assert flipped_off[1] == flipped_on[1] == 0.1 and flipped_on[0] == pytest.approx(2.4, abs=0.05)
    assert lost_delivered[1] == pytest.approx(0.2, abs=0.01) and lost_delivered[2] == pytest.approx(0.8, abs=0.05)
    for bad in (dict(touched=0), dict(missed=1.0), dict(ratio=1.5), dict(ratio=0), dict(wrong=0.5), dict(rho=0), dict(starts=0)):
        values = dict(dict(starts=5, touched=8.0, missed=0.4, ratio=0.5, wrong=0.1, rho=0.2), **bad)
        with pytest.raises(MeasureError):
            withholding_rejections(np.random.default_rng(1), sims=10, **values)


def test_the_rows_are_the_point_values_and_each_end_of_each_interval():
    rows = withholding_rows()
    assert [(row['touched'], row['missed'], row['wrong']) for row in rows] == [
        (8.30, 0.452, 0.0), (8.30, 0.452, 0.1), (8.30, 0.452, 0.167), (8.30, 0.452, 0.25),
        (5.64, 0.452, 0.1), (11.78, 0.452, 0.1), (8.30, 0.115, 0.1), (8.30, 0.690, 0.1), (5.64, 0.115, 0.1), (11.78, 0.690, 0.1)]
    assert rows[0]['case'] == 'point values, judge error 0' and rows[-1]['case'] == 'both at the favourable ends'


def test_the_search_finds_the_smallest_size_prices_it_and_is_fixed_by_its_seed():
    rows = [dict(case='strong', touched=11.78, missed=0.69, wrong=0.0), dict(case='weak', touched=5.64, missed=0.115, wrong=0.1)]
    report = simulate_withholding(rows, sims=3000, seed=5, ceiling=14)
    assert report == simulate_withholding(rows, sims=3000, seed=5, ceiling=14)  # seeded and reproducible
    assert report['cases'][0] == simulate_withholding(rows[:1], sims=3000, seed=5, ceiling=14)['cases'][0]  # a case stands alone
    assert simulate_withholding(rows[:1], sims=3000, seed=6, ceiling=14)['cases'][0]['scanned'] != report['cases'][0]['scanned']
    assert (report['schema'], report['seed'], report['sims'], report['alpha'], report['target'], report['withheld_probability']) == (
        'withholding-simulation/1', 5, 3000, 0.05, 0.8, 0.5)
    strong, weak = report['cases']
    assert 2 < strong['starts'] < 14 and strong['at'] == strong['starts'] == strong['scanned'][-1][0]
    assert [entry[0] for entry in strong['scanned']] == list(range(2, strong['starts'] + 1))
    assert strong['halving'] >= 0.8 > strong['scanned'][-2][1]  # the first size that reaches the target
    assert strong['third_cut'] < strong['halving'] and strong['false_alarm'] < 0.06
    play = strong['starts'] * 3.58
    assert strong['price'] == dict(reached=True, play_usd=round(play, 2), play_with_recall_usd=[round(play * 1.67, 2), round(play * 2.0, 2)],
        total_usd=[round(play + 23 + 1.16, 2), round(play * 2.0 + 23 + 4.19, 2)])
    assert weak['starts'] is None and weak['at'] == 14 and len(weak['scanned']) == 13 and weak['best'][1] < 0.8
    assert weak['price']['reached'] is False and weak['price']['play_usd'] == round(14 * 3.58, 2)
    table = render_withholding(report)
    assert f"| strong | 11.78 | 0.69 | 0 | {strong['starts']} | " in table and '| weak | 5.64 | 0.115 | 0.1 | none up to 14 (best ' in table
    assert f"over ${14 * 3.58:.0f}" in table and 'Seed 5, 3000 simulated studies a size' in table
    with pytest.raises(MeasureError, match='min-starts'):
        simulate_withholding(rows, minimum=5, ceiling=4)


def test_the_command_prints_the_report_as_json_and_renders_a_saved_one(tmp_path, capsys):
    arguments = ['simulate-withholding', '--sims', '400', '--seed', '9', '--ceiling', '6', '--wrong', '0.1']
    assert main([*arguments, '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['schema'] == 'withholding-simulation/1' and len(report['cases']) == 7 and report['prices']['per_start_usd'] == 3.58
    assert report['cases'][0]['touched'] == memory_measure.GATE_TOUCHED and report['cases'][0]['missed'] == memory_measure.GATE_MISSED
    saved = tmp_path / 'report.json'
    saved.write_text(json.dumps(report))
    assert main(['simulate-withholding', '--render', str(saved)]) == 0
    table = capsys.readouterr().out
    assert main(arguments) == 0
    assert capsys.readouterr().out == table == render_withholding(report) + '\n'  # the same seed, the same table
    # the header, the rule under it and seven cases
    assert table.count('\n| ') == 9 and '| Case | Touched | Missed | Judge error | Starts |' in table
    saved.write_text(json.dumps(dict(schema='memory-measure-simulation/1')))  # the comparison between arms: not read
    assert main(['simulate-withholding', '--render', str(saved)]) == 2
    assert 'not a withholding-simulation/1 report' in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == [saved]  # the command writes no file
