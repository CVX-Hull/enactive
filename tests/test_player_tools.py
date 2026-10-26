"""Real HTTP/runtime adapter fixtures and SDK transport; never native acceptance."""
from copy import deepcopy
import asyncio
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import pytest

from harness.gameplay.contracts import ContractError, validate_json
from harness.gameplay.mission_contracts import MAX_HANDOFF_SOURCES
from harness.gameplay.mission_requests import compose_request
from harness.mission_client import MissionClient
from harness.player_mcp import make_server
from harness.player_tools import DETAIL_SECTIONS, PlayerTools, tool_specs
from harness.player_view import decision_view
from tests import test_mission_http as http_fixture
from tools.configure_player_tools import configure, configuration, describe


class PlayerHTTPTests(unittest.TestCase):
    setUp = http_fixture.MissionHTTPTests.setUp
    request = http_fixture.MissionHTTPTests.request
    raw = http_fixture.MissionHTTPTests.raw
    status = http_fixture.MissionHTTPTests.status
    submit = http_fixture.MissionHTTPTests.submit
    settled = http_fixture.MissionHTTPTests.settled
    start = http_fixture.MissionHTTPTests.start

    def player(self):
        self.start()  # Explicit pre-adopted core fixture, not creation qualification.
        return PlayerTools(MissionClient(self.controller.root))

    def test_lead_admission_is_typed_and_never_adopts_or_launches_implicitly(self):
        player = PlayerTools(MissionClient(self.controller.root))
        delivered = deepcopy(self.bridge.delivered)
        result, image = player.call("enactive_start", dict(request_id="typed-start",
            admission=self.a.to_dict(), wait_seconds=2))
        self.assertTrue(result["settled"], result)
        self.assertEqual(result["next_snapshot"]["mission"]["phase"], "admitted")
        self.assertIsNone(image)
        self.assertIsNone(self.server.mission._lease)
        self.assertEqual(self.bridge.delivered, delivered)

    def navigate(self, snapshot, identity="move"):
        source = snapshot["source"]["reference"]
        return dict(snapshot_id=snapshot["snapshot_id"], request_id=identity, wait_seconds=2,
            scope="new_root", source_id=source["observation_id"], supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=30, game_seconds=10),
            intent=dict(skill_kind="navigate", goal=dict(target=[1, 0, 0]),
                work_id=None, perception=None, procedure=None))

    def test_one_semantic_call_returns_settlement_exact_image_and_duplicate_never_moves_twice(self):
        player = self.player()
        first, image = player.call("enactive_snapshot", {})
        self.assertTrue(image.startswith(b"\x89PNG"))
        full = deepcopy(first)
        handles = deepcopy((player.snapshots, player.sources))
        view = decision_view("enactive_snapshot", first)
        self.assertIn("progress", first["mission"])
        self.assertIn("last_receipt", first["mission"])
        self.assertEqual(view["mission"]["progress"], first["mission"]["progress"])
        self.assertIsNone(first["mission"]["last_receipt"])
        self.assertIsNone(view["mission"]["last_receipt"])
        detail, _ = player.call("enactive_detail", dict(snapshot_id=first["snapshot_id"], section="source"))
        self.assertEqual(detail["detail"], first["source"])
        self.assertEqual(first, full)
        self.assertEqual((player.snapshots, player.sources), handles)
        arguments = self.navigate(first)
        expected = compose_request(first["mission"], request_id=arguments["request_id"],
            intent=dict(kind="skill", **arguments["intent"]), limits=arguments["limits"],
            scope=arguments["scope"], source=first["source"], supporting_source_ids=[])
        # Presentation and detail reads must not replace the original binding.
        detail["detail"]["reference"]["revision"] = -1
        view["mission"]["epoch"] = -1
        player.client.submit = Mock(wraps=player.client.submit)
        result, image = player.call("enactive_skill", arguments)
        self.assertEqual(player.client.submit.call_args.args[0], expected)
        self.assertTrue(result["settled"], result)
        self.assertEqual(result["response"]["operation"]["state"], "completed")
        self.assertEqual(result["next_snapshot"]["source"]["observation"]["scene"]["position"], [1, 0, 0])
        self.assertEqual(image, Path(result["next_snapshot"]["source"]["reference"]["frame_path"]).read_bytes())
        delivered = deepcopy(self.bridge.delivered)
        duplicate, _ = player.call("enactive_skill", arguments)
        self.assertEqual(duplicate["operation_id"], "move")
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.server.mission.status()["spent_inputs"], 1)

    def test_selected_old_snapshot_after_pause_never_dispatches_or_auto_resumes(self):
        player = self.player()
        selected, _ = player.call("enactive_snapshot", {})
        self.server.mission.pause("Actual user Pause in fixture")
        delivered = deepcopy(self.bridge.delivered)
        result, _ = player.call("enactive_skill", self.navigate(selected))
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertNotEqual(result["response"].get("operation", {}).get("state"), "completed")
        self.assertTrue(self.controller.pause_requested)
        self.assertIsNone(self.server.mission._lease)

    def test_memory_correction_and_context_keep_complete_provenance(self):
        player = self.player()
        current, _ = player.call("enactive_snapshot", {})
        ref = current["source"]["reference"]
        scope = dict(mission_id=self.a.mission_id, session=ref["session"], coordinate_epoch=0)
        entry = dict(key=dict(subject="water", property="supply", unit="items", coverage_id="visible"),
            value=dict(quantity=1, state=None), text="Interpreted water supply", coverage="Visible source only",
            status="current", grounding=dict(kind="source", source_id=None, coordinate_epoch=None),
            supports=[dict(primary=True, sources=[], claims=[])])
        result, _ = player.call("enactive_remember", dict(snapshot_id=current["snapshot_id"],
            request_id="remember", wait_seconds=2, intent=dict(entry_type="claim", entry=entry)))
        self.assertEqual(result["response"]["operation"]["state"], "completed", result)
        original = result["response"]["operation"]["result"]["entry"]
        self.assertEqual(original["scope"], scope)
        self.assertEqual(original["sources"], [ref["observation_id"]])
        self.assertEqual(original["observed_time"], dict(revision=ref["revision"], turn=ref["turn"]))
        corrected = deepcopy(entry)
        corrected.update(text="Previously interpreted value is unverified", status="unknown")
        corrected["value"] = dict(quantity=None, state=None)
        result, _ = player.call("enactive_correct", dict(snapshot_id=result["next_snapshot"]["snapshot_id"],
            request_id="correct", wait_seconds=2, intent=dict(entry_type="claim", entry=corrected,
                retired_ids=[original["id"]], reason="Visible evidence does not establish that quantity")))
        self.assertEqual(result["response"]["operation"]["state"], "completed", result)
        replacement = result["response"]["operation"]["result"]["entry"]
        self.assertEqual(replacement["supersedes"], [original["id"]])
        result, _ = player.call("enactive_context", dict(snapshot_id=result["next_snapshot"]["snapshot_id"],
            intent=dict(scope=dict(session=ref["session"], coordinate_epoch=0), query="water",
                        max_bytes=32768, handoff=None)))
        packet = result["response"]["context"]["packet"]
        self.assertIn(replacement["id"], json.dumps(packet))
        self.assertIn(ref["observation_id"], json.dumps(packet))
        self.assertFalse(packet["grants_authority"])
        before = deepcopy(result)
        projected = decision_view("enactive_context", result)["response"]["context"]
        self.assertNotIn("native_sha256", projected["configuration"])
        for source in projected["packet"]["sources"]:
            self.assertNotIn("frame_sha256", source["reference"])
        self.assertEqual(projected["packet"]["claims"], packet["claims"])
        self.assertEqual(result, before)
        raw_source, raw_image = player.source(self.a.mission_id, ref["observation_id"])
        original_source = deepcopy(raw_source)
        self.assertIn("frame_sha256", raw_source["reference"])
        source_view = decision_view("enactive_source", raw_source)
        self.assertNotIn("frame_sha256", source_view["reference"])
        self.assertEqual(source_view["observation"], raw_source["observation"])
        self.assertEqual(raw_source, original_source)
        self.assertIsInstance(raw_image, bytes)

    @pytest.mark.assurance_ingress
    def test_unknown_delivery_is_preserved_without_retry_or_implicit_input(self):
        player = self.player()
        selected, _ = player.call("enactive_snapshot", {})
        delivered = deepcopy(self.bridge.delivered)
        calls = []
        def ambiguous(request, **options):
            calls.append(request)
            return dict(transport="uncertain", settled=False, operation_id=request["request_id"],
                        response=None, reason="Original submission response lost")
        player.client.submit = ambiguous
        result, _ = player.call("enactive_skill", self.navigate(selected))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["transport"], "uncertain")
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(result["operation_id"], "move")
        view = decision_view("enactive_skill", result)
        self.assertEqual(view["transport"], "uncertain")
        self.assertFalse(view["settled"])
        self.assertIsNone(view["response"])
        self.assertEqual(view["operation_id"], "move")
        self.assertEqual(view["reason"], "Original submission response lost")
        self.assertEqual(view["next_snapshot"]["source"],
            decision_view("enactive_snapshot", result["next_snapshot"])["source"])

    def test_source_must_have_been_returned_and_handles_expire_without_authority(self):
        player = self.player()
        selected, _ = player.call("enactive_snapshot", {})
        arguments = self.navigate(selected)
        player.sources.clear()
        with self.assertRaisesRegex(ContractError, "selected exact source"):
            player.call("enactive_skill", arguments)
        player.snapshots.clear()
        with self.assertRaisesRegex(ContractError, "Snapshot handle unavailable"):
            player.call("enactive_skill", arguments)
        self.assertEqual(self.server.mission.status()["spent_inputs"], 0)


