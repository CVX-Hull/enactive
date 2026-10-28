"""Historical, fail-closed adoption of every retained normal session.

Mission receipts supply provenance; canonical source order supplies chronology.
This projection grants no authority and never reconstructs a process or executor.
EvidenceStore integrity checks may persistently quarantine invalid source evidence.
"""
from __future__ import annotations

from .campaign_memory import CampaignMemory
from .cdda_identity import adoption_identity_refusal
from .contracts import ContractError, EvidenceRef, json_object
from .evidence import EvidenceError, EvidenceStore
from .mission_contracts import (
    effect_reconciliation,
    validate_lifecycle_transition,
    validate_normal_adoption, validate_prompt_result, validate_request, validate_saved_checkpoint,
)
from .mission_ledger import MissionLedger
from .native_receipts import compact_native_ack
from .semantic_controls import dismissal_input
from .cdda_timeline import MAX_TIMELINE_SEGMENTS, GameTimeline, SessionContinuity, game_timeline


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise EvidenceError(reason)


def lifecycle_input_sources(store: EvidenceStore, intent: dict, after_id: str) -> tuple[EvidenceRef, EvidenceRef]:
    """Authenticate the distinct dispatch preflight as well as its endpoints."""
    references = store.historical_references
    sources = {ref.observation_id: ref for ref in references}
    positions = {ref.observation_id: index for index, ref in enumerate(references)}
    identities = (intent["source_before"], intent["preflight_source"], after_id)
    _require(all(identity in sources for identity in identities), "Lifecycle input source is absent from the evidence archive")
    before, preflight, after = (sources[identity] for identity in identities)
    store.observation(before)
    preflight_obs = store.observation(preflight)
    store.observation(after)
    _require(positions[before.observation_id] <= positions[preflight.observation_id] < positions[after.observation_id]
             and preflight.session == before.session
             and (intent["expected_session"], intent["expected_revision"], intent["expected_boundary_id"]) ==
                 (preflight.session, preflight.revision, preflight_obs["boundary"]["id"]),
             "Lifecycle preflight is outside its source interval or differs from dispatch")
    return before, preflight


def identity_inspection_sources(ledger: MissionLedger, store: EvidenceStore, *, inspection_id: str,
                                first: EvidenceRef, screen: EvidenceRef) -> None:
    """Share the retained inspection-input proof with live refusal and history."""
    matches = [p for p in ledger.primitive_records() if p["request_id"] == inspection_id
        and p["intent"]["kind"] == "action" and p["intent"]["value"] == "player_data"
        and p["state"] == "returned" and (p["result"] or {}).get("source_after") == screen.observation_id
        and p["intent"]["expected_session"] == first.session and (p["result"] or {}).get("published") is True]
    _require(len(matches) == 1, "Identity screen has no unique returned player_data primitive")
    primitive = matches[0]
    intent, receipt = primitive["intent"], primitive["result"]
    before, preflight = lifecycle_input_sources(store, intent, screen.observation_id)
    positions = {ref.observation_id: index for index, ref in enumerate(store.historical_references)}
    _require(before.session == first.session and preflight.session == first.session
             and positions[first.observation_id] <= positions[before.observation_id],
             "Identity inspection primitive borrowed an earlier or foreign session source")
    for key, value in {"logical_action_id": primitive["logical_id"],
                       "native_request_id": primitive["native_id"], "transport_disposition": "returned",
                       **{k: intent[k] for k in ("kind", "value", "expected_session", "expected_revision",
                           "expected_boundary_id", "source_before", "preflight_source")}}.items():
        _require(receipt.get(key) == value, "Identity inspection receipt contradicts its primitive")


