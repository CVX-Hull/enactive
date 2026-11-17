"""Composition of mechanical control and fallible player services."""
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
from .player.contracts import PlayerError, common_arguments, references
from .player.journal import Journal
from .player.knowledge import Knowledge
from .player_tools import tool_specs

READ_TOOLS = {'computer_result', 'player_source', 'player_result', 'player_knowledge_read', 'player_knowledge_query'}


class Application:
    """One serialized playing-service caller; operator Pause bypasses this lock."""
    def __init__(self, runtime: ComputerRuntime, journal: Journal, context_directory: Path, *, knowledge: Path) -> None:
        self.runtime, self.journal = runtime, journal
        self.knowledge = Knowledge(knowledge)
        self.context_directory = context_directory
        context_directory.mkdir(mode=0o700)
        self.serial = threading.RLock()
        self.host: dict[str, Any] | None = None
        self.final_actor: str | None = None

    def status(self) -> dict[str, Any]:
        return dict(self.runtime.status(), host=copy.deepcopy(self.host), player_claims=[])

    def submission_status(self, actor_id: str, identity: str) -> str:
        if self.runtime.store.operation_exists(identity, actor_id):
            return 'uncertain'
        with self.serial:
            return 'uncertain' if self.journal.hint_exists(identity, actor_id) else 'none'

    def source(self, identity: str, actor_id: str | None = None) -> tuple[dict[str, Any], bytes]:
        with self.serial:
            value, png = (self.journal.read_source(identity) if self.journal.has_source(identity)
                          else self.runtime.source(identity))
            if actor_id is not None and self.runtime.store.has_source(identity):
                self.runtime.store.issue_source(actor_id, identity)
            return value, png

    def snapshot(self, actor_id: str, summary: str) -> tuple[str, str]:
        if not isinstance(summary, str) or len(summary) > 8192:
            raise PlayerError('Handoff summary must be within8192 characters')
        identity = uuid.uuid4().hex
        packet = dict(schema='player-handoff-context/2', context_id=identity, session=self.runtime.session,
                      actor_id=actor_id, summary=summary, summary_is_hint=True, created_wall=time.time(),
                      grants_authority=False)
        data = (canonical(packet) + '\n').encode('utf-8')
        with (self.context_directory / (identity + '.json')).open('xb') as stream:
            stream.write(data)
        return identity, hashlib.sha256(data).hexdigest()

    def call(self, token: str, name: str, args: dict[str, Any], identity: str) -> tuple[dict[str, Any], bytes | None]:
        actor = self.runtime.authorize(token, write=name not in READ_TOOLS)
        with self.serial:
            self.runtime.authorize(token, write=name not in READ_TOOLS)
            if name not in tool_specs():
                raise ControlError('Unknown current tool')
            semantic, intent, cites = common_arguments(args)
            fresh = self.journal.record_call(identity, actor, name, args)
            if name in ('computer_observe', 'computer_input', 'player_handoff') and not fresh:
                if self.runtime.store.operation_exists(identity, actor):
                    return self.runtime.result(actor, identity)
            if self.runtime.store.operation_exists(identity) and name not in ('computer_observe', 'computer_input', 'player_handoff'):
                raise ControlError('Original public identity belongs to another service; collect it, never dispatch')
            if name == 'computer_observe':
                closed(semantic, set())
                return self.runtime.observe(actor, operation_id=identity)
            if name == 'computer_input':
                if not {'actions'} <= semantic.keys() or semantic.keys() - {'actions', 'source_id'}:
                    raise ControlError('Input requires actions and optional source_id')
                return self.runtime.input(actor, semantic['actions'], source_id=semantic.get('source_id'), operation_id=identity)
            if name == 'computer_result':
                closed(semantic, {'operation_id'})
                return self.runtime.result(actor, semantic['operation_id'])
            if name == 'computer_stop':
                closed(semantic, set())
                return self.runtime.stop('Player chose permanent stop'), None
            if name == 'player_source':
                closed(semantic, {'source_id'})
                value, png = self.source(semantic['source_id'], actor)
                return dict(schema='player-source-read/1', source=value, read_wall=time.time()), png
            if name in ('player_knowledge_read', 'player_knowledge_query'):
                key = 'id_or_title' if name == 'player_knowledge_read' else 'query'
                closed(semantic, {key})
                if not isinstance(semantic[key], str):
                    raise PlayerError('Knowledge argument must be text')
                return (self.knowledge.read(semantic[key]) if key == 'id_or_title' else self.knowledge.query(semantic[key])), None
            if name == 'player_hint':
                if not {'text'} <= semantic.keys() or semantic.keys() - {'text', 'source_ids'}:
                    raise PlayerError('Hint requires text and optional source_ids')
                ids = references(semantic.get('source_ids', []))
                for source_id in ids:
                    if not self.journal.has_source(source_id):
                        metadata, png = self.runtime.source(source_id)
                        self.journal.register_source(metadata, png)
                return self.journal.hint(identity, actor, semantic['text'], ids, intent, cites), None
            if name == 'player_result':
                closed(semantic, {'operation_id'})
                return self.journal.service_result(semantic['operation_id'], actor), None
            if name == 'player_handoff':
                closed(semantic, {'summary'})
                if actor == self.final_actor:
                    raise PlayerError('Handoff not sealed: no successor is available, because this is the final actor. '
                                      'Write your report and call player_finish.')
                context_id, sha = self.snapshot(actor, semantic['summary'])
                return self.runtime.seal_actor(actor, identity, context_id, sha), None
            raise ControlError('Unknown current tool')