class ActivityPollBindingTests(unittest.TestCase):
    """Real MCP/PlayerTools/SDK staging with synthetic selected checkpoints."""

    def setUp(self):
        from tests.test_player_claims import StagingClient
        from tests.test_mission_request_producer import activity_root
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / ".runtime").mkdir()
        self.backend = StagingClient(self.root)
        self.player = PlayerTools(self.backend)
        self.original = activity_root(consent=False)
        original_json = self.backend._json

        def collect_original(path, *, data=None, **options):
            body = json.loads(data)
            if body["kind"] == "result":
                self.backend.reads.append(body)
                return dict(status="accepted", operation=dict(request=deepcopy(self.original),
                    state="partial", result={}))
            return original_json(path, data=data, **options)
        self.backend._json = collect_original

    def arguments(self, kind="menu", scope="prompt"):
        from tests.test_mission_request_producer import bundle, phase, snapshot
        source = bundle(7, kind=kind)
        self.player.snapshots["selected"] = dict(snapshot_id="selected", native={}, source=source,
            mission=snapshot(phase="active", **{scope + "_phase": phase(source, stage="awaiting_control")}))
        return dict(snapshot_id="selected", scope=scope, source_id=None, supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=7, game_seconds=60),
            intent=dict(skill_kind="activity", goal=dict(step="poll"),
                work_id=None, perception=None, procedure=None))

    def run_client(self, exercise):
        from mcp import Client
        async def run():
            async with Client(make_server(self.player)) as client:
                await exercise(client)
        asyncio.run(run())

    def test_new_poll_on_selected_menu_is_unsubmitted_without_staging_or_refresh(self):
        async def exercise(client):
            for fault in ("menu", "absent", "unread"):
                arguments = self.arguments()
                if fault == "absent":
                    self.player.snapshots["selected"]["source"] = None
                elif fault == "unread":
                    arguments["source_id"] = "unreturned-source"
                selected = deepcopy(self.player.snapshots["selected"])
                with self.subTest(fault=fault), patch.object(self.backend, "_stage", wraps=self.backend._stage) as stage, \
                        patch.object(self.backend, "submit", wraps=self.backend.submit) as submit:
                    reply = await client.call_tool("enactive_skill", arguments)
                    self.assertTrue(reply.is_error)
                    value = json.loads(reply.content[0].text)
                    self.assertEqual(value["submission"], "not_submitted")
                    self.assertNotIn("original_collection", value)
                    self.assertNotIn("next_snapshot", value)
                    if fault == "menu":
                        self.assertIn("Selected checkpoint is not an activity poll", value["error"])
                    stage.assert_not_called()
                    submit.assert_not_called()
                self.assertEqual(self.player.snapshots["selected"], selected)
                self.assertEqual(self.backend.writes, [])
                self.assertEqual(self.backend.events, [])
                self.assertFalse((self.root / ".runtime/mission-requests").exists())
        self.run_client(exercise)
        self.assertEqual(self.backend.reads, [dict(schema="mission/11", kind="result",
            mission_id="mission-test", operation_id="original-root")])

    def test_actual_activity_poll_submits_exact_child_under_selected_original_root(self):
        async def exercise(client):
            for scope in ("prompt", "activity"):
                arguments = self.arguments("activity_poll", scope)
                selected = deepcopy(self.player.snapshots["selected"])
                with self.subTest(scope=scope), patch.object(self.backend, "_stage", wraps=self.backend._stage) as stage:
                    reply = await client.call_tool("enactive_skill", arguments)
                    self.assertFalse(reply.is_error, reply)
                    stage.assert_called_once()
                request = self.backend.writes[-1]
                self.assertEqual(request["goal"], {**self.original["goal"], "step": "poll"})
                self.assertEqual(request["phase_id"], self.original["request_id"])
                self.assertEqual(request["limits"], arguments["limits"])
                self.assertEqual(request["sources"], [selected["source"]["reference"]["observation_id"]])
                self.assertEqual(self.backend.staged_request("mission-test", request["request_id"]), request)
                self.assertEqual(self.player.snapshots["selected"], selected)
        original = deepcopy(self.original)
        self.run_client(exercise)
        self.assertEqual(self.original, original)
        self.assertEqual(len(self.backend.writes), 2)
        self.assertEqual(len(self.backend.reads), 2)


