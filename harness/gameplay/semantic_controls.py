"""Passive bounded controls over retained player-visible evidence.

Interpretations are fallible. Arrows and text batches return fresh sources for
player verification, never native focus credit or proof of a desired game effect.
The caller alone owns authority, dispatch, phase and mission cost accounting.
"""
from __future__ import annotations

import hashlib
import math

from .contracts import ContractError, EvidenceRef, PrimitiveResult
from . import input_contracts as input_types
from .evidence import EvidenceError, EvidenceStore
from .mission_contracts import SourceRevalidation, validate_request
from .interactions import check_visible_row_agreement, item_selection_plan

_CHARACTER = frozenset({"NEW_CHAR_POINTS", "NEW_CHAR_STATS", "NEW_CHAR_TRAITS", "NEW_CHAR_PROFESSIONS",
                        "NEW_CHAR_SKILLS", "NEW_CHAR_SCENARIOS", "NEW_CHAR_DESCRIPTION"})
_VERTICAL = _CHARACTER | {"MAIN_MENU", "INVENTORY", "INVENTORY_SELECTOR", "CRAFTING", "CONSTRUCTION",
                          "PICK_WORLD_DIALOG", "WORLDGEN_CONFIRM_DIALOG"}
_TABS = _CHARACTER | {"MODMANAGER_DIALOG"}
_COLUMNS = frozenset({"INVENTORY", "INVENTORY_SELECTOR"})
_CONFIRMATIONS = frozenset({"YESNO", "CANCEL_ACTIVITY_OR_IGNORE_QUERY"})


class _ControlBlocked(Exception):
    """Current evidence or remaining budget cannot support another proposal."""


