"""Serialized, at-most-once file transport and conservative movement guard."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import re
import copy
import json
import math
import os
from pathlib import Path
import secrets
import stat
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Callable

from harness.movement import DIRECTIONS, MovementBlocked, guard, observed_step
from harness.gameplay.contracts import ContractError
from harness.gameplay.evidence import EvidenceError, same_native_custody, same_native_state, validate_native_progression
from harness.gameplay.mission_contracts import PAUSE_ORIGINS, validate_visible_ui
from harness.gameplay.native_input import validate_geometry, validate_input

MAX_REQUEST = 4096
MAX_WAIT = 15.0
RECOVERY_KINDS = frozenset({"request_interrupt", "answer_interrupt", "continue_debug_once"})
CONTROL_TERMINAL = frozenset({"prompt_opened", "answer_delivered", "dismissal_delivered", "not_applicable", "rejected"})
NAMED_KEYS = frozenset({"ENTER", "ESC", "UP", "DOWN", "LEFT", "RIGHT", "TAB",
                        "BACKSPACE", "SPACE", "PAGEUP", "PAGEDOWN"})
BOUNDARY_KINDS = frozenset({"normal_play", "activity_poll", "interrupt_confirmation",
                            "debug_prompt", "menu", "unsupported"})
INPUT_BOUNDARIES = frozenset({"normal_play", "menu"})


class ControlError(Exception):
    """A visible controller failure; never evidence of game success."""


class MissionInputRefusal(ControlError):
    """Trusted known-unpublished refusal; fatal custody guards still take priority."""

    def __init__(self, reason: str, *, status: str = "controller_error"):
        if type(reason) is not str or not 1 <= len(reason) <= 1024:
            raise ControlError("Mission refusal requires 1 to 1024 characters")
        super().__init__(reason)
        self.status = status


class _MissionPreflightFailure(ControlError):
    """A stopped mission preparation, before any native input admission."""


@dataclass(frozen=True)
class MissionLease:
    """Descriptive fields are public; only the controller's exact object grants input."""

    mission_id: str
    epoch: int
    actor_id: str
    session: str
    pause_generation: int
    takeover_generation: int
    operation: str


def atomic_json(path: Path, value: dict[str, Any], *,
                before_publish: Callable[[], None] | None = None,
                on_publish: Callable[[], None] | None = None) -> None:
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if before_publish is not None:
            before_publish()
        os.replace(temporary, path)
        if on_publish is not None:
            on_publish()
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
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
                "timestamp_ms": int, "frame_ok": bool, "in_game": bool, "frame": str,
                "pause_origin": str, "takeover_generation": int}
    if type(value.get("protocol")) is not int or value["protocol"] != 6:
        raise ControlError("Unsupported response protocol; observe after fixing the bridge")
    if request_id is not None and value.get("id") != request_id:
        raise ControlError("Response id does not match request")
    if (set(value) != set(required) | {"protocol", "boundary", "scene", "ui", "frame_geometry"}
            or any(type(value.get(key)) is not expected for key, expected in required.items())):
        raise ControlError("Malformed native response fields")
    if (not value["session"] or value["revision"] < 0
            or value["status"] not in {"ready", "dispatched", "rejected"}
            or not all(isinstance(action, str) for action in value["actions"])):
        raise ControlError("Invalid native response values")
    if value["pause_origin"] not in PAUSE_ORIGINS or value["takeover_generation"] < 0:
        raise ControlError("Malformed native takeover metadata")
    try:
        validate_visible_ui(value["ui"])
        if value["frame_ok"]:
            validate_geometry(value["frame_geometry"])
        elif value["frame_geometry"] is not None:
            raise ContractError("Unattested frame cannot assert geometry")
    except ContractError as exc:
        raise ControlError(f"Malformed visible evidence: {exc}") from exc
    if value["status"] == "dispatched" and value["frame_ok"]:
        raise ControlError("Dispatched response cannot assert a fresh frame")
    boundary = value.get("boundary")
    if (not isinstance(boundary, dict)
            or set(boundary) != {"kind", "id", "control_generation", "recovery_operations", "interrupt_request_id", "input_receiver"}
            or not isinstance(boundary["kind"], str) or boundary["kind"] not in BOUNDARY_KINDS
            or not isinstance(boundary["id"], str) or not boundary["id"]
            or type(boundary["control_generation"]) is not int or boundary["control_generation"] < 0
            or not isinstance(boundary["recovery_operations"], list)
            or type(boundary["input_receiver"]) is not bool
            or boundary["input_receiver"] and boundary["kind"] not in INPUT_BOUNDARIES):
        raise ControlError("Malformed or unsupported native boundary")
    operations = boundary["recovery_operations"]
    owner = boundary["interrupt_request_id"]
    expected = {"activity_poll": ["request_interrupt"], "interrupt_confirmation": ["answer_interrupt"],
                "debug_prompt": ["continue_debug_once"]}.get(boundary["kind"], [])
    if (operations not in ([], expected) or (boundary["kind"] == "interrupt_confirmation"
            and (not isinstance(owner, str) or not owner or operations != expected))
            or (boundary["kind"] != "interrupt_confirmation" and owner is not None)):
        raise ControlError("Malformed or unsupported native boundary")
    if boundary["kind"] != "menu" and value["ui"] is not None:
        raise ControlError("Visible menu data outside its native owner")
    if boundary["kind"] != "normal_play" and value.get("scene") is not None:
        raise ControlError("Scene outside normal play")
    if value.get("scene") is not None and not isinstance(value["scene"], dict):
        raise ControlError("Malformed native scene")


def validate_control_request(request: dict[str, Any]) -> None:
    fields = {"protocol", "id", "kind", "session", "control_generation", "authority", "created_ms", "deadline_ms"}
    kind = request.get("kind")
    if not isinstance(kind, str) or kind not in RECOVERY_KINDS:
        raise ControlError("Unsupported stored control kind")
    if kind != "request_interrupt":
        fields |= {"boundary_id", "revision", "frame"}
        if (not isinstance(request.get("boundary_id"), str) or not request["boundary_id"]
                or type(request.get("revision")) is not int or request["revision"] < 0
                or not isinstance(request.get("frame"), str) or not request["frame"]):
            raise ControlError("Malformed control prompt binding")
    if kind == "answer_interrupt":
        fields |= {"interrupt_request_id", "choice"}
        if (not isinstance(request.get("interrupt_request_id"), str) or not request["interrupt_request_id"]
                or not isinstance(request.get("choice"), str) or request["choice"] not in {"YES", "NO"}):
            raise ControlError("Malformed interrupt answer")
    authority = request.get("authority")
    try:
        valid_id = str(uuid.UUID(request.get("id", ""))) == request.get("id")
    except (ValueError, TypeError, AttributeError):
        valid_id = False
    if (set(request) != fields or type(request.get("protocol")) is not int or request["protocol"] != 6
            or not valid_id or len(request["id"]) > 80
            or not isinstance(request.get("session"), str) or not request["session"]
            or type(request.get("control_generation")) is not int or request["control_generation"] < 0
            or type(request.get("created_ms")) is not int or type(request.get("deadline_ms")) is not int
            or request["created_ms"] < 0 or request["created_ms"] > int(time.time() * 1000) + 1000
            or request["deadline_ms"] != request["created_ms"] + 2000
            or not isinstance(authority, dict) or set(authority) != {"controller_boot_id", "counter"}
            or not isinstance(authority["controller_boot_id"], str) or not authority["controller_boot_id"]
            or type(authority["counter"]) is not int or authority["counter"] < 0
            or len(json.dumps(request).encode()) > MAX_REQUEST):
        raise ControlError("Unsupported stored control format; preserve evidence and reconcile offline")


