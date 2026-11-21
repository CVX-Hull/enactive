"""The type list in the curator's session brief: counts, the unused flag and nearest types (#833).

Risk: R-REGRESSION. The curator proposes types from this list before the paid live curator
run; a wrong count, a missing flag or an unstable pair order would mislead it silently.
The portable tests use real Git repositories in tmp_path; the stand-in test runs the real
host through the proxy and the sandbox with no network and no spend.
"""
from __future__ import annotations

import json

from harness.curator import session, type_usage
from harness.curator.session import run_session
from tests.curator_stand_in import StandIn
from tests.test_curator_gate import fact, make_repo, run, submission
from tests.test_curator_host import native, session_config, world  # noqa: F401 - world is a fixture


def kind(name, fields):
    return {'schema': 'curator-type/1', 'name': name, 'description': 'd', 'fields': fields}


SECTION = '''\
### Types

Each published type with its fields and its count of current facts; a type with no current fact is flagged unused. \
Check this list before any `add_type`: reuse a type that fits instead of adding a near duplicate.

- 'container' (fields 'holds', 'capacity'): 2 current facts
- 'control' (fields 'input', 'effect'): 1 current fact
- 'hazard' (no fields): no current fact (unused)
- 'key_binding' (fields 'input', 'effect'): no current fact (unused)
- 'storage_container' (fields 'holds'): no current fact (unused)

### Nearest types

Two types are near when the lower-cased words of their names and field names overlap by at least 1/3 \
(shared words divided by all words of the two); at most 10 pairs are shown, closest first, then by name.

- 'container' and 'storage_container' share container, holds (2 of 4 words)
- 'control' and 'key_binding' share effect, input (2 of 5 words)
'''


def synthetic(tmp_path):
    """v1 adds five types and four facts; v2 retires the storage_container fact."""
    repo = make_repo(tmp_path)
    types = [kind('container', ['holds', 'capacity']), kind('storage_container', ['holds']),
             kind('control', ['input', 'effect']), kind('key_binding', ['input', 'effect']), kind('hazard', [])]
    facts = [fact('f1', 'container'), fact('f2', 'container'), fact('f3', 'control'), fact('f4', 'storage_container')]
    first = submission(tmp_path, [*({'op': 'add_type', 'type': t} for t in types),
                                  *({'op': 'add_fact', 'fact': f} for f in facts)], name='seed')
    assert run(repo, first)['version'] == 'v1'
    second = submission(tmp_path, [{'op': 'retire_fact', 'id': 'f4', 'reason': 'wrong', 'citations': ['frame-1']}],
                        name='retire', base_version='v1')
    assert run(repo, second)['version'] == 'v2'
    return repo


def test_the_brief_lists_counts_flags_unused_types_and_names_nearest_pairs(tmp_path):
    repo = synthetic(tmp_path)
    text = session.brief(repo, 'v2', {'sessions': []}, [])
    assert SECTION in text
    assert text.index('## Hints and flagged types') < text.index('### Types') < text.index('## Close-out')
    # Counts are of the version the session is given: before the retirement storage_container had a fact.
    earlier = session.brief(repo, 'v1', {'sessions': []}, [])
    assert "- 'storage_container' (fields 'holds'): 1 current fact" in earlier


def test_an_empty_store_says_there_are_no_types_or_pairs(tmp_path):
    text = session.brief(make_repo(tmp_path), 'v0', {'sessions': []}, [])
    assert '### Types' in text and 'No published types.' in text
    assert text.split('### Nearest types', 1)[1].split('## Close-out')[0].strip().endswith('None.')


def test_the_overlap_threshold_is_inclusive_at_one_third_and_ignores_case_and_separators():
    at = [kind('Alpha', ['shared']), kind('beta', ['SHARED'])]  # {alpha, shared} and {beta, shared}: 1/3
    below = [kind('alpha', ['shared']), kind('beta', ['shared', 'other'])]  # 1/4
    assert type_usage.nearest(at) == [('Alpha', 'beta', ('shared',), 3)]
    assert type_usage.nearest(below) == []
    assert type_usage.words(kind('Item-Location', ['item_count'])) == {'item', 'location', 'count'}


def test_pairs_are_capped_and_ordered_closest_first_then_by_name():
    types = [kind(f'type{index:02d}', ['common', 'words', 'here']) for index in range(12)]
    types.append(kind('closest_a', ['x', 'y', 'z']))
    types.append(kind('closest_b', ['x', 'y', 'z']))  # 4 of 6 shared, above the others' 3 of 5
    pairs = type_usage.nearest(list(reversed(types)))
    assert len(pairs) == type_usage.MAX_PAIRS
    assert pairs[0][:2] == ('closest_a', 'closest_b')
    assert pairs == type_usage.nearest(types)
    assert [p[:2] for p in pairs[1:]] == sorted(p[:2] for p in pairs[1:])


def test_curator_chosen_names_are_escaped_in_the_type_list():
    lines = type_usage.section([kind('x\n# Injected', ['`tick`'])], [])
    assert not any(line.startswith('# Injected') for line in lines)
    assert "- 'x\\n# Injected' (fields '`tick`'): no current fact (unused)" in lines


@native
def test_a_stand_in_session_is_shown_the_type_list(tmp_path, world):
    repo, trace = world
    with StandIn() as stand_in:
        for _ in range(2):  # the first admission publishes type control and fact f1; the second reads them
            proxy, config = session_config(tmp_path, stand_in.url)
            try:
                record = run_session(repo, trace, config)
            finally:
                proxy.close()
        second = stand_in.requests[-3]['body']  # the second session's first request: the brief is its first user message
    assert record['manifest']['lifecycle']['state'] == 'sealed'
    brief = (repo.state/'sessions'/record['manifest']['id']/'brief.md').read_text()
    assert "- 'control' (fields 'input', 'effect'): 1 current fact" in brief
    assert '### Nearest types' in brief and type_usage.RULE in brief
    assert "- 'control' (fields 'input', 'effect'): 1 current fact" in json.dumps(second)
