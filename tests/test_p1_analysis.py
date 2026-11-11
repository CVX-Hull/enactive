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


COUNTS_FOR_UNITS = object()     # the default of `scored`: the sentences step's counts for the study's units


def scored(rows, scores, *, hours=HOURS, screen=SCREEN, questions=None, sentences=COUNTS_FOR_UNITS):
    """`score` over the units of `rows`, with a question for each of them unless `questions` says otherwise, and the
    sentences step's counts for them (no failures) unless `sentences` says otherwise."""
    unit_rows = p1.units(p1.primary_probes(rows))
    counts = dict(failed=0, units=len(unit_rows)) if sentences is COUNTS_FOR_UNITS else sentences
    return p1.score(rows, hours, scores, questions_for(unit_rows) if questions is None else questions, screen, counts)


def rejudged(unit_rows, first, flip=lambda row: row['stated']):
    sample = p1.rejudge_sample(unit_rows)
    by_key = {('reobservation', r['arm'], r['repeat'], r['item']): r for r in first}
    return [dict(by_key[k], rejudge=True, stated=flip(by_key[k])) for k in sorted(sample)]


def guards_ok(false_b=1):
    return ([dict(type='audit', schema=p1.SCORE_SCHEMA, arm='A', repeat=1, item=f'a{i}', false=False) for i in range(40)]
            + [dict(type='audit', schema=p1.SCORE_SCHEMA, arm='B', repeat=r, item=f'b{i}', false=i < false_b)
               for r in (1, 2) for i in range(40)]
            + [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=r, lineage=lineage, curator_dollars=3.75,
                    actor_dollars=7.5, stopped_by_cap=False) for r in (1, 2) for lineage in p1.HELD_OUT])


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
     + [dict(type='cost', schema=p1.SCORE_SCHEMA, repeat=r, lineage=lineage, curator_dollars=10.0, actor_dollars=7.5,
             stopped_by_cap=False) for r in (1, 2) for lineage in p1.HELD_OUT], 'cost'),
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


def described(rows, scores, confirmed_audits=None):
    unit_rows = p1.units(p1.primary_probes(rows))
    return p1.describe_capped(rows, HOURS, scores, questions_for(unit_rows), SCREEN,
                             dict(failed=0, units=len(unit_rows)), confirmed_audits if confirmed_audits is not None
                             else [r for r in scores if r['type'] == 'audit'])


def historical_cap(scores):
    return [dict(r, stopped_by_cap=True) if r['type'] == 'cost' and (r['repeat'], r['lineage']) == (2, 'lh4')
            else r for r in scores]


def test_complete_description_preserves_cap_failure_even_with_strong_gain_and_passing_numeric_guards():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    expected = scored(rows, scores)
    capped = historical_cap(scores)
    result = described(rows, capped)
    assert result['schema'] == 'p1-description/1' and 'decision' not in result
    assert result['registered_decision'] == scored(rows, capped)['decision']
    assert result['registered_decision']['go'] is False and result['historical_capped_repeats'] == [2]
    assert result['figures'] == expected['figures']
    assert result['judge_agreement'] == expected['judge_agreement']
    assert result['benefit_diagnostics']['primary'] == expected['decision']['primary']
    assert result['benefit_diagnostics']['primary']['holds'] is True
    assert all(g['holds'] for g in result['benefit_diagnostics']['guards'].values())


