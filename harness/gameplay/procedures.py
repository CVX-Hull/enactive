"""Bounded procedure artifacts and pure, linear-family projection.

Shape and ancestry do not establish semantic truth, available episode sources or
input authority. Callers own source validation and environment-pin matching.
"""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
import hashlib
from typing import Any

from .contracts import (
    ContractError, _array, _enum, _integer, _nullable, _object, _text,
    json_object, validate_json,
)
from .contracts import canonical

VERSION = "procedure/3"
IMPORT_VERSION = "procedure-import/1"
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
    "program": _nullable(_object({"language": {"const": "javascript/1"},
                                   "source": _text(32_768)})),
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
        "native_protocol": {"type": "integer", "const": 7},
        "mission_schema": {"const": "mission/11"}, "configuration": _TEXT,
    }),
    "support": _array(_EPISODE, 8, 1), "counterexamples": _array(_EPISODE, 8),
    "status": _enum("candidate", "active", "disputed", "retired"), "reason": _TEXT,
})
# These are current advisory data contracts, never historical execution schemas.
# Original syntax admission and binding to archive bytes remain the importer's job.
_ORIGINAL_SCHEMA = deepcopy(_SCHEMA)
_ORIGINAL_SCHEMA["properties"]["environment"]["properties"]["native_protocol"]["const"] = 6
_SHA256 = {"type": "string", "minLength": 64, "maxLength": 64, "pattern": "^[a-f0-9]{64}$"}
_IMPORT_SCHEMA = deepcopy(_ORIGINAL_SCHEMA)
_IMPORT_SCHEMA["properties"].update({
    "schema": {"const": IMPORT_VERSION}, "record_type": {"const": "HistoricalProcedure"},
    "advisory_only": {"const": True},
    "origin": _object({
        "schema": {"const": VERSION}, "record_type": {"const": "Procedure"},
        "record_sha256": _SHA256, "ledger_sha256": _SHA256, "index_sha256": _SHA256,
        "program_view": {"const": "program-view/1"},
    }),
})
_IMPORT_SCHEMA["required"].extend(("advisory_only", "origin"))
_LINEAGE_SCHEMA = {"oneOf": [_SCHEMA, _IMPORT_SCHEMA]}


def procedure_schema() -> dict[str, Any]:
    """Return a defensive copy of the closed procedure/3 record schema."""
    return json_object(_SCHEMA)


def lineage_node_schema() -> dict[str, Any]:
    """Return the closed current/advisory lineage union, without execution eligibility."""
    return json_object(_LINEAGE_SCHEMA)


def import_procedure(body: str, *, ledger_sha256: str, index_sha256: str) -> dict[str, Any]:
    """Derive advisory data from an original procedure/3 native6 stored JSON body.

    The hash binds the exact supplied UTF-8 string, including whitespace. This
    pure conversion authenticates neither that string nor its archive pins and
    does not replace full offline validation of the original archive.
    """
    if not isinstance(body, str):
        raise ContractError("Procedure import requires an original stored JSON string")
    try:
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    except UnicodeError as exc:
        raise ContractError("Procedure import requires valid UTF-8 JSON") from exc
    original = _validate_node(body, _ORIGINAL_SCHEMA)
    return validate_lineage_node({
        **original, "schema": IMPORT_VERSION, "record_type": "HistoricalProcedure",
        "advisory_only": True,
        "origin": {"schema": VERSION, "record_type": "Procedure", "record_sha256": digest,
                   "ledger_sha256": ledger_sha256, "index_sha256": index_sha256,
                   "program_view": "program-view/1"},
    })


def procedure_authoring_schema() -> dict[str, Any]:
    """Return the closed semantic entry schema without software-owned metadata."""
    schema = procedure_schema()
    for field in ("schema", "record_type", "id", "mission_id", "procedure_id", "revision", "environment"):
        del schema["properties"][field]
        schema["required"].remove(field)
    return schema


def author_procedure(
    entry: dict[str, Any] | str | bytes, *, mission_id: str, identity: str,
    environment: dict[str, Any], parent: dict[str, Any] | str | bytes | None = None,
) -> dict[str, Any]:
    """Bind semantic authorship to caller-selected admission and parent metadata.

    The caller supplies the original admitted environment and owns source,
    availability, lineage/conflict and authority checks. This pure helper only
    validates shape, exact selected-parent identity and final canonical bounds.
    """
    semantic = json_object(entry)
    validate_json(semantic, procedure_authoring_schema())
    validate_json({"mission_id": mission_id, "identity": identity},
                  _object({"mission_id": _ID, "identity": _ID}))
    digest = hashlib.sha256((mission_id + "\0" + identity).encode()).hexdigest()
    family, revision = "procedure-" + digest, 1
    if semantic["parent"] is None:
        if parent is not None:
            raise ContractError("Root procedure cannot use a selected parent")
    else:
        if parent is None:
            raise ContractError("Procedure successor requires a selected parent revision")
        selected = validate_lineage_node(parent)
        if semantic["parent"] != {"mission_id": selected["mission_id"], "revision_id": selected["id"]}:
            raise ContractError("Procedure parent must match the selected qualified revision")
        family, revision = selected["procedure_id"], selected["revision"] + 1
    return validate_procedure({**semantic, "schema": VERSION, "record_type": "Procedure",
                               "id": "revision-" + digest, "mission_id": mission_id,
                               "procedure_id": family, "revision": revision,
                               "environment": environment})


def validate_procedure(value: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Validate shape and byte bounds, returning an independent decoded copy."""
    return _validate_node(value, _SCHEMA)


def validate_lineage_node(value: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Validate bounded current or historical advisory lineage data, not authority."""
    result = json_object(value)
    # Select the closed variant before validation so validate_json's additional
    # strict integer checks still traverse every field (they do not walk oneOf).
    schema = _SCHEMA if result.get("schema") == VERSION else _IMPORT_SCHEMA
    return _validate_node(result, schema)


def _validate_node(value: dict[str, Any] | str | bytes, schema: dict[str, Any]) -> dict[str, Any]:
    result = json_object(value)
    validate_json(result, schema)
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
        record = validate_lineage_node(value)
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
