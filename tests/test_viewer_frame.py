"""The spectator's frame (`spectator-frame/1`, ADR 009 D18) over synthetic runs, container indexes and episodes.

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


@pytest.fixture
def frame(tmp_path):
    runs = tmp_path / 'runs'
    main_scenario(runs / 'base1', session=SESSION)
    evaluate(runs / 'base1', FakeBinding(), tmp_path / 'root', created_wall=1.0)
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
    phases = {slot_id: slot for slot_id, slot in slots.items() if slot_id != 'actor_cadence'}
    assert {i: (s['state'], s['phase']) for i, s in phases.items()} == {
        'curator_lag': ('not-yet-measured', 'P1'), 'gate_pass_rate': ('not-yet-measured', 'P1'),
        'snapshot_freshness': ('not-yet-measured', 'P1'), 'program_delegation_share': ('not-yet-measured', 'P2'),
        'monitor_alerts': ('not-yet-measured', 'P2'), 'spend_against_cap': ('not-yet-measured', 'P1')}
    assert all(set(slot) == {'id', 'label', 'state', 'phase'} for slot in phases.values())     # no number rides along


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
    main_scenario(twin / 'base1', session=other)                  # a second archived run with the same name
    evaluate(twin / 'base1', FakeBinding(), tmp_path / 'root', created_wall=2.0)
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
