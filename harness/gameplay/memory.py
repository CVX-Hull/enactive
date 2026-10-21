"""Passive, bounded task memory. Snapshots describe evidence as of caller clocks.

Nothing here grants a run lease, advertises a skill, infers task completion, or
restores memory from a journal. EvidenceStore alone owns original image retention.
TaskMemory has one caller/writer, just like the task planner that will own it.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
import math
from typing import Literal

from .contracts import (
    ContractError, EvidenceRef, Fact, Interpretation, PlanCandidate,
    PrimitiveResult, SkillDescriptor, TaskSpec,
)
from .evidence import CapacityError, EvidenceError, EvidenceStore, DEFAULT_BYTES, DEFAULT_FRAMES

MAX_FACTS = 128
MAX_INTERPRETATIONS = 32
MAX_HYPOTHESES = 32
MAX_PLANS = 16
MAX_PROCEDURES = 16
MAX_ACTIONS = 32
MAX_TEXT_BYTES = 64 * 1024
MAX_TEXT_CHARS = 1024
MAX_SOURCES = 8
# Charge room for the one operator retirement reason (up to four UTF-8 bytes
# per codepoint), plus the fixed current-state diagnostic. Invalidation must
# remain possible even when the append budget is completely full.
STATE_TEXT_RESERVE = 4 * MAX_TEXT_CHARS + 128


@dataclass(frozen=True)
class Hypothesis:
    text: str
    sources: tuple[EvidenceRef, ...]
    tag: Literal["hypothesis"] = "hypothesis"


@dataclass(frozen=True)
class Belief:
    value: Interpretation | Hypothesis
    valid: bool = True
    reason: str = "Source retained; belief remains non-factual"


@dataclass(frozen=True)
class RememberedPlan:
    candidate: PlanCandidate
    evidence: EvidenceRef
    sources: tuple[EvidenceRef, ...]
    valid: bool = True
    reason: str = "Candidate retained for review; executable authority always belongs outside memory"


@dataclass(frozen=True)
class ProcedureReference:
    descriptor: SkillDescriptor
    sources: tuple[EvidenceRef, ...]
    failure: str | None
    valid: bool = True
    reason: str = "Reference only; no execution authority"
    advertises_execution: Literal[False] = False


@dataclass(frozen=True)
class RememberedAction:
    value: PrimitiveResult
    sources_valid: bool = True
    conflicted: bool = False
    reason: str = "Recorded observation only; no completion inference or execution authority"


@dataclass(frozen=True)
class MemoryCounts:
    source_facts: int
    interpretations: int
    hypotheses: int
    plans: int
    procedures: int
    actions: int
    unique_sources: int
    text_bytes: int  # Conservative charge includes reserved state-diagnostic bytes.


@dataclass(frozen=True)
class VerificationCost:
    """Unique source_status checks and the retained-image footprint ceiling.

    These are not total hash reads or bytes read per operation. EvidenceStore's
    current(), historical_facts() and position() also verify their referenced
    originals. Those bounded extra reads are separate from this deduplicated scan.
    """
    source_checks: int
    maximum_source_checks: int = DEFAULT_FRAMES
    maximum_retained_image_bytes: int = DEFAULT_BYTES


@dataclass(frozen=True)
class MemorySnapshot:
    task: TaskSpec
    execution_epoch: int
    as_of_monotonic: float
    as_of_timestamp_ms: int
    retired: bool
    reason: str
    current_facts: tuple[Fact, ...]
    last_seen: tuple[Fact, ...]
    disputed_facts: tuple[Fact, ...]
    interpretations: tuple[Belief, ...]
    hypotheses: tuple[Belief, ...]
    plans: tuple[RememberedPlan, ...]
    procedures: tuple[ProcedureReference, ...]
    actions: tuple[RememberedAction, ...]
    counts: MemoryCounts
    costs: VerificationCost
    grants_authority: Literal[False] = False


def _text(value: str) -> None:
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT_CHARS:
        raise ContractError("Memory text must contain 1 to 1024 characters")


def _text_size(value: object) -> int:
    # References already belong to the bounded EvidenceStore; count each retained
    # reference's metadata once in _counts rather than per dependency occurrence.
    if isinstance(value, EvidenceRef):
        return 0
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if is_dataclass(value) and not isinstance(value, type):
        return sum(_text_size(getattr(value, field.name)) for field in fields(value))
    if isinstance(value, tuple):
        return sum(_text_size(item) for item in value)
    return 0


class TaskMemory:
    """One immutable task/store and a monotonic execution epoch; no dispatcher.

    Call refresh after ingestion to retain new facts. snapshot rechecks all retained
    dependencies and current freshness but cannot promote a new observation. Old
    snapshots stay immutable and are explicitly classified as of their own clocks.
    Annotation/action operations recheck historical integrity without refreshing
    facts. Every live retrieval deduplicates the at most 32 original sources.
    """

    def __init__(self, task: TaskSpec, store: EvidenceStore, *, execution_epoch: int = 0):
        if not isinstance(task, TaskSpec) or not isinstance(store, EvidenceStore):
            raise ContractError("TaskMemory requires a typed task and evidence store")
        self._epoch_value(execution_epoch)
        self._task = task
        self._store = store
        self._store_generation = store.authority_generation()
        self._epoch = execution_epoch
        self._retired = False
        self._retirement_reason: str | None = None
        self._session_changed = False
        self._observed: EvidenceRef | None = None
        self._current: EvidenceRef | None = None
        self._facts: tuple[Fact, ...] = ()
        self._interpretations: tuple[Belief, ...] = ()
        self._hypotheses: tuple[Belief, ...] = ()
        self._plans: tuple[RememberedPlan, ...] = ()
        self._procedures: tuple[ProcedureReference, ...] = ()
        self._actions: tuple[RememberedAction, ...] = ()
        self._reason = "Explicit fresh observation required"

    @property
    def task(self) -> TaskSpec:
        return self._task

    @staticmethod
    def _epoch_value(epoch: int) -> None:
        if type(epoch) is not int or not 0 <= epoch <= 2**31 - 1:
            raise ContractError("Execution epoch must be a bounded nonnegative integer")

    def _active(self) -> None:
        if self._retired:
            raise EvidenceError("Task memory is retired")

    def _invalidate_plans(self, reason: str) -> None:
        self._reason = reason
        self._plans = tuple(replace(plan, valid=False, reason=reason) if plan.valid else plan
                            for plan in self._plans)

    def _check_generation(self) -> None:
        # The final frame may equal the original after an unseen A -> B -> A
        # sequence. Generation records that transient loss without disputing A's
        # historical truth or treating this counter as execution authority.
        generation = self._store.authority_generation()
        if generation != self._store_generation:
            self._store_generation = generation
            self._current = None
            self._invalidate_plans("Evidence authority changed")

    def _sources(self) -> tuple[EvidenceRef, ...]:
        references = [fact.evidence for fact in self._facts]
        for belief in self._interpretations + self._hypotheses:
            references.extend(belief.value.sources)
        for plan in self._plans:
            references.extend(plan.sources)
        for procedure in self._procedures:
            references.extend(procedure.sources)
        for action in self._actions:
            references.extend(self._action_sources(action.value))
        return tuple(dict.fromkeys(references))

    @staticmethod
    def _action_sources(result: PrimitiveResult) -> tuple[EvidenceRef, ...]:
        return (result.before,) + (() if result.after is None else (result.after,))

    def _scan(self, extra: tuple[EvidenceRef, ...] = ()) -> dict[EvidenceRef, str]:
        self._check_generation()
        references = tuple(dict.fromkeys(self._sources() + extra))
        if len(references) > DEFAULT_FRAMES:
            self._invalidate_plans("Source capacity exceeded")
            raise CapacityError("Memory dependencies exceed the 32-frame evidence bound")
        statuses: dict[EvidenceRef, str] = {}
        for ref in references:
            try:
                statuses[ref] = self._store.source_status(ref)
                if statuses[ref] != "retained" and ref == self._current:
                    self._current = None
            except EvidenceError:
                statuses[ref] = "disputed"
                self._current = None
                self._invalidate_plans("Source verification failed")
        def retained(sources: tuple[EvidenceRef, ...]) -> bool:
            return all(statuses[ref] == "retained" for ref in sources)
        for name in ("_interpretations", "_hypotheses"):
            beliefs = getattr(self, name)
            setattr(self, name, tuple(replace(b, valid=False, reason="Source disputed")
                                     if b.valid and not retained(b.value.sources) else b for b in beliefs))
        self._plans = tuple(replace(p, valid=False, reason="Source disputed")
                            if p.valid and not retained(p.sources) else p for p in self._plans)
        self._procedures = tuple(replace(p, valid=False, reason="Source disputed")
                                 if p.valid and not retained(p.sources) else p for p in self._procedures)
        self._actions = tuple(replace(a, sources_valid=False, reason="Source disputed")
                              if a.sources_valid and not retained(self._action_sources(a.value)) else a
                              for a in self._actions)
        self._check_generation()
        return statuses

    def _references(self, sources: tuple[EvidenceRef, ...], *, empty: bool = False) -> tuple[EvidenceRef, ...]:
        if type(sources) is not tuple or any(not isinstance(ref, EvidenceRef) for ref in sources):
            raise ContractError("Memory sources must be an immutable tuple of EvidenceRef values")
        unique = tuple(dict.fromkeys(sources))
        if not (0 if empty else 1) <= len(unique) <= MAX_SOURCES:
            raise ContractError("Annotation requires at most eight distinct source references")
        return unique

    def _require_retained(self, sources: tuple[EvidenceRef, ...], statuses: dict[EvidenceRef, str]) -> None:
        if any(statuses[ref] != "retained" for ref in sources):
            self._invalidate_plans("New record source is disputed or unavailable")
            raise EvidenceError("New memory records require retained undisputed sources")

    def _counts(self) -> MemoryCounts:
        sources = self._sources()
        values = (self._facts, self._interpretations, self._hypotheses,
                  self._plans, self._procedures, self._actions)
        metadata_bytes = sum(sum(len(str(getattr(ref, field.name)).encode("utf-8"))
                                 for field in fields(ref) if isinstance(getattr(ref, field.name), str))
                             for ref in sources)
        return MemoryCounts(len(self._facts), len(self._interpretations), len(self._hypotheses),
                            len(self._plans), len(self._procedures), len(self._actions),
                            len(sources), sum(_text_size(value) for value in values) + metadata_bytes
                            + _text_size(self._task) + STATE_TEXT_RESERVE)

    def _preflight(self, value: object, count: int, ceiling: int,
                   sources: tuple[EvidenceRef, ...] = ()) -> None:
        existing = set(self._sources())
        additional = tuple(ref for ref in sources if ref not in existing)
        metadata = sum(sum(len(getattr(ref, field.name).encode("utf-8"))
                           for field in fields(ref) if isinstance(getattr(ref, field.name), str))
                       for ref in additional)
        if count >= ceiling or self._counts().text_bytes + _text_size(value) + metadata > MAX_TEXT_BYTES:
            self._invalidate_plans("Memory capacity exceeded")
            raise CapacityError("Task memory count or text capacity exceeded; records preserved")

    def _synchronize(self, *, now_monotonic: float, now_timestamp_ms: int,
                     observe: bool, extra: tuple[EvidenceRef, ...] = ()) -> dict[EvidenceRef, str]:
        if (type(now_monotonic) not in (float, int) or not math.isfinite(now_monotonic)
                or now_monotonic < 0 or type(now_timestamp_ms) is not int or now_timestamp_ms < 0):
            self._current = None
            self._invalidate_plans("Invalid caller clocks")
            raise ContractError("Snapshot requires finite monotonic and integer wall clocks")
        statuses = self._scan(extra)
        try:
            ref = self._store.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        except EvidenceError:
            self._current = None
            self._invalidate_plans("Current evidence is missing, rejected, stale or unavailable")
            return statuses
        finally:
            # current() can itself invalidate on freshness or integrity failure.
            # Capture that generation before permitting any candidate retrieval.
            self._check_generation()
        if ref != self._observed:
            self._current = None
            self._invalidate_plans("Observation identity changed")
        if ref.session != self._task.session:
            self._session_changed = True
        if self._retired or self._session_changed:
            self._current = None
            self._invalidate_plans("Task retired or native session changed")
            return statuses
        if not observe:
            return statuses
        if ref not in statuses:
            if len(statuses) >= DEFAULT_FRAMES:
                self._current = None
                self._invalidate_plans("Memory source capacity exceeded; history preserved")
                raise CapacityError("Task memory dependencies exceed the 32-source bound")
            statuses[ref] = self._store.source_status(ref)
        if statuses[ref] != "retained":
            self._current = None
            self._invalidate_plans("Current evidence is disputed")
            return statuses
        if not any(fact.evidence == ref for fact in self._facts):
            facts = self._store.historical_facts(ref)
            self._preflight(facts, len(self._facts) + len(facts) - 1, MAX_FACTS, (ref,))
            self._facts += facts
        self._observed = self._current = ref
        self._reason = "Fresh observed facts; memory grants no authority"
        return statuses

    def _snapshot(self, statuses: dict[EvidenceRef, str], now_monotonic: float,
                  now_timestamp_ms: int) -> MemorySnapshot:
        current = tuple(f for f in self._facts if f.evidence == self._current and statuses[f.evidence] == "retained")
        historical = tuple(f for f in self._facts if f.evidence != self._current and statuses[f.evidence] == "retained")
        disputed = tuple(f for f in self._facts if statuses[f.evidence] != "retained")
        return MemorySnapshot(self._task, self._epoch, now_monotonic, now_timestamp_ms,
                              self._retired, self._retirement_reason or self._reason, current, historical, disputed,
                              self._interpretations, self._hypotheses, self._plans,
                              self._procedures, self._actions, self._counts(),
                              VerificationCost(len(statuses), DEFAULT_FRAMES, self._store.max_bytes))

    def refresh(self, *, now_monotonic: float, now_timestamp_ms: int) -> MemorySnapshot:
        """Retain fresh store facts if available; otherwise return explicit history."""
        statuses = self._synchronize(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms, observe=True)
        return self._snapshot(statuses, now_monotonic, now_timestamp_ms)

    def snapshot(self, *, now_monotonic: float, now_timestamp_ms: int) -> MemorySnapshot:
        statuses = self._synchronize(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms, observe=False)
        return self._snapshot(statuses, now_monotonic, now_timestamp_ms)

    def _annotate(self, text: str, sources: tuple[EvidenceRef, ...], *, hypothesis: bool) -> Belief:
        self._active()
        _text(text)
        sources = self._references(sources)
        statuses = self._scan(sources)
        self._require_retained(sources, statuses)
        # World beliefs are scoped to this immutable task's native world.
        if any(ref.session != self._task.session for ref in sources):
            raise EvidenceError("Beliefs must use the task's world session")
        value = Belief(Hypothesis(text, sources) if hypothesis else Interpretation(text, sources))
        name = "_hypotheses" if hypothesis else "_interpretations"
        previous = getattr(self, name)
        self._preflight(value, len(previous), MAX_HYPOTHESES if hypothesis else MAX_INTERPRETATIONS, sources)
        setattr(self, name, previous + (value,))
        return value

    def interpret(self, text: str, sources: tuple[EvidenceRef, ...]) -> Belief:
        return self._annotate(text, sources, hypothesis=False)

    def hypothesize(self, text: str, sources: tuple[EvidenceRef, ...]) -> Belief:
        return self._annotate(text, sources, hypothesis=True)

    def retain_plan(self, candidate: PlanCandidate, skill: SkillDescriptor, *,
                    sources: tuple[EvidenceRef, ...] = (), now_monotonic: float,
                    now_timestamp_ms: int) -> RememberedPlan:
        self._active()
        if not isinstance(candidate, PlanCandidate) or not isinstance(skill, SkillDescriptor):
            raise ContractError("Plan retention requires typed candidate and skill")
        extra = self._references(sources, empty=True)
        statuses = self._synchronize(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms,
                                     observe=False, extra=extra)
        if self._current is None or self._session_changed:
            raise EvidenceError("Refresh current task evidence before retaining a candidate")
        if any(a.conflicted or a.value.transport_disposition in {"unknown", "dispatched"} for a in self._actions):
            self._invalidate_plans("Unresolved or conflicting action")
            raise EvidenceError("An unresolved or conflicting action blocks candidates")
        references = self._references((self._current,) + extra)
        self._require_retained(references, statuses)
        if any(ref.session != self._task.session for ref in references):
            raise EvidenceError("Candidate dependencies must share the task session")
        candidate.check_binding(self._task, self._current, plan_id=candidate.plan_id,
                                plan_version=candidate.plan_version, execution_epoch=self._epoch, skill=skill)
        plan = RememberedPlan(candidate, self._current, references)
        self._preflight(plan, len(self._plans), MAX_PLANS, references)
        self._plans += (plan,)
        return plan

    def remember_procedure(self, descriptor: SkillDescriptor, sources: tuple[EvidenceRef, ...] = (),
                           *, failure: str | None = None) -> ProcedureReference:
        self._active()
        if not isinstance(descriptor, SkillDescriptor):
            raise ContractError("Procedure reference requires a typed versioned descriptor")
        if failure is not None:
            _text(failure)
        sources = self._references(sources, empty=failure is None)
        self._require_retained(sources, self._scan(sources))
        procedure = ProcedureReference(descriptor, sources, failure)
        self._preflight(procedure, len(self._procedures), MAX_PROCEDURES, sources)
        self._procedures += (procedure,)
        return procedure

    def record_action(self, result: PrimitiveResult) -> RememberedAction:
        self._active()
        if not isinstance(result, PrimitiveResult):
            raise ContractError("Action memory requires a typed PrimitiveResult")
        sources = self._action_sources(result)
        statuses = self._scan(sources)
        for index, previous in enumerate(self._actions):
            if previous.value.action_id == result.action_id:
                if previous.value == result:
                    return previous
                self._actions = self._actions[:index] + (replace(previous, conflicted=True,
                    reason="Conflicting duplicate action ID; original preserved"),) + self._actions[index + 1:]
                self._invalidate_plans("Conflicting duplicate action ID")
                raise EvidenceError("Conflicting duplicate action ID; original preserved")
        self._require_retained(sources, statuses)
        if result.before.session != self._task.session:
            raise EvidenceError("Action must originate in the task world")
        if result.observed_displacement is not None:
            before = self._store.position(result.before)
            after = self._store.position(result.after)
            if tuple(end - start for start, end in zip(before, after)) != result.observed_displacement:
                self._invalidate_plans("Action displacement contradicts source positions")
                raise EvidenceError("Action displacement contradicts source positions")
        action = RememberedAction(result)
        self._preflight(action, len(self._actions), MAX_ACTIONS, sources)
        self._actions += (action,)
        if result.transport_disposition in {"unknown", "dispatched"}:
            self._invalidate_plans("Unresolved action outcome")
        return action

    def advance_epoch(self, execution_epoch: int) -> None:
        self._active()
        self._epoch_value(execution_epoch)
        if execution_epoch <= self._epoch:
            raise ContractError("Execution epoch must strictly increase")
        self._epoch = execution_epoch
        self._invalidate_plans("Execution epoch advanced; verified history preserved")

    def retire(self, reason: str) -> None:
        _text(reason)
        self._retired = True
        self._retirement_reason = reason
        self._current = None
        self._invalidate_plans("Task retired")
