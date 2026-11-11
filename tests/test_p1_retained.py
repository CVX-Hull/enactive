"""Synthetic admission-prefix recovery through real projection, gate and Git state; no provider."""
from __future__ import annotations

from decimal import Decimal
import json
import hashlib
from pathlib import Path
import sqlite3

import pytest

from harness.curator import sandbox, session
from harness.curator.knowledge import Repository, _git
from tests.test_p1_replay import b_args, deliver_args, rows_of, schedule_of
from tests.test_trace_projection import make_session, make_store
from tools.curator_host import p1_replay as replay
from tools.curator_host import p1_retained as retained
from tools.curator_host import shadow


def historical_fixture(path):
    """Serialize the historical /1 evidence shape; the live writer only emits /2."""
    data = json.loads(path.read_text())
    data['schema'] = retained.EVIDENCE_SCHEDULE_SCHEMA
    for key in ('new_cap_usd', 'new_cost_usd', 'retained_cost_usd'):
        data.pop(key)
    path.write_text(json.dumps(data))


@pytest.fixture
def prefix_world(tmp_path, monkeypatch):
    runtime, evidence = tmp_path/'runtime', tmp_path/'evidence'
    for index, name in enumerate(('t1', 't2')):
        trace = make_session(evidence/'syn/computer-sessions', name)
        with sqlite3.connect(trace/'session.sqlite3') as db:
            db.execute('UPDATE operations SET created_wall = created_wall * 10 + ?', (index * 100,))
    make_store(evidence/'syn/memory.sqlite3')
    monkeypatch.setitem(replay.LINEAGES, 'syn', replay.Lineage('syn', ('t1', 't2'), 'memory.sqlite3'))
    lose = ['t2']
    calls = []

    class Proxy:
        token = 'fixture-token'

        def __init__(self, **kwargs):
            self.cap = kwargs['cap_usd']
            self.ledger = kwargs['ledger']
            self.ledger.write_text(json.dumps(dict(status=200, charged='.1', usage_missing=False, breach=False))+'\n')

        def start(self):
            return 12345  # No listener: the scripted sandbox below makes no network request.

        def close(self):
            return dict(schema='curator-proxy-close/1', spent_snapshot_usd='.1', settled=True,
                        unsettled_requests=0, pending_reserved_usd='0', receipt_error=None,
                        revoked=False, breaches=0)

    def run(argv, layout, **kwargs):
        name = Path(argv[-1]).stem
        calls.append(name)
        failed = name == lose[0]
        if not failed:
            version = (layout.workspace/'brief.md').read_text().split('`')[1]
            data = dict(schema='curator-submission/1', base_version=version, summary='fixture', from_drafts=[],
                        changes=[dict(op='add_type', type=dict(schema='curator-type/1', name='type_'+name,
                                                              description='fixture type', fields=['x']))])
            for sid in ('s1', 's2'):  # First accepts; second is stale. Both feedback rows must survive seeding.
                target = layout.workspace/'submissions'/sid
                target.mkdir()
                (target/'submission.json').write_text(json.dumps(data))
        telemetry = [dict(type='request-start', monotonic_ms=1),
                     dict(type='request-end', status=200, cost=.1, prompt_tokens=10, completion_tokens=2)]
        if not failed:
            telemetry.append(dict(type='host-end', reason='finished', ok=True))
        kwargs['stdout'].write(('\n'.join(map(json.dumps, telemetry))+'\n').encode())
        return sandbox.Result(-15 if failed else 0, 'volume free-space floor' if failed else None,
                              0, 0, .1, [], {})

    monkeypatch.setattr(shadow, 'ModelProxy', Proxy)
    monkeypatch.setattr(shadow, 'host_tools', lambda: dict(roots=(), env={}))
    monkeypatch.setattr(shadow, 'host_identity', lambda *args: dict(name='scripted'))
    monkeypatch.setattr(shadow, 'host_argv', lambda host, config: ('scripted', str(config)))
    monkeypatch.setattr(sandbox, 'run', run)
    original = replay.run_b(b_args(runtime, evidence), 'fixture-key')
    assert not original['complete'] and original['sessions_run'] == 2
    historical_fixture(schedule_of(runtime))
    frozen = runtime/'prospective-freeze.json'
    frozen.write_text('{}')
    plan = runtime/'retained/plan.json'
    info = retained.prepare(schedule_of(runtime), runtime, {'syn': ('t1', 't2')}, 1, frozen, plan)
    return runtime, evidence, frozen, plan, info['plan_sha256'], lose, calls


