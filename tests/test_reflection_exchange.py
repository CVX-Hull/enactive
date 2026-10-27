"""Passive advisory exchange checks; no claim of native/host concurrency."""
from copy import deepcopy
import ast
import inspect
import json
import threading
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.procedures import import_procedure, validate_procedure
from harness.gameplay.mission_contracts import validate_request
from harness.gameplay import reflection
from harness.gameplay.reflection import (
    ReflectiveExchange, validate_command, validate_job, validate_proposal,
)


def procedure():
    return {"schema": "procedure/3", "record_type": "Procedure", "id": "revision-1",
            "mission_id": "mission-a", "procedure_id": "inspect", "revision": 1,
            "parent": None, "program": None, "goal": "Inspect visible needs", "parameters": [],
            "applicability": ["Visible needs available"], "invalidators": [],
            "steps": [{"intent": "Inspect", "expected": "Visible needs",
                       "on_unexpected": "Reassess"}], "progress": ["Needs visible"],
            "stop_conditions": ["Needs interpreted"], "limits": [],
            "environment": {"engine_commit": "a" * 40, "native_protocol": 7,
                            "mission_schema": "mission/11", "configuration": "ordinary"},
            "support": [{"mission_id": "mission-a", "request_ids": ["request-1"],
                         "source_ids": ["source-1"], "interpretation": "One example"}],
            "counterexamples": [], "status": "candidate", "reason": "Scoped data"}


def job(**changes):
    request = {"schema": "mission/11", "kind": "observe", "request_id": "request-1",
               "mission_id": "mission-a", "epoch": 0}
    return {"schema": "reflection/3", "record_type": "ReflectionJob", "id": "job-1",
            "mission_id": "mission-a", "reflector_id": "reflector-a", "epoch": 0,
            "memory_version": 1, "after_sequence": 0, "through_sequence": 1,
            "included_request_ids": ["request-1"], "omitted_requests": 0,
            "omitted_sources": 0, "omitted_procedures": 0,
            "sources": [{"mission_id": "mission-a", "source_id": "source-1"}],
            "trajectory": [{"request": request, "state": "completed",
                            "result": {"exact": "retained", "sources": ["source-1"]}}],
            "procedures": [], **changes}


def proposal(**changes):
    return {"schema": "reflection/3", "record_type": "ReflectionProposal", "id": "proposal-1",
            "job_id": "job-1", "mission_id": "mission-a", "reflector_id": "reflector-a",
            "epoch": 0, "cutoff_sequence": 1, "memory_version": 1,
            "candidates": [procedure()],
            "notes": [{"kind": "finding", "text": "One observed result",
                       "request_ids": ["request-1"],
                       "source_refs": [{"mission_id": "mission-a", "source_id": "source-1"}]}],
            "reason": "Bounded finding", **changes}


def command(command_id="command-1", *, submit=False, **changes):
    value = {"schema": "reflection/3", "kind": "submit" if submit else "claim",
             "command_id": command_id, "mission_id": "mission-a",
             "reflector_id": "reflector-a", "job_id": "job-1", **changes}
    if submit:
        value["proposal"] = proposal()
    return value


def wrapper(value=None, **changes):
    return {"job": job() if value is None else value, "state": "offered",
            "claimed_at": None, "deadline": None, **changes}


def publish(exchange, *, phase="active", jobs=None, proposals=None, **changes):
    exchange.publish(mission_id="mission-a", reflector_id="reflector-a", phase=phase,
                     epoch=0, jobs=[wrapper()] if jobs is None else jobs,
                     proposals=[] if proposals is None else proposals, **changes)


