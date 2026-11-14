"""Original host-attempt and spend accounting, and known prelaunch failures."""
from decimal import Decimal
import json
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from harness.computer.protocol import ControlError
from tools.campaign_player import HostEvents,ending_trigger,finish_interruption,run_hosts
from tools.configure_player_tools import configuration


BOUND=Decimal('0.25')
START=dict(type='host-start',telemetry_version=5,schema='player-host/5')


def cost(request,amount,how='provider-reported',kind='response-complete'):
    return dict(type=kind,request_id=request,counted_cost_usd=amount,cost_counted_as=how)


def finished(tmp_path,rows,allowance=10):
    path=tmp_path/'host.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path,allowance,BOUND,Decimal('0.2'))
    try:return events.finish()
    finally:events.close()


def test_original_attempts_and_partial_trace_reservation(tmp_path):
    """Three requests: two priced by the provider and one counted at the bound. A trace that cannot be read to its
    end is incomplete."""
    path=tmp_path/'host.jsonl'
    rows=[START,
          dict(type='request-start',request_id='request-1'),cost('request-1','0.1'),
          dict(type='request-start',request_id='request-2'),cost('request-2','0.25','unpriced-bound'),
          dict(type='request-start',request_id='request-3'),cost('request-3','0.7'),
          dict(type='settled',unpriced_recall_requests=0,requests=3,ok=False,spent_usd='1.05',unpriced_requests=1)]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path,10,BOUND,Decimal('0.2'))
    try:
        result=events.finish()
        assert result['attempts_charged']==3 and result['accounting_complete']
        # 0.1 + 0.7 is exactly 0.8 here; the floating-point sum is 0.7999999999999999.
        assert (result['reported_usd'],result['unpriced_requests'],result['spent_usd'],result['spend_complete'])==('0.8',1,'1.05',True)
        assert events.counted_usd()==Decimal('1.05')
        with path.open('a') as stream:stream.write('{"partial":')
        result=events.finish()
        assert not result['accounting_complete'] and result['attempts_charged']==10
        assert (result['spent_usd'],result['spend_complete'])==('1.05',False)
    finally:events.close()


