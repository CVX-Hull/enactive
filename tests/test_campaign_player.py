"""Original host-attempt accounting and known prelaunch failures."""
import json
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
