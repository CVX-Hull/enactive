"""Actual SDL launch refusal and inherited shared-lock lifetime checks.

Requires explicit retained binaries/resources. No game or shared runtime launch.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import select
import shlex
import socket
import subprocess
import time
import uuid

from harness.computer import protocol
from tests.computer_native_check import arguments, exclusion, fixture, records, wait_for


def invalid(options, mode):
    case = options.output / mode
    case.mkdir()
    with (case / 'user.lock').open('a') as shared, (case / 'other.lock').open('a') as other:
        if mode != 'unlocked':
            fcntl.flock(shared, fcntl.LOCK_EX | fcntl.LOCK_NB)
        parent, native = socket.socketpair()
        pipe_read, pipe_write = os.pipe()
        invalid_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        datagram = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        env = dict(PATH=os.environ['PATH'], LANG='en_US.UTF-8',
                   ENACTIVE_COMPUTER_LIBRARY=str(options.library),
                   DYLD_FRAMEWORK_PATH=str(options.resources), DYLD_LIBRARY_PATH=str(options.resources),
                   ENACTIVE_COMPUTER_SESSION=uuid.uuid4().hex,
                   ENACTIVE_COMPUTER_FD=str(native.fileno()),
                   ENACTIVE_COMPUTER_LOCK_FD=str(shared.fileno()),
                   ENACTIVE_COMPUTER_LOCK_FILE=str(case / 'user.lock'),
                   SDL_MAC_BACKGROUND_APP='1', SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN='1')
        passed = [shared.fileno(), native.fileno()]
        if mode == 'unlocked':
            pass
        elif mode == 'missing':
            del env['ENACTIVE_COMPUTER_LOCK_FD']
        elif mode == 'malformed':
            env['ENACTIVE_COMPUTER_LOCK_FD'] = 'not-a-descriptor'
        elif mode == 'closed':
            passed.remove(shared.fileno())
        elif mode == 'nonregular':
            env['ENACTIVE_COMPUTER_LOCK_FD'] = str(pipe_read)
            passed.append(pipe_read)
        elif mode == 'wrong-file':
            env['ENACTIVE_COMPUTER_LOCK_FD'] = str(other.fileno())
            passed.append(other.fileno())
        elif mode == 'socket-missing':
            del env['ENACTIVE_COMPUTER_FD']
        elif mode == 'socket-file':
            env['ENACTIVE_COMPUTER_FD'] = str(other.fileno())
            passed.append(other.fileno())
        elif mode == 'socket-inet':
            env['ENACTIVE_COMPUTER_FD'] = str(invalid_socket.fileno())
            passed.append(invalid_socket.fileno())
        elif mode == 'socket-datagram':
            env['ENACTIVE_COMPUTER_FD'] = str(datagram.fileno())
            passed.append(datagram.fileno())
        elif mode == 'legacy-directory':
            env['ENACTIVE_COMPUTER_DIR'] = str(case)
        elif mode == 'legacy-harness':
            env['CDDA_HARNESS_DIR'] = str(case)
        else:
            raise AssertionError(mode)
        command = [str(options.fixture), str(case / 'events.jsonl'), '--hidden', '--exit-after-ms', '1400']
        script = case / 'launch.sh'
        script.write_text('export DYLD_INSERT_LIBRARIES="$ENACTIVE_COMPUTER_LIBRARY"\nexec ' + shlex.join(command) + '\n')
        with (case / 'console.log').open('x') as log:
            child = subprocess.Popen(['/bin/sh', str(script)], env=env, stdout=log, stderr=log,
                                     pass_fds=tuple(passed), start_new_session=True)
            native.close()
            try:
                wait_for(lambda: any(r.get('fixture_ready') for r in records(case / 'events.jsonl')))
                parent.sendall(protocol.encode_packet('request', dict(schema=protocol.SCHEMA,
                    id=uuid.uuid4().hex, session=env['ENACTIVE_COMPUTER_SESSION'], kind='input',
                    expires_ms=int(time.time() * 1000) + 4000,
                    input=dict(type='key', key='RIGHT', modifiers=[]))))
                assert not select.select([parent], [], [], .15)[0], 'Invalid inherited ownership enabled native transport'
                assert not any(r.get('key') == 1073741903 for r in records(case / 'events.jsonl'))
                child.wait(timeout=5)
                assert child.returncode == 0, 'Unowned fixture failed normal execution/exit'
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)
                parent.close()
                os.close(pipe_read)
                os.close(pipe_write)
                invalid_socket.close()
                datagram.close()
        return dict(mode=mode, input_refused=True, normal_exit=child.returncode)


def check(options):
    options.output.mkdir(parents=True, exist_ok=False)
    results = [invalid(options, mode) for mode in (
        'unlocked', 'missing', 'malformed', 'closed', 'nonregular', 'wrong-file', 'socket-missing',
        'socket-file', 'socket-inet', 'socket-datagram', 'legacy-directory', 'legacy-harness')]
    # Both descriptors' CLOEXEC and socket flags are checked by the fixture before
    # SDL_Init. The shell/native child keeps exclusion after the parent copy closes.
    with fixture(options, options.output / 'lifetime', lifetime=2000) as (peer, child):
        peer.observe()
        exclusion(options.output / 'lifetime/user.lock', True)
        peer.channel.close()
        time.sleep(.2)
        assert child.poll() is None
        exclusion(options.output / 'lifetime/user.lock', True)
    (options.output / 'check.json').write_text(json.dumps(dict(passed=True, results=results,
        exclusion_retained_after_parent_and_socket_close=True, released_after_native_exit=True), indent=2) + '\n')


if __name__ == '__main__':
    check(arguments())