def prefix_args(data, stage='recovered', cap='.5'):
    runtime, evidence, frozen, plan, digest, *_ = data
    return b_args(runtime, evidence, '--retained-prefix', str(plan), '--retained-sha256', digest,
                  '--frozen', str(frozen), stage=stage, cap=cap)


def test_seed_preserves_git_and_accepted_rejected_feedback_and_next_brief(prefix_world):
    runtime, _, frozen, plan_path, digest, *_ = prefix_world
    plan = retained.load(plan_path, digest, runtime, {'syn': ('t1', 't2')}, 1, frozen)
    source = Repository(runtime/plan['seeds']['syn']['root'], 'cdda')
    target = Repository(runtime/'knowledge/p1/copied/r1/syn', 'cdda')
    retained.seed(plan, 'syn', runtime, target)
    assert _git(source.path, 'show-ref', '--heads', '--tags') == _git(target.path, 'show-ref', '--heads', '--tags')
    assert (source.state/'gate.jsonl').read_bytes() == (target.state/'gate.jsonl').read_bytes()
    feedback = [json.loads(line) for line in (target.state/'gate.jsonl').read_text().splitlines()]
    assert [row['accepted'] for row in feedback] == [True, False]
    trace = dict(sessions=[])
    assert session.brief(source, source.published(), trace, []) == session.brief(target, target.published(), trace, [])
    assert not (target.state/'sessions').exists()  # No failed workspace, session record or draft is imported.


def test_fresh_suffix_composes_a_complete_selection_without_double_charging(prefix_world):
    runtime, evidence, _, _, _, lose, calls = prefix_world
    original = schedule_of(runtime).read_bytes()
    lose[0] = False
    result = replay.run_b(prefix_args(prefix_world), 'fixture-key')
    assert result['complete'] and result['sessions_run'] == 1 and result['retained_sessions'] == 1
    assert result['total_cost_usd'] == '0.1' and result['cap_usd'] == '0.5'
    assert calls == ['t1', 't2', 't2']
    selected_path = runtime/'curator-shadow/p1/recovered/r1/schedule.json'
    selected = replay.load_schedule(selected_path)
    assert selected['retained_cost_usd'] == selected['new_cost_usd'] == '0.1'
    assert selected['total_cost_usd'] == '0.2' and selected['cap_usd'] == '0.6'
    # Research costs retain the lost admission too; the selection is not a second invoice.
    assert Decimal(json.loads(original)['total_cost_usd']) + Decimal(result['total_cost_usd']) == Decimal('.3')
    assert [row['session'] for row in selected['lineages']['syn']['sessions']] == ['t1', 't2']
    assert replay.b_complete(selected, 'syn')
    assert schedule_of(runtime).read_bytes() == original
    assert not replay.b_complete(json.loads(schedule_of(runtime).read_text()), 'syn')
    with pytest.raises(replay.ReplayError, match='p1-schedule/2'):
        replay.load_schedule(schedule_of(runtime))
    out = runtime/'p1-delivered/recovered'
    replay.deliver(deliver_args(runtime, evidence, out, selected_path))
    assert rows_of(out) and all(row['complete'] for row in rows_of(out))
    record = next((runtime/'knowledge/p1/recovered/r1/syn/cdda.state/sessions').iterdir())
    manifest = json.loads((record/'manifest.json').read_text())
    expected = json.loads(prefix_world[3].read_text())['next_inputs']['syn']
    assert manifest['pinned']['brief_sha256'] == expected['brief_sha256']
    assert manifest['pinned']['trace_manifest_sha256'] == expected['trace_manifest_sha256']
    assert manifest['budgets']['cap_usd'] == '0.5'  # A new cap, not identical budget notes.


