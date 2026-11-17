"""Actual loopback service over a receiver double; no native/game acceptance."""
from pathlib import Path
from http.client import HTTPConnection
import json
import threading
import time
import uuid
from unittest.mock import patch

import pytest

from harness.application import Application
from harness.player.journal import Journal
from harness.server import serve
from harness.player_client import PlayerClient
from test_computer_runtime import make_runtime,key


@pytest.fixture
def service(tmp_path):
    runtime,channel,actor=make_runtime(tmp_path)
    memory=Journal(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts',knowledge=Path(__file__).with_name('fixtures')/'empty-delivered-knowledge.json')
    server,thread=serve(app,0)
    config=tmp_path/'actor.json';config.write_text(json.dumps(dict(schema='player-adapter/2',
        base_url=f'http://127.0.0.1:{server.server_port}',session=runtime.session,**actor)))
    try:yield app,channel,actor,server.server_port,PlayerClient(config)
    finally:
        server.shutdown();server.server_close();thread.join(2);runtime.close();memory.close()


def actor_call(client, tool, args):
    return client.call(tool,{'intent':'Exercise the fixture '+tool,**args})


def post(port,path,value,token=None,origin=None):
    if path == '/api/tool' and isinstance(value.get('arguments'),dict):
        value = dict(value,arguments={'intent':'Exercise the fixture '+value['tool'],**value['arguments']})
    conn=HTTPConnection('127.0.0.1',port,timeout=3)
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    if origin:headers['Origin']=origin
    try:
        conn.request('POST',path,json.dumps(value),headers)
        reply=conn.getresponse();return reply.status,json.loads(reply.read())
    finally:conn.close()


def test_adapter_exact_image_and_duplicate_original_id(service):
    app,channel,actor,port,client=service
    value,png,error=actor_call(client,'computer_observe',{})
    assert not error and png==channel.png and value['source']['schema']=='computer-source/1'
    identity=uuid.uuid4().hex
    request=dict(operation_id=identity,tool='computer_input',arguments=dict(actions=[key()]))
    status,first=post(port,'/api/tool',request,actor['token']);calls=len(channel.calls)
    assert status==200
    assert post(port,'/api/tool',request,actor['token'])==(200,first)
    assert len(channel.calls)==calls
    assert post(port,'/api/mission/start',{},actor['token'])[0]==404
    assert post(port,'/api/tool',request,None)[0]==400
    assert post(port,'/api/pause',{},origin='http://example.com')[0]==400
    assert not channel.stopped.is_set()


def test_operator_pause_does_not_wait_for_player_service_lock(service):
    app,channel,actor,port,client=service
    with app.serial:
        started=time.monotonic()
        status,value=post(port,'/api/pause',{})
        assert status==200 and value['schema']=='computer-pause/1'
        assert value['session']==app.runtime.session and value['stop']['stop_requested']
        assert time.monotonic()-started<1 and channel.stopped.is_set()


def get(port,path):
    connection=HTTPConnection('127.0.0.1',port,timeout=3)
    try:
        connection.request('GET',path)
        reply=connection.getresponse();return reply.status,reply.read(),reply
    finally:connection.close()


def test_custodian_serves_only_status_source_pause_and_actor_routes(service):
    app,channel,actor,port,client=service
    before=len(channel.calls)
    for path in ('/','/index.html','/app.js','/app/main.js','/api/activity','/api/investigation',
                 '/api/view/runs','/investigation.js'):
        assert get(port,path)[0]==404,path
    assert post(port,'/api/investigation',{})[0]==400
    status,body,reply=get(port,'/api/status')
    assert status==200 and json.loads(body)['schema']=='computer-status/1'
    assert reply.getheader('Content-Security-Policy')=="default-src 'none'; frame-ancestors 'none'"
    assert get(port,'/api/source/'+app.runtime.session+'-1')[0]==400
    assert len(channel.calls)==before and not channel.stopped.is_set()


def test_hint_lost_reply_is_collectable_without_input_or_duplicate_authoring(service):
    app,channel,actor,port,client=service
    original=client._post
    arguments=dict(intent='Report uncertainty',text='This is an unverified player hint')
    def lose(path,value,**kwargs):
        result=original(path,value,**kwargs)
        if path=='/api/tool' and value['tool']=='player_hint':
            raise OSError('Fixture lost reply after committed hint')
        return result
    before=len(channel.calls)
    with patch.object(client,'_post',side_effect=lose):
        unknown,_,error=actor_call(client,'player_hint',arguments)
    assert not error and unknown['status']=='unknown' and unknown['collect_with']=='player_result'
    collected,_,error=actor_call(client,'player_result',dict(operation_id=unknown['operation_id']))
    assert not error and collected['status']=='completed' and collected['value']['schema']=='player-hint/1'
    status,repeated=post(port,'/api/tool',dict(operation_id=unknown['operation_id'],tool='player_hint',arguments=arguments),actor['token'])
    assert status==200 and repeated['value']==collected['value'] and len(app.journal.hints())==1
    assert len(channel.calls)==before and not channel.stopped.is_set()


def test_direct_http_cannot_omit_public_intent(service):
    app,channel,actor,port,client=service
    before=len(channel.calls)
    result,_,error=client.call('computer_input',dict(actions=[key()]))
    assert error and result['submission']=='none' and len(channel.calls)==before
    assert app.journal.calls()==[] and not channel.stopped.is_set()


def test_sealed_actor_can_collect_but_cannot_stop_successor(service):
    app,channel,actor,port,client=service
    result,_,error=actor_call(client,'player_handoff',dict(summary='Fixture unfinished task'))
    assert not error and client.sealed
    assert actor_call(client,'computer_result',dict(operation_id=result['operation_id']))[0]['status']=='sealed'
    app.runtime.confirm_quiescent(actor['actor_id'],result['operation_id'],host_quiescent=True)
    successor=app.runtime.add_actor()
    assert successor['actor_id']!=actor['actor_id']
    status,_=post(port,'/api/actor-stop',dict(session=app.runtime.session,reason='old actor'),actor['token'])
    assert status==400 and not channel.stopped.is_set()



@pytest.mark.parametrize('extra', [{'ids':[]},{'ids':['retired-root']},{'knowledge':{}}])
def test_retired_handoff_roots_are_refused_before_sealing(service,extra):
    app,channel,actor,port,client=service
    refused,_,error=actor_call(client,'player_handoff',dict(summary='Fixture unfinished task',**extra))
    assert error and refused['submission']=='none' and not client.sealed
    assert list(app.context_directory.glob('*.json'))==[] and not channel.stopped.is_set()
    value,_,error=actor_call(client,'computer_observe',{})
    assert not error and value['status']=='completed'


def test_the_final_actor_is_refused_a_handoff_without_any_state_change(service):
    app,channel,actor,port,client=service
    app.final_actor=actor['actor_id']
    refused,_,error=actor_call(client,'player_handoff',dict(summary='Fixture unfinished task'))
    assert error and refused['schema']=='player-error/1' and refused['submission']=='none'
    assert 'no successor is available' in refused['reason'] and 'final actor' in refused['reason'] and 'player_finish' in refused['reason']
    assert not client.sealed and list(app.context_directory.glob('*.json'))==[]
    assert app.runtime.actor_stage(actor['actor_id'])=='active'
    observed,_,error=actor_call(client,'computer_observe',{})
    assert not error and observed['status']=='completed'



def test_lost_handoff_response_stops_current_sealed_actor_and_cannot_resume(service):
    app,channel,actor,port,client=service
    original=client._post
    def lose(path,value,**kwargs):
        result=original(path,value,**kwargs)
        if path=='/api/tool' and value['tool']=='player_handoff':
            raise OSError('Fixture lost response after actual sealing')
        return result
    with patch.object(client,'_post',side_effect=lose):
        value,_,error=actor_call(client,'player_handoff',dict(summary='Fixture unfinished work'))
    assert value['status']=='unknown' and not error and channel.stopped.is_set()
    collected,_,_=actor_call(client,'computer_result',dict(operation_id=value['operation_id']))
    assert collected['status']=='sealed'
    with pytest.raises(ValueError):
        app.runtime.confirm_quiescent(actor['actor_id'],value['operation_id'],host_quiescent=True)
    with pytest.raises(ValueError):app.runtime.add_actor()


def test_explicit_mcp_cancellation_can_stop_the_current_sealed_actor(service):
    app,channel,actor,port,client=service
    actor_call(client,'player_handoff',dict(summary='Fixture unfinished work'))
    assert client.sealed and not channel.stopped.is_set()
    result=client.stop('MCP operation cancelled')
    assert result['stop_requested'] and channel.stopped.is_set()
