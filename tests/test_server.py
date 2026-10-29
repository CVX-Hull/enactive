"""Actual loopback service over a receiver double; no native/game acceptance."""
from http.client import HTTPConnection
import json
import time
import uuid
from unittest.mock import patch

import pytest

from harness.application import Application
from harness.player.memory import Memory
from harness.server import serve
from harness.player_client import PlayerClient
from test_computer_runtime import make_runtime,key


@pytest.fixture
def service(tmp_path):
    runtime,channel,actor=make_runtime(tmp_path)
    memory=Memory(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts')
    server,thread=serve(app,0)
    config=tmp_path/'actor.json';config.write_text(json.dumps(dict(schema='player-adapter/1',
        base_url=f'http://127.0.0.1:{server.server_port}',session=runtime.session,**actor)))
    try:yield app,channel,actor,server.server_port,PlayerClient(config)
    finally:
        server.shutdown();server.server_close();thread.join(2);runtime.close();memory.close()


def post(port,path,value,token=None,origin=None):
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
    value,png,error=client.call('computer_observe',{})
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
        assert status==200 and value['stop_requested']
        assert time.monotonic()-started<1 and channel.stopped.is_set()


def test_sealed_actor_can_collect_but_cannot_stop_successor(service):
    app,channel,actor,port,client=service
    result,_,error=client.call('player_handoff',dict(ids=[],summary='Fixture unfinished task'))
    assert not error and client.sealed
    assert client.call('computer_result',dict(operation_id=result['operation_id']))[0]['status']=='sealed'
    app.runtime.confirm_quiescent(actor['actor_id'],result['operation_id'],host_quiescent=True)
    successor=app.runtime.add_actor()
    assert successor['actor_id']!=actor['actor_id']
    status,_=post(port,'/api/actor-stop',dict(session=app.runtime.session,reason='old actor'),actor['token'])
    assert status==400 and not channel.stopped.is_set()


def test_lost_handoff_response_stops_current_sealed_actor_and_cannot_resume(service):
    app,channel,actor,port,client=service
    original=client._post
    def lose(path,value,**kwargs):
        result=original(path,value,**kwargs)
        if path=='/api/tool' and value['tool']=='player_handoff':
            raise OSError('Fixture lost response after actual sealing')
        return result
    with patch.object(client,'_post',side_effect=lose):
        value,_,error=client.call('player_handoff',dict(ids=[],summary='Fixture unfinished work'))
    assert value['status']=='unknown' and not error and channel.stopped.is_set()
    collected,_,_=client.call('computer_result',dict(operation_id=value['operation_id']))
    assert collected['status']=='sealed'
    with pytest.raises(ValueError):
        app.runtime.confirm_quiescent(actor['actor_id'],value['operation_id'],host_quiescent=True)
    with pytest.raises(ValueError):app.runtime.add_actor()


def test_explicit_mcp_cancellation_can_stop_the_current_sealed_actor(service):
    app,channel,actor,port,client=service
    client.call('player_handoff',dict(ids=[],summary='Fixture unfinished work'))
    assert client.sealed and not channel.stopped.is_set()
    result=client.stop('MCP operation cancelled')
    assert result['stop_requested'] and channel.stopped.is_set()
