"""One bounded mission writer composing controller, evidence, memory and ledger.

Admission is not native Resume. Cached status is advisory data; process-local
leases and source bindings are never restored from disk or accepted from JSON.
"""
from __future__ import annotations

import copy
from contextlib import ExitStack
from dataclasses import asdict, dataclass, field, replace
import hashlib
import math
import os
from queue import Empty, Full, Queue
import threading
import time
from typing import Any
from uuid import UUID

from .controller import Controller, ControlError, MissionInputRefusal, MissionLease, validate_state
from .native_process import NativeProcess
from .mission_lifecycle import LifecycleRequestRefusal, NormalPhase, RegisteredLifecycle
from .mission_handoff import HandoffEvidenceError, HandoffPhase, RegisteredHandoff
from .mission_activity import ActivityFeedback, ActivityIntent, ActivityPhase, RegisteredActivity
from .mission_recovery import RecoveryEvidenceError, RecoveryPhase, RegisteredRecovery
from .mission_reflection import RegisteredReflection
from .gameplay.campaign_memory import CampaignMemory
from .gameplay.contracts import ContractError, EvidenceRef, PrimitiveResult
from .gameplay.evidence import MAX_AGE_SECONDS, MAX_FRAME_BYTES, CapacityError, CapacityReservation, EvidenceError, EvidenceStore, FreshnessError, same_native_custody, same_native_state, validate_native_progression
from .gameplay.interaction import MenuIntent, MenuOutcome, MenuSkill
from .gameplay.contracts import canonical
from .gameplay.mission_contracts import VERSION, MissionAdmission, InputObservation, SourceBinding, SourceRevalidation, MemoryRequestRefusal, validate_submission
from .gameplay.mission_ledger import BudgetError, LedgerError, LocalBudgetRefusal, MissionLedger, TERMINAL
from .gameplay.native_receipts import compact_native_ack
from .gameplay.navigation import NavigationIntent, NavigationOutcome, NavigationSkill, ObservedMap
from .gameplay.input_contracts import ControlIntent, ControlOutcome
from .gameplay.semantic_controls import SemanticControlSkill
from .gameplay.ordinary_input import OrdinaryInputSkill
from .gameplay.program_input import ProgramInputSkill
from .gameplay.timeline import SessionContinuity, game_timeline

MissionIntent = NavigationIntent | MenuIntent | ControlIntent


class _Cancelled(ContractError):
    pass


class _LocalGameLimit(LocalBudgetRefusal):
    """An original macro/child game cap, distinct from custody or mission loss."""


@dataclass
class _Work:
    request: dict
    ready: threading.Event = field(default_factory=threading.Event)
    cancelled: threading.Event = field(default_factory=threading.Event)
    response: dict | None = None
    game_anchor: EvidenceRef | None = None
    finish_epoch: int | None = None
    finish_mark: tuple[str, int] | None = None


@dataclass(frozen=True)
class _PromptPhase:
    root_id: str
    checkpoint: EvidenceRef
    game_anchor: EvidenceRef
    actor_id: str
    epoch: int
    controller_boot_id: str
    operator_generation: int
    takeover_generation: int
    quantity_editor: bool = False
    observation_generation: int | None = None


@dataclass(frozen=True)
class _OwnedLaunch:
    request_id: str
    launch_id: str
    checkpoint: EvidenceRef
    operator_mark: tuple[str, int]
    takeover_generation: int


@dataclass(frozen=True)
class _ExitPhase:
    root_id: str
    checkpoint: EvidenceRef
    launch: _OwnedLaunch
    actor_id: str
    epoch: int
    saved_checkpoint: str | None = None


@dataclass(frozen=True)
class _ResumeIntent:
    logical_id: str
    before: EvidenceRef
    expected_boundary_id: str
    kind: str = "resume"
    action: None = None
    revalidation: None = None


