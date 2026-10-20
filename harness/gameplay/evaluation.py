"""Passive, exact evaluation/1 artifacts and offline accounting.

All API inputs and outputs are JSON object snapshots; callers supply observed
clocks, evidence and judgments. This module never dispatches or measures a model
implicitly. ``manifest.admission.monotonic_ms`` is the admission clock reading;
all event/outcome ``elapsed_ms`` values are relative to that reading. ``finish``
requires the final clock even when a timeout follows the last event.

Manifest keys and every event payload are described by ``run_schema()``. Events
share event_id, elapsed_ms, kind, session, game_turn, game_turn_missing_reason,
evidence (gameplay/2 EvidenceRef objects), and payload. Payload kinds:

* action: unique primitive action_id, transport_disposition, dispatch_state,
  duration_ms, verified_steps (0, 1 or unknown), its missing reason, and boolean
  invalid/stale/unknown/verified_no_progress. Bounded walks emit one per attempt.
* model_call: role, model_id, configuration_id, duration_ms, status, input_tokens,
  output_tokens, cached_input_tokens and cost_usd. Each nullable metric has its
  own *_missing_reason. Cached tokens are already included in input tokens.
* observation: duration_ms, available and fresh.
* intervention/recovery: actor (operator/autonomous), operation, outcome, reason.
* decision: decision, public reason, actor, nullable model_id plus missing reason,
  expected/observed claim lists, unknowns. A claim has text, kind
  (fact/interpretation), and evidence; these are public claims, not chain of thought.

Every nullable measurement/identity requires a nonempty missing reason iff null.
An outcome has disposition, elapsed_ms, session, game_turn plus reason,
verified_steps plus reason, first_useful_action_event_id plus
first_useful_action_missing_reason, harmful_actions/deaths plus reasons,
evidence, and assessment {assessor, method}. Use null for unassessed harms;
zero asserts an actual assessment. The independent assessor identifies the first
useful action; transport delivery alone never establishes usefulness or success.

Typical use: ``r = RunRecorder(manifest); r.record(event); r.finish(outcome);
r.write(path)``. Pass real retained EvidenceRef.to_dict() references for native
measurements and describe the legitimate native start and assessment. No recorded
model calls means uninstrumented/absent calls, never proof that external Codex or
operator planning was free. Unknown/budget_exhausted runs are retained as censored. Structural validation
does not verify evidence bytes or establish native success. Native starts require
evidence; native success requires final evidence. A missing final frame on a failed
or unknown run belongs in the independent assessment method.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from jsonschema import Draft202012Validator, validators
from jsonschema.exceptions import ValidationError

from .contracts import ContractError, EvidenceRef, record_schema

VERSION = "evaluation/1"
MAX_EVENTS = 4096
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_RUNS = 4096
_MAX_NUMBER = 10**15
_OUTCOMES = ("success", "partial", "failed", "unknown", "budget_exhausted")
_ROLES = ("planner", "tactical", "monitor", "verifier", "router")


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def _text() -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": 4096}


def _enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


def _number(maximum: float = _MAX_NUMBER, *, integer: bool = False) -> dict[str, Any]:
    return {"type": "integer" if integer else "number", "minimum": 0, "maximum": maximum}


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _measured(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {name: _nullable(schema), f"{name}_missing_reason": _nullable(_text())}


def _array(schema: dict[str, Any], maximum: int = 64) -> dict[str, Any]:
    return {"type": "array", "items": schema, "maxItems": maximum}


_EVIDENCE = _array({"$ref": "#/$defs/EvidenceRef"})
_ENDPOINT = {"session": _text(), **_measured("game_turn", {"type": "integer", "minimum": -(2**31), "maximum": 2**31 - 1})}
_BUDGETS = _object({"primitives": _number(8, integer=True), "turns": _number(32, integer=True),
                    "wall_ms": _number(120000), "model_calls": _number(10, integer=True),
                    "model_call_ms": _number(30000),
                    **_measured("input_tokens", _number(10**12, integer=True)),
                    **_measured("output_tokens", _number(10**12, integer=True)),
                    **_measured("cost_usd", _number(10**9))})
_MANIFEST = _object({
    **{key: _text() for key in ("run_id", "scenario_id", "family_id", "protocol_version",
                                "start_description")},
    "split": _enum("development", "held_out"), "lane": _enum("synthetic", "native"),
    "condition": _enum("primitive", "bounded_skill", "same_model_roles"),
    "source_commit": {"type": "string", "minLength": 40, "maxLength": 40,
                      "pattern": "^[a-f0-9]{40}$"},
    **_measured("native_build", _text()), **_measured("model_id", _text()),
    **_measured("configuration_id", _text()), "budgets": _BUDGETS,
    "admission": _object({"monotonic_ms": _number(), **_ENDPOINT}), "evidence": _EVIDENCE,
})
_BOOL = {"type": "boolean"}
_CLAIM = _object({"text": _text(), "kind": _enum("fact", "interpretation"), "evidence": _EVIDENCE})
_PAYLOADS = {
    "action": _object({"action_id": _text(),
        "transport_disposition": _enum("not_dispatched", "dispatched", "returned", "rejected", "unknown"),
        "dispatch_state": _enum("not_dispatched", "dispatched", "unknown"),
        "duration_ms": _number(), **_measured("verified_steps", _number(1, integer=True)),
        **{key: _BOOL for key in ("invalid", "stale", "unknown", "verified_no_progress")}}),
    "model_call": _object({"role": _enum(*_ROLES), "model_id": _text(),
        "configuration_id": _text(), "duration_ms": _number(),
        "status": _enum("completed", "failed", "timed_out", "unknown"),
        **_measured("input_tokens", _number(10**12, integer=True)),
        **_measured("output_tokens", _number(10**12, integer=True)),
        **_measured("cached_input_tokens", _number(10**12, integer=True)),
        **_measured("cost_usd", _number(10**9))}),
    "observation": _object({"duration_ms": _number(), "available": _BOOL, "fresh": _BOOL}),
    "decision": _object({"decision": _enum("continue", "inspect", "escalate", "replan", "stop"),
        "reason": _text(), "actor": _enum("operator", "autonomous"),
        **_measured("model_id", _text()), "expected": _array(_CLAIM), "observed": _array(_CLAIM),
        "unknowns": _array(_text())}),
}
for _kind in ("intervention", "recovery"):
    _PAYLOADS[_kind] = _object({"actor": _enum("operator", "autonomous"),
                              "operation": _text(), "outcome": _text(), "reason": _text()})
_EVENT_COMMON = {"event_id": _text(), "elapsed_ms": _number(), **_ENDPOINT, "evidence": _EVIDENCE}
_EVENT = {"oneOf": [_object({**_EVENT_COMMON, "kind": {"const": kind}, "payload": payload})
                    for kind, payload in _PAYLOADS.items()]}
_OUTCOME = _object({"disposition": _enum(*_OUTCOMES), "elapsed_ms": _number(), **_ENDPOINT,
    **_measured("verified_steps", _number(8, integer=True)),
    "first_useful_action_event_id": _nullable(_text()),
    "first_useful_action_missing_reason": _nullable(_text()),
    **_measured("harmful_actions", _number(MAX_EVENTS, integer=True)),
    **_measured("deaths", _number(MAX_EVENTS, integer=True)), "evidence": _EVIDENCE,
    "assessment": _object({"assessor": _text(), "method": _text()})})
_DEFS = record_schema(EvidenceRef)["$defs"]
_RUN_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": _DEFS,
               **_object({"schema": {"const": VERSION}, "manifest": _MANIFEST,
                          "events": _array(_EVENT, MAX_EVENTS), "outcome": _OUTCOME})}
# jsonschema otherwise treats 1.0 as integer; measurements must preserve JSON types.
_Validator = validators.extend(Draft202012Validator, type_checker=
    Draft202012Validator.TYPE_CHECKER.redefine("integer", lambda checker, value: type(value) is int))


def run_schema() -> dict[str, Any]:
    """Return an independent exact JSON Schema (semantic invariants also apply)."""
    return json.loads(json.dumps(_RUN_SCHEMA))


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ContractError(f"Nonfinite JSON number: {value}")


def _snapshot(value: dict[str, Any] | str | bytes) -> dict[str, Any]:
    try:
        if type(value) is dict:
            # Reject non-JSON container/key types rather than coercing them.
            _json_types(value)
            encoded = json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":")).encode()
        elif isinstance(value, (str, bytes)):
            encoded = value.encode("utf-8") if isinstance(value, str) else value
        else:
            raise ContractError("Expected a JSON object")
        if len(encoded) > MAX_JSON_BYTES:
            raise ContractError("Run JSON exceeds 8 MiB")
        result = json.loads(encoded, object_pairs_hook=_pairs, parse_constant=_reject_constant)
        _json_types(result)
        if type(result) is not dict:
            raise ContractError("Expected a JSON object")
        # Also bound canonical serialization, not just a compact untrusted input.
        if len(json.dumps(result, ensure_ascii=True, allow_nan=False).encode()) > MAX_JSON_BYTES:
            raise ContractError("Run JSON exceeds 8 MiB")
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError(f"Invalid JSON: {exc}") from exc


def _json_types(value: Any) -> None:
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise ContractError("JSON object keys must be strings")
            _json_types(child)
    elif type(value) is list:
        for child in value:
            _json_types(child)
    elif type(value) in (int, float):
        if abs(value) > _MAX_NUMBER or not math.isfinite(value):
            raise ContractError("JSON numbers must be finite and bounded")
    elif type(value) is str:
        if len(value) > 4096:
            raise ContractError("Strings exceed 4096 characters")
    elif value is not None and type(value) is not bool:
        raise ContractError("Expected standard JSON values")


def _validate(value: dict[str, Any], schema: dict[str, Any]) -> None:
    try:
        _Validator({"$defs": _DEFS, **schema}).validate(value)
    except ValidationError as exc:
        path = ".".join(map(str, exc.absolute_path)) or "record"
        raise ContractError(f"{path}: {exc.message[:4096]}") from exc
    _missingness(value)


def _missingness(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_missing_reason"):
                name = key.removesuffix("_missing_reason")
                if name == "first_useful_action":
                    name = "first_useful_action_event_id"
                if (value[name] is None) != (child is not None):
                    raise ContractError(f"{name} requires a reason iff unavailable")
            _missingness(child)
    elif isinstance(value, list):
        for child in value:
            _missingness(child)


def _event_invariants(event: dict[str, Any]) -> None:
    payload = event["payload"]
    if "duration_ms" in payload and payload["duration_ms"] > event["elapsed_ms"]:
        raise ContractError("Event duration cannot start before admission")
    if event["kind"] == "action":
        disposition, dispatch = payload["transport_disposition"], payload["dispatch_state"]
        if ((disposition == "not_dispatched" and dispatch != "not_dispatched")
                or (disposition in ("dispatched", "returned") and dispatch != "dispatched")
                or (dispatch == "unknown" and disposition != "unknown")
                or (disposition == "unknown" and dispatch == "not_dispatched")):
            raise ContractError("Contradictory transport and dispatch state")
        if disposition == "unknown" and not payload["unknown"]:
            raise ContractError("Unknown transport requires an unknown flag")
        if payload["verified_no_progress"] and payload["verified_steps"] != 0:
            raise ContractError("Verified no-progress requires observed zero steps")
        if dispatch == "not_dispatched" and payload["verified_steps"] not in (0, None):
            raise ContractError("Undispatched attempt cannot claim a verified step")
    elif event["kind"] == "model_call":
        cached, total = payload["cached_input_tokens"], payload["input_tokens"]
        if cached is not None and (total is None or cached > total):
            raise ContractError("Cached input must be a known subset of input tokens")
    elif event["kind"] == "observation":
        if payload["fresh"] and not payload["available"]:
            raise ContractError("Unavailable observation cannot be fresh")
    elif event["kind"] == "decision":
        for claim in payload["expected"] + payload["observed"]:
            if not claim["evidence"]:
                raise ContractError("Claims require factual or interpreted evidence references")


def _sequence(manifest: dict[str, Any], events: list[dict[str, Any]],
              outcome: dict[str, Any] | None = None) -> None:
    seen_events: set[str] = set()
    seen_actions: set[str] = set()
    elapsed = 0
    endpoint = manifest["admission"]
    known_turns = {endpoint["session"]: endpoint["game_turn"]}
    for event in events:
        if event["event_id"] in seen_events:
            raise ContractError("Duplicate event ID")
        seen_events.add(event["event_id"])
        if event["kind"] == "action":
            action_id = event["payload"]["action_id"]
            if action_id in seen_actions:
                raise ContractError("One action event per primitive attempt; duplicate action ID")
            seen_actions.add(action_id)
        if event["elapsed_ms"] < elapsed:
            raise ContractError("Events must have nondecreasing elapsed time")
        _turn_order({"session": event["session"],
                     "game_turn": known_turns.get(event["session"])}, event)
        if event["game_turn"] is not None:
            known_turns[event["session"]] = event["game_turn"]
        elapsed, endpoint = event["elapsed_ms"], event
    if outcome is not None:
        if outcome["elapsed_ms"] < elapsed:
            raise ContractError("Final elapsed time predates the last event")
        _turn_order({"session": outcome["session"],
                     "game_turn": known_turns.get(outcome["session"])}, outcome)
        if (manifest["admission"]["session"] == outcome["session"]
                and manifest["admission"]["game_turn"] is not None
                and outcome["game_turn"] is not None
                and outcome["game_turn"] < manifest["admission"]["game_turn"]):
            raise ContractError("Final turn predates same-session admission")
        if outcome["disposition"] == "success" and outcome["verified_steps"] is None:
            raise ContractError("Success requires assessed verified progress")
        useful = outcome["first_useful_action_event_id"]
        if useful is not None and not any(e["event_id"] == useful and e["kind"] == "action"
                and e["payload"]["dispatch_state"] == "dispatched" for e in events):
            raise ContractError("First useful action must reference a known dispatched action in this run")


def _turn_order(before: dict[str, Any], after: dict[str, Any]) -> None:
    if (before["session"] == after["session"] and before["game_turn"] is not None
            and after["game_turn"] is not None and before["game_turn"] > after["game_turn"]):
        raise ContractError("Same-session game turns cannot decrease")


def _endpoint_evidence(evidence: list[dict[str, Any]], endpoint: dict[str, Any]) -> bool:
    return any(ref["session"] == endpoint["session"] and
               (endpoint["game_turn"] is None or ref["turn"] == endpoint["game_turn"])
               for ref in evidence)


def _manifest_invariants(manifest: dict[str, Any]) -> None:
    if manifest["lane"] == "native":
        if manifest["native_build"] is None:
            raise ContractError("Native measurements require native build identity")
        if not _endpoint_evidence(manifest["evidence"], manifest["admission"]):
            raise ContractError("Native measurements require legitimate start evidence matching admission")


def validate_run(value: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Validate a complete current run; return a detached snapshot or raise ContractError."""
    result = _snapshot(value)
    _validate(result, _RUN_SCHEMA)
    _manifest_invariants(result["manifest"])
    for event in result["events"]:
        _event_invariants(event)
    _sequence(result["manifest"], result["events"], result["outcome"])
    if (result["manifest"]["lane"] == "native"
            and result["outcome"]["disposition"] == "success"
            and not _endpoint_evidence(result["outcome"]["evidence"], result["outcome"])):
        raise ContractError("Native success requires final evidence matching its endpoint")
    return result


