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
from harness.player.knowledge import empty
from tools.campaign_player import HostEvents,LiveKnowledge,ending_trigger,finish_interruption,run_hosts
from tools.configure_player_tools import configuration


START=dict(type='host-start',telemetry_version=9,schema='player-host/9')


def cost(request,amount,how='provider-reported',kind='response-complete'):
    return dict(type=kind,request_id=request,reported_cost_usd=amount,counted_cost_usd=amount,cost_counted_as=how)


def finished(tmp_path,rows):
    path=tmp_path/'host.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path)
    try:return events.finish()
    finally:events.close()


def test_observed_attempts_and_partial_trace(tmp_path):
    """Three requests: two priced by the provider and one unknown. A trace that cannot be read to its
    end is incomplete."""
    path=tmp_path/'host.jsonl'
    rows=[START,
          dict(type='request-start',request_id='request-1'),cost('request-1','0.1'),
          dict(type='request-start',request_id='request-2'),cost('request-2',None,'unpriced'),
          dict(type='request-start',request_id='request-3'),cost('request-3','0.7'),
          dict(type='settled',unpriced_recall_requests=0,requests=3,player_requests=3,recall_requests=0,ok=False,spent_usd='0.8',unpriced_requests=1)]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path)
    try:
        result=events.finish()
        assert result['observed_attempts']==3 and result['accounting_complete']
        # 0.1 + 0.7 is exactly 0.8 here; the floating-point sum is 0.7999999999999999.
        assert (result['reported_usd'],result['unpriced_requests'],result['spent_usd'],result['spend_complete'])==('0.8',1,'0.8',True)
        assert events.counted_usd()==Decimal('0.8')
        with path.open('a') as stream:stream.write('{"partial":')
        result=events.finish()
        assert not result['accounting_complete'] and result['observed_attempts']==3
        assert (result['spent_usd'],result['spend_complete'])==('0.8',False)
    finally:events.close()


def test_recall_attempts_are_observed_and_keep_unknown_cost_separate(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[START,dict(type='request-start',request_id='recall-1',request_role='recall'),
          cost('recall-1',None,'unpriced'),dict(type='request-start',request_id='request-1'),
          cost('request-1','0.1'),dict(type='settled',requests=2,player_requests=1,recall_requests=1,unpriced_requests=0,unpriced_recall_requests=1,spent_usd='0.1')]
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    events=HostEvents(path)
    try:
        value=events.finish()
        assert events.counted_usd()==Decimal('0.1')
        assert value['accounting_complete'] and value['observed_attempts']==2
        assert value['unpriced_requests']==0 and value['unpriced_recall_requests']==1 and value['spent_usd']=='0.1'
    finally:events.close()
    with path.open('a') as stream:stream.write(json.dumps(dict(type='request-start',request_id='recall-2'))+'\n')
    events=HostEvents(path)
    try:
        with pytest.raises(ControlError,match='event follows settlement'):events.finish()
        assert events.observations()['observed_attempts']==2
    finally:events.close()


def test_a_started_request_without_a_cost_record_keeps_the_subtotal_and_flags_incomplete_trace(tmp_path):
    """A host killed mid-request preserves the observed provider subtotal and lacks a complete trace."""
    rows=[START,dict(type='request-start',request_id='request-1'),cost('request-1','0.1'),
          dict(type='request-start',request_id='request-2')]
    result=finished(tmp_path,rows)
    assert (result['reported_usd'],result['unpriced_requests'],result['spent_usd'],result['spend_complete'])==('0.1',1,'0.1',False)
    assert not result['accounting_complete'] and result['observed_attempts']==2


@pytest.mark.parametrize('totals',[dict(spent_usd='0.35',unpriced_requests=1),dict(spent_usd='0.1',unpriced_requests=0),
    dict(spent_usd='0.1'),dict(unpriced_requests=1),dict(spent_usd=0.1,unpriced_requests=1),dict(spent_usd='0.1',unpriced_requests=True),{}])
def test_host_totals_that_differ_from_the_drivers_own_sums_leave_the_spend_incomplete(tmp_path,totals):
    rows=[START,dict(type='request-start',request_id='request-1'),cost('request-1','0.1'),
          dict(type='request-start',request_id='request-2'),cost('request-2',None,'unpriced')]
    agreed=finished(tmp_path,[*rows,dict(type='settled',unpriced_recall_requests=0,requests=2,player_requests=2,recall_requests=0,ok=True,spent_usd='0.1',unpriced_requests=1)])
    assert agreed['accounting_complete'] and agreed['spend_complete'] and agreed['observed_attempts']==2
    (tmp_path/'host.jsonl').unlink()
    result=finished(tmp_path,[*rows,dict(type='settled',unpriced_recall_requests=0,requests=2,player_requests=2,recall_requests=0,ok=True,**totals)])
    assert not result['accounting_complete'] and not result['spend_complete'] and result['observed_attempts']==2
    assert result['spent_usd']=='0.1'


def test_a_reported_cost_longer_than_a_declared_amount_may_be_is_counted_exactly(tmp_path):
    """The host writes the provider's own digits: 19 and 23 fractional digits here, more than a declared amount
    may carry. The trace is read, and no digit is rounded away in the sums."""
    long19,long23='0.0034500000000000004','0.00000012345678901234567'
    rows=[START,dict(type='request-start',request_id='request-1'),cost('request-1',long19),
          dict(type='request-start',request_id='request-2'),cost('request-2',long23),
          dict(type='request-start',request_id='request-3'),cost('request-3','123456789012.5'),
          dict(type='settled',unpriced_recall_requests=0,requests=3,player_requests=3,recall_requests=0,ok=True,spent_usd='123456789012.50345012345678901274567',unpriced_requests=0)]
    result=finished(tmp_path,rows)
    assert result['accounting_complete'] and result['spend_complete']
    assert result['reported_usd']==result['spent_usd']=='123456789012.50345012345678901274567'


@pytest.mark.parametrize('record',[cost('request-2','0.1'),cost('request-1','0.1','estimated'),cost('request-1',0.1),
    cost('request-1','1e-1'),cost('request-1','0.2','unpriced-bound'),dict(type='response-complete',request_id='request-1')])
def test_a_cost_record_the_driver_cannot_count_makes_the_trace_unreadable(tmp_path,record):
    path=tmp_path/'host.jsonl'
    rows=[START,dict(type='request-start',request_id='request-1'),record,dict(type='settled',unpriced_recall_requests=0,requests=1,ok=True)]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path)
    try:
        with pytest.raises(ControlError):events.finish()
        assert events.spend(False)==dict(reported_usd='0',unpriced_requests=1,unpriced_recall_requests=0,spent_usd='0',spend_complete=False)
    finally:events.close()