class SnapshotDetailTests(unittest.TestCase):
    def test_source_metadata_supports_handoff_bound_without_expanding_other_caches(self):
        client = Mock()
        client.status.return_value = dict(mission=dict(mission_id="mission", current_source=None))
        client.source.side_effect = lambda mission, source: (
            dict(reference=dict(observation_id=source), disposition="retained", grants_authority=False), b"pixels")
        player = PlayerTools(client)
        for index in range(MAX_HANDOFF_SOURCES):
            player.source("mission", f"source-{index}")
        self.assertEqual(len(player.sources), MAX_HANDOFF_SOURCES)
        self.assertEqual(player._source("mission", "source-0")["reference"]["observation_id"], "source-0")
        player.source("mission", "overflow")
        self.assertEqual(len(player.sources), MAX_HANDOFF_SOURCES)
        before = client.source.call_count
        with self.assertRaisesRegex(ContractError, "selected exact source"):
            player._source("mission", "source-0")
        self.assertEqual(client.source.call_count, before)
        player.source("mission", "source-0")
        self.assertEqual(player._source("mission", "source-0")["reference"]["observation_id"], "source-0")
        for index in range(33):
            player.snapshot()
            player._remember(player.procedures, ("mission", f"revision-{index}"), dict(id=f"revision-{index}"))
        self.assertEqual(len(player.snapshots), 32)
        self.assertEqual(len(player.procedures), 32)
        self.assertNotIn(("mission", "revision-0"), player.procedures)

    def test_pending_and_busy_collection_guidance_preserves_original_mission_and_owner(self):
        client = Mock()
        client.status.return_value = dict(mission=dict(mission_id="later-snapshot", current_source=None))
        player = PlayerTools(client)
        original = dict(request=dict(kind="skill", mission_id="original-mission", request_id="text-owner"),
            state="running", result=None)
        pending = dict(transport="delivered", settled=False, operation_id="text-owner",
            response=dict(status="accepted", operation=original))
        busy = dict(transport="delivered", settled=False, operation_id="rejected-enter",
            response=dict(status="rejected", input_owner_operation_id="text-owner",
                mission=dict(mission_id="original-mission")))
        for envelope in (pending, busy):
            with self.subTest(envelope=envelope):
                result, _ = player._finish(envelope)
                self.assertEqual(result["next_call"], dict(tool="enactive_result", arguments=dict(
                    mission_id="original-mission", operation_id="text-owner")))
                self.assertEqual(result["next_snapshot"]["mission"]["mission_id"], "later-snapshot")
                self.assertIn("never replay or retarget", result["next_step"])
        self.assertEqual(player._finish(busy)[0]["input_admission"], "not_admitted")
        for envelope in (pending, busy):
            uncertain = deepcopy(envelope)
            uncertain.update(transport="uncertain", reason="Original operation unavailable or mismatched")
            result, _ = player._finish(uncertain)
            self.assertNotIn("next_call", result)
            self.assertNotIn("input_admission", result)
            self.assertEqual(result["operation_id"], envelope["operation_id"])
        mismatched = deepcopy(pending)
        mismatched["response"]["operation"]["request"]["request_id"] = "foreign-operation"
        self.assertNotIn("next_call", player._finish(mismatched)[0])
        settled = deepcopy(pending)
        settled.update(settled=True)
        settled["response"]["operation"].update(state="partial", result=dict(reason="Finished text"))
        self.assertNotIn("next_call", player._finish(settled)[0])
        rejected = dict(transport="delivered", settled=False, operation_id="unadmitted",
            response=dict(status="rejected", reason="No matching admission"))
        self.assertNotIn("next_call", player._finish(rejected)[0])
        client.submit.assert_not_called()
        client.collect.assert_not_called()

    def test_certified_refusal_keeps_raw_proof_current_context_and_new_decision_guidance(self):
        client = Mock()
        client.status.return_value = dict(mission=dict(mission_id="current", current_source=None, phase="paused"))
        player = PlayerTools(client)
        envelope = dict(transport="delivered", settled=True, submission="not_admitted", operation_id="refused",
            response=dict(status="rejected", reason="Choose current epoch", admission_refusal=dict(
                schema="mission-refusal/1", request_sha256="raw-sdk-proof"),
                input_owner_operation_id="distinct-busy-owner", mission=dict(mission_id="original")))
        before = deepcopy(envelope)
        result, image = player._finish(envelope)
        self.assertEqual(result["response"]["admission_refusal"], envelope["response"]["admission_refusal"])
        self.assertEqual(result["next_snapshot"]["mission"]["phase"], "paused")
        self.assertIn("new corrected decision", result["next_step"])
        self.assertNotIn("next_call", result)
        self.assertNotIn("input_admission", result)
        self.assertIsNone(image)
        self.assertEqual(envelope, before)
        client.collect.assert_not_called()
        projected = decision_view("enactive_observe", result)
        self.assertNotIn("admission_refusal", projected["response"])
        self.assertEqual(projected["response"]["reason"], "Choose current epoch")

    def test_old_admission_with_explicit_new_menu_source_still_composes(self):
        from tests.test_mission_request_producer import bundle, lifecycle, snapshot
        admission = snapshot(phase="admitted", native_process=dict(last_sample=None))
        menu = bundle(kind="menu")
        client = Mock()
        client.status.return_value = dict(mission=admission)
        client.source.return_value = (menu, b"selected menu image")
        client.submit.return_value = dict(transport="delivered", settled=False,
            operation_id="explicit-menu-source", response=None)
        player = PlayerTools(client)
        selected, _ = player.call("enactive_snapshot", {})
        source_id = menu["reference"]["observation_id"]
        player.call("enactive_source", dict(mission_id=admission["mission_id"], source_id=source_id))
        for operation in ("create", "load"):
            intent = lifecycle(operation)
            del intent["kind"]
            arguments = dict(snapshot_id=selected["snapshot_id"], request_id="explicit-menu-source",
                wait_seconds=1, scope="new_root", source_id=source_id, supporting_source_ids=[],
                limits=dict(primitives=8, wall_seconds=30, game_seconds=60), intent=intent)
            expected = compose_request(admission, request_id=arguments["request_id"],
                intent=dict(kind="lifecycle", **intent), limits=arguments["limits"],
                scope="new_root", source=menu, supporting_source_ids=[])
            client.reset_mock()
            with self.subTest(operation=operation):
                player.call("enactive_lifecycle", arguments)
                client.submit.assert_called_once_with(expected, wait_seconds=1)
                client.source.assert_not_called()
                self.assertEqual(player.snapshots[selected["snapshot_id"]], selected)

    def test_unlaunched_admission_explains_bootstrap_without_refresh_or_implicit_launch(self):
        client = Mock()
        client.staged_request.return_value = None
        client.status.return_value = dict(mission=dict(mission_id="unlaunched", epoch=0,
            phase="admitted", current_source=None, native_process=dict(last_sample=None)))
        player = PlayerTools(client)
        selected, _ = player.call("enactive_snapshot", {})
        before = deepcopy(selected)
        for operation in ("create", "load"):
            arguments = dict(snapshot_id=selected["snapshot_id"], request_id="missing-source", wait_seconds=1,
                scope="new_root", source_id=None, supporting_source_ids=[],
                limits=dict(primitives=8, wall_seconds=30, game_seconds=60),
                intent=dict(operation=operation, world="World", character="Survivor", work_id=None,
                    identity_claim_ids=[]))
            client.reset_mock()
            with self.subTest(operation=operation), self.assertRaisesRegex(ContractError,
                    "operation=launch, source_id=null"):
                player.call("enactive_lifecycle", arguments)
            client.staged_request.assert_called_once_with("unlaunched", "missing-source")
            self.assertEqual(len(client.mock_calls), 1, "Only the original-stage refusal check may run")
            self.assertEqual(player.snapshots[selected["snapshot_id"]], before)

    def test_lifecycle_readmission_misroute_is_actionable_without_submit_or_retarget(self):
        from tests.test_player_view import snapshot
        original = snapshot()
        client = Mock()
        client.staged_request.return_value = None
        client.status.return_value = dict(mission=original["mission"], **original["native"])
        client.source.return_value = (original["source"], b"original PNG")
        player = PlayerTools(client)
        selected, _ = player.call("enactive_snapshot", {})
        identity = selected["snapshot_id"]
        arguments = dict(snapshot_id=identity, request_id="wrong-readmission", wait_seconds=1,
            source_id="selected-source", intent=dict(mode="recovery", phase_id="load-root",
                reconciliation_request_id="load-reconcile", work_id=None,
                limits=dict(primitives=1, wall_seconds=30, game_seconds=60)))
        for operation in ("create", "load", "save", "exit"):
            player.snapshots[identity]["mission"]["lifecycle_phase"] = dict(operation=operation,
                origin_request_id="lifecycle-root", stage="awaiting_identity", grants_authority=False)
            retained = deepcopy(player.snapshots[identity])
            client.reset_mock()
            with self.subTest(operation=operation), self.assertRaisesRegex(ContractError,
                    f"enactive_lifecycle, scope=lifecycle, operation={operation}"):
                player.call("enactive_readmit", arguments)
            client.staged_request.assert_called_once_with(original["mission"]["mission_id"], "wrong-readmission")
            self.assertEqual(len(client.mock_calls), 1, "Only the original-stage refusal check may run")
            self.assertEqual(player.snapshots[identity], retained, "Selected as-of context is unchanged")

    def test_detail_is_exact_as_of_selected_snapshot_without_io_or_mutation_aliases(self):
        from tests.test_player_view import snapshot
        original = snapshot()
        client = Mock()
        client.status.return_value = dict(mission=original["mission"], **original["native"])
        client.source.return_value = (original["source"], b"original PNG")
        player = PlayerTools(client)
        selected, _ = player.call("enactive_snapshot", {})
        identity = selected["snapshot_id"]
        before = deepcopy(selected)
        paths = dict(mission=selected["mission"], configuration=selected["mission"]["configuration"], metrics=selected["mission"]["metrics"],
            receipt=selected["mission"]["last_receipt"], progress=selected["mission"]["progress"],
            native=selected["native"], source=selected["source"])
        paths = deepcopy(paths)
        for section in DETAIL_SECTIONS:
            detail, image = player.call("enactive_detail", dict(snapshot_id=identity, section=section))
            self.assertEqual(detail, dict(snapshot_id=identity, section=section, detail=paths[section],
                                         grants_authority=False))
            self.assertIsNone(image)
        # A later snapshot and changes to the client-owned results cannot retarget
        # the selected handle. Detail must never read status/source/submit.
        client.status.return_value["state"]["revision"] = 99
        client.status.return_value["mission"]["metrics"]["game_seconds"] = 100
        client.source.return_value[0]["observation"]["scene"] = {"newer": True}
        newer, _ = player.call("enactive_snapshot", {})
        self.assertNotEqual(newer["snapshot_id"], identity)
        client.reset_mock()
        for section in DETAIL_SECTIONS:
            detail, _ = player.call("enactive_detail", dict(snapshot_id=identity, section=section))
            self.assertEqual(detail["detail"], paths[section])
            detail["detail"]["mutation"] = True
        self.assertEqual(client.mock_calls, [])
        self.assertEqual(player.snapshots[identity], before)
        self.assertEqual(player._cached_snapshot(identity)["mission"], before["mission"])
        self.assertEqual(len(player.snapshots), 2)

    def test_source_failure_null_sections_and_eviction_are_explicit(self):
        client = Mock()
        client.status.return_value = dict(mission=dict(mission_id="mission", epoch=1,
            current_source={"observation_id": "unavailable"}, last_receipt=None), state={"frame_ok": False})
        client.source.side_effect = OSError("Original source unavailable")
        player = PlayerTools(client)
        selected, image = player.call("enactive_snapshot", {})
        self.assertIsNone(image)
        self.assertEqual(player.snapshots[selected["snapshot_id"]], selected)
        self.assertEqual(selected["source_error"], "Original source unavailable")
        client.reset_mock()
        for section in ("configuration", "metrics", "receipt", "progress", "source"):
            detail, image = player.call("enactive_detail", dict(snapshot_id=selected["snapshot_id"], section=section))
            self.assertIsNone(detail["detail"])
            self.assertFalse(detail["grants_authority"])
            self.assertIsNone(image)
        self.assertEqual(client.mock_calls, [])
        for _ in range(32):
            player.call("enactive_snapshot", {})
        self.assertEqual(len(player.snapshots), 32)
        for identity in (selected["snapshot_id"], "missing"):
            with self.assertRaisesRegex(ContractError, "explicitly read a new snapshot"):
                player.call("enactive_detail", dict(snapshot_id=identity, section="native"))
        with self.assertRaises(ContractError):
            player.call("enactive_detail", dict(snapshot_id=None, section="native"))
        with self.assertRaises(ContractError):
            player.call("enactive_detail", dict(snapshot_id=next(reversed(player.snapshots)), section="unlisted"))
        client.status.return_value = dict(mission=None, state={"error": "No mission"})
        passive, _ = player.call("enactive_snapshot", {})
        self.assertIsNone(passive["snapshot_id"])
        self.assertEqual(len(player.snapshots), 32)


