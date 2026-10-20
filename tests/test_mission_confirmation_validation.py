"""Real writer/ledger/transport with synthetic UI, never native acceptance.

Independent001's retained world popup supplies the question/legend distinction.
A local interpretation error must not become an input or renewed consent.
"""
import copy
import unittest
from unittest.mock import patch

from tests.test_mission_creation import MissionCreationFixture


QUESTION = "Are you SURE you're finished?"
POINTS = "Remaining points will be discarded, are you sure you want to proceed?"


class ConfirmationValidationTests(MissionCreationFixture, unittest.TestCase):
    def confirmation(self, stage):
        if stage == "save":
            self.create()
            self.assertEqual(self.run_request(self.lifecycle("save", "save"))["state"], "partial")
            return "save", "Save and quit?", "unknown"
        self.spare_points = stage == "points"
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        self.run_request(self.lifecycle("world-finalize", parent="create"))
        if stage == "world":
            return "create", QUESTION, "partial"
        self.run_request(self.control("world-yes", "Yes", question=QUESTION))
        self.run_request(self.control("character-menu", "Custom Character"))
        self.run_request(self.lifecycle("character-finish", parent="create"))
        return "create", POINTS if stage == "points" else QUESTION, "partial" if stage == "points" else "unknown"

    def reject_without_dispatch(self, bad, root):
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        before = self.runtime.status()
        root_deadline = self.runtime._ledger.request(root)["deadline"]
        delivered = copy.deepcopy(self.bridge.delivered)
        requests = len(self.runtime._ledger.request_records())
        with (patch.object(self.runtime, "_dispatch", wraps=self.runtime._dispatch) as dispatch,
              patch.object(self.runtime, "_rotate", wraps=self.runtime._rotate) as rotate,
              patch.object(self.runtime, "_observe_native", wraps=self.runtime._observe_native) as observe):
            blocked = self.run_request(bad)
        self.assertEqual(blocked["state"], "blocked", blocked)
        self.assertFalse(blocked["result"]["grants_authority"])
        self.assertEqual(blocked["result"]["source_ids"], [phase.checkpoint.observation_id])
        self.assertIn("No input was dispatched", blocked["result"]["reason"])
        dispatch.assert_not_called()
        rotate.assert_not_called()
        observe.assert_not_called()
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime._current, phase.checkpoint)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
        self.assertEqual(self.runtime.status()["metrics"]["primitives"], before["metrics"]["primitives"])
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime._ledger.request(root)["deadline"], root_deadline)
        self.assertEqual(len(self.runtime._ledger.request_records()), requests + 1)
        return blocked

    def corrected_confirmation(self, stage):
        root, question, outcome = self.confirmation(stage)
        bad = self.control("bad-question", "Yes", parent=root,
            question="Are you SURE you are finished? (Case Sensitive)")
        blocked = self.reject_without_dispatch(bad, root)
        # An identical request remains the immutable rejection, not a retry.
        delivered = copy.deepcopy(self.bridge.delivered)
        self.assertEqual(self.run_request(bad)["result"], blocked["result"])
        self.assertEqual(self.bridge.delivered, delivered)
        root_deadline = self.runtime._ledger.request(root)["deadline"]
        corrected = self.run_request(self.control("corrected-question", "Yes", parent=root, question=question))
        self.assertEqual(corrected["state"], outcome, corrected)
        self.assertEqual(len(self.bridge.delivered), len(delivered) + 1)
        self.assertEqual(self.bridge.delivered[-1].get("action"), "YES")
        self.assertEqual(self.runtime._ledger.request("bad-question")["result"], blocked["result"])
        self.assertEqual(self.runtime._ledger.request(root)["deadline"], root_deadline)

    def test_world_question_can_be_corrected_without_new_consent(self):
        self.corrected_confirmation("world")

    def test_character_question_can_be_corrected_without_new_consent(self):
        self.corrected_confirmation("character")

    def test_points_question_can_be_corrected_without_new_consent(self):
        self.corrected_confirmation("points")

    def test_save_question_can_be_corrected_without_new_consent(self):
        self.corrected_confirmation("save")

    def test_nonconfirmation_points_view_cannot_mutate_stage(self):
        root, question, _ = self.confirmation("points")
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "character_confirmation")
        bad = self.control("bad-points-kind", "Yes", parent=root)
        bad["perception"]["question"] = question
        self.reject_without_dispatch(bad, root)
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "character_confirmation")
        self.assertEqual(self.run_request(self.control("valid-points", "Yes", parent=root,
            question=question))["state"], "partial")

    def test_corrected_request_cannot_extend_expired_root(self):
        root, question, _ = self.confirmation("world")
        bad = self.control("bad-question", "Yes", question="Paraphrased")
        self.reject_without_dispatch(bad, root)
        corrected = self.control("expired-correction", "Yes", question=question)
        deadline = self.runtime._ledger.request(root)["deadline"]
        delivered = copy.deepcopy(self.bridge.delivered)
        # Per-fixture clock, kept forward through teardown; no global clock patch.
        self.runtime._wall = lambda: deadline + 0.01
        response = self.runtime.command(corrected)
        if response["status"] == "accepted":
            self.assertEqual(self.settled(corrected["request_id"])["state"], "blocked")
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime._ledger.request(root)["deadline"], deadline)
        self.assertEqual(self.runtime._ledger.request("bad-question")["state"], "blocked")

    def test_user_pause_revokes_phase_after_local_rejection(self):
        root, question, _ = self.confirmation("world")
        self.reject_without_dispatch(self.control("bad-question", "Yes", question="Paraphrased"), root)
        corrected = self.control("paused-correction", "Yes", question=question)
        delivered = copy.deepcopy(self.bridge.delivered)
        self.runtime.pause("User Pause after local validation")
        response = self.runtime.command(corrected)
        if response["status"] == "accepted":
            # Admission can race Pause persistence; it is never input delivery.
            self.assertIn(self.settled(corrected["request_id"])["state"], ("blocked", "paused", "cancelled"))
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.bridge.delivered, delivered)

    def test_pause_racing_blocked_commit_cannot_preserve_phase(self):
        root, question, _ = self.confirmation("world")
        bad = self.control("bad-question", "Yes", question="Paraphrased")
        corrected = self.control("paused-correction", "Yes", question=question)
        delivered = copy.deepcopy(self.bridge.delivered)
        complete = self.runtime._ledger.complete_request
        def pause_before_commit(identity, *args, **kwargs):
            if identity == bad["request_id"]:
                self.runtime.pause("User Pause before blocked result commit")
            return complete(identity, *args, **kwargs)
        with patch.object(self.runtime._ledger, "complete_request", side_effect=pause_before_commit):
            self.run_request(bad)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.command(corrected)["status"], "rejected")
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime._ledger.request(root)["request"]["request_id"], root)

    def test_wrong_source_is_not_softened_by_bad_question(self):
        root, _, _ = self.confirmation("world")
        bad = self.control("foreign-source", "Yes", question="Paraphrased")
        bad["sources"] = ["foreign-source"]
        bad["perception"]["source_id"] = "foreign-source"
        delivered = copy.deepcopy(self.bridge.delivered)
        operation = self.run_request(bad)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime._ledger.request(root)["request"]["request_id"], root)

    def test_corrected_request_still_rejects_changed_pixels(self):
        root, question, _ = self.confirmation("world")
        self.reject_without_dispatch(self.control("bad-question", "Yes", question="Paraphrased"), root)
        corrected = self.control("changed-pixels", "Yes", question=question)
        before = self.runtime._current
        delivered = copy.deepcopy(self.bridge.delivered)
        self.bridge.editor_text = "Different visible confirmation without changed actions"
        with patch.object(self.runtime._store, "inspect_current_boundary", return_value=(before, False)):
            operation = self.run_request(corrected)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertEqual(self.bridge.delivered, delivered)
