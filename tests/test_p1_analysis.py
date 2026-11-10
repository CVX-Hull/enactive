"""The P1 study's frozen analysis (#491, #529): units and clusters, completeness, re-judging, the controls, the decision rule and guards."""
import json
import re

import pytest

from tools import p1_analysis as p1

HOURS = {'lh1': 20.0, 'lh2': 20.0, 'lh3': 0.5, 'lh4': 0.0}   # the synthetic probes sit in lh1-lh3; lh4 adds no hours
CONTROL_RATES = {'R1': 0.5, 'PW1': 1.0, 'PP1': 1.0}          # the Reference, and the positive control's two forms
SCREEN = dict(flagged_twice=0)


def probes(per_boundary=6, boundaries=4, informative=True):
    """Probes of two held-out lineages; their earlier-frame hashes are all zero until `spread`."""
    return [dict(schema=p1.PROBES_SCHEMA, lineage=name, boundary=f'{name}-{b:03d}>{name}-{b + 1:03d}',
                 id=f'{name}-{b}-{i:02d}', confirmed=True, informative=informative, earlier_dhash='0' * 64)
            for name in ('lh1', 'lh2') for b in range(boundaries) for i in range(per_boundary)]


def spread(rows):
    """Random 256-bit earlier hashes (about 128 bits apart), so each probe is its own cluster."""
    import random
    rng = random.Random(7)
    for row in rows:
        row['earlier_dhash'] = format(rng.getrandbits(256), '064x')
    return rows


def labels(unit_rows, rates):
    """rates: arm+repeat (A1, B2, R1, PW1, ...) -> share of each boundary's units stated (the first ones in order)."""
    out = []
    for key, rate in rates.items():
        arm, repeat = re.fullmatch(r'([A-Z]+)(\d)', key).groups()
        by_boundary = {}
        for u in unit_rows:
            by_boundary.setdefault(u['boundary'], []).append(u)
        for group in by_boundary.values():
            for i, u in enumerate(group):
                out.append(dict(type='label', schema=p1.SCORE_SCHEMA, kind='reobservation', arm=arm, repeat=int(repeat),
                                item=u['probe'], stated=i < round(rate * len(group)), answered=True))
    return out


def questions_for(unit_rows):
    return [dict(schema=p1.QUESTION_SCHEMA, probe=u['probe'], question=f'Which entries are on list {u["probe"]}?', key='bolt, saw')
            for u in unit_rows]


def scored(rows, scores, *, hours=HOURS, screen=SCREEN, questions=None):
    """`score` over the units of `rows`, with a question for each of them unless `questions` says otherwise."""
    unit_rows = p1.units(p1.primary_probes(rows))
    return p1.score(rows, hours, scores, questions_for(unit_rows) if questions is None else questions, screen)


def rejudged(unit_rows, first, flip=lambda row: row['stated']):
    sample = p1.rejudge_sample(unit_rows)
    by_key = {('reobservation', r['arm'], r['repeat'], r['item']): r for r in first}
    return [dict(by_key[k], rejudge=True, stated=flip(by_key[k])) for k in sorted(sample)]


def guards_ok(false_b=1):
    return ([dict(type='audit', schema=p1.SCORE_SCHEMA, arm='A', repeat=1, item=f'a{i}', false=False) for i in range(40)]
            + [dict(type='audit', schema=p1.SCORE_SCHEMA, arm='B', repeat=r, item=f'b{i}', false=i < false_b)
               for r in (1, 2) for i in range(40)]
            + [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=r, lineage='lh1', curator_dollars=15.0,
                    actor_dollars=30.0, stopped_by_cap=False) for r in (1, 2)])


def study(rates, per_boundary=10, extra=(), flip=lambda row: row['stated']):
    rows = spread(probes(per_boundary=per_boundary))
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, {**CONTROL_RATES, **rates})
    return rows, first + rejudged(unit_rows, first, flip) + list(extra)


def test_a_clear_gain_within_every_guard_is_a_go():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    result = scored(rows, scores)
    assert result['decision']['go'] is True, result['decision']
    assert result['decision']['mean_delta'] == pytest.approx(0.5)
    assert result['judge_agreement']['percent'] == 1.0
    assert result['figures']['A1']['undelivered_per_game_hour'] == pytest.approx(56 / 40.5)
    assert result['questions_flagged_twice'] == 0
    assert 'arm_guessing' not in result and all('secondary' not in figure for figure in result['figures'].values())


def test_score_refuses_hours_that_do_not_name_exactly_the_held_out_lineages():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    for hours in ({k: v for k, v in HOURS.items() if k != 'lh4'}, dict(HOURS, lh5=1.0)):
        with pytest.raises(p1.ScoreError, match='--hours'):
            scored(rows, scores, hours=hours)