class ReflectionValidationTests(unittest.TestCase):
    def test_old_reflection_versions_refuse_in_jobs_proposals_and_commands(self):
        for validator, original in ((validate_job, job()), (validate_proposal, proposal()),
                                    (validate_command, command()), (validate_command, command(submit=True))):
            for version in ("reflection/1", "reflection/2"):
                with self.subTest(validator=validator.__name__, version=version), self.assertRaises(ContractError):
                    validator({**original, "schema": version})
        envelope = command(submit=True)
        envelope["proposal"]["schema"] = "reflection/2"
        with self.assertRaises(ContractError):
            validate_command(envelope)

    def test_jobs_accept_historical_lineage_inputs_but_candidates_remain_current(self):
        original = procedure()
        original["environment"]["native_protocol"] = 6
        historical = import_procedure(canonical(original), ledger_sha256="b" * 64, index_sha256="c" * 64)
        value = job(procedures=[historical, procedure()])
        self.assertEqual(validate_job(value), value)
        self.assertEqual(validate_proposal(proposal(), value), proposal())
        envelope = command(submit=True)
        envelope["proposal"]["candidates"] = [historical]
        for validator, invalid in ((validate_proposal, proposal(candidates=[historical])),
                                    (validate_command, envelope),
                                    (validate_job, job(procedures=[original])),
                                    (validate_job, job(procedures=[{**historical, "advisory_only": False}])),
                                    (validate_job, job(procedures=[{**historical, "parameters": [
                                        {"name": "p", "description": "first"},
                                        {"name": "p", "description": "second"}]}]))):
            with self.subTest(validator=validator.__name__), self.assertRaises(ContractError):
                validator(invalid)
        exchange = ReflectiveExchange()
        publish(exchange, jobs=[wrapper(value)], proposals=[proposal()])
        self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["job"]["job"], value)

    def test_adapter_schema_is_defensive(self):
        first = reflection.proposal_schema()
        first["properties"].clear()
        self.assertIn("candidates", reflection.proposal_schema()["properties"])

    def test_real_current_validators_and_defensive_copy(self):
        self.assertEqual(validate_request(job()["trajectory"][0]["request"])["schema"], "mission/11")
        self.assertEqual(validate_procedure(procedure())["schema"], "procedure/3")
        for validator, original in ((validate_job, job()), (validate_proposal, proposal()),
                                    (validate_command, command(submit=True))):
            for value in (original, json.dumps(original), json.dumps(original).encode()):
                result = validator(value)
                self.assertEqual(result, original)
                result.clear()
                self.assertTrue(original)

    def test_closed_records_every_required_field_and_utf8_finite(self):
        for validator, original in ((validate_job, job()), (validate_proposal, proposal()),
                                    (validate_command, command())):
            for field in original:
                value = deepcopy(original)
                del value[field]
                with self.subTest(field=field), self.assertRaises(ContractError):
                    validator(value)
            for value in ({**original, "grants_authority": True}, [], b"\xff",
                          '{"id":"a","id":"b"}', {**original, "epoch": float("nan")},
                          {**original, "mission_id": "mission-a\n"},
                          {**original, "mission_id": "é"}, {**original, "mission_id": "a" * 129}):
                with self.subTest(value=str(value)[:60]), self.assertRaises(ContractError):
                    validator(value)
        with self.assertRaises(ContractError):
            validate_job(job(trajectory=[{**job()["trajectory"][0], "result": {"text": "\ud800"}}]))
        with self.assertRaises(ContractError):
            validate_job(job(trajectory=[{**job()["trajectory"][0], "result": {"n": float("inf")}}]))

    def test_job_order_actor_span_recursion_and_limits(self):
        invalid = [job(after_sequence=1), job(through_sequence=4097), job(epoch=True),
                   job(memory_version=1.0), job(sources=job()["sources"] * 2),
                   job(included_request_ids=["request-other"]), job(procedures=[procedure()] * 17)]
        for field, value in (("mission_id", "mission-b"), ("schema", "mission/8"),
                             ("kind", "remember"), ("kind", "context"), ("kind", "reflection")):
            row = deepcopy(job()["trajectory"][0])
            row["request"][field] = value
            invalid.append(job(trajectory=[row]))
        invalid.extend([job(trajectory=[]), job(omitted_requests=4097),
                        job(omitted_sources=4097), job(omitted_procedures=257)])
        for value in invalid:
            with self.subTest(value=str(value)[:100]), self.assertRaises(ContractError):
                validate_job(value)
        value = job()
        value["trajectory"][0]["result"]["exact"] = "a" * 65_536
        with self.assertRaises(ContractError):
            validate_job(value)

    def test_proposal_exact_header_and_source_closure(self):
        self.assertEqual(validate_proposal(proposal(), job()), proposal())
        for field, value in (("job_id", "other"), ("mission_id", "other"),
                             ("reflector_id", "other"), ("epoch", 1),
                             ("cutoff_sequence", 2), ("memory_version", 2)):
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_proposal(proposal(**{field: value}), job())
        for field, value in (("request_ids", ["invented"]),
                             ("source_refs", [{"mission_id": "other", "source_id": "source-1"}])):
            note = {**proposal()["notes"][0], field: value}
            with self.assertRaises(ContractError):
                validate_proposal(proposal(notes=[note]), job())
        for field, value in (("request_ids", ["invented"]), ("source_ids", ["invented"]),
                             ("mission_id", "invented")):
            candidate = procedure()
            candidate["support"][0][field] = value
            with self.assertRaises(ContractError):
                validate_proposal(proposal(candidates=[candidate]), job())
        self.assertEqual(validate_proposal(proposal(candidates=[], notes=[]), job())["notes"], [])

    def test_historical_procedure_episode_closure_is_qualified(self):
        historical = procedure()
        historical["mission_id"] = "historical"
        historical["support"][0] = {"mission_id": "historical", "request_ids": ["old-request"],
                                    "source_ids": ["old-source"], "interpretation": "Old example"}
        historical["environment"]["native_protocol"] = 6
        historical = import_procedure(canonical(historical), ledger_sha256="b" * 64, index_sha256="c" * 64)
        candidate = procedure()
        candidate["support"] = deepcopy(historical["support"])
        note = {"kind": "question", "text": "Review old example", "request_ids": ["old-request"],
                "source_refs": [{"mission_id": "historical", "source_id": "old-source"}]}
        self.assertTrue(validate_proposal(proposal(candidates=[candidate], notes=[note]),
                                         job(procedures=[historical])))
        candidate["support"][0]["mission_id"] = "mission-a"
        with self.assertRaises(ContractError):
            validate_proposal(proposal(candidates=[candidate], notes=[]), job(procedures=[historical]))

    def test_proposal_and_command_bounds_and_matching(self):
        for value in (proposal(candidates=[procedure()] * 5), proposal(notes=proposal()["notes"] * 9),
                      proposal(reason="a" * 1025), proposal(epoch=1.0),
                      proposal(notes=[{**proposal()["notes"][0], "request_ids": ["r"] * 2}])):
            with self.assertRaises(ContractError):
                validate_proposal(value)
        large = proposal(candidates=[procedure()] * 4)
        for candidate in large["candidates"]:
            candidate["limits"] = ["界" * 1024] * 8
        with self.assertRaises(ContractError):
            validate_proposal(large)
        for field in ("job_id", "mission_id", "reflector_id"):
            value = command(submit=True)
            value["proposal"][field] = "other"
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_command(value)
        with self.assertRaises(ContractError):
            validate_command({**command(), "proposal": proposal()})


