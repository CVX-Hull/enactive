"""Structured player adapter; the existing mission ingress remains the executor.

Handles are bounded process-local copies of explicitly returned status/sources
and canonical procedure results.
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

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .gameplay.contracts import ContractError, _object, canonical, json_object, validate_json
from .gameplay.evidence import same_native_state
from .gameplay.mission_contracts import (
    VERSION, SKILLS, IDENTITY_COVERAGE, IDENTITY_UNIT, MAX_HANDOFF_SOURCES, perception_schema, request_schema, validate_request,
)
from .gameplay.mission_requests import _source_binding, compose_request
from .gameplay.policy_program import program_result_schema
from .gameplay.procedures import author_procedure, procedure_authoring_schema, validate_procedure
from .gameplay.reflection import (
    MAX_REFLECTION_READ_WAIT_SECONDS, proposal_schema, validate_command, validate_job, validate_proposal,
)
from .mission_client import MissionClient


DETAIL_SECTIONS = ("mission", "configuration", "metrics", "receipt", "progress", "native", "source")


class UnsubmittedRequest(ContractError):
    """Pure request validation/composition refused before calling SDK submission."""


def admission_refusal_feedback(envelope: dict) -> dict | None:
    """Copy only the SDK's validated outcome, never infer it from a reason/proof."""
    if (envelope.get("submission") != "not_admitted" or envelope.get("settled") is not True
            or envelope.get("transport") != "delivered"):
        return None
    response = envelope.get("response") or {}
    return dict(transport="delivered", settled=True, submission="not_admitted",
        operation_id=envelope["operation_id"], response=dict(status="rejected", reason=response.get("reason")),
        next_step="This request was not admitted. Inspect current context and explicitly choose a new corrected "
            "decision under the original limits. Do not collect or resubmit this refused request; "
            "software assigns a new identity. No authority is granted.")


class AdmissionRefusalPresentationError(ValueError):
    """Formatting failed after an SDK-validated refusal; no receipt/context copy."""
    def __init__(self, feedback: dict):
        super().__init__("Admission refusal presentation failed")
        self.feedback = feedback


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


def _claim_authoring_schema(canonical_schema: dict) -> dict:
    """Select semantic fields from the canonical Claim, with explicit grounding."""
    fields = deepcopy(canonical_schema["properties"])
    ordinary_key = deepcopy(fields["key"])
    ordinary_key["properties"]["property"]["enum"].remove("identity")
    scope = fields["scope"]["properties"]
    support = deepcopy(fields["supports"])
    support["items"] = _object({"primary": {"type": "boolean"}, **support["items"]["properties"]})
    fields["value"]["description"] = ("For identity Claims, state is the exact interpreted admitted name; "
        "demographic or other descriptive details belong in text, not the name value.")
    support["description"] = "All cited sources share the Claim grounding session; keep other-session evidence in separately grounded Claims."
    return _object({
        **{name: fields[name] for name in ("value", "text", "coverage", "status")},
        "key": {"anyOf": [
            _object({"property": {"const": "identity"}, "subject": {"enum": list(IDENTITY_COVERAGE)}}),
            ordinary_key]},
        "grounding": {"anyOf": [
            _object({"kind": {"const": "source"},
                "source_id": {"anyOf": [fields["id"], {"type": "null"}]},
                "coordinate_epoch": {"anyOf": [scope["coordinate_epoch"], {"type": "null"}]}}),
            _object({"kind": {"const": "unobserved"}, "session": scope["session"],
                "coordinate_epoch": scope["coordinate_epoch"]})]},
        "supports": support})


