"""Exact synthetic belief views and supplied-origin revision bookkeeping."""
from fractions import Fraction
from numbers import Rational


def evidence_views(r, s, W, a):
    """Map finite rational fixture inputs to matched opinion and Beta views."""
    if any(isinstance(value, bool) or not isinstance(value, Rational) for value in (r, s, W, a)):
        raise ValueError('inputs must be exact rational values')
    r, s, W, a = map(Fraction, (r, s, W, a))
    if r < 0 or s < 0 or W <= 0 or not 0 < a < 1:
        raise ValueError('inputs outside the finite evidence domain')
    total = r + s + W
    b, d, u = r / total, s / total, W / total
    alpha, beta = r + W * a, s + W * (1 - a)
    return {'opinion': (b, d, u, a), 'beta': (alpha, beta),
            'opinion_mean': b + a * u, 'beta_mean': alpha / (alpha + beta)}


def active_alternatives(alternatives, active_origins):
    """Return distinct supported nonempty conjunctions of supplied origin IDs."""
    active = frozenset(active_origins)
    clauses = frozenset(frozenset(clause) for clause in alternatives)
    if frozenset() in clauses:
        raise ValueError('an alternative must contain at least one origin')
    return frozenset(clause for clause in clauses if clause <= active)


def revision_state(positive_alternatives, negative_alternatives, active_origins):
    """Classify supplied positive and negative supports without assigning weights."""
    active = frozenset(active_origins)
    positive = bool(active_alternatives(positive_alternatives, active))
    negative = bool(active_alternatives(negative_alternatives, active))
    return {(True, False): 'support-only', (False, True): 'refutation-only',
            (True, True): 'conflicting', (False, False): 'unknown'}[positive, negative]
