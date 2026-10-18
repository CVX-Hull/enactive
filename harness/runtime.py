"""One explicitly admitted gameplay worker; external plans are bounded data.

No gameplay authority is restored. The metadata lock is never held over native
I/O; Pause revokes controller authority before touching runtime bookkeeping.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
import json
import math
import threading
import time
from uuid import uuid4

from .controller import Controller, ControlError, RunLease
from .gameplay.contracts import Budgets, ContractError, DIRECTIONS, EvidenceRef, PlanCandidate, PrimitiveResult, TaskSpec
from .gameplay.evidence import EvidenceError, EvidenceStore
from .gameplay.planner import PlannerConfig, ProviderReply, ProviderUsage
from .gameplay.supervisor import WaypointSupervisor
from .gameplay.skills import CARDINAL_MOVEMENT


class _ExternalInbox:
    def __init__(self, clock, wall_clock):
        self.clock, self.wall_clock = clock, wall_clock
        self.lock = threading.Lock()
        self.pending = None
        self.candidate = None
        self.ready = threading.Event()
        self.disabled = False

    def invoke(self, snapshot, cancelled, deadline):
        if snapshot.mode != "external" or deadline is None:
            raise ContractError("External provider requires an original deadline")
        request = {"request_id": f"request-{uuid4().hex}",
                   "deadline_ms": int((self.wall_clock() + max(0, deadline - self.clock())) * 1000),
                   "input": json.loads(snapshot.request_json)}
        with self.lock:
            if self.disabled or cancelled.is_set() or self.clock() >= deadline:
                raise ContractError("Planning was cancelled or expired")
            self.pending = (request, deadline)
            self.candidate = None
            self.ready.clear()
        try:
            while not cancelled.is_set() and self.clock() < deadline:
                if self.ready.wait(0.02):
                    with self.lock:
                        if self.candidate is None:
                            raise ContractError("External planning invalidated")
                        candidate = self.candidate
                    return ProviderReply(candidate, ProviderUsage())
            raise ContractError("External planning cancelled or timed out")
        finally:
            with self.lock:
                if self.pending is not None and self.pending[0]["request_id"] == request["request_id"]:
                    self.pending = None
                    self.candidate = None

    def request(self):
        with self.lock:
            if (self.pending is None or self.disabled or self.candidate is not None
                    or self.clock() >= self.pending[1]):
                return None
            return copy.deepcopy(self.pending[0])

    def submit(self, identity, candidate):
        candidate = PlanCandidate.from_dict(candidate)
        encoded = json.dumps(candidate.to_dict(), allow_nan=False)
        if len(encoded.encode()) > 16_384:
            raise ContractError("Planner reply exceeds byte ceiling")
        with self.lock:
            if (self.disabled or self.pending is None or self.candidate is not None
                    or identity != self.pending[0]["request_id"] or self.clock() >= self.pending[1]):
                raise ContractError("Planning response is duplicate, late or stale")
            binding = self.pending[0]["input"]["binding"]
            for field in ("task_id", "task_version", "plan_id", "plan_version", "execution_epoch",
                          "evidence_session", "evidence_revision", "distance_remaining"):
                if getattr(candidate, field) != binding[field]:
                    raise ContractError("Planning response binding differs from original request")
            if candidate.stage != binding["expected_stage"]:
                raise ContractError("Planning response stage differs from original request")
            data = self.pending[0]["input"]
            candidate.check_binding(TaskSpec.from_dict(data["task"]), EvidenceRef.from_dict(data["packet"]["current"]),
                plan_id=binding["plan_id"], plan_version=binding["plan_version"],
                execution_epoch=binding["execution_epoch"], skill=CARDINAL_MOVEMENT)
            self.candidate = encoded
            self.ready.set()

    def cancel(self):
        with self.lock:
            self.disabled = True
            self.pending = None
            self.candidate = None
            self.ready.set()


class GameplayRuntime:
    """Connect the passive supervisor to exactly one controller run lease."""
    def __init__(self, controller: Controller, *, clock=time.monotonic, wall_clock=time.time):
        self.controller = controller
        self._clock, self._wall = clock, wall_clock
        self._metadata = threading.Lock()
        self._admission = threading.Lock()
        self._wake = threading.Event()
        self._closed = threading.Event()
        self._pause = threading.Event()
        self._pause_reason = "Operator Pause"
        self._snapshot = None
        self._supervisor: WaypointSupervisor | None = None
        self._store: EvidenceStore | None = None
        self._lease: RunLease | None = None
        self._inbox: _ExternalInbox | None = None
        self._thread = None
        self._queued: tuple[str, dict] | None = None
        self._operation_inflight = False
        self._last_receipt = None
        self._run_id = None
        self._io_error = None

    def _clocks(self):
        return {"now_monotonic": self._clock(), "now_timestamp_ms": int(self._wall() * 1000)}

    def status(self) -> dict | None:
        with self._metadata:
            snapshot = copy.deepcopy(self._snapshot)
        if snapshot is not None:
            native = self.controller.status()
            owner = native["run_lease"]
            snapshot["run"]["lease_owner"] = None if owner is None else owner["owner"]
            snapshot["run"]["paused"] = native["pause_requested"]
            if native["state"] is None or native["state"]["session"] != snapshot["task"]["session"]:
                snapshot["run"]["fresh"] = False
            # Cached metadata remains responsive during Observe/action exchanges.
            sources = snapshot["run"]["evidence"]
            if sources:
                latest = max(sources, key=lambda ref: ref["received_monotonic"])
                if (self._clock() - latest["received_monotonic"] > 3
                        or int(self._wall() * 1000) - latest["timestamp_ms"] > 3000):
                    snapshot["run"]["fresh"] = False
            request = None if self._inbox is None else self._inbox.request()
            snapshot["planner"]["pending_request_id"] = None if request is None else request["request_id"]
            snapshot["planner"]["deadline_ms"] = None if request is None else request["deadline_ms"]
        return snapshot

    def _publish(self):
        run = self._supervisor.status(**self._clocks()).to_dict()
        native = self.controller.status()
        owner = native["run_lease"]
        run["lease_owner"] = None if owner is None else owner["owner"]
        run["paused"] = native["pause_requested"]
        if native["state"] is None or native["state"]["session"] != self._supervisor.task.session:
            run["fresh"] = False
        run["next_check"] = ("Await external candidate and fresh observation" if run["state"] == "planning"
                             else "Await exact native receipt" if run["state"] == "executing"
                             else "Guard next primitive" if run["state"] == "admitted"
                             else "Explicit operator continuation or new task")
        if self._io_error is not None:
            run["last_public_reason"] = (run["last_public_reason"] + "; " + self._io_error)[:1024]
        snapshot = {"run_id": self._run_id, "task": self._supervisor.task.to_dict(), "run": run,
                    "planner": {"kind": "external_chat", "pending_request_id": None,
                                "deadline_ms": None, "usage_known": False},
                    "last_receipt": copy.deepcopy(self._last_receipt)}
        with self._metadata:
            if self._pause.is_set():
                snapshot["run"]["paused"] = True
                snapshot["run"]["lease_owner"] = None
            self._snapshot = snapshot

    def _ingest_snapshot(self, reservation=None):
        value, received = self.controller.observation_snapshot()
        if value is None or received is None:
            raise EvidenceError("No actual native observation receipt")
        return self._store.ingest(value, received_monotonic=received,
                                  reservation=reservation, **self._clocks())

    def command(self, kind: str, **payload: object) -> dict:
        fields = {"start": {"direction", "distance", "expected_session", "expected_revision"},
                  "continue": {"run_id", "execution_epoch", "expected_session", "expected_revision"},
                  "abandon": {"run_id", "execution_epoch"}, "planning_request": set(),
                  "plan": {"request_id", "candidate"}}
        try:
            if type(kind) is not str or kind not in fields or set(payload) != fields[kind]:
                raise ContractError("Unknown gameplay kind or exact fields mismatch")
            if self._closed.is_set():
                raise ContractError("Gameplay runtime is closed")
            if kind == "planning_request":
                return {"status": "accepted", "gameplay": self.status(),
                        "planning_request": None if self._inbox is None else self._inbox.request()}
            if kind == "plan":
                if self._inbox is None or self._pause.is_set():
                    raise ContractError("No live external planning request")
                try:
                    self._check_lease()
                except ControlError:
                    self._inbox.cancel()
                    raise
                with self.controller.data_lock:
                    self.controller._check_owner(self._lease, self.controller.pause_generation)
                    self._inbox.submit(payload["request_id"], payload["candidate"])
                self._wake.set()
            else:
                with self._admission:
                    if kind == "start":
                        self._start(payload)
                    else:
                        status = self.status()
                        if (status is None or payload["run_id"] != status["run_id"]
                                or type(payload["execution_epoch"]) is not int
                                or payload["execution_epoch"] != status["run"]["execution_epoch"]):
                            raise ContractError("Run identity or execution epoch is stale")
                        if self._queued is not None or self._operation_inflight:
                            raise ContractError("A lifecycle operation is already queued")
                        if kind == "continue":
                            if status["run"]["state"] in ("idle", "planning", "admitted", "executing", "completed", "abandoned", "unknown"):
                                raise ContractError("Run cannot continue in its current state")
                            native = self.controller.status()
                            if native["pause_requested"] or native["frozen"]:
                                raise ContractError("Explicit Observe/Resume is required before continuation")
                            value, _ = self.controller.observation_snapshot()
                            if value is None:
                                raise ContractError("Continuation requires current observed evidence")
                            self.controller._expect(value, payload["expected_session"], payload["expected_revision"])
                        else:
                            self.pause("Operator abandoned exact run")
                        self._queued = (kind, payload)
                        self._wake.set()
            return {"status": "accepted", "gameplay": self.status()}
        except (ContractError, ControlError, OSError) as exc:
            return {"status": "rejected", "error": str(exc), "gameplay": self.status()}

    def _start(self, payload):
        old = self.status()
        if self._thread is not None and self._thread.is_alive():
            raise ContractError("A gameplay worker already owns an admitted task")
        if old is not None and old["run"]["state"] != "abandoned":
            raise ContractError("Abandon the retained task before starting another")
        direction, distance = payload["direction"], payload["distance"]
        if type(direction) is not str or direction not in DIRECTIONS or type(distance) is not int or not 1 <= distance <= 4:
            raise ContractError("Waypoint requires a cardinal direction and distance 1–4")
        value, received = self.controller.observation_snapshot()
        if value is None or received is None:
            raise ContractError("Start requires a current native observation")
        self.controller._expect(value, payload["expected_session"], payload["expected_revision"])
        run_id = f"run-{uuid4().hex}"
        store = EvidenceStore(self.controller.bridge, self.controller.journal.parent / run_id)
        try:
            reference = store.ingest(value, received_monotonic=received, **self._clocks())
            origin = store.position(reference)
            target = tuple(p + d * distance for p, d in zip(origin, DIRECTIONS[direction]))
            task = TaskSpec(f"task-{uuid4().hex}", reference.session, origin, direction, distance,
                            target, 1, Budgets(), f"operator-{uuid4().hex}")
            task.to_dict()
            lease = self.controller.acquire_run(task.task_id, 0, run_id,
                expected_session=reference.session, expected_revision=reference.revision)
            self._store, self._run_id, self._lease = store, run_id, lease
            self._inbox = _ExternalInbox(self._clock, self._wall)
            self._pause.clear()
            self._last_receipt = None
            self._io_error = None
            self._supervisor = WaypointSupervisor(task, run_id=run_id, store=store,
                task_start=reference, admission_monotonic=self._clock(), clock=self._clock,
                planner_config=PlannerConfig("external-unreported", "external-chat-v1", mode="external"),
                provider=self._provide)
            self._supervisor.start(**self._clocks())
            self._publish()
            self._thread = threading.Thread(target=self._work, name=run_id, daemon=True)
            self._thread.start()
        except BaseException:
            if self._lease is not None and self._run_id == run_id:
                self._release()
            store.close()
            raise

    def _provide(self, snapshot, cancelled):
        return self._inbox.invoke(snapshot, cancelled, self._supervisor.planner.active_deadline())

    def pause(self, reason: str = "Operator Pause") -> dict:
        try:
            result = self.controller.pause()
        except OSError as exc:
            # Controller revokes in-process authority before filesystem writes.
            # Still cancel the player and publish stopped state if logging fails.
            self._io_error = f"Pause persistence failed: {exc}"[:512]
            result = {"status": "pause_requested", "error": self._io_error,
                      "detail": "Local authority revoked; native pause persistence is unconfirmed"}
        if self._inbox is not None:
            self._inbox.cancel()
        with self._metadata:
            self._pause_reason = str(reason)[:1024] or "Operator Pause"
            self._pause.set()
            if self._snapshot is not None:
                self._snapshot["run"]["paused"] = True
                self._snapshot["run"]["lease_owner"] = None
        self._wake.set()
        return result

    def _apply_pause(self):
        # Consume one signal exactly once. A newer Pause stays set while the
        # worker applies this one; never clear it after exposing a paused epoch.
        with self._metadata:
            if not self._pause.is_set():
                return
            reason = self._pause_reason
            self._pause.clear()
        self._supervisor.pause(reason, **self._clocks())
        self._lease = None

    def _release(self):
        lease, self._lease = self._lease, None
        if lease is not None:
            try:
                self.controller.release_run(lease)
            except ControlError:
                pass  # A revoked lease cannot release another owner's authority.
            except OSError as exc:
                self._io_error = f"Release persistence failed: {exc}"[:512]

    def _check_lease(self):
        native = self.controller.status()
        if (self._lease is None or native["run_lease"] != asdict(self._lease)
                or native["pause_requested"] or native["frozen"]):
            raise ControlError("Run lease lost, native takeover, recovery or world change")

    def _dispatch(self):
        supervisor = self._supervisor
        intent = supervisor.propose(f"action-{uuid4().hex}", **self._clocks())
        if intent is None:
            return
        reservation = None
        execution_started = False
        envelope = {"logical_action_id": intent.proposal.action_id, "request": None,
                    "result": {"status": "controller_error", "error": "Dispatch not admitted"},
                    "published": False, "received_monotonic": None}
        try:
            self._check_lease()
            reservation = self._store.reserve_dispatch(intent.proposal.before, **self._clocks())
            deadline = supervisor.validate_dispatch(intent, **self._clocks())
            self._check_lease()
            self._publish()
            execution_started = True
            envelope = self.controller.execute_run(self._lease, action=intent.proposal.action,
                expected_session=intent.proposal.before.session, expected_revision=intent.proposal.before.revision,
                logical_action_id=intent.proposal.action_id, deadline_monotonic=deadline,
                timeout=min(self.controller.timeout, 15, intent.proposal.wait_seconds))
        except (ControlError, ContractError, OSError) as exc:
            # An exception can follow native publication or even a returned action
            # (for example, journal failure). Only pre-call failures prove nondelivery.
            envelope["published"] = execution_started
            envelope["result"] = {"status": "controller_error", "error": str(exc)}
        valid_envelope = (type(envelope) is dict and set(envelope) == {"logical_action_id", "request", "result",
            "published", "received_monotonic"} and envelope["logical_action_id"] == intent.proposal.action_id
            and type(envelope["published"]) is bool and type(envelope["result"]) is dict
            and (envelope["request"] is None or type(envelope["request"]) is dict)
            and (envelope["received_monotonic"] is None or
                 type(envelope["received_monotonic"]) in (int, float)
                 and math.isfinite(envelope["received_monotonic"])
                 and 0 <= envelope["received_monotonic"] <= self._clock()))
        if not valid_envelope:
            raw = envelope
            envelope = {"logical_action_id": intent.proposal.action_id, "request": None,
                        "result": {"status": "controller_error", "error": "Malformed or unattributable action envelope"},
                        "published": True, "received_monotonic": None}
            self.controller._record({"kind": "malformed_gameplay_receipt", "run_id": self._run_id}, {"raw": raw})
        result, request = envelope["result"], envelope["request"]
        exact = (envelope["logical_action_id"] == intent.proposal.action_id and request is not None
                 and type(request.get("id")) is str and request.get("kind") == "action" and request.get("action") == intent.proposal.action
                 and request.get("session") == intent.proposal.before.session
                 and request.get("revision") == intent.proposal.before.revision
                 and result.get("id") == request.get("id"))
        disposition = "not_dispatched" if not envelope["published"] else "unknown"
        after = None
        if exact and envelope["published"] and envelope["received_monotonic"] is not None:
            if result.get("status") == "rejected":
                disposition = "rejected"
            if result.get("status") == "ready":
                try:
                    after = self._store.ingest(result, received_monotonic=envelope["received_monotonic"],
                                               reservation=reservation, **self._clocks())
                    reservation = None
                    if after.session == intent.proposal.before.session:
                        disposition = "returned"
                except (EvidenceError, OSError):
                    disposition = "unknown"
        if reservation is not None and disposition in ("not_dispatched", "rejected"):
            self._store.release(reservation)
        reason = str(result.get("error") or result.get("status") or "Unattributable native result")[:1024]
        # Retain raw envelopes even when menu/activity/error evidence is ineligible.
        try:
            self.controller._record({"kind": "gameplay_receipt", "run_id": self._run_id}, envelope)
        except OSError as exc:
            reason = f"Receipt persistence failed: {exc}"[:1024]
            if envelope["published"]:
                disposition = "unknown"
            self.pause(reason)
        self._last_receipt = {"logical_action_id": intent.proposal.action_id,
                              "native_request_id": None if request is None else request.get("id"),
                              "disposition": disposition, "reason": reason}
        self._apply_pause()
        displacement = None if after is None or after.session != intent.proposal.before.session else tuple(
            b-a for a, b in zip(self._store.position(intent.proposal.before), self._store.position(after)))
        primitive = PrimitiveResult(intent.proposal.action_id, intent.proposal.before, after,
                                    disposition, displacement, reason)
        supervisor.settle(intent, primitive, **self._clocks())

    def _tick(self):
        self._apply_pause()
        with self._admission:
            queued, self._queued = self._queued, None
            self._operation_inflight = queued is not None
        if queued is not None:
            kind, payload = queued
            if kind == "abandon":
                self._supervisor.abandon("Operator abandoned exact run", **self._clocks())
            else:
                if self._supervisor.status(**self._clocks()).execution_epoch != payload["execution_epoch"]:
                    raise ContractError("Queued continuation epoch was superseded")
                ref = self._ingest_snapshot()
                self.controller._expect(self._store.observation(ref), payload["expected_session"], payload["expected_revision"])
                epoch = self._supervisor.status(**self._clocks()).execution_epoch + 1
                self._lease = self.controller.acquire_run(self._supervisor.task.task_id,
                    epoch, self._run_id, expected_session=ref.session, expected_revision=ref.revision)
                self._inbox = _ExternalInbox(self._clock, self._wall)
                self._supervisor.continue_task(**self._clocks())
        state = self._supervisor.status(**self._clocks()).state
        if state in ("planning", "admitted"):
            self._check_lease()
        if state == "planning":
            result = self._supervisor.planning_result()
            if result.status == "completed":
                observed = self.controller.execute("observe")
                if observed.get("status") != "ready":
                    raise ControlError("Fresh planning revalidation Observe failed")
                self._check_lease()
                ref = self._ingest_snapshot()
                self._supervisor.revalidate_planning(ref, **self._clocks())
            elif result.status != "pending":
                self._supervisor.poll(**self._clocks())
        elif state == "admitted":
            self._dispatch()
        self._publish()
        state = self._snapshot["run"]["state"]
        if state not in ("planning", "admitted", "executing", "verifying") and self._lease is not None:
            self._release()
            self._publish()
        return state

    def _work(self):
        try:
            while not self._closed.is_set():
                try:
                    state = self._tick()
                except (ContractError, ControlError, OSError) as exc:
                    self._supervisor.invalidate(str(exc)[:1024], **self._clocks())
                    self._release()
                    self._publish()
                    state = self._snapshot["run"]["state"]
                with self._admission:
                    self._operation_inflight = False
                if state == "abandoned":
                    break
                interval = 0.1 if state == "planning" else 0.02 if state in ("admitted", "executing", "verifying") else 1.0
                self._wake.wait(interval)
                self._wake.clear()
        finally:
            if self._closed.is_set():
                self._supervisor.pause("Runtime shutdown", **self._clocks())
                self._supervisor.planner.close()
                self._release()
                self._publish()
                self._store.close()
            elif self._snapshot["run"]["state"] == "abandoned":
                self._store.close()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self.pause("Runtime shutdown")
        self._closed.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(0.2)
        if self._supervisor is not None:
            self._supervisor.planner.close()
