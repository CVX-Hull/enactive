"""Synthetic supervision evidence; no game, provider, or human timing qualification."""
from datetime import datetime, timezone
import json
import os
import signal
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools import campaign_supervision as guard

SESSION = 'a' * 32
COMMIT = 'b' * 40


def row(**changes):
    return dict(schema='campaign-watch-attempt/1', source_commit=COMMIT,
        session=SESSION, sequence=1, observed_at=datetime.fromtimestamp(1040, timezone.utc).isoformat(),
        observation=140, start=144, phase='active', source=SESSION+'-1', sha256='c'*64,
        recorded_wall=1044, **changes)


def test_retained_exact_deadline_and_pause_boundaries():
    scope = dict(session=SESSION, source_commit=COMMIT, sequence=1, ready_wall=1000,
                 ready_at=100, last=100, custody_end=250)
    assert guard.verify_row(row(), now=144.999, **scope)
    for now in (145, 145.001):
        assert not guard.verify_row(row(), now=now, **scope)
    assert guard.cutoff_reason(145, 100, 250) == 'watch_deadline'
    assert guard.cutoff_reason(140, 100, 140) == 'custody_deadline'
    raced = dict(receipt=144.996, prior_observation=100, observation=144.95)
    rows = [raced]
    reason, grace, discarded = guard.pause_boundary(rows, 144.95, 144.995, 144.998, 250)
    assert reason is None and 0 < grace < .003 and discarded == [raced] and rows == []
    assert guard.pause_boundary([], 100, 144.999, 145, 250) == ('watch_deadline', 0, [])


@pytest.mark.parametrize('change', [dict(schema='old'), dict(source_commit='x'), dict(session='x'),
    dict(sequence=2), dict(source='other-1'), dict(sha256='wrong'), dict(observation=float('nan')),
    dict(observed_at='1970-01-01T00:16:45'), dict(start=140), dict(phase='unknown')])
def test_guard_rejects_substitution_or_invalid_clocks(change):
    value = row(); value.update(change)
    assert not guard.verify_row(value, session=SESSION, source_commit=COMMIT, sequence=1,
        ready_wall=1000, ready_at=100, last=100, custody_end=250, now=144.999)


def receipt(**changes):
    value = dict(schema='campaign-receipt/3', session=SESSION, source_commit=COMMIT,
        started_wall=1000, ended_wall=1010, elapsed_seconds=10,
        native_absence_verified=True, deciding_hosts_quiescent=True, input_authority_revoked=True,
        cleanup=dict(schema='computer-cleanup/1', session=SESSION, native_absence_verified=True,
                     normal_native_exit_zero=False, native=dict(pid=99, pgid=99, returncode=-15,
                                                               process_absent=True, group_absent=True)))
    value.update(changes)
    return value


def test_terminal_requires_check_and_current_bound_cleanup_receipt():
    rows = [dict(row(), observation=105, receipt=106, prior_observation=100)]
    scope = dict(session=SESSION, source_commit=COMMIT, rows=rows, ready_wall=1000,
                 ready_at=100, started_wall=999, native_pid=99, custody_end=120)
    assert guard.terminal_coverage(receipt(), **scope)
    assert not guard.terminal_coverage(receipt(), **dict(scope, rows=[]))
    for change in (dict(schema='campaign-receipt/2'), dict(source_commit='other'), dict(session='other'),
                   dict(native_absence_verified=False), dict(deciding_hosts_quiescent=False),
                   dict(input_authority_revoked=False), dict(cleanup={}), dict(ended_wall=float('inf')),
                   dict(ended_wall=1050, elapsed_seconds=50), dict(started_wall=900)):
        assert not guard.terminal_coverage(receipt(**change), **scope)
    assert not guard.terminal_coverage(receipt(), **dict(scope, native_pid=100))
    for wall in (1020, 1020.05):
        assert not guard.terminal_coverage(receipt(ended_wall=wall, elapsed_seconds=wall-1000), **scope)


def test_partial_watch_marker_is_never_rearmed(tmp_path, monkeypatch):
    (tmp_path/'watch-attempts.jsonl').write_text('partial')
    monkeypatch.setattr(guard, 'preflight', lambda _: ({}, {}, {}))
    with pytest.raises(ValueError, match='prior/partial'):
        guard.run_supervised(tmp_path)
    assert (tmp_path/'watch-attempts.jsonl').read_text() == 'partial'


