"""Bounded passive reflection data and a mailbox drained by the mission writer.

This module creates no executor and performs no input, storage or model work.
Queued receipts are not durable. Only the caller's existing writer applies short
bookkeeping callbacks; accepted procedure adoption remains outside this boundary.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from copy import deepcopy
from hashlib import sha256
import math
from queue import Queue
from threading import Condition, current_thread
from time import monotonic, time as wall_time
from typing import Any

from .contracts import (
    ContractError, _array, _enum, _integer, _nullable, _object, _text,
    canonical, json_object, validate_json,
)
from .mission_contracts import validate_request
from .procedures import procedure_schema, validate_procedure

VERSION = "reflection/2"
MAX_JOB_BYTES = 65_536
MAX_PROPOSAL_BYTES = 32_768
MAX_COMMAND_BYTES = MAX_PROPOSAL_BYTES + 2048
MAX_RESULT_BYTES = 65_536
MAX_RECORDS = 64
_ID = {**_text(128), "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
       "not": {"pattern": r"[^A-Za-z0-9_-]"}}
_SOURCE = _object({"mission_id": _ID, "source_id": _ID})
_PHASES = ("admitted", "active", "paused", "reconciling", "handoff", "finishing",
           "completed", "failed", "stopped")
_CLOSED_PHASES = frozenset(("completed", "failed", "stopped"))
_JOB_STATES = ("offered", "claimed", "completed", "expired", "unknown", "unreviewed")
_EXECUTABLE = frozenset(("observe", "skill", "lifecycle", "reconcile", "handoff",
                         "claim", "readmit", "stop"))
_JOB_SCHEMA = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "ReflectionJob"},
    "id": _ID, "mission_id": _ID, "reflector_id": _ID, "epoch": _integer(),
    "memory_version": _integer(), "after_sequence": _integer(4096),
    "through_sequence": _integer(4096),
    "included_request_ids": {**_array(_ID, 32, 1), "uniqueItems": True},
    "omitted_requests": _integer(4096),
    "omitted_sources": _integer(4096), "omitted_procedures": _integer(256),
    "sources": {**_array(_SOURCE, 8), "uniqueItems": True},
    # The existing current request validator owns its tagged closed union.
    "trajectory": _array(_object({"request": {"type": "object"},
        "state": _enum("completed", "partial", "blocked", "failed", "unknown", "paused"),
        "result": {"type": "object"}}), 32, 1),
    "procedures": _array(procedure_schema(), 16),
})
_PROPOSAL_SCHEMA = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "ReflectionProposal"},
    "id": _ID, "job_id": _ID, "mission_id": _ID, "reflector_id": _ID,
    "epoch": _integer(), "cutoff_sequence": _integer(4096), "memory_version": _integer(),
    "candidates": _array(procedure_schema(), 4),
    "notes": _array(_object({"kind": _enum("warning", "question", "correction", "finding"),
        "text": _text(2048), "request_ids": {**_array(_ID, 16), "uniqueItems": True},
        "source_refs": {**_array(_SOURCE, 8), "uniqueItems": True}}), 8),
    "reason": _text(1024),
})
_COMMAND_FIELDS = {"schema": {"const": VERSION}, "kind": _enum("claim", "submit"),
                   "command_id": _ID, "mission_id": _ID, "reflector_id": _ID, "job_id": _ID}
_WRAPPER_SCHEMA = _object({
    "job": _JOB_SCHEMA, "state": _enum(*_JOB_STATES),
    "claimed_at": _nullable({"type": "number", "minimum": 0}),
    "deadline": _nullable({"type": "number", "minimum": 0}),
})


def proposal_schema() -> dict[str, Any]:
    """Return an independent current proposal schema for structured adapters."""
    return deepcopy(_PROPOSAL_SCHEMA)


def _bounded(value: dict | str | bytes, maximum: int, label: str) -> dict[str, Any]:
    result = json_object(value)
    try:
        size = len(canonical(result).encode("utf-8"))
    except UnicodeError as exc:
        raise ContractError(f"{label} requires valid UTF-8 canonical JSON") from exc
    if size > maximum:
        raise ContractError(f"{label} exceeds {maximum} canonical bytes")
    return result


def validate_job(value: dict | str | bytes) -> dict[str, Any]:
    """Validate exact bounded source data, without establishing its truth."""
    result = _bounded(value, MAX_JOB_BYTES, "ReflectionJob")
    validate_json(result, _JOB_SCHEMA)
    if result["through_sequence"] <= result["after_sequence"]:
        raise ContractError("ReflectionJob cutoff must follow its starting sequence")
    request_ids = []
    for row in result["trajectory"]:
        request = validate_request(row["request"])
        if request["kind"] not in _EXECUTABLE:
            raise ContractError("Reflection trajectory requires executable non-memory requests")
        if request["mission_id"] != result["mission_id"]:
            raise ContractError("Reflection trajectory belongs to another mission")
        request_ids.append(request["request_id"])
    if request_ids != result["included_request_ids"]:
        raise ContractError("Reflection trajectory must preserve included request IDs and order")
    for record in result["procedures"]:
        validate_procedure(record)
    return result


def _support_closure(job: dict) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    requests = {(job["mission_id"], request_id) for request_id in job["included_request_ids"]}
    sources = {(source["mission_id"], source["source_id"]) for source in job["sources"]}
    for record in job["procedures"]:
        for episode in (*record["support"], *record["counterexamples"]):
            requests.update((episode["mission_id"], identity) for identity in episode["request_ids"])
            sources.update((episode["mission_id"], identity) for identity in episode["source_ids"])
    return requests, sources


def validate_proposal(value: dict | str | bytes, job: dict | str | bytes | None = None) -> dict[str, Any]:
    """Validate advisory output and, when supplied, its immutable input closure.

    Actual source availability, candidate ownership/environment and adoption are
    the durable writer's responsibility. No prose is evaluated as code or input.
    """
    result = _bounded(value, MAX_PROPOSAL_BYTES, "ReflectionProposal")
    validate_json(result, _PROPOSAL_SCHEMA)
    for candidate in result["candidates"]:
        validate_procedure(candidate)
    if job is None:
        return result
    original = validate_job(job)
    expected = {"job_id": original["id"], "mission_id": original["mission_id"],
                "reflector_id": original["reflector_id"], "epoch": original["epoch"],
                "cutoff_sequence": original["through_sequence"],
                "memory_version": original["memory_version"]}
    if any(result[key] != value for key, value in expected.items()):
        raise ContractError("ReflectionProposal differs from its original job header/cutoff")
    requests, sources = _support_closure(original)
    request_ids = {identity for _, identity in requests}
    for candidate in result["candidates"]:
        for episode in (*candidate["support"], *candidate["counterexamples"]):
            if (not {(episode["mission_id"], identity) for identity in episode["request_ids"]} <= requests
                    or not {(episode["mission_id"], identity) for identity in episode["source_ids"]} <= sources):
                raise ContractError("Candidate support is outside the original job closure")
    for note in result["notes"]:
        if (not set(note["request_ids"]) <= request_ids
                or not {(ref["mission_id"], ref["source_id"]) for ref in note["source_refs"]} <= sources):
            raise ContractError("Reflection note is outside the original job closure")
    return result


def validate_command(value: dict | str | bytes) -> dict[str, Any]:
    """Validate one stable advisory-only claim/submission envelope."""
    result = _bounded(value, MAX_COMMAND_BYTES, "ReflectionCommand")
    fields = dict(_COMMAND_FIELDS)
    if result.get("kind") == "submit":
        fields["proposal"] = _PROPOSAL_SCHEMA
    validate_json(result, _object(fields))
    if result["kind"] == "submit":
        proposal = validate_proposal(result["proposal"])
        if any(proposal[key] != result[key] for key in ("job_id", "mission_id", "reflector_id")):
            raise ContractError("ReflectionCommand and proposal headers differ")
    return result


def _integer_limit(value: Any, maximum: int, label: str, minimum: int = 1) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError(f"{label} must be an integer in {minimum}..{maximum}")


def _identity(value: str) -> None:
    validate_json({"id": value}, _object({"id": _ID}))


def _digest(value: dict) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()


class ReflectiveExchange:
    """A per-admission, bounded passive cache and advisory ingress mailbox.

    Queue capacity includes the callback in flight. Original operation identities
    and outcomes survive lost collectors; bodies are discarded after application.
    The first drain/publication binds the existing writer thread. There is no
    thread creation, durable store, deadline renewal or input authority here.
    """

    def __init__(self, *, pending_limit: int = 2, max_operations: int = 128,
                 wall_clock: Callable[[], float] = wall_time) -> None:
        _integer_limit(pending_limit, 2, "pending_limit")
        _integer_limit(max_operations, 128, "max_operations")
        self._pending_limit = pending_limit
        self._wall_clock = wall_clock
        self._max_operations = max_operations
        self._condition = Condition()
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=2)
        self._pending = 0
        self._operations: dict[str, dict[str, Any]] = {}
        self._writer = None
        self._draining = False
        self._scope: tuple[str, str] | None = None
        self._phase = "admitted"
        self._epoch = 0
        self._jobs: dict[str, dict[str, Any]] = {}
        self._proposals: dict[str, dict[str, Any]] = {}
        self._view: list[dict[str, Any]] = []
        self._proposal_view: list[str] = []
        self._sealed = False
        self._terminated = False

    def _bind_writer(self) -> None:
        writer = current_thread()
        if self._writer is None:
            self._writer = writer
        elif self._writer is not writer:
            raise ContractError("Reflection mutation requires the original mission writer thread")

    def _check_scope(self, mission_id: str, reflector_id: str) -> None:
        scope = (mission_id, reflector_id)
        if self._scope is not None and self._scope != scope:
            raise ContractError("Reflection exchange cannot change admission/reflector scope")

    def offer(self, command: dict | str | bytes) -> dict[str, Any]:
        """Stage a body once; busy is a known zero-admission disposition."""
        received_at = self._wall_clock()
        if type(received_at) not in (int, float) or not math.isfinite(received_at) or not 0 <= received_at <= 10**12:
            raise ContractError("Reflection ingress requires its actual finite software receipt clock")
        body = validate_command(command)
        identity = body["command_id"]
        digest = _digest(body)
        with self._condition:
            self._check_scope(body["mission_id"], body["reflector_id"])
            previous = self._operations.get(identity)
            if previous is not None:
                if previous["digest"] != digest:
                    raise ContractError("Conflicting body for an immutable reflection command ID")
                return deepcopy(previous["outcome"])
            if self._sealed or self._phase in _CLOSED_PHASES or (
                    self._phase == "finishing" and body["kind"] == "claim"):
                return {"status": "rejected", "admitted": False, "command_id": identity,
                        "reason": "Reflection admission is closing", "grants_authority": False}
            if self._pending >= self._pending_limit or len(self._operations) >= self._max_operations:
                reason = "pending_limit" if self._pending >= self._pending_limit else "operation_limit"
                return {"status": "busy", "admitted": False, "command_id": identity,
                        "reason": reason, "grants_authority": False}
            self._scope = (body["mission_id"], body["reflector_id"])
            outcome = {"status": "pending", "admitted": True, "command_id": identity,
                       "grants_authority": False}
            self._operations[identity] = {"digest": digest, "outcome": outcome, "received_at": float(received_at)}
            self._pending += 1
            self._queue.put_nowait(body)
            return deepcopy(outcome)

    def received_at(self, command_id: str) -> float:
        """Original software ingress time for the writer, never caller-supplied JSON."""
        _identity(command_id)
        with self._condition:
            self._bind_writer()
            if command_id not in self._operations:
                raise ContractError("Reflection command has no original ingress receipt")
            return self._operations[command_id]["received_at"]

    def collect(self, command_id: str) -> dict[str, Any]:
        """Read the original in-memory receipt, without any durable lookup."""
        _identity(command_id)
        with self._condition:
            previous = self._operations.get(command_id)
            if previous is not None:
                return deepcopy(previous["outcome"])
            return {"status": "missing", "admitted": False, "command_id": command_id,
                    "grants_authority": False}

    def restore(self, records: Sequence[dict]) -> None:
        """Hydrate verified durable receipts on the writer, without requeueing work."""
        self._bind_writer()
        if not isinstance(records, (list, tuple)) or len(records) > self._max_operations:
            raise ContractError("Reflection receipt restoration exceeds its finite bound")
        restored = {}
        scope = self._scope
        for record in records:
            if type(record) is not dict or set(record) != {"command", "result", "received_at"}:
                raise ContractError("Reflection restoration requires exact durable receipt data")
            body = validate_command(record["command"])
            result = _bounded(record["result"], MAX_RESULT_BYTES, "Reflection durable result")
            receipt = record["received_at"]
            if type(receipt) not in (int, float) or not math.isfinite(receipt) or not 0 <= receipt <= 1e12:
                raise ContractError("Reflection durable receipt has an invalid software clock")
            selected = (body["mission_id"], body["reflector_id"])
            if scope is not None and selected != scope:
                raise ContractError("Reflection restored receipt changes original scope")
            scope = selected
            identity = body["command_id"]
            if identity in restored:
                raise ContractError("Duplicate restored reflection command identity")
            restored[identity] = {"digest": _digest(body), "received_at": float(receipt),
                "outcome": {"status": "committed", "admitted": True,
                    "command_id": identity, "result": result, "grants_authority": False}}
        with self._condition:
            if self._operations or self._pending:
                raise ContractError("Reflection receipt restoration requires a fresh cache")
            self._operations = restored
            self._scope = scope

    def source_allowed(self, *, mission_id: str, reflector_id: str,
                       job_id: str, source_id: str) -> bool:
        """Authorize only a retained current-mission image in an original job."""
        for identity in (mission_id, reflector_id, job_id, source_id):
            _identity(identity)
        with self._condition:
            if self._scope != (mission_id, reflector_id):
                return False
            job = self._jobs.get(job_id)
            return job is not None and {"mission_id": mission_id, "source_id": source_id} in job["sources"]

    def seal_ingress(self, *, permanent: bool) -> None:
        """Stop new bodies; only permanent closure also terminates passive readers."""
        with self._condition:
            self._bind_writer()
            self._sealed = True
            self._terminated = self._terminated or permanent
            self._condition.notify_all()

    def reopen_ingress(self) -> None:
        """Cancel a preterminal seal; original jobs/results/windows stay unchanged."""
        with self._condition:
            self._bind_writer()
            if self._terminated or self._phase in _CLOSED_PHASES:
                raise ContractError("A terminal reflective exchange cannot be reopened")
            self._sealed = False
            self._condition.notify_all()

    def drain(self, apply: Callable[[dict], dict], *, max_operations: int = 2) -> int:
        """Run at most two callbacks on the existing writer, outside the lock.

        Any callback/result-validation exception leaves an unknown original
        outcome and is re-raised for the caller's durable failure policy.
        """
        _integer_limit(max_operations, 2, "drain max_operations", minimum=0)
        if not callable(apply):
            raise ContractError("Reflection drain requires a bookkeeping callback")
        with self._condition:
            self._bind_writer()
            if self._draining:
                raise ContractError("Reflection drain cannot recursively apply callbacks")
            self._draining = True
        count = 0
        try:
            while count < max_operations:
                with self._condition:
                    if self._queue.empty():
                        break
                    body = self._queue.get_nowait()
                    identity = body["command_id"]
                try:
                    returned = apply(deepcopy(body))
                    if type(returned) is not dict:
                        raise ContractError("Reflection callback must return a JSON object")
                    result = _bounded(returned, MAX_RESULT_BYTES, "Reflection callback result")
                except BaseException:
                    with self._condition:
                        self._operations[identity]["outcome"] = {
                            "status": "unknown", "admitted": True, "command_id": identity,
                            "grants_authority": False}
                        self._pending -= 1
                        self._queue.task_done()
                        self._condition.notify_all()
                    raise
                with self._condition:
                    self._operations[identity]["outcome"] = {
                        "status": "committed", "admitted": True, "command_id": identity,
                        "result": result, "grants_authority": False}
                    self._pending -= 1
                    self._queue.task_done()
                    self._condition.notify_all()
                count += 1
            return count
        finally:
            with self._condition:
                self._draining = False

    def publish(self, *, mission_id: str, reflector_id: str, phase: str, epoch: int,
                jobs: Sequence[dict], proposals: Sequence[dict]) -> None:
        """Publish one validated cached view atomically from the mission writer."""
        header = json_object({"mission_id": mission_id, "reflector_id": reflector_id,
                              "phase": phase, "epoch": epoch})
        validate_json(header, _object({"mission_id": _ID, "reflector_id": _ID,
                                      "phase": _enum(*_PHASES), "epoch": _integer()}))
        with self._condition:
            self._bind_writer()
            self._check_scope(mission_id, reflector_id)
            new_jobs = dict(self._jobs)
            new_advice = dict(self._proposals)
        for values in (jobs, proposals):
            if (not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray))
                    or len(values) > MAX_RECORDS):
                raise ContractError("Reflection publication requires at most 64 records per sequence")
        wrappers, advice = [], []
        for value in jobs:
            if type(value) is not dict:
                raise ContractError("Reflection job wrapper must be a JSON object")
            wrapper = json_object(value)
            validate_json(wrapper, _WRAPPER_SCHEMA)
            wrapper["job"] = validate_job(wrapper["job"])
            wrappers.append(wrapper)
        for value in proposals:
            advice.append(validate_proposal(value))
        for record in [*(wrapper["job"] for wrapper in wrappers), *advice]:
            if record["mission_id"] != mission_id or record["reflector_id"] != reflector_id:
                raise ContractError("Reflection publication record has another mission/reflector")
        if (len({wrapper["job"]["id"] for wrapper in wrappers}) != len(wrappers)
                or len({record["id"] for record in advice}) != len(advice)):
            raise ContractError("Reflection publication contains duplicate record identities")
        # Only this writer can publish. Validate its immutable snapshot outside
        # the condition so record validation cannot occupy passive ingress.
        for original, records in ((new_jobs, [wrapper["job"] for wrapper in wrappers]),
                                  (new_advice, advice)):
            for record in records:
                identity = record["id"]
                if identity in original and _digest(original[identity]) != _digest(record):
                    raise ContractError("Conflicting immutable reflection record body")
                original[identity] = record
            if len(original) > MAX_RECORDS:
                raise ContractError("Reflection admission exceeds 64 lifetime record identities")
        for record in advice:
            original = new_jobs.get(record["job_id"])
            if original is None:
                raise ContractError("Reflection proposal requires its original cached job")
            validate_proposal(record, original)
        wrappers.sort(key=lambda wrapper: (wrapper["state"] != "claimed",
                      wrapper["job"]["through_sequence"], wrapper["job"]["after_sequence"],
                      wrapper["job"]["id"]))
        with self._condition:
            self._check_scope(mission_id, reflector_id)
            self._scope = (mission_id, reflector_id)
            self._phase, self._epoch = phase, epoch
            self._jobs, self._proposals = new_jobs, new_advice
            self._view = wrappers
            self._proposal_view = [record["id"] for record in advice]
            self._condition.notify_all()

    def next_job(self, *, mission_id: str, reflector_id: str,
                 wait_seconds: float = 0) -> dict[str, Any]:
        """Read/wait on the cache only; receipt never claims or renews a job."""
        _identity(mission_id)
        _identity(reflector_id)
        if (type(wait_seconds) not in (int, float) or not math.isfinite(wait_seconds)
                or not 0 <= wait_seconds <= 15):
            raise ContractError("Reflection wait must be finite and within 0..15 seconds")
        end = monotonic() + wait_seconds
        with self._condition:
            if wait_seconds and self._writer is current_thread():
                raise ContractError("Mission writer cannot wait for reflection work")
            while True:
                if self._scope is not None and self._scope != (mission_id, reflector_id):
                    return {"status": "idle", "grants_authority": False}
                if self._terminated or self._phase in _CLOSED_PHASES:
                    return {"status": "closed", "grants_authority": False}
                if not self._sealed and self._phase != "finishing":
                    for wrapper in self._view:
                        if wrapper["state"] in ("offered", "claimed"):
                            return {"status": wrapper["state"], "job": deepcopy(wrapper),
                                    "grants_authority": False}
                remaining = end - monotonic()
                if remaining <= 0:
                    return {"status": "idle", "grants_authority": False}
                self._condition.wait(remaining)

    def proposal(self, *, mission_id: str, proposal_id: str) -> dict[str, Any]:
        """Return cached advice scoped to its original mission."""
        _identity(mission_id)
        _identity(proposal_id)
        with self._condition:
            record = self._proposals.get(proposal_id)
            if (record is None or record["mission_id"] != mission_id
                    or proposal_id not in self._proposal_view):
                return {"status": "missing", "grants_authority": False}
            return {"status": "available", "proposal": deepcopy(record), "grants_authority": False}

    def summary(self) -> dict[str, Any]:
        """Expose bounded counts and identities, never retained trajectory bodies."""
        with self._condition:
            counts = {state: 0 for state in ("pending", "committed", "unknown")}
            for operation in self._operations.values():
                counts[operation["outcome"]["status"]] += 1
            return {"mission_id": self._scope[0] if self._scope else None,
                    "reflector_id": self._scope[1] if self._scope else None,
                    "phase": self._phase, "epoch": self._epoch,
                    "pending": self._pending, "operations": len(self._operations),
                    "operation_states": counts,
                    "jobs": [{"id": wrapper["job"]["id"], "state": wrapper["state"]}
                             for wrapper in self._view],
                    "proposals": list(self._proposal_view),
                    "job_count": len(self._jobs), "proposal_count": len(self._proposals),
                    "grants_authority": False}
