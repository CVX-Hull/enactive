"""Shared campaign-memory data; no mission lifecycle or game identity policy.

The current serialized order has two optional counters (revision and turn).
They establish only a partial order; neither is interpreted as elapsed seconds.
"""
from __future__ import annotations
from .contracts import ContractError, _array, _enum, _integer, _nullable, _object, _text, json_object, canonical, validate_json
from .procedures import procedure_schema, validate_procedure

class MemoryRequestRefusal(ContractError):
    """A positively identified validation failure of a new memory candidate.

    This says nothing about retained evidence, storage health or input authority.
    """


MEMORY_VERSION = "campaign-memory/6"
MAX_CONTEXT_BYTES = 32_768
MAX_HANDOFF_CONTEXT_BYTES = 131_072
MAX_HANDOFF_SOURCES = 128
MAX_MEMORY_BYTES = 65_536
_ID = {**_text(128), "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]*$"}
_IDS = {**_array(_ID, 8), "uniqueItems": True}
_TIME = _integer(2**63 - 1)
_TURN = _integer(2**31 - 1, -(2**31))
_SCOPE = _object({"mission_id": _ID, "session": _ID, "coordinate_epoch": _integer()})
_PROCEDURE_REF = _object({"mission_id": _ID, "revision_id": _ID})
_QUALIFIED_SOURCE = _object({"mission_id": _ID, "source_id": _ID})

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

def _decode(value: dict | str | bytes, schema: dict, *, maximum=MAX_MEMORY_BYTES) -> dict:
    if isinstance(value, (str, bytes)) and len(value.encode() if isinstance(value, str) else value) > maximum:
        raise ContractError("Memory record exceeds its byte limit")
    result = json_object(value)
    if len(canonical(result).encode()) > maximum:
        raise ContractError("Memory record exceeds its byte limit")
    validate_json(result, schema)
    return result


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


def validate_scope(value: dict, *, mission_id: str) -> dict:
    scope = _decode(value, _SCOPE)
    if scope["mission_id"] != mission_id:
        raise ContractError("Context scope differs from mission")
    return scope


def validate_context_query(scope: dict, query: str, max_bytes: int) -> None:
    _decode({"scope": scope, "query": query, "max_bytes": max_bytes},
        _object({"scope": _SCOPE, "query": _text(1024), "max_bytes": _integer(MAX_CONTEXT_BYTES, 512)}))
