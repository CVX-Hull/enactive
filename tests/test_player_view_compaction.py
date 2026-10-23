"""Synthetic presentation fixtures; these establish no gameplay or host latency."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock

from harness.player_tools import DETAIL_SECTIONS, PlayerTools
from harness.player_view import decision_view


def representative_snapshot():
    """Normal play with a full vocabulary and technical receipt, without runtime I/O."""
    observation = dict(category="DEFAULTMODE", in_game=True, actions=[
        f"registered_engine_action_{number:03d}" for number in range(80)],
        boundary=dict(kind="normal_play", id="boundary", recovery_operations=[]),
        scene=dict(position=[1, 2, 0], visible_creatures=[dict(name="zombie", hostile=True)]),
        ui=None, status="ready", error="", paused=False, frame_ok=True,
        session="session", revision=8)
    receipt = dict(logical_action_id="logical", native_request_id="native", kind="key", value="UP",
        published=True, transport_disposition="returned", reason="Native input returned",
        processing_error=None, evidence_loss=None,
        expected_session="session", expected_revision=7, expected_boundary_id="previous-boundary",
        dispatch_binding=dict(controller_boot_id="controller", operator_pause_generation=2,
            takeover_generation=1, actor_id="player", epoch=4, game_anchor_source_id="anchor"),
        source_before="before", preflight_source="preflight", source_after="after",
        received_monotonic=1234.5, native_request_json='{"id":"native","key":"UP"}',
        native_ack=dict(status="ready", error="", revision=8))
    return dict(snapshot_id="selected", grants_authority=False,
        mission=dict(mission_id="mission", epoch=4, phase="active", current_source={"observation_id": "after"},
            configuration=dict(source_commit="pin", native_sha256="digest", model="chosen-model",
                effort="low", skills=["direct", "navigate"], lessons=["retained configuration lesson"]),
            last_receipt=receipt, progress=dict(outcome="partial", next="Find shelter"),
            metrics=dict(game_seconds=30, primitives=4, model_time_seconds=None),
            limits=dict(primitives=12), remaining=dict(primitives=8), reserve=dict(primitives=1),
            deadline=12345, unfinished=["Find shelter"], unknown_effects=[]),
        native=dict(state=deepcopy(observation), frozen=False, pause_requested=False,
            pause_generation=2, operator_pause_generation=2, pending=None,
            control_pending=None, connection="connected", error=None),
        source=dict(reference=dict(observation_id="after", session="session", revision=8),
            observation=observation, disposition="retained", grants_authority=False))


def serialized_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


class PlayerViewCompactionTests(unittest.TestCase):
    def test_normal_vocabulary_and_configuration_are_only_in_exact_detail(self):
        original = representative_snapshot()
        client = Mock()
        client.status.return_value = dict(mission=original["mission"], **original["native"])
        client.source.return_value = (original["source"], b"exact selected image")
        player = PlayerTools(client)
        full, image = player.call("enactive_snapshot", {})
        before = deepcopy((full, player.snapshots, player.sources, client.status.return_value))
        view = decision_view("enactive_snapshot", full)
        self.assertNotIn("configuration", view["mission"])
        self.assertNotIn("actions", view["native"]["state"])
        self.assertNotIn("actions", view["source"]["observation"])
        self.assertEqual(view["detail_sections"], list(DETAIL_SECTIONS))
        for section, exact in dict(configuration=full["mission"]["configuration"],
                receipt=full["mission"]["last_receipt"], native=full["native"], source=full["source"]).items():
            detail, _ = player.call("enactive_detail", dict(snapshot_id=full["snapshot_id"], section=section))
            self.assertEqual(decision_view("enactive_detail", detail)["detail"], exact)
            self.assertEqual(serialized_bytes(detail["detail"]), serialized_bytes(exact))
        source, source_image = player.call("enactive_source", dict(mission_id="mission", source_id="after"))
        self.assertEqual(decision_view("enactive_source", source)["observation"], original["source"]["observation"])
        self.assertEqual(image, source_image)
        view["source"]["observation"]["scene"]["visible_creatures"][0]["name"] = "changed"
        view["mission"]["last_receipt"]["reason"] = "changed"
        self.assertEqual((full, player.snapshots, player.sources, client.status.return_value), before)

    def test_normal_vocabulary_is_omitted_from_both_differing_views_and_native_without_source(self):
        for missing_source in (False, True):
            with self.subTest(missing_source=missing_source):
                original = representative_snapshot()
                original["native"]["state"]["scene"]["position"] = [2, 2, 0]
                if missing_source:
                    original.update(source=None, source_error="Selected source unavailable")
                view = decision_view("enactive_snapshot", original)
                self.assertNotIn("actions", view["native"]["state"])
                self.assertEqual(view["native"]["state"]["scene"], original["native"]["state"]["scene"])
                if missing_source:
                    self.assertEqual(view["source_error"], original["source_error"])
                else:
                    self.assertNotIn("actions", view["source"]["observation"])
                    self.assertEqual(view["source"]["observation"]["scene"], original["source"]["observation"]["scene"])

    def test_contextual_controls_and_rows_survive_even_for_defaultmode_menu(self):
        for category, in_game, kind, ui in (
                ("YESNO", True, "menu", None), ("DEFAULTMODE", True, "menu", None),
                ("DEFAULTMODE", False, "normal_play", None),
                ("DEFAULTMODE", True, "normal_play", dict(rows=[dict(text="Choose", hotkey="y")])),
                ("UILIST", True, "menu", dict(rows=[dict(text="Cancel", hotkey="ESC")]))):
            with self.subTest(category=category, in_game=in_game, kind=kind, ui=ui):
                original = representative_snapshot()
                observed = original["source"]["observation"]
                observed.update(category=category, in_game=in_game, ui=ui, actions=["YES", "NO", "QUIT"])
                observed["boundary"]["kind"] = kind
                original["native"]["state"] = deepcopy(observed)
                view = decision_view("enactive_snapshot", original)
                self.assertEqual(view["source"]["observation"], observed)

    def test_unknowns_pause_limits_feedback_and_unique_operation_result_survive(self):
        original = representative_snapshot()
        mission = original["mission"]
        mission.update(phase="paused", cause="Original user Pause", unknown_effects=["logical"],
            unfinished=["Reconcile unknown delivery"], next_needed_decision="Explicit reconciliation required")
        receipt = mission["last_receipt"]
        receipt.update(transport_disposition="unknown", reason="Original reply lost",
            processing_error="Original processing failed", evidence_loss="Original frame unavailable",
            future_status=dict(delivery="unknown"),
            control=dict(request=dict(protocol=6, id="native"), result=dict(status="unknown", state=None)))
        original["native"].update(frozen=True, pause_requested=True, pending={"operation_id": "unresolved"},
            error="Original connection unavailable")
        operation = dict(id="unresolved", state="unknown", result=dict(outcome="unknown", required="Observe"))
        result = dict(operation_id="unresolved", transport="uncertain", settled=False,
            response=dict(operation=operation), next_snapshot=original)
        view = decision_view("enactive_result", result)
        current = view["next_snapshot"]
        self.assertEqual(view["response"], result["response"])
        self.assertEqual(current["native"], {**original["native"], "state": {
            key: value for key, value in original["native"]["state"].items() if key not in ("actions", "scene", "ui")}})
        for field in ("progress", "phase", "cause", "unknown_effects", "unfinished", "limits", "remaining",
                      "reserve", "deadline", "next_needed_decision", "current_source"):
            self.assertEqual(current["mission"][field], mission[field])
        self.assertEqual(current["mission"]["metrics"], dict(game_seconds=30, primitives=4))
        summary = current["mission"]["last_receipt"]
        for field in ("transport_disposition", "reason", "processing_error", "evidence_loss", "published",
                      "logical_action_id", "native_request_id", "kind", "value", "future_status"):
            self.assertEqual(summary[field], receipt[field])
        for field in ("dispatch_binding", "native_request_json", "native_ack", "source_before", "preflight_source",
                      "source_after", "expected_session", "expected_revision", "expected_boundary_id", "received_monotonic"):
            self.assertNotIn(field, summary)
        self.assertNotIn("request", summary["control"])
        self.assertEqual(summary["control"]["result"], receipt["control"]["result"])

    def test_canonical_dedup_compares_original_vocabulary_before_omitting_it(self):
        original = representative_snapshot()
        original["native"]["state"]["actions"] = ["DIFFERENT"]
        view = decision_view("enactive_snapshot", original)
        for field in ("scene", "ui"):
            self.assertEqual(view["native"]["state"][field], original["native"]["state"][field])
        self.assertNotIn("actions", view["native"]["state"])


if __name__ == "__main__":
    unittest.main()
