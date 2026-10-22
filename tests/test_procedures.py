"""Pure procedure shape/ancestry tests; sources and truth require integration."""
from copy import deepcopy
import json
import unittest

from jsonschema import Draft202012Validator

from harness.gameplay.contracts import ContractError
from harness.gameplay.contracts import canonical
from harness.gameplay.procedures import (
    procedure_schema, project_procedures, validate_procedure,
)


def procedure(**changes):
    return {
        "schema": "procedure/2", "record_type": "Procedure", "id": "rev-1",
        "mission_id": "mission-a", "procedure_id": "collect-water", "revision": 1,
        "parent": None, "goal": "Collect usable water",
        "parameters": [{"name": "container", "description": "A suitable container"}],
        "applicability": ["A source is visibly available"],
        "invalidators": ["The source becomes inaccessible"],
        "steps": [{"intent": "Inspect the source", "expected": "Usable water is shown",
                   "on_unexpected": "Stop and reassess"}],
        "progress": ["Water is visibly carried"], "stop_conditions": ["Target met"],
        "limits": ["Not assessed with hostile creatures nearby"],
        "environment": {"engine_commit": "a" * 40, "native_protocol": 6,
                        "mission_schema": "mission/10", "configuration": "Ordinary setup"},
        "support": [{"mission_id": "episode-mission", "request_ids": ["request-1"],
                     "source_ids": ["source-1"], "interpretation": "One observed attempt"}],
        "counterexamples": [], "status": "candidate", "reason": "Scoped advisory candidate",
        **changes,
    }


def successor(parent, **changes):
    return procedure(**{
        "id": f"rev-{parent['revision'] + 1}", "mission_id": parent["mission_id"],
        "procedure_id": parent["procedure_id"], "revision": parent["revision"] + 1,
        "parent": {"mission_id": parent["mission_id"], "revision_id": parent["id"]},
        **changes,
    })


