"""Curator sandbox and model proxy (#451, ADR 009 isolation).

The proxy tests are portable. The escape suite runs the real macOS Seatbelt sandbox against the
real custodian/playing-service HTTP listener and the real Pause gateway (over their receiver
doubles; no game, no provider). It is a native lane: it skips off macOS, so Linux CI does not
execute it and a local run on the Mac is its evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import pytest

from harness.curator import proxy as proxy_module
from harness.curator import sandbox
from harness.curator.proxy import ANTHROPIC, ModelProxy, Price

ROOT = Path(__file__).resolve().parents[1]
ADVERSARY = Path(__file__).with_name('curator_adversary.py')
PYTHON = Path(os.path.realpath(sys.executable))
PYTHON_ROOT = Path(sys.base_prefix).resolve()
PRICES = {'model-a': Price(input=Decimal(3), output=Decimal(15), cache_write=Decimal('3.75'),
                           cache_read=Decimal('0.3'))}
native = pytest.mark.skipif(sys.platform != 'darwin' or not Path(sandbox.SANDBOX_EXEC).exists(),
                            reason='Seatbelt lane: macOS only')


# ---------------------------------------------------------------- helpers
def make_layout(base: Path) -> sandbox.Layout:
    base = base.resolve()
    workspace, home = base/'workspace', base/'home'
    for name in ('trace', 'knowledge', 'submissions', 'drafts', 'scratch'):
        (workspace/name).mkdir(parents=True)
    home.mkdir()
    (workspace/'brief.md').write_text('brief')
    (workspace/'knowledge'/'ontology.json').write_text('{}')
    (workspace/'trace'/'frame.json').write_text('{}')
    return sandbox.Layout(workspace=workspace, home=home,
                          writable=tuple(workspace/n for n in ('submissions', 'drafts', 'scratch')),
                          tools=(PYTHON_ROOT,))


class Upstream:
    """A local stand-in for the provider: records what it received and answers with usage."""

    def __init__(self, reply=None, stream=False, gzip=False):
        self.requests = []
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers['content-length']))
                upstream.requests.append(dict(path=self.path, headers=dict(self.headers.items()), body=body))
                if stream:
                    data = (b'event: message_start\ndata: {"type":"message_start","message":{"usage":'
                            b'{"input_tokens":1000,"output_tokens":1}}}\n\n'
                            b'event: message_delta\ndata: {"type":"message_delta","usage":{"output_tokens":200}}\n\n')
                    media = 'text/event-stream'
                else:
                    data = json.dumps(reply if reply is not None else
                                      dict(usage=dict(input_tokens=1000, output_tokens=200))).encode()
                    media = 'application/json'
                if gzip:
                    import gzip as compressor
                    data = compressor.compress(data)
                self.send_response(200)
                self.send_header('content-type', media)
                if gzip:
                    self.send_header('content-encoding', 'gzip')
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@contextmanager
def running_proxy(tmp_path, *, cap='1', reply=None, stream=False, gzip=False, betas=frozenset()):
    upstream = Upstream(reply, stream, gzip)
    proxy = ModelProxy(provider=ANTHROPIC, upstream=upstream.url, key='real-provider-key', prices=PRICES,
                       cap_usd=Decimal(cap), ledger=tmp_path/'ledger.jsonl', max_output_tokens=4096,
                       betas=betas)
    port = proxy.start()
    try:
        yield proxy, port, upstream
    finally:
        proxy.close()
        upstream.close()


def post(port, path, body: dict | bytes, token, headers=None):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    connection.request('POST', path, body=data, headers={'x-api-key': token, 'content-type': 'application/json',
                                                         **(headers or {})})
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, payload


def request(max_tokens=100):
    return dict(model='model-a', max_tokens=max_tokens, messages=[dict(role='user', content='hi')])


# ---------------------------------------------------------------- profile and layout (portable)
def test_profile_is_default_deny_with_one_loopback_port(tmp_path):
    layout = make_layout(tmp_path)
    text = sandbox.profile(layout, 4321)
    assert '(deny default)' in text
    assert text.count('network-outbound') == 1 and '(remote ip "localhost:4321")' in text
    assert 'mach-lookup (global-name' in text and 'pasteboard' not in text
    assert f'(subpath "{layout.workspace}")' in text
    write_rule = next(line for line in text.splitlines() if line.startswith('(allow file-write*'))
    assert str(layout.workspace/'knowledge') not in write_rule and str(layout.workspace/'trace') not in write_rule
    assert f'(subpath "{layout.workspace}")' not in write_rule
    assert 'network-outbound' not in sandbox.profile(layout, None)


@pytest.mark.parametrize('change', ['relative', 'writable-outside', 'writable-is-workspace', 'home-inside', 'quote'])
def test_layout_refuses_paths_that_widen_the_boundary(tmp_path, change):
    layout = make_layout(tmp_path)
    fields = dict(workspace=layout.workspace, home=layout.home, writable=layout.writable, tools=layout.tools)
    if change == 'relative':
        fields['tools'] = (Path('relative'),)
    elif change == 'writable-outside':
        fields['writable'] = (tmp_path.resolve(),)
    elif change == 'writable-is-workspace':
        fields['writable'] = (layout.workspace,)
    elif change == 'home-inside':
        fields['home'] = layout.workspace/'scratch'
    else:
        fields['tools'] = (tmp_path.resolve()/'a"b',)
    with pytest.raises(sandbox.SandboxError):
        sandbox.Layout(**fields)


def test_environment_inherits_nothing_and_cannot_be_overridden(tmp_path, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'should-not-pass')
    layout = make_layout(tmp_path)
    env = sandbox.environment(layout, proxy_port=1234, token='t')
    assert 'ANTHROPIC_API_KEY' not in env and env['HOME'] == str(layout.home)
    assert env['TMPDIR'].startswith(str(layout.workspace/'scratch'))
    with pytest.raises(sandbox.SandboxError):
        sandbox.environment(layout, proxy_port=1234, token='t', extra=dict(HOME='/Users'))


# ---------------------------------------------------------------- proxy (portable)
def test_proxy_swaps_the_session_token_for_the_key_and_records_no_key(tmp_path):
    with running_proxy(tmp_path) as (proxy, port, upstream):
        status, _ = post(port, '/v1/messages', request(), proxy.token)
        assert status == 200
        sent = upstream.requests[0]['headers']
        assert sent['x-api-key'] == 'real-provider-key'
        assert proxy.token not in json.dumps(sent)
    ledger = (tmp_path/'ledger.jsonl').read_text()
    assert 'real-provider-key' not in ledger and proxy.token not in ledger
    entry = json.loads(ledger.splitlines()[0])
    assert Decimal(entry['charged']) == Decimal('0.006') and entry['usage_missing'] is False


def image(source):
    return dict(request(), messages=[dict(role='user', content=[dict(type='image', source=source)])])


REFUSED = {
    'wrong token': (401, dict(token='x'*64)),
    'no token': (401, dict(token='')),
    'route': (404, dict(path='/v1/files')),
    'route with dots': (404, dict(path='/v1/messages/../files')),
    'unpriced model': (429, dict(body=dict(request(), model='unpriced'))),
    'no output limit': (429, dict(body=dict(model='model-a', messages=[]))),
    'over output limit': (429, dict(body=dict(request(), max_tokens=10_000))),
    'not json': (400, dict(body=b'not json')),
    'body too large': (413, dict(declared=proxy_module.MAX_BODY + 1)),
    'image by url': (400, dict(body=image(dict(type='url', url='https://example.com/x.png')))),
    'stored file': (400, dict(body=image(dict(type='file', file_id='file_1')))),
    'document block': (400, dict(body=dict(request(), messages=[dict(role='user', content=[
        dict(type='document', source=dict(type='base64', media_type='application/pdf', data='AA=='))])]))),
    'server tool': (400, dict(body=dict(request(), tools=[dict(type='web_fetch_20260209', name='web_fetch')]))),
    'mcp servers': (400, dict(body=dict(request(), mcp_servers=[dict(type='url', url='https://x', name='x')]))),
    'speed tier': (400, dict(body=dict(request(), speed='fast'))),
    'service tier': (400, dict(body=dict(request(), service_tier='priority'))),
    'fallbacks': (400, dict(body=dict(request(), fallbacks='default'))),
    'container': (400, dict(body=dict(request(), container='c'))),
}


@pytest.mark.parametrize('case', sorted(REFUSED))
def test_proxy_refuses_before_reaching_the_provider(tmp_path, case):
    expected, change = REFUSED[case]
    with running_proxy(tmp_path) as (proxy, port, upstream):
        if 'declared' in change:
            # Declare an oversize body and send none: the proxy must refuse on the header alone.
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            connection.putrequest('POST', '/v1/messages')
            connection.putheader('x-api-key', proxy.token)
            connection.putheader('content-length', str(change['declared']))
            connection.endheaders()
            status = connection.getresponse().status
            connection.close()
        else:
            status, _ = post(port, change.get('path', '/v1/messages'), change.get('body', request()),
                             change.get('token', proxy.token))
        assert status == expected
        assert upstream.requests == []


def test_inline_image_and_client_tools_pass(tmp_path):
    body = dict(image(dict(type='base64', media_type='image/png', data='AA==')),
                tools=[dict(name='t', description='d', input_schema=dict(type='object'))])
    with running_proxy(tmp_path) as (proxy, port, upstream):
        assert post(port, '/v1/messages', body, proxy.token)[0] == 200
        assert len(upstream.requests) == 1


def test_only_allowlisted_headers_and_frozen_betas_reach_the_provider(tmp_path):
    headers = {'cookie': 'c=1', 'openai-organization': 'org', 'accept-encoding': 'gzip, br',
               'anthropic-beta': 'allowed-beta,unlisted-beta', 'anthropic-version': '2026-10-21'}
    with running_proxy(tmp_path, betas=frozenset({'allowed-beta'})) as (proxy, port, upstream):
        assert post(port, '/v1/messages', request(), proxy.token, headers)[0] == 200
        sent = {k.lower(): v for k, v in upstream.requests[0]['headers'].items()}
    assert 'cookie' not in sent and 'openai-organization' not in sent
    assert sent['accept-encoding'] == 'identity' and sent['anthropic-beta'] == 'allowed-beta'
    assert sent['anthropic-version'] == '2026-10-21'
    assert json.loads((tmp_path/'ledger.jsonl').read_text())['dropped_betas'] == ['unlisted-beta']


def test_a_charge_above_its_reservation_revokes_the_session(tmp_path):
    expensive = dict(usage=dict(input_tokens=300_000, output_tokens=10))
    with running_proxy(tmp_path, reply=expensive) as (proxy, port, upstream):
        assert post(port, '/v1/messages', request(), proxy.token)[0] == 200
        assert proxy.breaches == 1 and proxy.revoked
        assert post(port, '/v1/messages', request(), proxy.token)[0] == 429
        assert len(upstream.requests) == 1
    assert json.loads((tmp_path/'ledger.jsonl').read_text().splitlines()[0])['breach'] is True


def test_an_encoded_response_cannot_hide_usage(tmp_path):
    with running_proxy(tmp_path, gzip=True) as (proxy, port, upstream):
        post(port, '/v1/messages', request(), proxy.token)
        assert proxy.revoked and proxy.spent > Decimal('0.0015')
        assert post(port, '/v1/messages', request(), proxy.token)[0] == 429
        assert len(upstream.requests) == 1


def test_proxy_cap_refuses_by_worst_case_reservation(tmp_path):
    # Each request reserves body bytes at 3.75/MTok plus 4096 output tokens at 15/MTok ≈ $0.062,
    # and settles at $0.006. A $0.07 cap admits one at a time only while settled spend leaves room.
    with running_proxy(tmp_path, cap='0.07') as (proxy, port, upstream):
        statuses = [post(port, '/v1/messages', request(4096), proxy.token)[0] for _ in range(4)]
        assert statuses[0] == 200 and 429 in statuses
        assert proxy.spent <= proxy.cap and proxy.reserved == 0
        assert len(upstream.requests) == statuses.count(200)


def test_missing_usage_keeps_the_whole_reservation(tmp_path):
    with running_proxy(tmp_path, reply=dict(content='no usage')) as (proxy, port, _):
        assert post(port, '/v1/messages', request(1000), proxy.token)[0] == 200
        assert proxy.spent > Decimal('0.015')
    assert json.loads((tmp_path/'ledger.jsonl').read_text())['usage_missing'] is True


def test_streamed_usage_is_settled(tmp_path):
    with running_proxy(tmp_path, stream=True) as (proxy, port, _):
        status, body = post(port, '/v1/messages', request(), proxy.token)
        assert status == 200 and b'message_delta' in body
        assert proxy.spent == Decimal('0.006')


def test_revoked_token_is_refused(tmp_path):
    with running_proxy(tmp_path) as (proxy, port, upstream):
        proxy.revoke()
        assert post(port, '/v1/messages', request(), proxy.token)[0] == 429
        assert upstream.requests == []


def test_proxy_needs_frozen_prices_a_cap_and_a_bare_origin(tmp_path):
    for kwargs in (dict(prices={}), dict(cap_usd=Decimal(0)), dict(upstream='https://h/v1')):
        values = dict(provider=ANTHROPIC, upstream='https://h', key='k', prices=PRICES, cap_usd=Decimal(1),
                      ledger=tmp_path/'l')
        values.update(kwargs)
        with pytest.raises(ValueError):
            ModelProxy(**values)
    assert proxy_module.usage_of(ANTHROPIC, b'garbage') is None


# ---------------------------------------------------------------- escape suite (native)
@pytest.fixture
def custodian(tmp_path):
    """The real custodian/playing-service HTTP listener (with /api/pause) over receiver doubles."""
    from harness.application import Application
    from harness.computer.runtime import ComputerRuntime
    from harness.player.memory import Memory
    from harness.server import serve
    from tests.test_computer_runtime import Channel, Process

    directory = tmp_path/'runtime'
    directory.mkdir()
    runtime = ComputerRuntime(directory, 'a'*32, Channel(), Process(), time.monotonic()+90,
                              dict(max_inputs=10, max_requests=20, max_frames=20, max_bytes=2**20))
    memory = Memory(directory/'player.sqlite3')
    server, thread = serve(Application(runtime, memory, directory/'contexts'), 0)
    actor = runtime.add_actor()
    (directory/'actor.json').write_text(json.dumps(dict(schema='player-adapter/1', session=runtime.session,
                                                        base_url=f'http://127.0.0.1:{server.server_port}', **actor)))
    try:
        yield server.server_port, directory
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        runtime.close()
        memory.close()


def run_adversary(layout, targets, *, proxy_port=None, token=None, limits=sandbox.Limits(wall_seconds=60)):
    shutil.copy(ADVERSARY, layout.workspace/'adversary.py')
    with tempfile.TemporaryFile() as out:
        result = sandbox.run([str(PYTHON), '-I', 'adversary.py', json.dumps(targets)], layout,
                             proxy_port=proxy_port, token=token, limits=limits, stdout=out, stderr=out)
        out.seek(0)
        text = out.read().decode()
    assert result.returncode == 0 and result.stopped is None and result.survivors == [], text
    return json.loads(text.splitlines()[-1])


@native
def test_escape_suite_against_real_listeners(tmp_path, custodian):
    from tests.test_campaign_watch import fixture as watch_fixture

    custodian_port, runtime_dir = custodian
    layout = make_layout(tmp_path/'session-a')
    other = make_layout(tmp_path/'session-b')
    (other.home/'marker').write_text('other session state')
    outside = tmp_path.resolve()/'published-snapshots'
    outside.mkdir()
    short = Path(tempfile.mkdtemp(prefix='cur-', dir='/tmp')).resolve()
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(short/'s'))
    listener.listen()
    canary = ROOT/'.runtime'/f'escape-canary-{uuid.uuid4().hex}'
    (tmp_path/'watch').mkdir()
    try:
        with watch_fixture(tmp_path/'watch') as watch, running_proxy(tmp_path) as (proxy, proxy_port, upstream):
            targets = dict(
                read={'workspace brief (control)': str(layout.workspace/'brief.md'),
                      'knowledge (control)': str(layout.workspace/'knowledge'/'ontology.json'),
                      'actor custody token': str(runtime_dir/'actor.json'),
                      'project credentials': str(ROOT/'.runtime'/'credentials.json'),
                      'repository': str(ROOT/'AGENTS.md'),
                      'other session home': str(other.home/'marker'),
                      'proxy ledger': str(tmp_path/'ledger.jsonl')},
                list={'user home': str(Path.home()), 'project runtime': str(ROOT/'.runtime'),
                      'user ssh': str(Path.home()/'.ssh')},
                write={'scratch (control)': str(layout.workspace/'scratch'/'x'),
                       'submissions (control)': str(layout.workspace/'submissions'/'x'),
                       'drafts (control)': str(layout.workspace/'drafts'/'x'),
                       'knowledge': str(layout.workspace/'knowledge'/'x'),
                       'trace': str(layout.workspace/'trace'/'x'),
                       'workspace root': str(layout.workspace/'x'),
                       'project runtime': str(canary),
                       'published snapshots': str(outside/'x'),
                       'shared tmp': str(short/'x'),
                       'other session home': str(other.home/'x')},
                tcp={'custodian and playing service': custodian_port, 'pause gateway': watch.port,
                     'proxy (control)': proxy_port},
                udp={'custodian': custodian_port},
                unix={'outside socket': str(short/'s')},
                stat={'project credentials': str(ROOT/'.runtime'/'credentials.json'),
                      'user ssh': str(Path.home()/'.ssh'), 'other session home': str(other.home/'marker')},
                terminals=sorted(str(p) for p in Path('/dev').glob('ttys*'))[:4],
                other_pid=os.getpid())
            outcomes = run_adversary(layout, targets, proxy_port=proxy_port, token=proxy.token)
            assert upstream.requests == []
            assert watch.state.get('paused') is not True
    finally:
        listener.close()
        shutil.rmtree(short, ignore_errors=True)
        if canary.exists():
            canary.unlink()
    allowed = {name for name, outcome in outcomes.items() if outcome == 'allowed'}
    assert allowed == {'read workspace brief (control)', 'read knowledge (control)', 'write scratch (control)',
                       'write submissions (control)', 'write drafts (control)', 'tcp proxy (control)'}, outcomes
    assert not canary.exists() and not (outside/'x').exists() and not (other.home/'x').exists()


@native
def test_no_state_survives_into_the_next_session(tmp_path):
    first, second = make_layout(tmp_path/'one'), make_layout(tmp_path/'two')
    script = ("import os,sys,json; open(os.environ['HOME']+'/note','w').write('kept');"
              "open('scratch/note','w').write('kept'); print('ok')")
    assert sandbox.run([str(PYTHON), '-I', '-c', script], first).returncode == 0
    probe = ("import os,json; r={}\n"
             "for p in sys.argv[1:]:\n"
             "    try: open(p).read(); r[p]='allowed'\n"
             "    except Exception as e: r[p]='denied'\n"
             "r['home empty']=os.listdir(os.environ['HOME'])==[]\n"
             "print(json.dumps(r))").replace('import os,json', 'import os,json,sys')
    with tempfile.TemporaryFile() as out:
        result = sandbox.run([str(PYTHON), '-I', '-c', probe, str(first.home/'note'),
                              str(first.workspace/'scratch'/'note')], second, stdout=out)
        out.seek(0)
        outcome = json.loads(out.read().decode().splitlines()[-1])
    assert result.returncode == 0
    assert outcome == {str(first.home/'note'): 'denied', str(first.workspace/'scratch'/'note'): 'denied',
                       'home empty': True}


@native
def test_the_proxy_is_the_only_channel_out(tmp_path):
    layout = make_layout(tmp_path/'s')
    script = ("import http.client,json,os,sys\n"
              "c=http.client.HTTPConnection('127.0.0.1',int(sys.argv[1]),timeout=10)\n"
              "body=json.dumps(dict(model='model-a',max_tokens=10,messages=[])).encode()\n"
              "for token in (os.environ['CURATOR_PROXY_TOKEN'],'forged'):\n"
              "    c.request('POST','/v1/messages',body=body,headers={'x-api-key':token})\n"
              "    r=c.getresponse(); r.read(); print(r.status)\n")
    with running_proxy(tmp_path) as (proxy, port, upstream), tempfile.TemporaryFile() as out:
        result = sandbox.run([str(PYTHON), '-I', '-c', script, str(port)], layout, proxy_port=port,
                             token=proxy.token, stdout=out)
        out.seek(0)
        statuses = out.read().decode().split()
    assert result.returncode == 0 and statuses == ['200', '401'] and len(upstream.requests) == 1


SPIN = 'while True: pass'
MEMORY = 'import time\nb=[]\nwhile True:\n    b.append(bytearray(16<<20)); time.sleep(.01)'
DISK = 'i=0\nwhile True:\n    open(f"scratch/f{i}","wb").write(b"x"*(1<<20)); i+=1'
FORKS = ('import subprocess,sys,time\nkids=[]\n'
         'try:\n    for i in range(64): kids.append(subprocess.Popen(["/bin/sleep","30"]))\n'
         'except OSError: print("fork refused"); sys.exit(3)\ntime.sleep(30)')
BIG_FILE = 'open("scratch/big","wb").write(b"x"*(8<<20))'
# Hide data from the disk count: a mode-000 directory, or a path too long to stat.
HIDDEN = ('import os,time\nos.makedirs("scratch/h"); open("scratch/h/f","wb").write(b"x"*(4<<20))\n'
          'os.chmod("scratch/h",0)\ntime.sleep(30)')
LONG_PATH = ('import os,time\nos.chdir("scratch")\n'
             'for i in range(9): os.mkdir("d"*120); os.chdir("d"*120)\n'
             'open("f"*250,"wb").write(b"x")\ntime.sleep(30)')


@native
@pytest.mark.parametrize('name, code, limits, expect', [
    ('memory', MEMORY, sandbox.Limits(memory_bytes=256 << 20, wall_seconds=30), 'memory limit'),
    ('disk', DISK, sandbox.Limits(disk_bytes=16 << 20, wall_seconds=30), 'disk limit'),
    ('processes', FORKS, sandbox.Limits(processes=8, wall_seconds=30), 'process limit'),
    ('wall clock', 'import time; time.sleep(30)', sandbox.Limits(wall_seconds=1), 'wall-clock limit'),
    ('cpu', SPIN, sandbox.Limits(cpu_seconds=1, wall_seconds=30), 'killed'),
    ('file size', BIG_FILE, sandbox.Limits(file_bytes=1 << 20, wall_seconds=30), 'killed'),
    ('hidden directory', HIDDEN, sandbox.Limits(wall_seconds=30), 'disk unmeasurable'),
    ('long path', LONG_PATH, sandbox.Limits(wall_seconds=30), 'disk unmeasurable'),
])
def test_resource_exhaustion_is_stopped(tmp_path, name, code, limits, expect):
    layout = make_layout(tmp_path/'s')
    started = time.monotonic()
    result = sandbox.run([str(PYTHON), '-I', '-c', code], layout, limits=limits,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for directory, _dirs, _files in os.walk(layout.workspace/'scratch'):
        os.chmod(directory, 0o700)  # let the test directory be removed after the hidden-directory case
    if (layout.workspace/'scratch'/'h').exists():
        os.chmod(layout.workspace/'scratch'/'h', 0o700)
    assert result.survivors == []
    assert time.monotonic() - started < 25
    if expect == 'killed':
        assert result.stopped is None and result.returncode not in (0, None)
    elif name == 'processes':
        # The kernel's per-user process cap or the supervisor's tree count, whichever binds first.
        assert result.stopped == 'process limit' or result.returncode == 3
    else:
        assert result.stopped == expect
