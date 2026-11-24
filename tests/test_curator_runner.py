"""The curator runner's rules (#845), with its snapshot, session, tag look and clock injected; and one run
beside a synthetic growing trace with the real reader and a real session under the sandbox. No game, no provider.
"""
from __future__ import annotations

from decimal import Decimal
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
from harness.curator.gate import COVERAGE, current, gate, journal as gate_journal
from harness.curator.knowledge import Repository
from harness.curator.runner import ActorSteps, Outcome, Reading, Runner, Settings, TagLook, choose, covered
from harness.curator.session import SessionConfig, SessionError, run_session
from harness.curator.window import Window
from harness.trace.snapshot import BoundExceeded, ReadRefused, SnapshotError
from harness.trace.stores import CURATOR_READ_LOCK, sealed
from tests import curator_stand_in
from tests.curator_stand_in import StandIn
from tests.curator_trace import SESSION_ID, LiveWriter, _Writer, make_long_session, record_package
from tools.curator_host import groom, live_runner, shadow

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


@pytest.mark.parametrize('case, reason', [('tag-never-seen', 'its tag was not seen'),
                                          ('other-stamp', 'its coverage stamp is not its window'),
                                          ('unknown-verdict', 'the gate result is unknown'),
                                          ('unclaimed-tag', 'no examined session reports it')])
def test_a_publication_that_cannot_be_confirmed_covers_nothing_and_is_recorded(world, case, reason):
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
    expected = [reason] + (['no examined session reports it'] if case == 'unknown-verdict' else [])
    assert [u['reason'] for u in now['unconfirmed']] == expected  # an unknown verdict also leaves its tag unclaimed


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


def test_a_refused_spend_reservation_retries_the_oldest_uncovered_steps_after_restart(world):
    world.reading = read({'001': 20})
    world.outcomes = [lambda window: Outcome('sealed', (), stop=live.SPEND_REFUSED), 'accepted']
    runner = world.runner()
    assert runner.poll()
    now = status(world)
    assert now['state'] == 'polling' and now['stop_reason'] is None
    assert now['examined'][-1]['outcome'] == live.SPEND_REFUSED
    assert runner.cursor == {} and runner.session_failures() == 0
    runner = world.runner()
    assert runner.poll()
    assert world.calls == [Window(RUN, '001', 1, 20), Window(RUN, '001', 1, 10)]
    assert runner.cursor == {'001': 10}
    assert status(world)['covered_prefix']['end']['operation'] == 'op-001-10'


@pytest.mark.parametrize('refusal', [live.SPEND_REFUSED, live.SPEND_EXHAUSTED])
def test_a_refusal_at_one_step_and_an_exhausted_cap_have_distinct_terminal_reasons(world, refusal):
    world.reading = read({'001': 1}, ended=('001',))
    world.outcomes = [lambda window: Outcome(None, stop=refusal)]
    runner = world.runner()
    assert not runner.poll()
    assert runner.cursor == {}
    assert status(world)['stop_reason'] == refusal
    assert json.loads((world.directory/'stopped.json').read_text())['reason'] == refusal


def test_a_spend_refusal_keeps_an_already_published_window(world):
    world.reading = read({'001': 20})
    world.outcomes = [lambda window: Outcome('sealed', ({'operation': 'submission', 'status': 'published',
                                                       'version': world.publish(window)},),
                                             stop=live.SPEND_REFUSED)]
    runner = world.runner()
    assert runner.poll() and runner.cursor == {'001': 20}
    assert status(world)['covered_prefix']['end']['operation'] == 'op-001-20'


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


def test_a_final_status_says_what_it_is_as_of_and_that_later_steps_are_unknown(world):
    world.reading = read({'001': 5})

    def interrupted(seconds):
        raise KeyboardInterrupt  # the signal lands between polls, after the last read

    runner = Runner(world.directory, RUN, snapshot=world.snapshot, session_call=world.session, look=world.look,
                    settings=SETTINGS, clock=world.clock, sleep=interrupted)
    with pytest.raises(KeyboardInterrupt):
        runner.run()
    now = status(world)
    assert now['state'] == 'ended' and now['stop_reason'] == 'interrupted'
    assert now['as_of']['operation'] == 'op-001-5' and now['as_of']['ordinal'] == 5
    assert set(now['as_of']['read_wall']) == {'began', 'ended'}
    assert now['after_last_read'] == 'unknown'  # never presented as caught up
    assert now['unexamined'] == [dict(actor='001', first=1, last=5)] and now['lag'] == 5 and now['backlog'] == 5
    poll = json.loads((world.directory/'polls.jsonl').read_text().splitlines()[-1])
    assert poll['coverage']['as_of'] == now['as_of']


def test_the_custodians_receipt_ends_the_runner_without_another_read(world, tmp_path):
    run = tmp_path/RUN
    run.mkdir()
    world.reading = read({'001': 5})
    runner = Runner(world.directory, RUN, snapshot=world.snapshot, session_call=world.session, look=world.look,
                    settings=SETTINGS, clock=world.clock, sleep=lambda seconds: None, run=run)
    assert runner.poll() and world.snapshots == 1
    (run/'receipt.json').write_text('{}')  # a custodian that died wrote no closing marker
    assert not runner.poll() and not runner.poll() and world.snapshots == 1
    now = status(world)
    assert now['state'] == 'ended' and now['stop_reason'] == 'store-closed'
    assert json.loads((world.directory/'polls.jsonl').read_text().splitlines()[-1])['outcome'] == 'custodian-ended'


