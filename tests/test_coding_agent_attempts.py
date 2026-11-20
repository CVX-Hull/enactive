"""The matched-run ledger (coding-agent-attempt/1) has the shape its reading rules on the routing page need.

Each row is one attempt; the two attempts at one leaf from one base commit are a pair, read within the routing
table's kind of work. The checks beyond the schema each protect the page's count of wins within one kind of work:
a leaf with one or three attempts has no pair to count; a kind of work the table does not have, or two kinds in
one pair, would split or misfile a count; and two blind preferences that do not complement each other mean the
labels were mapped back wrongly. The check refuses such a row here rather than when a default is about to move.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data/evaluation/coding-agent-attempts.jsonl'
SCHEMA = ROOT / 'schemas/coding-agent-attempt.schema.json'
ROUTING = ROOT / 'docs/operations/model-routing.md'
ROUTING_TABLE = '## Route by kind of work'


def kinds_of_work(page: str) -> set[str]:
    """The first cell of each body row of the routing table."""
    section = page.split(ROUTING_TABLE, 1)[1].split('\n## ', 1)[0]
    rows = [line for line in section.splitlines() if line.startswith('|')]
    return {row.split('|')[1].strip() for row in rows[2:]}


def problems(rows: list[dict], kinds: set[str]) -> list[str]:
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))
    found = [f'row {n}: {e.json_path}: {e.message}' for n, row in enumerate(rows, 1) for e in validator.iter_errors(row)]
    if found:
        return found
    pairs = defaultdict(list)
    for row in rows:
        if row['kind_of_work'] not in kinds:
            found.append(f"issue {row['issue']}: kind of work {row['kind_of_work']!r} is not a routing table row")
        pairs[row['issue'], row['base_commit']].append(row)
    for (issue, _), pair in pairs.items():
        if len(pair) != 2:
            found.append(f'issue {issue}: {len(pair)} attempts from one base commit; a matched run has two')
            continue
        first, second = pair
        if first['kind_of_work'] != second['kind_of_work']:
            found.append(f'issue {issue}: the two attempts name different kinds of work')
        if sorted(r['blind_preference'] for r in pair) not in (['not_preferred', 'preferred'], ['no_preference'] * 2):
            found.append(f'issue {issue}: the two blind preferences contradict each other')
    return found


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def attempt(**changes) -> dict:
    row = dict(schema='coding-agent-attempt/1', issue=900, kind_of_work='Bounded implementation from a written brief',
               base_commit='b' * 40, coding_agent='first agent', coding_agent_version='1.0.0', model='model-one',
               effort='high', date='2026-11-20', acceptance='passed', repairs=0, wall_seconds=1200,
               blind_preference='preferred', outcome='merged', false_report=None)
    return row | changes


def pair(**second) -> list[dict]:
    return [attempt(), attempt(coding_agent='second agent', model='model-two', effort=None, acceptance='failed',
                               repairs=2, blind_preference='not_preferred', outcome='discarded') | second]


KINDS = kinds_of_work(ROUTING.read_text())


def test_the_schema_is_valid_and_every_tracked_row_reads():
    Draft202012Validator.check_schema(json.loads(SCHEMA.read_text()))
    assert problems(read(LEDGER), KINDS) == []


def test_the_routing_table_supplies_the_kinds_of_work():
    assert 'Bounded implementation from a written brief' in KINDS and 'Kind of work here' not in KINDS


def test_a_matched_pair_reads():
    assert problems(pair(), KINDS) == []
    # Equal quality, both discarded: the reviewer saw no difference and the lead merged neither.
    neither = [attempt(blind_preference='no_preference', outcome='discarded'), pair(blind_preference='no_preference')[1]]
    assert problems(neither, KINDS) == []


@pytest.mark.parametrize(('rows', 'message'), [
    (pair()[:1], '1 attempts from one base commit'),
    (pair() + [attempt(coding_agent='third agent')], '3 attempts from one base commit'),
    (pair(kind_of_work='Review of code'), 'different kinds of work'),
    ([attempt(kind_of_work='Anything'), pair(kind_of_work='Anything')[1]], 'is not a routing table row'),
    ([attempt(false_report='')], 'should be non-empty'),
    (pair(blind_preference='preferred'), 'blind preferences contradict'),
    ([attempt(effort='extra-high')], "'extra-high' is not one of"),
    ([attempt(date='20 November 2026')], 'does not match'),
    ([attempt(wall_time=3)], 'Additional properties are not allowed'),
    ([{k: v for k, v in attempt().items() if k != 'outcome'}], "'outcome' is a required property"),
    ([attempt(schema='coding-agent-attempt/0')], "'coding-agent-attempt/1' was expected"),
])
def test_a_row_the_reading_rules_cannot_use_is_refused(rows, message):
    assert any(message in problem for problem in problems(rows, KINDS)), problems(rows, KINDS)
