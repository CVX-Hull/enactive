"""Passive data ports used by the memory reducer; no mission or game executor."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Protocol
from .contracts import ContractError
from .source_contracts import SourceReference


class MemoryRecordNotFound(ContractError):
    """The requested exact history record is absent, distinct from corrupt data."""


class MemoryLearning(Protocol):
    environment: Mapping | Sequence[tuple[str, object]]
    library_sources: Sequence[object]


class MemoryRepository(Protocol):
    mission_id: str
    learning: MemoryLearning | None

    def validate_application(self, request: dict) -> dict: ...
    def memory_records(self, entry_type: str) -> tuple[dict, ...]: ...
    def primitive_records(self) -> tuple[dict, ...]: ...
    def request(self, identity: str) -> dict: ...
    def append_memory(self, event_id: str, entry_type: str, entry: dict, *, now: float, candidate: bool = False) -> int: ...


class MemorySources(Protocol):
    @property
    def historical_references(self) -> tuple[SourceReference, ...]: ...
    def source_status(self, reference: SourceReference) -> str: ...
    def export_source(self, identity: str) -> tuple[dict, bytes]: ...
    def inspect_current(self, *, now_monotonic: float, now_timestamp_ms: int) -> tuple[SourceReference | None, bool]: ...


class ProcedureLibraryError(ContractError):
    """Historical support is unavailable or not an admitted sealed closure."""


class ProcedureEpisodeRefusal(ProcedureLibraryError):
    """An episode selects a mission/request/source outside the pinned support."""
