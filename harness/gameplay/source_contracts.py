"""Passive source identity and integrity failures, independent of a game schema."""
from typing import Protocol
from .contracts import ContractError


class EvidenceError(ContractError):
    """Evidence missing, inconsistent, stale, or unavailable; stop and re-observe."""


class FreshnessError(EvidenceError):
    """Original clock-check facts for audit; no source refresh or input authority."""

    def __init__(self, details: dict):
        super().__init__("Observation is stale or clock continuity is unknown")
        self.details = details


class CapacityError(EvidenceError):
    """Retention cannot be guaranteed before dispatch; nothing is deleted."""


class SourceReference(Protocol):
    observation_id: str
    session: str
    revision: int
    turn: int | None
    timestamp_ms: int
    received_monotonic: float
    frame_sha256: str
    boundary_kind: str

    def to_dict(self) -> dict: ...
