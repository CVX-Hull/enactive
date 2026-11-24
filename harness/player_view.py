"""Typed MCP actor views; canonical operator records and public hint data stay intact.

Only declared envelope positions are traversed. Public hint text and citation IDs
are never interpreted as envelopes.
"""
from __future__ import annotations

import copy

from .computer.protocol import receipt, source
from .player.contracts import PlayerError, common_arguments, references


class UnsupportedResult(PlayerError):
    """An undeclared result must never pass through to the actor."""


def _fields(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise UnsupportedResult('Unsupported player result shape')
    return dict(value)


# These are argument/custody facts, rather than controller diagnostics. Dynamic
# validation feedback originates from the closed player schemas, never runtime
# resource accounting. Unknown controller text is deliberately not echoed.
_FEEDBACK = {
    'Invalid mechanical object fields', 'Integer outside mechanical bound',
    'Input must be an object', 'Unsupported basic key', 'Invalid modifiers',
    'Text must be 1..31 UTF8 bytes without controls', 'Unsupported pointer button',
    'Unknown basic input', 'Invalid bounded wait', 'Choose 1..32 basic operations',
    'Combined waits exceed the original 15-second operation bound',
    'Pointer requires a source issued to this actor', 'Pointer exceeds original full-image coordinates',
    'Input requires actions and optional source_id', 'Unknown memory-query fields',
    'Actor sealed; original collection/read only', 'Actor is not the active writer',
    'Input fenced; original collection only', 'Unknown ephemeral actor capability',
    'Actor capability unavailable', 'Unsettled input cannot become a handoff',
    'Unknown retained source', 'Unknown original operation for this actor',
    'Unknown original player-service operation', 'Yield/done actions must be null',
    'Selection requires exactly crop and size', 'Selection size requires two dimensions',
    'Crop requires x,y,width,height', 'Crop exceeds the captured image',
    'Identity must be 1..128 characters',
    'Program duration must be finite within (0,20] seconds',
    'Unknown current tool',
    'Operation ID must be32 lowercase hexadecimal characters',
}


def _diagnostic(reason, error=None):
    if error == 'PlayerError' and isinstance(reason, str):
        return reason[:1100]
    if isinstance(reason, str) and reason in _FEEDBACK:
        return reason
    if isinstance(reason, str) and reason.startswith(('Invalid player data: ', 'Invalid player JSON: ',
                                                      'PlayerError: ')):
        return reason[:1100]
    if reason == 'Owned native child exited':
        return 'Owned application exited'
    if reason == 'Owned mechanical target is not available':
        return 'Owned target unavailable'
    return 'Service unavailable; collect original evidence where an operation ID is supplied. No authority is restored.'


def actor_error(error=None):
    """Bounded local/projection failures, with no raw unknown-envelope fallback."""
    return dict(schema='player-error/2', error='unsupported_result' if isinstance(error, UnsupportedResult) else 'service_error',
                reason='Unsupported player result' if isinstance(error, UnsupportedResult) else _diagnostic(str(error), type(error).__name__),
                input_replayed=False)


def _native(value):
    result = _fields(value, {'schema', 'id', 'session', 'disposition', 'emitted_events', 'reason', 'frame'})
    if result['schema'] == 'computer-receipt/2':
        receipt(result, identity=result['id'], session=result['session'])
        return result  # Actual native receipts, including reasons, retain integrity.
    if result['schema'] not in {'computer-local/1', 'computer-transport/2'}:
        raise UnsupportedResult('Unsupported native result')
    result['reason'] = _diagnostic(result['reason'])
    return result


def _operation_reason(value):
    return {
        'completed': 'Basic operations completed; application effect is not certified',
        'sealed': 'Actor sealed; successor requires actual host/MCP quiescence',
        'pending': 'Original operation pending; call computer_result with this operation_id; never replay input',
        'unknown': 'Delivery unknown; input is stopped and never replayed. Call computer_result with this operation_id for the original evidence.',
        'partial': 'Delivery partial; input is stopped and never replayed. Call computer_result with this operation_id for the original evidence.',
    }.get(value['status'], _diagnostic(value['reason']))


#: The actor's record of one computer operation: the original receipts, source and handoff issuance. The model reads it
#: from `computer_result`; for the other computer calls the host and the trace hold it and the model reads `short_result`.
OPERATION_SCHEMA = 'player-computer-operation/1'
#: What the model reads for `computer_observe`, `computer_input` and `player_handoff`.
RESULT_SCHEMA = 'player-computer-result/2'


def _operation(value):
    result = _fields(value, {'schema', 'operation_id', 'session', 'actor_id', 'kind', 'status', 'created_wall',
                             'deadline_monotonic', 'receipts', 'source', 'remaining', 'reason', 'handoff'},
                     {'image_unavailable', 'image_limit_bytes', 'image_note'})
    result.pop('deadline_monotonic')
    result.pop('remaining')
    result['schema'] = OPERATION_SCHEMA
    result['reason'] = _operation_reason(result)
    result['receipts'] = [_native(item) for item in result['receipts']]
    if result['source'] is not None:
        source(result['source'])
    if result['handoff'] is not None:
        issued = _fields(result['handoff'], {'schema', 'operation_id', 'session', 'actor_id', 'context_id',
                                            'context_sha256', 'sealed_wall', 'grants_authority'})
        if issued['schema'] != 'player-handoff/1' or issued['grants_authority'] is not False:
            raise UnsupportedResult('Unsupported handoff issuance')
    return result


def _hint(value):
    result = _fields(value, {'schema', 'id', 'actor_id', 'created_wall', 'text', 'source_ids', 'intent', 'cites'})
    if result['schema'] != 'player-hint/1' or type(result['text']) is not str or not 1 <= len(result['text']) <= 8192:
        raise UnsupportedResult('Unsupported hint')
    references(result['source_ids'])
    common_arguments({'intent': result['intent'], 'cites': result['cites']})
    return result


def _service(value):
    result = _fields(value, {'schema', 'operation_id', 'actor_id', 'kind', 'status', 'value', 'grants_authority'})
    if result['kind'] != 'player_hint' or result['status'] != 'completed' or result['grants_authority'] is not False:
        raise UnsupportedResult('Unsupported original service result')
    result['value'] = _hint(result['value'])
    if result['value']['id'] != result['operation_id'] or result['value']['actor_id'] != result['actor_id']:
        raise UnsupportedResult('Original service identity differs')
    return result


_KNOWLEDGE_RESOLUTIONS = frozenset(('current', 'revision', 'restated', 'narrowed', 'corrected', 'ended', 'retracted',
                                    'title', 'unknown', 'query'))


def _project(value):
    schema = value.get('schema')
    if schema == 'player-knowledge/2':
        result = _fields(value, {'schema', 'version', 'grants_authority', 'identity', 'resolution', 'resolved_from', 'records'})
        if (result['grants_authority'] is not False or not isinstance(result['records'], list)
                or result['resolution'] not in _KNOWLEDGE_RESOLUTIONS or not isinstance(result['identity'], str)
                or not (result['resolved_from'] is None or isinstance(result['resolved_from'], str))):
            raise UnsupportedResult('Unsupported delivered knowledge result')
        return result  # Article and fact text is opaque data, never another envelope.
    if schema == 'computer-operation/1':
        return _operation(value)
    if schema == 'player-service-result/2':
        return _service(value)
    if schema == 'player-hint/1':
        return _hint(value)
    if schema == 'player-transport/1':
        result = _fields(value, {'schema', 'operation_id', 'session', 'actor_id', 'kind', 'status', 'reason',
                                 'collect_with', 'input_replayed'})
        result.update(schema='player-transport/2', reason='Transport outcome unknown; collect the original ID without replay.')
        return result
    if schema == 'player-error/1':
        result = _fields(value, {'schema', 'error', 'reason', 'submission'}, {'operation_id'})
        result.update(schema='player-error/2', error='request_error', reason=_diagnostic(result['reason'], result['error']), input_replayed=False)
        return result
    if schema == 'player-source-read/1':
        result = _fields(value, {'schema', 'source', 'read_wall'}, {'image_unavailable', 'image_limit_bytes', 'image_note'})
        source(result['source'])
        return result
    if schema is None:
        result = _fields(value, {'stop_requested', 'native_pause_confirmed', 'reason'}, {'grants_authority'})
        result['reason'] = 'Input stop requested; application persistence and exit are not certified.'
        return result
    raise UnsupportedResult('Unsupported player result version')


def short_result(operation):
    """What the model reads of one operation record from `actor_result`: its status; the frame's `source_id` and
    size where it has a frame (and `image_unavailable` when the pixels were not returned); and, while the operation
    is neither completed nor sealed, its `operation_id` and a `reason` that says what to do next. Receipts, identities and times stay in `operation`."""
    if type(operation) is not dict or operation.get('schema') != OPERATION_SCHEMA:
        raise UnsupportedResult('Unsupported operation record')
    status = operation['status']
    result = dict(schema=RESULT_SCHEMA, status=status)
    frame = operation['source']
    if frame is not None:
        result.update(source_id=frame['source_id'], width=frame['width'], height=frame['height'])
    if operation.get('image_unavailable'):
        result['image_unavailable'] = True
    if status not in ('completed', 'sealed'):
        # A refusal can follow a part-delivered batch, so it too names the record that shows what was delivered.
        result['operation_id'] = operation['operation_id']
        result['reason'] = operation['reason']
    return result


def actor_result(value):
    """Copy and project only current declared result envelopes, or fail closed."""
    if type(value) is not dict:
        raise UnsupportedResult('Unsupported player result type')
    # The client already bounded and decoded transport JSON. Copy only declared
    # result envelopes; hint text remains an opaque public report.
    return _project(copy.deepcopy(value))
