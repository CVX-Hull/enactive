"""Bounded native rendered-row policy; the caller owns dispatch and authority.

This module proposes one registered UILIST action and checks its exact retained
feedback. CONFIRM delivery always leaves the player's semantic effect unverified.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Literal

from .contracts import ContractError, EvidenceRef, PrimitiveResult
from .evidence import EvidenceError, EvidenceStore
from .mission_contracts import SourceRevalidation, validate_request


@dataclass(frozen=True)
class MenuIntent:
    logical_id: str
    action: str
    before: EvidenceRef
    expected_boundary_id: str
    revalidation: SourceRevalidation | None = None
    kind: Literal["action"] = "action"


@dataclass(frozen=True)
class MenuOutcome:
    disposition: Literal["completed", "partial", "blocked", "unknown"]
    reason: str
    proposed_count: int
    verified_focus_steps: int
    evidence: tuple[EvidenceRef, ...]
    pending_logical_id: str | None
    verification_required: bool
    revalidation: SourceRevalidation | None = None


class _MenuBlocked(Exception):
    """Observed native state or remaining capability prevents another proposal."""


class MenuSkill:
    """One copied closed request, with no input, clocks, controller or storage.

    The runtime authenticates actor/lease/host generations, accounts mission game
    time from normal scenes and retains exact native-to-logical receipt mappings.
    A revalidation record is audit data and cannot restore that authority.
    """
    def __init__(self, request: dict | str | bytes, *, deadline_monotonic: float):
        data = validate_request(request)
        if data["kind"] != "skill" or data["skill_kind"] != "menu":
            raise ContractError("Menu policy requires an exact menu skill request")
        if data["perception"] is not None:
            raise ContractError("Native-row policy cannot substitute a player interpretation for native rows")
        if (type(deadline_monotonic) not in (int, float) or not math.isfinite(deadline_monotonic)
                or deadline_monotonic < 0):
            raise ContractError("Menu deadline must be finite and nonnegative")
        self._deadline_monotonic = deadline_monotonic
        self._request = data
        self._logical_prefix = "menu-" + hashlib.sha256(data["request_id"].encode()).hexdigest()
        self._store: EvidenceStore | None = None
        self._sources: tuple[EvidenceRef, ...] = ()
        self._start: EvidenceRef | None = None
        self._checkpoint: EvidenceRef | None = None
        self._generation: int | None = None
        self._shape: dict | None = None
        self._selected: str | None = None
        self._last_monotonic: float | None = None
        self._last_timestamp_ms: int | None = None
        self._proposals = self._steps = 0
        self._pending: MenuIntent | None = None
        self._terminal: MenuOutcome | None = None
        self._revalidation: SourceRevalidation | None = None

    def _bind(self, store: EvidenceStore) -> None:
        if not isinstance(store, EvidenceStore):
            raise ContractError("Menu policy requires the retained EvidenceStore")
        if self._store is not None and store is not self._store:
            raise EvidenceError("Menu policy cannot borrow another store or restored authority")
        self._store = store

    def _clocks(self, now_monotonic: float, now_timestamp_ms: int) -> None:
        if (type(now_monotonic) not in (int, float) or not math.isfinite(now_monotonic)
                or now_monotonic < 0 or type(now_timestamp_ms) is not int or now_timestamp_ms < 0
                or self._last_monotonic is not None and now_monotonic < self._last_monotonic
                or self._last_timestamp_ms is not None and now_timestamp_ms < self._last_timestamp_ms):
            raise EvidenceError("Invalid or regressing menu clock")
        self._last_monotonic, self._last_timestamp_ms = now_monotonic, now_timestamp_ms

    def _finish(self, reason: str, *, unknown: bool = False, inspected: bool = False,
                verification_required: bool = False, blocked: bool = False) -> MenuOutcome:
        disposition = ("unknown" if unknown else "completed" if inspected else "blocked" if blocked
                       else "partial" if self._steps or verification_required else "blocked")
        self._terminal = MenuOutcome(disposition, reason, self._proposals, self._steps,
                                     self._sources, self._pending.logical_id if self._pending else None,
                                     verification_required, self._revalidation)
        return self._terminal

    def _informing_sources(self, store: EvidenceStore) -> tuple[EvidenceRef, ...]:
        references = {ref.observation_id: ref for ref in store.historical_references}
        try:
            return tuple(references[identity] for identity in self._request["sources"])
        except KeyError as exc:
            raise EvidenceError("Menu informing source is unavailable") from exc

    def _scan_sources(self, store: EvidenceStore) -> None:
        for source in self._sources:
            store.observation(source)

    def _informing_boundary(self, reference: EvidenceRef, state: dict) -> None:
        request = self._request
        if ((reference.session, reference.revision, state["boundary"]["id"]) !=
                (request["expected_session"], request["expected_revision"], request["expected_boundary_id"])):
            raise EvidenceError("Menu informing boundary changed before first proposal")

    @staticmethod
    def supports_native_rows(state: dict) -> bool:
        """Representation support only; never evidence of authority or success."""
        ui = state["ui"]
        return (state["boundary"]["kind"] == "menu" and state["category"] == "UILIST"
                and ui is not None and ui["purpose"] == "uilist" and ui["coverage"] == "rendered_rows_only")

    @staticmethod
    def _native_shape(state: dict) -> dict:
        # Native focus changes only selection and the capture/boundary identity.
        return {**{key: state[key] for key in ("session", "category", "actions", "scene", "paused",
                                               "pause_origin", "takeover_generation", "in_game")},
                "boundary": {key: value for key, value in state["boundary"].items() if key != "id"},
                "ui": {key: value for key, value in state["ui"].items() if key != "selected"}}

    def _menu(self, state: dict) -> tuple[list[dict], int, int]:
        if state["status"] != "ready" or state["error"] or state["paused"] or not state["frame_ok"]:
            raise _MenuBlocked("Menu requires ready, unpaused native evidence with a valid capture")
        ui = state["ui"]
        if not self.supports_native_rows(state):
            raise _MenuBlocked("Capability requires native UILIST rendered rows; inventory/image adapters are unsupported")
        rows = ui["rows"]
        selected = next((i for i, row in enumerate(rows) if row["id"] == ui["selected"] and row["enabled"]), None)
        if selected is None:
            raise _MenuBlocked("Native selected row must be visible, known and enabled")
        targets = [i for i, row in enumerate(rows)
                   if row["text"] == self._request["goal"]["label"] and row["enabled"]]
        if len(targets) != 1:
            raise _MenuBlocked("Target requires a unique exact enabled label in represented visible rows")
        if self._shape is not None and self._native_shape(state) != self._shape:
            raise _MenuBlocked("Native menu shape/content, category or action set changed during focusing")
        return rows, selected, targets[0]

    def revalidate(self, receipt: SourceRevalidation, store: EvidenceStore, *, now_monotonic: float,
                   now_timestamp_ms: int) -> None:
        """Accept one exact equivalent source refresh before initialization."""
        if self._revalidation is not None or self._start is not None or self._terminal is not None:
            raise ContractError("Menu revalidation is allowed once before any proposal")
        if type(receipt) is not SourceRevalidation:
            raise ContractError("Menu requires typed SourceRevalidation")
        receipt.__post_init__()
        if (receipt.original.mission_id, receipt.original.epoch) != (self._request["mission_id"], self._request["epoch"]):
            raise ContractError("Menu refresh must match its exact mission and epoch")
        self._clocks(now_monotonic, now_timestamp_ms)
        self._bind(store)
        sources = self._informing_sources(store)
        original = next((ref for ref in sources if ref.observation_id == receipt.original.source_id), None)
        if original is None:
            raise EvidenceError("Menu refresh original must be an immutable informing source")
        current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        if (current.observation_id != receipt.current.source_id
                or store.authority_generation() != receipt.current.store_generation):
            raise EvidenceError("Menu refresh requires the exact current source and generation")
        for source in (*sources, current):
            state = store.observation(source)
            if source in (original, current):
                self._informing_boundary(source, state)
                if state["takeover_generation"] != receipt.original.takeover_generation:
                    raise EvidenceError("Menu refresh native takeover binding differs")
        if not store.equivalent(original, current, rule=receipt.rule):
            raise EvidenceError("Menu refresh is not equivalent to its informing native state")
        self._sources = tuple(dict.fromkeys((*sources, current)))
        self._checkpoint, self._generation = current, receipt.current.store_generation
        self._revalidation = receipt

    def _initialize(self, current: EvidenceRef, state: dict, store: EvidenceStore) -> None:
        self._informing_boundary(current, state)
        sources = self._informing_sources(store)
        if self._revalidation is not None:
            if current != self._checkpoint or store.authority_generation() != self._generation:
                raise EvidenceError("Menu refresh cannot adopt an intervening source or generation")
            start = next(ref for ref in sources if ref.observation_id == self._revalidation.original.source_id)
        elif current not in sources:
            raise EvidenceError("Menu requires its exact informing current source; refresh must be explicit")
        else:
            start = current
        self._sources = tuple(dict.fromkeys((*sources, current)))
        self._scan_sources(store)
        self._menu(state)
        self._shape = self._native_shape(state)
        self._selected = state["ui"]["selected"]
        self._start, self._checkpoint, self._generation = start, current, store.authority_generation()

    def _budget(self, current: EvidenceRef, now_monotonic: float, *, completing: bool = False) -> None:
        limits = self._request["limits"]
        remaining_wall = self._deadline_monotonic - now_monotonic
        # Menu refs deliberately have no game time. Unknown is never zero; the
        # runtime must account mission game time from its observed normal refs.
        remaining_game = None
        if self._start.turn is not None and current.turn is not None:
            elapsed = current.turn - self._start.turn
            if elapsed < 0:
                raise EvidenceError("Observed menu game time regressed")
            remaining_game = limits["game_seconds"] - elapsed
        if remaining_wall < 0 or remaining_game is not None and remaining_game < 0:
            raise _MenuBlocked("Original menu wall/game budget exceeded")
        if not completing and (self._proposals >= limits["primitives"] or remaining_wall <= 0
                               or remaining_game is not None and remaining_game <= 0):
            raise _MenuBlocked("Original menu proposal/wall/game budget exhausted")

    def propose(self, store: EvidenceStore, *, now_monotonic: float,
                now_timestamp_ms: int) -> MenuIntent | MenuOutcome:
        if self._terminal is not None:
            return self._terminal
        try:
            self._clocks(now_monotonic, now_timestamp_ms)
            self._bind(store)
            if not self._sources:
                self._sources = self._informing_sources(store)
            current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            state = store.observation(current)
            if self._start is None:
                self._initialize(current, state, store)
            self._scan_sources(store)
            if current != self._checkpoint or store.authority_generation() != self._generation:
                raise EvidenceError("Menu requires its exact attributed checkpoint and store generation")
            rows, selected, target = self._menu(state)
            if state["ui"]["selected"] != self._selected:
                raise _MenuBlocked("Menu selection changed outside verified feedback")
            if self._pending is not None:
                self._budget(current, now_monotonic, completing=True)
                return self._pending
            inspecting = self._request["goal"]["outcome"] == "inspected"
            focused = self._request["goal"]["outcome"] == "focused" and selected == target
            self._budget(current, now_monotonic, completing=inspecting or focused)
            if inspecting:
                return self._finish("Requested visible row inspected; no game effect asserted", inspected=True)
            if focused:
                return self._finish("Exact requested enabled row has native verified focus", inspected=True)
            action = "CONFIRM" if selected == target else "UILIST.DOWN" if selected < target else "UILIST.UP"
            if action not in state["actions"]:
                raise _MenuBlocked("Required native menu action is not registered in current evidence")
        except (EvidenceError, _MenuBlocked) as exc:
            return self._finish(str(exc), unknown=self._pending is not None)
        self._proposals += 1
        self._pending = MenuIntent(f"{self._logical_prefix}-{self._proposals}", action, current,
                                   state["boundary"]["id"], self._revalidation if self._proposals == 1 else None)
        return self._pending

    def accept(self, result: PrimitiveResult, store: EvidenceStore, *, now_monotonic: float,
               now_timestamp_ms: int) -> MenuOutcome | None:
        if self._terminal is not None:
            return self._terminal
        pending = self._pending
        if pending is None:
            raise ContractError("Menu feedback requires a pending proposal")
        if type(result) is not PrimitiveResult:
            raise ContractError("Menu feedback requires typed PrimitiveResult")
        try:
            result.to_dict()
        except ContractError as exc:
            return self._finish(f"Invalid menu feedback: {exc}", unknown=True)
        if (result.action_id, result.before) != (pending.logical_id, pending.before):
            return self._finish("Menu feedback does not match pending logical ID and before reference", unknown=True)
        try:
            self._clocks(now_monotonic, now_timestamp_ms)
            self._bind(store)
            before = store.observation(result.before)
            self._scan_sources(store)
            after = store.observation(result.after) if result.after is not None else None
            if result.after is not None:
                self._sources = tuple(dict.fromkeys((*self._sources, result.after)))
            current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            checkpoint = result.after if result.after is not None else result.before
            expected_generation = self._generation + (checkpoint != self._checkpoint)
            if current != checkpoint or store.authority_generation() != expected_generation:
                raise EvidenceError("Intervening observation or invalidation prevents menu attribution")
            if result.transport_disposition in ("unknown", "dispatched"):
                return self._finish(result.reason, unknown=True)
            if result.transport_disposition in ("not_dispatched", "rejected"):
                self._pending = None
                return self._finish(result.reason, blocked=True)
            if (result.after is None or result.after.session != result.before.session
                    or result.after.revision <= result.before.revision):
                raise EvidenceError("Returned menu feedback requires advanced same-session actual after evidence")
            if pending.action == "CONFIRM":
                # Category/boundary transitions are expected here. The returned
                # source is for player verification, never proof of the goal.
                if (after["status"] != "ready" or after["error"] or after["paused"] or not after["frame_ok"]
                        or after["takeover_generation"] != before["takeover_generation"]
                        or after["boundary"]["control_generation"] != before["boundary"]["control_generation"]
                        or after["boundary"]["kind"] not in ("normal_play", "menu", "activity_poll")):
                    raise EvidenceError("CONFIRM after evidence is not ready/unpaused classified play under unchanged control")
                self._pending = None
                self._checkpoint, self._generation = current, expected_generation
                try:
                    self._budget(current, now_monotonic, completing=True)
                except _MenuBlocked as exc:
                    return self._finish(f"CONFIRM returned; {exc}; player verification is required",
                                        verification_required=True)
                return self._finish("CONFIRM returned; player verification of the semantic effect is required",
                                    verification_required=True)
            rows, selected, target = self._menu(before)
            _, actual, _ = self._menu(after)
            direction = 1 if selected < target else -1
            next_enabled = next(i for i in range(selected + direction, target + direction, direction)
                                if rows[i]["enabled"])
            if (after["boundary"]["id"] == pending.expected_boundary_id or actual != next_enabled):
                return self._finish("Native focus made no progress or an unexpected/unexplained row jump", unknown=True)
            self._pending = None
            self._checkpoint, self._generation = current, expected_generation
            self._selected = after["ui"]["selected"]
            self._steps += 1
            self._budget(current, now_monotonic,
                         completing=self._request["goal"]["outcome"] == "focused" and actual == target)
        except EvidenceError as exc:
            return self._finish(str(exc), unknown=True)
        except _MenuBlocked as exc:
            return self._finish(str(exc), unknown=self._pending is not None)
        return None
