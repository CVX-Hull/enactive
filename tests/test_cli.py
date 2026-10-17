"""CLI discovery version checks reject mixed services before any HTTP request."""
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
import unittest
from unittest.mock import Mock, patch

from harness import __main__ as cli


class DiscoveryTests(unittest.TestCase):
    def test_mixed_or_missing_protocol_never_contacts_service(self):
        for version in (None, 1, 3, True, "2"):
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
        config = {"port": 8766, "token": "local", "protocol": 2}
        opener = Mock()
        opener.open.return_value = BytesIO(b'{"paused":true}')
        with patch.object(cli, "read_json", return_value=config), \
                patch.object(cli, "build_opener", return_value=opener), \
                patch("sys.argv", ["harness", "status"]), redirect_stdout(StringIO()):
            self.assertEqual(cli.main(), 0)
        self.assertEqual(opener.open.call_args.args[0].full_url,
                         "http://127.0.0.1:8766/api/status")
