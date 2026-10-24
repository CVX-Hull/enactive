"""Advisory tool boundaries with controlled callbacks and official SDK framing."""
from copy import deepcopy
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from harness.gameplay.contracts import ContractError
from harness.gameplay.reflection import proposal_schema, validate_command, validate_proposal
from harness.gameplay.procedures import procedure_authoring_schema
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools, request_tool_specs, tool_specs
from tests.test_gameplay_evidence import png
from tests import test_reflection_client as reflection_fixture
from tests.test_reflection_client import receipt
from tests.test_reflection_exchange import command, job, procedure, proposal, wrapper


SCOPE = dict(mission_id="mission-a", reflector_id="reflector-a")


def semantic(record=None):
    record = procedure() if record is None else record
    return {key: value for key, value in record.items() if key in procedure_authoring_schema()["properties"]}


def admitted_status():
    return dict(mission=dict(mission_id="mission-a", configuration=dict(procedure_environment=procedure()["environment"]),
        reflection=dict(proposals=["proposal-1"])))


def bind_advice(player):
    player.snapshots["selected"] = admitted_status()


def submit_args(**changes):
    return dict(dict(**SCOPE, job_id="job-1", request_id="submit-1", wait_seconds=0,
                candidates=[semantic()], notes=proposal()["notes"], reason="Scoped findings"), **changes)


class AdvisoryClient:
    def __init__(self):
        self.calls = []
        self.next_value = dict(status="offered", job=wrapper(), grants_authority=False)
        self.command_value = None
        self.image = png()
        self.metadata = dict(reference=dict(observation_id="source-1"), observation={},
                             disposition="retained", grants_authority=False)

    def reflection_next(self, *args, **kwargs):
        self.calls.append(("next", args, kwargs))
        return deepcopy(self.next_value)

    def reflection_command(self, value, **kwargs):
        self.calls.append(("command", deepcopy(value), kwargs))
        return deepcopy(self.command_value) if self.command_value is not None else receipt(value)

    def reflection_collect(self, mission_id, reflector_id, command_id, **kwargs):
        self.calls.append(("collect", command_id, kwargs))
        return receipt(command(command_id))

    def reflection_source(self, *args):
        self.calls.append(("source", args))
        return deepcopy(self.metadata), self.image

    def reflection_advice(self, mission_id, proposal_id):
        self.calls.append(("advice", (mission_id, proposal_id)))
        return dict(status="available", proposal=proposal(), grants_authority=False)

    def status(self):
        self.calls.append(("status",))
        return admitted_status()


