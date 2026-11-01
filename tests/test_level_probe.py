"""The level replay probe, against a recorded-session fixture and a scripted fake provider on loopback.

No real provider, credential, game or live session is involved; the host, MCP adapter, custodian and player HTTP
server are the real ones.
"""
import hashlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading
import time

from PIL import Image
import pytest

from harness.computer.store import SessionStore
from tools import level_probe
from tools.campaign_player import push_text
from tools.level_probe import build_replay, load_route, probe, recorded_passes

ROOT = Path(__file__).resolve().parents[1]
HOST = [shutil.which('node'), str(ROOT / 'tools/player_host/run.mjs')]
SESSION = 'c' * 32
RECORDED_ACTOR = 'a1' * 16
KEY = 'probe-secret-credential'
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is required for the level host')
THRESHOLDS = dict(schema='level-probe-thresholds/1', valid_terminal_rate_at_least=0.9, repeated_identical_refusal_at_most=1)


@pytest.fixture(autouse=True)
def clean_checkout(monkeypatch):
    """Probes refuse a dirty checkout; the working tree under test is not the subject here."""
    monkeypatch.setattr(level_probe, 'git_state', lambda root=None: ('d' * 40, False))


def png() -> bytes:
    out = io.BytesIO()
    Image.new('RGB', (4, 4), 'blue').save(out, format='PNG')
    return out.getvalue()


@pytest.fixture
def recorded(tmp_path):
    """A recorded single-actor campaign session with two level passes (after 3 and 6 operations)."""
    session = tmp_path / 'recorded'
    session.mkdir()
    limits = dict(max_inputs=100, max_requests=100, max_frames=100, max_bytes=2 ** 30)
    store = SessionStore(session, SESSION, limits, 1e9)
    store.add_actor(RECORDED_ACTOR, 'h' * 64)
    image = png()
    for number in range(1, 9):
        identity = f'{number:032x}'
        kind = 'observe' if number == 1 else 'input'
        actions = [] if kind == 'observe' else [dict(type='key', key='x', modifiers=[])]
        store.begin(dict(operation_id=identity, actor_id=RECORDED_ACTOR, kind=kind, created_wall=1000. + number,
                         deadline_monotonic=1e8), actions, len(actions))
        metadata = dict(schema='computer-source/1', source_id=f'{SESSION}-{number}', session=SESSION, capture_id=number,
                        sha256=hashlib.sha256(image).hexdigest(), media_type='image/png', presented_ms=1000 + number,
                        received_wall=1000. + number, window_width=4, viewport=[0, 0, 4, 4], width=4, window_height=4, height=4)
        store.put_source(metadata, image, RECORDED_ACTOR)
        store.finish(dict(schema='computer-operation/1', operation_id=identity, session=SESSION, actor_id=RECORDED_ACTOR,
                          kind=kind, status='completed', created_wall=1000. + number, deadline_monotonic=1e8, receipts=[],
                          source=metadata, remaining={}, reason='ok', handoff=None))
    store.close()
    (session / 'prompt.txt').write_text('Mission: survive and report.')
    (session / 'receipt.json').write_text(json.dumps(dict(schema='campaign-receipt/2', session=SESSION)))
    (session / 'manifest.json').write_text(json.dumps(dict(level=dict(mode='shadow', inputs_per_pass=3, staleness_inputs=10,
        budget_fractions=[.5], intent_tail_bytes=1024, max_http_attempts=60, pass_max_requests=4, pass_seconds=60))))
    actor_directory = session / 'actors/001'
    (actor_directory / 'level').mkdir(parents=True)
    (actor_directory / 'actor.json').write_text(json.dumps(dict(actor_id=RECORDED_ACTOR)))
    for index, entries in ((1, 3), (2, 6)):
        directory = actor_directory / 'level' / f'{index:03d}'
        directory.mkdir()
        (directory / 'context.txt').write_text('Frozen guide for the probe.')
        (directory / 'driver-receipt.json').write_text(json.dumps(dict(index=index, reason='inputs', log_entries=entries,
            actor_inputs=entries - 1, allocated_seconds=60, allocated_attempts=4, started_wall=2000. + index, level_events=[])))
    return session


