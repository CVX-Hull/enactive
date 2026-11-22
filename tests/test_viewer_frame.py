"""The spectator's frame (`spectator-frame/1`, ADR 009's spectator direction) over synthetic runs, container indexes and episodes.

No sealed evidence is read: one synthetic run stands in for an actor session, a synthetic index describes it and a
synthetic `probe-episodes/1` document anchors episodes in its frames. The tracked #397 index and episodes are
checked only for shape, with an empty catalog.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from harness.evaluation.core.pipeline import evaluate
from harness.evaluation.core.sources import MANIFEST_SCHEMA
from harness.trace.sidecar import INDEX_SCHEMA, SCHEMA
from harness.viewer.app import MAX_BYTES, create_app
from harness.viewer.catalog import Catalog
from harness.viewer.frame import API, DATA_ROOT, FrameSources
from tests.test_evaluation_core import FakeBinding, main_scenario
from tests.test_viewer_api import data_directory, snapshot

SESSION = 'a' * 32
ABSENT = 'e' * 32
FRAME = 'spectator-frame/1'
ROUTES = ['/api/view/frame/health', '/api/view/frame/containers', '/api/view/frame/episodes']


def manifest(name: str, session: str, state: str = 'sealed') -> dict:
    return dict(schema=SCHEMA, id=f'syn/{name}', kind='actor-session', owner_role='actor',
        inputs=dict(session_id=session, actors=[dict(directory='001', actor_id='actor-one', given_sha256={})]),
        pinned=dict(source_commit='c0ffee', run_manifest_sha256=None), budgets={}, lifecycle=dict(state=state),
        provenance=dict(evidence_study='syn', path=f'computer-sessions/{name}'),
        retention=dict(policy='evidence', note='sealed'))


def anchor(session: str, number: int | None, chunk: str = 'base1-001', **extra) -> dict:
    return dict(chunk=chunk, frame=None if number is None else f'{session}-{number}', **extra)


def episode(name: str, observed: dict, needed: dict, acted_without: dict | None = None) -> dict:
    return dict(id=name, title=f'Episode {name}', fact='F1', record=None, observed=observed, lost_at='base1-001>base1-002',
        probe=dict(boundary='base1-001>base1-002', failing=True, costly=True, annotation='blinded'), needed=needed,
        acted_without=acted_without)


def episodes_document() -> dict:
    return dict(schema='probe-episodes/1', lineage='syn', study='syn', source='synthetic', note='synthetic evaluation data',
        episodes=[
            episode('served', anchor(SESSION, 1), anchor(SESSION, 3), anchor(SESSION, 4)),
            episode('missing', anchor(SESSION, None, text='stated in the actor text only'), anchor(SESSION, 9999)),
            episode('elsewhere', anchor(ABSENT, 5, chunk='gone-001'), anchor(ABSENT, 6, chunk='gone-001'))])


def evaluate_frame_scenario(run: Path, root: Path, *, session: str, created_wall: float) -> None:
    main_scenario(run, session=session)
    package = run / 'manifest.json'
    document = json.loads(package.read_text())
    document['schema'] = MANIFEST_SCHEMA
    document['labels'] = dict(document.get('labels', {}), world=None)
    package.write_text(json.dumps(document))
    evaluate(run, FakeBinding(), root, created_wall=created_wall)


@pytest.fixture
def frame(tmp_path):
    runs = tmp_path / 'runs'
    evaluate_frame_scenario(runs / 'base1', tmp_path / 'root', session=SESSION, created_wall=1.0)
    containers = tmp_path / 'containers'
    containers.mkdir()
    index = dict(schema=INDEX_SCHEMA, study='syn', containers=[manifest('base1', SESSION), manifest('gone', ABSENT)])
    (containers / 'syn.json').write_text(json.dumps(index))
    probes = tmp_path / 'probes'
    (probes / 'syn').mkdir(parents=True)
    (probes / 'syn' / 'episodes.json').write_text(json.dumps(episodes_document()))
    (probes / 'syn' / 'a.jsonl').write_text('{}\n')     # other probe files sit beside the episodes and are ignored
    (probes / 'plain').mkdir()                           # a lineage without episodes contributes nothing
    catalog = Catalog(tmp_path / 'root', (runs,), data_dir=data_directory(tmp_path))
    sources = FrameSources(containers, probes)
    return TestClient(create_app(catalog, frame_sources=sources)), catalog, sources, tmp_path


def test_every_frame_route_has_its_schema_and_stays_bounded(frame):
    client, *_ = frame
    for route in [*ROUTES, '/api/view/frame/containers/syn/base1']:
        response = client.get(route)
        assert response.status_code == 200, (route, response.text[:200])
        assert response.headers['content-type'] == 'application/json'
        assert response.json()['schema'] == API == FRAME
        assert len(response.content) < MAX_BYTES
    for bad in ('limit=501', 'limit=0', 'after=-1', 'after=x'):
        assert client.get(f'/api/view/frame/containers?{bad}').status_code == 400, bad
    assert client.get('/api/view/frame/nothing').status_code == 404


def test_containers_list_one_generic_inventory_and_detail_is_the_manifest(frame):
    client, *_ = frame
    listing = client.get('/api/view/frame/containers').json()
    assert listing['total'] == 2 and listing['kinds'] == {'actor-session': 2} and listing['next'] is None
    row = listing['items'][0]
    assert row == dict(id='syn/base1', kind='actor-session', owner_role='actor', lifecycle_state='sealed',
        retention_policy='evidence', evidence_study='syn', index_study='syn')
    page = client.get('/api/view/frame/containers?limit=1').json()
    assert len(page['items']) == 1 and page['next'] == 1 and page['total'] == 2
    assert client.get('/api/view/frame/containers?limit=1&after=1').json()['items'][0]['id'] == 'syn/gone'
    detail = client.get('/api/view/frame/containers/syn/base1').json()
    assert detail['container'] == manifest('base1', SESSION) and detail['index_study'] == 'syn'
    missing = client.get('/api/view/frame/containers/syn/nothing')
    assert missing.status_code == 404 and missing.json()['error'] == 'unknown_container'


@pytest.mark.parametrize('damage', ['kind', 'state', 'fields', 'schema', 'repeat'])
def test_an_invalid_manifest_or_index_is_refused_not_listed(frame, damage):
    client, _, sources, _ = frame
    path = sources.containers / 'syn.json'
    index = json.loads(path.read_text())
    broken = index['containers'][0]
    if damage == 'kind':
        broken['kind'] = 'cupboard'
    elif damage == 'state':
        broken['lifecycle']['state'] = 'active'          # an actor session is only ever sealed
    elif damage == 'fields':
        del broken['retention']
    elif damage == 'schema':
        index['schema'] = 'container-index/0'
    else:
        index['containers'][1]['id'] = broken['id']
    path.write_text(json.dumps(index))
    for route in ('/api/view/frame/containers', '/api/view/frame/containers/syn/base1', '/api/view/frame/health',
            '/api/view/frame/episodes'):
        response = client.get(route)
        assert response.status_code == 500, (damage, route)
        assert response.json()['error'] in ('invalid_container', 'bad_data_file')


def test_health_measures_actor_cadence_and_never_invents_the_rest(frame):
    client, *_ = frame
    body = client.get('/api/view/frame/health').json()
    slots = {slot['id']: slot for slot in body['slots']}
    assert list(slots) == ['actor_cadence', 'curator_lag', 'gate_pass_rate', 'snapshot_freshness', 'program_delegation_share',
        'monitor_alerts', 'spend_against_cap']
    assert body['containers'] == 2 and body['runs'] == 1     # only base1 is a catalog run of a container
    cadence = slots['actor_cadence']
    hours = 2540 / 3600
    assert cadence['state'] == 'measured' and cadence['source'] == 'derived' and cadence['runs'] == 1
    assert cadence['unreadable_runs'] == 0
    assert cadence['decisions'] == 13 and cadence['steps'] == 14 and cadence['game_hours'] == pytest.approx(hours)
    assert cadence['decisions_per_game_hour'] == pytest.approx(13 / hours)
    assert cadence['steps_per_game_hour'] == pytest.approx(14 / hours)
    assert slots['curator_lag'] == dict(id='curator_lag', label='Curator lag', state='no-data', detail='curator runner status: not configured')
    phases = {slot_id: slot for slot_id, slot in slots.items() if slot_id not in ('actor_cadence', 'curator_lag')}
    curator, programs = 'curator-and-memory', 'programs-and-monitor'
    assert {i: (s['state'], s['phase']) for i, s in phases.items()} == {
        'gate_pass_rate': ('not-yet-measured', curator),
        'snapshot_freshness': ('not-yet-measured', curator), 'program_delegation_share': ('not-yet-measured', programs),
        'monitor_alerts': ('not-yet-measured', programs), 'spend_against_cap': ('not-yet-measured', curator)}
    assert all(set(slot) == {'id', 'label', 'state', 'phase'} for slot in phases.values())     # no number rides along


def test_health_states_the_curator_runners_own_lag_and_never_a_guess(tmp_path):
    path = tmp_path / 'status.json'
    lag = lambda: {s['id']: s for s in runner_status_client(tmp_path, path).get('/api/view/frame/health').json()['slots']}['curator_lag']
    assert lag()['state'] == 'no-data' and lag()['detail'] == 'curator runner status: missing'
    path.write_text(json.dumps(dict(schema='curator-runner-status/1', state='in-session', lag=20, backlog=21,
        latest_version=dict(version='v31', coverage=None))))
    assert lag() == dict(id='curator_lag', label='Curator lag', state='measured', source='recorded', lag=20, backlog=21,
        runner_state='in-session', latest_version='v31')
    path.write_text(json.dumps(dict(schema='curator-runner-status/1', state='polling', lag='unknown', backlog=3)))
    assert lag()['state'] == 'no-data' and 'lag' not in lag()
    path.write_text('{"schema":')
    assert lag()['detail'] == 'curator runner status: malformed'


def test_the_runner_status_of_a_selected_run_is_its_own(frame):
    """A configured status file belongs to the live run: a recorded run shows its own runner's file or none."""
    _, catalog, sources, tmp_path = frame
    configured = tmp_path / 'live-status.json'
    configured.write_text(json.dumps(dict(schema='curator-runner-status/1', state='polling', lag=1)))
    client = TestClient(create_app(catalog, frame_sources=FrameSources(sources.containers, sources.probes, curator_runner_status=configured)))
    assert client.get(RUNNER_STATUS).json()['status']['lag'] == 1
    assert client.get(RUNNER_STATUS, params=dict(run=SESSION)).json()['source_status'] == 'missing'
    own = tmp_path / 'runs' / 'base1' / 'curator-runner' / 'status.json'
    own.parent.mkdir()
    own.write_text(json.dumps(dict(schema='curator-runner-status/1', state='ended', lag=7)))
    assert client.get(RUNNER_STATUS, params=dict(run='base1')).json()['status']['lag'] == 7
    assert client.get(RUNNER_STATUS, params=dict(run='nope')).status_code == 404


