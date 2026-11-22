"""Synthetic sessions for the curator's tests. No game, no provider.

`make_long_session` builds a sealed session with many steps, for the window tests (#460). Each actor has
`steps` operations, one frame per operation and one `computer_input` tool call per operation (its result
names the operation). Every third operation is preceded by a `player_memory_read` call that names no
operation, the kind of call a window assigns by position. Each actor has a final report; the session has a
handoff packet.

`LiveWriter` runs a growing session in a child process, for the snapshot tests (#837): a real
`harness.computer.store.SessionStore` in write-ahead-log mode with the custodian's quarter-second timeout,
and beside it the files the driver and host write, in their order. Run as `python -m tests.curator_trace
RUN`, it reads one JSON command per line and answers each with one JSON line that carries `busy`, the
number of store calls that failed on a locked database. At `close` it runs the custodian's own close-out,
`tools.campaign_run.close_store`, which writes the closing marker, waits within the bound for an admitted
read and then closes the store.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import time
import uuid

from PIL import Image

from harness.trace.stores import CURATOR_READ_LOCK

SESSION_ID = 'a' * 32
ROOT = Path(__file__).resolve().parents[1]


def png(color) -> bytes:
    stream = io.BytesIO()
    Image.new('RGB', (4, 4), color).save(stream, format='PNG')
    return stream.getvalue()


def frame_id(actor: int, step: int, session_id: str = SESSION_ID) -> str:
    return f'{session_id}-{actor * 1000 + step}'


def record_package(session: Path, *, labels: dict, schema: str = 'campaign-run/12',
                   session_id: str = SESSION_ID, live: bool = False) -> None:
    source_commit = 'c' * 40
    current = dict(live_knowledge_updates=live) if schema == 'campaign-run/12' else {}
    package = json.dumps(dict(schema=schema, session=session_id, source_commit=source_commit, **current,
                              labels=labels, private_files={'private-note': 'raw package sentinel'})).encode()
    (session/'manifest.json').write_bytes(package)
    (session/'watch-start.json').write_text(json.dumps(dict(
        schema='campaign-watch-start/4', session=session_id, source_commit=source_commit,
        manifest_sha256=hashlib.sha256(package).hexdigest(), started_wall=1.0, started_monotonic=1.0,
        viewer_port=54321)))


def make_long_session(root: Path, name: str = 's1', steps: int = 12, actors: tuple[str, ...] = ('001', '002'),
                      *, session_id: str = SESSION_ID) -> Path:
    session = root/name
    (session/'sources').mkdir(parents=True)
    (session/'contexts').mkdir()
    db = sqlite3.connect(session/'session.sqlite3')
    db.executescript('''
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources(id TEXT PRIMARY KEY, metadata TEXT NOT NULL, bytes INTEGER NOT NULL);
        CREATE TABLE operations(id TEXT PRIMARY KEY, actor TEXT NOT NULL, kind TEXT NOT NULL, created_wall REAL NOT NULL,
            deadline REAL NOT NULL, input_json TEXT NOT NULL, final_json TEXT);
        CREATE TABLE native_intents(id TEXT PRIMARY KEY, operation TEXT NOT NULL, receipt TEXT, source TEXT, timing TEXT NOT NULL);
        CREATE TABLE collections(native_id TEXT PRIMARY KEY, receipt TEXT NOT NULL, source TEXT);''')
    db.execute("INSERT INTO metadata VALUES('session', ?)", (json.dumps(session_id),))
    for number, directory in enumerate(actors, 1):
        actor_id = f'{number:x}' * 32
        actor_dir = session/'actors'/directory
        actor_dir.mkdir(parents=True)
        (actor_dir/'frozen.json').write_text(json.dumps(dict(actor_id=actor_id)))
        (actor_dir/'prompt.txt').write_text(f'Play the game as actor {directory}.')
        (actor_dir/'player-final.txt').write_text(f'Actor {directory} report: everything, including the end.')
        events = []
        for step in range(1, steps + 1):
            sid, op = frame_id(number, step, session_id), f'op-{number}-{step}'
            data = png((step * 7 % 256, number * 40, 90))
            (session/'sources'/f'{sid}.png').write_bytes(data)
            db.execute('INSERT INTO sources VALUES(?,?,?)',
                       (sid, json.dumps(dict(source_id=sid, sha256=hashlib.sha256(data).hexdigest())), len(data)))
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', (op, actor_id, 'input', float(number * 1000 + step), 9e9,
                       json.dumps([dict(type='key', key='RIGHT', modifiers=[])]), json.dumps(dict(status='completed'))))
            db.execute('INSERT INTO native_intents VALUES(?,?,NULL,?, ?)', (f'n-{number}-{step}', op, sid, 't'))
            if step % 3 == 0:
                events += [dict(type='tool-start', tool_call_id=f'm{step}', tool='player_hint', arguments=dict(text=f'hint at step {step}', source_ids=[], intent='remember', cites=[])),
                           dict(type='tool-result', tool_call_id=f'm{step}', tool='player_hint', wall_time='t',
                                result=dict(isError=False, content=[dict(type='text', text=json.dumps(dict(records=[])))]))]
            events += [dict(type='tool-start', tool_call_id=f'c{step}', tool='computer_input',
                            arguments=dict(actions=[dict(type='key', key='RIGHT', modifiers=[])])),
                       dict(type='tool-result', tool_call_id=f'c{step}', tool='computer_input', wall_time='t',
                            result=dict(isError=False, content=[dict(type='text', text=json.dumps(dict(
                                schema='player-computer-result/1', operation_id=op, status='completed',
                                source=dict(source_id=sid))))]))]
        (actor_dir/'host.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    db.commit()
    db.close()
    (session/'contexts'/'ctx.json').write_text(json.dumps(dict(
        schema='player-handoff-context/1', context_id='ctx', summary='carry on', knowledge={})))
    return session


class LiveWriter:
    """A growing session in a child process; calling it sends one command and returns its answer."""

    def __init__(self, run: Path, *, read_lock: bool = True, session_id: str = SESSION_ID):
        run.mkdir()
        if read_lock:
            (run/CURATOR_READ_LOCK).touch()  # the runner creates it before the custodian starts
        record_package(run, labels=dict(world=None, lineage=None, admission=None), session_id=session_id)
        self.run = run
        self.process = subprocess.Popen([sys.executable, '-m', 'tests.curator_trace', str(run), session_id],
                                        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        assert self.answer() == dict(ready=True, busy=0)

    def send(self, **command) -> None:
        self.process.stdin.write(json.dumps(command) + '\n')
        self.process.stdin.flush()

    def answered(self) -> bool:
        return bool(select.select([self.process.stdout], [], [], 0)[0])

    def answer(self) -> dict:
        line = self.process.stdout.readline()
        if not line:
            raise AssertionError(f'the writer exited with {self.process.wait()}')
        value = json.loads(line)
        if 'error' in value:
            raise AssertionError(f"the writer failed: {value['error']}")
        return value

    def __call__(self, **command) -> dict:
        self.send(**command)
        return self.answer()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()


class _Writer:
    """The child side of `LiveWriter`: the custodian's store, the driver's files and the host's log."""

    LIMITS = dict(max_inputs=10**6, max_requests=10**6, max_frames=10**6, max_bytes=10**9)

    def __init__(self, run: Path, session_id: str):
        from harness.computer.store import SessionStore
        self.run, self.session = run, session_id
        self.store = SessionStore(run, session_id, self.LIMITS, time.monotonic() + 3600)
        self.busy, self.capture, self.calls, self.index = 0, 0, 0, 0
        self.actor: dict | None = None
        self.natives: dict[str, str] = {}
        self.half = b''

    def call(self, method: str, *args, **kwargs):
        try:
            return getattr(self.store, method)(*args, **kwargs)
        except sqlite3.OperationalError:
            self.busy += 1
            raise

    @staticmethod
    def line(event: dict) -> bytes:
        return (json.dumps(dict(event, wall_time='2026-11-20T00:00:00+00:00')) + '\n').encode()

    def log(self, event: dict, *, split: bool = False) -> None:
        line = self.line(event)
        with (self.actor['directory']/'host.jsonl').open('ab') as stream:
            if split:
                stream.write(line[:len(line) // 2])
                stream.flush()
                time.sleep(.002)
                line = line[len(line) // 2:]
            stream.write(line)

    def write(self, path: Path, value) -> None:
        with path.open('x') as stream:
            stream.write(value if isinstance(value, str) else json.dumps(value, sort_keys=True) + '\n')

    def new_actor(self, frozen: bool = True) -> dict:
        identity, token = uuid.uuid4().hex, uuid.uuid4().hex + uuid.uuid4().hex
        self.call('add_actor', identity, hashlib.sha256(token.encode()).hexdigest())
        self.index += 1
        directory = self.run/'actors'/f'{self.index:03d}'
        directory.mkdir(parents=True)
        self.actor = dict(id=identity, directory=directory)
        self.write(directory/'actor.json', dict(schema='player-adapter/2', base_url='http://127.0.0.1:54321',
                                                session=self.session, actor_id=identity, token=token))
        self.write(directory/'route.json', dict(model=dict(id='synthetic'), api_key_env='SYNTHETIC_KEY'))
        self.write(directory/'mcp.json', dict(servers=dict(player=dict(command='synthetic'))))
        self.write(directory/'context.txt', 'Play the game.')
        self.write(directory/'prompt.txt', f'You are actor {identity}.')
        (directory/'host.jsonl').touch()
        if frozen:
            self.freeze()
        return dict(directory=directory.name, actor_id=identity)

    def freeze(self) -> dict:
        directory = self.actor['directory']
        names = ('actor.json', 'route.json', 'mcp.json', 'context.txt', 'prompt.txt')
        self.write(directory/'frozen.json', dict(schema='player-host-inputs/4', actor_id=self.actor['id'],
            session=self.session, knowledge_updates=None,
            files={n: hashlib.sha256((directory/n).read_bytes()).hexdigest() for n in names}))
        self.log(dict(type='host-start', schema='player-host/10', telemetry_version=10, actor_id=self.actor['id']))
        return {}

    def frame(self) -> tuple[dict, bytes]:
        self.capture += 1
        data = png((self.capture % 256, 40, 90))
        metadata = dict(schema='computer-source/1', source_id=f'{self.session}-{self.capture}', session=self.session,
                        capture_id=self.capture, sha256=hashlib.sha256(data).hexdigest(), media_type='image/png',
                        presented_ms=self.capture, received_wall=time.time(), width=4, height=4, window_width=4,
                        window_height=4, viewport=[0, 0, 4, 4])
        return self.call('put_source', metadata, data, self.actor['id']), data

    @staticmethod
    def result(call: str, tool: str, operation: dict) -> dict:
        """A host's tool result for one operation: the short text the model reads and the full record beside it."""
        return dict(type='tool-result', tool_call_id=call, tool=tool, result=dict(
            isError=False, content=[dict(type='text', text=json.dumps(dict(schema='player-computer-result/2',
                                                                            status=operation['status'])))],
            structuredContent=dict(schema='player-computer-operation/1', operation_id=operation['operation_id'],
                                   status=operation['status'])))

    def step(self, unknown: bool = False, partial: bool = False, hint: bool = False, split: bool = False) -> dict:
        self.calls += 1
        if hint:
            self.log(dict(type='tool-start', tool_call_id=f'h{self.calls}', tool='player_hint',
                          arguments=dict(text=f'hint {self.calls}', source_ids=[])))
            self.log(dict(type='tool-result', tool_call_id=f'h{self.calls}', tool='player_hint',
                          result=dict(isError=False, content=[dict(type='text', text='{}')])))
        call, actions = f'c{self.calls}', [dict(type='key', key='RIGHT', modifiers=[])]
        self.log(dict(type='tool-start', tool_call_id=call, tool='computer_input', arguments=dict(actions=actions)))
        operation = dict(schema='computer-operation/1', operation_id=uuid.uuid4().hex, session=self.session,
                         actor_id=self.actor['id'], kind='input', status='pending', created_wall=time.time(),
                         deadline_monotonic=time.monotonic() + 15, receipts=[], source=None, remaining={},
                         reason='Original operation in progress', handoff=None)
        self.call('begin', operation, actions, 1)
        native = uuid.uuid4().hex
        self.natives[operation['operation_id']] = native
        self.call('native_intent', operation['operation_id'], native)
        if unknown:
            receipt = dict(schema='computer-transport/2', id=native, session=self.session, disposition='unknown')
            self.call('native_result', native, receipt, None, {})
            operation.update(status='unknown', receipts=[receipt])
        else:
            metadata, _ = self.frame()
            receipt = dict(schema='computer-receipt/2', id=native, session=self.session, disposition='delivered')
            self.call('native_result', native, receipt, metadata['source_id'], {})
            operation.update(status='completed', receipts=[receipt], source=metadata)
        self.call('finish', operation)  # the terminal row commits before the host hears the result
        if partial:  # the host is held mid-line until `finish_line`
            line = self.line(self.result(call, 'computer_input', operation))
            self.half = line[len(line) // 2:]
            with (self.actor['directory']/'host.jsonl').open('ab') as stream:
                stream.write(line[:len(line) // 2])
        else:
            self.log(self.result(call, 'computer_input', operation), split=split)
        return dict(operation_id=operation['operation_id'])

    def finish_line(self) -> dict:
        with (self.actor['directory']/'host.jsonl').open('ab') as stream:
            stream.write(self.half)
        self.half = b''
        return {}

    def collect(self, operation_id: str) -> dict:
        self.calls += 1
        call = f'r{self.calls}'
        self.log(dict(type='tool-start', tool_call_id=call, tool='computer_result',
                      arguments=dict(operation_id=operation_id)))
        native = self.natives[operation_id]
        metadata, _ = self.frame()
        self.call('add_collection', native, dict(schema='computer-receipt/2', id=native, session=self.session,
                                                 disposition='delivered'), metadata['source_id'])
        self.log(self.result(call, 'computer_result', dict(operation_id=operation_id, status='unknown')))
        return dict(source_id=metadata['source_id'])

    def handoff(self) -> dict:
        """Seal the actor, settle its host and confirm it quiescent, as the driver does at a handoff."""
        self.calls += 1
        call = f'x{self.calls}'
        self.log(dict(type='tool-start', tool_call_id=call, tool='player_handoff', arguments=dict(summary='go on')))
        operation = dict(schema='computer-operation/1', operation_id=uuid.uuid4().hex, session=self.session,
                         actor_id=self.actor['id'], kind='handoff', status='sealed', created_wall=time.time(),
                         deadline_monotonic=time.monotonic() + 15, receipts=[], source=None, remaining={},
                         reason='Actor sealed', handoff=None)
        self.call('begin', operation, None, 0)
        self.call('finish', operation, seal_actor=True)
        self.log(self.result(call, 'player_handoff', operation))
        self.log(dict(type='settled', ok=True, reason='handoff'))
        self.call('set_actor_stage', self.actor['id'], 'quiescent')
        return dict(operation_id=operation['operation_id'])

    def play(self, seconds: float, handoffs: int = 0, minimum: int = 50) -> dict:
        """Sustained writes: steps as fast as the store takes them, for `seconds` and at least `minimum`
        steps per actor, then a handoff and a fresh actor."""
        steps = 0
        for turn in range(handoffs + 1):
            end, first = time.monotonic() + seconds, steps
            while time.monotonic() < end or steps - first < minimum:
                steps += 1
                self.step(hint=steps % 3 == 0, split=steps % 5 == 0)
            if turn < handoffs:
                self.handoff()
                self.new_actor()
        return dict(steps=steps)

    def close(self) -> dict:
        """The custodian's real close-out: the closing marker, the wait for an admitted read, the store's close."""
        from tools.campaign_run import close_store
        errors: dict[str, str] = {}

        def attempt(name, function):
            try:
                return function()
            except BaseException as exc:
                errors[name] = f'{type(exc).__name__}: {exc}'

        started = time.monotonic()
        close_store(self.run, self.session, self.store.close, attempt)
        waited = time.monotonic() - started
        wal = self.run/'session.sqlite3-wal'
        return dict(errors=errors, waited=waited, wal=wal.stat().st_size if wal.exists() else 0)


def _serve(run: Path, session_id: str) -> None:
    writer = _Writer(run, session_id)
    print(json.dumps(dict(ready=True, busy=0)), flush=True)
    for line in sys.stdin:
        command = json.loads(line)
        name = command.pop('op')
        try:
            answer = getattr(writer, name)(**command)
        except Exception as exc:  # reported to the test, which fails on it
            answer = dict(error=f'{type(exc).__name__}: {exc}')
        print(json.dumps(dict(answer, busy=writer.busy)), flush=True)
        if name == 'close':
            return


if __name__ == '__main__':
    _serve(Path(sys.argv[1]), sys.argv[2])