def route_file(tmp_path, port, *, cost=1.0, extra=None, schema='player-host/5'):
    model = dict(id='fixture-model', name='Fixture', api='openai-completions', provider='fixture',
                 baseUrl=f'http://127.0.0.1:{port}/v1', reasoning=False, input=['text', 'image'],
                 cost=dict(input=cost, output=cost, cacheRead=0, cacheWrite=0), contextWindow=100000, maxTokens=1024,
                 compat=dict(supportsDeveloperRole=False, supportsStore=False, supportsUsageInStreaming=True))
    path = tmp_path / 'route.json'
    path.write_text(json.dumps(dict(schema=schema, model=model, api_key_env='PROBE_FIXTURE_KEY', max_requests=4,
                                    request_timeout_seconds=20, max_context_images=8, context_image_block=1, service_tier='default', **(extra or {}))))
    return path


class Raw:
    """Tool-call arguments sent exactly as written, so a malformed document can be scripted."""
    def __init__(self, text):
        self.text = text


class Provider:
    """A scripted OpenAI-compatible chat-completions endpoint: `policy(number, payload)` returns the tool call(s)."""
    def __init__(self, policy, tokens=11, delay=0., usage=True):
        self.policy, self.tokens, self.payloads, self.lock = policy, tokens, [], threading.Lock()
        self.usage = usage
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['content-length'])))
                with provider.lock:
                    provider.payloads.append(payload)
                    number = len(provider.payloads)
                calls = provider.policy(number, payload)
                time.sleep(delay)
                if calls is None:
                    body = b'{"error":{"message":"scripted failure","code":400}}'
                    self.send_response(400)
                    self.send_header('content-type', 'application/json')
                    self.send_header('content-length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                delta = dict(role='assistant', tool_calls=[dict(index=i, id=f'call-{number}-{i}', type='function',
                             function=dict(name=name, arguments=args.text if isinstance(args, Raw) else json.dumps(args))) for i, (name, args) in enumerate(calls)])
                chunks = [dict(id='r', model='fixture-backend', choices=[dict(index=0, delta=delta, finish_reason=None)]),
                          dict(id='r', model='fixture-backend', choices=[dict(index=0, delta={}, finish_reason='tool_calls')],
                               **(dict(usage=dict(prompt_tokens=provider.tokens, completion_tokens=provider.tokens,
                                                  total_tokens=2 * provider.tokens)) if provider.usage else {}))]
                body = ''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n'
                self.send_response(200)
                self.send_header('content-type', 'text/event-stream')
                self.end_headers()
                self.wfile.write(body.encode())

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)


REPLACE = dict(text='Open the door', expected_observations=['door open'], status='open', confidence=.5, sources=[],
               previous_outcome='none', previous_reason='')


def turns(payload):
    """Tool results already in this pass's conversation: which request of its pass this is."""
    return sum(m.get('role') == 'tool' for m in payload['messages'])


def clean_policy(number, payload):
    if turns(payload) == 0:
        return [('player_log_read', dict(after=0, limit=5))]
    return [('player_level_replace', REPLACE)]


@pytest.fixture
def provider():
    created = []

    def make(policy, **kwargs):
        value = Provider(policy, **kwargs)
        created.append(value)
        return value
    yield make
    for value in created:
        value.close()


def run(tmp_path, recorded, provider, *, name='probe', samples=2, max_usd=10., route=None, **kwargs):
    root = tmp_path / 'probes'
    thresholds = tmp_path / 'thresholds.json'
    thresholds.write_text(json.dumps(THRESHOLDS))
    report = probe([recorded], route or route_file(tmp_path, provider.port), samples=samples, max_usd=max_usd, name=name,
                   secret=KEY, host_argv=HOST, effort='off', probe_root=root, thresholds_path=thresholds, **kwargs)
    return report, root / name