@pytest.mark.parametrize('component', ['curator-runner', 'curator-runner/status.json'])
def test_the_runner_status_never_leaves_the_run_package_through_a_symlink(frame, component):
    _, catalog, sources, tmp_path = frame
    run = tmp_path / 'runs' / 'base1'
    own = run / 'curator-runner' / 'status.json'
    own.parent.mkdir()
    own.write_text(json.dumps(dict(schema='curator-runner-status/1', state='ended', lag=7)))
    # As the supervisor configures it, by its path in the package, and as the page asks for it, by the run.
    client = TestClient(create_app(catalog, frame_sources=FrameSources(sources.containers, sources.probes, curator_runner_status=own)))
    asked = (dict(), dict(run='base1'))
    assert [client.get(RUNNER_STATUS, params=p).json()['status']['lag'] for p in asked] == [7, 7]
    (run / component).rename(tmp_path / 'aside')
    (run / component).symlink_to(tmp_path / 'aside', target_is_directory=component == 'curator-runner')
    assert [client.get(RUNNER_STATUS, params=p).json()['source_status'] for p in asked] == ['unreadable', 'unreadable']
    slots = {slot['id']: slot for slot in client.get('/api/view/frame/health').json()['slots']}
    assert slots['curator_lag']['state'] == 'no-data'


