"""R-FALSE-CLAIM: blocked assignment inference and simulation against independent tiny calculations."""
import itertools
import json

import numpy as np
import pytest

from test_memory_measure import admission, save
from test_memory_measure_withholding import pilot_fixture
from test_knowledge_export import COMMIT, store
from tools import knowledge_export as ke, memory_measure as mm


def study_fixture(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    old = mm.pilot_units(packages[0])
    layout = dict(units=[{k: v for k, v in u.items() if k != 'withheld'} for u in old['units']], shared=old['shared'])
    design = ke.layout_draw(old['version'], layout, 2, ['save:2'], 653, ['lone'], commit=COMMIT)
    path = save(tmp_path / 'draw.json', design)
    facts = json.loads((run / 'judged-facts.json').read_text())
    for index, package in enumerate(packages):
        record = dict(schema='knowledge-units/2', version=old['version'], seed=653,
            draw_sha256=mm.file_sha256(path), start_index=index, block='save', shared=old['shared'],
            units=[dict(u, withheld=index in next(r['withheld'] for r in design['assignment'] if r['unit_id'] == u['id']),
                        placebo=u['id'] == 'lone') for u in layout['units']])
        unit_path = save(package / 'private/units.json', record)
        save(package / 'manifest.json', dict(schema='campaign-run/11', session=json.loads((package / 'manifest.json').read_text())['session'], private_files={'units.json': mm.file_sha256(unit_path)}))
        available = ke.delivered_fact_ids(record)
        for actor, entry in facts['admissions'][package.name].items():
            all_facts = [fact for route in mm.ROUTES for fact in entry.get(route, [])]
            facts['admissions'][package.name][actor] = dict(index=[f for f in all_facts if f['id'] in available],
                withheld=[f for f in all_facts if f['id'] not in available])
    save(run / 'judged-facts.json', facts)
    # Rebuild real blind packets and events under the new routes.
    import shutil
    shutil.rmtree(run / 'judge-packets')
    (run / 'private/judge-mapping.json').unlink()
    mapping = mm.fact_packets(run, packages, run / 'judged-facts.json', 'blind', budget=4200, every=1, seed=8)
    rows = json.loads((run / 'adjudicated.json').read_text())
    routes = {(p['window'], f): route for p in mapping['packets'] for f, route in p['facts'].items()}
    for row in rows['rows']:
        row['route'] = routes[(row['window'], row['fact'])]
    save(run / 'adjudicated.json', rows)
    return run, packages, path, design


def test_study_estimand_itt_touch_placebo_and_mixed_failure(tmp_path, monkeypatch):
    run, packages, path, design = study_fixture(tmp_path)
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
    monkeypatch.setattr(BinomialBayesMixedGLM, 'fit_vb', lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError('fit failed')))
    report = mm.study(run, packages, path, draws=2000)
    assert report == json.loads((run / 'study.json').read_text())
    assert report['schema'] == 'withholding-study/1' and 'not_a_claim' not in report
    primary = report['primary']
    assert primary['units'] == ['article-a']
    assert primary['excluded'] == dict(never_touched=['article-b', 'idle'], one_arm_only=[])
    record = mm.pilot_units(packages[0], independent=False)
    withheld_east = next(u['withheld'] for u in record['units'] if u['id'] == 'article-a')
    assert primary['value'] == (1 if withheld_east else -1)
    assert primary['p'] == pytest.approx(.5 if withheld_east else 1, abs=.04)
    assert report['intention_to_treat']['units_counted'] == 3
    assert report['intention_to_treat']['value'] == pytest.approx(primary['value'] / 3)
    assert report['touch_balance']['value'] == 0 and report['touch_balance']['p'] == 1
    assert report['touch_balance']['arms']['withheld']['share'] == pytest.approx(1 / 3)
    assert report['placebo']['units'] == ['lone']
    assert report['mixed_model'] == dict(status='failed', failure='RuntimeError: fit failed')
    assert len(report['shared']['facts']) == 2 and all(s['missed'] for s in report['shared']['facts'])
    assert sum(arm['missed'] for arm in report['shared']['arms'].values()) == 2
    assert report['judges']['all_pairs']['agreement_interval'] is not None
    assert report['judges']['all_pairs']['binary_missed']['pairs'] > report['judges']['driving_pairs']['binary_missed']['pairs']
    assert report['blocks'] == design['blocks'] and 'model-judge' in ' '.join(report['threats'])


