"""One-writer player replacement; durable receipts never restore live consent.

Actor names and source-read declarations are audit statements. Actual fresh agent
context and image inspection remain transcript/acceptance evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import os
from typing import TYPE_CHECKING, Callable

from .controller import MAX_WAIT, ControlError
from .gameplay.contracts import EvidenceRef
from .gameplay.mission_contracts import (
    VERSION, MAX_HANDOFF_CONTEXT_BYTES, MAX_HANDOFF_SOURCES, HANDOFF_CONTEXT_RESERVE,
)
from .gameplay.evidence import CapacityError, EvidenceError, same_native_state
from .gameplay.mission_ledger import BudgetError, LedgerError

if TYPE_CHECKING:
    from .mission_runtime import MissionRuntime, _ResumeIntent, _Work


@dataclass(frozen=True)
class HandoffPhase:
    handoff_id: str
    checkpoint: EvidenceRef
    operator_mark: tuple[str, int]
    pause_generation: int
    takeover_generation: int
    epoch: int
    claim_request_id: str | None = None


class HandoffEvidenceError(EvidenceError):
    """Correctable representation/claim failure before any input or epoch change."""


class RegisteredHandoff:
    def __init__(self, runtime: MissionRuntime):
        self.runtime = runtime
        self.phase: HandoffPhase | None = None

    def revoke(self) -> None:
        self.phase = None

    def _empty(self, work: _Work, mark: tuple[str, int], *, dispatch: bool = False) -> None:
        r = self.runtime
        r._check_cancelled(work)
        if r._operator_mark() != mark:
            raise ControlError("Handoff crossed controller restart or operator Pause")
        with r._metadata:
            if r._pending_pauses or any(h is not work for h in r._handles) or not r._queue.empty():
                raise ControlError("Handoff requires its sole handle and empty runtime queue")
        with r.controller.data_lock:
            c = r.controller
            if (c.closed or c.frozen or c.pending is not None or c.control_pending is not None
                    or c._mission_lease is not None or c._command_work > int(dispatch) or not c.pause_requested
                    or (not dispatch and c.command_lock.locked()) or c.control_lock.locked()):
                raise ControlError("Handoff requires paused empty controller slots")
        if any(os.path.lexists(r.controller.bridge / name) for name in
               ("request.json", "claimed.json", "control.json", "control-claimed.json")):
            raise ControlError("Handoff requires empty native inboxes")

    def _source_checker(self, maximum: int = MAX_HANDOFF_SOURCES) -> tuple[dict[str, EvidenceRef], Callable[[str], str]]:
        """One operation's distinct checks, including classification/checkpoints."""
        r = self.runtime
        refs, checks = r._memory._references(), {}
        def status(identity: str) -> str:
            if identity not in checks:
                if len(checks) >= maximum:
                    raise CapacityError("Handoff aggregate source-check bound exhausted; no truncation")
                try:
                    checks[identity] = (r._store.source_status(refs[identity]) if identity in refs
                                        else "unavailable")
                except CapacityError:
                    raise
                except EvidenceError as exc:
                    checks[identity] = ("unavailable: " + str(exc))[:1024]
            return checks[identity]
        return refs, status

    def _observation_remaining(self, work: _Work) -> float:
        r = self.runtime
        deadline = min(r._ledger.request(work.request["request_id"])["deadline"],
                       r._mission_deadline - r._admission.cleanup_reserve.wall_seconds)
        remaining = deadline - r._wall()
        if remaining <= 0:
            raise BudgetError("Original handoff/readmission observation deadline exhausted")
        return remaining

    def _observe(self, work: _Work) -> tuple[dict, float]:
        r = self.runtime
        remaining = self._observation_remaining(work)
        return r._observe_native(work, deadline_monotonic=r._clock() + min(MAX_WAIT, remaining))

    def issue(self, work: _Work) -> tuple[str, dict]:
        r, data = self.runtime, work.request
        r._check_lease()
        before = r._last_normal()
        if (r._current != before or r._prompt_phase is not None or r._exit_phase is not None
                or r._registered_lifecycle.phase is not None or r._registered_lifecycle.candidate is not None):
            raise ControlError("Handoff requires settled adopted normal play")
        launch = r._registered_lifecycle._owned()
        mark = launch.operator_mark
        # Prove complete successor representability while the original lease is
        # still live. Reserve one distinct source for the future post-Pause frame.
        refs, status = self._source_checker(MAX_HANDOFF_SOURCES - 1)
        try:
            unknown = None
            for identity in data["checkpoint_ids"]:
                if identity not in refs:
                    if unknown is None:
                        unknown = identity
                    continue
                if status(identity) != "retained":
                    raise EvidenceError("Handoff source unavailable: " + identity)
            if unknown is not None:
                raise HandoffEvidenceError(
                    "Handoff checkpoints require retained source observation IDs, not Claim/Work IDs; "
                    "unknown reference: " + unknown + ". Refused before stopping input; no handoff issued. "
                    "Select actual retained source IDs and submit a NEW request if still eligible.")
            unfinished = self._unfinished(status)
            packet = r._memory.context(r._coordinate_scope(before), "Complete unfinished Work for successor",
                max_bytes=MAX_HANDOFF_CONTEXT_BYTES - HANDOFF_CONTEXT_RESERVE,
                required_work_ids=frozenset(unfinished), support_source_ids=tuple(data["checkpoint_ids"]),
                source_status=status, cache=False, **r._clocks())
            if len(packet["sources"]) + len(packet["procedure_sources"]) >= MAX_HANDOFF_SOURCES:
                raise CapacityError("Complete handoff must reserve support for its future post-Pause frame")
            if set(data["unfinished_work_ids"]) != unfinished:
                raise HandoffEvidenceError(
                    "Handoff must identify every unfinished Work item, without extras or truncation. "
                    "Refused before stopping input; no handoff issued. Retrieve complete current Work and "
                    "submit a NEW request if still eligible.")
        except (CapacityError, HandoffEvidenceError) as exc:
            self._observation_remaining(work)  # A draft error cannot preserve spent ordinary time.
            if isinstance(exc, HandoffEvidenceError):
                raise
            raise HandoffEvidenceError("Handoff representation refused before stopping input: " + str(exc)) from exc
        r._check_lease()  # User Pause during source verification always wins.
        r.controller.stop_input()  # Internal stop; never cancel this handle or advance ledger epoch here.
        r._lease, r._map = None, None
        r._bindings.clear()
        self._empty(work, mark)
        r._capacity()
        state, received = self._observe(work)
        if (state["boundary"]["kind"] != "normal_play" or not state["paused"]
                or state["pause_origin"] in ("human", "fault") or state["session"] != before.session
                or state["takeover_generation"] != launch.takeover_generation):
            raise ControlError("Handoff Observe lost its internally paused same-character session")
        ref = r._ingest(state, received)
        r._publish_source(ref, authoritative=False)
        r._capture_memory(ref)
        self._empty(work, mark)
        live = r._live()
        if not same_native_state(live[0], state):
            raise EvidenceError("Handoff source changed before issuance")
        binding = dict(session=ref.session, revision=ref.revision, boundary_id=state["boundary"]["id"],
            pause_generation=live[1], takeover_generation=state["takeover_generation"], pause_origin=state["pause_origin"],
            post_pause_source_id=ref.observation_id, controller_boot_id=mark[0], operator_pause_generation=mark[1])
        result = r._ledger.issue_handoff(data["request_id"], binding=binding, now=r._wall())
        with r._metadata:
            r._check_cancelled(work)
            if r._pending_pauses or r._operator_mark() != mark:
                raise ControlError("Handoff receipt retained; continuation superseded by Pause")
            self.phase = HandoffPhase(data["request_id"], ref, mark, live[1], state["takeover_generation"], result["epoch"])
        return "completed", result

    def _unfinished(self, source_status: Callable[[str], str] | None = None) -> set[str]:
        r = self.runtime
        refs = r._memory._references()
        views, _ = r._memory._work_views(r._ledger.memory_records("work"), refs)
        if source_status is None:
            _, source_status = self._source_checker()
        return {identity for identity, entry in views.items() if entry["status"] not in ("completed", "failed")
            or any(source_status(s) != "retained" for s in entry["sources"])}

    def context_options(self) -> dict:
        """Only called after the live successor context binding has passed."""
        r, phase = self.runtime, self.phase
        issued = r._ledger.request(phase.handoff_id)["result"]
        _, status = self._source_checker()
        required = set(issued["unfinished_work_ids"]) | self._unfinished(status)
        return dict(required_work_ids=frozenset(required), source_status=status,
            support_source_ids=tuple(dict.fromkeys(issued["checkpoint_ids"] + [issued["post_pause_source_id"]])))

    def context_binding(self, work: _Work) -> dict | None:
        r, binding = self.runtime, work.request["handoff"]
        if binding is None:
            return None
        phase = self.phase
        if phase is None or binding["handoff_id"] != phase.handoff_id or phase.claim_request_id is not None:
            raise ControlError("Successor context requires its live unconsumed handoff")
        self.guard(work, phase, ledger_phase="handoff")
        issued = r._ledger.request(phase.handoff_id)["result"]
        if (binding["actor_role"] != issued["successor_role"]
                or binding["prospective_player_id"] == issued["original_player_id"]):
            raise ControlError("Context requires the prospective successor and issued role")
        if work.request["scope"] != r._coordinate_scope(phase.checkpoint):
            raise EvidenceError("Successor context requires the current adopted coordinate scope")
        return binding

    def guard(self, work: _Work, phase: HandoffPhase, proposal: _ResumeIntent | None = None,
              *, ledger_phase: str = "active") -> None:
        r = self.runtime
        self._empty(work, phase.operator_mark, dispatch=proposal is not None)
        state = r._ledger.snapshot(now=r._wall())
        live = r._live()
        expected = r._store.observation(phase.checkpoint)
        actual = live[0]
        if (self.phase is not phase or state["epoch"] != phase.epoch or state["phase"] != ledger_phase
                or state["unreconciled"] or state["pause_cause"] != "internal_handoff"
                or live[1] != phase.pause_generation or actual is None or not actual["paused"]
                or any(actual[key] != expected[key] for key in
                    ("session", "revision", "category", "boundary", "pause_origin", "takeover_generation"))
                or actual["takeover_generation"] != phase.takeover_generation
                or actual["pause_origin"] in ("human", "fault")):
            raise ControlError("Handoff lost its exact live epoch/source/controller/Pause binding")
        if proposal is not None and (proposal.kind != "resume" or proposal.before != phase.checkpoint):
            raise ControlError("Handoff permits only its separately charged exact Resume")

    def claim(self, work: _Work) -> tuple[str, dict]:
        r, data, phase = self.runtime, work.request, self.phase
        if phase is None or phase.claim_request_id is not None or data["handoff_id"] != phase.handoff_id:
            raise ControlError("Claim requires its live unconsumed handoff")
        self.guard(work, phase, ledger_phase="handoff")
        issued = r._ledger.request(phase.handoff_id)["result"]
        binding = dict(handoff_id=phase.handoff_id, prospective_player_id=data["player_id"], actor_role=data["actor_role"])
        packets = []
        for identity in data["packet_ids"]:
            wrapper = r._issued_packets.get(identity)
            if (wrapper is None or wrapper["handoff"] != binding or wrapper["epoch"] != phase.epoch
                    or wrapper["packet"]["memory_version"] != r._memory_version):
                raise HandoffEvidenceError("Claim requires fresh-version successor-bound issued context packets")
            packets.append(wrapper["packet"])
        refs, status = self._source_checker()
        def retained(identity: str) -> EvidenceRef:
            if status(identity) != "retained":
                raise EvidenceError("Handoff source unavailable: " + identity)
            return refs[identity]
        represented_work = {entry["id"] for packet in packets for entry in packet["work"]}
        required_work = set(issued["unfinished_work_ids"]) | self._unfinished(status)
        if len(required_work) > 16:
            raise HandoffEvidenceError("Claim unfinished Work bound exceeded; no truncated handoff")
        if not required_work <= represented_work:
            raise HandoffEvidenceError("Claim context omits unfinished Work; retrieve another bounded packet")
        allowed = set(issued["checkpoint_ids"]) | {issued["post_pause_source_id"]}
        allowed.update(source["id"] for packet in packets for source in packet["sources"])
        needed = set(issued["checkpoint_ids"]) | {issued["post_pause_source_id"]}
        for packet in packets:
            sources = {source["id"]: source for source in packet["sources"]}
            for entry in packet["work"]:
                if entry["id"] not in required_work:
                    continue
                for identity in entry["sources"]:
                    if identity not in sources:
                        raise HandoffEvidenceError("Work packet omitted a source disposition")
                    if sources[identity]["status"] == "retained":
                        try:
                            retained(identity)
                        except EvidenceError as exc:
                            raise HandoffEvidenceError("Work source changed after retrieval; retrieve its unknown disposition") from exc
                        needed.add(identity)
                    elif entry["status"] != "unknown":
                        raise HandoffEvidenceError("Lost Work source requires an explicit unknown context disposition")
        if not set(data["read_source_ids"]) <= allowed or not needed <= set(data["read_source_ids"]):
            raise HandoffEvidenceError("Claim read declarations must cover checkpoints/retained Work support and refer to issued sources")
        for identity in data["read_source_ids"]:
            retained(identity)
        required_procedures = {tuple(sorted(source.items())) for packet in packets for source in packet["procedure_sources"]}
        declared_procedures = {tuple(sorted(source.items())) for source in data["read_procedure_sources"]}
        if declared_procedures != required_procedures:
            raise HandoffEvidenceError("Claim must declare exact complete procedure support from issued packets")
        if len(data["read_source_ids"]) + len(declared_procedures) > MAX_HANDOFF_SOURCES:
            raise HandoffEvidenceError("Claim aggregate current/historical source bound exceeded")
        for source in data["read_procedure_sources"]:
            metadata, _ = r._memory.procedure_source(source["mission_id"], source["source_id"])
            if metadata["disposition"] != "retained":
                raise HandoffEvidenceError("Claim procedure support is no longer retained")
        self.guard(work, phase, ledger_phase="handoff")
        result = r._ledger.consume_handoff(data["request_id"], actor_id=data["player_id"], actor_role=data["actor_role"], now=r._wall())
        with r._metadata:
            r._check_cancelled(work)
            if self.phase is not phase or r._pending_pauses:
                raise ControlError("Claim receipt retained; continuation superseded by Pause")
            self.phase = replace(phase, claim_request_id=data["request_id"])
        return "completed", result

    def readmit(self, work: _Work) -> tuple[str, dict]:
        r, data, phase = self.runtime, work.request, self.phase
        if (phase is None or phase.claim_request_id != data["claim_request_id"]
                or phase.handoff_id != data["handoff_id"]):
            raise ControlError("Readmission requires its live exact claimed handoff; history restores no consent")
        self.guard(work, phase, ledger_phase="paused")
        if r._game_cost is None or r._game_cost >= r._admission.limits.game_seconds:
            raise LedgerError("Readmission cannot renew original game-time budget")
        r._capacity()
        state, received = self._observe(work)
        ref = r._ingest(state, received)
        if not r._store.equivalent(phase.checkpoint, ref, rule="exact_png_bytes"):
            raise EvidenceError("Readmission changed the paused handoff checkpoint")
        phase = replace(phase, checkpoint=ref)
        with r._metadata:
            r._check_cancelled(work)
            self.phase = phase
        r._current = ref
        r._ledger.activate(epoch=phase.epoch, player_id=r._ledger.snapshot(now=r._wall())["player_id"], now=r._wall())
        proposal = r._resume_intent(data["request_id"], ref)
        feedback = r._dispatch(work, proposal, ref, lifecycle=phase)
        r._check_cancelled(work)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, "source_ids": [ref.observation_id], "grants_authority": False}
        after = r._store.observation(feedback.after)
        r._game_guard(ref, data["limits"]["game_seconds"], after=True)
        if (after["paused"] or after["session"] != ref.session or after["boundary"]["kind"] != "normal_play"
                or phase.operator_mark != r._operator_mark() or after["takeover_generation"] != phase.takeover_generation):
            raise ControlError("Readmission lost its same adopted normal session")
        actor = r._ledger.snapshot(now=r._wall())["player_id"]
        r._lease = r.controller.acquire_mission(r._admission.mission_id, phase.epoch, actor, operation="interaction",
            expected_session=after["session"], expected_revision=after["revision"], expected_boundary_id=after["boundary"]["id"])
        r._publish_source(feedback.after, authoritative=True)
        r._capture_memory(feedback.after)
        with r._metadata:
            r._check_cancelled(work)
            if self.phase is not phase:
                raise ControlError("Readmission superseded by Pause")
            self.phase = None
        issued = r._ledger.request(phase.handoff_id)["result"]
        return "completed", {"readmission": dict(schema=VERSION, record_type="Readmission",
            mode="handoff",
            handoff_id=phase.handoff_id, claim_request_id=phase.claim_request_id, player_id=actor, epoch=phase.epoch,
            post_pause_source_id=issued["post_pause_source_id"], revalidated_source_id=ref.observation_id,
            after_source_id=feedback.after.observation_id, logical_id=proposal.logical_id, grants_authority=False),
            "source_ids": [ref.observation_id, feedback.after.observation_id],
            "reason": "Deliberate charged Resume; fresh successor lease, not restored authority", "grants_authority": False}
