"""Current visible geometry and direct-input data; no input or source authority."""
from __future__ import annotations

from .contracts import (
    ContractError, _array, _enum, _integer, _object, _text, json_object, validate_json,
)

_DIMENSION = _integer(16_384, 1)
_GEOMETRY = _object({
    "window_width": _DIMENSION, "window_height": _DIMENSION,
    "output_width": _DIMENSION, "output_height": _DIMENSION,
    "viewport": {**_array(_integer(16_384), 4, 4)},
})
_NAMED_KEYS = ("ENTER", "ESC", "UP", "DOWN", "LEFT", "RIGHT", "TAB", "BACKSPACE",
               "SPACE", "PAGEUP", "PAGEDOWN")
_KEY = _object({
    "type": {"const": "key"},
    "key": {"anyOf": [_enum(*_NAMED_KEYS), {**_text(1), "pattern": "^[ -~]$"}]},
    "modifiers": {**_array(_enum("CTRL", "ALT", "SHIFT"), 3), "uniqueItems": True},
})
_CLICK = _object({"type": {"const": "click"}, "button": _enum("left", "right"),
                  "x": _integer(16_383), "y": _integer(16_383), "geometry": _GEOMETRY})


def geometry_schema() -> dict:
    return json_object(_GEOMETRY)


def validate_geometry(value: dict) -> dict:
    data = json_object(value)
    validate_json(data, _GEOMETRY)
    x, y, width, height = data["viewport"]
    if (not width or not height or x + width > data["output_width"]
            or y + height > data["output_height"]
            or data["output_width"] * data["output_height"] > 16_777_216):
        raise ContractError("Viewport or pixel allocation exceeds the attested output")
    return data


def input_schema(*, text_limit: int = 1) -> dict:
    if type(text_limit) is not int or not 1 <= text_limit <= 24:
        raise ContractError("Direct text limit must be within one bounded operation")
    return json_object({"anyOf": [_KEY, _object({"type": {"const": "text"},
                        "text": _text(text_limit)}), _CLICK]})


def validate_input(value: dict, *, text_limit: int = 1) -> dict:
    data = json_object(value)
    validate_json(data, input_schema(text_limit=text_limit))
    if data["type"] == "text":
        if not data["text"].isprintable() or any(ord(char) > 0xFFFF for char in data["text"]):
            raise ContractError("Direct text requires printable scalars supported by the pinned 16-bit widget build")
        try:
            data["text"].encode("utf-8")
        except UnicodeError as exc:
            raise ContractError("Direct text contains an invalid Unicode scalar") from exc
    elif data["type"] == "click":
        geometry = validate_geometry(data["geometry"])
        if data["x"] >= geometry["output_width"] or data["y"] >= geometry["output_height"]:
            raise ContractError("Click must lie within the exact informing PNG")
    return data


def direct_goal_schema() -> dict:
    return _object({"input": input_schema(text_limit=24), "intent": _text(1024),
                    "expected": _text(1024), "interrupt_allowed": {"type": "boolean"}})
