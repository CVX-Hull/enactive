"""Mechanical wake rules for the subgoal level (ADR-007); pure counts, no store or game."""
import pytest

from tools.level_schedule import LevelSchedule


def schedule(**changes):
    return LevelSchedule(**{**dict(inputs_per_pass=10, budget_fractions=(.25, .5, .75), allowance=100), **changes})


def test_start_pass_runs_only_to_revalidate_open_records():
    assert schedule().due(entries=0, inputs=0, attempts=0, open_records=1) == 'start'
    fresh = schedule()
    assert fresh.due(entries=0, inputs=0, attempts=0, open_records=0) is None
    # The start is considered once; later records wait for log entries.
    assert fresh.due(entries=0, inputs=0, attempts=0, open_records=1) is None


def test_inputs_wake_every_k_and_never_on_an_empty_delta():
    rules = schedule()
    rules.due(entries=0, inputs=0, attempts=0, open_records=0)
    assert rules.due(entries=9, inputs=9, attempts=9, open_records=0) is None
    assert rules.due(entries=10, inputs=10, attempts=10, open_records=0) == 'inputs'
    assert rules.due(entries=10, inputs=10, attempts=10, open_records=1) is None
    assert rules.due(entries=19, inputs=19, attempts=19, open_records=1) is None
    assert rules.due(entries=21, inputs=20, attempts=20, open_records=1) == 'inputs'


def test_budget_fractions_fire_once_and_wait_for_new_entries():
    rules = schedule(inputs_per_pass=1000)
    rules.due(entries=0, inputs=0, attempts=0, open_records=0)
    assert rules.due(entries=0, inputs=0, attempts=30, open_records=0) is None
    assert rules.due(entries=1, inputs=1, attempts=30, open_records=0) == 'budget-0.25'
    assert rules.due(entries=2, inputs=2, attempts=40, open_records=0) is None
    # One pass covers every fraction crossed since the last one.
    assert rules.due(entries=3, inputs=3, attempts=80, open_records=0) == 'budget-0.75'
    assert rules.due(entries=4, inputs=4, attempts=99, open_records=0) is None


@pytest.mark.parametrize('changes', [dict(inputs_per_pass=0), dict(inputs_per_pass=1001), dict(allowance=0),
    dict(budget_fractions=(.5, .25)), dict(budget_fractions=(0.0,)), dict(budget_fractions=(1.0,)),
    dict(budget_fractions=(.5, .5)), dict(budget_fractions=tuple(i / 10 for i in range(1, 10)))])
def test_invalid_parameters_are_refused(changes):
    with pytest.raises(ValueError):
        schedule(**changes)
