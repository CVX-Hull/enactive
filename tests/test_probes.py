"""Probe derivation and rates from synthetic annotations (probe-protocol/1)."""
import pytest

from harness.evaluation.core.probes import Lineage, ProbeError, agreement, boundary_kind, kappa


def fact(fid, statement='s', **extra):
    return dict(type='fact', id=fid, statement=statement, category='resource', observed='x-1', stored=None, **extra)


def carry(fid, boundary, carried, where='packet'):
    return dict(type='carry', fact=fid, boundary=boundary, carried=carried, where=where if carried else None)


def event(fid, kind):
    return dict(type='event', fact=fid, event=kind, frame='x-2', note='n')


END = dict(type='end', frames_viewed=3)


def lineage():
    a, b, c = 'r1-001', 'r1-002', 'r2-001'
    return Lineage.from_lines([
        (a, [fact('F1', 'water in the tank'), fact('F2', 'batteries in the locker'), fact('F3'), END]),
        (b, [carry('F1', f'{a}>{b}', False), carry('F2', f'{a}>{b}', True), carry('F3', f'{a}>{b}', False),
             event('F1', 'acted_without'), event('F1', 'needed'), event('F2', 'used'), event('F2', 'needed'),
             event('F3', 'invalidated'), fact('F4'), END]),
        (c, [carry('F1', f'{b}>{c}', False), carry('F2', f'{b}>{c}', False), carry('F4', f'{b}>{c}', True),
             event('F2', 'rediscovered'), event('F2', 'needed'), event('F4', 'used'), END]),
    ])


def test_probes_fail_only_when_the_needed_fact_was_not_carried():
    probes = lineage().probes()
    by = {(p.boundary, p.fact): p for p in probes}
    assert by[('r1-001>r1-002', 'F1')].failing and by[('r1-001>r1-002', 'F1')].costly
    assert not by[('r1-001>r1-002', 'F2')].failing and not by[('r1-001>r1-002', 'F2')].costly
    assert by[('r1-002>r2-001', 'F2')].failing and by[('r1-002>r2-001', 'F2')].costly
    assert ('r1-002>r2-001', 'F4') not in by  # used but never needed: no probe
    assert len(probes) == 3


def test_carry_rates_count_live_facts_and_exclude_invalidated_ones():
    rows = lineage().boundary_rows()
    assert rows[0] == dict(boundary='r1-001>r1-002', kind='handoff', live=3, carried=1, unlabelled=[],
                           held=3, held_carried=1, needed=2, needed_carried=1)
    assert rows[1]['kind'] == 'admission' and rows[1]['live'] == 3 and rows[1]['carried'] == 1


def test_retention_counts_only_what_the_predecessor_held():
    a, b, c = 'r-001', 'r-002', 'r-003'
    rows = Lineage.from_lines([
        (a, [fact('F1'), fact('F2'), END]),
        (b, [carry('F1', f'{a}>{b}', False), carry('F2', f'{a}>{b}', True), END]),
        (c, [carry('F1', f'{b}>{c}', False), carry('F2', f'{b}>{c}', True), END]),
    ]).boundary_rows()
    # F1 was lost at the first boundary; the second boundary is charged only for what r-002 held.
    assert (rows[1]['live'], rows[1]['carried'], rows[1]['held'], rows[1]['held_carried']) == (2, 1, 1, 1)


def test_cost_is_charged_only_in_the_chunk_that_needed_the_fact():
    a, b, c = 'r-001', 'r-002', 'r-003'
    probes = Lineage.from_lines([
        (a, [fact('F1'), END]),
        (b, [carry('F1', f'{a}>{b}', False), event('F1', 'needed'), END]),
        (c, [carry('F1', f'{b}>{c}', False), event('F1', 'rediscovered'), event('F1', 'needed'), END]),
    ]).probes()
    assert [(p.boundary, p.failing, p.costly) for p in probes] == [(f'{a}>{b}', True, False), (f'{b}>{c}', True, True)]


def test_a_fact_observed_and_needed_in_one_chunk_yields_no_probe():
    probes = Lineage.from_lines([('r-001', [END]), ('r-002', [fact('F1'), event('F1', 'needed'), END])]).probes()
    assert probes == []


@pytest.mark.parametrize('second, message', [
    ([carry('F9', 'r-001>r-002', False), END], 'not live'),
    ([carry('F1', 'r-001>r-002', False), carry('F1', 'r-001>r-002', True), END], 'second carry'),
    ([dict(type='carry', boundary='r-001>r-002', carried=False), END], 'names its fact'),
])
def test_carry_lines_must_be_single_and_for_live_facts(second, message):
    with pytest.raises(ProbeError, match=message):
        Lineage.from_lines([('r-001', [fact('F1'), END]), ('r-002', second)])
    invalidated = [carry('F1', 'r-002>r-003', False), END]
    with pytest.raises(ProbeError, match='not live'):
        Lineage.from_lines([('r-001', [fact('F1'), END]),
                            ('r-002', [carry('F1', 'r-001>r-002', True), event('F1', 'invalidated'), END]),
                            ('r-003', invalidated)])