def test_replay_is_a_fresh_store_of_the_pass_start_state_and_leaves_the_recording_untouched(tmp_path, recorded):
    before = hashlib.sha256((recorded / 'session.sqlite3').read_bytes()).hexdigest()
    first, second = recorded_passes(recorded)
    assert (first['entries'], second['entries'], second['shown_through']) == (3, 6, 3)
    replay = build_replay(first, tmp_path / 'replay', 10)
    try:
        app, reader, actor = replay['application'], replay['reader'], replay['actor']
        assert app.runtime.store.actor_counts(actor['actor_id']) == (3, 2)
        text, shown, through = push_text(app, reader['actor_id'], actor['actor_id'], 0, 3)
        assert (shown, through) == (3, 3) and 'Current subgoal: none\nLevel records in player memory: 0' in text
        entries = [json.loads(line) for line in text.splitlines() if line.startswith('{"position"')]
        # The replay reads the recorded frames and writes only its own temporary memory.
        value, image = app.source(entries[0]['source_id'], actor['actor_id'])
        assert image == png() and value['source_id'] == f'{SESSION}-1'
        committed = app.call(reader['token'], 'player_level_replace', REPLACE, 'e' * 32)[0]
        assert committed['status'] == 'committed' and committed['inputs_since'] == 0
        assert app.runtime.channel.stopped.is_set() is False
    finally:
        replay['runtime'].close(); replay['memory'].close()
    assert hashlib.sha256((recorded / 'session.sqlite3').read_bytes()).hexdigest() == before
    # The second pass is pushed only what the first showed it did not already see.
    again = build_replay(second, tmp_path / 'replay2', 10)
    try:
        app, reader, actor = again['application'], again['reader'], again['actor']
        text, shown, _ = push_text(app, reader['actor_id'], actor['actor_id'], 3, 6)
        assert shown == 3 and [json.loads(l)['position'] for l in text.splitlines() if l.startswith('{"position"')] == [4, 5, 6]
        assert app.level_record_count() == 0
    finally:
        again['runtime'].close(); again['memory'].close()


def test_probe_replays_every_pass_through_the_real_host_and_labels_its_output(tmp_path, recorded, provider):
    fake = provider(clean_policy)
    report, out = run(tmp_path, recorded, fake)
    assert report['label'] == 'engineering-probe' and report['excluded_from_evidence'] is True
    assert (out / 'report.json').is_file() and json.loads((out / 'report.json').read_text())['label'] == 'engineering-probe'
    assert out.is_relative_to((tmp_path / 'probes').resolve())
    pooled = report['pooled']
    assert pooled['samples'] == 4 and pooled['valid_terminal_calls'] == 4 and pooled['valid_terminal_rate'] == 1
    assert pooled['outcomes'] == {'replace': 4} and pooled['refusals_by_field'] == {}
    assert pooled['level_final_refusal'] == 0 and pooled['request_limit'] == 0
    assert pooled['requests_used']['total'] == 8 and 0 < pooled['configured_cost_usd'] < 0.01
    assert report['thresholds']['valid_terminal_rate_met'] is True and report['thresholds']['repeated_identical_refusal_met'] is True
    assert sorted(report['passes']) == ['recorded/actor001/pass001', 'recorded/actor001/pass002']
    assert report['interface']['host'] == 'player-host/5' and report['interface']['role_prompt'] == 'subgoal-v3.txt'
    # The pass saw the production pushed input of the replay, the frozen role prompt and the real v3 tools.
    first = fake.payloads[0]
    prompt = json.dumps(first['messages'])
    assert 'Current subgoal: none\\nLevel records in player memory: 0' in prompt and 'Mission: survive and report.' in prompt
    assert 'Call player_level_keep, player_level_close or player_level_replace' in prompt
    assert first['tool_choice'] == 'required'
    assert [t['function']['name'] for t in first['tools']] == [
        'player_log_read', 'player_source', 'player_level_keep', 'player_level_replace', 'player_level_close', 'player_level_abstain']
    assert len(list((out / 'samples').iterdir())) == 4 and all((p / 'host.jsonl').is_file() for p in (out / 'samples').iterdir())


def test_probe_never_writes_the_credential_or_outside_the_probes_directory(tmp_path, recorded, provider):
    report, out = run(tmp_path, recorded, provider(clean_policy), samples=1)
    for path in out.rglob('*'):
        if path.is_file():
            assert KEY not in path.read_text(errors='ignore'), path
    assert KEY not in json.dumps(report)
    assert not (tmp_path / 'probes' / 'probe' / 'work').exists()
    for name in ('../escape', 'a/../../escape', '.', ''):
        with pytest.raises((ValueError, FileExistsError)):
            probe([recorded], route_file(tmp_path, 1), samples=1, max_usd=1., name=name, secret=KEY, host_argv=HOST,
                  probe_root=tmp_path / 'probes', thresholds_path=tmp_path / 'thresholds.json')
    assert not (tmp_path / 'escape').exists()