@pytest.mark.parametrize('fault', ['hash', 'repeated', 'missing', 'assignment', 'use'])
def test_study_rejects_bad_draw_provenance_and_use_packets(tmp_path, fault):
    run, packages, path, _ = study_fixture(tmp_path)
    if fault == 'missing':
        packages = packages[:1]
    elif fault == 'use':
        mapping = json.loads((run / 'private/judge-mapping.json').read_text())
        mapping['kind'] = 'use'
        save(run / 'private/judge-mapping.json', mapping)
    else:
        r = mm.pilot_units(packages[1], independent=False)
        if fault == 'hash':
            r['draw_sha256'] = 'f' * 64
        elif fault == 'repeated':
            r['start_index'] = 0
        else:
            r['units'][0]['placebo'] = not r['units'][0]['placebo']
        unit_path = save(packages[1] / 'private/units.json', r)
        save(packages[1] / 'manifest.json', dict(schema='campaign-run/11', session=json.loads((packages[1] / 'manifest.json').read_text())['session'], private_files={'units.json': mm.file_sha256(unit_path)}))
    with pytest.raises(mm.MeasureError):
        mm.study(run, packages, path, draws=10)
    assert not (run / 'study.json').exists()


def test_primary_randomization_matches_brute_force_on_tiny_block():
    assigned = np.array([[1, 1, 0, 0], [1, 0, 1, 0]], dtype=bool)
    touched = np.ones((2, 4), dtype=bool)
    missed = np.array([[1, 1, 0, 0], [1, 0, 0, 0]], dtype=bool)
    options = [np.array([i in pair for i in range(4)], dtype=bool) for pair in itertools.combinations(range(4), 2)]
    observed = .75  # (1 - 0 + 1/2 - 0) / 2
    values = []
    for a, b in itertools.product(options, repeat=2):
        values.append(np.mean([missed[0, a].mean() - missed[0, ~a].mean(),
                               missed[1, b].mean() - missed[1, ~b].mean()]))
    exact = sum(v >= observed for v in values) / len(values)
    result = mm.study_test(assigned, touched, missed, [4], np.array([[2], [2]]), draws=20000, seed=653)
    assert result['value'] == observed
    assert result['p'] == pytest.approx(exact, abs=.008)
    assert result['p'] == (1 + result['extreme']) / (1 + result['draws'])
    assert result == mm.study_test(assigned, touched, missed, [4], np.array([[2], [2]]), draws=20000, seed=653)


def test_primary_eligibility_is_per_unit_not_pooled():
    assigned = np.array([[1, 1, 0, 0]] * 4, dtype=bool)
    touched = np.array([[1, 0, 1, 1], [1, 1, 0, 1], [1, 0, 0, 0], [0, 0, 0, 0]], dtype=bool)
    missed = np.array([[1, 0, 0, 0], [1, 0, 0, 1], [1, 0, 0, 0], [0, 0, 0, 0]], dtype=bool)
    assert float(mm.study_statistic(assigned, touched, missed)) == pytest.approx(.25)  # (1 + (.5 - 1)) / 2
    assert float(mm.study_statistic(assigned, touched, missed, 'itt')) == pytest.approx(.25)
    assert float(mm.study_statistic(assigned, touched, missed, 'touch')) == pytest.approx(.125)


def test_binary_specific_agreement_and_ac1_hand_table():
    # a=20 yes/yes, b=5 yes/no, c=10 no/yes, d=15 no/no: p=.55, chance=.495.
    labels = [('against', 'found_again')] * 20 + [('against', 'in_line')] * 5
    labels += [('did_not_apply', 'against')] * 10 + [('in_line', 'did_not_apply')] * 15
    rows = [dict(labels=dict(zip(('a', 'b'), pair))) for pair in labels]
    result = mm.binary_agreement(rows, ['a', 'b'])
    assert result['table'] == [[15, 10], [5, 20]]
    assert result['positive_specific'] == pytest.approx(40 / 55)
    assert result['negative_specific'] == pytest.approx(30 / 45)
    assert result['ac1'] == pytest.approx((.7 - .495) / (1 - .495))
    assert mm.binary_agreement([], ['a', 'b'])['ac1'] is None
    assert mm.binary_agreement([dict(labels=dict(a='against', b='against'))], ['a', 'b'])['ac1'] == 1


