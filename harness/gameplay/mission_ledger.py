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
from .contracts import canonical
from .native_receipts import validate_ordinary_mapping
from .mission_contracts import VERSION, MissionAdmission, InputObservation, SourceRevalidation, validate_handoff_binding, effect_reconciliation, validate_effect_reconciliation, validate_delivery_resolution, validate_handoff_result, validate_lifecycle_transition, validate_memory_entry, validate_normal_adoption, validate_normal_exit, validate_normal_finish, validate_prompt_result, validate_request, validate_saved_checkpoint, validate_readmission

DB_VERSION = 12
MAX_DATABASE_BYTES = 64 * 1024 * 1024
MAX_RECEIPT_BYTES = 65_536
MAX_EFFECT_BYTES = 32_768
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
    "CREATE TABLE reflection_jobs (sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, claimed_at REAL, deadline REAL, charged_seconds REAL NOT NULL, proposal TEXT)",
    "CREATE TABLE reflection_commands (id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL, received_at REAL NOT NULL)",
)


class LedgerError(ContractError):
    """Invalid or unavailable accounting. Caller must revoke input before repair."""


class BudgetError(LedgerError):
    """Original budget/reserve cannot admit another side effect."""


class ReflectionRefusal(LedgerError):
    """A semantic advisory refusal that may be retained as a zero-input result."""


class ReflectionBudgetRefusal(BudgetError, ReflectionRefusal):
    """A semantic advisory allowance refusal, distinct from storage/clock failure."""


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
                "source_before", "preflight_source", "revalidation", "input_observation", "reservation_id"}
    if set(data) != expected or data["kind"] not in ("action", "key", "direct", "resume", "request_interrupt", "answer_interrupt"):
        raise LedgerError("Primitive intent fields do not match")
    for key in ("expected_session", "expected_boundary_id", "source_before", "preflight_source", "reservation_id"): _id(data[key])
    if data["revalidation"] is not None:
        if data["kind"] == "direct" or data["input_observation"] is not None:
            raise LedgerError("Ordinary observation cannot be semantic equivalence")
        refreshed = SourceRevalidation.from_dict(data["revalidation"])
        if refreshed.current.source_id != data["source_before"]:
            raise LedgerError("Revalidation current source differs from the proposal before-source")
    if data["input_observation"] is not None:
        observed = InputObservation.from_dict(data["input_observation"])
        if data["kind"] != "direct" or observed.current.source_id != data["source_before"]:
            raise LedgerError("Ordinary entry must name its exact direct before-source")
    if type(data["expected_revision"]) is not int or data["expected_revision"] < 0:
        raise LedgerError("Primitive requires exact observed revision")
    if data["kind"] in ("resume", "request_interrupt"):
        if data["value"] is not None:
            raise LedgerError("Resume/interrupt request has no action/key value")
    elif data["kind"] == "direct":
        from .native_input import validate_input
        validate_input(data["value"])
    elif data["kind"] == "answer_interrupt":
        value = data["value"]
        if type(value) is not dict or set(value) != {"interrupt_request_id", "choice"} or value["choice"] not in ("YES", "NO"):
            raise LedgerError("Interrupt answer requires its exact owner and YES/NO choice")
        _id(value["interrupt_request_id"])
    elif not isinstance(data["value"], str) or not 1 <= len(data["value"]) <= 160:
        raise LedgerError("Primitive requires bounded action/key")
    return data


def _primitive_parent(intent: dict, request: dict) -> None:
    """One prepare/reopen rule for ordinary, lifecycle and activity inputs."""
    if request["kind"] not in ("skill", "lifecycle", "readmit"):
        raise LedgerError("Primitive requires an executable parent")
    activity = (request["kind"] == "skill" and request["skill_kind"] == "activity"
                and request["phase_id"] is not None)
    kind = intent["kind"]
    if kind == "direct" and (request["kind"] != "skill" or request["skill_kind"] != "direct"):
        raise LedgerError("Direct input requires its exact ordinary skill parent")
    if request["kind"] == "skill" and request["skill_kind"] == "direct" and kind != "direct":
        raise LedgerError("An ordinary request cannot dispatch a semantic shortcut")
    if kind in ("request_interrupt", "answer_interrupt"):
        step = "interrupt" if kind == "request_interrupt" else "answer_interrupt"
        if not activity or request["goal"]["step"] != step or not request["goal"]["interrupt_allowed"]:
            raise LedgerError("Control requires its exact permitted activity child")
        if kind == "answer_interrupt" and intent["value"] != {
                "interrupt_request_id": request["goal"]["interrupt_request_id"], "choice": request["goal"]["answer"]}:
            raise LedgerError("Control intent differs from its immutable answer")
    if kind == "resume" and request["kind"] not in ("lifecycle", "readmit") and not (
            activity and request["goal"]["step"] == "resume"):
        raise LedgerError("Resume requires lifecycle/readmission or its activity resume child")
    if activity and request["goal"]["step"] in ("interrupt", "answer_interrupt", "resume"):
        expected = {"interrupt": "request_interrupt", "answer_interrupt": "answer_interrupt", "resume": "resume"}
        if kind != expected[request["goal"]["step"]]:
            raise LedgerError("Activity recovery cannot dispatch an ordinary action/key")
    if request["kind"] == "readmit" and kind != "resume":
        raise LedgerError("Readmission permits only its charged Resume")


def _ordinary_sequence(intent: dict, request: dict, position: int, previous: str | None) -> None:
    """Audit exact physical selection and one entry record per direct request."""
    if intent["kind"] != "direct":
        return
    if (intent["input_observation"] is not None) != (position == 0):
        raise LedgerError("Only the first ordinary primitive must record its entry observation")
    if position and previous != "returned":
        raise LedgerError("An ordinary batch cannot continue after refused or uncertain delivery")
    selected = request["goal"]["input"]
    if selected["type"] == "text":
        if position >= len(selected["text"]):
            raise LedgerError("Ordinary text exceeded its selected scalar sequence")
        selected = {"type": "text", "text": selected["text"][position]}
    elif position:
        raise LedgerError("A single physical event cannot be repeated under the same request")
    if (intent["value"] != selected or intent["expected_session"] != request["expected_session"]
            or intent["expected_revision"] < request["expected_revision"]):
        raise LedgerError("Ordinary primitive retargeted its immutable physical event/session")


def _control_mapping(intent: dict, result: dict, *, logical_id: str, native_id: str | None, disposition: str) -> None:
    """Audit control correlation; controller still owns full native validation."""
    if intent["kind"] not in ("request_interrupt", "answer_interrupt"):
        return
    if (result.get("logical_action_id") != logical_id or result.get("native_request_id") != native_id
            or result.get("transport_disposition") != disposition
            or any(result.get(k) != intent[k] for k in ("kind", "value", "expected_session", "expected_revision",
                                                        "expected_boundary_id", "source_before", "preflight_source"))):
        raise LedgerError("Control receipt contradicts its immutable logical/native mapping")
    if disposition not in ("returned", "rejected"):
        return
    control = result.get("control")
    if type(control) is not dict or set(control) != {"request", "result"}:
        raise LedgerError("Known control delivery lost its terminal ACK")
    request, ack = control["request"], control["result"]
    if (type(request) is not dict or type(ack) is not dict or not result.get("published")
            or native_id is None or request.get("id") != native_id or ack.get("id") != native_id
            or request.get("kind") != intent["kind"] or request.get("session") != intent["expected_session"]):
        raise LedgerError("Control ACK lost native operation/session correlation")
    if intent["kind"] == "answer_interrupt" and any(request.get(k) != v for k, v in {
            "revision": intent["expected_revision"], "boundary_id": intent["expected_boundary_id"], **intent["value"]}.items()):
        raise LedgerError("Control ACK differs from its exact owner/answer")
    allowed = ({"prompt_opened", "not_applicable"} if intent["kind"] == "request_interrupt" else {"answer_delivered"})
    if ack.get("status") not in (allowed if disposition == "returned" else {"rejected"}):
        raise LedgerError("Control ACK contradicts its terminal disposition")
    _clock(result.get("received_monotonic"))
    if disposition == "returned":
        native = ack.get("state")
        if (type(native) is not dict or native.get("session") != intent["expected_session"]
                or native.get("paused") is not True):
            raise LedgerError("Returned control lost its paused native state")
        if ack["status"] == "prompt_opened" and native.get("boundary", {}).get("interrupt_request_id") != native_id:
            raise LedgerError("Interrupt ACK lost its exact returned owner")


def _ordinary_mapping(intent: dict, result: dict, *, logical_id: str, native_id: str | None, disposition: str) -> None:
    try:
        validate_ordinary_mapping(intent, result, logical_id=logical_id, native_id=native_id, disposition=disposition)
    except ContractError as exc:
        raise LedgerError(str(exc)) from exc