def test_recall_attempts_share_allowance_but_keep_their_own_bound(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[START,dict(type='request-start',request_id='recall-1',request_role='recall'),
          cost('recall-1','0.2','unpriced-bound'),dict(type='request-start',request_id='request-1'),
          cost('request-1','0.1'),dict(type='settled',requests=2,unpriced_requests=0,unpriced_recall_requests=1,spent_usd='0.3')]
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    events=HostEvents(path,2,BOUND,Decimal('0.2'))
    try:
        value=events.finish()
        assert events.counted_usd()==Decimal('0.3')
        assert value['accounting_complete'] and value['attempts_charged']==2
        assert value['unpriced_requests']==0 and value['unpriced_recall_requests']==1 and value['spent_usd']=='0.3'
    finally:events.close()
    with path.open('a') as stream:stream.write(json.dumps(dict(type='request-start',request_id='recall-2'))+'\n')
    events=HostEvents(path,2,BOUND,Decimal('0.2'))
    try:
        with pytest.raises(ControlError,match='accounting'):events.finish()
    finally:events.close()


def test_a_started_request_with_no_cost_record_counts_at_the_bound_and_leaves_the_spend_incomplete(tmp_path):
    """A host killed mid-request leaves a request with no cost record and no settlement. The request counts at
    the bound, and nothing vouches for the total."""
    rows=[START,dict(type='request-start',request_id='request-1'),cost('request-1','0.1'),
          dict(type='request-start',request_id='request-2')]
    result=finished(tmp_path,rows)
    assert (result['reported_usd'],result['unpriced_requests'],result['spent_usd'],result['spend_complete'])==('0.1',1,'0.35',False)
    assert not result['accounting_complete'] and result['attempts_charged']==10


@pytest.mark.parametrize('totals',[dict(spent_usd='0.1',unpriced_requests=1),dict(spent_usd='0.35',unpriced_requests=0),
    dict(spent_usd='0.35'),dict(unpriced_requests=1),dict(spent_usd=0.35,unpriced_requests=1),dict(spent_usd='0.35',unpriced_requests=True),{}])
def test_host_totals_that_differ_from_the_drivers_own_sums_leave_the_spend_incomplete(tmp_path,totals):
    rows=[START,dict(type='request-start',request_id='request-1'),cost('request-1','0.1'),
          dict(type='request-start',request_id='request-2'),cost('request-2','0.25','unpriced-bound')]
    agreed=finished(tmp_path,[*rows,dict(type='settled',unpriced_recall_requests=0,requests=2,ok=True,spent_usd='0.35',unpriced_requests=1)])
    assert agreed['accounting_complete'] and agreed['spend_complete'] and agreed['attempts_charged']==2
    (tmp_path/'host.jsonl').unlink()
    result=finished(tmp_path,[*rows,dict(type='settled',unpriced_recall_requests=0,requests=2,ok=True,**totals)])
    assert not result['accounting_complete'] and not result['spend_complete'] and result['attempts_charged']==10
    assert result['spent_usd']=='0.35'


def test_a_reported_cost_longer_than_a_declared_amount_may_be_is_counted_exactly(tmp_path):
    """The host writes the provider's own digits: 19 and 23 fractional digits here, more than a declared amount
    may carry. The trace is read, and no digit is rounded away in the sums."""
    long19,long23='0.0034500000000000004','0.00000012345678901234567'
    rows=[START,dict(type='request-start',request_id='request-1'),cost('request-1',long19),
          dict(type='request-start',request_id='request-2'),cost('request-2',long23),
          dict(type='request-start',request_id='request-3'),cost('request-3','123456789012.5'),
          dict(type='settled',unpriced_recall_requests=0,requests=3,ok=True,spent_usd='123456789012.50345012345678901274567',unpriced_requests=0)]
    result=finished(tmp_path,rows)
    assert result['accounting_complete'] and result['spend_complete']
    assert result['reported_usd']==result['spent_usd']=='123456789012.50345012345678901274567'


@pytest.mark.parametrize('record',[cost('request-2','0.1'),cost('request-1','0.1','estimated'),cost('request-1',0.1),
    cost('request-1','1e-1'),cost('request-1','0.2','unpriced-bound'),dict(type='response-complete',request_id='request-1')])
def test_a_cost_record_the_driver_cannot_count_makes_the_trace_unreadable(tmp_path,record):
    path=tmp_path/'host.jsonl'
    rows=[START,dict(type='request-start',request_id='request-1'),record,dict(type='settled',unpriced_recall_requests=0,requests=1,ok=True)]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path,10,BOUND,Decimal('0.2'))
    try:
        with pytest.raises(ControlError):events.finish()
        assert events.spend(False)==dict(reported_usd='0',unpriced_requests=1,unpriced_recall_requests=0,spent_usd='0.25',spend_complete=False)
    finally:events.close()


@pytest.mark.parametrize('schema,telemetry',[('pi-player-host/5',4),('player-host/3',3),('player-host/3',4),('player-host/5',3),(None,4)])
def test_trace_from_another_host_contract_is_refused(tmp_path,schema,telemetry):
    path=tmp_path/'host.jsonl'
    path.write_text(json.dumps(dict(type='host-start',telemetry_version=telemetry,schema=schema))+'\n')
    events=HostEvents(path,10,BOUND,Decimal('0.2'))
    try:
        with pytest.raises(ControlError,match='Unsupported'):events.finish()
    finally:events.close()


