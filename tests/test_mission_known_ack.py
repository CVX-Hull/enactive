"""Actual controller/writer/SQLite composition with synthetic visible transport."""
import copy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from harness.gameplay.evidence import EvidenceError, _identity
from tests import test_mission_runtime as fixtures


class KnownAckRuntimeTests(unittest.TestCase):
    setUp = fixtures.MissionRuntimeTests.setUp
    start = fixtures.MissionRuntimeTests.start
    wait = fixtures.MissionRuntimeTests.wait
    request = fixtures.MissionRuntimeTests.request
    result = fixtures.MissionRuntimeTests.result
    settled = fixtures.MissionRuntimeTests.settled
    navigation = fixtures.MissionRuntimeTests.navigation
    control = fixtures.MissionRuntimeTests.control
    open_direction = fixtures.MissionRuntimeTests.open_direction

    def test_publication_bookkeeping_failure_binds_and_settles_known_ack_once(self):
        self.start()
        request = self.navigation()
        with patch.object(self.runtime._ledger, "published", side_effect=OSError("publication fsync failed")) as fail:
            self.runtime.command(request)
            operation = self.settled(request["request_id"])
        self.assertEqual(operation["state"], "completed", operation)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(fail.call_count, 1)
        self.assertEqual(primitive["state"], "returned")
        receipt = primitive["result"]
        self.assertEqual(receipt["native_ack"]["id"], primitive["native_id"])
        self.assertEqual(receipt["source_after"], _identity(receipt["native_ack"]))
        self.assertIn("publication fsync failed", receipt["processing_error"])
        self.assertIsNone(receipt["evidence_loss"])
        self.assertEqual(self.runtime.status()["unresolved_effects"], [])
        # A successful atomic fallback repairs the bookkeeping gap. Its durable
        # commit does not warrant another recovery loop or an automatic Pause.
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertIsNotNone(self.runtime._lease)
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)
        self.assertEqual(self.runtime.command(request)["operation"], operation)
        self.assertEqual(self.runtime._ledger.primitive_records()[0]["result"], receipt)

    def test_current_ingestion_failure_cannot_rewrite_or_lose_retained_known_delivery(self):
        self.start()
        request = self.navigation()
        terminal = self.runtime._store.retain_terminal
        ingest = self.runtime._store.ingest
        retained = []

        def capture(*args, **kwargs):
            ref = terminal(*args, **kwargs)
            retained.append(ref)
            return ref

        def ingest_current(*args, **kwargs):
            if retained:
                raise OSError("current capture index failed")
            return ingest(*args, **kwargs)

        with patch.object(self.runtime._store, "retain_terminal", side_effect=capture), \
                patch.object(self.runtime._store, "ingest", side_effect=ingest_current):
            self.runtime.command(request)
            operation = self.settled(request["request_id"])
        self.assertEqual(operation["state"], "blocked", operation)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(primitive["state"], "returned")
        self.assertEqual(primitive["result"]["source_after"], retained[0].observation_id)
        self.assertTrue(Path(retained[0].frame_path).is_file())
        # Current publication follows immutable settlement, so its failure is a
        # separate operation diagnostic, never a retrospective receipt rewrite.
        self.assertIsNone(primitive["result"]["processing_error"])
        self.assertIsNone(primitive["result"]["evidence_loss"])
        self.assertIn("current capture index failed", operation["result"]["reason"])
        self.assertEqual(self.runtime.status()["unresolved_effects"], [])
        self.assertIsNone(self.runtime.status()["current_source"])
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)

    def test_deferred_archive_audit_reports_loss_without_rewriting_known_delivery(self):
        self.start()
        request = self.navigation()
        execute = self.controller.execute_mission
        lost = []

        def lose_preflight(*args, **kwargs):
            raw = execute(*args, **kwargs)
            identity = _identity(raw["preflight"]["observation"])
            (self.runtime._store.frames / (identity + ".png")).unlink()
            lost.append(identity)
            return raw

        with patch.object(self.controller, "execute_mission", side_effect=lose_preflight):
            self.runtime.command(request)
            operation = self.settled(request["request_id"])
        self.assertEqual(operation["state"], "completed", operation)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(primitive["state"], "returned")
        self.assertEqual(lost, [primitive["intent"]["preflight_source"]])
        self.assertEqual(primitive["result"]["native_ack"]["id"], primitive["native_id"])
        self.assertEqual(primitive["result"]["source_after"], _identity(primitive["result"]["native_ack"]))
        # Authentication trusts the pre-publication capture, without another
        # full-file validation. The later consuming path detects the loss;
        # settlement is already immutable and must not be rewritten afterward.
        self.assertIsNone(primitive["result"]["evidence_loss"])
        preflight = next(ref for ref in self.runtime._store.historical_references
                         if ref.observation_id == lost[0])
        with self.assertRaises(EvidenceError):
            self.runtime._store.verify(preflight)
        self.assertEqual(self.runtime._ledger.primitive_records()[0]["result"], primitive["result"])
        self.assertEqual(self.runtime.status()["unresolved_effects"], [])
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)

    def test_superseding_current_capture_keeps_ack_and_ends_text_batch_at_new_prompt(self):
        self.superseding_current(advance_revision=True)

    def test_same_revision_distinct_current_capture_also_ends_batch(self):
        self.superseding_current(advance_revision=False, timestamp_delta=1)

    def test_same_revision_same_millisecond_current_also_ends_batch(self):
        self.superseding_current(advance_revision=False, timestamp_delta=0)

    def superseding_current(self, *, advance_revision, timestamp_delta=0):
        self.a = replace(self.a, allowed_skills=(*self.a.allowed_skills, "direct"))
        root, _ = self.open_direction()
        original_phase = self.runtime._prompt_phase
        request = self.control("direct", dict(input=dict(type="text", text="ab"),
            interrupt_allowed=False, intent="Try visible text", expected="Inspect effect"),
            phase_id=root["request_id"], request_id="text-with-current-drift")
        execute = self.controller.execute_mission
        acknowledgments = []

        def changed_current(*args, **kwargs):
            raw = execute(*args, **kwargs)
            acknowledgments.append(copy.deepcopy(raw))
            if advance_revision:
                self.bridge.value["category"] = "DIFFERENT_AFTER_INPUT"
                self.bridge.value["boundary"]["id"] = "changed-interface"
                self.bridge.value["revision"] += 1
            else:
                # A distinct current image can have identical pixels and game
                # revision; it is still not the immutable ACK capture.
                self.bridge.value["timestamp_ms"] += timestamp_delta
            self.bridge.publish(self.bridge.value.copy())
            self.controller.status()  # Independently receive the actual capture.
            return raw

        before_usage = self.runtime._store.usage()["frames"]
        with patch.object(self.controller, "execute_mission", side_effect=changed_current):
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            operation = self.settled(request["request_id"])
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(len(acknowledgments), 1)  # No automatic next scalar.
        primitive = self.runtime._ledger.primitive_records()[-1]
        ack = acknowledgments[0]["result"]
        current = self.runtime._current
        self.assertEqual(primitive["state"], "returned")
        self.assertEqual(primitive["result"]["source_after"], _identity(ack))
        self.assertNotEqual(current.observation_id, primitive["result"]["source_after"])
        self.assertIn(current.observation_id, operation["result"]["source_ids"])
        self.assertIn(_identity(ack), operation["result"]["source_ids"])
        phase = self.runtime._prompt_phase
        self.assertEqual(phase.checkpoint, current)
        self.assertEqual((phase.root_id, phase.game_anchor, phase.operator_generation),
                         (original_phase.root_id, original_phase.game_anchor, original_phase.operator_generation))
        self.assertFalse(phase.quantity_editor)
        # Entry, preflight, ACK and genuinely different current all cost a frame.
        self.assertEqual(self.runtime._store.usage()["frames"] - before_usage, 4)


if __name__ == "__main__":
    unittest.main()
