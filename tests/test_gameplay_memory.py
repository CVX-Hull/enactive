"""Synthetic memory tests use retained original PNG fixtures, never live gameplay."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import Budgets, ContractError, PrimitiveResult, TaskSpec
from harness.gameplay.evidence import CapacityError, EvidenceError, EvidenceStore, DEFAULT_BYTES, DEFAULT_FRAMES
from harness.gameplay.memory import TaskMemory
from tests.test_gameplay_contracts import candidate, skill
from tests.test_gameplay_evidence import observation, png


CLOCK = dict(now_monotonic=100.0, now_timestamp_ms=1_000_000)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".runtime" / "memory-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.directory = self.root / "evidence"
        self.store = self.open_store()
        self.task = TaskSpec("task-1", "synthetic-world", (0, 0, 0), "north", 4,
                             (0, -4, 0), 1, Budgets(), "request-1")
        self.memory = TaskMemory(self.task, self.store, execution_epoch=3)

    def open_store(self):
        store = EvidenceStore(self.bridge, self.directory)
        self.addCleanup(store.close)
        return store

    def ingest(self, number=1, *, position=(0, 0, 0), session="synthetic-world", frame=None):
        value = observation(number, session=session)
        value["scene"]["position"] = list(position)
        if frame is not None:
            value["frame"] = f"frame-{session}-{frame}.png"
        (self.bridge / value["frame"]).write_bytes(png())
        return self.store.ingest(value, received_monotonic=100.0, **CLOCK)

    def plan(self, **changes):
        values = dict(evidence_revision=1)
        values.update(changes)
        return self.memory.retain_plan(candidate(**values), skill(), **CLOCK)

    def snapshot(self, **clocks):
        return self.memory.snapshot(**(clocks or CLOCK))

    def test_explicit_refresh_immutable_snapshot_and_freshness(self):
        ref = self.ingest()
        self.assertEqual(self.snapshot().current_facts, ())
        snap = self.memory.refresh(**CLOCK)
        self.assertEqual(len(snap.current_facts), 3)
        self.assertTrue(all(f.evidence == ref for f in snap.current_facts))
        self.assertEqual(snap.as_of_monotonic, 100)
        self.assertEqual(snap.as_of_timestamp_ms, 1_000_000)
        self.assertFalse(snap.grants_authority)
        with self.assertRaises(FrozenInstanceError):
            snap.execution_epoch = 8
        self.plan()
        stale = self.snapshot(now_monotonic=104, now_timestamp_ms=1_004_000)
        self.assertEqual(stale.current_facts, ())
        self.assertEqual(len(stale.last_seen), 3)
        self.assertFalse(stale.plans[0].valid)
        self.assertEqual(snap.current_facts[0].evidence, ref)
        self.assertEqual(self.store.source_status(ref), "retained")

    def test_snapshot_and_plan_require_actual_clocks(self):
        self.ingest()
        self.memory.refresh(**CLOCK)
        with self.assertRaises(TypeError):
            self.memory.snapshot()
        for clocks in (dict(now_monotonic=True, now_timestamp_ms=1_000_000),
                       dict(now_monotonic=float("nan"), now_timestamp_ms=1_000_000),
                       dict(now_monotonic=100, now_timestamp_ms=True)):
            with self.subTest(clocks=clocks), self.assertRaises(ContractError):
                self.memory.snapshot(**clocks)
        self.assertEqual(self.snapshot().current_facts, ())
        with self.assertRaises(EvidenceError):
            self.memory.retain_plan(candidate(evidence_revision=1), skill(),
                                    now_monotonic=104, now_timestamp_ms=1_004_000)

    def test_same_revision_identity_change_invalidates_candidate(self):
        first = self.ingest()
        self.memory.refresh(**CLOCK)
        self.plan()
        second = self.ingest(frame=2)
        self.assertNotEqual(first.observation_id, second.observation_id)
        snap = self.snapshot()
        self.assertFalse(snap.plans[0].valid)
        self.assertEqual(snap.current_facts, ())
        self.assertEqual(len(self.memory.refresh(**CLOCK).current_facts), 3)
        self.assertFalse(self.snapshot().plans[0].valid)

    def _assert_return_to_original_invalidates_plan(self, *, reject_intermediate):
        first = self.ingest()
        self.memory.refresh(**CLOCK)
        self.memory.interpret("Retained historical context", (first,))
        self.plan()
        self.ingest(frame=2)
        if reject_intermediate:
            invalid = observation()
            invalid["frame"] = "frame-synthetic-world-2.png"
            invalid["frame_ok"] = False
            with self.assertRaises(EvidenceError):
                self.store.ingest(invalid, received_monotonic=100, **CLOCK)
        self.assertEqual(self.ingest(), first)
        snap = self.snapshot()
        self.assertFalse(snap.plans[0].valid)
        self.assertEqual(snap.current_facts, ())
        self.assertEqual(len(snap.last_seen), 3)
        self.assertTrue(snap.interpretations[0].valid)
        self.assertEqual(self.store.source_status(first), "retained")
        # Explicitly re-observing A permits new candidate data. The earlier
        # candidate remains invalid even though its frame identity matches again.
        self.memory.refresh(**CLOCK)
        self.plan(candidate_id="replacement")
        snap = self.snapshot()
        self.assertEqual(len(snap.current_facts), 3)
        self.assertFalse(snap.plans[0].valid)
        self.assertTrue(snap.plans[1].valid)

    def test_a_b_reject_a_cannot_hide_transient_store_invalidation(self):
        self._assert_return_to_original_invalidates_plan(reject_intermediate=True)

    def test_a_b_a_cannot_hide_transient_observation_identity_change(self):
        self._assert_return_to_original_invalidates_plan(reject_intermediate=False)

    def test_conflict_then_newer_ingest_between_refreshes_invalidates_beliefs_and_plans(self):
        first = self.ingest()
        self.memory.refresh(**CLOCK)
        self.memory.interpret("Possibly clear", (first,))
        self.memory.hypothesize("Return may work", (first,))
        self.plan()
        with self.assertRaises(EvidenceError):
            self.ingest(position=(1, 0, 0))
        self.ingest(2)
        snap = self.memory.refresh(**CLOCK)
        self.assertEqual(len(snap.current_facts), 3)
        self.assertEqual(len(snap.disputed_facts), 3)
        self.assertFalse(snap.interpretations[0].valid)
        self.assertFalse(snap.hypotheses[0].valid)
        self.assertFalse(snap.plans[0].valid)
        with self.assertRaises(EvidenceError):
            self.memory.interpret("Cannot reuse disputed evidence", (first,))

    def test_corrupt_restored_source_is_sticky_and_other_history_survives(self):
        first = self.ingest()
        self.memory.refresh(**CLOCK)
        self.memory.interpret("Old scene", (first,))
        self.ingest(2, position=(0, -1, 0))
        self.memory.refresh(**CLOCK)
        path = Path(first.frame_path)
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(png(b"bad"))
        snap = self.snapshot()
        self.assertFalse(snap.interpretations[0].valid)
        self.assertEqual(len(snap.disputed_facts), 3)
        path.write_bytes(original)
        self.store.close()
        self.store = self.open_store()
        self.assertEqual(self.store.source_status(first), "disputed")
        restarted = TaskMemory(self.task, self.store, execution_epoch=3)
        self.assertEqual(restarted.snapshot(**CLOCK).current_facts, ())
        self.assertEqual(restarted.snapshot(**CLOCK).last_seen, ())
        self.assertEqual(len(snap.last_seen) + len(snap.current_facts), 3)

    def test_epoch_retirement_session_change_and_restart_do_not_rearm(self):
        first = self.ingest()
        self.memory.refresh(**CLOCK)
        self.plan()
        self.memory.advance_epoch(4)
        snap = self.snapshot()
        self.assertEqual(len(snap.current_facts), 3)
        self.assertFalse(snap.plans[0].valid)
        self.plan(candidate_id="second", execution_epoch=4)
        for epoch in (4, 3, True):
            with self.assertRaises(ContractError):
                self.memory.advance_epoch(epoch)
        self.ingest(1, session="replacement-world")
        snap = self.memory.refresh(**CLOCK)
        self.assertEqual(snap.current_facts, ())
        self.assertEqual(len(snap.last_seen), 3)
        self.assertTrue(all(not p.valid for p in snap.plans))
        self.assertEqual(self.store.source_status(first), "retained")
        self.memory.retire("Goal replaced")
        self.assertTrue(self.snapshot().retired)
        with self.assertRaises(EvidenceError):
            self.plan(candidate_id="third", execution_epoch=4)
        with self.assertRaises(EvidenceError):
            self.memory.interpret("Retired", (first,))
        restarted = TaskMemory(self.task, self.store, execution_epoch=4)
        self.assertEqual(restarted.snapshot(**CLOCK).plans, ())

    def test_annotations_procedures_and_world_facts_stay_separate(self):
        first = self.ingest()
        self.memory.refresh(**CLOCK)
        self.memory.interpret("Route seems open", (first, first))
        self.memory.hypothesize("May return later", (first,))
        self.memory.remember_procedure(skill(), (first,), failure="A prior binding rejected")
        snap = self.snapshot()
        self.assertEqual(len(snap.current_facts), 3)
        self.assertEqual(len(snap.interpretations[0].value.sources), 1)
        self.assertEqual(snap.interpretations[0].value.tag, "interpretation")
        self.assertEqual(snap.hypotheses[0].value.tag, "hypothesis")
        self.assertEqual(snap.procedures[0].failure, "A prior binding rejected")
        self.assertFalse(snap.procedures[0].advertises_execution)
        self.assertEqual(snap.counts.procedures, 1)
        other = self.ingest(session="procedure-context-world")
        self.memory.remember_procedure(skill(), (other,), failure="Historical procedure context")
        self.assertEqual(self.snapshot().current_facts, ())
        self.assertEqual(self.snapshot().counts.procedures, 2)
        with self.assertRaises(EvidenceError):
            self.memory.interpret("Forged", (replace(first, turn=999),))
        with self.assertRaises(ContractError):
            self.memory.hypothesize("x" * 1025, (first,))

    def test_action_displacement_idempotency_conflict_and_unknown(self):
        before = self.ingest()
        self.memory.refresh(**CLOCK)
        after = self.ingest(2, position=(0, -1, 0))
        result = PrimitiveResult("action-1", before, after, "returned", (0, -1, 0), "Step observed")
        self.memory.record_action(result)
        self.memory.record_action(result)
        self.assertEqual(self.snapshot().counts.actions, 1)
        self.assertEqual(self.snapshot().actions[0].value, result)
        with self.assertRaises(EvidenceError):
            self.memory.record_action(replace(result, reason="Conflicting original"))
        snap = self.snapshot()
        self.assertTrue(snap.actions[0].conflicted)
        self.assertEqual(snap.actions[0].value, result)
        with self.assertRaises(EvidenceError):
            self.memory.record_action(replace(result, action_id="mismatch", observed_displacement=(0, -2, 0)))
        self.memory.refresh(**CLOCK)
        with self.assertRaises(EvidenceError):
            self.plan(candidate_id="conflict-blocked", evidence_revision=2)
        # A separate task-local memory tests unknown outcomes without the earlier
        # conflicting action, which must remain an independent permanent blocker.
        self.memory = TaskMemory(self.task, self.store, execution_epoch=3)
        self.memory.refresh(**CLOCK)
        self.plan(candidate_id="new", evidence_revision=2)
        unknown = PrimitiveResult("unknown", after, None, "unknown", None, "No observed result")
        self.memory.record_action(unknown)
        self.ingest(3, position=(0, -2, 0))
        snap = self.memory.refresh(**CLOCK)
        self.assertFalse(snap.plans[0].valid)
        self.assertIsNone(snap.actions[0].value.observed_displacement)
        with self.assertRaises(EvidenceError):
            self.plan(candidate_id="late", evidence_revision=3)

    def test_partial_rejected_and_cross_world_unknown_do_not_infer_success(self):
        before = self.ingest()
        self.memory.refresh(**CLOCK)
        after = self.ingest(2, position=(0, -1, 0))
        partial = PrimitiveResult("partial", before, after, "rejected", (0, -1, 0), "Blocked after movement")
        self.memory.record_action(partial)
        new_world = self.ingest(session="other-world")
        unknown = PrimitiveResult("old-world", after, new_world, "unknown", None, "World replaced")
        self.memory.record_action(unknown)
        snap = self.snapshot()
        self.assertEqual(snap.actions[0].value, partial)
        self.assertEqual(snap.actions[1].value, unknown)
        self.assertFalse(hasattr(snap, "completed"))
        with self.assertRaises(EvidenceError):
            self.memory.record_action(PrimitiveResult("foreign", new_world, None, "unknown", None, "Foreign action"))

    def test_larger_archive_cannot_expand_task_memory_dependency_limit(self):
        self.store.close()
        self.store = EvidenceStore(self.bridge, self.directory, max_frames=64)
        self.addCleanup(self.store.close)
        self.memory = TaskMemory(self.task, self.store, execution_epoch=3)
        for number in range(1, DEFAULT_FRAMES+1):
            self.ingest(number); self.memory.refresh(**CLOCK)
        self.ingest(DEFAULT_FRAMES+1)
        with self.assertRaises(CapacityError): self.memory.refresh(**CLOCK)
        snapshot = self.snapshot()
        self.assertEqual(snapshot.counts.unique_sources, DEFAULT_FRAMES)
        self.assertEqual(snapshot.counts.source_facts, 96)
        self.assertEqual(snapshot.costs.source_checks, DEFAULT_FRAMES)
        self.assertEqual(snapshot.current_facts, ())
        self.assertEqual(len(self.store.historical_references), DEFAULT_FRAMES+1)

    def test_long_history_bounded_unique_source_checks_and_capacity_no_eviction(self):
        refs = []
        for number in range(1, DEFAULT_FRAMES + 1):
            refs.append(self.ingest(number))
            self.memory.refresh(**CLOCK)
        for index in range(32):
            self.memory.interpret(f"Explanation {index}", tuple(refs[:8]))
            self.memory.hypothesize(f"Hypothesis {index}", tuple(refs[-8:]))
            self.memory.record_action(PrimitiveResult(f"action-{index}", refs[0], refs[1],
                                                     "returned", (0, 0, 0), "Observed no displacement"))
        for index in range(16):
            self.memory.remember_procedure(skill(), (refs[0],))
            self.plan(candidate_id=f"plan-{index}", evidence_revision=32)
        with patch.object(self.store, "source_status", wraps=self.store.source_status) as verify:
            snap = self.snapshot()
        self.assertEqual(verify.call_count, DEFAULT_FRAMES)
        self.assertEqual(len({call.args[0] for call in verify.call_args_list}), DEFAULT_FRAMES)
        self.assertEqual(snap.counts.source_facts, 96)
        self.assertEqual(snap.costs.maximum_source_checks, DEFAULT_FRAMES)
        self.assertEqual(snap.costs.maximum_retained_image_bytes, DEFAULT_BYTES)
        self.assertLessEqual(snap.counts.text_bytes, 64 * 1024)
        for append in (lambda: self.memory.interpret("Extra", (refs[0],)),
                       lambda: self.memory.hypothesize("Extra", (refs[0],)),
                       lambda: self.memory.remember_procedure(skill(), (refs[0],)),
                       lambda: self.plan(candidate_id="extra", evidence_revision=32),
                       lambda: self.memory.record_action(PrimitiveResult("extra", refs[0], refs[1], "returned", (0, 0, 0), "Extra"))):
            with self.assertRaises(CapacityError):
                append()
        final = self.snapshot()
        self.assertEqual(replace(final.counts, text_bytes=snap.counts.text_bytes), snap.counts)
        self.assertLessEqual(final.counts.text_bytes, snap.counts.text_bytes)
        self.assertTrue(all(not plan.valid for plan in final.plans))

    def test_plan_validation_checks_every_dependency_once_and_rejects_stale_bindings(self):
        first = self.ingest()
        self.memory.refresh(**CLOCK)
        self.memory.interpret("Historical expectation", (first,))
        self.ingest(2)
        self.memory.refresh(**CLOCK)
        with patch.object(self.store, "source_status", wraps=self.store.source_status) as verify:
            self.memory.retain_plan(candidate(evidence_revision=2), skill(), sources=(first,), **CLOCK)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(len({call.args[0] for call in verify.call_args_list}), 2)
        with self.assertRaises(ContractError):
            self.memory.retain_plan(candidate(evidence_revision=1), skill(), **CLOCK)
        self.assertEqual(self.snapshot().counts.plans, 1)
        # A transient store rejection that did not dispute historical sources
        # still revokes candidate use until an explicit new plan is retained.
        invalid = observation(3)
        invalid["frame_ok"] = False
        with self.assertRaises(EvidenceError):
            self.store.ingest(invalid, received_monotonic=100, **CLOCK)
        snap = self.snapshot()
        self.assertFalse(snap.plans[0].valid)
        self.assertTrue(snap.interpretations[0].valid)
        self.assertEqual(len(snap.last_seen), 6)

    def test_reference_and_total_text_limits_are_atomic(self):
        refs = [self.ingest(i) for i in range(1, 10)]
        self.memory.refresh(**CLOCK)
        with self.assertRaises(ContractError):
            self.memory.interpret("Too many references", tuple(refs))
        # UTF-8 bytes, not Python character count, enforce the task text budget.
        before = self.snapshot().counts
        for index in range(15):
            self.memory.hypothesize("界" * 1024, (refs[0],))
        with self.assertRaises(CapacityError):
            for index in range(32):
                self.memory.interpret("界" * 1024, (refs[0],))
        snap = self.snapshot()
        self.assertLessEqual(snap.counts.text_bytes, 64 * 1024)
        self.assertGreater(snap.counts.text_bytes, before.text_bytes)
        # Retirement and fail-closed diagnostics remain possible at text capacity;
        # their UTF-8 reserve is included in the conservative charge above.
        self.memory.retire("界" * 1024)
        retired = self.snapshot()
        self.assertLessEqual(retired.counts.text_bytes, 64 * 1024)
        self.assertEqual(retired.reason, "界" * 1024)
        self.assertEqual(retired.counts.interpretations, snap.counts.interpretations)


if __name__ == "__main__":
    unittest.main()
