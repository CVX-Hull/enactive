"""Current closed player data; assertions never grant computer custody."""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from harness.jsonio import canonical as _canonical, strict_loads


class PlayerError(ValueError):
    """Cannot remember, retrieve or evaluate a player helper."""


def _object(properties: dict) -> dict:
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def _text(limit: int, *, empty: bool = False) -> dict:
    return dict(type='string', minLength=0 if empty else 1, maxLength=limit)


def _enum(*values: str) -> dict:
    return dict(type='string', enum=list(values))


def json_object(value: Any) -> dict:
    try:
        if type(value) is dict:
            value = _canonical(value)
        if type(value) not in (str, bytes):
            raise PlayerError('Expected a JSON object')
        encoded = value.encode('utf-8') if type(value) is str else value
        if len(encoded) > 1048576:
            raise PlayerError('JSON exceeds 1 MiB')
        result = strict_loads(encoded, PlayerError)
        if type(result) is not dict:
            raise PlayerError('Expected a JSON object')
        # JSON escape sequences must also produce valid UTF-8 strings.
        _canonical(result).encode('utf-8')
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PlayerError(f'Invalid player JSON: {exc}') from exc


def canonical(value: dict) -> str:
    return _canonical(json_object(value), sort_keys=True)


def validate_json(value: dict, schema: dict) -> None:
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as exc:
        raise PlayerError(f'Invalid player data: {exc.message}') from exc


def identity(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= 128:
        raise PlayerError('Identity must be 1..128 characters')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise PlayerError('Identity must be valid UTF-8') from exc
    return value


def bounded_integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise PlayerError(f'Integer must be within {low}..{high}')
    return value


def references(value: object) -> list[str]:
    if type(value) is not list or len(value) > 16:
        raise PlayerError('References must be a list of at most 16 unique IDs')
    for item in value:
        identity(item)
    if len(set(value)) != len(value):
        raise PlayerError('References must be a list of at most 16 unique IDs')
    return value


def common_arguments(args: object) -> tuple[dict, str, list[str]]:
    if type(args) is not dict:
        raise PlayerError('Tool arguments must be an object')
    intent = args.get('intent')
    if type(intent) is not str or not 1 <= len(intent) <= 512 or not intent.strip() or len(intent.splitlines()) != 1 or any(c in intent for c in '\r\n'):
        raise PlayerError('Intent must be nonempty one-line text within 512 characters')
    cites = references(args.get('cites', []))
    return {k:v for k,v in args.items() if k not in {'intent', 'cites'}}, intent, cites
