"""The withholding simulation and frozen pilot analysis on synthetic packages: no game, model or spend."""
import json
import math

import numpy as np
import pytest

from tools import memory_measure
from tools.memory_measure import (MeasureError, critical_counts, main, render_withholding, simulate_withholding,
    withholding_rejections, withholding_rows)
from test_memory_measure import admission, save
from tools.knowledge_export import delivered_fact_ids, units


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
    for bad in (dict(touched=-1), dict(missed=1.1), dict(ratio=1.5), dict(ratio=0), dict(wrong=0.6), dict(rho=-0.1), dict(starts=0)):
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


def pilot_fixture(tmp_path, withheld=None, kind='blind', starts=2, quiet_west=False, same_seed=False,
                  facts_edit=None, third_label='against'):
    """Real packets, judge events and adjudication over two packages, multiple actors/windows and a frameless actor.
    article-a owns two exclusive facts; article-b owns an untouched fact; both cite shared. Lone and idle are
    unfiled facts. The default independently drawn arms put article-a withheld and the lone fact delivered."""
    packages = [admission(tmp_path / 'packages', 'pilot-east', 'e', [1, 2, 3, 4, 5, 6, 'handoff', 7, 8], (750, 400)),
        admission(tmp_path / 'packages', 'pilot-west', 'w', [9, 10, 11, 'handoff', None], (750, 400))][:starts]
    identities = ['mixed', 'straight', 'quiet', 'lone', 'idle', 'shared']
    knowledge = dict(version='synthetic-version', facts=[dict(id=identity, text='An observed fact.') for identity in identities],
        articles=[dict(id='article-a', body=[dict(facts=['mixed', 'straight', 'shared'])]),
            dict(id='article-b', body=[dict(facts=['quiet', 'shared'])])])
    admissions = {}
    for package in packages:
        record = dict(schema='knowledge-units/1', version=knowledge['version'],
            seed=73 if same_seed else 73 + packages.index(package),
            units=[dict(unit, withheld=(unit['id'] == 'article-a') if withheld is None else withheld)
                for unit in units(knowledge)['units']], shared=units(knowledge)['shared'])
        path = save(package / 'private' / 'units.json', record)
        save(package / 'manifest.json', dict(schema='campaign-run/7',
            private_files={'units.json': memory_measure.file_sha256(path)}))
        available = delivered_fact_ids(record)
        entry = dict(index=[fact for fact in knowledge['facts'] if fact['id'] in available],
            withheld=[fact for fact in knowledge['facts'] if fact['id'] not in available])
        admissions[package.name] = {'001': entry, '002': entry}
    if facts_edit is not None:
        facts_edit(admissions)
    run = tmp_path / 'memory-measure' / 'pilot'
    facts = save(run / 'judged-facts.json', dict(schema='judged-facts/1', admissions=admissions))
    mapping = memory_measure.fact_packets(run, packages, facts, kind, budget=3600, every=1, seed=8)
    assert len([packet for packet in mapping['packets'] if packet['start'] == 'pilot-east']) >= 3
    # The first pair needs a third judge, whose answer differs from both originals.
    disputed = next(packet['packet'] for packet in mapping['packets'] if packet['start'] == 'pilot-east')
    for name in ('judge-a', 'judge-b', 'judge-c'):
        answers = []
        for packet in mapping['packets']:
            verdicts = []
            for opaque, identity in packet['fact_ids'].items():
                east = packet['start'] == 'pilot-east'
                label = dict(mixed=('found_again' if packet['actor'] == '002' else 'in_line') if east else 'in_line',
                    straight='in_line', quiet='cannot_tell', lone='found_again' if east else 'in_line',
                    idle='did_not_apply', shared='found_again')[identity]
                if identity == 'mixed' and packet['packet'] == disputed:
                    label = {'judge-a': 'in_line', 'judge-b': 'did_not_apply', 'judge-c': third_label}[name]
                if quiet_west and not east:
                    label = 'did_not_apply'
                verdicts.append(dict(fact=opaque, label=label, holds='stale_or_false' if identity == 'straight' else 'held',
                    frames=['f001'] if label in memory_measure.judge.APPLIED else []))
            answers.append(save(run / 'answers' / name / (packet['packet'] + '.json'),
                dict(packet=packet['packet'], answers=verdicts)))
        memory_measure.judge_events(run, name, 'synthetic-model', answers)
    adjudicated = memory_measure.agreement(run, ['judge-a', 'judge-b'], 'judge-c')
    assert adjudicated['unresolved'] == 0
    return run, packages


