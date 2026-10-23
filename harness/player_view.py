"""Model presentation only; canonical player results and handles stay complete."""
from __future__ import annotations

from copy import deepcopy

from .gameplay.contracts import canonical


PRESENTATION_SCHEMA = "player-view/1"

# These PlayerTools paths return _finish's operation envelope. Sources and
# advisory payloads are opaque evidence, even if they contain similar names.
_NEXT_SNAPSHOT_TOOLS = frozenset({
    "enactive_start", "enactive_result", "enactive_skill", "enactive_lifecycle",
    "enactive_observe", "enactive_remember", "enactive_correct", "enactive_handoff",
    "enactive_stop", "enactive_reconcile", "enactive_claim", "enactive_readmit",
    "enactive_context",
})


def _project_snapshot(snapshot: dict, operation: dict | None = None, operation_id: str | None = None) -> None:
    mission = snapshot.get("mission")
    if mission is not None:
        result = operation.get("result") if operation is not None else None
        # Standalone status and a different/pending operation can carry unique
        # progress. Canonical JSON equality also distinguishes true from 1.
        if operation_id is not None and result is not None and canonical({"result": result}) == canonical({"result": mission.get("progress")}):
            mission.pop("progress")
            mission["progress_operation_id"] = operation_id
        receipt = mission.get("last_receipt")
        if receipt is not None:
            receipt.pop("native_request_json", None)
            receipt.pop("native_ack", None)
    native = snapshot.get("native")
    state = native.get("state") if native is not None else None
    source = snapshot.get("source")
    observed = source.get("observation") if source is not None else None
    if state is not None and observed is not None and all(
        name in state and name in observed
        and canonical({"value": state[name]}) == canonical({"value": observed[name]})
        for name in ("actions", "scene", "ui")
    ):
        # Only deduplicate an actually returned, matching visible view. Missing
        # source bytes or a newer native scene must retain their own information.
        for name in ("actions", "scene", "ui"):
            state.pop(name, None)


def decision_view(tool_name: str, value: dict) -> dict:
    """Copy a successful tool result and project only its explicit snapshot slot."""
    view = deepcopy(value)
    if tool_name == "enactive_snapshot":
        _project_snapshot(view)
    elif tool_name in _NEXT_SNAPSHOT_TOOLS and "next_snapshot" in view:
        response = view.get("response")
        operation = response.get("operation") if response is not None else None
        _project_snapshot(view["next_snapshot"], operation, view.get("operation_id"))
    view["presentation_schema"] = PRESENTATION_SCHEMA
    return view
