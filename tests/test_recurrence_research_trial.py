import json
from pathlib import Path

import pytest

from tools.recurrence_research.trial import cycle, edit, outcome


def test_disabled_edit_still_applies_values_and_unknown_source_rejected():
    candidate = {'state_schema': {'type': 'object'}, 'initial_state': {'records': []}}
    record = {'id': 'a', 'body': 'visible', 'source_ids': ['s']}
    _, state = edit(candidate['state_schema'], candidate['initial_state'], {'schema_edit': {'schema': {}, 'migrated_state': {}},
                                                              'value_edits': [record]}, ['s'], editing=False)
    assert state['records'] == [record]
    with pytest.raises(ValueError):
        edit(candidate['state_schema'], state, {'value_edits': [{**record, 'source_ids': ['outside']}]}, ['s'])
    assert state['records'] == [record]


def test_value_update_retains_the_published_schema():
    candidate = json.loads(Path('data/recurrence-research/spec.json').read_text())['candidate']
    result = cycle(candidate, ['a', 'b', 'c'])['publication']
    record = {**result['state']['records'][0], 'note': 'uncertain interpretation'}
    schema, state = edit(result['schema'], result['state'], {'value_edits': [record]}, ['a', 'b', 'c'])
    assert schema == result['schema']
    assert next(row for row in state['records'] if row['id'] == record['id'])['note'] == record['note']


def test_research_cycle_and_all_assigned_reduction():
    candidate = json.loads(Path('data/recurrence-research/spec.json').read_text())['candidate']
    result = cycle(candidate, ['a', 'b', 'c'])
    assert result['reset']['state'] == {'records': []}
    assert result['stale_coverage']['readout'].startswith('unknown')
    assert result['failed_edit']['publication_sha256'] == result['publication']['sha256']
    assert len(result['disabled_fallback']['state']['records']) == 3
    assert [r['id'] for r in result['readout']['records']] == ['inventory']
    assert result['decision']['type'] == 'stand-in only; not dispatched'
    result = outcome(['a', 'b', 'c'])
    assert result['all_assigned']['assigned'] == len(result['assigned_rows']) == 1
    assert result['all_assigned']['positive'] == 1
    assert result['sensitivity_only_not_actual_runs']['censoring']['unknown'] == 1
    assert outcome([])['status'] == 'unavailable'
