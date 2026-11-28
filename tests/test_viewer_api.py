"""The read-only spectator viewer (ADR008, spectator-view/4) over synthetic runs and a pure fake binding.

Every route is exercised through Starlette's TestClient: schema, bounds, pagination, frame digest refusal, no
write methods, Pause conditions (met and clear) and incremental live evaluation. These tests establish the API
contract, not any game reader.
"""
from __future__ import annotations

from functools import partial
import json
import hashlib
from pathlib import Path
import time

import pytest
from starlette.testclient import TestClient as StarletteTestClient

from harness.evaluation.core.pipeline import evaluate
from harness.evaluation.core.records import CORE_VERSION, open_readonly, read_metadata
from harness.evaluation.core.sources import MANIFEST_SCHEMA, MAX_JSON_FILE_BYTES, RECEIPT_SCHEMA, archive_sessions
from harness.player.contracts import PlayerError
from harness.player.knowledge import Knowledge
from harness.viewer.app import MAX_BYTES, create_app
from harness.viewer.catalog import API, ID_LIMIT, LIST_LIMIT, TEXT_LIMIT, Catalog
from harness.viewer.frame import FrameSources
from harness.viewer.live import LiveEvaluator
from harness.viewer.pause import dollars_per_minute, looping_streak
from tests.legacy_player_store import legacy_player_archive
from tests.test_evaluation_core import (BASE, F, FakeBinding, LIMITS, MULTI_DAY_SESSIONS, Run, SESSION, ended_run, growing_run, iso, key,
    main_scenario, memory_scenario)


TestClient = partial(StarletteTestClient, base_url='http://127.0.0.1')


def data_directory(tmp_path: Path, **overrides) -> Path:
    directory = tmp_path / 'data'
    directory.mkdir(exist_ok=True)
    files = dict(
        taxonomy=dict(version=1, codes=[dict(code='stall', name='Stall', definition='d', examples=[]),
            dict(code='death', name='Death', definition='d', examples=[]),
            dict(code='identity_or_world_error', name='Identity', definition='d', examples=[])]),
        changes=[dict(id='aid', name='Aid', arms=['aid*'], baseline=['base*'], commits=[], hypothesis='h', target_failure='stall',
            target_metric=dict(name='stall.longest', direction='lower', min_effect=1),
            uptake_metric=dict(name='memory.writes', key=''), guards=[dict(name='survival.game_hours', key='')],
            verdict='untested', notes='n'),
            dict(id='unused', name='Unused', arms=['aid*'], baseline=[], commits=[], hypothesis='h', target_failure='stall',
                target_metric=dict(name='stall.longest', direction='lower', min_effect=1), uptake_metric=None, guards=[],
                verdict='untested', notes='n')],
        validation=dict(mode=dict(version=1, accuracy=0.94, n=219, floor=0.97, **{'pass': False}, sample='first sample'),
            clock=dict(version=1, accuracy=1.0, n=115, floor=0.98, **{'pass': True}, sample='held out')))
    files.update(overrides)
    for name, file in (('taxonomy', 'taxonomy.json'), ('changes', 'changes.json'), ('validation', 'reader-validation.json')):
        (directory / file).write_text(json.dumps(files[name]))
    (directory / 'labels.jsonl').write_text(json.dumps(dict(id='l1', session='a' * 32, seq_start=0, seq_end=0, target='x',
        code='identity_or_world_error', verdict='confirm', note='n', author='o', date='2026-11-06', taxonomy_version=1)) + '\n')
    return directory


@pytest.fixture
def archive(tmp_path):
    """Three finished runs: a death, and two censored runs of different arms, all evaluated into one root."""
    runs = tmp_path / 'runs'
    sessions = {'base1': 'a' * 32, 'base2': 'b' * 32, 'aid1': 'c' * 32, 'aid2': 'd' * 32}
    labels = {'base1': dict(arm='base', start='S1'), 'base2': dict(arm='base', start='S2'),
        'aid1': dict(arm='aid', start='S1'), 'aid2': dict(arm='aid', start='S2')}
    for name, session in sessions.items():
        if name == 'base1':
            main_scenario(runs / name, session=session)
        else:
            ended_run(runs / name, session=session, settled=dict(ok=False, reason='provider-error') if name == 'aid2' else None)
        evaluate(runs / name, FakeBinding(), tmp_path / 'root', created_wall=1.0, labels=dict(labels[name], scenario='s',
            lineage=None, admission=None))
    catalog = Catalog(tmp_path / 'root', (runs,), data_dir=data_directory(tmp_path))
    return TestClient(create_app(catalog)), catalog, runs


def run_routes(session: str) -> list[str]:
    base = f'/api/view/run/{session}'
    return [f'{base}/summary', f'{base}/steps', f'{base}/tools', f'{base}/calls', f'{base}/requests', f'/api/view/archive/run/{session}/memory',
        f'{base}/curator', f'{base}/handoffs', f'{base}/feed', f'{base}/telemetry', f'{base}/delivered-knowledge']


CROSS_ROUTES = ['/api/view/runs', '/api/view/improve/changes', '/api/view/improve/failures', '/api/view/compare?group=arm',
    '/api/view/compare?group=start&runs=base1,aid1', '/api/view/explore', '/api/view/explore?arm=base&metric=stall.longest']


def test_recorded_page_is_opt_in_read_only_and_loopback(archive):
    api, catalog, _ = archive
    assert api.get('/recorded/').status_code == 404
    assert api.get('/app/main.js').status_code == 404
    base = 'http://127.0.0.1:8765'
    with TestClient(create_app(catalog, recorded_page=True), base_url=base) as client:
        response = client.get('/recorded/', headers={'Origin': base})
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/html')
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert "default-src 'self'" in response.headers['content-security-policy']
        assert '/app/main.js' in response.text and '/app/theme.js' in response.text
        assert all(markup not in response.text for markup in ('/app/control.js', 'id="pause"', 'id="sheet"'))
        for path in ('/app/main.js', '/app/app.css', '/vendor/preact.js', '/api/view/runs'):
            assert client.get(path).status_code == 200, path
        for path in ('/', '/index.html', '/README.md', '/app/%2e%2e/index.html', '/vendor/PROVENANCE.md',
                     '/api/status', '/api/source/unknown', '/api/pause'):
            assert client.get(path).status_code == 404, path
        assert client.post('/api/pause', json={'reason': 'other'}).status_code == 404
        assert client.post('/recorded/').status_code == 405
        assert client.post('/recorded/').headers['content-type'].startswith('text/plain')
        for path in ('/recorded/', '/api/view/runs'):
            assert client.get(path, headers={'Origin': 'https://other.example'}).status_code == 403
            assert client.get(path, headers={'Host': 'other.example:8765'}).status_code == 403


@pytest.mark.parametrize(('method', 'path', 'status', 'error', 'detail'), [
    ('GET', '/api/view/no-such-route', 404, 'not_found', 'route not found'),
    ('POST', '/api/view/curator-sources/drafts', 405, 'method_not_allowed', 'method not allowed'),
])
def test_api_routing_errors_use_the_view_envelope(tmp_path, method, path, status, error, detail):
    client = TestClient(create_app(Catalog(tmp_path)))
    response = client.request(method, path)
    assert response.status_code == status
    assert response.json() == dict(schema=API, error=error, detail=detail)
    assert response.headers['content-type'] == 'application/json'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    if status == 405:
        assert set(response.headers['allow'].split(', ')) == {'GET', 'HEAD'}
    assert client.get('/no-such-route').headers['content-type'].startswith('text/plain')


def draft_manifest(draft_id, state='open'):
    life = dict(state=state, untouched_sessions=2, last_touched_session='session-later')
    if state == 'promoted':
        life['promoted_by_session'] = 'session-promoted'
    return dict(schema='container-manifest/1', id=draft_id, kind='draft', owner_role='curator',
                inputs=dict(created_by_session='session-first'), pinned={}, budgets=dict(max_bytes=4096),
                lifecycle=life, provenance=dict(sessions=['session-first', 'session-later']),
                retention=dict(policy='stale after untouched sessions'))


def write_draft(root, bucket, manifest):
    path = root / bucket / manifest['id'] / 'manifest.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest))
    return path


def test_curator_draft_sources_page_by_manifest_snapshot(tmp_path):
    root = tmp_path / 'private-curator-state'
    sources = FrameSources(curator_drafts=(('drafts', root), ('other', tmp_path / 'absent')))
    client = TestClient(create_app(Catalog(tmp_path / 'evaluation'), frame_sources=sources))
    route = '/api/view/curator-sources/drafts'
    labels = client.get('/api/view/curator-sources/draft-sources?limit=1').json()
    assert labels == dict(schema='spectator-view/4', items=[dict(label='drafts')], total=2, next=1, limit=1)
    assert client.get('/api/view/curator-sources/draft-sources?after=1&limit=1').json()['items'] == [dict(label='other')]
    assert client.get(route, params=dict(source='unknown')).json()['error'] == 'unknown_source'

    removed = write_draft(root, 'drafts-archive', draft_manifest('a-abandoned', 'abandoned'))
    promoted = write_draft(root, 'drafts-archive', draft_manifest('z-promoted', 'promoted'))
    stale = write_draft(root, 'drafts', draft_manifest('z-stale', 'stale'))
    manifest = draft_manifest('a-open')
    manifest['inputs']['created_by_session'] = '/private/created'
    manifest['pinned']['withheld'] = '/private/pinned'
    manifest['provenance']['sessions'] = ['first', 'C:\\private\\session'] + ['later'] * LIST_LIMIT
    manifest['retention']['policy'] = 'read /private/policy'
    opened = write_draft(root, 'drafts', manifest)
    body = opened.with_name('notes.md')
    body.write_text('private draft body')
    params = dict(source='drafts', limit=2)
    response = client.get(route, params=params)
    first = response.json()
    assert first['schema'] == 'spectator-view/4' and first['source_status'] == 'available'
    assert first['total'] == 4 and first['next'] == 2 and first['limit'] == 2
    assert [(r['id'], r['bucket'], r['state']) for r in first['items']] == [('a-open', 'active', 'open'), ('z-stale', 'active', 'stale')]
    assert first['items'][0] == dict(id='a-open', bucket='active', state='open', untouched_sessions=2,
        created_by_session=None, last_touched_session='session-later', promoted_by_session=None, max_bytes=4096,
        retention_policy=None, sessions=dict(items=['first', None] + ['later'] * (LIST_LIMIT - 2), omitted=2, values_omitted=1))
    assert '/private' not in response.text and 'private draft body' not in response.text
    before = {path: path.read_bytes() for path in (opened, stale, removed, promoted)}
    entries = [(p.parent.parent.name, p.parent.name, hashlib.sha256(data).hexdigest(), len(data)) for p, data in before.items()]
    fingerprint = b''.join(json.dumps(row, separators=(',', ':')).encode() + b'\n' for row in sorted(entries))
    assert first['snapshot'] == dict(sha256=hashlib.sha256(fingerprint).hexdigest(), bytes=sum(map(len, before.values())))
    digest = first['snapshot']['sha256']
    for missing in (dict(after=2), dict(snapshot='invalid')):
        bad = client.get(route, params=dict(params, **missing))
        assert bad.status_code == 400 and bad.json()['error'] == 'bad_snapshot'
    body.write_text('different private draft body')
    second_params = dict(params, after=2, snapshot=digest)
    second = client.get(route, params=second_params).json()
    assert second['snapshot'] == first['snapshot'] and second['next'] is None
    assert [(r['id'], r['bucket'], r['state'], r['promoted_by_session']) for r in second['items']] == [
        ('a-abandoned', 'archived', 'abandoned', None), ('z-promoted', 'archived', 'promoted', 'session-promoted')]
    assert {path: path.read_bytes() for path in before} == before
    promoted.write_bytes(before[promoted] + b'\n')
    changed = client.get(route, params=second_params)
    assert changed.status_code == 409 and changed.json()['error'] == 'source_changed'


def test_curator_draft_source_reports_missing_empty_and_invalid_manifests(tmp_path):
    root = tmp_path / 'state'
    sources = FrameSources(curator_drafts=(('state', root),))
    client = TestClient(create_app(Catalog(tmp_path / 'evaluation'), frame_sources=sources))
    def read(status):
        value = client.get('/api/view/curator-sources/drafts?source=state').json()
        assert value['source_status'] == status and value['items'] == [] and value['total'] == 0
        assert (value['snapshot'] is None) == (status in ('missing', 'unreadable'))
        return value

    read('missing')
    root.mkdir()
    read('empty')
    (root / 'drafts' / 'unfinished').mkdir(parents=True)
    read('empty')
    write_draft(root, 'drafts', draft_manifest('valid'))
    path = write_draft(root, 'drafts', draft_manifest('broken'))
    for data in (b'{', b'', b'\xff'):
        path.write_bytes(data)
        read('malformed')
    manifest = draft_manifest('broken')
    for broken in (dict(manifest, schema='container-manifest/2'), dict(manifest, id='different'),
                   dict(manifest, owner_role='actor'), dict(manifest, kind=[]),
                   dict(manifest, lifecycle=dict(manifest['lifecycle'], state='abandoned')),
                   dict(manifest, lifecycle=dict(manifest['lifecycle'], untouched_sessions=True))):
        path.write_text(json.dumps(broken))
        read('unsupported')
    path.unlink()
    wrong_id = write_draft(root, 'drafts', draft_manifest('Invalid-ID'))
    read('unsupported')
    wrong_id.unlink()
    path.write_bytes(b'x' * (MAX_JSON_FILE_BYTES + 1))
    read('too_large')


def test_curator_drafts_refuse_symlinks_and_non_directories(tmp_path):
    root = tmp_path / 'state'
    outside = tmp_path / 'outside'
    manifest = write_draft(outside, 'drafts', draft_manifest('secret'))
    sources = FrameSources(curator_drafts=(('state', root),))
    client = TestClient(create_app(Catalog(tmp_path / 'evaluation'), frame_sources=sources))
    def unreadable():
        response = client.get('/api/view/curator-sources/drafts?source=state')
        value = response.json()
        assert value['source_status'] == 'unreadable' and value['snapshot'] is None and value['items'] == []
        assert 'secret' not in response.text

    root.touch()
    unreadable()
    root.unlink()
    root.symlink_to(outside, target_is_directory=True)
    unreadable()
    root.unlink()
    root.mkdir()
    bucket = root / 'drafts'
    bucket.symlink_to(outside / 'drafts', target_is_directory=True)
    unreadable()
    bucket.unlink()
    bucket.mkdir()
    draft = bucket / 'linked'
    draft.symlink_to(manifest.parent, target_is_directory=True)
    unreadable()
    draft.unlink()
    draft.mkdir()
    (draft / 'manifest.json').symlink_to(manifest)
    unreadable()


def test_gate_results_and_session_verdicts_project_bounded_draft_ids(tmp_path):
    result = dict(schema='curator-gate/2', operation='submission', operation_id='a' * 32, status='published',
                  base_version='v1', restored_from=None, version='v2', submission='submission', session='receipt',
                  from_drafts=[f'draft-{i}' for i in range(LIST_LIMIT + 1)], diagnostics=[])
    gate, receipt = tmp_path / 'gate.jsonl', tmp_path / 'close-out.json'
    gate.write_text(json.dumps(result) + '\n')
    manifest = dict(schema='container-manifest/1', kind='curator-session', id='receipt', owner_role='curator',
                    inputs={}, pinned={}, budgets={}, provenance={}, retention={}, lifecycle=dict(state='aborted',
                    ended_wall=1, stopped=None, returncode=None, survivors=None, errors=[], refused=[]))
    receipt.write_text(json.dumps(dict(manifest=manifest, verdicts=[result], drafts={}, published_after='v2')))
    sources = FrameSources(curator_results=(('journal', gate),), curator_sessions=(('receipt', receipt),))
    client = TestClient(create_app(Catalog(tmp_path / 'evaluation'), frame_sources=sources))
    for path in ('results?source=journal', 'session?source=receipt'):
        item = client.get('/api/view/curator-sources/' + path).json()['items'][0]
        assert item['from_drafts'] == result['from_drafts'][:LIST_LIMIT] and item['from_drafts_omitted'] == 1


def test_every_json_route_has_the_schema_and_stays_bounded(archive):
    client, catalog, _ = archive
    session = 'a' * 32
    for route in [*CROSS_ROUTES, *run_routes(session)]:
        response = client.get(route)
        assert response.status_code == 200, (route, response.text[:200])
        assert response.headers['content-type'] == 'application/json'
        assert response.json()['schema'] == API == 'spectator-view/4'
        assert len(response.content) < MAX_BYTES
    assert client.get(f'/api/view/run/base1/summary').json()['session'] == session  # the directory name works too
    assert client.get('/api/view/run/nope/summary').status_code == 404
    assert client.get('/api/view/run/nope/summary').json()['error'] == 'unknown_run'
    assert client.get('/api/view/nothing').status_code == 404


def test_runs_summarise_facts_outcome_and_versions(archive):
    client, _, _ = archive
    rows = {r['run']: r for r in client.get('/api/view/runs').json()['items']}
    assert set(rows) == {'base1', 'base2', 'aid1', 'aid2'}
    died, lost = rows['base1'], rows['aid2']
    assert died['outcome']['died'] is True and died['outcome']['censor_reason'] == 'died' and died['state'] == 'final'
    assert died['labels'] == dict(arm='base', start='S1', scenario='s', lineage=None, admission=None, world=None)
    assert died['versions'] == dict(core_version=CORE_VERSION, binding_id='fake', binding_version=3, state='final', created_wall=1.0)
    assert lost['outcome']['censor_reason'] == 'infrastructure' and lost['outcome']['lost'] is True
    assert rows['aid1']['outcome']['censor_reason'] == 'player_stop' or rows['aid1']['outcome']['censor_reason'] is None
    assert died['decisions'] == 13 and died['dollars'] == pytest.approx(0.14)


def test_limits_and_cursors_are_validated_and_paging_is_complete(archive):
    client, _, _ = archive
    steps = '/api/view/run/' + 'a' * 32 + '/steps'
    for bad in ('limit=501', 'limit=0', 'limit=x', 'after=-1', 'after=x'):
        response = client.get(f'{steps}?{bad}')
        assert response.status_code == 400 and response.json()['error'].startswith('bad_'), bad
    assert client.get(f'{steps}?limit=500').status_code == 200
    seen, after = [], 0
    while True:
        page = client.get(f'{steps}?limit=5&after={after}').json()
        assert page['limit'] == 5 and len(page['items']) <= 5
        seen += [item['seq'] for item in page['items']]
        if page['next'] is None:
            break
        after = page['next']
    assert seen == list(range(1, 15))
    first = client.get(steps).json()['items'][2]
    assert (first['seq'], first['decision'], first['mode'], first['game_time'], first['keys']) == (3, 2, 'in_play', 3600, ['key:j'])
    assert set(first) == {'seq', 'decision', 'wall', 'kind', 'mode', 'game_time', 'source_id', 'frame_changed', 'dollars', 'keys'}
    runs = client.get('/api/view/runs?limit=3').json()
    assert len(runs['items']) == 3 and runs['next'] == 3 and runs['total'] == 4
    assert client.get('/api/view/runs?limit=3&after=3').json()['next'] is None
    calls = '/api/view/run/' + 'a' * 32 + '/calls'
    page = client.get(f'{calls}?limit=4').json()
    assert len(page['items']) == 4 and page['next'] == page['items'][-1]['id']
    only = client.get(f'{calls}?tool=computer_observe').json()['items']
    assert only and all(c['tool'] == 'computer_observe' for c in only) and client.get(f'{calls}?status=bad').status_code == 400
    produced = [c for c in client.get(f'{calls}?limit=500').json()['items'] if c['step']]
    assert produced and produced[0]['step']['source_id']  # a call that created an operation carries its step and frame
    requests = client.get('/api/view/run/' + 'a' * 32 + '/requests?limit=3').json()
    assert len(requests['items']) == 3 and requests['next'] and requests['items'][0]['manifest'] == 'absent'
    assert 'markers' in requests


def test_frames_are_served_only_after_their_digest_matches(archive):
    client, _, runs = archive
    session = 'a' * 32
    item = next(i for i in client.get(f'/api/view/run/{session}/steps').json()['items'] if i['source_id'])
    route = f'/api/view/run/{session}/frame/{item["source_id"]}'
    response = client.get(route)
    assert response.status_code == 200 and response.headers['content-type'] == 'image/png'
    assert response.content == (runs / 'base1' / 'sources' / f'{item["source_id"]}.png').read_bytes()
    assert client.get(f'/api/view/run/{session}/frame/{session}-9999').status_code == 404
    assert client.get(f'/api/view/run/{session}/frame/..%2Fmanifest').status_code in (400, 404)
    (runs / 'base1' / 'sources' / f'{item["source_id"]}.png').write_bytes(b'tampered')
    refused = client.get(route)
    assert refused.status_code == 409 and refused.json()['error'] == 'frame_digest_mismatch'