class ProjectConfigurationTests(unittest.TestCase):
    def test_focused_help_keeps_the_actual_direct_input_contract(self):
        schema = describe("enactive_skill", "direct")["input_schema"]
        args = dict(snapshot_id="snapshot",
            scope="new_root", source_id="source", supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=10, game_seconds=10),
            intent=dict(skill_kind="direct", perception=None, procedure=None, work_id=None,
                goal=dict(input=dict(type="key", key="ESC", modifiers=[]),
                    intent="Dismiss current visible dialog", expected="Dialog closes",
                    interrupt_allowed=False)))
        validate_json(args, schema)
        self.assertEqual(schema["properties"]["intent"]["properties"]["perception"], {"type": "null"})
        args["intent"]["perception"] = dict(kind="dismissal", question="Visible dialog")
        with self.assertRaises(ContractError):
            validate_json(args, schema)
        args["intent"]["perception"] = None
        args["intent"]["goal"] = dict(keys=["ESC"])
        with self.assertRaises(ContractError):
            validate_json(args, schema)
        self.assertNotIn("$defs", schema)
        self.assertIn("$defs", describe("enactive_skill", "menu")["input_schema"])
        self.assertIn("$defs", describe("enactive_skill")["input_schema"])
        self.assertEqual(len(describe("enactive_skill")["input_schema"]["properties"]["intent"]["anyOf"]), 9)

    def test_focused_activity_help_exposes_minimal_current_goal_variants(self):
        schema = describe("enactive_skill", "activity")["input_schema"]
        args = dict(snapshot_id="snapshot", scope="new_root", source_id=None, supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=10, game_seconds=60),
            intent=dict(skill_kind="activity", work_id=None, perception=None, procedure=None,
                goal=dict(step="start", operation="rest", target="Exact rest", game_seconds=60,
                    interrupt_allowed=True)))
        validate_json(args, schema)
        start = deepcopy(args["intent"]["goal"])
        for key in ("answer", "interrupt_request_id"):
            args["intent"]["goal"] = {**start, key: None}
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_json(args, schema)
        for step in ("poll", "interrupt", "resume", "answer_interrupt"):
            args["scope"] = "activity"
            goal = dict(step=step, **(dict(answer="YES") if step == "answer_interrupt" else {}))
            args["intent"]["goal"] = goal
            validate_json(args, schema)
            for key, value in start.items():
                if key == "step":
                    continue
                args["intent"]["goal"] = {**goal, key: value}
                with self.subTest(step=step, key=key), self.assertRaises(ContractError):
                    validate_json(args, schema)
            args["intent"]["goal"] = {**goal, "interrupt_request_id": None}
            with self.assertRaises(ContractError):
                validate_json(args, schema)
        args["intent"]["goal"] = dict(step="answer_interrupt", answer=None)
        with self.assertRaises(ContractError):
            validate_json(args, schema)

    def test_focused_help_selects_memory_and_rejects_unknown_variants(self):
        schema = describe("enactive_remember", "claim")["input_schema"]
        self.assertEqual(schema["properties"]["intent"]["properties"]["entry_type"]["const"], "claim")
        for name, variant in (("missing", None), ("enactive_skill", "missing"),
                ("enactive_snapshot", "direct")):
            with self.assertRaises(ValueError):
                describe(name, variant)

    def test_narrow_project_table_preserves_other_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".codex").mkdir()
            path = root / ".codex" / "config.toml"
            original = b'model = "existing-model"\n[mcp_servers.other]\ncommand = "unrelated"\n'
            path.write_bytes(original)
            proposed = configure(root)
            self.assertFalse(proposed["active_host_verified"])
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(configure(root, write=True)["changed"])
            self.assertTrue(path.read_bytes().startswith(original))
            self.assertFalse(configure(root, write=True)["changed"])
            config = configuration(root)
            self.assertEqual(config["default_tools_approval_mode"], "approve")
            self.assertEqual(config["enabled_tools"], [s.name for s in tool_specs()])
            self.assertNotIn("approval_policy", config)
            self.assertNotIn("sandbox_mode", config)
            self.assertNotIn("env", config)

    def test_changed_table_and_symlink_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".codex").mkdir()
            path = root / ".codex" / "config.toml"
            path.write_text('[mcp_servers.enactive_player]\ncommand = "different"\n')
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "differs"):
                configure(root, write=True)
            self.assertEqual(path.read_bytes(), before)
            path.unlink()
            target = root / "other.toml"
            target.write_text('model = "untouched"\n')
            path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                configure(root, write=True)
            self.assertEqual(target.read_text(), 'model = "untouched"\n')