def test_a_host_that_cannot_be_resolved_is_its_own_outcome_and_stops_the_runner(world):
    world.reading = read({'001': 20})
    world.outcomes = [lambda window: Outcome(None, stop='host-unavailable: no node')]
    runner = world.runner()
    assert not runner.poll()
    rows = [json.loads(line) for line in (world.directory/'examined.jsonl').read_text().splitlines()]
    assert (rows[-1]['outcome'], rows[-1]['advanced'], rows[-1]['failed']) == ('host-unavailable', False, False)
    now = status(world)
    assert now['stop_reason'] == 'host-unavailable: no node' and now['examined'] == [] and now['cursor'] == {}


def test_an_unexpected_error_in_the_runner_is_recorded_as_a_stop_and_raised(world):
    world.reading = read({'001': 3})
    runner = world.runner()
    original = runner._append

    def failing(name, row):
        if name == 'polls.jsonl':
            raise OSError('disk full')
        original(name, row)

    runner._append = failing
    with pytest.raises(OSError):
        runner.run()
    now = status(world)
    assert now['state'] == 'stopped' and now['stop_reason'] == 'error: OSError'
    assert json.loads((world.directory/'stopped.json').read_text())['reason'] == 'error: OSError'
    assert not list(world.directory.glob('.*.partial'))


def test_a_row_cut_short_is_dropped_on_load_and_never_joined_to_the_next(world):
    world.reading = read({'001': 20})
    world.outcomes = ['accepted', 'accepted']
    world.runner().poll()
    whole = (world.directory/'examined.jsonl').read_bytes()
    for name in ('examined.jsonl', 'versions.jsonl', 'polls.jsonl'):
        with (world.directory/name).open('ab') as stream:
            stream.write(b'{"schema": "curator-runner-exa')  # a runner killed mid-write
    restarted = world.runner()
    assert (world.directory/'examined.jsonl').read_bytes() == whole
    assert all((world.directory/n).read_bytes().endswith(b'\n') for n in ('versions.jsonl', 'polls.jsonl'))
    world.reading = read({'001': 40})
    restarted.poll()  # appends after the cut
    again = world.runner()  # the second restart reads every row
    assert [e['outcome'] for e in again.examined()] == ['accepted', 'accepted'] and again.cursor == {'001': 40}


def test_each_poll_and_each_session_row_carries_the_coverage_at_that_moment(world):
    world.outcomes = ['accepted', 'rejected']
    runner = world.runner()
    for steps in (20, 40, 45):
        world.reading = read({'001': steps})
        runner.poll()
    rows = [json.loads(line) for line in (world.directory/'examined.jsonl').read_text().splitlines()]
    ends = [(r['event'], r['coverage']['covered_prefix']['end'] and r['coverage']['covered_prefix']['end']['step'],
             r['coverage']['lag'], r['coverage']['backlog']) for r in rows]
    assert ends == [('start', None, 20, 20), ('end', 20, 0, 0), ('start', 20, 20, 20), ('end', 20, 20, 0)]
    polls = [json.loads(line)['coverage'] for line in (world.directory/'polls.jsonl').read_text().splitlines()]
    assert [(p['lag'], p['backlog']) for p in polls] == [(20, 20), (20, 20), (25, 5)]


def test_the_prefix_end_is_placed_by_its_operations_identity(world):
    world.reading = read({'001': 20})
    world.outcomes = ['accepted']
    runner = world.runner()
    runner.poll()
    assert status(world)['covered_prefix']['end']['operation'] == 'op-001-20'
    # A later snapshot that no longer holds that operation at all: its place, and so lag, is unknown.
    world.reading = Reading(Path('/snapshots')/RUN, (ActorSteps('001', tuple(f'other-{n}' for n in range(1, 25)), False),),
                            .01, .005, .05)
    runner.poll()
    now = status(world)
    assert now['covered_prefix']['end'] == dict(actor='001', step=20, operation='op-001-20', ordinal='unknown')
    assert now['lag'] == 'unknown'


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


def test_three_runner_windows_publish_when_the_first_two_share_a_frame(tmp_path, monkeypatch):
    repo = Repository(tmp_path/'knowledge', 'testgame')
    repo.ensure()
    config = SessionConfig(argv=('scripted',), host=dict(name='scripted'))

    def submit(_argv, layout, **_kwargs):
        workspace = layout.workspace
        base = (workspace/'brief.md').read_text().split('`')[1]
        step = json.loads((workspace/'trace'/RUN/'001'/'steps.jsonl').read_text())
        changes = []
        if base == 'v0':
            changes.append(dict(op='add_type', type=dict(schema='curator-type/2', name='container',
                                                        description='a place that holds items', fields=['holds'], identity=[], reason='Describe a container')))
        changes.append(dict(op='add_fact', fact=dict(schema='curator-fact/4', record='fact', id=f'f{step["seq"]}',
                                                     type='container', text='the cupboard holds bottles', known='observed',
                                                     scope=dict(game=repo.game, level='game'), citations=[step['frame']])))
        directory = workspace/'submissions'/'s1'
        directory.mkdir()
        (directory/'submission.json').write_text(json.dumps(dict(schema='curator-submission/1', base_version=base,
                                                                 summary='window fact', changes=changes)))
        return sandbox.Result(0, None, 0, 0, 0., [])

    def session(reading, window, label):
        result = run_session(repo, [reading.directory], config, window=window, session_id=label)
        return Outcome(result['manifest']['lifecycle']['state'], tuple(result['verdicts']), session_id=label)

    monkeypatch.setattr(sandbox, 'run', submit)
    run = tmp_path/RUN
    run.mkdir()
    (run/CURATOR_READ_LOCK).touch()
    record_package(run, labels=dict(world=None, lineage=None, admission=None))
    runner = Runner(tmp_path/'runner', RUN, snapshot=live.staged(run), session_call=session, look=TagLook(repo),
                    settings=Settings(trigger_steps=1, ceiling_steps=1))
    writer = _Writer(run, SESSION_ID)
    try:
        writer.new_actor()
        shared = writer.frame()
        with monkeypatch.context() as reuse:
            reuse.setattr(writer, 'frame', lambda: shared)
            for _ in range(2):
                writer.step()
                assert runner.poll()
        writer.step()
        assert runner.poll()
    finally:
        writer.close()

    verdicts = gate_journal(repo)
    assert [(v['status'], v['version'], v['diagnostics']) for v in verdicts] == [
        ('published', 'v1', []), ('published', 'v2', []), ('published', 'v3', [])]
    now = status_of(runner)
    assert [e['outcome'] for e in now['examined']] == ['accepted', 'accepted', 'accepted']
    assert now['covered_prefix']['end']['step'] == 3 and now['lag'] == 0
    frame = shared[0]['source_id']
    recorded = dict(session=RUN, actor='001', step=1, order=[1, '001', 1])
    assert repo.provenance()['frames'][frame] == recorded
    first, second, third = repo.facts()
    assert first['citations'] == second['citations'] == [frame]
    assert first['seen'] == second['seen'] == recorded and third['seen']['step'] == 3


