"""Escape attempts run inside the curator sandbox (#451). Prints one JSON object of outcomes.

It reports only whether each attempt succeeded, never what it read, so a failed boundary does
not copy a secret into test output. Arguments: one JSON object naming the targets.
"""
import json
import os
import socket
import subprocess
import sys

targets = json.loads(sys.argv[1])
outcomes = {}


def attempt(name, action):
    try:
        action()
        outcomes[name] = 'allowed'
    except Exception as error:  # noqa: BLE001 - any refusal counts
        outcomes[name] = f'denied:{type(error).__name__}'


def read(path):
    with open(path, 'rb') as stream:
        stream.read(1)


def listing(path):
    os.listdir(path)


def write(path):
    with open(path, 'wb') as stream:
        stream.write(b'x')


def connect(host, port, family=socket.AF_INET):
    with socket.socket(family, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        s.connect((host, port))


def connect_unix(path):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(2)
        s.connect(path)


def udp(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(b'x', (host, port))


def succeeds(argv):
    def run():
        result = subprocess.run(argv, capture_output=True, timeout=10)
        if result.returncode != 0:
            raise PermissionError(f'exit {result.returncode}')
    return run


def signal_other():
    os.kill(targets['other_pid'], 0)


def shared_memory():
    from multiprocessing import shared_memory as shm
    block = shm.SharedMemory(create=True, size=16)
    block.close()
    block.unlink()


def semaphore():
    import multiprocessing
    multiprocessing.Lock()


def terminal(path):
    os.close(os.open(path, os.O_RDONLY | os.O_NONBLOCK))


for name, path in targets.get('stat', {}).items():
    attempt(f'stat {name}', lambda p=path: os.stat(p))
for path in targets.get('terminals', []):
    attempt(f'open terminal {os.path.basename(path)}', lambda p=path: terminal(p))
attempt('posix shared memory', shared_memory)
attempt('posix semaphore', semaphore)
for name, path in targets.get('read', {}).items():
    attempt(f'read {name}', lambda p=path: read(p))
for name, path in targets.get('list', {}).items():
    attempt(f'list {name}', lambda p=path: listing(p))
for name, path in targets.get('write', {}).items():
    attempt(f'write {name}', lambda p=path: write(p))
for name, port in targets.get('tcp', {}).items():
    attempt(f'tcp {name}', lambda p=port: connect('127.0.0.1', p))
    attempt(f'tcp6 {name}', lambda p=port: connect('::1', p, socket.AF_INET6))
for name, port in targets.get('udp', {}).items():
    attempt(f'udp {name}', lambda p=port: udp('127.0.0.1', p))
for name, path in targets.get('unix', {}).items():
    attempt(f'unix {name}', lambda p=path: connect_unix(p))
attempt('external tcp', lambda: connect('1.1.1.1', 443))
attempt('dns', lambda: socket.getaddrinfo('example.com', 443))
attempt('pasteboard', succeeds(['/usr/bin/pbpaste']))
attempt('open application', succeeds(['/usr/bin/open', '-g', '-a', 'Calculator']))
attempt('signal other process', signal_other)
attempt('list processes', succeeds(['/bin/ps', '-ax']))
print(json.dumps(outcomes, sort_keys=True))
