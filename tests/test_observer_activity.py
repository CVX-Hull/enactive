"""Passive real-record projections; these fixtures do not qualify gameplay UI."""
import json
import threading
from http.client import HTTPConnection
from unittest.mock import patch

import pytest

from harness.observer import BYTE_LIMIT, ActivityView
from tools.campaign_player import HostEvents
from test_computer_runtime import make_runtime, key
from test_server import service, post


def get(port, path):
    connection = HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


@pytest.mark.parametrize('broken', ['missing', 'corrupt'])
def test_spectator_verifies_pixels_without_actor_failure_fencing(service, broken):
    app, channel, actor, port, client = service
    result, png, _ = client.call('computer_observe', {})
    source = result['source']
    status, retained = get(port, '/api/source/' + source['source_id'])
    assert status == 200 and retained == png
    path = app.runtime.directory / 'sources' / (source['source_id'] + '.png')
    if broken == 'missing':
        path.unlink()
    else:
        path.write_bytes(b'not verified PNG bytes')
    before = app.runtime.remaining()
    assert get(port, '/api/source/' + source['source_id'])[0] == 400
    assert not channel.stopped.is_set()
    assert app.runtime.remaining()['inputs'] == before['inputs']
    # Integrity is still a required actor boundary, not silently relaxed.
    with pytest.raises(ValueError):
        app.runtime.source(source['source_id'])
    assert channel.stopped.is_set()


def test_live_activity_links_actual_operations_sources_and_retains_no_input_args(service):
    app, channel, actor, port, client = service
    original, _, _ = client.call('computer_observe', {})
    client.call('computer_input', {'actions': [key('x')]})
    before = len(channel.calls), app.runtime.store.counts()
    status, body = get(port, '/api/activity')
    data = json.loads(body)
    assert status == 200 and data['schema'] == 'observer-activity/1'
    row = next(r for r in data['entries'] if r['operation_id'] == original['operation_id'])
    assert row['session'] == app.runtime.session and row['actor_id'] == actor['actor_id']
    assert row['source'] == original['source'] and row['original_dispositions'] == ['delivered']
    assert len(data['entries']) == data['coverage']['computer_operations'] == 2
    assert data['coverage']['host'] == 'not-started'
    assert 'input_json' not in body.decode() and '"actions"' not in body.decode()
    assert (len(channel.calls), app.runtime.store.counts()) == before
    assert get(port, '/api/activity?history=1')[0] == 400
    assert not channel.stopped.is_set()


