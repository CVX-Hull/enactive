"""Synthetic supervision evidence; no game, provider, or human timing qualification."""
import json
import os
import signal
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from harness.viewer.app import create_app
from harness.viewer.catalog import Catalog
from tests.test_campaign_watch import fixture as watch_fixture
from tools import campaign_supervision as guard

SESSION = 'a' * 32
COMMIT = 'b' * 40


def test_gateway_passes_viewer_routing_errors_as_json(tmp_path):
    client = TestClient(create_app(Catalog(tmp_path / 'evaluation')))
    with watch_fixture(tmp_path) as gateway:
        for method, path, code, error in (
                ('GET', '/api/view/no-such-route', 404, 'not_found'),
                ('POST', '/api/view/frame/curator-drafts', 405, 'method_not_allowed')):
            # The gateway forwards GET only, including a 405 returned by the upstream viewer.
            upstream = client.request(method, path)
            assert upstream.status_code == code
            gateway.state['view'].update(status=code, media=upstream.headers['content-type'], body=upstream.content)
            response, data = gateway.reply(path)
            assert response.status == code and gateway.state['view']['paths'][-1] == path
            assert response.getheader('Content-Type') == 'application/json'
            assert data == upstream.content and json.loads(data)['error'] == error


def markers(directory, *, deadline=200):
    (directory/'started.json').write_text(json.dumps(dict(schema='computer-start/1', session=SESSION,
        started_wall=1000, deadline_monotonic=deadline)))
    (directory/'ready.json').write_text(json.dumps(dict(schema='computer-ready/1', session=SESSION,
        ready_wall=1000, pid=99, viewer_url='http://127.0.0.1:12345/')))


def receipt(**changes):
    value = dict(schema='campaign-receipt/7', session=SESSION, source_commit=COMMIT,
        started_wall=1000, ended_wall=1010, elapsed_seconds=10,
        native_absence_verified=True, deciding_hosts_quiescent=True, input_authority_revoked=True,
        cleanup=dict(schema='computer-cleanup/1', session=SESSION, native_absence_verified=True,
                     normal_native_exit_zero=False, native=dict(pid=99, pgid=99, returncode=-15,
                                                               process_absent=True, group_absent=True)))
    value.update(changes)
    return value


def test_terminal_requires_current_bound_cleanup_receipt_before_the_custody_deadline():
    # Readiness maps wall 1000 to monotonic 100, so a receipt ending at wall W maps to 100 + (W - 1000).
    scope = dict(session=SESSION, source_commit=COMMIT, ready_wall=1000,
                 ready_at=100, started_wall=999, native_pid=99, custody_end=120)
    assert guard.terminal_coverage(receipt(), **scope)
    for change in (dict(schema='campaign-receipt/3'), dict(source_commit='other'), dict(session='other'),
                   dict(native_absence_verified=False), dict(deciding_hosts_quiescent=False),
                   dict(input_authority_revoked=False), dict(cleanup={}), dict(ended_wall=float('inf')),
                   dict(ended_wall=1050, elapsed_seconds=50), dict(started_wall=900)):
        assert not guard.terminal_coverage(receipt(**change), **scope)
    assert not guard.terminal_coverage(receipt(), **dict(scope, native_pid=100))
    assert not guard.terminal_coverage(receipt(), **dict(scope, ready_wall=None, ready_at=None))
    assert not guard.terminal_coverage(receipt(), **dict(scope, custody_end=float('nan')))
    # The custody deadline (mapped 120) is strict.
    assert guard.terminal_coverage(receipt(ended_wall=1019.99, elapsed_seconds=19.99), **scope)
    for wall in (1020, 1020.05):
        assert not guard.terminal_coverage(receipt(ended_wall=wall, elapsed_seconds=wall-1000), **scope)


@pytest.mark.parametrize('marker', guard.MARKERS)
def test_partial_watch_marker_is_never_rearmed(tmp_path, monkeypatch, marker):
    (tmp_path/marker).write_text('partial')
    monkeypatch.setattr(guard, 'preflight', lambda _: ({}, {}, {}))
    with pytest.raises(ValueError, match='prior/partial'):
        guard.run_supervised(tmp_path)
    assert (tmp_path/marker).read_text() == 'partial'
    assert sorted(path.name for path in tmp_path.iterdir()) == [marker]


