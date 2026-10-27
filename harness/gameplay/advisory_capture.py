"""Current captured-data contracts for immutable advisory provenance.

These objects are not native observations, input packets or program views. Full
original wire grammar is validated during offline export. Current readers check
bounded data, exact original-byte derivation and shared capture/delivery facts.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .contracts import (
    ContractError, EvidenceRef, _array, _integer, _nullable, _object, _text, canonical, json_object, validate_json,
)
from .evidence import _OBSERVATION, _capture_consistency, _identity
from .native_receipts import (
    _ACK, _published_correlations, _published_input_schema,
    _published_receipt_mapping, _receipt_diagnostics, _terminal_correlations,
)

SOURCE_VERSION = "advisory-source/1"
CAPTURE_VERSION = "advisory-capture/1"
_SHA = {**_text(64), "pattern": "^[a-f0-9]{64}$", "not": {"pattern": "[^a-f0-9]"}}
_ID = {**_text(128), "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$",
       "not": {"pattern": "[^A-Za-z0-9_-]"}}
# These are explicit provenance values in a current data format, never supported
# native receiver versions. Original UI is opaque historical JSON, not current UI.
_PROTOCOL = {"type": "integer", "enum": [6, 7]}
_CAPTURE_FIELDS = deepcopy(_OBSERVATION["properties"])
del _CAPTURE_FIELDS["protocol"], _CAPTURE_FIELDS["ui"]
_CAPTURE_FIELDS.update(schema={"const": CAPTURE_VERSION}, original_protocol=_PROTOCOL,
                       original_ui={"anyOf": [{"type": "object"}, {"type": "null"}]})
_CAPTURE = _object(_CAPTURE_FIELDS)
_ORIGIN = _object({"ledger_sha256": _SHA, "index_sha256": _SHA,
                   "native_protocol": _PROTOCOL, "store_version": {"type": "integer", "enum": [5, 6]},
                   "program_view": {"enum": ["program-view/1", "program-view/2"]}})
_SOURCE = _object({"schema": {"const": SOURCE_VERSION}, "mission_id": _ID,
                   "origin": _ORIGIN, "reference": {"type": "object"}, "capture": _CAPTURE,
                   "disposition": {"const": "retained"}, "grants_authority": {"const": False}})


def capture_projection(original: dict) -> dict:
    """Losslessly rename provenance fields into the current advisory data type.

    The caller must independently obtain original from pinned bytes. This helper
    cannot authenticate an archive, its original wire syntax or export operation.
    """
    value = json_object(original)
    if set(value) != set(_OBSERVATION["properties"]):
        raise ContractError("Original capture fields differ from the selected export baseline")
    value["original_protocol"] = value.pop("protocol")
    value["original_ui"] = value.pop("ui")
    value["schema"] = CAPTURE_VERSION
    return validate_capture(value)


def validate_capture(value: dict) -> dict:
    """Validate current captured facts; never return a current observation."""
    captured = json_object(value)
    validate_json(captured, _CAPTURE)
    # Only the common consistency function sees these local aliases. No caller
    # receives an observation or a value accepted by current source binding.
    facts = {key: item for key, item in captured.items() if key != "schema"}
    facts["ui"] = facts.pop("original_ui")
    facts["protocol"] = facts.pop("original_protocol")
    _capture_consistency(facts)
    return captured


def source_envelope(mission_id: str, origin: dict, reference: dict, original: dict) -> dict:
    """Build explicit historical presentation after original-byte verification."""
    return validate_source({"schema": SOURCE_VERSION, "mission_id": mission_id, "origin": origin,
        "reference": reference, "capture": capture_projection(original),
        "disposition": "retained", "grants_authority": False})


def validate_source(value: dict, *, mission_id: str | None = None, source_id: str | None = None) -> dict:
    """Validate advisory metadata identity, without source/PNG authentication."""
    result = json_object(value)
    validate_json(result, _SOURCE)
    capture = validate_capture(result["capture"])
    reference = EvidenceRef.from_dict(result["reference"])
    origin = result["origin"]
    expected = (6, 5, "program-view/1") if capture["original_protocol"] == 6 else (7, 6, "program-view/2")
    if (origin["native_protocol"], origin["store_version"], origin["program_view"]) != expected:
        raise ContractError("Advisory origin contradicts its original capture contract")
    scene = capture["scene"]
    if (reference.observation_id != _identity(capture)
            or reference.session != capture["session"] or reference.revision != capture["revision"]
            or reference.timestamp_ms != capture["timestamp_ms"]
            or reference.boundary_kind != capture["boundary"]["kind"]
            or reference.turn != (None if scene is None else scene["turn"])
            or mission_id is not None and result["mission_id"] != mission_id
            or source_id is not None and reference.observation_id != source_id):
        raise ContractError("Advisory source contradicts its exact qualified capture")
    validate_json(reference.observation_id, _SHA)
    validate_json(reference.frame_sha256, _SHA)
    return result


_REQUEST = _object({
    "schema": {"const": "advisory-request/1"}, "original_schema": {"const": "mission/11"},
    "request_id": _ID, "mission_id": _ID,
    "kind": {"enum": ["start", "observe", "remember", "correct", "skill", "handoff", "claim", "readmit",
                       "lifecycle", "reconcile", "stop"]},
    "epoch": _nullable(_integer()), "sources": {**_array(_ID, 128), "uniqueItems": True},
})


def request_projection(original: dict) -> dict:
    """Type original captured identity fields without accepting an old request."""
    request = json_object(original)
    start = request.get("kind") == "start"
    if start and type(request.get("admission")) is not dict:
        raise ContractError("Captured Start requires its original admission identity")
    mission = request["admission"].get("mission_id") if start else request.get("mission_id")
    projected = {"schema": "advisory-request/1", "original_schema": request.get("schema"),
        "request_id": request.get("request_id"), "mission_id": mission, "kind": request.get("kind"),
        "epoch": None if start else request.get("epoch"), "sources": request.get("sources", [])}
    validate_json(projected, _REQUEST)
    if not start and projected["epoch"] is None:
        raise ContractError("Captured durable request requires its original epoch")
    return projected


def _native_projection(value: dict, schema: dict, *, tag: str, protocol: int) -> dict:
    """Validate a new captured packet type, not an old native receiver packet."""
    original = json_object(value)
    projected = dict(original)
    projected["original_protocol"] = projected.pop("protocol", None)
    projected["schema"] = tag
    shape = deepcopy(schema)
    del shape["properties"]["protocol"]
    shape["required"].remove("protocol")
    shape["properties"].update(original_protocol={"type": "integer", "const": protocol}, schema={"const": tag})
    shape["required"].extend(("original_protocol", "schema"))
    validate_json(projected, shape)
    return projected


def validate_captured_mapping(intent: dict, receipt: dict, *, logical_id: str,
                              native_id: str | None, disposition: str, protocol: int) -> dict | None:
    """Audit independently decoded provenance through shared delivery predicates.

    `protocol` is selected by the admitted export provenance, never by a live
    native input. Returned values remain captured-data projections only.
    """
    if type(protocol) is not int or protocol not in (6, 7):
        raise ContractError("Unknown advisory capture provenance")
    if intent["kind"] not in ("action", "key", "direct", "resume"):
        return None
    if disposition not in ("returned", "rejected"):
        if receipt.get("native_ack") is not None:
            raise ContractError("Uncertain or unpublished delivery cannot carry an authenticated ACK")
        return None
    _published_receipt_mapping(intent, receipt, logical_id=logical_id, native_id=native_id)
    encoded = receipt.get("native_request_json")
    if type(encoded) is not str or len(encoded.encode()) > 4096:
        raise ContractError("Captured admission requires bounded original canonical bytes")
    original = json_object(encoded)
    if canonical(original) != encoded:
        raise ContractError("Original captured admission must be canonical")
    request = _native_projection(original, _published_input_schema(intent),
        tag="advisory-native-input/1", protocol=protocol)
    _published_correlations(intent, receipt, request, native_id=native_id)
    _receipt_diagnostics(receipt, disposition=disposition)
    ack = _native_projection(receipt.get("native_ack"), _ACK, tag="advisory-native-ack/1", protocol=protocol)
    if ack["status"] not in ("ready", "rejected"):
        raise ContractError("Captured ordinary delivery requires a terminal ACK")
    if ack["boundary"]["input_receiver"] and ack["boundary"]["kind"] not in ("normal_play", "menu"):
        raise ContractError("Restricted captured boundary cannot assert an ordinary receiver")
    _terminal_correlations(intent, receipt, request, ack, native_id=native_id, disposition=disposition)
    return {"request": request, "ack": ack}