def test_health_without_container_runs_reports_no_data_rather_than_zero(frame):
    _, catalog, sources, tmp_path = frame
    empty = tmp_path / 'empty'
    empty.mkdir()
    client = TestClient(create_app(catalog, frame_sources=FrameSources(empty, sources.probes)))
    slots = {slot['id']: slot for slot in client.get('/api/view/frame/health').json()['slots']}
    assert slots['actor_cadence']['state'] == 'no-data' and 'decisions_per_game_hour' not in slots['actor_cadence']
    assert client.get('/api/view/frame/containers').json()['items'] == []


def test_episodes_resolve_anchors_to_runs_and_say_when_a_frame_cannot_be_served(frame):
    client, _, _, tmp_path = frame
    body = client.get('/api/view/frame/episodes').json()
    assert len(body['lineages']) == 1
    lineage = body['lineages'][0]
    assert (lineage['lineage'], lineage['study']) == ('syn', 'syn')
    served, missing, elsewhere = lineage['episodes']
    assert served['title'] == 'Episode served' and served['lost_at'] == 'base1-001>base1-002'
    assert served['probe'] == dict(boundary='base1-001>base1-002', failing=True, costly=True, annotation='blinded')
    for key, number in (('observed', 1), ('needed', 3), ('acted_without', 4)):
        assert served[key] == dict(chunk='base1-001', run='base1', actor='001', actor_id='actor-one', container='syn/base1',
            source_id=f'{SESSION}-{number}', available=True, reason=None)
    # An anchor the existing frame route would refuse is listed as unavailable with the route's own reason.
    assert missing['observed'] == dict(chunk='base1-001', run='base1', actor='001', actor_id='actor-one', container='syn/base1',
        source_id=None, available=False, reason='no_frame', text='stated in the actor text only')
    assert missing['needed']['available'] is False and missing['needed']['reason'] == 'unknown_frame'
    assert missing['acted_without'] is None
    assert elsewhere['needed'] == dict(chunk='gone-001', run=None, actor='001', actor_id='actor-one', container='syn/gone',
        source_id=f'{ABSENT}-6', available=False, reason='run_not_in_catalog')
    # The anchor's run name is the one the existing per-run routes accept.
    route = f'/api/view/run/{served["needed"]["run"]}/frame/{served["needed"]["source_id"]}'
    assert client.get(route).status_code == 200
    png = tmp_path / 'runs' / 'base1' / 'sources' / f'{SESSION}-3.png'
    png.write_bytes(b'tampered')
    again = client.get('/api/view/frame/episodes').json()['lineages'][0]['episodes'][0]
    assert again['needed']['available'] is False and again['needed']['reason'] == 'frame_digest_mismatch'
    assert again['observed']['available'] is True


def test_an_invalid_episodes_document_is_refused(frame):
    client, _, sources, _ = frame
    path = sources.probes / 'syn' / 'episodes.json'
    for damage in ('no needed frame', 'repeated id', 'numeric title', 'unknown anchor field'):
        document = episodes_document()
        if damage == 'no needed frame':
            document['episodes'][0]['needed']['frame'] = None
        elif damage == 'repeated id':
            document['episodes'][1]['id'] = document['episodes'][0]['id']
        elif damage == 'numeric title':
            document['episodes'][0]['title'] = 7
        else:
            document['episodes'][0]['observed']['url'] = 'https://example.com'
        path.write_text(json.dumps(document))
        response = client.get('/api/view/frame/episodes')
        assert response.status_code == 500 and response.json()['error'] == 'bad_data_file', damage