def test_refusals_by_field_final_refusal_and_repeated_identical_refusals_are_reported(tmp_path, recorded, provider):
    bad = dict(REPLACE, previous_outcome='done')

    def policy(number, payload):
        return [('player_level_replace', bad)]
    report, _ = run(tmp_path, recorded, provider(policy), samples=1, max_requests=3, passes={1})
    pooled = report['pooled']
    assert pooled['valid_terminal_calls'] == 0 and pooled['valid_terminal_rate'] == 0
    assert pooled['outcomes'] == {'no-terminal-call': 1}
    assert pooled['level_final_refusal'] == 1 and pooled['request_limit'] == 0
    assert pooled['refusals_by_field'] == {'player_level_replace.previous_outcome': 3}
    assert pooled['max_repeated_identical_refusal'] == 3
    assert report['thresholds']['valid_terminal_rate_met'] is False and report['thresholds']['repeated_identical_refusal_met'] is False
    assert pooled['requests_used']['total'] == 3


def test_the_state_error_then_repair_and_abstain_codes_are_counted(tmp_path, recorded, provider):
    def policy(number, payload):
        if turns(payload) == 0:
            return [('player_level_keep', dict(reason='still valid', sources=[]))]  # no current subgoal: a custodian refusal
        if turns(payload) == 1:
            return [('player_level_abstain', dict(reason_code='transient_screen_state', reason='A menu is open', sources=[]))]
        return [('player_level_abstain', dict(reason_code='other', reason='x', sources=[]))]
    report, _ = run(tmp_path, recorded, provider(policy), samples=1, passes={1})
    pooled = report['pooled']
    assert pooled['outcomes'] == {'abstain:transient_screen_state': 1} and pooled['valid_terminal_rate'] == 1
    assert pooled['refusals_by_field'] == {'player_level_keep.custodian': 1}


def test_the_spend_cap_is_required_and_positive(tmp_path, recorded):
    with pytest.raises(SystemExit):
        level_probe.main(['--session', str(recorded), '--route', str(tmp_path / 'route.json'), '--name', 'x',
                          '--thresholds', str(tmp_path / 't.json')])
    for bad in (0, -1):
        with pytest.raises(ValueError, match='max-usd'):
            probe([recorded], tmp_path / 'route.json', samples=1, max_usd=bad, name='x', secret=KEY, host_argv=HOST,
                  probe_root=tmp_path / 'probes', thresholds_path=tmp_path / 't.json')
    assert not (tmp_path / 'probes').exists()


def test_the_cap_is_hard_up_front_so_a_sample_never_has_more_requests_than_the_cap_covers(tmp_path, recorded, provider):
    # Each request costs 22 tokens at 50000 USD per million: $1.10. The bound for a request is $1.20.
    fake = provider(clean_policy)
    route = route_file(tmp_path, fake.port, cost=50000.)
    report, _ = run(tmp_path, recorded, fake, samples=3, max_usd=5., route=route, name='capped', max_request_usd=1.2, passes={1})
    spend = report['spend']
    assert spend['stopped_by_spend_guard'] is True and spend['charged_usd'] <= 5. and spend['configured_cost_usd'] <= 5.
    # $5 covers four requests at the bound; the first sample uses two, so the second may use only two, the third none.
    assert [s['allowance'] for s in report['samples']] == [dict(recorded=4, used=4), dict(recorded=4, used=2)]
    assert spend['samples_run'] == 2 and all(s['requests'] <= s['allowance']['used'] for s in report['samples'])
    assert not any(s['stopped_by_spend_guard'] for s in report['samples'])
    # A cap below one request's bound runs nothing at all.
    nothing, _ = run(tmp_path, recorded, provider(clean_policy), samples=1, max_usd=.01, name='tiny')
    assert nothing['spend']['samples_run'] == 0 and nothing['spend']['stopped_by_spend_guard'] is True


def test_the_in_flight_kill_is_only_a_backstop_for_a_request_dearer_than_the_bound(tmp_path, recorded, provider):
    slow = provider(lambda n, p: [('player_log_read', dict(after=0, limit=5))], delay=.4)
    cut, _ = run(tmp_path, recorded, slow, samples=1, max_usd=3., route=route_file(tmp_path, slow.port, cost=50000.),
                 name='cut', max_request_usd=.1, max_requests=6, passes={1})
    assert cut['samples'][0]['stopped_by_spend_guard'] is True and cut['samples'][0]['requests'] < 6
    assert cut['pooled']['outcomes'] == {'no-terminal-call': 1}


