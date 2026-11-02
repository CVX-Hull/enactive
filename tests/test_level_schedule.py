"""Mechanical wake rules for the subgoal level (ADR-007 level v4); pure counts, no store or game."""
import pytest

from tools.level_schedule import LevelSchedule


def schedule(**changes):
    return LevelSchedule(**{**dict(budget_fractions=(.25, .5, .75), allowance=100), **changes})


def test_start_wake_runs_only_to_revalidate_what_earlier_sessions_left():
    assert schedule().due(settled=0, attempts=0, carried=1) == 'start'
    fresh = schedule()
    assert fresh.due(settled=0, attempts=0, carried=0) is None
    # The start is considered once; carried records wait for a settle afterwards.
    assert fresh.due(settled=0, attempts=0, carried=1) is None
    assert fresh.due(settled=1, attempts=1, carried=1) == 'settle'


def test_every_settle_wakes_and_an_empty_delta_never_does():
    rules = schedule()
    rules.due(settled=0, attempts=0, carried=0)
    assert rules.due(settled=0, attempts=5, carried=0) is None
    assert rules.due(settled=1, attempts=5, carried=0) == 'settle'
    assert rules.due(settled=1, attempts=6, carried=0) is None
    assert rules.due(settled=2, attempts=7, carried=0) == 'settle'


def test_wakes_that_arrive_during_a_pass_coalesce_into_one():
    rules = schedule()
    rules.due(settled=0, attempts=0, carried=0)
    assert rules.due(settled=1, attempts=3, carried=0) == 'settle'
    # Three more episodes settle while that pass runs; the driver does not ask. When it does, there is one wake.
    assert rules.due(settled=4, attempts=9, carried=0) == 'settle'
    assert rules.due(settled=4, attempts=9, carried=0) is None


def test_budget_fractions_name_a_wake_only_after_a_settle_and_fire_once():
    rules = schedule()
    rules.due(settled=0, attempts=0, carried=0)
    # The fraction is crossed but nothing has settled since the last pass: no wake.
    assert rules.due(settled=0, attempts=30, carried=0) is None
    assert rules.due(settled=1, attempts=30, carried=0) == 'budget-0.25'
    assert rules.due(settled=2, attempts=40, carried=0) == 'settle'
    # One pass covers every fraction crossed since the last one.
    assert rules.due(settled=3, attempts=80, carried=0) == 'budget-0.75'
    assert rules.due(settled=4, attempts=99, carried=0) == 'settle'


def test_a_wake_after_start_still_counts_settles_made_before_the_start_pass():
    rules = schedule()
    assert rules.due(settled=2, attempts=0, carried=1) == 'start'
    assert rules.due(settled=2, attempts=0, carried=1) is None
    assert rules.due(settled=3, attempts=0, carried=1) == 'settle'


@pytest.mark.parametrize('changes', [dict(allowance=0), dict(budget_fractions=(.5, .25)), dict(budget_fractions=(0.0,)),
    dict(budget_fractions=(1.0,)), dict(budget_fractions=(.5, .5)), dict(budget_fractions=(1, )),
    dict(budget_fractions=tuple(i / 10 for i in range(1, 10)))])
def test_invalid_parameters_are_refused(changes):
    with pytest.raises(ValueError):
        schedule(**changes)