def test_a_run_name_shared_by_two_sessions_is_not_reported_available(frame):
    _, _, sources, tmp_path = frame
    other = 'b' * 32
    twin = tmp_path / 'twin-runs'
    evaluate_frame_scenario(twin / 'base1', tmp_path / 'root', session=other, created_wall=2.0)
    catalog = Catalog(tmp_path / 'root', (tmp_path / 'runs', twin), data_dir=data_directory(tmp_path))
    document = episodes_document()
    document['episodes'][0]['needed'] = anchor(other, 3)
    (sources.probes / 'syn' / 'episodes.json').write_text(json.dumps(document))
    client = TestClient(create_app(catalog, frame_sources=sources))
    needed = client.get('/api/view/frame/episodes').json()['lineages'][0]['episodes'][0]['needed']
    assert needed['available'] is False and needed['reason'] == 'ambiguous_run'
    # The route really would refuse it: the name selects the other session's run.
    assert client.get(f'/api/view/run/base1/frame/{other}-3').status_code == 404


def test_an_anchor_whose_session_is_absent_never_borrows_a_same_named_run(frame):
    client, _, sources, _ = frame
    document = episodes_document()
    document['episodes'][0]['needed'] = anchor(ABSENT, 3)           # chunk names base1, frame names another session
    (sources.probes / 'syn' / 'episodes.json').write_text(json.dumps(document))
    needed = client.get('/api/view/frame/episodes').json()['lineages'][0]['episodes'][0]['needed']
    assert needed['run'] is None and needed['reason'] == 'run_not_in_catalog' and needed['container'] == 'syn/gone'


def test_an_unreadable_store_marks_its_anchors_and_leaves_the_routes_up(frame, monkeypatch):
    from harness.viewer.catalog import ViewError
    client, catalog, _, _ = frame

    def broken(_info):
        raise ViewError(503, 'record_unavailable', 'synthetic')

    monkeypatch.setattr(catalog, 'connect', broken)
    episodes = client.get('/api/view/frame/episodes')
    assert episodes.status_code == 200
    served = episodes.json()['lineages'][0]['episodes'][0]
    assert served['needed']['available'] is False and served['needed']['reason'] == 'record_unavailable'
    health = client.get('/api/view/frame/health')
    assert health.status_code == 200
    cadence = {slot['id']: slot for slot in health.json()['slots']}['actor_cadence']
    assert cadence['state'] == 'no-data' and 'unreadable' in cadence['detail']


def test_the_tracked_data_follows_the_shapes_the_frame_reads(tmp_path):
    """The tracked #397 index and episodes validate; with no evidence in the catalog every anchor is honestly unavailable."""
    catalog = Catalog(tmp_path / 'none', data_dir=tmp_path)
    client = TestClient(create_app(catalog))
    containers = client.get('/api/view/frame/containers').json()
    assert containers['total'] >= 7 and all(i['kind'] == 'actor-session' for i in containers['items'])
    assert any(i['id'].startswith('397-seven-day/') for i in containers['items'])
    episodes = client.get('/api/view/frame/episodes').json()['lineages']
    assert [lineage['lineage'] for lineage in episodes] == ['397']
    assert len(episodes[0]['episodes']) == 4
    needed = [e['needed'] for e in episodes[0]['episodes']]
    assert all(a['available'] is False and a['reason'] == 'run_not_in_catalog' for a in needed)
    assert DATA_ROOT.joinpath('containers', '397-seven-day.json').is_file()


def test_the_frame_writes_nothing_and_accepts_no_write_method(frame):
    client, _, _, tmp_path = frame
    # The tracked data and the run directories. (The evaluation store's own WAL index may move under any reader.)
    watched = [tmp_path / 'containers', tmp_path / 'probes', tmp_path / 'runs']
    before = [snapshot(directory) for directory in watched]
    assert before[0] and before[1] and before[2]
    for route in [*ROUTES, '/api/view/frame/containers/syn/base1', '/api/view/frame/containers?limit=1']:
        assert client.get(route).status_code == 200, route
    assert client.get('/api/view/frame/containers/syn/nothing').status_code == 404
    assert [snapshot(directory) for directory in watched] == before
    for method in ('post', 'put', 'delete', 'patch'):
        for route in [*ROUTES, '/api/view/frame/containers/syn/base1']:
            assert getattr(client, method)(route).status_code == 405, (method, route)
    assert [snapshot(directory) for directory in watched] == before


def curator_row(**changes):
    row = dict(schema='curator-gate/2', operation='submission', operation_id='a' * 32,
               status='published', base_version='v1', restored_from=None, version='v2',
               submission='submission', session='session', from_drafts=[], diagnostics=[])
    row.update(changes)
    return row


def test_curator_sources_and_snapshot_pages(tmp_path):
    from harness.viewer.curator import parse_sources
    path = tmp_path / 'gate.jsonl'
    rows = [curator_row(), curator_row(status='rejected', version=None),
            curator_row(operation='restore', status='published', submission=None, session=None, restored_from='v0'),
            curator_row(operation='restore', status='unchanged', submission=None, session=None, restored_from='v0'),
            curator_row(status='unknown', version=None), curator_row(status='unknown', version='v3')]
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(curator_results=parse_sources([f'alpha={path}']))))
    assert client.get('/api/view/frame/curator-sources').json()['items'] == [{'label': 'alpha'}]
    url = '/api/view/frame/curator-results?source=alpha&limit=2'
    first = client.get(url).json()
    assert first['source_status'] == 'available' and first['total'] == 6 and first['next'] == 2
    assert first['items'][0]['operation_id'] == 'a' * 32 and 'from_drafts' not in first['items'][0]
    digest = first['snapshot']['sha256']
    assert client.get(url + '&after=2').status_code == 400
    page = client.get(url + '&after=2&snapshot=' + digest).json()
    assert [row['status'] for row in page['items']] == ['published', 'unchanged']
    assert [r['version'] for r in client.get(url + '&after=4&snapshot=' + digest).json()['items']] == [None, 'v3']
    path.write_text(path.read_text() + json.dumps(rows[0]) + '\n')
    changed = client.get(url + '&after=2&snapshot=' + digest)
    assert changed.status_code == 409 and changed.json()['error'] == 'source_changed'
    assert client.get(url + '&snapshot=invalid').status_code == 400
    assert client.get('/api/view/frame/curator-results?source=other').status_code == 404
    assert client.post(url).status_code == 405
    assert str(path) not in client.get(url).text


