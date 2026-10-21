"""Synthetic seven-day boundary observations through real mission budgeting.

No native time advance or seven-day survival is established by these fixtures.
"""
from dataclasses import replace
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_contracts import MissionAdmission, MissionLimits
from tests.test_mission_creation import MissionCreationFixture


class CampaignBudgetTests(MissionCreationFixture, unittest.TestCase):
    def observe_elapsed(self, elapsed):
        self.a = replace(self.a, limits=replace(self.a.limits, game_seconds=691_200))
        self.create()
        current = self.runtime._current
        self.turn = current.turn + elapsed
        self.bridge.value["revision"] += 1
        self.normal(current.session)
        self.observe("elapsed-campaign-time")
        return self.runtime.status()

    def assert_no_save_input(self, *, prepared_charge=0):
        request = self.lifecycle("exhausted-save", "save")
        before = self.runtime.status()["spent_inputs"]
        delivered = list(self.bridge.delivered)
        response = self.runtime.command(request)
        if response["status"] == "accepted":
            self.assertIn(self.settled(request["request_id"])["state"], ("blocked", "paused", "cancelled"))
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(self.runtime.status()["spent_inputs"], before + prepared_charge)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._lease)

    def test_finite_eight_day_ceiling_roundtrips_and_rejects_larger_values(self):
        admission = replace(self.a, limits=MissionLimits(game_seconds=691_200))
        self.assertEqual(MissionAdmission.from_dict(admission.to_dict()), admission)
        with self.assertRaises(ContractError):
            MissionLimits(game_seconds=691_201)
        value = admission.to_dict()
        value["limits"]["game_seconds"] = 691_201
        with self.assertRaises(ContractError):
            MissionAdmission.from_dict(value)
        self.assertEqual(self.a.limits.game_seconds, 43_200)

    def test_seven_day_target_has_room_for_normal_save_and_exit(self):
        status = self.observe_elapsed(604_800)
        self.assertEqual(status["metrics"]["game_seconds"], 604_800)
        self.assertEqual(status["phase"], "active")
        self.assertEqual(self.save()["state"], "completed")
        self.assertEqual(self.exit()["state"], "completed")
        self.assertEqual(self.runtime._admission.limits.game_seconds, 691_200)

    def test_just_below_selected_cap_allows_normal_closeout(self):
        status = self.observe_elapsed(691_199)
        self.assertEqual(status["metrics"]["game_seconds"], 691_199)
        self.assertEqual(self.save()["state"], "completed")
        self.assertEqual(self.exit()["state"], "completed")

    def test_exact_selected_cap_still_blocks_save_input(self):
        self.observe_elapsed(691_200)
        self.assert_no_save_input()
        self.assertEqual(self.runtime._admission.limits.game_seconds, 691_200)

    def test_over_selected_cap_never_grants_cleanup_exemption(self):
        self.observe_elapsed(691_201)
        self.assert_no_save_input()
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual(self.runtime._admission.limits.game_seconds, 691_200)

    def test_cap_reached_during_preflight_settles_before_revoking(self):
        self.observe_elapsed(691_199)
        prepare = self.runtime._ledger.prepare_primitive
        def exhaust_after_prepare(*args, **kwargs):
            result = prepare(*args, **kwargs)
            self.runtime._game_cost = 691_200
            return result
        with patch.object(self.runtime._ledger, "prepare_primitive", side_effect=exhaust_after_prepare):
            # Preparation is charged conservatively; known nondelivery does
            # not refund an admitted primitive under the existing contract.
            self.assert_no_save_input(prepared_charge=1)
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "not_dispatched")
        self.assertFalse(primitive["result"]["published"])