def test_requests_without_reported_usage_are_charged_at_the_per_request_bound(tmp_path, recorded, provider):
    fake = provider(clean_policy, usage=False)
    # The recorded allowance is 4 and the sample estimate $0.12, so a request is charged $0.03.
    report, _ = run(tmp_path, recorded, fake, samples=1, passes={1})
    spend = report['spend']
    assert spend['configured_cost_usd'] == 0 and spend['missing_usage_attempts'] == 2
    assert spend['charged_usd'] == pytest.approx(.06) and report['samples'][0]['charged_usd'] == pytest.approx(.06)
    # The charge, not the zero reported cost, is what the cap counts: $0.07 covers two requests of one sample only.
    capped, _ = run(tmp_path, recorded, provider(clean_policy, usage=False), samples=3, max_usd=.07, name='no-usage-cap', passes={1})
    assert capped['spend']['samples_run'] == 1 and capped['spend']['stopped_by_spend_guard'] is True
    assert capped['spend']['charged_usd'] <= .07
    # An explicit per-request bound replaces the estimate-derived one.
    explicit, _ = run(tmp_path, recorded, provider(clean_policy, usage=False), samples=1, name='explicit', max_request_usd=.5, passes={1})
    assert explicit['spend']['charged_usd'] == pytest.approx(1.)


def test_a_route_with_no_configured_cost_is_refused_before_anything_is_written(tmp_path, recorded, provider):
    with pytest.raises(ValueError, match='all zero'):
        run(tmp_path, recorded, provider(clean_policy), route=route_file(tmp_path, 9, cost=0.))
    assert not (tmp_path / 'probes' / 'probe').exists()


@pytest.mark.parametrize('schema', ['player-host/4', 'player-host/1', 'player-host/6', None])
def test_a_route_that_is_not_player_host_5_is_rejected_without_normalization(tmp_path, recorded, provider, schema):
    path = route_file(tmp_path, 9, schema=schema)
    with pytest.raises(ValueError, match='must be player-host/5'):
        load_route(path, 4, None)
    with pytest.raises(ValueError, match='must be player-host/5'):
        run(tmp_path, recorded, provider(clean_policy), route=path)
    assert not (tmp_path / 'probes' / 'probe').exists()
    route = json.loads(path.read_text())
    package = tmp_path / 'package.json'
    package.write_text(json.dumps(dict(schema='finite-provider-conformance/1', routes=[dict(tag='one', model='fixture-model',
                                                                                            configuration=route)])))
    with pytest.raises(ValueError, match='must be player-host/5'):
        load_route(package, 4, None)


def test_the_conformance_package_supplies_its_player_host_5_route_unchanged_except_the_level_fields(tmp_path):
    route = json.loads(route_file(tmp_path, 9).read_text())
    package = tmp_path / 'package.json'
    package.write_text(json.dumps(dict(schema='finite-provider-conformance/1', routes=[
        dict(tag='one', model='fixture-model', configuration=dict(route, role='actor', intent_tail_bytes=1024))])))
    selected = load_route(package, 5, None)
    assert selected == dict(route, role='level', intent_tail_bytes=None, max_requests=5)
    with pytest.raises(ValueError, match='exactly one'):
        load_route(package, 5, 'missing')
    # Nothing is defaulted: a route without a required field reaches the host as it is.
    del route['context_image_block']
    plain = tmp_path / 'plain.json'
    plain.write_text(json.dumps(route))
    assert 'context_image_block' not in load_route(plain, 5, None)


