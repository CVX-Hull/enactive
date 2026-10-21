"""Bounded advisory procedure records and pure, linear-family projection.

Shape and ancestry do not establish semantic truth, available episode sources or
input authority. Callers own source validation and environment-pin matching.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .contracts import (
    ContractError, _array, _enum, _integer, _nullable, _object, _text,
    json_object, validate_json,
)
from .contracts import canonical

VERSION = "procedure/1"
MAX_PROCEDURE_BYTES = 32_768
MAX_PROCEDURE_RECORDS = 256

# The negative character check also excludes a terminal newline, which Python's
# JSON Schema regex engine otherwise allows at the dollar anchor.
_ID = {**_text(128), "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
       "not": {"pattern": r"[^A-Za-z0-9_-]"}}
_TEXT = _text(1024)
_PARENT = _object({"mission_id": _ID, "revision_id": _ID})
_EPISODE = _object({
    "mission_id": _ID,
    "request_ids": {**_array(_ID, 16, 1), "uniqueItems": True},
    "source_ids": {**_array(_ID, 8, 1), "uniqueItems": True},
    "interpretation": _TEXT,
})
_SCHEMA = _object({
    "schema": {"const": VERSION}, "record_type": {"const": "Procedure"},
    "id": _ID, "mission_id": _ID, "procedure_id": _ID,
    "revision": _integer(1024, 1), "parent": _nullable(_PARENT),
    "goal": _TEXT,
    "parameters": _array(_object({"name": _ID, "description": _TEXT}), 8),
    "applicability": _array(_TEXT, 8, 1), "invalidators": _array(_TEXT, 8),
    "steps": _array(_object({"intent": _TEXT, "expected": _TEXT,
                              "on_unexpected": _TEXT}), 16, 1),
    "progress": _array(_TEXT, 8, 1), "stop_conditions": _array(_TEXT, 8, 1),
    "limits": _array(_TEXT, 8),
    "environment": _object({
        "engine_commit": {"type": "string", "minLength": 40, "maxLength": 40,
                          "pattern": "^[a-f0-9]{40}$"},
        "native_protocol": {"type": "integer", "const": 5},
        "mission_schema": {"const": "mission/9"}, "configuration": _TEXT,
    }),
    "support": _array(_EPISODE, 8, 1), "counterexamples": _array(_EPISODE, 8),
    "status": _enum("candidate", "active", "disputed", "retired"), "reason": _TEXT,
})


def procedure_schema() -> dict[str, Any]:
    """Return a defensive copy of the closed procedure/1 record schema."""
    return json_object(_SCHEMA)


def validate_procedure(value: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Validate shape and byte bounds, returning an independent decoded copy."""
    result = json_object(value)
    validate_json(result, _SCHEMA)
    try:
        size = len(canonical(result).encode("utf-8"))
    except UnicodeError as exc:
        raise ContractError("Procedure requires valid UTF-8 canonical JSON") from exc
    if size > MAX_PROCEDURE_BYTES:
        raise ContractError("Procedure exceeds 32 KiB canonical JSON")
    names = [parameter["name"] for parameter in result["parameters"]]
    if len(names) != len(set(names)):
        raise ContractError("Procedure parameter names must be unique")
    return result


def project_procedures(
    records: Sequence[dict[str, Any] | str | bytes],
) -> dict[str, dict[str, Any]]:
    """Resolve complete linear ancestry, independent of input/import order.

    Qualified immutable copies dedupe. Every family needs one root, complete
    exact parent closure and consecutive revisions; incomparable heads refuse.
    All input records count against the bound, including repeated copies.
    """
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        raise ContractError("Procedure projection requires a bounded sequence")
    if len(records) > MAX_PROCEDURE_RECORDS:
        raise ContractError("Procedure projection exceeds 256 records")

    revisions: dict[tuple[str, str], dict[str, Any]] = {}
    for value in records:
        record = validate_procedure(value)
        identity = (record["mission_id"], record["id"])
        if identity in revisions and revisions[identity] != record:
            raise ContractError("Conflicting copies of an immutable procedure revision")
        revisions[identity] = record

    roots: dict[str, tuple[str, str]] = {}
    children: dict[tuple[str, str], tuple[str, str]] = {}
    for identity, record in revisions.items():
        family = record["procedure_id"]
        parent = record["parent"]
        if parent is None:
            if record["revision"] != 1 or family in roots:
                raise ContractError("Procedure family requires exactly one revision-1 root")
            roots[family] = identity
            continue
        parent_id = (parent["mission_id"], parent["revision_id"])
        predecessor = revisions.get(parent_id)
        if predecessor is None:
            raise ContractError("Procedure parent is missing from the admitted closure")
        if predecessor["procedure_id"] != family:
            raise ContractError("Procedure parent belongs to another family")
        if record["revision"] != predecessor["revision"] + 1:
            raise ContractError("Procedure revision must advance exactly once from its parent")
        if parent_id in children:
            raise ContractError("Procedure family has incomparable branches or a stale parent")
        children[parent_id] = identity

    # Consecutive, positive revision numbers rule out cycles. Complete parents
    # and a single child per predecessor therefore give one chain from each root.
    result = {}
    for family, identity in roots.items():
        while identity in children:
            identity = children[identity]
        result[family] = revisions[identity]
    return result
