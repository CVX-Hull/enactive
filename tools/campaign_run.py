"""One frozen gameplay admission with a sole mechanical custodian and the selected player host."""
from __future__ import annotations

import argparse
from decimal import Decimal
import fcntl
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
from harness.player.journal import Journal
from harness.server import serve
from harness.trace.stores import CURATOR_READ_LOCK,READ_HOLD_BOUND_SECONDS,STORE_CLOSING_MARKER
from tools.campaign_package import preflight,usd_text
from tools.campaign_player import run_hosts,write_new


def accounting(profile: dict,route: dict,driver: dict | None,hosts_started: bool) -> dict:
    """Preserve the observed provider subtotal and the unknown cost counts separately."""
    bound=Decimal(route['unpriced_request_usd'])
    recall_bound=Decimal(route['recall']['unpriced_request_usd'])
    recall_unpriced=driver['unpriced_recall_requests'] if driver else 0
    reported=Decimal(driver['reported_usd']) if driver else Decimal(0)
    unpriced=driver['unpriced_requests'] if driver else 0
    return dict(spend_limit_usd=profile['spend_limit_usd'],reported_usd=usd_text(reported),unpriced_requests=unpriced,
        unpriced_request_usd=usd_text(bound),unpriced_recall_requests=recall_unpriced,unpriced_recall_request_usd=usd_text(recall_bound),
        spent_usd=usd_text(reported),
        observed_attempts=driver['observed_attempts'] if driver else 0,
        observed_recall_attempts=driver['observed_recall_attempts'] if driver else 0,
        spend_complete=driver['spend_complete'] if driver else not hosts_started)


def close_store(directory: Path,session: str,close,attempt) -> None:
    """Close-out only, after input is revoked: refuse new curator reads, wait within the bound for admitted ones, then close.

    Without a configured reader (no `curator-read.lock`) the store closes at once. A reader
    holds a shared lock from admission until its connection closes and is refused once the
    marker exists; the exclusive lock is held, when acquired, until the store is closed.
    """
    lock=directory/CURATOR_READ_LOCK
    if not attempt('curator_read_lock',lock.exists):
        attempt('store_close',close);return
    attempt('store_closing_marker',lambda:write_new(directory/STORE_CLOSING_MARKER,
        dict(schema='store-closing/1',session=session,closing_wall=time.time())))
    def wait():
        descriptor=os.open(lock,os.O_RDONLY);end=time.monotonic()+READ_HOLD_BOUND_SECONDS
        try:
            while True:
                try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB);return descriptor
                except BlockingIOError:
                    if time.monotonic()>=end:return descriptor
                    time.sleep(.01)
        except BaseException:
            os.close(descriptor);raise
    descriptor=attempt('curator_read_wait',wait)
    attempt('store_close',close)
    if descriptor is not None:attempt('curator_read_release',lambda:os.close(descriptor))


def run_campaign(directory: Path) -> dict:
    directory=directory.resolve(strict=True)
    profile,route,target=preflight(directory)
    secret=os.environ.get(route['api_key_env'])
    if not secret:raise ValueError('Selected provider credential is unavailable; supply only its explicit environment variable')
    started=time.monotonic();deadline=started+profile['wall_seconds']
    owner=OwnedTarget(directory,profile['session'],target,Path(profile['library']['path']),Path(profile['shared_lock']),deadline)
    runtime=memory=server=server_thread=None
    stopped=threading.Event();driver=None
    report=dict(schema='campaign-receipt/7',session=profile['session'],source_commit=profile['source_commit'],
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
        memory=Journal(player_path)
        if stopped.is_set():raise ValueError('Cancelled before native launch')
        channel=owner.start()
        if stopped.is_set():
            channel.stop('Cancelled during native launch')
            raise ValueError('Cancelled during native launch')
        runtime=ComputerRuntime(directory,profile['session'],channel,owner.process,deadline,profile['limits'],max_actors=profile['max_hosts'])
        owner.wait_target()
        if stopped.is_set():raise ValueError('Cancelled before actor admission')
        application=Application(runtime,memory,directory/'contexts',knowledge=directory/'delivered-knowledge.json')
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
        # Input is revoked above; only the store's closing may wait for an admitted curator read.
        if runtime is not None:close_store(directory,profile['session'],runtime.store.close,attempt)
        if memory is not None:attempt('player_store_close',memory.close)
        if driver is None:
            # Without a completed driver report, do not call an actor absent.
            # Before any actor directory exists, zero hosts were launched.
            report['deciding_hosts_quiescent']=not (directory/'actors').exists()
        report['ended_wall']=time.time();report['elapsed_seconds']=time.monotonic()-started
        report['accounting']=accounting(profile,route,driver,(directory/'actors').exists())
        attempt('receipt',lambda:write_new(directory/'receipt.json',report))
        for sig,handler in previous.items():attempt('signal_restore',lambda sig=sig,handler=handler:signal.signal(sig,handler))
    return report


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args(argv)
    result=run_campaign(args.run)
    print(json.dumps(result))
    # This exit code certifies bounded orchestration/owned cleanup, not game save,
    # native normal exit, a win or a qualified gameplay outcome.
    return 0 if (result['outcome'] in {'player_task_complete_unassessed','player_cannot_continue_unassessed',
                                    'player_external_stop_complete_unassessed'} and result['deciding_hosts_quiescent']
                 and result['native_absence_verified'] and result['input_authority_revoked']) else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as exc:raise SystemExit(f'Campaign refused: {type(exc).__name__}: {exc}')
