"""Structured player adapter; the existing mission ingress remains the executor.

Handles are bounded process-local copies of explicitly returned status/sources.
They confer no authority, survive no restart and never silently refresh a choice.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import threading
import time
import uuid

from .gameplay.contracts import ContractError, _object, canonical, json_object, validate_json
from .gameplay.evidence import same_native_state
from .gameplay.mission_contracts import (
    VERSION, SKILLS, perception_schema, request_schema, validate_request,
)
from .gameplay.mission_requests import compose_request
from .gameplay.reflection import (
    MAX_REFLECTION_READ_WAIT_SECONDS, proposal_schema, validate_command, validate_job, validate_proposal,
)
from .mission_client import MissionClient


DETAIL_SECTIONS = ("configuration", "metrics", "receipt", "progress", "native", "source")


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
        ToolSpec("enactive_detail", "Read one exact cached snapshot section as of its original read. Never refreshes status, reads a source image, retargets a snapshot or grants authority; explicitly obtain a new snapshot if its handle is unavailable.",
            _object(dict(snapshot_id=identity, section={"enum": list(DETAIL_SECTIONS)})), True),
        ToolSpec("enactive_source", "Read one explicitly selected historical source and its actual image; grants no input authority.", _object(dict(mission_id=identity, source_id=identity)), True),
        ToolSpec("enactive_result", "Collect only the original operation ID, including after interrupted submission. Never replays input.", _object(dict(mission_id=identity, operation_id=identity, wait_seconds=wait)), True),
        ToolSpec("enactive_skill", "Choose ordinary physical input (skill_kind=direct) or a semantic skill with an explicit returned snapshot/source and finite limits. Direct keys/scalars permit visual drift under owned custody; clicks keep original geometry. Semantic preconditions remain strict. Software retains lineage and collects delivery and actual current evidence separately.", skill),
        ToolSpec("enactive_lifecycle", "Explicit registered launch/create/save/exit/load/finish. With no owned child, first launch using scope=new_root and source_id=null; then choose create/load from its returned menu. Continue a returned lifecycle phase with scope=lifecycle and the same operation, including transition reconciliation, identity readmission and adoption. No implicit Resume, save or restart.", lifecycle),
        ToolSpec("enactive_observe", "Request one typed native observation using the chosen snapshot epoch. A healthy ordinary prompt may advance or record local macro_closure without task success or renewed mission allowance; explicitly choose any next root from fresh evidence. Does not Resume or reconcile unknown delivery. After known direct input with absent/aged current evidence, explicit Observe can refresh its read-only scope across the exact authenticated operation rotation; input requires the fresh binding. It never restores failed custody or renews limits.", _object(common)),
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
            "Pause the current mission/control; does not terminate the owned game or prove normal Finish. Original costs and uncertainty remain."
            if kind == "stop" else
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
    specs.append(ToolSpec("enactive_readmit", "Explicit recovery/handoff readmission from one selected returned source, not lifecycle continuation. A create/load/save lifecycle uses enactive_lifecycle with scope=lifecycle and the same operation, including identity readmission. Never implicit recovery or Resume.",
        _object({**common, "source_id": identity, "intent": {"anyOf": readmit}})))
    context = _without(request_schema("context", handoff=True), "schema", "kind", "mission_id")
    context["properties"]["scope"] = _without(context["properties"]["scope"], "mission_id")
    specs.append(ToolSpec("enactive_context", "Retrieve complete current memory/provenance; choose explicit successor binding for required Work. Does not claim or Resume.",
        _object(dict(snapshot_id=identity, intent=context)), True))
    proposal = proposal_schema()["properties"]
    reflection_scope = dict(mission_id=identity, reflector_id=identity)
    specs.extend((
        ToolSpec("enactive_reflect_next", "Advisory actor only: get and durably claim bounded original work. Compute only when status is claimed. Pending, busy or unknown grants no permission to compute; no gameplay input or automatic model work.",
            _object({**reflection_scope, "wait_seconds": {**wait, "maximum": MAX_REFLECTION_READ_WAIT_SECONDS}})),
        ToolSpec("enactive_reflect_submit", "Advisory actor only: submit explicitly authored candidates/notes/reason for a cached claimed job. Software preserves original headers; request_id is immutable. Corrected output requires a new request_id. No automatic memory adoption or gameplay.",
            _object({**reflection_scope, "job_id": identity, "request_id": identity, "wait_seconds": wait,
                **{field: proposal[field] for field in ("candidates", "notes", "reason")}})),
        ToolSpec("enactive_reflect_source", "Advisory actor only: read an allowlisted original image from a cached claimed job. Never Observe; this presentation cannot serve as a deciding player's source-read declaration.",
            _object({**reflection_scope, "job_id": identity, "source_id": identity}), True),
        ToolSpec("enactive_reflect_result", "Collect an original advisory command by its stable ID, including after adapter restart. Never submits or claims work; unavailable remains unknown.",
            _object({**reflection_scope, "command_id": identity, "wait_seconds": wait}), True),
        ToolSpec("enactive_advice", "Deciding player: passively read one exact advisory proposal. Missing is explicit; proposal data grants no current authority and is never automatically accepted.",
            _object(dict(mission_id=identity, proposal_id=identity)), True),
    ))
    return tuple(specs)


class PlayerTools:
    """One adapter, bounded descriptive handles, no controller capability."""
    def __init__(self, client: MissionClient):
        self.client = client
        self.snapshots: OrderedDict[str, dict] = OrderedDict()
        self.sources: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self.specs = {spec.name: spec for spec in tool_specs()}
        self._lock = threading.Lock()
        self._last_image: tuple[str, str, int, str, str] | None = None
        self._reflection_lock = threading.Lock()
        self._reflection_jobs: OrderedDict[tuple[str, str, str], dict] = OrderedDict()

    @staticmethod
    def _remember(cache: OrderedDict, key, value):
        cache[key] = deepcopy(value)
        cache.move_to_end(key)
        while len(cache) > 32:
            cache.popitem(last=False)

    def _cached_snapshot(self, identity: str) -> dict:
        if identity not in self.snapshots:
            raise ContractError("Snapshot handle unavailable; explicitly read a new snapshot")
        return deepcopy(self.snapshots[identity])

    def _snapshot(self, identity: str) -> dict:
        return self._cached_snapshot(identity)["mission"]

    def detail(self, identity: str, section: str) -> dict:
        snapshot = self._cached_snapshot(identity)
        if section in ("native", "source"):
            detail = snapshot.get(section)
        else:
            field = "last_receipt" if section == "receipt" else section
            detail = snapshot["mission"].get(field)
        return dict(snapshot_id=identity, section=section, detail=detail, grants_authority=False)

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
            output.update(snapshot_id=identity, mission=snapshot)
            selected = snapshot.get("current_source")
            if selected is not None:
                try:
                    output["source"], image = self.source(snapshot["mission_id"], selected["observation_id"])
                except (OSError, ValueError) as exc:
                    output["source_error"] = str(exc)[:1024]
            self._remember(self.snapshots, identity, output)
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

    @staticmethod
    def _image_context(snapshot: dict | None, image: bytes | None) -> tuple[str, str, int, str, str] | None:
        """One presentation fingerprint, never a source-read or authority proof."""
        if snapshot is None or image is None:
            return None
        mission, native, source = (snapshot.get(key) for key in ("mission", "native", "source"))
        if not all(isinstance(value, dict) for value in (mission, native, source)):
            return None
        state, observed = native.get("state"), source.get("observation")
        reference, selected = source.get("reference"), mission.get("current_source")
        if not all(isinstance(value, dict) for value in (state, observed, reference, selected)):
            return None
        if (not all(isinstance(mission.get(key), str) and mission[key] for key in ("mission_id", "player_id", "phase"))
                or mission.get("actor_id") != mission["player_id"]
                or type(mission.get("epoch")) is not int or mission["epoch"] < 0
                or mission.get("clock_valid") is not True or snapshot.get("source_error")
                or source.get("disposition") != "retained" or source.get("grants_authority") is not False
                or not reference.get("observation_id") or selected.get("observation_id") != reference["observation_id"]
                or native.get("connection") != "fresh" or native.get("error")
                or state.get("status") != "ready" or state.get("error") or state.get("frame_ok") is not True
                or not same_native_state(state, observed)
                or not observed.get("session") or type(observed.get("revision")) is not int
                or reference.get("session") != observed["session"] or reference.get("revision") != observed["revision"]):
            return None
        # Reuse the native equivalence policy: every semantic/control field is
        # relevant, while transport/capture identities do not change the scene.
        context = {**native, "state": {key: value for key, value in state.items()
            if key not in ("id", "timestamp_ms", "frame")},
            "mission_phase": mission["phase"], "pause_cause": mission.get("pause_cause")}
        return (mission["mission_id"], mission["player_id"], mission["epoch"],
            hashlib.sha256(canonical(context).encode()).hexdigest(), hashlib.sha256(image).hexdigest())

    def _present_image(self, output: dict, image: bytes | None, *, explicit: bool) -> tuple[dict, bytes | None]:
        snapshot = output if explicit else output.get("next_snapshot")
        context = self._image_context(snapshot, image)
        duplicate = context is not None and context == self._last_image
        self._last_image = context
        if duplicate and not explicit:
            # This note belongs only to the returned envelope, never its exact
            # cached snapshot/source or any handoff source-read declaration.
            output["image_presentation"] = (
                "Actual image pixels are unchanged from the last image shown in this player context. "
                "Use enactive_snapshot or enactive_source to redisplay the actual image. "
                "This omission is presentation only, not a source-read declaration.")
            return output, None
        return output, image

    def call(self, name: str, arguments: dict) -> tuple[dict, bytes | None]:
        if name not in self.specs:
            raise ContractError("Unknown player tool")
        data = json_object(arguments)
        validate_json(data, self.specs[name].schema)
        if name in ("enactive_reflect_next", "enactive_reflect_submit", "enactive_reflect_source", "enactive_reflect_result", "enactive_advice"):
            return self._reflection_call(name, data)
        if not self._lock.acquire(blocking=False):
            raise ContractError("Another player tool is active; collect its original operation before continuing")
        try:
            if name == "enactive_source":
                # Historical sources carry no current player/epoch context.
                self._last_image = None
            output, image = self._call(name, data)
            if name == "enactive_snapshot":
                return self._present_image(output, image, explicit=True)
            if name != "enactive_source" and name != "enactive_detail":
                return self._present_image(output, image, explicit=False)
            return output, image
        except (OSError, ValueError):
            self._last_image = None
            raise
        finally:
            self._lock.release()

    @staticmethod
    def _claim_id(mission_id: str, job_id: str) -> str:
        return "claim-" + hashlib.sha256((mission_id + "\0" + job_id).encode()).hexdigest()

    def _reflection_job(self, mission_id: str, reflector_id: str, job_id: str) -> dict:
        with self._reflection_lock:
            original = self._reflection_jobs.get((mission_id, reflector_id, job_id))
            if original is None:
                raise ContractError("Original claimed job handle unavailable; explicitly retrieve and verify its durable claim")
            return deepcopy(original)

    @staticmethod
    def _claim_wrapper(job: dict, receipt: dict, command_id: str) -> dict:
        if (receipt.get("status") != "committed" or receipt.get("admitted") is not True
                or receipt.get("command_id") != command_id or receipt.get("grants_authority") is not False):
            raise ContractError("Reflection claim requires its original committed receipt")
        result = receipt.get("result")
        number = {"type": "number", "minimum": 0}
        validate_json(result, _object(dict(job_id={"const": job["id"]}, state={"const": "claimed"},
            claimed_at=number, deadline=number, charged_seconds={"type": "number", "exclusiveMinimum": 0, "maximum": 180},
            measurement={"type": "string", "maxLength": 1024}, grants_authority={"const": False})))
        if result["deadline"] != result["claimed_at"] + result["charged_seconds"]:
            raise ContractError("Reflection claim changed its original window/deadline")
        return dict(job=job, state="claimed", claimed_at=result["claimed_at"], deadline=result["deadline"])

    def _reflection_call(self, name: str, data: dict) -> tuple[dict, bytes | None]:
        # Every network/wait/image operation is outside both cache and active
        # input locks. Only short immutable-handle copies take the cache lock.
        if name == "enactive_advice":
            return self.client.reflection_advice(**data), None
        if name == "enactive_reflect_result":
            return self.client.reflection_collect(**data), None
        mission_id, reflector_id = data["mission_id"], data["reflector_id"]
        if name == "enactive_reflect_next":
            deadline = time.monotonic() + data["wait_seconds"]
            offered = self.client.reflection_next(mission_id, reflector_id, wait_seconds=data["wait_seconds"])
            if offered["status"] in ("idle", "closed"):
                return offered, None
            job = validate_job(offered["job"]["job"])
            if (job["mission_id"], job["reflector_id"]) != (mission_id, reflector_id):
                raise ContractError("Reflection job belongs to another mission/reflector")
            identity = self._claim_id(mission_id, job["id"])
            wait = min(15., max(0., deadline - time.monotonic()))
            if offered["status"] == "claimed":
                claim = self.client.reflection_collect(mission_id, reflector_id, identity, wait_seconds=wait)
            else:
                command = validate_command(dict(schema="reflection/2", kind="claim", command_id=identity,
                    mission_id=mission_id, reflector_id=reflector_id, job_id=job["id"]))
                claim = self.client.reflection_command(command, wait_seconds=wait)
            if claim["status"] != "committed":
                # Do not leak an offered packet as permission to start compute.
                return claim, None
            if claim.get("result", {}).get("status") == "rejected":
                validate_json(claim["result"], _object(dict(status={"const": "rejected"},
                    reason={"type": "string", "minLength": 1, "maxLength": 1024}, grants_authority={"const": False})))
                return claim, None
            wrapper = self._claim_wrapper(job, claim, identity)
            if offered["status"] == "claimed" and wrapper != offered["job"]:
                raise ContractError("Reflection job wrapper differs from its original claim")
            output = dict(status="claimed", job=wrapper, claim=claim, grants_authority=False)
            key = (mission_id, reflector_id, job["id"])
            with self._reflection_lock:
                previous = self._reflection_jobs.get(key)
                if previous is not None and previous != output:
                    raise ContractError("Conflicting immutable reflection job/claim handle")
                self._reflection_jobs[key] = deepcopy(output)
                self._reflection_jobs.move_to_end(key)
                while len(self._reflection_jobs) > 64:
                    self._reflection_jobs.popitem(last=False)
            return output, None
        original = self._reflection_job(mission_id, reflector_id, data["job_id"])
        job = original["job"]["job"]
        if name == "enactive_reflect_source":
            if dict(mission_id=mission_id, source_id=data["source_id"]) not in job["sources"]:
                raise ContractError("Reflection source is outside the original claimed job allowlist")
            # Deliberately bypass source(), which populates player presentation
            # handles used by active-input and fresh-context handoff contracts.
            return self.client.reflection_source(mission_id, reflector_id, job["id"], data["source_id"])
        proposal = validate_proposal(dict(schema="reflection/2", record_type="ReflectionProposal",
            id="proposal-" + hashlib.sha256(data["request_id"].encode()).hexdigest(),
            job_id=job["id"], mission_id=job["mission_id"], reflector_id=job["reflector_id"],
            epoch=job["epoch"], cutoff_sequence=job["through_sequence"], memory_version=job["memory_version"],
            **{field: data[field] for field in ("candidates", "notes", "reason")}), job)
        command = validate_command(dict(schema="reflection/2", kind="submit", command_id=data["request_id"],
            mission_id=mission_id, reflector_id=reflector_id, job_id=job["id"], proposal=proposal))
        return self.client.reflection_command(command, wait_seconds=data["wait_seconds"]), None

    def _call(self, name: str, data: dict) -> tuple[dict, bytes | None]:
        if name == "enactive_start":
            request = validate_request(dict(schema=VERSION, kind="start", request_id=data["request_id"], admission=data["admission"]))
            return self._finish(self.client.submit(request, wait_seconds=data["wait_seconds"]))
        if name == "enactive_snapshot":
            return self.snapshot()
        if name == "enactive_detail":
            return self.detail(data["snapshot_id"], data["section"]), None
        if name == "enactive_source":
            return self.source(data["mission_id"], data["source_id"])
        if name == "enactive_result":
            return self._finish(self.client.collect(**data))
        snapshot = self._snapshot(data["snapshot_id"])
        kind = name.removeprefix("enactive_")
        if (kind == "lifecycle" and data["intent"]["operation"] in ("create", "load")
                and data["source_id"] is None and snapshot["phase"] == "admitted"
                and snapshot["current_source"] is None
                and snapshot["native_process"]["last_sample"] is None):
            raise ContractError("Selected admission has no owned game launch or current source. "
                "First use enactive_lifecycle, scope=new_root, operation=launch, source_id=null; "
                "then choose create/load from its returned menu. No request was submitted; "
                "this as-of guidance grants no authority or renewed limits.")
        if kind == "readmit" and snapshot.get("lifecycle_phase") is not None:
            phase = snapshot["lifecycle_phase"]
            raise ContractError(f"Selected snapshot has a {phase['operation']} lifecycle phase. "
                f"Continue with enactive_lifecycle, scope=lifecycle, operation={phase['operation']}; "
                "not recovery/handoff readmission. No request was submitted; "
                "this as-of guidance grants no authority or renewed limits.")
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