class ReflectionToolTests(unittest.TestCase):
    def setUp(self):
        self.client = AdvisoryClient()
        self.player = PlayerTools(self.client)
        bind_advice(self.player)

    def claim(self):
        return self.player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=0))[0]

    def test_closed_tool_shapes_derive_proposal_fields_and_strict_bounds(self):
        specs = {spec.name: spec for spec in tool_specs()}
        names = {"enactive_reflect_next", "enactive_reflect_submit", "enactive_reflect_source", "enactive_advice"}
        self.assertEqual(names & specs.keys(), names)
        for name in names:
            self.assertFalse(specs[name].schema["additionalProperties"])
        schema = proposal_schema()["properties"]
        for field in ("notes", "reason"):
            self.assertEqual(specs["enactive_reflect_submit"].schema["properties"][field], schema[field])
        for args in (dict(**SCOPE, wait_seconds=40.1), dict(**SCOPE, wait_seconds=0, command_id="forged"),
                     dict(**SCOPE, wait_seconds=True)):
            with self.assertRaises(ContractError): self.player.call("enactive_reflect_next", args)
        changed = proposal_schema()
        changed.clear()
        self.assertIn("properties", proposal_schema())
        self.assertEqual(specs["enactive_reflect_submit"].schema["properties"]["candidates"]["items"], procedure_authoring_schema())
        self.assertEqual(self.client.calls, [])

    def test_only_next_tool_allows_extended_wait_and_claim_keeps_original_remaining_allowance(self):
        for spec in request_tool_specs():
            wait = spec.schema["properties"].get("wait_seconds")
            if wait is not None:
                self.assertEqual(wait["maximum"], 40 if spec.name == "enactive_reflect_next" else 15)
        for name, args in (("enactive_reflect_submit", submit_args() | {"wait_seconds": 16}),
                           ("enactive_reflect_result", dict(**SCOPE, command_id="command-1", wait_seconds=16))):
            with self.assertRaises(ContractError): self.player.call(name, args)
        for state in ("offered", "claimed"):
            self.client.next_value = dict(status=state, job=wrapper(**(
                dict(state="claimed", claimed_at=1000., deadline=1180.) if state == "claimed" else {})),
                grants_authority=False)
            for elapsed, remaining in ((1, 15), (30, 10), (41, 0)):
                with self.subTest(state=state, elapsed=elapsed):
                    with patch("harness.player_tools.time.monotonic", side_effect=(100., 100. + elapsed)):
                        result, image = self.player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=40))
                    self.assertEqual(result["status"], "claimed")
                    self.assertEqual(result["job"]["deadline"], 1180.)
                    self.assertEqual(result["claim"]["result"]["charged_seconds"], 180.)
                    self.assertIsNone(image)
                    self.assertEqual(self.client.calls[-2][2], dict(wait_seconds=40))
                    self.assertEqual(self.client.calls[-1][0], "collect" if state == "claimed" else "command")
                    self.assertEqual(self.client.calls[-1][2], dict(wait_seconds=remaining))

    def test_extended_next_unknown_claim_retains_identity_and_only_collection_restores_job(self):
        identity = self.player._claim_id("mission-a", "job-1")
        unknown = receipt(command(identity), status="unknown", admitted=None)
        self.client.command_value = unknown
        for _ in range(2):
            result, _ = self.player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=40))
            self.assertEqual(result, unknown)
            self.assertNotIn("job", result)
            self.assertEqual(self.client.calls[-1][1]["command_id"], identity)
            self.assertLessEqual(self.client.calls[-1][2]["wait_seconds"], 15)
            with self.assertRaisesRegex(ContractError, "claimed job"):
                self.player.call("enactive_reflect_submit", submit_args())
        self.client.next_value = dict(status="claimed",
            job=wrapper(state="claimed", claimed_at=1000., deadline=1180.), grants_authority=False)
        collect = self.client.reflection_collect
        def collect_unknown(*args, **kwargs):
            collect(*args, **kwargs)
            return deepcopy(unknown)
        self.client.reflection_collect = collect_unknown
        result, _ = self.player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=40))
        self.assertEqual(result, unknown)
        self.assertEqual(self.client.calls[-1][1], identity)
        self.assertLessEqual(self.client.calls[-1][2]["wait_seconds"], 15)
        self.assertEqual(self.player._reflection_jobs, {})
        self.client.reflection_collect = collect
        result, _ = self.player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=40))
        self.assertEqual(result["status"], "claimed")
        self.assertEqual(result["claim"]["command_id"], identity)
        self.assertEqual([row[0] for row in self.client.calls].count("command"), 2)

    def test_claim_is_stable_verified_and_submit_headers_come_only_from_job(self):
        result = self.claim()
        self.assertEqual(result["status"], "claimed")
        self.assertEqual(result["job"]["job"], job())
        self.assertEqual(result["job"]["deadline"], 1180.)
        self.assertEqual(result["claim"]["result"]["charged_seconds"], 180.)
        claim = self.client.calls[1][1]
        self.assertEqual(claim, command("claim-" + hashlib.sha256(b"mission-a\0job-1").hexdigest()))
        value, image = self.player.call("enactive_reflect_submit", submit_args())
        self.assertIsNone(image)
        submitted = self.client.calls[-1][1]
        validate_command(submitted)
        validate_proposal(submitted["proposal"], job())
        self.assertEqual(submitted["command_id"], "submit-1")
        self.assertEqual(submitted["proposal"]["id"], "proposal-" + hashlib.sha256(b"submit-1").hexdigest())
        self.assertEqual({key: submitted["proposal"][key] for key in ("mission_id", "reflector_id", "epoch", "cutoff_sequence", "memory_version")},
                         dict(**SCOPE, epoch=0, cutoff_sequence=1, memory_version=1))
        self.assertNotIn("next_snapshot", value)
        self.assertEqual([row[0] for row in self.client.calls].count("status"), 1)

    def test_committed_claim_refusal_returns_original_reason_without_job(self):
        identity = self.player._claim_id("mission-a", "job-1")
        original = dict(status="committed", admitted=True, command_id=identity,
            result=dict(status="rejected", reason="Original reflective allowance exhausted", grants_authority=False),
            grants_authority=False)
        self.client.command_value = original
        returned, image = self.player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=0))
        self.assertEqual(returned, original)
        self.assertIsNone(image)
        self.assertNotIn("job", returned)

    def test_candidate_authoring_binds_exact_parent_environment_and_software_ids(self):
        parent = procedure()
        self.client.next_value["job"]["job"]["procedures"] = [parent]
        self.claim()
        entry = semantic()
        entry["parent"] = dict(mission_id=parent["mission_id"], revision_id=parent["id"])
        self.player.call("enactive_reflect_submit", submit_args(candidates=[entry], request_id="a" * 128))
        record = self.client.calls[-1][1]["proposal"]["candidates"][0]
        self.assertEqual(record["revision"], parent["revision"] + 1)
        self.assertEqual(record["procedure_id"], parent["procedure_id"])
        self.assertEqual(record["environment"], admitted_status()["mission"]["configuration"]["procedure_environment"])
        self.assertEqual(record["parent"], entry["parent"])
        self.assertNotEqual(record["id"], parent["id"])
        self.assertEqual(self.player.procedures, {})

    def test_old_candidate_metadata_unknown_parent_support_and_wrong_admission_refuse(self):
        self.claim()
        before = sum(row[0] == "command" for row in self.client.calls)
        for candidates in ([procedure()], [{**semantic(), "parent": dict(mission_id="mission-a", revision_id="unread")}],
                           [{**semantic(), "support": [{**semantic()["support"][0], "source_ids": ["unknown"]}]}]):
            with self.subTest(candidates=candidates), self.assertRaises(ContractError):
                self.player.call("enactive_reflect_submit", submit_args(candidates=candidates))
        self.client.status = lambda: dict(mission=dict(mission_id="foreign"))
        with self.assertRaisesRegex(ContractError, "original admitted"):
            self.player.call("enactive_reflect_submit", submit_args())
        self.assertEqual(sum(row[0] == "command" for row in self.client.calls), before)

    def test_notes_only_need_no_environment_status_or_empty_candidate_filler(self):
        self.claim()
        self.client.status = lambda: self.fail("Notes alone must not read admission status")
        result, _ = self.player.call("enactive_reflect_submit", submit_args(candidates=[]))
        self.assertEqual(result["status"], "committed")
        self.assertEqual(self.client.calls[-1][1]["proposal"]["candidates"], [])

    def test_original_submission_collection_survives_empty_adapter_cache(self):
        original = dict(status="committed", admitted=True, command_id="submit-1",
            result=dict(job_id="job-1", state="completed", grants_authority=False), grants_authority=False)
        self.client.reflection_collect = lambda **args: deepcopy(original)
        new_player = PlayerTools(self.client)
        with new_player._lock:
            returned, image = new_player.call("enactive_reflect_result",
                dict(**SCOPE, command_id="submit-1", wait_seconds=0))
        self.assertEqual(returned, original)
        self.assertIsNone(image)
        self.assertEqual(self.client.calls, [])

    def test_pending_busy_unknown_do_not_release_job_or_permission_to_compute(self):
        for state in ("pending", "busy", "unknown", "rejected"):
            self.client.command_value = receipt(status=state, admitted=state == "pending")
            self.client.command_value["command_id"] = "claim-" + hashlib.sha256(b"mission-a\0job-1").hexdigest()
            result = self.claim()
            self.assertEqual(result["status"], state)
            self.assertNotIn("job", result)
            with self.assertRaisesRegex(ContractError, "claimed job"):
                self.player.call("enactive_reflect_submit", submit_args())
        self.client.command_value = receipt()
        self.client.command_value["result"]["job_id"] = "other"
        with self.assertRaises(ContractError): self.claim()
        self.client.command_value = receipt()
        self.client.command_value["result"]["deadline"] += 1
        with self.assertRaises(ContractError): self.claim()

    def test_already_claimed_collects_original_receipt_without_claim_post(self):
        self.client.next_value = dict(status="claimed", job=wrapper(state="claimed", claimed_at=1000., deadline=1180.), grants_authority=False)
        first = self.claim()
        second = self.claim()
        self.assertEqual(first, second)
        self.assertEqual(first["claim"]["result"]["charged_seconds"], 180.)
        self.assertFalse(any(row[0] == "command" for row in self.client.calls))

    def test_missing_cache_wrong_scope_or_source_refuses_without_network(self):
        with self.assertRaisesRegex(ContractError, "claimed job"):
            self.player.call("enactive_reflect_submit", submit_args())
        args = dict(**SCOPE, job_id="job-1", source_id="source-1")
        with self.assertRaisesRegex(ContractError, "claimed job"):
            self.player.call("enactive_reflect_source", args)
        self.assertEqual(self.client.calls, [])
        self.claim()
        count = len(self.client.calls)
        for changes in (dict(source_id="new-source"), dict(mission_id="foreign"), dict(reflector_id="other")):
            with self.assertRaises(ContractError): self.player.call("enactive_reflect_source", args | changes)
        self.assertEqual(len(self.client.calls), count)
        self.player.call("enactive_reflect_source", args)
        self.assertEqual(self.player.sources, {})
        self.assertEqual(self.player.snapshots, {"selected": admitted_status()})
        bad = submit_args()
        bad["notes"][0]["source_refs"][0]["source_id"] = "new-source"
        with self.assertRaises(ContractError): self.player.call("enactive_reflect_submit", bad)
        self.assertEqual(self.client.calls[-1][0], "status")

    def test_all_advisory_tools_bypass_active_lock_without_touching_player_cache(self):
        self.claim()
        self.player._lock.acquire()
        try:
            for name, args in (("enactive_reflect_next", dict(**SCOPE, wait_seconds=0)),
                               ("enactive_reflect_submit", submit_args()),
                               ("enactive_reflect_source", dict(**SCOPE, job_id="job-1", source_id="source-1")),
                               ("enactive_advice", dict(snapshot_id="selected", proposal_index=0))):
                result, image = self.player.call(name, args)
                self.assertFalse(result["grants_authority"])
                if name == "enactive_reflect_source": self.assertEqual(image, self.client.image)
                else: self.assertIsNone(image)
        finally:
            self.player._lock.release()
        self.assertEqual(self.player.sources, {})
        self.assertEqual(self.player.snapshots, {"selected": admitted_status()})

    def test_blocked_next_does_not_hold_advisory_cache_lock_or_active_lock(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def next_wait(*args, **kwargs):
            entered.set()
            if not release.wait(2): raise AssertionError("bounded watchdog expired")
            return dict(status="idle", grants_authority=False)
        self.client.reflection_next = next_wait
        completed = []
        thread = threading.Thread(target=lambda: completed.append(self.player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=40))))
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        self.assertTrue(self.player._lock.acquire(blocking=False))
        self.player._lock.release()
        self.assertEqual(self.player.call("enactive_advice", dict(snapshot_id="selected", proposal_index=0))[0]["status"], "available")
        self.assertIsNone(self.player.call("enactive_snapshot", {})[1])
        release.set()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(completed[0][0]["status"], "idle")