def test_mixed_model_nonconvergence_and_success_are_reported(monkeypatch):
    from types import SimpleNamespace
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
    units = [dict(id='unit', start='start', arm='withheld', touched=True, missed=True),
             dict(id='unit', start='other-start', arm='delivered', touched=True, missed=False)]
    monkeypatch.setattr(BinomialBayesMixedGLM, 'fit_vb', lambda self, **kwargs: SimpleNamespace(optim_retvals=dict(success=False, message='limit')))
    assert 'did not converge' in mm.crossed_mixed_model(units)['failure']
    monkeypatch.setattr(BinomialBayesMixedGLM, 'fit_vb', lambda self, **kwargs: SimpleNamespace(optim_retvals=dict(success=True),
        fe_mean=np.array([0., .8]), fe_sd=np.array([.1, .2]), vcp_mean=np.array([0., 0., 0.]), vcp_sd=np.array([.1, .1, .1])))
    result = mm.crossed_mixed_model(units)
    assert result['withheld'] == dict(mean=.8, sd=.2)
    assert set(result['variance_components']) == {'unit', 'start', 'withheld_by_unit'}

    monkeypatch.setattr(BinomialBayesMixedGLM, 'fit_vb', lambda self, **kwargs: SimpleNamespace(optim_retvals=dict(success=True),
        fe_mean=np.array([0., .8]), fe_sd=np.array([.1, .2]), vcp_mean=np.array([400., 0., 0.]), vcp_sd=np.array([.1, .1, .1])))
    result = mm.crossed_mixed_model(units)
    assert result['status'] == 'failed' and 'nonfinite' in result['failure']
    json.dumps(result, allow_nan=False)


def test_real_mixed_model_reports_only_finite_numbers():
    rng = np.random.default_rng(653)
    units = [dict(id=f'unit-{u}', start=f'start-{s}', arm='withheld' if (u + s) % 2 else 'delivered',
                  touched=True, missed=bool(rng.random() < (.65 if (u + s) % 2 else .35)))
             for u in range(4) for s in range(6)]
    result = mm.crossed_mixed_model(units)
    assert result['status'] in ('ok', 'failed')
    if result['status'] == 'failed':
        assert result['failure']
    def finite_numbers(value):
        if isinstance(value, dict):
            return all(finite_numbers(v) for v in value.values())
        if isinstance(value, (int, float)):
            return np.isfinite(value)
        return True
    assert finite_numbers(result)
    json.dumps(result, allow_nan=False)


