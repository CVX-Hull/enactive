"""Frozen custodian contract tests; only controlled subprocesses, no paid/native work."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from tests.test_mission_contracts import admission
from tools import campaign_run as run


class CampaignRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.run = self.root / ".runtime/campaigns/mission-test"
        self.frozen = self.run / "frozen"
        self.frozen.mkdir(parents=True)
        (self.run / "preparation").mkdir()
        (self.root / ".runtime/bridge").mkdir()
        value = admission()
        self.admission = replace(value, configuration=replace(value.configuration, model="fixture-model")).to_dict()
        inputs = {"admission.json": self.admission, "player-pi-configuration.json": {
            "schema": "pi-player-host/2", "model": {"id": "fixture-model"},
            "api_key_env": "DEEPINFRA_API_KEY", "max_requests": 4},
            "player-host-configuration.json": {"command": sys.executable,
                "args": ["-m", "harness.player_mcp"], "cwd": str(self.root), "enabled": True, "required": True}}
        for name in run._INPUTS:
            (self.frozen / name).write_text(json.dumps(inputs[name]) if name in inputs else "Frozen context\n")
        self.profile = {"schema": "campaign-run/1", "mission_id": "mission-test", "source_commit": "a" * 40,
            "effort": "off", "max_hosts": 2, "begin_normal_ending_seconds": 1,
            "complete_normal_ending_before_seconds": 2,
            "validation": {name: {"source_commit": "a" * 40, "passed": True} for name in ("fast", "focused")},
            "provider": {"prior_requests": 2, "new_requests_max": 8, "total_requests_max": 10,
                "prior_reservation_usd": "1.00", "per_request_reservation_usd": "0.10",
                "total_reservation_usd": "1.80", "reservation_limit_usd": "2.00"}}
        self.freeze()
        self.enterContext(patch.object(run, "_source"))
        self.enterContext(patch.object(run.subprocess, "run"))  # Pure Node validation is separate from subprocess custody.
        self.enterContext(patch.dict(os.environ, {"DEEPINFRA_API_KEY": "fixture-private-value"}))

    def freeze(self):
        self.profile["files"] = {name: hashlib.sha256((self.frozen / name).read_bytes()).hexdigest()
            for name in run._INPUTS}
        (self.frozen / "manifest.json").write_text(json.dumps(self.profile))

    def test_redaction_covers_arbitrary_nested_output_and_escaped_secret(self):
        import io
        output = io.StringIO()
        with patch.dict(os.environ, {"DEEPINFRA_API_KEY": 'fixture-"escaped-secret'}):
            value = {"arbitrary": {"error": 'echo fixture-"escaped-secret'}}
            run._write(output, value)
            self.assertEqual(json.loads(output.getvalue()), {"arbitrary": {"error": "echo [REDACTED]"}})

    def test_preflight_requires_current_data_and_exact_source_declarations(self):
        self.assertEqual(run._preflight(self.root, "mission-test")[2], self.admission)
        self.profile["validation"]["fast"]["source_commit"] = "b" * 40
        self.freeze()
        with self.assertRaisesRegex(run.RunError, "exact-source"):
            run._preflight(self.root, "mission-test")

    def test_prior_mission_admission_and_driver_evidence_refuse_replay(self):
        mission = self.root / ".runtime/missions/mission-test"
        mission.mkdir(parents=True)
        with self.assertRaisesRegex(run.RunError, "Prior mission"):
            run._preflight(self.root, "mission-test")
        mission.rmdir()
        staged = self.root / ".runtime/mission-requests"
        staged.mkdir()
        path = staged / "mc-original.json"
        path.write_text(json.dumps({"kind": "start", "admission": self.admission}))
        with self.assertRaisesRegex(run.RunError, "Prior admission"):
            run._preflight(self.root, "mission-test")
        path.unlink()
        (self.run / "driver-original.jsonl").touch()
        with self.assertRaisesRegex(run.RunError, "Prior driver"):
            run._preflight(self.root, "mission-test")

    def test_frozen_mutation_and_reservation_overrun_refuse(self):
        context = self.frozen / "pi-player-context.txt"
        context.write_text("changed")
        with self.assertRaisesRegex(run.RunError, "differs"):
            run._preflight(self.root, "mission-test")
        self.freeze()
        self.profile["provider"]["total_reservation_usd"] = "2.01"
        self.freeze()
        with self.assertRaisesRegex(run.RunError, "reservation"):
            run._preflight(self.root, "mission-test")

    def test_ending_and_fixed_cleanup_must_fit_original_admission(self):
        self.profile["complete_normal_ending_before_seconds"] = self.admission["limits"]["wall_seconds"]
        self.freeze()
        with self.assertRaisesRegex(run.RunError, "reserves"):
            run._preflight(self.root, "mission-test")

    def test_ack_requires_original_completed_admitted_result(self):
        result = self.ack()
        self.assertTrue(run._admitted(result, "start-1", "mission-test"))
        result["response"]["operation"]["result"] = {"admitted": False}
        self.assertFalse(run._admitted(result, "start-1", "mission-test"))
        self.assertFalse(run._admitted(self.ack(), "different-request", "mission-test"))

    def ack(self):
        return {"transport": "delivered", "settled": True, "operation_id": "start-1",
            "response": {"status": "accepted", "operation": {"request_id": "start-1", "kind": "start",
                "state": "completed", "result": {"admitted": True}}},
            "next_snapshot": {"mission": {"mission_id": "mission-test", "phase": "admitted"}}}

    def exercise(self, *, ack=True, lost=False, deadline=False, cancel=False, nonterminal=False):
        """Actual children stand in for controller/driver; SDK is an explicit double."""
        children, launches = [], []
        real_popen = subprocess.Popen
        boot = "c" * 32
        discovery = self.root / ".runtime/bridge/controller.json"
        shutdown = self.root / ".runtime/bridge" / f"mission-shutdown-{boot}.json"
        client = Mock()
        client.status.side_effect = [{"mission": None, "controller_boot_id": boot},
            {"mission": {"mission_id": "mission-test", "phase": "active" if nonterminal else "completed"}}]
        player = Mock()
        player.model_arguments.return_value = ({"request_id": "start-1"}, None)
        player.call.side_effect = lambda *args, **kwargs: (self.ack() if ack else {"transport": "uncertain"}, None)
        player.snapshot.return_value = ({"snapshot_id": "snap", "mission": {"mission_id": "mission-test",
            "phase": "active" if nonterminal else "completed"}}, None)
        signals = []
        @contextmanager
        def cancellation():
            yield signals
        def popen(argv, **kwargs):
            role = "controller" if "harness" in argv else "driver"
            launches.append((role, argv, kwargs["env"].copy()))
            if role == "controller":
                code = ("import signal,time,pathlib,json; "
                    "signal.signal(signal.SIGINT,lambda *a: exit(0)); time.sleep(30)")
            else:
                if cancel:
                    signals.append("SIGTERM")
                if lost:
                    children[0].kill()
                    children[0].wait(timeout=2)
                report = self.run / "preparation/driver-report.json"
                report.write_text(json.dumps({"hosts": [{"returncode": 0}]}))
                code = "import time; time.sleep(30)" if deadline or cancel else "pass"
            child = real_popen([sys.executable, "-c", code], **kwargs)
            children.append(child)
            if role == "controller":
                discovery.write_text(json.dumps({"controller_boot_id": boot,
                    "port": 8766, "controller_pid": child.pid}))
            return child
        real_stop = run._stop_child
        def stop(child, **kwargs):
            receipt = real_stop(child, **kwargs)
            if child is children[0] and not lost:
                shutdown.write_text(json.dumps({"controller_boot_id": boot, "grants_authority": False,
                    "cleanup": {"writer_settled": True, "native_absence_verified": True}}))
            return receipt
        if deadline:
            self.profile["begin_normal_ending_seconds"] = .05
            self.profile["complete_normal_ending_before_seconds"] = .15
            self.freeze()
        before = {path.name: path.read_bytes() for path in self.frozen.iterdir()}
        try:
            with patch.object(run.subprocess, "Popen", side_effect=popen), patch.object(run, "_DeadlineClient", return_value=client), patch.object(
                    run, "PlayerTools", return_value=player), patch.object(run, "_stop_child", side_effect=stop), patch.object(
                    run, "_signals", cancellation):
                receipt = run.run_campaign(root=self.root, mission_id="mission-test")
            self.assertEqual(before, {path.name: path.read_bytes() for path in self.frozen.iterdir()})
            self.assertEqual(sum(call.args[0] == "enactive_start" for call in player.call.call_args_list), 1)
            self.assertEqual(sum(call.args[0] == "enactive_stop" for call in player.call.call_args_list),
                1 if nonterminal else 0)
            self.assertNotIn("enactive_lifecycle", [call.args[0] for call in player.call.call_args_list])
            return receipt, launches
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)

    def test_finite_run_keeps_credential_only_in_driver_environment_and_freeze_immutable(self):
        receipt, launches = self.exercise()
        self.assertEqual(receipt["outcome"], "terminal")
        self.assertTrue(receipt["native_absence_verified"])
        self.assertTrue(receipt["deciding_hosts_quiescent"])
        self.assertNotIn("DEEPINFRA_API_KEY", launches[0][2])
        self.assertEqual(launches[1][2]["DEEPINFRA_API_KEY"], "fixture-private-value")
        self.assertNotIn("fixture-private-value", json.dumps(receipt))
        self.assertNotIn("fixture-private-value", json.dumps([row[1] for row in launches]))
        timeout = float(launches[1][1][-1])
        self.assertGreater(timeout, 0)
        self.assertLessEqual(timeout, self.profile["complete_normal_ending_before_seconds"])
        with self.assertRaisesRegex(run.RunError, "Prior driver"):
            run.run_campaign(root=self.root, mission_id="mission-test")
        for path in (self.run / "preparation").iterdir():
            self.assertNotIn(b"fixture-private-value", path.read_bytes())

    def test_exclusive_artifact_collision_never_launches_controller(self):
        path = self.run / "preparation/custodian-receipt.json"
        path.write_text("retained original evidence")
        with patch.object(run.subprocess, "Popen") as popen:
            with self.assertRaises(FileExistsError):
                run.run_campaign(root=self.root, mission_id="mission-test")
            popen.assert_not_called()
        self.assertEqual(path.read_text(), "retained original evidence")

    def test_uncertain_admission_never_launches_deciding_driver(self):
        receipt, launches = self.exercise(ack=False)
        self.assertFalse(receipt["admission_acknowledged"])
        self.assertEqual([role for role, _, _ in launches], ["controller"])

    def test_nonterminal_driver_exit_uses_only_exceptional_stop(self):
        receipt, _ = self.exercise(nonterminal=True)
        self.assertEqual(receipt["outcome"], "incomplete")
        self.assertTrue(receipt["exceptional_stop"])
        self.assertFalse(receipt["normal_ending_claimed"])
        self.assertFalse(receipt["acceptance_claimed"])

    def test_lost_controller_does_not_imply_native_absence(self):
        receipt, _ = self.exercise(lost=True)
        self.assertFalse(receipt["native_absence_verified"])
        self.assertTrue(receipt["native_cleanup_unknown"])
        self.assertIsNone(receipt["shutdown_receipt"])

    def test_original_deadline_and_cancellation_stop_exact_owned_children(self):
        for option in ("deadline", "cancel"):
            with self.subTest(option=option):
                if option == "cancel":
                    for path in (self.run / "preparation").iterdir():
                        path.unlink()
                    for path in (self.root / ".runtime/bridge").iterdir():
                        path.unlink()
                started = time.monotonic()
                receipt, _ = self.exercise(**{option: True})
                self.assertLess(time.monotonic() - started, 3)
                self.assertEqual(receipt["outcome"], "incomplete")
                self.assertIn("SIGINT", receipt["children"]["driver"]["signals"])


class OwnedChildTests(unittest.TestCase):
    def test_exact_child_cleanup_never_signals_an_unrelated_child(self):
        children = [subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"]) for _ in range(2)]
        try:
            result = run._stop_child(children[0], deadline=time.monotonic() + 2, first_wait=1)
            self.assertFalse(result["exit_unresolved"])
            self.assertIsNone(children[1].poll())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)


class SourceCheckpointTests(unittest.TestCase):
    def test_exact_clean_git_checkpoint_refuses_untracked_or_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git("init")
            source = root / "source.txt"
            source.write_text("committed")
            git("add", "source.txt")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
            revision = git("rev-parse", "HEAD")
            run._source(root, revision)
            source.write_text("changed")
            with self.assertRaisesRegex(run.RunError, "clean committed"):
                run._source(root, revision)
            source.write_text("committed")
            (root / "untracked.txt").write_text("untracked")
            with self.assertRaisesRegex(run.RunError, "clean committed"):
                run._source(root, revision)
