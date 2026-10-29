"""Exact retained native/browser frame joins; no useful-task or paint inference."""
from __future__ import annotations

import json
from pathlib import Path

from harness.gameplay.contracts import ContractError, _pairs, _reject_constant
from tools.host_analysis import distribution, number


def read_metadata(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise ContractError(f"Metadata exceeds 64 MiB: {path}")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError(f"Malformed metadata JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"Expected metadata object: {path}")
    return value


def identity(state: dict) -> list:
    """The public viewer's frameIdentity fields; compare parsed JSON, not key order."""
    if not isinstance(state, dict):
        raise ContractError("Expected observation object")
    boundary = state.get("boundary") or {}
    if not isinstance(boundary, dict):
        raise ContractError("Expected boundary object")
    return [state.get("protocol"), state.get("session"), state.get("revision"), state.get("frame"),
        boundary.get("kind"), boundary.get("id"), boundary.get("control_generation"),
        boundary.get("interrupt_request_id"), boundary.get("recovery_operations"),
        state.get("takeover_generation"), state.get("pause_origin"), state.get("frame_geometry")]


def witness_summary(paths: list[Path]) -> dict:
    if len(paths) < 2 or len(paths) > 33:
        raise ContractError("Select one mission/evidence index and 1–32 observer exports")
    source = paths[0] / "evidence/evidence.json" if paths[0].is_dir() else paths[0]
    evidence = read_metadata(source)
    if type(evidence.get("store_version")) is not int or evidence["store_version"] != 6:
        raise ContractError("Unsupported evidence index version")
    if not isinstance(evidence.get("entries"), list):
        raise ContractError("Expected retained evidence entries")
    candidates, exports = {}, []
    for path in paths[1:]:
        data = read_metadata(path)
        if data.get("schema") != "observer-timing/3" or not isinstance(data.get("frames"), list):
            raise ContractError(f"Unsupported observer export: {path}")
        exports.append({"path": str(path), "dropped": data.get("dropped"), "frames": len(data["frames"])})
        for frame in data["frames"]:
            if not isinstance(frame, dict):
                raise ContractError(f"Expected frame object: {path}")
            if frame.get("outcome") != "dom_replaced":
                continue
            try:
                fields = json.loads(frame["frame_identity"], object_pairs_hook=_pairs, parse_constant=_reject_constant)
                if not isinstance(fields, list) or len(fields) != 12:
                    raise ValueError("Expected current frame identity")
                key = json.dumps(fields, sort_keys=True)
            except (KeyError, TypeError, ValueError, RecursionError) as exc:
                raise ContractError(f"Invalid DOM frame identity: {path}") from exc
            # Overlapping exports of the same page do not create new witnesses.
            clock = (frame.get("native_capture_epoch_ms"), frame.get("dom_replaced_epoch_ms"))
            if not all(number(value) for value in clock):
                raise ContractError(f"Expected finite DOM/capture clocks: {path}")
            candidates.setdefault(key, {})[clock] = frame
    rows, measured, seen = [], [], set()
    for entry in evidence["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("reference"), dict) or not isinstance(entry.get("observation"), dict):
            raise ContractError("Expected evidence reference and observation objects")
        ref, state = entry.get("reference", {}), entry.get("observation", {})
        key = json.dumps(identity(state), sort_keys=True)
        capture = ref.get("timestamp_ms")
        coherent = (ref.get("session") == state.get("session") and ref.get("revision") == state.get("revision")
            and state.get("frame_ok") is True and isinstance(state.get("frame"), str))
        matches = [f for f in candidates.get(key, {}).values()
            if coherent and number(capture) and f.get("native_capture_epoch_ms") == capture and state.get("timestamp_ms") == capture]
        dom = min((f["dom_replaced_epoch_ms"] for f in matches), default=None)
        elapsed = dom - capture if dom is not None else None
        invalid_clock = elapsed is not None and elapsed < 0
        rows.append({"source_id": ref.get("observation_id"), "session": ref.get("session"),
            "frame": state.get("frame"), "native_capture_epoch_ms": capture,
            "dom_replaced_epoch_ms": dom, "capture_to_dom_ms": elapsed,
            "distinct_matching_presentations": len(matches),
            "missing_reason": "invalid_cross_clock_interval" if invalid_clock else None if dom is not None else "no_exact_DOM_match"})
        witness_key = (key, capture)
        if elapsed is not None and not invalid_clock and witness_key not in seen:
            measured.append(elapsed)
            seen.add(witness_key)
    return {"schema": "witness-analysis/1", "scope": "First retained exact-frame DOM witness assuming shared wall clock; not physical paint, attention, source freshness or useful-goal latency",
        "evidence_index": str(source), "exports": exports, "source_rows": rows,
        "unique_frame_capture_to_dom_ms": distribution(measured),
        "missing_source_matches": sum(x["missing_reason"] is not None for x in rows)}