def snapshot(directory: Path) -> dict[str, tuple[int, bytes | None]]:
    """Every path under a directory with its modification time and bytes (None for a directory).

    A WAL-mode reader maps the `-shm` wal-index even with `mode=ro`, which can move its mtime; it is a transient
    lock/index file that holds no run data, so only its presence is compared."""
    return {str(p.relative_to(directory)): (None, None) if p.name.endswith('-shm') else
            (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
            for p in sorted(directory.rglob('*'))}


def test_evaluation_and_the_viewer_leave_the_run_directories_untouched(archive, tmp_path):
    client, _, runs = archive
    session = 'a' * 32
    before = snapshot(runs)
    names = {Path(name).name for name in before}
    assert {'session.sqlite3', 'host.jsonl', 'manifest.json'} <= names
    assert any(name.startswith('base1/sources/') and name.endswith('.png') for name in before)
    evaluate(runs / 'base1', FakeBinding(), tmp_path / 'fresh', created_wall=2.0)
    assert snapshot(runs) == before
    evaluate(runs / 'base1', FakeBinding(), tmp_path / 'live', state='live', created_wall=2.0)
    LiveEvaluator(runs / 'base1', tmp_path / 'live', FakeBinding()).step()
    assert snapshot(runs) == before
    item = next(i for i in client.get(f'/api/view/run/{session}/steps').json()['items'] if i['source_id'])
    for route in (f'/api/view/run/{session}/summary', f'/api/view/run/{session}/frame/{item["source_id"]}',
                  f'/api/view/run/{session}/context/request-1', f'/api/view/run/{session}/requests',
                  f'/api/view/run/{session}/steps', '/api/view/runs'):
        assert client.get(route).status_code == 200, route
    assert snapshot(runs) == before


@pytest.mark.parametrize('method', ['post', 'put', 'delete', 'patch'])
def test_no_route_accepts_a_write_method(archive, method):
    client, _, _ = archive
    for route in [*CROSS_ROUTES[:3], *run_routes('a' * 32), f'/api/view/run/{"a" * 32}/frame/x',
            f'/api/view/run/{"a" * 32}/context/request-1']:
        route = route.split('?')[0]
        assert getattr(client, method)(route).status_code == 405, route


def test_summary_carries_game_state_findings_ladder_metrics_and_validation(archive):
    client, _, _ = archive
    summary = client.get('/api/view/run/' + 'a' * 32 + '/summary').json()
    assert summary['live'] is False and summary['pause'] is None and summary['evaluator'] is None
    assert summary['facts']['labels']['arm'] == 'base' and summary['outcome']['hours'] == pytest.approx(2540 / 3600)
    state = summary['game_state']
    assert state['provenance'] == 'read' and state['mode'] == 'dead' and state['source_id'] and state['readings']['mode']['value'] == 'dead'
    assert state['readings']['mode']['validation'] == dict(accuracy=0.94, n=219, floor=0.97, **{'pass': False})
    assert state['readings']['clock']['validation']['pass'] is True and state['readings']['ate']['validation'] is None
    kinds = {f['kind'] for f in summary['findings']}
    assert {'long_activity', 'death', 'stall'} <= kinds | {'long_activity', 'death', 'stall'} and 'death' in kinds
    assert 'context_eviction' not in kinds and isinstance(summary['routine_findings']['context_eviction'], int)
    assert summary['started_wall'] == min(s['wall'] for s in client.get('/api/view/run/' + 'a' * 32 + '/steps?after=0').json()['items'])
    assert summary['ladder']['highest'] == 'ate' and [r['id'] for r in summary['ladder']['rungs']] == ['play', 'armed', 'ate']
    metric = next(m for m in summary['metrics'] if m['name'] == 'survival.game_hours')
    assert metric['source'] == 'derived' and metric['count'] == 12 and 'denominator' in metric and 'missing' in metric
    assert next(m for m in summary['metrics'] if m['name'] == 'host.dollars_per_decision')['source'] == 'recorded'
    assert next(m for m in summary['metrics'] if m['name'] == 'mode.out_of_play_share')['source'] == 'read'
    # `validated` follows the readers a metric depends on: mode fails its floor, clock passes, death has no entry.
    flags = {m['name']: m['validated'] for m in summary['metrics']}
    assert flags['mode.out_of_play_share'] is False and flags['survival.game_hours'] is False
    assert flags['host.dollars_per_decision'] is None and flags['pace.long_activities'] is True
    coverage = {c['reader']: c for c in summary['reader_coverage']}
    assert coverage['mode']['validation']['pass'] is False and coverage['clock']['validation']['pass'] is True
    assert coverage['ate']['validation'] is None and coverage['mode']['denominator'] == 14


def test_summary_projects_only_the_selected_current_custodian_receipt(archive):
    client, _, runs = archive
    session = 'b' * 32
    path = runs / 'base2' / 'receipt.json'
    manifest_path = path.with_name('manifest.json')
    manifest = json.loads(manifest_path.read_text())
    accounting = dict(reported_usd='0.102442', spent_usd='0.102442', unpriced_requests=0, unpriced_recall_requests=0)
    expected = dict(outcome='player_task_complete_unassessed', normal_native_exit_zero=False,
        native_absence_verified=True, deciding_hosts_quiescent=None, input_authority_revoked=True, accounting=accounting)
    receipt = dict(expected, schema=RECEIPT_SCHEMA, session=session, source_commit=manifest['source_commit'],
        deciding_hosts_quiescent=1, cleanup=dict(pid=123), reason='private fixture',
        accounting=dict(accounting, spend_complete=True, spend_limit_usd='4.50'))
    route = f'/api/view/run/{session}/summary'
    baseline = client.get(route).json()
    assert baseline['custodian_receipt'] is None
    path.write_text(json.dumps(receipt))
    assert client.get(route).json() == dict(baseline, custodian_receipt=expected)
    assert client.get('/api/view/run/aid1/summary').json()['custodian_receipt'] is None

    for invalid in ('{', '[]', *(json.dumps(dict(receipt, **change)) for change in (
            dict(schema='campaign-receipt/4'), dict(session='c' * 32), dict(source_commit='different')))):
        path.write_text(invalid)
        assert client.get(route).json() == baseline
    path.write_text(json.dumps(dict(receipt, outcome='private fixture')))
    assert client.get(route).json() == dict(baseline, custodian_receipt=dict(expected, outcome=None))
    for change in (dict(schema=MANIFEST_SCHEMA + '-invalid'), dict(session='c' * 32), dict(source_commit='different')):
        manifest_path.write_text(json.dumps(dict(manifest, **change)))
        assert client.get(route).json() == baseline


def test_summary_reports_complete_provider_cost_and_unpriced_attempts(archive):
    client, _, runs = archive
    path = runs / 'base2' / 'receipt.json'
    manifest = json.loads(path.with_name('manifest.json').read_text())
    receipt = dict(schema=RECEIPT_SCHEMA, session=manifest['session'], source_commit=manifest['source_commit'],
        outcome='incomplete')
    route = f"/api/view/run/{manifest['session']}/summary"
    zero = dict(reported_usd='0', spent_usd='0', unpriced_requests=0, unpriced_recall_requests=0)
    unpriced = dict(reported_usd='1.64493095', spent_usd='1.64493095', unpriced_requests=1, unpriced_recall_requests=1)
    for values in (zero, unpriced):
        path.write_text(json.dumps(dict(receipt, accounting=dict(values, spend_complete=True))))
        payload = client.get(route).json()['custodian_receipt']
        assert payload['outcome'] == 'incomplete'
        assert payload['accounting'] == values

    for invalid in (None, [], dict(zero, spend_complete=False), dict(zero, spend_complete=1),
                    *(dict(zero, spend_complete=True, **change) for change in (
                        dict(reported_usd='1e-7'), dict(spent_usd=0), dict(reported_usd='-1'),
                        dict(spent_usd='0.01'), dict(reported_usd='1'),
                        dict(unpriced_requests=True), dict(unpriced_recall_requests=-1)))):
        path.write_text(json.dumps(dict(receipt, accounting=invalid)))
        payload = client.get(route).json()['custodian_receipt']
        assert payload['outcome'] == 'incomplete' and payload['accounting'] is None


def test_tools_aggregate_calls_and_transitions(archive):
    client, _, _ = archive
    value = client.get('/api/view/run/' + 'a' * 32 + '/tools').json()
    by_tool = {t['tool']: t for t in value['tools']}
    assert by_tool['computer_input']['calls'] == 13 and by_tool['computer_observe']['calls'] == 1
    assert set(by_tool['computer_input']) == {'tool', 'calls', 'refused', 'errors', 'result_bytes', 'p50_ms', 'p95_ms'}
    assert ['computer_input', 'computer_input', 12] in value['transitions'] and ['computer_observe', 'computer_input', 1] in value['transitions']


def test_context_route_is_exact_with_a_manifest_and_reconstructed_without(tmp_path):
    runs = tmp_path / 'runs'
    run = Run(runs / 'm')
    a = run.actor()
    run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
    run.host[a].append(run.event(a, 'request-start', iso(BASE + 31), request_id='request-2', logical_request_id='request-2'))
    run.host[a].append(run.event(a, 'context-manifest', iso(BASE + 31), request_id='request-2', base_request_id=None,
        reused_prefix_parts=0, part_count=1, parts=[dict(index=0, role='system', kind='text', bytes=5, sha256='b' * 64)]))
    run.host[a].append(run.event(a, 'response-complete', iso(BASE + 32), request_id='request-2', stop_reason='stop',
        usage_available=True, usage=Run.usage()))
    run.finish()
    evaluate(runs / 'm', FakeBinding(), tmp_path / 'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path / 'root', (runs,), data_dir=data_directory(tmp_path))))
    exact = client.get(f'/api/view/run/{SESSION}/context/request-2').json()
    assert exact['exact'] is True and exact['parts'][0]['sha256'] == 'b' * 64 and exact['bytes_by_kind'] == dict(text=5)
    rows = {r['request_id']: r for r in client.get(f'/api/view/run/{SESSION}/requests').json()['items']}
    assert rows['request-2']['manifest'] == 'exact' and rows['request-1']['manifest'] == 'absent'
    built = client.get(f'/api/view/run/{SESSION}/context/request-1').json()
    assert built['exact'] is False and [p['kind'] for p in built['parts']] == ['text', 'text']
    assert client.get(f'/api/view/run/{SESSION}/context/request-99').status_code == 404


def test_archived_memory_and_handoffs(tmp_path, legacy_player_archive):
    runs = tmp_path / 'runs'
    memory_scenario(runs / 'mem')
    evaluate(runs / 'mem', FakeBinding(), tmp_path / 'root', created_wall=1.0)
    data = data_directory(tmp_path)
    client = TestClient(create_app(Catalog(tmp_path / 'root', (runs,), data_dir=data)))
    records = client.get(f'/api/view/archive/run/{SESSION}/memory').json()
    assert records['available'] is True and [r['kind'] for r in records['records']] == ['work', 'decision', 'claim']
    first, second, third = records['records']
    assert first['carried_by'] and not third['carried_by'] and second['text'] == 'note' and second['chain'] == []
    assert {r['tool'] for r in first['reads']} >= {'player_memory_read', 'player_memory_query'}
    handoffs = client.get(f'/api/view/run/{SESSION}/handoffs').json()['handoffs']
    assert len(handoffs) == 1 and handoffs[0]['decisions_to_resume'] == 2 and handoffs[0]['carry_text'] == 'carry'
    assert handoffs[0]['carried_agenda'] is None
    (runs / 'mem' / 'actors' / '002' / 'agenda.json').write_text(json.dumps(agenda_document('Successor agenda', 2)))
    agenda = client.get(f'/api/view/run/{SESSION}/handoffs').json()['handoffs'][0]['carried_agenda']
    assert (agenda['cut_count'], agenda['active_count'], agenda['threads'][0]['title']) == (2, 1, 'Successor agenda')
    assert handoffs[0]['carried_ids'] == [first['id']] and handoffs[0]['carry_ratio'] == pytest.approx(0.25)
    # a human label that names a carried record is the identity check
    (data / 'labels.jsonl').write_text(json.dumps(dict(id='l', session=SESSION, seq_start=0, seq_end=0, target=first['id'],
        code='identity_or_world_error', verdict='confirm', note='wrong world', author='o', date='d', taxonomy_version=1)) + '\n')
    checked = client.get(f'/api/view/run/{SESSION}/handoffs').json()['handoffs'][0]['identity_check']
    assert checked['checked'] is True and checked['errors'][0]['note'] == 'wrong world'
    assert client.get(f'/api/view/archive/run/{SESSION}/memory').json()['records'][0]['labels'][0]['id'] == 'l'


def test_improve_compare_and_explore_over_the_archive(archive):
    client, _, _ = archive
    changes = {c['id']: c for c in client.get('/api/view/improve/changes').json()['changes']}
    aid = changes['aid']
    assert aid['verdict'] == 'untested' and aid['target']['arm']['n'] == 1 and aid['target']['baseline']['n'] == 2
    assert aid['target']['excluded'] == ['aid2']  # the lost run is excluded
    assert aid['uptake']['n'] == 1 and aid['guard_values'][0]['metric']['name'] == 'survival.game_hours'
    assert aid['computed_verdict'] in ('untested', 'no_effect_detected', 'moved', 'wrong_way')
    assert changes['unused']['computed_verdict'] == 'untested' and changes['unused']['uptake'] is None
    failures = client.get('/api/view/improve/failures').json()
    modes = {m['code']: m for m in failures['failures']}
    assert failures['failures'][0]['code'] == 'death' and modes['death']['occurrences'] == 1
    assert modes['stall']['occurrences'] == 0 and modes['stall']['items'] == [] and modes['death']['items'][0]['source'] == 'reader'
    assert modes['identity_or_world_error']['occurrences'] == 1 and modes['identity_or_world_error']['sources'] == ['human']
    compare = client.get('/api/view/compare?group=arm&horizon=0.05').json()
    assert set(compare['groups']) == {'aid', 'base'} and [e['run'] for e in compare['excluded']] == ['aid2']
    base = compare['groups']['base']
    assert base['n'] == 2 and base['deaths'] == 1 and base['censored'] == 1 and base['curve']['survival'][0] == 1.0
    assert base['median'] == 'not_reached' or isinstance(base['median'], float)
    assert base['rmst']['horizon'] == 0.05 and base['versions']['binding_versions'] == ['3']
    beyond = client.get('/api/view/compare?group=start&horizon=99').json()
    assert beyond['groups']['S1']['rmst']['reason'] == 'horizon_beyond_observed_range'
    assert client.get('/api/view/compare?group=nope').status_code == 400
    assert client.get('/api/view/compare?runs=zzz').status_code == 404
    explore = client.get('/api/view/explore?outcome=died').json()
    assert [r['run'] for r in explore['cohort']] == ['base1'] and explore['stats']['bootstrap'] is None
    assert explore['stats']['bootstrap_note'] == 'needs n >= 5'
    steps = explore['before_death'][0]['decisions']
    assert len(steps) == 13 and steps[-1]['mode'] == 'dead' and steps[-1]['threat'] is None or steps[-1]['mode'] == 'dead'
    everyone = client.get('/api/view/explore?metric=survival.game_hours').json()
    assert everyone['stats']['n'] == 4 and everyone['stats']['median'] is not None


def test_bootstrap_interval_for_a_median_needs_five_values(tmp_path):
    runs = tmp_path / 'runs'
    for index in range(6):
        ended_run(runs / f'r{index}', session=f'{index + 1:032x}')
        evaluate(runs / f'r{index}', FakeBinding(), tmp_path / 'root', created_wall=1.0, labels=dict(arm='x', start='S1'))
    client = TestClient(create_app(Catalog(tmp_path / 'root', (runs,), data_dir=data_directory(tmp_path))))
    stats = client.get('/api/view/explore?metric=survival.game_hours').json()['stats']
    assert stats['n'] == 6 and stats['bootstrap']['low'] <= stats['median'] <= stats['bootstrap']['high']


# ---------------------------------------------------------------------------------------------
# Pause conditions and the live evaluator.

def pause_run(directory: Path, kind: str) -> Path:
    run = Run(directory)
    a = run.actor()
    # Synthetic requests are seconds apart, so any real limit is crossed by the one-hour projection; only the
    # spend case declares a small one.
    ceiling = dict(spend_limit_usd='0.5' if kind == 'spend' else '1000')
    cost = Run.usage(total=0.3) if kind == 'spend' else None
    run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1), usage=cost)
    run.step(a, 'input', [key('j')], F('in_play', 3660, fill=2), usage=cost)
    if kind == 'custody':
        run.step(a, 'input', [key('j')], F('in_play', 3720, fill=3), status='unknown', receipt='unknown')
    if kind == 'loop':
        for index in range(31):
            run.step(a, 'input', [key('ESC')], F('menu', fill=index))
    if kind == 'dead':
        run.step(a, 'input', [key('j')], F('dead', 3700, death=True, fill=4))
        run.step(a, 'input', [key('j')], F('dead', 3700, death=True, fill=5))
    if kind == 'spend':
        run.step(a, 'input', [key('j')], F('in_play', 3720, fill=3), usage=cost)
    run.finish(**ceiling)
    return directory


def live_client(tmp_path: Path, kind: str, now_offset: float | None = 5):
    directory = pause_run(tmp_path / 'live', kind)
    evaluate(directory, FakeBinding(), tmp_path / 'root', state='live', created_wall=1.0)
    last = Run.wall  # noqa: F841 (the clock below is relative to the last operation)
    from harness.evaluation.core.records import read_steps
    path = next((tmp_path / 'root').glob('*/*.sqlite3'))
    connection = open_readonly(path)
    last_wall = max(s.wall for s in read_steps(connection))
    connection.close()
    evaluator = LiveEvaluator(directory, tmp_path / 'root', FakeBinding())
    catalog = Catalog(tmp_path / 'root', (), directory, data_dir=data_directory(tmp_path))
    client = TestClient(create_app(catalog, evaluator, now=lambda: last_wall + (now_offset or 0)))
    return client, evaluator


def conditions_of(client: TestClient) -> tuple[dict, dict]:
    summary = client.get(f'/api/view/run/{SESSION}/summary').json()
    return summary['pause'], {c['id']: c for c in summary['pause']['conditions']}


def test_pause_conditions_are_clear_for_a_healthy_live_run(tmp_path):
    client, _ = live_client(tmp_path, 'clear')
    pause, by_id = conditions_of(client)
    assert pause['answer'] == 'no' and pause['met'] == []
    assert list(by_id) == ['feed_alive', 'custody_healthy', 'not_looping', 'spend_inside_allowance', 'not_dead_and_spending']
    assert by_id['feed_alive']['value'] == 5.0 and by_id['spend_inside_allowance']['value']['ceiling'] == 1000.0
    assert all({'value', 'threshold', 'met', 'dollars_per_minute'} <= set(c) for c in by_id.values()) and pause['dollars_per_minute'] > 0
    assert client.get(f'/api/view/run/{SESSION}/summary').json()['evaluator']['running'] is False


@pytest.mark.parametrize('kind, offset, condition', [
    ('clear', 301, 'feed_alive'), ('custody', 5, 'custody_healthy'), ('loop', 5, 'not_looping'),
    ('spend', 5, 'spend_inside_allowance'), ('dead', 5, 'not_dead_and_spending')])
def test_each_pause_condition_is_met_when_its_rule_holds(tmp_path, kind, offset, condition):
    client, _ = live_client(tmp_path, kind, offset)
    pause, by_id = conditions_of(client)
    assert by_id[condition]['met'] is True and pause['answer'] == 'yes' and condition_names(pause) == [by_id[condition]['name']]
    for other, row in by_id.items():
        if other != condition:
            assert row['met'] is False, other


def condition_names(pause: dict) -> list[str]:
    return pause['met']


def test_pause_helpers_cover_edges():
    assert dollars_per_minute([]) == 0.0 and dollars_per_minute([(0.0, 0.6)]) == pytest.approx(0.6)
    assert dollars_per_minute([(0.0, 0.1), (100.0, 0.1), (1000.0, 0.4)]) == pytest.approx(0.4 / 60 * 60 / 1.0)
    assert looping_streak([(1, 'in_play', 10), (2, 'menu', None), (3, 'unknown', None), (4, 'menu', None)]) == (2, False)
    assert looping_streak([(1, 'in_play', 10), (2, 'in_play', 20)]) == (0, True)
    assert looping_streak([(1, 'menu', None), (2, 'prompt', 5)])[1] is True  # game time advanced during the streak


def test_only_the_viewers_own_run_is_listed_live(tmp_path):
    """#435: a live store an earlier run left unfinalized must not be listed live, or the page follows it."""
    runs = tmp_path / 'runs'
    earlier = ended_run(runs / 'earlier', session='b' * 32)
    evaluate(earlier, FakeBinding(), tmp_path / 'root', state='live', created_wall=1.0)
    current = pause_run(runs / 'current', 'healthy')
    evaluate(current, FakeBinding(), tmp_path / 'root', state='live', created_wall=2.0)
    catalog = Catalog(tmp_path / 'root', (runs,), current, data_dir=data_directory(tmp_path))
    client = TestClient(create_app(catalog, LiveEvaluator(current, tmp_path / 'root', FakeBinding())))
    states = {r['session']: r['state'] for r in client.get('/api/view/runs').json()['items']}
    assert states == {'b' * 32: 'unfinished', SESSION: 'live'}
    explored = {r['session']: r['state'] for r in client.get('/api/view/explore').json()['cohort']}
    assert explored == states
    # A viewer with no live run lists every unfinalized store as unfinished.
    idle = TestClient(create_app(Catalog(tmp_path / 'root', (runs,), data_dir=data_directory(tmp_path))))
    assert {r['state'] for r in idle.get('/api/view/runs').json()['items']} == {'unfinished'}


def test_the_live_evaluator_extends_a_live_store_incrementally_and_never_touches_a_final_one(tmp_path):
    run_dir = tmp_path / 'run'
    run, a, sequence = growing_run(run_dir)
    for item in sequence[:4]:
        run.step(a, *item)
    run.finish(close=False)
    evaluator = LiveEvaluator(run_dir, tmp_path / 'root', FakeBinding())
    evaluator.tick()
    path = evaluator.record()
    assert evaluator.status['error'] is None and evaluator.status['passes'] == 1 and evaluator.status['last_seq'] == 4
    connection = open_readonly(path)
    assert read_metadata(connection)['state'] == 'live' and read_metadata(connection)['inputs'] == {}
    connection.close()
    for item in sequence[4:]:
        run.step(a, *item)
    run.finish(close=False)
    evaluator.tick()
    assert evaluator.status['last_seq'] == 7 and evaluator.status['passes'] == 2
    live = TestClient(create_app(Catalog(tmp_path / 'root', (), run_dir, data_dir=data_directory(tmp_path)), evaluator))
    steps = live.get(f'/api/view/run/{SESSION}/steps?limit=500').json()['items']
    assert [s['seq'] for s in steps] == list(range(1, 8))
    summary = live.get(f'/api/view/run/{SESSION}/summary').json()
    assert summary['live'] is True and summary['evaluator']['passes'] == 2 and summary['pause']['answer'] in ('yes', 'no')
    # The finished record is the same as one full pass over the grown run.
    full = evaluate(run_dir, FakeBinding(), tmp_path / 'full', created_wall=1.0)
    other = open_readonly(full)
    assert read_metadata(other)['last_seq'] == 7
    other.close()
    # A final store replaces the live one and is then left alone: the live loop stops, the summary says so.
    final = evaluate(run_dir, FakeBinding(), tmp_path / 'root', created_wall=1.0)
    assert final == path
    before = path.read_bytes()
    evaluator.tick()
    evaluator.tick()
    assert evaluator.status['finished'] is True and path.read_bytes() == before
    summary = live.get(f'/api/view/run/{SESSION}/summary').json()
    assert summary['state'] == 'final' and summary['live'] is False and summary['evaluator']['finished'] is True
    connection = open_readonly(path)
    assert read_metadata(connection)['state'] == 'final'
    connection.close()
    run.store.close()


def test_the_live_loop_never_overwrites_a_final_store_an_operator_wrote(tmp_path):
    run_dir = pause_run(tmp_path / 'run', 'clear')
    root = tmp_path / 'root'
    evaluator = LiveEvaluator(run_dir, root, FakeBinding(), interval=0.01)
    evaluator.tick()
    path = evaluator.record()
    final = evaluate(run_dir, FakeBinding(), root, created_wall=1.0)  # evaluate-run while the viewer's loop is running
    assert final == path
    before = path.read_bytes()
    evaluator.start()
    time.sleep(0.2)
    evaluator.stop()
    assert path.read_bytes() == before and evaluator.status['finished'] is True and evaluator.status['error'] is None
    connection = open_readonly(path)
    meta = read_metadata(connection)
    connection.close()
    assert meta['state'] == 'final' and meta['inputs']


def test_a_failed_pass_is_reported_and_retried(tmp_path):
    evaluator = LiveEvaluator(tmp_path / 'missing', tmp_path / 'root', FakeBinding())
    evaluator.tick()
    assert evaluator.status['error'] and evaluator.status['passes'] == 0
    run_dir = pause_run(tmp_path / 'later', 'clear')
    evaluator.run_dir = run_dir
    evaluator.tick()
    assert evaluator.status['error'] is None and evaluator.status['passes'] == 1


def info_for(run_dir: Path):
    from harness.viewer.catalog import RunInfo
    return RunInfo(SESSION, 'run', run_dir / 'record.sqlite3', run_dir, {}, {}, {}, 0, 0.0)


def test_tool_latency_percentiles_are_the_evaluators_nearest_rank():
    import sqlite3
    from harness.viewer import views
    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE tool_calls (actor TEXT, tool TEXT, status TEXT, latency_ms REAL, result_bytes INTEGER, wall REAL)')
    connection.executemany('INSERT INTO tool_calls VALUES (?,?,?,?,?,?)',
        [('a', 'computer_input', 'ok', latency, 1, index) for index, latency in enumerate((400, 100, 300, 200))])
    row = views.tools(connection)['tools'][0]
    assert (row['p50_ms'], row['p95_ms']) == (200, 400)  # nearest rank, not the 250 a median would give
    assert not hasattr(views, 'percentile')


def test_the_viewer_reads_only_manifests_of_a_supported_version(tmp_path):
    from harness.viewer import views
    from harness.viewer.catalog import ViewError
    (tmp_path / 'runs').mkdir()
    current, unversioned, future, replaced = (tmp_path / 'runs' / name for name in ('current', 'unversioned', 'future', 'replaced'))
    # The immediately prior manifest is refused for a session the closed archive does not list.
    for directory, manifest in ((current, dict(schema='campaign-run/14', session='1' * 32, context={})), (unversioned, dict(session='2' * 32)),
            (future, dict(schema='campaign-run/15', session='3' * 32, context={})), (replaced, dict(schema='campaign-run/13', session='4' * 32, context={}))):
        directory.mkdir()
        (directory / 'manifest.json').write_text(json.dumps(manifest))
    catalog = Catalog(tmp_path / 'root', (tmp_path / 'runs',), data_dir=data_directory(tmp_path))
    assert catalog.run_dir_for('1' * 32, {}) == current
    assert all(catalog.run_dir_for(digit * 32, {}) is None for digit in '234')
    store = tmp_path / 'player-memory.sqlite3'
    (unversioned / 'manifest.json').write_text(json.dumps(dict(session='2' * 32, player_store=str(store))))
    with pytest.raises(ViewError, match='bad_manifest') as error:
        views.memory_store(catalog, info_for(unversioned))
    assert error.value.status == 500 and 'unsupported manifest version' in error.value.detail
    assert views.memory_store(catalog, info_for(current)) is None  # a supported manifest naming no store


