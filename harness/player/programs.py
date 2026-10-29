"""Immutable player programs and an optional bounded computer-port coordinator."""
from __future__ import annotations

import hashlib
import math
import time
from time import monotonic
import uuid
from typing import Any

from harness.computer.ports import ComputerPort
from harness.computer.protocol import NoDispatch
from .contracts import PlayerError, bounded_integer, canonical, identity, json_object, program
from .images import program_view
from .memory import Memory
from .policy_program import PolicyProgram


class ProgramRepository:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def save(self, actor_id: str, value: dict, *, request_id: str | None = None) -> dict:
        identity(actor_id)
        value = program(value)
        stored = dict(value, id=request_id or uuid.uuid4().hex, actor_id=actor_id, created_wall=time.time(),
                      sha256=hashlib.sha256(value['code'].encode('utf-8')).hexdigest())
        with self.memory._transaction():
            if self.memory._db.execute('SELECT 1 FROM programs WHERE id=?',(stored['id'],)).fetchone():
                original = self.read(stored['id'])
                if original['actor_id'] != actor_id or {k:v for k,v in original.items() if k not in {'id','actor_id','created_wall','sha256'}} != value:
                    raise PlayerError('Original program request identity conflicts')
                return original
            self.memory._references('sources', value['source_ids'])
            self.memory._references('records', value['record_ids'])
            self.memory._references('programs', [value['parent_id']] if value['parent_id'] else [])
            self.memory._db.execute('INSERT INTO programs VALUES (?,?,?)',
                                    (stored['id'], canonical(stored), value['parent_id']))
            for table, field in (('program_sources', 'source_ids'), ('program_records', 'record_ids')):
                self.memory._db.executemany(f'INSERT INTO {table} VALUES (?,?)',
                                           [(stored['id'], ref) for ref in value[field]])
        return stored

    def read(self, program_id: str) -> dict:
        return self.memory._document('programs', program_id)


class ProgramRunner:
    """Propose through the same port, never reconstruct or renew its authority.

    Synchronous port calls retain their own original mechanical budgets. This
    runner passes its single original deadline to each callback and checks it
    before and after calls. Callbacks may only shorten their own limits.
    """
    def __init__(self, repository: ProgramRepository, control_port: ComputerPort) -> None:
        self.repository = repository
        self.control_port = control_port

    def run(self, program_id: str, actor_id: str, initial_state: dict,
            interpretation: dict, selection: dict, max_steps: int = 16,
            max_seconds: float = 10) -> dict[str, Any]:
        started = monotonic()
        state = {}
        operations, steps = [], []
        status, reason = 'limit', 'Original program time or step limit reached'
        operation, png = None, None
        in_port = False
        port_kind = None
        try:
            # Predispatch lookup/validation faults are helper outcomes too.
            # Retain a terminal result under the original service identity;
            # they cannot imply uncertain computer delivery or revoke custody.
            bounded_integer(max_steps, 1, 64)
            identity(actor_id)
            if type(max_seconds) not in (int, float) or not 0 < max_seconds <= 20 or not math.isfinite(max_seconds):
                raise PlayerError('Program duration must be finite within (0,20] seconds')
            state = json_object(initial_state)
            interpretation = json_object(interpretation)
            selection = json_object(selection)
            deadline = started + max_seconds
            saved = self.repository.read(program_id)
            with PolicyProgram(saved['code']) as policy:
                for _ in range(max_steps):
                    if monotonic() >= deadline:
                        break
                    if operation is None or png is None or operation.get('source') is None:
                        in_port, port_kind = True, 'observe'
                        operation, png = self.control_port.observe(actor_id, deadline_monotonic=deadline)
                        in_port = False
                        operation = json_object(operation)
                        operations.append(operation)
                    if operation.get('status') != 'completed':
                        status = operation.get('status', 'fault')
                        reason = operation.get('reason') or 'Computer operation did not complete'
                        break
                    if monotonic() >= deadline:
                        break
                    if png is None or operation.get('source') is None:
                        raise PlayerError('A program step requires an actual captured PNG')
                    view = program_view(operation['source'], png, selection, interpretation,
                                        operation.get('remaining', {}))
                    step = dict(operation=operation, source=view['source'], result=None)
                    steps.append(step)
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        break
                    result = policy.step(view, state, timeout_seconds=min(.05, remaining))
                    step['result'] = result
                    state = result['state']
                    if monotonic() >= deadline:
                        break
                    if result['status'] != 'act':
                        status, reason = result['status'], result['reason']
                        break
                    in_port, port_kind = True, 'input'
                    operation, png = self.control_port.input(actor_id, result['actions'],
                                                             source_id=view['source']['source_id'],
                                                             deadline_monotonic=deadline)
                    in_port = False
                    operation = json_object(operation)
                    operations.append(operation)
                    step['input_operation'] = operation
                    if operation.get('status') != 'completed':
                        status = operation.get('status', 'fault')
                        reason = operation.get('reason') or 'Computer operation did not complete'
                        break
        except NoDispatch as exc:
            status,reason='refused',str(exc)[:1024]
        except Exception as exc:
            # A port exception during input cannot be relabelled an undelivered
            # helper fault. The mechanical owner alone resolves its uncertainty.
            status = 'unknown' if in_port and port_kind == 'input' else 'fault'
            reason = f'{type(exc).__name__}: {str(exc)[:1024]}'
        return dict(schema='player-program-run/1', program_id=program_id, status=status, reason=reason,
                    steps=steps, operations=operations, final_state=state,
                    elapsed_seconds=monotonic() - started)
