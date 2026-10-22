"""CLI discovery version checks reject mixed services before any HTTP request."""
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from harness import __main__ as cli


class DiscoveryTests(unittest.TestCase):
    def test_mixed_or_missing_protocol_never_contacts_service(self):
        for version in (None, 1, 2, 3, 4, 5, 7, True, 6.0, "6"):
            with self.subTest(version=version):
                config = {"port": 8766, "token": "local", "protocol": version}
                output = StringIO()
                with patch.object(cli, "read_json", return_value=config), \
                        patch.object(cli, "build_opener") as opener, \
                        patch("sys.argv", ["harness", "status"]), redirect_stderr(output):
                    self.assertEqual(cli.main(), 1)
                    opener.assert_not_called()
                self.assertIn("Unsupported service protocol", output.getvalue())

    def test_matching_service_uses_discovered_port(self):
        config = {"port": 8766, "token": "local", "protocol": 6}
        opener = Mock()
        opener.open.return_value = BytesIO(b'{"paused":true}')
        with patch.object(cli, "read_json", return_value=config), \
                patch.object(cli, "build_opener", return_value=opener), \
                patch("sys.argv", ["harness", "status"]), redirect_stdout(StringIO()):
            self.assertEqual(cli.main(), 0)
        self.assertEqual(opener.open.call_args.args[0].full_url,
                         "http://127.0.0.1:8766/api/status")


class RecoveryCliTests(unittest.TestCase):
    def invoke(self, arguments, result=b'{"status":"not_applicable"}', error=False):
        output = StringIO()
        opener = Mock()
        if error:
            opener.open.side_effect = HTTPError("http://local", 409, "Conflict", {}, BytesIO(result))
        else:
            opener.open.return_value = BytesIO(result)
        with patch.object(cli, "read_json", return_value={"protocol": 6, "port": 8766, "token": "local"}), \
                patch.object(cli, "build_opener", return_value=opener), \
                patch("sys.argv", ["harness", *arguments]), redirect_stdout(output), redirect_stderr(StringIO()):
            code = cli.main()
        return code, output.getvalue(), opener

    def test_recovery_uses_explicit_authority_and_separate_endpoint(self):
        for operation in ("request_interrupt", "answer_interrupt", "continue_debug_once"):
            arguments = [operation, "--session", "seen-session", "--generation", "7", "--timeout", "1"]
            expected = {"kind": operation, "expected_session": "seen-session", "expected_control_generation": 7, "timeout": 1.0}
            if operation != "request_interrupt":
                arguments += ["--boundary", "shown-boundary", "--revision", "4", "--frame", "shown.png"]
                expected.update(expected_boundary_id="shown-boundary", expected_revision=4, expected_frame="shown.png")
            if operation == "answer_interrupt":
                arguments += ["--interrupt-request-id", "owner", "--choice", "NO"]
                expected.update(interrupt_request_id="owner", choice="NO")
            code, output, opener = self.invoke(arguments)
            self.assertEqual(code, 0)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:8766/api/recovery")
            self.assertEqual(json.loads(request.data), expected)
            self.assertEqual(request.get_header("X-cdda-token"), "local")
            self.assertEqual(opener.open.call_count, 1)

    def test_recovery_required_flags_and_invalid_values_never_contact_service(self):
        for arguments in (["request_interrupt"], ["request_interrupt", "--session", "s", "--generation", "-1"],
                          ["answer_interrupt", "--session", "s", "--generation", "1"],
                          ["continue_debug_once", "--session", "s", "--generation", "1"]):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as error:
                self.invoke(arguments)
            self.assertEqual(error.exception.code, 2)
        for timeout in ("nan", "inf", "0", "16"):
            code, _, opener = self.invoke(["request_interrupt", "--session", "s", "--generation", "0", "--timeout", timeout])
            self.assertEqual(code, 1)
            opener.open.assert_not_called()

    def test_recovery_failure_preserves_complete_json_without_retry(self):
        result = {"status": "unknown", "id": "control-id", "error": "uncertain", "retirement": "claimed"}
        code, output, opener = self.invoke(["request_interrupt", "--session", "s", "--generation", "0"],
                                            json.dumps(result).encode(), error=True)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output), result)
        self.assertEqual(opener.open.call_count, 1)


class MissionCliTests(unittest.TestCase):
    invoke = RecoveryCliTests.invoke

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / ".runtime" / "mission-requests"
        self.directory.mkdir(parents=True)
        self.path = self.directory / "request.json"
        self.record = dict(schema="mission/10", kind="observe", request_id="observe-1", mission_id="mission-1", epoch=0)
        self.path.write_text(json.dumps(self.record))
        root_patch = patch.object(cli, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def submit(self, path=None, **changes):
        return self.invoke(["mission-request", "--request", str(self.path if path is None else path)], **changes)

    def test_mission_record_uses_exact_payload_and_authenticated_endpoint(self):
        code, _, opener = self.submit(result=b'{"status":"accepted","mission":null}')
        self.assertEqual(code, 0)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8766/api/mission")
        self.assertEqual(json.loads(request.data), self.record)
        self.assertEqual(request.get_header("X-cdda-token"), "local")
        self.assertEqual(opener.open.call_count, 1)

    def test_malformed_old_contract_script_and_oversized_records_never_contact_service(self):
        for value in (json.dumps({**self.record, "schema":"mission/1"}), json.dumps({**self.record, "extra":1}),
                '{"schema":"mission/10","schema":"mission/10"}', '[]', 'NaN', 'x'*65537,
                'import os; os.system("false")'):
            self.path.write_text(value)
            code, _, opener = self.submit()
            self.assertEqual(code, 1, value[:80])
            opener.open.assert_not_called()

    def test_request_staging_cannot_read_outside_directory_symlinks_or_missing_files(self):
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(self.record))
        link = self.directory / "linked.json"
        link.symlink_to(outside)
        alias = self.root / "request-alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        wrong_suffix = self.directory / "request.py"
        wrong_suffix.write_text(json.dumps(self.record))
        for path in (outside, link, alias / self.path.name, wrong_suffix, self.directory / "missing.json", self.directory):
            code, _, opener = self.submit(path)
            self.assertEqual(code, 1, path)
            opener.open.assert_not_called()

    def test_retired_waypoint_commands_are_not_parser_aliases(self):
        for name in ("gameplay-start", "gameplay-continue", "gameplay-abandon", "gameplay-request", "gameplay-plan"):
            with self.subTest(name=name), self.assertRaises(SystemExit) as error:
                self.invoke([name])
            self.assertEqual(error.exception.code, 2)

    def test_mission_http_rejections_preserve_json_without_retry(self):
        for result in ({"error":"Invalid command fields"},
                {"status":"rejected","reason":"Stale request","mission":{"mission_id":"retained"}}):
            code, output, opener = self.submit(result=json.dumps(result).encode(), error=True)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output), result)
            self.assertEqual(opener.open.call_count, 1)
