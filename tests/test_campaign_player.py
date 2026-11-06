"""Original host-attempt accounting and known prelaunch failures."""
import json
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from harness.computer.protocol import ControlError
from tools.campaign_player import HostEvents,ending_trigger,finish_interruption,run_hosts


def test_original_attempts_and_partial_trace_reservation(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[dict(type='host-start',telemetry_version=3,schema='player-host/3'),
          dict(type='request-start',request_id='request-1'),
          dict(type='request-start',request_id='request-2'),
          dict(type='settled',requests=2,ok=False)]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path,10)
    try:
        assert events.finish()['attempts_charged']==2
        with path.open('a') as stream:stream.write('{"partial":')
        result=events.finish()
        assert not result['accounting_complete'] and result['attempts_charged']==10
    finally:events.close()


@pytest.mark.parametrize('schema',['pi-player-host/4','player-host/2',None])
def test_trace_from_another_host_contract_is_refused(tmp_path,schema):
    path=tmp_path/'host.jsonl'
    path.write_text(json.dumps(dict(type='host-start',telemetry_version=3,schema=schema))+'\n')
    events=HostEvents(path,10)
    try:
        with pytest.raises(ControlError,match='Unsupported'):events.finish()
    finally:events.close()


def test_known_prelaunch_failure_has_zero_attempts_and_no_successor(tmp_path):
    application=SimpleNamespace(runtime=SimpleNamespace(add_actor=Mock(side_effect=OSError('fixture store refusal')),stop=Mock()))
    profile=dict(max_hosts=2,host_seconds=100,total_host_seconds=200,max_http_attempts=30)
    with patch('tools.campaign_player.subprocess.Popen') as launch:
        result=run_hosts(tmp_path,profile,dict(max_requests=20),application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['attempts_charged']==0
    assert result['actors'][0]['cleanup']==dict(process_absent=True,group_absent=True)
    assert 'OSError' in result['reason'] and not launch.called
    assert application.runtime.add_actor.call_count==1


def test_invalid_consumed_trace_cannot_become_valid_during_cleanup(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[dict(type='host-start',telemetry_version=3,schema='player-host/3'),
          dict(type='request-start',request_id='request-1'),
          dict(type='settled',requests=1,ok=True),
          dict(type='player-finish',disposition='task_complete'),
          dict(type='handoff')]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path,20)
    try:
        with pytest.raises(ControlError,match='Conflicting'):events.read()
        with pytest.raises(ControlError,match='trace failed validation'):events.finish()
    finally:events.close()


FAKE_HOST = """
import json, os, sys
from datetime import datetime, timezone
mode, *rest = sys.argv[1:]
flags = dict(zip(rest[::2], rest[1::2]))
assert mode == 'run' and sorted(flags) == ['--actor-id', '--config', '--context', '--effort', '--mcp-config', '--model', '--pending-control-id', '--prompt', '--session', '--timeout-seconds', '-o'], sys.argv
assert sorted(os.environ) >= ['FIXTURE_KEY', 'LANG', 'PATH'] and os.environ['FIXTURE_KEY'] == 'fixture-secret'
prompt = open(flags['--prompt']).read()
assert prompt.startswith('Frozen mission') and 'Software actor/resource note' not in prompt
assert 'HTTP attempts' not in prompt and 'final actor' not in prompt
def emit(**value): print(json.dumps(dict(wall_time=datetime.now(timezone.utc).isoformat(),**value)), flush=True)
emit(type='host-start', telemetry_version=3, schema='player-host/3')
emit(type='request-start', request_id='request-1')
ending = 'READ_CONTROL' in prompt
handoff = 'HANDOFF_RACE' in prompt and flags['--actor-id'] == 'a'*32
control = json.loads(sys.stdin.readline()) if ending else None
if control:
    assert control['schema'] == 'player-control/1' and control['type'] == 'orderly_stop'
    assert control['actor_id'] == flags['--actor-id'] and control['session'] == flags['--session']
if handoff:
    emit(type='handoff',actor_id=flags['--actor-id'],session=flags['--session'],handoff_id='d'*32,context_id='e'*32,context_sha256='f'*64,grants_authority=False)
    emit(type='settled',ok=True,reason='handoff',requests=1)
else:
    reason = 'external_stop_complete' if ending else 'task_complete'
    control_id = control['id'] if control else None
    if 'WRONG_CONTROL' in prompt: control_id='f'*32
    if 'NO_FINISH' not in prompt:
        emit(type='player-finish',disposition=reason,control_id=control_id,report='report',source_ids=[])
    emit(type='settled',ok=True,reason=reason,control_id=control_id,requests=1)
open(flags['-o'], 'w').write('report\\n')
"""


def driver_case(tmp_path,prompt='Frozen mission',*,two_actors=False,low_frames=False):
    adapter=tmp_path/'adapter.py';adapter.write_text(FAKE_HOST)
    (tmp_path/'context.txt').write_text('Frozen context');(tmp_path/'prompt.txt').write_text(prompt)
    actors=[dict(actor_id=c*32,token='t') for c in ('a','c')]
    application=SimpleNamespace(
        runtime=SimpleNamespace(add_actor=Mock(side_effect=actors),stop=Mock(),confirm_quiescent=Mock(),
            remaining=Mock(return_value=dict(inputs=10000,requests=10000,frames=5 if low_frames else 10000,frame_bytes=10**9)),
            process=SimpleNamespace(poll=lambda:None),channel=SimpleNamespace(stopped=threading.Event(),
                stop_origin=lambda:dict(requested_wall=None,reason='fixture fence')),session='b'*32),
        activity_view=SimpleNamespace(host_event=Mock()),host=None)
    reserve=dict(seconds=10,http_attempts=19 if 'READ_CONTROL' in prompt else 2,inputs=10,requests=10,frames=5,frame_bytes=1000)
    profile=dict(max_hosts=2 if two_actors else 1,host_seconds=100,total_host_seconds=200,max_http_attempts=30,effort='off',port=8766,
                 ending_reserve=reserve,session='b'*32,host=dict(argv=[sys.executable,str(adapter)]))
    route=dict(max_requests=20,api_key_env='FIXTURE_KEY',model=dict(id='fixture',name='fixture'))
    return profile,route,application


def test_driver_launches_selected_host_without_experimental_prompt_additions(tmp_path):
    profile,route,application=driver_case(tmp_path)
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    actor=result['actors'][0]
    assert result['outcome']=='player_task_complete_unassessed' and result['attempts_charged']==1, result
    assert actor['accounting_complete'] and actor['settled']['reason']=='task_complete'
    launched=json.loads((tmp_path/'actors/001/host-process.json').read_text())['argv']
    assert launched[:3]==[*profile['host']['argv'],'run']
    assert (tmp_path/'actors/001/player-final.txt').read_text()=='report\n'
    assert result['ending_request'] is None


def test_driver_cleanup_retains_full_charge_after_invalid_consumed_trace(tmp_path):
    profile,route,application=driver_case(tmp_path,two_actors=True)
    adapter=tmp_path/'adapter.py'
    adapter.write_text(FAKE_HOST+"\nemit(type='handoff')\n")
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    actor=result['actors'][0]
    assert result['outcome']=='incomplete' and result['attempts_charged']==20,result
    assert not actor['accounting_complete'] and actor['attempts_charged']==20
    assert application.runtime.add_actor.call_count==1 and not application.runtime.confirm_quiescent.called
    assert actor['cleanup']['process_absent'] and actor['cleanup']['group_absent']


@pytest.mark.parametrize('trigger',['seconds','http_attempts','inputs','requests','frames','frame_bytes'])
def test_each_external_resource_can_trigger_ending(trigger):
    reserve=dict(seconds=10,http_attempts=5,inputs=20,requests=20,frames=20,frame_bytes=100)
    seconds,attempts=100.,30
    mechanical=dict(inputs=100,requests=100,frames=100,frame_bytes=1000)
    assert ending_trigger(reserve,seconds,attempts,mechanical) is None
    if trigger=='seconds':seconds=10
    elif trigger=='http_attempts':attempts=5
    else:mechanical[trigger]=reserve[trigger]
    assert ending_trigger(reserve,seconds,attempts,mechanical)==('host_seconds' if trigger=='seconds' else trigger)


def test_controller_retains_control_intent_and_checks_direct_finish_identity(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL')
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_external_stop_complete_unassessed',result
    intent=json.loads((tmp_path/'orderly-stop.json').read_text())
    command=json.loads((tmp_path/'actors/001/control.json').read_text())
    assert intent['id']==command['id']==result['actors'][0]['settled']['control_id']
    assert intent['trigger']=='http_attempts'
    assert set(command)=={'schema','id','session','actor_id','type'}


def test_frame_reserve_requests_ending_before_host_attempt_reserve(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL',low_frames=True)
    profile['ending_reserve']['http_attempts']=2
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['ending_request']['trigger']=='frames' and result['attempts_charged']==1,result


@pytest.mark.parametrize('fault',['WRONG_CONTROL','NO_FINISH'])
def test_unbound_or_missing_direct_finish_never_accepts_stop(tmp_path,fault):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL '+fault)
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['actors'][0]['orchestration_error'],result
    application.runtime.stop.assert_called()
    assert result['attempts_charged']==1


def test_pending_stop_survives_verified_handoff_before_successor_action(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL HANDOFF_RACE',two_actors=True)
    with patch('tools.campaign_player._handoff_context',return_value='{"fallible":"unfinished work"}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_external_stop_complete_unassessed',result
    first=json.loads((tmp_path/'actors/001/control.json').read_text())
    second=json.loads((tmp_path/'actors/002/control.json').read_text())
    assert first['id']==second['id'] and first['actor_id']!=second['actor_id']
    assert result['attempts_charged']==2 and application.runtime.confirm_quiescent.call_count==1
    launched=json.loads((tmp_path/'actors/002/host-process.json').read_text())['argv']
    assert launched[launched.index('--pending-control-id')+1]==first['id']
    # Only an actor with an available successor is offered the handoff tool.
    tools=[json.loads((tmp_path/f'actors/{n}/mcp.json').read_text())['enabled_tools'] for n in ('001','002')]
    assert 'player_handoff' in tools[0] and 'player_handoff' not in tools[1]
    assert set(tools[0])-set(tools[1])=={'player_handoff'}


def test_single_host_admission_offers_no_handoff_tool(tmp_path):
    profile,route,application=driver_case(tmp_path)
    run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert 'player_handoff' not in json.loads((tmp_path/'actors/001/mcp.json').read_text())['enabled_tools']


def test_permanent_fence_cannot_be_overwritten_by_later_finish_report(tmp_path):
    profile,route,application=driver_case(tmp_path)
    application.runtime.channel.stopped.set()
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='interrupted',result
    assert result['actors'][0]['player_finish']['disposition']=='task_complete'
    assert result['actors'][0]['interruption']['stop']['reason']=='fixture fence'


def test_post_finish_cleanup_and_unknown_stop_origin_have_separate_outcomes():
    channel=SimpleNamespace(stopped=threading.Event(),stop_origin=lambda:dict(requested_wall=100.002,reason='Actor adapter closed'))
    channel.stopped.set()
    assert finish_interruption(channel) is None
    channel.stop_origin=lambda:dict(requested_wall=100.0005,reason='Unresolved first stop')
    assert finish_interruption(channel)['reason']=='Input permanently fenced outside accepted host cleanup'
