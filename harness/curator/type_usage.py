"""Deterministic tag usage and word overlap for the curator's session brief."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from itertools import combinations

from .check import current

NEAR_AT_LEAST = Fraction(1, 3)
MAX_PAIRS = 10
LIST_BYTES = 32768
RULE = ('Two tags are near when shared words make up at least one third of their distinct words. '
        f'Up to {MAX_PAIRS} pairs are shown, closest first, then alphabetically.')


def words(tag: str) -> frozenset[str]:
    return frozenset(tag.split('-'))


def counts(records: list[dict]) -> dict[str, int]:
    return dict(Counter(tag for record in records if current(record) for tag in record['tags']))


def nearest(tags) -> list[tuple[str, str, tuple[str, ...], int]]:
    vocab = {tag: words(tag) for tag in tags}
    pairs = []
    for first, second in combinations(sorted(vocab), 2):
        union = vocab[first] | vocab[second]
        shared = vocab[first] & vocab[second]
        if Fraction(len(shared), len(union)) >= NEAR_AT_LEAST:
            pairs.append((first, second, tuple(sorted(shared)), len(union)))
    pairs.sort(key=lambda pair: (-Fraction(len(pair[2]), pair[3]), pair[0], pair[1]))
    return pairs[:MAX_PAIRS]


def section(records: list[dict]) -> list[str]:
    used = counts(records)
    lines = ['### Tags', '', 'Counts include current facts and articles.', '']
    rows = [f'- {name!r}: {n}' for name, n in sorted(used.items())]
    size = 0
    for index, row in enumerate(rows):
        size += len(row.encode()) + 1
        if size > LIST_BYTES:
            lines.append(f'{len(rows) - index} more tags in current-facts.jsonl.')
            break
        lines.append(row)
    if not rows:
        lines.append('No current tags.')
    pairs = nearest(used)
    lines += ['', '### Nearest tags', '', RULE, '']
    lines += [f'- {first!r} and {second!r} share {", ".join(shared)} ({len(shared)} of {total} words)'
              for first, second, shared, total in pairs] or ['None.']
    return lines