@pytest.mark.parametrize('rates, outcome', [
    ({'A1': 0.5, 'B1': 0.5, 'B2': 0.3}, 'negative'),
    ({'A1': 0.5, 'B1': 0.6, 'B2': 0.6}, 'inconclusive'),     # above A everywhere, but +0.10 is under the threshold
    ({'A1': 0.3, 'B1': 1.0, 'B2': 0.3}, 'inconclusive'),     # a large mean gain, but one repeat not above A
])
def test_no_go_without_a_large_consistent_gain(rates, outcome):
    rows, scores = study(rates, extra=guards_ok())
    result = scored(rows, scores)
    assert result['decision']['go'] is False
    assert result['decision']['outcome'].startswith(outcome)


def test_a_lineage_below_a_blocks_a_go_even_with_a_large_pooled_gain():
    rows = spread(probes(per_boundary=10))
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.2, 'B1': 0.9, 'B2': 0.9})
    for row in first:          # in lh2, B states nothing A does not
        if row['item'].startswith('lh2') and row['arm'] == 'B':
            row['stated'] = next(r['stated'] for r in first if r['arm'] == 'A' and r['item'] == row['item'])
    result = scored(rows, first + rejudged(unit_rows, first) + guards_ok())
    assert result['decision']['primary']['per_lineage']['lh2'] == 0
    assert result['decision']['go'] is False


def test_a_gain_carried_by_one_repeated_cluster_fails_the_cluster_bound():
    # Each lineage re-observes only two pieces of information, alternating over 24 boundaries.
    rows = probes(per_boundary=1, boundaries=24)
    for row in rows:
        row['earlier_dhash'] = ('0' if int(row['id'].split('-')[1]) % 2 else 'f') * 64
    unit_rows = p1.units(p1.primary_probes(rows))
    assert len(unit_rows) == 48 and len({(u['lineage'], u['cluster']) for u in unit_rows}) == 4
    gain = {u['cluster'] for u in unit_rows if int(u['probe'].split('-')[1]) % 2 == 0}
    first = [dict(type='label', schema=p1.SCORE_SCHEMA, kind='reobservation', arm=arm, repeat=rep, item=u['probe'],
                  stated=arm == 'B' and u['cluster'] in gain, answered=True)
             for u in unit_rows for arm, reps in p1.ARMS.items() for rep in reps]
    first += labels(unit_rows, CONTROL_RATES)
    result = scored(rows, first + rejudged(unit_rows, first) + guards_ok())
    primary = result['decision']['primary']
    # Half the units gained, every lineage above A, both repeats above A: only the cluster bound fails,
    # because resampling two clusters per lineage can draw the one without a gain twice.
    assert primary['delta'] == pytest.approx(0.5) and all(d > 0 for d in primary['per_lineage'].values())
    assert primary['lower_bound'] <= 0 and result['decision']['go'] is False


def test_a_gain_that_rejudging_removes_is_not_a_go():
    # A narrow first-pass gain (+0.2) that the seeded re-judging pulls under the threshold.
    rows, scores = study({'A1': 0.3, 'B1': 0.5, 'B2': 0.5}, extra=guards_ok(),
                         flip=lambda row: row['arm'] == 'A')
    result = scored(rows, scores)
    assert result['decision']['primary']['holds'] is True
    assert result['decision']['robust_to_rejudging'] is False and result['decision']['go'] is False
    assert result['judge_agreement']['percent'] < 1


@pytest.mark.parametrize('extra, check', [
    (lambda: [r for r in guards_ok() if r['type'] != 'cost']
     + [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=r, lineage='lh1', curator_dollars=40.0, actor_dollars=30.0,
             stopped_by_cap=False) for r in (1, 2)], 'cost'),
    (lambda: guards_ok(false_b=6), 'false_facts'),                  # 0.15 > 0.10
    (lambda: guards_ok(false_b=4), 'false_facts'),                  # 0.10, but its upper bound is above 0.20
])
def test_a_failed_guard_blocks_a_go_and_says_so(extra, check):
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=extra())
    result = scored(rows, scores)
    assert result['decision']['go'] is False
    assert result['decision']['outcome'].startswith('guard failed')
    assert result['decision']['guards']['1']['checks'][check] is False


def test_a_held_out_repeat_that_reached_its_cap_fails_the_cost_guard_without_scoring():
    rows = spread(probes())
    capped = [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=2, lineage='lh2', curator_dollars=31.0,
                   actor_dollars=30.0, stopped_by_cap=True)]
    result = scored(rows, capped)       # partial labels: none at all
    assert result['decision']['go'] is False and 'reached its cap' in result['decision']['outcome']
    assert result['questions_flagged_twice'] == 0


def test_rejudging_must_be_exactly_the_seeded_sample():
    rows = spread(probes())
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    with pytest.raises(p1.ScoreError, match='seeded sample'):
        scored(rows, first + guards_ok())                                        # none
    partial = rejudged(unit_rows, first)[:-1]
    with pytest.raises(p1.ScoreError, match='seeded sample'):
        scored(rows, first + partial + guards_ok())                              # a selected subset
    control = [dict(r, rejudge=True) for r in first if r['arm'] == 'R'][:1]
    with pytest.raises(p1.ScoreError, match='seeded sample'):
        scored(rows, first + rejudged(unit_rows, first) + control + guards_ok())   # a control is never re-judged