def test_curator_states_and_bounded_projection(tmp_path):
    from harness.evaluation.core.sources import MAX_JSON_FILE_BYTES
    from harness.viewer.curator import parse_sources
    path = tmp_path / 'gate'
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(curator_results=(('x', path),))))
    def state():
        return client.get('/api/view/frame/curator-results?source=x').json()
    assert state()['source_status'] == 'missing'
    path.write_bytes(b'')
    assert state()['source_status'] == 'empty'
    path.write_text(json.dumps(curator_row()))
    assert state()['source_status'] == 'malformed'
    path.write_text(json.dumps(curator_row()) + '\n{')
    assert state()['source_status'] == 'malformed' and state()['items'] == []
    path.write_text(json.dumps(curator_row()) + '\n' + json.dumps(curator_row(schema='old')) + '\n')
    assert state()['source_status'] == 'unsupported' and state()['items'] == []
    path.write_text(json.dumps(curator_row(status='pending')) + '\n')
    assert state()['source_status'] == 'unsupported'
    path.write_text(json.dumps(curator_row(submission='x' * 513, diagnostics=['<script>' + 'x' * 1024] * 101)) + '\n')
    item = state()['items'][0]
    assert item['submission'] is None and item['omitted_characters']['submission'] == 513
    assert len(item['diagnostics']) == 100 and len(item['diagnostics'][0]) == 1024 and item['diagnostics_omitted'] == 1
    path.write_bytes(b'x' * (MAX_JSON_FILE_BYTES + 1))
    assert state()['source_status'] == 'too_large' and state()['snapshot']['bytes'] == MAX_JSON_FILE_BYTES + 1
    path.unlink()
    path.mkdir()
    assert state()['source_status'] == 'unreadable'
    for values in (['=x'], ['a='], ['bad label=x'], ['a=x', 'a=y']):
        with pytest.raises(ValueError):
            parse_sources(values)
    assert parse_sources(['a=x=y'])[0][1] == Path('x=y')


def test_curator_projection_of_gate_and_restore_producer_results(tmp_path):
    from harness.curator.gate import restore
    from tests.test_curator_gate import fact, kind, make_repo, run, submission
    repo = make_repo(tmp_path)
    published = run(repo, submission(tmp_path, [dict(op='add_type', type=kind()),
                                               dict(op='add_fact', fact=fact())]))
    rejected = run(repo, submission(tmp_path, [], name='stale', base_version='v0'))
    changed = restore(repo, expected_base='v1', target='v0')
    unchanged = restore(repo, expected_base='v2', target='v0')
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(
        curator_results=(('fixture', repo.state / 'gate.jsonl'),))))
    result = client.get('/api/view/frame/curator-results?source=fixture').json()
    assert result['source_status'] == 'available'
    assert [(r['operation'], r['status'], r['base_version'], r['restored_from'], r['version']) for r in result['items']] == [
        ('submission', 'published', 'v0', None, 'v1'), ('submission', 'rejected', 'v0', None, None),
        ('restore', 'published', 'v1', 'v0', 'v2'), ('restore', 'unchanged', 'v2', 'v0', 'v2')]
    assert [r['operation_id'] for r in result['items']] == [r['operation_id'] for r in (published, rejected, changed, unchanged)]


def test_curator_omits_path_details_from_real_producer_failure(tmp_path):
    from harness.curator.knowledge import Repository
    from tests.test_curator_gate import kind, run, submission
    repo = Repository(tmp_path / 'private-repository-location', 'cdda')
    result = run(repo, submission(tmp_path, [dict(op='add_type', type=kind())]))
    assert result['status'] == 'rejected' and str(repo.path) in result['diagnostics'][0]
    source = repo.state / 'gate.jsonl'
    before = source.read_bytes()
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(
        curator_results=(('fixture', source),))))
    response = client.get('/api/view/frame/curator-results?source=fixture')
    item = response.json()['items'][0]
    assert item['status'] == 'rejected' and item['path_details_omitted'] == 1
    assert item['diagnostics'] == [] and str(tmp_path) not in response.text
    assert source.read_bytes() == before
    source.write_text(json.dumps(curator_row(submission='/private/a', session='C:\\private\\b')) + '\n')
    item = client.get('/api/view/frame/curator-results?source=fixture').json()['items'][0]
    assert item['submission'] is None and item['session'] is None and item['path_details_omitted'] == 2
    assert item['omitted_characters'] == {'submission': 10, 'session': 12}


def test_curator_oversize_response_can_be_narrowed_without_truncating_history(tmp_path):
    source = tmp_path / 'gate.jsonl'
    source.write_text((json.dumps(curator_row(diagnostics=['x' * 1024] * 100)) + '\n') * 45)
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(
        curator_results=(('fixture', source),))))
    url = '/api/view/frame/curator-results?source=fixture'
    assert client.get(url).status_code == 413
    narrowed = client.get(url + '&limit=1').json()
    assert narrowed['source_status'] == 'available' and narrowed['total'] == 45 and narrowed['next'] == 1
    assert len(narrowed['items']) == 1


