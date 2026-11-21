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
LIST_BYTES = 32768  # the type rows shown; the host refuses a brief over 262,144 bytes
RULE = ("A type's words are the distinct lower-cased runs of letters and digits in its name and field names. "
        f'Two types are near when the words they share are at least {NEAR_AT_LEAST.numerator}/{NEAR_AT_LEAST.denominator} '
        f'of all the words of the two; at most {MAX_PAIRS} pairs are shown, closest first, then in order of the '
        'first name and then the second.')
_WORD = re.compile(r'[^\W_]+')


def words(kind: dict) -> frozenset[str]:
    """The lower-cased letter-and-digit runs of a type's name and field names."""
    text = ' '.join([kind['name'], *kind['fields']]).lower()
    return frozenset(_WORD.findall(text))


def counts(types: list[dict], facts: list[dict]) -> dict[str, int]:
    """Current facts per published type name; a type with no current fact counts 0."""
    found = {kind['name']: 0 for kind in types}
    for item in facts:
        if current(item) and isinstance(item.get('type'), str) and item['type'] in found:
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
    rows = [f"- {name!r} ({'fields ' + ', '.join(repr(f) for f in kind['fields']) if kind['fields'] else 'no fields'}): "
            f'{_facts(used[name])}'
            for name, kind in sorted(((kind['name'], kind) for kind in types), key=lambda pair: pair[0])]
    shown, size = 0, 0
    for row in rows:  # whole rows up to the byte limit, so a large type list cannot push the brief past the host's limit
        size += len(row.encode()) + 1
        if size > LIST_BYTES:
            break
        shown += 1
    lines += rows[:shown] or ([] if rows else ['No published types.'])
    if shown < len(rows):
        lines += [f'{len(rows) - shown} more types are not shown here; read the published types before any `add_type`.']
    pairs = nearest(types)
    lines += ['', '### Nearest types', '', RULE, '']
    for first, second, shared, total in pairs:
        row = f'- {first!r} and {second!r} share {", ".join(shared)} ({len(shared)} of {total} words)'
        size += len(row.encode()) + 1
        if size > 2 * LIST_BYTES:
            lines.append('Further pairs are not shown here.')
            break
        lines.append(row)
    if not pairs:
        lines.append('None.')
    return lines
