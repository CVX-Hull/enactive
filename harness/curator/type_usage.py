"""Type usage for the curator's session brief: counts, unused types and nearest types (#833).

Software-written and deterministic. It counts current facts per published type, flags a type
with no current fact, and names pairs of types that are near by one stated overlap rule on the
words of their names and field names. It calls no model and enforces nothing; the curator
decides. See docs/design/curator-session.md#the-type-list-in-the-brief.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations
import re

from .gate import current

NEAR_AT_LEAST = Fraction(1, 3)
MAX_PAIRS = 10
RULE = ('Two types are near when the lower-cased words of their names and field names overlap by at '
        f'least {NEAR_AT_LEAST.numerator}/{NEAR_AT_LEAST.denominator} (shared words divided by all words of the two); '
        f'at most {MAX_PAIRS} pairs are shown, closest first, then by name.')
_WORD = re.compile(r'[^\W_]+')


def words(kind: dict) -> frozenset[str]:
    """The lower-cased letter-and-digit runs of a type's name and field names."""
    text = ' '.join([kind['name'], *kind['fields']]).lower()
    return frozenset(_WORD.findall(text))


def counts(types: list[dict], facts: list[dict]) -> dict[str, int]:
    """Current facts per published type name; a type with no current fact counts 0."""
    found = {kind['name']: 0 for kind in types}
    for item in facts:
        if current(item) and item.get('type') in found:
            found[item['type']] += 1
    return found


def nearest(types: list[dict]) -> list[tuple[str, str, tuple[str, ...], int]]:
    """Pairs at or above the threshold, capped: (first name, second name, shared words, all words)."""
    vocab = {kind['name']: words(kind) for kind in types}
    pairs = []
    for first, second in combinations(sorted(vocab), 2):
        union = vocab[first] | vocab[second]
        shared = vocab[first] & vocab[second]
        if union and Fraction(len(shared), len(union)) >= NEAR_AT_LEAST:
            pairs.append((first, second, tuple(sorted(shared)), len(union)))
    pairs.sort(key=lambda pair: (-Fraction(len(pair[2]), pair[3]), pair[0], pair[1]))
    return pairs[:MAX_PAIRS]


def _facts(count: int) -> str:
    return 'no current fact (unused)' if count == 0 else f'{count} current fact' + ('' if count == 1 else 's')


def section(types: list[dict], facts: list[dict]) -> list[str]:
    """Brief lines for the type list. Curator-chosen names and fields are shown `repr`-escaped."""
    lines = ['### Types', '',
             'Each published type with its fields and its count of current facts; a type with no current fact '
             'is flagged unused. Check this list before any `add_type`: reuse a type that fits instead of '
             'adding a near duplicate.', '']
    used = counts(types, facts)
    lines += [f"- {name!r} ({'fields ' + ', '.join(repr(f) for f in kind['fields']) if kind['fields'] else 'no fields'}): "
              f'{_facts(used[name])}'
              for name, kind in sorted((kind['name'], kind) for kind in types)] or ['No published types.']
    pairs = nearest(types)
    lines += ['', '### Nearest types', '', RULE, '']
    lines += [f'- {first!r} and {second!r} share {", ".join(shared)} ({len(shared)} of {total} words)'
              for first, second, shared, total in pairs] or ['None.']
    return lines
