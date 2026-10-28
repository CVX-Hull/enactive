"""Frozen custodian contract tests; only controlled subprocesses, no paid/native work."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import textwrap
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
            "schema": "pi-player-host/2", "model": {"id": "fixture-model", "name": "Offline fixture",
                "api": "openai-completions", "provider": "fixture", "baseUrl": "https://fixture.invalid/v1",
                "reasoning": False, "input": ["text", "image"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 100000, "maxTokens": 1024},
            "api_key_env": "DEEPINFRA_API_KEY", "max_requests": 4,
            "max_context_images": 4, "request_timeout_seconds": 2},
            "player-host-configuration.json": {"command": sys.executable,
                "args": ["-m", "harness.player_mcp"], "cwd": str(self.root), "enabled": True, "required": True,
                "enabled_tools": ["enactive_snapshot"], "startup_timeout_sec": 10, "tool_timeout_sec": 60}}
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
        self.validation_patch = patch.object(run.subprocess, "run")
        self.node_validation = self.validation_patch.start()
        self.addCleanup(self.validation_patch.stop)
        self.enterContext(patch.dict(os.environ, {"DEEPINFRA_API_KEY": "fixture-private-value"}))

    def freeze(self):
        self.profile["files"] = {name: hashlib.sha256((self.frozen / name).read_bytes()).hexdigest()
            for name in run._INPUTS}
        (self.frozen / "manifest.json").write_text(json.dumps(self.profile))

    def test_frozen_node_or_unknown_manifest_key_refuses_before_exec_or_admission(self):
        for key, value in (("node", "/usr/bin/true"), ("unknown", True)):
            with self.subTest(key=key):
                self.profile[key] = value
                self.freeze()
                with patch.object(run, "PlayerTools") as player, patch.object(run.subprocess, "Popen") as popen:
                    with self.assertRaisesRegex(run.RunError, "manifest"):
                        run.run_campaign(root=self.root, mission_id="mission-test")
                    player.assert_not_called()
                    popen.assert_not_called()
                self.node_validation.assert_not_called()
                del self.profile[key]

    def prepare_actual_node_validator(self):
        self.validation_patch.stop()
        source = Path(__file__).resolve().parents[1] / "tools/player_host"
        target = self.root / "tools/player_host"
        target.mkdir(parents=True)
        (target / "host.mjs").write_bytes((source / "host.mjs").read_bytes())
        dependencies = source / "node_modules"
        if not dependencies.is_dir():
            dependencies = Path(sys.prefix).parent / "tools/player_host/node_modules"
        self.assertTrue(dependencies.is_dir(), "Prepared project-local Pi dependencies are required")
        (target / "node_modules").symlink_to(dependencies, target_is_directory=True)
        node = shutil.which("node")
        self.assertIsNotNone(node, "Prepared Node runtime is required")
        return node

    def test_actual_maintained_node_validates_complete_route_and_mcp_before_admission(self):
        node = self.prepare_actual_node_validator()
        self.assertEqual(run._preflight(self.root, "mission-test", node=node)[2], self.admission)
        for name, field, value in (("player-pi-configuration.json", "max_requests", 0),
                ("player-pi-configuration.json", "schema", "unsupported"),
                ("player-host-configuration.json", "enabled_tools", None),
                ("player-host-configuration.json", "startup_timeout_sec", None),
                ("player-host-configuration.json", "tool_timeout_sec", None)):
            with self.subTest(name=name, field=field):
                path = self.frozen / name
                original = path.read_bytes()
                data = json.loads(original)
                if value is None:
                    del data[field]
                else:
                    data[field] = value
                path.write_text(json.dumps(data))
                self.freeze()
                with patch.object(run, "PlayerTools") as player:
                    with self.assertRaises(subprocess.CalledProcessError):
                        run.run_campaign(root=self.root, mission_id="mission-test", node=node)
                    player.assert_not_called()
                path.write_bytes(original)
        self.profile["effort"] = "unsupported"
        self.freeze()
        with self.assertRaises(subprocess.CalledProcessError):
            run._preflight(self.root, "mission-test", node=node)

    def test_duplicate_nonfinite_json_and_nonstring_costs_refuse_before_admission(self):
        manifest = self.frozen / "manifest.json"
        for payload in ('{"schema":"campaign-run/1","schema":"campaign-run/1"}', '{"number":NaN}'):
            with self.subTest(payload=payload):
                manifest.write_text(payload)
                with patch.object(run, "PlayerTools") as player:
                    with self.assertRaises(ValueError):
                        run.run_campaign(root=self.root, mission_id="mission-test")
                    player.assert_not_called()
                self.node_validation.assert_not_called()
        for value in (True, 1.8, 1, "NaN", "Infinity"):
            with self.subTest(cost=value):
                self.profile["provider"]["total_reservation_usd"] = value
                self.freeze()
                with patch.object(run, "PlayerTools") as player:
                    with self.assertRaisesRegex(run.RunError, "monetary"):
                        run.run_campaign(root=self.root, mission_id="mission-test")
                    player.assert_not_called()

    def test_fixed_owned_runtime_directories_refuse_symlinks_without_outside_read(self):
        with tempfile.TemporaryDirectory() as outside:
            for name in ("bridge", "missions", "mission-requests"):
                with self.subTest(name=name):
                    path = self.root / ".runtime" / name
                    if path.exists():
                        path.rmdir()
                    path.symlink_to(outside, target_is_directory=True)
                    with patch.object(run, "_read", side_effect=AssertionError("No file read before path refusal")) as read, \
                            patch.object(run, "PlayerTools") as player:
                        with self.assertRaisesRegex(run.RunError, "project-local"):
                            run.run_campaign(root=self.root, mission_id="mission-test")
                        read.assert_not_called()
                        player.assert_not_called()
                    path.unlink()
                    path.write_text("not a directory")
                    with self.assertRaisesRegex(run.RunError, "project-local"):
                        run._preflight(self.root, "mission-test")
                    path.unlink()

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

    def exercise(self, *, ack=True, lost=False, deadline=False, cancel=False, nonterminal=False,
            signal_error=False, node="node", terminal_cancel_ready=None):
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
        real_signals = run._signals
        events = self.root / ".runtime/bridge/cleanup-events.jsonl"
        @contextmanager
        def cancellation():
            if terminal_cancel_ready is not None:
                with real_signals() as interrupted:
                    yield interrupted
            else:
                yield signals
        def popen(argv, **kwargs):
            role = "controller" if "harness" in argv else "driver"
            launches.append((role, argv, kwargs["env"].copy()))
            if role == "controller":
                evidence = shutdown
                value = {"controller_boot_id": boot, "grants_authority": False,
                    "cleanup": {"writer_settled": True, "native_absence_verified": True}}
            else:
                if cancel:
                    signals.append("SIGTERM")
                if lost:
                    children[0].kill()
                    children[0].wait(timeout=2)
                evidence = self.run / "preparation/driver-report.json"
                value = {"hosts": [{"returncode": 0}]}
                if terminal_cancel_ready is None:
                    evidence.write_text(json.dumps(value))
            ready = self.root / f"{role}.ready"
            ready.unlink(missing_ok=True)
            code = textwrap.dedent(f"""\
                import json, pathlib, signal, time
                def cleanup(*args):
                    # A second SIGINT during cleanup must remain observable.
                    signal.signal(signal.SIGINT, signal.default_int_handler)
                    with pathlib.Path({str(events)!r}).open('a') as stream:
                        stream.write({role + '-cleanup-start'!r} + '\\n')
                    time.sleep(.2)
                    pathlib.Path({str(evidence)!r}).write_text(json.dumps({value!r}))
                    with pathlib.Path({str(events)!r}).open('a') as stream:
                        stream.write({role + '-cleanup-complete'!r} + '\\n')
                    raise SystemExit(0)
                signal.signal(signal.SIGINT, cleanup)
                pathlib.Path({str(ready)!r}).touch()
                time.sleep(30)
                """)
            if role == "driver" and not (deadline or cancel or signal_error or terminal_cancel_ready is not None):
                code = f"import pathlib; pathlib.Path({str(ready)!r}).touch()"
            child = real_popen([sys.executable, "-c", code], **kwargs)
            children.append(child)
            ready_deadline = time.monotonic() + 3
            while not ready.exists() and child.poll() is None and time.monotonic() < ready_deadline:
                time.sleep(.01)
            self.assertTrue(ready.exists(), f"{role} did not install its signal handler")
            if role == "driver" and terminal_cancel_ready is not None:
                terminal_cancel_ready.touch()
            if role == "driver" and signal_error:
                child.send_signal = Mock(side_effect=OSError("fixture private failure body"))
            if role == "controller":
                discovery.write_text(json.dumps({"controller_boot_id": boot,
                    "port": 8766, "controller_pid": child.pid}))
            return child
        if deadline or signal_error:
            self.profile["begin_normal_ending_seconds"] = .05
            self.profile["complete_normal_ending_before_seconds"] = .15
            self.freeze()
        before = {path.name: path.read_bytes() for path in self.frozen.iterdir()}
        try:
            with patch.object(run.subprocess, "Popen", side_effect=popen), patch.object(run, "_DeadlineClient", return_value=client), patch.object(
                    run, "PlayerTools", return_value=player), patch.object(run, "_signals", cancellation):
                receipt = run.run_campaign(root=self.root, mission_id="mission-test", node=node)
            self.assertEqual(before, {path.name: path.read_bytes() for path in self.frozen.iterdir()})
            self.assertEqual(sum(call.args[0] == "enactive_start" for call in player.call.call_args_list), 1)
            self.assertEqual(sum(call.args[0] == "enactive_stop" for call in player.call.call_args_list),
                1 if nonterminal else 0)
            self.assertNotIn("enactive_lifecycle", [call.args[0] for call in player.call.call_args_list])
            return receipt, launches
        finally:
            for child in children:
                if signal_error and child is children[-1] and len(children) > 1:
                    del child.send_signal
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)

    def test_finite_run_keeps_credential_only_in_driver_environment_and_freeze_immutable(self):
        receipt, launches = self.exercise(node="/trusted/operator-node")
        self.assertEqual(self.node_validation.call_args.args[0][0], "/trusted/operator-node")
        driver_args = launches[1][1]
        self.assertEqual(driver_args[driver_args.index("--node") + 1], "/trusted/operator-node")
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

    @unittest.skipUnless(os.name == "posix", "Terminal process-group cancellation requires POSIX")
    def test_terminal_sigint_settles_isolated_driver_then_controller(self):
        ready = self.root / "custodian.ready"
        unrelated_ready = self.root / "unrelated.ready"
        # Only this retained fixture session receives the terminal-style broadcast.
        code = textwrap.dedent("""\
            import json, sys
            from pathlib import Path
            from tests.test_campaign_run import CampaignRunTests
            fixture = CampaignRunTests()
            fixture.setUp()
            try:
                receipt, _ = fixture.exercise(terminal_cancel_ready=Path(sys.argv[1]))
                events = (fixture.root / '.runtime/bridge/cleanup-events.jsonl').read_text().splitlines()
                print(json.dumps({'receipt': receipt, 'events': events}))
            finally:
                fixture.doCleanups()
            """)
        unrelated_code = (f"import pathlib,time; pathlib.Path({str(unrelated_ready)!r}).touch(); "
            "time.sleep(30)")
        children = []
        started = time.monotonic()
        try:
            unrelated = subprocess.Popen([sys.executable, "-c", unrelated_code], start_new_session=True)
            children.append(unrelated)
            custodian = subprocess.Popen([sys.executable, "-c", code, str(ready)],
                cwd=Path(__file__).resolve().parents[1], start_new_session=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            children.append(custodian)
            ready_deadline = time.monotonic() + 5
            while not (ready.exists() and unrelated_ready.exists()) and time.monotonic() < ready_deadline:
                self.assertIsNone(custodian.poll(), "Custodian fixture exited before readiness")
                self.assertIsNone(unrelated.poll(), "Unrelated fixture exited before readiness")
                time.sleep(.01)
            self.assertTrue(ready.exists() and unrelated_ready.exists(), "Fixture readiness timed out")
            self.assertEqual(os.getsid(custodian.pid), custodian.pid)
            self.assertEqual(os.getpgid(custodian.pid), custodian.pid)
            os.killpg(custodian.pid, signal.SIGINT)
            output, errors = custodian.communicate(timeout=5)
            self.assertEqual(custodian.returncode, 0, errors)
            result = json.loads(output)
            receipt = result["receipt"]
            self.assertEqual(receipt["signals"], ["SIGINT"])
            self.assertEqual(receipt["outcome"], "incomplete")
            self.assertTrue(receipt["native_absence_verified"])
            self.assertTrue(receipt["deciding_hosts_quiescent"])
            self.assertEqual(receipt["shutdown_receipt"]["controller_boot_id"], receipt["controller_boot_id"])
            for role in ("driver", "controller"):
                self.assertEqual(receipt["children"][role]["returncode"], 0)
                self.assertEqual(receipt["children"][role]["signals"], ["SIGINT"])
                self.assertFalse(receipt["children"][role]["exit_unresolved"])
            self.assertEqual(result["events"], ["driver-cleanup-start", "driver-cleanup-complete",
                "controller-cleanup-start", "controller-cleanup-complete"])
            self.assertIsNone(unrelated.poll())
            self.assertLess(time.monotonic() - started, 10)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=3)

    def test_exclusive_artifact_collision_never_launches_controller(self):
        path = self.run / "preparation/custodian-receipt.json"
        path.write_text("retained original evidence")
        with patch.object(run.subprocess, "Popen") as popen:
            with self.assertRaises(FileExistsError):
                run.run_campaign(root=self.root, mission_id="mission-test")
            popen.assert_not_called()
        self.assertEqual(path.read_text(), "retained original evidence")

    def test_driver_signal_error_retains_unknown_and_still_closes_controller(self):
        receipt, _ = self.exercise(signal_error=True)
        driver = receipt["children"]["driver"]
        self.assertTrue(driver["exit_unresolved"])
        self.assertEqual(driver["error_type"], "OSError")
        self.assertFalse(receipt["deciding_hosts_quiescent"])
        self.assertFalse(receipt["children"]["controller"]["exit_unresolved"])
        self.assertTrue(receipt["native_absence_verified"])
        self.assertEqual(receipt["outcome"], "incomplete")
        saved = (self.run / "preparation/custodian-receipt.json").read_text()
        self.assertNotIn("fixture private failure body", saved)
        self.assertTrue(json.loads(saved)["children"]["driver"]["exit_unresolved"])

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
    def test_owned_wait_errors_return_fixed_unknown_receipt(self):
        for error in (OSError("private failure"), subprocess.SubprocessError("private failure")):
            with self.subTest(error=type(error).__name__):
                child = Mock()
                child.poll.return_value = None
                child.wait.side_effect = error
                receipt = run._stop_child(child, deadline=time.monotonic() + 1, first_wait=.1)
                self.assertTrue(receipt["exit_unresolved"])
                self.assertEqual(receipt["error_type"], type(error).__name__)
                self.assertNotIn("private failure", json.dumps(receipt))

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
