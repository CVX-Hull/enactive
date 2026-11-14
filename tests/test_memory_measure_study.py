"""R-FALSE-CLAIM: blocked assignment inference and simulation against independent tiny calculations."""
import itertools
import json

import numpy as np
import pytest

from test_memory_measure import admission, save
from test_memory_measure_withholding import pilot_fixture
from test_knowledge_export import store
from tools import knowledge_export as ke, memory_measure as mm


def study_fixture(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    old = mm.pilot_units(packages[0])
    layout = dict(units=[{k: v for k, v in u.items() if k != 'withheld'} for u in old['units']], shared=old['shared'])
    design = ke.layout_draw(old['version'], layout, 2, ['save:2'], 653, ['lone'])
    path = save(tmp_path / 'draw.json', design)
    facts = json.loads((run / 'judged-facts.json').read_text())
    for index, package in enumerate(packages):
        record = dict(schema='knowledge-units/2', version=old['version'], seed=653,
            draw_sha256=mm.file_sha256(path), start_index=index, block='save', shared=old['shared'],
            units=[dict(u, withheld=index in next(r['withheld'] for r in design['assignment'] if r['unit_id'] == u['id']),
                        placebo=u['id'] == 'lone') for u in layout['units']])
        unit_path = save(package / 'private/units.json', record)
        save(package / 'manifest.json', dict(schema='campaign-run/7', private_files={'units.json': mm.file_sha256(unit_path)}))
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
    mapping = mm.fact_packets(run, packages, run / 'judged-facts.json', 'blind', budget=3600, every=1, seed=8)
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
    record = mm.pilot_units(packages[0])
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
        r = mm.pilot_units(packages[1])
        if fault == 'hash':
            r['draw_sha256'] = 'f' * 64
        elif fault == 'repeated':
            r['start_index'] = 0
        else:
            r['units'][0]['placebo'] = not r['units'][0]['placebo']
        unit_path = save(packages[1] / 'private/units.json', r)
        save(packages[1] / 'manifest.json', dict(schema='campaign-run/7', private_files={'units.json': mm.file_sha256(unit_path)}))
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


def test_study_inputs_use_pooled_arms_and_beta_shrinkage_on_sealed_pilot_format(tmp_path):
    run, packages = pilot_fixture(tmp_path)
    path = tmp_path / 'inputs.json'
    result = mm.study_inputs(run, packages, path)
    assert result == json.loads(path.read_text()) and result['schema'] == 'withholding-study-inputs/1'
    assert result['prior_strength'] == 2 and result['pooled'] == dict(touch=.5, missed_when_touched=.5)
    units = {u['id']: u for u in result['units']}
    assert units['article-a']['raw'] == dict(touch=1., missed_when_touched=.5)
    assert units['article-a']['shrunk'] == dict(touch=.75, missed_when_touched=.5)
    assert units['idle']['raw'] == dict(touch=0., missed_when_touched=None)
    assert units['idle']['shrunk'] == dict(touch=.25, missed_when_touched=.5)
    assert result['spread'] == 1.
    assert mm.study_inputs(run, packages, tmp_path / 'again.json') == result


def test_simulate_study_seeded_power_and_prices(tmp_path):
    path = save(tmp_path / 'inputs.json', dict(schema='withholding-study-inputs/1', spread=.1,
        units=[dict(id=f'unit-{i}', shrunk=dict(touch=.8, missed_when_touched=.2)) for i in range(6)]))
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
        path = save(tmp_path / 'draw.json', ke.study_draw(value, 4, ['save:4'], 653))
        hashes = ke.export(package, value, study=path, start_index=0)
    manifest = dict(schema='campaign-run/7', session='a' * 32,
        files={'delivered-knowledge.json': hashes['delivered-knowledge.json']},
        private_files={n: hashes['private/' + n] for n in ('knowledge-full.json', 'units.json')})
    save(package / 'manifest.json', manifest)
    actor = package / 'actors/001'
    actor.mkdir(parents=True)
    (actor / 'host.jsonl').write_text(json.dumps(dict(type='host-start', schema='player-host/5', telemetry_version=5, actor_id='actor')) + '\n')
    record = mm.pilot_units(package)
    result = mm.build_facts(tmp_path / 'memory-measure/facts', [package])['admissions']['package']['001']
    assert {f['id'] for f in result['index']} == ke.delivered_fact_ids(record)
    record['schema'] = 'knowledge-units/3'
    path = save(package / 'private/units.json', record)
    manifest['private_files']['units.json'] = mm.file_sha256(path)
    save(package / 'manifest.json', manifest)
    with pytest.raises(mm.MeasureError, match='unsupported frozen knowledge'):
        mm.build_facts(tmp_path / 'memory-measure/invalid', [package])
    with pytest.raises(mm.MeasureError, match='knowledge-units/1 or knowledge-units/2'):
        mm.pilot_units(package)


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
    synthetic = save(tmp_path / 'synthetic.json', dict(schema='withholding-study-inputs/1', spread=0.,
        units=[dict(id='unit', shrunk=dict(touch=1., missed_when_touched=.1))]))
    before = sorted(tmp_path.rglob('*'))
    assert mm.main(['simulate-study', '--inputs', str(synthetic), '--price', '3', '--starts', '4', '--blocks', '1',
                    '--slope-sd', '0', '.5', '--sims', '2', '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['schema'] == 'withholding-study-simulation/1' and len(result['rows']) == 2
    assert sorted(tmp_path.rglob('*')) == before
    for row in result['rows']:
        assert result['delivered_missed_share'] / row['withheld_missed_share'] == pytest.approx(.5)


@pytest.mark.parametrize('fault', ['version', 'rho', 'effect', 'sims', 'price', 'probability'])
def test_simulation_refuses_invalid_or_impossible_inputs(tmp_path, fault):
    value = dict(schema='withholding-study-inputs/1', spread=.1,
        units=[dict(id='unit', shrunk=dict(touch=.8, missed_when_touched=.2))])
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
    else:
        kwargs['price'] = -1
    path = save(tmp_path / 'inputs.json', value)
    with pytest.raises(mm.MeasureError):
        mm.simulate_study(path, **kwargs)


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
