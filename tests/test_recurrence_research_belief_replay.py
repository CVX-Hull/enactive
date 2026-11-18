from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path

import pytest

from tools.recurrence_research.belief_replay import compare, exposed_input, replay


@pytest.fixture
def fixture():
    path = Path(__file__).parents[1] / 'data/recurrence-research/belief-replay-cases.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_both_methods_revise_or_abstain_on_the_same_five_cases(fixture):
    result = replay(fixture)
    assert len(result['cases']) == 5
    assert len({case['dependence_group'] for case in fixture['cases']}) == 2
    for case in result['cases']:
        assert {row['id'] for row in case['checkpoints']} == fixture['adjudication'][case['id']].keys()
        for row in case['checkpoints']:
            expected = fixture['adjudication'][case['id']][row['id']]
            assert row['qualitative'] == row['numerical']
            assert row['qualitative']['state'] == expected
            assert row['qualitative']['answer'] is (True if expected == 'support-only' else None)
            observations = {entry['source_id'] for entry in row['input']['observations']}
            assert set(row['qualitative']['source_ids']) <= observations


def test_excluded_results_and_adjudication_do_not_change_pre_answer_input_or_readout(fixture):
    changed = deepcopy(fixture)
    changed['adjudication'] = {'poisoned': 'An evaluator answer the methods must never see.'}
    baseline = replay(fixture)
    withheld_frame = 'd1f27714d8684654945e288f09cbcc73-694'
    for case, expected in zip(changed['cases'], baseline['cases'], strict=True):
        end = case['checkpoints'][0]['through']
        unseen = case['exposure'][end:]
        if case['id'] == 'drink-and-tupperware':
            assert withheld_frame in case['observations'] and withheld_frame not in case['exposure']
            unseen.append(withheld_frame)
        for source in unseen:
            case['observations'][source] = {
                'detail': 'Changed outcome for a source outside the prefix.',
                'reports': [{'origin': source, 'event': case['applicable_events'][0], 'polarity': 'refute'}],
            }
        modified = compare(exposed_input(case, case['checkpoints'][0]))
        assert dict(id='before', **modified) == expected['checkpoints'][0]
        for source in unseen:
            del case['observations'][source]
        case['exposure'] = case['exposure'][:end]
        del case['checkpoints'][1:]
    assert replay(changed)['cases'] == [
        dict(id=case['id'], checkpoints=case['checkpoints'][:1]) for case in baseline['cases']
    ]


def test_repeat_origin_and_question_boundaries_are_preserved(fixture):
    cases = {case['id']: case['checkpoints'] for case in replay(fixture)['cases']}
    _, tank, repeated = cases['drink-and-tupperware']
    assert tank['fixture_counts'] == repeated['fixture_counts'] == {'r': 1, 's': 0}
    assert tank['qualitative'] == repeated['qualitative']
    assert tank['numerical'] == repeated['numerical']
    assert tank['fixture_views']['opinion_mean'] == repeated['fixture_views']['beta_mean'] == Fraction(2, 3)
    assert '17.25 L' in tank['input']['observations'][-1]['detail']
    assert cases['plastic-bottle'][0]['fixture_counts'] == {'r': 0, 's': 0}

    _, title = cases['save-return-to-title']
    reload_input = {**title['input'], 'question': 'Was the same survivor loaded in a fresh child?',
                    'applicable_events': ['same-character-reload-identity']}
    assert compare(reload_input)['qualitative']['answer'] is None
    assert compare(reload_input)['numerical']['answer'] is None

    _, _, quit = cases['application-quit-delivery']
    assert quit['qualitative']['answer'] is quit['numerical']['answer'] is None
    assert quit['fixture_counts'] == {'r': 0, 's': 0}
    exit_input = {**quit['input'], 'question': 'Did the native process exit normally?',
                  'applicable_events': ['normal-native-exit-zero']}
    assert compare(exit_input)['qualitative']['answer'] is True
    assert compare(exit_input)['numerical']['answer'] is True


def test_synthetic_conflict_is_distinct_from_ignorance_after_retraction(fixture):
    observed = replay(fixture)['cases'][0]['checkpoints'][1]['input']
    support = observed['observations'][-1]['source_id']
    contrary = {'source_id': 'synthetic', 'detail': 'Synthetic contrary result.',
                'reports': [{'origin': 'synthetic', 'event': 'synthetic-contrary', 'polarity': 'refute'}]}
    shared = {**observed, 'observations': [*observed['observations'], contrary],
              'applicable_events': [*observed['applicable_events'], 'synthetic-contrary']}
    for withdrawn, expected, answer, counts in (
            ([], 'conflicting', None, {'r': 1, 's': 1}),
            ([support], 'refutation-only', False, {'r': 0, 's': 1}),
            ([support, 'synthetic'], 'unknown', None, {'r': 0, 's': 0})):
        result = compare({**shared, 'withdrawn_origins': withdrawn})
        assert result['qualitative'] == result['numerical']
        assert (result['qualitative']['state'], result['qualitative']['answer']) == (expected, answer)
        assert result['fixture_counts'] == counts


def test_report_cannot_borrow_a_future_or_unestablished_origin(fixture):
    case = fixture['cases'][0]
    first, last = case['exposure'][0], case['exposure'][-1]
    report = case['observations'][last]['reports'][0]
    case['observations'][first]['reports'] = [report]
    with pytest.raises(ValueError, match='invalid exposed report'):
        exposed_input(case, case['checkpoints'][0])
    del case['observations'][first]['reports']
    report['origin'] = first
    with pytest.raises(ValueError, match='missing original report'):
        replay(fixture)