# ---------------------------------------------------------------- versions left for the driver (#838)
def test_each_confirmed_version_is_left_whole_for_the_driver_and_a_failed_export_is_tried_again(tmp_path, monkeypatch, capsys):
    """R-REGRESSION: the runner's part of live delivery, over a real repository and gate. Each version the runner
    confirms is exported for the package's world as `delivered-knowledge/2` under `delivered/`; a failed export is
    reported once and tried again at the next poll; a restarted runner exports nothing it already left."""
    from harness.curator.knowledge import _git
    from harness.player.knowledge import Knowledge
    from tools import knowledge_export
    repo = Repository(tmp_path/'knowledge', 'testgame')
    repo.ensure()
    config = SessionConfig(argv=('scripted',), host=dict(name='scripted'))

    def submit(_argv, layout, **_kwargs):
        workspace = layout.workspace
        base = (workspace/'brief.md').read_text().split('`')[1]
        step = json.loads((workspace/'trace'/RUN/'001'/'steps.jsonl').read_text())
        changes = []
        if base == 'v0':
            changes.append(dict(op='add_type', type=dict(schema='curator-type/2', name='container',
                                                        description='a place that holds items', fields=['holds'], identity=[], reason='Describe a container')))
        # One fact of the game and one of the run's world (the gate stamps the world from the cited session),
        # which only an export for that world selects.
        for identity, scope in ((f'f{step["seq"]}', dict(game=repo.game, level='game')),
                                (f'w{step["seq"]}', dict(game=repo.game, level='world'))):
            changes.append(dict(op='add_fact', fact=dict(schema='curator-fact/4', record='fact', id=identity, type='container',
                                                         text=f'the cupboard {identity} holds bottles', known='observed',
                                                         scope=scope, citations=[step['frame']])))
        directory = workspace/'submissions'/'s1'
        directory.mkdir()
        (directory/'submission.json').write_text(json.dumps(dict(schema='curator-submission/1', base_version=base,
                                                                 summary='window fact', changes=changes)))
        return sandbox.Result(0, None, 0, 0, 0., [])

    def session(reading, window, label):
        result = run_session(repo, [reading.directory], config, window=window, session_id=label)
        return Outcome(result['manifest']['lifecycle']['state'], tuple(result['verdicts']), session_id=label)

    monkeypatch.setattr(sandbox, 'run', submit)
    run = tmp_path/RUN
    run.mkdir()
    (run/CURATOR_READ_LOCK).touch()
    record_package(run, labels=dict(world='the farm', lineage=None, admission=None), live=True)
    enabled, world, session_id = live_runner.delivery_world(run)
    assert (enabled, world, session_id) == (True, 'the farm', SESSION_ID)
    delivered = tmp_path/'runner'/'delivered'
    prefix = delivered/live_runner.COVERED_PREFIX_FILE

    def runner():
        return live_runner.DeliveringRunner(
            tmp_path/'runner', RUN, snapshot=live.staged(run), session_call=session, look=TagLook(repo),
            settings=Settings(trigger_steps=1, ceiling_steps=1),
            deliver=live_runner.Delivery(tmp_path/'runner', repo.path, world, session=session_id))

    first = runner()
    assert first.deliver.last == -1 and not delivered.exists()  # the repository's baseline v0 is never left
    writer = _Writer(run, SESSION_ID)
    try:
        writer.new_actor()
        operation = writer.step()['operation_id']
        assert first.poll()
        value = json.loads((delivered/'v1.json').read_text())
        assert value == knowledge_export.published(repo.path, 'v1', world='the farm') and Knowledge.from_dict(value).value == value
        root = _git(repo.path, 'rev-parse', 'v0^{commit}').decode().strip()
        assert (value['schema'], value['version'], value['repository_id']) == ('delivered-knowledge/2', 'v1', root)
        assert value['commit'] == _git(repo.path, 'rev-parse', 'v1^{commit}').decode().strip() != root
        # The facts are those of the package's world; the label itself is never written into the file.
        assert [f['id'] for f in value['facts']] == ['f1', 'w1'] and value['coverage']['last_step'] == 1
        assert [f['id'] for f in knowledge_export.published(repo.path, 'v1')['facts']] == ['f1'] and 'the farm' not in json.dumps(value)
        first_prefix = dict(schema='curator-covered-prefix/1', session=SESSION_ID, actor='001',
                            actor_id=writer.actor['id'], operation_id=operation, version='v1', restored=False)
        assert json.loads(prefix.read_text()) == first_prefix
        # An export that fails leaves nothing, says so once, and the next poll leaves the version.
        published = knowledge_export.published
        calls = []

        def failing(path, version, *, world):
            calls.append(version)
            raise OSError('disk refused the export')

        monkeypatch.setattr(knowledge_export, 'published', failing)
        operation = writer.step()['operation_id']
        assert first.poll() and first.poll()
        assert calls == ['v2', 'v2'] and sorted(p.name for p in delivered.glob('v*.json')) == ['v1.json']
        assert json.loads(prefix.read_text()) == first_prefix
        assert capsys.readouterr().err.splitlines() == ['curator_runner: delivery of v2 failed: OSError: disk refused the export']
        monkeypatch.setattr(knowledge_export, 'published', published)
        assert first.poll()
        assert sorted(p.name for p in delivered.glob('v*.json')) == ['v1.json', 'v2.json']
        assert json.loads(prefix.read_text()) == dict(first_prefix, operation_id=operation, version='v2')
        assert sorted(f['id'] for f in json.loads((delivered/'v2.json').read_text())['facts']) == ['f1', 'f2', 'w1', 'w2']
        # A restarted runner starts from what is already left.
        second = runner()
        assert second.deliver.last == 2
        before = {p.name: p.stat().st_mtime_ns for p in delivered.glob('v*.json')}
        assert second.poll() and {p.name: p.stat().st_mtime_ns for p in delivered.glob('v*.json')} == before
        writer.step()
        assert second.poll() and sorted(p.name for p in delivered.glob('v*.json')) == ['v1.json', 'v2.json', 'v3.json']
    finally:
        writer.close()
    assert capsys.readouterr().err == ''


