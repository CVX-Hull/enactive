"""Synthetic delivery reconciliation/readmission; no native gameplay claim."""
import copy
from contextlib import closing
import json
import sqlite3
import threading
import unittest
from unittest.mock import patch

from harness.gameplay.mission_ledger import MissionLedger
from harness.gameplay.contracts import canonical
from harness.gameplay.contracts import ContractError
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

    def unknown(self, *, interaction=False, target=(1, 0, 0), hold_position=False, limits=None):
        self.bridge.value["actions"].append("open")
        self.start()
        def withhold(bridge, request):
            if request["kind"] != "action": return True
            if hold_position:
                # Synthetic processed-but-no-displacement outcome. This is not
                # an engine simulation or a repair of real campaign evidence.
                bridge.value["scene"]["position"] = [0, 0, 0]
            return False
        self.bridge.behavior = withhold
        data = (self.control("interact", {"action": "open", "intent": "Open observed door",
                "desired_outcome": "Inspect result"}) if interaction else self.navigation(target=target))
        if limits is not None: data["limits"] = limits
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
        self.assertIsNone(self.runtime._store._reservation)
        self.assertIsNone(retained.reservation)
        self.assertIsNotNone(retained.terminal_source)
        self.assertNotEqual(retained.terminal_source, self.runtime._current)
        self.assertEqual(self.runtime._store.observation(retained.terminal_source)["id"], candidate.request["id"])
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["unresolved_effects"], [candidate.logical_id])
        self.assertIsNone(self.runtime._lease)
        self.assertTrue(self.controller.pause_requested)
        # The actual ACK frame consumes its original reservation; it does not
        # settle the effect or grant a lease. Missing proof keeps capacity below.
        self.runtime._ledger._verify(self.a)

    def reconcile_request(self, candidate, identity="resolve"):
        return self.request("reconcile", request_id=identity, unresolved_request_id=candidate.request_id,
            evidence_id=self.runtime._current.observation_id, reason="Assess exact captured delivery, not semantic success")

    def run_request(self, data):
        response = self.runtime.command(data)
        self.assertEqual(response["status"], "accepted", response)
        return self.settled(data["request_id"])

    def ready_resolution(self, *, target=(1, 0, 0), limits=None):
        candidate = self.unknown(target=target, hold_position=True, limits=limits)
        self.terminal(candidate)
        self.observe()
        operation = self.run_request(self.reconcile_request(candidate))
        self.assertEqual(operation["state"], "completed", operation)
        return candidate, operation

    def readmit_request(self, **changes):
        ref = self.runtime._current
        data = self.request("readmit", request_id="readmit-recovery", mode="recovery", reconciliation_request_id="resolve",
            phase_id=self.runtime._registered_recovery.phase.root_id, work_id=None, sources=[ref.observation_id],
            expected_session=ref.session, expected_revision=ref.revision,
            expected_boundary_id=self.runtime._store.observation(ref)["boundary"]["id"],
            limits=dict(primitives=1, wall_seconds=60, game_seconds=1200))
        data.update(changes)
        return data

    def test_reconcile_is_read_only_then_separate_resume_and_same_root_navigation(self):
        candidate, operation = self.ready_resolution()
        count = len(self.bridge.delivered)
        self.assertIsNone(self.runtime._lease)
        self.assertTrue(self.controller.pause_requested)
        original = self.runtime._ledger.primitive(candidate.logical_id)
        self.assertEqual(original["state"], "unknown")
        self.assertEqual(original["effect"]["proof"], operation["result"]["reconciliation"])
        self.assertEqual(original["effect"]["proof"]["native_request_json"], canonical(candidate.request))
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["unresolved_effects"], [])
        self.bridge.behavior = None
        readmitted = self.run_request(self.readmit_request())
        self.assertEqual(readmitted["state"], "completed", readmitted)
        self.assertEqual([r["kind"] for r in self.bridge.delivered[count:]], ["resume"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        child = self.navigation(target=(1, 0, 0), request_id="suffix", phase_id=candidate.root_id)
        suffix = self.run_request(child)
        self.assertEqual(suffix["state"], "completed", suffix)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertIsNone(self.runtime._registered_recovery.continuation)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id), original)
        self.runtime._ledger._verify(self.a)

    def test_recovered_suffix_menu_transfers_to_original_root_without_new_allowance(self):
        candidate, _ = self.ready_resolution()
        original = self.runtime._ledger.primitive(candidate.logical_id)
        deadline = self.runtime._ledger.request(candidate.root_id)["deadline"]
        anchor = self.runtime._registered_recovery.phase.game_anchor
        self.bridge.behavior = None
        self.assertEqual(self.run_request(self.readmit_request())["state"], "completed")
        normal = copy.deepcopy(self.bridge.value["scene"])
        def menu(bridge, request):
            if request.get("action") == "RIGHT":
                bridge.value.update(scene=None, ui=None, category="UILIST", actions=["UILIST.QUIT"])
                bridge.value["boundary"].update(kind="menu", id="suffix-menu")
            elif request.get("action") == "UILIST.QUIT":
                bridge.value.update(scene=copy.deepcopy(normal), ui=None, category="DEFAULTMODE",
                                    actions=["UP", "DOWN", "LEFT", "RIGHT"])
                bridge.value["boundary"].update(kind="normal_play", id="suffix-cancel-normal")
            return True
        self.bridge.behavior = menu
        suffix = self.run_request(self.navigation(request_id="menu-suffix", phase_id=candidate.root_id))
        self.assertEqual(suffix["state"], "partial", suffix)
        self.assertEqual(suffix["result"]["verified_steps"], 0)
        self.assertEqual(suffix["result"]["phase"]["origin_request_id"], candidate.root_id)
        self.assertEqual(self.runtime._prompt_phase.game_anchor, anchor)
        self.assertIsNone(self.runtime._registered_recovery.continuation)
        reference = self.runtime.status()["current_source"]
        cancel = self.control("menu", dict(purpose="Cancel", label="Cancel", outcome="dismissed"),
            request_id="suffix-menu-cancel", phase_id=candidate.root_id, perception=dict(
                kind="dismissal", basis="player_interpretation", question="Menu",
                source_id=reference["observation_id"]))
        closed = self.run_request(cancel)
        self.assertEqual(closed["state"], "partial", closed)
        self.assertEqual(closed["result"]["phase"]["origin_request_id"], candidate.root_id)
        self.assertEqual(closed["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)
        self.assertEqual(self.runtime._ledger.request(candidate.root_id)["deadline"], deadline)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id), original)
        self.runtime._ledger._verify(self.a)

    def test_ambiguous_input_cannot_reconcile_from_a_later_frame(self):
        candidate = self.unknown()
        self.observe()
        count = len(self.bridge.delivered)
        result = self.run_request(self.reconcile_request(candidate))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertIsNone(self.runtime._ledger.primitive(candidate.logical_id)["effect"])
        self.assertIsNotNone(self.runtime._store._reservation)

    def test_user_pause_after_proof_cannot_be_resampled_by_readmission(self):
        candidate, _ = self.ready_resolution()
        data = self.readmit_request()
        count = len(self.bridge.delivered)
        self.runtime.pause("User Pause after proof")
        self.wait(lambda: not self.runtime._pending_pauses)
        data["epoch"] = self.runtime.status()["epoch"]
        response = self.runtime.command(data)
        self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id)["state"], "unknown")
        self.assertIsNone(self.runtime._lease)

    def test_unknown_resume_is_not_a_recursive_recovery_candidate(self):
        candidate, _ = self.ready_resolution()
        data = self.readmit_request()
        self.bridge.behavior = lambda _, request: request["kind"] != "resume"
        result = self.run_request(data)
        self.assertEqual(result["state"], "unknown", result)
        self.assertTrue(self.runtime._registered_recovery.candidate.revoked)
        self.assertEqual(self.runtime._registered_recovery.candidate.logical_id, candidate.logical_id)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertIsNone(self.runtime._lease)

    def test_reopen_validates_proof_but_restores_no_phase_or_authority(self):
        candidate, _ = self.ready_resolution()
        directory = self.runtime._ledger.directory
        self.runtime.close()
        with MissionLedger(directory, now=self.runtime._wall()) as ledger:
            self.assertEqual(ledger.primitive(candidate.logical_id)["state"], "unknown")
            self.assertEqual(ledger.snapshot(now=self.runtime._wall())["phase"], "paused")
        self.assertIsNone(self.runtime._registered_recovery.phase)

    def test_completed_readmission_reopens_without_restoring_continuation(self):
        candidate, _ = self.ready_resolution()
        self.bridge.behavior = None
        operation = self.run_request(self.readmit_request())
        self.assertEqual(operation["state"], "completed", operation)
        directory = self.runtime._ledger.directory
        self.runtime.close()
        with MissionLedger(directory, now=self.runtime._wall()) as ledger:
            self.assertEqual(ledger.primitive(candidate.logical_id)["state"], "unknown")
            self.assertEqual(ledger.snapshot(now=self.runtime._wall())["phase"], "paused")
            self.assertEqual(ledger.snapshot(now=self.runtime._wall())["spent_inputs"], 2)
        self.assertIsNone(self.runtime._registered_recovery.continuation)

    def test_stale_diagnostic_blocks_without_revoking_original_readonly_collection(self):
        candidate = self.unknown(hold_position=True)
        self.terminal(candidate)
        self.observe()
        clock = self.runtime._clock
        with patch.object(self.runtime, "_clock", side_effect=lambda: clock() + 3.2):
            result = self.run_request(self.reconcile_request(candidate, "stale-resolution"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("fresh current", result["result"]["reason"])
        self.assertIsNone(self.runtime._ledger.primitive(candidate.logical_id)["effect"])
        self.assertFalse(self.runtime._registered_recovery.candidate.revoked)
        self.observe("fresh-diagnostic")
        result = self.run_request(self.reconcile_request(candidate))
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.runtime._lease)

    def test_suffix_cannot_borrow_child_game_budget_and_retains_returned_input(self):
        candidate, _ = self.ready_resolution(limits=dict(primitives=8, wall_seconds=120, game_seconds=2))
        self.bridge.behavior = None
        readmitted = self.run_request(self.readmit_request())
        self.assertEqual(readmitted["state"], "completed", readmitted)
        def overshoot(bridge, request):
            if request["kind"] == "action": bridge.value["scene"]["turn"] += 3
            return True
        self.bridge.behavior = overshoot
        suffix = self.run_request(self.navigation(request_id="overshoot-suffix", phase_id=candidate.root_id))
        self.assertEqual(suffix["state"], "partial", suffix)
        self.assertIn("budget_stop", suffix["result"])
        self.assertIsNone(self.runtime._lease)
        self.assertTrue(self.controller.pause_requested)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)

    def test_resume_and_suffix_share_original_primitive_ceiling(self):
        candidate, _ = self.ready_resolution(limits=dict(primitives=2, wall_seconds=120, game_seconds=1200))
        self.bridge.behavior = None
        readmitted = self.run_request(self.readmit_request())
        self.assertEqual(readmitted["state"], "completed", readmitted)
        count = len(self.bridge.delivered)
        suffix = self.run_request(self.navigation(request_id="budget-suffix", phase_id=candidate.root_id))
        self.assertNotEqual(suffix["state"], "completed", suffix)
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_repeated_unknown_retains_first_root_game_anchor(self):
        original, _ = self.ready_resolution()
        self.bridge.behavior = None
        self.assertEqual(self.run_request(self.readmit_request())["state"], "completed")
        self.bridge.behavior = lambda _, request: request["kind"] != "action"
        result = self.run_request(self.navigation(request_id="uncertain-suffix", phase_id=original.root_id))
        self.assertEqual(result["state"], "unknown", result)
        candidate = self.runtime._registered_recovery.candidate
        self.assertEqual(candidate.root_id, original.root_id)
        self.assertEqual(candidate.game_anchor, original.game_anchor)
        self.assertEqual(candidate.origin_epoch, original.recovery_epoch)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id)["result"]["dispatch_binding"]["game_anchor_source_id"],
                         original.game_anchor.observation_id)

    def test_handoff_cannot_skip_pending_continuation(self):
        candidate, _ = self.ready_resolution()
        self.bridge.behavior = None
        self.assertEqual(self.run_request(self.readmit_request())["state"], "completed")
        count = len(self.bridge.delivered)
        handoff = self.request("handoff", request_id="skip-root", checkpoint_ids=[self.runtime._current.observation_id],
            successor_role="player", unfinished_work_ids=[])
        result = self.run_request(handoff)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id)["state"], "unknown")

    def test_new_navigation_root_cannot_renew_pending_continuation(self):
        candidate, _ = self.ready_resolution()
        self.bridge.behavior = None
        self.assertEqual(self.run_request(self.readmit_request())["state"], "completed")
        count = len(self.bridge.delivered)
        result = self.run_request(self.navigation(request_id="renew-navigation-root", phase_id=None))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id)["state"], "unknown")

    def test_reopen_rejects_tampered_resume_logical_receipt(self):
        self.ready_resolution()
        self.bridge.behavior = None
        result = self.run_request(self.readmit_request())
        self.assertEqual(result["state"], "completed", result)
        path, directory = self.runtime._ledger.path, self.runtime._ledger.directory
        self.runtime.close()
        with closing(sqlite3.connect(path)) as db, db:
            identity, raw = db.execute("SELECT id,result FROM primitives WHERE request_id='readmit-recovery'").fetchone()
            receipt = json.loads(raw)
            receipt["logical_action_id"] = "another-resume"
            db.execute("UPDATE primitives SET result=? WHERE id=?", (canonical(receipt), identity))
        original = path.read_bytes()
        with self.assertRaises(ContractError): MissionLedger(directory, now=self.runtime._wall())
        self.assertEqual(path.read_bytes(), original)

    def test_exact_unclaimed_retirement_releases_only_its_reserved_frame(self):
        execute = self.controller.execute_mission
        def unclaimed(*args, **kwargs):
            preflight = kwargs["preflight"]
            def stop_consumer(state, received):
                preflight(state, received)
                self.bridge.__exit__(None, None, None)
            kwargs["preflight"] = stop_consumer
            return execute(*args, **kwargs)
        with patch.object(self.controller, "execute_mission", side_effect=unclaimed):
            candidate = self.unknown()
        self.bridge.stopped.clear()
        self.bridge.thread = threading.Thread(target=self.bridge.run, daemon=True)
        self.bridge.__enter__()
        self.observe()
        self.assertEqual(self.runtime._registered_recovery.candidate.proof["basis"], "unclaimed_retirement")
        self.assertIsNotNone(self.runtime._store._reservation)
        result = self.run_request(self.reconcile_request(candidate))
        self.assertEqual(result["state"], "completed", result)
        self.assertIsNone(self.runtime._store._reservation)
        self.assertIsNone(result["result"]["reconciliation"]["terminal_source_id"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime._ledger.primitive(candidate.logical_id)["state"], "unknown")

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
