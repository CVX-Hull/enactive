"""The P1 study's frozen analysis (#491): units and clusters, completeness, re-judging, the decision rule and guards."""
import json

import pytest

from tools import p1_analysis as p1

HOURS = {'lh1': 20.0, 'lh2': 20.0, 'lh3': 0.5, 'lh4': 0.0}   # the synthetic probes sit in lh1-lh3; lh4 adds no hours


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
    """rates: arm+repeat -> share of each boundary's units stated (the first ones in order)."""
    out = []
    for key, rate in rates.items():
        by_boundary = {}
        for u in unit_rows:
            by_boundary.setdefault(u['boundary'], []).append(u)
        for group in by_boundary.values():
            for i, u in enumerate(group):
                out.append(dict(type='label', schema=p1.SCORE_SCHEMA, kind='reobservation', arm=key[0],
                                repeat=int(key[1]), item=u['probe'], stated=i < round(rate * len(group))))
    return out


def rejudged(unit_rows, first, flip=lambda row: row['stated']):
    sample = p1.rejudge_sample(unit_rows)
    by_key = {('reobservation', r['arm'], r['repeat'], r['item']): r for r in first}
    return [dict(by_key[k], rejudge=True, stated=flip(by_key[k])) for k in sorted(sample)]


def guards_ok(false_b=1):
    return ([dict(type='audit', schema=p1.SCORE_SCHEMA, arm='A', repeat=1, item=f'a{i}', false=False) for i in range(40)]
            + [dict(type='audit', schema=p1.SCORE_SCHEMA, arm='B', repeat=r, item=f'b{i}', false=i < false_b)
               for r in (1, 2) for i in range(40)]
            + [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=r, lineage='lh1', curator_dollars=15.0,
                    actor_dollars=30.0, stopped_by_cap=False) for r in (1, 2)]
            + guesses(15))


def guesses(right):
    """30 arm guesses, 15 per arm, with `right` of them matching the arm under the label mapping A=1."""
    rows = [dict(type='guess', arm='A' if i < 15 else 'B') for i in range(30)]
    for i, row in enumerate(rows):
        matched = i < right
        row['guess'] = ('1' if row['arm'] == 'A' else '2') if matched else ('2' if row['arm'] == 'A' else '1')
    return rows


def study(rates, per_boundary=10, extra=(), flip=lambda row: row['stated']):
    rows = spread(probes(per_boundary=per_boundary))
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, rates)
    return rows, first + rejudged(unit_rows, first, flip) + list(extra)


def test_a_clear_gain_within_every_guard_is_a_go():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    result = p1.score(rows, HOURS, scores)
    assert result['decision']['go'] is True, result['decision']
    assert result['decision']['mean_delta'] == pytest.approx(0.5)
    assert result['judge_agreement']['percent'] == 1.0
    assert result['figures']['A1']['undelivered_per_game_hour'] == pytest.approx(56 / 40.5)


def test_score_refuses_hours_that_do_not_name_exactly_the_held_out_lineages():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    for hours in ({k: v for k, v in HOURS.items() if k != 'lh4'}, dict(HOURS, lh5=1.0)):
        with pytest.raises(p1.ScoreError, match='--hours'):
            p1.score(rows, hours, scores)


@pytest.mark.parametrize('rates, outcome', [
    ({'A1': 0.5, 'B1': 0.5, 'B2': 0.3}, 'negative'),
    ({'A1': 0.5, 'B1': 0.6, 'B2': 0.6}, 'inconclusive'),     # above A everywhere, but +0.10 is under the threshold
    ({'A1': 0.3, 'B1': 1.0, 'B2': 0.3}, 'inconclusive'),     # a large mean gain, but one repeat not above A
])
def test_no_go_without_a_large_consistent_gain(rates, outcome):
    rows, scores = study(rates, extra=guards_ok())
    result = p1.score(rows, HOURS, scores)
    assert result['decision']['go'] is False
    assert result['decision']['outcome'].startswith(outcome)


def test_a_lineage_below_a_blocks_a_go_even_with_a_large_pooled_gain():
    rows = spread(probes(per_boundary=10))
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, {'A1': 0.2, 'B1': 0.9, 'B2': 0.9})
    for row in first:          # in lh2, B states nothing A does not
        if row['item'].startswith('lh2') and row['arm'] == 'B':
            row['stated'] = next(r['stated'] for r in first if r['arm'] == 'A' and r['item'] == row['item'])
    result = p1.score(rows, HOURS, first + rejudged(unit_rows, first) + guards_ok())
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
                  stated=arm == 'B' and u['cluster'] in gain)
             for u in unit_rows for arm, reps in p1.ARMS.items() for rep in reps]
    result = p1.score(rows, HOURS, first + rejudged(unit_rows, first) + guards_ok())
    primary = result['decision']['primary']
    # Half the units gained, every lineage above A, both repeats above A: only the cluster bound fails,
    # because resampling two clusters per lineage can draw the one without a gain twice.
    assert primary['delta'] == pytest.approx(0.5) and all(d > 0 for d in primary['per_lineage'].values())
    assert primary['lower_bound'] <= 0 and result['decision']['go'] is False


