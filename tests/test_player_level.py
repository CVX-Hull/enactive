"""Reader custody, the player log projection and the software-mediated level commit.

Actual composition, SQLite and HTTP over a receiver double; no provider, game or level host.
"""
import json
from pathlib import Path
from unittest.mock import patch
import uuid

import pytest

from harness.application import Application
from harness.computer.protocol import ControlError
from harness.player.contracts import PlayerError
from harness.player.memory import Memory
from harness.player_client import PlayerClient
from harness.player_tools import PROFILES
from harness.server import serve
from test_computer_runtime import key, make_runtime
from test_server import post

S = 3


def request_id():
    return uuid.uuid4().hex


@pytest.fixture
def level(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    actor = app.add_actor('narrowed')
    reader = app.add_reader(actor['actor_id'], staleness_inputs=S)
    try:
        yield app, channel, actor, reader
    finally:
        runtime.close(); memory.close()


def call(app, capability, name, args, identity=None):
    return app.call(capability['token'], name, args, identity or request_id())[0]


KEEP, REPLACE, CLOSE, ABSTAIN = ('player_level_keep', 'player_level_replace', 'player_level_close',
                                 'player_level_abstain')


def keep(reason='Cited log entries', sources=()):
    return dict(reason=reason, sources=list(sources))


def close(outcome='achieved', reason='Cited log entries', sources=()):
    return dict(outcome=outcome, reason=reason, sources=list(sources))


def replace(text='Reach the visible door', sources=(), outcome='none', reason='', **change):
    """A flat replace call; `outcome` and `reason` say what happened to the subgoal it replaces."""
    return dict(text=text, expected_observations=['The door tile is adjacent'], status='open', confidence=.4,
                sources=list(sources), previous_outcome=outcome, previous_reason=reason, **change)


def supersede(text='Next', outcome='revised', sources=()):
    return replace(text, sources, outcome, 'Cited log entries')


def read_all(app, reader, after=0):
    return call(app, reader, 'player_log_read', dict(after=after, limit=50))


def store_rows(app):
    return (app.memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0],
            app.memory._db.execute('SELECT COUNT(*) FROM service_operations').fetchone()[0])


def source_rows(app):
    return app.memory._db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]


@pytest.mark.parametrize('name,args', [
    ('computer_observe', {}), ('computer_input', dict(actions=[key()])), ('computer_stop', {}),
    ('player_handoff', {}), ('player_program_save', dict(program={})), ('player_program_run', {}),
    ('player_memory_append', dict(record={}))])
def test_reader_class_cannot_send_input_stop_observe_seal_or_write_directly(level, name, args):
    app, channel, actor, reader = level
    # Either barrier may refuse first: runtime write authorization or the class allowlist.
    with pytest.raises(ControlError, match='capability'):
        call(app, reader, name, args)
    # The allowlist alone still refuses when runtime authorization is bypassed.
    with patch.object(app.runtime, 'authorize', return_value=reader['actor_id']), \
            pytest.raises(ControlError, match='capability class'):
        call(app, reader, name, args)
    assert channel.calls == [] and not channel.stopped.is_set()
    assert app.runtime.actor_stage(actor['actor_id']) == 'active'
    assert store_rows(app) == (0, 0)


def test_reader_cannot_request_stop_over_http_either(level):
    app, channel, actor, reader = level
    server, thread = serve(app, 0)
    try:
        status, value = post(server.server_port, '/api/actor-stop',
                             dict(session=app.runtime.session, reason='reader'), reader['token'])
        assert status == 400 and not channel.stopped.is_set()
        status, _ = post(server.server_port, '/api/tool', dict(operation_id=request_id(), tool='computer_input',
                         arguments=dict(actions=[key()])), reader['token'])
        assert status == 400 and channel.calls == []
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


@pytest.mark.parametrize('profile', ['flat', 'narrowed'])
def test_actors_are_refused_the_level_tools(tmp_path, profile):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        actor = app.add_actor(profile)
        for name, args in (('player_log_read', dict(after=0, limit=1)), (KEEP, keep()), (REPLACE, replace()),
                           (CLOSE, close()), (ABSTAIN, dict(reason_code='other', reason='none', sources=[]))):
            with pytest.raises(ControlError, match='capability'):
                call(app, actor, name, args)
        assert store_rows(app) == (0, 0)
    finally:
        runtime.close(); memory.close()


