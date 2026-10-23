"""Historical creation input provenance, without source reads or live authority.

The caller must inspect retained observations to establish the creation form,
confirmation flow and its retirement. A correlated input chain alone establishes
neither those visible categories nor character identity or successful creation.
"""
from __future__ import annotations

from .contracts import ContractError, _ID, _INT, _object, _text, canonical, json_object, validate_json
from .mission_contracts import validate_request
from .native_input import validate_input
from .native_receipts import validate_ordinary_mapping

_CORRELATION = ("kind", "value", "expected_session", "expected_revision",
                "expected_boundary_id", "source_before", "preflight_source")
_CUSTODY = ("controller_boot_id", "operator_pause_generation", "takeover_generation", "actor_id", "epoch")
_BINDING = _object({"controller_boot_id": _ID, "operator_pause_generation": _INT,
    "takeover_generation": _INT, "actor_id": _ID, "epoch": _INT, "game_anchor_source_id": _ID})


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ContractError(reason)


def creation_input_chain(requests: tuple[dict, ...], primitives: tuple[dict, ...], *,
                         root_id: str, terminal_request_id: str,
                         terminal_logical_id: str) -> tuple[dict, ...]:
    """Return the raw ordered character-stage commit through named terminal input.

    Inputs are the MissionLedger's ordered copied projections. Later reconciliation
    or identity work is outside this slice. Known unpublished nondelivery is
    audited but omitted from the returned dispatches; it cannot advance chronology.
    No records are changed, sources loaded, observations promoted or inputs sent.
    """
    _require(type(requests) is tuple and type(primitives) is tuple,
             "Creation provenance requires ordered ledger projections")
    for identity in (root_id, terminal_request_id, terminal_logical_id):
        validate_json(identity, _ID)
    owners, order = {}, {}
    for index, row in enumerate(requests):
        _require(type(row) is dict and type(row.get("request")) is dict,
                 "Creation provenance lost a request projection")
        identity = row["request"].get("request_id")
        validate_json(identity, _ID)
        _require(identity not in owners, "Creation request order contains duplicate identities")
        owners[identity], order[identity] = row, index
    _require(root_id in owners and terminal_request_id in owners,
             "Creation provenance lacks its root or terminal owner")
    root = validate_request(owners[root_id]["request"])
    _require(root["kind"] == "lifecycle" and root.get("operation") == "create"
             and root.get("phase_id") is None and owners[root_id].get("epoch") == root["epoch"],
             "Creation provenance requires its original create root")
    positions = {}
    for index, primitive in enumerate(primitives):
        _require(type(primitive) is dict and type(primitive.get("intent")) is dict,
                 "Creation provenance lost a primitive projection")
        identity = primitive.get("logical_id")
        validate_json(identity, _ID)
        _require(identity not in positions, "Creation primitive order contains duplicate identities")
        positions[identity] = index
    _require(terminal_logical_id in positions, "Creation terminal primitive is missing")
    end = positions[terminal_logical_id]
    terminal = primitives[end]
    _require(terminal.get("request_id") == terminal_request_id
             and terminal.get("state") in ("returned", "unknown")
             and terminal["intent"].get("kind") in ("action", "direct"),
             "Creation terminal lost its exact native input owner or outcome")

    # A menu label or private phase flag cannot substitute for this charged
    # explicit lifecycle child. Unpublished nondelivery did not commit a stage;
    # authenticate the latest published returned candidate without fallback.
    start = None
    for index, primitive in enumerate(primitives[:end]):
        owner = owners.get(primitive.get("request_id"), {}).get("request", {})
        intent = primitive["intent"]
        if (owner.get("phase_id") == root_id and owner.get("kind") == "lifecycle"
                and owner.get("operation") == "create" and intent.get("kind") == "action"
                and intent.get("value") == "NEXT_TAB" and primitive.get("state") == "returned"
                and type(primitive.get("result")) is dict and primitive["result"].get("published") is True):
            start = index
    _require(start is not None, "Creation terminal has no earlier explicit character-stage commit")
    chain = primitives[start:end + 1]
    published = []
    custody = None
    previous_revision = None
    previous_owner = order[root_id]
    for offset, primitive in enumerate(chain):
        identity = primitive.get("request_id")
        _require(identity in owners, "Creation input has no retained request owner")
        row = owners[identity]
        owner = validate_request(row["request"])
        _require(owner.get("phase_id") == root_id and order[root_id] < order[identity]
                 and previous_owner <= order[identity] <= order[terminal_request_id]
                 and owner["mission_id"] == root["mission_id"]
                 and row.get("epoch") == owner["epoch"] == root["epoch"]
                 and owner.get("work_id") == root.get("work_id"),
                 "Creation input changed its original root, mission, epoch, Work or order")
        _require((owner["kind"] == "lifecycle" and owner["operation"] == "create"
                  and owner["world"] == root["world"] and owner["character"] == root["character"])
                 or (owner["kind"] == "skill" and owner["skill_kind"] in ("menu", "edit", "direct")),
                 "Creation chain requires same-root setup controls")
        intent, receipt, state = primitive["intent"], primitive.get("result"), primitive.get("state")
        nondelivery = offset > 0 and offset < len(chain) - 1 and state in ("rejected", "not_dispatched")
        _require(type(receipt) is dict and intent.get("kind") in (
                     ("action", "key", "direct", "resume") if nondelivery else ("action", "key", "direct"))
                 and owner.get("expected_session") == intent.get("expected_session") == root["expected_session"],
                 "Creation input lost its native control/session binding")
        _require((intent["kind"] == "direct") == (owner["kind"] == "skill" and owner["skill_kind"] == "direct"),
                 "Creation direct input requires its exact ordinary skill parent")
        for key in ("expected_session", "expected_boundary_id", "source_before", "preflight_source"):
            validate_json(intent.get(key), _ID)
        if intent["kind"] == "direct":
            validate_input(intent.get("value"))
        elif intent["kind"] == "resume":
            _require(intent.get("value") is None and owner["kind"] == "lifecycle",
                     "Creation nondelivery Resume lost its lifecycle parent")
        else:
            validate_json(intent.get("value"), _text(160))
        validate_json(intent.get("expected_revision"), _INT)
        _require(owner["expected_revision"] <= intent["expected_revision"]
                 and (previous_revision is None or intent["expected_revision"] >= previous_revision),
                 "Creation inputs regress their retained native revision order")
        _require(all(key in receipt and receipt[key] == intent.get(key) for key in _CORRELATION)
                 and receipt.get("logical_action_id") == primitive["logical_id"]
                 and receipt.get("transport_disposition") == state,
                 "Creation receipt contradicts its immutable input correlation")
        previous_owner = order[identity]
        if nondelivery:
            _require(receipt.get("published") is False and primitive.get("native_id") is None
                     and receipt.get("native_request_json") is None and receipt.get("native_ack") is None,
                     "Only known unpublished nondelivery can remain between creation inputs")
            continue
        _require(not offset or intent.get("value") not in ("FINALIZE", "NEXT_TAB"),
                 "Another creation stage reset intervened after the character commit")
        _require(state == "returned" or (offset == len(chain) - 1 and state == "unknown"),
                 "Creation chain contains unsettled or uncertain intermediation")
        native_id = primitive.get("native_id")
        validate_json(native_id, _ID)
        _require(receipt.get("published") is True and receipt.get("native_request_id") == native_id,
                 "Creation input lacks its exact published native receipt")
        validate_ordinary_mapping(intent, receipt, logical_id=primitive["logical_id"],
                                  native_id=native_id, disposition=state)
        encoded = receipt.get("native_request_json")
        _require(type(encoded) is str and len(encoded.encode()) <= 4096,
                 "Creation input lacks its retained native admission")
        native = json_object(encoded)
        binding = receipt.get("dispatch_binding")
        validate_json(binding, _BINDING)
        _require(canonical(native) == encoded and native.get("protocol") == 6
                 and all(native.get(key) == value for key, value in {
                     "id": native_id, "kind": intent["kind"], "session": intent["expected_session"],
                     "revision": intent["expected_revision"], "boundary_id": intent["expected_boundary_id"],
                     "takeover_generation": binding["takeover_generation"],
                     "input" if intent["kind"] == "direct" else intent["kind"]: intent["value"]}.items())
                 and type(native.get("authority")) is dict
                 and native["authority"].get("controller_boot_id") == binding["controller_boot_id"]
                 and binding["epoch"] == root["epoch"],
                 "Creation input changed its retained native admission or dispatch custody")
        current_custody = tuple(binding[key] for key in _CUSTODY)
        _require(custody is None or current_custody == custody,
                 "Creation chain changed its dispatch actor or native custody")
        custody = current_custody
        previous_revision = (receipt["native_ack"]["revision"] if state == "returned"
                             else intent["expected_revision"])
        published.append(primitive)
    return tuple(published)
