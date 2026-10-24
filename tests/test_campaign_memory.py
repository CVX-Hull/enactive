"""Synthetic native-v4 regressions inspired by pilot failure families.

These fixtures are not historical campaign frames, gameplay or efficacy evidence.
The actual canonical EvidenceStore and SQLite ledger exercise source integrity and
restart behavior; no input authority or controller is involved.
"""
from copy import deepcopy
from contextlib import closing
import inspect
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from harness.gameplay.campaign_memory import CampaignMemory
from harness.gameplay.contracts import ContractError
from harness.gameplay.evidence import CapacityError, EvidenceStore
from harness.gameplay.contracts import canonical
from harness.gameplay.mission_contracts import MEMORY_VERSION, VERSION, MemoryRequestRefusal, validate_memory_entry, validate_work_view
from harness.gameplay.mission_ledger import LedgerError, MissionLedger
from tests.test_gameplay_evidence import observation, png
from tests.test_mission_contracts import admission, claim, request, scope, skill
from tests.test_mission_ledger import intent


def reference_frontier(claims, selected_ids=None):
    """Retain the original pairwise semantics independently of the reducer."""
    ancestors, retired = {}, set()
    for identity, entry in claims.items():
        parents = set(entry["supersedes"]) | {parent for support in entry["supports"] for parent in support["claims"]}
        if not parents <= ancestors.keys() or any(claims[parent]["scope"] != entry["scope"] for parent in parents):
            raise ContractError("Invalid reference dependency history")
        ancestors[identity] = set(entry["supersedes"])
        retired.update(entry["supersedes"])
        for parent in entry["supersedes"]:
            ancestors[identity].update(ancestors[parent])
    groups = {}
    for identity, entry in claims.items():
        key = canonical({"scope": entry["scope"], "key": entry["key"]})
        groups.setdefault(key, []).append(identity)
    frontiers = []
    for ids in groups.values():
        if selected_ids is not None and not selected_ids.intersection(ids):
            continue
        frontier = []
        for identity in ids:
            current = tuple(claims[identity]["observed_time"][key] for key in ("revision", "turn"))
            for other in ids:
                if other == identity:
                    continue
                candidate = tuple(claims[other]["observed_time"][key] for key in ("revision", "turn"))
                comparable = all((left is None) == (right is None) for left, right in zip(candidate, current))
                later = (comparable and candidate != current
                    and all(left >= right for left, right in zip(candidate, current) if left is not None))
                if identity in ancestors[other] or other not in ancestors[identity] and later:
                    break
            else:
                frontier.append(identity)
        frontiers.append(frontier)
    return frontiers, retired


class CampaignMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, self.root / "sources", max_frames=128)
        self.ledger = MissionLedger(self.root / "mission", admission=admission(), now=1000)
        self.addCleanup(lambda: self.store.close())
        self.addCleanup(lambda: self.ledger.close())
        self.memory = CampaignMemory(self.ledger, self.store)
        self.serial = 0

    def source(self, revision=30, *, turn=4, session="native-session", menu=False, position=None, timestamp_ms=1_000_000):
        value = observation(revision, session=session, timestamp_ms=timestamp_ms)
        value["scene"]["turn"] = turn
        if position is not None:
            value["scene"]["position"] = position
        if menu:
            value.update(scene=None, category="UILIST", ui={"purpose": "UILIST", "title": "Alarm",
                "rows": [{"id": "row-1", "text": "8 hours", "enabled": True, "hotkey": "8"}],
                "selected": "row-1", "filter": None, "count": None, "coverage": "rendered_rows_only"})
            value["boundary"]["kind"] = "menu"
        (self.bridge / value["frame"]).write_bytes(png())
        return self.store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=timestamp_ms)

    def assertion(self, identity, reference, **changes):
        entry = claim(id=identity, schema=MEMORY_VERSION, scope={**scope(), "session": reference.session},
            observed_time={"revision": reference.revision, "turn": reference.turn},
            received_time=1_000_000, sources=[reference.observation_id],
            supports=[{"sources": [reference.observation_id], "claims": []}], status="current")
        entry.update(changes)
        return entry

    def remember(self, entry, *, correction=None, reason="Corrected visible interpretation"):
        self.serial += 1
        data = request("correct" if correction else "remember", schema=VERSION,
            request_id=f"memory-{self.serial}", epoch=self.ledger.snapshot(now=1000)["epoch"],
            entry_type="work" if entry["record_type"] == "Work" else "claim", entry=entry)
        if correction:
            data.update(retired_ids=correction, reason=reason)
        self.ledger.begin_request(data, now=1000)
        return self.memory.apply(data, now=1000)

    def context(self, query="water", **changes):
        values = dict(max_bytes=32768, now_monotonic=100, now_timestamp_ms=1_000_000)
        values.update(changes)
        return self.memory.context(scope(), query, **values)

    def work(self, reference, **changes):
        quantity = {"subject": "water", "quantity": 6, "unit": "charges", "coverage_id": "ground-prompt"}
        value = {"schema": MEMORY_VERSION, "record_type": "Work", "predecessor_work_id": None, "id": "water-craft",
            "intent": "Treat water and verify storage", "scope": scope(), "stage": "pending-storage",
            "progress": 59, "available": [], "committed": [], "predicted_output": [quantity],
            "observed_output": [], "unresolved_effects": [], "sources": [reference.observation_id],
            "next_verification": "Inspect ground output, then carried inventory separately", "status": "interrupted"}
        value.update(changes)
        return value

    def primitive(self, reference, *, state="unknown"):
        self.ledger.activate(epoch=0, player_id="player-test", now=1000)
        data = skill(schema=VERSION, sources=[reference.observation_id], expected_revision=reference.revision)
        self.ledger.begin_request(data, now=1000)
        self.ledger.prepare_primitive("request-1", "logical-1", intent(source_before=reference.observation_id,
            expected_revision=reference.revision), now=1000)
        self.ledger.published("logical-1", "native-1", now=1000)
        self.ledger.settle_primitive("logical-1", state, {"delivery": state}, now=1000)

    def test_reload_work_links_intent_without_inheriting_old_progress_stock_or_coordinates(self):
        before = self.source()
        old = self.work(before, available=[dict(subject="water", quantity=6, unit="charges", coverage_id="ground")])
        self.remember(old)
        after = self.source(1, session="reloaded")
        new = self.work(after, id="verify-reloaded-work", predecessor_work_id=old["id"],
                        scope={**scope(), "session": "reloaded", "coordinate_epoch": 1},
                        progress=None, predicted_output=[], status="planned", stage="verify")
        self.remember(new)
        packet = self.memory.context(new["scope"], "water", max_bytes=32768,
                                     now_monotonic=100, now_timestamp_ms=1_000_000)
        current = next(w for w in packet["work"] if w["id"] == new["id"])
        self.assertEqual(current["predecessor_work_id"], old["id"])
        self.assertEqual((current["available"], current["observed_output"], current["progress"]), ([], [], None))
        self.assertEqual(current["sources"], [after.observation_id])
        self.ledger.close(); self.ledger = MissionLedger(self.root / "mission", now=1000)
        retained = self.ledger.memory_records("work")[-1]["entry"]
        self.assertEqual(retained, new)

    def test_work_lineage_requires_existing_parent_and_immutable_scope_intent_and_link(self):
        ref = self.source()
        old = self.work(ref)
        with self.assertRaisesRegex(MemoryRequestRefusal, "predecessor must already exist"):
            self.remember({**old, "predecessor_work_id": "future"})
        with self.assertRaises(ContractError): self.remember({**old, "predecessor_work_id": old["id"]})
        self.remember(old)
        other = {**old, "id": "child", "predecessor_work_id": old["id"]}
        self.remember(other)
        for change in (dict(predecessor_work_id="child"), dict(intent="Other intent"),
                       dict(scope={**scope(), "coordinate_epoch": 2})):
            with self.subTest(change=change), self.assertRaises(ContractError): self.remember({**old, **change})
        with self.assertRaises(LedgerError):
            self.ledger.append_memory("bypass", "work", {**old, "predecessor_work_id": "child"}, now=1000)

    def test_reopen_rejects_tampered_work_lineage_without_restoring_authority(self):
        ref = self.source(); old = self.work(ref)
        self.remember(old)
        self.remember({**old, "stage": "next"})
        self.ledger.close()
        with closing(sqlite3.connect(self.ledger.path)) as db, db:
            row = db.execute("SELECT sequence,body FROM memory WHERE entry_type='work' ORDER BY sequence DESC LIMIT 1").fetchone()
            entry = json.loads(row[1]); entry["predecessor_work_id"] = "missing"
            db.execute("UPDATE memory SET body=? WHERE sequence=?", (canonical(entry), row[0]))
        with self.assertRaisesRegex(LedgerError, "immutable scope, intent and predecessor"):
            MissionLedger(self.root / "mission", now=1000)

    def test_delayed_older_frontier_precedes_query_and_receipt_order(self):
        old = self.source(30)
        new = self.source(31)
        self.remember(self.assertion("new", new, text="Visible empty stock", value={"quantity": 0, "state": None}))
        self.remember(self.assertion("old", old, text="Rare phrase twelve bottles", received_time=1_000_000))
        packet = self.context()
        self.assertEqual([c["id"] for c in packet["claims"]], ["new"])
        self.assertEqual(packet["claims"][0]["value"]["quantity"], 0)
        self.assertEqual(self.context("twelve bottles")["claims"], [])
        self.assertEqual(packet["omitted"]["claims"], 1)

    def test_equal_order_conflict_and_incomparable_order_remain_disputed(self):
        ref = self.source()
        self.remember(self.assertion("a", ref))
        self.remember(self.assertion("b", ref, value={"quantity": 2, "state": None}))
        packet = self.context()
        self.assertEqual({c["status"] for c in packet["claims"]}, {"disputed"})
        self.assertTrue(all(c["value"]["quantity"] is None for c in packet["claims"]))
        later = self.source(31, turn=3)
        self.remember(self.assertion("incomparable", later, value={"quantity": 3, "state": None}))
        self.assertEqual({c["status"] for c in self.context()["claims"]}, {"disputed"})

    def test_newest_loss_never_resurrects_old_stock_after_sqlite_reopen(self):
        old, new = self.source(30), self.source(31)
        self.remember(self.assertion("old", old))
        self.remember(self.assertion("new", new, value={"quantity": 1, "state": None}))
        Path(new.frame_path).unlink()
        packet = self.context()
        self.assertEqual([c["id"] for c in packet["claims"]], ["new"])
        self.assertEqual(packet["claims"][0]["status"], "unknown")
        self.assertIn("unavailable", packet["sources"][0]["status"])
        self.ledger.close(); self.store.close()
        self.ledger = MissionLedger(self.root / "mission", now=1000)
        self.store = EvidenceStore(self.bridge, self.root / "sources", max_frames=128)
        self.memory = CampaignMemory(self.ledger, self.store)
        packet = self.context()
        self.assertEqual([c["id"] for c in packet["claims"]], ["new"])
        self.assertIsNone(packet["claims"][0]["value"]["quantity"])
        self.assertFalse(self.ledger.snapshot(now=1000)["grants_authority"])

    def test_retired_frontier_does_not_revive_older_matching_text(self):
        old, new = self.source(30), self.source(31)
        self.remember(self.assertion("old", old))
        self.remember(self.assertion("new", new))
        replacement = self.assertion("correct", new, supersedes=["new"], status="unknown",
            value={"quantity": None, "state": None}, text="Number unreadable")
        self.remember(replacement, correction=["new"])
        packet = self.context()
        self.assertEqual([c["id"] for c in packet["claims"]], ["correct"])
        self.assertEqual(packet["claims"][0]["status"], "unknown")
        retained = self.ledger.request("memory-3")["request"]
        self.assertEqual(retained["retired_ids"], ["new"])
        self.assertEqual(retained["reason"], "Corrected visible interpretation")

    def test_conjunctive_derivation_invalidates_but_independent_group_survives(self):
        ref = self.source()
        for identity, subject in [("a", "heat"), ("b", "container")]:
            self.remember(self.assertion(identity, ref, key={**claim()["key"], "subject": subject}))
        for identity, groups in [("joint", [{"sources": [], "claims": ["a", "b"]}]),
                                 ("independent", [{"sources": [], "claims": ["a", "b"]},
                                                  {"sources": [ref.observation_id], "claims": []}])]:
            self.remember(self.assertion(identity, ref, key={**claim()["key"], "subject": identity}, supports=groups))
        self.remember(self.assertion("fix", ref, key={**claim()["key"], "subject": "heat"}, supersedes=["a"]), correction=["a"])
        packet = self.context()
        found = {c["id"]: c for c in packet["claims"]}
        self.assertEqual(found["joint"]["status"], "unknown")
        self.assertEqual(found["independent"]["status"], "current")
        self.assertEqual(found["a"]["status"], "retired")
        self.assertEqual(found["a"]["value"], {"quantity": None, "state": None})

    def test_missing_self_forward_and_correction_cycle_support_reject(self):
        ref = self.source()
        for identity in ("future", "a"):
            with self.subTest(identity=identity), self.assertRaises(ContractError):
                self.remember(self.assertion("a", ref, supports=[{"sources": [], "claims": [identity]}]))
        self.remember(self.assertion("a", ref))
        self.remember(self.assertion("b", ref, supports=[{"sources": [], "claims": ["a"]}]))
        with self.assertRaises(ContractError):
            self.remember(self.assertion("c", ref, supersedes=["a"], supports=[{"sources": [], "claims": ["b"]}]), correction=["a"])

    def test_durable_forward_or_cyclic_support_is_rejected_without_projection(self):
        ref = self.source()
        first = self.assertion("cycle-a", ref, supports=[{"sources": [], "claims": ["cycle-b"]}])
        second = self.assertion("cycle-b", ref, supports=[{"sources": [], "claims": ["cycle-a"]}])
        self.ledger.append_memory("untrusted-a", "claim", first, now=1000)
        self.ledger.append_memory("untrusted-b", "claim", second, now=1000)
        with self.assertRaises(ContractError): self.context()

    def test_selected_frontier_keeps_complete_groups_and_full_default(self):
        ref = self.source()
        identity_key = dict(subject="character", property="identity", unit="name", coverage_id="screen")
        entries = [self.assertion("parent", ref),
            self.assertion("identity", ref, key=identity_key, supports=[{"sources": [], "claims": ["parent"]}]),
            self.assertion("conflict", ref, key=identity_key, value=dict(quantity=None, state="Other")),
            self.assertion("other-coverage", ref, key={**identity_key, "coverage_id": "menu"})]
        claims = {entry["id"]: entry for entry in entries}
        full = CampaignMemory._frontier(claims)
        self.assertEqual(full, ([["parent"], ["identity", "conflict"], ["other-coverage"]], set()))
        self.assertEqual(CampaignMemory._frontier(claims, selected_ids={"identity"}),
            ([["identity", "conflict"]], set()))
        self.assertEqual(CampaignMemory._frontier(claims, selected_ids=set()), ([], set()))

    def test_selected_frontier_keeps_global_retirement_and_cross_type_ancestors(self):
        ref = self.source()
        identity_key = dict(subject="character", property="identity", unit="name", coverage_id="screen")
        for old_order, new_order in ((dict(revision=99, turn=99), dict(revision=1, turn=1)),
                                     (dict(revision=1, turn=99), dict(revision=99, turn=1))):
            with self.subTest(old_order=old_order, new_order=new_order):
                old = self.assertion("old-identity", ref, key=identity_key, observed_time=old_order)
                bridge = self.assertion("nonidentity", ref, supersedes=["old-identity"])
                claims = {entry["id"]: entry for entry in (old, bridge)}
                self.assertEqual(CampaignMemory._frontier(claims, selected_ids={"old-identity"}),
                    ([["old-identity"]], {"old-identity"}))
                new = self.assertion("new-identity", ref, key=identity_key,
                    observed_time=new_order, supersedes=["nonidentity"])
                claims[new["id"]] = new
                self.assertEqual(CampaignMemory._frontier(claims, selected_ids={"old-identity"}),
                    ([["new-identity"]], {"old-identity", "nonidentity"}))
                self.assertEqual(CampaignMemory._frontier(claims),
                    ([["new-identity"], ["nonidentity"]], {"old-identity", "nonidentity"}))

    def test_selected_frontier_skips_unselected_group_comparisons(self):
        ref = self.source()
        entries = [self.assertion("parent", ref), self.assertion("unrelated", ref),
            self.assertion("identity", ref,
                key=dict(subject="character", property="identity", unit="name", coverage_id="screen"))]
        claims = {entry["id"]: entry for entry in entries}
        with patch("harness.gameplay.campaign_memory._later", side_effect=AssertionError("Unselected comparison")):
            self.assertEqual(CampaignMemory._frontier(claims, selected_ids={"identity"}), ([["identity"]], set()))

    def test_clock_frontier_preserves_ties_reversals_masks_and_original_order(self):
        ref = self.source()
        clocks = [(8, 3), (7, 4), (9, 1), (8, 2), (8, 3), (6, 4), (5, 5), (4, 0),
                  (None, None), (None, None), (9, None), (9, None), (8, None),
                  (None, 5), (None, 4), (None, 5)]
        claims = {str(index): self.assertion(str(index), ref,
            observed_time=dict(revision=revision, turn=turn), value=dict(quantity=index, state=None))
            for index, (revision, turn) in enumerate(clocks)}
        expected = ([["0", "1", "2", "4", "6", "8", "9", "10", "11", "13", "15"]], set())
        self.assertEqual(reference_frontier(claims), expected)
        self.assertEqual(CampaignMemory._frontier(claims), expected)

    def test_frontier_matches_pairwise_reference_across_randomized_histories_and_selection(self):
        ref = self.source()
        for supersession in (False, True):
            for seed in range(24):
                rng = random.Random(seed)
                claims = {}
                for index in range(80):
                    identity = f"claim-{index}"
                    predecessors = list(claims)
                    entry = self.assertion(identity, ref,
                        key={**claim()["key"], "subject": "group-" + str(rng.randrange(5))},
                        observed_time={key: rng.choice([None, *range(6)]) for key in ("revision", "turn")},
                        value=dict(quantity=rng.randrange(4), state=None))
                    if predecessors and rng.randrange(4) == 0:
                        entry["supports"] = [{"sources": [], "claims": [rng.choice(predecessors)]}]
                    if supersession and predecessors and rng.randrange(4) == 0:
                        entry["supersedes"] = rng.sample(predecessors, min(len(predecessors), rng.randrange(1, 3)))
                    claims[identity] = entry
                before = deepcopy(claims)
                selections = (None, set(), set(claims), set(rng.sample(list(claims), 4)))
                for selected in selections:
                    with self.subTest(seed=seed, supersession=supersession, selected=selected):
                        self.assertEqual(CampaignMemory._frontier(claims, selected_ids=selected),
                            reference_frontier(claims, selected))
                self.assertEqual(claims, before)

    def test_no_supersession_frontier_eliminates_pairwise_clock_comparisons(self):
        ref = self.source()
        claims = {f"claim-{index}": self.assertion(f"claim-{index}", ref,
            key={**claim()["key"], "subject": "group-" + str(index % 3)},
            observed_time=dict(revision=index, turn=index)) for index in range(3201)}
        with patch("harness.gameplay.campaign_memory._later", side_effect=AssertionError("Pairwise frontier work")):
            self.assertEqual(CampaignMemory._frontier(claims),
                ([["claim-3198"], ["claim-3199"], ["claim-3200"]], set()))

    def test_selected_frontier_rejects_unrelated_invalid_dependency_graphs(self):
        ref = self.source()
        selected = self.assertion("identity", ref,
            key=dict(subject="character", property="identity", unit="name", coverage_id="screen"))
        for dependency in ("supports", "supersedes"):
            for parents in (("missing", None), ("bad-a", None), ("bad-b", None), ("bad-b", "bad-a")):
                with self.subTest(dependency=dependency, parents=parents):
                    bad = [self.assertion("bad-a", ref), self.assertion("bad-b", ref)]
                    for entry, parent in zip(bad, parents):
                        if parent is not None:
                            entry[dependency] = ([parent] if dependency == "supersedes" else
                                [{"sources": [], "claims": [parent]}])
                    claims = {entry["id"]: entry for entry in (selected, *bad)}
                    with self.assertRaisesRegex(ContractError, "missing/forward/cyclic"):
                        CampaignMemory._frontier(claims, selected_ids={"identity"})

    def test_frontier_dispute_and_supersession_invalidate_derived_support(self):
        first = self.source()
        self.remember(self.assertion("premise", first))
        self.remember(self.assertion("derived", first, key={**claim()["key"], "subject": "derived"},
            supports=[{"sources": [], "claims": ["premise"]}]))
        self.remember(self.assertion("conflict", first, value={"quantity": 0, "state": None}))
        packet = self.context("derived")
        self.assertEqual(next(c for c in packet["claims"] if c["id"] == "derived")["status"], "unknown")
        later = self.source(31)
        self.remember(self.assertion("new-frontier", later))
        packet = self.context("derived")
        self.assertEqual(next(c for c in packet["claims"] if c["id"] == "derived")["status"], "unknown")

    def test_repeated_citation_and_source_loss_preserve_independent_support_only(self):
        old = self.source()
        current = self.source(31)
        entry = self.assertion("independent", current, sources=[old.observation_id, current.observation_id],
            supports=[{"sources": [old.observation_id], "claims": []},
                      {"sources": [current.observation_id], "claims": []}])
        self.remember(entry)
        Path(old.frame_path).chmod(0o644)
        Path(old.frame_path).write_bytes(png(b"corrupt"))
        packet = self.context()
        self.assertEqual(packet["claims"][0]["status"], "current")
        self.assertEqual(packet["claims"][0]["value"]["quantity"], 18)
        self.assertTrue(any("unavailable" in s["status"] for s in packet["sources"]))
        # Repetition supplies no new independent group or confidence field.
        self.assertNotIn("confidence", canonical(packet))
        self.assertEqual(len(packet["claims"]), 1)

    def test_native_capture_literal_only_player_forgery_and_time_binding_reject(self):
        ref = self.source()
        result = self.memory.capture_native(ref, scope(), now=1000)
        self.assertEqual(len(result["entries"]), 3)
        self.assertEqual({e["kind"] for e in result["entries"]}, {"native_fact"})
        self.assertEqual({e["key"]["property"] for e in result["entries"]}, {"place"})
        again = self.memory.capture_native(ref, scope(), now=1000)
        self.assertEqual(again, result)
        with self.assertRaises(ContractError): self.remember(self.assertion("forged", ref, kind="native_fact"))
        with self.assertRaises(ContractError): self.remember(self.assertion("wrong-time", ref, observed_time={"revision": 29, "turn": 4}))
        with self.assertRaises(ContractError): self.remember(self.assertion("wrong-coverage", ref, scope={**scope(), "session": "other"}))
        menu = self.source(31, menu=True)
        menu_capture = self.memory.capture_native(menu, scope(), now=1000)
        self.assertEqual(menu_capture["entries"], [])
        self.assertEqual(menu_capture["memory_version"], result["memory_version"])
        with self.assertRaises(ContractError): self.remember(self.assertion("invented-turn", menu, observed_time={"revision": 31, "turn": 4}))

    def test_wall_assertion_receipt_and_monotonic_freshness_clocks_are_separate(self):
        wall_ms = 1_790_000_000_000
        wall = wall_ms / 1000
        self.ledger.close()
        self.ledger = MissionLedger(self.root / "wall-mission", admission=admission(), now=wall)
        self.memory = CampaignMemory(self.ledger, self.store)
        ref = self.source(timestamp_ms=wall_ms)
        entry = self.assertion("receipt", ref, received_time=wall_ms)
        data = request("remember", schema=VERSION, entry_type="claim", entry=entry)
        self.ledger.begin_request(data, now=wall)
        result = self.memory.apply(data, now=wall)
        self.assertEqual(result["entry"]["received_time"], wall_ms)
        captured = self.memory.capture_native(ref, scope(), now=wall + 1)
        self.assertTrue(all(e["received_time"] == wall_ms + 1000 for e in captured["entries"]))
        self.assertNotEqual(captured["entries"][0]["received_time"], ref.timestamp_ms)
        repeated = self.memory.capture_native(ref, scope(), now=wall + 2)
        self.assertEqual(captured, repeated)
        packet = self.memory.context(scope(), "water", max_bytes=32768,
            now_monotonic=101, now_timestamp_ms=wall_ms + 1000)
        self.assertEqual(packet["claims"][0]["status"], "current")
        future = self.assertion("future-receipt", ref, received_time=wall_ms + 10_000)
        data = request("remember", schema=VERSION, request_id="future", entry_type="claim", entry=future)
        self.ledger.begin_request(data, now=wall + 2)
        with self.assertRaises(ContractError): self.memory.apply(data, now=wall + 2)

    def test_old_scope_hints_and_coordinate_epochs_do_not_gain_current_authority(self):
        ref = self.source()
        self.remember(self.assertion("old-coordinates", ref, scope={**scope(), "coordinate_epoch": 1}))
        packet = self.context()
        self.assertEqual(packet["claims"][0]["status"], "last_seen")
        self.assertIn("alignment unproved", packet["dispositions"]["old-coordinates"][0])
        other = self.source(1, session="new-session")
        packet = self.memory.context({**scope(), "session": other.session}, "water", max_bytes=32768,
            now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertEqual(packet["claims"][0]["scope"]["session"], ref.session)
        self.assertEqual(packet["claims"][0]["status"], "last_seen")
        with self.assertRaises(ContractError):
            self.remember(self.assertion("aligned", other, supports=[{"sources": [], "claims": ["old-coordinates"]}]))

    def test_unknown_alarm_delivery_and_later_observation_never_rewrite_receipt(self):
        before = self.source(menu=True)
        self.remember(self.assertion("alarm", before, value={"quantity": 8, "state": None},
            key={"subject": "alarm", "property": "work", "unit": "requested-hours", "coverage_id": "alarm-row"},
            text="Rendered eight hour alarm selection"))
        self.primitive(before)
        packet = self.context("alarm")
        self.assertEqual(packet["claims"][0]["status"], "last_seen")
        after = self.source(31, turn=40)
        self.remember(self.assertion("needs", after, key={"subject": "thirst", "property": "need", "unit": "display", "coverage_id": "sidebar"},
            value={"quantity": None, "state": "Thirsty"}, text="Displayed thirst after waking"))
        self.assertEqual(self.context("thirst")["claims"][0]["status"], "current")
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "unknown")
        self.assertIsNone(self.ledger.primitive("logical-1")["effect"])

    def test_known_nondelivery_is_charged_but_does_not_invalidate_current_claim_or_work(self):
        ref = self.source()
        self.remember(self.assertion("carried-water", ref))
        self.remember(self.work(ref, status="active", stage="verify-stock"))
        self.primitive(ref, state="not_dispatched")
        packet = self.context()
        self.assertEqual(packet["claims"][0]["status"], "current")
        self.assertEqual(packet["work"][0]["status"], "active")
        self.assertEqual(packet["work"][0]["unresolved_effects"], [])
        self.assertEqual(self.ledger.snapshot(now=1000)["spent_inputs"], 1)
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "not_dispatched")
        self.assertFalse(packet["grants_authority"])
        # Nondelivery does not refresh an earlier observation or align new scope.
        self.source(31)
        stale = self.context()
        self.assertEqual(stale["claims"][0]["status"], "last_seen")
        self.assertEqual(stale["work"][0]["status"], "unknown")
        self.assertNotIn("potentially changed", str(stale["dispositions"]))

    def test_prepared_published_returned_and_unknown_still_invalidate_prior_memory(self):
        ref = self.source()
        entry = self.assertion("carried-water", ref)
        for state in ("prepared", "published", "returned", "unknown"):
            primitive = {"logical_id": "possibly-changed", "state": state,
                         "intent": {"expected_session": ref.session, "expected_revision": ref.revision}}
            with self.subTest(state=state):
                self.assertEqual(self.memory._effects(entry, {ref.observation_id: ref}, (primitive,)), ["possibly-changed"])

    def test_pending_water_progress_ground_output_and_carried_stock_are_distinct(self):
        before = self.source()
        first = self.work(before)
        self.remember(first)
        output = deepcopy(first)
        output["sources"] = [self.source(31).observation_id]
        output.update(stage="ground-output", progress=100, predicted_output=[], observed_output=first["predicted_output"])
        self.remember(output)
        self.remember(self.assertion("carried", before, value={"quantity": 18, "state": None}))
        packet = self.context()
        self.assertEqual(len(self.ledger.memory_records("work")), 2)
        self.assertEqual(packet["work"][0]["observed_output"][0]["quantity"], 6)
        self.assertEqual(packet["work"][0]["available"], [])
        self.assertEqual(packet["claims"][0]["value"]["quantity"], 18)
        self.primitive(self.store.historical_references[-1])
        packet = self.context()
        self.assertEqual(packet["work"][0]["status"], "unknown")
        self.assertEqual(packet["work"][0]["unresolved_effects"], ["logical-1"])
        self.assertEqual(packet["work"][0]["observed_output"][0]["quantity"], 6)
        self.assertEqual(packet["claims"][0]["status"], "last_seen")
        # A later display is not proof of original input delivery. It cannot
        # clear unknown custody or attribute aggregate stock to this craft.
        after = self.source(32)
        self.assertIsNotNone(after)
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "unknown")
        self.assertEqual(self.context()["work"][0]["unresolved_effects"], ["logical-1"])

    def test_stale_work_clears_available_and_completion_but_retains_historical_output(self):
        ref = self.source()
        quantity = self.work(ref)["predicted_output"]
        self.remember(self.work(ref, progress=100, stage="stored", status="completed",
            available=quantity, observed_output=quantity, predicted_output=[]))
        fresh = self.context()["work"][0]
        self.assertEqual(fresh["status"], "completed")
        self.assertEqual(fresh["available"], quantity)
        packet = self.context(now_monotonic=104, now_timestamp_ms=1_004_000)
        stale = packet["work"][0]
        self.assertEqual(stale["status"], "unknown")
        self.assertEqual(stale["available"], [])
        self.assertEqual(stale["progress"], 100)
        self.assertEqual(stale["observed_output"], quantity)
        self.assertIn("historical", " ".join(packet["dispositions"][stale["id"]]))
        self.assertTrue(packet["reobservations"])

    def test_reopened_work_has_no_current_availability_or_completion(self):
        ref = self.source()
        quantity = self.work(ref)["predicted_output"]
        self.remember(self.work(ref, progress=100, stage="stored", status="completed",
            available=quantity, observed_output=quantity, predicted_output=[]))
        self.ledger.close(); self.store.close()
        self.ledger = MissionLedger(self.root / "mission", now=1000)
        self.store = EvidenceStore(self.bridge, self.root / "sources", max_frames=128)
        self.memory = CampaignMemory(self.ledger, self.store)
        packet = self.context()
        reopened = packet["work"][0]
        self.assertEqual(reopened["status"], "unknown")
        self.assertEqual(reopened["available"], [])
        self.assertEqual(reopened["progress"], 100)
        self.assertEqual(reopened["observed_output"], quantity)
        self.assertIn("historical", " ".join(packet["dispositions"][reopened["id"]]))
        self.assertTrue(packet["reobservations"])
        self.assertEqual(self.ledger.memory_records("work")[0]["entry"]["status"], "completed")

    def test_delayed_completion_cannot_mix_with_newer_active_work(self):
        old, new = self.source(30), self.source(31)
        self.remember(self.work(new, progress=50, status="active", stage="crafting"))
        self.remember(self.work(old, progress=100, status="completed", stage="done",
            next_verification="Inspect storage before planning another batch"))
        current = self.context()["work"][0]
        self.assertEqual(current["progress"], 50)
        self.assertEqual(current["status"], "active")
        self.assertEqual(current["stage"], "crafting")
        self.assertEqual(current["next_verification"], "Inspect storage before planning another batch")
        self.remember(self.work(new, progress=50, status="completed", stage="done"))
        packet = self.context()
        self.assertEqual(packet["work"][0]["status"], "unknown")
        self.assertEqual(packet["work"][0]["stage"], "unknown")
        self.assertTrue(packet["reobservations"])

    def test_source_free_plan_remains_advisory_when_no_current_source_exists(self):
        ref = self.source()
        self.remember(self.work(ref, sources=[], progress=None, status="planned", stage="plan"))
        packet = self.context(now_monotonic=104, now_timestamp_ms=1_004_000)
        self.assertEqual(packet["work"][0]["status"], "planned")
        self.assertEqual(packet["work"][0]["available"], [])
        self.assertEqual(packet["work"][0]["observed_output"], [])
        self.assertFalse(packet["grants_authority"])

    def test_delayed_work_quantities_keep_source_frontier_and_equal_conflicts_unknown(self):
        old, new = self.source(30), self.source(31)
        newest = self.work(new, progress=59, stage="current-reading")
        self.remember(newest)
        delayed = self.work(old, progress=0, stage="plan-to-verify")
        self.remember(delayed)
        packet = self.context()
        self.assertEqual(packet["work"][0]["progress"], 59)
        self.assertEqual(packet["work"][0]["stage"], "current-reading")
        conflict = self.work(new, progress=24)
        self.remember(conflict)
        packet = self.context()
        self.assertEqual(packet["work"][0]["status"], "unknown")
        self.assertIsNone(packet["work"][0]["progress"])
        self.assertTrue(packet["reobservations"])
        self.assertEqual(len(self.ledger.memory_records("work")), 3)

    def test_exact_admitted_payload_and_outer_correction_fields_required(self):
        ref = self.source()
        entry = self.assertion("a", ref)
        data = request("remember", schema=VERSION, entry_type="claim", entry=entry)
        with self.assertRaises(ContractError): self.memory.apply(data, now=1000)
        self.ledger.begin_request(data, now=1000)
        changed = deepcopy(data); changed["entry"]["text"] = "Changed after admission"
        with self.assertRaises(ContractError): self.memory.apply(changed, now=1000)
        result = self.memory.apply(data, now=1000)
        result["entry"]["value"]["quantity"] = 999
        self.assertEqual(self.memory.apply(data, now=1000)["entry"]["value"]["quantity"], 18)
        with self.assertRaises(ContractError): self.remember(self.assertion("b", ref, supersedes=["a"]))
        with self.assertRaises(ContractError): self.remember(self.assertion("c", ref), correction=["a"])
        with self.assertRaises(ContractError): self.remember(self.assertion("d", ref, supersedes=["missing"]), correction=["missing"])

    def test_bounded_deterministic_packets_complete_closures_and_copied_results(self):
        ref = self.source()
        for i in range(40):
            self.remember(self.assertion(f"c-{i:02}", ref, key={**claim()["key"], "subject": f"water-{i:02}"}))
        packet = self.context()
        self.assertEqual(len(packet["claims"]), 32)
        self.assertEqual(packet["omitted"]["claims"], 8)
        self.assertLessEqual(len(canonical(packet).encode()), 32768)
        self.assertEqual(packet, self.context())
        packet["claims"][0]["value"]["quantity"] = 999
        self.assertEqual(self.context()["claims"][0]["value"]["quantity"], 18)
        bounded = self.context(max_bytes=2048)
        self.assertLessEqual(len(canonical(bounded).encode()), 2048)
        self.assertGreater(bounded["omitted"]["claims"], 8)
        with self.assertRaises(CapacityError): self.context(max_bytes=512)
        with self.assertRaises(ContractError): self.context(max_bytes=32769)
        self.assertEqual(packet["schema"], MEMORY_VERSION)
        self.assertFalse(packet["grants_authority"])
        for item in self.context()["claims"]:
            validate_memory_entry(item, "claim")

    def test_work_bound_and_distinct_visible_coverage_do_not_merge_stock(self):
        ref = self.source()
        for i in range(17):
            self.remember(self.work(ref, id=f"work-{i:02}"))
        for identity, quantity, coverage in [("ground", 6, "ground-prompt"), ("carried", 18, "consume-page")]:
            self.remember(self.assertion(identity, ref, key={**claim()["key"], "coverage_id": coverage},
                value={"quantity": quantity, "state": None}))
        packet = self.context()
        self.assertEqual(len(packet["work"]), 16)
        self.assertEqual(packet["omitted"]["work"], 1)
        self.assertEqual({c["key"]["coverage_id"]: c["value"]["quantity"] for c in packet["claims"]},
            {"ground-prompt": 6, "consume-page": 18})
        self.assertLessEqual(len(canonical(packet).encode()), 32768)
        for work in packet["work"]:
            validate_work_view(work)

    def test_valid_eight_source_update_retains_nine_source_coherent_view(self):
        first = self.source(30)
        self.remember(self.work(first))
        menus = [self.source(31+i, menu=True) for i in range(8)]
        updated = self.work(menus[-1], sources=[ref.observation_id for ref in menus], progress=80)
        self.remember(updated)
        expected = {first.observation_id, *(ref.observation_id for ref in menus)}
        packet = self.context()
        view = packet["work"][0]
        self.assertEqual(view["record_type"], "WorkView")
        self.assertEqual(set(view["sources"]), expected)
        self.assertEqual(view["status"], "unknown")
        self.assertIsNone(view["progress"])
        self.assertEqual(validate_work_view(view), view)
        with self.assertRaises(ContractError):
            validate_memory_entry({**view, "record_type": "Work"}, "work")
        complete = self.context("irrelevant", required_work_ids=frozenset([view["id"]]))
        self.assertEqual(set(complete["work"][0]["sources"]), expected)
        self.assertEqual({ref["id"] for ref in complete["sources"]}, expected)
        self.assertEqual(complete["omitted"]["work"], 0)
        self.assertEqual(complete["claims"], [])
        with self.assertRaises(CapacityError):
            self.context("irrelevant", required_work_ids=frozenset([view["id"]]),
                         max_bytes=len(canonical(complete).encode())-1)
        Path(first.frame_path).unlink()
        missing = self.context("irrelevant", required_work_ids=frozenset([view["id"]]))
        self.assertEqual(set(missing["work"][0]["sources"]), expected)
        self.assertEqual(missing["work"][0]["status"], "unknown")
        self.assertEqual(missing["work"][0]["observed_output"], [])
        self.assertNotEqual(next(s for s in missing["sources"] if s["id"]==first.observation_id)["status"], "retained")

    def test_complete_work_context_and_decision_can_retain_more_than_sixteen_premises(self):
        first = self.source(30)
        self.remember(self.work(first))
        expected = {first.observation_id}
        for group in range(2):
            refs = [self.source(31+group*8+i, turn=5+group, menu=i!=0) for i in range(8)]
            expected.update(ref.observation_id for ref in refs)
            self.remember(self.work(refs[-1], sources=[r.observation_id for r in refs]))
        self.assertEqual(len(expected), 17)
        ordinary = self.context()
        self.assertEqual(ordinary["work"], [])
        self.assertEqual(ordinary["omitted"]["reasons"]["work/source limit"], 1)
        packet = self.context("replace context", required_work_ids=frozenset(["water-craft"]), max_bytes=131072)
        self.assertEqual(set(packet["work"][0]["sources"]), expected)
        self.assertEqual(packet["work"][0]["status"], "unknown")
        decision = dict(schema=MEMORY_VERSION, record_type="Decision", id="large-closure-decision",
            packet_id=packet["packet_id"], scope=scope(), query=packet["query"], memory_version=packet["memory_version"],
            claim_ids=[], work_ids=["water-craft"], source_ids=sorted(expected), procedure_refs=[], procedure_sources=[],
            omitted=packet["omitted"]["claims"]+packet["omitted"]["work"], reason="Retain every premise before replanning")
        self.assertEqual(self.memory.record_decision(decision, now=1000)["entry"], decision)

    def test_source_checks_are_bounded_and_dependency_closure_cannot_disappear(self):
        refs = [self.source(i + 1) for i in range(20)]
        for i, ref in enumerate(refs):
            self.remember(self.assertion(f"c-{i:02}", ref, key={**claim()["key"], "subject": f"water-{i:02}"}))
        original = self.store.source_status
        with patch.object(self.store, "source_status", wraps=original) as status:
            packet = self.context()
        # inspect_current verifies one source; cached selection never hashes it again.
        self.assertLessEqual(status.call_count, 15)
        self.assertLessEqual(len(packet["sources"]), 16)
        self.assertGreater(packet["omitted"]["bounds"], 0)
        # A dependency closure above 32 claims is omitted whole.
        self.remember(self.assertion("root", refs[-1], key={**claim()["key"], "subject": "closure"}))
        previous = "root"
        for i in range(33):
            identity = f"chain-{i}"
            self.remember(self.assertion(identity, refs[-1], text="uniquefinal" if i == 32 else "premise",
                key={**claim()["key"], "subject": identity}, supports=[{"sources": [], "claims": [previous]}]))
            previous = identity
        packet = self.context("uniquefinal")
        self.assertEqual(packet["claims"], [])
        self.assertTrue(packet["reobservations"])

    def test_decisions_bind_issued_packet_and_actual_selection_closure(self):
        ref = self.source()
        self.remember(self.assertion("a", ref))
        self.remember(self.assertion("b", ref, key={**claim()["key"], "subject": "derived"}, supports=[{"sources": [], "claims": ["a"]}]))
        packet = self.context()
        entry = {"schema": MEMORY_VERSION, "record_type": "Decision", "id": "choice", "scope": scope(),
            "packet_id": packet["packet_id"], "query": packet["query"], "memory_version": packet["memory_version"],
            "claim_ids": [c["id"] for c in packet["claims"]], "work_ids": [],
            "source_ids": [s["id"] for s in packet["sources"]], "procedure_refs": [], "procedure_sources": [],
            "omitted": packet["omitted"]["claims"] + packet["omitted"]["work"], "reason": "Check carried water"}
        for changes in [{"packet_id": "unissued-packet"}, {"memory_version": 999}, {"source_ids": []}, {"claim_ids": ["b"]}, {"procedure_refs": ["new-policy"]}]:
            with self.assertRaises(ContractError): self.memory.record_decision({**entry, **changes}, now=1000)
        result = self.memory.record_decision(entry, now=1000)
        self.assertEqual(result["packet_id"], packet["packet_id"])
        self.assertEqual(self.ledger.memory_records("decision")[0]["entry"], entry)
        self.memory = CampaignMemory(self.ledger, self.store)
        with self.assertRaises(ContractError): self.memory.record_decision({**entry, "id": "after-restart"}, now=1000)

    def test_passive_module_has_no_input_or_process_authority(self):
        import harness.gameplay.campaign_memory as module
        text = inspect.getsource(module)
        for forbidden in ("import subprocess", "import requests", "import controller", "import runtime", "import http", "import openai"):
            self.assertNotIn(forbidden, text)
        before = self.ledger.snapshot(now=1000)
        self.context()
        after = self.ledger.snapshot(now=1000)
        self.assertEqual(before, after)
        self.assertEqual(self.ledger.primitive_records(), ())


if __name__ == "__main__":
    unittest.main()
