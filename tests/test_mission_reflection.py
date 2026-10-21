"""Real writer/SQLite advisory composition over synthetic transport, not gameplay."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from http.client import HTTPConnection
import json
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_contracts import LearningPolicy, ReflectionLimits
from harness.gameplay.mission_ledger import LedgerError, MissionLedger
from harness.mission_reflection import RegisteredReflection
from harness.mission_client import MissionClient
from harness.player_tools import PlayerTools
from harness.server import Server
from tests.test_mission_contracts import admission
from tests import test_mission_runtime as runtime_fixture
from tests.test_reflection_exchange import command, procedure


class ReflectionCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.a = admission(mission_id="mission-a", learning=LearningPolicy(procedure()["environment"],
            reflector_id="reflector-a", reflection_limits=ReflectionLimits(total_seconds=360)))
        self.ledger = MissionLedger(Path(self.temporary.name) / "mission", admission=self.a, now=1000.)
        self.addCleanup(lambda: self.ledger.close())
        self.wall = 1000.
        self.r = SimpleNamespace(_ledger=self.ledger, _admission=self.a, _wall=lambda: self.wall,
            _metadata=threading.Lock(), _closed=threading.Event(), _memory_version=0,
            _memory=SimpleNamespace(_procedure_heads=lambda: {}),
            _store=SimpleNamespace(historical_references=[]), _publish=lambda: None)
        self.reflection = RegisteredReflection(self.r)
        self.reflection.reset()

    def settled(self, number, *, payload=None):
        request = dict(schema="mission/9", kind="observe", request_id=f"request-{number}",
                       mission_id="mission-a", epoch=self.ledger.snapshot(now=self.wall)["epoch"])
        self.ledger.begin_request(request, now=self.wall)
        result = dict(source_ids=[f"source-{number}"], grants_authority=False, **(payload or {}))
        self.ledger.complete_request(request["request_id"], "completed", result, now=self.wall)
        self.r._store.historical_references.append(SimpleNamespace(observation_id=f"source-{number}"))
        self.reflection.completed(request, "completed")

    def schedule(self):
        self.reflection._urgent = True
        self.reflection.tick()
        return self.ledger.reflection_records()[0][-1]["job"]

    def test_job_uses_original_trace_and_coalesces_without_input_or_memory_change(self):
        self.settled(1)
        self.settled(2)
        self.reflection.tick()
        self.assertEqual(self.ledger.reflection_records(), ((), ()))
        first = self.schedule()
        self.assertEqual(first["included_request_ids"], ["request-1", "request-2"])
        self.assertEqual((first["after_sequence"], first["through_sequence"], first["memory_version"]), (0, 2, 0))
        self.assertEqual(self.ledger.snapshot(now=self.wall)["spent_inputs"], 0)
        self.assertEqual(self.ledger.memory_records("procedure"), ())
        self.settled(3)
        second = self.schedule()
        self.assertEqual((second["after_sequence"], second["through_sequence"]), (2, 3))
        self.settled(4)
        self.reflection._urgent = True
        self.reflection.tick()
        self.assertEqual(len(self.ledger.reflection_records()[0]), 2)
        self.assertEqual(self.reflection.summary()["unreviewed_requests"], 1)

    def test_advisory_ingress_and_wait_do_not_own_writer_or_input_lock(self):
        self.settled(1)
        job = self.schedule()
        exchange = self.reflection.exchange
        value = command(job_id=job["id"])
        with ThreadPoolExecutor(max_workers=1) as executor:
            receipt = executor.submit(exchange.offer, value).result(1)
            self.assertEqual(receipt["status"], "pending")
            self.reflection.tick()
            claim = executor.submit(exchange.collect, value["command_id"]).result(1)
            self.assertEqual(claim["result"]["state"], "claimed")
        self.settled(2)  # useful writer work is independent of advisory computation
        self.assertIsNotNone(self.ledger.request("request-2")["result"])
        self.assertEqual(self.ledger.reflection_records()[0][0]["state"], "claimed")

    def test_refusal_is_durable_but_storage_failure_is_not_an_advisory_rejection(self):
        self.reflection.exchange.offer(command(job_id="unknown-job"))
        self.reflection.tick()
        receipt = self.reflection.exchange.collect("command-1")
        self.assertEqual((receipt["status"], receipt["result"]["status"]), ("committed", "rejected"))
        self.assertEqual(len(self.ledger.reflection_command_records()), 1)
        self.reflection.exchange.offer(command("storage-failure"))
        with patch.object(self.ledger, "apply_reflection", side_effect=LedgerError("Disk unavailable")):
            with self.assertRaisesRegex(LedgerError, "Disk unavailable"):
                self.reflection.tick()
        self.assertEqual(self.reflection.exchange.collect("storage-failure")["status"], "unknown")
        self.assertEqual(len(self.ledger.reflection_command_records()), 1)

    def test_idle_ticks_do_not_write_and_finish_stops_ingress_without_actor_claim(self):
        self.settled(1)
        job = self.schedule()
        self.reflection.exchange.offer(command(job_id=job["id"]))
        self.reflection.tick()
        before = self.ledger.path.read_bytes()
        for _ in range(5):
            self.reflection.tick()
        self.assertEqual(self.ledger.path.read_bytes(), before)
        self.reflection.finish()
        self.assertEqual(self.ledger.reflection_records()[0][0]["state"], "unknown")
        self.assertEqual(self.reflection.exchange.offer(command("new"))["admitted"], False)
        self.assertEqual(self.reflection.exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["status"], "closed")

    def test_context_omissions_remain_exact_and_single_oversized_result_does_not_stop_play(self):
        self.r._admission = replace(self.a, learning=replace(self.a.learning,
            reflection_limits=ReflectionLimits(requests_per_job=2, sources_per_job=1, total_seconds=360)))
        # The ledger's frozen policy permits these tighter producer bounds too.
        for number in range(1, 5):
            self.settled(number)
        job = self.schedule()
        self.assertEqual(job["included_request_ids"], ["request-1", "request-4"])
        self.assertEqual((job["omitted_requests"], job["omitted_sources"]), (2, 1))
        self.settled(5, payload={"large": "x" * 65400})
        self.reflection._urgent = True
        self.reflection.tick()
        self.assertEqual(len(self.ledger.reflection_records()[0]), 1)
        self.assertIn("exceeds", self.reflection.summary()["reason"])
        self.assertEqual(self.ledger.request("request-5")["state"], "completed")

    def test_restored_cache_collects_original_receipt_without_claim_renewal(self):
        self.settled(1)
        job = self.schedule()
        self.reflection.exchange.offer(command(job_id=job["id"]))
        self.reflection.tick()
        original = self.reflection.exchange.collect("command-1")
        self.reflection.reset()
        self.assertEqual(self.reflection.exchange.collect("command-1"), original)
        self.reflection.tick()
        self.assertEqual(len(self.ledger.reflection_command_records()), 1)
        with self.assertRaises(ContractError):
            self.reflection.current("another", "reflector-a")

    def test_interrupted_missing_result_does_not_starve_subsequent_reflection(self):
        request = dict(schema="mission/9", kind="observe", request_id="interrupted",
                       mission_id="mission-a", epoch=0)
        self.ledger.begin_request(request, now=self.wall)
        self.ledger.close()
        self.ledger = MissionLedger(Path(self.temporary.name) / "mission", now=self.wall)
        self.r._ledger = self.ledger
        self.reflection.reset()
        self.assertEqual(self.ledger.request("interrupted")["state"], "unknown")
        self.settled(2)
        job = self.schedule()
        self.assertEqual(job["included_request_ids"], ["request-2"])
        self.assertEqual(job["omitted_requests"], 1)

    def test_oversized_old_result_does_not_erase_or_starve_later_obligations(self):
        self.settled(1, payload={"large": "x" * 65400})
        self.reflection._urgent = True
        self.reflection.tick()
        self.assertEqual(self.ledger.reflection_records()[0], ())
        self.settled(2)
        self.reflection.reset()
        self.assertEqual(self.reflection.summary()["unreviewed_requests"], 2)
        job = self.schedule()
        self.assertEqual(job["included_request_ids"], ["request-2"])
        self.assertEqual(job["omitted_requests"], 1)


class ReflectionHTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_fixture.MissionRuntimeTests(methodName="runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        environment = procedure()["environment"]
        self.f.a = replace(self.f.a, learning=LearningPolicy(environment, reflector_id="reflector-a"))
        self.f.start()
        with patch("harness.mission_runtime.MissionRuntime", return_value=self.f.runtime):
            self.server = Server(self.f.controller, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.shutdown)
        self.player = PlayerTools(MissionClient(self.f.controller.root))
        self.scope = dict(mission_id=self.f.a.mission_id, reflector_id="reflector-a")

    def shutdown(self):
        self.server.shutdown()
        self.thread.join(1)
        self.server.server_close()

    def navigate(self, number):
        request = self.f.navigation(target=(number % 2, 0, 0), request_id=f"step-{number}")
        self.assertEqual(self.f.runtime.command(request)["status"], "accepted")
        return self.f.settled(request["request_id"])

    def test_real_http_claim_source_submit_advice_and_useful_play_overlap(self):
        for number in range(1, 5):
            self.assertEqual(self.navigate(number)["state"], "completed")
        self.f.wait(lambda: self.f.runtime.status()["reflection"]["job_count"] == 1)
        claimed, _ = self.player.call("enactive_reflect_next", {**self.scope, "wait_seconds": 2})
        self.assertEqual(claimed["status"], "claimed", claimed)
        job = claimed["job"]["job"]
        self.assertEqual(job["through_sequence"], 5)  # Start + four root decisions
        source = job["sources"][-1]["source_id"]
        metadata, image = self.player.call("enactive_reflect_source", {**self.scope, "job_id": job["id"], "source_id": source})
        self.assertEqual(metadata["reference"]["observation_id"], source)
        self.assertTrue(image.startswith(b"\x89PNG"))
        self.assertEqual(len(self.player.sources), 0)
        self.assertEqual(self.navigate(5)["state"], "completed")
        self.assertEqual(self.f.runtime.status()["reflection"]["jobs"][0]["state"], "claimed")
        result, _ = self.player.call("enactive_reflect_submit", {**self.scope,
            "job_id": job["id"], "request_id": "advice-1", "wait_seconds": 2,
            "candidates": [], "notes": [], "reason": "Synthetic overlap boundary, no gameplay efficacy claim"})
        self.assertEqual(result["status"], "committed", result)
        proposal_id = result["result"]["proposal_id"]
        self.f.wait(lambda: proposal_id in self.f.runtime.status()["reflection"]["proposals"])
        advice, _ = self.player.call("enactive_advice", dict(mission_id=self.f.a.mission_id, proposal_id=proposal_id))
        self.assertEqual(advice["proposal"]["cutoff_sequence"], 5)
        self.assertEqual(self.f.runtime._ledger.memory_records("procedure"), ())

    def test_passive_wait_does_not_block_player_and_invalid_queries_refuse(self):
        began, release = threading.Event(), threading.Event()
        exchange = self.f.runtime._registered_reflection.exchange
        original = exchange.next_job
        def waiting(**kwargs):
            began.set()
            if not release.wait(3):
                raise AssertionError("Player call was blocked behind advisory wait")
            return original(**{**kwargs, "wait_seconds": 0})
        with patch.object(exchange, "next_job", side_effect=waiting), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.player.call, "enactive_reflect_next", {**self.scope, "wait_seconds": 2})
            try:
                self.assertTrue(began.wait(1))
                snapshot = self.player.call("enactive_snapshot", {})[0]
                self.assertEqual(snapshot["mission"]["mission_id"], self.f.a.mission_id)
                self.assertFalse(future.done())
            finally:
                release.set()
            self.assertEqual(future.result(2)[0]["status"], "idle")
        for query in ("mission_id=x", "mission_id=x&reflector_id=y&wait_seconds=nan",
                      "mission_id=x&mission_id=y&reflector_id=z&wait_seconds=0"):
            connection = HTTPConnection("127.0.0.1", self.server.port, timeout=2)
            connection.request("GET", "/api/reflection/next?" + query,
                headers={"X-CDDA-Token": self.f.controller.token})
            response = connection.getresponse()
            self.assertEqual(response.status, 409)
            self.assertEqual(json.loads(response.read())["status"], "rejected")
            connection.close()
