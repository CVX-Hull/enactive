"""The read-only spectator viewer: every `spectator-view/1` route (docs/contracts/evaluation.md).

All routes are GET. JSON responses carry `"schema": "spectator-view/1"`, stay under 4 MiB and are paginated with
`after` and `limit` (at most 500) where they list. The application writes nothing; the only write in the process
is the live evaluator's own `live` store, which the app merely reports on.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from . import cross, views
from .catalog import API, Catalog, RunInfo, ViewError
from .live import LiveEvaluator

MAX_BYTES = 4 * 1024 * 1024
MAX_LIMIT = 500
DEFAULT_LIMIT = 100
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}


def reply(payload: dict, status: int = 200) -> Response:
    body = json.dumps(dict(schema=API, **payload), separators=(',', ':'), allow_nan=False, default=str).encode()
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


def create_app(catalog: Catalog, evaluator: LiveEvaluator | None = None, now: Callable[[], float] | None = None) -> Starlette:
    import time
    clock = now or time.time

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
        return endpoint

    def plain(handler: Callable[[Request], Response]) -> Callable[[Request], Response]:
        def endpoint(request: Request) -> Response:
            try:
                return handler(request)
            except ViewError as error:
                return error_reply(error)
        return endpoint

    def error_reply(error: ViewError) -> Response:
        return Response(json.dumps(dict(schema=API, error=error.code, detail=error.detail)), error.status, headers=HEADERS,
            media_type='application/json')

    def runs(request: Request) -> Response:
        after, limit = paging(request)
        live = live_session()
        rows = [views.run_row(info, live) for info in catalog.runs()]
        window = rows[after:after + limit + 1]
        more = len(window) > limit
        return reply(dict(items=window[:limit], next=after + limit if more else None, limit=limit, total=len(rows)))

    def summary(request: Request, info: RunInfo, connection) -> Response:
        mine = evaluator is not None and info.session == live_session()
        is_live = mine and info.state == 'live'
        # A final store of the live run is served read-only; the evaluator status says live evaluation stopped.
        return reply(views.summary(catalog, info, connection, is_live, evaluator.status if mine else None, clock()))

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

    def programs(request: Request, info: RunInfo, connection) -> Response:
        return reply(views.programs(catalog, info, connection))

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

    prefix = '/api/view'
    routes = [Route(f'{prefix}/runs', plain(runs), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/summary', with_run(summary), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/steps', with_run(steps), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/frame/{{source_id}}', with_run(frame), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/tools', with_run(tools), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/calls', with_run(calls), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/requests', with_run(requests_), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/context/{{request_id}}', with_run(context), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/memory', with_run(memory), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/programs', with_run(programs), methods=['GET']),
        Route(f'{prefix}/run/{{run}}/handoffs', with_run(handoffs), methods=['GET']),
        Route(f'{prefix}/improve/changes', plain(changes), methods=['GET']),
        Route(f'{prefix}/improve/failures', plain(failures), methods=['GET']),
        Route(f'{prefix}/compare', plain(compare), methods=['GET']),
        Route(f'{prefix}/explore', plain(explore), methods=['GET'])]
    app = Starlette(routes=routes)
    app.state.catalog = catalog
    app.state.evaluator = evaluator
    return app
