"""Evaluation core (ADR008, evaluation-record/1) on synthetic runs and a pure fake binding.

The runs are built with the real SessionStore and Memory schemas but contain no game
screenshots: a frame is a tiny generated PNG whose first pixels encode what the fake
binding "reads". These tests establish the core's contract, not any game reader.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3

from PIL import Image
import pytest

from harness.computer.store import SessionStore
from harness.evaluation.core.binding import FrameReading, Reading, Rung, Vital
from harness.evaluation.core.derive import guard_clock
from harness.evaluation.core.lineage import stitch
from harness.evaluation.core.pipeline import evaluate
from harness.evaluation.core.records import (CORE_VERSION, EvaluationError, RecordWriter, open_readonly, read_events, read_metadata,
    read_metrics, read_readings, read_requests, read_run_facts, read_steps, read_tool_calls, record_path)
from harness.evaluation.core.survival import (Observation, bootstrap_rmst, compare, kaplan_meier, logrank,
    restricted_mean, rmst)
from harness.player.memory import Memory
from tools.evaluate import main

SESSION = 'a' * 32
BASE = 1_700_000_000.0
MODES = ['loading', 'menu', 'in_play', 'prompt', 'dead', 'unknown']
THREATS = [None, 'none', 'low', 'high', 'lethal']
LIMITS = dict(max_inputs=10**6, max_requests=10**6, max_frames=10**6, max_bytes=10**9)


# ---------------------------------------------------------------------------------------------
# A pure fake binding: frames encode their reading in the first pixels of a 16x16 image.

@dataclass(frozen=True)
class F:
    mode: str = 'in_play'
    t: int | None = None
    threat: str | None = None
    death: bool = False
    critical: bool = False
    identity: int = 0
    vital: int = 255
    ate: bool = False
    fill: int = 0
    cause: bool = False


def png_bytes(frame: F) -> bytes:
    image = Image.new('RGB', (16, 16), (0, 0, 0))
    pixels = image.load()
    pixels[0, 0] = (MODES.index(frame.mode), 0, 0)
    t = (255, 255, 255) if frame.t is None else (frame.t >> 16, (frame.t >> 8) & 255, frame.t & 255)
    pixels[1, 0] = t
    pixels[2, 0] = (THREATS.index(frame.threat), int(frame.death), int(frame.critical))
    pixels[3, 0] = (frame.identity, 0, 0)
    pixels[4, 0] = (frame.vital, 0, 0)
    pixels[5, 0] = (int(frame.ate), int(frame.cause), 0)
    shade = (frame.fill * 37) % 256  # one fill step is a clearly visible change (over the 16-level delta)
    for x in range(16):
        for y in range(8, 16):
            pixels[x, y] = (shade, shade, shade)
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


class FakeBinding:
    binding_id = 'fake'
    binding_version = 3
    game_time_unit = 'seconds'
    long_activity_seconds = 900
    max_clock_jump_seconds = 7200
    map_region = (0, 8, 16, 16)
    movement_keys = frozenset({'h', 'j', 'k', 'l'})
    ladder = (Rung('play', 'In play', 'reader'), Rung('armed', 'Armed', 'human'), Rung('ate', 'Ate', 'reader'))

    def read_frame(self, png: Path) -> FrameReading:
        with Image.open(png) as image:
            pixels = image.convert('RGB').load()
        mode = MODES[pixels[0, 0][0]]
        raw = pixels[1, 0]
        t = None if raw == (255, 255, 255) else raw[0] * 65536 + raw[1] * 256 + raw[2]
        threat_code, death, critical = pixels[2, 0]
        identity = None if pixels[3, 0][0] == 0 else f'id{pixels[3, 0][0]}'
        vitals = (Vital('hunger', 'whole', pixels[4, 0][0] / 255, bool(critical)),) if mode == 'in_play' else ()
        readings = [Reading('mode', 1, mode, 0.9),
            Reading('clock', 1, t, 0.99) if t is not None else Reading('clock', 1, None, None, 'unreadable'),
            Reading('ate', 1, True, 0.8) if pixels[5, 0][0] else Reading('ate', 1, None, None, 'absent')]
        if death:
            readings.append(Reading('death_cause', 1, 'combat', 0.7))
        return FrameReading(mode, t, identity, vitals, THREATS[threat_code], 1 if THREATS[threat_code] else None,
            bool(death), tuple(readings))

    def severe_needs(self, values) -> list[str] | None:
        frame = values.get('core.frame')
        if not isinstance(frame, dict) or frame.get('mode') != 'in_play' or not frame.get('vitals'):
            return None
        return [v['name'] for v in frame['vitals'] if v['critical']]

    def rung_reached(self, rung: Rung, history) -> int | None:
        if rung.evidence == 'human':
            return None
        for index, frame in enumerate(history):
            if rung.id == 'play' and frame.mode == 'in_play':
                return index
            if rung.id == 'ate' and any(r.reader == 'ate' and r.value for r in frame.readings):
                return index
        return None


# ---------------------------------------------------------------------------------------------
# Synthetic run directories.

def iso(wall: float) -> str:
    return datetime.fromtimestamp(wall, timezone.utc).isoformat()


class Run:
    """Builds `session.sqlite3`, `sources/`, `actors/NNN/host.jsonl`, `manifest.json` and contexts."""

    def __init__(self, directory: Path, session: str = SESSION, base: float = BASE, hosts: bool = True) -> None:
        self.directory, self.session, self.base, self.hosts = directory, session, base, hosts
        directory.mkdir(parents=True, exist_ok=True)
        self.store = SessionStore(directory, session, LIMITS, 1e9)
        self.actors: list[str] = []
        self.host: dict[str, list[dict]] = {}
        self.count = 0
        self.captures = 0
        self.monotonic = 0.0
        self.requests = 0
        self.manifest: dict = {}
        self.records: dict[str, dict] = {}

    def actor(self, name: str | None = None) -> str:
        if self.actors:
            self.store.set_actor_stage(self.actors[-1], 'sealed')
        actor = name or f'{len(self.actors) + 1:032x}'
        self.store.add_actor(actor, hashlib.sha256(actor.encode()).hexdigest())
        self.actors.append(actor)
        self.host[actor] = [self.event(actor, 'host-start', schema='player-host/3', telemetry_version=3, actor_id=actor,
            session=self.session)]
        return actor

    def wall(self) -> float:
        return self.base + 10 * self.count

    def event(self, actor: str, kind: str, wall: float | str | None = None, **fields) -> dict:
        self.monotonic += 1
        value = dict(type=kind, monotonic_ms=self.monotonic, **fields)
        if wall is not None:
            value['wall_time'] = wall if isinstance(wall, str) else iso(wall)
        return value

    def request(self, actor: str, usage: dict | None = None, stop: str = 'toolUse', wall: float | None = None) -> str:
        """One logical request with a priced response."""
        self.requests += 1
        key = f'request-{self.requests}'
        start = self.monotonic + 1
        wall = self.wall() - 5 if wall is None else wall
        events = self.host[actor]
        events.append(self.event(actor, 'request-start', wall, request_id=key, logical_request_id=key))
        events.append(self.event(actor, 'request-fetch-start', wall, request_id=key))
        self.monotonic += 9
        events.append(self.event(actor, 'response-first-chunk', wall, request_id=key))
        self.monotonic += 190
        usage = self.usage() if usage is None else usage
        events.append(self.event(actor, 'response-complete', wall, request_id=key, stop_reason=stop,
            usage_available=bool(usage), usage=usage or None))
        # Fixed intervals make the latency figures exact: 200 ms response, 100 ms to the first chunk.
        events[-4]['monotonic_ms'], events[-3]['monotonic_ms'] = start, start + 10
        events[-2]['monotonic_ms'], events[-1]['monotonic_ms'] = start + 110, start + 200
        self.monotonic = start + 200
        return key

    @staticmethod
    def usage(cache_write: int = 1000, total: float = 0.01, cache_dollars: float = 0.004) -> dict:
        return dict(input=100, output=50, cacheRead=1000, cacheWrite=cache_write,
            cost=dict(total=total, cacheWrite=cache_dollars))

    def call(self, actor: str, tool: str, arguments: dict, result: object, *, key: str | None = None,
             error: bool = False, wall: float | None = None) -> None:
        key = key or f'request-{self.requests}'
        wall = self.wall() - 4 if wall is None else wall
        call_id = f'call-{len(self.host[actor])}'
        self.host[actor].append(self.event(actor, 'tool-start', wall, request_id=key, tool_call_id=call_id, tool=tool,
            arguments=arguments))
        content = [{'type': 'text', 'text': json.dumps(result)}]
        self.host[actor].append(self.event(actor, 'tool-result', wall, request_id=key, tool_call_id=call_id, tool=tool,
            result=dict(content=content, isError=error)))

    def step(self, actor: str, kind: str = 'input', actions: list | None = None, frame: F | None = None,
             status: str = 'completed', receipt: str = 'delivered', usage: dict | None = None,
             request: bool = True, handoff: dict | None = None, pending: bool = False) -> str:
        self.count += 1
        wall = self.wall()
        operation = f'{0x1000 + self.count:032x}'
        if self.hosts and request:
            self.request(actor, usage)
            tool = dict(input='computer_input', observe='computer_observe', handoff='player_handoff')[kind]
            self.call(actor, tool, dict(actions=actions or []), dict(operation_id=operation), wall=wall - 1)
        record = dict(schema='computer-operation/1', operation_id=operation, session=self.session, actor_id=actor,
            kind=kind, status=status, created_wall=wall, deadline_monotonic=1e9, receipts=[], source=None,
            remaining={}, reason='fixture', handoff=handoff)
        self.store.begin(record, actions if kind == 'input' else None, len(actions or []))
        native = f'native-{self.count}'
        if kind != 'handoff':
            self.store.native_intent(operation, native)
            metadata = None
            if frame is not None:
                png = png_bytes(frame)
                self.captures += 1
                metadata = dict(schema='computer-source/1', source_id=f'{self.session}-{self.captures}',
                    session=self.session, capture_id=self.captures, sha256=hashlib.sha256(png).hexdigest(),
                    media_type='image/png', presented_ms=self.captures, received_wall=wall, width=16, height=16,
                    window_width=16, window_height=16, viewport=[0, 0, 16, 16])
                self.store.put_source(metadata, png, actor)
                record['source'] = metadata
            self.store.native_result(native, dict(schema='computer-receipt/2', id=native, session=self.session,
                disposition=receipt, emitted_events=0 if receipt == 'rejected' else 1, reason='fixture', frame=None),
                metadata['source_id'] if metadata else None)
        self.records[operation] = record
        if not pending:
            self.store.finish(record)
        return operation

    def settle(self, operation: str) -> None:
        self.store.finish(self.records[operation])

    def finish(self, memory: Path | None = None, close: bool = True, settled: dict | None = None, **manifest) -> Path:
        """Write the host traces and manifest. `close=False` leaves the store open to keep growing.
        `settled` replaces the last actor's terminal `settled` fields (default: ok, task_complete)."""
        if close:
            self.store.close()
        for index, actor in enumerate(self.actors, 1):
            directory = self.directory / 'actors' / f'{index:03d}'
            directory.mkdir(parents=True, exist_ok=True)
            fields = dict(ok=True, reason='task_complete')
            if settled is not None and actor == self.actors[-1]:
                fields = settled
            events = [*self.host[actor], self.event(actor, 'settled', **fields,
                requests=sum(e['type'] == 'request-start' for e in self.host[actor]))]
            (directory / 'host.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
            (directory / 'actor.json').write_text(json.dumps(dict(schema='player-adapter/1', actor_id=actor)))
            (directory / 'context.txt').write_text('GUIDE')
            (directory / 'prompt.txt').write_text(f'ASSIGNMENT {index}')
        self.manifest = dict(schema='campaign-run/5', session=self.session, source_commit='fixture', **manifest)
        if memory is not None:
            self.manifest['player_store'] = str(memory)
        (self.directory / 'manifest.json').write_text(json.dumps(self.manifest))
        return self.directory

    def context(self, actor: str, records: list[str]) -> str:
        directory = self.directory / 'contexts'
        directory.mkdir(exist_ok=True)
        identity = f'{len(list(directory.iterdir())) + 1:032x}'
        (directory / f'{identity}.json').write_text(json.dumps(dict(schema='player-handoff-context/1', context_id=identity,
            session=self.session, actor_id=actor, summary='carry', grants_authority=False,
            knowledge=dict(records=[dict(id=r) for r in records], programs=[]))))
        return identity


def key(name: str) -> dict:
    return dict(type='key', key=name, modifiers=[])


def main_scenario(directory: Path, **options) -> Path:
    """The scenario used for most event and metric checks (see each assertion)."""
    run = Run(directory, **options)
    a = run.actor()
    step = lambda *args, **kwargs: run.step(a, *args, **kwargs)  # noqa: E731
    step('observe', [], F('loading'))
    step('input', [key('ENTER')], F('menu'))
    step('input', [key('j')], F('in_play', 3600, 'none', identity=1, fill=1))
    step('input', [key('h')], F('in_play', 3660, 'none', identity=1, fill=2))
    step('input', [key('h')], F('in_play', 3720, 'none', identity=1, fill=3))
    for t in (3780, 3840, 3900):  # three more 'h' with the map unchanged
        step('input', [key('h')], F('in_play', t, 'none', identity=1, fill=3))
    crit = dict(critical=True, vital=100, identity=1)
    step('input', [key('j')], F('in_play', 4000, 'low', fill=4, **crit))
    step('input', [key('l'), key('l'), key('l')], F('in_play', 5900, 'high', fill=5, **crit),
        usage=Run.usage(cache_write=40000))
    step('input', [key('j')], F('in_play', 5960, 'high', fill=6, ate=True, **crit))
    step('input', [key('h')], F('in_play', 6020, 'high', fill=7, **crit))
    step('input', [key('j')], F('in_play', 6080, 'high', fill=8, **crit))
    step('input', [key('j')], F('dead', 6140, 'high', death=True, cause=True, fill=9, identity=1))
    run.finish()
    return directory


def metrics_of(path: Path) -> dict:
    connection = open_readonly(path)
    try:
        # A keyless metric is found by its name, a member of a multi-valued one by (name, key).
        return {(name if not key else (name, key)): row for (name, key), row in read_metrics(connection).items()}
    finally:
        connection.close()


def events_of(path: Path, kind: str | None = None) -> list[dict]:
    connection = open_readonly(path)
    try:
        return [e for e in read_events(connection) if kind is None or e['kind'] == kind]
    finally:
        connection.close()


def run_and_evaluate(tmp_path: Path, build=main_scenario, **options) -> Path:
    directory = build(tmp_path / 'run')
    return evaluate(directory, FakeBinding(), tmp_path / 'evaluations', created_wall=1.0, **options)


# ---------------------------------------------------------------------------------------------
# Record format, refusal and incremental append.

def test_record_follows_the_contract_tables(tmp_path):
    path = run_and_evaluate(tmp_path)
    assert path == record_path(tmp_path / 'evaluations', SESSION, 'fake', 3)
    assert path.name == f'{CORE_VERSION}-fake-3.sqlite3'
    connection = open_readonly(path)
    tables = {r[0]: [c[1] for c in connection.execute(f'PRAGMA table_info({r[0]})')]
        for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables['metadata'] == ['key', 'value']
    assert tables['steps'] == ['seq', 'operation_id', 'actor', 'kind', 'wall', 'decision', 'tokens', 'dollars', 'game_time',
        'mode', 'source_id', 'frame_sha256', 'frame_changed']
    assert tables['readings'] == ['seq', 'reader', 'reader_version', 'value', 'confidence', 'abstain']
    assert tables['events'] == ['id', 'seq_start', 'seq_end', 'kind', 'source', 'confidence', 'payload']
    assert tables['metrics'] == ['name', 'key', 'version', 'value', 'count', 'denominator', 'missing']
    assert tables['run_facts'] == ['key', 'value']
    assert tables['tool_calls'] == ['request_id', 'tool_call_id', 'actor', 'decision', 'tool', 'status', 'latency_ms',
        'result_bytes', 'wall', 'operation_id']
    assert tables['requests'] == ['request_id', 'actor', 'wall', 'attempt', 'input_tokens', 'cache_read', 'cache_write',
        'output_tokens', 'dollars', 'retry_class', 'omitted_images', 'manifest']
    assert [r[1] for r in connection.execute("PRAGMA table_info(metrics)") if r[5]] == ['name', 'key']
    meta = read_metadata(connection)
    assert meta['state'] == 'final' and meta['labels'] == dict(arm=None, start=None, scenario=None, lineage=None, admission=None)
    assert (meta['schema'], meta['core_version'], meta['binding_id'], meta['binding_version'], meta['session']) == (
        'evaluation-record/1', CORE_VERSION, 'fake', 3, SESSION)
    assert meta['last_seq'] == 14 and meta['first_in_play_seq'] == 3 and meta['created_wall'] == 1.0
    assert set(meta['inputs']) == {'manifest.json', 'session.sqlite3', 'actors/001/host.jsonl'}
    steps = read_steps(connection)
    assert [s.seq for s in steps] == list(range(1, 15))
    # a decision is a completed input operation: the observe has none yet, the first input is decision 1
    assert [s.decision for s in steps[:4]] == [0, 1, 2, 3] and steps[2].tokens == 2150 * 3 and steps[2].dollars == pytest.approx(0.03)
    assert steps[2].mode == 'in_play' and steps[2].game_time == 3600 and steps[0].game_time is None
    assert steps[0].frame_changed is None and steps[1].frame_changed is True
    assert steps[9].tokens == 2150 * 10 + 39000
    connection.close()


def test_refuses_to_overwrite_unless_replaced(tmp_path):
    path = run_and_evaluate(tmp_path)
    first = path.read_bytes()
    with pytest.raises(EvaluationError, match='exists'):
        evaluate(tmp_path / 'run', FakeBinding(), tmp_path / 'evaluations', created_wall=1.0)
    assert path.read_bytes() == first
    assert evaluate(tmp_path / 'run', FakeBinding(), tmp_path / 'evaluations', replace=True, created_wall=1.0) == path
    other = FakeBinding()
    other.binding_version = 4  # new versions write a new file beside the old one
    second = evaluate(tmp_path / 'run', other, tmp_path / 'evaluations', created_wall=1.0)
    assert second != path and second.name == f'{CORE_VERSION}-fake-4.sqlite3' and path.exists()
    with pytest.raises(EvaluationError, match='exists'):
        RecordWriter.create(path, {})


def dump(path: Path) -> dict:
    connection = open_readonly(path)
    try:
        meta = read_metadata(connection)
        meta.pop('inputs')
        return dict(meta=meta, steps=read_steps(connection), readings=read_readings(connection),
            events=read_events(connection), metrics={k: v for k, v in read_metrics(connection).items()},
            run_facts=read_run_facts(connection), tool_calls=read_tool_calls(connection),
            requests=read_requests(connection))
    finally:
        connection.close()


def test_a_full_pass_is_deterministic(tmp_path):
    first = run_and_evaluate(tmp_path / 'one')
    second = run_and_evaluate(tmp_path / 'two')
    one, two = dump(first), dump(second)
    for part in ('steps', 'readings', 'events', 'metrics', 'run_facts', 'tool_calls', 'requests'):
        assert one[part] == two[part]
    assert one['meta']['created_wall'] == two['meta']['created_wall']


def growing_run(directory: Path) -> tuple[Run, str, list]:
    """A run whose store stays open, so it can grow between evaluation passes."""
    run = Run(directory)
    a = run.actor()
    sequence = [('observe', [], F('loading')), ('input', [key('ENTER')], F('menu')),
        ('input', [key('j')], F('in_play', 3600, 'none', identity=1, fill=1)),
        ('input', [key('h')], F('in_play', 3660, 'none', identity=1, fill=2)),
        ('input', [key('h')], F('in_play', 3720, 'none', identity=1, fill=2)),   # the map stops changing here
        ('input', [key('h')], F('in_play', 3780, 'none', identity=1, fill=2)),
        ('input', [key('h')], F('in_play', 3840, 'none', identity=1, fill=2))]
    return run, a, sequence


def test_incremental_append_equals_a_full_pass_over_the_grown_run(tmp_path):
    run_dir = tmp_path / 'run'
    run, a, sequence = growing_run(run_dir)
    for item in sequence[:4]:
        run.step(a, *item)
    run.finish(close=False)
    root = tmp_path / 'evals'
    path = evaluate(run_dir, FakeBinding(), root, created_wall=1.0, state='live')
    assert dump(path)['meta']['last_seq'] == 4
    assert events_of(path, 'ineffective_repeat') == []
    for item in sequence[4:]:  # the live store grows; the host trace grows with it
        run.step(a, *item)
    run.finish(close=False)
    with pytest.raises(EvaluationError, match='does not continue'):
        evaluate(run_dir, FakeBinding(), root, after_seq=3, state='live')
    assert evaluate(run_dir, FakeBinding(), root, after_seq=4, created_wall=1.0, state='live') == path
    incremental = dump(path)
    full = dump(evaluate(run_dir, FakeBinding(), tmp_path / 'full-evals', created_wall=1.0))
    assert incremental['meta']['last_seq'] == 7
    for part in ('steps', 'readings', 'events', 'metrics', 'run_facts', 'tool_calls', 'requests'):
        assert incremental[part] == full[part], part
    stuck = [e for e in incremental['events'] if e['kind'] == 'ineffective_repeat']
    assert [(e['seq_start'], e['seq_end'], e['payload']['inputs']) for e in stuck] == [(5, 7, 3)]
    # A second incremental pass with nothing new changes nothing.
    evaluate(run_dir, FakeBinding(), root, after_seq=7, created_wall=1.0, state='live')
    assert dump(path) == incremental
    run.store.close()
    with pytest.raises(EvaluationError, match='no evaluation record'):
        evaluate(run_dir, FakeBinding(), tmp_path / 'nowhere', after_seq=7, state='live')


def test_a_final_record_is_never_continued_or_overwritten_by_a_live_pass(tmp_path):
    run_dir = tmp_path / 'run'
    run, a, sequence = growing_run(run_dir)
    for item in sequence[:4]:
        run.step(a, *item)
    run.finish(close=False)
    root = tmp_path / 'evals'
    path = evaluate(run_dir, FakeBinding(), root, created_wall=1.0)
    for item in sequence[4:]:
        run.step(a, *item)
    run.finish(close=False)
    before = path.read_bytes()
    with pytest.raises(EvaluationError, match='cannot continue'):
        evaluate(run_dir, FakeBinding(), root, after_seq=4, created_wall=1.0)
    with pytest.raises(EvaluationError, match='cannot continue|never touches'):
        evaluate(run_dir, FakeBinding(), root, after_seq=4, created_wall=1.0, state='live')
    for replace in (False, True):
        with pytest.raises(EvaluationError, match='never touches'):
            evaluate(run_dir, FakeBinding(), root, created_wall=1.0, state='live', replace=replace)
    assert path.read_bytes() == before
    connection = open_readonly(path)
    assert read_metadata(connection)['inputs']  # the final input digests survive
    connection.close()
    # An operator's explicit final replacement is still allowed.
    assert evaluate(run_dir, FakeBinding(), root, created_wall=1.0, replace=True) == path
    assert dump(path)['meta']['last_seq'] == 7
    run.store.close()


def test_sources_report_unsettled_operations_and_resume_after_a_sequence(tmp_path):
    from harness.evaluation.core.sources import read_run
    run_dir = tmp_path / 'live'
    run, a, sequence = growing_run(run_dir)
    for item in sequence[:2]:
        run.step(a, *item)
    pending = run.step(a, *sequence[2], pending=True)
    run.step(a, *sequence[3])
    run.finish(close=False)
    assert [op.seq for op in read_run(run_dir, settled_only=True).operations] == [1, 2]
    assert [op.seq for op in read_run(run_dir).operations] == [1, 2, 3, 4]
    assert [op.seq for op in read_run(run_dir, after_seq=2).operations] == [3, 4]
    third = read_run(run_dir).operations[2]
    assert third.operation_id == pending and third.status == 'pending' and third.source_id is None
    # A full pass over a finished run records the pending operation as a step without a frame.
    full = evaluate(run_dir, FakeBinding(), tmp_path / 'full', created_wall=1.0)
    connection = open_readonly(full)
    assert read_steps(connection)[2].source_id is None and read_steps(connection)[2].mode == 'unknown'
    connection.close()
    run.store.close()


def test_an_unsettled_operation_is_reread_once_it_settles(tmp_path):
    run_dir = tmp_path / 'live'
    run, a, sequence = growing_run(run_dir)
    for item in sequence[:2]:
        run.step(a, *item)
    run.finish(close=False)
    root = tmp_path / 'evals'
    path = evaluate(run_dir, FakeBinding(), root, created_wall=1.0, state='live')
    assert dump(path)['meta']['last_seq'] == 2
    pending = run.step(a, *sequence[2], pending=True)
    run.step(a, *sequence[3])
    run.finish(close=False)
    evaluate(run_dir, FakeBinding(), root, after_seq=2, created_wall=1.0, state='live')
    waiting = dump(path)
    assert waiting['meta']['last_seq'] == 4 and waiting['meta']['pending_seqs'] == [3]
    assert [s.source_id is not None for s in waiting['steps']] == [True, True, False, True]
    assert [s.decision for s in waiting['steps']] == [0, 1, 1, 2]  # the unsettled input is no decision yet
    run.settle(pending)
    run.finish(close=False)
    evaluate(run_dir, FakeBinding(), root, after_seq=4, created_wall=1.0, state='live')
    caught_up = dump(path)
    assert caught_up['meta']['pending_seqs'] == [] and [s.source_id is not None for s in caught_up['steps']] == [True] * 4
    assert [s.decision for s in caught_up['steps']] == [0, 1, 2, 3]
    full = dump(evaluate(run_dir, FakeBinding(), tmp_path / 'full', created_wall=1.0))
    for part in ('steps', 'readings', 'events', 'metrics', 'run_facts', 'tool_calls', 'requests'):
        assert caught_up[part] == full[part], part
    run.store.close()


# ---------------------------------------------------------------------------------------------
# The plausibility guard.

def test_guard_rejects_backward_steps_and_unconfirmed_jumps():
    # a backward step is abstained and does not move the accepted clock
    assert guard_clock([100, 160, 90, 220], 100) == [(100, None), (160, None), (None, 'backward_step'), (220, None)]
    assert guard_clock([100, 160, 150, 170], 100)[2] == (None, 'backward_step')
    # a spike of +1000 that the next reading does not confirm is abstained
    assert guard_clock([100, 1100, 130], 500) == [(100, None), (None, 'implausible_jump'), (130, None)]
    # the same jump confirmed by the next reading is accepted
    assert guard_clock([100, 1100, 1130], 500) == [(100, None), (1100, None), (1130, None)]
    # confirmation must itself be plausible and not backward
    assert guard_clock([100, 1100, 1700], 500)[1] == (None, 'implausible_jump')
    # the newest reading of a live run stays unconfirmed
    assert guard_clock([100, 1100], 500)[1] == (None, 'implausible_jump')
    assert guard_clock([None, 100, None, 130], 500) == [(None, 'unreadable'), (100, None), (None, 'unreadable'), (130, None)]


def test_implausible_jump_is_marked_in_the_record(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        for t in (3600, 3660, 90000, 3720, 3780):  # one wild reading, then back on track
            run.step(a, 'input', [key('j')], F('in_play', t, 'none', fill=t % 200))
        run.finish()
        return directory
    path = run_and_evaluate(tmp_path, build)
    connection = open_readonly(path)
    clock = {r.seq: r for r in read_readings(connection) if r.reader == 'core.game_time'}
    assert clock[3].abstain == 'implausible_jump' and clock[3].value is None
    assert [r.value for r in clock.values()] == [3600, 3660, None, 3720, 3780]
    assert [s.game_time for s in read_steps(connection)] == [3600, 3660, None, 3720, 3780]
    connection.close()


# ---------------------------------------------------------------------------------------------
# Events.

def test_mode_vital_threat_long_activity_milestone_and_death_events(tmp_path):
    path = run_and_evaluate(tmp_path)
    events = events_of(path)
    by_kind = lambda kind: [e for e in events if e['kind'] == kind]  # noqa: E731
    assert [(e['seq_start'], e['payload']['previous'], e['payload']['mode']) for e in by_kind('mode_change')] == [
        (2, 'loading', 'menu'), (3, 'menu', 'in_play'), (14, 'in_play', 'dead')]
    assert all(e['source'] == 'reader' for e in by_kind('mode_change'))
    long = by_kind('long_activity')
    assert len(long) == 1 and (long[0]['seq_start'], long[0]['seq_end']) == (9, 10)
    assert long[0]['payload']['seconds'] == 1900
    vitals = by_kind('vital_change')
    assert len(vitals) == 1 and vitals[0]['seq_start'] == 9 and vitals[0]['payload']['critical'] is True
    assert vitals[0]['confidence'] == pytest.approx(0.9)  # the weakest legible reading on the frame
    assert [(e['seq_start'], e['payload']['previous'], e['payload']['threat']) for e in by_kind('threat_change')] == [
        (9, 'none', 'low'), (10, 'low', 'high')]
    milestones = {e['payload']['rung']: e for e in by_kind('milestone')}
    assert set(milestones) == {'play', 'ate'}  # the human rung is never fired by a reader
    assert milestones['play']['seq_start'] == 3 and milestones['play']['payload']['decisions_to_reach'] == 0
    assert milestones['ate']['seq_start'] == 11 and milestones['ate']['payload']['decisions_to_reach'] == 8
    assert milestones['ate']['payload']['clocks'] == dict(wall=BASE + 110, decision=10, tokens=2150 * 11 + 39000,
        dollars=pytest.approx(0.11), game_time=5960)
    death = by_kind('death')
    assert len(death) == 1 and death[0]['seq_start'] == 14 and death[0]['payload']['cause'] == 'combat'
    assert death[0]['source'] == 'reader' and death[0]['confidence'] == pytest.approx(0.7)
    for event in events:
        assert event['source'] in ('harness', 'reader', 'derived', 'player_claim', 'human')
        assert event['confidence'] is None or 0 <= event['confidence'] <= 1


def test_ineffective_repeat_needs_three_same_inputs_with_an_unchanged_map(tmp_path):
    path = run_and_evaluate(tmp_path)
    stuck = events_of(path, 'ineffective_repeat')
    assert len(stuck) == 1
    assert (stuck[0]['seq_start'], stuck[0]['seq_end']) == (6, 8)
    assert stuck[0]['payload'] == dict(key='h', inputs=3, max_change=0.0)

    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('h')], F('in_play', 3600, fill=1))
        run.step(a, 'input', [key('h')], F('in_play', 3660, fill=1))
        run.step(a, 'input', [key('j')], F('in_play', 3720, fill=1))  # a different key breaks the run
        run.step(a, 'input', [key('h')], F('in_play', 3780, fill=1))
        run.step(a, 'input', [key('h'), key('h')], F('in_play', 3840, fill=1))  # not a single movement input
        run.step(a, 'input', [key('h')], F('in_play', 3900, fill=1))
        run.step(a, 'input', [dict(type='key', key='h', modifiers=['CTRL'])], F('in_play', 3960, fill=1))
        run.finish()
        return directory
    assert events_of(run_and_evaluate(tmp_path / 'other', build), 'ineffective_repeat') == []


def test_stall_is_an_out_of_play_streak_of_fifteen_decisions(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
        for index in range(16):
            run.step(a, 'input', [key('ESC')], F('menu', fill=index))
        run.step(a, 'input', [key('j')], F('in_play', 3660, fill=99))
        for index in range(14):  # one short
            run.step(a, 'input', [key('ESC')], F('prompt', fill=index))
        run.step(a, 'input', [key('j')], F('in_play', 3720, fill=98))
        run.finish()
        return directory
    path = run_and_evaluate(tmp_path, build)
    stalls = events_of(path, 'stall')
    assert len(stalls) == 1
    assert stalls[0]['payload'] == dict(decisions=16, modes=dict(menu=16), setup=False, ongoing=False)
    assert (stalls[0]['seq_start'], stalls[0]['seq_end']) == (2, 17)
    metrics = metrics_of(path)
    assert metrics['stall.longest'].value == 16 and metrics['stall.count'].value == 1
    assert metrics['stall.count'].denominator == 33


def test_custody_stop_handoff_and_host_events(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
        run.step(a, 'input', [key('j')], F('in_play', 3660, fill=2), status='unknown', receipt='unknown')
        context = run.context(a, ['rec-1'])
        run.step(a, 'handoff', None, None, status='sealed', handoff=dict(schema='player-handoff/1', operation_id='x',
            session=SESSION, actor_id=a, context_id=context, context_sha256='b' * 64, sealed_wall=BASE, grants_authority=False))
        run.host[a].append(run.event(a, 'control-accepted', iso(BASE + 35), control_id='c' * 32, control_type='orderly_stop'))
        run.host[a].append(run.event(a, 'tool-refused', iso(BASE + 36), request_id='request-1', tool_call_id='x',
            tool='computer_input', reason='orderly-stop', dispatched=False, delivery='undelivered'))
        run.host[a].append(run.event(a, 'context-image-projection', iso(BASE + 37), request_id='request-3',
            projection_ms=1.0, input_images=9, omitted_images=3, retained_images=6, blocked=True))
        run.host[a].append(run.event(a, 'context-image-projection', iso(BASE + 38), request_id='request-3',
            projection_ms=1.0, input_images=4, omitted_images=0, retained_images=4))
        run.finish()
        return directory
    path = run_and_evaluate(tmp_path, build)
    stops = events_of(path, 'custody_stop')
    # An accepted orderly stop is a run_end, never a custody stop; only partial or unknown delivery is.
    assert [(e['payload']['cause'], e['source'], e['confidence']) for e in stops] == [('unknown', 'harness', None)]
    assert stops[0]['seq_start'] == 2
    ends = events_of(path, 'run_end')
    assert [(e['payload']['reason'], e['payload']['orderly_stop'], e['source']) for e in ends] == [('orderly_stop', True, 'harness')]
    handoff = events_of(path, 'handoff')
    assert len(handoff) == 1 and handoff[0]['payload']['context_sha256'] == 'b' * 64 and handoff[0]['seq_start'] == 3
    refused = events_of(path, 'tool_refused')
    assert [e['payload'] for e in refused] == [dict(actor=refused[0]['payload']['actor'], tool='computer_input',
        reason='orderly-stop', delivery='undelivered')]
    evictions = events_of(path, 'context_eviction')
    assert len(evictions) == 1  # only the projection that omitted images or blocked
    assert evictions[0]['payload'] == dict(actor=evictions[0]['payload']['actor'], omitted_images=3, retained_images=6, blocked=True)
    assert evictions[0]['source'] == 'harness' and evictions[0]['confidence'] is None
    metrics = metrics_of(path)
    # A custody stop is its own boolean; it never enters the receipt rate.
    assert metrics['custody.uncertain_receipts'].value == pytest.approx(0.5)
    assert (metrics['custody.uncertain_receipts'].count, metrics['custody.uncertain_receipts'].denominator) == (1, 2)
    assert metrics['custody.stopped'].value is True and metrics['custody.stopped'].count == 1


def record_doc(kind: str = 'work') -> dict:
    return dict(schema='player-record/1', kind=kind, text='note', data={}, sources=[], supports=[], supersedes=None,
        applicability=None, program_id=None)


def memory_scenario(directory: Path) -> Path:
    """Two actors: memory writes/reads, programs, a handoff with carried context and a resume."""
    run = Run(directory)
    memory_path = directory.parent / 'memory.sqlite3'
    with Memory(memory_path) as memory:
        first = memory.append('actor-a', record_doc())['id']
        second = memory.append('actor-a', record_doc('decision'))['id']
        third = memory.append('actor-b', record_doc('claim'))['id']
        memory._db.execute("INSERT INTO programs(id,document,parent_id) VALUES('prog-old',?,NULL)",
            (json.dumps(dict(id='prog-old', actor_id='actor-prior', created_wall=1.0, sha256='0' * 64)),))
        memory._db.commit()
    a = run.actor(f'{1:032x}')
    run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
    run.call(a, 'player_memory_append', dict(record=record_doc()), dict(id=first, kind='work', supports=[], sources=['s1']))
    run.call(a, 'player_memory_append', dict(record=record_doc()), dict(id=second, kind='decision', supports=[first], sources=[]))
    run.call(a, 'player_memory_append', dict(record=record_doc()), dict(id='broken'), error=True)  # failed writes do not count
    run.step(a, 'input', [key('j')], F('in_play', 3660, fill=2))
    run.call(a, 'player_program_save', dict(program={}), dict(id='prog-new', parent_id=None))
    run.call(a, 'player_program_run', dict(program_id='prog-new'), dict(program_id='prog-new', status='done', run_id='r1'))
    for index in range(7):  # the last six calls of this actor start after the last write
        run.step(a, 'input', [key('j')], F('in_play', 3720 + 60 * index, fill=3 + index))
    run.call(a, 'player_memory_append', dict(record=record_doc()), dict(id=third, kind='claim', supports=[], sources=[]))
    context = run.context(a, [first])
    run.step(a, 'handoff', None, None, status='sealed', handoff=dict(schema='player-handoff/1', operation_id='x',
        session=SESSION, actor_id=a, context_id=context, context_sha256='c' * 64, sealed_wall=BASE, grants_authority=False))
    run.host[a].append(run.event(a, 'context-estimate', iso(BASE + 99), request_id='request-10', tokens=8000))
    b = run.actor(f'{2:032x}')
    run.host[b].append(run.event(b, 'context-estimate', iso(BASE + 101), request_id='request-11', tokens=2000))
    run.step(b, 'input', [key('j')], F('in_play', 4200, fill=20))  # one action: not yet a resume
    run.call(b, 'player_memory_read', dict(record_id=first), dict(id=first, kind='work'))  # carried: not beyond carry
    run.call(b, 'player_memory_query', dict(), dict(schema='player-query/1', records=[dict(id=first), dict(id=second), dict(id=third)]))
    run.call(b, 'player_memory_context', dict(ids=[second]), dict(schema='player-context/1', records=[dict(id=second)], programs=[]))
    run.call(b, 'player_program_run', dict(program_id='prog-new'), dict(program_id='prog-new', status='yield', run_id='r2'))
    run.call(b, 'player_program_run', dict(program_id='prog-old'), dict(program_id='prog-old', status='done', run_id='r3'))
    run.step(b, 'input', [key('h'), key('j'), key('k')], F('in_play', 4260, fill=21))  # three actions and a changed frame
    run.finish(memory=memory_path)
    return directory


def test_memory_program_and_handoff_events_and_metrics(tmp_path):
    path = run_and_evaluate(tmp_path, memory_scenario)
    writes = events_of(path, 'memory_write')
    assert [e['payload']['record_kind'] for e in writes] == ['work', 'decision', 'claim']
    assert all(e['source'] == 'player_claim' and e['confidence'] is None for e in writes)
    reads = events_of(path, 'memory_read')
    assert [e['payload']['tool'] for e in reads] == ['player_memory_read', 'player_memory_query', 'player_memory_context']
    assert [len(e['payload']['record_ids']) for e in reads] == [1, 3, 1]
    assert reads[0]['payload']['record_ids'] == [writes[0]['payload']['record_id']]
    assert [e['payload']['program_id'] for e in events_of(path, 'program_save')] == ['prog-new']
    runs = events_of(path, 'program_run')
    assert [(e['payload']['program_id'], e['payload']['status'], e['payload']['reused']) for e in runs] == [
        ('prog-new', 'done', False), ('prog-new', 'yield', True), ('prog-old', 'done', True)]
    assert runs[2]['payload']['author'] == 'actor-prior'  # from the memory store, not this run
    metrics = metrics_of(path)
    assert metrics['memory.writes'].value == 3 and metrics['memory.writes'].count == 3
    assert metrics['memory.reads'].value == 3
    # Reads returned first, second and third; the carry from actor 1 is just the first record.
    carry = metrics['memory.retrieved_beyond_carry']
    assert (carry.count, carry.denominator, carry.value) == (2, 3, pytest.approx(2 / 3)) and carry.missing is None
    # Actor 1 made 16 tool calls; its third write is call 14, inside the last six. The first two are not.
    late = metrics['memory.late_write_share']
    assert late.denominator == 3 and late.count == 1 and late.value == pytest.approx(1 / 3)
    assert metrics['programs.saved'].value == 1 and metrics['programs.runs'].value == 3
    assert metrics['programs.reused'].value == 2
    assert [metrics['programs.outcomes', s].value for s in ('done', 'yield')] == [2, 1]
    assert metrics['programs.outcomes', 'done'].denominator == 3 and 'programs.outcomes' not in metrics
    assert [metrics['memory.records', k].value for k in ('claim', 'decision', 'work')] == [1, 1, 1]
    resume = metrics['handoff.decisions_to_resume']
    assert resume.denominator == 1 and resume.count == 1 and resume.value == dict(value=2, excluded=0)
    assert metrics['handoff.decisions_to_resume', '0'].value == 2  # per-handoff values are keyed by index
    ratio = metrics['handoff.carry_ratio']
    assert ratio.count == 1 and ratio.value['value'] == pytest.approx(0.25) and ratio.missing is None
    assert metrics['handoff.carry_ratio', '0'].value == pytest.approx(0.25)


def test_memory_metrics_missing_without_a_host_trace(tmp_path):
    def build(directory):
        run = Run(directory, hosts=False)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
        run.finish()
        return directory
    metrics = metrics_of(run_and_evaluate(tmp_path, build))
    assert metrics['memory.writes'].value is None and metrics['memory.writes'].missing == 'no_host_trace'
    assert metrics['host.dollars_per_decision'].missing == 'no_host_trace'
    assert metrics['pace.dollars_per_game_hour'].missing == 'no_host_trace'
    assert metrics['host.retry_share'].value['value'] is None


# ---------------------------------------------------------------------------------------------
# Metrics: denominator and missing rule for each row of the table.

def test_every_metric_row_is_present_with_count_and_denominator(tmp_path):
    metrics = metrics_of(run_and_evaluate(tmp_path))
    expected = {'survival.game_hours', 'pace.routine_seconds_per_decision', 'pace.long_activities',
        'pace.dollars_per_game_hour', 'mode.out_of_play_share', 'stall.longest', 'stall.count',
        'input.actions_per_call', 'input.unseen_action_share', 'input.frame_unchanged_rate',
        'custody.uncertain_receipts', 'custody.stopped', 'memory.writes', 'memory.reads', 'memory.retrieved_beyond_carry',
        'memory.late_write_share', 'programs.saved', 'programs.runs', 'programs.reused', 'programs.outcomes',
        'handoff.decisions_to_resume', 'handoff.carry_ratio', 'host.dollars_per_decision', 'host.cache_write_share',
        'host.large_rewrite_share', 'host.retry_share', 'needs.severe_share', 'ladder.reached',
        'lineage.continuity', 'run.infrastructure_loss'}
    assert expected <= set(metrics)
    keyed = {n: {k for item in metrics if isinstance(item, tuple) for name, k in [item] if name == n}
        for n in ('reader.coverage', 'host.latency', 'tools.calls')}
    assert keyed['reader.coverage'] >= {'core.frame', 'clock', 'mode', 'core.game_time', 'core.map_change'}
    assert keyed['host.latency'] == {'response.p50', 'response.p95', 'first_chunk.p50', 'first_chunk.p95'}
    assert {'computer_input', 'player_source+zoom'} <= keyed['tools.calls']
    assert all(row.version == 1 for row in metrics.values())


def test_survival_pace_and_cost_metrics(tmp_path):
    metrics = metrics_of(run_and_evaluate(tmp_path))
    survival = metrics['survival.game_hours']
    assert survival.value['outcome'] == 'died' and survival.value['hours'] == pytest.approx(2540 / 3600)
    assert survival.denominator is None and survival.count == 12
    routine = metrics['pace.routine_seconds_per_decision']
    assert routine.value == 60 and routine.count == routine.denominator == 10 and routine.missing is None
    assert metrics['pace.long_activities'].value == dict(count=1, total_game_seconds=1900)
    hours = 2540 / 3600
    dollars = metrics['pace.dollars_per_game_hour']
    assert dollars.value == pytest.approx(0.14 / hours) and dollars.denominator == pytest.approx(hours)
    per = metrics['host.dollars_per_decision']
    assert per.value['value'] == pytest.approx(0.14 / 13) and per.denominator == 13 and per.value['excluded'] == 0
    cache = metrics['host.cache_write_share']
    assert cache.value == pytest.approx(0.4) and cache.denominator == pytest.approx(0.14)
    large = metrics['host.large_rewrite_share']
    assert large.value == pytest.approx(1 / 14) and large.count == 1
    for series, expected in (('response', 200), ('first_chunk', 100)):
        for percentile in ('p50', 'p95'):
            latency = metrics['host.latency', f'{series}.{percentile}']
            assert latency.value == expected and latency.count == 14 and latency.denominator == 14
    retry = metrics['host.retry_share']
    assert retry.value['value'] == 0 and retry.count == 0 and retry.denominator == 14


def test_pace_routine_is_missing_with_fewer_than_five_intervals(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        for index, t in enumerate((3600, 3660, 3720, 3780, 3840)):  # four pairs
            run.step(a, 'input', [key('j')], F('in_play', t, fill=index))
        run.finish()
        return directory
    routine = metrics_of(run_and_evaluate(tmp_path, build))['pace.routine_seconds_per_decision']
    assert routine.value is None and routine.missing == 'insufficient' and routine.count == 4


def test_mode_input_and_needs_metrics(tmp_path):
    metrics = metrics_of(run_and_evaluate(tmp_path))
    mode = metrics['mode.out_of_play_share']
    assert mode.value == dict(value=pytest.approx(1 / 12), excluded=0, setup_decisions=2)
    assert (mode.count, mode.denominator, mode.missing) == (1, 12, None)
    assert metrics['stall.longest'].value == 0 and metrics['stall.count'].value == 0
    apc = metrics['input.actions_per_call']
    assert apc.value == pytest.approx(15 / 13) and (apc.count, apc.denominator) == (15, 13)
    unseen = metrics['input.unseen_action_share']
    assert unseen.value == pytest.approx(2 / 15) and unseen.denominator == 15
    unchanged = metrics['input.frame_unchanged_rate']
    assert unchanged.value == dict(value=0.0, excluded=0) and (unchanged.count, unchanged.denominator) == (0, 13)
    needs = metrics['needs.severe_share']
    assert needs.value == dict(value=pytest.approx(5 / 11), excluded=0) and (needs.count, needs.denominator) == (5, 11)
    uncertain = metrics['custody.uncertain_receipts']
    assert uncertain.value == 0 and uncertain.denominator == 14 and uncertain.count == 0
    assert metrics['custody.stopped'].value is False


def test_abstentions_and_missing_captures_are_excluded_and_counted(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
        run.step(a, 'input', [key('j')], F('unknown', fill=2))             # no legible mode: abstains
        run.step(a, 'input', [key('j')], F('in_play', 3660, fill=3))
        run.step(a, 'input', [key('j')], F('in_play', 3720, fill=3), usage={})  # same fill but time differs: still changed
        run.step(a, 'input', [key('j')], None, status='unknown', receipt='partial')  # no capture
        run.step(a, 'input', [key('j')], F('in_play', 3720, fill=3))
        run.step(a, 'input', [key('j')], F('in_play', 3720, fill=3))       # byte-identical capture: unchanged
        run.finish()
        return directory
    metrics = metrics_of(run_and_evaluate(tmp_path, build))
    mode = metrics['mode.out_of_play_share']
    assert mode.missing == 'abstentions_excluded' and mode.value['excluded'] == 1 and mode.value['value'] == 0
    rate = metrics['input.frame_unchanged_rate']
    # excluded and counted: the first input (no earlier capture) and the one with no capture at all
    assert rate.missing == 'no_capture_excluded' and rate.value['excluded'] == 2
    # the capture after the missing one is compared with the last real capture; two are byte-identical
    assert (rate.count, rate.denominator) == (2, 5) and rate.value['value'] == pytest.approx(0.4)
    per = metrics['host.dollars_per_decision']
    assert per.missing == 'missing_usage_excluded' and per.value['excluded'] == 1
    coverage = metrics['reader.coverage', 'core.frame']
    assert coverage.denominator == 6 and coverage.count == 6  # six captures; the unknown frame is still a legible frame
    assert metrics['reader.coverage', 'clock'].count == 5  # the unknown-mode frame carries no time
    uncertain = metrics['custody.uncertain_receipts']
    assert uncertain.count == 1 and uncertain.denominator == 7 and uncertain.value == pytest.approx(1 / 7)
    assert metrics['custody.stopped'].value is True


def test_ladder_marks_human_rungs_not_assessed_and_accepts_a_human_confirmation(tmp_path):
    path = run_and_evaluate(tmp_path, state='live')
    ladder = metrics_of(path)['ladder.reached']
    assert ladder.value['highest'] == 'ate'
    assert [(r['id'], r['status']) for r in ladder.value['rungs']] == [('play', 'reached'), ('armed', 'not_assessed'),
        ('ate', 'reached')]
    assert ladder.value['rungs'][2]['decisions'] == 8 and ladder.missing == 'human_rungs_not_assessed'
    assert (ladder.count, ladder.denominator) == (2, 3)
    # A hand-recorded event survives re-evaluation and confirms the rung.
    with RecordWriter.open(path) as writer:
        writer.connection.execute("INSERT INTO events(seq_start,seq_end,kind,source,confidence,payload) "
            "VALUES(5,5,'milestone','human',NULL,?)", (json.dumps(dict(rung='armed')),))
    again = evaluate(tmp_path / 'run', FakeBinding(), tmp_path / 'evaluations', replace=False, after_seq=14, created_wall=1.0, state='live')
    events = events_of(again, 'milestone')
    assert {e['source'] for e in events} == {'reader', 'human'}
    ladder = metrics_of(again)['ladder.reached']
    assert [r['status'] for r in ladder.value['rungs']] == ['reached', 'confirmed', 'reached'] and ladder.missing is None


def test_survival_is_missing_without_a_clock_or_an_in_play_reading(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('menu'))
        run.step(a, 'input', [key('j')], F('menu', fill=1))
        run.finish()
        return directory
    row = metrics_of(run_and_evaluate(tmp_path, build))['survival.game_hours']
    assert row.value is None and row.missing == 'no_clock_reading'

    def censored(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('in_play', 3600))
        run.step(a, 'input', [key('j')], F('in_play', 7200, fill=1))
        run.finish()
        return directory
    row = metrics_of(run_and_evaluate(tmp_path / 'c', censored))['survival.game_hours']
    assert row.value['outcome'] == 'censored' and row.value['hours'] == pytest.approx(1.0)


def test_retries_aborts_and_non_tool_stops_share_one_denominator(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))                  # request-1 ok
        failing = run.request(a, usage={}, stop='error')                               # request-2 fails
        run.host[a].append(run.event(a, 'provider-retry', stage='started', request_id='request-3', previous_request_id=failing))
        run.step(a, 'input', [key('j')], F('in_play', 3660, fill=2))                  # request-3 is the retry
        key_four = run.request(a, stop='stop')                                          # a non-tool stop
        run.host[a].append(run.event(a, 'abort', reason='cancelled', request_id=key_four))
        run.finish()
        return directory
    retry = metrics_of(run_and_evaluate(tmp_path, build))['host.retry_share']
    assert retry.denominator == 4 and retry.count == 3
    # a request is counted once even if it is both aborted and a non-tool stop: 2 failed, 3 retried, 4 aborted
    assert retry.value == dict(value=0.75, retries=1, aborts=1, non_tool_stops=2)


# ---------------------------------------------------------------------------------------------
# Survival statistics.

def test_kaplan_meier_rmst_and_logrank_on_a_hand_computed_example():
    runs = [Observation(3, True), Observation(4, False), Observation(5, True), Observation(8, True), Observation(10, False)]
    curve = kaplan_meier(runs)
    assert curve['times'] == [3, 4, 5, 8, 10]
    assert curve['survival'] == pytest.approx([0.8, 0.8, 0.8 * 2 / 3, 0.8 * 2 / 3 * 0.5, 0.8 * 2 / 3 * 0.5])
    assert curve['lower'][0] < 0.8 < curve['upper'][0] <= 1.0  # Greenwood-based interval around the first step
    # Hand integral to 10: 3*1 + 1*0.8 + 1*0.8 + 3*(8/15) + 2*(4/15) = 6.7333...
    expected = 3 + 0.8 + 0.8 + 3 * 8 / 15 + 2 * 4 / 15
    assert expected == pytest.approx(6.733333, abs=1e-5)
    assert restricted_mean(curve['times'], curve['survival'], 10) == pytest.approx(expected)
    assert rmst(runs, 10) == pytest.approx(expected)
    assert restricted_mean(curve['times'], curve['survival'], 2) == pytest.approx(2.0)  # before any event
    assert restricted_mean(curve['times'], curve['survival'], 4) == pytest.approx(3 + 0.8)
    with pytest.raises(ValueError):
        rmst(runs, 11)  # beyond the observed range
    # Censoring is kept: the same times all treated as deaths give a lower mean.
    assert rmst([Observation(o.time, True) for o in runs], 10) < expected
    a = [Observation(3, True), Observation(5, True), Observation(8, True), Observation(9, True)]
    b = [Observation(10, False), Observation(11, False), Observation(12, True), Observation(13, False)]
    test = logrank(a, b)
    assert test['pvalue'] is not None and 0 <= test['pvalue'] < 0.05
    assert logrank(a, a)['pvalue'] == pytest.approx(1.0)


def test_bootstrap_interval_is_deterministic_and_brackets_the_estimate():
    runs = [Observation(float(t), t % 3 != 0) for t in range(2, 14)]
    one = bootstrap_rmst(runs, 8.0, resamples=200, seed=7)
    two = bootstrap_rmst(runs, 8.0, resamples=200, seed=7)
    assert one == two and one['low'] <= rmst(runs, 8.0) <= one['high']
    assert bootstrap_rmst(runs[:1], 1.0)['low'] is None
    result = compare({'a': runs, 'b': [Observation(float(t + 3), True) for t in range(2, 8)]}, 5.0, resamples=100)
    assert set(result['arms']) == {'a', 'b'} and set(result['logrank']) == {'a|b'}
    assert result['arms']['a']['censored'] + result['arms']['a']['deaths'] == 12
    assert compare({'a': runs}, 100.0, resamples=10)['arms']['a']['rmst']['reason'] == 'horizon_beyond_observed_range'


# ---------------------------------------------------------------------------------------------
# Lineage.

def lineage_run(directory: Path, session: str, times: list[int], identity: int, base: float) -> Path:
    run = Run(directory, session=session, base=base)
    a = run.actor()
    for index, t in enumerate(times):
        run.step(a, 'input', [key('j')], F('in_play', t, identity=identity, fill=index))
    run.finish()
    return directory


DAY = 24 * 3600


def day_lineage(tmp_path: Path, name: str, *, critical: bool = False, death: bool = False) -> list[Path]:
    """Two admissions: the first writes a memory record, the second crosses one game day and reads it."""
    one = Run(tmp_path / f'{name}-one', session=f'{name}1'.ljust(32, '0')[:32], base=BASE)
    a = one.actor()
    one.step(a, 'input', [key('j')], F('in_play', 3600, identity=1, fill=0))
    one.call(a, 'player_memory_append', dict(record=record_doc()), dict(id='rec-1', kind='work', supports=[], sources=[]))
    one.step(a, 'input', [key('j')], F('in_play', 3660, identity=1, fill=1, death=death))
    one.step(a, 'input', [key('j')], F('in_play', 3720, identity=1, fill=2))
    one.finish()
    two = Run(tmp_path / f'{name}-two', session=f'{name}2'.ljust(32, '0')[:32], base=BASE + 1000)
    b = two.actor()
    two.step(b, 'input', [key('j')], F('in_play', 3600 + DAY - 60, identity=1, fill=0))
    two.call(b, 'player_memory_read', dict(record_id='rec-1'), dict(id='rec-1', kind='work'))
    two.step(b, 'input', [key('j')], F('in_play', 3600 + DAY + 60, identity=1, fill=1, critical=critical))
    two.step(b, 'input', [key('j')], F('in_play', 3600 + DAY + 120, identity=1, fill=2))
    two.finish()
    return [tmp_path / f'{name}-one', tmp_path / f'{name}-two']


def test_lineage_elapsed_day_check_and_memory_reuse(tmp_path):
    result = stitch(day_lineage(tmp_path, 'ab'), FakeBinding(), tmp_path / 'evals')
    elapsed = result['lineage.elapsed']
    assert elapsed['game_seconds'] == DAY + 120 and elapsed['admissions'] == 2 and elapsed['decisions'] > 0
    assert elapsed['game_seconds_per_decision'] == round((DAY + 120) / elapsed['decisions'], 2)
    day = result['lineage.day_check']
    assert (day['passed'], day['severe'], day['died_before']) == (True, [], False)
    assert day['elapsed_hours'] == round((DAY + 60) / 3600, 3)
    assert result['lineage.memory_reuse'] == dict(per_admission=[dict(run='ab-one', reused=0), dict(run='ab-two', reused=1)],
        reused=1)
    # Every admission carries the lineage metrics; a fresh re-score drops them until the lineage is stitched again.
    for path in map(Path, result['records']):
        metrics = metrics_of(path)
        assert metrics['lineage.day_check'].count == 1 and metrics['lineage.memory_reuse'].denominator == 1
    evaluate(tmp_path / 'ab-two', FakeBinding(), tmp_path / 'evals', replace=True)
    assert 'lineage.elapsed' not in metrics_of(Path(result['records'][1]))
    assert stitch(day_lineage(tmp_path / 'again', 'ab'), FakeBinding(), tmp_path / 'again-evals')['lineage.elapsed'] == elapsed
    # A severe need at the day point fails the check; a death read earlier in the lineage fails it too.
    severe = stitch(day_lineage(tmp_path, 'cd', critical=True), FakeBinding(), tmp_path / 'evals')['lineage.day_check']
    assert (severe['passed'], severe['severe']) == (False, ['hunger'])
    died = stitch(day_lineage(tmp_path, 'ef', death=True), FakeBinding(), tmp_path / 'evals')['lineage.day_check']
    assert (died['passed'], died['died_before']) == (False, True)
    # A lineage short of a day is reported as not reached, and a single admission has no earlier writes.
    short = stitch([lineage_run(tmp_path / 'short', '9' * 32, [3600, 3660], 1, BASE)], FakeBinding(), tmp_path / 'evals')
    record = metrics_of(Path(short['records'][0]))
    assert record['lineage.day_check'].missing == 'not_reached' and record['lineage.memory_reuse'].missing == 'no_earlier_writes'


def frames_lineage(tmp_path: Path, name: str, admissions: list[list[F]]) -> list[Path]:
    paths = []
    for number, frames in enumerate(admissions):
        directory = tmp_path / f'{name}-{number}'
        run = Run(directory, session=f'{name}{number}'.ljust(32, '0')[:32], base=BASE + 1000 * number)
        actor = run.actor()
        for index, frame in enumerate(frames):
            run.step(actor, 'input', [key('j')], dataclasses.replace(frame, fill=index))
        run.finish()
        paths.append(directory)
    return paths


def test_lineage_day_check_rewind_lag_start_and_episodes(tmp_path):
    day = lambda name, admissions: stitch(frames_lineage(tmp_path, name, admissions), FakeBinding(),
        tmp_path / 'evals')['lineage.day_check']
    # Start is the first in-play clock: an earlier clock on a prompt frame does not count.
    started = day('a5', [[F('prompt', 0, identity=1), F('in_play', 3600, identity=1), F('in_play', 3600 + DAY - 10, identity=1)]])
    assert started is None   # 3600 + DAY - 10 is short of a day from 3600, though a day from 0
    # A reload that rewinds below the day undoes an earlier crossing.
    rewound = stitch(frames_lineage(tmp_path, 'b6', [
        [F('in_play', 3600, identity=1), F('in_play', 3600 + DAY + 60, identity=1)],
        [F('in_play', 3600 + DAY - 600, identity=1), F('in_play', 3600 + DAY - 540, identity=1)]]),
        FakeBinding(), tmp_path / 'evals')
    assert rewound['lineage.day_check'] is None and rewound['lineage.elapsed']['game_seconds'] == DAY - 540
    assert metrics_of(Path(rewound['records'][0]))['lineage.day_check'].missing == 'not_reached'
    # A crossing on an unreadable screen is scored at the next legible step, in the next admission, with its lag.
    lagged = day('c7', [[F('in_play', 3600, identity=1), F('in_play', 3660, identity=1)],
                        [F('in_play', 3600 + DAY - 120, identity=1), F('in_play', 3600 + DAY - 60, identity=1),
                         F('prompt', 3600 + DAY + 60, identity=1)],
                        [F('in_play', 3600 + DAY + 3600, identity=1)]])
    assert (lagged['run'], lagged['scored_run'], lagged['passed'], lagged['lag_hours']) == ('c7-1', 'c7-2', True, 1.0)
    # Alive at the day, then dead before the needs could be read: unscored, not a day-check failure.
    in_lag = stitch(frames_lineage(tmp_path, 'e9', [[F('in_play', 3600, identity=1), F('in_play', 3660, identity=1)],
        [F('in_play', 3600 + DAY - 120, identity=1), F('in_play', 3600 + DAY - 60, identity=1),
         F('prompt', 3600 + DAY + 60, identity=1), F('prompt', 3600 + DAY + 120, identity=1, death=True)],
        [F('in_play', 3600 + DAY + 3600, identity=1)]]), FakeBinding(), tmp_path / 'evals')
    lagged_death = metrics_of(Path(in_lag['records'][0]))['lineage.day_check']
    assert lagged_death.missing == 'died_in_lag' and lagged_death.value['passed'] is None
    assert lagged_death.value['died_before'] is False
    # A net rewind below the start leaves no meaningful per-decision pace.
    net = stitch(frames_lineage(tmp_path, 'fa', [[F('in_play', 3600, identity=1), F('in_play', 3660, identity=1)],
        [F('in_play', 3000, identity=1), F('in_play', 3060, identity=1)]]), FakeBinding(), tmp_path / 'evals')['lineage.elapsed']
    assert net['game_seconds'] == -540 and net['game_seconds_per_decision'] is None and net['long_activity_share'] is None
    # A restarted clock inside an admission (another world) is listed for the continuity check.
    episode = stitch(frames_lineage(tmp_path, 'd8', [[F('in_play', t, identity=1) for t in (200_000, 200_060, 100, 160, 220)]]),
        FakeBinding(), tmp_path / 'evals')['lineage.elapsed']
    assert [change['run'] for change in episode['episode_changes']] == ['d8-0']


def test_lineage_reports_identity_and_rewound_game_time(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tools.evaluate.run_external", lambda run: dict(custody=dict(receipts=7, uncertain=0)))
    first = lineage_run(tmp_path / 'one', '1' * 32, [3600, 3660, 3720], 1, BASE)
    second = lineage_run(tmp_path / 'two', '2' * 32, [3780, 3840], 1, BASE + 1000)       # continues
    third = lineage_run(tmp_path / 'three', '3' * 32, [3000, 3060], 1, BASE + 2000)      # rewound by 840 s
    fourth = lineage_run(tmp_path / 'four', '4' * 32, [3100, 3160], 2, BASE + 3000)      # another survivor
    fifth = lineage_run(tmp_path / 'five', '5' * 32, [3200, 3260], 0, BASE + 4000)       # identity unreadable
    admissions = [first, second, third, fourth, fifth]
    result = stitch(admissions, FakeBinding(), tmp_path / 'evals')
    boundaries = result['boundaries']
    assert [(b['same_identity'], b['gap_seconds'], b['rewound']) for b in boundaries] == [
        (True, 60, False), (True, -840, True), (False, 40, False), ('unknown', 40, False)]
    paths = [Path(p) for p in result['records']]
    events = events_of(paths[2], 'continuity')
    assert len(events) == 1 and events[0]['payload']['rewound'] is True and events[0]['payload']['gap_seconds'] == -840
    assert events_of(paths[0], 'continuity') == []
    metric = metrics_of(paths[0])['lineage.continuity']
    assert metric.denominator == 4 and metric.count == 1 and metric.missing == 'unknown_identity'
    assert metric.value == boundaries
    assert len(events_of(paths[1], 'continuity')) == 1 and len(events_of(paths[4], 'continuity')) == 1
    # Re-scoring one admission writes a fresh record; stitching again restores its lineage rows.
    evaluate(second, FakeBinding(), tmp_path / 'evals', replace=True)
    assert events_of(paths[1], 'continuity') == []
    assert stitch(admissions, FakeBinding(), tmp_path / 'evals')['boundaries'] == boundaries
    assert len(events_of(paths[1], 'continuity')) == 1
    # The command line stitches the same lineage; a missing admission record is scored like evaluate-run.
    paths[3].unlink()
    assert main(['evaluate-lineage', *map(str, admissions), '--binding', 'fake', '--root', str(tmp_path / 'evals')],
        binding=FakeBinding()) == 0
    assert json.loads(capsys.readouterr().out)['boundaries'] == boundaries
    assert metrics_of(paths[3])['custody.uncertain_receipts'].denominator == 7    # the external numbers were used
    with pytest.raises(SystemExit):
        main(['evaluate-lineage', str(first), '--root', str(tmp_path / 'evals')])  # needs --binding
    capsys.readouterr()
    # A single run carries an empty continuity metric.
    solo = metrics_of(evaluate(lineage_run(tmp_path / 'solo', '6' * 32, [3600, 3660], 1, BASE), FakeBinding(),
        tmp_path / 'solo-evals'))['lineage.continuity']
    assert (solo.value, solo.count, solo.denominator) == ([], 0, 0)


# ---------------------------------------------------------------------------------------------
# Unsupported versions are refused with the file and version.

def test_unsupported_input_versions_are_errors(tmp_path):
    base = tmp_path / 'bad'
    directory = main_scenario(base)
    (directory / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/3', session=SESSION)))
    with pytest.raises(EvaluationError, match=r'manifest\.json.*campaign-run/3'):
        evaluate(directory, FakeBinding(), tmp_path / 'e1')
    (directory / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/5', session=SESSION)))
    host = directory / 'actors' / '001' / 'host.jsonl'
    original = host.read_text()
    host.write_text(original.replace('player-host/3', 'player-host/2'))
    with pytest.raises(EvaluationError, match=r'host\.jsonl.*player-host/2'):
        evaluate(directory, FakeBinding(), tmp_path / 'e2')
    host.write_text(original)
    connection = sqlite3.connect(directory / 'session.sqlite3')
    connection.execute("UPDATE metadata SET value='\"computer-session/2\"' WHERE key='schema'")
    connection.commit()
    connection.close()
    with pytest.raises(EvaluationError, match=r'session\.sqlite3.*computer-session/2'):
        evaluate(directory, FakeBinding(), tmp_path / 'e3')


def test_unsupported_memory_and_record_versions_are_errors(tmp_path):
    memory = tmp_path / 'old-memory.sqlite3'
    connection = sqlite3.connect(memory)
    connection.execute('CREATE TABLE metadata(schema TEXT)')
    connection.execute("INSERT INTO metadata VALUES('player-memory/1')")
    connection.execute('PRAGMA user_version=1')
    connection.commit()
    connection.close()
    directory = main_scenario(tmp_path / 'run')
    with pytest.raises(EvaluationError, match=r'old-memory\.sqlite3.*player-memory/2'):
        evaluate(directory, FakeBinding(), tmp_path / 'e', memory_store=memory)
    path = run_and_evaluate(tmp_path / 'ok')
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA user_version=9')
    connection.close()
    stale = sqlite3.connect(path)
    stale.execute("UPDATE metadata SET value='\"evaluation-record/2\"' WHERE key='schema'")
    stale.commit()
    stale.close()
    with pytest.raises(EvaluationError, match='evaluation-record/2'):
        open_readonly(path)
    with pytest.raises(EvaluationError, match='evaluation-record/2'):
        RecordWriter.open(path)


def test_missing_inputs_name_their_file(tmp_path):
    directory = main_scenario(tmp_path / 'run')
    (directory / 'manifest.json').unlink()
    with pytest.raises(EvaluationError, match=r'manifest\.json'):
        evaluate(directory, FakeBinding(), tmp_path / 'e')
    with pytest.raises(EvaluationError, match='not a run directory'):
        evaluate(tmp_path / 'absent', FakeBinding(), tmp_path / 'e')


def test_a_corrupt_frame_abstains_instead_of_being_read(tmp_path):
    directory = main_scenario(tmp_path / 'run')
    victim = directory / 'sources' / f'{SESSION}-4.png'  # the fourth capture belongs to step 4
    victim.write_bytes(b'not the original bytes')
    path = evaluate(directory, FakeBinding(), tmp_path / 'e', created_wall=1.0)
    connection = open_readonly(path)
    frames = {r.seq: r for r in read_readings(connection) if r.reader == 'core.frame'}
    assert frames[4].abstain == 'frame_integrity' and frames[4].value is None
    assert sum(1 for r in frames.values() if r.abstain) == 1
    connection.close()


def test_binding_reader_names_cannot_shadow_core_readers(tmp_path):
    class Greedy(FakeBinding):
        def read_frame(self, png):
            frame = super().read_frame(png)
            return FrameReading(frame.mode, frame.game_time, frame.identity, frame.vitals, frame.threat,
                frame.threat_count, frame.death, (Reading('core.frame', 1, 1, 1.0),))
    directory = main_scenario(tmp_path / 'run')
    with pytest.raises(EvaluationError, match='core reader name'):
        evaluate(directory, Greedy(), tmp_path / 'e')
    assert not list((tmp_path / 'e').rglob('*.sqlite3'))  # nothing half-written is left behind


# ---------------------------------------------------------------------------------------------
# Command line (with a fake binding injected through the test hook).

def test_evaluate_run_and_compare_commands(tmp_path, capsys):
    directory = main_scenario(tmp_path / 'run')
    root = tmp_path / 'evals'
    assert main(['evaluate-run', str(directory), '--binding', 'fake', '--root', str(root), '--arm', 'treatment'],
        binding=FakeBinding()) == 0
    out = json.loads(capsys.readouterr().out)
    record = Path(out['record'])
    assert record == record_path(root, SESSION, 'fake', 3) and out['last_seq'] == 14
    assert 'survival.game_hours' in out['metrics']
    # Host and custody figures come from the existing summaries.
    metrics = metrics_of(record)
    assert metrics['host.latency', 'response.p50'].value == pytest.approx(200)
    assert metrics['custody.uncertain_receipts'].denominator == 14  # the control summary counts native receipts
    from tools.evaluate import run_external
    external = run_external(directory)
    assert external['custody'] == dict(receipts=14, uncertain=0)
    assert len(external['response_ms']) == 14 and external['response_ms'][0] == pytest.approx(200)
    assert external['first_chunk_ms'][0] == pytest.approx(100)
    assert read_metadata(open_readonly(record))['arm'] == 'treatment'
    assert main(['evaluate-run', str(directory), '--binding', 'fake', '--root', str(root)], binding=FakeBinding()) == 1
    assert 'exists' in capsys.readouterr().err
    assert main(['evaluate-run', str(directory), '--binding', 'fake', '--root', str(root), '--replace', '--arm', 'treatment'],
        binding=FakeBinding()) == 0
    capsys.readouterr()
    # Compare: a second record under another arm label.
    other = main_scenario(tmp_path / 'run2')
    other_record = evaluate(other, FakeBinding(), tmp_path / 'evals2', created_wall=1.0)
    assert main(['evaluate-compare', str(record), str(other_record), '--horizon', '0.5',
        '--arm', f'{other_record}=control']) == 0
    result = json.loads(capsys.readouterr().out)
    assert set(result['arms']) == {'treatment', 'control'}
    assert result['arms']['control']['deaths'] == 1 and result['arms']['control']['rmst']['horizon'] == 0.5
    assert 'control|treatment' in result['logrank']
    assert main(['evaluate-compare', str(other_record), '--horizon', '0.5']) == 1  # no arm label anywhere
    assert 'arm' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(['evaluate-compare', str(record)])  # --horizon is required
    capsys.readouterr()
    assert main(['evaluate-run', str(directory), '--binding', 'nope', '--root', str(root)]) == 1
    assert 'Unknown binding' in capsys.readouterr().err
    # Table: one generated Markdown row per record, from a root or explicit files; nothing is written.
    before = sorted((p.name, p.read_bytes()) for p in root.rglob('*.sqlite3'))
    assert main(['evaluate-table', str(root), str(other_record)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].startswith('| Run | Arm |') and len(lines) == 4
    assert all(line.count('|') == lines[0].count('|') for line in lines)
    assert sorted((p.name, p.read_bytes()) for p in root.rglob('*.sqlite3')) == before  # the stores are unchanged


def test_evaluate_options_are_refused_for_other_commands_and_externals_are_used(tmp_path, capsys, monkeypatch):
    with pytest.raises(SystemExit):
        main(['host-summary', str(tmp_path), '--horizon', '1'])
    with pytest.raises(SystemExit):
        main(['evaluate-run', str(tmp_path)])  # needs --root and --binding
    capsys.readouterr()
    # Numbers the host and control summaries produce are what the core stores, not re-derived ones.
    directory = main_scenario(tmp_path / 'run')
    monkeypatch.setattr('tools.evaluate.run_external', lambda run: dict(response_ms=[10, 20, 30], first_chunk_ms=[1, 2],
        custody=dict(receipts=7, uncertain=2)))
    assert main(['evaluate-run', str(directory), '--binding', 'fake', '--root', str(tmp_path / 'evals')],
        binding=FakeBinding()) == 0
    metrics = metrics_of(Path(json.loads(capsys.readouterr().out)['record']))
    assert [metrics['host.latency', k].value for k in ('response.p50', 'response.p95', 'first_chunk.p50', 'first_chunk.p95')] == [20, 30, 1, 2]
    assert (metrics['host.latency', 'response.p50'].count, metrics['host.latency', 'first_chunk.p50'].count) == (3, 2)
    uncertain = metrics['custody.uncertain_receipts']
    assert (uncertain.value, uncertain.denominator, uncertain.count) == (pytest.approx(2 / 7), 7, 2)


# ---------------------------------------------------------------------------------------------
# Record extensions: episodes, run end, censor reasons, rows, replay.

def survival_of(path: Path) -> dict:
    return metrics_of(path)['survival.game_hours'].value


def test_a_restarted_clock_starts_a_new_episode_and_survival_uses_the_last(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        for index, t in enumerate((200_000, 200_060, 100, 160, 220)):  # the second world starts a day or more earlier
            run.step(a, 'input', [key('j')], F('in_play', t, identity=1, fill=index))
        run.finish()
        return directory
    path = run_and_evaluate(tmp_path, build)
    episodes = events_of(path, 'episode')
    assert [(e['seq_start'], e['source'], e['payload']['index'], e['payload']['reason']) for e in episodes] == [
        (3, 'derived', 1, 'clock_backward')]
    assert episodes[0]['payload']['previous_game_time'] == 200_060 and episodes[0]['payload']['game_time'] == 100
    value = survival_of(path)
    assert value['hours'] == pytest.approx(120 / 3600) and value['episode'] == 1 and value['episodes'] == 2
    assert value['start_game_time'] == 100 and value['end_game_time'] == 220
    # The first episode's long stretch is not mistaken for a long activity or a pace interval.
    assert events_of(path, 'long_activity') == []


def test_a_small_backward_step_is_still_a_rejected_reading_not_an_episode(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        for index, t in enumerate((3600, 3660, 3000, 3720)):
            run.step(a, 'input', [key('j')], F('in_play', t, identity=1, fill=index))
        run.finish()
        return directory
    path = run_and_evaluate(tmp_path, build)
    assert events_of(path, 'episode') == [] and survival_of(path)['hours'] == pytest.approx(120 / 3600)


def identity_run(directory: Path, readings: list[tuple[int, int]]) -> Path:
    run = Run(directory)
    a = run.actor()
    for index, (t, who) in enumerate(readings):
        run.step(a, 'input', [key('j')], F('in_play', t, identity=who, fill=index))
    run.finish()
    return directory


def test_a_confirmed_identity_change_starts_a_new_episode(tmp_path):
    path = evaluate(identity_run(tmp_path / 'a', [(3600, 1), (3660, 1), (3720, 2), (3780, 2), (3840, 2)]), FakeBinding(),
        tmp_path / 'evals', created_wall=1.0)
    episodes = events_of(path, 'episode')
    assert [(e['seq_start'], e['payload']['reason'], e['payload']['identity'], e['payload']['previous_identity'])
        for e in episodes] == [(3, 'identity_change', 'id2', 'id1')]
    assert survival_of(path)['hours'] == pytest.approx(120 / 3600)
    # An identity seen once is not confirmed, so it starts nothing.
    lone = evaluate(identity_run(tmp_path / 'b', [(3600, 1), (3660, 2), (3720, 1), (3780, 1)]), FakeBinding(),
        tmp_path / 'e2', created_wall=1.0)
    assert events_of(lone, 'episode') == []


def ended_run(directory: Path, *, finish: list[dict] = (), controls: list[dict] = (), settled: dict | None = None,
              status: str = 'completed', receipt: str = 'delivered', files: dict | None = None, hosts: bool = True,
              dead: bool = False, session: str = SESSION) -> Path:
    run = Run(directory, hosts=hosts, session=session)
    a = run.actor()
    for index, t in enumerate((3600, 3660, 3720)):
        run.step(a, 'input', [key('j')], F('in_play', t, identity=1, fill=index))
    if status != 'completed':
        run.step(a, 'input', [key('j')], F('in_play', 3780, identity=1, fill=9), status=status, receipt=receipt)
    if dead:
        run.step(a, 'input', [key('j')], F('dead', 3840, death=True, identity=1, fill=10))
    for index, fields in enumerate(controls):
        run.host[a].append(run.event(a, 'control-accepted', iso(BASE + 40 + index), session=SESSION, actor_id=a, **fields))
    for index, fields in enumerate(finish):
        run.host[a].append(run.event(a, 'player-finish', iso(BASE + 50 + index), request_id='request-1', report='r', **fields))
    run.finish(settled=settled)
    for name, value in (files or {}).items():
        (directory / name).write_text(json.dumps(value))
    return directory


@pytest.mark.parametrize('name, options, reason', [
    ('died', dict(dead=True), 'died'),
    ('player', dict(finish=[dict(disposition='cannot_continue', control_id=None)]), 'player_stop'),
    ('complete', dict(finish=[dict(disposition='task_complete', control_id=None)]), 'player_stop'),
    ('budget', dict(controls=[dict(control_id='c' * 32, control_type='orderly_stop')],
        finish=[dict(disposition='external_stop_complete', control_id='c' * 32)]), 'budget'),
    ('handoff', dict(settled=dict(ok=True, reason='handoff')), 'budget'),
    ('infra', dict(settled=dict(ok=False, reason='provider-error')), 'infrastructure'),
    ('custody', dict(status='unknown', receipt='unknown'), 'custody'),
    ('pause', dict(files={'watch-terminal.json': dict(schema='campaign-watch-terminal/3', reason='operator_pause',
        pause_reason='spend')}), 'owner_pause'),
    ('not-paused', dict(files={'watch-terminal.json': dict(schema='campaign-watch-terminal/3', reason='custodian_terminal',
        pause_reason=None)}), None),
    ('receipt', dict(files={'receipt.json': dict(schema='campaign-receipt/3', outcome='incomplete',
        driver=dict(ending_request=dict(trigger='http_attempts')))}), 'budget'),
    ('live', dict(hosts=False), None)])
def test_censor_reasons(tmp_path, name, options, reason):
    path = evaluate(ended_run(tmp_path / name, **options), FakeBinding(), tmp_path / 'evals', created_wall=1.0)
    value = survival_of(path)
    assert value['censor_reason'] == reason
    assert value['outcome'] == ('died' if reason == 'died' else 'censored')
    assert metrics_of(path)['run.infrastructure_loss'].value == int(reason in ('infrastructure', 'custody'))
    assert metrics_of(path)['run.provider_loss'].value == int(reason == 'infrastructure')


def test_end_facts_read_only_the_supported_receipt_and_terminal_versions(tmp_path, monkeypatch):
    from harness.evaluation.core.sources import read_end_facts
    archive_of(tmp_path, monkeypatch, {SESSION: dict(run='old01')})
    current = dict(schema='campaign-run/5', session=SESSION)
    archived = dict(schema='campaign-run/4', session=SESSION)
    directory = tmp_path / 'end'
    directory.mkdir()
    terminal = directory / 'watch-terminal.json'
    terminal.write_text(json.dumps(dict(schema='campaign-watch-terminal/3', reason='operator_pause', pause_reason='loop')))
    facts = read_end_facts(directory, current)
    assert facts.paused is True and facts.pause_reason == 'loop'
    # The archived /2 terminal is read for the Pause only, and only for an archived session; it has no reason of its own.
    terminal.write_text(json.dumps(dict(schema='campaign-watch-terminal/2', reason='operator_pause', pause_reason='loop')))
    facts = read_end_facts(directory, archived)
    assert facts.paused is True and facts.pause_reason is None
    for manifest in (current, dict(archived, session='f' * 32)):
        with pytest.raises(EvaluationError, match=r'watch-terminal\.json.*campaign-watch-terminal/2'):
            read_end_facts(directory, manifest)
    # No other shape counts as a Pause: not the old nested field, nor a forwarded reply on its own.
    terminal.write_text(json.dumps(dict(schema='campaign-watch-terminal/3', reason='custodian_terminal',
        pause=dict(reason='loop'), pause_reply_forwarded=True, pause_reason=None)))
    assert read_end_facts(directory, current).paused is False
    for found in ('campaign-watch-terminal/1', 'campaign-watch-terminal/4', None):
        terminal.write_text(json.dumps(dict(schema=found, reason='operator_pause')))
        for manifest in (current, archived):
            with pytest.raises(EvaluationError, match=rf'watch-terminal\.json.*{found}'):
                read_end_facts(directory, manifest)
    terminal.unlink()
    receipt = directory / 'receipt.json'
    receipt.write_text(json.dumps(dict(schema='campaign-receipt/3', outcome='complete')))
    assert read_end_facts(directory, current).outcome == 'complete'
    for found in ('campaign-receipt/2', 'campaign-receipt/4', None):
        receipt.write_text(json.dumps(dict(schema=found, outcome='complete')))
        with pytest.raises(EvaluationError, match=rf'receipt\.json.*{found}'):
            read_end_facts(directory, current)


def test_a_run_with_an_unsupported_terminal_or_receipt_version_is_an_error(tmp_path):
    for name, schema in (('watch-terminal.json', 'campaign-watch-terminal/1'), ('receipt.json', 'campaign-receipt/2')):
        directory = ended_run(tmp_path / name[:5], files={name: dict(schema=schema)})
        with pytest.raises(EvaluationError, match=rf'{name.replace(".", chr(92) + ".")}.*{schema}'):
            evaluate(directory, FakeBinding(), tmp_path / 'evals')


def archive_of(tmp_path: Path, monkeypatch, sessions: dict) -> None:
    import harness.evaluation.core.sources as sources
    path = tmp_path / 'archive-labels.json'
    path.write_text(json.dumps(dict(version=2, runs=sessions)))
    monkeypatch.setattr(sources, 'ARCHIVE_LABELS', path)


def archived_run(directory: Path, session: str = SESSION) -> Path:
    run = Run(directory, session=session)
    a = run.actor()
    for index, t in enumerate((3600, 3660, 3720)):
        run.step(a, 'input', [key('j')], F('in_play', t, identity=1, fill=index))
    run.finish()
    manifest = json.loads((directory / 'manifest.json').read_text())
    manifest['schema'] = 'campaign-run/4'
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    return directory


def test_a_campaign_run_4_manifest_is_read_only_for_a_listed_session(tmp_path, monkeypatch):
    listed = dict(run='old01', arm='pilot', start='S1', scenario='Evacuee', lineage=None, admission=None)
    archive_of(tmp_path, monkeypatch, {SESSION: listed})
    path = evaluate(archived_run(tmp_path / 'old01'), FakeBinding(), tmp_path / 'evals', created_wall=1.0)
    connection = open_readonly(path)
    assert read_run_facts(connection)['labels'] == dict(arm='pilot', start='S1', scenario='Evacuee', lineage=None, admission=None)
    assert read_run_facts(connection)['manifest_schema'] == 'campaign-run/4'
    connection.close()
    # The directory name is not the key: a renamed run directory is the same listed session.
    renamed = evaluate(archived_run(tmp_path / 'renamed'), FakeBinding(), tmp_path / 'other', created_wall=1.0)
    assert metrics_of(renamed)['survival.game_hours'].value['hours'] == pytest.approx(120 / 3600)


def test_a_campaign_run_4_manifest_of_an_unlisted_session_is_an_error(tmp_path, monkeypatch):
    archive_of(tmp_path, monkeypatch, {'f' * 32: dict(run=SESSION)})
    with pytest.raises(EvaluationError, match=r'manifest\.json.*campaign-run/4.*not listed'):
        evaluate(archived_run(tmp_path / SESSION), FakeBinding(), tmp_path / 'evals')
    archive_of(tmp_path, monkeypatch, {})
    with pytest.raises(EvaluationError, match='campaign-run/4'):
        evaluate(archived_run(tmp_path / 'again'), FakeBinding(), tmp_path / 'evals')


def test_an_archived_session_reads_its_v2_terminal_for_the_owner_pause(tmp_path, monkeypatch):
    archive_of(tmp_path, monkeypatch, {SESSION: dict(run='old01', arm='pilot', start='S1', scenario='Evacuee',
                                                     lineage=None, admission=None)})
    directory = archived_run(tmp_path / 'old01')
    (directory / 'watch-terminal.json').write_text(json.dumps(
        dict(schema='campaign-watch-terminal/2', reason='operator_pause')))
    path = evaluate(directory, FakeBinding(), tmp_path / 'evals', created_wall=1.0)
    assert survival_of(path)['censor_reason'] == 'owner_pause'


def test_a_campaign_run_5_run_with_a_v2_terminal_is_an_error(tmp_path, monkeypatch):
    # Listing the session does not matter: /2 is for campaign-run/4 manifests only.
    archive_of(tmp_path, monkeypatch, {SESSION: dict(run='old01')})
    directory = ended_run(tmp_path / 'current', files={'watch-terminal.json': dict(
        schema='campaign-watch-terminal/2', reason='operator_pause')})
    assert json.loads((directory / 'manifest.json').read_text())['schema'] == 'campaign-run/5'
    with pytest.raises(EvaluationError, match=r'watch-terminal\.json.*unsupported version.*campaign-watch-terminal/2'):
        evaluate(directory, FakeBinding(), tmp_path / 'evals')


def test_the_shipped_archive_lists_each_archived_session_once(tmp_path):
    from harness.evaluation.core.sources import archive_labels
    runs = archive_labels()
    assert len(runs) == 30 and all(len(key) == 32 and set(key) <= set('0123456789abcdef') for key in runs)
    assert len({item['run'] for item in runs.values()}) == 30
    assert all(set(item) >= {'run', 'arm', 'start', 'scenario', 'lineage', 'admission'} for item in runs.values())


def test_run_end_events_for_finishes_and_orderly_stops(tmp_path):
    control = dict(control_id='c' * 32, control_type='orderly_stop')
    path = evaluate(ended_run(tmp_path / 'one', controls=[control],
        finish=[dict(disposition='external_stop_complete', control_id='c' * 32)]), FakeBinding(), tmp_path / 'evals', created_wall=1.0)
    ends = events_of(path, 'run_end')
    assert [(e['payload']['reason'], e['payload']['orderly_stop'], e['payload']['control_id']) for e in ends] == [
        ('external_stop_complete', True, 'c' * 32)]
    assert events_of(path, 'custody_stop') == []
    two = evaluate(ended_run(tmp_path / 'two', finish=[dict(disposition='cannot_continue', control_id=None)]), FakeBinding(),
        tmp_path / 'e2', created_wall=1.0)
    assert [(e['payload']['reason'], e['payload']['orderly_stop']) for e in events_of(two, 'run_end')] == [('cannot_continue', False)]


def test_run_facts_labels_and_host_rows(tmp_path):
    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.host[a][0].update(model='m/x', provider='p', provider_routing=dict(only=['p']))
        run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
        run.call(a, 'computer_input', dict(actions=[]), dict(operation_id='o' * 32), error=True)
        run.host[a].append(run.event(a, 'tool-refused', iso(BASE + 20), request_id='request-1', tool_call_id='gone',
            tool='computer_input', reason='orderly-stop', dispatched=False, delivery='undelivered'))
        run.host[a].append(run.event(a, 'provider-retry', iso(BASE + 21), stage='eligible', request_id='request-1',
            retry_class='stream-start-error'))
        run.host[a].append(run.event(a, 'context-image-projection', iso(BASE + 22), request_id='request-1', omitted_images=2))
        run.finish(labels=dict(arm='X', start='S1', scenario='s', lineage=None, admission=None),
            effort='medium', files={'context.txt': 'g' * 64, 'prompt.txt': 'p' * 64},
            accounting=dict(prior_reserved_usd='10', ceiling_usd='25.5', prospective_reserved_usd='12'), limits=LIMITS)
        manifest = json.loads((directory / 'manifest.json').read_text())
        manifest['schema'] = 'campaign-run/5'
        (directory / 'manifest.json').write_text(json.dumps(manifest))
        return directory
    path = run_and_evaluate(tmp_path, build)
    connection = open_readonly(path)
    facts = read_run_facts(connection)
    assert facts['labels'] == dict(arm='X', start='S1', scenario='s', lineage=None, admission=None)
    assert (facts['model'], facts['provider'], facts['route'], facts['effort']) == ('m/x', 'p', dict(only=['p']), 'medium')
    assert (facts['guide_sha256'], facts['assignment_sha256']) == ('g' * 64, 'p' * 64)
    assert (facts['declared_ceiling_usd'], facts['spend_allowance_usd'], facts['limits']) == (25.5, 15.5, LIMITS)
    assert read_metadata(connection)['labels']['arm'] == 'X' and read_metadata(connection)['arm'] == 'X'
    calls = read_tool_calls(connection)
    by_status = {c.status: c for c in calls}
    assert len(calls) == 3 and set(by_status) == {'ok', 'error', 'refused'} and {c.tool for c in calls} == {'computer_input'}
    assert by_status['ok'].operation_id == f'{0x1001:032x}' and by_status['error'].operation_id == 'o' * 32
    assert by_status['error'].result_bytes > 0 and by_status['error'].latency_ms is not None
    assert by_status['refused'].latency_ms is None and by_status['refused'].tool_call_id == 'gone'
    requests = read_requests(connection)
    assert [(r.request_id, r.attempt, r.manifest, r.dollars) for r in requests] == [('request-1', 1, 'absent', 0.01)]
    assert (requests[0].retry_class, requests[0].omitted_images, requests[0].cache_write) == ('stream-start-error', 2, 1000)
    connection.close()
    assert metrics_of(path)['tools.calls', 'computer_input'].value == dict(calls=3, refused=1, errors=1)
    assert metrics_of(path)['tools.calls', 'player_source+zoom'].value == 0


def test_archived_manifests_use_supplied_labels(tmp_path):
    directory = main_scenario(tmp_path / 'run')
    path = evaluate(directory, FakeBinding(), tmp_path / 'evals', created_wall=1.0, labels=dict(arm='Old', start='S2'))
    connection = open_readonly(path)
    assert read_run_facts(connection)['labels']['arm'] == 'Old' and read_metadata(connection)['arm'] == 'Old'
    connection.close()


def test_manifest_replay_is_exact_and_rejects_a_broken_chain():
    from harness.evaluation.core.context import replay_manifests
    from harness.evaluation.core.sources import HostEvent

    def event(line, **fields):
        return HostEvent('actor', line, 'context-manifest', None, None, dict(type='context-manifest', **fields))

    def part(index, role, kind, **extra):
        return dict(index=index, role=role, kind=kind, bytes=10 + index, sha256=f'{index:064x}', **extra)
    first = [part(0, 'system', 'text'), part(1, 'user', 'text'), part(2, 'assistant', 'tool_call', tool_call_id='t1', tool='x')]
    second = [part(3, 'tool', 'tool_result_text', tool_call_id='t1', tool='x'),
        part(4, 'tool', 'image', state='sent', tool_call_id='t1', image_index=0, source_id='s-1')]
    events = [
        event(1, request_id='request-1', base_request_id=None, reused_prefix_parts=0, part_count=3, parts=first),
        event(2, request_id='request-2', base_request_id='request-1', reused_prefix_parts=3, part_count=5, parts=second),
        event(3, request_id='request-3', base_request_id='request-2', reused_prefix_parts=5, part_count=5),  # a retry resends
        event(4, request_id='request-4', base_request_id='request-3', reused_prefix_parts=4, part_count=5,
            parts=[part(4, 'tool', 'image', state='omitted', tool_call_id='t1', image_index=0)], omitted_image_indexes=[4]),
        event(5, request_id='request-5', base_request_id='request-4', reused_prefix_parts=5, part_count=5)]
    replayed = replay_manifests(events)
    assert [replayed[f'request-{n}']['part_count'] for n in range(1, 6)] == [3, 5, 5, 5, 5]
    assert replayed['request-3']['parts'] == replayed['request-2']['parts'] and replayed['request-3']['omitted_image_indexes'] == []
    assert replayed['request-4']['parts'][4]['state'] == 'omitted' and replayed['request-4']['parts'][:4] == replayed['request-2']['parts'][:4]
    assert replayed['request-5']['omitted_image_indexes'] == [4]  # absent means unchanged from the base
    assert [p['index'] for p in replayed['request-5']['parts']] == [0, 1, 2, 3, 4]
    for broken in (event(9, request_id='r', base_request_id='nope', reused_prefix_parts=0, part_count=0),
            event(9, request_id='r', base_request_id='request-1', reused_prefix_parts=9, part_count=9),
            event(9, request_id='r', base_request_id='request-1', reused_prefix_parts=3, part_count=4, parts=[])):
        with pytest.raises(EvaluationError):
            replay_manifests([*events[:1], broken])


def test_context_is_exact_with_a_manifest_and_reconstructed_without(tmp_path):
    from harness.evaluation.core.context import request_context
    from harness.evaluation.core.sources import read_run

    def build(directory):
        run = Run(directory)
        a = run.actor()
        run.step(a, 'input', [key('j')], F('in_play', 3600, fill=1))
        run.host[a].append(run.event(a, 'context-image-projection', iso(BASE + 30), request_id='request-2', omitted_images=1,
            omissions=[dict(tool_call_id='call-1', image_index=0, sha256='a' * 64)]))
        run.host[a].append(run.event(a, 'request-start', iso(BASE + 31), request_id='request-2', logical_request_id='request-2'))
        run.host[a].append(run.event(a, 'context-manifest', iso(BASE + 31), request_id='request-2', base_request_id=None,
            reused_prefix_parts=0, part_count=1, parts=[dict(index=0, role='system', kind='text', bytes=5, sha256='b' * 64)]))
        run.finish()
        return directory
    directory = build(tmp_path / 'run')
    inputs = read_run(directory)
    actor = inputs.actors[0]
    exact = request_context(directory, actor, inputs.host[actor], 'request-2')
    assert exact['exact'] is True and exact['part_count'] == 1 and exact['parts'][0]['sha256'] == 'b' * 64
    built = request_context(directory, actor, inputs.host[actor], 'request-1')
    assert built['exact'] is False and built['missing'] == ['assistant_text', 'reasoning']
    assert [(p['role'], p['kind']) for p in built['parts']] == [('system', 'text'), ('user', 'text')]
    assert built['parts'][0]['bytes'] == 5 and built['parts'][1]['bytes'] == len('ASSIGNMENT 1')
    with pytest.raises(EvaluationError, match='no request'):
        request_context(directory, actor, inputs.host[actor], 'request-99')
