"""Private HTTP worker for campaign_supervision; no provider credentials or game inputs."""
from datetime import datetime
from hashlib import sha256
import argparse
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

from harness.computer.protocol import read_json
from tools.campaign_package import digest

UI = Path(__file__).with_name('campaign_watch_ui.js')
WEB = Path(__file__).resolve().parents[1]/'web'
PAGES = {'/api/status'}
MAX_BODY = 4 * 1024 * 1024
NORMAL_EOF = 'Native receive failed: Native channel EOF'
# Owner Pause reasons (ADR008 item 5). The reason is recorded; the custodian never sees it.
PAUSE_REASONS = ('loop', 'fault', 'spend', 'other')
# The viewer is read-only and outside supervision: bounded, typed, never trusted.
VIEW_TIMEOUT = 2.
VIEW_MEDIA = {'application/json', 'image/png'}
VIEW_STATUSES = {200, 400, 404}
VIEW_SLOTS = 8
VIEW_PATH = re.compile(r'/api/view/[A-Za-z0-9_./=&?%,|:+~-]*')
STATIC_PART = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._-]*')
STATIC_TYPES = {'.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
                '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml',
                '.png': 'image/png', '.woff2': 'font/woff2', '.html': 'text/html; charset=utf-8'}


def static_file(web: Path, path: str) -> tuple[bytes, str] | None:
    """The page and its `app/` and `vendor/` files; nothing else under web/ is served."""
    if path == '/':
        parts = ['index.html']
    elif path.startswith(('/app/', '/vendor/')):
        parts = path[1:].split('/')
    else:
        return None
    media = STATIC_TYPES.get(Path(parts[-1]).suffix)
    if media is None or not all(STATIC_PART.fullmatch(part) for part in parts):
        return None
    candidate = web.joinpath(*parts)
    try:
        if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(web.resolve()):
            return None
        return candidate.read_bytes(), media
    except OSError:
        return None


def bind_pause_receiver(connection: HTTPConnection, upstream: int, receiver_pid: int) -> None:
    """Mac deployment limit: verify this connected socket belongs to the exact child.

    receiver_pid is supplied only by the supervisor's newly created Popen handle,
    never by mutable retained JSON. No POST precedes verification.
    """
    if type(receiver_pid) is not int or receiver_pid <= 0:
        raise ValueError('Pause has no exact owned receiver')
    connection.connect()
    local_port = connection.sock.getsockname()[1]
    expected = f'n127.0.0.1:{upstream}->127.0.0.1:{local_port}'
    sample = subprocess.run(['/usr/sbin/lsof', '-nP', '-a', '-p', str(receiver_pid),
        f'-iTCP:{upstream}', '-sTCP:ESTABLISHED', '-Fn'], capture_output=True, text=True, timeout=.4)
    if sample.returncode != 0 or expected not in sample.stdout.splitlines():
        raise ValueError('Pause receiver did not own the connected spectator socket')


class ViewerRefused(Exception):
    """The viewer answered, but not with something this gateway may pass on."""


