"""One-writer recovery: immutable delivery proof, then separate charged Resume.

Only actual private dispatch custody can reconcile. Historical proof never
restores these objects, a lease, prompt selection or operator consent.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace

from .controller import ControlError
from .gameplay.contracts import EvidenceRef
from .gameplay.evidence import CapacityReservation, EvidenceError
from .gameplay.contracts import canonical
from .gameplay.mission_contracts import VERSION, validate_delivery_resolution
from .gameplay.mission_ledger import BudgetError


class RecoveryEvidenceError(EvidenceError):
    """Correctable read-only evidence selection; never renew input consent."""


@dataclass(frozen=True)
class DeliveryCandidate:
    request_id: str
    root_id: str
    logical_id: str
    work_id: str | None
    actor_id: str
    origin_epoch: int
    recovery_epoch: int
    operator_mark: tuple[str, int]
    generation: int
    takeover_generation: int
    request: dict
    reservation: CapacityReservation | None
    game_anchor: EvidenceRef
    revoked: bool = False
    collected: bool = False
    proof: dict | None = None
    terminal_source: EvidenceRef | None = None


@dataclass(frozen=True)
class RecoveryPhase:
    candidate: DeliveryCandidate
    reconciliation_request_id: str
    checkpoint: EvidenceRef

    @property
    def operator_mark(self): return self.candidate.operator_mark

    @property
    def takeover_generation(self): return self.candidate.takeover_generation

    @property
    def game_anchor(self): return self.candidate.game_anchor

    @property
    def root_id(self): return self.candidate.root_id


class RegisteredRecovery:
    def __init__(self, runtime):
        self.runtime = runtime
        self.candidate: DeliveryCandidate | None = None
        self.phase: RecoveryPhase | None = None
        self.continuation: RecoveryPhase | None = None

    def revoke(self):
        self.phase = self.continuation = None
        # Revocation cannot free unknown dispatched capacity or erase custody.
        if self.candidate is not None:
            self.candidate = replace(self.candidate, revoked=True)

    def reset(self):
        # Only when the owning mission/storage is replaced, never on Pause.
        self.candidate = None
        self.phase = self.continuation = None

    def remember(self, work, proposal, raw, reservation, *, operator_mark, takeover_generation, game_anchor):
        r = self.runtime
        state = r._ledger.snapshot(now=r._wall())
        live = r._live()
        if (work.cancelled.is_set() or r._pending_pauses or operator_mark != r._operator_mark()
                or state["phase"] != "paused" or state["pause_cause"] != "unknown"
                or state["epoch"] != work.request["epoch"] + 1
                or live[3] is not None or live[0] is None
                or live[0]["takeover_generation"] != takeover_generation
                or type(raw) is not dict or raw.get("published") is not True
                or type(raw.get("request")) is not dict or proposal.kind == "resume"):
            return
        request = raw["request"]
        primitive = r._ledger.primitive(proposal.logical_id)
        if (primitive["state"] != "unknown" or primitive["request_id"] != work.request["request_id"]
                or primitive["native_id"] not in (None, request.get("id"))
                or request.get("session") != proposal.before.session
                or live[0]["session"] != request.get("session")
                or request.get("authority", {}).get("controller_boot_id") != operator_mark[0]):
            return
        candidate = DeliveryCandidate(work.request["request_id"], work.request.get("phase_id") or work.request["request_id"],
            proposal.logical_id, work.request.get("work_id"), state["player_id"], work.request["epoch"], state["epoch"],
            operator_mark, live[1], takeover_generation, copy.deepcopy(request), reservation, game_anchor)
        with r._metadata:
            r._check_cancelled(work)
            if operator_mark != r._operator_mark() or r._pending_pauses:
                return
            self.candidate = candidate

    def before_observe(self, work, *, deadline_monotonic):
        r, candidate = self.runtime, self.candidate
        if candidate is None or candidate.revoked or candidate.collected:
            return
        state = r._ledger.snapshot(now=r._wall())
        if (r._operator_mark() != candidate.operator_mark
                or (state["epoch"], state["player_id"], state["phase"], state["pause_cause"]) !=
                   (candidate.recovery_epoch, candidate.actor_id, "paused", "unknown")):
            self.revoke()
            return
        remaining = r._ledger.request(work.request["request_id"])["deadline"] - r._wall()
        deadline = r._clock() + remaining
        if deadline_monotonic is not None:
            deadline = min(deadline, deadline_monotonic)
        try:
            proof = r.controller.inspect_mission_delivery(expected_request=candidate.request,
                expected_controller_boot_id=candidate.operator_mark[0],
                expected_operator_generation=candidate.operator_mark[1], expected_generation=candidate.generation,
                expected_takeover_generation=candidate.takeover_generation, deadline_monotonic=deadline)
            error = None
        except ControlError as exc:
            proof, error = None, str(exc)[:1024]
        r._check_cancelled(work)
        terminal_source = None
        if proof is not None and proof["basis"] == "terminal_response":
            result = proof["result"]
            native = result["state"] if "state" in result else result
            if native["status"] == "ready" and native["frame_ok"]:
                try:
                    # Retain before Observe can advance the store or overwrite
                    # native pixels. Never refresh an old ACK's capture clock.
                    terminal_source = r._ingest(native, proof["received_monotonic"], reservation=candidate.reservation)
                    with r._metadata:
                        current = self.candidate
                        if current is not None and current.logical_id == candidate.logical_id:
                            self.candidate = replace(current, reservation=None, terminal_source=terminal_source)
                            candidate = self.candidate
                except Exception as exc:
                    error = f"Terminal frame unavailable: {type(exc).__name__}: {exc}"[:1024]
        # A missing/overwritten result never becomes evidence from the next frame.
        # One collection attempt precedes Observe; subsequent queries cannot renew
        # its window or reclassify the unknown from a later unrelated response.
        r._record("mission_delivery_collection", {"request_id": candidate.request_id,
            "root_id": candidate.root_id, "logical_id": candidate.logical_id,
            "proof": proof, "error": error, "grants_authority": False})
        with r._metadata:
            r._check_cancelled(work)
            if self.candidate is candidate and not r._pending_pauses and r._operator_mark() == candidate.operator_mark:
                self.candidate = replace(candidate, collected=True, proof=copy.deepcopy(proof), revoked=error is not None)

    def _candidate_guard(self, work, candidate):
        r = self.runtime
        r._check_cancelled(work)
        state, live = r._ledger.snapshot(now=r._wall()), r._live()
        if (candidate is None or candidate.revoked or candidate.operator_mark != r._operator_mark()
                or r._pending_pauses or state["epoch"] != candidate.recovery_epoch
                or state["player_id"] != candidate.actor_id or live[0] is None
                or live[3] is not r._lease
                or live[0]["session"] != candidate.request["session"]
                or live[0]["takeover_generation"] != candidate.takeover_generation
                or state["pause_cause"] != "unknown"):
            raise ControlError("Recovery lost its original unknown actor/epoch/operator/takeover custody")

    def reconcile(self, work):
        r, data, candidate = self.runtime, work.request, self.candidate
        if candidate is None:
            r._registered_lifecycle.reject_delivery_reconciliation(work)
        self._candidate_guard(work, candidate)
        state = r._ledger.snapshot(now=r._wall())
        ref = r._current
        if state["phase"] != "paused" or r._lease is not None or candidate.proof is None or not candidate.collected or ref is None:
            raise ControlError("Reconciliation requires exact captured delivery proof and current diagnostic source")
        if data["unresolved_request_id"] != candidate.request_id or data["evidence_id"] != ref.observation_id:
            raise RecoveryEvidenceError("Reconciliation must name its exact original request and current diagnostic source")
        native = r._store.observation(ref)
        r._store.verify(ref)
        inspected, fresh = r._store.inspect_current_boundary(**r._clocks())
        if inspected != ref or not fresh:
            raise RecoveryEvidenceError("Reconciliation requires a fresh current diagnostic source; Observe without replay")
        if (native != r._live()[0] or native["status"] != "ready" or not native["paused"]
                or ref.session != candidate.request["session"] or native["pause_origin"] == "human"):
            raise ControlError("Reconciliation requires its actual paused same-session diagnostic observation")
        proof = candidate.proof
        terminal = None
        if proof["result"] is not None:
            result = proof["result"]
            current = result.get("state", result)
            boundary = current["boundary"]
            terminal = dict(id=result["id"], channel="control" if "state" in result else "ordinary",
                status=result["status"], session=current["session"], revision=current["revision"],
                takeover_generation=current["takeover_generation"], boundary_id=boundary["id"],
                boundary_kind=boundary["kind"], interrupt_request_id=boundary["interrupt_request_id"],
                control_generation=boundary["control_generation"], frame_ok=current["frame_ok"])
        record = validate_delivery_resolution(dict(schema=VERSION, record_type="DeliveryResolution",
            reconciliation_request_id=data["request_id"], original_request_id=candidate.request_id,
            root_id=candidate.root_id, logical_id=candidate.logical_id, native_request_id=candidate.request["id"],
            actor_id=candidate.actor_id, origin_epoch=candidate.origin_epoch, recovery_epoch=candidate.recovery_epoch,
            controller_boot_id=candidate.operator_mark[0], operator_pause_generation=candidate.operator_mark[1],
            takeover_generation=candidate.takeover_generation, game_anchor_source_id=candidate.game_anchor.observation_id,
            before_source_id=r._ledger.primitive(candidate.logical_id)["intent"]["source_before"], observed_source_id=ref.observation_id,
            terminal_source_id=None if candidate.terminal_source is None else candidate.terminal_source.observation_id,
            native_request_json=canonical(candidate.request), retirement=proof["retirement"], terminal=terminal,
            collection_started_monotonic=proof["collection_started_monotonic"],
            collection_deadline_monotonic=proof["collection_deadline_monotonic"],
            collection_received_monotonic=proof["received_monotonic"], grants_authority=False))
        sources = tuple(dict.fromkeys(record[k] for k in ("before_source_id", "game_anchor_source_id", "terminal_source_id", "observed_source_id")
                                      if record[k] is not None))
        for identity in sources:
            r._store.verify(next(item for item in r._store.historical_references if item.observation_id == identity))
        self._candidate_guard(work, candidate)
        r._ledger.reconcile_effect(candidate.logical_id, proof=record, sources=sources, note=data["reason"], now=r._wall())
        if candidate.reservation is not None:
            r._store.release(candidate.reservation)
            candidate = replace(candidate, reservation=None)
        with r._metadata:
            self._candidate_guard(work, candidate)
            self.candidate = candidate
            self.phase = RecoveryPhase(candidate, data["request_id"], ref)
        return "completed", dict(reconciliation=record, source_ids=list(sources), reason=data["reason"], grants_authority=False)

    def guard(self, work, phase, proposal=None):
        r = self.runtime
        if self.phase is not phase:
            raise ControlError("Recovery phase was revoked")
        self._candidate_guard(work, phase.candidate)
        state = r._ledger.snapshot(now=r._wall())
        root = r._ledger.request(phase.root_id)
        if (work.request["phase_id"] != phase.root_id or work.request["work_id"] != root["request"].get("work_id")
                or state["phase"] not in ("paused", "active")
                or work.request["epoch"] != phase.candidate.recovery_epoch
                or phase.checkpoint.boundary_kind != "normal_play"
                or r._wall() >= root["deadline"]):
            raise ControlError("Recovery readmission requires its original normal-play root/Work/deadline")
        r._game_guard(phase.game_anchor, root["request"]["limits"]["game_seconds"])
        if proposal is not None and proposal.before != phase.checkpoint:
            raise ControlError("Recovery Resume lost its exact paused source")

    def readmit(self, work):
        r, data, phase = self.runtime, work.request, self.phase
        if phase is None or phase.reconciliation_request_id != data["reconciliation_request_id"]:
            raise ControlError("Readmission requires this live exact reconciled dispatch; history restores no consent")
        self.guard(work, phase)
        native = r._store.observation(phase.checkpoint)
        if (phase.checkpoint.observation_id not in data["sources"] or
                (data["expected_session"], data["expected_revision"], data["expected_boundary_id"]) !=
                (native["session"], native["revision"], native["boundary"]["id"])):
            raise ControlError("Recovery readmission changed its explicit diagnostic checkpoint")
        if r._game_cost is None or r._game_cost >= r._admission.limits.game_seconds:
            raise BudgetError("Recovery cannot renew original mission game time")
        r._capacity()
        observed, received = r._observe_native(work, deadline_monotonic=r._deadline(work, phase.checkpoint))
        self.guard(work, phase)
        ref = r._ingest(observed, received)
        if not r._store.equivalent(phase.checkpoint, ref, rule="exact_png_bytes") or not observed["paused"]:
            raise ControlError("Recovery readmission changed its paused normal checkpoint")
        phase = replace(phase, checkpoint=ref)
        with r._metadata:
            self._candidate_guard(work, phase.candidate)
            self.phase = phase
        r._ledger.activate(epoch=data["epoch"], player_id=phase.candidate.actor_id, now=r._wall())
        proposal = r._resume_intent(data["request_id"], ref)
        feedback = r._dispatch(work, proposal, phase.game_anchor, lifecycle=phase)
        r._check_cancelled(work)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", dict(
                reason=feedback.reason, source_ids=[ref.observation_id], grants_authority=False)
        self.guard(work, phase)
        after = r._store.observation(feedback.after)
        if after["paused"] or after["boundary"]["kind"] != "normal_play":
            raise ControlError("Recovery Resume did not return to the same normal play")
        r._lease = r.controller.acquire_mission(r._admission.mission_id, data["epoch"], phase.candidate.actor_id,
            operation="interaction", expected_session=after["session"], expected_revision=after["revision"],
            expected_boundary_id=after["boundary"]["id"])
        r._publish_source(feedback.after, authoritative=True)
        r._capture_memory(feedback.after)
        with r._metadata:
            self.guard(work, phase)
            self.phase = None
            root = r._ledger.request(phase.root_id)["request"]
            self.continuation = phase if root.get("skill_kind") == "navigate" else None
        record = dict(schema=VERSION, record_type="Readmission", mode="recovery",
            reconciliation_request_id=phase.reconciliation_request_id, root_id=phase.root_id,
            player_id=phase.candidate.actor_id, epoch=data["epoch"],
            post_pause_source_id=r._ledger.request(phase.reconciliation_request_id)["result"]["reconciliation"]["observed_source_id"],
            revalidated_source_id=ref.observation_id, after_source_id=feedback.after.observation_id,
            logical_id=proposal.logical_id, grants_authority=False)
        return "completed", dict(readmission=record, source_ids=[ref.observation_id, feedback.after.observation_id],
            reason="Deliberate charged Resume under original root; semantic assessment still required", grants_authority=False)

    def executable_guard(self, data):
        if self.phase is not None:
            raise ControlError("Reconciled recovery requires its separate deliberate readmission")
        if self.continuation is not None and not (data["kind"] == "skill" and self.continuation_guard(data)):
            raise ControlError("Recovery continuation fences unrelated executable roots")

    def continuation_guard(self, data, before=None):
        phase = self.continuation
        if phase is None: return False
        r = self.runtime
        root = r._ledger.request(phase.root_id)
        state = r._ledger.snapshot(now=r._wall())
        live = r._live()[0]
        if (data["kind"] != "skill" or data["skill_kind"] != "navigate"
                or data["phase_id"] != phase.root_id or data["goal"] != root["request"]["goal"]
                or data["work_id"] != root["request"].get("work_id")
                or state["epoch"] != phase.candidate.recovery_epoch or data["epoch"] != state["epoch"]
                or state["player_id"] != phase.candidate.actor_id or phase.operator_mark != r._operator_mark()
                or live is None or live["session"] != phase.checkpoint.session
                or live["takeover_generation"] != phase.takeover_generation
                or r._wall() >= root["deadline"]):
            raise ControlError("Navigation continuation lost its exact original root/goal/Work/epoch")
        r._game_guard(phase.game_anchor, root["request"]["limits"]["game_seconds"], after=before is None)
        if before is not None and before != r._current:
            raise ControlError("Continuation requires its actual fresh informing source")
        return True

    def finish_continuation(self, work, disposition):
        if self.continuation is not None and work.request.get("phase_id") == self.continuation.root_id:
            if disposition not in ("unknown",):
                # A verified terminal suffix closes this root; future plans are
                # new bounded work, never continuation under a renewed root.
                self.continuation = None
