"""Level-stage analysis on synthetic retained runs of the current contracts; negative cases for every version gate."""
import json
from pathlib import Path
import sqlite3

import pytest

from stage_support import (ACTOR, BASE, LEVEL_READER, RECORDER_READER, SESSION, PlayerStore, claim_record, correction_record, iso,
                           level_pass, make_run, recorder_pass, work_record)
from tools import level_stage_analysis as lsa

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = dict(schema='level-stage-criteria/1', min_decided=3, min_auditable_records=1, min_commit_rate=.6,
                max_commit_inputs_since_p95=10, bootstrap_seed=7, bootstrap_resamples=200)


def criteria_file(tmp_path, **changes):
    path = tmp_path / 'criteria.json'
    path.write_text(json.dumps(dict(CRITERIA, **changes)))
    return path


def mixed_level():
    return [level_pass(1, 'commit', action='replace', inputs_since=2, reason='start'),
            level_pass(2, 'commit', action='keep', inputs_since=4),
            level_pass(3, 'discard'),
            level_pass(4, 'discard', discard='Run stopped or fenced since the pass began'),
            level_pass(5, 'abstain', reason='start'),
            level_pass(6, 'none', ending='level-no-proposal', ok=False),
            level_pass(7, 'none', ending='cancelled', ok=False),
            level_pass(8, 'uncertain', outcome='absent'),
            level_pass(9, 'uncertain', action='replace', outcome='committed')]


def test_the_harness_still_words_the_censoring_discard_this_way():
    # The frozen classification depends on this exact reason; a rewording must change the tool, not silently reclassify.
    assert lsa.CENSORED[0] in (ROOT / 'harness/application.py').read_text()


@pytest.mark.parametrize('events,ending,wall,expected', [
    ([dict(type='level-commit')], None, 5, ('committed', None)),
    ([dict(type='level-uncertain')], None, 5, ('uncertain', None)),
    ([], 'level-uncertain', 5, ('uncertain', None)),
    ([dict(type='level-abstain')], None, 5, ('abstained', None)),
    ([dict(type='level-discard', reason='Run stopped or fenced since the pass began')], None, 5, ('censored', None)),
    ([dict(type='level-discard', reason='Current subgoal changed since the pass began')], None, 5, ('discarded_only', None)),
    ([], 'cancelled', 5, ('censored', None)),
    ([], 'cancelled', 59, ('failed', 'cancelled')),
    ([], 'level-final-refusal', 5, ('failed', 'level-final-refusal')),
    ([], None, 5, ('failed', 'unsettled')),
])
def test_every_pass_falls_in_exactly_one_class(events, ending, wall, expected):
    assert lsa.pass_class(events, ending, wall, 60) == expected


def test_a_consistent_run_is_classified_and_pooled(tmp_path):
    run = make_run(tmp_path, 'run-1', mixed_level(), [recorder_pass(1, 'record'), recorder_pass(2, 'abstain', code='unreadable_frames')])
    value = lsa.analyse([run], lsa.load_criteria(criteria_file(tmp_path)))
    pooled, decision = value['pooled'], value['decision_inputs']
    assert value['schema'] == 'level-stage-analysis/5'
    assert value['runs'][0]['receipt_mismatches'] == [] and decision['counts_consistent'] is True
    # Two trace commits and one lost call reconciled as committed; one non-censored discard is a decided failure.
    assert (pooled['commits'], pooled['failures'], pooled['censored'], pooled['decided']) == (3, 1, 1, 4)
    assert pooled['commits_by_action'] == dict(keep=1, replace=2, close=0, other=0)
    assert (pooled['passes'], pooled['committed_passes'], pooled['uncertain_passes'], pooled['censored_passes']) == (9, 2, 2, 2)
    assert pooled['failed_by_reason'] == {'level-no-proposal': 1}
    # Rated passes exclude the two censored and the two uncertain: 2 committed of 5.
    assert pooled['pass_success'] == pytest.approx(2 / 5) and pooled['commit_rate'] == pytest.approx(3 / 4)
    assert pooled['commit_rate_lower_bound'] == pytest.approx(3 / 5)
    assert pooled['inputs_since_commits']['max'] == 4 and pooled['recorder_trace_counts']['records'] == 1
    assert pooled['abstain_codes'] == {'other': 1}
    assert decision['E_decided_ok'] is True and decision['R1_commit_rate_ok'] is True and decision['R2_coupling_ok'] is True
    # No retained store was named: custody and auditable records are undecided, not assumed.
    assert pooled['auditable_records'] is None and decision['R4_custody_ok'] is None and decision['E_minimum_data'] is None
    # The commit-only p95 is below S by construction, so a limit at or above S cannot fire.
    assert decision['R2_vacuous'] is True


