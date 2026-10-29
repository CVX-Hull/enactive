"""Actual SDL refusal with invalid inherited ownership, never gameplay."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import uuid

from .build import ROOT
from .client import atomic
from .run import prepared_launch


def check(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for mode in ('missing', 'malformed', 'closed', 'nonregular', 'wrong-file'):
        case = output / mode
        case.mkdir()
        bridge = case / 'bridge'
        bridge.mkdir(mode=0o700)
        session = uuid.uuid4().hex
        with (case / 'user.lock').open('a') as shared, (case / 'other.lock').open('a') as other:
            fcntl.flock(shared, fcntl.LOCK_EX | fcntl.LOCK_NB)
            pipe_read, pipe_write = os.pipe()
            env = dict(PATH=os.environ['PATH'], LANG='en_US.UTF-8',
                ENACTIVE_COMPUTER_LIBRARY=str(ROOT / '.runtime/computer-control-build/bridge.dylib'),
                ENACTIVE_COMPUTER_DIR=str(bridge), ENACTIVE_COMPUTER_SESSION=session,
                ENACTIVE_COMPUTER_LOCK_FILE=str(case / 'user.lock'))
            passed = (shared.fileno(),)
            if mode == 'malformed':
                env['ENACTIVE_COMPUTER_LOCK_FD'] = 'not-a-descriptor'
            elif mode == 'closed':
                env['ENACTIVE_COMPUTER_LOCK_FD'] = str(shared.fileno())
                passed = ()
            elif mode == 'nonregular':
                env['ENACTIVE_COMPUTER_LOCK_FD'] = str(pipe_read)
                passed = (pipe_read,)
            elif mode == 'wrong-file':
                env['ENACTIVE_COMPUTER_LOCK_FD'] = str(other.fileno())
                passed = (other.fileno(),)
            command = [str(ROOT / '.runtime/computer-control-build/fixture'), str(case / 'events.jsonl'), '--hidden']
            script = '\n'.join('exec ' + shlex.join(command) if line.startswith('exec ./cataclysm-tiles') else line
                for line in prepared_launch().splitlines()) + '\n'
            (case / 'launch.sh').write_text(script)
            with (case / 'console.log').open('x') as log:
                child = subprocess.Popen(['/bin/sh', str(case / 'launch.sh')], env=env,
                    stdout=log, stderr=log, start_new_session=True, pass_fds=passed)
                try:
                    end = time.monotonic() + 10
                    while True:
                        path = case / 'events.jsonl'
                        records = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
                        if any(r.get('fixture_ready') for r in records):
                            break
                        assert child.poll() is None and time.monotonic() < end, 'Fixture startup unavailable'
                        time.sleep(.02)
                    identity = uuid.uuid4().hex
                    atomic(bridge / 'request.json', dict(schema='computer-request/1', id=identity, session=session,
                        kind='input', expires_ms=int((time.time() + 5) * 1000),
                        input=dict(type='key', key='RIGHT', modifiers=[])))
                    time.sleep(.15)
                    assert not (bridge / 'state.json').exists(), 'Invalid ownership enabled target'
                    assert (bridge / 'request.json').exists() and not (bridge / 'claimed.json').exists()
                    assert not list((bridge / 'receipts').glob('*.json'))
                    records = [json.loads(line) for line in path.read_text().splitlines()]
                    assert not any(r.get('key') == 1073741903 for r in records), 'Unowned RIGHT reached fixture'
                finally:
                    child.terminate()
                    child.wait(timeout=5)
                    os.close(pipe_read)
                    os.close(pipe_write)
            results.append(dict(mode=mode, input_refused_before_claim=True, child_exit=child.returncode))
    atomic(output / 'check.json', dict(passed=True, scope='Actual SDL through prepared shell; malformed inherited ownership refuses control', results=results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    check(parser.parse_args().output.resolve())
