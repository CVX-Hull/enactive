"""Shared-shape validation for Wave 3 (`curator-fact/5`, `curator-submission/2`,
`delivered-knowledge/3` fixtures, and synthetic two-world/two-lineage repositories).
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from jsonschema import Draft202012Validator
import pytest

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
FIXTURES = REPO_ROOT / 'tests' / 'fixtures' / 'delivered-knowledge-3'

SID1 = session_hex(1)
SID2 = session_hex(2)
F1 = frame_id(SID1, 1)
F2 = frame_id(SID1, 2)

_VERSION_RE = re.compile(r'^v(0|[1-9][0-9]*)\Z')
_HEX40_RE = re.compile(r'^[0-9a-f]{40}\Z')
_ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}\Z')
_REV_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}@v(0|[1-9][0-9]*)\Z')
_SOURCE_RE = re.compile(r'^[0-9a-f]{32}-[1-9][0-9]*\Z')
_ALIAS_RE = re.compile(r'^s(?:0[1-9]|[1-9][0-9]+)\Z')
_TAG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*\Z')
_AXIS_RE = re.compile(r'^[a-z][a-z0-9_]{0,31}\Z')
_ASCII_RE = re.compile(r'^[ -~]{1,64}\Z')

EXPECTED_VALID_FIXTURES = {
    'empty.json',
    'full-graph-and-history.json',
    'high-session-alias.json',
    'minimal.json',
    'standalone-facts-only.json',
}

EXPECTED_INVALID_FIXTURES = {
    'article-cites-missing-fact.json',
    'article-raw-world-label.json',
    'empty-version-with-records.json',
    'extra-fact-field-type.json',
    'extra-top-level-key.json',
    'history-ended-revision-id.json',
    'history-overlap-ended-retracted.json',
    'history-replaced-target-outside-public.json',
    'instance-state-unbound.json',
    'invalid-lifecycle-state.json',
    'invalid-revision-prefix.json',
    'invalid-tag-format.json',
    'link-outside-public-set.json',
    'malformed-citation-source-id.json',
    'missing-history.json',
    'old-schema-v2.json',
    'raw-session-name-in-coverage.json',
    'raw-session-name-in-last-confirmed.json',
    'raw-session-name-in-seen.json',
    'raw-world-label.json',
    'self-link.json',
    'stale-citation-outside-history.json',
    'unbound-with-branch-relation.json',
    'unbound-with-unverified-branch.json',
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
        'schema': 'curator-fact/5',
        'record': 'fact',
        'id': 'boil-water',
        'claim_kind': 'mechanic',
        'evidence_basis': 'observed',
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
        'schema': 'curator-fact/5',
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
        'schema': 'curator-fact/5',
        'record': 'fact',
        'id': 'boil-water',
        'claim_kind': 'mechanic',
        'evidence_basis': 'observed',
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
        'schema': 'curator-submission/2',
        'base_version': 'v0',
        'summary': 'Add initial knowledge.',
        'changes': changes,
    }
    base.update(overrides)
    return base


def _nonblank(v: object) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _is_valid_delivered_3(doc: object) -> bool:
    """Reference structural validator for `delivered-knowledge/3` shared fixtures."""
    top_keys = {'schema', 'version', 'commit', 'repository_id', 'coverage', 'articles', 'facts', 'history'}
    if not isinstance(doc, dict) or set(doc) != top_keys or doc['schema'] != 'delivered-knowledge/3':
        return False
    if not isinstance(doc['articles'], list) or not isinstance(doc['facts'], list):
        return False
    hist = doc['history']
    if not isinstance(hist, dict) or set(hist) != {'replaced', 'ended', 'retracted'}:
        return False
    if not isinstance(hist['replaced'], dict) or not isinstance(hist['ended'], list) or not isinstance(hist['retracted'], list):
        return False
    if doc['version'] is None:
        return (
            doc['commit'] is None and doc['repository_id'] is None and doc['coverage'] is None
            and not doc['articles'] and not doc['facts']
            and hist == {'replaced': {}, 'ended': [], 'retracted': []}
        )
    if not (isinstance(doc['version'], str) and _VERSION_RE.match(doc['version'])):
        return False
    if not (isinstance(doc['commit'], str) and _HEX40_RE.match(doc['commit'])):
        return False
    if not (isinstance(doc['repository_id'], str) and _HEX40_RE.match(doc['repository_id'])):
        return False
    cov = doc['coverage']
    if cov is not None:
        if (not isinstance(cov, dict) or set(cov) != {'schema', 'session', 'actor', 'last_step'}
                or cov['schema'] != 'curator-coverage/2'
                or not (isinstance(cov['session'], str) and _ALIAS_RE.match(cov['session']))
                or (cov['actor'] is not None and not _nonblank(cov['actor']))
                or (cov['last_step'] is not None and type(cov['last_step']) is not int)):
            return False

    def valid_pos(p: object) -> bool:
        return (
            isinstance(p, dict) and set(p) == {'session', 'actor', 'step', 'order'}
            and isinstance(p['session'], str) and bool(_ALIAS_RE.match(p['session']))
            and _nonblank(p['actor']) and type(p['step']) is int
            and isinstance(p['order'], list) and len(p['order']) == 3
            and type(p['order'][0]) is int and isinstance(p['order'][1], str) and type(p['order'][2]) is int
        )

    def valid_scope(s: object) -> bool:
        if not isinstance(s, dict) or not (1 <= len(s) <= 8) or 'game' not in s:
            return False
        for k, v in s.items():
            if not isinstance(k, str) or not _AXIS_RE.match(k):
                return False
            if k == 'world':
                if v is not None:
                    return False
            elif not isinstance(v, str) or not _ASCII_RE.match(v):
                return False
        return True

    def valid_tags(t: object) -> bool:
        return (
            isinstance(t, list) and len(t) <= 8 and len(set(t)) == len(t)
            and all(isinstance(x, str) and len(x) <= 32 and _TAG_RE.match(x) for x in t)
        )

    def valid_links(items: object, key_name: str, owner_id: str, public_ids: set[str]) -> bool:
        if not isinstance(items, list):
            return False
        seen = set()
        for item in items:
            if (not isinstance(item, dict) or set(item) != {'rel', key_name}
                    or item['rel'] not in ('depends_on', 'contradicts', 'part_of', 'see_also')
                    or not isinstance(item[key_name], str) or not _ID_RE.match(item[key_name])
                    or item[key_name] == owner_id or item[key_name] not in public_ids):
                return False
            pair = (item['rel'], item[key_name])
            if pair in seen:
                return False
            seen.add(pair)
        return True

    art_ids = [a.get('id') for a in doc['articles'] if isinstance(a, dict)]
    fact_ids = [f.get('id') for f in doc['facts'] if isinstance(f, dict)]
    if len(art_ids) != len(doc['articles']) or len(fact_ids) != len(doc['facts']):
        return False
    all_ids = art_ids + fact_ids
    if len(set(all_ids)) != len(all_ids) or not all(isinstance(x, str) and _ID_RE.match(x) for x in all_ids):
        return False
    art_set, fact_set, public_ids = set(art_ids), set(fact_ids), set(all_ids)
    delivered_revs = {a.get('revision') for a in doc['articles']}

    # Validate history sets first so stale_citations can be checked against H.
    ended, retracted = hist['ended'], hist['retracted']
    if (len(set(ended)) != len(ended) or len(set(retracted)) != len(retracted)
            or not all(isinstance(x, str) and _ID_RE.match(x) for x in ended + retracted)
            or set(ended) & set(retracted) or (set(ended) | set(retracted)) & public_ids):
        return False
    for key, entry in hist['replaced'].items():
        if (not isinstance(key, str) or key in public_ids or key in delivered_revs
                or key in ended or key in retracted
                or not isinstance(entry, dict) or set(entry) != {'reason', 'by'}
                or not isinstance(entry['by'], list) or not entry['by']
                or len(set(entry['by'])) != len(entry['by'])):
            return False
        if _REV_RE.match(key):
            slug = key.split('@', 1)[0]
            if entry['reason'] != 'restated' or entry['by'] != [slug] or slug not in art_set:
                return False
        elif _ID_RE.match(key):
            if entry['reason'] not in ('restated', 'narrowed', 'corrected') or not set(entry['by']) <= fact_set:
                return False
        else:
            return False
    history_ids = set(hist['replaced']) | set(ended) | set(retracted)

    art_req = {
        'id', 'revision', 'title', 'lead', 'body', 'tags', 'scope', 'branch_relation',
        'lifecycle_state', 'needs_review', 'stale_citations', 'condition_unverified',
        'unverified_branch', 'links', 'backlinks', 'shadowed_by', 'contradicted_by', 'last_confirmed',
    }
    for art in doc['articles']:
        if set(art) != art_req:
            return False
        if (not isinstance(art['revision'], str) or not _REV_RE.match(art['revision'])
                or not art['revision'].startswith(art['id'] + '@')):
            return False
        if not (_nonblank(art['title']) and _nonblank(art['lead']) and valid_tags(art['tags']) and valid_scope(art['scope'])):
            return False
        world_bound = 'world' in art['scope']
        if (world_bound and art['branch_relation'] not in ('same', 'inherited', 'unknown')) or (
            not world_bound and (art['branch_relation'] is not None or art['unverified_branch'] is not False)
        ):
            return False
        if art['lifecycle_state'] not in ('active', 'contested'):
            return False
        if not all(type(art[k]) is bool for k in ('needs_review', 'condition_unverified', 'unverified_branch')):
            return False
        if (not isinstance(art['stale_citations'], list) or len(set(art['stale_citations'])) != len(art['stale_citations'])
                or not all(isinstance(x, str) and x in history_ids for x in art['stale_citations'])):
            return False
        if not isinstance(art['body'], list) or not art['body']:
            return False
        for claim in art['body']:
            if (not isinstance(claim, dict) or set(claim) != {'text', 'facts'} or not _nonblank(claim['text'])
                    or not isinstance(claim['facts'], list) or not claim['facts']
                    or len(set(claim['facts'])) != len(claim['facts'])
                    or not set(claim['facts']) <= fact_set):
                return False
        if not (valid_links(art['links'], 'target', art['id'], public_ids)
                and valid_links(art['backlinks'], 'source', art['id'], public_ids)
                and valid_pos(art['last_confirmed'])):
            return False
        for k in ('shadowed_by', 'contradicted_by'):
            if (not isinstance(art[k], list) or len(set(art[k])) != len(art[k])
                    or not all(isinstance(x, str) and x in public_ids and x != art['id'] for x in art[k])):
                return False

    fact_req = {
        'id', 'claim_kind', 'evidence_basis', 'tags', 'text', 'scope', 'branch_relation',
        'lifecycle_state', 'needs_review', 'stale_citations', 'condition_unverified',
        'unverified_branch', 'links', 'backlinks', 'shadowed_by', 'contradicted_by',
        'cited_by_articles', 'citation_source_ids', 'seen',
    }
    fact_opt = {'subject', 'when'}
    for f in doc['facts']:
        if not (fact_req <= set(f) <= fact_req | fact_opt):
            return False
        if (f['claim_kind'] not in ('interface', 'mechanic', 'entity_property', 'instance_state', 'strategy')
                or f['evidence_basis'] not in ('observed', 'inferred', 'hinted')
                or not valid_tags(f['tags']) or not _nonblank(f['text']) or not valid_scope(f['scope'])):
            return False
        if 'subject' in f and not _nonblank(f['subject']):
            return False
        if 'when' in f:
            w = f['when']
            if (not isinstance(w, dict) or set(w) != {'note', 'requires'} or not _nonblank(w['note'])
                    or not isinstance(w['requires'], dict) or len(w['requires']) > 8
                    or not all(isinstance(k, str) and _AXIS_RE.match(k) and k not in ('game', 'world')
                               and isinstance(v, str) and _ASCII_RE.match(v) for k, v in w['requires'].items())):
                return False
        world_bound = 'world' in f['scope']
        if f['claim_kind'] == 'instance_state' and not world_bound:
            return False
        if (world_bound and f['branch_relation'] not in ('same', 'inherited', 'unknown')) or (
            not world_bound and (f['branch_relation'] is not None or f['unverified_branch'] is not False)
        ):
            return False
        if f['lifecycle_state'] not in ('active', 'contested'):
            return False
        if not all(type(f[k]) is bool for k in ('needs_review', 'condition_unverified', 'unverified_branch')):
            return False
        if (not isinstance(f['stale_citations'], list) or len(set(f['stale_citations'])) != len(f['stale_citations'])
                or not all(isinstance(x, str) and x in history_ids for x in f['stale_citations'])):
            return False
        if (not isinstance(f['citation_source_ids'], list) or not f['citation_source_ids']
                or len(set(f['citation_source_ids'])) != len(f['citation_source_ids'])
                or not all(isinstance(x, str) and _SOURCE_RE.match(x) for x in f['citation_source_ids'])):
            return False
        if (not isinstance(f['cited_by_articles'], list) or len(set(f['cited_by_articles'])) != len(f['cited_by_articles'])
                or not set(f['cited_by_articles']) <= art_set):
            return False
        if not (valid_links(f['links'], 'target', f['id'], public_ids)
                and valid_links(f['backlinks'], 'source', f['id'], public_ids)
                and valid_pos(f['seen'])):
            return False
        for k in ('shadowed_by', 'contradicted_by'):
            if (not isinstance(f[k], list) or len(set(f[k])) != len(f[k])
                    or not all(isinstance(x, str) and x in public_ids and x != f['id'] for x in f[k])):
                return False
    return True


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
            when={'note': 'needs a lit heat source', 'requires': {}},
            retagged=[{'from': ['water'], 'to': ['water', 'fire'], 'version': 'v2'}],
        ),
        _stored_fact(
            id='camp-fire', claim_kind='instance_state',
            scope={'game': 'example', 'world': 'world-alpha', 'ruleset': 'standard'},
            lineages=['lin-a'],
        ),
        _stored_fact(lifecycle_state='superseded', superseded_by=['boil-water-2']),
        _stored_fact(lifecycle_state='retracted', superseded_by=['boil-water-fixed']),
        _stored_fact(
            lifecycle_state='retracted',
            retired={
                'reason': 'Observed false.', 'reason_kind': 'wrong',
                'citations': [F2], 'published_in': 'v2', 'session': 'curator-v2',
            },
        ),
        _stored_fact(
            id='camp-fire', claim_kind='instance_state',
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
            id='camp-fire', claim_kind='instance_state',
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
    lambda r: r.__setitem__('claim_kind', 'instance_state'),  # missing scope.world
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
    lambda r: r.__setitem__('when', {'note': 'x', 'requires': {'world': 'w1'}}),
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
                id='camp-fire', claim_kind='instance_state', binds=['world'],
                when={'note': 'while fuel lasts', 'requires': {}},
            ),
        },
        {
            'op': 'add_article',
            'article': {
                'schema': 'curator-fact/5', 'record': 'article', 'slug': 'water-guide',
                'title': 'Water guide', 'lead': 'Boil water.',
                'body': [{'text': 'Boil murky water.', 'facts': ['boil-water']}],
                'tags': ['water'], 'links': [],
            },
        },
        {
            'op': 'supersede_fact', 'ids': ['camp-fire'], 'reason_kind': 'restated',
            'fact': {
                'schema': 'curator-fact/5', 'record': 'fact', 'id': 'camp-fire-2',
                'claim_kind': 'instance_state', 'evidence_basis': 'observed', 'tags': ['fire'],
                'text': 'Restated inheriting world binding.', 'links': [], 'citations': [],
            },
        },
        {
            'op': 'supersede_fact', 'ids': ['boil-water'], 'reason_kind': 'corrected',
            'fact': {
                'schema': 'curator-fact/5', 'record': 'fact', 'id': 'boil-water-fixed',
                'claim_kind': 'mechanic', 'evidence_basis': 'observed', 'tags': ['water'],
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
        {'op': 'remap_citations', 'from': 'boil-water', 'to': 'boil-water-2', 'in': ['water-guide']},
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
    {'op': 'add_fact', 'fact': _submitted_fact(claim_kind='instance_state')},
    {
        'op': 'supersede_fact', 'ids': ['camp-fire'], 'reason_kind': 'restated',
        'fact': {
            'schema': 'curator-fact/5', 'record': 'fact', 'id': 'camp-fire-2',
            'claim_kind': 'instance_state', 'evidence_basis': 'observed', 'tags': [],
            'text': 'Explicit empty binds refused for instance_state.', 'binds': [], 'links': [], 'citations': [],
        },
    },
    {
        'op': 'supersede_fact', 'ids': ['a'], 'reason_kind': 'corrected',
        'fact': {
            'schema': 'curator-fact/5', 'record': 'fact', 'id': 'b',
            'claim_kind': 'mechanic', 'evidence_basis': 'observed', 'tags': [],
            'text': 'Corrected without citation.', 'links': [], 'citations': [],
        },
    },
    {'op': 'narrow_fact', 'id': 'a', 'facts': [_submitted_fact(id='b')]},
    {'op': 'retire_fact', 'id': 'a', 'reason': 'Out.', 'reason_kind': 'ended', 'citations': [F1]},
    {'op': 'revise_article', 'slug': 'g'},
    {'op': 'revise_article', 'slug': 'g', 'lead': None},
    {'op': 'edit_article', 'slug': 'g'},
    {'op': 'remap_citations', 'from': 'a', 'to': 'b', 'in': []},
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

    for path in valid_paths:
        doc = json.loads(path.read_text(encoding='utf-8'))
        assert _is_valid_delivered_3(doc), f'valid fixture failed reference check: {path.name}'

    for path in invalid_paths:
        doc = json.loads(path.read_text(encoding='utf-8'))
        assert not _is_valid_delivered_3(doc), f'invalid fixture passed reference check: {path.name}'

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


def test_synthetic_repositories_build_clean_curator_knowledge_4_trees(tmp_path: Path):
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
        assert metadata == {'schema': 'curator-knowledge/4', 'game': info['game']}
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
            fact_id='bound-a', claim_kind='instance_state', tags=['camp'],
            text='Bound on A.', citations=[fa1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='unbound-b', claim_kind='mechanic', tags=['camp'],
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
        fact_id='f-parent', claim_kind='instance_state', tags=['fire'],
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
            fact_id='f-parent-child', claim_kind='instance_state', tags=['fire'],
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
        fact_id='f-uncertain', claim_kind='instance_state', tags=['fire'],
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
