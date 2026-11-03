"""Finite actors of the selected player host over one live mechanical custodian."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Callable

from harness.computer.launch import close_group
from harness.computer.protocol import ControlError,canonical,read_json
from harness.player.contracts import ABSTAIN_CODES,EPISODE_ABSTAIN_CODES,PlayerError
from tools.configure_player_tools import ROOT,configuration
from tools.episode_cutter import CLOSED_BY,Episode,EpisodeCutter,key_tokens,pick_frames,thumbnail
from tools.level_schedule import LevelSchedule

# The pass input the driver hands a reader host on stdin, and its two pushed inputs (ADR-007 level v4).
PASS_INPUT_SCHEMA='player-pass-input/1'
LEVEL_PUSH_SCHEMA='player-level-push/2'
EPISODE_PUSH_SCHEMA='player-episode-push/1'


def write_new(path: Path,value,*,text=False) -> None:
    with path.open('x') as stream:
        stream.write(value if text else canonical(value)+'\n')
    path.chmod(0o600)


class HostEvents:
    """Incremental JSONL; a partial final line never becomes an uncharged request."""
    def __init__(self,path: Path,allowance: int,observer=None):
        self.stream=path.open('rb');self.buffer=b'';self.allowance=allowance
        self.requests=set();self.settled=None;self.handoff=None;self.last_response_wall=None
        self.usage={};self.error=None;self.started=False
        self.observer=observer;self.ordinal=0
        # A level pass's own commit, discard and abstain outcomes, and a recorder pass's record and abstain outcomes.
        self.level=[]
        self.episode=[]
        # Terminal calls whose transport was lost: the pass ended, and the driver reconciles each identity afterwards.
        self.uncertain=[]
        # A recorder pass's terminal call whose transport was lost; the driver reconciles it from the store.
        self.episode_uncertain=[]

    def read(self) -> bool:
        chunk=self.stream.read(1048576)
        if not chunk:return False
        self.buffer+=chunk
        if len(self.buffer)>32*1048576:raise ControlError('Host event line exceeds original telemetry bound')
        lines=self.buffer.split(b'\n');self.buffer=lines.pop()
        for line in lines:
            if not line:continue
            value=json.loads(line)
            self.ordinal+=1
            kind=value.get('type')
            if kind=='host-start':
                if (self.started or value.get('telemetry_version')!=2
                        or value.get('schema')!='player-host/7'):raise ControlError('Unsupported/repeated current host trace')
                self.started=True
            elif kind in ('level-commit','level-discard','level-abstain'):
                if len(self.level)<256:self.level.append({k:value.get(k) for k in
                    ('type','action','reason_code','reason','position','inputs_since','staleness_inputs','record_ids','kept',
                     'subgoal_id','derived')})
            elif kind in ('episode-record','episode-abstain'):
                if len(self.episode)<256:self.episode.append({k:value.get(k) for k in
                    ('type','settled','first_position','last_position','subgoal_id','counted','closed','observations','stalled',
                     'reason_code','reason','record_ids')})
            elif kind=='episode-uncertain':
                if len(self.episode_uncertain)<16:self.episode_uncertain.append({k:value.get(k) for k in ('tool','identity','request_id')})
            elif kind=='level-uncertain':
                if len(self.uncertain)<16:self.uncertain.append({k:value.get(k) for k in ('tool','identity','request_id')})
            elif kind=='request-start':
                match=re.fullmatch(r'request-([1-9][0-9]*)',value.get('request_id',''))
                if not self.started or not match:raise ControlError('Host request lacks current origin')
                identity=int(match.group(1))
                if identity in self.requests or identity>self.allowance:raise ControlError('Host request accounting differs')
                self.requests.add(identity)
            elif kind=='response-complete':
                try:self.last_response_wall=datetime.fromisoformat(value['wall_time'].replace('Z','+00:00')).timestamp()
                except (KeyError,ValueError,TypeError):pass
                if value.get('usage_available') is True:self.usage[value['request_id']]=value['usage']
            elif kind=='handoff':
                if self.handoff is not None:raise ControlError('Repeated host handoff settlement')
                self.handoff=value
            elif kind=='settled':
                if self.settled is not None:raise ControlError('Repeated host terminal event')
                self.settled=value
            if self.observer is not None:
                self.observer(self.ordinal,value)
        return True

    def finish(self) -> dict:
        while self.read():pass
        valid=(not self.buffer and self.started and self.settled is not None
               and self.requests==set(range(1,len(self.requests)+1))
               and self.settled.get('requests')==len(self.requests))
        # Uncertain trace accounting reserves the entire original host allocation.
        return dict(observed_attempts=len(self.requests),attempts_charged=len(self.requests) if valid else self.allowance,
            accounting_complete=valid,settled=self.settled,handoff=self.handoff,level_events=self.level,episode_events=self.episode,
            level_uncertain=list(self.uncertain),episode_uncertain=list(self.episode_uncertain),configured_estimate_usd=sum(v.get('cost',{}).get('total',0) for v in self.usage.values()),
            usage_available_attempts=len(self.usage),missing_usage_attempts=len(self.requests)-len(self.usage))

    def close(self):self.stream.close()


def _handoff_context(application,actor,event):
    if event['actor_id']!=actor['actor_id'] or event['session']!=application.runtime.session:
        raise ControlError('Host handoff names a different actor/session')
    result=application.runtime.store.operation(event['handoff_id'],actor['actor_id'])
    issuance=result['handoff']
    if (result['kind']!='handoff' or result['status']!='sealed' or not isinstance(issuance,dict)
            or issuance['context_id']!=event['context_id'] or issuance['context_sha256']!=event['context_sha256']):
        raise ControlError('Host hint does not match canonical handoff issuance')
    path=application.context_directory/(issuance['context_id']+'.json')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=issuance['context_sha256']:
        raise ControlError('Frozen handoff context changed')
    packet=json.loads(data)
    if (packet.get('schema')!='player-handoff-context/2' or packet.get('context_id')!=issuance['context_id']
            or packet.get('actor_id')!=actor['actor_id'] or packet.get('grants_authority') is not False):
        raise ControlError('Frozen handoff context is not current mechanical identity')


BRIEF_MARK = '\n\nMission brief (the same the acting player has):\n'


def _lines(values: list) -> str:
    return '\n'.join(json.dumps(v, separators=(',', ':'), ensure_ascii=False) for v in values) or '(none)'


def wake_note(wake: dict) -> str:
    """Mechanical wake facts only; the frozen role prompt and the actor's own brief carry everything else."""
    return 'Software pass note: ' + ', '.join(f'{k.replace("_", " ")} {v}' for k, v in wake.items()) + '.'


