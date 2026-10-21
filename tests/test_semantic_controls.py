"""Passive policy tests with retained synthetic frames; no native gameplay claim."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.contracts import ContractError, PrimitiveResult
from harness.gameplay.evidence import EvidenceError, EvidenceStore
from harness.gameplay.mission_contracts import SourceBinding, SourceRevalidation, VERSION
from harness.gameplay.semantic_controls import ControlIntent, ControlOutcome, SemanticControlSkill
from tests.test_gameplay_evidence import observation, png


class SemanticControlTests(unittest.TestCase):
    def test_any_key_popup_acknowledgement_is_one_key_with_unverified_effect(self):
        for language_action in ([], ["toggle_language_to_en"]):
            for after_kind in ("same_popup", "question", "normal"):
                with self.subTest(language_action=language_action, after_kind=after_kind):
                    actions = language_action + ["ANY_INPUT", "COORDINATE"]
                    before = self.frame(category="POPUP_WAIT", actions=actions)
                    skill = self.skill(before, view=self.view(before, kind="dismissal"),
                        goal=dict(purpose="Acknowledge visible notice", label="Cancel", outcome="dismissed"))
                    intent = self.propose(skill)
                    self.assertIsInstance(intent, ControlIntent)
                    self.assertEqual((intent.kind, intent.action), ("key", "SPACE"))
                    if after_kind == "same_popup":
                        # A new returned observation may show the same pixels;
                        # reusing the old evidence as a return would be unknown.
                        after = self.frame(category="POPUP_WAIT", actions=actions, same=before)
                    else:
                        after = self.frame(normal=after_kind == "normal", category="YESNO", actions=["YES", "NO"])
                    outcome = self.accept(skill, intent, after)
                    self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
                    self.assertTrue(outcome.verification_required)
                    self.assertIsNone(outcome.pending_logical_id)
                    self.assertIs(self.propose(skill), outcome)

    def test_popup_acknowledgement_does_not_guess_ambiguous_or_other_controls(self):
        for category, actions in (("POPUP_WAIT", ["ANY_INPUT"]),
                                  ("POPUP_WAIT", ["COORDINATE"]),
                                  ("POPUP_WAIT", ["ANY_INPUT", "COORDINATE", "CONFIRM"]),
                                  ("POPUP_WAIT", ["toggle_language_to_en", "ANY_INPUT", "COORDINATE", "UNKNOWN"]),
                                  ("OTHER", ["ANY_INPUT", "COORDINATE"]),
                                  ("YESNO", ["ANY_INPUT", "COORDINATE", "YES", "NO"])):
            with self.subTest(category=category, actions=actions):
                before = self.frame(category=category, actions=actions)
                skill = self.skill(before, view=self.view(before, kind="dismissal"),
                    goal=dict(purpose="Close visible prompt", label="Cancel", outcome="dismissed"))
                outcome = self.propose(skill)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def test_any_key_popup_with_represented_choices_is_not_acknowledged(self):
        before = self.frame(category="POPUP_WAIT", actions=["toggle_language_to_en", "ANY_INPUT", "COORDINATE"],
            change=lambda value: value.update(ui=dict(purpose="uilist", title="Choose", rows=[
                dict(id="choice", text="Yes", enabled=True, hotkey=None)], selected="choice",
                filter=None, count=None, coverage="rendered_rows_only")))
        skill = self.skill(before, view=self.view(before, kind="dismissal"),
            goal=dict(purpose="Close visible prompt", label="Cancel", outcome="dismissed"))
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def test_any_key_popup_unknown_delivery_is_terminal_without_replay(self):
        before = self.frame(category="POPUP_WAIT", actions=["toggle_language_to_en", "ANY_INPUT", "COORDINATE"])
        skill = self.skill(before, view=self.view(before, kind="dismissal"),
            goal=dict(purpose="Close visible notice", label="Cancel", outcome="dismissed"))
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, disposition="unknown")
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("unknown", 1))
        self.assertEqual(outcome.pending_logical_id, intent.logical_id)
        self.assertIs(self.propose(skill), outcome)

    def test_any_key_popup_changed_source_pixels_block_before_proposal(self):
        before = self.frame(category="POPUP_WAIT", actions=["toggle_language_to_en", "ANY_INPUT", "COORDINATE"])
        skill = self.skill(before, view=self.view(before, kind="dismissal"),
            goal=dict(purpose="Close visible notice", label="Cancel", outcome="dismissed"))
        # Deliberately corrupt this test's owned archive; real archives are
        # read-only. No historical/native evidence is modified.
        Path(before.frame_path).chmod(0o600)
        Path(before.frame_path).write_bytes(png(b"changed visible prompt"))
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def test_popup_with_registered_quit_uses_quit_instead_of_an_acknowledgement_key(self):
        before = self.frame(category="POPUP_WAIT", actions=["toggle_language_to_en", "ANY_INPUT", "COORDINATE", "QUIT"])
        skill = self.skill(before, view=self.view(before, kind="dismissal"),
            goal=dict(purpose="Cancel visible popup", label="Cancel", outcome="dismissed"))
        intent = self.propose(skill)
        self.assertEqual((intent.kind, intent.action), ("action", "QUIT"))

    def test_dismissal_uses_one_actual_registered_action_without_effect_credit(self):
        for category, action in (("INVENTORY", "QUIT"), ("STRING_INPUT", "TEXT.QUIT"), ("YESNO", "QUIT"),
                                 ("UILIST", "UILIST.QUIT"), ("WORLDGEN_CONFIRM_DIALOG", "WORLDGEN_CONFIRM.QUIT")):
            with self.subTest(category=category):
                before = self.frame(category=category, actions=[action])
                skill = self.skill(before, view=self.view(before, kind="dismissal"),
                    goal=dict(purpose="Close visible prompt", label="Cancel", outcome="dismissed"))
                intent = self.propose(skill)
                self.assertEqual(intent.action, action)
                # A cancellation can open another prompt; do not answer it.
                after = self.frame(category="YESNO", actions=["YES", "NO"])
                outcome = self.accept(skill, intent, after)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
                self.assertTrue(outcome.verification_required)
                self.assertIs(self.propose(skill), outcome)

    def test_dismissal_never_substitutes_no_confirm_or_quit_for_editor_action(self):
        before = self.frame(category="STRING_INPUT", actions=["QUIT", "NO", "CONFIRM"])
        skill = self.skill(before, view=self.view(before, kind="dismissal"),
            goal=dict(purpose="Cancel editor", label="Cancel", outcome="dismissed"))
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def test_namespaced_dismissal_requires_its_actual_registered_action(self):
        for category in ("UILIST", "WORLDGEN_CONFIRM_DIALOG"):
            with self.subTest(category=category):
                before = self.frame(category=category, actions=["QUIT", "TEXT.QUIT", "NO", "CONFIRM"])
                skill = self.skill(before, view=self.view(before, kind="dismissal"),
                    goal=dict(purpose="Close visible menu", label="Cancel", outcome="dismissed"))
                outcome = self.propose(skill)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def setUp(self):
        owned = Path(__file__).resolve().parents[1] / ".runtime" / "semantic-control-tests"
        owned.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=owned)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, self.root / "retained", max_frames=256)
        self.addCleanup(self.store.close)
        self.clocks = dict(now_monotonic=100.0, now_timestamp_ms=1_000_000)
        self.number = 0
        self.rows = [dict(label=str(n), enabled=True) for n in range(12)]

    def frame(self, *, category="MAIN_MENU", actions=None, change=None, same=None, normal=False):
        self.number += 1
        value = observation(self.number, session="world", timestamp_ms=self.clocks["now_timestamp_ms"])
        value["boundary"]["id"] = f"boundary-{self.number}"
        if not normal:
            value.update(category=category, scene=None, actions=actions or ["UP", "DOWN", "CONFIRM"])
            value["boundary"]["kind"] = "menu"
        if change:
            change(value)
        data = Path(same.frame_path).read_bytes() if same is not None else png(str(self.number).encode())
        (self.bridge / value["frame"]).write_bytes(data)
        return self.store.ingest(value, received_monotonic=self.clocks["now_monotonic"], **self.clocks)

    def view(self, before, *, kind="menu", **changes):
        value = dict(source_id=before.observation_id, basis="player_interpretation", kind=kind)
        if kind == "menu":
            value.update(control="vertical", rows=deepcopy(self.rows), selected=0, question="")
        elif kind == "editor":
            value.update(purpose="character_name", label="Name", visible_text="", whole_value=True, focused=True)
        else:
            value.update(question="Visible exact question?")
        return value | changes

    def request(self, before, *, skill_kind="menu", view=None, goal=None, **changes):
        return dict(schema=VERSION, kind="skill", request_id=f"request-{self.number}", mission_id="mission", epoch=0,
                    skill_kind=skill_kind, work_id=None, phase_id=None,
                    perception=self.view(before) if view is None and skill_kind == "menu" else view,
                    goal=goal or dict(purpose="Choose", label="3", outcome="activated"),
                    sources=[before.observation_id], expected_session=before.session, expected_revision=before.revision,
                    expected_boundary_id=self.store.observation(before)["boundary"]["id"],
                    limits=dict(primitives=32, wall_seconds=120, game_seconds=100)) | changes

    def propose(self, skill):
        return skill.propose(self.store, **self.clocks)

    def accept(self, skill, intent, after=None, *, disposition="returned", **changes):
        result = PrimitiveResult(intent.logical_id, intent.before, after, disposition, None, "actual diagnostic")
        return skill.accept(replace(result, **changes), self.store, **self.clocks)

    def skill(self, before=None, **changes):
        return SemanticControlSkill(self.request(self.frame() if before is None else before, **changes))

    def test_focus_batch_is_bounded_unverified_and_never_confirms(self):
        skill = self.skill(goal=dict(purpose="Choose", label="10", outcome="activated"))
        for step in range(8):
            intent = self.propose(skill)
            self.assertIsInstance(intent, ControlIntent)
            self.assertEqual((intent.kind, intent.action), ("action", "DOWN"))
            self.assertIs(self.propose(skill), intent)
            with self.assertRaises(FrozenInstanceError):
                intent.action = "CONFIRM"
            outcome = self.accept(skill, intent, self.frame())
            if step < 7:
                self.assertIsNone(outcome)
        self.assertEqual((outcome.disposition, outcome.proposed_count, outcome.basis), ("partial", 8, "player_interpretation"))
        self.assertTrue(outcome.verification_required)
        self.assertIs(self.propose(skill), outcome)
        self.assertEqual(len(outcome.evidence), 9)
        self.assertFalse(hasattr(outcome, "verified_focus_steps"))

    def test_world_form_has_no_tab_navigation_even_if_an_action_is_reported(self):
        before = self.frame(category="WORLDGEN_CONFIRM_DIALOG", actions=["PREV_TAB", "NEXT_TAB"])
        skill = self.skill(before, view=self.view(before, control="tabs"),
            goal=dict(purpose="Choose world form section", label="1", outcome="focused"))
        result = self.propose(skill)
        self.assertIsInstance(result, ControlOutcome)
        self.assertEqual((result.disposition, result.proposed_count), ("blocked", 0))

    def test_world_finish_remains_focusable_but_activation_requires_lifecycle(self):
        before = self.frame(category="WORLDGEN_CONFIRM_DIALOG", actions=["UP", "DOWN", "CONFIRM", "FINALIZE"])
        rows = [dict(label="World name", enabled=True), dict(label="Finish", enabled=True)]
        for label, selected, outcome, action in (("Finish", 0, "focused", "DOWN"),
                                               ("World name", 0, "activated", "CONFIRM"),
                                               ("Finish", 1, "activated", None)):
            with self.subTest(label=label, selected=selected, outcome=outcome):
                skill = self.skill(before, view=self.view(before, rows=rows, selected=selected),
                    goal=dict(purpose="World setup", label=label, outcome=outcome))
                result = self.propose(skill)
                if action is None:
                    self.assertEqual((result.disposition, result.proposed_count), ("blocked", 0))
                    self.assertIn("lifecycle create stage commit", result.reason)
                else:
                    self.assertIsInstance(result, ControlIntent)
                    self.assertEqual(result.action, action)

    def test_character_finish_cannot_be_proposed_as_tab_focus(self):
        before = self.frame(category="NEW_CHAR_DESCRIPTION", actions=["PREV_TAB", "NEXT_TAB"])
        skill = self.skill(before, view=self.view(before, control="tabs"),
            goal=dict(purpose="Choose next tab", label="1", outcome="focused"))
        result = self.propose(skill)
        self.assertIsInstance(result, ControlOutcome)
        self.assertEqual((result.disposition, result.proposed_count), ("blocked", 0))
        self.assertIn("lifecycle", result.reason)

    def test_character_description_can_return_to_a_previous_tab(self):
        before = self.frame(category="NEW_CHAR_DESCRIPTION", actions=["PREV_TAB", "NEXT_TAB"])
        skill = self.skill(before, view=self.view(before, control="tabs", selected=1),
            goal=dict(purpose="Return to previous tab", label="0", outcome="focused"))
        result = self.propose(skill)
        self.assertIsInstance(result, ControlIntent)
        self.assertEqual(result.action, "PREV_TAB")

    def test_enabled_represented_rows_determine_arrow_count_and_direction(self):
        for selected, label, action in ((0, "3", "DOWN"), (3, "0", "UP")):
            before = self.frame()
            view = self.view(before, selected=selected)
            view["rows"][1]["enabled"] = False
            skill = self.skill(before, view=view, goal=dict(purpose="Choose", label=label, outcome="focused"))
            for _ in range(2):
                intent = self.propose(skill)
                self.assertEqual(intent.action, action)
                outcome = self.accept(skill, intent, self.frame())
            self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 2))
            self.assertTrue(outcome.verification_required)

    def test_target_reached_by_batch_still_needs_fresh_interpretation(self):
        skill = self.skill()
        for _ in range(3):
            intent = self.propose(skill)
            outcome = self.accept(skill, intent, self.frame())
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 3))
        self.assertTrue(outcome.verification_required)
        self.assertIs(self.propose(skill), outcome)

    def test_initial_target_inspection_and_single_activation(self):
        for outcome in ("inspected", "focused", "activated"):
            skill = self.skill(goal=dict(purpose="Choose", label="0", outcome=outcome))
            result = self.propose(skill)
            if outcome == "activated":
                self.assertEqual(result.action, "CONFIRM")
                result = self.accept(skill, result, self.frame(normal=True))
                self.assertEqual(result.disposition, "partial")
                self.assertTrue(result.verification_required)
            elif outcome == "inspected":
                self.assertEqual((result.disposition, result.proposed_count), ("completed", 0))
                self.assertIn("interpretation", result.reason)
            else:
                self.assertEqual((result.disposition, result.proposed_count), ("partial", 0))
                self.assertTrue(result.verification_required)

    def test_exact_mappings_and_rejection_of_activation_or_unknown_categories(self):
        cases = [("UILIST", "vertical", "UILIST.UP", "UILIST.DOWN"),
                 ("INVENTORY", "vertical", "UP", "DOWN"),
                 ("MAIN_MENU", "horizontal", "LEFT", "RIGHT"),
                 ("MODMANAGER_DIALOG", "tabs", "PREV_TAB", "NEXT_TAB"),
                 ("NEW_CHAR_STATS", "tabs", "PREV_TAB", "NEXT_TAB"),
                 ("INVENTORY_SELECTOR", "columns", "PREV_COLUMN", "NEXT_COLUMN")]
        for category, control, up, down in cases:
            with self.subTest(category=category, control=control):
                before = self.frame(category=category, actions=[up, down, "CONFIRM"])
                view = self.view(before, control=control)
                skill = self.skill(before, view=view, goal=dict(purpose="Choose", label="1", outcome="focused"))
                self.assertEqual(self.propose(skill).action, down)
                if control != "vertical":
                    self.assertEqual(self.propose(self.skill(before, view=view)).disposition, "blocked")
        for category in ("SETTINGS", "OTHER", "YESNO", "DEFAULTMODE"):
            self.assertEqual(self.propose(self.skill(self.frame(category=category))).disposition, "blocked")

    def test_unrepresented_disabled_unknown_selection_and_missing_action_stop(self):
        for mode in ("missing", "disabled", "selection", "action"):
            before = self.frame(actions=["CONFIRM"] if mode == "action" else None)
            view = self.view(before)
            if mode == "disabled": view["rows"][3]["enabled"] = False
            if mode == "selection": view["selected"] = None
            goal = dict(purpose="Choose", label="absent" if mode == "missing" else "3", outcome="focused")
            self.assertEqual(self.propose(self.skill(before, view=view, goal=goal)).disposition, "blocked")

    def test_native_same_vertical_rows_must_agree_but_other_region_is_not_native(self):
        def native(value):
            value["ui"] = dict(purpose="uilist", title="", rows=[dict(id=f"row-{n}", text=str(n), enabled=True, hotkey=None)
                for n in range(12)], selected="row-0", filter=None, count=None, coverage="rendered_rows_only")
        before = self.frame(category="UILIST", actions=["UILIST.UP", "UILIST.DOWN", "CONFIRM"], change=native)
        for mode in ("label", "enabled", "order", "selection"):
            view = self.view(before)
            if mode == "label": view["rows"][1]["label"] = "different"
            if mode == "enabled": view["rows"][1]["enabled"] = False
            if mode == "order": view["rows"].reverse()
            if mode == "selection": view["selected"] = 1
            self.assertEqual(self.propose(self.skill(before, view=view)).disposition, "blocked")
        self.assertIsInstance(self.propose(self.skill(before)), ControlIntent)
        before = self.frame(category="MAIN_MENU", actions=["LEFT", "RIGHT"], change=native)
        skill = self.skill(before, view=self.view(before, control="horizontal"),
                           goal=dict(purpose="Tabs", label="1", outcome="focused"))
        self.assertEqual(self.propose(skill).action, "RIGHT")

    def test_native_inventory_vertical_rows_and_selection_cannot_be_overridden(self):
        def inventory(value):
            value["ui"] = dict(purpose="inventory", title="Inventory",
                rows=[dict(id=f"item-{n}", text=str(n), enabled=True, hotkey=None) for n in range(12)],
                selected="item-0", filter=None, count=None, coverage="rendered_rows_only")
        for category in ("INVENTORY", "INVENTORY_SELECTOR"):
            before = self.frame(category=category, actions=["UP", "DOWN", "PREV_COLUMN", "NEXT_COLUMN"],
                                change=inventory)
            for mode in ("label", "enabled", "order", "selection"):
                with self.subTest(category=category, contradiction=mode):
                    view = self.view(before)
                    if mode == "label": view["rows"][1]["label"] = "different"
                    if mode == "enabled": view["rows"][1]["enabled"] = False
                    if mode == "order": view["rows"].reverse()
                    if mode == "selection": view["selected"] = 1
                    result = self.propose(self.skill(before, view=view,
                        goal=dict(purpose="Inventory", label="3", outcome="focused")))
                    self.assertIsInstance(result, ControlOutcome)
                    self.assertEqual(result.disposition, "blocked")
                    self.assertEqual(result.proposed_count, 0)
            agreeing = self.skill(before, goal=dict(purpose="Inventory", label="3", outcome="focused"))
            self.assertEqual(self.propose(agreeing).action, "DOWN")
            column_view = self.view(before, control="columns", rows=[dict(label="left", enabled=True),
                                         dict(label="right", enabled=True)])
            columns = self.skill(before, view=column_view,
                goal=dict(purpose="Columns", label="right", outcome="focused"))
            self.assertEqual(self.propose(columns).action, "NEXT_COLUMN")

    def test_native_vertical_arrows_require_exact_next_enabled_selection(self):
        for category, purpose, actions in (("UILIST", "uilist", ["UILIST.UP", "UILIST.DOWN"]),
                                          ("INVENTORY", "inventory", ["UP", "DOWN"])):
            for mode in ("jump", "null", "disabled", "unchanged", "valid"):
                with self.subTest(category=category, after_selection=mode):
                    def native(value, selected):
                        rows = [dict(id=f"row-{n}", text=str(n), enabled=n != 1, hotkey=None) for n in range(12)]
                        value["ui"] = dict(purpose=purpose, title="", rows=rows,
                            selected=None if selected is None else f"row-{selected}",
                            filter=None, count=None, coverage="rendered_rows_only")
                    before = self.frame(category=category, actions=actions,
                                        change=lambda v: native(v, 0))
                    view = self.view(before)
                    view["rows"][1]["enabled"] = False
                    skill = self.skill(before, view=view, goal=dict(purpose="Choose", label="3", outcome="focused"))
                    intent = self.propose(skill)
                    selected = {"jump": 11, "null": None, "disabled": 1, "unchanged": 0, "valid": 2}[mode]
                    after = self.frame(category=category, actions=actions, change=lambda v: native(v, selected))
                    self.assertNotEqual(before.frame_sha256, after.frame_sha256)
                    outcome = self.accept(skill, intent, after)
                    if mode == "valid":
                        self.assertIsNone(outcome)
                        self.assertEqual(self.propose(skill).action, actions[1])
                    else:
                        self.assertIsInstance(outcome, ControlOutcome)
                        self.assertEqual(outcome.disposition, "unknown")
                        self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                        self.assertEqual(outcome.evidence[-1], after)
                        self.assertTrue(outcome.verification_required)
                        self.assertFalse(hasattr(outcome, "verified_focus_steps"))
                        self.assertIs(self.propose(skill), outcome)
                        self.assertIs(self.accept(skill, intent, after), outcome)

    def test_missing_or_corrupt_canonical_after_keeps_diagnostic_reference(self):
        for mode in ("missing", "corrupt", "forged"):
            with self.subTest(after_integrity=mode):
                skill = self.skill()
                intent = self.propose(skill)
                after = self.frame()
                supplied = after
                if mode == "missing": Path(after.frame_path).unlink()
                elif mode == "corrupt":
                    path = Path(after.frame_path)
                    path.chmod(0o644)
                    path.write_bytes(png(b"corrupted-after"))
                else: supplied = replace(after, frame_sha256="0" * 64)
                outcome = self.accept(skill, intent, supplied)
                self.assertEqual(outcome.disposition, "unknown")
                self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                self.assertIn("actual diagnostic", outcome.reason)
                if mode == "forged": self.assertNotIn(supplied, outcome.evidence)
                else: self.assertEqual(outcome.evidence[-1], after)
                self.assertIs(self.propose(skill), outcome)

    def test_scope_changes_stop_and_authority_failures_keep_pending(self):
        changes = {
            "category": lambda v: v.update(category="CRAFTING"),
            "actions": lambda v: v["actions"].append("OTHER"),
            "control": lambda v: v["boundary"].update(control_generation=1),
            "pause": lambda v: v.update(paused=True, pause_origin="host"),
            "takeover": lambda v: v.update(takeover_generation=1),
            "error": lambda v: v.update(error="native diagnostic"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                skill = self.skill()
                intent = self.propose(skill)
                after = self.frame(change=change)
                outcome = self.accept(skill, intent, after)
                self.assertIsInstance(outcome, ControlOutcome)
                self.assertIn(after, outcome.evidence)
                if name in ("control", "pause", "takeover", "error"):
                    self.assertEqual(outcome.disposition, "unknown")
                    self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                self.assertIs(self.propose(skill), outcome)

    def test_identical_png_focus_and_literal_stop_but_clear_can_be_identical(self):
        skill = self.skill()
        intent = self.propose(skill)
        result = self.accept(skill, intent, self.frame(same=intent.before))
        self.assertEqual(result.disposition, "partial")
        self.assertIn("progress", result.reason)
        skill = self.editor(text="AB")
        clear = self.propose(skill)
        self.assertEqual(clear.action, "TEXT.CLEAR")
        self.assertIsNone(self.accept(skill, clear, self.editor_frame(same=clear.before)))
        literal = self.propose(skill)
        self.assertEqual((literal.kind, literal.action), ("key", "A"))
        result = self.accept(skill, literal, self.editor_frame(same=literal.before))
        self.assertEqual((result.disposition, result.proposed_count), ("partial", 2))
        self.assertTrue(result.verification_required)

    def editor_frame(self, **changes):
        return self.frame(category="STRING_INPUT", actions=["TEXT.CLEAR", "TEXT.CONFIRM"], **changes)

    def editor(self, *, text="AB", visible="", commit=False, **view_changes):
        before = self.editor_frame()
        return self.skill(before, skill_kind="edit", view=self.view(before, kind="editor", visible_text=visible, **view_changes),
                          goal=dict(purpose="character_name", text=text, commit=commit))

    def test_known_empty_clear_literal_and_separate_fresh_commit(self):
        skill = self.editor(text="A b-1_")
        for expected in ["TEXT.CLEAR", *"A b-1_"]:
            intent = self.propose(skill)
            self.assertEqual(intent.action, expected)
            self.assertEqual(intent.kind, "action" if expected == "TEXT.CLEAR" else "key")
            outcome = self.accept(skill, intent, self.editor_frame())
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 7))
        self.assertTrue(outcome.verification_required)
        self.assertIs(self.propose(skill), outcome)
        blocked = self.propose(self.editor(text="AB", visible="A", commit=True))
        self.assertEqual(blocked.disposition, "blocked")
        commit = self.editor(text="AB", visible="AB", commit=True)
        intent = self.propose(commit)
        self.assertEqual(intent.action, "TEXT.CONFIRM")
        result = self.accept(commit, intent, self.frame(normal=True))
        self.assertEqual(result.disposition, "partial")
        self.assertTrue(result.verification_required)
        for changes in (dict(focused=False), dict(whole_value=False)):
            self.assertEqual(self.propose(self.editor(**changes)).disposition, "blocked")

    def test_direction_here_and_confirmation_are_one_registered_action(self):
        for kind, category, label, action in [("direction", "DEFAULTMODE", "Here", "pause"),
                ("direction", "DEFAULTMODE", "North", "UP"), ("confirmation", "YESNO", "No", "NO")]:
            before = self.frame(category=category, actions=[action])
            skill = self.skill(before, view=self.view(before, kind=kind),
                              goal=dict(purpose="Answer", label=label, outcome="activated"))
            intent = self.propose(skill)
            self.assertEqual(intent.action, action)
            result = self.accept(skill, intent, self.frame(normal=True))
            self.assertEqual(result.disposition, "partial")
            self.assertTrue(result.verification_required)

    def test_owned_distraction_confirmation_is_one_registered_answer_not_rest_success(self):
        for label, action, normal in (("Yes", "YES", True), ("No", "NO", False)):
            with self.subTest(label=label):
                before = self.frame(category="CANCEL_ACTIVITY_OR_IGNORE_QUERY",
                    actions=["YES", "NO", "MANAGER", "IGNORE", "LEFT", "RIGHT"])
                skill = self.skill(before,
                    view=self.view(before, kind="confirmation", question="Heard blam! Stop waiting?"),
                    goal=dict(purpose="Assess interrupted shelter wait", label=label, outcome="activated"))
                intent = self.propose(skill)
                self.assertIsInstance(intent, ControlIntent)
                self.assertEqual((intent.kind, intent.action), ("action", action))
                if normal:
                    after = self.frame(normal=True)
                else:
                    def polling(value):
                        value["actions"] = []
                        value["boundary"].update(kind="activity_poll", recovery_operations=["request_interrupt"])
                    after = self.frame(category="DEFAULTMODE", change=polling)
                outcome = self.accept(skill, intent, after)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
                self.assertTrue(outcome.verification_required)
                self.assertIs(self.propose(skill), outcome)

    def test_distraction_answer_requires_known_menu_category_and_selected_native_action(self):
        for category, actions, boundary in (("OTHER_QUERY", ["YES", "NO"], "menu"),
                ("CANCEL_ACTIVITY_OR_IGNORE_QUERY", ["NO"], "menu"),
                ("CANCEL_ACTIVITY_OR_IGNORE_QUERY", ["YES", "NO"], "unsupported"),
                ("YESNO", ["YES", "NO"], "interrupt_confirmation")):
            with self.subTest(category=category, actions=actions, boundary=boundary):
                def owned_boundary(value):
                    value["boundary"]["kind"] = boundary
                    if boundary == "interrupt_confirmation":
                        value.update(paused=True, pause_origin="host")
                        value["boundary"].update(recovery_operations=["answer_interrupt"],
                            interrupt_request_id="owned-interrupt")
                before = self.frame(category=category, actions=actions,
                    change=owned_boundary)
                skill = self.skill(before, view=self.view(before, kind="confirmation"),
                    goal=dict(purpose="Answer question", label="Yes", outcome="activated"))
                outcome = self.propose(skill)
                self.assertIsInstance(outcome, ControlOutcome)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def test_interact_uses_closed_registered_action_and_does_not_claim_effect(self):
        before = self.frame(normal=True, change=lambda v: v["actions"].append("examine"))
        request = self.request(before, skill_kind="interact", goal=dict(action="examine", intent="Look", desired_outcome="Know"))
        skill = SemanticControlSkill(request)
        intent = self.propose(skill)
        self.assertEqual((intent.action, intent.kind), ("examine", "action"))
        result = self.accept(skill, intent, self.frame(category="POPUP_WAIT"))
        self.assertEqual((result.disposition, result.basis), ("partial", "registered_action"))
        self.assertTrue(result.verification_required)
        self.assertNotIn("Know", result.reason)
        for normal in (False, True):
            unsupported = self.frame(normal=normal)
            blocked = self.skill(unsupported, skill_kind="interact", goal=dict(action="examine", intent="Look", desired_outcome="Know"))
            self.assertEqual(self.propose(blocked).disposition, "blocked")
        request["goal"]["action"] = "EXAMINE"
        with self.assertRaises(ContractError): SemanticControlSkill(request)

    def test_uncertain_or_bad_receipts_keep_pending_diagnostics_and_never_replay(self):
        for mode in ("unknown", "dispatched", "wrong_id", "wrong_before", "missing_after", "malformed", "extra", "lost"):
            with self.subTest(mode=mode):
                earlier = self.frame()
                skill = self.skill()
                intent = self.propose(skill)
                after = self.frame()
                result = PrimitiveResult(intent.logical_id, intent.before, after, "returned", None, "actual diagnostic")
                if mode in ("unknown", "dispatched"): result = replace(result, transport_disposition=mode)
                if mode == "wrong_id": result = replace(result, action_id="wrong")
                if mode == "wrong_before": result = replace(result, before=earlier)
                if mode == "missing_after": object.__setattr__(result, "after", None)
                if mode == "malformed": object.__setattr__(result, "observed_displacement", "invalid")
                if mode == "extra": self.frame()
                if mode == "lost": Path(intent.before.frame_path).unlink()
                outcome = skill.accept(result, self.store, **self.clocks)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("unknown", 1))
                self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                self.assertIn("actual diagnostic", outcome.reason)
                if mode not in ("missing_after",): self.assertIn(after, outcome.evidence)
                self.assertIs(self.propose(skill), outcome)
                self.assertIs(skill.accept(result, self.store, **self.clocks), outcome)

    def test_game_regression_and_nonadvancing_feedback_retain_pending(self):
        for mode in ("turn", "revision"):
            before = self.frame(normal=True, change=lambda v: v["actions"].append("examine"))
            skill = self.skill(before, skill_kind="interact", goal=dict(action="examine", intent="Look", desired_outcome="Know"))
            intent = self.propose(skill)
            def change(value):
                value["actions"].append("examine")
                if mode == "turn": value["scene"]["turn"] = 3
                else:
                    value["revision"] = before.revision
                    value["boundary"]["id"] = intent.expected_boundary_id
            after = self.frame(normal=True, change=change)
            outcome = self.accept(skill, intent, after)
            self.assertEqual(outcome.disposition, "unknown")
            self.assertEqual(outcome.pending_logical_id, intent.logical_id)
            self.assertIn(after, outcome.evidence)

    def test_edit_scope_changes_stop_and_one_effect_can_return_activity(self):
        skill = self.editor()
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, self.frame(category="OTHER"))
        self.assertEqual(outcome.disposition, "partial")
        self.assertTrue(outcome.verification_required)
        skill = self.skill(goal=dict(purpose="Choose", label="0", outcome="activated"))
        intent = self.propose(skill)
        after = self.frame(category="ACTIVITY", change=lambda v: v["boundary"].update(kind="activity_poll"))
        outcome = self.accept(skill, intent, after)
        self.assertEqual(outcome.disposition, "partial")
        self.assertIn(after, outcome.evidence)
        self.assertIsNone(after.turn)
        self.assertIsNone(outcome.pending_logical_id)

    def test_normal_interact_native_refresh_and_source_loss_after_progress(self):
        original = self.frame(normal=True, change=lambda v: v["actions"].append("examine"))
        skill = self.skill(original, skill_kind="interact", goal=dict(action="examine", intent="Look", desired_outcome="Know"))
        current = self.refresh(original)
        relation = self.relation(original, current, "native_state")
        skill.revalidate(relation, self.store, **self.clocks)
        intent = self.propose(skill)
        self.assertEqual(intent.before, current)
        self.assertIs(intent.revalidation, relation)
        skill = self.skill()
        first = self.propose(skill)
        self.assertIsNone(self.accept(skill, first, self.frame()))
        Path(first.before.frame_path).unlink()
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
        self.assertTrue(outcome.verification_required)
        self.assertIs(self.propose(skill), outcome)

    def test_known_non_delivery_and_budget_cap_are_terminal_without_rearming(self):
        for disposition in ("not_dispatched", "rejected"):
            skill = self.skill()
            intent = self.propose(skill)
            outcome = self.accept(skill, intent, disposition=disposition)
            self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 1))
            self.assertIsNone(outcome.pending_logical_id)
            self.assertIs(self.propose(skill), outcome)
        skill = self.skill(limits=dict(primitives=1, wall_seconds=120, game_seconds=100))
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, self.frame())
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
        self.assertTrue(outcome.verification_required)

    def refresh(self, original):
        value = self.store.observation(original)
        self.number += 1
        value.update(frame=f"frame-world-{self.number}.png", timestamp_ms=self.clocks["now_timestamp_ms"])
        (self.bridge / value["frame"]).write_bytes(Path(original.frame_path).read_bytes())
        return self.store.ingest(value, received_monotonic=self.clocks["now_monotonic"], **self.clocks)

    def relation(self, original, current, rule="exact_png_bytes"):
        generation = self.store.authority_generation()
        before = SourceBinding(original.observation_id, "mission", 0, "actor", "boot", 0, 0, generation - 1)
        return SourceRevalidation(before, replace(before, source_id=current.observation_id, store_generation=generation), rule)

    def test_one_explicit_refresh_retains_original_budget_and_view_binding(self):
        original = self.frame()
        request = self.request(original)
        skill = SemanticControlSkill(request)
        self.clocks = dict(now_monotonic=104.0, now_timestamp_ms=1_004_000)
        current = self.refresh(original)
        relation = self.relation(original, current)
        skill.revalidate(relation, self.store, **self.clocks)
        request["goal"]["label"] = "external mutation"
        intent = self.propose(skill)
        self.assertEqual(intent.before, current)
        self.assertIs(intent.revalidation, relation)
        self.assertEqual(skill._start, original)
        with self.assertRaises(ContractError): skill.revalidate(relation, self.store, **self.clocks)
        self.assertIsNone(self.accept(skill, intent, self.frame()))
        self.assertIsNone(self.propose(skill).revalidation)
        original = self.frame()
        skill = self.skill(original, limits=dict(primitives=32, wall_seconds=1, game_seconds=100))
        self.clocks = dict(now_monotonic=106.0, now_timestamp_ms=1_006_000)
        current = self.refresh(original)
        skill.revalidate(self.relation(original, current), self.store, **self.clocks)
        result = self.propose(skill)
        self.assertEqual((result.disposition, result.proposed_count), ("blocked", 0))
        self.assertEqual(result.evidence, (original, current))

    def test_refresh_wrong_rule_source_generation_or_implicit_promotion_rejects(self):
        for mode in ("rule", "source", "generation", "intervening", "implicit"):
            original = self.frame()
            skill = self.skill(original)
            current = self.refresh(original)
            relation = self.relation(original, current, "native_state" if mode == "rule" else "exact_png_bytes")
            if mode == "source": relation = replace(relation, original=replace(relation.original, source_id="wrong"))
            if mode == "generation":
                relation = replace(relation, original=replace(relation.original, store_generation=1000),
                                   current=replace(relation.current, store_generation=1001))
            if mode == "intervening": self.frame()
            if mode == "implicit": self.assertEqual(self.propose(skill).disposition, "blocked")
            else:
                with self.assertRaises((ContractError, EvidenceError)):
                    skill.revalidate(relation, self.store, **self.clocks)

    def test_initial_binding_freshness_integrity_and_extra_pending_promotion_stop(self):
        for mode in ("view", "revision", "boundary", "stale", "lost", "pending_promotion"):
            earlier = self.frame()
            before = self.frame()
            request = self.request(before)
            if mode == "view":
                request["sources"].append(earlier.observation_id)
                request["perception"]["source_id"] = earlier.observation_id
            if mode == "revision": request["expected_revision"] += 1
            if mode == "boundary": request["expected_boundary_id"] = "wrong"
            skill = SemanticControlSkill(request)
            pending = None
            if mode == "pending_promotion": pending = self.propose(skill); self.frame()
            if mode == "lost": Path(before.frame_path).unlink()
            if mode == "stale":
                self.clocks = dict(now_monotonic=self.clocks["now_monotonic"] + 4,
                                   now_timestamp_ms=self.clocks["now_timestamp_ms"] + 4000)
            outcome = self.propose(skill)
            self.assertEqual(outcome.disposition, "unknown" if pending else "blocked")
            self.assertIs(self.propose(skill), outcome)


if __name__ == "__main__":
    unittest.main()
