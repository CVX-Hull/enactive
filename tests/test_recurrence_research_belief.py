from fractions import Fraction as F
from itertools import product

import pytest

from tools.recurrence_research.belief import active_alternatives, evidence_views, revision_state


def test_known_evidence_views():
    assert evidence_views(0, 0, 2, F(1, 2)) == {
        'opinion': (F(0), F(0), F(1), F(1, 2)), 'beta': (F(1), F(1)),
        'opinion_mean': F(1, 2), 'beta_mean': F(1, 2),
    }
    assert evidence_views(3, 1, 2, F(1, 3)) == {
        'opinion': (F(1, 2), F(1, 6), F(1, 3), F(1, 3)),
        'beta': (F(11, 3), F(7, 3)), 'opinion_mean': F(11, 18), 'beta_mean': F(11, 18),
    }


def test_exact_projection_grid():
    for r, s, W, a in product((F(0), F(1, 2), F(3)), (F(0), F(2, 3)),
                              (F(1, 2), F(2)), (F(1, 3), F(1, 2), F(2, 3))):
        views = evidence_views(r, s, W, a)
        b, d, u, base = views['opinion']
        alpha, beta = views['beta']
        assert all(isinstance(value, F) for value in (*views['opinion'], alpha, beta))
        assert b + d + u == 1 and alpha > 0 and beta > 0
        assert views['opinion_mean'] == b + base * u == alpha / (alpha + beta) == views['beta_mean']


@pytest.mark.parametrize('args', [(-1, 0, 2, F(1, 2)), (0, -1, 2, F(1, 2)),
                                  (0, 0, 0, F(1, 2)), (0, 0, -1, F(1, 2)),
                                  (0, 0, 2, 0), (0, 0, 2, 1),
                                  (0, 0, 2, F(-1, 2)), (0, 0, 2, F(3, 2)),
                                  (0.5, 0, 2, F(1, 2)), (0, 0, 2, float('inf')),
                                  (0, 0, 2, float('nan')), (True, 0, 2, F(1, 2))])
def test_invalid_domain(args):
    with pytest.raises(ValueError):
        evidence_views(*args)


def test_balanced_strength_does_not_resolve_conflict():
    prior = evidence_views(0, 0, 2, F(1, 2))
    balanced = evidence_views(100, 100, 2, F(1, 2))
    assert prior['opinion_mean'] == balanced['opinion_mean'] == F(1, 2)
    assert prior['opinion'][2] == 1 and balanced['opinion'][2] == F(1, 101)
    assert revision_state([['a']], [['a']], ['a']) == 'conflicting'
    assert revision_state([], [], []) == 'unknown'


def test_alternatives_repetition_permutation_and_retraction():
    clauses = [['a', 'b'], ['a', 'c']]
    expected = frozenset({frozenset({'a', 'b'}), frozenset({'a', 'c'})})
    assert active_alternatives(clauses, ['a', 'b', 'c']) == expected
    assert active_alternatives([['c', 'a', 'a'], ['b', 'a'], ['a', 'b']],
                               ['c', 'b', 'a', 'a']) == expected
    assert active_alternatives(clauses, ['a', 'c']) == frozenset({frozenset({'a', 'c'})})
    assert active_alternatives(clauses, ['b', 'c']) == frozenset()
    assert active_alternatives([], []) == frozenset()
    with pytest.raises(ValueError):
        active_alternatives([['a'], []], ['a'])


@pytest.mark.parametrize(('active', 'expected'), [(['p'], 'support-only'), (['n'], 'refutation-only'),
                                               (['p', 'n'], 'conflicting'), ([], 'unknown')])
def test_revision_states(active, expected):
    assert revision_state([['p']], [['n']], active) == expected