@pytest.mark.parametrize('damage, message', [
    ('no-cap', 'historical cap failure'), ('cost', 'cost rows must cover'),
    ('primary', 'primary labels do not cover'), ('rejudge', 're-judged labels'),
    ('control', 'Reference and positive-control labels'),
])
def test_description_requires_historical_failure_and_complete_measurements(damage, message):
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    if damage != 'no-cap':
        scores = historical_cap(scores)
    if damage == 'cost':
        scores.remove(next(r for r in scores if r['type'] == 'cost' and r['lineage'] == 'lh1'))
    elif damage in ('primary', 'rejudge', 'control'):
        scores.remove(next(r for r in scores if r['type'] == 'label' and
                           (r.get('rejudge', False) if damage == 'rejudge' else
                            not r.get('rejudge', False) and r['arm'] == ('A' if damage == 'primary' else 'PW'))))
    with pytest.raises(p1.ScoreError, match=message):
        described(rows, scores)


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'false', 'frame'])
def test_description_refuses_audit_rows_that_differ_from_manifest_validated_answers(damage):
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    scores = historical_cap(scores)
    confirmed = [dict(r) for r in scores if r['type'] == 'audit']
    audit = next(r for r in scores if r['type'] == 'audit')
    if damage == 'missing':
        scores.remove(audit)
    elif damage == 'duplicate':
        scores.append(dict(audit))
    elif damage == 'false':
        audit['false'] = not audit['false']
    else:
        audit['frame'] = 'different-frame'
    with pytest.raises(p1.ScoreError, match='exactly match'):
        described(rows, scores, confirmed)


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'empty'])
def test_costs_cover_each_repeat_and_lineage_once(damage):
    extra = guards_ok()
    cost = next(row for row in extra if row['type'] == 'cost')
    if damage == 'missing':
        extra.remove(cost)
    elif damage == 'duplicate':
        extra.append(dict(cost, curator_dollars=0))  # duplicate actor denominator can manufacture a pass
    else:
        extra = [row for row in extra if row['type'] != 'cost']
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=extra)
    with pytest.raises(p1.ScoreError, match='cost rows'):
        scored(rows, scores)


@pytest.mark.parametrize('field,value', [('actor_dollars', float('inf')), ('curator_dollars', float('nan')),
                                        ('actor_dollars', True), ('curator_dollars', -1),
                                        ('actor_dollars', 10 ** 1000), ('repeat', True)])
def test_costs_reject_invalid_or_unrepresentable_amounts(field, value):
    extra = guards_ok()
    next(row for row in extra if row['type'] == 'cost')[field] = value
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=extra)
    with pytest.raises(p1.ScoreError, match='cost row'):
        scored(rows, scores)


def test_finite_cost_rows_cannot_overflow_the_pooled_denominator():
    extra = [dict(row, actor_dollars=1e308) if row['type'] == 'cost' else row for row in guards_ok()]
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=extra)
    with pytest.raises(p1.ScoreError, match='cost totals'):
        scored(rows, scores)


def test_a_tiny_positive_denominator_cannot_produce_an_infinite_cost_ratio():
    extra = [dict(row, actor_dollars=1e-320) if row['type'] == 'cost' else row for row in guards_ok()]
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=extra)
    with pytest.raises(p1.ScoreError, match='cost ratio'):
        scored(rows, scores)


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


def frozen_dir(directory, rows, *, schema='p1-held-out-frozen/1', name='probes.jsonl', beside=None):
    """A held-out directory: `probes.jsonl` (or another file), the files `beside` it (name -> text), and the
    `frozen.json` that digests them all."""
    directory.mkdir(parents=True)
    path = directory/name
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    for other, text in (beside or {}).items():
        (directory/other).write_text(text)
    files = {file: p1.file_sha256(directory/file) for file in (name, *(beside or {}))}
    (directory/'frozen.json').write_text(json.dumps(dict(schema=schema, files=files)))
    return path


def frozen_questions(root, unit_rows, flagged_twice=0):
    """(questions file, screen.json) as `questions-freeze` leaves them under the repository `root`: the one frozen
    questions file, with the counts beside it."""
    directory = root/'data'/'evaluation'/'p1'/'questions'
    questions = questions_for(unit_rows)
    digest = p1.file_sha256(frozen_dir(directory, questions, name='questions.jsonl'))
    directory.joinpath('frozen.json').unlink()
    counts = json.dumps(dict(questions=3, flagged=flagged_twice, flagged_twice=flagged_twice, questions_sha256=digest))
    (directory/'screen.json').write_text(counts)
    files = {file: p1.file_sha256(directory/file) for file in ('questions.jsonl', 'screen.json')}
    (directory/'frozen.json').write_text(json.dumps(dict(schema=p1.FROZEN_SCHEMA, files=files)))
    return directory/'questions.jsonl', directory/'screen.json'


