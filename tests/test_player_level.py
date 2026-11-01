"""Reader custody, the player log projection and the software-mediated level commit.

Actual composition, SQLite and HTTP over a receiver double; no provider, game or level host.
"""
import json
from unittest.mock import patch
import uuid

import pytest

from harness.application import Application
from harness.computer.protocol import ControlError
from harness.player.contracts import PlayerError
from harness.player.memory import Memory
from harness.player_client import PlayerClient
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


def subgoal(text='Reach the visible door', sources=()):
    return dict(text=text, expected_observations=['The door tile is adjacent'], status='open',
                confidence=.4, sources=list(sources))


SCHEMA = 'player-level-proposal/2'


def keep(record_id, reason='Cited log entries'):
    return dict(proposal=dict(schema=SCHEMA, action='keep', record_id=record_id, reason=reason, sources=[]))


def close(record_id, outcome='achieved', reason='Cited log entries'):
    return dict(proposal=dict(schema=SCHEMA, action='close', record_id=record_id, outcome=outcome, reason=reason, sources=[]))


def previous(record_id, outcome='revised', sources=()):
    return dict(record_id=record_id, outcome=outcome, reason='Cited log entries', sources=list(sources))


def replace(new=None, prior=None):
    return dict(proposal=dict(schema=SCHEMA, action='replace', subgoal=new or subgoal(), previous=prior))


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
        for name, args in (('player_log_read', dict(after=0, limit=1)), ('player_level_commit', replace()),
                           ('player_level_abstain', dict(reason='none'))):
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
    committed = call(app, reader, 'player_level_commit', replace(subgoal(sources=[observed['source']['source_id']])))
    assert committed['status'] == 'committed' and committed['position'] == 2 and committed['inputs_since'] == 0
    (work,) = committed['records']
    assert work['kind'] == 'work' and work['actor_id'] == reader['actor_id'] and work['text'] == 'Reach the visible door'
    assert work['data'] == dict(level='subgoal', proposal_schema=SCHEMA, actor_id=actor['actor_id'],
        session=app.runtime.session, position=2, expected_observations=['The door tile is adjacent'],
        status='open', confidence=.4)
    assert app.memory.read_source(observed['source']['source_id'])[1] == channel.png
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]


def test_model_supplied_position_is_refused(level):
    app, channel, actor, reader = level
    read_all(app, reader)
    for change in (dict(position=7), dict(inputs_since=0)):
        value = replace()
        value['proposal'].update(change)
        with pytest.raises(PlayerError):
            call(app, reader, 'player_level_commit', value)
    with pytest.raises(ControlError):
        call(app, reader, 'player_level_commit', dict(replace(), position=7))
    assert store_rows(app) == (0, 0)


