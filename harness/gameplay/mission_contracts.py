"""Strict mission/11 data. Parsing never grants a controller capability.

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
    json_object, validate_json, canonical,
)
from .native_input import direct_goal_schema, validate_input
from .procedures import procedure_schema, validate_procedure

VERSION = "mission/11"
MEMORY_VERSION = "campaign-memory/6"
IDENTITY_UNIT = "name"
IDENTITY_COVERAGE = {"world": "visible-world-menu", "character": "visible-character-screen"}
MAX_REQUEST_BYTES = 65_536
MAX_CONTEXT_BYTES = 32_768
MAX_HANDOFF_CONTEXT_BYTES = 131_072
MAX_HANDOFF_SOURCES = 128
# Explicit campaign retention ceilings; ordinary defaults remain smaller.
MAX_RETAINED_FRAMES = 8192
MAX_RETAINED_BYTES = 2 * 1024 * 1024 * 1024
# Leave room for the bounded mission wrapper and the future post-Pause source.
# The packet itself must fit the remaining 96KiB before authority is relinquished.
HANDOFF_CONTEXT_RESERVE = 32_768
SKILLS = ("navigate", "menu", "item", "activity", "inspect", "edit", "interact", "direct", "program")
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
    # Seven elapsed days is an objective, not a safe total cap for ending work.
    "game_seconds": _integer(691_200, 1), "frames": _integer(MAX_RETAINED_FRAMES, 1),
    "frame_bytes": _integer(MAX_RETAINED_BYTES, 1),
    "requests": _integer(4096, 1), "primitive_mappings": _integer(8192, 1),
})
_RESERVE = _object({"inputs": _integer(8192, 1), "wall_seconds": _number(86_400),
                    "frames": _integer(MAX_RETAINED_FRAMES, 1), "frame_bytes": _integer(MAX_RETAINED_BYTES, 1)})
_SCENARIO = _object({"mode": _enum("fresh", "load"), "world": _text(80),
                     "character": _text(80)})
_CONFIGURATION = _object({
    "source_commit": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
    "native_sha256": _SHA, "skills": _text(128), "lessons": _text(128),
    "model": _text(128), "effort": _text(64),
})
_PROCEDURE_REF = _object({"mission_id": _ID, "revision_id": _ID})
_QUALIFIED_SOURCE = _object({"mission_id": _ID, "source_id": _ID})
_PROCEDURE_USE = _object({**_PROCEDURE_REF["properties"], "use_id": _ID, "applicability": _text(1024)})
_LIBRARY_SOURCE = _object({"mission_id": _ID, "ledger_sha256": _SHA, "index_sha256": _SHA})
_REFLECTION_LIMITS = _object({
    "jobs": _integer(64, 1), "pending": _integer(2, 1),
    "requests_per_job": _integer(32, 1), "sources_per_job": _integer(8, 1),
    "context_bytes": _integer(65_536, 1024), "result_bytes": _integer(32_768, 512),
    "job_seconds": _number(180), "total_seconds": _number(3600),
})
_LEARNING = _object({
    "environment": procedure_schema()["properties"]["environment"],
    "library_sources": _array(_LIBRARY_SOURCE, 4),
    "reflector_id": _nullable(_ID), "reflection_limits": _REFLECTION_LIMITS,
})
_ADMISSION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "MissionAdmission"},
    "mission_id": _ID, "objective": _text(2000), "player_id": _ID,
    "scenario": _SCENARIO, "limits": _LIMITS, "cleanup_reserve": _RESERVE,
    "allowed_skills": {**_array(_enum(*SKILLS), len(SKILLS), 1), "uniqueItems": True},
    "allowed_lifecycle": {**_array(_enum(*LIFECYCLE), len(LIFECYCLE)), "uniqueItems": True},
    "update_policy": {"const": "facts-procedures-reflection/3"}, "configuration": _CONFIGURATION,
    "learning": _nullable(_LEARNING),
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
_INPUT_OBSERVATION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "InputObservation"},
    "original": _SOURCE_BINDING, "current": _SOURCE_BINDING,
    "grants_authority": {"const": False},
})
_SKILL_LIMITS = _object({"primitives": _integer(32, 1), "wall_seconds": _number(900),
                         "game_seconds": _integer(43_200, 1)})
_LIFECYCLE_LIMITS = _object({"primitives": _integer(256, 1), "wall_seconds": _number(1800),
                             "game_seconds": _integer(43_200, 1)})
_VIEW_BASE = {"source_id": _ID, "basis": {"const": "player_interpretation"}}
_ITEM_UNIT = _enum("items", "charges")
_VIEWS = {
    "item_selection": _object({**_VIEW_BASE, "kind": {"const": "item_selection"},
        "control": {"const": "vertical"}, "mode": _enum("single", "multi"),
        "rows": _array(_object({"label": _text(1024), "enabled": {"type": "boolean"},
            "available_quantity": _nullable(_integer(9999)), "quantity_unit": _ITEM_UNIT,
            "chosen_quantity": _nullable(_integer(9999))}), 32, 1),
        "selected": _nullable(_integer(31)), "selection_coverage": _enum("all_selected", "visible_only"),
        "selected_items": _array(_object({"label": _text(1024), "quantity": _integer(9999, 1),
                                          "quantity_unit": _ITEM_UNIT}), 32)}),
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
                       "quantity_unit": _ITEM_UNIT, "step": _enum("start", "select", "commit"),
                       "outcome": _enum("acquired", "consumed", "stored", "dropped")}),
    "activity": _object({"operation": _enum("wait", "rest", "craft", "direct"),
                           "target": _text(1024), "game_seconds": _integer(43_200, 1),
                           "interrupt_allowed": {"type": "boolean"},
                           "step": _enum("start", "poll", "interrupt", "answer_interrupt", "resume"),
                           "answer": _nullable(_enum("YES", "NO")), "interrupt_request_id": _nullable(_ID)}),
    "inspect": _object({"purpose": _enum("inventory", "consume", "needs", "look", "messages", "map", "character_identity")}),
    "edit": _object({"purpose": _enum(*EDITOR_PURPOSES),
        "text": {**_text(24), "pattern": r"^[A-Za-z0-9 _-]+$"}, "commit": {"type": "boolean"}}),
    "interact": _object({"action": _enum(*INTERACTIONS), "intent": _text(1024),
        "desired_outcome": _text(1024)}),
    "direct": direct_goal_schema(),
    "program": _object({"state": {"type": "object"}, "intent": _text(1024),
                         "expected": _text(1024), "interrupt_allowed": {"type": "boolean"}}),
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
_WORK_VIEW = _object({**_WORK["properties"],
    "record_type": {"const": "WorkView"},
    "sources": {**_array(_ID, MAX_HANDOFF_SOURCES), "uniqueItems": True},
})
_DECISION = _object({
    "schema": {"const": MEMORY_VERSION}, "record_type": {"const": "Decision"},
    "id": _ID, "packet_id": _ID, "scope": _SCOPE, "query": _text(1024), "memory_version": _integer(),
    "claim_ids": {**_array(_ID, 32), "uniqueItems": True},
    "work_ids": {**_array(_ID, 16), "uniqueItems": True},
    "source_ids": {**_array(_ID, MAX_HANDOFF_SOURCES), "uniqueItems": True},
    "procedure_refs": {**_array(_PROCEDURE_REF, 16), "uniqueItems": True},
    "procedure_sources": {**_array(_QUALIFIED_SOURCE, MAX_HANDOFF_SOURCES), "uniqueItems": True},
    "omitted": _integer(), "reason": _text(1024),
})
_ENTRIES = {"claim": _CLAIM, "work": _WORK, "decision": _DECISION, "procedure": procedure_schema()}
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
    "post_pause_source_id": _ID, "controller_boot_id": _ID,
    "operator_pause_generation": _integer(),
})
_HANDOFF = _object({
    **_HANDOFF_BINDING["properties"], "schema": {"const": VERSION},
    "record_type": {"const": "Handoff"}, "handoff_id": _ID, "mission_id": _ID,
    "original_player_id": _ID, "successor_role": _ID, "epoch": _integer(),
    "checkpoint_ids": {**_array(_ID, 32), "uniqueItems": True},
    "unfinished_work_ids": {**_array(_ID, 16), "uniqueItems": True},
    "grants_authority": {"const": False},
})
_CLAIMED_HANDOFF = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "ClaimedHandoff"},
    "handoff_id": _ID, "mission_id": _ID, "player_id": _ID, "actor_role": _ID,
    "epoch": _integer(), "grants_authority": {"const": False},
    "packet_ids": {**_array(_ID, 4, 1), "uniqueItems": True},
    "read_source_ids": {**_array(_ID, 128), "uniqueItems": True},
    "read_procedure_sources": {**_array(_QUALIFIED_SOURCE, MAX_HANDOFF_SOURCES), "uniqueItems": True},
})
_READMISSION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "Readmission"},
    "mode": {"const": "handoff"},
    "handoff_id": _ID, "claim_request_id": _ID, "player_id": _ID, "epoch": _integer(),
    "post_pause_source_id": _ID, "revalidated_source_id": _ID, "after_source_id": _ID,
    "logical_id": _ID, "grants_authority": {"const": False},
})
_RECOVERY_READMISSION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "Readmission"},
    "mode": {"const": "recovery"}, "reconciliation_request_id": _ID,
    "root_id": _ID, "player_id": _ID, "epoch": _integer(),
    "post_pause_source_id": _ID, "revalidated_source_id": _ID, "after_source_id": _ID,
    "logical_id": _ID, "grants_authority": {"const": False},
})
_DELIVERY_TERMINAL = _object({
    "id": _ID, "channel": _enum("ordinary", "control"),
    "status": _enum("ready", "rejected", "prompt_opened", "not_applicable", "answer_delivered"),
    "session": _ID, "revision": _integer(), "takeover_generation": _integer(),
    "boundary_id": _ID, "boundary_kind": _enum("normal_play", "activity_poll", "interrupt_confirmation", "menu", "debug_prompt", "unsupported"),
    "interrupt_request_id": _nullable(_ID), "control_generation": _integer(), "frame_ok": {"type": "boolean"},
})
_DELIVERY_RESOLUTION = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "DeliveryResolution"},
    **{key: _ID for key in ("reconciliation_request_id", "original_request_id", "root_id", "logical_id",
        "native_request_id", "actor_id", "controller_boot_id", "game_anchor_source_id", "before_source_id", "observed_source_id")},
    "origin_epoch": _integer(), "recovery_epoch": _integer(), "operator_pause_generation": _integer(),
    "takeover_generation": _integer(), "terminal_source_id": _nullable(_ID),
    "native_request_json": _text(4096), "collection_started_monotonic": _number(10**12),
    "collection_deadline_monotonic": _number(10**12), "collection_received_monotonic": _number(10**12),
    "retirement": _nullable({**_text(128), "pattern": r"^(control-)?cancelled-[A-Za-z0-9_-]+\.json$"}),
    "terminal": _nullable(_DELIVERY_TERMINAL), "grants_authority": {"const": False},
})
_PROMPT_RECEIPT = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "PhaseReceipt"},
    "origin_request_id": _ID, "phase_kind": {"const": "interact"}, "operation": _enum(*INTERACTIONS),
    "stage": _enum("awaiting_control", "awaiting_observation", "activity_poll", "complete", "unknown"),
    "epoch": _integer(), "actor_id": _ID, "controller_boot_id": _ID,
    "operator_pause_generation": _integer(), "takeover_generation": _integer(),
    "source_ids": {**_IDS, "minItems": 1}, "continuity": {"type": "null"},
    "grants_authority": {"const": False},
})
_SEMANTIC_PHASE_RECEIPT = _object({
    **_PROMPT_RECEIPT["properties"], "phase_kind": _enum("item", "activity", "inspect", "direct", "program"),
    "operation": _text(128),
    "stage": _enum("awaiting_control", "awaiting_observation", "activity_poll", "interrupt_confirmation", "awaiting_readmission", "complete", "unknown"),
})
_NAVIGATION_PHASE_RECEIPT = _object({
    **_PROMPT_RECEIPT["properties"], "phase_kind": {"const": "navigate"},
    "operation": {"const": "navigate"}, "stage": _enum("awaiting_control", "awaiting_observation", "complete", "unknown"),
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


def validate_readmission(value: dict) -> dict:
    data = json_object(value)
    return _decode(data, _RECOVERY_READMISSION if data.get("mode") == "recovery" else _READMISSION)


def validate_delivery_resolution(value: dict) -> dict:
    data = _decode(value, _DELIVERY_RESOLUTION, maximum=32_768)
    native = json_object(data["native_request_json"])
    if canonical(native) != data["native_request_json"] or len(data["native_request_json"].encode()) > 4096:
        raise ContractError("Delivery resolution requires bounded canonical native admission")
    start, end, received = (data[k] for k in ("collection_started_monotonic", "collection_deadline_monotonic", "collection_received_monotonic"))
    if not start <= received < end <= start + 0.25 or (data["retirement"] is None) == (data["terminal"] is None):
        raise ContractError("Delivery resolution lacks its exact bounded collection basis")
    if data["retirement"] is not None and data["terminal_source_id"] is not None:
        raise ContractError("Unclaimed retirement cannot have a terminal frame")
    return data


def effect_reconciliation(proof: dict, *, sources: tuple[str, ...], note: str) -> dict:
    """One current envelope for every independently established unknown effect."""
    if type(proof) is not dict: raise ContractError("Effect reconciliation requires its closed typed proof")
    return validate_effect_reconciliation(dict(schema=VERSION, record_type="EffectReconciliation",
        basis=proof.get("record_type"), sources=list(sources), note=note, proof=proof))


def validate_effect_reconciliation(value: dict | str) -> dict:
    data = json_object(value)
    schemas = {"DeliveryResolution": _DELIVERY_RESOLUTION, "LifecycleTransition": _TRANSITION,
               "OwnedNormalExit": _SAVED_NORMAL_EXIT if type(data.get("proof")) is dict and data["proof"].get("no_save_required") is False else _NORMAL_EXIT}
    basis = data.get("basis")
    if type(basis) is not str or basis not in schemas:
        raise ContractError("Unknown current effect proof basis")
    data = _decode(data, _object({"schema": {"const": VERSION}, "record_type": {"const": "EffectReconciliation"},
        "basis": {"const": basis}, "sources": {**_IDS, "minItems": 1}, "note": _text(1024), "proof": schemas[basis]}), maximum=32_768)
    validators = {"DeliveryResolution": validate_delivery_resolution, "LifecycleTransition": validate_lifecycle_transition,
                  "OwnedNormalExit": validate_normal_exit}
    validators[basis](data["proof"])
    return data


def validate_prompt_result(value: dict, *, request: dict, root: dict, actor_id: str) -> dict:
    """Closed ordinary/lifecycle audit data; never restore a live phase."""
    lifecycle = type(value) is dict and value.get("phase_kind") == "lifecycle"
    exit_schema = _SAVED_EXIT_PHASE if lifecycle and value.get("no_save_required") is False else _EXIT_PHASE_RECEIPT
    schema = ((exit_schema if value.get("operation") == "exit" else _NORMAL_LIFECYCLE_PHASE) if lifecycle else
              _PROMPT_RECEIPT if value.get("phase_kind") == "interact" else
              _NAVIGATION_PHASE_RECEIPT if value.get("phase_kind") == "navigate" else _SEMANTIC_PHASE_RECEIPT)
    data = _decode(value, schema)
    valid_root = (root["kind"] == "lifecycle" and root["operation"] in ("exit", "create", "save", "load") if lifecycle else
                  root["kind"] == "skill" and root["skill_kind"] == data["phase_kind"])
    operation = root.get("operation") if lifecycle else data["phase_kind"] if data["phase_kind"] in ("direct", "program", "navigate") else root.get("goal", {}).get(
        "action" if data["phase_kind"] == "interact" else "operation" if data["phase_kind"] == "activity" else "purpose")
    if (not valid_root or root["phase_id"] is not None
            or data["origin_request_id"] != root["request_id"] or data["operation"] != operation
            or data["epoch"] != request["epoch"] or data["actor_id"] != actor_id
            or root["mission_id"] != request["mission_id"]):
        raise ContractError("Prompt receipt contradicts its immutable root, actor or epoch")
    if request["kind"] == "observe":
        activity_observation = (not lifecycle and (
            data["phase_kind"] in ("activity", "item", "inspect", "interact", "direct", "program")
            and data["stage"] in ("activity_poll", "awaiting_control", "complete")
            or data["phase_kind"] in ("activity", "direct", "program")
            and data["stage"] in ("interrupt_confirmation", "awaiting_readmission")))
        if (lifecycle and data["stage"] == "complete"
                or not lifecycle and not activity_observation and data["stage"] != "complete"):
            raise ContractError("Observe requires ordinary completion or supported owned activity progress")
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


def _source_transition(original: SourceBinding, current: SourceBinding) -> None:
    if type(original) is not SourceBinding or type(current) is not SourceBinding:
        raise ContractError("Observation transition requires immutable typed source bindings")
    if original.source_id == current.source_id:
        raise ContractError("An observation transition must identify a distinct current source")
    unchanged = ("mission_id", "epoch", "actor_id", "controller_boot_id", "pause_generation", "takeover_generation")
    if any(getattr(original, key) != getattr(current, key) for key in unchanged):
        raise ContractError("Observation transition cannot cross actor/epoch/controller/Pause/takeover")
    if current.store_generation != original.store_generation + 1:
        raise ContractError("Observation transition permits exactly one deliberate source capture")


@dataclass(frozen=True)
class InputObservation:
    """Ordinary entry observation; changed evidence is not an equivalence claim.

    The explicit physical event remains the player's choice. Live receiver,
    integrity, custody and dispatch checks belong to the writer, not this record.
    """
    original: SourceBinding
    current: SourceBinding

    def __post_init__(self):
        _source_transition(self.original, self.current)
        validate_json(self.to_dict(), _INPUT_OBSERVATION)

    def to_dict(self) -> dict:
        return {"schema": VERSION, "record_type": "InputObservation", "original": self.original.to_dict(),
                "current": self.current.to_dict(), "grants_authority": False}

    @classmethod
    def from_dict(cls, value: dict) -> InputObservation:
        data = _decode(value, _INPUT_OBSERVATION)
        return cls(SourceBinding.from_dict(data["original"]), SourceBinding.from_dict(data["current"]))


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
        _source_transition(self.original, self.current)
        validate_json(self.to_dict(), _REVALIDATION)

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
class LibrarySource:
    mission_id: str
    ledger_sha256: str
    index_sha256: str

    def __post_init__(self):
        validate_json(json_object(asdict(self)), _LIBRARY_SOURCE)


@dataclass(frozen=True)
class ReflectionLimits:
    jobs: int = 64
    pending: int = 2
    requests_per_job: int = 32
    sources_per_job: int = 8
    context_bytes: int = 65_536
    result_bytes: int = 32_768
    job_seconds: float = 180
    total_seconds: float = 3600

    def __post_init__(self):
        validate_json(json_object(asdict(self)), _REFLECTION_LIMITS)
        if self.job_seconds <= 0 or self.total_seconds < self.job_seconds:
            raise ContractError("Reflection requires positive bounded job and aggregate time")


@dataclass(frozen=True)
class LearningPolicy:
    environment: dict
    library_sources: tuple[LibrarySource, ...] = ()
    reflector_id: str | None = None
    reflection_limits: ReflectionLimits = ReflectionLimits()

    def __post_init__(self):
        if (type(self.library_sources) is not tuple or any(type(value) is not LibrarySource for value in self.library_sources)
                or type(self.reflection_limits) is not ReflectionLimits):
            raise ContractError("Learning admission requires typed source pins and reflection limits")
        # Retain immutable environment fields as a tuple, not a caller-owned dict.
        environment = json_object(dict(self.environment))
        object.__setattr__(self, "environment", tuple(sorted(environment.items())))
        validate_json(self.to_dict(), _LEARNING)
        if len({value.mission_id for value in self.library_sources}) != len(self.library_sources):
            raise ContractError("Library mission pins must be distinct")

    def to_dict(self) -> dict:
        return {"environment": dict(self.environment), "library_sources": [asdict(value) for value in self.library_sources],
                "reflector_id": self.reflector_id, "reflection_limits": asdict(self.reflection_limits)}

    @classmethod
    def from_dict(cls, value: dict) -> LearningPolicy:
        data = _decode(value, _LEARNING)
        return cls(data["environment"], tuple(LibrarySource(**source) for source in data["library_sources"]),
                   data["reflector_id"], ReflectionLimits(**data["reflection_limits"]))


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
    learning: LearningPolicy | None = None

    def __post_init__(self):
        for value, cls in ((self.scenario, Scenario), (self.limits, MissionLimits),
                           (self.cleanup_reserve, CleanupReserve), (self.configuration, Configuration)):
            if type(value) is not cls:
                raise ContractError("Admission requires typed immutable nested values")
        if type(self.allowed_skills) is not tuple or type(self.allowed_lifecycle) is not tuple:
            raise ContractError("Capabilities must be immutable tuples")
        if self.learning is not None and type(self.learning) is not LearningPolicy:
            raise ContractError("Learning requires its frozen typed admission")
        if self.learning is not None and any(source.mission_id == self.mission_id for source in self.learning.library_sources):
            raise ContractError("A live mission cannot be its own historical library")
        validate_json(self.to_dict(), _ADMISSION)
        for field in ("inputs", "wall_seconds", "frames", "frame_bytes"):
            if getattr(self.cleanup_reserve, field) >= getattr(self.limits, field):
                raise ContractError("Cleanup reserve must leave a positive ordinary-work budget")

    def to_dict(self) -> dict:
        value = asdict(self)
        value["allowed_skills"] = list(self.allowed_skills)
        value["allowed_lifecycle"] = list(self.allowed_lifecycle)
        value["learning"] = None if self.learning is None else self.learning.to_dict()
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
        data["learning"] = None if data["learning"] is None else LearningPolicy.from_dict(data["learning"])
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


def validate_work_view(value: dict | str | bytes) -> dict:
    """A coherent projection may retain more premises than one raw assertion."""
    return _decode(value, _WORK_VIEW, maximum=MAX_HANDOFF_CONTEXT_BYTES)


def validate_memory_entry(value: dict | str | bytes, entry_type: str, *, player=False) -> dict:
    if not isinstance(entry_type, str) or entry_type not in _ENTRIES:
        raise ContractError("Unknown memory entry type")
    result = (validate_procedure(value) if entry_type == "procedure" else _decode(value, _ENTRIES[entry_type]))
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
            if (result["kind"] != "interpretation" or key["subject"] not in IDENTITY_COVERAGE
                    or key["unit"] != IDENTITY_UNIT or key["coverage_id"] != IDENTITY_COVERAGE[key["subject"]]
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
            max_bytes=_integer(MAX_HANDOFF_CONTEXT_BYTES if data.get("handoff") is not None else MAX_CONTEXT_BYTES, 512), handoff=_nullable(_object({
                "handoff_id": _ID, "prospective_player_id": _ID, "actor_role": _ID})))
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
                         procedure=_nullable(_PROCEDURE_USE),
                         perception=_perception_schema(data))
        elif kind == "handoff":
            props.update(checkpoint_ids={**_array(_ID, 32), "uniqueItems": True}, successor_role=_ID,
                         unfinished_work_ids={**_array(_ID, 16), "uniqueItems": True})
        elif kind == "claim":
            props.update(handoff_id=_ID, player_id=_ID, pause_generation=_integer(),
                         takeover_generation=_integer(), expected_session=_ID, expected_revision=_integer(),
                         expected_boundary_id=_ID, expected_pause_origin=_enum(*PAUSE_ORIGINS), actor_role=_ID,
                         packet_ids={**_array(_ID, 4, 1), "uniqueItems": True},
                         read_source_ids={**_array(_ID, 128), "uniqueItems": True})
            props["read_procedure_sources"] = {**_array(_QUALIFIED_SOURCE, MAX_HANDOFF_SOURCES), "uniqueItems": True}
        elif kind == "readmit":
            mode = data.get("mode")
            if mode not in ("handoff", "recovery"): raise ContractError("Readmission requires an explicit current mode")
            props.update(mode={"const": mode}, sources={**_IDS, "minItems": 1},
                         expected_session=_ID, expected_revision=_integer(), expected_boundary_id=_ID,
                         limits=_object({**_SKILL_LIMITS["properties"], "primitives": {"const": 1}}))
            if mode == "handoff": props.update(handoff_id=_ID, claim_request_id=_ID)
            else: props.update(reconciliation_request_id=_ID, phase_id=_ID, work_id=_nullable(_ID))
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


def request_schema(kind: str, **selectors: Any) -> dict:
    """Copy the receiver's current shape for a selected tagged operation.

    Tool adapters may remove generated headers from this description, but must
    still validate their completed record through validate_request. This is a
    schema description, never evidence, admission or a second validator.
    """
    return json_object(_request_schema(kind, selectors))


def perception_schema() -> dict:
    """The current closed interpretation union, for structured client tools."""
    return json_object({"anyOf": [{"type": "null"}, *_VIEWS.values()]})


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
        if (entry["mission_id"] if result["entry_type"] == "procedure" else entry["scope"]["mission_id"]) != result["mission_id"]:
            raise ContractError("Memory scope differs from mission")
        if kind == "correct":
            if result["entry_type"] != "claim" or entry["id"] in result["retired_ids"]:
                raise ContractError("A correction must introduce a new claim identity")
    elif kind == "readmit":
        if result["limits"]["wall_seconds"] <= 0:
            raise ContractError("Readmission deadline must be positive")
    elif kind == "skill":
        if not result["sources"]: raise ContractError("A skill requires informing evidence")
        if result["limits"]["wall_seconds"] <= 0: raise ContractError("Skill deadline must be positive")
        if result["phase_id"] is not None and result["procedure"] is not None:
            raise ContractError("A child inherits its root procedure use; it cannot replace that selection")
        if result["skill_kind"] == "direct":
            validate_input(result["goal"]["input"], text_limit=24)
        if result["skill_kind"] == "program":
            if result["phase_id"] is not None or result["procedure"] is None:
                raise ContractError("A program invocation requires a selected procedure and its own root")
            if len(canonical(result["goal"]["state"]).encode()) > 16_384:
                raise ContractError("Program continuation exceeds 16 KiB")
        if (result["skill_kind"] == "activity" and result["goal"]["operation"] == "direct"
                and result["goal"]["step"] == "start"):
            raise ContractError("Direct activity observation requires its actual existing root")
        if result["skill_kind"] == "navigate":
            scope = result["goal"]["scope"]
            if scope["mission_id"] != result["mission_id"] or scope["session"] != result["expected_session"]:
                raise ContractError("Navigation scope differs from informing evidence")
        if result["skill_kind"] == "activity" and result["goal"]["game_seconds"] > result["limits"]["game_seconds"]:
            raise ContractError("Activity target exceeds admitted skill time")
        if result["skill_kind"] in ("item", "activity"):
            step = result["goal"]["step"]
            if (step == "start") != (result["phase_id"] is None):
                raise ContractError("Semantic start requires a root; later steps require its exact phase")
        if result["skill_kind"] == "activity":
            answer = result["goal"]["step"] == "answer_interrupt"
            if (answer != (result["goal"]["answer"] is not None)
                    or answer != (result["goal"]["interrupt_request_id"] is not None)):
                raise ContractError("Only explicit interrupt answers carry a choice and exact prompt owner")
        if result["skill_kind"] == "item":
            expected = {"pickup": "acquired", "consume": "consumed", "drop": "dropped", "store": "stored"}
            if result["goal"]["outcome"] != expected[result["goal"]["purpose"]]:
                raise ContractError("Item purpose and outcome disagree")
        view = result["perception"]
        if result["skill_kind"] == "item" and result["goal"]["step"] != "start" and (
                view is None or view["kind"] != "item_selection"):
            raise ContractError("Item selection/commit requires its exact visible selector interpretation")
        dismissing = result["skill_kind"] == "menu" and result["goal"]["outcome"] == "dismissed"
        if dismissing and (view is None or view["kind"] != "dismissal" or result["goal"]["label"] != "Cancel"):
            raise ContractError("Dismissal requires exact Cancel and its source-bound dismissal question")
        if view is not None and view["kind"] == "dismissal" and not dismissing:
            raise ContractError("Dismissal interpretation requires the exact menu dismissal goal")
        if view is not None:
            if view["source_id"] not in result["sources"]:
                raise ContractError("Interpretation must name an immutable informing source")
            if result["skill_kind"] not in ("menu", "edit", "item"):
                raise ContractError("Only menu/edit/item controls accept visible-control interpretations")
            if view["kind"] in ("menu", "item_selection"):
                labels = [row["label"] for row in view["rows"]]
                if len(set(labels)) != len(labels) or (view["selected"] is not None and view["selected"] >= len(labels)):
                    raise ContractError("Menu view requires distinct visible labels and represented selection")
            if result["skill_kind"] == "item" and (view["kind"] != "item_selection" or result["goal"]["step"] == "start"):
                raise ContractError("Item controls require their own selector interpretation, not a start interpretation")
            if result["skill_kind"] == "menu":
                if view["kind"] not in ("menu", "direction", "confirmation", "dismissal"):
                    raise ContractError("Menu cannot borrow another control interpretation")
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


def validate_submission(value: dict | str | bytes) -> dict:
    """Validate new intent before admission, without rewriting recorded failures.

    validate_request also reads immutable rejected request evidence. Submission
    checks cannot make those historical rows unreadable or grant live authority.
    """
    result = validate_request(value)
    if (result["kind"] == "lifecycle" and result["operation"] in ("create", "save", "load")
            and result["phase_id"] is None
            and (result["work_id"] is not None or result["identity_claim_ids"])):
        raise ContractError("Lifecycle root cannot import Work or old identity authority")
    return result
