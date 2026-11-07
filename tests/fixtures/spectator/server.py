"""Static fixture server for the spectator page tests: web/ plus stub APIs, no game, no provider.

It imitates only the parts of the supervised gateway that the page depends on:
- serves web/ and injects the operator-check panel and `campaign_watch_ui.js` into the
  index page at the same anchors the gateway uses;
- sends the gateway's Content-Security-Policy on every response;
- answers the control path: GET /api/status (computer-status/1), GET /api/source/<id>
  (PNG), POST /api/pause with a reason, POST /record;
- answers `/api/view/*` from the JSON files beside this script (one run, every route),
  or `503 {"viewer": "unavailable"}` while the viewer is switched off.

Test hooks (never part of the product): GET /__fixture/state, POST /__fixture/viewer?mode=down|up,
POST /__fixture/advance?n=5. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WEB = ROOT / 'web'
UI = ROOT / 'tools' / 'campaign_watch_ui.js'
CSP = "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'"
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
         '.md': 'text/markdown', '.json': 'application/json', '.png': 'image/png'}
SESSION = '5c7e91d2a4b84f60b3d1e0a9c2f7184d'
POLICY = 'Operator target: check every 15 seconds. Cutoff: 45 seconds.'
REASONS = {'loop', 'fault', 'spend', 'other'}


def load(name):
    return json.loads((HERE / name).read_text())


class State:
    def __init__(self, attention):
        self.lock = threading.Lock()
        self.attention = attention
        self.steps = load('steps.json')['steps']
        self.requests = load('requests.json')
        self.runs = {row['run'] for row in load('runs.json')['runs']}
        self.png = (HERE / 'frame.png').read_bytes()
        self.sha = hashlib.sha256(self.png).hexdigest()
        self.visible = len(self.steps) - 10
        self.viewer_down = False
        self.pauses, self.records, self.view_requests = [], [], []
        self.started = time.time()

    def capture(self):
        return 1000 + self.visible

    def status(self):
        now = time.time()
        capture = self.capture()
        source = dict(schema='computer-source/1', source_id=f'{SESSION}-{capture}', session=SESSION,
                      capture_id=capture, sha256=self.sha, media_type='image/png',
                      presented_ms=int((now - 4) * 1000), received_wall=now - 3.9, width=640, height=360,
                      window_width=640, window_height=360, viewport=[0, 0, 640, 360])
        paused = bool(self.pauses)
        return dict(schema='computer-status/1', session=SESSION,
                    target=dict(pid=4242, window_id=7, paused=False, takeover_generation=0),
                    stop=dict(stop_requested=paused, native_pause_confirmed=False,
                              reason='Operator Pause' if paused else None),
                    remaining=dict(custodian_seconds=2400, inputs=312, requests=800, frames=900, frame_bytes=10 ** 9),
                    actors=[dict(actor_id='actor-1', stage='retired'), dict(actor_id='actor-2', stage='active')],
                    last_operation=dict(kind='input', operation_id='op-91', status='ok', reason=None),
                    latest_source=source, native_returncode=None,
                    host=dict(index=2, model='terra-1', provider='openrouter', host_seconds_remaining=2300,
                              requests_total=61, max_requests_total=2000, latest_response_wall=now - 5),
                    player_claims=[])


def inject(data: bytes, attention: str, accepted: int) -> bytes:
    anchor = b'<div class="frame-shell" id="watch-frame-shell"'
    if attention != 'required':
        markup = f'<aside aria-label="Operator observation"><p>{POLICY}</p></aside>'.encode()
        return data.replace(anchor, markup + anchor, 1)
    data = data.replace(b'</head>', b'<script src="/campaign_watch_ui.js" defer></script></head>', 1)
    markup = (f'<aside aria-label="Operator acknowledgement"><button id="watch-record" '
              f'type="button" data-next="{accepted + 1}">Record operator check</button>'
              f'<span id="watch-feedback" role="status">Checks accepted: {accepted}</span>'
              f'<p>{POLICY}</p></aside>').encode()
    return data.replace(anchor, markup + anchor, 1)


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'

        def log_message(self, *args):
            pass

        def reply(self, status, data, media, extra=None):
            self.send_response(status)
            headers = {'Content-Type': media, 'Content-Length': str(len(data)), 'Cache-Control': 'no-store',
                       'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': CSP}
            headers.update(extra or {})
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def json(self, status, value):
            self.reply(status, json.dumps(value).encode(), 'application/json')

        # ------------------------------------------------------------ GET
        def do_GET(self):
            url = urlparse(self.path)
            path, query = url.path, parse_qs(url.query)
            if path == '/campaign_watch_ui.js':
                self.reply(200, UI.read_bytes(), TYPES['.js']); return
            if path == '/api/status':
                with state.lock:
                    self.json(200, state.status())
                return
            if path.startswith('/api/source/'):
                if re.fullmatch(SESSION + r'-[0-9]+', path[12:]):
                    self.reply(200, state.png, 'image/png')
                else:
                    self.send_error(404)
                return
            if path.startswith('/api/view/'):
                self.view(path[len('/api/view/'):], query); return
            if path == '/__fixture/state':
                with state.lock:
                    self.json(200, dict(pauses=state.pauses, records=state.records, visible=state.visible,
                                        viewer_down=state.viewer_down, view_requests=state.view_requests))
                return
            self.static(path)

        def static(self, path):
            name = 'index.html' if path == '/' else path.lstrip('/')
            target = (WEB / name).resolve()
            if not target.is_relative_to(WEB) or not target.is_file():
                self.send_error(404); return
            data = target.read_bytes()
            if name == 'index.html':
                data = inject(data, state.attention, len(state.records))
            self.reply(200, data, TYPES.get(target.suffix, 'application/octet-stream'))

        # ------------------------------------------------------------ viewer routes
        def view(self, route, query):
            with state.lock:
                state.view_requests.append(route + ('?' + urlparse(self.path).query if query else ''))
                down = state.viewer_down
                visible = state.visible
            if down:
                self.json(503, {'viewer': 'unavailable'}); return
            first = lambda key, default=None: (query.get(key) or [default])[0]
            if route == 'runs':
                self.json(200, load('runs.json')); return
            if route == 'improve/changes':
                self.json(200, load('improve-changes.json')); return
            if route == 'improve/failures':
                self.json(200, load('improve-failures.json')); return
            if route == 'compare':
                self.json(200, load('compare-start.json' if first('group') == 'start' else 'compare-arm.json')); return
            if route == 'explore':
                self.json(200, load('explore.json')); return
            match = re.fullmatch(r'run/([^/]+)/(.+)', route)
            if not match:
                self.send_error(404); return
            run, sub = match.groups()
            if run not in state.runs:
                self.json(404, {'error': 'unknown run'}); return
            if sub.startswith('frame/'):
                self.reply(200, state.png, 'image/png'); return
            if sub == 'summary':
                body = load('summary.json')
                body['facts']['decisions'] = body['outcome']['decisions'] = visible
                self.json(200, body); return
            if sub == 'steps':
                after = int(first('after', -1))
                limit = min(500, int(first('limit', 500)))
                rows = [s for s in state.steps[:visible] if s['seq'] > after]
                page = rows[:limit]
                self.json(200, dict(schema='spectator-view/1', steps=page,
                                    next=page[-1]['seq'] if len(rows) > limit else None)); return
            if sub == 'requests':
                body = load('requests.json')
                horizon = state.steps[visible - 1]['wall']
                body['requests'] = [r for r in body['requests'] if r['wall'] <= horizon]
                body['markers'] = [m for m in body['markers'] if m['wall'] <= horizon]
                self.json(200, body); return
            if sub.startswith('context/'):
                body = load('context.json')
                body['request_id'] = sub[len('context/'):]
                self.json(200, body); return
            if sub == 'calls':
                body = load('calls.json')
                for key in ('tool', 'status'):
                    if first(key):
                        body['calls'] = [c for c in body['calls'] if c[key] == first(key)]
                self.json(200, body); return
            if sub in ('tools', 'memory', 'programs', 'handoffs'):
                self.json(200, load(sub + '.json')); return
            self.send_error(404)

        # ------------------------------------------------------------ POST
        def do_POST(self):
            url = urlparse(self.path)
            length = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(length) if length else b''
            if url.path == '/__fixture/viewer':
                with state.lock:
                    state.viewer_down = parse_qs(url.query).get('mode') == ['down']
                self.json(200, {'viewer_down': state.viewer_down}); return
            if url.path == '/__fixture/advance':
                with state.lock:
                    state.visible = min(len(state.steps), state.visible + int(parse_qs(url.query).get('n', ['1'])[0]))
                self.json(200, {'visible': state.visible}); return
            try:
                form = json.loads(raw or b'{}')
            except ValueError:
                self.json(400, {'error': 'bad json'}); return
            if url.path == '/api/pause':
                if not isinstance(form, dict) or set(form) != {'reason'} or form['reason'] not in REASONS:
                    self.json(400, {'error': 'Pause requires one reason'}); return
                with state.lock:
                    state.pauses.append(form)
                self.json(200, dict(schema='computer-pause/1', session=SESSION,
                                    stop=dict(stop_requested=True, native_pause_confirmed=False,
                                              reason='Operator Pause')))
                return
            if url.path == '/record' and state.attention == 'required':
                with state.lock:
                    if form.get('sequence') != len(state.records) + 1 or form.get('session') != SESSION:
                        self.json(409, {'error': 'Wrong or stopped session, or stale check number'}); return
                    state.records.append(form)
                    self.json(200, dict(accepted=len(state.records), source=form['source']))
                return
            self.send_error(403)

    return Handler


def serve(attention: str = 'required', port: int = 0):
    state = State(attention)
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(state))
    return server, state


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--attention', choices=('required', 'best-effort'), default='required')
    args = parser.parse_args(argv)
    server, _ = serve(args.attention, args.port)
    print(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}/')), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
