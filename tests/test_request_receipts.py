"""Real writer/SQLite/journal with synthetic transport; no native game claim."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

from harness.gameplay.mission_contracts import validate_admission_refusal
from harness.gameplay.mission_ledger import LedgerError, RequestAdmissionRefusal, RequestNotFound
from harness.gameplay.evaluation import request_timing_summary
from harness.mission_client import MissionClient
from harness.mission_runtime import _Work
from tests import test_mission_http as http_fixture
from tests import test_mission_runtime as core
from tests.test_mission_creation import MissionCreationFixture


def timing_events(runtime):
    with runtime.controller._journal_lock:
        path = runtime.controller.journal
        events = [] if not path.exists() else [json.loads(line) for line in path.read_text().splitlines()]
    return [event for event in events if event["request"]["kind"] == "mission_request_settled"]


def settled_timing(runtime, identity):
    end = time.monotonic() + 3
    while time.monotonic() < end:
        events = [e["outcome"] for e in timing_events(runtime) if e["outcome"]["request_id"] == identity]
        if events:
            if len(events) != 1:
                raise AssertionError(f"Duplicate settlement for {identity}")
            return events[0]
        threading.Event().wait(.005)
    raise AssertionError(f"No settlement timing for {identity}")


class AdmissionRefusalIntegrationTests(MissionCreationFixture, unittest.TestCase):
    def test_wrong_launch_identity_is_certified_and_new_corrected_request_works(self):
        self.start()
        old = self.runtime.status()
        wrong = self.request(identity="wrong-world", world="unadmitted-world")
        response = self.runtime.command(wrong)
        self.assertEqual(response["status"], "rejected")
        validate_admission_refusal(response["admission_refusal"], wrong)
        with self.assertRaises(RequestNotFound):
            self.runtime._ledger.request(wrong["request_id"])
        self.process.launch.assert_not_called()
        self.assertEqual(self.runtime.status()["epoch"], old["epoch"])
        self.assertEqual(self.runtime.status()["phase"], old["phase"])
        self.assertEqual(self.runtime._ledger.primitive_records(), ())
        refused = settled_timing(self.runtime, wrong["request_id"])
        self.assertEqual(refused["admission"], "not_admitted")
        self.assertIsNone(refused["row_state"])
        self.assertIsNone(refused["admitted_at"])
        self.assertEqual(self.launch(identity="corrected-launch")["state"], "completed")
        self.assertEqual(self.process.launch.call_count, 1)

    def test_conflicting_existing_identity_never_gets_zero_admission_proof(self):
        self.start()
        original = self.launch()
        conflict = {**original["request"], "world": "different"}
        response = self.runtime.command(conflict)
        self.assertEqual(response["status"], "rejected")
        self.assertNotIn("admission_refusal", response)
        with self.assertRaises(LedgerError) as raised:
            self.runtime._ledger.begin_request(conflict, now=time.time())
        self.assertNotIsInstance(raised.exception, RequestAdmissionRefusal)
        self.assertEqual(self.runtime._ledger.request("launch"), original)
        self.assertEqual(self.process.launch.call_count, 1)

    def test_pause_between_absence_and_publication_cannot_publish_certificate(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        original = self.runtime._ledger.request_timing_state
        def pause_at_absence(identity):
            try:
                return original(identity)
            except RequestNotFound:
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("Refusal barrier not released")
                raise
        wrong = self.request(identity="pause-refusal", world="wrong")
        with patch.object(self.runtime._ledger, "request_timing_state", side_effect=pause_at_absence), \
                ThreadPoolExecutor(max_workers=1) as pool:
            response = pool.submit(self.runtime.command, wrong)
            try:
                self.assertTrue(entered.wait(2))
                self.runtime.pause()
            finally:
                release.set()
            self.assertNotIn("admission_refusal", response.result(3))
        self.process.launch.assert_not_called()
        with self.assertRaises(RequestNotFound):
            self.runtime._ledger.request(wrong["request_id"])

    def test_admission_timeout_is_not_a_certificate_or_later_launch(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        original_handle = self.runtime._handle
        def hold(work):
            entered.set()
            if not release.wait(2):
                raise TimeoutError("Admission barrier not released")
            return original_handle(work)
        def work_factory(data, **options):
            work = _Work(data, **options)
            def timeout(_):
                self.assertTrue(entered.wait(2))
                return False
            work.ready.wait = timeout
            return work
        wrong = self.request(identity="timed-out-refusal", world="wrong")
        with patch.object(self.runtime, "_handle", side_effect=hold), \
                patch("harness.mission_runtime._Work", side_effect=work_factory):
            try:
                response = self.runtime.command(wrong)
                self.assertIn("Admission wait expired", response["reason"])
                self.assertNotIn("admission_refusal", response)
            finally:
                release.set()
        self.runtime._queue.join()
        self.process.launch.assert_not_called()
        with self.assertRaises(RequestNotFound):
            self.runtime._ledger.request(wrong["request_id"])

    def test_storage_failure_is_not_absence(self):
        self.start()
        with patch.object(self.runtime._ledger, "request_timing_state", side_effect=sqlite3.OperationalError("unavailable")):
            response = self.runtime.command(self.request(world="wrong"))
        self.assertEqual(response["status"], "rejected")
        self.assertNotIn("admission_refusal", response)
        self.process.launch.assert_not_called()


class SettlementTimingTests(unittest.TestCase):
    setUp = core.MissionRuntimeTests.setUp
    wait = core.MissionRuntimeTests.wait
    request = core.MissionRuntimeTests.request
    result = core.MissionRuntimeTests.result
    settled = core.MissionRuntimeTests.settled
    start = core.MissionRuntimeTests.start
    navigation = core.MissionRuntimeTests.navigation

    def test_one_semantic_settlement_covers_finalization_but_not_passive_reads(self):
        self.start()
        request = self.navigation(target=(0, 0, 0))
        self.runtime.command(request)
        self.assertEqual(self.settled(request["request_id"])["state"], "completed")
        event = settled_timing(self.runtime, request["request_id"])
        self.assertEqual(event["row_state"], "completed")
        self.assertEqual(event["mission_phase"], "active")
        self.assertTrue(event["writer_finalized"])
        self.assertIsNone(event["censored_reason"])
        summary = request_timing_summary(timing_events(self.runtime), mission_id=self.a.mission_id,
            request_ids=[row["request"]["request_id"] for row in self.runtime._ledger.request_records()])
        self.assertEqual(summary["missing_request_ids"], [])
        row = next(row for row in summary["rows"] if row["request_id"] == request["request_id"])
        self.assertIsNotNone(row["service_ms"])
        self.assertIsNone(row["censored_reason"])
        self.assertLessEqual(event["received_monotonic"], event["admission_started_monotonic"])
        self.assertLessEqual(event["admission_started_monotonic"], event["admitted_monotonic"])
        self.assertLessEqual(event["admitted_monotonic"], event["settled_monotonic"])
        before = timing_events(self.runtime)
        self.runtime.command(request)
        self.result(request["request_id"])
        self.runtime.status()
        self.runtime._queue.join()
        self.assertEqual(timing_events(self.runtime), before)
        with self.controller.data_lock:
            self.assertFalse(any(e["request"]["kind"] == "mission_request_settled" for e in self.controller.events))

    def test_unknown_delivery_has_its_own_terminal_row_not_success(self):
        self.start()
        self.bridge.behavior = lambda bridge, request: request["kind"] != "action"
        data = self.navigation()
        self.runtime.command(data)
        operation = self.settled(data["request_id"])
        event = settled_timing(self.runtime, data["request_id"])
        self.assertEqual(operation["state"], "unknown")
        self.assertEqual(event["row_state"], "unknown")
        self.assertEqual(event["mission_phase"], "paused")
        self.assertTrue(event["writer_finalized"])

    def test_new_timing_append_failure_does_not_rewrite_or_pause_committed_work(self):
        self.start()
        original = self.controller._record
        attempted = threading.Event()
        def fail_only_timing(request, outcome, **options):
            if request["kind"] == "mission_request_settled":
                attempted.set()
                raise OSError("Timing-only append unavailable")
            return original(request, outcome, **options)
        data = self.navigation(target=(0, 0, 0))
        with patch.object(self.controller, "_record", side_effect=fail_only_timing), \
                self.assertLogs("harness.mission_runtime", level="WARNING"):
            self.runtime.command(data)
            operation = self.settled(data["request_id"])
            self.assertTrue(attempted.wait(2))
            self.runtime._queue.join()
        self.assertEqual(operation["state"], "completed")
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertFalse(self.runtime._closed.is_set())


class ProductionRefusalHTTPTests(unittest.TestCase):
    setUp = http_fixture.MissionHTTPTests.setUp
    raw = http_fixture.MissionHTTPTests.raw
    request = http_fixture.MissionHTTPTests.request

    def test_authenticated_writer_sdk_refusal_needs_no_phantom_collection(self):
        client = MissionClient(self.controller.root)
        client.submit(dict(schema="mission/11", kind="start", request_id="start",
                           admission=self.a.to_dict()), wait_seconds=2)
        epoch = self.server.mission.status()["epoch"]
        wrong = dict(schema="mission/11", kind="lifecycle", request_id="wrong-launch",
            mission_id=self.a.mission_id, epoch=epoch, operation="launch", world="wrong",
            character=self.a.scenario.character, sources=[], expected_session=None,
            expected_revision=None, expected_boundary_id=None, work_id=None, phase_id=None,
            identity_claim_ids=[], limits=dict(primitives=1, wall_seconds=30, game_seconds=1))
        with patch.object(client, "_json", wraps=client._json) as transport:
            result = client.submit(wrong, wait_seconds=2)
            self.assertEqual(transport.call_count, 1)
        self.assertTrue(result["settled"])
        self.assertEqual(result["submission"], "not_admitted")
        self.assertEqual(client.staged_request(self.a.mission_id, "wrong-launch"), wrong)
        with self.assertRaises(RequestNotFound):
            self.server.mission._ledger.request("wrong-launch")
        self.assertEqual(self.server.mission._ledger.primitive_records(), ())
        corrected = dict(schema="mission/11", kind="observe", request_id="new-choice",
                         mission_id=self.a.mission_id, epoch=epoch)
        client.submit(corrected, wait_seconds=2)
        self.assertEqual(self.server.mission._ledger.request("new-choice")["request"], corrected)
