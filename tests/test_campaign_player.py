"""Original host-attempt accounting and known prelaunch failures."""
import json
from pathlib import Path
import re
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from harness.computer.protocol import ControlError
from tools.campaign_player import HostEvents,run_hosts


def test_original_attempts_and_partial_trace_reservation(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[dict(type='host-start',telemetry_version=2,schema='player-host/6'),
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


@pytest.mark.parametrize('schema',['pi-player-host/6','player-host/5',None])
def test_trace_from_another_host_contract_is_refused(tmp_path,schema):
    path=tmp_path/'host.jsonl'
    path.write_text(json.dumps(dict(type='host-start',telemetry_version=2,schema=schema))+'\n')
    events=HostEvents(path,10)
    try:
        with pytest.raises(ControlError,match='Unsupported'):events.finish()
    finally:events.close()


def test_known_prelaunch_failure_has_zero_attempts_and_no_successor(tmp_path):
    application=SimpleNamespace(add_actor=Mock(side_effect=OSError('fixture store refusal')),runtime=SimpleNamespace(stop=Mock()))
    profile=dict(max_hosts=2,host_seconds=100,total_host_seconds=200,max_http_attempts=30,actor_profile='flat',level=None)
    with patch('tools.campaign_player.subprocess.Popen') as launch:
        result=run_hosts(tmp_path,profile,dict(max_requests=20),application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['attempts_charged']==0
    assert result['actors'][0]['cleanup']==dict(process_absent=True,group_absent=True)
    assert 'OSError' in result['reason'] and not launch.called
    assert application.add_actor.call_args_list==[(('flat',),{})]


FAKE_HOST = """
import json, os, sys
mode, *rest = sys.argv[1:]
flags = dict(zip(rest[::2], rest[1::2]))
assert mode == 'run' and sorted(flags) == ['--config', '--context', '--effort', '--mcp-config', '--model', '--timeout-seconds', '-o'], sys.argv
assert sorted(os.environ) >= ['FIXTURE_KEY', 'LANG', 'PATH'] and os.environ['FIXTURE_KEY'] == 'fixture-secret'
assert sys.stdin.read().startswith('Frozen mission')
for event in (dict(type='host-start', telemetry_version=2, schema='player-host/6'),
              dict(type='request-start', request_id='request-1'),
              dict(type='settled', ok=True, reason='completed', requests=1)):
    print(json.dumps(event), flush=True)
open(flags['-o'], 'w').write('report\\n')
"""


def test_driver_launches_the_selected_host_argv_in_run_mode(tmp_path):
    adapter=tmp_path/'adapter.py';adapter.write_text(FAKE_HOST)
    (tmp_path/'context.txt').write_text('Frozen context');(tmp_path/'prompt.txt').write_text('Frozen mission')
    application=SimpleNamespace(
        add_actor=Mock(return_value=dict(actor_id='a'*32,token='t')),
        runtime=SimpleNamespace(stop=Mock(),
            process=SimpleNamespace(poll=lambda:None),channel=SimpleNamespace(stopped=threading.Event()),session='s'*32),
        activity_view=SimpleNamespace(host_event=Mock()),host=None)
    profile=dict(max_hosts=1,host_seconds=100,total_host_seconds=200,max_http_attempts=30,effort='off',port=8766,
                 session='s'*32,host=dict(argv=[sys.executable,str(adapter)]),actor_profile='flat',level=None)
    route=dict(max_requests=20,api_key_env='FIXTURE_KEY',model=dict(id='fixture',name='fixture'))
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    actor=result['actors'][0]
    assert result['outcome']=='host_completed_unassessed' and result['attempts_charged']==1, result
    assert actor['accounting_complete'] and actor['settled']['reason']=='completed'
    launched=json.loads((tmp_path/'actors/001/host-process.json').read_text())['argv']
    assert launched[:3]==[sys.executable,str(adapter),'run']
    assert (tmp_path/'actors/001/player-final.txt').read_text()=='report\n'


# --- Level v4: the whole driver over the real composition, with scripted hosts and no provider or game ---

# A scripted host for all three roles over the real HTTP composition. A reader's pass input arrives as a
# `player-pass-input/1` document on stdin; the actor's is its frozen prompt text.
SCRIPTED_HOST = """
import json, sys, time
from pathlib import Path
sys.path.insert(0, ROOT)
from harness.player_client import PlayerClient
mode, *rest = sys.argv[1:]
flags = dict(zip(rest[::2], rest[1::2]))
route = json.load(open(flags['--config']))
client = PlayerClient(Path(json.load(open(flags['--mcp-config']))['args'][-1]))
requests = 0
def emit(kind, **fields):
    print(json.dumps(dict(type=kind, **fields)), flush=True)
def request():
    global requests
    requests += 1
    emit('request-start', request_id=f'request-{requests}')
emit('host-start', telemetry_version=2, schema='player-host/6', role=route['role'])
emit('mcp-connected')
if route['role'] == 'actor':
    assert route['intent_tail_bytes'] == 1024
    for _ in range(ACTOR_STEPS):
        request()
        client.call('computer_input', dict(actions=[dict(type='key', key='x', modifiers=[])]))
        time.sleep(.3)
    if HANDOFF and Path(flags['-o']).parent.name == '001':
        request()
        issued = client.call('player_handoff', {})[0]['handoff']
        emit('handoff', actor_id=issued['actor_id'], session=issued['session'], handoff_id=issued['operation_id'],
             context_id=issued['context_id'], context_sha256=issued['context_sha256'], grants_authority=False)
        emit('settled', ok=True, reason='handoff', requests=requests)
        sys.exit(0)
elif route['role'] == 'recorder':
    document = json.load(sys.stdin)
    assert document['schema'] == 'player-pass-input/1' and document['role'] == 'recorder' and document['brief'] is None
    emit('episode-pass')
    request()
    if RECORDER_MODE == 'sleep':
        time.sleep(120)
    if RECORDER_MODE == 'none':
        emit('settled', ok=False, reason='level-no-proposal', requests=requests)
        sys.exit(1)
    subgoal = document['pushed']['subgoal']
    if RECORDER_MODE == 'abstain':
        value = client.call('player_episode_abstain', dict(reason_code='no_player_action', reason='Scripted abstain', sources=[]))[0]
        emit('episode-abstain', reason_code='no_player_action', reason=value['reason'] if 'reason' in value else 'Scripted abstain',
             settled=value['settled'], first_position=value['first_position'], last_position=value['last_position'],
             subgoal_id=value['subgoal_id'])
    else:
        marks = ['not_yet'] * (len(subgoal['expected_observations']) if subgoal else 0)
        value = client.call('player_episode_record', dict(attempted='Scripted attempt', counterpart='', observation_status=marks,
            residual='', changed='', confidence=.5, sources=[]))[0]
        emit('episode-record', settled=value['settled'], first_position=value['first_position'],
             last_position=value['last_position'], subgoal_id=value['subgoal_id'], counted=value['counted'],
             closed=value['closed'], observations=value['observations'], stalled=value['stalled'],
             record_ids=[r['id'] for r in value['records']])
elif LEVEL_MODE == 'sleep':
    json.load(sys.stdin)
    emit('level-pass')
    request()
    time.sleep(120)
elif LEVEL_MODE == 'malformed':
    print('not a telemetry line', flush=True)
    time.sleep(120)
else:
    document = json.load(sys.stdin)
    assert document['schema'] == 'player-pass-input/1' and document['role'] == 'level' and document['brief'] == 'Frozen mission'
    emit('level-pass')
    request()
    request()
    current = document['pushed']['intent']['subgoal'] is not None
    if LEVEL_MODE == 'abstain':
        value = client.call('player_level_abstain', dict(reason_code='no_change_needed', reason='Scripted abstain', sources=[]))[0]
        emit('level-abstain', reason_code=value['reason_code'], reason=value['reason'])
    else:
        if LEVEL_MODE in ('lost', 'lost-absent'):
            # The response is lost; in 'lost' the service had already committed the call, in 'lost-absent' it never arrived.
            deliver = client._post
            def lost(path, value, **flags):
                if LEVEL_MODE == 'lost':
                    deliver(path, value, **flags)
                raise TimeoutError('response lost')
            client._post = lost
        value = client.call('player_level_replace', dict(text='Scripted subgoal', expected_observations=['A door is visible'],
            status='open', confidence=.5, sources=[], previous_outcome='revised' if current else 'none',
            previous_reason='scripted' if current else ''))[0]
        if value['schema'] == 'player-transport/1':
            assert value['collect_with'] is None and value['status'] == 'unknown'
            emit('level-uncertain', request_id=f'request-{requests}', tool_call_id='call-0', tool='player_level_replace',
                 identity=value['operation_id'])
            emit('settled', ok=False, reason='level-uncertain', requests=requests)
            sys.exit(1)
        emit('level-commit' if value['status'] == 'committed' else 'level-discard', action=value['action'], reason=value['reason'],
             position=value['position'], inputs_since=value['inputs_since'], staleness_inputs=value['staleness_inputs'],
             record_ids=[r['id'] for r in value['records']], kept=value['kept'], subgoal_id=value['subgoal_id'],
             derived=value['derived'])
emit('settled', ok=True, reason='completed', requests=requests)
open(flags['-o'], 'w').write('report')
"""

THETA = 0.1251514705882353


def grey_png(value):
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new('L', (8, 8), value).save(out, format='PNG')
    return out.getvalue()


def level_profile(**changes):
    recorder = dict(max_http_attempts=8, pass_max_requests=2, pass_seconds=30, backlog=3)
    level = dict(mode='live', episode_cap=10, staleness_inputs=10, budget_fractions=[.5], intent_tail_bytes=1024,
                 max_http_attempts=6, pass_max_requests=2, pass_seconds=30, theta=THETA, theta_fitting_sha256='a' * 64,
                 min_episode_inputs=2, stall_settles=3, confidence_floor=0.0,
                 recall=dict(tail_top=2, tail_exploration=1, level_items=10), recorder=recorder)
    recorder.update(changes.pop('recorder', {}))
    return dict(level, **changes)


@pytest.fixture
def level_campaign(tmp_path):
    """Run the real driver with scripted actor, level and recorder hosts over the real composition."""
    from harness.application import Application
    from harness.player.memory import Memory
    from harness.server import serve
    from test_computer_runtime import make_runtime
    from tools.campaign_player import ROOT
    (tmp_path/'session').mkdir()
    runtime,channel,_=make_runtime(tmp_path/'session',mint=False,max_inputs=100,max_requests=200,max_frames=200)
    memory=Memory(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts')
    server,thread=serve(app,0)
    for name,text in (('context.txt','Frozen guide'),('prompt.txt','Frozen mission'),('level-role.txt','Frozen level role'),
                      ('episode-role.txt','Frozen episode role')):
        (tmp_path/name).write_text(text)

    def pictures():
        # The capture changes every third request, so the cutter sees real content boundaries.
        channel.png = grey_png(0 if (len(channel.calls)//3) % 2 == 0 else 200)
        channel.capture = len(channel.calls) + 1
    channel.before_request = pictures

    def run(*,level_mode='commit',recorder_mode='record',actor_steps=9,handoff=False,max_hosts=1,cap=40,level=None):
        adapter=tmp_path/'host.py'
        adapter.write_text(f'ROOT={str(ROOT)!r}\nLEVEL_MODE={level_mode!r}\nRECORDER_MODE={recorder_mode!r}\n'
                           f'ACTOR_STEPS={actor_steps}\nHANDOFF={handoff}\n'+SCRIPTED_HOST)
        profile=dict(max_hosts=max_hosts,host_seconds=60,total_host_seconds=120,max_http_attempts=cap,effort='off',
                     port=server.server_port,session=runtime.session,host=dict(argv=[sys.executable,str(adapter)]),
                     actor_profile='narrowed',level=level or level_profile())
        route=dict(schema='player-host/6',role='actor',intent_tail_bytes=1024,max_requests=10,api_key_env='FIXTURE_KEY',
                   model=dict(id='fixture',name='fixture'))
        return run_hosts(tmp_path,profile,route,app,'fixture-secret',threading.Event(),time.monotonic()+300)
    try:
        yield SimpleNamespace(run=run,app=app,channel=channel,root=tmp_path,runtime=runtime)
    finally:
        server.shutdown();server.server_close();thread.join(2);runtime.close();memory.close()


def charged_within_cap(result,cap):
    levels=sum(a['level']['attempts_charged'] for a in result['actors'])
    return result['attempts_charged']==sum(a['attempts_charged'] for a in result['actors'])+levels<=cap


def claims(campaign,actor_index=0,result=None):
    """The settle claims of one actor in position order."""
    actor=result['actors'][actor_index]['actor_id']
    return sorted(campaign.app.settled_episodes(actor_id=actor),key=lambda v:v['first_position'])


def assert_every_operation_settled_exactly_once(campaign,result,actor_index=0):
    """The settles partition the actor's log: contiguous, no gap, no overlap, whatever each settled as."""
    views=claims(campaign,actor_index,result)
    assert views and views[0]['first_position']==1
    for before,after in zip(views,views[1:]):
        assert after['first_position']==before['last_position']+1
    total=campaign.runtime.store.actor_counts(result['actors'][actor_index]['actor_id'])[0]
    assert views[-1]['last_position']==total
    return views


def test_cut_episodes_are_recorded_and_the_level_runs_on_the_settles(level_campaign):
    result=level_campaign.run()
    actor=result['actors'][0];receipt=actor['level']
    assert result['outcome']=='host_completed_unassessed' and receipt['failure'] is None and receipt['quiescent'], result
    views=assert_every_operation_settled_exactly_once(level_campaign,result)
    assert all(v['settled']=='recorded' and v['writer']=='recorder' for v in views), (
        [(v['first_position'],v['last_position'],v['settled'],v.get('reason')) for v in views],receipt['failure'],
        [(p.get('settled'),p.get('trace_error'),p.get('cleanup')) for p in receipt['recorder']['passes']])
    assert receipt['episodes']['cut']==len(views)>=2 and receipt['episodes']['settled']['recorded']==len(views)
    assert receipt['episodes']['closed_by']['content']>=1 and receipt['episodes']['closed_by']['edge']==1
    assert receipt['recorder']['records']==len(views) and receipt['recorder']['failed_passes']==0
    # The session edge closed the last partial episode, and the recorder still recorded it after the actor ended.
    assert views[-1]['last_position']==level_campaign.runtime.store.actor_counts(actor['actor_id'])[0]
    assert charged_within_cap(result,40) and actor['allocated_attempts']==10
    # Recorder pass input: the role prompt, no brief, operations as key tokens, a baseline and a last frame, files on disk.
    passes=receipt['recorder']['passes']
    later=json.loads((level_campaign.root/'actors/001/recorder/002/input.json').read_text())
    assert later['schema']=='player-pass-input/1' and later['role_prompt']=='Frozen episode role' and later['brief'] is None
    pushed=later['pushed']
    assert pushed['schema']=='player-episode-push/1' and pushed['first_position']==passes[1]['first_position']
    assert pushed['operations'][0]['tokens']==['key:x'] and pushed['operations'][0]['position']==pushed['first_position']
    roles=[f['frame_role'] for f in pushed['frames']]
    assert roles[0]=='baseline' and roles[-1]=='last' and set(roles[1:-1])<={'in-episode'} and len(roles)<=7
    assert all(Path(f['path']).read_bytes()[:8]==b'\x89PNG\r\n\x1a\n' and f['source_id'] in pushed['sources'] for f in pushed['frames'])
    first=json.loads((level_campaign.root/'actors/001/recorder/001/input.json').read_text())['pushed']
    assert first['frames'][0]['frame_role']!='baseline' and first['first_position']==1
    # Level pass input: the frozen role, the actor's brief, the bound and the settled episodes since its last pass.
    one=json.loads((level_campaign.root/'actors/001/level/001/input.json').read_text())
    assert one['role_prompt']=='Frozen level role' and one['brief']=='Frozen mission' and one['wake']['reason']=='settle'
    assert one['pushed']['schema']=='player-level-push/1' and one['pushed']['intent']['subgoal'] is None
    shown=one['pushed']['episodes']
    assert shown and one['pushed']['bound']==dict(position=max(e['last_position'] for e in shown),subgoal_id=None)
    assert receipt['level']['commits']>=1 and [r['text'] for r in level_campaign.app.memory.current('work')]==['Scripted subgoal']
    assert json.loads((level_campaign.root/'actors/001/level/001/route.json').read_text())['role']=='level'
    assert json.loads((level_campaign.root/'actors/001/recorder/001/route.json').read_text())['role']=='recorder'
    assert json.loads((level_campaign.root/'actors/001/level/001/mcp.json').read_text())['enabled_tools']==[
        'player_source','player_level_keep','player_level_replace','player_level_close','player_level_abstain']
    assert json.loads((level_campaign.root/'actors/001/recorder/001/mcp.json').read_text())['enabled_tools']==[
        'player_source','player_episode_record','player_episode_abstain']
    assert not level_campaign.channel.stopped.is_set()
    # The level's later pushes carry the subgoal it committed, and the recorder's later episodes name it.
    assert any(v['subgoal_id'] is not None for v in views[1:])


def test_an_abstaining_recorder_still_settles_every_episode(level_campaign):
    result=level_campaign.run(recorder_mode='abstain',level_mode='abstain')
    receipt=result['actors'][0]['level']
    assert result['outcome']=='host_completed_unassessed', result
    views=assert_every_operation_settled_exactly_once(level_campaign,result)
    assert all(v['settled']=='abstained' and v['reason_code']=='no_player_action' for v in views)
    assert receipt['recorder']['abstains']==len(views) and receipt['recorder']['abstain_codes']['no_player_action']==len(views)
    assert receipt['level']['commits']==0 and receipt['level']['abstains']>=1
    assert level_campaign.app.memory.current('work')==[]


def test_a_recorder_pass_that_ends_without_a_call_settles_its_episode_as_failed(level_campaign):
    result=level_campaign.run(recorder_mode='none',level_mode='abstain')
    receipt=result['actors'][0]['level']
    assert result['outcome']=='host_completed_unassessed', result
    views=assert_every_operation_settled_exactly_once(level_campaign,result)
    assert {v['settled'] for v in views}=={'failed'} and all(v['writer']=='software' for v in views)
    assert all('level-no-proposal' in v['reason'] for v in views)
    assert receipt['recorder']['failed_passes']==len(views) and receipt['episodes']['settled']['failed']==len(views)


def test_a_recorder_pass_still_running_is_closed_at_its_time_and_charged_in_full(level_campaign):
    result=level_campaign.run(recorder_mode='sleep',level_mode='abstain',actor_steps=4,
                              level=level_profile(recorder=dict(pass_seconds=2)))
    receipt=result['actors'][0]['level']
    assert result['outcome']=='host_completed_unassessed', result
    first=receipt['recorder']['passes'][0]
    assert not first['accounting_complete'] and first['attempts_charged']==first['allocated_attempts']==2
    assert first['cleanup']['process_absent'] and first['cleanup']['group_absent'] and receipt['quiescent']
    views=assert_every_operation_settled_exactly_once(level_campaign,result)
    assert {v['settled'] for v in views}<={'failed','dropped'} and charged_within_cap(result,40)


def test_a_level_failure_disables_both_readers_but_never_stops_its_actor_and_no_episode_is_left_unsettled(level_campaign):
    result=level_campaign.run(level_mode='malformed')
    receipt=result['actors'][0]['level']
    assert result['outcome']=='host_completed_unassessed', result
    assert 'JSONDecodeError' in receipt['failure'] and receipt['quiescent'] and not level_campaign.channel.stopped.is_set()
    # Operations after the failure are never cut, but every episode that was cut settled, exactly once, in order.
    views=claims(level_campaign,0,result)
    assert views and views[0]['first_position']==1 and receipt['episodes']['waiting_unsettled']==0
    assert all(after['first_position']==before['last_position']+1 for before,after in zip(views,views[1:]))
    assert len(views)==receipt['episodes']['cut']


def test_each_successor_actor_gets_its_own_readers_after_the_last_episode_of_its_predecessor_is_recorded(level_campaign):
    result=level_campaign.run(handoff=True,max_hosts=2,cap=60,actor_steps=7)
    first,second=result['actors']
    assert result['outcome']=='host_completed_unassessed', result
    assert first['settled']['reason']=='handoff' and first['level']['quiescent']
    assert (first['reader_id'],first['recorder_id']) != (second['reader_id'],second['recorder_id'])
    views=assert_every_operation_settled_exactly_once(level_campaign,result,0)
    assert views[-1]['closed_by' if False else 'settled']=='recorded'
    # The predecessor's last episode (closed at the handoff edge) was recorded before the successor started.
    ended=max(p['ended_wall'] for p in first['level']['recorder']['passes'])
    assert views[-1]['last_position']==level_campaign.runtime.store.actor_counts(first['actor_id'])[0]
    assert all(p['started_wall']>=ended for p in second['level']['recorder']['passes']+second['level']['level']['passes'])
    # The successor's start pass revalidates what the first actor's level and recorder left.
    assert second['level']['level']['passes'][0]['reason']=='start' and second['level']['recorder']['records']>=1
    assert_every_operation_settled_exactly_once(level_campaign,result,1)
    assert charged_within_cap(result,60)


@pytest.mark.parametrize('mode,committed',[('lost',True),('lost-absent',False)])
def test_a_lost_terminal_call_ends_the_pass_and_the_driver_reconciles_its_identity(level_campaign,mode,committed):
    result=level_campaign.run(level_mode=mode)
    receipt=result['actors'][0]['level']['level']
    assert result['outcome']=='host_completed_unassessed', result
    first=receipt['passes'][0]
    assert first['settled']['reason']=='level-uncertain' and first['settled']['ok'] is False
    (event,)=first['level_uncertain']
    assert event['tool']=='player_level_replace' and re.fullmatch('[0-9a-f]{32}',event['identity'])
    row=level_campaign.app.memory._db.execute('SELECT result FROM service_operations WHERE id=?',(event['identity'],)).fetchone()
    # An absent call leaves only the tombstone the pass's close wrote: a row with no result.
    assert row is not None and (row[0] is not None)==committed and event['outcome']==('committed' if committed else 'absent')
    if committed:
        stored=[r[0] for r in level_campaign.app.memory._db.execute('SELECT id FROM records')]
        assert event['action']=='replace' and event['record_ids'] and set(event['record_ids'])<=set(stored)
    else:
        assert event['record_ids']==[] and level_campaign.app.memory.current('work')==[]
    # It is counted, charged, and kept apart from commits and the other refusals; no pass outcome was reported.
    assert receipt['uncertain_terminals']==sum(len(p['level_uncertain']) for p in receipt['passes'])>=1
    assert receipt['uncertain_committed']==(receipt['uncertain_terminals'] if committed else 0)
    assert receipt['uncertain_absent']==(0 if committed else receipt['uncertain_terminals'])
    assert receipt['commits']==0 and receipt['failed_passes']>=1 and receipt['final_refusals']==0
    assert result['level_uncertain_terminals']==receipt['uncertain_terminals'] and first['accounting_complete']


def test_the_driver_disposition_totals_and_version(level_campaign):
    result=level_campaign.run(level_mode='abstain')
    assert result['schema']=='player-driver/6'
    actor=result['actors'][0]['level']
    assert result['episodes_cut']==actor['episodes']['cut']>=2
    assert result['level_attempts_charged']==actor['attempts_charged']==actor['level']['attempts_charged']+actor['recorder']['attempts_charged']
    assert result['level_failed_passes']==actor['failed_passes']


# --- The driver's own rules, in process over the real application with host launches stubbed ---

class Child:
    def __init__(self):self.done=False
    def poll(self):return 0 if self.done else None


class Trace:
    """A pass's trace as the driver reads it: nothing to read, one settled request on finish."""
    def read(self):return False
    def finish(self):return dict(observed_attempts=1,attempts_charged=1,accounting_complete=True,settled=dict(ok=True,reason='completed'),
                                 handoff=None,level_events=[],episode_events=[],level_uncertain=[],configured_estimate_usd=0,
                                 usage_available_attempts=0,missing_usage_attempts=1)
    def close(self):pass


@pytest.fixture
def rig(tmp_path,monkeypatch):
    """A real application and the driver's real `LevelSystem`, with each pass's host launch replaced by a stub."""
    from harness.application import Application
    from harness.player.memory import Memory
    from test_computer_runtime import key,make_runtime
    from tools import campaign_player as player
    runtime,channel,_=make_runtime(tmp_path,mint=False,max_inputs=300,max_requests=400,max_frames=400)
    memory=Memory(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts')
    actor=app.add_actor('narrowed')
    directory=tmp_path/'driver';directory.mkdir()
    for name,text in (('context.txt','Frozen guide'),('prompt.txt','Frozen mission'),('level-role.txt','Level role'),('episode-role.txt','Episode role')):
        (directory/name).write_text(text)
    launches=[]
    def start(self,reservation,document,meta):
        child=Child()
        record=dict(index=reservation['index'],role=self.role,allocated_attempts=reservation['allowance'],
                    allocated_seconds=reservation['seconds'],started_wall=time.time(),**meta)
        self.current=(child,Trace(),record,time.monotonic()+100)
        launches.append(SimpleNamespace(role=self.role,document=document,meta=meta,child=child,lane=self,reservation=reservation))
    monkeypatch.setattr(player.ReaderLane,'start',start)
    monkeypatch.setattr(player,'close_group',lambda child:dict(process_absent=True,group_absent=True))
    def build(**changes):
        level=level_profile(**changes)
        (tmp_path/'actor').mkdir(exist_ok=True)
        profile=dict(port=1,session=runtime.session,host=dict(argv=['host']),effort='off')
        system=player.LevelSystem(tmp_path/'actor',directory,app,actor,level,dict(model=dict(id='fixture'),api_key_env='K'),
                                  profile,'secret',(20,20),50)
        return system
    state=SimpleNamespace(app=app,actor=actor,runtime=runtime,channel=channel,launches=launches,build=build,tmp=tmp_path,
                          events=SimpleNamespace(requests={1},handoff=None,settled=None))
    def act(grey,count=1):
        for _ in range(count):
            channel.png=grey_png(grey);channel.capture+=1
            app.call(actor['token'],'computer_input',dict(actions=[key()]),'%032x'%time.monotonic_ns())
    state.act=act
    state.poll=lambda system,**kw:system.poll(state.events,kw.get('stop',False),time.monotonic()+1000)
    state.token=lambda lane:json.loads(lane.reader_file.read_text())['token']
    def settle_pass(launch,*,record=True):
        """Complete the stubbed recorder pass the way its host would: one call to the custodian, then the process exits."""
        if record:
            expected=len(launch.document['pushed']['subgoal']['expected_observations']) if launch.document['pushed']['subgoal'] else 0
            app.call(state.token(launch.lane),'player_episode_record',dict(attempted='Scripted attempt',counterpart='',
                observation_status=['not_yet']*expected,residual='',changed='',confidence=.5,sources=[]),'%032x'%time.monotonic_ns())
        launch.child.done=True
    state.settle_pass=settle_pass
    try:
        yield state
    finally:
        runtime.close();memory.close()


def spans(app,actor):
    return [(v['first_position'],v['last_position'],v['settled']) for v in
            sorted(app.settled_episodes(actor_id=actor['actor_id']),key=lambda v:v['first_position'])]


def force_cut(system,rig,count,*,per=2):
    """Close `count` episodes of `per` inputs each through the cap, with the recorder not yet running."""
    system.cutter.cap=per
    for _ in range(count):
        rig.act(100,per)
    system._ingest(final=False)


def test_backlog_bound_three_waiting_then_the_oldest_waiting_settles_as_dropped(rig):
    system=rig.build()
    force_cut(system,rig,1)
    rig.poll(system)
    (first,)=rig.launches
    assert first.role=='recorder' and (first.meta['first_position'],first.meta['last_position'])==(1,2) and system.inflight is not None
    # Episodes 2..5 close while the recorder is busy: four waiting is one more than the bound of three.
    force_cut(system,rig,4)
    assert [(e.first_position,e.last_position) for e in system.queue]==[(5,6),(7,8),(9,10)]
    assert spans(rig.app,rig.actor)==[(3,4,'dropped')]
    claim=rig.app.settled_episodes(actor_id=rig.actor['actor_id'])[0]
    assert claim['writer']=='software' and 'backlog' in claim['reason'] and claim['subgoal_id'] is None
    assert system.max_waiting==3 and system.receipt()['episodes']['cut']==5
    # The recorder finishes episode 1; the FIFO order then proceeds with the oldest still waiting.
    rig.settle_pass(first);rig.poll(system)
    recorders=[l for l in rig.launches if l.role=='recorder']
    assert len(recorders)==2 and recorders[1].meta['first_position']==5
    assert (1,2,'recorded') in spans(rig.app,rig.actor)
    system.finish()
    # Whatever was still waiting or in flight settled as failed: one claim per cut, none twice.
    assert [(a,b) for a,b,_ in spans(rig.app,rig.actor)]==[(1,2),(3,4),(5,6),(7,8),(9,10)]
    assert [s for *_,s in spans(rig.app,rig.actor)]==['recorded','dropped','failed','failed','failed']


def test_the_next_episode_starts_after_the_furthest_cut_never_after_the_newest_settle(rig):
    system=rig.build()
    force_cut(system,rig,1)
    rig.poll(system)
    (first,)=rig.launches
    force_cut(system,rig,4)
    # The drop of episode 2 (3..4) settled before episode 1 (1..2, in flight) and the newest settle ends at 4,
    # but the cutter has cut through position 10, so the next episode starts at 11.
    assert max(v['last_position'] for v in rig.app.settled_episodes(actor_id=rig.actor['actor_id']))==4
    assert system.cutter.next_position==11 and system.cutter.open_first is None
    rig.act(100,1)
    system._ingest(final=False)
    assert system.cutter.open_first==11
    # Settling the in-flight episode out of position order leaves every range disjoint.
    rig.settle_pass(first);rig.poll(system)
    ranges=sorted((a,b) for a,b,_ in spans(rig.app,rig.actor))
    assert all(after[0]>before[1] for before,after in zip(ranges,ranges[1:]))
    system.finish()


def test_the_cutter_waits_for_an_input_whose_result_is_in_flight_but_not_for_a_lost_one(rig):
    system=rig.build()
    rig.act(0,2)
    store=rig.runtime.store
    # An input whose result has not arrived is the last entry: it is not fed yet.
    pending_id='%032x'%time.monotonic_ns()
    store.begin(dict(operation_id=pending_id,actor_id=rig.actor['actor_id'],kind='input',created_wall=time.time(),deadline_monotonic=1e9),
                [dict(type='key',key='x',modifiers=[])],1)
    system._ingest(final=False)
    assert system.cutter.next_position==3
    # Once the actor has moved on, the unresolved input is lost: it is fed with no distance.
    rig.act(0,1)
    system._ingest(final=False)
    assert system.cutter.next_position==5
    system.finish()


def test_session_edge_closes_the_partial_episode_once_and_the_recorder_gets_it(rig):
    system=rig.build()
    rig.act(0,3)
    system._ingest(final=False)
    assert system.cuts==[] and system.cutter.open_inputs==3
    rig.events.settled=dict(ok=True,reason='handoff')
    # The actor's host has ended: drain flushes the open episode and the recorder works on it.
    done=threading.Event()
    def finish_pass():
        while not rig.launches:time.sleep(.01)
        rig.settle_pass(rig.launches[0]);done.set()
    thread=threading.Thread(target=finish_pass);thread.start()
    system.drain(lambda:False,time.monotonic()+1000)
    thread.join(5)
    assert done.is_set() and [(e.first_position,e.last_position,e.closed_by) for e in system.cuts]==[(1,3,'edge')]
    assert spans(rig.app,rig.actor)==[(1,3,'recorded')] and system.receipt()['episodes']['closed_by']['edge']==1
    assert system.quiescent()


def test_drain_does_not_start_the_recorder_on_a_fenced_run_and_settles_the_edge_episode_as_failed(rig):
    system=rig.build()
    rig.act(0,2)
    system.drain(lambda:True,time.monotonic()+1000)
    assert rig.launches==[] and spans(rig.app,rig.actor)==[(1,2,'failed')]
    claim=rig.app.settled_episodes(actor_id=rig.actor['actor_id'])[0]
    assert 'session ended' in claim['reason'] and claim['subgoal_id'] is None


def settle_all_as_dropped(system,rig,first,last):
    rig.app.settle_episode(system.recorder_id,first_position=first,last_position=last,subgoal_id=None,settled='dropped',reason='fixture')


def test_level_wakes_once_per_batch_of_settles_and_coalesces_during_a_pass(rig):
    system=rig.build()
    rig.act(100,6)
    settle_all_as_dropped(system,rig,1,2)
    rig.poll(system)
    # The recorder lane also ran (the cutter has open work), so only the level's launches are counted.
    levels=[l for l in rig.launches if l.role=='level']
    assert len(levels)==1 and levels[0].document['wake']['reason']=='settle'
    assert [e['first_position'] for e in levels[0].document['pushed']['episodes']]==[1]
    # Two more settle while that level pass is in flight: no second pass, however many polls.
    settle_all_as_dropped(system,rig,3,4);settle_all_as_dropped(system,rig,5,6)
    for _ in range(3):rig.poll(system)
    assert len([l for l in rig.launches if l.role=='level'])==1
    levels[0].child.done=True
    rig.poll(system);rig.poll(system)
    levels=[l for l in rig.launches if l.role=='level']
    assert len(levels)==2 and levels[1].document['wake']['reason']=='settle'
    # One pass over the newest records: both settles since the last push, in commit order.
    assert [e['first_position'] for e in levels[1].document['pushed']['episodes']]==[3,5]
    system.finish()


def test_the_budget_fraction_wakes_only_after_a_settle(rig):
    system=rig.build(budget_fractions=[.5])
    rig.events.requests={n for n in range(1,40)}
    rig.act(100,2)
    system._ingest(final=False)
    # 39 attempts of 50 crosses the half-way fraction, but nothing has settled: no level pass.
    rig.poll(system)
    assert [l for l in rig.launches if l.role=='level']==[]
    settle_all_as_dropped(system,rig,1,2)
    rig.poll(system)
    (level,)=[l for l in rig.launches if l.role=='level']
    assert level.document['wake']['reason']=='budget-0.5'
    system.finish()


def test_binding_after_a_settle_with_no_record_is_the_end_of_the_settled_episode(rig):
    system=rig.build()
    rig.act(100,5)
    # An episode settles as failed (no record at all), and a pass woken by it binds exactly where it ended.
    system.cutter.cap=3
    system._ingest(final=False)
    (cut,)=system.cuts
    system._settle(system.queue.popleft(),'failed','The recorder pass ended without settling the episode (fixture)')
    rig.poll(system)
    (level,)=[l for l in rig.launches if l.role=='level']
    assert level.document['pushed']['bound']==dict(position=cut.last_position,subgoal_id=None)
    assert rig.app.readers[system.level_lane.reader_id]['bound']==cut.last_position
    assert [e['settled'] for e in level.document['pushed']['episodes']]==['failed']
    assert level.meta['bound']['position']==3
    system.finish()


def test_the_level_start_wake_needs_something_carried_and_may_run_on_an_empty_delta(rig):
    system=rig.build()
    rig.poll(system)
    assert rig.launches==[]
    system.finish()


def test_a_start_wake_revalidates_an_earlier_sessions_open_subgoal_on_an_empty_delta(rig):
    from episode_support import put
    put(rig.app.memory,'c'*32,dict(schema='player-record/1',kind='work',text='Earlier subgoal',data=dict(level='subgoal',
        level_contract='player-level/4',actor_id='c'*32,session='z'*32,position=0,expected_observations=['a door'],status='open',
        confidence=.5),sources=[],supports=[],supersedes=None,applicability=None,program_id=None))
    again=rig.build()
    rig.poll(again)
    (level,)=[l for l in rig.launches if l.role=='level']
    assert [l for l in rig.launches if l.role=='recorder']==[]
    assert level.document['wake']['reason']=='start' and level.document['pushed']['episodes']==[]
    assert level.document['pushed']['bound']['position']==0 and level.document['pushed']['intent']['subgoal']['text']=='Earlier subgoal'
    again.finish()


def test_a_recorder_allowance_that_is_exhausted_settles_the_waiting_episodes_as_failed(rig):
    system=rig.build()
    system.recorder_lane.charged=system.recorder_lane.allowance
    force_cut(system,rig,2)
    rig.poll(system)
    assert [l for l in rig.launches if l.role=='recorder']==[] and [s for *_,s in spans(rig.app,rig.actor)]==['failed','failed']
    assert 'allowance' in rig.app.settled_episodes(actor_id=rig.actor['actor_id'])[0]['reason']


def test_a_failure_to_remember_stops_both_readers_and_settles_what_waits_but_the_actor_continues(rig):
    system=rig.build()
    force_cut(system,rig,2)
    rig.app.remember_failure='fixture: store full'
    rig.poll(system)
    assert 'could not remember' in system.failure and rig.launches==[]
    assert [s for *_,s in spans(rig.app,rig.actor)]==['failed','failed']
    # No level state gates input: the actor can still act.
    rig.act(100,1)
    assert not rig.channel.stopped.is_set()
    # Once failed, later polls do nothing and nothing is launched.
    rig.poll(system)
    assert rig.launches==[]


def test_an_unreadable_capture_fails_the_readers_not_the_actor(rig,monkeypatch):
    system=rig.build()
    rig.act(100,2)
    monkeypatch.setattr(rig.runtime.store,'read_source',lambda identity:(_ for _ in ()).throw(OSError('unreadable')))
    rig.poll(system)
    assert 'OSError' in system.failure and rig.launches==[] and not rig.channel.stopped.is_set()


def test_the_recorder_input_has_a_baseline_and_at_most_six_own_frames_the_last_and_the_largest_distances(rig):
    system=rig.build()
    # Episode 1 is position 1, closed by a cap of one; episode 2 is a cap-closed run of ten inputs whose pictures change
    # by small steps (all under theta, so only the cap closes it) with two larger ones.
    system.cutter.cap=1
    rig.act(0,1)
    system._ingest(final=False)
    system.cutter.cap=10
    for grey in (2,4,6,8,36,38,40,42,70,72):
        rig.act(grey,1)
    system._ingest(final=False)
    episodes=list(system.cuts)
    assert len(episodes)==2 and episodes[1].inputs==10 and episodes[1].closed_by=='cap'
    rig.poll(system)
    (first,)=rig.launches
    assert first.meta['first_position']==1
    first.child.done=True;rig.poll(system)
    first=rig.launches[1]
    pushed=first.document['pushed']
    assert [f['frame_role'] for f in pushed['frames']]==['baseline']+['in-episode']*5+['last'] and len(pushed['frames'])==7
    sources=[f['source_id'] for f in pushed['frames']]
    assert len(set(sources))==7 and pushed['frames'][0]['source_id']==episodes[0].frames[0][1]
    assert pushed['frames'][-1]['source_id']==episodes[1].frames[-1][1]
    # In capture order, and the two big jumps (0 -> 200 at 5 and 200 -> 5 ... ) are among those chosen.
    positions=[next(p for p,s in episodes[1].frames if s==src) for src in sources[1:]]
    assert positions==sorted(positions)
    big=sorted(range(len(episodes[1].frames)-1),key=lambda i:(-(episodes[1].distances[episodes[1].frames[i][0]] or -1),i))[:5]
    assert set(positions[:-1])=={episodes[1].frames[i][0] for i in big}
    system.finish()


def test_a_pass_binds_the_subgoal_current_when_its_episode_opened(rig):
    system=rig.build()
    rig.act(100,1)
    system._ingest(final=False)
    # A level commit lands while the episode is open: the episode keeps the subgoal it opened under.
    from episode_support import put
    work=put(rig.app.memory,system.level_lane.reader_id,dict(schema='player-record/1',kind='work',text='New',data=dict(level='subgoal',
        level_contract='player-level/4',actor_id=rig.actor['actor_id'],session=rig.runtime.session,position=1,
        expected_observations=['a door'],status='open',confidence=.5),sources=[],supports=[],supersedes=None,applicability=None,program_id=None))
    system.cutter.cap=3
    rig.act(100,2)
    system._ingest(final=False)
    (cut,)=system.cuts
    assert cut.subgoal_id is None and (cut.first_position,cut.last_position)==(1,3)
    rig.act(100,1)
    system._ingest(final=False)
    assert system.cutter.open_first==4
    system.cutter.cap=1
    rig.act(100,1)
    system._ingest(final=False)
    assert system.cuts[-1].subgoal_id==work['id']
    system.finish()


def test_the_receipt_counts_failed_passes_and_start_abstains(rig):
    system=rig.build()
    event=lambda kind,action=None,code=None:dict(type=kind,action=action,reason_code=code,reason='r')
    lane=system.level_lane
    lane.charged=10
    lane.passes[:]=[dict(reason='start',settled=dict(ok=True),level_events=[event('level-abstain',code='other')],attempts_charged=2),
            dict(reason='settle',settled=dict(ok=True),level_events=[event('level-abstain',code='no_change_needed')],attempts_charged=2),
            dict(reason='settle',settled=dict(ok=False,reason='level-no-proposal'),level_events=[],attempts_charged=2),
            dict(reason='settle',level_events=[],attempts_charged=2),
            dict(reason='settle',settled=dict(ok=False,reason='level-final-refusal'),level_events=[],attempts_charged=3),
            dict(reason='settle',settled=dict(ok=True),level_events=[event('level-commit','replace')],attempts_charged=2),
            dict(reason='settle',settled=dict(ok=True),level_events=[event('level-commit','keep'),],attempts_charged=2),
            dict(reason='settle',settled=dict(ok=True),level_events=[event('level-commit','close')],attempts_charged=2),
            dict(reason='settle',settled=dict(ok=True),level_events=[event('level-discard','keep')],attempts_charged=2)]
    receipt=system.level_receipt()
    assert (receipt['commits'],receipt['abstains'],receipt['start_abstains'],receipt['failed_passes'])==(3,2,1,3)
    assert (receipt['keeps'],receipt['replaces'],receipt['closes'],receipt['discards'],receipt['final_refusals'])==(1,1,1,1,1)
    assert receipt['abstain_codes']==dict(insufficient_evidence=0,transient_screen_state=0,no_change_needed=1,other=1)
    recorder=system.recorder_lane
    recorder.passes[:]=[dict(settled=dict(ok=True),episode_events=[dict(type='episode-record')],attempts_charged=1),
                        dict(settled=dict(ok=True),episode_events=[dict(type='episode-abstain',reason_code='unreadable_frames')],attempts_charged=1),
                        dict(settled=dict(ok=False,reason='level-final-refusal'),episode_events=[],attempts_charged=1)]
    receipt=system.recorder_receipt()
    assert (receipt['records'],receipt['abstains'],receipt['failed_passes'],receipt['final_refusals'])==(1,1,1,1)
    assert receipt['abstain_codes']==dict(unreadable_frames=1,no_player_action=0,other=0)
    system.finish()


def test_the_trace_reader_collects_level_uncertain_and_episode_events(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[dict(type='host-start',telemetry_version=2,schema='player-host/6'),
          dict(type='request-start',request_id='request-1'),
          dict(type='level-uncertain',request_id='request-1',tool_call_id='c',tool='player_level_close',identity='f'*32),
          dict(type='episode-record',settled='recorded',first_position=1,last_position=3,subgoal_id=None,counted=False,closed=False,
               observations=[],stalled=None,record_ids=['r']),
          dict(type='episode-abstain',settled='abstained',reason_code='other',reason='x',first_position=4,last_position=5),
          dict(type='settled',requests=1,ok=False,reason='level-uncertain')]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    events=HostEvents(path,10)
    try:
        finished=events.finish()
        assert finished['level_uncertain']==[dict(tool='player_level_close',identity='f'*32,request_id='request-1')]
        assert [e['type'] for e in finished['episode_events']]==['episode-record','episode-abstain']
        assert finished['episode_events'][0]['record_ids']==['r'] and finished['episode_events'][1]['reason_code']=='other'
    finally:events.close()


def test_a_late_recorder_call_after_its_pass_ended_is_refused_and_writes_nothing(rig):
    from harness.player.contracts import PlayerError
    system=rig.build()
    force_cut(system,rig,1)
    rig.poll(system)
    (launch,)=rig.launches
    # The pass ends without a call (the host died); the driver settles the episode as failed under the lock.
    launch.child.done=True
    rig.poll(system)
    assert spans(rig.app,rig.actor)==[(1,2,'failed')]
    before=rig.app.memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
    with pytest.raises(PlayerError,match='No episode is bound'):
        rig.app.call(rig.token(launch.lane),
                     'player_episode_record',dict(attempted='late',counterpart='',observation_status=[],residual='',changed='',
                                                  confidence=.5,sources=[]),'%032x'%time.monotonic_ns())
    assert rig.app.memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0]==before
    system.finish()