def level_text(role_prompt: str, brief: str, wake: dict, pushed: dict) -> str:
    """A level pass's whole stdin, plain text (`player-host/7`): the frozen role, the actor's brief and the pushed input.

    The pushed input is closed episodes and software counts, never the actor's raw log: the episode records since the
    previous pass, the current subgoal with its derived status, stalled flag and id, the counts per subgoal and the
    recalled episodes. The role prompt leads, so a replay can swap it for the current frozen version at `BRIEF_MARK`.
    """
    intent = pushed['intent']
    subgoal = 'none' if intent['subgoal'] is None else json.dumps(dict(intent['subgoal'], age=intent['age']),
                                                                   separators=(',', ':'), ensure_ascii=False)
    return (role_prompt + BRIEF_MARK + brief
            + '\n\nEpisodes settled since your last pass, oldest first, one per line (positions are the served actor\'s):\n'
            + _lines(pushed['episodes'])
            + f'\n\nCurrent subgoal (id, derived status of each expected observation, stalled flag): {subgoal}'
            + '\n\nCounts per subgoal, history included:\n' + _lines(pushed['counts'])
            + f'\n\nRecalled episodes ({intent["recall"]["basis"]}), software-ranked, best first:\n' + _lines(intent['recall']['items'])
            + '\n\n' + wake_note(wake))


def recorder_document(role_prompt: str, wake: dict, pushed: dict) -> dict:
    """A recorder pass's whole stdin, one closed JSON document (`player-pass-input/1`, `player-host/7`).

    `text` is the frozen `episode-v1` role prompt, the episode's operations as key tokens and positions, and the id, text
    and ordered expected observations of the subgoal pushed. `frames` names the baseline and the episode's own frames
    (at most 7, in capture order, baseline first) by source id and role; no image is inlined, because the host fetches
    each frame itself through `player_source`.
    """
    subgoal = pushed['subgoal']
    text = (role_prompt + f'\n\nEpisode: positions {pushed["first_position"]} to {pushed["last_position"]} of the served log, '
            f'{pushed["inputs"]} inputs, closed by {pushed["closed_by"]}. Operations, one per line:\n' + _lines(pushed['operations'])
            + '\n\nSubgoal current when the episode began: '
            + ('none' if subgoal is None else json.dumps(subgoal, separators=(',', ':'), ensure_ascii=False))
            + '\n\nCitable source ids: ' + ', '.join(pushed['sources']) + '\n\n' + wake_note(wake))
    return dict(schema=PASS_INPUT_SCHEMA, text=text,
                frames=[dict(source_id=f['source_id'], role=f['frame_role']) for f in pushed['frames']])


def level_push(application, level_id: str, actor_id: str, session: str, cursor: str | None) -> tuple[dict, str | None, dict]:
    """A level pass's pushed input and its new episode cursor, in one hold of the application lock.

    The bind (the position and the current subgoal id) and everything shown are read together, so what the level sees
    and what the custodian will check its commit against are one state. The episodes are the served actor's records
    committed since the previous pass's cursor, whatever their outcome; the intent carries the current subgoal with its
    derived status and the recalled episodes; the counts are per subgoal. Returns the pushed dict, the cursor, and the
    bind (its `handoff` is True when the actor has already handed off, which launches nothing).
    """
    with application.serial:
        bind = application.bind_level(level_id)
        if bind['handoff']:
            return {}, cursor, bind
        episodes = application.settled_episodes(actor_id=actor_id, session=session, after=cursor)
        intent = application.intent(actor_id, audience='level')
        counts = application.subgoal_counts(actor_id)
    pushed = dict(schema=LEVEL_PUSH_SCHEMA, bound=dict(position=bind['position'], subgoal_id=bind['subgoal_id']),
                  episodes=[{k: v for k, v in e.items() if k != 'row'} for e in episodes], intent=intent, counts=counts)
    return pushed, episodes[-1]['record_id'] if episodes else cursor, bind


def episode_push(application, recorder_id: str, episode: Episode) -> dict:
    """A recorder pass's pushed input for one closed episode, bound under the application lock.

    The frames are the baseline (the result capture of the last input before the episode) and up to six of the
    episode's own frames (always the last, then the largest thumbnail distance from the predecessor, in capture
    order), each marked with its source id and role (baseline, in-episode or last). A source id appears once. A repeat of
    an earlier entry is dropped, except that a repeat which is the `last` frame keeps its place as `last` and replaces the
    earlier entry, so the list is always the host's `parsePassInput` shape: the baseline first, if any, then the
    in-episode frames ending in exactly one `last`.
    """
    with application.serial:
        bound = application.bind_episode(recorder_id, first_position=episode.first_position,
                                         last_position=episode.last_position, subgoal_id=episode.subgoal_id)
    wanted = [(bound['baseline_source'], 'baseline')] if bound['baseline_source'] else []
    wanted += [(source, role) for _, source, role in pick_frames(episode)]
    frames = []
    for source, role in wanted:
        earlier = next((frame for frame in frames if frame['source_id'] == source), None)
        if earlier is None:
            frames.append(dict(source_id=source, frame_role=role))
        elif role == 'last':
            frames.remove(earlier)
            frames.append(dict(source_id=source, frame_role=role))
    operations = [dict(position=e['position'], operation_id=e['operation_id'], kind=e['kind'], status=e['status'],
                       source_id=e['source_id'], tokens=key_tokens(e['actions'])) for e in bound['operations']]
    return dict(schema=EPISODE_PUSH_SCHEMA, first_position=bound['first_position'], last_position=bound['last_position'],
                inputs=episode.inputs, closed_by=episode.closed_by, operations=operations, subgoal=bound['subgoal'],
                frames=frames, sources=bound['sources'])


