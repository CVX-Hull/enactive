"""CDDA visible-scene projection into shared campaign-memory assertions."""
import hashlib
import math
from .contracts import ContractError, EvidenceRef, canonical, json_object
from .evidence import EvidenceStore
from .memory_contracts import MEMORY_VERSION, validate_scope
from .mission_contracts import validate_memory_entry
from .mission_ledger import MissionLedger


def _validate_wall(now: float) -> None:
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        raise ContractError("Memory requires finite nonnegative time")


def _identity(prefix: str, value: dict) -> str:
    return prefix + hashlib.sha256(canonical(value).encode()).hexdigest()


def capture_native(ledger: MissionLedger, store: EvidenceStore, reference: EvidenceRef, scope: dict, *, now: float) -> dict:
    """Literal scene values; host assertion receipt never borrows the native clock."""
    _validate_wall(now)
    scope = validate_scope(scope, mission_id=ledger.admission.mission_id)
    if reference.session != scope["session"]:
        raise ContractError("Native source differs from exact memory session")
    observation = store.observation(reference)
    entries = []
    existing = {row["entry"]["id"]: row["entry"] for row in ledger.memory_records("claim")}
    sequence = max((row["sequence"] for kind in ("claim", "work", "decision", "procedure")
                    for row in ledger.memory_records(kind)), default=0)
    for entry in project_native_claims(reference, scope, observation, received_time=int(now * 1000)):
        entry["received_time"] = existing.get(entry["id"], {}).get("received_time", entry["received_time"])
        sequence = max(sequence, ledger.append_memory(entry["id"], "claim", entry, now=now))
        entries.append(entry)
    return json_object({"memory_version": sequence, "entries": entries, "grants_authority": False})



def project_native_claims(reference: EvidenceRef, scope: dict, observation: dict, *, received_time: int) -> list[dict]:
    """Literal visible facts; caller owns source integrity and persistence."""
    scene = observation["scene"]
    entries = []
    if scene is not None:
        facts = [("player-position", "local-coordinate", {"quantity": None, "state": canonical({"position": scene["position"]})}),
                 ("observed-turn", "turn", {"quantity": None, "state": str(scene["turn"])}),
                 ("visible-creatures", "count", {"quantity": len(scene["visible_creatures"]), "state": None})]
        for subject, unit, value in facts:
            identity = _identity("native-", {"source": reference.observation_id, "scope": scope, "subject": subject})
            entry = validate_memory_entry({"schema": MEMORY_VERSION, "record_type": "Claim", "id": identity,
                "kind": "native_fact", "key": {"subject": subject, "property": "place", "unit": unit,
                    "coverage_id": "native-scene"}, "value": value, "text": subject,
                "scope": scope, "observed_time": {"revision": reference.revision, "turn": reference.turn},
                "received_time": received_time, "coverage": "literal player-visible scene fields",
                "sources": [reference.observation_id], "supports": [{"sources": [reference.observation_id], "claims": []}],
                "status": "current", "supersedes": []}, "claim")
            entries.append(entry)
    return entries