def request_tool_specs() -> tuple[ToolSpec, ...]:
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
        if kind == "navigate":
            schema["properties"]["goal"] = _without(schema["properties"]["goal"], "scope")
        elif kind == "activity":
            fields = schema["properties"]["goal"]["properties"]
            start = {name: deepcopy(fields[name]) for name in
                ("step", "operation", "target", "game_seconds", "interrupt_allowed")}
            start["step"] = {"const": "start"}
            start["operation"]["enum"].remove("direct")
            schema["properties"]["goal"] = {"anyOf": [_object(start),
                _object({"step": {"enum": ["poll", "interrupt", "resume"]}}),
                _object({"step": {"const": "answer_interrupt"},
                    "answer": deepcopy(fields["answer"]["anyOf"][0])})]}
        if kind in ("menu", "edit", "item"):
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
        ToolSpec("enactive_skill", "Choose ordinary input (direct), a semantic skill, or a selected executable procedure (program) with an explicit returned snapshot/source and finite limits. source_id=null selects that exact cached source. Direct uses perception=null; clicks keep informing geometry. Program requires its own new_root, selected current procedure revision and initial state, perception=null; software supplies each current visible program-view/1 and click geometry through the same writer and original cumulative limits. Its act/yield/done is fallible program behavior, never verified task success; unknown delivery stops evaluation. Activity start chooses operation/target/game_seconds/interrupt_allowed; prompt/activity children choose only step (poll/interrupt/resume) or step=answer_interrupt with answer=YES/NO. Software collects the selected immutable original root and derives stable fields and answer owner. Semantic preconditions remain strict. Software retains lineage and collects delivery and current evidence separately."
            "\nProgram result schema: " + canonical(program_result_schema())
            + "\nThis is the step(view,state) return shape, not the direct skill's input argument. "
            "Program clicks omit geometry. Source/result are bounded to32KiB, view256KiB and state16KiB; "
            "finite plain JSON and ordinary input validation still apply. Shape validity grants no input authority or useful-effect proof.", skill),
        ToolSpec("enactive_lifecycle", "Explicit registered launch/create/save/exit/load/finish. First obtain enactive_snapshot. With no owned child, launch using scope=new_root and source_id=null; then begin create/load with scope=new_root from its returned menu. For other operations, source_id=null selects that exact cached snapshot source. Continue an existing lifecycle phase with scope=lifecycle and the same operation, including transition reconciliation, identity readmission and adoption. Lifecycle direct children require interrupt_allowed=false. Owned paused-menu exit charges Resume plus Quit (at least2 primitives before any confirmation); a separate menu-only setup abort sends no input. No implicit save or restart.", lifecycle),
        ToolSpec("enactive_observe", "Request one typed native observation using the chosen snapshot epoch. A healthy ordinary prompt may advance or record local macro_closure without task success or renewed mission allowance; explicitly choose any next root from fresh evidence. Does not Resume or reconcile unknown delivery. After known direct input with absent/aged current evidence, explicit Observe can refresh its read-only scope across the exact authenticated operation rotation; input requires the fresh binding. It never restores failed custody or renews limits.", _object(common)),
    ]
    # Authoring projections bind metadata; canonical ledger contracts and
    # explicit semantic/evidence choices remain unchanged.
    for kind in ("remember", "correct"):
        variants = [_without(request_schema(kind, entry_type=entry), *headers, "kind")
                    for entry in (("claim",) if kind == "correct" else ("claim", "work", "decision", "procedure"))]
        variants[0]["properties"]["entry"] = _claim_authoring_schema(variants[0]["properties"]["entry"])
        if kind == "remember":
            variants[-1]["properties"]["entry"] = procedure_authoring_schema()
            variants.append(_object(dict(entry_type={"const": "procedure_candidate"},
                proposal_index={"type": "integer", "minimum": 0, "maximum": 63},
                candidate_index={"type": "integer", "minimum": 0, "maximum": 3})))
        specs.append(ToolSpec("enactive_" + kind,
            "Write explicit evidence-linked memory through the existing ledger. "
            "Set intent.entry_type alongside intent.entry, never inside entry. The selected entry contains only that memory type's fields. "
            "For Claims choose key, value, text, coverage, status, grounding and support groups. "
            "Identity keys choose world/character; software supplies the existing name unit/coverage, interpretation kind, schema/record type, Claim ID, scope/native observation order and host receipt time. "
            "Source grounding source_id=null selects the exact cached snapshot source; explicit IDs require a prior source read. "
            "coordinate_epoch=null uses only matching published coordinate_scope; before adoption or without a match, explicitly select the epoch from existing provisional_scope or a historical receipt. "
            "Each support group explicitly chooses primary plus additional source/claim IDs; primary=false never implies image support. "
            "Unobserved grounding stays source-free: every group requires primary=false and sources=[], with claim premises allowed. "
            + ("Correction supersedes come only from explicit retired_ids. " if kind == "correct" else "Remember supersedes are empty. ")
            + ("For Procedures choose content/program, support/counterexamples and parent=null for a new family or an explicit qualified revision revealed by enactive_context or a completed accepted Procedure write result, including original-result collection. "
               "Software derives schema, record/mission/family/revision IDs and revision number from the assigned operation and selected cached parent, and frozen admission environment from the selected snapshot; do not supply them. "
               "Alternatively choose entry_type=procedure_candidate with proposal_index/candidate_index read by enactive_advice for this exact snapshot. Software submits that original candidate through the same writer; no copying or automatic adoption. "
               if kind == "remember" else "")
            + "No inferred support, truth, success or automatic lesson promotion.",
            _object({**common, "intent": {"anyOf": variants}})))
    handoff = _without(request_schema("handoff"), *headers, "kind", "checkpoint_ids")
    handoff["properties"]["checkpoint_sources"] = {
        **request_schema("handoff")["properties"]["checkpoint_ids"], "items": nullable_id}
    handoff["required"].append("checkpoint_sources")
    specs.append(ToolSpec("enactive_handoff",
        "Explicit handoff through the existing mission state machine. checkpoint_sources selects retained observation sources, never Claim/Work IDs: null binds the exact selected cached snapshot source; an explicit source ID requires a prior source/image read. Software binds canonical checkpoint IDs without refreshing or substituting evidence. Choose the exact complete unfinished_work_ids and successor_role explicitly; original costs and uncertainty remain.",
        _object({**common, "intent": handoff})))
    for kind in ("stop", "reconcile"):
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
        ToolSpec("enactive_reflect_next", "Advisory actor only: get and durably claim bounded original work. requests_per_job bounds selected trajectory records per job, not tool calls or the admission's total jobs budget. Compute only when status is claimed. Pending, busy or unknown grants no permission to compute; no gameplay input or automatic model work.",
            _object({**reflection_scope, "wait_seconds": {**wait, "maximum": MAX_REFLECTION_READ_WAIT_SECONDS}})),
        ToolSpec("enactive_reflect_submit", "Advisory actor only: author semantic candidates/programs, notes and reason for a cached claimed job. Software supplies canonical candidate metadata from original admission and submission identity; parent must be an exact revision in that job's procedures. Prefer reusable executable repairs when supported, without inventing success or filling quotas. The original submission is immutable. Local validation refusal is not_submitted and has no command to collect. Collect uncertain original submissions instead of resubmitting. No automatic memory adoption or gameplay.",
            _object({**reflection_scope, "job_id": identity, "request_id": identity, "wait_seconds": wait,
                **{field: proposal[field] for field in ("notes", "reason")},
                "candidates": {**proposal["candidates"], "items": procedure_authoring_schema()}})),
        ToolSpec("enactive_reflect_source", "Advisory actor only: read an allowlisted original image from a cached claimed job. Never Observe; this presentation cannot serve as a deciding player's source-read declaration.",
            _object({**reflection_scope, "job_id": identity, "source_id": identity}), True),
        ToolSpec("enactive_reflect_result", "Collect an original advisory command by its stable ID, including after adapter restart. Never submits or claims work; unavailable remains unknown.",
            _object({**reflection_scope, "command_id": identity, "wait_seconds": wait}), True),
        ToolSpec("enactive_advice", "Deciding player: read advice indexed by the selected exact snapshot. proposal_index=null lists the latest four proposals with compact candidate summaries; select one returned index for full original proposal detail. An index never follows a newer snapshot. Read candidates can be explicitly adopted with enactive_remember entry_type=procedure_candidate; advice grants no current authority or guaranteed success.",
            _object(dict(snapshot_id=identity, proposal_index={"anyOf": [
                {"type": "integer", "minimum": 0, "maximum": 63}, {"type": "null"}]})), True),
    ))
    return tuple(specs)


