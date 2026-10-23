"""Registered character lifecycle, called only by MissionRuntime's one writer.

The runtime retains process/controller custody and charges every actual dispatch.
This component owns only private phase/expected-effect state. Durable records are
historical evidence; neither this object nor its phase is reconstructed on reopen.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import TYPE_CHECKING

from .controller import ControlError
from .gameplay.contracts import ContractError, EvidenceRef, canonical
from .gameplay.evidence import MAX_FRAME_BYTES, CapacityReservation, EvidenceError, same_native_state
from .gameplay.interaction import MenuOutcome, MenuSkill
from .gameplay.mission_contracts import VERSION, InputObservation, SourceRevalidation
from .gameplay.mission_ledger import BudgetError, LedgerError
from .gameplay.input_contracts import ControlIntent, ControlOutcome
from .gameplay.semantic_controls import SemanticControlSkill
from .gameplay.ordinary_input import OrdinaryInputSkill

if TYPE_CHECKING:
    from .mission_runtime import MissionRuntime, _OwnedLaunch, _ResumeIntent, _Work

_CHARACTER = frozenset({"NEW_CHAR_POINTS", "NEW_CHAR_STATS", "NEW_CHAR_TRAITS", "NEW_CHAR_PROFESSIONS",
    "NEW_CHAR_SKILLS", "NEW_CHAR_SCENARIOS", "NEW_CHAR_DESCRIPTION"})
_SETUP = _CHARACTER | {"MAIN_MENU", "PICK_WORLD_DIALOG", "WORLDGEN_CONFIRM_DIALOG", "MODMANAGER_DIALOG",
    "STRING_INPUT", "UILIST", "YESNO"}
_POINTS_QUESTION = "Remaining points will be discarded, are you sure you want to proceed?"


class LifecycleRequestRefusal(EvidenceError):
    """The chosen request is stale; no input or authority change occurred."""


@dataclass(frozen=True)
class NormalPhase:
    root_id: str
    checkpoint: EvidenceRef
    launch: _OwnedLaunch
    actor_id: str
    epoch: int
    operation: str
    stage: str = "awaiting_control"
    first_normal: EvidenceRef | None = None
    transition_request: str | None = None
    identity_inspect: str | None = None
    identity_screen: EvidenceRef | None = None
    saved_checkpoint: str | None = None


@dataclass(frozen=True)
class _TransitionCandidate:
    phase: NormalPhase
    logical_id: str
    native_request: dict
    reservation: CapacityReservation | None = None
    first_after: EvidenceRef | None = None
    latest_after: EvidenceRef | None = None
    diagnostic_only: bool = False


class RegisteredLifecycle:
    def __init__(self, runtime: MissionRuntime):
        self.runtime = runtime
        self.phase: NormalPhase | None = None
        self.candidate: _TransitionCandidate | None = None
        self.lineage: tuple[str, int] | None = None

    def reset(self) -> None:
        self.phase, self.candidate, self.lineage = None, None, None

    def revoke(self) -> None:
        # An unknown transition retains diagnostic correlation, never input state.
        self.phase = None

    def _install(self, work: _Work, phase: NormalPhase, *, previous: NormalPhase | None = None) -> NormalPhase:
        with self.runtime._metadata:
            self.runtime._check_cancelled(work)
            if previous is not None and self.phase is not previous:
                raise ControlError("Lifecycle phase advancement superseded by Pause")
            self.phase = phase
        return phase

    def launch_mark(self, mark: tuple[str, int], request_id: str) -> None:
        r = self.runtime
        if self.lineage is None:
            if any(row["request"].get("operation") == "launch" and row["request"]["request_id"] != request_id
                   for row in r._ledger.request_records()):
                raise ControlError("Reopen cannot reconstruct lifecycle continuation consent")
            self.lineage = mark
        if mark != self.lineage:
            raise ControlError("Original lifecycle operator mark changed; explicit user readmission required")

    def _source(self, identity: str) -> EvidenceRef:
        for ref in self.runtime._store.historical_references:
            if ref.observation_id == identity:
                self.runtime._store.observation(ref)
                return ref
        raise EvidenceError("Lifecycle source is unavailable")

    def _owned(self) -> _OwnedLaunch:
        r = self.runtime
        launch = r._owned_launch
        if launch is None or r._native is None or r._lost_process_custody:
            raise ControlError("Lifecycle requires this runtime's retained owned child")
        r._native_facts = r._native.status()
        if (not r._native_facts["running"] or r._native_facts["launch_id"] != launch.launch_id
                or launch.operator_mark != r._operator_mark() or self.lineage != launch.operator_mark):
            raise ControlError("Lifecycle child or original operator lineage changed")
        return launch

    def summary(self) -> dict | None:
        if self.candidate is not None and self.candidate.diagnostic_only:
            return None
        phase = self.phase if self.phase is not None else None if self.candidate is None else self.candidate.phase
        if phase is None:
            return None
        checkpoint = phase.checkpoint if self.candidate is None else self.candidate.latest_after or phase.checkpoint
        root = self.runtime._ledger.request(phase.root_id)
        return {"origin_request_id": phase.root_id, "operation": phase.operation,
            "stage": "awaiting_transition" if self.candidate is not None else phase.stage,
            "remaining_limits": {
                "wall_seconds": max(0, root["deadline"] - self.runtime._wall()),
                "primitives": max(0, root["request"]["limits"]["primitives"]
                    - self.runtime._ledger._phase_primitive_count(phase.root_id))},
            "checkpoint_id": checkpoint.observation_id, "grants_authority": False}

    def normal_after_launch(self) -> bool:
        r = self.runtime
        if r._owned_launch is None:
            raise ControlError("No owned launch provenance")
        source_ids = r._ledger.request(r._owned_launch.request_id)["result"]["source_ids"]
        refs = r._store.historical_references
        position = max(index for index, ref in enumerate(refs) if ref.observation_id in source_ids)
        return any(ref.boundary_kind == "normal_play" for ref in refs[position + 1:])

    def saved_exit_checkpoint(self) -> str | None:
        r = self.runtime
        if r._owned_launch is None:
            return None
        refs = r._store.historical_references
        positions = {ref.observation_id: index for index, ref in enumerate(refs)}
        normals = [ref for ref in refs if ref.boundary_kind == "normal_play"]
        for row in reversed(r._ledger.request_records()):
            if row["state"] != "completed" or row["result"] is None or "saved_checkpoint" not in row["result"]:
                continue
            saved = row["result"]["saved_checkpoint"]
            transition = r._ledger.request(saved["transition_result_request_id"])["result"]["lifecycle_transition"]
            if transition["launch_id"] != r._owned_launch.launch_id or transition["launch_request_id"] != r._owned_launch.request_id:
                continue
            if (not normals or normals[-1].observation_id != saved["normal_endpoint_source_id"]
                    or any(ref.boundary_kind == "normal_play" for ref in refs[positions[saved["menu_source_id"]] + 1:])):
                return None
            r._require_normal_adoption(normals[-1])
            self._source(saved["menu_source_id"])
            return row["request"]["request_id"]
        return None

    def receipt(self, phase: NormalPhase, stage: str, *, extra: tuple[EvidenceRef, ...] = (),
                epoch: int | None = None) -> dict:
        r = self.runtime
        sources = list(dict.fromkeys((*r._ledger.request(phase.launch.request_id)["result"]["source_ids"],
            *r._ledger.request(phase.root_id)["request"]["sources"],
            *(ref.observation_id for ref in (phase.first_normal, phase.identity_screen, phase.checkpoint, *extra) if ref is not None))))
        if len(sources) > 8:
            raise LedgerError("Lifecycle audit source ceiling exhausted")
        return {"schema": VERSION, "record_type": "PhaseReceipt", "phase_kind": "lifecycle",
            "operation": phase.operation, "origin_request_id": phase.root_id, "stage": stage,
            "epoch": phase.epoch if epoch is None else epoch, "actor_id": phase.actor_id,
            "controller_boot_id": phase.launch.operator_mark[0],
            "operator_pause_generation": phase.launch.operator_mark[1],
            "takeover_generation": phase.launch.takeover_generation, "source_ids": sources,
            "continuity": None, "launch_request_id": phase.launch.request_id, "launch_id": phase.launch.launch_id,
            "grants_authority": False}

    def retain_after(self, reference: EvidenceRef) -> None:
        r = self.runtime
        r._current = reference
        r._bindings.clear()
        r._map = None
        try:
            r._update_game_time()
        except EvidenceError:
            r._game_cost = None
        r._record("mission_lifecycle_source", {"source": reference.to_dict(), "grants_authority": False})

    def retain_diagnostic(self, reference: EvidenceRef) -> None:
        r, candidate = self.runtime, self.candidate
        r._current = reference
        r._bindings.clear()
        r._map = None
        r._record("mission_lifecycle_diagnostic", {"source": reference.to_dict(),
            "origin_request_id": candidate.phase.root_id, "logical_action_id": candidate.logical_id,
            "native_request_id": candidate.native_request["id"],
            "source_before": candidate.phase.checkpoint.observation_id, "grants_authority": False})

    def _budget(self, phase: NormalPhase) -> None:
        if phase.first_normal is None:
            return
        r = self.runtime
        first = r._store.observation(phase.first_normal)
        refs = [ref for ref in r._store.historical_references if ref.boundary_kind == "normal_play"
            and ref.session == phase.first_normal.session]
        latest = refs[-1]
        r._store.observation(latest)
        if latest.turn < first["scene"]["turn"] or latest.turn - phase.first_normal.turn > r._ledger.request(phase.root_id)["request"]["limits"]["game_seconds"]:
            raise BudgetError("Original provisional lifecycle game-time ceiling exceeded")

    def _paused_identity_diagnostic(self, phase: NormalPhase, ledger: dict, live: tuple) -> None:
        """Validate historical effect proof without activating or acquiring a lease."""
        r = self.runtime
        if (phase.operation not in ("create", "load") or phase.stage != "awaiting_identity"
                or phase.first_normal is None or phase.transition_request is None
                or phase.checkpoint.boundary_kind != "normal_play"
                or phase.checkpoint.session != phase.first_normal.session
                or ledger["pause_cause"] != "unknown" or r._lease is not None
                or live[3] is not None or live[5] or not live[4] or live[0] is None
                or not live[0]["paused"] or live[0]["pause_origin"] not in ("world_change", "host")
                or any(row["state"] in ("prepared", "published") for row in r._ledger.primitive_records())):
            raise ControlError("Paused lifecycle observation requires quiescent provisional identity scope")
        transition = r._ledger.request(phase.transition_request)
        proof = None if transition["result"] is None else transition["result"].get("lifecycle_transition")
        if transition["state"] != "completed" or proof is None:
            raise ControlError("Paused lifecycle observation requires a committed transition")
        # Reuse the ledger's complete root/launch/terminal UUID/effect validator;
        # neither a matching source ID nor an unreconciled count alone suffices.
        r._ledger._check_lifecycle_transition(phase.transition_request, transition["request"], proof, phase.actor_id)
        expected = dict(operation=phase.operation, origin_request_id=phase.root_id,
            launch_request_id=phase.launch.request_id, launch_id=phase.launch.launch_id,
            after_source_id=phase.first_normal.observation_id, reconciled_epoch=phase.epoch,
            actor_id=phase.actor_id, controller_boot_id=phase.launch.operator_mark[0],
            operator_pause_generation=phase.launch.operator_mark[1],
            after_takeover_generation=phase.launch.takeover_generation)
        if any(proof[key] != value for key, value in expected.items()):
            raise ControlError("Paused lifecycle observation lost its exact committed transition lineage")

    def guard(self, work: _Work, phase: NormalPhase, proposal: ControlIntent | _ResumeIntent | None = None,
              *, diagnostic: bool = False, ordinary: bool = False) -> None:
        r = self.runtime
        r._check_cancelled(work)
        launch = self._owned()
        ledger = r._ledger.snapshot(now=r._wall())
        state = r._store.observation(phase.checkpoint)
        live = r._live()
        actual = live[0]
        # Controller preflight obtains a newer timestamp/frame path. Exact
        # encoded pixels and complete native state are compared by _dispatch's
        # retained-equivalence callback, not by whole-dictionary clock equality.
        same_boundary = same_native_state(actual, state)
        if ordinary or proposal is not None and proposal.kind == "direct":
            same_boundary = (actual is not None and actual["session"] == state["session"]
                and actual["takeover_generation"] == state["takeover_generation"]
                and actual["boundary"]["control_generation"] == state["boundary"]["control_generation"]
                and actual["pause_origin"] == state["pause_origin"] and actual["paused"] == state["paused"])
        paused_diagnostic = diagnostic and ledger["phase"] == "paused"
        if diagnostic and proposal is not None:
            raise ControlError("Diagnostic lifecycle observation cannot authorize an input")
        if paused_diagnostic:
            self._paused_identity_diagnostic(phase, ledger, live)
        if (self.phase is not phase or phase.launch.launch_id != launch.launch_id
                or phase.epoch != ledger["epoch"] or phase.epoch != work.request["epoch"]
                or phase.actor_id != ledger["player_id"] or ledger["unreconciled"]
                or (ledger["phase"] != "active" and not paused_diagnostic) or not ledger["clock_valid"]
                or r._current != phase.checkpoint or not same_boundary
                or state["takeover_generation"] != launch.takeover_generation or state["pause_origin"] == "human"):
            raise ControlError("Lifecycle phase lost its exact source, actor, epoch, accounting or operator lineage")
        self._budget(phase)
        if proposal is None:
            return
        if proposal.before != phase.checkpoint:
            raise EvidenceError("Lifecycle proposal lost its exact private checkpoint")
        if proposal.kind == "resume":
            if live[3] is not None or live[5] or not state["paused"]:
                raise ControlError("Lifecycle Resume requires a paused empty controller")
            return
        r._check_lease()
        if r._lease.operation != "lifecycle":
            raise ControlError("Lifecycle input requires its exact lifecycle lease")
        if proposal.kind == "direct" and actual["boundary"]["kind"] != "menu":
            raise ControlError("Lifecycle ordinary input cannot enter unadopted normal play at preflight")
        if state["boundary"]["kind"] == "normal_play":
            allowed = ("save",) if phase.operation == "save" and phase.stage == "save_start" else (
                ("player_data",) if phase.stage == "awaiting_identity" else ())
            if proposal.kind != "action" or proposal.action not in allowed:
                raise ControlError("Provisional normal lifecycle permits only its registered save/identity action")
        elif proposal.kind == "direct":
            # Ordinary controls need an owned receiver, not a known menu or
            # task interpretation. Identity/adoption remains a separate proof.
            if not state["boundary"]["input_receiver"]:
                raise ControlError("Lifecycle ordinary input requires a visible live receiver")
        elif state["category"] == "PLAYER_INFO":
            if proposal.kind != "action" or proposal.action != "QUIT" or phase.identity_screen is None:
                raise ControlError("Identity inspection permits only its owned return; Confirm can upgrade a stat")
        elif state["category"] == "YESNO":
            if (proposal.kind != "action" or proposal.action not in ("YES", "NO")
                    or proposal.action == "YES" and phase.stage not in
                       ("world_confirmation", "points_confirmation", "character_confirmation", "save_confirmation")):
                raise ControlError("Lifecycle confirmation requires its explicitly committed stage")
        elif phase.operation == "load" and state["category"] == "UILIST" and proposal.action in ("CONFIRM", "UILIST.CONFIRM"):
            ui = state["ui"]
            rows = [] if ui is None else ui["rows"]
            targets = [row for row in rows if row["text"] == r._admission.scenario.character]
            if (phase.stage != "load_selection" or ui is None or ui["purpose"] != "uilist"
                    or len(targets) != 1 or not targets[0]["enabled"] or targets[0]["id"] != ui["selected"]):
                raise ControlError("Reload confirmation requires its unique enabled selected admitted-character row")
        elif state["category"] not in _SETUP or state["category"] in _CHARACTER and phase.operation != "create":
            raise ControlError("Unsupported lifecycle category or wrong operation")

    def published(self, phase: NormalPhase, proposal: ControlIntent, native_request: dict,
                  reservation: CapacityReservation) -> None:
        expected = (proposal.kind in ("action", "direct") and (
            phase.stage in ("character_confirmation", "points_confirmation", "save_confirmation")
            or phase.operation == "load" and phase.checkpoint.boundary_kind == "menu"))
        self.candidate = _TransitionCandidate(phase, proposal.logical_id, native_request.copy(), reservation,
            diagnostic_only=not expected)

    def returned(self, logical_id: str, reference: EvidenceRef) -> None:
        candidate = self.candidate
        if candidate is None or candidate.logical_id != logical_id:
            return
        phase = candidate.phase
        if (reference.session == phase.checkpoint.session
                and (reference.boundary_kind != "normal_play" or phase.first_normal is not None)):
            self.candidate = None

    def _binding_request(self, work: _Work, checkpoint: EvidenceRef) -> None:
        r, data = self.runtime, work.request
        state = r._store.observation(checkpoint)
        if (checkpoint.observation_id not in data["sources"]
                or (data["expected_session"], data["expected_revision"], data["expected_boundary_id"]) !=
                   (state["session"], state["revision"], state["boundary"]["id"])):
            # Preserve only a positively healthy existing phase. In particular,
            # the no-proposal guard alone does not check an active writer lease;
            # a stale request must not hide its revocation or a frozen controller.
            if self.candidate is not None:
                self._candidate_guard(work, self.candidate)
            elif self.phase is not None:
                paused = r._ledger.snapshot(now=r._wall())["phase"] == "paused"
                self.guard(work, self.phase, diagnostic=paused,
                    ordinary=data["kind"] == "skill" and data["skill_kind"] == "direct")
                if not paused:
                    r._check_lease()
            else:
                raise EvidenceError("Lifecycle root does not name its exact current informing source")
            raise LifecycleRequestRefusal("Lifecycle request does not name its exact current informing source. "
                "No input was sent. Select the returned current snapshot and submit a new request; "
                "the old request was not retargeted or replayed.")

    def _resume(self, work: _Work, phase: NormalPhase) -> NormalPhase:
        r = self.runtime
        inspected, _ = r._store.inspect_current_boundary(**r._clocks())
        if inspected != phase.checkpoint:
            raise EvidenceError("Lifecycle Resume lost its exact retained checkpoint")
        original = phase.checkpoint
        phase = self._refresh(work, phase)
        # Resume has no lease yet. Retain the exact source relation without
        # constructing a lease-bound SourceBinding or granting authority.
        r._record("mission_lifecycle_resume_checkpoint", {"request_id": work.request["request_id"],
            "before_source_id": original.observation_id, "refreshed_source_id": phase.checkpoint.observation_id,
            "rule": self.source_rule(phase), "grants_authority": False})
        # Constructor is private to the runtime, not serialized player data.
        proposal = r._resume_intent(work.request["request_id"], phase.checkpoint)
        feedback = r._dispatch(work, proposal, phase.checkpoint, lifecycle=phase)
        r._check_cancelled(work)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            raise ControlError("Lifecycle Resume was not verified; original receipt retained: " + feedback.reason)
        state = r._store.observation(feedback.after)
        if state["paused"] or state["session"] != phase.checkpoint.session or self.candidate is not None:
            raise ControlError("Lifecycle Resume did not return its same supported session")
        r._lease = r.controller.acquire_mission(r._admission.mission_id, phase.epoch, phase.actor_id,
            operation="lifecycle", expected_session=state["session"], expected_revision=state["revision"],
            expected_boundary_id=state["boundary"]["id"])
        phase = self._install(work, replace(phase, checkpoint=feedback.after), previous=phase)
        return phase

    def command(self, work: _Work) -> tuple[str, dict]:
        data = work.request
        if data["phase_id"] is None:
            return self._begin(work)
        if self.candidate is not None:
            return self._reconcile(work)
        phase = self.phase
        if phase is None or data["phase_id"] != phase.root_id or data["operation"] != phase.operation:
            raise ControlError("No live matching registered lifecycle phase; history restores no phase")
        if phase.stage == "awaiting_identity" and self.runtime._store.observation(phase.checkpoint)["paused"]:
            return self._readmit(work, phase)
        self.guard(work, phase)
        self._binding_request(work, phase.checkpoint)
        if data["identity_claim_ids"]:
            return self._adopt(work, phase)
        if phase.operation == "save" and phase.stage == "save_start":
            return self._save(work, phase)
        state = self.runtime._store.observation(phase.checkpoint)
        action = "FINALIZE" if state["category"] == "WORLDGEN_CONFIRM_DIALOG" else (
            "NEXT_TAB" if state["category"] == "NEW_CHAR_DESCRIPTION" else None)
        if phase.operation != "create" or phase.stage != "awaiting_control" or action is None:
            # A wrong stage request is not loss of the already-owned phase.
            # The no-proposal guard above does not check the writer lease or
            # execution deadline: establish both before retaining that phase.
            self.runtime._check_lease()
            self.runtime._deadline(work, phase.checkpoint)
            self.runtime._check_cancelled(work)
            return "blocked", {"reason": "No lifecycle stage commit applies to this request. "
                "No input was sent; the original phase and limits remain. Use enactive_skill "
                "with scope=lifecycle under the same root for player-chosen visible controls, "
                "ordinary key/text/click or identity inspection. Use lifecycle again only for "
                "an applicable stage commit, readmission, reconciliation or identity adoption.",
                "source_ids": [phase.checkpoint.observation_id], "grants_authority": False}
        phase, relation = self._action_checkpoint(work, phase)
        state = self.runtime._store.observation(phase.checkpoint)
        phase = replace(phase, stage="world_confirmation" if action == "FINALIZE" else "character_confirmation")
        phase = self._install(work, phase)
        proposal = ControlIntent("stage-" + hashlib.sha256(data["request_id"].encode()).hexdigest(),
            "action", action, phase.checkpoint, state["boundary"]["id"], relation)
        feedback = self.runtime._dispatch(work, proposal, phase.checkpoint, lifecycle=phase)
        self.runtime._check_cancelled(work)
        if feedback.transport_disposition in ("rejected", "not_dispatched") and self.phase is phase:
            # The explicit stage request remains in history, but no input was
            # committed. Do not leave the form labelled as its future question.
            phase = self._install(work, replace(phase, stage="awaiting_control"), previous=phase)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, **({"phase": self.receipt(phase, "unknown")}
                    if self.candidate is None or not self.candidate.diagnostic_only else {}), "grants_authority": False}
        after = self.runtime._store.observation(feedback.after)
        if after["category"] != "YESNO":
            raise ControlError("Stage commit did not produce its supported visible confirmation")
        phase = self._install(work, replace(phase, checkpoint=feedback.after), previous=phase)
        return "partial", {"reason": "Explicit lifecycle stage awaits the player's interpreted confirmation",
            "phase": self.receipt(phase, "awaiting_control"), "grants_authority": False}

    def _begin(self, work: _Work) -> tuple[str, dict]:
        r, data = self.runtime, work.request
        if self.phase is not None or self.candidate is not None or r._exit_phase is not None or r._prompt_phase is not None:
            raise ControlError("Another private prompt/lifecycle phase is outstanding")
        if data["work_id"] is not None or data["identity_claim_ids"]:
            raise ControlError("Lifecycle root cannot import Work or old identity authority")
        launch = self._owned()
        source = r._current
        if source is None:
            raise EvidenceError("Lifecycle root requires current owned evidence")
        self._binding_request(work, source)
        state = r._store.observation(source)
        ledger = r._ledger.snapshot(now=r._wall())
        saved = None
        if data["operation"] == "save":
            r._informing(data)
            r._require_normal_adoption(source)
            if source.boundary_kind != "normal_play":
                raise ControlError("Normal save starts from admitted normal play")
        else:
            if (source.boundary_kind != "menu" or state["category"] != "MAIN_MENU" or not state["paused"]
                    or state["session"] != launch.checkpoint.session):
                raise ControlError("Creation/load starts from this launch's paused main menu")
            normals = [ref for ref in r._store.historical_references if ref.boundary_kind == "normal_play"]
            if data["operation"] == "create" and (r._admission.scenario.mode != "fresh" or normals):
                raise ControlError("Fresh creation cannot replace a retained normal session")
            if data["operation"] == "load":
                checkpoints = [row for row in r._ledger.request_records() if row["state"] == "completed"
                    and row["result"] is not None and "saved_checkpoint" in row["result"]]
                initial_load = r._admission.scenario.mode == "load" and not normals and not checkpoints
                if not initial_load and (not checkpoints or not normals):
                    raise ControlError("Reload requires this mission's own saved checkpoint")
                if not initial_load:
                    saved = checkpoints[-1]["request"]["request_id"]
                    if normals[-1].observation_id != checkpoints[-1]["result"]["saved_checkpoint"]["normal_endpoint_source_id"]:
                        raise ControlError("Reload cannot roll back newer normal observations")
            r._ledger.activate(epoch=ledger["epoch"], player_id=ledger["player_id"], now=r._wall())
        phase = NormalPhase(data["request_id"], source, launch, ledger["player_id"], ledger["epoch"],
            data["operation"], stage="save_start" if data["operation"] == "save" else "awaiting_control",
            first_normal=source if data["operation"] == "save" else None, saved_checkpoint=saved)
        phase = self._install(work, phase)
        if data["operation"] != "save":
            phase = self._resume(work, phase)
            next_epoch = len({ref.session for ref in r._store.historical_references if ref.boundary_kind == "normal_play"})
            return "partial", {"reason": "Owned lifecycle setup awaits player menu/field decisions",
                "next_coordinate_epoch": next_epoch,
                "phase": self.receipt(phase, "awaiting_control"), "grants_authority": False}
        return self._save(work, phase)

    def _save(self, work: _Work, phase: NormalPhase) -> tuple[str, dict]:
        r, data = self.runtime, work.request
        phase, relation = self._action_checkpoint(work, phase)
        state = r._store.observation(phase.checkpoint)
        r._rotate(work, ControlIntent("save-rotation", "action", "save", phase.checkpoint, state["boundary"]["id"]))
        proposal = ControlIntent("save-" + hashlib.sha256(data["request_id"].encode()).hexdigest(),
            "action", "save", phase.checkpoint, state["boundary"]["id"], relation)
        feedback = r._dispatch(work, proposal, phase.checkpoint, lifecycle=phase)
        r._check_cancelled(work)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, **({"phase": self.receipt(phase, "unknown")}
                    if self.candidate is None or not self.candidate.diagnostic_only else {}), "grants_authority": False}
        after = r._store.observation(feedback.after)
        if after["category"] != "YESNO":
            raise ControlError("Normal Save did not produce its supported confirmation")
        phase = self._install(work, replace(phase, checkpoint=feedback.after, stage="save_confirmation"), previous=phase)
        return "partial", {"reason": "Normal Save awaits explicit Save and quit? confirmation",
            "phase": self.receipt(phase, "awaiting_control"), "grants_authority": False}

    def control(self, work: _Work) -> tuple[str, dict]:
        r, data, phase = self.runtime, work.request, self.phase
        if phase is None or data["phase_id"] != phase.root_id or data["work_id"] is not None:
            raise ControlError("Lifecycle child lost its direct root or imported unrelated Work")
        if (data["skill_kind"] == "inspect" and data["goal"]["purpose"] == "character_identity"
                and phase.operation in ("create", "load") and phase.stage == "awaiting_identity"
                and r._store.observation(phase.checkpoint)["paused"]):
            # A missing explicit readmission is a request precondition, not
            # consent to activate or a reason to discard a healthy private phase.
            if r._ledger.snapshot(now=r._wall())["phase"] != "paused":
                raise ControlError("Paused identity inspection requires its paused reconciled lifecycle")
            self.guard(work, phase, diagnostic=True)
            self._binding_request(work, phase.checkpoint)
            current, _ = r._store.inspect_current_boundary(**r._clocks())
            if current != phase.checkpoint or r.controller._frame_sha256(r._live()[0]) != current.frame_sha256:
                raise EvidenceError("Paused identity request lost its current source or exact native pixels")
            for identity in data["sources"]:
                self._source(identity)
            r._deadline(work, current)
            ledger = r._ledger.snapshot(now=r._wall())
            counts = r._ledger.measured_counts()["primitives"]
            if (ledger["remaining_inputs"] <= r._admission.cleanup_reserve.inputs
                    or counts["charged"] >= r._admission.limits.primitive_mappings
                    or r._game_cost is not None and r._game_cost >= r._admission.limits.game_seconds):
                raise BudgetError("Paused identity request cannot bypass exhausted mission limits")
            with r._ledger._mutex:
                root = r._ledger.request(phase.root_id)
                if r._ledger._phase_primitive_count(phase.root_id) >= root["request"]["limits"]["primitives"]:
                    raise BudgetError("Original lifecycle phase primitive limit exhausted")
            r._capacity(frames=2, byte_count=2 * MAX_FRAME_BYTES)
            r._store.preflight_retention()
            r._check_cancelled(work)
            return "blocked", {"reason": "Identity inspection requires explicit readmission first: use "
                "enactive_lifecycle with lifecycle scope, the same create/load operation and root, "
                "and no identity Claims or Work. That separate call charges Resume. No input was sent; "
                "the original paused phase and limits remain. Submit a NEW explicit request.",
                "source_ids": [phase.checkpoint.observation_id], "grants_authority": False}
        self.guard(work, phase, ordinary=data["skill_kind"] == "direct")
        self._binding_request(work, phase.checkpoint)
        if data["skill_kind"] == "inspect":
            return self._inspect(work, phase)
        if data["skill_kind"] not in ("menu", "edit", "direct"):
            raise ControlError("Lifecycle setup requires a control or identity inspection")
        if data["skill_kind"] == "edit" and data["goal"]["purpose"] in ("world_name", "character_name"):
            field = "world" if data["goal"]["purpose"] == "world_name" else "character"
            if phase.operation != "create" or data["goal"]["text"] != getattr(r._admission.scenario, field):
                raise ControlError("Creation name editor must use its exact admitted identity")
        state = r._store.observation(phase.checkpoint)
        if state["category"] == "YESNO" and data["skill_kind"] != "direct":
            view = data["perception"]
            next_stage = phase.stage
            question = "Save and quit?" if phase.stage == "save_confirmation" else "Are you SURE you're finished?"
            if (phase.stage == "character_confirmation" and view is not None
                    and view.get("question") == _POINTS_QUESTION):
                next_stage = "points_confirmation"
            if next_stage == "points_confirmation":
                question = _POINTS_QUESTION
            if view is None or view["kind"] != "confirmation" or view["question"] != question:
                # This is local request validation, before refresh, rotation or
                # dispatch. Keep the original phase so the player can correct
                # its interpretation; no input or new consent is granted.
                return "blocked", {
                    "reason": "Lifecycle confirmation lacks its exact interpreted stage question. "
                        "Copy only the visible question exactly, omitting a separate case-sensitivity legend. "
                        "No input was dispatched; re-read the phase and submit a new request.",
                    "source_ids": [phase.checkpoint.observation_id], "grants_authority": False}
            if next_stage != phase.stage:
                phase = self._install(work, replace(phase, stage=next_stage), previous=phase)
        if (state["category"] == "PLAYER_INFO" and data["skill_kind"] != "direct"
                and (data["perception"] is None or data["perception"]["kind"] != "dismissal")):
            raise ControlError("Identity screen supports only an explicit owned dismissal")
        if state["boundary"]["kind"] == "normal_play":
            raise ControlError("Normal provisional source requires character_identity inspection or adoption")
        deadline = r._deadline(work, phase.checkpoint)
        skill = (OrdinaryInputSkill(data, deadline_monotonic=deadline) if data["skill_kind"] == "direct" else
                 MenuSkill(data, deadline_monotonic=deadline) if data["skill_kind"] == "menu" and data["perception"] is None
                 else SemanticControlSkill(data, deadline_monotonic=deadline))
        inspected, _ = r._store.inspect_current_boundary(**r._clocks())
        if inspected != phase.checkpoint:
            raise EvidenceError("Lifecycle child lost its exact retained checkpoint")
        # A source just inside the age limit can expire before dispatch. Capture
        # and attest this operation's checkpoint even when it is currently fresh.
        # Original phase budgets and the independent final freshness checks stay.
        original, binding = phase.checkpoint, r._binding(phase.checkpoint)
        phase = self._refresh(work, phase, ordinary=data["skill_kind"] == "direct")
        if data["skill_kind"] == "direct":
            relation = InputObservation(binding, r._binding(phase.checkpoint))
            skill.observe(relation, r._store, **r._clocks())
            r._record("mission_input_observation", relation.to_dict())
        else:
            relation = SourceRevalidation(binding, r._binding(phase.checkpoint),
                "exact_png_bytes" if data["perception"] is not None else "native_state")
            skill.revalidate(relation, r._store, **r._clocks())
            r._record("mission_lifecycle_revalidation", relation.to_dict())
        r._store.observation(original)
        while True:
            proposal = skill.propose(r._store, **r._clocks())
            if isinstance(proposal, (MenuOutcome, ControlOutcome)):
                outcome = proposal
            else:
                feedback = r._dispatch(work, proposal, phase.checkpoint, lifecycle=phase)
                r._check_cancelled(work)
                outcome = skill.accept(feedback, r._store, **r._clocks())
                if feedback.transport_disposition == "returned" and feedback.after is not None:
                    after = r._store.observation(feedback.after)
                    stage = phase.stage
                    if (phase.operation == "load" and state["category"] == "MAIN_MENU"
                            and after["category"] == "UILIST" and proposal.action in ("CONFIRM", "UILIST.CONFIRM")):
                        stage = "load_selection"
                    elif phase.operation == "load" and after["category"] == "MAIN_MENU":
                        stage = "awaiting_control"
                    if stage == "points_confirmation":
                        stage = "character_confirmation" if after["category"] == "YESNO" else "awaiting_control"
                    if after["category"] != "YESNO" and stage in ("world_confirmation", "character_confirmation"):
                        stage = "awaiting_control"
                    if after["boundary"]["kind"] == "normal_play":
                        if (phase.operation == "save" and phase.first_normal is not None
                                and feedback.after.session == phase.first_normal.session):
                            self.phase = None
                            r._publish_source(feedback.after, authoritative=True)
                            result = r._control_result(outcome)
                            result["phase"] = self.receipt(replace(phase, checkpoint=feedback.after), "complete")
                            result["reason"] = "Save returned to the adopted normal session; no saved-checkpoint claim"
                            return "partial", result
                        if phase.identity_screen is not None:
                            stage = "awaiting_adoption"
                    phase = self._install(work, replace(phase, checkpoint=feedback.after, stage=stage), previous=phase)
                if outcome is None:
                    continue
            result = r._control_result(outcome)
            receipt_stage = "unknown" if outcome.disposition == "unknown" else (
                "awaiting_adoption" if phase.stage == "awaiting_adoption" else "awaiting_control")
            if self.candidate is None or not self.candidate.diagnostic_only:
                result["phase"] = self.receipt(phase, receipt_stage)
            return outcome.disposition, result

    @staticmethod
    def source_rule(phase: NormalPhase) -> str:
        # These registered normal-context operations retain their separate Save
        # or committed-transition/identity proofs. Their incidental pixels are
        # not an action precondition; actual identity screens/setup stay exact.
        normal_context = phase.checkpoint.boundary_kind == "normal_play" and (
            phase.operation == "save" and phase.stage == "save_start"
            or phase.operation in {"create", "load"} and phase.stage == "awaiting_identity")
        return "native_state" if normal_context else "exact_png_bytes"

    def _refresh(self, work: _Work, phase: NormalPhase, *, diagnostic: bool = False,
                 ordinary: bool = False) -> NormalPhase:
        r = self.runtime
        previous_phase = phase
        self.guard(work, phase, diagnostic=diagnostic, ordinary=ordinary)
        r._capacity()
        deadlines = [r._ledger.request(work.request["request_id"])["deadline"],
            r._mission_deadline - r._admission.cleanup_reserve.wall_seconds]
        menu_read = (diagnostic and phase.operation in ("create", "load")
            and phase.first_normal is None and phase.checkpoint.boundary_kind == "menu"
            and self.candidate is None and not self.normal_after_launch())
        if menu_read:
            # This explicit read or zero-input abort cannot renew execution.
            # Its own deadline bounds capture; children still retain the old
            # root deadline in the ledger. Reuse the controller's custody fence.
            r._check_lease()
        else:
            deadlines.append(r._ledger.request(phase.root_id)["deadline"])
        deadline = r._clock() + min(deadlines) - r._wall()
        state, received = r._observe_native(work, deadline_monotonic=deadline)
        r._check_cancelled(work)
        if menu_read:
            # A prior known rejected ACK can still be the cached state. Judge
            # readiness from this fresh read, not from that historical receipt.
            r._check_lease()
            r.controller.check_mission_refusal(r._lease, r._lease.pause_generation, command_work=0)
        reference = r._ingest(state, received)
        rule = self.source_rule(phase)
        if not ordinary and not r._store.equivalent(phase.checkpoint, reference, rule=rule):
            raise EvidenceError("Lifecycle refresh changed the owned action precondition")
        if (ordinary and phase.stage in ("world_confirmation", "points_confirmation", "character_confirmation")
                and r._store.observation(phase.checkpoint)["category"] == "YESNO" and state["category"] != "YESNO"):
            phase = replace(phase, stage="awaiting_control")
        if phase.operation == "save" and phase.stage == "save_start":
            # Preserve the interaction lease through refresh. _save performs the
            # existing checked lifecycle rotation only when dispatching Save.
            r._check_cancelled(work)
            r._check_lease()
            r._deadline(work, reference)
            ledger = r._ledger.snapshot(now=r._wall())
            counts = r._ledger.measured_counts()["primitives"]
            if any(counts["by_state"].get(state, 0) for state in ("prepared", "published")):
                raise LedgerError("Unsettled input cannot advance a Save observation")
            if (ledger["remaining_inputs"] <= r._admission.cleanup_reserve.inputs
                    or r._game_cost is not None and r._game_cost >= r._admission.limits.game_seconds):
                raise BudgetError("Save observation cannot bypass exhausted mission limits")
            root = r._ledger.request(phase.root_id)
            if r._ledger._phase_primitive_count(phase.root_id) >= root["request"]["limits"]["primitives"]:
                raise BudgetError("Original Save primitive ceiling exhausted")
        self.retain_after(reference)
        phase = self._install(work, replace(phase, checkpoint=reference), previous=previous_phase)
        self.guard(work, phase, diagnostic=diagnostic, ordinary=ordinary)
        return phase

    def _action_checkpoint(self, work: _Work, phase: NormalPhase) -> tuple[NormalPhase, SourceRevalidation]:
        """Refresh one already-decided action without changing its consent or anchor."""
        r = self.runtime
        inspected, _ = r._store.inspect_current_boundary(**r._clocks())
        if inspected != phase.checkpoint:
            raise EvidenceError("Lifecycle action lost its current owned checkpoint")
        binding = r._binding(phase.checkpoint)
        phase = self._refresh(work, phase)
        relation = SourceRevalidation(binding, r._binding(phase.checkpoint), self.source_rule(phase))
        r._record("mission_lifecycle_revalidation", relation.to_dict())
        return phase, relation

    def _readmit(self, work: _Work, phase: NormalPhase) -> tuple[str, dict]:
        r, data = self.runtime, work.request
        r._check_cancelled(work)
        self._owned()
        self._binding_request(work, phase.checkpoint)
        ledger = r._ledger.snapshot(now=r._wall())
        transition = None if phase.transition_request is None else r._ledger.request(phase.transition_request)
        if (data["identity_claim_ids"] or data["work_id"] is not None
                or ledger["phase"] != "paused"
                or ledger["epoch"] != phase.epoch or data["epoch"] != phase.epoch
                or ledger["player_id"] != phase.actor_id or ledger["unreconciled"]
                or transition is None or transition["state"] != "completed"
                or transition["result"].get("lifecycle_transition", {}).get("after_source_id") != phase.first_normal.observation_id):
            raise ControlError("Identity readmission requires the already committed exact transition/effect")
        self.guard(work, phase, diagnostic=True)
        r._ledger.activate(epoch=phase.epoch, player_id=phase.actor_id, now=r._wall())
        phase = self._refresh(work, phase)
        phase = self._resume(work, phase)
        return "completed", {"reason": "Explicit provisional readmission; only character identity inspection is eligible",
            "phase": self.receipt(phase, "awaiting_identity"), "grants_authority": False}

    def _candidate_guard(self, work: _Work, candidate: _TransitionCandidate) -> None:
        r, phase = self.runtime, candidate.phase
        r._check_cancelled(work)
        if candidate is not self.candidate or self._owned().launch_id != phase.launch.launch_id:
            raise ControlError("Expected lifecycle transition lost its owned child")
        state = r._live()[0]
        if state is not None and (state["pause_origin"] == "human" or state["takeover_generation"] != phase.launch.takeover_generation):
            raise ControlError("Expected transition was superseded by native takeover")
        ledger = r._ledger.snapshot(now=r._wall())
        if ledger["player_id"] != phase.actor_id or work.request["epoch"] != ledger["epoch"]:
            raise ControlError("Expected transition lost its current actor/epoch")
        if r._wall() >= min(r._ledger.request(phase.root_id)["deadline"],
                r._mission_deadline - r._admission.cleanup_reserve.wall_seconds):
            raise BudgetError("Original lifecycle transition deadline expired")
        if candidate.diagnostic_only:
            primitive = r._ledger.primitive(candidate.logical_id)
            intent, receipt = primitive["intent"], primitive["result"] or {}
            owner = r._ledger.request(primitive["request_id"])["request"]
            binding = receipt.get("dispatch_binding") or {}
            if (not ledger["clock_valid"] or ledger["phase"] != "paused"
                    or ledger["pause_cause"] not in ("unknown", "internal_recovery")
                    or ledger["epoch"] != phase.epoch + 1 or r._lease is not None
                    or primitive["state"] not in ("unknown", "returned", "rejected")
                    or primitive["effect"] is not None or receipt.get("published") is not True
                    or owner["epoch"] != phase.epoch
                    or (owner.get("phase_id") or owner["request_id"]) != phase.root_id
                    or primitive["native_id"] != candidate.native_request["id"]
                    or receipt.get("native_request_json") != canonical(candidate.native_request)
                    or receipt.get("logical_action_id") != candidate.logical_id
                    or intent["source_before"] != phase.checkpoint.observation_id
                    or binding.get("epoch") != phase.epoch or binding.get("actor_id") != phase.actor_id
                    or binding.get("controller_boot_id") != phase.launch.operator_mark[0]
                    or binding.get("operator_pause_generation") != phase.launch.operator_mark[1]
                    or binding.get("takeover_generation") != phase.launch.takeover_generation):
                raise ControlError("Diagnostic lifecycle evidence lost its original published dispatch custody")
            if candidate.reservation is not None:
                reservation = candidate.reservation
                if (reservation.token != intent["reservation_id"]
                        or reservation.before_observation_id != intent["source_before"]
                        or reservation.preflight_observation_id != intent["preflight_source"]):
                    raise EvidenceError("Diagnostic lifecycle reservation differs from its published dispatch")
                r._store._check_reservation(reservation)
            else:
                r._store.preflight_retention()

    def reject_delivery_reconciliation(self, work: _Work) -> None:
        """A healthy expected transition belongs to lifecycle, not delivery recovery."""
        candidate = self.candidate
        if candidate is None or candidate.diagnostic_only:
            return
        r = self.runtime
        self._candidate_guard(work, candidate)
        state = r._ledger.snapshot(now=r._wall())
        native = r._live()[0]
        primitive = r._ledger.primitive(candidate.logical_id)
        if (not state["clock_valid"] or state["phase"] != "paused"
                or state["pause_cause"] != "unknown" or r._lease is not None
                or r._pending_pauses or r.controller.frozen or r.controller.closed
                or native is None or native["status"] != "ready" or native["error"] or not native["frame_ok"]
                or primitive["state"] != "unknown" or primitive["effect"] is not None):
            raise ControlError("Expected lifecycle transition is no longer eligible for reconciliation")
        raise LifecycleRequestRefusal(
            f"This is an expected {candidate.phase.operation} lifecycle transition, not ordinary delivery recovery. "
            "No input was sent. After explicit Observe, use enactive_lifecycle with "
            f"operation={candidate.phase.operation}, scope=lifecycle and phase_id={candidate.phase.root_id}. "
            "The original limits and unknown acknowledgment remain unchanged.")

    def observe(self, work: _Work) -> dict:
        r = self.runtime
        if self.candidate is None:
            if self.phase is None:
                raise ControlError("No owned lifecycle evidence to observe")
            phase = self._refresh(work, self.phase, diagnostic=True, ordinary=True)
            stage = phase.stage if phase.stage in ("awaiting_identity", "awaiting_adoption") else "awaiting_control"
            return {"source_ids": [phase.checkpoint.observation_id], "phase": self.receipt(phase, stage),
                "lifecycle_needed": True, "grants_authority": False}
        candidate = self.candidate
        self._candidate_guard(work, candidate)
        r._capacity()
        deadline = r._clock() + min(r._ledger.request(candidate.phase.root_id)["deadline"],
            r._ledger.request(work.request["request_id"])["deadline"],
            r._mission_deadline - r._admission.cleanup_reserve.wall_seconds) - r._wall()
        state, received = r._observe_native(work, deadline_monotonic=deadline)
        self._candidate_guard(work, candidate)
        phase = candidate.phase
        expected = (state["category"] == "MAIN_MENU" and not state["in_game"] and state["boundary"]["kind"] == "menu"
            if phase.operation == "save" else state["boundary"]["kind"] == "normal_play" and state["in_game"] and state["scene"] is not None)
        if ((not candidate.diagnostic_only and (not expected or state["session"] == phase.checkpoint.session))
                or state["error"] or not state["frame_ok"]
                or not state["paused"] or state["pause_origin"] not in ("world_change", "host")):
            raise ControlError("Observed evidence does not establish the exact outstanding lifecycle transition")
        # Retain the actual after-frame against the exact published dispatch's
        # reservation. This consumes capacity, never repairs its unknown ACK.
        reference = r._ingest(state, received, reservation=candidate.reservation)
        candidate = replace(candidate, first_after=candidate.first_after or reference,
            latest_after=reference, reservation=None)
        self.candidate = candidate
        if candidate.diagnostic_only:
            self.retain_diagnostic(reference)
            return {"source_ids": list(dict.fromkeys((candidate.first_after.observation_id, reference.observation_id))),
                "reason": "Diagnostic-only evidence of an unexpected published lifecycle input; "
                    "no transition reconciliation, identity adoption or supported normal cleanup",
                "lifecycle_needed": True, "grants_authority": False}
        self.retain_after(reference)
        return {"source_ids": list(dict.fromkeys((candidate.first_after.observation_id, reference.observation_id))),
            "phase": self.receipt(phase, "awaiting_transition", extra=(candidate.first_after, reference), epoch=work.request["epoch"]),
            "reason": "Expected transition observed diagnostically; explicit same-root reconciliation required",
            "lifecycle_needed": True, "grants_authority": False}

    def _reconcile(self, work: _Work) -> tuple[str, dict]:
        r, data, candidate = self.runtime, work.request, self.candidate
        if candidate.diagnostic_only:
            raise ControlError("Diagnostic-only lifecycle evidence cannot reconcile a registered transition or adopt identity")
        self._candidate_guard(work, candidate)
        phase = candidate.phase
        if (data["phase_id"] != phase.root_id or data["operation"] != phase.operation
                or data["identity_claim_ids"] or data["work_id"] is not None
                or candidate.first_after is None or candidate.latest_after != r._current
                or candidate.first_after.observation_id not in data["sources"]):
            raise ControlError("Transition reconciliation requires exact retained diagnostic evidence and its original root")
        self._binding_request(work, candidate.latest_after)
        self._candidate_guard(work, candidate)
        proof = {"schema": VERSION, "record_type": "LifecycleTransition", "operation": phase.operation,
            "origin_request_id": phase.root_id, "terminal_request_id": r._ledger.primitive(candidate.logical_id)["request_id"],
            "terminal_logical_id": candidate.logical_id, "native_request_id": candidate.native_request["id"],
            "launch_request_id": phase.launch.request_id, "launch_id": phase.launch.launch_id,
            "before_source_id": phase.checkpoint.observation_id, "after_source_id": candidate.first_after.observation_id,
            "origin_epoch": phase.epoch, "reconciled_epoch": data["epoch"], "actor_id": phase.actor_id,
            "controller_boot_id": phase.launch.operator_mark[0], "operator_pause_generation": phase.launch.operator_mark[1],
            "before_takeover_generation": phase.launch.takeover_generation,
            "after_takeover_generation": phase.launch.takeover_generation, "grants_authority": False}
        primitive = r._ledger.primitive(candidate.logical_id)
        if phase.operation == "create":
            from .gameplay.creation_provenance import creation_input_chain, validate_creation_sources
            chain = creation_input_chain(r._ledger.request_records(), r._ledger.primitive_records(),
                root_id=phase.root_id, terminal_request_id=primitive["request_id"],
                terminal_logical_id=candidate.logical_id)
            validate_creation_sources(chain, r._store, terminal_before=phase.checkpoint)
        if primitive["state"] == "unknown":
            r._ledger.reconcile_effect(candidate.logical_id,
                proof=proof,
                sources=(proof["before_source_id"], proof["after_source_id"]),
                note=f"Observed lifecycle {phase.operation} transition after {candidate.native_request['id']}; original ACK remains unknown", now=r._wall())
        phase = replace(phase, checkpoint=candidate.latest_after, epoch=data["epoch"],
            first_normal=candidate.first_after if phase.operation != "save" else None,
            transition_request=data["request_id"], stage="awaiting_identity" if phase.operation != "save" else "awaiting_control")
        result = {"lifecycle_transition": proof, "grants_authority": False}
        if phase.operation == "save":
            normals = [ref for ref in r._store.historical_references if ref.boundary_kind == "normal_play"]
            previous = [row for row in r._ledger.request_records() if row["state"] == "completed"
                and row["result"] is not None and "normal_adoption" in row["result"]]
            if not normals or not previous:
                raise EvidenceError("Save transition lacks this mission's adopted normal endpoint")
            result["saved_checkpoint"] = {"schema": VERSION, "record_type": "SavedCheckpoint",
                "origin_request_id": phase.root_id, "transition_result_request_id": data["request_id"],
                "adoption_result_request_id": previous[-1]["request"]["request_id"],
                "normal_endpoint_source_id": normals[-1].observation_id,
                "menu_source_id": candidate.first_after.observation_id, "grants_authority": False}
            result["phase"] = self.receipt(phase, "complete",
                extra=(self._source(proof["before_source_id"]), normals[-1], candidate.first_after))
        else:
            result["phase"] = self.receipt(phase, "awaiting_identity", extra=(self._source(proof["before_source_id"]),))
            result["provisional_scope"] = {"mission_id": r._admission.mission_id,
                "session": phase.first_normal.session, "coordinate_epoch":
                    len({ref.session for ref in r._store.historical_references if ref.boundary_kind == "normal_play"}) - 1}
        # Durable effect and typed result precede any provisional Resume/identity
        # input. A later explicit child starts that stage after this commit.
        phase = self._install(work, phase)
        self.candidate = None
        return "completed", result

    def _inspect(self, work: _Work, phase: NormalPhase) -> tuple[str, dict]:
        r, data = self.runtime, work.request
        if (data["goal"]["purpose"] != "character_identity" or phase.stage != "awaiting_identity"
                or phase.first_normal is None or phase.checkpoint.boundary_kind != "normal_play"):
            raise ControlError("Only the owned provisional character identity screen may be inspected")
        state = r._store.observation(phase.checkpoint)
        if state["paused"]:
            raise ControlError("Explicit same-root lifecycle readmission is required before identity inspection")
        phase, relation = self._action_checkpoint(work, phase)
        state = r._store.observation(phase.checkpoint)
        proposal = ControlIntent("identity-" + hashlib.sha256(data["request_id"].encode()).hexdigest(),
            "action", "player_data", phase.checkpoint, state["boundary"]["id"], relation)
        feedback = r._dispatch(work, proposal, phase.checkpoint, lifecycle=phase)
        r._check_cancelled(work)
        if feedback.transport_disposition != "returned" or feedback.after is None:
            return "unknown" if feedback.transport_disposition == "unknown" else "blocked", {
                "reason": feedback.reason, "phase": self.receipt(phase, "unknown"), "grants_authority": False}
        after = r._store.observation(feedback.after)
        if after["category"] != "PLAYER_INFO" or not after["in_game"] or feedback.after.session != phase.first_normal.session:
            raise ControlError("Registered identity inspection did not return the expected character screen")
        phase = self._install(work, replace(phase, checkpoint=feedback.after,
            identity_inspect=data["request_id"], identity_screen=feedback.after), previous=phase)
        return "completed", {"identity_screen_source_id": feedback.after.observation_id,
            "source_ids": [proposal.before.observation_id, feedback.after.observation_id],
            "phase": self.receipt(phase, "awaiting_identity"), "grants_authority": False}

    def _adopt(self, work: _Work, phase: NormalPhase) -> tuple[str, dict]:
        r, data = self.runtime, work.request
        if (phase.stage != "awaiting_adoption" or phase.first_normal is None or phase.transition_request is None
                or phase.identity_inspect is None or phase.identity_screen is None
                or phase.checkpoint.boundary_kind != "normal_play"):
            raise ControlError("Normal adoption needs completed owned transition and visible identity inspection/return")
        claims = {row["entry"]["id"]: row["entry"] for row in r._ledger.memory_records("claim")}
        selected = [claims.get(identity) for identity in data["identity_claim_ids"]]
        if len(selected) != 2 or any(entry is None for entry in selected):
            raise ContractError("Adoption requires the exact two retained identity Claims")
        subjects = {entry["key"]["subject"]: entry["id"] for entry in selected}
        if set(subjects) != {"world", "character"}:
            raise ContractError("Adoption identity subjects must be world and character")
        sessions = []
        for ref in r._store.historical_references:
            if ref.boundary_kind == "normal_play" and ref.session not in sessions:
                sessions.append(ref.session)
        proof = {"schema": VERSION, "record_type": "NormalSessionAdoption", "origin_request_id": phase.root_id,
            "transition_result_request_id": phase.transition_request, "first_normal_source_id": phase.first_normal.observation_id,
            "world_claim_id": subjects["world"], "character_claim_id": subjects["character"],
            "identity_inspect_request_id": phase.identity_inspect, "checkpoint_source_id": phase.checkpoint.observation_id,
            "saved_checkpoint_request_id": phase.saved_checkpoint, "scope": {"mission_id": r._admission.mission_id,
                "session": phase.first_normal.session, "coordinate_epoch": sessions.index(phase.first_normal.session)},
            "grants_authority": False}
        result = {"normal_adoption": proof, "phase": self.receipt(phase, "complete"), "grants_authority": False}
        try:
            r._ledger._check_normal_adoption(data["request_id"], data, proof)
            from .gameplay.lifecycle import candidate_timeline
            candidate_timeline(r._ledger, r._store, request_id=data["request_id"], result=result)
        except ContractError as exc:
            return "blocked", {"reason": f"Adoption not committed: {exc}",
                "phase": self.receipt(phase, "awaiting_adoption"), "grants_authority": False}
        return "completed", result

    def after_commit(self, work: _Work, disposition: str, result: dict) -> None:
        r = self.runtime
        if disposition != "completed":
            return
        if "normal_adoption" in result:
            phase = self.phase
            self.guard(work, phase)
            r._require_normal_adoption(phase.checkpoint)
            self.phase = None
            r._map = None
            r._bindings.clear()
            r._publish_source(phase.checkpoint, authoritative=True)
            r._capture_memory(phase.checkpoint)
        elif "saved_checkpoint" in result:
            r._owned_launch = replace(r._owned_launch, checkpoint=r._current)
            self.phase = None
