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


def proposal(new=None, records=()):
    return dict(proposal=dict(schema='player-level-proposal/1', subgoal=new, records=list(records)))


def decision(record_id, choice, outcome=None):
    return dict(record_id=record_id, decision=choice, outcome=outcome, reason='Cited log entries', sources=[])


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
        for name, args in (('player_log_read', dict(after=0, limit=1)), ('player_level_commit', proposal(subgoal()))):
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
    with pytest.raises(ControlError, match='only the active actor'):
        app.add_reader(reader['actor_id'], staleness_inputs=S)
    with pytest.raises(ControlError, match='Staleness'):
        app.add_reader(actor['actor_id'], staleness_inputs=0)
    sealed = call(app, actor, 'player_handoff', {})
    assert sealed['handoff']['schema'] == 'player-handoff/2'
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
    committed = call(app, reader, 'player_level_commit', proposal(subgoal(sources=[observed['source']['source_id']])))
    assert committed['status'] == 'committed' and committed['position'] == 2 and committed['inputs_since'] == 0
    (work,) = committed['records']
    assert work['kind'] == 'work' and work['actor_id'] == reader['actor_id'] and work['text'] == 'Reach the visible door'
    assert work['data'] == dict(level='subgoal', proposal_schema='player-level-proposal/1', actor_id=actor['actor_id'],
        session=app.runtime.session, position=2, expected_observations=['The door tile is adjacent'],
        status='open', confidence=.4)
    assert app.memory.read_source(observed['source']['source_id'])[1] == channel.png
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]


def test_model_supplied_position_is_refused(level):
    app, channel, actor, reader = level
    read_all(app, reader)
    for change in (dict(position=7), dict(inputs_since=0)):
        value = proposal(subgoal())
        value['proposal'].update(change)
        with pytest.raises(PlayerError):
            call(app, reader, 'player_level_commit', value)
    with pytest.raises(ControlError):
        call(app, reader, 'player_level_commit', dict(proposal(subgoal()), position=7))
    assert store_rows(app) == (0, 0)


