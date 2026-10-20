"""Bounded remaining-route movement proposals and retained-evidence verification.

There is no dispatch, lease, automatic retry or supervisor here. The trusted
caller reserves after-frame capacity immediately before dispatch and serializes
one native input. It must retain an explicit one-to-one logical/native action ID
mapping with the submitted action, before session/revision and native receipt;
an Observe ID or a later observation cannot supply that attribution.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from harness.movement import DIRECTIONS, MovementBlocked, current_guard, expected_position, guard, observed_step
from .contracts import (
    Budgets, ContractError, EvidenceRef, PrimitiveResult, Progress, SkillDescriptor,
    Stage, StageResult, TaskSpec, Vector,
)
from .evidence import EvidenceError, EvidenceStore


# Declarative predicates, not an interpreter for arbitrary condition strings.
CARDINAL_MOVEMENT = SkillDescriptor(
    skill_id="cardinal_movement", skill_version=4,
    task_kinds=("waypoint_return",), stage_kinds=("outbound", "return"),
    contexts=("normal_play",), action_bindings=("UP", "DOWN", "LEFT", "RIGHT"),
    observable_predicates=("fresh_current_retained_normal_play", "same_session_and_checkpoint",
                           "undisputed_start_waypoint_and_credited_sources", "unpaused_unfrozen",
                           "known_nonhostile_visible_creatures", "current_boundary_at_exact_verified_target",
                           "visible_allowlisted_furniture_free_neighbor_before_further_step",
                           "registered_cardinal_action", "original_task_budgets_remaining"),
    allowed_primitives=("cardinal_step",),
    postconditions=("correlated_logical_action_and_before_reference", "exact_unit_displacement",
                    "advanced_revision_and_nonregressing_turn", "fresh_current_after_evidence",
                    "unchanged_or_single_correlated_authority_generation",
                    "current_guard_at_target_full_guard_before_further_step",
                    "immutable_leg_target_and_cumulative_verified_steps"),
    stop_rules=("pause_or_freeze", "missing_stale_disputed_or_replaced_evidence",
                "hostile_or_unknown_visible_creatures_or_current_boundary",
                "unknown_or_blocked_neighbor_before_further_step", "unregistered_action",
                "capacity_or_original_task_budget", "invalid_or_regressing_clock",
                "unknown_or_dispatched_only_outcome", "rejected_or_not_dispatched",
                "first_zero_or_unexpected_displacement", "no_automatic_retry_or_reconciliation"),
    maximum_budgets=Budgets(),
)

# Acceptance and limits: docs/acceptance/2026-10-17-bounded-skills.md.
# Supplying these to a planner still grants no execution authority.
ACCEPTED_SKILLS = (CARDINAL_MOVEMENT,)


@dataclass(frozen=True)
class StepProposal:
    """Data for one logical action; validity grants no native dispatch authority."""
    action_id: str
    before: EvidenceRef
    action: str
    expected_position: Vector
    wait_seconds: float


@dataclass(frozen=True)
class SkillEvaluation:
    primitive_result: PrimitiveResult | None
    progress: Progress
    reason: str
    stage_result: StageResult | None


def _clock(value: float) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _reference(value: EvidenceRef) -> None:
    if type(value) is not EvidenceRef:
        raise ContractError("Skill evidence requires typed EvidenceRef values")
    value.to_dict()


@dataclass(frozen=True)
class RouteAttempt:
    """One settled proposal from a trusted caller; never a native receipt."""
    stage: Stage
    result: PrimitiveResult


RouteHistory = tuple[RouteAttempt, ...]


@dataclass(frozen=True)
class RouteSummary:
    outbound_count: int
    return_count: int
    outbound_steps: int
    return_steps: int
    position: Vector
    waypoint: EvidenceRef | None
    latest: EvidenceRef
    sources: tuple[EvidenceRef, ...]

    @property
    def primitive_count(self) -> int:
        return self.outbound_count + self.return_count


def summarize_route(task: TaskSpec, store: EvidenceStore, task_start: EvidenceRef,
                    history: RouteHistory) -> RouteSummary:
    """Validate bounded settled history and derive counts/position; no authority.

    Caller provenance must come from exact skill settlements (or explicit revoked
    non-delivery). Rechecking retained geometry cannot authenticate transport.
    Unknown and unexpected movement cannot become a resumable route.
    """
    if type(task) is not TaskSpec or not isinstance(store, EvidenceStore):
        raise ContractError("Route requires typed task and evidence store")
    task.to_dict()
    if type(history) is not tuple or len(history) > 8:
        raise ContractError("Route history must be an immutable tuple of at most eight attempts")
    _reference(task_start)
    store.observation(task_start)  # position() alone does not reject sticky disputes.
    if task_start.session != task.session or store.position(task_start) != task.origin:
        raise ContractError("Original task-start evidence must match task origin/session")
    counts, steps = {"outbound": 0, "return": 0}, {"outbound": 0, "return": 0}
    position, latest, waypoint = task.origin, task_start, None
    sources, identities = [task_start], set()
    for attempt in history:
        if type(attempt) is not RouteAttempt or type(attempt.stage) is not str or attempt.stage not in counts:
            raise ContractError("History requires typed outbound/return attempts")
        result, leg = attempt.result, attempt.stage
        if type(result) is not PrimitiveResult:
            raise ContractError("History requires typed results")
        result.to_dict()
        if result.action_id in identities:
            raise ContractError("History logical action IDs must be unique")
        identities.add(result.action_id)
        if ((leg == "outbound" and counts["return"]) or steps[leg] >= task.distance
                or (leg == "return" and steps["outbound"] != task.distance)):
            raise ContractError("History must follow outbound then return, without extra steps")
        before, after = result.before, result.after
        for ref in (before,) + ((after,) if after else ()):
            _reference(ref)
            if ref.session != task.session or ref.revision < latest.revision or ref.turn < latest.turn:
                raise ContractError("History evidence must be ordered in the original session")
            store.observation(ref)
            sources.append(ref)
            latest = ref
        if store.position(before) != position:
            raise ContractError("History route checkpoint changed")
        disposition = result.transport_disposition
        if disposition not in ("returned", "not_dispatched", "rejected"):
            raise ContractError("Unresolved history cannot resume")
        displacement = tuple(b - a for a, b in zip(position, store.position(after))) if after else None
        if result.observed_displacement is not None and result.observed_displacement != displacement:
            raise ContractError("History displacement disagrees with retained evidence")
        dx, dy, _ = DIRECTIONS[task.direction]
        if leg == "return": dx, dy = -dx, -dy
        if disposition == "returned":
            if after is None or result.observed_displacement is None:
                raise ContractError("Returned history requires after evidence and displacement")
            if displacement == (dx, dy, 0):
                if after.revision <= before.revision or not observed_step(store.observation(before),
                                                                         store.observation(after), dx, dy):
                    raise ContractError("Credited history needs an advanced exact movement observation")
                steps[leg] += 1
                position = store.position(after)
                if leg == "outbound" and steps[leg] == task.distance:
                    waypoint = after
            elif displacement != (0, 0, 0):
                raise ContractError("Unexpected displacement cannot resume")
        elif displacement not in (None, (0, 0, 0)):
            raise ContractError("Non-delivery cannot change route position")
        counts[leg] += 1
        if counts[leg] > 4:
            raise ContractError("History exceeds the maximum per-leg proposal count")
    return RouteSummary(counts["outbound"], counts["return"], steps["outbound"], steps["return"],
                        position, waypoint, latest, tuple(dict.fromkeys(sources)))


class MovementStage:
    """One task-bound remaining outbound/return leg, at most four total proposals.

    Original admission/start and settled history are trusted supervisor inputs.
    Derivation validates route geometry and cumulative budgets, never authority.
    Use one serialized caller and the same EvidenceStore for its lifetime.
    """
    def __init__(self, task: TaskSpec, *, stage_id: str, stage_version: int,
                 stage: Stage, store: EvidenceStore, task_start: EvidenceRef,
                 checkpoint: EvidenceRef, admission_monotonic: float, history: RouteHistory):
        if type(task) is not TaskSpec or type(task.budgets) is not Budgets:
            raise ContractError("Movement requires a typed immutable TaskSpec and Budgets")
        task.to_dict()
        StageResult(stage_id, stage_version, "blocked", Progress(0, (0, 0, 0)), (), None)
        if stage not in ("outbound", "return") or type(stage) is not str:
            raise ContractError("Movement stage must be outbound or return")
        if not _clock(admission_monotonic):
            raise ContractError("Original admission clock must be finite and nonnegative")
        summary = summarize_route(task, store, task_start, history)
        if ((stage == "return" and summary.outbound_steps != task.distance)
                or (stage == "outbound" and summary.return_count)):
            raise ContractError("Stage differs from verified route history")
        _reference(checkpoint)
        if (checkpoint.session != task.session or checkpoint.revision < summary.latest.revision
                or checkpoint.turn < summary.latest.turn or store.position(checkpoint) != summary.position):
            raise ContractError("Checkpoint differs from retained route history")
        self._task = task
        self._stage_id, self._stage_version = stage_id, stage_version
        self._store = store
        self._task_start = task_start
        self._leg_origin = task.origin if stage == "outbound" else task.target
        self._admission = admission_monotonic
        self._prior_count = summary.primitive_count
        self._prior_leg_count = summary.outbound_count if stage == "outbound" else summary.return_count
        dx, dy, action = DIRECTIONS[task.direction]
        if stage == "return":
            dx, dy = -dx, -dy
            action = next(a for x, y, a in DIRECTIONS.values() if (x, y) == (dx, dy))
        self._dx, self._dy, self._action = dx, dy, action
        self._target = task.target if stage == "outbound" else task.origin
        self._sources = tuple(dict.fromkeys(summary.sources + (checkpoint,)))
        self._checkpoint = checkpoint
        self._generation = store.authority_generation()
        self._last_monotonic = admission_monotonic
        self._last_timestamp_ms: int | None = None
        self._proposed_count = 0
        prior_steps = summary.outbound_steps if stage == "outbound" else summary.return_steps
        self._progress = Progress(prior_steps, (dx * prior_steps, dy * prior_steps, 0))
        self._pending: StepProposal | None = None
        self._evaluations: dict[str, SkillEvaluation] = {}
        self._history_ids = frozenset(item.result.action_id for item in history)
        self._terminal: SkillEvaluation | None = None

    @property
    def progress(self) -> Progress:
        return self._progress

    def _clocks(self, now_monotonic: float, now_timestamp_ms: int) -> bool:
        if (not _clock(now_monotonic) or now_monotonic < self._last_monotonic
                or type(now_timestamp_ms) is not int or now_timestamp_ms < 0
                or (self._last_timestamp_ms is not None and now_timestamp_ms < self._last_timestamp_ms)):
            return False
        self._last_monotonic, self._last_timestamp_ms = now_monotonic, now_timestamp_ms
        return True

    def _finish(self, disposition: str, reason: str,
                result: PrimitiveResult | None = None) -> SkillEvaluation:
        value = SkillEvaluation(result, self._progress, reason,
                                StageResult(self._stage_id, self._stage_version, disposition,
                                            self._progress, self._sources,
                                            self._pending.action_id if self._pending else None))
        self._terminal = value
        return value

    def _scan_sources(self) -> None:
        for source in self._sources:
            self._store.observation(source)

    def _remaining(self, now_monotonic: float, ref: EvidenceRef) -> tuple[int, int, int, float]:
        budgets = self._task.budgets
        return (budgets.primitives - self._prior_count - self._proposed_count,
                min(4, budgets.primitives_per_stage) - self._prior_leg_count - self._proposed_count,
                budgets.turns - (ref.turn - self._task_start.turn),
                budgets.wall_seconds - (now_monotonic - self._admission))

    def _guard(self, ref: EvidenceRef, *, now_timestamp_ms: int,
               paused: bool, frozen: bool) -> Vector:
        state = self._store.observation(ref)
        # Exact displacement/history checks establish the step count independently.
        # The caller still requires the immutable target position before completion.
        predicate = current_guard if self._progress.verified_steps == self._task.distance else guard
        position = predicate(state, self._dx, self._dy, paused=paused, frozen=frozen,
                             now_timestamp_ms=now_timestamp_ms)
        if self._action not in CARDINAL_MOVEMENT.action_bindings or self._action not in state["actions"]:
            raise MovementBlocked("Movement stopped: cardinal action is not registered in current evidence")
        return position

    def propose(self, action_id: str, *, now_monotonic: float, now_timestamp_ms: int,
                paused: bool, frozen: bool) -> StepProposal | SkillEvaluation:
        if type(action_id) is not str or not 1 <= len(action_id) <= 128:
            raise ContractError("Logical action ID must contain between one and 128 characters")
        if self._terminal is not None:
            return self._terminal
        if not self._clocks(now_monotonic, now_timestamp_ms):
            return self._finish("failed", "Invalid or regressing caller clock")
        if self._pending is not None:
            raise ContractError("One logical movement proposal is already unresolved")
        if action_id in self._evaluations or action_id in self._history_ids:
            raise ContractError("Logical action IDs cannot be reused")
        try:
            self._scan_sources()
            current = self._store.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            if current != self._checkpoint or self._store.authority_generation() != self._generation:
                raise EvidenceError("Movement checkpoint or authority generation changed")
            position = self._guard(current, now_timestamp_ms=now_timestamp_ms, paused=paused, frozen=frozen)
            expected_checkpoint = tuple(p + d for p, d in zip(self._leg_origin,
                                                             self._progress.displacement))
            if position != expected_checkpoint:
                raise EvidenceError("Movement route continuity changed")
            remaining = self._remaining(now_monotonic, current)
            if self._progress.verified_steps == self._task.distance and position == self._target:
                if min(remaining) < 0:
                    return self._finish("budget_exhausted", "Original task budget overshot before verification")
                return self._finish("completed", "Retained complete leg verified at fresh checkpoint")
            if min(remaining) <= 0 or self._task.budgets.primitive_wait_seconds <= 0:
                return self._finish("budget_exhausted", "Original task or stage budget exhausted")
            self._store.preflight_dispatch(current, now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        except MovementBlocked as exc:
            return self._finish("interrupted" if paused or frozen or "paused or frozen" in str(exc) else "blocked", str(exc))
        except EvidenceError as exc:
            return self._finish("unknown" if self._progress.verified_steps else "blocked", str(exc))
        wait = min(self._task.budgets.primitive_wait_seconds, self._remaining(now_monotonic, current)[3])
        self._pending = StepProposal(action_id, current, self._action,
                                     expected_position(position, self._dx, self._dy), wait)
        self._proposed_count += 1  # Conservative consumption, including later non-delivery.
        return self._pending

    def settle(self, result: PrimitiveResult, *, now_monotonic: float,
               now_timestamp_ms: int, paused: bool, frozen: bool) -> SkillEvaluation:
        if type(result) is not PrimitiveResult:
            raise ContractError("Settlement requires a typed PrimitiveResult")
        _reference(result.before)
        if result.after is not None:
            _reference(result.after)
        result.to_dict()
        if result.transport_disposition == "returned" and result.observed_displacement is None:
            raise ContractError("Returned movement requires independently checkable displacement")
        previous = self._evaluations.get(result.action_id)
        if previous is not None and previous.primitive_result != result:
            raise ContractError("Conflicting duplicate primitive result")
        if self._terminal is not None:
            if previous is not None:
                return previous
            raise ContractError("Terminal movement stage cannot accept a new result")
        if previous is not None:
            if not self._clocks(now_monotonic, now_timestamp_ms):
                return self._finish("failed", "Invalid or regressing caller clock", result)
            return previous
        proposal = self._pending
        if proposal is None or (result.action_id, result.before) != (proposal.action_id, proposal.before):
            raise ContractError("Result must match the outstanding logical ID and exact before reference")
        if not self._clocks(now_monotonic, now_timestamp_ms):
            return self._finish("failed", "Invalid or regressing caller clock", result)
        try:
            self._scan_sources()
            before_state = self._store.observation(result.before)
            after_state = self._store.observation(result.after) if result.after else None
            displacement = None
            if result.after is not None and result.after.session == result.before.session:
                displacement = tuple(b - a for a, b in zip(before_state["scene"]["position"],
                                                           after_state["scene"]["position"]))
                if result.observed_displacement is not None and result.observed_displacement != displacement:
                    raise ContractError("Supplied displacement disagrees with retained observations")
            current = self._store.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            checkpoint = result.after if result.after is not None else result.before
            expected_generation = self._generation + (checkpoint != self._checkpoint)
            if current != checkpoint or self._store.authority_generation() != expected_generation:
                raise EvidenceError("Intervening observation or invalidation prevents movement attribution")
            if result.after is not None and result.after.session == self._task.session:
                self._sources = tuple(dict.fromkeys(self._sources + (result.after,)))
            self._checkpoint, self._generation = checkpoint, expected_generation
        except EvidenceError as exc:
            value = self._finish("unknown", str(exc), result)
            self._evaluations[result.action_id] = value
            return value
        # Malformed or conflicting result data raises without releasing the pending proposal.
        disposition = result.transport_disposition
        if disposition in ("unknown", "dispatched"):
            value = self._finish("unknown", result.reason, result)
        else:
            self._pending = None
            if disposition in ("rejected", "not_dispatched"):
                value = self._finish("blocked", result.reason, result)
            elif (result.after.turn < result.before.turn or result.after.revision <= result.before.revision
                  or not observed_step(before_state, after_state, self._dx, self._dy)):
                value = self._finish("blocked", "First zero, unexpected or unverified movement displacement", result)
            else:
                self._progress = Progress(self._progress.verified_steps + 1,
                                          tuple(p + d for p, d in zip(self._progress.displacement,
                                                                     (self._dx, self._dy, 0))))
                value = self._post_step(result, now_monotonic=now_monotonic,
                                        now_timestamp_ms=now_timestamp_ms, paused=paused, frozen=frozen)
        self._evaluations[result.action_id] = value
        return value

    def _post_step(self, result: PrimitiveResult, *, now_monotonic: float,
                   now_timestamp_ms: int, paused: bool, frozen: bool) -> SkillEvaluation:
        try:
            position = self._guard(result.after, now_timestamp_ms=now_timestamp_ms, paused=paused, frozen=frozen)
            self._scan_sources()  # Older disputes invalidate completion even at the target.
        except MovementBlocked as exc:
            return self._finish("interrupted" if paused or frozen or "paused or frozen" in str(exc) else "blocked",
                                str(exc), result)
        except EvidenceError as exc:
            return self._finish("unknown", str(exc), result)
        primitives, stage_primitives, turns, wall = self._remaining(now_monotonic, result.after)
        if min(primitives, stage_primitives, turns, wall) < 0:
            return self._finish("budget_exhausted", "Committed movement overshot an original task or stage budget", result)
        if self._progress.verified_steps == self._task.distance and position == self._target:
            return self._finish("completed", "Full leg target and all requested steps verified", result)
        if min(primitives, stage_primitives, turns, wall) <= 0:
            return self._finish("budget_exhausted", "Original task or stage budget exhausted after movement", result)
        return SkillEvaluation(result, self._progress, "Exact unit movement verified", None)
