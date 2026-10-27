"""Pure procedure shape/ancestry tests; sources and truth require integration."""
from copy import deepcopy
import hashlib
import json
import unittest

from jsonschema import Draft202012Validator

from harness.gameplay.contracts import ContractError
from harness.gameplay.contracts import canonical
from harness.gameplay.procedures import (
    author_procedure, import_procedure, lineage_node_schema, procedure_authoring_schema,
    procedure_schema, project_procedures, validate_lineage_node, validate_procedure,
)


def procedure(**changes):
    return {
        "schema": "procedure/3", "record_type": "Procedure", "id": "rev-1",
        "mission_id": "mission-a", "procedure_id": "collect-water", "revision": 1,
        "parent": None, "program": None, "goal": "Collect usable water",
        "parameters": [{"name": "container", "description": "A suitable container"}],
        "applicability": ["A source is visibly available"],
        "invalidators": ["The source becomes inaccessible"],
        "steps": [{"intent": "Inspect the source", "expected": "Usable water is shown",
                   "on_unexpected": "Stop and reassess"}],
        "progress": ["Water is visibly carried"], "stop_conditions": ["Target met"],
        "limits": ["Not assessed with hostile creatures nearby"],
        "environment": {"engine_commit": "a" * 40, "native_protocol": 7,
                        "mission_schema": "mission/11", "configuration": "Ordinary setup"},
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


def historical(record=None):
    original = procedure() if record is None else deepcopy(record)
    original["environment"]["native_protocol"] = 6
    return import_procedure(canonical(original), ledger_sha256="b" * 64, index_sha256="c" * 64)


class HistoricalProcedureTests(unittest.TestCase):
    def test_import_preserves_original_semantics_and_hashes_exact_stored_utf8_body(self):
        original = procedure(status="active", program={"language": "javascript/1",
                                                      "source": "return '水';"})
        original["environment"]["native_protocol"] = 6
        body = " \n" + json.dumps(original, ensure_ascii=False, indent=2) + "\n"
        node = import_procedure(body, ledger_sha256="b" * 64, index_sha256="c" * 64)
        self.assertEqual(node, {**original, "schema": "procedure-import/1",
                               "record_type": "HistoricalProcedure", "advisory_only": True,
                               "origin": {"schema": "procedure/3", "record_type": "Procedure",
                                          "record_sha256": hashlib.sha256(body.encode()).hexdigest(),
                                          "ledger_sha256": "b" * 64, "index_sha256": "c" * 64,
                                          "program_view": "program-view/1"}})
        self.assertNotEqual(node["origin"]["record_sha256"],
                            hashlib.sha256(canonical(original).encode()).hexdigest())
        for value in (node, canonical(node), canonical(node).encode()):
            result = validate_lineage_node(value)
            self.assertEqual(result, node)
            result["environment"]["configuration"] = "changed"
        self.assertEqual(node["environment"], original["environment"])
        with self.assertRaises(ContractError):
            validate_procedure(node)
        self.assertEqual(validate_lineage_node(procedure()), procedure())

    def test_union_schema_is_closed_tagged_and_defensively_copied(self):
        schema = lineage_node_schema()
        Draft202012Validator.check_schema(schema)
        self.assertEqual(len(schema["oneOf"]), 2)
        for variant in schema["oneOf"]:
            self.assertFalse(variant["additionalProperties"])
        schema["oneOf"][1]["properties"]["environment"]["properties"]["native_protocol"] = {}
        schema["oneOf"][0]["required"].clear()
        self.assertTrue(lineage_node_schema()["oneOf"][0]["required"])
        node = historical()
        for field in node:
            invalid = deepcopy(node)
            del invalid[field]
            with self.subTest(missing=field), self.assertRaises(ContractError):
                validate_lineage_node(invalid)
        for path in ((), ("origin",), ("environment",), ("support", 0)):
            invalid = deepcopy(node)
            target = invalid
            for key in path:
                target = target[key]
            target["extra"] = True
            with self.subTest(path=path), self.assertRaises(ContractError):
                validate_lineage_node(invalid)

    def test_forged_tags_environment_origin_and_unbounded_records_refuse(self):
        node = historical()
        invalid = [procedure(environment={**procedure()["environment"], "native_protocol": 6}),
                   {**node, "schema": "procedure/3", "record_type": "Procedure"},
                   {**procedure(), "schema": "procedure-import/1", "record_type": "HistoricalProcedure"},
                   {**node, "advisory_only": False},
                   {**node, "environment": procedure()["environment"]}]
        for field, value in (("schema", "procedure/2"), ("record_type", "HistoricalProcedure"),
                             ("record_sha256", "A" * 64), ("ledger_sha256", "b" * 63),
                             ("index_sha256", "c" * 65), ("program_view", "program-view/2")):
            invalid.append({**node, "origin": {**node["origin"], field: value}})
        invalid.extend([{**node, "parameters": node["parameters"] * 2},
                        {**node, "program": {"language": "javascript/1", "source": "x" * 32768}}])
        for value in invalid:
            with self.subTest(value=str(value)[:100]), self.assertRaises(ContractError):
                validate_lineage_node(value)
        for value in (procedure(), {**procedure(), "schema": "procedure/2"}, node,
                      {**procedure(), "environment": {**node["environment"], "native_protocol": 5}}):
            with self.subTest(original=value["schema"]), self.assertRaises(ContractError):
                import_procedure(canonical(value), ledger_sha256="b" * 64, index_sha256="c" * 64)
        for body in (node, b"{}", "{", "\ud800"):
            with self.subTest(body=str(body)[:30]), self.assertRaises(ContractError):
                import_procedure(body, ledger_sha256="b" * 64, index_sha256="c" * 64)
        with self.assertRaises(ContractError):
            import_procedure(canonical({**procedure(), "environment": node["environment"]}),
                             ledger_sha256="invalid", index_sha256="c" * 64)

    def test_lineage_union_preserves_strict_integer_and_exact_byte_bounds(self):
        for node in (procedure(), historical()):
            for invalid in ({**node, "revision": 1.0}, {**node, "revision": True},
                            {**node, "environment": {**node["environment"],
                                                    "native_protocol": float(node["environment"]["native_protocol"])}}):
                with self.subTest(schema=node["schema"], invalid=invalid), self.assertRaises(ContractError):
                    validate_lineage_node(invalid)
        node = historical(procedure(steps=[{"intent": "x" * 1024, "expected": "x" * 1024,
                                            "on_unexpected": "x" * 1024} for _ in range(10)]))
        size = len(canonical(node).encode())
        node["goal"] = "x" * (32768 - size + len(node["goal"]))
        self.assertEqual(len(canonical(node).encode()), 32768)
        self.assertEqual(validate_lineage_node(node), node)
        node["goal"] += "x"
        with self.assertRaises(ContractError):
            validate_lineage_node(node)
        original = {key: value for key, value in node.items() if key not in ("advisory_only", "origin")}
        original.update(schema="procedure/3", record_type="Procedure")
        # Import metadata itself must fit the same bound, even if the original fits.
        with self.assertRaises(ContractError):
            import_procedure(canonical(original), ledger_sha256="b" * 64, index_sha256="c" * 64)

    def test_exact_selected_historical_head_authors_current_same_family_revision_three(self):
        root = historical()
        child = historical(successor(root, mission_id="older-mission", status="active"))
        entry = ProcedureAuthoringTests().entry(
            parent={"mission_id": child["mission_id"], "revision_id": child["id"]})
        current = author_procedure(entry, mission_id="current-mission", identity="request-3",
                                   environment=procedure()["environment"], parent=child)
        self.assertEqual(current["procedure_id"], root["procedure_id"])
        self.assertEqual(current["revision"], 3)
        self.assertEqual(current["parent"], entry["parent"])
        self.assertEqual(validate_procedure(current), current)
        self.assertEqual(current["environment"]["native_protocol"], 7)
        for records in ([root, child, current], [current, child, root, child]):
            self.assertEqual(project_procedures(records), {root["procedure_id"]: current})
        with self.assertRaises(ContractError):
            author_procedure(entry, mission_id="current-mission", identity="request-3",
                             environment=procedure()["environment"], parent=root)
        with self.assertRaises(ContractError):
            author_procedure(entry, mission_id="current-mission", identity="request-3",
                             environment=child["environment"], parent=child)

    def test_historical_projection_keeps_parent_branch_and_conflict_refusals(self):
        root = historical()
        child = historical(successor(root))
        cases = [[child], [root, {**child, "parent": {"mission_id": "foreign", "revision_id": root["id"]}}],
                 [root, {**child, "procedure_id": "another-family"}],
                 [root, {**child, "revision": 3}], [root, child, {**child, "id": "branch"}],
                 [root, child, {**child, "origin": {**child["origin"], "record_sha256": "d" * 64}}],
                 [root, {**root, "schema": "procedure/3", "record_type": "Procedure"}]]
        for records in cases:
            with self.subTest(records=str(records)[:80]), self.assertRaises(ContractError):
                project_procedures(records)
        self.assertEqual(project_procedures([child, root]), {root["procedure_id"]: child})


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
            "schema": ["procedure/0", "procedure/1", "procedure/2", "procedure/4"], "record_type": ["Claim"],
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


class ProcedureAuthoringTests(unittest.TestCase):
    mechanical = {"schema", "record_type", "id", "mission_id", "procedure_id", "revision", "environment"}

    def entry(self, **changes):
        return {key: value for key, value in procedure(**changes).items() if key not in self.mechanical}

    def author(self, entry=None, **changes):
        return author_procedure(self.entry() if entry is None else entry,
                                **{"mission_id": "mission-a", "identity": "request-1",
                                   "environment": procedure()["environment"], **changes})

    def test_semantic_schema_is_derived_closed_and_defensively_copied(self):
        schema = procedure_authoring_schema()
        Draft202012Validator.check_schema(schema)
        expected = procedure_schema()
        for field in self.mechanical:
            del expected["properties"][field]
            expected["required"].remove(field)
        self.assertEqual(schema, expected)
        self.assertFalse(schema["additionalProperties"])
        schema["properties"]["steps"]["items"]["required"].clear()
        schema["required"].clear()
        self.assertEqual(procedure_authoring_schema(), expected)
        self.assertTrue(procedure_schema()["properties"]["steps"]["items"]["required"])

    def test_root_has_stable_canonical_ids_and_semantics(self):
        entry = self.entry(program={"language": "javascript/1", "source": "return null;"})
        result = self.author(entry)
        digest = hashlib.sha256(b"mission-a\0request-1").hexdigest()
        self.assertEqual(result, {**entry, "schema": "procedure/3", "record_type": "Procedure",
                                 "id": "revision-" + digest, "mission_id": "mission-a",
                                 "procedure_id": "procedure-" + digest, "revision": 1,
                                 "environment": procedure()["environment"]})
        self.assertEqual(self.author(entry), result)
        for change in ({"mission_id": "mission-b"}, {"identity": "request-2"}):
            other = self.author(entry, **change)
            self.assertNotEqual(other["id"], result["id"])
            self.assertNotEqual(other["procedure_id"], result["procedure_id"])
        self.assertEqual(validate_procedure(result), result)

    def test_successor_inherits_selected_family_and_advances_foreign_mission_parent(self):
        parent = procedure(revision=3, mission_id="older-mission",
                           environment={**procedure()["environment"], "configuration": "Older setup"})
        entry = self.entry(parent={"mission_id": parent["mission_id"], "revision_id": parent["id"]})
        result = self.author(entry, parent=parent)
        self.assertEqual(result["mission_id"], "mission-a")
        self.assertEqual(result["procedure_id"], parent["procedure_id"])
        self.assertEqual(result["revision"], 4)
        self.assertEqual(result["parent"], entry["parent"])
        self.assertEqual(result["id"], self.author()["id"])
        # A full validated revision is sufficient; ancestry/source availability is the caller's job.
        self.assertEqual(result["environment"], procedure()["environment"])

    def test_missing_unused_mismatched_and_invalid_selected_parents_refuse(self):
        parent = procedure()
        entry = self.entry(parent={"mission_id": parent["mission_id"], "revision_id": parent["id"]})
        cases = [(entry, None), (self.entry(), parent),
                 (entry, {**parent, "id": "other-revision"}),
                 (entry, {**parent, "mission_id": "other-mission"}),
                 (entry, entry["parent"]), (entry, {**parent, "extra": True})]
        for semantic, selected in cases:
            with self.subTest(entry_parent=semantic["parent"], selected=selected):
                with self.assertRaises(ContractError):
                    self.author(semantic, parent=selected)

    def test_semantic_fields_are_required_and_canonical_overrides_refuse(self):
        for field in self.entry():
            with self.subTest(missing=field):
                entry = self.entry()
                del entry[field]
                with self.assertRaises(ContractError):
                    self.author(entry)
        for field in self.mechanical | {"unknown"}:
            with self.subTest(override=field):
                with self.assertRaises(ContractError):
                    self.author({**self.entry(), field: procedure().get(field)})
        for entry in (None, [], True, {**self.entry(), "steps": []},
                      {**self.entry(), "parameters": procedure()["parameters"] * 2}):
            with self.subTest(entry=entry):
                with self.assertRaises(ContractError):
                    author_procedure(entry, mission_id="mission-a", identity="request-1",
                                     environment=procedure()["environment"])

    def test_mission_and_identity_use_existing_bounded_ascii_id_shape(self):
        for field in ("mission_id", "identity"):
            for invalid in (None, True, "", "a" * 129, "_leading", "a/b", "a b", "é", "a\n"):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaises(ContractError):
                        self.author(**{field: invalid})
        self.assertEqual(self.author(mission_id="a" * 128, identity="A_-9")["mission_id"], "a" * 128)

    def test_nested_inputs_and_outputs_are_independent(self):
        parent = procedure()
        entry = self.entry(parent={"mission_id": parent["mission_id"], "revision_id": parent["id"]})
        environment = procedure()["environment"]
        before = deepcopy((entry, parent, environment))
        result = self.author(entry, parent=parent, environment=environment)
        result["steps"][0]["intent"] = "changed"
        result["support"][0]["source_ids"].clear()
        result["parent"]["mission_id"] = "changed"
        result["environment"]["configuration"] = "changed"
        self.assertEqual((entry, parent, environment), before)
        clean = self.author(entry, parent=parent, environment=environment)
        entry["parameters"][0]["description"] = "changed"
        parent["procedure_id"] = "changed"
        environment["configuration"] = "changed"
        self.assertEqual(clean["parameters"], before[0]["parameters"])
        self.assertEqual(clean["procedure_id"], before[1]["procedure_id"])
        self.assertEqual(clean["environment"], before[2])

    def test_final_canonical_environment_revision_and_byte_bounds_remain(self):
        for environment in (None, {}, {**procedure()["environment"], "native_protocol": True},
                            {**procedure()["environment"], "mission_schema": "mission/10"}):
            with self.subTest(environment=environment):
                with self.assertRaises(ContractError):
                    self.author(environment=environment)
        reference = {"mission_id": "mission-a", "revision_id": "rev-1"}
        self.assertEqual(self.author(self.entry(parent=reference),
                                     parent=procedure(revision=1023))["revision"], 1024)
        with self.assertRaises(ContractError):
            self.author(self.entry(parent=reference), parent=procedure(revision=1024))
        entry = self.entry(steps=[{"intent": "x" * 1024, "expected": "x" * 1024,
                                  "on_unexpected": "x" * 1024} for _ in range(10)])
        size = len(canonical(self.author(entry)).encode())
        entry["goal"] = "x" * (32768 - size + len(entry["goal"]))
        self.assertEqual(len(canonical(self.author(entry)).encode()), 32768)
        entry["goal"] += "x"
        with self.assertRaises(ContractError):
            self.author(entry)


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