class ReaderLane:
    """One reader role's finite host passes: at most one in flight, each charged like an actor's host."""
    def __init__(self, role: str, target: Path, directory: Path, application, reader: dict, route: dict, profile: dict,
                 secret: str, allowance: int, limits: dict, role_prompt: str, brief: str | None):
        self.role, self.target, self.directory, self.application = role, target, directory, application
        self.route, self.profile, self.secret, self.allowance, self.limits = route, profile, secret, allowance, limits
        self.role_prompt, self.brief = role_prompt, brief
        self.reader_id = reader['actor_id']
        target.mkdir(mode=0o700)
        self.reader_file = target / 'reader.json'
        write_new(self.reader_file, dict(schema='player-adapter/1', base_url=f"http://127.0.0.1:{profile['port']}",
                                         session=profile['session'], **reader))
        self.passes = []
        self.charged = 0
        self.current = None
        # Called in one hold of the application lock when a pass has ended and been charged: (record).
        self.on_finish = None

    @property
    def busy(self) -> bool:
        return self.current is not None

    def remaining(self) -> int:
        return self.allowance - self.charged

    def can_launch(self, now: float, deadline: float) -> bool:
        return self.current is None and self.remaining() >= 1 and deadline - now >= 30 + self.limits['pass_seconds'] / 4

    def begin(self, now: float, deadline: float) -> dict:
        """Reserve the next pass's directory and its allowance: `dict(index, target, allowance, seconds)`."""
        index = len(self.passes) + 1
        target = self.target / f'{index:03d}'
        target.mkdir(mode=0o700)
        return dict(index=index, target=target, allowance=min(self.limits['pass_max_requests'], self.remaining()),
                    seconds=min(self.limits['pass_seconds'], deadline - now - 30))

    def abandon(self, reservation: dict) -> None:
        """Give back a reservation whose pass will not run, leaving no empty directory behind."""
        shutil.rmtree(reservation['target'], ignore_errors=True)

    def start(self, reservation: dict, stdin: dict | str, meta: dict) -> None:
        """Write the pass's frozen inputs and launch its host with `stdin` (text for a level, a document for a recorder)."""
        target, allowance, seconds = reservation['target'], reservation['allowance'], reservation['seconds']
        record = dict(index=reservation['index'], role=self.role, allocated_attempts=allowance, allocated_seconds=seconds,
                      started_wall=time.time(), **meta)
        write_new(target / 'route.json', dict(self.route, role=self.role, intent_tail_bytes=None, max_requests=allowance))
        write_new(target / 'mcp.json', configuration(str(self.reader_file), profile=self.role))
        # The level shares the acting player's guide (its prompt says actor-addressed text is not for it); the recorder is an
        # observer and gets no guide (ADR-007, no-nudge review on #352), so its context is empty.
        context = '' if self.role == 'recorder' else (self.directory / 'context.txt').read_text()
        write_new(target / 'context.txt', context, text=True)
        name = 'input.txt' if isinstance(stdin, str) else 'input.json'
        write_new(target / name, stdin, text=isinstance(stdin, str))
        write_new(target / 'player-final.txt', '', text=True)
        arguments = [*self.profile['host']['argv'], 'run', '--config', str(target / 'route.json'),
            '--mcp-config', str(target / 'mcp.json'), '--context', str(target / 'context.txt'), '--model', self.route['model']['id'],
            '--effort', self.profile['effort'], '--timeout-seconds', str(seconds), '-o', str(target / 'player-final.txt')]
        environment = dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8',
                           **{self.route['api_key_env']: self.secret})
        with (target / 'host.jsonl').open('x') as output, (target / 'host-stderr.log').open('x') as errors, \
                (target / name).open() as pass_input:
            child = subprocess.Popen(arguments, cwd=ROOT, env=environment, stdin=pass_input, stdout=output, stderr=errors,
                                     start_new_session=True)
        # Owned before anything else can fail, so a later error still closes and charges it.
        self.current = (child, None, record, time.monotonic() + seconds)
        write_new(target / 'host-process.json', dict(pid=child.pid, pgid=child.pid, argv=arguments))
        self.current = (child, HostEvents(target / 'host.jsonl', allowance), record, self.current[3])

    def advance(self, stop: bool) -> bool:
        """Read the pass's trace; close and charge it when its host exited, `stop` is set or its time is up."""
        if self.current is None:
            return False
        child, events, _, ends = self.current
        events.read()
        if child.poll() is not None or stop or time.monotonic() >= ends:
            self.finish()
            return True
        return False

    def finish(self) -> None:
        """Close the pass's exact process group, then charge it; incomplete accounting charges its whole allocation."""
        if self.current is None:
            return
        child, events, record, _ = self.current
        self.current = None
        try:
            record['cleanup'] = close_group(child)
        except Exception as exc:
            record['cleanup'] = dict(process_absent=False, group_absent=False, error=type(exc).__name__)
        try:
            if events is None:
                raise ControlError('Pass trace reader never started')
            record.update(events.finish())
        except Exception as exc:
            record.update(accounting_complete=False, attempts_charged=record['allocated_attempts'], trace_error=type(exc).__name__)
        finally:
            if events is not None:
                events.close()
        # One hold of the lock: a late call from the finished host changes nothing, and the role's own settlement
        # (a level's lost-call reconciliation, a recorder's failed settle) sees the store as the pass left it.
        try:
            with self.application.serial:
                self.application.release_reader(self.reader_id)
                if self.on_finish is not None:
                    self.on_finish(record)
        finally:
            record['ended_wall'] = time.time()
            self.charged += record['attempts_charged']
            self.passes.append(record)
            try:
                write_new(self.target / f"{record['index']:03d}" / 'driver-receipt.json', record)
            except (OSError, ValueError) as exc:
                record['receipt_error'] = type(exc).__name__

    def quiescent(self) -> bool:
        """Every pass's exact process group was confirmed absent; a successor needs this."""
        return self.current is None and all(p.get('cleanup', {}).get('process_absent') is True
                                            and p['cleanup'].get('group_absent') is True for p in self.passes)

    def usage(self) -> dict:
        return dict(configured_estimate_usd=sum(p.get('configured_estimate_usd', 0) for p in self.passes),
                    missing_usage_attempts=sum(p.get('missing_usage_attempts', p['attempts_charged']) for p in self.passes))