def test_curator_session_receipts_and_failures(tmp_path):
    path = tmp_path / 'close-out.json'
    manifest = dict(schema='container-manifest/1', id='session-1', kind='curator-session', owner_role='curator',
                    inputs=dict(session_kind='admission', trace_sessions=['trace-1'], window_frames=4, window={},
                                coverage=dict(schema='curator-coverage/2', session='trace-1', actor=None, last_step=None), drafts=['draft-1']),
                    pinned=dict(knowledge_version='v1', trace_manifest_sha256='a' * 64, brief_sha256='b' * 64, host={'private': '/secret'}),
                    budgets=dict(wall_seconds=60, memory_bytes=100, disk_bytes=200, cap_usd='2.50'),
                    lifecycle=dict(state='sealed', started_wall=1.0, ended_wall=2.0, stopped=None, returncode=0,
                                   survivors=[], errors=['private /secret'], refused=[]),
                    provenance=dict(repository='/secret/repo', seconds=1.0, peak_memory_bytes=5, peak_disk_bytes=6), retention={})
    report = dict(created=['draft-1'], renewed=[], aged=[], stale=[], abandoned=[], refused=[dict(id='/secret', reason='bad /secret')])
    receipt = dict(manifest=manifest, verdicts=[curator_row(), curator_row(status='unknown', version=None)], drafts=report, published_after='v2')
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(curator_sessions=(('receipt', path),))))
    url = '/api/view/frame/curator-session?source=receipt&limit=1'
    assert client.get('/api/view/frame/curator-session-sources').json()['items'] == [{'label': 'receipt'}]
    assert client.get(url).json()['source_status'] == 'missing'
    path.write_text(json.dumps(receipt))
    before = path.read_bytes()
    response = client.get(url)
    data = response.json()
    assert data['source_status'] == 'available' and data['total'] == 2 and data['next'] == 1
    assert data['header']['lifecycle']['survivor_count'] == 0 and data['drafts']['created']['items'] == ['draft-1']
    assert '/secret' not in response.text and path.read_bytes() == before
    digest = data['snapshot']['sha256']
    assert client.get(url + '&after=1').status_code == 400
    assert client.get(url + '&after=1&snapshot=' + digest).json()['items'][0]['status'] == 'unknown'
    manifest['lifecycle']['state'] = 'aborted'
    manifest['lifecycle']['survivors'] = None
    manifest['lifecycle'].pop('started_wall')
    manifest['inputs'] = {}; manifest['pinned'] = {}; manifest['budgets'] = {}; manifest['provenance'] = {}
    receipt['drafts'] = {}; receipt['verdicts'] = []; receipt['published_after'] = None
    path.write_text(json.dumps(receipt))
    assert client.get(url + '&snapshot=' + digest).status_code == 409
    minimal = client.get(url).json()
    assert minimal['header']['lifecycle']['survivor_count'] is None and minimal['drafts'] is None and minimal['total'] == 0
    manifest['kind'] = []
    path.write_text(json.dumps(receipt))
    assert client.get(url).json()['source_status'] == 'unsupported'
    manifest['kind'] = 'curator-session'; manifest['inputs'] = {'trace_sessions': 'bad'}
    path.write_text(json.dumps(receipt))
    assert client.get(url).json()['source_status'] == 'unsupported'
    path.write_text('{')
    assert client.get(url).json()['source_status'] == 'malformed'
    assert client.post(url).status_code == 405


def test_curator_session_reads_actual_minimal_close_out(tmp_path):
    from harness.curator.session import _close_out

    class Repository:
        def published(self):
            return 'v0'

    record = _close_out(Repository(), 'aborted-session', tmp_path, tmp_path, None, None,
                        ['pre-host failure'], {}, None, None, None)
    path = tmp_path / 'close-out.json'
    assert not path.read_bytes().endswith(b'\n')
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(curator_sessions=(('abort', path),))))
    result = client.get('/api/view/frame/curator-session?source=abort').json()
    assert result['source_status'] == 'available' and result['header']['id'] == record['manifest']['id']
    assert result['header']['lifecycle']['state'] == 'aborted' and result['drafts'] is None
    assert result['header']['lifecycle']['survivor_count'] is None and result['total'] == 0
    for key in ('ended_wall', 'stopped', 'returncode', 'survivors', 'errors', 'refused'):
        value = record['manifest']['lifecycle'].pop(key)
        path.write_text(json.dumps(record))
        assert client.get('/api/view/frame/curator-session?source=abort').json()['source_status'] == 'unsupported'
        record['manifest']['lifecycle'][key] = value
    record['manifest']['lifecycle']['state'] = 'sealed'
    path.write_text(json.dumps(record))
    assert client.get('/api/view/frame/curator-session?source=abort').json()['source_status'] == 'unsupported'


