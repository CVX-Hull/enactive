"""The episode recorder, episode settles, trust, derived status and stall, and software closure (level v4).

Actual composition and SQLite over a receiver double; no provider, game or recorder host.
"""
import time
from unittest.mock import patch

import pytest

from episode_support import (ABSTAIN, C, CLOSE, EPISODE_ABSTAIN, KEEP, N, RECORD, REPLACE, S, act, bind, call,
                             commit_first, current_id, episode, keep, mint, recorded, replace, request_id,
                             store_rows, sync, total)
from harness.application import Application
from harness.computer.protocol import ControlError
from harness.player.contracts import PlayerError, level_tool_schema
from harness.player.episodes import claim_data, derive, episode as trusted_episode
from harness.player.memory import Memory
from harness.player_tools import tool_specs
from harness.computer.runtime import ComputerRuntime
from test_computer_runtime import Channel, Process, make_runtime

OBSERVATIONS = ['The door tile is adjacent']


def claims(app):
    return [r for r in app.memory.query(kind='claim', limit=50)]


def with_subgoal(app, actor, reader, recorder, observations=None):
    """A committed first subgoal (default one expected observation); returns its Work record."""
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    return call(app, reader, REPLACE, replace(observations=observations))['records'][0]


# --- The recorder's tools ---

def test_a_record_settles_the_episode_with_one_claim_and_the_recorder_as_actor(level):
    app, channel, actor, reader, recorder = level
    work = with_subgoal(app, actor, reader, recorder)
    sync(app, actor, recorder)
    act(app, actor, 2)
    first = app._settled_end(actor['actor_id']) + 1
    bound = app.bind_episode(recorder['actor_id'], first_position=first, last_position=first + 1, subgoal_id=work['id'])
    assert bound['subgoal'] == dict(record_id=work['id'], text='Reach the visible door', expected_observations=OBSERVATIONS)
    assert [e['position'] for e in bound['operations']] == [first, first + 1]
    cited = bound['sources'][-1]
    receipt = call(app, recorder, RECORD, dict(attempted='Walked to the door', counterpart='the guard',
        observation_status=['seen'], residual='A bell rang', changed='The door is open (see frame)', confidence=.8,
        sources=[cited]))
    (claim, closure) = receipt['records']
    assert receipt['schema'] == 'player-episode-record/1' and receipt['status'] == 'recorded'
    assert (receipt['first_position'], receipt['last_position'], receipt['subgoal_id']) == (first, first + 1, work['id'])
    assert receipt['counted'] is True and receipt['closed'] is True and receipt['observations'] == ['seen']
    assert claim['kind'] == 'claim' and claim['actor_id'] == recorder['actor_id'] and claim['sources'] == [cited]
    assert claim['text'] == 'Walked to the door'
    assert claim['data'] == dict(level='episode', level_contract='player-episode/1', settled='recorded', writer='recorder',
        session=app.runtime.session, actor_id=actor['actor_id'], first_position=first, last_position=first + 1,
        subgoal_id=work['id'], attempted='Walked to the door', counterpart='the guard', observation_status=['seen'],
        residual='A bell rang', changed='The door is open (see frame)', confidence=.8)
    assert closure['actor_id'] == recorder['actor_id']
    # Only the cited frame was copied into player memory.
    assert app.memory.read_source(cited)[1] == channel.png
    assert app.readers[recorder['actor_id']]['episode'] is None


def test_the_changed_field_is_required_bounded_and_may_be_empty(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    args = recorded([])
    without = {k: v for k, v in args.items() if k != 'changed'}
    with pytest.raises(PlayerError, match='changed'):
        call(app, recorder, RECORD, without)
    with pytest.raises(PlayerError, match='changed'):
        call(app, recorder, RECORD, dict(args, changed='c' * 1025))
    with pytest.raises(PlayerError, match='changed'):
        call(app, recorder, RECORD, dict(args, changed=3))
    assert 'changed' in level_tool_schema(RECORD)['required']
    assert call(app, recorder, RECORD, dict(args, changed=''))['records'][0]['data']['changed'] == ''


@pytest.mark.parametrize('change', [
    dict(attempted=''), dict(attempted='  '), dict(attempted='a' * 1025), dict(counterpart='c' * 513),
    dict(observation_status=['maybe']), dict(observation_status=['seen'] * 9), dict(residual='r' * 1025),
    dict(confidence=1.5), dict(confidence=-.1), dict(confidence='high'), dict(sources=['s'] * 5),
    dict(sources='s'), dict(extra=1)])
def test_record_validation_is_closed_and_keeps_the_episode_bound(level, change):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    with pytest.raises(PlayerError):
        call(app, recorder, RECORD, dict(recorded([]), **change))
    assert store_rows(app) == (0, 0) and app.readers[recorder['actor_id']]['episode'] is not None
    assert call(app, recorder, RECORD, recorded([]))['status'] == 'recorded'


@pytest.mark.parametrize('missing', ['attempted', 'counterpart', 'observation_status', 'residual', 'changed',
                                     'confidence', 'sources'])
def test_every_record_property_is_required(level, missing):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    args = recorded([])
    del args[missing]
    with pytest.raises(PlayerError, match=missing):
        call(app, recorder, RECORD, args)


def test_observation_status_length_must_equal_the_pushed_subgoals_expected_observations(level):
    app, channel, actor, reader, recorder = level
    work = with_subgoal(app, actor, reader, recorder, observations=['one', 'two', 'three'])
    sync(app, actor, recorder)
    act(app, actor)
    end = app._settled_end(actor['actor_id'])
    app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=end + 1, subgoal_id=work['id'])
    for marks in ([], ['seen'], ['seen'] * 4):
        with pytest.raises(PlayerError, match='observation_status must be 3 entries'):
            call(app, recorder, RECORD, recorded(marks))
    assert call(app, recorder, RECORD, recorded(['not_yet', 'seen', 'contradicted']))['counted'] is True
    # With no subgoal pushed, the array must be empty.
    act(app, actor)
    end = app._settled_end(actor['actor_id'])
    app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=end + 1, subgoal_id=None)
    with pytest.raises(PlayerError, match='must be empty'):
        call(app, recorder, RECORD, recorded(['seen']))
    assert call(app, recorder, RECORD, recorded([]))['counted'] is False


