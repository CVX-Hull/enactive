"""Synthetic strict contract fixtures, never native gameplay evidence."""
from dataclasses import FrozenInstanceError, replace
import json
import unittest

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_contracts import (
    CleanupReserve, Configuration, MissionAdmission, MissionLimits, Scenario,
    MAX_REQUEST_BYTES, validate_memory_entry, validate_request, validate_visible_ui,
)


def admission(**changes):
    fields = dict(mission_id="mission-test", objective="Supplies and shelter",
                  player_id="player-test", scenario=Scenario("fresh", "test-world", "test-person"),
                  limits=MissionLimits(), cleanup_reserve=CleanupReserve(),
                  allowed_skills=("navigate", "item", "activity", "inspect", "menu"),
                  allowed_lifecycle=("launch", "create", "save", "exit", "load", "finish"),
                  update_policy="facts-and-provisional/1",
                  configuration=Configuration("a" * 40, "b" * 64, "skills-1", "none", "unreported", "unreported"))
    fields.update(changes)
    return MissionAdmission(**fields)


def scope():
    return {"mission_id": "mission-test", "session": "native-session", "coordinate_epoch": 0}


def claim(**changes):
    fields = dict(schema="campaign-memory/1", record_type="Claim", id="claim-1", kind="interpretation",
                  key={"subject": "water", "property": "supply", "unit": "charges", "coverage_id": "page-1"},
                  value={"quantity": 18, "state": None}, text="Visible clean water count",
                  scope=scope(), observed_time={"revision": 30, "turn": None}, received_time=100_000,
                  coverage="consume menu page", sources=["source-1"],
                  supports=[{"sources": ["source-1"], "claims": []}], status="last_seen", supersedes=[])
    fields.update(changes)
    return fields


def request(kind="observe", **changes):
    fields = dict(schema="mission/1", kind=kind, request_id="request-1", mission_id="mission-test", epoch=0)
    fields.update(changes)
    return fields


def skill(**changes):
    value = request("skill", skill_kind="navigate", goal={"scope": scope(), "target": [2, -3, 0]},
                    sources=["source-1"], expected_session="native-session", expected_revision=30,
                    expected_boundary_id="boundary-1", limits={"primitives": 32, "wall_seconds": 120.0, "game_seconds": 1200})
    value.update(changes)
    return value


