"""Finite actors of the selected player host over one live mechanical custodian."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

from harness.computer.launch import close_group
from harness.computer.protocol import ControlError,canonical,read_json
from harness.player.contracts import ABSTAIN_CODES
from tools.configure_player_tools import ROOT,configuration
from tools.level_schedule import LevelSchedule


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
        # A level pass's own commit, discard and abstain outcomes.
        self.level=[]

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
                        or value.get('schema')!='player-host/5'):raise ControlError('Unsupported/repeated current host trace')
                self.started=True
            elif kind in ('level-commit','level-discard','level-abstain'):
                if len(self.level)<256:self.level.append({k:value.get(k) for k in
                    ('type','action','reason_code','reason','position','inputs_since','staleness_inputs','record_ids','kept')})
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
            accounting_complete=valid,settled=self.settled,handoff=self.handoff,level_events=self.level,
            configured_estimate_usd=sum(v.get('cost',{}).get('total',0) for v in self.usage.values()),
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


def push_text(application,reader_id: str,actor_id: str,shown_through: int,total: int) -> tuple[str,int,int]:
    """A level pass's pushed input: its text, the entries shown and the new `shown_through` position.

    The served log since the previous pass (at most the latest 50 entries), the current subgoal and how many
    level records player memory holds, stated mechanically. The reader's bound is cleared first, so it ends up
    exactly the last entry shown and a bound left by an earlier pass (one that never reached a terminal call)
    cannot carry over. The replay probe builds its pass input through this same function.
    """
    with application.serial:
        application.reset_reader_bound(reader_id)
        after=max(shown_through,total-50)
        log=application.log_read(reader_id,after,50)
        subgoals=application.level_subgoals()
        intent=application.intent(actor_id) if subgoals else None
        records=application.level_record_count()
    omitted=after-shown_through
    entries=log['entries']
    if entries:shown_through=entries[-1]['position']
    lines=[json.dumps(e,separators=(',',':'),ensure_ascii=False) for e in entries]
    text=('Served player log since your last pass, oldest first, one entry per line with its position'
          +(f' ({omitted} earlier entries since then are not shown; read them with player_log_read)' if omitted else '')
          +':\n'+('\n'.join(lines) if lines else '(no new entries)'))
    if intent is None:
        subgoal='Current subgoal: none'
    else:
        record,age=intent['record'],intent['age']
        shown=dict(record_id=record['record_id'],text=record['text'],expected_observations=record['expected_observations'],
                   status=record['status'],confidence=record['confidence'],sources=record['sources'],
                   same_actor=age['same_actor'],
                   # Positions count per actor: another actor's is not a position in the served log.
                   position=subgoals[-1]['data']['position'] if age['same_actor'] else None,
                   inputs_since_commit=age['inputs_since_commit'])
        subgoal='Current subgoal:\n'+json.dumps(shown,separators=(',',':'),ensure_ascii=False)
    return f'{text}\n\n{subgoal}\nLevel records in player memory: {records}',len(entries),shown_through


def pass_prompt(role: str,brief: str,pushed: str,reason: str,entries: int,inputs: int,allowance: int,seconds: float) -> str:
    """One level pass's whole prompt. Mechanical wake facts only: the frozen role prompt and the actor's own
    mission brief carry everything else, so the level adds no lead content."""
    return (role+'\n\nMission brief (the same the acting player has):\n'+brief+'\n\n'
            +pushed+'\n\nSoftware level pass note: '
            +f'wake reason {reason}; the served actor log now has {entries} entries ({inputs} inputs); '
            +f'pass allowance {allowance} HTTP attempts and {seconds:.0f} seconds.')


class LevelPasses:
    """One actor's subgoal level: a reader plus finite level-role host passes, at most one in flight."""
    def __init__(self,target: Path,directory: Path,application,actor: dict,level: dict,route: dict,
                 profile: dict,secret: str,allowance: int,actor_allowance: int):
        self.target,self.directory,self.application,self.level=target,directory,application,level
        self.route,self.profile,self.secret,self.allowance=route,profile,secret,allowance
        self.actor_id=actor['actor_id']
        target.mkdir(mode=0o700)
        reader=application.add_reader(self.actor_id,staleness_inputs=level['staleness_inputs'])
        self.reader_id=reader['actor_id']
        self.reader_file=target/'reader.json'
        write_new(self.reader_file,dict(schema='player-adapter/1',base_url=f"http://127.0.0.1:{profile['port']}",
                                       session=profile['session'],**reader))
        self.schedule=LevelSchedule(level['inputs_per_pass'],tuple(level['budget_fractions']),actor_allowance)
        self.passes=[];self.charged=0;self.current=None;self.failure=None
        # The last log position shown to a pass by software; the next pass's push starts after it.
        self.shown_through=0

    def remaining(self) -> int:
        return self.allowance-self.charged

    def poll(self,actor_events: 'HostEvents',stopped: bool,actor_deadline: float) -> None:
        """A level failure disables further passes but never stops or gates its actor (ADR-007)."""
        try:
            self._poll(actor_events,stopped or actor_events.handoff is not None,actor_deadline)
        except Exception as exc:
            self.failure=f'{type(exc).__name__}: {str(exc)[:300]}'
            self.finish()

    def _poll(self,actor_events: 'HostEvents',stopped: bool,actor_deadline: float) -> None:
        now=time.monotonic()
        if self.current is not None:
            child,events,record,ends=self.current
            events.read()
            if child.poll() is not None or stopped or now>=ends:self.finish()
            return
        # The actor's first request follows its tool discovery and checks, so it is ready.
        if (self.failure or stopped or not actor_events.requests or self.remaining()<1
                or actor_deadline-now<30+self.level['pass_seconds']/4):return
        # One lock hold: the wake decision and the pass's pushed input see the same log count.
        with self.application.serial:
            entries,inputs=self.application.runtime.store.actor_counts(self.actor_id)
            open_records=len(self.application.level_subgoals())
            reason=self.schedule.due(entries=entries,inputs=inputs,attempts=len(actor_events.requests),open_records=open_records)
            if reason is None:return
            pushed,shown=self._push(entries)
        # Only a start pass may be given an empty delta (it revalidates the open subgoal).
        if shown or reason=='start':
            self.launch(reason,entries,inputs,min(self.level['pass_seconds'],actor_deadline-now-30),pushed)

    def launch(self,reason: str,entries: int,inputs: int,seconds: float,pushed: str) -> None:
        index=len(self.passes)+1
        target=self.target/f'{index:03d}';target.mkdir(mode=0o700)
        allowance=min(self.level['pass_max_requests'],self.remaining())
        record=dict(index=index,reason=reason,log_entries=entries,actor_inputs=inputs,allocated_attempts=allowance,
                    allocated_seconds=seconds,started_wall=time.time())
        write_new(target/'route.json',dict(self.route,role='level',intent_tail_bytes=None,max_requests=allowance))
        write_new(target/'mcp.json',configuration(str(self.reader_file),profile='reader'))
        write_new(target/'context.txt',(self.directory/'context.txt').read_text(),text=True)
        prompt=pass_prompt((self.directory/'level-role.txt').read_text(),(self.directory/'prompt.txt').read_text(),
                           pushed,reason,entries,inputs,allowance,seconds)
        write_new(target/'prompt.txt',prompt,text=True)
        write_new(target/'player-final.txt','',text=True)
        arguments=[*self.profile['host']['argv'],'run','--config',str(target/'route.json'),
            '--mcp-config',str(target/'mcp.json'),'--context',str(target/'context.txt'),'--model',self.route['model']['id'],
            '--effort',self.profile['effort'],'--timeout-seconds',str(seconds),'-o',str(target/'player-final.txt')]
        environment=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),LANG='en_US.UTF-8',**{self.route['api_key_env']:self.secret})
        with (target/'host.jsonl').open('x') as output,(target/'host-stderr.log').open('x') as errors,(target/'prompt.txt').open() as prompt_input:
            child=subprocess.Popen(arguments,cwd=ROOT,env=environment,stdin=prompt_input,stdout=output,stderr=errors,start_new_session=True)
        # Owned before anything else can fail, so a later error still closes and charges it.
        self.current=(child,None,record,time.monotonic()+seconds)
        write_new(target/'host-process.json',dict(pid=child.pid,pgid=child.pid,argv=arguments))
        self.current=(child,HostEvents(target/'host.jsonl',allowance),record,self.current[3])

    def _push(self,total: int) -> tuple[str,int]:
        """The pass's input text and its shown entry count, for a log of `total` entries."""
        text,shown,self.shown_through=push_text(self.application,self.reader_id,self.actor_id,self.shown_through,total)
        return text,shown

    def finish(self) -> None:
        """Close the pass's exact process group, then charge it; incomplete accounting charges its whole allocation."""
        if self.current is None:return
        child,events,record,_=self.current
        self.current=None
        try:
            record['cleanup']=close_group(child)
        except Exception as exc:
            record['cleanup']=dict(process_absent=False,group_absent=False,error=type(exc).__name__)
        try:
            if events is None:raise ControlError('Pass trace reader never started')
            record.update(events.finish())
        except Exception as exc:
            record.update(accounting_complete=False,attempts_charged=record['allocated_attempts'],trace_error=type(exc).__name__)
        finally:
            if events is not None:events.close()
        record['ended_wall']=time.time()
        self.charged+=record['attempts_charged'];self.passes.append(record)
        try:write_new(self.target/f"{record['index']:03d}"/'driver-receipt.json',record)
        except (OSError,ValueError) as exc:record['receipt_error']=type(exc).__name__

    def quiescent(self) -> bool:
        """Every pass's exact process group was confirmed absent; a successor needs this."""
        return self.current is None and all(p.get('cleanup',{}).get('process_absent') is True
                                            and p['cleanup'].get('group_absent') is True for p in self.passes)

    def receipt(self) -> dict:
        commits=[e for p in self.passes for e in p.get('level_events',[]) if e['type']=='level-commit']
        discards=[e for p in self.passes for e in p.get('level_events',[]) if e['type']=='level-discard']
        abstains=[(p['reason'],e) for p in self.passes for e in p.get('level_events',[]) if e['type']=='level-abstain']
        # A pass that settled unsuccessfully or never settled (for example level-no-proposal or a stopped pass).
        failed=[p for p in self.passes if (p.get('settled') or {}).get('ok') is not True]
        # A terminal call refused on the last allowed request is its own outcome, distinct from request-limit.
        refused=[p for p in failed if (p.get('settled') or {}).get('reason')=='level-final-refusal']
        codes={code:sum(e.get('reason_code')==code for _,e in abstains) for code in ABSTAIN_CODES}
        return dict(reader_id=self.reader_id,mode=self.level['mode'],allocated_attempts=self.allowance,
                    attempts_charged=self.charged,passes=self.passes,failure=self.failure,quiescent=self.quiescent(),
                    commits=len(commits),keeps=sum(e['action']=='keep' for e in commits),
                    replaces=sum(e['action']=='replace' for e in commits),closes=sum(e['action']=='close' for e in commits),
                    discards=len(discards),abstains=len(abstains),abstain_codes=codes,
                    start_abstains=sum(reason=='start' for reason,_ in abstains),failed_passes=len(failed),final_refusals=len(refused),
                    configured_estimate_usd=sum(p.get('configured_estimate_usd',0) for p in self.passes),
                    missing_usage_attempts=sum(p.get('missing_usage_attempts',p['attempts_charged']) for p in self.passes))


