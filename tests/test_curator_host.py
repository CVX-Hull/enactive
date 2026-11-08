"""The Pi curator host, its proxy and the shadow runner, end to end with no network and no spend (#454).

A local stand-in streams scripted OpenRouter chat completions. The real Node host runs through the
real model proxy and, on macOS, the real Seatbelt sandbox via `run_session` over a synthetic sealed
trace. The portable tests (runner argument handling, prices) run everywhere; the sandboxed ones are a
native lane and skip off macOS or without the host installed.
"""
from __future__ import annotations

from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from harness.curator import sandbox
from harness.curator.knowledge import Repository
from harness.curator.proxy import OPENROUTER, ModelProxy
from harness.curator.session import SessionConfig, run_session
from tests.curator_stand_in import StandIn
from tests.test_curator_sandbox import custodian  # noqa: F401 - the escape suite's real listeners
from tests.test_trace_projection import make_session
from tools import curator_shadow as shadow

ROOT = Path(__file__).resolve().parents[1]
INSTALLED = (shadow.HOST_DIR/'node_modules').is_dir() and shutil.which('node') is not None
native = pytest.mark.skipif(sys.platform != 'darwin' or not Path(sandbox.SANDBOX_EXEC).exists() or not INSTALLED,
                            reason='Seatbelt lane: macOS with the curator host installed (npm ci in tools/curator_host)')
PRICES = shadow.load_prices(shadow.DEFAULT_PRICES)
KEY = 'stand-in-provider-key'


def host_config(tmp_path: Path, arm='terra', **override):
    values = dict(effort='medium', max_requests=10, max_output_tokens=4096, request_timeout_seconds=30, wall_seconds=60,
                  max_context_images=4, context_image_block=2, workbench_timeout_seconds=30, budget_usd=1.0)
    values.update(override)
    config = shadow.host_configuration(shadow.ARMS[arm], PRICES, **values)
    directory = (tmp_path/'host-config').resolve()
    directory.mkdir(exist_ok=True)
    path = directory/f'{arm}.json'
    path.write_text(json.dumps(config))
    return config, path, directory


def session_config(tmp_path, upstream, *, cap='1', arm='terra', argv=None, **override):
    tools = shadow.host_tools()
    config, path, directory = host_config(tmp_path, arm, **override)
    proxy = ModelProxy(provider=OPENROUTER, upstream=upstream, key=KEY, prices={shadow.ARMS[arm].model: PRICES[shadow.ARMS[arm].model]},
                       cap_usd=Decimal(cap), ledger=tmp_path/'proxy-ledger.jsonl', max_output_tokens=4096)
    port = proxy.start()
    return proxy, SessionConfig(argv=argv or shadow.host_argv(tools, path), tools=(*tools['roots'], directory), limits=sandbox.Limits(wall_seconds=90),
                                proxy=proxy, proxy_port=port, extra_env=tools['env'],
                                host=shadow.host_identity(tools, config))


@pytest.fixture
def world(tmp_path):
    return Repository(tmp_path/'knowledge', 'testgame'), [make_session(tmp_path/'evidence')]


def events(record_dir: Path):
    return shadow._lines(record_dir/'host-output.log')


