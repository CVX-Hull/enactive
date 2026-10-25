"""Pure synthetic composition checks; these do not establish runtime authority."""
from copy import deepcopy
import unittest

from harness.gameplay.contracts import ContractError, EvidenceRef
from harness.gameplay.evidence import _identity
from harness.gameplay.contracts import canonical
from harness.gameplay.mission_contracts import validate_request
from harness.gameplay.mission_requests import compose_request
from tests.test_gameplay_evidence import observation


def bundle(number=1, *, kind="normal_play"):
    value = observation(number)
    value["boundary"]["id"] = f"boundary-{number}"
    if kind != "normal_play":
        value.update(scene=None, category="YESNO")
        value["boundary"].update(kind=kind, input_receiver=kind == "menu")
    reference = EvidenceRef(_identity(value), value["session"], value["revision"],
        value["timestamp_ms"], 100.0, 4 if kind == "normal_play" else None,
        "/synthetic/retained.png", "a" * 64, kind)
    return dict(reference=reference.to_dict(), observation=value, initial_lag_seconds=0.0)


def snapshot(**changes):
    value = dict(mission_id="mission-test", epoch=3, prompt_phase=None,
                 lifecycle_phase=None, activity_phase=None, current_source=None)
    value.update(changes)
    return value


def skill(kind="inspect", **changes):
    value = dict(kind="skill", skill_kind=kind, goal=dict(purpose="inventory"),
                 work_id=None, perception=None, procedure=None)
    value.update(changes)
    return value


def lifecycle(operation="create", **changes):
    value = dict(kind="lifecycle", operation=operation, world="Visible world",
                 character="Visible character", work_id=None, identity_claim_ids=[])
    value.update(changes)
    return value


def phase(source, **changes):
    return dict(origin_request_id="original-root", checkpoint_id=source["reference"]["observation_id"],
                grants_authority=False, **changes)


def activity_root(kind="activity", *, consent=True, game_seconds=60):
    """Canonical immutable original, independent of the selected child epoch."""
    goal = dict(operation="rest", target="Exact original rest description", game_seconds=game_seconds,
        interrupt_allowed=consent, step="start")
    procedure = None
    if kind in ("direct", "program"):
        goal = dict(expected="Exact original ordinary description", interrupt_allowed=consent)
        if kind == "direct":
            goal.update(input=dict(type="key", key="s", modifiers=[]), intent="Rest")
        else:
            goal.update(state={}, intent="Rest")
            procedure = dict(mission_id="mission-test", revision_id="routine-1", applicability="Visible rest")
    return compose_request(snapshot(epoch=1), request_id="original-root",
        intent=skill(kind, goal=goal, procedure=procedure),
        limits=dict(primitives=8, wall_seconds=45, game_seconds=game_seconds),
        scope="new_root", source=bundle())