def test_thresholds_are_a_required_closed_file_and_are_recorded_with_the_report_inputs(tmp_path, recorded, provider):
    with pytest.raises(SystemExit):
        level_probe.main(['--session', str(recorded), '--route', str(tmp_path / 'r.json'), '--name', 'x', '--max-usd', '1'])
    thresholds = tmp_path / 'strict.json'
    for bad in (dict(THRESHOLDS, extra=1), dict(THRESHOLDS, schema='level-probe-thresholds/0'),
                {k: v for k, v in THRESHOLDS.items() if k != 'valid_terminal_rate_at_least'},
                dict(THRESHOLDS, valid_terminal_rate_at_least=0), dict(THRESHOLDS, repeated_identical_refusal_at_most=0)):
        thresholds.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match='hreshold|must be'):
            level_probe.load_thresholds(thresholds)
    fake = provider(clean_policy)
    report, out = run(tmp_path, recorded, fake, samples=1, max_requests=3)
    strict = report['thresholds']
    assert strict['definition'] == THRESHOLDS and strict['file_sha256'] == hashlib.sha256((tmp_path / 'thresholds.json').read_bytes()).hexdigest()
    assert report['source'] == dict(commit='d' * 40, clean=True)
    assert report['route']['file_sha256'] == hashlib.sha256((tmp_path / 'route.json').read_bytes()).hexdigest()
    (item,) = report['inputs']['sessions']
    assert item == dict(session='recorded', manifest_sha256=hashlib.sha256((recorded / 'manifest.json').read_bytes()).hexdigest(),
                        receipt_sha256=hashlib.sha256((recorded / 'receipt.json').read_bytes()).hexdigest())
    assert report['interface']['role_sha256'] and any('No staleness or discard' in limit for limit in report['limits'])
    assert any('pending' in limit for limit in report['limits'])
    # The allowance is the recorded pass's own; an override is recorded, never silent.
    assert {tuple(s['allowance'].items()) for s in report['samples']} == {(('recorded', 4), ('used', 3))}
    # A different threshold file changes the verdict, not the measurement.
    lenient = tmp_path / 'lenient.json'
    lenient.write_text(json.dumps(dict(THRESHOLDS, valid_terminal_rate_at_least=1.0)))
    again = probe([recorded], tmp_path / 'route.json', samples=1, max_usd=10., name='again', secret=KEY, host_argv=HOST,
                  effort='off', probe_root=tmp_path / 'probes', thresholds_path=lenient)
    assert again['thresholds']['definition']['valid_terminal_rate_at_least'] == 1.0


def test_a_dirty_checkout_is_refused_before_anything_is_written_and_git_state_reads_the_repository(tmp_path, recorded, provider, monkeypatch):
    monkeypatch.setattr(level_probe, 'git_state', lambda root=None: ('e' * 40, True))
    with pytest.raises(ValueError, match='clean commit'):
        run(tmp_path, recorded, provider(clean_policy))
    assert not (tmp_path / 'probes').exists()
    repo = tmp_path / 'repo'
    repo.mkdir()
    git = lambda *a: subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *a], cwd=repo,
                                    check=True, capture_output=True, text=True).stdout.strip()
    git('init', '-q')
    (repo / 'a.txt').write_text('one')
    git('add', 'a.txt')
    git('commit', '-q', '-m', 'one')
    monkeypatch.undo()
    commit, dirty = level_probe.git_state(repo)
    assert commit == git('rev-parse', 'HEAD') and dirty is False
    (repo / 'untracked.txt').write_text('x')
    assert level_probe.git_state(repo)[1] is False
    (repo / 'a.txt').write_text('two')
    assert level_probe.git_state(repo)[1] is True


def write_receipt(recorded, index, events, **change):
    path = recorded / 'actors/001/level' / f'{index:03d}' / 'driver-receipt.json'
    value = json.loads(path.read_text())
    path.write_text(json.dumps(dict(value, level_events=events, **change)))


def commit_event(action):
    return dict(type='level-commit', action=action)


@pytest.mark.parametrize('earlier,fidelity', [
    ([], 'exact'), ([dict(type='level-abstain')], 'exact'), ([commit_event('keep')], 'exact'),
    ([dict(type='level-discard', action='replace')], 'exact'),
    ([commit_event('replace')], 'memory-reset'), ([commit_event('close')], 'memory-reset')])
def test_state_fidelity_is_whether_the_replay_memory_matches_the_recording_at_the_pass_start(tmp_path, recorded, provider, earlier, fidelity):
    write_receipt(recorded, 1, earlier)
    first, second = recorded_passes(recorded)
    assert first['prior_level_commits'] == 0 and second['prior_level_commits'] == (fidelity == 'memory-reset')
    report, _ = run(tmp_path, recorded, provider(clean_policy), samples=1)
    by_pass = {s['pass_index']: s for s in report['samples']}
    # The first pass is always exact: its own commits come after it started.
    assert by_pass[1]['state_fidelity'] == 'exact' and by_pass[2]['state_fidelity'] == fidelity