def test_cited_sources_must_be_frames_of_the_pushed_episode_baseline_included(level):
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    channel.capture = 2
    second = act(app, actor)
    channel.capture = 3
    third = act(app, actor)
    sources = [r['source']['source_id'] for r in (first, second, third)]
    app.settle_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None, settled='dropped',
                       reason='fixture')
    bound = app.bind_episode(recorder['actor_id'], first_position=2, last_position=2, subgoal_id=None)
    # The baseline is the newest result frame before the episode; the episode's own frame follows it.
    assert bound['baseline_source'] == sources[0] and bound['sources'] == [sources[0], sources[1]]
    with pytest.raises(PlayerError, match='not frames of this episode: ' + sources[2]):
        call(app, recorder, RECORD, recorded([]) | dict(sources=[sources[1], sources[2]]))
    assert store_rows(app)[0] == 1
    receipt = call(app, recorder, RECORD, recorded([]) | dict(sources=[sources[0], sources[1], sources[1]]))
    assert receipt['records'][0]['sources'] == [sources[0], sources[1]]
    assert app.memory.read_source(sources[0])[1] == channel.png


def test_abstain_settles_with_a_claim_that_has_no_marks(level):
    app, channel, actor, reader, recorder = level
    work = with_subgoal(app, actor, reader, recorder)
    sync(app, actor, recorder)
    act(app, actor)
    end = app._settled_end(actor['actor_id'])
    app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=end + 1, subgoal_id=work['id'])
    receipt = call(app, recorder, EPISODE_ABSTAIN, dict(reason_code='unreadable_frames', reason='Black frames', sources=[]))
    (claim,) = receipt['records']
    assert receipt['schema'] == 'player-episode-abstain/1' and receipt['status'] == 'abstained'
    assert receipt['counted'] is False and receipt['closed'] is False
    assert claim['data'] == dict(level='episode', level_contract='player-episode/1', settled='abstained',
        writer='recorder', session=app.runtime.session, actor_id=actor['actor_id'], first_position=end + 1,
        last_position=end + 1, subgoal_id=work['id'], reason_code='unreadable_frames', reason='Black frames')
    assert 'observation_status' not in claim['data']


@pytest.mark.parametrize('code,valid', [('unreadable_frames', True), ('no_player_action', True), ('other', True),
                                        ('insufficient_evidence', False), ('transient_screen_state', False),
                                        ('no_change_needed', False)])
def test_episode_abstain_has_its_own_codes(level, code, valid):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    args = dict(reason_code=code, reason='ok', sources=[])
    if valid:
        assert call(app, recorder, EPISODE_ABSTAIN, args)['status'] == 'abstained'
    else:
        with pytest.raises(PlayerError, match='reason_code'):
            call(app, recorder, EPISODE_ABSTAIN, args)


def test_recorder_schemas_use_only_portable_keywords():
    allowed = {'type', 'enum', 'description', 'properties', 'required', 'items', 'additionalProperties', 'minLength',
               'maxLength', 'minItems', 'maxItems', 'minimum', 'maximum'}

    def keywords(node):
        found = set(node)
        for child in list(node.get('properties', {}).values()) + ([node['items']] if 'items' in node else []):
            found |= keywords(child)
        assert 'type' in node
        return found
    for tool in (RECORD, EPISODE_ABSTAIN):
        schema = tool_specs()[tool][1]
        assert keywords(schema) <= allowed and schema['additionalProperties'] is False
        assert set(schema['required']) == set(schema['properties'])
    assert list(tool_specs()[RECORD][1]['properties']) == ['attempted', 'counterpart', 'observation_status', 'residual',
                                                           'changed', 'confidence', 'sources']


