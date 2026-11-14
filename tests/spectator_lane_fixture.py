"""Graphical-lane rehearsal: the real control path plus the real viewer over a replayed run.

The custodian, server, gateway and supervisor are the production modules, serving labelled
synthetic pixels (no game, provider or player). The viewer reads a copy of an archived run that
`tests/spectator_replay.py` advances at its original pace, so the page shows a moving run. Stop
the fixture by Pause or by creating `finish-fixture` in its directory. Kill the viewer at any
time to check that the control strip and Pause keep working.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from harness.application import Application
from harness.computer.launch import close_group
from harness.computer.runtime import ComputerRuntime
from harness.player.memory import Memory
from harness.server import serve
from tests.campaign_watch_browser_fixture import FixturePixels
from tests.spectator_replay import prepare, replay
from tests.test_computer_runtime import Process
from tools.campaign_supervision import supervise

ROOT = Path(__file__).resolve().parents[1]
SESSION = 'b'*32


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True, help='archived run directory to replay')
    parser.add_argument('--runs', type=Path, required=True, help='directory of archived runs for cross-run views')
    parser.add_argument('--records', type=Path, required=True, help='evaluation root holding final records')
    parser.add_argument('--instant-until', type=float, default=1200.0)
    parser.add_argument('--seconds', type=float, default=600.0, help='fixture lifetime')
    options = parser.parse_args(argv)
    directory = options.directory.resolve()
    if not directory.is_relative_to(ROOT/'.runtime'):
        raise ValueError('Select a fresh owned fixture directory under this checkout runtime')
    directory.mkdir(parents=True, exist_ok=False)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = b'{"schema":"watch-browser-fixture/1","scope":"no game or provider; replayed viewer data"}'
    (directory/'manifest.json').write_bytes(manifest)
    def write(name, value):
        (directory/name).write_text(json.dumps(value, indent=2)+'\n')
    # The replayed run and a private evaluation root (final records are copied in, never modified).
    replayed = directory/'replay'
    prepare(options.source.resolve(), replayed)
    records = directory/'evaluations'
    subprocess.run(['cp', '-R', str(options.records.resolve()), str(records)], check=True)
    # The replay keeps the archived session ID; a final record of it would (correctly) block the live store.
    session = json.loads((replayed/'manifest.json').read_text())['session']
    subprocess.run(['rm', '-rf', str(records/session)], check=True)
    pacing = threading.Thread(target=replay, args=(options.source.resolve(), replayed),
        kwargs=dict(instant_until=options.instant_until, speed=1.0, stop_after=options.seconds), daemon=True)
    pacing.start()
    viewer_port = free_port()
    viewer = subprocess.Popen([sys.executable, '-m', 'harness.viewer', '--run', str(replayed), '--root', str(records),
        '--runs', str(options.runs.resolve()), '--port', str(viewer_port), '--host', '127.0.0.1'], cwd=ROOT,
        stdout=open(directory/'viewer-stdout.txt', 'w'), stderr=open(directory/'viewer-stderr.txt', 'w'),
        start_new_session=True)
    wall, mono = time.time(), time.monotonic()
    write('watch-start.json', dict(schema='campaign-watch-start/4', session=SESSION, source_commit=source,
        manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        viewer_port=viewer_port, started_wall=wall, started_monotonic=mono))
    write('started.json', dict(schema='computer-start/1', session=SESSION, started_wall=wall,
                              deadline_monotonic=mono+options.seconds))
    channel = FixturePixels()
    runtime = ComputerRuntime(directory, SESSION, channel, Process(), mono+options.seconds,
        dict(max_inputs=20, max_requests=30, max_frames=40, max_bytes=2**30))
    memory = Memory(directory/'player.sqlite3')
    app = Application(runtime, memory, directory/'contexts',knowledge=Path(__file__).with_name('fixtures')/'empty-delivered-knowledge.json')
    actor = runtime.add_actor(); runtime.observe(actor['actor_id'])
    server, server_thread = serve(app, 0)
    write('ready.json', dict(schema='computer-ready/1', session=SESSION, pid=123, ready_wall=time.time(),
        viewer_url=f'http://127.0.0.1:{server.server_port}/'))
    stops, stop_tx = socket.socketpair(type=socket.SOCK_DGRAM)
    gateway = None; guardian = None; closing = threading.Event()
    result = dict(scope='Real control path and viewer; synthetic custodian pixels; replayed viewer run',
        started_wall=wall, started_monotonic=mono, viewer_pid=viewer.pid, viewer_port=viewer_port)
    try:
        gateway = subprocess.Popen([sys.executable, '-m', 'tools.campaign_watch', str(directory), SESSION, source,
            str(server.server_port), str(os.getpid()), str(stop_tx.fileno()),
            '--viewer-port', str(viewer_port)], cwd=ROOT, start_new_session=True,
            pass_fds=(stop_tx.fileno(),),
            env=dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8'))
        stop_tx.close()
        if not select.select([stops], [], [], 5)[0]: raise ValueError('Fixture gateway did not start')
        port = json.loads(stops.recv(4096))['port']
        result['gateway_url'] = f'http://127.0.0.1:{port}/'
        profile = dict(session=SESSION, source_commit=source, wall_seconds=options.seconds, port=server.server_port)
        live = SimpleNamespace(poll=lambda: None)
        def guard():
            result['reason'] = supervise(directory, profile, live, gateway, live, stops, closing.is_set, result)
        guardian = threading.Thread(target=guard, daemon=True); guardian.start()
        write('fixture-ready.json', dict(url=result['gateway_url'], scope=result['scope'], viewer_pid=viewer.pid,
                                        viewer_port=viewer_port, gateway_pid=gateway.pid, replay=str(replayed)))
        print(json.dumps(dict(url=result['gateway_url'], viewer_pid=viewer.pid)), flush=True)
        while time.monotonic() < mono+options.seconds and not (directory/'finish-fixture').exists():
            if not guardian.is_alive() and not channel.stopped.is_set(): break
            if channel.stopped.is_set() and not guardian.is_alive(): break
            closing.wait(.1)
    finally:
        closing.set()
        if guardian is not None: guardian.join(2)
        result['guardian_absent'] = guardian is None or not guardian.is_alive()
        result['viewer_alive_at_end'] = viewer.poll() is None
        if viewer.poll() is None: viewer.terminate()
        try: viewer.wait(5)
        except subprocess.TimeoutExpired: viewer.kill()
        if gateway is not None:
            if gateway.poll() is None: gateway.terminate()
            try: gateway.wait(5)
            except subprocess.TimeoutExpired: pass
            result['gateway_cleanup'] = close_group(gateway)
        result['synthetic_channel_stopped'] = channel.stopped.is_set()
        server.shutdown(); server.server_close(); server_thread.join(2)
        runtime.close(); memory.close()
        for link in (stops, stop_tx): link.close()
        terminal = directory/'watch-terminal.json'
        if terminal.exists(): result['pause_reason'] = json.loads(terminal.read_text()).get('pause_reason')
        write('fixture-result.json', result)
    return 0 if result.get('reason') == 'operator_pause' and result['synthetic_channel_stopped'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
