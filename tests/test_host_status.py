"""Passive campaign-host evidence; fixtures never launch or inspect processes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness.host_status import deciding_host_status


class HostStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.preparation = self.root / ".runtime/campaigns/mission/preparation"
        self.preparation.mkdir(parents=True)
        self.mission = dict(mission_id="mission", actor_id="original", phase="active")

    def write(self, name, value):
        (self.preparation / f"driver-{name}.json").write_text(json.dumps(value))

    def initial(self, **changes):
        self.write("initial-status", dict(mission={**self.mission, **changes}))

    def host(self, role="original", *, receipt=True, **changes):
        self.write(f"{role}-process", dict(start=100, pid=123, argv=["secret", "/private/path"]))
        value = dict(start=100, end=120, returncode=0, timed_out=False, interrupted=False,
            signals=[], native_cleanup_claimed=False)
        value.update(changes)
        if receipt:
            self.write(f"{role}-receipt", value)
        return dict(role=role, **value)

    def projection(self):
        result = deciding_host_status(self.root, self.mission)
        self.assertFalse(result["grants_authority"])
        self.assertNotRegex(json.dumps(result), "secret|private/path|pid|argv")
        return result

    def test_absent_empty_malformed_unreadable_and_oversized_are_unknown(self):
        for content in (None, "", "{", "[]", "x" * 1_048_577):
            with self.subTest(content=str(content)[:10]):
                if content is not None:
                    (self.preparation / "driver-initial-status.json").write_text(content)
                self.assertEqual(self.projection()["current"]["state"], "unreported")
        with patch.object(Path, "open", side_effect=PermissionError):
            self.assertEqual(self.projection()["current"]["state"], "unreported")

    def test_mission_and_actor_bindings_do_not_borrow_other_receipts(self):
        self.host()
        for changes in (dict(mission_id="other"), dict(actor_id="other")):
            self.initial(**changes)
            self.assertEqual(self.projection()["current"]["state"], "unreported")
        self.initial()
        self.write("successor-assignment", dict(mission_id="other", actor_id="successor"))
        self.host("successor")
        self.mission["actor_id"] = "successor"
        self.assertEqual(self.projection()["current"]["state"], "unreported")
        self.assertIsNone(self.projection()["successor"])
        self.write("successor-assignment", dict(mission_id="mission", actor_id="wrong"))
        self.assertEqual(self.projection()["current"]["state"], "unreported")

    def test_original_exit_during_handoff_does_not_end_driver_or_future_host(self):
        self.initial()
        self.host()
        self.mission["phase"] = "handoff"
        result = self.projection()
        self.assertEqual(result["current"]["state"], "exited")
        self.assertEqual(result["driver"]["outcome"], "unreported")
        self.assertFalse(result["driver"]["no_continuing_host_reported"])
        self.mission["actor_id"] = "successor"
        result = self.projection()
        self.assertEqual(result["current"]["state"], "unreported")
        self.assertEqual(result["original"]["state"], "exited")

    def test_successor_launch_is_not_current_liveness_and_exit_is_actor_bound(self):
        self.initial()
        self.host()
        self.write("successor-assignment", dict(mission_id="mission", actor_id="successor"))
        self.host("successor", receipt=False)
        self.mission["actor_id"] = "successor"
        result = self.projection()
        self.assertEqual(result["current"]["state"], "launch_reported")
        self.assertEqual(result["current"]["role"], "successor")
        self.assertTrue(result["successor"]["mission_adoption_observed"])
        for changes, state in (({}, "exited"), (dict(timed_out=True), "timed_out"),
                (dict(interrupted=True), "interrupted")):
            self.host("successor", **changes)
            self.assertEqual(self.projection()["current"]["state"], state)

    def test_assigned_successor_launch_is_visible_before_mission_actor_adoption(self):
        self.initial()
        self.host()
        self.mission["phase"] = "handoff"
        self.write("successor-assignment", dict(mission_id="mission", actor_id="successor"))
        self.host("successor", receipt=False)
        result = self.projection()
        self.assertEqual(result["current"], result["original"])
        self.assertEqual(result["current"]["actor_id"], "original")
        self.assertEqual(result["successor"]["state"], "launch_reported")
        self.assertEqual(result["successor"]["actor_id"], "successor")
        self.assertFalse(result["successor"]["mission_adoption_observed"])
        self.assertFalse(result["driver"]["no_continuing_host_reported"])

    def test_successor_failure_before_adoption_keeps_continuation_unknown_until_final_report(self):
        self.initial()
        original = self.host()
        self.mission["phase"] = "handoff"
        self.write("successor-assignment", dict(mission_id="mission", actor_id="successor"))
        for changes, state in ((dict(returncode=7), "exited"),
                (dict(returncode=-15, timed_out=True), "timed_out"),
                (dict(returncode=None, timed_out=True, host_exit_unresolved=True), "exit_unresolved")):
            with self.subTest(state=state):
                successor = self.host("successor", **changes)
                self.write("report", {})
                result = self.projection()
                self.assertEqual(result["current"]["actor_id"], "original")
                self.assertEqual(result["successor"]["state"], state)
                self.assertFalse(result["successor"]["mission_adoption_observed"])
                self.assertFalse(result["driver"]["no_continuing_host_reported"])
                self.write("report", dict(mission_id="mission", outcome="incomplete", exit_code=1,
                    hosts=[original, successor]))
                self.assertEqual(self.projection()["driver"]["no_continuing_host_reported"],
                    state != "exit_unresolved")

    def test_precreated_and_invalid_terminal_receipts_never_prove_exit(self):
        self.initial()
        self.host(receipt=False)
        for content in ("", "{", "{}", 'true'):
            (self.preparation / "driver-original-receipt.json").write_text(content)
            result = self.projection()
            self.assertEqual(result["current"]["state"], "launch_reported")
            self.assertFalse(result["driver"]["no_continuing_host_reported"])
        self.host(start=99)
        self.assertEqual(self.projection()["current"]["state"], "unreported")

    def test_final_incomplete_requires_all_host_exits_and_matching_report(self):
        self.initial()
        original = self.host()
        report = dict(mission_id="mission", outcome="incomplete", exit_code=1, hosts=[original])
        self.write("report", report)
        result = self.projection()
        self.assertEqual(result["driver"], dict(outcome="incomplete", no_continuing_host_reported=True))
        self.write("successor-assignment", dict(mission_id="mission", actor_id="successor"))
        self.host("successor", receipt=False)
        self.assertFalse(self.projection()["driver"]["no_continuing_host_reported"])
        successor = self.host("successor")
        self.write("report", dict(report, hosts=[original, successor]))
        self.assertTrue(self.projection()["driver"]["no_continuing_host_reported"])
        for changes in (dict(mission_id="other"), dict(hosts=[dict(original, returncode=9)])):
            self.write("report", dict(report, **changes))
            self.assertFalse(self.projection()["driver"]["no_continuing_host_reported"])

    def test_corrupt_unbound_successor_evidence_cannot_prove_no_continuing_host(self):
        self.initial()
        original = self.host()
        self.write("report", dict(mission_id="mission", outcome="incomplete", exit_code=1, hosts=[original]))
        (self.preparation / "driver-successor-process.json").write_text("{")
        self.assertFalse(self.projection()["driver"]["no_continuing_host_reported"])

    def test_unresolved_exit_stays_unknown_even_when_driver_ended(self):
        self.initial()
        host = self.host(returncode=None, timed_out=True, host_exit_unresolved=True)
        self.write("report", dict(mission_id="mission", outcome="incomplete", exit_code=1, hosts=[host]))
        result = self.projection()
        self.assertEqual(result["current"]["state"], "exit_unresolved")
        self.assertFalse(result["driver"]["no_continuing_host_reported"])

    def test_malformed_narrow_fields_cannot_break_status_or_prove_exit(self):
        self.initial()
        for change in (dict(start=10 ** 1000), dict(start=True), dict(end=float("inf")),
                dict(end=99), dict(returncode=True), dict(timed_out="true"), dict(host_exit_unresolved=[])):
            with self.subTest(change=change):
                self.host(**change)
                self.assertNotIn(self.projection()["current"]["state"], ("exited", "timed_out", "interrupted"))
        original = self.host()
        for change in (dict(role=[]), dict(role={}), dict(role="unknown")):
            with self.subTest(change=change):
                self.write("report", dict(mission_id="mission", outcome="incomplete", exit_code=1,
                    hosts=[{**original, **change}]))
                self.assertFalse(self.projection()["driver"]["no_continuing_host_reported"])

    def test_unsafe_mission_identity_does_not_select_a_path(self):
        self.mission["mission_id"] = "../../outside"
        with patch.object(Path, "open") as opened:
            self.assertEqual(self.projection()["current"]["state"], "unreported")
            opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