def test_the_live_session_comes_from_a_supported_manifest(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    (run_dir / 'manifest.json').write_text(json.dumps(dict(session=SESSION)))
    evaluator = LiveEvaluator(run_dir, tmp_path / 'root', FakeBinding())
    assert evaluator.session() is None
    (run_dir / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/14', session=SESSION, context={})))
    assert evaluator.session() == SESSION


def test_the_labels_file_is_bounded_and_a_bad_line_names_its_position(tmp_path):
    from harness.viewer.catalog import ViewError
    directory = data_directory(tmp_path)
    catalog = Catalog(tmp_path / 'root', (), data_dir=directory)
    assert [label['id'] for label in catalog.labels()] == ['l1']
    (directory / 'labels.jsonl').write_text('{"id": "l1"}\n\n{"id": "l2", "id": "l3"}\n')
    with pytest.raises(ViewError) as error:
        catalog.labels()
    assert error.value.code == 'bad_data_file' and 'labels.jsonl' in error.value.detail and ':3' in error.value.detail
    assert 'duplicate key' in error.value.detail
    (directory / 'labels.jsonl').write_text(' ' * (16 * 1024 * 1024 + 1))
    with pytest.raises(ViewError) as error:
        catalog.labels()
    assert error.value.code == 'bad_data_file' and 'larger than' in error.value.detail


#: Sessions the closed archive index lists with each sealed manifest version.
ARCHIVED_SESSIONS = {'campaign-run/12': '49964eb42a7d4dabaef0c5ff6230a9be', 'campaign-run/10': 'd16ea238c2794897a7839549df297a69'}


@pytest.mark.parametrize('schema', [MANIFEST_SCHEMA, 'campaign-run/12', 'campaign-run/10'])
def test_current_journal_hints_are_read_only_public_reports(tmp_path, schema):
    from harness.player.journal import Journal
    directory = tmp_path/'runs'/'current'
    session = ARCHIVED_SESSIONS.get(schema, SESSION)
    run = Run(directory, session=session)
    actor = run.actor()
    operation = run.step(actor, 'input', [key('j')], F('in_play', 3600))
    source_id = f'{session}-1'
    start = next(e for e in run.host[actor] if e['type'] == 'tool-start')
    start['arguments'].update(intent='Move carefully', cites=['fact-visible'])
    run.host[actor].append(run.event(actor, 'player-finish', request_id='request-1', disposition='task_complete', report='I believe I am done', intent='Finish', cites=['fact-visible'], source_ids=[source_id]))
    store = tmp_path/'journal.sqlite3'
    args = dict(intent='Report an uncertain observation',text='The visible passage may be blocked',cites=['fact-visible'])
    with Journal(store) as journal:
        journal.record_call('hint-call',actor,'player_hint',args)
        hint = journal.hint('hint-call',actor,args['text'],[],args['intent'],args['cites'])
    run.call(actor,'player_hint',args,hint)
    run.finish(memory=store, labels=dict(world='farm') if schema != 'campaign-run/10' else {})
    sealed = {k: v for k, v in run.manifest.items() if k != 'context'}
    (directory/'manifest.json').write_text(json.dumps(run.manifest if schema == MANIFEST_SCHEMA else dict(sealed, schema=schema)))
    before = store.read_bytes()
    evaluate(directory,FakeBinding(),tmp_path/'root',created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path/'root',(tmp_path/'runs',),data_dir=data_directory(tmp_path))))
    value = client.get(f'/api/view/archive/run/{session}/memory').json()
    assert value['store_schema']=='player-journal/1' and value['records']==[]
    assert value['hints']==[hint] and value['provenance']=='player_public_report'
    reader = client.get(f'/api/view/run/{session}/knowledge', params=dict(actor=actor,request='request-1')).json()
    assert reader['journal_available'] is True and reader['hints'][0]['cites']==['fact-visible']
    call = next(c for c in reader['calls'] if c['tool']=='computer_input')
    assert call['intent']=='Move carefully' and call['cites']==['fact-visible']
    assert call['operation_id']==operation and call['operation']['status']=='completed'
    assert call['operation']['receipts'][0]['disposition']=='delivered'
    assert call['anchors']==[dict(run='current',source_id=source_id,available=True,reason=None)]
    assert reader['finishes'][0]['report']=='I believe I am done' and reader['finishes'][0]['disposition']=='task_complete'
    summary = client.get(f'/api/view/run/{session}/summary').json()
    assert reader['outcome'] == summary['outcome']
    assert summary['labels']['world'] == ('farm' if schema != 'campaign-run/10' else None)
    assert reader['finishes'][0]['anchors'][0]['available'] is True
    assert store.read_bytes()==before
    store.unlink()
    missing = client.get(f'/api/view/archive/run/{session}/memory').json()
    assert missing['available'] is False and missing['store_schema']=='player-journal/1'
    assert client.get(f'/api/view/run/{session}/knowledge',params=dict(actor=actor)).json()['journal_available'] is False


def test_recorded_knowledge_projection_keeps_selection_delivery_and_public_calls_separate(tmp_path):
    directory = tmp_path/'runs'/'recorded'
    run = Run(directory)
    actor = run.actor()
    run.request(actor)
    run.host[actor].append(run.event(actor, 'request-start', request_id='recall-1'))
    recall = run.event(actor, 'knowledge-recall', status='selected', request_id='recall-1', article_ids=['article-a'], fact_ids=['fact-a'], reply_text='private-reasoning')
    recall['kind'] = 'briefing'
    run.host[actor].append(recall)
    delivery = run.event(actor, 'knowledge-delivery', outcome='delivered', recall_request_id='recall-1', receiving_player_request_id='request-1', version='v18', article_ids=['article-a'], fact_ids=['fact-a'])
    delivery['kind'] = 'briefing'
    run.host[actor].append(delivery)
    run.call(actor, 'player_knowledge_read', dict(intent='inspect', cites=['fact-a'], id_or_title='passage-state', secret='credential'),
             dict(schema='player-knowledge/4', resolution='state_key', resolved_from=None, records=[dict(id='fact-a', text='A fact')]))
    run.call(actor, 'player_knowledge_read', dict(intent='Look for missing entry', cites=[], id_or_title='missing-entry'), dict(records=[]))
    run.call(actor, 'player_knowledge_query', dict(intent='search facts', cites=[], query='fact'),
             dict(schema='player-knowledge/4', version='v18', grants_authority=False, identity='fact', resolution='query',
                  resolved_from=None, hits=[dict(id='fact-a', kind='fact', subject=None, statement_kind='state', state_key='passage-state',
                  scope=dict(game='cdda', world=None), snippet='A fact', cited_by_articles=['article-a'], via='fuzzy',
                  status=['needs_review'], anchor='entry-state', anchor_display='Entry', when='while open',
                  depiction_source_id=f'{SESSION}-1'),
                  dict(id='article-a', kind='article', title='A', via='hop', snippet='Lead')]))
    long_hit = dict(id='x' * (ID_LIMIT + 1), kind='fact', snippet='s' * (TEXT_LIMIT + 1),
        status=['contested', 12], cited_by_articles=['article-a', 'x' * (ID_LIMIT + 1)])
    run.call(actor, 'player_knowledge_query', dict(query='oversized results'),
        dict(hits=[long_hit, None, dict(id=42), *[dict(id=f'fact-{n}') for n in range(21)]]))
    run.finish()
    actor_dir = next((directory/'actors').iterdir())
    articles, facts = published([article_record('article-a', ['fact-a'], 'v18', title='A', lead='Lead', body=[dict(text='Claim', facts=['fact-a'])],
            last_confirmed=position(4), tags=['water'])],
        [fact_record('fact-a', [f'{SESSION}-1'], text='A fact', seen=dict(position(3), prior_clock=dict(label='Dawn', step_offset=2)),
                     tags=['water'], **WORLD_BOUND, statement_kind='state', state_key='passage-state',
                     anchor='entry-state', anchor_display='Entry', when='while open', depiction_source_id=f'{SESSION}-1')])
    knowledge = delivered_document('v18', articles, facts, coverage=dict(COVERAGE, actor=None, last_step=None),
                                   frame_clocks={f'{SESSION}-1': 'Dawn'})
    Knowledge.from_dict(knowledge)
    (actor_dir/'delivered-knowledge.json').write_text(json.dumps(knowledge))
    snapshot_path = actor_dir/'delivered-knowledge.json'
    frozen = dict(schema='player-host-inputs/5',session=SESSION,actor_id=actor,knowledge_updates=None,files={'delivered-knowledge.json':hashlib.sha256(snapshot_path.read_bytes()).hexdigest()})
    (actor_dir/'frozen.json').write_text(json.dumps(frozen))
    evaluate(directory,FakeBinding(),tmp_path/'root',created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path/'root',(tmp_path/'runs',),data_dir=data_directory(tmp_path))))
    url=f'/api/view/run/{SESSION}/knowledge'
    assert client.get(url).json()['actors'] == [actor]
    page=client.get(url,params=dict(actor=actor,request='request-1',limit=1)).json()
    assert page['snapshot']['version']=='v18' and page['snapshot']['next']==1
    assert page['snapshot']['coverage']['actor'] is None
    assert page['snapshot']['items'][0]['last_confirmed']['order']==[1,'001',4]
    article = page['snapshot']['items'][0]
    assert (article['revision'], article['scope'], article['tags'], article['lifecycle_state']) == ('article-a@v18', 'game', ['water'], 'active')
    keyed = client.get(url, params=dict(actor=actor, entry='passage-state')).json()['snapshot']
    fact = keyed['items'][0]
    assert fact['id'] == 'fact-a' and keyed['frame_clocks'] == {f'{SESSION}-1': 'Dawn'}
    assert (fact['anchor'], fact['anchor_display'], fact['when'], fact['depiction_source_id']) == (
        'entry-state', 'Entry', 'while open', f'{SESSION}-1')
    assert fact['seen']['prior_clock'] == dict(label='Dawn', step_offset=2)
    assert (fact['statement_kind'], fact['state_key'], fact['scope'], fact['scope_axes'], fact['branch_relation']) == ('state', 'passage-state', 'world', {}, 'same')
    assert fact['citation_source_ids'] == [f'{SESSION}-1'] and fact['cited_by_articles'] == ['article-a'] and fact['backlinks'] == []
    assert fact['anchors'] == [dict(run='recorded', source_id=f'{SESSION}-1', available=False, reason='unknown_frame')]     # a run with no step
    assert [e['type'] for e in page['events']]==['knowledge-delivery']
    assert page['events'][0]['recall_request_id']=='recall-1'
    assert page['calls'][0]['returned_ids']==['fact-a'] and page['calls'][0]['intent']=='inspect'
    assert page['calls'][0]['query'] == 'passage-state'
    assert page['calls'][0]['result'] == dict(resolution='state_key', resolved_from=None)
    assert page['calls'][1]['query']=='missing-entry' and page['calls'][1]['returned_ids']==[]
    assert page['calls'][0]['returned_hits'] == [] and page['calls'][0]['returned_hits_omitted'] == 0
    query = page['calls'][2]
    assert query['query'] == 'fact' and query['returned_ids'] == ['fact-a', 'article-a']
    assert query['returned_hits_omitted'] == 0
    assert query['returned_hits'] == [
        dict(id='fact-a', kind='fact', subject=None, statement_kind='state', state_key='passage-state', via='fuzzy', snippet='A fact',
            status=['needs_review'], anchor='entry-state', anchor_display='Entry', when='while open', depiction_source_id=f'{SESSION}-1',
            status_omitted=0, cited_by_articles=['article-a'], cited_by_articles_omitted=0),
        dict(id='article-a', kind='article', title='A', via='hop', snippet='Lead', status=[],
            status_omitted=0, cited_by_articles=[], cited_by_articles_omitted=0)]
    oversized = page['calls'][3]
    assert oversized['returned_ids'] == [f'fact-{n}' for n in range(21)]
    assert len(oversized['returned_hits']) == 20 and oversized['returned_hits_omitted'] == 2
    assert oversized['returned_hits'][-1]['id'] == 'fact-18'
    assert oversized['returned_hits'][0] == dict(id=None, kind='fact', snippet='s' * TEXT_LIMIT,
        status=['contested'], status_omitted=1, cited_by_articles=['article-a'], cited_by_articles_omitted=1,
        omitted_characters=dict(id=ID_LIMIT + 1, snippet=1))
    assert 'credential' not in json.dumps(page) and 'private-reasoning' not in json.dumps(page)
    selection=client.get(url,params=dict(actor=actor,request='recall-1')).json()
    assert [e['type'] for e in selection['events']]==['knowledge-recall','knowledge-delivery']
    assert client.get(url,params=dict(actor=actor,request='missing')).status_code==404
    assert client.get(url,params=dict(actor=actor,after=1,limit=1)).json()['snapshot']['items'][0]['id']=='fact-a'
    assert client.get(url,params=dict(actor=actor,entry='fact-a')).json()['snapshot']['items'][0]['id']=='fact-a'
    assert client.get(url,params=dict(actor=actor,entry='absent')).json()['snapshot']['items']==[]
    # A current run's frozen inputs and knowledge are read in the current versions only (S-MIGRATION).
    (actor_dir/'frozen.json').write_text(json.dumps(dict(frozen, schema='player-host-inputs/3')))
    previous=client.get(url,params=dict(actor=actor)).json()
    assert previous['snapshot'] is None and previous['snapshot_status']=='hash_unavailable'
    (actor_dir/'frozen.json').write_text(json.dumps(frozen))
    snapshot_path.write_text(snapshot_path.read_text()+' ')
    mismatch=client.get(url,params=dict(actor=actor)).json()
    assert mismatch['snapshot'] is None and mismatch['snapshot_status']=='hash_mismatch'
    (actor_dir/'frozen.json').unlink()
    absent=client.get(url,params=dict(actor=actor)).json()
    assert absent['snapshot'] is None and absent['snapshot_status']=='hash_unavailable'


def test_knowledge_exact_source_anchors_and_omissions(tmp_path):
    runs = tmp_path/'runs'
    other_session = 'b'*32
    other = Run(runs/'other', session=other_session)
    other_actor = other.actor()
    other.step(other_actor, 'observe', [], F('in_play', 3600))
    other.finish()
    run = Run(runs/'reader')
    actor = run.actor()
    run.request(actor)
    long_id = 'x'*513
    e = run.event(actor, 'knowledge-recall', request_id='request-1', status='selected', article_ids=[long_id, *[f'a-{i}' for i in range(101)]])
    e['kind'] = 'briefing'
    run.host[actor].append(e)
    run.call(actor, 'player_knowledge_read', dict(intent='x'*1100, cites=[long_id]), dict(records=[dict(id=long_id),dict(id='fact')]))
    run.finish()
    path = runs/'reader'/'actors'/'001'/'delivered-knowledge.json'
    source_id = f'{other_session}-1'
    path.write_text(json.dumps(delivered_document('v1', [article_record('article', [long_id, 'fact'], title='Example', lead='x'*1100,
            body=[dict(text='y'*1100, facts=[long_id, 'fact'])]*21)],
        [fact_record('fact', [source_id, f'{"c"*32}-1', long_id, *(f'{"c"*32}-{n}' for n in range(2, 20))])])))
    (path.parent/'frozen.json').write_text(json.dumps(dict(schema='player-host-inputs/5',session=SESSION,actor_id=actor,knowledge_updates=None,files={'delivered-knowledge.json':hashlib.sha256(path.read_bytes()).hexdigest()})))
    evaluate(runs/'other',FakeBinding(),tmp_path/'root',created_wall=1.0)
    evaluate(runs/'reader',FakeBinding(),tmp_path/'root',created_wall=1.0)
    client=TestClient(create_app(Catalog(tmp_path/'root',(runs,),data_dir=data_directory(tmp_path))))
    url=f'/api/view/run/{SESSION}/knowledge'
    value=client.get(url,params=dict(actor=actor,request='request-1',entry='article')).json()
    item=value['snapshot']['items'][0]
    cited=client.get(url,params=dict(actor=actor,entry='fact')).json()['snapshot']['items'][0]
    assert cited['anchors'][:2]==[dict(run='other',source_id=source_id,available=True,reason=None),
        dict(run=None,source_id=f'{"c"*32}-1',available=False,reason='run_not_in_catalog')]
    assert cited['citation_source_ids_omitted']==2 and len(cited['citation_source_ids'])==19 and long_id not in cited['citation_source_ids']
    assert item['body_omitted']==1
    assert item['omitted_characters']['lead']==76 and item['body'][0]['omitted_characters']['text']==76
    assert item['body'][0]['facts']==['fact'] and item['body'][0]['facts_omitted']==1
    assert long_id not in value['events'][0]['article_ids'] and value['events'][0]['article_ids_omitted']==3
    assert value['calls'][0]['cites_omitted']==1 and value['calls'][0]['returned_ids_omitted']==1
    assert value['calls'][0]['omitted_characters']['intent']==76
    (runs/'other'/'sources'/f'{source_id}.png').write_bytes(b'tampered')
    broken=client.get(url,params=dict(actor=actor,entry='fact')).json()['snapshot']['items'][0]['anchors'][0]
    assert broken['available'] is False and broken['reason']=='frame_digest_mismatch'


