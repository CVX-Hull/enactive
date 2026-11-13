"""The curator proxy's OpenRouter chat-completions provider (#454): allowlist and settlement."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import struct
import threading

import pytest

from harness.curator.proxy import ModelProxy, Price, refusal
from tools.curator_host.providers import ANTHROPIC, OPENROUTER, reported_cost

ROUTE = '/api/v1/chat/completions'
MODEL = 'vendor/model-a'
PRICES = {MODEL: Price(input=Decimal(2), output=Decimal(10), cache_write=Decimal('2.5'), cache_read=Decimal('0.2'))}


def body(**extra):
    return {**dict(model=MODEL, service_tier='default', stream=True, stream_options=dict(include_usage=True), max_completion_tokens=100,
                   messages=[dict(role='user', content='hi')]), **extra}


def sse(usage):
    chunks = [dict(id='g', object='chat.completion.chunk', choices=[dict(index=0, delta=dict(content='ok'))]),
              dict(id='g', object='chat.completion.chunk', choices=[], usage=usage)]
    return (b': OPENROUTER PROCESSING\n\n' + b''.join(b'data: ' + json.dumps(c).encode() + b'\n\n' for c in chunks)
            + b'data: [DONE]\n\n')


@contextmanager
def openrouter(tmp_path, usage, cap='1', *, broken=False, entered=None, release=None):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            seen.append(dict(path=self.path, headers=dict(self.headers.items()),
                             body=json.loads(self.rfile.read(int(self.headers['content-length'])))))
            if entered is not None:
                entered.set()
            if release is not None:
                assert release.wait(10), 'local response was never released'
            data = usage if isinstance(usage, bytes) else sse(usage)
            self.send_response(200)
            self.send_header('content-type', 'text/event-stream')
            if broken:
                self.send_header('transfer-encoding', 'chunked')
            else:
                self.send_header('content-length', str(len(data)))
            self.end_headers()
            self.wfile.write(b'100\r\nshort' if broken else data)
            if broken:
                self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    proxy = ModelProxy(provider=OPENROUTER, upstream=f'http://127.0.0.1:{server.server_port}', key='real-router-key',
                       prices=PRICES, cap_usd=Decimal(cap), ledger=tmp_path/'ledger.jsonl', max_output_tokens=4096)
    port = proxy.start()
    try:
        yield proxy, port, seen
    finally:
        proxy.close()
        server.shutdown()
        server.server_close()


def post(port, payload, token, extra=None):
    data = json.dumps(payload).encode()
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    connection.request('POST', ROUTE, body=data, headers={'authorization': f'Bearer {token}',
                                                          'content-type': 'application/json',
                                                          'x-session-id': 'curator-session', **(extra or {})})
    try:
        response = connection.getresponse()
        payload = response.read()
        return response.status, payload
    finally:
        connection.close()


REFUSED = {
    'web search plugin': body(plugins=[dict(id='web')]),
    'fallback models': body(models=['other/model']),
    'fallback route': body(route='fallback'),
    'raw prompt': dict(model=MODEL, prompt='hi', max_completion_tokens=10),
    'debug echo': body(debug=dict(echo_upstream_body=True)),
    'remote image': body(messages=[dict(role='user', content=[
        dict(type='image_url', image_url=dict(url='https://example.com/x.png'))])]),
    'remote image as string': body(messages=[dict(role='user', content=[
        dict(type='image_url', image_url='https://example.com/x.png')])]),
    'file part': body(messages=[dict(role='user', content=[dict(type='file', file=dict(file_data='x'))])]),
    'audio part': body(messages=[dict(role='user', content=[dict(type='input_audio', input_audio={})])]),
    'non-function tool': body(tools=[dict(type='web_search')]),
    'routing that sorts by price': body(provider=dict(sort='price')),
    'stored response': body(store=True),
}


@pytest.mark.parametrize('case', sorted(REFUSED))
def test_openrouter_requests_that_could_fetch_route_or_store_are_refused(case):
    assert refusal(OPENROUTER, json.loads(json.dumps(REFUSED[case])))


def test_the_shapes_pi_sends_for_an_openrouter_model_pass():
    allowed = body(
        reasoning=dict(effort='medium'), store=False,
        provider=dict(only=['vendor'], order=['vendor'], allow_fallbacks=False, require_parameters=True),
        tools=[dict(type='function', function=dict(name='read_file', description='d',
                                                   parameters=dict(type='object', properties={})))],
        tool_choice='auto',
        messages=[
            dict(role='system', content='brief'),
            dict(role='user', content=[dict(type='text', text='look', cache_control=dict(type='ephemeral')),
                                       dict(type='image_url', image_url=dict(url='data:image/png;base64,AA=='))]),
            dict(role='assistant', content=None, reasoning_details=[
                dict(type='reasoning.encrypted', data='opaque', id='r1', format='x', index=0),
                dict(type='reasoning.summary', summary='s', index=1)],
                 tool_calls=[dict(id='c1', type='function', function=dict(name='read_file', arguments='{}'))]),
            dict(role='tool', tool_call_id='c1', content='file text')])
    assert refusal(OPENROUTER, allowed) is None


@pytest.mark.parametrize('tier', [None, 'auto', 'priority', 'flex', 'fast', '', {}, True])
def test_only_an_explicit_default_service_tier_is_allowed(tier):
    assert refusal(OPENROUTER, body(service_tier=tier)) == 'the default service tier must be explicitly requested'


def test_omitting_the_tier_cannot_inherit_a_workspace_default():
    request = body()
    del request['service_tier']
    assert refusal(OPENROUTER, request) == 'the default service tier must be explicitly requested'


def test_an_unpriced_or_online_model_is_refused_before_reaching_openrouter(tmp_path):
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12, cost=0.0001)
    with openrouter(tmp_path, usage) as (proxy, port, seen):
        for model in ('vendor/model-a:online', 'other/model'):
            assert post(port, dict(body(), model=model), proxy.token)[0] == 429
        assert seen == []


def test_the_reported_cost_settles_and_the_key_never_leaves_the_proxy(tmp_path):
    # The reservation is about $0.0015 (body bytes at $2.5/MTok plus 100 output tokens at $10/MTok).
    usage = dict(prompt_tokens=100, completion_tokens=20, total_tokens=120, cost=0.00042,
                 prompt_tokens_details=dict(cached_tokens=80), completion_tokens_details=dict(reasoning_tokens=5))
    with openrouter(tmp_path, usage) as (proxy, port, seen):
        status, payload = post(port, body(), proxy.token)
        assert status == 200 and b'[DONE]' in payload
        assert proxy.spent == Decimal('0.00042') and not proxy.revoked
        sent = {k.lower(): v for k, v in seen[0]['headers'].items()}
        # The host's own affinity value ('curator-session') is never forwarded; the proxy's is.
        assert sent['authorization'] == 'Bearer real-router-key' and sent['x-session-id'] == proxy.affinity != 'curator-session'
        assert seen[0]['path'] == ROUTE
        assert seen[0]['body']['service_tier'] == 'default'
    ledger = (tmp_path/'ledger.jsonl').read_text()
    assert 'real-router-key' not in ledger and proxy.token not in ledger and proxy.affinity not in ledger


def test_version_and_frozen_beta_headers_pass_as_they_always_did(tmp_path):
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12, cost=0.0001)
    with openrouter(tmp_path, usage) as (proxy, port, seen):
        proxy.betas = frozenset({'allowed-beta'})
        extra = {'anthropic-version': '2026-10-21', 'anthropic-beta': 'allowed-beta,unlisted-beta', 'x-other': 'no'}
        assert post(port, body(), proxy.token, extra)[0] == 200
        sent = {k.lower(): v for k, v in seen[0]['headers'].items()}
        assert sent['anthropic-version'] == '2026-10-21' and sent['anthropic-beta'] == 'allowed-beta'
        assert 'x-other' not in sent and sent['accept-encoding'] == 'identity'
    assert json.loads((tmp_path/'ledger.jsonl').read_text())['dropped_betas'] == ['unlisted-beta']


def test_context_management_is_not_an_openrouter_field():
    assert 'context_management' in refusal(OPENROUTER, body(context_management=dict(edits=[])))


def test_one_affinity_value_per_proxy_session_on_every_request(tmp_path):
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12, cost=0.0001)
    with openrouter(tmp_path, usage) as (proxy, port, seen):
        for _ in range(3):
            assert post(port, body(), proxy.token)[0] == 200
        values = {{k.lower(): v for k, v in entry['headers'].items()}['x-session-id'] for entry in seen}
        assert values == {proxy.affinity} and len(seen) == 3
        # Not the session token, and not a function a reader of the ledger can invert to it.
        assert proxy.affinity != proxy.token and proxy.token not in proxy.affinity
    rows = [json.loads(line) for line in (tmp_path/'ledger.jsonl').read_text().splitlines()]
    assert {row['affinity_sha256'] for row in rows} == {proxy.affinity_digest} and proxy.affinity_digest != proxy.affinity
    (tmp_path/'other').mkdir()
    with openrouter(tmp_path/'other', usage) as (second, _port, _seen):
        assert second.affinity != proxy.affinity


def test_without_a_reported_cost_tokens_settle_at_the_highest_input_price(tmp_path):
    usage = dict(prompt_tokens=100, completion_tokens=20, total_tokens=120)
    with openrouter(tmp_path, usage) as (proxy, port, _seen):
        assert post(port, body(), proxy.token)[0] == 200
        assert proxy.spent == (100 * Decimal('2.5') + 20 * Decimal(10)) / Decimal(1_000_000)


def test_inline_images_reserve_a_bounded_token_count_not_their_encoding(tmp_path):
    from harness.curator.proxy import IMAGE_TOKENS, inline_images
    frame = 'A' * 280_000                                      # a 280 KB base64 frame
    request = body(messages=[dict(role='user', content=[
        dict(type='text', text='look'), dict(type='image_url', image_url=dict(url=f'data:image/png;base64,{frame}')),
        dict(type='image_url', image_url=dict(url=f'data:image/png;base64,{frame}'))])])
    assert inline_images(request) == (2 * (len(frame) + len('data:image/png;base64,')), 2)
    nested = dict(messages=[dict(role='user', content=[dict(type='tool_result', content=[
        dict(type='image', source=dict(type='base64', media_type='image/png', data=frame))])])])
    assert inline_images(nested) == (len(frame), 1) and inline_images(None) == (0, 0)
    assert refusal(ANTHROPIC, dict(nested, model='m', max_tokens=1)) is None
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12, cost=0.0001)
    with openrouter(tmp_path, usage) as (proxy, port, seen):
        assert post(port, request, proxy.token)[0] == 200
        reserved = Decimal(json.loads((tmp_path/'ledger.jsonl').read_text())['reserved'])
        encoded = len(json.dumps(request, separators=(',', ':')).encode())
        expected = ((encoded - inline_images(request)[0] + 2 * IMAGE_TOKENS) * Decimal('2.5') + 100 * 10) / Decimal(1_000_000)
        assert reserved == expected and reserved < Decimal('0.06')  # not the ~$1.40 the raw bytes would reserve
        assert len(seen) == 1


def test_a_bring_your_own_key_route_settles_at_the_upstream_charge_too():
    byok = sse(dict(prompt_tokens=10, completion_tokens=2, cost=0.00001, is_byok=True,
                    cost_details=dict(upstream_inference_cost=0.5)))
    assert reported_cost(byok) == Decimal('0.50001')
    routed = sse(dict(prompt_tokens=10, completion_tokens=2, cost=0.002, cost_details=dict(upstream_inference_cost=0.0019)))
    assert reported_cost(routed) == Decimal('0.002')
    with pytest.raises(ValueError, match='invalid reported cost'):
        reported_cost(sse(dict(prompt_tokens=1, cost='free', cost_details=dict(upstream_inference_cost=-1))))


# The player host reads reported cost by the same rule in Node, so both suites run one file of usage
# records (#555, R-OVERSPEND); its other reader is tools/player_host/test/reported-cost.test.mjs.
SHARED_COSTS = json.loads((Path(__file__).parent/'fixtures'/'provider-usage-cost.json').read_text())['cases']


@pytest.mark.parametrize('case', SHARED_COSTS, ids=[case['name'] for case in SHARED_COSTS])
def test_shared_usage_records_give_the_reported_cost_the_player_host_gives(case):
    # json.dumps writes each number at its shortest exact text, and infinity as the token the proxy's
    # reader takes for a non-finite number. (A literal 1e999 on the wire would reach it as a finite Decimal.)
    response = sse(case['usage'])
    if case['curator'] == 'error':
        # Where the curator refuses a record, the player host records no cost; neither guesses one.
        assert case['player_host'] is None
        with pytest.raises(ValueError):
            reported_cost(response)
    else:
        assert reported_cost(response) == (None if case['curator'] is None else Decimal(case['curator']))
        assert case['player_host'] == case['curator']


def test_only_image_blocks_are_discounted_as_images():
    from harness.curator.proxy import inline_images
    big = 'A' * 600_000
    smuggled = [
        dict(messages=[dict(role='assistant', content=[dict(type='tool_use', id='t', name='n', input=dict(
            source=dict(type='base64', media_type='image/png', data=big)))])]),
        dict(messages=[dict(role='user', content=[dict(type='image_url', image_url=f'data:text/plain;base64,{big}')])]),
        dict(messages=[dict(role='user', content=[dict(type='text', text='x', image_url=f'data:image/png;base64,{big}')])]),
        dict(messages=[dict(role='user', content=[dict(type='image', source=dict(type='base64', media_type='text/plain', data=big))])]),
    ]
    for request in smuggled:
        assert inline_images(request) == (0, 0), request


def test_the_proxy_requires_the_pinned_routing(tmp_path):
    pinned = dict(only=['vendor'], order=['vendor'], allow_fallbacks=False, require_parameters=True)
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12, cost=0.0001)
    with openrouter(tmp_path, usage) as (proxy, port, seen):
        proxy.routing = pinned
        for routing in (None, dict(pinned, allow_fallbacks=True), dict(pinned, only=['other'], order=['other'])):
            payload = body() if routing is None else body(provider=routing)
            assert post(port, payload, proxy.token)[0] == 400
        assert seen == []
        assert post(port, body(provider=pinned), proxy.token)[0] == 200 and len(seen) == 1


def test_an_image_billed_above_its_bound_still_revokes(tmp_path):
    usage = dict(prompt_tokens=50_000, completion_tokens=2, total_tokens=50_002)  # no reported cost: tokens settle
    request = body(messages=[dict(role='user', content=[
        dict(type='image_url', image_url=dict(url='data:image/png;base64,' + 'A' * 1000))])])
    with openrouter(tmp_path, usage) as (proxy, port, _seen):
        assert post(port, request, proxy.token)[0] == 200
        assert proxy.breaches == 1 and proxy.revoked


def test_a_reported_cost_above_the_reservation_revokes_the_session(tmp_path):
    usage = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12, cost=5)
    with openrouter(tmp_path, usage, cap='10') as (proxy, port, seen):
        assert post(port, body(), proxy.token)[0] == 200
        assert proxy.breaches == 1 and proxy.revoked
        assert post(port, body(), proxy.token)[0] == 429 and len(seen) == 1


@pytest.mark.parametrize(('response', 'accounting_error'), [
    (b'{"message":"malformed"}', None),
    (b'{"response":["malformed"]}', None),
    (b'{"usage":{"cost":1e99999999999999999999999999}}', 'InvalidOperation'),
    (b'{"usage":{"prompt_tokens":1,"cost":1e1000000}}', 'unrepresentable-cost'),
    (b'{"usage":{"prompt_tokens":"invalid","completion_tokens":0}}', 'ValueError'),
    (b'{"usage":{"prompt_tokens":-1,"completion_tokens":0}}', 'ValueError'),
    (b'{"usage":{"prompt_tokens":true,"completion_tokens":0}}', 'ValueError'),
    (b'{"usage":{"prompt_tokens":1,"completion_tokens":0,"cost":-1}}', 'ValueError'),
    (b'{"usage":{"prompt_tokens":1,"completion_tokens":0,"cost":[]}}', 'ValueError'),
    (b'{"usage":{"prompt_tokens":1,"completion_tokens":0,"cost":0.001,"is_byok":true}}', 'ValueError'),
])
def test_malformed_or_unrepresentable_accounting_keeps_the_reservation_and_revokes(tmp_path, response, accounting_error):
    with openrouter(tmp_path, response) as (proxy, port, seen):
        assert post(port, body(), proxy.token)[0] == 200
        row = json.loads(proxy.ledger.read_text())
        assert row['usage_missing'] and row['charged'] == row['reserved']
        assert row.get('accounting_error') == accounting_error
        assert proxy.spent == Decimal(row['reserved']) > 0 and proxy.reserved == 0 and proxy.revoked
        assert post(port, body(), proxy.token)[0] == 429 and len(seen) == 1


@pytest.mark.parametrize(('metadata', 'code', 'expected_type', 'expected_code'), [
    ({'error_type': 'provider_unavailable', 'raw': 'SECRET raw'}, 502, 'provider_unavailable', 502),
    ({'error_type': 'SECRET-type'}, True, None, None),
    (['SECRET malformed metadata'], {'SECRET': 'code'}, None, None),
])
def test_stream_error_classification_keeps_only_allowlisted_provider_fields(tmp_path, metadata, code, expected_type, expected_code):
    response = b'data: ' + json.dumps({'error': {'message': 'SECRET provider text', 'code': code, 'metadata': metadata}}).encode() + b'\n\n'
    with openrouter(tmp_path, response) as (proxy, port, _seen):
        assert post(port, body(), proxy.token)[0] == 200
        row = json.loads(proxy.ledger.read_text())
        assert row['response_error'] == {'kind': 'provider-error-event', 'error_type': expected_type, 'error_code': expected_code}
        assert 'SECRET' not in proxy.ledger.read_text()
        assert proxy.revoked and row['usage_missing'] and row['charged'] == row['reserved']


def test_a_truncated_upstream_http200_keeps_its_actual_status_and_conservative_charge(tmp_path):
    with openrouter(tmp_path, b'', broken=True) as (proxy, port, _seen):
        with pytest.raises(http.client.IncompleteRead):
            post(port, body(), proxy.token)
        row = json.loads(proxy.ledger.read_text())
        assert row['status'] == 200 and row['error'] == 'IncompleteRead'
        assert row['charged'] == row['reserved'] and row['usage_missing'] and proxy.revoked


def test_an_oversized_response_stops_with_its_reservation_instead_of_growing_the_buffer(tmp_path, monkeypatch):
    from harness.curator import proxy as proxy_module
    monkeypatch.setattr(proxy_module, 'MAX_RESPONSE', 64)
    with openrouter(tmp_path, b'x' * 65) as (proxy, port, _seen):
        with pytest.raises(http.client.IncompleteRead):
            post(port, body(), proxy.token)
        row = json.loads(proxy.ledger.read_text())
        assert row['status'] == 200 and row['error'] == 'ResponseTooLarge'
        assert row['usage_missing'] and row['charged'] == row['reserved'] and proxy.revoked


@pytest.mark.parametrize('missing', [False, True])
def test_close_observes_late_settlement_and_real_revocation_without_creating_an_incident(tmp_path, monkeypatch, missing):
    entered, release, closing = threading.Event(), threading.Event(), threading.Event()
    usage = {} if missing else dict(prompt_tokens=10, completion_tokens=2, cost=.0001)
    with openrouter(tmp_path, usage, entered=entered, release=release) as (proxy, port, _seen):
        results, closures = [], []
        request = threading.Thread(target=lambda: results.append(post(port, body(), proxy.token)))
        request.start()
        closer = None
        try:
            assert entered.wait(5)
            shutdown = proxy._server.shutdown

            def started_close():
                closing.set()
                shutdown()

            monkeypatch.setattr(proxy._server, 'shutdown', started_close)
            closer = threading.Thread(target=lambda: closures.append(proxy.close()))
            closer.start()
            assert closing.wait(5) and proxy._closed
            release.set()
            request.join(5)
            closer.join(5)
            assert not request.is_alive() and not closer.is_alive()
            closure, row = closures[0], json.loads(proxy.ledger.read_text())
            assert closure['settled'] and closure['unsettled_requests'] == 0 and Decimal(closure['pending_reserved_usd']) == 0
            assert closure['revoked'] is missing
            assert Decimal(closure['spent_snapshot_usd']) == Decimal(row['charged']) > 0
            assert results[0][0] == 200
            assert proxy._reserve(MODEL, json.dumps(body()).encode(), 100, body()) == 'session token revoked'
        finally:
            release.set()
            request.join(10)
            if closer is not None:
                closer.join(10)


@pytest.mark.parametrize('phase', ['upstream', 'ledger'])
def test_close_timeout_keeps_pending_reservation_or_unwritten_receipt_explicit(tmp_path, monkeypatch, phase):
    from harness.curator import proxy as proxy_module
    monkeypatch.setattr(proxy_module, 'CLOSE_TIMEOUT', .01)
    entered, release = threading.Event(), threading.Event()
    usage = dict(prompt_tokens=10, completion_tokens=2, cost=.0001)
    with openrouter(tmp_path, usage, entered=entered if phase == 'upstream' else None,
                    release=release if phase == 'upstream' else None) as (proxy, port, _seen):
        if phase == 'ledger':
            record = proxy._record

            def delayed_record(**fields):
                entered.set()
                assert release.wait(10)
                record(**fields)

            monkeypatch.setattr(proxy, '_record', delayed_record)
        request = threading.Thread(target=lambda: post(port, body(), proxy.token))
        request.start()
        try:
            assert entered.wait(5)
            closure = proxy.close()
            assert not closure['settled'] and closure['unsettled_requests'] == 1
            assert (Decimal(closure['pending_reserved_usd']) > 0) is (phase == 'upstream')
            assert closure['receipt_error'] is None and proxy._closed
        finally:
            release.set()
            request.join(10)
        assert not request.is_alive()
        assert proxy.close()['settled']  # later reconciliation does not reopen admission or renew the run
        assert closure['settled'] is False  # the original incomplete receipt is retained


def test_a_stall_inside_ledger_open_cannot_block_admission_shutdown_or_its_timeout(tmp_path, monkeypatch):
    from harness.curator import proxy as proxy_module
    monkeypatch.setattr(proxy_module, 'CLOSE_TIMEOUT', .01)
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    with openrouter(tmp_path, dict(prompt_tokens=10, completion_tokens=2, cost=.0001)) as (proxy, port, _seen):
        path = proxy.ledger

        class BlockingLedger:
            @contextmanager
            def open(self, *args, **kwargs):
                with path.open(*args, **kwargs) as stream:
                    entered.set()
                    assert release.wait(10)
                    yield stream

        proxy.ledger = BlockingLedger()
        closures = []

        def close():
            try:
                closures.append(proxy.close())
            finally:
                done.set()

        request = threading.Thread(target=lambda: post(port, body(), proxy.token))
        request.start()
        closer = None
        try:
            assert entered.wait(5)
            closer = threading.Thread(target=close)
            closer.start()
            assert done.wait(3), 'ledger I/O held the admission/accounting lock'
            assert proxy._closed and not closures[0]['settled'] and closures[0]['unsettled_requests'] == 1
            assert Decimal(closures[0]['pending_reserved_usd']) == 0  # money settled; its receipt is still blocked
        finally:
            release.set()
            request.join(10)
            if closer is not None:
                closer.join(10)
            proxy.ledger = path
        assert not request.is_alive() and json.loads(path.read_text())['status'] == 200


@pytest.mark.parametrize('failed_method', ['_record', '_settle'])
@pytest.mark.parametrize('error_type', [OSError, ConnectionResetError])
def test_accounting_failure_is_latched_after_the_active_request_finishes(tmp_path, monkeypatch, capsys,
                                                                        failed_method, error_type):
    usage = dict(prompt_tokens=10, completion_tokens=2, cost=.0001)
    with openrouter(tmp_path, usage) as (proxy, port, _seen):
        def fail(*args, **kwargs):
            raise error_type('fixture receipt failure')

        monkeypatch.setattr(proxy, failed_method, fail)
        with pytest.raises(http.client.IncompleteRead):
            post(port, body(), proxy.token)
        closure = proxy.close()
        assert not closure['settled'] and closure['unsettled_requests'] == 0
        assert closure['receipt_error'] == error_type.__name__ and closure['revoked']
        assert (Decimal(closure['pending_reserved_usd']) > 0) is (failed_method == '_settle')
    assert 'fixture receipt failure' in capsys.readouterr().err  # Active failures are not hidden as idle resets.


def reset_connection(connection):
    connection.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
    connection.close()


def test_idle_keepalive_reset_is_quiet_after_its_accounting_is_complete(tmp_path, monkeypatch, capsys):
    with openrouter(tmp_path, dict(prompt_tokens=10, completion_tokens=2, cost=.0001)) as (proxy, port, _seen):
        finished = threading.Event()
        handler = proxy._server.RequestHandlerClass
        original = handler.handle

        def observe(self):
            try:
                original(self)
            finally:
                finished.set()

        monkeypatch.setattr(handler, 'handle', observe)
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        payload = json.dumps(body())
        connection.request('POST', ROUTE, payload, {'authorization': f'Bearer {proxy.token}',
                                                 'content-type': 'application/json'})
        response = connection.getresponse()
        assert response.status == 200 and response.read()
        reset_connection(connection)
        assert finished.wait(5)
        closure = proxy.close()
        assert closure['settled'] and not closure['revoked']
        assert Decimal(closure['spent_snapshot_usd']) == Decimal('.0001')
        assert len(proxy.ledger.read_text().splitlines()) == 1
    assert 'ConnectionResetError' not in capsys.readouterr().err


def test_client_reset_before_response_headers_still_drains_and_settles(tmp_path):
    entered, release = threading.Event(), threading.Event()
    with openrouter(tmp_path, dict(prompt_tokens=10, completion_tokens=2, cost=.0001),
                    entered=entered, release=release) as (proxy, port, _seen):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request('POST', ROUTE, json.dumps(body()), {'authorization': f'Bearer {proxy.token}',
                                                           'content-type': 'application/json'})
        try:
            assert entered.wait(5)
            reset_connection(connection)
        finally:
            release.set()
            connection.close()
        closure = proxy.close()
        assert closure['settled'] and not closure['revoked']
        assert Decimal(closure['spent_snapshot_usd']) == Decimal('.0001')
        row = json.loads(proxy.ledger.read_text())
        assert row['status'] == 200 and not row['usage_missing'] and not row['breach']
