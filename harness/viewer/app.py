"""Loopback, read-only HTTP routes for the spectator viewer."""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Callable

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from harness.evaluation.core.records import EvaluationError
from harness.spectator_assets import PAGE_POLICY, WEB, static_file

from . import cross, views, knowledge, curator, curator_ops, delivered, feed as story, telemetry
from . import frame as frame_view
from .catalog import API, MAX_RESPONSE_BYTES, Catalog, RunInfo, ViewError
from .live import LiveEvaluator

MAX_BYTES = MAX_RESPONSE_BYTES
MAX_LIMIT = 500
DEFAULT_LIMIT = 100
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
LOOPBACK_HOSTS = ('127.0.0.1', 'localhost', '::1')


# Withhold absolute filesystem paths in producer diagnostics and free-text fields.
HOST_PATH = re.compile(r"""(?<![\w:/])(?:/(?![/\s])|[A-Za-z]:[\\/])[^\s'"\x60,;)}\]<>]+""")


def public(value):
    if isinstance(value, dict):
        return {HOST_PATH.sub('[path withheld]', key) if isinstance(key, str) else key: public(item)
                for key, item in value.items()
                if key != 'record' or not isinstance(item, str) or not any(c in item for c in ('/', chr(92)))}
    if isinstance(value, (list, tuple)):
        return [public(item) for item in value]
    if isinstance(value, str):
        return HOST_PATH.sub('[path withheld]', value)
    return value


def reply(payload: dict, status: int = 200) -> Response:
    body = json.dumps(public(dict(payload, schema=API)), separators=(',', ':'), allow_nan=False, default=str).encode()
    if len(body) > MAX_BYTES:
        raise ViewError(413, 'response_too_large', f'{len(body)} bytes')
    return Response(body, status, headers=HEADERS, media_type='application/json')


def paging(request: Request) -> tuple[int, int]:
    def number(name: str, default: int, low: int, high: int | None) -> int:
        raw = request.query_params.get(name)
        if raw is None or raw == '':
            return default
        try:
            value = int(raw)
        except ValueError:
            raise ViewError(400, f'bad_{name}', f'{name} must be an integer') from None
        if value < low or (high is not None and value > high):
            raise ViewError(400, f'bad_{name}', f'{name} must be {low}..{high if high is not None else "any"}')
        return value
    return number('after', 0, 0, None), number('limit', DEFAULT_LIMIT, 1, MAX_LIMIT)


