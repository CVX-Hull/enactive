"""Serialized, at-most-once file transport and conservative movement guard."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid
from typing import Any

MAX_REQUEST = 4096
MAX_WAIT = 15.0
NAMED_KEYS = frozenset({"ENTER", "ESC", "UP", "DOWN", "LEFT", "RIGHT", "TAB",
                        "BACKSPACE", "SPACE", "PAGEUP", "PAGEDOWN"})
DIRECTIONS = {"north": (0, -1, "UP"), "south": (0, 1, "DOWN"),
              "west": (-1, 0, "LEFT"), "east": (1, 0, "RIGHT")}
SAFE_TERRAIN = frozenset({"t_floor", "t_grass", "t_dirt", "t_pavement", "t_pavement_y"})


class ControlError(Exception):
    """A visible controller failure; never evidence of game success."""


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as stream:
            data = stream.read(1_048_577)
        if len(data) > 1_048_576:
            raise ControlError(f"{path.name} exceeds metadata size limit")
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ControlError(f"{path.name} is not a JSON object")
        return value
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise ControlError(f"Cannot read {path.name}: {exc}") from exc


def validate_state(value: dict[str, Any], request_id: str | None = None) -> None:
    required = {"id": str, "session": str, "revision": int, "category": str,
                "actions": list, "status": str, "error": str, "paused": bool,
                "timestamp_ms": int, "frame_ok": bool, "in_game": bool}
    if type(value.get("protocol")) is not int or value["protocol"] != 1:
        raise ControlError("Unsupported response protocol; observe after fixing the bridge")
    if request_id is not None and value.get("id") != request_id:
        raise ControlError("Response id does not match request")
    if any(type(value.get(key)) is not expected for key, expected in required.items()):
        raise ControlError("Malformed native response fields")
    if (not value["session"] or value["revision"] < 0
            or value["status"] not in {"ready", "dispatched", "rejected"}
            or not all(isinstance(action, str) for action in value["actions"])):
        raise ControlError("Invalid native response values")
    if value["status"] == "dispatched" and value["frame_ok"]:
        raise ControlError("Dispatched response cannot assert a fresh frame")
    if value.get("scene") is not None and not isinstance(value["scene"], dict):
        raise ControlError("Malformed native scene")


class Controller:
    def __init__(self, root: Path, *, timeout: float = 5.0):
        self.root = Path(root).resolve()
        self.bridge = self.root / ".runtime" / "bridge"
        self.bridge.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.bridge, 0o700)
        self._lock_file = (self.bridge / "controller.lock").open("a+")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock_file.close()
            raise ControlError("Another controller owns this bridge") from exc
        if not 0 < timeout <= MAX_WAIT:
            self.close()
            raise ControlError("Timeout must be greater than 0 and at most 15 seconds")
        self.timeout = timeout
        self.command_lock = threading.Lock()
        self.data_lock = threading.RLock()
        self.state: dict[str, Any] | None = None
        self.frozen = True
        self.closed = False
        self.pause_requested = True
        self.pause_generation = 0
        self.goal = ""
        self.events: list[dict[str, Any]] = []
        self.last_result: dict[str, Any] | None = None
        self.latency_ms: int | None = None
        self.transport_error = "Observe to reconcile, then explicitly resume"
        self.pending: dict[str, Any] | None = None
        self.token = secrets.token_urlsafe(32)
        local_session = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.journal = self.root / ".runtime" / "sessions" / local_session / "events.jsonl"
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        self._pause_file()
        retired = self._retire("startup")
        self._record({"kind": "startup"}, {"status": "paused", "retirement": retired,
                     "error": self.transport_error})

    def close(self) -> None:
        if not hasattr(self, "_lock_file") or self._lock_file.closed:
            return
        if hasattr(self, "data_lock"):
            with self.data_lock:
                self.closed = True
                self.frozen = True
                self.pause_requested = True
                self.pause_generation += 1
            self._pause_file()
            # The process lock outlives every writer, including HTTP worker threads.
            with self.command_lock:
                self._retire("shutdown")
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
                self._lock_file.close()
        else:
            self._pause_file()
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()

    def _pause_file(self) -> None:
        (self.bridge / "pause").touch(mode=0o600, exist_ok=True)

    def _retire(self, reason: str) -> str:
        destination = self.bridge / f"cancelled-{reason}-{uuid.uuid4().hex}.json"
        try:
            os.rename(self.bridge / "request.json", destination)
            return "retired_before_claim"
        except FileNotFoundError:
            return "absent_may_be_claimed_or_dispatched"

    def _record(self, request: dict[str, Any], outcome: dict[str, Any]) -> None:
        event = {"timestamp_ms": int(time.time() * 1000), "request": request,
                 "outcome": outcome}
        with self.data_lock:
            self.events.append(event)
            self.events = self.events[-60:]
            with self.journal.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=True) + "\n")

    def _accept(self, response: dict[str, Any]) -> None:
        with self.data_lock:
            if response["paused"] and self.state is not None and (
                    response["session"], response["revision"]) != (
                    self.state["session"], self.state["revision"]):
                # Native takeover can occur even while already paused. Its new
                # authority invalidates a Resume admitted before that input.
                self.pause_generation += 1
            self.state = response.copy()
            if response["paused"]:
                self.pause_requested = True

    def _exchange(self, kind: str, timeout: float, **payload: Any) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        started = time.monotonic()
        request = {"protocol": 1, "id": request_id, "kind": kind,
                   "deadline_ms": int(time.time() * 1000 + timeout * 1000), **payload}
        if kind not in {"observe", "pause"}:
            if self.state is None:
                raise ControlError("No observation; observe first")
            request.setdefault("session", self.state["session"])
            request.setdefault("revision", self.state["revision"])
        if len(json.dumps(request).encode()) > MAX_REQUEST:
            raise ControlError("Request exceeds 4096 bytes")
        try:
            if self.closed:
                raise ControlError("Controller is shutting down")
            if (self.bridge / "request.json").exists():
                raise ControlError("Unresolved bridge request; observe to reconcile")
            atomic_json(self.bridge / "request.json", request)
            with self.data_lock:
                self.pending = request
            while time.monotonic() - started < timeout:
                if self.closed:
                    raise ControlError("Controller stopped; request will not be replayed")
                response = read_json(self.bridge / "response.json")
                # Prior responses are expected; only the exact UUID can finish this command.
                if response is not None and response.get("id") == request_id:
                    validate_state(response, request_id)
                    if (response["status"] == "ready" and kind in {"key", "action", "resume"}
                            and (response["session"] != request["session"]
                                 or response["revision"] <= request["revision"])):
                        raise ControlError("Ready response has stale or changed session/revision")
                    self._accept(response)
                    if response["status"] != "dispatched":
                        with self.data_lock:
                            self.pending = None
                            self.latency_ms = round((time.monotonic() - started) * 1000)
                        self._record(request, response)
                        return response
                time.sleep(0.015)
            self._pause_file()
            retirement = self._retire("timeout")
            outcome = {"status": "timeout", "id": request_id, "retirement": retirement,
                       "error": "Deadline reached; outcome unknown. Observe to reconcile, then resume."}
            with self.data_lock:
                self.frozen = True
                self.pause_requested = True
                self.transport_error = outcome["error"]
                self.latency_ms = round((time.monotonic() - started) * 1000)
            self._record(request, outcome)
            return outcome
        except (ControlError, OSError) as exc:
            self._pause_file()
            retirement = self._retire("error")
            with self.data_lock:
                self.frozen = True
                self.pause_requested = True
                self.transport_error = str(exc)
            outcome = {"status": "controller_error", "id": request_id,
                       "error": str(exc), "retirement": retirement}
            self._record(request, outcome)
            return outcome

    def pause(self) -> dict[str, Any]:
        # This path deliberately never waits for the command lock or the game.
        with self.data_lock:
            self.pause_generation += 1
            self.pause_requested = True
            self._pause_file()
            result = {"status": "pause_requested", "error": "",
                      "detail": "Pause sentinel set; an already dispatched action cannot be undone"}
            self.last_result = result
        self._record({"kind": "pause"}, result)
        return result

    def execute(self, kind: str, *, timeout: float | None = None, **payload: Any) -> dict[str, Any]:
        wait = self.timeout if timeout is None else timeout
        with self.data_lock:
            admitted_generation = self.pause_generation
        try:
            if self.closed:
                raise ControlError("Controller is closed")
            if kind == "pause":
                return self.pause()
            if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not 0 < wait <= MAX_WAIT:
                raise ControlError("Timeout must be greater than 0 and at most 15 seconds")
            if kind not in {"observe", "key", "action", "resume", "walk", "goal"}:
                raise ControlError("Unknown command")
            if kind == "key":
                key = payload.get("key")
                if not isinstance(key, str) or not (key in NAMED_KEYS or len(key) == 1 and 32 <= ord(key) <= 126):
                    raise ControlError("Key must be one printable ASCII character or a supported named key")
            if kind == "action" and (not isinstance(payload.get("action"), str) or not 1 <= len(payload["action"]) <= 160):
                raise ControlError("Action must name one registered action")
            if kind == "goal":
                goal = payload.get("text")
                if not isinstance(goal, str) or len(goal) > 2000:
                    raise ControlError("Goal must be text of at most 2000 characters")
                with self.data_lock:
                    self.goal = goal
                result = {"status": "recorded", "goal": goal}
                self._record({"kind": "goal", "text": goal}, result)
                return result
            with self.command_lock:
                if self.closed:
                    raise ControlError("Controller is closed")
                if kind == "walk":
                    result = self._walk(payload.get("direction"), payload.get("steps"), wait,
                                        payload.get("expected_session"), payload.get("expected_revision"))
                else:
                    result = self._command(kind, wait, payload, admitted_generation)
                with self.data_lock:
                    self.last_result = result
                return result
        except (ControlError, OSError) as exc:
            result = {"status": "controller_error", "error": str(exc)}
            with self.data_lock:
                self.last_result = result
            self._record({"kind": kind, **payload}, result)
            return result

    def _command(self, kind: str, timeout: float, payload: dict[str, Any], generation: int) -> dict[str, Any]:
        with self.data_lock:
            if kind == "resume" and generation != self.pause_generation:
                return {"status": "pause_requested", "error": "Queued resume superseded by a later pause"}
        if kind != "observe":
            with self.data_lock:
                if self.frozen:
                    raise ControlError("Control is frozen; explicitly observe to reconcile first")
                if kind != "resume" and self.pause_requested:
                    raise ControlError("Paused; explicitly resume before sending inputs")
        if kind == "observe":
            # A fresh observe is safe after the prior deadline plus our pause sentinel.
            if self.pending is not None:
                remaining = (self.pending["deadline_ms"] - time.time() * 1000) / 1000
                if remaining > 0:
                    raise ControlError("Prior request deadline has not passed; wait before reconciliation")
                self._pause_file()
            result = self._exchange("observe", timeout)
            if result["status"] == "ready":
                with self.data_lock:
                    self.frozen = False
                    self.transport_error = ""
                self._record({"kind": "reconcile"}, {"status": "ready", "id": result["id"],
                             "detail": "Fresh observe returned at an eligible native input boundary"})
            return result
        # Observe verifies authority; it must never silently refresh a planner decision.
        observed = self._exchange("observe", timeout)
        if observed["status"] != "ready":
            return observed
        with self.data_lock:
            if kind == "resume" and generation != self.pause_generation:
                return {"status": "pause_requested", "error": "Resume superseded by a later pause"}
        if kind != "resume" and (observed["paused"] or self.pause_requested):
            raise ControlError("Native input is paused; explicit resume required")
        if kind != "resume":
            self._expect(observed, payload.get("expected_session"), payload.get("expected_revision"))
        if kind == "action" and payload["action"] not in observed["actions"]:
            raise ControlError("Action is not registered in the current input context")
        primitive = {kind: payload[kind]} if kind in {"key", "action"} else {}
        result = self._exchange(kind, timeout, session=observed["session"],
                                revision=observed["revision"], **primitive)
        if kind == "resume" and result["status"] == "ready":
            with self.data_lock:
                if generation != self.pause_generation:
                    self._pause_file()
                    self.pause_requested = True
                    result = {**result, "status": "pause_requested", "error": "Resume interrupted by pause"}
                else:
                    self.pause_requested = result["paused"]
        return result

    @staticmethod
    def _expect(state: dict[str, Any], session: Any, revision: Any) -> None:
        if not isinstance(session, str) or type(revision) is not int:
            raise ControlError("Gameplay commands require expected_session and expected_revision from observe")
        if session != state["session"] or revision != state["revision"]:
            raise ControlError("Stale session or revision; observe and reconsider the command")

    def _walk_guard(self, state: dict[str, Any], dx: int, dy: int) -> list[int]:
        if self.pause_requested or state["paused"] or self.frozen:
            raise ControlError("Walk stopped: control is paused or frozen")
        scene = state.get("scene")
        if state["category"] != "DEFAULTMODE" or not state["in_game"] or not isinstance(scene, dict):
            raise ControlError("Walk stopped: normal play scene is unavailable")
        creatures = scene.get("visible_creatures")
        if not isinstance(creatures, list) or creatures:
            raise ControlError("Walk stopped: visible creatures or unknown visibility")
        position = scene.get("position")
        if not isinstance(position, list) or len(position) != 3 or any(type(n) is not int for n in position):
            raise ControlError("Walk stopped: position is unknown")
        neighbors = scene.get("neighbors")
        if not isinstance(neighbors, list):
            raise ControlError("Walk stopped: neighboring terrain is unknown")
        tile = next((tile for tile in neighbors if isinstance(tile, dict)
                     and tile.get("dx") == dx and tile.get("dy") == dy), None)
        if (not tile or tile.get("visible") is not True or tile.get("furniture") != "f_null"
                or not isinstance(tile.get("terrain"), str)
                or tile["terrain"] not in SAFE_TERRAIN):
            raise ControlError("Walk stopped: next tile is not a visible, empty, allowlisted surface")
        return position

    def _walk(self, direction: Any, steps: Any, timeout: float, expected_session: Any, expected_revision: Any) -> dict[str, Any]:
        if not isinstance(direction, str) or direction not in DIRECTIONS or type(steps) is not int or not 1 <= steps <= 8:
            raise ControlError("Walk requires north/south/east/west and 1–8 steps")
        dx, dy, action = DIRECTIONS[direction]
        completed = 0
        previous = None
        try:
            if self.frozen:
                raise ControlError("Control is frozen; explicitly observe to reconcile first")
            for _ in range(steps):
                before = self._exchange("observe", timeout)
                if before["status"] != "ready":
                    raise ControlError(before.get("error") or "Walk stopped: observe failed")
                if previous is not None and any(before[key] != previous[key]
                                                for key in ("session", "revision", "category")):
                    raise ControlError("Walk stopped: input context changed between steps")
                if completed == 0:
                    self._expect(before, expected_session, expected_revision)
                position = self._walk_guard(before, dx, dy)
                if action not in before["actions"]:
                    raise ControlError("Walk stopped: movement action is not registered")
                after = self._exchange("action", timeout, action=action,
                                       session=before["session"], revision=before["revision"])
                if after["status"] != "ready":
                    raise ControlError(after.get("error") or "Walk stopped: action failed")
                scene = after.get("scene")
                expected = [position[0] + dx, position[1] + dy, position[2]]
                if (after["session"] != before["session"] or after["category"] != before["category"]
                        or not isinstance(scene, dict) or scene.get("position") != expected):
                    raise ControlError("Walk stopped: displacement or input context differs from expectation")
                completed += 1
                # Check threats and context even after the final requested step.
                self._walk_guard(after, dx, dy)
                previous = after
            result = {"status": "complete", "steps": completed,
                      "detail": "Requested tile displacement observed; objective success is not inferred"}
        except ControlError as exc:
            result = {"status": "stopped", "steps": completed, "error": str(exc)}
        self._record({"kind": "walk", "direction": direction, "steps": steps}, result)
        return result

    def status(self) -> dict[str, Any]:
        # Reading state never clears a freeze or authorizes a subsequent command.
        try:
            native = read_json(self.bridge / "state.json")
            if native is not None:
                validate_state(native)
                with self.data_lock:
                    if self.state is None or native["timestamp_ms"] >= self.state["timestamp_ms"]:
                        self._accept(native)
        except ControlError as exc:
            with self.data_lock:
                self.transport_error = str(exc)
        with self.data_lock:
            age = None if self.state is None else max(0, int(time.time() * 1000) - self.state["timestamp_ms"])
            connection = "disconnected" if age is None or age > 15000 else "stale" if age > 3000 else "fresh"
            return {"state": self.state, "frozen": self.frozen, "pause_requested": self.pause_requested,
                    "goal": self.goal, "events": list(self.events), "last_result": self.last_result,
                    "latency_ms": self.latency_ms, "age_ms": age, "connection": connection,
                    "error": self.transport_error, "pending": self.pending,
                    "journal": str(self.journal.relative_to(self.root)),
                    "expect": None if self.state is None else f'{self.state["session"]}:{self.state["revision"]}'}
