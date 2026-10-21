"""Pure item-selector policy tests; synthetic views establish no game outcome."""
from copy import deepcopy
import unittest

from harness.gameplay.evidence import EvidenceError
from harness.gameplay.interactions import check_visible_row_agreement, item_selection_plan


def row(label, *, enabled=True, available_quantity=10, quantity_unit="items", chosen_quantity=None):
    return dict(label=label, enabled=enabled, available_quantity=available_quantity,
                quantity_unit=quantity_unit, chosen_quantity=chosen_quantity)


def view(**changes):
    return dict(kind="item_selection", basis="player_interpretation", source_id="source",
                control="vertical", mode="multi", rows=[row("apple"), row("water")], selected=0,
                selection_coverage="all_selected", selected_items=[]) | changes


def goal(**changes):
    return dict(purpose="pickup", label="apple", quantity=2, quantity_unit="items",
                outcome="acquired", step="select") | changes


def state(**changes):
    return dict(category="INVENTORY_SELECTOR", boundary=dict(kind="menu"), ui=None,
                actions=["UP", "DOWN", "CONFIRM", "MARK_WITH_COUNT"]) | changes


def native_ui(rows, *, purpose="inventory", selected=0):
    return dict(purpose=purpose,
                rows=[dict(id=f"native-{n}", text=value["label"], enabled=value["enabled"])
                      for n, value in enumerate(rows)],
                selected=None if selected is None else f"native-{selected}")


class VisibleRowAgreementTests(unittest.TestCase):
    def test_menu_and_item_views_compare_only_labels_enabled_order_and_focus(self):
        item = view()
        menu = dict(kind="menu", control="vertical", selected=0,
                    rows=[dict(label=value["label"], enabled=value["enabled"]) for value in item["rows"]])
        for interpreted in (item, menu):
            for purpose in ("uilist", "inventory"):
                with self.subTest(kind=interpreted["kind"], purpose=purpose):
                    native = state(ui=native_ui(item["rows"], purpose=purpose))
                    self.assertIsNone(check_visible_row_agreement(interpreted, native))

    def test_native_label_enabled_order_and_selected_id_contradictions_stop(self):
        for contradiction in ("label", "enabled", "order", "focus", "count"):
            with self.subTest(contradiction=contradiction):
                interpreted = view()
                native = state(ui=native_ui(interpreted["rows"]))
                if contradiction == "label": native["ui"]["rows"][1]["text"] = "other"
                if contradiction == "enabled": native["ui"]["rows"][1]["enabled"] = False
                if contradiction == "order": native["ui"]["rows"].reverse()
                if contradiction == "focus": native["ui"]["selected"] = "native-1"
                if contradiction == "count": native["ui"]["rows"].pop()
                with self.assertRaises(EvidenceError):
                    check_visible_row_agreement(interpreted, native)

    def test_selected_native_id_maps_to_index_without_inventing_focus(self):
        interpreted = view(selected=None)
        native = state(ui=native_ui(interpreted["rows"], selected=None))
        self.assertIsNone(check_visible_row_agreement(interpreted, native))
        interpreted["selected"] = 0
        with self.assertRaises(EvidenceError):
            check_visible_row_agreement(interpreted, native)

    def test_other_axes_missing_ui_and_other_native_regions_confer_no_assertion(self):
        interpreted = view()
        disagreeing = native_ui([row("different")])
        for axis in ("horizontal", "tabs", "columns"):
            self.assertIsNone(check_visible_row_agreement(interpreted | dict(control=axis), state(ui=disagreeing)))
        self.assertIsNone(check_visible_row_agreement(interpreted, state()))
        disagreeing["purpose"] = "other"
        self.assertIsNone(check_visible_row_agreement(interpreted, state(ui=disagreeing)))

    def test_agreement_does_not_mutate_either_view(self):
        interpreted = view()
        native = state(ui=native_ui(interpreted["rows"]))
        before = deepcopy((interpreted, native))
        check_visible_row_agreement(interpreted, native)
        self.assertEqual((interpreted, native), before)


