"""Refusal presentation over controlled HTTP/real SDK staging; no game runtime."""
from copy import deepcopy
import asyncio
import json
import socket
import unittest
from unittest.mock import patch

from mcp import Client

from harness.gameplay.contracts import canonical
from harness.gameplay.mission_contracts import make_admission_refusal
from harness.mission_client import MissionClientError
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools
from tests import test_mission_client as http_fixture
from tests.test_mission_request_producer import snapshot


class RefusalMCPTests(unittest.TestCase):
    setUpHTTP = http_fixture.MissionClientTests.setUp
    start_stub = http_fixture.MissionClientTests.start_stub
    write_config = http_fixture.MissionClientTests.write_config
    stage_path = http_fixture.MissionClientTests.stage_path

    def setUp(self):
        self.setUpHTTP()
        self.current = snapshot(phase="paused", progress={"reason": "Current Pause remains in effect"})
        self.player = PlayerTools(self.client)
        self.player.snapshots["selected"] = dict(snapshot_id="selected", mission=snapshot(), native={}, source=None)
        self.proofs = []
        self.mode = "refused"
        self.server.callback = self.respond

    def respond(self, handler, body):
        if body is None:
            handler.reply(dict(mission=deepcopy(self.current), state={}))
        elif body["kind"] == "result":
            handler.reply(dict(status="rejected", reason="Unknown original operation"))
        else:
            proof = make_admission_refusal(body)
            self.proofs.append(deepcopy(proof))
            if self.mode == "lost":
                handler.connection.shutdown(socket.SHUT_RDWR)
                handler.connection.close()
                return
            if self.mode == "badproof":
                proof["request_sha256"] = "0" * 64
            response = dict(status="rejected", reason="Observe needs the current admitted epoch",
                            admission_refusal=proof)
            if self.mode == "uncertified":
                response.pop("admission_refusal")
            handler.reply(response, code=409)

    def run_client(self, exercise):
        async def run():
            async with Client(make_server(self.player)) as client:
                await exercise(client)
        asyncio.run(run())

    def value(self, result):
        self.assertIsNone(result.structured_content)
        return json.loads(result.content[0].text)

    def assert_refused(self, value):
        self.assertEqual(value["submission"], "not_admitted")
        self.assertTrue(value["settled"])
        self.assertNotIn("original_collection", value)
        self.assertNotIn("next_call", value)
        self.assertIn("new corrected decision", value["next_step"])
        self.assertEqual(value["response"]["reason"], "Observe needs the current admitted epoch")
        self.assertEqual(value["next_snapshot"]["mission"]["phase"], "paused")
        self.assertEqual(value["next_snapshot"]["mission"]["progress"], self.current["progress"])
        self.assertTrue(value["next_snapshot"]["read_only"])
        text = canonical(value)
        self.assertNotIn("mission-refusal", text)
        self.assertNotIn("request_sha256", text)
        self.assertNotIn(self.proofs[-1]["request_sha256"], text)

    def test_exact_refusal_and_explicit_new_decision_without_phantom_collection(self):
        async def exercise(client):
            first = await client.call_tool("enactive_observe", dict(snapshot_id="selected"))
            self.assertFalse(first.is_error, self.value(first))
            original = self.value(first)
            self.assert_refused(original)
            # A deliberate new invocation receives a new ID and current epoch.
            current_id = original["next_snapshot"]["snapshot_id"]
            corrected = await client.call_tool("enactive_observe", dict(snapshot_id=current_id))
            self.assertFalse(corrected.is_error)
            self.assert_refused(self.value(corrected))
            self.assertNotEqual(self.value(corrected)["operation_id"], original["operation_id"])
        self.run_client(exercise)
        posts = [call[3] for call in self.server.calls if call[3] is not None]
        self.assertEqual([body["kind"] for body in posts], ["observe", "observe"])
        for body in posts:
            self.assertEqual(self.stage_path(body).read_bytes(), canonical(body).encode())

    def test_validated_refusal_survives_finish_image_and_projection_errors(self):
        for failure in ("finish", "image", "projection"):
            with self.subTest(failure=failure):
                if failure == "finish":
                    target = patch.object(self.player, "_compact", side_effect=ValueError("request_sha256=private-proof in finish"))
                elif failure == "image":
                    target = patch.object(self.player, "present_image", side_effect=ValueError("request_sha256=private-proof in image"))
                else:
                    target = patch("harness.player_mcp.decision_view", side_effect=ValueError("request_sha256=private-proof in projection"))
                async def exercise(client):
                    result = await client.call_tool("enactive_observe", dict(snapshot_id="selected"))
                    self.assertTrue(result.is_error)
                    self.assert_refused(self.value(result))
                    self.assertIn("error", self.value(result))
                with target:
                    self.run_client(exercise)
        self.assertEqual([call[3]["kind"] for call in self.server.calls if call[3]], ["observe"] * 3)

    def test_uncertified_badproof_and_lost_response_do_not_gain_refusal_on_format_error(self):
        for mode in ("uncertified", "badproof", "lost"):
            with self.subTest(mode=mode):
                self.mode = mode
                async def exercise(client):
                    result = await client.call_tool("enactive_observe", dict(snapshot_id="selected"))
                    self.assertTrue(result.is_error)
                    value = self.value(result)
                    self.assertNotIn("submission", value)
                    collection = value["original_collection"]
                    self.assertEqual(collection["tool"], "enactive_result")
                    self.assertEqual(collection["arguments"]["mission_id"], "mission-test")
                    self.assertEqual(collection["arguments"]["operation_id"], self.proofs[-1]["request_id"])
                    self.assertNotIn("admission_refusal", canonical(value))
                with patch("harness.player_mcp.decision_view", side_effect=ValueError("Formatting failed")):
                    self.run_client(exercise)
        self.assertEqual([call[3]["kind"] for call in self.server.calls if call[3]], ["observe"] * 3)

    def test_stage_error_keeps_assigned_original_collection(self):
        async def exercise(client):
            result = await client.call_tool("enactive_observe", dict(snapshot_id="selected"))
            self.assertTrue(result.is_error)
            value = self.value(result)
            self.assertNotIn("submission", value)
            self.assertEqual(value["original_collection"]["arguments"]["mission_id"], "mission-test")
            self.assertTrue(value["original_collection"]["arguments"]["operation_id"].startswith("op-"))
        with patch.object(self.client, "_stage", side_effect=MissionClientError("Staging failed")):
            self.run_client(exercise)
        self.assertEqual(self.server.calls, [])

    def test_missing_current_context_does_not_undo_validated_refusal(self):
        async def exercise(client):
            result = await client.call_tool("enactive_observe", dict(snapshot_id="selected"))
            self.assertTrue(result.is_error)
            value = self.value(result)
            self.assertEqual(value["submission"], "not_admitted")
            self.assertTrue(value["settled"])
            self.assertNotIn("original_collection", value)
            self.assertIn("snapshot_error", value)
        with patch.object(self.player, "_compact", side_effect=ValueError("Formatting failed")), \
                patch.object(self.player, "snapshot", side_effect=OSError("Current context unavailable")):
            self.run_client(exercise)