class ProcedureValidationTests(unittest.TestCase):
    def test_schema_is_closed_valid_and_defensively_copied(self):
        schema = procedure_schema()
        Draft202012Validator.check_schema(schema)
        self.assertFalse(schema["additionalProperties"])
        schema["properties"]["environment"]["properties"]["native_protocol"] = {}
        schema["required"].clear()
        with self.assertRaises(ContractError):
            validate_procedure(procedure(environment={**procedure()["environment"], "native_protocol": 4}))
        self.assertTrue(procedure_schema()["required"])

    def test_decoded_inputs_and_nested_outputs_are_independent(self):
        original = procedure()
        expected = deepcopy(original)
        for value in (original, json.dumps(original), json.dumps(original).encode()):
            decoded = validate_procedure(value)
            self.assertEqual(decoded, expected)
            decoded["steps"][0]["intent"] = "Mutated"
            decoded["support"][0]["request_ids"].append("mutated")
        self.assertEqual(original, expected)

    def test_every_field_is_required_and_unknown_fields_are_rejected(self):
        for field in procedure():
            with self.subTest(field=field):
                value = procedure()
                del value[field]
                with self.assertRaises(ContractError):
                    validate_procedure(value)
        for path in ((), ("environment",), ("steps", 0), ("parameters", 0), ("support", 0)):
            with self.subTest(path=path):
                value = procedure()
                target = value
                for key in path:
                    target = target[key]
                target["inventory"] = "current-world fact"
                with self.assertRaises(ContractError):
                    validate_procedure(value)

    def test_rejects_malformed_json_and_non_objects(self):
        encoded = json.dumps(procedure())
        for value in ([], None, True, 4, b"\xff", '{"id":"one","id":"two"}',
                      encoded.replace('"revision": 1', '"revision": NaN'),
                      encoded.replace('"revision": 1', '"revision": Infinity')):
            with self.subTest(value=str(value)[:80]):
                with self.assertRaises(ContractError):
                    validate_procedure(value)

    def test_strict_versions_status_and_integer_bounds(self):
        for field, values in {
            "schema": ["procedure/0", "procedure/1", "procedure/3"], "record_type": ["Claim"],
            "revision": [True, False, 1.0, 0, -1, 1025], "status": ["verified", ""],
        }.items():
            for invalid in values:
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaises(ContractError):
                        validate_procedure(procedure(**{field: invalid}))
        for revision in (1, 1024):
            self.assertEqual(validate_procedure(procedure(revision=revision))["revision"], revision)
        for status in ("candidate", "active", "disputed", "retired"):
            self.assertEqual(validate_procedure(procedure(status=status))["status"], status)
        for field, invalid in (("native_protocol", True), ("native_protocol", 5.0),
                               ("native_protocol", 4), ("native_protocol", 5), ("mission_schema", "mission/8"),
                               ("engine_commit", "a" * 39), ("engine_commit", "A" * 40),
                               ("engine_commit", "g" * 40)):
            with self.subTest(field=field, invalid=invalid):
                with self.assertRaises(ContractError):
                    validate_procedure(procedure(environment={**procedure()["environment"], field: invalid}))

    def test_ids_have_bounded_ascii_shape_at_every_boundary(self):
        for invalid in ("", "a" * 129, "_leading", "-leading", "é", "a b", "a/b", "a\n"):
            for path in (("id",), ("mission_id",), ("procedure_id",), ("parameters", 0, "name"),
                         ("support", 0, "mission_id"), ("support", 0, "request_ids", 0),
                         ("support", 0, "source_ids", 0), ("parent", "revision_id")):
                with self.subTest(path=path, invalid=invalid):
                    value = procedure(parent={"mission_id": "m", "revision_id": "r"})
                    target = value
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = invalid
                    with self.assertRaises(ContractError):
                        validate_procedure(value)
        self.assertEqual(validate_procedure(procedure(id="A" + "_-0" * 42 + "z"))["id"],
                         "A" + "_-0" * 42 + "z")

    def test_text_character_and_canonical_byte_limits_are_distinct(self):
        for field in ("goal", "reason"):
            self.assertEqual(validate_procedure(procedure(**{field: "水" * 1024}))[field], "水" * 1024)
            for invalid in ("", "a" * 1025, "\ud800"):
                with self.subTest(field=field, invalid_length=len(invalid)):
                    with self.assertRaises(ContractError):
                        validate_procedure(procedure(**{field: invalid}))
        value = procedure(steps=[{"intent": "水" * 1024, "expected": "水" * 1024,
                                 "on_unexpected": "水" * 1024}] * 4)
        self.assertGreater(len(canonical(value).encode()), 32768)
        with self.assertRaises(ContractError):
            validate_procedure(value)
        # The limit applies to canonical bytes, not serialization whitespace.
        self.assertEqual(validate_procedure(" " * 32768 + json.dumps(procedure())), procedure())
        # Exercise the exact byte boundary with otherwise valid bounded fields.
        value = procedure(steps=[{"intent": "x" * 1024, "expected": "x" * 1024,
                                 "on_unexpected": "x" * 1024} for _ in range(10)])
        size = len(canonical(value).encode())
        value["goal"] = "x" * (32768 - size + len(value["goal"]))
        self.assertEqual(len(canonical(value).encode()), 32768)
        self.assertEqual(validate_procedure(value), value)
        value["goal"] += "x"
        with self.assertRaises(ContractError):
            validate_procedure(value)

    def test_nested_text_fields_are_bounded(self):
        for path in (("environment", "configuration"), ("parameters", 0, "description"),
                     ("support", 0, "interpretation"), ("steps", 0, "intent"),
                     ("steps", 0, "expected"), ("steps", 0, "on_unexpected")):
            for length in (1024, 1025):
                with self.subTest(path=path, length=length):
                    value = procedure()
                    target = value
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = "x" * length
                    if length == 1024:
                        self.assertEqual(validate_procedure(value), value)
                    else:
                        with self.assertRaises(ContractError):
                            validate_procedure(value)

    def test_condition_list_minima_maxima_and_text_bounds(self):
        for field in ("applicability", "invalidators", "progress", "stop_conditions", "limits"):
            for length in (0, 8, 9):
                with self.subTest(field=field, length=length):
                    value = procedure(**{field: ["condition"] * length})
                    if length == 9 or (length == 0 and field in ("applicability", "progress", "stop_conditions")):
                        with self.assertRaises(ContractError):
                            validate_procedure(value)
                    else:
                        self.assertEqual(validate_procedure(value), value)
            for invalid in ("", "x" * 1025):
                with self.assertRaises(ContractError):
                    validate_procedure(procedure(**{field: [invalid]}))

    def test_parameter_step_and_episode_bounds_and_uniqueness(self):
        parameters = [{"name": f"p-{i}", "description": "Scoped parameter"} for i in range(9)]
        self.assertEqual(len(validate_procedure(procedure(parameters=parameters[:8]))["parameters"]), 8)
        for invalid in (parameters, [parameters[0], {**parameters[0], "description": "Different description"}]):
            with self.assertRaises(ContractError):
                validate_procedure(procedure(parameters=invalid))
        self.assertEqual(validate_procedure(procedure(parameters=[]))["parameters"], [])
        step = procedure()["steps"][0]
        self.assertEqual(len(validate_procedure(procedure(steps=[step] * 16))["steps"]), 16)
        for steps in ([], [step] * 17):
            with self.assertRaises(ContractError):
                validate_procedure(procedure(steps=steps))
        for field in ("support", "counterexamples"):
            episode = procedure()["support"][0]
            self.assertEqual(len(validate_procedure(procedure(**{field: [episode] * 8}))[field]), 8)
            for invalid in ([episode] * 9, [] if field == "support" else [None]):
                with self.assertRaises(ContractError):
                    validate_procedure(procedure(**{field: invalid}))
            for ids, maximum in (("request_ids", 16), ("source_ids", 8)):
                valid = {**episode, ids: [f"id-{i}" for i in range(maximum)]}
                self.assertEqual(validate_procedure(procedure(**{field: [valid]}))[field], [valid])
                for invalid in ([], ["same", "same"], [f"id-{i}" for i in range(maximum + 1)]):
                    with self.assertRaises(ContractError):
                        validate_procedure(procedure(**{field: [{**episode, ids: invalid}]}))

    def test_shape_acceptance_does_not_claim_source_availability_or_truth(self):
        value = procedure(goal="A possibly mistaken interpretation", status="active")
        self.assertEqual(validate_procedure(value), value)
        self.assertEqual(project_procedures([value]), {value["procedure_id"]: value})


