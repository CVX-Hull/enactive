"""Mac finite-test spectator supervision around the existing campaign custodian.

This engineering entry point grants no player authority and certifies no game
outcome. The guardian never performs HTTP work; only the custodian child receives
the selected credential environment variable.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import ExitStack
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import socket
import subprocess
import sys
import time
import traceback

from harness.computer.launch import close_group
from harness.computer.protocol import read_json
from tools.campaign_package import digest, preflight
from tools.campaign_player import write_new

ROOT = Path(__file__).resolve().parents[1]
WINDOW = 45
PAUSE_REPLY = .75
MARKERS = ('watch-start.json', 'watch-attempts.jsonl', 'watch-terminal.json')


def finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def cutoff_reason(now: float, last: float | None, custody_end: float) -> str | None:
    if last is not None and last + WINDOW <= custody_end and now >= last + WINDOW:
        return 'watch_deadline'
    if now >= custody_end:
        return 'custody_deadline'
    return None


def verify_row(row: dict, *, session: str, source_commit: str, sequence: int, ready_wall: float,
               ready_at: float, last: float, now: float, custody_end: float) -> bool:
    try:
        stamp = datetime.fromisoformat(row['observed_at'])
        wall = stamp.timestamp()
        return (
            row['schema'] == 'campaign-watch-attempt/1' and row['source_commit'] == source_commit
            and row['session'] == session and type(row['sequence']) is int and row['sequence'] == sequence
            and row['phase'] in {'active', 'ending'} and stamp.utcoffset() is not None
            and all(finite(row[k]) for k in ('start', 'observation', 'recorded_wall'))
            and re.fullmatch(re.escape(session)+r'-[0-9]+', row['source']) is not None
            and re.fullmatch(r'[a-f0-9]{64}', row['sha256']) is not None
            and wall >= ready_wall and abs(ready_at + wall - ready_wall - row['observation']) < .25
            and last < row['observation'] <= row['start'] <= now < row['start'] + 4
            and row['start'] - row['observation'] <= 12
            and abs(row['recorded_wall'] - (ready_wall + row['start'] - ready_at)) < 4
            and cutoff_reason(now, last, custody_end) is None
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def terminal_coverage(receipt: dict, *, session: str, source_commit: str, rows: list, ready_wall: float | None,
                      ready_at: float | None, started_wall: float, native_pid: int | None) -> bool:
    try:
        cleanup = receipt['cleanup']
        native = cleanup['native']
        if (receipt['schema'] != 'campaign-receipt/3' or receipt['session'] != session
                or receipt['source_commit'] != source_commit or not rows or ready_wall is None
                or not all(finite(receipt[k]) for k in ('started_wall', 'ended_wall', 'elapsed_seconds'))
                or not started_wall <= receipt['started_wall'] <= ready_wall <= receipt['ended_wall']
                or receipt['elapsed_seconds'] < 0
                or abs(receipt['ended_wall'] - receipt['started_wall'] - receipt['elapsed_seconds']) > 1
                or any(receipt[k] is not True for k in ('native_absence_verified',
                    'deciding_hosts_quiescent', 'input_authority_revoked'))
                or cleanup['schema'] != 'computer-cleanup/1' or cleanup['session'] != session
                or cleanup['native_absence_verified'] is not True
                or type(cleanup['normal_native_exit_zero']) is not bool
                or native['pid'] != native_pid or native['pgid'] != native_pid
                or type(native['returncode']) is not int
                or native['process_absent'] is not True or native['group_absent'] is not True):
            return False
        terminal_at = ready_at + receipt['ended_wall'] - ready_wall
        return rows[-1]['receipt'] <= terminal_at < rows[-1]['observation'] + WINDOW
    except (KeyError, TypeError, ValueError):
        return False


def pause_boundary(rows: list, last: float | None, pause_at: float, now: float,
                   custody_end: float) -> tuple[str | None, float, list]:
    raced = []
    while rows and rows[-1]['receipt'] >= pause_at:
        row = rows.pop()
        raced.append(row)
        last = row['prior_observation']
    deadline = min(last + WINDOW, custody_end) if last is not None else custody_end
    reason = cutoff_reason(now, last, custody_end)
    grace = 0 if reason else max(0, min(PAUSE_REPLY, deadline-now))
    return reason, grace, raced


def supervise(package: Path, profile: dict, child: subprocess.Popen, gateway: subprocess.Popen,
              wake: subprocess.Popen, checks: socket.socket, stops: socket.socket,
              interrupted: Callable[[], bool], result: dict, *, clock=time) -> str:
    """Guard original clocks using datagrams, independently of the gateway worker."""
    ready, started, receipt = (package/name for name in ('ready.json', 'started.json', 'receipt.json'))
    custody_end = result['started_monotonic'] + profile['wall_seconds']
    checks.setblocking(False); stops.setblocking(False)
    last = ready_at = ready_wall = None
    have_started = False
    rows = result['accepted']

    def receive_stop():
        message = stops.recv(128).decode()
        if not message.startswith('pause:'):
            return 'acknowledgement_uncertain'
        pause_at = float(message.removeprefix('pause:'))
        if not finite(pause_at) or not result['started_monotonic'] <= pause_at <= clock.monotonic():
            return 'invalid_pause_clock'
        result['pause_requested'] = pause_at
        reason, grace, raced = pause_boundary(rows, last, pause_at, clock.monotonic(), custody_end)
        result['checks_raced_with_pause'] = raced
        if reason:
            return reason
        if select.select([stops], [], [], grace)[0]:
            result['pause_reply_forwarded'] = stops.recv(128) == b'pause-replied'
        return 'operator_pause'

    while True:
        # Pause wins a simultaneous terminal/check race and never renews custody.
        if select.select([stops], [], [], 0)[0]:
            return receive_stop()
        child_exited = child.poll() is not None
        wake_code = wake.poll()
        if (interrupted() or gateway.poll() is not None
                or (wake_code is not None and (not child_exited or wake_code != 0))):
            return 'supervision_lost'
        if child_exited:
            if not receipt.is_file():
                return 'custodian_receipt_missing'
            report = read_json(receipt, 1048576)
            result['custodian_receipt'] = report
            covered = have_started and terminal_coverage(report, session=profile['session'],
                source_commit=profile['source_commit'], rows=rows, ready_wall=ready_wall,
                ready_at=ready_at, started_wall=result['started_wall'], native_pid=result.get('native_pid'))
            result['terminal_coverage_verified'] = bool(covered)
            return 'custodian_terminal' if covered else 'terminal_watch_unverified'
        if not have_started and started.is_file():
            try:
                opening = read_json(started)
            except (OSError, ValueError):
                return 'invalid_custodian_start'
            if type(opening) is not dict:
                return 'invalid_custodian_start'
            end = opening.get('deadline_monotonic')
            wall = opening.get('started_wall')
            now = clock.monotonic()
            if (opening.get('schema') != 'computer-start/1' or opening.get('session') != profile['session']
                    or not finite(end) or not finite(wall)
                    or not result['started_wall'] <= wall <= clock.time()
                    or not now < end <= now + profile['wall_seconds']
                    or abs(end - (result['started_monotonic'] + wall - result['started_wall']
                                  + profile['wall_seconds'])) > 1):
                return 'invalid_custodian_start'
            custody_end = end
            result['custody_deadline_monotonic'] = end
            have_started = True
        if ready_at is None and ready.is_file():
            try:
                target = read_json(ready)
            except (OSError, ValueError):
                return 'invalid_custodian_ready'
            if type(target) is not dict:
                return 'invalid_custodian_ready'
            wall = target.get('ready_wall')
            if (target.get('schema') != 'computer-ready/1' or target.get('session') != profile['session']
                    or not have_started or target.get('viewer_url') != f"http://127.0.0.1:{profile['port']}/"
                    or type(target.get('pid')) is not int or target['pid'] <= 0 or not finite(wall)
                    or not opening['started_wall'] <= wall <= clock.time()):
                return 'invalid_custodian_ready'
            ready_wall = wall
            ready_at = last = clock.monotonic() - (clock.time() - wall)
            result.update(ready_wall=ready_wall, ready_monotonic=ready_at, native_pid=target['pid'])
            print(f"Exact spectator ready: {result.get('gateway_url')} ({profile['session']})", flush=True)
        interest = [stops, checks] if not receipt.exists() else [stops]
        deadline = min(last + WINDOW, custody_end) if last is not None else custody_end
        available, _, _ = select.select(interest, [], [], max(0, min(.1, deadline-clock.monotonic())))
        now = clock.monotonic()
        if stops in available:
            return receive_stop()
        reason = cutoff_reason(now, last, custody_end)
        if reason:
            return reason
        if checks not in available:
            continue
        row = json.loads(checks.recv(4096))
        now = clock.monotonic()
        if (last is None or receipt.exists() or child.poll() is not None
                or (rows and rows[-1]['phase'] == 'ending' and row.get('phase') != 'ending')
                or not verify_row(row, session=profile['session'], source_commit=profile['source_commit'],
                    sequence=len(rows)+1, ready_wall=ready_wall, ready_at=ready_at, last=last,
                    now=now, custody_end=custody_end)):
            return cutoff_reason(now, last, custody_end) or 'invalid_watch_acknowledgement'
        if select.select([stops], [], [], 0)[0]:
            return receive_stop()
        try:
            checks.send(f"accepted:{row['sequence']}:{row['start']!r}".encode())
        except OSError:
            return 'acknowledgement_uncertain'
        rows.append(dict(row, receipt=now, prior_observation=last))
        last = row['observation']


def run_supervised(directory: Path, *, popen=subprocess.Popen, clock=time) -> dict:
    directory = directory.resolve(strict=True)
    if any((directory/name).exists() or (directory/name).is_symlink() for name in MARKERS):
        raise ValueError('Selected package has prior/partial supervision; never rearm it')
    profile, route, _ = preflight(directory)
    secret = os.environ.get(route['api_key_env'])
    if not secret:
        raise ValueError('Selected provider credential is unavailable; supply its explicit environment variable')
    manifest_sha = digest(directory/'manifest.json')
    result = dict(schema='campaign-watch-terminal/1', session=profile['session'],
        source_commit=profile['source_commit'], manifest_sha256=manifest_sha,
        started_wall=clock.time(), started_monotonic=clock.monotonic(), watch_seconds=WINDOW,
        accepted=[], children={}, cleanup={}, gateway_url=None, pause_reply_forwarded=False,
        terminal_coverage_verified=False, reason='startup_failed')
    write_new(directory/'watch-start.json', {**{k: result[k] for k in ('session', 'source_commit',
        'manifest_sha256', 'started_wall', 'started_monotonic', 'watch_seconds')},
        'schema': 'campaign-watch-start/1'})
    # Reserve every evidence file before any child. Even partial reservation is inert forever.
    interrupted = False
    previous = {}
    handles = {}
    def stop(signum, frame):
        nonlocal interrupted
        interrupted = True
        result['signal'] = signal.Signals(signum).name
    try:
        with (directory/'watch-attempts.jsonl').open('x'):
            pass
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, stop)
        env = dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8')
        with ExitStack() as stack:
            checks, tx, stops, stop_tx = [stack.enter_context(s) for s in (
                *socket.socketpair(type=socket.SOCK_DGRAM), *socket.socketpair(type=socket.SOCK_DGRAM))]
            with (directory/'custodian-stdout.txt').open('xb') as stdout, (directory/'custodian-stderr.txt').open('xb') as stderr:
                def launch(name, argv, **kwargs):
                    if interrupted:
                        raise ValueError('Launch cancelled before '+name)
                    handle = popen(argv, start_new_session=True, **kwargs)
                    handles[name] = handle
                    result['children'][name] = dict(pid=handle.pid, pgid=handle.pid,
                                                   created_process_group=True, argv=argv)
                    return handle
                child = launch('custodian', [sys.executable, '-m', 'tools.campaign_run', '--run', str(directory)],
                    cwd=ROOT, env={**env, route['api_key_env']: secret}, stdout=stdout, stderr=stderr)
                del secret
                gateway = launch('gateway', [sys.executable, '-m', 'tools.campaign_watch', str(directory),
                    profile['session'], profile['source_commit'], str(profile['port']), str(child.pid),
                    str(tx.fileno()), str(stop_tx.fileno())], cwd=ROOT, env=env,
                    pass_fds=(tx.fileno(), stop_tx.fileno()), stdout=stdout, stderr=stderr)
                tx.close(); stop_tx.close()
                wake = launch('wake', ['/usr/bin/caffeinate', '-di', '-w', str(child.pid)], env=env,
                              stdout=stdout, stderr=stderr)
                # Bounded startup remains interruptible and observes all owned handles.
                end = clock.monotonic()+8
                while not select.select([checks], [], [], .1)[0]:
                    if interrupted or any(h.poll() is not None for h in handles.values()) or clock.monotonic() >= end:
                        raise ValueError('Spectator gateway failed to start or launch cancelled')
                opening = json.loads(checks.recv(4096))
                if set(opening) != {'port'} or type(opening['port']) is not int or not 1024 <= opening['port'] <= 65535:
                    raise ValueError('Invalid gateway startup')
                result['gateway_url'] = f"http://127.0.0.1:{opening['port']}/"
                result['reason'] = supervise(directory, profile, child, gateway, wake, checks, stops,
                                             lambda: interrupted, result, clock=clock)
    except (Exception, KeyboardInterrupt) as exc:
        result['error'] = f'{type(exc).__name__}: {str(exc)[:400]}'
        result['reason'] = 'launch_or_supervision_error'
    finally:
        result['guard_terminal_monotonic'] = clock.monotonic()
        # Request the original custodian stop and remove HTTP service immediately,
        # before waiting for the custodian's bounded independent closeout.
        termination = {}
        for name in ('custodian', 'gateway'):
            if name in handles and handles[name].poll() is None:
                try:
                    handles[name].terminate()
                    termination[name] = dict(termination_requested=True)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    termination[name] = dict(termination_error=type(exc).__name__)
        # close_group is only used for handles launched here with start_new_session.
        for name in ('gateway', 'custodian', 'wake'):
            if name not in handles:
                result['cleanup'][name] = dict(launched=False)
                continue
            try:
                handle = handles[name]
                graceful = termination.get(name, {})
                if name in {'custodian', 'gateway'} and handle.poll() is None:
                    # Preserve the original bounded custodian closeout opportunity;
                    # its own native/host cleanup remains authoritative.
                    try:
                        handle.wait(timeout=60 if name == 'custodian' else 5)
                    except subprocess.TimeoutExpired:
                        graceful['grace_expired'] = True
                result['cleanup'][name] = dict(launched=True, **graceful, **close_group(handle))
            except BaseException as exc:
                result['cleanup'][name] = dict(launched=True, process_absent=False, group_absent=False,
                    error=type(exc).__name__, error_message=str(exc)[:400],
                    error_traceback=traceback.format_exc(limit=8))
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        # Capture custodian disposition separately even when the watch deadline failed.
        if 'custodian' in handles and (directory/'receipt.json').is_file():
            try:
                final_receipt = read_json(directory/'receipt.json', 1048576)
                result['custodian_receipt_unchanged'] = (
                    'custodian_receipt' not in result or result['custodian_receipt'] == final_receipt)
                if not result['custodian_receipt_unchanged']:
                    result['terminal_coverage_verified'] = False
                    result['custodian_receipt_after_cleanup'] = final_receipt
                else:
                    result['custodian_receipt'] = final_receipt
            except (OSError, ValueError) as exc:
                result['custodian_receipt_error'] = type(exc).__name__
                result['terminal_coverage_verified'] = False
        elif 'custodian' in handles:
            result['custodian_receipt_missing_after_cleanup'] = True
            result['terminal_coverage_verified'] = False
        result['cleanup_verified'] = all(v.get('process_absent') is True and v.get('group_absent') is True
            for v in result['cleanup'].values() if v['launched'])
        result['ended_wall'] = clock.time(); result['ended_monotonic'] = clock.monotonic()
        try:
            result['manifest_unchanged'] = digest(directory/'manifest.json') == manifest_sha
        except OSError as exc:
            result['manifest_unchanged'] = False
            result['manifest_error'] = type(exc).__name__
        if not result['manifest_unchanged']:
            result['terminal_coverage_verified'] = False
        write_new(directory/'watch-terminal.json', result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    result = run_supervised(parser.parse_args(argv).run)
    print(json.dumps(result))
    return 0 if (result['reason'] == 'custodian_terminal' and result['terminal_coverage_verified']
        and result['cleanup_verified'] and result['manifest_unchanged']
        and result['cleanup']['custodian']['returncode'] == 0) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f'Supervision refused: {type(exc).__name__}: {exc}')
