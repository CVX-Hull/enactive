"""Actual composition/SQLite/V8; receiver remains an explicit test double."""
import uuid
import pytest

from harness.application import Application
from harness.player.memory import Memory
from harness.computer.protocol import ControlError
from test_computer_runtime import make_runtime,key


def request_id():
    return uuid.uuid4().hex


def program(code):
    return dict(schema='player-program/1',code=code,parent_id=None,reason='fixture',
        source_ids=[],record_ids=[],applicability=None)


def test_local_program_click_refusal_leaves_basic_input_available(tmp_path):
    runtime,channel,actor=make_runtime(tmp_path)
    memory=Memory(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts')
    try:
        saved,_=app.call(actor['token'],'player_program_save',{'program':program('''function step(v,s){
            return {status:'act',state:s,actions:[{type:'click',x:10,y:10,button:'left'}],reason:'wrong geometry'};
        }''')},request_id())
        run_id=request_id()
        result,_=app.call(actor['token'],'player_program_run',dict(program_id=saved['id'],initial_state={},
            interpretation={},selection={'crop':None,'size':[4,4]},max_steps=2),run_id)
        assert result['status']=='refused'
        assert not channel.stopped.is_set()
        assert all(call[0]!='input' for call in channel.calls)
        recovered,_=app.call(actor['token'],'player_result',dict(operation_id=run_id),request_id())
        assert recovered['progress']['steps'][-1]['kind']=='input'
        assert recovered['collected_operations'][-1]['status']=='not_submitted_to_computer'
        after,_=runtime.input(actor['actor_id'],[key()])
        assert after['status']=='completed'
    finally:
        runtime.close();memory.close()


def test_authoring_same_request_id_collects_one_immutable_record(tmp_path):
    runtime,channel,actor=make_runtime(tmp_path)
    memory=Memory(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts')
    try:
        frame,_=runtime.observe(actor['actor_id'])
        value=dict(schema='player-record/1',kind='claim',text='fallible fixture claim',data={'quantity':1},
            sources=[frame['source']['source_id']],supports=[],supersedes=None,applicability=None,program_id=None)
        identity=request_id()
        first,_=app.call(actor['token'],'player_memory_append',dict(record=value),identity)
        second,_=app.call(actor['token'],'player_memory_append',dict(record=value),identity)
        assert first==second and first['id']==identity
        assert len(memory.query())==1
        assert memory.read_source(value['sources'][0])[1]==channel.png
        assert not channel.stopped.is_set()
    finally:
        runtime.close();memory.close()


def test_public_identity_cannot_be_reused_across_player_and_computer(tmp_path):
    runtime,channel,actor=make_runtime(tmp_path)
    memory=Memory(tmp_path/'player.sqlite3');app=Application(runtime,memory,tmp_path/'contexts')
    try:
        saved,_=app.call(actor['token'],'player_program_save',dict(program=program('''function step(v,s){
          return {status:'act',state:s,actions:[{type:'key',key:'x',modifiers:[]}],reason:'fixture'};
        }''')),request_id())
        identity=request_id()
        app.call(actor['token'],'player_program_run',dict(program_id=saved['id'],initial_state={},interpretation={},
            selection=dict(crop=None,size=[4,4]),max_steps=1),identity)
        count=len(channel.calls)
        with pytest.raises(ControlError):app.call(actor['token'],'computer_input',dict(actions=[key()]),identity)
        assert len(channel.calls)==count
        other=request_id()
        app.call(actor['token'],'computer_input',dict(actions=[key()]),other)
        with pytest.raises(ControlError):app.call(actor['token'],'player_program_save',dict(program=program('function step(v,s){}')),other)
        assert not channel.stopped.is_set()
    finally:runtime.close();memory.close()
