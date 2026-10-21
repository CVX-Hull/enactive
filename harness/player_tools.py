"""Structured player adapter; the existing mission ingress remains the executor.

Handles are bounded process-local copies of explicitly returned status/sources.
They confer no authority, survive no restart and never silently refresh a choice.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import threading
import uuid

from .gameplay.contracts import ContractError, _object, json_object, validate_json
from .gameplay.mission_contracts import (
    VERSION, SKILLS, perception_schema, request_schema, validate_request,
)
from .gameplay.mission_requests import compose_request
from .mission_client import MissionClient


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict
    read_only: bool = False


def _without(schema: dict, *names: str) -> dict:
    value = deepcopy(schema)
    for name in names:
        value["properties"].pop(name, None)
    value["required"] = list(value["properties"])
    return value


def tool_specs() -> tuple[ToolSpec, ...]:
    """Derive semantic shapes from the receiver, never a parallel wire schema."""
    base = request_schema("observe")["properties"]
    identity = base["request_id"]
    nullable_id = {"anyOf": [identity, {"type": "null"}]}
    wait = {"type": "number", "minimum": 0, "maximum": 15}
    refs = request_schema("skill", skill_kind="inspect")["properties"]["sources"]
    common = dict(snapshot_id=identity, request_id=identity, wait_seconds=wait)
    headers = ("schema", "request_id", "mission_id", "epoch")
    ordinary_headers = (*headers, "limits", "phase_id", "sources", "expected_session",
                        "expected_revision", "expected_boundary_id", "kind")
    perception = perception_schema()
    perception["anyOf"] = [value if value.get("type") == "null" else
        _without(value, "source_id", "basis") for value in perception["anyOf"]]
    skill_intents = []
    for kind in SKILLS:
        schema = _without(request_schema("skill", skill_kind=kind), *ordinary_headers)
        schema["properties"]["perception"] = {"$ref": "#/$defs/perception"}
        schema["properties"]["procedure"]["anyOf"] = [value if value.get("type") == "null" else
            _without(value, "use_id") for value in schema["properties"]["procedure"]["anyOf"]]
        skill_intents.append(schema)
    skill = _object({**common, "scope": {"enum": ["new_root", "prompt", "lifecycle", "activity"]},
        "source_id": nullable_id, "supporting_source_ids": refs,
        "limits": request_schema("skill", skill_kind="inspect")["properties"]["limits"],
        "intent": {"anyOf": skill_intents}})
    skill["$defs"] = {"perception": perception}
    lifecycle = _object({**common, "scope": {"enum": ["new_root", "lifecycle"]},
        "source_id": nullable_id, "supporting_source_ids": refs,
        "limits": request_schema("lifecycle")["properties"]["limits"],
        "intent": _without(request_schema("lifecycle"), *ordinary_headers)})
    specs = [
        ToolSpec("enactive_start", "Lead-only explicit frozen mission admission. Supply the reviewed complete admission; no implicit launch, adoption or allowance extension.",
            _object({**_without(request_schema("start"), "schema", "kind")["properties"], "wait_seconds": wait})),
        ToolSpec("enactive_snapshot", "Read current status and its exact retained image. Returns a new snapshot handle; never Observe or Resume.", _object({}), True),
        ToolSpec("enactive_source", "Read one explicitly selected historical source and its actual image; grants no input authority.", _object(dict(mission_id=identity, source_id=identity)), True),
        ToolSpec("enactive_result", "Collect only the original operation ID, including after interrupted submission. Never replays input.", _object(dict(mission_id=identity, operation_id=identity, wait_seconds=wait)), True),
        ToolSpec("enactive_skill", "Choose a semantic skill using an explicit returned snapshot/source and finite limits. Software derives wire bindings and collects its result.", skill),
        ToolSpec("enactive_lifecycle", "Explicit registered launch/create/save/exit/load/finish. No implicit Resume, save or restart.", lifecycle),
        ToolSpec("enactive_observe", "Request one typed native observation using the chosen snapshot epoch. Does not Resume or reconcile an unknown input automatically.", _object(common)),
    ]
    # These operations keep their existing explicit semantic fields. Software
    # derives only the common envelope; memory provenance remains player-authored.
    for kind in ("remember", "correct"):
        variants = [_without(request_schema(kind, entry_type=entry), *headers, "kind")
                    for entry in (("claim",) if kind == "correct" else ("claim", "work", "decision", "procedure"))]
        specs.append(ToolSpec("enactive_" + kind,
            "Write explicit evidence-linked memory through the existing ledger. No automatic lesson promotion or invented support.",
            _object({**common, "intent": {"anyOf": variants}})))
    for kind in ("handoff", "stop", "reconcile"):
        specs.append(ToolSpec("enactive_" + kind,
            "Explicit " + kind + " through the existing mission state machine; original costs and uncertainty remain.",
            _object({**common, "intent": _without(request_schema(kind), *headers, "kind")})))
    claim = _without(request_schema("claim"), *headers, "kind", "pause_generation", "takeover_generation",
        "expected_session", "expected_revision", "expected_boundary_id", "expected_pause_origin")
    specs.append(ToolSpec("enactive_claim", "Claim a selected issued handoff using explicit packet IDs and truthful source-read declarations. Bindings come from that exact retained issuance.",
        _object({**common, "intent": claim})))
    readmit = []
    for mode in ("handoff", "recovery"):
        readmit.append(_without(request_schema("readmit", mode=mode), *headers, "kind", "sources",
            "expected_session", "expected_revision", "expected_boundary_id"))
    specs.append(ToolSpec("enactive_readmit", "Deliberate separately charged readmission from one selected returned source. Never implicit recovery or Resume.",
        _object({**common, "source_id": identity, "intent": {"anyOf": readmit}})))
    context = _without(request_schema("context", handoff=True), "schema", "kind", "mission_id")
    context["properties"]["scope"] = _without(context["properties"]["scope"], "mission_id")
    specs.append(ToolSpec("enactive_context", "Retrieve complete current memory/provenance; choose explicit successor binding for required Work. Does not claim or Resume.",
        _object(dict(snapshot_id=identity, intent=context)), True))
    return tuple(specs)


class PlayerTools:
    """One adapter, bounded descriptive handles, no controller capability."""
    def __init__(self, client: MissionClient):
        self.client = client
        self.snapshots: OrderedDict[str, dict] = OrderedDict()
        self.sources: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self.specs = {spec.name: spec for spec in tool_specs()}
        self._lock = threading.Lock()

    @staticmethod
    def _remember(cache: OrderedDict, key, value):
        cache[key] = deepcopy(value)
        cache.move_to_end(key)
        while len(cache) > 32:
            cache.popitem(last=False)

    def _snapshot(self, identity: str) -> dict:
        if identity not in self.snapshots:
            raise ContractError("Snapshot handle unavailable; explicitly read a new snapshot")
        return deepcopy(self.snapshots[identity])

    def _source(self, mission_id: str, identity: str | None) -> dict | None:
        if identity is None:
            return None
        if (mission_id, identity) not in self.sources:
            raise ContractError("Read the selected exact source/image before using it; no source substitution")
        return deepcopy(self.sources[(mission_id, identity)])

    def source(self, mission_id: str, identity: str) -> tuple[dict, bytes]:
        metadata, image = self.client.source(mission_id, identity)
        self._remember(self.sources, (mission_id, identity), metadata)
        return metadata, image

    def snapshot(self) -> tuple[dict, bytes | None]:
        raw = self.client.status()
        mission = raw.get("mission")
        native = {key: raw.get(key) for key in ("state", "frozen", "pause_requested", "pause_generation",
            "operator_pause_generation", "pending", "control_pending", "connection", "error")}
        output = dict(snapshot_id=None, mission=None, native=native, source=None, grants_authority=False)
        image = None
        if mission is not None:
            snapshot = {key: value for key, value in mission.items() if key != "memory_context"}
            identity = "s-" + uuid.uuid4().hex
            self._remember(self.snapshots, identity, snapshot)
            output.update(snapshot_id=identity, mission=snapshot)
            selected = snapshot.get("current_source")
            if selected is not None:
                try:
                    output["source"], image = self.source(snapshot["mission_id"], selected["observation_id"])
                except (OSError, ValueError) as exc:
                    output["source_error"] = str(exc)[:1024]
        return output, image

    @staticmethod
    def _compact(envelope: dict) -> dict:
        value = deepcopy(envelope)
        response = value.get("response")
        if response is not None:
            response.pop("mission", None)  # A separately returned next snapshot owns current status.
            operation = response.get("operation")
            if operation is not None:
                request = operation.pop("request", None)
                if request is not None:
                    operation["request_id"] = request["request_id"]
                    operation["kind"] = request["kind"]
        return value

    def _finish(self, envelope: dict) -> tuple[dict, bytes | None]:
        output = self._compact(envelope)
        image = None
        try:
            output["next_snapshot"], image = self.snapshot()
        except (OSError, ValueError) as exc:
            output["snapshot_error"] = str(exc)[:1024]
        return output, image

    def call(self, name: str, arguments: dict) -> tuple[dict, bytes | None]:
        if name not in self.specs:
            raise ContractError("Unknown player tool")
        data = json_object(arguments)
        validate_json(data, self.specs[name].schema)
        if not self._lock.acquire(blocking=False):
            raise ContractError("Another player tool is active; collect its original operation before continuing")
        try:
            return self._call(name, data)
        finally:
            self._lock.release()

    def _call(self, name: str, data: dict) -> tuple[dict, bytes | None]:
        if name == "enactive_start":
            request = validate_request(dict(schema=VERSION, kind="start", request_id=data["request_id"], admission=data["admission"]))
            return self._finish(self.client.submit(request, wait_seconds=data["wait_seconds"]))
        if name == "enactive_snapshot":
            return self.snapshot()
        if name == "enactive_source":
            return self.source(data["mission_id"], data["source_id"])
        if name == "enactive_result":
            return self._finish(self.client.collect(**data))
        snapshot = self._snapshot(data["snapshot_id"])
        kind = name.removeprefix("enactive_")
        if kind == "context":
            intent = data["intent"]
            intent["scope"]["mission_id"] = snapshot["mission_id"]
            request = dict(schema=VERSION, kind=kind, mission_id=snapshot["mission_id"], **intent)
            return self._finish(self.client.submit(validate_request(request), wait_seconds=0))
        identity = data["request_id"]
        intent = deepcopy(data.get("intent", {}))
        if kind in ("skill", "lifecycle"):
            intent["kind"] = kind
            if intent.get("perception") is not None:
                intent["perception"]["basis"] = "player_interpretation"
            source = self._source(snapshot["mission_id"], data["source_id"])
            request = compose_request(snapshot, request_id=identity, intent=intent, limits=data["limits"],
                scope=data["scope"], source=source, supporting_source_ids=data["supporting_source_ids"])
        else:
            if kind == "claim":
                for source in intent["read_procedure_sources"]:
                    self._source(source["mission_id"], source["source_id"])
                issued = self.client.collect(snapshot["mission_id"], intent["handoff_id"], wait_seconds=0)
                operation = (issued.get("response") or {}).get("operation")
                if (issued["transport"] != "delivered" or operation is None
                        or operation["state"] != "completed" or operation["request"]["kind"] != "handoff"):
                    raise ContractError("Select a retained completed handoff issuance")
                binding = operation["result"]
                intent.update(pause_generation=binding["pause_generation"], takeover_generation=binding["takeover_generation"],
                    expected_session=binding["session"], expected_revision=binding["revision"],
                    expected_boundary_id=binding["boundary_id"], expected_pause_origin=binding["pause_origin"])
            elif kind == "readmit":
                selected = self._source(snapshot["mission_id"], data["source_id"])
                reference, observation = selected["reference"], selected["observation"]
                intent.update(sources=[data["source_id"]], expected_session=reference["session"],
                    expected_revision=reference["revision"], expected_boundary_id=observation["boundary"]["id"])
            request = validate_request(dict(schema=VERSION, kind=kind, request_id=identity,
                mission_id=snapshot["mission_id"], epoch=snapshot["epoch"], **intent))
        return self._finish(self.client.submit(request, wait_seconds=data["wait_seconds"]))
