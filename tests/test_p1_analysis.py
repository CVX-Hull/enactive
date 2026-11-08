"""The P1 study's frozen analysis (#491): probe selection, completeness, the decision rule and its guards."""
import pytest

from tools import p1_analysis as p1

HOURS = {'lh1': 20.0, 'lh2': 20.0, 'lh3': 0.5}


def probes(per_boundary=6, boundaries=4, informative=True):
    rows = []
    for name in ('lh1', 'lh2'):
        for b in range(boundaries):
            for i in range(per_boundary):
                rows.append(dict(schema=p1.PROBES_SCHEMA, lineage=name, boundary=f'{name}-{b:03d}>{name}-{b + 1:03d}',
                                 id=f'{name}-{b}-{i}', confirmed=True, informative=informative))
    return rows


def labels(rows, rates, rejudge=None):
    """rates: arm+repeat -> share of each boundary's probes stated (the first ones in order)."""
    out = []
    for key, rate in rates.items():
        arm, rep = key[0], int(key[1])
        by_boundary = {}
        for row in rows:
            by_boundary.setdefault(row['boundary'], []).append(row)
        for group in by_boundary.values():
            for i, row in enumerate(group):
                out.append(dict(type='label', schema=p1.SCORE_SCHEMA, kind='reobservation', arm=arm, repeat=rep,
                                item=row['id'], stated=i < round(rate * len(group))))
    return out + (rejudge or [])


def guards_ok():
    return ([dict(type='audit', arm='A', repeat=1, false=False)] * 20
            + [dict(type='audit', arm='B', repeat=r, false=i == 0) for r in (1, 2) for i in range(20)]
            + [dict(type='cost', repeat=r, curator_dollars=15.0, actor_dollars=30.0) for r in (1, 2)])


def test_a_clear_gain_within_every_guard_is_a_go():
    rows = probes()
    result = p1.score(rows, HOURS, labels(rows, {'A1': 1 / 3, 'B1': 2 / 3, 'B2': 2 / 3}) + guards_ok())
    assert result['decision']['go'] is True
    assert result['decision']['mean_delta'] == pytest.approx(1 / 3)
    assert result['figures']['A1']['undelivered_per_game_hour'] == pytest.approx(32 / 40.5)


@pytest.mark.parametrize('rates, outcome', [
    ({'A1': 0.5, 'B1': 0.5, 'B2': 0.3}, 'negative'),
    ({'A1': 0.5, 'B1': 0.6, 'B2': 0.6}, 'inconclusive'),     # above A everywhere, but +0.10 is under the threshold
    ({'A1': 0.3, 'B1': 1.0, 'B2': 0.3}, 'inconclusive'),     # a large mean gain, but one repeat not above A
])
def test_no_go_without_a_large_consistent_gain(rates, outcome):
    rows = probes(per_boundary=10)
    result = p1.score(rows, HOURS, labels(rows, rates) + guards_ok())
    assert result['decision']['go'] is False
    assert result['decision']['outcome'].startswith(outcome)


def test_a_failed_guard_blocks_a_go_and_says_so():
    rows = probes()
    costly = [r for r in guards_ok() if r['type'] != 'cost'] + [
        dict(type='cost', repeat=r, curator_dollars=40.0, actor_dollars=30.0) for r in (1, 2)]
    result = p1.score(rows, HOURS, labels(rows, {'A1': 1 / 3, 'B1': 2 / 3, 'B2': 2 / 3}) + costly)
    assert result['decision']['go'] is False
    assert result['decision']['outcome'].startswith('guard failed')
    assert result['decision']['guards']['1']['checks']['cost'] is False


def test_a_gain_that_rejudging_removes_is_not_a_go():
    rows = probes()
    first = labels(rows, {'A1': 1 / 3, 'B1': 2 / 3, 'B2': 2 / 3})
    flipped = [dict(row, rejudge=True, stated=False) for row in first if row['arm'] == 'B' and row['stated']]
    result = p1.score(rows, HOURS, first + flipped + guards_ok())
    assert result['decision']['robust_to_rejudging'] is False and result['decision']['go'] is False


def test_only_confirmed_informative_probes_count():
    rows = probes() + [dict(schema=p1.PROBES_SCHEMA, lineage='lh1', boundary='lh1-000>lh1-001', id='empty',
                            confirmed=True, informative=False)]
    result = p1.score(rows, HOURS, labels(probes(), {'A1': 1 / 3, 'B1': 2 / 3, 'B2': 2 / 3}) + guards_ok())
    assert result['probes'] == dict(listed=49, primary=48)


@pytest.mark.parametrize('mutate, match', [
    (lambda rows: rows[:-1], 'do not cover'),
    (lambda rows: rows + [rows[0]], 'judged twice'),
    (lambda rows: rows + [dict(rows[0], arm='C')], 'outside the study'),
    (lambda rows: rows + [dict(rows[0], rejudge=True, item='never')], 'never judged'),
])
def test_incomplete_or_malformed_labels_are_refused(mutate, match):
    rows = probes()
    with pytest.raises(p1.ScoreError, match=match):
        p1.score(rows, HOURS, mutate(labels(rows, {'A1': 0.5, 'B1': 0.5, 'B2': 0.5})))


def test_development_lineages_are_never_scored():
    rows = [dict(r, lineage='397') for r in probes()]
    with pytest.raises(p1.ScoreError, match='held-out'):
        p1.score(rows, HOURS, [])


def test_the_tracked_power_simulation_reproduces():
    import json
    tracked = json.loads((p1.ROOT/'data'/'evaluation'/'p1'/'power.json').read_text())
    assert p1.simulate() == tracked
    # The frozen rule rarely fires without an effect and usually fires at the effect of interest.
    assert tracked['probability_of_go']['0.00'] <= 0.05 and tracked['probability_of_go']['0.25'] >= 0.75
