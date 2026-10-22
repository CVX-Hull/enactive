"""Bounded native delivery evidence, never an observation or input capability.

The controller authenticates the complete native body before projection. These
pure checks audit retained correlation without consulting current runtime state.
"""
from __future__ import annotations

import math

from .contracts import (
    ContractError, _INT, _object, _text, canonical, json_object, validate_json,
)
from .evidence import _OBSERVATION, _identity
from .native_input import input_schema, validate_input

_ACK_FIELDS = ("protocol", "id", "session", "revision", "status", "error", "paused",
               "pause_origin", "takeover_generation", "timestamp_ms", "frame_ok", "frame", "boundary")
_ACK = _object({key: _OBSERVATION["properties"][key] for key in _ACK_FIELDS})
_CORRELATION = ("kind", "value", "expected_session", "expected_revision", "expected_boundary_id",
                "source_before", "preflight_source")
_DIAGNOSTIC = {"anyOf": [_text(1024), {"type": "null"}]}


def _validate_ack(value: dict) -> dict:
    if type(value) is not dict:
        raise ContractError("Native ACK must be its closed projected object")
    ack = json_object(value)
    validate_json(ack, _ACK)
    if ack["status"] not in ("ready", "rejected"):
        raise ContractError("Ordinary delivery requires a terminal native ACK")
    boundary = ack["boundary"]
    if boundary["input_receiver"] and boundary["kind"] not in ("normal_play", "menu"):
        raise ContractError("Restricted native boundary cannot assert an ordinary receiver")
    return ack


def compact_native_ack(full_native_state: dict) -> dict:
    """Project an already authenticated full body, preserving native diagnostics.

    Excludes scene/UI/geometry rather than duplicating a potentially large archive.
    A rejected or failed capture still attests delivery, never input eligibility.
    """
    if type(full_native_state) is not dict or not set(_ACK_FIELDS) <= full_native_state.keys():
        raise ContractError("Native ACK lost its required projection fields")
    return _validate_ack({key: full_native_state[key] for key in _ACK_FIELDS})


def validate_ordinary_mapping(intent: dict, receipt: dict, *, logical_id: str,
                              native_id: str | None, disposition: str) -> None:
    """Audit immutable ordinary intent/request/ACK linkage, without live authority."""
    if intent["kind"] not in ("action", "key", "direct", "resume"):
        return
    if disposition not in ("returned", "rejected"):
        if receipt.get("native_ack") is not None:
            raise ContractError("Uncertain or unpublished delivery cannot carry an authenticated ACK")
        return
    validate_json(receipt.get("expected_revision"), _INT)
    if (native_id is None or receipt.get("logical_action_id") != logical_id
            or receipt.get("native_request_id") != native_id or receipt.get("published") is not True
            or receipt.get("transport_disposition") != disposition
            or any(key not in receipt or receipt[key] != intent[key] for key in _CORRELATION)):
        raise ContractError("Ordinary receipt contradicts its immutable logical/native mapping")
    for key in ("processing_error", "evidence_loss"):
        if key not in receipt:
            raise ContractError("Known ordinary delivery requires separate bounded processing/loss diagnostics")
        validate_json(receipt[key], _DIAGNOSTIC)
    validate_json(receipt.get("received_monotonic"), {"type": "number", "minimum": 0, "maximum": 10**12})
    if not math.isfinite(receipt["received_monotonic"]):
        raise ContractError("Native ACK requires its actual finite receipt clock")
    encoded = receipt.get("native_request_json")
    if type(encoded) is not str or len(encoded.encode()) > 4096:
        raise ContractError("Ordinary receipt requires bounded canonical native admission")
    request = json_object(encoded)
    if canonical(request) != encoded:
        raise ContractError("Native admission must be canonical")
    properties = _OBSERVATION["properties"]
    schema = {key: properties[key] for key in ("protocol", "session", "revision", "frame", "takeover_generation")}
    schema.update(id={**_text(128), "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$"},
        kind={"const": intent["kind"]}, deadline_ms=_INT,
        boundary_id=properties["boundary"]["properties"]["id"],
        require_exact_frame={"type": "boolean"},
        authority=_object({"controller_boot_id": _text(128), "counter": _INT}))
    payload = "input" if intent["kind"] == "direct" else intent["kind"]
    if intent["kind"] != "resume":
        schema[payload] = input_schema() if payload == "input" else _text(160)
        validate_json(receipt["value"], schema[payload])
    validate_json(request, _object(schema))
    if (request["id"] != native_id or request["session"] != intent["expected_session"]
            or request["revision"] != intent["expected_revision"]
            or request["boundary_id"] != intent["expected_boundary_id"]
            or not request["frame"]
            or intent["kind"] != "resume" and request[payload] != intent["value"]):
        raise ContractError("Native request differs from its actual immutable preflight intent")
    if intent["kind"] == "direct":
        validate_input(request["input"])
        if request["require_exact_frame"] is not False:
            raise ContractError("Ordinary input must not require frame equivalence")
    ack = _validate_ack(receipt.get("native_ack"))
    if ack["id"] != native_id or ack["status"] != ("ready" if disposition == "returned" else "rejected"):
        raise ContractError("Native ACK differs from its exact request/disposition")
    if disposition == "returned" and (ack["session"] != request["session"]
            or ack["revision"] <= intent["expected_revision"]):
        raise ContractError("Returned ACK must advance its actual preflight session/revision")
    source = receipt.get("source_after")
    if source is not None:
        validate_json(source, {**_text(128), "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$"})
        if source != _identity(ack):
            raise ContractError("Ordinary after-source differs from its authenticated ACK capture")
    elif disposition == "returned" and not receipt["evidence_loss"]:
        raise ContractError("Returned delivery without after evidence requires explicit evidence loss")
