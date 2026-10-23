"""Decision presentation preserves canonical records and complete selected evidence."""
from copy import deepcopy
import unittest
from unittest.mock import Mock

from harness.player_tools import PlayerTools
from harness.player_view import decision_view


def snapshot():
    coincident = dict(progress={"steps": [1, 2]}, last_receipt={"status": "unknown"},
        native={"state": {"actions": ["keep"], "scene": {"unknown": True}, "ui": "keep"}})
    return dict(snapshot_id="chosen-snapshot", grants_authority=False,
        mission=dict(mission_id="mission", epoch=4, actor={"id": "successor"},
            phase="paused", cause="unknown delivery", objective={"text": "original objective"},
            progress={"history": ["original-progress"]}, last_receipt=dict(id="receipt-original",
                native_request_json='{"keys":["open"]}', native_ack={"complete": "raw ack"},
                transport_disposition="unknown", processing_error="Original ack unavailable",
                evidence_loss=True, logical_request_id="logical-original", native_request_id="native-original",
                source_before={"observation_id": "before"}, source_after={"observation_id": "after"},
                published=True, reason="Original response lost", custody={"generation": 5},
                future_receipt_field={"progress": "keep", "native_ack": "keep nested value"}),
            prompt_phase=None, lifecycle_phase={"id": "lifecycle"}, activity_phase={"id": "activity"},
            current_source={"observation_id": "source"}, active_operation="operation-original",
            active_skill={"kind": "direct"}, limits={"inputs": 12}, remaining={"inputs": 2},
            deadline=1234, reserve={"inputs": 1}, unfinished=["required-work"],
            unknown_effects=[{"operation_id": "operation-original", "delivery": "unknown"}],
            diagnostic="Original response lost", ownership={"lease": None, "player": "successor"},
            reflection={"pending": ["job"]}, memory_version=9, memory=deepcopy(coincident),
            metrics={"spent_inputs": 10}, extra_future_field={"complete": True}),
        native=dict(state=dict(actions=["open"], scene={"position": [1, 2, 0]},
            ui={"menu": "visible"}, session="session", revision=8, boundary={"id": "boundary"},
            health={"status": "healthy"}, extra_future_field={"keep": True}),
            frozen=True, pause_requested=True, pause_generation=5, operator_pause_generation=2,
            pending={"operation_id": "operation-original"}, control_pending=None,
            connection="connected", error="historical diagnostic"),
        source=dict(reference=dict(observation_id="source", session="session", revision=8,
            frame_path="original.png", frame_sha256="original-hash"), observation=dict(
                actions=["open"], scene={"position": [1, 2, 0]}, ui={"menu": "visible"},
                memory=deepcopy(coincident)), disposition="retained", grants_authority=False))


def expected_snapshot(value):
    expected = deepcopy(value)
    del expected["mission"]["last_receipt"]["native_request_json"]
    del expected["mission"]["last_receipt"]["native_ack"]
    for key in ("actions", "scene", "ui"):
        del expected["native"]["state"][key]
    return expected