def test_units_count_one_cluster_once_per_boundary_and_only_confirmed_informative_probes():
    rows = spread(probes(per_boundary=3, boundaries=1))
    rows[1]['earlier_dhash'] = rows[0]['earlier_dhash']                         # same information, same boundary
    rows.append(dict(rows[2], id='zz-empty', informative=False))
    unit_rows = p1.units(p1.primary_probes(rows))
    assert len(unit_rows) == 5 and {u['probe'] for u in unit_rows} >= {'lh1-0-00'}
    assert 'lh1-0-01' not in {u['probe'] for u in unit_rows}


def test_clusters_do_not_chain_frames_that_are_not_all_near_each_other():
    rows = probes(per_boundary=1, boundaries=3)[:3]
    # a~b and b~c are 10 bits apart, a~c 20: chaining would merge all three; complete linkage does not.
    for row, h in zip(rows, (0, (1 << 10) - 1, (1 << 20) - 1)):
        row['earlier_dhash'] = format(h, '064x')
    found = p1.clusters(rows)
    assert found[rows[0]['id']] == found[rows[1]['id']] != found[rows[2]['id']]
    assert p1.cluster_sizes(p1.units(rows)) == {'1': 1, '2': 1}



@pytest.mark.parametrize('mutate, match', [
    (lambda rows: rows[:-1], 'do not cover'),
    (lambda rows: rows + [rows[0]], 'judged twice'),
    (lambda rows: rows + [dict(rows[0], arm='C')], 'outside the study'),
    (lambda rows: rows + [dict(type='audit', schema=p1.SCORE_SCHEMA, arm='B', repeat=3, item='x', false=False)],
     'audit row'),
    (lambda rows: rows + [dict(type='audit', schema=p1.SCORE_SCHEMA, arm='B', repeat=1, item='x', false='no')],
     'audit row'),
    (lambda rows: rows + [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=1, lineage='397', curator_dollars=1,
                               actor_dollars=1, stopped_by_cap=False)], 'cost row'),
])
def test_incomplete_or_malformed_rows_are_refused(mutate, match):
    rows = spread(probes())
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.5, 'B1': 0.5, 'B2': 0.5})
    with pytest.raises(p1.ScoreError, match=match):
        scored(rows, mutate(first) + rejudged(unit_rows, first) + guards_ok())


def test_development_lineages_are_never_scored():
    rows = [dict(r, lineage='397') for r in probes()]
    with pytest.raises(p1.ScoreError, match='held-out'):
        scored(rows, [], questions=[])


def test_the_study_2_plan_reproduces_and_its_page_figures_match():
    tracked = json.loads((p1.ROOT/'data'/'evaluation'/'p1'/'power-study-2.json').read_text())
    held_out = p1._lines(p1.ROOT/'data'/'evaluation'/'p1'/'held-out'/'probes.jsonl')
    assert p1.plan(held_out) == tracked
    gate = tracked['gate']
    assert gate == p1.gate(tracked['probability_of_go'][tracked['planning']]) and gate['passes']
    assert tracked['planning'] == f'lh4_boundaries={p1.PLAN_TARGET}, cluster_mean={p1.PLAN_MEAN}'
    page = (p1.ROOT/'docs'/'design'/'p1-study-3.md').read_text().replace('**', '')
    for key, variant in tracked['probability_of_go'].items():     # every row of the page's power table, by its labels
        boundaries, mean = (part.split('=')[1] for part in key.split(', '))
        cells = [boundaries, mean, f"{tracked['lh4_under_min_units'][key]:.3f}"]
        cells += [f'{variant[d]:.3f}' for d in ('0.00', '0.10', '0.15', '0.20', '0.25', '0.30')]
        row = '| ' + ' | '.join(cells) + ' |'
        assert row in page, f'the power table on p1-study-3.md must render power-study-2.json: {row}'
    prose = ' '.join(page.split())
    assert f"P(go) {gate['at_interest']:.3f} at the effect of interest and {gate['no_effect']:.3f}" in prose


def test_the_tracked_power_simulation_reproduces_and_its_page_figures_match():
    tracked = json.loads((p1.ROOT/'data'/'evaluation'/'p1'/'power.json').read_text())
    assert p1.simulate() == tracked
    gate = tracked['gate']
    assert gate['passes'] is (gate['no_effect'] <= 0.05 and gate['at_interest'] >= 0.80)
    planning = tracked['probability_of_go'][tracked['assumptions']['planning']]
    page = (p1.ROOT/'docs'/'design'/'p1-study.md').read_text()
    assert (gate['no_effect'], gate['at_interest']) == (planning['0.00'], planning[f'{p1.INTEREST:.2f}'])
    for variant in tracked['probability_of_go'].values():     # every row of the page's power table
        row = ' | '.join(f'{variant[d]:.3f}' for d in ('0.00', '0.10', '0.15', '0.20', '0.25', '0.30'))
        assert row in page.replace('**', ''), f'the power table on the page must render power.json: {row}'


# ---------------------------------------------------------------------------------------------
# p1-study/2: several frozen held-out probes files (lh4 beside lh1-lh3)

