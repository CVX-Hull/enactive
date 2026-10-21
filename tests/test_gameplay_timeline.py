"""Synthetic retained timelines; no native reload, identity or authority evidence."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.contracts import ContractError, EvidenceRef
from harness.gameplay.evidence import EvidenceError, EvidenceStore
from harness.gameplay.timeline import GameTimeline, SessionContinuity, game_timeline
from tests.test_gameplay_evidence import observation, png


CLOCK = dict(received_monotonic=100.0, now_monotonic=100.0, now_timestamp_ms=1_000_000)


class TimelineTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".runtime" / "timeline-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.directory = self.root / "evidence"
        self.store = self.open_store()
        self.number = 0

    def open_store(self):
        store = EvidenceStore(self.bridge, self.directory, max_frames=64)
        self.addCleanup(store.close)
        return store

    def ingest(self, turn=0, *, session="a", revision=None, kind="normal_play", position=(0, 0, 0)):
        self.number += 1
        value = observation(self.number, session=session)
        value["revision"] = self.number if revision is None else revision
        value["boundary"]["kind"] = kind
        if kind == "normal_play":
            value["scene"].update(turn=turn, position=list(position))
        else:
            value.update(scene=None, category="UILIST" if kind == "menu" else "ACTIVITY")
        (self.bridge / value["frame"]).write_bytes(png())
        return self.store.ingest(value, **CLOCK)

    def reopen(self, edit=None):
        self.store.close()
        if edit is not None:
            manifest = self.directory / "evidence.json"
            value = json.loads(manifest.read_bytes())
            edit(value)
            manifest.write_text(json.dumps(value))
        self.store = self.open_store()

    def pair(self):
        first = self.ingest(-10)
        before = self.ingest(20, position=(11, 7, 0))
        after = self.ingest(20, session="b")
        last = self.ingest(55, session="b", position=(0, 2, 0))
        return first, before, after, last

    def test_empty_and_only_non_normal_have_no_clock(self):
        self.assertIsNone(game_timeline(self.store, ()))
        self.ingest(kind="menu")
        self.ingest(kind="activity_poll")
        self.assertIsNone(game_timeline(self.store, ()))

    def test_single_session_negative_turns_and_original_chronological_endpoints(self):
        first = self.ingest(-100, revision=1)
        self.ingest(kind="menu", revision=2)
        self.ingest(-100, revision=3)
        self.ingest(kind="activity_poll", revision=4)
        self.ingest(-20, revision=5)
        last = self.ingest(-20, revision=5)
        timeline = game_timeline(self.store, ())
        self.assertEqual(timeline, GameTimeline(80, first, last, ((first, last),), 0))
        with self.assertRaises(FrozenInstanceError):
            timeline.elapsed_seconds = 0

    def test_single_capture_and_identical_recapture_do_not_add_time(self):
        first = self.ingest(-4)
        self.assertEqual(self.store.ingest(self.store.observation(first), **CLOCK), first)
        self.assertEqual(game_timeline(self.store, ()), GameTimeline(0, first, first, ((first, first),), 0))

    def test_three_sessions_sum_exact_spans_and_new_coordinate_epoch(self):
        first, before, after, last = self.pair()
        self.ingest(kind="menu", session="b")
        next_first = self.ingest(55, session="c")
        latest = self.ingest(100, session="c", position=(-3, 0, 0))
        links = (SessionContinuity(before, after), SessionContinuity(last, next_first))
        generation = self.store.authority_generation()
        timeline = game_timeline(self.store, links)
        self.assertEqual(timeline, GameTimeline(110, first, latest,
                         ((first, before), (after, last), (next_first, latest)), 2))
        self.assertEqual(self.store.position(after), (0, 0, 0))
        self.assertEqual(self.store.authority_generation(), generation)

    def test_exact_turn_required_at_reload_in_both_directions(self):
        for turn in (19, 21):
            with self.subTest(turn=turn):
                self.store.close()
                self.directory = self.root / f"exact-turn-{turn}"
                self.store = self.open_store()
                before = self.ingest(20, session=f"before-{turn}")
                after = self.ingest(turn, session=f"after-{turn}")
                with self.assertRaises(EvidenceError):
                    game_timeline(self.store, (SessionContinuity(before, after),))

    def test_links_must_cover_exactly_every_adjacency_in_order(self):
        _, before, after, last = self.pair()
        third = self.ingest(55, session="c")
        one, two = SessionContinuity(before, after), SessionContinuity(last, third)
        for links in ((), (one,), (two,), (two, one), (one, one), (one, two, two)):
            with self.subTest(links=links), self.assertRaises(EvidenceError):
                game_timeline(self.store, links)

    def test_equal_turn_captures_still_require_exact_selected_endpoints(self):
        first = self.ingest(10, revision=1)
        before = self.ingest(10, revision=1)
        after = self.ingest(10, session="b", revision=1)
        last = self.ingest(10, session="b", revision=1)
        self.assertEqual(game_timeline(self.store, (SessionContinuity(before, after),)).segments,
                         ((first, before), (after, last)))
        for link in (SessionContinuity(first, after), SessionContinuity(before, last),
                     SessionContinuity(after, before), SessionContinuity(first, before)):
            with self.subTest(link=link), self.assertRaises(EvidenceError):
                game_timeline(self.store, (link,))

    def test_non_normal_reference_cannot_replace_a_real_adjacency_endpoint(self):
        _, before, after, _ = self.pair()
        menu = self.ingest(session="b", kind="menu")
        for link in (SessionContinuity(before, menu), SessionContinuity(menu, after)):
            with self.subTest(link=link), self.assertRaises(EvidenceError):
                game_timeline(self.store, (link,))

    def test_orphan_and_non_normal_links_reject_even_without_normal_refs(self):
        menu = self.ingest(kind="menu")
        poll = self.ingest(kind="activity_poll")
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, (SessionContinuity(menu, poll),))
        first = self.ingest(4)
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, (SessionContinuity(first, menu),))

    def test_forged_reference_does_not_match_canonical_endpoint(self):
        _, before, after, _ = self.pair()
        for change in (dict(received_monotonic=101), dict(revision=999),
                       dict(frame_path=before.frame_path + "-forged"), dict(frame_sha256="0" * 64)):
            with self.subTest(change=change), self.assertRaises(EvidenceError):
                game_timeline(self.store, (SessionContinuity(replace(before, **change), after),))

    def test_copied_endpoint_values_and_reopened_archive_preserve_result_without_authority(self):
        first, before, after, last = self.pair()
        copied_before = EvidenceRef.from_dict(before.to_dict())
        copied_after = EvidenceRef.from_dict(after.to_dict())
        self.assertIsNot(copied_before, before)
        link = SessionContinuity(copied_before, copied_after)
        with self.assertRaises(FrozenInstanceError):
            link.before = first
        expected = game_timeline(self.store, (link,))
        self.reopen()
        generation = self.store.authority_generation()
        self.assertEqual(game_timeline(self.store, (link,)), expected)
        self.assertEqual(expected, GameTimeline(65, first, last, ((first, before), (after, last)), 1))
        self.assertEqual(self.store.authority_generation(), generation)
        with self.assertRaises(EvidenceError):
            self.store.current(now_monotonic=100, now_timestamp_ms=1_000_000)

    def test_turn_regression_fails_without_reanchoring(self):
        self.ingest(20)
        self.ingest(19)
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, ())

    def test_archive_revision_regression_rejects_chronological_order(self):
        self.ingest(10)
        self.ingest(10)
        self.reopen(lambda value: value["entries"].reverse())
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, ())

    def test_archive_same_revision_contradictory_turns_reject(self):
        self.ingest(10)
        self.ingest(20)
        def edit(value):
            value["entries"][1]["reference"]["revision"] = 1
            value["entries"][1]["observation"]["revision"] = 1
        self.reopen(edit)
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, ())

    def test_archive_session_return_is_not_a_new_segment(self):
        self.ingest(10)
        self.ingest(20)
        self.ingest(20, session="b")
        def edit(value):
            a, b, c = value["entries"]
            value["entries"] = [a, c, b]
        self.reopen(edit)
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, ())

    def test_every_selected_endpoint_requires_available_original_bytes(self):
        for index in range(4):
            with self.subTest(endpoint=index):
                self.store.close()
                self.directory = self.root / f"lost-endpoint-{index}"
                self.store = self.open_store()
                refs = self.pair()
                links = (SessionContinuity(refs[1], refs[2]),)
                ref = refs[index]
                path = Path(ref.frame_path)
                original = path.read_bytes()
                path.unlink()
                with self.assertRaises(EvidenceError):
                    game_timeline(self.store, links)
                path.write_bytes(original)
                with self.assertRaises(EvidenceError):
                    game_timeline(self.store, links)

    def test_corruption_dispute_remains_after_restoration_and_reopen(self):
        first, before, after, _ = self.pair()
        links = (SessionContinuity(before, after),)
        path = Path(first.frame_path)
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(png(b"corrupt"))
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, links)
        path.write_bytes(original)
        self.store.verify(first)  # Byte integrity alone passes restored bytes.
        self.reopen()
        self.assertEqual(self.store.source_status(first), "disputed")
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, links)

    def test_same_revision_scene_dispute_cannot_support_link(self):
        before = self.ingest(20)
        after = self.ingest(20, session="b")
        self.number += 1
        value = observation(self.number, session="b")
        value["revision"] = after.revision
        value["scene"]["turn"] = after.turn + 1
        with self.assertRaises(EvidenceError):
            self.store.ingest(value, **CLOCK)
        self.store.verify(after)
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, (SessionContinuity(before, after),))

    def test_functional_link_and_segment_caps(self):
        refs = [self.ingest(-5, session=f"s-{number}") for number in range(17)]
        links = tuple(SessionContinuity(a, b) for a, b in zip(refs, refs[1:]))
        timeline = game_timeline(self.store, links)
        self.assertEqual((len(timeline.segments), timeline.coordinate_epoch, timeline.elapsed_seconds), (17, 16, 0))
        extra = self.ingest(-5, session="s-17")
        with self.assertRaises(EvidenceError):
            game_timeline(self.store, links)  # 18 segments fails independently.
        with self.assertRaises(ContractError):
            game_timeline(self.store, links + (SessionContinuity(refs[-1], extra),))

    def test_strict_types_reject_serialized_or_duck_typed_inputs(self):
        first = self.ingest(0)
        for links in ([], {}, False, None, (first,), ({"before": first, "after": first},), (True,)):
            with self.subTest(links=links), self.assertRaises(ContractError):
                game_timeline(self.store, links)
        for store in ({}, [], True, None):
            with self.subTest(store=store), self.assertRaises(ContractError):
                game_timeline(store, ())
        for ref in (first.to_dict(), [], True, None):
            with self.subTest(ref=ref), self.assertRaises(ContractError):
                SessionContinuity(ref, first)
            with self.subTest(ref=ref), self.assertRaises(ContractError):
                SessionContinuity(first, ref)
        for values in ((True, first, first, ((first, first),), 0),
                       (0, first, first, [(first, first)], 0),
                       (0, first, first, ((first, first),), False)):
            with self.subTest(values=values), self.assertRaises(ContractError):
                GameTimeline(*values)


if __name__ == "__main__":
    unittest.main()
