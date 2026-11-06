"""Private HTTP worker for campaign_supervision; no provider credentials or game inputs."""
from datetime import datetime
from hashlib import sha256
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

from harness.computer.protocol import read_json
from tools.campaign_package import digest

UI = Path(__file__).with_name('campaign_watch_ui.js')
PAGES = {'/', '/app.js', '/style.css', '/investigation.js', '/investigation-worker.js',
         '/investigation-session.js', '/investigation.css', '/api/status', '/api/activity', '/api/investigation'}
MAX_BODY = 4 * 1024 * 1024
NORMAL_EOF = 'Native receive failed: Native channel EOF'


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


def worker(package: Path, session: str, source_commit: str, upstream: int, receiver_pid: int,
           checks: socket.socket, stops: socket.socket, *, receiver_check=bind_pause_receiver,
           connection_factory=HTTPConnection) -> None:
    if re.fullmatch('[a-f0-9]{32}', session) is None or re.fullmatch('[a-f0-9]{40}', source_commit) is None:
        raise ValueError('Invalid frozen watch binding')
    opening = read_json(package/'watch-start.json')
    attention = {('required', 45): 'Operator target: check every 15 seconds. Cutoff: 45 seconds.',
                 ('best-effort', None): 'Best-effort observation: checks are optional; Pause still stops input.'}
    policy = attention.get((opening.get('attention'), opening.get('watch_seconds')))
    if (opening.get('schema') != 'campaign-watch-start/2' or opening.get('session') != session
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
            if self.path not in PAGES and not (self.path.startswith('/api/source/')
                    and source_pattern.fullmatch(self.path[12:])):
                self.send_error(404); return
            try:
                status, data, media = relay(self.path)
            except (OSError, ValueError):
                self.reply_json(503, error='Original spectator unavailable'); return
            if self.path == '/' and status == 200:
                data = data.replace(b'</head>', b'<script src="/campaign_watch_ui.js" defer></script></head>', 1)
                markup = (f'<aside aria-label="Operator acknowledgement"><button id="watch-record" '
                    f'type="button" data-next="{accepted+1}">Record operator check</button>'
                    f'<span id="watch-feedback" role="status">Checks accepted: {accepted}</span>'
                    f'<p>{policy}</p></aside>').encode()
                data = data.replace(b'<div class="frame-shell" id="watch-frame-shell"',
                                    markup+b'<div class="frame-shell" id="watch-frame-shell"', 1)
            self.reply(status, data, media)

        def do_POST(self):
            nonlocal accepted, ending_seen
            if (not self.scoped(mutation=True) or self.path not in {'/record', '/api/pause'}
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
                    if form != {}:
                        raise ValueError('Pause requires an empty object')
                    # Independent from record lock, including blocked source fetch/guard ACK.
                    paused.set()
                    stops.send(f'pause:{time.monotonic()!r}'.encode())
                    status, payload, media = relay(self.path, body)
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
    worker(Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]),
           socket.socket(fileno=int(sys.argv[6])), socket.socket(fileno=int(sys.argv[7])))