class ItemSelectionPlanTests(unittest.TestCase):
    def test_focus_counts_enabled_rows_in_both_directions_without_count_or_commit(self):
        rows = [row("apple"), row("disabled", enabled=False), row("water"), row("bread")]
        for selected, target, action in ((0, "bread", "DOWN"), (3, "apple", "UP")):
            with self.subTest(selected=selected):
                interpreted = view(rows=rows, selected=selected)
                self.assertEqual(item_selection_plan(goal(label=target), interpreted, state()),
                                 (("action", action), ("action", action)))

    def test_focus_batch_has_at_most_eight_arrows(self):
        interpreted = view(rows=[row(str(n)) for n in range(15)])
        self.assertEqual(item_selection_plan(goal(label="14"), interpreted, state()),
                         (("action", "DOWN"),) * 8)

    def test_each_inventory_category_uses_registered_vertical_actions(self):
        for category in ("INVENTORY", "INVENTORY_SELECTOR"):
            self.assertEqual(item_selection_plan(goal(label="water"), view(), state(category=category)),
                             (("action", "DOWN"),))

    def test_native_contradictions_block_focus_count_and_commit(self):
        for step, selected in (("select", 1), ("select", 0), ("commit", 0)):
            with self.subTest(step=step, selected=selected):
                interpreted = self.committable() | dict(selected=selected)
                native = state(ui=native_ui(interpreted["rows"], selected=selected))
                native["ui"]["rows"][0]["text"] = "not apple"
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(step=step), interpreted, native)

    def test_absent_disabled_and_duplicate_target_labels_stop(self):
        for rows in ([row("water")], [row("apple", enabled=False)],
                     [row("apple"), row("apple")], [row("apple"), row("apple", enabled=False)]):
            with self.subTest(rows=rows):
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(), view(rows=rows), state())

    def test_unknown_disabled_or_unrepresented_current_selection_stops(self):
        for selected, rows in ((None, [row("apple")]), (2, [row("apple")]),
                               (-1, [row("apple")]), (0, [row("water", enabled=False), row("apple")])):
            with self.subTest(selected=selected):
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(), view(rows=rows, selected=selected), state())

    def test_units_are_explicit_and_never_converted(self):
        for unit, available in (("items", 10), ("charges", 10)):
            with self.subTest(unit=unit):
                interpreted = view(rows=[row("apple", quantity_unit=unit, available_quantity=available)])
                self.assertEqual(item_selection_plan(goal(quantity_unit=unit), interpreted, state()),
                                 (("action", "MARK_WITH_COUNT"),))
                other = "items" if unit == "charges" else "charges"
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(quantity_unit=other), interpreted, state())

    def test_known_insufficient_availability_blocks_even_before_focus(self):
        for selected in (0, 1):
            with self.subTest(selected=selected):
                interpreted = view(rows=[row("apple", available_quantity=1), row("water")], selected=selected)
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(quantity=2), interpreted, state())

    def test_unknown_availability_stays_unknown_and_equal_availability_suffices(self):
        for available in (None, 2):
            with self.subTest(available=available):
                interpreted = view(rows=[row("apple", available_quantity=available)])
                original = deepcopy(interpreted)
                self.assertEqual(item_selection_plan(goal(), interpreted, state()), (("action", "MARK_WITH_COUNT"),))
                self.assertEqual(interpreted, original)

    def test_multi_select_proposes_one_count_editor_for_pickup_drop_store(self):
        for purpose, outcome in (("pickup", "acquired"), ("drop", "dropped"), ("store", "stored")):
            for chosen in (None, 0, 1, 3):
                with self.subTest(purpose=purpose, chosen=chosen):
                    interpreted = view(rows=[row("apple", chosen_quantity=chosen)])
                    self.assertEqual(item_selection_plan(goal(purpose=purpose, outcome=outcome), interpreted, state()),
                                     (("action", "MARK_WITH_COUNT"),))

    def test_exact_multi_quantity_returns_empty_plan_requiring_explicit_commit(self):
        interpreted = view(rows=[row("apple", chosen_quantity=2)], selection_coverage="visible_only")
        self.assertEqual(item_selection_plan(goal(), interpreted, state(actions=[])), ())

    def test_single_consume_quantity_one_proposes_only_confirm(self):
        for unit in ("items", "charges"):
            interpreted = view(mode="single", rows=[row("apple", quantity_unit=unit)])
            request = goal(purpose="consume", outcome="consumed", quantity=1, quantity_unit=unit)
            self.assertEqual(item_selection_plan(request, interpreted, state()), (("action", "CONFIRM"),))

    def test_single_consume_multiple_quantity_refused_before_any_input(self):
        for selected in (0, 1):
            with self.subTest(selected=selected):
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(purpose="consume", outcome="consumed", quantity=2),
                                        view(mode="single", selected=selected), state())

    def committable(self, *, unit="items"):
        return view(rows=[row("apple", quantity_unit=unit, chosen_quantity=2), row("water")],
                    selected_items=[dict(label="apple", quantity=2, quantity_unit=unit)])

    def test_commit_requires_exact_complete_selection_and_returns_one_confirm(self):
        for unit in ("items", "charges"):
            self.assertEqual(item_selection_plan(goal(step="commit", quantity_unit=unit),
                                                self.committable(unit=unit), state()), (("action", "CONFIRM"),))

    def test_commit_rejects_extra_missing_wrong_or_partial_selection(self):
        changes = [dict(selection_coverage="visible_only"), dict(selection_coverage="unknown"),
                   dict(selected=1), dict(selected_items=[]),
                   dict(selected_items=[dict(label="apple", quantity=2, quantity_unit="items"),
                                        dict(label="water", quantity=1, quantity_unit="items")]),
                   dict(selected_items=[dict(label="water", quantity=2, quantity_unit="items")]),
                   dict(selected_items=[dict(label="apple", quantity=1, quantity_unit="items")]),
                   dict(selected_items=[dict(label="apple", quantity=2, quantity_unit="charges")])]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(step="commit"), self.committable() | change, state())
        for quantity in (None, 0, 1, 3):
            interpreted = self.committable()
            interpreted["rows"][0]["chosen_quantity"] = quantity
            with self.subTest(chosen=quantity):
                with self.assertRaises(EvidenceError):
                    item_selection_plan(goal(step="commit"), interpreted, state())

    def test_each_proposal_requires_its_exact_current_registered_action(self):
        cases = [(goal(label="water"), view(), "DOWN"),
                 (goal(label="apple"), view(selected=1), "UP"),
                 (goal(), view(), "MARK_WITH_COUNT"),
                 (goal(step="commit"), self.committable(), "CONFIRM")]
        for request, interpreted, action in cases:
            with self.subTest(action=action):
                self.assertEqual(item_selection_plan(request, interpreted, state(actions=[action])), (("action", action),))
                with self.assertRaises(EvidenceError):
                    item_selection_plan(request, interpreted, state(actions=["OTHER", "QUIT"]))

    def test_commit_rejects_visible_extra_count_even_when_summary_omits_it(self):
        interpreted = self.committable()
        interpreted["rows"][1]["chosen_quantity"] = 1
        with self.assertRaises(EvidenceError):
            item_selection_plan(goal(step="commit"), interpreted, state())

    def test_unsupported_modes_purposes_steps_categories_and_boundary_stop(self):
        cases = [(goal(purpose="wear"), view(), state()),
                 (goal(step="start"), view(), state()),
                 (goal(), view(mode="unknown"), state()),
                 (goal(), view(mode="single"), state()),
                 (goal(purpose="consume", outcome="consumed", quantity=1), view(), state()),
                 (goal(purpose="consume", outcome="consumed", quantity=1, step="commit"), view(mode="single"), state()),
                 (goal(), view(control="columns"), state()),
                 (goal(), view(kind="menu"), state()),
                 (goal(), view(), state(category="UILIST")),
                 (goal(), view(), state(boundary=dict(kind="normal_play")))]
        for request, interpreted, native in cases:
            with self.subTest(request=request, view=interpreted, state=native):
                with self.assertRaises(EvidenceError):
                    item_selection_plan(request, interpreted, native)

    def test_successful_and_blocked_plans_do_not_mutate_inputs(self):
        for step in ("select", "commit"):
            request, interpreted, native = goal(step=step), self.committable(), state()
            original = deepcopy((request, interpreted, native))
            result = item_selection_plan(request, interpreted, native)
            self.assertIsInstance(result, tuple)
            self.assertEqual((request, interpreted, native), original)
            native["actions"] = []
            if step == "commit":
                original = deepcopy((request, interpreted, native))
                with self.assertRaises(EvidenceError):
                    item_selection_plan(request, interpreted, native)
                self.assertEqual((request, interpreted, native), original)


if __name__ == "__main__":
    unittest.main()
