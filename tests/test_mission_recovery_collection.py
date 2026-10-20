"""Mission integration of retained delivery evidence; no readmission/native claim."""
import copy
import unittest
from unittest.mock import patch

from harness.gameplay.evidence import CapacityError
from tests import test_mission_runtime as fixtures


class MissionRecoveryCollectionTests(unittest.TestCase):
    setUp = fixtures.MissionRuntimeTests.setUp
    wait = fixtures.MissionRuntimeTests.wait
    request = fixtures.MissionRuntimeTests.request
    result = fixtures.MissionRuntimeTests.result
    settled = fixtures.MissionRuntimeTests.settled
    start = fixtures.MissionRuntimeTests.start
    navigation = fixtures.MissionRuntimeTests.navigation
    control = fixtures.MissionRuntimeTests.control

    def unknown(self, *, interaction=False):
        self.bridge.value["actions"].append("open")
        self.start()
        self.bridge.behavior = lambda _, request: request["kind"] != "action"
        data = (self.control("interact", {"action": "open", "intent": "Open observed door",
                "desired_outcome": "Inspect result"}) if interaction else self.navigation())
        self.assertEqual(self.runtime.command(data)["status"], "accepted")
        operation = self.settled(data["request_id"])
        self.assertEqual(operation["state"], "unknown", operation)
        candidate = self.runtime._registered_recovery.candidate
        self.assertIsNotNone(candidate)
        self.assertFalse(candidate.revoked)
        self.assertEqual(candidate.generation, self.controller.pause_generation)
        self.assertEqual(candidate.recovery_epoch, self.runtime.status()["epoch"])
        return candidate

    def observe(self, identity="collect-observe"):
        data = self.request("observe", request_id=identity)
        response = self.runtime.command(data)
        self.assertEqual(response["status"], "accepted", response)
        return self.settled(identity)

    def terminal(self, candidate):
        value = copy.deepcopy(self.bridge.value)
        value.update(id=candidate.request["id"], paused=True, pause_origin="recovery", status="ready", frame_ok=True)
        self.bridge.value = value
        self.bridge.publish(value)

    def test_navigation_unknown_keeps_original_reservation_and_collects_before_observe(self):
        candidate = self.unknown()
        original = self.runtime._ledger.primitive(candidate.logical_id)
        reservation = self.runtime._store._reservation
        self.assertIs(candidate.reservation, reservation)
        self.terminal(candidate)
        count = len(self.bridge.delivered)
        observed = self.observe()
        self.assertEqual(observed["state"], "completed")
        retained = self.runtime._registered_recovery.candidate
        self.assertTrue(retained.collected)
        self.assertEqual(retained.proof["basis"], "terminal_response")
        self.assertEqual(retained.proof["request"], candidate.request)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id), original)
        self.assertIs(self.runtime._store._reservation, reservation)
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["unresolved_effects"], [candidate.logical_id])
        self.assertIsNone(self.runtime._lease)
        self.assertTrue(self.controller.pause_requested)
        # Preserving data is not releasing capacity, effect reconciliation or Resume.
        with self.assertRaises(CapacityError):
            self.runtime._store.reserve_dispatch(self.runtime._current, **self.runtime._clocks())
        self.runtime._ledger._verify(self.a)

    def test_interaction_unknown_is_not_revoked_again_by_semantic_policy(self):
        candidate = self.unknown(interaction=True)
        self.assertEqual(candidate.generation, self.controller.pause_generation)
        self.terminal(candidate)
        self.observe()
        retained = self.runtime._registered_recovery.candidate
        self.assertTrue(retained.collected)
        self.assertIsNotNone(retained.proof)
        self.assertFalse(retained.revoked)

    def test_ambiguous_first_collection_does_not_gain_proof_from_a_later_frame(self):
        candidate = self.unknown()
        self.observe()
        retained = self.runtime._registered_recovery.candidate
        self.assertTrue(retained.collected)
        self.assertIsNone(retained.proof)
        with patch.object(self.controller, "inspect_mission_delivery", side_effect=AssertionError("No renewed collection")):
            self.observe("second-observe")
        self.assertEqual(self.runtime.status()["unresolved_effects"], [candidate.logical_id])
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id)["state"], "unknown")

    def test_user_pause_revokes_collection_but_keeps_uncertain_capacity_and_cost(self):
        candidate = self.unknown()
        reservation = candidate.reservation
        self.runtime.pause("User Pause before original evidence collection")
        self.wait(lambda: not self.runtime._pending_pauses and self.runtime.status()["epoch"] ==
                  self.runtime._ledger.snapshot(now=self.runtime._wall())["epoch"])
        with patch.object(self.controller, "inspect_mission_delivery", side_effect=AssertionError("No new Pause consent")):
            self.observe()
        retained = self.runtime._registered_recovery.candidate
        self.assertTrue(retained.revoked)
        self.assertIs(retained.reservation, reservation)
        self.assertIs(self.runtime._store._reservation, reservation)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id)["state"], "unknown")
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.runtime._lease)


if __name__ == "__main__":
    unittest.main()
