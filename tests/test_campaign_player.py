"""Mechanical host continuity with fake owned subprocesses and passive SDK reads."""
import copy
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from harness.mission_client import MissionClient, MissionClientError
from harness.host_status import deciding_host_status
from tools import campaign_player as driver


def issuance():
    return dict(schema="mission/11", record_type="Handoff", handoff_id="issued-handoff",
        mission_id="mission", original_player_id="original", successor_role="successor",
        epoch=3, checkpoint_ids=["checkpoint"], unfinished_work_ids=["unfinished"],
        session="session", revision=4, boundary_id="boundary", pause_generation=2,
        takeover_generation=0, pause_origin="host", post_pause_source_id="post-pause",
        controller_boot_id="boot", operator_pause_generation=0, grants_authority=False)


def status(phase="active", **changes):
    value = dict(mission_id="mission", phase=phase, pause_cause="internal_bootstrap",
        actor_id="original", player_id="original", epoch=2, active_operation=None,
        unresolved_effects=[], clock_valid=True,
        remaining_limits={key: 100 for key in driver._LIMITS}, progress=None)
    if phase == "handoff":
        value.update(pause_cause="internal_handoff", epoch=3, progress=issuance())
    value.update(changes)
    return value


def collection():
    issued = issuance()
    request = dict(schema="mission/11", kind="handoff", request_id=issued["handoff_id"],
        mission_id="mission", epoch=2, successor_role=issued["successor_role"],
        checkpoint_ids=issued["checkpoint_ids"], unfinished_work_ids=issued["unfinished_work_ids"])
    return dict(transport="delivered", settled=True, operation_id=issued["handoff_id"],
        response=dict(status="accepted", operation=dict(state="completed", request=request, result=issued)))


def snapshot(mission=None, **changes):
    value = dict(mission=status() if mission is None else mission, frozen=False, pending=None,
        control_pending=None, operator_pause_generation=0, pause_generation=2,
        state=dict(session="session", revision=4, boundary=dict(id="boundary"), paused=True,
            takeover_generation=0, pause_origin="host"), unknown_outcomes=[], control_unknown_outcomes=[],
        error=None)
    value.update(changes)
    return value


class FakeProcess:
    def __init__(self, args, *, outcome, events, **kwargs):
        self.pid, self.returncode = 1234, None
        self.stdin = io.StringIO()
        self.args, self.kwargs, self.outcome, self.events = args, kwargs, outcome, events
        self.prompt = None
        events.append(("launch", self.pid))

    def communicate(self, prompt, *, timeout):
        self.prompt = prompt
        self.events.append(("communicate", timeout))
        self.kwargs["stdout"].write('{"type":"test-output"}\n')
        self.kwargs["stderr"].write("test stderr\n")
        Path(self.args[self.args.index("-o") + 1]).write_text("test final\n")
        if callable(self.outcome):
            return self.outcome(self)
        if self.outcome == "timeout":
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.returncode = self.outcome
        self.events.append(("exit", self.returncode))
        return None, None

    def poll(self):
        return self.returncode

    def send_signal(self, value):
        self.events.append(("signal", self.pid, value))

    def terminate(self):
        self.events.append(("terminate", self.pid))
        self.returncode = -15

    def kill(self):
        self.events.append(("kill", self.pid))
        self.returncode = -9

    def wait(self, *, timeout):
        self.events.append(("wait", timeout))
        if self.returncode is None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return self.returncode


class CampaignPlayerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.counter = 0
        self.now = 100.0
        self.configuration = dict(command="/project/python", args=["-m", "harness.player_mcp"],
            cwd="/project", enabled=True, required=True, enabled_tools=["enactive_context"],
            default_tools_approval_mode="approve", startup_timeout_sec=10, tool_timeout_sec=60,
            tools={"enactive_context": dict(output_token_limit=131072)})

    def make_run(self):
        self.counter += 1
        self.root = Path(self.temporary.name).resolve() / str(self.counter)
        self.run = self.root / ".runtime" / "campaigns" / "mission"
        (self.run / "frozen").mkdir(parents=True)
        (self.run / "preparation").mkdir()
        (self.run / "frozen" / "player-host-configuration.json").write_text(json.dumps(self.configuration))
        (self.run / "frozen" / "original-player-prompt.txt").write_text("original frozen prompt\n")
        (self.run / "frozen" / "successor-player-brief.txt").write_text("generic frozen successor brief\n")
        self.pi_configuration = dict(schema="pi-player-host/2", model=dict(
            id="frozen-model", name="Offline fixture", api="openai-completions", provider="fixture",
            baseUrl="https://fixture.invalid/v1", reasoning=False, input=["text", "image"],
            cost=dict(input=0, output=0, cacheRead=0, cacheWrite=0), contextWindow=100000,
            maxTokens=1024), api_key_env="OFFLINE_TEST_KEY", max_requests=20, max_context_images=4,
            request_timeout_seconds=2)
        self.context = "Frozen player guide, mission brief and complete current interface schemas.\n"
        (self.run / "frozen" / "player-pi-configuration.json").write_text(json.dumps(self.pi_configuration))
        (self.run / "frozen" / "pi-player-context.txt").write_text(self.context)
        return self.run

    def invoke(self, *, statuses=None, collected=None, outcomes=None, run=None, **options):
        self.run = run or self.make_run()
        self.events, self.processes = [], []
        reads = iter(statuses or [status(), status("stopped")])
        outcomes = iter([0, 0] if outcomes is None else outcomes)

        def read():
            self.events.append(("status",))
            self.assertTrue(all(process.poll() is not None for process in self.processes))
            value = next(reads)
            if callable(value):
                value = value()
            if isinstance(value, Exception):
                raise value
            if isinstance(value, dict) and "mission" in value:
                return copy.deepcopy(value)
            return {**snapshot(), "mission": copy.deepcopy(value)}

        def collect(*args, **kwargs):
            self.events.append(("collect", args, kwargs))
            if callable(collected):
                return collected()
            return copy.deepcopy(collection() if collected is None else collected)

        self.client = Mock(spec=MissionClient)
        self.client.status.side_effect = read
        self.client.collect.side_effect = collect

        def launch(args, **kwargs):
            process = FakeProcess(args, outcome=next(outcomes), events=self.events, **kwargs)
            self.processes.append(process)
            return process

        with patch.object(driver, "_DeadlineClient", return_value=self.client), \
                patch.object(driver.subprocess, "Popen", side_effect=launch) as popen, \
                patch.object(driver.uuid, "uuid4", return_value=Mock(hex="mechanical-uuid")), \
                patch.object(driver.time, "monotonic", side_effect=lambda: self.now):
            self.report = driver.run_campaign(root=self.root, run_dir=self.run, mission_id="mission",
                model="frozen-model", effort="low", timeout_seconds=60, **options)
            self.launch_count = popen.call_count
        return self.report

    def receipt(self, name):
        return json.loads((self.run / "preparation" / name).read_text())

    def test_original_terminal_has_no_handoff_and_reports_actual_phase(self):
        for phase in ("completed", "failed", "stopped"):
            with self.subTest(phase=phase):
                report = self.invoke(statuses=[status(), status(phase)])
                self.assertEqual((report["outcome"], report["phase"], report["exit_code"]), ("terminal", phase, 0))
                self.assertFalse(report["acceptance_claimed"])
                self.assertEqual(self.launch_count, 1)
                self.client.collect.assert_not_called()
                self.assertEqual(self.events[:4], [("status",), ("launch", 1234), ("communicate", 60.0), ("exit", 0)])

    def test_single_host_can_report_a_normal_terminal_mission(self):
        for phase in ("completed", "failed", "stopped"):
            with self.subTest(phase=phase):
                report = self.invoke(statuses=[status(), status(phase)], max_hosts=1)
                self.assertEqual((report["outcome"], report["phase"], report["exit_code"]), ("terminal", phase, 0))
                self.assertEqual(self.launch_count, 1)
                self.assertEqual(len(report["hosts"]), 1)
                self.client.collect.assert_not_called()

    def test_single_host_refuses_nonterminal_continuation_before_handoff_collection(self):
        for phase in ("handoff", "active", "paused"):
            with self.subTest(phase=phase):
                after = status(phase)
                report = self.invoke(statuses=[status(), after], max_hosts=1)
                self.assertEqual((report["outcome"], report["phase"], report["exit_code"]), ("incomplete", phase, 1))
                self.assertIn("no successor", report["reason"])
                self.assertEqual(self.launch_count, 1)
                self.assertEqual(len(report["hosts"]), 1)
                self.assertEqual(self.client.status.call_count, 2)
                self.client.collect.assert_not_called()
                self.client.submit.assert_not_called()
                self.assertEqual(self.receipt("driver-original-status.json")["mission"], after)
                for name in ("driver-handoff-issuance.json", "driver-successor-assignment.json",
                        "driver-successor-admission-status.json", "driver-successor-argv.json",
                        "driver-successor-process.json", "driver-successor-receipt.json"):
                    self.assertEqual((self.run / "preparation" / name).read_text(), "")
                self.assertEqual([event[0] for event in self.events],
                    ["status", "launch", "communicate", "exit", "status"])

    def test_invalid_host_limits_refuse_before_outputs_status_or_launch(self):
        for max_hosts in (True, False, 0, 3, -1, 1.0, 2.0, "1", None):
            with self.subTest(max_hosts=max_hosts):
                run = self.make_run()
                with patch.object(driver, "_DeadlineClient") as client, \
                        patch.object(driver.subprocess, "Popen") as launch, \
                        self.assertRaisesRegex(driver.DriverError, "max_hosts"):
                    driver.run_campaign(root=self.root, run_dir=run, mission_id="mission",
                        model="frozen-model", effort="low", timeout_seconds=60, max_hosts=max_hosts)
                client.assert_not_called()
                launch.assert_not_called()
                self.assertEqual(list((run / "preparation").iterdir()), [])

    def test_one_fresh_successor_uses_only_frozen_brief_and_exact_assignment(self):
        report = self.invoke(statuses=[status(), status("handoff"), status("handoff"),
            status("stopped", actor_id="successor", player_id="successor")])
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(self.launch_count, 2)
        original, successor = self.processes
        self.assertNotIn("resume", original.args)
        self.assertNotIn("resume", successor.args)
        location = "Frozen player context and current MCP schemas are supplied by the host.\n\n"
        self.assertEqual(original.prompt, location + "original frozen prompt\n")
        generic, assignment = successor.prompt.split("\n\nMechanical player assignment:\n")
        self.assertEqual(generic, location + "generic frozen successor brief\n")
        assignment = json.loads(assignment)
        self.assertEqual(assignment, dict(mission_id="mission", actor_id="successor-mechanical-uuid", actor_role="successor",
            handoff_id="issued-handoff", epoch=3,
            issuance_path=str(self.run / "preparation" / "driver-handoff-issuance.json")))
        self.assertEqual(self.receipt("driver-handoff-issuance.json"), issuance())
        self.assertEqual(self.receipt("driver-successor-assignment.json"), assignment)
        self.client.collect.assert_called_once_with("mission", "issued-handoff", wait_seconds=0)
        self.assertEqual([event[0] for event in self.events], ["status", "launch", "communicate", "exit",
            "status", "collect", "status", "launch", "communicate", "exit", "status"])
        self.client.submit.assert_not_called()
        self.client.source.assert_not_called()

    def test_exact_argv_and_retained_receipts(self):
        self.invoke()
        args = self.processes[0].args
        self.assertEqual(args, ["node", str(self.root / "tools" / "player_host" / "run.mjs"),
            "--config", str(self.run / "frozen" / "player-pi-configuration.json"),
            "--mcp-config", str(self.run / "frozen" / "player-host-configuration.json"),
            "--context", str(self.run / "frozen" / "pi-player-context.txt"),
            "--model", "frozen-model", "--effort", "low", "--timeout-seconds", "60.0",
            "-o", str(self.run / "driver-original-final.txt")])
        self.assertEqual(self.receipt("driver-original-argv.json"), args)
        process = self.receipt("driver-original-process.json")
        receipt = self.receipt("driver-original-receipt.json")
        self.assertEqual(process["pid"], 1234)
        self.assertEqual(process["start"], receipt["start"])
        self.assertGreaterEqual(receipt["end"], receipt["start"])
        self.assertEqual(receipt["returncode"], 0)
        self.assertFalse(receipt["native_cleanup_claimed"])
        self.assertEqual((self.run / "driver-original.jsonl").read_text(), '{"type":"test-output"}\n')
        self.assertEqual((self.run / "driver-original-final.txt").read_text(), "test final\n")
        self.assertEqual((self.run / "preparation" / "driver-original.stderr").read_text(), "test stderr\n")
        self.assertEqual(self.receipt("driver-report.json"), self.report)
        self.assertEqual(self.processes[0].kwargs["cwd"], self.root)
        self.assertEqual(self.processes[0].kwargs["stdin"], subprocess.PIPE)
        self.assertTrue(self.processes[0].kwargs["text"])

    def test_pi_hosts_reuse_exit_before_successor_and_original_collection(self):
        run = self.make_run()
        report = self.invoke(run=run, node="/project/node",
            statuses=[status(), status("handoff"), status("handoff"),
                status("stopped", actor_id="successor", player_id="successor")])
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(self.launch_count, 2)
        for role, process in zip(("original", "successor"), self.processes):
            self.assertEqual(process.args, ["/project/node",
                str(self.root / "tools" / "player_host" / "run.mjs"),
                "--config", str(run / "frozen" / "player-pi-configuration.json"),
                "--mcp-config", str(run / "frozen" / "player-host-configuration.json"),
                "--context", str(run / "frozen" / "pi-player-context.txt"),
                "--model", "frozen-model", "--effort", "low",
                "--timeout-seconds", "60.0", "-o", str(run / f"driver-{role}-final.txt")])
            self.assertNotIn("resume", process.args)
            self.assertTrue(process.prompt.startswith(
                "Frozen player context and current MCP schemas are supplied by the host.\n\n"))
        self.assertEqual([event[0] for event in self.events], ["status", "launch", "communicate", "exit",
            "status", "collect", "status", "launch", "communicate", "exit", "status"])
        self.client.submit.assert_not_called()

    def test_pi_host_failure_prevents_successor_and_does_not_claim_native_cleanup(self):
        run = self.make_run()
        report = self.invoke(run=run, outcomes=[1], statuses=[status()])
        self.assertEqual(self.launch_count, 1)
        self.assertEqual(report["exit_code"], 1)
        self.assertFalse(report["native_cleanup_claimed"])
        self.client.collect.assert_not_called()
        self.assertEqual([event[0] for event in self.events], ["status", "launch", "communicate", "exit"])

    def test_all_frozen_inputs_are_read_before_output_reservation_and_launch(self):
        run = self.make_run()
        names = ("player-host-configuration.json", "player-pi-configuration.json", "pi-player-context.txt",
            "original-player-prompt.txt", "successor-player-brief.txt")
        contents = {}
        read = driver._read

        def frozen_read(path):
            self.assertEqual(list((run / "preparation").iterdir()), [])
            contents[path.name] = read(path)
            return contents[path.name]

        with patch.object(driver, "_read", side_effect=frozen_read) as reads:
            self.invoke(run=run)
        self.assertEqual([call.args[0] for call in reads.call_args_list],
            [run / "frozen" / name for name in names])
        self.assertEqual(json.loads(contents["player-host-configuration.json"]), self.configuration)
        self.assertEqual(json.loads(contents["player-pi-configuration.json"]), self.pi_configuration)
        self.assertEqual(contents["pi-player-context.txt"], self.context)

    def test_missing_frozen_inputs_refuse_before_host_launch_or_output_reservation(self):
        for missing in ("player-host-configuration.json", "player-pi-configuration.json", "pi-player-context.txt",
                "original-player-prompt.txt", "successor-player-brief.txt"):
            with self.subTest(missing=missing):
                run = self.make_run()
                (run / "frozen" / missing).unlink()
                with self.assertRaises(OSError), patch.object(driver.subprocess, "Popen") as launch:
                    driver.run_campaign(root=self.root, run_dir=run, mission_id="mission",
                        model="frozen-model", effort="low", timeout_seconds=60)
                launch.assert_not_called()
                self.assertEqual(list((run / "preparation").iterdir()), [])

    def test_invalid_mcp_configuration_refuses_before_output_reservation_or_launch(self):
        for configuration in ("[]", "{", '{"command":"python","unknown":true}'):
            with self.subTest(configuration=configuration):
                run = self.make_run()
                (run / "frozen" / "player-host-configuration.json").write_text(configuration)
                with self.assertRaises(ValueError), patch.object(driver.subprocess, "Popen") as launch:
                    driver.run_campaign(root=self.root, run_dir=run, mission_id="mission",
                        model="frozen-model", effort="low", timeout_seconds=60)
                launch.assert_not_called()
                self.assertEqual(list((run / "preparation").iterdir()), [])

    def test_removed_host_and_resume_api_arguments_refuse_before_launch(self):
        run = self.make_run()
        for removed in (dict(host="pi"), dict(host="codex"), dict(codex="codex"), dict(original_thread="old")):
            with self.subTest(removed=removed), self.assertRaises(TypeError), \
                    patch.object(driver.subprocess, "Popen") as launch:
                driver.run_campaign(root=self.root, run_dir=run, mission_id="mission",
                    model="frozen-model", effort="low", timeout_seconds=60, **removed)
            launch.assert_not_called()
        self.assertEqual(list((run / "preparation").iterdir()), [])

    def test_original_nonzero_never_reads_post_status_or_launches_successor(self):
        report = self.invoke(statuses=[status()], outcomes=[7])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(self.launch_count, 1)
        self.assertEqual(self.client.status.call_count, 1)
        self.client.collect.assert_not_called()
        self.assertEqual(report["hosts"][0]["returncode"], 7)

    def test_initial_guard_refuses_pause_terminal_wrong_mission_and_uncertainty(self):
        cases = [status("paused", pause_cause="user"), status("stopped"), status(mission_id="other"),
            status(active_operation="busy"), status(unresolved_effects=["unknown"]),
            status(clock_valid=False), status(pause_cause="takeover"), status(pause_cause="unknown"),
            status(actor_id="other"), None]
        for initial in cases:
            with self.subTest(initial=initial):
                report = self.invoke(statuses=[initial])
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual(self.launch_count, 0)
                self.client.collect.assert_not_called()

    def test_admitted_initial_allows_unmeasured_game_clock(self):
        initial = status("admitted")
        initial["remaining_limits"]["game_seconds"] = None
        self.assertEqual(self.invoke(statuses=[initial, status("stopped")])["exit_code"], 0)

    def test_post_original_refuses_pause_active_wrong_mission_and_unknown_effects(self):
        cases = [status("paused", pause_cause="user"), status(), status("handoff", mission_id="other"),
            status("handoff", active_operation="busy"), status("handoff", unresolved_effects=["unknown"]),
            status("handoff", clock_valid=False), status("handoff", pause_cause="user"),
            status("handoff", progress={"handoff_id": "guess-from-prose"}),
            status("handoff", progress=None), MissionClientError("Mission response unavailable or invalid")]
        for after in cases:
            with self.subTest(after=after):
                report = self.invoke(statuses=[status(), after])
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual(self.launch_count, 1)
                self.client.collect.assert_not_called()

    def test_exhausted_or_invalid_original_limits_refuse_successor(self):
        for key in driver._LIMITS:
            for value in (0, -1, None, float("nan"), True):
                with self.subTest(key=key, value=value):
                    after = status("handoff")
                    after["remaining_limits"][key] = value
                    report = self.invoke(statuses=[status(), after])
                    self.assertEqual(report["exit_code"], 1)
                    self.assertEqual(self.launch_count, 1)
                    self.client.collect.assert_not_called()

    def test_canonical_issuance_must_match_original_actor_epoch_and_mission(self):
        changes = [{"epoch": 4}, {"mission_id": "wrong"}, {"original_player_id": "wrong"},
            {"pause_origin": "human"}, {"record_type": "ClaimedHandoff"}]
        for change in changes:
            with self.subTest(change=change):
                after = status("handoff", progress={**issuance(), **change})
                report = self.invoke(statuses=[status(), after])
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual(self.launch_count, 1)
                self.client.collect.assert_not_called()

    def test_issued_role_can_equal_original_identity_but_new_actor_is_distinct(self):
        handoff = status("handoff")
        handoff["progress"]["successor_role"] = "original"
        envelope = collection()
        operation = envelope["response"]["operation"]
        operation["request"]["successor_role"] = operation["result"]["successor_role"] = "original"
        report = self.invoke(statuses=[status(), handoff, handoff, status("stopped")], collected=envelope)
        self.assertEqual(report["exit_code"], 0)
        assignment = self.receipt("driver-successor-assignment.json")
        self.assertEqual(assignment["actor_role"], "original")
        self.assertEqual(assignment["actor_id"], "successor-mechanical-uuid")

    def test_expected_frozen_bootstrap_allows_retained_historical_state(self):
        initial = snapshot(status("admitted"), frozen=True)
        initial["state"].update(session="historical-session", revision=99, pause_origin="fault", timestamp_ms=0)
        initial["mission"]["remaining_limits"]["game_seconds"] = None
        self.assertEqual(self.invoke(statuses=[initial, status("stopped")])["exit_code"], 0)
        retained = self.receipt("driver-initial-status.json")
        self.assertEqual(retained["state"], initial["state"])

    def test_bootstrap_user_pause_or_pending_slots_refuse_initial_launch(self):
        for changes in (dict(operator_pause_generation=1), dict(pending={"id": "busy"}),
                        dict(control_pending={"id": "busy"})):
            with self.subTest(changes=changes):
                initial = snapshot(status("admitted"), frozen=True, **changes)
                self.assertEqual(self.invoke(statuses=[initial])["exit_code"], 1)
                self.assertEqual(self.launch_count, 0)

    def test_live_controller_guards_refuse_original_and_successor_launches(self):
        cases = [dict(frozen=True), dict(pending={"id": "busy"}), dict(control_pending={"id": "busy"}),
            dict(operator_pause_generation=None), dict(state=dict(pause_origin="human"))]
        for changes in cases:
            with self.subTest(initial=changes):
                self.assertEqual(self.invoke(statuses=[snapshot(status(), **changes)])["exit_code"], 1)
                self.assertEqual(self.launch_count, 0)
            with self.subTest(successor=changes):
                self.assertEqual(self.invoke(statuses=[status(), status("handoff"),
                    snapshot(status("handoff"), **changes)])["exit_code"], 1)
                self.assertEqual(self.launch_count, 1)

    def test_successor_requires_exact_issued_controller_and_native_pause_binding(self):
        changes = [dict(operator_pause_generation=1), dict(pause_generation=3)]
        for key, value in (("session", "other"), ("revision", 99), ("takeover_generation", 1),
                ("pause_origin", "recovery"), ("paused", False), ("boundary", dict(id="other"))):
            native = snapshot()["state"]
            native[key] = value
            changes.append(dict(state=native))
        for change in changes:
            with self.subTest(change=change):
                report = self.invoke(statuses=[status(), status("handoff"), snapshot(status("handoff"), **change)])
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual(self.launch_count, 1)

    def test_retained_historical_diagnostics_do_not_block_quiescent_handoff(self):
        retained = snapshot(status("handoff"), error="Historical timeout; no current uncertainty",
            unknown_outcomes=[dict(status="unknown", request=dict(id="old-input"))],
            control_unknown_outcomes=[dict(status="unknown", request=dict(id="old-control"), transport_result="rejected")])
        report = self.invoke(statuses=[status(), retained, retained, status("stopped")])
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(self.launch_count, 2)
        self.assertEqual(self.receipt("driver-successor-admission-status.json"), retained)

    def test_collected_issuance_must_be_delivered_settled_completed_and_exact(self):
        for slot, key, value in [("envelope", "transport", "uncertain"), ("envelope", "settled", False),
                ("envelope", "operation_id", "other"), ("operation", "state", "blocked"),
                ("request", "kind", "claim"), ("request", "mission_id", "other"),
                ("request", "request_id", "other"), ("request", "epoch", 99),
                ("request", "successor_role", "other"), ("request", "checkpoint_ids", []),
                ("result", "original_player_id", "wrong"), ("result", "epoch", 4)]:
            with self.subTest(slot=slot, key=key):
                envelope = collection()
                operation = envelope["response"]["operation"]
                target = {"envelope": envelope, "operation": operation,
                    "request": operation["request"], "result": operation["result"]}[slot]
                target[key] = value
                report = self.invoke(statuses=[status(), status("handoff")], collected=envelope)
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual(self.launch_count, 1)

    def test_user_pause_or_changed_handoff_during_collection_prevents_launch(self):
        changed = status("handoff")
        changed["progress"]["handoff_id"] = "new-handoff"
        for latest in (status("paused", pause_cause="user"), changed,
                       status("handoff", active_operation="busy"), status("handoff", epoch=4)):
            with self.subTest(latest=latest):
                report = self.invoke(statuses=[status(), status("handoff"), latest])
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual(self.launch_count, 1)

    def test_successor_nonterminal_never_launches_third_host(self):
        for final in (status(), status("paused", pause_cause="user"), status("handoff")):
            with self.subTest(final=final):
                report = self.invoke(statuses=[status(), status("handoff"), status("handoff"), final])
                self.assertEqual(report["exit_code"], 1)
                self.assertEqual(self.launch_count, 2)
                self.assertEqual(self.client.collect.call_count, 1)

    def test_successor_failure_before_claim_projects_assignment_without_changing_current_actor(self):
        for outcome, state in ((7, "exited"), ("timeout", "timed_out")):
            with self.subTest(outcome=outcome):
                handoff = status("handoff")
                report = self.invoke(statuses=[status(), handoff, handoff], outcomes=[0, outcome])
                self.assertEqual(report["outcome"], "incomplete")
                self.assertEqual(self.client.status.call_count, 3, "failed successor cannot supply a new actor snapshot")
                projection = deciding_host_status(self.root, handoff)
                self.assertEqual(projection["current"]["actor_id"], "original")
                self.assertEqual(projection["successor"]["actor_id"], "successor-mechanical-uuid")
                self.assertEqual(projection["successor"]["state"], state)
                self.assertFalse(projection["successor"]["mission_adoption_observed"])
                self.assertTrue(projection["driver"]["no_continuing_host_reported"])
                self.client.submit.assert_not_called()

    def test_successor_launch_is_projected_before_host_claim_or_exit_receipt(self):
        handoff = status("handoff")
        def before_claim(process):
            projection = deciding_host_status(self.root, handoff)
            self.assertEqual(projection["current"]["actor_id"], "original")
            self.assertEqual(projection["original"]["state"], "exited")
            self.assertEqual(projection["successor"]["state"], "launch_reported")
            self.assertFalse(projection["successor"]["mission_adoption_observed"])
            self.assertFalse(projection["driver"]["no_continuing_host_reported"])
            process.returncode = 7
        report = self.invoke(statuses=[status(), handoff, handoff], outcomes=[0, before_claim])
        self.assertEqual(report["outcome"], "incomplete")
        self.assertEqual(self.launch_count, 2)
        self.client.submit.assert_not_called()

    def test_terminal_status_still_requires_quiescence(self):
        report = self.invoke(statuses=[status(), status("stopped", unresolved_effects=["uncertain"])])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(self.launch_count, 1)

    def test_unresolved_post_host_snapshot_is_retained_with_actual_paused_phase(self):
        paused = status("paused", unresolved_effects=["original-unknown-input"])
        report = self.invoke(statuses=[status(), paused], outcomes=[0])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["phase"], "paused")
        self.assertIn("effects remain unresolved", report["reason"])
        self.assertEqual(self.launch_count, 1)
        self.assertEqual(self.receipt("driver-original-status.json")["mission"], paused)
        self.client.collect.assert_not_called()

    def test_timeout_signals_only_owned_host_and_retains_actual_exit(self):
        report = self.invoke(statuses=[status()], outcomes=["timeout"])
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(self.launch_count, 1)
        self.assertEqual(self.client.status.call_count, 1)
        self.client.collect.assert_not_called()
        self.assertEqual([event for event in self.events if event[0] in ("signal", "terminate", "kill")],
            [("signal", 1234, signal.SIGINT), ("terminate", 1234)])
        receipt = self.receipt("driver-original-receipt.json")
        self.assertTrue(receipt["timed_out"])
        self.assertEqual(receipt["returncode"], -15)
        self.assertEqual(receipt["signals"], ["SIGINT", "SIGTERM"])
        self.assertFalse(receipt["native_cleanup_claimed"])

    def test_original_and_successor_share_one_deadline(self):
        def first(process):
            self.now += 17
            process.returncode = 0
        self.invoke(statuses=[status(), status("handoff"), status("handoff"), status("stopped")], outcomes=[first, 0])
        self.assertEqual([event[1] for event in self.events if event[0] == "communicate"], [60, 43])

    def test_deadline_spent_collecting_never_launches_successor(self):
        def slow_collection():
            self.now += 60
            return collection()
        report = self.invoke(statuses=[status(), status("handoff")], collected=slow_collection)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(self.launch_count, 1)
        self.assertIn("deadline", report["reason"])

    def test_client_caps_sdk_fetch_to_shared_remaining_deadline(self):
        with patch.object(driver.time, "monotonic", return_value=101), \
                patch.object(MissionClient, "_fetch", return_value=b"{}") as fetch:
            client = driver._DeadlineClient(self.root, 104)
            self.assertEqual(client._fetch("/api/status", timeout=6), b"{}")
            fetch.assert_called_once_with("/api/status", timeout=3)
        with patch.object(driver.time, "monotonic", return_value=104), \
                patch.object(MissionClient, "_fetch") as fetch:
            with self.assertRaisesRegex(driver.DriverError, "deadline"):
                client._fetch("/api/status")
            fetch.assert_not_called()

    def test_existing_outputs_refuse_before_launch_and_preserve_evidence(self):
        for name, folder in (("driver-original.jsonl", ""), ("driver-successor-final.txt", ""),
                ("driver-original-receipt.json", "preparation"), ("driver-report.json", "preparation")):
            with self.subTest(name=name):
                run = self.make_run()
                existing = run / folder / name
                existing.write_text("retained evidence")
                with patch.object(driver.subprocess, "Popen") as popen, self.assertRaises(FileExistsError):
                    driver.run_campaign(root=self.root, run_dir=run, mission_id="mission", model="model",
                        effort="low", timeout_seconds=60)
                popen.assert_not_called()
                self.assertEqual(existing.read_text(), "retained evidence")

    def test_invalid_timeout_or_run_location_refuses_before_launch(self):
        run = self.make_run()
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(driver.DriverError):
                driver.run_campaign(root=self.root, run_dir=run, mission_id="mission", model="model",
                    effort="low", timeout_seconds=timeout)
        with self.assertRaises(driver.DriverError):
            driver.run_campaign(root=self.root, run_dir=self.root, mission_id="mission", model="model",
                effort="low", timeout_seconds=60)

    def test_noncanonical_run_refuses_before_reserving_outputs_or_launch(self):
        run = self.make_run()
        for location, mission_id in ((run, "different-mission"), (run / "nested", "mission")):
            location.mkdir(exist_ok=True)
            with self.subTest(location=location), patch.object(driver.subprocess, "Popen") as popen, \
                    self.assertRaisesRegex(driver.DriverError, "mission_id"):
                driver.run_campaign(root=self.root, run_dir=location, mission_id=mission_id,
                    model="model", effort="low", timeout_seconds=60)
            popen.assert_not_called()
            self.assertEqual(list((run / "preparation").iterdir()), [])

    def test_cli_requires_frozen_launch_parameters_and_uses_generic_host(self):
        argv = ["campaign_player", "--root", str(self.root), "--run-dir", "/run", "--mission-id", "mission",
            "--model", "chosen", "--effort", "medium", "--timeout-seconds", "12"]
        with patch("sys.argv", argv), patch.object(driver, "run_campaign", return_value={"exit_code": 0}) as run, \
                patch("builtins.print"), self.assertRaises(SystemExit) as stopped:
            driver.main()
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(run.call_args.kwargs, dict(root=self.root, run_dir=Path("/run"), mission_id="mission",
            model="chosen", effort="medium", timeout_seconds=12, node="node", max_hosts=2))

    def test_cli_rejects_removed_host_and_resume_flags_without_dispatch(self):
        base = ["campaign_player", "--root", str(self.root), "--run-dir", "/run", "--mission-id", "mission",
            "--model", "chosen", "--effort", "medium", "--timeout-seconds", "12"]
        for removed in (["--host", "pi"], ["--host", "codex"], ["--codex", "codex"],
                ["--original-thread", "old-thread"]):
            with self.subTest(removed=removed), patch("sys.argv", base + removed), \
                    patch.object(driver, "run_campaign") as run, patch("sys.stderr", new_callable=io.StringIO), \
                    self.assertRaises(SystemExit) as stopped:
                driver.main()
            self.assertEqual(stopped.exception.code, 2)
            run.assert_not_called()

    def test_cli_requires_model_effort_and_finite_timeout_arguments(self):
        base = ["campaign_player", "--root", str(self.root), "--run-dir", "/run", "--mission-id", "mission",
            "--model", "chosen", "--effort", "medium", "--timeout-seconds", "12"]
        for flag in ("--model", "--effort", "--timeout-seconds"):
            argv = base.copy()
            index = argv.index(flag)
            del argv[index:index + 2]
            with self.subTest(flag=flag), patch("sys.argv", argv), patch.object(driver, "run_campaign") as run, \
                    patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as stopped:
                driver.main()
            self.assertEqual(stopped.exception.code, 2)
            run.assert_not_called()

    def test_cli_forwards_explicit_host_limit(self):
        base = ["campaign_player", "--root", str(self.root), "--run-dir", "/run", "--mission-id", "mission",
            "--model", "chosen", "--effort", "medium", "--timeout-seconds", "12"]
        for max_hosts in (1, 2):
            with self.subTest(max_hosts=max_hosts):
                with patch("sys.argv", base + ["--max-hosts", str(max_hosts)]), \
                        patch.object(driver, "run_campaign", return_value={"exit_code": 0}) as run, \
                        patch("builtins.print"), self.assertRaises(SystemExit) as stopped:
                    driver.main()
                self.assertEqual(stopped.exception.code, 0)
                self.assertEqual(run.call_args.kwargs["max_hosts"], max_hosts)
                self.assertIs(type(run.call_args.kwargs["max_hosts"]), int)

    def test_cli_rejects_invalid_host_limits_without_dispatch(self):
        base = ["campaign_player", "--root", str(self.root), "--run-dir", "/run", "--mission-id", "mission",
            "--model", "chosen", "--effort", "medium", "--timeout-seconds", "12"]
        for max_hosts in ("0", "3", "-1", "1.0", "true"):
            with self.subTest(max_hosts=max_hosts):
                with patch("sys.argv", base + ["--max-hosts", max_hosts]), \
                        patch.object(driver, "run_campaign") as run, patch("sys.stderr", new_callable=io.StringIO), \
                        self.assertRaises(SystemExit) as stopped:
                    driver.main()
                self.assertEqual(stopped.exception.code, 2)
                run.assert_not_called()

    def test_cli_preserves_explicit_node_executable(self):
        argv = ["campaign_player", "--root", str(self.root), "--run-dir", "/run", "--mission-id", "mission",
            "--model", "chosen", "--effort", "medium", "--timeout-seconds", "12", "--node", "/project/node"]
        with patch("sys.argv", argv), patch.object(driver, "run_campaign", return_value={"exit_code": 0}) as run, \
                patch("builtins.print"), self.assertRaises(SystemExit) as stopped:
            driver.main()
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(run.call_args.kwargs["node"], "/project/node")


if __name__ == "__main__":
    unittest.main()
