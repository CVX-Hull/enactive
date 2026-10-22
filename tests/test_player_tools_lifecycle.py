"""Structured tools over one real HTTP/runtime/controller/ledger, synthetic CDDA UI.

The fixture injects only the owned fake native process and rendered UI. It does
not bypass creation, adoption, handoff, source, claim or normal-ending guards.
Replacing PlayerTools tests disposable client context, not a fresh model agent.
"""
from copy import deepcopy
from contextlib import ExitStack
from dataclasses import replace
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from harness.mission_client import MissionClient
from harness.gameplay.contracts import ContractError
from harness.gameplay.evidence import EvidenceError
from harness.player_tools import PlayerTools
from harness.server import Server
from tests import test_mission_creation as creation
from tests import test_mission_handoff as handoff
from tests import test_mission_request_producer_integration as produced


class StructuredLifecycleTests(creation.MissionCreationFixture, unittest.TestCase):
    operation = handoff.MissionHandoffTests.operation
    remember_work = handoff.MissionHandoffTests.remember_work
    save_final = produced.ProducerLifecycleIntegrationTests.save_final

    def setUp(self):
        super().setUp()
        # Reuse the fixture's one actual runtime in the HTTP boundary. This is
        # constructor injection only, not a second runtime or mocked operation.
        with patch("harness.mission_runtime.MissionRuntime", return_value=self.runtime):
            self.server = Server(self.controller, 0)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, kwargs=dict(poll_interval=.01), daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.player = PlayerTools(MissionClient(self.controller.root))

    def launch(self, **changes):
        return self.run_request(self.request(**changes))

    def lifecycle(self, identity, operation="create", *, parent=None, claims=None, supports=()):
        value = super().lifecycle(identity, operation, parent=parent, claims=claims)
        value["sources"].extend(supports)
        return value

    def run_request(self, raw):
        selected, _ = self.player.call("enactive_snapshot", {})
        kind = raw["kind"]
        data = dict(snapshot_id=selected["snapshot_id"], request_id=raw["request_id"], wait_seconds=3)
        intent = deepcopy(raw)
        for field in ("schema", "kind", "mission_id", "epoch", "request_id"):
            intent.pop(field, None)
        if kind in ("skill", "lifecycle"):
            source_id = next(iter(raw["sources"]), None)
            if source_id is not None:
                self.player.call("enactive_source", dict(mission_id=self.a.mission_id, source_id=source_id))
            scope = "new_root"
            if raw["phase_id"] is not None:
                scope = next(name for name in ("prompt", "lifecycle", "activity")
                    if selected["mission"][name + "_phase"] is not None
                    and selected["mission"][name + "_phase"]["origin_request_id"] == raw["phase_id"])
            if intent.get("perception") is not None:
                intent["perception"].pop("source_id")
                intent["perception"].pop("basis")
            for field in ("sources", "expected_session", "expected_revision", "expected_boundary_id", "limits", "phase_id"):
                intent.pop(field)
            data.update(scope=scope, source_id=source_id, supporting_source_ids=raw["sources"][1:],
                        limits=raw["limits"], intent=intent)
        elif kind == "claim":
            for field in ("pause_generation", "takeover_generation", "expected_session", "expected_revision",
                          "expected_boundary_id", "expected_pause_origin"):
                intent.pop(field)
            data["intent"] = intent
        elif kind == "readmit":
            data["source_id"] = raw["sources"][0]
            self.player.call("enactive_source", dict(mission_id=self.a.mission_id, source_id=data["source_id"]))
            for field in ("sources", "expected_session", "expected_revision", "expected_boundary_id"):
                intent.pop(field)
            data["intent"] = intent
        elif kind != "observe":
            data["intent"] = intent
        result, _ = self.player.call("enactive_" + kind, data)
        self.assertEqual(result["transport"], "delivered", result)
        self.assertTrue(result["settled"], result)
        return result["response"]["operation"]

    def test_invalid_confirmation_label_is_local_and_correctable_in_same_phase(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        self.run_request(self.lifecycle("world-finalize", parent="create"))
        selected, _ = self.player.call("enactive_snapshot", {})
        before = deepcopy(self.runtime.status())
        delivered = deepcopy(self.bridge.delivered)
        arguments = dict(snapshot_id=selected["snapshot_id"], request_id="world-uppercase-yes",
            scope="lifecycle", source_id=selected["source"]["reference"]["observation_id"],
            supporting_source_ids=[], intent=dict(skill_kind="menu",
                goal=dict(purpose="confirmation", label="YES", outcome="activated"),
                perception=dict(kind="confirmation", question="Are you SURE you're finished?"), work_id=None, procedure=None),
            limits=dict(primitives=32, wall_seconds=900, game_seconds=3600), wait_seconds=15)
        with patch.object(self.player.client, "submit", wraps=self.player.client.submit) as submit:
            with self.assertRaisesRegex(ContractError, "typed direction/confirmation"):
                self.player.call("enactive_skill", arguments)
            submit.assert_not_called()
        after = self.runtime.status()
        for field in ("epoch", "lifecycle_phase", "spent_inputs", "current_source", "lease_owner"):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(self.bridge.delivered, delivered)
        corrected = self.run_request(self.control("world-corrected-yes", "Yes",
            question="Are you SURE you're finished?"))
        self.assertEqual(corrected["state"], "partial", corrected)

    def test_creation_successor_readmission_save_new_child_reload_and_normal_finish(self):
        selected, _ = self.player.call("enactive_snapshot", {})
        self.assertIsNone(selected["mission"])
        self.create()
        original_unknown = deepcopy(self.runtime._ledger.request("character-yes"))
        self.remember_work()
        before = self.runtime.status()["spent_inputs"]
        checkpoint = self.runtime._current.observation_id
        issued = self.run_request(self.operation("handoff", "handoff", checkpoint_ids=[checkpoint],
            unfinished_work_ids=["pending"], successor_role="player"))
        self.assertEqual(issued["state"], "completed", issued)
        self.player = PlayerTools(MissionClient(self.controller.root))
        selected, _ = self.player.call("enactive_snapshot", {})
        ref = selected["source"]["reference"]
        coordinate_scope = selected["mission"]["coordinate_scope"]
        self.assertEqual(coordinate_scope, dict(mission_id=self.a.mission_id,
            session=ref["session"], coordinate_epoch=0))
        self.assertNotEqual(selected["mission"]["epoch"], coordinate_scope["coordinate_epoch"])
        scope = {key: coordinate_scope[key] for key in ("session", "coordinate_epoch")}
        wrong_scope = dict(scope, coordinate_epoch=selected["mission"]["epoch"])
        rejected, _ = self.player.call("enactive_context", dict(snapshot_id=selected["snapshot_id"],
            intent=dict(scope=wrong_scope, query="unfinished", max_bytes=131072,
                handoff=dict(handoff_id="handoff", prospective_player_id="successor", actor_role="player"))))
        self.assertEqual(rejected["response"]["status"], "rejected")
        self.assertIn("current adopted coordinate scope", rejected["response"]["reason"])
        self.assertEqual(self.runtime.status()["phase"], "handoff")
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        self.assertIsNone(self.runtime._lease)
        context, _ = self.player.call("enactive_context", dict(snapshot_id=selected["snapshot_id"],
            intent=dict(scope=scope, query="unfinished",
                max_bytes=131072, handoff=dict(handoff_id="handoff", prospective_player_id="successor", actor_role="player"))))
        packet = context["response"]["context"]["packet"]
        self.assertIn("pending", [work["id"] for work in packet["work"]])
        declared = set(issued["result"]["checkpoint_ids"] + [issued["result"]["post_pause_source_id"]])
        for source_id in declared:
            self.player.call("enactive_source", dict(mission_id=self.a.mission_id, source_id=source_id))
        claimed = self.run_request(handoff.MissionHandoffTests.claim(self, packet))
        self.assertEqual(claimed["state"], "completed", claimed)
        self.assertIsNone(self.runtime._lease)
        resumed = self.run_request(handoff.MissionHandoffTests.readmit(self))
        self.assertEqual(resumed["state"], "completed", resumed)
        self.assertEqual(self.runtime.status()["spent_inputs"], before + 1)
        self.assertEqual(self.runtime._lease.actor_id, "successor")
        self.remember_work(status="completed", event="pending-completed")
        self.save()
        self.exit()
        self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
        self.stage = "load-world"
        self.assertEqual(self.run_request(self.lifecycle("load", "load"))["state"], "partial")
        world = self.runtime._current
        self.run_request(self.control("load-world", f"{self.a.scenario.world} (1)", parent="load"))
        selection = self.control("load-entry", self.a.scenario.character, parent="load")
        selection["perception"] = None
        self.assertEqual(self.run_request(selection)["state"], "unknown")
        self.observe("load-observe")
        adopted = self.finish_identity("load", world, 1, diagnostic_observe=True)
        self.assertEqual(adopted["result"]["normal_adoption"]["saved_checkpoint_request_id"], "save-reconcile")
        reloaded, _ = self.player.call("enactive_snapshot", {})
        self.assertEqual(reloaded["mission"]["coordinate_scope"], dict(mission_id=self.a.mission_id,
            session=reloaded["source"]["reference"]["session"], coordinate_epoch=1))
        self.assertNotEqual(reloaded["mission"]["coordinate_scope"]["session"], coordinate_scope["session"])
        self.save_final()
        self.exit("final-exit")
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["state"], "completed", finished)
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")
        self.assertEqual(self.runtime._ledger.request("character-yes"), original_unknown)
        self.runtime._ledger._verify(self.a)

    def test_save_root_draft_is_local_and_raw_rejection_preserves_explicit_normal_ending(self):
        self.create()
        selected, _ = self.player.call("enactive_snapshot", {})
        source = selected["source"]["reference"]["observation_id"]
        self.player.call("enactive_source", dict(mission_id=self.a.mission_id, source_id=source))
        before, lease = self.runtime.status(), self.runtime._lease
        checkpoint = self.runtime._current
        delivered = deepcopy(self.bridge.delivered)
        records = deepcopy(self.runtime._ledger.request_records())
        for index, fields in enumerate((dict(work_id="pending"), dict(identity_claim_ids=["old-identity"]),
                                       dict(work_id="pending", identity_claim_ids=["old-identity"]))):
            raw = self.lifecycle(f"malformed-save-{index}", "save")
            raw.update(fields)
            arguments = dict(snapshot_id=selected["snapshot_id"], request_id=raw["request_id"],
                scope="new_root", source_id=source, supporting_source_ids=[],
                intent=dict(operation="save", world=self.a.scenario.world, character=self.a.scenario.character,
                    work_id=raw["work_id"], identity_claim_ids=raw["identity_claim_ids"]),
                limits=raw["limits"], wait_seconds=3)
            with patch.object(self.player.client, "submit", wraps=self.player.client.submit) as submit:
                with self.assertRaisesRegex(ContractError, "root cannot import"):
                    self.player.call("enactive_lifecycle", arguments)
                submit.assert_not_called()
            # Raw callers cannot bypass the same pure receiver invariant.
            refused = self.runtime.command(raw)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertIn("root cannot import", refused["reason"])
            self.assertIs(self.runtime._lease, lease)
            self.assertIs(self.runtime._current, checkpoint)
            for field in ("epoch", "phase", "lifecycle_phase", "spent_inputs", "current_source", "lease_owner"):
                self.assertEqual(self.runtime.status()[field], before[field], field)
            self.assertEqual(self.runtime._ledger.request_records(), records)
            self.assertEqual(self.bridge.delivered, delivered)
        # A new, explicit corrected request follows all normal guards and the
        # existing unknown-ACK reconciliation, with no restored authority.
        self.save()
        self.exit()
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["state"], "completed", finished)
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")
        self.runtime._ledger._verify(self.a)

    def test_corrected_save_draft_cannot_restore_user_revoked_authority(self):
        self.create()
        bad = self.lifecycle("malformed-before-pause", "save")
        bad.update(work_id="pending", identity_claim_ids=["old-identity"])
        self.assertEqual(self.runtime.command(bad)["status"], "rejected")
        delivered = deepcopy(self.bridge.delivered)
        spent = self.runtime.status()["spent_inputs"]
        self.runtime.pause("Fixture real user Pause")
        corrected = self.lifecycle("corrected-after-pause", "save")
        response = self.runtime.command(corrected)
        if response["status"] == "accepted":
            self.assertEqual(self.settled(corrected["request_id"])["state"], "blocked")
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertIsNone(self.runtime._lease)

    def test_corrected_save_draft_still_checks_expired_mission_deadline(self):
        self.create()
        bad = self.lifecycle("malformed-before-exhaustion", "save")
        bad["work_id"] = "pending"
        self.assertEqual(self.runtime.command(bad)["status"], "rejected")
        delivered = deepcopy(self.bridge.delivered)
        spent = self.runtime.status()["spent_inputs"]
        # Expire the runtime's existing deadline; do not mock its guard or
        # extend the ledger's original admission/cleanup allowances.
        self.runtime._mission_deadline = self.runtime._wall() - 1
        corrected = self.run_request(self.lifecycle("corrected-after-exhaustion", "save"))
        self.assertEqual(corrected["state"], "blocked", corrected)
        self.assertLess(self.runtime._mission_deadline, self.runtime._wall())
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertIsNone(self.runtime._lease)

    def test_unadopted_launch_has_no_coordinate_scope(self):
        self.ready()
        selected, _ = self.player.call("enactive_snapshot", {})
        self.assertIsNone(selected["mission"]["coordinate_scope"])
        self.assertFalse(selected["mission"]["grants_authority"])

    def test_handoff_readmission_observe_source_refusal_can_be_explicitly_corrected(self):
        self.create()
        self.remember_work()
        issued = self.run_request(self.operation("handoff", "handoff",
            checkpoint_ids=[self.runtime._current.observation_id], unfinished_work_ids=["pending"],
            successor_role="player"))["result"]
        self.player = PlayerTools(MissionClient(self.controller.root))
        selected, _ = self.player.call("enactive_snapshot", {})
        scope = {key: selected["mission"]["coordinate_scope"][key] for key in ("session", "coordinate_epoch")}
        context, _ = self.player.call("enactive_context", dict(snapshot_id=selected["snapshot_id"],
            intent=dict(scope=scope, query="unfinished", max_bytes=131072,
                handoff=dict(handoff_id="handoff", prospective_player_id="successor", actor_role="player"))))
        packet = context["response"]["context"]["packet"]
        for identity in set(issued["checkpoint_ids"] + [issued["post_pause_source_id"]]):
            self.player.call("enactive_source", dict(mission_id=self.a.mission_id, source_id=identity))
        self.assertEqual(self.run_request(handoff.MissionHandoffTests.claim(self, packet))["state"], "completed")
        self.observe("after-claim-observe")
        selected, _ = self.player.call("enactive_snapshot", {})
        newer = selected["source"]["reference"]["observation_id"]
        self.assertNotEqual(newer, issued["post_pause_source_id"])
        phase = self.runtime._registered_handoff.phase
        before = self.runtime.status()
        delivered = deepcopy(self.bridge.delivered)
        arguments = dict(snapshot_id=selected["snapshot_id"], request_id="wrong-observe-source", wait_seconds=3,
            source_id=newer, intent=dict(mode="handoff", handoff_id="handoff", claim_request_id="claim",
                limits=dict(primitives=1, wall_seconds=30, game_seconds=10)))
        refused, _ = self.player.call("enactive_readmit", arguments)
        self.assertEqual(refused["response"]["status"], "rejected")
        self.assertIn("Select issued post-Pause source " + issued["post_pause_source_id"], refused["response"]["reason"])
        self.assertIn("before admission", refused["response"]["reason"])
        self.assertIs(self.runtime._registered_handoff.phase, phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.bridge.delivered, delivered)
        with self.assertRaisesRegex(ContractError, "Unknown semantic request"):
            self.runtime._ledger.request("wrong-observe-source")
        historical = handoff.MissionHandoffTests.readmit(self)
        historical["sources"] = [newer]
        with self.assertRaisesRegex(ContractError, "Readmission lost its exact issued post-Pause source"):
            self.runtime._ledger._readmit_deadline(historical, admitted_at=self.runtime._wall())
        # The adapter retains the rejected draft; correction uses a NEW ID.
        arguments.update(request_id="corrected-issued-source", source_id=issued["post_pause_source_id"])
        corrected, _ = self.player.call("enactive_readmit", arguments)
        self.assertEqual(corrected["response"]["operation"]["state"], "completed", corrected)
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"] + 1)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime._lease.actor_id, "successor")

    def test_handoff_draft_feedback_allows_explicit_player_correction(self):
        self.create()
        self.remember_work()
        selected, _ = self.player.call("enactive_snapshot", {})
        source = selected["source"]["reference"]["observation_id"]
        before, lease = self.runtime.status(), self.runtime._lease
        delivered = deepcopy(self.bridge.delivered)
        for identity, checkpoints, unfinished in (("wrong-reference", ["pending"], ["pending"]),
                                                  ("missing-work", [source], [])):
            refused, _ = self.player.call("enactive_handoff", dict(snapshot_id=selected["snapshot_id"],
                request_id=identity, wait_seconds=3, intent=dict(checkpoint_ids=checkpoints,
                    unfinished_work_ids=unfinished, successor_role="player")))
            operation = refused["response"]["operation"]
            self.assertEqual(operation["state"], "blocked", refused)
            self.assertIn("before stopping input", operation["result"]["reason"])
            self.assertFalse(operation["result"]["grants_authority"])
            self.assertIs(self.runtime._lease, lease)
            self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
            self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
            self.assertEqual(self.bridge.delivered, delivered)
        corrected, _ = self.player.call("enactive_handoff", dict(snapshot_id=selected["snapshot_id"],
            request_id="corrected-handoff", wait_seconds=3, intent=dict(checkpoint_ids=[source],
                unfinished_work_ids=["pending"], successor_role="player")))
        self.assertEqual(corrected["response"]["operation"]["state"], "completed", corrected)
        self.assertEqual(self.runtime.status()["phase"], "handoff")
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
        self.assertIsNone(self.runtime._lease)

    def test_disputed_normal_source_cannot_publish_coordinate_scope(self):
        self.create()
        selected, _ = self.player.call("enactive_snapshot", {})
        self.assertIsNotNone(selected["mission"]["coordinate_scope"])
        before = self.runtime.status()["spent_inputs"]
        delivered = deepcopy(self.bridge.delivered)
        with patch.object(self.runtime._store, "observation", side_effect=EvidenceError("fixture source-read race")):
            self.runtime._publish()
            raced, _ = self.player.call("enactive_snapshot", {})
            self.assertIsNone(raced["mission"]["coordinate_scope"])
            self.assertIsNone(raced["mission"]["current_source"])
        frame = Path(self.runtime._current.frame_path)
        # Archive files are read-only; replace only this disposable fixture file.
        frame.unlink()
        frame.write_bytes(b"corrupt fixture image")
        self.runtime._publish()
        selected, _ = self.player.call("enactive_snapshot", {})
        self.assertIsNone(selected["mission"]["coordinate_scope"])
        self.assertIsNone(selected["mission"]["current_source"])
        self.assertFalse(selected["mission"]["grants_authority"])
        self.assertEqual(selected["mission"]["spent_inputs"], before)
        self.assertEqual(self.bridge.delivered, delivered)

    def test_premature_identity_refusal_does_not_conceal_integrity_or_budget_faults(self):
        for fault in ("uncommitted_transition", "wrong_actor", "takeover", "changed_pixels",
                      "wrong_source", "process_lost", "published", "retention", "active_ledger", "root_budget"):
            with self.subTest(fault=fault):
                case = StructuredLifecycleTests("test_premature_identity_inspection_preserves_phase_for_explicit_readmission")
                case.setUp()
                try:
                    world, _ = case.paused_identity()
                    case.observe("identity-checkpoint")
                    owner = case.runtime._registered_lifecycle.phase
                    request = case.control("faulted-premature-inspection", "Character", kind="inspect")
                    with ExitStack() as faults:
                        if fault == "uncommitted_transition":
                            case.runtime._registered_lifecycle.phase = replace(owner, transition_request="character-yes")
                        elif fault == "wrong_actor":
                            case.runtime._registered_lifecycle.phase = replace(owner, actor_id="another-player")
                        elif fault == "takeover":
                            with case.controller.data_lock:
                                case.controller.state["takeover_generation"] += 1
                        elif fault == "changed_pixels":
                            # Corrupt only the disposable fixture's native frame,
                            # not a historical/native mission archive.
                            state = case.runtime._live()[0]
                            Path(case.controller.bridge / state["frame"]).write_bytes(b"\x89PNG\r\n\x1a\nchanged live pixels")
                        elif fault == "wrong_source":
                            request["sources"] = [world.observation_id]
                        elif fault == "process_lost":
                            case.process_state.update(running=False, returncode=1, outcome="exited")
                        elif fault == "published":
                            primitive = case.runtime._ledger.primitive_records()[0]
                            case.runtime._ledger._db.execute("UPDATE primitives SET state='published' WHERE id=?",
                                (primitive["logical_id"],))
                        elif fault == "retention":
                            case.runtime._store.max_frames = case.runtime._store.usage()["frames"]
                        elif fault == "active_ledger":
                            case.runtime._ledger.activate(epoch=owner.epoch, player_id=owner.actor_id, now=case.runtime._wall())
                        else:
                            root_limit = case.runtime._ledger.request("create")["request"]["limits"]["primitives"]
                            faults.enter_context(patch.object(case.runtime._ledger, "_phase_primitive_count", return_value=root_limit))
                        before = case.runtime.status()["spent_inputs"]
                        delivered = len(case.bridge.delivered)
                        response = case.runtime.command(request)
                        self.assertEqual(response["status"], "accepted", response)
                        blocked = case.settled(request["request_id"])
                        self.assertEqual(blocked["state"], "blocked", blocked)
                        self.assertNotIn("Identity inspection requires explicit readmission first", blocked["result"]["reason"])
                        self.assertEqual(case.runtime.status()["spent_inputs"], before)
                        self.assertEqual(len(case.bridge.delivered), delivered)
                        self.assertIsNone(case.runtime._lease)
                        self.assertIsNone(case.runtime._registered_lifecycle.phase)
                finally:
                    case.doCleanups()

    def test_identity_readmission_revalidates_complete_proof_before_activation(self):
        for field, value in (("actor_id", "another-player"), ("native_request_id", "00000000-0000-4000-8000-000000000000")):
            with self.subTest(field=field):
                case = StructuredLifecycleTests("test_premature_identity_inspection_preserves_phase_for_explicit_readmission")
                case.setUp()
                try:
                    _, original_unknown = case.paused_identity()
                    proof = deepcopy(case.runtime._ledger.request("transition")["result"])
                    proof["lifecycle_transition"][field] = value
                    # Deliberate corruption of this disposable test ledger only.
                    case.runtime._ledger._db.execute("UPDATE requests SET result=? WHERE id='transition'", (json.dumps(proof),))
                    charged = case.runtime.status()["spent_inputs"]
                    delivered = len(case.bridge.delivered)
                    with patch.object(case.runtime._ledger, "activate", wraps=case.runtime._ledger.activate) as activate:
                        blocked = case.run_request(case.lifecycle("bad-proof-readmit", parent="create"))
                        self.assertEqual(blocked["state"], "blocked", blocked)
                        activate.assert_not_called()
                    self.assertEqual(case.runtime.status()["spent_inputs"], charged)
                    self.assertEqual(len(case.bridge.delivered), delivered)
                    self.assertIsNone(case.runtime._lease)
                    self.assertEqual(case.runtime._ledger.request("character-yes"), original_unknown)
                finally:
                    case.doCleanups()

    def test_aged_paused_precondition_feedback_neither_refreshes_nor_grants_authority(self):
        self.paused_identity()
        phase = self.runtime._registered_lifecycle.phase
        charged, delivered = self.runtime.status()["spent_inputs"], len(self.bridge.delivered)
        request = self.control("aged-premature-inspection", "Character", kind="inspect")
        # Source age alone need not destroy a paused private phase just to
        # explain a missing step. Dispatch still needs its own fresh preflight.
        # Advance only this disposable runtime's clocks and keep them forward
        # through teardown; do not patch freshness or cause a clock rollback.
        clock, wall = self.runtime._clock, self.runtime._wall
        self.runtime._clock = lambda: clock() + 4
        self.runtime._wall = lambda: wall() + 4
        blocked = self.run_request(request)
        self.assertEqual(blocked["state"], "blocked", blocked)
        self.assertIn("explicit readmission first", blocked["result"]["reason"])
        self.assertFalse(self.runtime.status()["freshness"]["fresh"])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertEqual(self.runtime._current, phase.checkpoint)
        self.assertEqual(self.runtime.status()["spent_inputs"], charged)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertIsNone(self.runtime._lease)

    def test_paused_identity_observation_still_rejects_real_scope_and_custody_faults(self):
        for fault in ("uncommitted_transition", "wrong_actor", "wrong_epoch", "takeover", "changed_pixels",
                      "process_lost", "prepared", "published", "capacity"):
            with self.subTest(fault=fault):
                case = StructuredLifecycleTests("test_observe_after_committed_transition_keeps_paused_identity_scope")
                case.setUp()
                try:
                    case.paused_identity()
                    owner = case.runtime._registered_lifecycle.phase
                    if fault == "uncommitted_transition":
                        case.runtime._registered_lifecycle.phase = replace(owner, transition_request="character-yes")
                    elif fault in ("wrong_actor", "wrong_epoch"):
                        field = {"actor_id": "another-player"} if fault == "wrong_actor" else {"epoch": owner.epoch - 1}
                        case.runtime._registered_lifecycle.phase = replace(owner, **field)
                    elif fault == "takeover":
                        with case.controller.data_lock:
                            case.controller.state["takeover_generation"] += 1
                    elif fault == "changed_pixels":
                        case.bridge.editor_text = "Visible scene changed while paused"
                    elif fault == "process_lost":
                        case.process_state.update(running=False, returncode=1, outcome="exited")
                    elif fault in ("prepared", "published"):
                        # Fault-inject only this disposable fixture's audit. The
                        # unresolved count excludes these unsettled states.
                        primitive = case.runtime._ledger.primitive_records()[0]
                        case.runtime._ledger._db.execute("UPDATE primitives SET state=? WHERE id=?",
                            (fault, primitive["logical_id"]))
                        self.assertEqual(case.runtime.status()["unreconciled"], 0)
                    else:
                        case.runtime._store.max_frames = case.runtime._store.usage()["frames"]
                    before = case.runtime.status()["spent_inputs"]
                    delivered = len(case.bridge.delivered)
                    result = case.run_request(dict(schema="mission/10", kind="observe", request_id="bad-identity-observe",
                        mission_id=case.a.mission_id, epoch=case.runtime.status()["epoch"]))
                    self.assertEqual(result["state"], "blocked", result)
                    self.assertEqual(case.runtime.status()["spent_inputs"], before)
                    self.assertTrue(all(r["kind"] == "observe" for r in case.bridge.delivered[delivered:]))
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._registered_lifecycle.phase)
                finally:
                    case.doCleanups()

    def paused_identity(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        world = self.runtime._current
        self.run_request(self.lifecycle("world-finalize", parent="create"))
        self.run_request(self.control("world-yes", "Yes", question="Are you SURE you're finished?"))
        self.run_request(self.control("character-menu", "Custom Character"))
        self.run_request(self.lifecycle("character-finish", parent="create"))
        entered = self.run_request(self.control("character-yes", "Yes", question="Are you SURE you're finished?"))
        self.assertEqual(entered["state"], "unknown")
        original_unknown = deepcopy(self.runtime._ledger.request("character-yes"))
        self.observe("transition-observe")
        self.run_request(self.lifecycle("transition", parent="create"))
        return world, original_unknown

    def test_observe_after_committed_transition_keeps_paused_identity_scope(self):
        world, original_unknown = self.paused_identity()
        phase = self.runtime._registered_lifecycle.phase
        before = self.runtime.status()
        delivered = len(self.bridge.delivered)
        self.assertEqual(before["phase"], "paused")
        self.assertEqual(self.runtime._current.boundary_kind, "normal_play")
        selected, _ = self.player.call("enactive_snapshot", {})
        self.assertIsNone(selected["mission"]["coordinate_scope"])
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(selected["mission"]["spent_inputs"], before["spent_inputs"])
        self.observe("identity-observe")
        after = self.runtime.status()
        advanced = self.runtime._registered_lifecycle.phase
        for field in ("epoch", "phase", "pause_cause", "spent_inputs", "lease_owner"):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(advanced.root_id, phase.root_id)
        self.assertEqual(advanced.first_normal, phase.first_normal)
        self.assertNotEqual(advanced.checkpoint, phase.checkpoint)
        self.assertTrue(all(r["kind"] == "observe" for r in self.bridge.delivered[delivered:]))
        self.assertIsNone(self.runtime._lease)
        self.observe("identity-observe-again")
        self.assertEqual(self.runtime._registered_lifecycle.phase.first_normal, phase.first_normal)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
        self.run_request(self.lifecycle("identity-readmit", parent="create"))
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"] + 1)
        self.run_request(self.control("identity-inspect", "Character", kind="inspect"))
        screen = self.runtime._current
        world_id = self.remember_identity("world", "world", world, 0)
        character_id = self.remember_identity("character", "character", screen, 0)
        self.run_request(self.control("identity-return", "Cancel"))
        adopted = self.run_request(self.lifecycle("adopt", parent="create", claims=[world_id, character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)
        self.assertEqual(self.runtime._ledger.request("character-yes"), original_unknown)

    def test_premature_identity_inspection_preserves_phase_for_explicit_readmission(self):
        _, original_unknown = self.paused_identity()
        self.observe("identity-checkpoint")
        phase = self.runtime._registered_lifecycle.phase
        before = self.runtime.status()
        root_deadline = self.runtime._ledger.request("create")["deadline"]
        delivered = len(self.bridge.delivered)
        request = self.control("premature-identity-inspect", "Character", kind="inspect")
        blocked = self.run_request(request)
        self.assertEqual(blocked["state"], "blocked", blocked)
        self.assertIn("enactive_lifecycle", blocked["result"]["reason"])
        self.assertIn("readmission", blocked["result"]["reason"])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        after = self.runtime.status()
        for field in ("epoch", "phase", "pause_cause", "spent_inputs", "lease_owner"):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], root_deadline)
        self.assertEqual(self.run_request(request), blocked)
        self.assertEqual(len(self.bridge.delivered), delivered)

        readmitted = self.run_request(self.lifecycle("identity-readmit", parent="create"))
        self.assertEqual(readmitted["state"], "completed", readmitted)
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"] + 1)
        inspected = self.run_request(self.control("identity-inspect-after-readmit", "Character", kind="inspect"))
        self.assertEqual(inspected["state"], "completed", inspected)
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"] + 2)
        self.assertEqual(self.runtime._ledger.request("character-yes"), original_unknown)
        self.runtime._ledger._verify(self.a)
