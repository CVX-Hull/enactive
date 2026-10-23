"""Frozen gameplay/2 records; JSON Schema is the serialized trust boundary."""
from __future__ import annotations

from dataclasses import dataclass, fields
import json
from typing import Any, ClassVar, Literal, Self

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

VERSION = "gameplay/2"
VISIBILITY_VERSION = "cdda-visible/1"
MAX_JSON_BYTES = 1_048_576
Vector = tuple[int, int, int]
Direction = Literal["north", "south", "east", "west"]
Stage = Literal["outbound", "return"]
TransportDisposition = Literal["not_dispatched", "dispatched", "returned", "rejected", "unknown"]
BoundaryKind = Literal["normal_play", "activity_poll", "interrupt_confirmation", "debug_prompt", "menu", "unsupported"]
DIRECTIONS = {"north": (0, -1, 0), "south": (0, 1, 0),
              "east": (1, 0, 0), "west": (-1, 0, 0)}


class ContractError(ValueError):
    """Malformed or contradictory gameplay data; never proof of game success."""


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def _text(limit: int = 128, *, empty: bool = False) -> dict[str, Any]:
    return {"type": "string", "minLength": 0 if empty else 1, "maxLength": limit}


def _integer(maximum: int = 2**63 - 1, minimum: int = 0) -> dict[str, Any]:
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def _number(maximum: float) -> dict[str, Any]:
    return {"type": "number", "minimum": 0, "maximum": maximum}


def _enum(*values: str) -> dict[str, Any]:
    return {"enum": list(values), "type": "string"}


def _array(items: dict[str, Any], maximum: int, minimum: int = 0) -> dict[str, Any]:
    return {"type": "array", "items": items, "maxItems": maximum, "minItems": minimum}


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/$defs/{name}"}


