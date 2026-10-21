"""Pure plans over fallible visible item interpretations, without input authority.

The caller validates the current schema and source binding, observes every
proposal and requires fresh interpretation after focus prediction. Selection or
confirmation never establishes the requested game outcome.
"""
from __future__ import annotations

from .evidence import EvidenceError


def check_visible_row_agreement(view: dict, state: dict) -> None:
    """Reject contradictions with native rows for the same vertical control.

    Native rows attest only rendered labels, enabled flags, order and selection.
    Item quantities remain player interpretation, without native confirmation.
    """
    ui = state["ui"]
    if view["control"] != "vertical" or ui is None or ui["purpose"] not in ("uilist", "inventory"):
        return
    native_rows = [(row["text"], row["enabled"]) for row in ui["rows"]]
    interpreted_rows = [(row["label"], row["enabled"]) for row in view["rows"]]
    selected = next((n for n, row in enumerate(ui["rows"]) if row["id"] == ui["selected"]), None)
    if (native_rows, selected) != (interpreted_rows, view["selected"]):
        raise EvidenceError("Player interpretation conflicts with native rendered rows/order/selection")


def item_selection_plan(goal: dict, view: dict, state: dict) -> tuple[tuple[str, str], ...]:
    """Propose bounded focus, one count editor or one explicit confirmation.

    Schema parsing, retained evidence, action feedback and mission accounting
    stay with SemanticControlSkill and its caller. Unknown available quantities
    stay unknown; this policy never infers inventory contents or converts units.
    """
    if state["boundary"]["kind"] != "menu" or state["category"] not in ("INVENTORY", "INVENTORY_SELECTOR"):
        raise EvidenceError("Item selection requires an inventory menu boundary")
    if view["kind"] != "item_selection" or view["control"] != "vertical":
        raise EvidenceError("Item selection requires a vertical item interpretation")
    mode, purpose, step = view["mode"], goal["purpose"], goal["step"]
    if step not in ("select", "commit"):
        raise EvidenceError("Unsupported item selection step")
    if mode == "single":
        if purpose != "consume" or goal["quantity"] != 1 or step != "select":
            raise EvidenceError("Single selection supports only consume quantity one at the select step")
    elif mode == "multi":
        if purpose not in ("pickup", "drop", "store"):
            raise EvidenceError("Multi selection supports only pickup, drop or store")
    else:
        raise EvidenceError("Unsupported item selection mode")

    rows, selected = view["rows"], view["selected"]
    targets = [n for n, row in enumerate(rows) if row["label"] == goal["label"]]
    if (len(targets) != 1 or not rows[targets[0]]["enabled"]
            or type(selected) is not int or not 0 <= selected < len(rows) or not rows[selected]["enabled"]):
        raise EvidenceError("Exact distinct represented enabled target and known enabled selection are required")
    target = targets[0]
    item = rows[target]
    if item["quantity_unit"] != goal["quantity_unit"]:
        raise EvidenceError("Item quantity unit must exactly match the requested unit")
    if item["available_quantity"] is not None and item["available_quantity"] < goal["quantity"]:
        raise EvidenceError("Known available item quantity is less than requested")
    check_visible_row_agreement(view, state)

    if step == "commit":
        expected = dict(label=goal["label"], quantity=goal["quantity"], quantity_unit=goal["quantity_unit"])
        if (selected != target or item["chosen_quantity"] != goal["quantity"]
                or view["selection_coverage"] != "all_selected" or view["selected_items"] != [expected]
                or any(n != target and row["chosen_quantity"] is not None and row["chosen_quantity"] > 0
                       for n, row in enumerate(rows))):
            raise EvidenceError("Commit requires the selected target and exact complete item selection/count/unit")
        plan = (("action", "CONFIRM"),)
    elif selected != target:
        direction = 1 if target > selected else -1
        steps = sum(rows[n]["enabled"] for n in range(selected + direction, target + direction, direction))
        # Each arrow is observed by the existing skill. The predicted batch
        # requires a new interpretation before any count edit or confirmation.
        plan = (("action", "DOWN" if direction > 0 else "UP"),) * min(steps, 8)
    elif mode == "single":
        plan = (("action", "CONFIRM"),)
    elif item["chosen_quantity"] != goal["quantity"]:
        plan = (("action", "MARK_WITH_COUNT"),)
    else:
        # An exact marked count still requires a separate fresh commit request.
        plan = ()
    if any(action not in state["actions"] for _, action in plan):
        raise EvidenceError("Required item control action is not registered in current evidence")
    return plan