def test_lh4_is_a_held_out_lineage_of_its_seven_restarted_admissions():
    assert p1.LH4_ADMISSIONS == ('lh4b1', 'lh4b2', 'lh4b3', 'lh4b4', 'lh4b5', 'lh4b6', 'lh4b7')   # never the lost lh4a1
    assert p1.HELD_OUT == dict(p1.STUDY_1_HELD_OUT, lh4=p1.LH4_ADMISSIONS)
    assert p1.STUDY_1_HELD_OUT.keys() == {'lh1', 'lh2', 'lh3'}        # p1-study/1's planning never sees lh4
    assert p1.STUDY_1_BOUNDARIES == {'lh1': 4, 'lh2': 3, 'lh3': 3}


def frozen_dir(directory, rows, *, schema='p1-held-out-frozen/1', name='probes.jsonl'):
    """A held-out directory: `probes.jsonl` (or another file) and the `frozen.json` that digests it."""
    directory.mkdir(parents=True)
    path = directory/name
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    (directory/'frozen.json').write_text(json.dumps(dict(schema=schema, files={name: p1.file_sha256(path)})))
    return path


@pytest.fixture
def two_files(tmp_path):
    rows = spread(probes())
    return (frozen_dir(tmp_path/'a', [r for r in rows if r['lineage'] == 'lh1']),
            frozen_dir(tmp_path/'b', [r for r in rows if r['lineage'] == 'lh2']), rows)


