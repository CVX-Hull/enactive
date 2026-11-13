"""The memory-read reader on a fixture trace: two actors, a handoff, a query, a failed read and a read (#594)."""
from datetime import datetime, timezone
import json
from pathlib import Path

from harness.evaluation.core.host import (ToolCall, frame_source, host_facts, memory_reads, names_record, record_ids,
    returned_records, typed_text)
from harness.evaluation.core.records import RecordWriter, StepRow
from harness.evaluation.core.sources import read_carry, read_host
from harness.player.memory import Memory
from tools.memory_reads import main

SESSION = 'c' * 32
FIRST, SECOND = 'a' * 32, 'b' * 32
BASE = 4_000_000_000.0  # later than any clock that runs this test: the store stamps its records with the present
TORCH, LOCKER, CLOSING = '1' * 32, '2' * 32, '3' * 32


def document(text: str, **fields) -> dict:
    return dict(dict(schema='player-record/1', kind='work', text=text, data={}, sources=[], supports=[],
        supersedes=None, applicability=None, program_id=None), **fields)


def stored(identity: str, actor: str, created: float, text: str, **fields) -> dict:
    return dict(document(text, **fields), id=identity, actor_id=actor, created_wall=created)


class Trace:
    """One actor's host trace: every request makes one tool call, one second after the last."""

    def __init__(self, actor: str, start: float) -> None:
        self.actor, self.wall, self.requests = actor, start, 0
        self.events = [dict(type='host-start', schema='player-host/4', telemetry_version=4, session=SESSION,
            actor_id=actor, wall_time=self.iso(), monotonic_ms=0)]

    def iso(self) -> str:
        return datetime.fromtimestamp(self.wall, timezone.utc).isoformat()

    def call(self, tool: str, arguments: dict, result: dict, *, error: bool = False, record: dict | None = None) -> None:
        """`record` is the full operation record the tool server serves beside a short result."""
        self.requests += 1
        self.wall += 1
        request = f'request-{self.requests}'
        common = dict(wall_time=self.iso(), monotonic_ms=self.requests * 1000.0, request_id=request)
        self.events += [dict(common, type='request-start', logical_request_id=request),
            dict(common, type='response-complete', stop_reason='toolUse', usage_available=False,
                response_progress=dict(content_bytes=0, reasoning_bytes=12)),
            dict(common, type='tool-start', tool_call_id='call', tool=tool, arguments=arguments),
            dict(common, type='tool-result', tool_call_id='call', tool=tool,
                result=dict(content=[dict(type='text', text=json.dumps(result))], isError=error,
                    **({} if record is None else dict(structuredContent=record))))]

    def type(self, text: str) -> None:
        frame = f'{SESSION}-{len(self.events)}'
        self.call('computer_input', dict(actions=[dict(type='key', key='/', modifiers=[]), dict(type='text', text=text)]),
            dict(operation_id=f'{len(self.events):032x}', source=dict(source_id=frame)))

    def write(self, directory: Path) -> None:
        directory.mkdir(parents=True)
        (directory / 'host.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in self.events))


def build(root: Path) -> Path:
    """`run/` with a first actor that writes the torch record and hands it off, and a successor that types "torch",
    queries (the carried torch record and the locker record, new to it), then acts, reads the locker record again
    and closes. The lineage store holds a fourth record that no read returns."""
    run = root / 'run'
    torch = stored(TORCH, FIRST, BASE + 2, 'The torch needs fuel.')
    locker = stored(LOCKER, 'e' * 32, BASE - 3600, 'The shelter locker holds supplies.',
        data=dict(resources='rations and batteries'), sources=[f'{SESSION}-9'])
    first = Trace(FIRST, BASE)
    first.type('torch')
    first.call('player_memory_append', dict(record=document(torch['text'])), torch)
    first.call('player_handoff', dict(ids=[TORCH], summary='See the linked record.'), dict(kind='handoff'))
    first.write(run / 'actors' / '001')
    (run / 'contexts').mkdir()
    (run / 'contexts' / 'packet.json').write_text(json.dumps(dict(schema='player-handoff-context/1', actor_id=FIRST,
        knowledge=dict(records=[torch], programs=[]))))
    second = Trace(SECOND, BASE + 100)
    second.type('torch')
    second.call('player_memory_query', dict(limit=20), dict(schema='player-query/1', records=[torch, locker]))
    second.call('player_memory_read', dict(record_id='f' * 32), dict(error='missing'), error=True)
    second.type('battery')
    second.type('torch')
    second.call('player_source', dict(source_id=f'{SESSION}-9'), dict(source_id=f'{SESSION}-9'))
    second.call('player_memory_read', dict(record_id=LOCKER), locker)
    second.call('player_memory_append', dict(record=document('Closing.', supports=[LOCKER])),
        stored(CLOSING, SECOND, BASE + 108, 'Closing.', supports=[LOCKER]))
    second.write(run / 'actors' / '002')
    with Memory(root / 'store.sqlite3') as memory:
        memory.append('e' * 32, document(locker['text'], data=locker['data']), request_id=LOCKER)
        memory.append(FIRST, document(torch['text']), request_id=TORCH)
        memory.append(SECOND, document('Never delivered.'), request_id='4' * 32)
    return run


def facts_of(run: Path):
    host = dict(read_host(directory / 'host.jsonl', directory.name) for directory in sorted((run / 'actors').iterdir()))
    return host_facts(tuple(host), host)


def test_reads_list_records_held_ids_and_the_calls_around_them(tmp_path):
    run = build(tmp_path)
    query, read = memory_reads(facts_of(run), read_carry(run))  # the failed read is not listed
    assert (query.call.tool, query.request, query.actor_requests) == ('player_memory_query', 2, 8)
    assert [record['id'] for record in query.records] == record_ids(query.call) == [TORCH, LOCKER]
    assert query.held == {TORCH}  # the handoff context carried it; the locker record is new to this actor
    assert [call.tool for call in query.before] == ['computer_input']
    assert [call.tool for call in query.after] == ['player_memory_read', 'computer_input', 'computer_input',
        'player_source', 'player_memory_read', 'player_memory_append']
    assert [(r.call.decision - 3, r.record_id, r.how, r.detail, r.repeated) for r in query.references] == [
        (4, LOCKER, 'typed', 'battery', False),  # "battery" finds the record's "batteries"
        (5, TORCH, 'typed', 'torch', True),  # typed before the read as well, so the read did not prompt it
        (6, LOCKER, 'source', f'{SESSION}-9', False),
        (7, LOCKER, 'record', 'read', False),
        (8, LOCKER, 'record', 'supports', False)]
    assert (read.request, [record['id'] for record in read.records], read.held) == (7, [LOCKER], {LOCKER})
    assert [r.detail for r in read.references] == ['supports']
    assert memory_reads(facts_of(run))[0].held == frozenset()  # without the contexts nothing is known to be carried


def test_a_short_computer_result_gives_its_operation_and_frame_from_the_full_record_and_its_text_size_from_the_text(tmp_path):
    frame = f'{SESSION}-3'
    shown = dict(schema='player-computer-result/2', status='completed', source_id=frame, width=4, height=4)
    full = dict(schema='player-computer-operation/1', operation_id='7' * 32, status='completed', source=dict(source_id=frame))
    trace = Trace(FIRST, BASE)
    trace.call('computer_input', dict(actions=[]), shown, record=full)
    trace.call('computer_input', dict(actions=[]), dict(operation_id='8' * 32, source=dict(source_id=f'{SESSION}-4')))  # an earlier trace
    trace.write(tmp_path / 'actors' / '001')
    host = dict([read_host(tmp_path / 'actors' / '001' / 'host.jsonl', '001')])
    short, earlier = host_facts(tuple(host), host).calls
    assert (short.operation_id, frame_source(short)) == ('7' * 32, frame)
    assert short.result_bytes == len(json.dumps(shown).encode())  # what the model read, not the record beside it
    assert (earlier.operation_id, frame_source(earlier)) == ('8' * 32, f'{SESSION}-4')


def test_text_and_record_helpers():
    locker = dict(text='The shelter locker holds supplies.', data=dict(resources='rations and batteries'))
    assert names_record('battery', locker) and names_record('q:shelter locker', locker)
    assert not names_record('bat', locker) and not names_record('locker key', locker) and not names_record('12 ?', locker)
    call = ToolCall('actor', 0, None, 1, 1, 'computer_input', dict(actions=[dict(type='key', key='a', modifiers=[]),
        dict(type='text', text='rope'), dict(type='wait', seconds=1)]))
    assert typed_text(call) == ['rope']
    assert typed_text(ToolCall('actor', 0, None, 1, 1, 'player_source', dict(actions=[dict(type='text', text='x')]))) == []
    assert returned_records(ToolCall('actor', 0, None, 1, 1, 'player_memory_query', {}, result=dict(records='none'))) == []


def test_tool_reports_counts_ages_game_time_the_store_and_rediscoveries(tmp_path, capsys):
    run = build(tmp_path)
    with RecordWriter.create(tmp_path / 'records' / SESSION / 'record.sqlite3', dict(game_time_unit='seconds')) as writer:
        writer.append_steps([StepRow(1, 'o' * 32, FIRST, 'input', BASE - 4000, 1, None, None, 500, 'in_play', None, None, None),
            StepRow(2, 'p' * 32, SECOND, 'input', BASE + 101, 2, None, None, 9500, 'in_play', None, None, None)], [])
    probes = tmp_path / 'probes'
    probes.mkdir()
    frames = [json.loads(line)['result']['content'][0]['text'] for line in
        (run / 'actors' / '002' / 'host.jsonl').read_text().splitlines() if '"computer_input"' in line and 'tool-result' in line]
    early, late = (json.loads(text)['source']['source_id'] for text in frames[:2])
    (probes / 'run-002.jsonl').write_text(''.join(json.dumps(line) + '\n' for line in [
        dict(type='fact', id='F1', statement='The locker holds batteries', category='resource', stored=LOCKER[:6]),
        dict(type='event', fact='F1', event='rediscovered', frame=early, note='before the query'),
        dict(type='event', fact='F1', event='rediscovered', frame=late, note='after the query'),
        dict(type='end', frames_viewed=2)]))
    arguments = [str(tmp_path), '--records', str(tmp_path / 'records'), '--store', str(tmp_path / 'store.sqlite3'),
        '--probes', str(probes)]
    assert main([*arguments, '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert (result['runs'], result['traces'], result['tool_calls']) == (1, 2, 11)
    assert result['memory_calls'] == dict(player_memory_append=2, player_memory_query=1, player_memory_read=2)
    assert (result['responses'], result['responses_with_text'], result['responses_with_reasoning']) == (11, 0, 11)
    assert (result['reads_by_first_actors'], result['reads_by_successors']) == (0, 2)
    assert (result['handoff_contexts'], result['handoff_contexts_carrying_records']) == (1, 1)
    assert (result['records_returned'], result['distinct_records_returned'], result['returned_already_held']) == (3, 2, 2)
    query = result['reads'][0]
    assert (query['run'], query['actor'], query['request'], query['actor_requests'], query['game_time']) == ('run', '002', 2, 8, 9500)
    assert [(r['id'], r['author'], r['held'], r['age_seconds'], r['age_game_seconds']) for r in query['records']] == [
        (TORCH, 'run/001', True, 100, 9000), (LOCKER, 'e' * 32, False, 3702, 9000)]
    assert [call['typed'] for call in query['before']] == [['torch']] and query['calls_after'] == 6
    assert query['after'][1]['did'] == '/ "battery"' and query['after'][0]['error'] is True
    assert {row['id']: (row['returned_by_reads'], row['carried_by_handoff']) for row in result['store']} == {
        LOCKER: (2, False), TORCH: (1, True), '4' * 32: (0, False)}
    assert [(row['note'], row['given'], row['existed']) for row in result['rediscoveries']] == [
        ('before the query', [], True), ('after the query', ['own write or read'], True)]
    assert main(arguments) == 0  # the text listing renders the same result
    text = capsys.readouterr().out
    assert '2 reads (0 by the 1 first actors, 2 by the 1 successors) returned 3 records (2 distinct), 2 already held' in text
    assert "reference request 4 typed 'battery' -> 222222" in text
    assert '2 rediscoveries of facts with a stored record; in 2 the record had been written; in 1 of those' in text