def test_credential_prefers_environment_then_mapped_keychain_item(tmp_path):
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout='synthetic-not-a-provider-key\n')
    mapping = tmp_path/'credentials.json'
    assert guard.credential('KEY', environ={'KEY': 'from-env'}, mapping=mapping, run=run) == 'from-env'
    assert guard.credential('KEY', environ={}, mapping=mapping, run=run) is None
    mapping.write_text(json.dumps({'OTHER': {'keychain_service': 'other-item'}}))
    assert guard.credential('KEY', environ={}, mapping=mapping, run=run) is None and calls == []
    mapping.write_text(json.dumps({'KEY': {'keychain_service': 'operator-item'}}))
    assert guard.credential('KEY', environ={}, mapping=mapping, run=run) == 'synthetic-not-a-provider-key'
    assert calls == [['/usr/bin/security', 'find-generic-password', '-s', 'operator-item', '-w']]


@pytest.mark.parametrize('content, message', [('[]', 'must be a JSON object'), ('{"KEY": 1, "KEY": 2}', 'bounded regular'),
                                              ('not json', 'bounded regular')])
def test_credential_refuses_malformed_map_naming_it(tmp_path, content, message):
    mapping = tmp_path/'credentials.json'
    mapping.write_text(content)
    with pytest.raises(ValueError, match=message):
        guard.credential('KEY', environ={}, mapping=mapping, run=lambda *a, **k: pytest.fail('no lookup'))


def test_credential_lookup_timeout_is_a_clean_refusal(tmp_path):
    mapping = tmp_path/'credentials.json'
    mapping.write_text(json.dumps({'KEY': {'keychain_service': 'operator-item'}}))
    def run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs['timeout'], output='partial-secret')
    with pytest.raises(ValueError, match="'operator-item' for KEY timed out") as raised:
        guard.credential('KEY', environ={}, mapping=mapping, run=run)
    assert 'partial-secret' not in str(raised.value) and raised.value.__cause__ is None


@pytest.mark.parametrize('entry', [{'keychain_service': ''}, {'keychain_service': 1}, 'operator-item',
                                   {'keychain_service': 'item', 'account': 'x'}, None])
def test_credential_refuses_malformed_map_entries(tmp_path, entry):
    mapping = tmp_path/'credentials.json'
    mapping.write_text(json.dumps({'KEY': entry}))
    with pytest.raises(ValueError, match='Invalid credential map entry'):
        guard.credential('KEY', environ={}, mapping=mapping, run=lambda *a, **k: pytest.fail('no lookup'))


@pytest.mark.parametrize('result', [SimpleNamespace(returncode=44, stdout=''),
                                    SimpleNamespace(returncode=0, stdout='\n')])
def test_missing_keychain_item_is_named_without_any_value(tmp_path, result):
    mapping = tmp_path/'credentials.json'
    mapping.write_text(json.dumps({'KEY': {'keychain_service': 'operator-item'}}))
    with pytest.raises(ValueError, match="Keychain item 'operator-item' for KEY is unavailable"):
        guard.credential('KEY', environ={}, mapping=mapping, run=lambda *a, **k: result)


def test_unwatched_supervision_runs_until_the_custodian_terminal(tmp_path):
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    now = [100.0]
    clock = SimpleNamespace(monotonic=lambda: now[0], time=lambda: now[0]+900)
    markers(tmp_path)
    polls = [0]
    def poll():
        polls[0] += 1
        now[0] = 100 + polls[0]*10  # Ten seconds per poll with no operator action at all.
        if now[0] < 190:
            return None
        (tmp_path/'receipt.json').write_text(json.dumps(receipt(ended_wall=1085, elapsed_seconds=85)))
        return 0
    result = dict(started_wall=999, started_monotonic=99)
    live = SimpleNamespace(poll=lambda: None)
    with stops, stop_sender:
        reason = guard.supervise(tmp_path,
            dict(session=SESSION, source_commit=COMMIT, wall_seconds=101, port=12345),
            SimpleNamespace(poll=poll), live, live, stops, lambda: False, result, clock=clock)
    assert reason == 'custodian_terminal' and result['terminal_coverage_verified']
    assert 'pause_reason' not in result and result['native_pid'] == 99


@pytest.mark.parametrize('late', [0, .05])
def test_terminal_exit_does_not_bypass_original_custody_cutoff(tmp_path, late):
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    result = dict(started_wall=999, started_monotonic=99)
    now = [144.5]
    clock = SimpleNamespace(monotonic=lambda: now[0], time=lambda: now[0]+900)
    markers(tmp_path, deadline=160)
    def poll():
        if 'ready_monotonic' not in result:
            return None
        now[0] = 160.1
        (tmp_path/'receipt.json').write_text(json.dumps(receipt(ended_wall=1060+late,
            elapsed_seconds=60+late)))
        return 0
    live = SimpleNamespace(poll=lambda: None)
    with stops, stop_sender:
        reason = guard.supervise(tmp_path,
            dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345),
            SimpleNamespace(poll=poll), live, live, stops, lambda: False, result, clock=clock)
    assert reason == 'terminal_watch_unverified' and not result['terminal_coverage_verified']
    assert result['custodian_receipt']['native_absence_verified']  # Cleanup remains a separate fact.