def test_a_recorder_call_needs_a_bound_episode_and_settles_it_exactly_once(level):
    app, channel, actor, reader, recorder = level
    with pytest.raises(PlayerError, match='No episode is bound'):
        call(app, recorder, RECORD, recorded([]))
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    call(app, recorder, RECORD, recorded([]))
    with pytest.raises(PlayerError, match='No episode is bound'):
        call(app, recorder, RECORD, recorded([]))
    assert len(claims(app)) == 1
    # The same episode cannot be bound again, nor settled by software.
    with pytest.raises(PlayerError, match='already settled|overlaps'):
        app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    with pytest.raises(PlayerError, match='overlaps'):
        app.settle_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None, settled='dropped',
                           reason='late')
    assert len(claims(app)) == 1


def test_a_software_settle_that_beats_the_recorder_refuses_its_call(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    app.settle_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None, settled='failed',
                       reason='the pass timed out')
    # The settle of exactly the bound episode releases the binding.
    with pytest.raises(PlayerError, match='No episode is bound'):
        call(app, recorder, RECORD, recorded([]))
    # A settle that only overlaps the bound episode leaves it bound, and the recorder's call is refused as settled.
    act(app, actor, 2)
    app.bind_episode(recorder['actor_id'], first_position=2, last_position=3, subgoal_id=None)
    app.settle_episode(recorder['actor_id'], first_position=2, last_position=2, subgoal_id=None, settled='dropped',
                       reason='backlog')
    with pytest.raises(PlayerError, match='already settled'):
        call(app, recorder, RECORD, recorded([]))
    assert len(claims(app)) == 2 and app.readers[recorder['actor_id']]['episode'] is None


def test_bind_episode_refuses_bad_ranges_and_unknown_subgoals(level):
    app, channel, actor, reader, recorder = level
    work = with_subgoal(app, actor, reader, recorder)
    sync(app, actor, recorder)
    act(app, actor, 2)
    settled = app._settled_end(actor['actor_id'])
    count = total(app, actor)
    rid = recorder['actor_id']
    for first, last in ((0, 1), (settled + 2, settled + 1), (settled + 1, count + 1), (count + 1, count + 1)):
        with pytest.raises(PlayerError):
            app.bind_episode(rid, first_position=first, last_position=last, subgoal_id=None)
    # A range that overlaps a settled episode is refused.
    with pytest.raises(PlayerError, match='overlaps one that already settled'):
        app.bind_episode(rid, first_position=settled, last_position=count, subgoal_id=None)
    with pytest.raises(PlayerError, match='Unknown pushed subgoal'):
        app.bind_episode(rid, first_position=settled + 1, last_position=count, subgoal_id='nope')
    other = app.memory.append(actor['actor_id'], dict(schema='player-record/1', kind='work', text='x', data={},
        sources=[], supports=[], supersedes=None, applicability=None, program_id=None))
    with pytest.raises(PlayerError, match='not a player-level/4 level subgoal'):
        app.bind_episode(rid, first_position=settled + 1, last_position=count, subgoal_id=other['id'])
    with pytest.raises(ControlError, match='Not a recorder reader'):
        app.bind_episode(reader['actor_id'], first_position=settled + 1, last_position=count, subgoal_id=None)
    with pytest.raises(ControlError, match='Not a level reader'):
        app.bind_level(rid)
    assert app.bind_episode(rid, first_position=settled + 1, last_position=count, subgoal_id=work['id'])['sources']


def test_software_settles_are_failed_or_dropped_claims_stamped_software(level):
    app, channel, actor, reader, recorder = level
    act(app, actor, 2)
    rid = recorder['actor_id']
    for settled in ('recorded', 'abstained', 'other'):
        with pytest.raises(PlayerError, match='failed or dropped'):
            app.settle_episode(rid, first_position=1, last_position=1, subgoal_id=None, settled=settled, reason='r')
    for reason in ('', ' ', 'r' * 1025):
        with pytest.raises(PlayerError, match='reason'):
            app.settle_episode(rid, first_position=1, last_position=1, subgoal_id=None, settled='failed', reason=reason)
    failed = app.settle_episode(rid, first_position=1, last_position=1, subgoal_id=None, settled='failed', reason='timed out')
    dropped = app.settle_episode(rid, first_position=2, last_position=2, subgoal_id=None, settled='dropped', reason='backlog')
    assert failed['status'] == 'settled' and failed['settled'] == 'failed'
    assert failed['record']['actor_id'] == rid and failed['record']['sources'] == []
    assert failed['record']['data'] == dict(level='episode', level_contract='player-episode/1', settled='failed',
        writer='software', session=app.runtime.session, actor_id=actor['actor_id'], first_position=1, last_position=1,
        subgoal_id=None, reason='timed out')
    assert dropped['record']['data']['settled'] == 'dropped' and dropped['record']['data']['writer'] == 'software'
    with pytest.raises(ControlError, match='Not a recorder reader'):
        app.settle_episode(reader['actor_id'], first_position=1, last_position=1, subgoal_id=None, settled='failed', reason='r')
    assert [v['settled'] for v in app.settled_episodes()] == ['failed', 'dropped']


