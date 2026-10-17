"""Synthetic native-v2 observations only; never real CDDA/pipeline acceptance."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from harness.gameplay.contracts import ContractError
from harness.gameplay.evidence import (
    CapacityError, EvidenceError, EvidenceStore, MAX_BYTES, MAX_FRAME_BYTES,
)


def png(marker=b"synthetic"):
    # Static one-pixel fixture. Altered bytes exercise retained-hash integrity,
    # not image decoding; neither fixture is a real native observation.
    data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH3sAAAAASUVORK5CYII=")
    return data if marker == b"synthetic" else data + marker


def observation(number=1, *, session="synthetic-world", timestamp_ms=1_000_000):
    return {"protocol": 2, "id": "", "session": session, "revision": number,
            "category": "DEFAULTMODE", "actions": ["UP", "DOWN", "LEFT", "RIGHT"],
            "status": "ready", "error": "", "paused": False,
            "timestamp_ms": timestamp_ms, "frame_ok": True,
            "frame": f"frame-{session}-{number}.png", "in_game": True,
            "boundary": {"kind": "normal_play", "id": "boundary-1", "control_generation": 0,
                         "recovery_operations": [], "interrupt_request_id": None},
            "scene": {"provenance": "player-visible input boundary", "position": [0, 0, 0], "turn": 4,
                      "visible_creatures": [],
                      "neighbors": [{"dx": dx, "dy": dy, "visible": True,
                                     "terrain": "t_floor", "name": "floor", "furniture": "f_null"}
                                    for dy in range(-1, 2) for dx in range(-1, 2) if (dx, dy) != (0, 0)]}}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary_root = Path(__file__).resolve().parents[1] / ".runtime" / "gameplay-tests"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.directory = self.root / "session"
        self.store = self.open_store()

    def open_store(self, **changes):
        store = EvidenceStore(self.bridge, self.directory, **changes)
        self.addCleanup(store.close)
        return store

    def publish(self, value=None, data=None):
        value = observation() if value is None else value
        (self.bridge / value["frame"]).write_bytes(png() if data is None else data)
        return value

    def ingest(self, value=None, **changes):
        arguments = dict(received_monotonic=100.0, now_monotonic=100.0, now_timestamp_ms=1_000_000)
        arguments.update(changes)
        return self.store.ingest(self.publish() if value is None else value, **arguments)

    def current(self, **changes):
        arguments = dict(now_monotonic=100.0, now_timestamp_ms=1_000_000)
        arguments.update(changes)
        return self.store.current(**arguments)

    def test_retained_source_hash_identity_and_native_local_provenance(self):
        value = self.publish()
        ref = self.ingest(value)
        self.assertEqual(ref.frame_sha256, hashlib.sha256(png()).hexdigest())
        self.assertEqual(ref.session, value["session"])
        self.assertEqual(ref.timestamp_ms, value["timestamp_ms"])
        self.assertEqual(ref.received_monotonic, 100)
        self.assertEqual(ref.visibility_version, "cdda-visible/1")
        self.assertEqual(ref.observation_id, hashlib.sha256(json.dumps(
            [value["session"], value["frame"]], separators=(",", ":")).encode()).hexdigest())
        self.assertEqual(Path(ref.frame_path).read_bytes(), png())
        self.assertNotEqual(Path(ref.frame_path).parent, self.bridge)
        self.assertEqual(self.store.position(ref), (0, 0, 0))

    def test_original_survives_bridge_cache_eviction_and_reopen(self):
        value = self.publish()
        ref = self.ingest(value)
        (self.bridge / value["frame"]).unlink()
        self.store.verify(ref)
        self.assertEqual(self.ingest(value, received_monotonic=101, now_monotonic=101,
                                     now_timestamp_ms=1_001_000), ref)
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.current()
        self.assertEqual(self.ingest(value, received_monotonic=102, now_monotonic=102,
                                     now_timestamp_ms=1_002_000), ref)
        self.assertEqual(Path(ref.frame_path).read_bytes(), png())

    def test_reread_copy_and_different_transport_id_never_refresh_receipt(self):
        value = self.publish()
        original = self.ingest(value)
        copied = deepcopy(value)
        copied["id"] = "new-observe-request"
        self.assertEqual(self.ingest(copied, received_monotonic=102, now_monotonic=102,
                                     now_timestamp_ms=1_002_000), original)
        with self.assertRaises(EvidenceError):
            self.ingest(copied, received_monotonic=104, now_monotonic=104, now_timestamp_ms=1_004_000)
        with self.assertRaises(EvidenceError):
            self.current()
        self.assertEqual(self.store.historical_references, (original,))

    def test_first_ingestion_native_age_and_future_skew_limits(self):
        for number, timestamp in enumerate((996_999, 1_001_001), start=1):
            value = self.publish(observation(number, timestamp_ms=timestamp))
            with self.subTest(timestamp=timestamp), self.assertRaises(EvidenceError):
                self.ingest(value)
        value = self.publish(observation(3, timestamp_ms=997_000))
        ref = self.ingest(value)
        self.assertEqual(self.current(), ref)
        with self.assertRaises(EvidenceError):
            self.current(now_monotonic=100.001, now_timestamp_ms=1_000_000)
        value = self.publish(observation(4, timestamp_ms=1_001_000))
        self.ingest(value)

    def test_initial_native_lag_plus_elapsed_does_not_get_an_extra_three_seconds(self):
        value = self.publish(observation(timestamp_ms=997_100))
        ref = self.ingest(value)
        self.assertEqual(self.current(now_monotonic=100.05), ref)
        with self.assertRaises(EvidenceError):
            self.current(now_monotonic=100.2)
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.ingest(value, received_monotonic=100.2, now_monotonic=100.2)

    def test_exact_three_second_ceiling_and_clock_discontinuity(self):
        original = self.ingest()
        self.assertEqual(self.current(now_monotonic=103, now_timestamp_ms=1_003_000), original)
        with self.assertRaises(EvidenceError):
            self.current(now_monotonic=103.0001, now_timestamp_ms=1_003_000)
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.ingest(observation(), received_monotonic=1, now_monotonic=1)

    def test_invalid_time_types_and_nonfinite_fail_closed(self):
        for number, changes in enumerate((
            {"received_monotonic": True}, {"received_monotonic": float("nan")},
            {"now_monotonic": float("inf")}, {"now_monotonic": 99},
            {"now_timestamp_ms": True}, {"now_timestamp_ms": 1_000_000.0},
        ), start=1):
            value = self.publish(observation(number))
            with self.subTest(changes=changes), self.assertRaises(EvidenceError):
                self.ingest(value, **changes)
        self.assertEqual(self.store.historical_references, ())

    def test_all_other_boundaries_fail_positive_normal_play_requirement(self):
        for number, kind in enumerate(("activity_poll", "interrupt_confirmation", "debug_prompt", "menu", "unsupported", "invented"), start=1):
            value = self.publish(observation(number))
            value["boundary"]["kind"] = kind
            with self.subTest(kind=kind), self.assertRaises(EvidenceError):
                self.ingest(value)
        self.assertEqual(self.store.historical_references, ())

    def test_capture_failure_invalidates_current_and_old_frame_cannot_rearm(self):
        value = self.publish()
        ref = self.ingest(value)
        failed = deepcopy(value)
        failed["frame_ok"] = False
        with self.assertRaises(EvidenceError):
            self.ingest(failed)
        with self.assertRaises(EvidenceError):
            self.current()
        with self.assertRaises(EvidenceError):
            self.ingest(value)
        self.store.verify(ref)
        newer = self.publish(observation(2))
        self.assertEqual(self.ingest(newer).revision, 2)

    def test_session_transition_even_with_failed_capture_retires_old_world(self):
        old = self.ingest()
        failed_new = observation(2, session="synthetic-reloaded-world")
        failed_new["frame_ok"] = False
        with self.assertRaises(EvidenceError):
            self.ingest(failed_new)
        older_world_repaint = self.publish(observation(3))
        with self.assertRaises(EvidenceError):
            self.ingest(older_world_repaint)
        fresh_new = self.publish(observation(3, session="synthetic-reloaded-world"))
        new = self.ingest(fresh_new)
        self.assertNotEqual(old.session, new.session)
        self.store.verify(old)
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.ingest(older_world_repaint)

    def test_contradictory_scene_at_same_revision_invalidates_current(self):
        old = self.ingest()
        changed = self.publish(observation(2))
        changed["revision"] = 1
        changed["scene"]["position"] = [1, 0, 0]
        with self.assertRaises(EvidenceError):
            self.ingest(changed)
        with self.assertRaises(EvidenceError):
            self.current()
        self.assertEqual(self.store.historical_facts(old)[0].value, "[0, 0, 0]")
        with self.assertRaises(EvidenceError):
            self.ingest(observation())

    def test_same_source_cannot_change_timestamp_revision_or_scene_to_refresh(self):
        value = self.publish()
        ref = self.ingest(value)
        for field, replacement in (("timestamp_ms", 1_000_001), ("revision", 2)):
            altered = {**value, field: replacement}
            with self.subTest(field=field), self.assertRaises(EvidenceError):
                self.ingest(altered)
        self.assertEqual(self.store.historical_references, (ref,))
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.ingest(value, received_monotonic=102, now_monotonic=102)

    def test_revision_regression_is_not_fresh_authority(self):
        self.ingest(self.publish(observation(2)))
        with self.assertRaises(EvidenceError):
            self.ingest(self.publish(observation(1)))
        with self.assertRaises(EvidenceError):
            self.current()

    def test_noncurrent_metadata_conflict_stays_blocked_after_reopen(self):
        first = self.publish()
        old = self.ingest(first)
        second = self.publish({**observation(2), "revision": 1})
        self.ingest(second)
        with self.assertRaisesRegex(EvidenceError, "Contradictory metadata"):
            self.ingest({**first, "timestamp_ms": 1_000_001})
        for reopen in (False, True):
            if reopen:
                self.store.close()
                self.store = self.open_store()
            for value in (first, second):
                with self.subTest(reopen=reopen, frame=value["frame"]), self.assertRaises(EvidenceError):
                    self.ingest(value)
            self.store.verify(old)

    def test_noncurrent_revision_regression_is_also_an_identity_conflict(self):
        first = self.publish({**observation(1), "revision": 2})
        self.ingest(first)
        self.ingest(self.publish(observation(2)))
        with self.assertRaisesRegex(EvidenceError, "Contradictory metadata"):
            self.ingest({**first, "revision": 1})
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.ingest(first)

    def test_scene_conflict_blocks_all_retained_revision_peers(self):
        frames = [self.publish({**observation(number), "revision": 1}) for number in (1, 2, 3)]
        for value in frames:
            self.ingest(value)
        conflict = deepcopy(frames[0])
        conflict["scene"]["position"] = [1, 0, 0]
        with self.assertRaisesRegex(EvidenceError, "Contradictory metadata"):
            self.ingest(conflict)
        self.store.close()
        self.store = self.open_store()
        for value in frames:
            with self.subTest(frame=value["frame"]), self.assertRaises(EvidenceError):
                self.ingest(value)

    def test_strict_scene_types_neighbors_visibility_and_hidden_state_reject(self):
        changes = (
            lambda s: s.update(position=[0, False, 0]),
            lambda s: s.update(turn=True),
            lambda s: s.update(position=[0, 0]),
            lambda s: s.update(provenance="omniscient"),
            lambda s: s.update(inventory=[]),
            lambda s: s.update(visible_creatures=None),
            lambda s: s.update(visible_creatures=[{"name": "zombie", "hostile": 1}]),
            lambda s: s.update(neighbors=s["neighbors"][:-1]),
            lambda s: s["neighbors"].__setitem__(0, s["neighbors"][1]),
            lambda s: s["neighbors"][0].update(dx=True),
            lambda s: s["neighbors"][0].pop("furniture"),
            lambda s: s["neighbors"][0].update(visible=False),
        )
        for number, change in enumerate(changes, start=1):
            value = self.publish(observation(number))
            change(value["scene"])
            with self.subTest(number=number), self.assertRaises(EvidenceError):
                self.ingest(value)

    def test_invisible_unknown_neighbor_and_visible_creature_are_retained_as_facts(self):
        value = self.publish()
        value["scene"]["visible_creatures"] = [{"name": "cat", "hostile": False}]
        value["scene"]["neighbors"][0] = {"dx": -1, "dy": -1, "visible": False}
        ref = self.ingest(value)
        self.assertEqual(self.store.historical_facts(ref)[2].value, "1")
        # Retaining evidence does not implement movement admission or a safety claim.
        self.assertEqual(self.current(), ref)

    def test_wire_version_unknown_fields_bool_int_and_boundary_extra_fields_reject(self):
        changes = (
            lambda v: v.update(protocol=1), lambda v: v.update(protocol=True),
            lambda v: v.update(protocol=2.0), lambda v: v.update(revision=True),
            lambda v: v.update(revision=1.0), lambda v: v.update(timestamp_ms=True),
            lambda v: v.update(hidden_position=[1, 2, 3]), lambda v: v.pop("boundary"),
            lambda v: v["boundary"].update(control_generation=True),
            lambda v: v["boundary"].update(recovery_operations=["answer_interrupt"]),
            lambda v: v["boundary"].update(unknown=1),
            lambda v: v.update(category="YESNO"), lambda v: v.update(in_game=False),
            lambda v: v.update(status="dispatched"), lambda v: v.update(scene=None),
        )
        for number, change in enumerate(changes, start=1):
            value = self.publish(observation(number))
            change(value)
            with self.subTest(number=number), self.assertRaises(EvidenceError):
                self.ingest(value)

    def test_frame_path_session_identity_and_symlink_escape_reject(self):
        for number, frame in enumerate(("../outside.png", "/outside.png", "frame.png",
                                        "frame-other-world-1.png", "frame-synthetic-world-0.png"), start=1):
            value = observation(number)
            value["frame"] = frame
            with self.subTest(frame=frame), self.assertRaises(EvidenceError):
                self.ingest(value)
        value = observation(10)
        target = self.root / "outside.png"
        target.write_bytes(png())
        (self.bridge / value["frame"]).symlink_to(target)
        with self.assertRaises(EvidenceError):
            self.ingest(value)

    def test_evicted_unretained_source_and_missing_png_signature_never_get_reference(self):
        with self.assertRaises(EvidenceError):
            self.ingest(observation())
        for number, data in enumerate((b"not an image", b"", png()[:7]), start=2):
            with self.subTest(number=number), self.assertRaises(EvidenceError):
                self.ingest(self.publish(observation(number), data))
        self.assertEqual(self.store.historical_references, ())

    def test_oversized_native_png_is_missing_evidence_even_with_reservation(self):
        before = self.ingest()
        reservation = self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        value = observation(2)
        with (self.bridge / value["frame"]).open("wb") as stream:
            stream.write(png())
            stream.seek(MAX_FRAME_BYTES)
            stream.write(b"x")
        with self.assertRaises(EvidenceError):
            self.ingest(value, reservation=reservation)
        self.store.verify(before)
        self.assertEqual(self.store.historical_references, (before,))
        self.store.release(reservation)

    def test_retained_corruption_missing_source_and_modified_refs_fail(self):
        original = self.ingest()
        with self.assertRaises(EvidenceError):
            self.store.verify(replace(original, frame_sha256="b" * 64))
        with self.assertRaises(EvidenceError):
            self.store.verify(replace(original, frame_path=str(self.root / "outside.png")))
        retained = Path(original.frame_path)
        retained.chmod(0o600)
        retained.write_bytes(png(b"changed"))
        with self.assertRaises(EvidenceError):
            self.store.verify(original)
        with self.assertRaises(EvidenceError):
            self.current()
        self.store.close()
        with self.assertRaises(EvidenceError):
            self.open_store()
        retained.unlink()
        with self.assertRaises(EvidenceError):
            self.open_store()

    def test_32_distinct_frame_limit_survives_reopening_without_deletion(self):
        for number in range(1, 33):
            self.ingest(self.publish(observation(number)))
        accepted = self.store.historical_references
        self.store.close()
        self.store = self.open_store()
        self.assertEqual(self.store.historical_references, accepted)
        with self.assertRaises(CapacityError):
            self.ingest(self.publish(observation(33)))
        self.assertEqual(len(tuple((self.directory / "frames").iterdir())), 32)
        self.assertEqual(self.store.historical_references, accepted)

    def test_byte_limit_and_existing_orphan_frames_are_counted_on_reopen(self):
        ref = self.ingest()
        self.store.close()
        with self.assertRaises(CapacityError):
            self.open_store(max_bytes=len(png()) - 1)
        orphan = self.directory / "frames" / "orphan.png"
        orphan.write_bytes(png())
        with self.assertRaises(CapacityError):
            self.open_store(max_frames=1)
        self.assertTrue(orphan.exists())
        self.assertTrue(Path(ref.frame_path).exists())

    def test_limits_can_only_be_lowered_and_cache_directory_cannot_be_store(self):
        for arguments in ({"max_frames": 33}, {"max_bytes": MAX_BYTES + 1},
                          {"max_frames": True}, {"max_bytes": 0}):
            with self.subTest(arguments=arguments), self.assertRaises(CapacityError):
                EvidenceStore(self.bridge, self.root / "other-store", **arguments)
        with self.assertRaises(EvidenceError):
            EvidenceStore(self.bridge, self.bridge / "evictable")

    def test_dispatch_preflight_fails_before_frame_count_exhaustion(self):
        self.store.close()
        self.store = self.open_store(max_frames=1)
        ref = self.ingest()
        with self.assertRaises(CapacityError):
            self.store.preflight_dispatch(ref, now_monotonic=100, now_timestamp_ms=1_000_000)
        self.store.verify(ref)
        self.assertEqual(self.current(), ref)

    def test_dispatch_reserves_worst_case_bytes_not_current_frame_size(self):
        self.store.close()
        self.store = self.open_store(max_bytes=MAX_FRAME_BYTES + len(png()) - 1)
        ref = self.ingest()
        with self.assertRaises(CapacityError):
            self.store.reserve_dispatch(ref, now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertEqual(self.current(), ref)

    def test_reservation_excludes_unrelated_ingestion_and_consumes_exactly_once(self):
        self.store.close()
        self.store = self.open_store(max_frames=2)
        before = self.ingest()
        token = self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertEqual(token.frame_slots, 1)
        self.assertEqual(token.bytes_reserved, MAX_FRAME_BYTES)
        with self.assertRaises(CapacityError):
            self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        after = self.publish(observation(2))
        with self.assertRaises(CapacityError):
            self.ingest(after)
        result = self.ingest(after, reservation=token)
        self.assertEqual(result.revision, 2)
        with self.assertRaises(CapacityError):
            self.store.release(token)
        with self.assertRaises(CapacityError):
            self.store.reserve_dispatch(result, now_monotonic=100, now_timestamp_ms=1_000_000)
        self.store.verify(before)

    def test_release_reservation_and_require_exact_current_before(self):
        before = self.ingest()
        token = self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        with self.assertRaises(CapacityError):
            self.store.release(replace(token, token="forged"))
        self.store.release(token)
        new = self.ingest(self.publish(observation(2)))
        with self.assertRaises(EvidenceError):
            self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        token = self.store.reserve_dispatch(new, now_monotonic=100, now_timestamp_ms=1_000_000)
        self.store.release(token)

    def test_before_frame_reread_cannot_consume_after_reservation(self):
        value = self.publish()
        before = self.ingest(value)
        token = self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        with self.assertRaises(CapacityError):
            self.ingest(value, reservation=token)
        after = self.ingest(self.publish(observation(2)), reservation=token)
        self.assertEqual(after.revision, 2)

    def test_competing_threads_cannot_overbook_a_reservation(self):
        before = self.ingest()
        barrier = threading.Barrier(2)

        def reserve():
            barrier.wait(timeout=5)
            try:
                return self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
            except CapacityError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reserve), pool.submit(reserve)]
            results = [future.result(timeout=5) for future in futures]
        self.assertEqual(sum(result is not None for result in results), 1)
        self.store.release(next(result for result in results if result is not None))

    def test_one_writer_and_reopening_never_restores_dispatch_reservation(self):
        before = self.ingest()
        self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        with self.assertRaises(EvidenceError):
            self.open_store()
        self.store.close()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)

    def test_current_historical_facts_and_interpretations_have_separate_authority(self):
        ref = self.ingest()
        facts = self.store.current_facts(now_monotonic=100, now_timestamp_ms=1_000_000)
        comment = self.store.interpret("The route might be clear", (ref,))
        self.assertTrue(all(fact.tag == "fact" and fact.evidence == ref for fact in facts))
        self.assertEqual(comment.tag, "interpretation")
        with self.assertRaises(EvidenceError):
            self.current(now_monotonic=104, now_timestamp_ms=1_004_000)
        self.assertEqual(self.store.historical_facts(ref), facts)
        self.assertEqual(self.store.interpretations, (comment,))
        with self.assertRaises(EvidenceError):
            self.store.current_facts(now_monotonic=104, now_timestamp_ms=1_004_000)
        with self.assertRaises(ContractError):
            self.store.interpret("x" * 1025, (ref,))
        for _ in range(31):
            self.store.interpret("Bounded explanation", (ref,))
        with self.assertRaises(CapacityError):
            self.store.interpret("Too many explanations", (ref,))

    def test_malformed_persisted_metadata_fails_reopening_without_replacement(self):
        ref = self.ingest()
        self.store.close()
        manifest = self.directory / "evidence.json"
        original = manifest.read_bytes()
        value = json.loads(original)
        value["entries"][0]["reference"]["received_monotonic"] = 200
        manifest.write_text(json.dumps(value))
        # Original receipt is part of the locally trusted manifest: validate
        # continuity when re-ingested; a restart cannot grant current authority.
        self.store = self.open_store()
        with self.assertRaises(EvidenceError):
            self.ingest(observation(), now_monotonic=100)
        self.store.close()
        value = json.loads(original)
        value["entries"][0]["observation"]["session"] = "contradictory-world"
        manifest.write_text(json.dumps(value))
        with self.assertRaises(EvidenceError):
            self.open_store()
        self.assertEqual(Path(ref.frame_path).read_bytes(), png())

    def test_store_rejects_unsupported_versions_without_migration_or_replacement(self):
        ref = self.ingest()
        self.store.close()
        manifest = self.directory / "evidence.json"
        original = manifest.read_bytes()
        for version in (None, 0, 2, True, 1.0):
            with self.subTest(version=version):
                value = json.loads(original)
                if version is None:
                    value.pop("store_version")
                else:
                    value["store_version"] = version
                manifest.write_text(json.dumps(value))
                before = manifest.read_bytes()
                with self.assertRaises(EvidenceError):
                    self.open_store()
                self.assertEqual(manifest.read_bytes(), before)
                self.assertEqual(Path(ref.frame_path).read_bytes(), png())


if __name__ == "__main__":
    unittest.main()
