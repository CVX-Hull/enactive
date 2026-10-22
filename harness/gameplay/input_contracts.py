"""Passive input-policy records shared by ordinary input and optional shortcuts.

Policies cannot publish input or grant a lease. The mission writer owns delivery,
source validation, scope, budgets and durable receipt correlation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contracts import EvidenceRef
from .mission_contracts import InputObservation, SourceRevalidation


@dataclass(frozen=True)
class ControlIntent:
    logical_id: str
    kind: Literal["action", "key", "direct"]
    action: str | dict
    before: EvidenceRef
    expected_boundary_id: str
    revalidation: SourceRevalidation | None = None
    input_observation: InputObservation | None = None


@dataclass(frozen=True)
class ControlOutcome:
    disposition: Literal["completed", "partial", "blocked", "unknown"]
    reason: str
    proposed_count: int
    evidence: tuple[EvidenceRef, ...]
    pending_logical_id: str | None
    verification_required: bool
    basis: Literal["native_rows", "player_interpretation", "registered_action", "ordinary_input"]
    revalidation: SourceRevalidation | None = None
    input_observation: InputObservation | None = None