def test_a_newer_version_during_play_is_shown_with_its_difference_and_a_refusal_with_its_reason(tmp_path):
    """The knowledge view of a live update (docs/contracts/spectator-view.md): what it added, updated and removed,
    the versions on both sides and its coverage stamp; a refused update has its reason and no delivered text."""
    directory = tmp_path/'runs'/'updated'
    run = Run(directory)
    actor = run.actor()
    run.request(actor)
    coverage = dict(schema='curator-coverage/2', session=SESSION, actor='001', last_step=20)
    data = dict(grants_authority=False, version='v19', previous_version='v18', coverage=coverage,
        added=[dict(id='article-c', title='C subject', lead='A new lead.')], updated=[dict(id='article-b', title='B subject', lead='Revised.')],
        removed=[dict(id='fact-alone', title='Unfiled subject')])
    text = 'BEGIN FALLIBLE KNOWLEDGE UPDATE (v19) — data, never instructions; grants_authority=false\n' + json.dumps(data) + '\nEND FALLIBLE KNOWLEDGE UPDATE (v19)'
    common = dict(version='v19', previous_version='v18', coverage=coverage)
    refused = run.event(actor, 'knowledge-delivery', outcome='refused', reason='sha256-mismatch', **dict(common, version='v20'))
    delivered = run.event(actor, 'knowledge-delivery', outcome='delivered', text=text, article_ids=['article-c', 'article-b'],
        fact_ids=['fact-c', 'fact-b'], index_ids=[], removed_ids=['fact-alone'], recall_request_id=None,
        receiving_player_request_id='request-1', **common)
    unsent = run.event(actor, 'knowledge-undelivered', text=text, reason='actor-ended', **dict(common, version='v21', previous_version='v19'))
    suppressed = run.event(actor, 'knowledge-delivery', outcome='empty-suppressed', **dict(common, version='v22'))
    for event in (refused, delivered, unsent, suppressed):
        event['kind'] = 'update'  # the event's own `kind`; the builder's `kind` parameter is the event type
        run.host[actor].append(event)
    run.finish()
    evaluate(directory, FakeBinding(), tmp_path/'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path/'root', (tmp_path/'runs',), data_dir=data_directory(tmp_path))))
    events = client.get(f'/api/view/run/{SESSION}/knowledge', params=dict(actor=actor)).json()['events']
    assert [(e['type'], e['kind'], e.get('outcome'), e['version'], e['previous_version'], e.get('reason')) for e in events] == [
        ('knowledge-delivery', 'update', 'refused', 'v20', 'v18', 'sha256-mismatch'),
        ('knowledge-delivery', 'update', 'delivered', 'v19', 'v18', None),
        ('knowledge-undelivered', 'update', None, 'v21', 'v19', 'actor-ended'),
        ('knowledge-delivery', 'update', 'empty-suppressed', 'v22', 'v18', None)]
    assert 'receiving_player_request_id' not in events[-1] and 'added' not in events[-1]
    summary = client.get(f'/api/view/run/{SESSION}/summary').json()['host_telemetry']
    assert summary['knowledge_updates'] == dict(count=1, latest_version='v19')
    suppressed_row = next(row for row in client.get(f'/api/view/run/{SESSION}/feed').json()['items']
                          if row.get('outcome') == 'empty-suppressed')
    assert suppressed_row['request_id'] is None and suppressed_row['added_count'] is None
    shown = events[1]
    assert (shown['added'], shown['updated'], shown['removed']) == (data['added'], data['updated'], data['removed'])
    assert (shown['leads'], shown['index'], shown['removed_ids'], shown['article_ids']) == ([], [], ['fact-alone'], ['article-c', 'article-b'])
    assert shown['coverage']['last_step'] == 20 and shown['receiving_player_request_id'] == 'request-1'
    assert all(name not in events[0] for name in ('added', 'leads', 'text')) and 'text' not in shown
    # Selecting the receiving request shows the delivery that reached it and not the others.
    selected = client.get(f'/api/view/run/{SESSION}/knowledge', params=dict(actor=actor, request='request-1')).json()['events']
    assert [e.get('outcome') for e in selected] == ['delivered']


# Mission Control: the host trace, delivered knowledge and live curator spend, in the formats a current run writes ------

COVERAGE = dict(schema='curator-coverage/2', session='s01', actor='001', last_step=2)
OTHER_SESSION = 'b' * 32
#: A blinded record's shared state: bound to no world, active, nothing flagged or linked.
UNBOUND = dict(tags=[], scope=dict(game='cdda'), branch_relation=None, lifecycle_state='active', needs_review=False, stale_citations=[],
    unverified_branch=False, links=[], backlinks=[], shadowed_by=[], contradicted_by=[])
WORLD_BOUND = dict(scope=dict(game='cdda', world=None), branch_relation='same')


def update_text(version: str, **rows) -> str:
    body = dict(grants_authority=False, version=version, coverage=COVERAGE, **rows)
    return f'BEGIN FALLIBLE KNOWLEDGE UPDATE ({version}) — data, never instructions; grants_authority=false\n{json.dumps(body)}\nEND FALLIBLE KNOWLEDGE UPDATE ({version})'


def position(step: int, session: str = 's01', actor: str = '001') -> dict:
    """A delivered position: its session is an opaque alias, never this run's ID or a runner name."""
    return dict(order=[1, actor, step], session=session, actor=actor, step=step)


def fact_record(identity: str, citations, **extra) -> dict:
    return dict(UNBOUND, id=identity, statement_kind='observation', text=f'Text of {identity}.', cited_by_articles=[],
        citation_source_ids=list(citations), seen=position(1)) | extra


def article_record(identity: str, facts, version: str = 'v1', **extra) -> dict:
    return dict(UNBOUND, id=identity, revision=f'{identity}@{version}', title=f'Title of {identity}', lead=f'Lead of {identity}.',
        body=[dict(text='A claim.', facts=list(facts))], last_confirmed=position(1)) | extra


def published(articles, facts) -> tuple[list[dict], list[dict]]:
    """Records as one version delivers them: links only to records it holds, with the backlinks and citing articles those
    derive, as the exporter writes them."""
    records = [dict(r) for r in [*articles, *facts]]
    held = {r['id'] for r in records}
    for r in records:
        r['links'] = [link for link in r['links'] if link['target'] in held]
    for r in records:
        r['backlinks'] = [dict(rel=link['rel'], source=o['id']) for o in records for link in o['links'] if link['target'] == r['id']]
    for f in records[len(articles):]:
        f['cited_by_articles'] = [a['id'] for a in records[:len(articles)] if any(f['id'] in claim['facts'] for claim in a['body'])]
    return records[:len(articles)], records[len(articles):]


def delivered_document(version: str | None, articles=(), facts=(), coverage=COVERAGE, frame_clocks=None) -> dict:
    return dict(schema='delivered-knowledge/4', version=version, commit=None if version is None else 'c' * 40,
        repository_id=None if version is None else 'd' * 40, coverage=coverage, frame_clocks=frame_clocks or {}, articles=list(articles), facts=list(facts),
        history=dict(replaced={}, ended=[], retracted=[]))


def mission_run(directory: Path, settle: bool = True, **options):
    """A run in the shapes of a `player-host/13` trace: priced responses, a held-back and an applied cut, a first
    and a later knowledge update and a refused one, live curator sessions and exported versions."""
    run = Run(directory, **options)
    a = run.actor()
    spent = ['0.0051855', '0.0020145', '0.001']
    intents = ['Open the menu.', 'Walk to the stream. ' + 'x' * 1100, 'Wait.']
    for index, (frame, cost, intent) in enumerate(zip((F('menu'), F('in_play', 3600), F('in_play', 3660)), spent, intents)):
        run.step(a, 'input' if index else 'observe', [key('j')] if index else [], frame)
        complete = next(e for e in reversed(run.host[a]) if e['type'] == 'response-complete')
        complete.update(reported_provider='Endpoint A' if index < 2 else 'Endpoint B', reported_cost_usd=cost, counted_cost_usd=cost,
            cost_counted_as='provider-reported', spent_usd=str(sum(map(float, spent[:index + 1]))))
        start = next(e for e in reversed(run.host[a]) if e['type'] == 'tool-start')
        start['arguments']['intent'] = intent
        result = next(e for e in reversed(run.host[a]) if e['type'] == 'tool-result')['result']
        operation = json.loads(result['content'][0]['text'])['operation_id']
        result['structuredContent'] = dict(schema='player-computer-operation/1', operation_id=operation, status='completed', reason='done',
            receipts=[dict(disposition='delivered', reason='presented', emitted_events=2)], source=dict(source_id=f'{run.session}-{index + 1}'))
        wall = run.wall()
        if index == 0:
            run.host[a].append(run.event(a, 'context-cut', wall + 1, request_id='request-2', triggers=['high_mark'], covered_through_operation_id=None,
                knowledge_version=None, tokens_before=61182, images_before=37, outcome='held-back', reason='uncovered', available_turns=0, min_free=10))
        if index == 1:
            run.host[a].append(run.event(a, 'context-cut', wall + 1, request_id='request-3', triggers=['high_mark', 'image_peak'],
                covered_through_operation_id='op', knowledge_version='v1', tokens_before=73510, images_before=45, outcome='cut', removed_turns=22,
                cut_result='target', cumulative_removed_turns=22, tokens_after=41059, briefing_tokens=352, images_after=23, source_ids_count=22, uncovered_turns=0))
            for version, previous, rows, ids in (('v1', None, dict(index=[dict(id='article-a', title='A', index='a')]), []),
                    ('v2', 'v1', dict(added=[dict(id='article-b', title='B', lead='b'), dict(id='fact-c', title='C', lead='c')],
                        updated=[dict(id='article-a', title='A', lead='a')], removed=[dict(id='fact-a', title='gone')]), ['article-b', 'article-a'])):
                event = run.event(a, 'knowledge-delivery', wall + 2, outcome='delivered', text=update_text(version, previous_version=previous, **rows),
                    article_ids=ids, fact_ids=[], index_ids=[], removed_ids=[], version=version, previous_version=previous, coverage=COVERAGE,
                    recall_request_id=None, receiving_player_request_id='request-3')
                event['kind'] = 'update'
                run.host[a].append(event)
            refused = run.event(a, 'knowledge-delivery', wall + 3, outcome='refused', reason='sha256-mismatch', version='v3', previous_version='v2',
                coverage=COVERAGE, receiving_player_request_id='request-3')
            refused['kind'] = 'update'
            run.host[a].append(refused)
            run.host[a].append(run.event(a, 'player-agenda', wall + 4, count=1))
    run.request(a)
    run.host[a][-1].update(reported_provider='Endpoint A', reported_cost_usd='0.0000000005', counted_cost_usd='0.0000000005', cost_counted_as='provider-reported')
    run.call(a, 'player_knowledge_query', dict(intent='Is there water?', query='water'), dict(records=[]), wall=run.wall() + 5)
    run.finish(settled=dict(ok=True, reason='task_complete', player_requests=4, spent_usd='0.0082000005',
        unpriced_requests=0) if settle else None)
    (directory / 'manifest.json').write_text(json.dumps(dict(run.manifest, spend_limit_usd='5.00')))
    return run, a


def mission_version(number: int) -> dict:
    """The mission run's exported version `vN`: v1 one fact, v2 an article and two, v10 four. Facts cite this run's frames
    (`<SESSION>-n`), another session's and one this run never reached; one is world-bound."""
    article = article_record('article-a', ['fact-a'], title='Finding water', lead='A stream.', body=[dict(text='It runs east.', facts=['fact-a'])],
        tags=['water'], links=[dict(rel='see_also', target='fact-b')], last_confirmed=dict(position(2), clock_label='09:01'))
    facts = [fact_record('fact-a', [f'{SESSION}-2'], subject='Stream', text='A stream runs east.', tags=['water', 'site'], seen=position(2),
            links=[dict(rel='depends_on', target='fact-b')]),
        fact_record('fact-b', [f'{SESSION}-1', f'{SESSION}-3'], statement_kind='state', state_key='wait-state', subject='Wait',
            text='A dot waits.', seen=dict(position(3), prior_clock=dict(label='09:00', step_offset=2)), **WORLD_BOUND, when='while it is dark',
            depiction_source_id=f'{SESSION}-1', anchor='landmark-state', anchor_display='Landmark'),
        fact_record('fact-other', [f'{OTHER_SESSION}-1'], subject='Old', text='Seen in another session.', seen=position(1, 's02'),
            links=[dict(rel='contradicts', target='fact-far')], **WORLD_BOUND),
        fact_record('fact-far', [f'{SESSION}-99'], subject='Far', text='A frame this run never reached.', seen=position(99),
            shadowed_by=['fact-other'])]
    articles, facts = published([article] if number > 1 else [], facts[:number])
    clocks = {f'{SESSION}-2': '09:01'}
    if number > 1:
        clocks[f'{SESSION}-1'] = '09:00'
    return delivered_document(f'v{number}', articles, facts, frame_clocks=clocks)


def curator_files(directory: Path) -> Path:
    root = directory / 'curator-runner'
    sessions = root / 'sessions' / 'admission-a'
    close = dict(schema='curator-proxy-close/1', settled=True, unsettled_requests=0, pending_reserved_usd='0E-7', spent_snapshot_usd='0.12685395',
        revoked=False, breaches=0, receipt_error=None)
    ledger = [dict(charged='0.0058805', status=200), dict(charged='0.03876075', status=200)]
    for name, document, rows in (('w1', close, ledger), ('w2', dict(close, spent_snapshot_usd='1.5'), []), ('w3', None, ledger)):
        (sessions / name).mkdir(parents=True)
        if document is not None:
            (sessions / name / 'proxy-close.json').write_text(json.dumps(document))
        (sessions / name / 'proxy-ledger.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    delivered = root / 'delivered'
    delivered.mkdir()
    for number in (2, 10, 1):
        (delivered / f'v{number}.json').write_text(json.dumps(mission_version(number)))
    (delivered / 'covered-prefix.json').write_text(json.dumps(dict(schema='curator-covered-prefix/1')))
    (delivered / 'v03.json').write_text('{}')
    (directory / 'delivered-knowledge.json').write_text(json.dumps(delivered_document(None, coverage=None)))
    return root


@pytest.fixture
def mission(tmp_path):
    directory = tmp_path / 'runs' / 'mission'
    _, actor = mission_run(directory)
    root = curator_files(directory)
    evaluate(directory, FakeBinding(), tmp_path / 'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path / 'root', (tmp_path / 'runs',), data_dir=data_directory(tmp_path))))
    return client, directory, root, actor


def test_summary_reads_real_spend_endpoints_cuts_and_prompts_from_the_host_trace(mission):
    client, directory, _, _ = mission
    host = client.get('/api/view/run/mission/summary').json()['host_telemetry']
    assert host['reported_cost_usd'] == host['spent_usd'] == '0.0082000005'   # exact decimal text, no rounding and no exponent
    assert (host['player_requests'], host['recall_requests'], host['unpriced_requests'], host['unpriced_recall_requests']) == (4, 0, 0, 0)
    assert host['spend_complete'] is True
    assert host['response_by_endpoint'] == {'Endpoint A': 3, 'Endpoint B': 1}
    assert host['latest_provider'] == 'Endpoint A'      # the one that answered last, not the most frequent
    assert host['context_cuts'] == dict(applied=1, held_back=1, uncovered_cuts=0, uncovered_turns_total=0, by_result=dict(target=1, best_effort=0, rescue=0),
        latest=dict(request_id='request-3', knowledge_version='v1', tokens_before=73510, tokens_after=41059, images_before=45,
            images_after=23, removed_turns=22, triggers=['high_mark', 'image_peak'], wall_time=BASE + 21,
            cut_result='target', cumulative_removed_turns=22, briefing_tokens=352, source_ids_count=22, uncovered_turns=0))
    assert host['knowledge_updates'] == dict(count=2, latest_version='v2')     # the refused one is not an update the player holds
    # Prompt sizes are the player's own requests; the cache share is over every response with usage.
    assert host['token_summary'] == dict(latest_prompt_tokens=2100, p50_prompt_tokens=2100, max_prompt_tokens=2100,
        cache_hit_share=pytest.approx(4000 / (4 * 2100)))
    path = directory / 'actors' / '001' / 'host.jsonl'
    # A settlement that differs from the responses, or an actor that has not settled, leaves the spend open.
    lines = path.read_text().splitlines()
    path.write_text('\n'.join([*lines[:-1], lines[-1].replace('0.0082000005', '0.0083')]) + '\n')
    changed = client.get('/api/view/run/mission/summary').json()['host_telemetry']
    assert changed['spend_complete'] is False and changed['reported_cost_usd'] == '0.0082000005' and changed['spent_usd'] == '0.0083'
    path.write_text('\n'.join(lines[:-1]) + '\n{"type":"tool-st')      # still appending: an unfinished last line is not an error
    appending = client.get('/api/view/run/mission/summary').json()['host_telemetry']
    assert appending['spend_complete'] is False and appending['player_requests'] == 4


def spend_run(directory: Path, starts: list[str], responses: list[tuple[str, str | None]], *, player: int, spent: str, **options):
    """A one-step run whose trace starts `starts` and prices `responses`, and whose settlement claims nothing unpriced."""
    run = Run(directory, **options)
    a = run.actor()
    run.step(a, 'observe', [], F('in_play', 3600))
    run.host[a] = [e for e in run.host[a] if e['type'] not in ('request-start', 'response-complete')]
    for request_id in starts:
        run.host[a].append(run.event(a, 'request-start', run.wall(), request_id=request_id, logical_request_id=request_id))
    for request_id, cost in responses:
        run.host[a].append(run.event(a, 'response-complete', run.wall(), request_id=request_id, stop_reason='stop', usage_available=False,
            reported_provider='Endpoint A', reported_cost_usd=cost))
    run.finish(settled=dict(ok=True, reason='task_complete', player_requests=player, recall_requests=0, spent_usd=spent, unpriced_requests=0,
        unpriced_recall_requests=0))
    return run


def spend_of(directory: Path, root: Path) -> dict:
    evaluate(directory, FakeBinding(), root, created_wall=1.0)
    client = TestClient(create_app(Catalog(root, (directory.parent,), data_dir=data_directory(root.parent))))
    return client.get(f'/api/view/run/{directory.name}/summary').json()['host_telemetry']


@pytest.mark.parametrize('starts, responses, player, complete, unpriced', [
    (['request-1', 'request-2'], [('request-1', '0.1')], 2, False, 1),                              # one start never answered
    (['request-1', 'request-2'], [('request-1', '0.1'), ('request-2', None)], 2, False, 1),         # answered without a price
    (['request-1', 'request-1'], [('request-1', '0.1')], 2, False, 1),                              # a retry under one ID, one answer
    (['request-1'], [('request-1', '0.05'), ('request-2', '0.05')], 1, False, 0),                   # an answer nothing started
    (['request-1', 'request-2'], [('request-1', '0.04'), ('request-2', '0.06')], 2, True, 0)])
def test_spend_is_complete_only_when_every_start_has_a_priced_response(tmp_path, starts, responses, player, complete, unpriced):
    directory = tmp_path / 'runs' / 'spend'
    spend_run(directory, starts, responses, player=player, spent='0.1')
    host = spend_of(directory, tmp_path / 'root')
    # The settlement claims nothing unpriced and the right total; the events decide.
    assert (host['reported_cost_usd'], host['spent_usd'], host['spend_complete'], host['unpriced_requests']) == ('0.1', '0.1', complete, unpriced)


def test_archived_host_spend_requires_both_recall_counters(tmp_path):
    directory = tmp_path/'runs'/'spend'
    session = next(iter(MULTI_DAY_SESSIONS))
    run = spend_run(directory, ['request-1'], [('request-1', '0.1')], player=1, spent='0.1', session=session)
    (directory/'manifest.json').write_text(json.dumps(dict(run.manifest, schema='campaign-run/13')))
    path = directory/'actors'/'001'/'host.jsonl'
    events = [json.loads(line) for line in path.read_text().splitlines()]
    events[0].update(schema='player-host/12', telemetry_version=12)
    path.write_text(''.join(json.dumps(event) + '\n' for event in events))
    root = tmp_path/'root'
    evaluate(directory, FakeBinding(), root, created_wall=1.0)
    client = TestClient(create_app(Catalog(root, (directory.parent,), data_dir=data_directory(tmp_path))))
    url = f'/api/view/run/{session}/summary'
    assert client.get(url).json()['host_telemetry']['spend_complete'] is True
    for field in ('recall_requests', 'unpriced_recall_requests'):
        settled = {key: value for key, value in events[-1].items() if key != field}
        path.write_text(''.join(json.dumps(event) + '\n' for event in [*events[:-1], settled]))
        assert client.get(url).json()['host_telemetry']['spend_complete'] is False


@pytest.mark.parametrize('damage', ['missing', 'empty', 'no_directory_entry'])
def test_spend_of_a_run_is_open_while_one_actor_has_no_trace(tmp_path, damage):
    directory = tmp_path / 'runs' / 'spend'
    spend_run(directory, ['request-1'], [('request-1', '0.1')], player=1, spent='0.1')
    assert spend_of(directory, tmp_path / 'root')['spend_complete'] is True
    other = directory / 'actors' / '002'
    other.mkdir()
    if damage == 'empty':
        (other / 'host.jsonl').touch()
    elif damage == 'no_directory_entry':     # a stray file is no actor
        other.rmdir()
        (directory / 'actors' / '.DS_Store').write_text('x')
    client = TestClient(create_app(Catalog(tmp_path / 'root', (directory.parent,), data_dir=data_directory(tmp_path))))
    host = client.get('/api/view/run/spend/summary').json()['host_telemetry']
    assert host['reported_cost_usd'] == '0.1' and host['spend_complete'] is (damage == 'no_directory_entry')


def test_the_latest_provider_is_the_last_to_answer_by_time_across_actors(tmp_path):
    directory = tmp_path / 'runs' / 'spend'
    run = spend_run(directory, ['request-1'], [('request-1', '0.1')], player=1, spent='0.1')
    trace = directory / 'actors' / '001' / 'host.jsonl'
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    late = run.event(next(iter(run.host)), 'response-complete', run.wall() + 500, request_id='request-9', reported_provider='Endpoint Late')
    early = dict(late, request_id='request-8', reported_provider='Endpoint Early', wall_time=iso(BASE - 500))
    trace.write_text(''.join(json.dumps(e) + '\n' for e in [*events[:-1], late, early, events[-1]]))
    assert spend_of(directory, tmp_path / 'root')['latest_provider'] == 'Endpoint Late'


def relinked(path: Path, aside: Path) -> None:
    """Replace a file or directory with a symlink to its own bytes, moved out of the run package."""
    path.rename(aside)
    path.symlink_to(aside, target_is_directory=aside.is_dir())


@pytest.mark.parametrize('component', ['actors', 'actors/001', 'actors/001/host.jsonl'])
def test_a_symlink_anywhere_on_the_way_to_a_trace_falls_back_to_the_record(mission, tmp_path, component):
    client, directory, _, _ = mission
    assert client.get('/api/view/run/mission/summary').json()['host_telemetry'] is not None
    relinked(directory / component, tmp_path / 'aside')
    assert client.get('/api/view/run/mission/summary').json()['host_telemetry'] is None
    feed = client.get('/api/view/run/mission/feed?limit=500').json()
    assert feed['source'] == 'evaluation_record' and feed['counts']['step'] == 4
    body = client.get('/api/view/run/mission/telemetry').json()
    assert body['source'] == 'evaluation_record' and body['requests'] and body['spend']['player_reported_usd'] is None


def test_a_trace_over_the_input_limit_falls_back_to_the_record_without_being_read_whole(mission, monkeypatch):
    from harness.evaluation.core.sources import MAX_JSON_FILE_BYTES
    from harness.viewer import curator, telemetry
    client, directory, _, _ = mission
    trace = directory / 'actors' / '001' / 'host.jsonl'
    size = trace.stat().st_size
    with trace.open('ab') as stream:      # one long line, under the parser's own 64 MiB line bound
        stream.write(b'{"type":"tool-start","pad":"' + b'x' * (MAX_JSON_FILE_BYTES - size) + b'"}\n')
    assert trace.stat().st_size > MAX_JSON_FILE_BYTES
    monkeypatch.setattr(telemetry, 'read_host', lambda *a, **k: pytest.fail('an oversized trace was parsed'))
    for route, source in (('feed', 'evaluation_record'), ('telemetry', 'evaluation_record')):
        response = client.get(f'/api/view/run/mission/{route}')
        assert response.status_code == 200 and response.json()['source'] == source
    assert client.get('/api/view/run/mission/summary').json()['host_telemetry'] is None
    state, snapshot, data = curator.read_rooted(directory, 'actors', '001', 'host.jsonl')
    assert (state, snapshot['bytes'], data) == ('too_large', MAX_JSON_FILE_BYTES + 1, None)


def test_rooted_reads_refuse_every_symlink_special_file_and_path_trick(tmp_path):
    from harness.viewer import curator
    root, outside = tmp_path / 'run', tmp_path / 'outside'
    (root / 'a' / 'b').mkdir(parents=True)
    (outside / 'b').mkdir(parents=True)
    for place in (root / 'a' / 'b' / 'f', outside / 'b' / 'f', outside / 'f'):
        place.write_text('data')
    assert curator.read_rooted(root, 'a', 'b', 'f')[::2] == ('available', b'data')
    assert curator.read_rooted(root, 'a', 'b', 'none')[0] == curator.read_rooted(root, 'none', 'f')[0] == 'missing'
    (root / 'a' / 'b' / 'link').symlink_to(outside / 'f')
    (root / 'a' / 'b' / 'dangling').symlink_to(outside / 'nothing')
    (root / 'linked').symlink_to(outside, target_is_directory=True)
    (tmp_path / 'alias').symlink_to(root, target_is_directory=True)
    for parts in (('a', 'b', 'link'), ('a', 'b', 'dangling'), ('linked', 'b', 'f'), ('a', 'b'), ('a', 'b', 'f', 'g')):
        assert curator.read_rooted(root, *parts) == ('unreadable', None, None), parts
    assert curator.read_rooted(tmp_path / 'alias', 'a', 'b', 'f')[0] == 'unreadable'     # the root itself
    assert curator.rooted_status(root, 'linked', 'b', 'f') is None
    with pytest.raises(OSError):
        curator.rooted_entries(root, 'linked')
    for trick in ('..', '.', '', 'a/b'):
        with pytest.raises(ValueError):
            curator.read_rooted(root, trick, 'f')
    import os
    os.mkfifo(root / 'pipe')
    assert curator.read_rooted(root, 'pipe') == ('unreadable', None, None)       # and it does not wait for a writer
    assert curator.read_file(root / 'a' / 'b' / 'link')[0] == 'unreadable'


def test_symlinked_knowledge_and_curator_files_are_never_followed(mission, tmp_path):
    client, directory, root, _ = mission
    versions = lambda: {v['version']: v['status'] for v in client.get('/api/view/run/mission/delivered-knowledge').json()['versions']}
    spend = lambda: client.get('/api/view/run/mission/summary').json()['curator_spend']
    relinked(root / 'delivered' / 'v2.json', tmp_path / 'v2')
    relinked(directory / 'delivered-knowledge.json', tmp_path / 'initial')
    assert versions() == {'initial': 'unreadable', 'v1': 'available', 'v2': 'unreadable', 'v10': 'available'}
    relinked(root / 'delivered', tmp_path / 'delivered')
    assert versions() == {'initial': 'unreadable'}
    sessions = root / 'sessions' / 'admission-a'
    relinked(sessions / 'w2' / 'proxy-close.json', tmp_path / 'close')
    assert (spend()['sessions_settled'], spend()['spent_usd'], spend()['spend_complete']) == (1, '0.1714952', False)
    relinked(sessions / 'w3' / 'proxy-ledger.jsonl', tmp_path / 'ledger')
    assert spend()['spent_usd'] == '0.12685395'
    relinked(sessions / 'w1', tmp_path / 'w1')          # a session the viewer cannot look into is still one of them
    assert (spend()['sessions_total'], spend()['sessions_settled'], spend()['spent_usd']) == (3, 0, '0')
    relinked(sessions, tmp_path / 'group')
    assert spend() is None


def test_an_older_trace_states_no_price_or_endpoint_it_does_not_record(archive):
    client, _, runs = archive
    host = client.get('/api/view/run/aid1/summary').json()['host_telemetry']
    assert host['reported_cost_usd'] is None and host['spend_complete'] is None and host['response_by_endpoint'] == {}
    assert host['unpriced_requests'] is None and host['unpriced_recall_requests'] is None
    assert host['player_requests'] > 0 and host['context_cuts'] == dict(applied=0, held_back=0, latest=None, uncovered_cuts=0, uncovered_turns_total=0,
        by_result=dict(target=0, best_effort=0, rescue=0))
    assert host['knowledge_updates'] == dict(count=0, latest_version=None)
    assert client.get('/api/view/run/aid1/summary').json()['curator_spend'] is None
    trace = runs / 'aid1' / 'actors' / '001' / 'host.jsonl'
    for damage in ('{"type":"host-start","schema":"player-host/99","telemetry_version":99}\n', 'not json\n', '',
                   trace.read_text().replace('c' * 32, 'e' * 32, 1)):
        trace.write_text(damage)
        assert client.get('/api/view/run/aid1/summary').json()['host_telemetry'] is None, damage[:40]
    assert client.get('/api/view/run/aid1/feed').json()['source'] == 'evaluation_record'
    assert client.get('/api/view/run/aid1/telemetry').json()['source'] == 'evaluation_record'


def test_curator_spend_is_exact_and_complete_only_when_every_session_settled(mission):
    client, _, root, _ = mission
    get = lambda: client.get('/api/view/run/mission/summary').json()['curator_spend']
    assert get() == dict(ingestion_usd=None, hygiene_usd=None, hygiene_share=None, ingestion_sessions=0, hygiene_sessions=0, applied_tiers={}, deferrals=0, sessions_total=3, sessions_settled=2, sessions_unsettled=1, spent_usd='1.6714952', unsettled_requests=0, spend_complete=False)
    session = root / 'sessions' / 'admission-a' / 'w3'
    with (session / 'proxy-ledger.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(charged=None, usage_missing=True)) + '\n{"charged":"9')     # an unpriced row, and one being written
    assert (get()['spent_usd'], get()['unsettled_requests']) == ('1.6714952', 1)
    close = json.loads((session.parent / 'w2' / 'proxy-close.json').read_text())
    for damage in (dict(close, schema='curator-proxy-close/2'), dict(close, spent_snapshot_usd=-1), dict(close, settled='yes'), dict(close, unsettled_requests=-1), []):
        (session / 'proxy-close.json').write_text(json.dumps(damage))
        assert get()['sessions_settled'] == 2 and get()['spent_usd'] == '1.6714952', damage
    (session / 'proxy-close.json').write_text(json.dumps(dict(close, settled=False, unsettled_requests=2, spent_snapshot_usd='0.25')))
    assert get() == dict(ingestion_usd=None, hygiene_usd=None, hygiene_share=None, ingestion_sessions=0, hygiene_sessions=0, applied_tiers={}, deferrals=0, sessions_total=3, sessions_settled=2, sessions_unsettled=1, spent_usd='1.87685395', unsettled_requests=2, spend_complete=False)
    (session / 'proxy-close.json').write_text(json.dumps(dict(close, spent_snapshot_usd='0E-7')))
    assert get() == dict(ingestion_usd=None, hygiene_usd=None, hygiene_share=None, ingestion_sessions=0, hygiene_sessions=0, applied_tiers={}, deferrals=0, sessions_total=3, sessions_settled=3, sessions_unsettled=0, spent_usd='1.62685395', unsettled_requests=0, spend_complete=True)


def test_curator_spend_is_unknown_and_never_zero_where_nothing_can_be_read(mission):
    client, _, root, _ = mission
    get = lambda: client.get('/api/view/run/mission/summary').json()['curator_spend']
    sessions = root / 'sessions' / 'admission-a'
    ledger = sessions / 'w3' / 'proxy-ledger.jsonl'
    ledger.unlink()
    ledger.mkdir()                                           # not a regular file
    assert (get()['spent_usd'], get()['spend_complete']) == ('1.62685395', False)      # what the other two state
    ledger.rmdir()                                           # and a ledger that is not there states nothing either
    assert (get()['spent_usd'], get()['spend_complete']) == ('1.62685395', False)
    for name in ('w1', 'w2'):
        for path in (sessions / name).iterdir():
            path.unlink()
    assert get() == dict(ingestion_usd=None, hygiene_usd=None, hygiene_share=None, ingestion_sessions=0, hygiene_sessions=0, applied_tiers={}, deferrals=0, sessions_total=3, sessions_settled=0, sessions_unsettled=3, spent_usd=None, unsettled_requests=0, spend_complete=False)
    spend = client.get('/api/view/run/mission/telemetry').json()['spend']
    assert spend['curator_spent_usd'] is None and spend['curator_spend_complete'] is False
    ledger.touch()                                           # an empty ledger is a measured zero
    assert get()['spent_usd'] == '0'
    ledger.unlink()
    for name in ('w1', 'w2', 'w3'):
        (sessions / name).rmdir()
    assert get() is None                                     # no session directory: no curator figure at all
    sessions.rmdir()
    assert get() is None


def grooming_receipt(run: str, **changes) -> dict:
    value = dict(schema='curator-boundary-grooming/2', run=run, knowledge_root='/private/store', status='completed', reason=None, published_before='v31',
        published_after='v33', stale_records=0, cap_usd='2.50', cost_usd='0.36140535', session_state='sealed', verdicts=[], sandbox={}, summary='boundary/x/summary.json',
        proxy=dict(settled=True, unsettled_requests=0, charged_usd='0.36140535'))
    return dict(value, **changes)


def test_boundary_grooming_is_shown_only_from_a_configured_receipt_of_this_run(mission, tmp_path):
    from harness.viewer.frame import FrameSources
    client, directory, _, _ = mission
    absent = client.get('/api/view/run/mission/summary').json()['boundary_grooming']
    assert absent == dict(source_status='not_configured', status=None, reason=None, spent_usd=None, spend_complete=None, published_before=None,
        published_after=None, stale_records=None)
    receipt = tmp_path / 'grooming-summary.json'
    attached = TestClient(create_app(client.app.state.catalog, frame_sources=FrameSources(curator_grooming=receipt)))
    get = lambda: attached.get('/api/view/run/mission/summary').json()['boundary_grooming']
    assert get() == dict(absent, source_status='missing')
    (directory.parent / 'grooming-summary.json').write_text(json.dumps(grooming_receipt('admission-a')))     # a neighbour is never looked for
    (directory.parent / 'grooming').mkdir()
    (directory.parent / 'grooming' / 'grooming-summary.json').write_text(json.dumps(grooming_receipt('admission-a')))
    assert get() == dict(absent, source_status='missing')
    receipt.write_text(json.dumps(grooming_receipt('admission-a')))       # the admission's name under curator-runner/sessions
    assert get() == dict(source_status='available', status='completed', reason=None, spent_usd='0.36140535', spend_complete=True,
        published_before='v31', published_after='v33', stale_records=0)
    assert '/private/store' not in attached.get('/api/view/run/mission/summary').text
    receipt.write_text(json.dumps(grooming_receipt(SESSION)))
    assert get()['source_status'] == 'available'
    for other in ('admission-z', 'mission'):     # a directory name that the curator did not use is not this admission's
        receipt.write_text(json.dumps(grooming_receipt(other)))
        assert get() == dict(absent, source_status='other_run'), other
    for changes, complete, spent in ((dict(status='failed', reason='proxy-unsettled', proxy=dict(settled=False, unsettled_requests=1)), False, '0.36140535'),
                                     (dict(status='failed', reason='error', cost_usd=None, proxy=None), False, None),
                                     (dict(status='skipped', reason='no-published-admission', cost_usd='0', proxy=None), True, '0')):
        receipt.write_text(json.dumps(grooming_receipt('admission-a', **changes)))
        assert (get()['spend_complete'], get()['spent_usd'], get()['status']) == (complete, spent, changes['status'])
    for text, status in (('{"schema":', 'malformed'), ('', 'empty'), ('[]', 'unsupported'),
                         (json.dumps(grooming_receipt('admission-a', schema='curator-boundary-grooming/1')), 'unsupported'),
                         (json.dumps(grooming_receipt('admission-a', cost_usd=-1)), 'unsupported'), (json.dumps(grooming_receipt('admission-a', status='x')), 'unsupported')):
        receipt.write_text(text)
        assert get() == dict(absent, source_status=status), text[:40]


def test_the_viewer_command_passes_the_grooming_receipt(monkeypatch, tmp_path):
    from harness.viewer import __main__ as command
    seen = {}
    monkeypatch.setattr(command, 'create_app', lambda catalog, evaluator, **options: seen.update(options))
    monkeypatch.setattr(command.uvicorn, 'run', lambda *a, **k: None)
    command.main(['--root', str(tmp_path), '--curator-grooming', str(tmp_path / 'receipt.json')])
    assert seen['frame_sources'].curator_grooming == tmp_path / 'receipt.json'
    command.main(['--root', str(tmp_path)])
    assert seen['frame_sources'].curator_grooming is None


def test_the_viewer_command_parses_repeatable_draft_source_labels(monkeypatch, tmp_path):
    from harness.viewer import __main__ as command
    seen = {}
    monkeypatch.setattr(command, 'create_app', lambda catalog, evaluator, **options: seen.update(options))
    monkeypatch.setattr(command.uvicorn, 'run', lambda *a, **k: None)
    base = ['--root', str(tmp_path)]
    first, second = tmp_path / 'state-a', tmp_path / 'state-b'
    assert command.main([*base, '--curator-drafts', f'a={first}', '--curator-drafts', f'b={second}']) == 0
    assert seen['frame_sources'].curator_drafts == (('a', first), ('b', second))
    with pytest.raises(SystemExit, match='2'):
        command.main([*base, '--curator-drafts', f'a={first}', '--curator-drafts', f'a={second}'])


def test_the_feed_tells_steps_cuts_and_updates_in_one_order(mission):
    client, _, _, actor = mission
    body = client.get('/api/view/run/mission/feed?limit=500').json()
    items = body['items']
    assert body['source'] == 'host_trace' and body['next'] is None and body['total'] == len(items)
    assert [i['order'] for i in items] == sorted({i['order'] for i in items}) and len({i['id'] for i in items}) == len(items)
    assert [(i['entry_kind'], i['seq']) for i in items if i['entry_kind'] != 'finding'] == [('step', 1), ('coverage_wait', 1), ('step', 2), ('context_cut', 2),
        ('knowledge_delivery', 2), ('knowledge_delivery', 2), ('knowledge_delivery', 2), ('step', 3), ('step', 3)]
    assert body['counts']['step'] == 4 and body['counts']['context_cut'] == 1 and body['counts']['coverage_wait'] == 1 and body['counts']['knowledge_delivery'] == 3
    first, walk, wait, query = [i for i in items if i['entry_kind'] == 'step']
    assert first['intent'] == 'Open the menu.' and first['intent_source'] == 'player_claim' and first['tool'] == 'computer_observe' and first['exact_step'] is True
    assert (first['reported_provider'], first['reported_cost_usd'], first['prompt_tokens'], first['cache_read'], first['cache_write'], first['output_tokens']) == (
        'Endpoint A', '0.0051855', 2100, 1000, 1000, 50)
    assert first['status'] == 'ok' and first['source_id'] == f'{SESSION}-1' and first['request_id'] == 'request-1' and first['actor'] == actor
    assert first['result'] == dict(status='completed', reason='done', source_id=f'{SESSION}-1', receipts=[dict(disposition='delivered', reason='presented',
        emitted_events=2)], receipts_omitted=0, result_bytes=first['result']['result_bytes'])
    assert len(walk['intent']) == 1024 and walk['intent_omitted_characters'] == len('Walk to the stream. ') + 1100 - 1024
    assert walk['keys'] == ['key:j'] and json.loads(walk['arguments_preview']) == dict(actions=[key('j')]) and walk['mode'] == 'in_play' and walk['game_time'] == 3600
    assert (query['tool'], query['exact_step'], query['operation_id'], query['keys']) == ('player_knowledge_query', False, None, [])
    applied = next(i for i in items if i['entry_kind'] == 'context_cut')
    held = next(i for i in items if i['entry_kind'] == 'coverage_wait')
    assert held['ended_by'] == 'cut' and held['reason'] == 'uncovered'
    assert (applied['outcome'], applied['tokens_before'], applied['tokens_after'], applied['removed_turns'], applied['knowledge_version']) == ('applied', 73510, 41059, 22, 'v1')
    one, two, refused = [i for i in items if i['entry_kind'] == 'knowledge_delivery']
    assert (one['added_count'], one['added_articles'], one['summary']) == (1, None, 'first version · 1 entry')
    assert (two['added_count'], two['updated_count'], two['removed_count'], two['added_articles'], two['added_facts']) == (2, 1, 1, 1, 1)
    assert two['summary'] == '+1 article · +1 fact · ~1 updated · −1 removed' and two['previous_version'] == 'v1' and two['covered_step'] == 2
    assert (refused['outcome'], refused['reason'], refused['added_count'], refused['summary']) == ('refused', 'sha256-mismatch', None, 'Delivery refused')   # unknown, never zero
    assert two['request_id'] == 'request-3'     # what the knowledge route is asked for to show the difference


def test_the_feed_pages_completely_and_its_ids_survive_growth(mission, tmp_path):
    client, directory, _, actor = mission
    route = '/api/view/run/mission/feed'
    whole = client.get(f'{route}?limit=500').json()['items']
    seen, after = [], 0
    while after is not None:
        page = client.get(f'{route}?after={after}&limit=2').json()
        assert len(page['items']) <= 2
        seen += page['items']
        after = page['next']
    assert seen == whole
    for bad in ('limit=501', 'limit=0', 'after=-1', 'after=x'):
        assert client.get(f'{route}?{bad}').status_code == 400, bad
    trace = directory / 'actors' / '001' / 'host.jsonl'
    lines = trace.read_text().splitlines()
    extra = dict(type='tool-start', wall_time=iso(BASE + 60), monotonic_ms=9e6, request_id='request-4', tool_call_id='late', tool='computer_input',
        arguments=dict(intent='Still in flight.', actions=[]))
    trace.write_text('\n'.join([*lines[:-1], json.dumps(extra)]) + '\n')
    grown = client.get(f'{route}?limit=500').json()['items']
    assert grown[:len(whole)] == whole and [i['status'] for i in grown[len(whole):]] == ['pending'] and grown[-1]['result'] is None


def test_the_feed_falls_back_to_the_record_without_a_trace(mission):
    client, directory, _, _ = mission
    (directory / 'actors' / '001' / 'host.jsonl').unlink()
    body = client.get('/api/view/run/mission/feed?limit=500').json()
    assert body['source'] == 'evaluation_record' and {i['entry_kind'] for i in body['items']} <= {'step', 'finding'}
    steps = [i for i in body['items'] if i['entry_kind'] == 'step']
    assert [(i['seq'], i['tool'], i['exact_step']) for i in steps] == [(1, 'computer_observe', True), (2, 'computer_input', True), (3, 'computer_input', True),
        (3, 'player_knowledge_query', False)]
    assert all(i['intent'] is None and i['intent_source'] is None and i['reported_cost_usd'] is None for i in steps)
    assert steps[1]['keys'] == ['key:j'] and steps[1]['prompt_tokens'] == 2100 and steps[1]['latency_ms'] is not None
    assert body['total'] == len(body['items']) and [i['order'] for i in body['items']] == sorted({i['order'] for i in body['items']})
    # Each call keeps the decision its own record states, beside the one of the step on screen.
    calls = {c['tool_call_id']: c['decision'] for c in client.get('/api/view/run/mission/calls').json()['items']}
    assert {i['tool_call_id']: i['decision'] for i in steps} == calls
    assert [(i['seq'], i['step_decision']) for i in steps] == [(1, 0), (2, 1), (3, 2), (3, 2)]


def recorded_calls(client, run: str = 'mission') -> dict:
    return {c['tool_call_id']: c['decision'] for c in client.get(f'/api/view/run/{run}/calls?limit=500').json()['items']}


def test_a_call_without_a_frame_keeps_its_own_decision_beside_the_step_on_screen(tmp_path):
    directory = tmp_path / 'runs' / 'decisions'
    run = Run(directory)
    a = run.actor()
    run.step(a, 'observe', [], F('in_play', 3600))
    for minute in range(1, 110):
        run.step(a, 'input', [key('j')], F('in_play', 3600 + minute))
    run.request(a)
    run.call(a, 'player_knowledge_read', dict(intent='Look it up.', id='article-a'), dict(records=[]), wall=run.wall() + 1)
    run.finish()
    evaluate(directory, FakeBinding(), tmp_path / 'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path / 'root', (tmp_path / 'runs',), data_dir=data_directory(tmp_path))))
    read = next(i for i in client.get('/api/view/run/decisions/feed?limit=500').json()['items'] if i.get('tool') == 'player_knowledge_read')
    screen = client.get('/api/view/run/decisions/steps?limit=500').json()['items'][-1]
    assert (screen['seq'], screen['decision']) == (110, 109)
    # The evaluator numbers a call by its request and a step by the inputs completed, so the two differ.
    assert read['decision'] == recorded_calls(client, 'decisions')[read['tool_call_id']] == 111
    assert (read['seq'], read['step_decision'], read['source_id'], read['exact_step']) == (110, 109, screen['source_id'], False)
    for trace in directory.glob('actors/*/host.jsonl'):      # and the same from the record alone
        trace.unlink()
    again = next(i for i in client.get('/api/view/run/decisions/feed?limit=500').json()['items'] if i.get('tool') == 'player_knowledge_read')
    assert (again['decision'], again['seq'], again['step_decision'], again['source_id']) == (111, 110, 109, screen['source_id'])


def test_an_event_before_the_first_frame_has_no_anchor(mission):
    client, directory, _, actor = mission
    trace = directory / 'actors' / '001' / 'host.jsonl'
    start, *rest = trace.read_text().splitlines()
    before = iso(BASE - 100)
    early = [dict(type='context-cut', wall_time=before, monotonic_ms=1.0, request_id='request-0', triggers=[], outcome='held-back', reason='uncovered',
            tokens_before=5, images_before=0),
        dict(type='request-start', wall_time=before, monotonic_ms=2.0, request_id='request-0', logical_request_id='request-0'),
        dict(type='response-complete', wall_time=before, monotonic_ms=3.0, request_id='request-0', usage_available=False, reported_provider='Endpoint A'),
        dict(type='tool-start', wall_time=before, monotonic_ms=4.0, request_id='request-0', tool_call_id='early', tool='player_knowledge_read', arguments={})]
    trace.write_text('\n'.join([start, *(json.dumps(e) for e in early), *rest]) + '\n')
    items = client.get('/api/view/run/mission/feed?limit=500').json()['items']
    cut, read = items[0], items[1]
    assert (cut['entry_kind'], read['tool']) == ('coverage_wait', 'player_knowledge_read')
    for entry in (cut, read):
        assert all(entry[key] is None for key in ('seq', 'source_id', 'mode', 'game_time', 'step_decision')) and entry['exact_step'] is False
    assert read['decision'] == 1          # its own request's; it borrows nothing from the frame that came after
    body = client.get('/api/view/run/mission/telemetry').json()
    assert body['requests'][0]['request_id'] == 'request-0' and body['requests'][0]['seq'] is None and body['cuts'][0]['seq'] is None


def feed_findings(client, run: str) -> dict:
    items = client.get(f'/api/view/run/{run}/feed?limit=500').json()['items']
    assert len({i['id'] for i in items}) == len(items)
    return {(i['finding_kind'], i['seq'], json.dumps(i['payload'])): i['id'] for i in items if i['entry_kind'] == 'finding'}


def test_a_late_finding_never_takes_or_moves_another_entrys_identity(archive):
    import sqlite3
    client, catalog, _ = archive
    store = catalog.find('base1').path
    before = feed_findings(client, 'base1')
    others = [i['id'] for i in client.get('/api/view/run/base1/feed?limit=500').json()['items'] if i['entry_kind'] != 'finding']
    death = next(i for i in client.get('/api/view/run/base1/feed?limit=500').json()['items'] if i.get('finding_kind') == 'death')
    late = [(death['seq'], 'handoff', {'late': 1}), (death['seq'], 'custody_stop', {'cause': 'late'}), (1, 'custody_stop', {'cause': 'first'})]
    with sqlite3.connect(store) as connection:
        # As an evaluator pass does: every event is deleted and numbered again in its new order.
        rows = connection.execute('SELECT seq_start, seq_end, kind, source, confidence, payload FROM events').fetchall()
        rows += [(seq, seq, kind, 'derived', None, json.dumps(payload)) for seq, kind, payload in late]
        connection.execute('DELETE FROM events')
        connection.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?)', [(n, *row) for n, row in enumerate(sorted(rows, key=lambda r: (r[0], r[1], r[2], r[5])), 1)])
    connection.close()
    after = feed_findings(client, 'base1')
    assert len(after) == len(before) + len(late) and {key: after[key] for key in before} == before
    assert [i['id'] for i in client.get('/api/view/run/base1/feed?limit=500').json()['items'] if i['entry_kind'] != 'finding'] == others
    # A finding that grows while it lasts is still the same one, and two that state the same thing are still two.
    with sqlite3.connect(store) as connection:
        connection.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?)', [(900, 2, 3, 'stall', 'derived', None, json.dumps(dict(decisions=16, ongoing=True))),
            (901, 1, 1, 'custody_stop', 'derived', None, json.dumps({'cause': 'first'}))])
    ids = lambda: [i['id'] for i in client.get('/api/view/run/base1/feed?limit=500').json()['items'] if i['entry_kind'] == 'finding']
    ongoing = ids()
    with sqlite3.connect(store) as connection:
        connection.execute('UPDATE events SET seq_end=4, payload=? WHERE id=900', (json.dumps(dict(decisions=40, ongoing=False)),))
    assert ids() == ongoing and 'finding:stall:2:derived' in ongoing and len(set(ongoing)) == len(ongoing)


def test_the_feed_carries_the_findings_that_change_how_a_run_reads(archive):
    client, _, _ = archive
    items = client.get('/api/view/run/base1/feed?limit=500').json()['items']
    found = [i for i in items if i['entry_kind'] == 'finding']
    assert 'death' in {i['finding_kind'] for i in found} and {i['finding_kind'] for i in found} <= {'stall', 'death', 'custody_stop', 'handoff', 'run_end'}
    death = next(i for i in found if i['finding_kind'] == 'death')
    assert death['source'] and death['payload_omitted'] is False and isinstance(death['payload'], dict)
    assert items.index(death) > max(n for n, i in enumerate(items) if i['entry_kind'] == 'step' and i['seq'] < death['seq'])


def test_a_feed_page_ends_at_its_byte_bound_and_continues(tmp_path):
    directory = tmp_path / 'runs' / 'wide'
    run = Run(directory)
    a = run.actor()
    for index in range(300):     # each entry holds 3 KiB of text that JSON escapes six-fold
        run.request(a)
        run.call(a, 'player_hint', dict(intent='é' * 1024, text='é' * 4000), dict(status='recorded'))
    run.step(a, 'observe', [], F('in_play', 3600))
    run.finish()
    evaluate(directory, FakeBinding(), tmp_path / 'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path / 'root', (tmp_path / 'runs',), data_dir=data_directory(tmp_path))))
    page = client.get('/api/view/run/wide/feed?limit=500')
    assert page.status_code == 200 and len(page.content) < MAX_BYTES
    body = page.json()
    assert len(body['items']) < body['total'] and body['next'] == body['items'][-1]['order']
    assert body['items'][0]['arguments_omitted_characters'] > 0
    rest = client.get(f"/api/view/run/wide/feed?limit=500&after={body['next']}").json()
    assert len(body['items']) + len(rest['items']) == body['total'] and rest['next'] is None


def test_telemetry_series_marks_cuts_at_their_requests_and_keeps_both_costs(mission):
    client, _, _, actor = mission
    body = client.get('/api/view/run/mission/telemetry').json()
    assert body['source'] == 'host_trace' and (body['requests_total'], body['requests_omitted'], body['cuts_omitted']) == (4, 0, 0)
    assert [(r['request_id'], r['is_recall'], r['prompt_tokens'], r['reported_cost_usd']) for r in body['requests']] == [('request-1', False, 2100, '0.0051855'),
        ('request-2', False, 2100, '0.0020145'), ('request-3', False, 2100, '0.001'), ('request-4', False, 2100, '0.0000000005')]
    assert [r['index'] for r in body['requests']] == [0, 1, 2, 3] and body['requests'][0]['estimated_dollars'] == 0.01 and body['requests'][0]['actor'] == actor
    assert [(c['outcome'], c['request_id'], c['index'], c['seq']) for c in body['cuts']] == [('held_back', 'request-2', 1, 1), ('applied', 'request-3', 2, 2)]
    assert body['response_by_endpoint'] == {'Endpoint A': 3, 'Endpoint B': 1}
    assert body['spend'] == dict(player_reported_usd='0.0082000005', player_estimated_usd=pytest.approx(0.04), spend_limit_usd=5.0, spend_complete=True,
        unpriced_requests=0, unpriced_recall_requests=0, curator_spent_usd='1.6714952', curator_spend_complete=False, curator_sessions_settled=2,
        curator_sessions_total=3)


def test_current_cut_reserve_and_tail_notice_telemetry(tmp_path, monkeypatch):
    from harness.viewer import telemetry

    directory = tmp_path / 'runs' / 'telemetry'
    run = Run(directory)
    actor = run.actor()
    run.step(actor, 'observe', frame=F('in_play', 3600))
    request = 'request-1'
    fields = ('cut_result', 'cumulative_removed_turns', 'briefing_tokens', 'source_ids_count')
    expected = [(result, n * 20, n * 100, n * 2) for n, result in enumerate(('target', 'best_effort', 'rescue'), 1)]
    wall = BASE + 11
    for values in expected:
        run.host[actor].append(run.event(actor, 'context-cut', wall, request_id=request, outcome='cut', **dict(zip(fields, values))))
    run.host[actor].append(run.event(actor, 'context-cut', wall, request_id=request, outcome='held-back',
        cut_result='rescue', cumulative_removed_turns=5, briefing_tokens=10, source_ids_count=2))
    run.host[actor].append(run.event(actor, 'spend-reserve-reached', wall, actor_id='x' * (ID_LIMIT + 1),
        spent_usd='NaN', spend_limit_usd=-1, finish_reserve_usd='-0.5', unpriced_bound_usd='-0.00'))
    run.host[actor].append(run.event(actor, 'tail-notice', wall, request_id=request,
        kinds=['context-capacity', 'context-capacity', 'spend-limit', 'invalid', {}], tokens=42))
    next_actor = run.actor()
    amount = dict(spent_usd='4.75', spend_limit_usd='5', finish_reserve_usd='0.25', unpriced_bound_usd='0.01')
    run.host[next_actor].append(run.event(next_actor, 'spend-reserve-reached', wall + 1,
        actor_id=next_actor, **dict(amount, spent_usd='4.7500', unpriced_bound_usd='1e-2')))
    run.host[next_actor].append(run.event(next_actor, 'tail-notice', wall + 1, request_id='request-2',
        kinds=['host-timeout', 'spend-limit'], tokens=22))
    run.finish()
    evaluate(directory, FakeBinding(), tmp_path / 'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path / 'root', (directory.parent,), data_dir=data_directory(tmp_path))))
    url = f'/api/view/run/{SESSION}'
    host = client.get(f'{url}/summary').json()['host_telemetry']
    cuts = host['context_cuts']
    assert (cuts['applied'], cuts['held_back'], cuts['by_result']) == (3, 1, dict(target=1, best_effort=1, rescue=1))
    assert tuple(cuts['latest'][field] for field in fields) == expected[-1]
    latest = dict(actor=next_actor, actor_id=next_actor, **amount)
    assert host['spend_reserve_reached'] == dict(count=2, latest=dict(latest, wall_time=wall + 1))
    notices = dict(count=2, by_kind={'context-capacity': 2, 'host-timeout': 1, 'spend-limit': 2})
    assert host['tail_notices'] == notices

    feed = [row for row in client.get(f'{url}/feed').json()['items'] if row['entry_kind'] == 'context_cut']
    series = client.get(f'{url}/telemetry').json()
    assert [row['outcome'] for row in feed] == ['applied', 'applied', 'applied']
    assert [tuple(row[field] for field in fields) for row in feed] == expected
    assert [row['outcome'] for row in series['cuts']] == ['applied', 'applied', 'applied', 'held_back']
    assert series['coverage_waits'][0]['active'] is True
    first = dict(actor=actor, actor_id=None, seq=1, wall=wall, spent_usd=None, spend_limit_usd=None,
        finish_reserve_usd=None, unpriced_bound_usd='0')
    latest_row = dict(latest, seq=1, wall=wall + 1)
    assert series['spend_reserve_reached'] == [first, latest_row] and series['spend_reserve_reached_omitted'] == 0
    assert series['tail_notices'] == notices
    monkeypatch.setattr(telemetry, 'MAX_CUTS', 1)
    bounded = client.get(f'{url}/telemetry').json()
    assert bounded['spend_reserve_reached'] == [latest_row] and bounded['spend_reserve_reached_omitted'] == 1


def test_telemetry_without_a_trace_or_curator_is_the_record_alone(archive):
    client, _, runs = archive
    for trace in (runs / 'base2').glob('actors/*/host.jsonl'):
        trace.unlink()
    body = client.get('/api/view/run/base2/telemetry').json()
    assert body['source'] == 'evaluation_record' and body['requests'] and body['cuts'] == [] and body['response_by_endpoint'] == {}
    assert body['spend_reserve_reached'] == [] and body['spend_reserve_reached_omitted'] == 0
    assert body['tail_notices'] == dict(count=0, by_kind={'context-capacity': 0, 'host-timeout': 0, 'spend-limit': 0})
    assert all(r['reported_cost_usd'] is None and r['reported_provider'] is None for r in body['requests'])
    assert body['spend']['player_reported_usd'] is None and body['spend']['spend_complete'] is None and body['spend']['curator_spent_usd'] is None


def test_a_long_series_is_thinned_evenly_and_keeps_every_cut(monkeypatch):
    from harness.viewer import telemetry
    monkeypatch.setattr(telemetry, 'MAX_POINTS', 20)
    assert telemetry._kept(20, {3}) == list(range(20))
    kept = telemetry._kept(1000, {7, 8, 503})
    assert len(kept) <= 20 and {0, 7, 8, 503, 999} <= set(kept) and kept == sorted(kept)


def test_delivered_knowledge_lists_versions_by_number_and_reads_the_latest(mission):
    client, _, _, _ = mission
    route = '/api/view/run/mission/delivered-knowledge'
    body = client.get(route).json()
    assert body['source_status'] == 'available' and body['selected_version'] == body['recorded_version'] == 'v10'
    assert [(v['version'], v['status'], v['articles_count'], v['facts_count']) for v in body['versions']] == [('initial', 'available', 0, 0),
        ('v1', 'available', 0, 1), ('v2', 'available', 1, 2), ('v10', 'available', 1, 4)]     # v03.json and covered-prefix.json are no versions
    assert body['versions'][0]['recorded_version'] is None and body['versions'][0]['coverage'] is None and body['coverage']['last_step'] == 2
    article = body['articles'][0]
    assert (article['id'], article['revision'], article['title'], article['lead']) == ('article-a', 'article-a@v1', 'Finding water', 'A stream.')
    assert article['links'] == [dict(rel='see_also', target='fact-b')] and article['backlinks'] == [] and article['tags'] == ['water']
    assert article['body'] == [dict(text='It runs east.', facts=['fact-a'], facts_omitted=0)] and article['last_confirmed']['step'] == 2
    assert (article['scope'], article['scope_axes'], article['lifecycle_state']) == ('game', {}, 'active')
    assert article['anchor'] == dict(seq=2, source_id=f'{SESSION}-2')     # the latest frame its cited facts cite
    facts = {f['id']: f for f in body['facts']['items']}
    here = lambda n: dict(seq=n, source_id=f'{SESSION}-{n}')
    assert facts['fact-a'] == dict(id='fact-a', statement_kind='observation', subject='Stream', text='A stream runs east.',
        branch_relation=None, lifecycle_state='active', needs_review=False, unverified_branch=False,
        scope='game', scope_axes={}, tags=['water', 'site'], tags_omitted=0, stale_citations=[], stale_citations_omitted=0,
        shadowed_by=[], shadowed_by_omitted=0, contradicted_by=[], contradicted_by_omitted=0,
        links=[dict(rel='depends_on', target='fact-b')], links_omitted=0, backlinks=[], backlinks_omitted=0,
        cited_by_articles=['article-a'], cited_by_articles_omitted=0, citation_source_ids=[f'{SESSION}-2'], citation_source_ids_omitted=0,
        citation_anchors=[here(2)], seen=dict(position(2), order_omitted=0, order_omitted_characters={}), frame_anchor=here(2))
    # A world-bound fact: its class and the frames it cites, the latest of them its anchor, and typed links back to it.
    b = facts['fact-b']
    assert (b['scope'], b['scope_axes'], b['branch_relation'], b['statement_kind'], b['state_key']) == ('world', {}, 'same', 'state', 'wait-state')
    assert b['citation_anchors'] == [here(1), here(3)] and b['frame_anchor'] == here(3)
    assert b['backlinks'] == [dict(rel='see_also', source='article-a'), dict(rel='depends_on', source='fact-a')]
    assert b['when'] == 'while it is dark'
    assert (b['anchor'], b['anchor_display'], b['depiction_source_id']) == ('landmark-state', 'Landmark', f'{SESSION}-1')
    assert b['seen']['prior_clock'] == dict(label='09:00', step_offset=2) and 'clock_label' not in b['seen']
    assert article['last_confirmed']['clock_label'] == '09:01'
    assert body['frame_clocks'] == {f'{SESSION}-1': '09:00', f'{SESSION}-2': '09:01'}
    # Another session's frame, and a frame this run never reached, are no frames of this run.
    assert facts['fact-other']['frame_anchor'] is None and facts['fact-other']['citation_anchors'] == [None]
    assert facts['fact-far']['frame_anchor'] is None and facts['fact-far']['citation_anchors'] == [None]
    assert facts['fact-far']['shadowed_by'] == ['fact-other'] and facts['fact-far']['backlinks'] == [dict(rel='contradicts', source='fact-other')]
    assert body['scope_recorded'] is True and body['scope_counts'] == dict(world=2, game=2, unrecorded=0)
    assert body['tag_counts'] == [dict(tag='water', count=2), dict(tag='site', count=1)] and body['tag_counts_omitted'] == 0
    assert body['statement_kind_counts'] == dict(state=1, observation=3)
    assert client.get(f'{route}?version=initial').json()['articles'] == []
    assert client.get(f'{route}?version=v2').json()['facts']['total'] == 2
    for unknown in ('v99', 'v03', '../v1', 'covered-prefix', 'v' * 600):
        response = client.get(route, params=dict(version=unknown))
        assert response.status_code == 404 and response.json()['error'] == 'unknown_version', unknown[:20]


def test_delivered_knowledge_searches_scopes_and_pages(mission):
    client, _, root, _ = mission
    route = '/api/view/run/mission/delivered-knowledge'
    found = client.get(f'{route}?q=STREAM').json()
    assert [a['id'] for a in found['articles']] == ['article-a'] and [f['id'] for f in found['facts']['items']] == ['fact-a']
    assert client.get(f'{route}?q=nothing-like-it').json()['articles'] == []
    first = client.get(f'{route}?limit=3').json()['facts']
    rest = client.get(f"{route}?limit=3&after={first['next']}").json()['facts']
    assert (len(first['items']), first['next'], first['total'], len(rest['items']), rest['next']) == (3, 3, 4, 1, None)
    for bad, code in (('scope=belief', 'bad_scope'), ('limit=0', 'bad_limit'), ('after=x', 'bad_after'), ('q=' + 'x' * 201, 'bad_q')):
        response = client.get(f'{route}?{bad}')
        assert response.status_code == 400 and response.json()['error'] == code, bad
    # Tags and statement kinds are searched too.
    assert [f['id'] for f in client.get(f'{route}?q=site').json()['facts']['items']] == ['fact-a']
    assert [f['id'] for f in client.get(f'{route}?q=state').json()['facts']['items']] == ['fact-b']
    assert [f['id'] for f in client.get(f'{route}?q=wait-state').json()['facts']['items']] == ['fact-b']
    # The files here are what the player itself accepts.
    for path in (*(root / 'delivered').glob('v[0-9].json'), root / 'delivered' / 'v10.json', root.parent / 'delivered-knowledge.json'):
        assert Knowledge(path).value['schema'] == 'delivered-knowledge/4'
    # The scope filter uses the delivered classes: world-bound (label withheld) or bound to no world.
    for scope, ids in (('world', ['fact-b', 'fact-other']), ('game', ['fact-a', 'fact-far'])):
        listed = client.get(f'{route}?scope={scope}').json()
        assert [f['id'] for f in listed['facts']['items']] == ids and listed['facts']['total'] == 2
        assert listed['scope_counts'] == dict(world=2, game=2, unrecorded=0) and {f['scope'] for f in listed['facts']['items']} == {scope}
    # A file that carries a world or lineage label anyway does not follow the format; the label is still never shown.
    invented = [fact_record('f0', [f'{SESSION}-1'], scope=dict(game='cdda', world='farm-north', lineage='farm-north-a01', ruleset='standard'),
        branch_relation='same'), fact_record('f1', [f'{SESSION}-1'], scope='game')]
    document = delivered_document('v11', [], invented)
    with pytest.raises(PlayerError):
        Knowledge.from_dict(document)
    (root / 'delivered' / 'v11.json').write_text(json.dumps(document))
    response = client.get(route)
    body = response.json()
    assert body['selected_version'] == 'v11' and 'farm-north' not in response.text
    rows = body['facts']['items']
    assert (rows[0]['scope'], rows[0]['scope_axes']) == ('world', dict(ruleset='standard')) and (rows[1]['scope'], rows[1]['scope_axes']) == (None, {})
    assert body['scope_counts'] == dict(world=1, game=0, unrecorded=1) and client.get(f'{route}?scope=world').json()['facts']['total'] == 1
    assert [f['id'] for f in client.get(f'{route}?scope=unrecorded').json()['facts']['items']] == ['f1']     # the counted ones are listed


@pytest.mark.parametrize('broken', ['corrupt', 'missing'])
def test_a_delivered_anchor_is_only_a_frame_the_frame_route_serves(mission, broken):
    """A cited frame of this run whose PNG is missing or not the recorded one is no anchor: the latest verified one is,
    for the fact and for an article citing it, so the browser never links to a frame the frame route refuses."""
    client, directory, _, _ = mission
    route = '/api/view/run/mission/delivered-knowledge'
    here = lambda n: dict(seq=n, source_id=f'{SESSION}-{n}')
    png = directory / 'sources' / f'{SESSION}-3.png'
    assert png.is_file() and client.get(f'/api/view/run/mission/frame/{SESSION}-3').status_code == 200
    if broken == 'corrupt':
        png.write_bytes(b'tampered')
    else:
        png.unlink()
    assert client.get(f'/api/view/run/mission/frame/{SESSION}-3').status_code == (409 if broken == 'corrupt' else 404)
    facts = {f['id']: f for f in client.get(route).json()['facts']['items']}
    b = facts['fact-b']     # cites SESSION-1 and SESSION-3; the newer one fails verification
    assert b['citation_source_ids'] == [f'{SESSION}-1', f'{SESSION}-3']
    assert b['citation_anchors'] == [here(1), None] and b['frame_anchor'] == here(1)
    assert facts['fact-a']['frame_anchor'] == here(2)
    # An article's anchor is the latest verified frame among those its cited facts cite.
    (directory / 'sources' / f'{SESSION}-2.png').unlink()
    article = client.get(route).json()['articles'][0]
    assert article['id'] == 'article-a' and article['anchor'] is None
    cites_b = article_record('article-b', ['fact-a', 'fact-b'])
    root = directory / 'curator-runner' / 'delivered'
    (root / 'v11.json').write_text(json.dumps(delivered_document('v11', [cites_b], mission_version(10)['facts'])))
    assert client.get(route).json()['articles'][0]['anchor'] == here(1)


def test_delivered_knowledge_shows_graph_flags_and_kinds_and_never_reads_private_files(mission, monkeypatch):
    """A current export with contested readings, a shadowing scope, status flags, and typed links."""
    import io
    import os
    client, directory, root, _ = mission
    world = WORLD_BOUND | dict(scope=dict(game='cdda', world=None, ruleset='standard'),
                              lifecycle_state='contested', branch_relation='unknown', unverified_branch=True)
    tags = ['camp', 'fire', 'water']
    articles, facts = published([
        article_record('camp-water', ['boil-water', 'tank-full'], tags=tags, **world, needs_review=True,
                       stale_citations=['old-water-fact'], links=[dict(rel='see_also', target='fire-rule')]),
    ], [
        fact_record('boil-water', [f'{SESSION}-2'], tags=tags, when='needs a lit heat source',
                    links=[dict(rel='depends_on', target='fire-rule')]),
        fact_record('fire-rule', [f'{OTHER_SESSION}-1'], tags=tags, shadowed_by=['fire-rule-standard']),
        fact_record('fire-rule-standard', [f'{OTHER_SESSION}-1'], scope=dict(game='cdda', ruleset='standard'),
                    links=[dict(rel='contradicts', target='fire-rule')]),
        fact_record('fire-rule-camp', [f'{OTHER_SESSION}-1'], **WORLD_BOUND, statement_kind='inference'),
        fact_record('tank-full', [f'{SESSION}-3'], tags=tags, **world, needs_review=True, stale_citations=['ended-fire'],
                    statement_kind='state', state_key='tank-level', contradicted_by=['tank-empty'],
                    links=[dict(rel='contradicts', target='tank-empty')]),
        fact_record('tank-empty', [f'{OTHER_SESSION}-1'], **world, statement_kind='state', state_key='tank-level',
                    contradicted_by=['tank-full'], links=[dict(rel='contradicts', target='tank-full')]),
    ])
    document = delivered_document('v12', articles, facts)
    document['history'] = dict(replaced={
        'old-water-fact': dict(reason='restated', by=['boil-water']),
        'tank-reading': dict(reason='changed', by=['tank-full']),
    }, ended=['ended-fire'], retracted=[])
    Knowledge.from_dict(document)
    (root / 'delivered' / 'v12.json').write_text(json.dumps(document))
    # The private export beside the delivered one names the world, the lineage and the alias map; none of it is read.
    labels = dict(world='farm-north', lineage='farm-north-a01', session_aliases=dict(s01=SESSION, s04=SESSION))
    for place in (directory, directory / 'actors' / '001'):
        (place / 'private').mkdir(exist_ok=True)
        (place / 'private' / 'knowledge-full.json').write_text(json.dumps(dict(document, selection=labels)))
    opened = []
    real_open, real_io = os.open, io.open
    monkeypatch.setattr(os, 'open', lambda path, *a, **k: (opened.append(os.fspath(path)), real_open(path, *a, **k))[1])
    monkeypatch.setattr(io, 'open', lambda path, *a, **k: (opened.append(os.fspath(path) if not isinstance(path, int) else ''), real_io(path, *a, **k))[1])
    response = client.get('/api/view/run/mission/delivered-knowledge?version=v12')
    monkeypatch.undo()
    def private(name: str) -> bool:     # a component opened under a directory descriptor, or a path inside the run
        path = Path(name)
        inside = path.relative_to(directory) if path.is_absolute() and path.is_relative_to(directory) else None if path.is_absolute() else path
        return inside is not None and 'private' in inside.parts
    assert response.status_code == 200 and 'delivered' in opened and not any(private(p) for p in opened)
    assert 'farm-north' not in response.text and 'session_aliases' not in response.text
    body = response.json()
    assert body['schema'] == 'spectator-view/4' and body['scope_counts'] == dict(world=3, game=3, unrecorded=0)
    assert body['statement_kind_counts'] == dict(state=2, observation=3, inference=1)
    assert body['history']['replaced']['tank-reading'] == dict(reason='changed', by=['tank-full'], by_omitted=0)
    assert body['tag_counts'] == [dict(tag='camp', count=4), dict(tag='fire', count=4), dict(tag='water', count=4)]
    article = body['articles'][0]
    assert (article['scope'], article['scope_axes'], article['lifecycle_state'], article['branch_relation']) == ('world', dict(ruleset='standard'), 'contested', 'unknown')
    assert (article['needs_review'], article['unverified_branch'], article['stale_citations']) == (True, True, ['old-water-fact'])
    assert 'condition_unverified' not in article
    assert article['links'] == [dict(rel='see_also', target='fire-rule')]
    assert article['anchor'] == dict(seq=3, source_id=f'{SESSION}-3')     # the latest of its facts' frames of this run
    facts = {f['id']: f for f in body['facts']['items']}
    tank = facts['tank-full']
    assert (tank['lifecycle_state'], tank['contradicted_by'], tank['needs_review'], tank['stale_citations']) == ('contested', ['tank-empty'], True, ['ended-fire'])
    assert tank['links'] == [dict(rel='contradicts', target='tank-empty')] and tank['backlinks'] == [dict(rel='contradicts', source='tank-empty')]
    assert tank['frame_anchor'] == dict(seq=3, source_id=f'{SESSION}-3') and facts['tank-empty']['frame_anchor'] is None
    rule = facts['fire-rule']
    assert rule['shadowed_by'] == ['fire-rule-standard'] and rule['scope'] == 'game' and facts['fire-rule-standard']['scope_axes'] == dict(ruleset='standard')
    assert {b['source'] for b in rule['backlinks']} == {'boil-water', 'camp-water', 'fire-rule-standard'}
    assert facts['boil-water']['when'] == 'needs a lit heat source'
    assert facts['fire-rule-camp']['scope'] == 'world' and facts['fire-rule-camp']['statement_kind'] == 'inference'


def test_an_unreadable_delivered_version_is_listed_as_such_and_never_shown(mission):
    client, directory, root, _ = mission
    route = '/api/view/run/mission/delivered-knowledge'
    for text, status in (('{"schema":"delivered-knowledge/4"', 'malformed'), (json.dumps(dict(schema='delivered-knowledge/2', articles=[], facts=[])), 'unsupported'),
                         ('', 'empty'), (json.dumps(dict(schema='delivered-knowledge/4', articles={}, facts=[], frame_clocks={})), 'unsupported')):
        (root / 'delivered' / 'v12.json').write_text(text)
        body = client.get(route).json()
        row = next(v for v in body['versions'] if v['version'] == 'v12')
        assert row['status'] == status and row['articles_count'] is None and row['facts_count'] is None
        assert body['selected_version'] == 'v10'     # the latest that can be read
        refused = client.get(f'{route}?version=v12')
        assert refused.status_code == 409 and refused.json()['error'] == 'unsupported_knowledge'
    for path in [*(root / 'delivered').iterdir(), directory / 'delivered-knowledge.json']:
        path.unlink()
    empty = client.get(route).json()
    assert empty['source_status'] == 'unavailable' and empty['versions'] == [] and empty['selected_version'] is None and empty['facts']['items'] == []
    assert client.get(f'{route}?version=initial').status_code == 404


def test_odd_values_in_a_trace_or_a_version_never_break_the_new_routes(mission):
    client, directory, root, _ = mission
    trace = directory / 'actors' / '001' / 'host.jsonl'
    lines = trace.read_text().splitlines()
    odd = [dict(type='context-cut', outcome=['cut'], triggers='x', tokens_before=-1, tokens_after=1.5, request_id=7),
        dict(type='response-complete', request_id='request-9', reported_cost_usd='NaN', reported_provider=dict(a=1), usage_available=True, usage=dict(input='x')),
        dict(type='response-complete', request_id='request-10', reported_cost_usd='1e400', reported_provider='y' * 600, usage=[]),
        dict(type='knowledge-delivery', kind='update', outcome='delivered', text='one line', version=['v'], article_ids=7),
        dict(type='tool-start', request_id='request-9', tool_call_id='t', tool='player_hint', arguments=dict(intent=5, actions='no')),
        dict(type='tool-result', request_id='request-9', tool_call_id='t', result=dict(structuredContent=dict(receipts=[1, dict(disposition=[])], source=3, reason={})))]
    trace.write_text('\n'.join([*lines[:-1], *(json.dumps(e) for e in odd)]) + '\n')
    (root / 'delivered' / 'v11.json').write_text(json.dumps(delivered_document('v11', [7, dict(id=['x'], body=[3, dict(text=1, facts=[1])], links='x', last_confirmed=[],
            tags=[1, ['t']], scope=dict(world='farm', game=[1]), backlinks=[dict(rel=1, source={})], stale_citations='s')],
        [None, dict(id=1, text=['t'], seen=dict(session=['s01'], actor={}, step=True), scope=['world'], when=dict(note=[], requires=[1]),
            citation_source_ids=[f'{SESSION}-1', 2, None], links=[None, dict(rel='see_also')], statement_kind={}, tags='water'),
         dict(id='x', citation_source_ids='x', scope={1: 'a', 'axis': 'x' * 100})], coverage='x')))
    for route in ('summary', 'feed', 'telemetry', 'delivered-knowledge', 'delivered-knowledge?q=x'):
        response = client.get(f'/api/view/run/mission/{route}')
        assert response.status_code == 200, (route, response.text[:200])
    assert client.get('/api/view/run/mission/summary').json()['host_telemetry']['reported_cost_usd'] == '0.0082000005'


def test_the_new_routes_leave_the_run_untouched_and_name_no_path(mission, tmp_path):
    client, directory, _, _ = mission
    before = snapshot(directory)
    for route in ('summary', 'feed', 'telemetry', 'delivered-knowledge', 'delivered-knowledge?version=v2'):
        response = client.get(f'/api/view/run/mission/{route}')
        assert response.status_code == 200 and (route == 'summary' or str(tmp_path) not in response.text), route
        assert client.post(f'/api/view/run/mission/{route}').status_code == 405
    assert snapshot(directory) == before


def test_a_sealed_pre_world_session_keeps_its_frozen_snapshot_readable(tmp_path):
    """S-MIGRATION, closed archive reads (#838): a sealed `campaign-run/10` session of the archive index carries
    `player-host-inputs/3` and `delivered-knowledge/1`. The viewer reads those versions for it and for no current run."""
    session = 'd16ea238c2794897a7839549df297a69'
    directory = tmp_path/'runs'/'sealed'
    run = Run(directory, session=session)
    actor = run.actor()
    run.request(actor)
    run.finish()
    (directory/'manifest.json').write_text(json.dumps(dict(run.manifest, schema='campaign-run/10')))
    actor_dir = next((directory/'actors').iterdir())
    path = actor_dir/'delivered-knowledge.json'
    path.write_text(json.dumps(dict(schema='delivered-knowledge/1', version='v7', coverage=None, articles=[],
        facts=[dict(id='fact-a', text='A fact')])))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (actor_dir/'frozen.json').write_text(json.dumps(dict(schema='player-host-inputs/3', session=session, actor_id=actor,
        files={'delivered-knowledge.json': digest})))
    evaluate(directory, FakeBinding(), tmp_path/'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path/'root', (tmp_path/'runs',), data_dir=data_directory(tmp_path))))
    url = f'/api/view/run/{session}/knowledge'
    sealed = client.get(url, params=dict(actor=actor)).json()
    assert sealed['snapshot_status'] == 'verified' and sealed['snapshot']['version'] == 'v7'
    assert [item['id'] for item in sealed['snapshot']['items']] == ['fact-a']
    # The current versions are not this sealed session's.
    (actor_dir/'frozen.json').write_text(json.dumps(dict(schema='player-host-inputs/5', session=session, actor_id=actor,
        knowledge_updates=None, files={'delivered-knowledge.json': digest})))
    assert client.get(url, params=dict(actor=actor)).json()['snapshot_status'] == 'hash_unavailable'


@pytest.mark.parametrize('session', [
    ARCHIVED_SESSIONS['campaign-run/12'],
    '7a28b7bea730dce80c4ea14cbb16e421',  # indexed #896 seven-day-896-b-admission-10 campaign-run/12 + player-host/11
])
@pytest.mark.parametrize('frozen_schema, knowledge_schema', [('player-host-inputs/5', 'delivered-knowledge/2'),
    ('player-host-inputs/3', 'delivered-knowledge/1'), ('player-host-inputs/5', 'delivered-knowledge/4'), (None, None)])
def test_sealed_campaign_run_12_snapshot_hash_is_unavailable(tmp_path, session, frozen_schema, knowledge_schema):
    """S-MIGRATION, closed archive reads: a sealed `#889` or `#896` `campaign-run/12` session carries
    `delivered-knowledge/2`, which nothing reads now. Its snapshot is `hash_unavailable`, never verified as the
    archived `/1` nor as the current `/4`, and its files are not read: an actor without them (`None`) is
    `hash_unavailable` too."""
    directory = tmp_path/'runs'/'sealed-12'
    run = Run(directory, session=session)
    actor = run.actor()
    versions = archive_sessions()[session].combination.versions
    run.host[actor][0].update(schema=versions['host'], telemetry_version=versions['host_telemetry'])
    request = run.request(actor)
    run.call(actor, 'player_knowledge_query', dict(query='fact'), dict(schema='player-knowledge/2', records=[dict(id='fact-a')]))
    run.host[actor].append(run.event(actor, 'context-cut', BASE + 1, request_id=request, outcome='cut', removed_turns=3))
    run.finish()
    (directory/'manifest.json').write_text(json.dumps(dict({k: v for k, v in run.manifest.items() if k != 'context'}, schema='campaign-run/12')))
    actor_dir = next((directory/'actors').iterdir())
    path = actor_dir/'delivered-knowledge.json'
    if knowledge_schema is not None:
        path.write_text(json.dumps(dict(schema=knowledge_schema, version='v7', coverage=None, articles=[], facts=[dict(id='fact-a', text='A fact')])))
        (actor_dir/'frozen.json').write_text(json.dumps(dict(schema=frozen_schema, session=session, actor_id=actor, knowledge_updates=None,
            files={'delivered-knowledge.json': hashlib.sha256(path.read_bytes()).hexdigest()})))
    evaluate(directory, FakeBinding(), tmp_path/'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path/'root', (tmp_path/'runs',), data_dir=data_directory(tmp_path))))
    url = f'/api/view/run/{session}'
    value = client.get(f'{url}/knowledge', params=dict(actor=actor)).json()
    assert value['schema'] == 'spectator-view/4' and value['snapshot_status'] == 'hash_unavailable' and value['snapshot'] is None
    call = value['calls'][0]
    assert call['returned_ids'] == ['fact-a'] and call['returned_hits'] == [] and call['returned_hits_omitted'] == 0
    host = client.get(f'{url}/summary').json()['host_telemetry']
    assert host['context_cuts']['applied'] == 1 and host['context_cuts']['by_result'] == dict(target=0, best_effort=0, rescue=0)
    assert host['spend_reserve_reached'] == dict(count=0, latest=None)
    notices = dict(count=0, by_kind={'context-capacity': 0, 'host-timeout': 0, 'spend-limit': 0})
    assert host['tail_notices'] == notices
    feed_cut = next(row for row in client.get(f'{url}/feed').json()['items'] if row['entry_kind'] == 'context_cut')
    series = client.get(f'{url}/telemetry').json()
    assert series['spend_reserve_reached'] == [] and series['tail_notices'] == notices
    for cut in (host['context_cuts']['latest'], feed_cut, series['cuts'][0]):
        assert cut['removed_turns'] == 3
        assert all(cut[field] is None for field in ('cut_result', 'cumulative_removed_turns', 'briefing_tokens', 'source_ids_count'))


def frozen_reader(tmp_path: Path, articles=(), facts=(), coverage=COVERAGE, *, session=SESSION, document=None, archived=False):
    """A current run whose actor's verified frozen snapshot is a `delivered-knowledge/4` file of `articles` and `facts`,
    also exported as its `v1`, beside another catalog run whose first frame (`OTHER_SESSION-1`) they may cite."""
    runs = tmp_path/'runs'
    other = Run(runs/'other', session=OTHER_SESSION)
    other.step(other.actor(), 'observe', [], F('in_play', 3600))
    other.finish()
    run = Run(runs/'reader', session=session)
    actor = run.actor()
    if archived:
        run.host[actor][0].update(schema='player-host/12', telemetry_version=12)
    run.request(actor)
    run.finish()
    if archived:
        (run.directory/'manifest.json').write_text(json.dumps(dict(run.manifest, schema='campaign-run/13')))
    actor_dir = runs/'reader'/'actors'/'001'
    path = actor_dir/'delivered-knowledge.json'
    path.write_text(json.dumps(document if document is not None else delivered_document('v1', articles, facts, coverage=coverage)))
    (actor_dir/'frozen.json').write_text(json.dumps(dict(schema='player-host-inputs/4' if archived else 'player-host-inputs/5', session=session, actor_id=actor, knowledge_updates=None,
        files={'delivered-knowledge.json': hashlib.sha256(path.read_bytes()).hexdigest()})))
    exported = runs/'reader'/'curator-runner'/'delivered'
    exported.mkdir(parents=True)
    (exported/'v1.json').write_bytes(path.read_bytes())
    for directory in (runs/'other', runs/'reader'):
        evaluate(directory, FakeBinding(), tmp_path/'root', created_wall=1.0)
    client = TestClient(create_app(Catalog(tmp_path/'root', (runs,), data_dir=data_directory(tmp_path))))
    return client, actor, actor_dir


@pytest.mark.parametrize('session, archived', [*((session, True) for session in MULTI_DAY_SESSIONS),
                                               (SESSION, False), (next(iter(MULTI_DAY_SESSIONS)), False)])
def test_delivered_v3_reads_are_limited_to_the_approved_archive(tmp_path, session, archived):
    fact = dict(id='old-fact', claim_kind='instance_state', evidence_basis='observed',
                condition_unverified=True, when=dict(note='while open', requires=dict(phase='late')),
                seen=position(2), citation_source_ids=[f'{OTHER_SESSION}-1'])
    document = dict(schema='delivered-knowledge/3', version='v1', coverage=COVERAGE, articles=[], facts=[fact])
    client, actor, actor_dir = frozen_reader(tmp_path, session=session, document=document, archived=archived)
    browse = f'/api/view/run/{session}/delivered-knowledge'
    recorded = f'/api/view/run/{session}/knowledge'
    initial_files = {path: path.read_bytes() for path in (
        actor_dir/'frozen.json', actor_dir/'delivered-knowledge.json',
        actor_dir.parents[1]/'curator-runner'/'delivered'/'v1.json')}
    listing = client.get(browse).json()
    snapshot = client.get(recorded, params=dict(actor=actor))
    if not archived:
        assert listing['versions'][0]['status'] == 'unsupported'
        assert client.get(browse, params=dict(version='v1')).json()['error'] == 'unsupported_knowledge'
        assert snapshot.status_code == 409 and snapshot.json()['error'] == 'unsupported_knowledge'
    else:
        assert listing['versions'][0]['status'] == 'available' and snapshot.status_code == 200
        assert listing['claim_kind_counts'] == {'instance_state': 1}
        for row in (listing['facts']['items'][0], snapshot.json()['snapshot']['items'][0]):
            for field in ('claim_kind', 'evidence_basis', 'condition_unverified', 'when'):
                assert row[field] == fact[field]
        assert client.post(browse).status_code == 405 and client.post(recorded).status_code == 405
    assert all(path.read_bytes() == original for path, original in initial_files.items())


def test_a_current_snapshot_anchors_only_cited_frames_and_an_article_through_its_facts(tmp_path):
    """A current `/4` entry is anchored only by `citation_source_ids`: a stray `source_ids` field or a position's
    `source_id` is no citation. An article is anchored by the frames of the facts its body cites, looked up in the whole
    file, whether it is selected by `entry` or paged apart from those facts."""
    cited = f'{OTHER_SESSION}-1'
    stray = dict(source_ids=[cited], seen=dict(position(1), source_id=cited))
    articles, facts = published([article_record('article', ['fact-cited', 'fact-stray'], last_confirmed=dict(position(1), source_id=cited))],
        [fact_record('fact-stray', [], **stray), *(fact_record(f'fact-{n}', []) for n in range(3)), fact_record('fact-cited', [cited])])
    client, actor, _ = frozen_reader(tmp_path, articles, facts)
    url = f'/api/view/run/{SESSION}/knowledge'
    frame = [dict(run='other', source_id=cited, available=True, reason=None)]
    loose = client.get(url, params=dict(actor=actor, entry='fact-stray')).json()['snapshot']['items'][0]
    assert (loose['citation_source_ids'], loose['source_ids'], loose['anchors']) == ([], [], [])
    for params in (dict(entry='article'), dict(limit=1), dict(entry='article', limit=1)):
        page = client.get(url, params=dict(actor=actor, **params)).json()['snapshot']
        article = page['items'][0]
        assert len(page['items']) == 1 and article['id'] == 'article' and article['citation_source_ids'] == [], params
        assert article['anchors'] == frame and article['anchors_omitted'] == 0, params
    assert client.get(url, params=dict(actor=actor, entry='fact-cited')).json()['snapshot']['items'][0]['anchors'] == frame


def test_a_label_bearing_session_or_citation_is_never_served(tmp_path):
    """Blinding: a `/4` position or coverage stamp whose session is no alias is withheld, and a citation that is no frame
    source ID is omitted and counted, in both the frozen snapshot and the delivered-knowledge browser."""
    label = 'world-secret-admission'
    articles, facts = published([article_record('article', ['fact'], last_confirmed=position(2, label))],
        [fact_record('fact', [f'{label}-1', f'{SESSION}-1', 'x' * 32 + '-1'], seen=position(1, label)),
         fact_record('fact-alias', [], seen=position(1, 's02'))])
    client, actor, _ = frozen_reader(tmp_path, articles, facts, coverage=dict(COVERAGE, session=label))
    snapshot = client.get(f'/api/view/run/{SESSION}/knowledge', params=dict(actor=actor))
    browser = client.get('/api/view/run/reader/delivered-knowledge')
    for response in (snapshot, browser):
        assert response.status_code == 200 and label not in response.text
    shown = snapshot.json()['snapshot']
    assert shown['coverage']['session'] is None and shown['coverage']['last_step'] == 2
    article, fact, alias = shown['items']
    assert article['last_confirmed']['session'] is None and article['last_confirmed']['step'] == 2
    assert fact['seen']['session'] is None and alias['seen']['session'] == 's02'
    assert (fact['citation_source_ids'], fact['citation_source_ids_omitted']) == ([f'{SESSION}-1'], 2)
    listed = browser.json()
    assert listed['coverage']['session'] is None and listed['versions'][-1]['coverage']['session'] is None
    assert listed['articles'][0]['last_confirmed']['session'] is None
    rows = {f['id']: f for f in listed['facts']['items']}
    assert rows['fact']['seen'] == dict(position(1, None), order_omitted=0, order_omitted_characters={}) and rows['fact-alias']['seen']['session'] == 's02'
    assert (rows['fact']['citation_source_ids'], rows['fact']['citation_source_ids_omitted']) == ([f'{SESSION}-1'], 2)


@pytest.mark.parametrize('name, status', [('delivered-knowledge.json', 'unavailable'), ('frozen.json', 'hash_unavailable')])
def test_a_symlinked_frozen_snapshot_file_is_never_followed(tmp_path, name, status):
    """The frozen snapshot's files are read once each from the run package, never through a symlink, even to their
    own bytes."""
    client, actor, actor_dir = frozen_reader(tmp_path, *published([], [fact_record('fact', [])]))
    url = f'/api/view/run/{SESSION}/knowledge'
    assert client.get(url, params=dict(actor=actor)).json()['snapshot_status'] == 'verified'
    relinked(actor_dir/name, tmp_path/name)
    value = client.get(url, params=dict(actor=actor)).json()
    assert (value['snapshot_status'], value['snapshot']) == (status, None)


def test_context_and_knowledge_routes_reject_symlinked_host_trace(mission, tmp_path):
    client, directory, _, actor = mission
    outside = tmp_path / 'outside-host.jsonl'
    trace = directory / 'actors' / '001' / 'host.jsonl'
    outside.write_bytes(trace.read_bytes())
    trace.unlink()
    trace.symlink_to(outside)
    ctx_resp = client.get('/api/view/run/mission/context/request-1')
    assert ctx_resp.status_code == 404 and ctx_resp.json()['error'] == 'host_unavailable'
    kb_resp = client.get(f'/api/view/run/mission/knowledge?actor={actor}')
    assert kb_resp.status_code == 404 and kb_resp.json()['error'] == 'host_unavailable'


def test_malformed_only_curator_ledger_is_unavailable_not_zero(mission):
    import shutil
    client, directory, _, _ = mission
    sessions = directory / 'curator-runner' / 'sessions' / 'admission-a'
    for existing in list(sessions.iterdir()):
        shutil.rmtree(existing)
    bad = sessions / '001-1-2-bad'
    bad.mkdir()
    (bad / 'proxy-ledger.jsonl').write_text('{not valid json\n')
    cs = client.get('/api/view/run/mission/summary').json()['curator_spend']
    assert cs is not None and cs['spent_usd'] is None and cs['unsettled_requests'] == 1 and cs['spend_complete'] is False


def test_settled_actor_with_unpriced_counter_and_no_spend_marks_incomplete(mission):
    client, directory, _, _ = mission
    first_start = json.loads((directory / 'actors' / '001' / 'host.jsonl').read_text().splitlines()[0])
    second = directory / 'actors' / '002'
    second.mkdir()
    (second / 'host.jsonl').write_text('\n'.join([
        json.dumps(dict(first_start, actor_id='actor-2', wall_time=iso(BASE + 1), monotonic_ms=10.0)),
        json.dumps(dict(type='settled', wall_time=iso(BASE + 2), monotonic_ms=20.0, ok=True, spent_usd=None,
            player_requests=1, recall_requests=0, unpriced_requests=1, unpriced_recall_requests=0)),
    ]) + '\n')
    ht = client.get('/api/view/run/mission/summary').json()['host_telemetry']
    assert ht is not None and ht['spend_complete'] is False and ht['unpriced_requests'] == 1


def test_latest_provider_uses_chronologically_last_response_even_if_unlabelled(mission):
    client, directory, _, _ = mission
    trace = directory / 'actors' / '001' / 'host.jsonl'
    lines = trace.read_text().splitlines()
    extra = [
        json.dumps(dict(type='request-start', wall_time=iso(BASE + 90), monotonic_ms=9e6, request_id='request-99', logical_request_id='request-99')),
        json.dumps(dict(type='response-complete', wall_time=iso(BASE + 91), monotonic_ms=9.1e6, request_id='request-99',
            usage_available=True, usage=dict(input=10, output=5, cacheRead=0, cacheWrite=0), reported_provider=None, reported_cost_usd='0.001')),
    ]
    trace.write_text('\n'.join([*lines[:-1], *extra, lines[-1]]) + '\n')
    ht = client.get('/api/view/run/mission/summary').json()['host_telemetry']
    assert ht['latest_provider'] == 'unknown'


def test_delivered_knowledge_confirms_opening_briefing_delivery_for_initial(mission):
    client, directory, _, _ = mission
    initial_version = json.loads((directory / 'delivered-knowledge.json').read_text()).get('version')
    trace = directory / 'actors' / '001' / 'host.jsonl'
    lines = trace.read_text().splitlines()
    undelivered = json.dumps(dict(type='knowledge-delivery', kind='briefing', outcome='undelivered', version=initial_version,
        wall_time=iso(BASE + 0.4), monotonic_ms=4.0, receiving_player_request_id='request-1'))
    trace.write_text('\n'.join([lines[0], undelivered, *lines[1:]]) + '\n')
    # A row tagged undelivered is evidence of a missed placement, not of exposure.
    row = client.get('/api/view/run/mission/delivered-knowledge?version=initial').json()['version_chain'][0]
    assert row['delivery_status'] == 'exported_not_delivered' and row['deliveries'][0]['outcome'] == 'undelivered'
    briefing = json.dumps(dict(type='knowledge-delivery', kind='briefing', outcome='delivered', version=initial_version,
        wall_time=iso(BASE + 0.5), monotonic_ms=5.0, receiving_player_request_id='request-1'))
    trace.write_text('\n'.join([lines[0], briefing, *lines[1:]]) + '\n')
    body = client.get('/api/view/run/mission/delivered-knowledge?version=initial').json()
    assert body['delivery'] is not None and body['delivery']['kind'] == 'briefing' and body['delivery']['knowledge_version'] == initial_version


def test_placed_preserves_null_call_decision_separately_from_step_decision():
    from harness.viewer.feed import placed
    from harness.viewer.telemetry import Step
    step = Step(seq=5, operation_id='op-5', actor='a1', wall=100.0, decision=4, game_time=3600, mode='in_play', source_id='s-5')
    out = placed(step, None, 100.0, None)
    assert out['decision'] is None and out['step_decision'] == 4 and out['seq'] == 5


def test_split_mode_metrics_are_read_and_need_the_ui_boundary_validated(archive):
    from harness.viewer.views import validated
    client, _, _ = archive
    summary = client.get('/api/view/run/' + 'a' * 32 + '/summary').json()
    assert {m['name']: m['source'] for m in summary['metrics'] if m['name'].startswith('mode.')} == {
        'mode.out_of_play_share': 'read', 'mode.ui_share': 'read', 'mode.interruption_share': 'read'}
    passing = {'mode': {'pass': True}}
    assert validated('mode.out_of_play_share', passing) is True
    assert validated('mode.ui_share', passing) is False and validated('mode.interruption_share', passing) is False
    assert validated('mode.ui_share', passing | {'mode_ui': {'pass': True}}) is True


def test_a_version_2_ui_or_prompt_reading_is_checked_against_the_ui_boundary():
    from harness.viewer.views import reading_validation_key
    validation = {'mode': {'version': 1, 'pass': True}, 'mode_ui': {'version': 2, 'pass': None}}
    assert [reading_validation_key('mode', 2, value, validation) for value in ('ui', 'prompt', 'in_play', None)] == [
        'mode_ui', 'mode_ui', 'mode', 'mode']
    # A version-1 reading (a core-2 record) keeps the mode entry's held-out result.
    assert reading_validation_key('mode', 1, 'prompt', validation) == 'mode'
    assert reading_validation_key('game_time', 1, 3600, validation) == 'clock'
    tracked = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'evaluation' / 'reader-validation.json').read_text())
    assert tracked['mode_ui']['pass'] is None and tracked['mode']['pass'] is True


def test_a_symlinked_record_is_restamped_when_only_its_log_changes(tmp_path):
    from harness.evaluation.core.records import RecordWriter
    from harness.viewer.catalog import stamp
    from tests.test_evaluation_core import main_scenario
    record = evaluate(main_scenario(tmp_path / 'run'), FakeBinding(), tmp_path / 'evaluations', created_wall=1.0)
    link = tmp_path / 'links' / record.name
    link.parent.mkdir()
    link.symlink_to(record)
    writer = RecordWriter.open(record)
    try:
        writer.connection.execute('PRAGMA wal_autocheckpoint=0')
        before = stamp(link)
        writer.set_metadata(dict(last_seq=99))
        assert Path(f'{record}-wal').stat().st_size > 0
        assert stamp(link) != before and stamp(link) == stamp(record)
    finally:
        writer.close()


def test_blinded_markers_drop_source_id_archived_facts_keep_type_and_anchors_omitted_is_exact(mission):
    from harness.viewer.knowledge import entry as project_entry, marker
    client, directory, _, actor = mission
    catalog = client.app.state.catalog
    runs = catalog.runs()
    # 1. Blinded /4 marker drops stray `source_id` (raw label) while archived /1 marker keeps it.
    raw = dict(session='s01', actor='001', step=1, order=[1, '001', 1], source_id='raw-world-label-1')
    assert 'source_id' not in marker(raw, blinded=True)
    assert marker(raw, blinded=False)['source_id'] == 'raw-world-label-1'
    # 2. Archived /1 fact preserves `type`.
    v1_fact = dict(id='f-old', type='container', text='old fact', seen=raw, source_ids=[])
    assert project_entry(v1_fact, 'fact', catalog, runs, schema='delivered-knowledge/1')['type'] == 'container'
    # 3. >20 distinct valid citations report exact `anchors_omitted` for both facts and articles.
    cites = [f'{"a" * 32}-{i}' for i in range(1, 24)]
    fact_many = dict(id='f-many', statement_kind='observation', tags=[], text='many cites',
                     scope=dict(game='cdda'), branch_relation=None, lifecycle_state='active', stale_citations=[],
                     needs_review=False, unverified_branch=False, links=[], backlinks=[],
                     shadowed_by=[], contradicted_by=[], cited_by_articles=[], citation_source_ids=cites,
                     seen=dict(session='s01', actor='001', step=1, order=[1, '001', 1]))
    article_many = dict(id='art-many', revision='art-many@v1', title='Many', lead='Lead',
                        body=[dict(text='Claim', facts=['f-many'])], tags=[], scope=dict(game='cdda'),
                        branch_relation=None, lifecycle_state='active', stale_citations=[], needs_review=False,
                        unverified_branch=False, links=[], backlinks=[],
                        shadowed_by=[], contradicted_by=[],
                        last_confirmed=dict(session='s01', actor='001', step=1, order=[1, '001', 1]))
    pf = project_entry(fact_many, 'fact', catalog, runs)
    pa = project_entry(article_many, 'article', catalog, runs, facts={'f-many': fact_many})
    assert len(pf['anchors']) == 20 and pf['anchors_omitted'] == 3
    assert len(pa['anchors']) == 20 and pa['anchors_omitted'] == 3
    # 4. Update event coverage in a /13 run blinds raw session names.
    trace = directory / 'actors' / '001' / 'host.jsonl'
    lines = trace.read_text().splitlines()
    bad_update = json.dumps(dict(type='knowledge-delivery', kind='update', outcome='delivered', version='v9',
        previous_version='v1', wall_time=iso(BASE + 5), monotonic_ms=50.0, receiving_player_request_id='request-3',
        coverage=dict(schema='curator-coverage/2', session='raw-secret-world-run', actor='001', last_step=5,
                      source_id='raw-secret-source'),
        text='BEGIN FALLIBLE KNOWLEDGE UPDATE (v9)\n{"added":[],"updated":[],"removed":[]}\nEND FALLIBLE KNOWLEDGE UPDATE (v9)'))
    trace.write_text('\n'.join([*lines[:-1], bad_update, lines[-1]]) + '\n')
    resp = client.get(f'/api/view/run/mission/knowledge?actor={actor}')
    assert resp.status_code == 200
    assert 'raw-secret-world-run' not in resp.text and 'raw-secret-source' not in resp.text


def test_curator_viewer_accepts_hygiene_session_kind_with_grooming_sha256():
    import copy
    from harness.viewer.curator import session_projection

    sha = '0' * 64
    base_manifest = dict(
        schema='container-manifest/1', kind='curator-session', id='hygiene-1', owner_role='curator',
        inputs=dict(session_kind='hygiene', trace_sessions=[], window_frames=0, window={},
                    coverage=dict(schema='curator-coverage/2', session='s1', actor='001', last_step=5), drafts=[]),
        pinned=dict(knowledge_version='v1', trace_manifest_sha256=sha, brief_sha256=sha, grooming_sha256=sha),
        budgets=dict(wall_seconds=60, memory_bytes=1024, disk_bytes=1024, cap_usd='0.30'),
        provenance=dict(seconds=1.2, peak_memory_bytes=512, peak_disk_bytes=512),
        retention={},
        lifecycle=dict(state='sealed', started_wall=1.0, ended_wall=2.2, stopped=None, returncode=0,
                       survivors=[], errors=[], refused=[]),
    )
    record = dict(manifest=base_manifest, verdicts=[], drafts={}, published_after='v2')
    header, _, _ = session_projection(record)
    assert header['inputs']['session_kind'] == 'hygiene'
    assert header['pinned']['grooming_sha256'] == sha

    missing_groom_sha = copy.deepcopy(record)
    del missing_groom_sha['manifest']['pinned']['grooming_sha256']
    with pytest.raises(ValueError, match='incomplete prepared session'):
        session_projection(missing_groom_sha)


def test_v4_retired_routes_and_loopback_errors_have_the_view_schema(archive):
    client, _, _ = archive
    for path in ('frame/health', 'frame/curator-runner', 'frame/containers', 'frame/episodes',
                 'frame/curator-drafts', 'run/base1/programs', 'run/base1/memory'):
        response = client.get(f'/api/view/{path}')
        assert response.status_code == 404
        assert response.json()['schema'] == API and response.json()['error'] == 'not_found'
    for headers in ({'Host': 'external.example'}, {'Origin': 'https://external.example'}):
        response = client.get('/api/view/runs', headers=headers)
        assert response.status_code == 403
        assert response.json()['schema'] == API and response.json()['error'] == 'loopback_required'


def test_v4_catalog_counts_distinct_sessions_with_only_non_current_stores(archive):
    import shutil
    import sqlite3

    client, catalog, _ = archive
    by_run = {info.run: info for info in catalog.runs()}
    replaced = by_run['base2'].path
    old_copy = replaced.with_name('old.sqlite3')
    mixed_copy = by_run['base1'].path.with_name('obsolete.sqlite3')
    shutil.copyfile(replaced, old_copy)
    shutil.copyfile(by_run['base1'].path, mixed_copy)
    for path in (replaced, old_copy, mixed_copy):
        with sqlite3.connect(path) as db:
            db.execute("UPDATE metadata SET value=? WHERE key='core_version'", (str(CORE_VERSION - 1),))
    listing = client.get('/api/view/runs?limit=1').json()
    assert listing['skipped_non_current'] == catalog.skipped_non_current() == 1
    assert listing['total'] == 3 and listing['next'] == 1
    assert client.get('/api/view/run/base2/summary').status_code == 404
    with sqlite3.connect(replaced) as db:
        db.execute("UPDATE metadata SET value=? WHERE key='core_version'", (str(CORE_VERSION),))
    assert client.get('/api/view/runs').json()['skipped_non_current'] == 0


@pytest.mark.parametrize('part', ['sources', f'sources/{SESSION}-1.png'])
def test_v4_frame_refuses_symlinks_even_to_the_original_verified_bytes(mission, tmp_path, part):
    client, directory, _, _ = mission
    route = f'/api/view/run/mission/frame/{SESSION}-1'
    assert client.get(route).status_code == 200
    relinked(directory / part, tmp_path / 'outside-frame')
    refused = client.get(route)
    assert refused.status_code == 404
    assert refused.json()['schema'] == API and refused.json()['error'] == 'frame_unavailable'


def test_v4_summary_reports_evaluator_freshness_and_step_frontier(tmp_path):
    client, evaluator = live_client(tmp_path, 'clear')
    evaluator.status.update(running=True, passes=5, last_seq=1, last_pass_wall=BASE, error=None, finished=False,
                            internal='/Users/private/record.sqlite3')
    summary = client.get(f'/api/view/run/{SESSION}/summary')
    body = summary.json()
    assert body['evaluator_freshness'] == dict(running=True, passes=5, last_seq=1, last_pass_wall=BASE, error=None, finished=False)
    assert body['latest_step_seq'] == 2
    assert '/Users/private' not in summary.text


def test_v4_feed_joins_post_cut_briefing_by_actor_and_keeps_delivery_ids(tmp_path):
    from harness.viewer.telemetry import DELTA_BUCKETS

    run = Run(tmp_path / 'run')
    actor = run.actor()
    start = BASE + 10
    run.step(actor, 'observe', [], F('in_play', 3600))

    def delivery(owner, kind, version, data=None, event_type='knowledge-delivery', **fields):
        row = run.event(owner, event_type, start, version=version, **fields)
        row['kind'] = kind
        if data is not None:
            row['text'] = f'header\n{json.dumps(data)}\nfooter'
        run.host[owner].append(row)

    delivery(actor, 'briefing', 'v0', dict(leads=[dict(id='lead')], index=[dict(id='fact')]),
             outcome='delivered', receiving_player_request_id='request-1')
    run.host[actor].append(run.event(actor, 'context-cut', start, outcome='cut', request_id='request-2',
        uncovered_turns=2, briefing_tokens=320, source_ids_count=4))
    delivery(actor, 'briefing', 'v1', dict(leads=[], index=[dict(id='fact-2')]),
             outcome='delivered', receiving_player_request_id='request-2')
    delta = {key: [dict(state_key='water-state', title='water', reason='changed', text='x' * 500)] * 3 for key in DELTA_BUCKETS}
    delta['overflow'] = dict(omitted_count=2, read_ids=['water-state'])
    delivery(actor, 'update', 'v2', delta, outcome='delivered', receiving_player_request_id='request-3', previous_version='v1')
    delivery(actor, 'update', 'v3', empty=True, outcome='empty-suppressed')
    delivery(actor, 'update', 'v4', outcome='refused', reason='context-capacity')
    delivery(actor, 'update', 'v5', event_type='knowledge-undelivered', reason='actor-ended')
    next_actor = run.actor()
    delivery(next_actor, 'briefing', 'v6', dict(leads=[], index=[]), outcome='delivered', receiving_player_request_id='request-2')
    run.finish()
    root = tmp_path / 'evaluation'
    evaluate(run.directory, FakeBinding(), root, created_wall=0)
    client = TestClient(create_app(Catalog(root, (tmp_path,))))
    feed = client.get(f'/api/view/run/{SESSION}/feed').json()
    deliveries = {r['knowledge_version']: r for r in feed['items'] if r['entry_kind'] == 'knowledge_delivery'}
    cut = next(r for r in feed['items'] if r['entry_kind'] == 'context_cut')
    assert (cut['briefing']['delivery_id'], deliveries['v1']['joined_cut_id']) == (deliveries['v1']['id'], cut['id'])
    assert cut['briefing']['briefing_tokens'] == 320 and cut['briefing']['source_ids_count'] == 4
    assert cut['id'] != deliveries['v1']['id'] and deliveries['v6']['joined_cut_id'] is None
    assert [deliveries[f'v{i}']['delivery_kind'] for i in range(7)] == [
        'opening_briefing', 'post_cut_briefing', 'update', 'empty_suppressed', 'refused', 'undelivered', 'opening_briefing']
    assert (deliveries['v0']['leads_count'], deliveries['v0']['index_count']) == (1, 1)
    assert deliveries['v2']['delta_counts'] == dict.fromkeys(DELTA_BUCKETS, 3)
    assert len(deliveries['v2']['delta_preview']) == 12 and deliveries['v2']['overflow_omitted_count'] == 2
    assert deliveries['v2']['delta_preview'][0] == dict(bucket='corrections', state_key='water-state',
        title='water', reason='changed', text='x' * 256)
    summary = client.get(f'/api/view/run/{SESSION}/summary').json()['host_telemetry']
    assert summary['context_cuts']['uncovered_cuts'] == 1 and summary['context_cuts']['uncovered_turns_total'] == 2
    assert summary['knowledge_deliveries'] == dict(total=7, briefings=3, post_cut_briefings=1, updates=1,
        empty_suppressed=1, refused=1, undelivered=1, latest_version='v6')


def test_v4_coverage_wait_grows_under_one_trace_anchor_then_closes_at_cut(mission):
    client, directory, _, actor = mission
    trace = directory / 'actors' / '001' / 'host.jsonl'
    start = json.loads(trace.read_text().splitlines()[0])
    rows = [start]

    def add(kind, offset, **fields):
        rows.append(dict(type=kind, wall_time=iso(BASE + offset), monotonic_ms=10 + len(rows), **fields))

    def response(number, offset, tokens):
        add('response-complete', offset, request_id=f'request-{number}', usage_available=True,
            usage=dict(input=tokens, cacheRead=0, cacheWrite=0, output=1))

    def wait():
        trace.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        body = client.get('/api/view/run/mission/feed').json()
        return next(item for item in body['items'] if item['entry_kind'] == 'coverage_wait')

    add('context-cut', 5, request_id='request-1', outcome='held-back', reason='below-min-free',
        covered_through_operation_id='op-1', knowledge_version='v1', available_turns=3, min_free=5, tokens_before=100)
    response(1, 6, 90)
    first = wait()
    assert (first['active'], first['ended_by'], first['requests'], first['peak_tokens']) == (True, 'trace_end', 1, 100)
    assert first['restore_possible'] is True and first['duration_seconds'] == 1
    response(2, 9, 130)
    response(3, 12, 180)
    grown = wait()
    assert (grown['id'], grown['order']) == (first['id'], first['order'])
    assert (grown['end_request_id'], grown['requests'], grown['peak_tokens'], grown['duration_seconds']) == ('request-3', 3, 180, 7)
    add('context-cut', 15, request_id='request-4', outcome='cut', tokens_before=170)
    response(4, 17, 120)
    closed = wait()
    assert closed['id'] == first['id'] and closed['actor'] == actor
    assert (closed['active'], closed['ended_by'], closed['cut_request_id'], closed['restore_possible']) == (False, 'cut', 'request-4', False)
    assert (closed['requests'], closed['peak_tokens'], closed['duration_seconds']) == (4, 180, 10)
    [band] = client.get('/api/view/run/mission/telemetry').json()['coverage_waits']
    assert (band['id'], band['start_index'], band['end_index']) == (first['id'], 0, 3)
    summary = client.get('/api/view/run/mission/summary').json()['host_telemetry']['coverage_waits']
    assert (summary['count'], summary['active_count'], summary['total_requests'], summary['longest_seconds']) == (1, 0, 4, 10)
    add('context-cut', 20, request_id='request-5', outcome='held-back', reason='uncovered')
    add('context-cut', 21, request_id='request-6', outcome='held-back', reason='below-min-free',
        covered_through_operation_id='op-2')
    wait()
    bands = client.get('/api/view/run/mission/telemetry').json()['coverage_waits']
    assert [band['ended_by'] for band in bands] == ['cut', 'superseded', 'trace_end']
    assert len({band['id'] for band in bands}) == 3


def agenda_document(title, cut_count=0):
    return dict(schema='player-agenda-continuation/1', cut_count=cut_count,
        threads=[dict(id='water', title=title, status='active', notes='x' * 270, refs=['fact-water'] * 9)])


def test_v4_agenda_projects_events_and_rooted_continuation_files(mission):
    client, directory, _, actor = mission
    trace = directory / 'actors' / '001' / 'host.jsonl'
    original = trace.read_text()
    append = [
        dict(type='tool-start', request_id='request-4', tool_call_id='agenda-1', tool='player_agenda',
             arguments=dict(op='upsert')),
        dict(type='player-agenda', request_id='request-4', tool_call_id='agenda-1', op='upsert',
             cut_count=2, active_count=1, thread_count=1, agenda=agenda_document('Find water', 2)),
    ]
    trace.write_text(original + ''.join(json.dumps(dict(row, monotonic_ms=100000 + i, wall_time=iso(BASE + 60))) + '\n'
                                      for i, row in enumerate(append)))
    (directory / 'agenda.json').write_text(json.dumps(agenda_document('Initial')))
    summary = lambda: client.get('/api/view/run/mission/summary').json()['agenda']
    current = summary()
    assert current['initial']['threads'][0]['title'] == 'Initial'
    assert current['latest']['threads'][0]['title'] == 'Find water'
    assert (current['events_count'], current['tool_calls'], current['reconstructed'], current['final']) == (1, 1, True, None)
    assert len(current['latest']['threads'][0]['notes']) == 240 and len(current['latest']['threads'][0]['refs']) == 8
    entry = next(row for row in client.get('/api/view/run/mission/feed').json()['items'] if row['entry_kind'] == 'agenda_change')
    assert (entry['actor'], entry['op'], entry['tool_call_id'], entry['cut_count']) == (actor, 'upsert', 'agenda-1', 2)
    (directory / 'actors' / '001' / 'agenda-final.json').write_text(json.dumps(agenda_document('Actor final', 3)))
    assert summary()['final']['threads'][0]['title'] == 'Actor final'
    (directory / 'agenda-final.json').symlink_to(directory / 'agenda.json')
    assert summary()['final']['threads'][0]['title'] == 'Actor final'
    (directory / 'agenda-final.json').unlink()
    (directory / 'agenda-final.json').write_text(json.dumps(agenda_document('Run final', 4)))
    assert summary()['final']['threads'][0]['title'] == 'Run final' and summary()['reconstructed'] is False


def test_v4_service_tiers_and_top_costliest_use_the_unthinned_request_series(mission, monkeypatch):
    from harness.viewer import telemetry

    client, directory, _, actor = mission
    monkeypatch.setattr(telemetry, 'MAX_POINTS', 6)
    trace = directory / 'actors' / '001' / 'host.jsonl'
    start = json.loads(trace.read_text().splitlines()[0])
    second = directory / 'actors' / '002'
    second.mkdir()
    rows = [start]
    for i in range(10):
        wall = iso(BASE + 10 + i)
        key = f'request-{i + 1}'
        amount = '0.800000000000000001' if i == 1 else '0.8' if i == 4 else None
        usage = Run.usage(total=0.7 if i == 3 else 0.0001)
        rows.extend([dict(type='response-service-tier', monotonic_ms=10 + i * 2, wall_time=wall, request_id=key,
                          applied_service_tier='flex' if i < 5 else 'priority'),
                     dict(type='response-complete', monotonic_ms=11 + i * 2, wall_time=wall, request_id=key,
                          usage_available=True, usage=usage, reported_cost_usd=amount)])
    trace.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (second / 'host.jsonl').write_text(json.dumps(dict(start, actor_id='actor-two')) + '\n' +
        json.dumps(dict(rows[-1], request_id='request-1', wall_time=iso(BASE + 30))) + '\n')
    body = client.get('/api/view/run/mission/telemetry').json()
    assert len(body['requests']) <= 6 and 1 not in {row['index'] for row in body['requests']}
    assert [row['index'] for row in body['top_costliest'][:3]] == [1, 4, 3]
    assert body['top_costliest'][0]['reported_cost_usd'] == '0.800000000000000001'
    assert body['top_costliest'][0]['actor'] == actor and body['top_costliest'][0]['applied_service_tier'] == 'flex'
    assert body['service_tiers'] == dict(player=dict(flex=5, priority=5), latest_player_tier='priority')
    assert body['handoffs'][0]['actor'] == 'actor-two' and body['handoffs'][0]['index'] == 10
    summary = client.get('/api/view/run/mission/summary').json()
    assert summary['host_telemetry']['service_tiers'] == body['service_tiers']


def test_v4_delivered_chain_state_quality_and_kind_filter(mission):
    client, directory, root, _ = mission
    publications = [dict(schema='curator-runner-version/1', version=f'v{i}', baseline=i == 0, coverage=COVERAGE)
                    for i in (0, 1, 2, 4)]
    (root / 'versions.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in publications) + '{partial')
    (root / 'delivered' / 'v0.json').write_text(json.dumps(delivered_document('v0')))
    latest = json.loads((root / 'delivered' / 'v10.json').read_text())
    latest['history']['replaced']['previous-reading'] = dict(reason='changed', by=['fact-b'])
    latest['facts'][1].update(stale_citations=['previous-reading'], lifecycle_state='contested', needs_review=True,
                              unverified_branch=True)
    (root / 'delivered' / 'v10.json').write_text(json.dumps(latest))
    route = '/api/view/run/mission/delivered-knowledge'
    response = client.get(route, params=dict(kind='state'))
    body = response.json()
    assert response.status_code == 200 and len(response.content) <= MAX_BYTES
    assert body['facts']['total'] == 1 and body['facts']['limit'] == 100
    [group] = body['state_groups']
    assert group['state_key'] == 'wait-state' and group['count'] == 1 and group['facts'][0]['id'] == 'fact-b'
    assert group['replaced']['previous-reading']['by'] == ['fact-b']
    assert body['anchor_groups'] == [dict(anchor='landmark-state', anchor_display='Landmark', fact_count=1, state_keys=['wait-state'])]
    quality = body['quality']
    assert (quality['default_view'], quality['state_count'], quality['when_count'], quality['when_coverage']) == ('articles', 1, 1, 0.25)
    assert (quality['stale_count'], quality['contested_count'], quality['unverified_count'], quality['needs_review_count']) == (1, 1, 1, 1)
    versions = {row['version']: row for row in body['version_chain']}
    assert versions['v0']['baseline'] is True and versions['v0']['exported'] is True
    assert versions['v1']['published'] is True and versions['v1']['delivery_status'] == 'delivered'
    assert versions['v2']['delivery_status'] == 'delivered' and versions['v2']['deliveries'][0]['request_id'] == 'request-3'
    assert versions['v3']['delivery_status'] == 'refused' and versions['v3']['published'] is False
    assert versions['v4']['delivery_status'] == 'published_only' and versions['v4']['status'] == 'missing'
    assert versions['v10']['delivery_status'] == 'exported_not_delivered'
    delivery = client.get(route, params=dict(version='v2')).json()['delivery']
    assert delivery['delivery_kind'] == 'update' and delivery['delta_counts'] == dict(added=2, updated=1, removed=1)
    assert client.get(route, params=dict(kind='x' * (ID_LIMIT + 1))).json()['error'] == 'bad_kind'
    relinked(root / 'versions.jsonl', directory / 'outside-published')
    current = {r['version']: r for r in client.get(route).json()['version_chain']}
    assert 'v4' not in current and current['v2']['published'] is False


def test_v4_cross_admission_citations_and_source_read_share_cached_verification(tmp_path, monkeypatch):
    from harness.viewer import views

    cited = f'{OTHER_SESSION}-1'
    client, actor, actor_dir = frozen_reader(tmp_path, facts=[fact_record('fact-water', [cited])])
    trace = actor_dir / 'host.jsonl'
    lines = [json.loads(line) for line in trace.read_text().splitlines()]
    request = 'request-1'
    rows = [dict(type='tool-start', request_id=request, tool_call_id='source-read', tool='player_source',
                 arguments=dict(source_id=cited)),
            dict(type='tool-result', request_id=request, tool_call_id='source-read', tool='player_source',
                 result=dict(structuredContent=dict(schema='player-source-read/2', status='available', source_id=cited,
                     origin=dict(admission='s01', actor='001', step=1), clickable=False)))]
    insert_at = next(i for i, line in enumerate(lines) if line['type'] == 'response-complete') + 1
    lines[insert_at:insert_at] = rows
    trace.write_text(''.join(json.dumps(dict(row, monotonic_ms=i + 1, wall_time=iso(BASE + i))) + '\n'
                             for i, row in enumerate(lines)))
    counted = []
    original = views.read_rooted

    def tracked(run_dir, *parts):
        if parts == ('sources', f'{cited}.png'):
            counted.append((run_dir.name, parts))
        return original(run_dir, *parts)

    monkeypatch.setattr(views, 'read_rooted', tracked)
    expected = dict(run='other', session=OTHER_SESSION, seq=1, source_id=cited, available=True, reason=None)
    url = '/api/view/run/reader'
    for _ in range(2):
        [fact] = client.get(f'{url}/delivered-knowledge').json()['facts']['items']
        assert fact['frame_anchor'] == expected and fact['citation_anchors'] == [expected]
        [call] = client.get(f'{url}/knowledge', params=dict(actor=actor)).json()['calls']
        assert call['player_alias'] == 's01' and call['origin'] == 'ancestor' and call['non_clickable'] is True
        assert call['source_id'] == cited and call['anchors'] == [expected]
    assert len(counted) == 1
    feed = client.get(f'{url}/feed').json()['items']
    assert next(row['source_read'] for row in feed if row.get('tool') == 'player_source') == {
        'source_id': cited, 'origin': 'ancestor', 'player_alias': 's01', 'non_clickable': True}
    png = tmp_path / 'runs' / 'other' / 'sources' / f'{cited}.png'
    png.write_bytes(b'replacement')
    [fact] = client.get(f'{url}/delivered-knowledge').json()['facts']['items']
    assert fact['frame_anchor'] == dict(expected, available=False, reason='frame_digest_mismatch')
    assert len(counted) == 2


def test_v4_run_curator_filters_lineage_and_withholds_unlisted_session_fields(mission, tmp_path, monkeypatch):
    from harness.viewer import curator_ops

    client, directory, root, _ = mission
    group = root / 'sessions' / 'admission-a'
    first, hygiene = group / 'w1', group / 'w2'
    hidden = '/Users/private/record.json'
    summary = dict(schema='curator-shadow/2', kind='session', session_id='session-a', session_kind='admission',
        record=hidden, run_state=f'error: {hidden}', started_wall=BASE + 2, wall_seconds=1, session_state='sealed',
        applied_service_tiers=['priority'], cap_usd='2.50', tokens=dict(prompt=100), tool_calls=dict(count=2),
        sandbox=dict(stopped=None, returncode=0), errors=[hidden, 'visible-error'], refused=['safe refusal'],
        verdicts=[dict(status='published', diagnostics=[hidden, 'safe verdict'])],
        drafts=dict(created=['draft-own']), proxy=dict(settled=True, private=hidden))
    (first / 'summary.json').write_text(json.dumps(summary))
    (hygiene / 'summary.json').write_text(json.dumps(dict(summary, session_kind='hygiene', session_id='session-hygiene',
        started_wall=BASE + 4, deferrals=2, applied_service_tiers=['flex'])))
    ledger = dict(ts=BASE, model=hidden, status=200, charged='0.01', applied_service_tier='priority', record=hidden,
                  tokens=dict(prompt=4, internal=hidden))
    (first / 'proxy-ledger.jsonl').write_text((json.dumps(ledger) + '\n') * (LIST_LIMIT + 3) + '{partial')
    limits = dict(cap_usd='40', session_cap_usd='3', service_tier='flex', flex_deferral_limit=3,
        hygiene=dict(enabled=True, min_windows=5, max_unexamined_steps=10, pass_cap_usd='0.30', max_spend_share='0.1',
                     max_requests=10, wall_seconds=90, host_wall_seconds=60, max_consecutive_failures=2))
    (root / 'status.json').write_text(json.dumps(dict(schema='curator-runner-status/2', limits=limits,
        current=dict(label='w2', session_kind='hygiene'), examined=[dict(session_id='examined-only', session_kind='admission'),
            *[dict(session_id=f'earlier-{i}', session_kind='admission') for i in range(LIST_LIMIT)]],
        failures=dict(sessions=2, snapshots=1, hygiene=1, flex_deferrals=2))))
    gate = tmp_path / 'gate.jsonl'

    def result(session, n):
        return dict(schema='curator-gate/2', operation='submission', operation_id=f'{n:032x}', status='published',
                    base_version='v1', restored_from=None, version='v2', submission=f'submission-{n}', session=session,
                    from_drafts=[], diagnostics=[hidden])

    gate.write_text(''.join(json.dumps(result(session, i)) + '\n'
                            for i, session in enumerate(('session-a', 'other-admission', 'examined-only'))))
    drafts = tmp_path / 'drafts'
    for name, session in (('draft-own', 'session-a'), ('draft-other', 'other-admission'), ('draft-examined', 'examined-only')):
        draft = draft_manifest(name)
        draft['provenance']['sessions'] = [session]
        write_draft(drafts, 'drafts', draft)
    grooming = tmp_path / 'grooming.json'
    grooming.write_text(json.dumps(grooming_receipt('admission-a', stale_records=4)))
    client = TestClient(create_app(client.app.state.catalog, frame_sources=FrameSources(
        curator_results=(('gate', gate),), curator_drafts=(('drafts', drafts),), curator_grooming=grooming)))
    url = '/api/view/run/mission'
    calls = []
    compact = curator_ops._compact

    def tracked(*args):
        calls.append(args[1:])
        return compact(*args)

    monkeypatch.setattr(curator_ops, '_compact', tracked)
    payload = client.get(f'{url}/curator')
    data = payload.json()
    assert payload.status_code == 200 and hidden not in payload.text and '"record"' not in payload.text
    assert data['schema'] == API and data['grooming']['stale_records'] == 4
    assert data['runner']['status']['status_schema'] == 'curator-runner-status/2'
    assert data['runner']['status']['limits'] == limits and data['runner']['status']['current']['session_kind'] == 'hygiene'
    assert data['runner']['status']['failures'] == dict(sessions=2, snapshots=1, hygiene=1, flex_deferrals=2)
    assert [row['label'] for row in data['sessions']] == ['w1', 'w2', 'w3']
    assert data['spend']['ingestion_usd'] == '0.12685395' and data['spend']['hygiene_usd'] == '1.5'
    assert data['spend']['deferrals'] == 2 and data['spend']['applied_tiers'] == dict(flex=1, priority=1)
    assert data['spend']['hygiene_share'] == pytest.approx(1.5 / 1.6714952)
    assert data['gate_verdicts']['total_lineage'] == data['drafts']['total_lineage'] == 3
    assert [row['session'] for row in data['gate_verdicts']['items']] == ['session-a', 'examined-only']
    assert [row['id'] for row in data['drafts']['items']] == ['draft-examined', 'draft-own']
    assert client.get(f'{url}/summary').json()['curator_spend'] == data['spend']
    chart = client.get(f'{url}/telemetry').json()['curator_sessions']
    assert [(row['label'], row['session_kind']) for row in chart] == [('w1', 'admission'), ('w2', 'hygiene'), ('w3', None)]
    assert len(calls) == 3
    for name in ('session-a', 'w1', 'admission-a:w1'):
        response = client.get(f'{url}/curator/session/{name}')
        detail = response.json()
        assert response.status_code == 200 and detail['schema'] == API
        assert hidden not in response.text and '"record"' not in response.text
        assert detail['session']['tokens']['prompt'] == 100 and detail['session']['errors'] == ['visible-error']
        assert detail['session']['verdicts'][0]['diagnostics'] == ['safe verdict']
        assert (detail['ledger_total'], detail['ledger_omitted'], len(detail['ledger'])) == (LIST_LIMIT + 3, 3, LIST_LIMIT)
        assert detail['ledger'][0]['tokens']['prompt'] == 4 and detail['ledger'][0]['model'] is None
    for value in ('bad%2Fname', 'bad%5Cname', 'x' * (ID_LIMIT + 1)):
        assert client.get(f'{url}/curator/session/{value}').json()['error'] == 'bad_session_id'
    assert client.get(f'{url}/curator/session/no-such').json()['error'] == 'unknown_curator_session'
    for path in (first, hygiene):
        (path / 'summary.json').unlink()
    (root / 'status.json').unlink()
    empty = client.get(f'{url}/curator').json()
    assert empty['gate_verdicts']['items'] == empty['drafts']['items'] == []
    assert empty['gate_verdicts']['total_lineage'] == empty['drafts']['total_lineage'] == 3
    relinked(first / 'proxy-ledger.jsonl', directory / 'outside-ledger')
    assert client.get(f'{url}/curator/session/w1').json()['ledger_total'] == 0
