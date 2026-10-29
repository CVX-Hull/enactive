"""Single bounded writer for the isolated mechanical candidate."""
from __future__ import annotations

from typing import Any

from collections.abc import Callable
import copy
import fcntl
import hashlib
import os
from pathlib import Path
import re
import threading
import time
import uuid

from .protocol import (ControlError, GEOMETRY_KEYS, MAX_FRAME_BYTES, SCHEMA, canonical,
                       closed, finite_seconds, integer, read_json, receipt, state, validate_input)


class OperationExpired(ControlError):
    """Known local truncation, distinct from uncertain published input."""


def atomic(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    with temporary.open('x') as stream:
        stream.write(canonical(value) + '\n')
    os.replace(temporary, path)


class ComputerClient:
    def __init__(self, run: Path, *, clock: Callable[[], float] = time.monotonic, wall: Callable[[], float] = time.time) -> None:
        self.run = run.resolve(strict=True)
        self.config = read_json(self.run / 'control.json')
        closed(self.config, {'schema', 'session', 'pid', 'deadline_monotonic', 'max_inputs', 'max_requests', 'max_frames', 'max_bytes'})
        if self.config['schema'] != 'computer-run/1' or re.fullmatch('[0-9a-f]{32}', self.config['session']) is None:
            raise ControlError('Unsupported fresh run contract')
        integer(self.config['pid'], 1, 2**31 - 1)
        finite_seconds(self.config['deadline_monotonic'], 1e12)
        for field in ('max_inputs', 'max_requests', 'max_frames', 'max_bytes'):
            integer(self.config[field], 1, 2**40)
        self.directory = self.run / 'bridge'
        if self.directory.is_symlink() or not self.directory.is_dir():
            raise ControlError('Invalid owned bridge directory')
        self.session, self.pid = self.config['session'], self.config['pid']
        self.deadline = self.config['deadline_monotonic']
        self.clock, self.wall = clock, wall
        self.lock = (self.run / 'writer.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # A restart cannot renew counters or recover input authority.
            with (self.run / 'writer-started').open('x'):
                pass
        except BaseException:
            self.lock.close()
            raise
        self.serial = threading.Lock()
        self.stopped = threading.Event()
        self.inputs = self.requests = self.frames = self.bytes = 0
        self.captures = {}

    def close(self) -> None:
        self.stop('Writer closed; no rearm')
        self.lock.close()

    def stop(self, reason: str) -> dict[str, Any]:
        try:
            (self.directory / 'pause').touch()
        finally:
            self.stopped.set()
        self._event('stop', reason=reason)
        return {'paused': True, 'reason': reason, 'grants_authority': False}

    def _event(self, kind, **value):
        with (self.run / 'client.jsonl').open('a') as stream:
            stream.write(canonical(dict(type=kind, monotonic=self.clock(), wall_time=self.wall(), **value)) + '\n')

    def target(self) -> dict[str, Any]:
        return state(read_json(self.directory / 'state.json'), session=self.session, pid=self.pid)

    def remaining(self) -> dict[str, int | float]:
        return dict(seconds=max(0, self.deadline - self.clock()),
                    inputs=max(0, self.config['max_inputs'] - self.inputs),
                    requests=max(0, self.config['max_requests'] - self.requests),
                    frames=max(0, self.config['max_frames'] - self.frames),
                    frame_bytes=max(0, self.config['max_bytes'] - self.bytes))

    def _guard(self, *, input_needed=False):
        now = self.clock()
        if now >= self.deadline:
            self.stop('Original deadline exhausted')
            raise ControlError('Original deadline exhausted')
        try:
            target = self.target()
        except (OSError, ValueError):
            self.stop('Target identity/integrity unavailable')
            raise
        if target['window_id'] == 0 or input_needed and target['error']:
            raise ControlError('Target unavailable: ' + target['error'])
        if input_needed and (self.stopped.is_set() or (self.directory / 'pause').exists() or target['paused']):
            raise ControlError('Input paused; no automatic rearm')
        return target

    def _frame(self, metadata):
        try:
            return self._read_frame(metadata)
        except (OSError, ValueError):
            self.stop("Capture integrity/storage failed; no further input")
            raise

    def _read_frame(self, metadata):
        path = self.directory / metadata['name']
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FRAME_BYTES:
            raise ControlError('Invalid retained frame')
        data = path.read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ControlError('Invalid PNG signature')
        prior = self.captures.get(metadata['capture_id'])
        identity = hashlib.sha256(data).hexdigest()
        if prior is not None and prior != (metadata, identity):
            raise ControlError('Immutable capture identity changed')
        if prior is None:
            if self.frames >= self.config['max_frames'] or self.bytes + len(data) > self.config['max_bytes']:
                self.stop('Original frame capacity exhausted')
                raise ControlError('Original frame capacity exhausted')
            self.captures[metadata['capture_id']] = (copy.deepcopy(metadata), identity)
            self.frames += 1
            self.bytes += len(data)
        return data

    def _send(self, kind, value, deadline):
        self._guard(input_needed=kind == 'input')
        if kind == 'observe' and (self.frames >= self.config['max_frames']
                or self.bytes + MAX_FRAME_BYTES > self.config['max_bytes']):
            self.stop('Original capture reservation exhausted')
            raise ControlError('Original capture reservation exhausted')
        if self.clock() >= deadline:
            raise OperationExpired('Original operation deadline exhausted')
        identity = uuid.uuid4().hex
        packet = dict(schema=SCHEMA, id=identity, session=self.session, kind=kind,
                      expires_ms=int((self.wall() + min(5., deadline - self.clock())) * 1000), input=value)
        # No file is overwritten or replayed; one exact request is outstanding.
        if any((self.directory / n).exists() for n in ('request.json', 'claimed.json')):
            self.stop('Outstanding native delivery; no replay')
            raise ControlError('Outstanding native delivery; no replay')
        self._event('native-intent', request=packet)
        atomic(self.directory / 'request.json', packet)
        result_path = self.directory / 'receipts' / (identity + '.json')
        try:
            while self.clock() < deadline:
                if result_path.exists():
                    value = receipt(read_json(result_path), identity=identity, session=self.session)
                    self._event('native-receipt', result=value)
                    # Publication precedes native retirement by a few instructions.
                    # Keep the exact known ACK and await that bounded handoff.
                    while (self.directory / 'claimed.json').exists() and self.clock() < deadline:
                        time.sleep(.001)
                    if (self.directory / 'claimed.json').exists():
                        self.stop('Known ACK retained but native claim retirement failed')
                    if value['disposition'] in ('partial', 'unknown'):
                        self.stop('Partial/unknown delivery; collect only')
                    return value
                if self.stopped.is_set():
                    break
                time.sleep(.01)
        except BaseException:
            self.stop('Native delivery collection failed; effect unknown')
            raise
        self.stop('Native receipt timeout; effect unknown; never replay')
        return dict(schema='computer-transport/1', id=identity, session=self.session,
                    disposition='unknown', emitted_events=None, reason='No terminal receipt; emitted count unknown', frame=None)

    def result(self, operation_id: str) -> tuple[dict[str, Any], bytes | None]:
        if not isinstance(operation_id, str) or re.fullmatch('[0-9a-f]{32}', operation_id) is None:
            raise ControlError('Invalid original operation ID')
        path = self.run / 'operations' / (operation_id + '.json')
        if not path.exists():
            raise ControlError('Unknown original operation; no input submitted')
        try:
            value = read_json(path, maximum=262144)
        except (OSError, ValueError):
            self.stop('Original operation storage/integrity unavailable')
            raise
        late = []
        for item in value.get('receipts', []):
            if item.get('schema') == 'computer-transport/1':
                path = self.directory / 'receipts' / (item['id'] + '.json')
                if path.exists():
                    late.append(receipt(read_json(path), identity=item['id'], session=self.session))
        if late:
            value = dict(value, collected_native_receipts=late, input_authority_restored=False)
        return value, self._frame(value['capture']) if value.get('capture') is not None else None

    def _wait(self, seconds, deadline):
        end = self.clock() + seconds
        if end > deadline:
            raise OperationExpired('Requested wait does not fit original operation deadline')
        while self.clock() < end:
            self._guard(input_needed=True)
            time.sleep(min(.02, end - self.clock()))

    def execute(self, actions: object = None, *, capture_id: int | None = None, observe: bool = False) -> tuple[dict[str, Any], bytes | None]:
        # Validate the entire sequence before its first effect.
        if observe:
            prepared = []
        else:
            if type(actions) is not list or not 1 <= len(actions) <= 32:
                raise ControlError('Choose 1..32 basic operations')
            prepared = copy.deepcopy(actions)
            for action in prepared:
                if type(action) is dict and action.get('type') == 'wait':
                    if set(action) != {'type', 'seconds'}:
                        raise ControlError('Invalid wait fields')
                    finite_seconds(action['seconds'], 2)
                else:
                    if isinstance(action, dict) and action.get('type') == 'click':
                        if set(action) != {'type', 'x', 'y', 'button'} or capture_id not in self.captures:
                            raise ControlError('Pointer input requires its explicitly returned capture and fields')
                        action['geometry'] = {k: self.captures[capture_id][0][k] for k in GEOMETRY_KEYS}
                    validate_input(action)
            if sum(a['seconds'] for a in prepared if a['type'] == 'wait') > 15:
                raise ControlError('Sequence waits exceed15-second original operation bound')
        with self.serial:
            self._guard(input_needed=not observe)
            if self.requests >= self.config['max_requests']:
                self.stop('Original request capacity exhausted')
                raise ControlError('Original request capacity exhausted')
            needed = sum(a['type'] != 'wait' for a in prepared)
            if self.inputs + needed > self.config['max_inputs']:
                raise ControlError('Sequence exceeds remaining original input capacity')
            self.requests += 1
            operation = uuid.uuid4().hex
            result = dict(operation_id=operation, status='in_progress', receipts=[], remaining=self.remaining())
            path = self.run / 'operations' / (operation + '.json')
            try:
                atomic(path, result)
            except (OSError, ValueError):
                self.stop('Original operation record failed before input')
                raise
            deadline = min(self.deadline, self.clock() + 15.)
            png = None
            try:
                for action in prepared:
                    self._guard(input_needed=True)
                    if action['type'] == 'wait':
                        self._wait(action['seconds'], deadline)
                    else:
                        # A published uncertain delivery remains charged.
                        self.inputs += 1
                        reply = self._send('input', action, deadline)
                        result['receipts'].append(reply)
                        if reply['disposition'] != 'delivered':
                            result['status'] = 'unknown' if reply['disposition'] in ('unknown', 'partial') else 'refused'
                            break
                else:
                    result['status'] = 'completed'
                # Observation is a separate basic operation, not an effect verdict.
                if self.clock() < deadline:
                    reply = self._send('observe', None, deadline)
                    result['capture_receipt'] = reply
                    if reply['disposition'] != 'delivered':
                        result['status'] = 'unknown' if reply['disposition'] in ('unknown', 'partial') else 'refused'
                    if reply['frame'] is not None:
                        png = self._frame(reply['frame'])
                        result['capture'] = reply['frame']
                result['target'] = self.target()
            except OperationExpired as exc:
                result.update(status='partial', reason=str(exc))
            except BaseException as exc:
                self.stop('Operation interrupted or failed; retain original result')
                result.update(status='unknown', error=type(exc).__name__ + ': ' + str(exc)[:500])
                if not isinstance(exc, Exception):
                    raise
            finally:
                result['remaining'] = self.remaining()
                atomic(path, result)
                atomic(self.run / 'status.json', result)
                self._event('operation', result=result)
            return result, png
