"""Compose ordinary mission/11 requests from explicit passive context.

No I/O, refresh, source selection or execution occurs here. Supplied dictionaries
can establish metadata consistency, never archive membership, PNG integrity,
ownership, freshness or permission to dispatch. The receiver retains those checks.
Memory, handoff and recovery readmission use their existing specialized ingress.
"""
from __future__ import annotations

import hashlib

from .contracts import ContractError, EvidenceRef, json_object, validate_json
from .evidence import _identity, _validate_observation
from .mission_contracts import VERSION, request_schema, validate_request, validate_submission

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
        if (occupied and snapshot.get("phase") == "active"
                and phases["prompt_phase"] is not None
                and phases["lifecycle_phase"] is None and phases["activity_phase"] is None
                and snapshot.get("active_operation") is None):
            raise ContractError("The selected snapshot still has an open prompt. "
                "Explicitly call enactive_observe with this snapshot before choosing another root. "
                "Observe may report macro_closure for an exhausted ordinary prompt; inspect its returned "
                "phase and visible state. If prompt_phase remains open, continue that original root with "
                "a supported scope=prompt child; another Observe does not guarantee closure. "
                "A program requires new_root and cannot replace an open prompt root. "
                "Choose a new bounded root only after the phase actually closes. "
                "Mission remaining_limits describe the whole mission, not the local root's remaining allowance. "
                "This as-of guidance neither closes a phase nor resumes Pause, resolves unknown delivery "
                "or grants input authority.")
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
        supported = ("activity",) if scope == "activity" else ("menu", "edit", "inspect", "item", "activity", "direct")
        if intent.get("skill_kind") not in supported:
            raise ContractError("Selected scope does not support this skill child")
    else:
        operation = summary.get("operation")
        if intent["kind"] == "lifecycle":
            if operation not in ("create", "save", "load") or intent.get("operation") != operation:
                raise ContractError("Lifecycle child requires the same create/save/load operation")
        # Skill eligibility belongs to the receiver/ledger. Composition binds
        # the explicitly selected root and source, without a second UI taxonomy.
    return summary["origin_request_id"]


def _bind_skill_goal(snapshot: dict, data: dict, scope: str, source: dict,
                     original_root: dict | None, limits: dict) -> None:
    """Fill mechanical fields in this private intent copy, never fetch context."""
    kind = data.get("skill_kind")
    if kind not in ("navigate", "activity"):
        return
    goal = data.get("goal")
    if type(goal) is not dict:
        raise ContractError("Skill goal must be an object")
    if kind == "navigate":
        if "scope" in goal:
            raise ContractError("Navigation intent must omit its derived goal.scope")
        published = snapshot.get("coordinate_scope")
        reference = source["reference"]
        if (type(published) is not dict or published.get("mission_id") != snapshot["mission_id"]
                or published.get("session") != reference["session"] or reference["boundary_kind"] != "normal_play"):
            raise ContractError("Selected navigation source has no matching published coordinate_scope")
        goal["scope"] = json_object(published)
    else:
        if "interrupt_request_id" in goal:
            raise ContractError("Activity intent must omit its derived interrupt_request_id")
        stable = ("operation", "target", "game_seconds", "interrupt_allowed")
        if scope == "new_root":
            if set(goal) != {"step", *stable} or goal.get("step") != "start":
                raise ContractError("Activity root requires start and its semantic fields; omit answer and owner")
        else:
            fields = {"step", "answer"} if goal.get("step") == "answer_interrupt" else {"step"}
            if (scope not in ("prompt", "activity") or set(goal) != fields
                    or goal.get("step") not in ("poll", "interrupt", "resume", "answer_interrupt")):
                raise ContractError("Activity child requires only its step and explicit interrupt answer")
            root = validate_request(original_root)
            if (root.get("mission_id") != snapshot["mission_id"]
                    or root.get("request_id") != snapshot[scope + "_phase"]["origin_request_id"]
                    or root.get("phase_id") is not None or root["kind"] != "skill"
                    or root["skill_kind"] not in ("activity", "direct", "program")):
                raise ContractError("Activity child requires its exact canonical original root")
            if root["skill_kind"] == "activity":
                goal.update({key: root["goal"][key] for key in stable})
            else:
                # Ordinary roots declare a ceiling, not a semantic duration.
                # Keep this child within each explicit ceiling and wire bound.
                activity_fields = request_schema("skill", skill_kind="activity")["properties"]
                validate_json(limits, activity_fields["limits"])
                maximum = activity_fields["goal"]["properties"]["game_seconds"]["maximum"]
                goal.update(operation="direct", target=root["goal"]["expected"],
                    game_seconds=min(root["limits"]["game_seconds"], limits["game_seconds"], maximum),
                    interrupt_allowed=root["goal"]["interrupt_allowed"])
        goal.setdefault("answer", None)
        owner = None
        if goal.get("step") == "answer_interrupt":
            phase = snapshot["activity_phase"]
            boundary = source["observation"]["boundary"]
            if (scope != "activity" or type(phase) is not dict
                    or phase.get("stage") != "interrupt_confirmation" or phase.get("answered") is not False
                    or type(phase.get("interrupt_request_id")) is not str
                    or boundary["kind"] != "interrupt_confirmation"
                    or boundary["interrupt_request_id"] != phase["interrupt_request_id"]):
                raise ContractError("Selected activity phase/source has no matching unanswered interrupt owner")
            owner = phase["interrupt_request_id"]
        goal["interrupt_request_id"] = owner