def validate_control_response(value: dict[str, Any], request_id: str | None = None) -> None:
    if (set(value) != {"protocol", "id", "status", "error", "state"}
            or type(value.get("protocol")) is not int or value["protocol"] != 6
            or not isinstance(value.get("id"), str) or not value["id"]
            or not isinstance(value.get("status"), str) or value["status"] not in CONTROL_TERMINAL | {"dispatched"}
            or not isinstance(value.get("error"), str) or not isinstance(value.get("state"), dict)
            or (request_id is not None and value["id"] != request_id)):
        raise ControlError("Malformed or unsupported control response")
    validate_state(value["state"])
    if value["status"] == "prompt_opened":
        state = value["state"]
        if (not state["frame_ok"] or state["boundary"]["kind"] != "interrupt_confirmation"
                or state["boundary"]["interrupt_request_id"] != value["id"]):
            raise ControlError("Prompt result lacks fresh owned confirmation")


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
        self.control_lock = threading.Lock()
        self.data_lock = threading.RLock()
        self._journal_lock = threading.RLock()
        self.state: dict[str, Any] | None = None
        self._state_received_monotonic: float | None = None
        self.frozen = True
        self.closed = False
        self.pause_requested = True
        self.pause_generation = 0
        # Host-local user intent survives ordinary internal authority revocations.
        # A new controller boot cannot reuse a captured counter from the old boot.
        self.operator_pause_generation = 0
        self._mission_lease: MissionLease | None = None
        self._command_work = 0
        self.authority = {"controller_boot_id": uuid.uuid4().hex, "counter": 0}
        self.unknown_outcomes: list[dict[str, Any]] = []
        self.goal = ""
        self.events: list[dict[str, Any]] = []
        self.last_result: dict[str, Any] | None = None
        self.latency_ms: int | None = None
        self.transport_error = "Observe to reconcile, then explicitly resume"
        self.pending: dict[str, Any] | None = None
        self.control_pending: dict[str, Any] | None = None
        self.control_unknown_outcomes: list[dict[str, Any]] = []
        self.control_admitted: dict[str, dict[str, Any]] = {}
        # Process-local custody references, never restored as authority/history.
        # The existing admission/cancellation files remain the evidence source.
        self._retired_mission_inputs: dict[tuple[bool, str], tuple[Path, dict]] = {}
        self._mission_delivery_evidence: dict[tuple[bool, str], dict] = {}
        self.historical_unknowns: tuple[dict[str, Any], ...] = ()
        self.token = secrets.token_urlsafe(32)
        local_session = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.journal = self.root / ".runtime" / "sessions" / local_session / "events.jsonl"
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        self.admissions = self.bridge / "admissions"
        self.admissions.mkdir(mode=0o700, exist_ok=True)
        self.control_admissions = self.bridge / "control-admissions"
        self.control_admissions.mkdir(mode=0o700, exist_ok=True)
        self._revoke()
        self._pause_file()
        try:
            self._load_historical()
            restored_input_ids: set[str] = set()
            for path in sorted(self.admissions.glob("*.json")):
                admission = read_json(path)
                if admission is not None:
                    self._restore_request(admission, "startup found unresolved durable admission; never replay")
                    if admission["kind"] in {"key", "action", "direct", "resume"}:
                        restored_input_ids.add(admission["id"])
            inbox = read_json(self.bridge / "request.json")
            if inbox is not None:
                self._restore_request(inbox, "startup retired unclaimed request")
            for path in sorted(self.control_admissions.glob("*.json")):
                admission = read_json(path)
                if admission is not None:
                    self._restore_control(admission, "startup found unresolved control admission")
            for name in ("control.json", "control-claimed.json"):
                stored = read_json(self.bridge / name)
                if stored is not None:
                    validate_control_request(stored)
                    if self.control_admitted.get(stored["id"]) != stored:
                        raise ControlError("Control inbox/claim lacks its exact durable admission")
                    self._restore_control(stored, "startup found control request; never replay")
            control_response = read_json(self.bridge / "control-response.json")
            if control_response is not None:
                validate_control_response(control_response)
                if control_response["status"] == "dispatched" and control_response["id"] not in self.control_admitted:
                    raise ControlError("Dispatched control response lacks a current durable admission")
                self._reconcile_control(control_response)
            claimed = read_json(self.bridge / "claimed.json")
            if claimed is not None:
                self._restore_request(claimed, "startup found claimed request")
                if claimed["kind"] in {"key", "action", "direct", "resume"}:
                    restored_input_ids.add(claimed["id"])
            response = read_json(self.bridge / "response.json")
            if response is not None:
                validate_state(response)
                if (response["status"] == "dispatched"
                        and response["id"] not in restored_input_ids):
                    raise ControlError("Dispatched response lacks a current durable admission; preserve evidence and reconcile offline")
        except (ControlError, OSError):
            self.close()
            raise
        retired = self._retire("startup")
        self._retire("startup", control=True)
        self._record({"kind": "startup"}, {"status": "paused", "retirement": retired,
                     "error": self.transport_error, "historical_unknowns": list(self.historical_unknowns)})

    def _load_historical(self) -> None:
        value = read_json(self.bridge / "historical-incidents.json")
        if value is None:
            return
        if (set(value) != {"schema", "incidents"} or value["schema"] != "incident/1"
                or not isinstance(value["incidents"], list) or len(value["incidents"]) > 64):
            raise ControlError("Unsupported historical incident references")
        seen = set()
        references = []
        archive = (self.root / ".runtime/incidents").resolve()
        for item in value["incidents"]:
            if (not isinstance(item, dict) or set(item) != {"id", "channel", "source_path", "source_sha256", "reason"}
                    or not isinstance(item["id"], str) or not 1 <= len(item["id"]) <= 128
                    or not isinstance(item["channel"], str) or item["channel"] not in {"gameplay", "control"}
                    or not isinstance(item["reason"], str) or not 1 <= len(item["reason"]) <= 1024
                    or not isinstance(item["source_path"], str) or not 1 <= len(item["source_path"]) <= 1024
                    or not isinstance(item["source_sha256"], str)
                    or re.fullmatch(r"[0-9a-f]{64}", item["source_sha256"]) is None
                    or (item["channel"], item["id"]) in seen):
                raise ControlError("Malformed historical incident reference")
            relative = Path(item["source_path"])
            source = (self.root / relative).resolve()
            if (relative.is_absolute() or relative.parts[:2] != (".runtime", "incidents")
                    or not archive.is_relative_to(self.root / ".runtime")
                    or not source.is_relative_to(archive) or not source.is_file()):
                raise ControlError("Historical source is missing or outside the owned archive")
            with source.open("rb") as stream:
                data = stream.read(1_048_577)
            if len(data) > 1_048_576 or hashlib.sha256(data).hexdigest() != item["source_sha256"]:
                raise ControlError("Historical source size or SHA-256 mismatch")
            seen.add((item["channel"], item["id"]))
            references.append(item.copy())
        self.historical_unknowns = tuple(references)

    def _restore_control(self, request: dict[str, Any], reason: str) -> None:
        validate_control_request(request)
        previous = self.control_admitted.get(request["id"])
        if previous is not None and previous != request:
            raise ControlError("Conflicting durable control identity")
        self.control_admitted[request["id"]] = request.copy()
        if self.control_pending is None or request["created_ms"] > self.control_pending["created_ms"]:
            self.control_pending = request.copy()
        self._control_unknown(request, reason)

    def _control_unknown(self, request: dict[str, Any], reason: str) -> None:
        if any(item["request"]["id"] == request["id"] for item in self.control_unknown_outcomes):
            return
        outcome = {"status": "unknown", "reason": reason, "request": request.copy()}
        self.control_unknown_outcomes.append(outcome)
        self.control_unknown_outcomes = self.control_unknown_outcomes[-60:]
        self._record({"kind": "control_unresolved", "id": request["id"]}, outcome)

    def _validate_admitted_control_response(self, response: dict[str, Any]) -> dict[str, Any] | None:
        """Pure correlation under data_lock; no acceptance, revocation or I/O."""
        validate_control_response(response)
        request = self.control_admitted.get(response["id"])
        if request is None:
            return None
        status, native = response["status"], response["state"]
        allowed = {"request_interrupt": {"prompt_opened", "not_applicable"},
                   "answer_interrupt": {"answer_delivered"},
                   "continue_debug_once": {"dismissal_delivered"}}[request["kind"]] | {"dispatched", "rejected"}
        if status not in allowed:
            raise ControlError("Control result does not match admitted operation")
        if status not in {"rejected", "not_applicable"} and (native["session"] != request["session"]
                or native["boundary"]["control_generation"] <= request["control_generation"] or not native["paused"]):
            raise ControlError("Control result has stale session/generation or resumed gameplay")
        return request

    def _reconcile_control(self, response: dict[str, Any] | None = None, *, retire: bool = True) -> dict[str, Any] | None:
        with self.data_lock:
            response = read_json(self.bridge / "control-response.json") if response is None else response
            if response is None:
                return None
            request = self._validate_admitted_control_response(response)
            if request is None:
                return None
            status = response["status"]
            native = response["state"]
            if self.state is None or native["timestamp_ms"] >= self.state["timestamp_ms"]:
                # Correlated dispatched progress still owns the live slot; it
                # is neither a takeover nor an acknowledgment timeout. Only an
                # actual unknown path records uncertainty for this same input.
                self._accept(native, known_control_id=request["id"], historical=status in CONTROL_TERMINAL)
            if retire and status in CONTROL_TERMINAL:
                if self.control_pending is not None and self.control_pending["id"] == request["id"]:
                    self.control_pending = None
                self.control_admitted.pop(request["id"])
                for outcome in self.control_unknown_outcomes:
                    if outcome["request"]["id"] == request["id"]:
                        outcome["transport_result"] = status
        if retire and status in CONTROL_TERMINAL:
            (self.control_admissions / f'{request["id"]}.json').unlink(missing_ok=True)
            self._record(request, response)
        return response

    def _reconcile_expired_control(self, observed: dict[str, Any]) -> None:
        # Only an explicit successful fresh observe can retire the live slot. The
        # durable admission remains uncertainty; passive status never rearms it.
        with self.data_lock:
            self._reconcile_control()
            pending = self.control_pending
            if pending is None or self.control_lock.locked():
                return
            if (int(time.time() * 1000) <= pending["deadline_ms"] or not observed["frame_ok"]
                    or int(time.time() * 1000) - observed["timestamp_ms"] > 3000):
                return
            self._revoke()
            self._pause_file()
            self._retire("reconcile", control=True)
            claimed = read_json(self.bridge / "control-claimed.json")
            if claimed is not None:
                validate_control_request(claimed)
                if claimed["id"] != pending["id"] or claimed["deadline_ms"] >= int(time.time() * 1000):
                    raise ControlError("Control claim cannot safely reconcile")
                destination = self.bridge / f'control-cancelled-reconcile-{uuid.uuid4().hex}.json'
                try:
                    os.rename(self.bridge / "control-claimed.json", destination)
                except FileNotFoundError:
                    pass  # Native completed its claim; revoked token still prevents delivery.
            self._control_unknown(pending, "expired control reconciled without establishing outcome")
            self.control_pending = None

    def recover(self, kind: str, *, timeout: float | None = None, **payload: Any) -> dict[str, Any]:
        """Explicit local operator API; never called through ordinary execute ingress."""
        wait = self.timeout if timeout is None else timeout
        acquired = False
        request = None
        try:
            if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not 0 < wait <= MAX_WAIT:
                raise ControlError("Timeout must be greater than 0 and at most 15 seconds")
            if not isinstance(kind, str) or kind not in RECOVERY_KINDS:
                raise ControlError("Unknown recovery operation")
            acquired = self.control_lock.acquire(blocking=False)
            if not acquired:
                raise ControlError("Recovery writer is active")
            with self.data_lock:
                if self.closed:
                    raise ControlError("Controller is closed")
                if self.control_pending is not None or (self.bridge / "control.json").exists() or (self.bridge / "control-claimed.json").exists():
                    raise ControlError("Recovery is pending; explicitly observe after expiry to reconcile")
                self.pause()  # Revoke before admission, including when already paused.
                state = self.state
                required = {"expected_session", "expected_control_generation"}
                if kind != "request_interrupt":
                    required |= {"expected_boundary_id", "expected_revision", "expected_frame"}
                if kind == "answer_interrupt":
                    required |= {"interrupt_request_id", "choice"}
                if set(payload) != required or state is None:
                    raise ControlError("Recovery requires explicit current session/generation and exact prompt evidence")
                boundary = state["boundary"]
                if (type(payload["expected_control_generation"]) is not int
                        or payload["expected_session"] != state["session"]
                        or payload["expected_control_generation"] != boundary["control_generation"]):
                    raise ControlError("Stale recovery session or control generation")
                if not state["frame_ok"] or int(time.time() * 1000) - state["timestamp_ms"] > 3000:
                    raise ControlError("Recovery requires a fresh rendered boundary")
                if kind not in boundary["recovery_operations"]:
                    raise ControlError("Recovery operation is not advertised at this boundary")
                created = int(time.time() * 1000)
                request = {"protocol": 6, "id": str(uuid.uuid4()), "kind": kind, "session": state["session"],
                           "control_generation": boundary["control_generation"], "authority": self.authority.copy(),
                           "created_ms": created, "deadline_ms": created + 2000}
                if kind != "request_interrupt":
                    if (not state["frame_ok"] or created - state["timestamp_ms"] > 3000
                            or payload["expected_boundary_id"] != boundary["id"]
                            or type(payload["expected_revision"]) is not int or payload["expected_revision"] != state["revision"]
                            or payload["expected_frame"] != state["frame"]):
                        raise ControlError("Stale recovery prompt, revision or frame")
                    request.update(boundary_id=boundary["id"], revision=state["revision"], frame=state["frame"])
                if kind == "answer_interrupt":
                    if payload["interrupt_request_id"] != boundary["interrupt_request_id"]:
                        raise ControlError("Interrupt owner does not match")
                    request.update(interrupt_request_id=payload["interrupt_request_id"], choice=payload["choice"])
                validate_control_request(request)
                atomic_json(self.control_admissions / f'{request["id"]}.json', request)
                self.control_admitted[request["id"]] = request.copy()
                self.control_pending = request.copy()
                atomic_json(self.bridge / "control.json", request)
            started = time.monotonic()
            while time.monotonic() - started < min(wait, 2.0):
                if self.closed:
                    raise ControlError("Controller stopped during recovery; never replay")
                response = self._reconcile_control()
                if response is not None and response["id"] == request["id"] and response["status"] in CONTROL_TERMINAL:
                    return response
                time.sleep(0.015)
            with self.data_lock:
                self._revoke()
                self._pause_file()
                self._control_unknown(request, "control wait reached; delivery is unknown")
                self.frozen = True
                self.transport_error = "Recovery outcome unknown; explicitly observe after expiry to reconcile"
                retirement = self._retire("timeout", control=True)
            outcome = {"status": "unknown", "id": request["id"], "error": self.transport_error, "retirement": retirement}
            self._record(request, outcome)
            return outcome
        except (ControlError, OSError) as exc:
            with self.data_lock:
                if acquired:
                    self._revoke()
                    self._pause_file()
                    self.pause_requested = True
                if request is not None and request["id"] in self.control_admitted:
                    self._control_unknown(request, str(exc))
                    self.frozen = True
            outcome = {"status": "controller_error", "error": str(exc)}
            if request is not None:
                outcome["id"] = request["id"]
            self._record({"kind": kind, **payload}, outcome)
            return outcome
        finally:
            if acquired:
                self.control_lock.release()

    def recover_mission(self, kind: str, *, expected_generation: int, expected_operator_generation: int,
                        expected_controller_boot_id: str, expected_session: str, expected_revision: int,
                        expected_boundary_id: str, expected_takeover_generation: int,
                        expected_pause_origin: str, expected_control_generation: int,
                        logical_action_id: str, deadline_monotonic: float, timeout: float | None = None,
                        expected_image_sha256: str | None = None,
                        preflight: Callable[[dict[str, Any], float], None] | None = None,
                        interrupt_request_id: str | None = None, choice: str | None = None) -> dict[str, Any]:
        """Trusted paused activity control, retaining the mission's original consent.

        The runtime deliberately stops input and supplies its original operator
        mark. This API grants neither a lease nor Resume and is absent from JSON
        ingress. Native recovery requests/admissions keep their existing format.
        """
        receipt = {"logical_action_id": logical_action_id, "request": None, "result": None,
                   "published": False, "received_monotonic": None, "preflight": None, "processing_error": None}
        binding = {"session": expected_session, "revision": expected_revision,
                   "boundary_id": expected_boundary_id, "takeover_generation": expected_takeover_generation,
                   "pause_origin": expected_pause_origin, "control_generation": expected_control_generation,
                   "operator_pause_generation": expected_operator_generation,
                   "controller_boot_id": expected_controller_boot_id}
        wait = self.timeout if timeout is None else timeout
        request = None
        active = False
        acquired = False
        failed = False
        try:
            if (type(logical_action_id) is not str or not 1 <= len(logical_action_id) <= 128
                    or type(deadline_monotonic) not in (int, float) or not 0 <= deadline_monotonic <= 1e12):
                raise ControlError("Invalid mission identity or deadline")
            if (any(type(value) is not int or value < 0 for value in
                    (expected_generation, expected_operator_generation, expected_revision,
                     expected_takeover_generation, expected_control_generation))
                    or any(type(value) is not str or not value for value in
                           (expected_controller_boot_id, expected_session, expected_boundary_id))
                    or type(expected_pause_origin) is not str or expected_pause_origin not in PAUSE_ORIGINS):
                raise ControlError("Malformed mission recovery binding")
            if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not 0 < wait <= MAX_WAIT:
                raise ControlError("Timeout must be greater than 0 and at most 15 seconds")
            if type(kind) is not str or kind not in {"request_interrupt", "answer_interrupt"}:
                raise ControlError("Unsupported mission recovery operation")
            if (kind == "request_interrupt" and (interrupt_request_id is not None or choice is not None)
                    or kind == "answer_interrupt" and (type(interrupt_request_id) is not str
                        or not interrupt_request_id or type(choice) is not str or choice not in {"YES", "NO"})):
                raise ControlError("Mission recovery requires an exact interrupt owner and YES/NO answer")
            if expected_image_sha256 is not None and (type(expected_image_sha256) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", expected_image_sha256) is None):
                raise ControlError("Expected image hash must be exactly 64 lowercase hexadecimal characters")
            if preflight is not None and not callable(preflight):
                raise ControlError("Mission preflight must be a trusted Python callback")
            with self._command_slot(deadline_monotonic):
                acquired = self.control_lock.acquire(blocking=False)
                if not acquired:
                    raise ControlError("Recovery writer is active")
                try:
                    with self.data_lock:
                        if self._command_work:
                            raise ControlError("Command work is pending for mission recovery")
                        self._command_work += 1
                        active = True
                        self._check_mission_recovery(self.state, binding, expected_generation, kind,
                                                     interrupt_request_id)
                        pause_snapshot = self._pause_snapshot()
                    observation_receipt: dict[str, float] = {}
                    observed = self._exchange("observe", wait, deadline_monotonic=deadline_monotonic,
                                              observation_receipt=observation_receipt)
                    with self.data_lock:
                        self._check_mission_recovery(observed, binding, expected_generation, kind,
                                                     interrupt_request_id)
                    received = observation_receipt["received_monotonic"]
                    checked_frame = observed["frame"]

                    def check_preflight() -> None:
                        self._check_mission_recovery(observed, binding, expected_generation, kind,
                                                     interrupt_request_id)
                        if (not same_native_state(self.state, observed) or self.state["frame"] != checked_frame
                                or self._pause_snapshot() != pause_snapshot):
                            raise ControlError("Native boundary, frame or Pause changed during recovery preflight")
                        if not 0 <= time.monotonic() - received <= 3:
                            raise ControlError("Final preflight observation expired")
                        if time.monotonic() >= deadline_monotonic:
                            raise ControlError("Original dispatch deadline expired before control publication")
                        if request is not None and int(time.time() * 1000) >= request["deadline_ms"]:
                            raise ControlError("Original native control deadline expired before publication")

                    if expected_image_sha256 is not None and self._frame_sha256(observed) != expected_image_sha256:
                        raise ControlError("Final preflight image differs from the informing image")
                    receipt["preflight"] = {"observation": copy.deepcopy(observed),
                        "received_monotonic": received, "expected_image_sha256": expected_image_sha256}
                    if preflight is not None:
                        try:
                            preflight(copy.deepcopy(observed), received)
                        except Exception as exc:
                            raise ControlError(f"Mission preflight failed: {type(exc).__name__}: {exc}") from exc
                    # Retention and image I/O cannot hold up operator Pause.
                    if expected_image_sha256 is not None and self._frame_sha256(observed) != expected_image_sha256:
                        raise ControlError("Final preflight image changed during recovery preflight")
                    checked_frame = self._preflight_capture(observed)
                    with self.data_lock:
                        check_preflight()
                        authority = self.authority.copy()
                    created = int(time.time() * 1000)
                    request = {"protocol": 6, "id": str(uuid.uuid4()), "kind": kind,
                               "session": observed["session"], "control_generation": expected_control_generation,
                               "authority": authority, "created_ms": created, "deadline_ms": created + 2000}
                    if kind == "answer_interrupt":
                        request.update(boundary_id=expected_boundary_id, revision=expected_revision,
                                       frame=observed["frame"], interrupt_request_id=interrupt_request_id, choice=choice)
                    validate_control_request(request)
                    receipt["request"] = copy.deepcopy(request)
                    atomic_json(self.control_admissions / f'{request["id"]}.json', request)
                    self._record({"kind": "mission_admission", "logical_action_id": logical_action_id},
                                 {"request": copy.deepcopy(request)})
                    with self.data_lock:
                        self.control_admitted[request["id"]] = request.copy()
                    publication_locked = False

                    def before_publish() -> None:
                        nonlocal publication_locked
                        # Stage/fsync the file outside data_lock; serialize only
                        # its final authority check and atomic visibility with Pause.
                        self.data_lock.acquire()
                        publication_locked = True
                        check_preflight()
                        if self.authority != authority:
                            raise ControlError("Control authority changed before publication")

                    def on_publish() -> None:
                        nonlocal publication_locked
                        receipt["published"] = True
                        self.control_pending = request.copy()
                        self.data_lock.release()
                        publication_locked = False

                    try:
                        atomic_json(self.bridge / "control.json", request,
                                    before_publish=before_publish, on_publish=on_publish)
                    finally:
                        if publication_locked:
                            self.data_lock.release()
                    end = min(deadline_monotonic, time.monotonic() + wait,
                              time.monotonic() + max(0, (request["deadline_ms"] - time.time() * 1000) / 1000))
                    while time.monotonic() < end:
                        if self.closed:
                            raise ControlError("Controller stopped during recovery; never replay")
                        response = read_json(self.bridge / "control-response.json")
                        terminal_received = time.monotonic()
                        if response is not None and response.get("id") == request["id"]:
                            with self.data_lock:
                                admitted = self._validate_admitted_control_response(response)
                                terminal = admitted is not None and response["status"] in CONTROL_TERMINAL
                                if terminal:
                                    receipt["received_monotonic"] = terminal_received
                                    receipt["result"] = copy.deepcopy(response)
                            if terminal:
                                self._reconcile_control(response)
                                break
                            self._reconcile_control(response)
                        time.sleep(min(0.015, max(0, end - time.monotonic())))
                    else:
                        with self.data_lock:
                            self._revoke()
                            self._pause_file()
                            self.frozen = True
                            self.transport_error = "Recovery outcome unknown; explicitly observe after expiry to reconcile"
                        self._control_unknown(request, "control wait reached; delivery is unknown")
                        retirement = self._retire("timeout", control=True)
                        receipt["result"] = {"status": "unknown", "id": request["id"],
                                             "error": self.transport_error, "retirement": retirement}
                finally:
                    if active:
                        with self.data_lock:
                            self._command_work -= 1
                        active = False
                    self.control_lock.release()
                    acquired = False
        except (ControlError, OSError) as exc:
            failed = True
            known_terminal = receipt["received_monotonic"] is not None
            if known_terminal:
                self._mission_processing_failure(receipt, exc)
            if not known_terminal:
                receipt["result"] = {"status": "controller_error", "error": str(exc)}
            with self.data_lock:
                self.transport_error = str(exc)
            if request is not None:
                receipt["result"]["id"] = request["id"]
                if receipt["published"]:
                    with self.data_lock:
                        self._revoke()
                        self._pause_file()
                        self.frozen = True
                    if not known_terminal:
                        self._control_unknown(request, str(exc))
                else:
                    with self.data_lock:
                        self.control_admitted.pop(request["id"], None)
                    (self.control_admissions / f'{request["id"]}.json').unlink(missing_ok=True)
        known_terminal = receipt["received_monotonic"] is not None
        try:
            return self._finish_mission_receipt(receipt, failed and not known_terminal)
        except OSError as exc:
            if not known_terminal:
                raise
            # A retained terminal ACK is actual transport evidence even when
            # later receipt persistence fails. Stop input without rewriting it.
            with self.data_lock:
                self._revoke()
                self.frozen = True
                self.pause_requested = True
                self.transport_error = f"Mission control receipt persistence failed: {exc}"
            self._pause_file()
            return receipt

    def _check_mission_recovery(self, observed: dict[str, Any] | None, binding: dict[str, Any],
                                generation: int, kind: str, interrupt_request_id: str | None) -> None:
        """Under data_lock, excluding only this operation's command/control slots."""
        if (self.closed or generation != self.pause_generation
                or binding["operator_pause_generation"] != self.operator_pause_generation
                or binding["controller_boot_id"] != self.authority["controller_boot_id"]):
            raise ControlError("Mission recovery superseded by host Pause or takeover")
        if (not self.pause_requested or self._pause_snapshot() is None or self._mission_lease is not None
                or self._command_work != 1 or self.pending is not None or self.control_pending is not None
                or any((self.bridge / name).exists() for name in
                       ("request.json", "claimed.json", "control.json", "control-claimed.json"))):
            raise ControlError("Mission recovery requires paused empty command/control slots and no lease")
        if observed is None:
            raise ControlError("Mission recovery requires a current paused observation")
        validate_state(observed)
        self._expect(observed, binding["session"], binding["revision"])
        self._expect_boundary(observed, binding["boundary_id"])
        boundary = observed["boundary"]
        if (observed["takeover_generation"] != binding["takeover_generation"]
                or observed["pause_origin"] != binding["pause_origin"]
                or boundary["control_generation"] != binding["control_generation"]):
            raise ControlError("Mission recovery superseded by native pause/takeover or control generation")
        age = int(time.time() * 1000) - observed["timestamp_ms"]
        if (observed["status"] != "ready" or observed["error"] or not observed["paused"]
                or not observed["frame_ok"] or not observed["frame"] or not -1000 <= age <= 3000
                or kind not in boundary["recovery_operations"]):
            raise ControlError("Mission recovery requires a fresh paused advertised activity boundary")
        if kind == "answer_interrupt" and interrupt_request_id != boundary["interrupt_request_id"]:
            raise ControlError("Interrupt owner does not match")

    def _restore_request(self, request: dict[str, Any], reason: str) -> None:
        """Restore only current-format uncertainty; never translate older records."""
        self._validate_stored_request(request)
        self._unknown(request, reason)

    @staticmethod
    def _validate_stored_request(request: dict[str, Any]) -> None:
        fields = {"protocol", "id", "kind", "deadline_ms"}
        kind = request.get("kind")
        if not isinstance(kind, str) or kind not in {"observe", "pause", "resume", "key", "action", "direct"}:
            raise ControlError("Unsupported stored request kind; migrate or archive offline")
        if kind in {"resume", "key", "action", "direct"}:
            fields |= {"session", "revision", "boundary_id", "takeover_generation", "authority", "frame", "require_exact_frame"}
            authority = request.get("authority")
            if (not isinstance(request.get("session"), str) or not request["session"]
                    or type(request.get("revision")) is not int or request["revision"] < 0
                    or not isinstance(request.get("boundary_id"), str) or not request["boundary_id"]
                    or not isinstance(request.get("frame"), str) or not request["frame"]
                    or type(request.get("require_exact_frame")) is not bool
                    or type(request.get("takeover_generation")) is not int or request["takeover_generation"] < 0
                    or not isinstance(authority, dict) or set(authority) != {"controller_boot_id", "counter"}
                    or not isinstance(authority["controller_boot_id"], str) or not authority["controller_boot_id"]
                    or type(authority["counter"]) is not int or authority["counter"] < 0):
                raise ControlError("Malformed stored authority; migrate or archive offline")
        if kind in {"key", "action"}:
            fields.add(kind)
            if not isinstance(request.get(kind), str) or not request[kind]:
                raise ControlError("Malformed stored input; migrate or archive offline")
        if kind == "direct":
            fields.add("input")
            try:
                validate_input(request.get("input"))
            except ContractError as exc:
                raise ControlError(f"Malformed stored direct input: {exc}") from exc
            if request["require_exact_frame"] is not False:
                raise ControlError("Direct input must bind the actual receiver without exact-image equality")
        if (set(request) != fields or type(request.get("protocol")) is not int or request["protocol"] != 6
                or not isinstance(request.get("id"), str) or not request["id"]
                or type(request.get("deadline_ms")) is not int):
            raise ControlError("Unsupported stored request format; migrate or archive offline")

    def close(self) -> None:
        if not hasattr(self, "_lock_file") or self._lock_file.closed:
            return
        if hasattr(self, "data_lock"):
            with self.data_lock:
                self.closed = True
                self.frozen = True
                self.pause_requested = True
                self._revoke()
            self._pause_file()
            # The process lock outlives every writer, including HTTP worker threads.
            with self.command_lock, self.control_lock:
                self._retire("shutdown")
                self._retire("shutdown", control=True)
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
                self._lock_file.close()
        else:
            self._pause_file()
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()

    def _revoke(self) -> None:
        """Call under data_lock: token publication precedes retirement/admission."""
        self._mission_lease = None
        self.pause_generation += 1
        counter = self.authority["counter"] + 1
        if counter > 2_147_483_647:
            self.authority = {"controller_boot_id": uuid.uuid4().hex, "counter": 0}
        else:
            self.authority = {**self.authority, "counter": counter}
        atomic_json(self.bridge / "authority.json", self.authority)

    def _unknown(self, request: dict[str, Any], reason: str) -> None:
        if request.get("kind") not in {"key", "action", "direct", "resume"}:
            return
        if any(item["request"].get("id") == request.get("id") for item in self.unknown_outcomes):
            return
        outcome = {"status": "unknown", "reason": reason, "request": request.copy()}
        self.unknown_outcomes.append(outcome)
        self.unknown_outcomes = self.unknown_outcomes[-60:]
        self._record({"kind": "unresolved", "id": request.get("id")}, outcome)

    def _pause_file(self) -> None:
        (self.bridge / "pause").touch(mode=0o600, exist_ok=True)

    def _retire(self, reason: str, *, control: bool = False) -> str:
        prefix = "control-" if control else ""
        destination = self.bridge / f"{prefix}cancelled-{reason}-{uuid.uuid4().hex}.json"
        try:
            os.rename(self.bridge / ("control.json" if control else "request.json"), destination)
            with self.data_lock:
                pending = self.control_pending if control else self.pending
                if pending is not None:
                    # Compare the file's actual contents at proof collection.
                    # A pending ID alone cannot attest which file was renamed.
                    self._retired_mission_inputs[(control, pending["id"])] = (destination, copy.deepcopy(pending))
                    while len(self._retired_mission_inputs) > 60:
                        self._retired_mission_inputs.pop(next(iter(self._retired_mission_inputs)))
            return "retired_before_claim"
        except FileNotFoundError:
            return "absent_may_be_claimed_or_dispatched"

    def inspect_mission_delivery(self, *, expected_request: dict[str, Any],
                                 expected_controller_boot_id: str, expected_operator_generation: int,
                                 expected_generation: int, expected_takeover_generation: int,
                                 deadline_monotonic: float) -> dict[str, Any] | None:
        """Collect exact unknown-input evidence without sending/accepting input.

        Collect before publishing Observe: the native writer can overwrite a
        terminal response with that Observe. Host locks do not close that race.
        Collection is bounded to250ms and its original caller deadline. A miss
        remains ambiguous; no frame, absent inbox or caller assertion is proof.
        Returning evidence neither retires pending custody nor grants a lease,
        changes an ACK, clears frozen state, publishes Observe or sends Resume.
        """
        started = time.monotonic()
        if type(expected_request) is not dict:
            raise ControlError("Delivery proof requires its exact input request")
        request = copy.deepcopy(expected_request)
        control = request.get("kind") in RECOVERY_KINDS
        if control:
            validate_control_request(request)
        else:
            self._validate_stored_request(request)
            if request["kind"] not in {"action", "key", "direct", "resume"}:
                raise ControlError("Delivery proof requires an admitted input")
        try:
            exact_id = str(uuid.UUID(request["id"])) == request["id"]
        except (ValueError, TypeError, AttributeError):
            exact_id = False
        if (len(json.dumps(request).encode()) > MAX_REQUEST
                or not exact_id
                or type(expected_controller_boot_id) is not str or not expected_controller_boot_id
                or any(type(value) is not int or value < 0 for value in
                       (expected_operator_generation, expected_generation, expected_takeover_generation))
                or type(deadline_monotonic) not in (int, float) or not math.isfinite(deadline_monotonic)):
            raise ControlError("Malformed delivery-proof binding")
        key = control, request["id"]
        def guard():
            with self.data_lock:
                unknowns = self.control_unknown_outcomes if control else self.unknown_outcomes
                if (self.closed or self._command_work or self._mission_lease is not None
                        or not self.pause_requested or self.state is None
                        or expected_controller_boot_id != self.authority["controller_boot_id"]
                        or request["authority"]["controller_boot_id"] != expected_controller_boot_id
                        or self.operator_pause_generation != expected_operator_generation
                        or self.pause_generation != expected_generation
                        or not control and request["takeover_generation"] != expected_takeover_generation
                        or self.state["session"] != request["session"]
                        or self.state["takeover_generation"] != expected_takeover_generation
                        or not any(item["request"] == request for item in unknowns)
                        or any(pending is not None and pending != request
                               for pending in (self.pending, self.control_pending))):
                    raise ControlError("Delivery proof crossed its original unknown/Pause/controller custody")
                if time.monotonic() >= deadline_monotonic:
                    raise ControlError("Original delivery-proof deadline exhausted")
        if not self.command_lock.acquire(blocking=False):
            raise ControlError("Command writer is active")
        try:
            if not self.control_lock.acquire(blocking=False):
                raise ControlError("Recovery writer is active")
            try:
                guard()
                cached = self._mission_delivery_evidence.get(key)
                if cached is not None:
                    guard()
                    return copy.deepcopy(cached)
                admission = self.control_admissions if control else self.admissions
                if read_json(admission / f'{request["id"]}.json') != request:
                    raise ControlError("Delivery proof lacks its exact durable admission")
                end = min(deadline_monotonic, started + 0.25)
                while True:
                    guard()
                    if time.monotonic() >= end:
                        return None
                    retired = self._retired_mission_inputs.get(key)
                    proof = None
                    if retired is not None:
                        path, original = retired
                        if original != request or read_json(path) != request:
                            raise ControlError("Retired inbox differs from its exact admitted input")
                        proof = {"basis": "unclaimed_retirement", "request": request,
                                 "result": None, "retirement": path.name}
                    else:
                        response = read_json(self.bridge / ("control-response.json" if control else "response.json"))
                        if response is not None and response.get("id") == request["id"]:
                            if control:
                                with self.data_lock:
                                    correlated = self._validate_admitted_control_response(response)
                                terminal = correlated == request and response["status"] in CONTROL_TERMINAL
                                native = response["state"]
                            else:
                                validate_state(response, request["id"])
                                terminal = response["status"] in {"ready", "rejected"}
                                native = response
                            if terminal:
                                if (native["session"] != request["session"]
                                        or native["takeover_generation"] != expected_takeover_generation
                                        or not control and (native["revision"] < request["revision"]
                                            or response["status"] == "ready" and native["revision"] == request["revision"])):
                                    raise ControlError("Terminal delivery evidence changed session/takeover or regressed revision")
                                proof = {"basis": "terminal_response", "request": request,
                                         "result": response, "retirement": None}
                    guard()
                    received = time.monotonic()
                    if received >= end:
                        return None  # Filesystem delay cannot earn late proof credit.
                    if proof is not None:
                        proof.update(received_monotonic=received, collection_started_monotonic=started,
                                     collection_deadline_monotonic=end, grants_authority=False)
                        self._mission_delivery_evidence[key] = copy.deepcopy(proof)
                        while len(self._mission_delivery_evidence) > 60:
                            self._mission_delivery_evidence.pop(next(iter(self._mission_delivery_evidence)))
                        return copy.deepcopy(proof)
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        return None
                    time.sleep(min(0.01, remaining))
            finally:
                self.control_lock.release()
        finally:
            self.command_lock.release()

    def _record(self, request: dict[str, Any], outcome: dict[str, Any], *, recent: bool = True) -> None:
        event = {"timestamp_ms": int(time.time() * 1000), "request": request,
                 "outcome": outcome}
        if recent:
            with self.data_lock:
                self.events.append(event)
                self.events = self.events[-60:]
        with self._journal_lock:
            with self.journal.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

    def _accept(self, response: dict[str, Any], *, known_request_id: str | None = None,
                known_control_id: str | None = None,
                historical: bool = False) -> None:
        def newer_capture(candidate: dict, previous: dict) -> bool:
            if candidate["session"] == previous["session"]:
                if candidate["revision"] != previous["revision"]:
                    return candidate["revision"] > previous["revision"]
                if candidate["timestamp_ms"] == previous["timestamp_ms"]:
                    # Native frame counters order distinct captures minted in
                    # one millisecond. This is bridge ordering, not game time,
                    # image equivalence, receipt freshness or input authority.
                    pattern = r"frame-" + re.escape(candidate["session"]) + r"-([1-9][0-9]{0,19})\.png"
                    first = re.fullmatch(pattern, candidate["frame"])
                    second = re.fullmatch(pattern, previous["frame"])
                    return bool(first and second and int(first[1]) > int(second[1]))
            return candidate["timestamp_ms"] > previous["timestamp_ms"]

        if historical:
            # A terminal ACK is evidence about its request, not a current-screen
            # promotion. Prefer a newer atomic capture even across session exit.
            current = read_json(self.bridge / "state.json")
            if current is not None:
                validate_state(current)
                if newer_capture(current, response):
                    response = current
        with self.data_lock:
            if historical and self.state is not None:
                if (self.state["session"] == response["session"] and self.state["revision"] > response["revision"]
                        or self.state["session"] == response["session"]
                        and self.state["revision"] == response["revision"] and self.state["status"] == "ready"
                        and self.state["frame"] != response["frame"]
                        and not newer_capture(response, self.state)
                        or self.state["session"] != response["session"]
                        and self.state["timestamp_ms"] >= response["timestamp_ms"]):
                    return
            changed_session = self.state is not None and response["session"] != self.state["session"]
            takeover = self.state is not None and (
                response["takeover_generation"] != self.state["takeover_generation"] or response["paused"] and
                response["boundary"]["control_generation"] != self.state["boundary"]["control_generation"])
            if (self.state is not None and not changed_session
                    and response["takeover_generation"] < self.state["takeover_generation"]):
                raise ControlError("Native takeover generation regressed within a session")
            if changed_session or takeover or (response["paused"] and self._mission_lease is not None):
                self._revoke()
                if changed_session or takeover:
                    self.frozen = True
                    self.pause_requested = True
                    self._pause_file()
                    if self.pending is not None and self.pending["id"] != known_request_id:
                        self._unknown(self.pending, "native session changed; old-world outcome remains unknown")
                    if self.control_pending is not None and self.control_pending["id"] != known_control_id:
                        self._control_unknown(self.control_pending, "native session changed")
            if (self.state is None or (self.state["session"], self.state["frame"]) !=
                    (response["session"], response["frame"])):
                self._state_received_monotonic = time.monotonic()
            self.state = copy.deepcopy(response)
            if response["paused"]:
                self.pause_requested = True
            if response["pause_origin"] == "fault":
                self.frozen = True
                self.pause_requested = True
                self._mission_lease = None
                self._pause_file()

    def observation_snapshot(self) -> tuple[dict[str, Any] | None, float | None]:
        """Atomic observation and original receipt clock; reads never renew age."""
        with self.data_lock:
            return copy.deepcopy(self.state), self._state_received_monotonic

    def _exchange(self, kind: str, timeout: float, *, generation: int | None = None,
                  lease: MissionLease | None = None, deadline_monotonic: float | None = None,
                  receipt: dict[str, Any] | None = None,
                  observation_receipt: dict[str, float] | None = None,
                  unpublished_refusal: Callable[[], str | None] | None = None, **payload: Any) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        started = time.monotonic()
        if deadline_monotonic is not None:
            timeout = min(timeout, deadline_monotonic - started)
            if timeout <= 0:
                if unpublished_refusal is not None:
                    self._expired_before_publication("Original dispatch deadline expired before publication", unpublished_refusal)
                return {"status": "controller_error", "error": "Original dispatch deadline expired before publication"}
        # Both clocks describe the original exchange allowance. Sampling wall
        # first makes conversion conservative if scheduling intervenes; adding
        # a full timeout to this later sample would renew the native budget.
        wall_sample = time.time()
        remaining = started + timeout - time.monotonic()
        if remaining <= 0:
            if unpublished_refusal is not None:
                self._expired_before_publication("Original dispatch deadline expired before publication", unpublished_refusal)
            return {"status": "controller_error", "error": "Original dispatch deadline expired before publication"}
        request = {"protocol": 6, "id": request_id, "kind": kind,
                   "deadline_ms": int((wall_sample + remaining) * 1000), **payload}
        if kind not in {"observe", "pause"}:
            if self.state is None:
                raise ControlError("No observation; observe first")
            request.setdefault("session", self.state["session"])
            request.setdefault("revision", self.state["revision"])
            request.setdefault("boundary_id", self.state["boundary"]["id"])
            request.setdefault("takeover_generation", self.state["takeover_generation"])
            request.setdefault("frame", self.state["frame"])
            request.setdefault("require_exact_frame", False)
        if len(json.dumps(request).encode()) > MAX_REQUEST:
            raise ControlError("Request exceeds 4096 bytes")
        terminal_response = None
        terminal_received = False
        admitted_input = False
        unpublished_cleanup_failed = False
        published = False
        try:
            if self.closed:
                raise ControlError("Controller is shutting down")
            if (self.bridge / "request.json").exists():
                raise ControlError("Unresolved bridge request; observe to reconcile")
            with self.data_lock:
                if kind in {"key", "action", "direct", "resume"}:
                    self._check_owner(lease, generation)
                    if self.control_lock.locked() or self.control_pending is not None:
                        raise ControlError("Recovery is pending; ordinary input is blocked")
                    if generation is None or generation != self.pause_generation:
                        raise ControlError("Admission superseded by pause or takeover")
                    if self.closed or (kind != "resume" and self.pause_requested):
                        raise ControlError("Input authority revoked")
                    request["authority"] = self.authority.copy()
                    if len(json.dumps(request).encode()) > MAX_REQUEST:
                        raise ControlError("Request exceeds 4096 bytes")
                    # Survives a host crash after native dispatch removes claimed.json.
                    # Uncertain admissions are retained across reconciliation and restart.
                    atomic_json(self.admissions / f"{request_id}.json", request)
                    admitted_input = True
                    if receipt is not None:
                        receipt["request"] = copy.deepcopy(request)
                        self._record({"kind": "mission_admission", "logical_action_id": receipt["logical_action_id"]},
                                     {"request": copy.deepcopy(request)})
                if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                    self._expired_before_publication("Original dispatch deadline expired before publication", unpublished_refusal)
                if self.pending is not None:
                    self._unknown(self.pending, "reconciliation does not establish original outcome")
                def before_publish() -> None:
                    if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                        self._expired_before_publication("Original dispatch deadline expired at publication", unpublished_refusal)

                def on_publish() -> None:
                    nonlocal published
                    published = True
                    if receipt is not None:
                        receipt["published"] = True

                atomic_json(self.bridge / "request.json", request,
                            before_publish=before_publish, on_publish=on_publish)
                self.pending = request
            while time.monotonic() - started < timeout:
                if self.closed:
                    raise ControlError("Controller stopped; request will not be replayed")
                response = read_json(self.bridge / "response.json")
                # Prior responses are expected; only the exact UUID can finish this command.
                if response is not None and response.get("id") == request_id:
                    received_monotonic = time.monotonic()
                    validate_state(response, request_id)
                    if observation_receipt is not None and response["status"] != "dispatched":
                        observation_receipt["received_monotonic"] = received_monotonic
                    # A structurally valid correlated terminal closes transport
                    # waiting even when custody/session checks cannot attribute
                    # its effect. Preserve that unknown action, then permit a
                    # deliberate Observe without waiting out a completed request.
                    terminal_received = response["status"] != "dispatched"
                    if (response["status"] == "ready" and kind in {"key", "action", "direct", "resume"}
                            and (response["session"] != request["session"]
                                 or response["revision"] <= request["revision"])):
                        raise ControlError("Ready response has stale or changed session/revision")
                    if terminal_received:
                        terminal_response = copy.deepcopy(response)
                        if receipt is not None:
                            receipt["received_monotonic"] = received_monotonic
                            receipt["result"] = copy.deepcopy(response)
                    terminal_input = terminal_received and kind in {"key", "action", "direct", "resume"}
                    self._accept(response, known_request_id=request_id if terminal_input else None,
                                 historical=terminal_input)
                    if terminal_received:
                        with self.data_lock:
                            self.pending = None
                            self.latency_ms = round((time.monotonic() - started) * 1000)
                        self._record(request, response)
                        (self.admissions / f"{request_id}.json").unlink(missing_ok=True)
                        return response
                time.sleep(0.015)
            with self.data_lock:
                self._revoke()
                self._unknown(request, "deadline reached")
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
            if terminal_response is not None:
                self._mission_processing_failure(receipt, exc)
                with self.data_lock:
                    self.pending = None
                return terminal_response
            if isinstance(exc, MissionInputRefusal) and not published:
                try:
                    if admitted_input:
                        (self.admissions / f"{request_id}.json").unlink(missing_ok=True)
                except OSError as cleanup_error:
                    unpublished_cleanup_failed = True
                    exc = cleanup_error
                else:
                    return {"status": exc.status, "id": request_id, "error": str(exc)}
            with self.data_lock:
                self._revoke()
                if admitted_input and published:
                    self._unknown(request, str(exc))
                elif admitted_input and not unpublished_cleanup_failed:
                    (self.admissions / f"{request_id}.json").unlink(missing_ok=True)
                if terminal_received:
                    self.pending = None
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
        """Public operator Pause; no request field can select an internal origin."""
        return self._pause_input(operator=True)

    def stop_input(self) -> dict[str, Any]:
        """Trusted runtime stop, never evidence that the operator requested Pause."""
        return self._pause_input(operator=False)

    def retire_mission_exit(self, *, expected_controller_boot_id: str,
                            expected_operator_generation: int, expected_generation: int,
                            expected_request: dict[str, Any] | None, launch_id: str,
                            exit_request_id: str, returncode: int) -> dict[str, Any]:
        """Retire host pending state after runtime attests an owned normal exit.

        Runtime must prove its exact child and admitted final-input phase. This
        trusted Python API checks only controller custody; it cannot establish a
        save or native input outcome and is unavailable through command JSON.
        """
        for name, value in (("launch_id", launch_id), ("exit_request_id", exit_request_id)):
            if type(value) is not str or re.fullmatch(r"[\x21-\x7e]{1,128}", value) is None:
                raise ControlError(f"Exit {name} requires 1 to 128 printable ASCII characters")
        if type(returncode) is not int or returncode != 0:
            raise ControlError("Exit retirement requires a normal zero return code")
        if (type(expected_controller_boot_id) is not str or not expected_controller_boot_id
                or type(expected_operator_generation) is not int or expected_operator_generation < 0
                or type(expected_generation) is not int or expected_generation < 0
                or expected_request is not None and type(expected_request) is not dict):
            raise ControlError("Malformed exit retirement binding")
        if not self.command_lock.acquire(blocking=False):
            raise ControlError("Command writer is active")
        try:
            if not self.control_lock.acquire(blocking=False):
                raise ControlError("Recovery writer is active")
            try:
                with self.data_lock:
                    if (self.closed or expected_controller_boot_id != self.authority["controller_boot_id"]
                            or expected_operator_generation != self.operator_pause_generation
                            or expected_generation != self.pause_generation):
                        raise ControlError("Exit retirement superseded by controller change or Pause")
                    if (self._mission_lease is not None or self._command_work
                            or self.control_pending is not None):
                        raise ControlError("Mission or command/recovery work is active")
                    if not self.pause_requested or not self.frozen:
                        raise ControlError("Exit retirement requires a paused, frozen controller")
                    if any(os.path.lexists(self.bridge / name) for name in
                           ("request.json", "claimed.json", "control.json", "control-claimed.json")):
                        raise ControlError("Native or recovery inbox is not empty")
                    if self.pending != expected_request:
                        raise ControlError("Exit retirement requires the exact pending request")
                    if expected_request is not None:
                        self._validate_stored_request(expected_request)
                        if (expected_request["kind"] not in {"action", "key", "direct"}
                                or expected_request["deadline_ms"] > int(time.time() * 1000)):
                            raise ControlError("Exit retirement requires an expired ordinary input")
                        if not any(item["request"] == expected_request for item in self.unknown_outcomes):
                            raise ControlError("Exit retirement requires the exact existing unknown outcome")
                    receipt = {"launch_id": launch_id, "exit_request_id": exit_request_id,
                               "native_request_id": None if expected_request is None else expected_request["id"],
                               "returncode": 0, "retired_pending": expected_request is not None,
                               "grants_authority": False}
                    self._revoke()
                    self._pause_file()
                    # Durable evidence must precede removal of the in-memory gate.
                    self._record({"kind": "mission_exit_retirement"}, receipt)
                    self.pending = None
                    return receipt
            finally:
                self.control_lock.release()
        finally:
            self.command_lock.release()

    def _pause_input(self, *, operator: bool) -> dict[str, Any]:
        # This path deliberately never waits for the command lock or the game.
        with self.data_lock:
            if operator:
                self.operator_pause_generation += 1
            self.pause_requested = True
            self._revoke()
            self._pause_file()
            result = {"status": "pause_requested", "error": "",
                      "detail": "Pause sentinel set; an already dispatched action cannot be undone"}
            self.last_result = result
        self._record({"kind": "pause" if operator else "runtime_stop"}, result)
        return result

    def acquire_mission(self, mission_id: str, epoch: int, actor_id: str, *, operation: str,
                        expected_session: str, expected_revision: int,
                        expected_boundary_id: str, replace: MissionLease | None = None,
                        refuse_changed_context: bool = False) -> MissionLease:
        """Claim one admitted operation at a supported boundary; sends no input."""
        if operation not in ("navigate", "interaction", "lifecycle"):
            raise ControlError("Unknown mission operation")
        for name, value in (("mission_id", mission_id), ("actor_id", actor_id)):
            if not isinstance(value, str) or not value.strip() or len(value) > 160:
                raise ControlError(f"Run {name} must be nonempty text of at most 160 characters")
        if type(epoch) is not int or epoch < 0:
            raise ControlError("Mission epoch must be a nonnegative integer")
        if not self.command_lock.acquire(blocking=False):
            raise ControlError("Command writer is active")
        try:
            if not self.control_lock.acquire(blocking=False):
                raise ControlError("Recovery writer is active")
            try:
                with self.data_lock:
                    if self._command_work:
                        raise ControlError("Command work is active or queued")
                    if replace is not None:
                        self._check_owner(replace, self.pause_generation)
                        if (replace.mission_id, replace.epoch, replace.actor_id, replace.session) != (
                                mission_id, epoch, actor_id, expected_session):
                            raise ControlError("Operation replacement requires the same mission, epoch, actor and session")
                    elif self._mission_lease is not None:
                        raise ControlError("A run already owns this controller")
                    if self.closed or self.frozen or self.pause_requested or (self.bridge / "pause").exists():
                        raise ControlError("Run acquisition requires a reconciled, resumed controller")
                    if (self.pending is not None or self.control_pending is not None
                            or any((self.bridge / name).exists() for name in
                                   ("request.json", "claimed.json", "control.json", "control-claimed.json"))):
                        raise ControlError("Native or recovery work is pending")
                    if self.state is None:
                        raise ControlError("Run acquisition requires a current observation")
                    changed_context = (refuse_changed_context and replace is not None and operation != "lifecycle"
                        and self.state["session"] == expected_session
                        and (self.state["revision"] != expected_revision
                             or self.state["boundary"]["id"] != expected_boundary_id))
                    self._mission_frame(self.state, operation, direct=changed_context)
                    if changed_context:
                        # No revocation/rotation occurred. Runtime must still prove
                        # complete source/custody/resource health after locks release.
                        raise MissionInputRefusal("Semantic applicability changed during rotation; Observe and choose again",
                                                  status="rejected")
                    self._expect(self.state, expected_session, expected_revision)
                    self._expect_boundary(self.state, expected_boundary_id)
                    self._revoke()
                    lease = MissionLease(mission_id, epoch, actor_id, self.state["session"],
                                         self.pause_generation, self.state["takeover_generation"], operation)
                    self._mission_lease = lease
                    return lease
            finally:
                self.control_lock.release()
        finally:
            self.command_lock.release()

    @staticmethod
    def _native_progression(before: dict | None, after: dict | None) -> None:
        """Keep archive integrity failures fatal at controller refusal fences."""
        if before is None or after is None:
            raise ControlError("Native progression requires both actual samples")
        try:
            validate_native_progression(before, after, now_timestamp_ms=int(time.time() * 1000))
        except EvidenceError as exc:
            raise ControlError(str(exc)) from exc

    @staticmethod
    def _mission_frame(state: dict[str, Any], operation: str, *, direct: bool = False) -> None:
        validate_state(state)
        age = int(time.time() * 1000) - state["timestamp_ms"]
        boundary = state["boundary"]["kind"]
        supported = boundary == "normal_play" and state["in_game"] and state["scene"] is not None
        if operation in ("interaction", "lifecycle") and boundary == "menu": supported = True
        if direct:
            supported = boundary in INPUT_BOUNDARIES and state["boundary"]["input_receiver"]
        if (state["status"] != "ready" or state["error"] or state["paused"] or not supported
                or not state["frame_ok"] or not state["frame"] or not -1000 <= age <= 3000):
            raise ControlError("Mission input requires a fresh successful boundary eligible for its operation")

    def _check_owner(self, lease: MissionLease | None, generation: int | None) -> None:
        """Call under data_lock at each admission/commit boundary."""
        if lease is None:
            if self._mission_lease is not None:
                raise ControlError("A run owns input; Pause or release it before external input")
            return
        if (lease is not self._mission_lease or generation != self.pause_generation
                or self.state is None or lease.session != self.state["session"]
                or lease.pause_generation != self.pause_generation
                or lease.takeover_generation != self.state["takeover_generation"]
                or self.closed or self.frozen or self.pause_requested):
            raise ControlError("Run lease is stale or input authority was revoked")

    def execute_mission(self, lease: MissionLease, *, kind: str, value: str | dict, expected_session: str,
                        expected_revision: int, expected_boundary_id: str, logical_action_id: str,
                        deadline_monotonic: float, timeout: float | None = None,
                        expected_image_sha256: str | None = None,
                        preflight: Callable[[dict[str, Any], float], None] | None = None,
                        unpublished_refusal: Callable[[], str | None] | None = None) -> dict[str, Any]:
        """One ordinary input with its exact logical/native receipt."""
        receipt = {"logical_action_id": logical_action_id, "request": None, "result": None,
                   "published": False, "received_monotonic": None, "preflight": None, "processing_error": None}
        preflight_failed = False
        if (type(logical_action_id) is not str or not 1 <= len(logical_action_id) <= 128
                or type(deadline_monotonic) not in (int, float)
                or not 0 <= deadline_monotonic <= 1e12 or lease is None or kind not in ("action", "key", "direct")):
            receipt["result"] = {"status": "controller_error", "error": "Invalid mission identity, kind, deadline or lease"}
        else:
            try:
                receipt["result"] = self._execute(kind, timeout,
                    {"input" if kind == "direct" else kind: value, "expected_session": expected_session,
                     "expected_revision": expected_revision, "expected_boundary_id": expected_boundary_id}, lease,
                    deadline_monotonic=deadline_monotonic, receipt=receipt,
                    expected_image_sha256=expected_image_sha256, preflight=preflight,
                    unpublished_refusal=unpublished_refusal)
            except _MissionPreflightFailure as exc:
                preflight_failed = True
                self._stop_mission_preflight(receipt, exc)
        return self._finish_mission_receipt(receipt, preflight_failed)

    def _stop_mission_preflight(self, receipt: dict[str, Any], exc: ControlError) -> None:
        receipt["result"] = {"status": "controller_error", "error": str(exc)}
        # Memory authority was stopped under the command lock. Each durable
        # stop is independent: disk failure cannot skip Pause.
        with self.data_lock:
            for label, operation in (("authority revocation", self._revoke), ("Pause sentinel", self._pause_file)):
                try:
                    operation()
                except OSError as persistence_error:
                    receipt["result"]["error"] += f"; {label} failed: {persistence_error}"

    def _mission_processing_failure(self, receipt: dict[str, Any] | None, exc: Exception) -> None:
        diagnostic = str(exc)[:1024]
        if receipt is not None:
            prior = receipt["processing_error"]
            receipt["processing_error"] = (f"{prior}; {diagnostic}" if prior else diagnostic)[:1024]
        with self.data_lock:
            self.frozen = True
            self.pause_requested = True
            self._mission_lease = None
            self.transport_error = diagnostic
            for operation in (self._revoke, self._pause_file):
                try:
                    operation()
                except (ControlError, OSError):
                    # Independent stop barriers; failure cannot discard a known ACK.
                    pass

    def _finish_mission_receipt(self, receipt: dict[str, Any], preflight_failed: bool) -> dict[str, Any]:
        logical_action_id = receipt["logical_action_id"]
        if type(logical_action_id) is str:
            try:
                self._record({"kind": "mission_receipt", "logical_action_id": logical_action_id}, receipt)
            except (ControlError, OSError) as exc:
                if receipt["received_monotonic"] is not None:
                    self._mission_processing_failure(receipt, exc)
                elif preflight_failed:
                    receipt["result"]["error"] += f"; mission receipt persistence failed: {exc}"
                else:
                    self._mission_processing_failure(receipt, exc)
                    raise
        if preflight_failed:
            with self.data_lock:
                self.last_result = receipt["result"]
                self.transport_error = receipt["result"]["error"]
        return receipt

    def release_mission(self, lease: MissionLease) -> dict[str, Any]:
        with self.data_lock:
            if lease is None or lease is not self._mission_lease:
                raise ControlError("Run lease is stale; cannot release another owner")
            return self.stop_input()

    def resume_mission(self, *, expected_generation: int, expected_operator_generation: int,
                       expected_controller_boot_id: str, expected_session: str,
                       expected_revision: int, expected_boundary_id: str,
                       expected_takeover_generation: int, expected_pause_origin: str,
                       logical_action_id: str, deadline_monotonic: float, timeout: float | None = None,
                       expected_image_sha256: str | None = None,
                       preflight: Callable[[dict[str, Any], float], None] | None = None) -> dict[str, Any]:
        """CAS for runtime-admitted bootstrap/lifecycle/recovery, never a lease resume.

        Runtime must establish the admitted phase and cause. Exact observed values
        prevent a newer host/human event from becoming implicit permission while
        waiting for the command writer. Public command JSON cannot call this API.
        """
        binding = {"session": expected_session, "revision": expected_revision,
                   "boundary_id": expected_boundary_id, "takeover_generation": expected_takeover_generation,
                   "pause_origin": expected_pause_origin, "operator_pause_generation": expected_operator_generation,
                   "controller_boot_id": expected_controller_boot_id}
        receipt = {"logical_action_id": logical_action_id, "request": None, "result": None,
                   "published": False, "received_monotonic": None, "preflight": None, "processing_error": None}
        preflight_failed = False
        if (type(logical_action_id) is not str or not 1 <= len(logical_action_id) <= 128
                or type(deadline_monotonic) not in (int, float) or not 0 <= deadline_monotonic <= 1e12):
            receipt["result"] = {"status": "controller_error", "error": "Invalid mission identity or deadline"}
        elif (type(expected_generation) is not int or expected_generation < 0
                or type(expected_operator_generation) is not int or expected_operator_generation < 0
                or type(expected_controller_boot_id) is not str or not expected_controller_boot_id
                or type(expected_revision) is not int or expected_revision < 0
                or type(expected_takeover_generation) is not int or expected_takeover_generation < 0
                or not isinstance(expected_session, str) or not expected_session
                or not isinstance(expected_boundary_id, str) or not expected_boundary_id
                or type(expected_pause_origin) is not str or expected_pause_origin not in PAUSE_ORIGINS):
            receipt["result"] = {"status": "controller_error", "error": "Malformed mission continuation binding"}
        else:
            try:
                receipt["result"] = self._execute("resume", timeout, {}, None, expected_generation=expected_generation,
                    resume_binding=binding, deadline_monotonic=deadline_monotonic, receipt=receipt,
                    expected_image_sha256=expected_image_sha256, preflight=preflight)
            except _MissionPreflightFailure as exc:
                preflight_failed = True
                self._stop_mission_preflight(receipt, exc)
        return self._finish_mission_receipt(receipt, preflight_failed)

    def _check_mission_resume(self, observed: dict[str, Any] | None,
                              binding: dict[str, Any], generation: int) -> None:
        """Trusted host CAS under data_lock; native keeps its existing commit fences."""
        self._check_owner(None, generation)
        if (self.closed or generation != self.pause_generation
                or binding["operator_pause_generation"] != self.operator_pause_generation
                or binding["controller_boot_id"] != self.authority["controller_boot_id"]):
            raise ControlError("Mission continuation superseded by host Pause or takeover")
        if (self.control_lock.locked() or self.control_pending is not None or self.pending is not None
                or any((self.bridge / name).exists() for name in
                       ("request.json", "claimed.json", "control.json", "control-claimed.json"))):
            raise ControlError("Native or recovery work is pending for mission Resume")
        if observed is None:
            raise ControlError("Mission Resume requires a current paused observation")
        validate_state(observed)
        self._expect(observed, binding["session"], binding["revision"])
        self._expect_boundary(observed, binding["boundary_id"])
        if (observed["takeover_generation"] != binding["takeover_generation"]
                or observed["pause_origin"] != binding["pause_origin"]):
            raise ControlError("Mission continuation superseded by a native pause/takeover event")
        age = int(time.time() * 1000) - observed["timestamp_ms"]
        supported = (observed["boundary"]["kind"] == "menu" or
                     observed["boundary"]["kind"] == "normal_play" and observed["in_game"] and observed["scene"] is not None)
        if (observed["status"] != "ready" or observed["error"] or not observed["paused"] or not supported
                or not observed["frame_ok"] or not observed["frame"] or not -1000 <= age <= 3000):
            raise ControlError("Mission Resume requires a fresh successful paused normal-play or supported menu frame")

    def _pause_snapshot(self) -> tuple[int, int, int, int, int] | None:
        try:
            value = (self.bridge / "pause").stat()
        except FileNotFoundError:
            return None
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

    @contextmanager
    def _command_slot(self, deadline_monotonic: float | None, *, allow_expired: bool = False):
        if deadline_monotonic is None:
            with self.command_lock:
                yield
            return
        remaining = deadline_monotonic - time.monotonic()
        acquired = (self.command_lock.acquire(blocking=False) if remaining <= 0 and allow_expired else
                    remaining > 0 and self.command_lock.acquire(timeout=min(MAX_WAIT, remaining)))
        if not acquired:
            raise ControlError("Original dispatch deadline expired or command writer unavailable")
        try:
            yield
        finally:
            self.command_lock.release()

    def observe_mission(self, *, deadline_monotonic: float | None, timeout: float | None = None) -> tuple[dict, float | None]:
        """Passive read and its exact receipt; later status polling cannot renew it."""
        receipt = {"received_monotonic": None}
        result = self._execute("observe", timeout, {}, None, deadline_monotonic=deadline_monotonic, receipt=receipt)
        return result, receipt["received_monotonic"]

    def execute(self, kind: str, *, timeout: float | None = None,
                expected_generation: int | None = None, **payload: Any) -> dict[str, Any]:
        """Trusted ingress may bind its original host generation; JSON cannot set it."""
        return self._execute(kind, timeout, payload, None, expected_generation=expected_generation)

    def _execute(self, kind: str, timeout: float | None, payload: dict[str, Any],
                 lease: MissionLease | None, *, deadline_monotonic: float | None = None,
                 receipt: dict[str, Any] | None = None, expected_generation: int | None = None,
                 resume_binding: dict[str, Any] | None = None,
                 expected_image_sha256: str | None = None,
                 preflight: Callable[[dict[str, Any], float], None] | None = None,
                 unpublished_refusal: Callable[[], str | None] | None = None) -> dict[str, Any]:
        wait = self.timeout if timeout is None else timeout
        admitted = False
        with self.data_lock:
            admitted_generation = self.pause_generation
        try:
            if deadline_monotonic is not None and (type(deadline_monotonic) not in (int, float)
                    or not 0 <= deadline_monotonic <= 1e12):
                raise ControlError("Original deadline must be finite, nonbool and nonnegative")
            if expected_image_sha256 is not None and (type(expected_image_sha256) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", expected_image_sha256) is None):
                raise ControlError("Expected image hash must be exactly 64 lowercase hexadecimal characters")
            if preflight is not None and not callable(preflight):
                raise ControlError("Mission preflight must be a trusted Python callback")
            if unpublished_refusal is not None and (not callable(unpublished_refusal) or lease is None
                    or lease.operation == "lifecycle" or kind not in {"key", "action", "direct"}):
                raise ControlError("Unpublished refusal classifier requires trusted ordinary mission input")
            classifier = unpublished_refusal
            if classifier is not None:
                def unpublished_refusal() -> str | None:
                    return self._classify_unpublished_refusal(classifier, lease, admitted_generation, kind, receipt)
            if expected_generation is not None and (type(expected_generation) is not int or expected_generation < 0):
                raise ControlError("Expected host generation requires a nonnegative integer")
            if expected_generation is not None and expected_generation != admitted_generation:
                raise ControlError("Mission continuation superseded by host Pause or takeover")
            if self.closed:
                raise ControlError("Controller is closed")
            if not isinstance(kind, str) or kind not in {"observe", "pause", "resume", "goal", "key", "action", "walk", "direct"}:
                raise ControlError("Unknown command")
            if set(payload) - {"key", "action", "direction", "steps", "text", "input", "expected_session", "expected_revision", "expected_boundary_id"}:
                raise ControlError("Unknown command fields")
            if kind == "direct":
                if lease is None or lease.operation not in ("interaction", "lifecycle"):
                    raise ControlError("Direct input requires a mission interaction or lifecycle lease")
                if expected_image_sha256 is not None:
                    raise ControlError("Direct input requires expected_image_sha256=None")
                try:
                    payload["input"] = validate_input(payload.get("input"))
                except ContractError as exc:
                    raise ControlError(f"Invalid direct input: {exc}") from exc
            if kind == "pause":
                return self.pause()
            if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not 0 < wait <= MAX_WAIT:
                raise ControlError("Timeout must be greater than 0 and at most 15 seconds")
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
            with self.data_lock:
                if kind != "observe":
                    self._check_owner(lease, admitted_generation)
                self._command_work += 1
                admitted = True
            with self._command_slot(deadline_monotonic, allow_expired=unpublished_refusal is not None):
                if self.closed:
                    raise ControlError("Controller is closed")
                with self.data_lock:
                    if kind != "observe":
                        self._check_owner(lease, admitted_generation)
                        if kind == "walk" and admitted_generation != self.pause_generation:
                            raise ControlError("Admission superseded by pause or takeover")
                if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                    self._expired_before_publication("Original dispatch deadline expired in command queue", unpublished_refusal)
                if kind == "walk":
                    result = self._walk(payload.get("direction"), payload.get("steps"), wait,
                                        payload.get("expected_session"), payload.get("expected_revision"),
                                        admitted_generation)
                else:
                    result = self._command(kind, wait, payload, admitted_generation, lease,
                                           deadline_monotonic=deadline_monotonic, receipt=receipt, resume_binding=resume_binding,
                                           expected_image_sha256=expected_image_sha256, preflight=preflight,
                                           unpublished_refusal=unpublished_refusal)
                with self.data_lock:
                    self.last_result = result
                return result
        except MissionInputRefusal as exc:
            return {"status": exc.status, "error": str(exc)}
        except _MissionPreflightFailure:
            # The mission boundary preserves its determinate unpublished receipt
            # even when persisting this diagnostic would fail again.
            raise
        except (ControlError, OSError) as exc:
            if lease is not None and admitted:
                with self.data_lock:
                    if self._mission_lease is lease:
                        self.frozen = True
                        self.pause_requested = True
                        self._mission_lease = None
                        self.transport_error = str(exc)
                        raise _MissionPreflightFailure(str(exc)) from exc
            result = {"status": "controller_error", "error": str(exc)}
            with self.data_lock:
                self.last_result = result
            # Invalid ingress can contain arbitrary Python objects, including a
            # leaked capability. Never serialize those into a durable record.
            self._record({"kind": kind if isinstance(kind, str) else "invalid"}, result)
            return result
        finally:
            if admitted:
                with self.data_lock:
                    self._command_work -= 1

    def _command(self, kind: str, timeout: float, payload: dict[str, Any], generation: int,
                 lease: MissionLease | None = None, *, deadline_monotonic: float | None = None,
                 receipt: dict[str, Any] | None = None,
                 resume_binding: dict[str, Any] | None = None,
                 expected_image_sha256: str | None = None,
                 preflight: Callable[[dict[str, Any], float], None] | None = None,
                 unpublished_refusal: Callable[[], str | None] | None = None) -> dict[str, Any]:
        with self.data_lock:
            if kind != "observe":
                self._check_owner(lease, generation)
            if kind in {"key", "action", "direct", "resume"} and (self.control_lock.locked() or self.control_pending is not None):
                raise ControlError("Recovery is pending; ordinary input is blocked")
            if kind in {"key", "action", "direct", "resume"} and generation != self.pause_generation:
                return {"status": "pause_requested", "error": "Queued resume superseded by a later pause"}
        if kind != "observe":
            with self.data_lock:
                if self.frozen:
                    raise ControlError("Control is frozen; explicitly observe to reconcile first")
                if kind != "resume" and self.pause_requested:
                    raise ControlError("Paused; explicitly resume before sending inputs")
        if resume_binding is not None:
            with self.data_lock:
                if (self.pending is not None or any((self.bridge / name).exists() for name in
                        ("request.json", "claimed.json", "control.json", "control-claimed.json"))):
                    raise ControlError("Native or recovery work is pending for mission Resume")
        if kind == "observe":
            # A fresh observe is safe after the prior deadline plus our pause sentinel.
            if self.pending is not None:
                remaining = (self.pending["deadline_ms"] - time.time() * 1000) / 1000
                if remaining > 0:
                    raise ControlError("Prior request deadline has not passed; wait before reconciliation")
                self._pause_file()
            result = self._exchange("observe", timeout, deadline_monotonic=deadline_monotonic, receipt=receipt)
            if result["status"] == "ready":
                self._reconcile_expired_control(result)
                with self.data_lock:
                    self.frozen = False
                    self.transport_error = ""
                self._record({"kind": "reconcile"}, {"status": "ready", "id": result["id"],
                             "detail": "Fresh observe returned at an eligible native input boundary"})
            return result
        # Direct drift preserves custody from the owned entry screen.
        with self.data_lock:
            entry_state = copy.deepcopy(self.state)
            entry_control_generation = entry_state["boundary"]["control_generation"] if entry_state else None
        observation_receipt: dict[str, float] = {}
        observed = self._exchange("observe", timeout, deadline_monotonic=deadline_monotonic,
                                  observation_receipt=observation_receipt, unpublished_refusal=unpublished_refusal)
        if observed["status"] != "ready":
            return observed
        ordinary_input = lease is not None and lease.operation != "lifecycle" and kind in {"key", "action", "direct"}
        if ordinary_input:
            self._native_progression(entry_state, observed)
        context_changed = (ordinary_input and kind != "direct"
            and observed["session"] == payload.get("expected_session")
            and (observed["revision"] != payload.get("expected_revision")
                 or observed["boundary"]["id"] != payload.get("expected_boundary_id")))
        if receipt is not None and (lease is not None or resume_binding is not None):
            receipt["preflight"] = {"observation": copy.deepcopy(observed),
                "received_monotonic": observation_receipt["received_monotonic"],
                "expected_image_sha256": expected_image_sha256}
            if kind == "direct":
                receipt["preflight"]["informing"] = {name: payload.get(name) for name in
                    ("expected_session", "expected_revision", "expected_boundary_id")}
        with self.data_lock:
            self._check_owner(lease, generation)
            if kind in {"key", "action", "direct", "resume"} and generation != self.pause_generation:
                return {"status": "pause_requested", "error": "Resume superseded by a later pause"}
            if lease is not None:
                self._mission_frame(observed, lease.operation, direct=kind == "direct" or context_changed)
        if (observed["boundary"]["kind"] not in INPUT_BOUNDARIES or not observed["frame_ok"]
                or int(time.time() * 1000) - observed["timestamp_ms"] > 3000):
            raise ControlError("Input requires a fresh matching normal-play or supported menu frame")
        if kind != "resume" and (observed["paused"] or self.pause_requested):
            raise ControlError("Native input is paused; explicit resume required")
        if ordinary_input and (not observed["boundary"]["input_receiver"]
                or observed["boundary"]["control_generation"] != entry_control_generation):
            raise ControlError("Ordinary receiver or control custody changed")
        if kind not in {"resume", "direct"} and not context_changed:
            self._expect(observed, payload.get("expected_session"), payload.get("expected_revision"))
        elif kind == "direct":
            if payload.get("expected_session") != observed["session"]:
                raise ControlError("Direct informing session differs from the owned receiver")
        elif resume_binding is not None:
            with self.data_lock:
                self._check_mission_resume(observed, resume_binding, generation)
        if lease is not None:
            if kind != "direct" and not context_changed:
                self._expect_boundary(observed, payload.get("expected_boundary_id"))
            if lease.operation == "navigate":
                if kind != "action" or payload.get("action") not in {"UP", "DOWN", "LEFT", "RIGHT"}:
                    raise ControlError("Navigation lease admits only registered cardinal movement")
                dx, dy = {"UP": (0,-1), "DOWN": (0,1), "LEFT": (-1,0), "RIGHT": (1,0)}[payload["action"]]
                if not context_changed:
                    self._walk_guard(observed, dx, dy)
        if kind == "action" and payload["action"] not in observed["actions"] and not context_changed:
            raise ControlError("Action is not registered in the current input context")
        if (kind == "direct" and payload["input"]["type"] == "click"
                and payload["input"]["geometry"] != observed["frame_geometry"]):
            raise MissionInputRefusal("Click geometry differs from the actual receiver mapping", status="rejected")
        if lease is not None or resume_binding is not None:
            try:
                pause_snapshot = self._pause_snapshot() if resume_binding is not None else None
                if expected_image_sha256 is not None and self._frame_sha256(observed) != expected_image_sha256:
                    raise MissionInputRefusal("Final preflight image differs from the informing image", status="rejected")
                received = observation_receipt["received_monotonic"]
                deferred_refusal = (MissionInputRefusal(
                    "Semantic input no longer matches the current revision or boundary; Observe and choose again", status="rejected")
                    if context_changed else None)
                if preflight is not None:
                    try:
                        preflight(copy.deepcopy(observed), received)
                    except MissionInputRefusal as exc:
                        if lease is None or lease.operation == "lifecycle" or kind == "resume":
                            raise ControlError("Local refusal cannot preserve lifecycle or recovery authority") from exc
                        deferred_refusal = exc
                    except Exception as exc:
                        # A normal storage/capacity/contract failure proves no input
                        # publication. Crashes/BaseException retain durable unknowns.
                        raise ControlError(f"Mission preflight failed: {type(exc).__name__}: {exc}") from exc
                # Ordinary capture churn may be correctable nondelivery, but
                # only after every fatal guard below passes. Never replace its
                # retained frame/receipt. Native validates the original issued
                # capture, clock and metadata; image/spatial choices stay strict.
                exact_capture = (expected_image_sha256 is not None
                    or kind == "direct" and payload["input"]["type"] == "click")
                checked_frame = (observed["frame"] if ordinary_input or not exact_capture
                    else self._preflight_capture(observed))
                with self.data_lock:
                    self._check_owner(lease, generation)
                    if self._command_work != 1:
                        raise ControlError("Exclusive command work changed during preflight")
                    if (self.control_lock.locked() or self.control_pending is not None
                            or self.pending is not None or any((self.bridge / name).exists() for name in
                            ("request.json", "claimed.json", "control.json", "control-claimed.json"))):
                        raise ControlError("Native or recovery work appeared during preflight")
                    if ordinary_input:
                        self._native_progression(observed, self.state)
                        if not same_native_custody(observed, self.state):
                            raise ControlError("Native custody or immutable capture changed during preflight")
                    if not same_native_state(self.state, observed):
                        if not ordinary_input:
                            raise ControlError("Native custody or specialized boundary changed during preflight")
                        self.check_mission_refusal(lease, generation, command_work=1)
                        deferred_refusal = MissionInputRefusal(
                            "Native view advanced during preflight; Observe and choose again", status="rejected")
                    if exact_capture and not ordinary_input and self.state["frame"] != checked_frame:
                        raise ControlError("Native frame changed during specialized preflight")
                    if resume_binding is not None:
                        self._check_mission_resume(observed, resume_binding, generation)
                        if self._pause_snapshot() != pause_snapshot:
                            raise ControlError("Pause sentinel changed during mission Resume preflight")
                    else:
                        if (self.bridge / "pause").exists():
                            raise ControlError("Native boundary or frame changed during preflight")
                        self._mission_frame(observed, lease.operation,
                            direct=kind == "direct" or ordinary_input and deferred_refusal is not None)
                    if not 0 <= time.monotonic() - received <= 3:
                        raise ControlError("Final preflight observation expired")
                    capture_changed = ordinary_input and exact_capture and self.state["frame"] != checked_frame
                    if deferred_refusal is not None or capture_changed:
                        self.check_mission_refusal(lease, generation, command_work=1)
                    if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                        self._expired_before_publication("Original dispatch deadline expired during preflight", unpublished_refusal)
                    if capture_changed:
                        raise MissionInputRefusal(
                            "Native frame identity changed during final preflight; observe and choose a new input", status="rejected")
                    if deferred_refusal is not None:
                        raise deferred_refusal
            except MissionInputRefusal:
                raise
            except (ControlError, OSError) as exc:
                with self.data_lock:
                    self.frozen = True
                    self.pause_requested = True
                    self._mission_lease = None
                    self.transport_error = str(exc)
                raise _MissionPreflightFailure(str(exc)) from exc
        primitive = ({"input": payload["input"]} if kind == "direct" else
                     {kind: payload[kind]} if kind in {"key", "action"} else {})
        result = self._exchange(kind, timeout, generation=generation, lease=lease, session=observed["session"],
                                revision=observed["revision"], boundary_id=observed["boundary"]["id"],
                                takeover_generation=observed["takeover_generation"], deadline_monotonic=deadline_monotonic,
                                frame=observed["frame"], require_exact_frame=kind != "direct" and expected_image_sha256 is not None,
                                receipt=receipt, unpublished_refusal=unpublished_refusal, **primitive)
        if kind == "resume" and result["status"] == "ready":
            with self.data_lock:
                if generation != self.pause_generation:
                    self._pause_file()
                    self.pause_requested = True
                else:
                    self.pause_requested = result["paused"]
        return result

    @staticmethod
    def _expired_before_publication(message: str,
                                    unpublished_refusal: Callable[[], str | None] | None) -> None:
        if unpublished_refusal is not None:
            try:
                reason = unpublished_refusal()
            except Exception as exc:
                raise ControlError(f"Unpublished refusal classification failed: {type(exc).__name__}: {exc}") from exc
            if reason is not None:
                raise MissionInputRefusal(reason)
        raise ControlError(message)

    def check_mission_refusal(self, lease: MissionLease, generation: int, *, command_work: int) -> dict[str, Any]:
        """Read-only common custody fence for a healthy zero-input refusal."""
        with self.data_lock:
            self._check_owner(lease, generation)
            if (self._command_work != command_work or command_work == 0 and self.command_lock.locked()
                    or self.control_lock.locked() or self.control_pending is not None or self.pending is not None
                    or any((self.bridge / name).exists() for name in
                        ("pause", "request.json", "claimed.json", "control.json", "control-claimed.json"))):
                raise ControlError("Competing work or Pause prevents local refusal")
            state = self.state
            validate_state(state)
            if (state["status"] != "ready" or state["error"] or state["paused"]
                    or not state["frame_ok"] or not state["frame"]
                    or state["boundary"]["kind"] not in INPUT_BOUNDARIES
                    or not state["boundary"]["input_receiver"]):
                raise ControlError("Local refusal requires healthy capture and an owned ordinary receiver")
            # Read-only refusal is not a freshness promotion. Explicit Observe
            # may refresh aged evidence; actual publication still checks age.
            return copy.deepcopy(state)

    def _classify_unpublished_refusal(self, classifier: Callable[[], str | None], lease: MissionLease,
                                     generation: int, kind: str, receipt: dict[str, Any] | None) -> str | None:
        """Read-only runtime proof may reenter data_lock, never either writer lock."""
        if receipt is None or receipt["published"]:
            raise ControlError("Local refusal requires a known unpublished mission receipt")
        with self.data_lock:
            preflight = receipt["preflight"]
            observed = copy.deepcopy(preflight["observation"] if preflight else self.state)
            received = preflight["received_monotonic"] if preflight else self._state_received_monotonic

            def fence() -> None:
                self.check_mission_refusal(lease, generation, command_work=1)
                self._native_progression(observed, self.state)
                if not same_native_custody(self.state, observed):
                    raise ControlError("Native custody changed before local refusal")
                self._mission_frame(observed, lease.operation, direct=True)
                if received is None or not 0 <= time.monotonic() - received <= 3:
                    raise ControlError("Final preflight observation expired")

            fence()
            reason = classifier()
            fence()
            return reason

    def _preflight_capture(self, observed: dict) -> str:
        """Retain the exact immutable preflight identity and its original clock.

        Eligible unchanged native heartbeats retain their identity. A different
        identity after retention is a change or expiry, never a silent retarget.
        The caller fences this same filename again before publication.
        """
        current, _ = self.observation_snapshot()
        if not same_native_state(current, observed):
            raise ControlError("Native state changed during preflight")
        if current["frame"] != observed["frame"]:
            raise ControlError("Native frame identity changed during final preflight")
        return observed["frame"]

    def _frame_sha256(self, observed: dict[str, Any]) -> str:
        """Hash only the actual native immutable frame, outside the data lock."""
        frame = observed["frame"]
        if (Path(frame).name != frame or re.fullmatch(
                r"frame-" + re.escape(observed["session"]) + r"-[1-9][0-9]{0,19}\.png", frame) is None):
            raise ControlError("Final preflight frame must be a native session-scoped basename")
        limit = 32 * 1024 * 1024
        fd = os.open(self.bridge / frame, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= limit:
                raise ControlError("Final preflight frame must be a nonempty regular file of at most 32 MiB")
            data = stream.read(limit + 1)
        if not data or len(data) > limit:
            raise ControlError("Final preflight frame exceeds the bounded image size")
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _expect(state: dict[str, Any], session: Any, revision: Any) -> None:
        if not isinstance(session, str) or type(revision) is not int:
            raise ControlError("Gameplay commands require expected_session and expected_revision from observe")
        if session != state["session"] or revision != state["revision"]:
            raise ControlError("Stale session or revision; observe and reconsider the command")

    @staticmethod
    def _expect_boundary(state: dict[str, Any], boundary_id: Any) -> None:
        if not isinstance(boundary_id, str) or not boundary_id or boundary_id != state["boundary"]["id"]:
            raise ControlError("Stale or missing intended boundary; observe and reconsider")

    def _walk_guard(self, state: dict[str, Any], dx: int, dy: int) -> list[int]:
        try:
            return list(guard(state, dx, dy, paused=self.pause_requested, frozen=self.frozen,
                              now_timestamp_ms=int(time.time() * 1000)))
        except MovementBlocked as exc:
            raise ControlError(str(exc)) from exc

    def _walk(self, direction: Any, steps: Any, timeout: float, expected_session: Any,
              expected_revision: Any, generation: int) -> dict[str, Any]:
        if not isinstance(direction, str) or direction not in DIRECTIONS or type(steps) is not int or not 1 <= steps <= 8:
            raise ControlError("Walk requires north/south/east/west and 1–8 steps")
        dx, dy, action = DIRECTIONS[direction]
        completed = 0
        previous = None
        observation = None
        observation_phase = None
        observation_received_monotonic = None
        terminal_response = None

        def exchange(phase: str, kind: str, **payload: Any) -> dict[str, Any]:
            nonlocal observation, observation_phase, observation_received_monotonic, terminal_response
            response = self._exchange(kind, timeout, **payload)
            snapshot, received_monotonic = self.observation_snapshot()
            terminal_response = copy.deepcopy(response)
            if response["status"] == "ready":
                validate_state(response)
                observation = copy.deepcopy(response)
                observation_phase = phase
                # Status readers may have accepted another state since the exchange.
                # Only the entire matching snapshot supplies its original frame age.
                observation_received_monotonic = received_monotonic if snapshot == response else None
            return response

        try:
            if self.frozen:
                raise ControlError("Control is frozen; explicitly observe to reconcile first")
            for _ in range(steps):
                before = exchange("pre_step", "observe")
                if before["status"] != "ready":
                    raise ControlError(before.get("error") or "Walk stopped: observe failed")
                if previous is not None and any(before[key] != previous[key]
                                                for key in ("session", "revision", "category")):
                    raise ControlError("Walk stopped: input context changed between steps")
                if completed == 0:
                    self._expect(before, expected_session, expected_revision)
                self._walk_guard(before, dx, dy)
                if action not in before["actions"]:
                    raise ControlError("Walk stopped: movement action is not registered")
                after = exchange("post_step", "action", generation=generation, action=action,
                                 session=before["session"], revision=before["revision"],
                                 frame=before["frame"], require_exact_frame=False,
                                 boundary_id=before["boundary"]["id"], takeover_generation=before["takeover_generation"])
                if after["status"] != "ready":
                    raise ControlError(after.get("error") or "Walk stopped: action failed")
                if not observed_step(before, after, dx, dy):
                    raise ControlError("Walk stopped: displacement or input context differs from expectation")
                completed += 1
                # Check threats and context even after the final requested step.
                self._walk_guard(after, dx, dy)
                previous = after
            result = {"status": "complete", "steps": completed,
                      "detail": "Requested tile displacement observed; objective success is not inferred"}
        except ControlError as exc:
            result = {"status": "stopped", "steps": completed, "error": str(exc)}
            with self.data_lock:
                self.frozen = True
                self.pause_requested = True
                self._revoke()
                self._pause_file()
        result.update(observation=observation, observation_phase=observation_phase,
                      observation_received_monotonic=observation_received_monotonic,
                      terminal_response=terminal_response)
        self._record({"kind": "walk", "direction": direction, "steps": steps}, result)
        return result

    def status(self) -> dict[str, Any]:
        # Reading state never clears a freeze or authorizes a subsequent command.
        try:
            self._reconcile_control(retire=False)
            native = read_json(self.bridge / "state.json")
            if native is not None:
                validate_state(native)
                with self.data_lock:
                    if self.state is None or native["timestamp_ms"] >= self.state["timestamp_ms"]:
                        self._accept(native)
        except (ControlError, OSError) as exc:
            with self.data_lock:
                self._revoke()
                self._pause_file()
                self.pause_requested = True
                self.frozen = True
                self.transport_error = str(exc)
        with self.data_lock:
            age = None if self.state is None else max(0, int(time.time() * 1000) - self.state["timestamp_ms"])
            connection = "disconnected" if age is None or age > 15000 else "stale" if age > 3000 else "fresh"
            return {"state": self.state, "frozen": self.frozen, "pause_requested": self.pause_requested,
                    "pause_generation": self.pause_generation,
                    "operator_pause_generation": self.operator_pause_generation,
                    "goal": self.goal, "events": list(self.events), "last_result": self.last_result,
                    "latency_ms": self.latency_ms, "age_ms": age, "connection": connection,
                    "error": self.transport_error, "pending": self.pending,
                    "unknown_outcomes": copy.deepcopy(self.unknown_outcomes),
                    "control_pending": copy.deepcopy(self.control_pending),
                    "control_unknown_outcomes": copy.deepcopy(self.control_unknown_outcomes),
                    "historical_unknowns": copy.deepcopy(list(self.historical_unknowns)),
                    "mission_lease": None if self._mission_lease is None else asdict(self._mission_lease),
                    "journal": str(self.journal.relative_to(self.root)),
                    "expect": None if self.state is None else f'{self.state["session"]}:{self.state["revision"]}'}
