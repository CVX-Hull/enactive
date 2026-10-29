"""Small mechanical protocol; no game observations, goals or eligibility rules."""
from __future__ import annotations

from typing import Any

from collections.abc import Iterable
import json
import math
from pathlib import Path
import re

SCHEMA = "computer-request/1"
MAX_FRAME_BYTES = 64 * 1024 * 1024
GEOMETRY_KEYS = {"width", "height", "window_width", "window_height", "viewport"}


class ControlError(ValueError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def read_json(path: Path, maximum: int = 65536) -> Any:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ControlError("Missing or invalid bounded regular artifact")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ControlError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ControlError("Nonfinite JSON")))


def closed(value: object, keys: Iterable[str]) -> None:
    if type(value) is not dict or set(value) != set(keys):
        raise ControlError("Invalid mechanical object fields")


def integer(value: object, low: int, high: int) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ControlError("Integer outside mechanical bound")


def geometry(value: object) -> dict[str, Any]:
    closed(value, GEOMETRY_KEYS)
    for field in GEOMETRY_KEYS - {"viewport"}:
        integer(value[field], 1, 16384)
    v = value["viewport"]
    if type(v) is not list or len(v) != 4:
        raise ControlError("Invalid viewport")
    for n in v:
        integer(n, 0, 16384)
    if v[2] < 1 or v[3] < 1 or v[0] + v[2] > value["width"] or v[1] + v[3] > value["height"]:
        raise ControlError("Viewport exceeds captured output")
    return value


def validate_input(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise ControlError("Input must be an object")
    kind = value.get("type")
    if kind == "key":
        closed(value, {"type", "key", "modifiers"})
        key = value["key"]
        if not isinstance(key, str) or not (len(key) == 1 and 32 <= ord(key) <= 126 or key in {
            "ENTER", "ESC", "UP", "DOWN", "LEFT", "RIGHT", "TAB", "BACKSPACE", "SPACE", "PAGEUP", "PAGEDOWN", "HOME", "END", "DELETE"}):
            raise ControlError("Unsupported basic key")
        mods = value["modifiers"]
        if type(mods) is not list or len(mods) != len(set(mods)) or any(x not in ("CTRL", "ALT", "SHIFT") for x in mods):
            raise ControlError("Invalid modifiers")
    elif kind == "text":
        closed(value, {"type", "text"})
        text = value["text"]
        if not isinstance(text, str) or not text or len(text.encode("utf-8")) > 31 or any(ord(c) < 32 or ord(c) == 127 for c in text):
            raise ControlError("Text must be 1..31 UTF8 bytes without controls")
    elif kind == "click":
        closed(value, {"type", "x", "y", "button", "geometry"})
        geometry(value["geometry"])
        integer(value["x"], 0, value["geometry"]["width"] - 1)
        integer(value["y"], 0, value["geometry"]["height"] - 1)
        if value["button"] not in ("left", "right"):
            raise ControlError("Unsupported pointer button")
    else:
        raise ControlError("Unknown basic input")
    return value


def frame(value: object) -> dict[str, Any]:
    closed(value, {"name", "capture_id", "presented_ms", *GEOMETRY_KEYS})
    if not isinstance(value["name"], str) or re.fullmatch(r"frame-[1-9][0-9]*\.png", value["name"]) is None:
        raise ControlError("Invalid frame basename")
    integer(value["capture_id"], 1, 2**53 - 1)
    integer(value["presented_ms"], 1, 2**53 - 1)
    geometry({k: value[k] for k in GEOMETRY_KEYS})
    return value


def state(value: object, *, session: str, pid: int) -> dict[str, Any]:
    closed(value, {"schema", "session", "pid", "window_id", "paused", "takeover_generation", "latest_frame", "error"})
    if value["schema"] != "computer-target/1" or value["session"] != session or value["pid"] != pid:
        raise ControlError("Target/session identity differs")
    integer(value["window_id"], 0, 2**32 - 1)
    integer(value["takeover_generation"], 0, 2**53 - 1)
    if type(value["paused"]) is not bool or not isinstance(value["error"], str):
        raise ControlError("Invalid target health")
    if value["latest_frame"] is not None:
        frame(value["latest_frame"])
    return value


def receipt(value: object, *, identity: str, session: str) -> dict[str, Any]:
    closed(value, {"schema", "id", "session", "disposition", "emitted_events", "reason", "frame"})
    if value["schema"] != "computer-receipt/1" or value["id"] != identity or value["session"] != session:
        raise ControlError("Receipt identity differs")
    if value["disposition"] not in ("delivered", "rejected", "partial", "unknown"):
        raise ControlError("Invalid delivery disposition")
    integer(value["emitted_events"], 0, 8)
    if value["disposition"] == "rejected" and value["emitted_events"] != 0:
        raise ControlError("Emitted input cannot be rejected as undelivered")
    if not isinstance(value["reason"], str):
        raise ControlError("Invalid receipt reason")
    if value["frame"] is not None:
        frame(value["frame"])
    return value


def finite_seconds(value: object, maximum: float) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ControlError("Invalid bounded wait")
    return value
