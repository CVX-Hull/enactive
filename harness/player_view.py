"""Typed MCP actor views; canonical operator records and authored data stay intact.

Only declared envelope positions are traversed. In particular a record's data,
program source, decision reason and state are never interpreted as envelopes.
"""
from __future__ import annotations

import copy

from .computer.protocol import receipt, source
from .player.contracts import PlayerError, program, record


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
    'Context requires ids and optional max_bytes', 'Invalid program-run fields',
    'Actor sealed; original collection/read only', 'Actor is not the active writer',
    'Input fenced; original collection only', 'Unknown ephemeral actor capability',
    'Actor capability unavailable', 'Unsettled input cannot become a handoff',
    'Unknown retained source', 'Unknown original operation for this actor',
    'Unknown original player-service operation', 'Yield/done actions must be null',
    'Selection requires exactly crop and size', 'Selection size requires two dimensions',
    'Crop requires x,y,width,height', 'Crop exceeds the captured image',
    'Program source exceeds 32 KiB', 'Correction requires its prior record',
    'Record data exceeds 16 KiB', 'Identity must be 1..128 characters',
    'Program duration must be finite within (0,20] seconds',
    'Unknown current tool',
    'Operation ID must be32 lowercase hexadecimal characters',
}


def _diagnostic(reason, error=None):
    if error in {'PlayerError', 'PolicyProgramError'} and isinstance(reason, str):
        return reason[:1100]
    if isinstance(reason, str) and reason in _FEEDBACK:
        return reason
    if isinstance(reason, str) and reason.startswith(('Invalid player data: ', 'Invalid player JSON: ',
                                                      'PlayerError: ', 'PolicyProgramError: ')):
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


def _reference(value):
    result = _fields(value, {'operation_id', 'session', 'actor_id', 'kind', 'status', 'reason', 'source_id'})
    result['reason'] = _operation_reason(result)
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


def _program_run(value):
    result = _fields(value, {'schema', 'program_id', 'run_id', 'status', 'reason', 'final_state',
                             'elapsed_seconds', 'steps', 'operations', 'omissions'})
    if result['status'] not in {'done', 'yield', 'limit'}:
        result['reason'] = _diagnostic(result['reason'])
    steps = []
    for item in result['steps']:
        step = _fields(item, {'source', 'operation', 'input_operation', 'result'})
        source(step['source'])
        step['operation'] = _reference(step['operation'])
        if step['input_operation'] is not None:
            step['input_operation'] = _reference(step['input_operation'])
        if step['result'] is not None:
            # Player decision reason/actions and state hashes are opaque data.
            _fields(step['result'], {'status', 'actions', 'reason', 'state_sha256'})
        steps.append(step)
    result['steps'] = steps
    result['operations'] = [_reference(item) for item in result['operations']]
    return result


def _authored(value, kind):
    assigned = {'id', 'actor_id', 'created_wall'} | ({'sha256'} if kind == 'player-program/2' else set())
    if not assigned <= value.keys():
        raise UnsupportedResult('Incomplete stored player data')
    (program if kind == 'player-program/2' else record)({k: v for k, v in value.items() if k not in assigned})
    return value


def _service(value):
    result = _fields(value, {'schema', 'operation_id', 'actor_id', 'kind', 'status', 'value', 'progress',
                             'grants_authority'}, {'collected_operations'})
    _fields(result['progress'], {'steps'})
    for step in result['progress']['steps']:
        _fields(step, {'operation_id', 'session', 'kind'})
    if result['value'] is not None:
        expected = {'player_memory_append': 'player-record/1', 'player_program_save': 'player-program/2',
                    'player_program_run': 'player-program-run/1'}.get(result['kind'])
        if expected is None or result['value'].get('schema') != expected:
            raise UnsupportedResult('Unsupported original service result')
        result['value'] = _project(result['value'])
    if 'collected_operations' in result:
        children = []
        for child in result['collected_operations']:
            if child.get('schema') == 'computer-operation/1':
                children.append(_operation(child))
            else:
                item = _fields(child, {'operation_id', 'session', 'kind', 'status'})
                if item['status'] not in {'not_submitted_to_computer', 'retained_in_prior_session; no authority restored'}:
                    raise UnsupportedResult('Unsupported original child result')
                children.append(item)
        result['collected_operations'] = children
    return result


def _project(value):
    schema = value.get('schema')
    if schema == 'player-knowledge/1':
        result = _fields(value, {'schema', 'version', 'records', 'grants_authority'})
        if result['grants_authority'] is not False or not isinstance(result['records'], list):
            raise UnsupportedResult('Unsupported delivered knowledge result')
        return result  # Article and fact text is opaque data, never another envelope.
    if schema == 'computer-operation/1':
        return _operation(value)
    if schema == 'player-service-result/1':
        return _service(value)
    if schema == 'player-program-run/1':
        return _program_run(value)
    if schema in {'player-record/1', 'player-program/2'}:
        return _authored(value, schema)
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
    if schema == 'player-query/1':
        result = _fields(value, {'schema', 'records', 'grants_authority'})
        result['records'] = [_authored(item, 'player-record/1') for item in result['records']]
        return result
    if schema == 'player-context/1':
        result = _fields(value, {'schema', 'roots', 'records', 'programs', 'sources', 'omissions'})
        result['records'] = [_authored(item, 'player-record/1') for item in result['records']]
        result['programs'] = [_authored(item, 'player-program/2') for item in result['programs']]
        for item in result['sources']:
            _fields(item, {'source', 'available', 'read_verified'})
            source(item['source'])
        for item in result['omissions']:
            _fields(item, {'id', 'reason'})
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
    # The client already bounded/decoded transport JSON. Reuse that envelope
    # limit; the 1 MiB player authoring limit applies to individual records,
    # whereas a valid 50-record query can be larger.
    return _project(copy.deepcopy(value))