def test_narrowed_actor_acts_but_has_no_memory_writes_or_program_save(level):
    app, channel, actor, _ = level
    assert call(app, actor, 'computer_input', dict(actions=[key()]))['status'] == 'completed'
    for name in ('player_memory_append', 'player_memory_query', 'player_memory_read',
                 'player_memory_context', 'player_program_save'):
        with pytest.raises(ControlError, match='capability class'):
            call(app, actor, name, {})


def test_capability_minted_outside_the_composition_has_no_tools(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        with pytest.raises(ControlError, match='capability class'):
            call(app, actor, 'computer_observe', {})
        assert channel.calls == []
    finally:
        runtime.close(); memory.close()


def test_reader_serves_only_the_active_actor_once_and_never_blocks_succession(level):
    app, channel, actor, reader = level
    with pytest.raises(ControlError, match='already has its reader'):
        app.add_reader(actor['actor_id'], staleness_inputs=S)
    with pytest.raises(ControlError, match='narrowed-profile'):
        app.add_reader(reader['actor_id'], staleness_inputs=S)
    with pytest.raises(ControlError, match='Staleness'):
        app.add_reader(actor['actor_id'], staleness_inputs=0)
    sealed = call(app, actor, 'player_handoff', {})
    assert sealed['handoff']['schema'] == 'player-handoff/2'
    with pytest.raises(ControlError, match='only the active actor'):
        app.add_reader(actor['actor_id'], staleness_inputs=S)
    app.runtime.confirm_quiescent(actor['actor_id'], sealed['operation_id'], host_quiescent=True)
    # max_actors is 2: the live reader neither counts nor blocks the successor.
    successor = app.add_actor('narrowed')
    assert app.runtime.actor_stage(reader['actor_id']) == 'reader'
    assert {a['actor_id']: a['serves'] for a in app.status()['actors'] if a['stage'] == 'reader'} == {
        reader['actor_id']: actor['actor_id']}
    assert app.add_reader(successor['actor_id'], staleness_inputs=S)['actor_id'] != reader['actor_id']


def test_log_projection_is_scoped_ordered_and_marks_pending_and_handoff(level):
    app, channel, actor, reader = level
    assert read_all(app, reader) == dict(schema='player-log/1', session=app.runtime.session,
        actor_id=actor['actor_id'], after=0, entries=[], handoff=False, grants_authority=False)
    first = call(app, actor, 'computer_input', dict(actions=[key('a'), key('b')]))
    call(app, actor, 'computer_observe', {})
    # A retained intent with no terminal result is pending and has no source.
    pending = dict(schema='computer-operation/1', operation_id='c' * 32, session=app.runtime.session,
                   actor_id=actor['actor_id'], kind='input', created_wall=1., deadline_monotonic=1.)
    assert app.runtime.store.begin(pending, [key('c')], 1)
    log = read_all(app, reader)
    assert [(e['position'], e['kind'], e['status']) for e in log['entries']] == [
        (1, 'input', 'completed'), (2, 'observe', 'completed'), (3, 'input', 'pending')]
    assert log['entries'][0]['actions'] == [key('a'), key('b')] and log['entries'][1]['actions'] is None
    assert log['entries'][0]['source_id'] == first['source']['source_id'] and log['entries'][2]['source_id'] is None
    assert [e['position'] for e in read_all(app, reader, after=1)['entries']] == [2, 3]
    assert call(app, reader, 'player_log_read', dict(after=1, limit=1))['entries'][0]['position'] == 2
    for bad in (dict(after=-1, limit=1), dict(after=0, limit=0), dict(after=0, limit=51), dict(after=0)):
        with pytest.raises((PlayerError, ControlError)):
            call(app, reader, 'player_log_read', bad)
    app.runtime.store.finish(dict(pending, status='refused', receipts=[], source=None, remaining={},
                                  reason='fixture', handoff=None))
    call(app, actor, 'player_handoff', {})
    sealed = read_all(app, reader)
    assert sealed['entries'] == [] and sealed['handoff'] is True


def test_commit_binds_the_custodian_position_and_writes_one_work_record(level):
    app, channel, actor, reader = level
    observed = call(app, actor, 'computer_observe', {})
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    committed = call(app, reader, REPLACE, replace(sources=[observed['source']['source_id']]))
    assert committed['schema'] == 'player-level-commit/3'
    assert committed['status'] == 'committed' and committed['position'] == 2 and committed['inputs_since'] == 0
    (work,) = committed['records']
    assert work['kind'] == 'work' and work['actor_id'] == reader['actor_id'] and work['text'] == 'Reach the visible door'
    # Software stamps the contract version; the model supplied none.
    assert work['data'] == dict(level='subgoal', level_contract='player-level/3', actor_id=actor['actor_id'],
        session=app.runtime.session, position=2, expected_observations=['The door tile is adjacent'],
        status='open', confidence=.4)
    assert app.memory.read_source(observed['source']['source_id'])[1] == channel.png
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]