def printed(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_several_probes_files_are_concatenated_in_the_order_given(two_files, capsys):
    first, second, rows = two_files
    assert p1.main(['units', '--probes', str(first), '--probes', str(second)]) == 0
    forward = printed(capsys)
    assert forward == p1.units(p1.primary_probes(rows)) and {u['lineage'] for u in forward} == {'lh1', 'lh2'}
    assert p1.main(['units', '--probes', str(second), '--probes', str(first)]) == 0
    assert printed(capsys) == p1.units(p1.primary_probes([r for r in rows if r['lineage'] == 'lh2']
                                                         + [r for r in rows if r['lineage'] == 'lh1']))
    assert p1.main(['rejudge', '--probes', str(first), '--probes', str(second)]) == 0
    assert len(printed(capsys)) == len(p1.rejudge_sample(forward))


def test_a_probes_file_that_differs_from_its_frozen_digest_is_refused_naming_only_the_file(two_files, capsys):
    first, second, rows = two_files
    second.write_text(second.read_text().replace('"informative": true', '"informative": fals', 1))   # one byte
    for step in ('units', 'rejudge'):
        with pytest.raises(SystemExit) as stop:
            p1.main([step, '--probes', str(first), '--probes', str(second)])
        message = capsys.readouterr().err
        assert stop.value.code == 2 and str(second) in message and rows[-1]['id'] not in message
        assert 'fals' not in message
    with pytest.raises(SystemExit):
        p1.main(['simulate', '--probes', str(first), '--probes', str(second)])
    assert 'not a frozen held-out probes file' in capsys.readouterr().err


@pytest.mark.parametrize('damage', ['missing', 'schema', 'other-file', 'unlisted'])
def test_a_probes_file_needs_a_frozen_json_that_lists_it(two_files, capsys, damage):
    first, second, _ = two_files
    frozen = second.parent/'frozen.json'
    if damage == 'missing':
        frozen.unlink()
    elif damage == 'schema':
        frozen.write_text(frozen.read_text().replace('frozen/1', 'frozen/2'))
    elif damage == 'other-file':
        frozen.write_text(json.dumps(dict(schema=p1.FROZEN_SCHEMA, files={'probes.jsonl': p1.file_sha256(first)})))
    else:
        frozen.write_text(json.dumps(dict(schema=p1.FROZEN_SCHEMA, files={})))
    with pytest.raises(SystemExit):
        p1.main(['units', '--probes', str(first), '--probes', str(second)])
    assert str(second) in capsys.readouterr().err


def relabelled(rows, old, new):
    """The rows of lineage `old`, renamed as lineage `new` (ids and boundaries too)."""
    return [dict(r, lineage=new, id=r['id'].replace(old, new), boundary=r['boundary'].replace(old, new))
            for r in rows if r['lineage'] == old]


@pytest.fixture
def four_files(two_files, tmp_path):
    """One frozen probes file per held-out lineage: lh1, lh2, lh3 and lh4."""
    first, second, rows = two_files
    third, fourth = relabelled(rows, 'lh1', 'lh3'), relabelled(rows, 'lh2', 'lh4')
    return [first, second, frozen_dir(tmp_path/'c', third), frozen_dir(tmp_path/'d', fourth)], rows + third + fourth


def recorded(path):
    frozen = path.parent/'frozen.json'
    return dict(path=str(path), sha256=p1.file_sha256(path), frozen=str(frozen), frozen_sha256=p1.file_sha256(frozen))


def flags(paths):
    return [part for path in paths for part in ('--probes', str(path))]


def test_the_gate_file_follows_the_lineages_the_probes_cover(four_files, tmp_path, monkeypatch, capsys):
    paths, rows = four_files
    seen = []
    monkeypatch.setattr(p1, 'simulate', lambda layout=None: seen.append(layout) or {'probability_of_go': {}, 'gate': {}})
    one, both = tmp_path/'power-held-out.json', tmp_path/'power-held-out-study-2.json'
    monkeypatch.setattr(p1, 'POWER_STUDY_1', one)
    monkeypatch.setattr(p1, 'POWER_STUDY_2', both)
    assert p1.main(['simulate', *flags(paths)]) == 0                 # all four lineages: p1-study/2's gate
    assert both.is_file() and not one.exists()
    assert json.loads(both.read_text())['probe_files'] == [recorded(path) for path in paths]
    assert seen[0] == [(u['lineage'], u['cluster']) for u in p1.units(p1.primary_probes(rows))]
    both.unlink()
    assert p1.main(['simulate', *flags(paths[:3])]) == 0             # lh1-lh3, however many files: p1-study/1's gate
    assert one.is_file() and not both.exists()
    assert 'probe_files' not in json.loads(one.read_text())          # its tracked shape is unchanged
    one.unlink()
    monkeypatch.setattr(p1, 'simulate', lambda layout=None: pytest.fail('nothing may run'))
    for arguments, word in ((flags(paths[3:]), 'p1-study/2'),                              # lh4 alone: no default gate
                            ([*flags(paths[3:]), '--out', str(one)], 'p1-study/1'),         # lh4 never in study 1's file
                            ([*flags(paths), '--out', str(one)], 'p1-study/1'),
                            ([*flags(paths[:3]), '--out', str(both)], 'p1-study/2')):       # lh1-lh3 is not study 2's gate
        with pytest.raises(SystemExit):
            p1.main(['simulate', *arguments])
        assert word in capsys.readouterr().err and not one.exists() and not both.exists()


def test_the_repository_relative_path_is_recorded_for_files_inside_the_repository(monkeypatch, tmp_path):
    path = frozen_dir(tmp_path/'held-out-lh4', spread(probes()))
    monkeypatch.setattr(p1, 'ROOT', tmp_path.resolve())
    assert p1.frozen_probes([path])[1] == [dict(path='held-out-lh4/probes.jsonl', sha256=p1.file_sha256(path),
                                                frozen='held-out-lh4/frozen.json',
                                                frozen_sha256=p1.file_sha256(path.parent/'frozen.json'))]


def test_score_takes_one_frozen_file_per_lineage_and_records_them(four_files, tmp_path, capsys):
    paths, rows = four_files
    unit_rows = p1.units(p1.primary_probes(rows))
    first_pass = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    scores = tmp_path/'scores.jsonl'
    scores.write_text(''.join(json.dumps(r) + '\n' for r in first_pass + rejudged(unit_rows, first_pass) + guards_ok()))
    hours, out = tmp_path/'hours.json', tmp_path/'result.json'
    hours.write_text(json.dumps(dict(HOURS, lh4=10.0)))
    questions = frozen_dir(tmp_path/'questions', questions_for(unit_rows), name='questions.jsonl')
    screen = tmp_path/'counts.json'
    screen.write_text(json.dumps(dict(questions=3, flagged=2, flagged_twice=2)))
    common = ['--scores', str(scores), '--hours', str(hours), '--out', str(out), '--questions', str(questions),
              '--screen', str(screen)]
    assert p1.main(['score', *flags(paths), *common]) == 0
    result = json.loads(out.read_text())
    assert result['decision']['go'] is True and result['questions_flagged_twice'] == 2
    assert result['probe_files'] == [recorded(path) for path in paths]
    assert result['question_file'] == recorded(questions)
    out.unlink()
    with pytest.raises(SystemExit):                                   # probes that leave a held-out lineage out
        p1.main(['score', *flags(paths[:3]), *common])
    assert 'covering exactly' in capsys.readouterr().err and not out.exists()


def test_score_refuses_a_questions_file_that_differs_from_its_freeze_or_is_missing_an_input(four_files, tmp_path, capsys):
    paths, rows = four_files
    unit_rows = p1.units(p1.primary_probes(rows))
    first_pass = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    scores, hours, out = tmp_path/'scores.jsonl', tmp_path/'hours.json', tmp_path/'result.json'
    scores.write_text(''.join(json.dumps(r) + '\n' for r in first_pass + rejudged(unit_rows, first_pass) + guards_ok()))
    hours.write_text(json.dumps(dict(HOURS, lh4=10.0)))
    questions = frozen_dir(tmp_path/'questions', questions_for(unit_rows), name='questions.jsonl')
    screen = tmp_path/'counts.json'
    screen.write_text(json.dumps(dict(flagged_twice=0)))
    common = ['--scores', str(scores), '--hours', str(hours), '--out', str(out), '--screen', str(screen)]
    questions.write_text(questions.read_text().replace('bolt', 'nail'))          # one edit after the freeze
    with pytest.raises(SystemExit):
        p1.main(['score', *flags(paths), *common, '--questions', str(questions)])
    error = capsys.readouterr().err
    assert 'not a frozen questions file' in error and 'nail' not in error and not out.exists()
    for missing in ('--questions', '--screen'):
        arguments = [a for i, a in enumerate(common) if a != missing and common[i - 1] != missing]
        with pytest.raises(SystemExit):
            p1.main(['score', *flags(paths), *arguments, *([] if missing == '--questions' else ['--questions', str(questions)])])
        assert '--questions and --screen' in capsys.readouterr().err
    assert not out.exists()


def test_plan_takes_only_study_1s_lineages(four_files, capsys):
    paths, rows = four_files
    with pytest.raises(p1.ScoreError, match='lh4 is simulated'):
        p1.plan(rows)
    with pytest.raises(SystemExit):
        p1.main(['plan', '--probes', str(paths[3])])
    assert 'lh4 is simulated' in capsys.readouterr().err


def test_plan_keeps_exactly_one_probes_file(two_files, capsys):
    first, second, _ = two_files
    with pytest.raises(SystemExit):
        p1.main(['plan', '--probes', str(first), '--probes', str(second)])
    assert 'exactly one' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        p1.main(['plan'])


# ---------------------------------------------------------------------------------------------
# p1-study/3: the sample, the simulation's new parameters, and the controls

def test_the_rejudged_sample_is_what_it_was_before_the_controls_over_a_and_b_keys_only():
    sample = p1.rejudge_sample([dict(probe=f'lh1-p{n:04d}') for n in range(1, 11)])
    assert sorted(sample) == [('reobservation', 'A', 1, 'lh1-p0003'), ('reobservation', 'A', 1, 'lh1-p0005'),
                              ('reobservation', 'A', 1, 'lh1-p0006'), ('reobservation', 'B', 1, 'lh1-p0005'),
                              ('reobservation', 'B', 2, 'lh1-p0005'), ('reobservation', 'B', 2, 'lh1-p0010')]
    assert {key[1] for key in sample} == {'A', 'B'} and p1.rejudge_sample([]) == set()
    every = p1.rejudge_sample([dict(probe=f'p{n}') for n in range(4)], share=1.0)     # development: every A and B label
    assert len(every) == 12 and {key[1] for key in every} == {'A', 'B'}


LAYOUT = [(name, f'{name}-{c}') for name in ('lh1', 'lh2', 'lh3', 'lh4') for c in range(30)]
PINNED = {'0.00': 0.0, '0.10': 0.08, '0.15': 0.35, '0.20': 0.6, '0.25': 0.8, '0.30': 0.95}    # at 84d61e8, 100 simulations


def test_the_simulation_without_the_new_parameters_is_the_one_it_was():
    result = p1.simulate(simulations=100, layout=LAYOUT)
    assert result['probability_of_go']['held-out structure'] == PINNED
    assert result['gate'] == dict(no_effect=0.0, at_interest=0.95, passes=True) and 'varied' not in result
    assert p1.simulate(simulations=100, layout=LAYOUT, flip=None, sensitivity=None) == result
    assert p1.simulate(simulations=100, layout=LAYOUT, flip=p1.FLIP)['probability_of_go'] == result['probability_of_go']   # the same stream


def test_a_label_error_or_a_sensitivity_lowers_the_power_and_is_recorded():
    base = p1.simulate(simulations=100, layout=LAYOUT)['probability_of_go']['held-out structure']
    noisy = p1.simulate(simulations=100, layout=LAYOUT, flip=0.25)
    assert noisy['varied'] == dict(flip=0.25, sensitivity=None)
    assert noisy['probability_of_go']['held-out structure']['0.30'] < base['0.30']
    weak = p1.simulate(simulations=100, layout=LAYOUT, sensitivity=(0.5, 0.5))
    assert weak['varied'] == dict(flip=p1.FLIP, sensitivity=[0.5, 0.5])
    assert weak['probability_of_go']['held-out structure']['0.30'] < base['0.30']
    # a sensitivity that costs B alone lowers B's recall against A's: with nothing kept for B there is no go
    against_b = p1.simulate(simulations=100, layout=LAYOUT, sensitivity=(1.0, 0.0))
    assert against_b['probability_of_go']['held-out structure']['0.30'] == 0.0


def test_the_simulation_flags_take_values_in_range_and_never_write_a_committed_gate(four_files, tmp_path, monkeypatch, capsys):
    paths, _ = four_files
    seen = []
    monkeypatch.setattr(p1, 'simulate', lambda layout=None, **kw: seen.append(kw) or {'probability_of_go': {}, 'gate': {}})
    monkeypatch.setattr(p1, 'ROOT', tmp_path.resolve())
    (tmp_path/'data').mkdir()
    out = tmp_path/'variant.json'
    assert p1.main(['simulate', *flags(paths), '--flip', '0.1', '--sensitivity', '0.9', '0.8', '--out', str(out)]) == 0
    assert seen == [dict(flip=0.1, sensitivity=(0.9, 0.8))] and out.is_file()
    seen.clear()
    assert p1.main(['simulate', *flags(paths), '--out', str(tmp_path/'plain.json')]) == 0 and seen == [{}]       # off by default
    monkeypatch.setattr(p1, 'simulate', lambda layout=None, **kw: pytest.fail('nothing may run'))
    for arguments in (['--flip', '0.1'],                                                                  # no --out
                      ['--flip', '0.1', '--out', str(tmp_path/'data'/'p1'/'power-held-out-study-2.json')],      # a gate under data/
                      ['--sensitivity', '0.9', '0.9', '--out', str(tmp_path/'data'/'x.json')],
                      ['--flip', '0.7', '--out', str(out)], ['--flip', '-0.1', '--out', str(out)],
                      ['--sensitivity', '0', '0.9', '--out', str(out)], ['--sensitivity', '1.1', '0.9', '--out', str(out)]):
        with pytest.raises(SystemExit):
            p1.main(['simulate', *flags(paths), *arguments])
        capsys.readouterr()
    assert not (tmp_path/'data'/'p1').exists() and not (tmp_path/'data'/'x.json').exists()


def stated_table(a, b1, b2, reference, pw=(), pp=(), n=24):
    """Stated labels for probes p00..p{n-1}: each arg is the probes (by number) that arm or control got right."""
    probes = [f'p{i:02d}' for i in range(n)]
    got = {'A': a, 'R': reference, 'PW': pw or range(n), 'PP': pp or range(n)}
    out = {('reobservation', arm, 1, p): i in set(got[arm]) for arm in got for i, p in enumerate(probes)}
    out.update({('reobservation', 'B', 1, p): i in set(b1) for i, p in enumerate(probes)})
    out.update({('reobservation', 'B', 2, p): i in set(b2) for i, p in enumerate(probes)})
    return [dict(probe=p, lineage='lh1', cluster=p, boundary='b') for p in probes], out


def test_the_reference_the_bias_control_and_the_positive_control_are_counted_from_first_pass_labels():
    unit_rows, stated = stated_table(a=range(10), b1=range(5, 17), b2=range(10), reference=range(22), pw=range(24), pp=range(21))
    figures = p1.chain_controls(unit_rows, stated)
    assert figures['reference'] == dict(n=24, correct=22, recall=22 / 24)
    assert figures['bias_control'] == dict(units=22, difference=pytest.approx(1 / 22), applies=True, limit=0.10, min_units=20,
                                           only_a={'B1': 5, 'B2': 0}, only_b={'B1': 7, 'B2': 0}, flag=False, direction='B above A')
    assert figures['reference_wrong'] == {'A1': dict(units=2, stated=0, recall=0.0), 'B1': dict(units=2, stated=0, recall=0.0),
                                          'B2': dict(units=2, stated=0, recall=0.0)}
    assert figures['positive_control'] == dict(PW=dict(units=24, correct=24, sensitivity=1.0),
                                               PP=dict(units=24, correct=21, sensitivity=21 / 24))


def test_the_bias_flag_needs_a_difference_above_a_tenth_over_twenty_reference_correct_units_and_names_its_direction():
    cases = [(range(10), range(16), range(16), 22, True, True, 'B above A'),         # +6/22
             (range(16), range(10), range(10), 22, True, True, 'A above B'),         # -6/22
             (range(10), range(12), range(10), 22, True, False, 'B above A'),        # +1/22
             (range(10), range(12), range(12), 20, True, False, 'B above A'),        # exactly +2/20: not above 0.10
             (range(10), range(16), range(16), 19, False, False, 'B above A')]       # under 20 units: it does not apply
    for a, b1, b2, correct, applies, flag, direction in cases:
        unit_rows, stated = stated_table(a=a, b1=b1, b2=b2, reference=range(correct))
        control = p1.chain_controls(unit_rows, stated)['bias_control']
        assert (control['applies'], control['flag'], control['direction']) == (applies, flag, direction), (correct, control)
    unit_rows, stated = stated_table(a=range(10), b1=range(10), b2=range(10), reference=range(22))
    assert p1.chain_controls(unit_rows, stated)['bias_control']['direction'] is None


def test_only_a_and_only_b_are_given_for_each_b_repeat():
    unit_rows, stated = stated_table(a=range(0, 10), b1=range(5, 12), b2=range(8, 20), reference=range(24))
    control = p1.chain_controls(unit_rows, stated)['bias_control']
    assert control['only_a'] == {'B1': 5, 'B2': 8} and control['only_b'] == {'B1': 2, 'B2': 10}


@pytest.mark.parametrize('mutate, match', [
    (lambda stated: {k: v for k, v in stated.items() if k[1:3] != ('R', 1) or k[3] != 'p05'}, '1 missing, 0 unexpected'),
    (lambda stated: {k: v for k, v in stated.items() if k[1] != 'PP'}, '24 missing'),
    (lambda stated: {**stated, ('reobservation', 'PW', 1, 'p99'): True}, '0 missing, 1 unexpected'),
])
def test_every_unit_needs_a_label_for_each_control_and_no_other(mutate, match):
    unit_rows, stated = stated_table(a=range(5), b1=range(5), b2=range(5), reference=range(5))
    with pytest.raises(p1.ScoreError, match=match):
        p1.chain_controls(unit_rows, mutate(stated))


def test_a_missing_reference_label_is_refused_by_score_and_the_controls_stay_out_of_the_decision():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    gone = [r for r in scores if not (r.get('type') == 'label' and r['arm'] == 'R' and r['item'] == 'lh1-0-00')]
    with pytest.raises(p1.ScoreError, match='Reference and positive-control labels do not cover the study: 1 missing'):
        scored(rows, gone)
    odd = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8, 'R1': 0.0, 'PW1': 0.0, 'PP1': 0.0}, extra=guards_ok())[1]
    assert scored(rows, odd)['decision'] == scored(rows, scores)['decision']      # the controls never reach the rule
    result = scored(rows, scores)
    assert result['reference']['recall'] == 0.5 and result['positive_control']['PP']['sensitivity'] == 1.0
    assert result['bias_control']['applies'] is True and result['bias_control']['flag'] is True
    assert result['bias_control']['direction'] == 'B above A' and result['reference_wrong']['A1']['units'] == 40
    assert result['figures']['A1']['n'] == 80 and 'guards' in result['decision'] and 'R1' not in result['figures']


