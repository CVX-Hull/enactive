"""Finite actors of the selected player host over one live mechanical custodian."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from math import isfinite
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
from tools.campaign_package import EXACT,counted_usd,declared_floor,usd_sum,usd_text
from tools.configure_player_tools import ROOT,configuration


def write_new(path: Path,value,*,text=False) -> None:
    with path.open('x') as stream:
        stream.write(value if text else canonical(value)+'\n')
    path.chmod(0o600)


def configured_estimate(amounts) -> float | None:
    """Keep optional diagnostics from blocking the provider subtotal."""
    total=0.0
    for amount in amounts:
        if amount is None:return None
        total+=amount
    return total if isfinite(total) else None


class HostEvents:
    """Reconcile reported charges and unpriced attempts with a complete host settlement."""
    def __init__(self,path: Path):
        self.stream=path.open('rb');self.buffer=b''
        self.requests=set();self.settled=None;self.handoff=None;self.player_finish=None;self.last_response_wall=None
        self.usage={};self.error=None;self.started=False
        # A present key with value None has a finished attempt and unknown provider cost.
        self.costs={}

    def counted_usd(self) -> Decimal:
        """Dollars counted by the cost records read so far; a request still in flight is not in it."""
        return usd_sum(amount for amount in self.costs.values() if amount is not None)

    def _count(self,value: dict) -> None:
        identity=value.get('request_id')
        if identity not in self.requests or identity in self.costs:raise ControlError('Host cost record lacks its one request')
        if not {'reported_cost_usd','counted_cost_usd'}<=value.keys():raise ControlError('Host cost record lacks its cost fields')
        # The host writes the provider's own digits, so a counted amount has no cap on its length.
        reported=value['reported_cost_usd']
        counted=value['counted_cost_usd']
        kind=value.get('cost_counted_as')
        if kind=='provider-reported' and counted==reported:
            self.costs[identity]=counted_usd(reported,'reported_cost_usd')
        elif kind=='unpriced' and counted is None and reported is None:
            self.costs[identity]=None
        else:
            raise ControlError('Host cost record differs from the provider charge')

    def _sums(self) -> tuple[Decimal,int,int]:
        reported=self.counted_usd()
        unpriced=sum(key.startswith('request-') and self.costs.get(key) is None for key in self.requests)
        recall_unpriced=sum(key.startswith('recall-') and self.costs.get(key) is None for key in self.requests)
        return reported,unpriced,recall_unpriced

    def spend(self,complete: bool) -> dict:
        reported,unpriced,recall_unpriced=self._sums()
        amount=usd_text(reported)
        return dict(reported_usd=amount,unpriced_requests=unpriced,unpriced_recall_requests=recall_unpriced,
                    spent_usd=amount,spend_complete=complete)

    def _host_agrees(self) -> bool:
        """The host's own totals in `settled` are the driver's sums from the trace."""
        spent,unpriced,recall_unpriced=self._sums()
        try:total=counted_usd(self.settled.get('spent_usd'),'settled spent_usd')
        except ControlError:return False
        return total==spent and type(self.settled.get('unpriced_recall_requests')) is int and self.settled['unpriced_recall_requests']==recall_unpriced and type(self.settled.get('unpriced_requests')) is int and self.settled['unpriced_requests']==unpriced

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
            if self.settled is not None:raise ControlError('Host event follows settlement')
            if kind=='host-start':
                if (self.started or type(value.get('telemetry_version')) is not int or value['telemetry_version']!=8
                        or value.get('schema')!='player-host/8'):raise ControlError('Unsupported/repeated current host trace')
                self.started=True
            elif kind=='request-start':
                match=re.fullmatch(r'(request|recall)-([1-9][0-9]*)',value.get('request_id',''))
                if not self.started or not match:raise ControlError('Host request lacks current origin')
                identity=value['request_id']
                if identity in self.requests:raise ControlError('Host request accounting differs')
                self.requests.add(identity)
            elif kind=='response-complete':
                try:
                    if value.get('request_id','').startswith('request-'):self.last_response_wall=datetime.fromisoformat(value['wall_time']).timestamp()
                except (KeyError,ValueError,TypeError):pass
                self._count(value)
                if value.get('usage_available') is True:
                    usage=value.get('usage')
                    rates=usage.get('cost',{}) if isinstance(usage,dict) else None
                    total=rates.get('total',0) if isinstance(rates,dict) else None
                    try:estimate=float(total) if type(total) in (int,float) else None
                    except OverflowError:estimate=None
                    if estimate is None or not isfinite(estimate) or estimate<0:
                        raise ControlError('Malformed host usage record')
                    self.usage[value['request_id']]=estimate
            elif kind=='handoff':
                if self.handoff is not None or self.player_finish is not None:raise ControlError('Conflicting host terminal signal')
                self.handoff=value
            elif kind=='player-finish':
                if self.player_finish is not None or self.handoff is not None:raise ControlError('Conflicting host terminal signal')
                self.player_finish=value
            elif kind=='settled':
                self.settled=value
        return True

    def finish(self) -> dict:
        while self.read():pass
        observed=self.observations()
        recalls=observed['observed_recall_attempts']
        counts=dict(requests=len(self.requests),player_requests=len(self.requests)-recalls,recall_requests=recalls)
        valid=(not self.buffer and self.started and self.settled is not None and self.requests==self.costs.keys()
               and all({int(k.split('-')[1]) for k in self.requests if k.startswith(role+'-')}==set(range(1,1+sum(k.startswith(role+'-') for k in self.requests))) for role in ('request','recall'))
               and all(type(self.settled.get(name)) is int and self.settled[name]==count for name,count in counts.items())
               and self._host_agrees())
        return dict(accounting_complete=valid,settled=self.settled,handoff=self.handoff,player_finish=self.player_finish,
                    **observed,**self.spend(valid))

    def observations(self) -> dict:
        # These are lower bounds when the trace cannot be reconciled to settlement.
        return dict(observed_attempts=len(self.requests),
            observed_recall_attempts=sum(k.startswith('recall-') for k in self.requests),
            configured_estimate_usd=configured_estimate(self.usage.values()),
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


def ending_trigger(reserve: dict,seconds: float,dollars: Decimal,mechanical: dict) -> str | None:
    """Operator-only soft thresholds; no game interpretation or new allowance."""
    if seconds<=reserve['seconds']:return 'host_seconds'
    if dollars<=Decimal(reserve['usd']):return 'spend'
    for name in ('inputs','requests','frames','frame_bytes'):
        if mechanical[name]<=reserve[name]:return name
    return None


def _record_ending(directory,reserve,seconds,dollars,remaining):
    trigger=ending_trigger(reserve,seconds,dollars,remaining)
    if trigger is None:return None
    request=dict(id=uuid.uuid4().hex,trigger=trigger,requested_wall=time.time(),remaining=remaining,
                 spend_remaining_usd=usd_text(dollars))
    write_new(directory/'orderly-stop.json',request)
    return request


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
    total_attempts=0;total_recall_attempts=0;host_seconds_used=0.;records=[];context=None;ending_request=None
    # The dollar limit: each actor gets what the actors before it left, counted from their traces.
    limit=Decimal(profile['spend_limit_usd']);bound=Decimal(route['unpriced_request_usd']);recall_bound=Decimal(route['recall']['unpriced_request_usd']);spent=Decimal(0)
    outcome='incomplete';reason='Original actor allowance exhausted'
    for index in range(1,profile['max_hosts']+1):
        seconds=min(profile['host_seconds'],profile['total_host_seconds']-host_seconds_used,deadline-time.monotonic()-30)
        # A route's limit is a declared amount, so what remains is cut to the digits one may carry.
        dollars=declared_floor(EXACT.subtract(limit,spent))
        if stopped.is_set() or seconds<=30:
            reason='Original host/campaign resources or cancellation prevent another actor';break
        if dollars<=0:
            reason='The dollar limit leaves nothing for another actor';break
        target=actors/f'{index:03d}'
        child=None;events=None
        record=dict(index=index,actor_id=None,allocated_seconds=seconds,allocated_usd=usd_text(dollars))
        started=time.monotonic();ending_at=None
        try:
            actor=application.runtime.add_actor()
            target.mkdir(mode=0o700)
            record['actor_id']=actor['actor_id']
            actor_file=target/'actor.json'
            write_new(actor_file,dict(schema='player-adapter/2',base_url=f"http://127.0.0.1:{profile['port']}",
                                     session=profile['session'],**actor))
            selected_route=dict(route,spend_limit_usd=usd_text(dollars))
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
            with (target/'delivered-knowledge.json').open('xb') as stream:
                stream.write((directory/'delivered-knowledge.json').read_bytes())
            (target/'delivered-knowledge.json').chmod(0o600)
            write_new(target/'frozen.json',dict(schema='player-host-inputs/3',actor_id=actor['actor_id'],session=profile['session'],
                finish_reserve_usd=profile['ending_reserve']['usd'],
                files={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ('actor.json','route.json','mcp.json','context.txt','prompt.txt','delivered-knowledge.json')}))
            # A predecessor may have crossed a reserve after the driver's final live poll.
            # Bind the ending before a host can fetch or take input in that case.
            if ending_request is None:
                ending_request=_record_ending(directory,profile['ending_reserve'],
                    started+seconds-time.monotonic(),dollars,application.runtime.remaining())
            arguments=[*profile['host']['argv'],'run','--config',str(target/'route.json'),
                '--mcp-config',str(target/'mcp.json'),'--context',str(target/'context.txt'),'--prompt',str(target/'prompt.txt'),
                '--delivered-knowledge',str(target/'delivered-knowledge.json'),'--finish-reserve-usd',profile['ending_reserve']['usd'],
                '--session',profile['session'],'--actor-id',actor['actor_id'],'--model',route['model']['id'],
                '--pending-control-id',ending_request['id'] if ending_request is not None else 'none',
                '--effort',profile['effort'],'--timeout-seconds',str(seconds),'-o',str(target/'player-final.txt')]
            environment=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),LANG='en_US.UTF-8',**{route['api_key_env']:secret})
            with (target/'host.jsonl').open('x') as output,(target/'host-stderr.log').open('x') as errors:
                child=subprocess.Popen(arguments,cwd=ROOT,env=environment,stdin=subprocess.PIPE,stdout=output,stderr=errors,start_new_session=True)
                write_new(target/'host-process.json',dict(pid=child.pid,pgid=child.pid,argv=arguments))
                events=HostEvents(target/'host.jsonl')
                if ending_request is not None:
                    _send_control(child,target,profile['session'],actor['actor_id'],ending_request)
                    record['ending_control_id']=ending_request['id']
                while child.poll() is None:
                    events.read()
                    now=time.monotonic()
                    application.host=dict(index=index,model=route['model']['id'],provider=route['model']['name'],
                        observed_attempts=total_attempts+len(events.requests),
                        host_seconds_remaining=max(0.,started+seconds-now),latest_response_wall=events.last_response_wall)
                    if stopped.is_set() or now>=min(deadline-30,started+seconds):
                        application.runtime.stop('Original host deadline/operator cancellation');reason='Original host deadline/cancellation';break
                    code=application.runtime.process.poll()
                    if code is not None or application.runtime.channel.stopped.is_set():
                        if ending_at is None:ending_at=now+(45 if code is not None else 30)
                        if now>=ending_at:reason='Original final-report grace exhausted';break
                    elif ending_request is None:
                        dollars_left=EXACT.subtract(dollars,events.counted_usd())
                        ending_request=_record_ending(directory,profile['ending_reserve'],
                            started+seconds-now,dollars_left,application.runtime.remaining())
                        if ending_request is not None:
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
                    # The trace cannot be read to its end: what it showed is recorded, and the spend is incomplete.
                    record.update(accounting_complete=False,trace_error=type(exc).__name__,
                        **events.observations(),**events.spend(False))
                finally:events.close()
            else:
                # No trace: a host that was started may have spent; one that never started spent nothing.
                record.update(accounting_complete=False,observed_attempts=0,observed_recall_attempts=0,
                    reported_usd='0',unpriced_requests=0,unpriced_recall_requests=0,spent_usd='0',spend_complete=child is None)
            record['elapsed_seconds']=time.monotonic()-started
            total_recall_attempts+=record['observed_recall_attempts']
            total_attempts+=record['observed_attempts'];host_seconds_used+=record['elapsed_seconds']
            spent=EXACT.add(spent,Decimal(record['spent_usd']))
            records.append(record)
            try:write_new(target/'driver-receipt.json',record)
            except (OSError,ValueError) as exc:record['receipt_error']=type(exc).__name__
        if record.get('orchestration_error'):break
    reported=usd_sum(Decimal(r['reported_usd']) for r in records);unpriced=sum(r['unpriced_requests'] for r in records)
    recall_unpriced=sum(r['unpriced_recall_requests'] for r in records)
    # The subtotal covers all costs observed, even if a trace could not be reconciled.
    return dict(schema='player-driver/7',outcome=outcome,reason=reason,actors=records,ending_request=ending_request,
                observed_attempts=total_attempts,observed_recall_attempts=total_recall_attempts,host_seconds_used=host_seconds_used,
                reported_usd=usd_text(reported),unpriced_requests=unpriced,unpriced_request_usd=usd_text(bound),
                unpriced_recall_requests=recall_unpriced,unpriced_recall_request_usd=usd_text(recall_bound),
                spent_usd=usd_text(reported),
                spend_complete=all(r['spend_complete'] for r in records),
                configured_estimate_usd=configured_estimate(r.get('configured_estimate_usd',0) for r in records),
                missing_usage_attempts=sum(r.get('missing_usage_attempts',0) for r in records))
