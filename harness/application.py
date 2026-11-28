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
from .player.source_index import IMAGE_LIMIT, SOURCE_READ_SCHEMA, SourceIndex, SourceUnavailable
from .player_tools import tool_specs

READ_TOOLS = {'computer_result', 'player_source', 'player_result', 'player_knowledge_read', 'player_knowledge_query'}


class Application:
    """One serialized playing-service caller; operator Pause bypasses this lock."""
    def __init__(
        self,
        runtime: ComputerRuntime,
        journal: Journal,
        context_directory: Path,
        *,
        knowledge: Path,
        source_index: SourceIndex | None = None,
        initial_agenda_refs: tuple[str, ...] | set[str] | list[str] = (),
    ) -> None:
        self.runtime, self.journal = runtime, journal
        self.knowledge = Knowledge(knowledge)
        self.knowledge_lock = threading.Lock()
        self.source_index = source_index
        self._disclosed_sources: set[str] = set()
        self._sync_disclosed(self.knowledge)
        for ref in initial_agenda_refs:
            if isinstance(ref, str) and (self.source_index is not None and self.source_index.contains(ref)):
                self._disclosed_sources.add(ref)
        self.context_directory = context_directory
        context_directory.mkdir(mode=0o700)
        self.serial = threading.RLock()
        self.host: dict[str, Any] | None = None
        self.final_actor: str | None = None

    def _sync_disclosed(self, knowledge: Knowledge) -> None:
        for fact in knowledge.value.get('facts', ()):
            for src_id in fact.get('citation_source_ids', ()):
                self._disclosed_sources.add(src_id)
            depiction = fact.get('depiction_source_id')
            if isinstance(depiction, str):
                self._disclosed_sources.add(depiction)

    def _clock_label(self, identity: str) -> str | None:
        with self.knowledge_lock:
            clocks = self.knowledge.value.get('frame_clocks', {})
            label = clocks.get(identity)
            return label if isinstance(label, str) else None

    def set_knowledge(self, knowledge: Knowledge) -> None:
        """Serve a newer delivered version to every later knowledge read; each result names its version.

        The swap has a lock of its own, held only for the assignment, so the driver that adopts a
        version never waits for a tool call in progress and a read sees one whole version."""
        with self.knowledge_lock:
            self.knowledge = knowledge
            self._sync_disclosed(knowledge)

    def status(self) -> dict[str, Any]:
        return dict(self.runtime.status(), host=copy.deepcopy(self.host), player_claims=[])

    def submission_status(self, actor_id: str, identity: str) -> str:
        if self.runtime.store.operation_exists(identity, actor_id):
            return 'uncertain'
        with self.serial:
            return 'uncertain' if self.journal.hint_exists(identity, actor_id) else 'none'

    def read_player_source(self, identity: str, actor_id: str | None = None) -> tuple[dict[str, Any], bytes | None]:
        """Resolve `identity` under uniform frozen-eligibility + live-disclosure rules (`player-source-read/2`).

        Current-session frames stay clickable (`issue_source` called); ancestor/historical frames never
        call `issue_source` (`clickable: false`) and return structured `status: "unavailable"` on failure
        without tripping live `runtime.stop`.
        """
        now = time.time()
        with self.serial:
            if not isinstance(identity, str) or not identity or len(identity) > 128:
                return dict(schema=SOURCE_READ_SCHEMA, status='unavailable', source_id=str(identity)[:128],
                            reason='unknown-or-out-of-scope', read_wall=now), None
            # 1. Current mechanical session runtime store (clickable).
            if self.runtime.store.has_source(identity):
                value, png = self.runtime.source(identity)
                if actor_id is not None:
                    self.runtime.store.issue_source(actor_id, identity)
                self._disclosed_sources.add(identity)
                envelope: dict[str, Any] = dict(
                    schema=SOURCE_READ_SCHEMA,
                    status='available',
                    source_id=identity,
                    source=value,
                    origin=dict(admission='current', actor=actor_id or '001', step=None),
                    clickable=True,
                    read_wall=now,
                )
                clock = self._clock_label(identity)
                if clock is not None:
                    envelope['clock_label'] = clock
                return envelope, png

            # 2. Frozen same-lineage ancestor index (gated by live disclosure, never clickable, never stops live runtime).
            with self.knowledge_lock:
                disclosed = identity in self._disclosed_sources
            if self.source_index is not None and self.source_index.contains(identity):
                if not disclosed:
                    return dict(schema=SOURCE_READ_SCHEMA, status='unavailable', source_id=identity,
                                reason='unknown-or-out-of-scope', read_wall=now), None
                try:
                    value, png, origin = self.source_index.read_verified(identity, max_bytes=IMAGE_LIMIT)
                except SourceUnavailable as exc:
                    return dict(schema=SOURCE_READ_SCHEMA, status='unavailable', source_id=identity,
                                reason=exc.reason, read_wall=now), None
                envelope = dict(
                    schema=SOURCE_READ_SCHEMA,
                    status='available',
                    source_id=identity,
                    source=value,
                    origin=origin,
                    clickable=False,
                    read_wall=now,
                )
                clock = self._clock_label(identity)
                if clock is not None:
                    envelope['clock_label'] = clock
                return envelope, png

            # 3. Current-session journal source fallback (never fabricate aliases for cross-session sources).
            if self.journal.has_source(identity):
                try:
                    value, png = self.journal.read_source(identity)
                except PlayerError:
                    return dict(schema=SOURCE_READ_SCHEMA, status='unavailable', source_id=identity,
                                reason='integrity-failed', read_wall=now), None
                if value.get('session') != self.runtime.session:
                    return dict(schema=SOURCE_READ_SCHEMA, status='unavailable', source_id=identity,
                                reason='unknown-or-out-of-scope', read_wall=now), None
                if len(png) > IMAGE_LIMIT:
                    return dict(schema=SOURCE_READ_SCHEMA, status='unavailable', source_id=identity,
                                reason='image-limit', read_wall=now), None
                envelope = dict(
                    schema=SOURCE_READ_SCHEMA,
                    status='available',
                    source_id=identity,
                    source=value,
                    origin=dict(admission='current', actor=actor_id or '001', step=None),
                    clickable=False,
                    read_wall=now,
                )
                clock = self._clock_label(identity)
                if clock is not None:
                    envelope['clock_label'] = clock
                return envelope, png

            return dict(schema=SOURCE_READ_SCHEMA, status='unavailable', source_id=identity,
                        reason='unknown-or-out-of-scope', read_wall=now), None

    def source(self, identity: str, actor_id: str | None = None) -> tuple[dict[str, Any], bytes]:
        """Authenticated `/api/player-source` image lookup using the exact same eligibility & disclosure gate."""
        envelope, png = self.read_player_source(identity, actor_id)
        if envelope['status'] != 'available' or png is None:
            raise SourceUnavailable(envelope['reason'], f'Source unavailable: {envelope["reason"]}')
        return envelope['source'], png

    def snapshot(self, actor_id: str, summary: str) -> tuple[str, str]:
        if not isinstance(summary, str) or len(summary) > 8192:
            raise PlayerError('Handoff summary must be within 8192 characters')
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
                envelope, png = self.read_player_source(semantic['source_id'], actor)
                return envelope, png
            if name == 'player_knowledge_read':
                if not {'id_or_title'} <= semantic.keys() or semantic.keys() - {'id_or_title', 'by'}:
                    raise PlayerError('Knowledge read requires id_or_title and optional by')
                if not isinstance(semantic['id_or_title'], str):
                    raise PlayerError('Knowledge argument must be text')
                with self.knowledge_lock:
                    knowledge = self.knowledge
                return knowledge.read(semantic['id_or_title'], by=semantic.get('by', 'any')), None
            if name == 'player_knowledge_query':
                closed(semantic, {'query'})
                if not isinstance(semantic['query'], str):
                    raise PlayerError('Knowledge argument must be text')
                with self.knowledge_lock:
                    knowledge = self.knowledge
                return knowledge.query(semantic['query']), None
            if name == 'player_hint':
                if not {'text'} <= semantic.keys() or semantic.keys() - {'text', 'source_ids'}:
                    raise PlayerError('Hint requires text and optional source_ids')
                ids = references(semantic.get('source_ids', []))
                for source_id in ids:
                    if not self.journal.has_source(source_id):
                        envelope, png = self.read_player_source(source_id, actor)
                        if envelope['status'] != 'available' or png is None:
                            raise PlayerError(f'Unknown or unavailable source reference: {source_id}')
                        self.journal.register_source(envelope['source'], png)
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
