"""Deterministic tag and subject usage with word overlap for the curator's session brief."""
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


def subject_counts(records: list[dict]) -> dict[str, int]:
    return dict(Counter(record['subject'] for record in records
                        if current(record) and record.get('record') == 'fact' and 'subject' in record))


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
    active = [record for record in records if current(record)]
    total = len(active)
    used = counts(records)
    scope_tokens = {
        str(val).lower()
        for record in active
        for key, val in record.get('scope', {}).items()
        for val in (key, val)
    }
    lines = ['### Tags', '', f'Counts include {total} current facts and articles (`df/N`).', '']
    rows = []
    for name, n in sorted(used.items()):
        flags = []
        if total >= 2 and n * 2 > total:
            flags.append('majority >N/2')
        if name in scope_tokens:
            flags.append('overlaps scope')
        suffix = f' [{", ".join(flags)}]' if flags else ''
        rows.append(f'- {name!r}: {n}/{total}{suffix}' if total else f'- {name!r}: {n}')
    size = 0
    for index, row in enumerate(rows):
        size += len(row.encode()) + 1
        if size > LIST_BYTES:
            lines.append(f'{len(rows) - index} more tags in current-facts.jsonl.')
            break
        lines.append(row)
    if not rows:
        lines.append('No current tags.')

    facts_total = sum(1 for record in active if record.get('record') == 'fact')
    subjects = subject_counts(records)
    if subjects:
        lines += ['', '### Subjects', '']
        subj_rows = []
        for name, n in sorted(subjects.items(), key=lambda kv: (-kv[1], kv[0])):
            flag = ' [majority >N/2]' if facts_total >= 2 and n * 2 > facts_total else ''
            subj_rows.append(f'- {name!r}: {n}/{facts_total}{flag}')
        lines.extend(subj_rows[:25])

    pairs = nearest(used)
    lines += ['', '### Nearest tags', '', RULE, '']
    lines += [f'- {first!r} and {second!r} share {", ".join(shared)} ({len(shared)} of {total_w} words)'
              for first, second, shared, total_w in pairs] or ['None.']
    return lines
