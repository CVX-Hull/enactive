"""Shared-shape validation for Batch 1 (`curator-fact/6`, `curator-submission/3`,
`delivered-knowledge/4` fixtures, and synthetic two-world/two-lineage repositories).
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
import pytest

from harness.player.contracts import PlayerError
from harness.player.knowledge import Knowledge
from harness.player_view import actor_result

from tests.synthetic_knowledge_repo import (
    LINEAGE_A,
    LINEAGE_B,
    WORLD_ALPHA,
    SyntheticKnowledgeBuilder,
    build_cycle_and_withholding_repo,
    build_falsity_propagation_repo,
    build_nested_cut_repo,
    build_parent_target_repo,
    build_restore_repo,
    build_two_world_two_lineage_repo,
    frame_id,
    session_hex,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = REPO_ROOT / 'schemas'
FIXTURES = REPO_ROOT / 'tests' / 'fixtures' / 'delivered-knowledge-4'

SID1 = session_hex(1)
SID2 = session_hex(2)
F1 = frame_id(SID1, 1)
F2 = frame_id(SID1, 2)

EXPECTED_VALID_FIXTURES = {
    'bom-only-nonblank.json',
    'empty.json',
    'full-graph-and-history.json',
    'high-session-alias.json',
    'integral-json-number.json',
    'max-safe-integer-version.json',
    'minimal.json',
    'standalone-facts-only.json',
}

EXPECTED_INVALID_FIXTURES = {
    'state-key-collides-with-public-id.json',
    'frame-clock-outside-citations.json',
    'depiction-outside-citations.json',
    'position-with-both-clock-fields.json',
    'anchor-without-anchor-display.json',
    'state-without-state-key.json',
    'article-cites-missing-fact.json',
    'article-raw-world-label.json',
    'empty-version-with-records.json',
    'extra-top-level-key.json',
    'fractional-step.json',
    'lone-surrogate-order.json',
    'history-ended-revision-id.json',
    'history-overlap-ended-retracted.json',
    'history-replaced-target-outside-public.json',
    'invalid-lifecycle-state.json',
    'invalid-revision-prefix.json',
    'invalid-tag-format.json',
    'lineage-axis-in-scope.json',
    'link-outside-public-set.json',
    'malformed-citation-source-id.json',
    'missing-history.json',
    'old-schema-v3.json',
    'raw-session-name-in-coverage.json',
    'raw-session-name-in-last-confirmed.json',
    'self-link.json',
    'stale-citation-outside-history.json',
    'terminal-newline-version.json',
    'unbound-with-branch-relation.json',
    'unsafe-integer-step.json',
    'unsafe-integer-version.json',
    'whitespace-control-separators-lead.json',
    'whitespace-nel-title.json',
    'world-bound-null-branch-relation.json',
}


def _load_validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / name).read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _pos(step: int = 10) -> dict:
    return {'session': 'lin-a-a01-run', 'actor': '001', 'step': step, 'order': [1, '001', step]}


def _stored_fact(**overrides) -> dict:
    base = {
        'schema': 'curator-fact/6',
        'record': 'fact',
        'id': 'boil-water',
        'statement_kind': 'observation',
        'tags': ['water', 'fire'],
        'text': 'Boiling murky water yields clean water.',
        'scope': {'game': 'example'},
        'links': [],
        'citations': [F1],
        'seen': _pos(10),
        'valid_from': _pos(10),
        'valid_to': None,
        'lifecycle_state': 'active',
        'stale_citations': [],
        'needs_review': False,
        'published_in': 'v1',
        'session': 'curator-v1',
    }
    base.update(overrides)
    return base


def _stored_article(**overrides) -> dict:
    base = {
        'schema': 'curator-fact/6',
        'record': 'article',
        'id': 'water-guide@v1',
        'slug': 'water-guide',
        'title': 'Water guide',
        'lead': 'Boil murky water before drinking.',
        'body': [{'text': 'Boiling murky water yields clean water.', 'facts': ['boil-water']}],
        'tags': ['water'],
        'scope': {'game': 'example'},
        'links': [],
        'last_confirmed': _pos(10),
        'valid_from': _pos(10),
        'valid_to': None,
        'lifecycle_state': 'active',
        'stale_citations': [],
        'needs_review': False,
        'published_in': 'v1',
        'session': 'curator-v1',
    }
    base.update(overrides)
    return base


def _submitted_fact(**overrides) -> dict:
    base = {
        'schema': 'curator-fact/6',
        'record': 'fact',
        'id': 'boil-water',
        'statement_kind': 'observation',
        'tags': ['water'],
        'text': 'Boiling murky water yields clean water.',
        'scope': {},
        'links': [],
        'citations': [F1],
    }
    base.update(overrides)
    return base


def _submission(changes: list[dict], **overrides) -> dict:
    base = {
        'schema': 'curator-submission/3',
        'base_version': 'v0',
        'summary': 'Add initial knowledge.',
        'changes': changes,
    }
    base.update(overrides)
    return base


def test_schemas_are_valid_draft_2020_12():
    _load_validator('curator-fact.schema.json')
    _load_validator('curator-submission.schema.json')


def test_curator_fact_schema_accepts_all_valid_variants():
    validator = _load_validator('curator-fact.schema.json')
    valid_records = [
        _stored_fact(),
        _stored_fact(
            subject='water treatment',
            scope={'game': 'example', 'region': ' '},  # single printable ASCII space is legal
            when='needs a lit heat source',
            retagged=[{'from': ['water'], 'to': ['water', 'fire'], 'version': 'v2'}],
        ),
        _stored_fact(
            id='camp-fire', statement_kind='state', state_key='camp-hearth',
            scope={'game': 'example', 'world': 'world-alpha', 'ruleset': 'standard'},
            lineages=['lin-a'],
        ),
        _stored_fact(lifecycle_state='superseded', superseded_by=['boil-water-2'], superseded_reason='restated'),
        _stored_fact(lifecycle_state='retracted', superseded_by=['boil-water-fixed'], superseded_reason='corrected'),
        _stored_fact(
            lifecycle_state='retracted',
            retired={
                'reason': 'Observed false.', 'reason_kind': 'wrong',
                'citations': [F2], 'published_in': 'v2', 'session': 'curator-v2',
            },
        ),
        _stored_fact(
            id='camp-fire', statement_kind='state', state_key='camp-hearth',
            scope={'game': 'example', 'world': 'world-alpha'},
            lineages=['lin-a'],
            lifecycle_state='ended',
            valid_to=_pos(20),
            retired={
                'reason_kind': 'ended',
                'events': [{
                    'reason': 'Fire went out.', 'end': 'transition',
                    'end_citations': [F2],
                    'valid_to': _pos(20), 'published_in': 'v2', 'session': 'curator-v2',
                }],
            },
        ),
        _stored_fact(
            id='camp-fire', statement_kind='state', state_key='camp-hearth',
            scope={'game': 'example', 'world': 'world-alpha'},
            lineages=['lin-a'],
            lifecycle_state='ended',
            valid_to=None,
            retired={
                'reason_kind': 'ended',
                'events': [
                    {
                        'reason': 'Ended on branch B.', 'end': 'transition',
                        'end_citations': [frame_id(SID2, 1)], 'citations': [],
                        'valid_to': _pos(20), 'published_in': 'v2', 'session': 'curator-v2',
                    },
                    {
                        'reason': 'Ended on branch A.', 'end': 'absence',
                        'end_citations': [F2], 'citations': [],
                        'valid_to': _pos(30), 'published_in': 'v3', 'session': 'curator-v3',
                    },
                ],
            },
        ),
        _stored_article(),
        _stored_article(
            scope={'game': 'example', 'world': 'world-alpha'},
            lineages=['lin-a', None],
            lifecycle_state='superseded',
            superseded_by=['water-guide@v2'],
        ),
        _stored_article(
            lifecycle_state='ended',
            retired={'reason': 'Merged.', 'reason_kind': 'editorial', 'published_in': 'v2', 'session': 'curator-v2'},
        ),
        _stored_article(
            lifecycle_state='retracted',
            retired={'reason': 'Wrong premise.', 'reason_kind': 'wrong', 'published_in': 'v2', 'session': 'curator-v2'},
        ),
    ]
    for record in valid_records:
        errors = list(validator.iter_errors(record))
        assert not errors, f'{record.get("id")}: {errors}'


@pytest.mark.parametrize('mutator', [
    lambda r: r.__setitem__('schema', 'curator-fact/4'),
    lambda r: r.__setitem__('type', 'mechanic'),
    lambda r: r.__setitem__('known', 'observed'),
    lambda r: r.__setitem__('id', 'Bad_ID'),
    lambda r: r.__setitem__('id', 'abc\n'),
    lambda r: r.__setitem__('published_in', 'v1\n'),
    lambda r: r.__setitem__('citations', ['frame-1']),
    lambda r: r.__setitem__('citations', [f'{SID1}-0001']),
    lambda r: r.__setitem__('citations', [f'{F1}\n']),
    lambda r: r.__setitem__('tags', ['NotKebab']),
    lambda r: r.__setitem__('tags', ['water\n']),
    lambda r: r.__setitem__('tags', [f't{i}' for i in range(9)]),
    lambda r: r['scope'].__setitem__('axis\n', 'val'),
    lambda r: r['scope'].__setitem__('axis', 'line1\nline2'),
    lambda r: r.__setitem__('statement_kind', 'state'),  # missing scope.world
    lambda r: r.__setitem__('lineages', ['lin-a']),  # unbound with lineages
    lambda r: r['scope'].__setitem__('world', 'world-alpha'),  # bound without lineages
    lambda r: (r.__setitem__('superseded_by', ['x']), r.__setitem__('retired', {
        'reason': 'x', 'reason_kind': 'wrong', 'citations': [F2], 'published_in': 'v2', 'session': 'curator-v2',
    })),
    lambda r: r.__setitem__('lifecycle_state', 'superseded'),  # missing superseded_by
    lambda r: (r.__setitem__('lifecycle_state', 'retracted'), r.__setitem__('superseded_by', ['a', 'b'])),  # corrected > 1
    lambda r: r.__setitem__('valid_to', _pos(20)),  # non-null valid_to while active
    lambda r: (
        r.__setitem__('lifecycle_state', 'ended'),
        r.__setitem__('valid_to', _pos(20)),  # unbound fact must have valid_to=null
        r.__setitem__('retired', {
            'reason_kind': 'ended',
            'events': [{'reason': 'Ended.', 'end': 'transition', 'end_citations': [F2],
                        'valid_to': None, 'published_in': 'v2', 'session': 'curator-v2'}],
        }),
    ),
    lambda r: (
        r.__setitem__('lifecycle_state', 'ended'),
        r.__setitem__('valid_to', None),
        r.__setitem__('retired', {
            'reason_kind': 'ended',
            'events': [{'reason': 'Ended.', 'end': 'transition', 'end_citations': [F2],
                        'valid_to': _pos(20), 'published_in': 'v2', 'session': 'curator-v2'}],  # unbound event valid_to must be null
        }),
    ),
    lambda r: (
        r['scope'].__setitem__('world', 'world-alpha'),
        r.__setitem__('lineages', ['lin-a', 'lin-b']),
        r.__setitem__('lifecycle_state', 'ended'),
        r.__setitem__('valid_to', _pos(20)),  # multi-lineage fact must have valid_to=null
        r.__setitem__('retired', {
            'reason_kind': 'ended',
            'events': [{'reason': 'Ended.', 'end': 'transition', 'end_citations': [F2],
                        'valid_to': None, 'published_in': 'v2', 'session': 'curator-v2'}],
        }),
    ),
    lambda r: (
        r['scope'].__setitem__('world', 'world-alpha'),
        r.__setitem__('lineages', ['lin-a']),
        r.__setitem__('lifecycle_state', 'ended'),
        r.__setitem__('valid_to', _pos(20)),  # multiple end events must have top-level valid_to=null
        r.__setitem__('retired', {
            'reason_kind': 'ended',
            'events': [
                {'reason': 'E1.', 'end': 'transition', 'end_citations': [F2],
                 'valid_to': _pos(20), 'published_in': 'v2', 'session': 'curator-v2'},
                {'reason': 'E2.', 'end': 'absence', 'end_citations': [frame_id(SID2, 1)],
                 'valid_to': _pos(30), 'published_in': 'v3', 'session': 'curator-v3'},
            ],
        }),
    ),
    lambda r: r.__setitem__('links', [{'rel': 'supersedes', 'target': 'other'}]),
    lambda r: r.__setitem__('when', '   '),
])
def test_curator_fact_schema_rejects_invalid_facts(mutator):
    validator = _load_validator('curator-fact.schema.json')
    record = _stored_fact()
    mutator(record)
    assert not validator.is_valid(record)


def test_curator_submission_schema_accepts_every_operation():
    validator = _load_validator('curator-submission.schema.json')
    ops = [
        {'op': 'add_fact', 'fact': _submitted_fact(scope={'region': ' '})},
        {
            'op': 'add_fact',
            'fact': _submitted_fact(
                id='camp-fire', statement_kind='state', state_key='camp-hearth', binds=['world'],
                when='while fuel lasts',
            ),
        },
        {
            'op': 'add_article',
            'article': {
                'schema': 'curator-fact/6', 'record': 'article', 'slug': 'water-guide',
                'title': 'Water guide', 'lead': 'Boil water.',
                'body': [{'text': 'Boil murky water.', 'facts': ['boil-water']}],
                'tags': ['water'], 'links': [],
            },
        },
        {
            'op': 'supersede_fact', 'ids': ['camp-fire'], 'reason_kind': 'restated',
            'fact': {
                'schema': 'curator-fact/6', 'record': 'fact', 'id': 'camp-fire-2',
                'statement_kind': 'state', 'state_key': 'camp-hearth', 'tags': ['fire'],
                'text': 'Restated inheriting world binding.', 'links': [], 'citations': [],
            },
        },
        {
            'op': 'supersede_fact', 'ids': ['boil-water'], 'reason_kind': 'corrected',
            'fact': {
                'schema': 'curator-fact/6', 'record': 'fact', 'id': 'boil-water-fixed',
                'statement_kind': 'observation', 'tags': ['water'],
                'text': 'Corrected.', 'links': [], 'citations': [F2],
            },
        },
        {
            'op': 'narrow_fact', 'id': 'boil-water',
            'facts': [
                _submitted_fact(id='boil-water-std', scope={'ruleset': 'standard'}),
                _submitted_fact(id='boil-water-win', scope={'ruleset': 'winter'}),
            ],
        },
        {
            'op': 'retire_fact', 'id': 'boil-water', 'reason': 'False.',
            'reason_kind': 'wrong', 'citations': [F2],
        },
        {
            'op': 'retire_fact', 'id': 'camp-fire', 'reason': 'Burnt out.',
            'reason_kind': 'ended', 'end': 'transition', 'end_citations': [F2],
        },
        {
            'op': 'retire_article', 'slug': 'water-guide', 'reason': 'Superseded.',
            'reason_kind': 'editorial',
        },
        {'op': 'revise_article', 'slug': 'water-guide', 'lead': 'Updated lead.'},
        {
            'op': 'edit_article', 'slug': 'water-guide',
            'set_title': 'Water treatment',
            'replace_claims': [{
                'index': 0, 'old_text': 'Boil murky water.', 'old_facts': ['boil-water'],
                'text': 'Boil murky water over fire.', 'facts': ['boil-water-2'],
            }],
            'add_claims': [{'text': 'Store clean water.', 'facts': ['boil-water-2']}],
            'add_tags': ['fire'],
        },
        {'op': 'remap_citations', 'from': ['boil-water'], 'to': 'boil-water-2', 'in': ['water-guide']},
        {'op': 'retag', 'assignments': {'boil-water': ['water', 'survival'], 'water-guide': ['water']}},
    ]
    # Repeated draft IDs stay accepted, matching existing gate.py behavior.
    sub = _submission(ops, from_drafts=['draft-1', 'draft-1'])
    errors = list(validator.iter_errors(sub))
    assert not errors, errors
    # Zero retag operations also valid.
    assert validator.is_valid(_submission([{'op': 'add_fact', 'fact': _submitted_fact()}]))


@pytest.mark.parametrize('bad_op', [
    {'op': 'add_type', 'type': {'schema': 'curator-type/2', 'name': 'x'}},
    {'op': 'revise_types', 'action': 'rename', 'names': ['a'], 'types': [], 'assignments': {}},
    {'op': 'add_fact', 'fact': _submitted_fact(id='abc\n')},
    {'op': 'add_fact', 'fact': _submitted_fact(citations=['frame-1'])},
    {'op': 'add_fact', 'fact': _submitted_fact(citations=[f'{SID1}-0001'])},
    {'op': 'add_fact', 'fact': _submitted_fact(scope={'game': 'example'})},
    {'op': 'add_fact', 'fact': _submitted_fact(scope={'world': 'w1'})},
    {'op': 'add_fact', 'fact': _submitted_fact(scope={'world\n': 'w1'})},
    {'op': 'add_fact', 'fact': _submitted_fact(statement_kind='state', state_key='camp-hearth')},
    {
        'op': 'supersede_fact', 'ids': ['camp-fire'], 'reason_kind': 'restated',
        'fact': {
            'schema': 'curator-fact/6', 'record': 'fact', 'id': 'camp-fire-2',
            'statement_kind': 'state', 'state_key': 'camp-hearth', 'tags': [],
            'text': 'Explicit empty binds refused for state.', 'binds': [], 'links': [], 'citations': [],
        },
    },
    {
        'op': 'supersede_fact', 'ids': ['a'], 'reason_kind': 'corrected',
        'fact': {
            'schema': 'curator-fact/6', 'record': 'fact', 'id': 'b',
            'statement_kind': 'observation', 'tags': [],
            'text': 'Corrected without citation.', 'links': [], 'citations': [],
        },
    },
    {'op': 'narrow_fact', 'id': 'a', 'facts': [_submitted_fact(id='b')]},
    {'op': 'retire_fact', 'id': 'a', 'reason': 'Out.', 'reason_kind': 'ended', 'citations': [F1]},
    {'op': 'revise_article', 'slug': 'g'},
    {'op': 'revise_article', 'slug': 'g', 'lead': None},
    {'op': 'edit_article', 'slug': 'g'},
    {'op': 'remap_citations', 'from': ['a'], 'to': 'b', 'in': []},
    {'op': 'retag', 'assignments': {}},
])
def test_curator_submission_schema_rejects_invalid_operations(bad_op):
    validator = _load_validator('curator-submission.schema.json')
    assert not validator.is_valid(_submission([bad_op]))


def test_curator_submission_schema_rejects_two_retag_operations():
    validator = _load_validator('curator-submission.schema.json')
    sub = _submission([
        {'op': 'retag', 'assignments': {'fact-a': ['water']}},
        {'op': 'retag', 'assignments': {'fact-b': ['fire']}},
    ])
    assert not validator.is_valid(sub)


def test_shared_delivered_knowledge_fixtures_inventory_and_parity():
    empty_file = json.loads((REPO_ROOT / 'tests' / 'fixtures' / 'empty-delivered-knowledge.json').read_text(encoding='utf-8'))
    valid_empty = json.loads((FIXTURES / 'valid' / 'empty.json').read_text(encoding='utf-8'))
    assert empty_file == valid_empty

    valid_paths = sorted((FIXTURES / 'valid').glob('*.json'))
    invalid_paths = sorted((FIXTURES / 'invalid').glob('*.json'))
    assert {p.name for p in valid_paths} == EXPECTED_VALID_FIXTURES
    assert {p.name for p in invalid_paths} == EXPECTED_INVALID_FIXTURES

    expected = {str(path): True for path in valid_paths} | {str(path): False for path in invalid_paths}
    python = {}
    for path in valid_paths + invalid_paths:
        try:
            Knowledge(path)
        except PlayerError:
            python[str(path)] = False
        else:
            python[str(path)] = True

    node = subprocess.run(
        ['node', '--input-type=module', '-e', """
            import {readFileSync} from 'node:fs';
            import {validateKnowledge} from './tools/player_host/knowledge.mjs';
            const paths = JSON.parse(readFileSync(0, 'utf8'));
            const results = paths.map(path => {
                const fixture = JSON.parse(readFileSync(path, 'utf8'));
                try {
                    validateKnowledge(fixture);
                    return [path, true];
                } catch (error) {
                    if (error.message !== 'invalid-delivered-knowledge') throw error;
                    return [path, false];
                }
            });
            console.log(JSON.stringify(Object.fromEntries(results)));
        """],
        cwd=REPO_ROOT, input=json.dumps(list(expected)), capture_output=True, text=True, check=True,
    )
    assert python == expected
    assert json.loads(node.stdout) == expected

    # Verify full-graph-and-history internal semantic consistency (last_confirmed & 1-to-1 session aliases).
    full = json.loads((FIXTURES / 'valid' / 'full-graph-and-history.json').read_text(encoding='utf-8'))
    facts_by_id = {f['id']: f for f in full['facts']}
    for art in full['articles']:
        cited = [facts_by_id[fid] for claim in art['body'] for fid in claim['facts']]
        assert art['last_confirmed'] == max((f['seen'] for f in cited), key=lambda p: tuple(p['order']))
    sid_to_alias: dict[str, str] = {}
    alias_to_sid: dict[str, str] = {}
    for f in full['facts']:
        if len(f['citation_source_ids']) == 1:
            alias = f['seen']['session']
            sid = f['citation_source_ids'][0].partition('-')[0]
            assert sid_to_alias.setdefault(sid, alias) == alias
            assert alias_to_sid.setdefault(alias, sid) == sid
    for target_id in full['history']['replaced']['broad-fire-claim']['by']:
        assert len(facts_by_id[target_id]['scope']) >= 2


def test_synthetic_repositories_build_clean_curator_knowledge_5_trees(tmp_path: Path):
    builders = [
        ('two_world', build_two_world_two_lineage_repo),
        ('nested_cut', build_nested_cut_repo),
        ('parent_target', build_parent_target_repo),
        ('restore', build_restore_repo),
        ('falsity', build_falsity_propagation_repo),
        ('cycle', build_cycle_and_withholding_repo),
    ]
    for name, builder in builders:
        info = builder(tmp_path / name)
        repo_path = info['repo_path']
        tags = subprocess.run(
            ['git', 'tag', '--list', 'v*'], cwd=repo_path, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        assert 'v0' in tags and info['version'] in tags
        metadata = json.loads((repo_path / 'knowledge.json').read_text(encoding='utf-8'))
        assert metadata == {'schema': 'curator-knowledge/5', 'game': info['game']}
        assert not (repo_path / 'ontology' / 'types.json').exists()
        assert (repo_path / 'coverage.json').exists()

        # Verify causal monotonicity, valid link targets, and `last_admission` consistency at every tag.
        for tag in sorted(tags, key=lambda v: int(v[1:])):
            tag_num = int(tag[1:])
            prov = json.loads(subprocess.run(
                ['git', 'show', f'{tag}:provenance.json'], cwd=repo_path, capture_output=True, text=True, check=True,
            ).stdout)
            raw_facts = subprocess.run(
                ['git', 'show', f'{tag}:facts.jsonl'], cwd=repo_path, capture_output=True, text=True, check=True,
            ).stdout
            tag_rows = [json.loads(line) for line in raw_facts.splitlines() if line.strip()]
            known_public = {r['slug'] if r['record'] == 'article' else r['id'] for r in tag_rows}
            for row in tag_rows:
                for link in row['links']:
                    assert link['target'] in known_public, f'{name} {tag}: dangling link {link["target"]!r}'
            for branch in prov['branches'].values():
                if branch['fork_version'] is not None:
                    assert int(branch['fork_version'][1:]) <= tag_num
            for restore in prov['restores']:
                for field in ('saved_version', 'restored_version'):
                    if restore[field] is not None:
                        assert int(restore[field][1:]) <= tag_num
            if tag_num >= 1:
                la = prov.get('last_admission')
                assert la is not None
                cov_session = la['coverage']['session']
                for cid in la['citations']:
                    assert prov['frames'][cid]['session'] == cov_session

    # Nested cut: C's note is published strictly after its fork_version v7 (at v8).
    nested_rows = {
        row['id']: row
        for row in (json.loads(line) for line in (tmp_path / 'nested_cut' / 'example' / 'facts.jsonl').read_text(encoding='utf-8').splitlines())
    }
    assert nested_rows['c-camp-note']['published_in'] == 'v8'

    # Cycle & withholding repo: real stale_citations and transitive fixed point.
    cycle_rows = {
        row['id']: row
        for row in (json.loads(line) for line in (tmp_path / 'cycle' / 'example' / 'facts.jsonl').read_text(encoding='utf-8').splitlines())
    }
    assert cycle_rows['clean-cycle-a']['needs_review'] is False
    assert cycle_rows['clean-cycle-b']['needs_review'] is False
    assert cycle_rows['seed-conflict-1']['lifecycle_state'] == 'contested'
    assert cycle_rows['dirty-cycle-a']['needs_review'] is True
    assert cycle_rows['dirty-cycle-b']['needs_review'] is True
    assert cycle_rows['stale-dependent']['stale_citations'] == ['stale-premise']
    assert cycle_rows['stale-dependent']['needs_review'] is True
    assert cycle_rows['stale-cycle-a']['stale_citations'] == ['stale-premise']
    assert cycle_rows['stale-cycle-a']['needs_review'] is True
    assert cycle_rows['stale-cycle-b']['stale_citations'] == []
    assert cycle_rows['stale-cycle-b']['needs_review'] is True
    assert cycle_rows['dependent-fact']['stale_citations'] == []
    assert cycle_rows['dependent-fact']['needs_review'] is False

    # Two-world repo: shadow vs conflict and single publishing session per version.
    tw_rows = {
        row['id']: row
        for row in (json.loads(line) for line in (tmp_path / 'two_world' / 'example' / 'facts.jsonl').read_text(encoding='utf-8').splitlines())
    }
    assert tw_rows['fire-tinder']['lifecycle_state'] == 'active'
    assert tw_rows['shadow-standard']['lifecycle_state'] == 'active'
    assert tw_rows['conflict-left']['lifecycle_state'] == 'contested'
    assert tw_rows['conflict-right']['lifecycle_state'] == 'contested'
    assert tw_rows['camp-guide@v4']['needs_review'] is True
    assert len({r['session'] for r in tw_rows.values() if r['published_in'] == 'v1'}) == 1


def test_synthetic_builder_enforces_article_lineages_and_end_evidence(tmp_path: Path):
    b = SyntheticKnowledgeBuilder(tmp_path / 'probe')
    sid_a, sid_b = session_hex(91), session_hex(92)
    b.add_session(sid_a, f'{LINEAGE_A}-a01-p', world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1)
    b.add_session(sid_b, f'{LINEAGE_B}-a01-p', world=WORLD_ALPHA, lineage=LINEAGE_B, admission=1)
    fa1 = b.add_frame(sid_a, 1, 10, order_index=1)
    fa2 = b.add_frame(sid_a, 2, 20, order_index=1)
    fb1 = b.add_frame(sid_b, 1, 15, order_index=2)

    b.records.extend([
        b.make_fact(
            fact_id='bound-a', statement_kind='state', state_key='bound-a-key', tags=['camp'],
            text='Bound on A.', citations=[fa1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='unbound-b', statement_kind='observation', tags=['camp'],
            text='Unbound observed on B.', citations=[fb1], published_in='v1', session='curator-v1',
        ),
    ])
    article = b.make_article(
        slug='mixed-article', title='Mixed article', lead='Cites bound A and unbound B.',
        body=[
            {'text': 'Bound on A.', 'facts': ['bound-a']},
            {'text': 'Unbound observed on B.', 'facts': ['unbound-b']},
        ],
        tags=['camp'], published_in='v1', session='curator-v1',
    )
    # Must include BOTH lineages from all cited facts' citations, not just world-bound facts.
    assert article['lineages'] == sorted([LINEAGE_A, LINEAGE_B])

    # Ending a fact with its own sighting must raise.
    with pytest.raises(ValueError, match='disjoint'):
        b.retire_fact_ended(
            'bound-a', reason='Reused sighting.', end='transition',
            end_citations=[fa1], published_in='v2', session='curator-v2',
        )
    # Unknown supporting citation must raise before mutation.
    with pytest.raises(KeyError):
        b.retire_fact_ended(
            'bound-a', reason='Missing support.', end='transition',
            end_citations=[fa2], citations=[frame_id(sid_a, 999)],
            published_in='v2', session='curator-v2',
        )
    # Valid end on A succeeds, and a second end on A must raise.
    b.retire_fact_ended(
        'bound-a', reason='Ended on A.', end='transition',
        end_citations=[fa2], published_in='v2', session='curator-v2',
    )
    with pytest.raises(ValueError, match='visible end'):
        b.retire_fact_ended(
            'bound-a', reason='Duplicate end on A.', end='absence',
            end_citations=[b.add_frame(sid_a, 3, 30, order_index=1)], published_in='v3', session='curator-v3',
        )

    # Parent + child sightings with child end on one continuous timeline: event valid_to set, top-level null.
    b2 = SyntheticKnowledgeBuilder(tmp_path / 'probe_timeline')
    sa, sb = session_hex(93), session_hex(94)
    sess_a, sess_b = f'{LINEAGE_A}-a01-t', f'{LINEAGE_B}-a01-t'
    b2.add_session(sa, sess_a, world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1)
    p1 = b2.add_frame(sa, 1, 10, order_index=1)
    b2.records.append(b2.make_fact(
        fact_id='f-parent', statement_kind='state', state_key='f-parent-key', tags=['fire'],
        text='Lit.', citations=[p1], published_in='v1', session='curator-v1', bind_world=True,
    ))
    b2.commit_version(coverage_session=sess_a, last_step=10, admission_citations=[p1])
    b2.add_session(
        sb, sess_b, world=WORLD_ALPHA, lineage=LINEAGE_B, admission=1,
        branch={'parent': LINEAGE_A, 'fork_at': {'session': sess_a, 'actor': '001', 'step': 20, 'order': [1, '001', 20]},
                'fork_version': 'v1'},
    )
    c1 = b2.add_frame(sb, 1, 25, order_index=2)
    c2 = b2.add_frame(sb, 2, 35, order_index=2)
    b2.supersede_fact(
        ['f-parent'],
        b2.make_fact(
            fact_id='f-parent-child', statement_kind='state', state_key='f-parent-key', tags=['fire'],
            text='Still lit.', citations=[p1, c1], published_in='v2', session='curator-v2', bind_world=True,
        ),
        reason_kind='restated',
    )
    b2.retire_fact_ended(
        'f-parent-child', reason='Out on B.', end='transition',
        end_citations=[c2], published_in='v2', session='curator-v2',
    )
    ended = b2.find_record('f-parent-child')
    assert ended['retired']['events'][0]['valid_to'] == b2.provenance['frames'][c2]
    assert ended['valid_to'] is None

    # Unknown restore on parent before fork blocks child end.
    b3 = SyntheticKnowledgeBuilder(tmp_path / 'probe_parent_restore')
    b3.add_session(sa, sess_a, world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1)
    r_p1 = b3.add_frame(sa, 1, 10, order_index=1)
    b3.records.append(b3.make_fact(
        fact_id='f-uncertain', statement_kind='state', state_key='f-uncertain-key', tags=['fire'],
        text='Lit.', citations=[r_p1], published_in='v1', session='curator-v1', bind_world=True,
    ))
    b3.commit_version(coverage_session=sess_a, last_step=10, admission_citations=[r_p1])
    b3.add_restore(
        lineage=LINEAGE_A,
        restored_at={'session': sess_a, 'actor': '001', 'step': 15, 'order': [1, '001', 15]},
        restored_version='v1', saved_at=None, saved_version=None,
    )
    b3.add_session(
        sb, sess_b, world=WORLD_ALPHA, lineage=LINEAGE_B, admission=1,
        branch={'parent': LINEAGE_A, 'fork_at': {'session': sess_a, 'actor': '001', 'step': 20, 'order': [1, '001', 20]},
                'fork_version': 'v1'},
    )
    r_c1 = b3.add_frame(sb, 1, 25, order_index=2)
    with pytest.raises(ValueError, match='unknown restore'):
        b3.retire_fact_ended(
            'f-uncertain', reason='Out on B after unknown parent restore.', end='transition',
            end_citations=[r_c1], published_in='v2', session='curator-v2',
        )


def test_player_knowledge_4_contract_fixtures():
    fixtures = REPO_ROOT / 'tests' / 'fixtures' / 'player-knowledge-4'
    knowledge = Knowledge(FIXTURES / 'valid' / 'full-graph-and-history.json')
    read_doc = json.loads((fixtures / 'read-state-key.json').read_text(encoding='utf-8'))
    assert read_doc['schema'] == 'player-knowledge/4'
    assert read_doc['resolution'] == 'state_key'
    assert actor_result(read_doc) == knowledge.read(read_doc['identity']) == read_doc

    query_doc = json.loads((fixtures / 'query-compact-hits.json').read_text(encoding='utf-8'))
    assert query_doc['schema'] == 'player-knowledge/4'
    assert query_doc['resolution'] == 'query'
    assert actor_result(query_doc) == knowledge.query(query_doc['identity']) == query_doc
    assert query_doc['hits'] and all(hit['via'] == 'fuzzy' for hit in query_doc['hits'])
    fields = set().union(*(hit.keys() for hit in query_doc['hits']))
    assert {'statement_kind', 'when', 'state_key', 'anchor', 'anchor_display', 'depiction_source_id'} <= fields


def test_clock_label_astral_code_point_length_parity():
    doc = json.loads((FIXTURES / 'valid' / 'full-graph-and-history.json').read_text(encoding='utf-8'))
    src = doc['facts'][0]['citation_source_ids'][0]
    ok_label = '\U0001F31E' * 64  # 64 Unicode code points (128 UTF-16 code units)
    doc['frame_clocks'][src] = ok_label
    doc['facts'][0]['seen']['clock_label'] = ok_label
    doc['facts'][0]['seen'].pop('prior_clock', None)
    assert Knowledge.from_dict(doc).value['frame_clocks'][src] == ok_label
    too_long = '\U0001F31E' * 65
    doc['frame_clocks'][src] = too_long
    doc['facts'][0]['seen']['clock_label'] = too_long
    with pytest.raises(ValueError):
        Knowledge.from_dict(doc)
