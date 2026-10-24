"""Memory refusal boundaries over the real writer and synthetic transport only."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import time
import sqlite3
from unittest.mock import patch

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.evidence import CapacityError
import unittest

from harness.gameplay.mission_contracts import LearningPolicy
from tests import test_mission_runtime as fixture
from tests.test_mission_contracts import claim
from tests.test_procedures import procedure, successor


class MemoryRequestRefusalTests(unittest.TestCase):
    @contextmanager
    def running(self):
        case = fixture.MissionRuntimeTests()
        case.setUp()
        case.a = replace(case.a, learning=LearningPolicy(procedure()["environment"]))
        try:
            case.start()
            yield case
        finally:
            case.doCleanups()

    def assertion(self, case, **changes):
        source = case.runtime.status()["current_source"]
        return claim(scope=dict(mission_id=case.a.mission_id, session=source["session"], coordinate_epoch=0),
            observed_time={"revision": source["revision"], "turn": source["turn"]},
            received_time=int(time.time() * 1000), sources=[source["observation_id"]],
            supports=[dict(sources=[source["observation_id"]], claims=[])], **changes)

    def candidate(self, case, scenario):
        assertion = self.assertion(case)
        source = assertion["sources"][0]
        episode = dict(mission_id=case.a.mission_id, request_ids=["start-1"], source_ids=[source],
                       interpretation="Synthetic retained original episode")
        proc = procedure(mission_id=case.a.mission_id, support=[episode])
        good = dict(entry_type="claim", entry=assertion)
        bad = deepcopy(good)
        if scenario in ("missing-request", "unrelated-source", "missing-parent"):
            good = dict(entry_type="procedure", entry=proc)
            bad = deepcopy(good)
            if scenario == "missing-request":
                bad["entry"]["counterexamples"] = [episode | dict(request_ids=["op-7989e83de0934cf48b9e28bd420001ee"])]
            elif scenario == "unrelated-source":
                bad["entry"]["support"][0]["source_ids"] = ["uncited-source"]
            else:
                bad["entry"] = successor(proc, support=[episode])
        elif scenario == "work-predecessor":
            work = dict(schema="campaign-memory/6", record_type="Work", id="work-1", predecessor_work_id=None,
                intent="Inspect water", scope=assertion["scope"], stage="plan", progress=None,
                available=[], committed=[], predicted_output=[], observed_output=[], unresolved_effects=[],
                sources=[], next_verification="Inspect visible water", status="planned")
            good = dict(entry_type="work", entry=work)
            bad = dict(entry_type="work", entry=work | dict(predecessor_work_id="missing-work"))
        elif scenario in ("duplicate", "correction", "claim-support"):
            seed = case.request("remember", request_id="seed", **good)
            self.assertEqual(case.runtime.command(seed)["status"], "accepted")
            self.assertEqual(case.settled("seed")["state"], "completed")
            good = dict(entry_type="claim", entry=assertion | dict(id="new-claim"))
            if scenario == "correction":
                good.update(entry=good["entry"] | dict(supersedes=[assertion["id"]]), retired_ids=[assertion["id"]], reason="Correct count")
                bad = deepcopy(good)
                bad["retired_ids"] = ["missing-claim"]
                bad["entry"]["supersedes"] = ["missing-claim"]
            elif scenario == "claim-support":
                bad = dict(entry_type="claim", entry=good["entry"] | dict(supports=[dict(sources=[], claims=["missing-claim"])]))
        elif scenario == "decision":
            output = case.runtime.command(dict(schema="mission/11", kind="context", handoff=None,
                mission_id=case.a.mission_id, scope=assertion["scope"], query="water", max_bytes=32768))
            packet = output["context"]["packet"]
            decision = dict(schema="campaign-memory/6", record_type="Decision", id="decision-1",
                packet_id=packet["packet_id"], scope=packet["scope"], query=packet["query"],
                memory_version=packet["memory_version"], claim_ids=[], work_ids=[], source_ids=[],
                procedure_refs=[], procedure_sources=[], omitted=sum(packet["omitted"][key] for key in ("claims", "work", "procedures")),
                reason="Inspect visible water")
            good = dict(entry_type="decision", entry=decision)
            bad = dict(entry_type="decision", entry=decision | dict(packet_id="unissued"))
        return bad, good

    def memory_rows(self, case):
        return {kind: case.runtime._ledger.memory_records(kind) for kind in ("claim", "work", "decision", "procedure")}

    def test_new_candidate_refusals_keep_healthy_scope_and_allow_distinct_correction(self):
        for scenario in ("missing-request", "unrelated-source", "missing-parent", "work-predecessor", "duplicate", "correction", "claim-support", "decision"):
            with self.subTest(scenario=scenario), self.running() as case:
                bad, good = self.candidate(case, scenario)
                before = case.runtime.status()
                rows = self.memory_rows(case)
                primitives = case.runtime._ledger.primitive_records()
                bindings = dict(case.runtime._bindings)
                lease = case.runtime._lease
                generation = case.runtime._store.authority_generation()
                delivered = deepcopy(case.bridge.delivered)
                kind = "correct" if scenario == "correction" else "remember"
                request = case.request(kind, request_id="bad-memory", **bad)
                self.assertEqual(case.runtime.command(request)["status"], "accepted")
                operation = case.settled("bad-memory")
                self.assertEqual(operation["state"], "blocked", operation)
                self.assertIn("MemoryRequestRefusal", operation["result"]["reason"])
                self.assertFalse(operation["result"]["grants_authority"])
                self.assertEqual(self.memory_rows(case), rows)
                self.assertEqual(case.runtime._ledger.primitive_records(), primitives)
                self.assertEqual(case.bridge.delivered, delivered)
                self.assertIs(case.runtime._lease, lease)
                self.assertIs(case.controller._mission_lease, lease)
                self.assertEqual(case.runtime._bindings, bindings)
                self.assertEqual(case.runtime._store.authority_generation(), generation)
                after = case.runtime.status()
                for key in ("phase", "epoch", "spent_inputs", "current_source"):
                    self.assertEqual(after[key], before[key], key)
                self.assertEqual(case.runtime.command(request)["operation"], operation)
                conflict = deepcopy(request)
                conflict["entry"]["reason" if bad["entry_type"] in ("procedure", "decision") else "intent" if bad["entry_type"] == "work" else "text"] = "Changed identity payload"
                self.assertEqual(case.runtime.command(conflict)["status"], "rejected")
                self.assertEqual(case.result("bad-memory"), operation)
                corrected = case.request(kind, request_id="corrected-memory", **good)
                self.assertEqual(case.runtime.command(corrected)["status"], "accepted")
                self.assertEqual(case.settled("corrected-memory")["state"], "completed")
                self.assertIs(case.runtime._lease, lease)
                navigation = case.navigation(request_id="ordinary-next-intent")
                self.assertEqual(case.runtime.command(navigation)["status"], "accepted")
                self.assertEqual(case.settled(navigation["request_id"])["state"], "completed")

    def test_procedure_selection_refuses_only_new_caller_choice_not_retained_faults(self):
        for scenario in ("missing-selection", "corrupt-support"):
            with self.subTest(scenario=scenario), self.running() as case:
                _, good = self.candidate(case, "missing-request")
                seed = case.request("remember", request_id="seed-procedure", **good)
                self.assertEqual(case.runtime.command(seed)["status"], "accepted")
                self.assertEqual(case.settled(seed["request_id"])["state"], "completed")
                selection = dict(mission_id=case.a.mission_id,
                    revision_id=good["entry"]["id"], use_id="selected-use",
                    applicability="Synthetic current visible route")
                navigation = case.navigation(request_id="selected-navigation", procedure=selection)
                lease = case.runtime._lease
                rows = self.memory_rows(case)
                if scenario == "missing-selection":
                    navigation["procedure"] = selection | dict(revision_id="missing-revision")
                else:
                    source = case.runtime.status()["current_source"]
                    Path(source["frame_path"]).chmod(0o600)
                    Path(source["frame_path"]).write_bytes(b"corrupt retained bytes")
                self.assertEqual(case.runtime.command(navigation)["status"], "accepted")
                operation = case.settled(navigation["request_id"])
                self.assertEqual(operation["state"], "blocked", operation)
                self.assertEqual(self.memory_rows(case), rows)
                self.assertEqual(case.runtime._ledger.primitive_records(), ())
                if scenario == "missing-selection":
                    self.assertIn("Procedure selection refused before input", operation["result"]["reason"])
                    self.assertIs(case.runtime._lease, lease)
                    corrected = case.navigation(request_id="corrected-selection",
                        procedure=selection | dict(use_id="corrected-use"))
                    self.assertEqual(case.runtime.command(corrected)["status"], "accepted")
                    self.assertEqual(case.settled(corrected["request_id"])["state"], "completed")
                else:
                    self.assertIn("EvidenceError", operation["result"]["reason"])
                    self.assertIsNone(case.runtime._lease)
                    self.assertNotEqual(case.runtime.status()["phase"], "active")

    def test_actual_retained_procedure_bytes_failure_stops_instead_of_refusing_candidate(self):
        with self.running() as case:
            _, good = self.candidate(case, "missing-request")
            source = case.runtime.status()["current_source"]
            Path(source["frame_path"]).chmod(0o600)
            Path(source["frame_path"]).write_bytes(b"corrupt retained bytes")
            request = case.request("remember", request_id="corrupt-memory", **good)
            self.assertEqual(case.runtime.command(request)["status"], "accepted")
            operation = case.settled(request["request_id"])
            self.assertEqual(operation["state"], "blocked", operation)
            self.assertIn("EvidenceError", operation["result"]["reason"])
            self.assertIsNone(case.runtime._lease)
            self.assertNotEqual(case.runtime.status()["phase"], "active")
            self.assertEqual(case.runtime._ledger.memory_records("procedure"), ())
            self.assertEqual(case.runtime._ledger.primitive_records(), ())

    def test_retained_parent_request_and_claim_history_failures_stay_fatal(self):
        for scenario in ("procedure-parent", "claim-history"):
            with self.subTest(scenario=scenario), self.running() as case:
                if scenario == "procedure-parent":
                    _, good = self.candidate(case, "missing-request")
                    seed = case.request("remember", request_id="seed-procedure", **good)
                    self.assertEqual(case.runtime.command(seed)["status"], "accepted")
                    self.assertEqual(case.settled(seed["request_id"])["state"], "completed")
                    parent = deepcopy(good["entry"])
                    parent["support"][0]["request_ids"] = ["missing-trusted-original"]
                    case.runtime._ledger._db.execute("UPDATE memory SET body=? WHERE entry_type='procedure'",
                                                    (canonical(parent),))
                    good["entry"] = successor(good["entry"], support=good["entry"]["support"])
                else:
                    assertion = self.assertion(case, id="broken-parent")
                    seed = case.request("remember", request_id="seed-claim", entry_type="claim", entry=assertion)
                    self.assertEqual(case.runtime.command(seed)["status"], "accepted")
                    self.assertEqual(case.settled(seed["request_id"])["state"], "completed")
                    assertion["supports"] = [dict(sources=[], claims=["missing-trusted-premise"])]
                    case.runtime._ledger._db.execute("UPDATE memory SET body=? WHERE record_id='broken-parent'",
                                                    (canonical(assertion),))
                    good = dict(entry_type="claim", entry=self.assertion(case, id="new-candidate"))
                rows = self.memory_rows(case)
                request = case.request("remember", request_id="history-probe", **good)
                self.assertEqual(case.runtime.command(request)["status"], "accepted")
                operation = case.settled(request["request_id"])
                self.assertEqual(operation["state"], "blocked")
                self.assertNotIn("MemoryRequestRefusal", operation["result"]["reason"])
                self.assertIsNone(case.runtime._lease)
                self.assertNotEqual(case.runtime.status()["phase"], "active")
                self.assertEqual(self.memory_rows(case), rows)
                self.assertEqual(case.runtime._ledger.primitive_records(), ())

    def test_memory_transaction_write_commit_clock_and_capacity_faults_stay_fatal(self):
        for scenario in ("write", "commit", "clock", "capacity", "contract", "os-error"):
            with self.subTest(scenario=scenario), self.running() as case:
                rows = self.memory_rows(case)
                append = case.runtime._ledger.append_memory
                denied = []

                def fault(*args, **kwargs):
                    if scenario == "write":
                        case.runtime._ledger._db.execute("CREATE TEMP TRIGGER deny_memory BEFORE INSERT ON memory BEGIN SELECT RAISE(ABORT, 'memory disk write fault'); END")
                    elif scenario == "commit":
                        def authorizer(action, argument, *_):
                            if action == sqlite3.SQLITE_TRANSACTION and argument == "COMMIT" and not denied:
                                denied.append(True)
                                return sqlite3.SQLITE_DENY
                            return sqlite3.SQLITE_OK
                        case.runtime._ledger._db.set_authorizer(authorizer)
                    elif scenario == "clock":
                        kwargs["now"] -= 10
                    elif scenario == "capacity":
                        raise CapacityError("Actual campaign retention exhausted")
                    elif scenario == "contract":
                        raise ContractError("Internal memory projection failure")
                    elif scenario == "os-error":
                        raise OSError("Memory storage fault")
                    try:
                        return append(*args, **kwargs)
                    finally:
                        case.runtime._ledger._db.set_authorizer(None)

                request = case.request("remember", request_id="faulted-memory", entry_type="claim", entry=self.assertion(case))
                with patch.object(case.runtime._ledger, "append_memory", side_effect=fault):
                    self.assertEqual(case.runtime.command(request)["status"], "accepted")
                    operation = case.settled(request["request_id"])
                self.assertEqual(operation["state"], "blocked", operation)
                self.assertNotIn("MemoryRequestRefusal", operation["result"]["reason"])
                self.assertIsNone(case.runtime._lease)
                self.assertNotEqual(case.runtime.status()["phase"], "active")
                self.assertEqual(self.memory_rows(case), rows)
                self.assertEqual(case.runtime._ledger.primitive_records(), ())
                if scenario == "commit":
                    self.assertTrue(denied)

    def test_correction_after_a_fatal_stop_does_not_restore_authority(self):
        with self.running() as case:
            entry = self.assertion(case)
            request = case.request("remember", request_id="fatal-memory", entry_type="claim", entry=entry)
            with patch.object(case.runtime._ledger, "append_memory", side_effect=OSError("Storage failed")):
                self.assertEqual(case.runtime.command(request)["status"], "accepted")
                self.assertEqual(case.settled(request["request_id"])["state"], "blocked")
            epoch = case.runtime.status()["epoch"]
            corrected = case.request("remember", request_id="retained-after-stop", entry_type="claim", entry=entry)
            self.assertEqual(case.runtime.command(corrected)["status"], "accepted")
            self.assertEqual(case.settled(corrected["request_id"])["state"], "completed")
            self.assertEqual(case.runtime.status()["epoch"], epoch)
            self.assertNotEqual(case.runtime.status()["phase"], "active")
            self.assertIsNone(case.runtime._lease)
            self.assertIsNone(case.controller._mission_lease)
            self.assertEqual(case.runtime._ledger.primitive_records(), ())
