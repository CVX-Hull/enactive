"""Small deterministic helpers shared by the frozen memory-study suites."""
from __future__ import annotations

import hashlib
import json
import random


def json_bytes(value: object) -> int:
    """Count canonical UTF-8 JSON bytes, not Python heap size or model tokens."""
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8"))


def rng(seed: int, namespace: str) -> random.Random:
    """Give each suite/condition an isolated, stable pseudo-random stream."""
    digest = hashlib.sha256(f"{namespace}:{seed}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest, "big"))
