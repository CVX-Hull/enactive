"""The read-only spectator viewer (ADR008, spectator-view/1) over synthetic runs and a pure fake binding.

Every route is exercised through Starlette's TestClient: schema, bounds, pagination, frame digest refusal, no
write methods, Pause conditions (met and clear) and incremental live evaluation. These tests establish the API
contract, not any game reader.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

import pytest
from starlette.testclient import TestClient

from harness.evaluation.core.pipeline import evaluate
from harness.evaluation.core.records import CORE_VERSION, open_readonly, read_metadata
from harness.viewer.app import MAX_BYTES, create_app
from harness.viewer.catalog import API, Catalog
from harness.viewer.live import LiveEvaluator
from harness.viewer.pause import dollars_per_minute, looping_streak
from tests.test_evaluation_core import (BASE, F, FakeBinding, LIMITS, Run, SESSION, ended_run, growing_run, iso, key,
    main_scenario, memory_scenario)


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
    return [f'{base}/summary', f'{base}/steps', f'{base}/tools', f'{base}/calls', f'{base}/requests', f'{base}/memory',
        f'{base}/programs', f'{base}/handoffs']


CROSS_ROUTES = ['/api/view/runs', '/api/view/improve/changes', '/api/view/improve/failures', '/api/view/compare?group=arm',
    '/api/view/compare?group=start&runs=base1,aid1', '/api/view/explore', '/api/view/explore?arm=base&metric=stall.longest']


def test_every_json_route_has_the_schema_and_stays_bounded(archive):
    client, catalog, _ = archive
    session = 'a' * 32
    for route in [*CROSS_ROUTES, *run_routes(session)]:
        response = client.get(route)
        assert response.status_code == 200, (route, response.text[:200])
        assert response.headers['content-type'] == 'application/json'
        assert response.json()['schema'] == API == 'spectator-view/1'
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
    assert died['labels'] == dict(arm='base', start='S1', scenario='s', lineage=None, admission=None)
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


def test_memory_programs_and_handoffs(tmp_path):
    runs = tmp_path / 'runs'
    memory_scenario(runs / 'mem')
    evaluate(runs / 'mem', FakeBinding(), tmp_path / 'root', created_wall=1.0)
    data = data_directory(tmp_path)
    client = TestClient(create_app(Catalog(tmp_path / 'root', (runs,), data_dir=data)))
    records = client.get(f'/api/view/run/{SESSION}/memory').json()
    assert records['available'] is True and [r['kind'] for r in records['records']] == ['work', 'decision', 'claim']
    first, second, third = records['records']
    assert first['carried_by'] and not third['carried_by'] and second['text'] == 'note' and second['chain'] == []
    assert {r['tool'] for r in first['reads']} >= {'player_memory_read', 'player_memory_query'}
    programs = client.get(f'/api/view/run/{SESSION}/programs').json()
    assert [p['id'] for p in programs['programs']] == ['prog-old'] and [r['status'] for r in programs['runs']] == ['done', 'yield', 'done']
    assert programs['saves'][0]['program_id'] == 'prog-new'
    handoffs = client.get(f'/api/view/run/{SESSION}/handoffs').json()['handoffs']
    assert len(handoffs) == 1 and handoffs[0]['decisions_to_resume'] == 2 and handoffs[0]['carry_text'] == 'carry'
    assert handoffs[0]['carried_ids'] == [first['id']] and handoffs[0]['carry_ratio'] == pytest.approx(0.25)
    # a human label that names a carried record is the identity check
    (data / 'labels.jsonl').write_text(json.dumps(dict(id='l', session=SESSION, seq_start=0, seq_end=0, target=first['id'],
        code='identity_or_world_error', verdict='confirm', note='wrong world', author='o', date='d', taxonomy_version=1)) + '\n')
    checked = client.get(f'/api/view/run/{SESSION}/handoffs').json()['handoffs'][0]['identity_check']
    assert checked['checked'] is True and checked['errors'][0]['note'] == 'wrong world'
    assert client.get(f'/api/view/run/{SESSION}/memory').json()['records'][0]['labels'][0]['id'] == 'l'


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
    # Synthetic requests are seconds apart, so any real ceiling is crossed by the one-hour projection; only the
    # spend case declares a small one.
    ceiling = dict(accounting=dict(prior_reserved_usd='0.5', ceiling_usd='1.0', prospective_reserved_usd='0.9') if kind == 'spend'
        else dict(prior_reserved_usd='0', ceiling_usd='1000', prospective_reserved_usd='1'))
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
    current, unversioned, future = (tmp_path / 'runs' / name for name in ('current', 'unversioned', 'future'))
    for directory, manifest in ((current, dict(schema='campaign-run/5', session='1' * 32)), (unversioned, dict(session='2' * 32)),
            (future, dict(schema='campaign-run/6', session='3' * 32))):
        directory.mkdir()
        (directory / 'manifest.json').write_text(json.dumps(manifest))
    catalog = Catalog(tmp_path / 'root', (tmp_path / 'runs',), data_dir=data_directory(tmp_path))
    assert catalog.run_dir_for('1' * 32, {}) == current
    assert catalog.run_dir_for('2' * 32, {}) is None and catalog.run_dir_for('3' * 32, {}) is None
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
    (run_dir / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/5', session=SESSION)))
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