# ---------------------------------------------------------------- the host through the proxy and the sandbox
@native
def test_a_scripted_session_runs_through_the_proxy_and_the_sandbox_and_is_gated(tmp_path, world):
    repo, trace = world
    with StandIn() as stand_in:
        proxy, config = session_config(tmp_path, stand_in.url)
        try:
            record = run_session(repo, trace, config)
            spent, revoked, breaches = proxy.spent, proxy.revoked, proxy.breaches
        finally:
            proxy.close()
    life = record['manifest']['lifecycle']
    log = repo.state/'sessions'/record['manifest']['id']
    assert life['state'] == 'sealed' and life['returncode'] == 0 and life['stopped'] is None, (life, (log/'host-output.log').read_text())
    # A valid submission reached the gate and was published; the draft was kept.
    assert [v['accepted'] for v in record['verdicts']] == [True] and record['published_after'] == 'v1'
    assert [f['statement'] for f in repo.facts('v1')] == ['stand-in statement']
    assert record['drafts']['created'] == ['notes']
    # Every request passed the proxy's allowlist; the provider saw only the proxy's key.
    ledger = shadow._lines(tmp_path/'proxy-ledger.jsonl')
    assert len(ledger) == len(stand_in.requests) == 3
    assert all(not row.get('refused') and row['status'] == 200 and not row['usage_missing'] for row in ledger)
    assert all(request['headers']['authorization'] == f'Bearer {KEY}' for request in stand_in.requests)
    assert spent == Decimal('0.0036') and not revoked and breaches == 0
    # What the host sent: the frozen route and tools, and the frame as an inline image.
    first = stand_in.requests[0]['body']
    assert first['model'] == 'openai/gpt-6.1-terra' and first['max_completion_tokens'] == 4096
    assert first['provider'] == dict(only=['openai'], order=['openai'], allow_fallbacks=False, require_parameters=True)
    assert first['reasoning'] == {'effort': 'medium'} and 'service_tier' not in first and 'max_tokens' not in first
    assert [t['function']['name'] for t in first['tools']] == ['list_dir', 'read_file', 'view_frame', 'write_file', 'run_workbench', 'finish']
    assert 'data:image/png;base64,' in json.dumps(stand_in.requests[2]['body'])
    # Telemetry: every tool outcome, token usage and cost; never the session token or the key.
    rows = events(log)
    calls = [(r['name'], r['ok']) for r in rows if r['type'] == 'tool-call']
    assert calls == [('read_file', True), ('list_dir', True), ('read_file', True), ('view_frame', True), ('run_workbench', True),
                     ('write_file', True), ('write_file', True), ('read_file', False), ('finish', True)]
    ends = [r for r in rows if r['type'] == 'request-end']
    assert [(r['prompt_tokens'], r['completion_tokens'], r['cached_tokens'], r['reasoning_tokens'], r['cost']) for r in ends] == \
        [(1000, 40, 0, 10, 0.0012), (1100, 40, 800, 10, 0.0012), (1200, 40, 800, 10, 0.0012)]
    assert rows[0]['type'] == 'host-start' and rows[-1]['type'] == 'host-end' and rows[-1]['ok'] is True
    text = (log/'host-output.log').read_text()
    assert proxy.token not in text and KEY not in text
    for artifact in log.rglob('*'):
        if artifact.is_file():
            assert proxy.token.encode() not in artifact.read_bytes() and KEY.encode() not in artifact.read_bytes()


@native
def test_the_opus_arm_passes_the_same_allowlist_with_anthropic_cache_markers(tmp_path, world):
    repo, trace = world
    with StandIn() as stand_in:
        proxy, config = session_config(tmp_path, stand_in.url, arm='opus')
        try:
            record = run_session(repo, trace, config)
        finally:
            proxy.close()
    assert record['manifest']['lifecycle']['state'] == 'sealed' and record['published_after'] == 'v1'
    ledger = shadow._lines(tmp_path/'proxy-ledger.jsonl')
    assert len(ledger) == len(stand_in.requests) == 3 and all(not row.get('refused') and row['status'] == 200 for row in ledger)
    first = stand_in.requests[0]['body']
    assert first['model'] == 'anthropic/claude-opus-5.5' and first['provider']['only'] == ['anthropic']
    assert first['reasoning'] == {'effort': 'medium'} and first['max_completion_tokens'] == 4096
    assert 'cache_control' in json.dumps(first['messages'])  # Pi's Anthropic-style cache markers, which the proxy allows
    assert set(first) <= OPENROUTER.fields