def fraction_skip(reason: str, pushed: dict, inputs_since: int, staleness_inputs: int) -> str | None:
    """Fraction eligibility after a real bind; other wake reasons are unchanged."""
    if not reason.startswith('budget-'):
        return None
    intent = pushed['intent']
    if not (pushed['episodes'] or intent['subgoal'] or intent['recall']['items']):
        return 'no meaningful context'
    if inputs_since >= staleness_inputs:
        return 'settled evidence bound already stale'
    return None


class LevelSystem:
    """One actor's episode cutter, episode recorder and subgoal level (ADR-007 level v4).

    The cutter reads the served actor's log and cuts it into episodes; closed episodes wait in a FIFO backlog for the
    recorder, one pass at a time, and the oldest settles as `dropped` when more than the backlog bound are waiting.
    Every closed episode ends with exactly one settle claim in the store (recorded or abstained by the recorder;
    failed or dropped reported here). The level wakes on settles and is pushed what settled since its last pass.
    A failure in either role disables both and is recorded, but never stops or gates the actor.
    """
    def __init__(self, target: Path, directory: Path, application, actor: dict, level: dict, route: dict, profile: dict,
                 secret: str, allowances: tuple[int, int], actor_allowance: int):
        self.application, self.level, self.profile = application, level, profile
        self.actor_id, self.session = actor['actor_id'], profile['session']
        derived = dict(stall_settles=level['stall_settles'], confidence_floor=level['confidence_floor'])
        level_reader = application.add_reader(self.actor_id, 'level', staleness_inputs=level['staleness_inputs'], **derived)
        recorder_reader = application.add_reader(self.actor_id, 'recorder', **derived)
        brief = (directory / 'prompt.txt').read_text()
        self.level_lane = ReaderLane('level', target / 'level', directory, application, level_reader, route, profile, secret,
                                     allowances[0], level, (directory / 'level-role.txt').read_text().strip(), brief)
        self.recorder_lane = ReaderLane('recorder', target / 'recorder', directory, application, recorder_reader, route,
                                        profile, secret, allowances[1], level['recorder'],
                                        (directory / 'episode-role.txt').read_text().strip(), None)
        self.level_lane.on_finish = self._level_finished
        self.recorder_lane.on_finish = self._recorder_finished
        self.reader_id = self.level_lane.reader_id
        self.recorder_id = self.recorder_lane.reader_id
        self.schedule = LevelSchedule(tuple(level['budget_fractions']), actor_allowance)
        self.cutter = EpisodeCutter(level['theta'], level['min_episode_inputs'], level['episode_cap'], self._thumbnail)
        self.backlog = level['recorder']['backlog']
        # Closed episodes waiting for the recorder, oldest first; the one in flight is not waiting.
        self.queue: deque[Episode] = deque()
        self.inflight: Episode | None = None
        self.cuts: list[Episode] = []
        # The level's cursor over settled episodes (its last pushed record), and how many have settled in all.
        self.level_cursor: str | None = None
        self.wake_skips: list[dict] = []
        self.seen_cursor: str | None = None
        self.settled_total = 0
        self.max_waiting = 0
        self.failure: str | None = None
        self.edge_closed = False

    # --- reading the log ---

    def _thumbnail(self, source_id: str) -> bytes:
        return thumbnail(self.application.runtime.store.read_source(source_id)[1])

    def _ingest(self, final: bool) -> None:
        """Feed the cutter every operation of the served actor's log that is ready, in order.

        An input whose result is still in flight (the last entry, pending) waits; one that is not last and still has
        no result is lost, so it has no distance and cannot close an episode. `final` feeds everything.
        """
        store = self.application.runtime.store
        while True:
            entries = store.actor_log(self.actor_id, self.cutter.next_position - 1, 200)
            if not entries:
                return
            subgoal = None
            with self.application.serial:
                current = self.application.level_subgoals()
                subgoal = current[-1]['id'] if current else None
            for entry in entries:
                if entry['status'] == 'pending' and not final and entry['position'] == store.actor_counts(self.actor_id)[0]:
                    # The log's last entry, still in flight: it waits for its capture, whatever the batch boundary.
                    return
                for episode in self.cutter.feed(entry, subgoal):
                    self._enqueue(episode)
            if len(entries) < 200:
                return

    def _enqueue(self, episode: Episode) -> None:
        self.cuts.append(episode)
        self.queue.append(episode)
        # More than the bound waiting: the oldest waiting episode settles as dropped.
        while len(self.queue) > self.backlog:
            dropped = self.queue.popleft()
            self._settle(dropped, 'dropped', f'Recorder backlog: more than {self.backlog} closed episodes were waiting')
        self.max_waiting = max(self.max_waiting, len(self.queue))

    # --- settling through the custodian ---

    def _settled(self, episode: Episode) -> bool:
        return any(v['first_position'] == episode.first_position
                   for v in self.application.settled_episodes(actor_id=self.actor_id, session=self.session))

    def _settle(self, episode: Episode, settled: str, reason: str) -> None:
        """Report a failed or dropped episode to the custodian: exactly one settle claim, with no marks."""
        with self.application.serial:
            if self._settled(episode):
                return
            self.application.settle_episode(self.recorder_id, first_position=episode.first_position,
                last_position=episode.last_position, subgoal_id=episode.subgoal_id, settled=settled, reason=reason)

    def _recorder_finished(self, record: dict) -> None:
        episode, self.inflight = self.inflight, None
        if episode is None:
            return
        # A lost terminal call is reconciled from the store: the episode's settle claim is what it did.
        views = [v for v in self.application.settled_episodes(actor_id=self.actor_id, session=self.session)
                 if v['first_position'] == episode.first_position]
        record['episode_uncertain'] = [dict(e, outcome='committed' if views and views[0]['writer'] == 'recorder' else 'absent')
                                       for e in record.get('episode_uncertain', [])]
        if views:
            return
        ended = (record.get('settled') or {}).get('reason') or record.get('trace_error') or 'no settled event'
        self._settle(episode, 'failed', f'The recorder pass ended without settling the episode ({ended})')

    def _level_finished(self, record: dict) -> None:
        # A lost terminal call can still be waiting on the application's serial lock in a handler thread. In this one
        # hold of that lock every identity with no row is tombstoned (a row with no result, which `level_call`
        # refuses as an identity conflict), so a late arrival changes nothing; then each is reconciled.
        uncertain = record.get('level_uncertain', [])
        tombstoned = {e['identity'] for e in uncertain if isinstance(e.get('identity'), str)
                      and self.application.memory.tombstone_service(e['identity'], self.level_lane.reader_id, str(e.get('tool')))}
        record['level_uncertain'] = [self.reconcile(e, e.get('identity') in tombstoned) for e in uncertain]

    def reconcile(self, event: dict, tombstoned: bool = False) -> dict:
        """What a terminal call whose response was lost did, read from the store's `service_operations` row.

        `committed` when a row with a result exists (it commits in the same transaction as the call's records).
        `absent` when there is no row, or when the pass tombstoned the identity because there was none: a discard
        writes no row, so a discarded call and one that never arrived are both `absent`, and neither changed the
        store or the current subgoal. The identity is reported unchanged and never replayed.
        """
        identity = event.get('identity')
        outcome = dict(event, outcome='unreconciled')
        if not isinstance(identity, str):
            return outcome
        if tombstoned:
            return dict(outcome, outcome='absent', action=None, record_ids=[])
        with self.application.serial:
            row = self.application.memory._db.execute('SELECT actor,tool,result FROM service_operations WHERE id=?', (identity,)).fetchone()
        if row is None:
            return dict(outcome, outcome='absent', action=None, record_ids=[])
        if row[0] != self.level_lane.reader_id or row[1] != event.get('tool') or row[2] is None:
            return outcome
        result = json.loads(row[2])
        return dict(outcome, outcome=result.get('status'), action=result.get('action'),
                    record_ids=[r['id'] for r in result.get('records', [])])

    # --- the poll ---

    def poll(self, actor_events: 'HostEvents', hard_stop: bool, deadline: float) -> None:
        """A failure of the cutter, recorder or level disables further passes but never stops or gates its actor."""
        if self.failure:
            return
        try:
            self._poll(actor_events, hard_stop, deadline,
                       ending=hard_stop or actor_events.handoff is not None or actor_events.settled is not None)
        except Exception as exc:
            self._fail(exc)

    def _fail(self, exc: Exception) -> None:
        self.failure = f'{type(exc).__name__}: {str(exc)[:300]}'
        self.finish()

    def _poll(self, events: 'HostEvents | None', hard_stop: bool, deadline: float, *, ending: bool) -> None:
        now = time.monotonic()
        if self.application.remember_failure is not None:
            raise ControlError(f'Player memory could not remember ({self.application.remember_failure}); the recorder and the '
                               'level stop for this session')
        # The level stops with its actor; the recorder goes on to record the last episodes unless the run is fenced.
        self.level_lane.advance(ending)
        self.recorder_lane.advance(hard_stop)
        self._ingest(final=ending and events is None)
        self._launch_recorder(now, deadline, hard_stop)
        if not ending:
            self._launch_level(events, now, deadline)

    def _launch_recorder(self, now: float, deadline: float, hard_stop: bool) -> None:
        lane = self.recorder_lane
        if hard_stop or lane.busy or not self.queue:
            return
        if lane.remaining() < 1:
            # No pass can run again: every waiting episode still settles exactly once.
            while self.queue:
                self._settle(self.queue.popleft(), 'failed', 'The recorder allowance is exhausted')
            return
        if not lane.can_launch(now, deadline):
            return
        episode = self.queue[0]
        reservation = lane.begin(now, deadline)
        try:
            pushed = episode_push(self.application, self.recorder_id, episode)
        except PlayerError as exc:
            # The custodian refused to bind it (for example, it is already settled): it settles as failed, once.
            lane.abandon(reservation)
            self.queue.popleft()
            self._settle(episode, 'failed', f'The episode could not be bound for the recorder: {str(exc)[:200]}')
            return
        except BaseException:
            lane.abandon(reservation)
            raise
        self.queue.popleft()
        self.inflight = episode
        wake = dict(reason='episode', pass_index=reservation['index'], allowance_requests=reservation['allowance'],
                    allowance_seconds=int(reservation['seconds']), waiting=len(self.queue))
        meta = dict(first_position=episode.first_position, last_position=episode.last_position, inputs=episode.inputs,
                    closed_by=episode.closed_by, subgoal_id=episode.subgoal_id, frames=len(pushed['frames']))
        lane.start(reservation, recorder_document(lane.role_prompt, wake, pushed), meta)

    def _carried(self) -> int:
        """What earlier sessions left for a start pass to revalidate: current level subgoals plus recalled episodes."""
        with self.application.serial:
            earlier = [v for v in self.application.settled_episodes(actor_id=None)
                       if v['session'] != self.session and v['settled'] == 'recorded']
            return len(self.application.level_subgoals()) + len(earlier)

    def _launch_level(self, events: 'HostEvents', now: float, deadline: float) -> None:
        lane = self.level_lane
        # The actor's first request follows its tool discovery and checks, so it is ready.
        if lane.busy or not events.requests or not lane.can_launch(now, deadline):
            return
        with self.application.serial:
            fresh = self.application.settled_episodes(actor_id=self.actor_id, session=self.session, after=self.seen_cursor)
            if fresh:
                self.seen_cursor = fresh[-1]['record_id']
                self.settled_total += len(fresh)
            reason = self.schedule.due(settled=self.settled_total, attempts=len(events.requests),
                                       carried=0 if self.schedule.started else self._carried())
            if reason is None:
                return
            pushed, cursor, bind = level_push(self.application, lane.reader_id, self.actor_id, self.session, self.level_cursor)
            if bind['handoff']:
                # The served actor has already handed off: nothing to bind, so no pass.
                return
            # Fractions reconsider existing context without inventing a newer evidence position. A skipped
            # binding consumes no lane allowance and preserves the pending delta for the next real pass.
            if reason.startswith('budget-'):
                moved = self.application.runtime.store.inputs_after(self.actor_id, bind['position'])
                skip = fraction_skip(reason, pushed, moved, self.level['staleness_inputs'])
                if skip is not None:
                    self.application.release_reader(lane.reader_id)
                    self.wake_skips.append(dict(reason=reason, skip=skip, position=bind['position'],
                        binding_index=bind['pass_index'], inputs_since=moved,
                        staleness_inputs=self.level['staleness_inputs'], actor_attempts=len(events.requests),
                        settled_episodes=self.settled_total))
                    return
            reservation = lane.begin(now, deadline)
            self.level_cursor = cursor
            entries, inputs = self.application.runtime.store.actor_counts(self.actor_id)
        wake = dict(reason=reason, pass_index=reservation['index'], settled_episodes=self.settled_total,
                    allowance_requests=reservation['allowance'], allowance_seconds=int(reservation['seconds']))
        meta = dict(reason=reason, log_entries=entries, actor_inputs=inputs, bound=pushed['bound'],
                    episodes_pushed=len(pushed['episodes']))
        lane.start(reservation, level_text(lane.role_prompt, lane.brief, wake, pushed), meta)

    # --- the end ---

    def drain(self, halted: Callable[[], bool], deadline: float) -> None:
        """After the actor's host ended: stop the level, close the last partial episode and let the recorder finish.

        The session edge (a handoff, a stop or the end) closes the open episode mechanically so it is still recorded.
        The recorder then works through its backlog until it is empty, the run is fenced (`halted`), or there is no
        time; whatever is left settles as failed. The level does not run again before its actor's successor.
        """
        try:
            if not self.failure:
                self.level_lane.finish()
                self.close_edge()
                limit = time.monotonic() + (self.backlog + 1) * self.recorder_lane.limits['pass_seconds']
                while (self.queue or self.recorder_lane.busy) and not halted() and time.monotonic() < min(limit, deadline - 30):
                    self._poll(None, halted(), deadline, ending=True)
                    time.sleep(.1)
        except Exception as exc:
            self.failure = f'{type(exc).__name__}: {str(exc)[:300]}'
        self.finish()

    def close_edge(self) -> None:
        """Close the open episode at a session edge (a handoff, a stop or the end): it joins the backlog for the recorder."""
        self._ingest(final=True)
        tail = self.cutter.flush()
        if tail is not None:
            self.edge_closed = True
            self._enqueue(tail)

    def finish(self) -> None:
        """Close both lanes' passes and settle every episode still waiting as failed, so each settles exactly once."""
        # A lane that cannot close is recorded and the next still closes: a lane failure never stops the actor.
        for lane in (self.level_lane, self.recorder_lane):
            try:
                lane.finish()
            except Exception as exc:
                self.failure = self.failure or f'{type(exc).__name__}: {str(exc)[:300]}'
        failed = []
        if self.inflight is not None:
            # A pass that never started: its episode still settles exactly once.
            self.queue.appendleft(self.inflight)
            self.inflight = None
        while self.queue:
            episode = self.queue.popleft()
            try:
                self._settle(episode, 'failed', 'The session ended before the recorder ran' if not self.failure
                             else 'The recorder and the level stopped after a failure')
            except Exception as exc:
                failed.append(type(exc).__name__)
        if failed and not self.failure:
            self.failure = 'Could not settle waiting episodes: ' + ', '.join(sorted(set(failed)))

    def quiescent(self) -> bool:
        return self.level_lane.quiescent() and self.recorder_lane.quiescent()

    @property
    def charged(self) -> int:
        return self.level_lane.charged + self.recorder_lane.charged

    # --- the receipt ---

    def level_receipt(self) -> dict:
        lane = self.level_lane
        passes = lane.passes
        commits = [e for p in passes for e in p.get('level_events', []) if e['type'] == 'level-commit']
        discards = [e for p in passes for e in p.get('level_events', []) if e['type'] == 'level-discard']
        abstains = [(p['reason'], e) for p in passes for e in p.get('level_events', []) if e['type'] == 'level-abstain']
        # A pass that settled unsuccessfully or never settled (for example level-no-proposal or a stopped pass).
        failed = [p for p in passes if (p.get('settled') or {}).get('ok') is not True]
        # A terminal call refused on the last allowed request is its own outcome, distinct from request-limit.
        refused = [p for p in failed if (p.get('settled') or {}).get('reason') == 'level-final-refusal']
        codes = {code: sum(e.get('reason_code') == code for _, e in abstains) for code in ABSTAIN_CODES}
        # Terminal calls whose transport was lost, by what the store shows they did (see `reconcile`).
        uncertain = [e for p in passes for e in p.get('level_uncertain', [])]
        return dict(reader_id=lane.reader_id, allocated_attempts=lane.allowance, attempts_charged=lane.charged, passes=passes,
                    wake_skips=list(self.wake_skips),
                    commits=len(commits), keeps=sum(e['action'] == 'keep' for e in commits),
                    replaces=sum(e['action'] == 'replace' for e in commits), closes=sum(e['action'] == 'close' for e in commits),
                    discards=len(discards), abstains=len(abstains), abstain_codes=codes,
                    start_abstains=sum(reason == 'start' for reason, _ in abstains), failed_passes=len(failed),
                    final_refusals=len(refused), uncertain_terminals=len(uncertain),
                    uncertain_committed=sum(e['outcome'] == 'committed' for e in uncertain),
                    uncertain_absent=sum(e['outcome'] == 'absent' for e in uncertain), **lane.usage())

    def recorder_receipt(self) -> dict:
        lane = self.recorder_lane
        passes = lane.passes
        events = [e for p in passes for e in p.get('episode_events', [])]
        # A pass that settled not-ok after its record or abstain event already left its settle in the store: committed.
        failed = [p for p in passes if (p.get('settled') or {}).get('ok') is not True and not p.get('episode_events')]
        refused = [p for p in failed if (p.get('settled') or {}).get('reason') == 'episode-final-refusal']
        uncertain = [e for p in passes for e in p.get('episode_uncertain', [])]
        codes = {code: sum(e['type'] == 'episode-abstain' and e.get('reason_code') == code for e in events)
                 for code in EPISODE_ABSTAIN_CODES}
        return dict(reader_id=lane.reader_id, allocated_attempts=lane.allowance, attempts_charged=lane.charged, passes=passes,
                    records=sum(e['type'] == 'episode-record' for e in events),
                    abstains=sum(e['type'] == 'episode-abstain' for e in events), abstain_codes=codes,
                    failed_passes=len(failed), final_refusals=len(refused), uncertain_terminals=len(uncertain),
                    uncertain_committed=sum(e['outcome'] == 'committed' for e in uncertain),
                    uncertain_absent=sum(e['outcome'] == 'absent' for e in uncertain), **lane.usage())

    def episodes_receipt(self) -> dict:
        """The cutter's closes and every episode's settle, read back from the store (the claims are the authority)."""
        settled = {name: 0 for name in ('recorded', 'abstained', 'failed', 'dropped')}
        try:
            for view in self.application.settled_episodes(actor_id=self.actor_id, session=self.session):
                settled[view['settled']] += 1
        except Exception as exc:
            settled = dict(error=type(exc).__name__)
        reasons = {name: sum(e.closed_by == name for e in self.cuts) for name in CLOSED_BY}
        return dict(cut=len(self.cuts), closed_by=reasons, settled=settled, max_waiting=self.max_waiting,
                    backlog=self.backlog, waiting_unsettled=len(self.queue) + (self.inflight is not None),
                    next_position=self.cutter.next_position, open_inputs=self.cutter.open_inputs)

    def receipt(self) -> dict:
        level, recorder = self.level_receipt(), self.recorder_receipt()
        try:
            subgoals = self.application.subgoal_counts(self.actor_id)
        except Exception as exc:
            subgoals = dict(error=type(exc).__name__)
        return dict(reader_id=self.reader_id, recorder_id=self.recorder_id, mode=self.level['mode'],
                    allocated_attempts=level['allocated_attempts'] + recorder['allocated_attempts'],
                    attempts_charged=self.charged, failure=self.failure, quiescent=self.quiescent(),
                    level=level, recorder=recorder, episodes=self.episodes_receipt(), subgoals=subgoals,
                    failed_passes=level['failed_passes'] + recorder['failed_passes'],
                    final_refusals=level['final_refusals'] + recorder['final_refusals'],
                    uncertain_terminals=level['uncertain_terminals'] + recorder['uncertain_terminals'],
                    configured_estimate_usd=level['configured_estimate_usd'] + recorder['configured_estimate_usd'],
                    missing_usage_attempts=level['missing_usage_attempts'] + recorder['missing_usage_attempts'])


