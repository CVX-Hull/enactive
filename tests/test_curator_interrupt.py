"""Portable cancellation receipts and real loopback proxy closure; no provider calls."""
from __future__ import annotations

from decimal import Decimal
import fcntl
import json
import socket
from types import SimpleNamespace

import pytest

from harness.curator import session
from harness.curator.knowledge import Repository
from harness.curator.proxy import ModelProxy
from tests.test_curator_host import KEY, PRICES, host_config, synthetic_evidence
from tests.test_trace_projection import make_session
from tools.curator_host import shadow


def test_workspace_cleanup_does_not_require_a_fileflags_api(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    workspace.mkdir()
    owned = workspace/'readonly'
    owned.write_text('fixture')
    owned.chmod(0o400)
    monkeypatch.delattr(session.os, 'chflags', raising=False)
    session._remove(workspace)
    assert not workspace.exists()


@pytest.mark.parametrize('phase', ['prepare', 'run'])
def test_interruption_seals_abort_and_reraises_before_workspace_and_lock_cleanup(tmp_path, monkeypatch, phase):
    repo = Repository(tmp_path/'knowledge', 'testgame')
    trace = make_session(tmp_path/'evidence')
    interrupt = KeyboardInterrupt('operator cancelled')

    def stop(*args, **kwargs):
        interrupt.add_note('Sandbox cleanup failed: process-tree/OSError')
        raise interrupt

    monkeypatch.setattr(session if phase == 'prepare' else session.sandbox, 'project' if phase == 'prepare' else 'run', stop)
    with pytest.raises(KeyboardInterrupt) as caught:
        session.run_session(repo, [trace], session.SessionConfig(argv=('never-run',)), session_id='interrupted')
    assert caught.value is interrupt
    record = json.loads((repo.state/'sessions/interrupted/close-out.json').read_text())
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and life['returncode'] is None and life['survivors'] is None
    assert any('KeyboardInterrupt' in error for error in life['errors'])
    assert 'Sandbox cleanup failed: process-tree/OSError' in life['errors']
    assert record['verdicts'] == [] and repo.published() == 'v0'
    assert not any((repo.state/'workspaces').iterdir())
    with (repo.state/'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(lock, fcntl.LOCK_UN)


def test_failed_interruption_closeout_preserves_the_interrupt_and_failure_receipt(tmp_path, monkeypatch):
    repo = Repository(tmp_path/'knowledge', 'testgame')
    trace = make_session(tmp_path/'evidence')
    interrupt = KeyboardInterrupt('operator cancelled')

    def stop(*args, **kwargs):
        raise interrupt

    def fail(*args, **kwargs):
        raise OSError('cannot write close-out')

    monkeypatch.setattr(session.sandbox, 'run', stop)
    monkeypatch.setattr(session, '_close_out', fail)
    with pytest.raises(KeyboardInterrupt) as caught:
        session.run_session(repo, [trace], session.SessionConfig(argv=('never-run',)), session_id='interrupted')
    assert caught.value is interrupt
    failure = json.loads((repo.state/'sessions/interrupted/close-out-failed.json').read_text())
    assert failure == {'interrupted': True, 'error': 'OSError'}
    assert not any((repo.state/'workspaces').iterdir())


@pytest.mark.parametrize('phase', ['prepare', 'configure', 'run', 'success', 'shutdown'])
def test_proxy_listener_is_closed_after_preparation_failure_or_interruption(tmp_path, monkeypatch, phase):
    repo = Repository(tmp_path/'knowledge', 'testgame')
    repo.ensure()
    trace = make_session(tmp_path/'evidence')
    model, config, directory = host_config(tmp_path)
    proxies = []

    def proxy(**kwargs):
        value = ModelProxy(**kwargs)
        proxies.append(value)
        if phase == 'shutdown':
            close = value.close

            def fail_after_close():
                close()
                raise OSError('shutdown receipt failure')

            value.close = fail_after_close
        return value

    def stop(*args, **kwargs):
        raise KeyboardInterrupt('operator cancelled')

    def fail(*args, **kwargs):
        raise OSError('configuration write failed')

    monkeypatch.setattr(shadow, 'ModelProxy', proxy)
    monkeypatch.setattr(shadow, 'host_argv', lambda *args: ('never-run',))
    monkeypatch.setattr(shadow, 'host_identity', fail if phase == 'configure' else lambda *args: {'name': 'fixture'})
    monkeypatch.setattr(shadow, 'run_session', session.run_session if phase == 'success' else stop)
    if phase == 'success':
        monkeypatch.setattr(session.sandbox, 'run', lambda *args, **kw: session.sandbox.Result(0, None, 0, 0, 0., []))
    if phase == 'prepare':
        monkeypatch.setattr(shadow, '_write', fail)
    try:
        def run():
            return shadow.run_one(arm_name='terra', lineage='syn', name='one', trace=trace, repo=repo,
                                  memory=None, memory_note='fixture', host={'roots': (), 'env': {}},
                                  config_path=config, config_dir=directory, model_config=model, prices=PRICES,
                                  key=KEY, upstream='http://127.0.0.1:9', cap=Decimal(1), out=tmp_path/'out',
                                  wall_seconds=10, max_output_tokens=4096)

        if phase in ('configure', 'success'):
            summary = run()
            assert summary['run_state'].startswith('error:') if phase == 'configure' else summary['session_state'] == 'sealed'
            assert summary['proxy']['revoked'] is False  # listener shutdown must not become a session incident
        else:
            with pytest.raises(OSError if phase == 'prepare' else KeyboardInterrupt):
                run()
        assert proxies
        for value in proxies:
            if phase == 'prepare':
                assert value._server is None  # preparation now completes before acquiring the listener
            else:
                assert value._server is not None
                assert not value._thread.is_alive()
                with pytest.raises(OSError):
                    socket.create_connection(value._server.server_address, timeout=.2)
        if phase == 'shutdown':
            assert json.loads((tmp_path/'out/syn/one/cleanup-failed.json').read_text()) == {'error': 'OSError'}
    finally:
        for value in proxies:
            if value._server is not None:
                ModelProxy.close(value)


@pytest.mark.parametrize(('settled', 'survivors', 'expected'), [
    (False, [], 'proxy-unsettled'),
    (True, None, 'cleanup-unconfirmed'),
    (True, [12345], 'cleanup-unconfirmed'),
])
def test_generic_shadow_stops_on_incomplete_accounting_or_cleanup_without_optional_flag(tmp_path, monkeypatch, settled, survivors, expected):
    evidence = synthetic_evidence(tmp_path, names=('sd1a1', 'sd1a2'))
    runtime = tmp_path/'runtime'
    out = runtime/'curator-shadow/unsettled'
    calls = []

    def unsettled(**kwargs):
        calls.append(kwargs['name'])
        return dict(run_state='completed', session_state='sealed' if survivors == [] else 'aborted', cost_usd='.001', requests=1,
                    accepted=0, rejected=0, stopped_by_cap=False,
                    proxy=dict(revoked=False, breaches=0, settled=settled), sandbox=dict(survivors=survivors))

    monkeypatch.setattr(shadow, 'host_tools', lambda: {})
    monkeypatch.setattr(shadow, 'host_identity', lambda *args: {'name': 'fixture'})
    monkeypatch.setattr(shadow, 'run_one', unsettled)
    args = shadow.parser().parse_args(['--arm', 'terra', '--lineage', '397', '--sessions', 'sd1a1', 'sd1a2',
                                      '--cap-usd', '1', '--runtime-root', str(runtime), '--out', str(out),
                                      '--evidence-root', str(evidence)])
    assert not args.stop_on_abort
    run = shadow.run_shadow(args, KEY)
    assert calls == ['sd1a1'] and run['stopped'] == expected and not run['complete']


@pytest.fixture
def synthetic_sandbox(tmp_path, monkeypatch):
    workspace, home = tmp_path/'workspace', tmp_path/'home'
    workspace.mkdir()
    home.mkdir()
    scratch = workspace/'scratch'
    scratch.mkdir()
    child = SimpleNamespace(pid=12345, poll=lambda: None, returncode=0)
    monkeypatch.setattr(session.sandbox.subprocess, 'Popen', lambda *args, **kwargs: child)
    monkeypatch.setattr(session.sandbox, '_user_processes', lambda: 1)
    monkeypatch.setattr(session.sandbox, '_tree', lambda pid: {pid: 0})
    monkeypatch.setattr(session.sandbox, '_disk', lambda paths: 0)
    return session.sandbox.Layout(workspace=workspace, home=home, writable=(scratch,)), child


@pytest.mark.parametrize('phase', ['process-tree', 'profile'])
def test_native_cleanup_failures_cannot_replace_a_pending_interrupt(synthetic_sandbox, monkeypatch, phase):
    layout, _child = synthetic_sandbox
    interrupt = KeyboardInterrupt('operator cancelled')
    unlinked = []
    unlink = session.sandbox.os.unlink

    def stop(seconds):
        raise interrupt

    def close(child):
        if phase == 'process-tree':
            raise OSError('fixture tree cleanup failure')
        return []

    def remove(path):
        unlinked.append(path)
        if phase == 'profile':
            raise OSError('fixture profile cleanup failure')
        unlink(path)

    monkeypatch.setattr(session.sandbox.time, 'sleep', stop)
    monkeypatch.setattr(session.sandbox, '_close', close)
    monkeypatch.setattr(session.sandbox.os, 'unlink', remove)
    with pytest.raises(KeyboardInterrupt) as caught:
        session.sandbox.run(['never-run'], layout)
    assert caught.value is interrupt and unlinked
    assert f'Sandbox cleanup failed: {phase}/OSError' in interrupt.__notes__


def test_a_callers_handled_exception_does_not_hide_a_new_cleanup_failure(synthetic_sandbox, monkeypatch):
    layout, child = synthetic_sandbox
    child.poll = lambda: 0

    def fail(child):
        raise OSError('fixture tree cleanup failure')

    monkeypatch.setattr(session.sandbox, '_close', fail)
    try:
        raise ValueError('already handled by caller')
    except ValueError:
        with pytest.raises(OSError, match='tree cleanup failure'):
            session.sandbox.run(['never-run'], layout)


@pytest.mark.parametrize('grooming_fails', [False, True], ids=['all-groomed', 'grooming-failure-stops'])
def test_grooming_alternates_with_admissions_and_shares_the_run_cap(tmp_path, monkeypatch, grooming_fails):
    # #618: --groom runs a grooming session after each admission that publishes, each session's cap is what the run
    # has left, every session's cost counts toward the run, and a grooming that stops the run stops later admissions.
    evidence = synthetic_evidence(tmp_path, names=('sd1a1', 'sd1a2', 'sd1a3'))
    runtime = tmp_path/'runtime'
    out = runtime/'curator-shadow/groomed'
    calls = []
    versions = iter(range(1, 100))

    def fake(**kwargs):
        calls.append((kwargs['name'], kwargs['session_kind'], kwargs['cap']))
        kind = kwargs['session_kind']
        published = kwargs['name'] != 'sd1a2'  # the second admission publishes nothing
        before = 'v0'
        after = f'v{next(versions)}' if published else before
        survivors = [99] if grooming_fails and kind == 'grooming' else []
        return dict(run_state='completed', session_state='sealed', cost_usd='0.25', requests=1, accepted=int(published),
                    rejected=0, stopped_by_cap=False, published_before=before, published_after=after,
                    proxy=dict(revoked=False, breaches=0, settled=True), sandbox=dict(survivors=survivors))

    monkeypatch.setattr(shadow, 'host_tools', lambda: {})
    monkeypatch.setattr(shadow, 'host_identity', lambda *args: {'name': 'fixture'})
    monkeypatch.setattr(shadow, 'run_one', fake)
    args = shadow.parser().parse_args(['--arm', 'terra', '--lineage', '397', '--sessions', 'sd1a1', 'sd1a2', 'sd1a3', '--groom',
                                      '--cap-usd', '2', '--runtime-root', str(runtime), '--out', str(out),
                                      '--evidence-root', str(evidence)])
    run = shadow.run_shadow(args, KEY)
    if grooming_fails:
        assert [(n, k) for n, k, _ in calls] == [('sd1a1', 'admission'), ('sd1a1-grooming', 'grooming')]
        assert run['stopped'] == 'cleanup-unconfirmed' and not run['complete']
        return
    assert [(n, k, str(c)) for n, k, c in calls] == [
        ('sd1a1', 'admission', '2.0'), ('sd1a1-grooming', 'grooming', '1.75'), ('sd1a2', 'admission', '1.50'),
        ('sd1a3', 'admission', '1.25'), ('sd1a3-grooming', 'grooming', '1.00')]
    assert run['grooming_skipped'] == [dict(after='sd1a2', reason='the admission published nothing')]
    assert run['total_cost_usd'] == '1.25' and run['sessions_run'] == 5 and run['complete'] is True


def test_a_capped_grooming_is_rerun_alone_with_twice_the_cap(tmp_path, monkeypatch):
    # #618's stop rule: a session that reaches its cap is re-run once with twice the cap. For a grooming session that
    # is --groom-only on the existing repository; the admission is not paid for again.
    evidence = synthetic_evidence(tmp_path, names=('sd1a1',))
    runtime = tmp_path/'runtime'
    knowledge = runtime/'knowledge'/'shadow-454'/'first'/'terra'/'397'
    (knowledge/shadow.GAME/'.git').mkdir(parents=True)
    calls = []

    def fake(**kwargs):
        calls.append((kwargs['name'], kwargs['session_kind'], str(kwargs['cap'])))
        return dict(run_state='completed', session_state='sealed', cost_usd='0.1', requests=1, accepted=1, rejected=0,
                    stopped_by_cap=False, published_before='v1', published_after='v2',
                    proxy=dict(revoked=False, breaches=0, settled=True), sandbox=dict(survivors=[]))

    monkeypatch.setattr(shadow, 'host_tools', lambda: {})
    monkeypatch.setattr(shadow, 'host_identity', lambda *args: {'name': 'fixture'})
    monkeypatch.setattr(shadow, 'run_one', fake)
    monkeypatch.setattr(shadow, 'Repository', lambda path, game: SimpleNamespace(ensure=lambda: None, published=lambda: 'v1',
                                                                                 path=path/game))
    base = ['--arm', 'terra', '--lineage', '397', '--sessions', 'sd1a1', '--cap-usd', '5', '--session-cap-usd', '1',
            '--runtime-root', str(runtime), '--evidence-root', str(evidence)]
    args = shadow.parser().parse_args([*base, '--groom-only', '--double-session-cap', '--knowledge-root', str(knowledge),
                                      '--out', str(runtime/'curator-shadow'/'regroom')])
    run = shadow.run_shadow(args, KEY)
    assert calls == [('sd1a1-grooming', 'grooming', '2.0')] and run['complete'] is True and run['groom_only'] is True
    for extra, out in ((['--groom', '--double-session-cap'], 'a'), (['--groom-only'], 'b'),
                       (['--groom-only', '--groom', '--knowledge-root', str(knowledge)], 'c')):
        with pytest.raises(shadow.ShadowError):
            shadow.run_shadow(shadow.parser().parse_args([*base, *extra, '--out', str(runtime/'curator-shadow'/out)]), KEY)


def test_a_grooming_that_reaches_its_cap_stops_the_run(tmp_path, monkeypatch):
    evidence = synthetic_evidence(tmp_path, names=('sd1a1', 'sd1a2'))
    runtime = tmp_path/'runtime'
    calls = []

    def fake(**kwargs):
        calls.append(kwargs['name'])
        grooming = kwargs['session_kind'] == 'grooming'
        return dict(run_state='completed', session_state='sealed', cost_usd='0.1', requests=1, accepted=1, rejected=0,
                    stopped_by_cap=grooming, published_before='v0', published_after='v1',
                    proxy=dict(revoked=False, breaches=0, settled=True), sandbox=dict(survivors=[]))

    monkeypatch.setattr(shadow, 'host_tools', lambda: {})
    monkeypatch.setattr(shadow, 'host_identity', lambda *args: {'name': 'fixture'})
    monkeypatch.setattr(shadow, 'run_one', fake)
    args = shadow.parser().parse_args(['--arm', 'terra', '--lineage', '397', '--sessions', 'sd1a1', 'sd1a2', '--groom',
                                      '--cap-usd', '5', '--runtime-root', str(runtime), '--evidence-root', str(evidence),
                                      '--out', str(runtime/'curator-shadow'/'capped')])
    run = shadow.run_shadow(args, KEY)
    assert calls == ['sd1a1', 'sd1a1-grooming'] and run['stopped'] == 'cap-reached' and run['complete'] is False