def owned_transition_sources(ledger: MissionLedger, store: EvidenceStore, proof: dict) -> tuple[EvidenceRef, ...]:
    """Authenticate the owned launch and terminal dispatch before interpreting a source."""
    row = ledger._earlier_request(proof["origin_request_id"], proof["launch_request_id"])
    launch, launched = row["request"], row["result"] or {}
    _require(launch["kind"] == "lifecycle" and launch.get("operation") == "launch"
             and launch.get("phase_id") is None and row["state"] == "completed"
             and launched.get("native_ready") is True
             and (launched.get("process") or {}).get("launch_id") == proof["launch_id"],
             "Transition has no earlier owned launch")
    identities = launched.get("source_ids")
    _require(type(identities) is list and bool(identities), "Owned launch lacks a retained menu")
    sources = {ref.observation_id: ref for ref in store.historical_references}
    refs = []
    for identity in identities:
        _require(type(identity) is str and identity in sources, "Owned launch source is absent from the evidence archive")
        ref = sources[identity]
        obs = store.observation(ref)
        _require(ref.boundary_kind == "menu" and obs["category"] == "MAIN_MENU"
                 and not obs["in_game"] and obs["takeover_generation"] == proof["before_takeover_generation"],
                 "Owned launch baseline differs from the transition")
        refs.append(ref)
    positions = {ref.observation_id: index for index, ref in enumerate(store.historical_references)}
    _require(proof["before_source_id"] in sources and proof["after_source_id"] in sources,
             "Transition source is absent from the evidence archive")
    before, after = sources[proof["before_source_id"]], sources[proof["after_source_id"]]
    before_obs, after_obs = store.observation(before), store.observation(after)
    _require(max(positions[ref.observation_id] for ref in refs) <= positions[before.observation_id]
             < positions[after.observation_id]
             and before_obs["takeover_generation"] == proof["before_takeover_generation"]
             and after_obs["takeover_generation"] == proof["after_takeover_generation"],
             "Transition sources contradict canonical order or takeover baseline")
    lifecycle_input_sources(store, ledger.primitive(proof["terminal_logical_id"])["intent"], after.observation_id)
    return tuple(refs)


def world_identity_source_refusal(ledger: MissionLedger, store: EvidenceStore, *,
                                  request_id: str, adoption: dict) -> str | None:
    """Positive source applicability only; damaged proof/archive inputs stay fatal.

    Live selection uses a reason as caller feedback after its healthy-phase guard;
    historical projection treats the identical predicate as strict rejection.
    """
    adoption = validate_normal_adoption(adoption)
    transition_id = adoption["transition_result_request_id"]
    row, proof = ledger._lifecycle_record(request_id, transition_id, "lifecycle_transition")
    proof = validate_lifecycle_transition(proof)
    ledger._check_prompt_result(transition_id, row["request"], row["result"],
        actor_id=proof["actor_id"], request_state=row["state"])
    launch_refs = owned_transition_sources(ledger, store, proof)
    references = store.historical_references
    positions = {ref.observation_id: index for index, ref in enumerate(references)}
    sources = {ref.observation_id: ref for ref in references}
    first_id = adoption["first_normal_source_id"]
    _require(first_id in sources, "Adoption first normal source is absent from the evidence archive")
    first = sources[first_id]
    observed = store.observation(first)
    _require(first.boundary_kind == "normal_play" and observed["in_game"],
             "Adoption first normal source is not a retained normal boundary")
    _require(positions[first_id] >= positions[proof["after_source_id"]],
             "Adoption first normal source precedes its transition")
    world_id = adoption["world_claim_id"]
    selected = ledger.adoption_claims(request_id, [world_id])
    _require(world_id in selected, "Adoption world identity claim is missing")
    world = selected[world_id]["entry"]
    rows = ledger.request_records()
    phase_sources = {sid for record in rows
        if _phase_member(record["request"], record["request"]["request_id"], adoption["origin_request_id"])
        for sid in record["request"].get("sources", []) + (record["result"] or {}).get("source_ids", [])}
    selected_sources = []
    for identity in world["sources"]:
        _require(identity in sources, "World identity source is absent from the evidence archive")
        ref = sources[identity]
        selected_sources.append((ref, store.observation(ref)))
    launch_position = max(positions[ref.observation_id] for ref in launch_refs)
    if not selected_sources or not all(ref.boundary_kind == "menu"
               and obs["takeover_generation"] == proof["before_takeover_generation"]
               and ref.observation_id in phase_sources
               and launch_position <= positions[ref.observation_id] < positions[first_id]
               for ref, obs in selected_sources):
        return ("World identity was not observed in this owned root phase. Select a retained menu "
            "from this Load/Create root before its first normal boundary that visibly shows the world. "
            "If grounding changes session scope, author a fresh Claim; correction cannot cross scope.")
    return None


