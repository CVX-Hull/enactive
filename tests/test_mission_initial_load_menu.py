"""Initial Load menu recovery through the real writer and stores; synthetic UI."""
from dataclasses import replace
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import PropertyMock, patch

from harness.gameplay.contracts import ContractError
from harness.gameplay.lifecycle import adopted_timeline, initial_load_menu_sources
from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture


class InitialLoadMenuTests(MissionCreationFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.a = replace(self.a, scenario=replace(self.a.scenario, mode="load"),
                         allowed_skills=(*self.a.allowed_skills, "direct"))
        self.remaining_menus = 2
        self.load_menu_enabled = True
        self.menu_category = "INVENTORY"

    def loaded_menu(self):
        actions = {"INVENTORY": ["QUIT", "CONFIRM"], "UILIST": ["UILIST.QUIT", "CONFIRM"],
                   "POPUP_WAIT": ["ANY_INPUT", "COORDINATE"]}[self.menu_category]
        self.menu(self.menu_category, actions, in_game=True)

    def behavior(self, bridge, request):
        if (bridge.value["category"] == "UILIST" and request.get("action") == "CONFIRM"
                and self.stage == "load" and self.load_menu_enabled):
            bridge.value.update(session=f"normal-{self.launch_count}", paused=True, pause_origin="world_change")
            self.stage = "loaded-menu"
            self.loaded_menu()
            return False
        dismissal = {"INVENTORY": request.get("action") == "QUIT",
                     "UILIST": request.get("action") == "UILIST.QUIT",
                     "POPUP_WAIT": request.get("kind") == "key" and request.get("key") == "SPACE"}[self.menu_category]
        if self.stage == "loaded-menu" and dismissal:
            self.remaining_menus -= 1
            if self.remaining_menus:
                self.loaded_menu()
            else:
                self.stage = "normal"
                self.normal(f"normal-{self.launch_count}")
            return True
        return super().behavior(bridge, request)

    def pending_menu(self, *, root_primitives=32, reconcile=True):
        self.ready()
        self.stage = "load-world"
        root = self.lifecycle("initial-load", "load")
        root["limits"]["primitives"] = root_primitives
        self.assertEqual(self.run_request(root)["state"], "partial")
        world = self.runtime._current
        self.assertEqual(self.run_request(self.control("world", f"{self.a.scenario.world} (1)", parent="initial-load"))["state"], "partial")
        selection = self.control("character", self.a.scenario.character, parent="initial-load")
        selection["perception"] = None
        self.assertEqual(self.run_request(selection)["state"], "unknown")
        self.original = self.runtime._ledger.primitive_records()[-1]
        self.original_root = self.runtime._ledger.request("initial-load")
        self.original_deadline = self.runtime._mission_deadline
        delivered = len(self.bridge.delivered)
        self.observe("loaded-observe")
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertIsNone(self.runtime._lease)
        if not reconcile:
            return world
        reconciled = self.run_request(self.lifecycle("reconciled", "load", parent="initial-load"))
        self.assertEqual(reconciled["state"], "completed", reconciled)
        self.assertEqual(reconciled["result"]["phase"]["stage"], "awaiting_control")
        self.assertIn("separate same-root lifecycle Load call", reconciled["result"]["reason"])
        self.assertNotIn("provisional_scope", reconciled["result"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase.first_normal)
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertIsNone(adopted_timeline(self.runtime._ledger, self.runtime._store))
        return world

    def readmit_menu(self):
        operation = self.run_request(self.lifecycle("readmitted", "load", parent="initial-load"))
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_control")
        self.assertNotIn("provisional_scope", operation["result"])
        self.assertIsNone(adopted_timeline(self.runtime._ledger, self.runtime._store))

    def test_premature_child_before_reconciliation_names_original_lifecycle_root(self):
        self.pending_menu(reconcile=False)
        candidate = self.runtime._registered_lifecycle.candidate
        primitives = deepcopy(self.runtime._ledger.primitive_records())
        response = self.runtime.command(self.control("premature-menu", "Cancel", parent="initial-load"))
        self.assertEqual(response["status"], "rejected", response)
        self.assertIn("same-root reconciliation", response["reason"])
        self.assertNotIn("observe and choose a new root", response["reason"])
        self.assertIs(self.runtime._registered_lifecycle.candidate, candidate)
        self.assertEqual(self.runtime._ledger.primitive_records(), primitives)
        self.assertEqual(self.run_request(self.lifecycle("reconciled", "load", parent="initial-load"))["state"], "completed")

    def test_producer_refuses_premature_identity_then_explicit_sequence_adopts(self):
        from tests.test_mission_request_producer_integration import compose
        world = self.pending_menu()
        phase = self.runtime._registered_lifecycle.phase
        requests = deepcopy(self.runtime._ledger.request_records())
        primitives = deepcopy(self.runtime._ledger.primitive_records())
        deadline = self.runtime._mission_deadline
        delivered = len(self.bridge.delivered)
        inspect = self.control("premature-inspect", "Character", kind="inspect", parent="initial-load")
        with self.assertRaisesRegex(ContractError, "separate readmission"):
            compose(self, inspect, "lifecycle")
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime._ledger.request_records(), requests)
        self.assertEqual(self.runtime._ledger.primitive_records(), primitives)
        self.assertEqual(self.runtime._mission_deadline, deadline)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.readmit_menu()
        self.dismiss_menu("first-menu")
        self.dismiss_menu("second-menu")
        self.adopt(world)

    def dismiss_menu(self, identity):
        operation = self.run_request(self.control(identity, "Cancel", parent="initial-load"))
        self.assertEqual(operation["state"], "partial", operation)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        return operation

    def adopt(self, world):
        inspection = self.run_request(self.control("identity", "Character", kind="inspect", parent="initial-load"))
        self.assertEqual(inspection["state"], "completed", inspection)
        screen = self.runtime._current
        world_id = self.remember_identity("world-identity", "world", world, 0)
        character_id = self.remember_identity("character-identity", "character", screen, 0)
        self.assertEqual(self.run_request(self.control("identity-return", "Cancel", parent="initial-load"))["state"], "partial")
        adopted = self.run_request(self.lifecycle("adopted", "load", parent="initial-load", claims=[world_id, character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)
        return adopted

    def raw(self, identity):
        data = self.control(identity, "ignored", parent="initial-load")
        data.update(skill_kind="direct", perception=None, goal=dict(
            input=dict(type="key", key="ESC", modifiers=[]), intent="Dismiss visible menu",
            expected="Inspect the actual response", interrupt_allowed=False))
        return data

    def reopened_pending(self):
        spent = self.runtime.status()["spent_inputs"]
        request = self.lifecycle("history-is-not-readmission", "load", parent="initial-load")
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.assertEqual(self.start()["state"], "completed")
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(adopted_timeline(self.runtime._ledger, self.runtime._store))
        delivered = len(self.bridge.delivered)
        request["epoch"] = self.runtime.status()["epoch"]
        refused = self.run_request(request)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(len(self.bridge.delivered), delivered)

    def test_reopen_after_reconciliation_restores_history_only(self):
        self.pending_menu()
        self.reopened_pending()

    def test_reopen_after_readmission_restores_history_only(self):
        self.pending_menu()
        self.readmit_menu()
        self.reopened_pending()

    def test_reopen_after_intermediate_returned_dismissal_restores_history_only(self):
        self.pending_menu()
        self.readmit_menu()
        self.dismiss_menu("dismiss-first")
        self.reopened_pending()

    def test_one_menu_and_healthy_wrong_requests_allow_new_explicit_dismissal(self):
        self.remaining_menus = 1
        world = self.pending_menu()
        self.readmit_menu()
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        spent, delivered = self.runtime.status()["spent_inputs"], len(self.bridge.delivered)
        captured = len(self.runtime._store.historical_references)
        requests = [self.raw("wrong-direct"), self.control("wrong-menu", "Select", parent="initial-load"),
            self.control("early-identity", "Character", kind="inspect", parent="initial-load"),
            self.lifecycle("early-adoption", "load", parent="initial-load", claims=["absent-world", "absent-character"])]
        for request in requests:
            with self.subTest(kind=request["request_id"]):
                refused = self.run_request(request)
                self.assertEqual(refused["state"], "blocked", refused)
                self.assertIn("No input was sent", refused["result"]["reason"])
                self.assertIs(self.runtime._registered_lifecycle.phase, phase)
                self.assertIs(self.runtime._lease, lease)
                self.assertEqual(self.runtime.status()["spent_inputs"], spent)
                self.assertEqual(len(self.bridge.delivered), delivered)
                self.assertEqual(len(self.runtime._store.historical_references), captured)
        self.dismiss_menu("correct-dismissal")
        self.adopt(world)

    def stopped_request(self, request):
        delivered = len(self.bridge.delivered)
        response = self.runtime.command(request)
        if response["status"] == "accepted":
            response = self.settled(request["request_id"])
            self.assertIn(response["state"], ("blocked", "paused"), response)
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertIsNone(self.runtime._lease)
        return response

    def test_menu_readmission_cannot_cross_user_pause(self):
        self.pending_menu()
        self.runtime.pause("Operator revokes provisional menu")
        self.stopped_request(self.lifecycle("after-user-pause", "load", parent="initial-load"))
        self.assertEqual(self.runtime.status()["pause_cause"], "user")

    def test_menu_readmission_cannot_cross_native_takeover(self):
        self.pending_menu()
        observed = self.current()[1]
        observed.update(revision=observed["revision"] + 1,
            takeover_generation=observed["takeover_generation"] + 1, pause_origin="human")
        self.controller._accept(observed)
        self.stopped_request(self.lifecycle("after-takeover", "load", parent="initial-load"))

    def test_menu_readmission_cannot_cross_actor_change(self):
        self.pending_menu()
        phase = self.runtime._registered_lifecycle.phase
        self.runtime._registered_lifecycle.phase = replace(phase, actor_id="foreign-player")
        self.stopped_request(self.lifecycle("after-actor-change", "load", parent="initial-load"))

    def test_menu_readmission_cannot_cross_epoch_change(self):
        self.pending_menu()
        phase = self.runtime._registered_lifecycle.phase
        self.runtime._registered_lifecycle.phase = replace(phase, epoch=phase.epoch + 1)
        self.stopped_request(self.lifecycle("after-epoch-change", "load", parent="initial-load"))

    def test_menu_readmission_cannot_hide_source_corruption(self):
        self.pending_menu()
        request = self.lifecycle("after-source-loss", "load", parent="initial-load")
        path = Path(self.runtime._current.frame_path)
        path.chmod(0o600)
        path.write_bytes(b"corrupt retained evidence")
        self.stopped_request(request)

    def test_menu_readmission_cannot_hide_storage_failure(self):
        self.pending_menu()
        self.controller._mission_processing_failure(None, OSError("Synthetic storage failure"))
        self.stopped_request(self.lifecycle("after-storage-failure", "load", parent="initial-load"))

    def test_menu_readmission_cannot_cross_closed_controller(self):
        self.pending_menu()
        request = self.lifecycle("after-controller-close", "load", parent="initial-load")
        with patch.object(self.controller, "closed", True):
            self.stopped_request(request)

    def test_menu_readmission_cannot_hide_failure_after_activation(self):
        self.pending_menu()
        lifecycle = self.runtime._registered_lifecycle
        resume = lifecycle._resume

        def fail_before_resume(work, phase):
            self.controller._mission_processing_failure(None, OSError("Synthetic late storage failure"))
            return resume(work, phase)

        with patch.object(lifecycle, "_resume", side_effect=fail_before_resume):
            self.stopped_request(self.lifecycle("late-storage-failure", "load", parent="initial-load"))
        self.assertTrue(self.controller.frozen)

    def test_normal_first_readmission_cannot_hide_storage_failure(self):
        self.load_menu_enabled = False
        self.pending_menu(reconcile=False)
        reconciled = self.run_request(self.lifecycle("reconciled", "load", parent="initial-load"))
        self.assertEqual(reconciled["state"], "completed", reconciled)
        self.assertIsNotNone(self.runtime._registered_lifecycle.phase.first_normal)
        self.controller._mission_processing_failure(None, OSError("Synthetic storage failure"))
        self.stopped_request(self.lifecycle("normal-after-storage-failure", "load", parent="initial-load"))

    def test_menu_readmission_preserves_original_root_expiry(self):
        self.pending_menu()
        deadline = self.runtime._ledger.request("initial-load")["deadline"]
        with patch.object(self.runtime, "_wall", return_value=deadline + 0.01):
            self.stopped_request(self.lifecycle("expired-root", "load", parent="initial-load"))
        self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)

    def test_menu_readmission_cannot_consume_global_cleanup_frame_reserve(self):
        self.pending_menu()
        usage = self.runtime._store.usage()
        bounded = replace(self.a, limits=replace(self.a.limits,
            frames=usage["frames"] + self.a.cleanup_reserve.frames))
        with patch.object(self.runtime, "_admission", bounded):
            self.stopped_request(self.lifecycle("reserved-frames", "load", parent="initial-load"))

    def test_original_root_input_limit_stops_dismissal_after_charged_resume(self):
        self.pending_menu(root_primitives=4)
        self.readmit_menu()
        self.stopped_request(self.control("exhausted-root", "Cancel", parent="initial-load"))
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)

    def test_unknown_dismissal_never_becomes_another_load_candidate(self):
        self.pending_menu()
        self.readmit_menu()
        original = self.bridge.behavior

        def missing_ack(bridge, request):
            returned = original(bridge, request)
            return False if request.get("action") == "QUIT" else returned

        self.bridge.behavior = missing_ack
        result = self.run_request(self.control("unknown-dismissal", "Cancel", parent="initial-load"))
        self.assertEqual(result["state"], "unknown", result)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.stopped_request(self.lifecycle("not-another-load", "load", parent="initial-load"))
        with self.assertRaises(ContractError):
            adopted_timeline(self.runtime._ledger, self.runtime._store)

    def completed_menu_load(self):
        world = self.pending_menu()
        self.readmit_menu()
        self.dismiss_menu("dismiss-first")
        self.dismiss_menu("dismiss-last")
        first = self.runtime._registered_lifecycle.phase.first_normal
        self.adopt(world)
        return first

    def test_category_specific_registered_dismissal_reaches_normal_and_adopts(self):
        self.menu_category = "UILIST"
        self.remaining_menus = 1
        world = self.pending_menu()
        self.readmit_menu()
        self.dismiss_menu("list-dismissal")
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual((primitive["intent"]["kind"], primitive["intent"]["value"]), ("action", "UILIST.QUIT"))
        self.adopt(world)
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 1)

    def test_no_choice_popup_registered_key_reaches_normal_and_adopts(self):
        self.menu_category = "POPUP_WAIT"
        self.remaining_menus = 1
        world = self.pending_menu()
        self.readmit_menu()
        self.dismiss_menu("popup-dismissal")
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual((primitive["intent"]["kind"], primitive["intent"]["value"]), ("key", "SPACE"))
        self.adopt(world)
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 1)

    def test_unknown_dismissal_history_reopens_without_reconstructing_authority(self):
        self.pending_menu()
        self.readmit_menu()
        original = self.bridge.behavior

        def missing_ack(bridge, request):
            returned = original(bridge, request)
            return False if request.get("action") == "QUIT" else returned

        self.bridge.behavior = missing_ack
        result = self.run_request(self.control("unknown-dismissal", "Cancel", parent="initial-load"))
        self.assertEqual(result["state"], "unknown", result)
        spent = self.runtime.status()["spent_inputs"]
        unresolved = self.runtime.status()["unreconciled"]
        self.assertEqual(unresolved, 1)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.assertEqual(self.start()["state"], "completed")
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(self.runtime.status()["unreconciled"], unresolved)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        self.assertIsNone(self.runtime._lease)
        with self.assertRaises(ContractError):
            adopted_timeline(self.runtime._ledger, self.runtime._store)

    def test_continuity_reload_menu_does_not_use_initial_load_exception(self):
        self.completed_menu_load()
        self.save()
        self.exit()
        self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
        self.stage = "load-world"
        self.assertEqual(self.run_request(self.lifecycle("reload", "load"))["state"], "partial")
        self.assertEqual(self.run_request(self.control("reload-world", f"{self.a.scenario.world} (1)",
            parent="reload"))["state"], "partial")
        selection = self.control("reload-character", self.a.scenario.character, parent="reload")
        selection["perception"] = None
        self.assertEqual(self.run_request(selection)["state"], "unknown")
        delivered = len(self.bridge.delivered)
        observed = self.run_request(dict(schema="mission/11", kind="observe", request_id="reload-menu-observe",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        self.assertEqual(observed["state"], "blocked", observed)
        self.assertIn("does not establish the exact outstanding lifecycle transition", observed["result"]["reason"])
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertIsNone(self.runtime._lease)

    def test_pure_history_rejects_missing_foreign_future_and_uncertain_dismissal_chain(self):
        self.completed_menu_load()
        ledger = self.runtime._ledger
        originals = ledger.primitive_records()
        for mutation in ("missing-resume", "missing-dismissal", "foreign-root", "future-source", "unknown",
                         "actor", "epoch", "takeover", "wrong-input"):
            changed = deepcopy(originals)
            dismissal = next(p for p in changed if p["request_id"] == "dismiss-last")
            if mutation == "missing-resume":
                changed = [p for p in changed if p["request_id"] != "readmitted"]
            elif mutation == "missing-dismissal":
                changed = [p for p in changed if p["request_id"] != "dismiss-first"]
            elif mutation == "foreign-root":
                dismissal["request_id"] = "world"
            elif mutation == "future-source":
                dismissal["intent"]["source_before"] = self.runtime._current.observation_id
                dismissal["result"]["source_before"] = self.runtime._current.observation_id
            elif mutation == "unknown":
                dismissal["state"] = "unknown"
            elif mutation == "wrong-input":
                dismissal["intent"]["value"] = "CONFIRM"
            else:
                field = {"actor": "actor_id", "epoch": "epoch", "takeover": "takeover_generation"}[mutation]
                dismissal["result"]["dispatch_binding"][field] = "foreign" if mutation == "actor" else 99
            with self.subTest(mutation=mutation), patch.object(ledger, "primitive_records", return_value=tuple(changed)):
                with self.assertRaises(ContractError):
                    adopted_timeline(ledger, self.runtime._store)

    def test_pure_history_rejects_prior_unadopted_normal_even_with_null_saved_checkpoint(self):
        first = self.completed_menu_load()
        store = self.runtime._store
        references = store.historical_references
        with patch.object(type(store), "historical_references", new_callable=PropertyMock,
                return_value=(first, *[r for r in references if r != first])):
            with self.assertRaises(ContractError):
                adopted_timeline(self.runtime._ledger, store)

    def test_later_normal_snapshot_cannot_replace_returned_menu_dismissal(self):
        self.pending_menu()
        self.readmit_menu()
        execute = self.controller.execute_mission

        def unproved_normal(*args, **kwargs):
            result = execute(*args, **kwargs)
            self.normal(f"normal-{self.launch_count}")
            self.bridge.value["timestamp_ms"] += 1
            self.bridge.publish(deepcopy(self.bridge.value))
            self.controller.status()
            return result

        with patch.object(self.controller, "execute_mission", side_effect=unproved_normal):
            result = self.run_request(self.control("menu-ack-normal-current", "Cancel", parent="initial-load"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")

    def test_known_normal_ack_can_have_a_later_normal_current_capture(self):
        self.remaining_menus = 1
        world = self.pending_menu()
        self.readmit_menu()
        execute = self.controller.execute_mission

        def later_current(*args, **kwargs):
            result = execute(*args, **kwargs)
            self.bridge.value["timestamp_ms"] += 1
            self.bridge.publish(deepcopy(self.bridge.value))
            self.controller.status()
            return result

        with patch.object(self.controller, "execute_mission", side_effect=later_current):
            result = self.dismiss_menu("normal-ack-new-current")
        first = self.runtime._registered_lifecycle.phase.first_normal
        self.assertNotEqual(first, self.runtime._current)
        self.assertEqual(first.observation_id, self.runtime._ledger.primitive_records()[-1]["result"]["source_after"])
        self.adopt(world)
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 1)

    def test_unknown_initial_load_menu_explicit_dismissals_identity_and_reopen(self):
        world = self.pending_menu()
        self.readmit_menu()
        self.dismiss_menu("dismiss-first")
        self.assertIsNone(self.runtime._registered_lifecycle.phase.first_normal)
        self.assertIsNone(adopted_timeline(self.runtime._ledger, self.runtime._store))
        returned = self.dismiss_menu("dismiss-last")
        first = self.runtime._registered_lifecycle.phase.first_normal
        self.assertEqual(first.boundary_kind, "normal_play")
        self.assertEqual(returned["result"]["provisional_scope"]["session"], first.session)
        adopted = self.adopt(world)
        self.assertEqual(adopted["result"]["normal_adoption"]["first_normal_source_id"], first.observation_id)
        original = self.runtime._ledger.primitive(self.original["logical_id"])
        self.assertEqual(original["state"], "unknown")
        self.assertEqual(original["result"], self.original["result"])
        self.assertIsNotNone(original["effect"])
        self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], self.original_root["deadline"])
        self.assertEqual(self.runtime._ledger.request("initial-load")["request"], self.original_root["request"])
        self.assertEqual(self.runtime._mission_deadline, self.original_deadline)
        self.assertEqual([p["intent"]["kind"] for p in self.runtime._ledger.primitive_records()],
                         ["resume", "action", "action", "resume", "action", "action", "action", "action"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 8)
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 1)
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.assertEqual(self.start()["state"], "completed")
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 1)
