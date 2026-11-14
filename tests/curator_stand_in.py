"""A local stand-in for OpenRouter's chat completions, for the curator host's tests and dry runs.

It streams scripted server-sent events in OpenRouter's shape (a processing comment, tool-call
deltas, a finish chunk and a final `usage` chunk that carries `cost`). It makes no network
request and spends nothing. The script is a short curator session driven by what the host's
tools returned: read the brief, the frame list and the game name, then view a frame, run the
workbench, write one valid submission and one draft, and finish.

    python -m tests.curator_stand_in [--mode good|no-usage]   # prints its origin, serves until killed
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import sys
import threading
import time

ROUTE = '/api/v1/chat/completions'


def _text(message: dict) -> str:
    content = message.get('content')
    if isinstance(content, str):
        return content
    return ''.join(part.get('text', '') for part in content or [] if isinstance(part, dict))


def script(messages: list[dict], attack: str | None = None, *, unfiled: bool = False) -> list[tuple[str, dict]] | None:
    """The tool calls for the next turn, or None for a plain-text turn.

    With `attack` (the path of a planted secret), the session instead tries to read it, write
    outside the writable directories and list the workspace's parent, then finishes.
    """
    turns = sum(1 for message in messages if message.get('role') == 'assistant')
    if attack is not None:
        return [('read_file', {'path': attack}), ('write_file', {'path': 'knowledge/facts.jsonl', 'content': 'x'}),
                ('write_file', {'path': '/tmp/curator-escape', 'content': 'x'}),
                ('write_file', {'path': 'trace/manifest.json', 'content': 'x'}), ('list_dir', {'path': '..'}),
                ('read_file', {'path': '../../../credentials.json'})] if turns == 0 else (
                    [('finish', {'summary': 'attacks done'})] if turns == 1 else None)
    grooming = any('Session kind: grooming.' in _text(m) for m in messages if m.get('role') == 'user')
    if grooming:
        if turns == 0:
            return [('read_file', {'path': 'brief.md'}), ('read_file', {'path': 'knowledge/facts.jsonl'}),
                    ('read_file', {'path': 'knowledge/ontology/types.json'}),
                    ('read_file', {'path': 'grooming.md'}), ('read_file', {'path': 'trace/manifest.json'})]
        if turns == 1:
            tools = '\n'.join(_text(m) for m in messages if m.get('role') == 'tool')
            version = re.search(r'Published knowledge: `(v[0-9]+)`', tools).group(1)
            # This stand-in's admission publishes f1. Its grooming files that evidence.
            article = dict(schema='curator-fact/3', record='article', id='a1', title='Stand-in subject',
                           lead='A useful observed relation. Check before relying on it.',
                           body=[dict(text='An observed relation.', facts=['f1'])], links=[])
            submission = dict(schema='curator-submission/1', base_version=version, summary='stand-in grooming',
                              changes=([dict(op='add_type', type=dict(schema='curator-type/1', name='unfiled',
                                                                    description='a valid change with no filing', fields=[]))]
                                       if unfiled else [dict(op='add_article', article=article)]))
            return [('write_file', {'path': 'submissions/grooming/submission.json', 'content': json.dumps(submission)})]
        return [('finish', {'summary': 'stand-in grooming done'})] if turns == 2 else None
    if turns == 0:
        return [('read_file', {'path': 'brief.md'}), ('list_dir', {'path': 'trace/frames'}),
                ('read_file', {'path': 'knowledge/knowledge.json'})]
    if turns == 1:
        tools = '\n'.join(_text(m) for m in messages if m.get('role') == 'tool')
        version = re.search(r'Published knowledge: `(v[0-9]+)`', tools).group(1)
        frames = re.findall(r'file\t[0-9]+\t(.+?)\.png', tools)
        game = re.search(r'"game": "([^"]+)"', tools).group(1)
        submission = dict(schema='curator-submission/1', base_version=version, summary='stand-in: one control and one fact',
                          changes=[dict(op='add_type', type=dict(schema='curator-type/1', name='control',
                                                                 description='what an input does', fields=['input', 'effect'])),
                                   dict(op='add_fact', fact=dict(schema='curator-fact/3', record='fact', id='f1', type='control',
                                                                 text='stand-in statement', scope=dict(game=game),
                                                                 citations=frames[:1], subject='stand-in subject'))])
        return [('view_frame', {'frames': frames[:2]}), ('run_workbench', {'args': ['--help']}),
                ('write_file', {'path': 'submissions/stand-in/submission.json', 'content': json.dumps(submission)}),
                ('write_file', {'path': 'drafts/notes/notes.md', 'content': 'unfinished'}),
                ('read_file', {'path': '../escape'})]
    if turns == 2:
        return [('finish', {'summary': 'stand-in session done'})]
    return None


def stream(calls: list[tuple[str, dict]] | None, usage: dict | None, turn: int) -> bytes:
    delta = dict(role='assistant')
    if calls:
        delta['tool_calls'] = [dict(index=i, id=f'call-{turn}-{i}', type='function',
                                    function=dict(name=name, arguments=json.dumps(arguments)))
                               for i, (name, arguments) in enumerate(calls)]
    else:
        delta['content'] = 'done'
    chunks = [dict(id=f'gen-{turn}', model='stand-in-backend', provider='stand-in', choices=[dict(index=0, delta=delta, finish_reason=None)]),
              dict(id=f'gen-{turn}', model='stand-in-backend', provider='stand-in',
                   choices=[dict(index=0, delta={}, finish_reason='tool_calls' if calls else 'stop')])]
    if usage is not None:
        chunks.append(dict(id=f'gen-{turn}', model='stand-in-backend', provider='stand-in', choices=[], usage=usage))
    return (b': OPENROUTER PROCESSING\n\n' + b''.join(b'data: ' + json.dumps(c).encode() + b'\n\n' for c in chunks)
            + b'data: [DONE]\n\n')


class StandIn:
    """`rate-limit-once` refuses the first request with a server retry hint; otherwise `good`.

    `rate-limit-veto` adds the server's no-retry instruction to that refusal.

    `grooming-unfiled` submits a valid type addition without filing the admission fact.

    `no-usage` omits usage (the proxy then fails closed).
    """

    def __init__(self, mode: str = 'good', cost: float = 0.0012, delay: float = 0.0, attack: str | None = None):
        self.mode, self.cost, self.delay, self.attack = mode, cost, delay, attack
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['content-length'])))
                outer.requests.append(dict(path=self.path, headers={k.lower(): v for k, v in self.headers.items()}, body=body))
                if self.path != ROUTE:
                    self.send_response(404)
                    self.send_header('content-length', '0')
                    self.end_headers()
                    return
                time.sleep(outer.delay)
                if outer.mode in ('rate-limit-once', 'rate-limit-veto') and len(outer.requests) == 1:
                    data = json.dumps(dict(error=dict(code=429, message='synthetic admission timeout'))).encode()
                    self.send_response(429)
                    self.send_header('content-type', 'application/json')
                    self.send_header('retry-after', '0')
                    if outer.mode == 'rate-limit-veto':
                        self.send_header('x-should-retry', 'false')
                    self.send_header('content-length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                turn = sum(1 for m in body['messages'] if m.get('role') == 'assistant')
                usage = None if outer.mode == 'no-usage' else dict(
                    prompt_tokens=1000 + 100 * turn, completion_tokens=40, total_tokens=1040 + 100 * turn, cost=outer.cost,
                    prompt_tokens_details=dict(cached_tokens=800 if turn else 0, cache_write_tokens=0),
                    completion_tokens_details=dict(reasoning_tokens=10))
                data = stream(script(body['messages'], outer.attack, unfiled=outer.mode == 'grooming-unfiled'), usage, turn)
                self.send_response(200)
                self.send_header('content-type', 'text/event-stream')
                self.send_header('content-length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        class Server(ThreadingHTTPServer):
            def handle_error(self, request, client_address):
                # A proxy that closes a kept-alive connection resets it; that is not a failure of the stand-in.
                if not isinstance(sys.exc_info()[1], ConnectionError):
                    super().handle_error(request, client_address)

        self.server = Server(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


if __name__ == '__main__':
    options = argparse.ArgumentParser()
    options.add_argument('--mode', default='good', choices=['good', 'no-usage'])
    stand_in = StandIn(options.parse_args().mode)
    print(stand_in.url, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        sys.exit(0)