class RunRecorder:
    """Record explicit observations only. Errors leave the previous snapshot intact.

    ``to_dict`` and ``write`` require ``finish``; unfinished traces are not complete
    artifacts. A finished recorder is sealed. ``write`` uses exclusive creation and
    does not create parent directories or overwrite existing evidence.
    """

    def __init__(self, manifest: dict[str, Any]) -> None:
        self._manifest = _snapshot(manifest)
        _validate(self._manifest, _MANIFEST)
        _manifest_invariants(self._manifest)
        self._events: list[dict[str, Any]] = []
        self._outcome: dict[str, Any] | None = None

    def record(self, event: dict[str, Any]) -> None:
        if self._outcome is not None:
            raise ContractError("Finished recorder is sealed")
        if len(self._events) >= MAX_EVENTS:
            raise ContractError("Run exceeds 4096 events")
        candidate = _snapshot(event)
        _validate(candidate, _EVENT)
        _event_invariants(candidate)
        events = [*self._events, candidate]
        _sequence(self._manifest, events)
        _snapshot({"schema": VERSION, "manifest": self._manifest, "events": events})
        self._events.append(candidate)

    def finish(self, outcome: dict[str, Any]) -> None:
        if self._outcome is not None:
            raise ContractError("Finished recorder is sealed")
        result = validate_run({"schema": VERSION, "manifest": self._manifest,
                               "events": self._events, "outcome": outcome})
        self._outcome = result["outcome"]

    def to_dict(self) -> dict[str, Any]:
        if self._outcome is None:
            raise ContractError("Run requires an explicit final outcome")
        return validate_run({"schema": VERSION, "manifest": self._manifest,
                             "events": self._events, "outcome": self._outcome})

    def write(self, path: str | Path) -> None:
        value = self.to_dict()
        encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n"
        if len(encoded.encode()) > MAX_JSON_BYTES:
            raise ContractError("Run JSON exceeds 8 MiB")
        with Path(path).open("x", encoding="utf-8") as stream:
            stream.write(encoded)