class SDKTransportTests(unittest.TestCase):
    def test_qualified_procedure_claim_requires_original_source_presentation(self):
        client = _FixtureClient()
        client.collect = Mock(return_value={"transport": "uncertain", "response": None})
        player = PlayerTools(client)
        player.snapshots["chosen-snapshot"] = {"mission": {"mission_id": "current-mission", "epoch": 1}}
        arguments = dict(snapshot_id="chosen-snapshot", request_id="claim-with-procedure", wait_seconds=0,
            intent=dict(handoff_id="issued-handoff", player_id="fresh-player", actor_role="campaign-player",
                packet_ids=["issued-packet"], read_source_ids=["post-pause"],
                read_procedure_sources=[{"mission_id": "history-mission", "source_id": "original-image"}]))
        with self.assertRaisesRegex(ContractError, "selected exact source"):
            player.call("enactive_claim", arguments)
        client.collect.assert_not_called()
        player.source("history-mission", "original-image")
        with self.assertRaisesRegex(ContractError, "retained completed handoff"):
            player.call("enactive_claim", arguments)
        client.collect.assert_called_once()

    def test_actual_stdio_handshake_catalog_and_combined_result(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        async def exercise():
            parameters = StdioServerParameters(command=sys.executable,
                args=["-m", "tests.test_player_tools", "--stdio-fixture"], cwd=str(Path(__file__).resolve().parents[1]))
            async with Client(parameters) as client:
                self.assertEqual(client.server_info.version, "6.1.0")
                tools = await client.list_tools()
                self.assertEqual({t.name for t in tools.tools}, {s.name for s in tool_specs()})
                self.assertEqual(len(tools.tools), 21)
                for spec in tools.tools:
                    self.assertNotIn("request_id", spec.input_schema["properties"])
                    self.assertNotIn("wait_seconds", spec.input_schema["properties"])
                detail_spec = next(tool for tool in tools.tools if tool.name == "enactive_detail")
                self.assertTrue(detail_spec.annotations.read_only_hint)
                self.assertTrue(detail_spec.annotations.idempotent_hint)
                self.assertEqual(detail_spec.input_schema["properties"]["section"]["enum"], list(DETAIL_SECTIONS))
                result = await client.call_tool("enactive_snapshot", {})
                self.assertFalse(result.is_error)
                self.assertIsNone(result.structured_content)
                view = json.loads(result.content[0].text)
                self.assertEqual(view["mission"]["mission_id"], "sdk-fixture")
                self.assertEqual(view["presentation_schema"], "player-view/5")
                self.assertEqual(view["detail_sections"], list(DETAIL_SECTIONS))
                self.assertEqual(view["mission"]["progress"],
                                 _FixtureClient().status()["mission"]["progress"])
                self.assertEqual(view["mission"]["last_receipt"],
                                 {"id": "original-receipt", "transport_disposition": "unknown"})
                self.assertEqual(view["native"]["state"],
                                 {"session": "sdk-session", "health": "healthy"})
                self.assertEqual(view["source"],
                                 _FixtureClient().source("sdk-fixture", "sdk-source")[0])
                text, image = result.content
                self.assertEqual(text.type, "text")
                self.assertEqual(base64.b64decode(image.data), _FixtureClient.image)
                self.assertEqual(image.mime_type, "image/png")
                observed = await client.call_tool("enactive_observe", dict(snapshot_id=view["snapshot_id"]))
                self.assertFalse(observed.is_error)
                written = json.loads(observed.content[0].text)
                self.assertTrue(written["operation_id"].startswith("op-"))
                self.assertEqual(written["response"]["operation"]["request_id"], written["operation_id"])
                for obsolete in (dict(request_id="old"), dict(wait_seconds=0)):
                    rejected = await client.call_tool("enactive_observe", dict(
                        snapshot_id=view["snapshot_id"], **obsolete))
                    self.assertTrue(rejected.is_error)
                malformed = await client.call_tool("enactive_skill", dict(
                    snapshot_id=view["snapshot_id"], scope="new_root", source_id=None,
                    supporting_source_ids=[], limits=dict(primitives=1, wall_seconds=10, game_seconds=10),
                    intent=dict(skill_kind="direct", goal={"description": "private-player-payload"},
                                perception=None, procedure=None, work_id=None)))
                self.assertTrue(malformed.is_error)
                feedback = malformed.content[0].text
                self.assertIn("intent.goal", feedback)
                for field in ("input", "intent", "expected", "interrupt_allowed"):
                    self.assertIn(field, feedback)
                self.assertNotIn("private-player-payload", feedback)
                self.assertNotIn("navigate", feedback)
                detailed = await client.call_tool("enactive_detail", dict(
                    snapshot_id=view["snapshot_id"], section="receipt"))
                self.assertFalse(detailed.is_error)
                self.assertIsNone(detailed.structured_content)
                detail_view = json.loads(detailed.content[0].text)
                self.assertEqual(detail_view["detail"], _FixtureClient().status()["mission"]["last_receipt"])
                self.assertEqual(detail_view["presentation_schema"], "player-view/5")
                self.assertFalse(detail_view["grants_authority"])
                self.assertEqual(len(detailed.content), 1)
                collected = await client.call_tool("enactive_result", dict(mission_id="sdk-fixture",
                    operation_id="original-operation"))
                self.assertFalse(collected.is_error)
                self.assertIsNone(collected.structured_content)
                projected = json.loads(collected.content[0].text)
                self.assertEqual(projected["presentation_schema"], "player-view/5")
                self.assertEqual(projected["transport"], "uncertain")
                self.assertFalse(projected["settled"])
                self.assertEqual(projected["operation_id"], "original-operation")
                self.assertEqual(projected["response"], _FixtureClient().collect()["response"])
                self.assertEqual(projected["next_snapshot"]["mission"]["progress"],
                                 _FixtureClient().status()["mission"]["progress"])
                self.assertEqual(base64.b64decode(collected.content[1].data), _FixtureClient.image)
                duplicate = await client.call_tool("enactive_result", dict(mission_id="sdk-fixture",
                    operation_id="same-progress"))
                self.assertIsNone(duplicate.structured_content)
                compacted = json.loads(duplicate.content[0].text)
                self.assertFalse(duplicate.is_error)
                self.assertNotIn("progress", compacted["next_snapshot"]["mission"])
                self.assertEqual(compacted["next_snapshot"]["mission"]["progress_operation_id"], "same-progress")
                self.assertEqual(compacted["response"]["operation"]["result"],
                                 _FixtureClient().status()["mission"]["progress"])
                self.assertEqual(base64.b64decode(duplicate.content[1].data), _FixtureClient.image)
                unavailable = await client.call_tool("enactive_source", dict(mission_id="sdk-fixture",
                    source_id="unavailable"))
                self.assertTrue(unavailable.is_error)
                self.assertIsNone(unavailable.structured_content)
                self.assertEqual(len(unavailable.content), 1)
                self.assertEqual(unavailable.content[0].text, "Selected original source unavailable; choose a retained source")
                rejected = await client.call_tool("unlisted_shell_tool", {"command": "must not run"})
                self.assertTrue(rejected.is_error)
                self.assertIn("Unknown player tool", rejected.content[0].text)
                self.assertIsNone(rejected.structured_content)
                self.assertEqual(len(rejected.content), 1)
                self.assertEqual(rejected.content[0].type, "text")
        asyncio.run(exercise())


class _FixtureClient:
    """Only SDK framing/image-format fixture; it proves no game state or action."""
    from tests.test_gameplay_evidence import png
    image = png()
    def staged_request(self, mission_id, request_id):
        return None

    def status(self):
        return dict(state=dict(session="sdk-session", health="healthy", actions=["open"],
            scene={"position": [1, 2, 0]}, ui={"visible": "menu"}),
            mission=dict(mission_id="sdk-fixture", epoch=1,
            current_source=dict(observation_id="sdk-source"), prompt_phase=None,
            lifecycle_phase=None, activity_phase=None, progress={"history": ["duplicated"]},
            last_receipt=dict(id="original-receipt", transport_disposition="unknown",
                native_request_json='{"keys":["open"]}', native_ack={"raw": "ack"})))
    def source(self, mission_id, source_id):
        if source_id == "unavailable":
            raise OSError("Selected original source unavailable; choose a retained source")
        return dict(reference=dict(observation_id=source_id), observation=dict(actions=["open"],
            scene={"position": [1, 2, 0]}, ui={"visible": "menu"}),
                    disposition="retained", grants_authority=False), self.image

    def collect(self, **arguments):
        if arguments.get("operation_id") == "same-progress":
            return dict(transport="delivered", settled=True, operation_id="same-progress",
                response=dict(operation=dict(id="same-progress", state="completed",
                    result=self.status()["mission"]["progress"])))
        complete = dict(progress=["required-work"], last_receipt={"delivery": "unknown"},
                        obligations=["read-original-source"], grants_authority=False)
        return dict(transport="uncertain", settled=False, operation_id="original-operation",
            reason="Original submission response lost", response=dict(
                operation=dict(id="original-operation", request_id="original-request", kind="handoff",
                    state="unknown", result=deepcopy(complete), receipts=[{"id": "original-receipt"}]),
                context=deepcopy(complete), handoff=deepcopy(complete), reflection=deepcopy(complete),
                proposal=deepcopy(complete)))

    def submit(self, request, **options):
        return dict(transport="delivered", settled=True, operation_id=request["request_id"],
            response=dict(status="accepted", operation=dict(request=deepcopy(request), state="completed",
                result=dict(observed=True))))


async def _stdio_fixture():
    from mcp.server.stdio import stdio_server
    server = make_server(PlayerTools(_FixtureClient()))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    if sys.argv[1:] == ["--stdio-fixture"]:
        import anyio
        anyio.run(_stdio_fixture)
    else:
        unittest.main()