def test_host_projection_keeps_original_actor_scoped_links_not_raw_payloads(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        view = ActivityView(runtime.session, runtime.store.path)
        value, _ = runtime.observe(actor['actor_id'])
        for player in ('first', 'second'):
            view.host_event(player, 1, dict(type='tool-start', request_id='request-1',
                tool_call_id='tool-1', tool='computer_input', arguments={'secret': 'raw-private-value'}))
        view.host_event('first', 2, dict(type='tool-result', request_id='request-1',
            tool_call_id='tool-1', tool='computer_observe', result={'content': [
                {'type': 'text', 'text': json.dumps(value)}]}))
        data = view.snapshot()
        host = [r for r in data['entries'] if r['producer'] == 'host']
        assert len({r['id'] for r in host}) == 3
        assert host[-1]['operation_id'] == value['operation_id']
        assert host[-1]['source'] == value['source']
        assert 'raw-private-value' not in json.dumps(data)
        assert host[0]['created_wall'] is None
    finally:
        runtime.close()


def test_narration_tail_byte_bounds_and_explicit_projection_gaps(tmp_path):
    runtime, _, _ = make_runtime(tmp_path)
    try:
        view = ActivityView(runtime.session, runtime.store.path)
        for ordinal in range(250):
            view.host_event('player', ordinal, dict(type='assistant-text', request_id=f'request-{ordinal}',
                text='é' * 9000, omitted_bytes=23))
        data = view.snapshot()
        assert len((json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n').encode()) <= BYTE_LIMIT
        assert len(data['entries']) <= 200
        assert data['omitted_entries'] == 250 - len(data['entries'])
        statement = data['latest_statement']
        assert statement['omitted_bytes'] == 23
        assert len(statement['text'].encode()) == 8192 and statement['display_omitted_bytes'] == 9808
        assert data['entries'][-1]['id'] == statement['id']
        view.host_event('player', 251, dict(type='assistant-text', text='bad count', omitted_bytes=-1))
        view.host_event('player', 252, dict(type='request-start', request_id='request-251'))
        assert view.snapshot()['coverage']['host_projection_errors'] == 1
        assert view.snapshot()['coverage']['host'].startswith('unavailable:')
    finally:
        runtime.close()


def test_missing_computer_projection_is_an_observer_gap_not_stop(service):
    app, channel, actor, port, client = service
    with patch.object(app.activity_view, '_computer_rows', side_effect=OSError('fixture missing DB')):
        status, body = get(port, '/api/activity')
    data = json.loads(body)
    assert status == 200 and data['coverage']['computer'] == 'unavailable:OSError'
    assert data['coverage']['computer_operations'] is None
    assert data['omitted_entries'] is None
    assert not channel.stopped.is_set()


def test_pause_is_independent_of_blocked_activity_read(service):
    app, channel, actor, port, client = service
    entered, release = threading.Event(), threading.Event()
    result = []
    def blocked():
        entered.set()
        assert release.wait(3)
        return [], 0
    with patch.object(app.activity_view, '_computer_rows', side_effect=blocked):
        worker = threading.Thread(target=lambda: result.append(get(port, '/api/activity')))
        worker.start()
        try:
            assert entered.wait(2)
            status, value = post(port, '/api/pause', {})
            assert status == 200 and value['stop']['stop_requested']
            assert value['session'] == app.runtime.session and channel.stopped.is_set()
            assert worker.is_alive()  # Stop completed while activity is blocked.
        finally:
            release.set()
            worker.join(3)
    assert result[0][0] == 200


def test_partial_host_lines_keep_original_accounting_and_single_projection(tmp_path):
    path = tmp_path / 'host.jsonl'
    path.write_text(json.dumps(dict(type='host-start', telemetry_version=2)) + '\n' + '{"type":"request-start"')
    received = []
    events = HostEvents(path, 10, observer=lambda ordinal, row: received.append((ordinal, row['type'])))
    try:
        assert events.read() and received == [(1, 'host-start')]
        assert events.finish()['attempts_charged'] == 10
        with path.open('a') as stream:
            stream.write(',"request_id":"request-1"}\n' + json.dumps(dict(type='settled', requests=1)) + '\n')
        assert events.finish()['attempts_charged'] == 1
        assert received == [(1, 'host-start'), (2, 'request-start'), (3, 'settled')]
    finally:
        events.close()


def test_activity_does_not_rewrite_original_unknown_after_late_collection(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        channel.unknown = True
        original, _ = runtime.input(actor['actor_id'], [key()])
        native_id = original['receipts'][0]['id']
        channel.late[native_id] = (dict(schema='computer-receipt/2', id=native_id,
            session=runtime.session, disposition='delivered', emitted_events=2,
            reason='Late original evidence', frame=None), None)
        runtime.result(actor['actor_id'], original['operation_id'])
        data = ActivityView(runtime.session, runtime.store.path).snapshot()
        row = data['entries'][0]
        assert row['status'] == 'unknown'
        assert row['original_dispositions'] == ['unknown']
        assert row['additional_collection_dispositions'] == ['delivered']
        assert channel.stopped.is_set() and len(channel.calls) == 1
    finally:
        runtime.close()


def test_producer_order_survives_wall_clock_rollback_and_tail_eviction(tmp_path):
    runtime, _, _ = make_runtime(tmp_path)
    try:
        view = ActivityView(runtime.session, runtime.store.path)
        for ordinal in range(205):
            view.host_event('actor', ordinal, dict(type='request-start' if ordinal % 2 == 0 else 'response-complete',
                request_id=f'request-{ordinal // 2}', monotonic_ms=ordinal,
                wall_time='2026-10-29T10:00:10Z' if ordinal % 2 == 0 else '2026-10-29T10:00:00Z'))
        data = view.snapshot()
        assert [row['monotonic_ms'] for row in data['entries']] == list(range(5, 205))
        assert data['omitted_entries'] == 5
        assert data['entries'][-1]['id'] == 'host:actor:204'
    finally:
        runtime.close()