def test_the_chain_agreement_is_reported_as_percent_kappa_and_percent_over_the_items_either_pass_answered():
    first = {('reobservation', 'A', 1, 'a'): (True, True), ('reobservation', 'A', 1, 'b'): (False, False),
             ('reobservation', 'B', 1, 'c'): (True, True), ('reobservation', 'B', 2, 'd'): (False, False)}
    second = {('reobservation', 'A', 1, 'a'): (True, True), ('reobservation', 'A', 1, 'b'): (False, False),
              ('reobservation', 'B', 1, 'c'): (False, True), ('reobservation', 'B', 2, 'd'): (True, True)}
    whole = p1.agreement(first, second)
    assert whole['n'] == 4 and whole['percent'] == 0.5 and whole['kappa'] == pytest.approx(0.0)
    assert whole['answered_either'] == dict(n=3, percent=pytest.approx(1 / 3))           # b was not answered in either pass
    by_arm = p1.agreement(first, second, ('B',))
    assert by_arm['n'] == 2 and by_arm['percent'] == 0.0 and by_arm['answered_either']['n'] == 2
    assert p1.agreement({}, {}) == dict(n=0, percent=None, kappa=None, answered_either=dict(n=0, percent=None))


@pytest.mark.parametrize('change, ok', [
    ({}, True), (dict(answered=False), True), (dict(arm='PP'), True), (dict(arm='R'), True), (dict(arm='B', repeat=2), True),
    (dict(stated=...), False), (dict(answered=...), False), (dict(stated='yes'), False), (dict(answered=1), False),
    (dict(arm='PW', repeat=2), False), (dict(arm='A', repeat=2), False), (dict(kind='fact'), False), (dict(arm='N'), False),
    (dict(item=3), False)])
