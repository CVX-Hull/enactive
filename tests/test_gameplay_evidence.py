"""Synthetic native-v4 observations only; never real CDDA/pipeline acceptance."""
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
from unittest.mock import patch

from harness.gameplay.contracts import ContractError
from harness.gameplay.evidence import (
    CapacityError, EvidenceError, EvidenceStore, MAX_BYTES, MAX_FRAME_BYTES, same_native_state,
)


def png(marker=b"synthetic"):
    # Static one-pixel fixture. Altered bytes exercise retained-hash integrity,
    # not image decoding; neither fixture is a real native observation.
    data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH3sAAAAASUVORK5CYII=")
    return data if marker == b"synthetic" else data + marker


def black_png():
    # Opaque black RGBA pixel, distinct from png()'s opaque white grayscale pixel.
    return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAX+XDSwAAAABJRU5ErkJggg==")


def observation(number=1, *, session="synthetic-world", timestamp_ms=1_000_000):
    return {"protocol": 4, "pause_origin": "none", "takeover_generation": 0, "ui": None, "id": "", "session": session, "revision": number,
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
    def test_passive_capture_equivalence_excludes_only_transport_and_capture_identity(self):
        original = observation()
        captured = deepcopy(original)
        captured.update(id="another-request", frame="frame-synthetic-world-99.png", timestamp_ms=1_002_000)
        self.assertTrue(same_native_state(original, captured))
        self.assertFalse(same_native_state(original, None))
        for field, value in (("protocol", 3), ("revision", 99), ("session", "other"),
                ("status", "rejected"), ("error", "native failure"), ("frame_ok", False),
                ("paused", True), ("pause_origin", "human"), ("takeover_generation", 1),
                ("actions", ["QUIT"]), ("ui", {}), ("category", "OTHER"), ("in_game", False)):
            with self.subTest(field=field):
                altered = {**captured, field: value}
                self.assertFalse(same_native_state(original, altered))
        for field in ("scene", "boundary"):
            with self.subTest(field=field):
                altered = deepcopy(captured)
                altered[field]["turn" if field == "scene" else "control_generation"] += 1
                self.assertFalse(same_native_state(original, altered))

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

    def retain(self, value, *, store=None, rule="native_state", **changes):
        arguments = dict(received_monotonic=100.25, now_monotonic=100.5, now_timestamp_ms=1_000_500)
        arguments.update(changes)
        return (self.store if store is None else store).retain_equivalent(value, rule=rule, **arguments)

    def recapture(self, value, number=2):
        copied = deepcopy(value)
        copied.update(frame=f"frame-{value['session']}-{number}.png", timestamp_ms=1_000_000,
                      id="final-preflight")
        return copied

    def menu(self):
        value = observation()
        value.update(category="UILIST", scene=None, ui={"purpose": "UILIST", "title": "Alarm",
            "rows": [{"id": "rendered-1", "text": "8 hours", "enabled": True, "hotkey": "8"},
                     {"id": "rendered-2", "text": "4 hours", "enabled": True, "hotkey": "4"}],
            "selected": "rendered-1", "filter": None, "count": None, "coverage": "rendered_rows_only"})
        value["boundary"]["kind"] = "menu"
        return value

    def test_equivalent_preflight_preserves_current_generation_clocks_and_canonical_bytes(self):
        value = self.publish(observation(timestamp_ms=999_900))
        before = self.ingest(value)
        generation = self.store.authority_generation()
        incoming = self.publish(self.recapture(value), black_png())
        retained = self.retain(incoming)
        self.assertNotEqual(retained, before)
        self.assertEqual(retained.received_monotonic, 100.25)
        self.assertEqual(self.current(), before)
        self.assertEqual(self.store.authority_generation(), generation)
        incoming["scene"]["position"][0] = 99
        self.assertEqual(self.store.position(retained), (0, 0, 0))
        self.assertTrue(self.store.equivalent(before, retained, rule="native_state"))
        self.assertFalse(self.store.equivalent(before, retained, rule="exact_png_bytes"))
        self.assertEqual(self.store.authority_generation(), generation)
        manifest = json.loads((self.directory / "evidence.json").read_bytes())
        after_entry = next(item for item in manifest["entries"] if item["reference"]["observation_id"] == retained.observation_id)
        self.assertEqual(after_entry["initial_lag_seconds"], 0.5)
        for path in self.bridge.iterdir(): path.unlink()
        self.assertEqual(self.retain(self.store.observation(retained), received_monotonic=101,
                                     now_monotonic=101, now_timestamp_ms=1_001_000), retained)
        self.assertEqual(self.current(), before)
        # Normal ingestion explicitly promotes the source, preserving first receipt.
        self.assertEqual(self.ingest(self.store.observation(retained), received_monotonic=101,
                                     now_monotonic=101, now_timestamp_ms=1_001_000), retained)
        self.assertEqual(self.current(now_monotonic=101, now_timestamp_ms=1_001_000), retained)
        self.assertGreater(self.store.authority_generation(), generation)
        self.store.close(); self.store = self.open_store()
        self.assertEqual(Path(retained.frame_path).read_bytes(), black_png())
        self.assertTrue(self.store.equivalent(before, retained, rule="native_state"))
        with self.assertRaises(EvidenceError): self.current()
        # The original lag plus elapsed time still applies after reopen.
        with self.assertRaises(EvidenceError):
            self.ingest(self.store.observation(retained), received_monotonic=102.8,
                        now_monotonic=102.8, now_timestamp_ms=1_002_800)

    def test_menu_native_equivalence_attests_rows_but_not_pixels(self):
        before_value = self.publish(self.menu())
        before = self.ingest(before_value)
        after = self.retain(self.publish(self.recapture(before_value), black_png()))
        self.assertTrue(self.store.equivalent(before, after, rule="native_state"))
        self.assertFalse(self.store.equivalent(before, after, rule="exact_png_bytes"))
        self.assertEqual(self.store.current_boundary(now_monotonic=100.5, now_timestamp_ms=1_000_500), before)

    def test_historical_inequality_checks_both_statuses_and_never_changes_current(self):
        changes = ({"paused": True}, {"pause_origin": "human"}, {"status": "rejected"},
                   {"error": "diagnostic"}, {"revision": 2},
                   {"session": "other-world", "frame": "frame-other-world-2.png"})
        for number, change in enumerate(changes):
            with self.subTest(change=change), EvidenceStore(self.bridge, self.root / f"historical-{number}") as store:
                value = self.publish()
                before = store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
                incoming = self.recapture(value); incoming.update(change)
                after = store.ingest(self.publish(incoming), received_monotonic=100.25,
                                     now_monotonic=100.5, now_timestamp_ms=1_000_500)
                generation = store.authority_generation()
                for rule in ("native_state", "exact_png_bytes"):
                    self.assertFalse(store.equivalent(before, after, rule=rule))
                    self.assertFalse(store.equivalent(after, before, rule=rule))
                self.assertEqual(store.authority_generation(), generation)
                self.assertEqual(store.current_boundary(now_monotonic=100.5, now_timestamp_ms=1_000_500), after)

    def test_null_content_requires_exact_png_and_metadata_equality(self):
        for rule, same_bytes, accepted in (("native_state", True, False),
                                           ("exact_png_bytes", True, True),
                                           ("exact_png_bytes", False, False)):
            with self.subTest(rule=rule, same_bytes=same_bytes):
                directory = self.root / f"null-{rule}-{same_bytes}"
                with EvidenceStore(self.bridge, directory) as store:
                    value = self.menu(); value["ui"] = None
                    before = store.ingest(self.publish(value), received_monotonic=100,
                                          now_monotonic=100, now_timestamp_ms=1_000_000)
                    after_value = self.publish(self.recapture(value), png() if same_bytes else black_png())
                    if accepted:
                        after = self.retain(after_value, store=store, rule=rule)
                        self.assertTrue(store.equivalent(before, after, rule=rule))
                        self.assertFalse(store.equivalent(before, after, rule="native_state"))
                    else:
                        with self.assertRaises(EvidenceError): self.retain(after_value, store=store, rule=rule)
                        with self.assertRaises(EvidenceError): store.current_boundary(now_monotonic=100, now_timestamp_ms=1_000_000)

    def test_preflight_native_changes_fail_closed_without_adopting_session(self):
        mutations = {
            "session": lambda v: v.update(session="another-world", frame="frame-another-world-2.png"),
            "revision": lambda v: v.update(revision=2),
            "boundary": lambda v: v["boundary"].update(id="other-boundary"),
            "control": lambda v: v["boundary"].update(control_generation=1),
            "position": lambda v: v["scene"].update(position=[1, 0, 0]),
            "turn": lambda v: v["scene"].update(turn=5),
            "neighbor": lambda v: v["scene"]["neighbors"][0].update(terrain="t_wall"),
            "actions": lambda v: v.update(actions=["UP"]),
            "category": lambda v: v.update(category="other"),
            "paused": lambda v: v.update(paused=True),
            "origin": lambda v: v.update(pause_origin="human"),
            "takeover": lambda v: v.update(takeover_generation=1),
            "status": lambda v: v.update(status="rejected"),
            "error": lambda v: v.update(error="capture diagnostic"),
            "unfinished": lambda v: v.update(status="dispatched"),
            "capture": lambda v: v.update(frame_ok=False),
            "in_game": lambda v: v.update(in_game=False),
        }
        for name, mutate in mutations.items():
            with self.subTest(field=name), EvidenceStore(self.bridge, self.root / f"mismatch-{name}") as store:
                value = self.publish()
                before = store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
                generation = store.authority_generation()
                incoming = self.recapture(value); mutate(incoming)
                with self.assertRaises(EvidenceError): self.retain(self.publish(incoming), store=store)
                self.assertGreater(store.authority_generation(), generation)
                with self.assertRaises(EvidenceError): store.current_boundary(now_monotonic=100, now_timestamp_ms=1_000_000)
                manifest = json.loads((store.directory / "evidence.json").read_bytes())
                self.assertIn(before.observation_id, manifest["blocked"])
                self.assertEqual(manifest["session"], before.session)
                self.assertEqual(manifest["retired_sessions"], [])

    def test_changed_menu_content_or_selection_rejects_even_with_identical_png(self):
        for field in ("rows", "selected", "title", "filter"):
            with self.subTest(field=field), EvidenceStore(self.bridge, self.root / field) as store:
                value = self.publish(self.menu())
                before = store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
                incoming = self.recapture(value)
                if field == "rows": incoming["ui"]["rows"][0]["text"] = "9 hours"
                elif field == "selected": incoming["ui"][field] = "rendered-2"
                else: incoming["ui"][field] = "changed"
                with self.assertRaises(EvidenceError): self.retain(self.publish(incoming), store=store, rule="exact_png_bytes")
                self.assertEqual(store.source_status(before), "disputed")

    def test_exact_png_mismatch_retains_diagnostic_without_promoting_it(self):
        value = self.publish()
        before = self.ingest(value)
        with self.assertRaises(EvidenceError):
            self.retain(self.publish(self.recapture(value), black_png()), rule="exact_png_bytes")
        self.assertEqual(len(self.store.historical_references), 2)
        after = self.store.historical_references[-1]
        self.assertEqual(after.received_monotonic, 100.25)
        self.assertEqual(Path(after.frame_path).read_bytes(), black_png())
        self.assertFalse(self.store.equivalent(before, after, rule="exact_png_bytes"))
        with self.assertRaises(EvidenceError): self.current()
        self.store.close(); self.store = self.open_store()
        self.assertFalse(self.store.equivalent(before, after, rule="exact_png_bytes"))
        with self.assertRaises(EvidenceError): self.current()

    def test_unknown_equivalence_rule_is_rejected_and_retention_invalidates(self):
        before = self.ingest()
        generation = self.store.authority_generation()
        with self.assertRaises(ContractError): self.store.equivalent(before, before, rule="pixel_similarity")
        self.assertEqual(self.store.authority_generation(), generation)
        with self.assertRaises(ContractError): self.retain(self.publish(self.recapture(observation())), rule="pixel_similarity")
        with self.assertRaises(EvidenceError): self.current()
        self.assertEqual(self.store.historical_references, (before,))

    def test_preflight_requires_fresh_current_and_preserves_existing_reservation(self):
        value = self.publish()
        before = self.ingest(value)
        token = self.store.reserve_dispatch(before, now_monotonic=100, now_timestamp_ms=1_000_000)
        with self.assertRaises(CapacityError): self.retain(self.publish(self.recapture(value)))
        self.store.release(token)  # Retention cannot consume the after reservation.
        self.assertEqual(self.store.historical_references, (before,))
        with self.assertRaises(EvidenceError): self.current()
        # Fresh Observe is required after any failed preflight, including expiry.
        value = self.publish(observation(3, timestamp_ms=1_004_000))
        before = self.ingest(value, received_monotonic=104, now_monotonic=104, now_timestamp_ms=1_004_000)
        incoming = self.recapture(value, 4); incoming["timestamp_ms"] = 1_007_100
        with self.assertRaises(EvidenceError): self.retain(self.publish(incoming), received_monotonic=107.1,
                                                         now_monotonic=107.1, now_timestamp_ms=1_007_100)
        self.assertEqual(self.store.historical_references[-1], before)
        with self.assertRaises(EvidenceError): self.current(now_monotonic=107.1, now_timestamp_ms=1_007_100)

    def test_preflight_integrity_and_disputes_survive_reopen(self):
        for damage in ("missing", "corrupt", "disputed"):
            with self.subTest(damage=damage), EvidenceStore(self.bridge, self.root / damage) as store:
                value = self.publish()
                before = store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
                after = self.retain(self.publish(self.recapture(value)), store=store)
                if damage == "missing": Path(after.frame_path).unlink()
                elif damage == "corrupt":
                    Path(after.frame_path).chmod(0o600); Path(after.frame_path).write_bytes(png(b"corrupt"))
                else:
                    conflict = deepcopy(value); conflict["scene"]["position"][0] = 2
                    with self.assertRaises(EvidenceError):
                        store.ingest(conflict, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
                with self.assertRaises(EvidenceError): store.equivalent(before, after, rule="exact_png_bytes")
                with self.assertRaises(EvidenceError): self.retain(self.publish(self.recapture(value, 3)), store=store)
                store.close()
                with EvidenceStore(self.bridge, self.root / damage) as reopened:
                    with self.assertRaises(EvidenceError): reopened.equivalent(before, after, rule="native_state")
                    with self.assertRaises(EvidenceError): reopened.current_boundary(now_monotonic=100, now_timestamp_ms=1_000_000)

    def test_preflight_capacity_and_write_failures_invalidate_and_preserve_sources(self):
        for failure in ("frames", "bytes", "metadata", "frame_write", "manifest_write"):
            with self.subTest(failure=failure), EvidenceStore(self.bridge, self.root / failure) as store:
                value = self.publish()
                before = store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
                incoming = self.publish(self.recapture(value))
                if failure == "frames": store.max_frames = 1
                elif failure == "bytes": store.max_bytes = len(png())
                target = "harness.gameplay.evidence.MAX_METADATA_BYTES"
                if failure == "metadata": context = patch(target, store.usage()["metadata_bytes"] + 2 * 1024 * 1024)
                elif failure in ("frame_write", "manifest_write"):
                    original_open = Path.open
                    def failing_open(path, *args, **kwargs):
                        mode = args[0] if args else kwargs.get("mode", "r")
                        if mode == "xb" and (path.suffix == ".png" if failure == "frame_write" else path.suffix == ".tmp"):
                            raise OSError("synthetic write failure")
                        return original_open(path, *args, **kwargs)
                    context = patch.object(Path, "open", failing_open)
                else: context = patch(target, 34 * 1024 * 1024)
                with context, self.assertRaises(EvidenceError): self.retain(incoming, store=store)
                with self.assertRaises(EvidenceError): store.current_boundary(now_monotonic=100, now_timestamp_ms=1_000_000)
                self.assertEqual(Path(before.frame_path).read_bytes(), png())
                # A persistent manifest-write fault cannot promise a durable diagnostic.
                if failure != "manifest_write":
                    manifest = json.loads((store.directory / "evidence.json").read_bytes())
                    self.assertIn(before.observation_id, manifest["blocked"])

    def test_menu_is_retained_without_scene_time_or_movement_permission(self):
        value = observation()
        value.update(category="UILIST", scene=None, ui={"purpose": "UILIST", "title": "Alarm",
            "rows": [{"id": "rendered-1", "text": "8 hours", "enabled": True, "hotkey": "8"}],
            "selected": "rendered-1", "filter": None, "count": None, "coverage": "rendered_rows_only"})
        value["boundary"]["kind"] = "menu"
        ref = self.ingest(self.publish(value))
        self.assertIsNone(ref.turn)
        self.assertEqual(self.store.observation(ref)["ui"], value["ui"])
        self.assertEqual(self.store.historical_facts(ref), ())
        clocks = dict(now_monotonic=100.0, now_timestamp_ms=1_000_000)
        self.assertEqual(self.store.current_boundary(**clocks), ref)
        with self.assertRaises(EvidenceError): self.current()
        with self.assertRaises(EvidenceError): self.store.position(ref)
        self.assertEqual(self.store.current_boundary(**clocks), ref)
        self.store.close(); self.store = self.open_store()
        self.assertEqual(self.store.observation(ref)["ui"], value["ui"])
        with self.assertRaises(EvidenceError): self.store.current_boundary(**clocks)

    def test_activity_and_recovery_frames_preserve_missing_time_and_no_input_authority(self):
        for number, kind in enumerate(("activity_poll", "interrupt_confirmation", "debug_prompt", "unsupported"), 1):
            value = observation(number)
            value.update(scene=None, category="ACTIVITY", paused=True, pause_origin="recovery")
            operation = {"activity_poll": ["request_interrupt"], "interrupt_confirmation": ["answer_interrupt"],
                         "debug_prompt": ["continue_debug_once"]}.get(kind, [])
            value["boundary"].update(kind=kind, recovery_operations=operation,
                                     interrupt_request_id="exact-owner" if kind=="interrupt_confirmation" else None)
            with self.subTest(kind=kind):
                ref = self.ingest(self.publish(value))
                self.assertIsNone(ref.turn)
                self.assertEqual(self.store.observation(ref)["boundary"]["kind"], kind)
                with self.assertRaises(EvidenceError): self.current()
                self.assertEqual(self.store.historical_facts(ref), ())

    def test_ui_owner_offpage_and_takeover_metadata_reject_without_hidden_facts(self):
        ui = {"purpose": "UILIST", "title": "", "rows": [], "selected": None,
              "filter": None, "count": None, "coverage": "rendered_rows_only"}
        mutations = [lambda v: v.update(ui=ui), lambda v: v.update(takeover_generation=True),
                     lambda v: v.update(pause_origin="guessed"), lambda v: v.update(takeover_generation=-1)]
        for number, change in enumerate(mutations, 1):
            value = self.publish(observation(number)); change(value)
            with self.subTest(number=number), self.assertRaises(EvidenceError): self.ingest(value)
        value = observation(5); value.update(scene=None, category="UILIST", ui={**ui,"selected":"hidden-row"})
        value["boundary"]["kind"]="menu"
        with self.assertRaises(EvidenceError): self.ingest(self.publish(value))

    def test_metadata_capacity_is_checked_before_reserving_input_evidence(self):
        ref = self.ingest()
        usage = self.store.usage()
        self.assertEqual(usage["frames"], 1)
        self.assertEqual(usage["max_frames"], 32)
        from harness.gameplay.evidence import MAX_ENTRY_BYTES, METADATA_HEADROOM
        with patch("harness.gameplay.evidence.MAX_METADATA_BYTES", usage["metadata_bytes"]+MAX_ENTRY_BYTES+METADATA_HEADROOM-1):
            with self.assertRaises(CapacityError):
                self.store.reserve_dispatch(ref, now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertEqual(self.current(), ref)
        self.assertEqual(len(self.store.historical_references), 1)

    def test_mission_caps_can_increase_retention_without_changing_defaults(self):
        self.store.close()
        self.store = self.open_store(max_frames=4096, max_bytes=1024*1024*1024)
        ref = self.ingest()
        self.assertEqual(self.store.usage()["max_frames"], 4096)
        self.assertEqual(self.current(), ref)

    def test_observation_copy_cannot_mutate_store_or_refresh_authority(self):
        first = self.ingest()
        value = self.store.observation(first)
        value["scene"]["position"][0] = 99
        value["actions"].clear()
        self.assertEqual(self.store.position(first), (0, 0, 0))
        self.assertTrue(self.store.observation(first)["actions"])
        second = self.ingest(self.publish(observation(2)))
        generation = self.store.authority_generation()
        self.assertEqual(self.store.observation(first)["revision"], first.revision)
        self.assertEqual(self.current(), second)
        self.assertEqual(self.store.authority_generation(), generation)

    def test_observation_accessor_rejects_disputed_retained_source(self):
        first = self.ingest()
        conflict = observation()
        conflict["scene"]["position"][0] = 1
        with self.assertRaises(EvidenceError):
            self.ingest(conflict)
        with self.assertRaisesRegex(EvidenceError, "Disputed"):
            self.store.observation(first)

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

    def test_generation_preserves_intervening_identity_and_rejection_events(self):
        first = self.publish()
        initial = self.store.authority_generation()
        ref = self.ingest(first)
        observed = self.store.authority_generation()
        self.assertGreater(observed, initial)
        self.ingest(first)
        self.assertEqual(self.store.authority_generation(), observed)
        second = dict(first, frame="frame-synthetic-world-2.png")
        self.ingest(self.publish(second))
        changed = self.store.authority_generation()
        self.assertGreater(changed, observed)
        with self.assertRaises(EvidenceError):
            self.ingest(dict(second, frame_ok=False))
        self.assertGreater(self.store.authority_generation(), changed)
        self.ingest(first)
        self.assertEqual(self.current(), ref)
        self.assertGreater(self.store.authority_generation(), observed)
        # Invalidation history is independent of historical truth.
        self.assertEqual(self.store.source_status(ref), "retained")

    def test_transport_pause_preserves_scene_but_not_current_frame_identity(self):
        before = self.publish()
        original = self.ingest(before)
        generation = self.store.authority_generation()
        paused = dict(before, frame="frame-synthetic-world-2.png", paused=True)
        current = self.ingest(self.publish(paused))
        self.assertEqual(self.current(), current)
        self.assertNotEqual(current, original)
        self.assertGreater(self.store.authority_generation(), generation)
        self.assertEqual(self.store.source_status(original), "retained")
        self.assertEqual(self.store.position(original), self.store.position(current))
        # A paused transport does not explain changed game facts at this revision.
        conflicting = deepcopy(paused)
        conflicting["frame"] = "frame-synthetic-world-3.png"
        conflicting["scene"]["neighbors"][0]["terrain"] = "t_wall"
        with self.assertRaises(EvidenceError):
            self.ingest(self.publish(conflicting))
        self.assertEqual(self.store.source_status(original), "disputed")
        self.assertEqual(self.store.source_status(current), "disputed")
        with self.assertRaises(EvidenceError):
            self.current()

    def test_transport_pause_cannot_rewrite_an_immutable_frame(self):
        original = self.publish()
        ref = self.ingest(original)
        with self.assertRaises(EvidenceError):
            self.ingest(dict(original, paused=True))
        self.assertEqual(self.store.source_status(ref), "disputed")

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
            lambda v: v.update(protocol=1), lambda v: v.update(protocol=2),
            lambda v: v.update(protocol=3), lambda v: v.update(protocol=5), lambda v: v.update(protocol=True),
            lambda v: v.update(protocol=3.0), lambda v: v.update(revision=True),
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
        self.store = self.open_store()
        with self.assertRaises(EvidenceError): self.store.verify(original)
        self.store.close()
        retained.unlink()
        self.store = self.open_store()
        with self.assertRaises(EvidenceError): self.store.verify(original)
        self.assertEqual(self.store.historical_references, (original,))

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
        for arguments in ({"max_frames": 4097}, {"max_bytes": MAX_BYTES + 1},
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
        for version in (None, 0, 1, 2, 4, True, 3.0):
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

    def test_dispute_survives_new_evidence_and_reopen_without_confusing_staleness(self):
        first = self.ingest()
        second_value = self.publish(observation(2))
        second = self.ingest(second_value)
        disputed = observation()
        disputed["scene"]["position"] = [1, 0, 0]
        with self.assertRaises(EvidenceError):
            self.ingest(disputed)
        third = self.ingest(self.publish(observation(3)))
        self.assertEqual(self.store.source_status(first), "disputed")
        self.assertEqual(self.store.source_status(second), "retained")
        with self.assertRaises(EvidenceError):
            self.current(now_monotonic=104, now_timestamp_ms=1_004_000)
        self.assertEqual(self.store.source_status(third), "retained")
        self.store.close()
        self.store = self.open_store()
        self.assertEqual(self.store.source_status(first), "disputed")
        self.assertEqual(self.store.source_status(third), "retained")

    def test_corruption_stays_disputed_after_restoration_and_reopen(self):
        first = self.ingest()
        second = self.ingest(self.publish(observation(2)))
        frame = Path(first.frame_path)
        original = frame.read_bytes()
        frame.chmod(0o600)
        frame.write_bytes(png(b"corrupt"))
        self.store.close()
        # A valid index remains inspectable for durable-memory invalidation.
        # Corrupt bytes still cannot provide observations or input authority.
        self.store = self.open_store()
        with self.assertRaises(EvidenceError): self.store.observation(first)
        with self.assertRaises(EvidenceError): self.current()
        persisted = json.loads((self.directory / "evidence.json").read_text())
        self.assertEqual(len(persisted["entries"]), 2)
        self.assertIn(first.observation_id, persisted["disputed"])
        self.store.close()
        frame.write_bytes(original)
        self.store = self.open_store()
        self.assertEqual(self.store.source_status(first), "disputed")
        self.assertEqual(self.store.source_status(second), "retained")

    def test_missing_newest_source_preserves_all_references_without_authority(self):
        first = self.ingest()
        newest = self.ingest(self.publish(observation(2)))
        frame = Path(newest.frame_path)
        original = frame.read_bytes()
        frame.unlink()
        self.store.close()
        self.store = self.open_store()
        self.assertEqual(self.store.historical_references, (first, newest))
        self.assertEqual(self.store.source_status(first), "retained")
        with self.assertRaises(EvidenceError): self.store.source_status(newest)
        with self.assertRaises(EvidenceError): self.current()
        self.store.close()
        frame.write_bytes(original)
        self.store = self.open_store()
        self.assertEqual(self.store.source_status(newest), "disputed")
        with self.assertRaises(EvidenceError): self.store.observation(newest)
        with self.assertRaises(EvidenceError): self.current()

    def test_source_loss_reopen_does_not_swallow_persistence_failure(self):
        newest = self.ingest()
        Path(newest.frame_path).unlink()
        self.store.close()
        with patch.object(EvidenceStore, "_save", side_effect=EvidenceError("No receipt capacity")):
            with self.assertRaisesRegex(EvidenceError, "No receipt capacity"): self.open_store()

    def test_missing_sources_keep_retention_slots_and_cannot_grow_manifest(self):
        self.store.close()
        self.store = self.open_store(max_frames=2)
        references = (self.ingest(), self.ingest(self.publish(observation(2))))
        for reference in references: Path(reference.frame_path).unlink()
        self.store.close()
        self.store = self.open_store(max_frames=2)
        self.assertEqual(self.store.usage()["frames"], 2)
        with self.assertRaises(CapacityError): self.ingest(self.publish(observation(3)))
        self.assertEqual(self.store.historical_references, references)
        self.store.close()
        self.store = self.open_store(max_frames=2)
        self.assertEqual(self.store.historical_references, references)
        self.store.close()
        (self.directory / "frames" / "orphan.png").write_bytes(png())
        with self.assertRaises(CapacityError): self.open_store(max_frames=2)

    def test_usage_tolerates_indexed_source_loss_after_directory_listing_without_releasing_slot(self):
        reference = self.ingest()
        target = Path(reference.frame_path)
        original = Path.iterdir
        def lose_after_listing(path):
            entries = list(original(path))
            if path == self.store.frames:
                target.unlink()
            return iter(entries)
        with patch.object(Path, "iterdir", lose_after_listing):
            measured = self.store.usage()
        self.assertEqual((measured["frames"], measured["bytes"]), (1, 0))
        self.assertEqual(self.store.historical_references, (reference,))
        with self.assertRaises(EvidenceError): self.store.source_status(reference)
        with self.assertRaises(EvidenceError): self.current()

    def test_usage_still_rejects_directory_and_dangling_symlink(self):
        unexpected = self.store.frames / "unexpected"
        unexpected.mkdir()
        with self.assertRaisesRegex(EvidenceError, "non-file"): self.store.usage()
        unexpected.rmdir()
        unexpected.symlink_to(self.root / "missing")
        with self.assertRaisesRegex(EvidenceError, "non-file"): self.store.usage()

    def test_inspect_current_reports_age_without_authority_but_detects_corruption(self):
        first = self.ingest()
        generation = self.store.authority_generation()
        for _ in range(5):
            reference, fresh = self.store.inspect_current(now_monotonic=104, now_timestamp_ms=1_004_000)
            self.assertEqual(reference, first)
            self.assertFalse(fresh)
        self.assertEqual(self.store.authority_generation(), generation)
        retained = Path(first.frame_path)
        retained.chmod(0o600)
        retained.write_bytes(png(b"changed"))
        with self.assertRaises(EvidenceError):
            self.store.inspect_current(now_monotonic=104, now_timestamp_ms=1_004_000)
        self.assertGreater(self.store.authority_generation(), generation)

    def test_boundary_inspection_exposes_menu_without_normal_scene_eligibility(self):
        ref = self.ingest(self.publish(self.menu()))
        generation = self.store.authority_generation()
        clocks = dict(now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertEqual(self.store.inspect_current_boundary(**clocks), (ref, True))
        self.assertEqual(self.store.inspect_current(**clocks), (None, False))
        self.assertEqual(self.store.inspect_current_boundary(now_monotonic=104, now_timestamp_ms=1_004_000), (ref, False))
        self.assertEqual(self.store.authority_generation(), generation)
        Path(ref.frame_path).chmod(0o600)
        Path(ref.frame_path).write_bytes(png(b"lost integrity"))
        with self.assertRaises(EvidenceError): self.store.inspect_current_boundary(**clocks)


if __name__ == "__main__":
    unittest.main()