@pytest.mark.parametrize('pause', [False, True])
def test_custody_deadline_stops_a_live_run_and_a_late_pause_never_extends_it(tmp_path, pause):
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    result = dict(started_wall=999, started_monotonic=99)
    now = [144.5]
    clock = SimpleNamespace(monotonic=lambda: now[0], time=lambda: now[0]+900)
    markers(tmp_path, deadline=160)
    def poll():
        if 'ready_monotonic' in result:
            now[0] = 160  # Equality is already too late.
            if pause and not polls:
                stop_sender.send(b'pause:159.9:loop'); stop_sender.send(b'pause-replied')
            polls.append(1)
        return None
    polls = []
    with stops, stop_sender:
        reason = guard.supervise(tmp_path,
            dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345),
            SimpleNamespace(poll=poll), SimpleNamespace(poll=lambda: None), SimpleNamespace(poll=lambda: None),
            stops, lambda: False, result, clock=clock)
    assert reason == 'custody_deadline' and 'terminal_coverage_verified' not in result
    assert result.get('pause_reason') == ('loop' if pause else None)
    assert 'pause_reply_forwarded' not in result


def gateway_command(argv):
    code = ('import socket,sys,time,json; '
        's=socket.socket(fileno=int(sys.argv[1])); '
        's.send(json.dumps({"port":12346}).encode()); time.sleep(20)')
    return [sys.executable, '-c', code, argv[argv.index('--viewer-port')-1]]


@pytest.mark.parametrize('fail_at', [0, 1, 2, 3, None])
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
        opening = json.loads((tmp_path/'watch-start.json').read_text())
        assert opening['schema'] == 'campaign-watch-start/4' and opening['viewer_port'] == 54321
        assert set(opening) == {'schema', 'session', 'source_commit', 'manifest_sha256', 'started_wall',
                                'started_monotonic', 'viewer_port'}
        if index == fail_at:
            raise OSError('synthetic spawn failure')
        if '--viewer-port' in argv:
            command = gateway_command(argv)
        else:
            command = [sys.executable, '-c', 'import time; time.sleep(20)']
        child = subprocess.Popen(command, **kwargs)
        launched.append(child)
        return child
    def supervision(*args, **kwargs):
        # Exercise the installed real SIGTERM handler after all children exist.
        os.kill(os.getpid(), signal.SIGTERM)
        assert args[6]()
        return 'supervision_lost'
    monkeypatch.setattr(guard, 'supervise', supervision)
    original = signal.getsignal(signal.SIGTERM)
    result = guard.run_supervised(tmp_path, popen=launch, viewer_port=lambda: 54321,
                                  curator_results=('alpha=one', 'beta=two'), curator_sessions=('receipt=three',),
                                  curator_drafts=('drafts=four', 'archive=five'))
    assert signal.getsignal(signal.SIGTERM) == original
    assert all(child.poll() is not None for child in launched)
    assert result['cleanup_verified'] and not result['terminal_coverage_verified']
    assert result['manifest_unchanged']
    # A viewer that cannot start never costs the run its supervision; any other launch failure does.
    fatal = fail_at in (0, 2, 3)
    assert result['reason'] == ('launch_or_supervision_error' if fatal else 'supervision_lost')
    assert result['schema'] == 'campaign-watch-terminal/4' and result['pause_reason'] is None
    assert not {'attention', 'watch_seconds', 'accepted'} & set(result)
    assert not (tmp_path/'watch-attempts.jsonl').exists()
    order = ['custodian', 'viewer', 'gateway', 'wake']
    expected = set(order) if fail_at in (None, 1) else set(order[:fail_at])
    assert result['children'].keys() == expected
    if fail_at == 1:
        assert result['children']['viewer'] == dict(port=54321, supervised=False, launch_error='OSError')
        assert result['cleanup']['viewer'] == dict(launched=False)
    elif fail_at in (None, 2, 3):
        viewer = result['children']['viewer']
        assert viewer['port'] == 54321 and viewer['supervised'] is False and viewer['pid'] == launched[1].pid
        assert result['cleanup']['viewer']['process_absent'] and result['cleanup']['viewer']['group_absent']
    if fail_at is None:
        assert result['signal'] == 'SIGTERM'
        gateway = calls[2][0]
        assert gateway[gateway.index('--viewer-port')+1] == '54321'
        assert gateway[gateway.index('--viewer-port')-2] == str(launched[0].pid)
        assert calls[2][1]['pass_fds'] == (int(gateway[gateway.index('--viewer-port')-1]),)
    if fail_at != 0:
        argv = calls[1][0]
        assert argv[1:3] == ['-m', 'harness.viewer'] and argv[argv.index('--port')+1] == '54321'
        assert argv[-10:] == ['--curator-results', 'alpha=one', '--curator-results', 'beta=two', '--curator-sessions', 'receipt=three',
                              '--curator-drafts', 'drafts=four', '--curator-drafts', 'archive=five']
        assert all('--curator-sessions' not in args for args, _ in calls if 'harness.viewer' not in args)
        assert all('--curator-results' not in args for args, _ in calls if 'harness.viewer' not in args)
        assert all('--curator-drafts' not in args for args, _ in calls if 'harness.viewer' not in args)
        assert argv[argv.index('--host')+1] == '127.0.0.1' and argv[argv.index('--run')+1] == str(tmp_path)
        assert argv[argv.index('--root')+1] == str(guard.ROOT/'.runtime'/'evaluations') and '--runs' not in argv
    for index, (_, options) in enumerate(calls):
        assert options['start_new_session'] is True
        assert ('WATCH_TEST_KEY' in options['env']) == (index == 0)
    terminal = json.loads((tmp_path/'watch-terminal.json').read_text())
    assert terminal == result
    with pytest.raises(ValueError, match='prior/partial'):
        guard.run_supervised(tmp_path, popen=launch, viewer_port=lambda: 54321)