def test_curator_session_grooming_metadata_validation_and_bounds(tmp_path):
    from harness.evaluation.core.sources import MAX_JSON_FILE_BYTES
    path = tmp_path / 'receipt'
    manifest = dict(schema='container-manifest/1', id='groom', kind='curator-session', owner_role='curator',
                    inputs=dict(session_kind='grooming', trace_sessions=['s'], window_frames=0, window={},
                                coverage=dict(schema='curator-coverage/2', session='s', actor=None, last_step=None), drafts=[]),
                    pinned=dict(knowledge_version='v1', trace_manifest_sha256='a'*64, brief_sha256='b'*64, grooming_sha256='c'*64),
                    budgets=dict(wall_seconds=60, memory_bytes=100, disk_bytes=200, cap_usd='1E+2'),
                    lifecycle=dict(state='aborted', started_wall=1, ended_wall=2, stopped='timeout', returncode=-9,
                                   survivors=[42], errors=[], refused=[]),
                    provenance=dict(seconds=1, peak_memory_bytes=5, peak_disk_bytes=6), retention={})
    report = dict(created=[], renewed=[], aged=[], stale=[], abandoned=[], refused=[])
    receipt = dict(manifest=manifest, verdicts=[curator_row(status='unknown', version=None)], drafts=report, published_after=None)
    client = TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=FrameSources(curator_sessions=(('groom', path),))))
    url = '/api/view/frame/curator-session?source=groom'
    def get():
        path.write_text(json.dumps(receipt))
        return client.get(url).json()
    data = get()
    assert data['source_status'] == 'available' and data['drafts']['created']['items'] == []
    assert data['header']['inputs']['coverage']['schema'] == 'curator-coverage/2'
    assert data['header']['budgets']['cap_usd'] == '1E+2' and data['header']['lifecycle']['survivor_count'] == 1
    receipt['published_after'] = 'v' + '9' * 1000
    bounded = get()['header']
    assert bounded['published_after'] is None and bounded['omitted_characters']['published_after'] == 1001
    receipt['published_after'] = None
    for section, key in (('inputs', 'coverage'), ('pinned', 'brief_sha256'),
                         ('pinned', 'grooming_sha256'), ('budgets', 'wall_seconds')):
        value = manifest[section].pop(key)
        assert get()['source_status'] == 'unsupported'
        manifest[section][key] = value
    manifest['lifecycle']['state'] = 'sealed'
    manifest['lifecycle'].update(stopped=None, returncode=0)
    assert get()['source_status'] == 'available'
    value = manifest['provenance'].pop('peak_disk_bytes')
    assert get()['source_status'] == 'unsupported'
    manifest['provenance']['peak_disk_bytes'] = value
    manifest['lifecycle']['state'] = 'aborted'
    manifest['lifecycle'].update(stopped='timeout', returncode=-9)
    for first, last in ((0, 0), (2, 1)):
        manifest['inputs']['window'] = dict(session='s', actor='actor-1', first=first, last=last)
        assert get()['source_status'] == 'unsupported'
    manifest['inputs']['window'] = dict(session='s', actor='actor-1', first=1, last=2)
    assert get()['source_status'] == 'available'
    manifest['inputs']['window'] = {}
    manifest['lifecycle']['survivors'] = ['42']
    assert get()['source_status'] == 'unsupported'
    manifest['lifecycle']['survivors'] = []
    manifest['budgets']['wall_seconds'] = 10**1000
    assert get()['source_status'] == 'unsupported'
    manifest['budgets']['wall_seconds'] = 60
    manifest['inputs']['coverage']['schema'] = 'old'
    assert get()['source_status'] == 'unsupported'
    manifest['inputs']['coverage']['schema'] = 'curator-coverage/2'
    receipt['verdicts'][0]['schema'] = 'old'
    assert get()['source_status'] == 'unsupported'
    path.write_bytes(b'x' * (MAX_JSON_FILE_BYTES + 1))
    assert client.get(url).json()['source_status'] == 'too_large'
    path.unlink(); path.mkdir()
    assert client.get(url).json()['source_status'] == 'unreadable'


# The curator runner's status file. Against R-FALSE-CLAIM: a spectator watching the paid live run must never read
# a missing or half-written status as a curator that has caught up (zero lag, zero backlog).
RUNNER_STATUS = '/api/view/frame/curator-runner'


def runner_status_client(tmp_path, path):
    sources = FrameSources(containers=tmp_path / 'none', probes=tmp_path / 'none', curator_runner_status=path)
    return TestClient(create_app(Catalog(tmp_path / 'root'), frame_sources=sources, now=lambda: 2000.0))


def test_the_runner_status_file_shows_how_far_the_curator_trails_play(tmp_path):
    from tests.test_curator_runner import World, read
    world = World(tmp_path / 'run' / 'curator-runner')
    runner = world.runner()
    world.reading, world.outcomes = read({'actor-a': 25}), ['accepted']
    runner.poll()  # one session over steps 1-25, which publishes v1 stamped with that window
    world.reading = read({'actor-a': 30})
    runner.poll()  # play has reached step 30; five steps wait below the trigger
    path = world.directory / 'status.json'
    before = path.read_bytes()
    body = runner_status_client(tmp_path, path).get(RUNNER_STATUS).json()
    assert path.read_bytes() == before and not any(p.name.startswith('.') for p in world.directory.iterdir())
    assert body['schema'] == FRAME and body['source_status'] == 'available' and body['read_wall'] == 2000.0
    assert body['snapshot']['bytes'] == len(before)
    status = body['status']
    assert status['state'] == 'polling' and status['session'] == 'run'
    assert {k: status['position'][k] for k in ('actor', 'step', 'operation', 'ordinal')} == dict(
        actor='actor-a', step=30, operation='op-actor-a-30', ordinal=30)
    assert status['as_of'] == status['position'] and set(status['as_of']['read_wall']) == {'began', 'ended'}
    assert status['after_last_read'] == 'unknown'
    assert status['covered_prefix'] == dict(end=dict(actor='actor-a', step=25, operation='op-actor-a-25', ordinal=25),
                                            restore=None)
    assert (status['lag'], status['backlog'], status['stamp_distance'], status['unconfirmed']) == (5, 5, 5, 0)
    stamp = dict(session='run', actor='actor-a', last_step=25)
    assert status['last_confirmed']['version'] == 'v1' and status['last_confirmed']['coverage'] == stamp
    assert status['last_confirmed']['baseline'] is False
    assert status['latest_version'] == dict(version='v1', coverage=stamp, baseline=False)
    [examined] = status['examined']['items']
    assert examined['window'] == dict(session='run', actor='actor-a', first=1, last=25)
    assert (examined['outcome'], examined['advanced'], status['examined']['total']) == ('accepted', True, 1)
    assert status['current'] is None and status['stop_reason'] is None
    # Not written while the runner polls: the list and its counts stay null, never an empty list or zero.
    assert status['unexamined'] == dict(items=None, total=None, omitted=None)
    assert str(tmp_path) not in json.dumps(body)