@pytest.mark.parametrize('schema,telemetry',[('pi-player-host/6',4),('player-host/6',6),('player-host/3',3),('player-host/3',4),('player-host/7',7),('player-host/8',8),('player-host/9',8),('player-host/8',9),(None,4)])
def test_trace_from_another_host_contract_is_refused(tmp_path,schema,telemetry):
    path=tmp_path/'host.jsonl'
    path.write_text(json.dumps(dict(type='host-start',telemetry_version=telemetry,schema=schema))+'\n')
    events=HostEvents(path)
    try:
        with pytest.raises(ControlError,match='Unsupported'):events.finish()
    finally:events.close()


def test_known_prelaunch_failure_has_zero_attempts_and_no_successor(tmp_path):
    application=SimpleNamespace(runtime=SimpleNamespace(add_actor=Mock(side_effect=OSError('fixture store refusal')),stop=Mock()))
    profile=dict(max_hosts=2,host_seconds=100,total_host_seconds=200,spend_limit_usd='1')
    with patch('tools.campaign_player.subprocess.Popen') as launch:
        result=run_hosts(tmp_path,profile,dict(unpriced_request_usd='0.25',recall=dict(unpriced_request_usd='0.2')),application,'fixture-secret',
            threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['observed_attempts']==0
    assert (result['spent_usd'],result['spend_complete'])==('0',True)
    assert result['actors'][0]['cleanup']==dict(process_absent=True,group_absent=True)
    assert 'OSError' in result['reason'] and not launch.called
    assert application.runtime.add_actor.call_count==1


def test_invalid_consumed_trace_cannot_become_valid_during_cleanup(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[START,
          dict(type='request-start',request_id='request-1'),
          dict(type='player-finish',disposition='task_complete'),
          dict(type='handoff')]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path)
    try:
        with pytest.raises(ControlError,match='Conflicting'):events.read()
        with pytest.raises(ControlError,match='trace failed validation'):events.finish()
    finally:events.close()


FAKE_HOST = """
import json, os, sys
from datetime import datetime, timezone
mode, *rest = sys.argv[1:]
flags = dict(zip(rest[::2], rest[1::2]))
updates = flags.pop('--knowledge-updates', None)
assert mode == 'run' and sorted(flags) == ['--actor-id', '--config', '--context', '--delivered-knowledge', '--effort', '--finish-reserve-usd', '--mcp-config', '--model', '--pending-control-id', '--prompt', '--session', '--timeout-seconds', '-o'], sys.argv
assert sorted(os.environ) >= ['FIXTURE_KEY', 'LANG', 'PATH'] and os.environ['FIXTURE_KEY'] == 'fixture-secret'
prompt = open(flags['--prompt']).read()
assert (updates is not None) == ('LIVE_UPDATES' in prompt), sys.argv
import time
if updates is not None and flags['--actor-id'] == 'a'*32 and 'STALLED' not in prompt:
    # The first actor's host stands in for the curator runner: it leaves a version whole in the run's
    # delivery directory, then waits for the driver to list it, as a host would find it before a request.
    import hashlib
    actor = os.path.dirname(updates)
    run = os.path.dirname(os.path.dirname(actor))
    assert open(updates).read() == ''
    delivered = os.path.join(run, 'curator-runner', 'delivered')
    os.makedirs(delivered)
    data = open(os.path.join(run, 'published-v3.json'), 'rb').read()
    with open(os.path.join(delivered, '.v3.json.tmp'), 'wb') as stream: stream.write(data)
    os.replace(os.path.join(delivered, '.v3.json.tmp'), os.path.join(delivered, 'v3.json'))
    end = time.monotonic() + 20
    while not open(updates).read().endswith('\\n') and time.monotonic() < end: time.sleep(.02)
    entry, = map(json.loads, open(updates).read().splitlines())
    listed = open(os.path.join(actor, entry['file']), 'rb').read()
    assert listed == data and hashlib.sha256(listed).hexdigest() == entry['sha256'], entry
    assert sorted(entry) == ['commit', 'coverage', 'file', 'repository_id', 'schema', 'sha256', 'version'], entry
    assert (entry['schema'], entry['version'], entry['file']) == ('knowledge-update-entry/1', 'v3', 'knowledge/v3.json'), entry
assert prompt.startswith('Frozen mission') and 'Software actor/resource note' not in prompt
assert 'HTTP attempts' not in prompt and 'final actor' not in prompt
def emit(**value): print(json.dumps(dict(wall_time=datetime.now(timezone.utc).isoformat(),**value)), flush=True)
route = json.load(open(flags['--config']))
emit(type='host-start', telemetry_version=9, schema='player-host/9', spend_limit_usd=route['spend_limit_usd'])
if 'HANG' in prompt: time.sleep(120)  # a host still playing when the driver must stop it
recall_made = int('WITH_RECALL' in prompt and flags['--pending-control-id']=='none')
if recall_made:
    emit(type='request-start',request_id='recall-1',request_role='recall')
    emit(type='response-complete',request_id='recall-1',reported_cost_usd='0',counted_cost_usd='0',cost_counted_as='provider-reported')
unpriced = int('WITH_UNPRICED' in prompt)
if unpriced:
    emit(type='request-start',request_id='recall-1',request_role='recall')
    emit(type='response-complete',request_id='recall-1',reported_cost_usd=None,counted_cost_usd=None,cost_counted_as='unpriced')
    emit(type='request-start',request_id='request-1')
    emit(type='response-complete',request_id='request-1',reported_cost_usd=None,counted_cost_usd=None,cost_counted_as='unpriced')
request_id = f'request-{1+unpriced}'
emit(type='request-start', request_id=request_id)
spent = '0.0034500000000000004' if 'LONG_COST' in prompt else '0.004'
emit(type='response-complete', request_id=request_id, reported_cost_usd=spent, counted_cost_usd=spent, cost_counted_as='provider-reported')
ending = 'READ_CONTROL' in prompt or flags['--pending-control-id']!='none'
handoff = 'HANDOFF_RACE' in prompt and flags['--actor-id'] == 'a'*32
control = json.loads(sys.stdin.readline()) if ending else None
if control:
    assert control['schema'] == 'player-control/1' and control['type'] == 'orderly_stop'
    assert control['actor_id'] == flags['--actor-id'] and control['session'] == flags['--session']
if handoff:
    emit(type='handoff',actor_id=flags['--actor-id'],session=flags['--session'],handoff_id='d'*32,context_id='e'*32,context_sha256='f'*64,grants_authority=False)
    emit(type='settled',unpriced_recall_requests=0,ok=True,reason='handoff',requests=1+recall_made,player_requests=1,recall_requests=recall_made,spent_usd=spent,unpriced_requests=0)
else:
    reason = 'external_stop_complete' if ending else 'task_complete'
    control_id = control['id'] if control else None
    if 'WRONG_CONTROL' in prompt: control_id='f'*32
    if 'NO_FINISH' not in prompt:
        emit(type='player-finish',disposition=reason,control_id=control_id,report='report',source_ids=[])
    emit(type='settled',unpriced_recall_requests=unpriced,ok=True,reason=reason,control_id=control_id,requests=1+recall_made+2*unpriced,player_requests=1+unpriced,recall_requests=recall_made+unpriced,spent_usd=spent,unpriced_requests=unpriced)
open(flags['-o'], 'w').write('report\\n')
"""


def driver_case(tmp_path,prompt='Frozen mission',*,two_actors=False,low_frames=False):
    adapter=tmp_path/'adapter.py';adapter.write_text(FAKE_HOST)
    (tmp_path/'context.txt').write_text('Frozen context');(tmp_path/'prompt.txt').write_text(prompt)
    (tmp_path/'delivered-knowledge.json').write_text(json.dumps(empty()))
    actors=[dict(actor_id=c*32,token='t') for c in ('a','c')]
    application=SimpleNamespace(set_knowledge=Mock(),
        runtime=SimpleNamespace(add_actor=Mock(side_effect=actors),stop=Mock(),confirm_quiescent=Mock(),
            remaining=Mock(return_value=dict(inputs=10000,requests=10000,frames=5 if low_frames else 10000,frame_bytes=10**9)),
            process=SimpleNamespace(poll=lambda:None),channel=SimpleNamespace(stopped=threading.Event(),
                stop_origin=lambda:dict(requested_wall=None,reason='fixture fence')),session='b'*32),
        host=None)
    reserve=dict(seconds=10,inputs=10,requests=10,frames=5,frame_bytes=1000,usd='0.997' if 'READ_CONTROL' in prompt else '0.01')
    profile=dict(max_hosts=2 if two_actors else 1,host_seconds=100,total_host_seconds=200,effort='off',port=8766,
                 ending_reserve=reserve,session='b'*32,host=dict(argv=[sys.executable,str(adapter)]),spend_limit_usd='1')
    # Each fake host makes one request that reports $0.004.
    route=dict(recall=dict(model=dict(id='fixture'),every=5,unpriced_request_usd='0.2'),spend_limit_usd='1',unpriced_request_usd='0.25',api_key_env='FIXTURE_KEY',model=dict(id='fixture',name='fixture'))
    return profile,route,application


def test_driver_launches_selected_host_without_experimental_prompt_additions(tmp_path):
    profile,route,application=driver_case(tmp_path)
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    actor=result['actors'][0]
    assert result['outcome']=='player_task_complete_unassessed' and result['observed_attempts']==1, result
    assert actor['accounting_complete'] and actor['settled']['reason']=='task_complete'
    launched=json.loads((tmp_path/'actors/001/host-process.json').read_text())['argv']
    assert launched[:3]==[*profile['host']['argv'],'run']
    assert (tmp_path/'actors/001/player-final.txt').read_text()=='report\n'
    assert result['ending_request'] is None


@pytest.mark.parametrize('invalid_usage',[None,'None',"{'cost': {'total': 10**400}}"])
def test_driver_cleanup_retains_observations_after_invalid_consumed_trace(tmp_path,invalid_usage):
    profile,route,application=driver_case(tmp_path,two_actors=True)
    adapter=tmp_path/'adapter.py'
    script = FAKE_HOST+"\nemit(type='handoff')\n"
    if invalid_usage is not None:
        script=FAKE_HOST.replace(
            "emit(type='response-complete', request_id=request_id,",
            f"emit(type='response-complete', request_id=request_id, usage_available=True, usage={invalid_usage},")
    adapter.write_text(script)
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    actor=result['actors'][0]
    assert result['outcome']=='incomplete' and result['observed_attempts']==1,result
    assert not actor['accounting_complete'] and actor['observed_attempts']==1
    # The trace could not be read to its end: what it showed is recorded, the spend is incomplete and no successor starts.
    assert (actor['spent_usd'],actor['spend_complete'])==('0.004',False)
    assert (result['reported_usd'],result['spent_usd'],result['spend_complete'])==('0.004','0.004',False)
    assert application.runtime.add_actor.call_count==1 and not application.runtime.confirm_quiescent.called
    assert actor['cleanup']['process_absent'] and actor['cleanup']['group_absent']




@pytest.mark.parametrize('invalid_value',['1e309',r"'\ud800'"])
def test_invalid_terminal_diagnostic_keeps_incomplete_receipt_writable(tmp_path,invalid_value):
    profile,route,application=driver_case(tmp_path)
    (tmp_path/'adapter.py').write_text(FAKE_HOST.replace(
        "emit(type='settled',", f"emit(type='settled',event_output={{'max_callback_ms': {invalid_value}}},"))
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    actor=result['actors'][0]
    assert (actor['observed_attempts'],actor['spent_usd'],actor['spend_complete'])==(1,'0.004',False)
    assert result['outcome']=='incomplete'
    assert (tmp_path/'actors/001/driver-receipt.json').is_file()
    json.dumps(result,allow_nan=False)


def test_overflowing_configured_estimate_leaves_actual_spend_intact(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission HANDOFF_RACE',two_actors=True)
    (tmp_path/'adapter.py').write_text(FAKE_HOST.replace(
        "emit(type='response-complete', request_id=request_id,",
        "emit(type='response-complete', request_id=request_id, usage_available=True, usage={'cost': {'total': 1e308}},"))
    with patch('tools.campaign_player._handoff_context',return_value='{}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert [actor['configured_estimate_usd'] for actor in result['actors']]==[1e308,1e308]
    assert result['configured_estimate_usd'] is None
    assert (result['spent_usd'],result['spend_complete'])==('0.008',True)
    json.dumps(result,allow_nan=False)


def test_driver_total_keeps_unknown_attempts_separate_from_spend(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission WITH_UNPRICED')
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['observed_attempts']==3 and result['observed_recall_attempts']==1
    for receipt in (result,result['actors'][0]):
        assert receipt['spend_complete']
        assert receipt['unpriced_requests']==receipt['unpriced_recall_requests']==1
        assert receipt['spent_usd']==receipt['reported_usd']=='0.004'


@pytest.mark.parametrize('trigger',['seconds','usd','inputs','requests','frames','frame_bytes'])
def test_each_external_resource_can_trigger_ending(trigger):
    reserve=dict(seconds=10,inputs=20,requests=20,frames=20,frame_bytes=100,usd='0.05')
    seconds,dollars=100.,Decimal('0.0500001')
    mechanical=dict(inputs=100,requests=100,frames=100,frame_bytes=1000)
    assert ending_trigger(reserve,seconds,dollars,mechanical) is None
    if trigger=='seconds':seconds=10
    elif trigger=='usd':dollars=Decimal('0.05')
    else:mechanical[trigger]=reserve[trigger]
    assert ending_trigger(reserve,seconds,dollars,mechanical)==dict(seconds='host_seconds',usd='spend').get(trigger,trigger)


def test_the_dollar_reserve_requests_the_orderly_finish(tmp_path):
    """$0.01 declared, $0.007 kept for the ending: after one $0.004 response $0.006 is left, so the driver asks
    the player to finish with mechanical capacity still available."""
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL')
    profile['spend_limit_usd']='0.01';profile['ending_reserve'].update(usd='0.007')
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
    profile['spend_limit_usd']='0.004';profile['ending_reserve'].update(usd='0.001')
    with patch('tools.campaign_player._handoff_context',return_value='{"fallible":"unfinished work"}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['reason']=='The dollar limit leaves nothing for another actor',result
    assert application.runtime.add_actor.call_count==1 and len(result['actors'])==1
    assert not (tmp_path/'actors/002').exists()
    assert (result['spent_usd'],result['spend_complete'])==('0.004',True)


def test_recall_can_continue_with_remaining_budget_after_verified_handoff(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission HANDOFF_RACE WITH_RECALL',two_actors=True)
    with patch('tools.campaign_player._handoff_context',return_value='{}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_task_complete_unassessed',result
    assert [a['observed_recall_attempts'] for a in result['actors']]==[1,1]
    assert result['observed_attempts']==4 and result['observed_recall_attempts']==2
    assert application.runtime.confirm_quiescent.call_count==1
    for name,spend_limit in (('001','1'),('002','0.996')):
        actor=tmp_path/'actors'/name
        assert json.loads((actor/'route.json').read_text()) == dict(route,spend_limit_usd=spend_limit)
        frozen=json.loads((actor/'frozen.json').read_text())
        assert frozen['schema']=='player-host-inputs/4' and frozen['knowledge_updates'] is None
        assert 'delivered-knowledge.json' in frozen['files']
        assert not any('private' in key for key in frozen['files'])
        assert not (actor/'knowledge-updates.jsonl').exists() and '--knowledge-updates' not in json.loads((actor/'host-process.json').read_text())['argv']
    assert not application.set_knowledge.called


def published(number,*,repository='d'*40,**change):
    """A published version as the exporter writes it, with one fact per version number."""
    return dict(schema='delivered-knowledge/2',version=f'v{number}',commit=f'{number:040x}',repository_id=repository,
        coverage=dict(schema='curator-coverage/2',session='b'*32,actor='001',last_step=number),articles=[],
        facts=[dict(id=f'fact-{n}',type='observation',text=f'Claim {n}.',seen=dict(order=[n,'frame',0])) for n in range(1,number+1)],**change)


def test_a_version_left_during_play_is_listed_for_the_running_actor_and_seeds_its_successor(tmp_path):
    """R-REGRESSION: the driver's part of live delivery. The first actor's host leaves v3 as the runner would and
    finds it listed; the application serves it; the successor starts from it and has nothing listed."""
    import hashlib
    profile,route,application=driver_case(tmp_path,'Frozen mission HANDOFF_RACE LIVE_UPDATES',two_actors=True)
    data=(json.dumps(published(3),sort_keys=True,indent=2)+'\n').encode()
    (tmp_path/'published-v3.json').write_bytes(data)
    with patch('tools.campaign_player._handoff_context',return_value='{}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300,
                         tmp_path/'curator-runner'/'delivered')
    assert result['outcome']=='player_task_complete_unassessed',result
    first,second=tmp_path/'actors/001',tmp_path/'actors/002'
    # The first actor's frozen file is the package's; the listed version is beside it, bound by the entry.
    assert first.joinpath('delivered-knowledge.json').read_bytes()==(tmp_path/'delivered-knowledge.json').read_bytes()
    entry,=map(json.loads,first.joinpath('knowledge-updates.jsonl').read_text().splitlines())
    assert entry==dict(schema='knowledge-update-entry/1',version='v3',commit=published(3)['commit'],repository_id='d'*40,
        file='knowledge/v3.json',sha256=hashlib.sha256(data).hexdigest(),coverage=published(3)['coverage'])
    assert first.joinpath('knowledge/v3.json').read_bytes()==data
    served,=application.set_knowledge.call_args_list
    assert served.args[0].value==published(3)
    # The successor starts from the adopted version, hashed into its own frozen inputs.
    assert second.joinpath('delivered-knowledge.json').read_bytes()==data
    assert second.joinpath('knowledge-updates.jsonl').read_text()=='' and not second.joinpath('knowledge').exists()
    for actor in (first,second):
        frozen=json.loads((actor/'frozen.json').read_text())
        assert (frozen['schema'],frozen['knowledge_updates'])==('player-host-inputs/4','knowledge-updates.jsonl')
        assert frozen['files']['delivered-knowledge.json']==hashlib.sha256((actor/'delivered-knowledge.json').read_bytes()).hexdigest()
        assert 'knowledge-updates.jsonl' not in frozen['files']
        argv=json.loads((actor/'host-process.json').read_text())['argv']
        assert argv[argv.index('--knowledge-updates')+1]==str(actor/'knowledge-updates.jsonl')


def live_case(tmp_path,package=None):
    source=tmp_path/'delivered';source.mkdir()
    (tmp_path/'delivered-knowledge.json').write_text(json.dumps(package or empty()))
    actor=tmp_path/'actor';actor.mkdir()
    def leave(value,name=None):
        (source/(name or f"{value['version']}.json")).write_text(json.dumps(value))
    def listed():
        path=actor/'knowledge-updates.jsonl'
        return [json.loads(line)['version'] for line in path.read_text().splitlines()] if path.exists() else []
    return LiveKnowledge(source,tmp_path/'delivered-knowledge.json'),Mock(),actor,leave,listed


def test_the_highest_verified_version_above_the_current_one_is_adopted_and_a_refused_one_is_never_retried(tmp_path,capsys):
    live,application,actor,leave,listed=live_case(tmp_path,published(2))
    live.begin(actor)
    live.poll(application)  # nothing left yet
    for value in (published(1),published(2)):leave(value)  # not above the version held
    (tmp_path/'delivered'/'.v9.json.tmp').write_text('{')  # a file still being written is not a version
    (tmp_path/'delivered'/'notes.txt').write_text('ignored')
    live.poll(application)
    assert listed()==[] and not application.set_knowledge.called and capsys.readouterr().err==''
    leave(published(3))
    leave(published(4,repository='e'*40))  # another repository
    leave(published(5),'v6.json')  # names another version than its file
    leave(dict(published(7),schema='delivered-knowledge/1'))
    (tmp_path/'delivered'/'v8.json').write_text('{"schema":"delivered-knowledge/2","schema":"delivered-knowledge/2"}')
    live.poll(application)
    assert listed()==['v3'] and live.current.value['version']=='v3' and live.data==(tmp_path/'delivered'/'v3.json').read_bytes()
    assert application.set_knowledge.call_args.args[0].read('fact-3')['version']=='v3'
    refusals=capsys.readouterr().err.splitlines()
    assert [line.split(' refused: ')[0] for line in refusals]==[f'campaign_player: live knowledge v{n}' for n in (8,7,6,4)]
    assert 'another knowledge repository' in refusals[3] and 'another version' in refusals[2]
    live.poll(application)  # the refused versions stay refused, without another report
    assert listed()==['v3'] and application.set_knowledge.call_count==1 and capsys.readouterr().err==''
    leave(published(9))
    live.poll(application)
    assert listed()==['v3','v9'] and sorted(p.name for p in (actor/'knowledge').iterdir())==['v3.json','v9.json']
    assert sorted(p.name for p in actor.iterdir())==['knowledge','knowledge-updates.jsonl'],'no temporary list is left'


def test_the_first_version_after_an_empty_file_fixes_the_repository_and_between_actors_nothing_is_listed(tmp_path):
    live,application,actor,leave,listed=live_case(tmp_path)
    assert live.number==-1
    leave(published(0,repository='e'*40))
    live.poll(application)  # between actors: adopted for the next frozen file alone
    assert live.current.value['version']=='v0' and listed()==[] and not (actor/'knowledge').exists()
    assert application.set_knowledge.call_count==1
    leave(published(1))  # the default repository is not the adopted one
    leave(published(2,repository='e'*40))
    assert live.begin(actor)==live.data and json.loads(live.data)['version']=='v0'
    live.poll(application)
    assert listed()==['v2'] and live.current.value['repository_id']=='e'*40
    live.end()
    leave(published(3,repository='e'*40))
    live.poll(application)  # after the actor ended, nothing more is listed for it
    assert listed()==['v2'] and live.current.value['version']=='v3'


def test_without_a_source_the_driver_never_looks(tmp_path):
    (tmp_path/'delivered-knowledge.json').write_text(json.dumps(empty()))
    live,application=LiveKnowledge(None,tmp_path/'delivered-knowledge.json'),Mock()
    live.start(application);live.begin(tmp_path)
    live.poll(application)
    assert live.thread is None and not application.set_knowledge.called
    assert list(tmp_path.iterdir())==[tmp_path/'delivered-knowledge.json']


def test_a_list_publication_that_fails_to_reach_disk_leaves_the_list_the_application_and_the_successor_on_the_held_version(tmp_path,capsys):
    """R-REGRESSION (B2): the list is replaced whole only after its new bytes are durable, and the application and
    the next actor's frozen file move only after that. A failed fsync of the new list changes none of them."""
    import os
    live,application,actor,leave,listed=live_case(tmp_path,published(2))
    (actor/'knowledge-updates.jsonl').write_bytes(b'')
    live.begin(actor)
    leave(published(3))
    live.poll(application)
    before=(actor/'knowledge-updates.jsonl').read_bytes()
    assert listed()==['v3'] and application.set_knowledge.call_count==1
    leave(published(4))
    real,calls=os.fsync,[]
    def failing(fd):
        calls.append(fd)
        if len(calls)==2:raise OSError(5,'Input/output error')  # the copy reaches disk; the new list does not
        return real(fd)
    with patch('tools.campaign_player.os.fsync',side_effect=failing):
        live.poll(application)
    assert len(calls)==2
    assert (actor/'knowledge-updates.jsonl').read_bytes()==before and listed()==['v3']
    assert not (actor/'.knowledge-updates.jsonl.tmp').exists()
    assert application.set_knowledge.call_count==1 and application.set_knowledge.call_args.args[0].value['version']=='v3'
    assert live.current.value['version']=='v3' and live.data==(tmp_path/'delivered'/'v3.json').read_bytes()
    live.end()
    assert json.loads(live.begin(tmp_path/'successor'))['version']=='v3','the successor starts where the host and application are'
    assert 'live knowledge v4 refused: OSError' in capsys.readouterr().err


def test_a_version_prepared_for_an_actor_that_ended_is_decided_again_for_the_next(tmp_path):
    live,application,actor,leave,listed=live_case(tmp_path,published(2))
    live.begin(actor)
    leave(published(3))
    real=LiveKnowledge._adopt
    def ending_meanwhile(self,*args):
        self.end()  # the actor stops while its version is read
        return real(self,*args)
    with patch.object(LiveKnowledge,'_adopt',ending_meanwhile):
        live.poll(application)
    assert listed()==[] and not application.set_knowledge.called and live.current.value['version']=='v2'
    assert not (actor/'.knowledge-updates.jsonl.tmp').exists()
    live.poll(application)  # between actors: adopted for the next frozen file
    assert json.loads(live.begin(tmp_path/'next'))['version']=='v3' and application.set_knowledge.call_count==1


def stalled_source(tmp_path):
    """A version file that is a FIFO without a writer: reading it blocks, as a hung disk read would."""
    import os
    source=tmp_path/'curator-runner'/'delivered';source.mkdir(parents=True)
    os.mkfifo(source/'v3.json')
    def release():
        try:os.close(os.open(source/'v3.json',os.O_WRONLY|os.O_NONBLOCK))
        except OSError:pass
    return source,release


def bounded_run(*args):
    result={}
    thread=threading.Thread(target=lambda:result.update(value=run_hosts(*args)),daemon=True)
    began=time.monotonic();thread.start();thread.join(30)
    return result.get('value'),time.monotonic()-began


def test_a_stalled_read_of_the_delivery_directory_delays_neither_the_deadline_stop_nor_the_successor(tmp_path):
    """R-REGRESSION (B1): live delivery's reads happen on their own thread. With the only version file stalled,
    the operator stop still ends a hanging host at once, and a handoff starts the successor at once."""
    source,release=stalled_source(tmp_path/'stop')
    try:
        profile,route,application=driver_case(tmp_path/'stop','Frozen mission LIVE_UPDATES STALLED HANG')
        stopped=threading.Event();threading.Timer(1,stopped.set).start()
        result,seconds=bounded_run(tmp_path/'stop',profile,route,application,'fixture-secret',stopped,time.monotonic()+300,source)
        assert result is not None and seconds<15,'the stop was not held up by the stalled read'
        application.runtime.stop.assert_any_call('Original host deadline/operator cancellation')
        assert not application.set_knowledge.called
    finally:release()
    source,release=stalled_source(tmp_path/'handoff')
    try:
        profile,route,application=driver_case(tmp_path/'handoff','Frozen mission HANDOFF_RACE LIVE_UPDATES STALLED',two_actors=True)
        with patch('tools.campaign_player._handoff_context',return_value='{}'):
            result,seconds=bounded_run(tmp_path/'handoff',profile,route,application,'fixture-secret',threading.Event(),
                                       time.monotonic()+300,source)
        assert result is not None and seconds<15 and result['outcome']=='player_task_complete_unassessed',result
        second=tmp_path/'handoff'/'actors'/'002'
        assert second.joinpath('delivered-knowledge.json').read_bytes()==(tmp_path/'handoff'/'delivered-knowledge.json').read_bytes()
        assert second.joinpath('knowledge-updates.jsonl').read_text()=='' and not application.set_knowledge.called
    finally:release()


def test_the_applications_knowledge_tools_answer_from_the_version_the_driver_adopts(tmp_path):
    """R-REGRESSION (N2): the real application's read and query tools, before and after live adoption."""
    import uuid
    from harness.application import Application
    from harness.computer.runtime import ComputerRuntime
    from harness.player.journal import Journal
    from tests.test_computer_runtime import Channel,Process
    live,_,actor,leave,listed=live_case(tmp_path,published(2))
    (tmp_path/'computer').mkdir()
    runtime=ComputerRuntime(tmp_path/'computer','a'*32,Channel(),Process(),time.monotonic()+90,
        dict(max_inputs=10,max_requests=10,max_frames=10,max_bytes=2**20))
    journal=Journal(tmp_path/'player.sqlite3')
    try:
        application=Application(runtime,journal,tmp_path/'contexts',knowledge=tmp_path/'delivered-knowledge.json')
        token=runtime.add_actor()['token']
        def tool(name,**args):
            result,_=application.call(token,name,dict(intent='Check delivered knowledge',cites=[],**args),uuid.uuid4().hex)
            return result['version'],[r['id'] for r in result['records']]
        assert tool('player_knowledge_read',id_or_title='fact-3')==('v2',[])
        assert tool('player_knowledge_query',query='claim')==('v2',['fact-1','fact-2'])
        live.begin(actor);leave(published(3))
        live.poll(application)
        assert listed()==['v3']
        assert tool('player_knowledge_read',id_or_title='fact-3')==('v3',['fact-3'])
        assert tool('player_knowledge_query',query='claim')==('v3',['fact-1','fact-2','fact-3'])
    finally:
        runtime.close();journal.close()


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


def test_missing_response_record_cannot_pass_as_an_unpriced_settlement(tmp_path):
    rows=[START,dict(type='request-start',request_id='request-1'),
          dict(type='settled',requests=1,player_requests=1,recall_requests=0,spent_usd='0',unpriced_requests=1,unpriced_recall_requests=0)]
    result=finished(tmp_path,rows)
    assert result['spent_usd']=='0' and result['unpriced_requests']==1
    assert not result['accounting_complete'] and result['observed_attempts']==1


def test_controller_retains_control_intent_and_checks_direct_finish_identity(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL')
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_external_stop_complete_unassessed',result
    intent=json.loads((tmp_path/'orderly-stop.json').read_text())
    command=json.loads((tmp_path/'actors/001/control.json').read_text())
    assert intent['id']==command['id']==result['actors'][0]['settled']['control_id']
    assert intent['trigger']=='spend'
    assert set(command)=={'schema','id','session','actor_id','type'}


def test_frame_reserve_requests_ending_with_budget_left(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL',low_frames=True)
    profile['ending_reserve']['usd']='0.01'
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['ending_request']['trigger']=='frames' and result['observed_attempts']==1,result


@pytest.mark.parametrize('fault',['WRONG_CONTROL','NO_FINISH'])
def test_unbound_or_missing_direct_finish_never_accepts_stop(tmp_path,fault):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL '+fault)
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['actors'][0]['orchestration_error'],result
    application.runtime.stop.assert_called()
    assert result['observed_attempts']==1


def test_pending_stop_survives_verified_handoff_before_successor_action(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission READ_CONTROL HANDOFF_RACE',two_actors=True)
    with patch('tools.campaign_player._handoff_context',return_value='{"fallible":"unfinished work"}'):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='player_external_stop_complete_unassessed',result
    first=json.loads((tmp_path/'actors/001/control.json').read_text())
    second=json.loads((tmp_path/'actors/002/control.json').read_text())
    assert first['id']==second['id'] and first['actor_id']!=second['actor_id']
    assert result['observed_attempts']==2 and application.runtime.confirm_quiescent.call_count==1
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
    marks=dict(arm='LABEL-ARM-9f3',start='LABEL-START-9f3',scenario='LABEL-SCENARIO-9f3',world='LABEL-WORLD-9f3',lineage='LABEL-LINEAGE-9f3',admission=7777)
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


def test_successor_starts_in_ending_if_predecessor_crossed_reserve_between_polls(tmp_path):
    profile,route,application=driver_case(tmp_path,'Frozen mission HANDOFF_RACE',two_actors=True)
    profile['ending_reserve']['usd']='0.997'
    popen=subprocess.Popen

    def wait_for_fast_handoff(arguments,**kwargs):
        child=popen(arguments,**kwargs)
        if arguments[arguments.index('--actor-id')+1]=='a'*32:
            # Complete the first host before the driver can perform a live budget poll.
            child.wait(timeout=5)
        return child

    with (patch('tools.campaign_player.subprocess.Popen',side_effect=wait_for_fast_handoff),
          patch('tools.campaign_player._handoff_context',return_value='{}')):
        result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)

    assert result['outcome']=='player_external_stop_complete_unassessed',result
    intent=result['ending_request']
    assert (intent['trigger'],intent['spend_remaining_usd'])==('spend','0.996')
    assert not (tmp_path/'actors/001/control.json').exists()
    launched=json.loads((tmp_path/'actors/002/host-process.json').read_text())['argv']
    assert launched[launched.index('--pending-control-id')+1]==intent['id']
