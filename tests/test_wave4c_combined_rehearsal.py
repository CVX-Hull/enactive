"""Consolidated $0 Wave 3 + Wave 4 + Wave 4C end-to-end stand-in rehearsal (#943).

Exercises the combined stack together with zero CDDA launches and zero live provider spend:
- `campaign-run/13` (required top-level `context`);
- `curator-knowledge/5`, `curator-submission/3` (`validate_submission`, `add_fact`, `add_article`,
  `edit_article`, `remap_citations`, `retire_fact`), `curator-boundary-grooming/2` stale-citation
  close-out and `#918` proxy reservation bounds;
- `delivered-knowledge/4` export and `player-knowledge/4` (`bm25_1hop` + `_fold` morphological match,
  compact query `hits`, casefolded title read);
- real Node `tools/player_host` (`player-host/12`, `telemetry_version: 12`, bounded briefing,
  `already_in_context` reminder recall, `context_cut` hysteresis + `cut_result: "best_effort"` +
  ephemeral `recent_intents`, halving `tail-notice`, `"undelivered"` live knowledge update, and
  `spend-reserve-reached` handshake + orderly `player_finish`);
- `spectator-view/3` (`#464` read-only curator draft/gate views + `from_drafts` + API-scoped JSON
  `404`/`405` envelopes, `#957` `cut_result`/`spend-reserve-reached`/`tail-notice`/compact `returned_hits`,
  and `"undelivered"` update feed entry) plus `tools.host_analysis` roll-ups.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

import pytest
from starlette.testclient import TestClient

from harness.computer.store import SessionStore

from harness.curator import gate, sandbox
from harness.curator.check import current
from harness.curator.knowledge import Repository
from harness.curator.proxy import Price
from harness.curator.runner import Runner, Settings, TagLook, staged
from harness.evaluation.cdda import CddaBinding
from harness.evaluation.core.pipeline import evaluate
from harness.trace.sidecar import validate as validate_container
from harness.viewer.app import create_app
from harness.viewer.catalog import Catalog
from harness.viewer.frame import FrameSources
from tests import curator_stand_in
from tests.curator_stand_in import StandIn
from tests.curator_trace import SESSION_ID, LiveWriter, record_package
from tests.test_viewer_api import FakeBinding, data_directory
from tools import host_analysis, knowledge_export
from tools.curator_host import groom, live_runner, shadow

ROOT = Path(__file__).resolve().parents[1]
REPLAY_SCRIPT = ROOT / 'tests' / 'fixtures' / 'combined_rehearsal_replay.mjs'
PLAYER_HOST_READY = shutil.which('node') is not None and (ROOT / 'tools' / 'player_host' / 'node_modules').is_dir()
CURATOR_HOST_READY = (
    platform.system() == 'Darwin'
    and Path(sandbox.SANDBOX_EXEC).exists()
    and shutil.which('node') is not None
    and (shadow.HOST_DIR / 'node_modules').is_dir()
)
ACTOR_ID = '3' * 32


def _submit(repo: Repository, work: Path, name: str, frames: list[str], changes: list[dict], *,
            session_kind: str = 'admission', from_drafts: list[str] | None = None,
            last_step: int = 2) -> dict:
    sub_dir = work / name
    sub_dir.mkdir(parents=True, exist_ok=True)
    submission = dict(schema='curator-submission/3', base_version=repo.published(), summary=name, changes=changes)
    if from_drafts:
        submission['from_drafts'] = from_drafts
    (sub_dir / 'submission.json').write_text(json.dumps(submission))
    positions = {
        frame: dict(session='rehearsal-source', actor='001', step=index, order=[1, '001', index])
        for index, frame in enumerate(frames, 1)
    }
    labels = {SESSION_ID: dict(name='rehearsal-source', world='rehearsal-world', context=dict(ruleset='standard'))}
    coverage = dict(schema='curator-coverage/2', session='rehearsal-source', actor='001', last_step=last_step)
    result = gate.gate(repo, sub_dir, session_id=f'sess-{name}', window_frames=positions,
                       coverage=coverage, session_kind=session_kind, session_labels=labels)
    assert result['status'] == 'published', result['diagnostics']
    return result


@pytest.mark.skipif(not PLAYER_HOST_READY, reason='requires node and tools/player_host/node_modules')
def test_combined_wave3_wave4_player_host_and_spectator_rehearsal(tmp_path):
    # 1. Build a real `curator-knowledge/5` repository exercising `curator-submission/3`:
    #    `add_fact`, `add_article`, `edit_article`, `remap_citations`, `retire_fact`.
    frames = [f'{SESSION_ID}-{1000 + i}' for i in range(1, 5)]

    repo = Repository(tmp_path / 'knowledge', shadow.GAME)
    repo.ensure()
    sub_work = tmp_path / 'submissions'

    _submit(repo, sub_work, 'sub-v1', frames, [
        dict(op='add_fact', fact=dict(
            schema='curator-fact/6', record='fact', id='fact-boil-old', statement_kind='observation',
            subject='Purify water', tags=['water'], text='Boiling river water in a pot purifies dirty water.',
            scope=dict(ruleset='standard'), links=[], citations=[frames[0]])),
        dict(op='add_fact', fact=dict(
            schema='curator-fact/6', record='fact', id='fact-clean-water', statement_kind='observation',
            subject='Clean water container', tags=['water'], text='Store purified water inside sealed jugs.',
            scope=dict(ruleset='standard'), links=[], citations=[frames[1]])),
        dict(op='add_article', article=dict(
            schema='curator-fact/6', record='article', slug='water-purification', tags=['water'],
            title='Water Purification', lead='Boil dirty river water before drinking.',
            body=[dict(text='Purify water by boiling river water in a metal pot.', facts=['fact-boil-old'])],
            links=[])),
    ], from_drafts=['draft-water-01'])
    assert repo.published() == 'v1'

    # Supersede `fact-boil-old` (leaving a stale citation on `water-purification`) with a replacement fact.
    _submit(repo, sub_work, 'sub-v2', frames, [
        dict(op='supersede_fact', ids=['fact-boil-old'], reason_kind='restated', fact=dict(
            schema='curator-fact/6', record='fact', id='fact-boil-new', statement_kind='observation',
            subject='Purify water', tags=['water'], text='Boil dirty river water over fire for five minutes.',
            scope=dict(ruleset='standard'), links=[], citations=[frames[2]])),
    ])
    assert repo.published() == 'v2'
    assert groom.stale_records(repo, 'v2') == 1

    # Grooming submission clears stale citations via `remap_citations` + `edit_article`.
    _submit(repo, sub_work, 'sub-v3-groom', frames, [
        dict(op='remap_citations', **{'from': ['fact-boil-old'], 'to': 'fact-boil-new', 'in': ['water-purification']}),
        dict(op='edit_article', slug='water-purification',
             set_lead='Boil dirty river water over fire for five minutes before drinking.',
             add_claims=[dict(text='Keep purified water inside sealed jugs.', facts=['fact-clean-water'])]),
    ], session_kind='grooming')
    assert repo.published() == 'v3'
    assert groom.stale_records(repo, 'v3') == 0

    # Verify `#918` proxy reservation bounds against frozen terra prices.
    prices = shadow.load_prices(shadow.DEFAULT_PRICES)
    terra_price = prices[shadow.ARMS['terra'].model]
    assert isinstance(terra_price, Price)
    reservation = terra_price.reservation(120_000, 16_384)
    assert Decimal('0') < reservation < Decimal('5.00')

    # 2. Export real `delivered-knowledge/4` at `v1` (start, with `water-purification`) and `v3` (groomed live update)
    #    under `context={"ruleset": "standard"}`.
    run_dir = tmp_path / 'runs' / 'combined-rehearsal'
    (run_dir / 'actors' / '001').mkdir(parents=True)
    (run_dir / 'actors' / '002').mkdir(parents=True)
    v1_export = knowledge_export.published(repo, 'v1', world='rehearsal-world', context=dict(ruleset='standard'))
    v3_export = knowledge_export.published(repo, 'v3', world='rehearsal-world', context=dict(ruleset='standard'))
    assert v1_export['schema'] == 'delivered-knowledge/4' and v3_export['schema'] == 'delivered-knowledge/4'
    v1_bytes = (json.dumps(v1_export) + '\n').encode('utf-8')
    (run_dir / 'delivered-knowledge.json').write_bytes(v1_bytes)
    (run_dir / 'actors' / '001' / 'delivered-knowledge.json').write_bytes(v1_bytes)
    (run_dir / 'actors' / '002' / 'delivered-knowledge.json').write_bytes(v1_bytes)
    v3_path = tmp_path / 'v3-update.json'
    v3_path.write_text(json.dumps(v3_export) + '\n')

    # 3. Run two real Node `player-host/12` actors in place over real Python MCP (`player-knowledge/4`).
    completed = subprocess.run(
        ['node', str(REPLAY_SCRIPT), str(run_dir), str(v3_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
        env=dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8', ENACTIVE_TEST_PYTHON=sys.executable),
    )
    assert completed.returncode == 0, completed.stderr + '\n' + completed.stdout
    rehearsal = json.loads(completed.stdout.strip().splitlines()[-1])

    assert rehearsal['actor1'] == dict(ok=True, reason='external_stop_complete'), rehearsal['actor1']
    assert rehearsal['actor2'] == dict(ok=False, reason='provider-error'), rehearsal['actor2']
    assert rehearsal['host1']['schema'] == 'player-host/13' and rehearsal['host1']['telemetry_version'] == 13
    assert rehearsal['host1']['actor_id'] == ACTOR_ID
    assert rehearsal['host2']['schema'] == 'player-host/13' and rehearsal['host2']['telemetry_version'] == 13
    assert rehearsal['host2']['actor_id'] == '4' * 32
    assert rehearsal['cut_prompt_has_recent_intents'] is True
    assert rehearsal['cut_prompt_has_agenda'] is True
    assert len(rehearsal['agenda_events']) == 1 and rehearsal['agenda_events'][0]['op'] == 'upsert'
    applied_cuts = [c for c in rehearsal['cuts'] if c.get('outcome') == 'cut']
    assert any(c.get('cut_result') == 'best_effort' and c.get('uncovered_turns') == 0 for c in applied_cuts), rehearsal['cuts']
    assert len(rehearsal['tail_notices']) >= 1
    assert len(rehearsal['spend_reserves']) >= 1
    assert [u.get('outcome') for u in rehearsal['actor1_updates']] == ['delivered'], rehearsal['actor1_updates']
    assert [u.get('outcome') for u in rehearsal['actor2_updates']] == ['undelivered'], rehearsal['actor2_updates']

    # 4. Complete `campaign-run/14` run directory with real `player-host-inputs/5` frozen manifests
    #    so evaluator, `spectator-view/3`, and `host_analysis` verify snapshots and inspect both actors.
    manifest = dict(
        schema='campaign-run/14', session=SESSION_ID, source_commit='c' * 40,
        labels=dict(arm='rehearsal', start='S1', scenario='Wilderness / Campground / Survivor',
                    world='rehearsal-world', lineage=None, admission=None),
        context=dict(ruleset='standard'), live_knowledge_updates=True,
        spend_limit_usd='2.00', host=dict(argv=['/usr/bin/node']),
    )
    (run_dir / 'manifest.json').write_text(json.dumps(manifest))
    for actor_dir_name, actor_hex in (('001', ACTOR_ID), ('002', '4' * 32)):
        actor_dir = run_dir / 'actors' / actor_dir_name
        (actor_dir / 'actor.json').write_text(json.dumps(dict(actor_id=actor_hex)))
        actual_sha = hashlib.sha256((actor_dir / 'delivered-knowledge.json').read_bytes()).hexdigest()
        (actor_dir / 'frozen.json').write_text(json.dumps(dict(
            schema='player-host-inputs/5', session=SESSION_ID, actor_id=actor_hex,
            finish_reserve_usd='0.50', knowledge_updates='knowledge-updates.jsonl',
            files={'delivered-knowledge.json': actual_sha},
        )))
    (run_dir / 'receipt.json').write_text(json.dumps(dict(
        schema='campaign-receipt/7', session=SESSION_ID, source_commit='c' * 40,
        started_wall=1.0, ended_wall=5.0, elapsed_seconds=4.0, outcome='player_external_stop_complete_unassessed',
        native_absence_verified=True, deciding_hosts_quiescent=True, input_authority_revoked=True,
        normal_native_exit_zero=True,
        cleanup=dict(schema='computer-cleanup/1', session=SESSION_ID, native_absence_verified=True,
                     normal_native_exit_zero=True, native=dict(pid=1, pgid=1, returncode=0,
                     process_absent=True, group_absent=True)),
    )))
    # Real sealed `SessionStore` (`computer-session/1`) matching the run's session ID.
    store = SessionStore(run_dir, SESSION_ID, dict(max_inputs=100, max_requests=100, max_frames=100, max_bytes=10**7),
                         time.monotonic() + 3600)
    store.close()

    # 5. Prepare `#464` read-only curator drafts dir + gate journal + `curator-boundary-grooming/2` receipt.
    drafts_root = tmp_path / 'curator-drafts-source'
    draft_dir = drafts_root / 'drafts' / 'draft-water-01'
    draft_dir.mkdir(parents=True)
    draft_manifest = dict(
        schema='container-manifest/1', id='draft-water-01', kind='draft', owner_role='curator',
        inputs=dict(created_by_session='sess-sub-v1'), pinned={}, budgets=dict(max_bytes=4096),
        lifecycle=dict(state='open', untouched_sessions=0, last_touched_session='sess-sub-v1'),
        provenance=dict(sessions=['sess-sub-v1']),
        retention=dict(policy='stale after untouched sessions'),
    )
    validate_container(draft_manifest)
    (draft_dir / 'manifest.json').write_text(json.dumps(draft_manifest))
    grooming_receipt = tmp_path / 'grooming-summary.json'
    grooming_receipt.write_text(json.dumps(dict(
        schema='curator-boundary-grooming/2', run=SESSION_ID, knowledge_root=str(repo.path.parent),
        status='completed', reason=None, published_before='v2', published_after='v3',
        stale_records=0, cap_usd='2.50', cost_usd='0', session_state='sealed',
        verdicts=[dict(status='published', version='v3')],
        proxy=dict(settled=True, revoked=False, breaches=0), sandbox=dict(survivors=[]), summary=None,
    )))

    # 6. Evaluate and verify `spectator-view/3` (`#464` + `#957` + `"undelivered"`) and `tools.host_analysis`.
    eval_root = tmp_path / 'evaluations'
    evaluate(run_dir, FakeBinding(), eval_root, created_wall=1.0)
    frames_cfg = FrameSources(
        curator_results=(('rehearsal-gate', repo.state / 'gate.jsonl'),),
        curator_drafts=(('rehearsal-drafts', drafts_root),),
        curator_grooming=grooming_receipt,
    )
    client = TestClient(create_app(
        Catalog(eval_root, (run_dir.parent,), data_dir=data_directory(tmp_path)),
        frame_sources=frames_cfg,
    ))

    # `#957` summary, feed, telemetry, and knowledge compact hits.
    summary_resp = client.get(f'/api/view/run/{SESSION_ID}/summary')
    assert summary_resp.status_code == 200
    summary_body = summary_resp.json()
    assert summary_body['schema'] == 'spectator-view/3'
    host = summary_body['host_telemetry']
    assert host['context_cuts']['applied'] >= 1
    assert host['context_cuts']['by_result']['best_effort'] >= 1
    assert host['context_cuts']['latest']['cut_result'] == 'best_effort'
    assert host['spend_reserve_reached']['count'] >= 1
    assert host['tail_notices']['count'] >= 1
    assert summary_body['boundary_grooming']['source_status'] == 'available'
    assert summary_body['boundary_grooming']['status'] == 'completed'

    feed_items = client.get(f'/api/view/run/{SESSION_ID}/feed').json()['items']
    assert any(i['entry_kind'] == 'context_cut' and i.get('cut_result') == 'best_effort' for i in feed_items)
    assert any(i['entry_kind'] == 'knowledge_update' and i.get('outcome') == 'undelivered' for i in feed_items)
    assert any(i['entry_kind'] == 'knowledge_update' and i.get('outcome') == 'delivered' for i in feed_items)

    telem = client.get(f'/api/view/run/{SESSION_ID}/telemetry').json()
    assert any(c.get('cut_result') == 'best_effort' for c in telem['cuts'])
    assert len(telem['spend_reserve_reached']) >= 1 and telem['tail_notices']['count'] >= 1

    knowledge_page = client.get(f'/api/view/run/{SESSION_ID}/knowledge', params=dict(actor=ACTOR_ID)).json()
    assert knowledge_page['snapshot_status'] == 'verified'
    assert knowledge_page['snapshot']['version'] == 'v1'
    query_calls = [c for c in knowledge_page['calls'] if c['tool'] == 'player_knowledge_query']
    read_calls = [c for c in knowledge_page['calls'] if c['tool'] == 'player_knowledge_read']
    assert len(query_calls) == 1 and query_calls[0]['returned_hits'], query_calls
    hit_ids = [h['id'] for h in query_calls[0]['returned_hits']]
    assert 'water-purification' in hit_ids, hit_ids
    article_hit = next(h for h in query_calls[0]['returned_hits'] if h['id'] == 'water-purification')
    assert article_hit['kind'] == 'article' and article_hit['via'] in ('match', 'hop') and article_hit['snippet']
    assert len(read_calls) == 1 and read_calls[0]['returned_ids'] == ['water-purification']

    # `#464` curator draft & gate views + API-scoped JSON 404/405 envelopes.
    draft_sources = client.get('/api/view/frame/curator-draft-sources').json()
    assert draft_sources['schema'] == 'spectator-frame/1'
    assert [i['label'] for i in draft_sources['items']] == ['rehearsal-drafts']
    drafts_body = client.get('/api/view/frame/curator-drafts', params=dict(source='rehearsal-drafts')).json()
    assert drafts_body['source_status'] == 'available'
    assert [d['id'] for d in drafts_body['items']] == ['draft-water-01']
    gate_results = client.get('/api/view/frame/curator-results', params=dict(source='rehearsal-gate')).json()
    assert gate_results['source_status'] == 'available'
    assert any('draft-water-01' in (r.get('from_drafts') or ()) for r in gate_results['items'])

    r404 = client.get('/api/view/does-not-exist')
    assert r404.status_code == 404 and r404.json()['schema'] == 'spectator-view/3' and r404.json()['error'] == 'not_found'
    r405 = client.post('/api/view/runs')
    assert r405.status_code == 405 and r405.json()['schema'] == 'spectator-view/3' and r405.json()['error'] == 'method_not_allowed'

    # `#957` `tools.host_analysis` roll-up on the real `player-host/13` trace, plus `#1026` zero curator leakage.
    from harness.trace import projection
    trace_path = run_dir / 'actors' / '001' / 'host.jsonl'
    analyzed = host_analysis.analyze_trace(trace_path)
    assert analyzed['context_cuts']['by_result']['best_effort'] >= 1
    assert analyzed['spend_reserve_reached']['count'] >= 1
    rolled = host_analysis.host_summary([trace_path])
    assert rolled['selection']['context_cuts']['by_result']['best_effort'] >= 1
    assert rolled['selection']['spend_reserve_reached']['count'] >= 1
    (run_dir / 'agenda.json').write_text(json.dumps(dict(schema='player-agenda-continuation/1', cut_count=0, threads=[])))
    (run_dir / 'actors' / '001' / 'agenda.json').write_text(json.dumps(dict(
        schema='player-agenda-continuation/1', cut_count=1,
        threads=[dict(id='boil-water', title='Boil river water in shelter stove', status='active', created_at_cut=0, updated_at_cut=1)],
    )))
    proj_dir = tmp_path / 'projected-trace'
    projection.project([run_dir], proj_dir)
    assert not any(p.name in ('agenda.json', 'agenda-final.json', 'source-index.json') for p in proj_dir.rglob('*'))
    for p in proj_dir.rglob('*'):
        if p.is_file() and p.suffix in ('.json', '.jsonl', '.txt'):
            raw = p.read_text(encoding='utf-8', errors='ignore')
            assert 'player-agenda' not in raw and 'player_agenda' not in raw and 'boil-water' not in raw, p


@pytest.mark.skipif(not CURATOR_HOST_READY, reason='requires macOS Seatbelt and tools/curator_host/node_modules')
def test_combined_wave3_boundary_grooming_closeout_with_seatbelt_stand_in(tmp_path, monkeypatch):
    """Run real `tools.curator_host.groom` (`curator-boundary-grooming/2`) under macOS Seatbelt against
    loopback `StandIn` on a `campaign-run/13` run, verifying `validate_submission`, `remap_citations`,
    `edit_article`, stale-citation close-out (`stale_records == 0`), and settled proxy bounds."""
    original_script = curator_stand_in.script

    def rehearsal_script(messages, *args, **kwargs):
        calls = original_script(messages, *args, **kwargs)
        for index, (tool, params) in enumerate(calls or ()):
            if tool != 'write_file' or not params['path'].endswith('/submission.json'):
                continue
            submission = json.loads(params['content'])
            if params['path'].startswith('submissions/grooming/'):
                submission['changes'] = [
                    dict(op='remap_citations', **{'from': ['f1'], 'to': 'f2', 'in': ['guide']}),
                    dict(op='edit_article', slug='guide', set_lead='Updated stand-in lead after grooming.'),
                ]
                calls[index] = (tool, dict(params, content=json.dumps(submission)))
                calls.insert(index + 1, ('validate_submission', {'path': params['path']}))
            else:
                number = int(submission['base_version'][1:]) + 1
                fact = submission['changes'][-1]['fact']
                if number == 1:
                    fact.update(id='f1', text='initial observed control')
                    submission['changes'].append(dict(op='add_article', article=dict(
                        schema='curator-fact/6', record='article', slug='guide', tags=['control'],
                        title='Stand-in guide', lead='Initial stand-in lead.',
                        body=[dict(text='Initial control claim.', facts=['f1'])], links=[],
                    )))
                else:
                    fact.update(id='f2', text='refined observed control')
                    submission['changes'] = [dict(
                        op='supersede_fact', ids=['f1'], reason_kind='restated', fact=fact,
                    )]
                calls[index] = (tool, dict(params, content=json.dumps(submission)))
                calls.insert(index + 1, ('validate_submission', {'path': params['path']}))
            break
        return calls

    monkeypatch.setattr(curator_stand_in, 'script', rehearsal_script)
    runtime, run = tmp_path / 'runtime', tmp_path / 'rehearsal-admission'
    out = runtime / 'grooming'
    knowledge_root = runtime / 'knowledge' / 'cdda'
    with StandIn(cost=0) as stand_in:
        config_path = tmp_path / 'runner-config.json'
        config_path.write_text(json.dumps(dict(
            schema='curator-runner-config/2', knowledge_root=str(knowledge_root), arm='terra',
            service_tier='flex', cap_usd='2.00', session_cap_usd='1.00', upstream=stand_in.url,
            trigger_steps=2, ceiling_steps=2,
            host=dict(max_requests=10, max_output_tokens=4096, wall_seconds=120),
        )))
        config = live_runner.read_config(config_path, runtime)
        assert config['service_tier'] == 'flex' and config['host']['request_timeout_seconds'] == 960
        repo = Repository(config['knowledge_root'], shadow.GAME)
        repo.ensure()
        sessions = live_runner.Sessions(tmp_path / 'runner', config, repo, shadow.LOOPBACK_KEY)
        hygiene_sessions = live_runner.HygieneSessions(tmp_path / 'runner', config, repo, shadow.LOOPBACK_KEY, sessions=sessions)
        with LiveWriter(run) as writer:
            record_package(run, labels=dict(world='rehearsal-world', lineage=None, admission=None),
                           context=dict(ruleset='standard'), live=True)
            runner = Runner(tmp_path / 'runner', run.name, snapshot=staged(run), session_call=sessions,
                            hygiene_call=hygiene_sessions,
                            hygiene_check=lambda: dict(triggered=False, digest='d', reasons=[], counts={}),
                            look=TagLook(repo), settings=Settings(trigger_steps=2, ceiling_steps=2, poll_seconds=0.1, watch_seconds=0.1))
            writer(op='new_actor')
            for expected_version in ('v1', 'v2'):
                for _ in range(2):
                    writer(op='step')
                assert runner.poll()
                assert repo.published() == expected_version
            assert writer(op='close')['wal'] == 0
        # Before grooming, `v2` retired `f1` so `guide` carries 1 stale citation.
        assert groom.stale_records(repo, 'v2') == 1
        # Verify flex tier & prefix-suffix reservation mode reached the proxy ledger.
        ledgers = list((tmp_path / 'runner' / 'sessions').rglob('proxy-ledger.jsonl'))
        assert ledgers and any(
            json.loads(line).get('reservation_mode') == 'prefix-suffix'
            and json.loads(line).get('requested_service_tier') == 'flex'
            for path in ledgers for line in path.read_text().splitlines() if line.strip()
        )
        assert groom.main(['--run', str(run), '--config', str(config_path), '--runtime-root', str(runtime),
                           '--out', str(out), '--cap-usd', '1.00']) == 0

    summary = json.loads((out / 'grooming-summary.json').read_text())
    assert summary['schema'] == 'curator-boundary-grooming/2'
    assert (summary['status'], summary['reason']) == ('completed', None)
    assert (summary['published_before'], summary['published_after']) == ('v2', 'v3')
    assert summary['stale_records'] == 0
    assert summary['proxy']['settled'] is True and summary['proxy']['breaches'] == 0
    assert Decimal(summary['cost_usd']) == 0
    assert Decimal(summary['proxy']['max_reserved_usd']) > 0
    articles = [a for a in repo.articles('v3') if current(a)]
    assert len(articles) == 1 and articles[0]['lead'] == 'Updated stand-in lead after grooming.'
    assert articles[0]['body'][0]['facts'] == ['f2']

    # Pass the real `tools.curator_host.groom` receipt directly into `spectator-view/3`.
    eval_root = tmp_path / 'seatbelt-evaluations'
    evaluate(run, CddaBinding(), eval_root, created_wall=1.0)
    client = TestClient(create_app(
        Catalog(eval_root, (run.parent,), data_dir=data_directory(tmp_path)),
        frame_sources=FrameSources(curator_grooming=out / 'grooming-summary.json'),
    ))
    viewer_summary = client.get(f'/api/view/run/{SESSION_ID}/summary').json()
    assert viewer_summary['schema'] == 'spectator-view/3'
    assert viewer_summary['boundary_grooming']['source_status'] == 'available'
    assert viewer_summary['boundary_grooming']['status'] == 'completed'
    assert viewer_summary['boundary_grooming']['published_after'] == 'v3'