def test_a_missing_partly_written_or_foreign_status_file_is_shown_as_such_never_as_zero(tmp_path):
    path = tmp_path / 'curator-runner' / 'status.json'
    client = runner_status_client(tmp_path, path)
    get = lambda: client.get(RUNNER_STATUS).json()
    assert get() == dict(schema=FRAME, source_status='missing', snapshot=None, read_wall=2000.0, status=None)
    path.parent.mkdir()
    whole = json.dumps(dict(schema='curator-runner-status/1', state='polling', lag=0, backlog=0))
    path.write_text(whole[:len(whole) // 2])  # a status read while partly written
    partial = get()
    assert partial['source_status'] == 'malformed' and partial['status'] is None and partial['snapshot']['bytes']
    path.write_text(json.dumps(dict(schema='curator-runner-status/0', lag=0)))
    assert get()['source_status'] == 'unsupported' and get()['status'] is None
    path.write_text('')
    assert get()['source_status'] == 'empty'
    path.unlink(); path.mkdir()
    assert get()['source_status'] == 'unreadable'
    unconfigured = TestClient(create_app(Catalog(tmp_path / 'root'))).get(RUNNER_STATUS).json()
    assert unconfigured['source_status'] == 'not_configured' and unconfigured['status'] is None


def test_an_absent_or_unknown_runner_value_is_unknown_and_a_path_is_withheld(tmp_path):
    path = tmp_path / 'status.json'
    path.write_text(json.dumps(dict(schema='curator-runner-status/1', state='polling', position='unknown',
        lag='unknown', backlog=-1, covered_prefix=dict(end=None, restore=dict(version='v3', restored_from='unknown',
        counted_through='v2')), last_confirmed=None, stop_reason='host-unavailable: /Users/someone/private',
        examined=[dict(label=f'l{n}', window=dict(session='s', actor='a', first=n, last=n)) for n in range(150)])))
    status = runner_status_client(tmp_path, path).get(RUNNER_STATUS).json()['status']
    assert status['position'] == status['as_of'] == status['lag'] == status['backlog'] == 'unknown'
    assert status['stamp_distance'] == status['latest_version'] == status['failures'] == 'unknown'
    assert status['after_last_read'] == status['unconfirmed'] == status['session'] == 'unknown'
    assert status['covered_prefix']['restore'] == dict(version='v3', restored_from='unknown', counted_through='v2')
    assert status['last_confirmed'] is None
    assert status['stop_reason'] is None and status['omitted_characters'] == {'stop_reason': 40}
    assert '/Users' not in json.dumps(status)
    examined = status['examined']
    assert (examined['total'], examined['omitted'], len(examined['items'])) == (150, 50, 100)
    assert examined['items'][0]['label'] == 'l50' and examined['items'][0]['outcome'] == 'unknown'
    assert status['unexamined'] == dict(items='unknown', total='unknown', omitted='unknown')


def test_invalid_runner_values_never_break_the_projection(tmp_path):
    path = tmp_path / 'status.json'
    window = dict(session='s', actor='a', first=1, last=2)
    path.write_text(json.dumps(dict(schema='curator-runner-status/1', after_last_read=7, updated_wall=1e20,
        examined=[None, 'row', 3, dict(label='l', window=window, started_wall=1e20, ended_wall=-1)],
        unexamined=[], latest_version=dict(version='v0', coverage=None),
        versions=[dict(version='v0', baseline=True, coverage=None)])))
    status = runner_status_client(tmp_path, path).get(RUNNER_STATUS).json()['status']
    assert status['after_last_read'] == 'unknown'  # the runner only ever writes its sentinel here
    unknown_row = {key: 'unknown' for key in ('label', 'window', 'session_id', 'outcome', 'advanced', 'started_wall',
                                               'ended_wall')}
    assert status['examined']['items'][:3] == [unknown_row] * 3
    # A finite wall time far out of range is passed on as recorded; the page shows it as unknown.
    assert status['examined']['items'][3]['started_wall'] == 1e20 and status['updated_wall'] == 1e20
    assert status['examined']['items'][3]['ended_wall'] == 'unknown'
    assert status['unexamined'] == dict(items=[], total=0, omitted=0)
    # A null stamp is only "no stamp"; whether the version is the runner's baseline is its own flag.
    assert status['latest_version'] == dict(version='v0', coverage=None, baseline=True)
