"""Portable contract tests; all observations and outcomes here are synthetic."""
from dataclasses import FrozenInstanceError, replace
import json
import unittest

from jsonschema import Draft202012Validator

from harness.gameplay.contracts import (
    Budgets, ContractError, EvidencePacket, EvidenceRef, Fact, Interpretation,
    PlanCandidate, PrimitiveResult, Progress, RunStatus, SkillDescriptor,
    StageResult, TaskSpec, record_schema,
)


def evidence(**changes):
    values = dict(observation_id="observation-1", session="synthetic-world", revision=7,
                  timestamp_ms=1_000_000, received_monotonic=10.0, turn=4,
                  frame_path="/synthetic/retained/frame.png", frame_sha256="a" * 64,
                  boundary_kind="normal_play")
    values.update(changes)
    return EvidenceRef(**values)


def task(**changes):
    values = dict(task_id="task-1", session="synthetic-world", origin=(2, 3, 0),
                  direction="north", distance=4, target=(2, -1, 0), task_version=1,
                  budgets=Budgets(), operator_request_id="operator-1")
    values.update(changes)
    return TaskSpec(**values)


def skill():
    return SkillDescriptor("cardinal", 1, ("waypoint_return",), ("outbound", "return"),
                           ("normal_play",), ("UP", "DOWN", "LEFT", "RIGHT"),
                           ("visible_clear_neighbor",), ("cardinal_step",),
                           ("exact_displacement",), ("creature_or_prompt",), Budgets())


def candidate(**changes):
    values = dict(candidate_id="candidate-1", task_id="task-1", task_version=1,
                  plan_id="plan-1", plan_version=2, execution_epoch=3,
                  evidence_session="synthetic-world", evidence_revision=7,
                  stage="outbound", direction="north", distance_remaining=4,
                  skill_id="cardinal", skill_version=1, reason="Clear adjacent terrain")
    values.update(changes)
    return PlanCandidate(**values)


def records():
    ref = evidence()
    after = evidence(observation_id="observation-2", revision=8, turn=5)
    return (
        task(), ref,
        EvidencePacket("task-1", "plan-1", "outbound-1", after, ref, None, "action-1",
                       "returned", (0, -1, 0), None, Budgets(primitives=7),
                       (Fact("position", "[2, 2, 0]", after),),
                       (Interpretation("The route may remain clear", (after,)),)),
        skill(), candidate(),
        PrimitiveResult("action-1", ref, after, "returned", (0, -1, 0), "Observed one step"),
        StageResult("outbound-1", 1, "blocked", Progress(4, (0, -4, 0)), (after,), None),
        RunStatus("task-1", "plan-1", "outbound-1", 3, "planning", None, "fixture",
                  "cardinal", 1, Progress(1, (0, -1, 0)), Budgets(), "Inspect next tile",
                  "Waypoint not yet verified", "supervisor", False, True, (ref, after)),
    )