@pytest.mark.parametrize('change', ['plan', 'freeze', 'receipt', 'extra-tag', 'gate', 'draft', 'archive', 'staging', 'workspace'])
def test_changed_or_nonempty_retained_state_is_rejected_before_credentials(prefix_world, monkeypatch, change):
    runtime, evidence, frozen, plan_path, digest, *_ = prefix_world
    plan = json.loads(plan_path.read_text())
    repo = Repository(runtime/plan['seeds']['syn']['root'], 'cdda')
    if change == 'plan':
        plan_path.write_text(plan_path.read_text()+' ')
    elif change == 'freeze':
        frozen.write_text('{"changed":true}')
    elif change == 'receipt':
        path = runtime/next(name for name in plan['files'] if name.endswith('/summary.json'))
        path.write_text(path.read_text()+' ')
    elif change == 'extra-tag':
        _git(repo.path, 'tag', 'v99')
    elif change == 'gate':
        with (repo.state/'gate.jsonl').open('a') as stream:
            stream.write('{}\n')
    else:
        directory = {'draft': 'drafts', 'archive': 'drafts-archive', 'staging': 'drafts-staging',
                     'workspace': 'workspaces'}[change]
        (repo.state/directory/'unexpected').write_text('fixture')

    def forbidden(*args, **kwargs):
        raise AssertionError('credentials must not be retrieved')

    monkeypatch.setattr(shadow, 'credential', forbidden)
    assert replay.main(['b', '--stage', 'never', '--repeat', '1', '--lineage', 'syn', '--cap-usd', '.5',
                        '--runtime-root', str(runtime), '--evidence-root', str(evidence), '--frozen', str(frozen),
                        '--retained-prefix', str(plan_path), '--retained-sha256', digest]) == 2
    assert not (runtime/'curator-shadow/p1/never').exists()


def test_suffix_storage_loss_stops_without_certifying_the_selection(prefix_world):
    runtime, *_ = prefix_world
    result = replay.run_b(prefix_args(prefix_world), 'fixture-key')
    selected = replay.load_schedule(runtime/'curator-shadow/p1/recovered/r1/schedule.json')
    assert result['stopped'] == 'session-aborted' and not result['complete']
    assert not replay.b_complete(selected, 'syn')


@pytest.mark.parametrize('field', ['brief_sha256', 'trace_manifest_sha256'])
def test_input_reproduction_is_checked_before_any_fresh_host(prefix_world, monkeypatch, field):
    runtime, _, _, _, _, lose, calls = prefix_world
    lose[0] = False
    original = replay.retained_plan

    def wrong(args):
        plan = original(args)
        plan['next_inputs']['syn'][field] = '0'*64
        return plan

    monkeypatch.setattr(replay, 'retained_plan', wrong)
    result = replay.run_b(prefix_args(prefix_world), 'fixture-key')
    assert not result['complete'] and result['stopped'] == 'session-aborted'
    assert calls == ['t1', 't2']  # Preparation failed before the scripted host could run.


