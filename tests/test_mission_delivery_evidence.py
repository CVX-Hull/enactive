"""Unknown-input custody over real file transport, not native gameplay evidence."""
import copy
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from harness.controller import Controller, ControlError, atomic_json, read_json
from tests.test_controller import ControlBridge, FakeBridge, recovery_state


class MissionDeliveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.controller = Controller(Path(tmp.name), timeout=0.8)
        self.addCleanup(lambda: self.controller.close())
        with FakeBridge(self.controller):
            self.assertEqual(self.controller.execute("observe")["status"], "ready")
            self.assertEqual(self.controller.execute("resume")["status"], "ready")

    def unknown(self, *, claimed=False):
        """Exercise actual admission/timeout; a controlled consumer may claim it."""
        c = self.controller
        result = []
        def exchange():
            result.append(c._exchange("action", 0.08, generation=c.pause_generation, action="RIGHT"))
        if claimed:
            worker = threading.Thread(target=exchange)
            worker.start()
            try:
                end = time.monotonic() + 1
                while not (c.bridge / "request.json").exists() and time.monotonic() < end:
                    time.sleep(0.001)
                (c.bridge / "request.json").rename(c.bridge / "claimed.json")
            finally:
                worker.join(2)
            self.assertFalse(worker.is_alive())
        else:
            exchange()
        self.assertEqual(result[0]["status"], "timeout")
        return copy.deepcopy(c.unknown_outcomes[-1]["request"])

    def binding(self, request):
        c = self.controller
        return dict(expected_request=request, expected_controller_boot_id=c.authority["controller_boot_id"],
            expected_operator_generation=c.operator_pause_generation, expected_generation=c.pause_generation,
            expected_takeover_generation=c.state["takeover_generation"], deadline_monotonic=time.monotonic() + 1)

    def proof(self, request, **changes):
        values = self.binding(request)
        values.update(changes)
        return self.controller.inspect_mission_delivery(**values)

    def terminal(self, request, **changes):
        c = self.controller
        value = copy.deepcopy(c.state)
        value.update(id=request["id"], revision=request["revision"] + 1, status="ready", paused=True,
            pause_origin="recovery", timestamp_ms=int(time.time() * 1000))
        value.update(changes)
        atomic_json(c.bridge / "response.json", value)
        return value

    def test_exact_unclaimed_rename_is_evidence_without_any_controller_rearm(self):
        c = self.controller
        request = self.unknown()
        original = (copy.deepcopy(c.unknown_outcomes), copy.deepcopy(c.pending), copy.deepcopy(c.authority),
                    c.journal.read_bytes(), c.state.copy(), c.pause_generation)
        proof = self.proof(request)
        self.assertEqual(proof["basis"], "unclaimed_retirement")
        self.assertEqual(read_json(c.bridge / proof["retirement"]), request)
        self.assertIsNone(proof["result"])
        self.assertFalse(proof["grants_authority"])
        self.assertEqual((c.unknown_outcomes, c.pending, c.authority, c.journal.read_bytes(), c.state, c.pause_generation), original)
        self.assertTrue(c.frozen and c.pause_requested)
        self.assertIsNone(c._mission_lease)
        self.assertTrue((c.admissions / f'{request["id"]}.json').exists())

    def test_claimed_or_missing_inbox_is_ambiguous_even_with_a_fresh_frame(self):
        c = self.controller
        request = self.unknown(claimed=True)
        (c.bridge / "claimed.json").unlink()
        self.assertIsNone(self.proof(request))
        self.assertEqual(c.unknown_outcomes[-1]["status"], "unknown")
        self.assertEqual(c.pending, request)
        self.assertIsNone(c._mission_lease)

    def test_retirement_proof_requires_the_actual_renamed_contents(self):
        c = self.controller
        request = self.unknown()
        retired, _ = c._retired_mission_inputs[(False, request["id"])]
        atomic_json(retired, {**request, "action": "LEFT"})
        with self.assertRaisesRegex(ControlError, "Retired inbox differs"):
            self.proof(request)
        self.assertEqual(c.unknown_outcomes[-1]["request"], request)

    def test_late_terminal_is_captured_before_observe_without_accepting_it_as_current(self):
        c = self.controller
        request = self.unknown(claimed=True)
        terminal = self.terminal(request)
        old_state = copy.deepcopy(c.state)
        proof = self.proof(request)
        self.assertEqual(proof["basis"], "terminal_response")
        self.assertEqual(proof["result"], terminal)
        self.assertEqual(c.state, old_state)
        self.assertTrue(c.frozen)
        (c.bridge / "claimed.json").unlink()
        with FakeBridge(c) as bridge:
            bridge.value = copy.deepcopy(terminal)
            self.assertEqual(c.execute("observe")["status"], "ready")
            self.assertEqual([r["kind"] for r in bridge.requests], ["observe"])
        self.assertNotEqual(read_json(c.bridge / "response.json")["id"], request["id"])
        retained = self.proof(request)
        self.assertEqual(retained, proof)
        self.assertTrue(c.pause_requested)
        self.assertIsNone(c._mission_lease)
        self.assertEqual(c.unknown_outcomes[-1]["status"], "unknown")

    def test_observe_without_prior_collection_does_not_invent_the_overwritten_ack(self):
        c = self.controller
        request = self.unknown(claimed=True)
        terminal = self.terminal(request)
        (c.bridge / "claimed.json").unlink()
        with FakeBridge(c) as bridge:
            bridge.value = terminal
            self.assertEqual(c.execute("observe")["status"], "ready")
        self.assertIsNone(self.proof(request))
        self.assertTrue(c.pause_requested)

    def test_dispatched_progress_is_not_terminal_delivery_proof(self):
        request = self.unknown(claimed=True)
        self.terminal(request, status="dispatched", frame_ok=False, frame="")
        self.assertIsNone(self.proof(request))

    def test_wrong_uuid_never_correlates_even_if_state_and_revision_match(self):
        request = self.unknown(claimed=True)
        self.terminal(request, id=str(uuid.uuid4()))
        self.assertIsNone(self.proof(request))

    def test_terminal_proof_rejects_regressing_revision_new_world_or_takeover(self):
        request = self.unknown(claimed=True)
        for changes in ({"revision": request["revision"]}, {"session": "another-world"},
                        {"takeover_generation": request["takeover_generation"] + 1}):
            with self.subTest(changes=changes):
                self.terminal(request, **changes)
                with self.assertRaisesRegex(ControlError, "changed session/takeover or regressed"):
                    self.proof(request)

    def test_resampling_takeover_cannot_rebind_the_original_input(self):
        c = self.controller
        request = self.unknown(claimed=True)
        c.state["takeover_generation"] += 1
        self.terminal(request, takeover_generation=c.state["takeover_generation"])
        with self.assertRaisesRegex(ControlError, "original unknown/Pause"):
            self.proof(request)

    def test_actual_terminal_is_collected_when_it_arrives_within_the_bounded_window(self):
        request = self.unknown(claimed=True)
        published = threading.Event()
        def late():
            time.sleep(0.03)
            self.terminal(request)
            published.set()
        writer = threading.Thread(target=late)
        writer.start()
        try:
            proof = self.proof(request)
        finally:
            writer.join(1)
        self.assertTrue(published.is_set())
        self.assertEqual(proof["basis"], "terminal_response")

    def test_io_delay_cannot_admit_a_terminal_after_the_collection_cutoff(self):
        c = self.controller
        request = self.unknown(claimed=True)
        self.terminal(request)
        read = read_json
        for target in ("response.json", f'{request["id"]}.json'):
            def slow_read(path):
                if path.name == target:
                    time.sleep(0.28)
                return read(path)
            with self.subTest(target=target), patch("harness.controller.read_json", side_effect=slow_read):
                self.assertIsNone(self.proof(request))
            self.assertNotIn((False, request["id"]), c._mission_delivery_evidence)
        self.assertEqual(c.unknown_outcomes[-1]["status"], "unknown")

    def test_pause_while_collecting_invalidates_the_original_mark(self):
        c = self.controller
        request = self.unknown(claimed=True)
        read = read_json
        def pause_on_response(path):
            value = read(path)
            if path.name == "response.json":
                c.pause()
            return value
        with patch("harness.controller.read_json", side_effect=pause_on_response):
            with self.assertRaisesRegex(ControlError, "original unknown/Pause"):
                self.proof(request)
        self.assertTrue(c.pause_requested)
        self.assertIsNone(c._mission_lease)

    def test_receipt_uses_the_same_clock_sample_as_its_cutoff_check(self):
        request = self.unknown()
        binding = self.binding(request)
        binding["deadline_monotonic"] = 101
        # A later sample would cross the fixed100.25 collection cutoff.
        samples = [100, 100, 100, 100, 100, 100.249, 100.3]
        with patch("harness.controller.time.monotonic", side_effect=samples):
            proof = self.controller.inspect_mission_delivery(**binding)
        self.assertEqual(proof["received_monotonic"], 100.249)
        self.assertLess(proof["received_monotonic"], 100.25)
        self.assertEqual(self.controller._mission_delivery_evidence[(False, request["id"])], proof)

    def test_original_deadline_and_both_channel_locks_bound_collection(self):
        c = self.controller
        request = self.unknown(claimed=True)
        with self.assertRaisesRegex(ControlError, "deadline exhausted"):
            self.proof(request, deadline_monotonic=time.monotonic() - 1)
        for lock in (c.command_lock, c.control_lock):
            with lock:
                started = time.monotonic()
                with self.assertRaisesRegex(ControlError, "writer is active"):
                    self.proof(request)
                self.assertLess(time.monotonic() - started, 0.2)

    def test_cached_proof_is_copied_does_not_refresh_its_clock_and_dies_at_reboot(self):
        c = self.controller
        request = self.unknown()
        proof = self.proof(request)
        received = proof["received_monotonic"]
        proof["request"]["action"] = "LEFT"
        retained = self.proof(request)
        self.assertEqual(retained["request"], request)
        self.assertEqual(retained["received_monotonic"], received)
        old_binding = self.binding(request)
        c.close()
        self.controller = Controller(c.root, timeout=0.8)
        with self.assertRaisesRegex(ControlError, "original unknown/Pause"):
            self.controller.inspect_mission_delivery(**old_binding)

    def test_different_or_missing_admission_cannot_supply_a_proof(self):
        c = self.controller
        request = self.unknown()
        path = c.admissions / f'{request["id"]}.json'
        for wrong in ({**request, "action": "LEFT"}, None):
            if wrong is None: path.unlink()
            else: atomic_json(path, wrong)
            with self.assertRaisesRegex(ControlError, "exact durable admission"):
                self.proof(request)

    def test_late_control_ack_retains_owner_and_never_retires_or_accepts_it(self):
        c = self.controller
        c.state = recovery_state("activity_poll")
        with ControlBridge(c, publish=False) as bridge:
            result = c.recover("request_interrupt", timeout=0.04,
                expected_session=c.state["session"], expected_control_generation=0)
            self.assertEqual(result["status"], "unknown")
            self.assertTrue(bridge.committed.wait(1))
            request = copy.deepcopy(bridge.requests[0])
        native = recovery_state("interrupt_confirmation", owner=request["id"],
                                generation=1, revision=c.state["revision"] + 1)
        terminal = {"protocol": 4, "id": request["id"], "status": "prompt_opened", "error": "", "state": native}
        atomic_json(c.bridge / "control-response.json", terminal)
        original = copy.deepcopy(c.state)
        proof = self.proof(request)
        self.assertEqual(proof["result"], terminal)
        self.assertEqual(c.state, original)
        self.assertEqual(c.control_pending, request)
        self.assertIn(request["id"], c.control_admitted)
        self.assertTrue(c.pause_requested)


if __name__ == "__main__":
    unittest.main()
