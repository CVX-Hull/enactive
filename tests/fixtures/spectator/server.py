"""Static fixture server for the spectator page tests: web/ plus stub APIs, no game, no provider.

It imitates only the parts of the supervised gateway that the page depends on:
- serves web/index.html, web/app/* and web/vendor/* unchanged (as the gateway does);
- sends the gateway's Content-Security-Policy on every response;
- answers the control path: GET /api/status (computer-status/2), GET /api/source/<id>
  (PNG), POST /api/pause with a reason;
- answers `/api/view/*` from the JSON files beside this script (real viewer responses for one run and the
  cross-run routes, trimmed; `refresh.py` regenerates them),
  or `503 {"viewer": "unavailable"}` while the viewer is switched off; the `frame-*.json` files (the spectator's
  frame, `spectator-frame/1`) and everything in `synthetic.py` (the story feed, request telemetry, delivered knowledge,
  host telemetry and curator figures of the live run) are invented, not captured, so `refresh.py` does not touch them.
  Every other run has no host trace, delivered knowledge or curator, which is how an older run looks.

With `--viewer URL` the view routes go to a real viewer process instead (the control path stays stubbed).

Test hooks (never part of the product): GET /__fixture/state, POST /__fixture/viewer?mode=down|up|nolive|stale|stale-recorded|ended,
POST /__fixture/advance?n=5. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
# The browser runner launches the fixture with isolated Python and no installed dependencies.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import synthetic
from harness.spectator_assets import PAGE_POLICY as CSP, WEB, static_file

LIVE_RUN = 'ceil09'
SPEND_LIMIT = 5.0
SESSION = 'c6c09be0b7d43fba2839147651a4f6a5'    # the live run's real session id
REASONS = {'loop', 'fault', 'spend', 'other'}
CUT_RESULTS = {80: 'target', 120: 'rescue', 160: 'target', 200: 'best_effort'}


def load(name):
    return json.loads((HERE / name).read_text())


class State:
    def __init__(self, upstream=None):
        self.upstream = upstream
        self.lock = threading.Lock()
        self.steps = load('steps.json')['items']
        self.requests = load('requests.json')
        self.sessions = {row['session']: row['run'] for row in load('runs.json')['items']}
        self.png = (HERE / 'frame.png').read_bytes()
        self.sha = hashlib.sha256(self.png).hexdigest()
        self.visible = len(self.steps) - 4
        self.viewer_down = False
        self.no_live = False
        self.stale = False
        self.ended = False
        self.pauses, self.view_requests = [], []
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
        return dict(schema='computer-status/2', session=SESSION,
                    target=dict(pid=4242, window_id=7, paused=False, takeover_generation=0),
                    stop=dict(stop_requested=paused, native_pause_confirmed=False,
                              reason='Operator Pause' if paused else None),
                    remaining=dict(custodian_seconds=2400, inputs=312, requests=800, frames=900, frame_bytes=10 ** 9),
                    actors=[dict(actor_id='actor-1', stage='retired'), dict(actor_id='actor-2', stage='active')],
                    last_operation=dict(kind='input', operation_id='op-91', status='ok', reason=None),
                    latest_source=source, native_returncode=None,
                    host=dict(index=2, model='terra-1', provider='openrouter', host_seconds_remaining=2300,
                              observed_attempts=61, latest_response_wall=now - 5),
                    player_claims=[])


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
                    self.json(200, dict(pauses=state.pauses, visible=state.visible,
                                        viewer_down=state.viewer_down, view_requests=state.view_requests))
                return
            self.static(path)

        def static(self, path):
            recorded = path == '/recorded/'
            found = static_file(WEB, '/' if recorded else path, recorded=recorded)
            if found is None:
                self.send_error(404); return
            self.reply(200, *found)

        # ------------------------------------------------------------ viewer routes
        def forward(self, upstream, path):
            """Like the gateway: JSON or PNG only, 2 s timeout, 503 when the viewer cannot answer."""
            try:
                with urllib.request.urlopen(upstream.rstrip('/') + path, timeout=2) as response:
                    body, media, status = response.read(4 * 1024 * 1024 + 1), response.headers.get_content_type(), response.status
            except urllib.error.HTTPError as error:
                body, media, status = error.read(), error.headers.get_content_type(), error.code
            except (OSError, ValueError):
                self.json(503, {'viewer': 'unavailable'}); return
            if media not in ('application/json', 'image/png'):
                self.json(503, {'viewer': 'unavailable'}); return
            self.reply(status, body, media)

        def view(self, route, query):
            with state.lock:
                state.view_requests.append(route + ('?' + urlparse(self.path).query if query else ''))
                down = state.viewer_down
                visible = state.visible
            if down:
                self.json(503, {'viewer': 'unavailable'}); return
            if state.upstream:
                self.forward(state.upstream, self.path); return
            first = lambda key, default=None: (query.get(key) or [default])[0]
            if route == 'runs':
                body = load('runs.json')
                after, limit = int(first('after', 0)), min(500, int(first('limit', 100)))
                rows = body['items'][after:after + limit + 1]
                if state.no_live or state.ended:
                    rows = [dict(row, state='final') for row in rows]
                if state.stale:
                    # stale: the first-listed run left a live store that was never finalized (#435).
                    rows = [dict(row, state='unfinished') if index == 0 and after == 0 else row for index, row in enumerate(rows)]
                body.update(items=rows[:limit], next=after + limit if len(rows) > limit else None, limit=limit)
                self.json(200, body); return
            if route in ('frame/curator-sources', 'frame/curator-session-sources', 'frame/curator-draft-sources'):
                self.json(200, dict(schema='spectator-frame/1', items=[], total=0, next=None, limit=500)); return
            if route == 'frame/curator-runner':
                self.json(200, synthetic.runner_status(first('run') in (LIVE_RUN, SESSION))); return
            if route in ('frame/health', 'frame/containers', 'frame/episodes'):
                self.json(200, load('frame-' + route.split('/')[1] + '.json')); return
            if route.startswith('frame/containers/'):
                wanted = unquote(route[len('frame/containers/'):])
                found = [c for c in load('frame-container.json') if c['container']['id'] == wanted]
                if found:
                    self.json(200, found[0])
                else:
                    self.json(404, {'schema': 'spectator-view/3', 'error': 'unknown_container', 'detail': wanted})
                return
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
            run = state.sessions.get(run, run)     # a run by session, or by its name, as the viewer resolves one
            session = next((s for s, name in state.sessions.items() if name == run), None)
            if session is None:
                self.json(404, {'error': 'unknown run'}); return
            if sub.startswith('frame/'):
                self.reply(200, state.png, 'image/png'); return
            traced = run == LIVE_RUN
            shown = state.steps[:visible]
            if sub in ('summary', 'feed', 'telemetry'):
                body = load('summary.json')
                body['custodian_receipt'] = None
                body['facts']['spend_allowance_usd'] = SPEND_LIMIT
                body['host_telemetry'] = synthetic.host_telemetry(shown) if traced else None
                if traced:
                    host = body['host_telemetry']
                    results = [result for seq, result in CUT_RESULTS.items() if seq <= shown[-1]['seq']]
                    host['context_cuts']['by_result'] = {result: results.count(result) for result in ('target', 'best_effort', 'rescue')}
                    host['context_cuts']['latest']['cut_result'] = CUT_RESULTS.get(
                        int(host['context_cuts']['latest']['request_id'].removeprefix('request-')))
                    host['tail_notices'] = dict(count=2, by_kind={'context-capacity': 1, 'host-timeout': 0, 'spend-limit': 1})
                    host['spend_reserve_reached'] = dict(count=1, latest=dict(
                        actor='actor-1', actor_id='actor-1', wall_time=shown[-1]['wall'],
                        spent_usd='2.5', spend_limit_usd='5', finish_reserve_usd='2.5', unpriced_bound_usd='0.05'))
                body['curator_spend'] = synthetic.curator_spend() if traced else None
                body['boundary_grooming'] = synthetic.boundary_grooming()
                body.update(run=run, session=session)
                if traced and state.ended:
                    body.update(state='final', live=False, pause=None, findings=body['findings'] + synthetic.terminal_findings(shown))
            if sub == 'feed':
                items = synthetic.feed(shown, body['findings'], not traced)
                for item in items:
                    if item['entry_kind'] == 'context_cut':
                        item['cut_result'] = CUT_RESULTS.get(item['seq']) if item['outcome'] == 'applied' else None
                self.json(200, synthetic.feed_page(items, int(first('after', 0)), min(500, int(first('limit', 100))), not traced)); return
            if sub == 'telemetry':
                telemetry = synthetic.telemetry(shown, body, not traced)
                for cut in telemetry['cuts']:
                    cut['cut_result'] = CUT_RESULTS.get(cut['seq']) if cut['outcome'] == 'applied' else None
                telemetry['spend_reserve_reached'] = ([dict(actor='actor-1', actor_id='actor-1', seq=shown[-1]['seq'],
                    wall=shown[-1]['wall'], spent_usd='2.5', spend_limit_usd='5', finish_reserve_usd='2.5', unpriced_bound_usd='0.05')]
                    if traced else [])
                telemetry['spend_reserve_reached_omitted'] = 0
                telemetry['tail_notices'] = (dict(count=2, by_kind={'context-capacity': 1, 'host-timeout': 0, 'spend-limit': 1})
                    if traced else dict(count=0, by_kind={'context-capacity': 0, 'host-timeout': 0, 'spend-limit': 0}))
                self.json(200, telemetry); return
            if sub == 'delivered-knowledge':
                limit = min(500, int(first('limit', 100)))
                found = synthetic.delivered(shown, first('version'), first('q', ''), first('scope', 'all'), int(first('after', 0)), limit) \
                    if traced else synthetic.no_knowledge(limit)
                if found is None:
                    self.json(404, {'schema': 'spectator-view/3', 'error': 'unknown_version', 'detail': first('version')}); return
                self.json(200, found); return
            if sub == 'summary':
                if run in ('aidA1', 'aidA2', 'aidA3', 'aidA4'):
                    body.update(run=run, state='final', live=False, pause=None)
                if run == 'aidA1':
                    if state.stale:
                        # Summary exposes the stored state separately from live evaluation.
                        body['state'] = 'live'
                    body['custodian_receipt'] = dict(outcome='player_external_stop_complete_unassessed',
                        normal_native_exit_zero=True, native_absence_verified=True,
                        deciding_hosts_quiescent=None, input_authority_revoked=False,
                        accounting=dict(reported_usd='1.64493095', spent_usd='1.64493095',
                                        unpriced_requests=1, unpriced_recall_requests=1))
                if run in ('aidA3', 'aidA4'):
                    body['custodian_receipt'] = dict(outcome='incomplete', accounting=None)
                if run == 'aidA3':
                    body['custodian_receipt']['accounting'] = dict(reported_usd='0', spent_usd='0',
                        unpriced_requests=0, unpriced_recall_requests=0)
                body['decisions'] = state.steps[visible - 1]['decision']
                body['findings'] = [f for f in body['findings'] if f['seq_start'] <= state.steps[visible - 1]['seq']]
                self.json(200, body); return
            if sub == 'steps':
                after = int(first('after', 0))
                limit = min(500, int(first('limit', 100)))
                rows = [s for s in state.steps[:visible] if s['seq'] > after]
                page = rows[:limit]
                self.json(200, dict(schema='spectator-view/3', items=page, limit=limit,
                                    next=page[-1]['seq'] if len(rows) > limit else None)); return
            if sub == 'requests':
                body = load('requests.json')
                horizon = state.steps[visible - 1]['wall']
                after, limit = int(first('after', 0)), min(500, int(first('limit', 100)))
                rows = [r for r in body['items'] if r['id'] > after and r['wall'] <= horizon]
                body.update(items=rows[:limit], limit=limit, next=rows[limit - 1]['id'] if len(rows) > limit else None,
                            markers=[m for m in body['markers'] if m['wall'] is not None and m['wall'] <= horizon])
                self.json(200, body); return
            if sub.startswith('context/'):
                body = load('context.json')
                body['request_id'] = sub[len('context/'):]
                self.json(200, body); return
            if sub == 'calls':
                body = load('calls.json')
                for key in ('tool', 'status'):
                    if first(key):
                        body['items'] = [c for c in body['items'] if c[key] == first(key)]
                self.json(200, body); return
            if sub == 'knowledge':
                body = load('knowledge.json')
                actor = first('actor')
                if not actor:
                    body = {k: body[k] for k in ('schema', 'actors', 'actors_omitted')}
                    body.update(actor=None, request_id=None)
                else:
                    body['actor'] = actor
                    body['request_id'] = first('request') or None
                    selected = first('entry')
                    if selected:
                        body['snapshot']['entry_id'] = selected
                        body['snapshot']['items'] = [item for item in body['snapshot']['items'] if item['id'] == selected]
                        body['snapshot']['total'] = len(body['snapshot']['items'])
                    update = {f'request-{seq}': version for seq, version in synthetic.UPDATES.items()}.get(first('request'))
                    if update is not None:   # the delivery one story entry names
                        body['events'] = [synthetic.delivery_event(update)]
                    if actor == 'actor-2':
                        body.update(events=[], calls=[], hints=[], finishes=[], journal_available=False)
                    elif traced:
                        read = body['calls'][0]
                        hit = dict(id='fact-visible', kind='fact', subject='The passage', via='match', status=['needs_review'],
                            snippet='<img src=x onerror=window.hitExecuted=true>', cited_by_articles=['article-passage'])
                        body['calls'].append(dict(read, tool='player_knowledge_query', tool_call_id='query-call',
                            query='passage', returned_hits=[hit], returned_hits_omitted=0))
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
                    mode = parse_qs(url.query).get('mode', [''])[0]
                    state.viewer_down = mode == 'down'
                    # nolive: the viewer is up but has not yet listed the live run (its first pass is still running).
                    state.no_live = mode in ('nolive', 'stale-recorded')
                    state.stale = mode in ('stale', 'stale-recorded')
                    # ended: the live run was evaluated a last time, which added findings, and is now final.
                    state.ended = mode == 'ended'
                self.json(200, {'viewer_down': state.viewer_down, 'no_live': state.no_live, 'stale': state.stale}); return
            if url.path == '/__fixture/advance':
                with state.lock:
                    state.visible = min(len(state.steps), state.visible + int(parse_qs(url.query).get('n', ['1'])[0]))
                self.json(200, {'visible': state.visible}); return
            if url.path == '/api/pause':
                # Like tools/campaign_watch.py: a Pause is never refused; a missing or unknown reason is 'unspecified'.
                try:
                    form = json.loads(raw or b'{}')
                except ValueError:
                    form = None
                given = form.get('reason') if isinstance(form, dict) and set(form) == {'reason'} else None
                with state.lock:
                    state.pauses.append({'reason': given if given in REASONS else 'unspecified'})
                self.json(200, dict(schema='computer-pause/1', session=SESSION,
                                    stop=dict(stop_requested=True, native_pause_confirmed=False,
                                              reason='Operator Pause')))
                return
            self.send_error(403)

    return Handler


def serve(port: int = 0, upstream: str | None = None):
    state = State(upstream)
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(state))
    return server, state


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--viewer', help='forward /api/view/* to a real viewer (http://127.0.0.1:port) instead of the fixtures')
    args = parser.parse_args(argv)
    server, _ = serve(args.port, args.viewer)
    print(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}/')), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