def tool_specs() -> tuple[ToolSpec, ...]:
    """Current model contract; the imperative SDK owns transport mechanics.

    Keep a single schema source. The SDK's explicit-ID calls remain useful for
    engineering and exact duplicate collection, not an alternate MCP contract.
    """
    return tuple(ToolSpec(spec.name, spec.description,
        _without(spec.schema, "request_id", "wait_seconds"), spec.read_only)
        for spec in request_tool_specs())


def _validate_arguments(name: str, data: dict, schema: dict) -> None:
    """Keep canonical validation; narrow only rejected intent diagnostics."""
    try:
        validate_json(data, schema)
    except ContractError as original:
        discriminator = {"enactive_skill": "skill_kind", "enactive_remember": "entry_type",
                         "enactive_correct": "entry_type"}.get(name)
        if discriminator is None:
            raise
        intent = data.get("intent")
        selected = next((branch for branch in schema["properties"]["intent"]["anyOf"]
            if isinstance(intent, dict) and
            branch["properties"][discriminator]["const"] == intent.get(discriminator)), None)
        if selected is not None:
            # Keep root definitions for references in the selected current branch.
            schema = {**schema, "properties": {**schema["properties"], "intent": selected}}
        messages = []
        for error in Draft202012Validator(schema).iter_errors(data):
            if selected is None and list(error.absolute_path) == ["intent"]:
                message = f"intent.{discriminator}: required supported discriminator; see tool schema"
            else:
                if error.context:
                    error = best_match([error])
                path = ".".join(map(str, error.absolute_path)) or "arguments"
                if error.validator == "required":
                    message = f"{path}: {error.message}"
                elif error.validator == "type":
                    message = f"{path}: expected {error.validator_value}"
                elif error.validator == "additionalProperties":
                    fields = ", ".join(error.schema.get("properties", {}))
                    message = f"{path}: unexpected fields; allowed fields: {fields}"
                elif error.validator in ("const", "enum"):
                    message = f"{path}: expected {error.validator_value!r}"
                else:
                    message = f"{path}: does not satisfy {error.validator} constraint"
            messages.append(message[:180])
            if len(messages) == 8:
                messages.append("Further errors omitted; see selected tool schema")
                break
        if not messages:
            # Preserve canonical strict-number checks beyond JSON Schema.
            raise original
        raise ContractError("; ".join(messages)) from None


