"""Per-actor HTTP adapter. It owns no native writer, process or provider key."""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid

from .computer.protocol import ControlError, canonical, closed, decode_json, read_json

IMAGE_LIMIT = 16 * 1024 * 1024
EFFECT_TOOLS = {'computer_observe','computer_input','player_program_run','player_handoff'}


class PlayerClient:
    def __init__(self, config) -> None:
        value=read_json(config)
        closed(value,{'schema','base_url','session','actor_id','token'})
        if value['schema'] != 'player-adapter/1':
            raise ControlError('Unsupported player adapter; old mission profiles cannot run')
        url=urlsplit(value['base_url'])
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
                or url.username or url.password or url.path or url.query or url.fragment):
            raise ControlError('Only the selected loopback computer service is supported')
        for name in ('session','actor_id'):
            if not isinstance(value[name],str) or re.fullmatch('[0-9a-f]{32}',value[name]) is None:
                raise ControlError('Invalid mechanical actor/session identity')
        if not isinstance(value['token'],str) or re.fullmatch('[A-Za-z0-9_-]{32,128}',value['token']) is None:
            raise ControlError('Invalid actor capability')
        self.config=value
        self.sealed=False
        self.pending_handoff=None

    def _post(self, path: str, value: dict, *, timeout: float = 30., maximum: int = 8*1024*1024,
              image: bool = False) -> Any:
        request=Request(self.config['base_url']+path,data=canonical(value).encode('utf-8'),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+self.config['token']},method='POST')
        try:
            with urlopen(request,timeout=timeout) as response:
                data=response.read(maximum+1)
        except HTTPError as exc:
            data=exc.read(1048577)
            return decode_json(data,1048576)
        if len(data)>maximum:
            raise ControlError('Response exceeds frozen adapter byte capacity')
        return data if image else decode_json(data,maximum)

    def stop(self, reason: str='Actor adapter closed') -> dict:
        try:
            return self._post('/api/actor-stop',{'session':self.config['session'],'reason':reason[:600]},timeout=2.)
        except (OSError,ValueError):
            return dict(stop_requested=True,native_pause_confirmed=False,reason='Actor stop sent or unavailable; confirmation unknown')

    def close(self) -> None:
        if not self.sealed:
            self.stop()

    def _handoff(self, name, args, value) -> None:
        if name == 'player_handoff':
            if value.get('schema') == 'player-transport/1' and value.get('status') == 'unknown':
                self.pending_handoff=value['operation_id']
        original = self.pending_handoff if name == 'computer_result' else value.get('operation_id')
        if name not in ('player_handoff','computer_result') or original is None:
            return
        if name == 'computer_result' and args.get('operation_id') != original:
            return
        issued=value.get('handoff')
        if (value.get('schema') == 'computer-operation/1' and value.get('kind') == 'handoff'
                and value.get('status') == 'sealed' and isinstance(issued,dict)
                and issued.get('schema') == 'player-handoff/1'
                and value.get('operation_id') == original == issued.get('operation_id')
                and value.get('session') == self.config['session'] == issued.get('session')
                and value.get('actor_id') == self.config['actor_id'] == issued.get('actor_id')
                and issued.get('grants_authority') is False):
            self.sealed=True

    def call(self, name: str, args: dict) -> tuple[dict,bytes|None,bool]:
        identity=uuid.uuid4().hex
        kind='handoff' if name == 'player_handoff' else name
        try:
            response=self._post('/api/tool',dict(operation_id=identity,tool=name,arguments=args))
            if response.get('schema') == 'player-error/1':
                if response.get('submission') == 'uncertain':
                    raise ControlError('Service retained a possible original operation: '+response.get('reason',''))
                return response,None,True
            closed(response,{'schema','value'})
            if response['schema'] != 'player-response/1' or not isinstance(response['value'],dict):
                raise ControlError('Unsupported player response')
            value=response['value']
        except (OSError,ValueError) as exc:
            if name in EFFECT_TOOLS:
                self.stop('Uncertain actor HTTP operation; original collection only')
            value=dict(schema='player-transport/1',operation_id=identity,session=self.config['session'],
                actor_id=self.config['actor_id'],kind=kind,status='unknown',reason=str(exc)[:600],
                collect_with='computer_result' if name in ('computer_observe','computer_input','player_handoff') else 'player_result',
                input_replayed=False)
            self._handoff(name,args,value)
            return value,None,False
        self._handoff(name,args,value)
        metadata=value.get('source')
        png=None
        if isinstance(metadata,dict) and metadata.get('schema') == 'computer-source/1':
            try:
                png=self._post('/api/player-source',{'source_id':metadata['source_id']},image=True,maximum=IMAGE_LIMIT)
                if not isinstance(png,bytes) or hashlib.sha256(png).hexdigest() != metadata['sha256']:
                    raise ControlError('Exact source image unavailable or digest differs')
            except (OSError,ValueError):
                # The operation's exact delivery remains known. Never replay it
                # merely because a separate immutable-image read failed.
                png=None
                value=dict(value,image_unavailable=True,image_limit_bytes=IMAGE_LIMIT,
                           image_note='Full source remains retained; this adapter did not return its pixels.')
        return value,png,False
