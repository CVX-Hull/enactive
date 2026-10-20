"""Strict mission/3 data. Parsing never grants a controller capability.

The existing JSON decoder/schema helpers own duplicate, finite-number and strict
integer validation. Request dictionaries are decoded copies, not mutable aliases.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any

from .contracts import (
    ContractError, _array, _enum, _integer, _nullable, _number, _object, _text,
    json_object, validate_json,
)

VERSION = "mission/3"
MEMORY_VERSION = "campaign-memory/2"
MAX_REQUEST_BYTES = 65_536
MAX_CONTEXT_BYTES = 32_768
SKILLS = ("navigate", "menu", "item", "activity", "inspect", "edit", "interact")
LIFECYCLE = ("launch", "create", "save", "exit", "load", "finish")
INTERACTIONS = (
    "UP", "DOWN", "LEFT", "RIGHT", "open", "close", "smash", "examine", "examine_and_pickup",
    "apply", "apply_wielded", "wear", "take_off", "wield", "reload_item", "reload_weapon",
    "reload_wielded", "insert", "unload", "unload_container", "read", "butcher", "construct",
    "disassemble", "inventory", "open_consume", "eat", "pickup", "drop", "wait", "sleep",
    "craft", "recraft", "look", "peek",
)
EDITOR_PURPOSES = ("character_name", "world_name", "quantity", "filter")
_ID = {**_text(128), "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]*$"}
_IDS = _array(_ID, 8)
_IDS["uniqueItems"] = True
_TIME = _integer(2**63 - 1)
_TURN = _integer(2**31 - 1, -(2**31))
_VEC = {"type": "array", "items": _integer(1_000_000, -1_000_000),
        "minItems": 3, "maxItems": 3}
_SHA = {"type": "string", "pattern": "^[a-f0-9]{64}$"}

_LIMITS = _object({
    "inputs": _integer(8192, 1), "wall_seconds": _number(86_400),
    "game_seconds": _integer(604_800, 1), "frames": _integer(4096, 1),
    "frame_bytes": _integer(1_073_741_824, 1),
    "requests": _integer(4096, 1), "primitive_mappings": _integer(8192, 1),
})
_RESERVE = _object({"inputs": _integer(8192, 1), "wall_seconds": _number(86_400),
                    "frames": _integer(4096, 1), "frame_bytes": _integer(1_073_741_824, 1)})
_SCENARIO = _object({"mode": _enum("fresh", "load"), "world": _text(80),
                     "character": _text(80)})
_CONFIGURATION = _object({
    "source_commit": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
    "native_sha256": _SHA, "skills": _text(128), "lessons": _text(128),
    "model": _text(128), "effort": _text(64),
})
_ADMISSION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "MissionAdmission"},
    "mission_id": _ID, "objective": _text(2000), "player_id": _ID,
    "scenario": _SCENARIO, "limits": _LIMITS, "cleanup_reserve": _RESERVE,
    "allowed_skills": {**_array(_enum(*SKILLS), len(SKILLS), 1), "uniqueItems": True},
    "allowed_lifecycle": {**_array(_enum(*LIFECYCLE), len(LIFECYCLE)), "uniqueItems": True},
    "update_policy": {"const": "facts-and-provisional/1"}, "configuration": _CONFIGURATION,
})
_SCOPE = _object({"mission_id": _ID, "session": _ID, "coordinate_epoch": _integer()})
_SOURCE_BINDING = _object({
    "source_id": _ID, "mission_id": _ID, "epoch": _integer(), "actor_id": _ID,
    "controller_boot_id": _ID, "pause_generation": _integer(),
    "takeover_generation": _integer(), "store_generation": _integer(),
})
_REVALIDATION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "SourceRevalidation"},
    "original": _SOURCE_BINDING, "current": _SOURCE_BINDING,
    "rule": _enum("native_state", "exact_png_bytes"), "grants_authority": {"const": False},
})
_SKILL_LIMITS = _object({"primitives": _integer(32, 1), "wall_seconds": _number(900),
                         "game_seconds": _integer(43_200, 1)})
_LIFECYCLE_LIMITS = _object({"primitives": _integer(256, 1), "wall_seconds": _number(1800),
                             "game_seconds": _integer(43_200, 1)})
_VIEW_BASE = {"source_id": _ID, "basis": {"const": "player_interpretation"}}
_VIEWS = {
    "menu": _object({**_VIEW_BASE, "kind": {"const": "menu"},
        "control": _enum("vertical", "horizontal", "tabs", "columns"),
        "rows": _array(_object({"label": _text(1024), "enabled": {"type": "boolean"}}), 32, 1),
        "selected": _nullable(_integer(31)), "question": _text(1024, empty=True)}),
    "editor": _object({**_VIEW_BASE, "kind": {"const": "editor"},
        "purpose": _enum(*EDITOR_PURPOSES), "label": _text(1024),
        "visible_text": _text(128, empty=True), "whole_value": {"type": "boolean"},
        "focused": {"type": "boolean"}}),
    "direction": _object({**_VIEW_BASE, "kind": {"const": "direction"}, "question": _text(1024)}),
    "confirmation": _object({**_VIEW_BASE, "kind": {"const": "confirmation"}, "question": _text(1024)}),
    "dismissal": _object({**_VIEW_BASE, "kind": {"const": "dismissal"}, "question": _text(1024)}),
}
_GOALS = {
    "navigate": _object({"scope": _SCOPE, "target": _VEC}),
    "menu": _object({"purpose": _text(128), "label": _text(1024),
                       "outcome": _enum("focused", "activated", "inspected", "dismissed")}),
    "item": _object({"purpose": _enum("pickup", "consume", "drop", "store"),
                       "label": _text(1024), "quantity": _integer(9999, 1),
                       "outcome": _enum("acquired", "consumed", "stored", "dropped")}),
    "activity": _object({"operation": _enum("wait", "rest", "craft"),
                           "target": _text(1024), "game_seconds": _integer(43_200, 1),
                           "interrupt": {"type": "boolean"}}),
    "inspect": _object({"purpose": _enum("inventory", "consume", "needs", "look", "messages", "map", "character_identity")}),
    "edit": _object({"purpose": _enum(*EDITOR_PURPOSES),
        "text": {**_text(24), "pattern": r"^[A-Za-z0-9 _-]+$"}, "commit": {"type": "boolean"}}),
    "interact": _object({"action": _enum(*INTERACTIONS), "intent": _text(1024),
        "desired_outcome": _text(1024)}),
}
_KEY = _object({"subject": _ID, "property": _enum("need", "supply", "place", "work", "identity"),
                "unit": _text(32), "coverage_id": _ID})
_VALUE = _object({"quantity": _nullable(_integer(2**31 - 1)),
                  "state": _nullable(_text(1024))})
_ORDER = _object({"revision": _nullable(_integer()), "turn": _nullable(_TURN)})
_SUPPORT = _object({"sources": _IDS, "claims": _IDS})
_CLAIM = _object({
    "schema": {"const": MEMORY_VERSION}, "record_type": {"const": "Claim"},
    "id": _ID, "kind": _enum("native_fact", "interpretation"), "key": _KEY,
    "value": _VALUE, "text": _text(1024), "scope": _SCOPE,
    "observed_time": _ORDER, "received_time": _TIME, "coverage": _text(1024),
    "sources": _IDS, "supports": _array(_SUPPORT, 8),
    "status": _enum("current", "last_seen", "inferred", "disputed", "retired", "unknown"),
    "supersedes": _IDS,
})
_QUANTITY = _object({"subject": _ID, "quantity": _integer(2**31 - 1),
                     "unit": _text(32), "coverage_id": _ID})
_WORK = _object({
    "schema": {"const": MEMORY_VERSION}, "record_type": {"const": "Work"},
    "id": _ID, "intent": _text(1024), "scope": _SCOPE, "stage": _text(128),
    "predecessor_work_id": _nullable(_ID),
    "progress": _nullable(_integer(100)),
    "available": _array(_QUANTITY, 16), "committed": _array(_QUANTITY, 16),
    "predicted_output": _array(_QUANTITY, 16), "observed_output": _array(_QUANTITY, 16),
    "unresolved_effects": {**_array(_ID, 16), "uniqueItems": True},
    "sources": _IDS, "next_verification": _text(1024),
    "status": _enum("planned", "active", "interrupted", "completed", "failed", "unknown"),
})
_DECISION = _object({
    "schema": {"const": MEMORY_VERSION}, "record_type": {"const": "Decision"},
    "id": _ID, "packet_id": _ID, "scope": _SCOPE, "query": _text(1024), "memory_version": _integer(),
    "claim_ids": {**_array(_ID, 32), "uniqueItems": True},
    "work_ids": {**_array(_ID, 16), "uniqueItems": True},
    "source_ids": {**_array(_ID, 16), "uniqueItems": True},
    "lesson_ids": {**_array(_ID, 16), "uniqueItems": True},
    "omitted": _integer(), "reason": _text(1024),
})
_ENTRIES = {"claim": _CLAIM, "work": _WORK, "decision": _DECISION}
_VISIBLE_UI = _object({
    "purpose": _text(128), "title": _text(1024, empty=True),
    "rows": _array(_object({"id": _ID, "text": _text(1024, empty=True),
                            "enabled": {"type": "boolean"}, "hotkey": _nullable(_text(32))}), 32),
    "selected": _nullable(_ID), "filter": _nullable(_text(128, empty=True)),
    "count": _nullable(_text(32, empty=True)), "coverage": {"const": "rendered_rows_only"},
})
PAUSE_ORIGINS = ("startup", "world_change", "human", "host", "recovery", "fault", "none")
_HANDOFF_BINDING = _object({
    "session": _ID, "revision": _integer(), "boundary_id": _ID,
    "pause_generation": _integer(), "takeover_generation": _integer(),
    "pause_origin": _enum(*PAUSE_ORIGINS),
})
_HANDOFF = _object({
    **_HANDOFF_BINDING["properties"], "schema": {"const": VERSION},
    "record_type": {"const": "Handoff"}, "handoff_id": _ID, "mission_id": _ID,
    "original_player_id": _ID, "successor_role": _ID, "epoch": _integer(),
    "checkpoint_ids": {**_array(_ID, 32), "uniqueItems": True},
    "grants_authority": {"const": False},
})
_CLAIMED_HANDOFF = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "ClaimedHandoff"},
    "handoff_id": _ID, "mission_id": _ID, "player_id": _ID, "actor_role": _ID,
    "epoch": _integer(), "grants_authority": {"const": False},
})
_PROMPT_RECEIPT = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "PhaseReceipt"},
    "origin_request_id": _ID, "phase_kind": {"const": "interact"}, "operation": _enum(*INTERACTIONS),
    "stage": _enum("awaiting_control", "activity_poll", "complete", "unknown"),
    "epoch": _integer(), "actor_id": _ID, "controller_boot_id": _ID,
    "operator_pause_generation": _integer(), "takeover_generation": _integer(),
    "source_ids": {**_IDS, "minItems": 1}, "continuity": {"type": "null"},
    "grants_authority": {"const": False},
})
_EXIT_PHASE_RECEIPT = _object({
    **_PROMPT_RECEIPT["properties"], "phase_kind": {"const": "lifecycle"},
    "operation": {"const": "exit"}, "stage": _enum("awaiting_control", "complete", "unknown"),
    "launch_request_id": _ID, "launch_id": _ID, "no_save_required": {"const": True},
})
_SAVED_EXIT_PHASE = _object({
    **_EXIT_PHASE_RECEIPT["properties"], "no_save_required": {"const": False},
    "saved_checkpoint_request_id": _ID,
})
_NORMAL_LIFECYCLE_PHASE = _object({
    **_PROMPT_RECEIPT["properties"], "phase_kind": {"const": "lifecycle"},
    "operation": _enum("create", "save", "load"),
    "stage": _enum("awaiting_control", "awaiting_transition", "awaiting_identity", "awaiting_adoption", "complete", "unknown"),
    "launch_request_id": _ID, "launch_id": _ID,
})
_EXIT_RETIREMENT = _object({
    "launch_id": _ID, "exit_request_id": _ID, "native_request_id": _nullable(_ID),
    "returncode": {"const": 0}, "retired_pending": {"type": "boolean"},
    "grants_authority": {"const": False},
})
_NORMAL_EXIT = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "OwnedNormalExit"},
    "origin_request_id": _ID, "launch_request_id": _ID, "launch_id": _ID,
    "terminal_logical_id": _ID, "native_request_id": _ID,
    "source_ids": {**_IDS, "minItems": 1}, "no_save_required": {"const": True},
    "returncode": {"const": 0}, "retirement": _EXIT_RETIREMENT,
    "grants_authority": {"const": False},
})
_SAVED_NORMAL_EXIT = _object({
    **_NORMAL_EXIT["properties"], "no_save_required": {"const": False},
    "saved_checkpoint_request_id": _ID,
})
_TRANSITION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "LifecycleTransition"},
    "operation": _enum("create", "save", "load"), "origin_request_id": _ID,
    "terminal_request_id": _ID, "terminal_logical_id": _ID, "native_request_id": _ID,
    "launch_request_id": _ID, "launch_id": _ID,
    "before_source_id": _ID, "after_source_id": _ID,
    "origin_epoch": _integer(), "reconciled_epoch": _integer(), "actor_id": _ID,
    "controller_boot_id": _ID, "operator_pause_generation": _integer(),
    "before_takeover_generation": _integer(), "after_takeover_generation": _integer(),
    "grants_authority": {"const": False},
})
_ADOPTION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "NormalSessionAdoption"},
    "origin_request_id": _ID, "transition_result_request_id": _ID,
    "first_normal_source_id": _ID, "world_claim_id": _ID, "character_claim_id": _ID,
    "identity_inspect_request_id": _ID, "checkpoint_source_id": _ID,
    "saved_checkpoint_request_id": _nullable(_ID), "scope": _SCOPE,
    "grants_authority": {"const": False},
})
_SAVED_CHECKPOINT = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "SavedCheckpoint"},
    "origin_request_id": _ID, "transition_result_request_id": _ID,
    "adoption_result_request_id": _ID, "normal_endpoint_source_id": _ID,
    "menu_source_id": _ID, "grants_authority": {"const": False},
})
_NORMAL_FINISH = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "NormalFinish"},
    "final_source_id": _ID, "normal_exit_result_request_id": _ID,
    "completed_work_event_id": _nullable(_ID), "disposition": _enum("stopped", "completed"),
    "grants_authority": {"const": False},
})


def canonical(value: dict[str, Any]) -> str:
    """Canonical finite JSON for hashing, never shell quoting or game authority."""
    return json.dumps(json_object(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _decode(value: dict | str | bytes, schema: dict, *, maximum=MAX_REQUEST_BYTES) -> dict:
    if isinstance(value, (str, bytes)) and len(value.encode() if isinstance(value, str) else value) > maximum:
        raise ContractError("Mission record exceeds its byte limit")
    result = json_object(value)
    if len(canonical(result).encode()) > maximum:
        raise ContractError("Mission record exceeds its byte limit")
    validate_json(result, schema)
    return result


def validate_handoff_binding(value: dict) -> dict:
    """Runtime-attested post-Pause binding, never a capability or native proof."""
    return _decode(value, _HANDOFF_BINDING)


def validate_handoff_result(value: dict, *, claimed: bool = False) -> dict:
    """Closed durable result; the ledger crosschecks its originating requests."""
    return _decode(value, _CLAIMED_HANDOFF if claimed else _HANDOFF)


def validate_prompt_result(value: dict, *, request: dict, root: dict, actor_id: str) -> dict:
    """Closed ordinary/lifecycle audit data; never restore a live phase."""
    lifecycle = type(value) is dict and value.get("phase_kind") == "lifecycle"
    exit_schema = _SAVED_EXIT_PHASE if lifecycle and value.get("no_save_required") is False else _EXIT_PHASE_RECEIPT
    schema = (exit_schema if value.get("operation") == "exit" else _NORMAL_LIFECYCLE_PHASE) if lifecycle else _PROMPT_RECEIPT
    data = _decode(value, schema)
    valid_root = (root["kind"] == "lifecycle" and root["operation"] in ("exit", "create", "save", "load") if lifecycle else
                  root["kind"] == "skill" and root["skill_kind"] == "interact")
    operation = root.get("operation") if lifecycle else root.get("goal", {}).get("action")
    if (not valid_root or root["phase_id"] is not None
            or data["origin_request_id"] != root["request_id"] or data["operation"] != operation
            or data["epoch"] != request["epoch"] or data["actor_id"] != actor_id
            or root["mission_id"] != request["mission_id"]):
        raise ContractError("Prompt receipt contradicts its immutable root, actor or epoch")
    if request["kind"] == "observe":
        if (lifecycle and data["stage"] == "complete" or not lifecycle and data["stage"] != "complete"):
            raise ContractError("Observe may only close an ordinary prompt")
    elif request["kind"] not in (("skill", "lifecycle") if lifecycle else ("skill",)) or (
            request["request_id"] != root["request_id"] and request["phase_id"] != root["request_id"]):
        raise ContractError("Prompt result lost its root/child request correlation")
    return data


def validate_lifecycle_transition(value: dict) -> dict:
    """Closed observed-effect record; the ledger authenticates its input chain."""
    if type(value) is not dict:
        raise ContractError("Lifecycle transition requires a typed object")
    data = _decode(value, _TRANSITION)
    if (data["origin_epoch"] > data["reconciled_epoch"]
            or data["before_source_id"] == data["after_source_id"]
            or data["before_takeover_generation"] != data["after_takeover_generation"]):
        raise ContractError("Lifecycle transition cannot reverse epochs, reuse its source or absorb takeover")
    return data


def validate_normal_adoption(value: dict) -> dict:
    """Identity/chronology audit data, never a live admission or map."""
    if type(value) is not dict:
        raise ContractError("Normal-session adoption requires a typed object")
    data = _decode(value, _ADOPTION)
    if data["world_claim_id"] == data["character_claim_id"]:
        raise ContractError("World and character identity require distinct claims")
    return data


def validate_saved_checkpoint(value: dict) -> dict:
    """Exact observed save endpoints; no save-file inspection or input authority."""
    if type(value) is not dict:
        raise ContractError("Saved checkpoint requires a typed object")
    data = _decode(value, _SAVED_CHECKPOINT)
    if data["normal_endpoint_source_id"] == data["menu_source_id"]:
        raise ContractError("A save checkpoint needs distinct normal and menu endpoints")
    return data


def validate_normal_finish(value: dict) -> dict:
    """Historical cleanup and player-reported objective outcome, not acceptance."""
    if type(value) is not dict:
        raise ContractError("Normal finish requires a typed object")
    data = _decode(value, _NORMAL_FINISH)
    if (data["disposition"] == "completed") != (data["completed_work_event_id"] is not None):
        raise ContractError("Player-reported completion requires its exact objective Work event")
    return data


def validate_normal_exit(value: dict) -> dict:
    """Process/effect audit data, distinct from a positive input acknowledgment."""
    if type(value) is not dict:
        raise ContractError("Normal exit must be a typed nested object")
    data = _decode(value, _SAVED_NORMAL_EXIT if value.get("no_save_required") is False else _NORMAL_EXIT)
    retirement = data["retirement"]
    if (type(data["returncode"]) is not int or type(retirement["returncode"]) is not int
            or retirement["launch_id"] != data["launch_id"]
            or retirement["exit_request_id"] != data["origin_request_id"]
            or retirement["native_request_id"] != (data["native_request_id"] if retirement["retired_pending"] else None)):
        raise ContractError("Exit retirement lost its exact launch/root/native correlation")
    return data


@dataclass(frozen=True)
class SourceBinding:
    """Runtime-recorded observation context; serialized audit data is not authority."""
    source_id: str
    mission_id: str
    epoch: int
    actor_id: str
    controller_boot_id: str
    pause_generation: int
    takeover_generation: int
    store_generation: int

    def __post_init__(self):
        validate_json(json_object(asdict(self)), _SOURCE_BINDING)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> SourceBinding:
        return cls(**_decode(value, _SOURCE_BINDING))


@dataclass(frozen=True)
class SourceRevalidation:
    """One explicit refresh, preserving original model evidence and execution scope.

    Consumers verify actual retained bytes/native state. Runtime additionally
    checks its live opaque lease and actor context; parsing restores none of them.
    """
    original: SourceBinding
    current: SourceBinding
    rule: str

    def __post_init__(self):
        if type(self.original) is not SourceBinding or type(self.current) is not SourceBinding:
            raise ContractError("Revalidation requires immutable typed source bindings")
        validate_json(self.to_dict(), _REVALIDATION)
        if self.original.source_id == self.current.source_id:
            raise ContractError("A refresh must identify a distinct current source")
        unchanged = ("mission_id", "epoch", "actor_id", "controller_boot_id", "pause_generation", "takeover_generation")
        if any(getattr(self.original, key) != getattr(self.current, key) for key in unchanged):
            raise ContractError("Revalidation cannot cross actor/epoch/controller/Pause/takeover")
        if self.current.store_generation != self.original.store_generation + 1:
            raise ContractError("Revalidation permits exactly one deliberate source refresh")

    def to_dict(self) -> dict:
        return {"schema": VERSION, "record_type": "SourceRevalidation", "original": self.original.to_dict(),
                "current": self.current.to_dict(), "rule": self.rule, "grants_authority": False}

    @classmethod
    def from_dict(cls, value: dict) -> SourceRevalidation:
        data = _decode(value, _REVALIDATION)
        return cls(SourceBinding.from_dict(data["original"]), SourceBinding.from_dict(data["current"]), data["rule"])


@dataclass(frozen=True)
class MissionLimits:
    inputs: int = 1500
    wall_seconds: float = 7200.0
    game_seconds: int = 43_200
    frames: int = 4096
    frame_bytes: int = 1_073_741_824
    requests: int = 4096
    primitive_mappings: int = 8192

    def __post_init__(self):
        validate_json(json_object(asdict(self)), _LIMITS)
        if self.wall_seconds <= 0 or self.primitive_mappings < self.inputs:
            raise ContractError("Positive wall time and one mapping per possible input are required")


@dataclass(frozen=True)
class CleanupReserve:
    inputs: int = 100
    wall_seconds: float = 900.0
    frames: int = 256
    frame_bytes: int = 134_217_728

    def __post_init__(self):
        validate_json(json_object(asdict(self)), _RESERVE)
        if self.wall_seconds <= 0:
            raise ContractError("Cleanup wall reserve must be positive")


@dataclass(frozen=True)
class Scenario:
    mode: str
    world: str
    character: str

    def __post_init__(self):
        validate_json(json_object(asdict(self)), _SCENARIO)


@dataclass(frozen=True)
class Configuration:
    source_commit: str
    native_sha256: str
    skills: str
    lessons: str
    model: str
    effort: str

    def __post_init__(self):
        validate_json(json_object(asdict(self)), _CONFIGURATION)


@dataclass(frozen=True)
class MissionAdmission:
    mission_id: str
    objective: str
    player_id: str
    scenario: Scenario
    limits: MissionLimits
    cleanup_reserve: CleanupReserve
    allowed_skills: tuple[str, ...]
    allowed_lifecycle: tuple[str, ...]
    update_policy: str
    configuration: Configuration

    def __post_init__(self):
        for value, cls in ((self.scenario, Scenario), (self.limits, MissionLimits),
                           (self.cleanup_reserve, CleanupReserve), (self.configuration, Configuration)):
            if type(value) is not cls:
                raise ContractError("Admission requires typed immutable nested values")
        if type(self.allowed_skills) is not tuple or type(self.allowed_lifecycle) is not tuple:
            raise ContractError("Capabilities must be immutable tuples")
        validate_json(self.to_dict(), _ADMISSION)
        for field in ("inputs", "wall_seconds", "frames", "frame_bytes"):
            if getattr(self.cleanup_reserve, field) >= getattr(self.limits, field):
                raise ContractError("Cleanup reserve must leave a positive ordinary-work budget")

    def to_dict(self) -> dict:
        value = asdict(self)
        value["allowed_skills"] = list(self.allowed_skills)
        value["allowed_lifecycle"] = list(self.allowed_lifecycle)
        return {"schema": VERSION, "record_type": "MissionAdmission", **value}

    @classmethod
    def from_dict(cls, value: dict | str | bytes) -> MissionAdmission:
        data = _decode(value, _ADMISSION)
        data.pop("schema"); data.pop("record_type")
        for field, constructor in (("scenario", Scenario), ("limits", MissionLimits),
                                   ("cleanup_reserve", CleanupReserve), ("configuration", Configuration)):
            data[field] = constructor(**data[field])
        data["allowed_skills"] = tuple(data["allowed_skills"])
        data["allowed_lifecycle"] = tuple(data["allowed_lifecycle"])
        return cls(**data)


def visible_ui_schema() -> dict:
    """One closed shared shape; no hidden-item IDs or unseen row enumeration."""
    return json_object(_VISIBLE_UI)


def validate_visible_ui(value: dict | None) -> dict | None:
    if value is None:
        return None
    data = _decode(value, _VISIBLE_UI)
    ids = [row["id"] for row in data["rows"]]
    if len(ids) != len(set(ids)) or (data["selected"] is not None and data["selected"] not in ids):
        raise ContractError("Visible selection requires a distinct currently rendered row")
    return data


def validate_memory_entry(value: dict | str | bytes, entry_type: str, *, player=False) -> dict:
    if not isinstance(entry_type, str) or entry_type not in _ENTRIES:
        raise ContractError("Unknown memory entry type")
    result = _decode(value, _ENTRIES[entry_type])
    if entry_type == "claim":
        if player and result["kind"] != "interpretation":
            raise ContractError("A player cannot assert a native fact")
        content = result["value"]
        if content["quantity"] is not None and content["state"] is not None:
            raise ContractError("A value is a quantity or state, never both")
        if content["quantity"] is None and content["state"] is None and result["status"] not in ("unknown", "disputed", "retired"):
            raise ContractError("An unsupported value must remain unknown/disputed/retired")
        if result["key"]["property"] == "identity":
            key = result["key"]
            coverage = {"world": "visible-world-menu", "character": "visible-character-screen"}
            if (result["kind"] != "interpretation" or key["subject"] not in coverage
                    or key["unit"] != "name" or key["coverage_id"] != coverage[key["subject"]]
                    or content["quantity"] is not None):
                raise ContractError("Identity is a fallible visible world/menu or character/screen name")
        for support in result["supports"]:
            if not support["sources"] and not support["claims"]:
                raise ContractError("Empty support group cannot establish a claim")
            if result["id"] in support["claims"]:
                raise ContractError("A claim cannot support itself")
            if not set(support["sources"]) <= set(result["sources"]):
                raise ContractError("Support must reference declared sources")
    elif entry_type == "work" and result["predecessor_work_id"] == result["id"]:
        raise ContractError("Work cannot precede itself")
    return result


def _perception_schema(data: dict) -> dict:
    """Discriminate the closed union as for skill goals, using existing validation."""
    view = data.get("perception")
    if view is None:
        return {"type": "null"}
    if type(view) is not dict or not isinstance(view.get("kind"), str) or view["kind"] not in _VIEWS:
        raise ContractError("Unknown visible-control interpretation")
    return _VIEWS[view["kind"]]


def _request_schema(kind: str, data: dict) -> dict:
    props = {"schema": {"const": VERSION}, "kind": {"const": kind}}
    if kind in ("status", "result", "context"):
        props["mission_id"] = _ID
        if kind == "result": props["operation_id"] = _ID
        if kind == "context": props.update(query=_text(1024), scope=_SCOPE,
                                            max_bytes=_integer(MAX_CONTEXT_BYTES, 512))
    elif kind == "start":
        props.update(request_id=_ID, admission=_ADMISSION)
    else:
        props.update(request_id=_ID, mission_id=_ID, epoch=_integer())
        if kind in ("observe",): pass
        elif kind == "reconcile":
            props.update(unresolved_request_id=_ID, evidence_id=_ID, reason=_text(1024))
        elif kind in ("remember", "correct"):
            entry_type = data.get("entry_type")
            if not isinstance(entry_type, str) or entry_type not in _ENTRIES: raise ContractError("Unknown memory entry type")
            props.update(entry_type={"const": entry_type}, entry=_ENTRIES[entry_type])
            if kind == "correct": props.update(retired_ids={**_IDS, "minItems": 1}, reason=_text(1024))
        elif kind == "skill":
            skill_kind = data.get("skill_kind")
            if not isinstance(skill_kind, str) or skill_kind not in _GOALS: raise ContractError("Unknown skill kind")
            props.update(skill_kind={"const": skill_kind}, goal=_GOALS[skill_kind], sources=_IDS,
                         expected_session=_ID, expected_revision=_integer(), expected_boundary_id=_ID,
                         limits=_SKILL_LIMITS, work_id=_nullable(_ID), phase_id=_nullable(_ID),
                         perception=_perception_schema(data))
        elif kind == "handoff":
            props.update(checkpoint_ids={**_array(_ID, 32), "uniqueItems": True}, successor_role=_ID)
        elif kind == "claim":
            props.update(handoff_id=_ID, player_id=_ID, pause_generation=_integer(),
                         takeover_generation=_integer(), expected_session=_ID, expected_revision=_integer(),
                         expected_boundary_id=_ID, expected_pause_origin=_enum(*PAUSE_ORIGINS))
        elif kind == "lifecycle":
            props.update(operation=_enum(*LIFECYCLE), world=_text(80), character=_text(80),
                         sources=_IDS, expected_session=_nullable(_ID),
                         expected_revision=_nullable(_integer()), expected_boundary_id=_nullable(_ID),
                         limits=_LIFECYCLE_LIMITS, work_id=_nullable(_ID), phase_id=_nullable(_ID),
                         identity_claim_ids={**_array(_ID, 4), "uniqueItems": True})
        elif kind == "stop":
            props.update(reason=_text(1024))
        else: raise ContractError("Unknown mission operation")
    return _object(props)


def validate_request(value: dict | str | bytes) -> dict:
    """Validate and copy one closed operation. No controller/process reference."""
    if isinstance(value, (str, bytes)) and len(value.encode() if isinstance(value, str) else value) > MAX_REQUEST_BYTES:
        raise ContractError("Mission request exceeds its byte limit")
    result = json_object(value)
    kind = result.get("kind")
    if not isinstance(kind, str): raise ContractError("Mission operation requires kind")
    result = _decode(result, _request_schema(kind, result))
    if kind == "start":
        MissionAdmission.from_dict(result["admission"])
    elif kind == "context":
        if result["scope"]["mission_id"] != result["mission_id"]:
            raise ContractError("Context scope differs from mission")
    elif kind in ("remember", "correct"):
        entry = validate_memory_entry(result["entry"], result["entry_type"], player=True)
        if entry["scope"]["mission_id"] != result["mission_id"]:
            raise ContractError("Memory scope differs from mission")
        if kind == "correct":
            if result["entry_type"] != "claim" or entry["id"] in result["retired_ids"]:
                raise ContractError("A correction must introduce a new claim identity")
    elif kind == "skill":
        if not result["sources"]: raise ContractError("A skill requires informing evidence")
        if result["limits"]["wall_seconds"] <= 0: raise ContractError("Skill deadline must be positive")
        if result["skill_kind"] == "navigate":
            scope = result["goal"]["scope"]
            if scope["mission_id"] != result["mission_id"] or scope["session"] != result["expected_session"]:
                raise ContractError("Navigation scope differs from informing evidence")
        if result["skill_kind"] == "activity" and result["goal"]["game_seconds"] > result["limits"]["game_seconds"]:
            raise ContractError("Activity target exceeds admitted skill time")
        if result["skill_kind"] == "item":
            expected = {"pickup": "acquired", "consume": "consumed", "drop": "dropped", "store": "stored"}
            if result["goal"]["outcome"] != expected[result["goal"]["purpose"]]:
                raise ContractError("Item purpose and outcome disagree")
        view = result["perception"]
        dismissing = result["skill_kind"] == "menu" and result["goal"]["outcome"] == "dismissed"
        if dismissing and (view is None or view["kind"] != "dismissal" or result["goal"]["label"] != "Cancel"):
            raise ContractError("Dismissal requires exact Cancel and its source-bound dismissal question")
        if view is not None and view["kind"] == "dismissal" and not dismissing:
            raise ContractError("Dismissal interpretation requires the exact menu dismissal goal")
        if view is not None:
            if view["source_id"] not in result["sources"]:
                raise ContractError("Interpretation must name an immutable informing source")
            if result["skill_kind"] not in ("menu", "edit"):
                raise ContractError("Only menu/edit controls accept visible-control interpretations")
            if view["kind"] == "menu":
                labels = [row["label"] for row in view["rows"]]
                if len(set(labels)) != len(labels) or (view["selected"] is not None and view["selected"] >= len(labels)):
                    raise ContractError("Menu view requires distinct visible labels and represented selection")
            if result["skill_kind"] == "menu":
                if view["kind"] == "editor":
                    raise ContractError("Menu cannot borrow an editor interpretation")
                choices = {"direction": ("North", "South", "East", "West", "Here"),
                           "confirmation": ("Yes", "No")}
                if view["kind"] in choices and (result["goal"]["label"] not in choices[view["kind"]]
                        or result["goal"]["outcome"] != "activated"):
                    raise ContractError("Prompt requires one typed direction/confirmation activation")
        if result["skill_kind"] == "edit":
            if view is None or view["kind"] != "editor" or view["purpose"] != result["goal"]["purpose"]:
                raise ContractError("Edit requires its same-purpose visible editor interpretation")
            # Schema's $ may match before a final newline; no control character
            # belongs in the literal typing batch.
            if re.fullmatch(r"[A-Za-z0-9 _-]+", result["goal"]["text"]) is None:
                raise ContractError("Editor text requires only the supported literal ASCII characters")
            if result["goal"]["purpose"] == "quantity" and not result["goal"]["text"].isdigit():
                raise ContractError("Quantity requires ASCII digits")
        if result["phase_id"] == result["request_id"]:
            raise ContractError("A phase child cannot parent itself")
    elif kind == "lifecycle":
        binding = [result[k] for k in ("expected_session", "expected_revision", "expected_boundary_id")]
        if result["operation"] == "launch" and result["phase_id"] is None:
            if any(v is not None for v in binding): raise ContractError("Launch cannot borrow old native authority")
        elif any(v is None for v in binding):
            raise ContractError("Lifecycle requires a complete informing boundary")
        if result["limits"]["wall_seconds"] <= 0: raise ContractError("Lifecycle deadline must be positive")
        if result["phase_id"] == result["request_id"]:
            raise ContractError("A phase child cannot parent itself")
    return result
