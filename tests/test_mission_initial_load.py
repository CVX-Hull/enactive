"""New admitted Load, separate from continuity reload; synthetic game only."""
from dataclasses import replace
import unittest

from harness.gameplay.lifecycle import adopted_timeline
from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture


class InitialLoadTests(MissionCreationFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.a = replace(self.a, scenario=replace(self.a.scenario, mode="load"))

    def picker(self):
        self.ready()
        self.stage = "load-world"
        begun = self.run_request(self.lifecycle("initial-load", "load"))
        self.assertEqual(begun["state"], "partial", begun)
        world = self.runtime._current
        selected = self.run_request(self.control("world", f"{self.a.scenario.world} (1)", parent="initial-load"))
        self.assertEqual(selected["state"], "partial", selected)
        return world

    def initial_load(self):
        world = self.picker()
        selection = self.control("character", self.a.scenario.character, parent="initial-load")
        selection["perception"] = None
        entered = self.run_request(selection)
        self.assertEqual(entered["state"], "unknown", entered)
        self.observe("loaded-observe")
        return self.finish_identity("initial-load", world)

    def test_initial_load_then_own_save_reload_and_reopened_history(self):
        adopted = self.initial_load()
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