def _reject_constant(value: str) -> None:
    raise ContractError(f"Nonfinite JSON number: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def json_object(value: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Decode bounded, finite JSON, including callers already holding a dict."""
    try:
        if isinstance(value, (str, bytes)):
            if len(value.encode("utf-8") if isinstance(value, str) else value) > MAX_JSON_BYTES:
                raise ContractError("JSON input exceeds 1 MiB")
            result = json.loads(value, parse_constant=_reject_constant, object_pairs_hook=_pairs)
        elif type(value) is dict:
            data = json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"))
            if len(data.encode()) > MAX_JSON_BYTES:
                raise ContractError("JSON input exceeds 1 MiB")
            result = json.loads(data, object_pairs_hook=_pairs)
        else:
            raise ContractError("Expected a JSON object")
        if type(result) is not dict:
            raise ContractError("Expected a JSON object")
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError(f"Invalid JSON: {exc}") from exc


def validate_json(value: dict[str, Any], schema: dict[str, Any]) -> None:
    """JSON Schema rejects booleans as integers; additionally reject 1.0 as int."""
    try:
        Draft202012Validator(schema).validate(value)
        _strict_numbers(value, schema, schema)
    except ValidationError as exc:
        # jsonschema exceptions retain paths but are intentionally not public API.
        path = ".".join(map(str, exc.absolute_path)) or "record"
        raise ContractError(f"{path}: {exc.message}") from exc



def canonical(value: dict[str, Any]) -> str:
    """Canonical finite JSON for hashing, never shell quoting or authority."""
    return json.dumps(json_object(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)

def _strict_numbers(value: Any, node: dict[str, Any], root: dict[str, Any]) -> None:
    if "$ref" in node:
        node = root["$defs"][node["$ref"].rsplit("/", 1)[1]]
    if "anyOf" in node:
        if value is None:
            return
        node = node["anyOf"][0]
        if "$ref" in node:
            node = root["$defs"][node["$ref"].rsplit("/", 1)[1]]
    if node.get("type") == "integer" and type(value) is not int:
        raise ContractError("Integer fields require integers, not booleans or floats")
    if isinstance(value, dict):
        for key, child in value.items():
            _strict_numbers(child, node.get("properties", {}).get(key, {}), root)
    elif isinstance(value, list):
        for child in value:
            _strict_numbers(child, node.get("items", {}), root)


def _encode(value: Any) -> Any:
    if isinstance(value, _Value):
        result = {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
        if isinstance(value, Record):
            result = {"schema": VERSION, "record_type": type(value).__name__, **result}
        return result
    if isinstance(value, tuple):
        return [_encode(child) for child in value]
    return value


def _immutable(value: Any) -> None:
    if isinstance(value, (dict, list, set)):
        raise ContractError("Records require typed immutable nested values")
    if isinstance(value, tuple):
        for child in value:
            _immutable(child)


class _Value:
    """Shared validation for records and typed nested values."""
    def __post_init__(self) -> None:
        # Constructor inputs must themselves be immutable typed values.
        for field in fields(self):
            value = getattr(self, field.name)
            _immutable(value)
        validate_json(json_object(_encode(self)), _schema(type(self).__name__))
        self._invariants()

    def _invariants(self) -> None:
        pass


class Record(_Value):
    schema: ClassVar[str] = VERSION

    def to_dict(self) -> dict[str, Any]:
        # Frozen values and their nested inputs were validated at construction.
        # Encoding returns fresh containers; raw input still goes through from_dict.
        return _encode(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | str | bytes) -> Self:
        result = json_object(value)
        validate_json(result, _schema(cls.__name__))
        return _decode(cls, result)


@dataclass(frozen=True)
class Budgets(_Value):
    primitives: int = 8
    primitives_per_stage: int = 4
    turns: int = 32
    wall_seconds: float = 120.0
    planner_calls: int = 10
    planner_call_seconds: float = 30.0
    primitive_wait_seconds: float = 15.0
    spend_usd: float = 0.0


@dataclass(frozen=True)
class Progress(_Value):
    verified_steps: int
    displacement: Vector


@dataclass(frozen=True)
class TaskSpec(Record):
    task_id: str
    session: str
    origin: Vector
    direction: Direction
    distance: int
    target: Vector
    task_version: int
    budgets: Budgets
    operator_request_id: str
    kind: Literal["waypoint_return"] = "waypoint_return"

    def _invariants(self) -> None:
        delta = DIRECTIONS[self.direction]
        expected = tuple(p + d * self.distance for p, d in zip(self.origin, delta))
        if self.target != expected:
            raise ContractError("Task target must equal origin plus cardinal distance")


@dataclass(frozen=True)
class EvidenceRef(Record):
    observation_id: str
    session: str
    revision: int
    timestamp_ms: int
    received_monotonic: float
    turn: int | None
    frame_path: str
    frame_sha256: str
    boundary_kind: BoundaryKind
    visibility_version: Literal["cdda-visible/1"] = VISIBILITY_VERSION

    def _invariants(self) -> None:
        if self.boundary_kind == "normal_play" and self.turn is None:
            raise ContractError("Normal scene reference requires observed game time")
        if self.boundary_kind != "normal_play" and self.turn is not None:
            raise ContractError("Non-scene reference cannot manufacture game time")


@dataclass(frozen=True)
class Fact(_Value):
    name: str
    value: str
    evidence: EvidenceRef
    tag: Literal["fact"] = "fact"


@dataclass(frozen=True)
class Interpretation(_Value):
    text: str
    sources: tuple[EvidenceRef, ...]
    tag: Literal["interpretation"] = "interpretation"


@dataclass(frozen=True)
class EvidencePacket(Record):
    task_id: str
    plan_id: str
    stage_id: str
    current: EvidenceRef
    start: EvidenceRef
    waypoint: EvidenceRef | None
    last_primitive_id: str | None
    transport_disposition: TransportDisposition | None
    observed_displacement: Vector | None
    stop_reason: str | None
    remaining_budgets: Budgets
    facts: tuple[Fact, ...]
    interpretations: tuple[Interpretation, ...]

    def _invariants(self) -> None:
        if (self.last_primitive_id is None) != (self.transport_disposition is None):
            raise ContractError("Primitive identity and transport disposition must appear together")
        references = (self.start,) + ((self.waypoint,) if self.waypoint else ())
        if any(ref.session != self.current.session for ref in references):
            raise ContractError("Task evidence must share its world session")


@dataclass(frozen=True)
class SkillDescriptor(Record):
    skill_id: str
    skill_version: int
    task_kinds: tuple[Literal["waypoint_return"], ...]
    stage_kinds: tuple[Stage, ...]
    contexts: tuple[Literal["normal_play"], ...]
    action_bindings: tuple[str, ...]
    observable_predicates: tuple[str, ...]
    allowed_primitives: tuple[str, ...]
    postconditions: tuple[str, ...]
    stop_rules: tuple[str, ...]
    maximum_budgets: Budgets


@dataclass(frozen=True)
class PlanCandidate(Record):
    candidate_id: str
    task_id: str
    task_version: int
    plan_id: str
    plan_version: int
    execution_epoch: int
    evidence_session: str
    evidence_revision: int
    stage: Stage
    direction: Direction
    distance_remaining: int
    skill_id: str
    skill_version: int
    reason: str

    def check_binding(self, task: TaskSpec, evidence: EvidenceRef, *, plan_id: str,
                      plan_version: int, execution_epoch: int, skill: SkillDescriptor) -> None:
        """Check candidate data against explicitly supplied authority; grant no lease."""
        actual = (self.task_id, self.task_version, self.plan_id, self.plan_version,
                  self.execution_epoch, self.evidence_session, self.evidence_revision,
                  self.skill_id, self.skill_version)
        expected = (task.task_id, task.task_version, plan_id, plan_version, execution_epoch,
                    evidence.session, evidence.revision, skill.skill_id, skill.skill_version)
        if actual != expected or evidence.session != task.session:
            raise ContractError("Candidate binding is stale or mismatched")
        direction = task.direction
        if self.stage == "return":
            direction = {"north": "south", "south": "north", "west": "east", "east": "west"}[direction]
        if (self.direction != direction or self.distance_remaining > task.distance
                or self.stage not in skill.stage_kinds or task.kind not in skill.task_kinds):
            raise ContractError("Candidate exceeds the declared task or skill route")


@dataclass(frozen=True)
class PrimitiveResult(Record):
    action_id: str
    before: EvidenceRef
    after: EvidenceRef | None
    transport_disposition: TransportDisposition
    observed_displacement: Vector | None
    reason: str

    def _invariants(self) -> None:
        if self.transport_disposition == "returned" and self.after is None:
            raise ContractError("Returned primitive requires after evidence")
        if self.after is not None and self.after.session != self.before.session:
            # A new-world frame may explain why the old action is unresolved,
            # but cannot attribute displacement or a returned outcome to it.
            if self.transport_disposition != "unknown" or self.observed_displacement is not None:
                raise ContractError("New-world evidence is context only for an unknown old-world primitive")
        if self.observed_displacement is not None:
            if self.after is None:
                raise ContractError("Displacement requires after evidence")


@dataclass(frozen=True)
class StageResult(Record):
    stage_id: str
    stage_version: int
    disposition: Literal["completed", "blocked", "interrupted", "budget_exhausted", "failed", "unknown"]
    progress: Progress
    evidence: tuple[EvidenceRef, ...]
    pending_action_id: str | None

    def _invariants(self) -> None:
        if self.disposition == "completed" and (self.pending_action_id is not None or not self.evidence):
            raise ContractError("Completion requires evidence and no unresolved action")


@dataclass(frozen=True)
class RunStatus(Record):
    task_id: str | None
    plan_id: str | None
    stage_id: str | None
    execution_epoch: int
    state: Literal["idle", "planning", "admitted", "executing", "verifying", "completed", "blocked", "interrupted", "budget_exhausted", "failed", "unknown", "paused", "abandoned"]
    model_id: str | None
    configuration_id: str | None
    skill_id: str | None
    skill_version: int | None
    progress: Progress
    remaining_budgets: Budgets
    next_check: str
    last_public_reason: str
    lease_owner: str | None
    paused: bool
    fresh: bool
    evidence: tuple[EvidenceRef, ...]

    def _invariants(self) -> None:
        if (self.skill_id is None) != (self.skill_version is None):
            raise ContractError("Skill identity requires a version")


_ID = _text()
_INT = _integer()
_VERSION = _integer(2**31 - 1, 1)
_VECTOR = _array(_integer(2**31 - 1, -(2**31)), 3, 3)
_DIRECTION = _enum(*DIRECTIONS)
_STAGE = _enum("outbound", "return")
_TRANSPORT = _enum("not_dispatched", "dispatched", "returned", "rejected", "unknown")
_BOUNDARY = _enum("normal_play", "activity_poll", "interrupt_confirmation", "debug_prompt", "menu", "unsupported")
_DEFS = {
    "Budgets": _object({"primitives": _integer(8), "primitives_per_stage": _integer(4),
                        "turns": _integer(32), "wall_seconds": _number(120),
                        "planner_calls": _integer(10), "planner_call_seconds": _number(30),
                        "primitive_wait_seconds": _number(15), "spend_usd": _number(1_000_000)}),
    "Progress": _object({"verified_steps": _integer(8), "displacement": _VECTOR}),
    "TaskSpec": _object({"task_id": _ID, "session": _ID, "origin": _VECTOR,
                         "direction": _DIRECTION, "distance": _integer(4, 1), "target": _VECTOR,
                         "task_version": _VERSION, "budgets": _ref("Budgets"),
                         "operator_request_id": _ID, "kind": {"const": "waypoint_return"}}),
    "EvidenceRef": _object({"observation_id": _ID, "session": _ID, "revision": _INT,
                            "timestamp_ms": _INT, "received_monotonic": _number(1e15),
                            "turn": _nullable(_integer(2**31 - 1, -(2**31))), "frame_path": _text(4096),
                            "frame_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                            "boundary_kind": _BOUNDARY,
                            "visibility_version": {"const": VISIBILITY_VERSION}}),
    "Fact": _object({"name": _ID, "value": _text(1024, empty=True), "evidence": _ref("EvidenceRef"),
                     "tag": {"const": "fact"}}),
    "Interpretation": _object({"text": _text(1024), "sources": _array(_ref("EvidenceRef"), 32, 1),
                               "tag": {"const": "interpretation"}}),
    "EvidencePacket": _object({"task_id": _ID, "plan_id": _ID, "stage_id": _ID,
                               "current": _ref("EvidenceRef"), "start": _ref("EvidenceRef"),
                               "waypoint": _nullable(_ref("EvidenceRef")),
                               "last_primitive_id": _nullable(_ID),
                               "transport_disposition": _nullable(_TRANSPORT),
                               "observed_displacement": _nullable(_VECTOR),
                               "stop_reason": _nullable(_text(1024)),
                               "remaining_budgets": _ref("Budgets"),
                               "facts": _array(_ref("Fact"), 64),
                               "interpretations": _array(_ref("Interpretation"), 32)}),
    "SkillDescriptor": _object({"skill_id": _ID, "skill_version": _VERSION,
                                "task_kinds": _array({"const": "waypoint_return"}, 1, 1),
                                "stage_kinds": _array(_STAGE, 2, 1),
                                "contexts": _array({"const": "normal_play"}, 1, 1),
                                **{name: _array(_text(256), 32, 1) for name in
                                   ("action_bindings", "observable_predicates", "allowed_primitives",
                                    "postconditions", "stop_rules")},
                                "maximum_budgets": _ref("Budgets")}),
    "PlanCandidate": _object({"candidate_id": _ID, "task_id": _ID, "task_version": _VERSION,
                              "plan_id": _ID, "plan_version": _VERSION, "execution_epoch": _INT,
                              "evidence_session": _ID, "evidence_revision": _INT, "stage": _STAGE,
                              "direction": _DIRECTION, "distance_remaining": _integer(4, 1),
                              "skill_id": _ID, "skill_version": _VERSION, "reason": _text(1024)}),
    "PrimitiveResult": _object({"action_id": _ID, "before": _ref("EvidenceRef"),
                                "after": _nullable(_ref("EvidenceRef")),
                                "transport_disposition": _TRANSPORT,
                                "observed_displacement": _nullable(_VECTOR), "reason": _text(1024)}),
    "StageResult": _object({"stage_id": _ID, "stage_version": _VERSION,
                            "disposition": _enum("completed", "blocked", "interrupted", "budget_exhausted", "failed", "unknown"),
                            "progress": _ref("Progress"), "evidence": _array(_ref("EvidenceRef"), 32),
                            "pending_action_id": _nullable(_ID)}),
    "RunStatus": _object({"task_id": _nullable(_ID), "plan_id": _nullable(_ID), "stage_id": _nullable(_ID),
                          "execution_epoch": _INT,
                          "state": _enum("idle", "planning", "admitted", "executing", "verifying", "completed", "blocked", "interrupted", "budget_exhausted", "failed", "unknown", "paused", "abandoned"),
                          "model_id": _nullable(_ID), "configuration_id": _nullable(_ID),
                          "skill_id": _nullable(_ID), "skill_version": _nullable(_VERSION),
                          "progress": _ref("Progress"), "remaining_budgets": _ref("Budgets"),
                          "next_check": _text(1024, empty=True), "last_public_reason": _text(1024, empty=True),
                          "lease_owner": _nullable(_ID), "paused": {"type": "boolean"},
                          "fresh": {"type": "boolean"}, "evidence": _array(_ref("EvidenceRef"), 32)}),
}
_RECORDS = (TaskSpec, EvidenceRef, EvidencePacket, SkillDescriptor, PlanCandidate,
            PrimitiveResult, StageResult, RunStatus)
for _record in _RECORDS:
    _definition = _DEFS[_record.__name__]
    _definition["properties"].update(schema={"const": VERSION}, record_type={"const": _record.__name__})
    _definition["required"] += ["schema", "record_type"]


def _schema(name: str) -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": f"#/$defs/{name}", "$defs": _DEFS}


def record_schema(record_type: type[Record]) -> dict[str, Any]:
    """Return an independent schema for external validation without mutable globals."""
    if record_type not in _RECORDS:
        raise ContractError("Unknown gameplay record type")
    return json.loads(json.dumps(_schema(record_type.__name__)))


_NESTED = {"budgets": Budgets, "remaining_budgets": Budgets, "maximum_budgets": Budgets,
           "progress": Progress, "current": EvidenceRef, "start": EvidenceRef, "waypoint": EvidenceRef,
           "before": EvidenceRef, "after": EvidenceRef, "evidence": EvidenceRef,
           "facts": Fact, "interpretations": Interpretation, "sources": EvidenceRef}


def _decode(cls: type, value: dict[str, Any]) -> Any:
    values: dict[str, Any] = {}
    for field in fields(cls):
        child = value[field.name]
        nested = _NESTED.get(field.name)
        if nested and child is not None:
            if isinstance(child, list):
                child = tuple(_decode(nested, item) for item in child)
            else:
                child = _decode(nested, child)
        elif isinstance(child, list):
            child = tuple(child)
        values[field.name] = child
    return cls(**values)
