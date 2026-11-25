"""The per-actor HTTP adapter's uncertainty fence and handoff sealing, with the service replies stubbed."""
import json
from unittest.mock import patch

import pytest

from harness.player_client import PlayerClient

SESSION, ACTOR, HANDOFF = 'a' * 32, 'b' * 32, 'c' * 32


@pytest.fixture
def client(tmp_path):
    config = tmp_path / 'actor.json'
    config.write_text(json.dumps(dict(schema='player-adapter/2', base_url='http://127.0.0.1:9', session=SESSION,
                                      actor_id=ACTOR, token='t' * 32)))
    return PlayerClient(config)


def operation(status, handoff=None):
    return dict(schema='computer-operation/1', operation_id=HANDOFF, session=SESSION, actor_id=ACTOR, kind='handoff',
                status=status, handoff=handoff)


def sealed():
    return operation('sealed', dict(schema='player-handoff/1', operation_id=HANDOFF, session=SESSION, actor_id=ACTOR,
                                    context_id='d' * 32, context_sha256='e' * 64, sealed_wall=1., grants_authority=False))


def replies(*values):
    """`_post` answering each tool call in turn; every actor stop is recorded."""
    stops = []
    queue = list(values)

    def post(path, value, **kwargs):
        if path == '/api/actor-stop':
            stops.append(value['reason'])
            return dict(stop_requested=True)
        reply = queue.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply
    return post, stops


@pytest.mark.parametrize('status', ['pending', 'unknown'])
def test_a_handoff_the_service_reports_pending_or_unknown_seals_on_its_collection(client, status):
    """R-REGRESSION (#946): only a lost reply armed the pending handoff, so a pending or unknown
    service result never sealed the adapter, and closing it stopped the actor after a sealed handoff."""
    post, stops = replies(dict(schema='player-response/1', value=operation(status)),
                          dict(schema='player-response/1', value=sealed()))
    with patch.object(client, '_post', side_effect=post):
        value, _, error = client.call('player_handoff', dict(intent='Hand off', summary='unfinished'))
        assert (value['status'], error, client.sealed) == (status, False, False)
        assert client.call('computer_result', dict(intent='Collect', operation_id=HANDOFF))[0]['status'] == 'sealed'
        assert client.sealed
        client.close()
    assert stops == []


def test_a_collection_of_another_operation_does_not_seal(client):
    other = dict(sealed(), operation_id='f' * 32)
    other['handoff'] = dict(other['handoff'], operation_id='f' * 32)
    post, _ = replies(dict(schema='player-response/1', value=operation('pending')),
                      dict(schema='player-response/1', value=other))
    with patch.object(client, '_post', side_effect=post):
        client.call('player_handoff', dict(intent='Hand off', summary='unfinished'))
        client.call('computer_result', dict(intent='Collect', operation_id='f' * 32))
    assert not client.sealed


@pytest.mark.parametrize('reply', [[], None, 'text', 7])
def test_a_reply_that_is_not_a_json_object_is_an_uncertain_operation(client, reply):
    """R-REGRESSION (#946): a JSON array or null raised AttributeError past the uncertainty fence, so
    no stop was sent and the model lost the original operation ID."""
    post, stops = replies(reply)
    with patch.object(client, '_post', side_effect=post):
        value, png, error = client.call('computer_input', dict(intent='Press', actions=[]))
    assert (value['schema'], value['status'], value['collect_with'], png, error) == (
        'player-transport/1', 'unknown', 'computer_result', None, False)
    assert len(stops) == 1


@pytest.mark.parametrize('tool', ['computer_result', 'player_result'])
def test_a_failed_collection_names_the_original_and_its_own_collector(client, tool):
    """R-REGRESSION (#946): a lost collection reply advertised this request's fresh ID and, for
    computer_result, the wrong collector."""
    post, stops = replies(OSError('lost reply'))
    with patch.object(client, '_post', side_effect=post):
        value, _, error = client.call(tool, dict(intent='Collect', operation_id=HANDOFF))
    assert (value['operation_id'], value['collect_with'], value['status'], error) == (HANDOFF, tool, 'unknown', False)
    # Collection sends no input, so it fences nothing.
    assert stops == []


def test_stop_requests_join_shares_one_monotonic_deadline():
    """R-REGRESSION (#946): joining multiple slow stop threads must share one deadline, not timeout per thread."""
    import threading
    import time
    from harness.player_mcp import StopRequests

    block = threading.Event()
    class SlowClient:
        def stop(self, reason):
            block.wait(timeout=2.0)

    stops = StopRequests(SlowClient())
    for _ in range(3):
        stops.request('cancel')
    started = time.monotonic()
    stops.join(timeout=0.15)
    elapsed = time.monotonic() - started
    block.set()
    assert elapsed < 0.35, f'expected shared ~0.15s deadline, took {elapsed:.3f}s'
