"""Ordinary owned setup controls over real accounting and synthetic visible UI.

The fixture game assigns keys independently of semantic menu labels. These are
source regression checks, not native keyboard or cross-game qualification.
"""
from dataclasses import replace
from pathlib import Path
import time
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

    def assert_stale_request_refusal(self, kind):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(super().control("world-form", "Create World"))
        if kind == "direct":
            stale = self.raw("stale", "ENTER")
        elif kind == "lifecycle":
            stale = self.lifecycle("stale", parent="create")
        else:
            stale = super().control("stale", "Edit Name")
            if kind == "edit":
                stale.update(skill_kind="edit",
                    perception=dict(kind="editor", source_id=self.runtime._current.observation_id,
                        basis="player_interpretation", purpose="world_name", label="World name",
                        visible_text="Old", whole_value=True, focused=True),
                    goal=dict(purpose="world_name", text=self.a.scenario.world, commit=True))
        # Reproduce004's delivered text prefix, independently of the later
        # request's intended key. An unchanged receiver stops the text batch
        # after its first scalar and returns a new informing checkpoint.
        text = self.raw("text-prefix", "ignored")
        text["goal"]["input"] = dict(type="text", text=self.a.scenario.world)
        returned = self.run_request(text)
        self.assertEqual(returned["state"], "partial", returned)
        self.assertEqual(len([p for p in self.runtime._ledger.primitive_records()
            if p["request_id"] == text["request_id"]]), 1)
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        state = self.runtime.status()
        refused = self.run_request(stale)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("No input was sent", refused["result"]["reason"])
        self.assertEqual(refused["result"]["source_ids"], [phase.checkpoint.observation_id])
        self.assertEqual(refused["result"]["proposals"], 0)
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["epoch"], state["epoch"])
        self.assertEqual(self.runtime.status()["deadline"], state["deadline"])
        self.assertEqual(self.runtime.status()["spent_inputs"], state["spent_inputs"])
        corrected = self.run_request(self.raw("fresh-focus", "ENTER"))
        self.assertEqual(corrected["state"], "partial", corrected)
        self.assertEqual(self.current()[1]["category"], "STRING_INPUT")
        self.runtime._ledger._verify(self.a)

    def test_stale_direct_request_preserves_healthy_lifecycle(self):
        self.assert_stale_request_refusal("direct")

    def test_stale_menu_request_preserves_healthy_lifecycle(self):
        self.assert_stale_request_refusal("menu")

    def test_stale_editor_request_preserves_healthy_lifecycle(self):
        self.assert_stale_request_refusal("edit")

    def test_stale_stage_commit_preserves_healthy_lifecycle(self):
        self.assert_stale_request_refusal("lifecycle")

    def test_known_native_rejection_keeps_setup_observable_without_transition_candidate(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        original = self.behavior

        def reject_input(bridge, request):
            if request["kind"] == "direct" and request["input"].get("key") == "?":
                # The shared bridge fixture normally increments and delivers
                # before its callback; this case represents native refusal
                # before commit, with no game effect or revision advancement.
                bridge.delivered.pop()
                bridge.value["revision"] -= 1
                bridge.value.update(status="rejected", error="Unsupported physical event")
                return True
            bridge.value.update(status="ready", error="")
            if request["kind"] == "direct" and request["input"].get("key") == "n" and self.stage == "exit":
                self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
                return True
            return original(bridge, request)

        self.bridge.behavior = reject_input
        lease = self.runtime._lease
        refused = self.run_request(self.raw("native-rejection", "?"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("phase", refused["result"])
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        self.assertIsNotNone(self.runtime._registered_lifecycle.phase)
        self.assertIs(self.runtime._lease, lease)
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "rejected")
        self.assertTrue(primitive["result"]["published"])
        self.assertIsNone(primitive["result"]["source_after"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(len(self.bridge.delivered), 1)  # Original Resume only.
        self.observe("after-rejection")
        continued = self.run_request(self.raw("new-decision", "ESC"))
        self.assertEqual(continued["state"], "partial", continued)
        self.run_request(self.raw("cancel-quit", "n"))
        self.assertEqual(self.current()[1]["category"], "MAIN_MENU")
        self.run_request(self.lifecycle("abort", "exit"))
        self.bridge.value["pause_origin"] = "host"
        self.observe("abort-observe")
        exited = self.exit(root="exit")
        self.assertTrue(exited["result"]["normal_exit"]["no_save_required"])
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")
        self.runtime._ledger._verify(self.a)

    def assert_rejected_stage_can_be_explicitly_reselected(self, *, character):
        self.ready()
        self.run_request(self.lifecycle("create"))
        if character:
            self.stage = "character"
        self.run_request(super().control("form", "Custom Character" if character else "Create World"))
        action = "NEXT_TAB" if character else "FINALIZE"
        original = self.behavior

        def reject_stage(bridge, request):
            if request.get("action") == action:
                bridge.delivered.pop()
                bridge.value["revision"] -= 1
                bridge.value.update(status="rejected", error="Stage input refused before commit")
                return True
            bridge.value.update(status="ready", error="")
            return original(bridge, request)

        self.bridge.behavior = reject_stage
        before = self.runtime.status()
        lease = self.runtime._lease
        refused = self.run_request(self.lifecycle("rejected-stage", parent="create"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "awaiting_control")
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"] + 1)
        self.assertEqual(self.runtime.status()["deadline"], before["deadline"])
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
        self.observe("after-stage-rejection")
        self.bridge.behavior = original
        self.bridge.value.update(status="ready", error="")
        selected = self.run_request(self.lifecycle("new-stage-decision", parent="create"))
        self.assertEqual(selected["state"], "partial", selected)
        self.assertEqual(self.current()[1]["category"], "YESNO")
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage,
            "character_confirmation" if character else "world_confirmation")
        self.assertEqual(self.runtime._ledger.primitive_records()[-2]["state"], "rejected")
        self.runtime._ledger._verify(self.a)

    def test_rejected_world_stage_can_be_explicitly_reselected(self):
        self.assert_rejected_stage_can_be_explicitly_reselected(character=False)

    def test_rejected_character_stage_can_be_explicitly_reselected(self):
        self.assert_rejected_stage_can_be_explicitly_reselected(character=True)

    def expired_setup(self):
        self.ready()
        data = self.lifecycle("create")
        data["limits"]["wall_seconds"] = 1
        self.assertEqual(self.run_request(data)["state"], "partial")
        deadline = self.runtime._ledger.request("create")["deadline"]
        time.sleep(max(0, deadline - time.time()) + 0.02)
        return deadline

    def test_expired_setup_observe_and_separate_normal_cleanup_do_not_renew_inputs(self):
        deadline = self.expired_setup()
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        spent = self.runtime.status()["spent_inputs"]
        refused = self.runtime.command(self.raw("expired-child", "ESC"))
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertIn("Original phase deadline expired", refused["reason"])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.observe("expired-observe")
        self.assertEqual(self.runtime.status()["lifecycle_phase"]["remaining_limits"]["wall_seconds"], 0)
        self.assertEqual(self.runtime.status()["lifecycle_phase"]["remaining_limits"]["primitives"], 31)
        self.assertEqual(self.runtime._registered_lifecycle.phase.root_id, "create")
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], deadline)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        refused = self.runtime.command(self.raw("still-expired", "ESC"))
        self.assertEqual(refused["status"], "rejected", refused)
        aborted = self.run_request(self.lifecycle("abort", "exit"))
        self.assertTrue(aborted["result"]["cleanup_requested"])
        self.bridge.value["pause_origin"] = "host"
        self.observe("cleanup-observe")
        exited = self.exit(root="normal-exit")
        self.assertTrue(exited["result"]["normal_exit"]["no_save_required"])
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")
        self.runtime._ledger._verify(self.a)

    def test_expired_setup_observe_cannot_hide_controller_failure(self):
        self.expired_setup()
        spent = self.runtime.status()["spent_inputs"]
        self.controller._mission_processing_failure(None, OSError("Synthetic controller failure"))
        data = dict(schema="mission/10", kind="observe", request_id="observe-fault",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"])
        refused = self.run_request(data)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)

    def test_stale_request_cannot_hide_corrupted_current_evidence(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        stale = self.raw("stale", "ENTER")
        self.run_request(self.raw("changed-source", "ESC"))
        retained = Path(self.runtime._current.frame_path)
        retained.chmod(0o600)
        retained.write_bytes(b"corrupted archive")
        spent = self.runtime.status()["spent_inputs"]
        refused = self.run_request(stale)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertNotIn("No input was sent", refused["result"]["reason"])

    def test_stale_request_cannot_hide_controller_custody_loss(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        stale = self.raw("stale", "ENTER")
        self.run_request(self.raw("changed-source", "ESC"))
        spent = self.runtime.status()["spent_inputs"]
        self.controller._mission_processing_failure(None, OSError("Synthetic controller storage failure"))
        self.assertTrue(self.controller.frozen)
        self.assertIsNone(self.controller._mission_lease)
        refused = self.run_request(stale)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertNotIn("No input was sent", refused["result"]["reason"])

    def test_stale_reconciliation_preserves_unknown_until_fresh_explicit_request(self):
        with patch.object(self, "finish_identity", return_value=None):
            self.create()
        candidate = self.runtime._registered_lifecycle.candidate
        stale = self.lifecycle("stale-reconcile", parent="create")
        stale["expected_revision"] -= 1
        before = self.runtime.status()
        refused = self.run_request(stale)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIs(self.runtime._registered_lifecycle.candidate, candidate)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        for key in ("spent_inputs", "epoch", "deadline", "unreconciled"):
            self.assertEqual(self.runtime.status()[key], before[key])
        fresh = self.run_request(self.lifecycle("fresh-reconcile", parent="create"))
        self.assertEqual(fresh["state"], "completed", fresh)
        self.assertIn("lifecycle_transition", fresh["result"])

    def test_stale_readmission_preserves_paused_identity_until_fresh_explicit_request(self):
        with patch.object(self, "finish_identity", side_effect=lambda *_:
                self.run_request(self.lifecycle("create-reconcile", parent="create"))):
            self.create()
        phase = self.runtime._registered_lifecycle.phase
        stale = self.lifecycle("stale-readmit", parent="create")
        stale["expected_revision"] -= 1
        before = self.runtime.status()
        refused = self.run_request(stale)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIsNone(self.runtime._lease)
        for key in ("spent_inputs", "epoch", "deadline", "unreconciled", "phase"):
            self.assertEqual(self.runtime.status()[key], before[key])
        fresh = self.run_request(self.lifecycle("fresh-readmit", parent="create"))
        self.assertEqual(fresh["state"], "completed", fresh)
        self.assertIsNotNone(self.runtime._lease)

    def test_stale_readmission_cannot_hide_native_takeover(self):
        # Stop the fixture's successful creation at its real committed,
        # paused transition, before identity readmission/adoption.
        with patch.object(self, "finish_identity", side_effect=lambda *_:
                self.run_request(self.lifecycle("create-reconcile", parent="create"))):
            self.create()
        stale = self.lifecycle("stale-readmit", parent="create")
        stale["expected_revision"] -= 1
        observed = dict(self.current()[1])
        observed.update(revision=observed["revision"] + 1,
            takeover_generation=observed["takeover_generation"] + 1, pause_origin="human")
        self.controller._accept(observed)
        spent = self.runtime.status()["spent_inputs"]
        refused = self.run_request(stale)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertNotIn("No input was sent", refused["result"]["reason"])


if __name__ == "__main__":
    unittest.main()
