"""Typed MCP actor views; canonical operator records and public hint data stay intact.

Only declared envelope positions are traversed. Public hint text and citation IDs
are never interpreted as envelopes.
"""
from __future__ import annotations

import copy

from .computer.protocol import receipt, source
from .player.contracts import PlayerError, common_arguments, references
from .player.knowledge import ALIAS, QUERY_LIMIT, _clock_label, delivered_record, query_hit, revision_parts, version_number


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
    'Input requires actions and optional source_id',
    'Actor sealed; original collection/read only', 'Actor is not the active writer',
    'Input fenced; original collection only', 'Unknown ephemeral actor capability',
    'Actor capability unavailable', 'Unsettled input cannot become a handoff',
    'Unknown retained source', 'Unknown original operation for this actor',
    'Unknown original player-service operation',
    'Identity must be 1..128 characters',
    'Unknown current tool',
    'Operation ID must be 32 lowercase hexadecimal characters',
}

# Player-store failures whose detail is the storage engine's own text. The model reads only which
# operation failed; the detail stays in the service's own records.
_STORAGE_FAILURES = ('Cannot open current player journal', 'Cannot write journal', 'Cannot read source')


def _player_feedback(reason):
    """A player-data error as the model reads it: its own text, except a store failure's engine detail."""
    for failure in _STORAGE_FAILURES:
        if reason == failure or reason.startswith(failure + ':'):
            return failure + '; the player store did not complete this request. No authority is restored.'
    return reason[:1100]


def _diagnostic(reason, error=None):
    if error == 'PlayerError' and isinstance(reason, str):
        return _player_feedback(reason)
    if isinstance(reason, str) and reason in _FEEDBACK:
        return reason
    if isinstance(reason, str) and reason.startswith('PlayerError: '):
        return ('PlayerError: ' + _player_feedback(reason.removeprefix('PlayerError: ')))[:1100]
    if isinstance(reason, str) and reason.startswith(('Invalid player data: ', 'Invalid player JSON: ')):
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


def _resolution(resolution, identity, resolved_from, records, version):
    """The resolution's row of the read table, as `Knowledge.read` produces it: the record count and kind,
    `resolved_from`, and how the records answer `identity`. Records are already delivered records."""
    one = len(records) == 1
    article = one and 'body' in records[0]
    if resolution == 'current':
        return one and resolved_from is None and records[0]['id'] == identity
    if resolution == 'revision':
        revision = revision_parts(identity)
        current = revision_parts(records[0]['revision']) if article else None
        return (article and resolved_from == identity and revision is not None and current is not None
                and revision[0] == records[0]['id'] and revision[1] <= current[1] <= version)
    if resolution in ('restated', 'narrowed', 'corrected', 'changed'):
        return bool(records) and all('body' not in r for r in records) and resolved_from == identity
    if resolution == 'state_key':
        return (bool(records) and all('body' not in r and r.get('state_key') == identity for r in records)
                and resolved_from is None)
    if resolution in ('ended', 'retracted'):
        return records == [] and resolved_from == identity
    if resolution == 'title':
        return article and records[0]['title'].casefold() == identity.casefold() and resolved_from is None
    if resolution == 'unknown':
        return records == [] and resolved_from is None
    return False


def _knowledge(value):
    """A discriminated `player-knowledge/4` read (`records`) or query (`hits`): its version, its resolution's row
    of the read table, and every record or compact hit closed and blinded. The empty file (`version` null) answers
    only `unknown` (with empty `records`) and `query` (with empty `hits`). Article and fact text is opaque data,
    never another envelope."""
    common = {'schema', 'version', 'grants_authority', 'identity', 'resolution', 'resolved_from'}
    is_query = isinstance(value, dict) and value.get('resolution') == 'query'
    result = _fields(value, common | ({'hits'} if is_query else {'records'}))
    version, resolution = result['version'], result['resolution']
    identity, resolved_from = result['identity'], result['resolved_from']
    if result['grants_authority'] is not False or not isinstance(identity, str) or not isinstance(resolution, str):
        raise UnsupportedResult('Unsupported delivered knowledge result')
    if is_query:
        hits = result['hits']
        if not isinstance(hits, list) or resolved_from is not None or len(hits) > QUERY_LIMIT:
            raise UnsupportedResult('Unsupported delivered knowledge result')
        consistent = hits == [] if version is None else (
            version_number(version) is not None and all(query_hit(hit, version) for hit in hits)
            and len({hit['id'] for hit in hits}) == len(hits))
    else:
        records = result['records']
        if not isinstance(records, list):
            raise UnsupportedResult('Unsupported delivered knowledge result')
        if version is None:
            consistent = resolution == 'unknown' and records == [] and resolved_from is None
        else:
            number = version_number(version)
            consistent = (number is not None
                          and all(delivered_record(record, version) for record in records)
                          and _resolution(resolution, identity, resolved_from, records, number))
    if not consistent:
        raise UnsupportedResult('Unsupported delivered knowledge result')
    return result


def _project(value):
    schema = value.get('schema')
    if schema == 'player-knowledge/4':
        return _knowledge(value)
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
    if schema == 'player-source-read/2':
        status = value.get('status')
        if status == 'available':
            result = _fields(value, {'schema', 'status', 'source_id', 'source', 'origin', 'clickable', 'read_wall'}, {'clock_label'})
            source(result['source'])
            origin = result['origin']
            if (not isinstance(result['source_id'], str) or result['source_id'] != result['source']['source_id']
                    or type(result['clickable']) is not bool or type(result['read_wall']) not in (int, float)
                    or not isinstance(origin, dict) or set(origin) != {'admission', 'actor', 'step'}):
                raise UnsupportedResult('Unsupported player source read result')
            adm = origin['admission']
            if adm != 'current' and (not isinstance(adm, str) or ALIAS.fullmatch(adm) is None):
                raise UnsupportedResult('Unsupported player source read origin')
            if adm != 'current' and result['clickable'] is not False:
                raise UnsupportedResult('Ancestor player source cannot be clickable')
            if not isinstance(origin['actor'], str) or not origin['actor'].strip():
                raise UnsupportedResult('Unsupported player source read actor')
            if origin['step'] is not None and (type(origin['step']) is not int or origin['step'] < 0):
                raise UnsupportedResult('Unsupported player source read step')
            if 'clock_label' in result:
                if not _clock_label(result['clock_label']):
                    raise UnsupportedResult('Unsupported player source clock_label')
            return result
        if status == 'unavailable':
            result = _fields(value, {'schema', 'status', 'source_id', 'reason', 'read_wall'})
            if (not isinstance(result['source_id'], str) or not result['source_id']
                    or result['reason'] not in ('unknown-or-out-of-scope', 'missing', 'integrity-failed', 'image-limit')
                    or type(result['read_wall']) not in (int, float)):
                raise UnsupportedResult('Unsupported player source unavailable result')
            return result
        raise UnsupportedResult('Unsupported player source read status')
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
