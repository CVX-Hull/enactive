"""Synthetic providers test the port contract, never model or native performance."""
from dataclasses import FrozenInstanceError, replace
import json
import threading
import time
import unittest

from harness.gameplay.contracts import (
    Budgets, ContractError, EvidencePacket, EvidenceRef, PlanCandidate, SkillDescriptor, TaskSpec,
)
from harness.gameplay.evaluation import RunRecorder, validate_run
from harness.gameplay.planner import (
    PlannerConfig, PlannerPort, PlanningRequest, ProviderInput, ProviderReply, ProviderUsage,
)


class Clock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value


def task(**changes):
    values = dict(task_id="task", session="world", origin=(0, 0, 0), direction="north",
                  distance=4, target=(0, -4, 0), task_version=1,
                  budgets=Budgets(spend_usd=10), operator_request_id="operator")
    return TaskSpec(**(values | changes))


def evidence(**changes):
    values = dict(observation_id="observation", session="world", revision=7,
                  timestamp_ms=1000, received_monotonic=100.0, turn=4,
                  frame_path="synthetic/frame.png", frame_sha256="a" * 64,
                  boundary_kind="normal_play")
    return EvidenceRef(**(values | changes))


def skill(**changes):
    values = dict(skill_id="cardinal", skill_version=1, task_kinds=("waypoint_return",),
                  stage_kinds=("outbound", "return"), contexts=("normal_play",),
                  action_bindings=("UP",), observable_predicates=("clear",),
                  allowed_primitives=("step",), postconditions=("displacement",),
                  stop_rules=("creature",), maximum_budgets=Budgets())
    return SkillDescriptor(**(values | changes))


def request(**changes):
    ref = evidence()
    packet = EvidencePacket("task", "plan", "stage", ref, ref, None, None, None, None,
                            None, Budgets(spend_usd=10), (), ())
    values = dict(task=task(), packet=packet, skills=(skill(),), plan_version=1,
                  execution_epoch=1, expected_stage="outbound", distance_remaining=4,
                  admission_monotonic=100.0)
    return PlanningRequest(**(values | changes))


def candidate(**changes):
    values = dict(candidate_id="candidate", task_id="task", task_version=1, plan_id="plan",
                  plan_version=1, execution_epoch=1, evidence_session="world", evidence_revision=7,
                  stage="outbound", direction="north", distance_remaining=4,
                  skill_id="cardinal", skill_version=1, reason="Synthetic route")
    return PlanCandidate(**(values | changes))


def reply(value=None, usage=None):
    return ProviderReply(json.dumps((value or candidate()).to_dict()),
                         usage if usage is not None else ProviderUsage(100, 20, 0, 0.05))


class Gate:
    def __init__(self, result=None):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.cancelled = None
        self.snapshot = None
        self.result = result if result is not None else reply()
        self.count = 0

    def __call__(self, snapshot, cancelled):
        self.count += 1
        self.snapshot, self.cancelled = snapshot, cancelled
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError("Synthetic provider not released")
        return self.result


