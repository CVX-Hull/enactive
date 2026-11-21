"""The curator runner's rules (#845), with its snapshot, session, tag look and clock injected; and one run
beside a synthetic growing trace with the real reader and a real session under the sandbox. No game, no provider.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import textwrap
import threading
import time

import pytest

from harness.curator import runner as live
from harness.curator import sandbox
from harness.curator.gate import COVERAGE
from harness.curator.knowledge import Repository
from harness.curator.runner import ActorSteps, Outcome, Reading, Runner, Settings, TagLook, choose, covered
from harness.curator.session import SessionConfig, SessionError, run_session
from harness.curator.window import Window
from harness.trace.snapshot import BoundExceeded, ReadRefused, SnapshotError
from harness.trace.stores import sealed
from tests.curator_stand_in import StandIn
from tests.curator_trace import LiveWriter, make_long_session
from tools.curator_host import live_runner, shadow

RUN = 'run'
SETTINGS = Settings(trigger_steps=20, ceiling_steps=40, poll_seconds=15, watch_seconds=60)


def read(steps: dict[str, int], ended: tuple[str, ...] = ()) -> Reading:
    return Reading(Path('/snapshots')/RUN, tuple(ActorSteps(a, tuple(f'op-{a}-{n}' for n in range(1, count + 1)), a in ended)
                                              for a, count in steps.items()), .01, .005, .05)


class Clock:
    def __init__(self):
        self.now, self.lock = 1000.0, threading.Lock()

    def time(self):
        with self.lock:
            self.now += 1
            return self.now

    monotonic = time


class World:
    """A fake live run and knowledge repository: what the snapshot shows, the tags, and the sessions called."""

    def __init__(self, directory: Path, settings: Settings = SETTINGS):
        self.directory, self.settings = directory, settings
        self.reading: Reading | object = read({})
        self.tags: dict[str, dict] = {'v0': dict(coverage=None, restored_from=None)}
        self.outcomes: list = []
        self.calls: list[Window] = []
        self.snapshots = 0
        self.clock = Clock()
        self.during = None

    def snapshot(self, parent: Path) -> Reading:
        assert parent.is_dir() and not any(parent.iterdir())
        self.snapshots += 1
        value = self.reading.pop(0) if isinstance(self.reading, list) else self.reading
        if isinstance(value, BaseException):
            raise value
        return value

    def publish(self, window: Window, *, stamp: dict | None = None) -> str:
        version = f'v{len(self.tags)}'
        self.tags[version] = dict(coverage=stamp or dict(schema=COVERAGE, session=window.session, actor=window.actor,
                                                         last_step=window.last), restored_from=None)
        return version

    def session(self, reading: Reading, window: Window, label: str) -> Outcome:
        self.calls.append(window)
        if self.during:
            self.during(window)
        kind = self.outcomes.pop(0)
        if callable(kind):
            return kind(window)
        if kind == 'accepted':
            return Outcome('sealed', ({'operation': 'submission', 'status': 'published', 'version': self.publish(window)},),
                           session_id=label)
        if kind == 'nothing':
            return Outcome('sealed', (), session_id=label)
        if kind == 'rejected':
            return Outcome('sealed', ({'operation': 'submission', 'status': 'rejected', 'version': None},), session_id=label)
        if kind == 'aborted':
            return Outcome('aborted', (), session_id=label)
        if kind == 'refused':
            return Outcome(None, refused=True)
        if kind == 'interrupted':
            raise KeyboardInterrupt
        raise AssertionError(kind)

    def look(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self.tags.items()}

    def runner(self) -> Runner:
        return Runner(self.directory, RUN, snapshot=self.snapshot, session_call=self.session, look=self.look,
                      settings=self.settings, clock=self.clock, sleep=lambda seconds: None)


def status(world: World) -> dict:
    return json.loads((world.directory/'status.json').read_text())


@pytest.fixture
def world(tmp_path):
    return World(tmp_path/'runner')


# ---------------------------------------------------------------- the window
def test_a_window_waits_for_the_trigger_and_takes_at_most_the_ceiling():
    assert choose(read({'001': 19}), {}, SETTINGS) is None
    assert choose(read({'001': 20}), {}, SETTINGS) == Window(RUN, '001', 1, 20)
    assert choose(read({'001': 55}), {}, SETTINGS) == Window(RUN, '001', 1, 40)  # the oldest 40; the rest wait
    assert choose(read({'001': 55}), {'001': 40}, SETTINGS) is None  # 15 beyond the cursor: below the trigger
    assert choose(read({'001': 90}), {'001': 40}, SETTINGS) == Window(RUN, '001', 41, 80)


def test_an_ended_actors_tail_is_taken_however_few_and_an_empty_tail_is_skipped():
    handoff = read({'001': 45, '002': 30}, ended=('001',))
    assert choose(handoff, {'001': 40}, SETTINGS) == Window(RUN, '001', 41, 45)  # the tail first: admission order
    assert choose(read({'001': 130, '002': 30}, ended=('001',)), {'001': 40}, SETTINGS) == Window(RUN, '001', 41, 80)
    assert choose(handoff, {'001': 45}, SETTINGS) == Window(RUN, '002', 1, 30)  # the cursor moves to the next actor
    assert choose(read({'001': 40, '002': 3}, ended=('001',)), {'001': 40}, SETTINGS) is None  # empty tail skipped
    assert choose(read({'001': 0, '002': 25}, ended=('001',)), {}, SETTINGS) == Window(RUN, '002', 1, 25)
    assert choose(read({'001': 45, '002': 30}), {'001': 40}, SETTINGS) is None  # not ended: 001 holds the cursor


def test_the_covered_prefix_needs_an_unbroken_run_from_the_first_step():
    order = [('001', 50, True), ('002', 30, False)]
    assert covered(order, []) is None
    assert covered(order, [('001', 21, 40)]) is None  # a gap at the start
    assert covered(order, [('001', 1, 20), ('001', 1, 20), ('001', 21, 40)]) == ('001', 40)  # a retry overlaps
    assert covered(order, [('001', 1, 20), ('001', 41, 50), ('002', 1, 20)]) == ('001', 20)
    assert covered(order, [('001', 1, 50), ('002', 1, 20)]) == ('002', 20)  # across the handoff only once 001 is whole
    assert covered([('001', 50, False)] + order[1:], [('001', 1, 50), ('002', 1, 20)]) == ('001', 50)
    assert covered([('001', None, False)], [('001', 1, 20)]) == ('001', 20)  # no reading: no claim past one actor


# ---------------------------------------------------------------- the cursor
@pytest.mark.parametrize('ending, advances, failed', [('accepted', True, False), ('nothing', True, False),
                                                      ('rejected', True, True), ('aborted', False, True)])
def test_the_cursor_advances_on_a_closed_session_whatever_it_published(world, ending, advances, failed):
    world.reading = read({'001': 20})
    world.outcomes = [ending, 'nothing']
    runner = world.runner()
    assert runner.poll()
    assert world.calls == [Window(RUN, '001', 1, 20)]
    assert runner.cursor == ({'001': 20} if advances else {})
    assert runner.session_failures() == int(failed)
    named = dict(nothing='nothing-submitted').get(ending, ending)
    assert [e['outcome'] for e in status(world)['examined']] == [named]
    assert runner.poll()
    # An aborted session's range is taken again at the next poll; a closed one's is not.
    assert world.calls[1:] == ([] if advances else [Window(RUN, '001', 1, 20)])


def test_the_cursor_survives_a_restart_of_the_runner(world):
    world.reading = read({'001': 20})
    world.outcomes = ['rejected', 'accepted']
    world.runner().poll()
    restarted = world.runner()
    assert restarted.cursor == {'001': 20} and restarted.session_failures() == 1
    world.reading = read({'001': 45})  # the oldest 25 beyond the cursor: below the ceiling, all taken
    restarted.poll()
    assert world.calls == [Window(RUN, '001', 1, 20), Window(RUN, '001', 21, 45)]
    rows = [json.loads(line) for line in (world.directory/'examined.jsonl').read_text().splitlines()]
    assert [(r['event'], r['window']['first'], r.get('outcome')) for r in rows] == [
        ('start', 1, None), ('end', 1, 'rejected'), ('start', 21, None), ('end', 21, 'accepted')]
    assert rows[0]['first_operation'] == 'op-001-1' and rows[0]['last_operation'] == 'op-001-20'
    assert restarted.session_failures() == 0


def test_a_session_started_and_never_ended_reads_as_interrupted_after_a_restart(world):
    world.reading = read({'001': 25})
    world.outcomes = ['interrupted']
    with pytest.raises(KeyboardInterrupt):
        world.runner().poll()
    assert status(world)['state'] == 'ended' and status(world)['stop_reason'] == 'interrupted'
    # A start row whose end was never written (the runner was killed) reads the same way.
    rows = (world.directory/'examined.jsonl').read_text().splitlines()
    (world.directory/'examined.jsonl').write_text(rows[0] + '\n')
    restarted = world.runner()
    assert [e['outcome'] for e in restarted.examined()] == ['interrupted'] and restarted.cursor == {}


# ---------------------------------------------------------------- coverage
def test_accepted_then_rejected_leaves_the_prefix_at_the_accepted_window(world):
    world.outcomes = ['accepted', 'rejected']
    runner = world.runner()
    for steps in (20, 40, 50):
        world.reading = read({'001': steps})
        runner.poll()
    assert world.calls == [Window(RUN, '001', 1, 20), Window(RUN, '001', 21, 40)]
    now = status(world)
    end = now['covered_prefix']['end']
    assert (end['actor'], end['step'], end['operation'], end['ordinal']) == ('001', 20, 'op-001-20', 20)
    assert now['lag'] == 30 and now['backlog'] == 10 and now['cursor'] == {'001': 40}
    assert now['last_confirmed']['version'] == 'v1' and now['unconfirmed'] == []
    assert now['latest_version'] == dict(version='v1', coverage=dict(schema=COVERAGE, session=RUN, actor='001', last_step=20))
    assert now['stamp_distance'] == 30


def test_a_gap_stops_the_prefix_and_lag_is_counted_by_identity_across_a_handoff(world):
    world.outcomes = ['accepted', 'nothing', 'accepted']
    runner = world.runner()
    for steps, ended in ((20, ()), (40, ()), (60, ('001',))):
        world.reading = read({'001': steps}, ended=ended)
        runner.poll()
    world.reading = read({'001': 60, '002': 12}, ended=('001',))
    runner.poll()
    now = status(world)
    assert [e['window']['first'] for e in now['examined']] == [1, 21, 41]
    assert now['covered_prefix']['end']['step'] == 20 and now['lag'] == 72 - 20
    assert now['stamp_distance'] == 72 - 60  # the latest stamp is descriptive only
    assert now['position'] == dict(actor='002', step=12, operation='op-002-12', ordinal=72, read_wall=now['position']['read_wall'])


def test_a_retry_that_publishes_after_an_aborted_first_attempt_covers_the_range(world):
    world.reading = read({'001': 20})
    world.outcomes = ['aborted', 'accepted']
    runner = world.runner()
    runner.poll()
    assert status(world)['covered_prefix']['end'] is None and status(world)['lag'] == 20
    runner.poll()
    assert world.calls == [Window(RUN, '001', 1, 20)] * 2
    assert status(world)['covered_prefix']['end']['step'] == 20 and status(world)['lag'] == 0


def test_an_aborted_session_that_published_before_failing_still_covers_its_range(world):
    world.reading = read({'001': 20})

    def published_then_failed(window):
        return Outcome('aborted', ({'operation': 'submission', 'status': 'published', 'version': world.publish(window)},))

    world.outcomes = [published_then_failed]
    runner = world.runner()
    runner.poll()
    assert runner.cursor == {} and status(world)['covered_prefix']['end']['step'] == 20


@pytest.mark.parametrize('case', ['tag-never-seen', 'other-stamp', 'unknown-verdict', 'unclaimed-tag'])
def test_a_publication_that_cannot_be_confirmed_covers_nothing_and_is_recorded(world, case):
    world.reading = read({'001': 30})

    def claimed(window):
        if case == 'tag-never-seen':
            version = 'v7'
        elif case == 'other-stamp':
            version = world.publish(window, stamp=dict(schema=COVERAGE, session=RUN, actor='001', last_step=19))
        elif case == 'unknown-verdict':
            world.publish(window)
            return Outcome('sealed', ({'operation': 'submission', 'status': 'unknown', 'version': None},))
        else:
            world.publish(window)
            return Outcome('sealed', ())
        return Outcome('sealed', ({'operation': 'submission', 'status': 'published', 'version': version},))

    world.outcomes = [claimed]
    runner = world.runner()
    runner.poll()
    now = status(world)
    assert now['covered_prefix']['end'] is None and now['lag'] == 30 and now['last_confirmed'] is None
    assert len(now['unconfirmed']) >= 1
    reasons = {u['reason'] for u in now['unconfirmed']}
    assert reasons & {'its tag was not seen', 'its coverage stamp is not its window', 'the gate result is unknown',
                      'no examined session reports it'}


def test_a_restore_makes_the_prefix_unknown_from_the_restored_point(world):
    world.outcomes = ['accepted', 'accepted']
    runner = world.runner()
    for steps in (20, 40, 45):
        world.reading = read({'001': steps})
        runner.poll()
    assert status(world)['covered_prefix']['end']['step'] == 40
    world.tags['v3'] = dict(coverage=world.tags['v1']['coverage'], restored_from='v1')  # an operator's restore
    runner._look()
    runner.poll()
    now = status(world)
    assert now['covered_prefix']['end']['step'] == 20  # only v1's window counts past the restore
    assert now['covered_prefix']['restore'] == dict(version='v3', restored_from='v1', counted_through='v1')
    assert now['lag'] == 'unknown'


# ---------------------------------------------------------------- failure and the store's close
def test_two_consecutive_failed_sessions_stop_the_runner_for_the_rest_of_the_admission(world):
    world.reading = read({'001': 60})
    world.outcomes = ['rejected', 'aborted']
    runner = world.runner()
    assert runner.poll()
    assert not runner.poll()
    now = status(world)
    assert world.calls == [Window(RUN, '001', 1, 40), Window(RUN, '001', 41, 60)]
    assert now['state'] == 'stopped' and now['stop_reason'] == '2 consecutive failed sessions'
    assert now['unexamined'] == [dict(actor='001', first=41, last=60)]
    taken = world.snapshots
    assert not runner.poll() and world.snapshots == taken
    restarted = world.runner()
    assert restarted.run() == '2 consecutive failed sessions' and world.snapshots == taken


def test_a_success_between_failures_resets_the_count(world):
    world.reading = read({'001': 100})
    world.outcomes = ['rejected', 'accepted', 'rejected']
    runner = world.runner()
    assert runner.poll() and runner.poll() and runner.poll()
    assert runner.session_failures() == 1 and status(world)['state'] == 'polling'


def test_three_consecutive_failed_or_over_bound_snapshots_stop_the_runner_and_none_is_kept(world):
    good = read({'001': 3})
    world.reading = [SnapshotError('bad'), BoundExceeded('slow'), good, SnapshotError('bad'), BoundExceeded('slow'),
                     SnapshotError('bad')]
    runner = world.runner()
    outcomes = [runner.poll() for _ in range(6)]
    assert outcomes == [True, True, True, True, True, False]
    assert status(world)['stop_reason'] == '3 consecutive snapshots failed or passed their bound'
    polls = [json.loads(line)['outcome'] for line in (world.directory/'polls.jsonl').read_text().splitlines()]
    assert polls == ['failed', 'over-bound', 'read', 'failed', 'over-bound', 'failed']
    assert not any((world.directory/'snapshots').iterdir())


def test_a_lock_refusal_does_nothing_and_the_next_poll_computes_the_range_again(world):
    world.reading = read({'001': 20})
    world.outcomes = ['refused', 'accepted']
    runner = world.runner()
    assert runner.poll()
    assert runner.cursor == {} and runner.session_failures() == 0 and status(world)['examined'] == []
    assert runner.poll()
    assert world.calls == [Window(RUN, '001', 1, 20)] * 2 and runner.cursor == {'001': 20}


def test_a_refused_spend_reservation_stops_the_runner(world):
    world.reading = read({'001': 20})
    world.outcomes = [lambda window: Outcome('sealed', (), stop='spend-reservation-refused')]
    runner = world.runner()
    assert not runner.poll()
    now = status(world)
    assert now['state'] == 'stopped' and now['stop_reason'] == 'spend-reservation-refused'
    assert runner.cursor == {'001': 20}  # the session itself closed
    assert json.loads((world.directory/'stopped.json').read_text())['reason'] == 'spend-reservation-refused'


def test_no_store_waits_and_the_closing_marker_ends_every_read(world):
    world.reading = [ReadRefused('no-store', 'not yet'), read({'001': 5}), ReadRefused('closing', 'closing')]
    runner = world.runner()
    assert runner.poll() and status(world)['position'] == 'unknown'
    assert runner.poll() and status(world)['position']['operation'] == 'op-001-5'
    assert not runner.poll()
    assert not runner.poll() and world.snapshots == 3  # no read is opened once the store is closing
    now = status(world)
    assert now['state'] == 'ended' and now['stop_reason'] == 'store-closing'
    assert now['unexamined'] == [dict(actor='001', first=1, last=5)]


def test_an_interrupted_session_is_recorded_and_does_not_advance_the_cursor(world):
    world.reading = read({'001': 25})
    world.outcomes = ['interrupted']
    runner = world.runner()
    with pytest.raises(KeyboardInterrupt):
        runner.run()
    now = status(world)
    assert now['state'] == 'ended' and now['stop_reason'] == 'interrupted' and now['current'] is None
    assert [e['outcome'] for e in now['examined']] == ['interrupted'] and now['cursor'] == {}
    assert not any((world.directory/'snapshots').iterdir())


# ---------------------------------------------------------------- the publication watch and the status file
def test_each_version_records_its_last_look_without_the_tag_and_its_first_look_with_it(world):
    world.reading = read({'001': 20})
    looks = []
    real = world.look

    def look():
        began = world.clock.now  # the runner read its clock just before this call
        found = real()
        looks.append((began, set(found)))
        return found

    world.look = look
    world.outcomes = ['accepted', 'accepted']
    runner = world.runner()
    runner._look()  # the runner's first look, as `run` makes it: v0 is its baseline
    runner.poll()
    v0, v1 = runner.versions['v0'], runner.versions['v1']
    assert v0['baseline'] and v0['last_absent_began_wall'] == 'unknown'
    # Looks: the first, once before the session, once after it. v1 was published between the last two.
    assert [names for _, names in looks] == [{'v0'}, {'v0'}, {'v0', 'v1'}]
    assert v1['last_absent_began_wall'] == looks[1][0] and v1['first_present_ended_wall'] == looks[2][0] + 1
    assert not v1['baseline'] and v1['coverage']['last_step'] == 20


def test_while_a_session_runs_the_tags_are_looked_at_on_a_cadence(tmp_path):
    world = World(tmp_path/'runner', Settings(trigger_steps=20, ceiling_steps=40, poll_seconds=15, watch_seconds=.02))
    world.reading = read({'001': 20})
    seen_during = []

    def slow(window):
        version = world.publish(window)
        time.sleep(.3)
        seen_during.append('v1' in runner.versions)
        return Outcome('sealed', ({'operation': 'submission', 'status': 'published', 'version': version},))

    world.outcomes = [slow]
    runner = world.runner()
    runner.poll()
    assert seen_during == [True]  # the cadence saw it before the session returned
    lines = (world.directory/'versions.jsonl').read_text().splitlines()
    assert [json.loads(line)['version'] for line in lines] == ['v0', 'v1']


def test_the_status_file_at_a_sessions_start_and_end(world):
    world.reading = read({'001': 42})  # the window takes the oldest 40
    at_start = {}

    def capture(window):
        at_start.update(status(world))
        return Outcome('sealed', ({'operation': 'submission', 'status': 'published', 'version': world.publish(window)},),
                       session_id='curator-1')

    world.outcomes = [capture]
    runner = world.runner()
    runner.poll()
    assert at_start['schema'] == 'curator-runner-status/1' and at_start['state'] == 'in-session'
    assert at_start['current']['window'] == dict(session=RUN, actor='001', first=1, last=40)
    assert at_start['examined'][0]['outcome'] == 'in-session' and at_start['cursor'] == {}
    assert at_start['covered_prefix']['end'] is None and at_start['lag'] == 42 and at_start['backlog'] == 42
    assert at_start['position']['operation'] == 'op-001-42'
    assert at_start['snapshot']['hold_seconds'] == .01 and set(at_start['snapshot']['read_wall']) == {'began', 'ended'}
    assert at_start['settings'] == dict(trigger_steps=20, ceiling_steps=40, poll_seconds=15, watch_seconds=60)
    end = status(world)
    assert end['state'] == 'polling' and end['current'] is None and end['stop_reason'] is None
    assert end['examined'][0]['outcome'] == 'accepted' and end['examined'][0]['session_id'] == 'curator-1'
    assert end['cursor'] == {'001': 40} and end['lag'] == 2 and end['backlog'] == 2
    assert end['last_confirmed']['version'] == 'v1' and end['unexamined'] is None
    assert end['failures'] == dict(sessions=0, snapshots=0)


def test_the_tag_look_lists_each_version_of_a_real_repository_with_its_stamp(tmp_path):
    repo = Repository(tmp_path/'knowledge', 'testgame')
    repo.ensure()
    look = TagLook(repo)
    assert look() == {'v0': dict(coverage=None, restored_from=None)}


# ---------------------------------------------------------------- beside a growing trace, with a real session
native = pytest.mark.skipif(sys.platform != 'darwin' or not Path(sandbox.SANDBOX_EXEC).exists(),
                            reason='Seatbelt lane: macOS only')
PYTHON = Path(os.path.realpath(sys.executable))
SUBMIT = '''
import json, os
manifest = json.load(open('trace/manifest.json'))
frame = sorted(k[7:-4] for k in manifest['files'] if k.startswith('frames/'))[0]
version = open('brief.md').read().split('`')[1]
os.makedirs('submissions/s1')
json.dump(dict(schema='curator-submission/1', base_version=version, summary='first fact', from_drafts=[],
               changes=[dict(op='add_type', type=dict(schema='curator-type/1', name='container',
                                                    description='a place that holds items', fields=['holds'])),
                        dict(op='add_fact', fact=dict(schema='curator-fact/3', record='fact', id='f1', type='container',
                                                      text='the cupboard holds bottles', scope=dict(game='testgame'),
                                                      citations=[frame], subject='cupboard'))]),
          open('submissions/s1/submission.json', 'w'))
'''


@native
def test_beside_a_growing_trace_two_windows_are_examined_in_order_and_the_close_is_honoured(tmp_path):
    scripts = (tmp_path/'scripts').resolve()
    scripts.mkdir()
    (scripts/'submit.py').write_text(textwrap.dedent(SUBMIT))
    config = SessionConfig(argv=(str(PYTHON), '-I', str(scripts/'submit.py')),
                           tools=(Path(sys.base_prefix).resolve(), scripts), limits=sandbox.Limits(wall_seconds=60),
                           host=dict(name='scripted', script='submit'))
    repo = Repository(tmp_path/'knowledge', 'testgame')
    repo.ensure()

    def session(reading, window, label):
        try:
            record = run_session(repo, [reading.directory], config, window=window, session_id=label)
        except SessionError:
            return Outcome(None, refused=True)
        return Outcome(record['manifest']['lifecycle']['state'], tuple(record['verdicts']), session_id=label)

    reads = []
    snapshotter = live.staged(tmp_path/RUN)

    def snapshot(parent):
        reads.append(parent)
        return snapshotter(parent)

    with LiveWriter(tmp_path/RUN) as writer:
        runner = Runner(tmp_path/'runner', RUN, snapshot=snapshot, session_call=session, look=TagLook(repo),
                        settings=Settings(trigger_steps=4, ceiling_steps=6, poll_seconds=1, watch_seconds=.2))
        runner._look()
        assert runner.poll() and status_of(runner)['position']['ordinal'] == 0  # the store exists, with no actor yet
        writer(op='new_actor')
        for _ in range(3):
            writer(op='step')
        assert runner.poll() and runner.cursor == {}  # three finished steps: below the trigger
        for _ in range(4):
            writer(op='step')
        assert runner.poll()  # seven finished: the window takes the oldest six
        for _ in range(5):
            writer(op='step')
        assert runner.poll()  # six more beyond the cursor: the next window
        examined = status_of(runner)['examined']
        assert [(e['window']['first'], e['window']['last'], e['outcome']) for e in examined] == [
            (1, 6, 'accepted'), (7, 12, 'rejected')]  # the second repeats the fact id and the gate refuses it
        now = status_of(runner)
        assert now['covered_prefix']['end']['step'] == 6 and now['lag'] == 6
        assert now['last_confirmed']['version'] == 'v1' and repo.published() == 'v1'
        assert now['last_confirmed']['coverage'] == dict(schema=COVERAGE, session=RUN, actor='001', last_step=6)
        assert now['snapshot']['hold_seconds'] < 2 and now['position']['step'] == 12
        closed = writer(op='close')
        before = len(reads)
        assert not runner.poll()  # the marker exists: the read is refused and the runner ends
        assert not runner.poll() and len(reads) == before + 1
    assert closed['errors'] == {} and closed['wal'] == 0 and closed['busy'] == 0
    assert status_of(runner)['state'] == 'ended' and status_of(runner)['stop_reason'] == 'store-closing'
    with sealed(tmp_path/RUN/'session.sqlite3') as db:  # the store sealed after the runner's reads
        assert db.execute('SELECT count(*) FROM operations').fetchone() == (12,)
    assert not any((tmp_path/'runner'/'snapshots').iterdir())


def status_of(runner: Runner) -> dict:
    return json.loads((runner.directory/'status.json').read_text())


# ---------------------------------------------------------------- the process's own session call and configuration
def runner_config(tmp_path: Path, **values) -> Path:
    path = tmp_path/'runner.json'
    path.write_text(json.dumps(dict(dict(schema='curator-runner-config/1', knowledge_root=str(tmp_path/'runtime'/'knowledge'/'live'),
                                         arm='terra', cap_usd='1'), **values)))
    return path


@pytest.mark.parametrize('change, message', [
    (dict(schema='curator-runner-config/0'), 'not a curator-runner-config/1'),
    (dict(knowledge_root='data/knowledge'), 'knowledge_root must be inside'),
    (dict(arm='nobody'), 'unknown arm'), (dict(cap_usd=1), 'decimal string'), (dict(cap_usd='0'), 'positive'),
    (dict(upstream='http://example.com'), 'may only be OpenRouter'), (dict(trigger_steps=50), 'must not exceed'),
    (dict(host=dict(gpu=1)), 'host may have'), (dict(extra=1), 'may have')])
def test_the_runner_configuration_is_refused_before_anything_runs(tmp_path, change, message):
    with pytest.raises(live_runner.ConfigError, match=message):
        live_runner.read_config(runner_config(tmp_path, **change), tmp_path/'runtime')


def test_the_runner_configuration_takes_the_designs_defaults(tmp_path):
    config = live_runner.read_config(runner_config(tmp_path), tmp_path/'runtime')
    assert config['settings'] == Settings() and config['upstream'] == shadow.OPENROUTER_ORIGIN
    assert config['host']['max_requests'] == 120 and config['host']['effort'] is None and config['session_cap'] is None


INSTALLED = (shadow.HOST_DIR/'node_modules').is_dir() and shutil.which('node') is not None
native_host = pytest.mark.skipif(not INSTALLED or sys.platform != 'darwin' or not Path(sandbox.SANDBOX_EXEC).exists(),
                                 reason='Seatbelt lane: macOS with the curator host installed (npm ci in tools/curator_host)')


@native_host
def test_the_process_runs_windows_through_the_proxy_and_the_stand_in_and_reports_a_refused_lock(tmp_path):
    trace = make_long_session(tmp_path/'evidence', 'live', steps=12)
    reading = Reading(trace, (), 0., 0., 0.)
    with StandIn() as stand_in:
        config = live_runner.read_config(runner_config(tmp_path, upstream=stand_in.url, session_cap_usd='0.5',
                                                       host=dict(max_requests=10, max_output_tokens=4096, wall_seconds=120)),
                                         tmp_path/'runtime')
        repo = Repository(config['knowledge_root'], shadow.GAME)
        repo.ensure()
        sessions = live_runner.Sessions(tmp_path/'runner', config, repo, shadow.LOOPBACK_KEY)
        first = sessions(reading, Window('live', '001', 1, 4), 'first')
        second = sessions(reading, Window('live', '001', 5, 8), 'second')
        with (repo.state/'lock').open('w') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            third = sessions(reading, Window('live', '001', 9, 12), 'third')
    assert (first.state, [v['status'] for v in first.verdicts], first.stop) == ('sealed', ['published'], None)
    assert first.verdicts[0]['version'] == 'v1' and live.classify(first) == ('accepted', True, False)
    assert live.classify(second) == ('rejected', True, True)  # the stand-in repeats its fact id
    assert third.refused and third.state is None and live.classify(third) == ('lock-refused', False, False)
    summary = json.loads(Path(first.details['summary']).read_text())
    assert summary['window'] == dict(session='live', actor='001', first=1, last=4) and summary['cap_usd'] == '0.5'
    restarted = live_runner.Sessions(tmp_path/'runner', config, repo, shadow.LOOPBACK_KEY)
    assert restarted.spent == sessions.spent  # the spend already counted survives a restart