def test_viewer_exit_never_counts_as_supervision_loss(tmp_path, monkeypatch):
    profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345)
    monkeypatch.setattr(guard, 'preflight', lambda _: (profile, {'api_key_env': 'WATCH_TEST_KEY'}, {}))
    monkeypatch.setenv('WATCH_TEST_KEY', 'synthetic-not-a-provider-key')
    (tmp_path/'manifest.json').write_text('{}')
    launched = {}
    def launch(argv, **kwargs):
        if 'harness.viewer' in argv:
            command = [sys.executable, '-c', 'pass']  # The viewer exits at once.
            name = 'viewer'
        elif '--viewer-port' in argv:
            command = gateway_command(argv)
            command[2] = 'import time; time.sleep(.6); ' + command[2]  # Gateway reports after the viewer died.
            name = 'gateway'
        else:
            command = [sys.executable, '-c', 'import time; time.sleep(20)']
            name = 'other'+str(len(launched))
        launched[name] = subprocess.Popen(command, **kwargs)
        return launched[name]
    outcome = {}
    def supervision(*args, **kwargs):
        viewer = launched['viewer']
        viewer.wait(3)
        outcome['viewer_exited'] = viewer.returncode == 0
        outcome['others_alive'] = all(h.poll() is None for n, h in launched.items() if n != 'viewer')
        return 'custodian_terminal'
    monkeypatch.setattr(guard, 'supervise', supervision)
    result = guard.run_supervised(tmp_path, popen=launch, runs=tmp_path/'archive')
    assert outcome == dict(viewer_exited=True, others_alive=True)
    assert result['reason'] == 'custodian_terminal' and 'error' not in result
    assert result['cleanup_verified'] and result['children']['viewer']['supervised'] is False
    assert '--runs' in result['children']['viewer']['argv']
    assert result['cleanup']['viewer']['process_absent']


