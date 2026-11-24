"""Finite actors of the selected player host over one live mechanical custodian."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

from harness.computer.channel import NATIVE_EOF_REASON
from harness.computer.launch import close_group
from harness.computer.protocol import ControlError,canonical,read_json
from harness.jsonio import strict_loads
from harness.player.knowledge import Knowledge,version_number
from harness.player_client import ADAPTER_CLOSE_REASON
from tools.campaign_package import EXACT,counted_usd,declared_floor,usd_sum,usd_text
from tools.configure_player_tools import ROOT,configuration

#: An actor's append-only list of adopted versions and covered-prefix updates, beside its frozen inputs.
UPDATES_FILE='knowledge-updates.jsonl'
UPDATE_ENTRY_SCHEMA='knowledge-update-entry/1'
COVERAGE_ENTRY_SCHEMA='coverage-update-entry/1'
COVERED_PREFIX_FILE='covered-prefix.json'
COVERED_PREFIX_SCHEMA='curator-covered-prefix/1'
VERSION_FILE=re.compile(r'v(0|[1-9][0-9]*)\.json')
HEX_ID=re.compile(r'[0-9a-f]{32}')


def write_new(path: Path,value,*,text=False) -> None:
    with path.open('x') as stream:
        stream.write(value if text else canonical(value)+'\n')
    path.chmod(0o600)


class LiveKnowledge:
    """Newer delivered-knowledge versions for the actors of one run (`live_knowledge_updates`).

    The curator runner leaves each confirmed version whole as `vN.json` in `source`. `poll` adopts the
    highest one above the current version that is `delivered-knowledge/2`, names version `vN` and comes
    from the repository of the version already held (any repository after the empty file). For the
    running actor (`begin`) it copies the file to `knowledge/vN.json` in the actor's directory, publishes
    the actor's update list with one more `knowledge-update-entry/1` line and has the application serve the
    version; the host reads that list. Between actors (after `end`) a version is adopted for the next
    actor's frozen file alone, which `begin` returns.

    The runner also leaves its unbroken covered prefix. The driver lists verified coverage only
    after adopting the version it names. A restore closes the coverage path for the admission,
    and a successor's update list starts with that invalidation.

    During a run `start` makes the looks on a daemon thread, so a slow or stalled read of `source` never
    holds up the driver's deadline checks, settlement or handoff. `lock` protects the adopted state
    and actor generation. Background list writes happen outside it and are rolled back when stale.
    `begin` and `end` never read `source`. The next look decides again for the successor.

    Source and publication failures are reported on stderr while play continues with the state
    already held. A refused version is never tried again. Coverage is retried on later looks.
    """
    def __init__(self,source: Path | None,package: Path,session: str | None=None):
        self.source=source
        self.session=session
        self.data=package.read_bytes()
        self.current=Knowledge(package)
        self.refused=set()
        self.last_coverage_bytes: bytes | None = None
        self.current_coverage: dict | None = None
        self.actor_coverage: dict | None = None
        self.restored = False
        self.coverage_reports: set[str] = set()
        self.lock=threading.Lock()
        # One look at a time; held across reads of `source`, so only the looking thread ever waits on it.
        self.looking=threading.Lock()
        self.target=None;self.generation=0;self.closed=False
        self.stopping=threading.Event();self.thread=None

    @property
    def number(self) -> int:
        number=version_number(self.current.value['version'])
        return -1 if number is None else number

    def begin(self,target: Path) -> bytes:
        """Attach the running actor and return the adopted version's bytes for its frozen file. `target`
        holds the actor's update list already (empty). Never reads `source`."""
        with self.lock:
            self.actor_coverage = None
            if self.restored:
                try:
                    listing, _, _ = self._prepare_listing(target,self.current_coverage)
                    self._replace_listing(listing)
                    self.actor_coverage = self.current_coverage
                except OSError as exc:
                    self._report_coverage(exc)
            self.target=target;self.generation+=1
            return self.data

    def end(self) -> None:
        """Detach the actor that has stopped; later versions wait for the next actor."""
        with self.lock:
            self.target=None;self.generation+=1

    def start(self,application,interval: float=.1) -> None:
        """Look every `interval` seconds on a daemon thread until `close`."""
        if self.source is None or self.thread is not None:return
        def looks():
            while not self.stopping.is_set():
                self.poll(application)
                self.stopping.wait(interval)
        self.thread=threading.Thread(target=looks,name='live-knowledge',daemon=True)
        self.thread.start()

    def close(self) -> None:
        """No adoption after this returns; a look stalled on `source` is left to the daemon thread."""
        with self.lock:
            self.closed=True;self.target=None;self.generation+=1
        self.stopping.set()

    def poll(self,application) -> None:
        """One look at the source, for the running actor if one is attached."""
        if self.source is None:return
        with self.looking:
            with self.lock:
                if self.closed:return
                target,generation,held=self.target,self.generation,self.current
            try:names=os.listdir(self.source)
            except OSError:names=()  # no version has been left yet
            numbers={int(match[1]) for name in names if (match:=VERSION_FILE.fullmatch(name))}
            least=version_number(held.value['version'])
            for number in sorted((n for n in numbers if n>(-1 if least is None else least) and n not in self.refused),reverse=True):
                try:
                    self._adopt(number,application,target,generation,held)
                    break
                except Exception as exc:
                    self.refused.add(number)
                    print(f'campaign_player: live knowledge v{number} refused: {type(exc).__name__}: {str(exc)[:300]}',
                          file=sys.stderr,flush=True)
            self._poll_coverage(target,generation)

    def _coverage_entry(self,data: bytes,number: int) -> dict:
        value = strict_loads(data)
        fields = {'schema', 'session', 'actor', 'actor_id', 'operation_id', 'version', 'restored'}
        if not isinstance(value,dict) or set(value) != fields or value['schema'] != COVERED_PREFIX_SCHEMA:
            raise ControlError(f'Expected a closed {COVERED_PREFIX_SCHEMA} record')
        session = value['session']
        if (not isinstance(session,str) or not HEX_ID.fullmatch(session)
                or self.session is not None and session != self.session):
            raise ControlError('Covered prefix belongs to an invalid or different session')
        if type(value['restored']) is not bool:
            raise ControlError('Covered prefix restore flag must be a boolean')
        if value['restored']:
            if any(value[key] is not None for key in ('actor','actor_id','operation_id','version')):
                raise ControlError('A restored prefix must have a null endpoint and version')
        else:
            if (not isinstance(value['actor'],str) or not value['actor'] or any(
                    not isinstance(value[key],str) or not HEX_ID.fullmatch(value[key])
                    for key in ('actor_id','operation_id'))):
                raise ControlError('Covered prefix has an invalid endpoint')
            version = version_number(value['version'])
            if version is None or not 1 <= version <= number:
                raise ControlError('Covered prefix must name an adopted publication')
        return dict(schema=COVERAGE_ENTRY_SCHEMA,session=session,actor_id=value['actor_id'],
                    operation_id=value['operation_id'],version=value['version'],restored=value['restored'])

    def _report_coverage(self,exc: Exception) -> None:
        report = f'{type(exc).__name__}: {str(exc)[:300]}'
        if report not in self.coverage_reports:
            self.coverage_reports.add(report)
            print(f'campaign_player: live coverage refused: {report}',file=sys.stderr,flush=True)

    def _poll_coverage(self,target: Path | None,generation: int) -> None:
        with self.lock:
            if self.closed or self.generation != generation:
                return
            previous, entry = self.last_coverage_bytes, self.current_coverage
            restored, actor_coverage, number = self.restored, self.actor_coverage, self.number
        try:
            if restored:
                data = previous
            else:
                try:
                    data = (self.source/COVERED_PREFIX_FILE).read_bytes()
                except FileNotFoundError:
                    return
            if data != previous:
                entry = self._coverage_entry(data,number)
            elif entry is None or target is None or entry == actor_coverage:
                return

            def adopt() -> None:
                self.last_coverage_bytes, self.current_coverage = data, entry
                if target is not None:
                    self.actor_coverage = entry
                self.restored = entry['restored']

            listing_target = target if entry != actor_coverage else None
            self._publish_entry(entry,listing_target,generation,adopt)
        except Exception as exc:  # noqa: BLE001 - live coverage is optional and is retried off the driver thread
            self._report_coverage(exc)

    def _adopt(self,number: int,application,target: Path | None,generation: int,held: Knowledge) -> None:
        data=(self.source/f'v{number}.json').read_bytes()
        knowledge=Knowledge.from_dict(strict_loads(data),f'live knowledge v{number}')
        value=knowledge.value
        if value['version']!=f'v{number}':raise ControlError('The file names another version')
        repository=held.value['repository_id']
        if repository is not None and value['repository_id']!=repository:
            raise ControlError('The version comes from another knowledge repository')
        entry=None
        if target is not None:
            (target/'knowledge').mkdir(mode=0o700,exist_ok=True)
            name=f'knowledge/v{number}.json'
            temporary=target/'knowledge'/f'.v{number}.json.tmp'
            with temporary.open('wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            temporary.chmod(0o600)
            os.replace(temporary,target/name)
            entry=dict(schema=UPDATE_ENTRY_SCHEMA,version=value['version'],commit=value['commit'],
                repository_id=value['repository_id'],file=name,sha256=hashlib.sha256(data).hexdigest(),coverage=value['coverage'])

        def adopt() -> None:
            application.set_knowledge(knowledge)
            self.current,self.data=knowledge,data

        self._publish_entry(entry,target,generation,adopt)

    @staticmethod
    def _write_listing(path: Path,data: bytes) -> None:
        try:
            with path.open('wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            path.chmod(0o600)
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def _prepare_listing(self,target: Path,entry: dict) -> tuple[tuple[Path,Path],bytes,bool]:
        path = target/UPDATES_FILE
        try:
            prefix, existed = path.read_bytes(), True
        except FileNotFoundError:
            prefix, existed = b'', False
        listing = (target/f'.{UPDATES_FILE}.tmp',path)
        self._write_listing(listing[0],prefix+(canonical(entry)+'\n').encode('utf-8'))
        return listing,prefix,existed

    @staticmethod
    def _replace_listing(listing: tuple[Path,Path]) -> None:
        try:
            os.replace(*listing)
        except BaseException:
            listing[0].unlink(missing_ok=True)
            raise

    def _publish_entry(self,entry: dict | None,target: Path | None,generation: int,adopt: Callable[[],None]) -> None:
        # The host reads either the old list or the complete new line. Adopt only after the rename,
        # then roll back on this background thread if the actor stopped while the rename was in flight.
        listing = None
        if target is not None:
            listing,prefix,existed = self._prepare_listing(target,entry)
        with self.lock:
            stale = self.closed or self.generation != generation
        if stale:
            # Another actor began, or this one ended, while the version was prepared: the next look decides again.
            if listing is not None:listing[0].unlink(missing_ok=True)
            return
        if listing is not None:
            # Keep the background rename outside `self.lock` so it cannot block actor lifecycle calls.
            self._replace_listing(listing)
        with self.lock:
            stale = self.closed or self.generation != generation
            if not stale:
                adopt()
        if stale and listing is not None:
            # The actor ended (or the driver closed) while `os.replace` was in flight: restore the old actor's
            # list to its prior bytes on this background thread so it never records an unadopted version.
            try:
                if existed:
                    self._write_listing(listing[0],prefix)
                    self._replace_listing(listing)
                else:
                    listing[1].unlink(missing_ok=True)
            except OSError as error:
                listing[0].unlink(missing_ok=True)
                print(f'campaign_player: live knowledge list rollback failed: {type(error).__name__}: {error}',file=sys.stderr)


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
            if kind in ('handoff','player-finish','settled'):
                # These records are copied into the receipt. Reject data the writer cannot retain.
                canonical(value).encode('utf-8')
            if kind=='host-start':
                if (self.started or type(value.get('telemetry_version')) is not int or value['telemetry_version']!=11
                        or value.get('schema')!='player-host/11'):raise ControlError('Unsupported/repeated current host trace')
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


def finish_interruption(channel, *, accepted_finish: bool=True, native_exit_zero: Callable[[], bool] | None=None):
    """Classify the first fence. Only accepted cleanup can excuse a stop origin."""
    if not channel.stopped.is_set():return None
    origin=channel.stop_origin()
    if accepted_finish:
        if origin['reason']==ADAPTER_CLOSE_REASON:return None
        if origin['reason']==NATIVE_EOF_REASON and native_exit_zero is not None and native_exit_zero():return None
    return dict(reason='Input permanently fenced outside accepted host cleanup',stop=origin)


def run_hosts(directory: Path,profile: dict,route: dict,application,secret: str,
              stopped: threading.Event,deadline: float,live_updates: Path | None=None,
              *,native_exit_zero: Callable[[], bool] | None=None) -> dict:
    """`live_updates` is the directory where newer delivered-knowledge versions arrive during the run,
    or None when the package does not deliver them (`LiveKnowledge`)."""
    actors=directory/'actors';actors.mkdir(mode=0o700)
    live=None
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
            # The actor starts from the latest version adopted in this run: the package's frozen file
            # until a newer one arrived. The snapshot is in memory; `source` is read only on the looking
            # thread, so no read of it delays a handoff.
            if live is None:
                live=LiveKnowledge(live_updates,directory/'delivered-knowledge.json',session=profile['session'])
                live.start(application)
            if live_updates is not None:write_new(target/UPDATES_FILE,'',text=True)
            with (target/'delivered-knowledge.json').open('xb') as stream:
                stream.write(live.begin(target))
            (target/'delivered-knowledge.json').chmod(0o600)
            write_new(target/'frozen.json',dict(schema='player-host-inputs/4',actor_id=actor['actor_id'],session=profile['session'],
                finish_reserve_usd=profile['ending_reserve']['usd'],
                knowledge_updates=UPDATES_FILE if live_updates is not None else None,
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
                '--effort',profile['effort'],'--timeout-seconds',str(seconds),'-o',str(target/'player-final.txt'),
                *(['--knowledge-updates',str(target/UPDATES_FILE)] if live_updates is not None else [])]
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
                verify_exit=(native_exit_zero if disposition in ('task_complete','external_stop_complete')
                    and not cleanup['signals'] and not stopped.is_set() else None)
                interruption=finish_interruption(application.runtime.channel,native_exit_zero=verify_exit)
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
            # Nothing more is listed for an actor that has stopped; a version left now waits for the next one.
            if live is not None:live.end()
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
            if child is not None and outcome=='incomplete' and application.runtime.channel.fault is not None:
                interruption=finish_interruption(application.runtime.channel,accepted_finish=False)
                if interruption is not None:
                    record['interruption']=interruption
                    outcome='interrupted';reason=interruption['reason']
            record['elapsed_seconds']=time.monotonic()-started
            total_recall_attempts+=record['observed_recall_attempts']
            total_attempts+=record['observed_attempts'];host_seconds_used+=record['elapsed_seconds']
            spent=EXACT.add(spent,Decimal(record['spent_usd']))
            records.append(record)
            try:write_new(target/'driver-receipt.json',record)
            except (OSError,ValueError) as exc:record['receipt_error']=type(exc).__name__
        if outcome=='interrupted' or record.get('orchestration_error'):break
    if live is not None:live.close()
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