class MissionContractTests(unittest.TestCase):
    def test_admission_roundtrip_is_typed_and_immutable(self):
        original = admission()
        for value in [original.to_dict(), json.dumps(original.to_dict()), json.dumps(original.to_dict()).encode()]:
            self.assertEqual(MissionAdmission.from_dict(value), original)
        with self.assertRaises(FrozenInstanceError): original.player_id = "other"
        with self.assertRaises(ContractError): admission(allowed_skills=["navigate"])
        with self.assertRaises(ContractError): admission(limits=admission().limits.__dict__)

    def test_admission_reserve_and_unsupported_capabilities_reject(self):
        for changes in [dict(allowed_skills=("combat",)), dict(allowed_skills=("navigate", "navigate")),
                        dict(allowed_lifecycle=("shell",)), dict(mission_id="../outside"),
                        dict(update_policy="learn-new-code"), dict(cleanup_reserve=CleanupReserve(inputs=1500))]:
            with self.subTest(changes=changes), self.assertRaises(ContractError): admission(**changes)
        for cls, changes in [(MissionLimits, {"wall_seconds": 0}), (MissionLimits, {"inputs": True}),
                             (MissionLimits, {"inputs": 2.0}), (MissionLimits, {"frames": 4097}),
                             (MissionLimits, {"primitive_mappings": 1}),
                             (CleanupReserve, {"inputs": 0}), (CleanupReserve, {"frames": 0})]:
            with self.subTest(changes=changes), self.assertRaises(ContractError): cls(**changes)
        with self.assertRaises(ContractError): replace(admission(), allowed_lifecycle=("kill",))

    def test_untrusted_admission_no_extra_version_or_nested_number_coercion(self):
        for change in [{"schema": "mission/0"}, {"record_type": "Code"}, {"extra": True}]:
            with self.assertRaises(ContractError): MissionAdmission.from_dict({**admission().to_dict(), **change})
        value = admission().to_dict(); value["limits"]["inputs"] = 1500.0
        with self.assertRaises(ContractError): MissionAdmission.from_dict(value)
        for value in [float("nan"), float("inf"), True]:
            with self.assertRaises(ContractError): MissionLimits(wall_seconds=value)

    def test_closed_requests_and_scope_binding(self):
        valid = [request(), {"schema": "mission/1", "kind": "start", "request_id": "start-1", "admission": admission().to_dict()},
                 {"schema": "mission/1", "kind": "status", "mission_id": "mission-test"},
                 {"schema": "mission/1", "kind": "result", "mission_id": "mission-test", "operation_id": "old-1"},
                 {"schema": "mission/1", "kind": "context", "mission_id": "mission-test", "query": "water", "scope": scope(), "max_bytes": 32768},
                 skill(), request("stop", reason="Objective verified", finish=True)]
        for value in valid:
            with self.subTest(kind=value["kind"]): self.assertEqual(validate_request(value), value)
        for value in [request("exec", code="print(1)"), request(extra=True), request(epoch=1.0), skill(skill_kind=[]),
                      request("remember", entry_type={}, entry={}), {**valid[4], "mission_id": "wrong"}]:
            with self.subTest(value=value), self.assertRaises(ContractError): validate_request(value)

    def test_navigation_and_skill_limits_cannot_borrow_other_scope(self):
        for changes in [dict(expected_session="other"), dict(sources=[]),
                        dict(goal={"scope": {**scope(), "mission_id": "other"}, "target": [2, -3, 0]}),
                        dict(limits={"primitives": 33, "wall_seconds": 1, "game_seconds": 1}),
                        dict(goal={"scope": scope(), "target": [True, -3, 0]})]:
            with self.assertRaises(ContractError): validate_request(skill(**changes))
        current = skill(); current["goal"]["target"][0] = 1.0
        with self.assertRaises(ContractError): validate_request(current)

    def test_every_skill_has_a_closed_typed_goal(self):
        goals = {"menu": {"purpose": "alarm", "label": "8 hours", "quantity": 1, "outcome": "selected"},
                 "item": {"purpose": "consume", "label": "clean water", "quantity": 1, "outcome": "consumed"},
                 "activity": {"operation": "rest", "target": "bench", "game_seconds": 1800, "interrupt": True},
                 "inspect": {"purpose": "inventory"}}
        for name, goal in goals.items():
            self.assertEqual(validate_request(skill(skill_kind=name, goal=goal, limits={"primitives": 32, "wall_seconds": 120, "game_seconds": 1800}))["goal"], goal)
            with self.assertRaises(ContractError): validate_request(skill(skill_kind=name, goal={**goal, "hidden": 1}))

    def test_lifecycle_launch_has_no_old_authority_other_operations_require_binding(self):
        launch = request("lifecycle", operation="launch", world="world", character="person", sources=[],
                         expected_session=None, expected_revision=None, expected_boundary_id=None,
                         limits={"primitives": 1, "wall_seconds": 120, "game_seconds": 1})
        self.assertEqual(validate_request(launch), launch)
        with self.assertRaises(ContractError): validate_request({**launch, "expected_session": "old"})
        with self.assertRaises(ContractError): validate_request({**launch, "operation": "create"})
        create = {**launch, "operation": "create", "expected_session": "menu", "expected_revision": 3, "expected_boundary_id": "boundary"}
        self.assertEqual(validate_request(create), create)
        with self.assertRaises(ContractError): validate_request({**create, "pid": 42})

    def test_player_cannot_forge_native_fact_or_cross_mission_memory(self):
        native = claim(kind="native_fact")
        self.assertEqual(validate_memory_entry(native, "claim"), native)
        with self.assertRaises(ContractError): validate_request(request("remember", entry_type="claim", entry=native))
        self.assertEqual(validate_request(request("remember", entry_type="claim", entry=claim()))["entry"], claim())
        with self.assertRaises(ContractError): validate_request(request("remember", entry_type="claim", entry=claim(scope={**scope(), "mission_id": "elsewhere"})))
        for changes in [dict(value={"quantity": 18, "state": "full"}), dict(supports=[{"sources": [], "claims": []}]),
                        dict(supports=[{"sources": [], "claims": ["claim-1"]}]),
                        dict(supports=[{"sources": ["other"], "claims": []}])]:
            with self.assertRaises(ContractError): validate_memory_entry(claim(**changes), "claim")
        self.assertEqual(validate_memory_entry(claim(value={"quantity": None, "state": None}, status="unknown"), "claim")["status"], "unknown")

    def test_correction_requires_new_claim_identity(self):
        value = request("correct", entry_type="claim", entry=claim(id="correction-1"), retired_ids=["claim-1"], reason="Misread number")
        self.assertEqual(validate_request(value), value)
        with self.assertRaises(ContractError): validate_request({**value, "entry": claim()})

    def test_rendered_ui_rejects_hidden_fields_and_nonvisible_selection(self):
        ui = {"purpose": "UILIST", "title": "Choose", "rows": [{"id": "row-1", "text": "Eight hours", "enabled": True, "hotkey": "8"}],
              "selected": "row-1", "filter": None, "count": None, "coverage": "rendered_rows_only"}
        self.assertIsNone(validate_visible_ui(None))
        self.assertEqual(validate_visible_ui(ui), ui)
        for bad in [{**ui, "hidden_inventory": []}, {**ui, "selected": "off-page"},
                    {**ui, "rows": ui["rows"] * 2}, {**ui, "rows": [{**ui["rows"][0], "engine_item_id": 1}]}]:
            with self.assertRaises(ContractError): validate_visible_ui(bad)

    def test_duplicate_nonfinite_oversized_and_mutable_alias_inputs_reject(self):
        for value in ['{"schema":"mission/1","kind":"observe","kind":"stop"}',
                      '{"schema":"mission/1","kind":"observe","epoch":NaN}',
                      ' ' * MAX_REQUEST_BYTES + json.dumps(request())]:
            with self.assertRaises(ContractError): validate_request(value)
        original = skill(); parsed = validate_request(original)
        original["goal"]["target"][0] = 99
        self.assertEqual(parsed["goal"]["target"][0], 2)


if __name__ == "__main__": unittest.main()
