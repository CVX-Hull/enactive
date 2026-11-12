"""Private HTTP worker for campaign_supervision; no provider credentials or game inputs."""
from hashlib import file_digest
import argparse
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit

from harness.computer.protocol import read_json

WEB = Path(__file__).resolve().parents[1]/'web'
PAGES = {'/api/status'}
MAX_BODY = 4 * 1024 * 1024
# Owner Pause reasons (ADR008 item 5). The reason is recorded; the custodian never sees it. A Pause is
# never refused over its reason: a missing or unknown one is recorded as `unspecified`.
PAUSE_REASONS = ('loop', 'fault', 'spend', 'other')
UNSPECIFIED = 'unspecified'
PAUSE_RECORDED = (*PAUSE_REASONS, UNSPECIFIED)
# The viewer is read-only and outside supervision: bounded, typed, never trusted.
VIEW_TIMEOUT = 2.
VIEW_MEDIA = {'application/json', 'image/png'}
VIEW_STATUSES = {200, 400, 404, 409, 413}  # spectator-view/1: 409 ambiguous request, 413 too large; the rest is 503
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
           stops: socket.socket, *, viewer_port: int, web: Path = WEB,
           receiver_check=bind_pause_receiver, connection_factory=HTTPConnection) -> None:
    """Serve the page, status, frames and viewer reads, and forward Pause.

    `stops` is the one datagram channel to the guardian: the listening port first, then Pause.
    """
    if re.fullmatch('[a-f0-9]{32}', session) is None or re.fullmatch('[a-f0-9]{40}', source_commit) is None:
        raise ValueError('Invalid frozen watch binding')
    opening = read_json(package/'watch-start.json')
    with (package/'manifest.json').open('rb') as stream:
        manifest_sha256 = file_digest(stream, 'sha256').hexdigest()
    if (type(opening) is not dict or opening.get('schema') != 'campaign-watch-start/4'
            or opening.get('session') != session
            or type(viewer_port) is not int or opening.get('viewer_port') != viewer_port
            or opening.get('source_commit') != source_commit
            or opening.get('manifest_sha256') != manifest_sha256):
        raise ValueError('Worker has no current exclusively reserved supervision')
    source_pattern = re.compile(re.escape(session)+r'-[0-9]+')
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
            self.reply(status, data, media)

        def view(self):
            # Own connection and bounded slots: a slow viewer cannot delay Pause or status.
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

        def pause_reason(self):
            """The reason as given when valid, else `unspecified`; a bad body never refuses the stop."""
            try:
                length = int(self.headers.get('Content-Length') or 0)
                form = json.loads(self.rfile.read(length)) if 0 < length <= 512 else None
            except (OSError, TypeError, ValueError, OverflowError):
                return UNSPECIFIED
            reason = form.get('reason') if type(form) is dict and set(form) == {'reason'} else None
            return reason if type(reason) is str and reason in PAUSE_REASONS else UNSPECIFIED

        def do_POST(self):
            if (not self.scoped(mutation=True) or self.path != '/api/pause'
                    or self.headers.get('Content-Type') != 'application/json'):
                self.send_error(403); return
            try:
                reason = self.pause_reason()
                stops.send(f"pause:{time.monotonic()!r}:{reason}".encode())
                # The custodian receives the original empty Pause; the reason is not its concern.
                status, payload, media = relay(self.path, b'{}')
                received = json.loads(payload)
                if (status != 200 or received['schema'] != 'computer-pause/1'
                        or received['session'] != session or received['stop']['stop_requested'] is not True):
                    raise ValueError('Original Pause reply did not confirm the selected session')
                self.reply(status, payload, media); self.wfile.flush()
                stops.send(b'pause-replied')
            except (KeyError, OSError, TypeError, ValueError, OverflowError, subprocess.TimeoutExpired) as exc:
                self.reply_json(409, error=str(exc))

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        stops.send(json.dumps(dict(port=server.server_port)).encode())
        server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('session')
    parser.add_argument('source_commit')
    parser.add_argument('upstream', type=int)
    parser.add_argument('receiver_pid', type=int)
    parser.add_argument('stops_fd', type=int)
    parser.add_argument('--viewer-port', type=int, required=True)
    parser.add_argument('--web-root', type=Path, default=WEB)
    options = parser.parse_args()
    worker(options.package, options.session, options.source_commit, options.upstream, options.receiver_pid,
           socket.socket(fileno=options.stops_fd), viewer_port=options.viewer_port, web=options.web_root)
