"""Ordinary owned setup controls over real accounting and synthetic visible UI.

The fixture game assigns keys independently of semantic menu labels. These are
source regression checks, not native keyboard or cross-game qualification.
"""
from dataclasses import replace
import unittest
from unittest.mock import patch

from harness.gameplay.lifecycle import adopted_timeline
from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture


class OrdinaryLifecycleTests(MissionCreationFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.a = replace(self.a, allowed_skills=(*self.a.allowed_skills, "direct"))

    def raw(self, identity, key, *, parent="create"):
        data = super().control(identity, "ignored", parent=parent)
        data.update(skill_kind="direct", perception=None, goal=dict(
            input=dict(type="key", key=key, modifiers=[]),
            intent="Use the visible keyboard interface", expected="Inspect the actual response",
            interrupt_allowed=False))
        return data

    def control(self, identity, label, **kwargs):
        if getattr(self, "raw_confirmations", False) and kwargs.get("question") and kwargs.get("parent") != "exit":
            return self.raw(identity, "y" if label == "Yes" else "n", parent=kwargs.get("parent", "create"))
        return super().control(identity, label, **kwargs)

    def behavior(self, bridge, request):
        if request["kind"] == "direct":
            physical = request["input"]
            key = physical.get("key") if physical["type"] == "key" else physical.get("text")
            if key == "ESC" and bridge.value["category"].startswith("UNFAMILIAR_"):
                self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
                return True
            action = {"y": "YES", "n": "NO", "ENTER": "CONFIRM", "ESC": "QUIT"}.get(key)
            return super().behavior(bridge, {**request, "action": action})
        return super().behavior(bridge, request)

    def test_raw_creation_intermediate_save_cancel_reload_and_history(self):
        self.raw_confirmations, self.spare_points = True, True
        self.create()
        self.assertIsNotNone(adopted_timeline(self.runtime._ledger, self.runtime._store))
        self.assertEqual(self.run_request(self.lifecycle("declined-save", "save"))["state"], "partial")
        cancelled = self.run_request(self.raw("decline", "n", parent="declined-save"))
        self.assertEqual(cancelled["state"], "partial", cancelled)
        self.assertNotIn("saved_checkpoint", cancelled["result"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNotNone(adopted_timeline(self.runtime._ledger, self.runtime._store))
        self.save()
        self.exit()
        self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
        self.stage = "load-world"
        self.assertEqual(self.run_request(self.lifecycle("load", "load"))["state"], "partial")
        world = self.runtime._current
        self.run_request(super().control("load-world", self.a.scenario.world, parent="load"))
        entered = self.run_request(self.raw("load-character", "ENTER", parent="load"))
        self.assertEqual(entered["state"], "unknown", entered)
        self.observe("load-observe")
        self.finish_identity("load", world, 1)
        self.runtime._ledger._verify(self.a)
        self.assertIsNotNone(adopted_timeline(self.runtime._ledger, self.runtime._store))
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.controller._mission_lease)

    def test_unfamiliar_changed_receivers_cancel_without_stage_or_label_mapping(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        original = self.behavior
        count = 0

        def changing_game(bridge, request):
            nonlocal count
            if request["kind"] == "direct" and request["input"].get("key") == "?":
                count += 1
                self.menu(f"UNFAMILIAR_{count}", [])
                return True
            return original(bridge, request)

        self.bridge.behavior = changing_game
        for index in range(3):
            entered = self.run_request(self.raw(f"explore-{index}", "?"))
            self.assertEqual(entered["state"], "partial", entered)
            self.assertIsNone(self.runtime._registered_lifecycle.candidate)
            cancelled = self.run_request(self.raw(f"cancel-{index}", "ESC"))
            self.assertEqual(cancelled["state"], "partial", cancelled)
            self.assertEqual(self.current()[1]["category"], "MAIN_MENU")
        spent = self.runtime.status()["spent_inputs"]
        aborted = self.run_request(self.lifecycle("abort", "exit"))
        self.assertEqual(aborted["state"], "partial", aborted)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.bridge.value["pause_origin"] = "host"
        self.observe("abort-observe")
        exited = self.exit(root="exit")
        self.assertTrue(exited["result"]["normal_exit"]["no_save_required"])
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")

    def test_cancelled_character_commit_cannot_authorize_later_raw_load(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.stage = "character"
        self.run_request(super().control("character-menu", "Custom Character"))
        self.run_request(self.lifecycle("commit", parent="create"))
        original = self.behavior

        def altered_game(bridge, request):
            if request["kind"] == "direct" and request["input"].get("key") == "ESC":
                self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
                return True
            if request["kind"] == "direct" and request["input"].get("key") == "ENTER":
                self.normal("loaded-existing", paused=True)
                return False
            return original(bridge, request)

        self.bridge.behavior = altered_game
        cancelled = self.run_request(self.raw("cancel-commit", "ESC"))
        self.assertEqual(cancelled["state"], "partial", cancelled)
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "awaiting_control")
        loaded = self.run_request(self.raw("load-existing", "ENTER"))
        self.assertEqual(loaded["state"], "unknown", loaded)
        self.assertTrue(self.runtime._registered_lifecycle.candidate.diagnostic_only)
        self.observe("diagnose-existing")
        refused = self.run_request(self.lifecycle("cannot-adopt", parent="create"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertNotIn("lifecycle_transition", refused["result"])

    def test_click_resize_refuses_without_spending_or_discarding_setup(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        data = self.raw("click", "ignored")
        data["goal"]["input"] = dict(type="click", button="left", x=0, y=0,
            geometry=self.current()[1]["frame_geometry"])
        original = self.runtime._observe_native

        def resize(*args, **kwargs):
            self.bridge.value["revision"] += 1
            self.bridge.value["frame_geometry"]["window_width"] += 1
            return original(*args, **kwargs)

        spent = self.runtime.status()["spent_inputs"]
        with patch.object(self.runtime, "_observe_native", side_effect=resize):
            refused = self.run_request(data)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("mapping changed", refused["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertIsNotNone(self.runtime._registered_lifecycle.phase)
        self.observe("after-resize")

    def test_direct_child_cannot_extend_original_root_input_allowance(self):
        self.ready()
        root = self.lifecycle("create")
        root["limits"]["primitives"] = 1
        self.run_request(root)
        spent = self.runtime.status()["spent_inputs"]
        refused = self.run_request(self.raw("exhausted", "ESC"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertFalse(any(row["kind"] == "direct" for row in self.bridge.delivered))

    def test_ordinary_actual_preflight_cannot_cross_into_unadopted_normal_play(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        original = self.controller.execute_mission

        def receiver_changed(*args, **kwargs):
            self.bridge.value["revision"] += 1
            self.normal(self.current()[0].session)
            return original(*args, **kwargs)

        spent = self.runtime.status()["spent_inputs"]
        with patch.object(self.controller, "execute_mission", side_effect=receiver_changed):
            result = self.run_request(self.raw("changed-to-normal", "ENTER"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertFalse(any(row["kind"] == "direct" for row in self.bridge.delivered))

    def test_pause_during_ordinary_refresh_sends_no_input(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        original = self.runtime._observe_native

        def paused(*args, **kwargs):
            value = original(*args, **kwargs)
            self.runtime.pause("Operator Pause during ordinary lifecycle refresh")
            return value

        with patch.object(self.runtime, "_observe_native", side_effect=paused):
            result = self.run_request(self.raw("paused", "ESC"))
        self.assertEqual(result["state"], "paused", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertFalse(any(row["kind"] == "direct" for row in self.bridge.delivered))

    def test_observed_receiver_change_retires_committed_character_stage(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.stage = "character"
        self.run_request(super().control("character-menu", "Custom Character"))
        self.run_request(self.lifecycle("commit", parent="create"))
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "character_confirmation")
        self.bridge.value["revision"] += 1
        self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
        self.observe("changed-receiver")
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "awaiting_control")
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)

    def test_text_confirmation_prefix_keeps_one_entry_and_exact_terminal_proof(self):
        self.ready()
        self.spare_points = True
        self.run_request(self.lifecycle("create"))
        self.run_request(super().control("world-form", "Create World"))
        world = self.runtime._current
        self.run_request(self.lifecycle("world-finalize", parent="create"))
        self.run_request(super().control("world-yes", "Yes", question="Are you SURE you're finished?"))
        self.run_request(super().control("character-menu", "Custom Character"))
        self.run_request(self.lifecycle("commit", parent="create"))
        original = self.behavior

        def visible_questions(bridge, request):
            result = original(bridge, request)
            if request["kind"] == "direct":
                self.bridge.editor_text = self.stage
            return result

        self.bridge.behavior = visible_questions
        data = self.raw("typed-confirmations", "ignored")
        data["goal"]["input"] = dict(type="text", text="yy")
        entered = self.run_request(data)
        self.assertEqual(entered["state"], "unknown", entered)
        primitives = [p for p in self.runtime._ledger.primitive_records() if p["request_id"] == data["request_id"]]
        self.assertEqual([p["state"] for p in primitives], ["returned", "unknown"])
        self.assertIsNotNone(primitives[0]["intent"]["input_observation"])
        self.assertIsNone(primitives[1]["intent"]["input_observation"])
        self.observe("creation-observe")
        self.finish_identity("create", world)
        self.runtime._ledger._verify(self.a)
        self.assertIsNotNone(adopted_timeline(self.runtime._ledger, self.runtime._store))


if __name__ == "__main__":
    unittest.main()