@pytest.mark.parametrize('late', [0, .05])
def test_terminal_exit_does_not_bypass_original_custody_cutoff(tmp_path, late):
    checks, sender = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    result = dict(accepted=[], started_wall=999, started_monotonic=99)
    now = [144.5]
    clock = SimpleNamespace(monotonic=lambda: now[0], time=lambda: now[0]+900)
    (tmp_path/'started.json').write_text(json.dumps(dict(schema='computer-start/1', session=SESSION,
        started_wall=1000, deadline_monotonic=160)))
    (tmp_path/'ready.json').write_text(json.dumps(dict(schema='computer-ready/1', session=SESSION,
        ready_wall=1000, pid=99, viewer_url='http://127.0.0.1:12345/')))
    sender.send(json.dumps(row()).encode())
    def poll():
        if not result['accepted']:
            return None
        now[0] = 160.1
        (tmp_path/'receipt.json').write_text(json.dumps(receipt(ended_wall=1060+late,
            elapsed_seconds=60+late)))
        return 0
    live = SimpleNamespace(poll=lambda: None)
    with checks, sender, stops, stop_sender:
        reason = guard.supervise(tmp_path,
            dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345),
            SimpleNamespace(poll=poll), live, live, checks, stops, lambda: False, result, clock=clock)
    assert reason == 'terminal_watch_unverified' and not result['terminal_coverage_verified']
    assert result['custodian_receipt']['native_absence_verified']  # Cleanup remains a separate fact.


@pytest.mark.parametrize('completed', [144.997, 145, 145.1])
def test_confirmation_completion_obeys_cutoff_and_pause_rollback(tmp_path, completed):
    checks, sender = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    now = [144.5]
    class ScheduledConfirmation:
        def fileno(self):return checks.fileno()
        def setblocking(self, value):checks.setblocking(value)
        def recv(self, size):return checks.recv(size)
        def send(self, data):
            # Pause arrives after the final pre-send poll but before completion.
            stop_sender.send(b'pause:144.995');stop_sender.send(b'pause-replied')
            count = checks.send(data)
            now[0] = completed
            return count
    clock = SimpleNamespace(monotonic=lambda: now[0], time=lambda: now[0]+900)
    (tmp_path/'started.json').write_text(json.dumps(dict(schema='computer-start/1', session=SESSION,
        started_wall=1000, deadline_monotonic=200)))
    (tmp_path/'ready.json').write_text(json.dumps(dict(schema='computer-ready/1', session=SESSION,
        ready_wall=1000, pid=99, viewer_url='http://127.0.0.1:12345/')))
    sender.send(json.dumps(row()).encode())
    result = dict(accepted=[], started_wall=999, started_monotonic=99)
    live = SimpleNamespace(poll=lambda: None)
    with checks, sender, stops, stop_sender:
        reason = guard.supervise(tmp_path,
            dict(session=SESSION, source_commit=COMMIT, wall_seconds=100, port=12345),
            live, live, live, ScheduledConfirmation(), stops, lambda: False, result, clock=clock)
    assert result['accepted'] == []
    if completed < 145:
        assert reason == 'operator_pause'
        assert len(result['checks_raced_with_pause']) == 1
        assert result['checks_raced_with_pause'][0]['receipt'] == completed
    else:
        assert reason == 'watch_deadline'


def test_guard_does_not_renew_without_completed_confirmation(tmp_path):
    # A disconnected check socket fails the guard confirmation; no accepted row survives.
    checks, sender = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    live = SimpleNamespace(poll=lambda: None)
    profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=100, port=12345)
    clock = SimpleNamespace(monotonic=lambda: 144.5, time=lambda: 1044.5)
    (tmp_path/'started.json').write_text(json.dumps(dict(schema='computer-start/1', session=SESSION,
        started_wall=1000, deadline_monotonic=200)))
    (tmp_path/'ready.json').write_text(json.dumps(dict(schema='computer-ready/1', session=SESSION,
        ready_wall=1000, pid=99, viewer_url='http://127.0.0.1:12345/')))
    sender.send(json.dumps(row()).encode()); sender.close()
    result = dict(accepted=[], started_wall=999, started_monotonic=99)
    with checks, stops, stop_sender:
        reason = guard.supervise(tmp_path, profile, live, live, live, checks, stops,
                                 lambda: False, result, clock=clock)
    assert reason == 'acknowledgement_uncertain' and result['accepted'] == []