class SemanticControlSkill:
    """One immutable request; explicit clocks and retained feedback, no executor."""
    def __init__(self, request: dict | str | bytes, *, deadline_monotonic: float):
        data = validate_request(request)
        if (data["kind"] != "skill" or data["skill_kind"] not in ("menu", "edit", "interact", "item", "activity", "inspect")
                or data["skill_kind"] == "menu" and data["perception"] is None):
            raise ContractError("Semantic controls require edit/interact or an interpreted menu request")
        if (type(deadline_monotonic) not in (int, float) or not math.isfinite(deadline_monotonic)
                or deadline_monotonic < 0):
            raise ContractError("Semantic-control deadline must be finite and nonnegative")
        self._deadline_monotonic = deadline_monotonic
        self._request = data
        self._logical_prefix = "control-" + hashlib.sha256(data["request_id"].encode()).hexdigest()
        self._basis = "registered_action" if self._normal_root() else "player_interpretation"
        self._store: EvidenceStore | None = None
        self._sources: tuple[EvidenceRef, ...] = ()
        self._start: EvidenceRef | None = None
        self._checkpoint: EvidenceRef | None = None
        self._generation: int | None = None
        self._shape: dict | None = None
        self._last_monotonic: float | None = None
        self._last_timestamp_ms: int | None = None
        self._proposals = 0
        self._pending: input_types.ControlIntent | None = None
        self._terminal: input_types.ControlOutcome | None = None
        self._revalidation: SourceRevalidation | None = None
        self._plan: tuple[tuple[str, str | dict], ...] = ()
        self._index = 0

    def _normal_root(self) -> bool:
        data = self._request
        return data["skill_kind"] in ("interact", "inspect") or (
            data["skill_kind"] in ("item", "activity") and data["goal"]["step"] == "start")

    def _root_action(self) -> str:
        data = self._request
        if (data["phase_id"] is None and data["skill_kind"] in ("inspect", "item", "activity")
                and data["limits"]["primitives"] < 2):
            raise _ControlBlocked("A prompt-opening root needs at least two primitives for opening and return. "
                "Allocate for the whole phase, including all children (normally up to32), not only the opening key. "
                "No input was dispatched; submit a new request with a sufficient finite limit. "
                "The limit is a ceiling, not an upfront charge")
        if data["skill_kind"] == "interact": return data["goal"]["action"]
        if data["skill_kind"] == "item":
            if data["goal"]["purpose"] == "consume" and data["goal"]["quantity"] != 1:
                raise _ControlBlocked("Consume supports one selected native unit; larger quantities require an explicit revised goal")
            return {"pickup": "pickup", "consume": "eat", "drop": "drop", "store": "insert"}[data["goal"]["purpose"]]
        if data["skill_kind"] == "activity":
            if data["goal"]["step"] != "start":
                raise _ControlBlocked("Activity poll/recovery is owned by the registered runtime phase")
            return {"wait": "wait", "rest": "sleep", "craft": "craft"}[data["goal"]["operation"]]
        return {"inventory": "inventory", "consume": "eat", "needs": "player_data", "look": "look",
                "messages": "messages", "map": "map", "character_identity": "player_data"}[data["goal"]["purpose"]]

    def _bind(self, store: EvidenceStore) -> None:
        if not isinstance(store, EvidenceStore):
            raise ContractError("Semantic controls require the retained EvidenceStore")
        if self._store is not None and store is not self._store:
            raise EvidenceError("Semantic controls cannot borrow another store or restored authority")
        self._store = store

    def _clocks(self, now_monotonic: float, now_timestamp_ms: int) -> None:
        if (type(now_monotonic) not in (int, float) or not math.isfinite(now_monotonic)
                or now_monotonic < 0 or type(now_timestamp_ms) is not int or now_timestamp_ms < 0
                or self._last_monotonic is not None and now_monotonic < self._last_monotonic
                or self._last_timestamp_ms is not None and now_timestamp_ms < self._last_timestamp_ms):
            raise EvidenceError("Invalid or regressing semantic-control clock")
        self._last_monotonic, self._last_timestamp_ms = now_monotonic, now_timestamp_ms

    def _finish(self, reason: str, *, unknown: bool = False, inspected: bool = False,
                blocked: bool = False, verification_required: bool = False) -> input_types.ControlOutcome:
        disposition = ("unknown" if unknown else "completed" if inspected else "blocked" if blocked
                       else "partial" if self._proposals or verification_required else "blocked")
        self._terminal = input_types.ControlOutcome(disposition, reason, self._proposals, self._sources,
                                        self._pending.logical_id if self._pending else None,
                                        verification_required, self._basis, self._revalidation)
        return self._terminal

    def _informing_sources(self, store: EvidenceStore) -> tuple[EvidenceRef, ...]:
        references = {ref.observation_id: ref for ref in store.historical_references}
        try:
            return tuple(references[identity] for identity in self._request["sources"])
        except KeyError as exc:
            raise EvidenceError("Semantic-control informing source is unavailable") from exc

    def _scan_sources(self, store: EvidenceStore) -> None:
        for source in self._sources:
            store.observation(source)

    def _informing_boundary(self, reference: EvidenceRef, state: dict) -> None:
        request = self._request
        if ((reference.session, reference.revision, state["boundary"]["id"]) !=
                (request["expected_session"], request["expected_revision"], request["expected_boundary_id"])):
            raise EvidenceError("Semantic-control informing session, revision or boundary changed")

    @staticmethod
    def _ready(state: dict) -> None:
        if state["status"] != "ready" or state["error"] or state["paused"] or not state["frame_ok"]:
            raise EvidenceError("Semantic controls require ready, error-free, unpaused valid frame evidence")

    @staticmethod
    def _control_shape(state: dict) -> dict:
        ui = state["ui"]
        return {**{key: state[key] for key in ("session", "category", "actions", "scene", "paused",
                                               "pause_origin", "takeover_generation", "in_game", "frame_geometry")},
                "boundary": {key: value for key, value in state["boundary"].items() if key != "id"},
                "ui": None if ui is None else {key: value for key, value in ui.items() if key != "selected"}}

    def _image_source(self, source: EvidenceRef) -> None:
        view = self._request["perception"]
        if view is not None and view["source_id"] != source.observation_id:
            raise EvidenceError("Player interpretation must name the exact original source being used or refreshed")

    def revalidate(self, receipt: SourceRevalidation, store: EvidenceStore, *, now_monotonic: float,
                   now_timestamp_ms: int) -> None:
        """Accept precisely one attributed equivalent refresh before any proposal."""
        if self._revalidation is not None or self._start is not None or self._terminal is not None:
            raise ContractError("Semantic-control revalidation is allowed once before initialization")
        if type(receipt) is not SourceRevalidation:
            raise ContractError("Semantic controls require typed SourceRevalidation")
        receipt.__post_init__()
        if (receipt.original.mission_id, receipt.original.epoch) != (self._request["mission_id"], self._request["epoch"]):
            raise ContractError("Semantic-control refresh must match its exact mission and epoch")
        if not self._normal_root() and receipt.rule != "exact_png_bytes":
            raise EvidenceError("Player image interpretations require exact_png_bytes refresh")
        self._clocks(now_monotonic, now_timestamp_ms)
        self._bind(store)
        sources = self._informing_sources(store)
        original = next((ref for ref in sources if ref.observation_id == receipt.original.source_id), None)
        if original is None:
            raise EvidenceError("Refresh original must be an immutable informing source")
        self._image_source(original)
        current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        if (current.observation_id != receipt.current.source_id
                or store.authority_generation() != receipt.current.store_generation):
            raise EvidenceError("Refresh requires the exact current source and store generation")
        for source in (*sources, current):
            state = store.observation(source)
            if source in (original, current):
                self._informing_boundary(source, state)
                self._ready(state)
                if state["takeover_generation"] != receipt.original.takeover_generation:
                    raise EvidenceError("Refresh native takeover binding differs")
                if self._normal_root() and state["boundary"]["kind"] != "normal_play":
                    raise EvidenceError("Interact refresh requires normal play")
        if not store.equivalent(original, current, rule=receipt.rule):
            raise EvidenceError("Refresh is not equivalent to its original informing source")
        self._sources = tuple(dict.fromkeys((*sources, current)))
        self._checkpoint, self._generation = current, receipt.current.store_generation
        self._revalidation = receipt

    @staticmethod
    def _directions(category: str, control: str) -> tuple[str, str]:
        if control == "vertical":
            if category == "UILIST": return "UILIST.UP", "UILIST.DOWN"
            if category in _VERTICAL: return "UP", "DOWN"
        elif control == "horizontal" and category == "MAIN_MENU": return "LEFT", "RIGHT"
        elif control == "tabs" and category in _TABS: return "PREV_TAB", "NEXT_TAB"
        elif control == "columns" and category in _COLUMNS: return "PREV_COLUMN", "NEXT_COLUMN"
        raise _ControlBlocked("Unsupported menu category/control mapping")

    @staticmethod
    def _native_agreement(view: dict, state: dict) -> None:
        # Native UILIST and inventory rows attest the same vertical control.
        # Other axes describe another region and cannot acquire that assertion.
        check_visible_row_agreement(view, state)

    def _native_focus_transition(self, pending: input_types.ControlIntent, before: dict, after: dict) -> None:
        view = self._request["perception"]
        if (view is None or view["kind"] not in ("menu", "item_selection") or view["control"] != "vertical"
                or before["ui"] is None or before["ui"]["purpose"] not in ("uilist", "inventory")
                or self._control_shape(after) != self._shape):
            return
        up, down = self._directions(before["category"], "vertical")
        if pending.action not in (up, down):
            return
        rows = before["ui"]["rows"]
        selected = next((n for n, row in enumerate(rows) if row["id"] == before["ui"]["selected"]
                         and row["enabled"]), None)
        if selected is None:
            raise EvidenceError("Native vertical focus lost its known enabled before selection")
        direction = 1 if pending.action == down else -1
        next_enabled = next((rows[n]["id"] for n in range(selected + direction,
                             len(rows) if direction > 0 else -1, direction) if rows[n]["enabled"]), None)
        if next_enabled is None or after["ui"]["selected"] != next_enabled:
            raise EvidenceError("Native vertical focus contradicts the exact next represented enabled row")
        # Agreement is only a contradiction check; it grants no verified-focus
        # credit and never authorizes confirmation after this prediction batch.

    def _menu_plan(self, state: dict) -> tuple[tuple[str, str], ...]:
        view, goal = self._request["perception"], self._request["goal"]
        if state["boundary"]["kind"] != "menu":
            raise _ControlBlocked("Interpreted controls require a menu boundary")
        if view["kind"] == "dismissal":
            # The pinned input_context registers the language toggle globally.
            # A no-choice any-key popup needs a real key, not an absent QUIT.
            # Do not infer acknowledgement from arbitrary extra controls/rows.
            if (state["category"] == "POPUP_WAIT" and state["ui"] is None
                    and set(state["actions"]) - {"toggle_language_to_en"} == {"ANY_INPUT", "COORDINATE"}):
                return (("key", "SPACE"),)
            action = {"STRING_INPUT": "TEXT.QUIT", "UILIST": "UILIST.QUIT",
                      "WORLDGEN_CONFIRM_DIALOG": "WORLDGEN_CONFIRM.QUIT"}.get(state["category"], "QUIT")
            return (("action", action),)
        if view["kind"] in ("direction", "confirmation"):
            if view["kind"] == "direction":
                categories = {"DEFAULTMODE"}
                action = {"North": "UP", "South": "DOWN", "East": "RIGHT", "West": "LEFT", "Here": "pause"}[goal["label"]]
            else:
                # The native exact-owner distraction query preserves its own
                # category and YES/NO bindings; it is not an injected interrupt.
                categories = _CONFIRMATIONS
                action = {"Yes": "YES", "No": "NO"}[goal["label"]]
            if state["category"] not in categories:
                raise _ControlBlocked("Prompt category does not match the interpreted control")
            return (("action", action),)
        up, down = self._directions(state["category"], view["control"])
        if view["control"] != "vertical" and goal["outcome"] != "focused":
            raise _ControlBlocked("Horizontal/tab/column interpretations support focused outcomes only")
        rows, selected = view["rows"], view["selected"]
        targets = [i for i, row in enumerate(rows) if row["label"] == goal["label"] and row["enabled"]]
        if selected is None or not rows[selected]["enabled"] or len(targets) != 1:
            raise _ControlBlocked("Exact distinct represented enabled target and known enabled selection are required")
        self._native_agreement(view, state)
        target = targets[0]
        if goal["outcome"] == "inspected": return ()
        if target == selected:
            # CONFIRM on the world's Finish row opens the same question as
            # FINALIZE, but cannot establish the registered lifecycle stage.
            # Keep this a correctable zero-input outcome, like character finish.
            if (state["category"] == "WORLDGEN_CONFIRM_DIALOG" and goal["label"] == "Finish"
                    and goal["outcome"] == "activated"):
                raise _ControlBlocked("World Finish requires an explicit lifecycle create stage commit "
                    "with the current source and existing phase_id; no input was dispatched")
            return (("action", "CONFIRM"),) if goal["outcome"] == "activated" else ()
        direction = 1 if target > selected else -1
        # In CDDA's description screen NEXT_TAB starts character completion;
        # it is not a focus arrow. Only an explicit lifecycle stage may commit
        # that transition, regardless of the player's interpreted tab list.
        if state["category"] == "NEW_CHAR_DESCRIPTION" and view["control"] == "tabs" and direction > 0:
            raise _ControlBlocked("Character finish requires an explicit lifecycle stage commit")
        steps = sum(rows[n]["enabled"] for n in range(selected + direction, target + direction, direction))
        # Every arrow is observed, but subsequent interpretation is unavailable.
        # Bounded prediction never appends confirmation or verifies focus.
        return tuple(("action", down if direction > 0 else up) for _ in range(min(steps, 8)))

    def _edit_plan(self, state: dict) -> tuple[tuple[str, str], ...]:
        view, goal = self._request["perception"], self._request["goal"]
        if state["boundary"]["kind"] != "menu" or state["category"] != "STRING_INPUT":
            raise _ControlBlocked("Edit requires the STRING_INPUT menu category")
        if not view["focused"] or not view["whole_value"] or view["purpose"] != goal["purpose"]:
            raise _ControlBlocked("Edit requires a focused whole-value interpretation of the exact purpose")
        if goal["commit"]:
            if view["visible_text"] != goal["text"]:
                raise _ControlBlocked("Commit requires fresh interpreted visible_text exactly equal to the target")
            return (("action", "TEXT.CONFIRM"),)
        return (("action", "TEXT.CLEAR"), *(('key', char) for char in goal["text"]))

    def _initialize(self, current: EvidenceRef, state: dict, store: EvidenceStore) -> None:
        self._informing_boundary(current, state)
        sources = self._informing_sources(store)
        if self._revalidation is not None:
            if current != self._checkpoint or store.authority_generation() != self._generation:
                raise EvidenceError("Refresh cannot adopt an intervening source or store generation")
            start = next(ref for ref in sources if ref.observation_id == self._revalidation.original.source_id)
        elif current not in sources:
            raise EvidenceError("Semantic controls require their exact informing current source or explicit refresh")
        else:
            start = current
        self._image_source(start)
        self._sources = tuple(dict.fromkeys((*sources, current)))
        self._scan_sources(store)
        self._ready(state)
        kind = self._request["skill_kind"]
        if kind == "menu":
            plan = self._menu_plan(state)
        elif kind == "edit":
            plan = self._edit_plan(state)
        elif kind == "item" and self._request["goal"]["step"] != "start":
            plan = item_selection_plan(self._request["goal"], self._request["perception"], state)
        else:
            if state["boundary"]["kind"] != "normal_play" or state["scene"] is None:
                raise _ControlBlocked("Interact requires a fresh normal-play scene")
            plan = (("action", self._root_action()),)
        if any(kind == "action" and action not in state["actions"] for kind, action in plan):
            raise _ControlBlocked("Required control action is not registered in current evidence")
        self._plan = plan
        self._shape = self._control_shape(state)
        self._start, self._checkpoint, self._generation = start, current, store.authority_generation()

    def _budget(self, current: EvidenceRef, now_monotonic: float, *, completing: bool = False) -> None:
        limits = self._request["limits"]
        remaining_wall = self._deadline_monotonic - now_monotonic
        # Menu turns stay null; runtime owns mission costs across menu phases.
        remaining_game = None
        if self._start.turn is not None and current.turn is not None:
            elapsed = current.turn - self._start.turn
            if elapsed < 0: raise EvidenceError("Observed semantic-control game time regressed")
            remaining_game = limits["game_seconds"] - elapsed
        if remaining_wall < 0 or remaining_game is not None and remaining_game < 0:
            raise _ControlBlocked("Original control wall/game budget exceeded")
        if not completing and (self._proposals >= limits["primitives"] or remaining_wall <= 0
                               or remaining_game is not None and remaining_game <= 0):
            raise _ControlBlocked("Original control proposal/wall/game budget exhausted")

    def propose(self, store: EvidenceStore, *, now_monotonic: float,
                now_timestamp_ms: int) -> input_types.ControlIntent | input_types.ControlOutcome:
        if self._terminal is not None: return self._terminal
        try:
            self._clocks(now_monotonic, now_timestamp_ms)
            self._bind(store)
            if not self._sources: self._sources = self._informing_sources(store)
            current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            state = store.observation(current)
            if self._start is None: self._initialize(current, state, store)
            self._scan_sources(store)
            if current != self._checkpoint or store.authority_generation() != self._generation:
                raise EvidenceError("Semantic controls require their exact attributed checkpoint and generation")
            self._ready(state)
            if self._control_shape(state) != self._shape:
                raise _ControlBlocked("Control scope/category/action set changed")
            if self._pending is not None:
                self._budget(current, now_monotonic, completing=True)
                return self._pending
            if not self._plan:
                self._budget(current, now_monotonic, completing=True)
                inspected = self._request["skill_kind"] == "menu" and self._request["goal"]["outcome"] == "inspected"
                return self._finish("Visible control inspected by fallible player interpretation" if inspected else
                                    "Initial interpreted focus requires fresh player verification; no native focus credit",
                                    inspected=inspected, verification_required=not inspected)
            self._budget(current, now_monotonic)
            kind, action = self._plan[self._index]
            if kind == "action" and action not in state["actions"]:
                raise _ControlBlocked("Required control action is not registered")
        except (EvidenceError, _ControlBlocked) as exc:
            return self._finish(str(exc), unknown=self._pending is not None,
                                verification_required=self._proposals > 0)
        self._proposals += 1
        self._pending = input_types.ControlIntent(f"{self._logical_prefix}-{self._proposals}", kind, action, current,
                                      state["boundary"]["id"], self._revalidation if self._proposals == 1 else None)
        return self._pending

    def accept(self, result: PrimitiveResult, store: EvidenceStore, *, now_monotonic: float,
               now_timestamp_ms: int) -> input_types.ControlOutcome | None:
        if self._terminal is not None: return self._terminal
        pending = self._pending
        if pending is None:
            raise ContractError("Semantic-control feedback requires a pending proposal")
        if type(result) is not PrimitiveResult:
            return self._finish("Invalid semantic-control feedback: typed PrimitiveResult required", unknown=True,
                                verification_required=True)
        diagnostic = result.reason if isinstance(result.reason, str) else "Malformed result reason"
        try:
            self._clocks(now_monotonic, now_timestamp_ms)
            self._bind(store)
            # Preserve actual retained after diagnostics even for a corrupt or
            # miscorrelated receipt; retaining it does not attribute delivery.
            if type(result.after) is EvidenceRef and result.after in store.historical_references:
                self._sources = tuple(dict.fromkeys((*self._sources, result.after)))
            result.to_dict()
            after = store.observation(result.after) if result.after is not None else None
            if (result.action_id, result.before) != (pending.logical_id, pending.before):
                raise EvidenceError("Feedback does not match the pending logical ID and before reference")
            before = store.observation(result.before)
            self._scan_sources(store)
            current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            checkpoint = result.after if result.after is not None else result.before
            expected_generation = self._generation + (checkpoint != self._checkpoint)
            if current != checkpoint or store.authority_generation() != expected_generation:
                raise EvidenceError("Intervening observation or invalidation prevents control attribution")
            if result.transport_disposition in ("unknown", "dispatched"):
                return self._finish(diagnostic, unknown=True, verification_required=True)
            if result.transport_disposition in ("not_dispatched", "rejected"):
                self._pending = None
                # Earlier arrows/text may already have changed the UI. A known
                # refusal of this proposal does not erase those actual effects.
                progressed = self._index > 0
                return self._finish(diagnostic, blocked=not progressed, verification_required=progressed)
            if (result.after is None or result.after.session != pending.before.session
                    or result.after.revision <= pending.before.revision):
                raise EvidenceError("Returned control requires advanced same-session actual after evidence")
            self._ready(after)
            if (after["takeover_generation"] != before["takeover_generation"]
                    or after["pause_origin"] != before["pause_origin"]
                    or after["boundary"]["control_generation"] != before["boundary"]["control_generation"]
                    or after["boundary"]["kind"] not in ("normal_play", "menu", "activity_poll")):
                raise EvidenceError("Returned control crossed Pause/takeover/control or an unclassified boundary")
            if self._start.turn is not None and current.turn is not None and current.turn < self._start.turn:
                raise EvidenceError("Observed semantic-control game time regressed")
            self._native_focus_transition(pending, before, after)
            self._pending = None
            self._checkpoint, self._generation = current, expected_generation
            self._index += 1
            one_effect = (self._normal_root() or pending.action in
                          ("CONFIRM", "TEXT.CONFIRM", "MARK_WITH_COUNT") or self._request["perception"]["kind"] in
                          ("direction", "confirmation", "dismissal"))
            self._budget(current, now_monotonic, completing=True)
            if one_effect:
                return self._finish("Input returned; player verification of the semantic effect is required",
                                    verification_required=True)
            if self._control_shape(after) != self._shape:
                raise _ControlBlocked("Control scope/category/action set changed during focus/edit")
            if pending.action != "TEXT.CLEAR" and pending.before.frame_sha256 == result.after.frame_sha256:
                raise _ControlBlocked("Byte-identical PNG shows no progress; fresh player verification is required")
            if self._index == len(self._plan):
                return self._finish("Unverified focus/text batch returned; fresh player interpretation is required",
                                    verification_required=True)
            self._budget(current, now_monotonic)
        except EvidenceError as exc:
            return self._finish(f"{diagnostic}; {exc}", unknown=True, verification_required=True)
        except ContractError as exc:
            return self._finish(f"{diagnostic}; Invalid semantic-control feedback: {exc}", unknown=True,
                                verification_required=True)
        except _ControlBlocked as exc:
            return self._finish(f"{diagnostic}; {exc}", verification_required=True)
        return None
