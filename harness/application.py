"""Composition of mechanical control and optional, fallible player services."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from .computer.protocol import ControlError, canonical, closed
from .computer.runtime import ComputerRuntime
from .player.contracts import (LEVEL_ABSTAIN_SCHEMA, LEVEL_COMMIT_SCHEMA, LEVEL_CONTRACT, LEVEL_TERMINAL_TOOLS,
                               PlayerError, bounded_integer, level_arguments)
from .player.contracts import canonical as player_canonical
from .player.memory import Memory
from .player.programs import ProgramRepository, ProgramRunner
from .player_tools import PROFILES
from .observer import ActivityView

READ_TOOLS = {'computer_result', 'player_source', 'player_memory_read', 'player_memory_query',
              'player_memory_context', 'player_program_read', 'player_result', 'player_log_read', 'player_intent'}
# The reader's pass-ending calls: its only writes (keep and abstain write nothing; replace and close write memory).
LEVEL_END_TOOLS = LEVEL_TERMINAL_TOOLS


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
        # The custodian's per-capability allowlist, enforced here as well as by
        # each host's enabled tools; a capability minted elsewhere has no tools.
        self.profiles: dict[str, frozenset[str]] = {}
        self.readers: dict[str, dict[str, Any]] = {}
        # Optional sink for per-call lock wait/hold, the level's measured cost to the actor.
        self.timing = None
        self.host: dict[str, Any] | None = None
        self.claims: list[dict[str, Any]] = []
        self.activity_view = ActivityView(runtime.session, runtime.store.path)
        # The custodian may inject a bounded passive snapshot adapter. Actor
        # services and the independent Pause path never await this work.
        self.investigation_view = None

    def add_actor(self, profile: str) -> dict[str, str]:
        if profile not in ('flat', 'narrowed'):
            raise ControlError('Unknown actor tool profile')
        with self.serial:
            actor = self.runtime.add_actor()
            self.profiles[actor['actor_id']] = frozenset(PROFILES[profile])
            return actor

    def add_reader(self, actor_id: str, *, staleness_inputs: int) -> dict[str, str]:
        """Mint the subgoal level's reader for one active actor; S bounds a commit's staleness."""
        if type(staleness_inputs) is not int or not 1 <= staleness_inputs <= 1000:
            raise ControlError('Staleness bound must be 1..1000 actor inputs')
        with self.serial:
            # A level serves an actor that writes no memory, so only the level's own commits can
            # change the current subgoal after minting; more than one is a store no pass could resolve.
            if self.profiles.get(actor_id) != frozenset(PROFILES['narrowed']):
                raise ControlError('A reader serves only a narrowed-profile actor')
            if len(self.level_subgoals()) > 1:
                raise ControlError('More than one current level subgoal; the level could never commit')
            reader = self.runtime.add_reader(actor_id)
            self.profiles[reader['actor_id']] = frozenset(PROFILES['reader'])
            self.readers[reader['actor_id']] = dict(serves=actor_id, staleness_inputs=staleness_inputs, bound=None)
            return reader

    def log_read(self, reader_id: str, after: int, limit: int) -> dict[str, Any]:
        state = self.readers[reader_id]
        bounded_integer(after, 0, 1 << 40)
        bounded_integer(limit, 1, 50)
        actor = state['serves']
        stage = self.runtime.actor_stage(actor)
        # No active served actor means a handoff: no entries, so nothing can bind a commit.
        entries = self.runtime.store.actor_log(actor, after, limit) if stage == 'active' else []
        if entries:
            state['bound'] = max(state['bound'] or 0, entries[-1]['position'])
        elif after == 0 and stage == 'active' and state['bound'] is None:
            # Reading an empty log from its start has seen all of it, so an actor-start
            # pass can revalidate open records before the actor's first input.
            state['bound'] = 0
        return dict(schema='player-log/1', session=self.runtime.session, actor_id=actor, after=after,
                    entries=entries, handoff=stage != 'active', grants_authority=False)

    def level_subgoals(self) -> list[dict[str, Any]]:
        """The current Work records the level manages; at most one by construction. Other Work is out of its scope."""
        return [r for r in self.memory.current('work') if r['data'].get('level') == 'subgoal']

    def intent(self, actor_id: str) -> dict[str, Any]:
        """The latest committed subgoal for an actor's request-only tail; fallible data, never authority."""
        level = self.level_subgoals()
        value = dict(schema='player-intent/1', session=self.runtime.session, actor_id=actor_id, record=None,
                     age=None, grants_authority=False)
        if not level:
            return value
        latest = level[-1]
        data = latest['data']
        same_actor = data.get('actor_id') == actor_id
        value['record'] = dict(record_id=latest['id'], text=latest['text'], sources=latest['sources'],
            **{k: data.get(k) for k in ('expected_observations', 'status', 'confidence')})
        # Positions are per actor, so inputs since the commit are known only for the same actor.
        value['age'] = dict(seconds=max(0., time.time() - latest['created_wall']),
            inputs_since_commit=self.runtime.store.inputs_after(actor_id, data['position']) if same_actor else None,
            inputs_by_this_actor=self.runtime.store.inputs_after(actor_id, 0),
            same_actor=same_actor, same_session=data.get('session') == self.runtime.session)
        return value

    def level_record_count(self) -> int:
        """Level-written Work records in player memory, superseded history included; the pushed input states it."""
        return sum(json.loads(row[0])['data'].get('level') == 'subgoal' for row in
                   self.memory._db.execute("SELECT document FROM records WHERE kind='work'"))

    def _level_state(self, tool: str, args: dict[str, Any], subgoals: list[dict[str, Any]]) -> str | None:
        """The fixable wrong-state error for a call, naming the current subgoal state and the valid tool; else None."""
        if subgoals:
            current = subgoals[-1]
            state = f'The current subgoal is {current["id"]} ({current["data"].get("status")}): "{current["text"][:80]}".'
        else:
            state = 'There is no current subgoal.'
        if tool in ('player_level_keep', 'player_level_close') and not subgoals:
            return (f'{state} {tool} needs a current subgoal. Call player_level_replace with previous_outcome "none" '
                    'and previous_reason "" to set one, or player_level_abstain.')
        if tool == 'player_level_replace':
            outcome, reason = args['previous_outcome'], args['previous_reason']
            if outcome == 'none' and subgoals:
                return (f'{state} previous_outcome "none" is only valid when there is no current subgoal. Set '
                        'previous_outcome to achieved, failed, abandoned or revised with a previous_reason, or call '
                        'player_level_keep or player_level_close.')
            if outcome != 'none' and not subgoals:
                return f'{state} previous_outcome must be "none" (with previous_reason "") when there is nothing to replace.'
            if outcome != 'none' and not reason.strip():
                return f'{state} previous_reason must say why it was {outcome}; it may be empty only with previous_outcome "none".'
        return None

    def level_call(self, reader_id: str, tool: str, args: dict[str, Any], identity: str) -> dict[str, Any]:
        """One keep, replace or close: the pass's single terminal call, timely-checked and then committed or discarded."""
        state = self.readers[reader_id]
        prior = self.memory._db.execute('SELECT actor,tool,args,result FROM service_operations WHERE id=?',
                                        (identity,)).fetchone()
        if prior:
            # A retained identity collects its original commit; it never re-binds or recommits.
            if prior[:3] != (reader_id, tool, player_canonical(args)) or prior[3] is None:
                raise PlayerError('Original level-commit identity conflicts')
            return self.memory.service_result(identity, reader_id)['value']
        action = tool.removeprefix('player_level_')
        subgoals = self.level_subgoals()
        current = subgoals[-1]['id'] if subgoals else None
        # Fixable errors are tool errors and keep the bound for a resubmission.
        args = level_arguments(tool, args)
        wrong = self._level_state(tool, args, subgoals)
        if wrong is not None:
            raise PlayerError(wrong)
        # A replace that supersedes a current subgoal also writes the correction carrying its outcome.
        outcome = args.get('previous_outcome', args.get('outcome'))
        corrected = current is not None and action != 'keep'
        cited = list(dict.fromkeys(args['sources']))
        missing = [s for s in cited if not self.runtime.store.has_source(s) and not self._has_player_source(s)]
        if missing:
            raise PlayerError(f'Cited sources are unavailable: {", ".join(missing[:4])}')
        # Exact bytes are read (and integrity-checked) before the pass can end; they are
        # registered inside the commit transaction, never piecemeal.
        # A keep writes no record, so it registers no frame bytes: it only checks its citations are available.
        blobs = [] if action == 'keep' else [self.runtime.source(s) for s in cited if not self._has_player_source(s)]
        if sum(len(png) for _, png in blobs) > self.memory.source_bytes_left():
            raise PlayerError('Cannot remember: cited sources exceed player source capacity; no images evicted')
        actor, bound = state['serves'], state['bound']
        # A timeliness check ends the pass, committed or discarded: the next one must read again.
        state['bound'] = None
        moved = self.runtime.store.inputs_after(actor, bound) if bound is not None else None
        position = dict(position=bound, inputs_since=moved, staleness_inputs=state['staleness_inputs'])
        channel = self.runtime.channel
        reason = ('No log read bound a position in this pass' if bound is None
                  # A user Pause or takeover changes the game without custodian input.
                  else 'Run stopped or fenced since the read' if channel.stopped.is_set() or channel.fault is not None
                  or time.monotonic() >= self.runtime.deadline
                  else 'Served actor handed off since the read' if self.runtime.actor_stage(actor) != 'active'
                  else 'Served actor moved at least S inputs past the read' if moved >= state['staleness_inputs']
                  else None)
        if reason is not None:
            # A discard is returned to the level's host trace and never written to either store.
            return dict(schema=LEVEL_COMMIT_SCHEMA, status='discarded', action=action, reason=reason,
                        **position, records=[], kept=[])
        values, ids = [], self.memory.batch_ids(identity, 16)
        # Software, not the model, supplies the contract version stored with every record.
        common = dict(level='subgoal', level_contract=LEVEL_CONTRACT, actor_id=actor,
                      session=self.runtime.session, position=bound)
        if action == 'replace':
            values.append(dict(schema='player-record/1', kind='work', text=args['text'],
                data=dict(common, expected_observations=args['expected_observations'],
                          status=args['status'], confidence=args['confidence']),
                sources=cited, supports=[], supersedes=None, applicability=None, program_id=None))
        # A close or a replacement's previous outcome supersedes the subgoal; a revision supports its successor.
        if corrected:
            values.append(dict(schema='player-record/1', kind='correction',
                text=args.get('previous_reason', args.get('reason')),
                data=dict(common, outcome=outcome), sources=cited,
                supports=[ids[0]] if outcome == 'revised' else [],
                supersedes=current, applicability=None, program_id=None))
        result = dict(schema=LEVEL_COMMIT_SCHEMA, status='committed', action=action, reason=None, **position,
                      kept=[current] if action == 'keep' else [])
        records = self.memory.append_many(reader_id, values, request_id=identity,
                                          service=(tool, args, result), sources=blobs)
        self.claims = self.memory.query(limit=5)
        return dict(result, records=records)

    def reset_reader_bound(self, reader_id: str) -> None:
        """Forget a reader's bound, so the next pass's own log read alone binds its position."""
        with self.serial:
            self.readers[reader_id]['bound'] = None

    def level_abstain(self, reader_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """End a pass with no change: nothing is written and, like a terminal call, it clears the bound."""
        args = level_arguments('player_level_abstain', args)
        missing = [s for s in dict.fromkeys(args['sources'])
                   if not self.runtime.store.has_source(s) and not self._has_player_source(s)]
        if missing:
            raise PlayerError(f'Cited sources are unavailable: {", ".join(missing[:4])}')
        self.readers[reader_id]['bound'] = None
        return dict(schema=LEVEL_ABSTAIN_SCHEMA, status='abstained', reason_code=args['reason_code'],
                    reason=args['reason'])

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

    def snapshot(self, actor_id: str) -> tuple[str, str]:
        # Mechanical identity only: no actor-written summary and no knowledge
        # snapshot. Continuity comes from committed player records.
        identity = uuid.uuid4().hex
        packet = dict(schema='player-handoff-context/2', context_id=identity, session=self.runtime.session,
                      actor_id=actor_id, created_wall=time.time(), grants_authority=False)
        data = (canonical(packet) + '\n').encode('utf-8')
        with (self.context_directory / (identity + '.json')).open('xb') as stream:
            stream.write(data)
        return identity, hashlib.sha256(data).hexdigest()

    @contextmanager
    def _timed(self, actor: str, name: str, queued: float):
        """Record one call's wait for and hold of the serial lock; timing never affects the call."""
        acquired = time.monotonic()
        try:
            yield
        finally:
            if self.timing is not None:
                try:
                    self.timing(dict(schema='custodian-call-timing/1', wall=time.time(), actor_id=actor, tool=name,
                                     wait_ms=(acquired - queued) * 1000, held_ms=(time.monotonic() - acquired) * 1000))
                except Exception:
                    pass

    def call(self, token: str, name: str, args: dict[str, Any], identity: str) -> tuple[dict[str, Any], bytes | None]:
        write = dict(write=name not in READ_TOOLS, level_end=name in LEVEL_END_TOOLS)
        actor = self.runtime.authorize(token, **write)
        if name not in self.profiles.get(actor, ()):
            raise ControlError('Tool is outside this capability class')
        queued = time.monotonic()
        with self.serial, self._timed(actor, name, queued):
            # A handoff may have sealed the actor while this call queued.
            self.runtime.authorize(token, **write)
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
            if name == 'player_intent':
                closed(args, set())
                return self.intent(actor), None
            if name == 'player_log_read':
                closed(args, {'after','limit'})
                return self.log_read(actor, args['after'], args['limit']), None
            if name in ('player_level_keep', 'player_level_replace', 'player_level_close'):
                return self.level_call(actor, name, args, identity), None
            if name == 'player_level_abstain':
                return self.level_abstain(actor, args), None
            if name == 'player_handoff':
                closed(args, set())
                context_id, sha = self.snapshot(actor)
                return self.runtime.seal_actor(actor, identity, context_id, sha), None
            raise ControlError('Unknown current tool')