def create_app(catalog: Catalog, evaluator: LiveEvaluator | None = None, now: Callable[[], float] | None = None,
               frame_sources: frame_view.FrameSources | None = None, *, recorded_page: bool = False) -> Starlette:
    import time
    clock = now or time.time
    sources = frame_sources or frame_view.FrameSources()

    def live_session() -> str | None:
        return evaluator.session() if evaluator is not None else None

    def with_run(handler: Callable[..., Any]) -> Callable[[Request], Response]:
        def endpoint(request: Request) -> Response:
            try:
                info = catalog.find(request.path_params['run'])
                connection = catalog.connect(info)
                try:
                    return handler(request, info, connection)
                finally:
                    connection.close()
            except ViewError as error:
                return error_reply(error)
            except (EvaluationError, sqlite3.Error, OSError, ValueError, RecursionError):
                return error_reply(ViewError(500, 'view_unavailable'))
        return endpoint

    def plain(handler: Callable[[Request], Response]) -> Callable[[Request], Response]:
        def endpoint(request: Request) -> Response:
            try:
                return handler(request)
            except ViewError as error:
                return error_reply(error)
            except (EvaluationError, sqlite3.Error, OSError, ValueError, RecursionError):
                return error_reply(ViewError(500, 'view_unavailable'))
        return endpoint

    def error_reply(error: ViewError) -> Response:
        return reply(dict(error=error.code, detail=error.detail[:1024]), error.status)

    def view_path(request: Request) -> bool:
        return request.url.path == '/api/view' or request.url.path.startswith('/api/view/')

    async def routing_error(request: Request, exc: HTTPException) -> Response:
        if not view_path(request):
            return PlainTextResponse(exc.detail, status_code=exc.status_code, headers=exc.headers)
        code, detail = ('not_found', 'route not found') if exc.status_code == 404 else ('method_not_allowed', 'method not allowed')
        response = error_reply(ViewError(exc.status_code, code, detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    def runs(request: Request) -> Response:
        after, limit = paging(request)
        live = live_session()
        rows = [views.run_row(info, live) for info in catalog.runs()]
        window = rows[after:after + limit + 1]
        more = len(window) > limit
        return reply(dict(items=window[:limit], next=after + limit if more else None, limit=limit, total=len(rows),
            skipped_non_current=catalog.skipped_non_current()))

    def summary(request: Request, info: RunInfo, connection) -> Response:
        mine = evaluator is not None and info.session == live_session()
        is_live = mine and info.state == 'live'
        # A final store of the live run is served read-only; the evaluator status says live evaluation stopped.
        body = views.summary(catalog, info, connection, is_live, evaluator.status if mine else None, clock())
        host = telemetry.read(info)
        return reply(dict(body, host_telemetry=telemetry.summary(host), agenda=telemetry.agenda_summary(info, host),
            curator_spend=telemetry.curator_spend(info),
            boundary_grooming=telemetry.boundary_grooming(info, sources.curator_grooming)))

    def feed(request: Request, info: RunInfo, connection) -> Response:
        after, limit = paging(request)
        return reply(story.feed(info, connection, after, limit))

    def telemetry_(request: Request, info: RunInfo, connection) -> Response:
        return reply(telemetry.telemetry(info, connection))

    def delivered_knowledge(request: Request, info: RunInfo, connection) -> Response:
        after, limit = paging(request)
        query = request.query_params
        return reply(delivered.browse(catalog, info, connection, query.get('version') or None, query.get('q') or None,
            query.get('scope') or None, after, limit, kind=query.get('kind')))

    def steps(request: Request, info: RunInfo, connection) -> Response:
        after, limit = paging(request)
        return reply(views.steps(connection, after, limit))

    def frame(request: Request, info: RunInfo, connection) -> Response:
        data = views.frame(catalog, info, connection, request.path_params['source_id'])
        return Response(data, headers={'Cache-Control': 'private, max-age=31536000, immutable', 'X-Content-Type-Options': 'nosniff'},
            media_type='image/png')

    def tools(request: Request, info: RunInfo, connection) -> Response:
        return reply(views.tools(connection))

    def calls(request: Request, info: RunInfo, connection) -> Response:
        after, limit = paging(request)
        status = request.query_params.get('status') or None
        if status not in (None, 'ok', 'error', 'refused'):
            raise ViewError(400, 'bad_status', 'status must be ok, error or refused')
        return reply(views.calls(connection, request.query_params.get('tool') or None, status, after, limit))

    def requests_(request: Request, info: RunInfo, connection) -> Response:
        after, limit = paging(request)
        return reply(views.requests(connection, after, limit))

    def context(request: Request, info: RunInfo, connection) -> Response:
        return reply(views.context(catalog, info, connection, request.path_params['request_id'],
            request.query_params.get('actor') or None))

    def memory(request: Request, info: RunInfo, connection) -> Response:
        return reply(views.memory(catalog, info, connection))

    def knowledge_(request: Request, info: RunInfo, connection) -> Response:
        after, limit = paging(request)
        return reply(knowledge.projection(catalog, info, connection, request.query_params.get('actor') or None,
            request.query_params.get('request') or None, after, limit, request.query_params.get('entry') or None))

    def handoffs(request: Request, info: RunInfo, connection) -> Response:
        return reply(views.handoffs(catalog, info, connection))

    def changes(request: Request) -> Response:
        return reply(cross.changes(catalog, catalog.runs()))

    def failures(request: Request) -> Response:
        return reply(cross.failures(catalog, catalog.runs()))

    def compare(request: Request) -> Response:
        try:
            horizon = float(request.query_params.get('horizon', '0.5'))
        except ValueError:
            raise ViewError(400, 'bad_horizon') from None
        return reply(cross.compare(catalog, request.query_params.get('group', 'arm'), request.query_params.get('runs'), horizon))

    def explore(request: Request) -> Response:
        q = request.query_params
        return reply(cross.explore(catalog, q.get('arm') or None, q.get('start') or None, q.get('outcome') or None,
            q.get('metric') or None, live_session()))

    def frame_containers(request: Request) -> Response:
        after, limit = paging(request)
        return reply(frame_view.containers(sources, after, limit))

    def frame_container(request: Request) -> Response:
        return reply(frame_view.container(sources, request.path_params['container_id']))

    def frame_episodes(request: Request) -> Response:
        return reply(frame_view.episodes(catalog, sources))

    def source_labels(request: Request, configured) -> Response:
        after, limit = paging(request)
        return reply(dict(items=[dict(label=label) for label, _ in configured[after:after + limit]],
                                total=len(configured), next=after + limit if after + limit < len(configured) else None,
                                limit=limit))

    def curator_sources(request: Request) -> Response:
        return source_labels(request, sources.curator_results)

    def curator_results(request: Request) -> Response:
        after, limit = paging(request)
        return reply(curator.results(sources.curator_results, request.query_params.get('source'),
                                           after, limit, request.query_params.get('snapshot')))

    def curator_session_sources(request: Request) -> Response:
        return source_labels(request, sources.curator_sessions)

    def curator_session(request: Request) -> Response:
        after, limit = paging(request)
        return reply(curator.session(sources.curator_sessions, request.query_params.get('source'),
                                           after, limit, request.query_params.get('snapshot')))

    def curator_draft_sources(request: Request) -> Response:
        return source_labels(request, sources.curator_drafts)

    def curator_drafts(request: Request) -> Response:
        after, limit = paging(request)
        return reply(curator.drafts(sources.curator_drafts, request.query_params.get('source'),
                                         after, limit, request.query_params.get('snapshot')))

    def run_curator(request: Request, info: RunInfo, connection) -> Response:
        return reply(curator_ops.run_curator(info, sources, clock(), info.session == live_session() and info.state == 'live'))

    def run_curator_session(request: Request, info: RunInfo, connection) -> Response:
        return reply(curator_ops.run_curator_session(info, request.path_params['session_id']))

    prefix = '/api/view'
    routes = [Route(f'{prefix}/curator-sources/draft-sources', plain(curator_draft_sources), methods=['GET']),
        Route(f'{prefix}/curator-sources/drafts', plain(curator_drafts), methods=['GET']),
        Route(f'{prefix}/curator-sources/session-sources', plain(curator_session_sources), methods=['GET']),
        Route(f'{prefix}/curator-sources/session', plain(curator_session), methods=['GET']),
        Route(f'{prefix}/curator-sources/result-sources', plain(curator_sources), methods=['GET']),
        Route(f'{prefix}/curator-sources/results', plain(curator_results), methods=['GET']),
        Route(f'{prefix}/archive/containers', plain(frame_containers), methods=['GET']),
        Route(f'{prefix}/archive/containers/{{container_id:path}}', plain(frame_container), methods=['GET']),
        Route(f'{prefix}/archive/episodes', plain(frame_episodes), methods=['GET']),
        Route(f'{prefix}/runs', plain(runs), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/summary', with_run(summary), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/steps', with_run(steps), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/frame/{{source_id}}', with_run(frame), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/tools', with_run(tools), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/calls', with_run(calls), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/requests', with_run(requests_), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/context/{{request_id}}', with_run(context), methods=['GET']),
        Route(f'{prefix}/archive/run/{{run}}/memory', with_run(memory), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/knowledge', with_run(knowledge_), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/feed', with_run(feed), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/telemetry', with_run(telemetry_), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/delivered-knowledge', with_run(delivered_knowledge), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/curator', with_run(run_curator), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/curator/session/{{session_id:path}}', with_run(run_curator_session), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/handoffs', with_run(handoffs), methods=['GET']),
        Route(f'{prefix}/improve/changes', plain(changes), methods=['GET']),
        Route(f'{prefix}/improve/failures', plain(failures), methods=['GET']),
        Route(f'{prefix}/compare', plain(compare), methods=['GET']),
        Route(f'{prefix}/explore', plain(explore), methods=['GET'])]
    if recorded_page:
        if evaluator is not None:
            raise ValueError('Recorded page requires an offline viewer')

        def asset(request: Request) -> Response:
            page = request.url.path == '/recorded/'
            found = static_file(WEB, '/' if page else request.url.path, recorded=page)
            if found is None:
                return Response(status_code=404)
            data, media = found
            return Response(data, media_type=media, headers={**HEADERS, 'Content-Security-Policy': PAGE_POLICY})

        routes.extend(Route(path, asset, methods=['GET']) for path in (
            '/recorded/', '/app/{file:path}', '/vendor/{file:path}'))

    app = Starlette(routes=routes, exception_handlers={404: routing_error, 405: routing_error})
    async def local_only(request: Request, call_next):
        api = view_path(request)
        if api or recorded_page:
            host = request.headers.get('host', '')
            try:
                local = bool(host) and request.url.hostname in LOOPBACK_HOSTS
            except ValueError:
                local = False
            if not local or request.headers.get('origin', f'http://{host}') != f'http://{host}':
                return error_reply(ViewError(403, 'loopback_required')) if api else Response(status_code=403)
        return await call_next(request)

    app.router.redirect_slashes = False
    app.add_middleware(BaseHTTPMiddleware, dispatch=local_only)
    app.state.catalog = catalog
    app.state.evaluator = evaluator
    return app
