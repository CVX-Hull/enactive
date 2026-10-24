"""Synthetic ordinary receiver/history regressions; no native qualification."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from harness.gameplay.evidence import CapacityError, EvidenceError, EvidenceStore
from tests import test_gameplay_evidence as fixtures


class OrdinaryEvidenceTests(unittest.TestCase):
    setUp = fixtures.EvidenceTests.setUp
    open_store = fixtures.EvidenceTests.open_store
    publish = fixtures.EvidenceTests.publish
    ingest = fixtures.EvidenceTests.ingest
    current = fixtures.EvidenceTests.current
    menu = fixtures.EvidenceTests.menu
    recapture = fixtures.EvidenceTests.recapture

    def preflight(self, before, *, number=2, received=100.5, now=100.5,
                  timestamp=1_000_500, changes=None, rule="ordinary_input"):
        value = self.recapture(self.store.observation(before), number)
        value.update(timestamp_ms=timestamp)
        if changes:
            changes(value)
        return self.store.retain_preflight(self.publish(value, fixtures.black_png()),
            received_monotonic=received, now_monotonic=now,
            now_timestamp_ms=timestamp, rule=rule)

    def reserve(self, before, preflight, *, rule="ordinary_input", now=100.5, timestamp=1_000_500):
        return self.store.reserve_dispatch(before, preflight=preflight, rule=rule,
            now_monotonic=now, now_timestamp_ms=timestamp)

    def terminal(self, value, *, received=101, now=110, timestamp=1_010_000, reservation=None):
        return self.store.retain_terminal(value, received_monotonic=received,
            now_monotonic=now, now_timestamp_ms=timestamp, reservation=reservation)

    def manifest(self):
        return json.loads((self.directory / "evidence.json").read_bytes())

    def test_changed_unfamiliar_receiver_retained_without_equivalence_or_promotion(self):
        before = self.ingest()
        generation = self.store.authority_generation()
        def change(value):
            value.update(revision=2, category="unfamiliar workshop", scene=None, ui=None,
                         actions=["new binding"])
            value["boundary"].update(kind="menu", id="unexpected-chooser")
        preflight = self.preflight(before, changes=change)
        self.assertFalse(self.store.equivalent(before, preflight, rule="native_state"))
        self.assertFalse(self.store.equivalent(before, preflight, rule="exact_png_bytes"))
        self.assertEqual(self.current(), before)
        self.assertEqual(self.store.authority_generation(), generation)
        token = self.reserve(before, preflight)
        self.assertEqual(token.before_observation_id, before.observation_id)
        self.assertEqual(token.preflight_observation_id, preflight.observation_id)
        self.store.release(token)

    def test_stale_informing_entry_with_fresh_actual_preflight_can_reserve(self):
        before = self.ingest()
        preflight = self.preflight(before, received=110, now=110, timestamp=1_010_000)
        self.assertEqual(self.store.inspect_current_boundary(now_monotonic=110,
            now_timestamp_ms=1_010_000), (before, False))
        token = self.reserve(before, preflight, now=110, timestamp=1_010_000)
        self.store.release(token)

    def test_semantic_rule_still_rejects_stale_entry_even_with_fresh_capture(self):
        for rule in ("native_state", "exact_png_bytes"):
            with self.subTest(rule=rule):
                self.store.close()
                self.directory = self.root / rule
                self.store = self.open_store()
                before = self.ingest()
                with self.assertRaises(EvidenceError):
                    self.preflight(before, received=110, now=110, timestamp=1_010_000, rule=rule)

    def test_ordinary_preflight_requires_uninterrupted_custody_and_live_receiver(self):
        changes = {
            "control": lambda v: v["boundary"].update(control_generation=1),
            "takeover": lambda v: v.update(takeover_generation=1),
            "pause": lambda v: v.update(paused=True),
            "origin": lambda v: v.update(pause_origin="human"),
            "receiver": lambda v: v["boundary"].update(input_receiver=False),
            "session": lambda v: v.update(session="unowned", frame="frame-unowned-2.png"),
            "rejected": lambda v: v.update(status="rejected"),
            "error": lambda v: v.update(error="refused"),
        }
        for name, change in changes.items():
            with self.subTest(change=name):
                self.store.close()
                self.directory = self.root / name
                self.store = self.open_store()
                before = self.ingest()
                def mutate(value):
                    value["revision"] = 2
                    change(value)
                with self.assertRaises(EvidenceError): self.preflight(before, changes=mutate)
                with self.assertRaises(EvidenceError): self.current()

    def test_paused_entry_cannot_support_an_ordinary_preflight(self):
        for field, change in (("paused", True), ("pause_origin", "human")):
            with self.subTest(field=field):
                self.store.close()
                self.directory = self.root / field
                self.store = self.open_store()
                value = fixtures.observation()
                value[field] = change
                before = self.ingest(self.publish(value))
                with self.assertRaises(EvidenceError): self.preflight(before)

    def test_receiver_availability_changes_between_distinct_captures_without_revision_churn(self):
        value = fixtures.observation()
        value["boundary"]["input_receiver"] = False
        before = self.ingest(self.publish(value))
        generation = self.store.authority_generation()
        preflight = self.preflight(before,
            changes=lambda v: v["boundary"].update(input_receiver=True))
        self.assertEqual(before.revision, preflight.revision)
        self.assertFalse(self.store.equivalent(before, preflight, rule="native_state"))
        self.assertEqual(self.store.source_status(before), "retained")
        self.assertEqual(self.store.source_status(preflight), "retained")
        self.assertEqual(self.store.authority_generation(), generation)
        token = self.reserve(before, preflight)
        self.store.release(token)
        unavailable = self.recapture(self.store.observation(before), 3)
        terminal = self.terminal(self.publish(unavailable))
        self.assertEqual(self.store.source_status(terminal), "retained")
        self.assertEqual(self.store.source_status(preflight), "retained")
        self.assertEqual(self.current(), before)

    def test_receiver_availability_is_immutable_for_the_same_source(self):
        before = self.ingest()
        preflight = self.preflight(before)
        mutated = self.store.observation(before)
        mutated["boundary"]["input_receiver"] = False
        with self.assertRaisesRegex(EvidenceError, "Contradictory metadata"):
            self.ingest(mutated)
        self.assertEqual(self.store.source_status(before), "disputed")
        # Availability alone does not dispute a different capture at this revision.
        self.assertEqual(self.store.source_status(preflight), "retained")
        with self.assertRaises(EvidenceError): self.current()

    def test_native6_receiver_flag_is_required_boolean_and_restricted(self):
        for flag in (None, 0, 1, "true", []):
            value = fixtures.observation(2)
            if flag is None: value["boundary"].pop("input_receiver")
            else: value["boundary"]["input_receiver"] = flag
            with self.subTest(flag=flag), self.assertRaises(EvidenceError):
                self.ingest(self.publish(value))
        for kind in ("unsupported", "activity_poll", "debug_prompt", "interrupt_confirmation"):
            value = fixtures.observation(3)
            value.update(scene=None, category="unknown")
            value["boundary"].update(kind=kind)
            if kind == "interrupt_confirmation":
                value["boundary"].update(recovery_operations=["answer_interrupt"],
                                         interrupt_request_id="owned-query")
            with self.subTest(kind=kind), self.assertRaises(EvidenceError):
                self.ingest(self.publish(value))

    def test_reservation_requires_explicit_actual_preflight_and_policy(self):
        before = self.ingest()
        with self.assertRaises(TypeError):
            self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        with self.assertRaises(EvidenceError): self.reserve(before, before)
        preflight = self.preflight(before)
        with self.assertRaises(TypeError):
            self.store.reserve_dispatch(before, preflight=preflight,
                now_monotonic=100.5, now_timestamp_ms=1_000_500)
        with self.assertRaises(EvidenceError): self.reserve(before, preflight, rule="native_state")
        token = self.reserve(before, preflight)
        with self.assertRaises(CapacityError): self.store.release(replace(token, preflight_observation_id=before.observation_id))
        self.store.release(token)

    def test_superseded_preflight_cannot_be_reserved(self):
        before = self.ingest()
        old = self.preflight(before)
        latest = self.preflight(before, number=3)
        with self.assertRaises(EvidenceError): self.reserve(before, old)
        token = self.reserve(before, latest)
        self.store.release(token)

    def test_intervening_current_ingest_invalidates_preflight_even_if_entry_returns(self):
        before = self.ingest()
        preflight = self.preflight(before)
        another = self.recapture(self.store.observation(before), 3)
        self.ingest(self.publish(another))
        self.ingest(self.store.observation(before))
        with self.assertRaises(EvidenceError): self.reserve(before, preflight)

    def test_reopen_and_reobserve_do_not_restore_preflight_binding(self):
        before = self.ingest()
        preflight = self.preflight(before)
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError): self.reserve(before, preflight)
        self.ingest(self.store.observation(before))
        with self.assertRaises(EvidenceError): self.reserve(before, preflight)

    def test_preflight_cannot_consume_its_own_after_reservation(self):
        before = self.ingest()
        preflight = self.preflight(before)
        token = self.reserve(before, preflight)
        with self.assertRaises(CapacityError):
            self.terminal(self.store.observation(preflight), reservation=token)
        self.store.release(token)

    def test_late_lower_revision_terminal_preserves_current_generation_and_clocks(self):
        current = self.ingest(self.publish(fixtures.observation(5)))
        generation = self.store.authority_generation()
        value = self.publish(fixtures.observation(2, timestamp_ms=1_000_200))
        terminal = self.terminal(value, received=100.3, now=160, timestamp=1_060_000)
        self.assertEqual(terminal.received_monotonic, 100.3)
        self.assertEqual(terminal.timestamp_ms, 1_000_200)
        self.assertEqual(self.store.authority_generation(), generation)
        self.assertEqual(self.current(), current)
        stored = self.manifest()["entries"][-1]
        self.assertEqual(stored["retention"], "terminal")
        self.assertAlmostEqual(stored["initial_lag_seconds"], 0.1)
        self.assertEqual(self.store.observation(terminal), value)
        self.store.close()
        self.store = self.open_store()
        self.assertEqual(self.store.observation(terminal), value)
        self.assertEqual(self.manifest()["entries"][-1], stored)
        self.assertEqual(self.store.authority_generation(), 0)
        with self.assertRaises(EvidenceError): self.current()

    def test_terminal_from_retired_owned_session_never_changes_session_frontier(self):
        first = self.ingest()
        current_value = self.publish(fixtures.observation(5, session="new-session"))
        current = self.ingest(current_value)
        generation = self.store.authority_generation()
        value = self.publish(fixtures.observation(2))
        terminal = self.terminal(value)
        self.assertEqual(terminal.session, first.session)
        self.assertEqual(self.current(), current)
        self.assertEqual(self.store.authority_generation(), generation)
        self.assertEqual(self.manifest()["session"], current.session)
        self.assertEqual(self.manifest()["retired_sessions"], [first.session])
        with self.assertRaises(EvidenceError): self.ingest(value)

    def test_terminal_does_not_advance_revision_frontier(self):
        current = self.ingest()
        value = self.publish(fixtures.observation(99))
        terminal = self.terminal(value)
        self.assertEqual(self.current(), current)
        self.assertEqual(terminal.revision, 99)
        next_current = self.ingest(self.publish(fixtures.observation(2)))
        self.assertEqual(self.current(), next_current)
        self.store.close()
        self.store = self.open_store()
        newer = self.ingest(self.publish(fixtures.observation(3)))
        self.assertEqual(self.current(), newer)

    def test_fresh_explicit_ingest_can_establish_current_from_terminal_without_clock_renewal(self):
        self.ingest()
        value = self.publish(fixtures.observation(2, timestamp_ms=1_000_200))
        terminal = self.terminal(value, received=100.25, now=100.5, timestamp=1_000_500)
        generation = self.store.authority_generation()
        self.assertEqual(self.ingest(value, received_monotonic=101, now_monotonic=101,
            now_timestamp_ms=1_001_000), terminal)
        self.assertEqual(self.current(now_monotonic=101, now_timestamp_ms=1_001_000), terminal)
        self.assertGreater(self.store.authority_generation(), generation)
        self.assertEqual(terminal.received_monotonic, 100.25)
        self.assertAlmostEqual(self.manifest()["entries"][-1]["initial_lag_seconds"], 0.05)
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError): self.ingest(fixtures.observation())

    def test_late_terminal_duplicate_keeps_first_clocks_and_cannot_become_fresh(self):
        self.ingest()
        value = self.publish(fixtures.observation(2, timestamp_ms=1_000_200))
        terminal = self.terminal(value, received=100.25, now=110, timestamp=1_010_000)
        stored = self.manifest()["entries"][-1]
        (self.bridge / value["frame"]).unlink()
        self.assertEqual(self.terminal(value, received=120, now=120, timestamp=1_020_000), terminal)
        self.assertEqual(self.manifest()["entries"][-1], stored)
        with self.assertRaises(EvidenceError):
            self.ingest(value, received_monotonic=120, now_monotonic=120, now_timestamp_ms=1_020_000)
        # Authority blocking caused by the failed refresh does not erase valid history.
        self.assertEqual(self.terminal(value, received=121, now=121, timestamp=1_021_000), terminal)
        self.assertEqual(self.manifest()["entries"][-1], stored)

    def test_delayed_retention_counts_original_age_once_up_to_historical_limit(self):
        before = self.ingest()
        value = self.publish(fixtures.observation(2))
        terminal = self.terminal(value, received=100, now=43_301, timestamp=44_201_000)
        self.assertEqual(self.manifest()["entries"][-1]["initial_lag_seconds"], 0)
        self.assertEqual(self.store.inspect_current_boundary(now_monotonic=43_301,
            now_timestamp_ms=44_201_000), (before, False))
        self.assertEqual(self.terminal(value, received=86_499, now=86_499,
            timestamp=87_399_000), terminal)
        self.assertEqual(terminal.received_monotonic, 100)
        with self.assertRaises(EvidenceError):
            self.terminal(value, received=86_501, now=86_501, timestamp=87_401_000)

    def test_delayed_terminal_processing_does_not_shorten_or_renew_dispatch_age(self):
        self.ingest()
        value = self.publish(fixtures.observation(2))
        terminal = self.terminal(value, received=100.25, now=101, timestamp=1_001_000)
        self.assertEqual(self.manifest()["entries"][-1]["initial_lag_seconds"], 0.25)
        self.assertEqual(self.ingest(value, received_monotonic=103,
            now_monotonic=103, now_timestamp_ms=1_003_000), terminal)
        with self.assertRaises(EvidenceError):
            self.ingest(value, received_monotonic=103.001,
                now_monotonic=103.001, now_timestamp_ms=1_003_001)

    def test_terminal_original_age_is_bounded_for_new_and_duplicate_sources(self):
        self.ingest()
        value = self.publish(fixtures.observation(2))
        terminal = self.terminal(value)
        generation = self.store.authority_generation()
        # Wall clock alone looks young; original monotonic receipt exposes the age.
        with self.assertRaises(EvidenceError):
            self.terminal(value, received=90_000, now=90_000, timestamp=1_020_000)
        self.assertEqual(self.store.historical_references[-1], terminal)
        self.assertGreaterEqual(self.store.authority_generation(), generation)
        too_old = self.publish(fixtures.observation(3))
        with self.assertRaises(EvidenceError):
            self.terminal(too_old, received=90_000, now=90_000, timestamp=90_000_000)
        future = self.publish(fixtures.observation(4, timestamp_ms=1_012_000))
        with self.assertRaises(EvidenceError): self.terminal(future)

    def test_duplicate_terminal_metadata_or_bytes_cannot_be_rewritten(self):
        self.ingest()
        value = self.publish(fixtures.observation(2))
        terminal = self.terminal(value)
        changed = deepcopy(value)
        changed["timestamp_ms"] += 1
        with self.assertRaises(EvidenceError): self.terminal(changed)
        self.assertEqual(self.store.source_status(terminal), "disputed")
        with self.assertRaises(EvidenceError): self.terminal(value)
        self.assertEqual(Path(terminal.frame_path).read_bytes(), fixtures.png())

    def test_terminal_requires_owned_session_and_available_capture(self):
        self.ingest()
        unknown = self.publish(fixtures.observation(2, session="unknown-session"))
        with self.assertRaises(EvidenceError): self.terminal(unknown)
        value = fixtures.observation(2)
        with self.assertRaises(EvidenceError): self.terminal(value)
        self.assertEqual(len(self.store.historical_references), 1)

    def test_terminal_reservation_consumes_capacity_without_current_promotion(self):
        self.store.close()
        self.store = self.open_store(max_frames=3)
        before = self.ingest()
        preflight = self.preflight(before)
        token = self.reserve(before, preflight)
        generation = self.store.authority_generation()
        value = self.publish(fixtures.observation(3))
        terminal = self.terminal(value, reservation=token)
        self.assertEqual(self.store.usage()["frames"], 3)
        self.assertEqual(self.current(), before)
        self.assertEqual(self.store.authority_generation(), generation)
        with self.assertRaises(CapacityError): self.store.release(token)
        with self.assertRaises(CapacityError): self.terminal(self.publish(fixtures.observation(4)))
        self.store.verify(terminal)

    def test_terminal_missing_or_corrupt_archive_remains_explicit_loss_on_reopen(self):
        for loss in ("missing", "corrupt"):
            with self.subTest(loss=loss):
                self.store.close()
                self.directory = self.root / loss
                self.store = self.open_store()
                self.ingest()
                terminal = self.terminal(self.publish(fixtures.observation(2)))
                path = Path(terminal.frame_path)
                if loss == "missing": path.unlink()
                else:
                    path.chmod(0o600)
                    path.write_bytes(fixtures.png(b"corrupt"))
                self.store.close()
                self.store = self.open_store()
                self.assertIn(terminal, self.store.historical_references)
                self.assertEqual(self.store.usage()["frames"], 2)
                with self.assertRaises(EvidenceError): self.store.observation(terminal)
                with self.assertRaises(EvidenceError): self.current()

    def test_archive5_rejects_missing_or_invalid_retention_and_bad_original_age(self):
        self.ingest()
        # This source was five seconds old at its actual receipt; only the
        # historical role may retain it, regardless of later processing delay.
        terminal = self.terminal(self.publish(fixtures.observation(2)), received=105)
        original = self.manifest()
        self.store.close()
        mutations = [lambda e: e.pop("retention"), lambda e: e.update(retention="unknown"),
                     lambda e: e.update(retention=True), lambda e: e.update(initial_lag_seconds=86_401),
                     lambda e: e.update(retention="current"), lambda e: e.update(retention="preflight")]
        for mutate in mutations:
            value = deepcopy(original)
            mutate(value["entries"][-1])
            (self.directory / "evidence.json").write_text(json.dumps(value))
            with self.subTest(mutate=mutate), self.assertRaises(EvidenceError): self.open_store()
            self.assertEqual(Path(terminal.frame_path).read_bytes(), fixtures.png())


if __name__ == "__main__":
    unittest.main()