def supervised_with_runner(tmp_path, monkeypatch, runner_code, *, configured=True):
    """A supervised run whose curator runner child runs `runner_code` (None: its launch fails)."""
    profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345)
    monkeypatch.setattr(guard, 'preflight', lambda _: (profile, {'api_key_env': 'WATCH_TEST_KEY'}, {}))
    monkeypatch.setenv('WATCH_TEST_KEY', 'synthetic-not-a-provider-key')
    run = tmp_path/'run'
    run.mkdir()
    (run/'manifest.json').write_text('{}')
    config = tmp_path/'runner.json'
    config.write_text('{}')
    launched, calls, closed = {}, [], []
    def launch(argv, **kwargs):
        if 'tools.campaign_run' in argv:
            name = 'custodian'
            assert (run/'curator-read.lock').is_file() == configured  # before the custodian, or never
        elif 'tools.curator_host.live_runner' in argv:
            name = 'curator_runner'
            if runner_code is None:
                raise OSError('synthetic runner spawn failure')
        else:
            name = 'viewer' if 'harness.viewer' in argv else 'gateway' if '--viewer-port' in argv else 'wake'
        calls.append((name, argv, kwargs))
        command = gateway_command(argv) if name == 'gateway' else [sys.executable, '-c',
            runner_code if name == 'curator_runner' else 'import time; time.sleep(20)']
        handle = launched[name] = subprocess.Popen(command, cwd=run, **{k: v for k, v in kwargs.items() if k != 'cwd'})
        if name == 'curator_runner':
            terminate = handle.terminate
            handle.terminate = lambda: (events.append('runner-terminate'), terminate())[1]
        if name == 'custodian':
            wait = handle.wait
            handle.wait = lambda *a, **k: (events.append('custodian-wait'), wait(*a, **k))[1]
        return handle
    events = []
    outcome = {}
    def supervision(*args, **kwargs):
        if 'curator_runner' in launched and 'runner-ready' in runner_code:
            end = time.monotonic() + 10
            while not (run/'runner-ready').exists() and time.monotonic() < end:
                time.sleep(.02)
        if 'curator_runner' in launched:
            try:  # long enough for an early exit to happen, while the run goes on
                launched['curator_runner'].wait(timeout=.5 if 'sleep' in runner_code else 10)
            except subprocess.TimeoutExpired:
                pass
            outcome['runner_alive'] = launched['curator_runner'].poll() is None
        outcome['others_alive'] = all(h.poll() is None for n, h in launched.items() if n != 'curator_runner')
        return 'custodian_terminal'
    monkeypatch.setattr(guard, 'supervise', supervision)
    original_close = guard.close_group
    def close(handle):
        closed.append(next(name for name, h in launched.items() if h is handle))
        return original_close(handle)
    monkeypatch.setattr(guard, 'close_group', close)
    result = guard.run_supervised(run, popen=launch, viewer_port=lambda: 54321,
                                  curator_runner=config if configured else None)
    assert all(h.poll() is not None for h in launched.values())
    outcome['events'] = events
    return run, result, calls, closed, outcome


def test_a_curator_runner_starts_after_the_custodian_outside_supervision_and_is_closed_last(tmp_path, monkeypatch):
    run, result, calls, closed, outcome = supervised_with_runner(tmp_path, monkeypatch, 'import time; time.sleep(20)')
    assert [name for name, _, _ in calls] == ['custodian', 'viewer', 'curator_runner', 'gateway', 'wake']
    assert outcome['runner_alive'] and outcome['others_alive']
    assert result['reason'] == 'custodian_terminal' and 'error' not in result and result['cleanup_verified']
    child = result['children']['curator_runner']
    assert child['supervised'] is False and child['created_process_group'] is True
    argv = child['argv']
    assert argv[1:3] == ['-m', 'tools.curator_host.live_runner']
    assert argv[argv.index('--run')+1] == str(run) and argv[argv.index('--directory')+1] == str(run/'curator-runner')
    assert argv[argv.index('--config')+1] == str((tmp_path/'runner.json').resolve())
    # The viewer it starts reads the runner's status file (against R-REGRESSION: a paid run nobody can watch).
    viewer = result['children']['viewer']['argv']
    assert viewer[viewer.index('--curator-runner-status')+1] == str(run/'curator-runner'/'status.json')
    options = calls[2][2]
    assert options['start_new_session'] is True and 'WATCH_TEST_KEY' not in options['env']
    cleanup = result['cleanup']['curator_runner']
    assert cleanup['launched'] and not cleanup['exited_before_teardown']
    assert cleanup['process_absent'] and cleanup['group_absent']
    # The custodian's bounded wait comes before anything that waits for the runner.
    assert closed.index('custodian') < closed.index('curator_runner') and closed[-1] == 'curator_runner'
    assert (run/'curator-read.lock').is_file() and (run/'curator-runner').is_dir()
    assert (run/'curator-runner'/'stdout.txt').is_file()


def test_a_runner_finishes_its_close_out_before_group_cleanup(tmp_path, monkeypatch):
    assert guard.CURATOR_RUNNER_TEARDOWN_GRACE_SECONDS >= 15.0
    monkeypatch.setattr(guard, 'CURATOR_RUNNER_TEARDOWN_GRACE_SECONDS', 2.5)
    runner_code = '''
import signal, time
def close_out(*_):
    time.sleep(.9)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, close_out)
open('runner-ready', 'w').close()
signal.pause()
'''
    _, result, _, _, outcome = supervised_with_runner(tmp_path, monkeypatch, runner_code)
    cleanup = result['cleanup']['curator_runner']
    assert outcome['runner_alive'] and cleanup['returncode'] == 0
    assert 'grace_expired' not in cleanup and cleanup['signals'] == []
    assert cleanup['process_absent'] and cleanup['group_absent'] and result['cleanup_verified']


