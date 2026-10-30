"""Composition of mechanical control and optional, fallible player services."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from .computer.protocol import ControlError, canonical, closed
from .computer.runtime import ComputerRuntime
from .player.contracts import PlayerError
from .player.memory import Memory
from .player.programs import ProgramRepository, ProgramRunner
from .observer import ActivityView

READ_TOOLS = {'computer_result', 'player_source', 'player_memory_read', 'player_memory_query',
              'player_memory_context', 'player_program_read', 'player_result'}


class _ProgramControl:
    """Retain each original child ID before calling the one mechanical writer."""
    def __init__(self, runtime, memory, request_id):
        self.runtime, self.memory, self.request_id = runtime, memory, request_id

    def _call(self, kind, actor_id, actions=None, *, source_id=None, deadline_monotonic=None):
        identity = uuid.uuid4().hex
        self.memory.service_step(self.request_id,dict(operation_id=identity,session=self.runtime.session,kind=kind))
        if kind == 'observe':
            return self.runtime.observe(actor_id,operation_id=identity,deadline_monotonic=deadline_monotonic)
        return self.runtime.input(actor_id,actions,source_id=source_id,
                                  operation_id=identity,deadline_monotonic=deadline_monotonic)

    def observe(self, actor_id, *, deadline_monotonic=None):
        return self._call('observe',actor_id,deadline_monotonic=deadline_monotonic)

    def input(self, actor_id, actions, *, source_id=None, deadline_monotonic=None):
        return self._call('input',actor_id,actions,source_id=source_id,deadline_monotonic=deadline_monotonic)


def _operation_reference(value):
    return {k:copy.deepcopy(value.get(k)) for k in ('operation_id','session','actor_id','kind','status','reason')} | {
        'source_id':value['source']['source_id'] if value.get('source') else None}


def _program_projection(value, request_id):
    steps=[]
    for step in value['steps']:
        decision=step['result']
        steps.append(dict(source=step['source'],operation=_operation_reference(step['operation']),
            input_operation=_operation_reference(step['input_operation']) if step.get('input_operation') else None,
            result=None if decision is None else dict(status=decision['status'],actions=decision['actions'],
                reason=decision['reason'],state_sha256=hashlib.sha256(canonical(decision['state']).encode()).hexdigest())))
    return {k:copy.deepcopy(value[k]) for k in ('schema','program_id','status','reason','final_state','elapsed_seconds')} | {
        'run_id':request_id,'steps':steps,'operations':[_operation_reference(o) for o in value['operations']],
        'omissions':['Per-step state bytes omitted; final_state and state hashes retained.',
                     'Full native receipts and pixels are available by original computer_result/source IDs.']}


class Application:
    """One serialized playing-service caller; operator Pause bypasses this lock."""
    def __init__(self, runtime: ComputerRuntime, memory: Memory, context_directory: Path) -> None:
        self.runtime, self.memory = runtime, memory
        self.programs = ProgramRepository(memory)
        self.context_directory = context_directory
        context_directory.mkdir(mode=0o700)
        self.serial = threading.RLock()
        self.host: dict[str, Any] | None = None
        self.claims: list[dict[str, Any]] = []
        self.activity_view = ActivityView(runtime.session, runtime.store.path)
        # The custodian may inject a bounded passive snapshot adapter. Actor
        # services and the independent Pause path never await this work.
        self.investigation_view = None

    def status(self) -> dict[str, Any]:
        return dict(self.runtime.status(), host=copy.deepcopy(self.host), player_claims=copy.deepcopy(self.claims))

    def submission_status(self, actor_id: str, identity: str) -> str:
        if self.runtime.store.operation_exists(identity,actor_id):
            return 'uncertain'
        with self.serial:
            row=self.memory._db.execute('SELECT 1 FROM service_operations WHERE id=? AND actor=?',
                                        (identity,actor_id)).fetchone()
            return 'uncertain' if row else 'none'

    def _has_player_source(self, identity: str) -> bool:
        return self.memory._db.execute('SELECT 1 FROM sources WHERE id=?', (identity,)).fetchone() is not None

    def _register(self, identities: list[str]) -> None:
        # Explicit knowledge/program authoring requests durable provenance. A
        # referenced image is availability, not proof the player inspected it.
        for identity in identities:
            if not self._has_player_source(identity):
                metadata, png = self.runtime.source(identity)
                self.memory.register_source(metadata, png)

    def source(self, identity: str, actor_id: str | None = None) -> tuple[dict[str, Any], bytes]:
        with self.serial:
            if self._has_player_source(identity):
                value, png = self.memory.read_source(identity)
            else:
                value, png = self.runtime.source(identity)
            if actor_id is not None and self.runtime.store.has_source(identity):
                self.runtime.store.issue_source(actor_id, identity)
            return value, png

    def snapshot(self, actor_id: str, roots: list[str], summary: str) -> tuple[str, str]:
        if not isinstance(summary, str) or len(summary) > 8192:
            raise PlayerError('Handoff summary must be within8192 characters')
        context = self.memory.context(roots, max_bytes=65536)
        identity = uuid.uuid4().hex
        packet = dict(schema='player-handoff-context/1', context_id=identity, session=self.runtime.session,
                      actor_id=actor_id, summary=summary, knowledge=context, created_wall=time.time(),
                      grants_authority=False)
        data = (canonical(packet) + '\n').encode('utf-8')
        with (self.context_directory / (identity + '.json')).open('xb') as stream:
            stream.write(data)
        return identity, hashlib.sha256(data).hexdigest()

    def call(self, token: str, name: str, args: dict[str, Any], identity: str) -> tuple[dict[str, Any], bytes | None]:
        actor = self.runtime.authorize(token, write=name not in READ_TOOLS)
        with self.serial:
            # A handoff may have sealed the actor while this call queued.
            self.runtime.authorize(token, write=name not in READ_TOOLS)
            if name not in READ_TOOLS:
                # A public HTTP identity has one owner across the composed
                # services. A program's child IDs do not free its parent ID for
                # a second basic-input submission after an uncertain response.
                computer_owned=self.runtime.store.operation_exists(identity)
                player_owned=self.memory._db.execute('SELECT 1 FROM service_operations WHERE id=?',(identity,)).fetchone()
                computer_tool=name in ('computer_observe','computer_input','player_handoff')
                if (computer_owned and not computer_tool) or (player_owned and computer_tool):
                    raise ControlError('Original public identity belongs to another service; collect it, never dispatch')
            if name == 'computer_observe':
                closed(args, set())
                return self.runtime.observe(actor, operation_id=identity)
            if name == 'computer_input':
                if type(args) is not dict or not {'actions'} <= args.keys() or args.keys() - {'actions','source_id'}:
                    raise ControlError('Input requires actions and optional source_id')
                return self.runtime.input(actor, args['actions'], source_id=args.get('source_id'), operation_id=identity)
            if name == 'computer_result':
                closed(args, {'operation_id'})
                return self.runtime.result(actor, args['operation_id'])
            if name == 'computer_stop':
                closed(args, set())
                return self.runtime.stop('Player chose permanent stop'), None
            if name == 'player_source':
                closed(args, {'source_id'})
                value, png = self.source(args['source_id'], actor)
                return dict(schema='player-source-read/1', source=value, read_wall=time.time()), png
            if name == 'player_memory_append':
                closed(args, {'record'})
                from .player.contracts import record
                value = record(args['record'])
                if not self.memory.begin_service(identity,actor,name,args):
                    retained=self.memory.service_result(identity,actor)
                    return retained['value'] or retained,None
                self._register(value['sources'])
                result = self.memory.append(actor, value,request_id=identity)
                self.memory.finish_service(identity,result)
                self.claims = self.memory.query(limit=5)
                return result, None
            if name == 'player_memory_read':
                closed(args, {'record_id'})
                return self.memory.read(args['record_id']), None
            if name == 'player_memory_query':
                if type(args) is not dict or args.keys() - {'kind','limit','include_superseded'}:
                    raise PlayerError('Unknown memory-query fields')
                return dict(schema='player-query/1', records=self.memory.query(**args), grants_authority=False), None
            if name == 'player_memory_context':
                if type(args) is not dict or not {'ids'} <= args.keys() or args.keys() - {'ids','max_bytes'}:
                    raise PlayerError('Context requires ids and optional max_bytes')
                return self.memory.context(args['ids'], max_bytes=args.get('max_bytes',65536)), None
            if name == 'player_program_save':
                closed(args, {'program'})
                from .player.contracts import program
                value = program(args['program'])
                if not self.memory.begin_service(identity,actor,name,args):
                    retained=self.memory.service_result(identity,actor)
                    return retained['value'] or retained,None
                self._register(value['source_ids'])
                result=self.programs.save(actor, value,request_id=identity)
                self.memory.finish_service(identity,result)
                return result,None
            if name == 'player_program_read':
                closed(args, {'program_id'})
                return self.programs.read(args['program_id']), None
            if name == 'player_program_run':
                if (type(args) is not dict or not {'program_id','initial_state','interpretation','selection'} <= args.keys()
                        or args.keys() - {'program_id','initial_state','interpretation','selection','max_steps','max_seconds'}):
                    raise PlayerError('Invalid program-run fields')
                if not self.memory.begin_service(identity,actor,name,args):
                    retained=self.memory.service_result(identity,actor)
                    return retained['value'] or retained,None
                raw = ProgramRunner(self.programs,_ProgramControl(self.runtime,self.memory,identity)).run(actor_id=actor, **args)
                result = _program_projection(raw,identity)
                if raw['status'] in ('unknown','partial'):
                    self.runtime.stop('Program encountered uncertain delivery; original collection only')
                self.memory.finish_service(identity,result)
                return result, None
            if name == 'player_result':
                closed(args,{'operation_id'})
                result=self.memory.service_result(args['operation_id'])
                collected=[]
                for step in result['progress']['steps']:
                    if step['session'] != self.runtime.session:
                        collected.append(dict(**step,status='retained_in_prior_session; no authority restored'))
                    elif self.runtime.store.operation_exists(step['operation_id'],result['actor_id']):
                        original,_=self.runtime.result(result['actor_id'],step['operation_id'])
                        collected.append(original)
                    else:
                        collected.append(dict(**step,status='not_submitted_to_computer'))
                return dict(result,collected_operations=collected),None
            if name == 'player_handoff':
                closed(args, {'ids','summary'})
                context_id, sha = self.snapshot(actor, args['ids'], args['summary'])
                return self.runtime.seal_actor(actor, identity, context_id, sha), None
            raise ControlError('Unknown current tool')
