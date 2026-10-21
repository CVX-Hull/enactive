"""Reflection adapter transport fixtures; no native game or host concurrency claim."""
from copy import deepcopy
import hashlib
import os
import socket
import stat
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.reflection import MAX_RESULT_BYTES
from harness.mission_client import MissionClient, MissionClientError
from tests import test_mission_client as mission_fixture
from tests.test_reflection_exchange import command, job, proposal, wrapper


def receipt(value=None, *, status="committed", admitted=True, **changes):
    value = command() if value is None else value
    result = dict(job_id=value["job_id"], state="claimed", claimed_at=1000., deadline=1180.,
                  charged_seconds=180., measurement="Conservative claimed wall window; model compute/tokens unknown",
                  grants_authority=False)
    if value["kind"] == "submit":
        result = dict(job_id=value["job_id"], state="completed", proposal_id=value["proposal"]["id"],
                      observed_claim_elapsed_seconds=10., late=False,
                      measurement="Observed claim-to-submit wall elapsed; model compute/tokens unknown",
                      grants_authority=False)
    return dict(status=status, admitted=admitted, command_id=value["command_id"],
                grants_authority=False, **({"result": result} if status == "committed" else {})) | changes


class ReflectionClientTests(unittest.TestCase):
    setUp = mission_fixture.MissionClientTests.setUp
    start_stub = mission_fixture.MissionClientTests.start_stub
    write_config = mission_fixture.MissionClientTests.write_config
    source_fixture = mission_fixture.MissionClientTests.source_fixture

    def stage_path(self, value=None):
        value = command() if value is None else value
        identity = hashlib.sha256((value["mission_id"] + "\0" + value["command_id"]).encode()).hexdigest()
        return self.root / ".runtime" / "reflection-commands" / ("rc-" + identity + ".json")

    def test_exact_staging_before_post_duplicate_collect_and_conflict(self):
        value = command(submit=True)
        def callback(handler, body):
            self.assertEqual(self.stage_path(value).read_bytes(), canonical(value).encode())
            self.assertEqual(stat.S_IMODE(self.stage_path(value).stat().st_mode), 0o600)
            handler.reply(receipt(value))
        self.server.callback = callback
        expected = self.client.reflection_command(value, wait_seconds=0)
        self.assertEqual(expected, receipt(value))
        self.assertEqual(MissionClient(self.root).reflection_command(value, wait_seconds=0), expected)
        self.assertEqual([call[0] for call in self.server.calls], ["POST", "GET"])
        self.assertEqual(urlsplit(self.server.calls[1][1]).path, "/api/reflection/result")
        changed = deepcopy(value)
        changed["proposal"]["reason"] = "Corrected body requires a new ID"
        with self.assertRaises(MissionClientError):
            self.client.reflection_command(changed, wait_seconds=0)
        self.assertEqual(len(self.server.calls), 2)
        self.assertFalse((self.root / ".runtime" / "mission-requests").exists())

    def test_lost_post_pending_and_missing_are_collection_only_after_restart(self):
        def disconnect(handler, body):
            handler.connection.shutdown(socket.SHUT_RDWR)
            handler.connection.close()
        self.server.callback = disconnect
        value = command(submit=True)
        first = self.client.reflection_command(value, wait_seconds=0)
        self.assertEqual(first["status"], "unknown")
        self.server.callback = lambda handler, body: handler.reply(receipt(value, status="pending"))
        second = MissionClient(self.root).reflection_command(value, wait_seconds=0)
        self.assertEqual(second["status"], "pending")
        self.server.callback = lambda handler, body: handler.reply(receipt(value, status="missing", admitted=False))
        third = self.client.reflection_command(value, wait_seconds=0)
        self.assertEqual(third["status"], "unknown")
        self.assertEqual([call[0] for call in self.server.calls], ["POST", "GET", "GET"])

    def test_pending_post_polls_original_only_and_correlates_command(self):
        value = command()
        def callback(handler, body):
            handler.reply(receipt(value, status="pending") if body else receipt(value))
        self.server.callback = callback
        self.assertEqual(self.client.reflection_command(value, wait_seconds=.5), receipt(value))
        self.assertEqual([call[0] for call in self.server.calls], ["POST", "GET"])
        self.server.callback = lambda handler, body: handler.reply(receipt(command("other")))
        self.assertEqual(self.client.reflection_collect("mission-a", "reflector-a", "command-1", wait_seconds=0)["status"], "unknown")

    def test_busy_retry_is_bounded_same_claim_only_known_zero_admission(self):
        value = command()
        busy = receipt(value, status="busy", admitted=False, reason="pending_limit")
        self.server.callback = lambda handler, body: handler.reply(busy)
        with patch("harness.mission_client.time.sleep") as sleep:
            self.assertEqual(self.client.reflection_command(value, wait_seconds=1), busy)
        self.assertEqual(len(self.server.calls), 3)
        self.assertTrue(all(call[3] == value for call in self.server.calls))
        self.assertTrue(all(0 <= call.args[0] <= .2 for call in sleep.call_args_list))
        self.server.calls.clear()
        submitted = command("submit-busy", submit=True)
        self.server.callback = lambda handler, body: handler.reply(receipt(submitted, status="busy", admitted=False))
        self.client.reflection_command(submitted, wait_seconds=1)
        self.assertEqual(len(self.server.calls), 1)

    def test_busy_retry_uses_original_deadline_and_uncertain_busy_never_retries(self):
        value = command()
        busy = receipt(value, status="busy", admitted=False)
        self.server.callback = lambda handler, body: handler.reply(busy)
        started = time.monotonic()
        self.assertEqual(self.client.reflection_command(value, wait_seconds=.03), busy)
        self.assertLess(time.monotonic() - started, .8)
        self.assertEqual(len(self.server.calls), 1)
        self.server.calls.clear()
        value = command("uncertain-busy")
        self.server.callback = lambda handler, body: handler.reply(receipt(value, status="busy", admitted=False, grants_authority=True))
        self.assertEqual(self.client.reflection_command(value, wait_seconds=1)["status"], "unknown")
        self.assertEqual(len(self.server.calls), 1)

    def test_bounded_malformed_receipts_return_unknown_without_post_retry(self):
        for index, change in enumerate((dict(result=dict(huge="x" * (MAX_RESULT_BYTES + 1))),
                                        dict(grants_authority=True), dict(admitted="yes"),
                                        dict(extra="no"), dict(result=[]))):
            value = command(f"malformed-{index}")
            response = receipt(value) | change
            self.server.callback = lambda handler, body: handler.reply(response)
            self.assertEqual(self.client.reflection_command(value, wait_seconds=1)["status"], "unknown")
        self.assertEqual([call[0] for call in self.server.calls], ["POST"] * 5)
        self.server.calls.clear()
        unsafe = command("unsafe-busy")
        self.server.callback = lambda handler, body: handler.reply(receipt(unsafe, status="busy", admitted=True))
        self.assertEqual(self.client.reflection_command(unsafe, wait_seconds=1)["status"], "unknown")
        self.assertEqual(len(self.server.calls), 1)

    def test_stage_symlink_partial_nonregular_and_cancel_fence(self):
        target = self.root / "foreign"
        target.mkdir()
        path = self.stage_path()
        path.parent.symlink_to(target, target_is_directory=True)
        with self.assertRaises(MissionClientError): self.client.reflection_command(command(), wait_seconds=0)
        path.parent.unlink()
        path.parent.mkdir()
        destination = target / "body"
        destination.write_text(canonical(command()))
        path.symlink_to(destination)
        with self.assertRaises(MissionClientError): self.client.reflection_command(command(), wait_seconds=0)
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(MissionClientError): self.client.reflection_command(command(), wait_seconds=0)
        path.unlink()
        path.write_text('{"schema":')
        path.chmod(0o600)
        with self.assertRaises(MissionClientError): self.client.reflection_command(command(), wait_seconds=0)
        path.unlink()
        with patch.object(self.client._opener, "open", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.client.reflection_command(command(), wait_seconds=0)
        self.assertEqual(self.server.calls, [])
        self.server.callback = lambda handler, body: handler.reply(receipt())
        self.assertEqual(self.client.reflection_command(command(), wait_seconds=0), receipt())
        self.assertEqual([call[0] for call in self.server.calls], ["GET"])

    def test_closed_reads_scope_and_bounds_fail_before_network(self):
        for invalid in (-1, 15.1, True, float("nan")):
            with self.assertRaises(MissionClientError):
                self.client.reflection_next("mission-a", "reflector-a", wait_seconds=invalid)
        with self.assertRaises(ContractError):
            self.client.reflection_command(command(extra="no"), wait_seconds=0)
        for identity in ("../foreign", "https://foreign", "x/y"):
            with self.assertRaises(ContractError):
                self.client.reflection_source("mission-a", "reflector-a", "job-1", identity)
        self.assertEqual(self.server.calls, [])
        self.server.callback = lambda handler, body: handler.reply(dict(status="offered", job=wrapper(), grants_authority=False))
        result = self.client.reflection_next("mission-a", "reflector-a", wait_seconds=0)
        self.assertEqual(result["job"]["job"], job())
        self.assertEqual(parse_qs(urlsplit(self.server.calls[-1][1]).query),
                         dict(mission_id=["mission-a"], reflector_id=["reflector-a"], wait_seconds=["0.0"]))
        self.server.callback = lambda handler, body: handler.reply(dict(status="offered", job=wrapper(job(mission_id="other")), grants_authority=False))
        with self.assertRaises(MissionClientError): self.client.reflection_next("mission-a", "reflector-a", wait_seconds=0)

    def test_exact_source_uses_reflection_endpoints_and_hash_checks(self):
        metadata, image, source_id = self.source_fixture()
        self.server.callback = lambda handler, body: handler.reply(metadata if urlsplit(handler.path).path == "/api/reflection/source" else image)
        self.assertEqual(self.client.reflection_source("mission-a", "reflector-a", "job-1", source_id), (metadata, image))
        for method, path, headers, body, _ in self.server.calls:
            self.assertEqual(method, "GET")
            self.assertEqual(parse_qs(urlsplit(path).query), dict(mission_id=["mission-a"], reflector_id=["reflector-a"], job_id=["job-1"], source_id=[source_id]))
            self.assertEqual(headers["X-Cdda-Token"], self.config["token"])
        self.assertEqual([urlsplit(call[1]).path for call in self.server.calls], ["/api/reflection/source", "/api/reflection/frame"])
        self.server.callback = lambda handler, body: handler.reply(metadata if urlsplit(handler.path).path == "/api/reflection/source" else image + b"bad")
        with self.assertRaises(MissionClientError): self.client.reflection_source("mission-a", "reflector-a", "job-1", source_id)

    def test_passive_proposal_validated_without_staging(self):
        response = dict(status="available", proposal=proposal(), grants_authority=False)
        self.server.callback = lambda handler, body: handler.reply(response)
        self.assertEqual(self.client.reflection_advice("mission-a", "proposal-1"), response)
        self.assertEqual(self.server.calls[-1][0], "GET")
        self.assertEqual(urlsplit(self.server.calls[-1][1]).path, "/api/reflection/proposal")
        self.assertFalse(self.stage_path().parent.exists())
        response["proposal"]["mission_id"] = "other"
        with self.assertRaises(MissionClientError): self.client.reflection_advice("mission-a", "proposal-1")
        self.server.callback = lambda handler, body: handler.reply(dict(status="missing", grants_authority=False))
        self.assertEqual(self.client.reflection_advice("mission-a", "proposal-1")["status"], "missing")
        self.server.callback = lambda handler, body: handler.reply(dict(status="missing", grants_authority=0))
        with self.assertRaises(MissionClientError): self.client.reflection_advice("mission-a", "proposal-1")


if __name__ == "__main__":
    unittest.main()
