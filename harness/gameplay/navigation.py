"""Bounded candidate steering over retained visible cells; never a dispatcher.

The runtime owns admission, original operation deadlines, capacity and the durable
logical-to-native mapping. One serialized caller uses one map/store per scoped
request. Historical terrain suggests a route; movement.guard checks each next step.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import math
from typing import Literal

from harness.movement import (
    DIRECTIONS, MovementBlocked, current_guard, expected_position, guard,
    observed_step, visible_destination,
)
from .contracts import ContractError, EvidenceRef, PrimitiveResult, Vector
from .evidence import CapacityError, EvidenceError, EvidenceStore
from .mission_contracts import VERSION, SourceRevalidation, validate_request


@dataclass(frozen=True)
class NavigationIntent:
    """One logical proposal, with no controller capability or delivery claim."""
    logical_id: str
    action: str
    before: EvidenceRef
    expected_boundary_id: str
    target_next: Vector
    revalidation: SourceRevalidation | None = None
    kind: Literal["action"] = "action"


@dataclass(frozen=True)
class NavigationOutcome:
    """Terminal result; position is the last verified route checkpoint."""
    disposition: Literal["completed", "partial", "blocked", "unknown"]
    reason: str
    verified_steps: int
    proposed_count: int
    position: Vector | None
    evidence: tuple[EvidenceRef, ...]
    pending_logical_id: str | None
    revalidation: SourceRevalidation | None = None


@dataclass(frozen=True)
class NavigationPath:
    disposition: Literal["candidate", "blocked", "unknown"]
    path: tuple[Vector, ...]
    sources: tuple[EvidenceRef, ...]
    reason: str


@dataclass(frozen=True)
class _Cell:
    traversable: bool
    source: EvidenceRef


def _position(value: Vector) -> Vector:
    # Reuse movement's exact coordinate and bool rejection without moving a tile.
    expected_position(value, 1, 0)
    return tuple(value)


class ObservedMap:
    """Lossy candidate cache of at most 512 coordinates in one supplied scope.

    EvidenceRef carries a native session, not mission/coordinate-epoch metadata.
    The owner must create a new map on reload; requests match this exact scope.
    Standing positions anchor searches but never establish traversable terrain.
    Eviction forgets routing candidates, never their retained source evidence.
    """
    def __init__(self, mission_id: str, session: str, coordinate_epoch: int, *, max_nodes: int = 512):
        scope = {"mission_id": mission_id, "session": session, "coordinate_epoch": coordinate_epoch}
        validate_request({"schema": VERSION, "kind": "context", "handoff": None, "mission_id": mission_id,
                          "scope": scope, "query": "Validate navigation scope", "max_bytes": 512})
        if type(max_nodes) is not int or not 1 <= max_nodes <= 512:
            raise ContractError("Observed-map node limit must be between one and 512")
        self._scope = (mission_id, session, coordinate_epoch)
        self._max_nodes = max_nodes
        self._cells: dict[Vector, _Cell] = {}
        self._anchors: dict[Vector, EvidenceRef] = {}
        self._store: EvidenceStore | None = None

    @property
    def scope(self) -> tuple[str, str, int]:
        return self._scope

    @property
    def node_count(self) -> int:
        return len(self._cells.keys() | self._anchors.keys())

    def _bind(self, store: EvidenceStore) -> None:
        if not isinstance(store, EvidenceStore):
            raise ContractError("Navigation requires the retained EvidenceStore")
        if self._store is not None and store is not self._store:
            raise EvidenceError("Observed map cannot borrow another store or restored authority")
        self._store = store

    def _source(self, reference: EvidenceRef, store: EvidenceStore,
                verified: dict[EvidenceRef, dict] | None = None) -> dict:
        if type(reference) is not EvidenceRef:
            raise ContractError("Observed map requires typed evidence references")
        reference.__post_init__()
        if reference.session != self._scope[1] or reference.boundary_kind != "normal_play":
            raise EvidenceError("Observed map requires normal evidence in its exact session")
        if verified is not None and reference in verified:
            return verified[reference]
        state = store.observation(reference)
        if verified is not None:
            verified[reference] = state
        return state

    @staticmethod
    def _newer(reference: EvidenceRef, previous: EvidenceRef) -> bool:
        if reference.revision <= previous.revision:
            return False
        if reference.turn < previous.turn:
            raise EvidenceError("Observed cell game time regressed across source revisions")
        return True

    def add(self, reference: EvidenceRef, store: EvidenceStore) -> None:
        """Project verified cardinal cells atomically; retain no hidden map data."""
        self._bind(store)
        scene = self._source(reference, store)["scene"]
        self._project(reference, scene)

    def _project(self, reference: EvidenceRef, scene: dict) -> None:
        """Project an observation already verified in this call; no store access."""
        position = _position(scene["position"])
        footprint = {position}
        updates: dict[Vector, _Cell] = {}
        for dx, dy, _ in DIRECTIONS.values():
            point = expected_position(position, dx, dy)
            footprint.add(point)
            try:
                visible_destination(scene, dx, dy)
                traversable = True
            except MovementBlocked:
                traversable = False
            previous = self._cells.get(point)
            if previous is None or self._newer(reference, previous.source):
                updates[point] = _Cell(traversable, reference)
        anchor = self._anchors.get(position)
        replace_anchor = anchor is None or self._newer(reference, anchor)
        if len(footprint) > self._max_nodes:
            raise CapacityError("Observed-map footprint exceeds node limit; retained evidence was preserved")
        # Validate every update before replacing either cache. Source revisions
        # already provide recency; a separate access journal would duplicate it.
        cells = self._cells | updates
        anchors = self._anchors.copy()
        if replace_anchor:
            anchors[position] = reference
        coordinates = cells.keys() | anchors.keys()
        excess = len(coordinates) - self._max_nodes
        if excess > 0:
            def oldest(point: Vector) -> tuple[int, Vector]:
                revision = max(cells[point].source.revision if point in cells else -1,
                               anchors[point].revision if point in anchors else -1)
                return revision, point

            for point in sorted(coordinates - footprint, key=oldest)[:excess]:
                cells.pop(point, None)
                anchors.pop(point, None)
        self._cells, self._anchors = cells, anchors

    def shortest_path(self, current_position: Vector, target: Vector, store: EvidenceStore) -> NavigationPath:
        """Deterministic cardinal BFS of candidates, never execution eligibility."""
        return self._shortest_path(current_position, target, store, {})

    def _shortest_path(self, current_position: Vector, target: Vector, store: EvidenceStore,
                       verified: dict[EvidenceRef, dict]) -> NavigationPath:
        current_position, target = _position(current_position), _position(target)
        try:
            self._bind(store)
        except EvidenceError as exc:
            return NavigationPath("unknown", (), (), str(exc))
        if current_position not in self._anchors or current_position[2] != target[2]:
            return NavigationPath("blocked", (), (), "No observed same-level route anchor")
        queue = deque([current_position])
        parents: dict[Vector, Vector | None] = {current_position: None}
        explored_sources = [self._anchors[current_position]]
        path: tuple[Vector, ...] = ()
        while queue:
            point = queue.popleft()
            if point == target:
                reverse_path = []
                while point is not None:
                    reverse_path.append(point)
                    point = parents[point]
                path = tuple(reversed(reverse_path))
                break
            for dx, dy, _ in DIRECTIONS.values():
                neighbor = expected_position(point, dx, dy)
                cell = self._cells.get(neighbor)
                if cell is not None and neighbor not in parents:
                    explored_sources.append(cell.source)
                if neighbor not in parents and cell is not None and cell.traversable:
                    parents[neighbor] = point
                    queue.append(neighbor)
        supports = ([self._anchors[current_position], *(self._cells[point].source for point in path[1:])]
                    if path else explored_sources)
        sources = tuple(dict.fromkeys(supports))
        try:
            for source in sources:
                self._source(source, store, verified)
        except EvidenceError as exc:
            return NavigationPath("unknown", (), sources, str(exc))
        if path:
            return NavigationPath("candidate", path, sources, "Observed cardinal candidate route")
        return NavigationPath("blocked", (), sources, "Target or connecting terrain is unknown or blocked")


class NavigationSkill:
    """One scoped request, at most 32 proposals, with exact settled displacement.

    Repeated propose returns the same still-valid logical proposal. accept consumes
    that proposal once and returns None for verified intermediate progress, or a
    terminal outcome. Unknown delivery never becomes success from a later frame.
    """
    def __init__(self, request: dict | str | bytes, observed_map: ObservedMap):
        data = validate_request(request)
        if data["kind"] != "skill" or data["skill_kind"] != "navigate":
            raise ContractError("Navigation requires an exact navigate skill request")
        scope = data["goal"]["scope"]
        if (type(observed_map) is not ObservedMap or observed_map.scope !=
                (scope["mission_id"], scope["session"], scope["coordinate_epoch"])):
            raise ContractError("Navigation request and observed map must share exact scope")
        self._request = data
        self._logical_prefix = "nav-" + hashlib.sha256(data["request_id"].encode()).hexdigest()
        self._map = observed_map
        self._target = tuple(data["goal"]["target"])
        self._sources: tuple[EvidenceRef, ...] = ()
        self._checkpoint: EvidenceRef | None = None
        self._generation: int | None = None
        self._start: EvidenceRef | None = None
        self._last_monotonic: float | None = None
        self._last_timestamp_ms: int | None = None
        self._steps = self._proposals = 0
        self._position: Vector | None = None
        self._pending: NavigationIntent | None = None
        self._terminal: NavigationOutcome | None = None
        self._revalidation: SourceRevalidation | None = None

    def _clocks(self, now_monotonic: float, now_timestamp_ms: int) -> None:
        if (type(now_monotonic) not in (int, float) or not math.isfinite(now_monotonic)
                or now_monotonic < 0 or type(now_timestamp_ms) is not int or now_timestamp_ms < 0
                or self._last_monotonic is not None and now_monotonic < self._last_monotonic
                or self._last_timestamp_ms is not None and now_timestamp_ms < self._last_timestamp_ms):
            raise EvidenceError("Invalid or regressing navigation clock")
        self._last_monotonic, self._last_timestamp_ms = now_monotonic, now_timestamp_ms

    def _finish(self, reason: str, *, unknown: bool = False, completed: bool = False,
                interrupted: bool = False) -> NavigationOutcome:
        disposition = "unknown" if unknown else "completed" if completed else "partial" if self._steps or interrupted else "blocked"
        self._terminal = NavigationOutcome(disposition, reason, self._steps, self._proposals,
                                           self._position, self._sources,
                                           self._pending.logical_id if self._pending else None,
                                           self._revalidation)
        return self._terminal

    def _scan_sources(self, store: EvidenceStore, verified: dict[EvidenceRef, dict]) -> None:
        self._map._bind(store)
        for source in self._sources:
            self._map._source(source, store, verified)

    def _informing_boundary(self, reference: EvidenceRef, state: dict) -> None:
        data = self._request
        if ((reference.session, reference.revision, state["boundary"]["id"]) !=
                (data["expected_session"], data["expected_revision"], data["expected_boundary_id"])):
            raise EvidenceError("Navigation informing boundary changed before first proposal")

    def _informing_sources(self, store: EvidenceStore) -> tuple[EvidenceRef, ...]:
        references = {ref.observation_id: ref for ref in store.historical_references}
        try:
            return tuple(references[identity] for identity in self._request["sources"])
        except KeyError as exc:
            raise EvidenceError("Navigation informing source is unavailable") from exc

    def revalidate(self, receipt: SourceRevalidation, store: EvidenceStore, *, now_monotonic: float,
                   now_timestamp_ms: int) -> None:
        """Accept one equivalent refresh before initialization; never renew budgets.

        This checks retained evidence and process-local store continuity. The
        runtime must separately authenticate actor/controller/Pause audit fields
        against its live capability map; these records cannot restore authority.
        """
        if self._revalidation is not None or self._start is not None or self._terminal is not None:
            raise ContractError("Navigation revalidation is allowed once before any proposal")
        if type(receipt) is not SourceRevalidation:
            raise ContractError("Navigation requires typed SourceRevalidation")
        receipt.__post_init__()
        if (receipt.original.mission_id, receipt.original.epoch) != (self._request["mission_id"], self._request["epoch"]):
            raise ContractError("Navigation refresh must match its exact mission and epoch")
        self._clocks(now_monotonic, now_timestamp_ms)
        self._map._bind(store)
        sources = self._informing_sources(store)
        original = next((ref for ref in sources if ref.observation_id == receipt.original.source_id), None)
        if original is None:
            raise EvidenceError("Navigation refresh original must be an immutable informing source")
        current = store.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        if (current.observation_id != receipt.current.source_id
                or store.authority_generation() != receipt.current.store_generation):
            raise EvidenceError("Navigation refresh requires the exact current source and generation")
        verified: dict[EvidenceRef, dict] = {}
        for source in (*sources, current):
            state = self._map._source(source, store, verified)
            if source in (original, current):
                self._informing_boundary(source, state)
                if state["takeover_generation"] != receipt.original.takeover_generation:
                    raise EvidenceError("Navigation refresh native takeover binding differs")
        if not store.equivalent(original, current, rule=receipt.rule):
            raise EvidenceError("Navigation refresh is not equivalent to its informing native state")
        self._sources = tuple(dict.fromkeys((*sources, current)))
        self._checkpoint, self._generation = current, receipt.current.store_generation
        self._revalidation = receipt

    def _initialize(self, current: EvidenceRef, state: dict, store: EvidenceStore,
                    verified: dict[EvidenceRef, dict]) -> None:
        self._informing_boundary(current, state)
        sources = self._informing_sources(store)
        if self._revalidation is not None:
            if current != self._checkpoint or store.authority_generation() != self._generation:
                raise EvidenceError("Navigation refresh cannot adopt an intervening source or generation")
            start = next(ref for ref in sources if ref.observation_id == self._revalidation.original.source_id)
        elif current not in sources:
            raise EvidenceError("Navigation requires its exact informing current source")
        else:
            start = current
        self._sources = tuple(dict.fromkeys((*sources, current)))
        self._scan_sources(store, verified)
        self._start, self._checkpoint = start, current
        self._position = _position(state["scene"]["position"])
        self._generation = store.authority_generation()

    def _budget(self, current: EvidenceRef, now_monotonic: float, *, completing: bool = False) -> None:
        limits = self._request["limits"]
        remaining_wall = limits["wall_seconds"] - (now_monotonic - self._start.received_monotonic)
        remaining_game = limits["game_seconds"] - (current.turn - self._start.turn)
        if current.turn < self._start.turn or remaining_wall < 0 or remaining_game < 0:
            raise EvidenceError("Original navigation wall/game budget or time continuity exceeded")
        if not completing and (self._proposals >= limits["primitives"] or remaining_wall <= 0 or remaining_game <= 0):
            raise MovementBlocked("Original navigation proposal/wall/game budget exhausted")

    def _current_guard(self, state: dict, now_timestamp_ms: int, *, dx: int = 1, dy: int = 0,
                       at_goal: bool = False) -> Vector:
        predicate = current_guard if at_goal else guard
        return predicate(state, dx, dy, paused=state["paused"], frozen=False,
                         now_timestamp_ms=now_timestamp_ms)

    def propose(self, store: EvidenceStore, *, now_monotonic: float,
                now_timestamp_ms: int) -> NavigationIntent | NavigationOutcome:
        if self._terminal is not None:
            return self._terminal
        # Observation copies are reused only within this call. current() and
        # observation(current) each verify the current file through public APIs.
        verified: dict[EvidenceRef, dict] = {}
        try:
            self._clocks(now_monotonic, now_timestamp_ms)
            self._map._bind(store)
            current = store.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            state = self._map._source(current, store, verified)
            if self._start is None:
                self._initialize(current, state, store, verified)
            self._scan_sources(store, verified)
            if current.session != self._map.scope[1] or _position(state["scene"]["position"]) != self._position:
                raise EvidenceError("Navigation session or route position changed")
            if self._revalidation is not None and (current != self._checkpoint
                                                   or store.authority_generation() != self._generation):
                raise EvidenceError("Navigation refresh requires its exact attributed checkpoint generation")
            if self._pending is not None:
                if current != self._checkpoint or store.authority_generation() != self._generation:
                    raise EvidenceError("Pending navigation proposal requires exact unchanged before evidence")
                dx = self._pending.target_next[0] - self._position[0]
                dy = self._pending.target_next[1] - self._position[1]
                self._current_guard(state, now_timestamp_ms, dx=dx, dy=dy)
                # The unresolved proposal is already counted; do not require another slot.
                self._budget(current, now_monotonic, completing=True)
                return self._pending
            if current.revision < self._checkpoint.revision or current.turn < self._checkpoint.turn:
                raise EvidenceError("Navigation checkpoint revision or game time regressed")
            self._checkpoint, self._generation = current, store.authority_generation()
            self._sources = tuple(dict.fromkeys((*self._sources, current)))
            self._current_guard(state, now_timestamp_ms, at_goal=True)
            at_goal = self._position == self._target
            self._budget(current, now_monotonic, completing=at_goal)
            if at_goal:
                return self._finish("Scoped target verified at fresh normal checkpoint", completed=True)
            self._map._project(current, state["scene"])
            path = self._map._shortest_path(self._position, self._target, store, verified)
            self._sources = tuple(dict.fromkeys((*self._sources, *path.sources)))
            if path.disposition != "candidate":
                return self._finish(path.reason, unknown=path.disposition == "unknown")
            next_position = path.path[1]
            dx, dy = next_position[0] - self._position[0], next_position[1] - self._position[1]
            self._current_guard(state, now_timestamp_ms, dx=dx, dy=dy)
            action = next(action for x, y, action in DIRECTIONS.values() if (x, y) == (dx, dy))
            if action not in state["actions"]:
                raise MovementBlocked("Navigation cardinal action is not registered in current evidence")
        except (EvidenceError, MovementBlocked) as exc:
            return self._finish(str(exc), unknown=self._pending is not None)
        self._proposals += 1
        self._pending = NavigationIntent(f"{self._logical_prefix}-{self._proposals}", action,
                                         current, state["boundary"]["id"], next_position,
                                         self._revalidation if self._proposals == 1 else None)
        return self._pending

    def accept(self, result: PrimitiveResult, store: EvidenceStore, *, now_monotonic: float,
               now_timestamp_ms: int) -> NavigationOutcome | None:
        if type(result) is not PrimitiveResult:
            raise ContractError("Navigation feedback requires typed PrimitiveResult")
        result.__post_init__()
        pending = self._pending
        if (self._terminal is not None or pending is None or
                (result.action_id, result.before) != (pending.logical_id, pending.before)):
            raise ContractError("Navigation accepts its exact pending logical ID and before reference once")
        verified: dict[EvidenceRef, dict] = {}
        try:
            self._clocks(now_monotonic, now_timestamp_ms)
            self._map._bind(store)
            current = store.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            before = self._map._source(result.before, store, verified)
            after = store.observation(result.after) if result.after is not None else None
            self._scan_sources(store, verified)
            if after is not None and result.after.session != result.before.session:
                raise EvidenceError("Navigation feedback crossed its exact session")
            displacement = (tuple(b - a for a, b in zip(before["scene"]["position"], after["scene"]["position"]))
                            if after is not None and result.after.boundary_kind == "normal_play" else None)
            if result.observed_displacement is not None and result.observed_displacement != displacement:
                raise ContractError("Navigation displacement disagrees with retained observations")
            if (result.transport_disposition == "returned" and result.after is not None
                    and result.after.boundary_kind == "normal_play" and result.observed_displacement is None):
                raise ContractError("Returned navigation requires independently checkable displacement")
            checkpoint = result.after if result.after is not None else result.before
            expected_generation = self._generation + (checkpoint != self._checkpoint)
            if current != checkpoint or store.authority_generation() != expected_generation:
                raise EvidenceError("Intervening observation or invalidation prevents navigation attribution")
            if result.after is not None:
                self._sources = tuple(dict.fromkeys((*self._sources, result.after)))
            if result.transport_disposition in ("unknown", "dispatched"):
                return self._finish(result.reason, unknown=True)
            if result.transport_disposition == "returned" and result.after.boundary_kind != "normal_play":
                if (result.after.boundary_kind != "menu" or not after["in_game"]
                        or after["status"] != "ready" or after["error"] or after["paused"]
                        or after["takeover_generation"] != before["takeover_generation"]
                        or result.after.revision <= result.before.revision):
                    raise EvidenceError("Navigation returned an unsupported or revoked non-normal boundary")
                if now_monotonic - self._start.received_monotonic > self._request["limits"]["wall_seconds"]:
                    raise EvidenceError("Original navigation wall budget exceeded at menu interruption")
                # This input returned, but a menu has no scene or displacement.
                # Keep the verified prefix and last position; never project or
                # retry the interrupted step. The runtime owns explicit controls.
                self._pending = None
                return self._finish("Returned navigation opened an ordinary menu; movement effect unverified",
                                    interrupted=True)
            self._pending = None
            if result.transport_disposition in ("not_dispatched", "rejected"):
                return self._finish(result.reason, unknown=displacement not in (None, (0, 0, 0)))
            dx, dy = pending.target_next[0] - self._position[0], pending.target_next[1] - self._position[1]
            if (result.after.revision <= result.before.revision or result.after.turn < result.before.turn
                    or displacement != (dx, dy, 0) or not observed_step(before, after, dx, dy)):
                return self._finish("First zero, unexpected or unverified navigation displacement")
            self._position = pending.target_next
            self._steps += 1
            self._checkpoint, self._generation = current, expected_generation
            self._current_guard(after, now_timestamp_ms, at_goal=True)
            at_goal = self._position == self._target
            self._budget(current, now_monotonic, completing=at_goal)
            if at_goal:
                return self._finish("Exact returned displacement reached the scoped target", completed=True)
            self._map._project(current, after["scene"])
        except (EvidenceError, MovementBlocked) as exc:
            return self._finish(str(exc), unknown=self._pending is not None)
        return None