def run_hosts(directory: Path,profile: dict,route: dict,application,secret: str,
              stopped: threading.Event,deadline: float) -> dict:
    actors=directory/'actors';actors.mkdir(mode=0o700)
    total_attempts=0;host_seconds_used=0.;records=[]
    outcome='incomplete';reason='Original actor allowance exhausted'
    for index in range(1,profile['max_hosts']+1):
        seconds=min(profile['host_seconds'],profile['total_host_seconds']-host_seconds_used,deadline-time.monotonic()-30)
        # The actor, its level and its recorder are partitioned before launch; their sum stays within the campaign cap.
        level=profile['level']
        level_allowance=min(level['max_http_attempts'],profile['max_http_attempts']-total_attempts) if level else 0
        recorder_allowance=min(level['recorder']['max_http_attempts'],
                               profile['max_http_attempts']-total_attempts-level_allowance) if level else 0
        allowance=min(route['max_requests'],profile['max_http_attempts']-total_attempts-level_allowance-recorder_allowance)
        if stopped.is_set() or seconds<=30 or allowance<1 or (level and (level_allowance<1 or recorder_allowance<1)):
            reason='Original host/campaign resources or cancellation prevent another actor';break
        if level and application.remember_failure is not None:
            # The lineage ends here as a recorded failure; an actor that could not be served is never minted.
            reason=f'The lineage ends: player memory could not remember ({application.remember_failure}); no further actor';break
        target=actors/f'{index:03d}'
        child=None;events=None;levels=None
        record=dict(index=index,actor_id=None,allocated_seconds=seconds,allocated_attempts=allowance)
        started=time.monotonic();ending_at=None
        fenced=lambda:stopped.is_set() or application.runtime.channel.stopped.is_set()
        try:
            actor=application.add_actor(profile['actor_profile'])
            target.mkdir(mode=0o700)
            record['actor_id']=actor['actor_id']
            actor_file=target/'actor.json'
            write_new(actor_file,dict(schema='player-adapter/1',base_url=f"http://127.0.0.1:{profile['port']}",
                                     session=profile['session'],**actor))
            selected_route=dict(route,max_requests=allowance)
            write_new(target/'route.json',selected_route)
            write_new(target/'mcp.json',configuration(str(actor_file),profile=profile['actor_profile']))
            # Identical frozen system context across actors maximizes stable prefix
            # reuse. Actor/resource/knowledge changes belong in the explicit prompt.
            write_new(target/'context.txt',(directory/'context.txt').read_text(),text=True)
            role=(f'Actor {index}/{profile["max_hosts"]}. Original host allowance {seconds:.3f} seconds and {allowance} HTTP attempts; '
                  f'original campaign attempts remaining {profile["max_http_attempts"]-total_attempts}. '
                  'The host supplies current decision-time/attempt snapshots; custodian time is separate. ')
            if index<profile['max_hosts']:
                role+='player_handoff seals this actor for a successor with a fresh context; it carries no summary or knowledge snapshot. Retain ending capacity for your successor. '
            else:
                role+='You are the final actor in this admission. Preserve ending capacity and finish with normal Save plus separate application exit. '
            prompt=(directory/'prompt.txt').read_text()+'\n\nSoftware actor/resource note: '+role
            write_new(target/'prompt.txt',prompt,text=True)
            write_new(target/'player-final.txt','',text=True)
            write_new(target/'frozen.json',dict(schema='player-host-inputs/1',actor_id=actor['actor_id'],session=profile['session'],
                files={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ('actor.json','route.json','mcp.json','context.txt','prompt.txt')}))
            arguments=[*profile['host']['argv'],'run','--config',str(target/'route.json'),
                '--mcp-config',str(target/'mcp.json'),'--context',str(target/'context.txt'),'--model',route['model']['id'],
                '--effort',profile['effort'],'--timeout-seconds',str(seconds),'-o',str(target/'player-final.txt')]
            environment=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),LANG='en_US.UTF-8',**{route['api_key_env']:secret})
            if level:
                levels=LevelSystem(target,directory,application,actor,level,route,profile,secret,
                                   (level_allowance,recorder_allowance),allowance)
                record['reader_id']=levels.reader_id;record['recorder_id']=levels.recorder_id
            with (target/'host.jsonl').open('x') as output,(target/'host-stderr.log').open('x') as errors,(target/'prompt.txt').open() as prompt_input:
                child=subprocess.Popen(arguments,cwd=ROOT,env=environment,stdin=prompt_input,stdout=output,stderr=errors,start_new_session=True)
                write_new(target/'host-process.json',dict(pid=child.pid,pgid=child.pid,argv=arguments))
                events=HostEvents(target/'host.jsonl',allowance,
                    observer=lambda ordinal,event:application.activity_view.host_event(actor['actor_id'],ordinal,event))
                while child.poll() is None:
                    events.read()
                    if levels is not None:
                        levels.poll(events,fenced(),min(deadline,started+seconds))
                    now=time.monotonic()
                    application.host=dict(index=index,model=route['model']['id'],provider=route['model']['name'],
                        requests_total=total_attempts+len(events.requests),max_requests_total=profile['max_http_attempts'],
                        host_seconds_remaining=max(0.,started+seconds-now),latest_response_wall=events.last_response_wall)
                    if stopped.is_set() or now>=min(deadline-30,started+seconds):
                        application.runtime.stop('Original host deadline/operator cancellation');reason='Original host deadline/cancellation';break
                    code=application.runtime.process.poll()
                    if code is not None or application.runtime.channel.stopped.is_set():
                        if ending_at is None:ending_at=now+(45 if code is not None else 30)
                        if now>=ending_at:reason='Original final-report grace exhausted';break
                    time.sleep(.1)
            # The level stops on its actor's stop, Pause or handoff, before any successor. The open episode closes at this
            # session edge, and the recorder records the last episodes unless the run is fenced or out of time.
            cleanup=close_group(child)
            record['cleanup']=cleanup
            record.update(events.finish())
            if levels is not None:levels.drain(fenced,deadline)
            if not record['accounting_complete'] or not cleanup['process_absent'] or not cleanup['group_absent']:
                raise ControlError('Host accounting or exact process-group quiescence is unresolved')
            if levels is not None and not levels.quiescent():
                raise ControlError('A level or recorder pass process group is not confirmed absent; no successor')
            settled=record['settled']
            if child.returncode!=0 or settled.get('ok') is not True:
                reason='Deciding host ended unsuccessfully';break
            if settled.get('reason')=='handoff':
                if record['handoff'] is None:raise ControlError('Host settled without its originating handoff')
                _handoff_context(application,actor,record['handoff'])
                application.runtime.confirm_quiescent(actor['actor_id'],record['handoff']['handoff_id'],host_quiescent=True)
                if index==profile['max_hosts']:
                    reason='Final actor handed off beyond original actor allowance';break
                continue
            if settled.get('reason')=='completed':
                outcome='host_completed_unassessed';reason='Terminal player report; gameplay/normal exit assessed separately';break
            reason='Unknown host terminal disposition';break
        except Exception as exc:
            application.runtime.stop('Actor orchestration failed; no successor')
            reason=f'{type(exc).__name__}: {str(exc)[:500]}'
            record['orchestration_error']=reason
        finally:
            if 'cleanup' not in record:
                try:
                    record['cleanup']=close_group(child) if child is not None else dict(process_absent=True,group_absent=True)
                except Exception as exc:
                    record['cleanup']=dict(process_absent=False,group_absent=False,error=type(exc).__name__)
            if events is not None:
                try:
                    record.update(events.finish())
                except Exception as exc:
                    record.update(accounting_complete=False,attempts_charged=allowance,trace_error=type(exc).__name__)
                finally:events.close()
            else:record.update(accounting_complete=False,attempts_charged=allowance if child else 0)
            if levels is not None:
                # An orchestration failure is a stop: the open episode closes at the edge, where that is safe.
                if not levels.failure:
                    try:levels.close_edge()
                    except Exception as exc:levels.failure=f'{type(exc).__name__}: {str(exc)[:300]}'
                try:levels.finish()
                except Exception as exc:record['level_error']=type(exc).__name__
                record['level']=levels.receipt()
                # finish() charged every pass, an unaccounted one at its whole allocation.
                total_attempts+=levels.charged
            record['elapsed_seconds']=time.monotonic()-started
            total_attempts+=record['attempts_charged'];host_seconds_used+=record['elapsed_seconds']
            records.append(record)
            try:write_new(target/'driver-receipt.json',record)
            except (OSError,ValueError) as exc:record['receipt_error']=type(exc).__name__
        if record.get('orchestration_error'):break
    # attempts_charged includes every actor's level passes; each record keeps its own split.
    levels_of=lambda r:r.get('level') or {}
    return dict(schema='player-driver/7',outcome=outcome,reason=reason,actors=records,
                attempts_charged=total_attempts,host_seconds_used=host_seconds_used,
                level_attempts_charged=sum(levels_of(r).get('attempts_charged',0) for r in records),
                level_failed_passes=sum(levels_of(r).get('failed_passes',0) for r in records),
                level_final_refusals=sum(levels_of(r).get('final_refusals',0) for r in records),
                level_uncertain_terminals=sum(levels_of(r).get('uncertain_terminals',0) for r in records),
                episodes_cut=sum((levels_of(r).get('episodes') or {}).get('cut',0) for r in records),
                configured_estimate_usd=sum(r.get('configured_estimate_usd',0)+levels_of(r).get('configured_estimate_usd',0) for r in records),
                missing_usage_attempts=sum(r.get('missing_usage_attempts',r['attempts_charged'])
                                           +levels_of(r).get('missing_usage_attempts',0) for r in records))
