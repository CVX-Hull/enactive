"""Typed mechanical callbacks consumed by optional player programs.

This module defines no dispatcher, game interpretation or implementation owner.
"""
from __future__ import annotations

from typing import Any, Protocol


class ComputerPort(Protocol):
    def observe(self, actor_id: str, *, deadline_monotonic: float | None = None
                ) -> tuple[dict[str, Any], bytes | None]: ...

    def input(self, actor_id: str, actions: list[dict[str, Any]], *,
              source_id: str | None = None, deadline_monotonic: float | None = None
              ) -> tuple[dict[str, Any], bytes | None]: ...
