"""The delegated-attempt ledger (coding-agent-attempt/3) has the shape its reading rules on the routing page need.

Each row is one delegated attempt. A row with a blind preference is one of a matched run's two attempts; the two at
one leaf from one base commit are a pair, read within the routing table's kind of work. A row with no blind
preference is a single delegation and needs no pair. The schema states each role's shape. The checks beyond it each
protect the page's count of wins within one kind of work: a matched leaf with one or three attempts has no pair to
count; a kind of work the table does not have, or two kinds in one pair, would split or misfile a count; and two
blind preferences that do not complement each other mean the labels were mapped back wrongly. The check refuses
such a row here rather than when a default is about to move.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import tomllib

import frontmatter
from jsonschema import Draft202012Validator
import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data/evaluation/coding-agent-attempts.jsonl'
SCHEMA = ROOT / 'schemas/coding-agent-attempt.schema.json'
ROUTING = ROOT / 'docs/operations/model-routing.md'
ROUTING_TABLE = '## Route by kind of work'
ROLE_DEFAULTS_TABLE = '## Roles and their default models'
EFFORT_LABEL = {'low': 'Low', 'medium': 'Medium', 'high': 'High', 'xhigh': 'Extra-high', 'max': 'Max'}
USAGE = dict(input_tokens=100, cached_input_tokens=20, cache_write_input_tokens=None, output_tokens=0)


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
        if row['blind_preference'] is not None:
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
    row = dict(schema='coding-agent-attempt/3', issue=900, kind_of_work='Bounded implementation from a written brief',
               base_commit='b' * 40, role='worker', coding_agent='first agent', coding_agent_version='1.0.0',
               model='model-one', effort='high', reason='Matched run: the routing row\'s first choice',
               date='2026-11-20', hand_back='handed_back', acceptance='passed', repairs=0, wall_seconds=1200,
               blind_preference='preferred', outcome='merged', findings=None, false_report=None,
               usage=None, brief_design=None, brief_extent=None, brief_check=None)
    return row | changes


def single(**changes) -> dict:
    """One delegation outside a matched run: no blind preference and so no pair."""
    return attempt(reason='The written brief is small and fully pinned', blind_preference=None) | changes


def review(**changes) -> dict:
    return single(role='reviewer', kind_of_work='Review of code', acceptance=None, outcome='used',
                  findings={'confirmed': 2, 'rejected': 1}) | changes


def pair(**second) -> list[dict]:
    return [attempt(), attempt(coding_agent='second agent', model='model-two', effort=None,
                               reason='Matched run: the challenger the lead named', acceptance='failed', repairs=2,
                               blind_preference='not_preferred', outcome='discarded') | second]


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


def test_a_single_delegation_reads_without_a_pair():
    assert problems([single()], KINDS) == []
    assert problems([review()], KINDS) == []
    # A locator that could not be started: no version to report, nothing handed back, nothing used.
    unstarted = review(role='locator', kind_of_work='Locating files and mechanical sweeps', coding_agent_version=None,
                       hand_back='failed_start', outcome='not_used', findings=None)
    assert problems([unstarted], KINDS) == []


def test_an_attempt_can_record_usage_and_brief_properties():
    row = single(usage=USAGE, brief_design='pinned', brief_extent='medium', brief_check=True)
    assert problems([row], KINDS) == []


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
    ([attempt(schema='coding-agent-attempt/0')], "'coding-agent-attempt/3' was expected"),
    ([attempt(schema='coding-agent-attempt/1')], "'coding-agent-attempt/3' was expected"),
    ([attempt(schema='coding-agent-attempt/2')], "'coding-agent-attempt/3' was expected"),
    ([single(usage={k: v for k, v in USAGE.items() if k != 'input_tokens'})], "'input_tokens' is a required property"),
    ([single(usage=USAGE | {'input_tokens': -1})], '-1 is less than the minimum of 0'),
    ([single(usage=USAGE | {'total_tokens': 120})], "'total_tokens' was unexpected"),
    ([single(brief_design='fixed')], "'fixed' is not one of ['pinned', 'open', None]"),
    ([review(outcome='merged')], "'merged' is not one of ['used', 'not_used']"),
    ([single(findings={'confirmed': 1, 'rejected': 0})], "is not of type 'null'"),
    ([review(role='explorer')], "is not of type 'null'"),
    (pair(acceptance=None), "None is not of type 'string'"),
])
def test_a_row_the_reading_rules_cannot_use_is_refused(rows, message):
    assert any(message in problem for problem in problems(rows, KINDS)), problems(rows, KINDS)


def role_default_cells(page: str) -> list[list[str]]:
    section = page.split(ROLE_DEFAULTS_TABLE, 1)[1].split('\n## ', 1)[0]
    rows = [line for line in section.splitlines() if line.startswith('|')]
    return [[cell.strip() for cell in row.strip('|').split('|')] for row in rows[2:]]


def _parse_wrapper_cell(cell: str) -> tuple[str, str, str | None]:
    match = re.fullmatch(r'`([^`]+)`:\s*(?:alias\s+)?`([^`]+)`(?:\s+at\s+([A-Za-z-]+))?', cell)
    assert match is not None, f'unparseable role-defaults cell: {cell!r}'
    return match.group(1), match.group(2), match.group(3)


def test_role_wrappers_match_routing_table_and_tool_policy():
    rows = role_default_cells(ROUTING.read_text())
    assert len(rows) == 4
    seen_claude, seen_codex, seen_agy = set(), set(), set()
    for _, claude_cell, codex_cell, agy_cell in rows:
        name, model, effort = _parse_wrapper_cell(claude_cell)
        seen_claude.add(name)
        meta = frontmatter.loads((ROOT / '.claude/agents' / f'{name}.md').read_text()).metadata
        assert meta['name'] == name and meta['model'] == model
        assert (EFFORT_LABEL[meta['effort']] if 'effort' in meta else None) == effort

        name, model, effort = _parse_wrapper_cell(codex_cell)
        seen_codex.add(name)
        data = tomllib.loads((ROOT / '.codex/agents' / f'{name}.toml').read_text())
        assert data['name'] == name and data['model'] == model
        assert EFFORT_LABEL[data['model_reasoning_effort']] == effort

        name, alias, effort = _parse_wrapper_cell(agy_cell)
        seen_agy.add(name)
        meta = frontmatter.loads((ROOT / '.agents/agents' / name / 'agent.md').read_text()).metadata
        assert meta['name'] == name and meta['model'] == alias and effort is None
        tools = meta.get('tools')
        assert isinstance(tools, list) and tools

    assert seen_claude == {p.stem for p in (ROOT / '.claude/agents').glob('*.md')}
    assert seen_codex == {p.stem for p in (ROOT / '.codex/agents').glob('*.toml')}
    assert seen_agy == {p.parent.name for p in (ROOT / '.agents/agents').glob('*/agent.md')}
