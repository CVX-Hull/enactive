"""Inert state edits and one fixed, non-causal all-assigned reduction."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from jsonschema import Draft202012Validator, ValidationError


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def validate(schema, state, sources):
    if len(encoded(schema)) + len(encoded(state)) > 65536:
        raise ValueError('state and schema exceed 64 KiB')
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(state)
    for record in state['records']:
        if not set(record['source_ids']) <= set(sources):
            raise ValueError('source outside exposed packet')


def edit(current_schema, published, proposal, sources, *, editing=True):
    """Validate a scratch copy before publication; disabled schema edits do not block values."""
    schema = deepcopy(current_schema)
    state = deepcopy(published)
    if editing and 'schema_edit' in proposal:
        schema = deepcopy(proposal['schema_edit']['schema'])
        state = deepcopy(proposal['schema_edit']['migrated_state'])
    for record in proposal.get('value_edits', []):
        state['records'] = [r for r in state['records'] if r['id'] != record['id']]
        state['records'].append(deepcopy(record))
    validate(schema, state, sources)
    return schema, state


def cycle(candidate, ids):
    if len(ids) != 3:
        return {'status': 'unavailable', 'reason': 'three selected sources not available'}
    if len(encoded([candidate['updater'], candidate['reader']])) > 16384:
        raise ValueError('definitions exceed 16 KiB')
    initial = deepcopy(candidate['initial_state'])
    validate(candidate['state_schema'], initial, ids)
    records = [
        {'id': 'location', 'body': 'The displayed place is evac shelter B-19.', 'source_ids': [ids[0]]},
        {'id': 'identity', 'body': 'The character sheet says Morgan Hale.', 'source_ids': [ids[1]]},
        {'id': 'inventory', 'body': 'The inventory lists a wooden club.', 'source_ids': [ids[2]]},
    ]
    revised_schema = deepcopy(candidate['state_schema'])
    revised_schema['properties']['records']['items']['properties']['note'] = {'type': 'string'}
    update = {'schema_edit': {'schema': revised_schema, 'migrated_state': initial}, 'value_edits': records}
    schema, published = edit(candidate['state_schema'], initial, update, ids)
    publication = {'version': 'research-v1', 'parent': 'research-v0', 'schema': schema,
                   'state': published, 'coverage': ids}
    before = digest(publication)
    bad = {'schema_edit': {'schema': revised_schema, 'migrated_state': {'records': [
        {'id': 'bad', 'body': 'bad', 'source_ids': ['unseen'], 'note': 9}]}}}
    try:
        edit(schema, published, bad, ids)
    except (ValueError, ValidationError):
        failure = {'proposal': bad, 'status': 'rejected', 'publication_sha256': digest(publication)}
    else:
        raise AssertionError('invalid migration was accepted')
    assert before == failure['publication_sha256']
    fallback = edit(candidate['state_schema'], initial, {'schema_edit': bad['schema_edit'], 'value_edits': records},
                    ids, editing=False)[1]
    readout = {'query': 'What weapon is listed?', 'version': 'research-v1',
               'records': [r for r in published['records'] if r['id'] == 'inventory'], 'coverage': ids}
    return {'status': 'available', 'kind': 'inert research publication, not delivered-knowledge/1',
            'candidate': candidate['id'], 'candidate_sha256': digest(candidate),
            'reset': {'version': 'research-v0', 'state': initial, 'sha256': digest(initial)},
            'update': {'proposal': update, 'sha256': digest(update)},
            'publication': {**publication, 'sha256': before},
            'disabled_fallback': {'state': fallback, 'sha256': digest(fallback)},
            'failed_edit': failure, 'stale_coverage': {'version': 'research-v0', 'coverage': [],
                                                        'readout': 'unknown: no source covered'},
            'contradiction': {'interpretation': 'No weapon is listed.', 'status': 'contradicted',
                              'source_ids': [ids[2]]},
            'unknown': {'question': 'Where will the survivor travel next?', 'answer': 'unknown'},
            'readout': {**readout, 'sha256': digest(readout)},
            'decision': {'type': 'stand-in only; not dispatched', 'intent': 'Close the inventory screen.',
                         'input': {'type': 'key', 'key': 'ESC', 'modifiers': []},
                         'cites': ['research-v1/inventory'], 'source_ids': [ids[2]],
                         'readout_sha256': digest(readout), 'observed_effect': 'unknown; no input dispatched'},
            'production_mapping': 'A future integration maps source citations through curator.window.positions; '
            'harness.curator.gate validates a fact/article submission against the base version and coverage; '
            'tools.knowledge_export freezes delivered-knowledge/1 for host recall/read. Arbitrary JSON state '
            'cannot be submitted to that closed interface; no gate or production publication was run.',
            'missing_links': ['historical player intent', 'cites', 'hints', 'readout delivery',
                              'historical player decision and effect']}


def reduce_rows(rows):
    """Reduce this fixed example; unknown and failed assignments remain in the denominator."""
    return {'assigned': len(rows), **{key: sum(row['result'] == key for row in rows)
            for key in ('positive', 'negative', 'unknown')},
            'technical_failure': sum(row['technical_failure'] for row in rows),
            'censored': sum(row['censored'] for row in rows)}


def outcome(ids):
    if len(ids) != 3:
        return {'status': 'unavailable'}
    rows = [{'assignment': 'development-397-sd1a2-subset', 'world_lineage': '397-L1',
             'result': 'positive', 'technical_failure': False, 'censored': False,
             'source_ids': [ids[2]]}]
    failed = [{**rows[0], 'result': 'unknown', 'technical_failure': True}]
    censored = [{**rows[0], 'result': 'unknown', 'censored': True}]
    return {'fixed_question': 'Does the selected inventory screen list a wooden club?',
            'assigned_rows': rows, 'all_assigned': reduce_rows(rows),
            'support': {'positive': {'status': 'supported', 'source_ids': [ids[2]], 'reason': 'wooden club listed'},
                        'negative': {'status': 'contradicted', 'claim': 'No weapon is listed', 'source_ids': [ids[2]]},
                        'unknown': {'status': 'unknown', 'reason': 'no observed future travel or task progress'}},
            'sensitivity_only_not_actual_runs': {'technical_failure': reduce_rows(failed),
                                                 'censoring': reduce_rows(censored)},
            'endpoint': {'alive': 'unknown pending qualified reader; active inventory and visible health '
                         'are supporting observations, not a qualified survival label',
                         'source_ids': [ids[2]], 'game_time': '188 and 208 show 3:11:24 PM: '
                         'zero displayed elapsed seconds between those frames; 210 clock is occluded, '
                         'so endpoint elapsed time is unknown',
                         'task_progress': 'unknown: starting inventory does not establish acquisition',
                         'travel': 'unknown; no distance inferred from pixels'},
            'limitations': 'One selected subset and one inventory question; no inference about efficacy or later endpoint.'}