RUNNER_IGNORING_SIGTERM = '''
import os, signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN); signal.signal(signal.SIGINT, signal.SIG_IGN)
os.makedirs('curator-runner/snapshots/killed/run/actors', exist_ok=True)  # a snapshot left mid-poll
open('curator-runner/snapshots/killed/run/actors/actor.json', 'w').write('{"token": "custody copy"}')
open('runner-ready', 'w').close()
time.sleep(60)
'''


def test_a_runner_that_ignores_sigterm_is_asked_first_killed_last_and_its_snapshots_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, 'CURATOR_RUNNER_TEARDOWN_GRACE_SECONDS', .2)
    run, result, _, closed, outcome = supervised_with_runner(tmp_path, monkeypatch, RUNNER_IGNORING_SIGTERM)
    assert outcome['runner_alive']
    # Asked to terminate before the custodian's bounded wait is entered; closed after it.
    assert outcome['events'].index('runner-terminate') < outcome['events'].index('custodian-wait')
    assert closed.index('custodian') < closed.index('curator_runner')
    cleanup = result['cleanup']['curator_runner']
    assert cleanup.get('grace_expired') is True
    assert cleanup['signals'][-1] == 'SIGKILL' and cleanup['process_absent'] and cleanup['group_absent']
    assert result['reason'] == 'custodian_terminal' and result['cleanup_verified'] and 'error' not in result
    assert cleanup['snapshots_removed'] is True and not (run/'curator-runner'/'snapshots').exists()


@pytest.mark.parametrize('left', ['curator-read.lock', 'curator-runner'])
def test_a_package_that_already_holds_runner_files_is_refused_before_the_reservation(tmp_path, monkeypatch, left):
    monkeypatch.setattr(guard, 'preflight', lambda _: pytest.fail('refused before preflight'))
    run = tmp_path/'run'
    run.mkdir()
    (run/left).mkdir() if left == 'curator-runner' else (run/left).touch()
    config = tmp_path/'runner.json'
    config.write_text('{}')
    with pytest.raises(ValueError, match='already holds a curator read lock or runner directory'):
        guard.run_supervised(run, curator_runner=config)
    assert sorted(p.name for p in run.iterdir()) == [left]  # no reservation: the package is not made inert


@pytest.mark.parametrize('runner_code', ['raise SystemExit(3)', None])
def test_a_curator_runner_that_exits_early_or_cannot_start_never_ends_or_fails_the_run(tmp_path, monkeypatch, runner_code):
    _, result, calls, _, outcome = supervised_with_runner(tmp_path, monkeypatch, runner_code)
    assert outcome['others_alive'] and result['reason'] == 'custodian_terminal' and 'error' not in result
    assert result['cleanup_verified']
    if runner_code is None:
        assert result['children']['curator_runner'] == dict(supervised=False, launch_error='OSError')
        assert result['cleanup']['curator_runner'] == dict(launched=False)
    else:
        assert outcome['runner_alive'] is False
        assert result['cleanup']['curator_runner']['exited_before_teardown'] is True
        assert result['cleanup']['curator_runner']['returncode'] == 3
    assert [name for name, _, _ in calls if name != 'curator_runner'] == ['custodian', 'viewer', 'gateway', 'wake']


def test_without_a_curator_runner_nothing_is_created_and_the_launches_are_unchanged(tmp_path, monkeypatch):
    run, result, calls, _, _ = supervised_with_runner(tmp_path, monkeypatch, 'pass', configured=False)
    assert [name for name, _, _ in calls] == ['custodian', 'viewer', 'gateway', 'wake']
    assert 'curator_runner' not in result['children'] and 'curator_runner' not in result['cleanup']
    assert '--curator-runner-status' not in result['children']['viewer']['argv']
    assert not (run/'curator-read.lock').exists() and not (run/'curator-runner').exists()