def sentence_counts(tmp_path, questions, failed=0, units=None, **over):
    """The sentences step's counts for the questions file `questions` (units default to the study's)."""
    path = tmp_path/'sentence-counts.json'
    counts = dict(units=units, stages=1, rewritten=0, failed=failed, questions_sha256=p1.file_sha256(questions))
    path.write_text(json.dumps({k: v for k, v in dict(counts, **over).items() if v is not None}))
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
    return dict(path=p1._relative(path), sha256=p1.file_sha256(path), frozen=p1._relative(frozen), frozen_sha256=p1.file_sha256(frozen))


def flags(paths):
    return [part for path in paths for part in ('--probes', str(path))]


@pytest.fixture
def description_files(four_files, tmp_path, monkeypatch):
    from tools import p1_batches as batches
    monkeypatch.setattr(p1, 'ROOT', tmp_path.resolve())
    monkeypatch.setattr(batches, 'ROOT', tmp_path.resolve())
    paths, rows = four_files
    unit_rows = p1.units(p1.primary_probes(rows))
    first = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    extra = guards_ok()
    audits = [r for r in extra if r['type'] == 'audit']
    build, answers = tmp_path/'.runtime/audit', tmp_path/'.runtime/audit-answers'
    entries = [dict(public=dict(statement='synthetic statement', frames=[]),
                    key={k: r[k] for k in ('arm', 'repeat', 'item')}) for r in audits]
    delivered = tmp_path/'delivered.jsonl'
    delivered.write_text('synthetic delivered-file bytes\n')
    inputs = [p1.file_sha256(delivered), *batches.Frozen(paths).digests]
    batch_meta = batches.write_batches('audit', build, batches.chunks(entries), seed=4913,
                                      host_version='synthetic', inputs=inputs)
    key = json.loads((build/'keys/audit.json').read_text())
    answers.mkdir()
    false_by_item = {(r['arm'], r['repeat'], r['item']): r['false'] for r in audits}
    for batch in key['batches']:
        result = []
        for opaque in batch['ids']:
            item = key['items'][opaque]
            false = false_by_item[(item['arm'], item['repeat'], item['item'])]
            result.append(dict(id=opaque, false=false, frame=None, why='synthetic'))
        (answers/f'{batch["name"]}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in result))
    scores = tmp_path/'scores.jsonl'
    score_rows = first + rejudged(unit_rows, first) + [r for r in extra if r['type'] == 'cost']
    score_rows += batches.parse('audit', build, answers)
    scores.write_text(''.join(json.dumps(r)+'\n' for r in historical_cap(score_rows)))
    questions, screen = frozen_questions(tmp_path, unit_rows)
    counts = sentence_counts(tmp_path, questions, units=len(unit_rows))
    hours = tmp_path/'hours.json'
    hours.write_text(json.dumps(dict(HOURS, lh4=10.0)))
    args = ['describe-capped', *flags(paths), '--scores', str(scores), '--hours', str(hours),
            '--questions', str(questions), '--screen', str(screen), '--sentences-counts', str(counts),
            '--audit-batches', str(build), '--audit-answers', str(answers),
            '--delivered', str(delivered), '--audit-key-sha256', batch_meta['key_sha256']]
    return dict(args=args, out=tmp_path/'description.json', build=build, answers=answers, scores=scores,
                delivered=delivered, canonical=tmp_path/'data/evaluation/p1/result.json')


def test_description_cli_checks_actual_audit_manifest_and_records_separate_provenance(description_files):
    f = description_files
    assert p1.main([*f['args'], '--out', str(f['out'])]) == 0
    result = json.loads(f['out'].read_text())
    assert result['schema'] == p1.DESCRIPTION_SCHEMA and result['registered_decision']['go'] is False
    assert result['benefit_diagnostics']['primary']['holds'] is True
    assert result['audit_evidence']['key']['sha256'] == p1.file_sha256(f['build']/'keys/audit.json')
    assert len(result['audit_evidence']['answers']) == 12
    assert result['input_files']['scores']['sha256'] == p1.file_sha256(f['scores'])
    assert result['delivered_files'][0]['sha256'] == p1.file_sha256(f['delivered'])
    assert set(result['analysis_files']) == {'tools/p1_analysis.py', 'tools/p1_batches.py'}
    assert not f['canonical'].exists()


@pytest.mark.parametrize('damage', ['batch', 'answer'])
def test_description_cli_refuses_changed_batches_or_incomplete_audit_answers(description_files, damage, capsys):
    f = description_files
    if damage == 'batch':
        path = next((f['build']/'batches').glob('*.json'))
        path.write_text(path.read_text()+' ')
    else:
        path = next(f['answers'].glob('*.jsonl'))
        path.write_text('\n'.join(path.read_text().splitlines()[1:])+'\n')
    with pytest.raises(SystemExit):
        p1.main([*f['args'], '--out', str(f['out'])])
    assert ('batch files differ' if damage == 'batch' else 'ids missing') in capsys.readouterr().err
    assert not f['out'].exists()


@pytest.mark.parametrize('damage', ['key', 'delivered'])
def test_description_cli_rejects_modified_manifest_or_audit_from_another_delivery(description_files, damage, capsys):
    f = description_files
    path = f['build']/'keys/audit.json' if damage == 'key' else f['delivered']
    path.write_text(path.read_text()+' ')
    with pytest.raises(SystemExit):
        p1.main([*f['args'], '--out', str(f['out'])])
    assert ('pre-dispatch digest' if damage == 'key' else 'not bound to these delivered/probe') in capsys.readouterr().err
    assert not f['out'].exists()


@pytest.mark.parametrize('destination', ['existing', 'canonical-alias'])
def test_description_cli_cannot_overwrite_any_output_or_alias_the_canonical_result(description_files, destination, capsys):
    f = description_files
    if destination == 'existing':
        protected = out = f['out']
    else:
        protected = f['canonical']
        out = f['out']
        out.symlink_to(protected)
    protected.write_text('preserved result')
    with pytest.raises(SystemExit):
        p1.main([*f['args'], '--out', str(out)])
    assert 'new and distinct' in capsys.readouterr().err
    assert protected.read_text() == 'preserved result'


def test_description_cli_requires_manifest_bindings_and_an_explicit_output(capsys):
    with pytest.raises(SystemExit):
        p1.main(['describe-capped'])
    assert '--audit-key-sha256, --delivered and an explicit new --out' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        p1.main(['score', '--audit-batches', 'unused'])
    assert 'only for describe-capped' in capsys.readouterr().err


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


def test_score_takes_one_frozen_file_per_lineage_and_records_them(four_files, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(p1, 'ROOT', tmp_path.resolve())       # the questions are frozen at the repository root's one path
    paths, rows = four_files
    unit_rows = p1.units(p1.primary_probes(rows))
    first_pass = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    scores = tmp_path/'scores.jsonl'
    scores.write_text(''.join(json.dumps(r) + '\n' for r in first_pass + rejudged(unit_rows, first_pass) + guards_ok()))
    hours, out = tmp_path/'hours.json', tmp_path/'result.json'
    hours.write_text(json.dumps(dict(HOURS, lh4=10.0)))
    questions, screen = frozen_questions(tmp_path, unit_rows, flagged_twice=2)
    counts = sentence_counts(tmp_path, questions, failed=3, units=len(unit_rows))
    common = ['--scores', str(scores), '--hours', str(hours), '--out', str(out), '--questions', str(questions),
              '--screen', str(screen), '--sentences-counts', str(counts)]
    assert p1.main(['score', *flags(paths), *common]) == 0
    result = json.loads(out.read_text())
    assert result['decision']['go'] is True and result['questions_flagged_twice'] == 2
    assert result['positive_control']['paraphrases_failed_twice'] == 3
    assert result['probe_files'] == [recorded(path) for path in paths]
    assert result['question_file'] == recorded(questions)
    assert result['screen_file'] == dict(path=p1._relative(screen), sha256=p1.file_sha256(screen))
    out.unlink()
    with pytest.raises(SystemExit):                                   # probes that leave a held-out lineage out
        p1.main(['score', *flags(paths[:3]), *common])
    assert 'covering exactly' in capsys.readouterr().err and not out.exists()


def test_score_refuses_a_questions_file_that_differs_from_its_freeze_or_is_missing_an_input(four_files, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(p1, 'ROOT', tmp_path.resolve())
    paths, rows = four_files
    unit_rows = p1.units(p1.primary_probes(rows))
    first_pass = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    scores, hours, out = tmp_path/'scores.jsonl', tmp_path/'hours.json', tmp_path/'result.json'
    scores.write_text(''.join(json.dumps(r) + '\n' for r in first_pass + rejudged(unit_rows, first_pass) + guards_ok()))
    hours.write_text(json.dumps(dict(HOURS, lh4=10.0)))
    questions, screen = frozen_questions(tmp_path, unit_rows)
    counts = sentence_counts(tmp_path, questions, units=len(unit_rows))
    common = ['--scores', str(scores), '--hours', str(hours), '--out', str(out), '--screen', str(screen),
              '--sentences-counts', str(counts)]
    questions.write_text(questions.read_text().replace('bolt', 'nail'))          # one edit after the freeze
    with pytest.raises(SystemExit):
        p1.main(['score', *flags(paths), *common, '--questions', str(questions)])
    error = capsys.readouterr().err
    assert 'not a frozen questions file' in error and 'nail' not in error and not out.exists()
    questions.write_text(questions.read_text().replace('nail', 'bolt'))
    assert p1.file_sha256(questions) == json.loads((questions.parent/'frozen.json').read_text())['files']['questions.jsonl']
    # the screen's counts must be the freeze's screen.json: an edited copy, a copy elsewhere and an unlisted one are refused
    other = tmp_path/'other-screen.json'
    other.write_text(json.dumps(dict(flagged_twice=0)))
    edited = screen
    original = edited.read_text()
    edited.write_text(json.dumps(dict(flagged_twice=9)))
    for given in (other, edited):
        with pytest.raises(SystemExit):
            p1.main(['score', *flags(paths), *common[:6], '--screen', str(given), '--sentences-counts', str(counts),
                     '--questions', str(questions)])
        assert 'not the screen counts the questions were frozen with' in capsys.readouterr().err
    edited.write_text(original)
    frozen = questions.parent/'frozen.json'                       # a freeze that does not list the screen's counts
    frozen.write_text(json.dumps(dict(schema=p1.FROZEN_SCHEMA, files={'questions.jsonl': p1.file_sha256(questions)})))
    with pytest.raises(SystemExit):
        p1.main(['score', *flags(paths), *common[:6], '--screen', str(screen),
                 '--sentences-counts', str(counts), '--questions', str(questions)])
    assert 'not the screen counts the questions were frozen with' in capsys.readouterr().err
    for missing in ('--questions', '--screen', '--sentences-counts'):
        arguments = [a for i, a in enumerate(common) if a != missing and common[i - 1] != missing]
        with pytest.raises(SystemExit):
            p1.main(['score', *flags(paths), *arguments,
                     *([] if missing == '--questions' else ['--questions', str(questions)])])
        assert '--questions, --screen and --sentences-counts' in capsys.readouterr().err
    assert not out.exists()


def test_score_refuses_questions_at_another_path_and_sentence_counts_of_another_questions_file(four_files, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(p1, 'ROOT', tmp_path.resolve())
    paths, rows = four_files
    unit_rows = p1.units(p1.primary_probes(rows))
    first_pass = labels(unit_rows, {**CONTROL_RATES, 'A1': 0.3, 'B1': 0.8, 'B2': 0.8})
    scores, hours, out = tmp_path/'scores.jsonl', tmp_path/'hours.json', tmp_path/'result.json'
    scores.write_text(''.join(json.dumps(r) + '\n' for r in first_pass + rejudged(unit_rows, first_pass) + guards_ok()))
    hours.write_text(json.dumps(dict(HOURS, lh4=10.0)))
    questions, screen = frozen_questions(tmp_path, unit_rows)
    n = len(unit_rows)
    common = ['--scores', str(scores), '--hours', str(hours), '--out', str(out), '--screen', str(screen), '--questions', str(questions)]

    def score_with(counts):
        with pytest.raises(SystemExit):
            p1.main(['score', *flags(paths), *common, '--sentences-counts', str(counts)])
        assert not out.exists()
        return capsys.readouterr().err

    # sentences made from another questions file (a Q0 the questions were rewritten from), or from none the counts name
    for over in (dict(questions_sha256='c' * 64), dict(questions_sha256=None)):
        assert 'not of the frozen questions file' in score_with(sentence_counts(tmp_path, questions, units=n, **over))
    # the counts must give the unit count: it is no longer optional
    assert 'one paraphrase for each unit' in score_with(sentence_counts(tmp_path, questions))
    assert 'one paraphrase for each unit' in score_with(sentence_counts(tmp_path, questions, units=n - 1))
    assert p1.main(['score', *flags(paths), *common, '--sentences-counts', str(sentence_counts(tmp_path, questions, units=n))]) == 0
    out.unlink()
    # the freeze verifies in a subdirectory too, but the frozen questions file is exactly one path
    sub = tmp_path/'data'/'evaluation'/'p1'/'questions'/'sub'
    sub.mkdir()
    for name in ('questions.jsonl', 'screen.json', 'frozen.json'):
        (sub/name).write_bytes((questions.parent/name).read_bytes())
    assert p1.frozen_file(sub/'questions.jsonl', 'questions')[0]
    with pytest.raises(SystemExit):
        p1.main(['score', *flags(paths), '--scores', str(scores), '--hours', str(hours), '--out', str(out), '--screen', str(sub/'screen.json'),
                 '--questions', str(sub/'questions.jsonl'), '--sentences-counts', str(sentence_counts(tmp_path, questions, units=n))])
    assert 'the frozen questions file is exactly data/evaluation/p1/questions/questions.jsonl' in capsys.readouterr().err
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
    for counts in ({}, dict(failed=None), dict(failed=-1), dict(failed=True), dict(failed=1.5), None, [1], dict(failed=0, units=1),
                   dict(failed=0), dict(failed=0, units=None), dict(failed=0, units=True)):      # `units` is required
        with pytest.raises(p1.ScoreError, match='sentences-counts'):
            scored(rows, scores, sentences=counts)


def test_a_flagged_bias_control_is_stated_beside_the_outcome_with_its_direction_and_changes_nothing_else():
    rows, scores = study({'A1': 0.3, 'B1': 0.8, 'B2': 0.8}, extra=guards_ok())
    flagged = scored(rows, scores, sentences=dict(failed=4, units=len(p1.units(p1.primary_probes(rows)))))
    assert flagged['bias_control']['flag'] is True
    assert flagged['outcome_note'] == "the received text's answer changed by arm: B above A"    # beside `decision`, not in it
    assert 'outcome_note' not in flagged['decision'] and flagged['decision']['outcome'].startswith('go:')
    assert flagged['positive_control']['paraphrases_failed_twice'] == 4
    assert {'PW', 'PP'} <= set(flagged['positive_control'])
    quiet_rows, quiet = study({'A1': 0.5, 'B1': 0.5, 'B2': 0.5}, extra=guards_ok())
    result = scored(quiet_rows, quiet)
    assert result['bias_control']['flag'] is False and 'outcome_note' not in result
    assert result['positive_control']['paraphrases_failed_twice'] == 0
    # A above B is stated as such, and the decision is the same with or without the note
    reversed_rows, reversed_scores = study({'A1': 0.8, 'B1': 0.3, 'B2': 0.3}, extra=guards_ok())
    below = scored(reversed_rows, reversed_scores)
    assert below['outcome_note'] == "the received text's answer changed by arm: A above B"
    assert below['decision']['outcome'].startswith('negative')


# ---------------------------------------------------------------------------------------------
# The development summary

def dev_label(arm, probe, stated, *, answered=True, rejudge=False, repeat=1):
    row = dict(type='label', schema=p1.SCORE_SCHEMA, kind='reobservation', arm=arm, repeat=repeat, item=probe,
               stated=stated, answered=answered)
    return dict(row, rejudge=True) if rejudge else row


def dev_study(n=20, *, a=range(10), b=range(12), reference=range(18), pw=range(20), pp=range(18), flip_a=(), flip_b=(),
              unanswered=()):
    """Development labels for `n` units: each arm's or control's stated units, and the re-judged twins of A and B with
    `flip_*` units changed; the `unanswered` units were mechanically "not stated" in both passes (they must be unstated)."""
    probes = [f'pair-{i:02d}' for i in range(n)]
    got = {'A': set(a), 'B': set(b), 'R': set(reference), 'PW': set(pw), 'PP': set(pp)}
    rows = [dev_label(arm, p, i in hits, answered=not (arm in ('A', 'B') and i in unanswered))
            for i, p in enumerate(probes) for arm, hits in got.items()]
    rows += [dev_label(arm, p, (i in got[arm]) != (i in flips), answered=i not in unanswered, rejudge=True)
             for i, p in enumerate(probes) for arm, flips in (('A', flip_a), ('B', flip_b))]
    return rows


def test_the_development_summary_reports_the_noise_the_sensitivity_and_the_reference():
    rows = dev_study(flip_a={0, 1}, flip_b={2}, unanswered={19})
    summary = p1.development_summary(rows)
    assert summary['units'] == 20
    noise = summary['noise']
    assert noise['A'] | {'kappa': None} == dict(labels=20, disagreements=2, d=pytest.approx(0.1), kappa=None,
                                                answered_either=dict(labels=19, disagreements=2, d=pytest.approx(2 / 19)))
    assert noise['B']['labels'] == 20 and noise['B']['disagreements'] == 1 and noise['B']['d'] == pytest.approx(0.05)
    assert noise['B']['answered_either'] == dict(labels=19, disagreements=1, d=pytest.approx(1 / 19))
    pooled = noise['pooled']
    assert (pooled['labels'], pooled['disagreements']) == (40, 3) and pooled['d'] == pytest.approx(0.075)
    assert pooled['answered_either'] == dict(labels=38, disagreements=3, d=pytest.approx(3 / 38))
    assert pooled['label_error'] == pytest.approx((1 - (1 - 2 * 0.075) ** 0.5) / 2)
    first, second = p1.labels(rows)
    assert pooled['kappa'] == pytest.approx(p1.agreement(first, second)['kappa']) and noise['A']['kappa'] is not None
    assert summary['sensitivity'] == dict(PW=dict(units=20, correct=20, sensitivity=1.0),
                                          PP=dict(units=20, correct=18, sensitivity=0.9))
    assert summary['reference'] == dict(units=20, correct=18, recall=0.9)
    assert summary['recall'] == dict(A=dict(units=20, stated=10, recall=0.5), B=dict(units=20, stated=12, recall=0.6))
    assert summary['noise_ok'] is True and summary['sensitivity_ok'] is True and summary['floor_ok'] is True
    # The Reference missed units 18 and 19; A states units 0-9 and B units 0-11, so neither states those two.
    assert summary['reference_wrong'] == dict(A=dict(units=2, stated=0), B=dict(units=2, stated=0))
    assert summary['limits'] == dict(noise=0.10, sensitivity=0.85, floor=0.15)


@pytest.mark.parametrize('flips, noise_ok', [(4, True), (5, False)])      # 4 of 40 is exactly 10%: at most 10% passes
def test_the_noise_check_is_a_pooled_disagreement_of_at_most_ten_percent(flips, noise_ok):
    summary = p1.development_summary(dev_study(flip_a=set(range(flips))))
    assert summary['noise']['pooled']['disagreements'] == flips and summary['noise_ok'] is noise_ok


@pytest.mark.parametrize('a, b, reference, ok', [(0, 0, 0, False), (2, 2, 2, False), (3, 0, 0, True), (0, 3, 0, True), (0, 0, 3, True)])
def test_the_floor_check_needs_an_arm_or_the_reference_stated_on_three_of_twenty_units(a, b, reference, ok):
    """The first development run scored A, B and the Reference at 0 of 20 and passed both other checks (10 November 2026)."""
    summary = p1.development_summary(dev_study(a=range(a), b=range(b), reference=range(reference)))
    assert summary['floor_ok'] is ok and summary['limits']['floor'] == 0.15
    assert summary['noise_ok'] is True and summary['sensitivity_ok'] is True


@pytest.mark.parametrize('correct, ok', [(17, True), (16, False), (20, True)])    # 17 of 20 is exactly 85%
def test_the_sensitivity_check_needs_at_least_85_percent_for_each_form(correct, ok):
    assert p1.development_summary(dev_study(pp=range(correct)))['sensitivity_ok'] is ok
    assert p1.development_summary(dev_study(pw=range(correct)))['sensitivity_ok'] is ok


def test_the_label_error_is_capped_when_the_disagreement_reaches_a_half():
    summary = p1.development_summary(dev_study(flip_a=set(range(20)), flip_b=set(range(20))))
    assert summary['noise']['pooled']['d'] == 1.0 and summary['noise']['pooled']['label_error'] == 0.5
    assert summary['noise_ok'] is False


@pytest.mark.parametrize('mutate, match', [
    (lambda rows: rows + [dict(rows[0], item='lh1-p0001')], 'held-out lineage'),
    (lambda rows: rows + [dict(rows[0], item='lh4b3-x')], 'held-out lineage'),
    (lambda rows: [r for r in rows if not (r['arm'] == 'R' and r['item'] == 'pair-03')], '1 missing, 0 unexpected'),
    (lambda rows: [r for r in rows if r['arm'] != 'PP'], '20 missing'),
    (lambda rows: [r for r in rows if not (r['arm'] == 'A' and r['item'] == 'pair-03' and not r.get('rejudge'))], '1 missing'),
    (lambda rows: [r for r in rows if not (r['arm'] == 'B' and r['item'] == 'pair-04' and r.get('rejudge'))], 'must be re-judged'),
    (lambda rows: [r for r in rows if not r.get('rejudge')], 'must be re-judged'),
    (lambda rows: rows + [dict(rows[0], repeat=2, arm='B')], r'0 missing, 1 unexpected'),
    (lambda rows: rows + [dict(rows[0], arm='R', rejudge=True)], r'0 missing, 1 unexpected'),
    (lambda rows: rows + [dict(rows[0], arm='A')], 'judged twice'),
    (lambda rows: rows + [dict(type='cost', schema=p1.SCORE_SCHEMA)], 'label rows only'),
    (lambda rows: [], 'no development labels')])
def test_the_development_summary_refuses_what_is_not_a_complete_development_chain(mutate, match):
    with pytest.raises(p1.ScoreError, match=match):
        p1.development_summary(mutate(dev_study()))


def test_the_development_command_writes_and_prints_figures_only_under_the_runtime_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(p1, 'ROOT', tmp_path.resolve())
    scores = tmp_path/'dev-scores.jsonl'
    scores.write_text(''.join(json.dumps(r) + '\n' for r in dev_study(flip_a={0})))
    out = tmp_path/'.runtime'/'development'/'summary.json'
    assert p1.main(['development', '--scores', str(scores), '--out', str(out)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(out.read_text()) == p1.development_summary(dev_study(flip_a={0}))
    assert 'pair-' not in out.read_text() and printed['noise_ok'] is True
    for arguments, message in ((['--scores', str(scores), '--out', str(out)], '--out exists'),
                               (['--scores', str(scores), '--out', str(tmp_path/'elsewhere.json')], 'under the repository'),
                               (['--out', str(out.with_name('x.json'))], 'needs --scores and --out'),
                               (['--scores', str(scores)], 'needs --scores and --out')):
        with pytest.raises(SystemExit):
            p1.main(['development', *arguments])
        assert message in capsys.readouterr().err
    bad = tmp_path/'bad.jsonl'
    bad.write_text(''.join(json.dumps(r) + '\n' for r in dev_study()[:-1]))
    with pytest.raises(SystemExit):
        p1.main(['development', '--scores', str(bad), '--out', str(tmp_path/'.runtime'/'bad.json')])
    assert 'must be re-judged' in capsys.readouterr().err and not (tmp_path/'.runtime'/'bad.json').exists()
