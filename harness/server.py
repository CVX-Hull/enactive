"""Loopback mechanical HTTP transport; composition is injected, never imported."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

from .computer.protocol import ControlError, canonical, closed, decode_json
from .computer.runtime import request_identity

ROOT = Path(__file__).resolve().parents[1]


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False


def serve(application, port: int) -> tuple[LocalServer, threading.Thread]:
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def log_message(self, *args):
            pass

        def _origin(self) -> None:
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                raise ControlError('Only the selected loopback host is supported')
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + expected:
                raise ControlError('Cross-origin access refused')

        def reply(self, status: int, data: bytes, media: str, *, immutable: bool = False):
            self.send_response(status)
            self.send_header('Content-Type', media)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'private,max-age=31536000,immutable' if immutable else 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def json_reply(self, status: int, value: object):
            self.reply(status, (canonical(value)+'\n').encode('utf-8'), 'application/json; charset=utf-8')

        def do_GET(self):
            try:
                self._origin()
                path = urlsplit(self.path)
                if path.query or path.fragment:
                    raise ControlError('Query/fragment routes are unsupported')
                if path.path == '/api/status':
                    self.json_reply(200, application.status())
                elif path.path == '/api/activity':
                    self.json_reply(200, application.activity_view.snapshot())
                elif path.path.startswith('/api/source/'):
                    identity = unquote(path.path.removeprefix('/api/source/'))
                    # Public spectator reads only this mechanical session, not
                    # the selected player's historical knowledge store.
                    # The spectator verifies retained bytes without invoking
                    # actor-side source-failure fencing or issuing a source.
                    _, png = application.runtime.store.read_source(identity)
                    self.reply(200, png, 'image/png', immutable=True)
                elif path.path in ('/','/app.js','/style.css'):
                    name = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path.path]
                    media = {'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[name]
                    self.reply(200, (ROOT/'web'/name).read_bytes(), media)
                else:
                    self.json_reply(404, dict(error='Unknown current route'))
            except (OSError, ValueError) as exc:
                self.json_reply(400, dict(schema='player-error/1', error=type(exc).__name__, reason=str(exc)[:600], submission='none'))

        def do_POST(self):
            identity = actor = None
            try:
                self._origin()
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise ControlError('Only JSON mutations are supported')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 1048576:
                    raise ControlError('JSON body must be within 1 MiB')
                value = decode_json(self.rfile.read(length),1048576)
                if self.path == '/api/pause':
                    closed(value,set())
                    stopped = application.runtime.stop('Operator Pause')
                    self.json_reply(200, dict(schema='computer-pause/1',
                        session=application.runtime.session, stop=stopped))
                    return
                authorization = self.headers.get('Authorization','')
                if not authorization.startswith('Bearer '):
                    raise ControlError('Actor capability required')
                token = authorization.removeprefix('Bearer ')
                actor = application.runtime.authorize(token)
                if self.path == '/api/actor-stop':
                    closed(value,{'session','reason'})
                    if value['session'] != application.runtime.session or not isinstance(value['reason'],str):
                        raise ControlError('Actor stop belongs to another session')
                    self.json_reply(200,application.runtime.stop_actor(token,value['reason'][:600]))
                    return
                if self.path == '/api/player-source':
                    closed(value,{'source_id'})
                    _, png = application.source(value['source_id'],actor)
                    self.reply(200,png,'image/png')
                    return
                if self.path != '/api/tool':
                    self.json_reply(404,dict(error='Unknown current route'))
                    return
                closed(value,{'operation_id','tool','arguments'})
                identity = request_identity(value['operation_id'])
                result, _ = application.call(token,value['tool'],value['arguments'],identity)
                # Images use a separate exact-source read; no base64 in HTTP.
                self.json_reply(200, dict(schema='player-response/1',value=result))
            except (OSError, ValueError, TypeError) as exc:
                self._failure(exc,actor,identity)
            except Exception as exc:
                self._failure(exc,actor,identity)

        def _failure(self, exc, actor, identity):
            submission = 'none'
            if identity and actor:
                try:
                    submission = application.submission_status(actor,identity)
                except Exception:
                    submission = 'uncertain'
            try:
                self.json_reply(400 if submission == 'none' else 409,
                    dict(schema='player-error/1',error=type(exc).__name__,reason=str(exc)[:600],
                         operation_id=identity,submission=submission))
            except (OSError,ValueError):
                pass

    server = LocalServer(('127.0.0.1',port),Handler)
    thread = threading.Thread(target=server.serve_forever,name='computer-http',daemon=True)
    thread.start()
    return server,thread