def test_a_retained_recorder_identity_collects_without_resettling(level):
    app, channel, actor, reader, recorder = level
    act(app, actor)
    app.bind_episode(recorder['actor_id'], first_position=1, last_position=1, subgoal_id=None)
    identity = request_id()
    first = call(app, recorder, RECORD, recorded([]), identity)
    assert call(app, recorder, RECORD, recorded([]), identity) == first and len(claims(app)) == 1
    with pytest.raises(PlayerError):
        call(app, recorder, RECORD, recorded([], attempted='Different'), identity)
    assert app.memory.service_result(identity, recorder['actor_id'])['value'] == first


# --- Trust: forged records ---

FORGERIES = [dict(level='episode'), dict(writer='recorder'), dict(writer='software'), dict(level='episode', writer='x',
             level_contract='player-episode/1', settled='recorded')]


def forged(data):
    return dict(schema='player-record/1', kind='claim', text='forged', data=data, sources=[], supports=[],
                supersedes=None, applicability=None, program_id=None)


@pytest.mark.parametrize('data', FORGERIES)
def test_the_general_memory_path_refuses_episode_and_writer_data(level, data):
    app, channel, actor, reader, recorder = level
    for kind in ('claim', 'work', 'correction', 'decision'):
        value = dict(forged(data), kind=kind, supersedes=None)
        if kind == 'correction':
            continue
        with pytest.raises(PlayerError, match='custodian settle path'):
            app.memory.append(actor['actor_id'], value)
        with pytest.raises(PlayerError, match='custodian settle path'):
            app.memory.append_many(actor['actor_id'], [value], request_id=request_id())
    # Not even the settle flag admits a non-claim carrying it.
    with pytest.raises(PlayerError, match='custodian settle path'):
        app.memory.append_many(actor['actor_id'], [dict(forged(data), kind='work')], request_id=request_id(), settle=True)
    assert store_rows(app) == (0, 0)


def test_a_flat_actor_cannot_forge_an_episode_through_the_tool(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        flat = app.add_actor('flat')
        for data in FORGERIES:
            identity = request_id()
            with pytest.raises(PlayerError, match='custodian settle path'):
                call(app, flat, 'player_memory_append', dict(record=forged(data)), identity)
            # Refused before any service row, so the identity is not left pending.
            assert memory._db.execute('SELECT COUNT(*) FROM service_operations WHERE id=?', (identity,)).fetchone()[0] == 0
        assert call(app, flat, 'player_memory_append', dict(record=forged(dict(level='subgoal'))))['kind'] == 'claim'
        assert memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0] == 1
    finally:
        runtime.close(); memory.close()


def test_a_forged_record_that_reached_the_store_is_never_trusted(level):
    app, channel, actor, reader, recorder = level
    work = commit_first(app, actor, reader, recorder)
    good = dict(forged(claim_data(session='z' * 32, actor_id='y' * 32, first_position=1, last_position=1,
        subgoal_id=work['id'], settled='recorded', attempted='forged', counterpart='', observation_status=['seen'],
        residual='', changed='', confidence=1.)), id='f' * 32, actor_id='x' * 32, created_wall=1.)
    # Each variant is stored raw, bypassing every writer, as old or hostile data could be.
    variants = [dict(good, id='1' * 32, data={k: v for k, v in good['data'].items() if k != 'writer'}),
                dict(good, id='2' * 32, data=dict(good['data'], writer='nobody')),
                dict(good, id='3' * 32, data=dict(good['data'], writer='software')),
                dict(good, id='4' * 32, data=dict(good['data'], level_contract='player-episode/0')),
                dict(good, id='5' * 32, data=dict(good['data'], confidence=7)),
                dict(good, id='6' * 32, data=dict(good['data'], first_position=3, last_position=1)),
                dict(good, id='7' * 32, kind='advice'),
                dict(good, id='8' * 32, data=dict(good['data'], observation_status=['yes'])),
                dict(good, id='9' * 32, data={k: v for k, v in good['data'].items() if k != 'changed'})]
    for item in variants:
        assert trusted_episode(item) is None, item['id']
    from harness.player.contracts import canonical
    for item in variants[:6] + variants[7:]:
        app.memory._db.execute('INSERT INTO records VALUES (?,?,?,?,?)', (item['id'], canonical(item), item['kind'],
                                                                           None, None))
    app.memory._db.commit()
    # Only the honest settle of commit_first's setup remains.
    assert [v['settled'] for v in app.settled_episodes()] == ['dropped']
    assert bind(app, reader)['position'] == total(app, actor)
    assert app._derived(actor['actor_id'], work)['counts']['episodes'] == 0
    assert app.intent(actor['actor_id'])['recall']['items'] == []
    # The honest claim with the same data is trusted.
    assert trusted_episode(dict(good, id='a' * 32, data=dict(good['data']))) is not None


# --- Derived status and stall ---

def marks_of(app, actor):
    return [o['status'] for o in app.intent(actor['actor_id'])['subgoal']['expected_observations']]