def test_a_gain_that_rejudging_removes_is_not_a_go():
    # A narrow first-pass gain (+0.2) that the seeded re-judging pulls under the threshold.
    rows, scores = study({'A1': 0.3, 'B1': 0.5, 'B2': 0.5}, extra=guards_ok(),
                         flip=lambda row: row['arm'] == 'A')
    result = p1.score(rows, HOURS, scores)
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
    result = p1.score(rows, HOURS, scores)
    assert result['decision']['go'] is False
    assert result['decision']['outcome'].startswith('guard failed')
    assert result['decision']['guards']['1']['checks'][check] is False


def test_a_held_out_repeat_that_reached_its_cap_fails_the_cost_guard_without_scoring():
    rows = spread(probes())
    capped = [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=2, lineage='lh2', curator_dollars=31.0,
                   actor_dollars=30.0, stopped_by_cap=True), *guesses(15)]
    result = p1.score(rows, HOURS, capped)       # partial labels: none at all
    assert result['decision']['go'] is False and 'reached its cap' in result['decision']['outcome']


def test_rejudging_must_be_exactly_the_seeded_sample():
    rows = spread(probes())
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, {'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    with pytest.raises(p1.ScoreError, match='seeded sample'):
        p1.score(rows, HOURS, first + guards_ok())                               # none
    partial = rejudged(unit_rows, first)[:-1]
    with pytest.raises(p1.ScoreError, match='seeded sample'):
        p1.score(rows, HOURS, first + partial + guards_ok())                     # a selected subset


def test_the_arm_guessing_check_is_required_and_bounded():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=[r for r in guards_ok() if r['type'] != 'guess'])
    with pytest.raises(p1.ScoreError, match='arm-guessing'):
        p1.score(rows, HOURS, scores)                                    # missing
    with pytest.raises(p1.ScoreError, match='arm-guessing'):
        p1.score(rows, HOURS, scores + guesses(15)[:-1])                 # not 30, or unbalanced
    # The limit is the binomial tail under no leak, with the better of two mappings: 21 of 30.
    assert p1.guess_limit() == 21
    for right in (21, 9):                                                # either mapping counts
        with pytest.raises(p1.ScoreError, match='guessed'):
            p1.score(rows, HOURS, scores + guesses(right))
    assert p1.score(rows, HOURS, scores + guesses(20))['arm_guessing']['leaks'] is False


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
    first = labels(unit_rows, {'A1': 0.5, 'B1': 0.5, 'B2': 0.5})
    with pytest.raises(p1.ScoreError, match=match):
        p1.score(rows, HOURS, mutate(first) + rejudged(unit_rows, first) + guards_ok())


def test_development_lineages_are_never_scored():
    rows = [dict(r, lineage='397') for r in probes()]
    with pytest.raises(p1.ScoreError, match='held-out'):
        p1.score(rows, HOURS, guesses(15))


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


def frozen_dir(directory, rows, *, schema='p1-held-out-frozen/1'):
    """A held-out directory: `probes.jsonl` and the `frozen.json` that digests it."""
    directory.mkdir(parents=True)
    path = directory/'probes.jsonl'
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    (directory/'frozen.json').write_text(json.dumps(dict(schema=schema, files={'probes.jsonl': p1.file_sha256(path)})))
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
    first_pass = labels(unit_rows, {'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    scores = tmp_path/'scores.jsonl'
    scores.write_text(''.join(json.dumps(r) + '\n' for r in first_pass + rejudged(unit_rows, first_pass) + guards_ok()))
    hours, out = tmp_path/'hours.json', tmp_path/'result.json'
    hours.write_text(json.dumps(dict(HOURS, lh4=10.0)))
    common = ['--scores', str(scores), '--hours', str(hours), '--out', str(out)]
    assert p1.main(['score', *flags(paths), *common]) == 0
    result = json.loads(out.read_text())
    assert result['decision']['go'] is True
    assert result['probe_files'] == [recorded(path) for path in paths]
    out.unlink()
    with pytest.raises(SystemExit):                                   # probes that leave a held-out lineage out
        p1.main(['score', *flags(paths[:3]), *common])
    assert 'covering exactly' in capsys.readouterr().err and not out.exists()


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
