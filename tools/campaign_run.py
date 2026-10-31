"""One frozen gameplay admission with a sole mechanical custodian and the selected player host."""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
if __package__ in (None,''):sys.path.insert(0,str(ROOT))

from harness.application import Application
from harness.computer.launch import OwnedTarget
from harness.computer.runtime import ComputerRuntime
from harness.player.memory import Memory
from harness.server import serve
from tools.campaign_package import preflight
from tools.campaign_player import run_hosts,write_new
from tools.investigation_live import LiveInvestigationView


def run_campaign(directory: Path) -> dict:
    directory=directory.resolve(strict=True)
    profile,route,target=preflight(directory)
    secret=os.environ.get(route['api_key_env'])
    if not secret:raise ValueError('Selected provider credential is unavailable; supply only its explicit environment variable')
    started=time.monotonic();deadline=started+profile['wall_seconds']
    owner=OwnedTarget(directory,profile['session'],target,Path(profile['library']['path']),Path(profile['shared_lock']),deadline)
    runtime=memory=server=server_thread=investigation_view=None
    stopped=threading.Event();driver=None
    report=dict(schema='campaign-receipt/2',session=profile['session'],source_commit=profile['source_commit'],
                started_wall=time.time(),outcome='incomplete',normal_save_claimed_by_harness=False,
                deciding_hosts_quiescent=False,native_absence_verified=False,input_authority_revoked=False)
    def cancel(signum,frame):
        stopped.set()
        if owner.channel is not None:owner.channel.stop('Operator signal cancellation')
    previous={sig:signal.signal(sig,cancel) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        owner.reserve()
        # Unsupported selected player stores reject before a native child exists.
        player_path=Path(profile['player_store']);player_path.parent.mkdir(parents=True,exist_ok=True)
        memory=Memory(player_path)
        if stopped.is_set():raise ValueError('Cancelled before native launch')
        channel=owner.start()
        if stopped.is_set():
            channel.stop('Cancelled during native launch')
            raise ValueError('Cancelled during native launch')
        runtime=ComputerRuntime(directory,profile['session'],channel,owner.process,deadline,profile['limits'],max_actors=profile['max_hosts'])
        owner.wait_target()
        if stopped.is_set():raise ValueError('Cancelled before actor admission')
        application=Application(runtime,memory,directory/'contexts')
        investigation_view=LiveInvestigationView(directory,profile)
        application.investigation_view=investigation_view
        server,server_thread=serve(application,profile['port'])
        write_new(directory/'ready.json',dict(schema='computer-ready/1',session=profile['session'],pid=owner.process.pid,
            viewer_url=f"http://127.0.0.1:{profile['port']}/",ready_wall=time.time()))
        driver=run_hosts(directory,profile,route,application,secret,stopped,deadline)
        report['driver']=driver
        report['deciding_hosts_quiescent']=all(r['cleanup']['process_absent'] and r['cleanup']['group_absent'] for r in driver['actors'])
        report['outcome']=driver['outcome']
    except (Exception,KeyboardInterrupt) as exc:
        report['reason']=f'{type(exc).__name__}: {str(exc)[:600]}'
    finally:
        def attempt(name,function):
            try:return function()
            except BaseException as exc:
                report[name+'_error']=type(exc).__name__;return None
        if runtime is not None:attempt('pause',lambda:runtime.stop('Custodian closeout; no rearm'))
        cleanup=attempt('native_cleanup',owner.close)
        if cleanup is not None:
            report['cleanup']=cleanup
            report['native_absence_verified']=cleanup['native_absence_verified']
            report['normal_native_exit_zero']=cleanup['normal_native_exit_zero']
        report['input_authority_revoked']=bool(owner.channel and owner.channel.stopped.is_set()) or report['native_absence_verified']
        if server is not None:
            attempt('server_shutdown',server.shutdown);attempt('server_close',server.server_close)
            attempt('server_join',lambda:server_thread.join(2))
        if investigation_view is not None:attempt('investigation_close',investigation_view.close)
        if runtime is not None:attempt('store_close',runtime.store.close)
        if memory is not None:attempt('player_store_close',memory.close)
        if driver is None:
            # Without a completed driver report, do not call an actor absent.
            # Before any actor directory exists, zero hosts were launched.
            report['deciding_hosts_quiescent']=not (directory/'actors').exists()
        if report['outcome']=='host_completed_unassessed' and not report.get('normal_native_exit_zero'):
            report['outcome']='incomplete_normal_native_exit'
        report['ended_wall']=time.time();report['elapsed_seconds']=time.monotonic()-started
        attempts=driver['attempts_charged'] if driver else (profile['max_http_attempts'] if (directory/'actors').exists() else 0)
        budget=profile['accounting']
        allocated=Decimal(str(budget['prospective_reserved_usd']))-Decimal(str(budget['prior_reserved_usd']))
        per=allocated/profile['max_http_attempts']
        report['accounting']=dict(attempts_charged=attempts,cumulative_attempts=budget['prior_attempts']+attempts,
            consumed_conservative_reservation_usd=float(per*attempts),
            cumulative_conservative_reservation_usd=float(Decimal(str(budget['prior_reserved_usd']))+per*attempts),
            allocated_max_attempts=profile['max_http_attempts'],unused_allocation_retired=profile['max_http_attempts']-attempts,
            configured_estimate_usd=driver['configured_estimate_usd'] if driver else None,
            missing_usage_attempts=driver['missing_usage_attempts'] if driver else None,
            reservation_is_not_invoice=True)
        attempt('receipt',lambda:write_new(directory/'receipt.json',report))
        for sig,handler in previous.items():attempt('signal_restore',lambda sig=sig,handler=handler:signal.signal(sig,handler))
    return report


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args(argv)
    result=run_campaign(args.run)
    print(json.dumps(result))
    return 0 if (result['outcome']=='host_completed_unassessed' and result['deciding_hosts_quiescent']
                 and result['native_absence_verified'] and result.get('normal_native_exit_zero')) else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as exc:raise SystemExit(f'Campaign refused: {type(exc).__name__}: {exc}')