@pytest.mark.parametrize('tool,args', [(KEEP, keep()), (REPLACE, replace()), (CLOSE, close()),
                                       (ABSTAIN, dict(reason_code='other', reason='x', sources=[]))])
def test_model_supplied_position_id_or_version_is_refused(level, tool, args):
    app, channel, actor, reader = level
    read_all(app, reader)
    for change in (dict(position=7), dict(inputs_since=0), dict(record_id='r'), dict(schema='player-level-commit/3'),
                   dict(version=3)):
        with pytest.raises(PlayerError, match=next(iter(change))):
            call(app, reader, tool, dict(args, **change))
    assert store_rows(app) == (0, 0)


def test_commit_after_s_inputs_is_discarded_and_written_nowhere(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    for _ in range(S - 1):
        call(app, actor, 'computer_input', dict(actions=[key()]))
    call(app, actor, 'computer_observe', {})
    assert call(app, reader, REPLACE, replace())['status'] == 'committed'
    read_all(app, reader)
    for _ in range(S):
        call(app, actor, 'computer_input', dict(actions=[key()]))
    before = store_rows(app)
    discarded = call(app, reader, REPLACE, supersede('Later'))
    assert discarded == dict(schema='player-level-commit/3', status='discarded', action='replace',
        reason='Served actor moved at least S inputs past the read', position=S + 1, inputs_since=S,
        staleness_inputs=S, records=[], kept=[])
    assert store_rows(app) == before
    # The discard ended the pass: without a new read nothing binds.
    assert call(app, reader, REPLACE, supersede('Later'))['reason'] == 'No log read bound a position in this pass'


@pytest.mark.parametrize('tool,args,action', [(KEEP, keep(), 'keep'), (CLOSE, close(), 'close'),
                                              (REPLACE, supersede(), 'replace')])
def test_all_three_terminal_calls_obey_the_same_staleness_rule(level, tool, args, action):
    app, channel, actor, reader = level
    commit_first(app, actor, reader)
    read_all(app, reader)
    for _ in range(S):
        call(app, actor, 'computer_input', dict(actions=[key()]))
    before = store_rows(app)
    result = call(app, reader, tool, args)
    assert result['status'] == 'discarded' and result['action'] == action
    assert result['reason'] == 'Served actor moved at least S inputs past the read' and store_rows(app) == before


def test_commit_after_handoff_is_discarded(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    call(app, actor, 'player_handoff', {})
    result = call(app, reader, REPLACE, replace())
    assert result['status'] == 'discarded' and result['reason'] == 'Served actor handed off since the read'
    assert store_rows(app) == (0, 0)


def test_empty_delta_binds_nothing(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    assert read_all(app, reader, after=1)['entries'] == []
    result = call(app, reader, REPLACE, replace())
    assert result['status'] == 'discarded' and result['position'] is None
    assert store_rows(app) == (0, 0)


def commit_first(app, actor, reader):
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    return call(app, reader, REPLACE, replace())['records'][0]


def test_replace_without_a_current_subgoal_writes_one_work_record_and_no_correction(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    committed = call(app, reader, REPLACE, replace())
    assert committed['action'] == 'replace' and committed['kept'] == [] and len(committed['records']) == 1
    assert committed['records'][0]['kind'] == 'work'


def test_replace_with_a_previous_outcome_writes_work_and_a_superseding_correction(level):
    app, channel, actor, reader = level
    first = commit_first(app, actor, reader)
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    revised = call(app, reader, REPLACE, supersede('Next'))
    work, correction = revised['records']
    assert revised['status'] == 'committed' and revised['position'] == 2
    assert correction['kind'] == 'correction' and correction['supersedes'] == first['id']
    assert correction['text'] == 'Cited log entries' and correction['data']['level_contract'] == 'player-level/3'
    assert correction['supports'] == [work['id']] and correction['data']['outcome'] == 'revised'
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]
    read_all(app, reader)
    ended = call(app, reader, REPLACE, supersede('Last', 'failed'))
    assert ended['records'][1]['supports'] == [] and ended['records'][1]['data']['outcome'] == 'failed'
    assert [r['text'] for r in app.memory.current('work')] == ['Last']


def test_replace_cites_its_sources_on_both_records(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    work = call(app, reader, REPLACE, replace())['records'][0]
    read_all(app, reader)
    cited = first['source']['source_id']
    new, correction = call(app, reader, REPLACE, supersede('Next', 'achieved', [cited]))['records']
    assert new['sources'] == [cited] and correction['sources'] == [cited] and correction['supersedes'] == work['id']


def test_keep_writes_nothing_gives_the_current_id_and_close_records_its_outcome(level):
    app, channel, actor, reader = level
    work = commit_first(app, actor, reader)
    read_all(app, reader)
    before = store_rows(app)
    kept = call(app, reader, KEEP, keep())
    assert kept['schema'] == 'player-level-commit/3'
    assert kept['status'] == 'committed' and kept['action'] == 'keep' and kept['records'] == [] and kept['kept'] == [work['id']]
    assert store_rows(app)[0] == before[0]
    read_all(app, reader)
    closed = call(app, reader, CLOSE, close())
    assert closed['action'] == 'close' and len(closed['records']) == 1 and closed['kept'] == []
    assert closed['records'][0]['data']['outcome'] == 'achieved' and closed['records'][0]['supersedes'] == work['id']
    assert app.memory.current('work') == []
    read_all(app, reader)
    assert call(app, reader, REPLACE, replace())['status'] == 'committed'


def test_close_outcomes_are_achieved_failed_or_abandoned(level):
    app, channel, actor, reader = level
    commit_first(app, actor, reader)
    read_all(app, reader)
    with pytest.raises(PlayerError, match='outcome'):
        call(app, reader, CLOSE, close('revised'))
    assert call(app, reader, CLOSE, close('abandoned'))['records'][0]['data']['outcome'] == 'abandoned'


def test_wrong_state_errors_name_the_state_and_the_valid_tool_and_keep_the_pass(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    for tool, wrong in ((KEEP, keep()), (CLOSE, close())):
        with pytest.raises(PlayerError, match=f'There is no current subgoal. {tool} needs a current subgoal. '
                           'Call player_level_replace with previous_outcome "none"'):
            call(app, reader, tool, wrong)
    with pytest.raises(PlayerError, match='There is no current subgoal. previous_outcome must be "none"'):
        call(app, reader, REPLACE, supersede())
    first = call(app, reader, REPLACE, replace())['records'][0]
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    current = first['id']
    before = store_rows(app)
    with pytest.raises(PlayerError, match=f'The current subgoal is {current} \\(open\\): "Reach the visible door". '
                       'previous_outcome "none" is only valid when there is no current subgoal.*player_level_keep or player_level_close'):
        call(app, reader, REPLACE, replace('Next'))
    with pytest.raises(PlayerError, match=f'The current subgoal is {current}.*previous_reason must say why it was failed'):
        call(app, reader, REPLACE, replace('Next', outcome='failed', reason=' '))
    assert store_rows(app) == before
    # The fixable errors kept the bound, so the corrected call commits without a new read.
    assert call(app, reader, KEEP, keep())['kept'] == [current]


def test_state_errors_fit_the_custodian_error_bound(level):
    app, channel, actor, reader = level
    first = commit_first(app, actor, reader)
    read_all(app, reader)
    with pytest.raises(PlayerError) as raised:
        call(app, reader, REPLACE, replace('Next'))
    assert len(str(raised.value)) <= 600 and first['id'] in str(raised.value)


@pytest.mark.parametrize('tool,change', [
    (KEEP, dict(reason='')), (KEEP, dict(reason='  ')), (KEEP, dict(reason='r' * 1025)), (KEEP, dict(sources=['s'] * 17)),
    (KEEP, dict(sources='s')), (KEEP, dict(extra=1)),
    (CLOSE, dict(outcome='revised')), (CLOSE, dict(outcome='done')), (CLOSE, dict(reason='')), (CLOSE, dict(reason='r' * 1025)),
    (REPLACE, dict(status='closed')), (REPLACE, dict(text='t' * 2049)), (REPLACE, dict(text=' ')),
    (REPLACE, dict(expected_observations=['o'] * 9)), (REPLACE, dict(expected_observations=['o' * 513])),
    (REPLACE, dict(sources=['s'] * 17)), (REPLACE, dict(confidence=1.5)), (REPLACE, dict(confidence=-.1)),
    (REPLACE, dict(previous_outcome='done')), (REPLACE, dict(previous_reason='r' * 1025)), (REPLACE, dict(extra=1))])
def test_bounds_and_closed_enums_hold_and_keep_the_bound(level, tool, change):
    app, channel, actor, reader = level
    commit_first(app, actor, reader)
    read_all(app, reader)
    base = dict(keep=keep(), close=close(), replace=supersede())[tool.removeprefix('player_level_')]
    with pytest.raises(PlayerError):
        call(app, reader, tool, dict(base, **change))
    assert app.readers[reader['actor_id']]['bound'] is not None
    assert call(app, reader, tool, base)['status'] == 'committed'


@pytest.mark.parametrize('tool,missing', [(KEEP, 'reason'), (KEEP, 'sources'), (CLOSE, 'outcome'), (REPLACE, 'previous_outcome'),
                                          (REPLACE, 'text'), (REPLACE, 'confidence')])
def test_every_property_is_required(level, tool, missing):
    app, channel, actor, reader = level
    commit_first(app, actor, reader)
    read_all(app, reader)
    base = dict(keep=keep(), close=close(), replace=supersede())[tool.removeprefix('player_level_')]
    del base[missing]
    with pytest.raises(PlayerError, match=missing):
        call(app, reader, tool, base)


def test_abstain_writes_nothing_clears_the_bound_and_reports_its_code(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    assert app.readers[reader['actor_id']]['bound'] == 1
    result = call(app, reader, ABSTAIN, dict(reason_code='no_change_needed', reason='The log shows nothing to act on',
                                             sources=[]))
    assert result == dict(schema='player-level-abstain/2', status='abstained', reason_code='no_change_needed',
                          reason='The log shows nothing to act on')
    assert store_rows(app) == (0, 0) and app.readers[reader['actor_id']]['bound'] is None
    # Like any terminal call, it ended the pass: without a new read nothing binds.
    assert call(app, reader, REPLACE, replace())['reason'] == 'No log read bound a position in this pass'


@pytest.mark.parametrize('code', ['insufficient_evidence', 'transient_screen_state', 'no_change_needed', 'other'])
def test_abstain_accepts_each_closed_reason_code_with_empty_sources(level, code):
    app, channel, actor, reader = level
    read_all(app, reader)
    assert call(app, reader, ABSTAIN, dict(reason_code=code, reason='ok', sources=[]))['reason_code'] == code


@pytest.mark.parametrize('args', [
    {}, dict(reason_code='other', sources=[]), dict(reason='ok', sources=[]), dict(reason_code='unknown', reason='ok', sources=[]),
    dict(reason_code='other', reason='', sources=[]), dict(reason_code='other', reason='  ', sources=[]),
    dict(reason_code='other', reason='r' * 1025, sources=[]), dict(reason_code='other', reason=3, sources=[]),
    dict(reason_code='other', reason='ok', sources=[], extra=1), dict(reason_code='other', reason='ok')])
def test_abstain_needs_a_code_a_bounded_reason_and_sources(level, args):
    app, channel, actor, reader = level
    read_all(app, reader)
    with pytest.raises((PlayerError, ControlError)):
        call(app, reader, ABSTAIN, args)
    assert app.readers[reader['actor_id']]['bound'] == 0


def test_abstain_checks_its_cited_sources(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, ABSTAIN, dict(reason_code='other', reason='ok', sources=['missing']))
    assert app.readers[reader['actor_id']]['bound'] == 1
    cited = first['source']['source_id']
    assert call(app, reader, ABSTAIN, dict(reason_code='other', reason='ok', sources=[cited]))['status'] == 'abstained'


def test_keep_registers_no_frames_but_still_needs_its_citations_available(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    call(app, reader, REPLACE, replace())
    read_all(app, reader)
    before = store_rows(app), source_rows(app)
    cited = first['source']['source_id']
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, KEEP, keep(sources=[cited, 'missing']))
    kept = call(app, reader, KEEP, keep(sources=[cited]))
    assert kept['status'] == 'committed' and kept['records'] == []
    # Only the service row is new: the cited frame was not copied into the player store.
    assert (store_rows(app)[0], source_rows(app)) == (before[0][0], before[1])
    read_all(app, reader)
    closed = call(app, reader, CLOSE, close(sources=[cited]))
    assert closed['status'] == 'committed' and source_rows(app) == before[1] + 1


def test_retained_commit_identity_collects_without_recommitting(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    identity = request_id()
    first = call(app, reader, REPLACE, replace(), identity)
    again = call(app, reader, REPLACE, replace(), identity)
    assert again == first and len(app.memory.current('work')) == 1
    # The reader has no result tool: the retained identity collects by repeating the same call.
    assert app.memory.service_result(identity, reader['actor_id'])['value'] == first
    with pytest.raises(PlayerError):
        call(app, reader, REPLACE, replace('Different'), identity)
    # The same arguments under another tool name are another request, not the original.
    with pytest.raises(PlayerError):
        call(app, reader, KEEP, keep(), identity)
    # A keep writes no record but is still collectable as its original result.
    read_all(app, reader)
    kept_id = request_id()
    kept = call(app, reader, KEEP, keep(), kept_id)
    assert call(app, reader, KEEP, keep(), kept_id) == kept
    assert app.memory.service_result(kept_id, reader['actor_id'])['value'] == kept


def test_unavailable_cited_source_writes_nothing_and_keeps_the_pass(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    work = call(app, reader, REPLACE, replace())['records'][0]
    read_all(app, reader)
    before = store_rows(app), source_rows(app)
    valid = first['source']['source_id']
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, REPLACE, supersede('Next', sources=[valid, 'missing']))
    assert (store_rows(app), source_rows(app)) == before
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]
    corrected = call(app, reader, REPLACE, supersede('Next', sources=[valid]))
    assert corrected['status'] == 'committed' and source_rows(app) == before[1] + 1


def test_source_capacity_failure_writes_nothing_and_keeps_the_pass(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    channel.capture = 2
    second = call(app, actor, 'computer_observe', {})['source']['source_id']
    assert second != first['source']['source_id']
    read_all(app, reader)
    # Room for one PNG only: the second cited source fails inside the commit transaction.
    app.memory.max_source_bytes = len(channel.png)
    before = store_rows(app), source_rows(app)
    with pytest.raises(PlayerError, match='capacity'):
        call(app, reader, REPLACE, replace(sources=[first['source']['source_id'], second]))
    assert (store_rows(app), source_rows(app)) == before
    # The failure kept the pass, so a corrected resubmission commits without a new read.
    assert call(app, reader, REPLACE, replace(sources=[second]))['status'] == 'committed'


def test_commit_after_pause_or_deadline_is_discarded(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    app.runtime.stop('Operator Pause')
    result = call(app, reader, REPLACE, replace())
    assert result['status'] == 'discarded' and result['reason'] == 'Run stopped or fenced since the read'
    assert store_rows(app) == (0, 0)


def test_deadline_fences_a_commit(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    app.runtime.deadline = 0.
    assert call(app, reader, REPLACE, replace())['reason'] == 'Run stopped or fenced since the read'


def test_actor_start_pass_revalidates_before_any_input(level):
    app, channel, actor, reader = level
    assert read_all(app, reader)['entries'] == []
    committed = call(app, reader, REPLACE, replace())
    assert committed['status'] == 'committed' and committed['position'] == 0 and committed['inputs_since'] == 0


def test_runtime_write_authorization_separates_reader_and_actor_writes(level):
    app, channel, actor, reader = level
    runtime = app.runtime
    assert runtime.authorize(reader['token'], write=True, level_end=True) == reader['actor_id']
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(reader['token'], write=True)
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(actor['token'], write=True, level_end=True)
    assert runtime.authorize(actor['token'], write=True) == actor['actor_id']


def test_reader_minting_refuses_more_than_one_current_level_subgoal_and_ignores_other_work(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        flat = app.add_actor('flat')
        with pytest.raises(ControlError, match='narrowed-profile'):
            app.add_reader(flat['actor_id'], staleness_inputs=S)
        sealed = call(app, flat, 'player_handoff', {})
        runtime.confirm_quiescent(flat['actor_id'], sealed['operation_id'], host_quiescent=True)
        actor = app.add_actor('narrowed')

        def work(index, level=False):
            memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text=f'work {index}',
                data=dict(level='subgoal', level_contract='player-level/3') if level else {}, sources=[], supports=[], supersedes=None,
                applicability=None, program_id=None))
        for index in range(16):
            work(index)
        work('one', level=True)
        work('two', level=True)
        # Other current Work is out of the level's scope; two level subgoals are not resolvable.
        with pytest.raises(ControlError, match='More than one current level subgoal'):
            app.add_reader(actor['actor_id'], staleness_inputs=S)
        memory.append(actor['actor_id'], dict(schema='player-record/1', kind='correction', text='ended',
            data={}, sources=[], supports=[], supersedes=memory.current('work')[-1]['id'], applicability=None, program_id=None))
        assert app.add_reader(actor['actor_id'], staleness_inputs=S)['actor_id']
    finally:
        runtime.close(); memory.close()


def test_other_current_work_is_untouched_by_a_level_commit(level):
    app, channel, actor, reader = level
    other = app.memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text='not the level\'s',
        data={}, sources=[], supports=[], supersedes=None, applicability=None, program_id=None))
    commit_first(app, actor, reader)
    read_all(app, reader)
    assert call(app, reader, CLOSE, close())['status'] == 'committed'
    assert [r['id'] for r in app.memory.current('work')] == [other['id']]


def test_level_records_are_counted_across_superseded_history_and_other_work_is_not(level):
    app, channel, actor, reader = level
    app.memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text='not the level\'s',
        data={}, sources=[], supports=[], supersedes=None, applicability=None, program_id=None))
    assert app.level_record_count() == 0
    commit_first(app, actor, reader)
    read_all(app, reader)
    call(app, reader, REPLACE, supersede('Next'))
    assert app.level_record_count() == 2 and len(app.level_subgoals()) == 1


def test_intent_reports_the_latest_level_subgoal_and_its_age(level):
    app, channel, actor, reader = level
    assert app.intent(actor['actor_id'])['record'] is None
    assert call(app, actor, 'player_intent', {})['schema'] == 'player-intent/1'
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    call(app, reader, REPLACE, replace())
    call(app, actor, 'computer_input', dict(actions=[key()]))
    intent = call(app, actor, 'player_intent', {})
    assert intent['record']['text'] == 'Reach the visible door' and intent['grants_authority'] is False
    assert intent['age']['inputs_since_commit'] == 1 and intent['age']['inputs_by_this_actor'] == 2
    assert intent['age']['same_actor'] is True and intent['age']['same_session'] is True


def test_call_timing_records_lock_wait_and_never_breaks_a_call(level):
    app, channel, actor, reader = level
    rows = []
    app.timing = rows.append
    call(app, actor, 'computer_observe', {})
    assert rows[0]['tool'] == 'computer_observe' and rows[0]['wait_ms'] >= 0 and rows[0]['held_ms'] >= 0
    app.timing = lambda row: 1 / 0
    assert call(app, actor, 'computer_observe', {})['status'] == 'completed'


def test_reader_profile_is_exactly_the_log_the_sources_and_the_four_terminal_tools():
    from harness.player_tools import PROFILES, tool_specs
    assert PROFILES['reader'] == ('player_log_read', 'player_source', KEEP, REPLACE, CLOSE, ABSTAIN)
    assert not {'player_level_commit', 'player_memory_read', 'player_memory_query', 'player_memory_context',
                'player_program_read', 'player_result', 'computer_result'} & set(PROFILES['reader'])
    assert set(PROFILES['reader']) <= set(tool_specs())
    assert 'player_level_commit' not in tool_specs()


@pytest.mark.parametrize('name', ['player_memory_read', 'player_memory_query', 'player_memory_context',
                                  'player_program_read', 'player_result', 'computer_result', 'player_level_commit'])
def test_the_reader_is_refused_the_removed_memory_program_and_result_tools(level, name):
    app, channel, actor, reader = level
    # A removed tool is outside the class allowlist, or (as a write) outside the reader's pass-ending writes.
    with pytest.raises(ControlError, match='capability'):
        call(app, reader, name, {})


def test_reader_mcp_adapter_reads_and_ends_a_pass_over_http(level, tmp_path):
    app, channel, actor, reader = level
    server, thread = serve(app, 0)
    try:
        config = tmp_path / 'reader.json'
        config.write_text(json.dumps(dict(schema='player-adapter/1', base_url=f'http://127.0.0.1:{server.server_port}',
                                          session=app.runtime.session, **reader)))
        client = PlayerClient(config)
        call(app, actor, 'computer_input', dict(actions=[key()]))
        log, _, error = client.call('player_log_read', dict(after=0, limit=10))
        assert not error and log['entries'][0]['position'] == 1
        committed, _, error = client.call(REPLACE, replace())
        assert not error and committed['status'] == 'committed'
        abstained, _, error = client.call(ABSTAIN, dict(reason_code='other', reason='Nothing changed', sources=[]))
        assert not error and abstained['status'] == 'abstained'
        refused, _, error = client.call('computer_input', dict(actions=[key()]))
        assert error and len(channel.calls) == 2
        client.close()
        assert not channel.stopped.is_set()
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_refusals_name_the_offenders_and_the_valid_action_and_end_with_the_fix_line(level):
    from harness.player.contracts import LEVEL_FIX_LINE
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    channel.capture = 2
    second = call(app, actor, 'computer_observe', {})['source']['source_id']
    read_all(app, reader)
    refused = []

    def refusal(tool, args):
        with pytest.raises(PlayerError) as raised:
            call(app, reader, tool, args)
        refused.append(str(raised.value))
        return str(raised.value)
    wrong = refusal(KEEP, keep())
    assert 'There is no current subgoal. player_level_keep needs a current subgoal.' in wrong
    missing = refusal(REPLACE, replace(sources=['ghost-' + 'x' * 100, 'other']))
    assert 'Cited sources are unavailable: ghost-' in missing and ', other.' in missing and 'player_log_read' in missing
    assert 'unavailable' in refusal(ABSTAIN, dict(reason_code='other', reason='r', sources=['ghost']))
    app.memory.max_source_bytes = len(channel.png)
    capacity = refusal(REPLACE, replace(sources=[first['source']['source_id'], second]))
    assert f'total {2 * len(channel.png)} bytes' in capacity and f'{len(channel.png)} bytes of source capacity left' in capacity
    assert 'Cite fewer frames or give sources as []' in capacity
    invalid = refusal(REPLACE, replace(text=' '))
    assert 'text: must not be blank' in invalid
    schema = refusal(REPLACE, dict(replace(), status='closed', confidence=3, sources=['s'] * 20, text='t' * 3000))
    assert 'status' in schema
    assert all(message.endswith(LEVEL_FIX_LINE) and len(message) <= 600 for message in refused), refused
    # The line is the same text the host's validation refusals end with.
    host = (Path(__file__).parents[1] / 'tools/player_host/validation-feedback.mjs').read_text()
    assert f"FIX_LINE = '{LEVEL_FIX_LINE}'" in host


def test_reader_minting_refuses_a_current_level_record_of_another_contract(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        actor = app.add_actor('narrowed')

        def level_work(text, **data):
            return memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text=text,
                data=dict(level='subgoal', **data), sources=[], supports=[], supersedes=None, applicability=None,
                program_id=None))
        def end(record):
            memory.append(actor['actor_id'], dict(schema='player-record/1', kind='correction', text='ended',
                data={}, sources=[], supports=[], supersedes=record['id'], applicability=None, program_id=None))
        for text, data in (('v2 record', dict(level_contract='player-level/2')), ('unversioned record', {})):
            stale = level_work(text, **data)
            with pytest.raises(ControlError, match='Unsupported level record contract.*migrate or start a fresh player store') as raised:
                app.add_reader(actor['actor_id'], staleness_inputs=S)
            assert stale['id'] in str(raised.value)
            # Superseded history of another contract is not current and does not refuse.
            end(stale)
        level_work('current record', level_contract='player-level/3')
        assert app.add_reader(actor['actor_id'], staleness_inputs=S)['actor_id']
    finally:
        runtime.close(); memory.close()


@pytest.mark.parametrize('tool,args,collect_with', [
    (REPLACE, replace(), None), (KEEP, keep(), None), (CLOSE, close(), None),
    (ABSTAIN, dict(reason_code='other', reason='r', sources=[]), None), ('player_log_read', dict(after=0, limit=1), 'player_result')])
def test_a_readers_lost_terminal_call_is_unknown_with_no_collecting_tool(level, tmp_path, tool, args, collect_with):
    app, channel, actor, reader = level
    server, thread = serve(app, 0)
    try:
        config = tmp_path / 'reader.json'
        config.write_text(json.dumps(dict(schema='player-adapter/1', base_url=f'http://127.0.0.1:{server.server_port}',
                                          session=app.runtime.session, **reader)))
        client = PlayerClient(config)
        delivered = client._post

        def lost(path, value, **options):
            delivered(path, value, **options)
            raise TimeoutError('response lost')
        client._post = lost
        value, _, error = client.call(tool, args)
        assert value['schema'] == 'player-transport/1' and value['status'] == 'unknown' and not error
        assert value['collect_with'] == collect_with
        assert 'player_result' not in PROFILES['reader'] and value['input_replayed'] is False
        client.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
