"""Reader custody, the binding and the software-mediated level commit (level v4).

Actual composition, SQLite and HTTP over a receiver double; no provider, game or level host.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from episode_support import (ABSTAIN, CLOSE, KEEP, RECORD, REPLACE, EPISODE_ABSTAIN, S, act, bind, call, close,
                             commit_first, current_id, keep, mint, replace, request_id, source_rows, store_rows,
                             supersede, sync, total)
from harness.application import Application
from harness.computer.protocol import ControlError
from harness.player.contracts import PlayerError
from harness.player.memory import Memory
from harness.player_client import PlayerClient
from harness.player_tools import PROFILES, tool_specs
from harness.server import serve
from test_computer_runtime import key, make_runtime
from test_server import post


@pytest.mark.parametrize('name,args', [
    ('computer_observe', {}), ('computer_input', dict(actions=[key()])), ('computer_stop', {}),
    ('player_handoff', {}), ('player_program_save', dict(program={})), ('player_program_run', {}),
    ('player_memory_append', dict(record={}))])
@pytest.mark.parametrize('which', [3, 4])
def test_readers_cannot_send_input_stop_observe_seal_or_write_directly(level, name, args, which):
    app, channel, actor, *_ = level
    reader = level[which]
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


def test_readers_cannot_request_stop_over_http_either(level):
    app, channel, actor, reader, recorder = level
    server, thread = serve(app, 0)
    try:
        for capability in (reader, recorder):
            status, _ = post(server.server_port, '/api/actor-stop',
                             dict(session=app.runtime.session, reason='reader'), capability['token'])
            assert status == 400 and not channel.stopped.is_set()
            status, _ = post(server.server_port, '/api/tool', dict(operation_id=request_id(), tool='computer_input',
                             arguments=dict(actions=[key()])), capability['token'])
            assert status == 400 and channel.calls == []
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


@pytest.mark.parametrize('profile', ['flat', 'narrowed'])
def test_actors_are_refused_the_level_and_recorder_tools(tmp_path, profile):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        actor = app.add_actor(profile)
        for name, args in ((KEEP, keep()), (REPLACE, replace()), (CLOSE, close()),
                           (ABSTAIN, dict(reason_code='other', reason='none', sources=[])),
                           (RECORD, {}), (EPISODE_ABSTAIN, dict(reason_code='other', reason='none', sources=[])),
                           ('player_log_read', dict(after=0, limit=1))):
            with pytest.raises(ControlError, match='capability'):
                call(app, actor, name, args)
        assert store_rows(app) == (0, 0)
    finally:
        runtime.close(); memory.close()


def test_the_level_and_the_recorder_each_hold_only_their_own_writes(level):
    app, channel, actor, reader, recorder = level
    for capability, foreign in ((reader, (RECORD, EPISODE_ABSTAIN)), (recorder, (KEEP, REPLACE, CLOSE, ABSTAIN))):
        for name in foreign:
            with pytest.raises(ControlError, match='no such write'):
                call(app, capability, name, {})
            with patch.object(app.runtime, 'authorize', return_value=capability['actor_id']), \
                    pytest.raises(ControlError, match='capability class'):
                call(app, capability, name, {})
    assert store_rows(app) == (0, 0)


def test_narrowed_actor_acts_but_has_no_memory_writes_or_program_save(level):
    app, channel, actor, *_ = level
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


def test_two_readers_per_actor_one_per_role_and_a_third_is_refused(level):
    app, channel, actor, reader, recorder = level
    parameters = dict(stall_settles=3, confidence_floor=.5)
    stages = {a['actor_id']: (a['stage'], a['serves'], a['reader_role']) for a in app.status()['actors']}
    assert stages[reader['actor_id']] == ('reader', actor['actor_id'], 'level')
    assert stages[recorder['actor_id']] == ('reader', actor['actor_id'], 'recorder')
    with pytest.raises(ControlError, match='already has its level reader'):
        app.add_reader(actor['actor_id'], 'level', staleness_inputs=S, **parameters)
    with pytest.raises(ControlError, match='already has its recorder reader'):
        app.add_reader(actor['actor_id'], 'recorder', **parameters)
    with pytest.raises(ControlError, match='level or recorder'):
        app.add_reader(actor['actor_id'], 'third', **parameters)
    with pytest.raises(ControlError, match='narrowed-profile'):
        app.add_reader(reader['actor_id'], 'level', staleness_inputs=S, **parameters)
    # The store enforces the same uniqueness underneath the runtime check.
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        app.runtime.store.add_actor('f' * 32, 'f' * 64, actor['actor_id'], 'level')


def test_reader_parameters_are_validated_and_shared_by_one_actors_readers(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        actor = app.add_actor('narrowed')
        base = dict(stall_settles=3, confidence_floor=.5)
        for bad in (dict(staleness_inputs=0), dict(staleness_inputs=1001), dict(staleness_inputs=None),
                    dict(staleness_inputs=S, stall_settles=0), dict(staleness_inputs=S, stall_settles=True),
                    dict(staleness_inputs=S, confidence_floor=1.5), dict(staleness_inputs=S, confidence_floor=-.1),
                    dict(staleness_inputs=S, confidence_floor=float('nan'))):
            with pytest.raises(ControlError):
                app.add_reader(actor['actor_id'], 'level', **(base | bad))
        with pytest.raises(ControlError, match='Only the level'):
            app.add_reader(actor['actor_id'], 'recorder', staleness_inputs=S, **base)
        app.add_reader(actor['actor_id'], 'level', staleness_inputs=S, **base)
        with pytest.raises(ControlError, match='share one stall test'):
            app.add_reader(actor['actor_id'], 'recorder', stall_settles=4, confidence_floor=.5)
        with pytest.raises(ControlError, match='share one stall test'):
            app.add_reader(actor['actor_id'], 'recorder', stall_settles=3, confidence_floor=.6)
        assert app.add_reader(actor['actor_id'], 'recorder', **base)['actor_id']
    finally:
        runtime.close(); memory.close()


def test_readers_serve_only_the_active_actor_and_never_block_succession(level):
    app, channel, actor, reader, recorder = level
    sealed = call(app, actor, 'player_handoff', {})
    assert sealed['handoff']['schema'] == 'player-handoff/2'
    with pytest.raises(ControlError, match='only the active actor'):
        app.add_reader(actor['actor_id'], 'level', staleness_inputs=S, stall_settles=3, confidence_floor=.5)
    app.runtime.confirm_quiescent(actor['actor_id'], sealed['operation_id'], host_quiescent=True)
    # max_actors is 2: the live readers neither count nor block the successor.
    successor = app.add_actor('narrowed')
    assert app.runtime.actor_stage(reader['actor_id']) == 'reader'
    assert app.runtime.actor_stage(recorder['actor_id']) == 'reader'
    new_level, new_recorder = mint(app, successor)
    assert {new_level['actor_id'], new_recorder['actor_id']}.isdisjoint({reader['actor_id'], recorder['actor_id']})


def test_the_log_read_tool_and_its_schema_are_removed(level):
    app, channel, actor, reader, recorder = level
    assert 'player_log_read' not in tool_specs() and not hasattr(app, 'log_read')
    assert not hasattr(app, 'reset_reader_bound')
    for capability in (actor, reader, recorder):
        with pytest.raises(ControlError, match='capability'):
            call(app, capability, 'player_log_read', dict(after=0, limit=1))
    source = (Path(__file__).parents[1] / 'harness/application.py').read_text()
    assert 'player-log' not in source and 'player_log_read' not in source


def test_commit_binds_the_end_of_the_newest_settled_episode_and_writes_one_work_record(level):
    app, channel, actor, reader, recorder = level
    observed = call(app, actor, 'computer_observe', {})
    act(app, actor)
    sync(app, actor, recorder)
    assert bind(app, reader) == dict(position=2, subgoal_id=None, pass_index=1, handoff=False)
    committed = call(app, reader, REPLACE, replace(sources=[observed['source']['source_id']]))
    assert committed['schema'] == 'player-level-commit/4'
    assert committed['status'] == 'committed' and committed['position'] == 2 and committed['inputs_since'] == 0
    assert committed['subgoal_id'] is None and committed['derived'] is None
    (work,) = committed['records']
    assert work['kind'] == 'work' and work['actor_id'] == reader['actor_id'] and work['text'] == 'Reach the visible door'
    # Software stamps the contract version; the model supplied none.
    assert work['data'] == dict(level='subgoal', level_contract='player-level/4', actor_id=actor['actor_id'],
        session=app.runtime.session, position=2, expected_observations=['The door tile is adjacent'],
        status='open', confidence=.4)
    assert app.memory.read_source(observed['source']['source_id'])[1] == channel.png
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]


def test_replace_needs_at_least_one_expected_observation(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    with pytest.raises(PlayerError, match='expected_observations'):
        call(app, reader, REPLACE, replace(observations=[]))
    assert store_rows(app) == (1, 0)
    assert call(app, reader, REPLACE, replace())['status'] == 'committed'
    assert tool_specs()[REPLACE][1]['properties']['expected_observations']['minItems'] == 1


@pytest.mark.parametrize('tool,args', [(KEEP, keep()), (REPLACE, replace()), (CLOSE, close()),
                                       (ABSTAIN, dict(reason_code='other', reason='x', sources=[]))])
def test_model_supplied_position_id_or_version_is_refused(level, tool, args):
    app, channel, actor, reader, recorder = level
    bind(app, reader)
    for change in (dict(position=7), dict(inputs_since=0), dict(record_id='r'), dict(schema='player-level-commit/4'),
                   dict(version=4), dict(subgoal_id='x')):
        with pytest.raises(PlayerError, match=next(iter(change))):
            call(app, reader, tool, dict(args, **change))
    assert store_rows(app) == (0, 0)


def test_commit_after_s_inputs_is_discarded_and_written_nowhere(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    act(app, actor, S - 1)
    call(app, actor, 'computer_observe', {})
    first = call(app, reader, REPLACE, replace())
    assert first['status'] == 'committed' and first['inputs_since'] == S - 1
    sync(app, actor, recorder)
    bind(app, reader)
    act(app, actor, S)
    before = store_rows(app)
    discarded = call(app, reader, REPLACE, supersede('Later'))
    assert discarded == dict(schema='player-level-commit/4', status='discarded', action='replace',
        reason='Served actor moved at least S inputs past the bound', position=S + 1, inputs_since=S,
        staleness_inputs=S, subgoal_id=current_id(app), records=[], kept=[])
    assert store_rows(app) == before
    # The discard ended the pass: without a new bind nothing binds.
    assert call(app, reader, REPLACE, supersede('Later'))['reason'] == 'No position was bound for this pass'


@pytest.mark.parametrize('tool,args,action', [(KEEP, keep(), 'keep'), (CLOSE, close(), 'close'),
                                              (REPLACE, supersede(), 'replace')])
def test_all_three_terminal_calls_obey_the_same_staleness_rule(level, tool, args, action):
    app, channel, actor, reader, recorder = level
    commit_first(app, actor, reader, recorder)
    sync(app, actor, recorder)
    bind(app, reader)
    act(app, actor, S)
    before = store_rows(app)
    result = call(app, reader, tool, args)
    assert result['status'] == 'discarded' and result['action'] == action
    assert result['reason'] == 'Served actor moved at least S inputs past the bound' and store_rows(app) == before


def test_commit_after_handoff_is_discarded(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    call(app, actor, 'player_handoff', {})
    result = call(app, reader, REPLACE, replace())
    assert result['status'] == 'discarded' and result['reason'] == 'Served actor handed off since the pass began'
    assert store_rows(app) == (1, 0)


def test_binding_a_handed_off_actor_binds_nothing(level):
    app, channel, actor, reader, recorder = level
    call(app, actor, 'player_handoff', {})
    assert bind(app, reader) == dict(position=None, subgoal_id=None, pass_index=0, handoff=True)
    result = call(app, reader, REPLACE, replace())
    assert result['status'] == 'discarded' and result['position'] is None


def test_an_unbound_pass_commits_nothing(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    result = call(app, reader, REPLACE, replace())
    assert result['status'] == 'discarded' and result['position'] is None
    assert result['reason'] == 'No position was bound for this pass' and store_rows(app) == (0, 0)


def test_binding_is_zero_at_start_and_follows_every_settle_even_without_a_record(level):
    app, channel, actor, reader, recorder = level
    assert bind(app, reader) == dict(position=0, subgoal_id=None, pass_index=1, handoff=False)
    act(app, actor, 2)
    # Operations alone bind nothing: only a settled episode does.
    assert bind(app, reader)['position'] == 0
    app.settle_episode(recorder['actor_id'], first_position=1, last_position=2, subgoal_id=None,
                       settled='failed', reason='the recorder pass failed')
    assert bind(app, reader)['position'] == 2
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=3, last_position=3, subgoal_id=None)
    call(app, recorder, EPISODE_ABSTAIN, dict(reason_code='no_player_action', reason='nothing happened', sources=[]))
    assert bind(app, reader)['position'] == 3
    act(app, actor)
    app.settle_episode(recorder['actor_id'], first_position=4, last_position=4, subgoal_id=None,
                       settled='dropped', reason='backlog')
    assert bind(app, reader)['position'] == 4
    # The first commit after a record-less settle is timely from that position.
    assert call(app, reader, REPLACE, replace())['position'] == 4


def test_binding_ignores_earlier_session_records(tmp_path):
    from harness.computer.runtime import ComputerRuntime
    from test_computer_runtime import Channel, Process
    import time
    memory = Memory(tmp_path / 'player.sqlite3')
    runtimes = []
    try:
        for index, session in enumerate(('a' * 32, 'b' * 32)):
            directory = tmp_path / f's{index}'
            directory.mkdir()
            runtime = ComputerRuntime(directory, session, Channel(), Process(), time.monotonic() + 60,
                                      dict(max_inputs=20, max_requests=30, max_frames=40, max_bytes=2**30))
            runtimes.append(runtime)
            app = Application(runtime, memory, tmp_path / f'contexts{index}')
            actor = app.add_actor('narrowed')
            reader, recorder = mint(app, actor)
            if index == 0:
                act(app, actor, 3)
                sync(app, actor, recorder)
                assert bind(app, reader)['position'] == 3
            else:
                # A recalled earlier-session record never binds: the new session starts at 0.
                assert len(app.settled_episodes()) == 1
                assert bind(app, reader)['position'] == 0
    finally:
        for runtime in runtimes:
            runtime.close()
        memory.close()


def test_stale_subgoal_id_is_refused_as_a_discard(level):
    app, channel, actor, reader, recorder = level
    first = commit_first(app, actor, reader, recorder)
    sync(app, actor, recorder)
    pushed = bind(app, reader)['subgoal_id']
    assert pushed == first['id']
    # Software closes the subgoal while the pass runs: every expected observation is now seen.
    receipt = _closing_record(app, actor, recorder)
    assert receipt['closed'] is True and app.level_subgoals() == []
    before = store_rows(app)
    discarded = call(app, reader, REPLACE, replace('Next'))
    assert discarded['status'] == 'discarded' and discarded['reason'] == 'Current subgoal changed since the pass began'
    assert discarded['subgoal_id'] == first['id'] and discarded['records'] == []
    assert store_rows(app) == before
    # A replace over a different current subgoal is stale too, and the discard ended the pass.
    assert app.readers[reader['actor_id']]['bound'] is None


def _closing_record(app, actor, recorder):
    from episode_support import episode
    return episode(app, actor, recorder, ['seen'])


def test_stale_when_a_subgoal_appears_after_binding_with_none(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    # A subgoal appears (as if another commit ran) after the bind with none.
    app.memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text='other', data=dict(
        level='subgoal', level_contract='player-level/4', expected_observations=['x']), sources=[], supports=[],
        supersedes=None, applicability=None, program_id=None))
    result = call(app, reader, REPLACE, supersede('Next'))
    assert result['status'] == 'discarded' and result['reason'] == 'Current subgoal changed since the pass began'
    assert result['subgoal_id'] is None


def test_replace_without_a_current_subgoal_writes_one_work_record_and_no_correction(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    committed = call(app, reader, REPLACE, replace())
    assert committed['action'] == 'replace' and committed['kept'] == [] and len(committed['records']) == 1
    assert committed['records'][0]['kind'] == 'work'


def test_replace_with_a_previous_outcome_writes_work_and_a_superseding_correction(level):
    app, channel, actor, reader, recorder = level
    first = commit_first(app, actor, reader, recorder)
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    revised = call(app, reader, REPLACE, supersede('Next'))
    work, correction = revised['records']
    assert revised['status'] == 'committed' and revised['position'] == 2
    assert correction['kind'] == 'correction' and correction['supersedes'] == first['id']
    assert correction['text'] == 'Cited episodes' and correction['data']['level_contract'] == 'player-level/4'
    assert correction['supports'] == [work['id']] and correction['data']['outcome'] == 'revised'
    assert 'by' not in correction['data']
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]
    bind(app, reader)
    ended = call(app, reader, REPLACE, supersede('Last', 'failed'))
    assert ended['records'][1]['supports'] == [] and ended['records'][1]['data']['outcome'] == 'failed'
    assert [r['text'] for r in app.memory.current('work')] == ['Last']


def test_replace_cites_its_sources_on_both_records(level):
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    work = call(app, reader, REPLACE, replace())['records'][0]
    bind(app, reader)
    cited = first['source']['source_id']
    new, correction = call(app, reader, REPLACE, supersede('Next', 'achieved', [cited]))['records']
    assert new['sources'] == [cited] and correction['sources'] == [cited] and correction['supersedes'] == work['id']


def test_keep_writes_nothing_gives_the_current_id_and_close_records_its_outcome(level):
    app, channel, actor, reader, recorder = level
    work = commit_first(app, actor, reader, recorder)
    bind(app, reader)
    before = store_rows(app)
    kept = call(app, reader, KEEP, keep())
    assert kept['schema'] == 'player-level-commit/4' and kept['subgoal_id'] == work['id']
    assert kept['status'] == 'committed' and kept['action'] == 'keep' and kept['records'] == [] and kept['kept'] == [work['id']]
    assert kept['derived'] == dict(observations=['not_yet'], stalled=False)
    assert store_rows(app)[0] == before[0]
    bind(app, reader)
    closed = call(app, reader, CLOSE, close())
    assert closed['action'] == 'close' and len(closed['records']) == 1 and closed['kept'] == []
    assert closed['records'][0]['data']['outcome'] == 'achieved' and closed['records'][0]['supersedes'] == work['id']
    assert app.memory.current('work') == []
    bind(app, reader)
    assert call(app, reader, REPLACE, replace())['status'] == 'committed'


def test_close_outcomes_are_achieved_failed_or_abandoned(level):
    app, channel, actor, reader, recorder = level
    commit_first(app, actor, reader, recorder)
    bind(app, reader)
    with pytest.raises(PlayerError, match='outcome'):
        call(app, reader, CLOSE, close('revised'))
    assert call(app, reader, CLOSE, close('abandoned'))['records'][0]['data']['outcome'] == 'abandoned'


def test_wrong_state_errors_name_the_state_and_the_valid_tool_and_keep_the_pass(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    for tool, wrong in ((KEEP, keep()), (CLOSE, close())):
        with pytest.raises(PlayerError, match=f'There is no current subgoal. {tool} needs a current subgoal. '
                           'Call player_level_replace with previous_outcome "none"'):
            call(app, reader, tool, wrong)
    with pytest.raises(PlayerError, match='There is no current subgoal. previous_outcome must be "none"'):
        call(app, reader, REPLACE, supersede())
    first = call(app, reader, REPLACE, replace())['records'][0]
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    current = first['id']
    before = store_rows(app)
    with pytest.raises(PlayerError, match=f'The current subgoal is {current} \\(open\\): "Reach the visible door". '
                       'previous_outcome "none" is only valid when there is no current subgoal.*player_level_keep or player_level_close'):
        call(app, reader, REPLACE, replace('Next'))
    with pytest.raises(PlayerError, match=f'The current subgoal is {current}.*previous_reason must say why it was failed'):
        call(app, reader, REPLACE, replace('Next', outcome='failed', reason=' '))
    assert store_rows(app) == before
    # The fixable errors kept the bound, so the corrected call commits without a new bind.
    assert call(app, reader, KEEP, keep())['kept'] == [current]


def test_state_errors_fit_the_custodian_error_bound(level):
    app, channel, actor, reader, recorder = level
    first = commit_first(app, actor, reader, recorder)
    bind(app, reader)
    with pytest.raises(PlayerError) as raised:
        call(app, reader, REPLACE, replace('Next'))
    assert len(str(raised.value)) <= 600 and first['id'] in str(raised.value)


@pytest.mark.parametrize('tool,change', [
    (KEEP, dict(reason='')), (KEEP, dict(reason='  ')), (KEEP, dict(reason='r' * 1025)), (KEEP, dict(sources=['s'] * 17)),
    (KEEP, dict(sources='s')), (KEEP, dict(extra=1)),
    (CLOSE, dict(outcome='revised')), (CLOSE, dict(outcome='done')), (CLOSE, dict(reason='')), (CLOSE, dict(reason='r' * 1025)),
    (REPLACE, dict(status='closed')), (REPLACE, dict(text='t' * 2049)), (REPLACE, dict(text=' ')),
    (REPLACE, dict(expected_observations=['o'] * 9)), (REPLACE, dict(expected_observations=['o' * 513])),
    (REPLACE, dict(expected_observations=[])),
    (REPLACE, dict(sources=['s'] * 17)), (REPLACE, dict(confidence=1.5)), (REPLACE, dict(confidence=-.1)),
    (REPLACE, dict(previous_outcome='done')), (REPLACE, dict(previous_reason='r' * 1025)), (REPLACE, dict(extra=1))])
def test_bounds_and_closed_enums_hold_and_keep_the_bound(level, tool, change):
    app, channel, actor, reader, recorder = level
    commit_first(app, actor, reader, recorder)
    bind(app, reader)
    base = dict(keep=keep(), close=close(), replace=supersede())[tool.removeprefix('player_level_')]
    with pytest.raises(PlayerError):
        call(app, reader, tool, dict(base, **change))
    assert app.readers[reader['actor_id']]['bound'] is not None
    assert call(app, reader, tool, base)['status'] == 'committed'


@pytest.mark.parametrize('tool,missing', [(KEEP, 'reason'), (KEEP, 'sources'), (CLOSE, 'outcome'), (REPLACE, 'previous_outcome'),
                                          (REPLACE, 'text'), (REPLACE, 'confidence')])
def test_every_property_is_required(level, tool, missing):
    app, channel, actor, reader, recorder = level
    commit_first(app, actor, reader, recorder)
    bind(app, reader)
    base = dict(keep=keep(), close=close(), replace=supersede())[tool.removeprefix('player_level_')]
    del base[missing]
    with pytest.raises(PlayerError, match=missing):
        call(app, reader, tool, base)


def test_abstain_writes_nothing_clears_the_bound_and_reports_its_code(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    assert app.readers[reader['actor_id']]['bound'] == 1
    before = store_rows(app)
    result = call(app, reader, ABSTAIN, dict(reason_code='no_change_needed', reason='The episodes show nothing to act on',
                                             sources=[]))
    assert result == dict(schema='player-level-abstain/2', status='abstained', reason_code='no_change_needed',
                          reason='The episodes show nothing to act on')
    assert store_rows(app) == before and app.readers[reader['actor_id']]['bound'] is None
    # Like any terminal call, it ended the pass: without a new bind nothing binds.
    assert call(app, reader, REPLACE, replace())['reason'] == 'No position was bound for this pass'


@pytest.mark.parametrize('code', ['insufficient_evidence', 'transient_screen_state', 'no_change_needed', 'other'])
def test_abstain_accepts_each_closed_reason_code_with_empty_sources(level, code):
    app, channel, actor, reader, recorder = level
    bind(app, reader)
    assert call(app, reader, ABSTAIN, dict(reason_code=code, reason='ok', sources=[]))['reason_code'] == code


@pytest.mark.parametrize('args', [
    {}, dict(reason_code='other', sources=[]), dict(reason='ok', sources=[]), dict(reason_code='unknown', reason='ok', sources=[]),
    dict(reason_code='unreadable_frames', reason='ok', sources=[]),
    dict(reason_code='other', reason='', sources=[]), dict(reason_code='other', reason='  ', sources=[]),
    dict(reason_code='other', reason='r' * 1025, sources=[]), dict(reason_code='other', reason=3, sources=[]),
    dict(reason_code='other', reason='ok', sources=[], extra=1), dict(reason_code='other', reason='ok')])
def test_abstain_needs_a_code_a_bounded_reason_and_sources(level, args):
    app, channel, actor, reader, recorder = level
    bind(app, reader)
    with pytest.raises((PlayerError, ControlError)):
        call(app, reader, ABSTAIN, args)
    assert app.readers[reader['actor_id']]['bound'] == 0


def test_abstain_checks_its_cited_sources(level):
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, ABSTAIN, dict(reason_code='other', reason='ok', sources=['missing']))
    assert app.readers[reader['actor_id']]['bound'] == 1
    cited = first['source']['source_id']
    assert call(app, reader, ABSTAIN, dict(reason_code='other', reason='ok', sources=[cited]))['status'] == 'abstained'


def test_keep_registers_no_frames_but_still_needs_its_citations_available(level):
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    call(app, reader, REPLACE, replace())
    bind(app, reader)
    before = store_rows(app), source_rows(app)
    cited = first['source']['source_id']
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, KEEP, keep(sources=[cited, 'missing']))
    kept = call(app, reader, KEEP, keep(sources=[cited]))
    assert kept['status'] == 'committed' and kept['records'] == []
    # Only the service row is new: the cited frame was not copied into the player store.
    assert (store_rows(app)[0], source_rows(app)) == (before[0][0], before[1])
    bind(app, reader)
    closed = call(app, reader, CLOSE, close(sources=[cited]))
    assert closed['status'] == 'committed' and source_rows(app) == before[1] + 1


def test_retained_commit_identity_collects_without_recommitting(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
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
    bind(app, reader)
    kept_id = request_id()
    kept = call(app, reader, KEEP, keep(), kept_id)
    assert call(app, reader, KEEP, keep(), kept_id) == kept
    assert app.memory.service_result(kept_id, reader['actor_id'])['value'] == kept


def test_unavailable_cited_source_writes_nothing_and_keeps_the_pass(level):
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    work = call(app, reader, REPLACE, replace())['records'][0]
    bind(app, reader)
    before = store_rows(app), source_rows(app)
    valid = first['source']['source_id']
    with pytest.raises(PlayerError, match='unavailable: missing'):
        call(app, reader, REPLACE, supersede('Next', sources=[valid, 'missing']))
    assert (store_rows(app), source_rows(app)) == before
    assert [r['id'] for r in app.memory.current('work')] == [work['id']]
    assert app.remember_failure is None
    corrected = call(app, reader, REPLACE, supersede('Next', sources=[valid]))
    assert corrected['status'] == 'committed' and source_rows(app) == before[1] + 1


def test_source_capacity_failure_writes_nothing_and_stops_the_recorder_and_the_level_but_not_the_actor(level):
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    channel.capture = 2
    second = call(app, actor, 'computer_observe', {})['source']['source_id']
    assert second != first['source']['source_id']
    sync(app, actor, recorder)
    bind(app, reader)
    # Room for one PNG only: the cited frames do not fit, and nothing is evicted.
    app.memory.max_source_bytes = len(channel.png)
    before = store_rows(app), source_rows(app)
    with pytest.raises(PlayerError, match='capacity'):
        call(app, reader, REPLACE, replace(sources=[first['source']['source_id'], second]))
    assert (store_rows(app), source_rows(app)) == before
    assert 'source capacity' in app.remember_failure and app.status()['remember_failure'] == app.remember_failure
    # The level and the recorder are stopped for the session, and a fixed call is no exception.
    for capability, name, args in ((reader, REPLACE, replace(sources=[second])), (reader, ABSTAIN, dict(
            reason_code='other', reason='r', sources=[])), (recorder, EPISODE_ABSTAIN, dict(
            reason_code='other', reason='r', sources=[]))):
        with pytest.raises(ControlError, match='stopped for this session'):
            call(app, capability, name, args)
    with pytest.raises(ControlError, match='stopped for this session'):
        bind(app, reader)
    with pytest.raises(ControlError, match='stopped for this session'):
        app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    # The actor is unaffected: its input still works.
    assert act(app, actor)['status'] == 'completed' and not channel.stopped.is_set()


def test_a_storage_failure_while_remembering_stops_the_readers_too(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    app.memory._db.execute('PRAGMA query_only=ON')
    try:
        with pytest.raises(PlayerError, match='Cannot remember'):
            call(app, reader, REPLACE, replace())
    finally:
        app.memory._db.execute('PRAGMA query_only=OFF')
    assert 'Cannot remember' in app.remember_failure
    with pytest.raises(ControlError, match='stopped for this session'):
        call(app, reader, REPLACE, replace())
    assert act(app, actor)['status'] == 'completed'


def test_a_settle_the_driver_reports_can_still_try_after_a_failure_to_remember(level):
    app, channel, actor, reader, recorder = level
    act(app, actor, 2)
    app.remember_failure = 'fixture'
    receipt = app.settle_episode(recorder['actor_id'], first_position=1, last_position=2, subgoal_id=None,
                                 settled='failed', reason='the recorder stopped')
    assert receipt['record']['data']['settled'] == 'failed'


def test_commit_after_pause_or_deadline_is_discarded(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    app.runtime.stop('Operator Pause')
    result = call(app, reader, REPLACE, replace())
    assert result['status'] == 'discarded' and result['reason'] == 'Run stopped or fenced since the pass began'
    assert store_rows(app) == (1, 0)


def test_deadline_fences_a_commit(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    app.runtime.deadline = 0.
    assert call(app, reader, REPLACE, replace())['reason'] == 'Run stopped or fenced since the pass began'


def test_actor_start_pass_revalidates_before_any_input(level):
    app, channel, actor, reader, recorder = level
    assert bind(app, reader)['position'] == 0
    committed = call(app, reader, REPLACE, replace())
    assert committed['status'] == 'committed' and committed['position'] == 0 and committed['inputs_since'] == 0


def test_runtime_write_authorization_separates_reader_and_actor_writes(level):
    app, channel, actor, reader, recorder = level
    runtime = app.runtime
    assert runtime.authorize(reader['token'], write=True, reader_role='level') == reader['actor_id']
    assert runtime.authorize(recorder['token'], write=True, reader_role='recorder') == recorder['actor_id']
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(reader['token'], write=True)
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(reader['token'], write=True, reader_role='recorder')
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(recorder['token'], write=True, reader_role='level')
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(actor['token'], write=True, reader_role='level')
    with pytest.raises(ControlError, match='no such write'):
        runtime.authorize(actor['token'], write=True, reader_role='recorder')
    assert runtime.authorize(actor['token'], write=True) == actor['actor_id']


def test_reader_minting_refuses_more_than_one_current_level_subgoal_and_ignores_other_work(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    parameters = dict(stall_settles=3, confidence_floor=.5)
    try:
        flat = app.add_actor('flat')
        with pytest.raises(ControlError, match='narrowed-profile'):
            app.add_reader(flat['actor_id'], 'level', staleness_inputs=S, **parameters)
        sealed = call(app, flat, 'player_handoff', {})
        runtime.confirm_quiescent(flat['actor_id'], sealed['operation_id'], host_quiescent=True)
        actor = app.add_actor('narrowed')

        def work(index, level=False):
            memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text=f'work {index}',
                data=dict(level='subgoal', level_contract='player-level/4') if level else {}, sources=[], supports=[],
                supersedes=None, applicability=None, program_id=None))
        for index in range(16):
            work(index)
        work('one', level=True)
        work('two', level=True)
        # Other current Work is out of the level's scope; two level subgoals are not resolvable.
        with pytest.raises(ControlError, match='More than one current level subgoal'):
            app.add_reader(actor['actor_id'], 'level', staleness_inputs=S, **parameters)
        with pytest.raises(ControlError, match='More than one current level subgoal'):
            app.add_reader(actor['actor_id'], 'recorder', **parameters)
        memory.append(actor['actor_id'], dict(schema='player-record/1', kind='correction', text='ended',
            data={}, sources=[], supports=[], supersedes=memory.current('work')[-1]['id'], applicability=None, program_id=None))
        assert app.add_reader(actor['actor_id'], 'level', staleness_inputs=S, **parameters)['actor_id']
    finally:
        runtime.close(); memory.close()


def test_other_current_work_is_untouched_by_a_level_commit(level):
    app, channel, actor, reader, recorder = level
    other = app.memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text='not the level\'s',
        data={}, sources=[], supports=[], supersedes=None, applicability=None, program_id=None))
    commit_first(app, actor, reader, recorder)
    bind(app, reader)
    assert call(app, reader, CLOSE, close())['status'] == 'committed'
    assert [r['id'] for r in app.memory.current('work')] == [other['id']]


def test_level_records_are_counted_across_superseded_history_and_other_work_is_not(level):
    app, channel, actor, reader, recorder = level
    app.memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text='not the level\'s',
        data={}, sources=[], supports=[], supersedes=None, applicability=None, program_id=None))
    assert app.level_record_count() == 0
    commit_first(app, actor, reader, recorder)
    bind(app, reader)
    call(app, reader, REPLACE, supersede('Next'))
    assert app.level_record_count() == 2 and len(app.level_subgoals()) == 1


def test_call_timing_records_lock_wait_and_never_breaks_a_call(level):
    app, channel, actor, *_ = level
    rows = []
    app.timing = rows.append
    call(app, actor, 'computer_observe', {})
    assert rows[0]['tool'] == 'computer_observe' and rows[0]['wait_ms'] >= 0 and rows[0]['held_ms'] >= 0
    app.timing = lambda row: 1 / 0
    assert call(app, actor, 'computer_observe', {})['status'] == 'completed'


def test_reader_profiles_are_exactly_the_level_and_recorder_tools():
    assert PROFILES['level'] == ('player_source', KEEP, REPLACE, CLOSE, ABSTAIN)
    assert PROFILES['recorder'] == ('player_source', RECORD, EPISODE_ABSTAIN)
    assert 'reader' not in PROFILES
    removed = {'player_log_read', 'player_level_commit', 'player_memory_read', 'player_memory_query',
               'player_memory_context', 'player_program_read', 'player_result', 'computer_result'}
    for profile in ('level', 'recorder'):
        assert not removed & set(PROFILES[profile])
        assert set(PROFILES[profile]) <= set(tool_specs())
    assert not {RECORD, EPISODE_ABSTAIN} & {t for p in ('flat', 'narrowed') for t in PROFILES[p]}
    assert 'player_level_commit' not in tool_specs()


@pytest.mark.parametrize('which,name', [(3, n) for n in ('player_memory_read', 'player_memory_query', 'player_memory_context',
                                                         'player_program_read', 'player_result', 'computer_result',
                                                         'player_level_commit', RECORD)]
                         + [(4, n) for n in (KEEP, 'player_memory_read', 'player_result', 'computer_result')])
def test_the_readers_are_refused_the_removed_memory_program_result_and_foreign_tools(level, which, name):
    app, *_ = level
    # A removed tool is outside the class allowlist, or (as a write) outside the reader's pass-ending writes.
    with pytest.raises(ControlError, match='capability'):
        call(app, level[which], name, {})


def test_reader_mcp_adapter_binds_and_ends_a_pass_over_http(level, tmp_path):
    app, channel, actor, reader, recorder = level
    server, thread = serve(app, 0)
    try:
        config = tmp_path / 'reader.json'
        config.write_text(json.dumps(dict(schema='player-adapter/1', base_url=f'http://127.0.0.1:{server.server_port}',
                                          session=app.runtime.session, **reader)))
        client = PlayerClient(config)
        act(app, actor)
        sync(app, actor, recorder)
        bind(app, reader)
        committed, _, error = client.call(REPLACE, replace())
        assert not error and committed['status'] == 'committed'
        abstained, _, error = client.call(ABSTAIN, dict(reason_code='other', reason='Nothing changed', sources=[]))
        assert not error and abstained['status'] == 'abstained'
        refused, _, error = client.call('computer_input', dict(actions=[key()]))
        assert error and len(channel.calls) == 2
        refused, _, error = client.call(RECORD, {})
        assert error
        client.close()
        assert not channel.stopped.is_set()
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_refusals_name_the_offenders_and_the_valid_action_and_end_with_the_fix_line(level):
    from harness.player.contracts import LEVEL_FIX_LINE
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    channel.capture = 2
    second = call(app, actor, 'computer_observe', {})['source']['source_id']
    sync(app, actor, recorder)
    bind(app, reader)
    refused = []

    def refusal(tool, args):
        with pytest.raises(PlayerError) as raised:
            call(app, reader, tool, args)
        refused.append(str(raised.value))
        return str(raised.value)
    wrong = refusal(KEEP, keep())
    assert 'There is no current subgoal. player_level_keep needs a current subgoal.' in wrong
    missing = refusal(REPLACE, replace(sources=['ghost-' + 'x' * 100, 'other']))
    assert 'Cited sources are unavailable: ghost-' in missing and ', other.' in missing and 'pushed input' in missing
    assert 'unavailable' in refusal(ABSTAIN, dict(reason_code='other', reason='r', sources=['ghost']))
    invalid = refusal(REPLACE, replace(text=' '))
    assert 'text: must not be blank' in invalid
    schema = refusal(REPLACE, dict(replace(), status='closed', confidence=3, sources=['s'] * 20, text='t' * 3000))
    assert 'status' in schema
    assert all(message.endswith(LEVEL_FIX_LINE) and len(message) <= 600 for message in refused), refused
    # The line is the same text the host's validation refusals end with.
    host = (Path(__file__).parents[1] / 'tools/player_host/validation-feedback.mjs').read_text()
    assert f"FIX_LINE = '{LEVEL_FIX_LINE}'" in host
    assert first['source']['source_id'] != second


def test_reader_minting_refuses_a_current_level_record_of_another_contract(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    parameters = dict(stall_settles=3, confidence_floor=.5)
    try:
        actor = app.add_actor('narrowed')

        def level_work(text, **data):
            return memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text=text,
                data=dict(level='subgoal', **data), sources=[], supports=[], supersedes=None, applicability=None,
                program_id=None))

        def end(record):
            memory.append(actor['actor_id'], dict(schema='player-record/1', kind='correction', text='ended',
                data={}, sources=[], supports=[], supersedes=record['id'], applicability=None, program_id=None))
        for text, data in (('v2 record', dict(level_contract='player-level/2')),
                           ('v3 record', dict(level_contract='player-level/3')), ('unversioned record', {})):
            stale = level_work(text, **data)
            for role, extra in (('level', dict(staleness_inputs=S)), ('recorder', {})):
                with pytest.raises(ControlError, match='Unsupported level record contract.*migrate or start a fresh player store') as raised:
                    app.add_reader(actor['actor_id'], role, **parameters, **extra)
                assert stale['id'] in str(raised.value) and 'player-level/4' in str(raised.value)
            # Superseded history of another contract is not current and does not refuse.
            end(stale)
        level_work('current record', level_contract='player-level/4')
        assert app.add_reader(actor['actor_id'], 'level', staleness_inputs=S, **parameters)['actor_id']
    finally:
        runtime.close(); memory.close()


def test_the_session_store_is_computer_session_3_with_a_reader_role_column(level):
    app, *_ = level
    store = app.runtime.store
    assert store.connection.execute('PRAGMA user_version').fetchone()[0] == 3
    assert json.loads(store.connection.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0]) == 'computer-session/3'
    columns = {row[1] for row in store.connection.execute('PRAGMA table_info(actors)')}
    assert {'serves', 'reader_role'} <= columns
    indexes = {row[1] for row in store.connection.execute('PRAGMA index_list(actors)')}
    assert 'one_reader_per_actor_role' in indexes and 'one_reader_per_actor' not in indexes
    # A role is required of a reader, and refused for an actor.
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.add_actor('e' * 32, 'e' * 64, app.readers and next(iter(app.readers.values()))['serves'], None)
    with pytest.raises(sqlite3.IntegrityError):
        store.add_actor('d' * 32, 'd' * 64, None, 'level')
    with pytest.raises(sqlite3.IntegrityError):
        store.add_actor('c' * 32, 'c' * 64, next(iter(app.readers.values()))['serves'], 'viewer')


@pytest.mark.parametrize('tool,args,collect_with', [
    (REPLACE, replace(), None), (KEEP, keep(), None), (CLOSE, close(), None),
    (ABSTAIN, dict(reason_code='other', reason='r', sources=[]), None), ('player_source', dict(source_id='x'), 'player_result')])
def test_a_readers_lost_terminal_call_is_unknown_with_no_collecting_tool(level, tmp_path, tool, args, collect_with):
    app, channel, actor, reader, recorder = level
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
        assert 'player_result' not in PROFILES['level'] and value['input_replayed'] is False
        client.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