def worker(package: Path, session: str, source_commit: str, upstream: int, receiver_pid: int,
           checks: socket.socket, stops: socket.socket, *, viewer_port: int, web: Path = WEB,
           receiver_check=bind_pause_receiver, connection_factory=HTTPConnection) -> None:
    if re.fullmatch('[a-f0-9]{32}', session) is None or re.fullmatch('[a-f0-9]{40}', source_commit) is None:
        raise ValueError('Invalid frozen watch binding')
    opening = read_json(package/'watch-start.json')
    attention = {('required', 45): 'Operator target: check every 15 seconds. Cutoff: 45 seconds.',
                 ('best-effort', None): 'Best-effort observation: checks are optional; Pause still stops input.'}
    policy = attention.get((opening.get('attention'), opening.get('watch_seconds')))
    recording = opening.get('attention') == 'required'
    if (opening.get('schema') != 'campaign-watch-start/3' or opening.get('session') != session
            or type(viewer_port) is not int or opening.get('viewer_port') != viewer_port
            or opening.get('source_commit') != source_commit or policy is None
            or opening.get('manifest_sha256') != digest(package/'manifest.json')
            or not (package/'watch-attempts.jsonl').is_file()
            or (package/'watch-attempts.jsonl').is_symlink()):
        raise ValueError('Worker has no current exclusively reserved supervision')
    source_pattern = re.compile(re.escape(session)+r'-[0-9]+')
    accepted = 0
    lock = threading.Lock()
    paused = threading.Event()
    ending_seen = False
    checks.settimeout(4.5)
    stops.setblocking(False)
    view_slots = threading.BoundedSemaphore(VIEW_SLOTS)

    def relay(path, body=None):
        connection = connection_factory('127.0.0.1', upstream, timeout=2)
        try:
            if body is not None:
                receiver_check(connection, upstream, receiver_pid)
            connection.request('GET' if body is None else 'POST', path, body,
                               {} if body is None else {'Content-Type': 'application/json'})
            response = connection.getresponse()
            data = response.read(MAX_BODY+1)
            if len(data) > MAX_BODY:
                raise ValueError('Spectator body exceeds this launcher limit')
            return response.status, data, response.getheader('Content-Type')
        finally:
            connection.close()

    def forward_view(path):
        """GET one viewer route under a total deadline and size cap; JSON and PNG only."""
        end = time.monotonic()+VIEW_TIMEOUT
        connection = connection_factory('127.0.0.1', viewer_port, timeout=VIEW_TIMEOUT)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            media = (response.getheader('Content-Type') or '').split(';')[0].strip().lower()
            declared = response.getheader('Content-Length')
            if response.status not in VIEW_STATUSES:
                raise OSError(f'Viewer returned HTTP {response.status}')
            if media not in VIEW_MEDIA:
                raise ViewerRefused('Viewer response type is not allowed')
            if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY):
                raise ViewerRefused('Viewer response exceeds the size cap')
            data = bytearray()
            while len(data) <= MAX_BODY:
                remaining = end-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Viewer response exceeded the deadline')
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                chunk = response.read1(65536)
                if not chunk:
                    break
                data += chunk
            if len(data) > MAX_BODY:
                raise ViewerRefused('Viewer response exceeds the size cap')
            return response.status, bytes(data), media
        finally:
            connection.close()

    def read_upstream(path):
        status, data, _ = relay(path)
        if status != 200:
            raise ValueError(f'Original spectator returned HTTP {status}')
        return data

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(4)

        def log_message(self, *args):
            pass

        def reply(self, status, data, media):
            self.send_response(status)
            for key, value in {'Content-Type': media or 'application/octet-stream',
                'Content-Length': str(len(data)), 'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy':
                "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'"}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def reply_json(self, status, **value):
            self.reply(status, json.dumps(value).encode(), 'application/json')

        def scoped(self, mutation=False):
            host = f'127.0.0.1:{self.server.server_port}'
            origin = self.headers.get('Origin')
            return self.headers.get('Host') == host and (origin == 'http://'+host or (origin is None and not mutation))

        def do_GET(self):
            if not self.scoped():
                self.send_error(403); return
            if self.path == '/campaign_watch_ui.js':
                self.reply(200, UI.read_bytes(), 'text/javascript'); return
            if self.path.startswith('/api/view/'):
                self.view(); return
            if self.path in PAGES or (self.path.startswith('/api/source/')
                    and source_pattern.fullmatch(self.path[12:])):
                try:
                    status, data, media = relay(self.path)
                except (OSError, ValueError):
                    self.reply_json(503, error='Original spectator unavailable'); return
            else:
                found = static_file(web, urlsplit(self.path).path)
                if found is None:
                    self.send_error(404); return
                status, (data, media) = 200, found
            if self.path == '/' and status == 200 and not recording:
                # Best-effort observation offers no check that could stop a healthy run.
                markup = f'<aside aria-label="Operator observation"><p>{policy}</p></aside>'.encode()
                data = data.replace(b'<div class="frame-shell" id="watch-frame-shell"',
                                    markup+b'<div class="frame-shell" id="watch-frame-shell"', 1)
            elif self.path == '/' and status == 200:
                data = data.replace(b'</head>', b'<script src="/campaign_watch_ui.js" defer></script></head>', 1)
                markup = (f'<aside aria-label="Operator acknowledgement"><button id="watch-record" '
                    f'type="button" data-next="{accepted+1}">Record operator check</button>'
                    f'<span id="watch-feedback" role="status">Checks accepted: {accepted}</span>'
                    f'<p>{policy}</p></aside>').encode()
                data = data.replace(b'<div class="frame-shell" id="watch-frame-shell"',
                                    markup+b'<div class="frame-shell" id="watch-frame-shell"', 1)
            self.reply(status, data, media)

        def view(self):
            # Own connection and bounded slots: a slow viewer cannot delay Pause, checks or status.
            if VIEW_PATH.fullmatch(self.path) is None or '..' in self.path:
                self.send_error(404); return
            if not view_slots.acquire(blocking=False):
                self.reply_json(503, viewer='unavailable'); return
            try:
                status, data, media = forward_view(self.path)
            except ViewerRefused:
                self.reply_json(502, error='Viewer response refused'); return
            except (OSError, ValueError):
                self.reply_json(503, viewer='unavailable'); return
            finally:
                view_slots.release()
            self.reply(status, data, media)

        def do_POST(self):
            nonlocal accepted, ending_seen
            if (not self.scoped(mutation=True) or self.path not in {'/record', '/api/pause'}
                    or (self.path == '/record' and not recording)
                    or self.headers.get('Content-Type') != 'application/json'):
                self.send_error(403); return
            try:
                length = int(self.headers['Content-Length'])
                if not 0 < length <= 512:
                    raise ValueError('Unexpected request size')
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError('Incomplete request body')
                form = json.loads(body)
                if self.path == '/api/pause':
                    if type(form) is not dict or set(form) != {'reason'} or form['reason'] not in PAUSE_REASONS:
                        raise ValueError('Pause requires {"reason": ' + ' | '.join(PAUSE_REASONS) + '}')
                    # Independent from record lock, including blocked source fetch/guard ACK.
                    paused.set()
                    stops.send(f"pause:{time.monotonic()!r}:{form['reason']}".encode())
                    # The custodian receives the original empty Pause; the reason is not its concern.
                    status, payload, media = relay(self.path, b'{}')
                    received = json.loads(payload)
                    if (status != 200 or received['schema'] != 'computer-pause/1'
                            or received['session'] != session or received['stop']['stop_requested'] is not True):
                        raise ValueError('Original Pause reply did not confirm the selected session')
                    self.reply(status, payload, media); self.wfile.flush()
                    stops.send(b'pause-replied')
                    return
                with lock:
                    if (type(form) is not dict or set(form) != {'sequence', 'session', 'observed', 'source', 'sha256'}
                            or type(form['sequence']) is not int or form['sequence'] != accepted+1
                            or form['session'] != session or paused.is_set()):
                        raise ValueError('Wrong or stopped session, or stale check number')
                    started = time.monotonic()
                    stamp = datetime.fromisoformat(form['observed'])
                    age = time.time()-stamp.timestamp()
                    if stamp.utcoffset() is None or not 0 <= age <= 12:
                        raise ValueError('Displayed status is stale or invalid')
                    source = form['source']
                    if not source_pattern.fullmatch(source) or not re.fullmatch('[a-f0-9]{64}', form['sha256']):
                        raise ValueError('Displayed source identity or digest is invalid')
                    status = json.loads(read_upstream('/api/status'))
                    native_code, stop = status.get('native_returncode'), status['stop']
                    ending = type(native_code) is int and native_code == 0
                    if (status['schema'] != 'computer-status/1' or status['session'] != session or paused.is_set()
                            or (native_code is not None and not ending) or (ending_seen and not ending)
                            or type(stop['stop_requested']) is not bool
                            or (stop['stop_requested'] and not (ending and stop['reason'] == NORMAL_EOF))
                            or sha256(read_upstream('/api/source/'+source)).hexdigest() != form['sha256']
                            or paused.is_set()):
                        raise ValueError('Original target, stop state or displayed PNG could not be verified')
                    row = dict(schema='campaign-watch-attempt/1', source_commit=source_commit,
                        sequence=accepted+1, session=session, start=started, observation=started-age,
                        observed_at=form['observed'], phase='ending' if ending else 'active',
                        source=source, sha256=form['sha256'], recorded_wall=time.time())
                    attempts.write(json.dumps(row)+'\n'); attempts.flush(); os.fsync(attempts.fileno())
                    confirmation = f"accepted:{row['sequence']}:{started!r}".encode()
                    try:
                        checks.send(json.dumps(row).encode())
                        if checks.recv(128) != confirmation or paused.is_set():
                            raise ValueError('Unmatched or stopped guard confirmation')
                    except (OSError, ValueError):
                        already_paused = paused.is_set()
                        paused.set()
                        if not already_paused:
                            stops.send(b'ack-uncertain')
                        raise
                    accepted += 1
                    ending_seen = ending
            except (KeyError, OSError, TypeError, ValueError, OverflowError, subprocess.TimeoutExpired) as exc:
                self.reply_json(409, error=str(exc)); return
            self.reply_json(200, accepted=accepted, source=source)

    # The supervisor exclusively reserved this file before launch; append attempts only.
    with (package/'watch-attempts.jsonl').open('a') as attempts:
        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            checks.send(json.dumps(dict(port=server.server_port)).encode())
            server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('session')
    parser.add_argument('source_commit')
    parser.add_argument('upstream', type=int)
    parser.add_argument('receiver_pid', type=int)
    parser.add_argument('checks_fd', type=int)
    parser.add_argument('stops_fd', type=int)
    parser.add_argument('--viewer-port', type=int, required=True)
    parser.add_argument('--web-root', type=Path, default=WEB)
    options = parser.parse_args()
    worker(options.package, options.session, options.source_commit, options.upstream, options.receiver_pid,
           socket.socket(fileno=options.checks_fd), socket.socket(fileno=options.stops_fd),
           viewer_port=options.viewer_port, web=options.web_root)
