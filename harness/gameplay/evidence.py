"""Retain immutable visible observations, without issuing inputs or granting leases.

The caller supplies receipt time at actual ingestion, never at a later cache read.
Reopening preserves original receipt and initial native lag and starts without
current authority. One store writer holds a local lock for its lifetime.
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import uuid
from typing import Any, Callable

from .mission_contracts import PAUSE_ORIGINS, visible_ui_schema, validate_visible_ui
from .contracts import (
    ContractError, EvidenceRef, Fact, Interpretation, Vector, _BOUNDARY, _ID,
    _INT, _VECTOR, MAX_JSON_BYTES, _pairs, _reject_constant, _array, _integer, _object, _text, json_object, validate_json,
)

DEFAULT_FRAMES = 32
DEFAULT_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 4096
MAX_BYTES = 1024 * 1024 * 1024
MAX_FRAME_BYTES = 32 * 1024 * 1024
MAX_AGE_SECONDS = 3.0
MAX_METADATA_BYTES = 34 * 1024 * 1024
# Preserve space for bounded dispute/blocked/session lists even at admission cap.
METADATA_HEADROOM = 2 * 1024 * 1024
MAX_ENTRY_BYTES = MAX_JSON_BYTES + 8192
_PNG = b"\x89PNG\r\n\x1a\n"
_SCENE = _object({
    "provenance": {"const": "player-visible input boundary"}, "position": _VECTOR,
    "turn": _integer(2**31 - 1, -(2**31)),
    "visible_creatures": _array(_object({"name": _text(1024), "hostile": {"type": "boolean"}}), 512),
    "neighbors": _array({"type": "object", "properties": {
        "dx": _integer(1, -1), "dy": _integer(1, -1), "visible": {"type": "boolean"},
        "terrain": _text(256), "name": _text(1024), "furniture": _text(256)},
        "required": ["dx", "dy", "visible"], "additionalProperties": False}, 8, 8),
})
_OBSERVATION = _object({
    "protocol": {"type": "integer", "const": 4},
    "pause_origin": {"enum": list(PAUSE_ORIGINS)}, "takeover_generation": _INT,
    "ui": {"anyOf": [visible_ui_schema(), {"type": "null"}]}, "id": _text(128, empty=True),
    "session": {**_ID, "pattern": "^[A-Za-z0-9_-]+$"}, "revision": _INT,
    "category": _text(128, empty=True), "actions": _array(_text(128), 512),
    "status": {"enum": ["ready", "rejected", "dispatched"]}, "error": _text(4096, empty=True),
    "paused": {"type": "boolean"}, "timestamp_ms": _INT, "frame_ok": {"type": "boolean"},
    "frame": _text(300, empty=True), "in_game": {"type": "boolean"},
    "boundary": _object({"kind": _BOUNDARY, "id": _ID, "control_generation": _INT,
                          "recovery_operations": {"type": "array", "maxItems": 1, "uniqueItems": True,
                                                  "items": {"enum": ["request_interrupt", "answer_interrupt", "continue_debug_once"]}},
                          "interrupt_request_id": {"anyOf": [_ID, {"type": "null"}]}}),
    "scene": {"anyOf": [_SCENE, {"type": "null"}]},
})


class EvidenceError(ContractError):
    """Evidence missing, inconsistent, stale, or unavailable; stop and re-observe."""


class CapacityError(EvidenceError):
    """Retention cannot be guaranteed before dispatch; nothing is deleted."""


@dataclass(frozen=True)
class CapacityReservation:
    """Opaque single-use reservation for one worst-case after/failure frame."""
    token: str
    before_observation_id: str
    frame_slots: int = 1
    bytes_reserved: int = MAX_FRAME_BYTES
    metadata_reserved: int = MAX_ENTRY_BYTES


@dataclass(frozen=True)
class _Entry:
    reference: EvidenceRef
    observation: dict[str, Any]
    initial_lag_seconds: float


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _identity(observation: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical([observation["session"], observation["frame"]])).hexdigest()


def _metadata(observation: dict[str, Any]) -> dict[str, Any]:
    # Transport request IDs and result text do not identify rendered evidence.
    return {key: value for key, value in observation.items() if key not in {"id", "status", "error"}}


def same_native_state(before: dict | None, after: dict | None) -> bool:
    """Compare validated native states, excluding only capture/transport identity.

    This proves neither image equality, freshness nor authority. A passive capture
    must not rewrite an archived source or replace its original receipt clock.
    """
    ignored = {"id", "timestamp_ms", "frame"}
    return (before is not None and after is not None
            and {key: value for key, value in before.items() if key not in ignored}
            == {key: value for key, value in after.items() if key not in ignored})


def _scene_authority(observation: dict[str, Any]) -> dict[str, Any]:
    # Host Pause changes transport permission, not game facts or scene revision.
    # _metadata still forbids rewriting paused (or anything else) on one frame.
    return {key: observation[key] for key in ("scene", "ui", "boundary", "category", "actions", "in_game", "takeover_generation")}


def _validate_observation(value: dict[str, Any] | str | bytes) -> dict[str, Any]:
    observation = json_object(value)
    validate_json(observation, _OBSERVATION)
    if observation["status"] == "dispatched" or observation["frame_ok"] is not True:
        raise EvidenceError("A failed or unfinished capture is missing evidence")
    validate_visible_ui(observation["ui"])
    kind = observation["boundary"]["kind"]
    if kind == "normal_play":
        if (not observation["in_game"] or observation["category"] != "DEFAULTMODE" or observation["scene"] is None
                or observation["boundary"]["recovery_operations"] != []
                or observation["boundary"]["interrupt_request_id"] is not None):
            raise EvidenceError("Normal-play evidence requires a positively marked scene")
    elif observation["scene"] is not None:
        raise EvidenceError("Non-normal boundary cannot publish a scene")
    if kind != "menu" and observation["ui"] is not None:
        raise EvidenceError("Visible menu data requires its native menu owner")
    expected_recovery = {"activity_poll": ["request_interrupt"], "interrupt_confirmation": ["answer_interrupt"],
                         "debug_prompt": ["continue_debug_once"]}.get(kind, [])
    boundary = observation["boundary"]
    if (boundary["recovery_operations"] not in ([], expected_recovery)
            or kind == "interrupt_confirmation" and (boundary["recovery_operations"] != expected_recovery or boundary["interrupt_request_id"] is None)
            or kind != "interrupt_confirmation" and boundary["interrupt_request_id"] is not None):
        raise EvidenceError("Recovery evidence contradicts its boundary owner")
    if not re.fullmatch(r"frame-" + re.escape(observation["session"]) + r"-[1-9][0-9]*\.png", observation["frame"]):
        raise EvidenceError("Frame identity must match its native session and immutable basename")
    if kind != "normal_play": return observation
    neighbors = observation["scene"]["neighbors"]
    expected = {(dx, dy) for dx in range(-1, 2) for dy in range(-1, 2) if (dx, dy) != (0, 0)}
    if {(tile["dx"], tile["dy"]) for tile in neighbors} != expected:
        raise EvidenceError("Scene requires exactly eight distinct adjacent cells")
    for tile in neighbors:
        fields = {"terrain", "name", "furniture"}
        if tile["visible"] and not fields <= tile.keys():
            raise EvidenceError("Visible cell lacks terrain, name or furniture")
        if not tile["visible"] and fields & tile.keys():
            raise EvidenceError("Invisible cells must not disclose hidden terrain")
    return observation


def _check_frame_bytes(data: bytes) -> None:
    """Check native PNG signature/size, not decoding or renderability.

    Native frame_ok attests capture; hashes preserve exactly those bytes. The
    viewer and native acceptance own image decoding and visible-frame quality.
    """
    if not data.startswith(_PNG) or len(data) > MAX_FRAME_BYTES:
        raise EvidenceError("Frame lacks the supported bounded PNG signature")


def _serialized(method: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(method)
    def guarded(self: EvidenceStore, *args: Any, **kwargs: Any) -> Any:
        with self._mutex:
            return method(self, *args, **kwargs)
    return guarded


class EvidenceStore:
    """Single-writer run/task retention store, independent of the bridge cache.

    Session directory is caller-owned/project-local. Never point two task/run
    stores at the same directory. A reservation retains a verified before-frame
    and excludes one slot plus 32 MiB from all unrelated ingestions until consumed
    or explicitly released. No store operation dispatches inputs.
    """
    def __init__(self, bridge_directory: Path, session_directory: Path, *,
                 max_frames: int = DEFAULT_FRAMES, max_bytes: int = DEFAULT_BYTES):
        if type(max_frames) is not int or not 1 <= max_frames <= MAX_FRAMES:
            raise CapacityError("Frame cap must be between 1 and 4096")
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
            raise CapacityError("Byte cap must be between 1 and 1 GiB")
        self.bridge = Path(bridge_directory).resolve(strict=True)
        self.directory = Path(session_directory).resolve()
        if self.directory == self.bridge or self.bridge in self.directory.parents:
            raise EvidenceError("Retained evidence must be outside the evictable bridge cache")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.frames = self.directory / "frames"
        if self.frames.is_symlink():
            raise EvidenceError("Retained frames directory cannot be a symlink")
        self.frames.mkdir(exist_ok=True)
        self.max_frames = max_frames
        self.max_bytes = max_bytes
        self._mutex = threading.RLock()
        self._lock = (self.directory / "evidence.lock").open("a+b")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock.close()
            raise EvidenceError("Another writer owns this evidence store") from exc
        self._entries: dict[str, _Entry] = {}
        self._current: EvidenceRef | None = None
        self._authority_generation = 0
        self._session: str | None = None
        self._retired_sessions: list[str] = []
        self._blocked: list[str] = []
        self._disputed: list[str] = []
        self._reservation: CapacityReservation | None = None
        self._interpretations: tuple[Interpretation, ...] = ()
        self.invalid_reason = "Observe after opening the store"
        try:
            self._load()
        except Exception:
            self.close()
            raise

    def __enter__(self) -> EvidenceStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @_serialized
    def close(self) -> None:
        self._authority_generation += 1
        self._current = None
        self._reservation = None
        self._lock.close()

    def _open(self) -> None:
        if self._lock.closed:
            raise EvidenceError("Evidence store is closed")

    def _usage(self) -> tuple[int, int]:
        # Missing indexed sources retain their slots: dropping their bytes cannot
        # admit an unbounded manifest or erase a memory frontier. Orphans consume
        # additional slots rather than substituting for those missing sources.
        count, size = len(self._entries), 0
        indexed_names = {identity + ".png" for identity in self._entries}
        for path in self.frames.iterdir():
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                # A source may disappear after listing. Indexed slots already
                # remain counted above; integrity checks retain the loss, not an
                # older source or permission to dispatch. Other I/O errors stop.
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise EvidenceError("Unexpected non-file in retained evidence")
            if path.name not in indexed_names:
                count += 1
            size += metadata.st_size
        if count > self.max_frames or size > self.max_bytes:
            raise CapacityError("Existing retention exceeds cap; no evidence was deleted")
        return count, size

    def _load(self) -> None:
        manifest = self.directory / "evidence.json"
        if manifest.exists():
            try:
                if manifest.is_symlink() or manifest.stat().st_size > MAX_METADATA_BYTES:
                    raise EvidenceError("Invalid evidence manifest")
                value = json.loads(manifest.read_bytes(), parse_constant=_reject_constant, object_pairs_hook=_pairs)
                if (type(value) is not dict or set(value) != {"store_version", "entries", "session", "retired_sessions", "blocked", "disputed"}
                        or type(value["store_version"]) is not int or value["store_version"] != 3
                        or type(value["entries"]) is not list or len(value["entries"]) > MAX_FRAMES
                        or type(value["retired_sessions"]) is not list or len(value["retired_sessions"]) > MAX_FRAMES
                        or any(type(s) is not str or not 1 <= len(s) <= 128 for s in value["retired_sessions"])
                        or type(value["blocked"]) is not list or len(value["blocked"]) > MAX_FRAMES
                        or any(type(s) is not str or not re.fullmatch("[a-f0-9]{64}", s) for s in value["blocked"])
                        or type(value["disputed"]) is not list or len(value["disputed"]) > MAX_FRAMES
                        or any(type(s) is not str or not re.fullmatch("[a-f0-9]{64}", s) for s in value["disputed"])
                        or (value["session"] is not None and (type(value["session"]) is not str
                            or not re.fullmatch("[A-Za-z0-9_-]{1,128}", value["session"])))):
                    raise EvidenceError("Malformed evidence manifest")
                self._session = value["session"]
                self._retired_sessions = value["retired_sessions"]
                self._blocked = value["blocked"]
                self._disputed = value["disputed"]
                for item in value["entries"]:
                    if type(item) is not dict or set(item) != {"reference", "observation", "initial_lag_seconds"}:
                        raise EvidenceError("Malformed retained observation")
                    ref = EvidenceRef.from_dict(item["reference"])
                    observation = _validate_observation(item["observation"])
                    lag = item["initial_lag_seconds"]
                    if type(lag) not in (int, float) or not math.isfinite(lag) or not 0 <= lag <= 3:
                        raise EvidenceError("Invalid original observation age")
                    expected = self._reference(observation, ref.received_monotonic, ref.frame_sha256)
                    if ref != expected or ref.observation_id in self._entries:
                        raise EvidenceError("Retained metadata contradicts observation identity")
                    self._entries[ref.observation_id] = _Entry(ref, observation, lag)
                if not set(self._disputed) <= self._entries.keys():
                    raise EvidenceError("Disputed source is not retained")
                # Preserve valid metadata even when an original image is lost.
                # Memory needs the missing newest reference to avoid resurrecting
                # older claims. No loaded source becomes current on reopen.
                lost_source = False
                for entry in self._entries.values():
                    try:
                        self._verify_file(entry.reference)
                    except EvidenceError as exc:
                        self._invalidate(str(exc), entry.reference.observation_id)
                        lost_source = True
                if lost_source:
                    self._save()
            except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
                if isinstance(exc, EvidenceError):
                    raise
                raise EvidenceError(f"Cannot reopen retained evidence: {exc}") from exc
        self._usage()

    def _manifest(self) -> dict[str, Any]:
        return {"store_version": 3, "session": self._session, "retired_sessions": self._retired_sessions,
                 "blocked": self._blocked, "disputed": self._disputed,
                 "entries": [{"reference": item.reference.to_dict(), "observation": item.observation,
                              "initial_lag_seconds": item.initial_lag_seconds} for item in self._entries.values()]}

    def _save(self) -> None:
        encoded = _canonical(self._manifest())
        if len(encoded) > MAX_METADATA_BYTES:
            raise CapacityError("Metadata retention cap reached; existing evidence preserved")
        temporary = self.directory / ("evidence-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / "evidence.json")
        except OSError as exc:
            raise EvidenceError(f"Cannot persist evidence metadata: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _reference(self, observation: dict[str, Any], received: float, digest: str) -> EvidenceRef:
        identity = _identity(observation)
        return EvidenceRef(identity, observation["session"], observation["revision"], observation["timestamp_ms"],
                           received, None if observation["scene"] is None else observation["scene"]["turn"], str(self.frames / (identity + ".png")),
                           digest, observation["boundary"]["kind"])

    def _invalidate(self, reason: str, *disputed: str) -> None:
        self._authority_generation += 1
        for identity in disputed:
            if identity in self._entries and identity not in self._disputed:
                self._disputed.append(identity)
        identities = disputed + (() if self._current is None else (self._current.observation_id,))
        for identity in identities:
            if identity in self._entries and identity not in self._blocked:
                self._blocked.append(identity)
        self._current = None
        self.invalid_reason = reason

    def _frame_bytes(self, reference: EvidenceRef) -> bytes:
        path = Path(reference.frame_path)
        expected = self.frames / (reference.observation_id + ".png")
        if path != expected or path.is_symlink() or path.resolve() != expected:
            raise EvidenceError("Retained frame path escapes its identity or store")
        try:
            with path.open("rb") as stream:
                data = stream.read(MAX_FRAME_BYTES + 1)
        except OSError as exc:
            raise EvidenceError(f"Retained source is unavailable: {exc}") from exc
        _check_frame_bytes(data)
        if hashlib.sha256(data).hexdigest() != reference.frame_sha256:
            raise EvidenceError("Retained source hash mismatch")
        return data

    def _verify_file(self, reference: EvidenceRef) -> None:
        self._frame_bytes(reference)

    @_serialized
    def export_source(self, identity: str) -> tuple[dict, bytes]:
        """Read one exact retained source; no refresh or authority mutation.

        This reader is independent of the evictable bridge and does not scan the
        manifest. Missing/changed bytes fail instead of returning a later image.
        Runtime validation remains responsible for sticky evidence invalidation.
        """
        self._open()
        entry = self._entries.get(identity)
        if entry is None:
            raise EvidenceError("Unknown retained source")
        data = self._frame_bytes(entry.reference)
        return {"reference": entry.reference.to_dict(),
                "observation": json_object(entry.observation),
                "disposition": "disputed" if identity in self._disputed else "retained",
                "grants_authority": False}, data

    @_serialized
    def verify(self, reference: EvidenceRef) -> None:
        """Verify historical source availability/integrity; this does not make it current."""
        self._open()
        item = self._entries.get(reference.observation_id)
        if item is None or item.reference != reference:
            raise EvidenceError("Unknown or modified evidence reference")
        try:
            self._verify_file(reference)
        except EvidenceError as exc:
            self._invalidate(str(exc), reference.observation_id)
            self._save()
            raise

    @_serialized
    def source_status(self, reference: EvidenceRef) -> str:
        """Sticky historical validity, independent of present freshness/authority.

        Conflicting sources remain disputed after newer observations and reopen.
        A stale or old-session source can remain retained historical evidence.
        Neither status grants permission to use it as current command authority.
        """
        self.verify(reference)
        return "disputed" if reference.observation_id in self._disputed else "retained"

    @_serialized
    def authority_generation(self) -> int:
        """Process-local invalidation/identity generation, never an execution token.

        Returning to an earlier retained frame cannot conceal intervening changes.
        This is meaningful only for this store instance; reopening has no current
        authority, and task memory is never restored across instances.
        """
        return self._authority_generation

    def _fresh(self, entry: _Entry, now_monotonic: float, now_timestamp_ms: int) -> None:
        if type(now_monotonic) not in (int, float) or not math.isfinite(now_monotonic):
            raise EvidenceError("Invalid monotonic time")
        if type(now_timestamp_ms) is not int:
            raise EvidenceError("Native clock comparison requires integer milliseconds")
        elapsed = now_monotonic - entry.reference.received_monotonic
        wall_age = now_timestamp_ms - entry.reference.timestamp_ms
        if elapsed < 0 or wall_age < -1000 or wall_age > 3000 or entry.initial_lag_seconds + elapsed > MAX_AGE_SECONDS:
            raise EvidenceError("Observation is stale or clock continuity is unknown")

    @staticmethod
    def _equivalence_rule(rule: str) -> None:
        if rule not in ("native_state", "exact_png_bytes"):
            raise ContractError("Unsupported evidence equivalence rule")

    @_serialized
    def equivalent(self, before: EvidenceRef, after: EvidenceRef, *, rule: str) -> bool:
        """Compare verified historical sources without freshness or authority promotion.

        Native-state equality attests only the retained normal scene or rendered
        menu data. Exact-PNG equality additionally compares encoded canonical
        bytes. Neither rule proves host or store generation continuity.
        """
        self._equivalence_rule(rule)
        original, actual = self.observation(before), self.observation(after)
        if any(value["status"] != "ready" or value["error"] != "" for value in (original, actual)):
            return False
        if not same_native_state(original, actual):
            return False
        if rule == "native_state":
            return all((value["boundary"]["kind"] == "normal_play" and value["scene"] is not None)
                       or (value["boundary"]["kind"] == "menu" and value["ui"] is not None)
                       for value in (original, actual))
        return before.frame_sha256 == after.frame_sha256

    @_serialized
    def ingest(self, value: dict[str, Any] | str | bytes, *, received_monotonic: float,
               now_monotonic: float, now_timestamp_ms: int,
               reservation: CapacityReservation | None = None) -> EvidenceRef:
        """Retain a native-v4 normal/menu/activity/recovery observation with its actual first receipt.

        Repeated source identity reuses original receipt/lag and immutable copied
        source; bridge-cache eviction is harmless after initial retention. Altered
        metadata for that identity is a contradiction, never a fresh observation.
        """
        return self._ingest(value, received_monotonic=received_monotonic, now_monotonic=now_monotonic,
                            now_timestamp_ms=now_timestamp_ms, reservation=reservation, promote_current=True)

    @_serialized
    def retain_equivalent(self, value: dict[str, Any] | str | bytes, *, received_monotonic: float,
                          now_monotonic: float, now_timestamp_ms: int, rule: str) -> EvidenceRef:
        """Archive final preflight with its actual receipt, preserving current attribution.

        Requires fresh current evidence and no outstanding after-frame reservation.
        A successful result is historical evidence only; any failed retention
        invalidates current authority and preserves available diagnostics.
        """
        return self._ingest(value, received_monotonic=received_monotonic, now_monotonic=now_monotonic,
                            now_timestamp_ms=now_timestamp_ms, reservation=None, promote_current=False, rule=rule)

    def _ingest(self, value: dict[str, Any] | str | bytes, *, received_monotonic: float,
                now_monotonic: float, now_timestamp_ms: int, reservation: CapacityReservation | None,
                promote_current: bool, rule: str = "native_state") -> EvidenceRef:
        self._open()
        try:
            before = None
            if not promote_current:
                self._equivalence_rule(rule)
                before = self.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
                self.observation(before)  # A disputed current source cannot support equivalence.
                if self._reservation is not None:
                    raise CapacityError("An unresolved dispatch already reserves after evidence")
            observation = json_object(value)
            validate_json(observation, _OBSERVATION)
            session = observation["session"]
            if not promote_current and session != before.session:
                raise EvidenceError("Equivalent preflight cannot adopt another world session")
            if session in self._retired_sessions:
                raise EvidenceError("An old world session cannot become current again")
            if self._session is not None and session != self._session:
                self._invalidate("World session changed")
                if len(self._retired_sessions) >= MAX_FRAMES:
                    raise CapacityError("Too many world transitions for one task/run store")
                self._retired_sessions.append(self._session)
            self._session = session
            observation = _validate_observation(observation)
            if not promote_current and (observation["status"] != "ready" or observation["error"] != ""):
                raise EvidenceError("Equivalent preflight requires ready evidence without an error")
            if type(received_monotonic) not in (int, float) or not math.isfinite(received_monotonic) or received_monotonic < 0:
                raise EvidenceError("Invalid actual receipt time")
            identity = _identity(observation)
            if reservation is not None:
                self._check_reservation(reservation)
                if identity == reservation.before_observation_id:
                    raise CapacityError("A before-frame reread cannot consume an after-frame reservation")
            if identity in self._blocked:
                raise EvidenceError("Invalidated source cannot regain current authority")
            peers = [item for item in self._entries.values() if item.reference.session == session]
            entry = self._entries.get(identity)
            if entry is not None and _metadata(entry.observation) != _metadata(observation):
                disputed = [identity]
                if (entry.reference.revision == observation["revision"]
                        and _scene_authority(entry.observation) != _scene_authority(observation)):
                    disputed.extend(item.reference.observation_id for item in peers
                                    if item.reference.revision == observation["revision"])
                self._invalidate("Contradictory metadata for the same source identity", *disputed)
                raise EvidenceError("Contradictory metadata for the same source identity")
            if peers and observation["revision"] < max(item.reference.revision for item in peers):
                raise EvidenceError("Observation revision regressed")
            for peer in peers:
                if (peer.reference.revision == observation["revision"]
                        and _scene_authority(peer.observation) != _scene_authority(observation)):
                    self._invalidate("Contradictory scene or boundary at the same revision", *(
                        item.reference.observation_id for item in peers
                        if item.reference.revision == observation["revision"]))
                    raise EvidenceError("Contradictory scene or boundary at the same revision")
            if entry is not None:
                self._fresh(entry, now_monotonic, now_timestamp_ms)
                self.verify(entry.reference)
            else:
                if type(now_timestamp_ms) is not int or not -1000 <= now_timestamp_ms - observation["timestamp_ms"] <= 3000:
                    raise EvidenceError("First observation is stale or from a future clock")
                source = self.bridge / observation["frame"]
                if source.is_symlink() or source.resolve() != source:
                    raise EvidenceError("Native frame path escapes the bridge")
                try:
                    with source.open("rb") as stream:
                        data = stream.read(MAX_FRAME_BYTES + 1)
                except OSError as exc:
                    raise EvidenceError(f"Native source is unavailable or evicted: {exc}") from exc
                _check_frame_bytes(data)
                reference = self._reference(observation, received_monotonic, hashlib.sha256(data).hexdigest())
                entry = _Entry(reference, observation, max(0, now_timestamp_ms - observation["timestamp_ms"]) / 1000)
                self._fresh(entry, now_monotonic, now_timestamp_ms)
                self._capacity(len(data), reservation, metadata_bytes=len(_canonical(observation)) + 8192)
                destination = Path(reference.frame_path)
                if destination.exists():
                    raise EvidenceError("Unindexed retained source exists; refusing replacement")
                with destination.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                destination.chmod(0o444)
                self._entries[identity] = entry
            if not promote_current and not self.equivalent(before, entry.reference, rule=rule):
                raise EvidenceError("Final preflight is not equivalent to current retained evidence")
            if reservation is not None:
                self._check_reservation(reservation)
                self._reservation = None
            if promote_current:
                if self._current != entry.reference:
                    self._authority_generation += 1
                self._current = entry.reference
                self.invalid_reason = ""
            self._save()
            return entry.reference
        except (ContractError, OSError) as exc:
            self._invalidate(str(exc))
            self._save()
            if isinstance(exc, EvidenceError):
                raise
            raise EvidenceError(str(exc)) from exc

    @_serialized
    def current(self, *, now_monotonic: float, now_timestamp_ms: int) -> EvidenceRef:
        """Current normal scene only: movement callers cannot use menu retention."""
        reference = self.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        if reference.boundary_kind != "normal_play":
            raise EvidenceError("Current evidence requires positively marked normal play")
        return reference

    @_serialized
    def current_boundary(self, *, now_monotonic: float, now_timestamp_ms: int) -> EvidenceRef:
        """Fresh retained boundary, never a dispatch capability or normal scene."""
        self._open()
        if self._current is None:
            raise EvidenceError(self.invalid_reason)
        try:
            entry = self._entries[self._current.observation_id]
            self._fresh(entry, now_monotonic, now_timestamp_ms)
            self.verify(entry.reference)
            return entry.reference
        except EvidenceError as exc:
            self._invalidate(str(exc))
            self._save()
            raise

    @_serialized
    def inspect_current(self, *, now_monotonic: float, now_timestamp_ms: int) -> tuple[EvidenceRef | None, bool]:
        """Inspect normal-play eligibility; menu retention does not grant it."""
        reference, fresh = self.inspect_current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        return (reference, fresh) if reference is not None and reference.boundary_kind == "normal_play" else (None, False)

    @_serialized
    def inspect_current_boundary(self, *, now_monotonic: float, now_timestamp_ms: int) -> tuple[EvidenceRef | None, bool]:
        """Report age without granting authority or invalidating merely old evidence.

        Integrity failures still invalidate through verify; dispatch uses current_boundary().
        Like current_boundary(), this includes retained menus and activity polls.
        """
        self._open()
        reference = self._current
        if reference is None:
            return None, False
        self.verify(reference)
        try:
            self._fresh(self._entries[reference.observation_id], now_monotonic, now_timestamp_ms)
        except EvidenceError:
            return reference, False
        return reference, True

    def _check_reservation(self, reservation: CapacityReservation) -> None:
        if self._reservation is None or reservation != self._reservation:
            raise CapacityError("Reservation is unknown, released or already consumed")

    def _capacity(self, size: int, reservation: CapacityReservation | None, *,
                  metadata_bytes: int = MAX_ENTRY_BYTES) -> None:
        count, used = self._usage()
        reserved_frames = reserved_bytes = reserved_metadata = 0
        if reservation is not None:
            self._check_reservation(reservation)
        elif self._reservation is not None:
            reserved_frames = self._reservation.frame_slots
            reserved_bytes = self._reservation.bytes_reserved
            reserved_metadata = self._reservation.metadata_reserved
        if len(_canonical(self._manifest())) + reserved_metadata + metadata_bytes + METADATA_HEADROOM > MAX_METADATA_BYTES:
            raise CapacityError("Metadata capacity/reserve exhausted before dispatch")
        if count + reserved_frames + 1 > self.max_frames or used + reserved_bytes + size > self.max_bytes:
            raise CapacityError("Retention cap reached; existing evidence was preserved")

    @_serialized
    def usage(self) -> dict[str, int]:
        """Measured archive usage; mission admission owns stricter cleanup reserves."""
        self._open()
        count, size = self._usage()
        return {"frames": count, "bytes": size, "metadata_bytes": len(_canonical(self._manifest())),
                "max_frames": self.max_frames, "max_bytes": self.max_bytes,
                "max_metadata_bytes": MAX_METADATA_BYTES}

    @_serialized
    def preflight_dispatch(self, before: EvidenceRef, *, now_monotonic: float,
                           now_timestamp_ms: int) -> None:
        """Check worst-case capacity without claiming a reservation or dispatch guarantee."""
        if self.current_boundary(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms) != before:
            raise EvidenceError("Dispatch before-frame must be current retained evidence")
        if self._reservation is not None:
            raise CapacityError("An unresolved dispatch already reserves after evidence")
        self._capacity(MAX_FRAME_BYTES, None)

    @_serialized
    def reserve_dispatch(self, before: EvidenceRef, *, now_monotonic: float,
                         now_timestamp_ms: int) -> CapacityReservation:
        """Reserve one distinct slot and 32 MiB for required after/failure capture.

        Consume by passing this token to ingest, or explicitly release after a
        non-dispatch. Oversized/missing capture remains an error/unknown outcome;
        no reservation fabricates source evidence or promises engine capture.
        """
        self.preflight_dispatch(before, now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
        reservation = CapacityReservation(uuid.uuid4().hex, before.observation_id)
        self._reservation = reservation
        return reservation

    @_serialized
    def release(self, reservation: CapacityReservation) -> None:
        self._open()
        self._check_reservation(reservation)
        self._reservation = None

    @property
    @_serialized
    def historical_references(self) -> tuple[EvidenceRef, ...]:
        return tuple(item.reference for item in self._entries.values())

    @_serialized
    def observation(self, reference: EvidenceRef) -> dict[str, Any]:
        """Independent retained observation copy; historical data grants no authority."""
        if self.source_status(reference) != "retained":
            raise EvidenceError("Disputed observation cannot supply skill predicates")
        return json_object(self._entries[reference.observation_id].observation)

    @_serialized
    def historical_facts(self, reference: EvidenceRef) -> tuple[Fact, ...]:
        """Source-tagged measurements; being retained never implies freshness."""
        self.verify(reference)
        scene = self._entries[reference.observation_id].observation["scene"]
        if scene is None: return ()
        return (Fact("position", json.dumps(scene["position"]), reference),
                Fact("turn", str(scene["turn"]), reference),
                Fact("visible_creature_count", str(len(scene["visible_creatures"])), reference))

    @_serialized
    def current_facts(self, *, now_monotonic: float, now_timestamp_ms: int) -> tuple[Fact, ...]:
        return self.historical_facts(self.current(now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms))

    @_serialized
    def position(self, reference: EvidenceRef) -> Vector:
        self.verify(reference)
        scene = self._entries[reference.observation_id].observation["scene"]
        if scene is None: raise EvidenceError("Position requires a normal scene")
        return tuple(scene["position"])

    @_serialized
    def interpret(self, text: str, sources: tuple[EvidenceRef, ...]) -> Interpretation:
        """Bounded, explicitly tagged commentary; never changes measured facts."""
        if len(self._interpretations) >= 32:
            raise CapacityError("Interpretation limit reached")
        interpretation = Interpretation(text, sources)
        for reference in sources:
            self.verify(reference)
        self._interpretations += (interpretation,)
        return interpretation

    @property
    @_serialized
    def interpretations(self) -> tuple[Interpretation, ...]:
        return self._interpretations