def _total(values: Iterable[int | float | None]) -> dict[str, Any]:
    items = list(values)
    known = [item for item in items if item is not None]
    return {"known_subtotal": sum(known) if known else None, "known_count": len(known),
            "missing_count": len(items) - len(known)}


def _distribution(values: Iterable[int | float]) -> dict[str, Any]:
    items = sorted(values)
    return {"count": len(items), "median": median(items) if items else None,
            "p95": items[math.ceil(0.95 * len(items)) - 1] if items else None}


def _calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(calls), "statuses": dict(Counter(item["status"] for item in calls)),
            **{key: _total(item[key] for item in calls) for key in
               ("input_tokens", "output_tokens", "cached_input_tokens", "cost_usd")},
            "duration_ms": _distribution(item["duration_ms"] for item in calls)}


def _identity(run: dict[str, Any]) -> dict[str, Any]:
    manifest = run["manifest"]
    keys = ("family_id", "split", "lane", "condition", "source_commit", "native_build",
            "native_build_missing_reason", "model_id", "model_id_missing_reason",
            "configuration_id", "configuration_id_missing_reason", "protocol_version")
    return {key: manifest[key] for key in keys}


def _turns(run: dict[str, Any]) -> int | None:
    before, after = run["manifest"]["admission"], run["outcome"]
    if (before["session"] != after["session"] or before["game_turn"] is None
            or after["game_turn"] is None
            or any(event["session"] != before["session"] for event in run["events"])):
        return None
    return after["game_turn"] - before["game_turn"]


