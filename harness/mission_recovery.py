"""Retain unknown-input custody before Observe; never reconcile or grant input.

The deciding recovery/readmission contract is a separate integration gate. This
private holder prevents ordinary Observe from destroying available transport
evidence or losing the original after-frame reservation while that ACK is unknown.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace

from .controller import ControlError
from .gameplay.contracts import EvidenceRef
from .gameplay.evidence import CapacityReservation


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


class RegisteredRecovery:
    def __init__(self, runtime):
        self.runtime = runtime
        self.candidate: DeliveryCandidate | None = None

    def revoke(self):
        # Revocation cannot free unknown dispatched capacity or erase custody.
        if self.candidate is not None:
            self.candidate = replace(self.candidate, revoked=True)

    def reset(self):
        # Only when the owning mission/storage is replaced, never on Pause.
        self.candidate = None

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