def test_the_decision_inputs_follow_the_frozen_criteria_not_the_code(tmp_path):
    run = make_run(tmp_path, 'run-1', mixed_level())
    base = lsa.analyse([run], lsa.load_criteria(criteria_file(tmp_path)))['decision_inputs']
    strict = lsa.analyse([run], lsa.load_criteria(criteria_file(tmp_path, min_decided=5, min_commit_rate=.9,
                                                                 max_commit_inputs_since_p95=4)))['decision_inputs']
    assert (base['E_decided_ok'], base['R1_commit_rate_ok'], base['R2_coupling_ok']) == (True, True, True)
    assert (strict['E_decided_ok'], strict['R1_commit_rate_ok'], strict['R2_coupling_ok'], strict['R2_vacuous']) == (False, False, False, False)
    assert strict['E_minimum_data'] is False


def test_the_receipt_check_lists_every_disagreement(tmp_path):
    run = make_run(tmp_path, 'run-1', mixed_level(), [recorder_pass(1, 'record')], level_overrides=dict(commits=5, discards=0),
                   recorder_overrides=dict(records=3))
    value = lsa.analyse([run], lsa.load_criteria(criteria_file(tmp_path)))
    fields = {(m['source'], m['field']) for m in value['pooled']['receipt_count_mismatches']}
    assert fields == {('driver receipt', 'commits'), ('driver receipt', 'discards'), ('recorder driver receipt', 'records')}
    assert value['decision_inputs']['counts_consistent'] is False


def test_a_pass_whose_driver_events_differ_from_its_own_trace_is_listed(tmp_path):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')])
    receipt = json.loads((run / 'receipt.json').read_text())
    receipt['driver']['actors'][0]['level']['level']['passes'][0]['level_events'] = []
    (run / 'receipt.json').write_text(json.dumps(receipt))
    mismatches = lsa.analyse_run(run)['receipt_mismatches']
    assert [m['source'] for m in mismatches] == ['pass level_events']


def test_an_unreconciled_lost_call_makes_the_counts_inconsistent(tmp_path):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'uncertain', outcome='unreconciled')])
    mismatches = lsa.analyse_run(run)['receipt_mismatches']
    assert any(m['field'] == 'uncertain_unreconciled' for m in mismatches)


# ---------------------------------------------------------------- version gates

@pytest.mark.parametrize('overrides,message', [
    (dict(manifest='campaign-run/4'), 'manifest'),
    (dict(receipt='campaign-receipt/1'), 'receipt'),
    (dict(driver='player-driver/5'), 'driver receipt'),
])
def test_an_unsupported_artifact_version_is_rejected(tmp_path, overrides, message):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')], schema_overrides=overrides)
    with pytest.raises(lsa.UnsupportedTrace, match=message):
        lsa.analyse_run(run)


@pytest.mark.parametrize('schema,telemetry', [('player-host/5', 2), ('player-host/6', 1), ('pi-player-host/5', 2)])
def test_an_unsupported_host_trace_is_rejected(tmp_path, schema, telemetry):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')])
    trace = run / 'actors/001/level/001/host.jsonl'
    trace.write_text(trace.read_text().replace('"player-host/6"', json.dumps(schema)).replace('"telemetry_version": 2', f'"telemetry_version": {telemetry}'))
    with pytest.raises(lsa.UnsupportedTrace, match='host trace'):
        lsa.analyse_run(run)


