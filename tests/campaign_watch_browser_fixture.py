"""Real spectator/gateway UI over labelled synthetic pixels; no game or provider.

This test-only manifest cannot pass the production campaign package validator.
The rehearsal exercises an explicit browser click and Pause, not native effects.
"""
from __future__ import annotations

import argparse
import hashlib
import io
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

from PIL import Image, ImageDraw

from harness.application import Application
from harness.computer.launch import close_group
from harness.computer.runtime import ComputerRuntime
from harness.player.memory import Memory
from harness.server import serve
from tests.test_computer_runtime import Channel, Process
from tools.campaign_supervision import supervise

ROOT = Path(__file__).resolve().parents[1]
SESSION = 'a'*32


class FixturePixels(Channel):
    def __init__(self):
        super().__init__()
        pixels = Image.new('RGB', (640, 360), '#e8f3f8')
        ImageDraw.Draw(pixels).multiline_text((30, 120),
            'BROWSER UI FIXTURE - NO GAME\n\nSynthetic pixels. No player or provider running.', fill='#16364a')
        encoded = io.BytesIO(); pixels.save(encoded, format='PNG'); self.png = encoded.getvalue()

    def request(self, *args):
        value, png = super().request(*args)
        if value['frame'] is not None:
            value['frame'].update(width=640, height=360, window_width=640, window_height=360,
                                  viewport=[0, 0, 640, 360], presented_ms=int(time.time()*1000))
        return value, png


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    directory = parser.parse_args(argv).directory.resolve()
    if not directory.is_relative_to(ROOT/'.runtime'):
        raise ValueError('Select a fresh owned fixture directory under this checkout runtime')
    directory.mkdir(parents=True, exist_ok=False)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = b'{"schema":"watch-browser-fixture/1","scope":"no game or provider"}'
    (directory/'manifest.json').write_bytes(manifest)
    def write(name, value):
        (directory/name).write_text(json.dumps(value, indent=2)+'\n')
    wall, mono = time.time(), time.monotonic()
    write('watch-start.json', dict(schema='campaign-watch-start/1', session=SESSION,
        source_commit=source, manifest_sha256=hashlib.sha256(manifest).hexdigest(), watch_seconds=45,
        started_wall=wall, started_monotonic=mono))
    (directory/'watch-attempts.jsonl').touch()
    write('started.json', dict(schema='computer-start/1', session=SESSION,
                              started_wall=wall, deadline_monotonic=mono+180))
    channel = FixturePixels()
    runtime = ComputerRuntime(directory, SESSION, channel, Process(), mono+180,
        dict(max_inputs=20, max_requests=30, max_frames=40, max_bytes=2**30))
    memory = Memory(directory/'player.sqlite3')
    app = Application(runtime, memory, directory/'contexts')
    actor = runtime.add_actor(); runtime.observe(actor['actor_id'])
    server, server_thread = serve(app, 0)
    write('ready.json', dict(schema='computer-ready/1', session=SESSION, pid=123,
        ready_wall=time.time(), viewer_url=f'http://127.0.0.1:{server.server_port}/'))
    checks, tx = socket.socketpair(type=socket.SOCK_DGRAM)
    stops, stop_tx = socket.socketpair(type=socket.SOCK_DGRAM)
    gateway = None; guardian = None; closing = threading.Event()
    result = dict(scope='Real browser/service UI; synthetic pixels, no game/provider',
        accepted=[], started_wall=wall, started_monotonic=mono)
    try:
        gateway = subprocess.Popen([sys.executable, '-m', 'tools.campaign_watch', str(directory),
            SESSION, source, str(server.server_port), str(os.getpid()), str(tx.fileno()), str(stop_tx.fileno())],
            cwd=ROOT, start_new_session=True, pass_fds=(tx.fileno(), stop_tx.fileno()),
            env=dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8'))
        tx.close(); stop_tx.close()
        if not select.select([checks], [], [], 5)[0]:raise ValueError('Fixture gateway did not start')
        port = json.loads(checks.recv(4096))['port']
        result['gateway_url'] = f'http://127.0.0.1:{port}/'
        profile = dict(session=SESSION, source_commit=source, wall_seconds=180, port=server.server_port)
        live = SimpleNamespace(poll=lambda: None)
        def guard():
            result['reason'] = supervise(directory, profile, live, gateway, live, checks, stops,
                                         closing.is_set, result)
        guardian = threading.Thread(target=guard, daemon=True); guardian.start()
        write('fixture-ready.json', dict(url=result['gateway_url'], scope=result['scope'],
                                        source_commit=source, fixture_pid=os.getpid(), gateway_pid=gateway.pid))
        print(json.dumps(dict(url=result['gateway_url'], scope=result['scope'])), flush=True)
        while time.monotonic() < mono+180 and not (directory/'finish-fixture').exists():
            if not guardian.is_alive() and not channel.stopped.is_set():break
            closing.wait(.1)
    finally:
        closing.set()
        if guardian is not None:guardian.join(2)
        result['guardian_absent'] = guardian is None or not guardian.is_alive()
        if gateway is not None:
            if gateway.poll() is None:gateway.terminate()
            try:gateway.wait(5)
            except subprocess.TimeoutExpired:pass
            result['gateway_cleanup'] = close_group(gateway)
        result['synthetic_channel_stopped'] = channel.stopped.is_set()
        server.shutdown(); server.server_close(); server_thread.join(2)
        result['service_thread_absent'] = not server_thread.is_alive()
        runtime.close(); memory.close()
        for link in (checks, tx, stops, stop_tx):link.close()
        write('fixture-result.json', result)
    return 0 if (result.get('reason') == 'operator_pause' and result['synthetic_channel_stopped']
        and result['guardian_absent'] and result['service_thread_absent']
        and result['gateway_cleanup']['process_absent'] and result['gateway_cleanup']['group_absent']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
