"""New admitted Load, separate from continuity reload; synthetic game only."""
from dataclasses import replace
from copy import deepcopy
import unittest
from unittest.mock import patch

from harness.gameplay.lifecycle import adopted_timeline
from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture


class InitialLoadTests(MissionCreationFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.a = replace(self.a, scenario=replace(self.a.scenario, mode="load"))

    def picker(self):
        self.begin_initial_load()
        world = self.runtime._current
        selected = self.run_request(self.control("world", f"{self.a.scenario.world} (1)", parent="initial-load"))
        self.assertEqual(selected["state"], "partial", selected)
        return world

    def begin_initial_load(self):
        self.ready()
        self.stage = "load-world"
        self.assertEqual(self.run_request(self.lifecycle("initial-load", "load"))["state"], "partial")

    def test_premature_continuation_preserves_original_load_for_player_correction(self):
        self.begin_initial_load()
        phase = self.runtime._registered_lifecycle.phase
        lease = self.runtime._lease
        deadline = self.runtime._ledger.request("initial-load")["deadline"]
        mission_deadline = self.runtime._mission_deadline
        delivered = len(self.bridge.delivered)
        spent = self.runtime.status()["spent_inputs"]
        request = self.lifecycle("premature-load", "load", parent="initial-load")
        refused = self.run_request(request)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("enactive_skill", refused["result"]["reason"])
        self.assertIn("No input was sent", refused["result"]["reason"])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)
        self.assertEqual(self.runtime._mission_deadline, mission_deadline)
        self.assertEqual(self.run_request(request), refused)
        world = self.runtime._current
        selected = self.run_request(self.control("world", f"{self.a.scenario.world} (1)", parent="initial-load"))
        self.assertEqual(selected["state"], "partial", selected)
        selection = self.control("character", self.a.scenario.character, parent="initial-load")
        selection["perception"] = None
        self.assertEqual(self.run_request(selection)["state"], "unknown")
        self.observe("loaded-observe")
        adopted = self.finish_identity("initial-load", world)
        self.assertEqual(adopted["state"], "completed", adopted)
        self.assertIsNone(adopted["result"]["normal_adoption"]["saved_checkpoint_request_id"])
        self.runtime._ledger._verify(self.a)

    def assert_premature_continuation_fault(self):
        delivered = len(self.bridge.delivered)
        refused = self.run_request(self.lifecycle("premature-load", "load", parent="initial-load"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertNotIn("No input was sent", refused["result"]["reason"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.delivered), delivered)

    def test_premature_continuation_cannot_hide_frozen_controller(self):
        self.begin_initial_load()
        self.controller._mission_processing_failure(None, OSError("Synthetic storage failure"))
        self.assert_premature_continuation_fault()

    def test_premature_continuation_cannot_hide_lost_lease(self):
        self.begin_initial_load()
        with self.controller.data_lock:
            self.controller._mission_lease = None
        self.assert_premature_continuation_fault()

    def test_premature_continuation_cannot_hide_original_root_expiry(self):
        self.begin_initial_load()
        deadline = self.runtime._ledger.request("initial-load")["deadline"]
        lifecycle = self.runtime._registered_lifecycle
        command = lifecycle.command

        def cross_deadline(work):
            # Admission happened while live; the original root expires before
            # the writer decides whether this request is merely inapplicable.
            with patch.object(self.runtime, "_wall", return_value=deadline + 0.01):
                return command(work)

        with patch.object(lifecycle, "command", side_effect=cross_deadline):
            self.assert_premature_continuation_fault()
        self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)

    def test_identity_value_refusal_names_character_and_allows_explicit_correction(self):
        world = self.pending_initial_load()
        self.assertEqual(self.run_request(self.lifecycle("reconciled", "load", parent="initial-load"))["state"], "completed")
        self.assertEqual(self.run_request(self.lifecycle("readmitted", "load", parent="initial-load"))["state"], "completed")
        self.assertEqual(self.run_request(self.control("inspected", "Character", kind="inspect", parent="initial-load"))["state"], "completed")
        screen = self.runtime._current
        world_id = self.remember_identity("selected-world", "world", world, 0)
        wrong_name = self.a.scenario.character + " (Male)"
        character_id = self.remember_identity("selected-character", "character", screen, 0, value=wrong_name)
        self.assertEqual(self.run_request(self.control("dismissed", "Cancel", parent="initial-load"))["state"], "partial")
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        deadline = self.runtime._ledger.request("initial-load")["deadline"]
        delivered = len(self.bridge.delivered)
        rejected = self.run_request(self.lifecycle("wrong-adoption", "load", parent="initial-load", claims=[world_id, character_id]))
        self.assertEqual(rejected["state"], "blocked", rejected)
        self.assertIn("character identity value", rejected["result"]["reason"])
        self.assertIn(repr(wrong_name), rejected["result"]["reason"])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)
        original = next(row["entry"] for row in self.runtime._ledger.memory_records("claim") if row["entry"]["id"] == character_id)
        corrected = deepcopy(original)
        corrected.update(id="corrected-character", value=dict(quantity=None, state=self.a.scenario.character), supersedes=[character_id])
        fixed = self.run_request(dict(schema="mission/10", kind="correct", request_id="correct-character",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=corrected,
            retired_ids=[character_id], reason="Separate the interpreted name from demographic text in the retained identity screen"))
        self.assertEqual(fixed["state"], "completed", fixed)
        adopted = self.run_request(self.lifecycle("corrected-adoption", "load", parent="initial-load", claims=[world_id, corrected["id"]]))
        self.assertEqual(adopted["state"], "completed", adopted)
        self.assertEqual(original["value"]["state"], wrong_name)
        self.runtime._ledger._verify(self.a)

    def pending_initial_load(self):
        world = self.picker()
        selection = self.control("character", self.a.scenario.character, parent="initial-load")
        selection["perception"] = None
        entered = self.run_request(selection)
        self.assertEqual(entered["state"], "unknown", entered)
        self.assertEqual(self.runtime.status()["lifecycle_phase"]["stage"], "awaiting_transition")
        self.observe("loaded-observe")
        return world

    def delivery_reconciliation(self):
        return dict(schema="mission/10", kind="reconcile", request_id="wrong-recovery",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"],
            unresolved_request_id="character", evidence_id=self.runtime._current.observation_id,
            reason="Assess actual observed Load transition without replay")

    def initial_load(self, *, wrong_reconcile=False):
        world = self.pending_initial_load()
        if wrong_reconcile:
            candidate = self.runtime._registered_lifecycle.candidate
            before = self.runtime.status()
            deadline = self.runtime._ledger.request("initial-load")["deadline"]
            delivered = len(self.bridge.delivered)
            refused = self.run_request(self.delivery_reconciliation())
            self.assertEqual(refused["state"], "blocked", refused)
            self.assertIn("enactive_lifecycle", refused["result"]["reason"])
            self.assertIn("scope=lifecycle", refused["result"]["reason"])
            self.assertIs(candidate, self.runtime._registered_lifecycle.candidate)
            self.assertIsNone(self.runtime._registered_recovery.candidate)
            self.assertIsNone(self.runtime._lease)
            self.assertEqual(len(self.bridge.delivered), delivered)
            self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)
            after = self.runtime.status()
            for field in ("spent_inputs", "epoch", "unreconciled", "phase", "pause_cause"):
                self.assertEqual(after[field], before[field], field)
        return self.finish_identity("initial-load", world)

    def test_initial_load_then_own_save_reload_and_reopened_history(self):
        adopted = self.initial_load(wrong_reconcile=True)
        self.assertIsNone(adopted["result"]["normal_adoption"]["saved_checkpoint_request_id"])
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 0)
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 1)
        self.save()
        self.exit()
        self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
        self.stage = "load-world"
        self.run_request(self.lifecycle("reload", "load"))
        world = self.runtime._current
        self.run_request(self.control("reload-world", f"{self.a.scenario.world} (1)", parent="reload"))
        selection = self.control("reload-character", self.a.scenario.character, parent="reload")
        selection["perception"] = None
        self.assertEqual(self.run_request(selection)["state"], "unknown")
        self.observe("reload-observe")
        reloaded = self.finish_identity("reload", world, 1)
        self.assertEqual(reloaded["result"]["normal_adoption"]["saved_checkpoint_request_id"], "save-reconcile")
        self.runtime._ledger._verify(self.a)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 2)

    def assert_delivery_reconciliation_fault(self):
        delivered = len(self.bridge.delivered)
        refused = self.run_request(self.delivery_reconciliation())
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertNotIn("No input was sent", refused["result"]["reason"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime.status()["unreconciled"], 1)

    def test_wrong_recovery_cannot_hide_controller_failure(self):
        self.pending_initial_load()
        self.controller._mission_processing_failure(None, OSError("Synthetic storage failure"))
        self.assertTrue(self.controller.frozen)
        self.assert_delivery_reconciliation_fault()

    def test_wrong_recovery_requires_actual_native_custody(self):
        self.pending_initial_load()
        with self.controller.data_lock:
            self.controller.state = None
        self.assert_delivery_reconciliation_fault()

    def test_wrong_recovery_cannot_hide_native_error(self):
        self.pending_initial_load()
        observed = self.current()[1]
        observed["error"] = "Native unavailable"
        self.controller._accept(observed)
        self.assert_delivery_reconciliation_fault()

    def test_wrong_recovery_cannot_hide_failed_native_frame(self):
        self.pending_initial_load()
        observed = self.current()[1]
        observed.update(frame_ok=False, frame_geometry=None)
        self.controller._accept(observed)
        self.assert_delivery_reconciliation_fault()

    def test_wrong_recovery_cannot_hide_operator_pause(self):
        self.pending_initial_load()
        delivered = len(self.bridge.delivered)
        self.runtime.pause("Operator Pause before wrong recovery")
        response = self.runtime.command(self.delivery_reconciliation())
        # Pause is immediate at the controller and asynchronous at the writer.
        # A request bound before its epoch update rejects at ingress; one bound
        # afterward may queue, but can never regain the old transition custody.
        if response["status"] == "accepted":
            operation = self.settled("wrong-recovery")
            self.assertIn(operation["state"], ("blocked", "paused"), operation)
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.delivered), delivered)

    def test_wrong_recovery_cannot_extend_original_transition_deadline(self):
        self.pending_initial_load()
        deadline = self.runtime._ledger.request("initial-load")["deadline"]
        with patch.object(self.runtime, "_wall", return_value=deadline + 0.01):
            self.assert_delivery_reconciliation_fault()
            self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)

    def test_wrong_recovery_cannot_hide_native_takeover(self):
        self.pending_initial_load()
        observed = self.current()[1]
        observed.update(revision=observed["revision"] + 1,
            takeover_generation=observed["takeover_generation"] + 1, pause_origin="human")
        self.controller._accept(observed)
        self.assert_delivery_reconciliation_fault()

    def test_initial_load_is_not_permitted_by_fresh_admission(self):
        self.a = replace(self.a, scenario=replace(self.a.scenario, mode="fresh"))
        self.ready()
        refused = self.run_request(self.lifecycle("not-a-reload", "load"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("own saved checkpoint", refused["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 0)

    def test_initial_load_keeps_unique_enabled_character_precondition(self):
        self.load_rows = [dict(id="row-0", text="Another character", enabled=True, hotkey=None)]
        self.picker()
        selection = self.control("wrong-character", self.a.scenario.character, parent="initial-load")
        selection["perception"] = None
        before = self.runtime.status()["spent_inputs"]
        refused = self.run_request(selection)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)


if __name__ == "__main__":
    unittest.main()