class ProcedureProjectionTests(unittest.TestCase):
    def test_complete_ancestry_is_independent_of_input_order_and_mission(self):
        root = procedure()
        child = successor(root)
        transferred = successor(child)
        transferred["mission_id"] = "mission-b"
        transferred["id"] = "rev-1"  # Revision IDs are mission qualified.
        transferred["status"] = "retired"
        for records in ([root, child, transferred], [transferred, child, root],
                        [child, root, transferred, root, child, transferred]):
            self.assertEqual(project_procedures(records), {root["procedure_id"]: transferred})

    def test_independent_families_and_empty_sequence(self):
        a = procedure()
        b = procedure(id="other-root", procedure_id="shelter")
        child = successor(b)
        self.assertEqual(project_procedures((child, a, b)), {a["procedure_id"]: a, b["procedure_id"]: child})
        self.assertEqual(project_procedures([]), {})

    def test_projection_copies_all_nested_values_and_never_edits_history(self):
        records = [procedure(), successor(procedure())]
        before = deepcopy(records)
        result = project_procedures(records)
        result["collect-water"]["parent"]["mission_id"] = "mutated"
        result["collect-water"]["support"][0]["source_ids"].clear()
        self.assertEqual(records, before)
        self.assertEqual(project_procedures(records)["collect-water"], before[-1])

    def test_rejects_changed_qualified_identity_even_in_a_different_family(self):
        root = procedure()
        for change in ({"reason": "Changed immutable copy"}, {"procedure_id": "another-family"}):
            with self.subTest(change=change):
                with self.assertRaises(ContractError):
                    project_procedures([root, {**root, **change}])

    def test_rejects_branches_multiple_roots_and_duplicate_revision_numbers(self):
        root = procedure()
        child = successor(root)
        alternatives = [
            [root, procedure(id="another-root", mission_id="mission-b")],
            [root, child, {**child, "id": "alternate-child"}],
            [root, child, {**child, "id": "stale-child", "mission_id": "mission-b"}],
            [root, child, successor(child, id="next") | {"revision": 2}],
        ]
        for records in alternatives:
            with self.subTest(records=records):
                with self.assertRaises(ContractError):
                    project_procedures(records)

    def test_missing_stale_cross_family_and_nonconsecutive_parents_refuse(self):
        root = procedure()
        child = successor(root)
        other = procedure(id="other", procedure_id="shelter")
        bad_parent = {"mission_id": "wrong-mission", "revision_id": root["id"]}
        cases = [[child], [root, {**child, "parent": bad_parent}],
                 [root, other, {**child, "parent": {"mission_id": other["mission_id"], "revision_id": other["id"]}}],
                 [root, {**child, "revision": 3}], [root, child, {**successor(child), "parent": child["parent"]}],
                 [procedure(revision=2)], [procedure(parent={"mission_id": "mission-a", "revision_id": "rev-1"})],
                 [root, {**child, "parent": None}]]
        for records in cases:
            with self.subTest(records=records):
                with self.assertRaises(ContractError):
                    project_procedures(records)

    def test_cycles_and_self_parent_cannot_supply_closure(self):
        a = procedure(revision=2, parent={"mission_id": "mission-a", "revision_id": "rev-2"})
        b = procedure(id="rev-2", revision=3, parent={"mission_id": "mission-a", "revision_id": "rev-1"})
        for records in ([a, b], [{**a, "parent": b["parent"]}]):
            with self.assertRaises(ContractError):
                project_procedures(records)

    def test_sequence_bound_counts_copies_and_rejects_unordered_or_lazy_inputs(self):
        root = procedure()
        self.assertEqual(project_procedures([root] * 256), {root["procedure_id"]: root})
        for records in ([root] * 257, iter([root]), {"record": root}, "[]", None):
            with self.subTest(type=type(records).__name__):
                with self.assertRaises(ContractError):
                    project_procedures(records)

    def test_all_history_is_validated_even_when_only_latest_is_returned(self):
        root = procedure()
        child = successor(root)
        with self.assertRaises(ContractError):
            project_procedures([{**root, "unexpected": True}, child])


if __name__ == "__main__":
    unittest.main()
