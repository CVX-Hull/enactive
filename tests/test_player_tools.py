"""Real HTTP/runtime adapter fixtures and SDK transport; never native acceptance."""
from copy import deepcopy
import asyncio
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

from harness.gameplay.contracts import ContractError
from harness.mission_client import MissionClient
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools, tool_specs
from harness.player_view import decision_view
from tests import test_mission_http as http_fixture
from tests.test_mission_contracts import claim
from tools.configure_player_tools import configure, configuration


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
            intent=dict(skill_kind="navigate", goal=dict(scope=dict(mission_id=self.a.mission_id,
                session=source["session"], coordinate_epoch=0), target=[1, 0, 0]),
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
        self.assertEqual(view["source"], first["source"])
        self.assertEqual(first, full)
        self.assertEqual((player.snapshots, player.sources), handles)
        arguments = self.navigate(first)
        result, image = player.call("enactive_skill", arguments)
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
        entry = claim(id="interpreted-water", scope=scope,
            observed_time=dict(revision=ref["revision"], turn=ref["turn"]),
            sources=[ref["observation_id"]], supports=[dict(sources=[ref["observation_id"]], claims=[])])
        result, _ = player.call("enactive_remember", dict(snapshot_id=current["snapshot_id"],
            request_id="remember", wait_seconds=2, intent=dict(entry_type="claim", entry=entry)))
        self.assertEqual(result["response"]["operation"]["state"], "completed", result)
        corrected = deepcopy(entry)
        corrected.update(id="corrected-water", text="Previously interpreted value is unverified", status="unknown",
                         supersedes=[entry["id"]])
        corrected["value"] = dict(quantity=None, state=None)
        result, _ = player.call("enactive_correct", dict(snapshot_id=result["next_snapshot"]["snapshot_id"],
            request_id="correct", wait_seconds=2, intent=dict(entry_type="claim", entry=corrected,
                retired_ids=[entry["id"]], reason="Visible evidence does not establish that quantity")))
        self.assertEqual(result["response"]["operation"]["state"], "completed", result)
        result, _ = player.call("enactive_context", dict(snapshot_id=result["next_snapshot"]["snapshot_id"],
            intent=dict(scope=dict(session=ref["session"], coordinate_epoch=0), query="water",
                        max_bytes=32768, handoff=None)))
        packet = result["response"]["context"]["packet"]
        self.assertIn("corrected-water", json.dumps(packet))
        self.assertIn(ref["observation_id"], json.dumps(packet))
        self.assertFalse(packet["grants_authority"])

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
        self.assertEqual(view["next_snapshot"]["source"], result["next_snapshot"]["source"])

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


class ProjectConfigurationTests(unittest.TestCase):
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
        player.snapshots["chosen-snapshot"] = {"mission_id": "current-mission", "epoch": 1}
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
                tools = await client.list_tools()
                self.assertEqual({t.name for t in tools.tools}, {s.name for s in tool_specs()})
                result = await client.call_tool("enactive_snapshot", {})
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["mission"]["mission_id"], "sdk-fixture")
                self.assertEqual(result.structured_content["presentation_schema"], "player-view/1")
                self.assertEqual(result.structured_content["mission"]["progress"],
                                 _FixtureClient().status()["mission"]["progress"])
                self.assertEqual(result.structured_content["mission"]["last_receipt"],
                                 {"id": "original-receipt", "transport_disposition": "unknown"})
                self.assertEqual(result.structured_content["native"]["state"],
                                 {"session": "sdk-session", "health": "healthy"})
                self.assertEqual(result.structured_content["source"],
                                 _FixtureClient().source("sdk-fixture", "sdk-source")[0])
                text, image = result.content
                self.assertEqual(json.loads(text.text), result.structured_content)
                self.assertEqual(base64.b64decode(image.data), _FixtureClient.image)
                self.assertEqual(image.mime_type, "image/png")
                collected = await client.call_tool("enactive_result", dict(mission_id="sdk-fixture",
                    operation_id="original-operation", wait_seconds=0))
                self.assertFalse(collected.is_error)
                projected = collected.structured_content
                self.assertEqual(projected["presentation_schema"], "player-view/1")
                self.assertEqual(projected["transport"], "uncertain")
                self.assertFalse(projected["settled"])
                self.assertEqual(projected["operation_id"], "original-operation")
                self.assertEqual(projected["response"], _FixtureClient().collect()["response"])
                self.assertEqual(projected["next_snapshot"]["mission"]["progress"],
                                 _FixtureClient().status()["mission"]["progress"])
                self.assertEqual(json.loads(collected.content[0].text), projected)
                self.assertEqual(base64.b64decode(collected.content[1].data), _FixtureClient.image)
                duplicate = await client.call_tool("enactive_result", dict(mission_id="sdk-fixture",
                    operation_id="same-progress", wait_seconds=0))
                compacted = duplicate.structured_content
                self.assertFalse(duplicate.is_error)
                self.assertNotIn("progress", compacted["next_snapshot"]["mission"])
                self.assertEqual(compacted["next_snapshot"]["mission"]["progress_operation_id"], "same-progress")
                self.assertEqual(compacted["response"]["operation"]["result"],
                                 _FixtureClient().status()["mission"]["progress"])
                self.assertEqual(json.loads(duplicate.content[0].text), compacted)
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