def test_the_tracked_baseline_reproduces_from_the_tracked_annotations(tmp_path):
    from pathlib import Path
    import json
    from tools import probe_baseline
    tracked = Path(probe_baseline.ROOT)/'data'/'evaluation'/'probes'
    assert probe_baseline.main(['--out', str(tmp_path/'baseline.json')]) == 0
    assert json.loads((tmp_path/'baseline.json').read_text()) == json.loads((tracked/'baseline.json').read_text())


def test_the_tracked_episodes_validate_and_malformed_ones_are_refused():
    from pathlib import Path
    import json
    from harness.evaluation.core.probes import episodes
    from tools import probe_baseline
    tracked = json.loads((Path(probe_baseline.ROOT)/'data'/'evaluation'/'probes'/'397'/'episodes.json').read_text())
    assert [e['id'] for e in episodes(tracked)] == ['batteries', 'fishing-rod', 'rations', 'roof-tank']
    for broken in ({**tracked, 'schema': 'probe-episodes/2'}, {**tracked, 'episodes': []},
                   {**tracked, 'episodes': [{**tracked['episodes'][0], 'extra': 1}]},
                   {**tracked, 'episodes': [{**tracked['episodes'][0], 'needed': {'chunk': 'x', 'frame': None}}]}):
        with pytest.raises(ProbeError):
            episodes(broken)


def test_adjudication_rows_must_name_a_chunk_of_the_lineage(tmp_path, monkeypatch):
    import json
    from tools import probe_baseline
    probes = tmp_path/'probes'
    (probes/'x').mkdir(parents=True)
    (probes/'x'/'x-001.jsonl').write_text(json.dumps(fact('F1')) + '\n' + json.dumps(END) + '\n')
    (probes/'x'/'adjudication.jsonl').write_text(json.dumps(dict(event('F1', 'needed'), chunk='x-009')) + '\n')
    monkeypatch.setitem(probe_baseline.LINEAGES, 'x', ['x-001'])
    with pytest.raises(ProbeError, match='name no chunk'):
        probe_baseline._lineage(probes, 'x', adjudicated=True)


def test_rediscovery_counts_only_facts_known_before_a_boundary():
    assert lineage().rediscoveries() == 1
    assert lineage().frames_viewed() == 9


def test_missing_carry_labels_are_reported_not_assumed():
    a, b = 'r-001', 'r-002'
    rows = Lineage.from_lines([(a, [fact('F1'), END]), (b, [END])]).boundary_rows()
    assert rows[0]['unlabelled'] == ['F1'] and rows[0]['carried'] == 0


@pytest.mark.parametrize('lines, message', [
    ([fact('X1'), END], 'fact id'),
    ([dict(fact('F1'), category='weather'), END], 'category'),
    ([fact('F1'), fact('F1'), END], 'duplicate'),
    ([fact('F1')], 'end line'),
    ([END, fact('F1')], 'before the end line'),
    ([dict(type='note'), END], 'unknown line type'),
    ([event('F9', 'used'), END], 'unknown fact'),
    ([fact('F1'), dict(event('F1', 'remembered')), END], 'unknown event'),
])
def test_malformed_annotations_are_rejected(lines, message):
    with pytest.raises(ProbeError, match=message):
        Lineage.from_lines([('r-001', lines)])


def test_carry_lines_must_name_the_incoming_boundary_and_where():
    with pytest.raises(ProbeError, match='wrong boundary'):
        Lineage.from_lines([('r-001', [fact('F1'), END]), ('r-002', [carry('F1', 'r-000>r-002', False), END])])
    with pytest.raises(ProbeError, match='names where'):
        Lineage.from_lines([('r-001', [fact('F1'), END]),
                            ('r-002', [carry('F1', 'r-001>r-002', True, where='memory'), END])])
    with pytest.raises(ProbeError, match='reused'):
        Lineage.from_lines([('r-001', [fact('F1'), END]), ('r-002', [fact('F1'), END])])


def test_summary_derives_rates_from_the_annotations():
    from harness.evaluation.core.probes import summary
    result = summary('r', lineage(), game_hours=2.0)
    assert result['schema'] == 'probe-baseline/1' and result['facts'] == 4 and result['frames_viewed'] == 9
    assert result['carry']['handoff']['carry_rate'] == 1 / 3 and result['carry']['admission']['carried'] == 1
    assert result['carry']['pooled']['live'] == 6 and result['carry']['pooled']['needed_carry_rate'] == 1 / 3
    assert result['probes'] == dict(total=3, failing=2, failing_with_cost=2)
    assert result['rediscoveries_per_game_hour'] == 0.5


def test_boundary_kinds_and_agreement():
    assert boundary_kind('sd1a3-001>sd1a3-002') == 'handoff'
    assert boundary_kind('sd1a3-002>sd1a4-001') == 'admission'
    assert kappa([(True, True), (False, False)]) == 1.0
    assert kappa([(True, False), (False, True)]) == -1.0
    assert kappa([(True, True), (True, True)]) is None and kappa([]) is None
    assert agreement([(True, True), (True, False)]) == dict(n=2, percent=0.5, kappa=0.0)
