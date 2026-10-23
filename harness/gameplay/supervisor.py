"""Passive waypoint-and-return supervision for one serialized, trusted caller.

Intents are immutable data, never dispatch authority or authenticated native
receipts. The caller supplies exactly correlated transport results. This module
has no controller, service, lease, restoration, dispatch or automatic retry path.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import math
import time
from typing import Callable, Literal

from harness.movement import DIRECTIONS, MovementBlocked, current_guard, guard
from .contracts import (
    Budgets, ContractError, EvidencePacket, EvidenceRef, PrimitiveResult, Progress,
    RunStatus, Stage, TaskSpec, PlanCandidate,
)
from .evidence import EvidenceError, EvidenceStore
from .memory import TaskMemory
from .planner import AccountingSnapshot, CallResult, PlannerConfig, PlannerPort, PlanningRequest, Provider
from .skills import (
    ACCEPTED_SKILLS, CARDINAL_MOVEMENT, MovementStage, RouteAttempt, RouteHistory,
    SkillEvaluation, StepProposal, summarize_route,
)


@dataclass(frozen=True)
class DispatchIntent:
    run_id: str
    task_id: str
    task_version: int
    plan_id: str
    plan_version: int
    execution_epoch: int
    stage: Stage
    stage_id: str
    stage_version: int
    skill_id: str
    skill_version: int
    proposal: StepProposal
    grants_dispatch_authority: Literal[False] = False


def _text(value: str, name: str, maximum: int = 128) -> None:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise ContractError(f"{name} requires bounded nonempty text")


def _monotonic(value: float) -> bool:
    try:
        return type(value) in (int, float) and 0 <= value <= 1e12 and math.isfinite(value)
    except OverflowError:
        return False


class WaypointSupervisor:
    """One immutable task, original memory/port, bounded retained route and epochs.

    All mutating operations require explicit nondecreasing caller clocks. Bad
    clocks revoke applicability while preserving unresolved intent context.
    ``status`` validates clocks without rebinding or admitting a stale plan.
    The injected port clock must use the same monotonic domain as caller clocks.
    """

    def __init__(self, task: TaskSpec, *, run_id: str, store: EvidenceStore,
                 task_start: EvidenceRef, admission_monotonic: float,
                 planner_config: PlannerConfig, provider: Provider,
                 clock: Callable[[], float] = time.monotonic):
        _text(run_id, "run_id")
        if not _monotonic(admission_monotonic):
            raise ContractError("Original admission requires a finite monotonic clock")
        summary = summarize_route(task, store, task_start, ())
        self._task, self._run_id, self._store = task, run_id, store
        self._start, self._admission = task_start, admission_monotonic
        self._config = planner_config
        self._memory = TaskMemory(task, store)
        self._planner = PlannerPort(task, planner_config, provider,
                                    admission_monotonic=admission_monotonic, clock=clock)
        self._history: RouteHistory = ()
        self._summary = summary
        self._epoch = 0
        self._state, self._reason = "idle", "Explicit start required"
        self._started, self._retired = False, False
        self._last_monotonic, self._last_timestamp = admission_monotonic, None
        self._leg: Stage = "outbound"
        self._version = 0
        self._request: PlanningRequest | None = None
        self._call: str | None = None
        self._checkpoint = task_start
        self._generation = store.authority_generation()
        self._stage: MovementStage | None = None
        self._pending: DispatchIntent | None = None
        self._intent_time: float | None = None
        self._revoked, self._operator_revoked = False, False
        self._settlements: dict[str, tuple[DispatchIntent, PrimitiveResult]] = {}
        self._used_ids: set[str] = set()
        self._failed_signatures: list[str] = []  # At most eight charged attempts.
        self._actions: list[str] = []
        self._decisions: deque[str] = deque(maxlen=64)
        self._decision_count = 0

    @property
    def task(self) -> TaskSpec:
        return self._task

    @property
    def task_start(self) -> EvidenceRef:
        return self._start

    @property
    def memory(self) -> TaskMemory:
        """Inspectable original memory; caller must not mutate component state."""
        return self._memory

    @property
    def planner(self) -> PlannerPort:
        """Inspectable original port; caller must not submit/cancel independently."""
        return self._planner

    @property
    def route_history(self) -> RouteHistory:
        return self._history

    @property
    def pending_intent(self) -> DispatchIntent | None:
        return self._pending

    @property
    def dropped_decision_events(self) -> int:
        return self._decision_count - len(self._decisions)

    def _clocks(self, now_monotonic: float, now_timestamp_ms: int, *, mutate: bool = True) -> None:
        if (not _monotonic(now_monotonic) or now_monotonic < self._last_monotonic
                or type(now_timestamp_ms) is not int or not 0 <= now_timestamp_ms <= 2**63 - 1
                or (self._last_timestamp is not None and now_timestamp_ms < self._last_timestamp)):
            if mutate and not self._retired:
                self._revoke("failed", "Invalid or regressing caller clocks")
            raise ContractError("Supervisor requires finite nondecreasing caller clocks")
        if mutate:
            self._last_monotonic, self._last_timestamp = now_monotonic, now_timestamp_ms
            # Expiry precedes pause/takeover too: operator input cannot change the
            # first cause of an intent whose applicability already elapsed.
            self._expire_intent(now_monotonic)

    def _revoke(self, state: str, reason: str, *, operator: bool = False) -> None:
        if self._retired or (self._state == "completed" and state != "abandoned"):
            return
        self._epoch += 1
        self._memory.advance_epoch(self._epoch)
        if self._call is not None:
            self._planner.cancel(self._call)
            self._call = None
        self._stage = None
        if self._pending is not None and not self._revoked:
            # Only the first revocation establishes a known operator cause.
            # A later pause cannot promote an expired/invalid-clock intent.
            self._operator_revoked = operator
            self._revoked = True
        self._state, self._reason = state, reason[:1024]

    def _expire_intent(self, now: float) -> None:
        if (self._pending is not None and not self._revoked and not self._retired
                and now >= self._intent_time + self._pending.proposal.wait_seconds):
            self._revoke("unknown", "Passive intent wait bound expired; result applicability revoked")

    def _stop(self, state: str, reason: str) -> None:
        self._stage = None
        self._state, self._reason = state, reason[:1024]

    def _delta(self) -> tuple[int, int, str]:
        dx, dy, action = DIRECTIONS[self._task.direction]
        if self._leg == "return":
            dx, dy = -dx, -dy
            action = next(a for x, y, a in DIRECTIONS.values() if (x, y) == (dx, dy))
        return dx, dy, action

    def _current(self, now_monotonic: float, now_timestamp_ms: int, *, exact: bool) -> EvidenceRef:
        summary = summarize_route(self._task, self._store, self._start, self._history)
        current = self._store.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        if (current.session != self._task.session or current.revision < summary.latest.revision
                or current.turn < summary.latest.turn or self._store.position(current) != summary.position):
            raise EvidenceError("Current evidence differs from the original verified route checkpoint")
        if exact and (current != self._checkpoint or self._store.authority_generation() != self._generation):
            raise EvidenceError("Observation or evidence authority changed; explicit continuation required")
        dx, dy, action = self._delta()
        observation = self._store.observation(current)
        progress = summary.outbound_steps if self._leg == "outbound" else summary.return_steps
        predicate = current_guard if progress == self._task.distance else guard
        predicate(observation, dx, dy, paused=False, frozen=False, now_timestamp_ms=now_timestamp_ms)
        if action not in observation["actions"]:
            raise MovementBlocked("Cardinal movement action is unavailable")
        self._summary = summary
        return current

    def _remaining(self, now_monotonic: float, current: EvidenceRef | None = None) -> Budgets:
        budgets, summary = self._task.budgets, self._summary
        pending = int(self._pending is not None and
                      self._pending.proposal.action_id not in {a.result.action_id for a in self._history})
        leg_count = summary.outbound_count if self._leg == "outbound" else summary.return_count
        accounting = self._planner.snapshot()
        ref = (current if current is not None and current.session == self._task.session
               and current.revision >= self._checkpoint.revision
               and current.turn >= self._checkpoint.turn else self._checkpoint)
        wall = max(0, budgets.wall_seconds - (now_monotonic - self._admission))
        return Budgets(primitives=max(0, budgets.primitives - summary.primitive_count - pending),
            primitives_per_stage=max(0, budgets.primitives_per_stage - leg_count - pending),
            turns=max(0, budgets.turns - max(0, ref.turn - self._start.turn)), wall_seconds=wall,
            planner_calls=max(0, min(budgets.planner_calls, self._config.max_calls) - len(accounting.calls)),
            planner_call_seconds=min(budgets.planner_call_seconds, self._config.call_timeout_seconds, wall),
            primitive_wait_seconds=min(budgets.primitive_wait_seconds, wall),
            spend_usd=max(0, min(budgets.spend_usd, self._config.spend_ceiling_usd) - accounting.committed_usd))

    def _signature(self, ref: EvidenceRef) -> str:
        state = self._store.observation(ref)
        dx, dy, action = self._delta()
        scene = state["scene"]
        tile = next((t for t in scene["neighbors"] if (t["dx"], t["dy"]) == (dx, dy)), None)
        # Deliberately exclude revision, clocks, image bytes, names and model text.
        signature = (scene["position"], (dx, dy), action, action in state["actions"],
                     state["paused"], state["boundary"]["kind"], state["category"],
                     scene["visible_creatures"], None if tile is None else
                     (tile["visible"], tile.get("terrain"), tile.get("furniture")))
        return json.dumps(signature, sort_keys=True, separators=(",", ":"))

    def _new_stage(self, current: EvidenceRef) -> MovementStage:
        return MovementStage(self._task, stage_id=f"{self._leg}-{self._version}",
            stage_version=max(1, self._version), stage=self._leg, store=self._store,
            task_start=self._start, checkpoint=current, admission_monotonic=self._admission,
            history=self._history)

    def _decision(self, decision: str, now: float) -> None:
        self._decision_count += 1
        event = self._event(f"decision-{self._decision_count}", "decision", now, (), {
            "decision": decision, "reason": self._reason, "actor": "autonomous",
            "model_id": None, "model_id_missing_reason": "Deterministic passive supervisor",
            "expected": [], "observed": [], "unknowns": []})
        self._decisions.append(json.dumps(event))

    def _event(self, identity: str, kind: str, now: float, sources: tuple[EvidenceRef, ...],
               payload: dict) -> dict:
        return {"event_id": f"{self._run_id}:{identity}", "kind": kind,
            "elapsed_ms": (now - self._admission) * 1000, "session": self._task.session,
            "game_turn": None, "game_turn_missing_reason": "Passive event has no independently timed game turn",
            "evidence": [r.to_dict() for r in sources], "payload": payload}

    def _submit_or_verify(self, current: EvidenceRef, now: float, timestamp: int) -> None:
        self._checkpoint, self._generation = current, self._store.authority_generation()
        progress = self._summary.outbound_steps if self._leg == "outbound" else self._summary.return_steps
        if progress == self._task.distance:
            self._state = "verifying"
            evaluation = self._new_stage(current).propose(f"verify-{self._version}",
                now_monotonic=now, now_timestamp_ms=timestamp, paused=False, frozen=False)
            if not isinstance(evaluation, SkillEvaluation):
                raise ContractError("Complete-leg verification must not create an action")
            self._finish_stage(evaluation, now, timestamp)
            return
        remaining = self._remaining(now, current)
        if (min(remaining.primitives, remaining.primitives_per_stage, remaining.turns,
                remaining.wall_seconds, remaining.planner_calls, remaining.planner_call_seconds,
                remaining.primitive_wait_seconds) <= 0):
            self._stop("budget_exhausted", "Original task, leg or planner budget exhausted")
            return
        self._store.preflight_dispatch(current, now_monotonic=now, now_timestamp_ms=timestamp)
        self._version += 1
        memory = self._memory.refresh(now_monotonic=now, now_timestamp_ms=timestamp)
        last = self._history[-1].result if self._history else None
        packet = EvidencePacket(self._task.task_id, f"plan-{self._version}", f"{self._leg}-{self._version}",
            current, self._start, self._summary.waypoint, last.action_id if last else None,
            last.transport_disposition if last else None, last.observed_displacement if last else None,
            self._reason, remaining, memory.current_facts, ())
        request = PlanningRequest(self._task, packet, ACCEPTED_SKILLS, self._version, self._epoch,
            self._leg, self._task.distance - progress, self._admission,
            public_context=json.dumps({"outbound_verified_steps": self._summary.outbound_steps,
                "return_verified_steps": self._summary.return_steps,
                "primitive_attempts": self._summary.primitive_count, "stop_reason": self._reason}))
        try:
            call = self._planner.submit(request)
        except ContractError as exc:
            self._stop("blocked", str(exc))
            return
        self._request, self._call = request, call
        self._state, self._reason = "planning", "Awaiting exactly bound strategic candidate"
        self._decision("replan", now)

    def _finish_stage(self, evaluation: SkillEvaluation, now: float, timestamp: int) -> None:
        terminal = evaluation.stage_result
        if terminal is None:
            self._state, self._reason = "admitted", evaluation.reason
        elif terminal.disposition != "completed":
            self._stop(terminal.disposition, evaluation.reason)
        elif self._leg == "outbound":
            self._stage = None
            self._leg = "return"
            current = self._current(now, timestamp, exact=False)
            self._reason = "Outbound verified; a fresh strategic return decision is required"
            self._submit_or_verify(current, now, timestamp)
        else:
            summary = summarize_route(self._task, self._store, self._start, self._history)
            if (summary.outbound_steps != self._task.distance or summary.return_steps != self._task.distance
                    or summary.waypoint is None or self._pending is not None):
                raise EvidenceError("Task completion lacks both verified legs or has an unresolved action")
            self._current(now, timestamp, exact=True)
            self._stop("completed", "Both route legs verified from retained start, waypoint and final evidence")
        self._decision("continue" if self._state == "admitted" else "stop", now)

    def start(self, *, now_monotonic: float, now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms)
        if self._started or self._retired:
            raise ContractError("A supervisor admits its immutable task only once")
        self._started = True
        try:
            current = self._current(now_monotonic, now_timestamp_ms, exact=False)
            self._submit_or_verify(current, now_monotonic, now_timestamp_ms)
        except (EvidenceError, MovementBlocked) as exc:
            self._stop("blocked", str(exc))
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def planning_result(self) -> CallResult:
        """Inspect the original request lifecycle without refreshing aged evidence."""
        if self._state != "planning" or self._call is None:
            raise ContractError("No planning request is pending")
        return self._planner.poll(self._call, self._request.binding)

    def _admit_candidate(self, candidate: PlanCandidate, current: EvidenceRef, now: float, timestamp: int) -> None:
        candidate.check_binding(self._task, current, plan_id=self._request.packet.plan_id,
            plan_version=self._version, execution_epoch=self._epoch, skill=CARDINAL_MOVEMENT)
        self._checkpoint, self._generation = current, self._store.authority_generation()
        self._memory.refresh(now_monotonic=now, now_timestamp_ms=timestamp)
        sources = (self._start,) + ((self._summary.waypoint,) if self._summary.waypoint else ())
        self._memory.retain_plan(candidate, CARDINAL_MOVEMENT, sources=sources,
            now_monotonic=now, now_timestamp_ms=timestamp)
        self._stage = self._new_stage(current)
        self._call = None
        self._state, self._reason = "admitted", "Bound candidate retained; eligible intent may be proposed"
        self._decision("continue", now)

    def revalidate_planning(self, refreshed: EvidenceRef, *, now_monotonic: float,
                            now_timestamp_ms: int) -> RunStatus:
        """Admit the original candidate only after one equivalent fresh Observe.

        Only the refresh's single generation advance is accepted. The candidate
        and original task/history/budgets are never rewritten or renewed.
        """
        self._clocks(now_monotonic, now_timestamp_ms)
        old = self._checkpoint
        try:
            result = self.planning_result()
            if now_monotonic >= self._planner.deadline(self._call):
                raise ContractError("Original planning revalidation deadline expired")
            if result.status != "completed":
                raise ContractError("Original planner request is not a live completed candidate")
            if self._request.execution_epoch != self._epoch:
                raise ContractError("Original planning epoch changed")
            self._store.observation(old)
            current = self._store.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            if (current != refreshed or current == old
                    or self._store.authority_generation() != self._generation + 1):
                raise EvidenceError("Planning refresh has intervening evidence invalidation")
            before, after = self._store.observation(old), self._store.observation(current)
            keys = ("session", "revision", "scene", "boundary", "category", "actions", "paused", "in_game")
            if (any(before[key] != after[key] for key in keys)
                    or current.frame_sha256 != old.frame_sha256):
                raise EvidenceError("Planning refresh differs from original visible state or pixels")
            self._current(now_monotonic, now_timestamp_ms, exact=False)
            self._admit_candidate(result.candidate, current, now_monotonic, now_timestamp_ms)
            self._reason = "Original candidate explicitly revalidated against equivalent fresh evidence"
            decision = "equivalent"
        except (EvidenceError, MovementBlocked, ContractError) as exc:
            self._revoke("interrupted", str(exc))
            decision = "not equivalent: " + str(exc)
        self._decision_count += 1
        self._decisions.append(json.dumps(self._event(f"decision-{self._decision_count}", "decision",
            now_monotonic, tuple(dict.fromkeys((old, refreshed))), {
                "decision": "replan", "reason": decision[:1024], "actor": "autonomous",
                "model_id": None, "model_id_missing_reason": "Deterministic revalidation",
                "expected": [], "observed": [], "unknowns": []})))
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def poll(self, *, now_monotonic: float, now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms)
        if self._state == "executing":
            try:
                summarize_route(self._task, self._store, self._start, self._history)
                self._store.observation(self._pending.proposal.before)
                current, _ = self._store.inspect_current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
                if current is None or current.session != self._task.session:
                    raise EvidenceError("Pending intent evidence changed native session")
            except (EvidenceError, ContractError) as exc:
                self._revoke("unknown", str(exc))
        if self._state in ("planning", "admitted"):
            try:
                if self._state == "planning":
                    current, _ = self._store.inspect_current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
                    if current != self._checkpoint or self._store.authority_generation() != self._generation:
                        raise EvidenceError("Observation or evidence authority changed; explicit continuation required")
                    result = self.planning_result()
                    if result.status == "completed":
                        current = self._current(now_monotonic, now_timestamp_ms, exact=True)
                        self._admit_candidate(result.candidate, current, now_monotonic, now_timestamp_ms)
                    elif result.status != "pending":
                        self._call = None
                        self._stop("budget_exhausted" if result.status == "timed_out" else "failed", result.reason)
                else:
                    self._current(now_monotonic, now_timestamp_ms, exact=True)
            except (EvidenceError, MovementBlocked, ContractError) as exc:
                self._revoke("interrupted", str(exc))
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def propose(self, action_id: str, *, now_monotonic: float, now_timestamp_ms: int) -> DispatchIntent | None:
        self._clocks(now_monotonic, now_timestamp_ms)
        _text(action_id, "action_id")
        if action_id in self._used_ids:
            raise ContractError("Logical action IDs cannot be reused across epochs or legs")
        if self._state != "admitted" or self._retired:
            return None
        if self._pending is not None:
            raise ContractError("One intent is already unresolved")
        try:
            self._current(now_monotonic, now_timestamp_ms, exact=True)
            proposal = self._stage.propose(action_id, now_monotonic=now_monotonic,
                now_timestamp_ms=now_timestamp_ms, paused=False, frozen=False)
            if isinstance(proposal, SkillEvaluation):
                self._finish_stage(proposal, now_monotonic, now_timestamp_ms)
                return None
        except (EvidenceError, MovementBlocked) as exc:
            self._revoke("interrupted", str(exc))
            return None
        self._used_ids.add(action_id)
        self._pending = DispatchIntent(self._run_id, self._task.task_id, self._task.task_version,
            self._request.packet.plan_id, self._version, self._epoch, self._leg,
            self._request.packet.stage_id, self._version, CARDINAL_MOVEMENT.skill_id,
            CARDINAL_MOVEMENT.skill_version, proposal)
        self._intent_time = now_monotonic
        self._revoked, self._operator_revoked = False, False
        self._state, self._reason = "executing", "One passive intent awaits an exact correlated result"
        return self._pending

    def validate_dispatch(self, intent: DispatchIntent, *, now_monotonic: float,
                          now_timestamp_ms: int) -> float:
        """Recheck live intent/evidence and return its original absolute deadline."""
        self._clocks(now_monotonic, now_timestamp_ms)
        if (intent != self._pending or self._revoked or self._retired
                or self._state != "executing" or intent.execution_epoch != self._epoch):
            raise ContractError("Dispatch intent is no longer live")
        self._current(now_monotonic, now_timestamp_ms, exact=True)
        deadline = min(self._admission + self._task.budgets.wall_seconds,
                       self._intent_time + intent.proposal.wait_seconds)
        if now_monotonic >= deadline or self._remaining(now_monotonic).turns <= 0:
            raise ContractError("Original dispatch budget exhausted")
        return deadline

    def _non_delivery(self, result: PrimitiveResult) -> None:
        if result.transport_disposition not in ("not_dispatched", "rejected"):
            raise ContractError("Detached settlement requires explicit non-delivery")
        if result.observed_displacement not in (None, (0, 0, 0)):
            raise ContractError("Non-delivery cannot attribute displacement")
        before = result.before
        self._store.observation(before)
        if before.session != self._task.session:
            raise ContractError("Non-delivery must retain the original session")
        if result.after is not None:
            after = result.after
            if (after.session != before.session or after.revision < before.revision or after.turn < before.turn
                    or self._store.position(after) != self._store.position(before)):
                raise ContractError("Non-delivery after evidence must be ordered at the same checkpoint")
        summarize_route(self._task, self._store, self._start,
                        self._history + (RouteAttempt(self._pending.stage, result),))

    def _action_event(self, intent: DispatchIntent, result: PrimitiveResult, now: float,
                      steps: int | None, *, stale: bool) -> None:
        disposition = result.transport_disposition
        dispatch = ("not_dispatched" if disposition in ("not_dispatched", "rejected") else
                    "unknown" if disposition == "unknown" else "dispatched")
        # This is the observed passive intent-to-settlement interval, not an
        # invented engine/input latency or a usefulness/harm assessment.
        payload = {"action_id": result.action_id, "transport_disposition": disposition,
            "dispatch_state": dispatch, "duration_ms": (now - self._intent_time) * 1000,
            "verified_steps": steps, "verified_steps_missing_reason": None if steps is not None else
            "Revoked or unresolved result cannot establish credited movement", "invalid": disposition == "rejected",
            "stale": stale, "unknown": steps is None or disposition in ("unknown", "dispatched"),
            "verified_no_progress": steps == 0 and disposition == "returned"}
        sources = (result.before,) + ((result.after,) if result.after else ())
        self._actions.append(json.dumps(self._event(f"action-{len(self._actions)+1}", "action", now, sources, payload)))

    def settle(self, intent: DispatchIntent, result: PrimitiveResult, *, now_monotonic: float,
               now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms)
        if type(intent) is not DispatchIntent or type(result) is not PrimitiveResult:
            raise ContractError("Settlement requires typed intent and primitive result")
        result.__post_init__()
        previous = self._settlements.get(result.action_id)
        if previous is not None:
            if previous != (intent, result):
                raise ContractError("Conflicting duplicate intent or primitive result")
            return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        if (intent != self._pending or result.action_id != intent.proposal.action_id
                or result.before != intent.proposal.before):
            raise ContractError("Settlement must equal the complete outstanding intent and exact result binding")
        stale = self._revoked or self._retired or intent.execution_epoch != self._epoch
        if stale:
            non_delivery = result.transport_disposition in ("not_dispatched", "rejected")
            if non_delivery:
                self._non_delivery(result)
                if not self._retired:
                    self._memory.record_action(result)
                self._history += (RouteAttempt(intent.stage, result),)
                self._summary = summarize_route(self._task, self._store, self._start, self._history)
                if not self._operator_revoked:
                    self._failed_signatures.append(self._signature(result.after or result.before))
                self._pending = None
                steps = 0
            else:
                # Late observations cannot establish attribution after revocation.
                # Keep the exact pending intent even after its result is audited.
                if not self._retired:
                    try:
                        self._memory.record_action(result)
                    except EvidenceError:
                        pass  # Result remains in settlement audit with no memory/source promotion.
                    self._stop("unknown", "Revoked intent has no explicit non-delivery; outcome remains unknown")
                steps = None
        else:
            evaluation = self._stage.settle(result, now_monotonic=now_monotonic,
                now_timestamp_ms=now_timestamp_ms, paused=False, frozen=False)
            old_steps = self._summary.outbound_steps + self._summary.return_steps
            safe = not (evaluation.stage_result and evaluation.stage_result.disposition == "unknown")
            try:
                summary = summarize_route(self._task, self._store, self._start,
                    self._history + (RouteAttempt(intent.stage, result),)) if safe else None
            except (ContractError, EvidenceError):
                summary = None
            try:
                self._memory.record_action(result)
            except EvidenceError:
                # The exact result is still audited, but disputed/capacity-limited
                # sources cannot create route credit or release pending context.
                summary = None
            if summary is None:
                self._revoked = True
                self._stop("unknown", "Result cannot establish a resumable retained route")
                steps = None
            else:
                self._history += (RouteAttempt(intent.stage, result),)
                self._summary = summary
                self._pending = None
                self._checkpoint = result.after or result.before
                self._generation = self._store.authority_generation()
                steps = summary.outbound_steps + summary.return_steps - old_steps
                if steps == 0:
                    self._failed_signatures.append(self._signature(self._checkpoint))
                try:
                    self._finish_stage(evaluation, now_monotonic, now_timestamp_ms)
                except (EvidenceError, MovementBlocked) as exc:
                    self._stop("blocked", str(exc))
        self._settlements[result.action_id] = (intent, result)
        self._action_event(intent, result, now_monotonic, steps, stale=stale)
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def pause(self, reason: str, *, now_monotonic: float, now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms)
        _text(reason, "reason", 1024)
        if not self._retired:
            self._revoke("paused", reason, operator=True)
            self._decision("stop", now_monotonic)
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def invalidate(self, reason: str, *, now_monotonic: float, now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms)
        _text(reason, "reason", 1024)
        if not self._retired:
            self._revoke("interrupted", reason, operator=True)
            self._decision("stop", now_monotonic)
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def continue_task(self, *, now_monotonic: float, now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms)
        if (not self._started or self._retired or self._pending is not None
                or self._state in ("idle", "planning", "admitted", "executing", "completed")):
            raise ContractError("Explicit continuation requires a stopped active task with no unresolved intent")
        self._revoke("interrupted", "Explicit continuation requested")
        try:
            current = self._current(now_monotonic, now_timestamp_ms, exact=False)
            if self._signature(current) in self._failed_signatures:
                raise ContractError("Equivalent no-progress conditions require a concrete relevant observable change")
            self._submit_or_verify(current, now_monotonic, now_timestamp_ms)
        except (EvidenceError, MovementBlocked, ContractError) as exc:
            self._stop("blocked", str(exc))
            raise
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def abandon(self, reason: str, *, now_monotonic: float, now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms)
        _text(reason, "reason", 1024)
        if not self._retired:
            self._revoke("abandoned", reason)
            self._memory.retire(reason)
            self._planner.close()
            self._retired = True
            self._decision("stop", now_monotonic)
        return self.status(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)

    def status(self, *, now_monotonic: float, now_timestamp_ms: int) -> RunStatus:
        self._clocks(now_monotonic, now_timestamp_ms, mutate=False)
        fresh = False
        try:
            current, fresh = self._store.inspect_current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            fresh = fresh and current is not None and current.session == self._task.session
        except EvidenceError:
            current = None
        summary = self._summary
        sources = tuple(dict.fromkeys(summary.sources + (self._checkpoint,)))
        reason = self._reason
        try:
            for ref in sources:
                self._store.observation(ref)
        except EvidenceError:
            fresh = False
            reason = "Retained task evidence is disputed or missing; historical progress is preserved"
        progress = Progress(summary.outbound_steps + summary.return_steps,
                            tuple(p-o for p, o in zip(summary.position, self._task.origin)))
        request = self._request
        return RunStatus(self._task.task_id, request.packet.plan_id if request else None,
            request.packet.stage_id if request else None, self._epoch, self._state,
            self._config.model_id, self._config.configuration_id,
            CARDINAL_MOVEMENT.skill_id if request else None, CARDINAL_MOVEMENT.skill_version if request else None,
            progress, self._remaining(now_monotonic, current), "Explicit caller operation required", reason,
            None, self._state == "paused", fresh, sources)

    def accounting_snapshot(self, *, cutoff_monotonic: float | None = None) -> AccountingSnapshot:
        """Original port accounting; one immutable snapshot per exported artifact."""
        if cutoff_monotonic is not None and (not _monotonic(cutoff_monotonic)
                or cutoff_monotonic < self._last_monotonic):
            raise ContractError("Accounting cutoff predates supervisor operations")
        return self._planner.snapshot(cutoff_monotonic=cutoff_monotonic)

    def evaluation_events(self, accounting: AccountingSnapshot) -> tuple[dict, ...]:
        """Merge exactly one supplied snapshot; caller supplies manifest/outcome.

        Decisions retain the last 64 entries and a dropped count; all at most
        eight action attempts remain. An unresolved intent contributes one
        snapshot-only unknown action at cutoff, never a delivery claim. Export
        at a covering cutoff; later results/financial knowledge belong in a
        separately named artifact, not an append to the old snapshot.
        """
        if type(accounting) is not AccountingSnapshot or accounting.admission_monotonic != self._admission:
            raise ContractError("Export requires the original port's immutable accounting snapshot")
        current = self._planner.snapshot()
        if (tuple(c.call_id for c in accounting.calls) != tuple(c.call_id for c in current.calls)
                or accounting.cutoff_monotonic < self._last_monotonic):
            raise ContractError("Accounting snapshot does not cover this supervisor's calls and operations")
        events = [json.loads(e) for e in (*self._decisions, *self._actions)]
        if (self._pending is not None
                and self._pending.proposal.action_id not in self._settlements):
            intent, cutoff = self._pending, accounting.cutoff_monotonic
            payload = {"action_id": intent.proposal.action_id,
                "transport_disposition": "unknown", "dispatch_state": "unknown",
                "duration_ms": (cutoff - self._intent_time) * 1000,
                "verified_steps": None,
                "verified_steps_missing_reason": "No correlated settlement at snapshot cutoff",
                "invalid": False,
                "stale": self._revoked or cutoff >= self._intent_time + intent.proposal.wait_seconds,
                "unknown": True, "verified_no_progress": False}
            events.append(self._event(f"action-{len(self._actions)+1}", "action", cutoff,
                                      (intent.proposal.before,), payload))
        events.extend(accounting.evaluation_events())
        # Stable ordering retains same-time route decisions/actions; planner
        # events have unknown turn endpoints and never rebase route evidence.
        events.sort(key=lambda event: event["elapsed_ms"])
        return tuple(events)