def test_commit_after_s_inputs_is_discarded_and_written_nowhere(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    for _ in range(S - 1):
        call(app, actor, 'computer_input', dict(actions=[key()]))
    call(app, actor, 'computer_observe', {})
    assert call(app, reader, 'player_level_commit', replace())['status'] == 'committed'
    read_all(app, reader)
    for _ in range(S):
        call(app, actor, 'computer_input', dict(actions=[key()]))
    before = store_rows(app)
    current = app.memory.current('work')[0]['id']
    discarded = call(app, reader, 'player_level_commit', replace(subgoal('Later'), previous(current)))
    assert discarded == dict(schema='player-level-commit/2', status='discarded', action='replace',
        reason='Served actor moved at least S inputs past the read', position=S + 1, inputs_since=S,
        staleness_inputs=S, records=[], kept=[])
    assert store_rows(app) == before
    # The discard ended the pass: without a new read nothing binds.
    assert call(app, reader, 'player_level_commit', replace(subgoal('Later'), previous(current)))[
        'reason'] == 'No log read bound a position in this pass'


def test_commit_after_handoff_is_discarded(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    call(app, actor, 'player_handoff', {})
    result = call(app, reader, 'player_level_commit', replace())
    assert result['status'] == 'discarded' and result['reason'] == 'Served actor handed off since the read'
    assert store_rows(app) == (0, 0)


def test_empty_delta_binds_nothing(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    assert read_all(app, reader, after=1)['entries'] == []
    result = call(app, reader, 'player_level_commit', replace())
    assert result['status'] == 'discarded' and result['position'] is None
    assert store_rows(app) == (0, 0)


def commit_first(app, actor, reader):
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    return call(app, reader, 'player_level_commit', replace())['records'][0]


def test_replace_without_a_current_subgoal_writes_one_work_record_and_no_correction(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    committed = call(app, reader, 'player_level_commit', replace())
    assert committed['action'] == 'replace' and committed['kept'] == [] and len(committed['records']) == 1
    assert committed['records'][0]['kind'] == 'work'


def test_replace_with_previous_writes_work_and_a_superseding_correction(level):
    app, channel, actor, reader = level
    first = commit_first(app, actor, reader)
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    revised = call(app, reader, 'player_level_commit', replace(subgoal('Next'), previous(first['id'])))
    work, correction = revised['records']
    assert revised['status'] == 'committed' and revised['position'] == 2
    assert correction['kind'] == 'correction' and correction['supersedes'] == first['id']
    assert correction['supports'] == [work['id']] and correction['data']['outcome'] == 'revised'
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]
    read_all(app, reader)
    ended = call(app, reader, 'player_level_commit', replace(subgoal('Last'), previous(work['id'], 'failed')))
    assert ended['records'][1]['supports'] == [] and ended['records'][1]['data']['outcome'] == 'failed'
    assert [r['text'] for r in app.memory.current('work')] == ['Last']


def test_keep_writes_nothing_and_close_records_its_outcome(level):
    app, channel, actor, reader = level
    work = commit_first(app, actor, reader)
    read_all(app, reader)
    before = store_rows(app)
    kept = call(app, reader, 'player_level_commit', keep(work['id']))
    assert kept['status'] == 'committed' and kept['action'] == 'keep' and kept['records'] == [] and kept['kept'] == [work['id']]
    assert store_rows(app)[0] == before[0]
    read_all(app, reader)
    closed = call(app, reader, 'player_level_commit', close(work['id']))
    assert closed['action'] == 'close' and len(closed['records']) == 1
    assert closed['records'][0]['data']['outcome'] == 'achieved' and app.memory.current('work') == []
    read_all(app, reader)
    assert call(app, reader, 'player_level_commit', replace())['status'] == 'committed'


def test_wrong_state_errors_name_the_valid_shapes_and_the_current_id_and_keep_the_pass(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    none_message = 'no current subgoal \\(none\\): use replace with previous null'
    for wrong in (keep('absent'), close('absent'), replace(prior=previous('absent'))):
        with pytest.raises(PlayerError, match=none_message):
            call(app, reader, 'player_level_commit', wrong)
    first = call(app, reader, 'player_level_commit', replace())['records'][0]
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    current = first['id']
    message = (f'current subgoal {current}: use keep or close with record_id {current}, '
               f'or replace with previous.record_id {current} and its outcome')
    before = store_rows(app)
    for wrong in (replace(subgoal('Next')), keep('other'), close('other'), replace(prior=previous('other'))):
        with pytest.raises(PlayerError, match=message):
            call(app, reader, 'player_level_commit', wrong)
    assert store_rows(app) == before
    # The fixable errors kept the bound, so the corrected proposal commits without a new read.
    assert call(app, reader, 'player_level_commit', keep(current))['status'] == 'committed'


@pytest.mark.parametrize('change', [
    dict(action='close'), dict(action='keep', subgoal=subgoal()), dict(action='other'), dict(action=None), dict(schema='player-level-proposal/1'),
    dict(extra=1), dict(outcome='revised')])
def test_malformed_proposals_are_tool_errors_that_name_the_shapes_and_current_id(level, change):
    app, channel, actor, reader = level
    work = commit_first(app, actor, reader)
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    value = keep(work['id'])
    value['proposal'].update(change)
    with pytest.raises(PlayerError, match=f'Valid shapes: keep.*close.*replace.*Current subgoal: {work["id"]}'):
        call(app, reader, 'player_level_commit', value)
    assert call(app, reader, 'player_level_commit', keep(work['id']))['status'] == 'committed'


@pytest.mark.parametrize('bad', [
    close('x', 'revised'), close('x', 'achieved', reason=''), close('x', 'achieved', reason='r' * 1025),
    replace(subgoal(), dict(previous('x'), outcome='done')), replace(dict(subgoal(), status='closed')),
    replace(dict(subgoal(), text='t' * 2049)), replace(dict(subgoal(), expected_observations=['o'] * 9)),
    replace(dict(subgoal(), expected_observations=['o' * 513])), replace(dict(subgoal(), sources=['s'] * 17)),
    replace(dict(subgoal(), confidence=1.5))])
def test_proposal_bounds_and_closed_enums_hold(level, bad):
    app, channel, actor, reader = level
    read_all(app, reader)
    with pytest.raises(PlayerError):
        call(app, reader, 'player_level_commit', bad)
    assert store_rows(app) == (0, 0)


def test_abstain_writes_nothing_and_clears_the_bound(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    assert app.readers[reader['actor_id']]['bound'] == 1
    result = call(app, reader, 'player_level_abstain', dict(reason='The log shows nothing to act on'))
    assert result == dict(schema='player-level-abstain/1', status='abstained', reason='The log shows nothing to act on')
    assert store_rows(app) == (0, 0) and app.readers[reader['actor_id']]['bound'] is None
    # Like a commit attempt, it ended the pass: without a new read nothing binds.
    assert call(app, reader, 'player_level_commit', replace())['reason'] == 'No log read bound a position in this pass'


@pytest.mark.parametrize('args', [{}, dict(reason=''), dict(reason='  '), dict(reason='r' * 1025), dict(reason=3),
                                  dict(reason='ok', extra=1)])
def test_abstain_needs_one_bounded_reason(level, args):
    app, channel, actor, reader = level
    read_all(app, reader)
    with pytest.raises((PlayerError, ControlError)):
        call(app, reader, 'player_level_abstain', args)
    assert app.readers[reader['actor_id']]['bound'] == 0


def test_keep_registers_no_frames_but_still_needs_its_citations_available(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    work = call(app, reader, 'player_level_commit', replace())['records'][0]
    read_all(app, reader)
    before = store_rows(app), source_rows(app)
    cited = first['source']['source_id']
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, 'player_level_commit', dict(proposal=dict(keep(work['id'])['proposal'], sources=[cited, 'missing'])))
    kept = call(app, reader, 'player_level_commit', dict(proposal=dict(keep(work['id'])['proposal'], sources=[cited])))
    assert kept['status'] == 'committed' and kept['records'] == []
    # Only the service row is new: the cited frame was not copied into the player store.
    assert (store_rows(app)[0], source_rows(app)) == (before[0][0], before[1])
    read_all(app, reader)
    closed = call(app, reader, 'player_level_commit', dict(proposal=dict(close(work['id'])['proposal'], sources=[cited])))
    assert closed['status'] == 'committed' and source_rows(app) == before[1] + 1


def test_retained_commit_identity_collects_without_recommitting(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    identity = request_id()
    first = call(app, reader, 'player_level_commit', replace(), identity)
    again = call(app, reader, 'player_level_commit', replace(), identity)
    assert again == first and len(app.memory.current('work')) == 1
    collected = call(app, reader, 'player_result', dict(operation_id=identity))
    assert collected['status'] == 'completed' and collected['value'] == first
    with pytest.raises(PlayerError):
        call(app, reader, 'player_level_commit', replace(subgoal('Different')), identity)
    # A keep-only commit writes no record but is still collectable as its original result.
    read_all(app, reader)
    kept_id = request_id()
    kept = call(app, reader, 'player_level_commit', keep(first['records'][0]['id']), kept_id)
    assert call(app, reader, 'player_result', dict(operation_id=kept_id))['value'] == kept


def test_unavailable_cited_source_writes_nothing_and_keeps_the_pass(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    work = call(app, reader, 'player_level_commit', replace())['records'][0]
    read_all(app, reader)
    before = store_rows(app), source_rows(app)
    valid = first['source']['source_id']
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, 'player_level_commit', replace(subgoal('Next', sources=[valid, 'missing']), previous(work['id'])))
    assert (store_rows(app), source_rows(app)) == before
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]
    corrected = call(app, reader, 'player_level_commit', replace(subgoal('Next', sources=[valid]), previous(work['id'])))
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
        call(app, reader, 'player_level_commit', replace(subgoal(sources=[first['source']['source_id'], second])))
    assert (store_rows(app), source_rows(app)) == before
    # The failure kept the pass, so a corrected resubmission commits without a new read.
    assert call(app, reader, 'player_level_commit', replace(subgoal(sources=[second])))['status'] == 'committed'


def test_commit_after_pause_or_deadline_is_discarded(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    app.runtime.stop('Operator Pause')
    result = call(app, reader, 'player_level_commit', replace())
    assert result['status'] == 'discarded' and result['reason'] == 'Run stopped or fenced since the read'
    assert store_rows(app) == (0, 0)


def test_deadline_fences_a_commit(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    app.runtime.deadline = 0.
    assert call(app, reader, 'player_level_commit', replace())['reason'] == 'Run stopped or fenced since the read'


def test_actor_start_pass_revalidates_before_any_input(level):
    app, channel, actor, reader = level
    assert read_all(app, reader)['entries'] == []
    committed = call(app, reader, 'player_level_commit', replace())
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
                data=dict(level='subgoal') if level else {}, sources=[], supports=[], supersedes=None,
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
    first = commit_first(app, actor, reader)
    read_all(app, reader)
    assert call(app, reader, 'player_level_commit', close(first['id']))['status'] == 'committed'
    assert [r['id'] for r in app.memory.current('work')] == [other['id']]


def test_intent_reports_the_latest_level_subgoal_and_its_age(level):
    app, channel, actor, reader = level
    assert app.intent(actor['actor_id'])['record'] is None
    assert call(app, actor, 'player_intent', {})['schema'] == 'player-intent/1'
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    call(app, reader, 'player_level_commit', replace())
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


def test_reader_mcp_adapter_reads_and_commits_over_http(level, tmp_path):
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
        committed, _, error = client.call('player_level_commit', replace())
        assert not error and committed['status'] == 'committed'
        abstained, _, error = client.call('player_level_abstain', dict(reason='Nothing changed'))
        assert not error and abstained['status'] == 'abstained'
        refused, _, error = client.call('computer_input', dict(actions=[key()]))
        assert error and len(channel.calls) == 2
        client.close()
        assert not channel.stopped.is_set()
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
