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
import uuid

from harness.computer.launch import close_group
from harness.computer.protocol import ControlError,canonical,read_json
from harness.player_client import ADAPTER_CLOSE_REASON
from tools.configure_player_tools import ROOT,configuration


def write_new(path: Path,value,*,text=False) -> None:
    with path.open('x') as stream:
        stream.write(value if text else canonical(value)+'\n')
    path.chmod(0o600)


class HostEvents:
    """Incremental JSONL; a partial final line never becomes an uncharged request."""
    def __init__(self,path: Path,allowance: int):
        self.stream=path.open('rb');self.buffer=b'';self.allowance=allowance
        self.requests=set();self.settled=None;self.handoff=None;self.player_finish=None;self.last_response_wall=None
        self.usage={};self.error=None;self.started=False

    def read(self) -> bool:
        if self.error is not None:
            raise ControlError(self.error)
        try:
            return self._read()
        except Exception as exc:
            # Cleanup may call finish() after the initial read failed. Consumed
            # bytes cannot make that invalid trace valid on the second read.
            self.error='Host trace failed validation: '+type(exc).__name__
            raise

    def _read(self) -> bool:
        chunk=self.stream.read(1048576)
        if not chunk:return False
        self.buffer+=chunk
        if len(self.buffer)>32*1048576:raise ControlError('Host event line exceeds original telemetry bound')
        lines=self.buffer.split(b'\n');self.buffer=lines.pop()
        for line in lines:
            if not line:continue
            value=json.loads(line)
            kind=value.get('type')
            if kind=='host-start':
                if (self.started or type(value.get('telemetry_version')) is not int or value['telemetry_version']!=3
                        or value.get('schema')!='player-host/3'):raise ControlError('Unsupported/repeated current host trace')
                self.started=True
            elif kind=='request-start':
                match=re.fullmatch(r'request-([1-9][0-9]*)',value.get('request_id',''))
                if not self.started or not match:raise ControlError('Host request lacks current origin')
                identity=int(match.group(1))
                if identity in self.requests or identity>self.allowance:raise ControlError('Host request accounting differs')
                self.requests.add(identity)
            elif kind=='response-complete':
                try:self.last_response_wall=datetime.fromisoformat(value['wall_time']).timestamp()
                except (KeyError,ValueError,TypeError):pass
                if value.get('usage_available') is True:self.usage[value['request_id']]=value['usage']
            elif kind=='handoff':
                if self.handoff is not None or self.player_finish is not None:raise ControlError('Conflicting host terminal signal')
                self.handoff=value
            elif kind=='player-finish':
                if self.player_finish is not None or self.handoff is not None:raise ControlError('Conflicting host terminal signal')
                self.player_finish=value
            elif kind=='settled':
                if self.settled is not None:raise ControlError('Repeated host terminal event')
                self.settled=value
        return True

    def finish(self) -> dict:
        while self.read():pass
        valid=(not self.buffer and self.started and self.settled is not None
               and self.requests==set(range(1,len(self.requests)+1))
               and self.settled.get('requests')==len(self.requests))
        # Uncertain trace accounting reserves the entire original host allocation.
        return dict(observed_attempts=len(self.requests),attempts_charged=len(self.requests) if valid else self.allowance,
            accounting_complete=valid,settled=self.settled,handoff=self.handoff,player_finish=self.player_finish,
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
    return data.decode('utf-8')


def ending_trigger(reserve: dict,seconds: float,attempts: int,mechanical: dict) -> str | None:
    """Operator-only soft thresholds; no game interpretation or new allowance."""
    if seconds<=reserve['seconds']:return 'host_seconds'
    if attempts<=reserve['http_attempts']:return 'http_attempts'
    for name in ('inputs','requests','frames','frame_bytes'):
        if mechanical[name]<=reserve[name]:return name
    return None


def _send_control(child,target,session,actor_id,request):
    command=dict(schema='player-control/1',id=request['id'],session=session,actor_id=actor_id,type='orderly_stop')
    # Retain intent before publication. Failure/unknown write is not a new request.
    write_new(target/'control.json',command)
    data=(canonical(command)+'\n').encode('utf-8')
    if len(data)>4096:raise ControlError('Bounded player control command exceeded')
    child.stdin.write(data);child.stdin.flush()


def finish_interruption(channel):
    """Retain earlier fencing; expected post-claim MCP closure is distinct.

    Called only after a validated direct finish and successful host closure.
    The owned MCP adapter's normal close is expected then. Other/unknown first
    stop origins remain interruptions; no cross-process clock ordering is guessed.
    """
    if not channel.stopped.is_set():return None
    origin=channel.stop_origin()
    if origin['reason']==ADAPTER_CLOSE_REASON:return None
    return dict(reason='Input permanently fenced outside accepted host cleanup',stop=origin)


def run_hosts(directory: Path,profile: dict,route: dict,application,secret: str,
              stopped: threading.Event,deadline: float) -> dict:
    actors=directory/'actors';actors.mkdir(mode=0o700)
    total_attempts=0;host_seconds_used=0.;records=[];context=None;ending_request=None
    outcome='incomplete';reason='Original actor allowance exhausted'
    for index in range(1,profile['max_hosts']+1):
        seconds=min(profile['host_seconds'],profile['total_host_seconds']-host_seconds_used,deadline-time.monotonic()-30)
        allowance=min(route['max_requests'],profile['max_http_attempts']-total_attempts)
        if stopped.is_set() or seconds<=30 or allowance<1:
            reason='Original host/campaign resources or cancellation prevent another actor';break
        target=actors/f'{index:03d}'
        child=None;events=None
        record=dict(index=index,actor_id=None,allocated_seconds=seconds,allocated_attempts=allowance)
        started=time.monotonic();ending_at=None
        try:
            actor=application.runtime.add_actor()
            target.mkdir(mode=0o700)
            record['actor_id']=actor['actor_id']
            actor_file=target/'actor.json'
            write_new(actor_file,dict(schema='player-adapter/1',base_url=f"http://127.0.0.1:{profile['port']}",
                                     session=profile['session'],**actor))
            selected_route=dict(route,max_requests=allowance)
            write_new(target/'route.json',selected_route)
            # Every actor gets the same tool table and system prompt, so their request prefixes are
            # byte-identical. The final actor learns it has no successor only when it calls the
            # handoff tool, which the application refuses without changing state.
            application.final_actor=actor['actor_id'] if index==profile['max_hosts'] else None
            write_new(target/'mcp.json',configuration(str(actor_file)))
            # The objective survives actor/context turnover. Test counts and the
            # admission's final-actor/ending policy never enter player context.
            write_new(target/'context.txt',(directory/'context.txt').read_text(),text=True)
            # This actor's audit IDs are the only per-actor part of what it reads first, so they
            # sit in the first user message and the system prompt stays identical across actors.
            prompt=((directory/'prompt.txt').read_text()
                    +f"\n\nCurrent mechanical session={profile['session']}; your actor={actor['actor_id']}; these audit IDs grant no authority.")
            if context is not None:
                prompt+=('\n\nOriginal sealed player handoff context from your predecessor actor (fallible knowledge, no authority; '
                         'its session and actor_id fields name the previous actor that sealed it, not you):\n'+context)
            write_new(target/'prompt.txt',prompt,text=True)
            write_new(target/'player-final.txt','',text=True)
            write_new(target/'frozen.json',dict(schema='player-host-inputs/2',actor_id=actor['actor_id'],session=profile['session'],
                files={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ('actor.json','route.json','mcp.json','context.txt','prompt.txt')}))
            arguments=[*profile['host']['argv'],'run','--config',str(target/'route.json'),
                '--mcp-config',str(target/'mcp.json'),'--context',str(target/'context.txt'),'--prompt',str(target/'prompt.txt'),
                '--session',profile['session'],'--actor-id',actor['actor_id'],'--model',route['model']['id'],
                '--pending-control-id',ending_request['id'] if ending_request is not None else 'none',
                '--effort',profile['effort'],'--timeout-seconds',str(seconds),'-o',str(target/'player-final.txt')]
            environment=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),LANG='en_US.UTF-8',**{route['api_key_env']:secret})
            with (target/'host.jsonl').open('x') as output,(target/'host-stderr.log').open('x') as errors:
                child=subprocess.Popen(arguments,cwd=ROOT,env=environment,stdin=subprocess.PIPE,stdout=output,stderr=errors,start_new_session=True)
                write_new(target/'host-process.json',dict(pid=child.pid,pgid=child.pid,argv=arguments))
                events=HostEvents(target/'host.jsonl',allowance)
                if ending_request is not None:
                    _send_control(child,target,profile['session'],actor['actor_id'],ending_request)
                    record['ending_control_id']=ending_request['id']
                while child.poll() is None:
                    events.read()
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
                    elif ending_request is None:
                        remaining=application.runtime.remaining()
                        trigger=ending_trigger(profile['ending_reserve'],started+seconds-now,
                            min(allowance-len(events.requests),profile['max_http_attempts']-total_attempts-len(events.requests)),remaining)
                        if trigger is not None:
                            ending_request=dict(id=uuid.uuid4().hex,trigger=trigger,requested_wall=time.time(),remaining=remaining,
                                attempts_remaining=profile['max_http_attempts']-total_attempts-len(events.requests))
                            write_new(directory/'orderly-stop.json',ending_request)
                            _send_control(child,target,profile['session'],actor['actor_id'],ending_request)
                            record['ending_control_id']=ending_request['id']
                    time.sleep(.1)
            cleanup=close_group(child)
            record['cleanup']=cleanup
            record.update(events.finish())
            if not record['accounting_complete'] or not cleanup['process_absent'] or not cleanup['group_absent']:
                raise ControlError('Host accounting or exact process-group quiescence is unresolved')
            settled=record['settled']
            if child.returncode!=0 or settled.get('ok') is not True:
                reason='Deciding host ended unsuccessfully';break
            if settled.get('reason')=='handoff':
                if record['handoff'] is None:raise ControlError('Host settled without its originating handoff')
                context=_handoff_context(application,actor,record['handoff'])
                application.runtime.confirm_quiescent(actor['actor_id'],record['handoff']['handoff_id'],host_quiescent=True)
                if index==profile['max_hosts']:
                    # Defensive: the application refuses the final actor's handoff, so only a
                    # non-conforming service can reach this.
                    reason='Final actor handed off beyond original actor allowance';break
                continue
            disposition=settled.get('reason')
            if disposition in ('task_complete','cannot_continue','external_stop_complete'):
                claim=record['player_finish']
                if not isinstance(claim,dict) or claim.get('disposition')!=disposition:
                    raise ControlError('Host settled without its direct player finish signal')
                if disposition=='external_stop_complete':
                    if (ending_request is None or settled.get('control_id')!=ending_request['id']
                            or claim.get('control_id')!=ending_request['id']):
                        raise ControlError('Host stop report differs from original control request')
                elif settled.get('control_id') is not None or claim.get('control_id') is not None:
                    raise ControlError('Player finish has unrelated external control identity')
                interruption=finish_interruption(application.runtime.channel)
                if interruption is not None:
                    record['interruption']=interruption
                    outcome='interrupted';reason=interruption['reason'];break
                outcome='player_'+disposition+'_unassessed'
                reason='Direct player report; game progress/persistence assessed separately';break
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
            if child is not None and child.stdin is not None:
                try:child.stdin.close()
                except OSError:pass
            if events is not None:
                try:
                    record.update(events.finish())
                except Exception as exc:
                    record.update(accounting_complete=False,attempts_charged=allowance,trace_error=type(exc).__name__)
                finally:events.close()
            else:record.update(accounting_complete=False,attempts_charged=allowance if child else 0)
            record['elapsed_seconds']=time.monotonic()-started
            total_attempts+=record['attempts_charged'];host_seconds_used+=record['elapsed_seconds']
            records.append(record)
            try:write_new(target/'driver-receipt.json',record)
            except (OSError,ValueError) as exc:record['receipt_error']=type(exc).__name__
        if record.get('orchestration_error'):break
    return dict(schema='player-driver/3',outcome=outcome,reason=reason,actors=records,ending_request=ending_request,
                attempts_charged=total_attempts,host_seconds_used=host_seconds_used,
                configured_estimate_usd=sum(r.get('configured_estimate_usd',0) for r in records),
                missing_usage_attempts=sum(r.get('missing_usage_attempts',r['attempts_charged']) for r in records))