def test_commit_after_s_inputs_is_discarded_and_written_nowhere(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    for _ in range(S - 1):
        call(app, actor, 'computer_input', dict(actions=[key()]))
    call(app, actor, 'computer_observe', {})
    assert call(app, reader, 'player_level_commit', proposal(subgoal()))['status'] == 'committed'
    read_all(app, reader)
    for _ in range(S):
        call(app, actor, 'computer_input', dict(actions=[key()]))
    before = store_rows(app)
    discarded = call(app, reader, 'player_level_commit', proposal(subgoal('Later'), [
        decision(app.memory.current('work')[0]['id'], 'revise')]))
    assert discarded == dict(schema='player-level-commit/1', status='discarded',
        reason='Served actor moved at least S inputs past the read', position=S + 1, inputs_since=S,
        staleness_inputs=S, records=[], kept=[])
    assert store_rows(app) == before
    # The discard ended the pass: without a new read nothing binds.
    assert call(app, reader, 'player_level_commit', proposal(subgoal('Later'), [
        decision(app.memory.current('work')[0]['id'], 'revise')]))['reason'] == 'No log read bound a position in this pass'


def test_commit_after_handoff_is_discarded(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    call(app, actor, 'player_handoff', {})
    result = call(app, reader, 'player_level_commit', proposal(subgoal()))
    assert result['status'] == 'discarded' and result['reason'] == 'Served actor handed off since the read'
    assert store_rows(app) == (0, 0)


def test_empty_delta_binds_nothing(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    assert read_all(app, reader, after=1)['entries'] == []
    result = call(app, reader, 'player_level_commit', proposal(subgoal()))
    assert result['status'] == 'discarded' and result['position'] is None
    assert store_rows(app) == (0, 0)


def test_every_current_work_record_needs_a_decision_and_a_fixable_error_keeps_the_pass(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    first = call(app, reader, 'player_level_commit', proposal(subgoal()))['records'][0]
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    with pytest.raises(PlayerError, match='exactly every current Work record'):
        call(app, reader, 'player_level_commit', proposal(subgoal('Next')))
    for bad in ([decision(first['id'], 'keep')], [decision(first['id'], 'close')],
                [decision(first['id'], 'revise', 'achieved')], [decision(first['id'], 'close', 'achieved')] * 2):
        with pytest.raises(PlayerError):
            call(app, reader, 'player_level_commit', proposal(subgoal('Next'), bad))
    with pytest.raises(PlayerError):
        call(app, reader, 'player_level_commit', proposal(None, []))
    revised = call(app, reader, 'player_level_commit', proposal(subgoal('Next'), [decision(first['id'], 'revise')]))
    work, correction = revised['records']
    assert revised['status'] == 'committed' and revised['position'] == 2
    assert correction['kind'] == 'correction' and correction['supersedes'] == first['id']
    assert correction['supports'] == [work['id']] and correction['data']['outcome'] == 'revised'
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]


def test_keep_writes_nothing_and_close_records_its_outcome(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    work = call(app, reader, 'player_level_commit', proposal(subgoal()))['records'][0]
    read_all(app, reader)
    before = store_rows(app)
    kept = call(app, reader, 'player_level_commit', proposal(None, [decision(work['id'], 'keep')]))
    assert kept['status'] == 'committed' and kept['records'] == [] and kept['kept'] == [work['id']]
    assert store_rows(app)[0] == before[0]
    read_all(app, reader)
    closed = call(app, reader, 'player_level_commit', proposal(None, [decision(work['id'], 'close', 'achieved')]))
    assert closed['records'][0]['data']['outcome'] == 'achieved' and app.memory.current('work') == []


def test_retained_commit_identity_collects_without_recommitting(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    identity = request_id()
    first = call(app, reader, 'player_level_commit', proposal(subgoal()), identity)
    again = call(app, reader, 'player_level_commit', proposal(subgoal()), identity)
    assert again == first and len(app.memory.current('work')) == 1
    collected = call(app, reader, 'player_result', dict(operation_id=identity))
    assert collected['status'] == 'completed' and collected['value'] == first
    with pytest.raises(PlayerError):
        call(app, reader, 'player_level_commit', proposal(subgoal('Different')), identity)
    # A keep-only commit writes no record but is still collectable as its original result.
    read_all(app, reader)
    kept_id = request_id()
    kept = call(app, reader, 'player_level_commit', proposal(None, [decision(first['records'][0]['id'], 'keep')]), kept_id)
    assert call(app, reader, 'player_result', dict(operation_id=kept_id))['value'] == kept


def test_unavailable_cited_source_writes_nothing_and_keeps_the_pass(level):
    app, channel, actor, reader = level
    first = call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    work = call(app, reader, 'player_level_commit', proposal(subgoal()))['records'][0]
    read_all(app, reader)
    before = store_rows(app), source_rows(app)
    valid = first['source']['source_id']
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, 'player_level_commit', proposal(subgoal('Next', sources=[valid, 'missing']),
                                                          [decision(work['id'], 'revise')]))
    assert (store_rows(app), source_rows(app)) == before
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]
    corrected = call(app, reader, 'player_level_commit', proposal(subgoal('Next', sources=[valid]),
                                                                  [decision(work['id'], 'revise')]))
    assert corrected['status'] == 'committed' and source_rows(app) == before[1] + 1


def test_commit_after_pause_or_deadline_is_discarded(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    app.runtime.stop('Operator Pause')
    result = call(app, reader, 'player_level_commit', proposal(subgoal()))
    assert result['status'] == 'discarded' and result['reason'] == 'Run stopped or fenced since the read'
    assert store_rows(app) == (0, 0)


def test_deadline_fences_a_commit(level):
    app, channel, actor, reader = level
    call(app, actor, 'computer_input', dict(actions=[key()]))
    read_all(app, reader)
    app.runtime.deadline = 0.
    assert call(app, reader, 'player_level_commit', proposal(subgoal()))['reason'] == 'Run stopped or fenced since the read'


def test_actor_start_pass_revalidates_before_any_input(level):
    app, channel, actor, reader = level
    assert read_all(app, reader)['entries'] == []
    committed = call(app, reader, 'player_level_commit', proposal(subgoal()))
    assert committed['status'] == 'committed' and committed['position'] == 0 and committed['inputs_since'] == 0


def test_runtime_write_authorization_separates_reader_and_actor_writes(level):
    app, channel, actor, reader = level
    runtime = app.runtime
    assert runtime.authorize(reader['token'], write=True, level_commit=True) == reader['actor_id']
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(reader['token'], write=True)
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(actor['token'], write=True, level_commit=True)
    assert runtime.authorize(actor['token'], write=True) == actor['actor_id']


def test_reader_minting_refuses_a_store_no_commit_could_cover(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        actor = app.add_actor('flat')
        for index in range(16):
            memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text=f'work {index}', data={},
                sources=[], supports=[], supersedes=None, applicability=None, program_id=None))
        with pytest.raises(ControlError, match='More than 15'):
            app.add_reader(actor['actor_id'], staleness_inputs=S)
    finally:
        runtime.close(); memory.close()


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
        committed, _, error = client.call('player_level_commit', proposal(subgoal()))
        assert not error and committed['status'] == 'committed'
        refused, _, error = client.call('computer_input', dict(actions=[key()]))
        assert error and len(channel.calls) == 2
        client.close()
        assert not channel.stopped.is_set()
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
