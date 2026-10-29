"""Custodian for one frozen #181 candidate proof, outside the product runtime."""
from __future__ import annotations

from typing import Any

import argparse
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

from .build import ROOT
from .client import atomic
from .protocol import ControlError, closed, integer, read_json
from .viewer import serve
from harness.prepared_app import wrapper_source


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepared_launch() -> str:
    source = wrapper_source(ROOT)
    exports = [line for line in source.splitlines() if line.startswith('export CDDA_HARNESS_DIR=')]
    if len(exports) != 1:
        raise ControlError('Prepared wrapper changed; review isolated launch derivation')
    derived = source.replace(exports[0], 'unset CDDA_HARNESS_DIR', 1)
    # Protected /bin/sh may strip inherited DYLD_*; export after shell startup.
    return derived.replace('exec ./cataclysm-tiles',
        'export DYLD_INSERT_LIBRARIES="$ENACTIVE_COMPUTER_LIBRARY"\nexec ./cataclysm-tiles', 1)


def preflight(run: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    run = run.resolve(strict=True)
    if run.is_symlink() or ROOT not in run.parents:
        raise ControlError('Proof must be project-local')
    profile = read_json(run / 'manifest.json')
    if profile['schema'] != 'computer-proof/2':
        raise ControlError('Unsupported proof manifest')
    if not isinstance(profile['session'], str) or re.fullmatch('[0-9a-f]{32}', profile['session']) is None:
        raise ControlError('Invalid fresh session')
    closed(profile['limits'], {'max_inputs', 'max_requests', 'max_frames', 'max_bytes'})
    for value in profile['limits'].values():
        integer(value, 1, 2**40)
    integer(profile['port'], 1024, 65535)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if profile['source_commit'] != source or subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ControlError('Proof requires exact clean source checkpoint')
    expected = {'route.json', 'mcp.json', 'context.txt', 'prompt.txt', 'launch.sh'}
    if set(profile['files']) != expected:
        raise ControlError('Freeze every driver input')
    for name, sha in profile['files'].items():
        if digest(run / name) != sha:
            raise ControlError('Frozen input changed')
    initial = profile['initial_files']
    if type(initial) is not dict or not 1 <= len(initial) <= 16:
        raise ControlError('Freeze bounded initial target configuration files')
    for name, sha in initial.items():
        path = Path(name)
        if (not path.is_absolute() or path != path.resolve() or ROOT not in path.parents or not path.is_file() or path.is_symlink()
                or not isinstance(sha, str) or re.fullmatch('[0-9a-f]{64}', sha) is None or digest(path) != sha):
            raise ControlError('Initial target configuration changed')
    if (run / 'launch.sh').read_text() != prepared_launch():
        raise ControlError('Frozen wrapper is not the isolated prepared launch')
    for name in ('native', 'library'):
        artifact = Path(profile[name]['path'])
        if not artifact.is_file() or artifact.is_symlink() or digest(artifact) != profile[name]['sha256']:
            raise ControlError('Frozen mechanical binary changed')
    if (run / 'started.json').exists() or (run / 'bridge').exists():
        raise ControlError('Never reopen an old proof')
    route = read_json(run / 'route.json')
    if route['api_key_env'] != 'OPENROUTER_API_KEY':
        raise ControlError('Only the selected credential route is admitted')
    validator = "import{readFileSync as r}from'node:fs';import{validateConfiguration as v,validateMcpConfiguration as m}from'./tools/player_host/host.mjs';const j=p=>JSON.parse(r(p,'utf8'));v(j(process.argv[1]),process.argv[3],process.argv[4]);m(j(process.argv[2]));"
    subprocess.run([profile['node'], '--input-type=module', '-e', validator,
        str(run / 'route.json'), str(run / 'mcp.json'), route['model']['id'], profile['effort']],
        cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    if not 60 <= profile['wall_seconds'] <= 9000 or not 0 < profile['host_seconds'] < profile['wall_seconds'] - 30:
        raise ControlError('Original host/cleanup forecast does not fit')
    return profile, route


def stop_child(child: subprocess.Popen, grace: float, *, native: bool = False) -> dict[str, Any]:
    signals = []
    plan = ((signal.SIGTERM, grace), (signal.SIGKILL, 2)) if native else ((signal.SIGINT, grace), (signal.SIGTERM, 3), (signal.SIGKILL, 2))
    for sig, wait in plan:
        if child.poll() is not None:
            break
        try:
            child.send_signal(sig)
            signals.append(sig.name)
            child.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            pass
        except ProcessLookupError:
            pass
    return dict(pid=child.pid, returncode=child.poll(), signals=signals, exit_unresolved=child.poll() is None)


def run_proof(run: Path) -> dict[str, Any]:
    profile, route = preflight(run)
    secret = os.environ.get('OPENROUTER_API_KEY')
    if not secret:
        raise ControlError('Selected provider credential unavailable')
    clean = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'en_US.UTF-8'}
    session = profile['session']
    start = time.monotonic()
    deadline = start + profile['wall_seconds']
    lock_path = ROOT / '.runtime/bridge/game.lock'
    runtime_lock = lock_path.open('a')
    fcntl.flock(runtime_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    run.joinpath('bridge').mkdir(mode=0o700)
    run.joinpath('operations').mkdir(mode=0o700)
    with (run / 'started.json').open('x') as stream:
        stream.write(json.dumps(dict(session=session, source_commit=profile['source_commit'],
            started_wall=time.time(), started_monotonic=start)))
    interrupted = []
    def cancel(signum, frame):
        interrupted.append(signal.Signals(signum).name)
        (run / 'bridge/pause').touch()
    previous = {sig: signal.signal(sig, cancel) for sig in (signal.SIGINT, signal.SIGTERM)}
    game = host = server = thread = None
    report = dict(session=session, outcome='incomplete', input_authority_revoked=False,
                  native_absence_verified=False, deciding_host_quiescent=False, signals=interrupted)
    try:
        game_env = dict(clean, ENACTIVE_COMPUTER_LIBRARY=profile['library']['path'],
            ENACTIVE_COMPUTER_DIR=str(run / 'bridge'), ENACTIVE_COMPUTER_SESSION=session,
            ENACTIVE_COMPUTER_LOCK_FD=str(runtime_lock.fileno()), ENACTIVE_COMPUTER_LOCK_FILE=str(lock_path))
        # The frozen derived prepared wrapper explicitly unsets the old bridge.
        with (run / 'game-console.log').open('x') as game_log:
            game = subprocess.Popen(['/bin/sh', str(run / 'launch.sh')], cwd=ROOT, env=game_env,
                stdin=subprocess.DEVNULL, stdout=game_log, stderr=game_log, start_new_session=True,
                pass_fds=(runtime_lock.fileno(),))
        atomic(run / 'control.json', dict(schema='computer-run/1', session=session, pid=game.pid,
            deadline_monotonic=deadline, **profile['limits']))
        launch_deadline = min(deadline, start + 60)
        while time.monotonic() < launch_deadline:
            if interrupted or game.poll() is not None:
                raise ControlError('Owned launch cancelled or exited')
            try:
                target = read_json(run / 'bridge/state.json')
                if target['session'] != session or target['pid'] != game.pid:
                    raise ControlError('Native target identity differs')
                if target['error']:
                    raise ControlError('Native mechanical target fault: ' + target['error'])
                if target['window_id'] > 0:
                    break
            except FileNotFoundError:
                pass
            except ControlError as exc:
                if (run / 'bridge/state.json').exists():
                    raise exc
            time.sleep(.05)
        else:
            raise ControlError('Native interposition did not establish owned target')
        report['target_established_wall'] = time.time()
        server, thread = serve(run, profile['port'])
        host_args = [profile['node'], str(ROOT / 'tools/player_host/run.mjs'), '--config', str(run / 'route.json'),
            '--mcp-config', str(run / 'mcp.json'), '--context', str(run / 'context.txt'), '--model', route['model']['id'],
            '--effort', profile['effort'], '--timeout-seconds', str(min(profile['host_seconds'], deadline - time.monotonic() - 30)),
            '-o', str(run / 'player-final.txt')]
        with (run / 'host.jsonl').open('x') as output, (run / 'host-stderr.log').open('x') as errors, (run / 'prompt.txt').open() as prompt:
            host = subprocess.Popen(host_args, cwd=ROOT, env=dict(clean, OPENROUTER_API_KEY=secret),
                stdin=prompt, stdout=output, stderr=errors, start_new_session=True)
            atomic(run / 'host-process.json', dict(pid=host.pid, argv=host_args))
            exited_at = None
            paused_at = None
            while host.poll() is None:
                target = read_json(run / 'bridge/state.json')
                if interrupted or time.monotonic() >= deadline - 30:
                    raise ControlError('Original deadline or operator cancellation')
                if (run / 'bridge/pause').exists() or target['paused']:
                    # Native dispatch is already fenced. Allow only a bounded final
                    # report/collection grace, including normal MCP shutdown races.
                    if paused_at is None:
                        paused_at = time.monotonic()
                    if time.monotonic() - paused_at >= 30:
                        raise ControlError('Pause/takeover final-report grace exhausted')
                if game.poll() is not None:
                    if exited_at is None:
                        exited_at = time.monotonic()
                        report['native_exit_wall'] = time.time()
                    if time.monotonic() - exited_at >= 45:
                        raise ControlError('Native exited; final host grace exhausted')
                time.sleep(.1)
            report['host_returncode'] = host.returncode
            report['outcome'] = 'host_completed' if host.returncode == 0 else 'incomplete'
    except (Exception, KeyboardInterrupt) as exc:
        report['reason'] = str(exc)[:600]
        report['error_type'] = type(exc).__name__
    finally:
        def attempt(name, function):
            try:
                return function()
            except (Exception, KeyboardInterrupt) as exc:
                report[name + '_error'] = type(exc).__name__
                return None
        # Every owned cleanup action is independent of Pause/storage failures.
        attempt('pause', lambda: (run / 'bridge/pause').touch())
        report['input_authority_revoked'] = (run / 'bridge/pause').exists()
        if host is not None:
            report['host'] = attempt('host_cleanup', lambda: stop_child(host, 10))
            report['deciding_host_quiescent'] = attempt('host_status', host.poll) is not None
        else:
            report['deciding_host_quiescent'] = True
        if game is not None:
            normal_before_cleanup = attempt('native_status_before', game.poll)
            report['native'] = attempt('native_cleanup', lambda: stop_child(game, 2, native=True))
            report['normal_native_exit_zero'] = normal_before_cleanup == 0
            report['native_absence_verified'] = attempt('native_status_after', game.poll) is not None
        else:
            report['native_absence_verified'] = True
        if server is not None:
            attempt('viewer_shutdown', server.shutdown)
            attempt('viewer_close', server.server_close)
            attempt('viewer_join', lambda: thread.join(2))
        report['input_authority_revoked'] = report['input_authority_revoked'] or report['native_absence_verified']
        report['ended_wall'] = time.time()
        report['elapsed_seconds'] = time.monotonic() - start
        attempt('receipt', lambda: atomic(run / 'receipt.json', report))
        attempt('runtime_lock_close', runtime_lock.close)
        for sig, handler in previous.items():
            attempt('signal_restore', lambda sig=sig, handler=handler: signal.signal(sig, handler))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    options = parser.parse_args()
    result = run_proof(options.run.resolve(strict=True))
    print(json.dumps(result))
    raise SystemExit(0 if result['native_absence_verified'] and result['deciding_host_quiescent'] else 1)
