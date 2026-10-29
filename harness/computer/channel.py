"""One owned native socket, bounded packet collection and independent stop.

The receive thread never publishes files or touches SQLite. Native SDL callbacks
therefore do not wait on the custodian's evidence storage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import select
import re
import socket
import struct
import threading
import time
from typing import Any
import uuid

from .protocol import (ControlError, NoDispatch, MAX_FRAME_BYTES, MAX_HEADER_BYTES, SCHEMA,
                       decode_json, encode_packet, receipt, state, wire_header)


@dataclass
class _Pending:
    reply: dict[str, Any] | None = None
    png: bytes | None = None
    timing: dict[str, float] = field(default_factory=dict)


class NativeChannel:
    """A normal request plus one independent, permanent Pause request.

    Unknown delivery retains its slot for late original collection. No reconnect,
    replay or new native writer is supported.
    """

    def __init__(self, connection: socket.socket, session: str, pid: int) -> None:
        self.connection = connection
        self.connection.setblocking(False)
        self.session, self.pid = session, pid
        self.stopped = threading.Event()
        self.closed = threading.Event()
        self._write_closed = threading.Event()
        self._condition = threading.Condition()
        self._send_lock = threading.Lock()
        self._pending: dict[str, _Pending] = {}
        self._normal: str | None = None
        self._pause_id: str | None = None
        self._target: dict[str, Any] | None = None
        self._fault: str | None = None
        self.stop_reason: str | None = None
        self._reader = threading.Thread(target=self._receive, name='native-pixels', daemon=True)
        self._reader.start()

    def target(self) -> dict[str, Any] | None:
        with self._condition:
            return self._target.copy() if self._target is not None else None

    @property
    def fault(self) -> str | None:
        with self._condition:
            return self._fault

    def _send(self, data: bytes, deadline: float, *, pause: bool = False) -> None:
        remaining = max(0., deadline - time.monotonic())
        if not self._send_lock.acquire(timeout=remaining):
            raise TimeoutError('Native sender is busy')
        offset = 0
        try:
            if self._write_closed.is_set():
                raise NoDispatch('Native write half already closed')
            if self.stopped.is_set() and not pause:
                raise NoDispatch('Stop preceded native publication')
            while offset < len(data):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Original native publication deadline exhausted')
                try:
                    count = self.connection.send(memoryview(data)[offset:])
                    if count == 0:
                        raise ConnectionError('Native channel closed during publication')
                    offset += count
                except BlockingIOError:
                    select.select([], [self.connection], [], min(.05, remaining))
        except BaseException:
            if offset:
                # Once a frame has begun, no second header may be appended.
                # Do this before releasing the writer lock, including on cancel.
                self._write_half_close()
            raise
        finally:
            self._send_lock.release()

    def _write_half_close(self) -> None:
        self._write_closed.set()
        try:
            self.connection.shutdown(socket.SHUT_WR)
        except OSError:
            pass

    def stop(self, reason: str) -> dict[str, Any]:
        """Fence first; never wait on the executor, evidence store or reader."""
        self.stopped.set()
        with self._condition:
            if self.stop_reason is None:
                self.stop_reason = reason[:600]
            if self._pause_id is not None or self.closed.is_set():
                return self.stop_status()
            identity = self._pause_id = uuid.uuid4().hex
            self._pending[identity] = _Pending()
            self._condition.notify_all()
        packet = dict(schema=SCHEMA, id=identity, session=self.session,
                      kind='pause', expires_ms=int(time.time() * 1000) + 5000, input=None)
        try:
            self._send(encode_packet('request', packet), time.monotonic() + .25, pause=True)
        except (OSError, TimeoutError, ValueError):
            # This also terminates a partially written original frame. Inserting
            # another packet into that frame would corrupt command correlation.
            self._write_half_close()
        return self.stop_status()

    def stop_status(self) -> dict[str, Any]:
        with self._condition:
            return dict(stop_requested=self.stopped.is_set(),
                        native_pause_confirmed=bool(self._target and self._target['paused']),
                        reason=self.stop_reason, grants_authority=False)

    def _fail(self, reason: str) -> None:
        with self._condition:
            if self._fault is None:
                self._fault = reason[:600]
            self._condition.notify_all()
        self.stop(reason)

    def request(self, kind: str, value: dict[str, Any] | None, deadline: float,
                identity: str) -> tuple[dict[str, Any], bytes | None]:
        with self._condition:
            if self.stopped.is_set() or self.closed.is_set() or self._fault is not None:
                raise NoDispatch('Native input fenced; original collection only')
            if time.monotonic() >= deadline:
                raise NoDispatch('Original deadline expired before native publication')
            if self._normal is not None or identity in self._pending:
                raise NoDispatch('Original native request remains outstanding')
            self._normal = identity
            pending = self._pending[identity] = _Pending()
        packet = dict(schema=SCHEMA, id=identity, session=self.session, kind=kind,
                      expires_ms=int((time.time() + max(0., min(5., deadline - time.monotonic()))) * 1000),
                      input=value)
        try:
            pending.timing.update(send_started_wall=time.time(),send_started_monotonic=time.monotonic())
            self._send(encode_packet('request', packet), deadline)
            pending.timing.update(send_finished_wall=time.time(),send_finished_monotonic=time.monotonic())
            with self._condition:
                while pending.reply is None and not self.stopped.is_set() and self._fault is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._condition.wait(min(.05, remaining))
                if pending.reply is not None:
                    return pending.reply, pending.png
        except NoDispatch:
            with self._condition:
                self._pending.pop(identity, None)
                self._normal = None
            raise
        except (OSError, TimeoutError, ValueError) as exc:
            self._fail('Native publication/collection failed: ' + type(exc).__name__)
        self.stop('Native delivery unresolved; original collection only')
        return dict(schema='computer-transport/2', id=identity, session=self.session,
                    disposition='unknown', emitted_events=None,
                    reason=self.fault or self.stop_reason or 'Original native receipt deadline exhausted',
                    frame=None), None

    def collect(self, identity: str) -> tuple[dict[str, Any], bytes | None] | None:
        with self._condition:
            pending = self._pending.get(identity)
            if pending is None or pending.reply is None:
                return None
            return pending.reply, pending.png

    def timing(self, identity: str) -> dict[str, float]:
        with self._condition:
            pending=self._pending.get(identity)
            return pending.timing.copy() if pending else {}

    def release(self, identity: str) -> None:
        """Release only a terminal receipt already retained by the session store."""
        with self._condition:
            pending = self._pending.get(identity)
            if pending is None or pending.reply is None:
                raise ControlError('Cannot discard unresolved native delivery')
            if identity == self._pause_id:
                return
            del self._pending[identity]
            if self._normal == identity:
                self._normal = None

    def _accept(self, header: dict[str, Any], png: bytes, received_wall: float, received_monotonic: float) -> None:
        kind, value = header['kind'], header['value']
        if kind == 'state':
            value = state(value, session=self.session, pid=self.pid)
            with self._condition:
                self._target = value
                if value['paused']:
                    self.stopped.set()
                    self.stop_reason = self.stop_reason or value['error'] or 'Native Pause'
                self._condition.notify_all()
            return
        if kind != 'receipt':
            raise ControlError('Native sent an unexpected request packet')
        identity = value.get('id')
        if not isinstance(identity, str) or re.fullmatch('[0-9a-f]{32}', identity) is None:
            raise ControlError('Native receipt has no valid original ID')
        value = receipt(value, identity=identity, session=self.session)
        if bool(value['frame']) != bool(png):
            raise ControlError('Native capture receipt/image differs')
        if png and not png.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ControlError('Native image is not PNG')
        with self._condition:
            if identity == self._pause_id and (png or value['emitted_events'] != 0):
                raise ControlError('Pause receipt cannot carry a capture or game events')
            pending = self._pending.get(identity)
            if pending is None or pending.reply is not None:
                raise ControlError('Native receipt is unsolicited or repeated')
            pending.reply, pending.png = value, png or None
            pending.timing.update(receipt_received_wall=received_wall,receipt_received_monotonic=received_monotonic)
            if value['disposition'] in ('partial', 'unknown'):
                self.stopped.set()
                self.stop_reason = self.stop_reason or value['reason']
            self._condition.notify_all()

    def _receive(self) -> None:
        buffer = bytearray()
        header = None
        try:
            while not self.closed.is_set():
                ready, _, _ = select.select([self.connection], [], [], .1)
                if not ready:
                    continue
                try:
                    chunk = self.connection.recv(65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    raise ConnectionError('Native channel EOF')
                buffer.extend(chunk)
                if len(buffer) > MAX_FRAME_BYTES + MAX_HEADER_BYTES + 65540:
                    raise ControlError('Native receive byte capacity exceeded')
                while True:
                    if header is None:
                        if len(buffer) < 4:
                            break
                        length = struct.unpack('!I', buffer[:4])[0]
                        if not 1 <= length <= MAX_HEADER_BYTES:
                            raise ControlError('Native header length outside bound')
                        if len(buffer) < 4 + length:
                            break
                        header = wire_header(decode_json(bytes(buffer[4:4 + length])))
                        del buffer[:4 + length]
                    length = header['payload_bytes']
                    if len(buffer) < length:
                        break
                    png = bytes(buffer[:length])
                    del buffer[:length]
                    self._accept(header, png, time.time(), time.monotonic())
                    header = None
        except (OSError, ValueError) as exc:
            if not self.closed.is_set():
                self._fail('Native receive failed: ' + str(exc)[:400])
        finally:
            with self._condition:
                self._condition.notify_all()

    def close(self) -> None:
        self.stop('Custodian closed; no rearm')
        self.closed.set()
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.connection.close()
        if threading.current_thread() is not self._reader:
            self._reader.join(1.)