def test_known_prelaunch_failure_has_zero_attempts_and_no_successor(tmp_path):
    application=SimpleNamespace(runtime=SimpleNamespace(add_actor=Mock(side_effect=OSError('fixture store refusal')),stop=Mock()))
    profile=dict(max_hosts=2,host_seconds=100,total_host_seconds=200,max_http_attempts=30,spend_limit_usd='1')
    with patch('tools.campaign_player.subprocess.Popen') as launch:
        result=run_hosts(tmp_path,profile,dict(max_requests=20,unpriced_request_usd='0.25',recall=dict(unpriced_request_usd='0.2',max_requests=5)),application,'fixture-secret',
            threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['attempts_charged']==0
    assert (result['spent_usd'],result['spend_complete'])==('0',True)
    assert result['actors'][0]['cleanup']==dict(process_absent=True,group_absent=True)
    assert 'OSError' in result['reason'] and not launch.called
    assert application.runtime.add_actor.call_count==1


def test_invalid_consumed_trace_cannot_become_valid_during_cleanup(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[START,
          dict(type='request-start',request_id='request-1'),
          dict(type='settled',unpriced_recall_requests=0,requests=1,ok=True),
          dict(type='player-finish',disposition='task_complete'),
          dict(type='handoff')]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path,20,BOUND,Decimal('0.2'))
    try:
        with pytest.raises(ControlError,match='Conflicting'):events.read()
        with pytest.raises(ControlError,match='trace failed validation'):events.finish()
    finally:events.close()


FAKE_HOST = """
import json, os, sys
from datetime import datetime, timezone
mode, *rest = sys.argv[1:]
flags = dict(zip(rest[::2], rest[1::2]))
assert mode == 'run' and sorted(flags) == ['--actor-id', '--config', '--context', '--delivered-knowledge', '--effort', '--finish-reserve-usd', '--mcp-config', '--model', '--pending-control-id', '--prompt', '--session', '--timeout-seconds', '-o'], sys.argv
assert sorted(os.environ) >= ['FIXTURE_KEY', 'LANG', 'PATH'] and os.environ['FIXTURE_KEY'] == 'fixture-secret'
prompt = open(flags['--prompt']).read()
assert prompt.startswith('Frozen mission') and 'Software actor/resource note' not in prompt
assert 'HTTP attempts' not in prompt and 'final actor' not in prompt
def emit(**value): print(json.dumps(dict(wall_time=datetime.now(timezone.utc).isoformat(),**value)), flush=True)
route = json.load(open(flags['--config']))
emit(type='host-start', telemetry_version=5, schema='player-host/5', spend_limit_usd=route['spend_limit_usd'])
recall_made = int('WITH_RECALL' in prompt and route['recall']['max_requests']>0)
if recall_made:
    emit(type='request-start',request_id='recall-1',request_role='recall')
    emit(type='response-complete',request_id='recall-1',counted_cost_usd='0',cost_counted_as='provider-reported')
emit(type='request-start', request_id='request-1')
spent = '0.0034500000000000004' if 'LONG_COST' in prompt else '0.004'
emit(type='response-complete', request_id='request-1', counted_cost_usd=spent, cost_counted_as='provider-reported')
ending = 'READ_CONTROL' in prompt
handoff = 'HANDOFF_RACE' in prompt and flags['--actor-id'] == 'a'*32
control = json.loads(sys.stdin.readline()) if ending else None
if control:
    assert control['schema'] == 'player-control/1' and control['type'] == 'orderly_stop'
    assert control['actor_id'] == flags['--actor-id'] and control['session'] == flags['--session']
if handoff:
    emit(type='handoff',actor_id=flags['--actor-id'],session=flags['--session'],handoff_id='d'*32,context_id='e'*32,context_sha256='f'*64,grants_authority=False)
    emit(type='settled',unpriced_recall_requests=0,ok=True,reason='handoff',requests=1+recall_made,spent_usd=spent,unpriced_requests=0)
else:
    reason = 'external_stop_complete' if ending else 'task_complete'
    control_id = control['id'] if control else None
    if 'WRONG_CONTROL' in prompt: control_id='f'*32
    if 'NO_FINISH' not in prompt:
        emit(type='player-finish',disposition=reason,control_id=control_id,report='report',source_ids=[])
    emit(type='settled',unpriced_recall_requests=0,ok=True,reason=reason,control_id=control_id,requests=1+recall_made,spent_usd=spent,unpriced_requests=0)
open(flags['-o'], 'w').write('report\\n')
"""


def driver_case(tmp_path,prompt='Frozen mission',*,two_actors=False,low_frames=False):
    adapter=tmp_path/'adapter.py';adapter.write_text(FAKE_HOST)
    (tmp_path/'context.txt').write_text('Frozen context');(tmp_path/'prompt.txt').write_text(prompt)
    (tmp_path/'delivered-knowledge.json').write_text(json.dumps(dict(schema='delivered-knowledge/1',version=None,coverage=None,articles=[],facts=[])))
    actors=[dict(actor_id=c*32,token='t') for c in ('a','c')]
    application=SimpleNamespace(
        runtime=SimpleNamespace(add_actor=Mock(side_effect=actors),stop=Mock(),confirm_quiescent=Mock(),
            remaining=Mock(return_value=dict(inputs=10000,requests=10000,frames=5 if low_frames else 10000,frame_bytes=10**9)),
            process=SimpleNamespace(poll=lambda:None),channel=SimpleNamespace(stopped=threading.Event(),
                stop_origin=lambda:dict(requested_wall=None,reason='fixture fence')),session='b'*32),
        host=None)
    reserve=dict(seconds=10,http_attempts=19 if 'READ_CONTROL' in prompt else 2,inputs=10,requests=10,frames=5,frame_bytes=1000,usd='0.01')
    profile=dict(max_hosts=2 if two_actors else 1,host_seconds=100,total_host_seconds=200,max_http_attempts=30,effort='off',port=8766,
                 ending_reserve=reserve,session='b'*32,host=dict(argv=[sys.executable,str(adapter)]),spend_limit_usd='1')
    # Each fake host makes one request that reports $0.004.
    route=dict(recall=dict(model=dict(id='fixture'),every=5,max_requests=5,unpriced_request_usd='0.2'),max_requests=20,spend_limit_usd='1',unpriced_request_usd='0.25',api_key_env='FIXTURE_KEY',model=dict(id='fixture',name='fixture'))
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
    # The trace could not be read to its end: what it showed is recorded, the spend is incomplete and no successor starts.
    assert (actor['spent_usd'],actor['spend_complete'])==('0.004',False)
    assert (result['reported_usd'],result['spent_usd'],result['spend_complete'])==('0.004','0.004',False)
    assert application.runtime.add_actor.call_count==1 and not application.runtime.confirm_quiescent.called
    assert actor['cleanup']['process_absent'] and actor['cleanup']['group_absent']


@pytest.mark.parametrize('trigger',['seconds','http_attempts','usd','inputs','requests','frames','frame_bytes'])
def test_each_external_resource_can_trigger_ending(trigger):
    reserve=dict(seconds=10,http_attempts=5,inputs=20,requests=20,frames=20,frame_bytes=100,usd='0.05')
    seconds,attempts,dollars=100.,30,Decimal('0.0500001')
    mechanical=dict(inputs=100,requests=100,frames=100,frame_bytes=1000)
    assert ending_trigger(reserve,seconds,attempts,dollars,mechanical) is None
    if trigger=='seconds':seconds=10
    elif trigger=='http_attempts':attempts=5
    elif trigger=='usd':dollars=Decimal('0.05')
    else:mechanical[trigger]=reserve[trigger]
    assert ending_trigger(reserve,seconds,attempts,dollars,mechanical)==dict(seconds='host_seconds',usd='spend').get(trigger,trigger)


def test_the_dollar_reserve_requests_the_orderly_finish(tmp_path):
    """$0.01 declared, $0.007 kept for the ending: after one $0.004 response $0.006 is left, so the driver asks
    the player to finish, exactly as it does when requests run low."""
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL')
    profile['spend_limit_usd']='0.01';profile['ending_reserve'].update(http_attempts=2,usd='0.007')
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_external_stop_complete_unassessed',result
    intent=json.loads((tmp_path/'orderly-stop.json').read_text())
    assert (intent['trigger'],intent['spend_remaining_usd'])==('spend','0.006')
    assert intent['id']==json.loads((tmp_path/'actors/001/control.json').read_text())['id']==result['actors'][0]['settled']['control_id']
    assert (result['reported_usd'],result['unpriced_requests'],result['unpriced_request_usd'],result['spent_usd'],
            result['spend_complete'])==('0.004',0,'0.25','0.004',True)


def test_a_successors_limit_is_cut_to_the_digits_a_route_may_carry(tmp_path):
    """The first actor's cost has 19 fractional digits. What remains has 19 too; the successor's route gets it cut
    down to 18, never rounded up, and the totals keep every digit."""
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL HANDOFF_RACE LONG_COST',two_actors=True)
    with patch('tools.campaign_player._handoff_context',return_value='{"fallible":"unfinished work"}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_external_stop_complete_unassessed',result
    assert json.loads((tmp_path/'actors/002/route.json').read_text())['spend_limit_usd']=='0.996549999999999999'
    assert (result['reported_usd'],result['spent_usd'],result['spend_complete'])==('0.0069000000000000008','0.0069000000000000008',True)


def test_no_successor_is_started_when_no_dollars_remain(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL HANDOFF_RACE',two_actors=True)
    profile['spend_limit_usd']='0.004';profile['ending_reserve'].update(http_attempts=2,usd='0.001')
    with patch('tools.campaign_player._handoff_context',return_value='{"fallible":"unfinished work"}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['reason']=='The dollar limit leaves nothing for another actor',result
    assert application.runtime.add_actor.call_count==1 and len(result['actors'])==1
    assert not (tmp_path/'actors/002').exists()
    assert (result['spent_usd'],result['spend_complete'])==('0.004',True)


def test_driver_narrows_recall_allowance_and_freezes_only_delivered_knowledge(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL HANDOFF_RACE',two_actors=True)
    profile['max_http_attempts']=3;route['max_requests']=3
    with patch('tools.campaign_player._handoff_context',return_value='{"fallible":"unfinished work"}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert len(result['actors'])==2,result
    for name,maximum in (('001',3),('002',2)):
        actor=tmp_path/'actors'/name
        selected=json.loads((actor/'route.json').read_text())
        assert selected['max_requests']==selected['recall']['max_requests']==maximum
        frozen=json.loads((actor/'frozen.json').read_text())
        assert frozen['schema']=='player-host-inputs/3'
        assert 'delivered-knowledge.json' in frozen['files']
        assert not any('private' in key for key in frozen['files'])


def test_recall_allowance_is_consumed_across_actors(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL HANDOFF_RACE WITH_RECALL',two_actors=True)
    route['recall']['max_requests']=1
    with patch('tools.campaign_player._handoff_context',return_value='{}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert len(result['actors'])==2,result
    assert [a['allocated_recall_attempts'] for a in result['actors']]==[1,0]
    assert [a['observed_recall_attempts'] for a in result['actors']]==[1,0]
    assert result['recall_attempts_charged']==1
    assert json.loads((tmp_path/'actors/002/route.json').read_text())['recall']['max_requests']==0


def test_incomplete_actor_consumes_its_whole_recall_allowance(tmp_path):
    profile,route,application=driver_case(tmp_path,two_actors=True)
    (tmp_path/'adapter.py').write_text(FAKE_HOST+"\nemit(type='handoff')\n")
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert not result['actors'][0]['accounting_complete']
    assert result['actors'][0]['recall_attempts_charged']==result['recall_attempts_charged']==route['recall']['max_requests']


def test_driver_copies_delivered_knowledge_as_exact_bytes(tmp_path):
    import hashlib
    profile,route,application=driver_case(tmp_path)
    source=tmp_path/'delivered-knowledge.json'
    data=source.read_bytes()+b'\r\n'
    source.write_bytes(data)
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['actors'][0]['accounting_complete']
    target=tmp_path/'actors/001/delivered-knowledge.json'
    assert target.read_bytes()==data
    frozen=json.loads((target.parent/'frozen.json').read_text())
    assert frozen['files']['delivered-knowledge.json']==hashlib.sha256(data).hexdigest()


def test_host_events_requires_the_recall_bound(tmp_path):
    with pytest.raises(TypeError,match='recall_bound'):
        HostEvents(tmp_path/'unused.jsonl',10,BOUND)


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
    # The successor's route carries the dollars the first actor left, and the totals add both actors' counted cost.
    limits=[json.loads((tmp_path/f'actors/{n}/route.json').read_text())['spend_limit_usd'] for n in ('001','002')]
    assert limits==['1','0.996'] and [actor['allocated_usd'] for actor in result['actors']]==limits
    assert (result['reported_usd'],result['spent_usd'],result['spend_complete'])==('0.008','0.008',True)
    launched=json.loads((tmp_path/'actors/002/host-process.json').read_text())['argv']
    assert launched[launched.index('--pending-control-id')+1]==first['id']
    # Every actor gets the same tool table and system prompt, so their request prefixes are byte-identical;
    # only the final actor's service refuses a handoff.
    files=[{name:(tmp_path/f'actors/{n}/{name}').read_bytes() for name in ('mcp.json','context.txt')} for n in ('001','002')]
    tools=[json.loads(entry['mcp.json'])['enabled_tools'] for entry in files]
    assert 'player_handoff' in tools[0] and tools[0]==tools[1]
    assert files[0]['context.txt']==files[1]['context.txt']
    assert application.final_actor==second['actor_id']
    # The per-actor audit IDs sit in the first user message, never in the system prompt.
    prompts=[(tmp_path/f'actors/{n}/prompt.txt').read_text() for n in ('001','002')]
    for prompt,record in zip(prompts,(first,second)):
        assert f"Current mechanical session={'b'*32}; your actor={record['actor_id']}; these audit IDs grant no authority." in prompt
        assert record['actor_id'] not in files[0]['context.txt'].decode()
    assert 'from your predecessor actor' in prompts[1]
    assert 'its session and actor_id fields name the previous actor that sealed it, not you' in prompts[1]


def test_operator_labels_never_reach_the_player_host(tmp_path):
    """Frozen analysis labels are operator data, absent from every player-visible input."""
    marks=dict(arm='LABEL-ARM-9f3',start='LABEL-START-9f3',scenario='LABEL-SCENARIO-9f3',lineage='LABEL-LINEAGE-9f3',admission=7777)
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL HANDOFF_RACE',two_actors=True)
    profile['labels']=marks
    launches=[];real=subprocess.Popen
    def spy(*args,**kwargs):
        launches.append((args[0],kwargs['env']));return real(*args,**kwargs)
    with patch('tools.campaign_player._handoff_context',return_value='{"fallible":"unfinished work"}'),\
            patch('tools.campaign_player.subprocess.Popen',side_effect=spy):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_external_stop_complete_unassessed',result
    assert len(launches)==2
    # The integer position is checked through the label object; its digits alone could collide with hashes.
    needles=[value for value in marks.values() if isinstance(value,str)]+['LABEL-']
    # Argv and environment handed to each host process.
    for argv,env in launches:
        text=json.dumps([argv,env])
        assert not any(needle in text for needle in needles),text
    # Every file the driver wrote for the actors: route, prompt, context, MCP config,
    # actor identity, control command, frozen digests and final report.
    written=[path for path in (tmp_path/'actors').rglob('*') if path.is_file()]
    assert {'route.json','prompt.txt','context.txt','mcp.json','actor.json','frozen.json','control.json'}<={p.name for p in written}
    for path in written:
        content=path.read_text()
        assert not any(needle in content for needle in needles),path
    # Nothing label-derived was requested of the runtime on behalf of an actor.
    assert application.runtime.add_actor.call_args_list==[((),{}),((),{})]


def test_single_host_admission_keeps_the_constant_tool_table_and_marks_its_actor_final(tmp_path):
    profile,route,application=driver_case(tmp_path)
    run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert json.loads((tmp_path/'actors/001/mcp.json').read_text())['enabled_tools']==configuration('x')['enabled_tools']
    assert 'player_handoff' in json.loads((tmp_path/'actors/001/mcp.json').read_text())['enabled_tools']
    assert application.final_actor=='a'*32


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
