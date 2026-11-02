"""Current closed player data; assertions never grant computer custody."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from harness.computer.protocol import validate_actions


class PlayerError(ValueError):
    """Cannot remember, retrieve or evaluate a player helper."""


class RememberError(PlayerError):
    """Player memory could not store a write (storage fault or source capacity), as distinct from a refused one.

    The composition stops the recorder and the level for the session on it; the actor's input is unaffected.
    """


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


# The subgoal level's four terminal calls (level v4) and the episode recorder's two. Each is one flat object using
# only the portable schema keywords (type, enum, description, properties, required, items and the length/size/range
# bounds): no const, anyOf, $ref, nested union or model-supplied constant. The model supplies neither a record id nor
# a version; software resolves the one current level subgoal and stamps the contract versions into what it stores.
LEVEL_CONTRACT = 'player-level/4'
LEVEL_COMMIT_SCHEMA = 'player-level-commit/4'
LEVEL_ABSTAIN_SCHEMA = 'player-level-abstain/2'
EPISODE_CONTRACT = 'player-episode/1'
EPISODE_RECORD_SCHEMA = 'player-episode-record/1'
EPISODE_ABSTAIN_SCHEMA = 'player-episode-abstain/1'
INTENT_SCHEMA = 'player-intent/2'
CLOSE_OUTCOMES = ('achieved', 'failed', 'abandoned')
PREVIOUS_OUTCOMES = ('none', *CLOSE_OUTCOMES, 'revised')
ABSTAIN_CODES = ('insufficient_evidence', 'transient_screen_state', 'no_change_needed', 'other')
EPISODE_ABSTAIN_CODES = ('unreadable_frames', 'no_player_action', 'other')
OBSERVATION_STATUSES = ('seen', 'not_yet', 'contradicted')
# How an episode ended: the recorder writes recorded and abstained, the driver reports failed and dropped.
SETTLE_WRITERS = dict(recorded='recorder', abstained='recorder', failed='software', dropped='software')
SOFTWARE_SETTLES = ('failed', 'dropped')
EPISODE_SOURCES = 4
LEVEL_TERMINAL_TOOLS = ('player_level_keep', 'player_level_replace', 'player_level_close', 'player_level_abstain')
EPISODE_TOOLS = ('player_episode_record', 'player_episode_abstain')
# Ends every refusal of a terminal call, whichever layer raised it; the host's validation refusals end with the same text.
LEVEL_FIX_LINE = 'Fix the call and resend it; abstaining is not the remedy for a fixable call.'


def _described(schema: dict, description: str) -> dict:
    return dict(schema, description=description)


_LEVEL_SOURCES = _described(dict(type='array', items=_text(128), maxItems=16),
                            'Ids of the log frames (source ids) that support this call; may be empty.')
_LEVEL_KEEP = _object(dict(
    reason=_described(_text(1024), 'Why the current subgoal still stands.'), sources=_LEVEL_SOURCES))
_LEVEL_REPLACE = _object(dict(
    text=_described(_text(2048), 'The new subgoal, one sentence that advances the mission objective.'),
    expected_observations=_described(dict(type='array', items=_text(512), minItems=1, maxItems=8),
                                     '1 to 8 observations that would show the subgoal is achieved.'),
    status=_described(_enum('open', 'blocked'), 'open if it can be pursued now, blocked if something prevents it.'),
    confidence=_described(dict(type='number', minimum=0, maximum=1), 'Your confidence from 0 to 1.'),
    sources=_LEVEL_SOURCES,
    previous_outcome=_described(_enum(*PREVIOUS_OUTCOMES),
        'What happened to the subgoal this replaces. none only when there is no current subgoal; otherwise '
        'achieved, failed, abandoned or revised.'),
    previous_reason=_described(_text(1024, empty=True),
        'Why that outcome; empty only when previous_outcome is none.')))
_LEVEL_CLOSE = _object(dict(
    outcome=_described(_enum(*CLOSE_OUTCOMES), 'How the current subgoal ended.'),
    reason=_described(_text(1024), 'Why it ended that way.'), sources=_LEVEL_SOURCES))
_LEVEL_ABSTAIN = _object(dict(
    reason_code=_described(_enum(*ABSTAIN_CODES), 'The closed reason for ending the pass without a change.'),
    reason=_described(_text(1024), 'One sentence of explanation.'), sources=_LEVEL_SOURCES))

_EPISODE_SOURCES = _described(dict(type='array', items=_text(128), maxItems=EPISODE_SOURCES),
                              'Ids of at most 4 frames of this episode (source ids) that support this call; may be empty.')
_EPISODE_RECORD = _object(dict(
    attempted=_described(_text(1024), 'What the player attempted in this episode, in one or two sentences.'),
    counterpart=_described(_text(512, empty=True), 'With what or whom it acted; empty if there was none.'),
    observation_status=_described(dict(type='array', items=_enum(*OBSERVATION_STATUSES), maxItems=8),
        'One entry per expected observation of the subgoal, in order: seen if this episode showed it, not_yet if '
        'it did not, contradicted if it showed the opposite. Empty only when the pushed input has no subgoal.'),
    changed=_described(_text(1024, empty=True),
        'What visibly changed in the player\'s own state between the baseline frame and the last frame of this '
        'episode, citing the frames that show it; empty if nothing changed.'),
    residual=_described(_text(1024, empty=True),
                        'Anything that happened which the subgoal did not anticipate; empty if nothing.'),
    confidence=_described(dict(type='number', minimum=0, maximum=1), 'Your confidence from 0 to 1.'),
    sources=_EPISODE_SOURCES))
_EPISODE_ABSTAIN = _object(dict(
    reason_code=_described(_enum(*EPISODE_ABSTAIN_CODES), 'The closed reason the frames support no record.'),
    reason=_described(_text(1024), 'One sentence of explanation.'), sources=_EPISODE_SOURCES))
_LEVEL_SCHEMAS = dict(player_level_keep=_LEVEL_KEEP, player_level_replace=_LEVEL_REPLACE,
                      player_level_close=_LEVEL_CLOSE, player_level_abstain=_LEVEL_ABSTAIN,
                      player_episode_record=_EPISODE_RECORD, player_episode_abstain=_EPISODE_ABSTAIN)


def _brief(error: ValidationError) -> str:
    path = '.'.join(str(part) for part in error.absolute_path) or 'arguments'
    return f'{path}: {error.message}'[:240]


def level_arguments(tool: str, value: object) -> dict:
    """One terminal call's arguments (a level or a recorder tool), validated against its flat schema.

    The error names the field and rule. The text field (`reason`, `text` or `attempted`) must not be blank.
    """
    result = json_object(value)
    errors = sorted(Draft202012Validator(_LEVEL_SCHEMAS[tool]).iter_errors(result), key=lambda e: list(e.absolute_path))
    if errors:
        # The server bounds an error at 600 characters; the fix line must survive that bound.
        raise PlayerError(f'Invalid {tool} arguments - ' + '; '.join(_brief(e) for e in errors[:3])[:440] + '\n' + LEVEL_FIX_LINE)
    field = next(name for name in ('reason', 'text', 'attempted') if name in result)
    if not result[field].strip():
        raise PlayerError(f'Invalid {tool} arguments - {field}: must not be blank\n' + LEVEL_FIX_LINE)
    return result


def level_tool_schema(tool: str) -> dict:
    return json_object(_LEVEL_SCHEMAS[tool])


def refuse_custodian_data(value: dict) -> None:
    """The general memory-append path never carries the custodian's reserved data.

    `data.level` (any value), `data.level_contract`, `data.writer` and `data.by == "software"` are stamped only
    by the custodian's level-commit, closure and episode-settle paths, so no actor can forge a level record,
    an episode or a software closure.
    """
    data = value.get('data', {})
    reserved = [k for k in ('level', 'level_contract', 'writer') if k in data] + (['by'] if data.get('by') == 'software' else [])
    if reserved:
        raise PlayerError('The custodian reserves data.level, data.level_contract, data.writer and data.by "software" '
                          'for its commit and settle paths; this record sets ' + ', '.join(f'data.{k}' for k in reserved))


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
