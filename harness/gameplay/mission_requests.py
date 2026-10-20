"""Compose ordinary mission/7 requests from explicit passive context.

No I/O, refresh, source selection or execution occurs here. Supplied dictionaries
can establish metadata consistency, never archive membership, PNG integrity,
ownership, freshness or permission to dispatch. The receiver retains those checks.
Memory, handoff and recovery readmission use their existing specialized ingress.
"""
from __future__ import annotations

from .contracts import ContractError, EvidenceRef, json_object
from .evidence import _identity, _validate_observation
from .mission_contracts import VERSION, validate_request

_DERIVED = frozenset(("schema", "mission_id", "epoch", "request_id", "limits", "phase_id",
                      "sources", "expected_session", "expected_revision", "expected_boundary_id"))
_PHASES = ("prompt_phase", "lifecycle_phase", "activity_phase")


def _source_binding(source: dict) -> tuple[str, dict]:
    if type(source) is not dict or not {"reference", "observation"} <= source.keys():
        raise ContractError("Select one archive entry with reference and observation")
    reference = EvidenceRef.from_dict(source["reference"])
    observation = _validate_observation(source["observation"])
    scene = observation["scene"]
    if (reference.observation_id != _identity(observation)
            or reference.session != observation["session"]
            or reference.revision != observation["revision"]
            or reference.timestamp_ms != observation["timestamp_ms"]
            or reference.boundary_kind != observation["boundary"]["kind"]
            or reference.turn != (None if scene is None else scene["turn"])):
        raise ContractError("Selected reference and observation metadata disagree")
    return reference.observation_id, dict(expected_session=reference.session,
        expected_revision=reference.revision, expected_boundary_id=observation["boundary"]["id"])


def _selected_phase(snapshot: dict, scope: str, intent: dict, primary: str | None) -> str | None:
    phases = {key: snapshot[key] for key in _PHASES}
    if scope == "new_root":
        occupied = any(value is not None for value in phases.values())
        if intent["kind"] == "skill":
            if occupied or intent.get("skill_kind") in ("menu", "edit"):
                raise ContractError("A new skill root requires no phase and cannot be menu/edit")
        elif occupied:
            lifecycle = phases["lifecycle_phase"]
            if (intent.get("operation") != "exit" or phases["prompt_phase"] is not None
                    or phases["activity_phase"] is not None or type(lifecycle) is not dict
                    or lifecycle.get("operation") not in ("create", "load")):
                raise ContractError("A new lifecycle root requires no phase except explicit create/load abort exit")
        return None

    summary = phases[scope + "_phase"]
    if (type(summary) is not dict or type(summary.get("origin_request_id")) is not str
            or not summary["origin_request_id"] or summary.get("checkpoint_id") != primary
            or primary is None):
        raise ContractError("Selected scope requires its exact root and primary checkpoint")
    if scope != "lifecycle":
        if intent["kind"] != "skill":
            raise ContractError("Prompt/activity scopes support skill children only")
        supported = ("activity",) if scope == "activity" else ("menu", "edit", "inspect", "item", "activity")
        if intent.get("skill_kind") not in supported:
            raise ContractError("Selected scope does not support this skill child")
    else:
        operation = summary.get("operation")
        if intent["kind"] == "lifecycle":
            if operation not in ("create", "save", "load") or intent.get("operation") != operation:
                raise ContractError("Lifecycle child requires the same create/save/load operation")
        else:
            skill = intent.get("skill_kind")
            identity = (skill == "inspect" and type(intent.get("goal")) is dict
                        and intent["goal"].get("purpose") == "character_identity")
            if (intent.get("work_id") is not None
                    or operation not in ("create", "save", "load", "exit")
                    or (operation == "exit" and skill != "menu")
                    or (skill not in ("menu", "edit") and not identity)):
                raise ContractError("Lifecycle skill child requires its menu/editor/identity operation and no Work")
    return summary["origin_request_id"]


def compose_request(snapshot: dict, *, request_id: str, intent: dict, limits: dict,
                    scope: str, source: dict | None = None,
                    supporting_source_ids: tuple[str, ...] = ()) -> dict:
    """Copy chosen semantics into one validated current request, without authority.

    All three public phase summaries must be present, including explicit nulls.
    Existing scopes bind their exact origin and selected primary checkpoint; no
    other summary or current_source is substituted. A new-root exit alongside
    create/load merely represents an explicit abort request; only the receiver
    decides whether its narrow Resume-only path is eligible. Historical Finish
    and frameless activity checkpoints do not require current_source.

    Intent contains the existing skill/lifecycle semantic fields, including Work
    and perception choices, with every derived header omitted. Perception's
    source_id is also derived. Limits and a new request ID are caller choices;
    no deadline or budget is inferred or extended. Explicit support IDs supplement
    the chosen primary (for example, first/latest transition observations).
    validate_request owns the final closed schema and cross-field constraints;
    the ordinary canonical serializer remains the serialization path.
    """
    if type(snapshot) is not dict or not {"mission_id", "epoch", *_PHASES} <= snapshot.keys():
        raise ContractError("Select a mission status snapshot with explicit phase summaries")
    if scope not in ("new_root", "prompt", "lifecycle", "activity"):
        raise ContractError("Select new_root, prompt, lifecycle or activity scope")
    data = json_object(intent)
    if _DERIVED & data.keys():
        raise ContractError("Intent must omit derived request headers and limits")
    if data.get("kind") not in ("skill", "lifecycle"):
        raise ContractError("Producer supports skill and lifecycle intent only")
    view = data.get("perception")
    if view is not None and (type(view) is not dict or "source_id" in view):
        raise ContractError("Perception must omit its derived source_id")
    if type(supporting_source_ids) not in (tuple, list):
        raise ContractError("Supporting sources must be explicitly supplied IDs")

    launch = data["kind"] == "lifecycle" and data.get("operation") == "launch"
    if launch:
        if scope != "new_root" or source is not None or supporting_source_ids:
            raise ContractError("Launch requires new_root with no source or supporting IDs")
        primary = None
        binding = dict(expected_session=None, expected_revision=None, expected_boundary_id=None)
    else:
        primary, binding = _source_binding(source)
    parent = _selected_phase(snapshot, scope, data, primary)
    if view is not None:
        view["source_id"] = primary
    return validate_request({**data, "schema": VERSION, "mission_id": snapshot["mission_id"],
        "epoch": snapshot["epoch"], "request_id": request_id, "limits": limits, "phase_id": parent,
        "sources": ([] if primary is None else [primary]) + list(supporting_source_ids), **binding})
