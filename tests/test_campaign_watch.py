"""Actual local socket/HTTP fixtures; no real native target or provider calls."""
from contextlib import contextmanager
from hashlib import sha256
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import signal
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
INDEX = (b'<html><head></head><body><button id="pause">Pause</button>'
         b'<div class="frame-shell"></div></body></html>')
VIEWER_SCRIPT = (
    'import http.server,sys\n'
    'class H(http.server.BaseHTTPRequestHandler):\n'
    '    def log_message(self,*a):pass\n'
    '    def do_GET(self):\n'
    '        d=b\'{"schema":"spectator-view/1"}\'\n'
    '        self.send_response(200);self.send_header("Content-Type","application/json")\n'
    '        self.send_header("Content-Length",str(len(d)));self.end_headers();self.wfile.write(d)\n'
    'http.server.ThreadingHTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()\n')


def unused_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def put(path, value):
    path.write_text(json.dumps(value))


@contextmanager
def fixture(tmp_path, *, receiver_pid=None, viewer='thread'):
    state = dict(block=False, fetching=threading.Event(), unblock=threading.Event(), paused=False,
                 status_session=SESSION, native=None, reason=None, source_bytes=PNG, pause_body=None,
                 view=dict(status=200, media='application/json', body=b'{"schema":"spectator-view/1"}',
                           declared=None, delay=0, paths=[]))
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
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            state['paused'] = True
            state['pause_body'] = self.rfile.read(int(self.headers['Content-Length']))
            data = json.dumps(dict(schema='computer-pause/1', session=SESSION,
                                   stop=dict(stop_requested=True))).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers()
            self.wfile.write(data)

    class Viewer(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            view = state['view']
            view['paths'].append(self.path)
            time.sleep(view['delay'])
            body = view['body']
            try:
                if view.get('trickle'):
                    self.send_response(200); self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', '100'); self.end_headers()
                    for _ in range(100):
                        self.wfile.write(b' '); self.wfile.flush(); time.sleep(.1)
                    return
                self.send_response(view['status'])
                self.send_header('Content-Type', view['media'])
                self.send_header('Content-Length', str(len(body) if view['declared'] is None else view['declared']))
                self.send_header('Content-Security-Policy', "default-src *; script-src 'unsafe-inline'")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    serving = threading.Thread(target=server.serve_forever, daemon=True); serving.start()
    web = tmp_path/'web'
    (web/'app').mkdir(parents=True); (web/'vendor').mkdir(); (web/'private').mkdir()
    (web/'index.html').write_bytes(INDEX)
    (web/'app'/'main.js').write_text('export const ready = true;')
    (web/'app'/'style.css').write_text('body{margin:0}')
    (web/'vendor'/'chart.js').write_text('/* vendored */')
    (web/'app'/'notes.txt').write_text('not a served type')
    (web/'private'/'secret.js').write_text('not under app or vendor')
    (tmp_path/'outside.js').write_text('outside the web root')
    (web/'app'/'link.js').symlink_to(tmp_path/'outside.js')
    viewing = viewer_process = None
    if viewer == 'process':
        port_of_viewer = unused_port()
        viewer_process = subprocess.Popen([sys.executable, '-c', VIEWER_SCRIPT, str(port_of_viewer)],
                                          start_new_session=True)
    elif viewer == 'thread':
        viewing = ThreadingHTTPServer(('127.0.0.1', 0), Viewer)
        threading.Thread(target=viewing.serve_forever, daemon=True).start()
        port_of_viewer = viewing.server_port
    else:
        port_of_viewer = unused_port()
    stops, stop_tx = socket.socketpair(type=socket.SOCK_DGRAM)
    wall, mono = time.time(), time.monotonic()
    (tmp_path/'manifest.json').write_text('{}')
    put(tmp_path/'watch-start.json', dict(schema='campaign-watch-start/4', session=SESSION,
        source_commit=COMMIT, manifest_sha256=sha256(b'{}').hexdigest(), viewer_port=port_of_viewer,
        started_wall=wall-.1, started_monotonic=mono-.1))
    put(tmp_path/'started.json', dict(schema='computer-start/1', session=SESSION,
        started_wall=wall-.1, deadline_monotonic=mono-.1+60))
    put(tmp_path/'ready.json', dict(schema='computer-ready/1', session=SESSION, pid=123,
        ready_wall=wall, viewer_url=f'http://127.0.0.1:{server.server_port}/'))
    process = subprocess.Popen([sys.executable, '-m', 'tools.campaign_watch', str(tmp_path), SESSION,
        COMMIT, str(server.server_port), str(os.getpid() if receiver_pid is None else receiver_pid),
        str(stop_tx.fileno()), '--viewer-port', str(port_of_viewer), '--web-root', str(web)],
        cwd=ROOT, pass_fds=(stop_tx.fileno(),),
        start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stop_tx.close()
    try:
        assert select.select([stops], [], [], 5)[0], 'gateway failed to establish local fixture'
        port = json.loads(stops.recv(4096))['port']
        profile = dict(session=SESSION, source_commit=COMMIT, wall_seconds=60, port=server.server_port)
        result = dict(started_wall=wall-.1, started_monotonic=mono-.1, gateway_url=f'http://127.0.0.1:{port}/')
        live = SimpleNamespace(poll=lambda: None)
        def supervise(child=live):
            result['reason'] = guard.supervise(tmp_path, profile, child, process, live,
                                              stops, lambda: False, result)
        def reply(path, form=None, origin=True):
            connection = HTTPConnection('127.0.0.1', port, timeout=8)
            try:
                headers = {'Content-Type': 'application/json'}
                if origin:
                    headers['Origin'] = f'http://127.0.0.1:{port}'
                connection.request('GET' if form is None else 'POST', path,
                                   None if form is None else json.dumps(form), headers)
                response = connection.getresponse()
                return response, response.read()
            finally:
                connection.close()
        def call(path, form=None, origin=True):
            response, data = reply(path, form, origin)
            return response.status, data
        yield SimpleNamespace(state=state, call=call, reply=reply, supervise=supervise, result=result,
                              stops=stops, process=process, port=port, profile=profile,
                              viewer_process=viewer_process, web=web)
    finally:
        state['unblock'].set()
        close_group(process)
        if viewer_process is not None:
            close_group(viewer_process)
        if viewing is not None:
            viewing.shutdown(); viewing.server_close()
        server.shutdown(); server.server_close(); serving.join(2)
        stops.close()
        stdout, stderr = process.communicate(timeout=2)
        assert process.returncode is not None, (stdout, stderr)


def test_gateway_serves_the_page_unchanged_and_accepts_no_mutation_but_pause(tmp_path):
    with fixture(tmp_path) as f:
        code, page = f.call('/')
        assert code == 200 and page == INDEX
        for path in ('/api/tool', '/record', '/api/status', '/'):
            assert f.call(path, {})[0] == 403, path
        assert f.call('/api/pause', {'reason': 'other'}, origin=False)[0] == 403
        assert f.call('/campaign_watch_ui.js')[0] == 404
        assert not f.state['paused'] and not select.select([f.stops], [], [], 0)[0]
        assert sorted(path.name for path in tmp_path.iterdir() if path.name.startswith('watch-')) == ['watch-start.json']


def test_pause_binds_the_exact_receiver_rather_than_retained_json(tmp_path):
    with fixture(tmp_path) as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        # Exact receiver is this fixture server's process, rather than retained JSON.
        put(tmp_path/'launcher-process.json', dict(pid=1, session='substituted'))
        pause_code = f.call('/api/pause', {'reason': 'other'})[0]
        assert pause_code == (200 if sys.platform == 'darwin' else 409)
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert f.result.get('pause_reply_forwarded', False) == (sys.platform == 'darwin')
        assert f.state['paused'] == (sys.platform == 'darwin')


def test_uncertain_receiver_never_receives_pause_post(tmp_path):
    with fixture(tmp_path, receiver_pid=1) as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        assert f.call('/api/pause', {'reason': 'other'})[0] == 409
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert not f.result.get('pause_reply_forwarded', False) and not f.state['paused']


def test_blocked_source_read_cannot_delay_pause(tmp_path):
    with fixture(tmp_path) as f:
        f.state['block'] = True
        outcome = []
        request = threading.Thread(target=lambda: outcome.append(f.call('/api/source/'+SESSION+'-91')[0]))
        thread = threading.Thread(target=f.supervise); thread.start(); request.start()
        assert f.state['fetching'].wait(1)
        began = time.monotonic()
        assert f.call('/api/pause', {'reason': 'fault'})[0] == (200 if sys.platform == 'darwin' else 409)
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert time.monotonic()-began < 1.5 and request.is_alive()
        f.state['unblock'].set()
        request.join(6)
        assert outcome == [200]


def wait_ready(f):
    deadline = time.monotonic() + 5
    while 'ready_monotonic' not in f.result and time.monotonic() < deadline:
        time.sleep(.01)
    assert 'ready_monotonic' in f.result


def test_guard_accepts_generic_terminal_without_claiming_normal_native_exit(tmp_path):
    with fixture(tmp_path) as f:
        ended = threading.Event()
        child = SimpleNamespace(poll=lambda: 0 if ended.is_set() else None)
        thread = threading.Thread(target=lambda: f.supervise(child)); thread.start()
        wait_ready(f)
        # Nobody acted on the page; the run ends on the guard's own wall/monotonic mapping.
        ending_wall = f.result['ready_wall'] + .05
        report = dict(schema='campaign-receipt/5', session=SESSION, source_commit=COMMIT,
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
def test_current_marker_writer_can_finish_after_exposing_its_path(tmp_path, marker):
    with fixture(tmp_path) as f:
        path = tmp_path/marker
        payload = path.read_text()
        path.unlink()  # Only this synthetic fixture, before the guard starts.
        errors = []
        def supervise():
            try:
                f.supervise()
            except BaseException as exc:
                errors.append(repr(exc))
        thread = threading.Thread(target=supervise)
        try:
            with path.open('x') as writer:
                # Match the real producers' visible pathname before buffered close.
                thread.start()
                threading.Event().wait(.15)
                assert thread.is_alive() and 'reason' not in f.result
                writer.write(payload)
            wait_ready(f)
            assert thread.is_alive() and 'reason' not in f.result
            f.call('/api/pause', {'reason': 'other'})
            thread.join(3)
            assert not thread.is_alive() and not errors and f.result['reason'] == 'operator_pause'
            assert f.result['ready_monotonic'] <= f.result['pause_requested']
        finally:
            if thread.is_alive():
                f.call('/api/pause', {'reason': 'other'})
            thread.join(3)


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


@pytest.mark.parametrize('change', [
    dict(schema='campaign-watch-start/1'), dict(schema='campaign-watch-start/2'),
    dict(schema='campaign-watch-start/3'),
    dict(schema='campaign-watch-start/3', attention='best-effort', watch_seconds=None),
    dict(schema='campaign-watch-start/3', attention='required', watch_seconds=45),
    dict(schema='campaign-watch-start/5'), dict(schema=None), dict(viewer_port=5001), dict(session='c'*32),
    dict(source_commit='d'*40), dict(manifest_sha256=sha256(b'{"other":1}').hexdigest())])
def test_gateway_refuses_old_or_mismatched_watch_start(tmp_path, change):
    (tmp_path/'manifest.json').write_text('{}')
    opening = dict(schema='campaign-watch-start/4', session=SESSION, source_commit=COMMIT,
                   manifest_sha256=sha256(b'{}').hexdigest(), viewer_port=5000)
    put(tmp_path/'watch-start.json', {**opening, **change})
    stops, tx = socket.socketpair(type=socket.SOCK_DGRAM)
    with stops, tx:
        with pytest.raises(ValueError, match='exclusively reserved'):
            watch.worker(tmp_path, SESSION, COMMIT, 1, 1, tx, viewer_port=5000)
        assert not select.select([stops], [], [], 0)[0]  # no listening port was announced


def test_pause_forwards_empty_object_and_reports_the_reason_to_the_guard(tmp_path):
    with fixture(tmp_path) as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        assert f.call('/api/pause', {'reason': 'spend'})[0] == (200 if sys.platform == 'darwin' else 409)
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert f.result['pause_reason'] == 'spend'
        if sys.platform == 'darwin':
            assert f.state['pause_body'] == b'{}'


@pytest.mark.parametrize('bad', [{}, {'reason': 'boredom'}, {'reason': 'loop', 'note': 'x'}, {'reason': None}, [],
    {'reason': ['loop']}, {'reason': ''}, 'loop'])
def test_pause_is_never_refused_for_a_missing_or_unknown_reason(tmp_path, bad):
    with fixture(tmp_path) as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        assert f.call('/api/pause', bad)[0] == (200 if sys.platform == 'darwin' else 409)
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert f.result['pause_reason'] == 'unspecified'
        if sys.platform == 'darwin':
            assert f.state['pause_body'] == b'{}'


@pytest.mark.parametrize('reason', watch.PAUSE_REASONS)
def test_every_pause_reason_is_recorded_by_the_guard(tmp_path, reason):
    with fixture(tmp_path) as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        f.call('/api/pause', {'reason': reason})
        thread.join(3)
        assert not thread.is_alive() and f.result['pause_reason'] == reason


def test_viewer_json_and_png_pass_with_gateway_owned_headers(tmp_path):
    with fixture(tmp_path) as f:
        response, data = f.reply('/api/view/runs?limit=5')
        assert response.status == 200 and json.loads(data) == {'schema': 'spectator-view/1'}
        assert f.state['view']['paths'] == ['/api/view/runs?limit=5']
        assert response.getheader('Content-Type') == 'application/json'
        policy = response.getheader('Content-Security-Policy')
        assert policy.startswith("default-src 'self'") and 'unsafe-inline' not in policy
        assert response.getheader('X-Content-Type-Options') == 'nosniff'
        assert response.getheader('Cache-Control') == 'no-store'
        f.state['view'].update(media='image/png; charset=binary', body=b'\x89PNG viewer bytes')
        response, data = f.reply('/api/view/run/'+SESSION+'/frame/'+SESSION+'-1')
        assert response.status == 200 and data == b'\x89PNG viewer bytes'
        assert response.getheader('Content-Type') == 'image/png'
        f.state['view'].update(media='application/json', status=404, body=b'{"error":"unknown run"}')
        assert f.call('/api/view/run/other/summary')[0] == 404


@pytest.mark.parametrize('media', ['text/html', 'text/html; charset=utf-8', 'text/javascript',
                                   'application/javascript', 'image/svg+xml', 'application/octet-stream', ''])
def test_forwarding_refuses_html_script_and_untyped_viewer_responses(tmp_path, media):
    with fixture(tmp_path) as f:
        f.state['view'].update(media=media, body=b'<script>alert(1)</script>')
        code, data = f.call('/api/view/runs')
        assert code == 502 and b'<script' not in data


@pytest.mark.parametrize('declared', [None, 4*1024*1024+1])
def test_forwarding_refuses_oversize_bodies_declared_or_not(tmp_path, declared):
    with fixture(tmp_path) as f:
        f.state['view'].update(body=b'{"pad":"' + b'x'*(4*1024*1024) + b'"}', declared=declared)
        assert f.call('/api/view/runs')[0] == 502
        f.state['view'].update(body=b'{"ok":true}', declared=None)
        assert f.call('/api/view/runs')[0] == 200


def test_forwarding_accepts_a_body_exactly_at_the_cap(tmp_path):
    with fixture(tmp_path) as f:
        body = b'{"pad":"' + b'x'*(4*1024*1024-10) + b'"}'
        assert len(body) == 4*1024*1024
        f.state['view'].update(body=body)
        code, data = f.call('/api/view/runs')
        assert code == 200 and len(data) == 4*1024*1024


@pytest.mark.parametrize('status', [400, 404, 409, 413])
def test_documented_viewer_statuses_pass_through(tmp_path, status):
    with fixture(tmp_path) as f:
        f.state['view'].update(status=status, media='application/json', body=b'{"error":"documented"}')
        code, data = f.call('/api/view/runs')
        assert code == status and json.loads(data) == {'error': 'documented'}


@pytest.mark.parametrize('status', [301, 401, 429, 500, 502, 503])
def test_viewer_failure_statuses_become_unavailable(tmp_path, status):
    with fixture(tmp_path) as f:
        f.state['view'].update(status=status)
        code, data = f.call('/api/view/runs')
        assert code == 503 and json.loads(data) == {'viewer': 'unavailable'}


@pytest.mark.parametrize('path', ['/api/view/../status', '/api/view/%00x#', '/api/viewer/runs',
                                  '/api/view'])
def test_forwarding_only_takes_view_routes(tmp_path, path):
    with fixture(tmp_path) as f:
        assert f.call(path)[0] in (403, 404)
        assert f.state['view']['paths'] == []


def test_unreachable_viewer_is_unavailable_and_never_blocks_pause_status_or_frames(tmp_path):
    with fixture(tmp_path, viewer='absent') as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        code, data = f.call('/api/view/runs')
        assert code == 503 and json.loads(data) == {'viewer': 'unavailable'}
        assert f.call('/api/status')[0] == 200
        assert f.call('/api/source/'+SESSION+'-91') == (200, PNG)
        assert f.call('/api/pause', {'reason': 'fault'})[0] == (200 if sys.platform == 'darwin' else 409)
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'


def test_killed_viewer_mid_run_leaves_status_frames_and_pause_working(tmp_path):
    with fixture(tmp_path, viewer='process') as f:
        thread = threading.Thread(target=f.supervise); thread.start()
        deadline = time.monotonic()+5
        while True:
            code, data = f.call('/api/view/runs')
            if code == 200 or time.monotonic() > deadline:
                break
            time.sleep(.05)
        assert code == 200 and json.loads(data)['schema'] == 'spectator-view/1'
        os.killpg(f.viewer_process.pid, signal.SIGKILL)
        f.viewer_process.wait(3)
        assert json.loads(f.call('/api/view/runs')[1]) == {'viewer': 'unavailable'}
        assert thread.is_alive() and 'reason' not in f.result
        assert f.call('/api/source/'+SESSION+'-91') == (200, PNG)
        assert f.call('/api/status')[0] == 200
        assert f.call('/api/pause', {'reason': 'loop'})[0] == (200 if sys.platform == 'darwin' else 409)
        thread.join(3)
        assert not thread.is_alive() and f.result['reason'] == 'operator_pause'
        assert f.result['pause_reason'] == 'loop'


def test_slow_viewer_times_out_without_delaying_pause_or_status(tmp_path):
    with fixture(tmp_path) as f:
        f.state['view'].update(delay=4)
        outcome = []
        slow = threading.Thread(target=lambda: outcome.append((f.call('/api/view/runs'), time.monotonic())))
        started = time.monotonic()
        slow.start()
        time.sleep(.3)
        thread = threading.Thread(target=f.supervise); thread.start()
        began = time.monotonic()
        assert f.call('/api/source/'+SESSION+'-91') == (200, PNG)
        assert f.call('/api/status')[0] == 200
        assert f.call('/api/pause', {'reason': 'other'})[0] == (200 if sys.platform == 'darwin' else 409)
        assert time.monotonic()-began < 1.5
        slow.join(6)
        (code, data), finished = outcome[0]
        assert code == 503 and json.loads(data) == {'viewer': 'unavailable'}
        assert 1.8 <= finished-started < 3.5
        thread.join(3)


def test_slow_trickling_viewer_cannot_exceed_the_total_deadline(tmp_path):
    with fixture(tmp_path) as f:
        f.state['view'].update(trickle=True)
        started = time.monotonic()
        code, data = f.call('/api/view/runs')
        assert code == 503 and json.loads(data) == {'viewer': 'unavailable'}
        assert time.monotonic()-started < 3.5


def test_gateway_serves_only_the_page_app_and_vendor_files_with_media_types(tmp_path):
    with fixture(tmp_path) as f:
        response, page = f.reply('/')
        assert response.status == 200 and response.getheader('Content-Type').startswith('text/html')
        for path, media, text in [('/app/main.js', 'text/javascript', b'export const ready'),
                                  ('/app/style.css', 'text/css', b'margin'),
                                  ('/vendor/chart.js', 'text/javascript', b'vendored')]:
            response, data = f.reply(path)
            assert response.status == 200 and text in data and response.getheader('Content-Type').startswith(media)
            assert response.getheader('X-Content-Type-Options') == 'nosniff'
        for path in ['/app/notes.txt', '/private/secret.js', '/app/link.js', '/app/missing.js', '/app/', '/app',
                     '/vendor/', '/index.html', '/app.js', '/style.css', '/investigation.js', '/api/activity',
                     '/api/investigation', '/app/../private/secret.js', '/app/%2e%2e/private/secret.js',
                     '/app//main.js', '/../outside.js']:
            assert f.call(path)[0] in (403, 404), path