class ReflectionHTTPConcurrencyTests(unittest.TestCase):
    setUp = reflection_fixture.ReflectionClientTests.setUp
    start_stub = reflection_fixture.ReflectionClientTests.start_stub
    write_config = reflection_fixture.ReflectionClientTests.write_config

    def test_generated_submit_is_staged_once_and_recovered_by_collection(self):
        proposals = []
        def callback(handler, body):
            path = urlsplit(handler.path).path
            if path == "/api/reflection/next":
                handler.reply(dict(status="offered", job=wrapper(), grants_authority=False))
            elif path == "/api/reflection/command":
                if body["kind"] == "submit":
                    proposals.append(deepcopy(body))
                    handler.connection.shutdown(2)
                    handler.connection.close()
                else:
                    handler.reply(receipt(body))
            elif path == "/api/status":
                handler.reply(admitted_status())
            elif path == "/api/reflection/result":
                handler.reply(receipt(proposals[0]))
            else:
                raise AssertionError(path)
        self.server.callback = callback
        player = PlayerTools(self.client)
        bind_advice(player)
        player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=0))
        first, image = player.call("enactive_reflect_submit", submit_args())
        self.assertIsNone(image)
        self.assertEqual(first["status"], "unknown")
        second, _ = player.call("enactive_reflect_submit", submit_args())
        self.assertEqual(second["status"], "committed")
        self.assertEqual(second["result"]["proposal_id"], proposals[0]["proposal"]["id"])
        self.assertEqual(len(proposals), 1)
        with self.assertRaises(ValueError):
            player.call("enactive_reflect_submit", submit_args() | {"reason": "Changed body"})
        self.assertEqual(len(proposals), 1)
        self.assertEqual([urlsplit(call[1]).path for call in self.server.calls],
                         ["/api/reflection/next", "/api/reflection/command", "/api/status", "/api/reflection/command", "/api/status", "/api/reflection/result", "/api/status"])
        self.assertFalse((self.root / ".runtime" / "mission-requests").exists())

    def test_actually_blocked_http_next_keeps_snapshot_and_advice_available(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def callback(handler, body):
            path = urlsplit(handler.path).path
            if path == "/api/reflection/next":
                entered.set()
                release.wait(2)
                handler.reply(dict(status="idle", grants_authority=False))
            elif path == "/api/reflection/proposal":
                handler.reply(dict(status="available", proposal=proposal(), grants_authority=False))
            elif path == "/api/status":
                handler.reply(admitted_status())
            else: raise AssertionError(path)
        self.server.callback = callback
        player = PlayerTools(self.client)
        bind_advice(player)
        results = []
        thread = threading.Thread(target=lambda: results.append(player.call("enactive_reflect_next", dict(**SCOPE, wait_seconds=40))))
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(1))
        self.assertEqual(player.call("enactive_advice", dict(snapshot_id="selected", proposal_index=0))[0]["status"], "available")
        self.assertIsNone(player.call("enactive_snapshot", {})[1])
        release.set()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0][0]["status"], "idle")