@native
def test_the_host_cannot_read_or_write_outside_the_workspace(tmp_path, world):
    repo, trace = world
    secret = tmp_path/'planted-secret.txt'
    secret.write_text('planted secret value')
    with StandIn(attack=str(secret)) as stand_in:
        proxy, config = session_config(tmp_path, stand_in.url)
        try:
            record = run_session(repo, trace, config)
        finally:
            proxy.close()
    log = repo.state/'sessions'/record['manifest']['id']
    rows = events(log)
    calls = [(r['name'], r['ok'], r.get('error', '')) for r in rows if r['type'] == 'tool-call']
    assert [(name, ok) for name, ok, _ in calls[:6]] == [('read_file', False), ('write_file', False), ('write_file', False),
                                                         ('write_file', False), ('list_dir', False), ('read_file', False)]
    assert 'planted secret value' not in (log/'host-output.log').read_text()
    assert not Path('/tmp/curator-escape').exists() and secret.read_text() == 'planted secret value'
    assert record['published_after'] == 'v0'
    # The refusals above were the host's own. The sandbox refuses the same attempts made by the node process itself.
    probe = ("const fs=require('fs'),r={};"
             "for(const [k,p] of Object.entries({secret:process.argv[1],cred:process.argv[2]})){try{fs.readFileSync(p);r[k]='read'}catch(e){r[k]=e.code}}"
             "for(const [k,p] of Object.entries({knowledge:'knowledge/x',trace:'trace/x',tmp:'/tmp/curator-node-escape'})){try{fs.writeFileSync(p,'x');r['w'+k]='wrote'}catch(e){r['w'+k]=e.code}}"
             "try{fs.writeFileSync('scratch/ok','x');r.scratch='wrote'}catch(e){r.scratch=e.code}"
             "console.log('PROBE '+JSON.stringify(r))")
    tools = shadow.host_tools()
    planted_credentials = tmp_path/'runtime-like'/'credentials.json'
    planted_credentials.parent.mkdir()
    planted_credentials.write_text('{"key": "planted"}')
    probing = SessionConfig(argv=(str(tools['python']), '-I', str(shadow.HOST_DIR/'launch.py'), str(tools['node']), '-e', probe,
                                  str(secret), str(planted_credentials)),
                            tools=tools['roots'], limits=sandbox.Limits(wall_seconds=60), extra_env=tools['env'])
    record = run_session(repo, trace, probing)
    out = (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()
    result = json.loads(out.split('PROBE ')[1].splitlines()[0])
    assert result == dict(secret='EPERM', cred='EPERM', wknowledge='EPERM', wtrace='EPERM', wtmp='EPERM', scratch='wrote'), out
    assert not Path('/tmp/curator-node-escape').exists()


@native
def test_the_escape_suite_still_passes_with_the_curator_hosts_tool_roots(tmp_path, monkeypatch, custodian):  # noqa: F811
    """tests/curator_adversary.py through tests/test_curator_sandbox.py's real-listener suite, with node, its libraries,
    the host package and the config directory added to the layout. The suite's own assertion is that only the
    five controls are allowed."""
    from tests import test_curator_sandbox as suite

    tools = shadow.host_tools()
    original = suite.make_layout

    def with_host(base):
        layout = original(base)
        return sandbox.Layout(workspace=layout.workspace, home=layout.home, writable=layout.writable,
                              tools=(*layout.tools, *tools['roots']))

    monkeypatch.setattr(suite, 'make_layout', with_host)
    suite.test_escape_suite_against_real_listeners(tmp_path, custodian)


@native
def test_the_footprint_is_recorded_for_the_documentation(tmp_path, world, capsys):
    repo, trace = world
    with StandIn() as stand_in:
        proxy, config = session_config(tmp_path, stand_in.url)
        try:
            record = run_session(repo, trace, config)
        finally:
            proxy.close()
    provenance = record['manifest']['provenance']
    digest = shadow.telemetry(events(repo.state/'sessions'/record['manifest']['id']))
    with capsys.disabled():
        print(f"\ncurator host footprint: seconds={provenance['seconds']} peak_memory_mb={provenance['peak_memory_bytes'] >> 20} "
              f"time_to_first_request={digest['time_to_first_request_seconds']}")
    assert record['manifest']['lifecycle']['survivors'] == []
    assert provenance['peak_memory_bytes'] < sandbox.Limits().memory_bytes


# ---------------------------------------------------------------- the shadow runner
def synthetic_evidence(root: Path, lineage='397', names=('sd1a1',)) -> Path:
    evidence = root/'evidence'
    for name in names:
        make_session(evidence/shadow.LINEAGES[lineage]['directory']/'computer-sessions', name)
    return evidence


def run_cli(tmp_path, upstream, *extra, names=('sd1a1',), monkeypatch=None, key=KEY, lineage='397'):
    runtime = tmp_path/'runtime'
    evidence = synthetic_evidence(tmp_path, lineage, names)
    assert monkeypatch is not None
    monkeypatch.setenv(shadow.KEY_VARIABLE, key)
    out = runtime/'curator-shadow'/'dry-run'
    code = shadow.main(['--arm', 'terra', '--lineage', lineage, '--sessions', *names, '--cap-usd', '1', '--upstream', upstream,
                        '--runtime-root', str(runtime), '--evidence-root', str(evidence), '--out', str(out),
                        '--max-output-tokens', '4096', '--wall-seconds', '120', *extra])
    return code, out, runtime


def test_the_runner_refuses_held_out_and_unsampled_names(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(shadow.KEY_VARIABLE, KEY)
    out = tmp_path/'runtime'/'curator-shadow'/'x'
    base = ['--arm', 'terra', '--cap-usd', '1', '--runtime-root', str(tmp_path/'runtime'), '--out', str(out)]
    for lineage, sessions in (('lh1', []), ('lh2', []), ('lh3', []), ('372-382-dev-loop', []), ('397', ['lh1a1']), ('397', ['sd1a1', 'lh3a2']),
                              ('372', ['lh2a1']), ('372', ['aidA1']), ('397', ['sd1a9']), ('372', ['sd1a1'])):
        code = shadow.main([*base, '--lineage', lineage, *(['--sessions', *sessions] if sessions else [])])
        message = capsys.readouterr().err
        assert code == 2 and 'curator_shadow:' in message, (lineage, sessions)
        assert not out.exists()
    assert shadow.select('372', ['aidA5', 'aidB3'])[1] == ['aidB3', 'aidA5']  # lineage order, not request order
    assert shadow.select('397', None)[1] == [f'sd1a{n}' for n in range(1, 8)]


@pytest.fixture(autouse=True)
def no_keychain(monkeypatch):
    """The runner falls back to the operator's keychain map; tests never reach a real keychain."""
    seen = []

    def stub(name, *, mapping):
        seen.append(mapping)
        return os.environ.get(name) or None

    monkeypatch.setattr(shadow, 'credential', stub)
    return seen


def test_the_key_map_is_looked_up_under_the_runtime_root(tmp_path, monkeypatch, no_keychain):
    monkeypatch.delenv(shadow.KEY_VARIABLE, raising=False)
    shadow.main(['--arm', 'terra', '--lineage', '397', '--cap-usd', '1', '--runtime-root', str(tmp_path/'rt'),
                 '--out', str(tmp_path/'rt'/'curator-shadow'/'x')])
    assert no_keychain == [tmp_path/'rt'/'credentials.json']


def test_the_runner_needs_the_key_in_its_variable_and_only_loopback_or_openrouter(tmp_path, monkeypatch, capsys):
    base = ['--arm', 'terra', '--lineage', '397', '--cap-usd', '1', '--runtime-root', str(tmp_path/'runtime'),
            '--out', str(tmp_path/'runtime'/'curator-shadow'/'x')]
    monkeypatch.delenv(shadow.KEY_VARIABLE, raising=False)
    assert shadow.main(base) == 2 and shadow.KEY_VARIABLE in capsys.readouterr().err
    monkeypatch.setenv(shadow.KEY_VARIABLE, KEY)
    for upstream in ('https://example.com', 'http://192.168.0.5:80', 'http://127.0.0.1.evil.example:80'):
        assert shadow.main([*base, '--upstream', upstream]) == 2
        assert 'upstream' in capsys.readouterr().err
    assert shadow.main([*base[:-1], str(tmp_path/'elsewhere')]) == 2 and 'inside' in capsys.readouterr().err


def test_tool_roots_that_expose_the_disk_home_or_runtime_are_refused():
    for broad in (Path('/'), Path.home().resolve(), shadow.ROOT.resolve(), shadow.ROOT.resolve()/'.runtime',
                  shadow.ROOT.resolve()/'.runtime'/'evidence'):
        with pytest.raises(shadow.ShadowError, match='too much'):
            shadow.refuse_broad_root(broad)
    shadow.refuse_broad_root(shadow.HOST_DIR.resolve())          # the host package itself is fine
    shadow.refuse_broad_root(Path(sys.base_prefix).resolve())


@pytest.mark.skipif(not INSTALLED, reason='needs npm ci in tools/curator_host')
def test_the_hosts_node_unit_tests_pass():
    done = subprocess.run([shutil.which('node'), '--test', *sorted(str(p) for p in (shadow.HOST_DIR/'test').glob('*.test.mjs'))],
                          cwd=shadow.HOST_DIR, capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]


def test_the_prompt_states_the_gate_and_carries_no_game_knowledge():
    prompt = (shadow.HOST_DIR/'prompt.md').read_text()
    for needed in ('curator-submission/1', 'curator-fact/1', 'curator-type/1', 'add_fact', 'supersede_fact', 'add_type', 'base_version',
                   'from_drafts', 'submissions/', 'drafts/', 'scratch/', 'view_frame', 'run_workbench', 'finish', '256 KiB', '200'):
        assert needed in prompt, needed
    # P-GENERALITY and the blinding of #449 probes: nothing about the game, its items or the recorded runs.
    lowered = prompt.lower()
    for forbidden in ('cdda', 'cataclysm', 'dark days', 'zombie', 'survivor', 'evacuee', 'scenario', 'seven-day', '397', '372', '382',
                      'terra', 'opus', 'probe set', 'held-out', 'sd1a', 'lh1'):
        assert forbidden not in lowered, forbidden


def test_the_frozen_prices_cover_exactly_the_two_arms():
    assert sorted(PRICES) == sorted(arm.model for arm in shadow.ARMS.values())
    terra, opus = PRICES['openai/gpt-6.1-terra'], PRICES['anthropic/claude-opus-5.5']
    assert (terra.input, terra.output, terra.cache_read, terra.cache_write) == (Decimal(1), Decimal(5), Decimal('0.05'), Decimal('1.25'))
    assert (opus.input, opus.output, opus.cache_read, opus.cache_write) == (Decimal(4), Decimal(20), Decimal('0.2'), Decimal(8))
    data = json.loads(shadow.DEFAULT_PRICES.read_text())
    assert data['source'] == 'https://openrouter.ai/api/v1/models' and data['fetched'] == '2026-11-08'


def test_both_arms_configure_a_host_the_proxy_allows():
    for arm in shadow.ARMS.values():
        config = shadow.host_configuration(arm, PRICES, effort=arm.effort, max_requests=5, max_output_tokens=4096,
                                           request_timeout_seconds=30, wall_seconds=60, max_context_images=4,
                                           context_image_block=2, workbench_timeout_seconds=30, budget_usd=1.0)
        assert config['model']['compat']['maxTokensField'] == 'max_completion_tokens'
        assert config['model']['compat']['openRouterRouting']['only'] == [arm.provider]
        script = ("import {validateConfiguration} from './host.mjs';"
                  "validateConfiguration(JSON.parse(process.argv[1]));console.log('valid')")
        if INSTALLED:
            done = subprocess.run(['node', '--input-type=module', '-e', script, json.dumps(config)], cwd=shadow.HOST_DIR,
                                  capture_output=True, text=True)
            assert done.stdout.strip() == 'valid', done.stderr


SUMMARY_FIELDS = {'schema', 'kind', 'arm', 'model', 'effort', 'lineage', 'trace_session', 'memory', 'cap_usd', 'started_wall',
                  'run_state', 'wall_seconds', 'cost_usd', 'proxy', 'stopped_by_cap', 'session_id', 'record', 'session_state',
                  'sandbox', 'errors', 'refused', 'submissions', 'accepted', 'rejected', 'verdicts', 'drafts', 'published_after',
                  'requests', 'time_to_first_request_seconds', 'first_request_prompt_tokens', 'tokens', 'host_reported_cost_usd',
                  'tool_calls', 'host_end', 'model_status', 'host_budget_usd', 'published_before'}


@native
def test_a_dry_run_writes_a_complete_summary_per_session_and_per_run(tmp_path, monkeypatch):
    with StandIn() as stand_in:
        code, out, runtime = run_cli(tmp_path, stand_in.url, monkeypatch=monkeypatch)
    assert code == 0
    session = json.loads((out/'397'/'sd1a1'/'summary.json').read_text())
    assert set(session) == SUMMARY_FIELDS, set(session) ^ SUMMARY_FIELDS
    assert session['schema'] == 'curator-shadow/1' and session['kind'] == 'session' and session['session_state'] == 'sealed'
    assert session['cost_usd'] == '0.0036' and session['requests'] == 3 and session['first_request_prompt_tokens'] == 1000
    assert session['tokens'] == dict(prompt=3300, completion=120, cached=1600, cache_write=0, reasoning=30)
    assert session['proxy'] == dict(revoked=False, breaches=0, entries=3, refusals=0, refusal_reasons=[], forwarded=3,
                                    cap_refused=False, usage_missing=0)
    assert session['stopped_by_cap'] is False and session['submissions'] == 1 and (session['accepted'], session['rejected']) == (1, 0)
    assert session['verdicts'][0]['accepted'] and session['drafts']['created'] == ['notes']
    assert session['tool_calls']['by_name']['write_file'] == 2 and session['tool_calls']['failed'] == 1
    assert session['time_to_first_request_seconds'] > 0 and session['host_end'] == dict(reason='finished', ok=True)
    assert session['memory']['passed'] is False and Path(session['record']).is_dir()
    run = json.loads((out/'summary.json').read_text())
    assert run['schema'] == 'curator-shadow/1' and run['kind'] == 'run' and run['complete'] is True and run['stopped'] is None
    assert run['total_cost_usd'] == '0.0036' and run['published_version'] == 'v1' and run['sessions_run'] == 1
    # Each run has its own fresh repository, named by its output directory.
    assert (runtime/'knowledge'/'shadow-454'/'dry-run'/'terra'/'397'/'cdda').is_dir()
    assert json.loads((out/'397'/'sd1a1'/'summary.json').read_text())['published_before'] == 'v0'
    assert KEY not in ''.join(p.read_text(errors='replace') for p in out.rglob('*') if p.is_file())
    assert [r['status'] for r in shadow._lines(out/'397'/'sd1a1'/'proxy-ledger.jsonl')] == [200, 200, 200]


@native
def test_the_run_stops_when_the_cap_is_reached(tmp_path, monkeypatch):
    # Each request reserves its body at the highest input price plus 4,096 output tokens, about $0.03, and settles at
    # $0.02: against a $0.045 cap the first is admitted and the second refused.
    with StandIn(cost=0.02) as stand_in:
        runtime = tmp_path/'runtime'
        evidence = synthetic_evidence(tmp_path, '397', ('sd1a1', 'sd1a2'))
        monkeypatch.setenv(shadow.KEY_VARIABLE, KEY)
        out = runtime/'curator-shadow'/'cap'
        code = shadow.main(['--arm', 'terra', '--lineage', '397', '--sessions', 'sd1a1', 'sd1a2', '--cap-usd', '0.045', '--upstream', stand_in.url, '--runtime-root', str(runtime),
                            '--evidence-root', str(evidence), '--out', str(out), '--max-output-tokens', '4096', '--wall-seconds', '120'])
    assert code == 0
    run = json.loads((out/'summary.json').read_text())
    first = json.loads((out/'397'/'sd1a1'/'summary.json').read_text())
    assert run['stopped'] == 'cap-reached' and run['sessions_run'] == 1 and not (out/'397'/'sd1a2').exists()
    assert first['stopped_by_cap'] is True and 'spend cap reached' in first['proxy']['refusal_reasons']
    assert Decimal(run['total_cost_usd']) == Decimal('0.02') <= Decimal('0.045')
    assert first['session_state'] == 'aborted' and first['host_end'] == dict(reason='provider-error', ok=False)
    assert first['model_status'] == [200, 429] and first['published_after'] == 'v0' and first['submissions'] == 0


@native
def test_a_revoked_proxy_stops_the_run(tmp_path, monkeypatch):
    with StandIn(mode='no-usage') as stand_in:
        runtime = tmp_path/'runtime'
        evidence = synthetic_evidence(tmp_path, '397', ('sd1a1', 'sd1a2'))
        monkeypatch.setenv(shadow.KEY_VARIABLE, KEY)
        out = runtime/'curator-shadow'/'revoked'
        code = shadow.main(['--arm', 'terra', '--lineage', '397', '--sessions', 'sd1a1', 'sd1a2', '--cap-usd', '1', '--upstream', stand_in.url, '--runtime-root', str(runtime),
                            '--evidence-root', str(evidence), '--out', str(out), '--max-output-tokens', '4096', '--wall-seconds', '120'])
    assert code == 0
    run = json.loads((out/'summary.json').read_text())
    first = json.loads((out/'397'/'sd1a1'/'summary.json').read_text())
    assert run['stopped'] == 'proxy-revoked' and run['sessions_run'] == 1 and first['proxy']['revoked'] is True
    assert first['proxy']['usage_missing'] == 1 and not (out/'397'/'sd1a2').exists()
    assert os.path.exists(out/'summary.json')