class PlannerTests(unittest.TestCase):
    def port(self, provider=None, config=None, clock=None, spec=None, admission=100.0):
        clock = clock if clock is not None else Clock()
        port = PlannerPort(spec or task(), config or PlannerConfig("fixture-model", "config",
                           reservation_usd_per_call=0.1, spend_ceiling_usd=10),
                           provider or (lambda snapshot, cancelled: reply()),
                           admission_monotonic=admission, clock=clock)
        self.addCleanup(port.close)
        return port

    def gated(self, result=None, **options):
        gate = Gate(result)
        port = self.port(gate, **options)
        self.addCleanup(gate.release.set)
        return port, gate

    def done(self, port):
        deadline = time.monotonic() + 2
        while port.snapshot().physical_call_active:
            if time.monotonic() >= deadline:
                self.fail("Synthetic provider did not complete within two real seconds")
            threading.Event().wait(0.001)
        return port.snapshot()

    def test_valid_data_only_snapshot_and_exact_candidate(self):
        port, gate = self.gated()
        req = request(public_context="Public context")
        call = port.submit(req)
        self.assertTrue(gate.entered.wait(1))
        self.assertIs(type(gate.snapshot), ProviderInput)
        self.assertEqual(json.loads(gate.snapshot.request_json)["public_context"], "Public context")
        self.assertEqual(gate.snapshot.max_input_tokens, 32768)
        with self.assertRaises(FrozenInstanceError):
            gate.snapshot.max_output_tokens = 1
        gate.release.set()
        snap = self.done(port)
        self.assertEqual(port.poll(call, req.binding).candidate, candidate())
        self.assertEqual(snap.committed_usd, 0.05)
        self.assertEqual(snap.unresolved_reservation_usd, 0)
        event = snap.evaluation_events()[0]
        event["payload"]["cost_usd"] = 999
        self.assertEqual(snap.evaluation_events()[0]["payload"]["cost_usd"], 0.05)

    def test_configuration_and_origin_validate_strict_bounds(self):
        for changes in ({"max_calls": 11}, {"max_calls": True}, {"max_context_bytes": 1048577},
                        {"max_reply_bytes": 0}, {"max_input_tokens": 1048577},
                        {"max_output_tokens": 0}, {"call_timeout_seconds": float("nan")},
                        {"reservation_usd_per_call": -1}, {"spend_ceiling_usd": float("inf")},
                        {"mode": "unknown"}, {"credentials_available": 1}, {"model_id": ""}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                PlannerConfig(**({"model_id": "fixture", "configuration_id": "config"} | changes))
        for origin in (101, -1, float("nan"), float("inf"), True):
            with self.subTest(origin=origin), self.assertRaises(ContractError):
                self.port(admission=origin)
        port = self.port()
        with self.assertRaises(FrozenInstanceError):
            request().public_context = "mutated"
        for req in (replace(request(), admission_monotonic=99),
                    replace(request(), task=task(operator_request_id="replacement"))):
            with self.assertRaises(ContractError):
                port.submit(req)
        self.assertEqual(len(port.snapshot().evaluation_events()), 0)

    def test_request_relationships_before_invocation(self):
        req = request()
        for changes in ({"skills": ()}, {"skills": [skill()]}, {"skills": (skill(), skill())},
                        {"plan_version": True}, {"execution_epoch": -1},
                        {"distance_remaining": 0}, {"expected_stage": "return"},
                        {"public_context": "x" * 4097},
                        {"packet": replace(req.packet, task_id="other")},
                        {"packet": replace(req.packet, current=evidence(boundary_kind="menu", turn=None))},
                        {"packet": replace(req.packet, current=evidence(session="other"),
                                           start=evidence(session="other"))},
                        {"skills": (skill(stage_kinds=("return",)),)}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                replace(req, **changes)

    def test_wrong_candidate_schema_identity_and_semantics(self):
        mutations = [{"schema": "gameplay/1"}, {"extra": True}, {"candidate_id": ""},
                     {"execution_epoch": True}, {"distance_remaining": 2},
                     {"direction": "south"}, {"stage": "return", "direction": "south"},
                     {"task_id": "other"}, {"task_version": 2}, {"plan_id": "other"},
                     {"plan_version": 2}, {"execution_epoch": 2},
                     {"evidence_session": "other"}, {"evidence_revision": 8},
                     {"skill_id": "unaccepted"}, {"skill_version": 2},
                     {"reason": "x" * 1025}, {"distance_remaining": float("nan")}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                data = candidate().to_dict() | mutation
                port = self.port(lambda snapshot, cancelled: ProviderReply(json.dumps(data)))
                call = port.submit(request())
                self.done(port)
                self.assertEqual(port.poll(call, request().binding).status, "failed")
                self.assertIsNone(port.poll(call, request().binding).candidate)

    def test_serialized_reply_bounds_duplicate_fields_and_wrong_types(self):
        values = (b"x" * 16385, '{"a":1,"a":2}', "[]", {}, b"\xff", 'NaN')
        for value in values:
            with self.subTest(value=str(value)[:30]):
                port = self.port(lambda snapshot, cancelled: ProviderReply(value))
                call = port.submit(request())
                self.done(port)
                self.assertEqual(port.poll(call, request().binding).status, "failed")
        port = self.port(config=PlannerConfig("fixture", "config", max_context_bytes=100))
        with self.assertRaisesRegex(ContractError, "context"):
            port.submit(request())
        self.assertEqual(port.snapshot().calls, ())

    def test_return_stage_and_partial_remaining_exactness(self):
        req = request()
        req = replace(req, expected_stage="return", distance_remaining=2,
                      packet=replace(req.packet, waypoint=evidence()))
        port = self.port(lambda snapshot, cancelled: reply(candidate(stage="return",
                                         direction="south", distance_remaining=2)))
        call = port.submit(req)
        self.done(port)
        self.assertEqual(port.poll(call, req.binding).candidate.distance_remaining, 2)

    def test_network_missing_credentials_pricing_or_approved_budget_disables_calls(self):
        base = PlannerConfig("network-model-v1", "config", mode="network",
                             credentials_available=True, bounded_pricing=True,
                             operator_approved_spend=True, reservation_usd_per_call=0.1,
                             spend_ceiling_usd=1)
        for changes in ({"credentials_available": False}, {"bounded_pricing": False},
                        {"operator_approved_spend": False}, {"spend_ceiling_usd": 0},
                        {"reservation_usd_per_call": 0}):
            with self.subTest(changes=changes):
                gate = Gate()
                port = self.port(gate, replace(base, **changes))
                with self.assertRaises(ContractError):
                    port.submit(request())
                self.assertEqual(gate.count, 0)
                self.assertEqual(port.snapshot().evaluation_events(), ())
        # Still a fake callable: selecting network mode never invokes an SDK here.
        port = self.port(config=base)
        port.submit(request())
        self.assertEqual(len(self.done(port).calls), 1)

    def test_concurrent_submit_reserves_once(self):
        port, gate = self.gated()
        barrier = threading.Barrier(3)
        results, errors = [], []
        def submit():
            barrier.wait()
            try:
                results.append(port.submit(request()))
            except ContractError as exc:
                errors.append(str(exc))
        threads = [threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(1)
            self.assertFalse(thread.is_alive())
        self.assertEqual((len(results), len(errors)), (1, 1))
        self.assertTrue(gate.entered.wait(1))
        self.assertEqual(gate.count, 1)
        self.assertEqual(port.snapshot().committed_usd, 0.1)
        gate.release.set()
        self.done(port)

    def test_stuck_timeout_holds_physical_slot_and_late_settlement_never_revives(self):
        clock = Clock()
        port, gate = self.gated(clock=clock)
        call = port.submit(request())
        self.assertTrue(gate.entered.wait(1))
        clock.value = 131
        self.assertEqual(port.poll(call, request().binding).status, "timed_out")
        self.assertTrue(gate.cancelled.is_set())
        for _ in range(70):
            with self.assertRaisesRegex(ContractError, "Physical"):
                port.submit(request())
        pending = port.snapshot()
        self.assertEqual(len(pending.rejections), 64)
        self.assertEqual(pending.rejection_count, 70)
        self.assertEqual(pending.dropped_rejection_count, 6)
        self.assertEqual(len(pending.evaluation_events()), 1)
        self.assertEqual(pending.committed_usd, 0.1)
        self.assertTrue(pending.calls[0].duration_censored)
        clock.value = 132
        gate.release.set()
        settled = self.done(port)
        self.assertEqual(settled.committed_usd, 0.05)
        self.assertEqual(settled.calls[0].stop_monotonic, 131)
        self.assertEqual(settled.calls[0].completed_monotonic, 132)
        self.assertEqual(settled.calls[0].settled_monotonic, 132)
        self.assertIsNone(port.poll(call, request().binding).candidate)
        self.assertEqual(port.poll(call, request().binding).status, "timed_out")

    def test_cancel_close_and_stale_binding_race_completion(self):
        for operation in ("cancel", "close", "stale"):
            for finish_first in (False, True):
                with self.subTest(operation=operation, finish_first=finish_first):
                    port, gate = self.gated()
                    req = request()
                    call = port.submit(req)
                    self.assertTrue(gate.entered.wait(1))
                    if finish_first:
                        gate.release.set()
                        self.done(port)
                    if operation == "cancel":
                        port.cancel(call)
                    elif operation == "close":
                        start = time.monotonic()
                        port.close()
                        self.assertLess(time.monotonic() - start, 0.1)
                    else:
                        changed = replace(req.binding, execution_epoch=2)
                        self.assertEqual(port.poll(call, changed).status, "stale")
                    self.assertTrue(gate.cancelled.is_set())
                    gate.release.set()
                    self.done(port)
                    self.assertIsNone(port.poll(call, req.binding).candidate)
                    self.assertNotEqual(port.poll(call, req.binding).status, "completed")
                    if operation == "close":
                        with self.assertRaises(ContractError):
                            port.submit(req)
                    if operation == "cancel":
                        self.assertEqual(port.snapshot().evaluation_events()[0]["payload"]["status"], "unknown")

    def test_completion_checks_deadline_without_poll_and_real_wait_is_bounded(self):
        clock = Clock()
        port, gate = self.gated(clock=clock)
        call = port.submit(request())
        self.assertTrue(gate.entered.wait(1))
        clock.value = 130
        gate.release.set()
        self.done(port)
        self.assertEqual(port.poll(call, request().binding).status, "timed_out")
        # Real monotonic clock proves production does not depend on a test counter.
        origin = time.monotonic()
        config = PlannerConfig("fixture", "config", call_timeout_seconds=0.02,
                               reservation_usd_per_call=0.1, spend_ceiling_usd=10)
        port, gate = self.gated(clock=time.monotonic, admission=origin, config=config)
        req = replace(request(), admission_monotonic=origin)
        call = port.submit(req)
        self.assertTrue(gate.entered.wait(1))
        threading.Event().wait(0.03)
        self.assertEqual(port.poll(call, req.binding).status, "timed_out")
        start = time.monotonic()
        port.close()
        self.assertLess(time.monotonic() - start, 0.1)
        gate.release.set()
        self.done(port)

    def test_delayed_first_submit_and_continuation_never_reset_origin(self):
        clock = Clock(221)
        port = self.port(clock=clock)
        with self.assertRaisesRegex(ContractError, "budget"):
            port.submit(request())
        self.assertEqual(port.snapshot().admission_monotonic, 100)
        clock = Clock()
        port = self.port(clock=clock)
        port.submit(request())
        self.done(port)
        clock.value = 221
        with self.assertRaises(ContractError):
            port.submit(replace(request(), execution_epoch=2))
        self.assertEqual(len(port.snapshot().calls), 1)

    def test_declared_remaining_call_time_and_spend_ceilings_cannot_replenish(self):
        req = request()
        for name, value in (("planner_calls", 1), ("spend_usd", 0.1), ("wall_seconds", 2),
                            ("turns", 1)):
            with self.subTest(ceiling=name):
                clock = Clock()
                config = PlannerConfig("fixture", "config", reservation_usd_per_call=0.1,
                                       spend_ceiling_usd=10)
                port = self.port(lambda snapshot, cancelled: reply(usage=ProviderUsage(1, 1, 0, 0.1)),
                                 config, clock)
                limited = replace(req, packet=replace(req.packet,
                                  remaining_budgets=replace(req.packet.remaining_budgets,
                                                            **{name: value})))
                port.submit(limited)
                self.done(port)
                if name == "wall_seconds":
                    clock.value = 103
                continued = replace(req, execution_epoch=2)
                if name == "turns":
                    continued = replace(continued, packet=replace(req.packet,
                                         current=evidence(turn=5)))
                with self.assertRaises(ContractError):
                    port.submit(continued)
                self.assertEqual(len(port.snapshot().calls), 1)

    def test_original_lifetime_calls_spend_and_declared_remaining_admission(self):
        req = request()
        spec = task(budgets=Budgets(planner_calls=1, spend_usd=0.1))
        port = self.port(spec=spec)
        port.submit(replace(req, task=spec))
        self.done(port)
        with self.assertRaises(ContractError):
            port.submit(replace(req, task=spec, execution_epoch=2))
        for limits in ({"planner_calls": 0}, {"wall_seconds": 0}, {"planner_call_seconds": 0},
                       {"spend_usd": 0.09}, {"primitives": 0}, {"turns": 0}):
            with self.subTest(limits=limits):
                port = self.port()
                limited = replace(req, packet=replace(req.packet,
                    remaining_budgets=replace(req.packet.remaining_budgets, **limits)))
                with self.assertRaises(ContractError):
                    port.submit(limited)
                self.assertEqual(port.snapshot().evaluation_events(), ())
        port = self.port(lambda snapshot, cancelled: reply())
        for number in range(10):
            port.submit(replace(req, execution_epoch=number))
            self.done(port)
        with self.assertRaises(ContractError):
            port.submit(req)
        self.assertEqual(len(port.snapshot().calls), 10)

    def test_missing_malformed_and_failed_usage_retains_reservation(self):
        for usage in (None, {"cost_usd": 0}, ProviderUsage(True, 2, 0, 0.05),
                      ProviderUsage(1, 2, 2, 0.05), ProviderUsage(1, 2, 0, float("nan")),
                      ProviderUsage(1, 2, 0, -1), ProviderUsage(1, 2, 0, 10**1000),
                      ProviderUsage(1, 2, 0, None)):
            with self.subTest(usage=usage):
                port = self.port(lambda snapshot, cancelled: ProviderReply(
                    json.dumps(candidate().to_dict()), usage))
                port.submit(request())
                snap = self.done(port)
                self.assertEqual(snap.committed_usd, 0.1)
                self.assertEqual(snap.unresolved_reservation_usd, 0.1)
                self.assertIsNone(snap.calls[0].observed_usage.cost_usd)
                self.assertIsNone(snap.calls[0].settled_monotonic)
                self.assertIsNotNone(snap.calls[0].completed_monotonic)
        def failed(snapshot, cancelled):
            raise RuntimeError("secret credential never public")
        port = self.port(failed)
        call = port.submit(request())
        snap = self.done(port)
        self.assertEqual(port.poll(call, request().binding).status, "failed")
        self.assertNotIn("secret", str(snap))
        self.assertEqual(snap.committed_usd, 0.1)

    def test_valid_cost_settles_independently_from_missing_token_metrics(self):
        port = self.port(lambda snapshot, cancelled: reply(usage=ProviderUsage(cost_usd=0.03)))
        port.submit(request())
        snap = self.done(port)
        self.assertEqual(snap.committed_usd, 0.03)
        self.assertEqual(snap.unresolved_reservation_usd, 0)
        payload = snap.evaluation_events()[0]["payload"]
        self.assertIsNone(payload["input_tokens"])
        self.assertIsNotNone(payload["input_tokens_missing_reason"])
        self.assertEqual(payload["cost_usd"], 0.03)
        self.assertIsNone(payload["cost_usd_missing_reason"])

    def test_adapter_cost_and_token_bound_faults_freeze_future_calls(self):
        for usage in (ProviderUsage(100, 20, 0, 0.3), ProviderUsage(40000, 20, 0, 0.05),
                      ProviderUsage(100, 3000, 0, 0.05)):
            with self.subTest(usage=usage):
                port = self.port(lambda snapshot, cancelled: reply(usage=usage))
                call = port.submit(request())
                snap = self.done(port)
                self.assertTrue(snap.frozen)
                self.assertEqual(snap.calls[0].observed_usage, usage)
                self.assertEqual(snap.calls[0].overshoot_usd, max(0, usage.cost_usd - 0.1))
                self.assertEqual(port.poll(call, request().binding).status, "failed")
                with self.assertRaisesRegex(ContractError, "frozen"):
                    port.submit(request())

    def test_metrics_outside_evaluation_range_still_freeze_and_preserve_reservation(self):
        for usage, overshoot in ((ProviderUsage(10**12 + 1, 20, None, 0.05), 0),
                                 (ProviderUsage(100, 20, None, 10**9 + 1), 10**9 + 1 - 0.1),
                                 (ProviderUsage(100, 20, None, 10**1000), None),
                                 (ProviderUsage(100, 20, None, float("inf")), None)):
            with self.subTest(usage=usage):
                port = self.port(lambda snapshot, cancelled: reply(usage=usage))
                call = port.submit(request())
                snap = self.done(port)
                self.assertTrue(snap.frozen)
                self.assertEqual(port.poll(call, request().binding).status, "failed")
                self.assertEqual(snap.unresolved_reservation_usd, 0.1)
                self.assertEqual(snap.committed_usd, 0.1)
                self.assertIsNone(snap.calls[0].settled_monotonic)
                self.assertEqual(snap.calls[0].overshoot_usd, overshoot)
                self.assertEqual(snap.calls[0].overshoot_missing_reason is not None,
                                 overshoot is None)
                payload = snap.evaluation_events()[0]["payload"]
                self.assertIsNone(payload["cost_usd"])
                self.assertIsNotNone(payload["cost_usd_missing_reason"])
                with self.assertRaisesRegex(ContractError, "frozen"):
                    port.submit(request())

    def test_contradictory_overbound_usage_cannot_settle_finances(self):
        for cost in (0.05, 0.3):
            with self.subTest(cost=cost):
                usage = ProviderUsage(40000, 20, 40001, cost)
                port = self.port(lambda snapshot, cancelled: reply(usage=usage))
                call = port.submit(request())
                snap = self.done(port)
                self.assertTrue(snap.frozen)
                self.assertEqual(port.poll(call, request().binding).status, "failed")
                self.assertEqual(snap.committed_usd, 0.1)
                self.assertEqual(snap.unresolved_reservation_usd, 0.1)
                self.assertIsNone(snap.calls[0].observed_usage.cost_usd)
                self.assertIsNone(snap.calls[0].settled_monotonic)
                self.assertEqual(snap.calls[0].overshoot_usd, max(0, cost - 0.1))
                with self.assertRaisesRegex(ContractError, "frozen"):
                    port.submit(request())

    def test_initial_start_evidence_and_turn_budget_cannot_be_replaced(self):
        req = request()
        port = self.port()
        port.submit(req)
        self.done(port)
        replacements = (evidence(turn=36), evidence(observation_id="replacement"),
                        evidence(timestamp_ms=1001))
        for start in replacements:
            with self.subTest(start=start):
                packet = replace(req.packet, start=start, current=start)
                with self.assertRaisesRegex(ContractError, "start"):
                    port.submit(replace(req, packet=packet, execution_epoch=2))
                self.assertEqual(len(port.snapshot().calls), 1)
        # Keeping the original anchor still enforces the original 32-turn ceiling.
        packet = replace(req.packet, current=evidence(turn=36))
        with self.assertRaises(ContractError):
            port.submit(replace(req, packet=packet, execution_epoch=2))
        packet = replace(req.packet, current=evidence(turn=5))
        port.submit(replace(req, packet=packet))
        self.done(port)
        self.assertEqual(len(port.snapshot().calls), 2)

    def test_completed_duration_independent_unknown_cost_and_reporting_cutoff(self):
        clock = Clock()
        port, gate = self.gated(ProviderReply(json.dumps(candidate().to_dict())), clock=clock)
        call = port.submit(request())
        self.assertTrue(gate.entered.wait(1))
        clock.value = 101
        gate.release.set()
        self.done(port)
        clock.value = 160
        snap = port.snapshot(cutoff_monotonic=160)
        self.assertEqual(snap.calls[0].completed_monotonic, 101)
        self.assertFalse(snap.calls[0].duration_censored)
        self.assertEqual(snap.evaluation_events()[0]["payload"]["duration_ms"], 1000)
        self.assertEqual(snap.evaluation_events()[0]["elapsed_ms"], 1000)
        self.assertIsNone(snap.evaluation_events()[0]["payload"]["cost_usd"])
        self.assertEqual(port.poll(call, request().binding).status, "completed")
        for cutoff in (159, 161, float("nan")):
            with self.assertRaises(ContractError):
                port.snapshot(cutoff_monotonic=cutoff)

    def test_generated_events_validate_with_real_recorder_for_each_lifecycle(self):
        for lifecycle in ("complete", "missing", "cancel", "timeout", "stale", "failed", "pending",
                          "huge_tokens", "huge_cost", "infinite_cost", "contradictory_overrun"):
            with self.subTest(lifecycle=lifecycle):
                clock = Clock()
                value = ProviderReply("invalid") if lifecycle == "failed" else reply()
                if lifecycle == "missing":
                    value = ProviderReply(json.dumps(candidate().to_dict()))
                if lifecycle == "huge_tokens":
                    value = reply(usage=ProviderUsage(10**12 + 1, 20, None, 0.05))
                elif lifecycle == "huge_cost":
                    value = reply(usage=ProviderUsage(100, 20, None, 10**9 + 1))
                elif lifecycle == "infinite_cost":
                    value = reply(usage=ProviderUsage(100, 20, None, float("inf")))
                elif lifecycle == "contradictory_overrun":
                    value = reply(usage=ProviderUsage(40000, 20, 40001, 0.05))
                port, gate = self.gated(value, clock=clock)
                call = port.submit(request())
                self.assertTrue(gate.entered.wait(1))
                clock.value = 101
                if lifecycle == "cancel":
                    port.cancel(call)
                elif lifecycle == "timeout":
                    clock.value = 131
                    port.poll(call, request().binding)
                elif lifecycle == "stale":
                    port.poll(call, replace(request().binding, evidence_revision=8))
                if lifecycle != "pending":
                    gate.release.set()
                    self.done(port)
                clock.value = 160
                snap = port.snapshot(cutoff_monotonic=160)
                manifest = dict(run_id=lifecycle, scenario_id="fixture", family_id="fixture",
                    protocol_version="fixture/1", start_description="Synthetic planner calls",
                    split="development", lane="synthetic", condition="bounded_skill",
                    source_commit="a" * 40, native_build=None, native_build_missing_reason="Fixture",
                    model_id="fixture-model", model_id_missing_reason=None,
                    configuration_id="config", configuration_id_missing_reason=None,
                    budgets=dict(primitives=8, turns=32, wall_ms=120000, model_calls=10,
                                 model_call_ms=30000, input_tokens=32768, input_tokens_missing_reason=None,
                                 output_tokens=2048, output_tokens_missing_reason=None,
                                 cost_usd=10, cost_usd_missing_reason=None),
                    admission=dict(monotonic_ms=snap.admission_monotonic * 1000,
                                   session="world", game_turn=4, game_turn_missing_reason=None), evidence=[])
                recorder = RunRecorder(manifest)
                for event in snap.evaluation_events():
                    recorder.record(event)
                recorder.finish(dict(disposition="unknown", elapsed_ms=60000, session="world",
                    game_turn=None, game_turn_missing_reason="No game running", verified_steps=0,
                    verified_steps_missing_reason=None, first_useful_action_event_id=None,
                    first_useful_action_missing_reason="No action dispatched", harmful_actions=None,
                    harmful_actions_missing_reason="Unassessed", deaths=None,
                    deaths_missing_reason="Unassessed", evidence=[],
                    assessment=dict(assessor="fixture", method="Synthetic lifecycle test")))
                result = validate_run(recorder.to_dict())
                self.assertEqual(len(result["events"]), 1)
                gate.release.set()
                self.done(port)

    def test_external_mode_reports_unknown_usage_and_requires_zero_api_spend(self):
        for changes in ({"reservation_usd_per_call": 0.1}, {"spend_ceiling_usd": 1}):
            with self.assertRaises(ContractError):
                PlannerConfig("external-unreported", "external-chat-v1", mode="external", **changes)
        config = PlannerConfig("external-unreported", "external-chat-v1", mode="external")
        port, gate = self.gated(ProviderReply(json.dumps(candidate().to_dict()), ProviderUsage()), config=config)
        call = port.submit(request())
        self.assertTrue(gate.entered.wait(1))
        self.assertEqual(gate.snapshot.mode, "external")
        deadline = port.deadline(call)
        self.assertEqual(deadline, 130)
        gate.release.set()
        snapshot = self.done(port)
        self.assertEqual(port.poll(call, request().binding).status, "completed")
        self.assertEqual(snapshot.committed_usd, 0)
        self.assertEqual(snapshot.unresolved_reservation_usd, 0)
        self.assertEqual(snapshot.calls[0].observed_usage, ProviderUsage())
        for name in ("input_tokens", "output_tokens", "cached_input_tokens", "cost_usd"):
            payload = snapshot.evaluation_events()[0]["payload"]
            self.assertIsNone(payload[name])
            self.assertIn("unmeasured", payload[name + "_missing_reason"])


if __name__ == "__main__":
    unittest.main()