@pytest.mark.parametrize('fail_at', [0, 1, 2, None])
def test_startup_failures_and_signal_close_only_created_groups(tmp_path, monkeypatch, fail_at):
    profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345)
    monkeypatch.setattr(guard, 'preflight', lambda _: (profile, {'api_key_env': 'WATCH_TEST_KEY'}, {}))
    monkeypatch.setenv('WATCH_TEST_KEY', 'synthetic-not-a-provider-key')
    (tmp_path/'manifest.json').write_text('{}')
    launched = []
    calls = []
    def launch(argv, **kwargs):
        index = len(calls)
        calls.append((argv, kwargs))
        assert json.loads((tmp_path/'watch-start.json').read_text())['schema'] == 'campaign-watch-start/1'
        if index == fail_at:
            raise OSError('synthetic spawn failure')
        if index == 1:
            code = ('import socket,sys,time,json; '
                's=socket.socket(fileno=int(sys.argv[1])); '
                's.send(json.dumps({"port":12346}).encode()); time.sleep(20)')
            command = [sys.executable, '-c', code, argv[-2]]
        else:
            command = [sys.executable, '-c', 'import time; time.sleep(20)']
        child = subprocess.Popen(command, **kwargs)
        launched.append(child)
        return child
    def supervision(*args, **kwargs):
        # Exercise the installed real SIGTERM handler after all children exist.
        os.kill(os.getpid(), signal.SIGTERM)
        assert args[7]()
        return 'supervision_lost'
    monkeypatch.setattr(guard, 'supervise', supervision)
    original = signal.getsignal(signal.SIGTERM)
    result = guard.run_supervised(tmp_path, popen=launch)
    assert signal.getsignal(signal.SIGTERM) == original
    assert all(child.poll() is not None for child in launched)
    assert result['cleanup_verified'] and not result['terminal_coverage_verified']
    assert result['manifest_unchanged']
    assert result['reason'] == ('supervision_lost' if fail_at is None else 'launch_or_supervision_error')
    assert result['children'].keys() == set(('custodian', 'gateway', 'wake')[:len(launched)])
    if fail_at is None:
        assert result['signal'] == 'SIGTERM'
        assert calls[1][0][-3] == str(launched[0].pid)
    for index, (_, options) in enumerate(calls):
        assert options['start_new_session'] is True
        assert ('WATCH_TEST_KEY' in options['env']) == (index == 0)
    terminal = json.loads((tmp_path/'watch-terminal.json').read_text())
    assert terminal == result
    with pytest.raises(ValueError, match='prior/partial'):
        guard.run_supervised(tmp_path, popen=launch)


def test_terminal_without_first_check_never_certifies_coverage(tmp_path):
    (tmp_path/'receipt.json').write_text(json.dumps(receipt()))
    checks, sender = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    result = dict(accepted=[], started_wall=999, started_monotonic=99)
    live = SimpleNamespace(poll=lambda: None)
    with checks, sender, stops, stop_sender:
        reason = guard.supervise(tmp_path, dict(session=SESSION, source_commit=COMMIT, wall_seconds=100),
            SimpleNamespace(poll=lambda: 0), live, live, checks, stops, lambda: False, result)
    assert reason == 'terminal_watch_unverified'
    assert result['terminal_coverage_verified'] is False