def test_state_fidelity_also_reads_level_work_in_the_recorded_player_store_created_before_the_pass(tmp_path, recorded, provider):
    from harness.player.memory import Memory
    store = tmp_path / 'recorded-player.sqlite3'
    memory = Memory(store)
    memory.append(RECORDED_ACTOR, dict(schema='player-record/1', kind='work', text='Earlier', data=dict(level='subgoal'),
                                       sources=[], supports=[], supersedes=None, applicability=None, program_id=None))
    memory.append(RECORDED_ACTOR, dict(schema='player-record/1', kind='work', text='Other work', data={}, sources=[],
                                       supports=[], supersedes=None, applicability=None, program_id=None))
    memory.close()
    manifest = json.loads((recorded / 'manifest.json').read_text())
    (recorded / 'manifest.json').write_text(json.dumps(dict(manifest, player_store=str(store))))
    write_receipt(recorded, 2, [], started_wall=time.time() + 100)
    first, second = recorded_passes(recorded)
    assert (first['prior_stored_rows'], second['prior_stored_rows'], second['prior_level_commits']) == (0, 1, 0)
    report, _ = run(tmp_path, recorded, provider(clean_policy), samples=1)
    assert {s['pass_index']: s['state_fidelity'] for s in report['samples']} == {1: 'exact', 2: 'memory-reset'}


def test_terminal_calls_the_host_refused_or_could_not_parse_are_counted_and_repeat_identically(tmp_path, recorded, provider):
    coerced = dict(REPLACE, confidence='0.5')
    report, _ = run(tmp_path, recorded, provider(lambda n, p: [('player_level_replace', coerced)]), samples=1, max_requests=3, passes={1})
    pooled = report['pooled']
    assert pooled['refusals_by_field'] == {'player_level_replace.tool-refused:tool-arguments-changed': 3}
    assert pooled['max_repeated_identical_refusal'] == 3 and pooled['level_final_refusal'] == 1
    assert report['thresholds']['repeated_identical_refusal_met'] is False
    malformed = provider(lambda n, p: [('player_level_abstain', Raw('{"reason_code":"other",'))])
    report, _ = run(tmp_path, recorded, malformed, samples=1, max_requests=3, passes={1}, name='malformed')
    pooled = report['pooled']
    assert pooled['refusals_by_field'] == {'player_level_abstain.arguments_error': 3}
    assert pooled['max_repeated_identical_refusal'] == 3 and pooled['valid_terminal_calls'] == 0


def test_reserved_requests_report_refused_non_terminal_calls_and_provider_errors_on_them(tmp_path, recorded, provider):
    def policy(number, payload):
        return [('player_log_read', dict(after=0, limit=5))] if number == 1 else [('player_level_abstain', dict(reason_code='other', reason='r', sources=[]))]
    report, _ = run(tmp_path, recorded, provider(policy), samples=1, max_requests=2, passes={1})
    pooled = report['pooled']
    assert pooled['reserved_non_terminal_calls'] == 1 and pooled['valid_terminal_calls'] == 1
    assert pooled['provider_error_on_reserved_request'] == 0
    # The second of three requests is reserved: a provider failure there is its own count; on the first request it is not.
    def fail_second(number, payload):
        return None if number == 2 else [('player_log_read', dict(after=0, limit=5))]
    report, _ = run(tmp_path, recorded, provider(fail_second), samples=1, max_requests=3, passes={1}, name='reserved-error')
    assert report['pooled']['provider_error_on_reserved_request'] == 1
    assert report['samples'][0]['settled_reason'] == 'provider-error'
    report, _ = run(tmp_path, recorded, provider(lambda n, p: None), samples=1, max_requests=4, passes={1}, name='first-error')
    assert report['samples'][0]['settled_reason'] == 'provider-error' and report['pooled']['provider_error_on_reserved_request'] == 0


def test_the_credential_comes_only_from_the_keychain_item(monkeypatch):
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return type('Result', (), dict(stdout=KEY + '\n'))()
    monkeypatch.setattr(level_probe.subprocess, 'run', fake_run)
    assert level_probe.keychain_secret() == KEY
    assert calls == [['security', 'find-generic-password', '-s', 'userspace-dev-openrouter', '-w']]

    def missing(arguments, **kwargs):
        raise level_probe.subprocess.CalledProcessError(44, arguments, stderr=KEY)
    monkeypatch.setattr(level_probe.subprocess, 'run', missing)
    with pytest.raises(ValueError) as raised:
        level_probe.keychain_secret()
    assert KEY not in str(raised.value)
