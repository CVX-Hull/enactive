"""Original host-attempt accounting and known prelaunch failures."""
import json
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
    rows=[dict(type='host-start',telemetry_version=2,schema='player-host/4'),
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


@pytest.mark.parametrize('schema',['pi-player-host/4','player-host/3',None])
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
for event in (dict(type='host-start', telemetry_version=2, schema='player-host/4'),
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


# A scripted host for both roles over the real HTTP composition; no provider or game.
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
emit('host-start', telemetry_version=2, schema='player-host/4', role=route['role'])
emit('mcp-connected')
if route['role'] == 'actor':
    assert route['intent_tail_bytes'] == 1024
    for _ in range(ACTOR_STEPS):
        request()
        client.call('computer_input', dict(actions=[dict(type='key', key='x', modifiers=[])]))
        time.sleep(.4)
    if HANDOFF and Path(flags['-o']).parent.name == '001':
        request()
        issued = client.call('player_handoff', {})[0]['handoff']
        emit('handoff', actor_id=issued['actor_id'], session=issued['session'], handoff_id=issued['operation_id'],
             context_id=issued['context_id'], context_sha256=issued['context_sha256'], grants_authority=False)
        emit('settled', ok=True, reason='handoff', requests=requests)
        sys.exit(0)
elif LEVEL_MODE == 'sleep':
    emit('level-pass')
    request()
    time.sleep(120)
elif LEVEL_MODE == 'malformed':
    print('not a telemetry line', flush=True)
    time.sleep(120)
else:
    # The pass input is pushed, so no log read is needed: the bound is already what the prompt shows.
    emit('level-pass')
    request()
    request()
    current = [r for r in client.call('player_memory_query', dict(kind='work'))[0]['records']
               if r['data'].get('level') == 'subgoal']
    if LEVEL_MODE == 'abstain':
        value = client.call('player_level_abstain', dict(reason='Scripted abstain'))[0]
        emit('level-abstain', reason=value['reason'])
    else:
        proposal = dict(schema='player-level-proposal/2', action='replace', subgoal=dict(text='Scripted subgoal',
            expected_observations=[], status='open', confidence=.5, sources=[]),
            previous=dict(record_id=current[0]['id'], outcome='revised', reason='scripted', sources=[]) if current else None)
        value = client.call('player_level_commit', dict(proposal=proposal))[0]
        emit('level-commit' if value['status'] == 'committed' else 'level-discard', action=value['action'], reason=value['reason'],
             position=value['position'], inputs_since=value['inputs_since'], staleness_inputs=value['staleness_inputs'],
             record_ids=[r['id'] for r in value['records']], kept=value['kept'])
emit('settled', ok=True, reason='completed', requests=requests)
open(flags['-o'], 'w').write('report')
"""


@pytest.fixture
def level_campaign(tmp_path):
    """Run the real driver with scripted actor and level hosts over the real composition."""
    from harness.application import Application
    from harness.player.memory import Memory
    from harness.server import serve
    from test_computer_runtime import make_runtime
    from tools.campaign_player import ROOT
    (tmp_path/'session').mkdir()
    runtime,channel,_=make_runtime(tmp_path/'session',mint=False)
    memory=Memory(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts')
    server,thread=serve(app,0)
    for name,text in (('context.txt','Frozen guide'),('prompt.txt','Frozen mission'),('level-role.txt','Frozen role')):
        (tmp_path/name).write_text(text)

    def run(*,level_mode='commit',actor_steps=6,handoff=False,max_hosts=1,cap=20):
        adapter=tmp_path/'host.py'
        adapter.write_text(f'ROOT={str(ROOT)!r}\nLEVEL_MODE={level_mode!r}\nACTOR_STEPS={actor_steps}\n'
                           f'HANDOFF={handoff}\n'+SCRIPTED_HOST)
        level=dict(mode='live',inputs_per_pass=2,staleness_inputs=10,budget_fractions=[.5],intent_tail_bytes=1024,
                   max_http_attempts=6,pass_max_requests=2,pass_seconds=30)
        profile=dict(max_hosts=max_hosts,host_seconds=60,total_host_seconds=120,max_http_attempts=cap,effort='off',
                     port=server.server_port,session=runtime.session,host=dict(argv=[sys.executable,str(adapter)]),
                     actor_profile='narrowed',level=level)
        route=dict(schema='player-host/4',role='actor',intent_tail_bytes=1024,max_requests=10,api_key_env='FIXTURE_KEY',
                   model=dict(id='fixture',name='fixture'))
        return run_hosts(tmp_path,profile,route,app,'fixture-secret',threading.Event(),time.monotonic()+300)
    try:
        yield SimpleNamespace(run=run,app=app,channel=channel,root=tmp_path)
    finally:
        server.shutdown();server.server_close();thread.join(2);runtime.close();memory.close()


def charged_within_cap(result,cap):
    levels=sum(a['level']['attempts_charged'] for a in result['actors'])
    return result['attempts_charged']==sum(a['attempts_charged'] for a in result['actors'])+levels<=cap


def test_level_passes_wake_on_inputs_and_commit(level_campaign):
    result=level_campaign.run()
    actor=result['actors'][0];receipt=actor['level']
    assert result['outcome']=='host_completed_unassessed', result
    first=receipt['passes'][0]
    assert first['reason']=='inputs' and first['accounting_complete'] and receipt['commits']>=1
    assert receipt['quiescent'] and receipt['failure'] is None and charged_within_cap(result,20)
    assert receipt['attempts_charged']<=6 and actor['allocated_attempts']==10
    # Each pass ran the frozen role and mission, with mechanical wake facts only.
    prompt=(level_campaign.root/'actors/001/level/001/prompt.txt').read_text()
    assert prompt.startswith('Frozen role\n\nMission brief') and 'wake reason inputs' in prompt
    # The pushed projection (not a level read) set the bound: the commit's position is the last entry shown.
    shown=[json.loads(line) for line in prompt.splitlines() if line.startswith('{"position"')]
    assert shown and shown[0]['position']==1 and 'Current subgoal: none.' in prompt
    assert first['level_events'][0]['position']==shown[-1]['position'] and first['level_events'][0]['action']=='replace'
    if len(receipt['passes'])>1:
        later=(level_campaign.root/'actors/001/level/002/prompt.txt').read_text()
        assert '"text":"Scripted subgoal"' in later and 'Current subgoal:\n{"record_id"' in later
        assert json.loads([l for l in later.splitlines() if l.startswith('{"position"')][0])['position']==shown[-1]['position']+1
    assert json.loads((level_campaign.root/'actors/001/level/001/route.json').read_text())['role']=='level'
    assert json.loads((level_campaign.root/'actors/001/level/001/mcp.json').read_text())['enabled_tools'][-2:]==['player_level_commit','player_level_abstain']
    intent=level_campaign.app.intent(actor['actor_id'])
    assert intent['record']['text']=='Scripted subgoal' and intent['age']['same_actor'] is True
    assert len(level_campaign.app.memory.current('work'))==1 and not level_campaign.channel.stopped.is_set()


def test_an_abstaining_level_is_counted_and_writes_nothing(level_campaign):
    result=level_campaign.run(level_mode='abstain')
    receipt=result['actors'][0]['level']
    assert result['outcome']=='host_completed_unassessed', result
    assert receipt['abstains']>=1 and receipt['commits']==0 and receipt['discards']==0 and receipt['failure'] is None
    assert [e['type'] for e in receipt['passes'][0]['level_events']]==['level-abstain']
    assert receipt['passes'][0]['level_events'][0]['reason']=='Scripted abstain'
    assert level_campaign.app.memory.current('work')==[]


def test_a_pass_still_running_stops_with_its_actor_and_is_charged_in_full(level_campaign):
    result=level_campaign.run(level_mode='sleep',actor_steps=3)
    receipt=result['actors'][0]['level']
    assert result['outcome']=='host_completed_unassessed', result
    (stopped,)=receipt['passes']
    assert not stopped['accounting_complete'] and stopped['attempts_charged']==stopped['allocated_attempts']==2
    assert stopped['cleanup']['process_absent'] and stopped['cleanup']['group_absent'] and receipt['quiescent']
    assert receipt['commits']==0 and charged_within_cap(result,20)


def test_a_level_failure_disables_the_level_but_never_stops_its_actor(level_campaign):
    result=level_campaign.run(level_mode='malformed')
    receipt=result['actors'][0]['level']
    assert result['outcome']=='host_completed_unassessed', result
    assert 'JSONDecodeError' in receipt['failure'] and len(receipt['passes'])==1 and receipt['quiescent']
    assert receipt['passes'][0]['attempts_charged']==2 and not level_campaign.channel.stopped.is_set()


def test_a_start_pass_revalidates_open_records_before_inputs_wake(level_campaign):
    level_campaign.app.memory.append('c'*32,dict(schema='player-record/1',kind='work',text='Earlier session subgoal',
        data=dict(level='subgoal',actor_id='c'*32,session='z'*32,position=0,expected_observations=[],status='open',confidence=.5),sources=[],supports=[],supersedes=None,applicability=None,program_id=None))
    receipt=level_campaign.run()['actors'][0]['level']
    assert receipt['passes'][0]['reason']=='start' and receipt['commits']>=1
    assert 'Earlier session subgoal' in (level_campaign.root/'actors/001/level/001/prompt.txt').read_text()
    assert [r['text'] for r in level_campaign.app.memory.current('work')]==['Scripted subgoal']


def test_each_successor_actor_gets_its_own_level_after_its_predecessors_passes_close(level_campaign):
    result=level_campaign.run(handoff=True,max_hosts=2,cap=30)
    first,second=result['actors']
    assert result['outcome']=='host_completed_unassessed', result
    assert first['settled']['reason']=='handoff' and first['level']['quiescent']
    assert first['reader_id']!=second['reader_id'] and second['level']['passes']
    assert all(p['started_wall']>=first['level']['passes'][-1]['ended_wall'] for p in second['level']['passes'])
    assert second['allocated_attempts']==min(10,30-first['attempts_charged']-first['level']['attempts_charged']-6)
    assert charged_within_cap(result,30)


def test_pushed_projection_binds_the_bound_shows_the_latest_fifty_and_the_current_subgoal(tmp_path):
    from harness.application import Application
    from harness.player.memory import Memory
    from test_computer_runtime import key,make_runtime
    from tools.campaign_player import LevelPasses
    runtime,channel,_=make_runtime(tmp_path,mint=False,max_inputs=100,max_requests=100,max_frames=200)
    memory=Memory(tmp_path/'player.sqlite3')
    app=Application(runtime,memory,tmp_path/'contexts')
    try:
        actor=app.add_actor('narrowed')
        reader=app.add_reader(actor['actor_id'],staleness_inputs=100)
        passes=SimpleNamespace(application=app,actor_id=actor['actor_id'],reader_id=reader['actor_id'],shown_through=0)
        push=lambda:LevelPasses._push(passes)
        bound=lambda:app.readers[reader['actor_id']]['bound']
        step=lambda:app.call(actor['token'],'computer_input',dict(actions=[key()]),'%032x'%time.monotonic_ns())
        # An empty log from its start binds 0, so a start pass can revalidate.
        assert 'Current subgoal: none.' in push() and '(no new entries)' in push() and bound()==0
        for _ in range(60):step()
        text=push()
        lines=[json.loads(l) for l in text.splitlines() if l.startswith('{"position"')]
        assert [e['position'] for e in lines]==list(range(11,61)) and '(10 earlier entries since then are not shown' in text
        assert bound()==60 and passes.shown_through==60
        # Nothing new: the push shows so and leaves the bound as read.
        assert '(no new entries)' in push() and bound()==60
        committed=app.call(reader['token'],'player_level_commit',dict(proposal=dict(schema='player-level-proposal/2',action='replace',
            subgoal=dict(text='Pushed subgoal',expected_observations=['a door'],status='open',confidence=.5,sources=[]),previous=None)),
            'e'*32)[0]
        assert committed['status']=='committed' and committed['position']==60 and bound() is None
        step();step()
        text=push()
        assert [json.loads(l)['position'] for l in text.splitlines() if l.startswith('{"position"')]==[61,62]
        assert 'earlier entries' not in text and bound()==62
        shown=json.loads(text.split('Current subgoal:\n')[1])
        assert shown==dict(record_id=committed['records'][0]['id'],text='Pushed subgoal',expected_observations=['a door'],
                           status='open',confidence=.5,sources=[],position=60,inputs_since_commit=2)
    finally:
        runtime.close();memory.close()
