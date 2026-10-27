"""Offline validation of current sealed missions before advisory export.

SQLite validates a bounded in-memory snapshot. Shared locks keep cooperating
writers out until close; original files are never created, repaired or updated.
This validates retained support linkage, not interpretations or game success.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any

from .contracts import canonical, ContractError, EvidenceRef, _pairs, _reject_constant, json_object, validate_json
from .evidence import (
    MAX_FRAME_BYTES, MAX_FRAMES, MAX_BYTES, MAX_METADATA_BYTES, MAX_AGE_SECONDS, MAX_HISTORICAL_LAG_SECONDS, _check_frame_bytes,
    _identity, _validate_observation,
)
from .mission_contracts import MAX_LIBRARY_SOURCES, MissionAdmission, validate_effect_reconciliation, validate_request
from .mission_ledger import DB_VERSION, MissionLedger, _intent, _primitive_parent, _ordinary_sequence
from .native_receipts import compact_native_ack, validate_ordinary_mapping
from .procedures import MAX_PROCEDURE_RECORDS, procedure_schema, project_procedures, validate_procedure

MAX_DATABASE_BYTES = 64 * 1024 * 1024
MAX_REQUESTS = 4096
MAX_PRIMITIVES = 8192
MAX_ARCHIVE_BYTES = MAX_BYTES
_ELIGIBLE_ARCHIVE_PHASES = frozenset({"completed", "failed", "stopped", "paused"})
_REQUEST_TERMINAL = frozenset({"completed", "partial", "blocked", "failed", "unknown", "paused"})
_PRIMITIVE_TERMINAL = frozenset({"returned", "rejected", "not_dispatched", "unknown"})


class ProcedureLibraryError(ContractError):
    """Historical support is unavailable or not an admitted sealed closure."""


class ProcedureEpisodeRefusal(ProcedureLibraryError):
    """An episode selects a mission/request/source outside the pinned support."""


@contextmanager
def captured_database(encoded: bytes) -> Iterator[sqlite3.Connection]:
    """Bounded read-only original bytes; never open a persisted actor database."""
    if len(encoded) > MAX_DATABASE_BYTES:
        raise ProcedureLibraryError("Original database exceeds its captured byte bound")
    database = sqlite3.connect(":memory:")
    try:
        database.deserialize(encoded)
        database.execute("PRAGMA query_only=ON")
        database.execute("PRAGMA trusted_schema=OFF")
        remaining = 20_000
        def progress() -> int:
            nonlocal remaining
            remaining -= 1
            return int(remaining <= 0)
        database.set_progress_handler(progress, 1000)
        if database.execute("PRAGMA quick_check").fetchmany(2) != [("ok",)]:
            raise ProcedureLibraryError("Captured original database is corrupt")
        required = {"metadata", "requests", "primitives", "memory", "reflection_jobs", "reflection_commands"}
        tables = {name for name, kind, sql in database.execute(
            "SELECT name,type,sql FROM sqlite_schema WHERE name IN ('metadata','requests','primitives','memory','reflection_jobs','reflection_commands')")
            if kind == "table" and type(sql) is str and sql.upper().startswith("CREATE TABLE ")}
        if tables != required:
            raise ProcedureLibraryError("Captured database requires ordinary retained tables")
        yield database
    finally:
        database.close()


def _id(value: Any) -> str:
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value) is None:
        raise ProcedureLibraryError("Library identifier must be bounded ASCII")
    return value


def _sha(value: Any) -> None:
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ProcedureLibraryError("Library digest must be lowercase SHA256")


def _pins(sources: Sequence[dict], current: str) -> dict[str, dict]:
    if (not isinstance(sources, Sequence) or isinstance(sources, (str, bytes, bytearray))
            or len(sources) > MAX_LIBRARY_SOURCES):
        raise ProcedureLibraryError(f"Library requires at most {MAX_LIBRARY_SOURCES} explicit source pins")
    result = {}
    for value in sources:
        if type(value) is not dict or set(value) != {"mission_id", "ledger_sha256", "index_sha256"}:
            raise ProcedureLibraryError("Library pin fields must match exactly")
        mission = _id(value["mission_id"])
        _sha(value["ledger_sha256"]); _sha(value["index_sha256"])
        if mission == current or mission in result:
            raise ProcedureLibraryError("Library missions must be distinct and historical")
        result[mission] = dict(value)
    return result


def _object(encoded: str, maximum: int = 65_536) -> dict:
    if type(encoded) is not str or len(encoded.encode()) > maximum:
        raise ProcedureLibraryError("Historical row exceeds its byte bound")
    return json_object(encoded)


def _sources(value: dict, key: str) -> set[str]:
    identities = value.get(key, [])
    if type(identities) is not list or len(identities) > 128:
        raise ProcedureLibraryError("Malformed bounded source association")
    return {_id(identity) for identity in identities}


class SealedProcedureArchive:
    """A bounded historical reader. Every returned value is a defensive copy.

    The caller supplies the project root and exact pins, never archive paths.
    Request validation covers the current request contract, immutable identity,
    digest and terminal result. It does not rerun the actor's complete accounting,
    authority, lifecycle or semantic-success adjudication.
    """

    def __init__(self, root: Path, sources: Sequence[dict], *, current_mission_id: str):
        self._closed = False
        self._locks: list[int] = []
        self._root_fd: int | None = None
        self._records: list[dict] = []
        self._requests: dict[str, dict[str, dict]] = {}
        self._entries: dict[str, dict[str, dict]] = {}
        self._links: dict[str, dict[str, set[str]]] = {}
        self._dependencies: dict[str, dict[str, dict]] = {}
        self._environments: dict[str, dict | None] = {}
        try:
            self._pins = _pins(sources, _id(current_mission_id))
            self.root = Path(root).absolute()
            if ".." in self.root.parts:
                raise ProcedureLibraryError("Project root must have no parent traversal")
            # Walk from / with O_NOFOLLOW, including every ancestor of root.
            self._root_fd = os.open(self.root.anchor, os.O_RDONLY | os.O_DIRECTORY)
            for part in self.root.parts[1:]:
                opened = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._root_fd)
                os.close(self._root_fd)
                self._root_fd = opened
            # Lock the complete declared closure before reading any of it.
            for mission in self._pins:
                self._lock(mission, "mission.lock")
                self._lock(mission, "evidence/evidence.lock")
            for mission, pin in self._pins.items():
                self._load_index(mission, pin)
                self._load_ledger(mission, pin)
            self._validate_closure()
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
            self.close()
            if isinstance(exc, ContractError):
                raise
            raise ProcedureLibraryError(f"Cannot read sealed procedure library: {exc}") from exc

    def __enter__(self) -> SealedProcedureArchive:
        self._open()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _open(self) -> None:
        if self._closed:
            raise ProcedureLibraryError("Procedure library is closed")

    def close(self) -> None:
        """Release all shared locks; safe after partial construction or repeatedly."""
        for descriptor in self._locks:
            os.close(descriptor)
        self._locks.clear()
        if self._root_fd is not None:
            os.close(self._root_fd)
            self._root_fd = None
        self._closed = True

    def _parts(self, mission: str) -> tuple[str, ...]:
        return (".runtime", "missions", mission)

    def _index_version(self, mission: str) -> int:
        return 6

    def _expected_frame_path(self, mission: str, identity: str, reference: EvidenceRef) -> Path:
        return self.root / ".runtime" / "missions" / mission / "evidence" / "frames" / (identity + ".png")

    def _observation_data(self, mission: str, value: dict) -> dict:
        return _validate_observation(value)

    def _request_data(self, mission: str, value: str) -> dict:
        return validate_request(_object(value))

    def _mapping(self, mission: str, intent: dict, receipt: dict, **scope: Any) -> None:
        validate_ordinary_mapping(intent, receipt, **scope)

    def _file(self, mission: str, relative: str) -> int:
        """Open only derived paths using directory descriptors, never a stored path."""
        descriptor = os.dup(self._root_fd)
        try:
            parts = (*self._parts(mission), *relative.split("/"))
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            opened = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            metadata = os.fstat(opened)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                os.close(opened)
                raise ProcedureLibraryError("Archive files must be owned regular files without aliases")
            return opened
        finally:
            os.close(descriptor)

    def _read(self, mission: str, relative: str, maximum: int, digest: str | None = None) -> bytes:
        with os.fdopen(self._file(mission, relative), "rb") as stream:
            if os.fstat(stream.fileno()).st_size > maximum:
                raise ProcedureLibraryError("Archive exceeds byte bound")
            data = stream.read(maximum + 1)
        if len(data) > maximum or digest is not None and hashlib.sha256(data).hexdigest() != digest:
            raise ProcedureLibraryError("Archive exceeds byte bound or pinned hash differs")
        return data

    def _lock(self, mission: str, relative: str) -> None:
        descriptor = self._file(mission, relative)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BaseException:
            os.close(descriptor)
            raise
        self._locks.append(descriptor)

    def _frame(self, mission: str, reference: EvidenceRef) -> bytes:
        data = self._read(mission, "evidence/frames/" + reference.observation_id + ".png",
                          MAX_FRAME_BYTES, reference.frame_sha256)
        _check_frame_bytes(data)
        return data

    def _load_index(self, mission: str, pin: dict) -> None:
        encoded = self._read(mission, "evidence/evidence.json", MAX_METADATA_BYTES, pin["index_sha256"])
        value = json.loads(encoded, object_pairs_hook=_pairs, parse_constant=_reject_constant)
        if (type(value) is not dict
                or set(value) != {"store_version", "entries", "session", "retired_sessions", "blocked", "disputed"}
                or type(value["store_version"]) is not int or value["store_version"] != self._index_version(mission)
                or type(value["entries"]) is not list or len(value["entries"]) > MAX_FRAMES
                or type(value["retired_sessions"]) is not list or len(value["retired_sessions"]) > MAX_FRAMES
                or type(value["blocked"]) is not list or len(value["blocked"]) > MAX_FRAMES
                or value["disputed"] != []):
            raise ProcedureLibraryError("Unsupported or unavailable historical evidence index")
        blocked = value["blocked"]
        for identity in blocked:
            _sha(identity)
        if len(set(blocked)) != len(blocked):
            raise ProcedureLibraryError("Duplicate blocked historical source identity")
        if value["session"] is not None:
            _id(value["session"])
        retired = value["retired_sessions"]
        if any(_id(session) != session for session in retired) or len(set(retired)) != len(retired):
            raise ProcedureLibraryError("Corrupt retired session identities")
        entries = {}
        total_bytes = 0
        for item in value["entries"]:
            if type(item) is not dict or set(item) != {"reference", "observation", "initial_lag_seconds", "retention"}:
                raise ProcedureLibraryError("Malformed historical observation")
            reference = EvidenceRef.from_dict(item["reference"])
            observation = self._observation_data(mission, item["observation"])
            lag = item["initial_lag_seconds"]
            retention = item["retention"]
            age_limit = MAX_HISTORICAL_LAG_SECONDS if retention == "terminal" else MAX_AGE_SECONDS
            if (retention not in ("current", "preflight", "terminal") or type(lag) not in (int, float)
                    or not math.isfinite(lag) or not 0 <= lag <= age_limit):
                raise ProcedureLibraryError("Invalid original receipt age")
            identity = _identity(observation)
            _sha(reference.observation_id); _sha(reference.frame_sha256)
            expected_path = self._expected_frame_path(mission, identity, reference)
            expected = EvidenceRef(identity, observation["session"], observation["revision"], observation["timestamp_ms"],
                reference.received_monotonic, None if observation["scene"] is None else observation["scene"]["turn"],
                str(expected_path), reference.frame_sha256, observation["boundary"]["kind"])
            if (reference != expected or identity in entries
                    or observation["session"] not in [value["session"], *retired]):
                raise ProcedureLibraryError("Historical reference contradicts its observation or owned identity")
            total_bytes += len(self._frame(mission, reference))
            if total_bytes > MAX_ARCHIVE_BYTES:
                raise ProcedureLibraryError("Historical frame archive exceeds byte bound")
            entries[identity] = {"reference": reference.to_dict(), "observation": observation,
                                 "disposition": "retained", "grants_authority": False}
        # Revocation prevents current input authority; it does not dispute history.
        if not set(blocked) <= entries.keys():
            raise ProcedureLibraryError("Blocked historical source is not retained")
        self._entries[mission] = entries

    def _load_ledger(self, mission: str, pin: dict) -> None:
        for suffix in ("-wal", "-shm", "-journal"):
            try:
                descriptor = self._file(mission, "mission.sqlite3" + suffix)
            except FileNotFoundError:
                continue
            os.close(descriptor)
            raise ProcedureLibraryError("A sealed ledger cannot have SQLite sidecars")
        encoded = self._read(mission, "mission.sqlite3", MAX_DATABASE_BYTES, pin["ledger_sha256"])
        with captured_database(encoded) as database:
            if database.execute("PRAGMA user_version").fetchone() != (DB_VERSION,):
                raise ProcedureLibraryError("Unsupported or corrupt historical mission ledger")
            metadata = self._rows(database, "SELECT key,value FROM metadata", 64)
            if len({key for key, _ in metadata}) != len(metadata):
                raise ProcedureLibraryError("Duplicate ledger metadata identity")
            metadata = dict(metadata)
            admission = MissionAdmission.from_dict(_object(metadata["admission"]))
            state = _object(metadata["state"])
            # Campaign outcome does not decide procedure validity. Shared locks,
            # exact pins and settled retained work also fence paused archives.
            if admission.mission_id != mission or state.get("phase") not in _ELIGIBLE_ARCHIVE_PHASES:
                raise ProcedureLibraryError("Library requires the current admission and an eligible archive phase")
            reflection = self._rows(database, "SELECT state FROM reflection_jobs", 64)
            if any(row[0] not in ("completed", "expired", "unknown", "unreviewed") for row in reflection):
                raise ProcedureLibraryError("Historical reflection admission must be closed before library use")
            learning = admission.learning
            if learning is None:
                self._dependencies[mission], self._environments[mission] = {}, None
            else:
                learning = learning.to_dict()
                self._dependencies[mission] = _pins(learning["library_sources"], mission)
                self._environments[mission] = learning["environment"]
            self._load_requests(database, mission)
            self._load_primitives(database, mission)
            events = set()
            for event_id, record_id, body in self._rows(database,
                    "SELECT event_id,record_id,body FROM memory WHERE entry_type='procedure' ORDER BY sequence",
                    MAX_PROCEDURE_RECORDS):
                _id(event_id)
                if event_id in events:
                    raise ProcedureLibraryError("Duplicate immutable procedure event identity")
                events.add(event_id)
                record = validate_procedure(_object(body, 32_768))
                if (record["id"] != record_id or record["mission_id"] != mission
                        or record["environment"] != self._environments[mission]):
                    raise ProcedureLibraryError("Procedure differs from its owning identity/environment admission")
                self._records.append(record)
                if len(self._records) > MAX_PROCEDURE_RECORDS:
                    raise ProcedureLibraryError("Library exceeds procedure record bound")

    @staticmethod
    def _rows(database: sqlite3.Connection, query: str, maximum: int) -> list[tuple]:
        rows = database.execute(query).fetchmany(maximum + 1)
        if len(rows) > maximum:
            raise ProcedureLibraryError("Historical row count exceeds bound")
        return rows

    def _load_requests(self, database: sqlite3.Connection, mission: str) -> None:
        requests, links = {}, {}
        for identity, payload, digest, state, result in self._rows(database,
                "SELECT id,payload,digest,state,result FROM requests", MAX_REQUESTS):
            _id(identity)
            request = self._request_data(mission, payload)
            request_mission = request.get("mission_id", request.get("admission", {}).get("mission_id"))
            if (identity in requests or request.get("request_id") != identity or request_mission != mission
                    or state not in _REQUEST_TERMINAL or result is None
                    or hashlib.sha256(payload.encode()).hexdigest() != digest or payload != canonical(request)):
                raise ProcedureLibraryError("Historical request identity/digest/terminal result differs")
            decoded = _object(result)
            requests[identity] = {"request": request, "state": state, "result": decoded}
            links[identity] = _sources(request, "sources") | _sources(decoded, "source_ids")
        self._requests[mission], self._links[mission] = requests, links

    def _load_primitives(self, database: sqlite3.Connection, mission: str) -> None:
        seen = set()
        positions = {}
        dispositions = {}
        for identity, parent, intent, native_id, state, result, effect in self._rows(database,
                "SELECT id,request_id,intent,native_id,state,result,effect FROM primitives ORDER BY rowid", MAX_PRIMITIVES):
            _id(identity)
            if native_id is not None:
                _id(native_id)
            if identity in seen or parent not in self._requests[mission] or state not in _PRIMITIVE_TERMINAL:
                raise ProcedureLibraryError("Historical primitive has no terminal retained request")
            seen.add(identity)
            intent = _intent(_object(intent))
            request = self._requests[mission][parent]["request"]
            _primitive_parent(intent, request)
            _ordinary_sequence(intent, request, positions.get(parent, 0), dispositions.get(parent))
            positions[parent] = positions.get(parent, 0) + 1
            dispositions[parent] = state
            MissionLedger._check_source_transition(intent, request["epoch"], mission,
                informing_sources=request["sources"])
            if state == "unknown":
                if effect is None:
                    raise ProcedureLibraryError("Historical primitive effects remain unresolved")
                resolution = validate_effect_reconciliation(_object(effect, 32_768))
                proof = resolution["proof"]
                if not set(resolution["sources"]) <= self._entries[mission].keys():
                    raise ProcedureLibraryError("Historical effect has unavailable original sources")
                if resolution["basis"] in ("DeliveryResolution", "LifecycleTransition"):
                    if proof["before_source_id"] != intent["source_before"]:
                        raise ProcedureLibraryError("Historical effect contradicts its original before-source")
                if resolution["basis"] == "LifecycleTransition" and not {
                        proof["before_source_id"], proof["after_source_id"]} <= set(resolution["sources"]):
                    raise ProcedureLibraryError("Historical transition lost its original source support")
                logical_field = "logical_id" if resolution["basis"] == "DeliveryResolution" else "terminal_logical_id"
                if proof[logical_field] != identity or intent["source_before"] not in resolution["sources"]:
                    raise ProcedureLibraryError("Historical effect does not settle this original primitive")
                if resolution["basis"] == "DeliveryResolution" and proof["original_request_id"] != parent:
                    raise ProcedureLibraryError("Historical delivery resolution belongs to another request")
                if resolution["basis"] == "LifecycleTransition" and proof["terminal_request_id"] != parent:
                    raise ProcedureLibraryError("Historical lifecycle resolution belongs to another request")
            elif effect is not None:
                raise ProcedureLibraryError("Effect resolution contradicts original primitive disposition")
            if result is None and state != "unknown":
                raise ProcedureLibraryError("Historical terminal primitive lost its receipt")
            receipt = {} if result is None else _object(result)
            self._mapping(mission, intent, receipt, logical_id=identity, native_id=native_id, disposition=state)
            if intent["kind"] in ("action", "key", "direct", "resume") and state in ("returned", "rejected"):
                self._ordinary_captures(mission, intent, receipt)
            linked = set()
            for field in ("source_before", "preflight_source"):
                linked.add(_id(intent[field]))
                if field in receipt and receipt[field] is not None and receipt[field] != intent[field]:
                    raise ProcedureLibraryError("Primitive receipt contradicts its source intent")
            if receipt.get("source_after") is not None:
                linked.add(_id(receipt["source_after"]))
            self._links[mission][parent].update(linked)

    def _ordinary_captures(self, mission: str, intent: dict, receipt: dict) -> None:
        """Audit retained capture linkage separately from known delivery."""
        entries = self._entries[mission]
        preflight = entries.get(intent["preflight_source"])
        if preflight is None:
            raise ProcedureLibraryError("Known ordinary delivery lost its retained preflight")
        request = _object(receipt["native_request_json"], 4096)
        observed = preflight["observation"]
        if (any(request[key] != observed[key] for key in ("session", "revision", "frame", "takeover_generation"))
                or request["boundary_id"] != observed["boundary"]["id"]):
            raise ProcedureLibraryError("Native admission contradicts its retained actual preflight capture")
        if receipt.get("source_after") is None:
            return
        after = entries.get(receipt["source_after"])
        if after is None:
            raise ProcedureLibraryError("Known delivery names unavailable after evidence")
        projected = compact_native_ack(after["observation"])
        # A spectator may have first retained this same capture under its own
        # request ID and transport result. All immutable capture fields agree.
        ignored = {"id", "status", "error"}
        ack = receipt["native_ack"]
        if (any(ack[key] != value for key, value in projected.items() if key not in ignored)
                or receipt["source_after"] != _identity(ack)):
            raise ProcedureLibraryError("Native ACK contradicts its retained after capture identity")

    def _validate_closure(self) -> None:
        validate_record_closure(self._records, self._pins, self._dependencies, self.validate_episode)

    def validate_episode(self, episode: dict) -> tuple[tuple[str, str], ...]:
        """Validate historical request/source linkage, never the episode's prose.

        New current-ledger revisions use this same check before accepting imported
        support. Qualification remains explicit even when two missions share IDs.
        """
        self._open()
        episode = json_object(episode)
        validate_json(episode, procedure_schema()["properties"]["support"]["items"])
        mission = _id(episode["mission_id"])
        for identity in [*episode["request_ids"], *episode["source_ids"]]:
            _id(identity)
        if mission not in self._pins:
            raise ProcedureEpisodeRefusal("Procedure episode mission is missing from pinned closure")
        linked = set()
        for identity in episode["request_ids"]:
            if identity not in self._requests[mission]:
                raise ProcedureEpisodeRefusal("Procedure episode request is not retained")
            linked.update(self._links[mission][identity])
        for identity in episode["source_ids"]:
            if identity not in self._entries[mission] or identity not in linked:
                raise ProcedureEpisodeRefusal("Procedure source is unavailable or unrelated to its episode requests")
        return tuple((mission, identity) for identity in episode["source_ids"])

    def records(self) -> tuple[dict, ...]:
        self._open()
        return tuple(deepcopy(self._records))

    def request(self, mission_id: str, request_id: str) -> dict:
        self._open()
        _id(mission_id); _id(request_id)
        try:
            return deepcopy(self._requests[mission_id][request_id])
        except KeyError as exc:
            raise ProcedureLibraryError("Unknown pinned historical request") from exc

    def source(self, mission_id: str, source_id: str) -> tuple[dict, bytes]:
        self._open()
        _id(mission_id); _id(source_id)
        try:
            metadata = self._entries[mission_id][source_id]
            data = self._frame(mission_id, EvidenceRef.from_dict(metadata["reference"]))
        except (KeyError, OSError) as exc:
            raise ProcedureLibraryError("Unknown or unavailable pinned historical source") from exc
        return deepcopy(metadata), data


def validate_record_closure(
    records: Sequence[dict], pins: dict[str, dict], dependencies: dict[str, dict[str, dict]],
    validate_episode: Callable[[dict], tuple[tuple[str, str], ...]],
) -> None:
    """One qualified closure predicate for offline validation and current imports."""
    for declared in dependencies.values():
        for mission, pin in declared.items():
            if pins.get(mission) != pin:
                raise ProcedureLibraryError("Historical admission has a missing or conflicting dependency pin")
    project_procedures(records)
    for record in records:
        owner = record["mission_id"]
        parent = record["parent"]
        needed = {episode["mission_id"] for episode in record["support"] + record["counterexamples"]}
        if parent is not None:
            needed.add(parent["mission_id"])
        if not needed <= {owner, *dependencies[owner]}:
            raise ProcedureLibraryError("Procedure predecessor/evidence mission was not admitted by its owner")
        for episode in record["support"] + record["counterexamples"]:
            validate_episode(episode)
