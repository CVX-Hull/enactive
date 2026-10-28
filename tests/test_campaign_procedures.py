"""Player-authored data over synthetic retained episodes, not real learning."""

from harness.gameplay.mission_memory import MissionMemory
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness.gameplay.campaign_memory import CampaignMemory
from harness.gameplay.contracts import ContractError
from harness.gameplay.evidence import CapacityError, EvidenceError, EvidenceStore
from harness.gameplay.mission_contracts import LearningPolicy
from harness.gameplay.memory_contracts import MEMORY_VERSION
from harness.gameplay.mission_ledger import MissionLedger
from tests.test_gameplay_evidence import observation, png
from tests.test_mission_contracts import admission, claim, request, scope, skill
from tests.test_mission_ledger import intent
from tests.test_procedures import procedure, successor


class CampaignProcedureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.bridge = root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, root / "evidence")
        self.addCleanup(self.store.close)
        self.policy = LearningPolicy(procedure()["environment"])
        self.admission = admission(learning=self.policy)
        self.ledger = MissionLedger(root / "mission", admission=self.admission, now=1000)
        self.addCleanup(self.ledger.close)
        self.memory = CampaignMemory(MissionMemory(self.ledger), self.store)

    def episode(self, number=30):
        value = observation(number, session="native-session")
        (self.bridge / value["frame"]).write_bytes(png(str(number).encode()))
        ref = self.store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
        identity = f"observe-{number}"
        data = request("observe", request_id=identity)
        self.ledger.begin_request(data, now=1000)
        self.ledger.complete_request(identity, "completed", {"source_ids": [ref.observation_id],
            "grants_authority": False}, now=1000)
        return dict(mission_id=self.admission.mission_id, request_ids=[identity],
                    source_ids=[ref.observation_id], interpretation="Scoped observed water interaction")

    def remember(self, entry):
        data = request("remember", request_id="remember-" + entry["id"], entry_type="procedure", entry=entry,
                       epoch=self.ledger.snapshot(now=1000)["epoch"])
        self.ledger.begin_request(data, now=1000)
        result = self.memory.apply(data, now=1000)
        self.ledger.complete_request(data["request_id"], "completed", result, now=1000)
        return result

    def context(self, **changes):
        values = dict(max_bytes=32768, now_monotonic=100, now_timestamp_ms=1_000_000)
        return self.memory.context(scope(), "water", **(values | changes))

    def test_historical_program_selection_refuses_before_support_reads_or_primitives(self):
        from types import SimpleNamespace
        from tests.test_procedures import historical
        old = historical(procedure(status="active", program={"language": "javascript/1", "source": "old code"}))
        read = unittest.mock.Mock(side_effect=AssertionError("Historical execution must refuse before source reads"))
        self.memory.library = SimpleNamespace(records=lambda: (old,), source=read)
        with self.assertRaises(ContractError):
            self.memory.select_procedure({"mission_id": old["mission_id"], "revision_id": old["id"]})
        read.assert_not_called()
        self.assertEqual(self.ledger.primitive_records(), ())

    def test_oversized_procedure_closure_is_omitted_before_reading_support_images(self):
        episodes = [self.episode(number) for number in range(30, 47)]
        first = procedure(mission_id=self.admission.mission_id, support=episodes[:8])
        self.remember(first)
        second = successor(first, support=episodes[8:16])
        self.remember(second)
        self.remember(successor(second, support=episodes[16:]))
        with patch.object(self.store, "_frame_bytes", wraps=self.store._frame_bytes) as reads:
            packet = self.context()
        self.assertEqual(packet["procedures"], [])
        self.assertEqual(packet["omitted"]["reasons"]["procedure/source limit"], 1)
        self.assertEqual([call.args[0].observation_id for call in reads.call_args_list],
                         episodes[-1]["source_ids"])
        with patch.object(self.store, "_frame_bytes", wraps=self.store._frame_bytes) as reads:
            complete = self.context(required_work_ids=frozenset(), max_bytes=131072)
        self.assertEqual(len(complete["procedures"]), 1)
        self.assertEqual(len(complete["procedure_sources"]), 17)
        self.assertCountEqual([call.args[0].observation_id for call in reads.call_args_list],
                              [episode["source_ids"][0] for episode in episodes])
        with self.assertRaisesRegex(CapacityError, "packet byte limit; no omission"):
            self.context(required_work_ids=frozenset(), max_bytes=1024)

    def test_overlapping_procedures_and_claim_sources_share_image_checks(self):
        episodes = [self.episode(number) for number in range(30, 33)]
        for index, support in enumerate((episodes[:2], episodes[1:])):
            self.remember(procedure(id=f"revision-{index}", procedure_id=f"water-{index}",
                mission_id=self.admission.mission_id, support=support))
        ref = self.store.historical_references[0]
        entry = claim(sources=[ref.observation_id],
            supports=[{"sources": [ref.observation_id], "claims": []}],
            observed_time={"revision": ref.revision, "turn": ref.turn})
        data = request("remember", request_id="remember-claim", entry_type="claim", entry=entry)
        self.ledger.begin_request(data, now=1000)
        self.memory.apply(data, now=1000)
        with patch.object(self.store, "_frame_bytes", wraps=self.store._frame_bytes) as reads:
            packet = self.context()
        self.assertEqual(len(packet["procedures"]), 2)
        self.assertEqual(len(packet["claims"]), 1)
        self.assertCountEqual([call.args[0].observation_id for call in reads.call_args_list],
                              [episode["source_ids"][0] for episode in episodes])

    def test_procedure_checks_count_candidates_omitted_for_packet_bytes(self):
        episodes = [self.episode(number) for number in range(30, 47)]
        for index in range(3):
            support = episodes[index * 8:(index + 1) * 8]
            self.remember(procedure(id=f"revision-{index}", procedure_id=f"water-{index}",
                mission_id=self.admission.mission_id, support=support))
        with patch.object(self.store, "_frame_bytes", wraps=self.store._frame_bytes) as reads:
            packet = self.context(max_bytes=1024)
        self.assertEqual(packet["procedures"], [])
        self.assertEqual(packet["omitted"]["reasons"]["procedure/source limit"], 1)
        self.assertEqual(packet["omitted"]["reasons"]["procedure packet byte limit"], 2)
        self.assertLessEqual(reads.call_count, 16)

    def test_corrupt_selected_support_fails_selection_and_complete_context(self):
        episode = self.episode()
        entry = procedure(mission_id=self.admission.mission_id, support=[episode])
        self.remember(entry)
        packet = self.context()
        decision = dict(schema=MEMORY_VERSION, record_type="Decision", id="corrupt-decision",
            packet_id=packet["packet_id"], scope=scope(), query=packet["query"],
            memory_version=packet["memory_version"], claim_ids=[], work_ids=[], source_ids=[],
            procedure_refs=packet["procedure_refs"], procedure_sources=packet["procedure_sources"],
            omitted=0, reason="Try the supported procedure")
        retained = Path(self.store.historical_references[0].frame_path)
        retained.chmod(0o644)
        retained.write_bytes(png(b"corrupt"))
        selection = dict(mission_id=entry["mission_id"], revision_id=entry["id"],
                         use_id="corrupt-use", applicability="Visible water")
        with self.assertRaises(EvidenceError):
            self.memory.select_procedure(selection)
        with self.assertRaises(EvidenceError):
            self.memory.record_decision(decision, now=1000)
        self.assertEqual(self.context()["procedures"], [])
        with self.assertRaisesRegex(CapacityError, "unavailable support"):
            self.context(required_work_ids=frozenset())

    def test_admission_is_immutable_and_missing_current_learning_field_rejects(self):
        raw = self.admission.to_dict()
        raw["learning"]["environment"]["configuration"] = "changed"
        self.assertNotEqual(dict(self.policy.environment)["configuration"], "changed")
        self.assertEqual(type(self.admission).from_dict(self.admission.to_dict()), self.admission)
        raw = self.admission.to_dict()
        raw.pop("learning")
        with self.assertRaises(ContractError):
            type(self.admission).from_dict(raw)

    def test_procedure_retrieval_decision_and_counterexample_revision(self):
        first = procedure(mission_id=self.admission.mission_id, support=[self.episode()])
        self.remember(first)
        chosen = dict(mission_id=first["mission_id"], revision_id=first["id"], use_id="use-1",
                      applicability="Currently visible ordinary water context")
        self.assertEqual(self.memory.select_procedure(chosen), first)
        packet = self.context()
        self.assertEqual(packet["procedures"], [first])
        decision = dict(schema=MEMORY_VERSION, record_type="Decision", id="chosen-procedure", packet_id=packet["packet_id"],
            scope=scope(), query=packet["query"], memory_version=packet["memory_version"], claim_ids=[], work_ids=[],
            source_ids=[], procedure_refs=packet["procedure_refs"], procedure_sources=packet["procedure_sources"],
            omitted=0, reason="Scoped candidate trial")
        with self.assertRaises(ContractError):
            self.memory.record_decision(decision | dict(procedure_sources=[]), now=1000)
        self.memory.record_decision(decision, now=1000)
        second = successor(first, support=first["support"], counterexamples=[self.episode(31)], status="disputed",
                           invalidators=["Changed observed water control"], reason="Counterexample requires revised scope")
        self.remember(second)
        self.assertEqual(self.context()["procedures"], [second])
        with self.assertRaises(ContractError):
            self.memory.select_procedure(chosen)
        with self.assertRaises(ContractError):
            self.memory.select_procedure(chosen | dict(revision_id=second["id"]))

    def test_missing_or_unrelated_episode_support_cannot_be_promoted(self):
        episode = self.episode()
        other = self.episode(31)
        entry = procedure(mission_id=self.admission.mission_id,
                          support=[episode | dict(source_ids=other["source_ids"])])
        data = request("remember", entry_type="procedure", entry=entry)
        self.ledger.begin_request(data, now=1000)
        with self.assertRaisesRegex(ContractError, "unrelated"):
            self.memory.apply(data, now=1000)
        self.assertEqual(self.ledger.memory_records("procedure"), ())

    def test_unresolved_original_input_cannot_support_adoption_or_selection(self):
        episode = self.episode()
        identity = episode["source_ids"][0]
        self.ledger.activate(epoch=0, player_id="player-test", now=1000)
        attempted = skill(request_id="uncertain-step", sources=[identity])
        self.ledger.begin_request(attempted, now=1000)
        self.ledger.prepare_primitive(attempted["request_id"], "unknown-input",
            intent(source_before=identity, preflight_source=identity), now=1000)
        self.ledger.settle_primitive("unknown-input", "unknown", {"reason": "Reply lost"}, now=1000)
        self.ledger.complete_request(attempted["request_id"], "unknown", {"source_ids": [identity]}, now=1000)
        entry = procedure(mission_id=self.admission.mission_id,
            support=[episode | dict(request_ids=[attempted["request_id"]])])
        with self.assertRaisesRegex(ContractError, "unresolved"):
            self.remember(entry)
        self.assertEqual(self.ledger.memory_records("procedure"), ())
        # Low-level typed storage is not semantic acceptance; retrieval rechecks it.
        self.ledger.append_memory("storage-probe", "procedure", entry, now=1000)
        with self.assertRaisesRegex(ContractError, "unresolved"):
            self.memory.select_procedure(dict(mission_id=entry["mission_id"], revision_id=entry["id"],
                use_id="unsafe-use", applicability="Unproved effect"))

    def test_reopen_preserves_procedure_head_and_conflicting_branch_refuses(self):
        first = procedure(mission_id=self.admission.mission_id, support=[self.episode()])
        self.remember(first)
        second = successor(first, support=first["support"], status="active")
        self.remember(second)
        sibling = successor(first, support=first["support"], id="conflicting-revision")
        with self.assertRaisesRegex(ContractError, "branch|heads"):
            self.remember(sibling)
        directory = self.ledger.directory
        self.ledger.close()
        self.ledger = MissionLedger(directory, now=1000)
        self.addCleanup(self.ledger.close)
        self.memory = CampaignMemory(MissionMemory(self.ledger), self.store)
        self.assertEqual(self.context()["procedures"], [second])
