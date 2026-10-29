"""Lead-owned actual SDL fixture check; not gameplay or real-human qualification."""
from __future__ import annotations

import argparse
import json
import os
import shlex
from pathlib import Path
import subprocess
import time
import uuid

from .build import ROOT
from .client import ComputerClient, atomic
from .protocol import read_json, receipt
from .run import prepared_launch


def check(path: Path, *, via_shell: bool = False, offscreen: bool = False, terminal: str = 'takeover') -> None:
    path.mkdir(parents=True, exist_ok=False)
    (path / 'bridge').mkdir(mode=0o700)
    (path / 'operations').mkdir()
    resources = ROOT / '.runtime/Cataclysm.app/Contents/Resources'
    session = uuid.uuid4().hex
    env = dict(PATH=os.environ['PATH'], LANG='en_US.UTF-8',
        DYLD_FRAMEWORK_PATH=str(resources), DYLD_LIBRARY_PATH=str(resources),
        DYLD_INSERT_LIBRARIES=str(ROOT / '.runtime/computer-control-build/bridge.dylib'),
        ENACTIVE_COMPUTER_DIR=str(path / 'bridge'), ENACTIVE_COMPUTER_SESSION=session,
        SDL_MAC_BACKGROUND_APP='1', SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN='1')
    command = [str(ROOT / '.runtime/computer-control-build/fixture'), str(path / 'events.jsonl'), '--hidden']
    if offscreen:
        command.append('--offscreen')
    if via_shell:
        source = prepared_launch()
        lines = source.splitlines()
        lines = ['exec ' + shlex.join(command) if line.startswith('exec ./cataclysm-tiles') else line for line in lines]
        (path / 'launch.sh').write_text('\n'.join(lines) + '\n')
        env['ENACTIVE_COMPUTER_LIBRARY'] = str(ROOT / '.runtime/computer-control-build/bridge.dylib')
        command = ['/bin/sh', str(path / 'launch.sh')]
    client = None
    results = []
    with (path / 'console.log').open('w') as log:
        child = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            atomic(path / 'control.json', dict(schema='computer-run/1', session=session, pid=child.pid,
                deadline_monotonic=time.monotonic() + 60, max_inputs=32, max_requests=32,
                max_frames=32, max_bytes=1073741824))
            # Bind is earlier than the first present. Retain known no-capture
            # refusals and explicitly choose a later observation, without input.
            startup = time.monotonic() + 10
            while not (path / 'bridge/state.json').exists():
                if child.poll() is not None or time.monotonic() >= startup:
                    raise RuntimeError('Fixture did not establish its target within startup allowance')
                time.sleep(.02)
            client = ComputerClient(path)
            for attempt in range(3):
                value, png = client.execute(observe=True)
                results.append(value)
                print('observe', attempt, value['status'], len(png or b''), flush=True)
                if png:
                    break
                time.sleep(.1)
            assert png, results[-1]
            initial = value['capture']
            for action in (dict(type='key', key='a', modifiers=[]),
                           dict(type='text', text='hé✓'),
                           dict(type='key', key='a', modifiers=['SHIFT'])):
                value, png = client.execute([action])
                results.append(value)
                print('input', action['type'], value['status'], flush=True)
                assert value['status'] == 'completed', value
            capture = value['capture']['capture_id']
            value, png = client.execute([dict(type='click', x=200, y=180, button='left')], capture_id=capture)
            results.append(value)
            assert value['status'] == 'completed', value
            value, png = client.execute([dict(type='key', key='r', modifiers=[])])
            results.append(value)
            print('resize', value.get('capture'), flush=True)
            assert value['capture']['width'] == 800, value
            value, png = client.execute([dict(type='click', x=200, y=180, button='left')], capture_id=capture)
            results.append(value)
            assert value['status'] == 'refused' and value['receipts'][0]['emitted_events'] == 0, value
            value, png = client.execute([dict(type='key', key='RIGHT', modifiers=[])])
            results.append(value)
            assert value['status'] == 'completed', value
            value, png = client.execute([dict(type='key', key='d' if terminal == 'target-loss' else 't', modifiers=[])])
            results.append(value)
            print(terminal, value['status'], value.get('target'), flush=True)
            assert value['target']['paused'] and value['status'] == 'unknown', value
            if terminal == 'target-loss':
                assert value['target']['takeover_generation'] == 0
                assert 'target' in value['target']['error'].lower() or 'renderer' in value['target']['error'].lower()
                # Already-published Observe may settle late after input fencing.
                # Count publication, not asynchronous receipt arrival.
                def published():
                    return sum(json.loads(line)['type'] == 'native-intent'
                        for line in (path / 'client.jsonl').read_text().splitlines())
                count = published()
                try:
                    client.execute([dict(type='key', key='RIGHT', modifiers=[])])
                except ValueError:
                    pass
                else:
                    raise AssertionError('Lost renderer permitted new input')
                time.sleep(.1)
                assert published() == count
                def retained_capture():
                    end = time.monotonic() + 1
                    while any((path / 'bridge' / n).exists() for n in ('request.json', 'claimed.json')):
                        assert time.monotonic() < end, 'Old collection did not settle'
                        time.sleep(.005)
                    # Read-only collection after Pause; never rearm or input.
                    reply = client._send('observe', None, end)
                    target = path / 'bridge/receipts' / (reply['id'] + '.json')
                    while not target.exists():
                        assert time.monotonic() < end, 'Read-only capture receipt unavailable'
                        time.sleep(.005)
                    collected = receipt(read_json(target), identity=reply['id'], session=session)
                    assert collected['disposition'] == 'delivered'
                    return collected['frame']['capture_id']
                captured = retained_capture()
                time.sleep(.1)
                assert retained_capture() == captured, 'Replacement renderer resumed capture'
            records = [json.loads(line) for line in (path / 'events.jsonl').read_text().splitlines()]
            texts = [r.get('text') for r in records if r['type'] == 771]
            assert 'a' in texts and 'hé✓' in texts and 'A' in texts, texts
            clicks = [r for r in records if r['type'] in (1025, 1026)]
            assert len(clicks) == 2 and clicks[0]['drain'] != clicks[1]['drain'], clicks
            assert all(r['position'] == [200, 180] and r['mouse'] == [200, 180] for r in clicks), clicks
            assert clicks[0]['buttons'] & 1 and not clicks[1]['buttons'] & 1, clicks
            if offscreen:
                assert all(r['offscreen'] for r in clicks), clicks
            assert initial['width'] == 640 and initial['window_width'] == 640
            atomic(path / 'check.json', dict(passed=True, scope='Actual SDL fixture; hidden window, unit geometry; synthetic unowned events, not real-human/game qualification',
                results=results, event_count=len(records), via_shell=via_shell, offscreen=offscreen, terminal=terminal))
        finally:
            if client is not None:
                client.close()
            child.terminate()
            child.wait(timeout=5)
            print('owned fixture closed', child.returncode, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--via-shell', action='store_true')
    parser.add_argument('--offscreen', action='store_true')
    parser.add_argument('--terminal', choices=('takeover', 'target-loss'), default='takeover')
    options = parser.parse_args()
    check(options.output.resolve(), via_shell=options.via_shell, offscreen=options.offscreen, terminal=options.terminal)
