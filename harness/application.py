"""Composition of mechanical control and optional, fallible player services."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import math
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from .computer.protocol import ControlError, canonical, closed
from .computer.runtime import ComputerRuntime
from .player import recall
from .player.contracts import (EPISODE_ABSTAIN_SCHEMA, EPISODE_RECORD_SCHEMA, EPISODE_TOOLS, INTENT_SCHEMA,
                               LEVEL_ABSTAIN_SCHEMA, LEVEL_COMMIT_SCHEMA, LEVEL_CONTRACT, LEVEL_FIX_LINE,
                               LEVEL_TERMINAL_TOOLS, SOFTWARE_SETTLES, PlayerError, RememberError, bounded_integer,
                               level_arguments, refuse_custodian_data)
from .player.contracts import canonical as player_canonical
from .player.episodes import claim_data, closure_evidence, derive, episode
from .player.memory import Memory
from .player.programs import ProgramRepository, ProgramRunner
from .player_tools import PROFILES
from .observer import ActivityView

READ_TOOLS = {'computer_result', 'player_source', 'player_memory_read', 'player_memory_query',
              'player_memory_context', 'player_program_read', 'player_result', 'player_intent'}
# The readers' pass-ending calls, their only writes. A level's keep and abstain write nothing; its replace and close
# write memory. A recorder's record and abstain each write the one claim that settles its episode.
LEVEL_END_TOOLS = LEVEL_TERMINAL_TOOLS
RECORDER_END_TOOLS = EPISODE_TOOLS
ACTOR_PROFILES = ('flat', 'narrowed')
STALE_SUBGOAL = 'Current subgoal changed since the pass began'


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


def _stall_parameters(stall_settles: object, confidence_floor: object) -> dict[str, Any]:
    if type(stall_settles) is not int or not 1 <= stall_settles <= 1000:
        raise ControlError('Stall test N must be 1..1000 settled episodes')
    if type(confidence_floor) not in (int, float) or not math.isfinite(confidence_floor) or not 0 <= confidence_floor <= 1:
        raise ControlError('Confidence floor c must be a number from 0 to 1')
    return dict(stall_settles=stall_settles, floor=float(confidence_floor))


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
        # The stall test N and confidence floor c, fixed per served actor at reader minting and shared by its readers.
        self.derivation: dict[str, dict[str, Any]] = {}
        # Why remembering failed, once it has: the recorder and the level then stop for this session. The actor's
        # input never depends on it, so a driver reads this and ends those hosts, nothing else.
        self.remember_failure: str | None = None
        self._episode_views: list[dict[str, Any]] = []
        self._episode_scanned = 0
        # Optional sink for per-call lock wait/hold, the level's measured cost to the actor.
        self.timing = None
        self.host: dict[str, Any] | None = None
        self.claims: list[dict[str, Any]] = []
        self.activity_view = ActivityView(runtime.session, runtime.store.path)
        # The custodian may inject a bounded passive snapshot adapter. Actor
        # services and the independent Pause path never await this work.
        self.investigation_view = None

    def add_actor(self, profile: str) -> dict[str, str]:
        if profile not in ACTOR_PROFILES:
            raise ControlError('Unknown actor tool profile')
        with self.serial:
            actor = self.runtime.add_actor()
            self.profiles[actor['actor_id']] = frozenset(PROFILES[profile])
            return actor

    def add_reader(self, actor_id: str, role: str, *, stall_settles: int, confidence_floor: float,
                   staleness_inputs: int | None = None) -> dict[str, str]:
        """Mint a `level` or `recorder` reader for one active actor.

        N (`stall_settles`) and c (`confidence_floor`) are fixed here like S (`staleness_inputs`, the level's
        only), and one actor's two readers share one N and c, since both derive the same state from the store.
        """
        if role not in ('level', 'recorder'):
            raise ControlError('Reader role must be level or recorder')
        parameters = _stall_parameters(stall_settles, confidence_floor)
        if role == 'level':
            if type(staleness_inputs) is not int or not 1 <= staleness_inputs <= 1000:
                raise ControlError('Staleness bound must be 1..1000 actor inputs')
        elif staleness_inputs is not None:
            raise ControlError('Only the level has a staleness bound')
        with self.serial:
            self._remember_ok()
            # A reader serves an actor that writes no memory, so only the readers' own commits can
            # change the current subgoal after minting; more than one is a store no pass could resolve.
            if self.profiles.get(actor_id) != frozenset(PROFILES['narrowed']):
                raise ControlError('A reader serves only a narrowed-profile actor')
            if self.derivation.get(actor_id, parameters) != parameters:
                raise ControlError('One actor\'s level and recorder share one stall test N and confidence floor c')
            current = self.level_subgoals()
            if len(current) > 1:
                raise ControlError('More than one current level subgoal; the level could never commit')
            # A record written under another level contract is not read, converted or superseded: S-MIGRATION.
            stale = [r['id'] for r in current if r['data'].get('level_contract') != LEVEL_CONTRACT]
            if stale:
                raise ControlError(f'Unsupported level record contract (current level Work {", ".join(stale)} is not '
                                   f'{LEVEL_CONTRACT}); migrate or start a fresh player store')
            reader = self.runtime.add_reader(actor_id, role)
            self.derivation[actor_id] = parameters
            self.profiles[reader['actor_id']] = frozenset(PROFILES[role])
            self.readers[reader['actor_id']] = (
                dict(role=role, serves=actor_id, staleness_inputs=staleness_inputs, bound=None, subgoal_id=None, passes=0)
                if role == 'level' else dict(role=role, serves=actor_id, episode=None))
            return reader

    def _reader(self, reader_id: str, role: str) -> dict[str, Any]:
        state = self.readers.get(reader_id)
        if state is None or state['role'] != role:
            raise ControlError(f'Not a {role} reader')
        return state

    def _remember_ok(self) -> None:
        if self.remember_failure is not None:
            raise ControlError(f'Player memory could not remember ({self.remember_failure}); the recorder and the '
                               'level are stopped for this session. The actor is unaffected.')

    @contextmanager
    def _remembering(self):
        """A failure to remember stops the recorder and the level for the session; nothing is evicted."""
        try:
            yield
        except RememberError as exc:
            self.remember_failure = str(exc)[:300]
            raise

    def _cannot_remember_sources(self, blobs: list[tuple[dict, bytes]]) -> None:
        needed, left = sum(len(png) for _, png in blobs), self.memory.source_bytes_left()
        if needed > left:
            reason = (f'Cannot remember: the {len(blobs)} cited frames not yet remembered total {needed} bytes, but '
                      f'player memory has {left} bytes of source capacity left and evicts no images.')
            self.remember_failure = reason[:300]
            raise PlayerError(reason + ' The recorder and the level are stopped for this session.')

    def level_subgoals(self) -> list[dict[str, Any]]:
        """The current Work records the level manages; at most one by construction. Other Work is out of its scope."""
        return [r for r in self.memory.current('work') if r['data'].get('level') == 'subgoal']

    def level_record_count(self) -> int:
        """Level-written Work records in player memory, superseded history included; the pushed input states it."""
        return len(self.memory.level_records('work', 'subgoal'))

    # --- Episodes: trusted views, derived state, binding ---

    def _episodes(self) -> list[dict[str, Any]]:
        """Every trusted episode claim in commit order, each with its `row` commit position. Appended to as claims commit."""
        revision = self.memory.revision()
        if revision > self._episode_scanned:
            for row, record in self.memory.episode_claims(self._episode_scanned, revision):
                view = episode(record)
                if view is not None:
                    self._episode_views.append(dict(view, row=row))
            self._episode_scanned = revision
        return self._episode_views

    def settled_episodes(self, *, actor_id: str | None = None, session: str | None = None,
                         after: str | None = None) -> list[dict[str, Any]]:
        """Trusted episode claims in commit order, optionally of one served actor or session, or committed after a record.

        `after` is a record id used as a cursor (the driver's last-seen episode record). For the level's pushed input.
        """
        with self.serial:
            floor = self.memory.rowid(after) if after is not None else 0
            return [copy.deepcopy(v) for v in self._episodes() if v['row'] > floor
                    and (actor_id is None or v['actor_id'] == actor_id) and (session is None or v['session'] == session)]

    def _derived(self, actor_id: str, subgoal: dict, extra: list[dict] = ()) -> dict[str, Any] | None:
        """Status, stall and counts of the subgoal over trusted claims committed after it, across all sessions."""
        parameters = self.derivation.get(actor_id)
        if parameters is None:
            return None
        floor = self.memory.rowid(subgoal['id'])
        views = [v for v in self._episodes() if v['row'] > floor] + list(extra)
        return derive(subgoal, views, **parameters)

    def _settled_end(self, actor_id: str) -> int:
        """The end position of the served actor's newest settled episode in this session, whatever its outcome, else 0."""
        for view in reversed(self._episodes()):
            if view['actor_id'] == actor_id and view['session'] == self.runtime.session:
                return view['last_position']
        return 0

    def _overlapping(self, actor_id: str, first: int, last: int) -> dict[str, Any] | None:
        for view in self._episodes():
            if (view['actor_id'] == actor_id and view['session'] == self.runtime.session
                    and view['first_position'] <= last and first <= view['last_position']):
                return view
        return None

    def bind_level(self, level_id: str) -> dict[str, Any]:
        """Bind a level pass's position and subgoal, under `Application.serial`, replacing a log read.

        The position is the end of the served actor's newest settled episode in this session, or 0 before any has
        settled; recalled earlier-session records never bind. The subgoal is the current level subgoal's id, or
        None. A served actor that has handed off binds nothing, so the pass's commit is discarded.
        """
        with self.serial:
            state = self._reader(level_id, 'level')
            self._remember_ok()
            actor = state['serves']
            if self.runtime.actor_stage(actor) != 'active':
                state.update(bound=None, subgoal_id=None)
                return dict(position=None, subgoal_id=None, pass_index=state['passes'], handoff=True)
            subgoals = self.level_subgoals()
            state.update(bound=self._settled_end(actor), subgoal_id=subgoals[-1]['id'] if subgoals else None,
                         passes=state['passes'] + 1)
            return dict(position=state['bound'], subgoal_id=state['subgoal_id'], pass_index=state['passes'], handoff=False)

    def release_reader(self, reader_id: str) -> None:
        """Forget a reader's binding at the end of its pass, so a late call from a finished host changes nothing."""
        with self.serial:
            state = self.readers[reader_id]
            if state['role'] == 'level':
                state.update(bound=None, subgoal_id=None)
            else:
                state['episode'] = None

    def bind_episode(self, recorder_id: str, *, first_position: int, last_position: int,
                     subgoal_id: str | None) -> dict[str, Any]:
        """Bind a recorder pass to one closed episode, under `Application.serial`; the driver pushes what this returns.

        The episode is the served actor's operations at positions first..last. `subgoal_id` is the level subgoal
        current at its first input, or None. The recorder may cite only the returned `sources`: the result frames of
        those operations, led by the baseline frame (the newest result frame before the episode, if any).
        """
        with self.serial:
            state = self._reader(recorder_id, 'recorder')
            self._remember_ok()
            actor = state['serves']
            total = self.runtime.store.actor_counts(actor)[0]
            bounded_integer(first_position, 1, total or 1)
            bounded_integer(last_position, first_position, total or 1)
            if total < 1:
                raise PlayerError('The served actor has no operations to form an episode')
            if self._overlapping(actor, first_position, last_position) is not None:
                raise PlayerError('This episode overlaps one that already settled; every episode settles exactly once')
            subgoal = self._pushed_subgoal(subgoal_id)
            entries = self.runtime.store.actor_log(actor, first_position - 1, last_position - first_position + 1)
            baseline = next((e['source_id'] for e in reversed(self.runtime.store.actor_log(actor, 0, first_position - 1))
                             if e['source_id']), None) if first_position > 1 else None
            sources = list(dict.fromkeys([*([baseline] if baseline else []), *(e['source_id'] for e in entries if e['source_id'])]))
            expected = subgoal['data']['expected_observations'] if subgoal else []
            state['episode'] = dict(first_position=first_position, last_position=last_position, subgoal_id=subgoal_id,
                                    expected=len(expected), sources=sources)
            return dict(first_position=first_position, last_position=last_position, operations=entries,
                        baseline_source=baseline, sources=sources,
                        subgoal=None if subgoal is None else dict(record_id=subgoal['id'], text=subgoal['text'],
                                                                  expected_observations=list(expected)))

    def _pushed_subgoal(self, subgoal_id: str | None) -> dict[str, Any] | None:
        if subgoal_id is None:
            return None
        try:
            record = self.memory.read(subgoal_id)
        except PlayerError as exc:
            raise PlayerError(f'Unknown pushed subgoal: {subgoal_id}') from exc
        if record['kind'] != 'work' or record['data'].get('level') != 'subgoal' \
                or record['data'].get('level_contract') != LEVEL_CONTRACT:
            raise PlayerError(f'Record {subgoal_id} is not a {LEVEL_CONTRACT} level subgoal')
        return record

    def settle_episode(self, recorder_id: str, *, first_position: int, last_position: int, subgoal_id: str | None,
                       settled: str, reason: str) -> dict[str, Any]:
        """Settle an episode the driver reports as `failed` or `dropped`, with one claim and no marks.

        The recorder is the record actor, as for its own settles; `data.writer` is stamped `software`. It is
        refused when any settle already covers a position of the episode, so an episode settles exactly once.
        Unlike a recorder call it is not stopped by a failure to remember, so a store that cannot remember can
        still try to record the failure.
        """
        if settled not in SOFTWARE_SETTLES:
            raise PlayerError('Software settles an episode as failed or dropped')
        if type(reason) is not str or not 1 <= len(reason.strip()) or len(reason) > 1024:
            raise PlayerError('A settle reason is 1..1024 characters')
        with self.serial:
            state = self._reader(recorder_id, 'recorder')
            actor = state['serves']
            total = self.runtime.store.actor_counts(actor)[0]
            bounded_integer(first_position, 1, total or 1)
            bounded_integer(last_position, first_position, total or 1)
            if total < 1:
                raise PlayerError('The served actor has no operations to form an episode')
            if self._overlapping(actor, first_position, last_position) is not None:
                raise PlayerError('This episode overlaps one that already settled; every episode settles exactly once')
            self._pushed_subgoal(subgoal_id)
            data = claim_data(session=self.runtime.session, actor_id=actor, first_position=first_position,
                              last_position=last_position, subgoal_id=subgoal_id, settled=settled, reason=reason)
            identity = hashlib.sha256(f'settle:{self.runtime.session}:{actor}:{first_position}'.encode()).hexdigest()[:32]
            value = dict(schema='player-record/1', kind='claim', text=reason, data=data, sources=[], supports=[],
                         supersedes=None, applicability=None, program_id=None)
            with self._remembering():
                (stored,) = self.memory.append_many(recorder_id, [value], request_id=identity, settle=True)
            if state['episode'] is not None and (state['episode']['first_position'], state['episode']['last_position']) \
                    == (first_position, last_position):
                state['episode'] = None
            self.claims = self.memory.query(limit=5)
            return dict(status='settled', settled=settled, record=stored)

    # --- Intent and recall ---

    def _level_of(self, actor_id: str) -> dict[str, Any] | None:
        return next((s for s in self.readers.values() if s['role'] == 'level' and s['serves'] == actor_id), None)

    def intent(self, actor_id: str, *, audience: str = 'tail') -> dict[str, Any]:
        """The current subgoal with its derived status, and software-ranked recall, for `player-intent/2`.

        `audience` is `tail` (the actor's request-only tail: 2 top recall items plus 1 exploration item) or
        `level` (the level's pushed input: the top 10). Fallible data, never authority. Byte truncation of what
        is shown belongs to the host; this emits structured data.
        """
        with self.serial:
            return self._intent(actor_id, audience)

    def _intent(self, actor_id: str, audience: str) -> dict[str, Any]:
        level = self._level_of(actor_id)
        pass_index = level['passes'] if level else 0
        subgoals = self.level_subgoals()
        latest = subgoals[-1] if subgoals else None
        value = dict(schema=INTENT_SCHEMA, session=self.runtime.session, actor_id=actor_id, audience=audience,
                     pass_index=pass_index, subgoal=None, age=None, recall=None, grants_authority=False)
        if latest is not None:
            data = latest['data']
            derived = self._derived(actor_id, latest)
            observed = derived['observations'] if derived else [dict(text=t, status=None) for t in
                                                                data.get('expected_observations') or []]
            value['subgoal'] = dict(record_id=latest['id'], text=latest['text'], sources=latest['sources'],
                status=data.get('status'), confidence=data.get('confidence'), expected_observations=observed,
                stalled=derived['stalled'] if derived else None,
                contradicted=bool(derived['contradicting']) if derived else None,
                counts=derived['counts'] if derived else None)
            same_actor = data.get('actor_id') == actor_id
            # Positions are per actor, so inputs since the commit are known only for the same actor.
            value['age'] = dict(seconds=max(0., time.time() - latest['created_wall']),
                inputs_since_commit=self.runtime.store.inputs_after(actor_id, data['position']) if same_actor else None,
                inputs_by_this_actor=self.runtime.store.inputs_after(actor_id, 0),
                same_actor=same_actor, same_session=data.get('session') == self.runtime.session)
        candidates = [v for v in self._episodes() if v['settled'] == 'recorded']
        ranked = recall.rank(candidates, recall.query_text(latest))
        items = recall.select(ranked, audience=audience, session=self.runtime.session, pass_index=pass_index)
        value['recall'] = dict(basis='ranked' if latest is not None else 'recent', items=[
            dict({k: item['episode'][k] for k in ('record_id', 'session', 'first_position', 'last_position', 'subgoal_id',
                                                  'attempted', 'counterpart', 'residual', 'changed', 'observation_status',
                                                  'confidence', 'sources')},
                 first_source=item['episode']['sources'][0] if item['episode']['sources'] else None,
                 same_session=item['episode']['session'] == self.runtime.session, score=item['score'],
                 exploration=item['exploration']) for item in items])
        return value

    def subgoal_counts(self, actor_id: str) -> list[dict[str, Any]]:
        """Per level subgoal, history included: its episodes, seen and contradicted observations, closures and failures."""
        with self.serial:
            parameters = self.derivation.get(actor_id)
            if parameters is None:
                raise ControlError('This actor has no reader, so no stall test or confidence floor')
            closures = {r['supersedes'] for r in self.memory.level_records('correction', 'subgoal')
                        if r['data'].get('by') == 'software'}
            counted = []
            for work in self.memory.level_records('work', 'subgoal'):
                derived = self._derived(actor_id, work)
                counts = derived['counts']
                counted.append(dict(subgoal_id=work['id'], episodes=counts['episodes'], seen=counts['seen'],
                                    contradicted=counts['contradicted'], closures=int(work['id'] in closures),
                                    failures=counts['failed']))
            return counted

    # --- The level's terminal calls ---

    def _level_state(self, tool: str, args: dict[str, Any], subgoals: list[dict[str, Any]]) -> str | None:
        """The fixable wrong-state error for a call, naming the current subgoal state and the valid tool; else None."""
        if subgoals:
            current = subgoals[-1]
            state = f'The current subgoal is {current["id"]} ({current["data"].get("status")}): "{current["text"][:80]}".'
        else:
            state = 'There is no current subgoal.'
        if tool in ('player_level_keep', 'player_level_close') and not subgoals:
            return (f'{state} {tool} needs a current subgoal. Call player_level_replace with previous_outcome "none" '
                    f'and previous_reason "" to set one, or player_level_abstain.\n{LEVEL_FIX_LINE}')
        if tool == 'player_level_replace':
            outcome, reason = args['previous_outcome'], args['previous_reason']
            if outcome == 'none' and subgoals:
                return (f'{state} previous_outcome "none" is only valid when there is no current subgoal. Set '
                        'previous_outcome to achieved, failed, abandoned or revised with a previous_reason, or call '
                        f'player_level_keep or player_level_close.\n{LEVEL_FIX_LINE}')
            if outcome != 'none' and not subgoals:
                return (f'{state} previous_outcome must be "none" (with previous_reason "") when there is nothing to '
                        f'replace.\n{LEVEL_FIX_LINE}')
            if outcome != 'none' and not reason.strip():
                return (f'{state} previous_reason must say why it was {outcome}; it may be empty only with '
                        f'previous_outcome "none".\n{LEVEL_FIX_LINE}')
        return None

    def _stalled_error(self, tool: str, subgoal: dict, derived: dict) -> str:
        return (f'The current subgoal {subgoal["id"]} is stalled: its last {derived["no_progress_settles"]} settled '
                f'episodes showed nothing newly seen. {tool} is not available while it is stalled; call '
                f'player_level_replace or player_level_close.\n{LEVEL_FIX_LINE}')

    def _contradiction_error(self, subgoal: dict, derived: dict, cited: list[str]) -> str | None:
        """A keep over a contradicted observation must cite a frame of a counted episode record with that mark."""
        if not derived['contradicting']:
            return None
        allowed = list(dict.fromkeys(s for c in derived['contradicting'] for s in c['sources']))
        if set(cited) & set(allowed):
            return None
        index = derived['contradicting'][0]['index'] + 1
        options = (f'Cite one of: {", ".join(s[:64] for s in allowed[:4])}.' if allowed else
                   'None of those records cites a frame, so keep is not available.')
        return (f'The current subgoal {subgoal["id"]} has a contradicted expected observation (number {index}). A keep '
                f'must cite a frame of a counted episode record that contradicts it. {options} Or call '
                f'player_level_replace or player_level_close.\n{LEVEL_FIX_LINE}')

    def _check_citations(self, cited: list[str]) -> None:
        """A terminal call's cited frames must exist; the refusal names the missing ids and the valid action."""
        missing = [s for s in cited if not self.runtime.store.has_source(s) and not self._has_player_source(s)]
        if missing:
            shown = ', '.join(s[:64] for s in missing[:4]) + (f' and {len(missing) - 4} more' if len(missing) > 4 else '')
            raise PlayerError(f'Cited sources are unavailable: {shown}. Cite only source ids that appeared in your '
                              f'pushed input or that player_source returned, or give sources as [].\n{LEVEL_FIX_LINE}')

    def level_call(self, reader_id: str, tool: str, args: dict[str, Any], identity: str) -> dict[str, Any]:
        """One keep, replace or close: the pass's single terminal call, timely-checked and then committed or discarded."""
        state = self._reader(reader_id, 'level')
        self._remember_ok()
        prior = self.memory._db.execute('SELECT actor,tool,args,result FROM service_operations WHERE id=?',
                                        (identity,)).fetchone()
        if prior:
            # A retained identity collects its original commit; it never re-binds or recommits.
            if prior[:3] != (reader_id, tool, player_canonical(args)) or prior[3] is None:
                raise PlayerError('Original level-commit identity conflicts')
            return self.memory.service_result(identity, reader_id)['value']
        action = tool.removeprefix('player_level_')
        actor, bound, pushed = state['serves'], state['bound'], state['subgoal_id']
        # Fixable errors are tool errors and keep the bound for a resubmission.
        args = level_arguments(tool, args)
        subgoals = self.level_subgoals()
        current = subgoals[-1]['id'] if subgoals else None
        channel = self.runtime.channel

        def position(inputs_since):
            return dict(position=bound, inputs_since=inputs_since, staleness_inputs=state['staleness_inputs'],
                        subgoal_id=pushed)

        def discard(reason, inputs_since):
            # A discard is returned to the level's host trace and never written to either store. It ends the pass.
            state.update(bound=None, subgoal_id=None)
            return dict(schema=LEVEL_COMMIT_SCHEMA, status='discarded', action=action, reason=reason,
                        **position(inputs_since), records=[], kept=[])
        if bound is not None and pushed != current:
            # A closure or a replace happened since the pass began: what the level saw is no longer the subgoal.
            return discard(STALE_SUBGOAL,
                           self.runtime.store.inputs_after(actor, bound))
        wrong = self._level_state(tool, args, subgoals)
        if wrong is not None:
            raise PlayerError(wrong)
        derived = self._derived(actor, subgoals[-1]) if subgoals else None
        if action == 'keep' and derived is not None:
            if derived['stalled']:
                raise PlayerError(self._stalled_error(tool, subgoals[-1], derived))
            refusal = self._contradiction_error(subgoals[-1], derived, args['sources'])
            if refusal is not None:
                raise PlayerError(refusal)
        # A replace that supersedes a current subgoal also writes the correction carrying its outcome.
        outcome = args.get('previous_outcome', args.get('outcome'))
        corrected = current is not None and action != 'keep'
        cited = list(dict.fromkeys(args['sources']))
        self._check_citations(cited)
        # Exact bytes are read (and integrity-checked) before the pass can end; they are
        # registered inside the commit transaction, never piecemeal.
        # A keep writes no record, so it registers no frame bytes: it only checks its citations are available.
        blobs = [] if action == 'keep' else [self.runtime.source(s) for s in cited if not self._has_player_source(s)]
        self._cannot_remember_sources(blobs)
        # A timeliness check ends the pass, committed or discarded: the next one must be bound again.
        moved = self.runtime.store.inputs_after(actor, bound) if bound is not None else None
        reason = ('No position was bound for this pass' if bound is None
                  # A user Pause or takeover changes the game without custodian input.
                  else 'Run stopped or fenced since the pass began' if channel.stopped.is_set() or channel.fault is not None
                  or time.monotonic() >= self.runtime.deadline
                  else 'Served actor handed off since the pass began' if self.runtime.actor_stage(actor) != 'active'
                  else 'Served actor moved at least S inputs past the bound' if moved >= state['staleness_inputs']
                  else None)
        if reason is not None:
            return discard(reason, moved)
        state.update(bound=None, subgoal_id=None)
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
        result = dict(schema=LEVEL_COMMIT_SCHEMA, status='committed', action=action, reason=None, **position(moved),
                      derived=None if derived is None else dict(
                          observations=[o['status'] for o in derived['observations']], stalled=derived['stalled']),
                      kept=[current] if action == 'keep' else [])
        with self._remembering():
            records = self.memory.append_many(reader_id, values, request_id=identity,
                                              service=(tool, args, result), sources=blobs)
        self.claims = self.memory.query(limit=5)
        return dict(result, records=records)

    def level_abstain(self, reader_id: str, args: dict[str, Any]) -> dict[str, Any]:
        """End a pass with no change: nothing is written and, like a terminal call, it clears the bound.

        Refused as a fixable error while the current subgoal is stalled, which keeps the bound.
        """
        state = self._reader(reader_id, 'level')
        self._remember_ok()
        args = level_arguments('player_level_abstain', args)
        subgoals = self.level_subgoals()
        derived = self._derived(state['serves'], subgoals[-1]) if subgoals else None
        if derived is not None and derived['stalled']:
            raise PlayerError(self._stalled_error('player_level_abstain', subgoals[-1], derived))
        self._check_citations(list(dict.fromkeys(args['sources'])))
        state.update(bound=None, subgoal_id=None)
        return dict(schema=LEVEL_ABSTAIN_SCHEMA, status='abstained', reason_code=args['reason_code'],
                    reason=args['reason'])

    # --- The recorder's terminal calls ---

    def episode_call(self, recorder_id: str, tool: str, args: dict[str, Any], identity: str) -> dict[str, Any]:
        """The recorder's one call for its bound episode: it writes the claim that settles the episode, or is refused.

        A closure is appended in the same transaction as the record that makes every expected observation seen.
        """
        state = self._reader(recorder_id, 'recorder')
        self._remember_ok()
        prior = self.memory._db.execute('SELECT actor,tool,args,result FROM service_operations WHERE id=?',
                                        (identity,)).fetchone()
        if prior:
            if prior[:3] != (recorder_id, tool, player_canonical(args)) or prior[3] is None:
                raise PlayerError('Original episode-settle identity conflicts')
            return self.memory.service_result(identity, recorder_id)['value']
        bound = state['episode']
        if bound is None:
            raise PlayerError('No episode is bound to this pass, so there is nothing to settle')
        args = level_arguments(tool, args)
        actor, first, last = state['serves'], bound['first_position'], bound['last_position']
        if self._overlapping(actor, first, last) is not None:
            state['episode'] = None
            raise PlayerError('This episode already settled; every episode settles exactly once')
        cited = list(dict.fromkeys(args['sources']))
        foreign = [s for s in cited if s not in bound['sources']]
        if foreign:
            raise PlayerError('Cited sources are not frames of this episode: ' + ', '.join(s[:64] for s in foreign[:4])
                              + '. Cite only ids from the pushed episode (at most 4), or give sources as [].\n' + LEVEL_FIX_LINE)
        recorded = tool == 'player_episode_record'
        if recorded and len(args['observation_status']) != bound['expected']:
            wanted = (f'{bound["expected"]} entries (one per expected observation of the pushed subgoal)'
                      if bound['expected'] else 'empty (no subgoal was pushed)')
            raise PlayerError(f'observation_status must be {wanted}, but has {len(args["observation_status"])}.\n{LEVEL_FIX_LINE}')
        blobs = [self.runtime.source(s) for s in cited if not self._has_player_source(s)]
        self._cannot_remember_sources(blobs)
        ids = self.memory.batch_ids(identity, 2)
        fields = (dict(attempted=args['attempted'], counterpart=args['counterpart'],
                       observation_status=args['observation_status'], residual=args['residual'],
                       changed=args['changed'], confidence=args['confidence'])
                  if recorded else dict(reason_code=args['reason_code'], reason=args['reason']))
        data = claim_data(session=self.runtime.session, actor_id=actor, first_position=first, last_position=last,
                          subgoal_id=bound['subgoal_id'], settled='recorded' if recorded else 'abstained', **fields)
        claim = dict(schema='player-record/1', kind='claim', text=args['attempted'] if recorded else args['reason'],
                     data=data, sources=cited, supports=[], supersedes=None, applicability=None, program_id=None)
        values, closure, derived, counted = [claim], None, None, False
        subgoals = self.level_subgoals()
        if subgoals and bound['subgoal_id'] == subgoals[-1]['id'] and self.derivation.get(actor) is not None:
            goal = subgoals[-1]
            before = self._derived(actor, goal)
            candidate = episode(dict(claim, id=ids[0], created_wall=time.time()))
            derived = self._derived(actor, goal, [dict(candidate, row=math.inf)])
            counted = recorded and derived['counts']['counted'] > before['counts']['counted']
            if derived['all_seen'] and not before['all_seen']:
                supports, closing_sources = closure_evidence(derived)
                closure = dict(schema='player-record/1', kind='correction',
                    text='Every expected observation was seen in the counted episode records.',
                    data=dict(level='subgoal', level_contract=LEVEL_CONTRACT, actor_id=actor,
                              session=self.runtime.session, position=last, outcome='achieved', by='software'),
                    sources=closing_sources, supports=supports, supersedes=goal['id'], applicability=None,
                    program_id=None)
                values.append(closure)
        schema = EPISODE_RECORD_SCHEMA if recorded else EPISODE_ABSTAIN_SCHEMA
        result = dict(schema=schema, status='recorded' if recorded else 'abstained', settled=data['settled'],
                      first_position=first, last_position=last, subgoal_id=bound['subgoal_id'], counted=counted,
                      closed=closure is not None,
                      observations=None if derived is None else [o['status'] for o in derived['observations']],
                      stalled=None if derived is None else derived['stalled'])
        state['episode'] = None
        with self._remembering():
            try:
                records = self.memory.append_many(recorder_id, values, request_id=identity,
                                                  service=(tool, args, result), sources=blobs, settle=True)
            except BaseException:
                state['episode'] = bound
                raise
        self.claims = self.memory.query(limit=5)
        return dict(result, records=records)

    def status(self) -> dict[str, Any]:
        return dict(self.runtime.status(), host=copy.deepcopy(self.host), player_claims=copy.deepcopy(self.claims),
                    remember_failure=self.remember_failure)

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
        reader_role = 'level' if name in LEVEL_END_TOOLS else 'recorder' if name in RECORDER_END_TOOLS else None
        write = dict(write=name not in READ_TOOLS, reader_role=reader_role)
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
                refuse_custodian_data(value)
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
                return result,None
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
            if name in ('player_level_keep', 'player_level_replace', 'player_level_close'):
                return self.level_call(actor, name, args, identity), None
            if name == 'player_level_abstain':
                return self.level_abstain(actor, args), None
            if name in EPISODE_TOOLS:
                return self.episode_call(actor, name, args, identity), None
            if name == 'player_handoff':
                closed(args, set())
                context_id, sha = self.snapshot(actor)
                return self.runtime.seal_actor(actor, identity, context_id, sha), None
            raise ControlError('Unknown current tool')
