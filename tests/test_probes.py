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
                           needed=2, needed_carried=1)
    assert rows[1]['kind'] == 'admission' and rows[1]['live'] == 3 and rows[1]['carried'] == 1


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
