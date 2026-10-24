"""Decision presentation preserves canonical records and complete selected evidence."""
from copy import deepcopy
import unittest
from unittest.mock import Mock

from harness.player_tools import DETAIL_SECTIONS, PlayerTools
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
            current_source={"observation_id": "source", "frame_sha256": "retained-pin"}, active_operation="operation-original",
            active_skill={"kind": "direct"}, limits={"inputs": 12}, remaining={"inputs": 2},
            deadline=1234, reserve={"inputs": 1}, unfinished=["required-work"],
            unknown_effects=[{"operation_id": "operation-original", "delivery": "unknown"}],
            diagnostic="Original response lost", ownership={"lease": None, "player": "successor"},
            reflection={"pending": ["job"]}, memory_version=9, memory=deepcopy(coincident),
            configuration=dict(source_commit="source-pin", native_sha256="native-pin", model="chosen-model",
                effort="low", skills=["direct"], lessons=["original-lesson"]),
            native_process=dict(owner_mission_id="mission", restored_from_disk=True,
                unresolved_custody_requests=["unresolved-request"], last_sample=dict(pid=123, launch_id="launch",
                    running=False, outcome="unknown", returncode=None, error="Original exit unavailable")),
            spent_inputs=10, remaining_limits={"inputs": 2}, cleanup_reserve={"inputs": 1},
            unreconciled=["unknown-operation"], next_needed_decision="Explicit supported transition required",
            metrics={"game_seconds": None, "primitives": 10, "model_time_seconds": None, "archive": {"bytes": 20}},
            extra_future_field={"complete": True}),
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
    expected["detail_sections"] = list(DETAIL_SECTIONS)
    expected.pop("grants_authority", None)
    expected["read_only"] = True
    for name in ("configuration", "objective", "epoch", "deadline"):
        expected["mission"].pop(name, None)
    expected["mission"]["metrics"] = dict(game_seconds=None, primitives=10)
    expected["mission"]["current_source"] = {"observation_id": "source"}
    expected["mission"]["native_process"]["last_sample"] = dict(running=False, outcome="unknown",
        returncode=None, error="Original exit unavailable")
    expected["source"]["reference"] = dict(observation_id="source", session="session", revision=8)
    del expected["mission"]["last_receipt"]["native_request_json"]
    del expected["mission"]["last_receipt"]["native_ack"]
    del expected["mission"]["last_receipt"]["source_before"]
    del expected["mission"]["last_receipt"]["source_after"]
    for key in ("actions", "scene", "ui"):
        del expected["native"]["state"][key]
    return expected


