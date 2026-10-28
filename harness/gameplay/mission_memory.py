"""Mission admission/provenance adapter for the passive shared memory reducer."""
from .contracts import ContractError
from .mission_contracts import validate_request
from .mission_ledger import MissionLedger


class MissionMemory:
    def __init__(self, ledger: MissionLedger):
        self._ledger = ledger

    @property
    def mission_id(self):
        return self._ledger.admission.mission_id

    @property
    def learning(self):
        return self._ledger.admission.learning

    def validate_application(self, request: dict) -> dict:
        data = validate_request(request)
        if data["kind"] not in ("remember", "correct"):
            raise ContractError("Memory apply requires remember/correct")
        if self._ledger.request(data["request_id"])["request"] != data:
            raise ContractError("Memory request differs from its durable admitted payload")
        return data

    def memory_records(self, entry_type):
        return self._ledger.memory_records(entry_type)

    def primitive_records(self):
        return self._ledger.primitive_records()

    def request(self, identity):
        return self._ledger.request(identity)

    def append_memory(self, event_id, entry_type, entry, *, now, candidate=False):
        return self._ledger.append_memory(event_id, entry_type, entry, now=now, candidate=candidate)