class MissionRequestProducerTests(unittest.TestCase):
    def setUp(self):
        self.source = bundle()
        self.status = snapshot()
        self.limits = dict(primitives=8, wall_seconds=45.0, game_seconds=600)

    def compose(self, intent=None, *, scope="new_root", **changes):
        args = dict(request_id="new-request", intent=skill() if intent is None else intent,
                    limits=self.limits, scope=scope, source=self.source)
        args.update(changes)
        return compose_request(self.status, **args)

    def test_root_preserves_semantics_and_copies_every_input(self):
        intent = skill(work_id="chosen-work")
        supports = ["explicit-support"]
        before = deepcopy((self.status, self.source, self.limits, intent, supports))
        result = self.compose(intent, supporting_source_ids=supports)
        expected = dict(schema="mission/11", mission_id="mission-test", epoch=3,
            request_id="new-request", phase_id=None, sources=[self.source["reference"]["observation_id"],
            "explicit-support"], expected_session="synthetic-world", expected_revision=1,
            expected_boundary_id="boundary-1", limits=self.limits, **intent)
        self.assertEqual(result, validate_request(expected))
        self.assertEqual(canonical(result), canonical(expected))
        self.assertEqual((self.status, self.source, self.limits, intent, supports), before)
        result["goal"]["purpose"] = "needs"
        result["limits"]["primitives"] = 1
        result["sources"].append("mutated")
        self.assertEqual((self.status, self.source, self.limits, intent, supports), before)

    def test_navigation_binds_only_selected_published_scope_and_preserves_target(self):
        published = dict(mission_id=self.status["mission_id"], session=self.source["reference"]["session"], coordinate_epoch=4)
        self.status["coordinate_scope"] = published
        self.status["current_source"] = bundle(99)["reference"]
        intent = skill("navigate", goal=dict(target=[1, 2, 0]))
        before = deepcopy((self.status, self.source, intent))
        result = self.compose(intent)
        self.assertEqual(result["goal"], dict(scope=published, target=[1, 2, 0]))
        self.assertEqual(result["expected_revision"], self.source["reference"]["revision"])
        self.assertEqual(result["sources"], [self.source["reference"]["observation_id"]])
        self.assertEqual((self.status, self.source, intent), before)
        with self.assertRaisesRegex(ContractError, "scope"):
            self.compose(skill("navigate", goal=dict(scope=published, target=[1, 2, 0])))
        for invalid in (None, {**published, "mission_id": "other"}, {**published, "session": "other"},
                        {**published, "coordinate_epoch": None}, {key: value for key, value in published.items() if key != "coordinate_epoch"}):
            self.status["coordinate_scope"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ContractError):
                self.compose(intent)

    def test_activity_answer_binds_exact_selected_unanswered_owner(self):
        self.source = bundle(kind="interrupt_confirmation")
        self.source["observation"]["boundary"].update(recovery_operations=["answer_interrupt"], interrupt_request_id="interrupt-1")
        selected = phase(self.source, stage="interrupt_confirmation", answered=False, interrupt_request_id="interrupt-1")
        self.status["activity_phase"] = selected
        root = activity_root()
        goal = dict(step="answer_interrupt", answer="NO")
        intent = skill("activity", goal=goal)
        before = deepcopy((self.status, self.source, intent))
        result = self.compose(intent, scope="activity", original_root=root)
        self.assertEqual(result["goal"], {**root["goal"], **goal, "interrupt_request_id": "interrupt-1"})
        self.assertEqual(result["phase_id"], "original-root")
        self.assertEqual((self.status, self.source, intent), before)
        with self.assertRaisesRegex(ContractError, "interrupt_request_id"):
            self.compose(skill("activity", goal={**root["goal"], **goal, "interrupt_request_id": "interrupt-1"}), scope="activity", original_root=root)
        for changes in (dict(answered=True), dict(stage="activity_poll"), dict(interrupt_request_id=None),
                        dict(interrupt_request_id="other"), dict(checkpoint_id="other")):
            self.status["activity_phase"] = {**selected, **changes}
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.compose(intent, scope="activity", original_root=root)
        self.status["activity_phase"] = selected
        self.source["observation"]["boundary"]["interrupt_request_id"] = "other-owner"
        with self.assertRaises(ContractError):
            self.compose(intent, scope="activity", original_root=root)

    def test_activity_start_preserves_semantics_and_rejects_old_fields(self):
        goal = dict(step="start", operation="craft", target="Exact recipe", game_seconds=60,
            interrupt_allowed=False)
        result = self.compose(skill("activity", goal=goal))
        self.assertEqual(result["goal"], {**goal, "answer": None, "interrupt_request_id": None})
        for changes in (dict(answer=None), dict(interrupt_request_id=None), dict(operation="direct")):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.compose(skill("activity", goal={**goal, **changes}))

    def test_activity_children_inherit_exact_semantic_or_ordinary_root(self):
        for kind in ("activity", "direct", "program"):
            for scope in ("prompt", "activity"):
                for step in ("poll", "interrupt", "resume"):
                    with self.subTest(kind=kind, scope=scope, step=step):
                        self.status = snapshot(**{scope + "_phase": phase(self.source)})
                        root = activity_root(kind, consent=False)
                        before = deepcopy(root)
                        result = self.compose(skill("activity", goal=dict(step=step)),
                            scope=scope, original_root=root)
                        stable = {key: root["goal"][key] for key in
                            ("operation", "target", "game_seconds", "interrupt_allowed")} if kind == "activity" else dict(
                                operation="direct", target=root["goal"]["expected"],
                                game_seconds=60, interrupt_allowed=False)
                        self.assertEqual(result["goal"], {**stable, "step": step,
                            "answer": None, "interrupt_request_id": None})
                        self.assertEqual(result["limits"], self.limits)
                        self.assertEqual(result["phase_id"], root["request_id"])
                        self.assertEqual(root, before)
                        self.assertEqual(result["epoch"], 3)

    def test_ordinary_activity_duration_uses_explicit_ceilings_without_renewing_limits(self):
        self.status["prompt_phase"] = phase(self.source)
        for kind in ("direct", "program"):
            root = activity_root(kind, game_seconds=43_200)
            for child_seconds, expected in ((10, 10), (43_200, 43_200), (0, None), (43_201, None), (True, None), (None, None)):
                limits = {**self.limits, "game_seconds": child_seconds}
                with self.subTest(kind=kind, child_seconds=child_seconds):
                    if expected is None:
                        with self.assertRaises(ContractError):
                            self.compose(skill("activity", goal=dict(step="poll")), scope="prompt",
                                original_root=root, limits=limits)
                    else:
                        child = self.compose(skill("activity", goal=dict(step="poll")), scope="prompt",
                            original_root=root, limits=limits)
                        self.assertEqual(child["goal"]["game_seconds"], expected)
                        self.assertEqual(child["limits"], limits)
            root["limits"]["game_seconds"] = 0
            with self.subTest(kind=kind, root_seconds=0), self.assertRaises(ContractError):
                self.compose(skill("activity", goal=dict(step="poll")), scope="prompt", original_root=root)

    def test_activity_child_requires_exact_canonical_original_root_and_minimal_goal(self):
        self.status["prompt_phase"] = phase(self.source)
        root = activity_root()
        intent = skill("activity", goal=dict(step="poll"))
        for invalid in (None, {}, {**root, "mission_id": "other"}, {**root, "request_id": "other"},
                        {**root, "schema": "mission/10"}, {**root, "phase_id": "ancestor"},
                        {**root, "skill_kind": "inspect", "goal": dict(purpose="needs")}):
            with self.subTest(invalid=invalid), self.assertRaises(ContractError):
                self.compose(intent, scope="prompt", original_root=invalid)
        for key in ("operation", "target", "game_seconds", "interrupt_allowed", "answer", "interrupt_request_id"):
            with self.subTest(key=key), self.assertRaises(ContractError):
                self.compose(skill("activity", goal=dict(step="poll", **{key: root["goal"][key]})),
                    scope="prompt", original_root=root)
        with self.assertRaises(ContractError):
            self.compose(intent, scope="prompt", original_root=root,
                limits={**self.limits, "game_seconds": 59})

    def test_opaque_headers_and_perception_source_cannot_be_overridden(self):
        for key in ("schema", "mission_id", "epoch", "request_id", "limits", "phase_id", "sources",
                    "expected_session", "expected_revision", "expected_boundary_id"):
            with self.subTest(key=key), self.assertRaises(ContractError):
                self.compose({**skill(), key: None})
        self.status["prompt_phase"] = phase(self.source)
        with self.assertRaisesRegex(ContractError, "source_id"):
            self.compose(skill("menu", goal=dict(purpose="Answer", label="Yes", outcome="activated"),
                perception=dict(kind="confirmation", basis="player_interpretation",
                                question="Exact question?", source_id="copied-source")), scope="prompt")

    def test_prompt_binds_exact_primary_and_preserves_perception(self):
        self.source = bundle(kind="menu")
        self.status["prompt_phase"] = phase(self.source)
        view = dict(kind="confirmation", basis="player_interpretation", question="Exact question?")
        intent = skill("menu", goal=dict(purpose="Answer", label="Yes", outcome="activated"),
                       perception=view, work_id="chosen-work")
        before = deepcopy(intent)
        result = self.compose(intent, scope="prompt")
        self.assertEqual(result["phase_id"], "original-root")
        self.assertEqual(result["perception"], {**view, "source_id": self.source["reference"]["observation_id"]})
        self.assertEqual(intent, before)
        self.assertEqual(result["work_id"], "chosen-work")
        result["perception"]["question"] = "Changed after composition"
        self.assertEqual(intent, before)

    def test_valid_menu_and_editor_children_cannot_be_new_roots(self):
        self.status["prompt_phase"] = phase(self.source)
        menu = skill("menu", goal=dict(purpose="Choose", label="Visible row", outcome="focused"))
        editor = skill("edit", goal=dict(purpose="quantity", text="2", commit=True),
            perception=dict(kind="editor", basis="player_interpretation", purpose="quantity",
                            label="Count", visible_text="1", whole_value=True, focused=True))
        for intent in (menu, editor):
            with self.subTest(intent=intent):
                self.assertEqual(self.compose(intent, scope="prompt")["phase_id"], "original-root")
                self.status["prompt_phase"] = None
                with self.assertRaisesRegex(ContractError, "new skill root"):
                    self.compose(intent)
                self.status["prompt_phase"] = phase(self.source)

    def test_missing_wrong_and_incomplete_scopes_reject_without_root_fallback(self):
        for selected in ("prompt", "lifecycle", "activity", "unknown", None):
            with self.subTest(selected=selected), self.assertRaises(ContractError):
                self.compose(scope=selected)
        self.status["lifecycle_phase"] = phase(self.source, operation="create")
        with self.assertRaises(ContractError):
            self.compose(skill(goal=dict(purpose="character_identity")), scope="prompt")
        with self.assertRaises(ContractError):
            self.compose()
        self.status["lifecycle_phase"]["checkpoint_id"] = "another-source"
        with self.assertRaises(ContractError):
            self.compose(skill(goal=dict(purpose="character_identity")), scope="lifecycle")
        self.status = snapshot()
        del self.status["activity_phase"]
        with self.assertRaises(ContractError):
            self.compose()

    def test_lifecycle_binds_headers_and_leaves_skill_eligibility_to_receiver(self):
        self.status["lifecycle_phase"] = phase(self.source, operation="create")
        result = self.compose(skill(goal=dict(purpose="character_identity")), scope="lifecycle")
        self.assertEqual(result["phase_id"], "original-root")
        for intent in (skill(), skill(goal=dict(purpose="character_identity"), work_id="unrelated"),
                       skill("interact", goal=dict(action="inventory", intent="Open", desired_outcome="View"))):
            with self.subTest(intent=intent):
                request = self.compose(intent, scope="lifecycle")
                self.assertEqual(request["phase_id"], "original-root")
                self.assertEqual(request["work_id"], intent["work_id"])
                validate_request(request)

    def test_lifecycle_direct_uses_the_selected_root_without_a_menu_taxonomy(self):
        self.source = bundle(kind="menu")
        intent = skill("direct", goal=dict(input=dict(type="key", key="n", modifiers=[]),
            intent="Cancel the visible incidental dialog", expected="Dialog closes",
            interrupt_allowed=False))
        for operation in ("create", "load", "save", "exit"):
            self.status["lifecycle_phase"] = phase(self.source, operation=operation)
            with self.subTest(operation=operation):
                request = self.compose(intent, scope="lifecycle")
                self.assertEqual(request["phase_id"], "original-root")
                self.assertEqual(request["goal"], intent["goal"])
                self.assertEqual(request["sources"], [self.source["reference"]["observation_id"]])
                validate_request(request)
        self.status["lifecycle_phase"]["checkpoint_id"] = "different-checkpoint"
        with self.assertRaises(ContractError):
            self.compose(intent, scope="lifecycle")

    def test_existing_scope_rejects_unsupported_skill_without_dispatch(self):
        self.status["prompt_phase"] = phase(self.source)
        with self.assertRaisesRegex(ContractError, "does not support"):
            self.compose(skill("interact", goal=dict(action="inventory", intent="Open", desired_outcome="View")),
                         scope="prompt")
        self.status["activity_phase"] = phase(self.source)
        for kind in ("inspect", "menu", "edit", "item", "interact", "navigate"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ContractError, "does not support"):
                self.compose(skill(kind), scope="activity")

    def test_lifecycle_menu_and_editor_children_preserve_choices(self):
        self.status["lifecycle_phase"] = phase(self.source, operation="create")
        intents = (skill("menu", goal=dict(purpose="Choose", label="Visible row", outcome="focused")),
            skill("edit", goal=dict(purpose="character_name", text="Visible character", commit=True),
                perception=dict(kind="editor", basis="player_interpretation", purpose="character_name",
                    label="Name", visible_text="", whole_value=True, focused=True)))
        for intent in intents:
            with self.subTest(intent=intent):
                result = self.compose(intent, scope="lifecycle")
                self.assertEqual(result["goal"], intent["goal"])
                self.assertEqual(result["phase_id"], "original-root")
                composed = self.compose({**intent, "work_id": "unrelated-work"}, scope="lifecycle")
                self.assertEqual(composed["work_id"], "unrelated-work")

    def test_source_free_launch_is_explicit_new_root_only(self):
        result = self.compose(lifecycle("launch"), source=None)
        self.assertEqual(result["sources"], [])
        self.assertIsNone(result["phase_id"])
        self.assertTrue(all(result[field] is None for field in
            ("expected_session", "expected_revision", "expected_boundary_id")))
        for changes in (dict(source=self.source), dict(source=None, supporting_source_ids=["old"]),
                        dict(source=None, scope="lifecycle")):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.compose(lifecycle("launch"), **changes)
        for intent in (skill(), lifecycle("create"), lifecycle("finish")):
            with self.subTest(intent=intent), self.assertRaises(ContractError):
                self.compose(intent, source=None)

    def test_lifecycle_roots_and_same_operation_children(self):
        for operation in ("create", "save", "load"):
            with self.subTest(operation=operation):
                self.status = snapshot()
                self.assertIsNone(self.compose(lifecycle(operation))["phase_id"])
                self.status["lifecycle_phase"] = phase(self.source, operation=operation)
                child = self.compose(lifecycle(operation), scope="lifecycle")
                self.assertEqual(child["phase_id"], "original-root")
                with self.assertRaises(ContractError):
                    self.compose(lifecycle("exit"), scope="lifecycle")
                with self.assertRaises(ContractError):
                    self.compose(lifecycle("load" if operation != "load" else "save"), scope="lifecycle")
                with self.assertRaises(ContractError):
                    self.compose(lifecycle(operation))

    def test_two_observation_transition_uses_explicit_latest_primary_and_first_support(self):
        first, latest = bundle(2), bundle(3)
        self.status["lifecycle_phase"] = phase(latest, operation="create")
        self.status["current_source"] = None
        request = self.compose(lifecycle("create"), scope="lifecycle", source=latest,
                               supporting_source_ids=(first["reference"]["observation_id"],))
        self.assertEqual(request["sources"], [latest["reference"]["observation_id"],
                                             first["reference"]["observation_id"]])
        self.assertEqual(request["expected_revision"], 3)
        with self.assertRaises(ContractError):
            self.compose(lifecycle("create"), scope="lifecycle", source=first,
                         supporting_source_ids=(latest["reference"]["observation_id"],))

    def test_exit_menu_and_retained_finish_do_not_require_current_source(self):
        self.source = bundle(kind="menu")
        self.status["lifecycle_phase"] = phase(self.source, operation="exit")
        intent = skill("menu", goal=dict(purpose="Quit", label="Yes", outcome="activated"),
            perception=dict(kind="confirmation", basis="player_interpretation", question="Really quit?"))
        self.assertEqual(self.compose(intent, scope="lifecycle")["phase_id"], "original-root")
        request = self.compose(skill(goal=dict(purpose="character_identity")), scope="lifecycle")
        self.assertEqual(request["phase_id"], "original-root")
        self.status["lifecycle_phase"] = None
        self.status["current_source"] = bundle(99)["reference"]
        result = self.compose(lifecycle("finish"))
        self.assertIsNone(result["phase_id"])
        self.assertEqual(result["expected_revision"], 1)

    def test_setup_abort_exit_is_explicit_null_root_only_alongside_create_or_load(self):
        for operation in ("create", "load"):
            self.status["lifecycle_phase"] = phase(self.source, operation=operation)
            self.assertIsNone(self.compose(lifecycle("exit"))["phase_id"])
        self.status["lifecycle_phase"] = phase(self.source, operation="save")
        with self.assertRaises(ContractError):
            self.compose(lifecycle("exit"))
        self.status["lifecycle_phase"] = phase(self.source, operation="create")
        self.status["prompt_phase"] = phase(self.source)
        with self.assertRaises(ContractError):
            self.compose(lifecycle("exit"))

    def test_frameless_activity_checkpoint_can_have_no_current_source(self):
        self.source = bundle(kind="interrupt_confirmation")
        self.source["observation"]["boundary"].update(recovery_operations=["answer_interrupt"],
                                                      interrupt_request_id="interrupt-1")
        self.status["activity_phase"] = phase(self.source, stage="awaiting_readmission")
        intent = skill("activity", goal=dict(step="resume"), work_id="rest-work")
        result = self.compose(intent, scope="activity", original_root=activity_root())
        self.assertEqual(result["phase_id"], "original-root")
        self.assertEqual(result["work_id"], "rest-work")
        for selected in ("activity", "prompt"):
            self.status[selected + "_phase"] = phase(self.source)
            with self.subTest(selected=selected), self.assertRaises(ContractError):
                self.compose(lifecycle(), scope=selected)

    def test_bundle_metadata_must_agree_without_claiming_file_verification(self):
        for field, value in (("observation_id", "wrong-id"), ("session", "wrong-session"),
                             ("revision", 99), ("timestamp_ms", 999), ("turn", 9),
                             ("boundary_kind", "menu")):
            with self.subTest(field=field), self.assertRaises(ContractError):
                altered = deepcopy(self.source)
                altered["reference"][field] = value
                self.compose(source=altered)
        for field in ("reference", "observation"):
            with self.subTest(missing=field), self.assertRaises(ContractError):
                altered = deepcopy(self.source)
                del altered[field]
                self.compose(source=altered)
        # The synthetic reference points at no actual PNG; composition performs no I/O.
        self.assertEqual(self.compose()["expected_boundary_id"], "boundary-1")

    def test_existing_validator_owns_support_bounds_limits_and_cross_fields(self):
        for supports in ((self.source["reference"]["observation_id"],), ("same", "same"),
                         tuple(f"support-{number}" for number in range(8))):
            with self.subTest(supports=supports), self.assertRaises(ContractError):
                self.compose(supporting_source_ids=supports)
        for limits in ({**self.limits, "wall_seconds": 0}, {**self.limits, "primitives": True}):
            with self.subTest(limits=limits), self.assertRaises(ContractError):
                self.compose(limits=limits)
        for intent in (dict(kind="handoff"), dict(kind="readmit"), dict(kind="remember"), dict(kind="claim")):
            with self.subTest(intent=intent), self.assertRaises(ContractError):
                self.compose(intent)


if __name__ == "__main__":
    unittest.main()