def test_a_real_curator_runner_process_exits_promptly_on_sigterm(tmp_path):
    runtime = tmp_path/'runtime'
    run = tmp_path/'run'
    run.mkdir()
    (run/'curator-read.lock').touch()  # a reader is configured; the store does not exist yet
    config = tmp_path/'runner.json'
    config.write_text(json.dumps(dict(schema='curator-runner-config/2', knowledge_root=str(runtime/'knowledge'/'live'),
                                      arm='terra', cap_usd='1', upstream='http://127.0.0.1:9', poll_seconds=.2)))
    directory = run/'curator-runner'
    child = subprocess.Popen([sys.executable, '-m', 'tools.curator_host.live_runner', '--run', str(run), '--directory',
                              str(directory), '--config', str(config), '--runtime-root', str(runtime)],
                             cwd=guard.ROOT, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        end = time.monotonic() + 30
        while not (directory/'polls.jsonl').is_file():
            assert child.poll() is None, child.communicate()
            assert time.monotonic() < end
            time.sleep(.05)
        sent = time.monotonic()
        child.send_signal(signal.SIGTERM)
        assert child.wait(timeout=5) == 130
        assert time.monotonic() - sent < 5
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate()
    status = json.loads((directory/'status.json').read_text())
    assert status['state'] == 'ended' and status['stop_reason'] == 'interrupted'
    assert json.loads((directory/'polls.jsonl').read_text().splitlines()[0])['outcome'] == 'refused:no-store'
    assert not any((directory/'snapshots').iterdir())


@pytest.mark.parametrize('first', [b'pause:1.0:loop', b'{"port": 80}', b'[]', b'not json', None])
def test_gateway_startup_accepts_only_a_listening_port_announcement(tmp_path, monkeypatch, first):
    profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345)
    monkeypatch.setattr(guard, 'preflight', lambda _: (profile, {'api_key_env': 'WATCH_TEST_KEY'}, {}))
    monkeypatch.setenv('WATCH_TEST_KEY', 'synthetic-not-a-provider-key')
    (tmp_path/'manifest.json').write_text('{}')
    launched = []
    def launch(argv, **kwargs):
        if '--viewer-port' not in argv:
            command = [sys.executable, '-c', 'import time; time.sleep(20)']
        elif first is None:
            command = [sys.executable, '-c', 'pass']  # The gateway exits at once without announcing a port.
        else:
            code = ('import socket,sys,time; socket.socket(fileno=int(sys.argv[1])).send(sys.argv[2].encode()); '
                    'time.sleep(20)')
            command = [sys.executable, '-c', code, argv[argv.index('--viewer-port')-1], first.decode()]
        launched.append(subprocess.Popen(command, **kwargs))
        return launched[-1]
    supervised = []
    monkeypatch.setattr(guard, 'supervise', lambda *args, **kwargs: supervised.append(args) or 'custodian_terminal')
    result = guard.run_supervised(tmp_path, popen=launch, viewer_port=lambda: 54321)
    assert result['reason'] == 'launch_or_supervision_error' and not supervised
    assert result['gateway_url'] is None and 'pause_requested' not in result and result['pause_reason'] is None
    assert result['cleanup_verified'] and not result['terminal_coverage_verified']
    assert len(launched) == 4 and all(child.poll() is not None for child in launched)
    assert json.loads((tmp_path/'watch-terminal.json').read_text()) == result


@pytest.mark.parametrize('gateway_reports_dead', [False, True])
def test_a_gateway_that_closed_its_end_is_supervision_loss_never_a_pause(tmp_path, gateway_reports_dead):
    stops, peer = socket.socketpair(type=socket.SOCK_DGRAM)
    peer.close()  # Really closed: on macOS the guard's read then raises ConnectionResetError.
    live = SimpleNamespace(poll=lambda: None)
    polls = []
    def poll():
        polls.append(1)
        return 1 if gateway_reports_dead or len(polls) > 1 else None
    result = dict(started_wall=999, started_monotonic=time.monotonic())
    with stops:
        reason = guard.supervise(tmp_path, dict(session=SESSION, source_commit=COMMIT, wall_seconds=60),
                                 live, SimpleNamespace(poll=poll), live, stops, lambda: False, result)
    assert reason == 'supervision_lost' and 'pause_reason' not in result and 'pause_requested' not in result


def stops_case(message, tmp_path):
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    live = SimpleNamespace(poll=lambda: None)
    now = time.monotonic()
    result = dict(started_wall=999, started_monotonic=now-10)
    with stops, stop_sender:
        stop_sender.send(message.format(at=now-1).encode())
        stop_sender.send(b'pause-replied')
        reason = guard.supervise(tmp_path, dict(session=SESSION, source_commit=COMMIT, wall_seconds=100),
                                 live, live, live, stops, lambda: False, result)
    return reason, result