def run_hosts(directory: Path,profile: dict,route: dict,application,secret: str,
              stopped: threading.Event,deadline: float) -> dict:
    actors=directory/'actors';actors.mkdir(mode=0o700)
    total_attempts=0;host_seconds_used=0.;records=[]
    outcome='incomplete';reason='Original actor allowance exhausted'
    for index in range(1,profile['max_hosts']+1):
        seconds=min(profile['host_seconds'],profile['total_host_seconds']-host_seconds_used,deadline-time.monotonic()-30)
        # The actor-and-level pair is partitioned before launch; their sum stays within the campaign cap.
        level=profile['level']
        level_allowance=min(level['max_http_attempts'],profile['max_http_attempts']-total_attempts) if level else 0
        allowance=min(route['max_requests'],profile['max_http_attempts']-total_attempts-level_allowance)
        if stopped.is_set() or seconds<=30 or allowance<1 or (level and level_allowance<1):
            reason='Original host/campaign resources or cancellation prevent another actor';break
        target=actors/f'{index:03d}'
        child=None;events=None;levels=None
        record=dict(index=index,actor_id=None,allocated_seconds=seconds,allocated_attempts=allowance)
        started=time.monotonic();ending_at=None
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
                levels=LevelPasses(target/'level',directory,application,actor,level,route,profile,secret,
                                   level_allowance,allowance)
                record['reader_id']=levels.reader_id
            with (target/'host.jsonl').open('x') as output,(target/'host-stderr.log').open('x') as errors,(target/'prompt.txt').open() as prompt_input:
                child=subprocess.Popen(arguments,cwd=ROOT,env=environment,stdin=prompt_input,stdout=output,stderr=errors,start_new_session=True)
                write_new(target/'host-process.json',dict(pid=child.pid,pgid=child.pid,argv=arguments))
                events=HostEvents(target/'host.jsonl',allowance,
                    observer=lambda ordinal,event:application.activity_view.host_event(actor['actor_id'],ordinal,event))
                while child.poll() is None:
                    events.read()
                    if levels is not None:
                        levels.poll(events,stopped.is_set() or application.runtime.channel.stopped.is_set(),
                                    min(deadline,started+seconds))
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
            # A level host stops on its actor's stop, Pause or handoff, before any successor.
            if levels is not None:levels.finish()
            cleanup=close_group(child)
            record['cleanup']=cleanup
            record.update(events.finish())
            if not record['accounting_complete'] or not cleanup['process_absent'] or not cleanup['group_absent']:
                raise ControlError('Host accounting or exact process-group quiescence is unresolved')
            if levels is not None and not levels.quiescent():
                raise ControlError('A level pass process group is not confirmed absent; no successor')
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
    return dict(schema='player-driver/5',outcome=outcome,reason=reason,actors=records,
                attempts_charged=total_attempts,host_seconds_used=host_seconds_used,
                level_attempts_charged=sum(levels_of(r).get('attempts_charged',0) for r in records),
                level_failed_passes=sum(levels_of(r).get('failed_passes',0) for r in records),
                level_final_refusals=sum(levels_of(r).get('final_refusals',0) for r in records),
                configured_estimate_usd=sum(r.get('configured_estimate_usd',0)+levels_of(r).get('configured_estimate_usd',0) for r in records),
                missing_usage_attempts=sum(r.get('missing_usage_attempts',r['attempts_charged'])
                                           +levels_of(r).get('missing_usage_attempts',0) for r in records))