def test_study_inputs_use_pooled_arms_and_beta_shrinkage_on_sealed_pilot_format(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    path = tmp_path / 'inputs.json'
    result = mm.study_inputs(run, packages, path)
    assert result == json.loads(path.read_text()) and result['schema'] == 'withholding-study-inputs/2'
    assert result['prior_strength'] == 2 and result['pooled'] == dict(touch=.5, missed_when_touched=.5)
    units = {u['id']: u for u in result['units']}
    assert units['article-a']['raw'] == dict(touch=1., missed_when_touched=.5)
    assert units['article-a']['shrunk'] == dict(touch=.75, missed_when_touched=.5)
    assert units['idle']['raw'] == dict(touch=0., missed_when_touched=None)
    assert units['idle']['shrunk'] == dict(touch=.25, missed_when_touched=.5)
    assert units['idle']['exclusive_scoreable'] is True and units['idle']['placebo'] is False
    assert result['spread'] == 1.
    assert mm.study_inputs(run, packages, tmp_path / 'again.json') == result


def test_simulate_study_seeded_power_and_prices(tmp_path):
    path = save(tmp_path / 'inputs.json', dict(schema='withholding-study-inputs/2', spread=.1,
        units=[dict(id=f'unit-{i}', exclusive_scoreable=True, placebo=False, shrunk=dict(touch=.8, missed_when_touched=.2)) for i in range(6)]))
    report = mm.simulate_study(path, 4., starts=[4, 40], blocks=[1, 2], slope_sd=[0.], sims=40, seed=653)
    assert report == mm.simulate_study(path, 4., starts=[4, 40], blocks=[1, 2], slope_sd=[0.], sims=40, seed=653)
    assert report['draws'] == 2000 and report['effect'] == .5
    for b in (1, 2):
        small, large = [r for r in report['rows'] if r['blocks'] == b]
        assert small['power'] < large['power']
        assert small['price_usd'] == 16 and large['price_usd'] == 160
    assert report['minimum_starts'][0]['starts'] == 40
    assert report['start_sd'] > 0
    assert report['delivered_missed_share'] < .5


@pytest.mark.parametrize('version', [1, 2])
def test_facts_builder_reads_both_unit_record_versions_and_refuses_others(tmp_path, version):
    value = store()
    package = tmp_path / 'package'
    if version == 1:
        hashes = ke.export(package, value, 12)
    else:
        path = save(tmp_path / 'draw.json', ke.study_draw(value, 4, ['save:4'], 653, commit=COMMIT))
        hashes = ke.export(package, value, study=path, start_index=0, commit=COMMIT)
    manifest = dict(schema='campaign-run/11', session='a' * 32, labels=dict(world=None),
        files={'delivered-knowledge.json': hashes['delivered-knowledge.json']},
        private_files={n: hashes['private/' + n] for n in ('knowledge-full.json', 'units.json')})
    save(package / 'manifest.json', manifest)
    actor = package / 'actors/001'
    actor.mkdir(parents=True)
    (actor / 'host.jsonl').write_text(json.dumps(dict(type='host-start', schema='player-host/8', telemetry_version=8, actor_id='actor')) + '\n')
    record = mm.pilot_units(package, independent=False)
    result = mm.build_facts(tmp_path / 'memory-measure/facts', [package])['admissions']['package']['001']
    assert {f['id'] for f in result['index']} == ke.delivered_fact_ids(record)
    record['schema'] = 'knowledge-units/3'
    path = save(package / 'private/units.json', record)
    manifest['private_files']['units.json'] = mm.file_sha256(path)
    save(package / 'manifest.json', manifest)
    with pytest.raises(mm.MeasureError, match='unsupported frozen knowledge'):
        mm.build_facts(tmp_path / 'memory-measure/invalid', [package])
    with pytest.raises(mm.MeasureError, match='knowledge-units/1 or knowledge-units/2'):
        mm.pilot_units(package, independent=False)


def test_pilot_refuses_study_unit_records(tmp_path):
    run, packages, _, _ = study_fixture(tmp_path)
    with pytest.raises(mm.MeasureError, match='pilot requires knowledge-units/1'):
        mm.pilot(run, packages, draws=10)
    assert not (run / 'pilot.json').exists()


@pytest.mark.parametrize('units', [None, {}, ['unit'], [{}], [dict(id='unit', placebo=False)]])
def test_study_unit_records_refuse_malformed_units(tmp_path, units):
    _, packages, _, _ = study_fixture(tmp_path)
    path = packages[0] / 'private/units.json'
    record = json.loads(path.read_text())
    record['units'] = units
    save(path, record)
    with pytest.raises(mm.MeasureError, match='units must be a list of dicts'):
        mm.pilot_units(packages[0], independent=False)


@pytest.mark.parametrize('contents', ['{', '{}', '{"schema": "withholding-study-draw/1"}',
    '{"schema": "withholding-study-draw/2", "version": "v1", "layout": {}, "seed": 1, "blocks": ["a"], '
    '"starts": 3, "placebo": [], "assignment": []}'])
def test_study_wraps_malformed_draw_as_measure_error(tmp_path, contents):
    path = tmp_path / 'malformed-draw.json'
    path.write_text(contents)
    with pytest.raises(mm.MeasureError, match='invalid study draw'):
        mm.study(tmp_path / 'unused-run', [], path)


def test_study_and_inputs_cli_and_simulation_json_do_not_write_outputs(tmp_path, monkeypatch, capsys):
    run, packages, path, _ = study_fixture(tmp_path)
    monkeypatch.setattr(mm, 'crossed_mixed_model', lambda rows: dict(status='failed', failure='fixture'))
    args = [str(p) for p in packages]
    assert mm.main(['study', str(run), '--runs', *args, '--draw', str(path), '--draws', '30', '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['schema'] == 'withholding-study/1' and report['primary']['seed'] == 653
    inputs = tmp_path / 'derived.json'
    assert mm.main(['study-inputs', str(run), '--runs', *args, '--out', str(inputs)]) == 0
    capsys.readouterr()
    synthetic = save(tmp_path / 'synthetic.json', dict(schema='withholding-study-inputs/2', spread=0.,
        units=[dict(id='unit', exclusive_scoreable=True, placebo=False, shrunk=dict(touch=1., missed_when_touched=.1))]))
    before = sorted(tmp_path.rglob('*'))
    assert mm.main(['simulate-study', '--inputs', str(synthetic), '--price', '3', '--starts', '4', '--blocks', '1',
                    '--slope-sd', '0', '.5', '--sims', '2', '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['schema'] == 'withholding-study-simulation/2' and len(result['rows']) == 2
    assert sorted(tmp_path.rglob('*')) == before
    for row in result['rows']:
        assert result['delivered_missed_share'] / row['withheld_missed_share'] == pytest.approx(.5)


@pytest.mark.parametrize('fault', ['version', 'rho', 'effect', 'sims', 'price', 'probability', 'singleton-block'])
def test_simulation_refuses_invalid_or_impossible_inputs(tmp_path, fault):
    value = dict(schema='withholding-study-inputs/2', spread=.1,
        units=[dict(id='unit', exclusive_scoreable=True, placebo=False, shrunk=dict(touch=.8, missed_when_touched=.2))])
    kwargs = dict(price=2., sims=1)
    if fault == 'version':
        value['schema'] = 'withholding-study-inputs/0'
    elif fault == 'rho':
        value['spread'] = None
    elif fault == 'probability':
        value['units'][0]['shrunk']['touch'] = 1.1
    elif fault == 'effect':
        kwargs['effect'] = .01
    elif fault == 'sims':
        kwargs['sims'] = 0
    elif fault == 'singleton-block':
        kwargs.update(starts=[5], blocks=[3])
    else:
        kwargs['price'] = -1
    path = save(tmp_path / 'inputs.json', value)
    with pytest.raises(mm.MeasureError):
        mm.simulate_study(path, **kwargs)


@pytest.mark.parametrize('slope_sd', [1000., 1e6])
def test_simulation_extreme_slope_solves_effect_or_refuses(tmp_path, slope_sd):
    path = save(tmp_path / 'inputs.json', dict(schema='withholding-study-inputs/2', spread=0.,
        units=[dict(id='unit', exclusive_scoreable=True, placebo=False, shrunk=dict(touch=1., missed_when_touched=.2))]))
    try:
        report = mm.simulate_study(path, 1., starts=[4], blocks=[1], slope_sd=[slope_sd], sims=1)
    except mm.MeasureError as error:
        assert 'cannot match the requested effect' in str(error)
    else:
        row = report['rows'][0]
        assert abs(row['log_or']) > 100
        assert abs(row['withheld_missed_share'] - report['delivered_missed_share'] / report['effect']) <= 1e-6


def test_study_inputs_read_actual_sealed_pilot_when_available(tmp_path):
    from tools import evidence
    sealed = evidence.default_store() / 'withholding-pilot-619'
    if not sealed.is_dir():
        pytest.skip('sealed pilot evidence is not present in this checkout')
    packages = sorted((sealed / 'computer-sessions').iterdir())
    result = mm.study_inputs(sealed / 'memory-measure/pilot-619-blind', packages, tmp_path / 'sealed-inputs.json')
    assert result['starts'] == 6 and len(result['units']) == 32
    assert result['pooled']['missed_when_touched'] == pytest.approx(21 / 53)
    assert sum(u['touched'] for u in result['units']) == 53
    assert result['spread'] is not None
    structural = [u for u in result['units'] if not u['exclusive_scoreable']]
    assert len(structural) == 8
    assert all(u['touched'] == u['missed'] == 0 and u['shrunk'] == dict(touch=0, missed_when_touched=0)
               for u in structural)


def test_primary_empty_and_one_arm_only_and_itt_missing_arm():
    assigned = np.array([[True, False]])
    touched = np.array([[True, False]])
    missed = touched.copy()
    result = mm.study_test(assigned, touched, missed, [2], np.array([[1]]), draws=10, seed=653)
    assert result['value'] is None and result['p'] is None and result['units_counted'] == 0
    assert mm.study_test(assigned, touched, missed, [2], np.array([[1]]), draws=10, seed=653, mode='itt')['value'] == 1
    # Singleton blocks can assign an entire unit to one arm. The all-unit estimand is then undefined.
    result = mm.study_test(np.array([[True, True]]), np.ones((1, 2), dtype=bool), np.zeros((1, 2), dtype=bool),
                          [1, 1], np.array([[1, 1]]), draws=10, seed=653, mode='itt')
    assert result['value'] is None and result['p'] is None


def test_inputs_zero_structural_units_and_require_consistent_layout(tmp_path, monkeypatch):
    run, packages = pilot_fixture(tmp_path)
    original = mm.unit_outcomes(run, packages, independent=False)
    for name, record in original['records'].items():
        record['units'].append(dict(id='empty', article_id='empty', fact_ids=[], withheld=False))
        original['units'].append(dict(id='empty', start=name, touched=False, missed=False))
    monkeypatch.setattr(mm, 'unit_outcomes', lambda *args, **kwargs: original)
    result = mm.study_inputs(run, packages, tmp_path / 'inputs.json')
    units = {u['id']: u for u in result['units']}
    assert units['empty']['exclusive_scoreable'] is False
    assert units['empty']['raw'] == dict(touch=0, missed_when_touched=None)
    assert units['empty']['shrunk'] == dict(touch=0, missed_when_touched=0)
    assert units['idle']['shrunk']['touch'] > 0
    original['records'][packages[1].name]['units'][-1]['fact_ids'] = ['new-fact']
    with pytest.raises(mm.MeasureError, match='same exclusive facts'):
        mm.study_inputs(run, packages, tmp_path / 'bad.json')
    original['records'][packages[1].name]['units'][-1]['fact_ids'] = []
    original['records'][packages[1].name]['units'][-1]['placebo'] = True
    with pytest.raises(mm.MeasureError, match='placebo flags'):
        mm.study_inputs(run, packages, tmp_path / 'bad.json')


def test_simulator_excludes_units_and_uses_real_primary_analysis(tmp_path, monkeypatch):
    units = [dict(id='always', exclusive_scoreable=True, placebo=False, shrunk=dict(touch=1., missed_when_touched=.2)),
             dict(id='never', exclusive_scoreable=True, placebo=False, shrunk=dict(touch=0., missed_when_touched=.2)),
             dict(id='empty', exclusive_scoreable=False, placebo=False, shrunk=dict(touch=0., missed_when_touched=0.)),
             dict(id='placebo', exclusive_scoreable=True, placebo=True, shrunk=dict(touch=1., missed_when_touched=.2))]
    path = save(tmp_path / 'inputs.json', dict(schema='withholding-study-inputs/2', spread=0., units=units))
    real_test = mm.study_test
    observed = []
    def check(assigned, touched, missed, sizes, halves, **kwargs):
        assert touched.shape == (2, 4)
        assert touched[0].all() and not touched[1].any()
        assert not (missed & ~touched).any()
        result = real_test(assigned, touched, missed, sizes, halves, **kwargs)
        assert result['units_counted'] == 1
        observed.append(result)
        return result
    monkeypatch.setattr(mm, 'study_test', check)
    result = mm.simulate_study(path, 1, starts=[4], blocks=[1], slope_sd=[0], sims=1)
    assert result['excluded'] == dict(structural_empty=['empty'], placebo=['placebo'])
    assert len(observed) == 1
    units[0]['shrunk']['touch'] = 0
    save(path, dict(schema='withholding-study-inputs/2', spread=0., units=units))
    with pytest.raises(mm.MeasureError):
        mm.simulate_study(path, 1, starts=[4], blocks=[1], slope_sd=[0], sims=1)


@pytest.mark.parametrize('fault', ['missing_scoreable', 'bad_scoreable', 'missing_placebo', 'structural_touch',
                                   'structural_miss', 'structural_count', 'missing_shrunk', 'old_version'])
def test_simulator_rejects_invalid_scoreability(tmp_path, fault):
    unit = dict(id='empty', exclusive_scoreable=False, placebo=False, touched=0, missed=0,
                shrunk=dict(touch=0, missed_when_touched=0))
    companion = dict(id='valid', exclusive_scoreable=True, placebo=False,
                     shrunk=dict(touch=1, missed_when_touched=.2))
    value = dict(schema='withholding-study-inputs/2', spread=0, units=[unit, companion])
    if fault == 'missing_scoreable': del unit['exclusive_scoreable']
    elif fault == 'bad_scoreable': unit['exclusive_scoreable'] = 1
    elif fault == 'missing_placebo': del unit['placebo']
    elif fault == 'structural_touch': unit['shrunk']['touch'] = .1
    elif fault == 'structural_miss': unit['shrunk']['missed_when_touched'] = .1
    elif fault == 'structural_count': unit['touched'] = 1
    elif fault == 'missing_shrunk': del unit['shrunk']
    else: value['schema'] = 'withholding-study-inputs/1'
    with pytest.raises(mm.MeasureError):
        mm.simulate_study(save(tmp_path / 'bad.json', value), 1, starts=[4], blocks=[1], slope_sd=[0], sims=1)


def test_simulated_one_arm_and_empty_primary_are_undefined(tmp_path, monkeypatch):
    units = [dict(id='one-arm', exclusive_scoreable=True, placebo=False,
                  shrunk=dict(touch=.5, missed_when_touched=.2)),
             dict(id='never', exclusive_scoreable=True, placebo=False,
                  shrunk=dict(touch=.5, missed_when_touched=.2)),
             dict(id='empty', exclusive_scoreable=False, placebo=False,
                  shrunk=dict(touch=0, missed_when_touched=0)),
             dict(id='placebo', exclusive_scoreable=True, placebo=True,
                  shrunk=dict(touch=1, missed_when_touched=.2))]
    path = save(tmp_path / 'inputs.json', dict(schema='withholding-study-inputs/2', spread=0, units=units))
    class FixedRandom:
        def random(self, shape):
            return np.array([[0, 1, 1, 1], [1, 1, 1, 1]]) if shape == (2, 4) else np.ones(shape)
        def normal(self, mean, sd, size):
            return np.zeros(size)
        def integers(self, *args):
            return 653
    real_test, real_rng, real_assignment = mm.study_test, mm.np.random.default_rng, mm.blocked_assignment
    results = []
    def check(assigned, touched, missed, sizes, halves, **kwargs):
        assert touched.tolist() == [[True, False, False, False], [False] * 4]
        monkeypatch.setattr(mm.np.random, 'default_rng', real_rng)
        monkeypatch.setattr(mm, 'blocked_assignment', real_assignment)
        result = real_test(assigned, touched, missed, sizes, halves, **kwargs)
        results.append(result)
        return result
    monkeypatch.setattr(mm.np.random, 'default_rng', lambda seed: FixedRandom())
    monkeypatch.setattr(mm, 'blocked_assignment', lambda rng, sizes, count: (
        np.array([[[True, True, False, False]] * count]), np.array([[[2]] * count])))
    monkeypatch.setattr(mm, 'study_test', check)
    report = mm.simulate_study(path, 1, starts=[4], blocks=[1], slope_sd=[0], sims=1)
    assert results[0]['value'] is None and results[0]['p'] is None and results[0]['units_counted'] == 0
    assert report['rows'][0]['power'] == 0
