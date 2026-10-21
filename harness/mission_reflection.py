"""Private advisory composition on the existing mission writer, never an executor.

The mailbox accepts passive HTTP work while a skill runs. Only completed semantic
boundaries and idle writer ticks mutate SQLite; no model or network wait runs here.
"""
from __future__ import annotations

from hashlib import sha256

from .gameplay.contracts import ContractError, canonical
from .gameplay.evidence import EvidenceError
from .gameplay.mission_ledger import TERMINAL
from .gameplay.reflection import ReflectiveExchange, VERSION, validate_job


class RegisteredReflection:
    def __init__(self, runtime):
        self.runtime = runtime
        self.exchange: ReflectiveExchange | None = None
        self._jobs: tuple[dict, ...] = ()
        self._proposals: tuple[dict, ...] = ()
        self._dirty = False
        self._semantic_count = 0
        self._urgent = False
        self._published = None
        self._revision = 0
        self._coverage = {"unreviewed_requests": 0, "reason": None}

    def reset(self) -> None:
        r = self.runtime
        policy = r._admission.learning
        exchange = (None if policy is None or policy.reflector_id is None else
                    ReflectiveExchange(pending_limit=policy.reflection_limits.pending, wall_clock=r._wall))
        self._jobs, self._proposals = (), ()
        self._dirty, self._urgent, self._semantic_count = False, False, 0
        self._published = None
        self._revision = 0
        self._coverage = {"unreviewed_requests": 0, "reason": None}
        if exchange is not None:
            exchange.restore(r._ledger.reflection_command_records())
            self._jobs, self._proposals = r._ledger.reflection_records()
        with r._metadata:
            self.exchange = exchange
        if exchange is not None:
            after = self._jobs[-1]["job"]["through_sequence"] if self._jobs else 0
            for sequence, row in enumerate(r._ledger.request_records(), 1):
                if sequence > after:
                    self.completed(row["request"], row["state"])
            self._publish()

    def current(self, mission_id: str, reflector_id: str | None = None) -> ReflectiveExchange:
        r = self.runtime
        with r._metadata:
            exchange, admission = self.exchange, r._admission
            closed = r._closed.is_set()
        if (closed or exchange is None or admission is None or admission.mission_id != mission_id
                or reflector_id is not None and admission.learning.reflector_id != reflector_id):
            raise ContractError("No matching admitted advisory role")
        return exchange

    def source(self, *, mission_id: str, reflector_id: str, job_id: str, source_id: str):
        exchange = self.current(mission_id, reflector_id)
        if not exchange.source_allowed(mission_id=mission_id, reflector_id=reflector_id,
                                       job_id=job_id, source_id=source_id):
            raise EvidenceError("Image is outside the original reflection job allowlist")
        return self.runtime.source(mission_id, source_id)

    def summary(self):
        return None if self.exchange is None else {**self.exchange.summary(), **self._coverage}

    def completed(self, request: dict, disposition: str) -> None:
        if self.exchange is None or request["kind"] in ("start", "remember", "correct"):
            return
        self._dirty = True
        self._coverage["unreviewed_requests"] += 1
        self._urgent |= disposition in ("blocked", "failed", "unknown", "paused")
        # Children and setup remain in the trajectory, but do not each wake the
        # learner. Four root decisions coalesce routine work; surprises are early.
        if request["kind"] == "skill" and request.get("phase_id") is None:
            self._semantic_count += 1
            self._urgent |= disposition not in ("completed", "partial")
        elif request["kind"] in ("reconcile", "handoff", "claim", "readmit", "stop"):
            self._urgent = True

    def _publish(self) -> None:
        r = self.runtime
        state = r._ledger.snapshot(now=r._wall())
        mark = (state["phase"], state["epoch"], self._revision)
        if mark == self._published:
            return
        self.exchange.publish(mission_id=r._admission.mission_id,
            reflector_id=r._admission.learning.reflector_id, phase=state["phase"], epoch=state["epoch"],
            jobs=self._jobs, proposals=self._proposals)
        self._published = mark

    def _apply(self, command: dict) -> dict:
        from .gameplay.mission_ledger import ReflectionRefusal
        r = self.runtime
        receipt = self.exchange.received_at(command["command_id"])
        now = r._wall()
        try:
            return r._ledger.apply_reflection(command, now=now, received_at=receipt)
        except ReflectionRefusal as exc:
            # Storage/clock failures are NOT this subtype and fault the writer.
            return r._ledger.record_reflection_rejection(command, str(exc)[:1024] or "Advisory refusal",
                now=now, received_at=receipt)

    def tick(self) -> None:
        if self.exchange is None:
            return
        r, changed = self.runtime, False
        if self.exchange.drain(self._apply):
            self._jobs, self._proposals = r._ledger.reflection_records()
            self._revision += 1
            changed = True
        state, now = r._ledger.snapshot(now=r._wall()), r._wall()
        if state["phase"] not in TERMINAL and any(
                row["state"] == "claimed" and row["deadline"] < now
                or state["phase"] == "finishing" and row["state"] == "offered" for row in self._jobs):
            r._ledger.expire_reflection(now=now)
            self._jobs, self._proposals = r._ledger.reflection_records()
            self._revision += 1
            changed = True
        if self._dirty and state["phase"] not in TERMINAL | {"finishing"}:
            changed |= self._schedule(state, now)
        self._publish()
        if changed:
            r._publish()

    def _schedule(self, state: dict, now: float) -> bool:
        r, policy = self.runtime, self.runtime._admission.learning
        limits = policy.reflection_limits
        if len(self._jobs) >= limits.jobs:
            self._coverage["reason"] = "Original reflective job allowance exhausted; trajectory retained"
            self._dirty = False
            return False
        if now >= state["deadline"]:
            self._coverage["reason"] = "Mission deadline passed; trajectory retained without new reflection"
            self._dirty = False
            return False
        if sum(row["state"] in ("offered", "claimed") for row in self._jobs) >= limits.pending:
            self._coverage["reason"] = "Pending reflection coalesces subsequent settled work"
            return False
        if not self._urgent and self._semantic_count < 4:
            self._coverage["reason"] = "Coalescing routine semantic decisions"
            return False
        after = self._jobs[-1]["job"]["through_sequence"] if self._jobs else 0
        records = r._ledger.request_records()
        rows = [(sequence, {"request": row["request"], "state": row["state"], "result": row["result"]})
                for sequence, row in enumerate(records, 1) if sequence > after
                and row["request"]["kind"] not in ("start", "remember", "correct")]
        self._coverage["unreviewed_requests"] = len(rows)
        if not rows or any(row["state"] in ("accepted", "running") for _, row in rows):
            return False
        settled = [(sequence, row) for sequence, row in rows if row["result"] is not None]
        if not settled:
            self._coverage["reason"] = "Interrupted requests have no original result; retained unreviewed"
            self._dirty = False
            return False
        selected = settled[:limits.requests_per_job]
        if len(settled) > limits.requests_per_job and limits.requests_per_job > 1:
            selected = [*selected[:-1], settled[-1]]
        heads = sorted(r._memory._procedure_heads().values(), key=lambda value: (value["procedure_id"], value["id"]))
        procedures = heads[:16]
        primitives = r._ledger.primitive_records()
        available = {ref.observation_id for ref in r._store.historical_references}
        while selected:
            identities = {row["request"]["request_id"] for _, row in selected}
            linked = []
            for _, row in selected:
                linked.extend(row["request"].get("sources", ()))
                linked.extend(row["result"].get("source_ids", ()))
            for primitive in primitives:
                if primitive["request_id"] in identities:
                    linked.extend(primitive["intent"][key] for key in ("source_before", "preflight_source"))
                    linked.extend(value for key, value in (primitive["result"] or {}).items()
                                  if key in ("source_before", "preflight_source", "source_after") and value is not None)
            distinct = list(dict.fromkeys(linked))
            sources = [identity for identity in distinct if identity in available][-limits.sources_per_job:]
            identity = "reflection-" + sha256(canonical(dict(mission_id=r._admission.mission_id,
                after=after, through=len(records))).encode()).hexdigest()
            job = dict(schema=VERSION, record_type="ReflectionJob", id=identity,
                mission_id=r._admission.mission_id, reflector_id=policy.reflector_id, epoch=state["epoch"],
                memory_version=r._memory_version, after_sequence=after, through_sequence=len(records),
                included_request_ids=[row["request"]["request_id"] for _, row in selected],
                omitted_requests=len(rows) - len(selected), omitted_sources=len(distinct) - len(sources),
                omitted_procedures=len(heads) - len(procedures),
                sources=[dict(mission_id=r._admission.mission_id, source_id=identity) for identity in sources],
                trajectory=[row for _, row in selected], procedures=procedures)
            if len(canonical(job).encode()) <= limits.context_bytes:
                validate_job(job)
                r._ledger.append_reflection_job(job, now=now)
                self._jobs, self._proposals = r._ledger.reflection_records()
                self._revision += 1
                self._dirty, self._urgent, self._semantic_count = False, False, 0
                self._coverage = {"unreviewed_requests": 0, "reason": None}
                return True
            if procedures:
                procedures = procedures[:-1]
            elif len(selected) > 1:
                # Preserve oldest obligation and latest event where two fit.
                selected = selected[:1] + selected[2:] if len(selected) > 2 else selected[:1]
            else:
                excluded = selected[0][0]
                settled = [(sequence, row) for sequence, row in settled if sequence != excluded]
                if not settled:
                    self._coverage["reason"] = "Single original result exceeds reflective context; retained unreviewed"
                    self._dirty = False
                    return False
                selected = settled[:limits.requests_per_job]
                if len(settled) > limits.requests_per_job and limits.requests_per_job > 1:
                    selected = [*selected[:-1], settled[-1]]
                procedures = heads[:16]
        return False

    def finish(self) -> None:
        """Close admission and settle bookkeeping, without asserting actor quiescence."""
        if self.exchange is None:
            return
        self.exchange.seal_ingress()
        self.exchange.drain(self._apply)
        self.runtime._ledger.settle_reflection(now=self.runtime._wall())
        self._jobs, self._proposals = self.runtime._ledger.reflection_records()
        self._revision += 1
        self._publish()

    def cancel_finish(self) -> None:
        if (self.exchange is not None and not self.runtime._closed.is_set()
                and self.runtime._ledger.snapshot(now=self.runtime._wall())["phase"] not in TERMINAL):
            self.exchange.reopen_ingress()
            self._publish()
