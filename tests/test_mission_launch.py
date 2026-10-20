"""Registered launch composition with a fake process; never native/game acceptance."""
import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from harness.controller import Controller
from harness.mission_runtime import MissionRuntime
from harness.native_process import NativeProcess
from tests.test_mission_contracts import admission
from tests.test_mission_runtime import VisibleBridge


class MissionLaunchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # Functional file exchanges need scheduling/fsync time on shared runners.
        # Deliberately withheld ACKs still time out and remain unknown.
        self.controller = Controller(Path(temporary.name), timeout=0.8)
        self.addCleanup(self.controller.close)
        self.bridge = VisibleBridge(self.controller)
        self.bridge.value.update(in_game=False, scene=None, ui=None, category="MAIN_MENU",
            actions=["UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "QUIT"], paused=True)
        self.bridge.value["boundary"].update(kind="menu", id="main-menu")
        self.bridge.__enter__()
        self.addCleanup(self.bridge.__exit__, None, None, None)
        self.process_state = dict(launch_id=None, pid=None, running=False, returncode=None,
                                  outcome="not_launched", error=None)
        self.process = Mock(spec=NativeProcess)
        self.process.status.side_effect = lambda: copy.deepcopy(self.process_state)
        self.process.launch.side_effect = self.fake_launch
        self.factory = self.enterContext(patch("harness.mission_runtime.NativeProcess", return_value=self.process))
        self.runtime = MissionRuntime(self.controller)
        self.addCleanup(lambda: self.runtime.close())
        self.a = admission()

    def fake_launch(self, *, deadline_monotonic, cancelled):
        self.assertGreater(deadline_monotonic, time.monotonic())
        self.assertLessEqual(deadline_monotonic, time.monotonic() + 60)
        self.assertFalse(cancelled())
        self.process_state.update(launch_id="owned-launch", pid=1234, running=True, outcome="running")
        return copy.deepcopy(self.process_state)

    def settled(self, identity):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            response = self.runtime.command(dict(schema="mission/7", kind="result",
                mission_id=self.a.mission_id, operation_id=identity))
            operation = response.get("operation")
            if operation is not None and operation["result"] is not None:
                return operation
            threading.Event().wait(0.005)
        self.fail(f"Unsettled {identity}: {self.runtime.status()}")

    def start(self):
        response = self.runtime.command(dict(schema="mission/7", kind="start", request_id="start",
            admission=self.a.to_dict()))
        self.assertEqual(response["status"], "accepted", response)
        return self.settled("start")

    def request(self, identity="launch", **changes):
        data = dict(schema="mission/7", kind="lifecycle", request_id=identity,
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], operation="launch",
            world=self.a.scenario.world, character=self.a.scenario.character,
            sources=[], expected_session=None, expected_revision=None, expected_boundary_id=None,
            work_id=None, phase_id=None, identity_claim_ids=[],
            limits=dict(primitives=1, wall_seconds=60, game_seconds=1))
        data.update(changes)
        return data

    def launch(self, **changes):
        data = self.request(**changes)
        response = self.runtime.command(data)
        self.assertEqual(response["status"], "accepted", response)
        return self.settled(data["request_id"])

    def assert_read_only(self):
        self.assertFalse(any(r["kind"] in ("resume", "action", "key") for r in self.bridge.requests))
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 0)
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertEqual(self.runtime._bindings, {})
        self.assertIsNone(self.runtime._map)

    def test_registered_launch_verifies_only_owned_process_and_paused_menu(self):
        self.start()
        operation = self.launch()
        self.assertEqual(operation["state"], "completed", operation)
        self.assertTrue(operation["result"]["native_ready"])
        self.assertTrue(operation["result"]["launch_attempted"])
        self.assertFalse(operation["result"]["identity_verified"])
        self.assertFalse(operation["result"]["grants_authority"])
        self.assertEqual(operation["result"]["process"]["launch_id"], "owned-launch")
        self.assertEqual(len(operation["result"]["source_ids"]), 1)
        self.factory.assert_called_once_with(self.controller.root, self.a.configuration.native_sha256,
                                             clock=self.runtime._clock)
        self.assert_read_only()
        with patch.object(self.process, "status", side_effect=AssertionError("cached status polled process")):
            status = self.runtime.status()
        self.assertTrue(status["native_process"]["last_sample"]["running"])
        self.assertEqual(status["native_process"]["owner_mission_id"], self.a.mission_id)
        self.assertFalse(status["native_process"]["restored_from_disk"])
        self.assertEqual(self.runtime.command(operation["request"])["operation"]["state"], "completed")
        second = self.launch(identity="second-launch")
        self.assertEqual(second["state"], "blocked")
        self.process.launch.assert_called_once()

    def test_launch_cannot_use_a_source_claim_or_work_to_adopt_a_running_game(self):
        self.start()
        for index, changes in enumerate((dict(sources=["unowned-source"]),
                dict(identity_claim_ids=["claim"]), dict(work_id="work"))):
            operation = self.launch(identity=f"invalid-{index}", **changes)
            self.assertEqual(operation["state"], "blocked", operation)
            self.assertIn("source-free root", operation["result"]["reason"])
        rejected = self.runtime.command(self.request(identity="borrowed-native", expected_session="other"))
        self.assertEqual(rejected["status"], "rejected", rejected)
        self.assertIn("Launch cannot borrow", rejected["reason"])
        self.factory.assert_not_called()
        self.assert_read_only()

    def test_native_unsettled_inbox_prevents_even_process_construction(self):
        self.start()
        path = self.controller.bridge / "control-claimed.json"
        path.write_text("{}")
        try:
            operation = self.launch()
            self.assertEqual(operation["state"], "blocked", operation)
            self.assertIn("empty native inboxes", operation["result"]["reason"])
            self.factory.assert_not_called()
        finally:
            path.unlink(missing_ok=True)
        self.assert_read_only()

    def test_unrelated_normal_scene_is_not_retained_as_identity_or_time(self):
        self.start()
        def normal_after_launch(**arguments):
            facts = self.fake_launch(**arguments)
            from tests.test_controller import state
            self.bridge.value.update(state(in_game=True, paused=True))
            return facts
        self.process.launch.side_effect = normal_after_launch
        operation = self.launch()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertFalse(operation["result"]["native_ready"])
        self.assertEqual(operation["result"]["source_ids"], [])
        self.assertTrue(operation["result"]["process"]["running"])
        self.assertFalse(any(r.boundary_kind == "normal_play" for r in self.runtime._store.historical_references))
        self.assert_read_only()

    def test_error_bearing_ready_menu_cannot_be_claimed_as_native_readiness(self):
        self.start()
        def error_after_spawn(**arguments):
            facts = self.fake_launch(**arguments)
            self.bridge.value["error"] = "native readiness error"
            return facts
        self.process.launch.side_effect = error_after_spawn
        operation = self.launch()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertFalse(operation["result"]["native_ready"])
        self.assertEqual(operation["result"]["source_ids"], [])
        self.assert_read_only()

    def test_stale_native_timestamp_cannot_be_claimed_as_fresh_readiness(self):
        self.start()
        def stale_after_spawn(**arguments):
            facts = self.fake_launch(**arguments)
            self.bridge.behavior = lambda bridge, request: bridge.value.update(timestamp_ms=1) or True
            return facts
        self.process.launch.side_effect = stale_after_spawn
        operation = self.launch()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertFalse(operation["result"]["native_ready"])
        self.assertEqual(operation["result"]["source_ids"], [])
        self.assert_read_only()

    def test_human_takeover_after_spawn_prevents_readiness(self):
        self.start()
        def takeover(**arguments):
            facts = self.fake_launch(**arguments)
            self.bridge.value.update(pause_origin="human", takeover_generation=1)
            return facts
        self.process.launch.side_effect = takeover
        operation = self.launch()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("untouched MAIN_MENU", operation["result"]["reason"])
        self.assertTrue(operation["result"]["process"]["running"])
        self.assert_read_only()

    def test_pause_during_launch_keeps_custody_without_menu_adoption_or_input(self):
        self.start()
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        def spawn_and_wait(**arguments):
            facts = self.fake_launch(**arguments)
            entered.set()
            self.assertTrue(release.wait(2))
            self.assertTrue(arguments["cancelled"]())
            facts.update(outcome="cancelled", error="Operation cancelled")
            return facts
        self.process.launch.side_effect = spawn_and_wait
        self.assertEqual(self.runtime.command(self.request())["status"], "accepted")
        self.assertTrue(entered.wait(1))
        started = time.monotonic()
        self.runtime.pause("User Pause during spawn")
        self.assertLess(time.monotonic() - started, 0.5)
        release.set()
        operation = self.settled("launch")
        self.assertEqual(operation["state"], "paused", operation)
        self.assertTrue(operation["result"]["launch_attempted"])
        self.assertTrue(operation["result"]["process"]["running"])
        self.assertFalse(operation["result"]["native_ready"])
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assert_read_only()

    def test_deadline_after_spawn_reports_owned_child_without_automatic_relaunch(self):
        self.start()
        def expired(**arguments):
            facts = self.fake_launch(**arguments)
            facts.update(outcome="deadline", error="Original deadline expired")
            return facts
        self.process.launch.side_effect = expired
        operation = self.launch()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertTrue(operation["result"]["process"]["running"])
        self.assertFalse(operation["result"]["native_ready"])
        self.assertEqual(self.launch(identity="retry")["state"], "blocked")
        self.process.launch.assert_called_once()
        self.assert_read_only()

    def test_launch_preparation_failure_is_explicit_and_has_no_ready_source(self):
        self.start()
        self.process.launch.side_effect = OSError("preparation unavailable")
        operation = self.launch()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertTrue(operation["result"]["launch_attempted"])
        self.assertFalse(operation["result"]["process"]["running"])
        self.assertEqual(operation["result"]["source_ids"], [])
        self.assertIn("preparation unavailable", operation["result"]["reason"])
        self.assert_read_only()

    def test_owned_launch_cannot_be_rebound_to_a_different_admission_or_binary(self):
        self.start()
        self.launch()
        other = replace(self.a, mission_id="other-mission", configuration=replace(self.a.configuration,
            native_sha256="c" * 64))
        response = self.runtime.command(dict(schema="mission/7", kind="start", request_id="other-start",
                                             admission=other.to_dict()))
        self.assertEqual(response["status"], "rejected", response)
        self.assertIn("settle owned process custody", response["reason"])
        self.assertEqual(self.runtime.status()["mission_id"], self.a.mission_id)
        self.assertEqual(self.runtime.status()["configuration"]["native_sha256"], self.a.configuration.native_sha256)
        self.factory.assert_called_once()
        self.assert_read_only()

    def test_unsettled_launch_request_on_reopen_is_not_an_instruction_to_spawn(self):
        self.start()
        self.runtime._ledger.begin_request(self.request(), now=time.time())
        self.runtime.close()
        self.assertFalse(self.runtime._thread.is_alive())
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["native_process"]["unresolved_custody_requests"], ["launch"])
        operation = self.launch(identity="after-unsettled")
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("custody is unavailable", operation["result"]["reason"])
        self.factory.assert_not_called()
        self.assert_read_only()

    def test_reopen_reports_lost_custody_and_never_restores_or_replays_a_handle(self):
        self.start()
        self.launch()
        records = self.runtime._ledger.request_records()
        self.assertEqual([r["request"]["request_id"] for r in records], ["start", "launch"])
        records[-1]["result"]["process"]["running"] = False
        self.assertTrue(self.runtime._ledger.request("launch")["result"]["process"]["running"])
        self.runtime.close()
        self.assertFalse(self.runtime._thread.is_alive())
        self.assertTrue(any(event["request"]["kind"] == "mission_process_shutdown_custody"
                            for event in self.controller.status()["events"]))
        self.runtime = MissionRuntime(self.controller)
        self.start()
        status = self.runtime.status()
        self.assertEqual(status["native_process"]["unresolved_custody_requests"], ["launch"])
        self.assertIsNone(status["native_process"]["last_sample"])
        operation = self.launch(identity="new-launch")
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("custody is unavailable", operation["result"]["reason"])
        self.factory.assert_called_once()
        self.process.launch.assert_called_once()
        self.assert_read_only()