def _summarize(identity: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    events = [event for run in runs for event in run["events"]]
    actions = [event["payload"] for event in events if event["kind"] == "action"]
    calls = [event["payload"] for event in events if event["kind"] == "model_call"]
    outcomes = [run["outcome"] for run in runs]
    call_identities = [{"role": role, "model_id": model, "configuration_id": config}
        for role, model, config in sorted({(c["role"], c["model_id"], c["configuration_id"]) for c in calls})]
    useful_times: list[int | float | None] = []
    switches = 0
    for run in runs:
        useful = run["outcome"]["first_useful_action_event_id"]
        useful_times.append(next((event["elapsed_ms"] for event in run["events"]
                                 if event["event_id"] == useful), None))
        sequence = [e["payload"]["model_id"]
                    for e in run["events"] if e["kind"] == "model_call"]
        switches += sum(before != after for before, after in zip(sequence, sequence[1:]))
    observations = [e["payload"] for e in events if e["kind"] == "observation"]
    outcome_counts = {key: sum(o["disposition"] == key for o in outcomes) for key in _OUTCOMES}
    return {"identity": identity, "runs": len(runs),
        "run_ids": [run["manifest"]["run_id"] for run in runs],
        "scenario_ids": sorted({run["manifest"]["scenario_id"] for run in runs}),
        "sessions": sorted({run["manifest"]["admission"]["session"] for run in runs}),
        "outcomes": outcome_counts,
        "outcome_coverage": {"assessed": len(runs) - outcome_counts["unknown"],
                             "unknown": outcome_counts["unknown"]},
        "censored_runs": outcome_counts["unknown"] + outcome_counts["budget_exhausted"],
        **{key: _total(o[key] for o in outcomes) for key in ("verified_steps", "harmful_actions", "deaths")},
        "primitive_attempts": len(actions),
        "known_dispatches": sum(a["dispatch_state"] == "dispatched" for a in actions),
        "unknown_dispatches": sum(a["dispatch_state"] == "unknown" for a in actions),
        "not_dispatched": sum(a["dispatch_state"] == "not_dispatched" for a in actions),
        "action_verified_steps": _total(a["verified_steps"] for a in actions),
        "action_flags": {key: sum(a[key] for a in actions) for key in
                         ("invalid", "stale", "unknown", "verified_no_progress")},
        "game_turns": _total(_turns(run) for run in runs),
        "wall_ms": _total(o["elapsed_ms"] for o in outcomes),
        "wall_duration_ms": _distribution(o["elapsed_ms"] for o in outcomes),
        "time_to_first_useful_action_ms": _total(useful_times),
        "first_useful_action_duration_ms": _distribution(t for t in useful_times if t is not None),
        "model_switches": switches,
        "model_calls": {**_calls(calls),
            "by_role": {role: _calls([c for c in calls if c["role"] == role]) for role in _ROLES},
            "by_identity": [{"identity": call_identity,
                             **_calls([call for call in calls if all(call[k] == v for k, v in call_identity.items())])}
                            for call_identity in call_identities]},
        "event_duration_ms": {kind: _distribution(e["payload"]["duration_ms"] for e in events
                              if e["kind"] == kind) for kind in ("action", "observation", "model_call")},
        "interventions": {actor: sum(e["kind"] == "intervention" and e["payload"]["actor"] == actor
                                     for e in events) for actor in ("operator", "autonomous")},
        "recoveries": {actor: sum(e["kind"] == "recovery" and e["payload"]["actor"] == actor
                                  for e in events) for actor in ("operator", "autonomous")},
        "observations": {"count": len(observations),
                         "unavailable": sum(not o["available"] for o in observations),
                         "stale": sum(o["available"] and not o["fresh"] for o in observations)},
    }


def summarize_runs(runs: Iterable[dict[str, Any] | str | bytes]) -> dict[str, Any]:
    """Retain all outcomes in separate full-identity groups; never infer efficacy.

    ``known_subtotal`` is null when no measurement is known, including no model
    calls. Counts are recorded observations, not claims of complete instrumentation.
    Session changes/missing endpoints make game-turn totals unavailable. Percentile
    durations use nearest rank (ceil(0.95*n)); no censored run is discarded.
    """
    groups: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    seen: set[str] = set()
    for count, value in enumerate(runs, 1):
        if count > MAX_RUNS:
            raise ContractError("Summary exceeds 4096 runs")
        run = validate_run(value)
        run_id = run["manifest"]["run_id"]
        if run_id in seen:
            raise ContractError(f"Duplicate run ID: {run_id}")
        seen.add(run_id)
        identity = _identity(run)
        key = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        if key not in groups:
            groups[key] = (identity, [])
        groups[key][1].append(run)
    return {"schema": "evaluation-summary/1", "groups":
            [_summarize(identity, members) for identity, members in groups.values()]}