def test_only_a_confirmed_publication_that_is_not_a_restore_is_left_for_the_driver(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tools import knowledge_export
    exported = []
    monkeypatch.setattr(knowledge_export, 'published',
                        lambda path, version, *, world: exported.append((version, world)) or dict(version=version))
    deliver = live_runner.Delivery(tmp_path, tmp_path/'repository', 'farm')
    versions = {'v1': dict(restored_from=None), 'v2': dict(restored_from='v1'), 'v3': dict(restored_from=live.UNKNOWN),
                'v4': dict(restored_from=None)}
    state = SimpleNamespace(versions=versions, lock=threading.RLock(),
                            publications=lambda: ([], [dict(version='v4')], None))
    deliver(state)  # v4's tag was seen but no examined session confirms it
    assert exported == [] and not (tmp_path/'delivered').exists()
    state.publications = lambda: ([dict(version=v) for v in ('v1', 'v2', 'v3')], [], dict(version='v2'))
    deliver(state)  # v2 and v3 are restores, or may be: only v1 is left
    assert exported == [('v1', 'farm')] and [p.name for p in (tmp_path/'delivered').iterdir()] == ['v1.json']
    deliver(state)
    assert exported == [('v1', 'farm')]  # nothing above the last version left


@pytest.mark.parametrize('gap', ['rejected', 'nothing'])
def test_delivery_leaves_the_prefix_before_a_gap_until_a_restore_invalidates_it(tmp_path, monkeypatch, gap):
    world = World(tmp_path/'runner', Settings(trigger_steps=1, ceiling_steps=1))
    world.outcomes = ['accepted', gap, 'accepted']
    monkeypatch.setattr(live_runner.knowledge_export, 'published',
                        lambda path, version, *, world: dict(version=version))
    runner = world.runner()
    deliver = live_runner.Delivery(world.directory, tmp_path/'repository', None, session=SESSION_ID)
    delivered = world.directory/'delivered'
    prefix = delivered/live_runner.COVERED_PREFIX_FILE
    actor_id = 'b' * 32
    operations = ('1' * 32, '2' * 32, '3' * 32)
    expected = dict(schema='curator-covered-prefix/1', session=SESSION_ID, actor='001', actor_id=actor_id,
                    operation_id=operations[0], version='v1', restored=False)
    for step in range(1, 4):
        world.reading = Reading(Path('/snapshots')/RUN, (ActorSteps('001', operations[:step], False, actor_id),), 0, 0, 0)
        assert runner.poll()
        deliver(runner)
        assert json.loads(prefix.read_text()) == expected
    assert (delivered/'v2.json').is_file()  # the publication after the gap still reaches the driver
    world.tags['v3'] = dict(coverage=world.tags['v1']['coverage'], restored_from='v1')
    runner._look()
    assert runner.poll()
    deliver(runner)
    assert json.loads(prefix.read_text()) == dict(schema='curator-covered-prefix/1', session=SESSION_ID,
                                                  actor=None, actor_id=None, operation_id=None, version=None, restored=True)
    assert not (delivered/'v3.json').exists()


def test_delivery_is_read_from_the_current_package_manifest(tmp_path):
    run = tmp_path/RUN
    run.mkdir()
    record_package(run, labels=dict(world='the farm', lineage='L1', admission=1))
    assert live_runner.delivery_world(run) == (False, 'the farm', SESSION_ID)
    record_package(run, labels=dict(lineage='L1', admission=1), schema='campaign-run/10')
    with pytest.raises(ValueError, match='not a campaign-run/12 manifest'):
        live_runner.delivery_world(run)
    (run/'manifest.json').unlink()
    with pytest.raises(OSError):
        live_runner.delivery_world(run)


def test_delivery_is_never_enabled_from_a_manifest_the_supervisor_did_not_launch(tmp_path):
    """R-REGRESSION (B4): replaced manifest bytes, whose SHA-256 differs from the supervisor's launch record,
    neither enable delivery nor choose its world; nor does a launch record of another session or schema."""
    import hashlib
    run = tmp_path/RUN
    run.mkdir()
    record_package(run, labels=dict(world='the farm', lineage=None, admission=None), live=True)
    assert live_runner.delivery_world(run) == (True, 'the farm', SESSION_ID)
    assert live_runner.delivery_world(run, session_id=SESSION_ID) == (True, 'the farm', SESSION_ID)
    with pytest.raises(ValueError, match='launched session'):
        live_runner.delivery_world(run, session_id='b' * 32)
    original = (run/'manifest.json').read_bytes()
    replaced = json.loads(original)
    replaced['labels']['world'] = 'another farm'
    (run/'manifest.json').write_text(json.dumps(replaced))
    with pytest.raises(ValueError, match='SHA-256 differs from the supervisor launch record'):
        live_runner.delivery_world(run)
    # Missing session in both manifest and watch-start (even with matching SHA-256) is refused.
    no_session = json.loads(original)
    no_session.pop('session')
    no_session_bytes = json.dumps(no_session).encode()
    (run/'manifest.json').write_bytes(no_session_bytes)
    opening = json.loads((run/'watch-start.json').read_text())
    no_session_opening = {k: v for k, v in opening.items() if k != 'session'}
    no_session_opening['manifest_sha256'] = hashlib.sha256(no_session_bytes).hexdigest()
    (run/'watch-start.json').write_text(json.dumps(no_session_opening))
    with pytest.raises(ValueError, match='missing or invalid session'):
        live_runner.delivery_world(run)
    (run/'manifest.json').write_bytes(original)
    (run/'watch-start.json').write_text(json.dumps(opening))
    for change, message in ((dict(session='b' * 32), 'session differs'), (dict(schema='campaign-watch-start/3'), 'unsupported')):
        (run/'watch-start.json').write_text(json.dumps(dict(opening, **change)))
        with pytest.raises(ValueError, match=message):
            live_runner.delivery_world(run)
    (run/'watch-start.json').unlink()
    with pytest.raises(OSError):
        live_runner.delivery_world(run)


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
               changes=[dict(op='add_type', type=dict(schema='curator-type/2', name='container',
                                                    description='a place that holds items', fields=['holds'], identity=[], reason='Describe a container')),
                        dict(op='add_fact', fact=dict(schema='curator-fact/4', record='fact', id='f1', type='container',
                                                      text='the cupboard holds bottles', known='observed', scope=dict(game='testgame', level='game'),
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


def fake_sessions(tmp_path: Path, monkeypatch, behave) -> live_runner.Sessions:
    """The process's session call with `shadow.run_one` replaced by `behave(session_dir, kwargs)`; no host runs."""
    config = live_runner.read_config(runner_config(tmp_path, cap_usd='1'), tmp_path/'runtime')
    repo = Repository(config['knowledge_root'], shadow.GAME)

    def run_one(**kwargs):
        directory = kwargs['out']/kwargs['lineage']/kwargs['name']
        directory.mkdir(parents=True)
        return behave(directory, kwargs)

    monkeypatch.setattr(shadow, 'run_one', run_one)
    sessions = live_runner.Sessions(tmp_path/'runner', config, repo, shadow.LOOPBACK_KEY)
    sessions.tools = {}  # as if the host tools were resolved
    return sessions


def summary(directory: Path, *, survivors=(), state='sealed', host_output=b'', **change) -> dict:
    record = directory/'record'
    record.mkdir()
    (record/'host-output.log').write_bytes(host_output)
    value = dict(cost_usd='0.1', proxy=dict(revoked=False, breaches=0, settled=True), stopped_by_cap=False,
                 run_state='completed', session_id='s', session_state=state, verdicts=[], record=str(record),
                 sandbox=dict(survivors=None if survivors is None else list(survivors)))
    value.update(change)
    return value


def closed(directory: Path, spent: str, pending: str = '0') -> None:
    (directory/'proxy-close.json').write_text(json.dumps(dict(schema='curator-proxy-close/1', spent_snapshot_usd=spent,
                                                              pending_reserved_usd=pending)))


def test_spend_is_counted_from_what_the_proxy_left_even_for_a_session_cut_short(tmp_path, monkeypatch):
    caps = []

    def behave(directory, kwargs):
        caps.append(kwargs['cap'])
        if len(caps) == 1:
            closed(directory, '0.3', '0.05')  # the proxy closed in run_one's finally; then the interruption
            raise KeyboardInterrupt
        if len(caps) == 2:  # the proxy's close raised: only its ledger is left
            (directory/'proxy-ledger.jsonl').write_text(json.dumps(dict(reserved='0.2', charged='0.15')) + '\n')
            raise RuntimeError('proxy shutdown failed')
        closed(directory, '0.1')
        return summary(directory)

    sessions = fake_sessions(tmp_path, monkeypatch, behave)
    reading = Reading(tmp_path/RUN, (), 0., 0., 0.)
    with pytest.raises(KeyboardInterrupt):
        sessions(reading, Window(RUN, '001', 1, 20), 'first')
    assert sessions.spent == Decimal('0.35')  # spent and still reserved
    restarted = fake_sessions(tmp_path, monkeypatch, behave)
    assert restarted.spent == Decimal('0.35')
    with pytest.raises(RuntimeError):
        restarted(reading, Window(RUN, '001', 1, 20), 'second')
    assert restarted.spent == Decimal('0.50') and caps[1] == Decimal('0.65')
    restarted(reading, Window(RUN, '001', 1, 20), 'third')
    assert caps[2] == Decimal('0.50') and restarted.spent == Decimal('0.60')


def test_an_unclosed_session_holds_its_cap_across_runner_restart(tmp_path, monkeypatch):
    def interrupted(directory, kwargs):
        (directory/'proxy-start.json').write_text(json.dumps(dict(cap_usd=str(kwargs['cap']))))
        raise KeyboardInterrupt

    sessions = fake_sessions(tmp_path, monkeypatch, interrupted)
    reading = Reading(tmp_path/RUN, (), 0., 0., 0.)
    window = Window(RUN, '001', 1, 20)
    with pytest.raises(KeyboardInterrupt):
        sessions(reading, window, 'killed')
    restarted = fake_sessions(tmp_path, monkeypatch, interrupted)
    assert restarted.spent == Decimal(1)
    assert restarted(reading, window, 'no-budget').stop == live.SPEND_EXHAUSTED


@pytest.mark.parametrize('spent,stop', [('0.75', live.SPEND_REFUSED), ('1', live.SPEND_EXHAUSTED)])
def test_live_spend_refusal_distinguishes_remaining_headroom(tmp_path, monkeypatch, spent, stop):
    def behave(directory, kwargs):
        closed(directory, spent)
        return summary(directory, stopped_by_cap=True)

    outcome = fake_sessions(tmp_path, monkeypatch, behave)(Reading(tmp_path/RUN, (), 0., 0., 0.),
                                                           Window(RUN, '001', 1, 20), 'one')
    assert outcome.stop == stop


@pytest.mark.parametrize('survivors, host_output, stops', [
    (None, b'', False),  # aborted before its host ran: an ordinary failed session
    (None, b'{"type":"host-start"}\n', True),  # the host ran and the sandbox's result is missing
    ((), b'{"type":"host-start"}\n', False), (('4242',), b'', True)])
def test_cleanup_stops_the_runner_only_when_a_host_may_have_survived(tmp_path, monkeypatch, survivors, host_output, stops):
    def behave(directory, kwargs):
        closed(directory, '0')
        return summary(directory, survivors=survivors, host_output=host_output,
                       state='aborted' if survivors is None else 'sealed')

    outcome = fake_sessions(tmp_path, monkeypatch, behave)(Reading(tmp_path/RUN, (), 0., 0., 0.),
                                                           Window(RUN, '001', 1, 20), 'one')
    assert outcome.stop == ('cleanup-unconfirmed' if stops else None)
    if survivors is None and not stops:
        assert live.classify(outcome) == ('aborted', False, True)


def test_a_host_that_cannot_be_resolved_is_reported_by_the_process(tmp_path, monkeypatch):
    sessions = fake_sessions(tmp_path, monkeypatch, lambda directory, kwargs: pytest.fail('no session without a host'))
    sessions.tools = None

    def missing():
        raise shadow.ShadowError('Node.js is required for the curator host')

    monkeypatch.setattr(shadow, 'host_tools', missing)
    outcome = sessions(Reading(tmp_path/RUN, (), 0., 0., 0.), Window(RUN, '001', 1, 20), 'one')
    assert outcome.stop.startswith('host-unavailable: ') and live.classify(outcome) == ('host-unavailable', False, False)


def grooming_args(run: Path, config: Path, runtime: Path, out: Path) -> list[str]:
    return ['--run', str(run), '--config', str(config), '--runtime-root', str(runtime), '--out', str(out)]


@pytest.fixture
def grooming_run(tmp_path, monkeypatch):
    runtime = tmp_path/'runtime'
    run = make_long_session(tmp_path/'runs', 'live-admission', steps=1, actors=('001',))
    config = runner_config(tmp_path, upstream='http://127.0.0.1:1')
    repo = Repository(runtime/'knowledge'/'live', shadow.GAME)
    out = runtime/'grooming'

    def unexpected(*args, **kwargs):
        pytest.fail('grooming preflight must not resolve credentials or host tools, or start a session')

    for name in ('route_key', 'host_tools', 'run_one'):
        monkeypatch.setattr(shadow, name, unexpected)
    return repo, run, out, grooming_args(run, config, runtime, out)


def publish_admission(repo: Repository, submission: Path, name: str) -> None:
    repo.ensure()
    submission.mkdir()
    kind = dict(schema='curator-type/2', name='control', description='what an input does',
                fields=[], identity=[], reason='Describe a control')
    (submission/'submission.json').write_text(json.dumps(dict(
        schema='curator-submission/1', base_version='v0', summary='admission type',
        changes=[dict(op='add_type', type=kind)])))
    verdict = gate(repo, submission, session_id='admission', window_frames={}, session_kind='admission',
                   coverage=dict(schema=COVERAGE, session=name, actor='001', last_step=1))
    assert verdict['status'] == 'published', verdict


def test_boundary_grooming_skips_a_repository_without_a_published_admission(grooming_run, capsys):
    repo, run, out, args = grooming_run
    assert repo.ensure() == 'v0'
    assert groom.main(args) == 0
    result = json.loads((out/'grooming-summary.json').read_text())
    assert result == dict(schema='curator-boundary-grooming/1', status='skipped', reason='no-published-admission',
                          run=run.name, knowledge_root=str(repo.path.parent), published_before='v0', published_after='v0',
                          cost_usd='0', summary=None)
    assert 'skipped' in capsys.readouterr().out


@pytest.mark.parametrize('case, message', [
    ('mismatch', 'other-admission'), ('missing-repo', 'existing knowledge repository'),
    ('journal', 'unsupported active gate journal'), ('out-exists', 'fresh output directory'),
    ('out-outside', '--out must be inside'), ('out-in-run', '--out must be outside --run'),
    ('out-in-repo', 'outside the knowledge worktree'),
    ('cap-zero', '--cap-usd must be positive'), ('cap-negative', '--cap-usd must be positive'),
    ('missing-store', 'missing store'), ('wal', 'un-checkpointed write-ahead log'),
    ('unreadable-store', 'file is not a database'),
])
def test_boundary_grooming_refuses_invalid_inputs_before_resolving_the_host(grooming_run, tmp_path, capsys, case, message):
    repo, run, out, args = grooming_run
    db = run/'session.sqlite3'
    if case == 'mismatch':
        publish_admission(repo, tmp_path/'submission', 'other-admission')
    elif case != 'missing-repo':
        repo.ensure()
    if case == 'journal':
        repo.state.mkdir()
        (repo.state/'gate.jsonl').write_text('{}\n')
    elif case == 'out-exists':
        out.mkdir()
    elif case == 'out-outside':
        out = tmp_path/'outside'
        args[-1] = str(out)
    elif case == 'out-in-run':
        runtime_run = make_long_session(out.parent/'runs', 'live-admission', steps=1, actors=('001',))
        args[1] = str(runtime_run)
        out = runtime_run/'grooming'
        args[-1] = str(out)
    elif case == 'out-in-repo':
        out = repo.path/'grooming'
        args[-1] = str(out)
    elif case in ('cap-zero', 'cap-negative'):
        args.extend(['--cap-usd', '0' if case == 'cap-zero' else '-1'])
    elif case == 'missing-store':
        db.unlink()
    elif case == 'wal':
        db.with_name('session.sqlite3-wal').write_bytes(b'uncheckpointed')
    elif case == 'unreadable-store':
        db.write_bytes(b'not a SQLite database')
    assert groom.main(args) == 2
    assert message in capsys.readouterr().err
    assert not (out/'grooming-summary.json').exists()
    if case == 'missing-repo':
        assert not repo.path.exists()


@pytest.mark.parametrize('changes, reason', [
    ({}, None),
    (dict(unresolved=True, verdicts=[dict(operation='submission', status='unknown')], published_after=None), 'unresolved-result'),
    (dict(stopped_by_cap=True), 'cap-reached'),
    (dict(stopped_by_cap=True, proxy=dict(settled=True, revoked=True, breaches=0)), 'proxy-revoked-or-breached'),
    (dict(proxy=dict(settled=False, revoked=False, breaches=0)), 'proxy-unsettled'),
    (dict(proxy=dict(settled=True, revoked=True, breaches=0)), 'proxy-revoked-or-breached'),
    (dict(proxy=dict(settled=True, revoked=False, breaches=1)), 'proxy-revoked-or-breached'),
    (dict(session_state='aborted'), 'session-not-sealed'),
    (dict(sandbox=dict(survivors=[42])), 'cleanup-unconfirmed'),
    (dict(run_state='error: test failure'), 'error: test failure'),
])
def test_boundary_grooming_freezes_the_session_and_reports_its_outcome(grooming_run, tmp_path, monkeypatch, changes, reason):
    repo, run, out, args = grooming_run
    publish_admission(repo, tmp_path/'submission', run.name)
    host = dict(test_host=True)
    monkeypatch.setattr(shadow, 'host_tools', lambda: host)

    def route_key(upstream, runtime):
        assert upstream == 'http://127.0.0.1:1' and runtime == out.parent
        return shadow.LOOPBACK_KEY

    monkeypatch.setattr(shadow, 'route_key', route_key)
    verdicts = [dict(operation='submission', status='rejected', diagnostics=['test verdict'])]
    session = dict(dict(run_state='completed', session_state='sealed', verdicts=verdicts, published_after='v1',
                        proxy=dict(settled=True, revoked=False, breaches=0), sandbox=dict(survivors=[]), cost_usd='0.07'),
                   **changes)
    relative = f'boundary/groom-{run.name}/summary.json'

    def run_one(**kwargs):
        assert kwargs['arm_name'] == 'terra' and kwargs['host'] is host and kwargs['key'] == shadow.LOOPBACK_KEY
        assert kwargs['trace'] == run and kwargs['repo'].path == repo.path and kwargs['memory'] is None
        assert kwargs['window'] == Window() and kwargs['session_kind'] == 'grooming'
        assert kwargs['cap'] == Decimal('0.25') and kwargs['model_config']['budget_usd'] == 0.25
        assert kwargs['config_path'].parent == out/'host-config' == kwargs['config_dir']
        assert json.loads(kwargs['config_path'].read_text()) == kwargs['model_config']
        assert kwargs['model_config']['wall_seconds'] == kwargs['wall_seconds'] - 30
        assert kwargs['model_config']['model']['maxTokens'] == kwargs['max_output_tokens']
        assert kwargs['out']/kwargs['lineage']/kwargs['name']/'summary.json' == out/relative
        shadow._write(out/relative, session)
        return session

    monkeypatch.setattr(shadow, 'run_one', run_one)
    assert groom.main([*args, '--cap-usd', '0.25']) == (0 if reason is None else 1)
    result = json.loads((out/'grooming-summary.json').read_text())
    assert result == dict(schema='curator-boundary-grooming/1', status='completed' if reason is None else 'failed',
                          reason=reason, run=run.name, knowledge_root=str(repo.path.parent), cap_usd='0.25',
                          published_before='v1', published_after=session['published_after'], cost_usd='0.07',
                          verdicts=session['verdicts'], session_state=session['session_state'], proxy=session['proxy'],
                          sandbox=session['sandbox'], summary=relative)


def test_boundary_grooming_writes_summary_if_published_lookup_fails_after_session_error(grooming_run, tmp_path, monkeypatch):
    repo, run, out, args = grooming_run
    publish_admission(repo, tmp_path/'submission', run.name)
    monkeypatch.setattr(shadow, 'host_tools', lambda: dict(test_host=True))
    monkeypatch.setattr(shadow, 'route_key', lambda upstream, runtime: shadow.LOOPBACK_KEY)

    def fail_session(**kwargs):
        def broken_published(self):
            raise ValueError('unreadable repository state')
        monkeypatch.setattr(Repository, 'published', broken_published)
        raise RuntimeError('proxy closed early')

    monkeypatch.setattr(shadow, 'run_one', fail_session)
    assert groom.main([*args, '--cap-usd', '0.25']) == 1
    result = json.loads((out/'grooming-summary.json').read_text())
    assert result['status'] == 'failed' and result['reason'] == 'error: RuntimeError: proxy closed early'
    assert result['published_before'] == 'v1' and result['published_after'] is None and result['summary'] is None


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


@native_host
def test_boundary_grooming_files_game_facts_and_keeps_world_facts_after_live_windows(tmp_path, monkeypatch):
    scripted = curator_stand_in.script

    def scoped_submissions(messages, *args, **kwargs):
        calls = scripted(messages, *args, **kwargs)
        for tool, params in calls or []:
            if tool != 'write_file' or not params['path'].endswith('/submission.json'):
                continue
            submission = json.loads(params['content'])
            changes = submission['changes']
            if params['path'].startswith('submissions/grooming/'):
                changes[0]['article']['body'][0]['facts'] = ['f1', 'f2']
            else:
                number = int(submission['base_version'][1:]) + 1
                game_fact = changes[-1]['fact']
                game_fact.update(id=f'f{number}', text=f'observed control {number}')
                world_fact = dict(game_fact, id=f'world-f{number}', text=f'observed place {number}',
                                  scope=dict(game=shadow.GAME, level='world'))
                submission['changes'] = [*(changes if number == 1 else changes[-1:]), dict(op='add_fact', fact=world_fact)]
            params['content'] = json.dumps(submission)
        return calls

    monkeypatch.setattr(curator_stand_in, 'script', scoped_submissions)
    runtime, run = tmp_path/'runtime', tmp_path/'live-admission'
    out = runtime/'grooming'
    with StandIn(cost=0) as stand_in:
        config_path = runner_config(tmp_path, upstream=stand_in.url, session_cap_usd='0.5', trigger_steps=2,
                                    ceiling_steps=2, host=dict(max_requests=10, max_output_tokens=4096, wall_seconds=120))
        config = live_runner.read_config(config_path, runtime)
        repo = Repository(config['knowledge_root'], shadow.GAME)
        repo.ensure()
        directory = tmp_path/'runner'
        sessions = live_runner.Sessions(directory, config, repo, shadow.LOOPBACK_KEY)
        with LiveWriter(run) as writer:
            record_package(run, labels=dict(world='pond', lineage='pond-lineage', admission=1))
            runner = Runner(directory, run.name, snapshot=live.staged(run), session_call=sessions,
                            look=TagLook(repo), settings=config['settings'])
            writer(op='new_actor')
            for version in ('v1', 'v2'):
                for _ in range(2):
                    writer(op='step')
                assert runner.poll()
                assert repo.published() == version, status_of(runner)
                assert {f['scope']['level'] for f in repo.facts(version)} == {'game', 'world'}
            examined = status_of(runner)['examined']
            assert [(e['window']['first'], e['window']['last'], e['outcome']) for e in examined] == [
                (1, 2, 'accepted'), (3, 4, 'accepted')]
            assert writer(op='close')['wal'] == 0
            assert not runner.poll() and status_of(runner)['stop_reason'] == 'store-closing'
        assert sessions.spent == 0
        admission = repo.provenance()['last_admission']
        assert admission['coverage'] == dict(schema=COVERAGE, session=run.name, actor='001', last_step=4)
        assert len(admission['citations']) == 2
        assert groom.main(grooming_args(run, config_path, runtime, out)) == 0
        assert len(stand_in.requests) == 9

    result = json.loads((out/'grooming-summary.json').read_text())
    assert (result['status'], result['published_before'], result['published_after']) == ('completed', 'v2', 'v3')
    assert result['session_state'] == 'sealed' and result['cap_usd'] == '0.5' and Decimal(result['cost_usd']) == 0
    assert result['proxy']['settled'] is True and not result['proxy']['revoked'] and result['proxy']['breaches'] == 0
    assert result['sandbox']['survivors'] == [] and [v['status'] for v in result['verdicts']] == ['published']
    session = json.loads((out/result['summary']).read_text())
    assert session['session_kind'] == 'grooming' and session['window'] is None and session['run_state'] == 'completed'
    assert repo.published() == 'v3' and repo.provenance()['last_admission'] == admission
    facts = {f['id']: f for f in repo.facts() if current(f)}
    assert set(facts) == {'f1', 'f2', 'world-f1', 'world-f2'}
    assert all(f['schema'] == 'curator-fact/4' for f in facts.values())
    assert {f['id']: f['scope'] for f in facts.values() if f['scope']['level'] == 'world'} == dict.fromkeys(
        ('world-f1', 'world-f2'), dict(game=shadow.GAME, level='world', world='pond'))
    assert {f for a in repo.articles() if current(a) for claim in a['body'] for f in claim['facts']} == {'f1', 'f2'}
