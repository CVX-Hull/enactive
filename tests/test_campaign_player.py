"""Original host-attempt accounting and known prelaunch failures."""
import json
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.campaign_player import HostEvents,run_hosts


def test_original_attempts_and_partial_trace_reservation(tmp_path):
    path=tmp_path/'host.jsonl'
    rows=[dict(type='host-start',telemetry_version=2),
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


def test_known_prelaunch_failure_has_zero_attempts_and_no_successor(tmp_path):
    application=SimpleNamespace(runtime=SimpleNamespace(add_actor=Mock(side_effect=OSError('fixture store refusal')),stop=Mock()))
    profile=dict(max_hosts=2,host_seconds=100,total_host_seconds=200,max_http_attempts=30)
    with patch('tools.campaign_player.subprocess.Popen') as launch:
        result=run_hosts(tmp_path,profile,dict(max_requests=20),application,'fixture-secret',threading.Event(),time.monotonic()+300)
    assert result['outcome']=='incomplete' and result['attempts_charged']==0
    assert result['actors'][0]['cleanup']==dict(process_absent=True,group_absent=True)
    assert 'OSError' in result['reason'] and not launch.called
    assert application.runtime.add_actor.call_count==1


FAKE_HOST = """
import json, os, sys
mode, *rest = sys.argv[1:]
flags = dict(zip(rest[::2], rest[1::2]))
assert mode == 'run' and sorted(flags) == ['--config', '--context', '--effort', '--mcp-config', '--model', '--timeout-seconds', '-o'], sys.argv
assert sorted(os.environ) >= ['FIXTURE_KEY', 'LANG', 'PATH'] and os.environ['FIXTURE_KEY'] == 'fixture-secret'
assert sys.stdin.read().startswith('Frozen mission')
for event in (dict(type='host-start', telemetry_version=2, schema='player-host/1'),
              dict(type='request-start', request_id='request-1'),
              dict(type='settled', ok=True, reason='completed', requests=1)):
    print(json.dumps(event), flush=True)
open(flags['-o'], 'w').write('report\\n')
"""


def test_driver_launches_the_selected_host_argv_in_run_mode(tmp_path):
    adapter=tmp_path/'adapter.py';adapter.write_text(FAKE_HOST)
    (tmp_path/'context.txt').write_text('Frozen context');(tmp_path/'prompt.txt').write_text('Frozen mission')
    application=SimpleNamespace(
        runtime=SimpleNamespace(add_actor=Mock(return_value=dict(actor_id='a'*32,token='t')),stop=Mock(),
            process=SimpleNamespace(poll=lambda:None),channel=SimpleNamespace(stopped=threading.Event()),session='s'*32),
        activity_view=SimpleNamespace(host_event=Mock()),host=None)
    profile=dict(max_hosts=1,host_seconds=100,total_host_seconds=200,max_http_attempts=30,effort='off',port=8766,
                 session='s'*32,host=dict(argv=[sys.executable,str(adapter)]))
    route=dict(max_requests=20,api_key_env='FIXTURE_KEY',model=dict(id='fixture',name='fixture'))
    result=run_hosts(tmp_path,profile,route,application,'fixture-secret',threading.Event(),time.monotonic()+300)
    actor=result['actors'][0]
    assert result['outcome']=='host_completed_unassessed' and result['attempts_charged']==1, result
    assert actor['accounting_complete'] and actor['settled']['reason']=='completed'
    launched=json.loads((tmp_path/'actors/001/host-process.json').read_text())['argv']
    assert launched[:3]==[sys.executable,str(adapter),'run']
    assert (tmp_path/'actors/001/player-final.txt').read_text()=='report\n'
