"""Offline checks for prefix reservations and atomic spend admission."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import threading

import pytest

from harness.curator.proxy import IMAGE_TOKENS, ModelProxy, Price, body_token_bound, canonical_bytes
from tools.curator_host.providers import ANTHROPIC, OPENROUTER


MODEL = 'test-model'


def _proxy(tmp_path, *, cap='1', provider=OPENROUTER, price=None):
    return ModelProxy(provider=provider, upstream='http://127.0.0.1:1', key='offline',
                      prices={MODEL: price or Price(Decimal(1), Decimal(1))},
                      cap_usd=Decimal(cap), ledger=tmp_path/'ledger.jsonl')


def _reserve(proxy, request):
    receipt = {}
    amount = proxy._reserve(MODEL, canonical_bytes(request), 100, request, receipt=receipt)
    return amount, receipt.get('reservation_mode')


def _seed(proxy, request, usage=None, actual='0.00004', **outcome):
    reserve, mode = _reserve(proxy, request)
    assert isinstance(reserve, Decimal) and mode == 'full-bound'
    settled = dict(status=200, error=None, accounting_error=None)
    settled.update(outcome)
    proxy._settle(reserve, Decimal(actual), request=request,
                  usage={'prompt_tokens': 40} if usage is None else usage, **settled)


@pytest.fixture
def request_body():
    return dict(model=MODEL, service_tier='default', max_completion_tokens=100,
                provider=dict(only=['example'], order=['example']),
                tools=[dict(type='function', function=dict(name='read', parameters={'type': 'object'}))],
                messages=[dict(role='user', content='several paragraphs ' * 200)])


@pytest.mark.parametrize('change', ['tool', 'tier', 'provider', 'system', 'message', 'evicted', 'malformed', 'output'])
def test_prefix_compares_canonical_messages_and_every_prompt_header(tmp_path, request_body, change):
    proxy = _proxy(tmp_path)
    _seed(proxy, request_body)
    previous, = request_body['messages']
    extended = dict(request_body, messages=[dict(reversed(list(previous.items()))), dict(role='assistant', content='ok')])
    if change == 'tool':
        extended['tools'] = [dict(type='function', function=dict(name='write', parameters={'type': 'object'}))]
    elif change == 'tier':
        extended['service_tier'] = 'flex'
    elif change == 'provider':
        extended['provider'] = {'only': ['alternative']}
    elif change == 'system':
        extended['system'] = 'new instructions'
    elif change == 'message':
        extended['messages'][0]['content'] += ' edited'
    elif change == 'evicted':
        extended['messages'] = extended['messages'][1:]
    elif change == 'malformed':
        extended['messages'] = 'invalid'
    else:
        extended['max_completion_tokens'] = 200

    amount, mode = _reserve(proxy, extended)
    full = proxy.prices[MODEL].reservation(body_token_bound(MODEL, canonical_bytes(extended), extended), 100)
    if change == 'output':
        assert mode == 'prefix-suffix' and amount < full
    else:
        assert mode == 'full-bound' and amount == full


@pytest.mark.parametrize('usage,outcome', [
    ({'prompt_tokens': -1}, {}),
    ({'prompt_tokens': True}, {}),
    ({'completion_tokens': 5}, {}),
    ({'prompt_tokens': 20}, {'status': 400}),
    ({'prompt_tokens': 20}, {'error': 'TimeoutError'}),
    ({'prompt_tokens': 20}, {'accounting_error': 'ValueError'}),
])
def test_unsuccessful_or_unaccounted_prefix_is_never_used(tmp_path, request_body, usage, outcome):
    proxy = _proxy(tmp_path)
    _seed(proxy, request_body, usage, **outcome)
    assert _reserve(proxy, request_body)[1] == 'full-bound'


def test_generic_suffix_counts_image_and_anthropic_cache_tokens(tmp_path):
    proxy = _proxy(tmp_path, provider=ANTHROPIC)
    initial = dict(model=MODEL, max_tokens=100, messages=[dict(role='user', content='x' * 30_000)])
    _seed(proxy, initial, dict(input_tokens=180, cache_creation_input_tokens=200, cache_read_input_tokens=300))
    data = 'A' * 80_000
    suffix = [dict(role='user', content=[dict(type='image', source=dict(type='base64', media_type='image/png', data=data))])]
    amount, mode = _reserve(proxy, dict(initial, messages=initial['messages'] + suffix))
    expected = 680 + len(canonical_bytes(suffix)) - len(data) + IMAGE_TOKENS + 256 + 32
    assert mode == 'prefix-suffix'
    assert amount == proxy.prices[MODEL].reservation(expected, 100)


def test_prefix_reservation_uses_reachable_long_prompt_price_cliff(tmp_path, request_body):
    price = Price(Decimal(1), Decimal(1), long_prompt=(600, Price(Decimal(10), Decimal(20))))
    proxy = _proxy(tmp_path, price=price)
    _seed(proxy, request_body, {'prompt_tokens': 200})
    for content, above_cliff in [('x', False), ('x'*200, True)]:
        suffix = [dict(role='user', content=content)]
        extended = dict(request_body, messages=request_body['messages'] + suffix)
        amount, mode = _reserve(proxy, extended)
        bound = 200 + OPENROUTER.suffix_bound(MODEL, suffix, extended)
        assert (bound >= 600) == above_cliff
        assert mode == 'prefix-suffix' and amount == price.reservation(bound, 100)


def test_concurrent_prefix_reservations_do_not_overspend(tmp_path, request_body):
    proxy = _proxy(tmp_path, cap='0.0042')
    _seed(proxy, request_body, actual='0.00355')
    suffix = [dict(role='user', content='continue')]
    extended = dict(request_body, messages=request_body['messages'] + suffix)
    workers = 8
    ready = threading.Barrier(workers)

    def try_reserve():
        ready.wait(timeout=5)
        return _reserve(proxy, extended)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: try_reserve(), range(workers)))
    assert all(mode == 'prefix-suffix' for _, mode in results)
    accepted = [amount for amount, _ in results if isinstance(amount, Decimal)]
    assert len(accepted) == 1
    assert results.count(('spend cap reached', 'prefix-suffix')) == workers - 1
    assert proxy.spent + proxy.reserved <= proxy.cap < proxy.spent + 2 * accepted[0]
