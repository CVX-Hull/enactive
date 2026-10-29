"""Serialized basic control, original receipts and ephemeral actor custody."""
from __future__ import annotations

import copy
import hashlib
import hmac
import math
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from typing import Any
import uuid

from .channel import NativeChannel
from .protocol import ControlError, NoDispatch, GEOMETRY_KEYS, MAX_FRAME_BYTES, validate_actions
from .store import SessionStore


class OperationExpired(ControlError):
    pass


def request_identity(value: str | None) -> str:
    if value is None:
        return uuid.uuid4().hex
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ControlError('Operation ID must be32 lowercase hexadecimal characters')
    return value


class ComputerRuntime:
    """No game interpretation, recovery phases, restored custody or semantic veto."""

    def __init__(self, directory: Path, session: str, channel: NativeChannel,
                 process: Any, deadline: float, limits: dict[str, int], *, max_actors: int = 2) -> None:
        self.directory, self.session = directory, session
        self.channel, self.process, self.deadline = channel, process, deadline
        self.limits, self.max_actors = limits.copy(), max_actors
        self.store = SessionStore(directory, session, limits, deadline)
        self.serial = threading.RLock()
        self._custody = threading.RLock()
        self._actors: dict[str, dict[str, Any]] = {}
        self._counts = self.store.counts()
        self._last: dict[str, Any] | None = None
        self._latest_source: dict[str, Any] | None = None
        self._handoffs: dict[str, dict[str, Any]] = {}
        self._closed = False

    def add_actor(self) -> dict[str, str]:
        with self.serial:
            if self.channel.stopped.is_set() or time.monotonic() >= self.deadline:
                raise ControlError('Stopped run cannot mint actor custody')
            if len(self._actors) >= self.max_actors or any(v['stage'] != 'quiescent' for v in self._actors.values()):
                raise ControlError('Prior actor is not quiescent or original actor capacity exhausted')
            identity, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            self.store.add_actor(identity, digest)
            with self._custody:
                self._actors[identity] = dict(token_hash=digest, stage='active')
            return dict(actor_id=identity, token=token)

    def authorize(self, token: str, *, write: bool = False) -> str:
        if not isinstance(token, str) or len(token) > 256:
            raise ControlError('Actor capability unavailable')
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._custody:
            for identity, actor in self._actors.items():
                if hmac.compare_digest(digest, actor['token_hash']):
                    if write and actor['stage'] != 'active':
                        raise ControlError('Actor sealed; original collection/read only')
                    return identity
        raise ControlError('Unknown ephemeral actor capability')

    def actor_stage(self, actor_id: str) -> str | None:
        with self._custody:
            return self._actors.get(actor_id, {}).get('stage')

    def remaining(self) -> dict[str, int | float]:
        counts = self._counts.copy()
        return dict(custodian_seconds=max(0., self.deadline - time.monotonic()),
                    inputs=max(0, self.limits['max_inputs'] - counts['inputs']),
                    requests=max(0, self.limits['max_requests'] - counts['requests']),
                    frames=max(0, self.limits['max_frames'] - counts['frames']),
                    frame_bytes=max(0, self.limits['max_bytes'] - counts['frame_bytes']))

    def status(self) -> dict[str, Any]:
        with self._custody:
            actors = [dict(actor_id=k, stage=v['stage']) for k, v in self._actors.items()]
        return dict(schema='computer-status/1', session=self.session, target=self.channel.target(),
                    stop=self.channel.stop_status(), remaining=self.remaining(), actors=actors,
                    last_operation=copy.deepcopy(self._last), latest_source=copy.deepcopy(self._latest_source),
                    native_returncode=self.process.poll())

    def _guard(self, actor_id: str) -> None:
        if self.actor_stage(actor_id) != 'active':
            raise ControlError('Actor is not the active writer')
        if self.channel.stopped.is_set() or self.channel.fault is not None:
            raise ControlError('Input fenced; original collection only')
        if time.monotonic() >= self.deadline:
            self.stop('Original custodian deadline exhausted')
            raise ControlError('Original custodian deadline exhausted')
        if self.process.poll() is not None:
            self.stop('Owned native child exited')
            raise ControlError('Owned native child exited')
        target = self.channel.target()
        if target is None or target['window_id'] == 0 or target['paused']:
            raise ControlError('Owned mechanical target is not available')

    def stop(self, reason: str = 'Operator Pause') -> dict[str, Any]:
        return self.channel.stop(reason)

    def stop_actor(self, token: str, reason: str) -> dict[str, Any]:
        # A lost handoff response/cancel must still fence the currently sealed
        # actor. A retired actor cannot revoke its successor. This arbitration
        # shares the custody lock with the transition to quiescence, but never
        # waits for the executor, application or database lock to request Stop.
        with self._custody:
            actor_id=self.authorize(token)
            if self._actors[actor_id]['stage'] not in ('active','sealed'):
                raise ControlError('Retired actor cannot stop a successor')
            return self.stop(reason)

    def source(self, source_id: str) -> tuple[dict[str, Any], bytes]:
        if not isinstance(source_id, str) or not self.store.has_source(source_id):
            raise ControlError('Unknown retained source')
        try:
            return self.store.read_source(source_id)
        except (OSError, ValueError):
            self.stop('Retained current source integrity/storage failed')
            raise

    def _capture(self, frame: dict[str, Any], png: bytes, actor_id: str, received_wall: float | None) -> dict[str, Any]:
        if received_wall is None:
            raise ControlError('Original native receipt time is unavailable')
        metadata = dict(schema='computer-source/1', source_id=f"{self.session}-{frame['capture_id']}",
            session=self.session, capture_id=frame['capture_id'], sha256=hashlib.sha256(png).hexdigest(),
            media_type='image/png', presented_ms=frame['presented_ms'], received_wall=received_wall,
            **{k:frame[k] for k in GEOMETRY_KEYS})
        metadata = self.store.put_source(metadata, png, actor_id)
        self._counts = self.store.counts()
        if self._latest_source is None or metadata['capture_id'] >= self._latest_source['capture_id']:
            self._latest_source = copy.deepcopy(metadata)
        return metadata

    def _native(self, operation: dict[str, Any], kind: str, value: dict[str, Any] | None,
                deadline: float) -> tuple[dict[str, Any], dict[str, Any] | None, bytes | None]:
        identity = uuid.uuid4().hex
        self.store.native_intent(operation['operation_id'], identity)
        try:
            reply, png = self.channel.request(kind, value, deadline, identity)
        except NoDispatch as exc:
            self.stop('Native channel refused publication; collect original pending input')
            reply, png = dict(schema='computer-local/1', id=identity, session=self.session,
                disposition='rejected', emitted_events=0, reason=str(exc), frame=None), None
        # Preserve each known/unknown original receipt BEFORE another basic input.
        operation['receipts'].append(reply)
        timing=self.channel.timing(identity)
        self.store.native_result(identity, reply, None,timing)
        metadata = None
        if reply.get('frame') is not None and png is not None:
            metadata = self._capture(reply['frame'], png, operation['actor_id'],timing.get('receipt_received_wall'))
            self.store.link_native_source(identity, metadata['source_id'])
        if reply['schema'] == 'computer-receipt/2':
            self.channel.release(identity)
        return reply, metadata, png

    def _wait(self, actor_id: str, seconds: float, deadline: float) -> None:
        end = time.monotonic() + seconds
        if end > deadline:
            raise OperationExpired('Wait does not fit the original operation deadline')
        while time.monotonic() < end:
            self._guard(actor_id)
            time.sleep(min(.02, max(0., end - time.monotonic())))

    def observe(self, actor_id: str, *, deadline_monotonic: float | None = None,
                operation_id: str | None = None) -> tuple[dict[str, Any], bytes | None]:
        return self._execute(actor_id, [], None, 'observe', operation_id, deadline_monotonic)

    def input(self, actor_id: str, actions: list[dict[str, Any]], *, source_id: str | None = None,
              deadline_monotonic: float | None = None,
              operation_id: str | None = None) -> tuple[dict[str, Any], bytes | None]:
        try:
            prepared=copy.deepcopy(validate_actions(actions))
        except (ValueError,TypeError) as exc:
            raise NoDispatch(str(exc)) from exc
        identity=request_identity(operation_id)
        try:
            return self._execute(actor_id, prepared, source_id,
                                 'input', identity, deadline_monotonic)
        except ControlError as exc:
            if not self.store.operation_exists(identity,actor_id):
                raise NoDispatch(str(exc)) from exc
            raise

    def _execute(self, actor_id: str, actions: list[dict[str, Any]], source_id: str | None,
                 kind: str, supplied_id: str | None, deadline: float | None
                 ) -> tuple[dict[str, Any], bytes | None]:
        identity = request_identity(supplied_id)
        if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
            raise ControlError('Operation deadline must be finite')
        started = time.monotonic()
        original = min(self.deadline, started + 15., deadline if deadline is not None else math.inf)
        with self.serial:
            # Queueing never restarts the caller's original operation horizon.
            try:
                existing = self.store.operation(identity, actor_id)
            except ControlError:
                existing = None
            if existing is not None:
                return self.result(actor_id, identity)
            self._guard(actor_id)
            if time.monotonic() >= original:
                raise OperationExpired('Original operation deadline expired before dispatch')
            if (self._counts['frames'] >= self.limits['max_frames']
                    or self._counts['frame_bytes'] + MAX_FRAME_BYTES > self.limits['max_bytes']):
                self.stop('Original capture reservation exhausted')
                raise ControlError('Original capture reservation exhausted before input')
            geometry = None
            if any(a['type'] == 'click' for a in actions):
                if source_id is None or not self.store.has_source(source_id, actor_id):
                    raise ControlError('Pointer requires a source issued to this actor')
                metadata,_ = self.source(source_id)
                geometry = {k:metadata[k] for k in GEOMETRY_KEYS}
                for a in actions:
                    if a['type'] == 'click' and (a['x'] >= geometry['width'] or a['y'] >= geometry['height']):
                        raise ControlError('Pointer exceeds original full-image coordinates')
            result = dict(schema='computer-operation/1', operation_id=identity, session=self.session,
                actor_id=actor_id, kind=kind, status='pending', created_wall=time.time(),
                deadline_monotonic=original, receipts=[], source=None, remaining=self.remaining(),
                reason='Original operation in progress', handoff=None)
            count = sum(a['type'] != 'wait' for a in actions)
            try:
                if not self.store.begin(result, actions, count):
                    return self.result(actor_id, identity)
            except (OSError,sqlite3.Error) as exc:
                self.stop('Cannot retain original intent; no input submitted')
                raise NoDispatch('Original intent storage failed before input') from exc
            self._counts = self.store.counts()
            png = None
            try:
                for action in actions:
                    self._guard(actor_id)
                    if time.monotonic() >= original:
                        raise OperationExpired('Original operation deadline exhausted')
                    if action['type'] == 'wait':
                        self._wait(actor_id, action['seconds'], original)
                        continue
                    if action['type'] == 'click':
                        action = dict(action, geometry=geometry)
                    reply, _, _ = self._native(result, 'input', action, original)
                    if reply['disposition'] != 'delivered':
                        result['status'] = 'unknown' if reply['disposition'] in ('partial', 'unknown') else 'refused'
                        result['reason'] = reply['reason']
                        break
                else:
                    result['status'] = 'completed'
                    result['reason'] = 'Basic operations completed; application effect is not certified'
                # The post-input screenshot is an observation, not a goal verdict.
                if not self.channel.stopped.is_set() and time.monotonic() < original:
                    reply, metadata, png = self._native(result, 'observe', None, original)
                    result['source'] = metadata
                    if reply['disposition'] != 'delivered':
                        result['status'] = 'unknown' if reply['disposition'] in ('partial', 'unknown') else 'refused'
                        result['reason'] = reply['reason']
            except OperationExpired as exc:
                result.update(status='partial', reason=str(exc))
                self.stop(str(exc))
            except BaseException as exc:
                self.stop('Operation failed; original intent/receipts remain collectible')
                result.update(status='unknown', reason=f'{type(exc).__name__}: {str(exc)[:500]}')
                if not isinstance(exc, Exception):
                    raise
            finally:
                result['remaining'] = self.remaining()
                self._last = copy.deepcopy(result)
                try:
                    self.store.finish(result)
                except BaseException:
                    self.stop('Original terminal storage failed; no new input')
                    raise
            return result, png

    def result(self, actor_id: str, identity: str) -> tuple[dict[str, Any], bytes | None]:
        with self.serial:
            return self._result(actor_id, identity)

    def _result(self, actor_id: str, identity: str) -> tuple[dict[str, Any], bytes | None]:
        request_identity(identity)
        value = self.store.operation(identity, actor_id)
        for native_id,prior in self.store.native_records(identity):
            collected = self.channel.collect(native_id)
            if collected is not None:
                reply, png = collected
                metadata = self._capture(reply['frame'], png, actor_id,self.channel.timing(native_id).get('receipt_received_wall')) if reply['frame'] is not None and png is not None else None
                if prior is None:
                    self.store.native_result(native_id,reply,metadata['source_id'] if metadata else None,self.channel.timing(native_id))
                elif prior['schema'] == 'computer-transport/2':
                    self.store.add_collection(native_id, reply, metadata['source_id'] if metadata else None)
                elif metadata:
                    self.store.link_native_source(native_id,metadata['source_id'])
                self.channel.release(native_id)
        value = self.store.operation(identity, actor_id)
        png = self.source(value['source']['source_id'])[1] if value['source'] else None
        return value, png

    def seal_actor(self, actor_id: str, identity: str, context_id: str, context_sha256: str) -> dict[str, Any]:
        request_identity(identity)
        request_identity(context_id)
        if not isinstance(context_sha256, str) or re.fullmatch('[0-9a-f]{64}', context_sha256) is None:
            raise ControlError('Handoff context requires its original SHA256')
        with self.serial:
            self._guard(actor_id)
            if self._last is not None and self._last['status'] in ('pending', 'partial', 'unknown'):
                raise ControlError('Unsettled input cannot become a handoff')
            now = time.time()
            issuance = dict(schema='player-handoff/1', operation_id=identity, session=self.session,
                actor_id=actor_id, context_id=context_id, context_sha256=context_sha256,
                sealed_wall=now, grants_authority=False)
            result = dict(schema='computer-operation/1', operation_id=identity, session=self.session,
                actor_id=actor_id, kind='handoff', status='sealed', created_wall=now,
                deadline_monotonic=self.deadline, receipts=[], source=None, remaining=self.remaining(),
                reason='Actor sealed; successor requires actual host/MCP quiescence', handoff=issuance)
            if not self.store.begin(result, None, 0):
                return self.store.operation(identity, actor_id)
            self._counts = self.store.counts()
            result['remaining'] = self.remaining()
            self.store.finish(result, seal_actor=True)
            with self._custody:
                self._actors[actor_id]['stage'] = 'sealed'
                self._handoffs[actor_id] = issuance
            self._last = copy.deepcopy(result)
            return result

    def confirm_quiescent(self, actor_id: str, identity: str, *, host_quiescent: bool) -> None:
        """Driver-only: actual owned-host/group checks precede this call."""
        with self.serial:
            if (not host_quiescent or self.channel.stopped.is_set()
                    or self.actor_stage(actor_id) != 'sealed'
                    or self._handoffs.get(actor_id, {}).get('operation_id') != identity):
                raise ControlError('Original handoff/host quiescence does not permit succession')
            self.store.set_actor_stage(actor_id, 'quiescent')
            with self._custody:
                if self.channel.stopped.is_set() or self._actors[actor_id]['stage'] != 'sealed':
                    raise ControlError('Cancellation during quiescence prevents succession')
                self._actors[actor_id]['stage'] = 'quiescent'

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.channel.close()
        self.store.close()