@pytest.mark.parametrize('reason', ['loop', 'fault', 'spend', 'other', 'unspecified'])
def test_guard_records_the_owner_pause_reason(tmp_path, reason):
    outcome, result = stops_case('pause:{at!r}:'+reason, tmp_path)
    assert outcome == 'operator_pause' and result['pause_reason'] == reason
    assert result['pause_reply_forwarded'] is True


@pytest.mark.parametrize('message, expected', [
    ('pause:{at!r}', 'invalid_pause_message'), ('pause:{at!r}:loop:x', 'invalid_pause_message'),
    ('pause:{at!r}:boredom', 'invalid_pause_reason'),
    ('pause:nan:loop', 'invalid_pause_clock'), ('pause:abc:loop', 'invalid_pause_clock'),
    ('resume:{at!r}:loop', 'invalid_pause_message'), ('{{"port": 12346}}', 'invalid_pause_message')])
def test_guard_refuses_unknown_or_malformed_pause_messages(tmp_path, message, expected):
    outcome, result = stops_case(message, tmp_path)
    assert outcome == expected and 'pause_reason' not in result


def test_guard_records_a_missing_pause_reason_as_unspecified(tmp_path):
    outcome, result = stops_case('pause:{at!r}:', tmp_path)
    assert outcome == 'operator_pause' and result['pause_reason'] == 'unspecified'
    assert result['pause_reply_forwarded'] is True


def test_terminal_before_start_and_ready_markers_never_certifies_coverage(tmp_path):
    (tmp_path/'receipt.json').write_text(json.dumps(receipt()))
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    result = dict(started_wall=999, started_monotonic=99)
    live = SimpleNamespace(poll=lambda: None)
    with stops, stop_sender:
        reason = guard.supervise(tmp_path, dict(session=SESSION, source_commit=COMMIT, wall_seconds=100),
            SimpleNamespace(poll=lambda: 0), live, live, stops, lambda: False, result)
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
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    live = SimpleNamespace(poll=lambda: None)
    with stops, stop_sender:
        actual = guard.supervise(tmp_path,
            dict(session=SESSION, source_commit=COMMIT, wall_seconds=100, port=12345),
            live, live, live, stops, lambda: False,
            dict(started_wall=999, started_monotonic=99),
            clock=SimpleNamespace(monotonic=lambda: 144.5, time=lambda: 1044.5))
    assert actual == reason


@pytest.mark.parametrize('lost', ['gateway', 'wake', 'signal'])
def test_guard_detects_independent_supervision_loss(tmp_path, lost):
    stops, stop_sender = socket.socketpair(type=socket.SOCK_DGRAM)
    live = SimpleNamespace(poll=lambda: None)
    dead = SimpleNamespace(poll=lambda: 1)
    with stops, stop_sender:
        reason = guard.supervise(tmp_path, dict(wall_seconds=60), live,
            dead if lost == 'gateway' else live, dead if lost == 'wake' else live,
            stops, lambda: lost == 'signal',
            dict(started_wall=999, started_monotonic=99))
    assert reason == 'supervision_lost'


@pytest.mark.parametrize('substitution', ['receipt', 'manifest', 'cleanup'])
def test_final_substitution_and_cleanup_failure_cannot_certify_success(tmp_path, monkeypatch, substitution):
    profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=12345)
    monkeypatch.setattr(guard, 'preflight', lambda _: (profile, {'api_key_env': 'WATCH_TEST_KEY'}, {}))
    monkeypatch.setenv('WATCH_TEST_KEY', 'synthetic-not-a-provider-key')
    (tmp_path/'manifest.json').write_text('{}')
    handles = []
    def launch(argv, **kwargs):
        if '--viewer-port' in argv:
            command = gateway_command(argv)
        else:
            command = [sys.executable, '-c', 'import time; time.sleep(20)']
        handle = subprocess.Popen(command, **kwargs); handles.append(handle)
        return handle
    def supervision(*args, **kwargs):
        result = args[7]
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
        if substitution == 'cleanup' and handle is handles[2]:
            raise PermissionError('synthetic denied cleanup verification after actual fixture cleanup')
        return actual
    monkeypatch.setattr(guard, 'close_group', close)
    result = guard.run_supervised(tmp_path, popen=launch)
    assert len(closed) == 4 and all(h.poll() is not None for h in handles)
    if substitution == 'cleanup':
        assert not result['cleanup_verified']
        assert result['cleanup']['gateway']['error'] == 'PermissionError'
        assert 'synthetic denied' in result['cleanup']['gateway']['error_traceback']
    else:
        assert not result['terminal_coverage_verified']
    if substitution == 'receipt':
        assert result['custodian_receipt']['source_commit'] == COMMIT
        assert not result['custodian_receipt_unchanged']
