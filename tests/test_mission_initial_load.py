"""New admitted Load, separate from continuity reload; synthetic game only."""
from dataclasses import replace
from copy import deepcopy
from pathlib import Path
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
        with self.runtime._ledger._mutex:
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

    def prepare_wrong_identity(self):
        world = self.pending_initial_load()
        self.assertEqual(self.run_request(self.lifecycle("reconciled", "load", parent="initial-load"))["state"], "completed")
        self.assertEqual(self.run_request(self.lifecycle("readmitted", "load", parent="initial-load"))["state"], "completed")
        self.assertEqual(self.run_request(self.control("inspected", "Character", kind="inspect", parent="initial-load"))["state"], "completed")
        screen = self.runtime._current
        world_id = self.remember_identity("selected-world", "world", world, 0)
        wrong_name = self.a.scenario.character + " (Male)"
        character_id = self.remember_identity("selected-character", "character", screen, 0, value=wrong_name)
        self.assertEqual(self.run_request(self.control("dismissed", "Cancel", parent="initial-load"))["state"], "partial")
        return world_id, character_id, screen, wrong_name

    def test_identity_value_refusal_names_character_and_allows_explicit_correction(self):
        world_id, character_id, screen, wrong_name = self.prepare_wrong_identity()
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
        fixed = self.run_request(dict(schema="mission/11", kind="correct", request_id="correct-character",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=corrected,
            retired_ids=[character_id], reason="Separate the interpreted name from demographic text in the retained identity screen"))
        self.assertEqual(fixed["state"], "completed", fixed)
        adopted = self.run_request(self.lifecycle("corrected-adoption", "load", parent="initial-load", claims=[world_id, corrected["id"]]))
        self.assertEqual(adopted["state"], "completed", adopted)
        self.assertEqual(original["value"]["state"], wrong_name)
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)

    def prepare_corrected_identity(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        corrected = self.correct_identity(character_id, "correct-character", self.a.scenario.character)
        return world_id, corrected["id"]

    def prepare_misgrounded_world(self):
        world_id, character_id = self.prepare_corrected_identity()
        screen = self.runtime._registered_lifecycle.phase.identity_screen
        mistaken_id = self.remember_identity("screen-world", "world", screen, 0)
        return mistaken_id, world_id, character_id, screen

    def test_world_on_identity_screen_can_be_replaced_by_fresh_menu_claim(self):
        mistaken_id, world_id, character_id, _ = self.prepare_misgrounded_world()
        unknown = deepcopy(next(p for p in self.runtime._ledger.primitive_records()
            if p["request_id"] == "character"))
        self.assertEqual(unknown["state"], "unknown")
        self.assert_correctable_selection(mistaken_id, character_id)
        proper = deepcopy(next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
            if row["entry"]["id"] == world_id))
        proper.update(id="cross-scope-world", supersedes=[mistaken_id])
        refused = self.run_request(dict(schema="mission/11", kind="correct", request_id="cross-scope-correct",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=proper,
            retired_ids=[mistaken_id], reason="Replace the unsupported world grounding with the actual menu"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("exact scope", refused["result"]["reason"])
        reference = next(ref for ref in self.runtime._store.historical_references
            if ref.observation_id == proper["sources"][0])
        fresh_id = self.remember_identity("fresh-menu-world", "world", reference, 0)
        adopted = self.run_request(self.lifecycle("fresh-menu-adoption", "load", parent="initial-load",
            claims=[fresh_id, character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)
        self.assertEqual(next(p for p in self.runtime._ledger.primitive_records()
            if p["request_id"] == "character"), unknown)
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)

    def test_misgrounded_world_cannot_hide_corrupt_selected_pixels(self):
        mistaken_id, _, character_id, screen = self.prepare_misgrounded_world()
        def corrupt():
            path = Path(screen.frame_path)
            path.chmod(0o600)
            path.write_bytes(b"corrupt selected world source")
        self.assert_wrong_identity_fault(mistaken_id, character_id, corrupt)

    def test_misgrounded_world_cannot_hide_corrupt_launch_pixels(self):
        mistaken_id, _, character_id, _ = self.prepare_misgrounded_world()
        launch_id = self.runtime._owned_launch.request_id
        launch_source = self.runtime._ledger.request(launch_id)["result"]["source_ids"][0]
        reference = next(ref for ref in self.runtime._store.historical_references
            if ref.observation_id == launch_source)
        def corrupt():
            path = Path(reference.frame_path)
            path.chmod(0o600)
            path.write_bytes(b"corrupt original launch endpoint")
        self.assert_wrong_identity_fault(mistaken_id, character_id, corrupt)

    def corrupt_primitive_preflight(self, request_id):
        primitive = next(p for p in self.runtime._ledger.primitive_records()
            if p["request_id"] == request_id)
        identity = primitive["intent"]["preflight_source"]
        self.assertNotEqual(identity, primitive["intent"]["source_before"])
        self.assertNotEqual(identity, (primitive["result"] or {}).get("source_after"))
        reference = next(ref for ref in self.runtime._store.historical_references
            if ref.observation_id == identity)
        def corrupt():
            path = Path(reference.frame_path)
            path.chmod(0o600)
            path.write_bytes(b"corrupt distinct primitive preflight")
        return corrupt

    def test_misgrounded_world_cannot_hide_corrupt_transition_preflight(self):
        mistaken_id, _, character_id, _ = self.prepare_misgrounded_world()
        self.assert_wrong_identity_fault(mistaken_id, character_id,
            self.corrupt_primitive_preflight("character"))

    def test_wrong_identity_value_cannot_hide_corrupt_transition_preflight(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        self.assert_wrong_identity_fault(world_id, character_id,
            self.corrupt_primitive_preflight("character"))

    def test_misgrounded_world_cannot_hide_corrupt_inspection_preflight(self):
        mistaken_id, _, character_id, _ = self.prepare_misgrounded_world()
        self.assert_wrong_identity_fault(mistaken_id, character_id,
            self.corrupt_primitive_preflight("inspected"))

    def test_wrong_identity_value_cannot_hide_corrupt_launch_pixels(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        source_id = self.runtime._ledger.request(self.runtime._owned_launch.request_id)["result"]["source_ids"][0]
        reference = next(ref for ref in self.runtime._store.historical_references
            if ref.observation_id == source_id)
        def corrupt():
            path = Path(reference.frame_path)
            path.chmod(0o600)
            path.write_bytes(b"corrupt launch before early semantic refusal")
        self.assert_wrong_identity_fault(world_id, character_id, corrupt)

    def test_misgrounded_world_cannot_hide_missing_launch_endpoint(self):
        from harness.gameplay.contracts import canonical
        mistaken_id, _, character_id, _ = self.prepare_misgrounded_world()
        launch_id = self.runtime._owned_launch.request_id
        def corrupt():
            result = self.runtime._ledger.request(launch_id)["result"]
            result["source_ids"] = ["f" * 64]
            self.runtime._ledger._db.execute("UPDATE requests SET result=? WHERE id=?", (canonical(result), launch_id))
        self.assert_wrong_identity_fault(mistaken_id, character_id, corrupt)

    def test_misgrounded_world_cannot_hide_damaged_transition(self):
        mistaken_id, _, character_id, _ = self.prepare_misgrounded_world()
        self.assert_wrong_identity_fault(mistaken_id, character_id, self.remove_primitive("character"))

    def test_misgrounded_world_cannot_hide_forged_claim_payload(self):
        mistaken_id, _, character_id, _ = self.prepare_misgrounded_world()
        self.assert_wrong_identity_fault(mistaken_id, character_id, self.change_selected_claim(mistaken_id,
            lambda entry: entry.update(text="Unadmitted interpretation replacement")))

    def test_misgrounded_world_cannot_hide_lost_current_lease(self):
        mistaken_id, _, character_id, _ = self.prepare_misgrounded_world()
        def lose_lease():
            with self.controller.data_lock:
                self.controller._mission_lease = None
        self.assert_wrong_identity_fault(mistaken_id, character_id, lose_lease)

    def correct_identity(self, identity, request_id, name, *, retired=None):
        entry = deepcopy(next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
            if row["entry"]["id"] == identity))
        retired = [identity] if retired is None else retired
        entry.update(id=request_id + "-claim", value=dict(quantity=None, state=name), supersedes=retired)
        response = self.run_request(dict(schema="mission/11", kind="correct", request_id=request_id,
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=entry,
            retired_ids=retired, reason="Correct the interpreted identity using the retained visible source"))
        self.assertEqual(response["state"], "completed", response)
        return entry

    def assert_correctable_selection(self, world_id, character_id):
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        deadline = self.runtime._ledger.request("initial-load")["deadline"]
        delivered = len(self.bridge.delivered)
        refused = self.run_request(self.lifecycle("frontier-refusal", "load", parent="initial-load",
            claims=[world_id, character_id]))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("No input was sent", refused["result"]["reason"])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)
        self.assertEqual(len(self.bridge.delivered), delivered)

    def test_retired_identity_selection_preserves_phase_for_replacement(self):
        world_id, character_id = self.prepare_corrected_identity()
        replacement = self.correct_identity(world_id, "replace-world", self.a.scenario.world)
        self.assert_correctable_selection(world_id, character_id)
        adopted = self.run_request(self.lifecycle("replacement-adoption", "load", parent="initial-load",
            claims=[replacement["id"], character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)

    def test_authentic_identity_conflict_preserves_phase_for_explicit_correction(self):
        world_id, character_id = self.prepare_corrected_identity()
        original = next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
            if row["entry"]["id"] == world_id)
        conflict = deepcopy(original)
        conflict.update(id="conflicting-world", value=dict(quantity=None, state="Other world"))
        response = self.run_request(dict(schema="mission/11", kind="remember", request_id="remember-conflict",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=conflict))
        self.assertEqual(response["state"], "completed", response)
        self.assert_correctable_selection(world_id, character_id)
        replacement = self.correct_identity(world_id, "resolve-world", self.a.scenario.world,
            retired=[world_id, conflict["id"]])
        adopted = self.run_request(self.lifecycle("resolved-adoption", "load", parent="initial-load",
            claims=[replacement["id"], character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)

    def test_corrupt_frontier_influence_cannot_preserve_retired_selection(self):
        world_id, character_id = self.prepare_corrected_identity()
        replacement = self.correct_identity(world_id, "replace-world", self.a.scenario.world)
        def corrupt():
            from harness.gameplay.contracts import canonical
            replacement["value"]["state"] = "Corrupted world"
            self.runtime._ledger._db.execute("UPDATE memory SET body=? WHERE record_id=?",
                (canonical(replacement), replacement["id"]))
        self.assert_wrong_identity_fault(world_id, character_id, corrupt)

    def test_equivalent_equal_order_identity_assertions_remain_admissible(self):
        world_id, character_id = self.prepare_corrected_identity()
        original = next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
            if row["entry"]["id"] == world_id)
        equivalent = deepcopy(original)
        equivalent["id"] = "equivalent-world"
        response = self.run_request(dict(schema="mission/11", kind="remember", request_id="remember-equivalent",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=equivalent))
        self.assertEqual(response["state"], "completed", response)
        adopted = self.run_request(self.lifecycle("equivalent-adoption", "load", parent="initial-load",
            claims=[world_id, character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)

    def test_wrong_world_epoch_preserves_phase_for_original_selection(self):
        world_id, character_id = self.prepare_corrected_identity()
        original = next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
            if row["entry"]["id"] == world_id)
        wrong = deepcopy(original)
        wrong["id"] = "wrong-epoch-world"
        wrong["scope"]["coordinate_epoch"] = 1
        response = self.run_request(dict(schema="mission/11", kind="remember", request_id="remember-wrong-epoch",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=wrong))
        self.assertEqual(response["state"], "completed", response)
        self.assert_correctable_selection(wrong["id"], character_id)
        adopted = self.run_request(self.lifecycle("right-epoch-adoption", "load", parent="initial-load",
            claims=[world_id, character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)

    def test_later_equivalent_identity_does_not_poison_historical_adoption(self):
        adopted = self.initial_load()
        world_id = adopted["result"]["normal_adoption"]["world_claim_id"]
        equivalent = deepcopy(next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
            if row["entry"]["id"] == world_id))
        equivalent["id"] = "later-equivalent-world"
        response = self.run_request(dict(schema="mission/11", kind="remember", request_id="remember-later-equivalent",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=equivalent))
        self.assertEqual(response["state"], "completed", response)
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.assertEqual(self.start()["state"], "completed")
        self.assertEqual(len(adopted_timeline(self.runtime._ledger, self.runtime._store).segments), 1)

    def assert_wrong_identity_fault(self, world_id, character_id, corruption, *, claims=None):
        delivered = len(self.bridge.delivered)
        deadline = self.runtime._ledger.request("initial-load")["deadline"]
        lifecycle = self.runtime._registered_lifecycle
        command = lifecycle.command
        injected = []

        def corrupt_at_adoption(work):
            if work.request["request_id"] == "unhealthy-adoption":
                # Result visibility precedes trailing publication. Inject on the
                # single writer only after this target request is admitted, so a
                # prior request's finalization cannot consume the fault first.
                corruption()
                injected.append(work.request["request_id"])
            return command(work)

        with patch.object(lifecycle, "command", side_effect=corrupt_at_adoption):
            rejected = self.run_request(self.lifecycle("unhealthy-adoption", "load", parent="initial-load",
                claims=[world_id, character_id] if claims is None else claims))
        self.assertEqual(injected, ["unhealthy-adoption"])
        self.assertEqual(rejected["state"], "blocked", rejected)
        self.assertNotIn("No input was sent", rejected["result"]["reason"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime._ledger.request("initial-load")["deadline"], deadline)

    def remove_primitive(self, request_id):
        return lambda: self.runtime._ledger._db.execute(
            "DELETE FROM primitives WHERE request_id=?", (request_id,))

    def test_wrong_identity_cannot_hide_corrupt_inspection_pixels(self):
        world_id, character_id, screen, _ = self.prepare_wrong_identity()
        def corrupt():
            path = Path(screen.frame_path)
            path.chmod(0o600)
            path.write_bytes(b"corrupt retained inspection")
        self.assert_wrong_identity_fault(world_id, character_id, corrupt)

    def test_wrong_identity_cannot_hide_missing_inspection_primitive(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        self.assert_wrong_identity_fault(world_id, character_id, self.remove_primitive("inspected"))

    def change_selected_claim(self, character_id, change):
        from harness.gameplay.contracts import canonical
        def corrupt():
            original = next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
                if row["entry"]["id"] == character_id)
            change(original)
            self.runtime._ledger._db.execute("UPDATE memory SET body=? WHERE record_id=?",
                (canonical(original), character_id))
        return corrupt

    def test_wrong_identity_cannot_hide_changed_admitted_claim(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        self.assert_wrong_identity_fault(world_id, character_id, self.change_selected_claim(character_id,
            lambda entry: entry["value"].update(state="Unadmitted replacement")))

    def test_wrong_identity_subject_cannot_hide_changed_admitted_claim(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        self.assert_wrong_identity_fault(world_id, character_id, self.change_selected_claim(character_id,
            lambda entry: entry["key"].update(subject="world", coverage_id="visible-world-menu")))

    def test_incomplete_selection_cannot_hide_missing_inspection_primitive(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        self.assert_wrong_identity_fault(world_id, character_id, self.remove_primitive("inspected"), claims=[world_id])

    def test_wrong_subject_selection_cannot_hide_missing_inspection_primitive(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        world = next(row["entry"] for row in self.runtime._ledger.memory_records("claim")
            if row["entry"]["id"] == world_id)
        reference = next(ref for ref in self.runtime._store.historical_references
            if ref.observation_id == world["sources"][0])
        other_world = self.remember_identity("other-world", "world", reference, 0)
        self.assert_wrong_identity_fault(world_id, character_id, self.remove_primitive("inspected"),
            claims=[world_id, other_world])

    def test_wrong_identity_value_cannot_hide_missing_transition_primitive(self):
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        self.assert_wrong_identity_fault(world_id, character_id, self.remove_primitive("character"))

    def test_incomplete_selection_cannot_hide_missing_inspection_phase(self):
        from harness.gameplay.contracts import canonical
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        def corrupt():
            result = self.runtime._ledger.request("inspected")["result"]
            del result["phase"]
            self.runtime._ledger._db.execute("UPDATE requests SET result=? WHERE id='inspected'", (canonical(result),))
        self.assert_wrong_identity_fault(world_id, character_id, corrupt, claims=[world_id])

    def test_incomplete_selection_cannot_hide_missing_inspection_source_membership(self):
        from harness.gameplay.contracts import canonical
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        def corrupt():
            result = self.runtime._ledger.request("inspected")["result"]
            result["source_ids"] = []
            self.runtime._ledger._db.execute("UPDATE requests SET result=? WHERE id='inspected'", (canonical(result),))
        self.assert_wrong_identity_fault(world_id, character_id, corrupt, claims=[world_id])

    def test_incomplete_selection_cannot_hide_missing_inspection_ack(self):
        from harness.gameplay.contracts import canonical
        world_id, character_id, _, _ = self.prepare_wrong_identity()
        def corrupt():
            primitive = next(row for row in self.runtime._ledger.primitive_records()
                if row["request_id"] == "inspected")
            del primitive["result"]["native_ack"]
            self.runtime._ledger._db.execute("UPDATE primitives SET result=? WHERE id=?",
                (canonical(primitive["result"]), primitive["logical_id"]))
        self.assert_wrong_identity_fault(world_id, character_id, corrupt, claims=[world_id])

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
        return dict(schema="mission/11", kind="reconcile", request_id="wrong-recovery",
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
        with self.runtime._ledger._mutex:
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
        self.load_rows = [dict(id="row-0", text="Another character", enabled=True, hotkey=None, rendered_marker=None)]
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