class PlayerTools:
    """One adapter, bounded descriptive handles, no controller capability."""
    def __init__(self, client: MissionClient):
        self.client = client
        self.snapshots: OrderedDict[str, dict] = OrderedDict()
        self.sources: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self.procedures: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self._advice: OrderedDict[tuple[str, int], dict] = OrderedDict()
        self.specs = {spec.name: spec for spec in request_tool_specs()}
        self.model_specs = {spec.name: spec for spec in tool_specs()}
        self._lock = threading.Lock()
        self._last_image: tuple[str, str, int, str, str] | None = None
        self._reflection_lock = threading.Lock()
        self._reflection_jobs: OrderedDict[tuple[str, str, str], dict] = OrderedDict()

    def model_arguments(self, name: str, arguments: dict) -> tuple[dict, dict | None]:
        """Assign once before ordinary SDK staging and bounded collection.

        Request IDs are new semantic invocation IDs, never JSON-RPC IDs. This
        method does not refresh evidence, infer scope/limits, or replay a call.
        """
        if name not in self.model_specs:
            raise ContractError("Unknown player tool")
        properties = self.specs[name].schema["properties"]
        try:
            data = json_object(arguments)
            _validate_arguments(name, data, self.model_specs[name].schema)
            if "request_id" in properties and name != "enactive_reflect_submit":
                mission_id = (data["admission"]["mission_id"] if name == "enactive_start" else
                    self._cached_snapshot(data["snapshot_id"])["mission"]["mission_id"])
        except ContractError as exc:
            # No original identity has been assigned or staged for this new
            # model invocation. Read-tool errors keep their ordinary meaning.
            if "request_id" in properties:
                raise UnsubmittedRequest(str(exc)) from None
            raise
        if "wait_seconds" in properties:
            data["wait_seconds"] = (MAX_REFLECTION_READ_WAIT_SECONDS
                if name == "enactive_reflect_next" else 15)
        collection = None
        if "request_id" in properties:
            identity = "op-" + uuid.uuid4().hex
            data["request_id"] = identity
            if name == "enactive_reflect_submit":
                collection = dict(tool="enactive_reflect_result", arguments=dict(
                    mission_id=data["mission_id"], reflector_id=data["reflector_id"], command_id=identity))
            else:
                collection = dict(tool="enactive_result", arguments=dict(
                    mission_id=mission_id, operation_id=identity))
        return data, collection

    @staticmethod
    def _remember(cache: OrderedDict, key, value, *, maximum: int = 32):
        cache[key] = deepcopy(value)
        cache.move_to_end(key)
        while len(cache) > maximum:
            cache.popitem(last=False)

    def _cached_snapshot(self, identity: str) -> dict:
        if identity not in self.snapshots:
            raise ContractError("Snapshot handle unavailable; explicitly read a new snapshot")
        return deepcopy(self.snapshots[identity])

    def detail(self, identity: str, section: str) -> dict:
        snapshot = self._cached_snapshot(identity)
        if section == "mission":
            detail = snapshot["mission"]
        elif section in ("native", "source"):
            detail = snapshot.get(section)
        else:
            field = "last_receipt" if section == "receipt" else section
            detail = snapshot["mission"].get(field)
        return dict(snapshot_id=identity, section=section, detail=detail, grants_authority=False)

    def _source(self, mission_id: str, identity: str | None) -> dict | None:
        if identity is None:
            return None
        if (mission_id, identity) not in self.sources:
            raise ContractError("Read the selected exact source/image explicitly; its metadata is unavailable in this producer; no source substitution")
        return deepcopy(self.sources[(mission_id, identity)])

    def source(self, mission_id: str, identity: str) -> tuple[dict, bytes]:
        metadata, image = self.client.source(mission_id, identity)
        self._remember(self.sources, (mission_id, identity), metadata, maximum=MAX_HANDOFF_SOURCES)
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
        response = envelope.get("response") or {}
        operation = response.get("operation")
        request = operation.get("request") if isinstance(operation, dict) else None
        delivered = envelope.get("transport") == "delivered" and envelope.get("reason") is None
        if (delivered and response.get("status") == "accepted" and isinstance(request, dict)
                and request.get("request_id") == envelope.get("operation_id")
                and operation.get("state") == "completed" and request.get("kind") == "remember"
                and request.get("entry_type") == "procedure"):
            result = operation.get("result")
            if isinstance(result, dict) and result.get("entry") is not None:
                record = validate_procedure(result["entry"])
                if record != request.get("entry") or record["mission_id"] != request.get("mission_id"):
                    raise ContractError("Completed procedure result differs from its original request")
                # This returned record is descriptive parent material, not a
                # current-head, source, applicability or input-authority check.
                self._remember(self.procedures, (record["mission_id"], record["id"]), record)
        collection = None
        refusal = admission_refusal_feedback(envelope)
        if refusal is not None:
            output["next_step"] = refusal["next_step"]
        elif (delivered and request is not None and request["request_id"] == envelope.get("operation_id")
                and operation["state"] in ("accepted", "running")
                and request["kind"] in ("skill", "lifecycle")):
            collection = dict(mission_id=request["mission_id"], operation_id=request["request_id"])
        elif (delivered and response.get("status") == "rejected" and operation is None
                and response.get("input_owner_operation_id") is not None):
            collection = dict(mission_id=response["mission"]["mission_id"],
                operation_id=response["input_owner_operation_id"])
            output["input_admission"] = "not_admitted"
        if collection is not None:
            output["next_call"] = dict(tool="enactive_result", arguments=collection)
            output["next_step"] = ("Collect this original input operation before choosing another input. "
                "An in-progress image is read-only evidence, not its completed outcome. "
                "After collection, inspect and explicitly select current evidence; never replay or retarget input.")
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

    def invalidate_image_presentation(self) -> None:
        """A failed response cannot establish that its image was presented."""
        self._last_image = None

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

    def present_image(self, name: str, output: dict, image: bytes | None) -> tuple[dict, bytes | None]:
        """Present only after the transport's background call has returned."""
        if name == "enactive_source":
            self.invalidate_image_presentation()
        if name == "enactive_snapshot":
            return self._present_image(output, image, explicit=True)
        if name not in ("enactive_source", "enactive_detail", "enactive_reflect_next",
                        "enactive_reflect_submit", "enactive_reflect_source", "enactive_reflect_result", "enactive_advice"):
            return self._present_image(output, image, explicit=False)
        return output, image

    def call(self, name: str, arguments: dict, *, present_image: bool = True) -> tuple[dict, bytes | None]:
        if name not in self.specs:
            raise ContractError("Unknown player tool")
        data = json_object(arguments)
        try:
            _validate_arguments(name, data, self.specs[name].schema)
        except ContractError as exc:
            self._preparation_refusal(name, data, exc)
        if name in ("enactive_reflect_next", "enactive_reflect_submit", "enactive_reflect_source", "enactive_reflect_result", "enactive_advice"):
            return self._reflection_call(name, data)
        if not self._lock.acquire(blocking=False):
            self._preparation_refusal(name, data,
                ContractError("Another player tool is active; collect its original operation before continuing"))
        try:
            output, image = self._call(name, data)
            return self.present_image(name, output, image) if present_image else (output, image)
        except (OSError, ValueError):
            self._last_image = None
            raise
        finally:
            self._lock.release()

    def _preparation_refusal(self, name: str, data: dict, error: ContractError) -> None:
        """Only a proven new ordinary intent can have no original to collect."""
        if "request_id" not in self.specs[name].schema["properties"] or name == "enactive_reflect_submit":
            raise error
        snapshot_id = data.get("snapshot_id")
        selected = self.snapshots.get(snapshot_id) if isinstance(snapshot_id, str) else None
        mission = data.get("admission") if name == "enactive_start" else (
            None if selected is None else selected.get("mission"))
        if (not isinstance(mission, dict) or not isinstance(mission.get("mission_id"), str)
                or not isinstance(data.get("request_id"), str)):
            raise error
        # Probe only a refusal path. Existing, corrupt or unavailable stages
        # retain their original uncertainty; SDK stage/submit is never inside.
        if self.client.staged_request(mission["mission_id"], data["request_id"]) is not None:
            raise error
        raise UnsubmittedRequest(str(error)) from None

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
            return self._read_advice(data), None
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
        if name == "enactive_reflect_source":
            job = self._reflection_job(mission_id, reflector_id, data["job_id"])["job"]["job"]
            if dict(mission_id=mission_id, source_id=data["source_id"]) not in job["sources"]:
                raise ContractError("Reflection source is outside the original claimed job allowlist")
            # Deliberately bypass source(), which populates player presentation
            # handles used by active-input and fresh-context handoff contracts.
            return self.client.reflection_source(mission_id, reflector_id, job["id"], data["source_id"])
        # Admission metadata is immutable; read it off the deciding player's hot
        # path only when the learner actually authors a candidate. This is not a
        # new observation or an authority refresh. Transport errors stay outside
        # the pure-validation/not_submitted classification below.
        try:
            job = self._reflection_job(mission_id, reflector_id, data["job_id"])["job"]["job"]
        except ContractError as exc:
            raise UnsubmittedRequest(str(exc)) from exc
        environment = None
        if data["candidates"]:
            mission = self.client.status().get("mission") or {}
            if mission.get("mission_id") != mission_id:
                raise UnsubmittedRequest("Candidate authoring requires its original admitted mission")
            environment = (mission.get("configuration") or {}).get("procedure_environment")
        try:
            parents = {(record["mission_id"], record["id"]): record for record in job["procedures"]}
            candidates = []
            for index, entry in enumerate(data["candidates"]):
                parent = entry["parent"]
                selected = None if parent is None else parents.get((parent["mission_id"], parent["revision_id"]))
                identity = "candidate-" + hashlib.sha256((data["request_id"] + "\0" + str(index)).encode()).hexdigest()
                candidates.append(author_procedure(entry, mission_id=mission_id,
                    identity=identity, environment=environment, parent=selected))
            proposal = validate_proposal(dict(schema="reflection/2", record_type="ReflectionProposal",
                id="proposal-" + hashlib.sha256(data["request_id"].encode()).hexdigest(),
                job_id=job["id"], mission_id=job["mission_id"], reflector_id=job["reflector_id"],
                epoch=job["epoch"], cutoff_sequence=job["through_sequence"], memory_version=job["memory_version"],
                candidates=candidates, **{field: data[field] for field in ("notes", "reason")}), job)
            command = validate_command(dict(schema="reflection/2", kind="submit", command_id=data["request_id"],
                mission_id=mission_id, reflector_id=reflector_id, job_id=job["id"], proposal=proposal))
        except ContractError as exc:
            # Only immutable cache lookup and pure validation precede this
            # classification. SDK staging, submission and collection stay out.
            raise UnsubmittedRequest(str(exc)) from None
        return self.client.reflection_command(command, wait_seconds=data["wait_seconds"]), None

    def _read_advice(self, data: dict) -> dict:
        """Bind compact discovery and detail to an explicitly retained snapshot."""
        selected = self._cached_snapshot(data["snapshot_id"])
        mission = selected.get("mission") or {}
        identities = (mission.get("reflection") or {}).get("proposals", [])
        index = data["proposal_index"]
        if index is not None and index >= len(identities):
            raise ContractError("Proposal index is outside the selected snapshot")
        indices = range(max(0, len(identities) - 4), len(identities)) if index is None else [index]
        proposals = []
        for number in indices:
            value = self.client.reflection_advice(mission["mission_id"], identities[number])
            if value["status"] != "available":
                proposals.append(dict(proposal_index=number, status=value["status"]))
                continue
            proposal = validate_proposal(value["proposal"])
            if (proposal["mission_id"], proposal["id"]) != (mission["mission_id"], identities[number]):
                raise ContractError("Advice differs from the exact selected snapshot proposal")
            with self._reflection_lock:
                self._remember(self._advice, (data["snapshot_id"], number), proposal)
            if index is not None:
                proposals.append(dict(proposal_index=number, status="available", proposal=proposal))
            else:
                candidates = [dict(candidate_index=n, **{field: record[field] for field in (
                    "goal", "applicability", "invalidators", "stop_conditions", "limits", "status", "reason")},
                    executable=record["program"] is not None) for n, record in enumerate(proposal["candidates"])]
                proposals.append(dict(proposal_index=number, status="available", candidates=candidates,
                    notes=[{field: note[field] for field in ("kind", "text")} for note in proposal["notes"]],
                    reason=proposal["reason"]))
        return dict(snapshot_id=data["snapshot_id"], status="available" if proposals else "empty",
            proposals=proposals, omitted_proposals=max(0, len(identities) - 4) if index is None else 0,
            grants_authority=False)

    def _selected_candidate(self, snapshot_id: str, mission: dict, intent: dict) -> dict:
        with self._reflection_lock:
            proposal = deepcopy(self._advice.get((snapshot_id, intent["proposal_index"])))
        if proposal is None:
            raise ContractError("Read this snapshot's proposal with enactive_advice before selecting a candidate")
        index = intent["candidate_index"]
        if proposal["mission_id"] != mission["mission_id"] or index >= len(proposal["candidates"]):
            raise ContractError("Candidate index is outside the read proposal")
        return validate_procedure(proposal["candidates"][index])

    def _claim_entry(self, selected: dict, identity: str, kind: str, intent: dict) -> dict:
        """Expand explicit interpretation without choosing its truth or support."""
        entry = intent["entry"]
        mission = selected["mission"]
        grounding = entry["grounding"]
        primary = None
        sources = []
        if grounding["kind"] == "source":
            source = (selected.get("source") if grounding["source_id"] is None else
                self._source(mission["mission_id"], grounding["source_id"]))
            primary, _ = _source_binding(source)
            reference = source["reference"]
            session = reference["session"]
            epoch = grounding["coordinate_epoch"]
            if epoch is None:
                published = mission.get("coordinate_scope")
                if (not isinstance(published, dict) or published.get("mission_id") != mission["mission_id"]
                        or published.get("session") != session):
                    raise ContractError("Select explicit coordinate_epoch from an existing provisional_scope or historical "
                        "receipt; the selected source has no matching published coordinate_scope")
                epoch = published["coordinate_epoch"]
            observed = dict(revision=reference["revision"], turn=reference["turn"])
            sources.append(primary)
        else:
            session, epoch = grounding["session"], grounding["coordinate_epoch"]
            observed = dict(revision=None, turn=None)
        supports = []
        for group in entry["supports"]:
            if primary is None and (group["primary"] or group["sources"]):
                raise ContractError("Unobserved grounding requires primary=false and sources=[] in every support group")
            for source_id in group["sources"]:
                self._source(mission["mission_id"], source_id)
            cited = list(dict.fromkeys(([primary] if group["primary"] else []) + group["sources"]))
            supports.append(dict(sources=cited, claims=group["claims"]))
            sources.extend(source_id for source_id in cited if source_id not in sources)
        key = deepcopy(entry["key"])
        if key["property"] == "identity":
            key.update(unit=IDENTITY_UNIT, coverage_id=IDENTITY_COVERAGE[key["subject"]])
        staged = self.client.staged_request(mission["mission_id"], identity)
        if staged is not None and (staged["kind"] != kind or staged.get("entry_type") != "claim"):
            raise ContractError("Request identity already staged for another operation or memory type")
        received = int(time.time() * 1000) if staged is None else staged["entry"]["received_time"]
        schema = request_schema(kind, entry_type="claim")["properties"]["entry"]["properties"]
        return dict(schema=schema["schema"]["const"], record_type=schema["record_type"]["const"],
            id="claim-" + hashlib.sha256(identity.encode()).hexdigest(), kind="interpretation", key=key,
            **{field: entry[field] for field in ("value", "text", "coverage", "status")},
            scope=dict(mission_id=mission["mission_id"], session=session, coordinate_epoch=epoch),
            observed_time=observed, received_time=received, sources=sources, supports=supports,
            supersedes=intent["retired_ids"] if kind == "correct" else [])

    def _procedure_entry(self, selected: dict, identity: str, entry: dict) -> dict:
        mission = selected["mission"]
        environment = (mission.get("configuration") or {}).get("procedure_environment")
        if not isinstance(environment, dict):
            raise ContractError("Selected snapshot has no admitted procedure environment; obtain explicit current context")
        parent = entry["parent"]
        record = None
        if parent is not None:
            record = self.procedures.get((parent["mission_id"], parent["revision_id"]))
            if record is None:
                raise ContractError("Parent revision unavailable; explicitly retrieve its procedure through "
                    "enactive_context or collect its original completed write result")
        return author_procedure(entry, mission_id=mission["mission_id"], identity=identity,
            environment=environment, parent=record)

    def _call(self, name: str, data: dict) -> tuple[dict, bytes | None]:
        if name == "enactive_snapshot":
            return self.snapshot()
        if name == "enactive_detail":
            return self.detail(data["snapshot_id"], data["section"]), None
        if name == "enactive_source":
            return self.source(data["mission_id"], data["source_id"])
        if name == "enactive_result":
            return self._finish(self.client.collect(**data))
        if name == "enactive_context":
            selected = self._cached_snapshot(data["snapshot_id"])
            snapshot = selected["mission"]
            intent = data["intent"]
            intent["scope"]["mission_id"] = snapshot["mission_id"]
            request = dict(schema=VERSION, kind="context", mission_id=snapshot["mission_id"], **intent)
            envelope = self.client.submit(validate_request(request), wait_seconds=0)
            response = envelope.get("response") or {}
            context = response.get("context")
            if response.get("status") == "accepted" and isinstance(context, dict):
                if context.get("mission_id") != snapshot["mission_id"]:
                    raise ContractError("Returned procedure context belongs to another mission")
                for value in (context.get("packet") or {}).get("procedures", ()):
                    record = validate_procedure(value)
                    self._remember(self.procedures, (record["mission_id"], record["id"]), record)
            return self._finish(envelope)
        try:
            request = self._prepare_mutation(name, data)
        except ContractError as exc:
            self._preparation_refusal(name, data, exc)
        envelope = self.client.submit(request, wait_seconds=data["wait_seconds"])
        try:
            return self._finish(envelope)
        except Exception as exc:
            feedback = admission_refusal_feedback(envelope)
            if feedback is not None:
                raise AdmissionRefusalPresentationError(feedback) from exc
            raise

    def _prepare_mutation(self, name: str, data: dict) -> dict:
        """Bind one explicit intent; no staging, submit or response presentation.

        Claim preparation may read an immutable local stage or collect the
        selected original activity root or old handoff issuance. These reads
        never stage or submit the new request.
        """
        if name == "enactive_start":
            return validate_request(dict(schema=VERSION, kind="start", request_id=data["request_id"], admission=data["admission"]))
        selected = self._cached_snapshot(data["snapshot_id"])
        snapshot = selected["mission"]
        kind = name.removeprefix("enactive_")
        if (kind == "lifecycle" and data["intent"]["operation"] in ("create", "load")
                and data["source_id"] is None and snapshot["phase"] == "admitted"
                and selected.get("source") is None and snapshot["current_source"] is None
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
        identity = data["request_id"]
        intent = deepcopy(data.get("intent", {}))
        if kind in ("skill", "lifecycle"):
            intent["kind"] = kind
            if intent.get("perception") is not None:
                intent["perception"]["basis"] = "player_interpretation"
            if data["source_id"] is not None:
                source = self._source(snapshot["mission_id"], data["source_id"])
            elif kind == "lifecycle" and intent["operation"] == "launch":
                source = None
            else:
                source = selected.get("source")
                if source is None:
                    raise ContractError("Selected snapshot has no source to bind. Null source_id selects only "
                        "that cached snapshot source. If an Observe/lifecycle result returned diagnostic "
                        "source_ids, read the chosen exact image with enactive_source and explicitly select "
                        "its source_id. No request was submitted; no refresh, retarget or authority renewal.")
            original_root = None
            if kind == "skill" and intent["skill_kind"] == "activity" and data["scope"] in ("prompt", "activity"):
                phase = snapshot.get(data["scope"] + "_phase")
                if type(phase) is not dict or not phase.get("origin_request_id"):
                    raise ContractError("Selected activity scope has no original root to collect")
                collected = self.client.collect(snapshot["mission_id"], phase["origin_request_id"], wait_seconds=0)
                operation = (collected.get("response") or {}).get("operation")
                if collected.get("transport") != "delivered" or type(operation) is not dict:
                    raise ContractError("Selected original activity root unavailable; no child was submitted")
                original_root = operation.get("request")
            request = compose_request(snapshot, request_id=identity, intent=intent, limits=data["limits"],
                scope=data["scope"], source=source, supporting_source_ids=data["supporting_source_ids"],
                original_root=original_root)
        else:
            if kind == "handoff":
                checkpoints = []
                for source_id in intent.pop("checkpoint_sources"):
                    source = selected.get("source") if source_id is None else self._source(snapshot["mission_id"], source_id)
                    if source is None:
                        raise ContractError("Selected snapshot has no checkpoint source. Read and explicitly select "
                            "a retained source/image; null selects only this exact cached snapshot. No request was submitted.")
                    checkpoints.append(source["reference"]["observation_id"])
                intent["checkpoint_ids"] = checkpoints
            elif kind in ("remember", "correct") and intent["entry_type"] == "claim":
                intent["entry"] = self._claim_entry(selected, identity, kind, intent)
            elif kind == "remember" and intent["entry_type"] == "procedure":
                intent["entry"] = self._procedure_entry(selected, identity, intent["entry"])
            elif kind == "remember" and intent["entry_type"] == "procedure_candidate":
                intent = dict(entry_type="procedure", entry=self._selected_candidate(data["snapshot_id"], snapshot, intent))
            elif kind == "claim":
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
        return request