class DecisionViewTests(unittest.TestCase):
    def test_program_state_uses_exact_detail_only_when_that_snapshot_preserves_it(self):
        result = dict(program=dict(status="yield", state={"continuation": "x" * 500}, reason="novel view"))
        original = dict(operation_id="program-original", response=dict(operation=dict(result=deepcopy(result))),
                        next_snapshot=snapshot())
        original["next_snapshot"]["mission"]["progress"] = deepcopy(result)
        player = PlayerTools(Mock())
        player.snapshots["chosen-snapshot"] = deepcopy(original["next_snapshot"])
        projected = decision_view("enactive_skill", original)
        self.assertNotIn("state", projected["response"]["operation"]["result"]["program"])
        self.assertIn("state_detail", projected["response"]["operation"]["result"]["program"])
        self.assertEqual(player.detail("chosen-snapshot", "progress")["detail"], result)
        self.assertEqual(original["response"]["operation"]["result"], result)
        # A later collection may have a different current operation. Its
        # snapshot cannot address the original continuation: retain it inline.
        original["next_snapshot"]["mission"]["progress"] = {"different": "operation"}
        projected = decision_view("enactive_result", original)
        self.assertEqual(projected["response"]["operation"]["result"], result)

    def test_snapshot_keeps_decisions_unknowns_and_visible_source_with_detail_addresses(self):
        original = snapshot()
        expected = expected_snapshot(original)
        expected["presentation_schema"] = "player-view/4"
        view = decision_view("enactive_snapshot", original)
        self.assertEqual(view, expected)
        self.assertEqual(view["source"]["observation"], original["source"]["observation"])
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
        self.assertEqual(player.snapshots[full["snapshot_id"]], full)

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
                expected["presentation_schema"] = "player-view/4"
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
                self.assertEqual(view["source"]["observation"], current["source"]["observation"])

    def test_source_advice_and_reflection_roots_are_complete_even_with_coincident_names(self):
        original = snapshot()
        original.update(next_snapshot=snapshot(), progress=["keep"], last_receipt={"keep": True})
        expected = deepcopy(original)
        expected["presentation_schema"] = "player-view/4"
        for tool in ("source", "detail", "advice", "reflect_next", "reflect_submit", "reflect_source", "reflect_result"):
            with self.subTest(tool=tool):
                self.assertEqual(decision_view("enactive_" + tool, original), expected)

    def test_no_mission_or_native_state_and_snapshot_errors_remain_explicit(self):
        for current in (dict(snapshot_id=None, mission=None, native={"state": None}, source=None,
                             grants_authority=False, source_error="Original image unavailable"),
                        dict(snapshot_id="s", mission={"phase": "admitted"}, native={}, source=None)):
            with self.subTest(current=current):
                expected = dict(deepcopy(current), presentation_schema="player-view/4", read_only=True)
                expected.pop("grants_authority", None)
                if current["snapshot_id"] is not None:
                    expected["detail_sections"] = list(DETAIL_SECTIONS)
                self.assertEqual(decision_view("enactive_snapshot", current), expected)
        error = dict(transport="uncertain", settled=False, operation_id="original",
                     response=None, snapshot_error="Status unavailable")
        self.assertEqual(decision_view("enactive_result", error),
                         dict(error, presentation_schema="player-view/4"))

    def test_reflection_inventory_and_mechanical_clocks_move_to_exact_mission_detail(self):
        current = snapshot()
        current["mission"].update(started_at=100, last_wall=101, remaining_wall_seconds=99,
            remaining_inputs=2, last_context_id="previous-packet", grants_authority=False,
            reflection=dict(jobs=[{"id": "old-job", "state": "unknown"}], proposals=["old-proposal"],
                phase="active", pending=1, job_count=1, proposal_count=1,
                operation_states={"unknown": 1}, reason="Retained unreviewed work", unreviewed_requests=4),
            lease_owner=dict(actor_id="successor", operation="interaction", session="session", epoch=4,
                mission_id="mission", pause_generation=5, takeover_generation=0))
        client = Mock()
        player = PlayerTools(client)
        player.snapshots["chosen-snapshot"] = deepcopy(current)
        view = decision_view("enactive_snapshot", current)
        self.assertTrue(view["read_only"])
        self.assertNotIn("grants_authority", view)
        for field in ("objective", "started_at", "deadline", "last_wall", "remaining_wall_seconds",
                      "remaining_inputs", "last_context_id", "epoch", "grants_authority"):
            self.assertNotIn(field, view["mission"])
        self.assertEqual(view["mission"]["lease_owner"], {"actor_id": "successor", "operation": "interaction"})
        self.assertEqual(view["mission"]["reflection"], dict(phase="active", pending=1, job_count=1,
            proposal_count=1, operation_states={"unknown": 1}, reason="Retained unreviewed work", unreviewed_requests=4))
        self.assertEqual(view["mission"]["unreconciled"], current["mission"]["unreconciled"])
        self.assertEqual(view["mission"]["unknown_effects"], current["mission"]["unknown_effects"])
        self.assertEqual(view["mission"]["remaining_limits"], current["mission"]["remaining_limits"])
        self.assertEqual(view["mission"]["cleanup_reserve"], current["mission"]["cleanup_reserve"])
        self.assertEqual(player.detail("chosen-snapshot", "mission")["detail"], current["mission"])
        self.assertEqual(client.mock_calls, [])

    def test_equal_native_metadata_lives_in_source_but_changed_capture_and_unknown_fields_remain(self):
        current = snapshot()
        for visible in (current["native"]["state"], current["source"]["observation"]):
            visible.update(category="MENU", boundary={"kind": "menu", "id": "same-boundary"},
                in_game=True, paused=True, revision=8, session="session", frame_ok=True,
                frame_geometry={"width": 960}, timestamp_ms=100)
        current["native"]["state"]["timestamp_ms"] = 110
        before = deepcopy(current)
        view = decision_view("enactive_snapshot", current)
        self.assertEqual(view["source"]["observation"], current["source"]["observation"])
        self.assertEqual(view["native"]["state"], dict(timestamp_ms=110, health={"status": "healthy"},
            extra_future_field={"keep": True}))
        self.assertEqual(current, before)
        # A changed visible view cannot borrow the source's metadata body.
        current["native"]["state"]["ui"] = {"menu": "changed"}
        self.assertEqual(decision_view("enactive_snapshot", current)["native"], current["native"])

    def test_transport_omissions_are_scoped_and_partial_visible_views_stay_complete(self):
        reference = dict(schema="evidence/5", record_type="observation", frame_path="exact.png",
            frame_sha256="pin", received_monotonic=12, visibility_version=1,
            observation_id="a" * 64, session="session", revision=8, timestamp_ms=123, boundary_kind="prompt",
            turn=10, unknown=True)
        visible = dict(protocol="wire/5", id=18, frame={"raw": "transport"}, frame_ok=False,
            timestamp_ms=123, session="session", revision=8, geometry={"columns": 80},
            actions=["open"], scene={"partial": True}, ui={"error": "Unknown display"})
        current = snapshot()
        current["mission"]["current_source"] = deepcopy(reference)
        current["mission"]["last_receipt"]["source_before"] = deepcopy(reference)
        current["mission"]["last_receipt"]["source_after"] = None
        current["mission"]["memory"] = deepcopy(reference)
        current["native"]["state"] = deepcopy(visible)
        current["source"]["reference"] = deepcopy(reference)
        current["source"]["observation"] = deepcopy(visible)
        # A partial source cannot prove all three native body fields duplicate.
        del current["source"]["observation"]["ui"]
        view = decision_view("enactive_snapshot", current)
        expected_reference = dict(observation_id="a" * 64, session="session", revision=8, timestamp_ms=123,
            boundary_kind="prompt", turn=10, unknown=True)
        self.assertEqual(view["mission"]["current_source"], expected_reference)
        self.assertEqual(view["source"]["reference"], expected_reference)
        self.assertNotIn("source_before", view["mission"]["last_receipt"])
        self.assertNotIn("source_after", view["mission"]["last_receipt"])
        self.assertEqual(view["mission"]["memory"], reference)
        self.assertEqual(view["native"]["state"], {key: value for key, value in visible.items()
            if key not in ("protocol", "id", "frame")})
        self.assertNotIn("frame", view["source"]["observation"])
        self.assertFalse(view["source"]["observation"]["frame_ok"])

    def test_metrics_do_not_invent_available_counters_and_no_mission_keeps_diagnostics(self):
        current = dict(snapshot_id=None, mission=None, source=None, grants_authority=False,
            native=dict(state=dict(protocol="wire/5", id=1, frame=None, frame_ok=False,
                scene={"partial": True}, error="No frame"), error="Disconnected"))
        view = decision_view("enactive_snapshot", current)
        self.assertEqual(view["native"], dict(state=dict(frame_ok=False, scene={"partial": True},
            error="No frame"), error="Disconnected"))
        self.assertNotIn("detail_sections", view)
        current.update(snapshot_id="s", mission={"metrics": {"primitives": None, "model_time_seconds": 9}})
        self.assertEqual(decision_view("enactive_snapshot", current)["mission"]["metrics"], {"primitives": None})


if __name__ == "__main__":
    unittest.main()
