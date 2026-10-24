"""Passive physical-input proposals over owned visible evidence.

No menu catalogue, game task, input transport or semantic success inference lives
here. The mission writer owns custody, actual preflight, delivery and global costs.
"""
from __future__ import annotations

import hashlib
import math

from .contracts import ContractError, EvidenceRef, PrimitiveResult
from .evidence import EvidenceError, EvidenceStore
from .input_contracts import ControlIntent, ControlOutcome
from .mission_contracts import InputObservation, validate_request
from .native_input import validate_input


class _OrdinaryStop(Exception):
    """Another physical proposal needs a new player decision."""


class OrdinaryInputSkill:
    """One immutable ordinary request; explicit entry and attributed feedback."""

    def __init__(self, request: dict | str | bytes, *, deadline_monotonic: float):
        data = validate_request(request)
        if data["kind"] != "skill" or data["skill_kind"] not in ("direct", "program"):
            raise ContractError("Ordinary input requires a direct skill request")
        if (type(deadline_monotonic) not in (int, float) or not math.isfinite(deadline_monotonic)
                or deadline_monotonic < 0):
            raise ContractError("Ordinary input requires a finite nonnegative deadline")
        direct = (validate_input(data["goal"]["input"], text_limit=24)
                  if data["skill_kind"] == "direct" else None)
        self._events = (tuple({"type": "text", "text": scalar} for scalar in direct["text"])
                        if direct is not None and direct["type"] == "text" else (direct,) if direct else ())
        self._request, self._deadline = data, deadline_monotonic
        self._prefix = "ordinary-" + hashlib.sha256(data["request_id"].encode()).hexdigest()
        self._store: EvidenceStore | None = None
        self._observation: InputObservation | None = None
        self._sources: tuple[EvidenceRef, ...] = ()
        self._entry: EvidenceRef | None = None
        self._game_anchor: EvidenceRef | None = None
        self._checkpoint: EvidenceRef | None = None
        self._generation: int | None = None
        self._shape: dict | None = None
        self._last_clocks: tuple[float, int] | None = None
        self._pending: ControlIntent | None = None
        self._terminal: ControlOutcome | None = None
        self._proposals = 0
        self._index = 0
        self._returned = 0
        self._entry_refusal: str | None = None

    def _context(self, store: EvidenceStore, now_monotonic: float, now_timestamp_ms: int) -> None:
        if (not isinstance(store, EvidenceStore)
                or self._store is not None and self._store is not store):
            raise EvidenceError("Ordinary input cannot borrow another store or restored authority")
        if (type(now_monotonic) not in (int, float) or not math.isfinite(now_monotonic)
                or now_monotonic < 0 or type(now_timestamp_ms) is not int or now_timestamp_ms < 0
                or self._last_clocks is not None and
                (now_monotonic < self._last_clocks[0] or now_timestamp_ms < self._last_clocks[1])):
            raise EvidenceError("Invalid or regressing ordinary-input clocks")
        self._store, self._last_clocks = store, (now_monotonic, now_timestamp_ms)

    @staticmethod
    def _ready(state: dict) -> bool:
        return (state["status"] == "ready" and not state["error"] and not state["paused"]
                and state["pause_origin"] == "none"
                and state["frame_ok"] and state["boundary"]["kind"] in ("normal_play", "menu")
                and state["boundary"]["input_receiver"])

    @staticmethod
    def _batch_shape(state: dict) -> dict:
        # Optional text batching stops on structural change. Single events do
        # not require equal pixels, geometry, labels or registered actions.
        return {**{key: state[key] for key in ("session", "category", "actions", "paused", "pause_origin",
                                              "takeover_generation", "frame_geometry")},
                "boundary": {key: value for key, value in state["boundary"].items() if key != "id"}}

    def observe(self, receipt: InputObservation, store: EvidenceStore, *, now_monotonic: float,
                now_timestamp_ms: int) -> None:
        if self._observation is not None or self._terminal is not None:
            raise ContractError("Ordinary entry is recorded once before any proposal")
        if type(receipt) is not InputObservation:
            raise ContractError("Ordinary entry requires typed InputObservation")
        receipt.__post_init__()
        self._context(store, now_monotonic, now_timestamp_ms)
        if (receipt.original.mission_id, receipt.original.epoch) != (self._request["mission_id"], self._request["epoch"]):
            raise ContractError("Ordinary entry differs from its mission/epoch")
        references = {ref.observation_id: ref for ref in store.historical_references}
        try:
            sources = tuple(references[identity] for identity in self._request["sources"])
            original, current = references[receipt.original.source_id], references[receipt.current.source_id]
        except KeyError as exc:
            raise EvidenceError("Ordinary input source is not retained") from exc
        if original not in sources:
            raise EvidenceError("Ordinary entry original must inform the immutable request")
        states = {ref.observation_id: store.observation(ref) for ref in (*sources, current)}
        before, actual = states[original.observation_id], states[current.observation_id]
        if ((original.session, original.revision, before["boundary"]["id"]) !=
                (self._request["expected_session"], self._request["expected_revision"],
                 self._request["expected_boundary_id"])):
            raise EvidenceError("Ordinary informing session/revision/boundary differs from its request")
        if (current != store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
                or store.authority_generation() != receipt.current.store_generation):
            raise EvidenceError("Ordinary entry must name the actual current source/generation")
        if (original.session != current.session or before["paused"] or not self._ready(actual)
                or any(before[key] != actual[key] for key in ("pause_origin", "takeover_generation"))
                or before["boundary"]["control_generation"] != actual["boundary"]["control_generation"]
                or actual["takeover_generation"] != receipt.current.takeover_generation):
            raise EvidenceError("Ordinary entry crossed custody or lacks an owned live receiver")
        direct = self._request["goal"].get("input")
        if direct is not None and direct["type"] == "click" and (direct["geometry"] != before["frame_geometry"]
                                           or direct["geometry"] != actual["frame_geometry"]):
            self._entry_refusal = "Original click mapping changed; choose a new coordinate from current evidence"
        self._observation = receipt
        self._sources = tuple(dict.fromkeys((*sources, current)))
        self._entry = self._checkpoint = current
        self._game_anchor = original
        self._generation = receipt.current.store_generation
        self._shape = self._batch_shape(actual)

    def _finish(self, reason: str, *, unknown: bool = False, refused: bool = False) -> ControlOutcome:
        self._terminal = ControlOutcome("unknown" if unknown else "blocked" if refused and not self._returned else "partial",
            reason, self._proposals, self._sources, self._pending.logical_id if unknown and self._pending else None,
            self._returned > 0 or unknown, "ordinary_input", input_observation=self._observation)
        return self._terminal

    def _budget(self, current: EvidenceRef, now_monotonic: float) -> None:
        if now_monotonic >= self._deadline or self._proposals >= self._request["limits"]["primitives"]:
            raise _OrdinaryStop("Original ordinary input/wall limit exhausted")
        if self._game_anchor.turn is not None and current.turn is not None:
            elapsed = current.turn - self._game_anchor.turn
            if elapsed < 0:
                raise EvidenceError("Observed ordinary game time regressed")
            if elapsed >= self._request["limits"]["game_seconds"]:
                raise _OrdinaryStop("Original ordinary game limit exhausted")

    def propose(self, store: EvidenceStore, *, now_monotonic: float,
                now_timestamp_ms: int) -> ControlIntent | ControlOutcome:
        if self._terminal is not None:
            return self._terminal
        self._context(store, now_monotonic, now_timestamp_ms)
        if self._observation is None:
            raise ContractError("Ordinary input requires its explicit entry observation")
        if self._pending is not None:
            return self._pending
        try:
            if self._entry_refusal:
                raise _OrdinaryStop(self._entry_refusal)
            current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            if current != self._checkpoint or store.authority_generation() != self._generation:
                raise EvidenceError("Ordinary input lost its exact attributed checkpoint/generation")
            if not self._ready(store.observation(current)):
                raise _OrdinaryStop("A new player decision needs an owned live ordinary receiver")
            self._budget(current, now_monotonic)
        except _OrdinaryStop as exc:
            return self._finish(str(exc), refused=True)
        chosen = self._choose(current, now_monotonic)
        if isinstance(chosen, ControlOutcome):
            return chosen
        self._proposals += 1
        self._pending = ControlIntent(f"{self._prefix}-{self._proposals}", "direct", chosen,
            current, store.observation(current)["boundary"]["id"],
            input_observation=self._observation if self._proposals == 1 else None)
        return self._pending

    def _choose(self, current: EvidenceRef, now_monotonic: float) -> dict | ControlOutcome:
        return self._events[self._index]

    def _sequence_complete(self) -> bool:
        return self._index == len(self._events)

    def _same_shape_required(self) -> bool:
        return True

    def accept(self, result: PrimitiveResult, store: EvidenceStore, *, now_monotonic: float,
               now_timestamp_ms: int) -> ControlOutcome | None:
        if self._terminal is not None:
            return self._terminal
        if self._pending is None or type(result) is not PrimitiveResult:
            raise ContractError("Ordinary feedback requires a pending typed result")
        result.__post_init__()
        pending = self._pending
        if (result.action_id, result.before) != (pending.logical_id, pending.before):
            raise ContractError("Ordinary feedback differs from the pending logical ID/before source")
        self._context(store, now_monotonic, now_timestamp_ms)
        if result.after is not None:
            store.observation(result.after)
            self._sources = tuple(dict.fromkeys((*self._sources, result.after)))
        if result.transport_disposition in ("unknown", "dispatched"):
            return self._finish(result.reason, unknown=True)
        if result.transport_disposition in ("rejected", "not_dispatched"):
            self._pending = None
            return self._finish(result.reason, refused=True)
        if result.after.revision <= pending.before.revision:
            raise ContractError("Returned ordinary input needs an advanced actual terminal source")
        self._pending = None
        # The writer has authenticated delivery separately from semantic effect.
        # Novel, superseded or old terminal evidence cannot un-deliver this key.
        self._index += 1
        self._returned += 1
        after = store.observation(result.after)
        if self._sequence_complete():
            return self._finish("Physical input returned; player must interpret the effect")
        current, fresh = store.inspect_current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        if (not fresh or current != result.after or store.authority_generation() != self._generation + 1
                or not self._ready(after) or self._same_shape_required() and (
                    self._batch_shape(after) != self._shape
                    or pending.before.frame_sha256 == result.after.frame_sha256)):
            return self._finish("Known scalar returned; text batch stopped for fresh player interpretation")
        self._checkpoint, self._generation = current, store.authority_generation()
        try:
            self._budget(current, now_monotonic)
        except _OrdinaryStop as exc:
            return self._finish(str(exc))
        return None