class DecisionViewTests(unittest.TestCase):
    def test_snapshot_removes_only_declared_duplicates_and_keeps_exact_source(self):
        original = snapshot()
        expected = expected_snapshot(original)
        expected["presentation_schema"] = "player-view/1"
        view = decision_view("enactive_snapshot", original)
        self.assertEqual(view, expected)
        self.assertEqual(view["source"], original["source"])
        self.assertNotIn("presentation_schema", view["source"])
        self.assertEqual(view["mission"]["progress"], original["mission"]["progress"])

    def test_projection_never_mutates_or_aliases_full_result_or_handle_cache(self):
        original = snapshot()
        client = Mock()
        client.status.return_value = dict(mission=original["mission"], **original["native"])
        client.source.return_value = (original["source"], b"exact original PNG bytes")
        player = PlayerTools(client)
        full, png = player.call("enactive_snapshot", {})
        before = deepcopy((full, player.snapshots, player.sources, client.status.return_value))
        view = decision_view("enactive_snapshot", full)
        self.assertEqual((full, player.snapshots, player.sources, client.status.return_value), before)
        view["mission"]["memory"]["progress"]["steps"].append(3)
        view["source"]["observation"]["actions"].append("changed")
        view["native"]["state"]["health"]["status"] = "changed"
        view["mission"]["last_receipt"]["custody"]["generation"] = 99
        self.assertEqual((full, player.snapshots, player.sources, client.status.return_value), before)
        self.assertEqual(png, b"exact original PNG bytes")
        self.assertIn("last_receipt", player.snapshots[full["snapshot_id"]])

    def test_operation_results_keep_unknown_delivery_and_all_complete_payloads(self):
        payload = dict(progress=["required"], last_receipt={"delivery": "unknown"},
            next_snapshot=snapshot(), mission=snapshot()["mission"], native=snapshot()["native"])
        for state in ("unknown", "pending", "completed", "interrupted", "failed"):
            with self.subTest(state=state):
                original = dict(transport="uncertain", settled=False, operation_id="operation-original",
                    status="unresolved", reason="Original submission response lost",
                    response=dict(operation=dict(id="operation-original", request_id="request-original",
                        state=state, result=deepcopy(payload), receipts=[{"id": "receipt-original"}]),
                        context=deepcopy(payload), handoff=deepcopy(payload), reflection=deepcopy(payload),
                        proposal=deepcopy(payload)), next_snapshot=snapshot(), diagnostic="retained")
                expected = deepcopy(original)
                expected["next_snapshot"] = expected_snapshot(original["next_snapshot"])
                expected["presentation_schema"] = "player-view/1"
                for tool in ("start", "result", "skill", "lifecycle", "observe", "remember", "correct",
                             "handoff", "stop", "reconcile", "claim", "readmit", "context"):
                    with self.subTest(tool=tool):
                        self.assertEqual(decision_view("enactive_" + tool, original), expected)

    def test_only_exact_nonnull_enclosing_result_can_replace_progress(self):
        current = snapshot()
        progress = current["mission"]["progress"]
        original = dict(operation_id="stable-operation", response=dict(operation=dict(
            id="different-nested-id", result=deepcopy(progress))), next_snapshot=current)
        before = deepcopy(original)
        expected = expected_snapshot(current)
        del expected["mission"]["progress"]
        expected["mission"]["progress_operation_id"] = "stable-operation"
        view = decision_view("enactive_result", original)
        self.assertEqual(view["next_snapshot"], expected)
        self.assertEqual(view["response"], original["response"])
        self.assertEqual(original, before)
        # Without an enclosing operation, a standalone snapshot keeps progress.
        self.assertEqual(decision_view("enactive_snapshot", current)["mission"]["progress"], progress)

    def test_pending_missing_and_different_results_keep_current_progress(self):
        for response in (None, {}, {"operation": None}, {"operation": {"state": "pending", "result": None}},
                         {"operation": {"state": "completed", "result": {"history": ["other-progress"]}}}):
            with self.subTest(response=response):
                current = snapshot()
                original = dict(transport="uncertain", settled=False, operation_id="original-operation",
                                response=response, next_snapshot=current)
                view = decision_view("enactive_result", original)
                self.assertEqual(view["next_snapshot"], expected_snapshot(current))
                self.assertEqual(view["response"], response)
                self.assertNotIn("progress_operation_id", view["next_snapshot"]["mission"])

    def test_progress_deduplication_does_not_equate_json_booleans_and_numbers(self):
        for progress, result in (({"count": True}, {"count": 1}), ({"count": 1}, {"count": 1.0})):
            with self.subTest(progress=progress, result=result):
                current = snapshot()
                current["mission"]["progress"] = progress
                view = decision_view("enactive_result", dict(operation_id="original-operation",
                    response={"operation": {"result": result}}, next_snapshot=current))
                self.assertEqual(view["next_snapshot"]["mission"]["progress"], progress)

    def test_equal_progress_without_operation_identity_is_retained(self):
        for identity in ({}, {"operation_id": None}):
            current = snapshot()
            original = dict(**identity, response={"operation": {
                "result": deepcopy(current["mission"]["progress"])}}, next_snapshot=current)
            view = decision_view("enactive_result", original)
            self.assertEqual(view["next_snapshot"]["mission"]["progress"], current["mission"]["progress"])
            self.assertNotIn("progress_operation_id", view["next_snapshot"]["mission"])

    def test_source_failure_preserves_the_only_returned_visible_state(self):
        original = snapshot()
        client = Mock()
        client.status.return_value = dict(mission=original["mission"], **original["native"])
        client.source.side_effect = OSError("Retained source temporarily unavailable")
        full, png = PlayerTools(client).call("enactive_snapshot", {})
        self.assertIsNone(full["source"])
        self.assertIsNone(png)
        view = decision_view("enactive_snapshot", full)
        self.assertEqual(view["native"], full["native"])
        self.assertEqual(view["source_error"], full["source_error"])

    def test_different_latest_native_view_is_not_a_duplicate_of_selected_source(self):
        for field, changed in (("actions", ["new action"]), ("scene", {"position": [2, 2, 0]}),
                               ("ui", {"menu": "changed"})):
            with self.subTest(field=field):
                current = snapshot()
                current["native"]["state"][field] = changed
                view = decision_view("enactive_snapshot", current)
                self.assertEqual(view["native"], current["native"])
                self.assertEqual(view["source"], current["source"])

    def test_source_advice_and_reflection_roots_are_complete_even_with_coincident_names(self):
        original = snapshot()
        original.update(next_snapshot=snapshot(), progress=["keep"], last_receipt={"keep": True})
        expected = deepcopy(original)
        expected["presentation_schema"] = "player-view/1"
        for tool in ("source", "advice", "reflect_next", "reflect_submit", "reflect_source", "reflect_result"):
            with self.subTest(tool=tool):
                self.assertEqual(decision_view("enactive_" + tool, original), expected)

    def test_no_mission_or_native_state_and_snapshot_errors_remain_explicit(self):
        for current in (dict(snapshot_id=None, mission=None, native={"state": None}, source=None,
                             grants_authority=False, source_error="Original image unavailable"),
                        dict(snapshot_id="s", mission={"phase": "admitted"}, native={}, source=None)):
            with self.subTest(current=current):
                expected = dict(deepcopy(current), presentation_schema="player-view/1")
                self.assertEqual(decision_view("enactive_snapshot", current), expected)
        error = dict(transport="uncertain", settled=False, operation_id="original",
                     response=None, snapshot_error="Status unavailable")
        self.assertEqual(decision_view("enactive_result", error),
                         dict(error, presentation_schema="player-view/1"))


if __name__ == "__main__":
    unittest.main()