class ReflectiveExchangeTests(unittest.TestCase):
    def test_temporary_seal_and_finishing_hide_jobs_with_original_bounded_wait(self):
        for sealed, phase in ((True, "active"), (False, "finishing")):
            with self.subTest(sealed=sealed, phase=phase):
                exchange = ReflectiveExchange()
                original = wrapper(state="claimed", claimed_at=1000., deadline=1060.)
                publish(exchange, phase=phase, jobs=[original])
                if sealed:
                    exchange.seal_ingress(permanent=False)
                with patch.object(reflection, "monotonic", side_effect=[100., 101., 103., 106.]), \
                        patch.object(exchange._condition, "wait") as wait:
                    results = []
                    reader = threading.Thread(target=lambda: results.append(exchange.next_job(
                        mission_id="mission-a", reflector_id="reflector-a", wait_seconds=5)))
                    reader.start()
                    reader.join(2)
                self.assertFalse(reader.is_alive())
                self.assertEqual(results, [{"status": "idle", "grants_authority": False}])
                self.assertEqual([call.args for call in wait.call_args_list], [(4.,), (2.,)])
                exchange.reopen_ingress()
                publish(exchange, phase="paused", jobs=[original])
                self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["job"], original)

    def test_permanent_seal_cannot_downgrade_or_reopen(self):
        exchange = ReflectiveExchange()
        publish(exchange)
        exchange.seal_ingress(permanent=True)
        exchange.seal_ingress(permanent=False)
        publish(exchange, phase="paused")
        with self.assertRaisesRegex(ContractError, "cannot be reopened"):
            exchange.reopen_ingress()
        self.assertFalse(exchange.offer(command())["admitted"])
        self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["status"], "closed")

    def test_terminal_publication_closes_and_cannot_reopen(self):
        for phase in ("completed", "failed", "stopped"):
            with self.subTest(phase=phase):
                exchange = ReflectiveExchange()
                publish(exchange, phase=phase)
                with self.assertRaisesRegex(ContractError, "cannot be reopened"):
                    exchange.reopen_ingress()
                self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["status"], "closed")

    def test_restore_original_receipts_without_requeue_and_seal_new_ingress(self):
        exchange = ReflectiveExchange()
        original = command()
        outcome = dict(status="rejected", reason="Original known refusal", grants_authority=False)
        exchange.restore([dict(command=original, result=outcome, received_at=1000.)])
        receipt = exchange.collect(original["command_id"])
        self.assertEqual(receipt["result"], outcome)
        self.assertEqual(exchange.drain(lambda body: self.fail("Restoration requeued a body")), 0)
        self.assertEqual(exchange.offer(original), receipt)
        exchange.seal_ingress(permanent=True)
        self.assertEqual(exchange.offer(command("new"))["admitted"], False)
        self.assertEqual(exchange.collect(original["command_id"]), receipt)
        self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["status"], "closed")

    def test_cached_source_allowlist_never_broadens_to_another_job_or_mission(self):
        exchange = ReflectiveExchange()
        publish(exchange)
        select = dict(mission_id="mission-a", reflector_id="reflector-a", job_id="job-1", source_id="source-1")
        self.assertTrue(exchange.source_allowed(**select))
        for changes in (dict(mission_id="another"), dict(reflector_id="another"),
                        dict(job_id="another"), dict(source_id="another")):
            self.assertFalse(exchange.source_allowed(**(select | changes)))

    def test_stable_duplicates_conflict_full_zero_admission_and_lost_collector(self):
        exchange = ReflectiveExchange(max_operations=2)
        first = exchange.offer(command())
        self.assertEqual(first["status"], "pending")
        self.assertEqual(exchange.offer(command()), first)
        self.assertEqual(exchange.offer(command("command-2"))["status"], "pending")
        self.assertEqual(exchange.offer(command("command-3"))["admitted"], False)
        self.assertEqual(exchange.collect("command-3")["status"], "missing")
        with self.assertRaises(ContractError):
            exchange.offer(command(job_id="other"))
        self.assertEqual(exchange.drain(lambda body: {"original": body["job_id"]}), 2)
        completed = exchange.collect("command-1")
        self.assertEqual(completed["result"], {"original": "job-1"})
        self.assertEqual(exchange.offer(command()), completed)
        self.assertEqual(exchange.collect("command-1"), completed)
        self.assertEqual(exchange.offer(command("command-3"))["admitted"], False)
        completed["result"].clear()
        self.assertTrue(exchange.collect("command-1")["result"])

    def test_callback_outside_condition_inflight_counts_against_bound(self):
        exchange = ReflectiveExchange()
        entered, release = threading.Event(), threading.Event()
        failures = []
        exchange.offer(command())

        def apply(body):
            entered.set()
            if not release.wait(2):
                raise AssertionError("Callback watchdog")
            body.clear()
            return {"done": True}

        def drain():
            try:
                exchange.drain(apply, max_operations=1)
            except BaseException as exc:
                failures.append(exc)

        writer = threading.Thread(target=drain)
        writer.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(exchange.offer(command())["status"], "pending")
            self.assertEqual(exchange.offer(command("command-2"))["admitted"], True)
            self.assertEqual(exchange.offer(command("command-3"))["admitted"], False)
            self.assertEqual(exchange.collect("command-1")["status"], "pending")
        finally:
            release.set()
            writer.join(2)
        self.assertFalse(writer.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(exchange.collect("command-1")["status"], "committed")

    def test_failure_unknown_releases_capacity_and_never_replays(self):
        exchange = ReflectiveExchange(pending_limit=1)
        exchange.offer(command())
        calls = []

        def fail(body):
            calls.append(body)
            raise RuntimeError("Bookkeeping uncertain")

        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            exchange.drain(fail)
        self.assertEqual(exchange.collect("command-1")["status"], "unknown")
        self.assertEqual(exchange.offer(command())["status"], "unknown")
        self.assertEqual(exchange.drain(fail), 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(exchange.offer(command("command-2"))["status"], "pending")

    def test_invalid_callback_result_is_unknown_and_reraised(self):
        for result in ([], "{}", b"{}", {"x": float("nan")}, {"x": "a" * 65_536}):
            exchange = ReflectiveExchange()
            exchange.offer(command())
            with self.subTest(result=str(result)[:30]), self.assertRaises(ContractError):
                exchange.drain(lambda body: result)
            self.assertEqual(exchange.collect("command-1")["status"], "unknown")

    def test_passive_wait_survives_temporary_seal_and_permanent_close_wakes(self):
        exchange = ReflectiveExchange()
        publish(exchange, jobs=[])
        waiting, resealed = threading.Event(), threading.Event()
        original_wait = exchange._condition.wait
        results = []

        def notified_wait(timeout=None):
            (resealed if exchange._sealed else waiting).set()
            return original_wait(timeout)

        with patch.object(exchange._condition, "wait", side_effect=notified_wait):
            reader = threading.Thread(target=lambda: results.append(exchange.next_job(
                mission_id="mission-a", reflector_id="reflector-a", wait_seconds=40)))
            reader.start()
            try:
                self.assertTrue(waiting.wait(2))
                self.assertEqual(exchange.offer(command())["admitted"], True)
                game_work = []
                self.assertEqual(exchange.drain(lambda body: game_work.append("boundary") or {}), 1)
                self.assertEqual(game_work, ["boundary"])
                exchange.seal_ingress(permanent=False)
                self.assertTrue(resealed.wait(2))
                self.assertEqual(results, [])
                publish(exchange, phase="finishing", jobs=[])
                exchange.seal_ingress(permanent=True)
            finally:
                reader.join(2)
        self.assertFalse(reader.is_alive())
        self.assertEqual(results, [{"status": "closed", "grants_authority": False}])

    def test_extended_wait_wakes_on_job_without_claiming_or_renewing_it(self):
        for seconds in (16, 40):
            with self.subTest(wait_seconds=seconds):
                exchange = ReflectiveExchange()
                publish(exchange, jobs=[])
                waiting = threading.Event()
                original_wait = exchange._condition.wait
                results = []
                def notified_wait(timeout=None):
                    waiting.set()
                    return original_wait(timeout)
                with patch.object(exchange._condition, "wait", side_effect=notified_wait) as wait:
                    reader = threading.Thread(target=lambda: results.append(exchange.next_job(
                        mission_id="mission-a", reflector_id="reflector-a", wait_seconds=seconds)))
                    reader.start()
                    try:
                        self.assertTrue(waiting.wait(2))
                        self.assertGreater(wait.call_args.args[0], seconds - 2)
                        self.assertLessEqual(wait.call_args.args[0], seconds)
                        publish(exchange)
                        reader.join(2)
                        self.assertFalse(reader.is_alive())
                    finally:
                        exchange.seal_ingress(permanent=True)
                        reader.join(2)
                self.assertEqual(results, [dict(status="offered", job=wrapper(), grants_authority=False)])
                self.assertEqual(exchange.summary()["operations"], 0)

    def test_terminal_publication_wakes_passive_wait(self):
        exchange = ReflectiveExchange()
        publish(exchange, jobs=[])
        waiting = threading.Event()
        original_wait = exchange._condition.wait
        results = []
        def notified_wait(timeout=None):
            waiting.set()
            return original_wait(timeout)
        with patch.object(exchange._condition, "wait", side_effect=notified_wait):
            reader = threading.Thread(target=lambda: results.append(exchange.next_job(
                mission_id="mission-a", reflector_id="reflector-a", wait_seconds=40)))
            reader.start()
            try:
                self.assertTrue(waiting.wait(2))
                publish(exchange, phase="stopped", jobs=[])
            finally:
                reader.join(2)
        self.assertFalse(reader.is_alive())
        self.assertEqual(results, [{"status": "closed", "grants_authority": False}])

    def test_publish_copies_conflicts_and_retrieval_actor_scope(self):
        exchange = ReflectiveExchange()
        value, advice = wrapper(), proposal()
        publish(exchange, jobs=[value], proposals=[advice])
        value["job"]["trajectory"].clear()
        advice["notes"].clear()
        result = exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")
        self.assertEqual(result["status"], "offered")
        result["job"]["job"]["trajectory"].clear()
        self.assertTrue(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["job"]["job"]["trajectory"])
        found = exchange.proposal(mission_id="mission-a", proposal_id="proposal-1")
        self.assertEqual(found["status"], "available")
        found["proposal"]["notes"].clear()
        self.assertTrue(exchange.proposal(mission_id="mission-a", proposal_id="proposal-1")["proposal"]["notes"])
        self.assertEqual(exchange.proposal(mission_id="other", proposal_id="proposal-1")["status"], "missing")
        self.assertEqual(exchange.next_job(mission_id="other", reflector_id="reflector-a")["status"], "idle")
        publish(exchange, jobs=[wrapper(state="claimed", claimed_at=1.0, deadline=181.0)])
        self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["status"], "claimed")
        with self.assertRaises(ContractError):
            publish(exchange, jobs=[wrapper(job(memory_version=2))])
        with self.assertRaises(ContractError):
            publish(exchange, proposals=[proposal(reason="Changed immutable advice")])
        with self.assertRaises(ContractError):
            exchange.publish(mission_id="other", reflector_id="reflector-a", phase="active",
                             epoch=0, jobs=[], proposals=[])

    def test_job_numeric_canonical_identity_cannot_change_with_python_equality(self):
        exchange = ReflectiveExchange()
        original = job()
        original["trajectory"][0]["result"] = {"count": 1}
        publish(exchange, jobs=[wrapper(original)])
        changed = deepcopy(original)
        changed["trajectory"][0]["result"]["count"] = 1.0
        self.assertEqual(changed, original)  # Python equality is weaker than JSON identity.
        with self.assertRaises(ContractError):
            publish(exchange, jobs=[wrapper(changed)])

    def test_only_writer_drains_or_publishes_and_writer_cannot_wait(self):
        exchange = ReflectiveExchange()
        publish(exchange)
        failures = []

        def other_writer():
            for action in (lambda: exchange.drain(lambda body: {}), lambda: publish(exchange)):
                try:
                    action()
                except ContractError:
                    failures.append("refused")

        thread = threading.Thread(target=other_writer)
        thread.start()
        thread.join(2)
        self.assertEqual(failures, ["refused", "refused"])
        with self.assertRaises(ContractError):
            exchange.next_job(mission_id="mission-a", reflector_id="reflector-a", wait_seconds=40)

    def test_job_order_claimed_priority_unknown_proposal_and_atomic_refusal(self):
        exchange = ReflectiveExchange()
        newer = wrapper(job(id="newer", through_sequence=3))
        older = wrapper(job(id="older", through_sequence=2))
        publish(exchange, jobs=[newer, older])
        self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["job"]["job"]["id"], "older")
        newer["state"] = "claimed"
        publish(exchange, jobs=[older, newer])
        self.assertEqual(exchange.next_job(mission_id="mission-a", reflector_id="reflector-a")["job"]["job"]["id"], "newer")
        before = exchange.summary()
        with self.assertRaises(ContractError):
            publish(exchange, jobs=[], proposals=[proposal(job_id="unknown-job")])
        self.assertEqual(exchange.summary(), before)
        with self.assertRaises(ContractError):
            publish(exchange, jobs=[], proposals=[proposal(job_id="older", cutoff_sequence=3)])
        self.assertEqual(exchange.summary(), before)
        publish(exchange, jobs=[], proposals=[proposal(job_id="older", cutoff_sequence=2)])
        self.assertEqual(exchange.proposal(mission_id="mission-a", proposal_id="proposal-1")["status"], "available")

    def test_publication_lifetime_and_wrapper_bounds(self):
        exchange = ReflectiveExchange()
        jobs = [wrapper(job(id=f"job-{index}")) for index in range(64)]
        publish(exchange, jobs=jobs)
        self.assertEqual(exchange.summary()["job_count"], 64)
        with self.assertRaises(ContractError):
            publish(exchange, jobs=[wrapper(job(id="overflow"))])
        self.assertEqual(exchange.summary()["job_count"], 64)
        for value in (wrapper(claimed_at=float("nan")), wrapper(deadline=float("inf")),
                      wrapper(state="success"), {**wrapper(), "authority": True},
                      json.dumps(wrapper()).replace('"deadline": null', '"deadline": 1e999')):
            with self.subTest(value=str(value)[:50]), self.assertRaises(ContractError):
                publish(exchange, jobs=[value])

    def test_wait_and_construction_bounds_summary_no_authority_or_io(self):
        for kwargs in ({"pending_limit": 0}, {"pending_limit": 3}, {"pending_limit": True},
                       {"max_operations": 129}, {"max_operations": 1.0}):
            with self.assertRaises(ContractError):
                ReflectiveExchange(**kwargs)
        exchange = ReflectiveExchange()
        publish(exchange)
        for value in (-1, 40.1, True, False, float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ContractError):
                exchange.next_job(mission_id="mission-a", reflector_id="reflector-a", wait_seconds=value)
        exchange.offer(command())
        summary = exchange.summary()
        self.assertFalse(summary["grants_authority"])
        self.assertNotIn("trajectory", canonical(summary))
        self.assertNotIn("retained", canonical(summary))
        tree = ast.parse(inspect.getsource(reflection))
        imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertFalse(set(imported) & {"sqlite3", "subprocess", "http", "harness.controller"})
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr in ("Thread", "start", "connect", "open")
                             for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
