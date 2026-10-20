"""One bounded mission writer composing controller, evidence, memory and ledger.

Admission is not native Resume. Cached status is advisory data; process-local
leases and source bindings are never restored from disk or accepted from JSON.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
import math
from queue import Empty, Full, Queue
import threading
import time
from typing import Any
from uuid import UUID

from .controller import Controller, ControlError, MissionLease, validate_state
from .gameplay.campaign_memory import CampaignMemory
from .gameplay.contracts import ContractError, EvidenceRef, PrimitiveResult
from .gameplay.evidence import MAX_FRAME_BYTES, CapacityError, EvidenceError, EvidenceStore
from .gameplay.mission_contracts import (
    MissionAdmission, SourceBinding, SourceRevalidation, canonical, validate_request,
)
from .gameplay.mission_ledger import BudgetError, LedgerError, MissionLedger, TERMINAL
from .gameplay.navigation import NavigationIntent, NavigationOutcome, NavigationSkill, ObservedMap


class _Cancelled(ContractError):
    pass


@dataclass
class _Work:
    request: dict
    ready: threading.Event = field(default_factory=threading.Event)
    cancelled: threading.Event = field(default_factory=threading.Event)
    response: dict | None = None


class MissionRuntime:
    """One serialized worker and one bounded queue; constructor sends no input.

    Only the worker touches mission storage. The metadata lock protects copied
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
        self._memory: CampaignMemory | None = None
        self._admission: MissionAdmission | None = None
        self._lease: MissionLease | None = None
        self._bindings: dict[str, tuple[EvidenceRef, SourceBinding]] = {}
        self._current: EvidenceRef | None = None
        self._map: ObservedMap | None = None
        self._rotation: tuple | None = None
        self._mission_deadline: float | None = None
        self._game_cost: int | None = None
        self._memory_version = 0
        self._last_context_id: str | None = None
        self._issued_packets: list[str] = []
        self._last_receipt: dict | None = None
        self._progress: dict | None = None
        self._skill: str | None = None
        self._diagnostic: str | None = None
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

    def command(self, request: dict | str | bytes) -> dict:
        try:
            data = validate_request(request)
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
            elif kind == "stop" and not data["finish"] and self._handles:
                rejection = "Pause requested; Stop not admitted while writer busy. Read settled state and submit a new Stop ID/current epoch"
                busy_stop = True
            elif (kind in ("skill", "lifecycle") and any(
                    h.request["kind"] in ("skill", "lifecycle") for h in self._handles)):
                rejection = "An unfinished input operation already owns the writer"
            else:
                try:
                    self._queue.put_nowait(work)
                    self._handles.append(work)
                except Full:
                    rejection = "Mission writer queue is full"
        if rejection:
            if busy_stop:
                self.pause(data["reason"], cause="user")
            return self._response("rejected", reason=rejection)
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
            self._rotation = None
            if self._snapshot is not None:
                self._snapshot.update(phase="paused", pause_cause=cause, reason=reason, lease_owner=None,
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
        limits, reserve = self._admission.limits, self._admission.cleanup_reserve
        active = self._active.request if self._active is not None else None
        current_available = self._current is not None
        if current_available and self._current.boundary_kind == "normal_play":
            try:
                inspected, _ = self._store.inspect_current(**self._clocks())
                current_available = inspected == self._current and self._live()[0] == self._store.observation(self._current)
            except EvidenceError:
                current_available = False
        live = self._live()
        lease_owner = asdict(self._lease) if self._lease is not None and live[3] is self._lease and not live[4] else None
        value = {**state, "lease_owner": lease_owner, "objective": self._admission.objective, "actor_id": state["player_id"],
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
            "next_needed_decision": "Player semantic decision" if state["phase"] == "active" else
                "Registered lifecycle/readmission needed" if state["phase"] == "admitted" else
                "Explicit supported transition required", "grants_authority": False,
            "configuration": asdict(self._admission.configuration),
            "metrics": {"harness_api_spend": 0, "external_tokens": None, "api_quota": None,
                "model_time_seconds": None, "game_seconds": self._game_cost, "archive": usage},
            "diagnostic": self._diagnostic}
        with self._metadata:
            if self._pending_pauses and self._snapshot is not None:
                for key in ("phase", "epoch", "pause_cause", "reason", "next_needed_decision"):
                    value[key] = self._snapshot[key]
            self._snapshot = value

    def _apply_pauses(self) -> bool:
        with self._metadata:
            events, self._pending_pauses = self._pending_pauses, []
        if events:
            self._bindings.clear()
            self._rotation = None
            self._lease = None
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

    def _capacity(self, *, frames: int = 1, byte_count: int = MAX_FRAME_BYTES) -> None:
        usage = self._store.usage()
        limits, reserve = self._admission.limits, self._admission.cleanup_reserve
        if (usage["frames"] + frames > limits.frames - reserve.frames
                or usage["bytes"] + byte_count > limits.frame_bytes - reserve.frame_bytes):
            raise CapacityError("Ordinary evidence would consume cleanup/required after-frame reserve")

    def _game_time(self, reference: EvidenceRef) -> None:
        refs = [r for r in self._store.historical_references if r.boundary_kind == "normal_play"]
        if not refs:
            self._game_cost = None
            return
        if any(r.session != refs[0].session for r in refs):
            self._map = None
            self._bindings.clear()
            raise EvidenceError("Session changed; registered same-character lifecycle alignment required")
        ordered = sorted(refs, key=lambda r: r.revision)
        if any(b.turn < a.turn for a, b in zip(ordered, ordered[1:])):
            raise EvidenceError("Observed game time regressed")
        self._store.verify(ordered[0])
        self._store.verify(ordered[-1])
        self._game_cost = ordered[-1].turn - ordered[0].turn

    def _binding(self, reference: EvidenceRef) -> SourceBinding:
        state, generation, boot = self._check_lease()
        ledger = self._ledger.snapshot(now=self._wall())
        observed = self._store.observation(reference)
        if state != observed:
            raise EvidenceError("Source differs from the exact live controller observation")
        return SourceBinding(reference.observation_id, self._admission.mission_id, ledger["epoch"],
            ledger["player_id"], boot, generation, state["takeover_generation"], self._store.authority_generation())

    def _publish_source(self, reference: EvidenceRef, *, authoritative: bool) -> SourceBinding | None:
        self._current = reference
        self._game_time(reference)
        if reference.boundary_kind == "normal_play":
            scope = {"mission_id": self._admission.mission_id, "session": reference.session, "coordinate_epoch": 0}
            if self._map is None:
                self._map = ObservedMap(**scope)
            if self._map.scope != (scope["mission_id"], scope["session"], scope["coordinate_epoch"]):
                self._map = None
                self._bindings.clear()
                raise EvidenceError("New session cannot adopt old coordinate scope")
            self._map.add(reference, self._store)
        binding = self._binding(reference) if authoritative else None
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

    def _observe_native(self, work: _Work) -> tuple[dict, float]:
        self._check_cancelled(work)
        result = self.controller.execute("observe")
        self._check_cancelled(work)
        state, received = self.controller.observation_snapshot()
        if result.get("status") != "ready" or state != result or received is None:
            raise ControlError("Fresh exact Observe unavailable; registered lifecycle may be needed")
        if not math.isfinite(received) or received > self._clock():
            raise EvidenceError("Observe lacks a finite original receipt")
        return state, received

    def _ingest(self, state: dict, received: float, *, reservation=None) -> EvidenceRef:
        reference = self._store.ingest(state, received_monotonic=received, reservation=reservation, **self._clocks())
        self._current = reference
        return reference

    def _start(self, data: dict) -> bool:
        admission = MissionAdmission.from_dict(data["admission"])
        if self._ledger is not None:
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
        with self._metadata:
            self._operations.clear()
        self._diagnostic, self._progress, self._last_receipt = None, None, None
        self._memory = CampaignMemory(ledger, store)
        self._bindings, self._map, self._lease, self._current, self._rotation = {}, None, None, None, None
        self._game_cost = None
        historical = [r for r in store.historical_references if r.boundary_kind == "normal_play"]
        if historical:
            try:
                self._game_time(historical[-1])
            except EvidenceError as exc:
                self._diagnostic = f"Historic game time unprovable: {exc}"[:1024]
                self._game_cost = None
        self._memory_version = max((r["sequence"] for k in ("claim", "work", "decision")
                                   for r in ledger.memory_records(k)), default=0)
        self._last_context_id = None
        self._issued_packets = []
        self._mission_deadline = ledger.snapshot(now=self._wall())["deadline"]
        return ledger.snapshot(now=self._wall())["phase"] == "admitted"

    def _bootstrap(self, work: _Work) -> dict:
        # Admission and observation never implicitly Resume or create a world.
        before = self._live()
        try:
            state, received = self._observe_native(work)
        except ControlError as exc:
            self._diagnostic = str(exc)
            return {"admitted": True, "lifecycle_needed": True, "reason": str(exc), "grants_authority": False}
        self._capacity()
        self._check_cancelled(work)
        live = self._live()
        eligible = (live[1] == before[1] and not live[4] and not live[5]
                    and not state["paused"] and state["boundary"]["kind"] == "normal_play"
                    and state["in_game"] and state["scene"] is not None
                    and not self.controller.unknown_outcomes and not self.controller.control_unknown_outcomes)
        if eligible:
            ledger = self._ledger.snapshot(now=self._wall())
            if ledger["phase"] == "admitted" and ledger["pause_cause"] == "internal_bootstrap":
                self._lease = self.controller.acquire_mission(self._admission.mission_id,
                    ledger["epoch"], ledger["player_id"], operation="interaction",
                    expected_session=state["session"], expected_revision=state["revision"],
                    expected_boundary_id=state["boundary"]["id"])
                self._check_cancelled(work)
                self._ledger.activate(epoch=ledger["epoch"], player_id=ledger["player_id"], now=self._wall())
        reference = self._ingest(state, received)
        self._publish_source(reference, authoritative=self._lease is not None)
        self._capture_memory(reference)
        return {"admitted": True, "lifecycle_needed": self._lease is None,
                "source_ids": [reference.observation_id], "grants_authority": False}

    def _capture_memory(self, reference: EvidenceRef) -> None:
        if reference.boundary_kind == "normal_play":
            receipt = self._memory.capture_native(reference, {"mission_id": self._admission.mission_id,
                "session": reference.session, "coordinate_epoch": 0}, now=self._wall())
            self._record("mission_native_memory", receipt)
            self._memory_version = receipt["memory_version"]

    def _observe(self, work: _Work) -> dict:
        self._capacity()
        state, received = self._observe_native(work)
        reference = self._ingest(state, received)
        live = self._live()
        authoritative = self._lease is not None and live[3] is self._lease and not live[4] and not live[5]
        self._publish_source(reference, authoritative=authoritative)
        self._capture_memory(reference)
        return {"source_ids": [reference.observation_id], "lifecycle_needed": not authoritative,
                "grants_authority": False}

    def _context(self, work: _Work) -> dict:
        data = work.request
        self._check_cancelled(work)
        state = self._ledger.snapshot(now=self._wall())
        wrapper = {"objective": self._admission.objective, "mission_id": state["mission_id"],
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
        packet = self._memory.context(data["scope"], data["query"], max_bytes=allowance, **self._clocks())
        wrapper["packet"] = packet
        if len(canonical(wrapper).encode()) > data["max_bytes"]:
            raise ContractError("Context wrapper exceeds requested byte ceiling")
        self._check_cancelled(work)
        self._record("mission_context", {"context": wrapper})
        self._check_cancelled(work)
        self._issued_packets = (self._issued_packets + [packet["packet_id"]])[-32:]
        self._last_context_id = packet["packet_id"]
        self._memory_version = packet["memory_version"]
        return wrapper

    def _memory_request(self, work: _Work) -> dict:
        self._check_cancelled(work)
        if work.request["entry_type"] == "decision" and work.request["entry"]["packet_id"] not in self._issued_packets:
            raise ContractError("Decision requires a durably issued context wrapper")
        result = self._memory.apply(work.request, now=self._wall())
        self._memory_version = result["memory_version"]
        return result

    def _handoff(self, work: _Work) -> tuple[str, dict]:
        return self._unsupported("Registered quiescent handoff/claim adapter required")

    def _lifecycle(self, work: _Work) -> tuple[str, dict]:
        return self._unsupported("Registered normal lifecycle adapter and engine evidence required")

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
        if state != observed:
            raise EvidenceError("Informing source differs from exact live controller state")
        return original

    def _rotate(self, work: _Work, proposal: NavigationIntent) -> None:
        state, generation, _ = self._check_lease()
        if self._store.observation(proposal.before) != state:
            raise EvidenceError("Proposal before-source is not the exact live controller state")
        self._check_cancelled(work)
        old = self._lease
        new = self.controller.acquire_mission(old.mission_id, old.epoch, old.actor_id,
            operation="navigate", expected_session=state["session"], expected_revision=state["revision"],
            expected_boundary_id=state["boundary"]["id"], replace=old)
        self._lease = new
        if new.pause_generation != generation + 1:
            raise ControlError("Operation rotation did not make exactly one host generation")
        self._rotation = (work.request["request_id"], proposal.before.observation_id, generation, old, new)
        self._record("mission_rotation", {"request_id": work.request["request_id"],
            "source_id": proposal.before.observation_id, "before": asdict(old), "after": asdict(new)})
        self._check_cancelled(work)

    def _dispatch_guard(self, work: _Work, proposal: NavigationIntent) -> None:
        self._check_cancelled(work)
        state, generation, boot = self._check_lease()
        ledger = self._ledger.snapshot(now=self._wall())
        if ledger["epoch"] != work.request["epoch"] or ledger["phase"] != "active":
            raise LedgerError("Operation epoch/phase revoked")
        entry = self._bindings.get(proposal.before.observation_id)
        if entry is None:
            raise EvidenceError("Proposal source has no live binding")
        binding = entry[1]
        if (binding.epoch, binding.actor_id, binding.controller_boot_id, binding.takeover_generation) != (
                ledger["epoch"], ledger["player_id"], boot, state["takeover_generation"]):
            raise EvidenceError("Proposal binding crossed live actor/controller/takeover")
        if binding.pause_generation != generation:
            transition = self._rotation
            if (transition is None or transition[:3] != (work.request["request_id"],
                    proposal.before.observation_id, binding.pause_generation)
                    or transition[3].pause_generation != binding.pause_generation
                    or transition[4] is not self._lease or generation != binding.pause_generation + 1):
                raise EvidenceError("Proposal binding crossed an unauthenticated host generation")
        if self._store.authority_generation() != binding.store_generation:
            raise EvidenceError("Proposal store generation changed")
        if self._game_cost is None or self._game_cost >= self._admission.limits.game_seconds:
            raise BudgetError("Game time unavailable or exhausted")

    def _deadline(self, work: _Work, original: EvidenceRef) -> float:
        operation = self._ledger.request(work.request["request_id"])
        wall_deadline = min(operation["deadline"], self._mission_deadline - self._admission.cleanup_reserve.wall_seconds)
        deadline = min(self._clock() + wall_deadline - self._wall(),
                       original.received_monotonic + work.request["limits"]["wall_seconds"])
        if deadline <= self._clock():
            raise BudgetError("Original navigation/mission deadline exhausted")
        return deadline

    def _envelope(self, raw: dict, work: _Work, proposal: NavigationIntent, preflight: EvidenceRef | None) -> tuple[str, str]:
        fields = {"logical_action_id", "request", "result", "published", "received_monotonic", "preflight"}
        if type(raw) is not dict or set(raw) != fields or raw["logical_action_id"] != proposal.logical_id or type(raw["published"]) is not bool:
            raise ContractError("Malformed exact mission receipt envelope")
        request, result = raw["request"], raw["result"]
        if type(result) is not dict:
            raise ContractError("Mission receipt lacks terminal result")
        if request is None:
            if raw["published"]:
                raise ContractError("Published receipt lost native request identity")
        else:
            expected = {"kind": proposal.kind, proposal.kind: proposal.action, "session": proposal.before.session,
                "revision": proposal.before.revision, "boundary_id": proposal.expected_boundary_id}
            if any(request.get(key) != value for key, value in expected.items()) or not isinstance(request.get("id"), str):
                raise ContractError("Mission native request does not correlate with logical proposal")
            if str(UUID(request["id"])) != request["id"]:
                raise ContractError("Malformed native request UUID")
            if (raw["published"] or result.get("id") is not None) and result.get("id") != request["id"]:
                raise ContractError("Mission native result identity differs")
        if raw["preflight"] is not None:
            proof = raw["preflight"]
            if type(proof) is not dict or set(proof) != {"observation", "received_monotonic", "expected_image_sha256"}:
                raise ContractError("Malformed mission preflight receipt")
            validate_state(proof["observation"])
            proof_time = proof["received_monotonic"]
            if (type(proof_time) not in (int, float) or not math.isfinite(proof_time)
                    or proof_time < 0 or proof_time > self._clock()
                    or raw["published"] and self._clock() - proof_time > 3):
                raise ContractError("Preflight receipt lacks its original finite clock")
            if preflight is None:
                if request is not None or raw["published"]:
                    raise ContractError("Published input lacks retained preflight source")
            elif (preflight.received_monotonic != proof_time
                    or raw["published"] and self._store.observation(preflight) != proof["observation"]):
                raise ContractError("Preflight receipt differs from actual retained source")
        elif request is not None:
            raise ContractError("Native request lacks retained final preflight")
        received = raw["received_monotonic"]
        if received is not None and (type(received) not in (int, float) or not math.isfinite(received)
                or not 0 <= self._clock() - received <= 3 or preflight is not None and received < preflight.received_monotonic):
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
            if (received is None or result["session"] != proposal.before.session
                    or result["revision"] <= proposal.before.revision
                    or result["boundary"]["kind"] != "normal_play"
                    or not result["in_game"] or result["scene"] is None):
                raise ContractError("Ready receipt lacks exact advanced same-session source")
            actual, actual_received = self.controller.observation_snapshot()
            if (actual != result or actual_received is None or actual_received < received
                    or actual_received > self._clock()):
                raise ContractError("Ready receipt is not the exact current atomic observation")
            return "returned", "Exact terminal ready receipt; displacement requires independent verification"
        return "unknown", str(result.get("error") or "Input acknowledgment is unresolved")[:1024]

    def _dispatch(self, work: _Work, proposal: NavigationIntent, original: EvidenceRef) -> PrimitiveResult:
        reservation = None
        preflight_source = None
        prepared = False
        after = None
        raw = None
        disposition, reason = "not_dispatched", "Dispatch not admitted"
        envelope_valid = False
        def preflight(observed: dict, received: float) -> None:
            nonlocal reservation, preflight_source, prepared
            self._dispatch_guard(work, proposal)
            self._capacity(frames=2, byte_count=2 * MAX_FRAME_BYTES)
            preflight_source = self._store.retain_equivalent(observed,
                received_monotonic=received, rule="native_state", **self._clocks())
            if (preflight_source == proposal.before or preflight_source.received_monotonic != received
                    or self._store.observation(preflight_source) != observed):
                raise EvidenceError("Preflight retention must attest its actual distinct source and original receipt")
            self._dispatch_guard(work, proposal)
            self._capacity()
            reservation = self._store.reserve_dispatch(proposal.before, **self._clocks())
            intent = {"kind": proposal.kind, "value": proposal.action,
                "expected_session": proposal.before.session, "expected_revision": proposal.before.revision,
                "expected_boundary_id": proposal.expected_boundary_id, "source_before": proposal.before.observation_id,
                "preflight_source": preflight_source.observation_id,
                "revalidation": None if proposal.revalidation is None else proposal.revalidation.to_dict(),
                "reservation_id": reservation.token}
            self._ledger.prepare_primitive(work.request["request_id"], proposal.logical_id, intent, now=self._wall())
            prepared = True
            self._cache_operation(self._ledger.request(work.request["request_id"]))
            self._dispatch_guard(work, proposal)
            self._store.verify(proposal.before)
            self._store.verify(preflight_source)
        try:
            self._dispatch_guard(work, proposal)
            deadline = self._deadline(work, original)
            self._publish()
            raw = self.controller.execute_mission(self._lease, kind=proposal.kind, value=proposal.action,
                expected_session=proposal.before.session, expected_revision=proposal.before.revision,
                expected_boundary_id=proposal.expected_boundary_id, logical_action_id=proposal.logical_id,
                deadline_monotonic=deadline, preflight=preflight)
            if not prepared:
                prepared = any(row["logical_id"] == proposal.logical_id for row in self._ledger.primitive_records())
            disposition, reason = self._envelope(raw, work, proposal, preflight_source)
            envelope_valid = True
            if raw["published"]:
                self._ledger.published(proposal.logical_id, raw["request"]["id"], now=self._wall())
            if disposition == "returned":
                after = self._ingest(raw["result"], raw["received_monotonic"], reservation=reservation)
                reservation = None
                live = self._live()
                authoritative = live[3] is self._lease and self._lease is not None and not live[4] and not work.cancelled.is_set()
                self._publish_source(after, authoritative=authoritative)
        except Exception as exc:
            disposition = "unknown" if raw is not None and (not envelope_valid or raw.get("published")) or prepared and raw is None else "not_dispatched"
            reason = f"{type(exc).__name__}: {exc}"[:1024]
            # An exception from execute_mission may occur after input publication.
            if prepared and raw is None:
                disposition = "unknown"
        if raw is not None and (type(raw) is not dict or set(raw) != {
                "logical_action_id", "request", "result", "published", "received_monotonic", "preflight"}):
            disposition = "unknown"
        if reservation is not None and disposition in ("not_dispatched", "rejected"):
            self._store.release(reservation)
        receipt = {"logical_action_id": proposal.logical_id,
            "native_request_id": raw["request"].get("id") if envelope_valid and type(raw.get("request")) is dict else None,
            "kind": proposal.kind, "value": proposal.action, "expected_session": proposal.before.session,
            "expected_revision": proposal.before.revision, "expected_boundary_id": proposal.expected_boundary_id,
            "published": raw.get("published") is True if type(raw) is dict else False,
            "transport_disposition": disposition, "source_before": proposal.before.observation_id,
            "preflight_source": None if preflight_source is None else preflight_source.observation_id,
            "source_after": None if after is None else after.observation_id,
            "received_monotonic": raw.get("received_monotonic") if envelope_valid and
                type(raw.get("received_monotonic")) in (int, float) and math.isfinite(raw["received_monotonic"]) else None,
            "reason": reason}
        # Pause may already own the epoch/cause. Settle cost without rewriting it.
        self._apply_pauses()
        if prepared:
            self._ledger.settle_primitive(proposal.logical_id, disposition, receipt, now=self._wall())
        live = self._live()
        if disposition != "unknown" and (live[3] is not self._lease or live[4]):
            self._stop_after_failure(reason)
        self._last_receipt = receipt
        if disposition == "unknown":
            # Settlement owns the unknown epoch transition. Do not advance it again
            # or replace an already recorded user/takeover Pause with a late receipt.
            try:
                self.controller.stop_input()
            except OSError as exc:
                self._diagnostic = f"Unknown-input Pause persistence failed: {exc}"[:1024]
            self._bindings.clear()
            self._lease, self._rotation = None, None
        displacement = None if after is None or after.session != proposal.before.session else tuple(
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

    def _navigate(self, work: _Work) -> tuple[str, dict]:
        data = work.request
        original, binding = self._informing(data)
        if self._map is None:
            raise EvidenceError("Navigation has no current observed map")
        skill = NavigationSkill(data, self._map)
        self._skill = "navigate"
        inspected, fresh = self._store.inspect_current(**self._clocks())
        if inspected != original:
            raise EvidenceError("Informing source is no longer the current retained source")
        if not fresh:
            # Exactly one intentional promotion; never mutate original request/source age.
            self._store.verify(original)
            self._capacity()
            state, received = self._observe_native(work)
            current = self._ingest(state, received)
            refreshed = self._publish_source(current, authoritative=True)
            relation = SourceRevalidation(binding, refreshed, "native_state")
            skill.revalidate(relation, self._store, **self._clocks())
            self._record("mission_revalidation", relation.to_dict())
        self._capture_memory(self._current)
        self._check_cancelled(work)
        rotated = False
        while True:
            self._check_cancelled(work)
            proposal = skill.propose(self._store, **self._clocks())
            if isinstance(proposal, NavigationOutcome):
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
            outcome = skill.accept(feedback, self._store, **self._clocks())
            self._publish()
            if self._game_cost > self._admission.limits.game_seconds:
                self.pause("Observed mission game budget overshot", cause="internal_recovery")
                self._apply_pauses()
                result = self._navigation_result(outcome) if outcome is not None else {
                    "verified_steps": skill._steps, "source_ids": [self._current.observation_id], "grants_authority": False}
                result.update(disposition="partial", reason="Observed mission game budget overshot; cost retained")
                return "partial", result
            if outcome is not None:
                self._capture_memory(self._current)
                return outcome.disposition, self._navigation_result(outcome)

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
            if work.request["phase_id"] is not None:
                return "blocked", {"reason": "Owned phase adapter is not integrated; phase IDs grant no authority"}
            work_id = work.request["work_id"]
            if work_id is not None:
                matches = [row["entry"] for row in self._ledger.memory_records("work") if row["entry"]["id"] == work_id]
                if not matches or matches[-1]["scope"]["session"] != work.request["expected_session"]:
                    return "blocked", {"reason": "Associated Work must exist in this mission and current session"}
                if work.request["skill_kind"] == "navigate" and matches[-1]["scope"] != work.request["goal"]["scope"]:
                    return "blocked", {"reason": "Navigation Work coordinate scope differs"}
            if work.request["skill_kind"] == "navigate":
                return self._navigate(work)
        if kind in ("handoff", "claim"):
            return self._handoff(work)
        if kind == "lifecycle":
            return self._lifecycle(work)
        if kind == "stop" and not work.request["finish"]:
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
        except (ContractError, ControlError, OSError, ValueError) as exc:
            disposition, result = "blocked", {"reason": f"{type(exc).__name__}: {exc}"[:1024], "grants_authority": False}
            result["source_ids"] = [] if self._current is None else [self._current.observation_id]
            self._diagnostic = result["reason"]
            if data["kind"] not in ("remember", "correct") or isinstance(exc, (OSError, LedgerError)):
                self._stop_after_failure(result["reason"])
        self._rotation = None
        self._apply_pauses()
        operation = self._ledger.complete_request(data["request_id"], disposition, result, now=self._wall())
        self._progress = result
        self._publish()
        self._cache_operation(operation)

    def _work(self) -> None:
        try:
            while not self._closed.is_set():
                try:
                    if self._apply_pauses():
                        self._publish()
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
                        self._publish()
                    except Exception as exc:
                        self._fault(exc)
        finally:
            self._cancel_queue()
            try:
                self._apply_pauses()
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
        try:
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
