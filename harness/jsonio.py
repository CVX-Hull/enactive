"""Strict JSON decoding, canonical JSON dumps and streaming file SHA-256.

Neutral: standard library only, so the computer, player, evaluation and tools may all use it.
Each caller keeps its own error type by passing it to `strict_loads`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def strict_loads(data: str | bytes, error: type[Exception] = ValueError) -> Any:
    """Decode one JSON document. A duplicate object key or a non-finite number (`NaN`, `Infinity`)
    raises `error`; malformed syntax raises `json.JSONDecodeError`, a `ValueError`."""
    def pairs(items: list[tuple[str, Any]]) -> dict:
        found: dict[str, Any] = {}
        for key, value in items:
            if key in found:
                raise error(f'duplicate key {key!r}')
            found[key] = value
        return found

    def constant(name: str) -> Any:
        raise error(f'non-finite number {name}')

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def canonical(value: object, *, sort_keys: bool = False) -> str:
    """Compact UTF-8 JSON text without NaN or Infinity; keys keep insertion order unless `sort_keys`."""
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False, sort_keys=sort_keys)


def file_sha256(path: Path) -> str:
    """Hex SHA-256 of a file, read in chunks."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
