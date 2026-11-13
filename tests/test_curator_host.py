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
import re
import shutil
import subprocess
import sys

import pytest

from harness.curator import sandbox
from harness.curator.knowledge import Repository
from harness.curator.proxy import ModelProxy
from harness.curator.session import SessionConfig, run_session
from tests.curator_stand_in import StandIn
from tests.curator_trace import make_long_session
from tests.test_curator_sandbox import custodian  # noqa: F401 - the escape suite's real listeners
from tests.test_trace_projection import make_session
from tools.curator_host import shadow
from tools.curator_host.providers import OPENROUTER

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
    assert first['reasoning'] == {'effort': 'medium'} and first['service_tier'] == 'default' and 'max_tokens' not in first
    assert all(request['body']['service_tier'] == 'default' for request in stand_in.requests)
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
    assert rows[0]['requested_service_tier'] == 'default'
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
             "for(const [k,p] of Object.entries({secret:process.argv[1],cred:process.argv[2],providers:process.argv[3],runner:process.argv[4],host:process.argv[5],prompt:process.argv[6]})){try{fs.readFileSync(p);r[k]='read'}catch(e){r[k]=e.code}}"
             "for(const [k,p] of Object.entries({knowledge:'knowledge/x',trace:'trace/x',tmp:'/tmp/curator-node-escape'})){try{fs.writeFileSync(p,'x');r['w'+k]='wrote'}catch(e){r['w'+k]=e.code}}"
             "try{fs.writeFileSync('scratch/ok','x');r.scratch='wrote'}catch(e){r.scratch=e.code}"
             "console.log('PROBE '+JSON.stringify(r))")
    tools = shadow.host_tools()
    planted_credentials = tmp_path/'runtime-like'/'credentials.json'
    planted_credentials.parent.mkdir()
    planted_credentials.write_text('{"key": "planted"}')
    probing = SessionConfig(argv=(str(tools['python']), '-I', str(shadow.HOST_DIR/'launch.py'), str(tools['node']), '-e', probe,
                                  str(secret), str(planted_credentials), str(shadow.HOST_DIR/'providers.py'),
                                  str(shadow.HOST_DIR/'shadow.py'), str(shadow.HOST_DIR/'host.mjs'),
                                  str(shadow.HOST_DIR/'prompt.md')),
                            tools=tools['roots'], limits=sandbox.Limits(wall_seconds=60), extra_env=tools['env'])
    record = run_session(repo, trace, probing)
    out = (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()
    result = json.loads(out.split('PROBE ')[1].splitlines()[0])
    # The host package's Python (providers, runner) is out of the curator's reach; the Node host and prompt are in.
    assert result == dict(secret='EPERM', cred='EPERM', providers='EPERM', runner='EPERM', host='read', prompt='read',
                          wknowledge='EPERM', wtrace='EPERM', wtmp='EPERM', scratch='wrote'), out
    assert not Path('/tmp/curator-node-escape').exists()


def test_the_readable_host_files_hold_no_python_but_the_launcher():
    host = shadow.HOST_DIR.resolve()
    inside = [(host/name).resolve() for name in shadow.HOST_READABLE]
    assert host not in inside and all(host in root.parents for root in inside)
    files = [f for root in inside for f in ([root] if root.is_file() else root.rglob('*'))]
    assert [f for f in files if f.suffix == '.py'] == [host/'launch.py']
    assert not [f for f in files if '__pycache__' in f.parts]


@native
def test_the_sandbox_reads_exactly_the_readable_host_files():
    tools = shadow.host_tools()  # needs the macOS loader tools to find node's libraries
    host = shadow.HOST_DIR.resolve()
    inside = [Path(root) for root in tools['roots'] if Path(root) == host or host in Path(root).parents]
    assert sorted(p.name for p in inside) == sorted(shadow.HOST_READABLE)
    # No host-package Python besides the launcher is on any root, including a root that contains the package.
    for name in ('shadow.py', 'providers.py'):
        assert not any(Path(root) == host/name or Path(root) in (host, *host.parents) for root in tools['roots']), name


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
    for lineage, sessions in (('lh4', None), ('397', ['lh4b1']), ('372', ['lh4b2'])):   # #522's held-out lineage
        with pytest.raises(shadow.ShadowError, match='held-out'):
            shadow.select(lineage, sessions)
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
    for needed in ('curator-submission/1', 'curator-fact/2', 'curator-type/1', 'add_fact', 'supersede_fact', 'add_type', 'base_version',
                   'from_drafts', 'submissions/', 'drafts/', 'scratch/', 'view_frame', 'run_workbench', 'finish', '256 KiB', '200'):
        assert needed in prompt, needed
    # P-GENERALITY and the blinding of #449 probes: nothing about the game, its items or the recorded runs.
    lowered = prompt.lower()
    for forbidden in ('cdda', 'cataclysm', 'dark days', 'zombie', 'survivor', 'evacuee', 'scenario', 'seven-day', '397', '372', '382',
                      'terra', 'opus', 'probe set', 'held-out', 'sd1a', 'lh1'):
        assert forbidden not in lowered, forbidden
    # The brief gate is honest only if the prompt names none of the four facts it looks for (#460).
    assert not re.search(r'\b(tanks?|rations?|rods?|batter(y|ies)|roofs?)\b', lowered)


def test_the_prompt_defines_the_four_fact_kinds_and_the_new_fields():
    prompt = (shadow.HOST_DIR/'prompt.md').read_text()
    for needed in ('place_with_goods', 'hazard', 'open_commitment', 'how_it_works', '`subject`', '`place`', '`game_time`',
                   'One fact per item', 'coverage.json'):
        assert needed in prompt, needed


def test_the_frozen_prices_cover_exactly_the_two_arms():
    assert sorted(PRICES) == sorted(arm.model for arm in shadow.ARMS.values())
    terra, opus = PRICES['openai/gpt-6.1-terra'], PRICES['anthropic/claude-opus-5.5']
    assert (terra.input, terra.output, terra.cache_read, terra.cache_write) == (Decimal(2), Decimal('7.5'), Decimal('0.1'), Decimal('2.5'))
    assert (opus.input, opus.output, opus.cache_read, opus.cache_write) == (Decimal(4), Decimal(20), Decimal('0.2'), Decimal(8))
    data = json.loads(shadow.DEFAULT_PRICES.read_text())
    assert data['source'] == 'https://openrouter.ai/api/v1/models' and data['fetched'] == '2026-11-08'


@pytest.mark.parametrize('tier,field,value', [
    (None, 'input', '-1'), (None, 'output', 'NaN'), (None, 'cache_read', 'Infinity'),
    (None, 'cache_write', 'invalid'), (None, 'input', 1),
    ('long_prompt', 'input', '-1'), ('long_prompt', 'output', 'sNaN'),
    ('long_prompt', 'min_prompt_tokens', True), ('long_prompt', 'min_prompt_tokens', 0),
    ('long_prompt', 'unexpected', '1'),
])
def test_invalid_price_components_and_tiers_are_refused(tmp_path, tier, field, value):
    data = json.loads(shadow.DEFAULT_PRICES.read_text())
    row = data['models']['openai/gpt-6.1-terra']
    (row[tier] if tier else row)[field] = value
    path = tmp_path/'prices.json'
    path.write_text(json.dumps(data))
    with pytest.raises(shadow.ShadowError):
        shadow.load_prices(path)


@pytest.mark.parametrize('tier', [None, [], {}, {'min_prompt_tokens': 272000, 'input': '2'}])
def test_a_present_long_prompt_tier_must_be_complete(tmp_path, tier):
    data = json.loads(shadow.DEFAULT_PRICES.read_text())
    data['models']['openai/gpt-6.1-terra']['long_prompt'] = tier
    path = tmp_path/'prices.json'
    path.write_text(json.dumps(data))
    with pytest.raises(shadow.ShadowError):
        shadow.load_prices(path)


def test_each_price_component_is_bounded_independently(tmp_path):
    data = json.loads(shadow.DEFAULT_PRICES.read_text())
    tier = data['models']['openai/gpt-6.1-terra']['long_prompt']
    tier.update(input='0.5', cache_write='0')
    path = tmp_path/'prices.json'
    path.write_text(json.dumps(data))
    price = shadow.load_prices(path)['openai/gpt-6.1-terra']
    assert (price.input, price.output, price.cache_read, price.cache_write) == (
        Decimal(1), Decimal('7.5'), Decimal('0.1'), Decimal('1.25'))


def test_long_prompt_prices_bound_reservation_and_fallback_without_repricing_reported_cost(tmp_path):
    model = 'openai/gpt-6.1-terra'
    price = PRICES[model]
    usage = dict(prompt_tokens=280000, completion_tokens=16384)
    response = json.dumps(dict(usage=usage)).encode()
    fallback = OPENROUTER.cost(price, usage, response)
    standard_long_charge = (280000 * Decimal(2) + 16384 * Decimal('7.5')) / Decimal(1000000)
    assert fallback == Decimal('0.82288') >= standard_long_charge == Decimal('0.68288')
    proxy = ModelProxy(provider=OPENROUTER, upstream='http://127.0.0.1:1', key=KEY, prices=PRICES,
                       cap_usd=Decimal(2), ledger=tmp_path/'ledger.jsonl', max_output_tokens=16384)
    request = json.dumps(dict(messages=[dict(role='user', content='x' * 280000)])).encode()
    assert proxy._reserve(model, request, 16384) >= fallback
    # Reported actual fees remain authoritative, even for a base-tier response.
    assert OPENROUTER.cost(price, usage, json.dumps(dict(usage=dict(usage, cost=0.01))).encode()) == Decimal('0.01')


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


SUMMARY_FIELDS = {'window', 'coverage', 'schema', 'kind', 'arm', 'model', 'effort', 'lineage', 'trace_session', 'memory', 'cap_usd', 'started_wall',
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
    proxy = dict(session['proxy'])
    assert Decimal(proxy.pop('pending_reserved_usd')) == 0
    assert Decimal(proxy.pop('max_reserved_usd')) > 0 and proxy.pop('charged_usd') == '0.0036'
    assert proxy == dict(revoked=False, breaches=0, entries=3, refusals=0, refusal_reasons=[], forwarded=3,
                         cap_refused=False, usage_missing=0, settled=True, unsettled_requests=0, receipt_error=None)
    closure = json.loads((out/'397/sd1a1/proxy-close.json').read_text())
    assert closure['schema'] == 'curator-proxy-close/1' and closure['settled']
    assert closure['spent_snapshot_usd'] == session['cost_usd']
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


def run_windows(tmp_path, upstream, windows, monkeypatch, *extra, out_name='windows', steps=12):
    runtime = tmp_path/'runtime'
    evidence = tmp_path/'evidence'
    if not (evidence/shadow.LINEAGES['397']['directory']).exists():
        make_long_session(evidence/shadow.LINEAGES['397']['directory']/'computer-sessions', 'sd1a1', steps=steps)
    monkeypatch.setenv(shadow.KEY_VARIABLE, KEY)
    listing = tmp_path/'windows.json'
    listing.write_text(json.dumps(windows))
    out = runtime/'curator-shadow'/out_name
    code = shadow.main(['--arm', 'terra', '--lineage', '397', '--windows-file', str(listing), '--cap-usd', '1',
                        '--upstream', upstream, '--runtime-root', str(runtime), '--evidence-root', str(evidence),
                        '--out', str(out), '--max-output-tokens', '4096', '--wall-seconds', '120', *extra])
    return code, out, runtime


@native
def test_a_window_run_goes_through_the_stand_in_one_window_after_another_on_one_repository(tmp_path, monkeypatch):
    windows = [dict(session='sd1a1', actor='001', first=1, last=4, game_time='day 1 08:00'),
               dict(session='sd1a1', actor='001', first=5, last=8)]
    with StandIn() as stand_in:
        code, out, runtime = run_windows(tmp_path, stand_in.url, windows, monkeypatch)
    assert code == 0
    first = json.loads((out/'397'/'sd1a1-001-1-4'/'summary.json').read_text())
    second = json.loads((out/'397'/'sd1a1-001-5-8'/'summary.json').read_text())
    assert first['window'] == dict(session='sd1a1', actor='001', first=1, last=4, game_time='day 1 08:00')
    assert first['session_state'] == 'sealed' and (first['accepted'], first['rejected']) == (1, 0)
    assert first['coverage'] == dict(schema='curator-coverage/1', session='sd1a1', actor='001', last_step=4,
                                     game_time='day 1 08:00')
    assert first['published_before'] == 'v0' and second['published_before'] == 'v1'  # the store as the last left it
    assert second['coverage']['last_step'] == 8 and second['coverage']['game_time'] is None
    assert (second['accepted'], second['rejected']) == (0, 1)  # the stand-in repeats its fact id: the gate refuses it
    for summary in (first, second):
        assert summary['cost_usd'] == '0.0036' and summary['wall_seconds'] > 0 and summary['memory']['passed'] is False
    run = json.loads((out/'summary.json').read_text())
    assert run['complete'] is True and run['sessions_planned'] == ['sd1a1-001-1-4', 'sd1a1-001-5-8']
    assert run['windows'] == windows or [dict(w, game_time=w.get('game_time')) for w in windows] == run['windows']
    assert run['windows_sha256'] == shadow.windows_digest([shadow.Window.read(w) for w in windows])
    assert [(s['label'], s['cost_usd'], s['ledger_charged_usd'], s['stopped_by_cap']) for s in run['sessions']] == [
        ('sd1a1-001-1-4', '0.0036', '0.0036', False), ('sd1a1-001-5-8', '0.0036', '0.0036', False)]
    assert all(s['wall_seconds'] > 0 for s in run['sessions']) and run['total_cost_usd'] == '0.0072'
    repo = Repository(runtime/'knowledge'/'shadow-454'/'windows'/'terra'/'397', 'cdda')
    assert repo.published() == 'v1' and [f['id'] for f in repo.facts()] == ['f1']


def test_windows_are_one_list_written_two_ways_and_selected_with_the_runners_refusals(tmp_path):
    from argparse import Namespace
    plan = Namespace(windows_file=None, window_plan=['sd1a1', '001', '1', '20', '10'], sessions=None)
    windows = shadow.read_windows(plan)
    assert [(w.first, w.last) for w in windows] == [(n * 20 + 1, n * 20 + 20) for n in range(10)]
    listing = tmp_path/'w.json'
    listing.write_text(json.dumps([w.record() for w in windows]))
    assert shadow.read_windows(Namespace(windows_file=str(listing), window_plan=None, sessions=None)) == windows
    assert shadow.windows_digest(windows) == shadow.windows_digest(shadow.read_windows(Namespace(
        windows_file=str(listing), window_plan=None, sessions=None)))
    spec, units = shadow.select_units('397', None, windows)
    assert spec is shadow.LINEAGES['397'] and units[0] == ('sd1a1-001-1-20', 'sd1a1', windows[0]) and len(units) == 10
    assert shadow.read_windows(Namespace(windows_file=None, window_plan=None, sessions=None)) is None
    for bad in (Namespace(windows_file=str(listing), window_plan=['sd1a1', '001', '1', '20', '2'], sessions=None),
                Namespace(windows_file=None, window_plan=['sd1a1', '001', '1', '20', '2'], sessions=['sd1a1']),
                Namespace(windows_file=None, window_plan=['sd1a1', '001', '0', '20', '2'], sessions=None),
                Namespace(windows_file=None, window_plan=['sd1a1', '001', 'x', '20', '2'], sessions=None)):
        with pytest.raises(shadow.ShadowError):
            shadow.read_windows(bad)
    for held_out in ('lh1a1', 'lh4b1', 'sd1a9'):
        with pytest.raises(shadow.ShadowError):
            shadow.select_units('397', None, [shadow.Window(held_out, '001', 1, 2)])
    with pytest.raises(shadow.ShadowError, match='listed once'):
        shadow.select_units('397', None, [shadow.Window('sd1a1', '001', 1, 2)]*2)


def test_a_double_cap_run_names_one_session_and_needs_the_cap_it_doubles(tmp_path, monkeypatch, capsys):
    one = [dict(session='sd1a1', actor='001', first=1, last=4)]
    two = one + [dict(session='sd1a1', actor='001', first=5, last=8)]
    for windows, extra in ((two, ['--session-cap-usd', '0.5', '--double-session-cap']), (one, ['--double-session-cap'])):
        code, out, _ = run_windows(tmp_path, 'http://127.0.0.1:9', windows, monkeypatch, *extra)
        assert code == 2 and 'double-session-cap' in capsys.readouterr().err and not out.exists()


@native
def test_a_double_cap_rerun_applies_twice_the_cap_on_the_repository_it_continues(tmp_path, monkeypatch):
    one = [dict(session='sd1a1', actor='001', first=1, last=4)]
    with StandIn() as stand_in:
        code, out, runtime = run_windows(tmp_path, stand_in.url, one, monkeypatch, '--session-cap-usd', '0.25',
                                         out_name='first')
        assert code == 0
        root = runtime/'knowledge'/'shadow-454'/'first'/'terra'/'397'
        again, redo, _ = run_windows(tmp_path, stand_in.url, one, monkeypatch, '--session-cap-usd', '0.25',
                                     '--double-session-cap', '--knowledge-root', str(root), out_name='redo')
    assert again == 0
    first, second = (json.loads((path/'summary.json').read_text()) for path in (out, redo))
    assert (first['session_cap_usd'], first['session_cap_doubled'], first['published_before_run']) == ('0.25', False, 'v0')
    assert (second['session_cap_usd'], second['session_cap_doubled'], second['published_before_run']) == ('0.50', True, 'v1')
    assert json.loads((redo/'397'/'sd1a1-001-1-4'/'summary.json').read_text())['cap_usd'] == '0.50'
    assert second['knowledge_root'] == str(root.resolve())
    assert not (runtime/'knowledge'/'shadow-454'/'redo').exists()  # no fresh repository was made for the re-run
    bad, _, _ = run_windows(tmp_path, 'http://127.0.0.1:9', one, monkeypatch, '--knowledge-root',
                            str(tmp_path/'elsewhere'), out_name='elsewhere')
    assert bad == 2


@native
def test_an_upstream_429_retry_is_counted_and_recovers_through_the_real_proxy_and_sandbox(tmp_path, world):
    repo, trace = world
    with StandIn(mode='rate-limit-once') as stand_in:
        proxy, config = session_config(tmp_path, stand_in.url)
        try:
            record = run_session(repo, trace, config)
            spent, revoked, breaches = proxy.spent, proxy.revoked, proxy.breaches
        finally:
            proxy.close()
    life = record['manifest']['lifecycle']
    assert life['state'] == 'sealed' and life['survivors'] == [] and record['published_after'] == 'v1'
    ledger = shadow._lines(tmp_path/'proxy-ledger.jsonl')
    assert [r['status'] for r in ledger] == [429, 200, 200, 200]
    assert ledger[0]['usage_missing'] and ledger[0]['provider_refused'] and Decimal(ledger[0]['charged']) == 0
    assert spent == sum(Decimal(r['charged']) for r in ledger) and not revoked and breaches == 0
    assert stand_in.requests[0]['body'] == stand_in.requests[1]['body']
    log = repo.state/'sessions'/record['manifest']['id']
    telemetry = shadow.telemetry(events(log))
    assert telemetry['requests'] == 4 and telemetry['host_end'] == dict(reason='finished', ok=True)
    assert len([e for e in events(log) if e.get('retry')]) == 1


@native
def test_an_upstream_retry_veto_survives_the_real_proxy(tmp_path, world):
    repo, trace = world
    with StandIn(mode='rate-limit-veto') as stand_in:
        proxy, config = session_config(tmp_path, stand_in.url)
        try:
            record = run_session(repo, trace, config)
        finally:
            proxy.close()
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and life['survivors'] == [] and record['published_after'] == 'v0'
    assert len(stand_in.requests) == 1
    ledger = shadow._lines(tmp_path/'proxy-ledger.jsonl')
    assert len(ledger) == 1 and ledger[0]['status'] == 429 and ledger[0]['usage_missing']
    log = repo.state/'sessions'/record['manifest']['id']
    assert not [e for e in events(log) if e.get('retry')]


@native
def test_the_run_stops_when_the_cap_is_reached(tmp_path, monkeypatch):
    # Tier bounds reserve about $0.06 for the first body plus 4,096 output tokens, then settle at
    # $0.02: against a $0.075 cap the first is admitted and the larger second request refused.
    with StandIn(cost=0.02) as stand_in:
        runtime = tmp_path/'runtime'
        evidence = synthetic_evidence(tmp_path, '397', ('sd1a1', 'sd1a2'))
        monkeypatch.setenv(shadow.KEY_VARIABLE, KEY)
        out = runtime/'curator-shadow'/'cap'
        code = shadow.main(['--arm', 'terra', '--lineage', '397', '--sessions', 'sd1a1', 'sd1a2', '--cap-usd', '0.075', '--upstream', stand_in.url, '--runtime-root', str(runtime),
                            '--evidence-root', str(evidence), '--out', str(out), '--max-output-tokens', '4096', '--wall-seconds', '120'])
    assert code == 0
    run = json.loads((out/'summary.json').read_text())
    first = json.loads((out/'397'/'sd1a1'/'summary.json').read_text())
    assert run['stopped'] == 'cap-reached' and run['sessions_run'] == 1 and not (out/'397'/'sd1a2').exists()
    assert first['stopped_by_cap'] is True and 'spend cap reached' in first['proxy']['refusal_reasons']
    assert len(stand_in.requests) == 1
    assert Decimal(run['total_cost_usd']) == Decimal('0.02') <= Decimal('0.075')
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
