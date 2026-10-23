"""Model presentation only; canonical player results and handles stay complete."""
from __future__ import annotations

from copy import deepcopy

from .gameplay.contracts import canonical
from .player_tools import DETAIL_SECTIONS


PRESENTATION_SCHEMA = "player-view/2"

_REFERENCE_FIELDS = ("schema", "record_type", "frame_path", "frame_sha256",
                     "received_monotonic", "visibility_version")
_RECEIPT_DETAIL_FIELDS = ("native_request_json", "native_ack", "dispatch_binding",
                          "source_before", "preflight_source", "source_after",
                          "expected_session", "expected_revision", "expected_boundary_id",
                          "received_monotonic")


def _omit(value: dict | None, fields: tuple[str, ...]) -> None:
    if isinstance(value, dict):
        for field in fields:
            value.pop(field, None)

# These PlayerTools paths return _finish's operation envelope. Sources and
# advisory payloads are opaque evidence, even if they contain similar names.
_NEXT_SNAPSHOT_TOOLS = frozenset({
    "enactive_start", "enactive_result", "enactive_skill", "enactive_lifecycle",
    "enactive_observe", "enactive_remember", "enactive_correct", "enactive_handoff",
    "enactive_stop", "enactive_reconcile", "enactive_claim", "enactive_readmit",
    "enactive_context",
})


def _project_snapshot(snapshot: dict, operation: dict | None = None, operation_id: str | None = None) -> None:
    if snapshot.get("snapshot_id") is not None:
        snapshot["detail_sections"] = list(DETAIL_SECTIONS)
    mission = snapshot.get("mission")
    if mission is not None:
        # The exact frozen configuration is already addressable by detail.
        _omit(mission, ("configuration",))
        metrics = mission.get("metrics")
        if isinstance(metrics, dict):
            mission["metrics"] = {key: metrics[key] for key in ("game_seconds", "primitives") if key in metrics}
        _omit(mission.get("current_source"), _REFERENCE_FIELDS)
        process = mission.get("native_process")
        if isinstance(process, dict):
            _omit(process.get("last_sample"), ("pid", "launch_id"))
        result = operation.get("result") if operation is not None else None
        # Standalone status and a different/pending operation can carry unique
        # progress. Canonical JSON equality also distinguishes true from 1.
        if operation_id is not None and result is not None and canonical({"result": result}) == canonical({"result": mission.get("progress")}):
            mission.pop("progress")
            mission["progress_operation_id"] = operation_id
        receipt = mission.get("last_receipt")
        if receipt is not None:
            # Retain delivery, errors, correlation and unique feedback; only
            # known technical binding/evidence fields move behind exact detail.
            _omit(receipt, _RECEIPT_DETAIL_FIELDS)
            _omit(receipt.get("control"), ("request",))
    native = snapshot.get("native")
    state = native.get("state") if native is not None else None
    source = snapshot.get("source")
    observed = source.get("observation") if source is not None else None
    if source is not None:
        _omit(source.get("reference"), _REFERENCE_FIELDS)
    _omit(state, ("protocol", "id", "frame"))
    _omit(observed, ("protocol", "id", "frame"))
    if state is not None and observed is not None and all(
        name in state and name in observed
        and canonical({"value": state[name]}) == canonical({"value": observed[name]})
        for name in ("actions", "scene", "ui")
    ):
        # Only deduplicate an actually returned, matching visible view. Missing
        # source bytes or a newer native scene must retain their own information.
        for name in ("actions", "scene", "ui"):
            state.pop(name, None)
    for visible in (state, observed):
        # DEFAULTMODE can also be a directional menu. Only a normal in-game
        # boundary without represented UI carries the general engine vocabulary.
        if (visible is not None and visible.get("category") == "DEFAULTMODE"
                and visible.get("in_game") is True and visible.get("ui") is None
                and (visible.get("boundary") or {}).get("kind") == "normal_play"):
            _omit(visible, ("actions",))


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