def initial_load_menu_sources(ledger: MissionLedger, store: EvidenceStore, *, transition_id: str,
                              first_normal_source_id: str | None = None,
                              through_request_id: str | None = None,
                              allow_pending: bool = False) -> None:
    """Verify the actual initial-menu prefix, including every retained capture.

    Raw dispatch/Resume/QUIT provenance has one ledger owner. This layer adds
    canonical source chronology and the boundary/ACK evidence it cannot inspect.
    Nothing here reconstructs a private phase, lease or game-time anchor.
    """
    chain = ledger.initial_load_menu_chain(transition_id, through_request_id=through_request_id,
        first_normal_source_id=first_normal_source_id, allow_pending=allow_pending)
    proof = ledger.request(transition_id)["result"]["lifecycle_transition"]
    references = store.historical_references
    positions = {ref.observation_id: index for index, ref in enumerate(references)}
    refs = {ref.observation_id: ref for ref in references}

    def source(identity: str) -> tuple[EvidenceRef, dict]:
        _require(identity in refs, "Initial Load menu source is absent")
        return refs[identity], store.observation(refs[identity])

    after, observed = source(proof["after_source_id"])
    before, _ = source(proof["before_source_id"])
    _require(before.boundary_kind == "menu" and after.boundary_kind == "menu"
             and after.session != before.session and observed["in_game"] and observed["paused"]
             and observed["pause_origin"] in ("host", "world_change")
             and positions[before.observation_id] < positions[after.observation_id]
             and not any(ref.boundary_kind == "normal_play"
                         for ref in references[:positions[after.observation_id]]),
             "Provisional menu is not the mission's initial Load entry")

    def owned(ref: EvidenceRef, obs: dict, *, normal: bool = False) -> None:
        _require(ref.session == after.session and obs["in_game"] and obs["status"] == "ready"
                 and not obs["error"] and obs["frame_ok"]
                 and obs["takeover_generation"] == proof["after_takeover_generation"]
                 and obs["pause_origin"] != "human"
                 and ref.boundary_kind == ("normal_play" if normal else "menu")
                 and (not normal or obs["scene"] is not None and not obs["paused"]),
                 "Initial menu prefix left its owned supported session")

    cursor = after
    owned(after, observed)
    for index, primitive in enumerate(chain):
        intent, receipt = primitive["intent"], primitive["result"]
        start, state = source(intent["source_before"])
        preflight, preflight_obs = source(intent["preflight_source"])
        end, end_obs = source(receipt["source_after"])
        _require(positions[cursor.observation_id] <= positions[start.observation_id]
                 <= positions[preflight.observation_id] < positions[end.observation_id],
                 "Initial menu input borrowed a missing, foreign or future source")
        for ref in references[positions[cursor.observation_id]:positions[preflight.observation_id] + 1]:
            obs = store.observation(ref)
            owned(ref, obs)
            _require(store.equivalent(cursor, ref, rule="exact_png_bytes"),
                     "Initial menu source changed outside a returned dismissal")
        _require((intent["expected_session"], intent["expected_revision"], intent["expected_boundary_id"]) ==
                 (preflight.session, preflight.revision, preflight_obs["boundary"]["id"])
                 and compact_native_ack(end_obs) == receipt["native_ack"],
                 "Initial menu input differs from its actual retained preflight or ACK")
        normal = end.observation_id == first_normal_source_id
        owned(end, end_obs, normal=normal)
        if index == 0:
            _require(state["paused"] and not end_obs["paused"]
                     and state["category"] == end_obs["category"] and state["ui"] == end_obs["ui"]
                     and start.frame_sha256 == end.frame_sha256,
                     "Initial menu Resume changed its visible receiver")
        else:
            _require(not state["paused"] and not end_obs["paused"],
                     "Initial menu dismissal lost its readmitted receiver")
            _require((intent["kind"], intent["value"]) == dismissal_input(state)
                     and dismissal_input(state) == dismissal_input(preflight_obs),
                     "Initial menu input differs from its registered dismissal")
        # No intermediate retained capture may silently establish another first
        # normal source, even when a later ACK is normal in the same session.
        for ref in references[positions[preflight.observation_id] + 1:positions[end.observation_id]]:
            owned(ref, store.observation(ref))
        cursor = end
    if first_normal_source_id is not None:
        first, _ = source(first_normal_source_id)
        _require(not any(ref.boundary_kind == "normal_play" for ref in references[:positions[first.observation_id]]),
                 "Initial menu dismissal skipped the earliest canonical normal source")
    else:
        # Interrupted histories may contain only this one menu proof and a
        # verified returned prefix. A later snapshot cannot repair missing input.
        for ref in references[positions[cursor.observation_id]:]:
            owned(ref, store.observation(ref))
            _require(store.equivalent(cursor, ref, rule="exact_png_bytes"),
                     "Interrupted initial menu history has an unauthenticated capture")


