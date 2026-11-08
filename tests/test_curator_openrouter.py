"""The curator proxy's OpenRouter chat-completions provider (#454): allowlist and settlement."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from harness.curator.proxy import OPENROUTER, ModelProxy, Price, refusal

ROUTE = '/api/v1/chat/completions'
MODEL = 'vendor/model-a'
PRICES = {MODEL: Price(input=Decimal(2), output=Decimal(10), cache_write=Decimal('2.5'), cache_read=Decimal('0.2'))}


def body(**extra):
    return {**dict(model=MODEL, stream=True, stream_options=dict(include_usage=True), max_completion_tokens=100,
                   messages=[dict(role='user', content='hi')]), **extra}


def sse(usage):
    chunks = [dict(id='g', object='chat.completion.chunk', choices=[dict(index=0, delta=dict(content='ok'))]),
              dict(id='g', object='chat.completion.chunk', choices=[], usage=usage)]
    return (b': OPENROUTER PROCESSING\n\n' + b''.join(b'data: ' + json.dumps(c).encode() + b'\n\n' for c in chunks)
            + b'data: [DONE]\n\n')


@contextmanager
def openrouter(tmp_path, usage, cap='1'):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            seen.append(dict(path=self.path, headers=dict(self.headers.items()),
                             body=json.loads(self.rfile.read(int(self.headers['content-length'])))))
            data = sse(usage)
            self.send_response(200)
            self.send_header('content-type', 'text/event-stream')
            self.send_header('content-length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

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


def post(port, payload, token):
    data = json.dumps(payload).encode()
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    connection.request('POST', ROUTE, body=data, headers={'authorization': f'Bearer {token}',
                                                          'content-type': 'application/json',
                                                          'x-session-id': 'curator-session'})
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, payload


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
        assert sent['authorization'] == 'Bearer real-router-key' and 'x-session-id' not in sent
        assert seen[0]['path'] == ROUTE
    ledger = (tmp_path/'ledger.jsonl').read_text()
    assert 'real-router-key' not in ledger and proxy.token not in ledger


def test_without_a_reported_cost_tokens_settle_at_the_highest_input_price(tmp_path):
    usage = dict(prompt_tokens=100, completion_tokens=20, total_tokens=120)
    with openrouter(tmp_path, usage) as (proxy, port, _seen):
        assert post(port, body(), proxy.token)[0] == 200
        assert proxy.spent == (100 * Decimal('2.5') + 20 * Decimal(10)) / Decimal(1_000_000)


def test_inline_images_reserve_a_bounded_token_count_not_their_encoding(tmp_path):
    from harness.curator.proxy import ANTHROPIC, IMAGE_TOKENS, inline_images
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