def test_a_trace_without_host_start_is_a_valid_pass_and_a_missing_one_is_unsettled(tmp_path):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'none', ending='level-no-proposal', ok=False), level_pass(2, 'none', ok=None)])
    (run / 'actors/001/level/001/host.jsonl').write_text('')
    (run / 'actors/001/level/002/host.jsonl').unlink()
    passes = lsa.analyse_run(run)['passes']
    assert [p['pass_class'] for p in passes] == ['failed', 'failed']


def test_the_session_store_must_be_the_current_version(tmp_path):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')])
    db = sqlite3.connect(run / 'session.sqlite3')
    db.execute('PRAGMA user_version=2')
    db.close()
    with pytest.raises(ValueError, match='version'):
        lsa.analyse_run(run)


def test_two_actors_or_no_level_or_a_missing_lane_receipt_are_unsupported(tmp_path):
    run = make_run(tmp_path, 'two', [level_pass(1, 'commit')])
    receipt = json.loads((run / 'receipt.json').read_text())
    receipt['driver']['actors'].append(receipt['driver']['actors'][0])
    (run / 'receipt.json').write_text(json.dumps(receipt))
    with pytest.raises(lsa.UnsupportedTrace, match='exactly one'):
        lsa.analyse_run(run)
    run = make_run(tmp_path, 'nolevel', [level_pass(1, 'commit')])
    (run / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/5', session=SESSION, level=None)))
    with pytest.raises(lsa.UnsupportedTrace, match='no level'):
        lsa.analyse_run(run)
    run = make_run(tmp_path, 'old', [level_pass(1, 'commit')])
    receipt = json.loads((run / 'receipt.json').read_text())
    actor = receipt['driver']['actors'][0]
    actor['level'] = actor['level']['level']      # the earlier shape: the lane receipt directly under `level`
    (run / 'receipt.json').write_text(json.dumps(receipt))
    with pytest.raises(lsa.UnsupportedTrace, match='level and recorder receipts'):
        lsa.analyse_run(run)


@pytest.mark.parametrize('changes', [dict(schema='level-stage-criteria/0'), dict(extra=1), dict(min_decided=-1), dict(min_decided='20'),
                                     dict(bootstrap_resamples=0), dict(bootstrap_seed=1.5)])
def test_criteria_are_closed_typed_and_never_defaulted(tmp_path, changes):
    with pytest.raises(lsa.UnsupportedTrace):
        lsa.load_criteria(criteria_file(tmp_path, **changes))
    path = tmp_path / 'missing.json'
    path.write_text(json.dumps({k: v for k, v in CRITERIA.items() if k != 'min_commit_rate'}))
    with pytest.raises(lsa.UnsupportedTrace, match='min_commit_rate'):
        lsa.load_criteria(path)


# ---------------------------------------------------------------- the retained player store

def store_for(tmp_path, *, name='player', stray=False, software=True, tombstone=None, other_tool=False, claims=None):
    store = PlayerStore(tmp_path / f'{name}.sqlite3')
    (work,) = store.commit(LEVEL_READER, 'player_level_replace', 'replace', [work_record()])
    store.commit(LEVEL_READER, 'player_level_keep', 'keep', [])
    if claims is None:
        store.commit(RECORDER_READER, 'player_episode_record', 'record', [claim_record('recorded')], writer=RECORDER_READER)
    if software:
        store.software(RECORDER_READER, [claim_record('failed', 3, 3)])
    if stray:
        store.software(LEVEL_READER, [correction_record('stray', work['id'])])
    if tombstone:
        store.tombstone(LEVEL_READER, 'player_level_replace', tombstone)
    if other_tool:
        store.commit(LEVEL_READER, 'player_source', 'keep', [])
    return store.path


def custody_run(tmp_path, name='run-1', **settles):
    level = [level_pass(1, 'commit', action='replace'), level_pass(2, 'commit', action='keep')]
    episodes = dict(cut=2, closed_by={}, settled=settles or dict(recorded=1, failed=1), max_waiting=0, backlog=3, waiting_unsettled=0,
                    next_position=4, open_inputs=0)
    return make_run(tmp_path, name, level, [recorder_pass(1, 'record')], episodes=episodes)


def test_a_consistent_store_passes_custody_and_counts_the_auditable_replace(tmp_path):
    run = custody_run(tmp_path)
    result = lsa.analyse_run(run, store_for(tmp_path))
    assert result['receipt_mismatches'] == []
    assert result['content']['auditable_records'] == 1 and result['content']['committed_by_action'] == {'replace': 1, 'keep': 1}
    assert result['content']['episode_claims_by_settle'] == dict(recorded=1, failed=1)
    assert result['custody'] == dict(reader_operations=0, readers=2, reader_non_level_writes=0, reader_other_service_rows=0)
    value = lsa.analyse([run], lsa.load_criteria(criteria_file(tmp_path)), str(tmp_path / 'player.sqlite3'))
    assert value['decision_inputs']['R4_custody_ok'] is True and value['decision_inputs']['E_auditable_ok'] is True


def test_a_reader_record_outside_its_service_result_violates_custody(tmp_path):
    result = lsa.analyse_run(custody_run(tmp_path), store_for(tmp_path, stray=True))
    assert result['custody']['reader_non_level_writes'] == 1


def test_a_reader_service_row_for_another_tool_or_an_unexcused_tombstone_violates_custody(tmp_path):
    result = lsa.analyse_run(custody_run(tmp_path), store_for(tmp_path, other_tool=True))
    assert result['custody']['reader_other_service_rows'] == 1
    result = lsa.analyse_run(custody_run(tmp_path, 'second'), store_for(tmp_path, name='second', tombstone='f' * 32))
    assert result['custody']['reader_other_service_rows'] == 1


def test_a_tombstone_is_excused_only_for_a_recorded_lost_call(tmp_path):
    identity = '0' * 31 + 'e'
    level = [level_pass(1, 'commit', action='replace'), level_pass(2, 'commit', action='keep'), level_pass(3, 'uncertain', identity=identity, outcome='absent')]
    episodes = dict(cut=2, closed_by={}, settled=dict(recorded=1, failed=1), max_waiting=0, backlog=3, waiting_unsettled=0, next_position=4, open_inputs=0)
    run = make_run(tmp_path, 'run-1', level, [recorder_pass(1, 'record')], episodes=episodes)
    result = lsa.analyse_run(run, store_for(tmp_path, tombstone=identity))
    assert result['custody']['reader_other_service_rows'] == 0 and result['content']['tombstone_rows'] == 1
    assert result['receipt_mismatches'] == []


def test_the_store_must_agree_with_the_trace_about_commits_and_settles(tmp_path):
    run = custody_run(tmp_path, recorded=2, failed=0)
    fields = {m['field'] for m in lsa.analyse_run(run, store_for(tmp_path))['receipt_mismatches']}
    assert fields == {'episode settles'}
    run = make_run(tmp_path, 'run-2', [level_pass(1, 'commit', action='close')], [recorder_pass(1, 'record')])
    fields = {m['field'] for m in lsa.analyse_run(run, store_for(tmp_path, name='close'))['receipt_mismatches']}
    assert 'committed service rows of the three commit tools' in fields and 'committed service rows by action' in fields


def test_a_missing_or_unsupported_store_is_reported_not_trusted(tmp_path):
    run = custody_run(tmp_path)
    assert lsa.analyse_run(run, tmp_path / 'absent.sqlite3')['content'] == 'retained store missing'
    stale = tmp_path / 'stale.sqlite3'
    db = sqlite3.connect(stale)
    db.execute('CREATE TABLE metadata (schema TEXT)')
    db.close()
    with pytest.raises(lsa.UnsupportedTrace, match='player-memory/1'):
        lsa.analyse_run(run, stale)


# ---------------------------------------------------------------- refusal circuit breaker

def refusal_rows(tool, count, field='sources'):
    return [dict(type='tool-validation-feedback', tool=tool, projected_text=f'Invalid arguments\n  - {field}: too long') for _ in range(count)]


def breaker_run(tmp_path, specs, rows_for=None, name='run-1'):
    run = make_run(tmp_path, name, specs)
    for index, rows in (rows_for or {}).items():
        trace = run / f'actors/001/level/{index:03d}/host.jsonl'
        trace.write_text(trace.read_text() + '\n'.join(json.dumps(r) for r in rows) + '\n')
    return run


def test_three_identical_refusals_without_a_success_trip_the_breaker(tmp_path):
    run = breaker_run(tmp_path, [level_pass(1, 'none', ending='level-final-refusal', ok=False)], {1: refusal_rows('player_level_replace', 3)})
    result = lsa.circuit_breaker(run)
    assert result['tripped'] is True and result['worst'] == dict(tool='player_level_replace', field='sources', count=3)


def test_a_success_of_the_same_tool_or_fewer_refusals_do_not_trip_it(tmp_path):
    run = breaker_run(tmp_path, [level_pass(1, 'commit', action='replace'), level_pass(2, 'none', ending='level-no-proposal', ok=False)],
                      {2: refusal_rows('player_level_replace', 5)})
    assert lsa.circuit_breaker(run)['tripped'] is False
    run = breaker_run(tmp_path, [level_pass(1, 'none', ending='level-no-proposal', ok=False)],
                      {1: refusal_rows('player_level_replace', 2)}, name='few')
    assert lsa.circuit_breaker(run)['tripped'] is False


def test_a_refusal_after_the_pass_ended_is_not_a_refusal(tmp_path):
    rows = [dict(type='tool-refused', tool='player_level_replace', reason=reason) for reason in ('level-ended', 'handoff', 'episode-ended')] * 2
    run = breaker_run(tmp_path, [level_pass(1, 'none', ending='level-no-proposal', ok=False)], {1: rows})
    assert lsa.circuit_breaker(run)['refusals'] == {}
    rows = [dict(type='tool-refused', tool='player_level_replace', reason='level-reserved')] * 3
    run = breaker_run(tmp_path, [level_pass(1, 'none', ending='level-no-proposal', ok=False)], {1: rows}, name='reserved')
    assert lsa.circuit_breaker(run)['worst']['field'] == 'refused:level-reserved'


def test_custodian_errors_name_their_failing_fields(tmp_path):
    reason = 'Invalid player_level_replace arguments - text: too long; confidence: out of range\nFix the call'
    error = dict(type='tool-result', tool='player_level_replace', result=dict(isError=True, content=[dict(type='text', text=json.dumps(dict(reason=reason)))]))
    other = dict(type='tool-result', tool='player_level_replace', result=dict(isError=True, content=[dict(type='text', text='boom')]))
    keys = lsa.refusal_keys([error, other])
    assert keys == [('player_level_replace', 'text'), ('player_level_replace', 'confidence'), ('player_level_replace', 'custodian:boom')]


def test_the_breaker_reads_the_recorder_lane_and_credits_a_reconciled_lost_call(tmp_path):
    run = make_run(tmp_path, 'run-1', [], [recorder_pass(1, 'none', ending='episode-final-refusal', ok=False)])
    trace = run / 'actors/001/recorder/001/host.jsonl'
    trace.write_text(trace.read_text() + '\n'.join(json.dumps(r) for r in refusal_rows('player_episode_record', 3, 'observation_status')) + '\n')
    assert lsa.circuit_breaker(run, 'recorder')['tripped'] is True
    assert lsa.circuit_breaker(run, 'level')['tripped'] is False
    run = make_run(tmp_path, 'run-2', [], [recorder_pass(1, 'uncertain', outcome='committed')])
    trace = run / 'actors/001/recorder/001/host.jsonl'
    trace.write_text(trace.read_text() + '\n'.join(json.dumps(r) for r in refusal_rows('player_episode_record', 3, 'x')) + '\n')
    assert lsa.circuit_breaker(run, 'recorder')['tripped'] is False


# ---------------------------------------------------------------- clean exit

def exit_run(tmp_path, *, last_status='completed', exit_after_send=4.0, extra_op=False, name='exit', **receipt):
    run = make_run(tmp_path, name, [level_pass(1, 'commit')], receipt_extra=receipt,
                   settled=dict(ok=True, reason='cancelled', wall_time=iso(BASE + 6 + 45 + exit_after_send)))
    db = sqlite3.connect(run / 'session.sqlite3')
    ops = [r[0] for r in db.execute('SELECT id FROM operations ORDER BY rowid')]
    with db:
        for op in ops:
            db.execute('INSERT INTO native_intents VALUES(?,?,?,?,?)', (f'n{op[-4:]}', op, None, None, json.dumps(dict(send_finished_wall=BASE + 6))))
        if last_status != 'completed':
            final = json.loads(db.execute('SELECT final_json FROM operations WHERE id=?', (ops[-1],)).fetchone()[0])
            final.update(status=last_status, receipts=[dict(reason=lsa.EOF_REASON)])
            db.execute('UPDATE operations SET final_json=? WHERE id=?', (json.dumps(final), ops[-1]))
        if extra_op:
            db.execute("INSERT INTO operations VALUES(?,?,'observe',?,1e8,'[]',NULL)", ('f' * 32, ACTOR, BASE + 100))
    db.close()
    return run


def test_a_run_that_exits_just_after_its_last_input_is_a_clean_exit(tmp_path):
    run = exit_run(tmp_path)
    holds, facts = lsa.clean_exit(run, json.loads((run / 'receipt.json').read_text()), True)
    assert holds is True and facts['exit_seconds_after_last_send'] == pytest.approx(4.0) and facts['input_operations'] == 6


def test_the_last_input_may_be_unknown_only_with_the_native_eof(tmp_path):
    run = exit_run(tmp_path, last_status='unknown')
    assert lsa.clean_exit(run, json.loads((run / 'receipt.json').read_text()), True)[0] is True
    run = exit_run(tmp_path, last_status='refused', name='refused')
    assert lsa.clean_exit(run, json.loads((run / 'receipt.json').read_text()), True)[1]['inputs_delivered_before_exit'] is False


@pytest.mark.parametrize('changes', [dict(exit_after_send=30.0), dict(exit_after_send=-3.0), dict(extra_op=True),
                                     dict(normal_native_exit_zero=False), dict(native_absence_verified=False), dict(input_authority_revoked=False),
                                     dict(deciding_hosts_quiescent=False)])
def test_any_broken_exit_fact_withholds_inclusion(tmp_path, changes):
    run = exit_run(tmp_path, **changes)
    holds, facts = lsa.clean_exit(run, json.loads((run / 'receipt.json').read_text()), True)
    assert holds is False
    assert lsa.clean_exit(run, json.loads((run / 'receipt.json').read_text()), False)[0] is False


# ---------------------------------------------------------------- command line

def test_the_command_records_its_inputs_and_refuses_to_overwrite(tmp_path, capsys):
    run = make_run(tmp_path, 'run-1', mixed_level())
    criteria, output = criteria_file(tmp_path), tmp_path / 'out.json'
    assert lsa.main([str(output), str(run), '--criteria', str(criteria)]) == 0
    value = json.loads(output.read_text())
    assert value['criteria_sha256'] == lsa.sha256(criteria) and value['code_sha256'] == lsa.sha256(Path(lsa.__file__)) and value['criteria'] == CRITERIA
    assert lsa.main([str(output), str(run), '--criteria', str(criteria)]) == 1
    assert 'failed' in capsys.readouterr().err


def test_the_command_exits_two_for_an_unsupported_version_and_writes_nothing(tmp_path, capsys):
    run = make_run(tmp_path, 'old', [level_pass(1, 'commit')], schema_overrides=dict(driver='player-driver/5'))
    output = tmp_path / 'out.json'
    assert lsa.main([str(output), str(run), '--criteria', str(criteria_file(tmp_path))]) == 2
    assert not output.exists() and 'unsupported' in capsys.readouterr().err
