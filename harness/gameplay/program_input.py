"""Observation-conditioned ordinary proposals; transport stays with the writer.

A program is fallible learned data, not another owner or a success verifier.
There is no image decoder/perception model here: absent visible facts must yield
or be handled by the deciding player's ordinary image-informed exploration.
"""
from __future__ import annotations

import time
from typing import Callable

from .contracts import ContractError, EvidenceRef, canonical, json_object
from .input_contracts import ControlOutcome
from .native_input import validate_input
from .ordinary_input import OrdinaryInputSkill
from .policy_program import PolicyProgram, PolicyProgramError


def program_view(observation: dict) -> dict:
    """Project an already-retained visible observation, without authority metadata."""
    return json_object({"schema": "program-view/2",
        **{key: observation[key] for key in ("category", "actions", "in_game", "ui", "scene", "frame_geometry")},
        "boundary": {key: observation["boundary"][key] for key in ("kind", "input_receiver")},
        "omissions": ["No PNG pixels or pixel-derived detections in this program view; null UI/scene is unavailable, not empty.",
                      "Scene contains only supplied visible cells/creatures; no unseen map or inventory."]})


class ProgramInputSkill(OrdinaryInputSkill):
    """One pinned routine, one original budget and serialized current feedback."""

    def __init__(self, request: dict, *, deadline_monotonic: float, source: str,
                 on_step: Callable[[dict], None]):
        super().__init__(request, deadline_monotonic=deadline_monotonic)
        if self._request["skill_kind"] != "program":
            raise ContractError("Program proposals require their selected program request")
        self._source = source
        self._engine: PolicyProgram | None = None
        self._state = json_object(self._request["goal"]["state"])
        self._on_step = on_step
        self._evaluations = 0
        self._program_status = "not_started"
        self._program_reason = "Program has not evaluated a view"
        self._trace: list[dict] = []
        self._omitted_trace = 0

    def _retain(self, event: dict) -> None:
        # A bounded result projection of existing journal events, not a second
        # durable trajectory. Complete evaluation state stays in the audit log;
        # actual primitive intent/receipts stay in the existing ledger.
        event = json_object(event)
        if "state" in event and len(canonical(event["state"]).encode()) > 2048:
            event.pop("state")
            event["state_omitted"] = "Continuation exceeds per-event preview; final state and original audit retain it"
        if len(canonical({"events": [*self._trace, event]}).encode()) <= 16_384:
            self._trace.append(event)
        else:
            self._omitted_trace += 1

    def close(self) -> None:
        if self._engine is not None:
            self._engine.close()
            self._engine = None

    def _sequence_complete(self) -> bool:
        # The next decision is computed from returned evidence, not a static
        # event stream. The inherited custody/game/primitive/deadline checks run
        # before each proposal, including between scalar text events.
        return False

    def _same_shape_required(self) -> bool:
        return self._index < len(self._events)

    def summary(self) -> dict:
        return {"evaluations": self._evaluations, "status": self._program_status,
                "reason": self._program_reason, "state": json_object(self._state),
                "trace": json_object({"events": self._trace, "omitted_events": self._omitted_trace}),
                "task_success_verified": False}

    def record_feedback(self, result) -> None:
        """Expose the writer's actual receipt even if changed custody ends accept."""
        pending = self._pending
        self._retain({"kind": "delivery", "evaluation": self._evaluations,
            "logical_id": result.action_id, "input": pending.action,
            "before_source_id": result.before.observation_id,
            "after_source_id": None if result.after is None else result.after.observation_id,
            "transport_disposition": result.transport_disposition, "reason": result.reason[:1024]})

    def _choose(self, current: EvidenceRef, now_monotonic: float) -> dict | ControlOutcome:
        if self._index < len(self._events):
            return self._events[self._index]
        started = time.monotonic()
        try:
            if self._engine is None:
                # Host compilation is bounded independently; recheck the
                # original deadline afterwards, never replenish it.
                self._engine = PolicyProgram(self._source)
                self._engine.__enter__()
            elapsed = time.monotonic() - started
            remaining = self._deadline - now_monotonic - elapsed
            if remaining <= 0:
                return self._finish("Original program wall allowance exhausted during compilation", refused=True)
            view = program_view(self._store.observation(current))
            result = self._engine.step(view, self._state, timeout_seconds=min(0.05, remaining))
        except PolicyProgramError as exc:
            self._program_status, self._program_reason = "error", str(exc)[:1024]
            self.close()
            event = {"kind": "evaluation_error", "source_id": current.observation_id,
                     "evaluation": self._evaluations + 1, "reason": self._program_reason}
            self._retain(event)
            self._on_step(event)
            return self._finish("Program evaluation stopped: " + str(exc)[:900], refused=True)
        self._evaluations += 1
        self._program_status, self._program_reason = result["status"], result["reason"]
        self._state = result["state"]
        event = {"kind": "evaluation", "evaluation": self._evaluations,
                 "source_id": current.observation_id, **result,
                 "evaluation_seconds": time.monotonic() - started}
        self._retain(event)
        self._on_step(event)
        if result["status"] != "act":
            return self._finish("Program " + result["status"] + ": " + result["reason"],
                                refused=result["status"] == "yield")
        selected = result["input"]
        if selected["type"] == "click":
            selected = {**selected, "geometry": self._store.observation(current)["frame_geometry"]}
        try:
            selected = validate_input(selected, text_limit=24)
        except ContractError as exc:
            self._program_status, self._program_reason = "error", str(exc)[:1024]
            return self._finish("Program input stopped: " + str(exc)[:900], refused=True)
        self._events = (tuple({"type": "text", "text": scalar} for scalar in selected["text"])
                        if selected["type"] == "text" else (selected,))
        self._index = 0
        self._shape = self._batch_shape(self._store.observation(current))
        return self._events[0]
