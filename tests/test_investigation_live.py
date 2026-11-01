"""Finite live snapshots use real store/trace fixtures, without native custody."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from tests import test_investigation as closed_fixture
from harness.computer.protocol import ControlError
from tools.investigation import validate_bundle
from tools import investigation_live as live


@pytest.fixture
def case():
    fixture = closed_fixture.InvestigationTests()
    fixture.setUp()
    fixture.profile = dict(schema='campaign-run/3', session=fixture.session, source_commit='f' * 40)
    (fixture.case / 'manifest.json').write_text(json.dumps(fixture.profile))
    (fixture.case / 'actors/001/frozen.json').write_text(json.dumps(dict(
        schema='player-host-inputs/1', session=fixture.session, actor_id=fixture.actor,
        files={'actor.json': '0' * 64})))
    (fixture.case / 'receipt.json').unlink()
    (fixture.case / 'actors/001/actor.json').write_text('PRIVATE_TOKEN_DO_NOT_READ')
    try:
        yield fixture
    finally:
        fixture.doCleanups()


def capture(case, tmp_path):
    return live.snapshot_bundle(case.case, case.profile, tmp_path, time.monotonic() + 5)


def wait_ready(view):
    limit = time.monotonic() + 10
    result = view.snapshot()
    while result['state'] == 'loading' and time.monotonic() < limit:
        time.sleep(.01)
        result = view.snapshot()
    assert result['state'] != 'loading'
    return result


def test_live_original_joins_without_closed_receipt_or_secret_reads(case, tmp_path):
    real_open = Path.open
    def allow_selected(path, *args, **kwargs):
        assert path.name not in {'actor.json', 'route.json', 'mcp.json', 'context.txt', 'prompt.txt', 'receipt.json'}
        return real_open(path, *args, **kwargs)
    with patch.object(Path, 'open', new=allow_selected):
        bundle = capture(case, tmp_path)
    assert validate_bundle(bundle) is bundle
    result = bundle['cases'][0]
    assert result['session'] == case.session and result['source_commit'] == 'f' * 40
    assert all(value is None for value in result['accounting'].values())
    assert result['configuration'][0]['actor_id'] == case.actor
    assert next(e for e in result['events'] if e['kind'] == 'request')['actor_id'] == case.actor
    assert next(e for e in result['events'] if e['kind'] == 'program')['links'] == ['operation:op1']
    assert result['sources'][0]['source_id'] == case.source_id
    assert result['coverage']['observer_status'] == 'not_selected'
    encoded = json.dumps(bundle)
    assert 'PRIVATE_' not in encoded and str(case.root) not in encoded
    assert any('unknown' in note for note in result['coverage']['notes'])


def test_single_immutable_prefix_censors_pending_and_discloses_partial_tail(case, tmp_path):
    case.events = [row for row in case.events if row['type'] not in ('response-complete', 'tool-result', 'settled')]
    case.write_trace()
    path = case.case / 'actors/001/host.jsonl'
    prefix = path.read_bytes()
    path.write_bytes(prefix + b'{"type":"response-complete"')
    real_analyze = live.analyze_trace
    def analyze(frozen):
        assert frozen.read_bytes() == prefix
        with path.open('ab') as stream:
            stream.write(b',"request_id":"r1"}\n')
        return real_analyze(frozen)
    with patch.object(live, 'analyze_trace', side_effect=analyze):
        result = capture(case, tmp_path)['cases'][0]
    request = next(e for e in result['events'] if e['kind'] == 'request')
    tool = next(e for e in result['events'] if e['kind'] == 'tool')
    assert request['disposition'] == 'censored' and tool['disposition'] == 'pending'
    assert request['end_wall_ms'] is None and request['elapsed_ms'] is None
    assert any('incomplete' in note for note in result['coverage']['notes'])


def test_busy_lane_borrows_unused_capacity_without_losing_quiet_lanes(case, tmp_path):
    case.events = [case.events[0]]
    for i in range(2200):
        case.events.append(dict(type='assistant-text', text=f'statement-{i}', monotonic_ms=i + 1))
    case.write_trace()
    result = capture(case, tmp_path)['cases'][0]
    statements = [e for e in result['events'] if e['kind'] == 'statement']
    assert len(result['events']) == 2000
    assert len(statements) == 1997
    assert [e['text'] for e in statements] == [f'statement-{i}' for i in range(203, 2200)]
    assert {'operation', 'native', 'source'} <= {e['kind'] for e in result['events']}
    assert result['coverage']['event_candidates'] > 2000
    assert result['coverage']['event_omitted'] == 203


def test_every_candidate_survives_when_whole_case_fits(case, tmp_path):
    case.events = [case.events[0]] + [dict(type='assistant-text', text=f'statement-{i}', monotonic_ms=i + 1)
        for i in range(400)]
    case.write_trace()
    result = capture(case, tmp_path)['cases'][0]
    assert len(result['events']) == result['coverage']['event_candidates'] == 403
    assert result['coverage']['event_omitted'] == 0


def test_recent_request_cutoff_uses_original_start_order_not_pending_emission(case, tmp_path):
    case.events = [case.events[0], dict(type='request-start', request_id='old-pending', monotonic_ms=1)]
    for i in range(2010):
        case.events.extend([dict(type='request-start', request_id=f'request-{i}', monotonic_ms=2 + i * 2),
            dict(type='response-complete', request_id=f'request-{i}', monotonic_ms=3 + i * 2, stop_reason='stop')])
    case.write_trace()
    rows = capture(case, tmp_path)['cases'][0]['events']
    requests = [e['request_id'] for e in rows if e['kind'] == 'request']
    assert requests == [f'request-{i}' for i in range(13, 2010)]


@pytest.mark.parametrize('fault', ['version', 'session', 'actor_session', 'manifest', 'budget'])
def test_invalid_or_changed_input_is_unavailable(case, tmp_path, fault):
    if fault in ('version', 'session'):
        with sqlite3.connect(case.case / 'session.sqlite3') as db:
            if fault == 'version':
                db.execute('PRAGMA user_version=1')
            else:
                db.execute("UPDATE metadata SET value=? WHERE key='session'", (json.dumps('b' * 32),))
    if fault == 'actor_session':
        (case.case / 'actors/001/frozen.json').write_text(json.dumps(dict(
            schema='player-host-inputs/1', actor_id=case.actor, session='b' * 32, files={})))
    if fault == 'manifest':
        (case.case / 'manifest.json').write_text(json.dumps({**case.profile, 'source_commit': 'e' * 40}))
    context = patch.object(live, 'MAX_TRACE_BYTES', 1) if fault == 'budget' else patch.object(live, 'MAX_TRACE_BYTES', live.MAX_TRACE_BYTES)
    with context, pytest.raises((ControlError, TimeoutError)):
        capture(case, tmp_path)


def test_view_coalesces_stable_ready_and_explicit_refresh(case):
    view = live.LiveInvestigationView(case.case, case.profile)
    try:
        with patch.object(live.subprocess, 'Popen', wraps=subprocess.Popen) as launch:
            first = view.snapshot()
            assert first['state'] == 'loading'
            view.snapshot(refresh=True)
            ready = wait_ready(view)
            assert ready['state'] == 'ready' and launch.call_count == 1
            assert view.snapshot() == ready
            view.snapshot(refresh=True)
            assert wait_ready(view)['state'] == 'ready' and launch.call_count == 2
            kwargs = launch.call_args.kwargs
            assert kwargs['close_fds'] is True and kwargs.get('pass_fds', ()) == ()
            assert kwargs['stdin'] == subprocess.DEVNULL and kwargs['stderr'] == subprocess.DEVNULL
            assert not set(kwargs['env']) & {'OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'HOME', 'DYLD_INSERT_LIBRARIES'}
    finally:
        view.close()
    assert view.snapshot()['state'] == 'unavailable'
    assert not list((live.ROOT / '.runtime').glob('investigation-live-*'))


def test_timeout_close_and_stdout_budget_reap_exact_child_and_cleanup(case):
    real_popen = subprocess.Popen
    for behavior in ('sleep', 'flood', 'close'):
        children = []
        def launch(*args, **kwargs):
            code = "import time;time.sleep(30)" if behavior != 'flood' else "import sys;sys.stdout.write('x'*100000);sys.stdout.flush();import time;time.sleep(30)"
            child = real_popen([sys.executable, '-c', code], **kwargs)
            children.append(child)
            return child
        with patch.object(live.subprocess, 'Popen', side_effect=launch), \
                patch.object(live, 'JOB_SECONDS', .4), patch.object(live, 'MAX_STDOUT_BYTES', 2000):
            view = live.LiveInvestigationView(case.case, case.profile)
            started = time.monotonic()
            view.snapshot()
            if behavior == 'close':
                while not children and time.monotonic() - started < 1:
                    time.sleep(.005)
                view.close()
                result = view.snapshot()
            else:
                result = wait_ready(view)
                view.close()
            assert result['state'] == 'unavailable' and len(result['error']) <= 600
            assert result['bundle'] is None and time.monotonic() - started < 2
            assert children and children[0].poll() is not None
            assert view._thread is None or not view._thread.is_alive()
    assert not list((live.ROOT / '.runtime').glob('investigation-live-*'))


def test_latest_three_exact_images_and_missing_source_never_substitute(case, tmp_path):
    with sqlite3.connect(case.case / 'session.sqlite3') as db:
        for i in range(2, 6):
            identity = case.session + '-' + str(i)
            metadata = {**case.metadata, 'source_id': identity, 'capture_id': i}
            db.execute('INSERT INTO sources VALUES(?,?,?)', (identity, json.dumps(metadata), len(case.png)))
            if i != 4:
                (case.case / 'sources' / (identity + '.png')).write_bytes(case.png)
    result = capture(case, tmp_path)['cases'][0]
    assert [row['capture_id'] for row in result['sources']] == [3, 4, 5]
    assert result['sources'][0]['png_base64'] == result['sources'][2]['png_base64']
    assert result['sources'][1]['png_base64'] is None
    assert result['sources'][1]['unavailable_reason']
    assert result['coverage']['source_candidates'] == 5 and result['coverage']['source_omitted'] == 2


def test_missing_actor_is_unknown_and_unselected_siblings_are_never_read(case, tmp_path):
    (case.case / 'actors/001/frozen.json').unlink()
    sibling = case.case / 'actors/003'
    sibling.mkdir()
    (sibling / 'frozen.json').write_text('INVALID_PRIVATE_UNSELECTED_METADATA')
    (sibling / 'host.jsonl').write_text('INVALID_PRIVATE_UNSELECTED_TRACE')
    result = capture(case, tmp_path)['cases'][0]
    assert result['configuration'][0]['actor_id'] is None
    assert next(e for e in result['events'] if e['kind'] == 'request')['actor_id'] is None
    assert any('Original actor ID is not recorded' in note for note in result['coverage']['notes'])


def test_busy_database_and_expired_backup_deadline_do_not_publish_success(case, tmp_path):
    with sqlite3.connect(case.case / 'session.sqlite3') as db:
        db.execute('BEGIN EXCLUSIVE')
        started = time.monotonic()
        with pytest.raises(ControlError):
            capture(case, tmp_path)
        assert time.monotonic() - started < 1
    with pytest.raises(TimeoutError):
        live.snapshot_bundle(case.case, case.profile, tmp_path, time.monotonic() - 1)


def test_error_is_generic_stable_and_can_be_explicitly_refreshed(case):
    (case.case / 'manifest.json').write_text('PRIVATE_ERROR_PATH ' + str(case.root))
    view = live.LiveInvestigationView(case.case, case.profile)
    try:
        result = wait_ready(view)
        assert result['state'] == 'unavailable' and result['bundle'] is None
        assert result['error'] == live.ERROR and result['snapshot_wall_ms'] is None
        assert view.snapshot() == result
        (case.case / 'manifest.json').write_text(json.dumps(case.profile))
        assert view.snapshot() == result
        assert view.snapshot(refresh=True)['state'] == 'loading'
        assert wait_ready(view)['state'] == 'ready'
    finally:
        view.close()


def test_campaign_injects_view_and_closes_after_server_before_stores(tmp_path):
    from unittest.mock import Mock
    from tests.test_campaign_run import package
    from tools import campaign_run

    directory, profile = package(tmp_path)
    order = []
    owner = Mock()
    owner.process.pid = 123
    owner.close.return_value = dict(native_absence_verified=True, normal_native_exit_zero=False)
    memory = Mock()
    memory.close.side_effect = lambda: order.append('memory')
    runtime = Mock()
    runtime.store.close.side_effect = lambda: order.append('store')
    application = Mock()
    view = Mock()
    view.close.side_effect = lambda: order.append('view')
    server = Mock()
    server.server_close.side_effect = lambda: order.append('server')
    def serve(app, port):
        assert app.investigation_view is view
        return server, Mock()
    driver = dict(schema='player-driver/2', actors=[], outcome='incomplete', attempts_charged=0,
        configured_estimate_usd=0, missing_usage_attempts=0)
    with patch.object(campaign_run, 'preflight', return_value=(profile, dict(api_key_env='OFFLINE_KEY'), {})), \
            patch.dict('os.environ', {'OFFLINE_KEY': 'PRIVATE_TOKEN'}), \
            patch.object(campaign_run, 'OwnedTarget', return_value=owner), \
            patch.object(campaign_run, 'Memory', return_value=memory), \
            patch.object(campaign_run, 'ComputerRuntime', return_value=runtime), \
            patch.object(campaign_run, 'Application', return_value=application), \
            patch.object(campaign_run, 'LiveInvestigationView', return_value=view), \
            patch.object(campaign_run, 'serve', side_effect=serve), \
            patch.object(campaign_run, 'run_hosts', return_value=driver):
        result = campaign_run.run_campaign(directory)
    assert 'reason' not in result
    assert order == ['server', 'view', 'store', 'memory']


def test_eight_recent_lanes_fill_but_never_exceed_2000_rows(case, tmp_path):
    from collections import Counter
    case.events = [case.events[0]]
    for i in range(260):
        request, tool, at = f'r-{i}', f't-{i}', i * 10
        projection = dict(schema='player-program-run/1', program_id='version', run_id=f'run-{i}',
            status='yield', elapsed_seconds=.01, operations=[])
        case.events.extend([
            dict(type='request-start', request_id=request, monotonic_ms=at + 1),
            dict(type='response-complete', request_id=request, monotonic_ms=at + 2, stop_reason='toolUse'),
            dict(type='tool-start', request_id=request, tool_call_id=tool, monotonic_ms=at + 3),
            dict(type='tool-result', request_id=request, tool_call_id=tool, monotonic_ms=at + 4,
                result=dict(content=[dict(type='text', text=json.dumps(projection))])),
            dict(type='assistant-text', text=f'claim-{i}', monotonic_ms=at + 5),
            dict(type='context-image-projection', monotonic_ms=at + 6, projection_ms=1)])
    case.write_trace()
    with sqlite3.connect(case.case / 'session.sqlite3') as db:
        for i in range(260):
            source_id = case.session + '-' + str(i + 2)
            db.execute('INSERT INTO sources VALUES(?,?,?)', (source_id,
                json.dumps({**case.metadata, 'source_id': source_id, 'capture_id': i + 2}), len(case.png)))
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)',
                (f'op-{i}', case.actor, 'observe', i + 2, 10000, 'PRIVATE_ARGS', None))
            db.execute('INSERT INTO native_intents VALUES(?,?,?,?,?)',
                (f'native-{i}', f'op-{i}', None, source_id, '{}'))
    result = capture(case, tmp_path)['cases'][0]
    counts = Counter(row['kind'] for row in result['events'])
    assert set(counts.values()) == {250} and len(counts) == 8
    assert len(result['events']) == 2000
    assert result['coverage']['event_candidates'] == 2083
    assert result['coverage']['event_omitted'] == 83
