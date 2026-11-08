"""Run a real coding-agent host inside the curator sandbox against a mock provider ($0; #451).

The host reaches only the model proxy, which forwards to a local stand-in that answers in the
Messages streaming shape. It records which routes the host asked for, what it wrote to its home,
and whether it finished. Usage: python -m tests.curator_host_probe <claude-binary> <out.json>
"""
from __future__ import annotations

from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

from harness.curator import sandbox
from harness.curator.proxy import ANTHROPIC, ModelProxy, Price

REPLY = 'probe-reply-ok'


def sse(events):
    return b''.join(f'event: {e["type"]}\ndata: {json.dumps(e)}\n\n'.encode() for e in events)


def answer(model):
    return sse([
        dict(type='message_start', message=dict(id='msg_probe', type='message', role='assistant', model=model,
                                                content=[], stop_reason=None, stop_sequence=None,
                                                usage=dict(input_tokens=1000, output_tokens=1))),
        dict(type='content_block_start', index=0, content_block=dict(type='text', text='')),
        dict(type='content_block_delta', index=0, delta=dict(type='text_delta', text=REPLY)),
        dict(type='content_block_stop', index=0),
        dict(type='message_delta', delta=dict(stop_reason='end_turn', stop_sequence=None),
             usage=dict(output_tokens=5)),
        dict(type='message_stop'),
    ])


def tool_call(model, command):
    """A turn that asks the host to run one Bash command."""
    return sse([
        dict(type='message_start', message=dict(id='msg_tool', type='message', role='assistant', model=model,
                                                content=[], stop_reason=None, stop_sequence=None,
                                                usage=dict(input_tokens=1000, output_tokens=1))),
        dict(type='content_block_start', index=0, content_block=dict(type='tool_use', id='toolu_probe',
                                                                     name='Bash', input={})),
        dict(type='content_block_delta', index=0, delta=dict(type='input_json_delta',
                                                             partial_json=json.dumps(dict(command=command)))),
        dict(type='content_block_stop', index=0),
        dict(type='message_delta', delta=dict(stop_reason='tool_use', stop_sequence=None),
             usage=dict(output_tokens=20)),
        dict(type='message_stop'),
    ])


def tool_results(body) -> list[str]:
    texts = []
    for message in body.get('messages', []):
        for block in message.get('content') if isinstance(message.get('content'), list) else []:
            if isinstance(block, dict) and block.get('type') == 'tool_result':
                content = block.get('content')
                texts.append(content if isinstance(content, str) else json.dumps(content))
    return texts


def main(binary: str, out: str, mode: str = 'text') -> int:
    seen = []
    secret = Path(__file__).resolve().parents[1]/'.runtime'/'credentials.json'
    command = (f'echo written > scratch/from-bash && cat scratch/from-bash && '
               f'(head -c 1 "{secret}" >/dev/null 2>&1 && echo SECRET-READABLE || echo secret-denied) && '
               f'(ls ~/../.. >/dev/null 2>&1 && echo LISTED-USERS || echo users-denied)')

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['content-length'])))
            results = tool_results(body)
            seen.append(dict(path=self.path, model=body.get('model'), stream=body.get('stream'),
                             key_is_real=self.headers.get('x-api-key') == 'probe-provider-key',
                             tool_results=results))
            if mode == 'tool' and body.get('stream') and not results:
                data = tool_call(body.get('model'), command)
            else:
                data = answer(body.get('model')) if body.get('stream') else json.dumps(dict(
                id='msg_probe', type='message', role='assistant', model=body.get('model'),
                content=[dict(type='text', text=REPLY)], stop_reason='end_turn',
                usage=dict(input_tokens=1000, output_tokens=5))).encode()
            self.send_response(200)
            self.send_header('content-type', 'text/event-stream' if body.get('stream') else 'application/json')
            self.send_header('content-length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    base = Path(tempfile.mkdtemp(prefix='curator-host-probe-')).resolve()
    workspace, home = base/'workspace', base/'home'
    for name in ('trace', 'knowledge', 'submissions', 'drafts', 'scratch'):
        (workspace/name).mkdir(parents=True)
    home.mkdir()
    ledger = base/'ledger.jsonl'
    prices = {'probe-model': Price(Decimal(1), Decimal(5))}
    proxy = ModelProxy(provider=ANTHROPIC, upstream=f'http://127.0.0.1:{upstream.server_port}',
                       key='probe-provider-key', prices=prices, cap_usd=Decimal('0.5'), ledger=ledger)
    port = proxy.start()
    tool = Path(os.path.realpath(binary))
    layout = sandbox.Layout(workspace=workspace, home=home, writable=tuple(workspace/n for n in
                            ('submissions', 'drafts', 'scratch')), tools=(tool,))
    env = dict(ANTHROPIC_BASE_URL=f'http://127.0.0.1:{port}', ANTHROPIC_API_KEY=proxy.token,
               CLAUDE_CODE_DISABLE_AUTO_MEMORY='1', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
               CLAUDE_CODE_TMPDIR=str(workspace/'scratch'))
    log = base/'host.log'
    with log.open('wb') as stream:
        result = sandbox.run([str(tool), '--bare', '-p', 'Reply with the word ok.', '--model', 'probe-model',
                              '--no-session-persistence', '--output-format', 'json',
                              '--max-turns', '3', '--allowedTools', 'Bash'],
                             layout, proxy_port=port, token=proxy.token, extra_env=env,
                             limits=sandbox.Limits(wall_seconds=120), stdout=stream, stderr=stream)
    proxy.close()
    upstream.shutdown()
    text = log.read_text(errors='replace')
    record = dict(returncode=result.returncode, stopped=result.stopped, seconds=round(result.seconds, 2),
                  peak_memory_mb=result.peak_memory_bytes >> 20, survivors=result.survivors,
                  upstream_requests=seen, reply_seen=REPLY in text,
                  proxy_ledger=[json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else [],
                  home_files=sorted(str(p.relative_to(home)) for p in home.rglob('*')),
                  output_tail=text[-1500:])
    Path(out).write_text(json.dumps(record, indent=1, default=str))
    print(json.dumps({k: record[k] for k in ('returncode', 'stopped', 'seconds', 'reply_seen')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))
