"""Actual independent SDL checks. Run only under the lead's native runtime turn.

This is test-side framing, not another product channel. Python owns canonical JSON;
Foundation's native parser does not independently reject duplicate object keys.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import shlex
import signal
import socket
import struct
import subprocess
import time
import uuid

from harness.computer import protocol


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def wait_for(predicate, seconds=10):
    end = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < end, 'Fixture check timed out'
        time.sleep(.01)


def exclusion(path, held):
    with path.open('a') as candidate:
        try:
            fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            assert held, 'Shared exclusion survived child exit'
        else:
            assert not held, 'Shared exclusion lost while child lives'


class Peer:
    """Bounded fixture reader; deliberately permits partial sends and slow reads."""
    def __init__(self, channel, session, pid):
        self.channel, self.session, self.pid = channel, session, pid
        self.buffer = bytearray()
        self.results = []
        self.target = None

    def request_packet(self, kind, value=None, *, identity=None):
        identity = identity or uuid.uuid4().hex
        value = dict(schema=protocol.SCHEMA, id=identity, session=self.session,
                     kind=kind, expires_ms=int(time.time() * 1000) + 4000, input=value)
        return identity, protocol.encode_packet('request', value)

    def request(self, kind, value=None, *, fragmented=False, identity=None):
        identity, packet = self.request_packet(kind, value, identity=identity)
        if fragmented:
            for position in range(0, len(packet), 3):
                self.channel.sendall(packet[position:position + 3])
                time.sleep(.001)
        else:
            self.channel.sendall(packet)
        return identity

    def packet(self, timeout=10):
        end = time.monotonic() + timeout
        while True:
            if len(self.buffer) >= 4:
                size = struct.unpack('!I', self.buffer[:4])[0]
                assert 1 <= size <= protocol.MAX_HEADER_BYTES
                if len(self.buffer) >= 4 + size:
                    header = protocol.wire_header(protocol.decode_json(bytes(self.buffer[4:4 + size])))
                    total = 4 + size + header['payload_bytes']
                    if len(self.buffer) >= total:
                        png = bytes(self.buffer[4 + size:total])
                        del self.buffer[:total]
                        assert header['kind'] in ('state', 'receipt')
                        value = header['value']
                        if header['kind'] == 'state':
                            protocol.state(value, session=self.session, pid=self.pid)
                            self.target = value
                        else:
                            protocol.receipt(value, identity=value['id'], session=self.session)
                            assert bool(png) == (value['frame'] is not None)
                            if png:
                                assert png.startswith(b'\x89PNG\r\n\x1a\n')
                            self.results.append(value)
                        return header['kind'], value, png
            remaining = end - time.monotonic()
            assert remaining > 0 and select.select([self.channel], [], [], remaining)[0], 'No native packet'
            data = self.channel.recv(16384)
            assert data, 'Native channel closed unexpectedly'
            self.buffer.extend(data)
            assert len(self.buffer) <= protocol.MAX_FRAME_BYTES + protocol.MAX_HEADER_BYTES + 4

    def collect(self, identity):
        while True:
            kind, value, png = self.packet()
            if kind == 'receipt':
                assert value['id'] == identity, ('Receipt order/identity differs', value, identity)
                return value, png

    def execute(self, value=None, *, fragmented=False):
        identity = self.request('observe' if value is None else 'input', value, fragmented=fragmented)
        return self.collect(identity)

    def observe(self):
        # Binding precedes the first present; a no-capture refusal is retained.
        for _ in range(3):
            value, png = self.execute()
            if png:
                return value, png
            time.sleep(.05)
        raise AssertionError('Fixture never supplied a presented capture')


@contextmanager
def fixture(options, case, *, offscreen=False, noise=False, lifetime=8000):
    case.mkdir(parents=True, exist_ok=False)
    shared = (case / 'user.lock').open('a')
    fcntl.flock(shared, fcntl.LOCK_EX | fcntl.LOCK_NB)
    parent, native = socket.socketpair()
    native.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    session = uuid.uuid4().hex
    command = [str(options.fixture), str(case / 'events.jsonl'), '--hidden',
               '--exit-after-ms', str(lifetime), '--check-fd', str(shared.fileno()),
               '--check-fd', str(native.fileno()), '--check-socket', str(native.fileno())]
    if offscreen:
        command.append('--offscreen')
    if noise:
        command.append('--noise')
    script = case / 'launch.sh'
    script.write_text('export DYLD_INSERT_LIBRARIES="$ENACTIVE_COMPUTER_LIBRARY"\nexec ' + shlex.join(command) + '\n')
    env = dict(PATH=os.environ['PATH'], LANG='en_US.UTF-8',
               ENACTIVE_COMPUTER_LIBRARY=str(options.library),
               DYLD_FRAMEWORK_PATH=str(options.resources), DYLD_LIBRARY_PATH=str(options.resources),
               ENACTIVE_COMPUTER_FD=str(native.fileno()), ENACTIVE_COMPUTER_SESSION=session,
               ENACTIVE_COMPUTER_LOCK_FD=str(shared.fileno()), ENACTIVE_COMPUTER_LOCK_FILE=str(case / 'user.lock'),
               SDL_MAC_BACKGROUND_APP='1', SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN='1')
    console = (case / 'console.log').open('x')
    child = subprocess.Popen(['/bin/sh', str(script)], env=env, stdout=console, stderr=console,
                             pass_fds=(shared.fileno(), native.fileno()), start_new_session=True)
    native.close()
    peer = Peer(parent, session, child.pid)
    try:
        wait_for(lambda: any(r.get('fixture_ready') for r in records(case / 'events.jsonl')))
        shared.close()
        exclusion(case / 'user.lock', True)
        yield peer, child
        child.wait(timeout=lifetime / 1000 + 5)
        assert child.returncode == 0, ('Fixture did not exit normally', child.returncode)
    finally:
        parent.close()
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        shared.close()
        console.close()
        exclusion(case / 'user.lock', False)


def key(name, modifiers=None):
    return dict(type='key', key=name, modifiers=modifiers or [])


def click(frame):
    return dict(type='click', x=200, y=180, button='left',
                geometry={k: frame[k] for k in protocol.GEOMETRY_KEYS})


def mechanics(options, *, offscreen, terminal):
    case = options.output / ('offscreen-' if offscreen else 'default-') / terminal
    with fixture(options, case, offscreen=offscreen) as (peer, child):
        first, before = peer.observe()
        for action in (key('a'), dict(type='text', text='hé✓'), key('a', ['SHIFT'])):
            value, _ = peer.execute(action, fragmented=True)
            assert value['disposition'] == 'delivered', value
        value, _ = peer.execute(click(first['frame']))
        assert value['disposition'] == 'delivered', value
        peer.execute(key('r'))
        wait_for(lambda: any(r.get('window_event') == 6 for r in records(case / 'events.jsonl')))
        resized, image = peer.observe()
        assert resized['frame']['width'] == 800 and image != before
        stale, _ = peer.execute(click(first['frame']))
        assert stale['disposition'] == 'rejected' and stale['emitted_events'] == 0, stale
        current, _ = peer.execute(click(resized['frame']))
        assert current['disposition'] == 'delivered', current
        _, image2 = peer.observe()
        _, image3 = peer.observe()
        assert hashlib.sha256(image2).digest() == hashlib.sha256(image3).digest(), 'Unchanged pixels must remain observable'
        value, _ = peer.execute(key('d' if terminal == 'target-loss' else 't'))
        assert value['disposition'] == 'partial', value
        stopped, _ = peer.observe()
        while not peer.target or not peer.target['paused']:
            peer.packet()
        assert peer.target['takeover_generation'] == (terminal == 'takeover')
        refused, _ = peer.execute(key('RIGHT'))
        assert refused['disposition'] == 'rejected' and refused['emitted_events'] == 0
        if terminal == 'target-loss':
            again, _ = peer.observe()
            assert again['frame']['capture_id'] == stopped['frame']['capture_id'], 'Replacement target captured'
        entries = records(case / 'events.jsonl')
        texts = [r.get('text') for r in entries if r['type'] == 771]
        assert 'a' in texts and 'hé✓' in texts and 'A' in texts, texts
        clicks = [r for r in entries if r['type'] in (1025, 1026)]
        assert len(clicks) == 4 and all(r['position'] == [200, 180] for r in clicks)
        assert all(a['drain'] != b['drain'] for a, b in zip(clicks[::2], clicks[1::2]))
        assert clicks[0]['buttons'] & 1 and not clicks[1]['buttons'] & 1
        if offscreen:
            assert all(r['offscreen'] for r in clicks)
        if terminal == 'takeover':
            assert any(r.get('key') == 1073741882 for r in entries), 'Unowned physical queue event was lost'
        (case / 'check.json').write_text(json.dumps(dict(results=peer.results, stopped=peer.target), indent=2) + '\n')


def partial_control_checks(options):
    """Fence before the first stage; this does not qualify mid-held-key timing."""
    for prefix in ('length', 'json'):
        for completion in ('pause', 'eof'):
            case = options.output / ('partial-' + prefix + '-' + completion)
            with fixture(options, case, lifetime=3500) as (peer, child):
                peer.observe()
                # Stop exactly this owned independent fixture, confirm the stop,
                # and place both packets before the next native callback. This
                # avoids assuming a sleep can catch a particular event stage.
                try:
                    os.kill(child.pid, signal.SIGSTOP)
                    pid, status = os.waitpid(child.pid, os.WUNTRACED)
                    assert pid == child.pid and os.WIFSTOPPED(status), 'Fixture stop was not confirmed'
                    baseline = max((r.get('heartbeat', 0) for r in records(case / 'events.jsonl')), default=0)
                    original, command = peer.request_packet('input', key('a', ['CTRL']))
                    pause, packet = peer.request_packet('pause')
                    split = 2 if prefix == 'length' else len(packet) - 1
                    peer.channel.sendall(command + packet[:split])
                finally:
                    # Resume even when setup/assertion fails: fixture cleanup must
                    # be able to terminate/reap the exact child without a stop.
                    if child.poll() is None:
                        os.kill(child.pid, signal.SIGCONT)
                wait_for(lambda: max((r.get('heartbeat', 0) for r in records(case / 'events.jsonl')), default=0) >= baseline + 30)
                entries = records(case / 'events.jsonl')
                assert not any(r['type'] in (768, 769, 771) for r in entries), 'Partial control packet permitted command events'
                assert child.poll() is None, 'Partial control packet blocked normal fixture execution'
                if completion == 'pause':
                    peer.channel.sendall(packet[split:])
                else:
                    peer.channel.shutdown(socket.SHUT_WR)
                result, _ = peer.collect(original)
                assert result['disposition'] == 'rejected' and result['emitted_events'] == 0, result
                if completion == 'pause':
                    ack, _ = peer.collect(pause)
                    assert ack['disposition'] == 'delivered', ack
                while not peer.target or not peer.target['paused']:
                    peer.packet()
                assert not any(r['type'] in (768, 769, 771) for r in records(case / 'events.jsonl'))
                (case / 'check.json').write_text(json.dumps(dict(results=peer.results,
                    stopped=peer.target, prefix=prefix, completion=completion,
                    scope='Partial control bytes fence before first command stage; not mid-held-key timing'), indent=2) + '\n')


def channel_checks(options):
    partial_control_checks(options)
    case = options.output / 'backpressure'
    with fixture(options, case, noise=True, lifetime=12000) as (peer, child):
        first, initial_png = peer.observe()
        # Drain the first capture's passive state before witnessing the next
        # receipt header with MSG_PEEK. The image stays entirely unread below.
        while not peer.target or peer.target['latest_frame'] != first['frame']:
            peer.packet()
        original = peer.request('observe', fragmented=True)
        witness = {}

        def pending_image():
            if not select.select([peer.channel], [], [], 0)[0]:
                return False
            data = peer.channel.recv(protocol.MAX_HEADER_BYTES + 4, socket.MSG_PEEK)
            assert data, 'Fixture channel closed before pending image witness'
            if len(data) < 4:
                return False
            size = struct.unpack('!I', data[:4])[0]
            assert 1 <= size <= protocol.MAX_HEADER_BYTES
            if len(data) < 4 + size:
                return False
            header = protocol.wire_header(protocol.decode_json(data[4:4 + size]))
            assert header['kind'] == 'receipt' and header['value']['id'] == original, header
            assert header['payload_bytes'] > 262144, 'Image did not exceed the constrained send buffer'
            witness.update(header)
            return True

        wait_for(pending_image)
        pause_wall = int(time.time() * 1000)
        pause = peer.request('pause', fragmented=True)
        before = max((r.get('heartbeat', 0) for r in records(case / 'events.jsonl')), default=0)
        # No socket receive/collection occurs until an actual later loop witness.
        # This is a finite liveness check, not a cadence/performance threshold.
        wait_for(lambda: max((r.get('heartbeat', 0) for r in records(case / 'events.jsonl')), default=0) > before)
        after = max((r.get('heartbeat', 0) for r in records(case / 'events.jsonl')), default=0)
        assert child.poll() is None, 'Fixture ended before pending image collection'
        result, png = peer.collect(original)
        assert result == witness['value'] and len(png) == witness['payload_bytes'], 'Pending receipt/image changed'
        assert hashlib.sha256(png).digest() == hashlib.sha256(initial_png).digest(), 'Pending image bytes changed'
        assert result['disposition'] == 'delivered' and len(png) > 262144, 'Did not exercise partial image send'
        assert result['frame']['presented_ms'] <= pause_wall, 'Pending frame timestamp was renewed'
        ack, _ = peer.collect(pause)
        assert ack['disposition'] == 'delivered'
        refused, _ = peer.execute(key('RIGHT'))
        assert refused['disposition'] == 'rejected' and refused['emitted_events'] == 0
        assert not any(r.get('key') == 1073741903 for r in records(case / 'events.jsonl'))
        (case / 'check.json').write_text(json.dumps(dict(original=result, pause=ack, refused=refused,
            heartbeat_before=before, heartbeat_after=after, payload_bytes=len(png),
            payload_sha256=hashlib.sha256(png).hexdigest()), indent=2) + '\n')
    case = options.output / 'half-close'
    with fixture(options, case, lifetime=2500) as (peer, child):
        peer.observe()
        original = peer.request('input', key('a', ['CTRL']))
        peer.channel.shutdown(socket.SHUT_WR)
        result, _ = peer.collect(original)
        assert result['disposition'] in ('rejected', 'partial'), result
        time.sleep(.3)
        assert child.poll() is None and any('heartbeat' in r for r in records(case / 'events.jsonl'))
    case = options.output / 'peer-close'
    with fixture(options, case, noise=True, lifetime=12000) as (peer, child):
        peer.observe()
        peer.request('observe')
        peer.channel.close()
        before = max((r.get('heartbeat', 0) for r in records(case / 'events.jsonl')), default=0)
        wait_for(lambda: max((r.get('heartbeat', 0) for r in records(case / 'events.jsonl')), default=0) > before)
        assert child.poll() is None, 'Fixture ended before peer-close loop witness'
    case = options.output / 'duplicate'
    with fixture(options, case, lifetime=2500) as (peer, child):
        peer.observe()
        original = peer.request('input', key('a'))
        peer.collect(original)
        peer.request('input', key('RIGHT'), identity=original)
        while not peer.target or not peer.target['paused']:
            peer.packet()
        assert 'Duplicate' in peer.target['error']
        time.sleep(.2)
        assert not any(r.get('key') == 1073741903 for r in records(case / 'events.jsonl'))
        assert sum(r['id'] == original for r in peer.results) == 1


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'library', 'resources', 'output'):
        parser.add_argument('--' + name, type=lambda p: Path(p).resolve(), required=True)
    return parser.parse_args()


def check(options):
    options.output.mkdir(parents=True, exist_ok=False)
    for offscreen in (False, True):
        for terminal in ('takeover', 'target-loss'):
            mechanics(options, offscreen=offscreen, terminal=terminal)
    channel_checks(options)
    (options.output / 'check.json').write_text(json.dumps(dict(passed=True,
        scope='Actual independent SDL; synthetic unowned takeover, not real human/game qualification'), indent=2) + '\n')


if __name__ == '__main__':
    check(arguments())
