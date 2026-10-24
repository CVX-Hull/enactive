"""MCP advisory validation over real SDK staging and synthetic HTTP/SQLite work."""
from copy import deepcopy
import asyncio
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from mcp import Client

from harness.gameplay.mission_contracts import LearningPolicy
from harness.gameplay.mission_ledger import MissionLedger
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools
from tests.test_mission_contracts import admission
from tests import test_reflection_client as reflection_fixture
from tests.test_reflection_exchange import job, procedure, wrapper
from tests.test_reflection_tools import SCOPE, submit_args


class AdvisoryPreflightTests(unittest.TestCase):
    start_stub = reflection_fixture.ReflectionClientTests.start_stub
    write_config = reflection_fixture.ReflectionClientTests.write_config

    def setUp(self):
        reflection_fixture.ReflectionClientTests.setUp(self)
        admitted = admission(mission_id="mission-a", learning=LearningPolicy(
            procedure()["environment"], reflector_id="reflector-a"))
        self.ledger = MissionLedger(self.root / "mission", admission=admitted, now=1000.)
        self.addCleanup(self.ledger.close)
        self.job = job(memory_version=0)
        row = self.job["trajectory"][0]
        row["result"]["source_ids"] = row["result"].pop("sources")
        self.ledger.begin_request(row["request"], now=1000.)
        self.ledger.complete_request("request-1", row["state"], row["result"], now=1000.)
        self.ledger.append_reflection_job(self.job, now=1000.)
        self.server.callback = self.respond
        self.player = PlayerTools(self.client)

    def respond(self, handler, body):
        path = urlsplit(handler.path).path
        if path == "/api/reflection/next":
            handler.reply(dict(status="offered", job=wrapper(self.job), grants_authority=False))
        elif path == "/api/reflection/command":
            result = self.ledger.apply_reflection(body, now=1001.)
            handler.reply(dict(status="committed", admitted=True, command_id=body["command_id"],
                result=result, grants_authority=False))
        elif path == "/api/reflection/result":
            identity = parse_qs(urlsplit(handler.path).query)["command_id"][0]
            original = next(row for row in self.ledger.reflection_command_records()
                if row["command"]["command_id"] == identity)
            handler.reply(dict(status="committed", admitted=True, command_id=identity,
                result=original["result"], grants_authority=False))
        else:
            raise AssertionError(path)

    def run_client(self, exercise):
        async def run():
            async with Client(make_server(self.player)) as client:
                await exercise(client)
        asyncio.run(run())

    @staticmethod
    def value(reply):
        return json.loads(reply.content[0].text)

    @staticmethod
    def args():
        return {key: value for key, value in submit_args().items()
            if key not in ("request_id", "wait_seconds")}

    def staged(self, identity):
        digest = hashlib.sha256(("mission-a\0" + identity).encode()).hexdigest()
        return self.root / ".runtime" / "reflection-commands" / ("rc-" + digest + ".json")

    def test_local_closure_refusals_leave_no_stage_post_collection_or_ledger_command_and_allow_correction(self):
        invalids = []
        for field in ("request_ids", "source_refs"):
            args = self.args()
            args["notes"][0][field] = (["prior-job-request"] if field == "request_ids" else
                [dict(mission_id="mission-a", source_id="prior-job-source")])
            invalids.append(args)
        for evidence in ("support", "counterexamples"):
            for field in ("request_ids", "source_ids"):
                args = self.args()
                episode = deepcopy(args["candidates"][0]["support"][0])
                episode[field] = ["prior-job-evidence"]
                args["candidates"][0][evidence] = [episode]
                invalids.append(args)

        async def exercise(client):
            claim = await client.call_tool("enactive_reflect_next", SCOPE)
            self.assertFalse(claim.is_error)
            self.assertEqual(self.value(claim)["status"], "claimed")
            commands = self.ledger.reflection_command_records()
            stages = sorted((self.root / ".runtime/reflection-commands").glob("*.json"))
            calls = deepcopy(self.server.calls)
            with patch.object(self.client, "_stage_payload", wraps=self.client._stage_payload) as stage:
                for index, args in enumerate(invalids):
                    with self.subTest(index=index), patch("harness.player_tools.uuid.uuid4",
                            return_value=SimpleNamespace(hex=f"invalid-{index}")):
                        reply = await client.call_tool("enactive_reflect_submit", args)
                    self.assertTrue(reply.is_error)
                    value = self.value(reply)
                    self.assertEqual(value.get("submission"), "not_submitted")
                    self.assertNotIn("original_collection", value)
                    self.assertIn("original job closure", value["error"])
                    self.assertFalse(self.staged(f"op-invalid-{index}").exists())
                    self.assertEqual(self.ledger.reflection_command_records(), commands)
                    self.assertEqual(self.server.calls, calls)
                    self.assertEqual(sorted((self.root / ".runtime/reflection-commands").glob("*.json")), stages)
                stage.assert_not_called()
            with patch("harness.player_tools.uuid.uuid4", return_value=SimpleNamespace(hex="corrected")):
                corrected = await client.call_tool("enactive_reflect_submit", self.args())
            self.assertFalse(corrected.is_error)
            self.assertEqual(self.value(corrected)["command_id"], "op-corrected")
            self.assertTrue(self.staged("op-corrected").exists())
            self.assertEqual(len(self.ledger.reflection_command_records()), len(commands) + 1)
            self.assertEqual(self.ledger.reflection_records()[0][0]["state"], "completed")
            self.assertEqual([urlsplit(call[1]).path for call in self.server.calls[len(calls):]],
                ["/api/reflection/command"])
        self.run_client(exercise)

    def test_missing_claimed_handle_is_proven_unsubmitted_without_network_or_stage(self):
        async def exercise(client):
            with patch.object(self.client, "_stage_payload") as stage:
                reply = await client.call_tool("enactive_reflect_submit", self.args())
                self.assertTrue(reply.is_error)
                value = self.value(reply)
                self.assertEqual(value.get("submission"), "not_submitted")
                self.assertNotIn("original_collection", value)
                self.assertIn("claimed job", value["error"])
                stage.assert_not_called()
            self.assertEqual(self.server.calls, [])
            self.assertEqual(self.ledger.reflection_command_records(), ())
        self.run_client(exercise)

    def test_post_stage_uncertainty_and_format_failure_keep_original_collection_without_replay(self):
        async def exercise(client):
            self.assertFalse((await client.call_tool("enactive_reflect_next", SCOPE)).is_error)
            for failure in ("uncertain", "format"):
                with self.subTest(failure=failure):
                    if failure == "uncertain":
                        def disconnect(handler, body):
                            if urlsplit(handler.path).path == "/api/reflection/command":
                                handler.connection.shutdown(2)
                                handler.connection.close()
                            else:
                                handler.reply(dict(status="missing", admitted=False,
                                    command_id=f"op-{failure}", grants_authority=False))
                        self.server.callback = disconnect
                    else:
                        self.server.callback = self.respond
                    start = len(self.server.calls)
                    with patch("harness.player_tools.uuid.uuid4", return_value=SimpleNamespace(hex=failure)):
                        if failure == "format":
                            with patch("harness.player_mcp.decision_view", side_effect=ValueError("Formatting failed")):
                                reply = await client.call_tool("enactive_reflect_submit", self.args())
                            self.assertTrue(reply.is_error)
                            value = self.value(reply)
                            self.assertNotIn("submission", value)
                            collection = value["original_collection"]
                            self.assertEqual(collection, dict(tool="enactive_reflect_result",
                                arguments=dict(**SCOPE, command_id=f"op-{failure}")))
                        else:
                            reply = await client.call_tool("enactive_reflect_submit", self.args())
                            self.assertFalse(reply.is_error)
                            value = self.value(reply)
                            self.assertEqual(value["status"], "unknown")
                            collection = dict(tool="enactive_reflect_result",
                                arguments=dict(**SCOPE, command_id=value["command_id"]))
                    self.assertTrue(self.staged(f"op-{failure}").exists())
                    collected = await client.call_tool(collection["tool"], collection["arguments"])
                    self.assertFalse(collected.is_error)
                    self.assertEqual(self.value(collected)["command_id"], f"op-{failure}")
                    self.assertEqual([call[0] for call in self.server.calls[start:]], ["POST", "GET"])
        self.run_client(exercise)


if __name__ == "__main__":
    unittest.main()