class MissionRuntime:
    """One serialized worker and one bounded queue; constructor sends no input.

    Only the worker mutates mission storage; indexed presentation reads use the
    store's own lock. The metadata lock protects copied
    responses and cancellation handles, never file/native/SQLite operations.
    Controller Pause itself can wait on controller-owned durable critical sections.
    """
    def __init__(self, controller: Controller, *, clock=time.monotonic, wall_clock=time.time):
        self.controller = controller
        self._clock, self._wall = clock, wall_clock
        self._metadata = threading.Lock()
        self._queue: Queue[_Work] = Queue(maxsize=1)
        self._closed = threading.Event()
        self._pending_pauses: list[tuple[str, str]] = []
        self._handles: list[_Work] = []
        self._operations: dict[str, dict] = {}
        self._snapshot: dict | None = None
        self._active: _Work | None = None
        self._ledger: MissionLedger | None = None
        self._store: EvidenceStore | None = None
        self._presentation_store: tuple[str, EvidenceStore, CampaignMemory] | None = None
        self._memory: CampaignMemory | None = None
        self._admission: MissionAdmission | None = None
        self._lease: MissionLease | None = None
        self._bindings: dict[str, tuple[EvidenceRef, SourceBinding]] = {}
        self._current: EvidenceRef | None = None
        self._map: ObservedMap | None = None
        self._rotation: tuple | None = None
        self._prompt_phase: _PromptPhase | None = None
        self._mission_deadline: float | None = None
        self._game_cost: int | None = None
        self._timeline_links: tuple[SessionContinuity, ...] = ()
        self._native: NativeProcess | None = None
        self._native_owner: tuple[str, str] | None = None
        self._native_facts: dict | None = None
        self._lost_process_custody: tuple[str, ...] = ()
        self._owned_launch: _OwnedLaunch | None = None
        self._exit_phase: _ExitPhase | None = None
        self._exit_candidate: tuple[_ExitPhase, str, dict, CapacityReservation | None] | None = None
        self._memory_version = 0
        self._last_context_id: str | None = None
        self._last_memory_context: dict | None = None
        self._issued_packets: dict[str, dict] = {}
        self._last_receipt: dict | None = None
        self._progress: dict | None = None
        self._skill: str | None = None
        self._diagnostic: str | None = None
        self._registered_lifecycle = RegisteredLifecycle(self)
        self._registered_handoff = RegisteredHandoff(self)
        self._registered_activity = RegisteredActivity(self)
        self._registered_recovery = RegisteredRecovery(self)
        self._registered_reflection = RegisteredReflection(self)
        self._thread = threading.Thread(target=self._work, name="mission-runtime", daemon=True)
        self._thread.start()

    def _clocks(self) -> dict:
        return {"now_monotonic": self._clock(), "now_timestamp_ms": int(self._wall() * 1000)}

    def status(self) -> dict | None:
        """Read only cache and clocks; never reconcile, verify or complete work."""
        with self._metadata:
            value = copy.deepcopy(self._snapshot)
        if value is not None:
            now, wall = self._clock(), self._wall()
            valid_clock = (type(now) in (int, float) and type(wall) in (int, float)
                and math.isfinite(now) and math.isfinite(wall) and 0 <= now <= 1e12 and 0 <= wall <= 1e12)
            value["clock_valid"] = valid_clock and wall >= value["last_wall"]
            value["remaining_limits"]["wall_seconds"] = max(0, value["deadline"] - max(wall, value["last_wall"])) if valid_clock else 0
            source = value["current_source"]
            value["freshness"] = {"age_seconds": None, "fresh": False}
            if source is not None and valid_clock:
                age = now - source["received_monotonic"]
                native_age = int(wall * 1000) - source["timestamp_ms"]
                value["freshness"] = {"age_seconds": max(0, age),
                    "fresh": 0 <= age <= 3 and -1000 <= native_age <= 3000}
        return value

    def _response(self, status: str, **fields: Any) -> dict:
        return {"status": status, "mission": self.status(), **copy.deepcopy(fields)}

    def source(self, mission_id: str, source_id: str) -> tuple[dict, bytes]:
        """Indexed historical presentation only; never Observe, reconcile or resume."""
        with self._metadata:
            binding = self._presentation_store
            if self._closed.is_set() or binding is None:
                raise EvidenceError("No matching admitted evidence store")
            store = binding[1]
            memory = binding[2]
        if binding[0] != mission_id:
            if memory.library is None:
                raise EvidenceError("No matching admitted evidence store or pinned procedure library")
            return memory.procedure_source(mission_id, source_id)
        return store.export_source(source_id)

    def reflection_command(self, value: dict) -> dict:
        from .gameplay.reflection import validate_command
        command = validate_command(value)
        exchange = self._registered_reflection.current(command["mission_id"], command["reflector_id"])
        return exchange.offer(command)

    def reflection_result(self, *, mission_id: str, reflector_id: str, command_id: str) -> dict:
        return self._registered_reflection.current(mission_id, reflector_id).collect(command_id)

    def reflection_next(self, *, mission_id: str, reflector_id: str, wait_seconds: float = 0) -> dict:
        return self._registered_reflection.current(mission_id, reflector_id).next_job(
            mission_id=mission_id, reflector_id=reflector_id, wait_seconds=wait_seconds)

    def reflection_proposal(self, *, mission_id: str, proposal_id: str) -> dict:
        return self._registered_reflection.current(mission_id).proposal(mission_id=mission_id, proposal_id=proposal_id)

    def reflection_source(self, **selection) -> tuple[dict, bytes]:
        return self._registered_reflection.source(**selection)

    def command(self, request: dict | str | bytes) -> dict:
        try:
            data = validate_submission(request)
        except (ContractError, ValueError, TypeError) as exc:
            return self._response("rejected", reason=str(exc)[:1024])
        kind = data["kind"]
        with self._metadata:
            if self._closed.is_set():
                rejection = "Mission runtime is closed"
            elif kind != "start" and (self._snapshot is None or data["mission_id"] != self._snapshot["mission_id"]):
                rejection = "No matching admitted mission"
            else:
                rejection = None
            cached = copy.deepcopy(self._operations.get(data.get("request_id", data.get("operation_id"))))
            if kind == "start" and self._snapshot is not None and data["admission"]["mission_id"] != self._snapshot["mission_id"]:
                cached = None
        if rejection:
            return self._response("rejected", reason=rejection)
        if kind == "status":
            return self._response("accepted")
        if cached is not None and kind == "result":
            return self._response("accepted", operation=cached)
        if cached is not None:
            if cached["request"] != data:
                return self._response("rejected", reason="Request ID reused with different payload")
            return self._response("accepted", operation_id=data["request_id"], operation=cached)
        work = _Work(data)
        busy_stop = False
        input_owner = None
        with self._metadata:
            # Admission handles are bounded by the active writer and one queue slot.
            duplicate = next((h for h in self._handles if data.get("request_id") is not None
                              and h.request.get("request_id") == data["request_id"]), None)
            if duplicate is not None and duplicate.request != data:
                rejection = "Request ID reused with different payload"
            elif duplicate is not None:
                work = duplicate
            elif self._closed.is_set():
                rejection = "Mission runtime is closed"
            elif kind == "stop" and self._handles:
                rejection = "Pause requested; Stop not admitted while writer busy. Read settled state and submit a new Stop ID/current epoch"
                busy_stop = True
            elif (any(h.request["kind"] in ("handoff", "claim", "readmit") for h in self._handles)
                    or kind in ("handoff", "claim", "readmit") and self._handles):
                rejection = "Quiescent player transition requires its sole writer handle; retry only after settled work"
            elif (kind in ("skill", "lifecycle") and any(
                    h.request["kind"] in ("skill", "lifecycle") for h in self._handles)):
                rejection = "An unfinished input operation already owns the writer"
                input_owner = next(h.request["request_id"] for h in self._handles
                    if h.request["kind"] in ("skill", "lifecycle"))
            elif (self._prompt_phase is not None and kind in ("skill", "lifecycle") and
                    (kind != "skill" or data["phase_id"] != self._prompt_phase.root_id
                     or data["skill_kind"] not in ("menu", "edit", "inspect", "item", "activity", "direct"))):
                rejection = "An owned prompt requires its exact phase and supported control child"
            elif (self._exit_phase is not None and kind in ("skill", "lifecycle") and
                    (kind != "skill" or data["phase_id"] != self._exit_phase.root_id or data["skill_kind"] not in ("menu", "direct"))):
                rejection = "Owned exit requires its exact ordinary or menu control child"
            elif (kind == "skill" and data["skill_kind"] == "edit"
                    and data["goal"]["purpose"] in ("character_name", "world_name")
                    and (self._registered_lifecycle.phase is None
                         or self._registered_lifecycle.phase.operation != "create"
                         or self._registered_lifecycle.phase.root_id != data["phase_id"])):
                rejection = "Creation-name editing requires the registered lifecycle adapter"
            else:
                try:
                    self._queue.put_nowait(work)
                    self._handles.append(work)
                except Full:
                    rejection = "Mission writer queue is full"
        if rejection:
            if busy_stop:
                self.pause(data["reason"], cause="user")
            return self._response("rejected", reason=rejection,
                **({"input_owner_operation_id": input_owner} if input_owner is not None else {}))
        # A timed-out admission may persist a blocked row, but cannot send future input.
        if not work.ready.wait(5):
            with self._metadata:
                timed_out = not work.ready.is_set()
                if timed_out:
                    work.cancelled.set()
            if timed_out:
                return self._response("rejected", reason="Admission wait expired; work cancelled")
        response = copy.deepcopy(work.response)
        if response is None:
            return self._response("rejected", reason="Admission cancelled")
        return self._response(**response)

    def pause(self, reason: str = "Operator Pause", cause: str = "user") -> dict:
        if cause not in ("user", "takeover", "unknown", "internal_recovery", "internal_lifecycle", "finishing"):
            raise ContractError("Unsupported runtime Pause cause")
        reason = str(reason)[:1024] or "Operator Pause"
        # Controller first; no runtime storage or metadata lock can delay revocation.
        try:
            result = self.controller.pause() if cause == "user" else self.controller.stop_input()
        except OSError as exc:
            result = {"status": "pause_requested", "error": f"Pause persistence unconfirmed: {exc}"[:1024]}
        with self._metadata:
            if not self._closed.is_set():
                self._pending_pauses.append((cause, reason))
            for handle in self._handles:
                handle.cancelled.set()
            self._bindings.clear()
            self._prompt_phase = None
            self._exit_phase = None
            self._registered_lifecycle.revoke()
            self._registered_handoff.revoke()
            self._registered_activity.revoke()
            self._registered_recovery.revoke()
            self._rotation = None
            if self._snapshot is not None and self._snapshot["phase"] not in TERMINAL:
                self._snapshot.update(phase="paused", pause_cause=cause, reason=reason, lease_owner=None,
                    prompt_phase=None, lifecycle_phase=None, activity_phase=None,
                    current_source=None, coordinate_scope=None,
                    epoch=self._snapshot["epoch"] + 1, next_needed_decision="Explicit supported readmission required")
        return result

    def _check_cancelled(self, work: _Work) -> None:
        if self._closed.is_set() or work.cancelled.is_set():
            raise _Cancelled("Operation cancelled by Pause, close or admission expiry")

    def _record(self, kind: str, result: dict) -> None:
        self.controller._record({"kind": kind, "mission_id": self._admission.mission_id}, result)

    def _cache_operation(self, operation: dict) -> None:
        with self._metadata:
            self._operations[operation["request"]["request_id"]] = copy.deepcopy(operation)

    def _publish(self) -> None:
        if self._ledger is None:
            return
        state = self._ledger.snapshot(now=self._wall())
        usage = self._store.usage()
        measured = self._ledger.measured_counts()
        limits, reserve = self._admission.limits, self._admission.cleanup_reserve
        active = self._active.request if self._active is not None else None
        with self._metadata:
            input_admitted = (active is not None and active["kind"] in ("skill", "lifecycle")
                and active["request_id"] in self._operations)
        # The collection cache is deliberately updated after this publication.
        # Its older state cannot describe the result already committed in SQLite.
        input_pending = (input_admitted
            and self._ledger.request(active["request_id"])["state"] in ("accepted", "running"))
        current_available = self._current is not None and not (
            self._prompt_phase is not None and self._prompt_phase.observation_generation is not None)
        inspected = None
        if current_available:
            try:
                launch = self._owned_launch
                owned_menu_checkpoint = (state["phase"] in ("admitted", "active") and launch is not None
                    and launch.checkpoint == self._current and launch.operator_mark == self._operator_mark()
                    and self._native is not None
                    and self._native_owner == (self._admission.mission_id, self._admission.configuration.native_sha256)
                    and self._native.status()["running"])
                handoff = self._registered_handoff.phase
                handoff_observation = handoff is not None and state["phase"] in ("handoff", "paused")
                if handoff_observation:
                    # Observe may publish a newer read-only sample while the
                    # issued post-Pause checkpoint stays fixed for readmission.
                    self._registered_handoff.check_binding(handoff, state, self._live(), ledger_phase=state["phase"])
                private_checkpoint = handoff_observation or owned_menu_checkpoint or any(phase is not None and phase.checkpoint == self._current for phase in
                    (self._registered_lifecycle.phase, self._registered_activity.phase,
                     self._registered_handoff.phase, self._exit_phase,
                     self._prompt_phase if self._prompt_phase is not None
                        and self._prompt_phase.checkpoint.boundary_kind == "activity_poll" else None))
                if not private_checkpoint:
                    # A retained as-of sample is not a current published source
                    # after stop/handoff/storage failure cleared its live binding.
                    self._informing({"sources": [self._current.observation_id]})
                inspected, _ = self._store.inspect_current_boundary(**self._clocks())
                observed, live = self._store.observation(self._current), self._live()[0]
                self._capture_custody(observed, live)
                current_available = inspected == self._current
            except (EvidenceError, ControlError, LedgerError):
                current_available = False
                inspected = None
        live = self._live()
        lease_owner = asdict(self._lease) if self._lease is not None and live[3] is self._lease and not live[4] else None
        coordinate_scope = None
        if (self._map is not None and inspected is not None and inspected == self._current
                and inspected.boundary_kind == "normal_play" and self._map.scope[1] == inspected.session):
            # Normal source publication already verified this adopted scope.
            # Do not repeat lifecycle/source checks during passive publication.
            mission_id, session, coordinate_epoch = self._map.scope
            coordinate_scope = dict(mission_id=mission_id, session=session, coordinate_epoch=coordinate_epoch)
        value = {**state, "lease_owner": lease_owner, "objective": self._admission.objective,
            "scenario": asdict(self._admission.scenario), "actor_id": state["player_id"],
            "coordinate_scope": coordinate_scope,
            "prompt_phase": None if self._prompt_phase is None else {
                "origin_request_id": self._prompt_phase.root_id,
                "checkpoint_id": self._prompt_phase.checkpoint.observation_id,
                "observation_needed": self._prompt_phase.observation_generation is not None, "grants_authority": False},
            "lifecycle_phase": self._registered_lifecycle.summary() if self._exit_phase is None else {
                "origin_request_id": self._exit_phase.root_id, "operation": "exit",
                "direct_interrupt_allowed": False,
                "checkpoint_id": self._exit_phase.checkpoint.observation_id, "grants_authority": False},
            "activity_phase": self._registered_activity.summary(),
            "reflection": self._registered_reflection.summary(),
            "active_operation": None if active is None else active.get("request_id", active["kind"]),
            "skill": self._skill, "progress": copy.deepcopy(self._progress),
            "last_receipt": copy.deepcopy(self._last_receipt),
            "current_source": self._current.to_dict() if current_available else None,
            "remaining_limits": {"inputs": state["remaining_inputs"],
                "wall_seconds": state["remaining_wall_seconds"],
                "game_seconds": None if self._game_cost is None else max(0, limits.game_seconds - self._game_cost),
                "frames": limits.frames - usage["frames"], "frame_bytes": limits.frame_bytes - usage["bytes"],
                "primitive_mappings": limits.primitive_mappings - state["spent_inputs"]},
            "cleanup_reserve": asdict(reserve), "unresolved_effects": [p["logical_id"]
                for p in self._ledger.primitive_records() if p["state"] in ("prepared", "published")
                or p["state"] == "unknown" and p["effect"] is None],
            "memory_version": self._memory_version, "last_context_id": self._last_context_id,
            "memory_context": copy.deepcopy(self._last_memory_context),
            "native_process": {"owner_mission_id": None if self._native_owner is None else self._native_owner[0],
                "last_sample": copy.deepcopy(self._native_facts),
                "unresolved_custody_requests": list(self._lost_process_custody), "restored_from_disk": False},
            "next_needed_decision": "Collect the original unfinished input operation before choosing new input" if input_pending else
                "Explicit Observe needed before input" if state["phase"] == "active"
                and self._prompt_phase is not None and self._prompt_phase.observation_generation is not None else
                "Player semantic decision" if state["phase"] == "active" else
                "Mission ended; historical evidence only" if state["phase"] in TERMINAL else
                "Registered lifecycle/readmission needed" if state["phase"] == "admitted" else
                "Explicit supported transition required", "grants_authority": False,
            "configuration": {**asdict(self._admission.configuration),
                "procedure_environment": (None if self._admission.learning is None else
                                          dict(self._admission.learning.environment))},
            "metrics": {**measured, "model_requests": None, "tool_calls": None, "interventions": None,
                "harness_api_spend": 0, "external_tokens": None, "api_quota": None,
                "model_time_seconds": None, "game_seconds": self._game_cost, "archive": usage},
            "diagnostic": self._diagnostic}
        with self._metadata:
            if self._pending_pauses and self._snapshot is not None:
                for key in ("phase", "epoch", "pause_cause", "reason", "next_needed_decision",
                            "lease_owner", "prompt_phase", "lifecycle_phase", "activity_phase",
                            "current_source", "coordinate_scope"):
                    value[key] = self._snapshot[key]
            self._snapshot = value
            self._presentation_store = (self._admission.mission_id, self._store, self._memory)

    def _apply_pauses(self) -> bool:
        with self._metadata:
            events, self._pending_pauses = self._pending_pauses, []
        if events:
            self._bindings.clear()
            self._rotation = None
            self._lease = None
            self._registered_handoff.revoke()
            self._registered_activity.revoke()
            self._registered_recovery.revoke()
        if self._ledger is not None:
            for cause, reason in events:
                self._ledger.pause(cause=cause, reason=reason, now=self._wall())
        return bool(events)

    def _live(self) -> tuple:
        with self.controller.data_lock:
            return (copy.deepcopy(self.controller.state), self.controller.pause_generation,
                self.controller.authority["controller_boot_id"], self.controller._mission_lease,
                self.controller.pause_requested or self.controller.frozen or self.controller.closed,
                self.controller.pending is not None or self.controller.control_pending is not None)

    def _check_lease(self) -> tuple:
        state, generation, boot, lease, paused, pending = self._live()
        if (self._lease is None or lease is not self._lease or paused or pending or state is None
                or lease.pause_generation != generation or lease.session != state["session"]
                or lease.takeover_generation != state["takeover_generation"]):
            raise ControlError("Mission lease lost or native Pause/takeover/session changed")
        return state, generation, boot

    def _operator_mark(self) -> tuple[str, int]:
        with self.controller.data_lock:
            return self.controller.authority["controller_boot_id"], self.controller.operator_pause_generation

    def _last_normal(self) -> EvidenceRef:
        refs = [ref for ref in self._store.historical_references if ref.boundary_kind == "normal_play"]
        if not refs:
            raise BudgetError("An observed normal game-time anchor is required")
        self._store.verify(refs[-1])
        self._require_normal_adoption(refs[-1])
        return refs[-1]

    def _require_normal_adoption(self, reference: EvidenceRef) -> None:
        """Validate every normal segment; one reference cannot select a subset."""
        from .gameplay.lifecycle import adopted_timeline
        self._store.observation(reference)
        timeline = adopted_timeline(self._ledger, self._store)
        if timeline is None or not any(first.session == reference.session for first, _ in timeline.segments):
            raise EvidenceError("Registered normal-session identity/adoption proof is required")
        self._timeline_links = tuple(SessionContinuity(before[1], after[0])
            for before, after in zip(timeline.segments, timeline.segments[1:]))

    def _coordinate_scope(self, reference: EvidenceRef) -> dict:
        self._require_normal_adoption(reference)
        timeline = game_timeline(self._store, self._timeline_links)
        epoch = next(index for index, pair in enumerate(timeline.segments) if pair[0].session == reference.session)
        return {"mission_id": self._admission.mission_id, "session": reference.session, "coordinate_epoch": epoch}

    def _resume_intent(self, request_id: str, source: EvidenceRef) -> _ResumeIntent:
        return _ResumeIntent("resume-" + hashlib.sha256(request_id.encode()).hexdigest(), source,
            self._store.observation(source)["boundary"]["id"])

    def _game_guard(self, anchor: EvidenceRef, limit: int, *, after=False) -> None:
        latest = self._last_normal()
        self._store.verify(anchor)
        if latest.session != anchor.session or latest.turn < anchor.turn:
            raise BudgetError("Game-time anchor cannot cross an unexplained session or regression")
        elapsed = latest.turn - anchor.turn
        if elapsed > limit or not after and elapsed == limit:
            raise _LocalGameLimit("Original observed root/child game-time budget exhausted")

    @staticmethod
    def _item_control_reason(data: dict, root: dict, category: str, quantity_editor: bool) -> str | None:
        if root["skill_kind"] == "item":
            if data["skill_kind"] == "edit" and (not quantity_editor
                    or data["goal"]["purpose"] != "quantity"
                    or data["goal"]["text"] != str(root["goal"]["quantity"])):
                return "Quantity editor requires its returned MARK_WITH_COUNT and exact immutable count"
            if (data["skill_kind"] == "menu" and data["goal"]["outcome"] == "activated"
                    and category in ("INVENTORY", "INVENTORY_SELECTOR", "STRING_INPUT")):
                return ("Item selector menu confirmation requires its typed quantity/selection step; "
                        "ordinary direct input remains available")
        return None

    def _prompt_authority_guard(self, data: dict, before: EvidenceRef | None = None) -> _PromptPhase | None:
        if data["skill_kind"] == "edit" and data["goal"]["purpose"] in ("character_name", "world_name"):
            raise ControlError("Creation-name editing requires the registered lifecycle adapter")
        with self._metadata:
            phase = self._prompt_phase
        if phase is None:
            if self._registered_recovery.continuation_guard(data, before):
                return None
            if data["phase_id"] is not None or data["skill_kind"] in ("menu", "edit"):
                raise ControlError("Control requires its actual live owned prompt phase")
            return None
        if phase.observation_generation is not None:
            raise ControlError("Fresh explicit Observe is required before another input")
        if data["phase_id"] != phase.root_id or data["skill_kind"] not in ("menu", "edit", "inspect", "item", "activity", "direct"):
            raise ControlError("An owned prompt permits only its explicit control children")
        root = self._ledger.request(phase.root_id)["request"]
        if (data["skill_kind"] == "item" and root["skill_kind"] != "item"
                or data["skill_kind"] == "activity" and root["skill_kind"] not in ("activity", "direct", "program")):
            raise ControlError("Semantic control cannot borrow another root kind")
        if data["skill_kind"] == "activity":
            if ((root["skill_kind"] in ("direct", "program")) != (data["goal"]["operation"] == "direct")):
                raise ControlError("Activity child must preserve its original semantic or ordinary operation")
            if data["goal"]["interrupt_allowed"] and not root["goal"].get("interrupt_allowed", False):
                raise ControlError("Activity child cannot enlarge its root interruption consent")
        if (data["skill_kind"] == "direct" and data["goal"]["interrupt_allowed"]
                and not root["goal"].get("interrupt_allowed", False)):
            raise ControlError("Direct child cannot enlarge its root interruption consent")
        state, _, boot = self._check_lease()
        actor = self._ledger.snapshot(now=self._wall())["player_id"]
        if ((boot, self._operator_mark()[1], state["takeover_generation"], data["epoch"], actor) !=
                (phase.controller_boot_id, phase.operator_generation, phase.takeover_generation, phase.epoch, phase.actor_id)):
            raise ControlError("Prompt crossed actor/epoch/controller/operator Pause/native takeover")
        if before is not None and phase.checkpoint != before:
            raise EvidenceError("Prompt checkpoint cannot rebase from an unrelated observation")
        return phase

    def _prompt_guard(self, data: dict, before: EvidenceRef | None = None) -> _PromptPhase | None:
        phase = self._prompt_authority_guard(data, before)
        if phase is not None:
            root = self._ledger.request(phase.root_id)["request"]
            reason = self._item_control_reason(data, root,
                self._store.observation(phase.checkpoint)["category"], phase.quantity_editor)
            if reason is not None:
                raise ControlError(reason)
        return phase

    def _clear_prompt(self) -> None:
        with self._metadata:
            self._prompt_phase = None

    def _prompt_receipt(self, phase: _PromptPhase, stage: str) -> dict:
        root = self._ledger.request(phase.root_id)["request"]
        kind = root["skill_kind"]
        return {"schema": VERSION, "record_type": "PhaseReceipt", "origin_request_id": phase.root_id,
            "phase_kind": kind, "operation": kind if kind in ("direct", "program", "navigate") else root["goal"][
                "action" if kind == "interact" else "operation" if kind == "activity" else "purpose"], "stage": stage,
            "epoch": phase.epoch, "actor_id": phase.actor_id, "controller_boot_id": phase.controller_boot_id,
            "operator_pause_generation": phase.operator_generation, "takeover_generation": phase.takeover_generation,
            "source_ids": list(dict.fromkeys((phase.game_anchor.observation_id, phase.checkpoint.observation_id))),
            "continuity": None, "grants_authority": False}

    def _advance_prompt(self, work: _Work, before: EvidenceRef, after: EvidenceRef,
                        *, action: str | dict | None = None, observed_only: bool = False) -> _PromptPhase | None:
        phase = self._prompt_guard(work.request, before)
        if phase is None:
            return None
        quantity_editor = False if observed_only or work.request["skill_kind"] == "direct" else phase.quantity_editor
        if not observed_only and self._ledger.request(phase.root_id)["request"].get("skill_kind") == "item":
            entering_editor = (self._store.observation(before)["category"] != "STRING_INPUT"
                               and self._store.observation(after)["category"] == "STRING_INPUT")
            if entering_editor:
                if work.request["skill_kind"] == "direct":
                    # Ordinary exploration supplies no typed-count attestation.
                    quantity_editor = False
                elif (work.request["skill_kind"] != "item" or work.request["goal"]["step"] != "select"
                        or action != "MARK_WITH_COUNT"):
                    raise ControlError("Item quantity editor lacks its exact returned count-opening input")
                else:
                    quantity_editor = True
            elif self._store.observation(after)["category"] != "STRING_INPUT":
                quantity_editor = False
        advanced = replace(phase, checkpoint=after, quantity_editor=quantity_editor)
        with self._metadata:
            self._check_cancelled(work)
            if self._prompt_phase is not phase:
                raise ControlError("Prompt revoked during checkpoint advancement")
            self._prompt_phase = None if after.boundary_kind == "normal_play" else advanced
        return advanced

    def _open_prompt(self, work: _Work, original: EvidenceRef, after: EvidenceRef,
                     mark: tuple[str, int], *, observation_generation: int | None = None) -> _PromptPhase:
        state, _, boot = self._check_lease()
        ledger = self._ledger.snapshot(now=self._wall())
        if (mark != self._operator_mark() or boot != mark[0] or ledger["epoch"] != work.request["epoch"]
                or state["takeover_generation"] != self._store.observation(original)["takeover_generation"]
                or (original.boundary_kind != "normal_play" and not
                    (work.request["skill_kind"] in ("direct", "program") and original.boundary_kind == "menu"))
                or after.session != original.session):
            raise ControlError("Interaction cannot open a prompt across changed authority/session")
        phase = _PromptPhase(work.request.get("phase_id") or work.request["request_id"], after,
            work.game_anchor or original, ledger["player_id"],
            ledger["epoch"], boot, mark[1], state["takeover_generation"],
            observation_generation=observation_generation)
        with self._metadata:
            self._check_cancelled(work)
            if self._prompt_phase is not None:
                raise ControlError("A second prompt cannot replace its owner")
            if observation_generation is not None or after.boundary_kind in ("menu", "activity_poll"):
                self._prompt_phase = phase
        return phase

    def _await_current_observation(self, work: _Work, before: EvidenceRef, original: EvidenceRef,
                                   mark: tuple[str, int], reason: str) -> None:
        """Keep only the existing scope's read-only lineage across this rotation."""
        _, generation, _ = self._check_lease()
        binding = self._bindings[before.observation_id][1]
        if binding.pause_generation != generation:
            rotation = self._rotation
            if (rotation is None or rotation[:3] != (work.request["request_id"],
                    before.observation_id, binding.pause_generation)
                    or rotation[3].pause_generation != binding.pause_generation
                    or rotation[4] is not self._lease or generation != binding.pause_generation + 1):
                raise EvidenceError("Read-only observation lacks its exact authenticated operation rotation")
        phase = self._prompt_phase
        if phase is None:
            phase = self._open_prompt(work, original, before, mark,
                                      observation_generation=generation)
        else:
            if phase.checkpoint != before:
                raise EvidenceError("Read-only observation cannot replace an unrelated prompt checkpoint")
            phase = replace(phase, observation_generation=generation, quantity_editor=False)
            with self._metadata:
                self._check_cancelled(work)
                self._prompt_phase = phase
        self._update_game_time()
        self._prompt_observation_guard(work, phase)
        self._record("mission_awaiting_observation", {"root_id": phase.root_id,
            "checkpoint_source_id": phase.checkpoint.observation_id, "reason": reason,
            "pause_generation": generation, "grants_authority": False})

    def _stop_unknown_policy(self) -> None:
        # The immutable primitive may already be returned. Semantic uncertainty
        # still revokes input; complete_request owns the ledger epoch transition.
        try:
            self.controller.stop_input()
        except OSError as exc:
            self._diagnostic = f"Unknown policy Pause persistence failed: {exc}"[:1024]
        self._bindings.clear()
        self._lease, self._rotation = None, None
        self._clear_prompt()
        self._exit_phase = None
        self._registered_lifecycle.revoke()
        self._registered_handoff.revoke()
        self._registered_activity.revoke()
        self._registered_recovery.revoke()

    def _capacity(self, *, frames: int = 1, byte_count: int = MAX_FRAME_BYTES) -> None:
        usage = self._store.usage()
        limits, reserve = self._admission.limits, self._admission.cleanup_reserve
        if (usage["frames"] + frames > limits.frames - reserve.frames
                or usage["bytes"] + byte_count > limits.frame_bytes - reserve.frame_bytes):
            raise CapacityError("Ordinary evidence would consume cleanup/required after-frame reserve")

    def _update_game_time(self) -> None:
        try:
            first = next((ref for ref in self._store.historical_references if ref.boundary_kind == "normal_play"), None)
            if first is not None:
                self._require_normal_adoption(first)
            timeline = game_timeline(self._store, self._timeline_links)
        except EvidenceError:
            self._game_cost = None
            self._map = None
            self._bindings.clear()
            raise
        self._game_cost = None if timeline is None else timeline.elapsed_seconds

    def _binding(self, reference: EvidenceRef) -> SourceBinding:
        state, generation, boot = self._check_lease()
        ledger = self._ledger.snapshot(now=self._wall())
        observed = self._store.observation(reference)
        self._capture_custody(observed, state)
        return SourceBinding(reference.observation_id, self._admission.mission_id, ledger["epoch"],
            ledger["player_id"], boot, generation, state["takeover_generation"], self._store.authority_generation())

    def _capture_custody(self, observed: dict, state: dict | None) -> None:
        """A captured sample survives healthy visible change, never custody loss."""
        if state is None:
            raise EvidenceError("Current native custody is unavailable")
        for value in (observed, state):
            validate_state(value)
            if value["status"] != "ready" or value["error"] or not value["frame_ok"]:
                raise EvidenceError("Captured or current native observation is unhealthy")
        if not same_native_custody(observed, state):
            raise EvidenceError("Captured source crossed native custody or immutable capture identity")
        validate_native_progression(observed, state, now_timestamp_ms=int(self._wall() * 1000))

    def _publish_source(self, reference: EvidenceRef, *, authoritative: bool) -> SourceBinding | None:
        self._current = reference
        self._update_game_time()
        if reference.boundary_kind == "normal_play":
            scope = self._coordinate_scope(reference)
            if self._map is None:
                self._map = ObservedMap(**scope)
            if self._map.scope != (scope["mission_id"], scope["session"], scope["coordinate_epoch"]):
                self._map = None
                self._bindings.clear()
                raise EvidenceError("New session cannot adopt old coordinate scope")
            self._map.add(reference, self._store)
        binding = self._binding(reference) if authoritative and reference.boundary_kind in ("normal_play", "menu") else None
        self._record("mission_source", {"source": reference.to_dict(),
            "binding": None if binding is None else binding.to_dict(), "grants_authority": False})
        if binding is not None:
            with self._metadata:
                if self._closed.is_set() or self._pending_pauses or self._active is not None and self._active.cancelled.is_set():
                    raise _Cancelled("Source publication superseded by Pause/close")
                self._bindings[reference.observation_id] = (reference, binding)
                while len(self._bindings) > self._store.max_frames:
                    del self._bindings[next(iter(self._bindings))]
        return binding

    def _observe_native(self, work: _Work, *, timeout: float | None = None,
                        deadline_monotonic: float | None = None) -> tuple[dict, float]:
        self._check_cancelled(work)
        self._registered_recovery.before_observe(work, deadline_monotonic=deadline_monotonic)
        self._check_cancelled(work)
        result, received = self.controller.observe_mission(deadline_monotonic=deadline_monotonic, timeout=timeout)
        self._check_cancelled(work)
        state, _ = self.controller.observation_snapshot()
        if result.get("status") != "ready" or received is None:
            raise ControlError("Fresh captured Observe unavailable; registered lifecycle may be needed")
        self._capture_custody(result, state)
        if not math.isfinite(received) or received > self._clock():
            raise EvidenceError("Observe lacks a finite original receipt")
        return result, received

    def _ingest(self, state: dict, received: float, *, reservation=None) -> EvidenceRef:
        reference = self._store.ingest(state, received_monotonic=received, reservation=reservation, **self._clocks())
        self._current = reference
        return reference

    def _start(self, data: dict) -> bool:
        admission = MissionAdmission.from_dict(data["admission"])
        if self._ledger is not None:
            if self._native is not None and self._native.status()["launch_id"] is not None:
                raise LedgerError("Registered normal finish must settle owned process custody before mission replacement")
            if self._lost_process_custody:
                raise LedgerError("Unresolved process custody prevents mission replacement")
            old = self._ledger.snapshot(now=self._wall())
            if old["phase"] not in TERMINAL:
                raise LedgerError("A live mission cannot be replaced")
            if self._lease is not None:
                raise LedgerError("Previous mission ownership must be closed before switching")
            self._close_storage()
        directory = self.controller.root / ".runtime" / "missions" / admission.mission_id
        for path in (self.controller.root / ".runtime", directory.parent, directory, directory / "evidence"):
            if path.is_symlink():
                raise LedgerError("Mission storage cannot follow a symlink")
        ledger = MissionLedger(directory, now=self._wall(), admission=admission)
        try:
            store = EvidenceStore(self.controller.bridge, directory / "evidence",
                max_frames=admission.limits.frames, max_bytes=admission.limits.frame_bytes)
        except Exception:
            ledger.close()
            raise
        self._ledger, self._store, self._admission = ledger, store, admission
        # Validated immutable exit results resolve history, never restore a handle.
        closed_launches = {row["result"]["normal_exit"]["launch_request_id"] for row in ledger.request_records()
            if row["state"] == "completed" and row["result"] is not None and "normal_exit" in row["result"]}
        self._lost_process_custody = tuple(row["request"]["request_id"] for row in ledger.request_records()
            if row["request"]["kind"] == "lifecycle" and row["request"]["operation"] == "launch"
            and row["request"]["request_id"] not in closed_launches
            and (row["result"] is None or row["state"] in ("accepted", "running", "unknown")
                 or row["result"].get("launch_attempted", False)))
        with self._metadata:
            self._operations.clear()
        self._diagnostic, self._progress, self._last_receipt = None, None, None
        library = None
        try:
            if admission.learning is not None:
                from .gameplay.procedure_library import ProcedureLibrary
                library = ProcedureLibrary(self.controller.root,
                    [asdict(source) for source in admission.learning.library_sources], current_mission_id=admission.mission_id)
            self._memory = CampaignMemory(ledger, store, library)
        except Exception:
            if library is not None:
                library.close()
            raise
        self._bindings, self._map, self._lease, self._current, self._rotation = {}, None, None, None, None
        self._clear_prompt()
        self._owned_launch, self._exit_phase, self._exit_candidate = None, None, None
        self._registered_lifecycle.reset()
        self._game_cost = None
        self._timeline_links = ()
        historical = [r for r in store.historical_references if r.boundary_kind == "normal_play"]
        if historical:
            try:
                self._update_game_time()
            except EvidenceError as exc:
                self._diagnostic = f"Historic game time unprovable: {exc}"[:1024]
                self._game_cost = None
        self._memory_version = max((r["sequence"] for k in ("claim", "work", "decision", "procedure")
                                   for r in ledger.memory_records(k)), default=0)
        self._last_context_id = None
        self._last_memory_context = None
        self._issued_packets = {}
        self._registered_handoff.revoke()
        self._registered_activity.revoke()
        self._registered_recovery.reset()
        self._mission_deadline = ledger.snapshot(now=self._wall())["deadline"]
        self._registered_reflection.reset()
        return ledger.snapshot(now=self._wall())["phase"] == "admitted"

    def _bootstrap(self, work: _Work) -> dict:
        # Source-free admission cannot adopt an existing game. Publishing Observe
        # before owned launch would strand an expired pending slot when no game
        # exists, preventing the launch this admission is supposed to enable.
        self._check_cancelled(work)
        return {"admitted": True, "lifecycle_needed": True, "source_ids": [],
            "reason": "Source-free admission; registered owned launch/identity required", "grants_authority": False}

    def _capture_memory(self, reference: EvidenceRef) -> None:
        if reference.boundary_kind == "normal_play":
            receipt = self._memory.capture_native(reference, self._coordinate_scope(reference), now=self._wall())
            self._record("mission_native_memory", receipt)
            self._memory_version = receipt["memory_version"]

    def _prompt_observation_guard(self, work: _Work, phase: _PromptPhase,
                                  reference: EvidenceRef | None = None) -> float:
        """Observe may change visible facts, never the original prompt's authority.

        Historical integrity and ownership survive source age or visual drift.
        The new capture advances the store once; it does not renew any limit.
        """
        self._check_cancelled(work)
        ledger = self._ledger.snapshot(now=self._wall())
        state, generation, boot = self._check_lease()
        prior = self._bindings.get(phase.checkpoint.observation_id)
        if (self._prompt_phase is not phase or not ledger["clock_valid"]
                or (ledger["phase"], ledger["epoch"], ledger["player_id"], work.request["epoch"]) !=
                   ("active", phase.epoch, phase.actor_id, phase.epoch)
                or self._operator_mark() != (phase.controller_boot_id, phase.operator_generation)
                or boot != phase.controller_boot_id
                or (self._lease.mission_id, self._lease.epoch, self._lease.actor_id) !=
                   (self._admission.mission_id, phase.epoch, phase.actor_id)):
            raise ControlError("Observe crossed its original prompt actor/epoch/controller/Pause")
        if prior is None or prior[0] != phase.checkpoint or self._current != (reference or phase.checkpoint):
            raise EvidenceError("Observe requires its original current prompt checkpoint/binding")
        binding = prior[1]
        pending = phase.observation_generation is not None
        if ((binding.source_id, binding.mission_id, binding.epoch, binding.actor_id,
             binding.controller_boot_id, binding.takeover_generation) !=
                (phase.checkpoint.observation_id, self._admission.mission_id, phase.epoch, phase.actor_id,
                 phase.controller_boot_id, phase.takeover_generation)):
            raise EvidenceError("Observe prompt authority lost: binding_identity")
        if (phase.observation_generation != generation or binding.pause_generation not in (generation, generation - 1)
                if pending else binding.pause_generation != generation):
            raise EvidenceError("Observe prompt authority lost: pause_generation")
        if self._store.authority_generation() != binding.store_generation + (reference is not None):
            raise EvidenceError("Observe prompt authority lost: store_generation")
        if self._store.source_status(phase.checkpoint) != "retained":
            raise EvidenceError("Observe prompt authority lost: source_retention")
        before = self._store.observation(phase.checkpoint)
        if (phase.checkpoint.boundary_kind not in (("normal_play", "menu") if pending else ("menu",))
                or state["session"] != phase.checkpoint.session
                or state["status"] != "ready" or state["error"] or state["paused"] or not state["frame_ok"]
                or state["boundary"]["kind"] not in ("menu", "normal_play")
                or state["takeover_generation"] != phase.takeover_generation
                or state["boundary"]["control_generation"] != before["boundary"]["control_generation"]
                or state["pause_origin"] != before["pause_origin"] or state["pause_origin"] in ("human", "fault")):
            raise ControlError("Observe changed prompt session/native control/Pause or capture health")
        primitive_states = self._ledger.measured_counts()["primitives"]["by_state"]
        if ledger["unreconciled"] or any(primitive_states.get(state, 0) for state in ("prepared", "published")):
            raise LedgerError("Unsettled input cannot advance a prompt observation")
        # A refused child performs no capture/input and may already be locally
        # expired. Only actual Observe pays its own finite capture deadline.
        deadline_wall = self._mission_deadline - self._admission.cleanup_reserve.wall_seconds
        if work.request["kind"] == "observe":
            deadline_wall = min(deadline_wall, self._ledger.request(work.request["request_id"])["deadline"])
        if self._wall() >= deadline_wall:
            raise BudgetError("Original Observe/mission deadline exhausted")
        if ledger["spent_inputs"] >= min(self._admission.limits.inputs - self._admission.cleanup_reserve.inputs,
                                        self._admission.limits.primitive_mappings):
            raise BudgetError("Mission input capacity exhausted")
        if self._game_cost is None or self._game_cost >= self._admission.limits.game_seconds:
            raise BudgetError("Observed mission game budget exhausted")
        return self._clock() + deadline_wall - self._wall()

    def _ordinary_macro_limit(self, phase: _PromptPhase) -> str | None:
        """Local execution exhaustion, never a global fault or goal verdict."""
        root = self._ledger.request(phase.root_id)
        if self._wall() >= root["deadline"]:
            return "wall_seconds"
        if self._ledger._phase_primitive_count(phase.root_id) >= root["request"]["limits"]["primitives"]:
            return "primitives"
        latest = self._last_normal()
        if latest.session != phase.game_anchor.session or latest.turn < phase.game_anchor.turn:
            raise BudgetError("Macro clock crossed an unexplained session or regression")
        if latest.turn - phase.game_anchor.turn >= root["request"]["limits"]["game_seconds"]:
            return "game_seconds"
        return None

    def _exhausted_prompt_refusal(self, work: _Work) -> dict | None:
        """Refuse spent local scope before rotation or controller preflight.

        Only explicit Observe may close this scope. Its original root and all
        costs remain immutable; a new player decision still needs a new root.
        """
        phase = self._prompt_phase
        if (phase is None or work.request["phase_id"] != phase.root_id
                or self._exit_phase is not None or self._registered_lifecycle.phase is not None
                or self._registered_activity.phase is not None or self._registered_recovery.phase is not None
                or self._registered_recovery.continuation is not None):
            return None
        limit = self._ordinary_macro_limit(phase)
        if limit is None:
            return None
        self._prompt_authority_guard(work.request)
        self._prompt_observation_guard(work, phase)
        self.controller.check_mission_refusal(self._lease, self._lease.pause_generation, command_work=0)
        self._store.verify(phase.checkpoint)
        self._store.verify(phase.game_anchor)
        self._capacity(frames=0, byte_count=0)
        return {"reason": "Original local macro allowance exhausted; explicitly Observe before choosing a new root",
            "macro_exhausted": limit, "source_ids": [phase.checkpoint.observation_id],
            "phase": self._prompt_receipt(phase, "awaiting_control"), "grants_authority": False}

    def _observe_prompt(self, work: _Work, phase: _PromptPhase) -> dict:
        deadline = self._prompt_observation_guard(work, phase)
        self._capacity()
        state, received = self._observe_native(work, deadline_monotonic=deadline)
        self._prompt_observation_guard(work, phase)
        reference = self._ingest(state, received)
        self._prompt_observation_guard(work, phase, reference)
        self._capacity(frames=0, byte_count=0)
        relation = None
        if (phase.observation_generation is None and reference.boundary_kind == "menu"
                and self._store.equivalent(phase.checkpoint, reference, rule="exact_png_bytes")):
            relation = SourceRevalidation(self._bindings[phase.checkpoint.observation_id][1],
                                          self._binding(reference), "exact_png_bytes")
            self._record("mission_prompt_revalidation", relation.to_dict())
        transition = {"root_id": phase.root_id, "before": phase.checkpoint.observation_id,
                      "after": reference.observation_id, "grants_authority": False}
        self._publish_source(reference, authoritative=True)
        self._prompt_observation_guard(work, phase, reference)
        local_limit = self._ordinary_macro_limit(phase)
        if local_limit is not None:
            result = {"source_ids": list(dict.fromkeys((phase.checkpoint.observation_id, reference.observation_id))),
                "lifecycle_needed": False, "observation": transition, "grants_authority": False,
                "macro_closure": {"root_request_id": phase.root_id,
                    "checkpoint_source_id": phase.checkpoint.observation_id, "fresh_source_id": reference.observation_id,
                    "detected_at": self._wall(), "limit": local_limit, "grants_authority": False}}
            self._capture_memory(reference)
            # Reuse SQLite's immutable operation result, before clearing the
            # private scope. No new table/history or old-result rewrite.
            self._ledger.complete_request(work.request["request_id"], "completed", result, now=self._wall())
            with self._metadata:
                if self._prompt_phase is phase:
                    self._prompt_phase = None
            return result
        advanced = replace(phase, checkpoint=reference, quantity_editor=phase.quantity_editor if relation else False,
                           observation_generation=None)
        with self._metadata:
            self._check_cancelled(work)
            if self._prompt_phase is not phase:
                raise ControlError("Observe prompt advancement superseded by Pause")
            self._prompt_phase = None if reference.boundary_kind == "normal_play" else advanced
        self._record("mission_prompt_observation", transition)
        result = {"source_ids": [reference.observation_id], "lifecycle_needed": False,
                  "observation": transition, "grants_authority": False}
        if relation is not None:
            result["revalidation"] = relation.to_dict()
        if reference.boundary_kind == "normal_play":
            result["phase"] = self._prompt_receipt(advanced, "complete")
            root = self._ledger.request(phase.root_id)["request"]
            try:
                self._game_guard(phase.game_anchor, root["limits"]["game_seconds"], after=True)
                if self._game_cost is None or self._game_cost >= self._admission.limits.game_seconds:
                    raise BudgetError("Observed mission game time unavailable or exceeded")
            except BudgetError as exc:
                self._stop_after_failure(str(exc))
                result["budget_stop"] = str(exc)
        self._capture_memory(reference)
        return result

    def _observe(self, work: _Work) -> dict:
        if self._registered_activity.phase is not None:
            return self._registered_activity.observe(work)
        if self._registered_lifecycle.phase is not None or self._registered_lifecycle.candidate is not None:
            return self._registered_lifecycle.observe(work)
        if self._exit_phase is not None:
            phase = self._refresh_exit(work, self._exit_phase, ordinary=True)
            return {"source_ids": [phase.checkpoint.observation_id], "phase": self._exit_receipt(phase, "awaiting_control"),
                "lifecycle_needed": True, "grants_authority": False}
        phase = self._prompt_phase
        if phase is not None and phase.checkpoint.boundary_kind == "activity_poll":
            return self._poll_activity(work)[1]
        if phase is not None:
            return self._observe_prompt(work, phase)
        self._capacity()
        state, received = self._observe_native(work)
        normals = [r for r in self._store.historical_references if r.boundary_kind == "normal_play"]
        if state["boundary"]["kind"] == "normal_play" and (not normals or normals[-1].session != state["session"]):
            return {"source_ids": [], "lifecycle_needed": True,
                "reason": "Unowned normal session requires registered lifecycle adoption", "grants_authority": False}
        reference = self._ingest(state, received)
        owned = self._owned_launch
        if (owned is not None and self._native is not None and owned.operator_mark == self._operator_mark()
                and self._native.status()["running"] and state["category"] == "MAIN_MENU" and state["paused"]
                and (self._store.equivalent(owned.checkpoint, reference, rule="exact_png_bytes")
                     or self._resume_only_menu(owned, reference))):
            self._owned_launch = replace(owned, checkpoint=reference)
            self._record("mission_owned_menu_checkpoint", {"before": owned.checkpoint.observation_id,
                "after": reference.observation_id, "rule": "exact_png_bytes", "grants_authority": False})
        live = self._live()
        authoritative = self._lease is not None and live[3] is self._lease and not live[4] and not live[5]
        self._publish_source(reference, authoritative=authoritative)
        result = {"source_ids": [reference.observation_id], "lifecycle_needed": not authoritative,
                  "grants_authority": False}
        self._capture_memory(reference)
        return result

    def _poll_activity(self, work: _Work) -> tuple[str, dict]:
        """One bounded observation of an owned activity, never an input loop.

        Ordinary native activities can continue while the model is thinking.
        Same-session/takeover/control fences attribute fresh observations to the
        existing root; a poll neither resumes nor certifies its semantic effect.
        """
        data = work.request
        phase = self._prompt_phase
        if phase is None:
            raise ControlError("Activity poll requires its live root phase")
        root = self._ledger.request(phase.root_id)
        if phase.checkpoint.boundary_kind != "activity_poll":
            raise ControlError("Activity poll requires its actual owned activity boundary")
        if data["kind"] == "skill":
            if root["request"].get("skill_kind") not in ("activity", "direct", "program"):
                raise ControlError("Typed activity polling requires its original activity root; use Observe for other owned activities")
            self._prompt_guard(data, phase.checkpoint)
            observed = self._store.observation(phase.checkpoint)
            if (phase.checkpoint != self._current or phase.checkpoint.observation_id not in data["sources"]
                    or (data["expected_session"], data["expected_revision"], data["expected_boundary_id"]) !=
                       (phase.checkpoint.session, phase.checkpoint.revision, observed["boundary"]["id"])):
                raise EvidenceError("Activity poll lost its exact informing checkpoint")
        deadline_wall = min(self._ledger.request(data["request_id"])["deadline"],
                            self._mission_deadline - self._admission.cleanup_reserve.wall_seconds)
        # Plain Observe pays its own immutable capture allowance. The old root
        # still bounds all input and typed polling, even while native work runs.
        if data["kind"] != "observe":
            deadline_wall = min(deadline_wall, root["deadline"])
        deadline = self._clock() + deadline_wall - self._wall()
        def guard() -> None:
            self._check_cancelled(work)
            ledger = self._ledger.snapshot(now=self._wall())
            state, _, boot = self._check_lease()
            if (self._prompt_phase is not phase or ledger["phase"] != "active" or not ledger["clock_valid"]
                    or ledger["unreconciled"]
                    or (boot, self._operator_mark()[1], state["takeover_generation"], ledger["epoch"], ledger["player_id"]) !=
                       (phase.controller_boot_id, phase.operator_generation, phase.takeover_generation, phase.epoch, phase.actor_id)):
                raise ControlError("Activity poll crossed actor/epoch/controller/operator/native authority")
            with self._ledger._mutex:
                pending = self._ledger._db.execute(
                    "SELECT 1 FROM primitives WHERE state IN ('prepared','published') LIMIT 1").fetchone()
            if pending is not None:
                raise LedgerError("Unsettled input cannot advance an activity observation")
            if (self._wall() >= self._mission_deadline - self._admission.cleanup_reserve.wall_seconds
                    or ledger["remaining_inputs"] <= self._admission.cleanup_reserve.inputs
                    or ledger["spent_inputs"] >= self._admission.limits.primitive_mappings):
                raise BudgetError("Mission allowance or ending reserve exhausted")
            if self._game_cost is None or self._game_cost >= self._admission.limits.game_seconds:
                raise BudgetError("Observed mission game time unavailable or exceeded")
            if self._wall() >= deadline_wall or self._clock() >= deadline:
                raise BudgetError("Original activity/root observation deadline exhausted")
        guard()
        self._store.verify(phase.checkpoint)
        self._capacity()
        observed, received = self._observe_native(work, deadline_monotonic=deadline)
        guard()
        before = self._store.observation(phase.checkpoint)
        if (observed["session"] != before["session"] or observed["paused"]
                or observed["takeover_generation"] != phase.takeover_generation
                or observed["boundary"]["control_generation"] != before["boundary"]["control_generation"]
                or observed["boundary"]["kind"] not in ("activity_poll", "menu", "normal_play")):
            raise ControlError("Activity observation changed session/Pause/control or unsupported boundary")
        reference = self._ingest(observed, received)
        self._publish_source(reference, authoritative=reference.boundary_kind in ("menu", "normal_play"))
        # Check the newly measured global cost before classifying local overshoot.
        guard()
        self._capacity(frames=0, byte_count=0)
        advanced = replace(phase, checkpoint=reference)
        with self._metadata:
            self._check_cancelled(work)
            if self._prompt_phase is not phase:
                raise ControlError("Activity poll superseded by Pause")
            self._prompt_phase = None if reference.boundary_kind == "normal_play" else advanced
        stage = ("complete" if reference.boundary_kind == "normal_play" else "activity_poll"
                 if reference.boundary_kind == "activity_poll" else "awaiting_control")
        result = {"source_ids": [reference.observation_id], "phase": self._prompt_receipt(advanced, stage),
            "proposals": 0, "pending_logical_id": None, "verification_required": True,
            "basis": "registered_action", "grants_authority": False,
            "reason": "Owned activity observed; actual progress/output/rest requires player interpretation"}
        self._record("mission_activity_observation", {"root_id": phase.root_id,
            "before": phase.checkpoint.observation_id, "after": reference.observation_id, "grants_authority": False})
        try:
            self._game_guard(phase.game_anchor, root["request"]["limits"]["game_seconds"], after=True)
            if data["kind"] == "skill":
                self._game_guard(phase.game_anchor, data["limits"]["game_seconds"], after=True)
        except _LocalGameLimit as exc:
            # The observed effect is real and remains charged. Normal return
            # closes this root; a menu retains it for explicit Observe closure.
            # Neither observation nor exhaustion replays input or renews scope.
            result.update(macro_exhausted="game_seconds", reason=str(exc))
        except BudgetError as exc:
            result["budget_stop"] = str(exc)
            self._stop_after_failure(str(exc))
        if (data["kind"] == "observe" and "budget_stop" not in result
                and self._wall() >= root["deadline"]):
            result.update(macro_exhausted="wall_seconds", reason="Original local macro wall-time allowance exhausted")
        self._capture_memory(reference)
        return "partial", result

    def _context(self, work: _Work) -> dict:
        data = work.request
        self._check_cancelled(work)
        state = self._ledger.snapshot(now=self._wall())
        handoff = self._registered_handoff.context_binding(work)
        wrapper = {"objective": self._admission.objective, "mission_id": state["mission_id"],
            "handoff": handoff,
            "epoch": state["epoch"], "actor_id": state["player_id"], "phase": state["phase"],
            "pause_cause": state["pause_cause"], "reason": state["reason"],
            "remaining_limits": self.status()["remaining_limits"],
            "cleanup_reserve": asdict(self._admission.cleanup_reserve),
            "unresolved_effects": self.status()["unresolved_effects"],
            "configuration": asdict(self._admission.configuration),
            "unknowns": {"external_tokens": None, "model_time_seconds": None, "api_quota": None},
            "grants_authority": False, "packet": None}
        # Account for the actual finite wrapper, including replacement of JSON null.
        allowance = data["max_bytes"] - len(canonical(wrapper).encode()) + len("null")
        if allowance < 512:
            raise ContractError("Context allowance cannot hold wrapper and memory packet")
        options = {} if handoff is None else self._registered_handoff.context_options()
        packet = self._memory.context(data["scope"], data["query"], max_bytes=allowance,
            **options, **self._clocks())
        wrapper["packet"] = packet
        if len(canonical(wrapper).encode()) > data["max_bytes"]:
            raise ContractError("Context wrapper exceeds requested byte ceiling")
        self._check_cancelled(work)
        self._record("mission_context", {"context": wrapper})
        self._check_cancelled(work)
        self._issued_packets[packet["packet_id"]] = copy.deepcopy(wrapper)
        while len(self._issued_packets) > 32:
            del self._issued_packets[next(iter(self._issued_packets))]
        self._last_context_id = packet["packet_id"]
        # Observer preview of the exact journaled packet, never a fresh projection.
        self._last_memory_context = copy.deepcopy(packet)
        self._memory_version = packet["memory_version"]
        return wrapper

    def _memory_request(self, work: _Work) -> dict:
        self._check_cancelled(work)
        if work.request["entry_type"] in ("work", "procedure") and self._registered_handoff.phase is not None:
            raise HandoffEvidenceError("Work/procedure adoption is frozen during handoff; retrieve/claim/readmit first")
        if work.request["entry_type"] == "decision" and work.request["entry"]["packet_id"] not in self._issued_packets:
            raise MemoryRequestRefusal("Decision requires a durably issued context wrapper")
        result = self._memory.apply(work.request, now=self._wall())
        self._memory_version = result["memory_version"]
        return result

    def _handoff(self, work: _Work) -> tuple[str, dict]:
        if work.request["kind"] == "handoff":
            return self._registered_handoff.issue(work)
        if work.request["kind"] == "claim":
            return self._registered_handoff.claim(work)
        return self._registered_handoff.readmit(work)

    def _launch_guard(self, work: _Work, mark: tuple[str, int]) -> None:
        self._check_cancelled(work)
        if mark != self._operator_mark():
            raise ControlError("Owned launch superseded by controller restart or operator Pause")
        ledger = self._ledger.snapshot(now=self._wall())
        if (ledger["epoch"] != work.request["epoch"] or not ledger["clock_valid"]
                or ledger["phase"] not in ("admitted", "paused") or ledger["unreconciled"]):
            raise ControlError("Owned launch requires unchanged paused/admitted actor epoch and reconciled accounting")
        with self.controller.data_lock:
            if (self.controller.closed or self.controller.pending is not None
                    or self.controller.control_pending is not None or self.controller._mission_lease is not None
                    or self.controller._command_work or self.controller.command_lock.locked()
                    or self.controller.control_lock.locked() or not self.controller.pause_requested):
                raise ControlError("Owned launch requires paused empty controller slots")
        if any(os.path.lexists(self.controller.bridge / name) for name in
               ("request.json", "claimed.json", "control.json", "control-claimed.json")):
            raise ControlError("Owned launch requires empty native inboxes")

    def _launch(self, work: _Work) -> tuple[str, dict]:
        data = work.request
        if (data["phase_id"] is not None or data["work_id"] is not None or data["sources"]
                or data["identity_claim_ids"] or any(data[key] is not None for key in
                    ("expected_session", "expected_revision", "expected_boundary_id"))):
            raise ControlError("Launch is a source-free root; it cannot adopt identity or an existing phase")
        if self._lost_process_custody:
            raise ControlError("Previous launch custody is unavailable; no handle restore, PID adoption or replay")
        mark = self._operator_mark()
        self._registered_lifecycle.launch_mark(mark, data["request_id"])
        self._launch_guard(work, mark)
        owner = (self._admission.mission_id, self._admission.configuration.native_sha256)
        if self._native is not None:
            current_launch = self._native.status()["launch_id"]
            verified = any(row["state"] == "completed" and row["result"] is not None
                and row["result"].get("normal_exit", {}).get("launch_id") == current_launch
                for row in self._ledger.request_records()) if current_launch is not None else False
            if self._native_owner != owner or current_launch is not None and not verified:
                raise ControlError("Owned launch must reach registered normal exit before another launch")
        else:
            self._native = NativeProcess(self.controller.root, owner[1], clock=self._clock)
            self._native_owner = owner
        operation = self._ledger.request(data["request_id"])
        deadline = self._clock() + min(operation["deadline"],
            self._mission_deadline - self._admission.cleanup_reserve.wall_seconds) - self._wall()
        if deadline <= self._clock():
            raise BudgetError("Original launch/mission wall budget exhausted")
        attempted = False
        result = {"launch_attempted": False, "process": None, "source_ids": [],
            "native_ready": False, "identity_verified": False, "grants_authority": False}
        try:
            self._record("mission_process_launch_prepared", {"request_id": data["request_id"],
                "native_sha256": owner[1], "deadline_monotonic": deadline, "grants_authority": False})
            self._launch_guard(work, mark)
            attempted = True
            facts = self._native.launch(deadline_monotonic=deadline,
                cancelled=lambda: work.cancelled.is_set() or self._closed.is_set() or mark != self._operator_mark())
            self._native_facts = copy.deepcopy(facts)
            if facts["outcome"] in ("cancelled", "deadline"):
                raise ControlError(f"Owned process launch {facts['outcome']}; custody retained")
            while True:
                self._launch_guard(work, mark)
                self._native_facts = self._native.status()
                if not self._native_facts["running"]:
                    raise ControlError("Owned child exited before native readiness; normal exit is unverified")
                remaining = deadline - self._clock()
                if remaining <= 0:
                    raise BudgetError("Original native readiness deadline expired; no retry of launch")
                self._capacity()
                try:
                    state, received = self._observe_native(work,
                        timeout=min(self.controller.timeout, remaining), deadline_monotonic=deadline)
                except ControlError:
                    self._launch_guard(work, mark)
                    if self._clock() >= deadline:
                        raise BudgetError("Original native readiness deadline expired")
                    work.cancelled.wait(min(0.05, max(0, deadline - self._clock())))
                    continue
                self._launch_guard(work, mark)
                if (state["boundary"]["kind"] != "menu" or state["category"] != "MAIN_MENU"
                        or state["in_game"] or not state["paused"] or not state["frame_ok"] or state["error"]
                        or not 0 <= self._clock() - received <= 3
                        or not -1000 <= int(self._wall() * 1000) - state["timestamp_ms"] <= 3000
                        or state["pause_origin"] not in ("startup", "host") or state["takeover_generation"] != 0):
                    raise ControlError("Owned launch did not reach a fresh paused untouched MAIN_MENU")
                if self._clock() >= deadline or not self._native.status()["running"]:
                    raise ControlError("Owned readiness exceeded its deadline or child exited")
                reference = self._ingest(state, received)
                self._publish_source(reference, authoritative=False)
                self._launch_guard(work, mark)
                self._owned_launch = _OwnedLaunch(data["request_id"], self._native_facts["launch_id"], reference,
                    mark, state["takeover_generation"])
                result.update(native_ready=True, source_ids=[reference.observation_id],
                    reason="Owned child and fresh paused main menu verified; creation/identity/Resume remain pending")
                return "completed", result
        except (ControlError, ContractError, OSError, ValueError) as exc:
            result["reason"] = f"{type(exc).__name__}: {exc}"[:1024]
            return "paused" if work.cancelled.is_set() else "blocked", result
        finally:
            self._native_facts = self._native.status()
            result.update(launch_attempted=attempted, process=copy.deepcopy(self._native_facts))
            self._record("mission_process_launch_result", {"request_id": data["request_id"], **result})

    def _lifecycle(self, work: _Work) -> tuple[str, dict]:
        if work.request["operation"] == "launch":
            return self._launch(work)
        if work.request["operation"] == "exit":
            return self._exit(work)
        if work.request["operation"] in ("create", "save", "load"):
            return self._registered_lifecycle.command(work)
        if work.request["operation"] == "finish":
            return self._finish(work)
        return self._unsupported("Registered create/save/exit/load/finish adapter and identity/effect evidence required")

    def _finish_guard(self, work: _Work) -> None:
        self._check_cancelled(work)
        operation = self._ledger.request(work.request["request_id"])
        if self._wall() >= min(operation["deadline"], self._mission_deadline):
            raise BudgetError("Original finish/mission wall deadline expired")
        if self._operator_mark() != work.finish_mark:
            raise ControlError("Finish superseded by operator Pause or controller restart")
        with self._metadata:
            self._check_cancelled(work)
            if any(handle is not work for handle in self._handles) or not self._queue.empty():
                raise ControlError("Finish requires settled other runtime handles and queue")
        with self.controller.data_lock:
            if (self.controller.pending is not None or self.controller.control_pending is not None
                    or self.controller._mission_lease is not None or self.controller._command_work
                    or self.controller.command_lock.locked() or self.controller.control_lock.locked()
                    or not self.controller.pause_requested):
                raise ControlError("Finish requires paused empty controller slots")
        if any(os.path.lexists(self.controller.bridge / name) for name in
                ("request.json", "claimed.json", "control.json", "control-claimed.json")):
            raise ControlError("Finish requires empty native inboxes")
        if self._native is not None:
            self._native_facts = self._native.status()
            if self._native_facts["running"] or self._native_facts["returncode"] != 0:
                raise ControlError("Finish requires its retained child's normal exit")

    def _finish(self, work: _Work) -> tuple[str, dict]:
        data = work.request
        work.finish_mark = self._operator_mark()
        self._finish_guard(work)
        if (self._lost_process_custody or self._lease is not None or self._prompt_phase is not None
                or self._exit_phase is not None or self._registered_lifecycle.phase is not None
                or self._registered_lifecycle.candidate is not None or data["phase_id"] is not None
                or data["identity_claim_ids"] or self._current is None):
            raise ControlError("Finish requires settled lifecycle and owned custody")
        reference = self._current
        state = self._store.observation(reference)
        if (reference.observation_id not in data["sources"]
                or (data["expected_session"], data["expected_revision"], data["expected_boundary_id"]) !=
                   (reference.session, reference.revision, state["boundary"]["id"])
                or self._store.source_status(reference) != "retained"):
            raise EvidenceError("Finish requires its exact retained final source; age alone is not failure")
        exits = [row for row in self._ledger.request_records() if row["state"] == "completed"
            and row["result"] is not None and "normal_exit" in row["result"]]
        if not exits:
            raise ControlError("Normal finish requires a committed owned exit, not process absence")
        event = None
        if data["work_id"] is not None:
            records = self._ledger.memory_records("work")
            matches = [row for row in records if row["entry"]["id"] == data["work_id"]]
            if not matches:
                raise EvidenceError("Objective finish requires retained Work")
            entry = matches[-1]["entry"]
            refs = {ref.observation_id: ref for ref in self._store.historical_references}
            views, reasons = CampaignMemory._work_views(records, refs)
            if data["work_id"] in reasons or views[data["work_id"]]["status"] != "completed":
                raise EvidenceError("Objective Work has incomplete or conflicting observed progress")
            for identity in views[data["work_id"]]["sources"]:
                if identity not in refs or self._store.source_status(refs[identity]) != "retained":
                    raise EvidenceError("Objective Work source is lost or disputed")
            normals = [ref for ref in refs.values() if ref.boundary_kind == "normal_play"]
            if not normals or entry["scope"] != self._coordinate_scope(normals[-1]):
                raise EvidenceError("Objective Work must be revalidated in the last adopted normal session")
            event = matches[-1]["event_id"]
        proof = {"schema": VERSION, "record_type": "NormalFinish", "final_source_id": reference.observation_id,
            "normal_exit_result_request_id": exits[-1]["request"]["request_id"],
            "completed_work_event_id": event, "disposition": "stopped" if event is None else "completed",
            "grants_authority": False}
        self._ledger._check_normal_finish(data["request_id"], data, proof)
        self._finish_guard(work)
        self.controller.stop_input()
        self._lease, self._map = None, None
        self._bindings.clear()
        state = self._ledger.begin_finishing(epoch=data["epoch"], reason="Normal exit verified; recording mission outcome", now=self._wall())
        work.finish_epoch = state["epoch"]
        self._finish_guard(work)
        return "completed", {"normal_finish": proof, "grants_authority": False}

    def _commit_finish(self, work: _Work, result: dict) -> None:
        """Pause before this final fence wins; later Pause cannot rewrite history."""
        self._apply_pauses()
        self._finish_guard(work)
        state = self._ledger.snapshot(now=self._wall())
        if state["epoch"] != work.finish_epoch or state["phase"] != "finishing":
            raise ControlError("Finishing epoch changed before terminal persistence")
        # Process sampling and ledger reads may yield to an operator Pause.
        # This is the final cancellation fence, after those reads and before
        # terminal persistence; no controller/runtime lock spans SQLite I/O.
        with self._metadata:
            self._check_cancelled(work)
            if self._pending_pauses or self._operator_mark() != work.finish_mark:
                raise _Cancelled("Normal finish superseded before terminal persistence")
        disposition = result["normal_finish"]["disposition"]
        try:
            self._registered_reflection.finish(permanent=False)
            self._finish_guard(work)
            self._ledger.finish_mission(disposition, epoch=work.finish_epoch,
                request_id=work.request["request_id"],
                reason="Player-reported objective completion" if disposition == "completed" else "Normal cleanup; objective completion unclaimed",
                now=self._wall())
        except (_Cancelled, ControlError, BudgetError):
            self._registered_reflection.cancel_finish()
            raise
        self._record("mission_normal_finish", result)
        self._native, self._native_owner, self._owned_launch = None, None, None

    def _owned_menu(self) -> _OwnedLaunch:
        launch = self._owned_launch
        if launch is None or self._native is None or self._lost_process_custody:
            raise ControlError("Untouched-menu exit requires this runtime's retained owned launch")
        self._native_facts = self._native.status()
        if (self._native_facts["launch_id"] != launch.launch_id or not self._native_facts["running"]
                or self._operator_mark() != launch.operator_mark):
            raise ControlError("Owned menu custody or original operator mark changed")
        if self._registered_lifecycle.saved_exit_checkpoint() is None:
            if self._registered_lifecycle.normal_after_launch():
                raise ControlError("Normal gameplay requires its own verified saved checkpoint before menu exit")
            root = self._exit_phase.root_id if self._exit_phase is not None else (
                self._active.request["request_id"] if self._active is not None
                and self._active.request.get("operation") == "exit" else None)
            self._ledger.menu_cleanup_resume(launch.request_id, exit_root_id=root)
        return launch

    def _resume_only_menu(self, launch: _OwnedLaunch, reference: EvidenceRef) -> bool:
        """Adopt only the internally paused menu after one proven setup Resume.

        Uses immutable launch/dispatch evidence, not caller assertions or process
        exit codes. It authorizes no input; a separate normal-exit root is needed.
        """
        if (self._registered_lifecycle.phase is not None or self._registered_lifecycle.candidate is not None
                or self._registered_lifecycle.normal_after_launch() or self._exit_candidate is not None
                or self._lease is not None or self._live()[5]
                or any((self.controller.bridge / name).exists() for name in
                       ("request.json", "claimed.json", "control.json", "control-claimed.json"))):
            return False
        return self._resume_menu_equivalent(launch, reference, paused=True, exit_root_id=None)

    def _resume_menu_equivalent(self, launch: _OwnedLaunch, reference: EvidenceRef, *, paused: bool,
                                exit_root_id: str | None) -> bool:
        """Compare settled setup exploration with its current owned main menu.

        The caller owns live-phase/lease/custody checks. This shared proof grants
        neither setup continuation nor cleanup authority by itself.
        """
        primitive = self._ledger.menu_cleanup_resume(launch.request_id, exit_root_id=exit_root_id)
        if primitive is None:
            return False
        intent, receipt = primitive["intent"], primitive["result"]
        refs = {ref.observation_id: ref for ref in self._store.historical_references}
        baseline = refs[self._ledger.request(launch.request_id)["result"]["source_ids"][0]]
        before, preflight, after = (refs[identity] for identity in (
            intent["source_before"], intent["preflight_source"], receipt["source_after"]))
        binding = receipt["dispatch_binding"]
        setup_requests = {row["request"]["request_id"] for row in self._ledger.request_records()
            if row["request"]["request_id"] == primitive["request_id"]
                or row["request"].get("phase_id") == primitive["request_id"]}
        settled = [item for item in self._ledger.primitive_records() if item["request_id"] in setup_requests]
        last_ack = settled[-1]["result"]["native_ack"]
        original, resumed, current = (self._store.observation(ref) for ref in (baseline, after, reference))
        expected = copy.deepcopy(original)
        expected.update(revision=before.revision + 1, paused=False, pause_origin="none")
        expected["boundary"]["control_generation"] += 1
        positions = {ref.observation_id: index for index, ref in enumerate(self._store.historical_references)}
        interval = self._store.historical_references[positions[after.observation_id]:positions[reference.observation_id] + 1]
        explored = all(ref.session == baseline.session and ref.boundary_kind == "menu"
            and not self._store.observation(ref)["in_game"]
            and self._store.observation(ref)["takeover_generation"] == launch.takeover_generation
            and self._store.observation(ref)["pause_origin"] != "human" for ref in interval)
        ledger = self._ledger.snapshot(now=self._wall())
        return (launch.operator_mark == self._operator_mark() and ledger["clock_valid"] and not ledger["unreconciled"]
            and binding["controller_boot_id"] == launch.operator_mark[0]
            and binding["operator_pause_generation"] == launch.operator_mark[1]
            and binding["takeover_generation"] == launch.takeover_generation
            and binding["actor_id"] == ledger["player_id"]
            and original["category"] == "MAIN_MENU" and not original["in_game"] and original["paused"]
            and self._store.equivalent(baseline, before, rule="exact_png_bytes")
            and self._store.equivalent(before, preflight, rule="exact_png_bytes")
            and same_native_state(expected, resumed) and explored
            and current["session"] == resumed["session"] and current["category"] == "MAIN_MENU"
            and current["revision"] == last_ack["revision"]
            and not current["in_game"] and current["boundary"]["kind"] == "menu"
            and current["boundary"]["control_generation"] == resumed["boundary"]["control_generation"]
            and current["paused"] == paused and current["pause_origin"] == ("host" if paused else "none")
            and resumed["id"] == primitive["native_id"]
            and self._store.current_boundary(**self._clocks()) == reference)

    def _abort_untouched_setup(self, work: _Work) -> tuple[str, dict]:
        """An explicit exit may first revoke settled menu-only exploration.

        No input is sent and the launch checkpoint is not rebased. Separate
        Observe and a new finite exit root are required after the epoch change.
        """
        data, adapter = work.request, self._registered_lifecycle
        phase = adapter.phase
        launch = self._owned_menu()
        if (phase is None or adapter.candidate is not None or phase.launch != launch
                or phase.operation not in ("create", "load") or phase.stage != "awaiting_control"
                or data["phase_id"] is not None or data["work_id"] is not None or data["identity_claim_ids"]
                or self._exit_phase is not None or self._exit_candidate is not None or self._prompt_phase is not None
                or adapter.normal_after_launch() or self._live()[5]
                or any((self.controller.bridge / name).exists() for name in
                       ("request.json", "claimed.json", "control.json", "control-claimed.json"))):
            raise ControlError("Setup abort requires settled exploration and its owned main menu")
        adapter.guard(work, phase)
        adapter._binding_request(work, phase.checkpoint)
        observed = self._store.observation(phase.checkpoint)
        if observed["category"] != "MAIN_MENU" or observed["paused"] or observed["in_game"]:
            raise ControlError("Setup abort cannot cancel another setup screen or normal gameplay")
        # Even a fresh retained image is compared with a new native capture:
        # this is a zero-input revocation, without dispatch's usual preflight.
        phase = adapter._refresh(work, phase, diagnostic=True, ordinary=True)
        if not self._resume_menu_equivalent(launch, phase.checkpoint, paused=False, exit_root_id=data["request_id"]):
            raise EvidenceError("Setup abort lost its settled same-session menu evidence")
        self._check_cancelled(work)
        source = phase.checkpoint.observation_id
        self._stop_after_failure("Explicit menu-only setup abort; fresh Observe and new normal exit required")
        self._check_cancelled(work)
        result = {"cleanup_requested": True, "source_ids": [source], "grants_authority": False,
            "reason": "Setup authority revoked without input; separately Observe then request normal exit"}
        self._record("mission_menu_cleanup_requested", result)
        return "partial", result

    def _exit_guard(self, work: _Work, phase: _ExitPhase,
                    proposal: MissionIntent | _ResumeIntent | None = None) -> None:
        self._check_cancelled(work)
        launch = self._owned_menu()
        ledger = self._ledger.snapshot(now=self._wall())
        if (phase is not self._exit_phase or phase.launch.launch_id != launch.launch_id
                or phase.launch.operator_mark != launch.operator_mark
                or ledger["epoch"] != phase.epoch or work.request["epoch"] != phase.epoch
                or ledger["player_id"] != phase.actor_id or ledger["unreconciled"] or not ledger["clock_valid"]):
            raise ControlError("Exit phase lost its actor/epoch/accounting or original operator mark")
        before = self._store.observation(phase.checkpoint)
        if (before["session"] != launch.checkpoint.session or before["takeover_generation"] != launch.takeover_generation
                or before["in_game"] or before["boundary"]["kind"] != "menu" or before["error"]
                or before["status"] != "ready" or not before["frame_ok"]):
            raise ControlError("Exit phase cannot adopt a different native session/boundary")
        if proposal is not None:
            if proposal.before != phase.checkpoint:
                raise EvidenceError("Exit input does not name its exact owned checkpoint")
            if proposal.kind == "resume":
                state, _, boot, lease, _, pending = self._live()
                if (lease is not None or pending or boot != launch.operator_mark[0] or state is None
                        or not before["paused"] or before["category"] != "MAIN_MENU"):
                    raise ControlError("Bootstrap Resume requires an owned paused untouched main menu")
            else:
                state, _, _ = self._check_lease()
                if self._lease.operation != "lifecycle" or state["session"] != before["session"]:
                    raise ControlError("Exit requires its exact lifecycle lease")
                if proposal.kind not in ("action", "key", "direct"):
                    raise ControlError("Owned exit requires an ordinary or menu input proposal")

    def _exit_receipt(self, phase: _ExitPhase, stage: str) -> dict:
        saved_sources = () if phase.saved_checkpoint is None else (
            self._ledger.request(phase.saved_checkpoint)["result"]["saved_checkpoint"]["menu_source_id"],)
        resume = (self._ledger.menu_cleanup_resume(phase.launch.request_id, exit_root_id=phase.root_id)
                  if phase.saved_checkpoint is None else None)
        resume_sources = () if resume is None else (
            resume["intent"]["source_before"], resume["intent"]["preflight_source"], resume["result"]["source_after"])
        return {"schema": VERSION, "record_type": "PhaseReceipt", "phase_kind": "lifecycle", "operation": "exit",
            "origin_request_id": phase.root_id, "stage": stage, "epoch": phase.epoch, "actor_id": phase.actor_id,
            "controller_boot_id": phase.launch.operator_mark[0], "operator_pause_generation": phase.launch.operator_mark[1],
            "takeover_generation": phase.launch.takeover_generation,
            "source_ids": list(dict.fromkeys((*self._ledger.request(phase.launch.request_id)["result"]["source_ids"],
                *saved_sources, *resume_sources, phase.launch.checkpoint.observation_id, phase.checkpoint.observation_id))),
            "continuity": None, "launch_request_id": phase.launch.request_id, "launch_id": phase.launch.launch_id,
            "no_save_required": phase.saved_checkpoint is None,
            **({"saved_checkpoint_request_id": phase.saved_checkpoint} if phase.saved_checkpoint is not None else {}),
            "grants_authority": False}

    def _refresh_exit(self, work: _Work, phase: _ExitPhase, *, ordinary: bool = False) -> _ExitPhase:
        self._exit_guard(work, phase)
        self._capacity()
        source = phase.checkpoint
        operation = self._ledger.request(phase.root_id if work.request["kind"] == "observe" else work.request["request_id"])
        deadline = self._clock() + min(operation["deadline"],
            self._mission_deadline - self._admission.cleanup_reserve.wall_seconds) - self._wall()
        state, received = self._observe_native(work, deadline_monotonic=deadline)
        reference = self._ingest(state, received)
        if ordinary:
            self._capture_custody(self._store.observation(source), state)
        elif not self._store.equivalent(source, reference, rule="exact_png_bytes"):
            raise EvidenceError("Owned exit refresh changed the exact interpreted menu image/state")
        self._exit_guard(work, phase)
        phase = replace(phase, checkpoint=reference)
        self._exit_phase = phase
        self._exit_guard(work, phase)
        self._publish_source(reference, authoritative=False)
        self._record("mission_exit_checkpoint", {"before": source.observation_id, "after": reference.observation_id,
            "rule": "ordinary_input" if ordinary else "exact_png_bytes", "grants_authority": False})
        return phase

    def _exit(self, work: _Work) -> tuple[str, dict]:
        if self._registered_lifecycle.phase is not None:
            return self._abort_untouched_setup(work)
        data = work.request
        launch = self._owned_menu()
        if (data["phase_id"] is not None or data["work_id"] is not None or data["identity_claim_ids"]
                or self._exit_phase is not None or self._prompt_phase is not None
                or self._current != launch.checkpoint or launch.checkpoint.observation_id not in data["sources"]):
            raise ControlError("Untouched exit requires its owned source as a new unambiguous root")
        state = self._store.observation(launch.checkpoint)
        if (state["category"] != "MAIN_MENU" or not state["paused"]
                or (data["expected_session"], data["expected_revision"], data["expected_boundary_id"]) !=
                   (state["session"], state["revision"], state["boundary"]["id"])):
            raise ControlError("Untouched exit requires its exact paused main-menu binding")
        ledger = self._ledger.snapshot(now=self._wall())
        saved = self._registered_lifecycle.saved_exit_checkpoint()
        # This immediate plan always charges Resume and Quit separately. Refuse
        # an unaffordable draft before installing a phase or sending either.
        if data["limits"]["primitives"] < 2:
            return "blocked", {"reason": "Owned paused-menu exit requires at least2 primitives for "
                "Resume plus Quit, before any later confirmation. No input was sent or exit phase "
                "installed. Choose a separate new exit request with a sufficient finite allowance; "
                "original mission limits remain unchanged.", "required_primitives": 2,
                "source_ids": [launch.checkpoint.observation_id], "grants_authority": False}
        self._exit_phase = phase = _ExitPhase(data["request_id"], launch.checkpoint, launch,
            ledger["player_id"], ledger["epoch"], saved)
        phase = self._refresh_exit(work, phase)
        self._ledger.activate(epoch=phase.epoch, player_id=phase.actor_id, now=self._wall())
        logical = "resume-" + hashlib.sha256(data["request_id"].encode()).hexdigest()
        proposal = _ResumeIntent(logical, phase.checkpoint, self._store.observation(phase.checkpoint)["boundary"]["id"])
        feedback = self._dispatch(work, proposal, phase.launch.checkpoint, lifecycle=phase)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return feedback.transport_disposition if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, "phase": self._exit_receipt(phase, "unknown"), "grants_authority": False}
        state = self._store.observation(feedback.after)
        if state["paused"] or state["category"] != "MAIN_MENU" or state["takeover_generation"] != launch.takeover_generation:
            raise ControlError("Bootstrap Resume did not return the same owned main menu")
        self._lease = self.controller.acquire_mission(self._admission.mission_id, phase.epoch, phase.actor_id,
            operation="lifecycle", expected_session=state["session"], expected_revision=state["revision"],
            expected_boundary_id=state["boundary"]["id"])
        self._exit_phase = phase = replace(phase, checkpoint=feedback.after)
        proposal = ControlIntent("quit-" + hashlib.sha256(data["request_id"].encode()).hexdigest(),
            "action", "QUIT", phase.checkpoint, state["boundary"]["id"])
        feedback = self._dispatch(work, proposal, phase.launch.checkpoint, lifecycle=phase)
        if self._exit_candidate is not None and (feedback.transport_disposition == "unknown"
                or not self._native.status()["running"]):
            return self._finish_owned_exit(work, phase, proposal)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, "phase": self._exit_receipt(phase,
                    "awaiting_control" if self._exit_phase is not None else "unknown"), "grants_authority": False}
        self._exit_candidate = None
        self._exit_phase = phase = replace(phase, checkpoint=self._current)
        self._exit_guard(work, phase)
        return "partial", {"reason": "Owned Quit returned; inspect the actual menu and choose ordinary or semantic input",
            "phase": self._exit_receipt(phase, "awaiting_control"), "grants_authority": False}

    def _exit_control(self, work: _Work) -> tuple[str, dict]:
        phase, data = self._exit_phase, work.request
        if (phase is None or data["phase_id"] != phase.root_id or data["work_id"] is not None
                or data["skill_kind"] not in ("menu", "direct")
                or phase.checkpoint.observation_id not in data["sources"]):
            raise ControlError("Owned exit requires its exact source-bound ordinary or menu child")
        self._exit_guard(work, phase)
        ordinary = data["skill_kind"] == "direct"
        deadline = self._deadline(work, phase.checkpoint)
        skill = (OrdinaryInputSkill(data, deadline_monotonic=deadline) if ordinary else
                 MenuSkill(data, deadline_monotonic=deadline) if data["perception"] is None else
                 SemanticControlSkill(data, deadline_monotonic=deadline))
        inspected, _ = self._store.inspect_current_boundary(**self._clocks())
        if inspected != phase.checkpoint:
            raise EvidenceError("Exit input lost its exact retained checkpoint")
        binding = self._binding(phase.checkpoint)
        original = phase.checkpoint
        phase = self._refresh_exit(work, phase, ordinary=True)
        if not ordinary and not self._store.equivalent(original, phase.checkpoint, rule="exact_png_bytes"):
            return "blocked", {"reason": "Fresh owned menu changed; inspect it and choose a new ordinary or semantic input",
                "phase": self._exit_receipt(phase, "awaiting_control"), "grants_authority": False}
        if ordinary:
            relation = InputObservation(binding, self._binding(phase.checkpoint))
            skill.observe(relation, self._store, **self._clocks())
            self._record("mission_input_observation", relation.to_dict())
        else:
            relation = SourceRevalidation(binding, self._binding(phase.checkpoint), "exact_png_bytes")
            skill.revalidate(relation, self._store, **self._clocks())
            self._record("mission_exit_revalidation", relation.to_dict())
        while True:
            proposal = skill.propose(self._store, **self._clocks())
            if isinstance(proposal, (ControlOutcome, MenuOutcome)):
                outcome = proposal
            else:
                feedback = self._dispatch(work, proposal, phase.launch.checkpoint, lifecycle=phase)
                if self._exit_candidate is not None and (feedback.transport_disposition == "unknown"
                        or not self._native.status()["running"]):
                    return self._finish_owned_exit(work, phase, proposal)
                self._exit_candidate = None
                outcome = skill.accept(feedback, self._store, **self._clocks())
                if feedback.transport_disposition == "returned" and feedback.after is not None:
                    inspected, _ = self._store.inspect_current_boundary(**self._clocks())
                    if inspected is None or inspected != self._current:
                        raise EvidenceError("Known exit input lost its current evidence authority")
                    live, _, _ = self._check_lease()
                    self._capture_custody(self._store.observation(inspected), live)
                    self._exit_phase = phase = replace(phase, checkpoint=self._current)
                    self._exit_guard(work, phase)
                    if self._store.observation(phase.checkpoint)["category"] == "MAIN_MENU":
                        # Returning to the owned main menu closes this attempt,
                        # regardless of the physical key or optional label used.
                        self.controller.stop_input()
                        self._lease = None
                        self._exit_phase = None
                        state, received = self._observe_native(work, deadline_monotonic=self._deadline(work, proposal.before))
                        reference = self._ingest(state, received)
                        if (state["session"] != phase.launch.checkpoint.session or state["category"] != "MAIN_MENU"
                                or not state["paused"] or state["error"] or not state["frame_ok"]
                                or state["takeover_generation"] != phase.launch.takeover_generation
                                or self._operator_mark() != phase.launch.operator_mark):
                            raise ControlError("Exit cancellation did not return the same owned paused main menu")
                        self._owned_launch = replace(phase.launch, checkpoint=reference)
                        self._publish_source(reference, authoritative=False)
                        phase = replace(phase, checkpoint=reference)
                        return "partial", {"reason": "Returned to owned main menu; process remains live",
                            "normal_exit_verified": False, "phase": self._exit_receipt(phase, "complete"),
                            "grants_authority": False}
                    if self._current != feedback.after:
                        return "partial", {"reason": "Known input returned; changed current menu needs a new decision",
                            "phase": self._exit_receipt(phase, "awaiting_control"), "grants_authority": False}
                    if outcome is not None and outcome.disposition == "unknown":
                        # Optional policy surprise cannot un-deliver this known
                        # input or revoke the verified healthy ordinary receiver.
                        outcome = replace(outcome, disposition="partial", pending_logical_id=None)
                if outcome is None:
                    continue
            result = self._control_result(outcome)
            result["phase"] = self._exit_receipt(phase,
                "unknown" if outcome.disposition == "unknown" else "awaiting_control")
            return outcome.disposition, result

    def _finish_owned_exit(self, work: _Work, phase: _ExitPhase, proposal: ControlIntent) -> tuple[str, dict]:
        candidate = self._exit_candidate
        if candidate is None or candidate[:2] != (phase, proposal.logical_id):
            raise ControlError("No correlated published terminal exit candidate")
        self._exit_effect_guard(work, phase)
        facts = self._native.wait_exit(deadline_monotonic=self._deadline(work, proposal.before),
            cancelled=lambda: work.cancelled.is_set() or self._closed.is_set() or phase.launch.operator_mark != self._operator_mark())
        self._native_facts = copy.deepcopy(facts)
        self._exit_effect_guard(work, phase)
        if (phase.launch.operator_mark != self._operator_mark() or facts["launch_id"] != phase.launch.launch_id
                or facts["running"] or facts["returncode"] != 0 or facts["outcome"] != "exited"):
            raise ControlError("Expected terminal input did not establish this owned child's normal exit")
        for identity in self._exit_receipt(phase, "complete")["source_ids"]:
            self._store.verify(next(ref for ref in self._store.historical_references if ref.observation_id == identity))
        self.controller.stop_input()
        self._lease = None
        with self.controller.data_lock:
            self._exit_effect_guard(work, phase)
            self.controller.frozen = True
            pending = copy.deepcopy(self.controller.pending)
            generation = self.controller.pause_generation
        if pending is not None and pending != candidate[2]:
            raise ControlError("Exit pending slot differs from its exact terminal native request")
        retirement = self.controller.retire_mission_exit(expected_controller_boot_id=phase.launch.operator_mark[0],
            expected_operator_generation=phase.launch.operator_mark[1], expected_generation=generation,
            expected_request=pending, launch_id=phase.launch.launch_id, exit_request_id=phase.root_id, returncode=0)
        receipt = self._exit_receipt(phase, "complete")
        primitive = self._ledger.primitive(proposal.logical_id)
        proof = {"schema": VERSION, "record_type": "OwnedNormalExit", "origin_request_id": phase.root_id,
            "launch_request_id": phase.launch.request_id, "launch_id": phase.launch.launch_id,
            "terminal_logical_id": proposal.logical_id, "native_request_id": candidate[2]["id"],
            "source_ids": receipt["source_ids"], "no_save_required": phase.saved_checkpoint is None, "returncode": 0,
            **({"saved_checkpoint_request_id": phase.saved_checkpoint} if phase.saved_checkpoint is not None else {}),
            "retirement": retirement, "grants_authority": False}
        if primitive["state"] == "unknown":
            self._ledger.reconcile_effect(proposal.logical_id, proof=proof, sources=tuple(receipt["source_ids"]),
                note=f"Owned normal exit {phase.launch.launch_id} after published exit input; ACK remains unknown", now=self._wall())
        if candidate[3] is not None:
            # This exact child exited normally and its pending input/effect is
            # retired. No after-frame can arrive; keep the unknown ACK/charge.
            self._store.release(candidate[3])
        self._exit_phase = None
        self._exit_candidate = None
        self._bindings.clear()
        return "completed", {"reason": "Owned main-menu normal exit verified; input ACK retained separately",
            "phase": receipt, "normal_exit": proof, "grants_authority": False}

    def _exit_effect_guard(self, work: _Work, phase: _ExitPhase) -> None:
        """An expected unknown destroys input authority, not takeover precedence."""
        self._check_cancelled(work)
        before = self._store.observation(phase.checkpoint)
        state = self._live()[0]
        if (self._operator_mark() != phase.launch.operator_mark or state is None
                or state["session"] != phase.checkpoint.session or state["pause_origin"] == "human"
                or state["in_game"] or state["scene"] is not None or state["error"]
                or state["boundary"]["kind"] != "menu"
                or phase.saved_checkpoint is None and self._registered_lifecycle.normal_after_launch()
                or phase.saved_checkpoint is not None and self._registered_lifecycle.saved_exit_checkpoint() != phase.saved_checkpoint
                or state["takeover_generation"] != phase.launch.takeover_generation
                or state["boundary"]["control_generation"] != before["boundary"]["control_generation"]):
            raise ControlError("Expected exit effect superseded by controller/native Pause or takeover")

    @staticmethod
    def _unsupported(reason: str) -> tuple[str, dict]:
        return "blocked", {"reason": reason, "capability_needed": True, "grants_authority": False}

    def _informing(self, data: dict) -> tuple[EvidenceRef, SourceBinding]:
        state, generation, boot = self._check_lease()
        ledger = self._ledger.snapshot(now=self._wall())
        if ledger["phase"] != "active" or ledger["unreconciled"]:
            raise LedgerError("Navigation requires active reconciled mission")
        original = None
        for identity in data["sources"]:
            if identity not in self._bindings:
                raise EvidenceError("Informing source was not published to this live actor")
            ref, binding = self._bindings[identity]
            if (binding.mission_id, binding.epoch, binding.actor_id, binding.controller_boot_id,
                    binding.pause_generation, binding.takeover_generation) != (
                    self._admission.mission_id, ledger["epoch"], ledger["player_id"], boot,
                    generation, state["takeover_generation"]):
                raise EvidenceError("Informing source crossed actor/epoch/controller/Pause/takeover")
            self._store.verify(ref)
            if ref == self._current:
                original = (ref, binding)
        if original is None or original[1].store_generation != self._store.authority_generation():
            raise EvidenceError("Another observation invalidated this informing source")
        observed = self._store.observation(original[0])
        self._capture_custody(observed, state)
        return original

    def _rotate(self, work: _Work, proposal: MissionIntent) -> None:
        state, generation, _ = self._check_lease()
        observed = self._store.observation(proposal.before)
        self._capture_custody(observed, state)
        if proposal.kind != "direct" and not same_native_state(observed, state):
            if work.request["kind"] != "skill" or not self._ordinary_refusal_guard(work, proposal.before):
                raise EvidenceError("Specialized proposal lost its exact live native state")
            raise MissionInputRefusal("Semantic applicability changed before rotation; Observe and choose again",
                                      status="rejected")
        self._check_cancelled(work)
        old = self._lease
        new = self.controller.acquire_mission(old.mission_id, old.epoch, old.actor_id,
            operation="lifecycle" if work.request["kind"] == "lifecycle" else (
                "navigate" if work.request["skill_kind"] == "navigate" else "interaction"),
            expected_session=state["session"], expected_revision=state["revision"],
            expected_boundary_id=state["boundary"]["id"], replace=old,
            refuse_changed_context=work.request["kind"] == "skill"
                and self._exit_phase is None and self._registered_lifecycle.phase is None
                and self._registered_activity.phase is None and self._registered_recovery.phase is None
                and self._registered_recovery.continuation is None)
        self._lease = new
        if new.pause_generation != generation + 1:
            raise ControlError("Operation rotation did not make exactly one host generation")
        self._rotation = (work.request["request_id"], proposal.before.observation_id, generation, old, new)
        self._record("mission_rotation", {"request_id": work.request["request_id"],
            "source_id": proposal.before.observation_id, "before": asdict(old), "after": asdict(new)})
        self._check_cancelled(work)

    def _dispatch_authority_guard(self, work: _Work, before: EvidenceRef, *, local_limits: bool = True) -> None:
        self._check_cancelled(work)
        state, generation, boot = self._check_lease()
        ledger = self._ledger.snapshot(now=self._wall())
        if ledger["epoch"] != work.request["epoch"] or ledger["phase"] != "active":
            raise LedgerError("Operation epoch/phase revoked")
        entry = self._bindings.get(before.observation_id)
        if entry is None:
            raise EvidenceError("Proposal source has no live binding")
        binding = entry[1]
        if (binding.epoch, binding.actor_id, binding.controller_boot_id, binding.takeover_generation) != (
                ledger["epoch"], ledger["player_id"], boot, state["takeover_generation"]):
            raise EvidenceError("Proposal binding crossed live actor/controller/takeover")
        if binding.pause_generation != generation:
            transition = self._rotation
            if (transition is None or transition[:3] != (work.request["request_id"],
                    before.observation_id, binding.pause_generation)
                    or transition[3].pause_generation != binding.pause_generation
                    or transition[4] is not self._lease or generation != binding.pause_generation + 1):
                raise EvidenceError("Proposal binding crossed an unauthenticated host generation")
        if self._store.authority_generation() != binding.store_generation:
            raise EvidenceError("Proposal store generation changed")
        if self._game_cost is None or self._game_cost >= self._admission.limits.game_seconds:
            raise BudgetError("Game time unavailable or exhausted")
        phase = self._prompt_authority_guard(work.request, before)
        if local_limits and phase is not None:
            root = self._ledger.request(phase.root_id)["request"]
            self._game_guard(phase.game_anchor, root["limits"]["game_seconds"])
        if local_limits and work.game_anchor is not None:
            self._game_guard(work.game_anchor, work.request["limits"]["game_seconds"])

    def _dispatch_guard(self, work: _Work, before: EvidenceRef) -> None:
        self._dispatch_authority_guard(work, before)
        self._prompt_guard(work.request, before)

    def _ordinary_refusal_guard(self, work: _Work, before: EvidenceRef,
                                logical_id: str | None = None, *, command_work: int = 0) -> bool:
        """Shared health proof for ordinary nondelivery, never input permission."""
        data, phase = work.request, self._prompt_phase
        if (data["kind"] != "skill"
                or self._exit_phase is not None or self._registered_lifecycle.phase is not None
                or self._registered_activity.phase is not None or self._registered_recovery.phase is not None
                or self._registered_recovery.continuation is not None):
            return False
        self._dispatch_authority_guard(work, before, local_limits=False)
        native = self.controller.check_mission_refusal(self._lease, self._lease.pause_generation, command_work=command_work)
        observed = self._store.observation(before)
        self._capture_custody(observed, native)
        state = self._ledger.snapshot(now=self._wall())
        if not state["clock_valid"] or state["unreconciled"]:
            raise LedgerError("Local refusal cannot hide clock faults or unresolved delivery")
        if (self._wall() >= self._mission_deadline - self._admission.cleanup_reserve.wall_seconds
                or state["remaining_inputs"] <= self._admission.cleanup_reserve.inputs
                or state["spent_inputs"] >= self._admission.limits.primitive_mappings):
            raise BudgetError("Mission allowance or ending reserve exhausted")
        # This proof can run under the controller's publication RLock. Query
        # counters/pending identities in SQLite, not all historical ACK bodies.
        with self._ledger._mutex:
            pending = self._ledger._db.execute(
                "SELECT id,request_id,state FROM primitives WHERE state IN ('prepared','published')").fetchall()
        if any((identity, request, status) != (logical_id, data["request_id"], "prepared")
               for identity, request, status in pending):
            raise LedgerError("Local refusal cannot hide another unsettled input")
        self._store.verify(before)
        self._capacity(frames=0, byte_count=0)
        if phase is not None:
            self._store.verify(phase.checkpoint)
            self._store.verify(phase.game_anchor)
        if work.game_anchor is not None:
            self._store.verify(work.game_anchor)
        return True

    def _local_input_refusal(self, work: _Work, before: EvidenceRef,
                             logical_id: str | None = None, *, command_work: int = 0) -> str | None:
        """Positive local expiry proof, never authority from an error message."""
        data, phase = work.request, self._prompt_phase
        if (data["kind"] != "skill" or phase is None and data["skill_kind"] not in ("direct", "program")
                or not self._ordinary_refusal_guard(work, before, logical_id, command_work=command_work)):
            return None
        with self._ledger._mutex:
            count = self._ledger._db.execute("SELECT count(*) FROM primitives WHERE request_id=?",
                                            (data["request_id"],)).fetchone()[0]
        local = None
        if phase is not None:
            local = self._ordinary_macro_limit(phase)
        operation = self._ledger.request(data["request_id"])
        if self._wall() >= operation["deadline"]:
            local = "wall_seconds"
        elif count >= data["limits"]["primitives"]:
            local = "primitives"
        if work.game_anchor is not None:
            try:
                self._game_guard(work.game_anchor, data["limits"]["game_seconds"])
            except _LocalGameLimit:
                local = "game_seconds"
        return None if local is None else f"Original local {local} allowance exhausted; Observe before a new input decision"

    def _unpublished_refusal_guard(self, work: _Work, before: EvidenceRef,
                                   logical_id: str, raw: dict, preflight: EvidenceRef | None) -> None:
        """Authenticate an existing rejected receipt before preserving read-only lineage.

        Image/geometry refusals may precede controller preparation. Their status
        alone proves neither final custody nor mission/source/storage health.
        """
        if not self._ordinary_refusal_guard(work, before, logical_id):
            raise ControlError("Unpublished refusal cannot preserve lifecycle or recovery authority")
        proof = raw["preflight"]
        if proof is None:
            raise EvidenceError("Unpublished refusal lacks its actual preflight observation")
        native, _ = self.controller.observation_snapshot()
        observed, received = proof["observation"], proof["received_monotonic"]
        if (preflight is None or self._store.observation(preflight) != observed
                or preflight.received_monotonic != received
                or self._store.source_status(preflight) != "retained"):
            raise EvidenceError("Unpublished refusal lost its actual retained preflight and original receipt")
        self._capture_custody(observed, native)
        if (not 0 <= self._clock() - received <= MAX_AGE_SECONDS
                or not -1000 <= self._wall() * 1000 - observed["timestamp_ms"] <= MAX_AGE_SECONDS * 1000):
            raise EvidenceError("Unpublished refusal preflight observation expired")

    def _skill_draft_rejection(self, work: _Work) -> dict | None:
        """Reject metadata/representation drafts only while their scope is eligible.

        This reads an immutable source, never substitutes fields or promotes its
        freshness. Real authority/evidence/budget faults retain their stopping
        path; a new corrected request must still pass normal execution checks.
        """
        data = work.request
        current, _ = self._store.inspect_current_boundary(**self._clocks())
        if current is None or current != self._current:
            return None
        obsolete_selection = current.observation_id not in data["sources"]
        if obsolete_selection and self._registered_lifecycle.phase is not None:
            # Lifecycle already checks a stale selection against its owned
            # active or paused transition. Preserve that narrower recovery path.
            return None
        if (not obsolete_selection and data["perception"] is not None
                and data["perception"]["source_id"] != current.observation_id):
            return None
        observed = self._store.observation(current)
        metadata_mismatch = (not obsolete_selection and
                            (data["expected_session"], data["expected_revision"], data["expected_boundary_id"]) !=
                             (current.session, current.revision, observed["boundary"]["id"]))
        current_entry = self._bindings.get(current.observation_id)
        authority_fields = ("mission_id", "epoch", "actor_id", "controller_boot_id",
                            "pause_generation", "takeover_generation")
        incompatible_support = any(
            identity != current.observation_id and (current_entry is None or identity not in self._bindings or
                any(getattr(self._bindings[identity][1], field) != getattr(current_entry[1], field)
                    for field in authority_fields)) for identity in data["sources"])
        missing_native_rows = (data["skill_kind"] == "menu" and data["perception"] is None
                               and not MenuSkill.supports_native_rows(observed))
        with self._metadata:
            phase = self._prompt_phase
        item_control_reason = None if phase is None else self._item_control_reason(data,
            self._ledger.request(phase.root_id)["request"],
            self._store.observation(phase.checkpoint)["category"], phase.quantity_editor)
        lifecycle_control_reason = self._registered_lifecycle.draft_rejection_reason(data)
        if (not obsolete_selection and not metadata_mismatch and not incompatible_support
                and not missing_native_rows and item_control_reason is None and lifecycle_control_reason is None):
            return None

        # A bad extra source must not conceal loss of another retained source,
        # including historical evidence whose live binding has been cleared.
        retained = {ref.observation_id: ref for ref in self._store.historical_references}
        for identity in data["sources"]:
            if identity in retained and self._store.source_status(retained[identity]) != "retained":
                raise EvidenceError("Inconsistent request cannot bypass disputed supporting evidence")
        self._check_cancelled(work)
        ledger = self._ledger.snapshot(now=self._wall())
        counts = self._ledger.measured_counts()["primitives"]
        if (ledger["phase"] != "active" or ledger["unreconciled"] or not ledger["clock_valid"]
                or any(counts["by_state"].get(state, 0) for state in ("prepared", "published"))):
            raise LedgerError("Inconsistent request cannot bypass unsettled or inactive mission authority")
        if self._game_cost is not None and self._game_cost >= self._admission.limits.game_seconds:
            raise BudgetError("Mission game-time ceiling exhausted")
        if (ledger["remaining_inputs"] <= self._admission.cleanup_reserve.inputs
                or counts["charged"] >= self._admission.limits.primitive_mappings):
            raise BudgetError("Input budget or cleanup reserve exhausted")
        self._deadline(work, current)
        self._capacity(frames=2, byte_count=2 * MAX_FRAME_BYTES)
        root_id = data["phase_id"]
        if root_id is not None:
            root = self._ledger.request(root_id)
            with self._ledger._mutex:
                if self._ledger._phase_primitive_count(root_id) >= root["request"]["limits"]["primitives"]:
                    raise BudgetError("Phase primitive limit exhausted")

        if self._registered_lifecycle.phase is not None:
            phase = self._registered_lifecycle.phase
            if root_id != phase.root_id or data["work_id"] is not None or self._lease is None:
                return None
            self._registered_lifecycle.guard(work, phase)
            self._check_lease()
        elif self._exit_phase is not None:
            phase = self._exit_phase
            if root_id != phase.root_id or data["skill_kind"] not in ("menu", "direct") or self._lease is None:
                return None
            self._exit_guard(work, phase)
            self._check_lease()
        elif self._registered_activity.phase is not None:
            phase = self._registered_activity.phase
            if (data["skill_kind"] != "activity" or root_id != phase.prompt.root_id
                    or phase.needs_observation or phase.checkpoint != current):
                return None
            self._registered_activity.guard(work, phase)
        else:
            # Guard only: never dispatch this projection or rewrite the retained
            # request. The corrected new request must pass every ordinary guard.
            self._informing({**data, "sources": [current.observation_id]})
            self._prompt_authority_guard(data, current)
            work.game_anchor = current if current.boundary_kind == "normal_play" else self._last_normal()
            self._dispatch_authority_guard(work, current)
        actual = self._live()[0]
        self._capture_custody(observed, actual)
        image_informed = (data["skill_kind"] == "direct" or missing_native_rows or item_control_reason is not None
            or data["perception"] is not None or self._registered_lifecycle.phase is not None
            or self._exit_phase is not None or self._registered_activity.phase is not None
            or data["skill_kind"] == "activity" and data["goal"]["step"] in ("interrupt", "answer_interrupt", "resume"))
        if (not same_native_state(actual, observed)
                or image_informed and self.controller._frame_sha256(actual) != current.frame_sha256):
            if not self._ordinary_refusal_guard(work, current):
                raise EvidenceError("Inconsistent specialized request lost its exact native source")
            raise MissionInputRefusal("Native view changed during draft validation; Observe before correcting the request",
                                      status="rejected")
        self._check_cancelled(work)
        reasons = []
        if obsolete_selection:
            reasons.append("The selected informing source has been superseded by another recorded observation. "
                           "Collect any original unfinished input, then inspect and explicitly select current evidence.")
        if incompatible_support:
            reasons.append("Additional informing sources do not belong to the current actor and authority; "
                           "historical support belongs in memory.")
        if metadata_mismatch:
            reasons.append("Skill request session, revision or boundary differs from its cited immutable source.")
        if missing_native_rows:
            reasons.append("This source has no supported native UILIST row representation. "
                           "Supply an explicit source-bound visible-control interpretation for the observed UI.")
        if item_control_reason is not None:
            reasons.append(item_control_reason + ".")
        if lifecycle_control_reason is not None:
            reasons.append(lifecycle_control_reason + ".")
        reason = " ".join(reasons) + " "
        return {"reason": reason +
                    "No input or refresh was attempted; read the source and submit a new corrected request ID.",
                "source_ids": [current.observation_id], "proposals": 0, "grants_authority": False}

    def _deadline(self, work: _Work, original: EvidenceRef) -> float:
        operation = self._ledger.request(work.request["request_id"])
        wall_deadline = min(operation["deadline"], self._mission_deadline - self._admission.cleanup_reserve.wall_seconds)
        deadline = self._clock() + wall_deadline - self._wall()
        # Control requests use their original ledger admission, capped by the
        # parent/mission. Source first-seen time is evidence freshness, not a
        # new child's execution start. Keep navigation's existing passive
        # source-origin allowance; its continuation never renews that origin.
        if work.request["kind"] == "skill" and work.request["skill_kind"] == "navigate":
            deadline = min(deadline, original.received_monotonic + work.request["limits"]["wall_seconds"])
        if deadline <= self._clock():
            if self._wall() < self._mission_deadline - self._admission.cleanup_reserve.wall_seconds:
                raise LocalBudgetRefusal("Original operation deadline exhausted")
            raise BudgetError("Original operation/mission deadline exhausted")
        return deadline

    def _envelope(self, raw: dict, work: _Work, proposal: MissionIntent | _ResumeIntent,
                  preflight: EvidenceRef | None, *, image_informed: bool,
                  preflight_observation: dict | None) -> tuple[str, str]:
        fields = {"logical_action_id", "request", "result", "published", "received_monotonic", "preflight", "processing_error"}
        if type(raw) is not dict or set(raw) != fields or raw["logical_action_id"] != proposal.logical_id or type(raw["published"]) is not bool:
            raise ContractError("Malformed exact mission receipt envelope")
        if raw["processing_error"] is not None and (type(raw["processing_error"]) is not str
                or len(raw["processing_error"]) > 1024):
            raise ContractError("Malformed mission processing diagnostic")
        request, result = raw["request"], raw["result"]
        if type(result) is not dict:
            raise ContractError("Mission receipt lacks terminal result")
        if request is None:
            if raw["published"]:
                raise ContractError("Published receipt lost native request identity")
        else:
            self.controller._validate_stored_request(request)
            actual = preflight_observation if proposal.kind == "direct" else None
            if proposal.kind == "direct" and actual is None:
                raise ContractError("Ordinary publication lost its actual final preflight")
            expected = {"kind": proposal.kind,
                "session": actual["session"] if actual is not None else proposal.before.session,
                "revision": actual["revision"] if actual is not None else proposal.before.revision,
                "boundary_id": actual["boundary"]["id"] if actual is not None else proposal.expected_boundary_id}
            if proposal.kind != "resume":
                expected["input" if proposal.kind == "direct" else proposal.kind] = proposal.action
            if any(request.get(key) != value for key, value in expected.items()) or not isinstance(request.get("id"), str):
                raise ContractError("Mission native request does not correlate with logical proposal")
            if request.get("require_exact_frame") is not image_informed:
                raise ContractError("Mission native request contradicts the admitted image policy")
            if str(UUID(request["id"])) != request["id"]:
                raise ContractError("Malformed native request UUID")
            if (raw["published"] or result.get("id") is not None) and result.get("id") != request["id"]:
                raise ContractError("Mission native result identity differs")
        if raw["preflight"] is not None:
            proof = raw["preflight"]
            proof_fields = {"observation", "received_monotonic", "expected_image_sha256"}
            if proposal.kind == "direct":
                proof_fields.add("informing")
            if type(proof) is not dict or set(proof) != proof_fields:
                raise ContractError("Malformed mission preflight receipt")
            if proposal.kind == "direct" and proof["informing"] != dict(expected_session=proposal.before.session,
                    expected_revision=proposal.before.revision, expected_boundary_id=proposal.expected_boundary_id):
                raise ContractError("Ordinary preflight lost its immutable entry binding")
            if proof["expected_image_sha256"] != (proposal.before.frame_sha256 if image_informed else None):
                raise ContractError("Mission preflight hash contradicts the admitted image policy")
            validate_state(proof["observation"])
            if request is not None and request.get("frame") != proof["observation"]["frame"]:
                raise ContractError("Native request frame differs from its final preflight")
            proof_time = proof["received_monotonic"]
            if (type(proof_time) not in (int, float) or not math.isfinite(proof_time)
                    or proof_time < 0 or proof_time > self._clock()):
                raise ContractError("Preflight receipt lacks its original finite clock")
            # Controller checks freshness at publication. A terminal timeout can
            # arrive later than that window; it cannot invalidate the historical
            # preflight correlation or renew the source for another input.
            if preflight is None:
                if request is not None or raw["published"]:
                    raise ContractError("Published input lacks retained preflight source")
            elif (preflight.received_monotonic != proof_time
                    or raw["published"] and preflight_observation != proof["observation"]):
                raise ContractError("Preflight receipt differs from actual retained source")
        elif request is not None:
            raise ContractError("Native request lacks retained final preflight")
        received = raw["received_monotonic"]
        if received is not None and (type(received) not in (int, float) or not math.isfinite(received)
                or not 0 <= received <= self._clock() or preflight is not None and received < preflight.received_monotonic):
            raise ContractError("Invalid original terminal receipt time")
        if not raw["published"]:
            if (result.get("status") in ("ready", "dispatched") or request is not None
                    and (received is not None or result.get("status") == "rejected")):
                raise ContractError("Unpublished flag contradicts the correlated native terminal receipt")
            return "not_dispatched", str(result.get("error") or "Proven unpublished input")[:1024]
        if result.get("status") == "rejected":
            validate_state(result, request["id"])
            if received is None:
                raise ContractError("Native rejection lacks terminal receipt clock")
            return "rejected", str(result.get("error") or "Native rejected input")[:1024]
        if result.get("status") == "ready":
            validate_state(result, request["id"])
            if (received is None or result["session"] != request["session"]
                    or result["revision"] <= request["revision"]):
                raise ContractError("Ready receipt lacks exact advanced same-session source")
            return "returned", "Correlated terminal ready ACK; current eligibility and semantic effect are separate"
        return "unknown", str(result.get("error") or "Input acknowledgment is unresolved")[:1024]

    def _dispatch(self, work: _Work, proposal: MissionIntent | _ResumeIntent | ActivityIntent, original: EvidenceRef,
                  *, lifecycle: _ExitPhase | NormalPhase | HandoffPhase | None = None,
                  activity: ActivityPhase | None = None) -> PrimitiveResult | ActivityFeedback:
        reservation = None
        preflight_source = None
        preflight_observation = None
        prepared = False
        prepared_intent = None
        after = None
        raw = None
        disposition, reason = "not_dispatched", "Dispatch not admitted"
        envelope_valid = False
        native_ack = None
        processing_error = None
        processing_fatal = False
        evidence_loss = None
        current_error = None
        game_budget_exhausted = False
        local_nonpublication = False
        operator_mark = self._operator_mark()
        dispatch_actor = self._ledger.snapshot(now=self._wall())["player_id"]
        takeover_generation = self._store.observation(proposal.before)["takeover_generation"]
        game_anchor = (activity.prompt.game_anchor if activity is not None else
                       self._registered_recovery.continuation.game_anchor if self._registered_recovery.continuation is not None else
                       self._prompt_phase.game_anchor if self._prompt_phase is not None else original)
        control = isinstance(proposal, ActivityIntent)
        ordinary = proposal.kind == "direct"
        lifecycle_image = lifecycle is not None and not (
            isinstance(lifecycle, NormalPhase)
            and self._registered_lifecycle.source_rule(lifecycle) == "native_state")
        image_informed = not ordinary and (work.request.get("perception") is not None
                          or lifecycle_image or activity is not None)
        rule = "ordinary_input" if ordinary else "exact_png_bytes" if image_informed else "native_state"
        def unpublished_refusal() -> str | None:
            nonlocal local_nonpublication
            if lifecycle is not None or activity is not None:
                return None
            local = self._local_input_refusal(work, proposal.before, proposal.logical_id, command_work=1)
            local_nonpublication = local is not None
            return local

        def guard() -> None:
            nonlocal game_budget_exhausted
            # Check every input lane. Startup/provisional identity has no
            # canonical game clock yet; ending adopted work needs headroom.
            if self._game_cost is not None and self._game_cost >= self._admission.limits.game_seconds:
                game_budget_exhausted = True
                raise BudgetError("Mission game-time ceiling exhausted")
            if activity is not None:
                self._registered_activity.guard(work, activity, proposal)
            elif lifecycle is None:
                self._dispatch_guard(work, proposal.before)
            elif isinstance(lifecycle, NormalPhase):
                self._registered_lifecycle.guard(work, lifecycle, proposal)
            elif isinstance(lifecycle, HandoffPhase):
                self._registered_handoff.guard(work, lifecycle, proposal)
            elif isinstance(lifecycle, RecoveryPhase):
                self._registered_recovery.guard(work, lifecycle, proposal)
            else:
                self._exit_guard(work, lifecycle, proposal)
        def checked_preflight(observed: dict, received: float) -> None:
            nonlocal reservation, preflight_source, preflight_observation, prepared, prepared_intent
            guard()
            self._capacity(frames=2, byte_count=2 * MAX_FRAME_BYTES)
            inapplicable = (lifecycle is None and activity is None and not ordinary
                and not same_native_state(self._store.observation(proposal.before), observed))
            if inapplicable:
                self._capture_custody(self._store.observation(proposal.before), observed)
            preflight_source = self._store.retain_preflight(observed,
                received_monotonic=received, rule="ordinary_input" if inapplicable else rule, **self._clocks())
            if (preflight_source == proposal.before or preflight_source.received_monotonic != received
                    or self._store.observation(preflight_source) != observed):
                raise EvidenceError("Preflight retention must attest its actual distinct source and original receipt")
            preflight_observation = copy.deepcopy(observed)
            guard()
            if inapplicable:
                # This custody-only source is refusal evidence, never a weaker
                # semantic preflight. Return before reservation or preparation.
                if not self._ordinary_refusal_guard(work, proposal.before, command_work=1):
                    raise ControlError("Semantic refusal lacks ordinary custody")
                raise MissionInputRefusal("Semantic intent is not applicable to the actual preflight; Observe and choose again",
                                          status="rejected")
            self._capacity()
            reservation = self._store.reserve_dispatch(proposal.before, preflight=preflight_source, rule=rule, **self._clocks())
            actual = self._store.observation(preflight_source) if ordinary else None
            intent = {"kind": proposal.kind, "value": proposal.action,
                "expected_session": actual["session"] if actual is not None else proposal.before.session,
                "expected_revision": actual["revision"] if actual is not None else proposal.before.revision,
                "expected_boundary_id": actual["boundary"]["id"] if actual is not None else proposal.expected_boundary_id,
                "source_before": proposal.before.observation_id,
                "preflight_source": preflight_source.observation_id,
                "revalidation": None if proposal.revalidation is None else proposal.revalidation.to_dict(),
                "input_observation": (proposal.input_observation.to_dict() if isinstance(proposal, ControlIntent)
                                      and proposal.input_observation is not None else None),
                "reservation_id": reservation.token}
            prepared_intent = intent
            self._ledger.prepare_primitive(work.request["request_id"], proposal.logical_id, intent, now=self._wall())
            prepared = True
            self._cache_operation(self._ledger.request(work.request["request_id"]))
            guard()
            self._store.verify(proposal.before)
            self._store.verify(preflight_source)

        def preflight(observed: dict, received: float) -> None:
            try:
                checked_preflight(observed, received)
            except FreshnessError as exc:
                self._record("mission_preflight_freshness", dict(request_id=work.request["request_id"],
                    logical_action_id=proposal.logical_id, **exc.details, grants_authority=False))
                # An aged semantic entry cannot authorize input. When its
                # distinct actual preflight was already retained and nothing
                # prepared, refuse this shortcut through the existing controller
                # health checks; preserve only explicit Observe/redecision.
                if (lifecycle is None and activity is None and not ordinary
                        and reservation is None and not prepared and preflight_source is not None
                        and exc.details["source_id"] == proposal.before.observation_id
                        and exc.details["failures"]
                        and set(exc.details["failures"]) <= {"wall_age", "receipt_age"}
                        and self._ordinary_refusal_guard(work, proposal.before, command_work=1)):
                    raise MissionInputRefusal("Semantic entry expired before publication; Observe and choose again",
                                              status="rejected") from exc
                raise

        def bounded_preflight(observed: dict, received: float) -> None:
            try:
                preflight(observed, received)
            except LocalBudgetRefusal:
                local = unpublished_refusal()
                if local is None:
                    raise
                raise MissionInputRefusal(local) from None
        try:
            guard()
            deadline = self._deadline(work, proposal.before if lifecycle is not None or activity is not None else original)
            self._publish()
            if control:
                observed = self._store.observation(proposal.before)
                raw = self.controller.recover_mission(proposal.kind, expected_generation=activity.generation,
                    expected_operator_generation=activity.operator_mark[1], expected_controller_boot_id=activity.operator_mark[0],
                    expected_session=proposal.before.session, expected_revision=proposal.before.revision,
                    expected_boundary_id=proposal.expected_boundary_id, expected_takeover_generation=activity.takeover_generation,
                    expected_pause_origin=observed["pause_origin"], expected_control_generation=proposal.control_generation,
                    logical_action_id=proposal.logical_id, deadline_monotonic=deadline, preflight=preflight,
                    expected_image_sha256=proposal.before.frame_sha256, **(proposal.action or {}))
            elif isinstance(proposal, _ResumeIntent) and (lifecycle is not None or activity is not None):
                with self.controller.data_lock:
                    generation = self.controller.pause_generation
                observed = self._store.observation(proposal.before)
                context = activity or lifecycle
                mark = context.operator_mark if isinstance(context, (HandoffPhase, ActivityPhase, RecoveryPhase)) else context.launch.operator_mark
                takeover = context.takeover_generation if isinstance(context, (HandoffPhase, ActivityPhase, RecoveryPhase)) else context.launch.takeover_generation
                raw = self.controller.resume_mission(expected_generation=generation,
                    expected_operator_generation=mark[1],
                    expected_controller_boot_id=mark[0],
                    expected_takeover_generation=takeover,
                    expected_pause_origin=observed["pause_origin"], expected_session=proposal.before.session,
                    expected_revision=proposal.before.revision, expected_boundary_id=proposal.expected_boundary_id,
                    logical_action_id=proposal.logical_id, deadline_monotonic=deadline, preflight=preflight,
                    expected_image_sha256=proposal.before.frame_sha256 if image_informed else None)
            else:
                raw = self.controller.execute_mission(self._lease, kind=proposal.kind, value=proposal.action,
                    expected_session=proposal.before.session, expected_revision=proposal.before.revision,
                    expected_boundary_id=proposal.expected_boundary_id, logical_action_id=proposal.logical_id,
                    deadline_monotonic=deadline, preflight=bounded_preflight,
                    unpublished_refusal=unpublished_refusal if lifecycle is None else None,
                    expected_image_sha256=proposal.before.frame_sha256 if image_informed else None)
            if not prepared:
                prepared = any(row["logical_id"] == proposal.logical_id for row in self._ledger.primitive_records())
            disposition, reason = (self._registered_activity.envelope(raw, proposal, preflight_source,
                preflight_observation=preflight_observation, takeover_generation=takeover_generation) if control else
                self._envelope(raw, work, proposal, preflight_source, image_informed=image_informed,
                    preflight_observation=preflight_observation))
            envelope_valid = True
            if (disposition == "not_dispatched" and lifecycle is None and activity is None
                    and raw["result"].get("status") == "rejected" and preflight_source is None):
                # Early image/geometry refusals precede the callback. Preserve
                # their actual captured proof without promoting current or
                # preparing a semantic input under a custody-only rule.
                if not self._ordinary_refusal_guard(work, proposal.before, proposal.logical_id):
                    raise ControlError("Unpublished refusal lacks ordinary custody")
                proof = raw["preflight"]
                if proof is None:
                    raise EvidenceError("Unpublished refusal lacks an actual preflight")
                self._capacity()
                preflight_observation = copy.deepcopy(proof["observation"])
                preflight_source = self._store.retain_preflight(preflight_observation,
                    received_monotonic=proof["received_monotonic"], rule="ordinary_input", **self._clocks())
            processing_error = raw["processing_error"]
            processing_fatal = processing_error is not None
            if not control and disposition in ("returned", "rejected"):
                native_ack = compact_native_ack(raw["result"])
            if raw["published"]:
                try:
                    self._ledger.published(proposal.logical_id, raw["request"]["id"], now=self._wall())
                except Exception as exc:
                    if disposition not in ("returned", "rejected"):
                        raise
                    # The mandatory known settlement below can atomically
                    # repair this row state; no extra recovery if it commits.
                    processing_error = ((processing_error + "; " if processing_error else "")
                        + f"Publication bookkeeping: {type(exc).__name__}: {exc}")[:1024]
                # Publication is transport custody, not evidence that an input
                # reached the game. An authenticated native rejection committed
                # no input and cannot create an uncertain transition candidate.
                if disposition != "rejected":
                    if isinstance(lifecycle, NormalPhase):
                        self._registered_lifecycle.published(lifecycle, proposal, raw["request"], reservation)
                    elif isinstance(lifecycle, _ExitPhase) and proposal.kind != "resume":
                        self._exit_candidate = (lifecycle, proposal.logical_id, copy.deepcopy(raw["request"]), reservation)
            native_after = raw["result"].get("state") if control else raw["result"]
            if disposition == "returned" and (not control or native_after.get("frame_ok") and native_after.get("status") == "ready"):
                # Delivery has already been authenticated. Archival retention
                # must neither require freshness nor promote this ACK to current.
                after = self._store.retain_terminal(native_after, received_monotonic=raw["received_monotonic"],
                    reservation=reservation, **self._clocks())
                reservation = None
                if self._exit_candidate is not None and self._exit_candidate[1] == proposal.logical_id:
                    self._exit_candidate = (*self._exit_candidate[:3], None)
                candidate = self._registered_lifecycle.candidate
                if candidate is not None and candidate.logical_id == proposal.logical_id:
                    self._registered_lifecycle.candidate = replace(candidate, reservation=None)
        except Exception as exc:
            if (isinstance(exc, LocalBudgetRefusal) and raw is None and not prepared
                    and lifecycle is None and activity is None):
                # No controller input call/prepared intent exists at this point.
                # Any failed health proof still propagates to the fatal path.
                local_nonpublication = self._local_input_refusal(work, proposal.before, proposal.logical_id) is not None
            if not (envelope_valid and disposition in ("returned", "rejected")):
                disposition = "unknown" if raw is not None and (not envelope_valid or raw.get("published")) or prepared and raw is None else "not_dispatched"
            elif disposition == "returned" and after is None:
                evidence_loss = f"{type(exc).__name__}: {exc}"[:1024]
            else:
                processing_error = f"{type(exc).__name__}: {exc}"[:1024]
                processing_fatal = True
            reason = f"{type(exc).__name__}: {exc}"[:1024]
            # An exception from execute_mission may occur after input publication.
            if prepared and raw is None:
                disposition = "unknown"
        if raw is not None and (type(raw) is not dict or set(raw) != {
                "logical_action_id", "request", "result", "published", "received_monotonic", "preflight", "processing_error"}):
            disposition = "unknown"
        if reservation is not None and disposition != "unknown":
            try:
                self._store.release(reservation)
                candidate = self._registered_lifecycle.candidate
                if candidate is not None and candidate.logical_id == proposal.logical_id:
                    self._registered_lifecycle.candidate = replace(candidate, reservation=None)
                reservation = None
            except Exception as exc:
                processing_error = f"Reservation release: {type(exc).__name__}: {exc}"[:1024]
                processing_fatal = True
        # Preserve correlation from the prepared admission itself. A subsequent
        # archive failure may make even a preflight reread unavailable.
        actual_preflight = prepared_intent if ordinary else None
        receipt = {"logical_action_id": proposal.logical_id,
            "native_request_id": raw["request"].get("id") if envelope_valid and type(raw.get("request")) is dict
                and (not control or raw["published"]) else None,
            "kind": proposal.kind, "value": proposal.action,
            "expected_session": actual_preflight["expected_session"] if actual_preflight is not None else proposal.before.session,
            "expected_revision": actual_preflight["expected_revision"] if actual_preflight is not None else proposal.before.revision,
            "expected_boundary_id": actual_preflight["expected_boundary_id"] if actual_preflight is not None else proposal.expected_boundary_id,
            "published": raw.get("published") is True if type(raw) is dict else False,
            "native_request_json": canonical(raw["request"]) if envelope_valid and raw.get("published") is True else None,
            "dispatch_binding": dict(controller_boot_id=operator_mark[0], operator_pause_generation=operator_mark[1],
                takeover_generation=takeover_generation, actor_id=dispatch_actor, epoch=work.request["epoch"],
                game_anchor_source_id=game_anchor.observation_id),
            "transport_disposition": disposition, "source_before": proposal.before.observation_id,
            "preflight_source": None if preflight_source is None else preflight_source.observation_id,
            "source_after": None if after is None else after.observation_id,
            "received_monotonic": raw.get("received_monotonic") if envelope_valid and
                type(raw.get("received_monotonic")) in (int, float) and math.isfinite(raw["received_monotonic"]) else None,
            "native_ack": native_ack, "processing_error": processing_error, "evidence_loss": evidence_loss,
            "reason": reason}
        if control and envelope_valid:
            receipt["control"] = {"request": copy.deepcopy(raw["request"]), "result": copy.deepcopy(raw["result"])}
        # Unknown settlement must preserve an already recorded user Pause.
        # Known delivery is durable before fallible Pause/publication work.
        known = envelope_valid and disposition in ("returned", "rejected")
        if not known:
            self._apply_pauses()
        if prepared:
            self._ledger.settle_primitive(proposal.logical_id, disposition, receipt, now=self._wall())
        self._last_receipt = receipt
        self._apply_pauses()
        if known and (processing_fatal or evidence_loss is not None):
            self._stop_after_failure(processing_error or evidence_loss)
        elif known and after is not None:
            # Current authority comes from an independent snapshot and its
            # original receipt clock, never from a historical ACK's existence.
            try:
                state, received = self.controller.observation_snapshot()
                unavailable = "Current snapshot is absent" if state is None and received is None else None
                if unavailable is None:
                    validate_state(state)
                    if (state["session"] != after.session
                            or state["takeover_generation"] != takeover_generation
                            or state["boundary"]["control_generation"] != native_after["boundary"]["control_generation"]):
                        raise EvidenceError("Current snapshot crossed the dispatch session, native control or takeover custody")
                    if (type(received) not in (int, float) or not math.isfinite(received)
                            or received > self._clock() or self._wall() * 1000 - state["timestamp_ms"] < -1000):
                        raise EvidenceError("Current snapshot lacks its original finite clock continuity")
                    if (self._clock() - received > MAX_AGE_SECONDS
                            or self._wall() * 1000 - state["timestamp_ms"] > MAX_AGE_SECONDS * 1000):
                        unavailable = "Current snapshot is stale"
                if unavailable is not None:
                    if not ordinary or lifecycle is not None or activity is not None:
                        raise EvidenceError(unavailable)
                    self._await_current_observation(work, proposal.before, original, operator_mark, unavailable)
                else:
                    # A genuinely different current capture consumes its own slot.
                    if state["frame"] != native_after["frame"]:
                        self._capacity()
                    current = self._ingest(state, received)
                    live = self._live()
                    authoritative = (live[3] is self._lease and self._lease is not None and not live[4]
                        and not work.cancelled.is_set() and current.boundary_kind in ("normal_play", "menu"))
                    if isinstance(lifecycle, NormalPhase):
                        candidate = self._registered_lifecycle.candidate
                        if (candidate is not None and candidate.diagnostic_only
                                and current.boundary_kind == "normal_play" and candidate.phase.first_normal is None):
                            self._registered_lifecycle.retain_diagnostic(current)
                        else:
                            self._registered_lifecycle.retain_after(current)
                        self._registered_lifecycle.returned(proposal.logical_id, current)
                    else:
                        self._publish_source(current, authoritative=authoritative)
                    if current != after:
                        self._record("mission_post_dispatch_current", {"logical_action_id": proposal.logical_id,
                            "source_after": after.observation_id, "source_current": current.observation_id,
                            "grants_authority": False})
            except Exception as exc:
                # The immutable terminal receipt remains known and unchanged.
                current_error = f"Current observation unavailable after known ACK: {type(exc).__name__}: {exc}"[:1024]
                self._stop_after_failure(current_error)
        typed_refusal = (envelope_valid and not control and lifecycle is None and activity is None
                         and not raw["published"] and raw["result"].get("status") == "rejected")
        if (ordinary and envelope_valid and disposition == "rejected" and raw["published"] and prepared
                and after is None and lifecycle is None and activity is None
                and not processing_fatal and evidence_loss is None):
            # An authenticated native refusal settled no input, but the lease
            # rotation already happened. Preserve only read-only lineage after
            # re-proving healthy custody; never retry or manufacture an ACK frame.
            if self._ordinary_refusal_guard(work, proposal.before, proposal.logical_id):
                self._await_current_observation(work, proposal.before, original, operator_mark, reason)
        if (ordinary and envelope_valid or local_nonpublication or typed_refusal) and disposition == "not_dispatched":
            live = self._live()
            if processing_fatal or evidence_loss is not None:
                self._stop_after_failure(processing_error or evidence_loss)
            elif self._lease is not None and live[3] is self._lease and not live[4]:
                if typed_refusal:
                    self._unpublished_refusal_guard(work, proposal.before, proposal.logical_id, raw, preflight_source)
                # Rotation is already committed even when this first input was
                # not published. Preserve only authenticated read-only lineage
                # until Observe, never an old binding for another input.
                if lifecycle is None:
                    self._await_current_observation(work, proposal.before, original, operator_mark, reason)
        live = self._live()
        if game_budget_exhausted:
            # Keep revocation outside controller preflight and after any
            # reserved intent has been settled.
            self._stop_after_failure(reason)
        elif disposition != "unknown" and (activity is None or disposition != "returned") and (live[3] is not self._lease or live[4]):
            self._stop_after_failure(reason)
        if disposition == "unknown":
            # Settlement owns the unknown epoch transition. Do not advance it again
            # or replace an already recorded user/takeover Pause with a late receipt.
            self._stop_unknown_policy()
            if lifecycle is None and prepared and envelope_valid:
                self._registered_recovery.remember(work, proposal, raw, reservation,
                    operator_mark=operator_mark, takeover_generation=takeover_generation, game_anchor=game_anchor)
        if control:
            return ActivityFeedback(proposal.before, after, disposition, reason, raw)
        if disposition == "returned" and after is None:
            raise EvidenceError("Known returned delivery settled without after evidence: " + (evidence_loss or "Capture unavailable"))
        if known and (processing_fatal or evidence_loss is not None or current_error is not None):
            raise EvidenceError("Known delivery settled before processing stopped: " + (processing_error or evidence_loss or current_error))
        displacement = None if (after is None or after.session != proposal.before.session
            or after.boundary_kind != "normal_play" or proposal.before.boundary_kind != "normal_play") else tuple(
            b - a for a, b in zip(self._store.position(proposal.before), self._store.position(after)))
        return PrimitiveResult(proposal.logical_id, proposal.before, after, disposition, displacement, reason)

    @staticmethod
    def _navigation_result(outcome: NavigationOutcome) -> dict:
        result = {"disposition": outcome.disposition, "reason": outcome.reason[:1024],
            "verified_steps": outcome.verified_steps, "proposals": outcome.proposed_count,
            "position": None if outcome.position is None else list(outcome.position),
            "source_ids": list(dict.fromkeys(ref.observation_id for ref in outcome.evidence)),
            "pending_logical_id": outcome.pending_logical_id,
            "revalidation": None if outcome.revalidation is None else outcome.revalidation.to_dict(),
            "grants_authority": False}
        if len(canonical(result).encode()) > 65_536:
            raise LedgerError("Semantic navigation result exceeds durable receipt ceiling")
        return result

    @staticmethod
    def _control_result(outcome: MenuOutcome | ControlOutcome) -> dict:
        return {"disposition": outcome.disposition, "reason": outcome.reason[:1024],
            "proposals": outcome.proposed_count, "source_ids": list(dict.fromkeys(ref.observation_id for ref in outcome.evidence)),
            "pending_logical_id": outcome.pending_logical_id, "verification_required": outcome.verification_required,
            "basis": "native_rows" if isinstance(outcome, MenuOutcome) else outcome.basis,
            "verified_focus_steps": outcome.verified_focus_steps if isinstance(outcome, MenuOutcome) else None,
            "revalidation": None if outcome.revalidation is None else outcome.revalidation.to_dict(),
            "input_observation": (outcome.input_observation.to_dict() if isinstance(outcome, ControlOutcome)
                                  and outcome.input_observation is not None else None),
            "grants_authority": False}

    def _applicability_refusal(self, work: _Work, original: EvidenceRef,
                              current: EvidenceRef, mark: tuple[str, int]) -> tuple[str, dict]:
        """A verified refresh invalidated this intent, not observation custody."""
        if self._operator_mark() != mark:
            raise ControlError("Applicability refusal crossed operator Pause")
        phase = self._prompt_phase
        advanced = self._advance_prompt(work, original, current, observed_only=True) if phase is not None else None
        if not self._ordinary_refusal_guard(work, current):
            raise EvidenceError("Applicability refusal cannot replace specialized authority")
        result = {"disposition": "blocked", "reason": "Fresh evidence does not support this semantic intent; inspect it and choose again",
            "source_ids": list(dict.fromkeys((original.observation_id, current.observation_id))),
            "proposals": 0, "verification_required": False, "grants_authority": False}
        if advanced is not None:
            result["phase"] = self._prompt_receipt(advanced,
                "complete" if current.boundary_kind == "normal_play" else "awaiting_control")
        self._capture_memory(current)
        self._record("mission_applicability_refusal", result)
        return "blocked", result

    def _semantic(self, work: _Work) -> tuple[str, dict]:
        with ExitStack() as stack:
            return self._semantic_run(work, stack)

    def _semantic_run(self, work: _Work, stack: ExitStack) -> tuple[str, dict]:
        data = work.request
        original, binding = self._informing(data)
        phase = self._prompt_guard(data, original)
        work.game_anchor = original if original.boundary_kind == "normal_play" else self._last_normal()
        deadline = self._deadline(work, original)
        if data["skill_kind"] == "program":
            selected = self._memory.select_procedure(data["procedure"])
            if selected["program"] is None:
                return "blocked", {"reason": "Selected procedure has no executable program; choose ordinary input or another revision",
                    "proposals": 0, "source_ids": list(data["sources"]), "grants_authority": False}
            skill = ProgramInputSkill(data, deadline_monotonic=deadline,
                source=selected["program"]["source"],
                on_step=lambda value: self._record("mission_program_step", {
                    "request_id": data["request_id"], "procedure": data["procedure"], **value}))
            stack.callback(skill.close)
        else:
            skill = (OrdinaryInputSkill(data, deadline_monotonic=deadline) if data["skill_kind"] in ("direct", "program") else
                     MenuSkill(data, deadline_monotonic=deadline) if data["skill_kind"] == "menu" and data["perception"] is None
                     else SemanticControlSkill(data, deadline_monotonic=deadline))
        self._skill = data["skill_kind"]
        mark = self._operator_mark()
        inspected, _ = self._store.inspect_current_boundary(**self._clocks())
        if inspected != original:
            raise EvidenceError("Control informing source is no longer the exact retained checkpoint")
        self._store.verify(original)
        self._capacity()
        state, received = self._observe_native(work, deadline_monotonic=self._deadline(work, original))
        current = self._ingest(state, received)
        refreshed = self._binding(current)
        if data["skill_kind"] in ("direct", "program"):
            relation = InputObservation(binding, refreshed)
            skill.observe(relation, self._store, **self._clocks())
            self._record("mission_input_observation", relation.to_dict())
        else:
            rule = "exact_png_bytes" if data["perception"] is not None else "native_state"
            if not self._store.equivalent(original, current, rule=rule):
                self._publish_source(current, authoritative=True)
                return self._applicability_refusal(work, original, current, mark)
            relation = SourceRevalidation(binding, refreshed,
                rule)
            skill.revalidate(relation, self._store, **self._clocks())
            self._record("mission_revalidation", relation.to_dict())
        self._publish_source(current, authoritative=True)
        if phase is not None:
            phase = self._advance_prompt(work, original, current)
        self._capture_memory(self._current)
        rotated = False
        receipt_phase = phase
        proposed_count = 0
        last_returned = None
        while True:
            self._check_cancelled(work)
            proposal = skill.propose(self._store, **self._clocks())
            if isinstance(proposal, (MenuOutcome, ControlOutcome)):
                outcome = proposal
                # Program termination is a separate evaluation after known
                # input. Preserve that input's prompt owner and original macro
                # even when the program yields/errors before another proposal.
                if (isinstance(skill, ProgramInputSkill) and last_returned is not None
                        and self._prompt_phase is None and last_returned == self._current
                        and last_returned.boundary_kind in ("menu", "activity_poll")):
                    receipt_phase = self._open_prompt(work, original, last_returned, mark)
                    phase = self._prompt_phase
            else:
                refusal = self._exhausted_prompt_refusal(work)
                if refusal is not None:
                    disposition = "partial" if proposed_count else "blocked"
                    outcome = ControlOutcome(disposition, refusal["reason"], proposed_count,
                        tuple(dict.fromkeys((original, self._current))), None, proposed_count > 0,
                        "ordinary_input" if data["skill_kind"] in ("direct", "program") else
                        "native_rows" if isinstance(skill, MenuSkill) else "player_interpretation",
                        relation if isinstance(relation, SourceRevalidation) else None,
                        relation if isinstance(relation, InputObservation) else None)
                    self._capture_memory(self._current)
                    return disposition, {**self._control_result(outcome), **refusal,
                        **({"program": skill.summary()} if isinstance(skill, ProgramInputSkill) else {})}
                self._progress = {"pending_logical_id": proposal.logical_id, "source_before": proposal.before.observation_id}
                if not rotated:
                    self._rotate(work, proposal)
                    rotated = True
                proposed_count += 1
                feedback = self._dispatch(work, proposal, original)
                if isinstance(skill, ProgramInputSkill):
                    skill.record_feedback(feedback)
                if feedback.transport_disposition == "returned":
                    last_returned = feedback.after
                if work.cancelled.is_set() or self._closed.is_set():
                    return ("unknown" if feedback.transport_disposition == "unknown" else "paused"), {
                        "reason": "Authority revoked; actual control receipt retained", "source_ids": [
                            ref.observation_id for ref in (feedback.before, feedback.after) if ref is not None],
                        "pending_logical_id": proposal.logical_id, "grants_authority": False,
                        **({"program": skill.summary()} if isinstance(skill, ProgramInputSkill) else {})}
                pending_observation = (self._prompt_phase is not None
                    and self._prompt_phase.observation_generation is not None)
                actual_current, current_fresh = self._store.inspect_current_boundary(**self._clocks())
                live_changed = False
                if (feedback.transport_disposition == "returned" and actual_current is not None
                        and actual_current.boundary_kind in ("normal_play", "menu")):
                    observed = self._store.observation(actual_current)
                    live = self._live()[0]
                    self._capture_custody(observed, live)
                    live_changed = not same_native_state(observed, live)
                current_changed = (feedback.transport_disposition == "returned" and actual_current == self._current
                    and (live_changed or current_fresh and actual_current != feedback.after))
                if pending_observation:
                    receipt_phase = self._prompt_phase
                    if feedback.transport_disposition == "returned":
                        outcome = ControlOutcome("partial", "Known input returned; explicit Observe required before a new input decision",
                            proposed_count, tuple(dict.fromkeys((original, proposal.before, feedback.after))), None, True,
                            "ordinary_input", input_observation=relation if isinstance(relation, InputObservation) else None)
                    elif feedback.transport_disposition == "not_dispatched":
                        # _dispatch authenticated this read-only scope. Passive
                        # semantic attribution requires fresh current evidence;
                        # it cannot turn positively known nondelivery into an
                        # unknown input merely because the old entry aged.
                        outcome = ControlOutcome("partial" if proposed_count > 1 else "blocked", feedback.reason,
                            proposed_count, tuple(dict.fromkeys((*skill._sources, original, proposal.before))), None, proposed_count > 1,
                            "ordinary_input" if data["skill_kind"] in ("direct", "program") else
                            "native_rows" if isinstance(skill, MenuSkill) else "player_interpretation",
                            relation if isinstance(relation, SourceRevalidation) else None,
                            relation if isinstance(relation, InputObservation) else None)
                    else:
                        outcome = skill.accept(feedback, self._store, **self._clocks())
                elif current_changed:
                    # Delivery is known; a different actual current capture ends
                    # this operation without attributing its meaning or taking
                    # another focus/text step against the changed interface.
                    outcome = ControlOutcome("partial", "Known input returned; current capture changed and needs a new player decision",
                        proposed_count, tuple(dict.fromkeys((original, proposal.before, feedback.after, actual_current))),
                        None, True, "ordinary_input" if data["skill_kind"] in ("direct", "program") else
                        "native_rows" if isinstance(skill, MenuSkill) else "player_interpretation",
                        relation if isinstance(relation, SourceRevalidation) else None,
                        relation if isinstance(relation, InputObservation) else None)
                else:
                    outcome = skill.accept(feedback, self._store, **self._clocks())
                checkpoint = actual_current if current_changed else feedback.after
                if (not pending_observation and feedback.transport_disposition == "returned" and feedback.after is not None and phase is not None
                        and (outcome is None or outcome.disposition != "unknown")):
                    receipt_phase = self._advance_prompt(work, proposal.before, checkpoint, action=proposal.action,
                        observed_only=current_changed)
                    phase = self._prompt_phase
                if outcome is None:
                    self._publish()
                    continue
                if (not pending_observation and data["phase_id"] is None and data["skill_kind"] in ("interact", "item", "activity", "inspect", "direct", "program") and outcome.disposition == "partial"
                        and feedback.transport_disposition == "returned" and feedback.after is not None):
                    receipt_phase = self._open_prompt(work, original, checkpoint, mark)
                if live_changed and not pending_observation:
                    self._await_current_observation(work, checkpoint, original, mark,
                        "Native view advanced after the retained ACK; Observe before choosing another input")
                    receipt_phase = self._prompt_phase
            result = self._control_result(outcome)
            if isinstance(skill, ProgramInputSkill):
                result["program"] = skill.summary()
            if receipt_phase is not None:
                stage = ("unknown" if outcome.disposition == "unknown" else "awaiting_observation"
                    if receipt_phase.observation_generation is not None else "complete"
                    if receipt_phase.checkpoint.boundary_kind == "normal_play" else "activity_poll"
                    if receipt_phase.checkpoint.boundary_kind == "activity_poll" else "awaiting_control")
                result["phase"] = self._prompt_receipt(receipt_phase, stage)
            # Transport unknown already stopped in _dispatch and retained its
            # exact recovery generation. Only a new semantic uncertainty stops
            # here; another revoke would destroy that original custody binding.
            if outcome.disposition == "unknown" and self._lease is not None:
                self._stop_unknown_policy()
            try:
                if self._game_cost is None or self._game_cost >= self._admission.limits.game_seconds:
                    raise BudgetError("Observed mission game time unavailable or exceeded")
                self._game_guard(work.game_anchor, data["limits"]["game_seconds"], after=True)
                if receipt_phase is not None:
                    root = self._ledger.request(receipt_phase.root_id)["request"]
                    self._game_guard(receipt_phase.game_anchor, root["limits"]["game_seconds"], after=True)
            except _LocalGameLimit as exc:
                if outcome.disposition == "unknown":
                    # Unknown already revoked authority above; do not replace
                    # its original unknown epoch/cause with another Pause.
                    result["budget_stop"] = str(exc)
                    return "unknown", result
                else:
                    # Normal return ends this root; an owned menu awaits
                    # explicit Observe closure. Neither replenishes a limit.
                    result["macro_exhausted"] = "game_seconds"
                result.update(disposition="partial", reason=str(exc))
                return "partial", result
            except BudgetError as exc:
                result["budget_stop"] = str(exc)
                if outcome.disposition == "unknown":
                    return "unknown", result
                self._stop_after_failure(str(exc))
                result.update(disposition="partial", reason=str(exc))
                return "partial", result
            self._capture_memory(self._current)
            return outcome.disposition, result

    def _navigate(self, work: _Work) -> tuple[str, dict]:
        data = work.request
        original, binding = self._informing(data)
        continuation = self._registered_recovery.continuation
        anchor = original if continuation is None else continuation.game_anchor
        game_limit = (data["limits"]["game_seconds"] if continuation is None else
                      self._ledger.request(continuation.root_id)["request"]["limits"]["game_seconds"])
        work.game_anchor = anchor
        if self._map is None:
            raise EvidenceError("Navigation has no current observed map")
        skill = NavigationSkill(data, self._map)
        self._skill = "navigate"
        inspected, _ = self._store.inspect_current(**self._clocks())
        if inspected != original:
            raise EvidenceError("Informing source is no longer the current retained source")
        # Exactly one entry capture, even for a source near the freshness limit;
        # never mutate the original request/source age or renew its limits.
        self._store.verify(original)
        self._capacity()
        state, received = self._observe_native(work, deadline_monotonic=self._deadline(work, original))
        current = self._ingest(state, received)
        refreshed = self._publish_source(current, authoritative=True)
        if not self._store.equivalent(original, current, rule="native_state"):
            return self._applicability_refusal(work, original, current, self._operator_mark())
        relation = SourceRevalidation(binding, refreshed, "native_state")
        skill.revalidate(relation, self._store, **self._clocks())
        self._record("mission_revalidation", relation.to_dict())
        self._capture_memory(self._current)
        self._check_cancelled(work)
        rotated = False
        mark = self._operator_mark()
        while True:
            self._check_cancelled(work)
            proposal = skill.propose(self._store, **self._clocks())
            if isinstance(proposal, NavigationOutcome):
                self._registered_recovery.finish_continuation(work, proposal.disposition)
                return proposal.disposition, self._navigation_result(proposal)
            self._progress = {"pending_logical_id": proposal.logical_id, "source_before": proposal.before.observation_id}
            if not rotated:
                self._rotate(work, proposal)
                rotated = True
            feedback = self._dispatch(work, proposal, original)
            if work.cancelled.is_set() or self._closed.is_set():
                return ("unknown" if feedback.transport_disposition == "unknown" else "paused"), {
                    "reason": "Authority revoked; actual primitive receipt retained", "source_ids": [
                        r.observation_id for r in (feedback.before, feedback.after) if r is not None],
                    "pending_logical_id": proposal.logical_id, "grants_authority": False}
            current, _ = self._store.inspect_current_boundary(**self._clocks())
            changed = False
            if feedback.transport_disposition == "returned" and current is not None:
                observed = self._store.observation(current)
                live = self._live()[0]
                self._capture_custody(observed, live)
                changed = current != feedback.after or not same_native_state(observed, live)
            if (feedback.transport_disposition == "not_dispatched" and self._prompt_phase is not None
                    and self._prompt_phase.observation_generation is not None):
                outcome = NavigationOutcome("partial" if skill._steps else "blocked", feedback.reason,
                    skill._steps, skill._proposals, skill._position,
                    tuple(dict.fromkeys((*skill._sources, feedback.before))), None, skill._revalidation)
            elif changed and current != feedback.after:
                # The separate current sample cannot prove this step's effect.
                # Preserve delivery and the already verified route prefix.
                outcome = NavigationOutcome("partial", "Current capture changed after returned navigation",
                    skill._steps, skill._proposals, skill._position,
                    tuple(dict.fromkeys((*skill._sources, feedback.after, current))), None, skill._revalidation)
            else:
                outcome = skill.accept(feedback, self._store, **self._clocks())
            if changed:
                if outcome is None:
                    outcome = NavigationOutcome("partial", "Native view advanced after returned navigation",
                        skill._steps, skill._proposals, skill._position, skill._sources, None, skill._revalidation)
                elif outcome.disposition != "unknown":
                    outcome = replace(outcome, disposition="partial", reason="Native view advanced after returned navigation")
                if not self._ordinary_refusal_guard(work, current):
                    raise EvidenceError("Specialized navigation continuation lost its exact current source")
                self._await_current_observation(work, current, anchor, mark,
                    "Navigation returned; Observe before a new input decision")
            self._publish()
            if self._game_cost >= self._admission.limits.game_seconds:
                result = self._navigation_result(outcome) if outcome is not None else {
                    "verified_steps": skill._steps, "source_ids": [self._current.observation_id], "grants_authority": False}
                if outcome is not None and outcome.disposition == "unknown":
                    result["budget_stop"] = "Observed mission game budget overshot; cost retained"
                    return "unknown", result
                self.pause("Observed mission game budget overshot", cause="internal_recovery")
                self._apply_pauses()
                result.update(disposition="partial", reason="Observed mission game budget overshot; cost retained")
                return "partial", result
            try:
                self._game_guard(anchor, game_limit, after=True)
            except _LocalGameLimit as exc:
                result = self._navigation_result(outcome) if outcome is not None else {
                    "verified_steps": skill._steps, "source_ids": [self._current.observation_id], "grants_authority": False}
                if outcome is not None and outcome.disposition == "unknown":
                    result["budget_stop"] = str(exc)
                    return "unknown", result
                if feedback.after is not None and feedback.after.boundary_kind == "menu":
                    phase = self._open_prompt(work, anchor, feedback.after, mark)
                    result["phase"] = self._prompt_receipt(phase, "awaiting_control")
                self._registered_recovery.finish_continuation(work, "partial")
                result.update(disposition="partial", reason=str(exc), macro_exhausted="game_seconds")
                self._capture_memory(self._current)
                return "partial", result
            except BudgetError as exc:
                result = self._navigation_result(outcome) if outcome is not None else {
                    "verified_steps": skill._steps, "source_ids": [self._current.observation_id], "grants_authority": False}
                self._stop_after_failure(str(exc))
                result.update(disposition="partial", reason=str(exc), budget_stop=str(exc))
                return "unknown" if outcome is not None and outcome.disposition == "unknown" else "partial", result
            if outcome is not None:
                result = self._navigation_result(outcome)
                if self._prompt_phase is not None and self._prompt_phase.observation_generation is not None:
                    result["phase"] = self._prompt_receipt(self._prompt_phase, "awaiting_observation")
                elif (outcome.disposition == "partial" and feedback.transport_disposition == "returned"
                        and feedback.after is not None and feedback.after.boundary_kind == "menu"):
                    phase = self._open_prompt(work, anchor, feedback.after, mark)
                    result["phase"] = self._prompt_receipt(phase, "awaiting_control")
                self._registered_recovery.finish_continuation(work, outcome.disposition)
                self._capture_memory(self._current)
                return outcome.disposition, result

    def _execute_work(self, work: _Work, *, bootstrap: bool) -> tuple[str, dict]:
        kind = work.request["kind"]
        if kind == "start":
            return "completed", self._bootstrap(work) if bootstrap else {
                "admitted": True, "lifecycle_needed": True, "grants_authority": False}
        if kind == "observe":
            return "completed", self._observe(work)
        if kind in ("remember", "correct"):
            return "completed", self._memory_request(work)
        if kind == "skill":
            if work.request["procedure"] is not None:
                try:
                    self._memory.select_procedure(work.request["procedure"])
                except MemoryRequestRefusal as exc:
                    return "blocked", {"reason": "Procedure selection refused before input: " + str(exc),
                        "source_ids": list(work.request["sources"]), "grants_authority": False}
            self._registered_recovery.executable_guard(work.request)
            refusal = self._exhausted_prompt_refusal(work)
            if refusal is not None:
                return "blocked", refusal
            rejection = self._skill_draft_rejection(work)
            if rejection is not None:
                return "blocked", rejection
            if self._registered_lifecycle.phase is not None:
                return self._registered_lifecycle.control(work)
            if self._exit_phase is not None:
                return self._exit_control(work)
            activity_control = (work.request["skill_kind"] == "activity" and (
                work.request["goal"]["step"] in ("interrupt", "answer_interrupt", "resume")
                or self._registered_activity.phase is not None))
            if not activity_control:
                self._prompt_guard(work.request)
            work_id = work.request["work_id"]
            if work_id is not None:
                matches = [row["entry"] for row in self._ledger.memory_records("work") if row["entry"]["id"] == work_id]
                if not matches or matches[-1]["scope"]["session"] != work.request["expected_session"]:
                    return "blocked", {"reason": "Associated Work must exist in this mission and current session"}
                if work.request["skill_kind"] == "navigate" and matches[-1]["scope"] != work.request["goal"]["scope"]:
                    return "blocked", {"reason": "Navigation Work coordinate scope differs"}
            if activity_control:
                return self._registered_activity.execute(work)
            if work.request["skill_kind"] == "navigate":
                return self._navigate(work)
            if work.request["skill_kind"] == "activity" and work.request["goal"]["step"] == "poll":
                return self._poll_activity(work)
            if work.request["skill_kind"] in ("menu", "edit", "interact", "item", "activity", "inspect", "direct", "program"):
                return self._semantic(work)
        if kind == "reconcile":
            return self._registered_recovery.reconcile(work)
        if kind == "readmit" and work.request["mode"] == "recovery":
            return self._registered_recovery.readmit(work)
        if kind in ("handoff", "claim", "readmit"):
            self._registered_recovery.executable_guard(work.request)
            return self._handoff(work)
        if kind == "lifecycle":
            self._registered_recovery.executable_guard(work.request)
            return self._lifecycle(work)
        if kind == "stop":
            self.pause(work.request["reason"], cause="user")
            self._apply_pauses()
            return "completed", {"reason": work.request["reason"], "paused": True, "grants_authority": False}
        return self._unsupported("Registered semantic/normal finish adapter and objective evidence required")

    def _handle(self, work: _Work) -> None:
        data = work.request
        self._check_cancelled(work)
        bootstrap = False
        if data["kind"] == "start":
            bootstrap = self._start(data)
        if self._ledger is None:
            raise LedgerError("No admitted mission")
        if data["kind"] == "result":
            operation = self._ledger.request(data["operation_id"])
            self._cache_operation(operation)
            work.response = {"status": "accepted", "operation": operation}
            work.ready.set()
            return
        if data["kind"] == "context":
            result = self._context(work)
            self._publish()
            work.response = {"status": "accepted", "context": result}
            work.ready.set()
            return
        if (data["kind"] in ("skill", "lifecycle") and self._prompt_phase is not None
                and self._prompt_phase.observation_generation is not None):
            work.response = {"status": "rejected", "reason": "Fresh explicit Observe is required before another input"}
            work.ready.set()
            return
        # Queue consumption owns the current scope. An Observe ahead of this
        # child may have closed its macro after the request was enqueued.
        if (data["kind"] == "skill" and data["phase_id"] is not None and self._prompt_phase is None
                and self._exit_phase is None and self._registered_lifecycle.phase is None
                and self._registered_activity.phase is None and self._registered_recovery.phase is None
                and self._registered_recovery.continuation is None):
            work.response = {"status": "rejected",
                "reason": "No live prompt owns this child; observe and choose a new root from current evidence"}
            work.ready.set()
            return
        admitted = self._ledger.begin_request(data, now=self._wall())
        operation = admitted["operation"]
        self._cache_operation(operation)
        self._publish()
        try:
            with self._metadata:
                self._check_cancelled(work)
                work.response = {"status": "accepted", "operation_id": data["request_id"], "operation": operation}
                work.ready.set()
        except _Cancelled:
            self._apply_pauses()
            if admitted["created"]:
                self._cache_operation(self._ledger.complete_request(data["request_id"], "paused",
                    {"reason": "Admission cancelled before acknowledgment", "grants_authority": False}, now=self._wall()))
            raise
        if not admitted["created"]:
            return
        try:
            disposition, result = self._execute_work(work, bootstrap=bootstrap)
        except _Cancelled as exc:
            self._apply_pauses()
            disposition, result = "paused", {"reason": str(exc), "grants_authority": False}
        except LifecycleRequestRefusal as exc:
            # The receiver rejected only the caller's old selected binding.
            # Existing custody, Pause, evidence and dispatch checks still own
            # authority; do not turn this zero-input request error into recovery.
            disposition, result = "blocked", {"reason": str(exc), "proposals": 0,
                "source_ids": [] if self._current is None else [self._current.observation_id],
                "grants_authority": False}
        except MemoryRequestRefusal as exc:
            disposition, result = "blocked", {"reason": f"MemoryRequestRefusal: {exc}"[:1024],
                "source_ids": [] if self._current is None else [self._current.observation_id],
                "grants_authority": False}
        except LocalBudgetRefusal as exc:
            try:
                refusal = self._exhausted_prompt_refusal(work) if data["kind"] == "skill" else None
                local = (self._local_input_refusal(work, self._current)
                    if data["kind"] == "skill" and self._current is not None else None)
            except (ContractError, ControlError, OSError, ValueError) as health_error:
                local, refusal, exc = None, None, health_error
            disposition = "blocked"
            result = refusal or {"reason": str(exc) if local is None else local,
                "source_ids": [] if self._current is None else [self._current.observation_id],
                "grants_authority": False}
            if local is None:
                self._stop_after_failure(result["reason"])
        except MissionInputRefusal as exc:
            try:
                before = self._current
                if before is None or not self._ordinary_refusal_guard(work, before):
                    raise EvidenceError("Applicability refusal lacks an ordinary owned source")
                self._await_current_observation(work, before, work.game_anchor or before,
                    self._operator_mark(), str(exc))
                disposition, result = "blocked", {"reason": str(exc), "source_ids": [before.observation_id],
                    "phase": self._prompt_receipt(self._prompt_phase, "awaiting_observation"),
                    "proposals": 0, "grants_authority": False}
            except (ContractError, ControlError, OSError, ValueError) as health_error:
                disposition, result = "blocked", {"reason": f"{type(health_error).__name__}: {health_error}"[:1024],
                    "grants_authority": False}
                self._stop_after_failure(result["reason"])
        except (ContractError, ControlError, OSError, ValueError) as exc:
            disposition, result = "blocked", {"reason": f"{type(exc).__name__}: {exc}"[:1024], "grants_authority": False}
            result["source_ids"] = [] if self._current is None else [self._current.observation_id]
            self._diagnostic = result["reason"]
            if (not isinstance(exc, (HandoffEvidenceError, RecoveryEvidenceError))
                    or isinstance(exc, (OSError, LedgerError))):
                self._stop_after_failure(result["reason"])
        self._rotation = None
        self._apply_pauses()
        if disposition == "unknown" and self._lease is not None:
            self._stop_unknown_policy()
        committed = self._ledger.request(data["request_id"])
        if (committed["state"] == "completed" and (data["kind"] in ("handoff", "claim")
                or data["kind"] == "observe" and committed["result"] is not None
                and "macro_closure" in committed["result"])):
            # Atomic handoff or Observe closure is already immutable. A later
            # Pause revokes continuation, never rewrites that committed history.
            operation = committed
            disposition, result = operation["state"], operation["result"]
        else:
            if data["kind"] == "skill":
                root = data if data["phase_id"] is None else self._ledger.request(data["phase_id"])["request"]
                selection = root.get("procedure")
                result["procedure_use"] = (None if selection is None else {
                    **selection, "root_request_id": root["request_id"], "inherited": root is not data,
                    "grants_authority": False})
            operation = self._ledger.complete_request(data["request_id"], disposition, result, now=self._wall())
        try:
            self._registered_lifecycle.after_commit(work, disposition, result)
            if disposition == "completed" and "normal_finish" in result:
                self._commit_finish(work, result)
        except _Cancelled:
            # The immutable result remains historical evidence. A concurrent
            # operator Pause cancels publication, not the entire mission writer.
            self._bindings.clear()
            self._map = None
            self._registered_lifecycle.revoke()
            self._apply_pauses()
        except (ContractError, ControlError) as exc:
            if "normal_finish" not in result:
                raise
            self._diagnostic = f"Finish report retained; terminal transition withheld: {exc}"[:1024]
            self._stop_after_failure(self._diagnostic)
        self._progress = result
        self._registered_reflection.completed(data, disposition)
        self._publish()
        self._cache_operation(operation)

    def _work(self) -> None:
        try:
            while not self._closed.is_set():
                try:
                    if self._apply_pauses():
                        self._publish()
                    self._registered_reflection.tick()
                    work = self._queue.get(timeout=0.05)
                except Empty:
                    continue
                except Exception as exc:
                    self._fault(exc)
                    continue
                self._active = work
                try:
                    self._handle(work)
                except Exception as exc:
                    if not work.ready.is_set():
                        work.response = {"status": "rejected", "reason": f"{type(exc).__name__}: {exc}"[:1024]}
                    if not isinstance(exc, (ContractError, ControlError)) or work.ready.is_set():
                        self._fault(exc)
                finally:
                    work.ready.set()
                    self._active = None
                    self._skill = None
                    self._rotation = None
                    with self._metadata:
                        self._handles = [handle for handle in self._handles if handle is not work]
                    self._queue.task_done()
                    try:
                        self._apply_pauses()
                        self._registered_reflection.tick()
                        self._publish()
                    except Exception as exc:
                        self._fault(exc)
        finally:
            self._cancel_queue()
            try:
                self._apply_pauses()
                self._registered_reflection.finish(permanent=True)
                if self._native is not None:
                    self._native_facts = self._native.status()
                    verified = self._ledger is not None and any(row["state"] == "completed" and row["result"] is not None
                        and row["result"].get("normal_exit", {}).get("launch_id") == self._native_facts["launch_id"]
                        for row in self._ledger.request_records())
                    self._record("mission_process_shutdown_custody", {"process": self._native_facts,
                        "normal_exit_verified": verified, "restored_from_disk": False, "grants_authority": False})
                self._publish()
            except Exception as exc:
                self._diagnostic = f"Terminal persistence failed: {exc}"[:1024]
            self._close_storage()

    def _stop_after_failure(self, reason: str) -> None:
        try:
            self.controller.stop_input()
        except OSError as exc:
            self._diagnostic = f"{reason}; Pause persistence unconfirmed: {exc}"[:1024]
        self._bindings.clear()
        self._clear_prompt()
        self._exit_phase = None
        self._registered_lifecycle.revoke()
        self._registered_handoff.revoke()
        self._registered_activity.revoke()
        self._registered_recovery.revoke()
        self._rotation = None
        self._apply_pauses()
        state = self._ledger.snapshot(now=self._wall())
        if state["phase"] not in TERMINAL | {"paused"}:
            native = self._live()[0]
            cause = "takeover" if native is not None and (native["pause_origin"] == "human"
                or self._lease is not None and native["takeover_generation"] != self._lease.takeover_generation) else "internal_recovery"
            self._ledger.pause(cause=cause, reason=reason, now=self._wall())
        self._lease = None

    def _fault(self, exc: Exception) -> None:
        self._diagnostic = f"Mission writer stopped: {type(exc).__name__}: {exc}"[:1024]
        self.pause(self._diagnostic, cause="internal_recovery")
        self._closed.set()
        # Journal/SQLite failures cannot authorize more work. Keep diagnostics in cache.
        with self._metadata:
            if self._snapshot is not None:
                self._snapshot.update(phase="paused", reason=self._diagnostic,
                    diagnostic=self._diagnostic, next_needed_decision="Storage repair required")

    def _cancel_queue(self) -> None:
        while True:
            try:
                work = self._queue.get_nowait()
            except Empty:
                break
            work.cancelled.set()
            work.response = {"status": "rejected", "reason": "Queued work cancelled"}
            work.ready.set()
            self._queue.task_done()
            with self._metadata:
                self._handles = [handle for handle in self._handles if handle is not work]

    def _close_storage(self) -> None:
        with self._metadata:
            self._presentation_store = None
        try:
            if self._memory is not None and self._memory.library is not None:
                self._memory.library.close()
            if self._store is not None:
                self._store.close()
        finally:
            if self._ledger is not None:
                self._ledger.close()
        self._bindings.clear()
        self._lease, self._rotation = None, None

    def close(self) -> None:
        if not self._closed.is_set():
            self.pause("Mission runtime closed", cause="internal_recovery")
            self._closed.set()
            self._cancel_queue()
        # A blocked writer owns its storage until its finally clause; never close underneath it.
        self._thread.join(min(16.0, self.controller.timeout + 0.5))