def test_complete_earlier_lineage_is_reused_without_a_new_host(prefix_world, monkeypatch):
    runtime, evidence, frozen, _, _, lose, calls = prefix_world
    for index, name in enumerate(('u1', 'u2')):
        trace = make_session(evidence/'syn2/computer-sessions', name)
        with sqlite3.connect(trace/'session.sqlite3') as db:
            db.execute('UPDATE operations SET created_wall = created_wall * 10 + ?', (index * 100,))
    make_store(evidence/'syn2/memory.sqlite3')
    monkeypatch.setitem(replay.LINEAGES, 'syn2', replay.Lineage('syn2', ('u1', 'u2'), 'memory.sqlite3'))
    lose[0] = 'u2'
    replay.run_b(b_args(runtime, evidence, stage='two-source', lineage=('syn', 'syn2')), 'fixture-key')
    source = runtime/'curator-shadow/p1/two-source/r1/schedule.json'
    historical_fixture(source)
    plan_path = runtime/'retained/two.json'
    info = retained.prepare(source, runtime, {'syn': ('t1', 't2'), 'syn2': ('u1', 'u2')}, 1, frozen, plan_path)
    assert info['retained_sessions'] == 3 and info['remaining_sessions'] == 1
    lose[0] = False
    before = len(calls)
    args = b_args(runtime, evidence, '--retained-prefix', str(plan_path), '--retained-sha256', info['plan_sha256'],
                  '--frozen', str(frozen), stage='two-recovered', cap='.5', lineage=('syn', 'syn2'))
    result = replay.run_b(args, 'fixture-key')
    assert result['complete'] and result['sessions_run'] == 1 and result['retained_sessions'] == 3
    assert calls[before:] == ['u2']
    selected = replay.load_schedule(runtime/'curator-shadow/p1/two-recovered/r1/schedule.json')
    assert all(replay.b_complete(selected, name) for name in ('syn', 'syn2'))
    assert selected['total_cost_usd'] == '0.4' and result['total_cost_usd'] == '0.1'


@pytest.mark.parametrize('change', ['hole', 'duplicate', 'wrong-order', 'unsupported-schema'])
def test_invalid_source_cannot_be_reapproved_as_a_new_plan(prefix_world, change):
    runtime, _, frozen, *_ = prefix_world
    source = schedule_of(runtime)
    data = json.loads(source.read_text())
    rows = data['lineages']['syn']['sessions']
    if change == 'hole':
        rows.pop(0)
    elif change == 'duplicate':
        rows[1]['session'] = rows[0]['session']
    elif change == 'wrong-order':
        rows.reverse()
    else:
        data['schema'] = 'p1-schedule/0'
    source.write_text(json.dumps(data))
    with pytest.raises(retained.RetainedError):
        retained.prepare(source, runtime, {'syn': ('t1', 't2')}, 1, frozen, runtime/'retained/invalid.json')


@pytest.mark.parametrize('change', ['survivors', 'errors', 'refused', 'returncode', 'stopped', 'published_after'])
def test_authoritative_closeout_contradiction_cannot_be_hidden_by_summary(prefix_world, change):
    runtime, _, frozen, *_ = prefix_world
    source = json.loads(schedule_of(runtime).read_text())
    failed = source['lineages']['syn']['sessions'][-1]
    summary = json.loads((schedule_of(runtime).parent/failed['summary']).read_text())
    root = Path(summary['record'])
    record = json.loads((root/'close-out.json').read_text())
    if change == 'published_after':
        record['published_after'] = 'v99'
    else:
        record['manifest']['lifecycle'][change] = {'survivors': [999], 'errors': ['close-out failed'],
                                                 'refused': ['unsafe tree'], 'returncode': 99,
                                                 'stopped': 'another stop'}[change]
    (root/'close-out.json').write_text(json.dumps(record))
    (root/'manifest.json').write_text(json.dumps(record['manifest']))
    with pytest.raises(retained.RetainedError, match='authoritative lifecycle or publication'):
        retained.prepare(schedule_of(runtime), runtime, {'syn': ('t1', 't2')}, 1, frozen,
                         runtime/'retained/contradiction.json')