def compose_request(snapshot: dict, *, request_id: str, intent: dict, limits: dict,
                    scope: str, source: dict | None = None,
                    supporting_source_ids: tuple[str, ...] = (),
                    original_root: dict | None = None) -> dict:
    """Copy chosen semantics into one validated current request, without authority.

    All three public phase summaries must be present, including explicit nulls.
    Existing scopes bind their exact origin and selected primary checkpoint; no
    other summary or current_source is substituted. A new-root exit alongside
    create/load merely represents an explicit abort request; only the receiver
    decides whether settled menu-only cleanup is eligible. Historical Finish
    and frameless activity checkpoints do not require current_source.

    Intent contains the existing skill/lifecycle semantic fields, including Work
    and perception choices, with every derived header omitted. Perception's
    source_id, navigation goal.scope and activity interrupt owner are also derived
    only from this selected context. Activity children choose only step/answer;
    their explicit canonical original_root supplies the immutable semantics.
    Limits and a new request ID are caller choices;
    no deadline or budget is inferred or extended. Explicit support IDs supplement
    the chosen primary (for example, first/latest transition observations).
    validate_submission owns the final closed schema and admission constraints;
    the ordinary canonical serializer remains the serialization path.
    """
    if type(snapshot) is not dict or not {"mission_id", "epoch", *_PHASES} <= snapshot.keys():
        raise ContractError("Select a mission status snapshot with explicit phase summaries")
    if scope not in ("new_root", "prompt", "lifecycle", "activity"):
        raise ContractError("Select new_root, prompt, lifecycle or activity scope")
    data = json_object(intent)
    if _DERIVED & data.keys():
        raise ContractError("Intent must omit derived request headers and limits")
    if data.get("procedure") is not None:
        if type(data["procedure"]) is not dict or "use_id" in data["procedure"]:
            raise ContractError("Select a procedure revision/applicability; software derives its root use ID")
        data["procedure"]["use_id"] = "use-" + hashlib.sha256(request_id.encode()).hexdigest()
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
    if data["kind"] == "skill":
        _bind_skill_goal(snapshot, data, scope, source, original_root, limits)
    if view is not None:
        view["source_id"] = primary
    request = validate_submission({**data, "schema": VERSION, "mission_id": snapshot["mission_id"],
        "epoch": snapshot["epoch"], "request_id": request_id, "limits": limits, "phase_id": parent,
        "sources": ([] if primary is None else [primary]) + list(supporting_source_ids), **binding})
    phase = snapshot["lifecycle_phase"]
    if (request["kind"] == "skill" and scope == "lifecycle"
            and snapshot.get("phase") == "paused" and snapshot.get("pause_cause") == "unknown"
            and snapshot.get("unreconciled") == 0 and type(phase) is dict
            and phase.get("operation") == "load" and phase.get("stage") == "awaiting_control"
            and source["observation"]["in_game"]
            and source["observation"]["boundary"]["kind"] == "menu"):
        raise ContractError("The selected Load menu snapshot is still paused after reconciliation. "
            "Explicitly call enactive_lifecycle with operation=load and scope=lifecycle under the "
            "same root, selecting this checkpoint, with no identity Claims or Work, for separate readmission. "
            "Only then may a supported menu dismissal reach actual normal play before identity inspection. "
            "This as-of guidance establishes neither current custody nor freshness or input authority.")
    if (request["kind"] == "skill" and request["skill_kind"] == "activity"
            and scope in ("prompt", "activity") and request["goal"]["step"] == "poll"
            and source["observation"]["boundary"]["kind"] != "activity_poll"):
        raise ContractError("Selected checkpoint is not an activity poll. Inspect the returned visible phase "
            "and choose the current decision under the original root and bounds. "
            "This as-of check establishes neither completion nor freshness or renewed authority.")
    return request
