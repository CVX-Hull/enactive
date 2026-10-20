"""Private paused activity composition; all inputs use the mission writer/ledger.

Control ACKs are transport evidence even without a rendered after-frame. This
adapter never treats them as sleep, cancellation, craft or Work completion.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from typing import Any

from .controller import ControlError, validate_control_request, validate_control_response
from .gameplay.contracts import ContractError, EvidenceRef
from .gameplay.evidence import EvidenceError
from .gameplay.mission_ledger import BudgetError


@dataclass(frozen=True)
class ActivityIntent:
    logical_id: str
    before: EvidenceRef
    expected_boundary_id: str
    kind: str
    action: dict | None
    control_generation: int
    revalidation: None = None


@dataclass(frozen=True)
class ActivityFeedback:
    """Delivery-only result, deliberately distinct from a movement after-frame."""
    before: EvidenceRef
    after: EvidenceRef | None
    transport_disposition: str
    reason: str
    raw: dict | None


@dataclass(frozen=True)
class ActivityPhase:
    prompt: Any
    checkpoint: EvidenceRef
    generation: int
    control_generation: int
    interrupt_id: str | None = None
    minimum_revision: int = 0
    needs_observation: bool = False
    answered: bool = False

    @property
    def operator_mark(self):
        return self.prompt.controller_boot_id, self.prompt.operator_generation

    @property
    def takeover_generation(self):
        return self.prompt.takeover_generation


class RegisteredActivity:
    def __init__(self, runtime):
        self.runtime = runtime
        self.phase: ActivityPhase | None = None

    def revoke(self):
        self.phase = None

    def guard(self, work, phase: ActivityPhase, proposal=None):
        r = self.runtime
        r._check_cancelled(work)
        ledger = r._ledger.snapshot(now=r._wall())
        state, generation, boot, lease, _, pending = r._live()
        if (self.phase is not phase or phase.operator_mark != r._operator_mark()
                or (ledger["epoch"], ledger["player_id"], ledger["phase"]) !=
                   (phase.prompt.epoch, phase.prompt.actor_id, "active") or ledger["unreconciled"]
                or state is None or boot != phase.operator_mark[0] or generation != phase.generation
                or lease is not None or r._lease is not None or pending
                or state["session"] != phase.checkpoint.session or not state["paused"]
                or state["takeover_generation"] != phase.takeover_generation
                or state["boundary"]["control_generation"] != phase.control_generation
                or state["pause_origin"] in ("human", "fault")
                or r.controller.frozen and (not phase.needs_observation or r.controller.transport_error)
                or state["revision"] < max(phase.minimum_revision, phase.checkpoint.revision)):
            raise ControlError("Activity recovery crossed its original actor/Pause/native authority")
        root = r._ledger.request(phase.prompt.root_id)
        if r._wall() >= root["deadline"]:
            raise BudgetError("Original activity root deadline exhausted")
        r._game_guard(phase.prompt.game_anchor, root["request"]["limits"]["game_seconds"])
        if work.request["kind"] == "skill":
            r._game_guard(phase.prompt.game_anchor, work.request["limits"]["game_seconds"])
        if r._game_cost is None or r._game_cost >= r._admission.limits.game_seconds:
            raise BudgetError("Original observed mission game budget exhausted")
        if proposal is not None and proposal.before != phase.checkpoint:
            raise EvidenceError("Activity dispatch lost its private paused checkpoint")

    def _deadline(self, work, phase):
        r = self.runtime
        deadline = min(r._ledger.request(phase.prompt.root_id)["deadline"],
                       r._ledger.request(work.request["request_id"])["deadline"],
                       r._mission_deadline - r._admission.cleanup_reserve.wall_seconds)
        if deadline <= r._wall():
            raise BudgetError("Original activity observation deadline exhausted")
        return r._clock() + deadline - r._wall()

    def _replace(self, work, before, after):
        r = self.runtime
        with r._metadata:
            r._check_cancelled(work)
            if self.phase is not before or r._pending_pauses:
                raise ControlError("Activity transition superseded by Pause")
            self.phase = after
        return after

    def _request_source(self, data, phase):
        r = self.runtime
        observed = r._store.observation(phase.checkpoint)
        if (data["phase_id"] != phase.prompt.root_id or phase.checkpoint != r._current
                or phase.checkpoint.observation_id not in data["sources"]
                or (data["expected_session"], data["expected_revision"], data["expected_boundary_id"]) !=
                   (phase.checkpoint.session, phase.checkpoint.revision, observed["boundary"]["id"])):
            raise EvidenceError("Activity child requires its exact published paused source")

    def _result(self, phase, *, reason, feedback=None):
        r = self.runtime
        source = r._store.observation(phase.checkpoint)
        kind = source["boundary"]["kind"]
        stage = ("interrupt_confirmation" if kind == "interrupt_confirmation" else
                 "activity_poll" if kind == "activity_poll" else "awaiting_readmission")
        prompt = replace(phase.prompt, checkpoint=phase.checkpoint)
        result = {"source_ids": [phase.checkpoint.observation_id], "phase": r._prompt_receipt(prompt, stage),
                  "verification_required": True, "grants_authority": False, "reason": reason,
                  "interrupt_request_id": phase.interrupt_id}
        if feedback is not None:
            result["transport_disposition"] = feedback.transport_disposition
        return result

    def observe(self, work):
        r, phase = self.runtime, self.phase
        self.guard(work, phase)
        r._capacity()
        state, received = r._observe_native(work, deadline_monotonic=self._deadline(work, phase))
        self.guard(work, phase)
        if (state["session"] != phase.checkpoint.session or not state["paused"]
                or state["revision"] < max(phase.minimum_revision, phase.checkpoint.revision)
                or state["takeover_generation"] != phase.takeover_generation
                or state["boundary"]["control_generation"] != phase.control_generation
                or state["boundary"]["kind"] not in ("normal_play", "menu", "activity_poll", "interrupt_confirmation")
                or state["boundary"]["kind"] == "interrupt_confirmation"
                   and state["boundary"]["interrupt_request_id"] != phase.interrupt_id):
            raise ControlError("Paused activity observation changed identity/control or interrupt owner")
        ref = r._ingest(state, received)
        advanced = replace(phase, checkpoint=ref, needs_observation=False,
            interrupt_id=None if phase.answered and ref.boundary_kind != "interrupt_confirmation" else phase.interrupt_id,
            answered=phase.answered and ref.boundary_kind == "interrupt_confirmation")
        self._replace(work, phase, advanced)
        r._publish_source(ref, authoritative=False)
        r._capture_memory(ref)
        self.guard(work, advanced)
        return self._result(advanced, reason="Activity recovery observed; no Resume or semantic success")

    def _begin(self, work):
        r, data = self.runtime, work.request
        prompt = r._prompt_phase
        if prompt is None:
            raise ControlError("Interrupt requires its actual live activity root")
        original = prompt.checkpoint
        prompt = r._prompt_guard(data, original)
        if prompt is None or original.boundary_kind != "activity_poll" or not data["goal"]["interrupt_allowed"]:
            raise ControlError("Interrupt requires its permitted live activity poll")
        self._request_source(data, ActivityPhase(prompt, original, r._live()[1], 0))
        r.controller.stop_input()
        r._lease, r._rotation = None, None
        r._bindings.clear()
        phase = ActivityPhase(prompt, original, r._live()[1],
                              r._store.observation(original)["boundary"]["control_generation"])
        with r._metadata:
            r._check_cancelled(work)
            if r._prompt_phase is not prompt or phase.operator_mark != r._operator_mark():
                raise ControlError("Activity stop superseded by Pause")
            r._prompt_phase = None
            self.phase = phase
        # Internal stop is not an operator Pause and does not renew the ledger.
        # Observe is allowed to see natural completion before interrupt publication.
        r._capacity()
        state, received = r._observe_native(work, deadline_monotonic=r._deadline(work, original))
        self.guard(work, phase)
        if state["revision"] < original.revision:
            raise ControlError("Activity observation regressed before interruption")
        ref = r._ingest(state, received)
        phase = self._replace(work, phase, replace(phase, checkpoint=ref))
        r._publish_source(ref, authoritative=False)
        r._record("mission_activity_stop", {"root_id": prompt.root_id,
            "before": original.observation_id, "paused_source": ref.observation_id,
            "operator_mark": list(phase.operator_mark), "grants_authority": False})
        return phase

    def execute(self, work):
        r, data = self.runtime, work.request
        step = data["goal"]["step"]
        phase = self.phase
        if phase is None:
            if step != "interrupt":
                raise ControlError("Activity recovery has no live paused phase")
            phase = self._begin(work)
        else:
            self.guard(work, phase)
            self._request_source(data, phase)
        if step == "poll":
            return "partial", self.observe(work)
        self.guard(work, phase)
        source = r._store.observation(phase.checkpoint)
        if step == "resume":
            return self._resume(work, phase)
        if step == "interrupt":
            if source["boundary"]["kind"] in ("normal_play", "menu"):
                return "partial", self._result(phase, reason="Activity ended before interruption; separate Resume required")
            if source["boundary"]["kind"] != "activity_poll" or phase.interrupt_id is not None:
                raise ControlError("Interrupt requires a poll without an earlier interrupt owner")
            kind, value = "request_interrupt", None
        elif step == "answer_interrupt":
            if (source["boundary"]["kind"] != "interrupt_confirmation"
                    or phase.interrupt_id is None or phase.answered or data["goal"]["interrupt_request_id"] != phase.interrupt_id
                    or source["boundary"]["interrupt_request_id"] != phase.interrupt_id):
                raise ControlError("Answer requires its exact returned interrupt owner")
            kind = "answer_interrupt"
            value = {"interrupt_request_id": phase.interrupt_id, "choice": data["goal"]["answer"]}
        else:
            raise ControlError("Unsupported paused activity step")
        proposal = ActivityIntent("activity-" + hashlib.sha256(data["request_id"].encode()).hexdigest(),
            phase.checkpoint, source["boundary"]["id"], kind, value, phase.control_generation)
        feedback = r._dispatch(work, proposal, phase.checkpoint, activity=phase)
        if work.cancelled.is_set() or r._closed.is_set():
            return ("unknown" if feedback.transport_disposition == "unknown" else "paused"), {
                "reason": "Activity authority revoked; actual delivery receipt retained",
                "source_ids": [phase.checkpoint.observation_id], "grants_authority": False}
        if feedback.transport_disposition != "returned":
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, "source_ids": [phase.checkpoint.observation_id], "grants_authority": False}
        r._check_cancelled(work)
        raw = feedback.raw
        native = raw["result"]["state"]
        live = r._live()
        expected_generation = phase.generation + int(native["boundary"]["control_generation"] != phase.control_generation)
        if (self.phase is not phase or phase.operator_mark != r._operator_mark() or live[0] != native
                or live[1] != expected_generation or r.controller.transport_error or live[3] is not None or live[5]):
            raise ControlError("Activity ACK retained; later authority or persistence fault blocks continuation")
        owner = raw["request"]["id"] if raw["result"]["status"] == "prompt_opened" else phase.interrupt_id
        advanced = replace(phase, generation=expected_generation,
                           control_generation=native["boundary"]["control_generation"], interrupt_id=owner,
                           minimum_revision=native["revision"], answered=kind == "answer_interrupt",
                           needs_observation=feedback.after is None or r.controller.frozen,
                           checkpoint=feedback.after or phase.checkpoint)
        self._replace(work, phase, advanced)
        if advanced.needs_observation:
            # ACK and effect observation are separate; this is read-only, bounded,
            # and never an implicit retry or Resume.
            return "partial", self.observe(work)
        r._publish_source(feedback.after, authoritative=False)
        r._capture_memory(feedback.after)
        return "partial", self._result(advanced, reason="Activity control delivered; actual effect requires interpretation", feedback=feedback)

    def _resume(self, work, phase):
        r = self.runtime
        self.guard(work, phase)
        source = r._store.observation(phase.checkpoint)
        if source["boundary"]["kind"] not in ("normal_play", "menu"):
            raise ControlError("Activity Resume requires a fresh paused normal/menu boundary")
        feedback = r._dispatch(work, r._resume_intent(work.request["request_id"], phase.checkpoint),
                               phase.checkpoint, activity=phase)
        if work.cancelled.is_set() or r._closed.is_set():
            return ("unknown" if feedback.transport_disposition == "unknown" else "paused"), {
                "reason": "Activity Resume authority revoked; actual receipt retained",
                "source_ids": [phase.checkpoint.observation_id], "grants_authority": False}
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, "source_ids": [phase.checkpoint.observation_id], "grants_authority": False}
        after = r._store.observation(feedback.after)
        ledger = r._ledger.snapshot(now=r._wall())
        if (self.phase is not phase or phase.operator_mark != r._operator_mark() or after["paused"]
                or after["session"] != phase.checkpoint.session or after["takeover_generation"] != phase.takeover_generation
                or (ledger["epoch"], ledger["player_id"]) != (phase.prompt.epoch, phase.prompt.actor_id)):
            raise ControlError("Activity Resume cannot adopt changed authority/session")
        r._game_guard(phase.prompt.game_anchor, r._ledger.request(phase.prompt.root_id)["request"]["limits"]["game_seconds"], after=True)
        r._game_guard(phase.prompt.game_anchor, work.request["limits"]["game_seconds"], after=True)
        if r._game_cost is None or r._game_cost > r._admission.limits.game_seconds:
            raise BudgetError("Observed activity Resume exceeded original mission game budget")
        self._deadline(work, phase)
        r._lease = r.controller.acquire_mission(r._admission.mission_id, phase.prompt.epoch, phase.prompt.actor_id,
            operation="interaction", expected_session=after["session"], expected_revision=after["revision"],
            expected_boundary_id=after["boundary"]["id"])
        self._deadline(work, phase)
        r._check_cancelled(work)
        r._publish_source(feedback.after, authoritative=True)
        advanced = replace(phase.prompt, checkpoint=feedback.after)
        with r._metadata:
            r._check_cancelled(work)
            if self.phase is not phase or r._pending_pauses:
                raise ControlError("Activity resumed receipt retained; user Pause prevents new phase")
            self.phase = None
            r._prompt_phase = advanced if feedback.after.boundary_kind == "menu" else None
        r._capture_memory(feedback.after)
        return "partial", {"source_ids": [feedback.after.observation_id],
            "phase": r._prompt_receipt(advanced, "awaiting_control" if r._prompt_phase else "complete"),
            "verification_required": True, "grants_authority": False,
            "reason": "Separate charged Resume returned; task/rest/craft success remains interpretive"}

    def envelope(self, raw, proposal, preflight):
        """Validate ACK correlation, independently of a usable rendered after-state."""
        r = self.runtime
        fields = {"logical_action_id", "request", "result", "published", "received_monotonic", "preflight"}
        if type(raw) is not dict or set(raw) != fields or raw["logical_action_id"] != proposal.logical_id or type(raw["published"]) is not bool:
            raise ContractError("Malformed exact activity receipt envelope")
        request, result = raw["request"], raw["result"]
        if type(result) is not dict:
            raise ContractError("Activity receipt lacks terminal result")
        if request is not None:
            validate_control_request(request)
            if (request["kind"] != proposal.kind or request["session"] != proposal.before.session
                    or request["control_generation"] != proposal.control_generation
                    or proposal.kind == "answer_interrupt" and any(request.get(k) != v for k, v in {
                        "revision": proposal.before.revision, "boundary_id": proposal.expected_boundary_id,
                        **proposal.action}.items())):
                raise ContractError("Activity request contradicts its immutable proposal")
        proof = raw["preflight"]
        if request is not None or raw["published"]:
            if (type(proof) is not dict or set(proof) != {"observation", "received_monotonic", "expected_image_sha256"}
                    or preflight is None or proof["expected_image_sha256"] != proposal.before.frame_sha256
                    or proof["received_monotonic"] != preflight.received_monotonic
                    or r._store.observation(preflight) != proof["observation"]
                    or proposal.kind == "answer_interrupt" and request["frame"] != proof["observation"]["frame"]):
                raise ContractError("Activity publication lacks exact retained preflight")
        if not raw["published"]:
            if raw["received_monotonic"] is not None or result.get("status") in ("prompt_opened", "answer_delivered", "not_applicable", "dispatched"):
                raise ContractError("Unpublished activity receipt contradicts terminal delivery")
            return "not_dispatched", str(result.get("error") or "Proven unpublished activity control")[:1024]
        if request is None or result.get("id") != request["id"]:
            raise ContractError("Activity result lost its exact native request identity")
        if result.get("status") not in ("prompt_opened", "answer_delivered", "not_applicable", "rejected"):
            return "unknown", str(result.get("error") or "Activity control acknowledgment unknown")[:1024]
        validate_control_response(result, request["id"])
        allowed = {"request_interrupt": ("prompt_opened", "not_applicable", "rejected"),
                   "answer_interrupt": ("answer_delivered", "rejected")}[proposal.kind]
        received = raw["received_monotonic"]
        if (result["status"] not in allowed or type(received) not in (int, float) or not math.isfinite(received)
                or not preflight.received_monotonic <= received <= r._clock()):
            raise ContractError("Activity terminal receipt lost operation or original clock")
        state = result["state"]
        if result["status"] != "rejected" and (state["session"] != proposal.before.session or not state["paused"]
                or state["takeover_generation"] != r._store.observation(proposal.before)["takeover_generation"]
                or state["boundary"]["control_generation"] < proposal.control_generation
                or result["status"] != "not_applicable" and state["boundary"]["control_generation"] <= proposal.control_generation):
            raise ContractError("Activity receipt crossed native session/control/takeover")
        return ("rejected" if result["status"] == "rejected" else "returned"), "Exact activity terminal ACK; semantic effect unverified"
