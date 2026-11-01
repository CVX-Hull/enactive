"""Current closed player data; assertions never grant computer custody."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from harness.computer.protocol import validate_actions


class PlayerError(ValueError):
    """Cannot remember, retrieve or evaluate a player helper."""


def _object(properties: dict) -> dict:
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def _text(limit: int, *, empty: bool = False) -> dict:
    return dict(type='string', minLength=0 if empty else 1, maxLength=limit)


def _enum(*values: str) -> dict:
    return dict(type='string', enum=list(values))


def json_object(value: Any) -> dict:
    def pairs(items):
        result = {}
        for key, child in items:
            if key in result:
                raise PlayerError('Duplicate JSON key')
            result[key] = child
        return result
    try:
        if type(value) is dict:
            value = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        if type(value) not in (str, bytes):
            raise PlayerError('Expected a JSON object')
        encoded = value.encode('utf-8') if type(value) is str else value
        if len(encoded) > 1048576:
            raise PlayerError('JSON exceeds 1 MiB')
        result = json.loads(encoded, object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(PlayerError('Nonfinite JSON')))
        if type(result) is not dict:
            raise PlayerError('Expected a JSON object')
        # JSON escape sequences must also produce valid UTF-8 strings.
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PlayerError(f'Invalid player JSON: {exc}') from exc


def canonical(value: dict) -> str:
    return json.dumps(json_object(value), ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':'))


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


_APPLICABILITY = {'anyOf': [_object(dict(game=_text(128), version=_text(128), notes=_text(1024, empty=True))), {'type': 'null'}]}
_REFS = dict(type='array', items=_text(128), maxItems=16, uniqueItems=True)
_NULL_ID = {'anyOf': [_text(128), {'type': 'null'}]}
_RECORD = _object(dict(schema={'const': 'player-record/1'}, kind=_enum('claim', 'work', 'decision', 'procedure', 'correction', 'advice'),
                       text=_text(8192, empty=True), data={'type': 'object'}, sources=_REFS, supports=_REFS,
                       supersedes=_NULL_ID, applicability=_APPLICABILITY, program_id=_NULL_ID))
_PROGRAM = _object(dict(schema={'const': 'player-program/1'}, code=_text(32768), parent_id=_NULL_ID,
                        reason=_text(2048, empty=True), source_ids=_REFS, record_ids=_REFS, applicability=_APPLICABILITY))


_SUBGOAL = _object(dict(text=_text(2048), expected_observations=dict(type='array', items=_text(512), maxItems=8),
                        status=_enum('open', 'blocked'), confidence=dict(type='number', minimum=0, maximum=1),
                        sources=_REFS))
_CLOSE_OUTCOMES = ('achieved', 'failed', 'abandoned')
# The level manages only its own subgoal; every proposal is exactly one of three closed shapes.
_KEEP = _object(dict(schema={'const': 'player-level-proposal/2'}, action={'const': 'keep'}, record_id=_text(128),
                     reason=_text(1024), sources=_REFS))
_PREVIOUS = _object(dict(record_id=_text(128), outcome=_enum(*_CLOSE_OUTCOMES, 'revised'),
                         reason=_text(1024), sources=_REFS))
_REPLACE = _object(dict(schema={'const': 'player-level-proposal/2'}, action={'const': 'replace'}, subgoal=_SUBGOAL,
                        previous={'anyOf': [_PREVIOUS, {'type': 'null'}]}))
_CLOSE = _object(dict(schema={'const': 'player-level-proposal/2'}, action={'const': 'close'}, record_id=_text(128),
                      outcome=_enum(*_CLOSE_OUTCOMES), reason=_text(1024), sources=_REFS))
_SHAPES = dict(keep=_KEEP, replace=_REPLACE, close=_CLOSE)
_LEVEL_PROPOSAL = {'anyOf': list(_SHAPES.values())}
LEVEL_SHAPES = ('Valid shapes: keep {record_id, reason, sources}; close {record_id, outcome: achieved|failed|abandoned, '
                'reason, sources}; replace {subgoal, previous: null | {record_id, outcome: achieved|failed|abandoned|revised, '
                'reason, sources}}')
_ABSTAIN = _object(dict(reason=_text(1024)))


def level_proposal(value: object) -> dict:
    """The subgoal level's versioned commit proposal; the custodian binds its position."""
    result = json_object(value)
    action = result.get('action')
    if type(action) is not str or action not in _SHAPES:
        raise PlayerError('A proposal action must be keep, close or replace')
    validate_json(result, _SHAPES[action])
    return result


def level_proposal_schema() -> dict:
    return json_object(_LEVEL_PROPOSAL)


def level_abstain(value: object) -> str:
    """The reason a level pass ends without a proposal; nothing is written."""
    result = json_object(value)
    validate_json(result, _ABSTAIN)
    if not result['reason'].strip():
        raise PlayerError('An abstain reason must not be blank')
    return result['reason']


def level_abstain_schema() -> dict:
    return json_object(_ABSTAIN)


def record(value: object) -> dict:
    result = json_object(value)
    validate_json(result, _RECORD)
    if len(canonical(result['data']).encode('utf-8')) > 16384:
        raise PlayerError('Record data exceeds 16 KiB')
    if result['kind'] == 'correction' and result['supersedes'] is None:
        raise PlayerError('Correction requires its prior record')
    return result


def program(value: object) -> dict:
    result = json_object(value)
    validate_json(result, _PROGRAM)
    if len(result['code'].encode('utf-8')) > 32768:
        raise PlayerError('Program source exceeds 32 KiB')
    return result


def record_schema() -> dict:
    return json_object(_RECORD)


def program_schema() -> dict:
    return json_object(_PROGRAM)


def policy_result(value: object) -> dict:
    result = json_object(value)
    validate_json(result, _object(dict(status=_enum('act', 'yield', 'done'), state={'type': 'object'},
                                      actions={}, reason=_text(1024))))
    if result['status'] == 'act':
        validate_actions(result['actions'])
    elif result['actions'] is not None:
        raise PlayerError('Yield/done actions must be null')
    return result
