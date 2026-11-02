"""Shared fixtures and helpers for the level v4 tests: one narrowed actor with its level and recorder readers.

Actual composition and SQLite over the receiver double; no provider, game or host.
"""
import uuid

import pytest

from harness.application import Application
from harness.player.memory import Memory
from test_computer_runtime import key, make_runtime

S, N, C = 3, 3, .5
KEEP, REPLACE, CLOSE, ABSTAIN = ('player_level_keep', 'player_level_replace', 'player_level_close',
                                 'player_level_abstain')
RECORD, EPISODE_ABSTAIN = 'player_episode_record', 'player_episode_abstain'


def request_id():
    return uuid.uuid4().hex


def call(app, capability, name, args, identity=None):
    return app.call(capability['token'], name, args, identity or request_id())[0]


def keep(reason='Cited episodes', sources=()):
    return dict(reason=reason, sources=list(sources))


def close(outcome='achieved', reason='Cited episodes', sources=()):
    return dict(outcome=outcome, reason=reason, sources=list(sources))


def replace(text='Reach the visible door', sources=(), outcome='none', reason='', observations=None, **change):
    """A flat replace call; `outcome` and `reason` say what happened to the subgoal it replaces."""
    return dict(text=text, expected_observations=['The door tile is adjacent'] if observations is None else observations,
                status='open', confidence=.4, sources=list(sources), previous_outcome=outcome, previous_reason=reason,
                **change)


def supersede(text='Next', outcome='revised', sources=(), **change):
    return replace(text, sources, outcome, 'Cited episodes', **change)


def mint(app, actor, *, stall=N, floor=C, staleness=S):
    level = app.add_reader(actor['actor_id'], 'level', stall_settles=stall, confidence_floor=floor, staleness_inputs=staleness)
    recorder = app.add_reader(actor['actor_id'], 'recorder', stall_settles=stall, confidence_floor=floor)
    return level, recorder


@pytest.fixture
def level(tmp_path):
    """(app, channel, actor, level reader, recorder reader) for one narrowed actor."""
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    actor = app.add_actor('narrowed')
    reader, recorder = mint(app, actor)
    try:
        yield app, channel, actor, reader, recorder
    finally:
        runtime.close(); memory.close()


def act(app, actor, count=1):
    """`count` basic inputs by the actor; returns the last result."""
    result = None
    for _ in range(count):
        result = call(app, actor, 'computer_input', dict(actions=[key()]))
    return result


def total(app, actor):
    return app.runtime.store.actor_counts(actor['actor_id'])[0]


def sync(app, actor, recorder):
    """Settle every unsettled operation of the actor as one dropped episode (no subgoal), returning the new end."""
    end = app._settled_end(actor['actor_id'])
    count = total(app, actor)
    if count > end:
        app.settle_episode(recorder['actor_id'], first_position=end + 1, last_position=count, subgoal_id=None,
                           settled='dropped', reason='fixture')
    return count


def bind(app, reader):
    return app.bind_level(reader['actor_id'])


def current_id(app):
    subgoals = app.level_subgoals()
    return subgoals[-1]['id'] if subgoals else None


def recorded(marks, confidence=.9, **change):
    return dict(attempted='Walked toward the door', counterpart='', observation_status=list(marks), residual='',
                changed='', confidence=confidence, sources=[]) | change


def episode(app, actor, recorder, marks, *, confidence=.9, subgoal='current', inputs=1, sources=(), identity=None,
            **change):
    """Act `inputs` times, bind the episode of every unsettled operation and record it; returns the receipt."""
    act(app, actor, inputs)
    end, count = app._settled_end(actor['actor_id']), total(app, actor)
    pushed = current_id(app) if subgoal == 'current' else subgoal
    app.bind_episode(recorder['actor_id'], first_position=end + 1, last_position=count, subgoal_id=pushed)
    return call(app, recorder, RECORD, recorded(marks, confidence, **change) | dict(sources=list(sources)), identity)



def commit_first(app, actor, reader, recorder, **change):
    """Act, settle the log and commit a first subgoal; returns its Work record."""
    act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    return call(app, reader, REPLACE, replace(**change))['records'][0]


def put(memory, actor_id, value):
    """Store a record the way the custodian's own paths do (reserved level/episode data allowed); returns it.

    The general append path refuses such data, so tests that need a prior or foreign level record use this.
    """
    return memory.append_many(actor_id, [value], request_id=request_id(), custodian=True)[0]


def store_rows(app):
    return (app.memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0],
            app.memory._db.execute('SELECT COUNT(*) FROM service_operations').fetchone()[0])


def source_rows(app):
    return app.memory._db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]
