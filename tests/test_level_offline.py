"""The offline-fixture stage over a synthetic recorded run; mechanism only, no provider or game."""
import io
import json
import random
import sqlite3

from PIL import Image

from tools.level_offline import cut_run, load, projection_check, simulate, stage

THETA = 0.1251514705882353


def recorded_run(root, inputs=30, interval=2., latency=1., block=5):
    """A recorded single-actor run whose capture changes every `block` inputs, so the cutter has content boundaries."""
    run = root / 'run'
    (run / 'actors/001').mkdir(parents=True)
    (run / 'sources').mkdir()
    database = sqlite3.connect(run / 'session.sqlite3')
    database.execute('CREATE TABLE operations(id TEXT PRIMARY KEY,actor TEXT NOT NULL,kind TEXT NOT NULL,'
                     'created_wall REAL NOT NULL,deadline REAL NOT NULL,input_json TEXT NOT NULL,final_json TEXT)')
    events = []
    for index in range(inputs):
        identity, at = f'{index:032x}', 1000. + index * interval
        source = f'{"a" * 32}-{index + 1}'
        out = io.BytesIO()
        Image.new('L', (8, 8), 0 if (index // block) % 2 == 0 else 200).save(out, format='PNG')
        (run / 'sources' / f'{source}.png').write_bytes(out.getvalue())
        final = dict(schema='computer-operation/1', operation_id=identity, session='a' * 32, actor_id='b' * 32,
                     kind='input', status='completed', created_wall=at, deadline_monotonic=at + 15, receipts=[],
                     source=dict(source_id=source), remaining={}, reason='fixture', handoff=None)
        database.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', (identity, 'b' * 32, 'input', at, at + 15,
            json.dumps([dict(type='key', key='x', modifiers=[])]), json.dumps(final)))
        stamp = lambda t: f'1970-01-01T00:{int(t) // 60:02d}:{t % 60:06.3f}Z'
        events += [dict(type='request-start', request_id=f'request-{index + 1}', wall_time=stamp(at - latency)),
                   dict(type='response-complete', request_id=f'request-{index + 1}', wall_time=stamp(at))]
    database.commit(); database.close()
    (run / 'actors/001/host.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    return run


def sim(recorded, pool, **changes):
    values = dict(theta=THETA, m=2, cap=10, s=3, backlog=3, recorder_requests=1, level_requests=1, rng=random.Random(1))
    return simulate(recorded, pool, **{**values, **changes})


def test_recorded_operations_round_trip_through_the_current_projection(tmp_path):
    check = projection_check(load(recorded_run(tmp_path)))
    assert check['matches_recorded'] and check['positions_contiguous'] and check['entries'] == check['operations'] == 30
    assert check['counts'] == [30, 30] and check['pending'] == 0


def test_the_production_cutter_cuts_the_recorded_timeline_on_content_and_at_the_edge(tmp_path):
    cuts = cut_run(load(recorded_run(tmp_path)), theta=THETA, m=2, cap=10)
    assert [(e.first_position, e.last_position, e.closed_by) for e, _ in cuts] == [
        (1, 5, 'content'), (6, 10, 'content'), (11, 15, 'content'), (16, 20, 'content'), (21, 25, 'content'), (26, 30, 'edge')]
    # A content cut closes when the crossing input's result arrives; the edge at the last operation.
    assert [wall for _, wall in cuts] == [1010., 1020., 1030., 1040., 1050., 1058.]
    (tmp_path / 'again').mkdir()
    capped = cut_run(load(recorded_run(tmp_path / 'again', block=100)), theta=THETA, m=2, cap=10)
    assert [(e.inputs, e.closed_by) for e, _ in capped] == [(10, 'cap'), (10, 'cap'), (10, 'cap')]


def test_staleness_follows_pass_latency_against_the_input_interval(tmp_path):
    recorded = load(recorded_run(tmp_path))
    fast = sim(recorded, [1.])
    # Episodes close every 10 s; a 1 s recorder pass and a 1 s level pass land 2 s after the close, and the bound is the
    # end of the settled episode, so at most the crossing input and the next one have moved: under S = 3.
    assert fast['passes'] > 0 and fast['commits'] == fast['passes'] and set(fast['moved']) <= {1, 2}
    assert fast['dropped'] == 0 and fast['recorder_passes'] == fast['episodes'] == 6
    slow = sim(recorded, [8.], s=2)
    # An 8 s recorder pass and an 8 s level pass: eight inputs pass the bound, at least S = 2, so every observed pass is
    # discarded; a pass committing after the recording's last input is censored, not counted.
    assert slow['passes'] > 0 and slow['commits'] == 0 and min(slow['moved']) >= 2 and slow['censored'] >= 1


def test_a_slow_recorder_overflows_the_backlog_and_drops_the_oldest_waiting_episodes(tmp_path):
    recorded = load(recorded_run(tmp_path, inputs=60, block=2))
    slow = sim(recorded, [30.], backlog=3)
    assert slow['episodes'] == 30 and slow['dropped'] > 0 and slow['dropped_share'] > 0
    # Every episode settles exactly once: recorded by the recorder or dropped from the backlog.
    assert slow['recorder_passes'] + slow['dropped'] == slow['episodes']
    quick = sim(recorded, [.1], backlog=3)
    assert quick['dropped'] == 0 and quick['recorder_passes'] == quick['episodes']


def test_the_stage_reports_the_coupling_for_the_given_parameters(tmp_path):
    report = stage([recorded_run(tmp_path)], theta=THETA, m=2, cap=10, s=3, backlog=3, recorder_requests=1, level_requests=1,
                   replicates=20, seed=7)
    assert report['schema'] == 'level-offline-stage/3' and report['parameters']['theta'] == THETA
    (run,) = report['runs']
    assert run['episodes'] == 6 and run['mean_episode_inputs'] == 5 and run['projection']['matches_recorded']
    assert run['reader_request_overhead'] > 0 and report['pooled_commit_rate'] == 1.