@pytest.mark.parametrize('marker, change, reason', [
    ('started.json', dict(schema='computer-start/0'), 'invalid_custodian_start'),
    ('started.json', dict(session='other'), 'invalid_custodian_start'),
    ('started.json', dict(deadline_monotonic=float('inf')), 'invalid_custodian_start'),
    ('started.json', dict(deadline_monotonic=210), 'invalid_custodian_start'),
    ('ready.json', dict(schema='computer-ready/0'), 'invalid_custodian_ready'),
    ('ready.json', dict(session='other'), 'invalid_custodian_ready'),
    ('ready.json', dict(ready_wall=2000), 'invalid_custodian_ready'),
    ('ready.json', dict(viewer_url='http://127.0.0.1:54321/'), 'invalid_custodian_ready'),
])
def test_start_ready_substitution_never_extends_custody(tmp_path, marker, change, reason):
    opening = dict(schema='computer-start/1', session=SESSION, started_wall=1000, deadline_monotonic=200)
    ready = dict(schema='computer-ready/1', session=SESSION, ready_wall=1000, pid=99,
                 viewer_url='http://127.0.0.1:12345/')
    for name, value in (('started.json', opening), ('ready.json', ready)):
        if name == marker:
            value.update(change)
        (tmp_path/name).write_text(json.dumps(value))
    checks, sender = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    live = SimpleNamespace(poll=lambda: None)
    with checks, sender, stops, stop_sender:
        actual = guard.supervise(tmp_path,
            dict(session=SESSION, source_commit=COMMIT, wall_seconds=100, port=12345),
            live, live, live, checks, stops, lambda: False,
            dict(accepted=[], started_wall=999, started_monotonic=99),
            clock=SimpleNamespace(monotonic=lambda: 144.5, time=lambda: 1044.5))
    assert actual == reason


@pytest.mark.parametrize('lost', ['gateway', 'wake', 'signal'])
def test_guard_detects_independent_supervision_loss(tmp_path, lost):
    checks, sender = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    live = SimpleNamespace(poll=lambda: None)
    dead = SimpleNamespace(poll=lambda: 1)
    with checks, sender, stops, stop_sender:
        reason = guard.supervise(tmp_path, dict(wall_seconds=60), live,
            dead if lost == 'gateway' else live, dead if lost == 'wake' else live,
            checks, stops, lambda: lost == 'signal',
            dict(accepted=[], started_wall=999, started_monotonic=99))
    assert reason == 'supervision_lost'


@pytest.mark.parametrize('substitution', ['receipt', 'manifest', 'cleanup'])
def test_final_substitution_and_cleanup_failure_cannot_certify_success(tmp_path, monkeypatch, substitution):
    profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345)
    monkeypatch.setattr(guard, 'preflight', lambda _: (profile, {'api_key_env': 'WATCH_TEST_KEY'}, {}))
    monkeypatch.setenv('WATCH_TEST_KEY', 'synthetic-not-a-provider-key')
    (tmp_path/'manifest.json').write_text('{}')
    handles = []
    def launch(argv, **kwargs):
        if len(handles) == 1:
            command = [sys.executable, '-c',
                'import socket,sys,time; socket.socket(fileno=int(sys.argv[1])).send(b\'{"port":12346}\'); time.sleep(20)',
                argv[-2]]
        else:
            command = [sys.executable, '-c', 'import time; time.sleep(20)']
        handle = subprocess.Popen(command, **kwargs); handles.append(handle)
        return handle
    def supervision(*args, **kwargs):
        result = args[8]
        result['terminal_coverage_verified'] = True
        result['custodian_receipt'] = receipt()
        report = receipt(source_commit='substituted') if substitution == 'receipt' else receipt()
        (tmp_path/'receipt.json').write_text(json.dumps(report))
        if substitution == 'manifest':
            (tmp_path/'manifest.json').write_text('{"substituted":true}')
        return 'custodian_terminal'
    monkeypatch.setattr(guard, 'supervise', supervision)
    original_close = guard.close_group
    closed = []
    def close(handle):
        actual = original_close(handle); closed.append(handle.pid)
        if substitution == 'cleanup' and handle is handles[1]:
            raise PermissionError('synthetic denied cleanup verification after actual fixture cleanup')
        return actual
    monkeypatch.setattr(guard, 'close_group', close)
    result = guard.run_supervised(tmp_path, popen=launch)
    assert len(closed) == 3 and all(h.poll() is not None for h in handles)
    if substitution == 'cleanup':
        assert not result['cleanup_verified']
        assert result['cleanup']['gateway']['error'] == 'PermissionError'
        assert 'synthetic denied' in result['cleanup']['gateway']['error_traceback']
    else:
        assert not result['terminal_coverage_verified']
    if substitution == 'receipt':
        assert result['custodian_receipt']['source_commit'] == COMMIT
        assert not result['custodian_receipt_unchanged']