def test_status_follows_the_latest_counted_seen_or_contradicted_mark(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b', 'c'])
    assert marks_of(app, actor) == ['not_yet'] * 3
    episode(app, actor, recorder, ['seen', 'contradicted', 'not_yet'])
    assert marks_of(app, actor) == ['seen', 'contradicted', 'not_yet']
    # Contradicted then seen is seen; seen then contradicted is contradicted; not_yet changes nothing.
    episode(app, actor, recorder, ['contradicted', 'seen', 'not_yet'])
    assert marks_of(app, actor) == ['contradicted', 'seen', 'not_yet']
    episode(app, actor, recorder, ['not_yet', 'not_yet', 'not_yet'])
    assert marks_of(app, actor) == ['contradicted', 'seen', 'not_yet']
    assert app.level_subgoals()
    subgoal = app.intent(actor['actor_id'])['subgoal']
    assert subgoal['contradicted'] is True and subgoal['stalled'] is False
    assert subgoal['counts'] == dict(episodes=3, recorded=3, abstained=0, failed=0, dropped=0, counted=3, seen=1,
                                     contradicted=1)


def test_marks_count_only_from_recorded_claims_at_or_above_the_floor(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b'])
    episode(app, actor, recorder, ['seen', 'seen'], confidence=C - .01)
    assert marks_of(app, actor) == ['not_yet', 'not_yet']
    assert app.level_subgoals() and app.intent(actor['actor_id'])['subgoal']['counts']['counted'] == 0
    receipt = episode(app, actor, recorder, ['seen', 'not_yet'], confidence=C)
    assert receipt['counted'] is True and marks_of(app, actor) == ['seen', 'not_yet']


def test_a_claim_for_another_subgoal_is_ignored(level):
    app, channel, actor, reader, recorder = level
    first = with_subgoal(app, actor, reader, recorder)
    # An episode that began under an older subgoal id never marks the current subgoal.
    sync(app, actor, recorder)
    bind(app, reader)
    second = call(app, reader, REPLACE, replace('Second', outcome='revised', reason='x'))['records'][0]
    assert second['id'] != first['id']
    receipt = episode(app, actor, recorder, ['seen'], subgoal=first['id'])
    assert receipt['counted'] is False and receipt['closed'] is False and app.level_subgoals()[0]['id'] == second['id']
    assert marks_of(app, actor) == ['not_yet']
    assert app.intent(actor['actor_id'])['subgoal']['counts']['episodes'] == 0
    # A claim committed before the subgoal does not count either, even with the right id.
    sync(app, actor, recorder)
    assert episode(app, actor, recorder, ['seen'], subgoal=second['id'])['closed'] is True


def test_a_pass_stalls_after_n_settles_with_nothing_newly_seen_and_progress_resets_it(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b', 'c'])
    rid = recorder['actor_id']

    def settle_without_record(kind):
        act(app, actor)
        end, count = app._settled_end(actor['actor_id']), total(app, actor)
        if kind == 'abstained':
            app.bind_episode(rid, first_position=end + 1, last_position=count, subgoal_id=current_id(app))
            call(app, recorder, EPISODE_ABSTAIN, dict(reason_code='other', reason='r', sources=[]))
        else:
            app.settle_episode(rid, first_position=end + 1, last_position=count, subgoal_id=current_id(app),
                               settled=kind, reason='r')

    def stalled():
        return app.intent(actor['actor_id'])['subgoal']['stalled']
    episode(app, actor, recorder, ['seen', 'not_yet', 'not_yet'])
    for kind in ('failed', 'dropped'):
        settle_without_record(kind)
        assert not stalled()
    # An abstained settle is the third settle with nothing newly seen: N consecutive settles stall it.
    settle_without_record('abstained')
    assert stalled() and app.intent(actor['actor_id'])['subgoal']['counts'] == dict(
        episodes=4, recorded=1, abstained=1, failed=1, dropped=1, counted=1, seen=1, contradicted=0)
    # A recorded settle below the floor marks nothing, so it neither resets the run nor counts as seen.
    episode(app, actor, recorder, ['seen', 'seen', 'not_yet'], confidence=C - .1)
    assert stalled() and marks_of(app, actor) == ['seen', 'not_yet', 'not_yet']
    # A counted mark of b is newly seen: the run restarts.
    episode(app, actor, recorder, ['not_yet', 'seen', 'not_yet'], confidence=C)
    assert not stalled()


def test_a_below_floor_record_does_not_end_a_run_before_it_stalls(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b'])
    episode(app, actor, recorder, ['seen', 'not_yet'])
    for settled in ('failed', 'dropped'):
        act(app, actor)
        end, count = app._settled_end(actor['actor_id']), total(app, actor)
        app.settle_episode(recorder['actor_id'], first_position=end + 1, last_position=count,
                           subgoal_id=current_id(app), settled=settled, reason='r')
    assert not app.intent(actor['actor_id'])['subgoal']['stalled']
    episode(app, actor, recorder, ['seen', 'seen'], confidence=C - .1)
    assert app.intent(actor['actor_id'])['subgoal']['stalled']


def test_progress_resets_the_stall_count_and_re_marking_seen_is_not_progress(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b', 'c'])

    def stalled():
        return app.intent(actor['actor_id'])['subgoal']['stalled']
    for _ in range(N + 1):
        episode(app, actor, recorder, ['seen', 'not_yet', 'not_yet'])
        assert not stalled() or app.intent(actor['actor_id'])['subgoal']['counts']['episodes'] == N + 1
    assert stalled() and app.intent(actor['actor_id'])['subgoal']['counts']['seen'] == 1
    # b is newly seen: the run restarts.
    episode(app, actor, recorder, ['seen', 'seen', 'not_yet'])
    assert not stalled()
    episode(app, actor, recorder, ['contradicted', 'seen', 'not_yet'])
    episode(app, actor, recorder, ['not_yet', 'not_yet', 'not_yet'])
    assert not stalled()
    episode(app, actor, recorder, ['not_yet', 'not_yet', 'not_yet'])
    assert stalled()
    # a becomes seen again after being contradicted: that is progress.
    episode(app, actor, recorder, ['seen', 'not_yet', 'not_yet'])
    assert not stalled()


def test_keep_and_abstain_are_refused_while_stalled_and_name_replace_and_close(level):
    app, channel, actor, reader, recorder = level
    work = with_subgoal(app, actor, reader, recorder)
    for _ in range(N):
        episode(app, actor, recorder, ['not_yet'])
    sync(app, actor, recorder)
    bind(app, reader)
    before = store_rows(app)
    for tool, args in ((KEEP, keep()), (ABSTAIN, dict(reason_code='no_change_needed', reason='r', sources=[]))):
        with pytest.raises(PlayerError, match=f'{work["id"]} is stalled.*player_level_replace or player_level_close') as raised:
            call(app, reader, tool, args)
        assert len(str(raised.value)) <= 600 and tool in str(raised.value)
    assert store_rows(app) == before and app.readers[reader['actor_id']]['bound'] is not None
    # Replace and close stay available, and the refusal kept the pass.
    assert call(app, reader, REPLACE, replace('Next', outcome='failed', reason='stalled'))['status'] == 'committed'


def test_close_is_available_while_stalled(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder)
    for _ in range(N):
        episode(app, actor, recorder, ['not_yet'])
    sync(app, actor, recorder)
    bind(app, reader)
    assert call(app, reader, CLOSE, dict(outcome='failed', reason='stalled', sources=[]))['status'] == 'committed'


def test_a_keep_while_contradicted_must_cite_a_counted_contradicting_claims_source(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b'])
    act(app, actor)
    end = app._settled_end(actor['actor_id'])
    cited = app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=end + 1,
                             subgoal_id=current_id(app))['sources'][-1]
    call(app, recorder, RECORD, recorded(['contradicted', 'not_yet']) | dict(sources=[cited]))
    # A below-floor contradicting claim does not count, so its source does not unlock a keep.
    act(app, actor)
    end = app._settled_end(actor['actor_id'])
    other = app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=end + 1,
                             subgoal_id=current_id(app))['sources'][-1]
    channel.capture = 2
    call(app, recorder, RECORD, recorded(['not_yet', 'contradicted'], confidence=C - .1) | dict(sources=[other]))
    sync(app, actor, recorder)
    bind(app, reader)
    before = store_rows(app)
    for sources in ([], ['nonexistent']):
        with pytest.raises(PlayerError, match='contradicted expected observation \\(number 1\\).*must cite a frame'):
            call(app, reader, KEEP, keep(sources=sources))
    assert store_rows(app) == before
    assert call(app, reader, KEEP, keep(sources=[cited]))['status'] == 'committed'


def test_a_keep_over_a_contradiction_with_no_cited_frames_is_unavailable(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder)
    episode(app, actor, recorder, ['contradicted'])
    sync(app, actor, recorder)
    bind(app, reader)
    with pytest.raises(PlayerError, match='None of those records cites a frame, so keep is not available'):
        call(app, reader, KEEP, keep())
    assert call(app, reader, CLOSE, dict(outcome='failed', reason='contradicted', sources=[]))['status'] == 'committed'


def test_the_commit_receipt_reports_the_derived_status(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b'])
    episode(app, actor, recorder, ['seen', 'contradicted'])
    sync(app, actor, recorder)
    bind(app, reader)
    result = call(app, reader, REPLACE, replace('Next', outcome='revised', reason='contradicted'))
    assert result['derived'] == dict(observations=['seen', 'contradicted'], stalled=False)


# --- Closure ---

def test_closure_is_appended_in_the_records_transaction_with_the_recorder_as_actor(level):
    app, channel, actor, reader, recorder = level
    work = with_subgoal(app, actor, reader, recorder, observations=['a', 'b'])
    first = episode(app, actor, recorder, ['seen', 'not_yet'])
    assert first['closed'] is False and app.level_subgoals()[0]['id'] == work['id']
    act(app, actor)
    end = app._settled_end(actor['actor_id'])
    cited = app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=end + 1,
                             subgoal_id=work['id'])['sources']
    identity = request_id()
    receipt = call(app, recorder, RECORD, recorded(['seen', 'seen']) | dict(sources=cited), identity)
    claim, closing = receipt['records']
    assert receipt['closed'] is True and receipt['observations'] == ['seen', 'seen']
    assert closing['kind'] == 'correction' and closing['supersedes'] == work['id'] and closing['actor_id'] == recorder['actor_id']
    assert closing['data'] == dict(level='subgoal', level_contract='player-level/4', actor_id=actor['actor_id'],
        session=app.runtime.session, position=end + 1, outcome='achieved', by='software')
    assert closing['supports'] == [first['records'][0]['id'], claim['id']]
    assert closing['sources'] == cited and app.level_subgoals() == []
    # The service row, the claim and the closure committed in one transaction.
    assert app.memory.service_result(identity, recorder['actor_id'])['value'] == receipt


def test_closure_is_atomic_with_the_record_that_triggers_it(level):
    app, channel, actor, reader, recorder = level
    work = with_subgoal(app, actor, reader, recorder)
    act(app, actor)
    end = app._settled_end(actor['actor_id'])
    app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=end + 1, subgoal_id=work['id'])
    before = store_rows(app)
    real = app.memory._insert

    def failing(stored):
        if stored['kind'] == 'correction':
            raise PlayerError('closure insert failed')
        return real(stored)
    with patch.object(app.memory, '_insert', side_effect=failing), pytest.raises(PlayerError, match='closure insert failed'):
        call(app, recorder, RECORD, recorded(['seen']))
    # Neither the claim, the closure nor the service row was written, and the episode is still bound.
    assert store_rows(app) == before and app.level_subgoals()[0]['id'] == work['id']
    assert app.readers[recorder['actor_id']]['episode'] is not None
    assert app._overlapping(actor['actor_id'], end + 1, end + 1) is None
    assert call(app, recorder, RECORD, recorded(['seen']))['closed'] is True


def test_closure_needs_every_observation_counted_seen_and_never_fires_twice(level):
    app, channel, actor, reader, recorder = level
    with_subgoal(app, actor, reader, recorder, observations=['a', 'b'])
    assert episode(app, actor, recorder, ['seen', 'seen'], confidence=C - .1)['closed'] is False
    assert episode(app, actor, recorder, ['seen', 'contradicted'])['closed'] is False
    assert episode(app, actor, recorder, ['seen', 'not_yet'])['closed'] is False
    sync(app, actor, recorder)
    assert app.level_subgoals() != []
    receipt = episode(app, actor, recorder, ['not_yet', 'seen'])
    assert receipt['closed'] is True and app.level_subgoals() == []
    # With the subgoal closed, a later episode for it has no current subgoal to close or mark.
    later = episode(app, actor, recorder, ['seen', 'seen'], subgoal=receipt['subgoal_id'])
    assert later['closed'] is False and later['counted'] is False and len(later['records']) == 1


def test_closure_caps_supports_and_sources_at_sixteen_and_keeps_the_deciding_claims(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False, max_inputs=100, max_requests=200, max_frames=200)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        actor = app.add_actor('narrowed')
        reader, recorder = mint(app, actor)
        observations = [f'o{i}' for i in range(8)]
        act(app, actor)
        sync(app, actor, recorder)
        bind(app, reader)
        work = call(app, reader, REPLACE, replace(observations=observations))['records'][0]
        claim_ids, frames_of = [], []
        for index in range(20):
            # Twenty counted claims; observation i is first seen at claim 12 + i, so claim 19 closes the subgoal.
            marks = ['not_yet'] * 8
            if index >= 12:
                marks[index - 12] = 'seen'
            for _ in range(4):
                channel.capture += 1
                act(app, actor)
            end = app._settled_end(actor['actor_id'])
            bound = app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=total(app, actor),
                                     subgoal_id=work['id'])
            frames = bound['sources'][-4:]
            receipt = call(app, recorder, RECORD, recorded(marks) | dict(sources=frames))
            claim_ids.append(receipt['records'][0]['id'])
            frames_of.append(frames)
        assert receipt['closed'] is True and len(receipt['records']) == 2
        closing = receipt['records'][1]
        assert closing['data']['by'] == 'software' and closing['data']['outcome'] == 'achieved'
        # 20 counted claims and 80 frames were cited; the closure keeps 16 of each. The eight claims that made the
        # observations seen are always supported, then the newest others fill the cap.
        assert closing['supports'] == claim_ids[4:]
        assert closing['sources'] == [s for frames in reversed(frames_of[16:]) for s in frames]
        assert len(set(closing['sources'])) == 16
        for source in closing['sources']:
            assert app.memory.read_source(source)[1] == channel.png
    finally:
        runtime.close(); memory.close()


# --- Across sessions, one store ---

def second_session(tmp_path, memory, session):
    directory = tmp_path / f'session-{session[:4]}'
    directory.mkdir()
    runtime = ComputerRuntime(directory, session, Channel(), Process(), time.monotonic() + 60,
                              dict(max_inputs=20, max_requests=30, max_frames=40, max_bytes=2**30))
    return runtime, Application(runtime, memory, tmp_path / f'contexts-{session[:4]}')


def test_stall_and_status_derive_across_sessions_from_one_store(tmp_path):
    memory = Memory(tmp_path / 'player.sqlite3')
    runtimes = []
    try:
        runtime, app = second_session(tmp_path, memory, 'a' * 32)
        runtimes.append(runtime)
        actor = app.add_actor('narrowed')
        reader, recorder = mint(app, actor)
        work = with_subgoal(app, actor, reader, recorder, observations=['a', 'b'])
        episode(app, actor, recorder, ['seen', 'not_yet'])
        episode(app, actor, recorder, ['not_yet', 'not_yet'])
        episode(app, actor, recorder, ['not_yet', 'not_yet'])
        first = app.intent(actor['actor_id'])['subgoal']
        assert first['stalled'] is False and first['counts']['episodes'] == 3
        # Session b mints new readers over the same store: the subgoal and its claims carry over.
        runtime2, app2 = second_session(tmp_path, memory, 'b' * 32)
        runtimes.append(runtime2)
        actor2 = app2.add_actor('narrowed')
        reader2, recorder2 = mint(app2, actor2)
        carried = app2.intent(actor2['actor_id'])['subgoal']
        assert carried['record_id'] == work['id'] and carried['counts']['episodes'] == 3
        assert [o['status'] for o in carried['expected_observations']] == ['seen', 'not_yet']
        # One more non-progress settle in session b: the run since the last progress is now N across the sessions.
        act(app2, actor2)
        app2.settle_episode(recorder2['actor_id'], first_position=1, last_position=1, subgoal_id=work['id'],
                            settled='dropped', reason='backlog')
        assert app2.intent(actor2['actor_id'])['subgoal']['stalled'] is True
        assert app.intent(actor['actor_id'])['subgoal']['stalled'] is True
        bind(app2, reader2)
        with pytest.raises(PlayerError, match='is stalled'):
            call(app2, reader2, KEEP, keep())
        assert app2.intent(actor2['actor_id'])['age']['same_session'] is False
        # Session b's binding is its own episodes only; the earlier session's settles do not bind.
        assert app2.bind_level(reader2['actor_id'])['position'] == 1
        # Counts per subgoal, across both sessions.
        assert app2.subgoal_counts(actor2['actor_id']) == [dict(subgoal_id=work['id'], episodes=4, seen=1,
                                                                contradicted=0, closures=0, failures=0)]
    finally:
        for runtime in runtimes:
            runtime.close()
        memory.close()


def test_a_start_pass_in_a_new_session_is_refused_a_keep_for_a_stalled_subgoal(tmp_path):
    memory = Memory(tmp_path / 'player.sqlite3')
    runtimes = []
    try:
        runtime, app = second_session(tmp_path, memory, 'a' * 32)
        runtimes.append(runtime)
        actor = app.add_actor('narrowed')
        reader, recorder = mint(app, actor)
        with_subgoal(app, actor, reader, recorder)
        for _ in range(N):
            episode(app, actor, recorder, ['not_yet'])
        runtime2, app2 = second_session(tmp_path, memory, 'b' * 32)
        runtimes.append(runtime2)
        actor2 = app2.add_actor('narrowed')
        reader2, _ = mint(app2, actor2)
        assert bind(app2, reader2)['position'] == 0
        with pytest.raises(PlayerError, match='is stalled'):
            call(app2, reader2, KEEP, keep())
        with pytest.raises(PlayerError, match='is stalled'):
            call(app2, reader2, ABSTAIN, dict(reason_code='other', reason='r', sources=[]))
        assert call(app2, reader2, REPLACE, replace('Fresh', outcome='failed', reason='stalled'))['status'] == 'committed'
    finally:
        for runtime in runtimes:
            runtime.close()
        memory.close()


def test_derive_is_a_pure_function_of_the_trusted_claims():
    work = dict(id='w', data=dict(expected_observations=['a', 'b']))

    def view(settled, marks=None, confidence=.9, subgoal='w'):
        data = claim_data(session='s', actor_id='x', first_position=1, last_position=1, subgoal_id=subgoal, settled=settled,
                          **(dict(attempted='t', counterpart='', observation_status=marks, residual='', changed='',
                                  confidence=confidence) if settled == 'recorded' else dict(reason='r')))
        return trusted_episode(dict(kind='claim', id='c', data=data, sources=[], created_wall=1.))
    result = derive(work, [view('recorded', ['seen', 'not_yet']), view('failed'), view('recorded', ['seen', 'seen'], subgoal='z'),
                           view('dropped')], stall_settles=2, floor=.5)
    assert result['stalled'] is True and result['no_progress_settles'] == 2 and result['counts']['episodes'] == 3
    assert [o['status'] for o in result['observations']] == ['seen', 'not_yet'] and result['all_seen'] is False
    assert derive(work, [], stall_settles=1, floor=.5)['stalled'] is False
    # A mark array of the wrong length is a settle that counts as nothing.
    short = derive(work, [view('recorded', ['seen'])], stall_settles=1, floor=.5)
    assert short['stalled'] is True and short['counts']['counted'] == 0
