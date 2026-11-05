"""Actor serialization over real service records; no native/game/provider calls."""
import copy
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch
import uuid

import anyio
from mcp import types
import pytest

from harness.application import Application
from harness.computer.protocol import ControlError
from harness.player.contracts import PlayerError, canonical
from harness.player.memory import Memory
from harness.player.programs import ProgramRepository, ProgramRunner
from harness.player_mcp import make_server
from harness.player_view import UnsupportedResult, actor_error, actor_result
from test_computer_runtime import make_runtime, key
from test_player_context import program
from test_player_memory import record


OPAQUE = dict(remaining={'requests': 987654}, deadline_monotonic=123456,
              schema='computer-operation/999', value={'remaining': 'player meaning'})


@pytest.fixture
def service(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        yield app, runtime, channel, actor
    finally:
        runtime.close()
        memory.close()


def call(app, actor, name, args):
    return app.call(actor['token'], name, args, uuid.uuid4().hex)[0]


def test_direct_collection_handoff_and_accounting_stay_original(service):
    app, runtime, channel, actor = service
    raw = call(app, actor, 'computer_input', {'actions': [key()]})
    original = copy.deepcopy(raw)
    counts = runtime.store.counts()
    view = actor_result(raw)
    assert view['schema'] == 'player-computer-result/1'
    assert 'remaining' not in view and 'deadline_monotonic' not in view
    assert view['receipts'] == original['receipts']
    assert view['source'] == original['source']
    for field in ('operation_id', 'actor_id', 'session', 'status', 'created_wall', 'kind'):
        assert view[field] == original[field]
    collected = call(app, actor, 'computer_result', {'operation_id': raw['operation_id']})
    assert actor_result(collected) == view
    assert raw == original and runtime.store.operation(raw['operation_id']) == original
    assert runtime.store.counts() == counts
    assert [item[0] for item in channel.calls] == ['input', 'observe']
    handoff = call(app, actor, 'player_handoff', {'ids': [], 'summary': 'unfinished'})
    assert actor_result(handoff)['handoff'] == handoff['handoff']
    assert actor_result(handoff)['status'] == 'sealed'


def test_malformed_collection_id_keeps_repairable_feedback_without_computer_calls(service):
    app,runtime,channel,actor=service
    with pytest.raises(ControlError) as failure:
        call(app,actor,'computer_result',{'operation_id':'typo'})
    view=actor_result(dict(schema='player-error/1',error='ControlError',reason=str(failure.value),submission='rejected'))
    assert view['reason']=='Operation ID must be32 lowercase hexadecimal characters'
    assert view['input_replayed'] is False and channel.calls==[] and runtime.store.counts()['inputs']==0


def test_nested_program_result_collection_and_opaque_authored_data(service):
    app, runtime, channel, actor = service
    saved = call(app, actor, 'player_program_save', {'program': program(code="""
        function step(v,s){
          if(v.schema!=='program-view/4'||'remaining' in v || JSON.stringify(v.interpretation)!==JSON.stringify(s)) throw Error('wrong view');
          return {status:'yield',state:s,actions:null,reason:'remaining requests are player words'};
        }""")})
    args = dict(program_id=saved['id'], initial_state=OPAQUE, interpretation=OPAQUE,
                selection={'crop': None, 'size': [4, 4]})
    identity = uuid.uuid4().hex
    raw, _ = app.call(actor['token'], 'player_program_run', args, identity)
    snapshot = copy.deepcopy(raw)
    counts = runtime.store.counts()
    view = actor_result(raw)
    assert view['final_state'] == OPAQUE
    assert view['reason'] == 'remaining requests are player words'
    assert view['steps'][0]['result'] == raw['steps'][0]['result']
    assert raw == snapshot
    collected = call(app, actor, 'player_result', {'operation_id': identity})
    result = actor_result(collected)
    assert result['value'] == view
    assert result['collected_operations'][0]['schema'] == 'player-computer-result/1'
    assert 'remaining' not in result['collected_operations'][0]
    assert collected['collected_operations'][0]['remaining']
    assert runtime.store.counts() == counts
    assert app.memory.service_result(identity)['value'] == raw
    data = call(app, actor, 'player_memory_append', {'record': record(data=OPAQUE)})
    assert actor_result(data) == data
    assert actor_result(saved) == saved
    query = call(app, actor, 'player_memory_query', {})
    assert actor_result(query) == query
    context = call(app, actor, 'player_memory_context', {'ids': [data['id'], saved['id']]})
    assert actor_result(context) == context
    source_read = call(app, actor, 'player_source', {'source_id': raw['steps'][0]['source']['source_id']})
    assert actor_result(source_read) == source_read
    assert call(app, actor, 'computer_input', {'actions': [key()]})['status'] == 'completed'


def test_compile_fault_is_collected_once_and_healthy_direct_input_remains(service):
    app, runtime, channel, actor = service
    saved = call(app, actor, 'player_program_save', {'program': program(code='function step(')})
    args = dict(program_id=saved['id'], initial_state={}, interpretation={}, selection={'crop': None, 'size': [1, 1]})
    identity = uuid.uuid4().hex
    raw, _ = app.call(actor['token'], 'player_program_run', args, identity)
    assert raw['status'] == 'fault' and channel.calls == []
    assert actor_result(raw)['status'] == 'fault'
    collected = call(app, actor, 'player_result', {'operation_id': identity})
    assert actor_result(collected)['value'] == actor_result(raw)
    assert channel.calls == [] and not channel.stopped.is_set()
    assert call(app, actor, 'computer_input', {'actions': [key()]})['status'] == 'completed'


def test_valid_large_query_keeps_each_complete_record_and_copy_isolation():
    item = dict(record(text='x'*8192, data={'remaining': 'x'*16000}),
                id='record', actor_id='actor', created_wall=1)
    query = dict(schema='player-query/1', records=[item]*50, grants_authority=False)
    assert len(json.dumps(query)) > 1048576
    projected = actor_result(query)
    assert projected == query
    projected['records'][0]['data']['remaining'] = 'changed actor copy'
    assert query['records'][0]['data']['remaining'] == 'x'*16000


def test_controller_diagnostics_are_bounded_but_native_receipts_are_exact(service):
    app, runtime, channel, actor = service
    channel.unknown = True
    raw = call(app, actor, 'computer_input', {'actions': [key()]})
    raw['reason'] = 'Original trial has 987654 requests remaining'
    raw['receipts'][0]['reason'] = 'Controller private diagnostic 987654'
    view = actor_result(raw)
    assert view['status'] == 'unknown'
    assert '987654' not in canonical(view)
    assert view['receipts'][0]['id'] == raw['receipts'][0]['id']
    native = dict(raw['receipts'][0], schema='computer-receipt/2', disposition='partial', emitted_events=1)
    raw['receipts'] = [native]
    assert actor_result(raw)['receipts'] == [native]
    local = dict(native, schema='computer-local/1', disposition='rejected', emitted_events=0,
                 reason='Private controller remaining=987654')
    local_view = actor_result(dict(raw, status='refused', receipts=[local]))
    assert local_view['receipts'][0]['disposition'] == 'rejected'
    assert '987654' not in canonical(local_view)
    # A late native receipt adds evidence to the original unknown operation;
    # projection never rewrites its terminal status or sends input again.
    late_receipt = dict(native, disposition='delivered', emitted_events=2)
    channel.late[native['id']] = (late_receipt, None)
    counts = runtime.store.counts()
    collected = call(app, actor, 'computer_result', {'operation_id': raw['operation_id']})
    late_view = actor_result(collected)
    assert late_view['status'] == 'unknown'
    assert [r['schema'] for r in late_view['receipts']] == ['computer-transport/2', 'computer-receipt/2']
    assert late_view['receipts'][-1] == late_receipt
    assert runtime.store.counts() == counts
    with pytest.raises(ValueError):
        call(app, actor, 'computer_input', {'actions': [key()]})
    assert len(channel.calls) == 1


def test_transport_error_stop_and_validation_paths_preserve_control_facts(service):
    app, runtime, channel, actor = service
    raw = dict(schema='player-transport/1', operation_id='b'*32, session=runtime.session,
               actor_id=actor['actor_id'], kind='computer_input', status='unknown', reason='987654 left',
               collect_with='computer_result', input_replayed=False)
    result = actor_result(raw)
    assert result['schema'] == 'player-transport/2' and result['status'] == 'unknown'
    assert result['operation_id'] == raw['operation_id'] and result['input_replayed'] is False
    assert '987654' not in canonical(result) and raw['reason'] == '987654 left'
    error = dict(schema='player-error/1', error='ControlError', reason='987654 left',
                 operation_id='b'*32, submission='uncertain')
    assert actor_result(error)['submission'] == 'uncertain'
    assert actor_result(error)['operation_id'] == error['operation_id']
    for feedback in ('Unsupported basic key', 'Pointer exceeds original full-image coordinates',
                     "Invalid player data: 'view_schema' is a required property"):
        assert actor_result(dict(error, reason=feedback))['reason'] == feedback
    for feedback in ('Missing sources reference: absent', 'Integer must be within 1..96',
                     'Source unavailable: absent', 'Context selects at most 32 roots'):
        assert actor_result(dict(error, error='PlayerError', reason=feedback))['reason'] == feedback
        assert actor_error(PlayerError(feedback))['reason'] == feedback
    stop = call(app, actor, 'computer_stop', {})
    projected = actor_result(stop)
    assert projected['stop_requested'] == stop['stop_requested']
    assert projected['native_pause_confirmed'] == stop['native_pause_confirmed']
    assert actor_error(RuntimeError('987654 left'))['schema'] == 'player-error/2'
    assert '987654' not in canonical(actor_error(RuntimeError('987654 left')))


def test_unknown_envelopes_and_nested_versions_never_pass_through(service):
    app, runtime, channel, actor = service
    raw = call(app, actor, 'computer_observe', {})
    for bad in (dict(raw, schema='computer-operation/99'), dict(raw, surprise=987654),
                dict(raw, receipts=[dict(raw['receipts'][0], schema='computer-receipt/99')])):
        with pytest.raises(UnsupportedResult):
            actor_result(bad)
    for bad in ({'schema': 'unknown/1', 'value': OPAQUE}, {'remaining': 987654},
                {'schema': 'player-program/1', 'code': 'old executable'}):
        with pytest.raises(UnsupportedResult):
            actor_result(bad)
    assert actor_error(UnsupportedResult('PRIVATE'))['error'] == 'unsupported_result'
    nested = dict(schema='player-service-result/1', operation_id='b'*32, actor_id=actor['actor_id'],
                  kind='player_program_run', status='completed', value={'schema': 'player-program-run/99'},
                  progress={'steps': []}, grants_authority=False)
    with pytest.raises(UnsupportedResult):
        actor_result(nested)
    nested.update(status='pending', value=None, collected_operations=[dict(raw, schema='computer-operation/99')])
    with pytest.raises(UnsupportedResult):
        actor_result(nested)


def test_mcp_projects_success_errors_and_unknown_result_without_image_leak(service):
    app, runtime, channel, actor = service
    raw = call(app, actor, 'computer_observe', {})
    client = SimpleNamespace(config={'session': runtime.session, 'actor_id': actor['actor_id']},
                             call=lambda name, args: (raw, channel.png, False))
    # Capture the real adapter callback; exercise exactly its serialization and
    # exception path without starting a native receiver or provider connection.
    with patch('harness.player_mcp.Server') as server:
        make_server(client)
        callback = server.call_args.kwargs['on_call_tool']
    async def invoke():
        return await callback(None, types.CallToolRequestParams(name='computer_observe', arguments={}))
    result = anyio.run(invoke)
    assert json.loads(result.content[0].text) == actor_result(raw)
    assert result.content[1].mime_type == 'image/png'
    raw['schema'] = 'computer-operation/99'
    result = anyio.run(invoke)
    assert result.is_error and len(result.content) == 1
    assert json.loads(result.content[0].text)['error'] == 'unsupported_result'
    transport = dict(schema='player-transport/1', operation_id='b'*32, session=runtime.session,
                     actor_id=actor['actor_id'], kind='computer_input', status='unknown', reason='987654 left',
                     collect_with='computer_result', input_replayed=False)
    client.call = lambda name, args: (transport, None, False)
    result = anyio.run(invoke)
    assert json.loads(result.content[0].text) == actor_result(transport)
    error = dict(schema='player-error/1', error='ControlError', reason='Unsupported basic key', submission='none')
    client.call = lambda name, args: (error, None, True)
    result = anyio.run(invoke)
    assert result.is_error and json.loads(result.content[0].text) == actor_result(error)
    client.call = lambda name, args: (_ for _ in ()).throw(RuntimeError('987654 left'))
    result = anyio.run(invoke)
    assert result.is_error and '987654' not in result.content[0].text


def test_old_store_and_executable_formats_reject_before_port_effects(tmp_path):
    path = tmp_path / 'memory'
    with Memory(path) as memory:
        assert memory._db.execute('PRAGMA user_version').fetchone()[0] == 2
        assert memory._db.execute('SELECT schema FROM metadata').fetchone()[0] == 'player-memory/2'
        repo = ProgramRepository(memory)
        current = program()
        for old in (dict(current, schema='player-program/1'), dict(current, view_schema='program-view/3'),
                    {k: v for k, v in current.items() if k != 'view_schema'}):
            with pytest.raises(PlayerError):
                repo.save('actor', old)
        saved = repo.save('actor', current)
        damaged = dict(saved, view_schema='program-view/3')
        memory._db.execute('UPDATE programs SET document=? WHERE id=?', (canonical(damaged), saved['id']))
        memory._db.commit()
        class NoEffects:
            def observe(self, *args, **kwargs):
                pytest.fail('old executable reached computer port')
        result = ProgramRunner(repo, NoEffects()).run(saved['id'], 'actor', {}, {}, {'crop': None, 'size': [1, 1]})
        assert result['status'] == 'fault' and result['operations'] == []
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=1')
        db.execute("UPDATE metadata SET schema='player-memory/1'")
    before = path.read_bytes()
    with pytest.raises(PlayerError, match='fresh player-memory/2'):
        Memory(path)
    assert path.read_bytes() == before