def test_a_label_row_needs_a_boolean_stated_and_answered_and_an_arm_of_the_study_or_a_control(change, ok):
    base = dict(type='label', schema=p1.SCORE_SCHEMA, kind='reobservation', arm='A', repeat=1, item='x', stated=True, answered=True)
    made = {k: v for k, v in {**base, **change}.items() if v is not ...}          # `...` removes the field
    if ok:
        first, second = p1.labels([made])
        assert first == {('reobservation', made['arm'], made['repeat'], 'x'): (True, made['answered'])} and second == {}
    else:
        with pytest.raises(p1.ScoreError, match='outside the study'):
            p1.labels([made])


def test_the_questions_must_be_one_p1_question_row_for_each_unit():
    units = [dict(probe='p1'), dict(probe='p2')]
    good = [dict(schema='p1-question/1', probe=p, question='q?', key='') for p in ('p1', 'p2')]
    assert set(p1.question_rows(good, units)) == {'p1', 'p2'}
    for bad, match in ((good[:1], '1 units have none'), (good + [dict(good[0], probe='p3')], '1 questions belong to no unit'),
                       (good + [good[0]], 'two questions'), ([dict(good[0], schema='p1-question/2'), good[1]], 'not a p1-question/1'),
                       ([dict(good[0], question=' '), good[1]], 'not a p1-question/1'), ([dict(good[0], extra=1), good[1]], 'not a p1-question/1'),
                       ([dict(good[0], key=None), good[1]], 'not a p1-question/1'), (['x'], 'not a p1-question/1')):
        with pytest.raises(p1.ScoreError, match=match) as raised:
            p1.question_rows(bad, units)
        assert 'q?' not in str(raised.value)
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    with pytest.raises(p1.ScoreError, match='units have none'):
        scored(rows, scores, questions=questions_for(p1.units(p1.primary_probes(rows)))[1:])
    for screen in ({}, dict(flagged_twice=None), dict(flagged_twice=-1), dict(flagged_twice=True), None, [1]):
        with pytest.raises(p1.ScoreError, match='flagged_twice'):
            scored(rows, scores, screen=screen)