def _effect(value: dict | str) -> dict:
    data = validate_effect_reconciliation(value)
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
                    self._db.execute("UPDATE reflection_jobs SET state='unknown' WHERE state='claimed'")
                    self._db.execute("UPDATE reflection_jobs SET state='unreviewed' WHERE state='offered'")
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
            if data["kind"] == "readmit":
                if deadline != self._readmit_deadline(data, admitted_at=admitted_at):
                    raise LedgerError("Original handoff readmission deadline was altered")
                for linked in ((data["handoff_id"], data["claim_request_id"]) if data["mode"] == "handoff"
                               else (data["reconciliation_request_id"],)):
                    self._earlier_request(request_id, linked)
            if data["kind"] in ("handoff", "claim") and deadline != state["deadline"]:
                raise LedgerError("Original handoff/claim deadline was altered")
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
        procedures = []
        for event_id, entry_type, record_id, body in self._db.execute("SELECT event_id,entry_type,record_id,body FROM memory ORDER BY sequence"):
            _id(event_id)
            entry = validate_memory_entry(body, entry_type)
            if entry["id"] != record_id or (entry["mission_id"] if entry_type == "procedure" else entry["scope"]["mission_id"]) != stored.mission_id:
                raise LedgerError("Corrupt semantic record scope")
            if entry_type == "procedure":
                self._check_procedure_lineage(entry, procedures, stored)
                procedures.append(entry)
            if entry_type == "work":
                self._check_work_lineage(entry, work_lineage)
                work_lineage[entry["id"]] = entry
        issued, consumed = self._handoffs(state=state)
        self._verify_reflection(stored, state)
        actors = [(0, stored.player_id)] + sorted((issued[identity]["epoch"], self.request(claim)["result"]["player_id"])
                                                 for identity, claim in consumed.items())
        for request_id, payload, result, status in self._db.execute("SELECT id,payload,result,state FROM requests WHERE result IS NOT NULL"):
            data = json_object(payload)
            actor = next(player for epoch, player in reversed(actors) if epoch <= data.get("epoch", 0))
            self._check_prompt_result(request_id, data, json_object(result), actor_id=actor, request_state=status)
        if state["phase"] == "completed":
            rows = self.request_records()
            if (not rows or rows[-1]["state"] != "completed" or rows[-1]["result"] is None
                    or rows[-1]["result"].get("normal_finish", {}).get("disposition") != "completed"):
                raise LedgerError("Completed mission lost its final immutable NormalFinish report")
        count = 0
        primitive_counts = {}
        primitive_dispositions = {}
        for logical_id, request_id, intent, native_id, status, result, effect in self._db.execute(
                "SELECT id,request_id,intent,native_id,state,result,effect FROM primitives ORDER BY rowid"):
            _id(logical_id)
            if native_id is not None: _id(native_id)
            if status not in PRIMITIVE_STATES: raise LedgerError("Corrupt primitive state")
            data = _intent(intent)
            if intent != _json(data): raise LedgerError("Noncanonical primitive intent")
            parent = self.request(request_id)
            _primitive_parent(data, parent["request"])
            position = primitive_counts.get(request_id, 0)
            _ordinary_sequence(data, parent["request"], position, primitive_dispositions.get(request_id))
            primitive_counts[request_id] = position + 1
            primitive_dispositions[request_id] = status
            actor = next(player for epoch, player in reversed(actors) if epoch <= parent["epoch"])
            self._check_source_transition(data, parent["epoch"], stored.mission_id,
                                     informing_sources=parent["request"]["sources"], actor_id=actor)
            if status == "prepared" and native_id is not None or status == "published" and native_id is None:
                raise LedgerError("Corrupt publication identity")
            if result is not None:
                if result != _json(json_object(result)) or status in ("prepared", "published"):
                    raise LedgerError("Corrupt primitive receipt")
                _control_mapping(data, json_object(result), logical_id=logical_id, native_id=native_id, disposition=status)
                _ordinary_mapping(data, json_object(result), logical_id=logical_id, native_id=native_id, disposition=status)
            elif status not in ("prepared", "published", "unknown"):
                raise LedgerError("Terminal primitive lost its receipt")
            if effect is not None and (status != "unknown" or effect != _json(_effect(effect))):
                raise LedgerError("Corrupt primitive effect evidence")
            if effect is not None:
                self._check_effect(logical_id, _effect(effect), actor_id=actor)
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
                        or receipt["unfinished_work_ids"] != data["unfinished_work_ids"]
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
                "actor_role": role, "epoch": data["epoch"], "packet_ids": data["packet_ids"],
                "read_source_ids": data["read_source_ids"], "read_procedure_sources": data["read_procedure_sources"], "grants_authority": False}

    @staticmethod
    def _claim_binding(data: dict, handoff: dict) -> None:
        if data["actor_role"] != handoff["successor_role"] or handoff["post_pause_source_id"] not in data["read_source_ids"]:
            raise LedgerError("Claim lacks its successor role/post-Pause source declaration")
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
                "epoch": state["epoch"] + 1, "checkpoint_ids": data["checkpoint_ids"],
                "unfinished_work_ids": data["unfinished_work_ids"], "grants_authority": False})
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
            if handoff is None or handoff["successor_role"] != actor_role or data["actor_role"] != actor_role:
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

    def measured_counts(self) -> dict:
        """Cumulative retained rows, not delivered keys, tasks or model calls.

        The mission writer caches this projection on publication. Viewer polling
        must not scan receipts, journal files or the bounded recent event buffer.
        No new counter/history is maintained alongside SQLite's source records.
        """
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            rows = self._db.execute("""
                SELECT 'by_kind',json_extract(payload,'$.kind'),count(*) FROM requests
                    GROUP BY json_extract(payload,'$.kind')
                UNION ALL
                SELECT 'by_skill',json_extract(payload,'$.skill_kind'),count(*) FROM requests
                    WHERE json_extract(payload,'$.kind')='skill'
                    GROUP BY json_extract(payload,'$.skill_kind')
                UNION ALL
                SELECT 'by_state',state,count(*) FROM requests GROUP BY state
                UNION ALL
                SELECT 'primitives',state,count(*) FROM primitives GROUP BY state
            """).fetchall()
        operations = {"total": 0, "by_kind": {}, "by_skill": {}, "by_state": {}}
        primitives = {"charged": 0, "by_state": {}}
        for dimension, label, count in rows:
            if dimension == "primitives":
                primitives["by_state"][label] = count
                primitives["charged"] += count
            else:
                operations[dimension][label] = count
                if dimension == "by_kind": operations["total"] += count
        return {"operations": operations, "primitives": primitives}

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
            if data["kind"] == "skill" and data["procedure"] is not None:
                if self._db.execute("SELECT 1 FROM requests WHERE json_extract(payload,'$.procedure.use_id')=?",
                                    (data["procedure"]["use_id"],)).fetchone():
                    raise LedgerError("A procedure use identity belongs to one immutable skill root")
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
            if data["kind"] == "readmit":
                deadline = self._readmit_deadline(data, admitted_at=now, admitting=True)
                if now >= deadline:
                    raise BudgetError("Readmission cannot renew issuance/claim/ordinary deadlines")
            self._db.execute("INSERT INTO requests(id,payload,digest,epoch,state,admitted_at,deadline) VALUES (?,?,?,?,'accepted',?,?)",
                             (data["request_id"], encoded, digest, state["epoch"], now, deadline))
            self._reserve(f"request:{data['request_id']}", RESULT_RESERVE)
        return {"created": True, "operation": self.request(data["request_id"])}

    def _readmit_deadline(self, data: dict, *, admitted_at: float, admitting: bool = False) -> float:
        if data["mode"] == "recovery":
            resolved = self.request(data["reconciliation_request_id"])
            if resolved["request"]["kind"] != "reconcile" or resolved["state"] != "completed" or resolved["result"] is None:
                raise LedgerError("Recovery readmission requires its completed reconciliation")
            proof = validate_delivery_resolution(resolved["result"].get("reconciliation"))
            root = self.request(proof["root_id"])
            if (data["phase_id"] != proof["root_id"] or data["work_id"] != root["request"].get("work_id")
                    or data["epoch"] != proof["recovery_epoch"] or proof["observed_source_id"] not in data["sources"]
                    or data["expected_session"] != json_object(proof["native_request_json"])["session"]):
                raise LedgerError("Recovery readmission lost its original root/Work/epoch/source")
            admission = MissionAdmission.from_dict(self._get("admission"))
            return min(root["deadline"], self._get("state")["deadline"] - admission.cleanup_reserve.wall_seconds,
                       admitted_at + data["limits"]["wall_seconds"])
        issued = self.request(data["handoff_id"])
        claim = self.request(data["claim_request_id"])
        if (issued["request"]["kind"] != "handoff" or issued["state"] != "completed"
                or claim["request"]["kind"] != "claim" or claim["state"] != "completed"
                or claim["request"]["handoff_id"] != data["handoff_id"]
                or claim["epoch"] != data["epoch"] or issued["result"]["epoch"] != data["epoch"]
                or admitted_at < claim["admitted_at"]):
            raise LedgerError("Readmission requires its exact prior completed handoff/claim")
        handoff = issued["result"]
        if any(data[a] != handoff[b] for a, b in
                (("expected_session", "session"), ("expected_revision", "revision"), ("expected_boundary_id", "boundary_id"))):
            raise LedgerError("Readmission lost its exact issued post-Pause source")
        if handoff["post_pause_source_id"] not in data["sources"]:
            if not admitting:
                # Historical validation cannot assert that delivery never happened.
                raise LedgerError("Readmission lost its exact issued post-Pause source")
            raise LedgerError("Select issued post-Pause source " + handoff["post_pause_source_id"]
                + "; a later Observe source cannot replace it. This request was refused before admission; "
                "no Resume or input was attempted. Correct with a NEW request ID only if the original "
                "claimed handoff remains eligible. Readmission performs its own bounded fresh Observe; "
                "no prerequisite Observe is needed.")
        admission = MissionAdmission.from_dict(self._get("admission"))
        return min(issued["deadline"], claim["deadline"], self._get("state")["deadline"] - admission.cleanup_reserve.wall_seconds,
                   admitted_at + data["limits"]["wall_seconds"])

    @staticmethod
    def _is_phase_root(data: dict) -> bool:
        return data.get("phase_id") is None and (data["kind"] == "lifecycle"
            or data["kind"] == "skill" and data["skill_kind"] in ("navigate", "item", "activity", "interact", "inspect", "direct"))

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
        if data.get("work_id") != root.get("work_id"):
            raise LedgerError("Phase child cannot replace its immutable root Work association")
        if data["kind"] == "skill":
            if data["skill_kind"] == "navigate":
                if root.get("skill_kind") != "navigate" or data["goal"] != root["goal"]:
                    raise LedgerError("Navigation continuation must keep its exact original goal/scope")
            elif data["skill_kind"] not in ("menu", "edit", "interact", "inspect", "item", "activity", "direct"):
                raise LedgerError("Phase skill child must be a direct control operation")
            elif root.get("skill_kind") == "navigate" and data["skill_kind"] not in ("menu", "edit"):
                raise LedgerError("Navigation root permits only its exact suffix or ordinary menu/editor controls")
            if data["skill_kind"] == "direct":
                if root["kind"] != "skill" or root["skill_kind"] not in ("interact", "item", "inspect", "activity", "direct"):
                    raise LedgerError("Direct child cannot borrow lifecycle or navigation authority")
                if data["goal"]["interrupt_allowed"] and not root["goal"].get("interrupt_allowed", False):
                    raise LedgerError("Direct child cannot enlarge original interruption consent")
            if data["skill_kind"] == "activity" and root.get("skill_kind") == "direct":
                if (data["goal"]["operation"] != "direct" or data["goal"]["target"] != root["goal"]["expected"]
                        or data["goal"]["game_seconds"] > root["limits"]["game_seconds"]
                        or data["goal"]["interrupt_allowed"] and not root["goal"]["interrupt_allowed"]):
                    raise LedgerError("Ordinary activity child changed its original intent, time or consent")
            elif data["skill_kind"] in ("item", "activity"):
                kind = data["skill_kind"]
                keys = ("purpose", "label", "quantity", "quantity_unit", "outcome") if kind == "item" else (
                    "operation", "target", "game_seconds", "interrupt_allowed")
                if root.get("skill_kind") != kind or any(data["goal"][key] != root["goal"][key] for key in keys):
                    raise LedgerError("Semantic child differs from its exact immutable root goal")
            if root.get("skill_kind") == "interact" and data["skill_kind"] == "interact":
                raise LedgerError("Ordinary interaction returns to normal play before another interaction root")
        elif data["kind"] == "readmit" and data["mode"] == "recovery":
            pass  # Exact reconciliation/root correlation is checked by _readmit_deadline.
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
            _primitive_parent(data, request["request"])
            if now >= request["deadline"]:
                raise BudgetError("Original operation deadline expired")
            count = self._db.execute("SELECT count(*) FROM primitives WHERE request_id=?", (request_id,)).fetchone()[0]
            prior = self._db.execute("SELECT state FROM primitives WHERE request_id=? ORDER BY rowid DESC LIMIT 1", (request_id,)).fetchone()
            _ordinary_sequence(data, request["request"], count, None if prior is None else prior[0])
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
            self._check_source_transition(data, request["epoch"], self.admission.mission_id,
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
    def _check_source_transition(intent: dict, epoch: int, mission_id: str, *, informing_sources: list[str],
                                 actor_id: str | None = None) -> None:
        for key, record in (("revalidation", SourceRevalidation), ("input_observation", InputObservation)):
            if intent[key] is None:
                continue
            refreshed = record.from_dict(intent[key])
            current = refreshed.current
            if current.epoch != epoch or current.mission_id != mission_id or (actor_id is not None and current.actor_id != actor_id):
                raise LedgerError("Observation transition belongs to another mission/epoch/actor")
            if refreshed.original.source_id not in informing_sources:
                raise LedgerError("Observation transition original source did not inform the immutable request")

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
            if (p["native_id"] is None
                    and (p["intent"]["kind"] in ("request_interrupt", "answer_interrupt") or disposition in ("returned", "rejected"))
                    and result.get("published") is True and result.get("native_request_id") is not None):
                # A prior publication bookkeeping transaction may have failed
                # after a real ACK. Bind and settle atomically; never resend.
                native_id = result["native_request_id"]
                _id(native_id)
                _control_mapping(p["intent"], result, logical_id=logical_id, native_id=native_id, disposition=disposition)
                _ordinary_mapping(p["intent"], result, logical_id=logical_id, native_id=native_id, disposition=disposition)
                self._db.execute("UPDATE primitives SET native_id=? WHERE id=?", (native_id, logical_id))
                p["native_id"] = native_id
            _control_mapping(p["intent"], result, logical_id=logical_id, native_id=p["native_id"], disposition=disposition)
            _ordinary_mapping(p["intent"], result, logical_id=logical_id, native_id=p["native_id"], disposition=disposition)
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

    def reconcile_effect(self, logical_id: str, *, proof: dict, sources: tuple[str, ...], note: str, now: float) -> dict:
        """Record controller-verified reconciliation, keeping original ACK unknown."""
        if type(sources) is not tuple: raise LedgerError("Reconciliation sources must be an explicit tuple")
        effect = _effect(effect_reconciliation(proof, sources=sources, note=note))
        with self._transaction():
            self._touch(now)
            p = self.primitive(logical_id)
            if p["state"] != "unknown": raise LedgerError("Only unknown effects require this reconciliation")
            self._check_effect(logical_id, effect, actor_id=self._get("state")["player_id"])
            if p["effect"] is not None:
                if p["effect"] == effect: return p
                raise LedgerError("Reconciliation is immutable")
            self._release(f"effect:{logical_id}")
            self._db.execute("UPDATE primitives SET effect=? WHERE id=?", (_json(effect), logical_id))
        return self.primitive(logical_id)

    def _check_effect(self, logical_id: str, effect: dict, *, actor_id: str) -> None:
        p, proof = self.primitive(logical_id), effect["proof"]
        intent = p["intent"]
        if effect["basis"] != "DeliveryResolution":
            root_row = self.request(proof["origin_request_id"])
            root = root_row["request"]
            parent = self.request(p["request_id"])
            if (proof["terminal_logical_id"] != logical_id or proof["native_request_id"] != p["native_id"]
                    or p["state"] != "unknown" or root["kind"] != "lifecycle"
                    or root["phase_id"] is not None
                    or root["operation"] != (proof["operation"] if effect["basis"] == "LifecycleTransition" else "exit")
                    or p["request_id"] != (proof["terminal_request_id"] if effect["basis"] == "LifecycleTransition" else p["request_id"])
                    or (self.request(p["request_id"])["request"].get("phase_id") or p["request_id"]) != root["request_id"]):
                raise LedgerError("Lifecycle/exit effect lost its exact original primitive")
            sources = ([proof["before_source_id"], proof["after_source_id"]]
                       if effect["basis"] == "LifecycleTransition" else proof["source_ids"])
            if effect["sources"] != sources or intent["source_before"] not in sources:
                raise LedgerError("Lifecycle/exit effect lost its exact retained sources")
            launched = self._earlier_request(root["request_id"], proof["launch_request_id"])
            launch_result = launched["result"] or {}
            receipt = p["result"] or {}
            if (launched["request"].get("operation") != "launch" or launched["state"] != "completed"
                    or launch_result.get("native_ready") is not True
                    or type(launch_result.get("process")) is not dict
                    or launch_result["process"].get("launch_id") != proof["launch_id"]
                    or intent["kind"] != "action" or receipt.get("published") is not True
                    or any(receipt.get(k) != v for k, v in {
                        "logical_action_id": logical_id, "native_request_id": p["native_id"],
                        "transport_disposition": "unknown", **{key: intent[key] for key in
                            ("kind", "value", "expected_session", "expected_revision", "expected_boundary_id", "source_before", "preflight_source")}
                    }.items())):
                raise LedgerError("Orphan lifecycle/exit effect lost its actual owned launch/published input")
            if effect["basis"] == "LifecycleTransition":
                if (proof["actor_id"] != actor_id or proof["origin_epoch"] != root_row["epoch"]
                        or parent["epoch"] != root_row["epoch"] or proof["reconciled_epoch"] != parent["epoch"] + 1
                        or proof["reconciled_epoch"] > self._get("state")["epoch"]):
                    raise LedgerError("Orphan lifecycle effect changed its original actor/unknown epoch")
                binding = receipt.get("dispatch_binding") or {}
                if any(binding.get(k) != v for k, v in {
                        "controller_boot_id": proof["controller_boot_id"], "operator_pause_generation": proof["operator_pause_generation"],
                        "takeover_generation": proof["before_takeover_generation"], "actor_id": actor_id, "epoch": parent["epoch"]}.items()):
                    raise LedgerError("Orphan lifecycle effect changed its independently captured dispatch custody")
                if proof["operation"] in ("create", "save"):
                    question = "Are you SURE you're finished?" if proof["operation"] == "create" else "Save and quit?"
                    perception = parent["request"].get("perception") or {}
                    if (intent["value"] != "YES" or perception.get("kind") != "confirmation"
                            or perception.get("question") != question or parent["request"].get("goal", {}).get("label") != "Yes"):
                        raise LedgerError("Orphan lifecycle effect lacks its actual exact confirmation")
                elif intent["value"] not in ("CONFIRM", "UILIST.CONFIRM"):
                    raise LedgerError("Orphan load effect lacks its registered selection confirmation")
            elif intent["value"] != "YES" or not self._exit_confirmation(intent, parent["request"]):
                raise LedgerError("Orphan exit effect lacks its exact normal-exit confirmation")
            elif proof["no_save_required"]:
                self._check_menu_cleanup_sources(proof, root["request_id"])
            return
        owner = self._earlier_request(proof["reconciliation_request_id"], proof["original_request_id"])
        resolution = self.request(proof["reconciliation_request_id"])
        root = self.request(proof["root_id"])
        native = json_object(proof["native_request_json"])
        if type(native.get("authority")) is not dict or type(native.get("protocol")) is not int or native["protocol"] != 6:
            raise LedgerError("Delivery proof lacks its original native authority envelope")
        receipt = p["result"] or {}
        binding = receipt.get("dispatch_binding") or {}
        if any(binding.get(k) != v for k, v in {"controller_boot_id": proof["controller_boot_id"],
                "operator_pause_generation": proof["operator_pause_generation"], "takeover_generation": proof["takeover_generation"],
                "actor_id": proof["actor_id"], "epoch": proof["origin_epoch"], "game_anchor_source_id": proof["game_anchor_source_id"]}.items()):
            raise LedgerError("Delivery effect changed its independently captured original dispatch custody")
        if (resolution["request"]["kind"] != "reconcile"
                or resolution["request"]["unresolved_request_id"] != proof["original_request_id"]
                or resolution["request"]["evidence_id"] != proof["observed_source_id"]
                or resolution["epoch"] != proof["recovery_epoch"] or proof["recovery_epoch"] != owner["epoch"] + 1
                or proof["origin_epoch"] != owner["epoch"] or proof["actor_id"] != actor_id
                or owner["request"]["kind"] != "skill"
                or proof["root_id"] != (owner["request"]["phase_id"] or owner["request"]["request_id"])
                or owner["request"].get("work_id") != root["request"].get("work_id")
                or p["request_id"] != proof["original_request_id"] or p["state"] != "unknown"
                or proof["logical_id"] != logical_id or intent["kind"] == "resume"
                or p["native_id"] not in (None, proof["native_request_id"])
                or receipt.get("native_request_json") != proof["native_request_json"]
                or receipt.get("published") is not True or receipt.get("native_request_id") != proof["native_request_id"]
                or native.get("id") != proof["native_request_id"] or native.get("kind") != intent["kind"]
                or native.get("session") != intent["expected_session"]
                or native.get("authority", {}).get("controller_boot_id") != proof["controller_boot_id"]
                or intent["source_before"] != proof["before_source_id"]):
            raise LedgerError("Delivery effect lost its independent original request/root/actor/epoch correlation")
        if intent["kind"] in ("action", "key", "direct"):
            if (native.get("input" if intent["kind"] == "direct" else intent["kind"]) != intent["value"] or native.get("revision") != intent["expected_revision"]
                    or native.get("boundary_id") != intent["expected_boundary_id"]
                    or native.get("takeover_generation") != proof["takeover_generation"]):
                raise LedgerError("Delivery effect contradicts original native intent")
        elif intent["kind"] == "answer_interrupt" and any(native.get(k) != v for k, v in intent["value"].items()):
            raise LedgerError("Delivery effect borrowed another interrupt owner/answer")
        terminal = proof["terminal"]
        if terminal is not None:
            ordinary = intent["kind"] in ("action", "key", "direct")
            allowed = {"ready", "rejected"} if ordinary else ({"prompt_opened", "not_applicable", "rejected"}
                if intent["kind"] == "request_interrupt" else {"answer_delivered", "rejected"})
            if (terminal["id"] != native["id"] or terminal["channel"] != ("ordinary" if ordinary else "control")
                    or terminal["status"] not in allowed or terminal["session"] != native["session"]
                    or terminal["takeover_generation"] != proof["takeover_generation"]
                    or terminal["revision"] < intent["expected_revision"]
                    or ordinary and terminal["status"] == "ready" and terminal["revision"] == intent["expected_revision"]
                    or terminal["status"] == "prompt_opened" and terminal["interrupt_request_id"] != native["id"]):
                raise LedgerError("Delivery effect terminal is not correlated to the actual input")
        required = {proof[k] for k in ("before_source_id", "observed_source_id", "game_anchor_source_id")}
        if proof["terminal_source_id"] is not None: required.add(proof["terminal_source_id"])
        if set(effect["sources"]) != required:
            raise LedgerError("Delivery effect omitted or imported source evidence")

    def _check_recovery_result(self, request_id: str, data: dict, result: dict, actor_id: str) -> None:
        if set(result) != {"reconciliation", "source_ids", "reason", "grants_authority"} or result["grants_authority"] is not False:
            raise LedgerError("Reconciliation requires its closed read-only result")
        proof = validate_delivery_resolution(result["reconciliation"])
        p = self.primitive(proof["logical_id"])
        effect = None if p["effect"] is None else _effect(p["effect"])
        if (proof["reconciliation_request_id"] != request_id or data["kind"] != "reconcile"
                or effect is None or effect["basis"] != "DeliveryResolution"
                or effect["proof"] != proof or result["source_ids"] != effect["sources"]):
            raise LedgerError("Reconciliation result differs from its immutable typed effect")
        self._check_effect(proof["logical_id"], p["effect"], actor_id=actor_id)

    def _check_recovery_readmission(self, request_id: str, data: dict, result: dict, actor_id: str) -> None:
        if set(result) != {"readmission", "source_ids", "reason", "grants_authority"} or result["grants_authority"] is not False:
            raise LedgerError("Recovery readmission requires its closed result")
        proof = validate_readmission(result["readmission"])
        row = self._earlier_request(request_id, data["reconciliation_request_id"])
        resolution = validate_delivery_resolution((row["result"] or {}).get("reconciliation"))
        p = self.primitive(proof["logical_id"])
        if (proof["mode"] != "recovery" or proof["reconciliation_request_id"] != data["reconciliation_request_id"]
                or proof["root_id"] != data["phase_id"] or proof["root_id"] != resolution["root_id"]
                or proof["player_id"] != actor_id or proof["player_id"] != resolution["actor_id"]
                or proof["epoch"] != data["epoch"] or proof["epoch"] != resolution["recovery_epoch"]
                or proof["post_pause_source_id"] != resolution["observed_source_id"]
                or p["request_id"] != request_id or p["intent"]["kind"] != "resume" or p["state"] != "returned"
                or p["intent"]["source_before"] != proof["revalidated_source_id"]
                or p["result"] is None or p["result"].get("source_after") != proof["after_source_id"]
                or p["result"].get("published") is not True
                or p["result"].get("logical_action_id") != proof["logical_id"]
                or any(p["result"].get(k) != p["intent"][k] for k in ("kind", "value", "expected_session",
                    "expected_revision", "expected_boundary_id", "source_before", "preflight_source"))
                or p["result"].get("transport_disposition") != "returned"
                or p["result"].get("native_request_id") != p["native_id"]
                or any(p["intent"][a] != data[b] for a, b in (("expected_session", "expected_session"),
                    ("expected_revision", "expected_revision"), ("expected_boundary_id", "expected_boundary_id")))
                or result["source_ids"] != [proof["revalidated_source_id"], proof["after_source_id"]]):
            raise LedgerError("Recovery readmission lost its exact proof/root/actor/charged Resume")

    def _check_prompt_result(self, request_id: str, data: dict, result: dict, *, actor_id: str,
                             request_state: str) -> None:
        if "reconciliation" in result or data["kind"] == "reconcile" and request_state == "completed":
            if data["kind"] != "reconcile" or request_state != "completed":
                raise LedgerError("Delivery resolution requires its completed reconcile operation")
            self._check_recovery_result(request_id, data, result, actor_id)
            return
        if "readmission" in result or data["kind"] == "readmit" and request_state == "completed":
            if data["kind"] != "readmit" or request_state != "completed":
                raise LedgerError("Readmission proof requires its completed readmit request")
            proof = validate_readmission(result.get("readmission"))
            if data["mode"] == "recovery":
                self._check_recovery_readmission(request_id, data, result, actor_id)
                return
            issued = self._earlier_request(request_id, data["handoff_id"])["result"]
            claim = self._earlier_request(request_id, data["claim_request_id"])["result"]
            primitive = self.primitive(proof["logical_id"])
            if (data["kind"] != "readmit" or request_state != "completed" or proof["epoch"] != data["epoch"]
                    or proof["player_id"] != actor_id or proof["player_id"] != claim["player_id"]
                    or proof["handoff_id"] != data["handoff_id"] or proof["claim_request_id"] != data["claim_request_id"]
                    or proof["post_pause_source_id"] != issued["post_pause_source_id"]
                    or primitive["request_id"] != request_id or primitive["intent"]["kind"] != "resume"
                    or primitive["intent"]["source_before"] != proof["revalidated_source_id"]
                    or primitive["state"] != "returned" or primitive["result"] is None
                    or primitive["result"].get("published") is not True
                    or primitive["result"].get("native_request_id") != primitive["native_id"]
                    or primitive["result"].get("logical_action_id") != proof["logical_id"]
                    or any(primitive["intent"][a] != data[b] for a, b in
                        (("expected_session", "expected_session"), ("expected_revision", "expected_revision"),
                         ("expected_boundary_id", "expected_boundary_id")))
                    or primitive["result"].get("source_after") != proof["after_source_id"]
                    or result.get("source_ids") != [proof["revalidated_source_id"], proof["after_source_id"]]):
                raise LedgerError("Readmission lost its exact handoff/claim/charged Resume correlation")
        if "normal_finish" in result:
            if request_state != "completed":
                raise LedgerError("Normal finish requires a completed immutable result")
            self._check_normal_finish(request_id, data, result["normal_finish"])
        self._check_lifecycle_records(request_id, data, result, actor_id=actor_id, request_state=request_state)
        if "normal_exit" in result:
            if request_state != "completed":
                raise LedgerError("Normal exit requires a completed operation result")
            try:
                self._check_normal_exit(request_id, data, result)
            except ContractError as exc:
                raise LedgerError(f"Invalid normal exit: {exc}") from exc
        if "phase" not in result:
            return
        try:
            if data["kind"] not in ("skill", "observe", "lifecycle"):
                raise LedgerError("Phase receipt requires executable work or closing Observe")
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
            if phase["phase_kind"] == "lifecycle":
                launch = self.request(phase["launch_request_id"])
                launched = launch["result"]
                launch_row = self._db.execute("SELECT rowid FROM requests WHERE id=?", (phase["launch_request_id"],)).fetchone()[0]
                if (launch["request"].get("operation") != "launch" or launch["state"] != "completed"
                        or launched is None or launched.get("native_ready") is not True
                        or type(launched.get("process")) is not dict or launched["process"].get("launch_id") != phase["launch_id"]
                        or launch["epoch"] > root["epoch"] or launch_row >= root_row
                        or not launched.get("source_ids") or not set(launched["source_ids"]) <= set(phase["source_ids"])
                        or not set(root["request"]["sources"]) & set(phase["source_ids"])):
                    raise LedgerError("Exit phase lost its owned launch/epoch")
        except ContractError as exc:
            raise LedgerError(f"Invalid prompt result: {exc}") from exc

    def _earlier_request(self, request_id: str, referenced_id: str, *, inclusive: bool = False) -> dict:
        _id(referenced_id)
        current = self._db.execute("SELECT rowid FROM requests WHERE id=?", (request_id,)).fetchone()
        previous = self._db.execute("SELECT rowid FROM requests WHERE id=?", (referenced_id,)).fetchone()
        if current is None or previous is None or previous[0] > current[0] or previous == current and not inclusive:
            raise LedgerError("Lifecycle proof refers to a missing, self or future request")
        return self.request(referenced_id)

    def _lifecycle_record(self, request_id: str, referenced_id: str, key: str,
                          *, current_result: dict | None = None) -> tuple[dict, dict]:
        row = self._earlier_request(request_id, referenced_id, inclusive=current_result is not None)
        result = current_result if referenced_id == request_id else row["result"]
        if (referenced_id != request_id and row["state"] != "completed"
                or result is None or type(result.get(key)) is not dict):
            raise LedgerError(f"Lifecycle proof requires a completed typed {key} result")
        return row, result[key]

    def _check_lifecycle_records(self, request_id: str, data: dict, result: dict, *, actor_id: str,
                                  request_state: str) -> None:
        keys = {"lifecycle_transition", "normal_adoption", "saved_checkpoint"} & result.keys()
        if not keys:
            return
        if request_state != "completed" or data["kind"] != "lifecycle":
            raise LedgerError("Durable lifecycle proofs require a completed lifecycle operation")
        try:
            phase = result.get("phase")
            expected_stage = "complete" if keys & {"normal_adoption", "saved_checkpoint"} else (
                "awaiting_identity" if data["operation"] in ("create", "load") else "awaiting_control")
            if (type(phase) is not dict or phase.get("phase_kind") != "lifecycle"
                    or phase.get("operation") != data["operation"] or phase.get("stage") != expected_stage):
                raise LedgerError("Lifecycle proof lost its typed operation/stage receipt")
            for key in keys:
                if type(result[key]) is not dict:
                    raise LedgerError("Lifecycle proofs require typed nested objects")
            if "lifecycle_transition" in keys:
                self._check_lifecycle_transition(request_id, data, result["lifecycle_transition"], actor_id)
                transition = result["lifecycle_transition"]
                if any(phase.get(key) != transition[value] for key, value in {
                        "origin_request_id": "origin_request_id", "launch_request_id": "launch_request_id",
                        "launch_id": "launch_id", "controller_boot_id": "controller_boot_id",
                        "operator_pause_generation": "operator_pause_generation",
                        "takeover_generation": "after_takeover_generation",
                }.items()) or not {transition["before_source_id"], transition["after_source_id"]} <= set(phase["source_ids"]):
                    raise LedgerError("Transition differs from its exact lifecycle phase receipt")
            if "normal_adoption" in keys:
                self._check_normal_adoption(request_id, data, result["normal_adoption"])
                _, transition = self._lifecycle_record(request_id,
                    result["normal_adoption"]["transition_result_request_id"], "lifecycle_transition")
                if any(phase[key] != transition[value] for key, value in {
                        "launch_request_id": "launch_request_id", "launch_id": "launch_id", "actor_id": "actor_id",
                        "controller_boot_id": "controller_boot_id", "operator_pause_generation": "operator_pause_generation",
                        "takeover_generation": "after_takeover_generation"}.items()):
                    raise LedgerError("Adoption differs from its exact lifecycle transition audit")
            if "saved_checkpoint" in keys:
                self._check_saved_checkpoint(request_id, data, result)
        except ContractError as exc:
            raise LedgerError(f"Invalid lifecycle proof: {exc}") from exc

    def _check_lifecycle_transition(self, request_id: str, data: dict, value: dict, actor_id: str) -> None:
        proof = validate_lifecycle_transition(value)
        root = self._earlier_request(request_id, proof["origin_request_id"])
        terminal = self._earlier_request(request_id, proof["terminal_request_id"])
        launched = self._earlier_request(root["request"]["request_id"], proof["launch_request_id"])
        root_data, terminal_data = root["request"], terminal["request"]
        launch_result = launched["result"]
        primitive = self.primitive(proof["terminal_logical_id"])
        refreshed = primitive["intent"]["revalidation"]
        informing = proof["before_source_id"] in terminal_data.get("sources", []) or (
            refreshed is not None and refreshed["current"]["source_id"] == proof["before_source_id"]
            and refreshed["original"]["source_id"] in terminal_data.get("sources", []))
        if (root_data["kind"] != "lifecycle" or root_data["phase_id"] is not None
                or data["phase_id"] != root_data["request_id"]
                or any(row.get("operation") != proof["operation"] for row in (data, root_data))
                or root["epoch"] != proof["origin_epoch"] or terminal["epoch"] != root["epoch"]
                or proof["reconciled_epoch"] != data["epoch"] or proof["actor_id"] != actor_id
                or terminal_data.get("phase_id") != root_data["request_id"]
                   and terminal_data["request_id"] != root_data["request_id"]
                or not informing
                or proof["after_source_id"] not in data["sources"]
                or launched["request"].get("operation") != "launch" or launched["state"] != "completed"
                or launch_result is None or launch_result.get("native_ready") is not True
                or type(launch_result.get("process")) is not dict
                or launch_result["process"].get("launch_id") != proof["launch_id"]):
            raise LedgerError("Lifecycle transition lost its root, actor, epoch, source or owned launch")
        receipt = primitive["result"]
        if (primitive["request_id"] != proof["terminal_request_id"]
                or primitive["native_id"] != proof["native_request_id"]
                or primitive["state"] not in ("returned", "unknown")
                or primitive["intent"]["source_before"] != proof["before_source_id"]
                or primitive["intent"]["kind"] != "action" or receipt is None
                or receipt.get("published") is not True
                or any(receipt.get(key) != value for key, value in {
                    "logical_action_id": proof["terminal_logical_id"], "native_request_id": proof["native_request_id"],
                    "kind": "action", "value": primitive["intent"]["value"],
                    "expected_session": primitive["intent"]["expected_session"],
                    "expected_revision": primitive["intent"]["expected_revision"],
                    "expected_boundary_id": primitive["intent"]["expected_boundary_id"],
                    "source_before": proof["before_source_id"], "preflight_source": primitive["intent"]["preflight_source"],
                    "transport_disposition": primitive["state"],
                }.items())):
            raise LedgerError("Lifecycle transition lacks its exact charged published terminal input")
        if proof["operation"] in ("create", "save"):
            question = "Are you SURE you're finished?" if proof["operation"] == "create" else "Save and quit?"
            perception = terminal_data.get("perception")
            if (primitive["intent"]["value"] != "YES" or terminal_data.get("skill_kind") != "menu"
                    or perception is None or perception.get("kind") != "confirmation"
                    or perception.get("question") != question or terminal_data["goal"]["label"] != "Yes"):
                raise LedgerError("Creation/save transition requires its explicit exact confirmation")
        elif primitive["intent"]["value"] not in ("CONFIRM", "UILIST.CONFIRM"):
            raise LedgerError("Load transition requires its registered selection confirmation")
        if primitive["state"] == "unknown" and primitive["effect"] != effect_reconciliation(proof,
                sources=(proof["before_source_id"], proof["after_source_id"]),
                note=f"Observed lifecycle {proof['operation']} transition after {proof['native_request_id']}; original ACK remains unknown"):
            raise LedgerError("Lifecycle transition lost its exact independently reconciled effect")
        if primitive["state"] == "returned" and receipt.get("source_after") != proof["after_source_id"]:
            raise LedgerError("Returned lifecycle transition lost its exact after-source")

    def _check_normal_adoption(self, request_id: str, data: dict, value: dict) -> None:
        proof = validate_normal_adoption(value)
        transition_row, transition = self._lifecycle_record(request_id, proof["transition_result_request_id"], "lifecycle_transition")
        transition = validate_lifecycle_transition(transition)
        inspect = self._earlier_request(request_id, proof["identity_inspect_request_id"])
        inspect_data, inspect_result = inspect["request"], inspect["result"]
        self._earlier_request(proof["identity_inspect_request_id"], proof["transition_result_request_id"])
        if (data["operation"] not in ("create", "load") or transition["operation"] != data["operation"]
                or data["phase_id"] != proof["origin_request_id"]
                or transition["origin_request_id"] != proof["origin_request_id"]
                or transition_row["request"].get("phase_id") != proof["origin_request_id"]
                or transition["reconciled_epoch"] != data["epoch"]
                or proof["first_normal_source_id"] != transition["after_source_id"]
                or proof["scope"]["mission_id"] != self._get("admission")["mission_id"]
                or inspect["state"] != "completed" or inspect_data["kind"] != "skill"
                or inspect_data["skill_kind"] != "inspect" or inspect_data["goal"]["purpose"] != "character_identity"
                or inspect_data["phase_id"] != proof["origin_request_id"] or inspect["epoch"] != data["epoch"]
                or inspect_result is None or type(inspect_result.get("identity_screen_source_id")) is not str
                or proof["checkpoint_source_id"] not in data["sources"]
                or set(data["identity_claim_ids"]) != {proof["world_claim_id"], proof["character_claim_id"]}
                or (data["operation"] == "create") != (proof["saved_checkpoint_request_id"] is None)):
            raise LedgerError("Normal adoption lost its transition, inspection, scope or identity claims")
        claims = {row["entry"]["id"]: row for row in self.memory_records("claim")}
        inspection_inputs = [p for p in self.primitive_records()
            if p["request_id"] == proof["identity_inspect_request_id"]]
        if len(inspection_inputs) != 1:
            raise LedgerError("Identity inspection requires its unique charged player_data primitive")
        primitive = inspection_inputs[0]
        intent, receipt = primitive["intent"], primitive["result"] or {}
        expected = {"logical_action_id": primitive["logical_id"], "native_request_id": primitive["native_id"],
            "transport_disposition": "returned", "published": True,
            "source_after": inspect_result["identity_screen_source_id"],
            **{key: intent[key] for key in ("kind", "value", "expected_session", "expected_revision",
                "expected_boundary_id", "source_before", "preflight_source")}}
        if (intent["kind"] != "action" or intent["value"] != "player_data"
                or intent["expected_session"] != proof["scope"]["session"]
                or primitive["state"] != "returned" or primitive["native_id"] is None
                or any(receipt.get(key) != value for key, value in expected.items())):
            raise LedgerError("Identity inspection lacks its exact returned published player_data receipt")
        scenario = self._get("admission")["scenario"]
        for subject, name in (("world", scenario["world"]), ("character", scenario["character"])):
            selected = claims.get(proof[f"{subject}_claim_id"])
            if selected is None:
                raise LedgerError("Normal adoption references a missing identity Claim")
            entry = selected["entry"]
            memory_request = self._earlier_request(request_id, selected["event_id"])["request"]
            if (memory_request["kind"] not in ("remember", "correct") or memory_request["entry_type"] != "claim"
                    or memory_request["entry"] != entry or entry["key"]["property"] != "identity"
                    or entry["key"]["subject"] != subject or entry["value"] != {"quantity": None, "state": name}
                    or entry["status"] not in ("current", "last_seen")
                    or any(group["claims"] for group in entry["supports"])):
                raise LedgerError("Normal adoption requires directly supported admitted identity Claims")
            if subject == "character" and (entry["scope"] != proof["scope"]
                    or entry["sources"] != [inspect_result["identity_screen_source_id"]]):
                raise LedgerError("Character identity lost its exact inspected source/scope")
        if proof["saved_checkpoint_request_id"] is not None:
            _, saved = self._lifecycle_record(request_id, proof["saved_checkpoint_request_id"], "saved_checkpoint")
            validate_saved_checkpoint(saved)

    def _check_saved_checkpoint(self, request_id: str, data: dict, result: dict) -> None:
        proof = validate_saved_checkpoint(result["saved_checkpoint"])
        _, transition = self._lifecycle_record(request_id, proof["transition_result_request_id"], "lifecycle_transition",
            current_result=result)
        transition = validate_lifecycle_transition(transition)
        _, adoption = self._lifecycle_record(proof["origin_request_id"], proof["adoption_result_request_id"], "normal_adoption")
        validate_normal_adoption(adoption)
        _, entry = self._lifecycle_record(proof["origin_request_id"], adoption["transition_result_request_id"], "lifecycle_transition")
        entry = validate_lifecycle_transition(entry)
        if (data["operation"] != "save" or data["phase_id"] != proof["origin_request_id"]
                or transition["operation"] != "save" or transition["origin_request_id"] != proof["origin_request_id"]
                or transition["reconciled_epoch"] != data["epoch"]
                or any(transition[key] != entry[key] for key in ("launch_request_id", "launch_id"))
                or proof["menu_source_id"] != transition["after_source_id"]):
            raise LedgerError("Saved checkpoint lost its exact save transition or prior adoption")
        primitives = [p for p in self.primitive_records() if self.request(p["request_id"])["request"].get("phase_id") == proof["origin_request_id"]
            or p["request_id"] == proof["origin_request_id"]]
        def saved_action(p: dict) -> bool:
            intent, receipt = p["intent"], p["result"] or {}
            expected = {"logical_action_id": p["logical_id"], "native_request_id": p["native_id"],
                "transport_disposition": "returned", "published": True,
                **{key: intent[key] for key in ("kind", "value", "expected_session", "expected_revision",
                    "expected_boundary_id", "source_before", "preflight_source")}}
            return (intent["kind"] == "action" and intent["value"] == "save"
                and intent["preflight_source"] == proof["normal_endpoint_source_id"]
                and p["state"] == "returned" and p["native_id"] is not None
                and all(receipt.get(key) == value for key, value in expected.items()))
        if not any(saved_action(p) for p in primitives):
            raise LedgerError("Saved checkpoint lacks its exact normal save-action preflight")

    @staticmethod
    def _exit_confirmation(intent: dict, data: dict) -> bool:
        view, goal = data.get("perception") or {}, data.get("goal") or {}
        if (data.get("kind") != "skill" or data.get("skill_kind") != "menu"
                or view.get("kind") != "confirmation" or view.get("question") != "Really quit?"
                or goal.get("label") != "Yes" or goal.get("outcome") != "activated"):
            return False
        relation = intent["revalidation"]
        if relation is None:
            return intent["source_before"] == view.get("source_id")
        refreshed = SourceRevalidation.from_dict(relation)
        return (refreshed.rule == "exact_png_bytes" and refreshed.original.source_id == view.get("source_id")
                and refreshed.current.source_id == intent["source_before"])

    def menu_cleanup_resume(self, launch_request_id: str, *, exit_root_id: str | None = None) -> dict | None:
        """Audit pre-character input history; bytes/live custody remain runtime checks.

        The current exit subtree is outside the cutoff. An earlier exit must have
        no inputs or a settled deliberate No. A returned Resume is delivery, never
        gameplay or a saved checkpoint. Unknown/prepared input cannot qualify.
        """
        rows = self.request_records()
        positions = {row["request"]["request_id"]: index for index, row in enumerate(rows)}
        if launch_request_id not in positions or exit_root_id is not None and exit_root_id not in positions:
            raise LedgerError("Menu cleanup lost its exact launch/exit root")
        start = positions[launch_request_id]
        stop = len(rows) if exit_root_id is None else positions[exit_root_id]
        if stop <= start:
            raise LedgerError("Menu cleanup exit precedes its launch")
        selected = rows[start + 1:stop]
        selected_ids = {row["request"]["request_id"] for row in selected}
        indexed = {row["request"]["request_id"]: row for row in rows}
        primitives = self.primitive_records()
        setup = []
        for row in selected:
            data = row["request"]
            if data["kind"] == "lifecycle" and data["operation"] in ("create", "load", "save"):
                if row["state"] in ("accepted", "running", "unknown"):
                    raise LedgerError("Menu cleanup cannot interrupt unsettled character setup")
            if data["kind"] == "lifecycle" and data["operation"] == "exit" and data["phase_id"] is None:
                family = [member for member in selected if member["request"]["request_id"] == data["request_id"]
                          or member["request"].get("phase_id") == data["request_id"]]
                identities = {member["request"]["request_id"] for member in family}
                inputs = [p for p in primitives if p["request_id"] in identities]
                self._check_prior_menu_exit(family, inputs)
        for primitive in primitives:
            if primitive["request_id"] not in selected_ids:
                continue
            data = indexed[primitive["request_id"]]["request"]
            root = indexed[data.get("phase_id") or data["request_id"]]["request"]
            if root["kind"] == "lifecycle" and root["operation"] == "exit":
                continue
            setup.append(primitive)
        if not setup:
            return None
        if len(setup) != 1:
            raise LedgerError("No-save cleanup permits only one returned setup Resume")
        primitive = setup[0]
        owner = indexed[primitive["request_id"]]
        data, intent, receipt = owner["request"], primitive["intent"], primitive["result"] or {}
        native = json_object(receipt["native_request_json"]) if receipt.get("native_request_json") else {}
        binding = receipt.get("dispatch_binding") or {}
        if (data["kind"] != "lifecycle" or data["operation"] not in ("create", "load") or data["phase_id"] is not None
                or primitive["state"] != "returned" or primitive["effect"] is not None
                or intent["kind"] != "resume" or intent["value"] is not None
                or primitive["native_id"] is None or receipt.get("published") is not True
                or receipt.get("transport_disposition") != "returned"
                or receipt.get("logical_action_id") != primitive["logical_id"]
                or receipt.get("native_request_id") != primitive["native_id"]
                or any(receipt.get(key) != intent[key] for key in ("kind", "value", "expected_session",
                    "expected_revision", "expected_boundary_id", "source_before", "preflight_source"))
                or not receipt.get("source_after") or receipt.get("received_monotonic") is None
                or native.get("protocol") != 6 or native.get("kind") != "resume"
                or native.get("id") != primitive["native_id"] or native.get("require_exact_frame") is not True
                or native.get("session") != intent["expected_session"]
                or native.get("revision") != intent["expected_revision"]
                or native.get("boundary_id") != intent["expected_boundary_id"]
                or native.get("takeover_generation") != binding.get("takeover_generation")
                or native.get("authority", {}).get("controller_boot_id") != binding.get("controller_boot_id")
                or set(binding) != {"controller_boot_id", "operator_pause_generation", "takeover_generation",
                                    "actor_id", "epoch", "game_anchor_source_id"}
                or not isinstance(binding.get("controller_boot_id"), str) or not binding["controller_boot_id"]
                or binding.get("epoch") != owner["epoch"]
                or binding.get("actor_id") != self._get("admission")["player_id"]
                or any(type(binding.get(key)) is not int or binding[key] < 0
                       for key in ("operator_pause_generation", "takeover_generation", "epoch"))):
            raise LedgerError("Menu cleanup lost its exact returned Resume/native correlation")
        return primitive

    @staticmethod
    def _check_prior_menu_exit(family: list[dict], inputs: list[dict]) -> None:
        if any(member["state"] in ("accepted", "running", "unknown") for member in family):
            raise LedgerError("Menu cleanup cannot skip an unsettled prior exit")
        if not inputs:
            return
        expected = [("resume", None, "returned"), ("action", "QUIT", "returned"), ("action", "NO", "returned")]
        actual = [(p["intent"]["kind"], p["intent"]["value"], p["state"]) for p in inputs]
        final = next(member for member in family if member["request"]["request_id"] == inputs[-1]["request_id"])
        result, data = final["result"] or {}, final["request"]
        if (actual != expected or final["state"] != "partial" or result.get("normal_exit_verified") is not False
                or result.get("phase", {}).get("stage") != "complete"
                or (data.get("perception") or {}).get("question") != "Really quit?"
                or data.get("goal", {}).get("label") != "No"):
            raise LedgerError("Menu cleanup cannot skip an unverified prior exit")

    def _check_menu_cleanup_sources(self, proof: dict, root_id: str) -> None:
        resume = self.menu_cleanup_resume(proof["launch_request_id"], exit_root_id=root_id)
        if resume is not None and not {resume["intent"]["source_before"], resume["intent"]["preflight_source"],
                                      resume["result"]["source_after"]} <= set(proof["source_ids"]):
            raise LedgerError("No-save exit omitted its returned Resume evidence")

    def _check_normal_exit(self, request_id: str, data: dict, result: dict) -> None:
        proof = validate_normal_exit(result["normal_exit"])
        phase = result.get("phase", {})
        if type(phase) is not dict:
            raise LedgerError("Normal exit requires a typed phase object")
        root = self.request(proof["origin_request_id"])["request"]
        if (data["kind"] != "skill" or data["skill_kind"] != "menu" or data["phase_id"] != root["request_id"]
                or root.get("operation") != "exit" or root["phase_id"] is not None
                or phase.get("phase_kind") != "lifecycle" or phase.get("stage") != "complete"
                or phase.get("origin_request_id") != root["request_id"]
                or any(phase.get(key) != proof[key] for key in ("launch_request_id", "launch_id", "source_ids"))
                or data["goal"]["label"] != "Yes" or data["goal"]["outcome"] != "activated"
                or data["perception"] is None or data["perception"]["kind"] != "confirmation"
                or data["perception"]["question"] != "Really quit?"):
            raise LedgerError("Normal exit lacks its exact root/confirmation phase")
        primitive = self.primitive(proof["terminal_logical_id"])
        if (primitive["request_id"] != request_id or primitive["intent"]["kind"] != "action"
                or primitive["intent"]["value"] != "YES" or primitive["native_id"] != proof["native_request_id"]
                or primitive["state"] not in ("unknown", "returned")
                or primitive["intent"]["source_before"] not in proof["source_ids"]
                or not self._exit_confirmation(primitive["intent"], data)
                or primitive["result"] is None or primitive["result"].get("published") is not True
                or primitive["result"].get("native_request_id") != proof["native_request_id"]
                or any(primitive["result"].get(key) != value for key, value in {
                    "logical_action_id": proof["terminal_logical_id"], "kind": "action", "value": "YES",
                    "transport_disposition": primitive["state"], "expected_session": primitive["intent"]["expected_session"],
                    "expected_revision": primitive["intent"]["expected_revision"],
                    "expected_boundary_id": primitive["intent"]["expected_boundary_id"],
                    "source_before": primitive["intent"]["source_before"], "preflight_source": primitive["intent"]["preflight_source"],
                }.items())
                or primitive["state"] == "unknown" and primitive["effect"] is None):
            raise LedgerError("Normal exit lacks its charged terminal input/effect correlation")
        if primitive["state"] == "unknown" and primitive["effect"] != effect_reconciliation(proof,
                sources=tuple(proof["source_ids"]),
                note=f"Owned normal exit {proof['launch_id']} after published YES; ACK remains unknown"):
            raise LedgerError("Normal exit effect evidence differs from the exact owned phase")
        if not proof["no_save_required"]:
            _, saved = self._lifecycle_record(root["request_id"], proof["saved_checkpoint_request_id"], "saved_checkpoint")
            saved = validate_saved_checkpoint(saved)
            _, transition = self._lifecycle_record(proof["saved_checkpoint_request_id"], saved["transition_result_request_id"],
                "lifecycle_transition", current_result=self.request(proof["saved_checkpoint_request_id"])["result"])
            if (phase.get("no_save_required") is not False
                    or phase.get("saved_checkpoint_request_id") != proof["saved_checkpoint_request_id"]
                    or transition["launch_id"] != proof["launch_id"]
                    or transition["launch_request_id"] != proof["launch_request_id"]
                    or saved["menu_source_id"] not in proof["source_ids"]):
                raise LedgerError("Saved-character exit lost its same-child saved checkpoint")
        elif phase.get("no_save_required") is not True:
            raise LedgerError("Untouched-menu exit cannot borrow a saved-character phase")
        else:
            self._check_menu_cleanup_sources(proof, root["request_id"])

    def complete_request(self, request_id: str, disposition: str, result: dict, *, now: float) -> dict:
        if disposition not in REQUEST_STATES - {"accepted", "running"}: raise LedgerError("Invalid operation result")
        if "normal_exit" in result and disposition != "completed":
            raise LedgerError("A verified normal-exit result requires completed effect reconciliation")
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
            self._check_prompt_result(request_id, old["request"], json_object(encoded), actor_id=state["player_id"],
                                      request_state=disposition)
            unresolved = self._db.execute("SELECT 1 FROM primitives WHERE request_id=? AND (state IN ('prepared','published') OR (state='unknown' AND effect IS NULL))", (request_id,)).fetchone()
            if disposition == "completed" and unresolved: raise LedgerError("Unresolved effects cannot silently become completion")
            self._release(f"request:{request_id}")
            self._db.execute("UPDATE requests SET state=?,result=? WHERE id=?", (disposition, encoded, request_id))
            if disposition in ("unknown", "paused") and state["phase"] not in TERMINAL | {"paused"}:
                state.update(phase="paused", epoch=state["epoch"] + 1, pause_cause="unknown",
                             reason="Operation stopped without input authority")
                self._put("state", state)
        return self.request(request_id)

    def _check_normal_finish(self, request_id: str, data: dict, value: dict) -> None:
        proof = validate_normal_finish(value)
        exit_row = self._earlier_request(request_id, proof["normal_exit_result_request_id"])
        result = exit_row["result"]
        if (data["kind"] != "lifecycle" or data["operation"] != "finish" or data["phase_id"] is not None
                or data["identity_claim_ids"] or exit_row["state"] != "completed" or result is None
                or "normal_exit" not in result or proof["final_source_id"] not in data["sources"]):
            raise LedgerError("Normal finish requires its exact prior exit and retained informing source")
        exit_proof = validate_normal_exit(result["normal_exit"])
        if proof["final_source_id"] not in exit_proof["source_ids"]:
            raise LedgerError("Final source does not belong to the normal exit")
        prior = []
        for row in self.request_records():
            if row["request"]["request_id"] == request_id:
                break
            prior.append(row)
        launched = {row["request"]["request_id"] for row in prior
            if row["request"].get("operation") == "launch" and (row["result"] is None
                or row["state"] in ("accepted", "running", "unknown") or row["result"].get("launch_attempted", False))}
        exited = [row for row in prior if row["state"] == "completed" and row["result"] is not None
            and "normal_exit" in row["result"]]
        closed = [validate_normal_exit(row["result"]["normal_exit"])["launch_request_id"] for row in exited]
        if (not launched or set(closed) != launched or len(closed) != len(set(closed))
                or not exited or exited[-1]["request"]["request_id"] != proof["normal_exit_result_request_id"]):
            raise LedgerError("Normal finish requires every owned launch's unique committed exit")
        event = proof["completed_work_event_id"]
        if event is None:
            if data["work_id"] is not None:
                raise LedgerError("Stopped cleanup cannot claim objective Work completion")
            return
        prior_ids = {row["request"]["request_id"] for row in prior}
        # A historical report is an as-of statement. Later legitimate Work
        # updates may change a future finish, never poison its earlier ledger.
        entries = tuple(row for row in self.memory_records("work") if row["event_id"] in prior_ids)
        selected = [row for row in entries if row["event_id"] == event]
        if len(selected) != 1:
            raise LedgerError("Objective finish requires its exact retained Work event")
        entry = selected[0]["entry"]
        memory_request = self._earlier_request(request_id, event)["request"]
        _, saved = self._lifecycle_record(request_id, exit_proof.get("saved_checkpoint_request_id", ""), "saved_checkpoint")
        _, adoption = self._lifecycle_record(request_id, saved["adoption_result_request_id"], "normal_adoption")
        if (memory_request["kind"] != "remember" or memory_request["entry_type"] != "work"
                or memory_request["entry"] != entry or entry["id"] != data["work_id"]
                or entry["intent"] != self._get("admission")["objective"] or entry["status"] != "completed"
                or entry["unresolved_effects"] or not entry["sources"] or entry["scope"] != adoption["scope"]
                or any(row["entry"]["id"] == entry["id"] for row in entries[entries.index(selected[0]) + 1:])):
            raise LedgerError("Objective finish lost its latest completed, supported and scoped Work report")

    def finish_mission(self, disposition: str, *, epoch: int, request_id: str | None, reason: str, now: float) -> dict:
        """Record runtime-verified ending; operational evidence stays in its journal."""
        if disposition not in TERMINAL or not isinstance(reason, str) or not 1 <= len(reason) <= 1024:
            raise LedgerError("Invalid mission ending")
        with self._transaction():
            state = self._touch(now)
            if type(epoch) is not int or state["epoch"] != epoch:
                raise LedgerError("Mission ending lost its exact epoch")
            if request_id is not None:
                operation = self.request(request_id)
                result = operation["result"] or {}
                if (operation["state"] != "completed" or "normal_finish" not in result
                        or result["normal_finish"]["disposition"] != disposition
                        or self.request_records()[-1]["request"]["request_id"] != request_id):
                    raise LedgerError("Normal terminal transition requires its exact latest committed finish report")
                self._check_normal_finish(request_id, operation["request"], result["normal_finish"])
                if now >= min(operation["deadline"], state["deadline"]):
                    raise BudgetError("Original normal-finish deadline expired before terminal persistence")
            elif disposition == "completed":
                raise LedgerError("Completion requires its exact normal-finish operation")
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
                completed = [row for row in self.request_records() if row["state"] == "completed"
                    and row["result"] is not None and row["result"].get("normal_finish", {}).get("disposition") == "completed"]
                if not completed:
                    raise LedgerError("Mission completion requires its immutable NormalFinish report")
                if completed[-1]["request"]["request_id"] != self.request_records()[-1]["request"]["request_id"]:
                    raise LedgerError("Mission completion cannot reuse an older finish report")
            self._settle_reflection()
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
        if (data["mission_id"] if entry_type == "procedure" else data["scope"]["mission_id"]) != self.admission.mission_id:
            raise LedgerError("Memory belongs to another mission")
        encoded = _json(data)
        with self._transaction():
            self._touch(now)
            old = self._db.execute("SELECT sequence,entry_type,body FROM memory WHERE event_id=?", (event_id,)).fetchone()
            if old:
                if old[1:] != (entry_type, encoded): raise LedgerError("Memory event identity reused")
                return old[0]
            maximum = {"claim": 2048, "work": 256, "decision": 2048, "procedure": 256}[entry_type]
            if self._db.execute("SELECT count(*) FROM memory WHERE entry_type=?", (entry_type,)).fetchone()[0] >= maximum:
                raise BudgetError("Memory event retention limit reached")
            if entry_type != "work" and self._db.execute("SELECT 1 FROM memory WHERE entry_type=? AND record_id=?", (entry_type, data["id"])).fetchone():
                raise LedgerError("An immutable assertion/decision identity cannot be overwritten")
            if entry_type == "work":
                self._check_work_lineage(data, {row["entry"]["id"]: row["entry"] for row in self.memory_records("work")})
            if entry_type == "procedure":
                self._check_procedure_lineage(data, [row["entry"] for row in self.memory_records("procedure")], self.admission)
            cursor = self._db.execute("INSERT INTO memory(event_id,entry_type,record_id,body) VALUES (?,?,?,?)", (event_id, entry_type, data["id"], encoded))
            return cursor.lastrowid

    def memory_records(self, entry_type: str) -> tuple[dict, ...]:
        if entry_type not in ("claim", "work", "decision", "procedure"): raise LedgerError("Unknown memory type")
        with self._mutex:
            if self._db is None: raise LedgerError("Ledger is closed")
            return tuple({"sequence": row[0], "event_id": row[1], "entry": json_object(row[2])}
                         for row in self._db.execute("SELECT sequence,event_id,body FROM memory WHERE entry_type=? ORDER BY sequence", (entry_type,)))

    @staticmethod
    def _check_procedure_lineage(entry: dict, previous: list[dict], admission: MissionAdmission) -> None:
        policy = admission.learning
        if policy is None or entry["environment"] != dict(policy.environment):
            raise LedgerError("Procedure requires its exact admitted learning environment")
        parent = entry["parent"]
        family = [record for record in previous if record["procedure_id"] == entry["procedure_id"]]
        if parent is None:
            if family or entry["revision"] != 1:
                raise LedgerError("Procedure family must have one first revision")
        else:
            if any(record["parent"] == parent for record in previous):
                raise LedgerError("Procedure ancestry cannot branch")
            if parent["mission_id"] == admission.mission_id:
                matches = [record for record in previous if record["id"] == parent["revision_id"]]
                if (not matches or matches[0]["procedure_id"] != entry["procedure_id"]
                        or matches[0]["revision"] + 1 != entry["revision"]):
                    raise LedgerError("Procedure parent must be an earlier consecutive family revision")
            elif parent["mission_id"] not in {source.mission_id for source in policy.library_sources}:
                raise LedgerError("Historical procedure parent must be explicitly admitted")

    def reflection_records(self) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
        """Original advisory jobs/proposals, on a sequence separate from memory."""
        with self._mutex:
            jobs, proposals = [], []
            for payload, state, claimed, deadline, proposal in self._db.execute(
                    "SELECT payload,state,claimed_at,deadline,proposal FROM reflection_jobs ORDER BY sequence"):
                jobs.append(dict(job=json_object(payload), state=state, claimed_at=claimed, deadline=deadline))
                if proposal is not None:
                    proposals.append(json_object(proposal))
            return tuple(jobs), tuple(proposals)

    def reflection_command_records(self) -> tuple[dict, ...]:
        """Read original durable advisory receipts for writer cache restoration."""
        from .reflection import validate_command
        with self._mutex:
            return tuple(dict(command=validate_command(payload), result=json_object(result),
                              received_at=float(received_at))
                         for payload, result, received_at in self._db.execute(
                             "SELECT payload,result,received_at FROM reflection_commands ORDER BY rowid"))

    def record_reflection_rejection(self, value: dict, reason: str, *, now: float, received_at: float) -> dict:
        """Retain an admitted command's semantic refusal without work/input charges."""
        from .reflection import validate_command
        now, received_at = _clock(now), _clock(received_at)
        if received_at > now:
            raise LedgerError("Advisory ingress time cannot be after writer drain time")
        command = validate_command(value)
        policy = self.admission.learning
        if (policy is None or command["mission_id"] != self.admission.mission_id
                or command["reflector_id"] != policy.reflector_id):
            raise LedgerError("Reflective command actor/mission was not admitted")
        if not isinstance(reason, str) or not 1 <= len(reason) <= 1024:
            raise LedgerError("Reflection refusal requires a bounded reason")
        with self._transaction():
            old = self._db.execute("SELECT payload,result FROM reflection_commands WHERE id=?",
                (command["command_id"],)).fetchone()
            if old:
                if old[0] != canonical(command):
                    raise LedgerError("Reflective command identity changed")
                return json_object(old[1])
            if self._get("state")["phase"] in TERMINAL:
                raise LedgerError("Sealed terminal mission accepts no late advisory writes")
            self._touch(now)
            if self._db.execute("SELECT count(*) FROM reflection_commands").fetchone()[0] >= 128:
                raise BudgetError("Reflective command retention exhausted")
            result = dict(status="rejected", reason=reason, grants_authority=False)
            self._db.execute("INSERT INTO reflection_commands(id,payload,result,received_at) VALUES (?,?,?,?)",
                (command["command_id"], canonical(command), canonical(result), received_at))
        return result

    def _settle_reflection(self) -> None:
        """Use the caller's writer transaction; elapsed model computation is unknown."""
        self._db.execute("UPDATE reflection_jobs SET state='unknown' WHERE state='claimed'")
        self._db.execute("UPDATE reflection_jobs SET state='unreviewed' WHERE state='offered'")

    def settle_reflection(self, *, now: float) -> None:
        """Close outstanding advisory work before sealing, without renewing windows."""
        with self._mutex:
            if self._get("state")["phase"] in TERMINAL:
                return
            with self._transaction():
                self._touch(now)
                self._settle_reflection()

    def _reflection_trace(self, job: dict) -> None:
        """Compare job data with original durable rows, never model-written history."""
        rows = self._db.execute("SELECT rowid,payload,state,result FROM requests WHERE rowid>? AND rowid<=? ORDER BY rowid",
            (job["after_sequence"], job["through_sequence"])).fetchall()
        original = {}
        for sequence, payload, state, result in rows:
            request = json_object(payload)
            if request["kind"] not in ("start", "remember", "correct"):
                original[request["request_id"]] = (sequence, dict(request=request, state=state,
                    result=None if result is None else json_object(result)))
        if len(original) - len(job["trajectory"]) != job["omitted_requests"]:
            raise LedgerError("Reflection coverage must retain its original omitted request count")
        ordered = []
        linked_sources = set()
        primitives_by_request = {}
        for primitive in self.primitive_records():
            primitives_by_request.setdefault(primitive["request_id"], []).append(primitive)
        for row in job["trajectory"]:
            identity = row["request"]["request_id"]
            if identity not in original or canonical(original[identity][1]) != canonical(row):
                raise LedgerError("Reflection trajectory differs from its original settled request/result")
            ordered.append(original[identity][0])
            linked_sources.update(row["request"].get("sources", ()))
            linked_sources.update(row["result"].get("source_ids", ()))
            for primitive in primitives_by_request.get(identity, ()):
                linked_sources.update(primitive["intent"][key] for key in ("source_before", "preflight_source"))
                receipt = primitive["result"] or {}
                linked_sources.update(receipt[key] for key in ("source_before", "preflight_source", "source_after")
                                      if receipt.get(key) is not None)
        if ordered != sorted(ordered):
            raise LedgerError("Reflection trajectory changed original request order")
        if any(source["mission_id"] != job["mission_id"] or source["source_id"] not in linked_sources
               for source in job["sources"]):
            raise LedgerError("Reflection source is unrelated to its original trajectory")

    def append_reflection_job(self, value: dict, *, now: float) -> dict:
        from .reflection import validate_job
        job = validate_job(value)
        policy = self.admission.learning
        if policy is None or policy.reflector_id != job["reflector_id"] or job["mission_id"] != self.admission.mission_id:
            raise LedgerError("Reflection actor/mission was not admitted")
        limits = policy.reflection_limits
        if (len(job["trajectory"]) > limits.requests_per_job or len(job["sources"]) > limits.sources_per_job
                or len(canonical(job).encode()) > limits.context_bytes):
            raise BudgetError("Reflection job exceeds its frozen context bounds")
        with self._transaction():
            state = self._touch(now)
            if state["phase"] in TERMINAL | {"finishing"} or now >= state["deadline"]:
                raise LedgerError("Reflection cannot start after finishing or expiry")
            prior = self._db.execute("SELECT payload FROM reflection_jobs WHERE id=?", (job["id"],)).fetchone()
            if prior:
                if prior[0] != canonical(job):
                    raise LedgerError("Reflection job identity cannot change")
                return job
            counts = self._db.execute("SELECT count(*),coalesce(sum(state IN ('offered','claimed')),0) FROM reflection_jobs").fetchone()
            if counts[0] >= limits.jobs or counts[1] >= limits.pending:
                raise BudgetError("Reflection job/pending allowance exhausted")
            previous = self._db.execute("SELECT coalesce(max(json_extract(payload,'$.through_sequence')),0) FROM reflection_jobs").fetchone()[0]
            current = self._db.execute("SELECT coalesce(max(rowid),0) FROM requests").fetchone()[0]
            memory = self._db.execute("SELECT coalesce(max(sequence),0) FROM memory").fetchone()[0]
            if (job["after_sequence"] != previous or job["through_sequence"] != current
                    or job["epoch"] != state["epoch"] or job["memory_version"] != memory):
                raise LedgerError("Reflection job must name the actual current cutoff/version")
            self._reflection_trace(job)
            self._db.execute("INSERT INTO reflection_jobs(id,payload,state,charged_seconds) VALUES (?,?,'offered',0)",
                (job["id"], canonical(job)))
        return job

    def expire_reflection(self, *, now: float) -> None:
        with self._mutex:
            if self._get("state")["phase"] in TERMINAL:
                return
            with self._transaction():
                state = self._touch(now)
                self._db.execute("UPDATE reflection_jobs SET state='expired' WHERE state='claimed' AND deadline<?", (now,))
                if state["phase"] == "finishing":
                    self._db.execute("UPDATE reflection_jobs SET state='unreviewed' WHERE state='offered'")

    def apply_reflection(self, value: dict, *, now: float, received_at: float | None = None) -> dict:
        """Short writer-only bookkeeping; reserves finite claim windows, never input."""
        from .reflection import validate_command, validate_proposal
        now = _clock(now)
        received_at = _clock(now if received_at is None else received_at)
        if received_at > now:
            raise LedgerError("Advisory ingress time cannot be after writer drain time")
        try:
            command = validate_command(value)
        except ContractError as exc:
            raise ReflectionRefusal(str(exc)) from exc
        policy = self.admission.learning
        if (policy is None or command["mission_id"] != self.admission.mission_id
                or command["reflector_id"] != policy.reflector_id):
            raise ReflectionRefusal("Reflective command actor/mission was not admitted")
        with self._transaction():
            old = self._db.execute("SELECT payload,result FROM reflection_commands WHERE id=?", (command["command_id"],)).fetchone()
            if old:
                if old[0] != canonical(command):
                    raise ReflectionRefusal("Reflective command identity changed")
                return json_object(old[1])
            if self._get("state")["phase"] in TERMINAL:
                raise ReflectionRefusal("Sealed terminal mission accepts no late advisory writes")
            state = self._touch(now)
            if self._db.execute("SELECT count(*) FROM reflection_commands").fetchone()[0] >= 128:
                raise ReflectionBudgetRefusal("Reflective command retention exhausted")
            row = self._db.execute("SELECT payload,state,claimed_at,deadline,proposal FROM reflection_jobs WHERE id=?", (command["job_id"],)).fetchone()
            if row is None:
                raise ReflectionRefusal("Reflective command has no original job")
            job = json_object(row[0])
            result = {"job_id": job["id"], "grants_authority": False}
            limits = policy.reflection_limits
            if command["kind"] == "claim":
                if row[1] != "offered" or state["phase"] == "finishing" or now >= state["deadline"]:
                    raise ReflectionRefusal("Reflection job cannot be claimed or renewed")
                reserved = float(min(limits.job_seconds, state["deadline"] - now))
                spent = self._db.execute("SELECT coalesce(sum(charged_seconds),0) FROM reflection_jobs").fetchone()[0]
                if spent + reserved > limits.total_seconds:
                    raise ReflectionBudgetRefusal("Original reflective claim-window allowance exhausted")
                self._db.execute("UPDATE reflection_jobs SET state='claimed',claimed_at=?,deadline=?,charged_seconds=? WHERE id=?",
                    (now, now + reserved, reserved, job["id"]))
                result.update(state="claimed", claimed_at=now, deadline=now + reserved, charged_seconds=reserved,
                    measurement="Conservative claimed wall window; model compute/tokens unknown")
            else:
                try:
                    proposal = validate_proposal(command["proposal"], job)
                except ContractError as exc:
                    raise ReflectionRefusal(str(exc)) from exc
                if row[2] is None or row[1] not in ("claimed", "expired", "unknown"):
                    raise ReflectionRefusal("Proposal needs its original claimed job")
                if row[4] is not None:
                    raise ReflectionRefusal("A claimed job retains one immutable proposal")
                if self._db.execute("SELECT 1 FROM reflection_jobs WHERE json_extract(proposal,'$.id')=?",
                                    (proposal["id"],)).fetchone():
                    raise ReflectionRefusal("A proposal identity belongs to one immutable original job")
                if len(canonical(proposal).encode()) > limits.result_bytes:
                    raise ReflectionBudgetRefusal("Proposal exceeds its original result allowance")
                if any(candidate["mission_id"] != job["mission_id"] or candidate["environment"] != dict(policy.environment)
                       for candidate in proposal["candidates"]):
                    raise ReflectionRefusal("Proposal candidate changed admitted owner/environment")
                if received_at < row[2]:
                    raise ReflectionRefusal("Advisory output predates its original claim")
                late = received_at > row[3] or row[1] == "unknown"
                self._db.execute("UPDATE reflection_jobs SET state=?,proposal=? WHERE id=?",
                    ("expired" if late else "completed", canonical(proposal), job["id"]))
                result.update(state="expired" if late else "completed", proposal_id=proposal["id"],
                    observed_claim_elapsed_seconds=received_at - row[2], late=late,
                    measurement="Observed claim-to-submit wall elapsed; model compute/tokens unknown")
            self._db.execute("INSERT INTO reflection_commands(id,payload,result,received_at) VALUES (?,?,?,?)",
                (command["command_id"], canonical(command), canonical(result), received_at))
        return result

    def _verify_reflection(self, admission: MissionAdmission, state: dict) -> None:
        from .reflection import validate_job, validate_command, validate_proposal
        rows = self._db.execute("SELECT id,payload,state,claimed_at,deadline,charged_seconds,proposal FROM reflection_jobs ORDER BY sequence").fetchall()
        policy = admission.learning
        if rows and (policy is None or policy.reflector_id is None):
            raise LedgerError("Unadmitted reflective history")
        if len(rows) > (0 if policy is None else policy.reflection_limits.jobs):
            raise LedgerError("Reflective history exceeds frozen job count")
        previous, spent, proposals = 0, 0, set()
        by_id = {}
        for identity, payload, job_state, claimed, deadline, cost, proposal in rows:
            job = validate_job(payload)
            if (job["id"] != identity or payload != canonical(job) or job["mission_id"] != admission.mission_id
                    or job["reflector_id"] != policy.reflector_id or job["after_sequence"] != previous
                    or job_state not in ("offered", "claimed", "completed", "expired", "unknown", "unreviewed")
                    or job["epoch"] > state["epoch"]
                    or state["phase"] in TERMINAL and job_state in ("offered", "claimed")):
                raise LedgerError("Corrupt reflective job identity/cutoff/state")
            self._reflection_trace(job)
            if claimed is None:
                if deadline is not None or cost != 0 or job_state not in ("offered", "unreviewed") or proposal is not None:
                    raise LedgerError("Unclaimed reflection cannot assert computation or output")
            else:
                _clock(claimed); _clock(deadline)
                if (not 0 < cost <= policy.reflection_limits.job_seconds or deadline != claimed + cost
                        or job_state in ("offered", "unreviewed") or claimed < state["started_at"]):
                    raise LedgerError("Original reflective claim window changed")
                spent += cost
            if proposal is not None:
                output = validate_proposal(proposal, job)
                if output["id"] in proposals or proposal != canonical(output) or job_state not in ("completed", "expired"):
                    raise LedgerError("Corrupt reflective proposal identity/state")
                proposals.add(output["id"])
            elif job_state == "completed":
                raise LedgerError("Completed reflection lost its proposal")
            previous = job["through_sequence"]
            by_id[identity] = (job, job_state, claimed, deadline, cost, proposal)
        if policy is not None and spent > policy.reflection_limits.total_seconds:
            raise LedgerError("Original reflective wall-window allowance changed")
        commands = self._db.execute("SELECT id,payload,result,received_at FROM reflection_commands").fetchall()
        if len(commands) > 128:
            raise LedgerError("Reflective command retention exceeded")
        claims, submissions = set(), set()
        for identity, payload, encoded_result, received_at in commands:
            _clock(received_at)
            command = validate_command(payload)
            result = json_object(encoded_result)
            if (command["command_id"] != identity or payload != canonical(command) or canonical(result) != encoded_result
                    or command["mission_id"] != admission.mission_id or policy is None
                    or command["reflector_id"] != policy.reflector_id
                    or received_at > state["last_wall"]):
                raise LedgerError("Corrupt reflective command identity/result")
            if result.get("status") == "rejected":
                if (set(result) != {"status", "reason", "grants_authority"}
                        or result["grants_authority"] is not False
                        or not isinstance(result["reason"], str) or not 1 <= len(result["reason"]) <= 1024):
                    raise LedgerError("Corrupt reflective rejection result")
                continue
            if command["job_id"] not in by_id:
                raise LedgerError("Reflective command has no original job")
            job, job_state, claimed, deadline, cost, proposal = by_id[command["job_id"]]
            if command["kind"] == "claim":
                expected = dict(job_id=job["id"], grants_authority=False, state="claimed", claimed_at=claimed,
                    deadline=deadline, charged_seconds=cost,
                    measurement="Conservative claimed wall window; model compute/tokens unknown")
                if claimed is None or received_at > claimed or job["id"] in claims or canonical(result) != canonical(expected):
                    raise LedgerError("Reflective claim receipt contradicts its original window")
                claims.add(job["id"])
            else:
                if proposal is None or canonical(command["proposal"]) != proposal or job["id"] in submissions:
                    raise LedgerError("Reflective submission contradicts its immutable original output")
                output = validate_proposal(proposal, job)
                elapsed = result.get("observed_claim_elapsed_seconds")
                _clock(elapsed)
                expected = dict(job_id=job["id"], grants_authority=False, state=job_state, proposal_id=output["id"],
                    observed_claim_elapsed_seconds=elapsed, late=job_state == "expired",
                    measurement="Observed claim-to-submit wall elapsed; model compute/tokens unknown")
                if (claimed is None or elapsed != received_at - claimed
                        or job_state == "completed" and elapsed > cost or canonical(result) != canonical(expected)):
                    raise LedgerError("Reflective submission receipt changed its original elapsed time/state")
                submissions.add(job["id"])
        if claims != {identity for identity, row in by_id.items() if row[2] is not None}:
            raise LedgerError("Claimed reflection lost its original durable command")
        if submissions != {identity for identity, row in by_id.items() if row[5] is not None}:
            raise LedgerError("Reflective output lost its original durable submission")
