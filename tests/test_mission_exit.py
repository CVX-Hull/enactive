"""Owned no-save menu cleanup composition; synthetic transport, no native acceptance."""
import copy
from unittest.mock import patch
import time
import unittest

from harness.mission_runtime import MissionRuntime
from tests import test_mission_launch as launch_fixtures



class MissionExitTests(unittest.TestCase):
    setUp = launch_fixtures.MissionLaunchTests.setUp
    fake_launch = launch_fixtures.MissionLaunchTests.fake_launch
    start = launch_fixtures.MissionLaunchTests.start
    settled = launch_fixtures.MissionLaunchTests.settled
    request = launch_fixtures.MissionLaunchTests.request
    launch = launch_fixtures.MissionLaunchTests.launch

    def ready(self):
        self.bridge.behavior = self.behavior
        self.exit_code = 0
        self.exit_on_yes = True
        self.process.wait_exit.side_effect = lambda **_: copy.deepcopy(self.process_state)
        self.start()
        self.launch()

    def behavior(self, bridge, request):
        action = request.get("action")
        if action == "QUIT":
            bridge.value.update(category="YESNO", actions=["YES", "NO", "QUIT"])
            bridge.value["boundary"]["id"] = "owned-quit-confirmation"
        elif action == "YES":
            if self.exit_on_yes:
                self.process_state.update(running=False, returncode=self.exit_code, outcome="exited")
            # Final process exit has no native terminal ACK. It is never replayed.
            return False
        elif action == "NO":
            bridge.value.update(category="MAIN_MENU", actions=["UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "QUIT"])
            bridge.value["boundary"]["id"] = "main-menu-returned"
        return True

    def exit_request(self, identity="exit", **changes):
        reference = self.runtime.status()["current_source"]
        state = self.runtime._store.observation(self.runtime._current)
        return self.request(identity, operation="exit", sources=[reference["observation_id"]],
            expected_session=reference["session"], expected_revision=reference["revision"],
            expected_boundary_id=state["boundary"]["id"],
            **{"limits": dict(primitives=4, wall_seconds=10, game_seconds=1), **changes})

    def run_request(self, request):
        response = self.runtime.command(request)
        self.assertEqual(response["status"], "accepted", response)
        return self.settled(request["request_id"])

    def begin_exit(self, **changes):
        return self.run_request(self.exit_request(**changes))

    def confirmation(self, label="Yes", identity="confirmation", **changes):
        state = self.runtime._store.observation(self.runtime._current)
        reference = self.runtime._current
        request = dict(schema="mission/2", kind="skill", request_id=identity, mission_id=self.a.mission_id,
            epoch=self.runtime.status()["epoch"], skill_kind="menu", phase_id="exit", work_id=None,
            goal=dict(purpose="Answer owned Quit confirmation", label=label, outcome="activated"),
            sources=[reference.observation_id], expected_session=reference.session, expected_revision=reference.revision,
            expected_boundary_id=state["boundary"]["id"], limits=dict(primitives=1, wall_seconds=10, game_seconds=1),
            perception=dict(source_id=reference.observation_id, basis="player_interpretation", kind="confirmation",
                question="Really quit?"))
        request.update(changes)
        return request

    def test_resume_and_quit_are_separately_charged_with_no_normal_authority(self):
        self.ready()
        operation = self.begin_exit()
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_control")
        primitives = self.runtime._ledger.primitive_records()
        self.assertEqual([(p["intent"]["kind"], p["intent"]["value"], p["state"]) for p in primitives],
                         [("resume", None, "returned"), ("action", "QUIT", "returned")])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._ledger.memory_records("claim"), ())
        self.assertEqual(self.controller._mission_lease.operation, "lifecycle")

    def test_published_yes_unknown_ack_and_owned_exit_are_distinct_retained_facts(self):
        self.ready()
        self.begin_exit()
        operation = self.run_request(self.confirmation())
        self.assertEqual(operation["state"], "completed", operation)
        proof = operation["result"]["normal_exit"]
        primitive = self.runtime._ledger.primitive(proof["terminal_logical_id"])
        self.assertEqual(primitive["state"], "unknown")
        self.assertEqual(primitive["result"]["transport_disposition"], "unknown")
        self.assertIsNotNone(primitive["effect"])
        self.assertEqual(proof["native_request_id"], primitive["native_id"])
        self.assertTrue(proof["retirement"]["retired_pending"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertIsNone(self.controller.pending)
        self.assertTrue((self.controller.admissions / (primitive["native_id"] + ".json")).is_file())
        self.assertTrue(any(row["request"]["id"] == primitive["native_id"] for row in self.controller.unknown_outcomes))
        self.assertTrue(self.controller.pause_requested)
        self.assertTrue(self.controller.frozen)
        self.assertIsNone(self.controller._mission_lease)
        self.assertIsNone(self.runtime.status()["lifecycle_phase"])
        self.assertEqual([r.get("action") for r in self.bridge.delivered if r["kind"] == "action"], ["QUIT", "YES"])

    def test_committed_exit_resolves_history_but_reopen_restores_no_handle_phase_or_input(self):
        self.ready()
        self.begin_exit()
        self.assertEqual(self.run_request(self.confirmation())["state"], "completed")
        self.runtime.close()
        custody = [event["outcome"] for event in self.controller.events
                   if event["request"]["kind"] == "mission_process_shutdown_custody"]
        self.assertTrue(custody[-1]["normal_exit_verified"])
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["native_process"]["unresolved_custody_requests"], [])
        self.assertIsNone(self.runtime._native)
        self.assertIsNone(self.runtime._owned_launch)
        self.assertIsNone(self.runtime.status()["lifecycle_phase"])
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)

    def test_declining_quit_preserves_owned_custody_for_new_deliberate_exit(self):
        self.ready()
        self.begin_exit()
        declined = self.run_request(self.confirmation("No"))
        self.assertEqual(declined["state"], "partial", declined)
        self.assertFalse(declined["result"]["normal_exit_verified"])
        self.assertNotIn("normal_exit", declined["result"])
        self.assertTrue(self.process_state["running"])
        self.assertIsNone(self.runtime.status()["lifecycle_phase"])
        retried = self.begin_exit(identity="exit-again")
        self.assertEqual(retried["state"], "partial", retried)
        self.assertEqual(self.runtime.status()["spent_inputs"], 5)

    def test_root_ceiling_counts_resume_and_children_without_reset(self):
        self.ready()
        self.begin_exit(limits=dict(primitives=2, wall_seconds=10, game_seconds=1))
        operation = self.run_request(self.confirmation())
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn("normal_exit", operation["result"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertTrue(self.process_state["running"])
        self.assertFalse(any(r.get("action") == "YES" for r in self.bridge.delivered))

    def test_new_root_cannot_adopt_operator_pause_since_launch(self):
        self.ready()
        self.runtime.pause()
        deadline = time.monotonic() + 2
        while self.runtime._ledger.snapshot(now=time.time())["pause_cause"] != "user" and time.monotonic() < deadline:
            time.sleep(0.005)
        operation = self.begin_exit()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("operator mark", operation["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 0)

    def test_wrong_question_or_identity_never_publishes_confirmation(self):
        self.ready()
        self.begin_exit()
        request = self.confirmation()
        request["perception"]["question"] = "Delete world?"
        operation = self.run_request(request)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertFalse(any(r.get("action") == "YES" for r in self.bridge.delivered))

    def test_nonzero_exit_keeps_unknown_cost_and_unresolved_custody(self):
        self.ready()
        self.exit_code = 1
        self.begin_exit()
        operation = self.run_request(self.confirmation())
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn("normal_exit", operation["result"])
        self.assertIsNotNone(self.controller.pending)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["native_process"]["unresolved_custody_requests"], ["launch"])

    def test_missing_exit_does_not_replay_yes_or_claim_normal_shutdown(self):
        self.ready()
        self.exit_on_yes = False
        self.process.wait_exit.side_effect = lambda **_: copy.deepcopy(self.process_state)
        self.begin_exit()
        operation = self.run_request(self.confirmation())
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn("normal_exit", operation["result"])
        self.assertEqual(sum(r.get("action") == "YES" for r in self.bridge.delivered), 1)
        self.assertIsNotNone(self.controller.pending)

    def test_changed_phase_observe_image_stops_without_confirmation(self):
        self.ready()
        self.begin_exit()
        self.bridge.value["actions"].append("CHANGED")
        operation = self.run_request(dict(schema="mission/2", kind="observe", request_id="changed-observe",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("Contradictory", operation["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_resume_publication_loses_to_user_pause_in_preflight(self):
        self.ready()
        prepare = self.runtime._ledger.prepare_primitive
        def pause_after_prepare(*args, **kwargs):
            result = prepare(*args, **kwargs)
            self.runtime.pause("Prepublication operator stop")
            return result
        with patch.object(self.runtime._ledger, "prepare_primitive", side_effect=pause_after_prepare):
            operation = self.begin_exit()
        self.assertNotEqual(operation["state"], "completed")
        self.assertEqual(self.controller.operator_pause_generation, 1)
        self.assertEqual(self.runtime._ledger.snapshot(now=time.time())["pause_cause"], "user")
        self.assertFalse(any(row["kind"] == "resume" for row in self.bridge.delivered))
        primitives = self.runtime._ledger.primitive_records()
        self.assertEqual(len(primitives), 1)
        self.assertEqual(primitives[0]["state"], "not_dispatched")

    def test_routine_owned_menu_and_prompt_observe_preserve_exact_checkpoint_lineage(self):
        self.ready()
        before = self.runtime._owned_launch.checkpoint
        observe = lambda identity: self.run_request(dict(schema="mission/2", kind="observe", request_id=identity,
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        self.assertEqual(observe("owned-menu-observe")["state"], "completed")
        self.assertNotEqual(self.runtime._owned_launch.checkpoint, before)
        self.assertEqual(self.begin_exit()["state"], "partial")
        self.assertEqual(observe("owned-prompt-observe")["state"], "completed")
        self.assertEqual(self.run_request(self.confirmation("No"))["state"], "partial")
        self.assertTrue(self.process_state["running"])

    def test_short_child_uses_its_refreshed_source_without_renewing_root_deadline(self):
        self.ready()
        root = self.begin_exit()
        root_deadline = root["deadline"]
        time.sleep(1.05)
        self.run_request(dict(schema="mission/2", kind="observe", request_id="fresh-prompt",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        operation = self.run_request(self.confirmation("No", limits=dict(primitives=1, wall_seconds=1, game_seconds=1)))
        self.assertEqual(operation["state"], "partial", operation)
        self.assertLess(operation["deadline"], root_deadline)
        self.assertEqual(self.runtime._ledger.request("exit")["deadline"], root_deadline)

    def test_native_takeover_on_terminal_ready_cannot_become_normal_exit(self):
        self.ready()
        original = self.behavior
        def takeover(bridge, request):
            if request.get("action") == "YES":
                self.process_state.update(running=False, returncode=0, outcome="exited")
                bridge.value.update(paused=True, pause_origin="human", takeover_generation=1)
                bridge.value["boundary"]["control_generation"] += 1
                return True
            return original(bridge, request)
        self.bridge.behavior = takeover
        self.begin_exit()
        operation = self.run_request(self.confirmation())
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn("normal_exit", operation["result"])
        self.assertIn("takeover", operation["result"]["reason"])
        self.assertFalse(any(event["request"]["kind"] == "mission_exit_retirement" for event in self.controller.events))

    def test_native_takeover_during_exit_wait_prevents_retirement(self):
        self.ready()
        self.begin_exit()
        def wait_exit(**_):
            with self.controller.data_lock:
                self.controller.state["takeover_generation"] += 1
            return copy.deepcopy(self.process_state)
        self.process.wait_exit.side_effect = wait_exit
        operation = self.run_request(self.confirmation())
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn("normal_exit", operation["result"])
        self.assertIsNotNone(self.controller.pending)

    def unexpected_normal_case(self, trigger):
        from tests.test_gameplay_evidence import observation
        self.ready()
        normal_scene = observation()["scene"]
        original = self.behavior
        def unexpected_normal(bridge, request):
            if request["kind"] == trigger or request.get("action") == trigger:
                bridge.value.update(in_game=True, category="DEFAULTMODE", scene=normal_scene, actions=["UP"])
                bridge.value["boundary"]["kind"] = "normal_play"
                return True
            return original(bridge, request)
        self.bridge.behavior = unexpected_normal
        operation = self.begin_exit()
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._bindings, {})
        self.assertEqual(self.runtime._ledger.memory_records("claim"), ())
        self.assertTrue(any(ref.boundary_kind == "normal_play" for ref in self.runtime._store.historical_references))
        return normal_scene

    def test_unexpected_resume_normal_is_diagnostic_without_map_clock_memory_or_binding(self):
        self.unexpected_normal_case("resume")

    def test_unexpected_quit_normal_remains_unadopted_across_reopen_and_observe(self):
        self.unexpected_normal_case("QUIT")
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["native_process"]["unresolved_custody_requests"], ["launch"])
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        operation = self.run_request(dict(schema="mission/2", kind="observe", request_id="diagnostic-observe",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._ledger.memory_records("claim"), ())

    def test_terminal_yes_normal_return_plus_code_zero_is_not_no_save_exit(self):
        from tests.test_gameplay_evidence import observation
        self.ready()
        original = self.behavior
        def normal_after_yes(bridge, request):
            if request.get("action") == "YES":
                self.process_state.update(running=False, returncode=0, outcome="exited")
                bridge.value.update(in_game=True, category="DEFAULTMODE", scene=observation()["scene"], actions=["UP"])
                bridge.value["boundary"]["kind"] = "normal_play"
                return True
            return original(bridge, request)
        self.bridge.behavior = normal_after_yes
        self.begin_exit()
        operation = self.run_request(self.confirmation())
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn("normal_exit", operation["result"])
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._ledger.memory_records("claim"), ())

    def test_normal_exit_proof_corruption_cannot_resolve_custody_on_reopen(self):
        import json
        import sqlite3
        from contextlib import closing
        from harness.gameplay.mission_contracts import canonical
        from harness.gameplay.mission_ledger import LedgerError, MissionLedger
        self.ready()
        self.begin_exit()
        self.assertEqual(self.run_request(self.confirmation())["state"], "completed")
        directory = self.runtime._ledger.directory
        self.runtime.close()
        original = (directory / "mission.sqlite3").read_bytes()
        changes = ("nested-string", "logical-id", "effect-source", "status", "missing-launch-source", "null-phase", "bool-code")
        for index, mutation in enumerate(changes):
            with self.subTest(mutation=mutation):
                target = directory.parent / f"corrupt-exit-{index}"
                target.mkdir()
                (target / "mission.sqlite3").write_bytes(original)
                with closing(sqlite3.connect(target / "mission.sqlite3")) as db, db:
                    result = json.loads(db.execute("SELECT result FROM requests WHERE id='confirmation'").fetchone()[0])
                    logical = result["normal_exit"]["terminal_logical_id"]
                    if mutation == "nested-string":
                        result["normal_exit"] = canonical(result["normal_exit"])
                    elif mutation == "logical-id":
                        primitive = json.loads(db.execute("SELECT result FROM primitives WHERE id=?", (logical,)).fetchone()[0])
                        primitive["logical_action_id"] = "other-logical"
                        db.execute("UPDATE primitives SET result=? WHERE id=?", (canonical(primitive), logical))
                    elif mutation == "effect-source":
                        effect = json.loads(db.execute("SELECT effect FROM primitives WHERE id=?", (logical,)).fetchone()[0])
                        effect["sources"] = ["unrelated"]
                        db.execute("UPDATE primitives SET effect=? WHERE id=?", (canonical(effect), logical))
                    elif mutation == "status":
                        db.execute("UPDATE requests SET state='blocked' WHERE id='confirmation'")
                    elif mutation == "missing-launch-source":
                        source = result["normal_exit"]["source_ids"][-1]
                        result["normal_exit"]["source_ids"] = [source]
                        result["phase"]["source_ids"] = [source]
                        effect = json.loads(db.execute("SELECT effect FROM primitives WHERE id=?", (logical,)).fetchone()[0])
                        effect["sources"] = [source]
                        db.execute("UPDATE primitives SET effect=? WHERE id=?", (canonical(effect), logical))
                    elif mutation == "null-phase":
                        result["phase"] = None
                    else:
                        result["normal_exit"]["returncode"] = False
                    db.execute("UPDATE requests SET result=? WHERE id='confirmation'", (canonical(result),))
                with self.assertRaises(LedgerError):
                    MissionLedger(target, now=time.time(), admission=self.a)

    def test_terminal_timeout_can_outlive_preflight_freshness_without_losing_exit_correlation(self):
        self.ready()
        self.begin_exit()
        self.controller.timeout = 3.05
        request = self.confirmation()
        response = self.runtime.command(request)
        self.assertEqual(response["status"], "accepted", response)
        end = time.monotonic() + 5
        while time.monotonic() < end:
            result = self.runtime.command(dict(schema="mission/2", kind="result", mission_id=self.a.mission_id,
                operation_id=request["request_id"]))["operation"]
            if result["result"] is not None:
                break
            time.sleep(0.02)
        self.assertEqual(result["state"], "completed", result)
        primitive = self.runtime._ledger.primitive(result["result"]["normal_exit"]["terminal_logical_id"])
        self.assertEqual(primitive["state"], "unknown")
        self.assertIn("Deadline reached", primitive["result"]["reason"])
        self.assertIsNotNone(primitive["effect"])
        self.assertIsNone(self.controller.pending)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
