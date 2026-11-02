"""The offline-fixture stage over a synthetic recorded run; mechanism only, no provider or game."""
import json
import random
import sqlite3

from tools.level_offline import load, projection_check, simulate


def recorded_run(root, inputs=30, interval=2., latency=1.):
    run = root / 'run'
    (run / 'actors/001').mkdir(parents=True)
    database = sqlite3.connect(run / 'session.sqlite3')
    database.execute('CREATE TABLE operations(id TEXT PRIMARY KEY,actor TEXT NOT NULL,kind TEXT NOT NULL,'
                     'created_wall REAL NOT NULL,deadline REAL NOT NULL,input_json TEXT NOT NULL,final_json TEXT)')
    events = []
    for index in range(inputs):
        identity, at = f'{index:032x}', 1000. + index * interval
        final = dict(schema='computer-operation/1', operation_id=identity, session='a' * 32, actor_id='b' * 32,
                     kind='input', status='completed', created_wall=at, deadline_monotonic=at + 15, receipts=[],
                     source=dict(source_id=f'{"a" * 32}-{index + 1}'), remaining={}, reason='fixture', handoff=None)
        database.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', (identity, 'b' * 32, 'input', at, at + 15,
            json.dumps([dict(type='key', key='x', modifiers=[])]), json.dumps(final)))
        stamp = lambda t: f'1970-01-01T00:{int(t) // 60:02d}:{t % 60:06.3f}Z'
        events += [dict(type='request-start', request_id=f'request-{index + 1}', wall_time=stamp(at - latency)),
                   dict(type='response-complete', request_id=f'request-{index + 1}', wall_time=stamp(at))]
    database.commit(); database.close()
    (run / 'actors/001/host.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    return run


def test_recorded_operations_round_trip_through_the_current_projection(tmp_path):
    check = projection_check(load(recorded_run(tmp_path)))
    assert check['matches_recorded'] and check['positions_contiguous'] and check['entries'] == check['operations'] == 30
    assert check['counts'] == [30, 30] and check['pending'] == 0


def test_staleness_follows_pass_latency_against_the_input_interval(tmp_path):
    recorded = load(recorded_run(tmp_path))
    fast = simulate(recorded, [1.], k=5, s=3, fractions=(), requests_per_pass=2, allowance=30, rng=random.Random(1))
    # The bound is the push at launch and the commit lands after both responses (2 s): a 2 s window
    # at a 2 s input interval holds at most one input, under S=3.
    assert fast['passes'] > 0 and fast['commits'] == fast['passes'] and set(fast['moved']) <= {0, 1}
    assert fast['level_requests'] == (fast['passes'] + fast['censored']) * 2
    slow = simulate(recorded, [4.], k=5, s=3, fractions=(), requests_per_pass=2, allowance=30, rng=random.Random(1))
    # Bound at launch, commit 8 s later: four inputs pass, at least S=3, so every observed pass is
    # discarded; a pass committing after the recording's last input is censored, not counted.
    assert slow['passes'] > 0 and slow['commits'] == 0 and min(slow['moved']) >= 3 and slow['censored'] >= 1


def test_v2_timing_has_no_read_delay_and_no_closing_turn(tmp_path):
    recorded = load(recorded_run(tmp_path, interval=10.))
    # One 4 s response: the bound is the launch, so a 10 s input interval never lets an input in before the commit.
    one = simulate(recorded, [4.], k=1, s=1, fractions=(), requests_per_pass=1, allowance=30, rng=random.Random(1))
    assert one['passes'] > 0 and one['commits'] == one['passes'] and set(one['moved']) == {0}
