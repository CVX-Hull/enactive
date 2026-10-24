"""Bounded injected planning; candidates are data and grant no execution authority.

A port belongs to one immutable TaskSpec and its original admission clock (seconds;
use ``admission_monotonic * 1000`` in the evaluation manifest). Submit a
PlanningRequest, then poll its call ID with the caller's current PlanningBinding.
The trusted provider accepts only ProviderInput and a cooperative threading.Event.
It must honor the explicit token ceilings; byte counts are not token estimates.

``snapshot(cutoff_monotonic=...)`` produces one evaluation event per invocation.
Record that snapshot once into a RunRecorder, alongside other events in timestamp
order. Later snapshots belong in separately named artifacts. This module performs
no I/O, model selection, dispatch, retries, journal restoration or live API calls.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
import math
import threading
import time
from typing import Callable, Literal, Protocol
from uuid import uuid4

from .contracts import (
    ContractError, EvidencePacket, EvidenceRef, PlanCandidate, SkillDescriptor, Stage, TaskSpec,
)


def _number(value: object, name: str, maximum: float = 1e12, *, positive: bool = False) -> None:
    if (type(value) not in (int, float) or value < 0 or value > maximum
            or not math.isfinite(value) or (positive and value == 0)):
        raise ContractError(f"{name} must be finite and within bounds")


def _integer(value: object, name: str, maximum: int, minimum: int = 0) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError(f"{name} must be an integer within bounds")


def _text(value: object, name: str, maximum: int = 128) -> None:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise ContractError(f"{name} must be bounded nonempty text")


@dataclass(frozen=True)
class PlannerConfig:
    model_id: str
    configuration_id: str
    mode: Literal["fixture", "network", "external"] = "fixture"
    max_context_bytes: int = 1_048_576
    max_reply_bytes: int = 16_384
    max_input_tokens: int = 32_768
    max_output_tokens: int = 2_048
    max_calls: int = 10
    call_timeout_seconds: float = 30.0
    reservation_usd_per_call: float = 0.0
    spend_ceiling_usd: float = 0.0
    credentials_available: bool = False
    bounded_pricing: bool = False
    operator_approved_spend: bool = False

    def __post_init__(self) -> None:
        _text(self.model_id, "model_id")
        _text(self.configuration_id, "configuration_id")
        if self.mode not in ("fixture", "network", "external"):
            raise ContractError("Unknown planner mode")
        for name in ("max_context_bytes", "max_reply_bytes"):
            _integer(getattr(self, name), name, 1_048_576, 1)
        for name in ("max_input_tokens", "max_output_tokens"):
            _integer(getattr(self, name), name, 1_048_576, 1)
        _integer(self.max_calls, "max_calls", 10, 1)
        _number(self.call_timeout_seconds, "call_timeout_seconds", 30, positive=True)
        for name in ("reservation_usd_per_call", "spend_ceiling_usd"):
            _number(getattr(self, name), name, 1_000_000)
        if self.mode == "external" and (self.reservation_usd_per_call != 0 or self.spend_ceiling_usd != 0):
            raise ContractError("External chat accepts only zero API reservation and spend")
        for name in ("credentials_available", "bounded_pricing", "operator_approved_spend"):
            if type(getattr(self, name)) is not bool:
                raise ContractError(f"{name} must be boolean")


@dataclass(frozen=True)
class PlanningBinding:
    task_id: str
    task_version: int
    plan_id: str
    plan_version: int
    execution_epoch: int
    evidence_session: str
    evidence_revision: int
    expected_stage: Stage
    distance_remaining: int

    def __post_init__(self) -> None:
        for name in ("task_id", "plan_id", "evidence_session"):
            _text(getattr(self, name), name)
        for name in ("task_version", "plan_version"):
            _integer(getattr(self, name), name, 2**31 - 1, 1)
        for name in ("execution_epoch", "evidence_revision"):
            _integer(getattr(self, name), name, 2**63 - 1)
        _integer(self.distance_remaining, "distance_remaining", 4, 1)
        if self.expected_stage not in ("outbound", "return"):
            raise ContractError("Unknown expected stage")


@dataclass(frozen=True)
class PlanningRequest:
    task: TaskSpec
    packet: EvidencePacket
    skills: tuple[SkillDescriptor, ...]
    plan_version: int
    execution_epoch: int
    expected_stage: Stage
    distance_remaining: int
    admission_monotonic: float
    public_context: str = ""

    def __post_init__(self) -> None:
        if type(self.task) is not TaskSpec or type(self.packet) is not EvidencePacket:
            raise ContractError("Request requires typed task and packet")
        self.task.__post_init__()
        self.packet.__post_init__()
        _number(self.admission_monotonic, "admission_monotonic", 1e12)
        if (type(self.skills) is not tuple or not 1 <= len(self.skills) <= 32
                or any(type(skill) is not SkillDescriptor for skill in self.skills)):
            raise ContractError("Supply a nonempty bounded tuple of accepted skills")
        identities = set()
        for skill in self.skills:
            skill.__post_init__()
            if (skill.skill_id, skill.skill_version) in identities:
                raise ContractError("Duplicate skill identity")
            identities.add((skill.skill_id, skill.skill_version))
            if (self.expected_stage not in skill.stage_kinds or self.task.kind not in skill.task_kinds
                    or "normal_play" not in skill.contexts):
                raise ContractError("Supplied skill does not support the request")
        if type(self.public_context) is not str or len(self.public_context) > 4096:
            raise ContractError("Public context must be bounded text")
        self.binding  # Validate the scalar binding even before provider admission.
        if (self.packet.task_id != self.task.task_id
                or self.packet.current.session != self.task.session
                or self.packet.current.boundary_kind != "normal_play"
                or self.distance_remaining > self.task.distance):
            raise ContractError("Request task, route or evidence mismatch")
        if self.expected_stage == "return" and self.packet.waypoint is None:
            raise ContractError("Return planning requires retained waypoint evidence")

    @property
    def binding(self) -> PlanningBinding:
        return PlanningBinding(self.task.task_id, self.task.task_version, self.packet.plan_id,
                               self.plan_version, self.execution_epoch, self.packet.current.session,
                               self.packet.current.revision, self.expected_stage,
                               self.distance_remaining)


@dataclass(frozen=True)
class ProviderInput:
    """Immutable JSON data snapshot; contains no controller or filesystem handles."""
    request_json: str
    model_id: str
    configuration_id: str
    mode: Literal["fixture", "network", "external"]
    max_context_bytes: int
    max_reply_bytes: int
    max_input_tokens: int
    max_output_tokens: int


@dataclass(frozen=True)
class ProviderUsage:
    """Observed metrics; None means unknown. Untrusted values are checked on return."""
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class ProviderReply:
    candidate_json: str | bytes
    usage: ProviderUsage | None = None


class Provider(Protocol):
    def __call__(self, snapshot: ProviderInput, cancelled: threading.Event) -> ProviderReply: ...


@dataclass(frozen=True)
class CallResult:
    call_id: str
    status: str
    reason: str
    candidate: PlanCandidate | None


@dataclass(frozen=True)
class CallAccounting:
    call_id: str
    status: str
    reason: str
    invoked_monotonic: float
    stop_monotonic: float | None
    completed_monotonic: float | None
    settled_monotonic: float | None
    observed_usage: ProviderUsage
    usage_missing_reason: str | None
    unresolved_reservation_usd: float
    reserved_usd: float
    overshoot_usd: float | None
    overshoot_missing_reason: str | None
    duration_censored: bool


@dataclass(frozen=True)
class AuditRejection:
    monotonic: float
    reason: str


@dataclass(frozen=True)
class AccountingSnapshot:
    cutoff_monotonic: float
    admission_monotonic: float
    calls: tuple[CallAccounting, ...]
    rejections: tuple[AuditRejection, ...]
    rejection_count: int
    dropped_rejection_count: int
    committed_usd: float
    unresolved_reservation_usd: float
    physical_call_active: bool
    frozen: bool
    _events_json: tuple[str, ...] = field(repr=False)

    def evaluation_events(self) -> tuple[dict, ...]:
        """Independent JSON objects, one per invoked call, sorted for RunRecorder."""
        return tuple(json.loads(event) for event in self._events_json)


@dataclass
class _Call:
    call_id: str
    request: PlanningRequest
    invoked: float
    deadline: float
    reservation: float
    cancelled: threading.Event = field(default_factory=threading.Event)
    status: str = "pending"
    reason: str = "Provider pending"
    candidate: PlanCandidate | None = None
    stopped: float | None = None
    completed: float | None = None
    settled: float | None = None
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    usage_reason: str | None = "Provider usage unresolved"
    overshoot: float | None = None
    overshoot_reason: str | None = "Provider cost unresolved"


class PlannerPort:
    """One task, ten lifetime calls and one physical daemon slot, even after stop.

    Inject ``clock`` only for controlled testing. Production uses monotonic time;
    no operation waits for provider completion. Rejected submits raise ContractError
    and enter a bounded audit ring; they never become model-call events. The first
    successful submission pins its immutable packet.start for every continuation.
    """
    def __init__(self, task: TaskSpec, config: PlannerConfig, provider: Provider, *,
                 admission_monotonic: float, clock: Callable[[], float] = time.monotonic):
        if type(task) is not TaskSpec or type(config) is not PlannerConfig or not callable(provider):
            raise ContractError("Port requires typed task, configuration and callable provider")
        task.__post_init__()
        _number(admission_monotonic, "admission_monotonic", 1e12)
        self._task, self._config, self._provider = task, config, provider
        self._admission, self._clock = admission_monotonic, clock
        self._lock = threading.Lock()
        self._calls: dict[str, _Call] = {}
        self._rejections: deque[AuditRejection] = deque(maxlen=64)
        self._rejection_count = 0
        self._active: str | None = None
        self._start: EvidenceRef | None = None
        self._turn_ceiling: int | None = None
        self._call_ceiling = min(10, config.max_calls, task.budgets.planner_calls)
        self._spend_ceiling = min(config.spend_ceiling_usd, task.budgets.spend_usd)
        self._wall_deadline = admission_monotonic + task.budgets.wall_seconds
        self._closed = False
        self._frozen = False
        self._last_time = admission_monotonic
        self._now()  # Reject future admission and invalid clock before accepting work.

    def _now(self) -> float:
        now = self._clock()
        _number(now, "monotonic clock", 1e12)
        if now < self._last_time:
            raise ContractError("Admission is in the future or monotonic clock regressed")
        self._last_time = now
        return now

    def _reject(self, now: float, reason: str) -> None:
        self._rejection_count += 1
        self._rejections.append(AuditRejection(now, reason))
        raise ContractError(reason)

    def _committed(self) -> float:
        return math.fsum(call.usage.cost_usd if call.settled is not None and call.usage.cost_usd is not None else call.reservation
                         for call in self._calls.values())

    def _stop(self, call: _Call, status: str, reason: str, now: float) -> None:
        call.status, call.reason, call.candidate = status, reason, None
        if call.stopped is None:
            call.stopped = now
        call.cancelled.set()

    def _expire(self, call: _Call, now: float) -> None:
        if call.status in ("pending", "completed"):
            if now >= self._wall_deadline:
                self._stop(call, "timed_out", "Task lifetime exhausted", now)
            elif call.status == "pending" and now >= call.deadline:
                self._stop(call, "timed_out", "Planner call deadline exhausted", now)

    def submit(self, request: PlanningRequest) -> str:
        with self._lock:
            now = self._now()
            for call in self._calls.values():
                self._expire(call, now)
            if type(request) is not PlanningRequest:
                self._reject(now, "Expected immutable PlanningRequest")
            if request.task != self._task or request.admission_monotonic != self._admission:
                self._reject(now, "Task identity, specification or admission origin changed")
            if self._start is not None and request.packet.start != self._start:
                self._reject(now, "Initial task start evidence cannot be replaced")
            if self._closed or self._frozen:
                self._reject(now, "Planner port is closed or frozen")
            if self._active is not None:
                self._reject(now, "Physical provider slot remains occupied")
            config, budgets, remaining = self._config, self._task.budgets, request.packet.remaining_budgets
            start = self._start or request.packet.start
            turn_ceiling = min(start.turn + budgets.turns,
                               request.packet.current.turn + remaining.turns,
                               self._turn_ceiling if self._turn_ceiling is not None
                               else start.turn + budgets.turns)
            call_ceiling = min(self._call_ceiling, len(self._calls) + remaining.planner_calls)
            spend_ceiling = min(self._spend_ceiling, self._committed() + remaining.spend_usd)
            wall_deadline = min(self._wall_deadline, now + remaining.wall_seconds)
            if (now >= wall_deadline or len(self._calls) >= call_ceiling
                    or remaining.primitives <= 0 or remaining.primitives_per_stage <= 0
                    or remaining.turns <= 0 or request.packet.current.turn < start.turn
                    or request.packet.current.turn >= turn_ceiling):
                self._reject(now, "Planner lifetime call or time budget exhausted")
            timeout = min(config.call_timeout_seconds, budgets.planner_call_seconds,
                          remaining.planner_call_seconds, remaining.wall_seconds,
                          wall_deadline - now)
            if timeout <= 0:
                self._reject(now, "No planner call time remains")
            if config.mode == "network" and not (
                    config.credentials_available and config.bounded_pricing
                    and config.operator_approved_spend and config.spend_ceiling_usd > 0
                    and config.reservation_usd_per_call > 0):
                self._reject(now, "Network credentials, bounded pricing or approved spend unavailable")
            reservation = config.reservation_usd_per_call
            if self._committed() + reservation > spend_ceiling:
                self._reject(now, "Conservative reservation exceeds remaining spend")
            payload = {"task": request.task.to_dict(), "packet": request.packet.to_dict(),
                       "skills": [skill.to_dict() for skill in request.skills],
                       "binding": vars(request.binding), "public_context": request.public_context,
                       "admission_monotonic": self._admission}
            encoded = json.dumps(payload, allow_nan=False, ensure_ascii=True, separators=(",", ":"))
            if len(encoded.encode()) > config.max_context_bytes:
                self._reject(now, "Planner context exceeds byte ceiling")
            snapshot = ProviderInput(encoded, config.model_id, config.configuration_id, config.mode,
                                     config.max_context_bytes, config.max_reply_bytes,
                                     config.max_input_tokens, config.max_output_tokens)
            call_id = f"planner-{uuid4().hex}"
            call = _Call(call_id, request, now, now + timeout, reservation)
            self._call_ceiling, self._spend_ceiling = call_ceiling, spend_ceiling
            self._wall_deadline = wall_deadline
            self._calls[call_id] = call
            self._active = call_id
            thread = threading.Thread(target=self._invoke, args=(call, snapshot), daemon=True,
                                      name=call_id)
            try:
                thread.start()
            except RuntimeError:
                self._active = None
                del self._calls[call_id]
                self._reject(now, "Provider thread could not start")
            self._start = start
            self._turn_ceiling = turn_ceiling
            return call_id

    def _usage(self, call: _Call, usage: object, now: float) -> bool:
        if self._config.mode == "external":
            call.usage = ProviderUsage()
            call.usage_reason = "External chat usage is unmeasured"
            call.overshoot, call.overshoot_reason = None, "External chat cost is unmeasured"
            call.settled = now  # The zero API reservation is resolved, not a token/cost measurement.
            return False
        if type(usage) is not ProviderUsage:
            call.usage_reason = "Provider usage missing or malformed"
            return False
        # Declared bounds apply to the raw report, even when a metric is too
        # large or malformed for evaluation/1. Sanitizing first would hide faults.
        ceilings = {"input_tokens": self._config.max_input_tokens,
                    "output_tokens": self._config.max_output_tokens,
                    "cached_input_tokens": self._config.max_input_tokens,
                    "cost_usd": call.reservation}
        bound_fault = any(type(getattr(usage, name)) in (int, float)
                          and getattr(usage, name) > ceiling
                          for name, ceiling in ceilings.items())
        raw_cost = usage.cost_usd
        if (type(raw_cost) in (int, float) and 0 <= raw_cost <= 1e15
                and math.isfinite(raw_cost)):
            call.overshoot = max(0.0, raw_cost - call.reservation)
            call.overshoot_reason = None
        elif raw_cost is not None:
            call.overshoot_reason = "Reported cost is not a bounded finite accounting amount"
        values = {}
        malformed = False
        for name in ("input_tokens", "output_tokens", "cached_input_tokens", "cost_usd"):
            value = getattr(usage, name)
            try:
                if value is not None:
                    if name == "cost_usd":
                        _number(value, name, 1e9)
                    else:
                        _integer(value, name, 10**12)
                values[name] = value
            except ContractError:
                values[name], malformed = None, True
        if (values["cached_input_tokens"] is not None and (values["input_tokens"] is None
                or values["cached_input_tokens"] > values["input_tokens"])):
            values["cached_input_tokens"], malformed = None, True
        call.usage = ProviderUsage(**values)
        call.usage_reason = ("Provider usage malformed or outside evaluation bounds" if malformed else
                             "Provider metric not reported" if None in values.values() else None)
        cost = values["cost_usd"]
        if cost is not None and not malformed:
            call.settled = now
        elif malformed:
            # Do not label a cost settled when the adapter's usage is contradictory.
            call.usage = ProviderUsage(values["input_tokens"], values["output_tokens"],
                                       values["cached_input_tokens"], None)
        if bound_fault:
            self._frozen = True
        return bool(bound_fault)

    def _candidate(self, call: _Call, reply: ProviderReply) -> PlanCandidate:
        data = reply.candidate_json
        if type(data) not in (str, bytes):
            raise ContractError("Provider candidate must be serialized JSON")
        if len(data.encode("utf-8") if type(data) is str else data) > self._config.max_reply_bytes:
            raise ContractError("Provider reply exceeds byte ceiling")
        candidate = PlanCandidate.from_dict(data)
        request = call.request
        skill = next((skill for skill in request.skills if
                      (skill.skill_id, skill.skill_version) ==
                      (candidate.skill_id, candidate.skill_version)), None)
        if skill is None:
            raise ContractError("Unsupported skill identity or version")
        candidate.check_binding(request.task, request.packet.current,
                                plan_id=request.packet.plan_id, plan_version=request.plan_version,
                                execution_epoch=request.execution_epoch, skill=skill)
        if (candidate.stage != request.expected_stage
                or candidate.distance_remaining != request.distance_remaining):
            raise ContractError("Candidate differs from exact remaining route")
        return candidate

    def _invoke(self, call: _Call, snapshot: ProviderInput) -> None:
        reply = None
        failed = False
        try:
            reply = self._provider(snapshot, call.cancelled)
        except BaseException:
            # Trusted adapters may fail with sensitive diagnostics; retain a public
            # bounded lifecycle reason, never arbitrary provider text or credentials.
            failed = True
        physical_completion = self._clock()
        with self._lock:
            now = self._now()
            _number(physical_completion, "provider completion", 1e12)
            if not call.invoked <= physical_completion <= now:
                raise ContractError("Provider completion clock regressed")
            call.completed = physical_completion  # Physical completion is independent of usage settlement.
            self._active = None
            self._expire(call, now)
            valid_reply = type(reply) is ProviderReply
            fault = self._usage(call, reply.usage if valid_reply else None, now)
            if call.status != "pending":
                return  # Late accounting only; cancelled/stale/deadline state is final.
            if failed or not valid_reply or fault:
                self._stop(call, "failed", "Provider failed or exceeded declared bounds", now)
                return
            try:
                candidate = self._candidate(call, reply)
            except (ContractError, UnicodeError, ValueError, TypeError, RecursionError):
                self._stop(call, "failed", "Provider candidate rejected by planner contract", now)
                return
            call.status, call.reason, call.candidate = "completed", "Candidate validated; no execution authority", candidate

    def poll(self, call_id: str, binding: PlanningBinding) -> CallResult:
        if type(binding) is not PlanningBinding:
            raise ContractError("Poll requires the caller's current PlanningBinding")
        with self._lock:
            now = self._now()
            call = self._lookup(call_id)
            self._expire(call, now)
            if call.status in ("pending", "completed") and binding != call.request.binding:
                self._stop(call, "stale", "Caller binding changed; candidate permanently invalidated", now)
            return CallResult(call.call_id, call.status, call.reason, call.candidate)

    def deadline(self, call_id: str) -> float:
        with self._lock:
            return self._lookup(call_id).deadline

    def active_deadline(self) -> float | None:
        """Original absolute deadline for the physical call; reads never renew it."""
        with self._lock:
            return None if self._active is None else self._calls[self._active].deadline

    def _lookup(self, call_id: str) -> _Call:
        if type(call_id) is not str or call_id not in self._calls:
            raise ContractError("Unknown planner call identity")
        return self._calls[call_id]

    def cancel(self, call_id: str) -> CallResult:
        with self._lock:
            now = self._now()
            call = self._lookup(call_id)
            self._expire(call, now)
            if call.status in ("pending", "completed"):
                self._stop(call, "cancelled", "Caller cancelled planning", now)
            return CallResult(call.call_id, call.status, call.reason, None)

    def close(self) -> None:
        with self._lock:
            now = self._now()
            self._closed = True
            for call in self._calls.values():
                self._expire(call, now)
                if call.status in ("pending", "completed"):
                    self._stop(call, "closed", "Planner port closed", now)

    def snapshot(self, *, cutoff_monotonic: float | None = None) -> AccountingSnapshot:
        with self._lock:
            previous = self._last_time
            now = self._now()
            cutoff = now if cutoff_monotonic is None else cutoff_monotonic
            _number(cutoff, "cutoff_monotonic", 1e12)
            if cutoff < previous or cutoff > now:
                raise ContractError("Reporting cutoff must cover observed transitions and not be future")
            accounts, events = [], []
            for call in self._calls.values():
                self._expire(call, cutoff)
                unresolved = call.reservation if call.settled is None else 0.0
                accounts.append(CallAccounting(call.call_id, call.status, call.reason, call.invoked,
                    call.stopped, call.completed, call.settled, call.usage, call.usage_reason,
                    unresolved, call.reservation, call.overshoot, call.overshoot_reason,
                    call.completed is None))
                endpoint = call.completed if call.completed is not None else cutoff
                payload = {"role": "planner", "model_id": self._config.model_id,
                           "configuration_id": self._config.configuration_id,
                           "duration_ms": (endpoint - call.invoked) * 1000,
                           "status": {"completed": "completed", "failed": "failed",
                                      "stale": "failed", "timed_out": "timed_out"}.get(call.status, "unknown")}
                for name in ("input_tokens", "output_tokens", "cached_input_tokens", "cost_usd"):
                    value = getattr(call.usage, name)
                    payload[name] = value
                    payload[f"{name}_missing_reason"] = None if value is not None else (
                        call.usage_reason or "Provider metric unavailable")
                event = {"event_id": call.call_id, "kind": "model_call",
                         "elapsed_ms": (endpoint - self._admission) * 1000,
                         "session": call.request.task.session, "game_turn": None,
                         "game_turn_missing_reason": "Planner does not observe game turns",
                         "evidence": [], "payload": payload}
                events.append(event)
            events.sort(key=lambda event: (event["elapsed_ms"], event["event_id"]))
            return AccountingSnapshot(cutoff, self._admission, tuple(accounts), tuple(self._rejections),
                self._rejection_count, self._rejection_count - len(self._rejections), self._committed(), math.fsum(item.unresolved_reservation_usd for item in accounts),
                self._active is not None, self._frozen,
                tuple(json.dumps(event, allow_nan=False) for event in events))
