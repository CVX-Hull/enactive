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
        for version in (None, 1, 2, 3, 5, True, 4.0, "4"):
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
        config = {"port": 8766, "token": "local", "protocol": 4}
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
        with patch.object(cli, "read_json", return_value={"protocol": 4, "port": 8766, "token": "local"}), \
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


class GameplayCliTests(unittest.TestCase):
    invoke = RecoveryCliTests.invoke

    def test_gameplay_commands_use_exact_payload_and_authenticated_endpoint(self):
        cases = [(["gameplay-start", "east", "--distance", "2", "--expect", "seen:7"],
                  {"kind": "start", "direction": "east", "distance": 2, "expected_session": "seen", "expected_revision": 7}),
                 (["gameplay-continue", "run", "--epoch", "3", "--expect", "seen:8"],
                  {"kind": "continue", "run_id": "run", "execution_epoch": 3, "expected_session": "seen", "expected_revision": 8}),
                 (["gameplay-abandon", "run", "--epoch", "3"],
                  {"kind": "abandon", "run_id": "run", "execution_epoch": 3}),
                 (["gameplay-request"], {"kind": "planning_request"})]
        for arguments, expected in cases:
            code, _, opener = self.invoke(arguments, b'{"status":"accepted","gameplay":null}')
            self.assertEqual(code, 0)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:8766/api/gameplay")
            self.assertEqual(json.loads(request.data), expected)
            self.assertEqual(request.get_header("X-cdda-token"), "local")

    def test_candidate_file_is_bounded_json_with_exact_current_schema(self):
        candidate = {"schema": "gameplay/2", "record_type": "PlanCandidate", "candidate_id": "candidate", "task_id": "task", "task_version": 1,
                     "plan_id": "plan", "plan_version": 1, "execution_epoch": 0, "evidence_session": "seen",
                     "evidence_revision": 7, "stage": "outbound", "direction": "east", "distance_remaining": 2,
                     "skill_id": "cardinal_movement", "skill_version": 3, "reason": "Visible route is clear"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate))
            arguments = ["gameplay-plan", "request", "--candidate", str(path)]
            code, _, opener = self.invoke(arguments)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(opener.open.call_args.args[0].data),
                             {"kind": "plan", "request_id": "request", "candidate": candidate})
            for text in [json.dumps({**candidate, "schema": "gameplay/1"}), json.dumps({**candidate, "extra": 1}),
                         '{"schema":"gameplay/2","schema":"gameplay/2"}', '[]', 'NaN', 'x' * 4097,
                         'import os; os.system("false")']:
                path.write_text(text)
                code, _, opener = self.invoke(arguments)
                self.assertEqual(code, 1, text[:80])
                opener.open.assert_not_called()
            path.unlink()
            code, _, opener = self.invoke(arguments)
            self.assertEqual(code, 1)
            opener.open.assert_not_called()

    def test_gameplay_invalid_cli_authority_never_contacts_service(self):
        for arguments in (["gameplay-start", "north", "--distance", "5", "--expect", "s:1"],
                          ["gameplay-start", "north", "--distance", "1"],
                          ["gameplay-continue", "run", "--epoch", "-1", "--expect", "s:1"],
                          ["gameplay-abandon", "run"], ["gameplay-request", "--extra", "1"]):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as error:
                self.invoke(arguments)
            self.assertEqual(error.exception.code, 2)

    def test_gameplay_http_ingress_and_runtime_rejections_preserve_json_without_retry(self):
        for result in ({"error": "Invalid command fields"},
                       {"status": "rejected", "error": "Stale request", "gameplay": {"run_id": "retained"}}):
            code, output, opener = self.invoke(["gameplay-request"], json.dumps(result).encode(), error=True)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output), result)
            self.assertEqual(opener.open.call_count, 1)
