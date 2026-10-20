"""Single-writer durable mission accounting, not an execution queue.

SQLite owns intents, counters and immutable semantic records. The EvidenceStore
owns image retention/capacity and the controller owns every dispatch capability.
A saved intent is never an instruction to send input after reopening.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import threading
from typing import Any

from .contracts import ContractError, json_object
from .mission_contracts import (
    VERSION, MissionAdmission, SourceRevalidation, canonical, validate_handoff_binding,
    validate_handoff_result, validate_memory_entry, validate_prompt_result, validate_request,
)

DB_VERSION = 6
MAX_DATABASE_BYTES = 64 * 1024 * 1024
MAX_RECEIPT_BYTES = 65_536
MAX_EFFECT_BYTES = 4096
# SQLite overflow pages reserved in separate rows, released transactionally
# before storing results. Padding covers page rounding and small state/index edits.
RESULT_RESERVE = MAX_RECEIPT_BYTES + 16_384
# Updating an effect may rewrite a row that already contains a maximal receipt.
EFFECT_RESERVE = MAX_RECEIPT_BYTES + MAX_EFFECT_BYTES + 16_384
TERMINAL = frozenset({"completed", "failed", "stopped"})
REQUEST_STATES = frozenset({"accepted", "running", "completed", "partial", "blocked", "failed", "unknown", "paused"})
PRIMITIVE_STATES = frozenset({"prepared", "published", "returned", "rejected", "not_dispatched", "unknown"})
CAUSES = frozenset({"user", "takeover", "unknown", "internal_bootstrap", "internal_lifecycle",
                    "internal_handoff", "internal_recovery", "finishing"})
_DDL = (
    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL, epoch INTEGER NOT NULL, state TEXT NOT NULL, result TEXT, admitted_at REAL NOT NULL, deadline REAL NOT NULL)",
    "CREATE INDEX requests_phase ON requests (json_extract(payload, '$.phase_id'))",
    "CREATE TABLE primitives (id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id), intent TEXT NOT NULL, native_id TEXT UNIQUE, state TEXT NOT NULL, result TEXT, effect TEXT)",
    "CREATE TABLE memory (sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, entry_type TEXT NOT NULL, record_id TEXT NOT NULL, body TEXT NOT NULL)",
    "CREATE INDEX memory_record ON memory (entry_type, record_id, sequence)",
    "CREATE TABLE reservations (id TEXT PRIMARY KEY, space BLOB NOT NULL)",
)


class LedgerError(ContractError):
    """Invalid or unavailable accounting. Caller must revoke input before repair."""


class BudgetError(LedgerError):
    """Original budget/reserve cannot admit another side effect."""


def _id(value: Any) -> None:
    if not isinstance(value, str) or not value or len(value) > 128 or not value[0].isalnum() or not all(c.isascii() and (c.isalnum() or c in "_-") for c in value):
        raise LedgerError("Identifier must be bounded ASCII letters/digits/_/-")


def _clock(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10**12:
        raise LedgerError("Clock must be a finite nonnegative epoch time")
    return float(value)


def _json(value: dict, maximum=65_536) -> str:
    data = canonical(json_object(value))
    if len(data.encode()) > maximum:
        raise LedgerError("Ledger record exceeds byte limit")
    return data


def _intent(value: dict | str) -> dict:
    data = json_object(value)
    expected = {"kind", "value", "expected_session", "expected_revision", "expected_boundary_id",
                "source_before", "preflight_source", "revalidation", "reservation_id"}
    if set(data) != expected or data["kind"] not in ("action", "key", "resume"):
        raise LedgerError("Primitive intent fields do not match")
    for key in ("expected_session", "expected_boundary_id", "source_before", "preflight_source", "reservation_id"): _id(data[key])
    if data["revalidation"] is not None:
        refreshed = SourceRevalidation.from_dict(data["revalidation"])
        if refreshed.current.source_id != data["source_before"]:
            raise LedgerError("Revalidation current source differs from the proposal before-source")
    if type(data["expected_revision"]) is not int or data["expected_revision"] < 0:
        raise LedgerError("Primitive requires exact observed revision")
    if data["kind"] == "resume":
        if data["value"] is not None:
            raise LedgerError("Resume has no action/key value")
    elif not isinstance(data["value"], str) or not 1 <= len(data["value"]) <= 160:
        raise LedgerError("Primitive requires bounded action/key")
    return data


def _effect(value: dict | str) -> dict:
    data = json_object(value)
    if set(data) != {"sources", "note"} or type(data["sources"]) is not list:
        raise LedgerError("Malformed reconciliation evidence")
    sources = data["sources"]
    if not 1 <= len(sources) <= 8:
        raise LedgerError("Reconciliation requires bounded source identities")
    for source in sources: _id(source)
    if len(set(sources)) != len(sources): raise LedgerError("Reconciliation sources must be distinct")
    if not isinstance(data["note"], str) or not 1 <= len(data["note"]) <= 1024:
        raise LedgerError("Reconciliation requires a reason")
    _json(data, MAX_EFFECT_BYTES)
    return data


class MissionLedger:
    """One caller-owned directory, one locked connection, no dispatch imports.

    `now` is supplied real wall time. Reopen pauses and advances the advisory
    epoch, preserving original deadlines and all potentially spent inputs.
    Source files and SQLite's normal journal are not a distributed transaction.
    """
    def __init__(self, directory: Path, *, now: float, admission: MissionAdmission | None = None):
        now = _clock(now)
        path = Path(directory)
        if path.is_symlink(): raise LedgerError("Ledger directory cannot be a symlink")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory = path.resolve()
        self.path = self.directory / "mission.sqlite3"
        for p in [self.path, self.directory / "mission.lock", self.directory / "mission.sqlite3-journal"]:
            if p.is_symlink() or (p.exists() and not p.is_file()):
                raise LedgerError("Unexpected non-regular ledger file")
        self._mutex = threading.RLock()
        self._lock = (self.directory / "mission.lock").open("a+b")
        self._db: sqlite3.Connection | None = None
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            exists = self.path.exists()
            if not exists and admission is None:
                raise LedgerError("A new ledger requires explicit admission")
            if admission is not None and type(admission) is not MissionAdmission:
                raise LedgerError("Admission must be a validated immutable record")
            self._db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
            if exists and self._db.execute("PRAGMA user_version").fetchone()[0] != DB_VERSION:
                raise LedgerError("Unsupported mission ledger version; no automatic migration")
            if self.path.stat().st_size > MAX_DATABASE_BYTES:
                raise LedgerError("Existing ledger exceeds database ceiling")
            self.path.chmod(0o600)
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("PRAGMA journal_mode=DELETE")
            page = self._db.execute("PRAGMA page_size").fetchone()[0]
            self._db.execute(f"PRAGMA max_page_count={MAX_DATABASE_BYTES // page}")
            if not exists:
                with self._transaction():
                    for statement in _DDL: self._db.execute(statement)
                    self._db.execute(f"PRAGMA user_version={DB_VERSION}")
                    self._put("admission", admission.to_dict())
                    self._put("state", dict(phase="admitted", epoch=0, player_id=admission.player_id,
                                             pause_cause="internal_bootstrap", reason="Explicit admission; no input authority",
                                             started_at=now, deadline=now + admission.limits.wall_seconds,
                                             last_wall=now, spent_inputs=0))
            self._verify(admission)
            self.admission = MissionAdmission.from_dict(self._get("admission"))
            if exists:
                with self._transaction():
                    state = self._get("state")
                    self._db.execute("UPDATE primitives SET state='unknown' WHERE state IN ('prepared','published')")
                    self._db.execute("UPDATE requests SET state='unknown' WHERE state IN ('accepted','running')")
                    state["epoch"] += 1
                    if state["phase"] not in TERMINAL:
                        state["phase"] = "paused"
                        state["pause_cause"] = "unknown"
                        state["reason"] = "Reopened without authority; reconcile interrupted intents"
                    if now < state["last_wall"] and state["phase"] not in TERMINAL:
                        state["reason"] = "Wall clock moved backward; remaining budget unprovable"
                    state["last_wall"] = max(now, state["last_wall"])
                    self._put("state", state)
        except Exception as exc:
            self.close()
            if isinstance(exc, (LedgerError, ContractError)): raise
            raise LedgerError(f"Cannot open mission ledger: {exc}") from exc

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def close(self):
        with self._mutex:
            if self._db is not None:
                self._db.close()
                self._db = None
            if not self._lock.closed: self._lock.close()

    @contextmanager
    def _transaction(self):
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            self._observed_wall = None
            try:
                self._db.execute("BEGIN IMMEDIATE")
                yield
                self._db.execute("COMMIT")
            except BaseException as exc:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                # Rejection rolls back intent/cost, never an observed clock advance.
                # Persist separately so expiry followed by wall-clock rollback cannot
                # renew dispatch authority. Storage failure closes this writer.
                if self._observed_wall is not None:
                    try:
                        state = self._get("state")
                        if self._observed_wall > state["last_wall"]:
                            self._db.execute("BEGIN IMMEDIATE")
                            state["last_wall"] = self._observed_wall
                            self._put("state", state)
                            self._db.execute("COMMIT")
                    except Exception as clock_exc:
                        self.close()
                        raise LedgerError("Cannot retain clock watermark; ledger closed") from clock_exc
                if isinstance(exc, sqlite3.Error):
                    raise LedgerError(f"Mission transaction failed: {exc}") from exc
                raise

    def _get(self, key):
        row = self._db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        if row is None: raise LedgerError("Required ledger metadata missing")
        return json_object(row[0])

    def _put(self, key, value):
        self._db.execute("INSERT INTO metadata(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (key, _json(value)))

    def _reserve(self, identity: str, size: int) -> None:
        self._db.execute("INSERT INTO reservations(id,space) VALUES (?,zeroblob(?))", (identity, size))

    def _release(self, identity: str) -> None:
        # DELETE frees overflow pages before UPDATE needs them; shrinking a blob
        # in the primitive row can itself require allocation on a full database.
        self._db.execute("DELETE FROM reservations WHERE id=?", (identity,))

    def _verify(self, admission):
        if self._db.execute("PRAGMA user_version").fetchone()[0] != DB_VERSION:
            raise LedgerError("Unsupported mission ledger version; no automatic migration")
        if self._db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise LedgerError("Mission ledger integrity check failed")
        stored = MissionAdmission.from_dict(self._get("admission"))
        if admission is not None and stored != admission:
            raise LedgerError("Original admission/configuration cannot be replaced")
        state = self._get("state")
        keys = {"phase", "epoch", "player_id", "pause_cause", "reason", "started_at", "deadline", "last_wall", "spent_inputs"}
        if set(state) != keys or state["phase"] not in TERMINAL | {"admitted", "active", "paused", "reconciling", "handoff", "finishing"}:
            raise LedgerError("Malformed mission state")
        if not isinstance(state["reason"], str) or not 1 <= len(state["reason"]) <= 1024:
            raise LedgerError("Malformed mission reason")
        if state["pause_cause"] not in CAUSES or type(state["epoch"]) is not int or state["epoch"] < 0:
            raise LedgerError("Malformed mission epoch/cause")
        _id(state["player_id"])
        for key in ("started_at", "deadline", "last_wall"): _clock(state[key])
        if state["deadline"] != state["started_at"] + stored.limits.wall_seconds or state["last_wall"] < state["started_at"]:
            raise LedgerError("Original mission clock was altered")
        expected_reservations = {}
        phase_roots = {}
        for rowid, request_id, payload, digest, epoch, status, result, admitted_at, deadline in self._db.execute("SELECT rowid,id,payload,digest,epoch,state,result,admitted_at,deadline FROM requests ORDER BY rowid"):
            data = validate_request(payload)
            if (data.get("request_id") != request_id or hashlib.sha256(payload.encode()).hexdigest() != digest
                    or payload != _json(data) or status not in REQUEST_STATES or type(epoch) is not int or epoch < 0
                    or epoch > state["epoch"] or data.get("epoch", epoch) != epoch
                    or data.get("mission_id", data.get("admission", {}).get("mission_id")) != stored.mission_id):
                raise LedgerError("Corrupt request identity/state")
            if result is not None and (result != _json(json_object(result)) or status in ("accepted", "running")):
                raise LedgerError("Corrupt operation result")
            if result is None: expected_reservations[f"request:{request_id}"] = RESULT_RESERVE
            _clock(admitted_at); _clock(deadline)
            if admitted_at < state["started_at"] or admitted_at > state["last_wall"]:
                raise LedgerError("Corrupt operation admission time")
            if deadline < admitted_at or (deadline > state["deadline"] and data["kind"] not in ("observe", "reconcile", "stop")):
                raise LedgerError("Corrupt operation deadline")
            root = self._phase_parent(data, before_rowid=rowid)
            if data["kind"] in ("skill", "lifecycle"):
                expected_deadline = min(state["deadline"], admitted_at + data["limits"]["wall_seconds"])
                if root is not None:
                    expected_deadline = min(expected_deadline, root["deadline"])
                if deadline != expected_deadline:
                    raise LedgerError("Original operation/phase deadline was altered")
                if self._is_phase_root(data): phase_roots[request_id] = data["limits"]["primitives"]
        if self._db.execute("SELECT count(*) FROM requests").fetchone()[0] > stored.limits.requests:
            raise LedgerError("Request retention exceeded")
        work_lineage = {}
        for event_id, entry_type, record_id, body in self._db.execute("SELECT event_id,entry_type,record_id,body FROM memory ORDER BY sequence"):
            _id(event_id)
            entry = validate_memory_entry(body, entry_type)
            if entry["id"] != record_id or entry["scope"]["mission_id"] != stored.mission_id:
                raise LedgerError("Corrupt semantic record scope")
            if entry_type == "work":
                self._check_work_lineage(entry, work_lineage)
                work_lineage[entry["id"]] = entry
        issued, consumed = self._handoffs(state=state)
        actors = [(0, stored.player_id)] + sorted((issued[identity]["epoch"], self.request(claim)["result"]["player_id"])
                                                 for identity, claim in consumed.items())
        for request_id, payload, result in self._db.execute("SELECT id,payload,result FROM requests WHERE result IS NOT NULL"):
            data = json_object(payload)
            actor = next(player for epoch, player in reversed(actors) if epoch <= data.get("epoch", 0))
            self._check_prompt_result(request_id, data, json_object(result), actor_id=actor)
        count = 0
        for logical_id, request_id, intent, native_id, status, result, effect in self._db.execute(
                "SELECT id,request_id,intent,native_id,state,result,effect FROM primitives"):
            _id(logical_id)
            if native_id is not None: _id(native_id)
            if status not in PRIMITIVE_STATES: raise LedgerError("Corrupt primitive state")
            data = _intent(intent)
            if intent != _json(data): raise LedgerError("Noncanonical primitive intent")
            parent = self.request(request_id)
            if parent["request"]["kind"] not in ("skill", "lifecycle"):
                raise LedgerError("Primitive lost its executable parent")
            if data["kind"] == "resume" and parent["request"]["kind"] != "lifecycle":
                raise LedgerError("Resume requires an admitted lifecycle parent")
            actor = next(player for epoch, player in reversed(actors) if epoch <= parent["epoch"])
            self._check_revalidation(data, parent["epoch"], stored.mission_id,
                                     informing_sources=parent["request"]["sources"], actor_id=actor)
            if status == "prepared" and native_id is not None or status == "published" and native_id is None:
                raise LedgerError("Corrupt publication identity")
            if result is not None:
                if result != _json(json_object(result)) or status in ("prepared", "published"):
                    raise LedgerError("Corrupt primitive receipt")
            elif status not in ("prepared", "published", "unknown"):
                raise LedgerError("Terminal primitive lost its receipt")
            if effect is not None and (status != "unknown" or effect != _json(_effect(effect))):
                raise LedgerError("Corrupt primitive effect evidence")
            if result is None: expected_reservations[f"receipt:{logical_id}"] = RESULT_RESERVE
            if effect is None and status in ("prepared", "published", "unknown"):
                expected_reservations[f"effect:{logical_id}"] = EFFECT_RESERVE
            count += 1
        reservations = dict(self._db.execute("SELECT id,length(space) FROM reservations"))
        if reservations != expected_reservations:
            raise LedgerError("Terminal receipt reservations lost or altered")
        for payload, count_per_request in self._db.execute("SELECT r.payload,count(p.id) FROM requests r JOIN primitives p ON p.request_id=r.id GROUP BY r.id"):
            if count_per_request > json_object(payload)["limits"]["primitives"]:
                raise LedgerError("Operation primitive ceiling was exceeded")
        for root_id, limit in phase_roots.items():
            if self._phase_primitive_count(root_id) > limit:
                raise LedgerError("Phase primitive ceiling was exceeded")
        if type(state["spent_inputs"]) is not int or state["spent_inputs"] != count or count > stored.limits.inputs:
            raise LedgerError("Spent inputs differ from immutable primitive mappings")
        if self._db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise LedgerError("Primitive lost its semantic request")

    def _handoffs(self, *, state: dict | None = None) -> tuple[dict, dict]:
        """Derive one-use consumption from existing immutable request results.

        At most sixteen issuances, no copied mutable consumption pointer/table.
        Reopen validates the actor chain as well as individual closed receipts.
        """
        admission = MissionAdmission.from_dict(self._get("admission"))
        issued, consumed = {}, {}
        player, previous_epoch = admission.player_id, -1
        for identity, payload, status, result in self._db.execute(
                "SELECT id,payload,state,result FROM requests ORDER BY rowid"):
            data = json_object(payload)
            if data["kind"] not in ("handoff", "claim") or status != "completed":
                continue
            receipt = validate_handoff_result(json_object(result), claimed=data["kind"] == "claim")
            if receipt["mission_id"] != admission.mission_id:
                raise LedgerError("Handoff receipt belongs to another mission")
            if data["kind"] == "handoff":
                if (receipt["handoff_id"] != identity or receipt["epoch"] != data["epoch"] + 1
                        or receipt["epoch"] <= previous_epoch
                        or receipt["original_player_id"] != player
                        or receipt["successor_role"] != data["successor_role"]
                        or receipt["checkpoint_ids"] != data["checkpoint_ids"]
                        or receipt["pause_origin"] in ("human", "fault")):
                    raise LedgerError("Handoff issuance contradicts request/actor chain")
                issued[identity] = receipt
                previous_epoch = receipt["epoch"]
            else:
                handoff = issued.get(data["handoff_id"])
                if (handoff is None or data["handoff_id"] in consumed
                        or data["epoch"] != handoff["epoch"]
                        or player != handoff["original_player_id"]
                        or data["player_id"] == player
                        or receipt != self._claim_receipt(data, handoff["successor_role"])):
                    raise LedgerError("Claim lost its one-use issuance/actor binding")
                self._claim_binding(data, handoff)
                consumed[data["handoff_id"]] = identity
                player = data["player_id"]
        if len(issued) > 16:
            raise LedgerError("Handoff retention ceiling exceeded")
        if state is not None:
            if state["player_id"] != player or any(h["epoch"] > state["epoch"] for h in issued.values()):
                raise LedgerError("Mission actor/epoch contradicts handoff history")
            pending = [h for key, h in issued.items() if key not in consumed and h["epoch"] == state["epoch"]]
            if state["phase"] == "handoff" and (len(pending) != 1 or state["pause_cause"] != "internal_handoff"):
                raise LedgerError("Handoff phase lost its eligible issuance")
            if state["phase"] == "active" and pending:
                raise LedgerError("Unconsumed handoff cannot be active")
        return issued, consumed

    @staticmethod
    def _claim_receipt(data: dict, role: str) -> dict:
        return {"schema": VERSION, "record_type": "ClaimedHandoff", "handoff_id": data["handoff_id"],
                "mission_id": data["mission_id"], "player_id": data["player_id"],
                "actor_role": role, "epoch": data["epoch"], "grants_authority": False}

    @staticmethod
    def _claim_binding(data: dict, handoff: dict) -> None:
        for requested, issued in (("expected_session", "session"), ("expected_revision", "revision"),
                                  ("expected_boundary_id", "boundary_id"), ("expected_pause_origin", "pause_origin"),
                                  ("pause_generation", "pause_generation"), ("takeover_generation", "takeover_generation")):
            if data[requested] != handoff[issued]:
                raise LedgerError("Claim differs from the exact post-Pause handoff binding")

    def _settled_transition(self, request_id: str, result: dict) -> None:
        self._release(f"request:{request_id}")
        self._db.execute("UPDATE requests SET state='completed',result=? WHERE id=?", (_json(result), request_id))

    def _quiescent(self, except_request: str, *, competing_claim: str | None = None) -> None:
        if self._db.execute("SELECT 1 FROM primitives WHERE state IN ('prepared','published') OR (state='unknown' AND effect IS NULL)").fetchone():
            raise LedgerError("Handoff requires reconciled primitive effects")
        for payload, in self._db.execute("SELECT payload FROM requests WHERE id<>? AND state IN ('accepted','running')", (except_request,)):
            data = json_object(payload)
            if competing_claim is None or data["kind"] != "claim" or data["handoff_id"] != competing_claim:
                raise LedgerError("Handoff requires settled other semantic work")

    def issue_handoff(self, request_id: str, *, binding: dict, now: float) -> dict:
        """Record runtime-attested quiescence; no Pause or Resume is sent here."""
        binding = validate_handoff_binding(binding)
        if binding["pause_origin"] in ("human", "fault"):
            raise LedgerError("Human/fault Pause cannot be relabelled as internal handoff")
        with self._transaction():
            operation = self.request(request_id)
            data = operation["request"]
            if data["kind"] != "handoff": raise LedgerError("Issuance requires a handoff request")
            issued, consumed = self._handoffs()
            if request_id in issued:
                if any(issued[request_id][key] != value for key, value in binding.items()):
                    raise LedgerError("Handoff issuance cannot be rebound")
                return json_object(issued[request_id])
            if operation["result"] is not None: raise LedgerError("Handoff operation already settled")
            state = self._touch(now, dispatch=True)
            if data["epoch"] != state["epoch"] or now >= operation["deadline"]:
                raise LedgerError("Handoff epoch/deadline expired")
            self._quiescent(request_id)
            if len(issued) >= 16: raise BudgetError("Handoff count exhausted")
            if any(h["epoch"] == state["epoch"] and key not in consumed for key, h in issued.items()):
                raise LedgerError("Another eligible handoff is pending")
            result = validate_handoff_result({**binding, "schema": VERSION, "record_type": "Handoff",
                "mission_id": self.admission.mission_id, "handoff_id": request_id,
                "original_player_id": state["player_id"], "successor_role": data["successor_role"],
                "epoch": state["epoch"] + 1, "checkpoint_ids": data["checkpoint_ids"], "grants_authority": False})
            self._settled_transition(request_id, result)
            state.update(phase="handoff", epoch=result["epoch"], pause_cause="internal_handoff",
                         reason="Runtime attested quiescent internal handoff; no input authority")
            self._put("state", state)
        return json_object(result)

    def consume_handoff(self, request_id: str, *, actor_id: str, actor_role: str, now: float) -> dict:
        """Runtime compares its designated actor context; IDs are audit, not authentication."""
        _id(actor_id); _id(actor_role)
        with self._transaction():
            operation = self.request(request_id)
            data = operation["request"]
            if data["kind"] != "claim" or data["player_id"] != actor_id:
                raise LedgerError("Claim differs from designated runtime actor")
            issued, consumed = self._handoffs()
            handoff = issued.get(data["handoff_id"])
            if handoff is None or handoff["successor_role"] != actor_role:
                raise LedgerError("Claim differs from issued successor role")
            self._claim_binding(data, handoff)
            if consumed.get(data["handoff_id"]) == request_id:
                return json_object(operation["result"])
            if data["handoff_id"] in consumed or operation["result"] is not None:
                raise LedgerError("Handoff already consumed or claim settled")
            state = self._touch(now)
            if (state["phase"] != "handoff" or state["pause_cause"] != "internal_handoff"
                    or data["epoch"] != state["epoch"] or handoff["epoch"] != state["epoch"]
                    or data["player_id"] == state["player_id"]):
                raise LedgerError("Handoff was invalidated or actor context was not replaced")
            if now >= min(operation["deadline"], self.request(data["handoff_id"])["deadline"],
                          state["deadline"] - self.admission.cleanup_reserve.wall_seconds):
                raise BudgetError("Claim cannot renew original operation/ordinary mission budget")
            self._quiescent(request_id, competing_claim=data["handoff_id"])
            result = validate_handoff_result(self._claim_receipt(data, actor_role), claimed=True)
            self._settled_transition(request_id, result)
            state.update(phase="paused", player_id=actor_id, reason="Handoff consumed; fresh runtime readmission still required")
            self._put("state", state)
        return json_object(result)

    def snapshot(self, *, now: float) -> dict:
        now = _clock(now)
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            state = self._get("state")
            return {**state, "mission_id": self.admission.mission_id,
                    "remaining_inputs": self.admission.limits.inputs - state["spent_inputs"],
                    "remaining_wall_seconds": max(0, state["deadline"] - now),
                    "clock_valid": now >= state["last_wall"],
                    "unreconciled": self._db.execute("SELECT count(*) FROM primitives WHERE state='unknown' AND effect IS NULL").fetchone()[0],
                    "grants_authority": False}

    def _touch(self, now, *, dispatch=False, cleanup=False):
        now = _clock(now)
        state = self._get("state")
        if now < state["last_wall"]: raise BudgetError("Clock rollback; do not renew mission time")
        self._observed_wall = now
        if dispatch:
            reserve = 0 if cleanup else self.admission.cleanup_reserve.wall_seconds
            if now >= state["deadline"] - reserve:
                raise BudgetError("Original wall budget or cleanup reserve exhausted")
            if state["phase"] not in ({"finishing"} if cleanup else {"active"}):
                raise LedgerError("Mission phase cannot dispatch ordinary input")
        state["last_wall"] = now
        self._put("state", state)
        return state

    def activate(self, *, epoch: int, player_id: str, now: float) -> dict:
        """Record runtime-verified readmission, never issue or restore a lease."""
        _id(player_id)
        with self._transaction():
            state = self._touch(now)
            if type(epoch) is not int or epoch != state["epoch"] or state["phase"] in TERMINAL | {"handoff"} or player_id != state["player_id"]:
                raise LedgerError("Stale epoch, actor change without handoff or terminal mission")
            if now >= state["deadline"] - self.admission.cleanup_reserve.wall_seconds:
                raise BudgetError("Readmission cannot renew the ordinary wall budget")
            if self._db.execute("SELECT 1 FROM primitives WHERE state IN ('prepared','published') OR (state='unknown' AND effect IS NULL)").fetchone():
                raise LedgerError("Unsettled/unknown primitives require explicit reconciliation")
            state.update(phase="active", player_id=player_id, reason="Runtime recorded deliberate fresh readmission")
            self._put("state", state)
        return self.snapshot(now=now)

    def pause(self, *, cause: str, reason: str, now: float) -> dict:
        if cause not in CAUSES or not isinstance(reason, str) or not 1 <= len(reason) <= 1024:
            raise LedgerError("Invalid pause cause/reason")
        with self._transaction():
            state = self._touch(now)
            if state["phase"] not in TERMINAL:
                state.update(phase="paused", epoch=state["epoch"] + 1, pause_cause=cause, reason=reason)
                self._put("state", state)
        return self.snapshot(now=now)

    def begin_finishing(self, *, epoch: int, reason: str, now: float) -> dict:
        """Record deliberate cleanup phase after runtime has revoked ordinary input."""
        if not isinstance(reason, str) or not 1 <= len(reason) <= 1024:
            raise LedgerError("Finishing needs a bounded reason")
        with self._transaction():
            state = self._touch(now)
            if type(epoch) is not int or epoch != state["epoch"] or state["phase"] in TERMINAL:
                raise LedgerError("Stale or terminal cleanup transition")
            if self._db.execute("SELECT 1 FROM primitives WHERE state IN ('prepared','published') OR (state='unknown' AND effect IS NULL)").fetchone():
                raise LedgerError("Reconcile unknown work before cleanup input")
            state.update(phase="finishing", epoch=state["epoch"] + 1, pause_cause="finishing", reason=reason)
            self._put("state", state)
        return self.snapshot(now=now)

    def begin_request(self, value: dict, *, now: float) -> dict:
        data = validate_request(value)
        if data["kind"] in ("status", "result", "context"): raise LedgerError("Read-only request is not executable work")
        encoded = _json(data); digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self._transaction():
            prior = self._db.execute("SELECT payload FROM requests WHERE id=?", (data["request_id"],)).fetchone()
            if prior:
                if prior[0] != encoded: raise LedgerError("Request ID reused with different payload")
                return {"created": False, "operation": self.request(data["request_id"])}
            state = self._touch(now)
            if now >= state["deadline"] and data["kind"] not in ("observe", "reconcile", "stop"):
                raise BudgetError("Original mission deadline exhausted")
            mission = data.get("mission_id", data.get("admission", {}).get("mission_id"))
            if mission != self.admission.mission_id or data.get("epoch", state["epoch"]) != state["epoch"]:
                raise LedgerError("Request belongs to another mission/epoch")
            if data["kind"] == "skill" and data["skill_kind"] not in self.admission.allowed_skills:
                raise LedgerError("Skill not admitted")
            if data["kind"] == "lifecycle":
                if data["operation"] not in self.admission.allowed_lifecycle:
                    raise LedgerError("Lifecycle operation not admitted")
                if (data["world"], data["character"]) != (self.admission.scenario.world, self.admission.scenario.character):
                    raise LedgerError("Lifecycle identity differs from admitted scenario")
            if data["kind"] == "start" and MissionAdmission.from_dict(data["admission"]) != self.admission:
                raise LedgerError("Start cannot replace admission")
            if state["phase"] in TERMINAL: raise LedgerError("Mission is terminal")
            if self._db.execute("SELECT count(*) FROM requests").fetchone()[0] >= self.admission.limits.requests:
                raise BudgetError("Semantic request count exhausted")
            deadline = (now + 15 if data["kind"] in ("observe", "reconcile", "stop")
                        else min(state["deadline"], now + data.get("limits", {}).get("wall_seconds", self.admission.limits.wall_seconds)))
            root = self._phase_parent(data)
            if root is not None:
                if now >= root["deadline"]: raise BudgetError("Original phase deadline expired")
                deadline = min(deadline, root["deadline"])
            self._db.execute("INSERT INTO requests(id,payload,digest,epoch,state,admitted_at,deadline) VALUES (?,?,?,?,'accepted',?,?)",
                             (data["request_id"], encoded, digest, state["epoch"], now, deadline))
            self._reserve(f"request:{data['request_id']}", RESULT_RESERVE)
        return {"created": True, "operation": self.request(data["request_id"])}

    @staticmethod
    def _is_phase_root(data: dict) -> bool:
        return data.get("phase_id") is None and (data["kind"] == "lifecycle"
            or data["kind"] == "skill" and data["skill_kind"] in ("item", "activity", "interact"))

    def _phase_parent(self, data: dict, *, before_rowid: int | None = None) -> dict | None:
        """Validate a direct immutable accounting link, never live input authority."""
        parent_id = data.get("phase_id")
        if parent_id is None: return None
        row = self._db.execute("SELECT rowid,payload,digest,epoch,admitted_at,deadline FROM requests WHERE id=?", (parent_id,)).fetchone()
        if row is None or parent_id == data["request_id"] or (before_rowid is not None and row[0] >= before_rowid):
            raise LedgerError("Phase parent must be an earlier existing direct root")
        root = validate_request(row[1])
        if (root.get("request_id") != parent_id or row[1] != _json(root)
                or hashlib.sha256(row[1].encode()).hexdigest() != row[2]
                or root.get("epoch") != row[3] or not self._is_phase_root(root)
                or root["mission_id"] != data["mission_id"] or data["epoch"] < root["epoch"]):
            raise LedgerError("Phase parent identity, kind or epoch differs")
        if data["kind"] == "skill":
            if data["skill_kind"] not in ("menu", "edit", "interact", "inspect"):
                raise LedgerError("Phase skill child must be a direct control operation")
            if root.get("skill_kind") == "interact" and data["skill_kind"] == "interact":
                raise LedgerError("Ordinary interaction returns to normal play before another interaction root")
        elif data["kind"] == "lifecycle":
            if root["kind"] != "lifecycle" or any(data[key] != root[key] for key in ("operation", "world", "character")):
                raise LedgerError("Lifecycle child differs from its phase root")
        else:
            raise LedgerError("Phase child must be executable work")
        admitted_at, deadline = _clock(row[4]), _clock(row[5])
        mission_deadline = self._get("state")["deadline"]
        if deadline != min(mission_deadline, admitted_at + root["limits"]["wall_seconds"]):
            raise LedgerError("Original phase deadline was altered")
        return {"request": root, "deadline": deadline}

    def _phase_primitive_count(self, root_id: str) -> int:
        # The indexed direct-root selection includes each request once. Existing
        # primitive rows retain rejected/unknown costs without another counter.
        return self._db.execute("SELECT count(*) FROM primitives WHERE request_id IN "
            "(SELECT id FROM requests WHERE id=? OR json_extract(payload, '$.phase_id')=?)",
            (root_id, root_id)).fetchone()[0]

    def request(self, request_id: str) -> dict:
        _id(request_id)
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            row = self._db.execute("SELECT payload,epoch,state,result,admitted_at,deadline FROM requests WHERE id=?", (request_id,)).fetchone()
            if row is None: raise LedgerError("Unknown semantic request")
            return {"request": json_object(row[0]), "epoch": row[1], "state": row[2],
                    "result": None if row[3] is None else json_object(row[3]),
                    "admitted_at": row[4], "deadline": row[5]}

    def request_records(self) -> tuple[dict, ...]:
        """Ordered copied audit history; never restore an executor or process handle."""
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            ids = [row[0] for row in self._db.execute("SELECT id FROM requests ORDER BY rowid")]
            return tuple(self.request(identity) for identity in ids)

    def prepare_primitive(self, request_id: str, logical_id: str, intent: dict, *, now: float,
                          cleanup=False) -> dict:
        """Call after EvidenceStore reservation, before any transport publication.

        Image capacity is owned by EvidenceStore; its reservation/source IDs are
        recorded inside intent, not another ledger image counter or copy.
        """
        _id(request_id); _id(logical_id)
        data = _intent(intent)
        if type(cleanup) is not bool: raise LedgerError("Cleanup intent must be explicit")
        encoded = _json(data)
        with self._transaction():
            prior = self._db.execute("SELECT request_id,intent FROM primitives WHERE id=?", (logical_id,)).fetchone()
            if prior:
                if prior != (request_id, encoded): raise LedgerError("Logical ID reused with different intent")
                return {"created": False, "primitive": self.primitive(logical_id)}
            state = self._touch(now, dispatch=True, cleanup=cleanup)
            request = self.request(request_id)
            if request["request"]["kind"] not in ("skill", "lifecycle"):
                raise LedgerError("Only an admitted skill/lifecycle can propose input")
            if data["kind"] == "resume" and request["request"]["kind"] != "lifecycle":
                raise LedgerError("Resume requires an admitted lifecycle parent")
            if now >= request["deadline"]:
                raise BudgetError("Original operation deadline expired")
            count = self._db.execute("SELECT count(*) FROM primitives WHERE request_id=?", (request_id,)).fetchone()[0]
            if count >= request["request"]["limits"]["primitives"]:
                raise BudgetError("Per-operation primitive limit exhausted")
            if request["epoch"] != state["epoch"] or request["state"] not in ("accepted", "running"):
                raise LedgerError("Request is stale or no longer dispatchable")
            root = self._phase_parent(request["request"])
            if root is None and self._is_phase_root(request["request"]): root = request
            if root is not None:
                if now >= root["deadline"]: raise BudgetError("Original phase deadline expired")
                if self._phase_primitive_count(root["request"]["request_id"]) >= root["request"]["limits"]["primitives"]:
                    raise BudgetError("Phase primitive limit exhausted")
            self._check_revalidation(data, request["epoch"], self.admission.mission_id,
                                     informing_sources=request["request"]["sources"], actor_id=state["player_id"])
            reserve = 0 if cleanup else self.admission.cleanup_reserve.inputs
            if state["spent_inputs"] >= self.admission.limits.inputs - reserve:
                raise BudgetError("Input budget or cleanup reserve exhausted")
            if self._db.execute("SELECT 1 FROM primitives WHERE state IN ('prepared','published') OR (state='unknown' AND effect IS NULL)").fetchone():
                raise LedgerError("Another primitive is unsettled/unknown")
            if state["spent_inputs"] >= self.admission.limits.primitive_mappings:
                raise BudgetError("Primitive mapping count exhausted")
            self._db.execute("INSERT INTO primitives(id,request_id,intent,state) VALUES (?,?,?,'prepared')", (logical_id, request_id, encoded))
            self._reserve(f"receipt:{logical_id}", RESULT_RESERVE)
            self._reserve(f"effect:{logical_id}", EFFECT_RESERVE)
            self._db.execute("UPDATE requests SET state='running' WHERE id=?", (request_id,))
            state["spent_inputs"] += 1
            self._put("state", state)
        return {"created": True, "primitive": self.primitive(logical_id)}

    @staticmethod
    def _check_revalidation(intent: dict, epoch: int, mission_id: str, *, informing_sources: list[str],
                            actor_id: str | None = None) -> None:
        if intent["revalidation"] is not None:
            refreshed = SourceRevalidation.from_dict(intent["revalidation"])
            current = refreshed.current
            if current.epoch != epoch or current.mission_id != mission_id or (actor_id is not None and current.actor_id != actor_id):
                raise LedgerError("Revalidation belongs to another mission/epoch/actor")
            if refreshed.original.source_id not in informing_sources:
                raise LedgerError("Revalidation original source did not inform the immutable request")

    def primitive(self, logical_id: str) -> dict:
        _id(logical_id)
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            row = self._db.execute("SELECT request_id,intent,native_id,state,result,effect FROM primitives WHERE id=?", (logical_id,)).fetchone()
            if row is None: raise LedgerError("Unknown logical primitive")
            return dict(logical_id=logical_id, request_id=row[0], intent=json_object(row[1]), native_id=row[2],
                        state=row[3], result=None if row[4] is None else json_object(row[4]),
                        effect=None if row[5] is None else json_object(row[5]))

    def primitive_records(self) -> tuple[dict, ...]:
        """Bounded copied effect history for memory reduction; never an outbox.

        Includes prepared/unknown intents so consumers cannot treat an uncertain
        state-changing input as evidence that old dynamic facts remain current.
        """
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            ids = [row[0] for row in self._db.execute("SELECT id FROM primitives ORDER BY rowid")]
            return tuple(self.primitive(identity) for identity in ids)

    def published(self, logical_id: str, native_id: str, *, now: float) -> dict:
        _id(native_id)
        with self._transaction():
            self._touch(now)
            p = self.primitive(logical_id)
            if p["state"] == "published" and p["native_id"] == native_id: return p
            if p["state"] != "prepared": raise LedgerError("Only prepared input can be marked published")
            self._db.execute("UPDATE primitives SET native_id=?,state='published' WHERE id=?", (native_id, logical_id))
        return self.primitive(logical_id)

    def settle_primitive(self, logical_id: str, disposition: str, result: dict, *, now: float) -> dict:
        if disposition not in PRIMITIVE_STATES - {"prepared", "published"}: raise LedgerError("Invalid terminal disposition")
        encoded = _json(result)
        with self._transaction():
            state = self._touch(now)
            p = self.primitive(logical_id)
            if p["state"] not in ("prepared", "published"):
                if p["state"] == disposition and p["result"] == json_object(encoded): return p
                raise LedgerError("Terminal receipt cannot be rewritten")
            self._release(f"receipt:{logical_id}")
            if disposition != "unknown":
                self._release(f"effect:{logical_id}")
            self._db.execute("UPDATE primitives SET state=?,result=? WHERE id=?", (disposition, encoded, logical_id))
            if disposition == "unknown":
                if state["phase"] not in TERMINAL | {"paused"}:
                    state.update(phase="paused", epoch=state["epoch"] + 1, pause_cause="unknown", reason="Unknown input; observe without replay")
                    self._put("state", state)
                self._db.execute("UPDATE requests SET state='unknown' WHERE id=?", (p["request_id"],))
        return self.primitive(logical_id)

    def reconcile_effect(self, logical_id: str, *, sources: tuple[str, ...], note: str, now: float) -> dict:
        """Record controller-verified reconciliation, keeping original ACK unknown."""
        if type(sources) is not tuple: raise LedgerError("Reconciliation sources must be an explicit tuple")
        effect = _effect({"sources": list(sources), "note": note})
        with self._transaction():
            self._touch(now)
            p = self.primitive(logical_id)
            if p["state"] != "unknown": raise LedgerError("Only unknown effects require this reconciliation")
            if p["effect"] is not None:
                if p["effect"] == effect: return p
                raise LedgerError("Reconciliation is immutable")
            self._release(f"effect:{logical_id}")
            self._db.execute("UPDATE primitives SET effect=? WHERE id=?", (_json(effect), logical_id))
        return self.primitive(logical_id)

    def _check_prompt_result(self, request_id: str, data: dict, result: dict, *, actor_id: str) -> None:
        if "phase" not in result:
            return
        try:
            if data["kind"] not in ("skill", "observe"):
                raise LedgerError("Ordinary prompt receipt requires a skill or closing Observe")
            if type(result["phase"]) is not dict:
                raise LedgerError("Prompt result.phase must be a typed object")
            phase = json_object(result["phase"])
            root_id = phase.get("origin_request_id")
            _id(root_id)
            root = self.request(root_id)
            root_row = self._db.execute("SELECT rowid FROM requests WHERE id=?", (root_id,)).fetchone()[0]
            child_row = self._db.execute("SELECT rowid FROM requests WHERE id=?", (request_id,)).fetchone()[0]
            if root_row > child_row or root["epoch"] > data["epoch"]:
                raise LedgerError("Prompt result refers to a future root")
            validate_prompt_result(phase, request=data, root=root["request"], actor_id=actor_id)
        except ContractError as exc:
            raise LedgerError(f"Invalid prompt result: {exc}") from exc

    def complete_request(self, request_id: str, disposition: str, result: dict, *, now: float) -> dict:
        if disposition not in REQUEST_STATES - {"accepted", "running"}: raise LedgerError("Invalid operation result")
        encoded = _json(result)
        with self._transaction():
            state = self._touch(now)
            old = self.request(request_id)
            if old["request"]["kind"] in ("handoff", "claim") and disposition == "completed":
                raise LedgerError("Successful handoff/claim requires its atomic transition")
            if old["result"] is not None:
                if old["state"] == disposition and old["result"] == json_object(encoded): return old
                raise LedgerError("Operation result cannot be rewritten")
            if "phase" in result:
                issued, consumed = self._handoffs()
                actors = [(0, self.admission.player_id)] + sorted((issued[identity]["epoch"], self.request(claim)["result"]["player_id"])
                    for identity, claim in consumed.items())
                actor = next(player for epoch, player in reversed(actors) if epoch <= old["epoch"])
                if actor != state["player_id"]:
                    raise LedgerError("New prompt result cannot cross the current actor")
            self._check_prompt_result(request_id, old["request"], json_object(encoded), actor_id=state["player_id"])
            unresolved = self._db.execute("SELECT 1 FROM primitives WHERE request_id=? AND (state IN ('prepared','published') OR (state='unknown' AND effect IS NULL))", (request_id,)).fetchone()
            if disposition == "completed" and unresolved: raise LedgerError("Unresolved effects cannot silently become completion")
            self._release(f"request:{request_id}")
            self._db.execute("UPDATE requests SET state=?,result=? WHERE id=?", (disposition, encoded, request_id))
            if disposition in ("unknown", "paused") and state["phase"] not in TERMINAL | {"paused"}:
                state.update(phase="paused", epoch=state["epoch"] + 1, pause_cause="unknown",
                             reason="Operation stopped without input authority")
                self._put("state", state)
        return self.request(request_id)

    def finish_mission(self, disposition: str, *, reason: str, now: float) -> dict:
        """Record runtime-verified ending; operational evidence stays in its journal."""
        if disposition not in TERMINAL or not isinstance(reason, str) or not 1 <= len(reason) <= 1024:
            raise LedgerError("Invalid mission ending")
        with self._transaction():
            state = self._touch(now)
            if state["phase"] in TERMINAL:
                if state["phase"] == disposition and state["reason"] == reason:
                    return self.snapshot(now=now)
                raise LedgerError("Mission ending cannot be rewritten")
            if disposition == "completed":
                if state["phase"] != "finishing" or now > state["deadline"]:
                    raise LedgerError("Completion requires timely normal finishing")
                if self._db.execute("SELECT 1 FROM primitives WHERE state IN ('prepared','published') OR (state='unknown' AND effect IS NULL)").fetchone():
                    raise LedgerError("Completion still has unresolved inputs")
                if self._db.execute("SELECT 1 FROM requests WHERE state IN ('accepted','running')").fetchone():
                    raise LedgerError("Complete operation results before mission completion")
            state.update(phase=disposition, reason=reason)
            self._put("state", state)
        return self.snapshot(now=now)

    @staticmethod
    def _check_work_lineage(entry: dict, previous: dict[str, dict]) -> None:
        old = previous.get(entry["id"])
        if old is not None:
            if any(entry[key] != old[key] for key in ("scope", "intent", "predecessor_work_id")):
                raise LedgerError("Work retains immutable scope, intent and predecessor")
        elif entry["predecessor_work_id"] is not None and entry["predecessor_work_id"] not in previous:
            raise LedgerError("Work predecessor must already exist in this mission")

    def append_memory(self, event_id: str, entry_type: str, entry: dict, *, now: float) -> int:
        """Immutable typed storage; semantic reduction belongs to campaign memory."""
        _id(event_id)
        data = validate_memory_entry(entry, entry_type)
        if data["scope"]["mission_id"] != self.admission.mission_id: raise LedgerError("Memory belongs to another mission")
        encoded = _json(data)
        with self._transaction():
            self._touch(now)
            old = self._db.execute("SELECT sequence,entry_type,body FROM memory WHERE event_id=?", (event_id,)).fetchone()
            if old:
                if old[1:] != (entry_type, encoded): raise LedgerError("Memory event identity reused")
                return old[0]
            maximum = {"claim": 2048, "work": 256, "decision": 2048}[entry_type]
            if self._db.execute("SELECT count(*) FROM memory WHERE entry_type=?", (entry_type,)).fetchone()[0] >= maximum:
                raise BudgetError("Memory event retention limit reached")
            if entry_type != "work" and self._db.execute("SELECT 1 FROM memory WHERE entry_type=? AND record_id=?", (entry_type, data["id"])).fetchone():
                raise LedgerError("An immutable assertion/decision identity cannot be overwritten")
            if entry_type == "work":
                self._check_work_lineage(data, {row["entry"]["id"]: row["entry"] for row in self.memory_records("work")})
            cursor = self._db.execute("INSERT INTO memory(event_id,entry_type,record_id,body) VALUES (?,?,?,?)", (event_id, entry_type, data["id"], encoded))
            return cursor.lastrowid

    def memory_records(self, entry_type: str) -> tuple[dict, ...]:
        if entry_type not in ("claim", "work", "decision"): raise LedgerError("Unknown memory type")
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            return tuple({"sequence": row[0], "event_id": row[1], "entry": json_object(row[2])}
                         for row in self._db.execute("SELECT sequence,event_id,body FROM memory WHERE entry_type=? ORDER BY sequence", (entry_type,)))
