"""Finite software idle waiting, with no native/game or inference process."""
import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import anyio

from harness.gameplay.contracts import ContractError
from harness.player_mcp import call_player, make_server
from tools.configure_player_tools import configuration


class AdviserWaitTests(unittest.TestCase):
    def exercise(self, outcomes, *, window=100., remaining=65., name="enactive_reflect_next", cancel=False):
        clock, calls, reads = [100.], [], []
        def status():
            reads.append(True)
            return dict(mission=dict(mission_id="mission-a", deadline=1000. + remaining))
        def call(tool, arguments, **options):
            calls.append((tool, deepcopy(arguments), options))
            outcome = outcomes.pop(0)
            if outcome == "idle":
                clock[0] += arguments["wait_seconds"]
            return dict(status=outcome, grants_authority=False), None
        player = SimpleNamespace(client=SimpleNamespace(status=status), call=call)
        arguments = dict(mission_id="mission-a", reflector_id="reflector-a", wait_seconds=40.)
        async def run():
            with patch("harness.player_mcp.time.time", return_value=1000.), \
                    patch("harness.player_mcp.time.monotonic", side_effect=lambda: clock[0]), \
                    patch("harness.player_mcp.anyio.sleep", new_callable=AsyncMock):
                if cancel:
                    with patch("harness.player_mcp.anyio.lowlevel.checkpoint", AsyncMock(side_effect=asyncio.CancelledError)):
                        return await call_player(player, name, arguments, advisory_idle_seconds=window)
                return await call_player(player, name, arguments, advisory_idle_seconds=window)
        result = anyio.run(run)
        return result, calls, reads

    def test_empty_queue_does_not_return_to_model_before_original_deadline(self):
        result, calls, reads = self.exercise(["idle", "idle"])
        self.assertEqual(result[0]["status"], "idle")
        self.assertEqual([entry[1]["wait_seconds"] for entry in calls], [40., 25.])
        self.assertEqual(len(reads), 1)
        self.assertTrue(all(entry[2] == dict(present_image=False) for entry in calls))

    def test_frozen_window_can_shorten_but_never_extend_original_deadline(self):
        _, calls, _ = self.exercise(["idle"], window=10., remaining=100.)
        self.assertEqual(calls[0][1]["wait_seconds"], 10.)
        _, calls, _ = self.exercise(["idle"], remaining=-1.)
        self.assertEqual(calls[0][1]["wait_seconds"], 0.)

    def test_only_idle_is_repeated_and_claim_receipt_is_returned_immediately(self):
        for outcome in ("claimed", "closed", "pending", "busy", "unknown", "rejected"):
            with self.subTest(outcome=outcome):
                result, calls, reads = self.exercise(["idle", outcome])
                self.assertEqual(result[0], dict(status=outcome, grants_authority=False))
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(reads), 1)

    def test_default_player_and_other_tools_never_enter_adviser_wait_loop(self):
        for name, window in (("enactive_reflect_next", 0), ("enactive_skill", 100)):
            result, calls, reads = self.exercise(["idle"], name=name, window=window)
            self.assertEqual(result[0]["status"], "idle")
            self.assertEqual(len(calls), 1)
            self.assertEqual(reads, [])

    def test_cancellation_after_passive_poll_prevents_another_poll(self):
        with self.assertRaises(asyncio.CancelledError):
            self.exercise(["idle"], cancel=True)

    def test_wrong_mission_never_polls(self):
        player = SimpleNamespace(client=SimpleNamespace(status=lambda: dict(mission=dict(mission_id="other"))))
        with self.assertRaisesRegex(ContractError, "original admitted"):
            anyio.run(lambda: call_player(player, "enactive_reflect_next", dict(mission_id="mission-a"), advisory_idle_seconds=5))

    def test_profile_export_is_finite_role_scoped_and_default_is_unchanged(self):
        default = configuration(Path("/project"))
        selected = configuration(Path("/project"), advisory_idle_seconds=300.)
        self.assertEqual(default["tool_timeout_sec"], 60)
        self.assertEqual(default["args"], ["-m", "harness.player_mcp"])
        self.assertEqual(selected["tool_timeout_sec"], 330.)
        self.assertEqual(selected["args"][-2:], ["--advisory-idle-seconds", "300.0"])
        self.assertEqual(set(selected["enabled_tools"]), {"enactive_reflect_next", "enactive_reflect_submit",
            "enactive_reflect_source", "enactive_reflect_result"})
        for invalid in (-1, True, float("inf"), float("nan")):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError): configuration(Path("/project"), advisory_idle_seconds=invalid)
                with self.assertRaises(ValueError): make_server(SimpleNamespace(), advisory_idle_seconds=invalid)


if __name__ == "__main__":
    unittest.main()