class ReflectionSDKTests(unittest.TestCase):
    def test_official_stdio_catalog_and_advisory_callbacks(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        async def exercise():
            params = StdioServerParameters(command=sys.executable,
                args=["-m", "tests.test_reflection_tools", "--stdio-fixture"], cwd=str(Path(__file__).resolve().parents[1]))
            async with Client(params) as client:
                tools = await client.list_tools()
                self.assertEqual({value.name for value in tools.tools}, {value.name for value in tool_specs()})
                claimed = await client.call_tool("enactive_reflect_next", SCOPE)
                self.assertFalse(claimed.is_error)
                self.assertIsNone(claimed.structured_content)
                self.assertEqual(json.loads(claimed.content[0].text)["status"], "claimed")
                self.assertEqual(len(claimed.content), 1)
                source = await client.call_tool("enactive_reflect_source", dict(**SCOPE, job_id="job-1", source_id="source-1"))
                self.assertFalse(source.is_error)
                self.assertIsNone(source.structured_content)
                self.assertEqual(base64.b64decode(source.content[1].data), png())
                snapshot = await client.call_tool("enactive_snapshot", {})
                selected = json.loads(snapshot.content[0].text)["snapshot_id"]
                advice = await client.call_tool("enactive_advice", dict(snapshot_id=selected, proposal_index=0))
                self.assertFalse(advice.is_error)
                self.assertIsNone(advice.structured_content)
                self.assertEqual(len(advice.content), 1)
                self.assertEqual(json.loads(advice.content[0].text)["status"], "available")
                invalid = await client.call_tool("enactive_reflect_submit", submit_args() | {"epoch": 99})
                self.assertTrue(invalid.is_error)
        asyncio.run(exercise())


async def _stdio_fixture():
    from mcp.server.stdio import stdio_server
    server = make_server(PlayerTools(AdvisoryClient()))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    if sys.argv[1:] == ["--stdio-fixture"]:
        import anyio
        anyio.run(_stdio_fixture)
    else:
        unittest.main()
