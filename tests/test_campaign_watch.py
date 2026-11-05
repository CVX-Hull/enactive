"""Actual local socket/HTTP fixtures; no real native target or provider calls."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from harness.computer.launch import close_group
from tools import campaign_supervision as guard
from tools import campaign_watch as watch

ROOT = Path(__file__).resolve().parents[1]
SESSION = 'a'*32
COMMIT = 'b'*40
PNG = b'synthetic immutable source bytes'


def put(path, value):
    path.write_text(json.dumps(value))


@contextmanager
def fixture(tmp_path, *, ready_age=0, receiver_pid=None):
    state = dict(block=False, fetching=threading.Event(), unblock=threading.Event(), paused=False,
                 status_session=SESSION, native=None, reason=None, source_bytes=PNG)
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == '/api/status':
                value = dict(schema='computer-status/1', session=state['status_session'],
                    native_returncode=state['native'],
                    stop=dict(stop_requested=state['paused'], reason=state['reason']))
                data = json.dumps(value).encode()
            elif self.path.startswith('/api/source/'):
                state['fetching'].set()
                if state['block']:
                    state['unblock'].wait(3)
                data = state['source_bytes']
            else:
                data = b'<head></head><button id="pause">Pause</button><div class="frame-shell" id="watch-frame-shell"></div>'
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            state['paused'] = True
            data = json.dumps(dict(schema='computer-pause/1', session=SESSION,
                                   stop=dict(stop_requested=True))).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    serving = threading.Thread(target=server.serve_forever, daemon=True); serving.start()
    checks, tx = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_tx = socket.socketpair(type=socket.SOCK_DGRAM)
    wall, mono = time.time(), time.monotonic()
    (tmp_path/'manifest.json').write_text('{}')
    put(tmp_path/'watch-start.json', dict(schema='campaign-watch-start/1', session=SESSION,
        source_commit=COMMIT, manifest_sha256=sha256(b'{}').hexdigest(), watch_seconds=45,
        started_wall=wall-ready_age-.1, started_monotonic=mono-ready_age-.1))
    (tmp_path/'watch-attempts.jsonl').touch()
    put(tmp_path/'started.json', dict(schema='computer-start/1', session=SESSION,
        started_wall=wall-ready_age-.1, deadline_monotonic=mono-ready_age-.1+60))
    put(tmp_path/'ready.json', dict(schema='computer-ready/1', session=SESSION, pid=123,
        ready_wall=wall-ready_age, viewer_url=f'http://127.0.0.1:{server.server_port}/'))
    process = subprocess.Popen([sys.executable, '-m', 'tools.campaign_watch', str(tmp_path), SESSION,
        COMMIT, str(server.server_port), str(os.getpid() if receiver_pid is None else receiver_pid),
        str(tx.fileno()), str(stop_tx.fileno())], cwd=ROOT, pass_fds=(tx.fileno(), stop_tx.fileno()),
        start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    tx.close(); stop_tx.close()
    try:
        assert select.select([checks], [], [], 5)[0], 'gateway failed to establish local fixture'
        port = json.loads(checks.recv(4096))['port']
        profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=server.server_port)
        result = dict(accepted=[], started_wall=wall-ready_age-.1,
                      started_monotonic=mono-ready_age-.1, gateway_url=f'http://127.0.0.1:{port}/')
        live = SimpleNamespace(poll=lambda: None)
        def supervise(child=live):
            result['reason'] = guard.supervise(tmp_path, profile, child, process, live,
                                              checks, stops, lambda: False, result)
        def call(path, form=None, origin=True):
            connection = HTTPConnection('127.0.0.1', port, timeout=5)
            try:
                headers = {'Content-Type': 'application/json'}
                if origin:
                    headers['Origin'] = f'http://127.0.0.1:{port}'
                connection.request('GET' if form is None else 'POST', path,
                                   None if form is None else json.dumps(form), headers)
                response = connection.getresponse()
                return response.status, response.read()
            finally:
                connection.close()
        yield SimpleNamespace(state=state, call=call, supervise=supervise, result=result,
                              checks=checks, stops=stops, process=process, port=port, profile=profile)
    finally:
        state['unblock'].set()
        close_group(process)
        server.shutdown(); server.server_close(); serving.join(2)
        checks.close(); stops.close()
        stdout, stderr = process.communicate(timeout=2)
        assert process.returncode is not None, (stdout, stderr)


def form(sequence=1, **changes):
    value = dict(session=SESSION, sequence=sequence, observed=datetime.now(timezone.utc).isoformat(),
                 source=SESSION+'-91', sha256=sha256(PNG).hexdigest())
    value.update(changes)
    return value


def test_gateway_rejects_stale_wrong_source_session_digest_and_origin(tmp_path):
    with fixture(tmp_path) as f:
        assert f.call('/api/tool', {})[0] == 403
        assert f.call('/record', form(), origin=False)[0] == 403
        bad = [dict(session='other'), dict(sequence=2), dict(source='other-1'), dict(sha256='0'*64),
               dict(observed=(datetime.now(timezone.utc)-timedelta(seconds=13)).isoformat())]
        for change in bad:
            assert f.call('/record', form(**change))[0] == 409
        f.state['status_session'] = 'other'
        assert f.call('/record', form())[0] == 409
        assert (tmp_path/'watch-attempts.jsonl').read_text() == ''
        code, page = f.call('/')
        assert code == 200 and page.index(b'id="pause"') < page.index(b'id="watch-record"')


def test_completed_checks_duplicate_rejection_ending_and_pause(tmp_path):
    with fixture(tmp_path) as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        assert f.call('/record', form())[0] == 200
        assert f.call('/record', form())[0] == 409
        f.state.update(native=0, paused=True, reason=watch.NORMAL_EOF)
        assert f.call('/record', form(2))[0] == 200
        f.state.update(native=None, paused=False, reason=None)
        assert f.call('/record', form(3))[0] == 409
        # Exact receiver is this fixture server's process, rather than retained JSON.
        put(tmp_path/'launcher-process.json', dict(pid=1, session='substituted'))
        pause_code = f.call('/api/pause', {})[0]
        assert pause_code == (200 if sys.platform == 'darwin' else 409)
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert f.result.get('pause_reply_forwarded', False) == (sys.platform == 'darwin')
        assert f.state['paused'] == (sys.platform == 'darwin')
        assert [r['phase'] for r in f.result['accepted']] == ['active', 'ending']
        assert f.call('/record', form(3))[0] == 409


def test_uncertain_receiver_never_receives_pause_post(tmp_path):
    with fixture(tmp_path, receiver_pid=1) as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        assert f.call('/api/pause', {})[0] == 409
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert not f.result.get('pause_reply_forwarded', False) and not f.state['paused']


def test_blocked_http_cannot_delay_first_check_deadline(tmp_path):
    with fixture(tmp_path, ready_age=44.5) as f:
        f.state['block'] = True
        outcome = []
        request = threading.Thread(target=lambda: outcome.append(f.call('/record', form())[0]))
        thread = threading.Thread(target=f.supervise); thread.start(); request.start()
        assert f.state['fetching'].wait(1)
        thread.join(2)
        assert not thread.is_alive() and f.result['reason'] == 'watch_deadline'
        assert f.result['accepted'] == []
        f.state['unblock'].set()
        # The worker can complete its attempt after the guard has already stopped;
        # its missing confirmation is not a renewal.
        request.join(6)
        assert outcome == [409]


def test_partial_or_mismatched_guard_ack_is_never_reported_as_accepted(tmp_path):
    with fixture(tmp_path) as f:
        outcome = []
        request = threading.Thread(target=lambda: outcome.append(f.call('/record', form())[0])); request.start()
        assert select.select([f.checks], [], [], 2)[0]
        attempt = json.loads(f.checks.recv(4096))
        assert attempt['schema'] == 'campaign-watch-attempt/1'
        f.checks.send(b'accepted:1:partial')
        request.join(2)
        assert outcome == [409]
        assert f.stops.recv(128) == b'ack-uncertain'
        assert f.call('/record', form())[0] == 409


def test_guard_accepts_generic_terminal_without_claiming_normal_native_exit(tmp_path):
    with fixture(tmp_path) as f:
        ended = threading.Event()
        child = SimpleNamespace(poll=lambda: 0 if ended.is_set() else None)
        thread = threading.Thread(target=lambda: f.supervise(child)); thread.start()
        assert f.call('/record', form())[0] == 200
        ending_wall = time.time()
        report = dict(schema='campaign-receipt/3', session=SESSION, source_commit=COMMIT,
            started_wall=f.result['started_wall'], ended_wall=ending_wall,
            elapsed_seconds=ending_wall-f.result['started_wall'],
            outcome='player_external_stop_complete_unassessed', normal_save_claimed_by_harness=False,
            native_absence_verified=True, deciding_hosts_quiescent=True, input_authority_revoked=True,
            cleanup=dict(schema='computer-cleanup/1', session=SESSION, native_absence_verified=True,
                normal_native_exit_zero=False,
                native=dict(pid=123, pgid=123, returncode=-15, process_absent=True, group_absent=True)))
        put(tmp_path/'receipt.json', report); ended.set()
        thread.join(2)
        assert not thread.is_alive() and f.result['reason'] == 'custodian_terminal'
        assert f.result['terminal_coverage_verified']
        assert f.result['custodian_receipt']['normal_save_claimed_by_harness'] is False
        assert f.result['custodian_receipt']['cleanup']['normal_native_exit_zero'] is False


@pytest.mark.parametrize('marker', ['started.json', 'ready.json'])
@pytest.mark.parametrize('delay_confirmation', [False, True])
def test_current_marker_writer_can_finish_after_exposing_its_path(tmp_path, marker, delay_confirmation):
    with fixture(tmp_path) as f:
        path = tmp_path/marker
        payload = path.read_text()
        path.unlink()  # Only this synthetic fixture, before the guard starts.
        forwarded, release = threading.Event(), threading.Event()
        errors = []
        class DelayedConfirmation:
            def fileno(self):return f.checks.fileno()
            def setblocking(self, value):f.checks.setblocking(value)
            def recv(self, size):return f.checks.recv(size)
            def send(self, data):
                count = f.checks.send(data)
                forwarded.set()
                if not release.wait(3):raise TimeoutError('Fixture did not release confirmation completion')
                return count
        def supervise():
            try:
                live = SimpleNamespace(poll=lambda: None)
                f.result['reason'] = guard.supervise(tmp_path, f.profile, live, f.process, live,
                    DelayedConfirmation() if delay_confirmation else f.checks,
                    f.stops, lambda: False, f.result)
            except BaseException as exc:
                errors.append(repr(exc))
        thread = threading.Thread(target=supervise)
        pause = None
        try:
            with path.open('x') as writer:
                # Match the real producers' visible pathname before buffered close.
                thread.start()
                threading.Event().wait(.15)
                assert thread.is_alive() and 'reason' not in f.result
                writer.write(payload)
            response = f.call('/record', form())
            assert response[0] == 200, (response, f.result)
            assert json.loads(response[1])['accepted'] == 1
            if delay_confirmation:
                # HTTP success can precede the guardian's post-send sample.
                # The worker can reply after receiving bytes, before the sender
                # resumes to publish its fixture barrier. Synchronize on that
                # barrier before checking the deliberately held completion.
                assert forwarded.wait(2), 'Guard did not enter the confirmation barrier'
                assert not f.result['accepted']
                pause = threading.Thread(target=lambda: f.call('/api/pause', {}))
                pause.start()
                assert select.select([f.stops], [], [], 2)[0], 'Pause was not queued'
                release.set()
            else:
                f.call('/api/pause', {})
            thread.join(3)
            if pause is not None:pause.join(3)
            assert not thread.is_alive() and not errors and f.result['reason'] == 'operator_pause'
            raced = f.result.get('checks_raced_with_pause', [])
            assert [r['sequence'] for r in f.result['accepted']+raced] == [1]
            assert all(r['receipt'] < f.result['pause_requested'] for r in f.result['accepted'])
            assert all(r['receipt'] >= f.result['pause_requested'] for r in raced)
            if delay_confirmation:
                assert not pause.is_alive() and not f.result['accepted'] and len(raced) == 1
        finally:
            release.set()
            if thread.is_alive() and pause is None:
                f.call('/api/pause', {})
            thread.join(3)
            if pause is not None:pause.join(3)


def test_ui_behavior_is_included_in_python_suite():
    result = subprocess.run([shutil.which('node') or 'node', '--test', str(ROOT/'tests/test_campaign_watch.cjs')],
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout+result.stderr


def test_receiver_check_binds_exact_connected_socket_and_handle_pid(monkeypatch):
    called = []
    connection = SimpleNamespace(sock=SimpleNamespace(getsockname=lambda: ('127.0.0.1', 56789)),
                                 connect=lambda: called.append('connected'))
    def sample(argv, **kwargs):
        assert called == ['connected']
        assert argv[argv.index('-p')+1] == '1234'
        return SimpleNamespace(returncode=0, stdout='p1234\nn127.0.0.1:12345->127.0.0.1:56789\n')
    monkeypatch.setattr(watch.subprocess, 'run', sample)
    watch.bind_pause_receiver(connection, 12345, 1234)
    called.clear()
    with pytest.raises(ValueError, match='did not own'):
        watch.bind_pause_receiver(connection, 12346, 1234)