def adopted_timeline(ledger: MissionLedger, store: EvidenceStore) -> GameTimeline | None:
    """Verify complete lifecycle/identity provenance before composing game time.

    Callers serialize writes to both stores. Reading historical observations checks
    bytes and sticky disputes, potentially persisting a quarantine when evidence
    is invalid, without refreshing observations or acquiring authority.
    """
    if not isinstance(ledger, MissionLedger) or not isinstance(store, EvidenceStore):
        raise ContractError("Adoption requires a MissionLedger and EvidenceStore")
    try:
        return _project(ledger, store)
    except ContractError as exc:
        raise EvidenceError(f"Invalid durable lifecycle evidence: {exc}") from exc


def candidate_timeline(ledger: MissionLedger, store: EvidenceStore, *, request_id: str,
                       result: dict) -> GameTimeline | None:
    """Check one pending real adoption result before its immutable publication.

    Only this named unsettled lifecycle request can be completed prospectively.
    No request, primitive or memory row is replaced or written. Source integrity
    checks may persistently quarantine invalid evidence; observations are never
    refreshed or promoted.
    """
    if not isinstance(ledger, MissionLedger) or not isinstance(store, EvidenceStore):
        raise ContractError("Candidate adoption requires a MissionLedger and EvidenceStore")
    if type(request_id) is not str or not request_id or type(result) is not dict:
        raise ContractError("Candidate adoption requires a request identity and typed result")
    prospective = json_object(result)
    rows = ledger.request_records()
    matches = [row for row in rows if row["request"]["request_id"] == request_id]
    _require(len(matches) == 1, "Candidate adoption request does not exist")
    target = matches[0]
    _require(target["state"] in ("accepted", "running") and target["result"] is None,
             "Candidate adoption cannot replace a settled request")
    _require(target["request"]["kind"] == "lifecycle"
             and target["request"]["operation"] in ("create", "load")
             and "normal_adoption" in prospective, "Candidate requires a pending create/load adoption result")
    target.update(state="completed", result=prospective)
    try:
        issued, consumed = ledger._handoffs()
        actors = [(0, ledger.admission.player_id)] + sorted(
            (issued[identity]["epoch"], ledger.request(claim)["result"]["player_id"])
            for identity, claim in consumed.items())
        actor = next(player for epoch, player in reversed(actors) if epoch <= target["request"]["epoch"])
        ledger._check_prompt_result(request_id, target["request"], prospective,
            actor_id=actor, request_state="completed")
        return _project(ledger, store, rows=rows)
    except ContractError as exc:
        raise EvidenceError(f"Invalid candidate lifecycle evidence: {exc}") from exc