def test_pilot_aggregates_mixed_windows_actors_and_exclusive_units(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    report = memory_measure.pilot(run, packages, seed=22, draws=500)
    assert report['schema'] == 'withholding-pilot/1'
    assert json.loads((run / 'pilot.json').read_text()) == report
    assert report['touched_per_start'] == dict(value=2.0, interval=[2.0, 2.0],
        per_start={'pilot-east': 2, 'pilot-west': 2}, variance_over_mean=dict(value=0.0, interval=[0.0, 0.0]))
    east = {unit['id']: unit for unit in report['units'] if unit['start'] == 'pilot-east'}
    assert east['article-a']['touched'] and east['article-a']['missed']
    assert east['article-a']['against'] and east['article-a']['found_again']  # mixed wins over straight in the unit
    assert east['article-a']['stale_or_false']  # holds contributes only to this secondary count
    assert not east['article-b']['touched'] and not east['idle']['touched']
    assert len([fact for fact in report['facts'] if fact['start'] == 'pilot-east' and fact['fact'] == 'mixed']) == 1
    assert report['missed_share']['pooled'] == dict(numerator=2, denominator=4, value=0.5, interval=[0.0, 1.0])
    assert report['spread'] == dict(value=1.0, interval=[1.0, 1.0])
    assert report['comparison']['per_start']['pilot-east'] == dict(
        arms=dict(withheld=dict(touched=1, missed=1), delivered=dict(touched=1, missed=1)), statistic=0, p=0.75)
    assert report['comparison']['pooled']['p'] == 0.75
    assert report['shared']['arms'] == dict(withheld=dict(touched=0, missed=0), delivered=dict(touched=2, missed=2))
    assert report['secondary']['by_arm']['withheld'] == dict(against_only=0, found_again_only=0, both=1, stale_or_false=2)
    assert report['secondary']['by_arm']['delivered']['found_again_only'] == 1
    assert report['secondary']['no_frames'] == ['pilot-west/002']
    assert report['simulation'] == dict(touched=dict(value=2.0, interval=[2.0, 2.0]),
        missed=dict(value=0.5, interval=[0.0, 1.0]), rho=1.0, wrong=report['judges']['wrong']['value'])
    assert 'descriptive' in report['not_a_claim'] and 'adjudicated' in report['not_corrected']
    assert 'four game minutes' in ' '.join(report['threats']) and '2 starts.' in report['threats']
    text = memory_measure.render_pilot(report)
    assert 'exact p=0.75' in text and 'shared facts (outside test)' in text
    with pytest.raises(FileExistsError):
        memory_measure.pilot(run, packages, seed=22, draws=500)


@pytest.mark.parametrize('withheld', [True, False])
def test_pilot_all_or_none_withheld_keeps_empty_arm_undefined(tmp_path, withheld):
    run, packages = pilot_fixture(tmp_path, withheld=withheld)
    report = memory_measure.pilot(run, packages, seed=1, draws=100)
    present, absent = ('withheld', 'delivered') if withheld else ('delivered', 'withheld')
    assert report['missed_share'][present]['value'] == 0.5
    assert report['missed_share'][absent] == dict(numerator=0, denominator=0, value=None, interval=None)
    assert report['shared']['arms'][present] == dict(touched=2, missed=2)
    assert report['comparison']['pooled']['p'] == (0.25 if withheld else 1.0)


def test_pilot_judges_use_the_first_two_labels_before_third_adjudication(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    report = memory_measure.pilot(run, packages, seed=5, draws=200)
    adjudicated = json.loads((run / 'adjudicated.json').read_text())
    assert adjudicated['third_alone'] == 1
    assert any(row['label'] == 'against' and row['by'] == 'third_alone' for row in adjudicated['rows'])
    rows = adjudicated['rows']
    driving = [row for row in rows if any(row['labels'][name] in memory_measure.judge.APPLIED for name in adjudicated['judges'])]
    boot = memory_measure.StartBootstrap([path.name for path in packages], 5, 200)
    for selected, key in ((rows, 'all_pairs'), (driving, 'driving_pairs')):
        expected = memory_measure.judges_beside(boot, selected, adjudicated['judges'])
        assert {key: value for key, value in report['judges'][key].items() if key != 'agreement_interval'} == expected
    first, second = adjudicated['judges']
    missed = memory_measure.PILOT_MISSED
    dispute = sum((row['labels'][first] in missed) != (row['labels'][second] in missed) for row in driving) / len(driving)
    assert report['judges']['wrong']['missed_dispute_rate'] == pytest.approx(dispute)
    assert report['judges']['wrong']['value'] == pytest.approx((1 - math.sqrt(1 - 2 * dispute)) / 2)
    assert report['judges']['all_pairs']['pairs'] > report['judges']['driving_pairs']['pairs']


def test_pilot_exact_randomization_and_unbalanced_binary_anova_icc():
    # P[Binomial(4, 1/2) >= 3] = (4 + 1) / 16. Pooling two starts convolves their binomials.
    assert memory_measure.withholding_pvalue(3, 1) == 5 / 16
    assert memory_measure.withholding_pvalue(0, 0) == 1
    # Sizes 2,4; missed 0,2: MSB=1/3, MSW=1/4, n0=8/3; ICC=(1/12)/(3/4)=1/9.
    assert float(memory_measure.unit_icc(np.array([2, 4]), np.array([0, 2]))) == pytest.approx(1 / 9)
    # Repeating the size-2 start makes three clusters: MSB=1/4, MSW=1/5, n0=5/2; ICC=1/11.
    assert float(memory_measure.unit_icc(np.array([2, 2, 4]), np.array([0, 0, 2]))) == pytest.approx(1 / 11)
    assert float(memory_measure.unit_icc(np.array([4, 4]), np.array([1, 3]))) == pytest.approx(0.2)
    assert float(memory_measure.unit_icc(np.array([4, 4]), np.array([2, 2]))) == 0
    assert np.isnan(memory_measure.unit_icc(np.array([2]), np.array([1])))
    assert np.isnan(memory_measure.unit_icc(np.array([2, 4]), np.array([0, 0])))
    # Vectorized bootstrap calculations retain duplicate starts as distinct sampled clusters.
    np.testing.assert_allclose(memory_measure.unit_icc(np.array([[2, 4], [4, 4], [0, 2]]),
        np.array([[0, 2], [1, 3], [0, 1]])), [1 / 9, 0.2, np.nan], equal_nan=True)


@pytest.mark.parametrize('fault, message', [
    ('seed', 'recorded seed'), ('hash', 'does not match its manifest'), ('unit', 'in no unit and not shared'),
    ('missing-file', 'units.json: missing'),
    ('units-version', 'knowledge-units/1'), ('adjudicated-version', 'judge-adjudicated/2'),
    ('facts-version', 'judged-facts/1'), ('mapping-version', 'judge-mapping/2'),
    ('unresolved', 'every pair resolved'), ('missing-pair', 'every mapped pair adjudicated')])
def test_pilot_refuses_ineligible_or_inconsistent_inputs(tmp_path, fault, message):
    run, packages = pilot_fixture(tmp_path)
    unit_path = packages[0] / 'private' / 'units.json'
    record = json.loads(unit_path.read_text())
    if fault == 'missing-file':
        unit_path.unlink()
    elif fault in ('seed', 'hash', 'unit', 'units-version'):
        if fault == 'seed':
            record['seed'] = None
        elif fault == 'unit':
            record['units'] = [unit for unit in record['units'] if unit['id'] != 'lone']
        elif fault == 'units-version':
            record['schema'] = 'knowledge-units/0'
        else:
            record['seed'] += 1
        save(unit_path, record)
        if fault != 'hash':
            save(packages[0] / 'manifest.json', dict(schema='campaign-run/7',
                private_files={'units.json': memory_measure.file_sha256(unit_path)}))
    else:
        path = run / {'adjudicated-version': 'adjudicated.json', 'facts-version': 'judged-facts.json',
            'mapping-version': 'private/judge-mapping.json', 'unresolved': 'adjudicated.json',
            'missing-pair': 'adjudicated.json'}[fault]
        value = json.loads(path.read_text())
        if fault.endswith('-version'):
            value['schema'] = 'unsupported/0'
        elif fault == 'unresolved':
            value['rows'][0]['unresolved'] = True
        else:
            value['rows'].pop()
        save(path, value)
    with pytest.raises(MeasureError, match=message):
        memory_measure.pilot(run, packages, seed=1, draws=50)
    assert not (run / 'pilot.json').exists()


def test_pilot_refuses_use_packets(tmp_path):
    run, packages = pilot_fixture(tmp_path, kind='use')
    with pytest.raises(MeasureError, match='requires blind packets'):
        memory_measure.pilot(run, packages)


def test_pilot_cli_and_simulation_round_trip(tmp_path, capsys, monkeypatch):
    run, packages = pilot_fixture(tmp_path)
    assert main(['pilot', str(run), '--runs', *(str(path) for path in packages), '--seed', '16', '--draws', '100', '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == json.loads((run / 'pilot.json').read_text())
    simulation = report['simulation']
    expected_rows = withholding_rows(simulation['touched']['value'], simulation['touched']['interval'],
        simulation['missed']['value'], simulation['missed']['interval'], [simulation['wrong']], simulation['wrong'])
    called = []
    actual_simulate = memory_measure.simulate_withholding

    def bounded_simulation(rows, **options):
        # Inspect the command boundary, then run the actual simulator at a small test size.
        called.append((rows, options))
        return actual_simulate(rows, **dict(options, sims=30, ceiling=3))

    monkeypatch.setattr(memory_measure, 'simulate_withholding', bounded_simulation)
    assert main(['simulate-withholding', '--pilot', str(run / 'pilot.json'), '--json']) == 2
    assert '--pilot needs --price' in capsys.readouterr().err
    assert main(['simulate-withholding', '--pilot', str(run / 'pilot.json'), '--render', str(run / 'pilot.json'),
        '--price', '1']) == 2
    assert 'cannot be combined with --render' in capsys.readouterr().err
    assert main(['simulate-withholding', '--pilot', str(run / 'pilot.json'), '--price', '3.58', '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert called[0][0] == expected_rows
    assert called[0][1] == dict(rho=simulation['rho'], sims=10000, seed=386, target=0.8, alpha=0.05,
        minimum=2, ceiling=60, price=3.58)
    assert result['rho'] == simulation['rho'] and len(result['cases']) == 7
    for row, case in zip(expected_rows, result['cases']):
        assert all(case[key] == value for key, value in row.items())
    for flag, values in [('--touched', ['2']), ('--touched-ends', ['1', '3']), ('--missed', ['0.5']),
            ('--missed-ends', ['0', '1']), ('--wrong', ['0.1']), ('--base-wrong', ['0.1']), ('--rho', ['0.2'])]:
        assert main(['simulate-withholding', '--pilot', str(run / 'pilot.json'), '--price', '3.58', flag, *values]) == 2
        assert 'an input it measures' in capsys.readouterr().err
    assert len(called) == 1
    # The price per start and the search settings stay flags: the re-priced study uses the pilot's own price.
    assert main(['simulate-withholding', '--pilot', str(run / 'pilot.json'), '--price', '7.5', '--seed', '5', '--json']) == 0
    capsys.readouterr()
    assert called[1][0] == expected_rows and called[1][1]['price'] == 7.5 and called[1][1]['seed'] == 5
    save(run / 'unsupported.json', dict(schema='withholding-pilot/0'))
    assert main(['simulate-withholding', '--pilot', str(run / 'unsupported.json'), '--price', '1']) == 2
    assert 'not a withholding-pilot/1' in capsys.readouterr().err


def test_simulation_handles_measured_boundary_values_without_perturbing_them():
    for values in (dict(touched=0), dict(missed=0), dict(missed=1), dict(rho=0), dict(rho=1), dict(wrong=0.5)):
        options = dict(dict(touched=3, missed=0.5, ratio=0.5, wrong=0, rho=0.2), **values)
        result = withholding_rejections(np.random.default_rng(1), starts=2, sims=30, **options)
        assert result.shape == (30,) and result.dtype == bool
        if values == dict(touched=0) or values == dict(missed=0):
            assert not result.any()
    # The boundary draws are the Beta's limits: rho 0 gives every start the mean, rho 1 gives each start 0 or 1.
    recorded = []
    original = np.random.Generator.binomial

    class Recording:
        def __init__(self, rng):
            self.rng = rng

        def __getattr__(self, name):
            return getattr(self.rng, name)

        def binomial(self, n, p, size=None):
            recorded.append(np.asarray(p))
            return original(self.rng, n, p, size)

    for rho, check in ((0, lambda shares: np.allclose(shares, 0.3)), (1, lambda shares: set(np.unique(shares)) <= {0, 1})):
        recorded.clear()
        withholding_rejections(Recording(np.random.default_rng(2)), starts=3, sims=40, touched=4, missed=0.3,
            ratio=0.5, wrong=0, rho=rho)
        shares = next(p for p in recorded if p.shape == (40, 3))  # the first per-start probability: the share
        assert check(shares)


def test_pilot_preserves_zero_touched_starts_in_the_bootstrap(tmp_path):
    run, packages = pilot_fixture(tmp_path, quiet_west=True)
    report = memory_measure.pilot(run, packages, seed=12, draws=500)
    assert report['bootstrap']['starts'] == 2
    assert report['touched_per_start'] == dict(value=1.0, interval=[0.0, 2.0],
        per_start={'pilot-east': 2, 'pilot-west': 0}, variance_over_mean=dict(value=2.0, interval=[0.0, 2.0]))
    assert report['comparison']['per_start']['pilot-west']['p'] == 1
    assert report['spread']['value'] is None  # only one start has any binary observations


def test_pilot_one_start_has_no_intervals_and_cannot_supply_simulation_ends(tmp_path):
    run, packages = pilot_fixture(tmp_path, starts=1)
    report = memory_measure.pilot(run, packages, seed=2, draws=100)
    assert report['touched_per_start']['interval'] is None
    assert report['missed_share']['withheld']['interval'] is None
    assert report['spread'] == dict(value=None, interval=None)
    assert report['judges']['wrong']['interval'] is None
    with pytest.raises(MeasureError, match='needs defined interval ends'):
        memory_measure.simulation_from_pilot(run / 'pilot.json')


def test_pilot_judge_error_counts_only_disputes_on_the_missed_outcome(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    path = run / 'adjudicated.json'
    adjudicated = json.loads(path.read_text())
    for row in adjudicated['rows']:
        row['labels']['judge-a'], row['labels']['judge-b'] = 'against', 'found_again'
    save(path, adjudicated)
    report = memory_measure.pilot(run, packages, seed=2, draws=100)
    # Every pair is disputed on the label, but both labels mean missed: no judge error on the outcome.
    assert report['judges']['driving_pairs']['dispute_rate']['value'] == 1
    assert report['judges']['wrong'] == dict(missed_dispute_rate=0.0, value=0.0, interval=[0.0, 0.0])


def test_pilot_clips_missed_disputes_for_implied_judge_error(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    path = run / 'adjudicated.json'
    adjudicated = json.loads(path.read_text())
    for row in adjudicated['rows']:
        row['labels']['judge-a'], row['labels']['judge-b'] = 'against', 'in_line'
    save(path, adjudicated)
    report = memory_measure.pilot(run, packages, seed=2, draws=100)
    assert report['judges']['wrong'] == dict(missed_dispute_rate=1.0, value=0.5, interval=[0.5, 0.5])


def test_pilot_refuses_a_seed_repeated_across_starts(tmp_path):
    run, packages = pilot_fixture(tmp_path, same_seed=True)
    with pytest.raises(MeasureError, match='its own seed'):
        memory_measure.pilot(run, packages, seed=2, draws=100)


def test_pilot_defaults_to_the_frozen_bootstrap_seed_and_counts_its_starts(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    report = memory_measure.pilot(run, packages, draws=50)
    assert report['bootstrap']['seed'] == memory_measure.PILOT_SEED == 619
    assert report['not_a_claim'].startswith('2 starts') and '2 starts.' in report['threats']


def test_pilot_keeps_a_driving_pair_adjudicated_did_not_apply(tmp_path):
    run, packages = pilot_fixture(tmp_path, third_label='did_not_apply')
    adjudicated = json.loads((run / 'adjudicated.json').read_text())
    rows = adjudicated['rows']
    disputed = [row for row in rows if row['labels']['judge-a'] != row['labels']['judge-b']]
    assert len(disputed) == 1
    assert disputed[0]['labels'] == {'judge-a': 'in_line', 'judge-b': 'did_not_apply', 'judge-c': 'did_not_apply'}
    assert disputed[0]['label'] == 'did_not_apply'
    report = memory_measure.pilot(run, packages, draws=50)
    applied_after_adjudication = sum(row['label'] in memory_measure.judge.APPLIED for row in rows)
    pairs = report['judges']['driving_pairs']['pairs']
    assert pairs == applied_after_adjudication + 1
    assert report['judges']['driving_pairs']['dispute_rate']['value'] == pytest.approx(1 / pairs)


def test_pilot_pools_missed_units_from_both_starts_for_its_pvalue(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    path = run / 'adjudicated.json'
    adjudicated = json.loads(path.read_text())
    for row in adjudicated['rows']:
        if row['start'] == 'pilot-west' and row['fact'] == 'lone':
            row['label'] = 'found_again'
            row['labels'] = dict.fromkeys(adjudicated['judges'], 'found_again')
    save(path, adjudicated)
    report = memory_measure.pilot(run, packages, draws=50)
    starts = list(report['comparison']['per_start'].values())
    assert all(sum(arm['missed'] for arm in start['arms'].values()) > 0 for start in starts)
    withheld = sum(start['arms']['withheld']['missed'] for start in starts)
    delivered = sum(start['arms']['delivered']['missed'] for start in starts)
    pooled = report['comparison']['pooled']['p']
    assert (withheld, delivered) == (1, 2)
    assert pooled == memory_measure.withholding_pvalue(withheld, delivered) == 7 / 8
    assert all(pooled != start['p'] for start in starts)


@pytest.mark.parametrize('start, actor', [('pilot-east', '002'), ('pilot-west', '002')])
def test_pilot_requires_every_fact_for_each_judged_actor_including_no_frames(tmp_path, start, actor):
    def omit_fact(admissions):
        entry = admissions[start][actor]
        admissions[start][actor] = dict(entry, index=[fact for fact in entry['index'] if fact['id'] != 'idle'])

    run, packages = pilot_fixture(tmp_path, facts_edit=omit_fact)
    with pytest.raises(MeasureError, match='judged facts do not cover the draw'):
        memory_measure.pilot(run, packages)
    assert not (run / 'pilot.json').exists()


@pytest.mark.parametrize('keep_not_judged', [True, False])
def test_pilot_refuses_an_actor_with_frames_but_no_judged_entry(tmp_path, keep_not_judged):
    def omit_actor(admissions):
        del admissions['pilot-west']['001']

    run, packages = pilot_fixture(tmp_path, facts_edit=omit_actor)
    path = run / 'private' / 'judge-mapping.json'
    mapping = json.loads(path.read_text())
    assert mapping['not_judged'] == ['pilot-west/001']
    if not keep_not_judged:
        del mapping['not_judged']
        save(path, mapping)
    with pytest.raises(MeasureError, match='judged facts do not cover the draw'):
        memory_measure.pilot(run, packages)


def test_pilot_refuses_an_actor_listed_as_not_judged(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    path = run / 'private' / 'judge-mapping.json'
    mapping = json.loads(path.read_text())
    mapping['not_judged'] = mapping['no_frames']
    save(path, mapping)
    with pytest.raises(MeasureError, match='judged facts do not cover the draw'):
        memory_measure.pilot(run, packages)


@pytest.mark.parametrize('identity, source, target', [
    ('mixed', 'withheld', 'index'), ('lone', 'index', 'withheld'), ('shared', 'index', 'withheld')])
def test_pilot_requires_judged_routes_to_match_the_draw_including_shared_facts(tmp_path, identity, source, target):
    def reroute(admissions):
        entry = admissions['pilot-east']['002']
        moved = next(fact for fact in entry[source] if fact['id'] == identity)
        admissions['pilot-east']['002'] = dict(entry,
            **{source: [fact for fact in entry[source] if fact != moved], target: [*entry[target], moved]})

    run, packages = pilot_fixture(tmp_path, facts_edit=reroute)
    with pytest.raises(MeasureError, match="judged routes do not match the package's draw"):
        memory_measure.pilot(run, packages)


def test_pilot_refuses_a_resolved_package_path_under_the_held_out_lineage(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    held_out = tmp_path / memory_measure.HELD_OUT
    held_out.mkdir()
    moved = held_out / packages[0].name
    packages[0].rename(moved)
    alias = tmp_path / packages[0].name
    alias.symlink_to(moved, target_is_directory=True)
    with pytest.raises(MeasureError, match='held-out lineage'):
        memory_measure.pilot(run, [alias, *packages[1:]])


@pytest.mark.parametrize('fault, message', [
    ('campaign-schema', 'requires campaign-run/7'), ('facts-hash', 'differs from the judge mapping hash'),
    ('tampered-pair', 'adjudicated pairs differ'), ('shared-in-unit', 'shared facts must be separate'),
    ('holds', 'holds values from the known set')])
def test_pilot_refuses_invalid_provenance_units_and_holds(tmp_path, fault, message):
    run, packages = pilot_fixture(tmp_path)
    if fault == 'campaign-schema':
        save(packages[0] / 'manifest.json', dict(schema='campaign-run/6'))
    elif fault == 'facts-hash':
        path = run / 'judged-facts.json'
        path.write_text(path.read_text() + '\n')
    elif fault == 'shared-in-unit':
        path = packages[0] / 'private' / 'units.json'
        record = json.loads(path.read_text())
        next(unit for unit in record['units'] if unit['id'] == 'article-a')['fact_ids'].append('shared')
        save(path, record)
        save(packages[0] / 'manifest.json', dict(schema='campaign-run/7',
            private_files={'units.json': memory_measure.file_sha256(path)}))
    else:
        path = run / 'adjudicated.json'
        adjudicated = json.loads(path.read_text())
        adjudicated['rows'][0]['actor' if fault == 'tampered-pair' else 'holds'] = 'unknown'
        save(path, adjudicated)
    with pytest.raises(MeasureError, match=message):
        memory_measure.pilot(run, packages)
    assert not (run / 'pilot.json').exists()


@pytest.mark.parametrize('filename, message', [
    ('units.json', 'expected knowledge-units/1'), ('adjudicated.json', 'expected judge-adjudicated/2'),
    ('judged-facts.json', 'expected judged-facts/1')])
@pytest.mark.parametrize('root', [[], None, 'unexpected'])
def test_pilot_non_object_json_roots_raise_measure_error(tmp_path, filename, message, root):
    run, packages = pilot_fixture(tmp_path)
    path = packages[0] / 'private' / filename if filename == 'units.json' else run / filename
    save(path, root)
    with pytest.raises(MeasureError, match=message):
        memory_measure.pilot(run, packages)


def test_simulation_from_pilot_refuses_undefined_rho_with_defined_intervals(tmp_path):
    path = save(tmp_path / 'pilot.json', dict(schema='withholding-pilot/1', simulation=dict(
        touched=dict(value=2, interval=[1, 3]), missed=dict(value=0.5, interval=[0, 1]), rho=None, wrong=0.1)))
    with pytest.raises(MeasureError, match='defined finite numbers'):
        memory_measure.simulation_from_pilot(path)


def test_pilot_cli_refuses_a_missing_runs_directory_without_a_traceback(tmp_path, capsys):
    run, missing = tmp_path / 'memory-measure' / 'pilot', tmp_path / 'missing-package'
    assert main(['pilot', str(run), '--runs', str(missing)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == f'memory_measure: {missing}: not a run directory or a directory of run directories\n'