def test_historical_schedule_needs_explicit_digest_bound_offline_migration(prefix_world):
    runtime, evidence, _, _, _, lose, _ = prefix_world
    lose[0] = False
    replay.run_b(b_args(runtime, evidence, stage='historical-complete'), 'fixture-key')
    source = runtime/'curator-shadow/p1/historical-complete/r1/schedule.json'
    historical_fixture(source)
    original = source.read_bytes()
    with pytest.raises(replay.ReplayError, match='p1-schedule/2'):
        replay.load_schedule(source)
    out = runtime/'retained/migrated.json'
    digest = hashlib.sha256(original).hexdigest()
    info = retained.migrate_schedule(source, digest, runtime, {'syn': ('t1', 't2')}, out)
    selected = replay.load_schedule(out)
    assert info['sessions'] == 2 and source.read_bytes() == original
    assert selected['new_cost_usd'] == selected['new_cap_usd'] == '0'
    assert selected['retained_cost_usd'] == selected['total_cost_usd'] == '0.2'
    assert selected['migration']['source_sha256'] == digest
    assert replay.b_complete(selected, 'syn')
    with pytest.raises(retained.RetainedError, match='source digest'):
        retained.migrate_schedule(source, '0'*64, runtime, {'syn': ('t1', 't2')}, runtime/'retained/wrong.json')


def test_current_schedule_rejects_inconsistent_retained_and_new_costs(prefix_world):
    runtime, _, _, _, _, lose, _ = prefix_world
    lose[0] = False
    replay.run_b(prefix_args(prefix_world), 'fixture-key')
    path = runtime/'curator-shadow/p1/recovered/r1/schedule.json'
    data = json.loads(path.read_text())
    data['new_cost_usd'] = '0.2'
    path.write_text(json.dumps(data))
    with pytest.raises(replay.ReplayError, match='accounting disagree'):
        replay.load_schedule(path)


def test_reapproved_plan_with_changed_host_limits_still_fails_before_credentials(prefix_world, monkeypatch):
    runtime, evidence, frozen, *_ = prefix_world
    for path in (schedule_of(runtime).parent/'host-config').glob('*.json'):
        value = json.loads(path.read_text())
        value['max_requests'] = 119
        path.write_text(json.dumps(value))
    plan = runtime/'retained/changed-host.json'
    info = retained.prepare(schedule_of(runtime), runtime, {'syn': ('t1', 't2')}, 1, frozen, plan)

    def forbidden(*args, **kwargs):
        raise AssertionError('changed host template must not retrieve credentials')

    monkeypatch.setattr(shadow, 'credential', forbidden)
    assert replay.main(['b', '--stage', 'never', '--repeat', '1', '--lineage', 'syn', '--cap-usd', '.5',
                        '--runtime-root', str(runtime), '--evidence-root', str(evidence), '--frozen', str(frozen),
                        '--retained-prefix', str(plan), '--retained-sha256', info['plan_sha256']]) == 2


@pytest.mark.parametrize('cap', ['nan', 'inf', '-inf', '0'])
def test_new_allocation_must_be_finite_and_positive_before_launch(prefix_world, cap):
    runtime, *_, calls = prefix_world
    args = prefix_args(prefix_world, stage='bad-cap')
    args.cap_usd = float(cap)
    with pytest.raises(replay.ReplayError, match='finite and positive'):
        replay.run_b(args, 'fixture-key')
    assert calls == ['t1', 't2'] and not (runtime/'curator-shadow/p1/bad-cap').exists()


def test_live_prefix_loading_does_not_parse_historical_schedule_format(prefix_world, monkeypatch):
    runtime, _, _, _, _, lose, _ = prefix_world
    lose[0] = False
    original = retained._json

    def current_only(path):
        assert path != schedule_of(runtime), 'live loading must not parse historical /1'
        return original(path)

    def no_migration(*args, **kwargs):
        raise AssertionError('offline import must not run inside live execution')

    monkeypatch.setattr(retained, '_json', current_only)
    monkeypatch.setattr(retained, 'inspect', no_migration)
    assert replay.run_b(prefix_args(prefix_world), 'fixture-key')['complete']