def _project(ledger: MissionLedger, store: EvidenceStore, *, rows: tuple[dict, ...] | None = None) -> GameTimeline | None:
    references = store.historical_references
    refs = {ref.observation_id: ref for ref in references}
    positions = {ref.observation_id: index for index, ref in enumerate(references)}
    rows = ledger.request_records() if rows is None else rows
    for row in rows:
        validate_request(row["request"])
    requests = {row["request"]["request_id"]: row for row in rows}
    order = {row["request"]["request_id"]: index for index, row in enumerate(rows)}
    issued, consumed = ledger._handoffs()
    actors = [(0, ledger.admission.player_id)] + sorted(
        (issued[identity]["epoch"], requests[claim]["result"]["player_id"])
        for identity, claim in consumed.items())
    primitives = {p["logical_id"]: p for p in ledger.primitive_records()}
    claim_rows = {row["entry"]["id"]: row for row in ledger.memory_records("claim")}
    # The ledger validates immutable entries on insertion/reopen and returns fresh copies.
    claims = {identity: row["entry"] for identity, row in claim_rows.items()}
    # Identity selection shares the campaign reducer's correction/partial order.
    identity_ids = {identity for identity, claim in claims.items()
                    if claim["key"]["property"] == "identity" and claim["key"]["unit"] == "name"}
    frontiers, retired = CampaignMemory._frontier(claims, selected_ids=identity_ids)
    proofs: dict[str, dict[str, dict]] = {}
    validators = {"lifecycle_transition": validate_lifecycle_transition,
                  "normal_adoption": validate_normal_adoption,
                  "saved_checkpoint": validate_saved_checkpoint}
    for key, validator in validators.items():
        proofs[key] = {}
        for row in rows:
            result = row["result"] or {}
            if key in result:
                _require(row["state"] == "completed", "Lifecycle proof requires a completed immutable result")
                proofs[key][row["request"]["request_id"]] = validator(result[key])

    def source(identity: str) -> tuple[EvidenceRef, dict]:
        _require(identity in refs, "Lifecycle proof source is absent from the evidence archive")
        ref = refs[identity]
        return ref, store.observation(ref)

    def request(identity: str) -> dict:
        _require(identity in requests, "Lifecycle proof request is missing")
        return requests[identity]["request"]

    def phase_member(identity: str, root_id: str) -> bool:
        data = request(identity)
        return identity == root_id or (data.get("phase_id") == root_id and order[identity] > order[root_id])

    for key, records in proofs.items():
        for identity, proof in records.items():
            root_id = proof["origin_request_id"]
            root, data = request(root_id), request(identity)
            _require(data["kind"] == "lifecycle" and data.get("phase_id") == root_id
                     and order[root_id] < order[identity], "Lifecycle proofs require a later direct lifecycle child")
            phase_value = requests[identity]["result"].get("phase")
            _require(type(phase_value) is dict, "Lifecycle proof lacks a typed phase receipt")
            actor = next(player for epoch, player in reversed(actors) if epoch <= data["epoch"])
            phase = validate_prompt_result(phase_value, request=data, root=root, actor_id=actor)
            expected_stage = "complete" if key != "lifecycle_transition" or "saved_checkpoint" in (
                requests[identity]["result"] or {}) else ("awaiting_identity" if data["operation"] in ("create", "load") else "awaiting_control")
            if (key == "lifecycle_transition" and proof["operation"] == "load"
                    and source(proof["after_source_id"])[0].boundary_kind == "menu"):
                ledger._initial_load_root(root_id)
                expected_stage = "awaiting_control"
            _require(phase["stage"] == expected_stage, "Lifecycle proof has the wrong phase stage")
            for sid in phase["source_ids"]:
                source(sid)

    def transition(identity: str) -> dict:
        _require(identity in proofs["lifecycle_transition"], "Lifecycle transition result is missing")
        proof = proofs["lifecycle_transition"][identity]
        root_id = proof["origin_request_id"]
        root = request(root_id)
        terminal_id = proof["terminal_request_id"]
        request(terminal_id)
        _require(root["kind"] == "lifecycle" and root.get("phase_id") is None
                 and root["operation"] == proof["operation"]
                 and root["world"] == ledger.admission.scenario.world
                 and root["character"] == ledger.admission.scenario.character
                 and phase_member(identity, root_id) and phase_member(terminal_id, root_id)
                 and order[terminal_id] < order[identity]
                 and root["epoch"] == proof["origin_epoch"]
                 and request(terminal_id)["epoch"] == proof["origin_epoch"]
                 and request(identity)["epoch"] == proof["reconciled_epoch"],
                 "Lifecycle transition lost its immutable phase, scenario, epoch or request order")
        launch_refs = owned_transition_sources(ledger, store, proof)
        launch_sources = [ref.observation_id for ref in launch_refs]
        before, before_obs = source(proof["before_source_id"])
        after, after_obs = source(proof["after_source_id"])
        phase = requests[identity]["result"]["phase"]
        _require(all(phase[key] == proof[field] for key, field in {
            "launch_request_id": "launch_request_id", "launch_id": "launch_id", "actor_id": "actor_id",
            "controller_boot_id": "controller_boot_id", "operator_pause_generation": "operator_pause_generation",
            "takeover_generation": "after_takeover_generation"}.items())
            and {before.observation_id, after.observation_id, *launch_sources} <= set(phase["source_ids"]),
            "Transition differs from its retained owned phase audit")
        _require(proof["terminal_logical_id"] in primitives, "Transition terminal primitive is missing")
        primitive = primitives[proof["terminal_logical_id"]]
        intent, receipt = primitive["intent"], primitive["result"] or {}
        _require(primitive["request_id"] == terminal_id and primitive["state"] in ("returned", "unknown")
                 and primitive["native_id"] == proof["native_request_id"]
                 and intent["kind"] in ("action", "direct")
                 and intent["source_before"] == before.observation_id
                 and receipt.get("published") is True,
                 "Transition has no matching published terminal primitive")
        for key, value in {"logical_action_id": primitive["logical_id"], "native_request_id": primitive["native_id"],
                           "transport_disposition": primitive["state"], **{k: intent[k] for k in
                           ("kind", "value", "expected_session", "expected_revision", "expected_boundary_id", "source_before", "preflight_source")}}.items():
            _require(receipt.get(key) == value, "Transition primitive receipt contradicts its immutable intent")
        if proof["operation"] == "create":
            from .creation_provenance import creation_input_chain, validate_creation_sources
            chain = creation_input_chain(tuple(requests.values()), tuple(primitives.values()),
                root_id=root_id, terminal_request_id=terminal_id, terminal_logical_id=proof["terminal_logical_id"])
            validate_creation_sources(chain, store, terminal_before=before)
        if primitive["state"] == "unknown":
            effect = primitive["effect"] or {}
            _require(effect == effect_reconciliation(proof, sources=(before.observation_id, after.observation_id),
                     note=f"Observed lifecycle {proof['operation']} transition after {proof['native_request_id']}; original ACK remains unknown"),
                     "Unknown ACK has no independent retained effect")
            for sid in effect["sources"]:
                source(sid)
        else:
            _require(receipt.get("source_after") == after.observation_id, "Returned transition points to another after-source")
        if proof["operation"] == "save":
            _require(after.boundary_kind == "menu" and not after_obs["in_game"], "Save did not reach a menu")
        elif proof["operation"] == "load" and after.boundary_kind == "menu":
            ledger._initial_load_root(root_id)
            _require(before.boundary_kind == "menu" and after_obs["in_game"]
                     and after.session != before.session
                     and not any(ref.boundary_kind == "normal_play"
                                 for ref in references[:positions[after.observation_id]]),
                     "Only initial Load may enter an owned provisional menu")
        else:
            _require(before.boundary_kind == "menu" and after.boundary_kind == "normal_play"
                     and after_obs["in_game"], "Create/load did not enter normal play from a menu")
        return proof

    # Authenticate every proof, including save checkpoints after the final span.
    for identity in proofs["lifecycle_transition"]:
        transition(identity)
    segments: list[list[EvidenceRef]] = []
    seen: set[str] = set()
    for ref in references:
        if ref.boundary_kind != "normal_play":
            continue
        if not segments or ref.session != segments[-1][0].session:
            _require(ref.session not in seen and len(segments) < MAX_TIMELINE_SEGMENTS,
                     "Normal session returned or exceeded the timeline bound")
            seen.add(ref.session)
            segments.append([ref, ref])
        else:
            segments[-1][1] = ref
    adoptions = proofs["normal_adoption"]
    _require(len(adoptions) == len(segments), "Every normal-session segment requires exactly one adoption")
    if not segments:
        _require(not proofs["saved_checkpoint"] and len(proofs["lifecycle_transition"]) <= 1,
                 "Lifecycle proofs cannot substitute for absent normal sessions")
        if proofs["lifecycle_transition"]:
            initial_load_menu_sources(ledger, store, transition_id=next(iter(proofs["lifecycle_transition"])))
        return None

    def identity_claim(identity: str, *, subject: str, scope: dict, value: str, result_id: str) -> dict:
        _require(identity in claims, "Adoption identity claim is missing")
        claim = claims[identity]
        event_id = claim_rows[identity]["event_id"]
        remembered = request(event_id)
        _require(order[event_id] < order[result_id] and remembered["kind"] in ("remember", "correct")
                 and remembered["entry_type"] == "claim" and remembered["entry"] == claim,
                 "Identity claim has no earlier immutable memory request")
        reason = adoption_identity_refusal(claim, subject=subject, scope=scope, name=value,
            claims=claims, frontiers=frontiers, retired=retired)
        _require(reason is None, reason or "Invalid identity applicability")
        if claim["supersedes"]:
            _require(remembered["kind"] == "correct"
                     and set(remembered["retired_ids"]) == set(claim["supersedes"]),
                     "Corrected identity lacks its exact explicit retirement request")
        observed = []
        for sid in claim["sources"]:
            ref, obs = source(sid)
            _require(ref.session == scope["session"], "Identity borrowed another session's source")
            observed.append(dict(revision=ref.revision, turn=ref.turn))
        _require(claim["observed_time"] in observed, "Identity observed order has no retained source")
        return claim

    ordered_adoptions = list(adoptions.items())
    adoption_by_id = dict(ordered_adoptions)
    used_transitions = [adoption["transition_result_request_id"] for adoption in adoptions.values()]
    used_transitions += [saved["transition_result_request_id"] for saved in proofs["saved_checkpoint"].values()]
    _require(len(set(used_transitions)) == len(used_transitions)
             and set(used_transitions) == set(proofs["lifecycle_transition"]),
             "Every lifecycle transition requires exactly one adoption or saved checkpoint")
    saved_adoptions = [saved["adoption_result_request_id"] for saved in proofs["saved_checkpoint"].values()]
    _require(len(saved_adoptions) == len(set(saved_adoptions)), "A normal segment cannot have duplicate saved checkpoints")
    for index, (result_id, adoption) in enumerate(ordered_adoptions):
        first, last = segments[index]
        proof = transition(adoption["transition_result_request_id"])
        root_id = adoption["origin_request_id"]
        expected_scope = dict(mission_id=ledger.admission.mission_id, session=first.session, coordinate_epoch=index)
        initial_operation = "load" if ledger.admission.scenario.mode == "load" else "create"
        _require(proof["origin_request_id"] == root_id and proof["operation"] == (initial_operation if index == 0 else "load")
                 and phase_member(result_id, root_id)
                 and order[adoption["transition_result_request_id"]] <= order[result_id]
                 and adoption["scope"] == expected_scope
                 and adoption["first_normal_source_id"] == first.observation_id,
                 "Adoption must cover the exact earliest normal source in canonical segment order")
        if proof["after_source_id"] != first.observation_id:
            _require(index == 0 and proof["operation"] == "load"
                     and adoption["saved_checkpoint_request_id"] is None,
                     "Only the initial Load may reach normal play through menus")
            initial_load_menu_sources(ledger, store, transition_id=adoption["transition_result_request_id"],
                first_normal_source_id=first.observation_id,
                through_request_id=adoption["identity_inspect_request_id"])
        checkpoint, checkpoint_obs = source(adoption["checkpoint_source_id"])
        adoption_phase = requests[result_id]["result"]["phase"]
        _require(all(adoption_phase[key] == proof[field] for key, field in {
            "launch_request_id": "launch_request_id", "launch_id": "launch_id",
            "actor_id": "actor_id", "operator_pause_generation": "operator_pause_generation",
            "controller_boot_id": "controller_boot_id", "takeover_generation": "after_takeover_generation"}.items()),
            "Adoption changed its owned process or takeover baseline")
        _require(checkpoint.boundary_kind == "normal_play" and checkpoint.session == first.session
                 and checkpoint_obs["takeover_generation"] == proof["after_takeover_generation"]
                 and positions[first.observation_id] <= positions[checkpoint.observation_id] <= positions[last.observation_id],
                 "Adoption checkpoint is outside its normal segment")
        launch = requests[proof["launch_request_id"]]["result"]
        _require(adoption["world_claim_id"] in claims, "Adoption world identity claim is missing")
        world_scope = dict(expected_scope, session=claims[adoption["world_claim_id"]]["scope"]["session"])
        identity_claim(adoption["world_claim_id"], subject="world", scope=world_scope,
                               value=ledger.admission.scenario.world, result_id=result_id)
        reason = world_identity_source_refusal(ledger, store, request_id=result_id, adoption=adoption)
        _require(reason is None, reason or "Invalid world source applicability")
        character = identity_claim(adoption["character_claim_id"], subject="character", scope=expected_scope,
                                   value=ledger.admission.scenario.character, result_id=result_id)
        inspect_id = adoption["identity_inspect_request_id"]
        inspect = request(inspect_id)
        inspected = requests[inspect_id]["result"] or {}
        screen_id = inspected.get("identity_screen_source_id")
        _require(inspect["kind"] == "skill" and inspect.get("skill_kind") == "inspect"
                 and inspect.get("goal") == {"purpose": "character_identity"} and inspect.get("phase_id") == root_id
                 and order[root_id] < order[inspect_id] < order[result_id]
                 and requests[inspect_id]["state"] == "completed"
                 and screen_id in inspected.get("source_ids", []) and character["sources"] == [screen_id],
                 "Character identity lacks its exact correlated inspection")
        screen, obs = source(screen_id)
        _require(screen.boundary_kind == "menu" and obs["category"] == "PLAYER_INFO" and obs["in_game"]
                 and obs["takeover_generation"] == proof["after_takeover_generation"]
                 and positions[first.observation_id] < positions[screen_id] < positions[checkpoint.observation_id],
                 "Character inspection is outside its adoption checkpoints")
        identity_inspection_sources(ledger, store, inspection_id=inspect_id, first=first, screen=screen)
        if index == 0:
            _require(adoption["saved_checkpoint_request_id"] is None, "Initial entry cannot borrow a saved checkpoint")
        else:
            saved_id = adoption["saved_checkpoint_request_id"]
            _require(saved_id in proofs["saved_checkpoint"], "Reload lacks its exact preceding saved checkpoint")
            saved = proofs["saved_checkpoint"][saved_id]
            _require(saved["adoption_result_request_id"] == ordered_adoptions[index - 1][0]
                     and saved["normal_endpoint_source_id"] == segments[index - 1][1].observation_id
                     and order[saved_id] < order[root_id], "Reload skipped or borrowed a prior saved checkpoint")
    for result_id, saved in proofs["saved_checkpoint"].items():
        proof = transition(saved["transition_result_request_id"])
        adoption_id = saved["adoption_result_request_id"]
        _require(adoption_id in adoption_by_id, "Saved checkpoint refers to an absent adoption")
        adoption = adoption_by_id[adoption_id]
        entry_transition = transition(adoption["transition_result_request_id"])
        _require(all(proof[key] == entry_transition[key] for key in ("launch_request_id", "launch_id")),
                 "Save transition changed the normal adoption's owned launch")
        saved_phase = requests[result_id]["result"]["phase"]
        _require(all(saved_phase[key] == proof[field] for key, field in {
            "launch_request_id": "launch_request_id", "launch_id": "launch_id", "actor_id": "actor_id",
            "controller_boot_id": "controller_boot_id", "operator_pause_generation": "operator_pause_generation",
            "takeover_generation": "after_takeover_generation"}.items()),
            "Saved checkpoint changed its transition's owned phase audit")
        index = next(i for i, (rid, _) in enumerate(ordered_adoptions) if rid == adoption_id)
        endpoint, _ = source(saved["normal_endpoint_source_id"])
        menu, _ = source(saved["menu_source_id"])
        prior_normal = [ref for ref in references[:positions[menu.observation_id]] if ref.boundary_kind == "normal_play"]
        _require(proof["operation"] == "save" and saved["origin_request_id"] == proof["origin_request_id"]
                 and phase_member(result_id, saved["origin_request_id"])
                 and order[adoption_id] < order[saved["origin_request_id"]]
                 and order[saved["transition_result_request_id"]] <= order[result_id]
                 and saved["menu_source_id"] == proof["after_source_id"]
                 and endpoint == segments[index][1] and bool(prior_normal) and prior_normal[-1] == endpoint
                 and positions[adoption["checkpoint_source_id"]] <= positions[endpoint.observation_id]
                 and positions[endpoint.observation_id] <= positions[proof["before_source_id"]] < positions[menu.observation_id],
                 "Saved checkpoint must equal the exact final old-normal endpoint before its menu")
        save_inputs = [p for p in primitives.values() if _phase_member(request(p["request_id"]), p["request_id"], saved["origin_request_id"])
                       and p["state"] == "returned" and p["intent"]["kind"] == "action"
                       and p["intent"]["value"] == "save"
                       and p["intent"]["preflight_source"] == endpoint.observation_id]
        _require(len(save_inputs) == 1, "Saved endpoint has no unique returned save-action preflight")
        save_input = save_inputs[0]
        save_intent, save_receipt = save_input["intent"], save_input["result"] or {}
        _require(type(save_input["native_id"]) is str and bool(save_input["native_id"]),
                 "Returned save input has no published native identity")
        for key, value in {"logical_action_id": save_input["logical_id"], "native_request_id": save_input["native_id"],
                           "transport_disposition": "returned", **{key: save_intent[key] for key in
                           ("kind", "value", "expected_session", "expected_revision", "expected_boundary_id", "source_before", "preflight_source")}}.items():
            _require(save_receipt.get(key) == value, "Save receipt contradicts its immutable primitive intent")
        save_before, save_before_obs = source(save_intent["source_before"])
        save_after_id = (save_input["result"] or {}).get("source_after")
        _require(save_after_id in refs, "Save action lost its retained confirmation menu")
        save_after, save_after_obs = source(save_after_id)
        _require(save_before.session == endpoint.session == save_after.session
                 and save_input["intent"]["expected_session"] == endpoint.session
                 and save_intent["expected_revision"] == save_before.revision
                 and save_intent["expected_boundary_id"] == save_before_obs["boundary"]["id"]
                 and save_before.boundary_kind == "normal_play" and save_after.boundary_kind == "menu"
                 and save_after_obs["in_game"] and (save_input["result"] or {}).get("published") is True
                 and positions[save_before.observation_id] <= positions[endpoint.observation_id]
                 < positions[save_after_id] <= positions[proof["before_source_id"]],
                 "Saved endpoint is outside the returned normal save-action interval")
        _require(all(ref.session == endpoint.session and ref.boundary_kind == "menu"
            and source(ref.observation_id)[1]["in_game"]
            for ref in references[positions[save_after_id]:positions[proof["before_source_id"]] + 1]),
            "Save confirmation left its original adopted session before completion")
    links = tuple(SessionContinuity(segments[i - 1][1], segments[i][0]) for i in range(1, len(segments)))
    return game_timeline(store, links)


def _phase_member(data: dict, identity: str, root_id: str) -> bool:
    """Select immutable direct-phase source annotations only."""
    return identity == root_id or data.get("phase_id") == root_id