class ContractTests(unittest.TestCase):
    def test_menu_and_activity_references_cannot_manufacture_normal_scene_time(self):
        for kind in ("menu", "activity_poll", "interrupt_confirmation", "unsupported"):
            with self.subTest(kind=kind):
                ref = evidence(boundary_kind=kind, turn=None)
                self.assertEqual(EvidenceRef.from_dict(ref.to_dict()), ref)
                with self.assertRaises(ContractError): evidence(boundary_kind=kind, turn=4)
        with self.assertRaises(ContractError): evidence(turn=None)

    def test_all_eight_records_round_trip_and_expose_valid_schemas(self):
        self.assertEqual(len(records()), 8)
        for record in records():
            with self.subTest(record=type(record).__name__):
                schema = record_schema(type(record))
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(record.to_dict())
                self.assertEqual(type(record).from_dict(record.to_dict()), record)
                self.assertEqual(type(record).from_dict(json.dumps(record.to_dict())), record)
                self.assertEqual(type(record).from_dict(json.dumps(record.to_dict()).encode()), record)

    def test_every_record_rejects_unknown_missing_and_wrong_version(self):
        for record in records():
            for change in ({"extra": True}, {"schema": "gameplay/1"}, {"schema": "gameplay/3"}, {"record_type": "Code"}):
                with self.subTest(record=type(record).__name__, change=change):
                    value = record.to_dict()
                    value.update(change)
                    with self.assertRaises(ContractError):
                        type(record).from_dict(value)
            value = record.to_dict()
            del value[next(key for key in value if key not in {"schema", "record_type"})]
            with self.assertRaises(ContractError):
                type(record).from_dict(value)

    def test_cardinal_target_relation_for_each_direction(self):
        for direction, target in (("north", (2, -1, 0)), ("south", (2, 7, 0)),
                                  ("east", (6, 3, 0)), ("west", (-2, 3, 0))):
            self.assertEqual(task(direction=direction, target=target).target, target)
            with self.assertRaises(ContractError):
                task(direction=direction, target=(2, 3, 0))
        for distance in (0, 5, True, 1.0):
            with self.subTest(distance=distance), self.assertRaises(ContractError):
                task(distance=distance)

    def test_nested_budget_vector_and_enum_validation(self):
        original = task().to_dict()
        modifications = [
            ("distance", True), ("task_version", 1.0), ("direction", "up"),
            ("kind", "explore"), ("origin", [1, 2]), ("origin", [1, 2, False]),
            ("target", [2, -1, 1]), ("budgets", {**original["budgets"], "unbounded": True}),
            ("budgets", {**original["budgets"], "primitives": 9}),
            ("budgets", {**original["budgets"], "primitive_wait_seconds": 15.1}),
            ("budgets", {**original["budgets"], "planner_calls": True}),
        ]
        for key, value in modifications:
            with self.subTest(key=key, value=value), self.assertRaises(ContractError):
                TaskSpec.from_dict({**original, key: value})

    def test_nonfinite_negative_and_boolean_numbers_reject(self):
        for value in (float("nan"), float("inf"), -float("inf"), -1, True):
            with self.subTest(value=value), self.assertRaises(ContractError):
                evidence(received_monotonic=value)
        for name in ("primitives", "turns", "wall_seconds", "planner_call_seconds", "spend_usd"):
            with self.subTest(name=name), self.assertRaises(ContractError):
                Budgets(**{name: float("nan")})
        for value in (True, 1.0, -1):
            with self.subTest(revision=value), self.assertRaises(ContractError):
                evidence(revision=value)

    def test_strings_arrays_and_json_are_bounded(self):
        with self.assertRaises(ContractError):
            task(task_id="x" * 129)
        with self.assertRaises(ContractError):
            candidate(reason="x" * 1025)
        value = records()[2].to_dict()
        value["facts"] *= 65
        with self.assertRaises(ContractError):
            EvidencePacket.from_dict(value)
        for value in (" " * 1_048_577, b" " * 1_048_577, [], None, "[]", "NaN",
                      '{"schema":"gameplay/2","schema":"gameplay/2"}', '{"a":Infinity}',
                      {"payload": "x" * 1_048_576}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ContractError):
                TaskSpec.from_dict(value)

    def test_frozen_records_contain_no_mutable_nested_inputs(self):
        with self.assertRaises(FrozenInstanceError):
            task().distance = 1
        with self.assertRaises(ContractError):
            task(origin=[2, 3, 0])
        with self.assertRaises(ContractError):
            Interpretation("Unchecked mutable reference", (evidence().to_dict(),))
        value = records()[2]
        serialized = value.to_dict()
        serialized["facts"][0]["evidence"]["revision"] = 999
        self.assertEqual(value.facts[0].evidence.revision, 8)
        schema = record_schema(TaskSpec)
        schema["$defs"]["TaskSpec"]["properties"].clear()
        self.assertEqual(TaskSpec.from_dict(task().to_dict()), task())

    def test_candidate_binds_exact_versions_epoch_evidence_and_skill(self):
        def check(value, **changes):
            arguments = dict(plan_id="plan-1", plan_version=2, execution_epoch=3, skill=skill())
            arguments.update(changes)
            value.check_binding(task(), evidence(), **arguments)
        check(candidate())
        for field, changed in (("task_id", "another-task"), ("task_version", 2),
                               ("plan_id", "plan-2"), ("plan_version", 3),
                               ("execution_epoch", 4), ("evidence_session", "world-2"),
                               ("evidence_revision", 8), ("skill_version", 2), ("skill_id", "other"),
                               ("direction", "south")):
            with self.subTest(field=field), self.assertRaises(ContractError):
                check(candidate(**{field: changed}))
        check(candidate(stage="return", direction="south"))
        with self.assertRaises(ContractError):
            candidate().check_binding(task(distance=1, target=(2, 2, 0)), evidence(),
                                     plan_id="plan-1", plan_version=2, execution_epoch=3, skill=skill())
        value = candidate().to_dict()
        for key in ("code", "tools", "credentials", "frame_path"):
            with self.subTest(key=key), self.assertRaises(ContractError):
                PlanCandidate.from_dict({**value, key: "arbitrary"})

    def test_primitive_vocabulary_preserves_unknown_and_displacement_independence(self):
        before = evidence()
        after = evidence(revision=8)
        for disposition in ("not_dispatched", "dispatched", "returned", "rejected", "unknown"):
            value = PrimitiveResult("action", before, after, disposition, (0, -1, 0), "Transport result")
            self.assertEqual(PrimitiveResult.from_dict(value.to_dict()), value)
        unknown = PrimitiveResult("action", before, None, "unknown", None, "Outcome unobserved")
        self.assertIsNone(unknown.observed_displacement)
        with self.assertRaises(ContractError):
            replace(unknown, transport_disposition="returned")
        with self.assertRaises(ContractError):
            replace(unknown, observed_displacement=(0, 0, 0))
        new_world_context = replace(unknown, after=evidence(session="new-world"))
        self.assertEqual(PrimitiveResult.from_dict(new_world_context.to_dict()), new_world_context)
        with self.assertRaises(ContractError):
            replace(new_world_context, transport_disposition="returned")
        with self.assertRaises(ContractError):
            replace(new_world_context, observed_displacement=(0, 1, 0))

    def test_full_progress_does_not_force_completed_disposition(self):
        for disposition in ("completed", "blocked", "interrupted", "budget_exhausted", "failed", "unknown"):
            value = StageResult("stage", 1, disposition, Progress(4, (0, -4, 0)), (evidence(),), None)
            self.assertEqual(StageResult.from_dict(value.to_dict()).disposition, disposition)
        with self.assertRaises(ContractError):
            StageResult("stage", 1, "completed", Progress(4, (0, -4, 0)), (evidence(),), "pending")
        with self.assertRaises(ContractError):
            StageResult("stage", 1, "completed", Progress(0, (0, 0, 0)), (), None)

    def test_packet_separates_fact_and_interpretation_and_retains_world_identity(self):
        value = records()[2]
        with self.assertRaises(ContractError):
            replace(value, start=evidence(session="old-world"))
        with self.assertRaises(ContractError):
            replace(value, last_primitive_id=None)
        serialized = value.to_dict()
        serialized["facts"][0]["tag"] = "interpretation"
        with self.assertRaises(ContractError):
            EvidencePacket.from_dict(serialized)
        serialized = value.to_dict()
        serialized["interpretations"][0]["tag"] = "fact"
        with self.assertRaises(ContractError):
            EvidencePacket.from_dict(serialized)


if __name__ == "__main__":
    unittest.main()
