"""`delivered-knowledge/3` reader, `player-knowledge/3` reads/compact queries and `bm25_1hop` ranking (#937, #950).

Gate 1's Python half loads the shared reader fixtures; Gate 9 replays the #924 queries on test-only projections of
the sealed `#896-b v91` and `#889 v17` files when the main checkout's evidence store holds them, and synthetic
graph tests always run.
"""
import copy
import json
import math
from pathlib import Path
import time
import uuid

import pytest

from harness.application import Application
from harness.computer.protocol import ControlError
from harness.player.contracts import PlayerError
from harness.player.journal import Journal
from harness.player.knowledge import (
    HIT_CITED_BY_LIMIT,
    MAX_SAFE_INT,
    QUERY_LIMIT,
    RESULT,
    SCHEMA,
    SNIPPET_LIMIT,
    Knowledge,
    _valid,
    empty,
    revision_parts,
    terms_of,
    version_number,
)
from harness.player_tools import tool_specs
from harness.player_view import UnsupportedResult, actor_result
from test_computer_runtime import make_runtime

FIXTURES = Path(__file__).with_name('fixtures')
SHARED = FIXTURES / 'delivered-knowledge-3'
PK3_FIXTURES = FIXTURES / 'player-knowledge-3'
FULL = SHARED / 'valid' / 'full-graph-and-history.json'


def position(step: int, session: str = 's01') -> dict:
    return dict(session=session, actor='001', step=step, order=[1, '001', step])


def flags(**fields) -> dict:
    value = dict(tags=[], scope=dict(game='example'), branch_relation=None, lifecycle_state='active',
                 needs_review=False, stale_citations=[], condition_unverified=False, unverified_branch=False,
                 links=[], backlinks=[], shadowed_by=[], contradicted_by=[])
    value.update(fields)
    return value


def article(slug: str, title: str, lead: str, *claims: tuple[str, list[str]], version: str = 'v1', **fields) -> dict:
    return dict(id=slug, revision=f'{slug}@{version}', title=title, lead=lead, last_confirmed=position(1),
                body=[dict(text=text, facts=list(cited)) for text, cited in claims], **flags(**fields))


def fact(identity: str, text: str, subject: str | None = None, *, step: int = 1, kind: str = 'mechanic', **fields) -> dict:
    return dict(id=identity, claim_kind=kind, evidence_basis='observed', text=text, cited_by_articles=[],
                citation_source_ids=[f'{step:032x}-1'], seen=position(step),
                **({} if subject is None else dict(subject=subject)), **flags(**fields))


def document(articles: list[dict], facts: list[dict], history: dict | None = None, version: str = 'v1') -> dict:
    """A closed `delivered-knowledge/3` file; backlinks and `cited_by_articles` are derived as the exporter does."""
    articles, facts = copy.deepcopy(articles), copy.deepcopy(facts)
    records = {r['id']: r for r in articles + facts}
    for record in articles + facts:
        for link in record['links']:
            records[link['target']]['backlinks'].append(dict(rel=link['rel'], source=record['id']))
    for a in articles:
        for cited in dict.fromkeys(f for claim in a['body'] for f in claim['facts']):
            records[cited]['cited_by_articles'].append(a['id'])
    return dict(schema=SCHEMA, version=version, commit='a' * 40, repository_id='b' * 40, coverage=None,
                articles=articles, facts=facts, history=history or dict(replaced={}, ended=[], retracted=[]))


def store(articles: list[dict], facts: list[dict], history: dict | None = None) -> Knowledge:
    return Knowledge.from_dict(document(articles, facts, history))


def ids(result: dict) -> list[str]:
    if result['resolution'] == 'query':
        assert 'hits' in result and 'records' not in result
        return [h['id'] for h in result['hits']]
    assert 'records' in result and 'hits' not in result
    return [r['id'] for r in result['records']]


# Gate 1, Python half: the shared reader fixtures, which `tools/player_host/knowledge.mjs` loads too.

@pytest.mark.parametrize('path', sorted((SHARED / 'valid').glob('*.json')) + [FIXTURES / 'empty-delivered-knowledge.json'],
                         ids=lambda p: p.name)
def test_every_shared_valid_fixture_is_accepted(path):
    knowledge = Knowledge(path)
    assert knowledge.value['schema'] == SCHEMA


@pytest.mark.parametrize('path', sorted((SHARED / 'invalid').glob('*.json')), ids=lambda p: p.name)
def test_every_shared_invalid_fixture_is_refused(path):
    with pytest.raises(PlayerError, match='unsupported delivered knowledge'):
        Knowledge(path)


def test_the_empty_file_is_exact_and_the_fixture_directories_are_populated():
    assert Knowledge.from_dict(empty()).value == json.loads((FIXTURES / 'empty-delivered-knowledge.json').read_text())
    assert len(list((SHARED / 'valid').glob('*.json'))) >= 5 and len(list((SHARED / 'invalid').glob('*.json'))) >= 25


@pytest.mark.parametrize('change', [
    lambda d: d.update(version='v1\n'),
    lambda d: d.update(commit='a' * 40 + '\n'),
    lambda d: d['facts'][0]['seen'].update(session='s01\n'),
    lambda d: d['facts'][0]['seen'].update(session='s1'),
    lambda d: d['facts'][0].update(scope=dict(game='example', world='world-alpha'), branch_relation='same'),
    lambda d: d['facts'][0].update(tags=['water', 'water']),
    lambda d: d['facts'][0].update(tags=['x' * 33]),
    lambda d: d['facts'][0].update(subject=' '),
    lambda d: d['facts'][0].update(type='mechanic'),
    lambda d: d['facts'][0].update(claim_kind='observation'),
    lambda d: d['facts'][0].update(citation_source_ids=[]),
    lambda d: d['facts'][0].update(cited_by_articles=['missing-article']),
    lambda d: d['articles'][0].update(revision='other@v1'),
    lambda d: d['articles'][0].update(world=None),
    lambda d: d['articles'][0]['body'][0].update(facts=['fact-a', 'fact-a']),
    lambda d: d['articles'][0].update(shadowed_by=['guide']),
    lambda d: d['history'].update(ended=['fact-a']),
    lambda d: d['history']['replaced'].update({'guide@v0': dict(reason='corrected', by=['guide'])}),
    lambda d: d['history']['replaced'].update({'old-fact': dict(reason='restated', by=['guide'])}),
    lambda d: d.update(version=None, commit=None, repository_id=None),
], ids=lambda _: 'mutation')
def test_closed_forms_refuse_edge_cases_beyond_the_shared_fixtures(change):
    value = document([article('guide', 'Guide', 'Lead.', ('Claim.', ['fact-a']))], [fact('fact-a', 'A claim.')])
    Knowledge.from_dict(value)
    change(value)
    with pytest.raises(PlayerError):
        Knowledge.from_dict(value)


def graph(version: str = 'v3', revision: str = 'v2', **guide) -> dict:
    """An article citing `fact-a`, and `fact-b`, scoped more narrowly, contradicting and so shadowing `fact-a`;
    derived fields as exported."""
    return document([article('guide', 'Guide', 'Lead.', ('Claim.', ['fact-a']), version=revision, **guide)],
                    [fact('fact-a', 'A claim.', shadowed_by=['fact-b']),
                     fact('fact-b', 'A narrower claim.', step=2, scope=dict(game='example', ruleset='standard'),
                          links=[dict(rel='contradicts', target='fact-a')])],
                    dict(replaced={'guide@v1': dict(reason='restated', by=['guide'])}, ended=[], retracted=[]),
                    version=version)


def bound(record: dict, relation: str = 'same', **fields) -> None:
    record.update(scope=dict(game='example', world=None), branch_relation=relation, **fields)


def test_derived_fields_and_inherited_flags_that_agree_are_accepted():
    Knowledge.from_dict(graph())
    Knowledge.from_dict(graph(version='v2'))  # The delivered revision may be the file's own version.
    value = graph()
    bound(value['articles'][0], unverified_branch=True)
    bound(value['facts'][0], 'unknown', unverified_branch=True)
    # Both bound records hold `world: null`, so `fact-b` is still the narrower one.
    bound(value['facts'][1])
    value['facts'][1]['scope'].update(ruleset='standard')
    value['facts'][0].update(condition_unverified=True)
    value['articles'][0].update(condition_unverified=True)
    Knowledge.from_dict(value)
    # An article may be unverified_branch by its own unknown lineage when no cited fact is.
    value = graph()
    bound(value['articles'][0], 'unknown', unverified_branch=True)
    Knowledge.from_dict(value)


def conflict(value: dict) -> dict:
    """`fact-a` and `fact-b` in conflict: both contested, and the article citing `fact-a` inherits it."""
    value['facts'][0].update(shadowed_by=[], contradicted_by=['fact-b'], lifecycle_state='contested')
    value['facts'][1].update(contradicted_by=['fact-a'], lifecycle_state='contested')
    value['articles'][0].update(lifecycle_state='contested')
    return value


def test_contradicts_pairs_are_classified_by_constraint_and_scope_order():
    # Equal scopes conflict.
    value = graph()
    value['facts'][1].update(scope=dict(game='example'))
    Knowledge.from_dict(conflict(value))
    # Incomparable scopes with compatible constraints conflict too.
    value = graph()
    bound(value['facts'][0])
    Knowledge.from_dict(conflict(value))
    # A shared axis that differs, here a scope against a `requires`, is disjoint: neither shadows nor conflicts.
    value = graph()
    value['facts'][0].update(when=dict(note='hard rules only', requires=dict(ruleset='hard')), shadowed_by=[])
    Knowledge.from_dict(value)
    # A `requires` on the general record that agrees keeps the pair compatible, so the shadow stands.
    value = graph()
    value['facts'][0].update(when=dict(note='standard rules', requires=dict(ruleset='standard')))
    Knowledge.from_dict(value)


@pytest.mark.parametrize('change', [
    lambda d: d['facts'][0].update(shadowed_by=[]),
    lambda d: d['facts'][1].update(shadowed_by=['fact-a']),
    lambda d: conflict(d),
    lambda d: (d['facts'][1].update(scope=dict(game='example')), conflict(d), d['articles'][0].update(lifecycle_state='active')),
    lambda d: (d['facts'][1].update(scope=dict(game='example')), conflict(d), d['facts'][1].update(lifecycle_state='active')),
    lambda d: (d['facts'][1].update(scope=dict(game='example')), conflict(d), d['facts'][1].update(contradicted_by=[])),
    lambda d: d['facts'][0].update(when=dict(note='hard rules only', requires=dict(ruleset='hard'))),
], ids=lambda _: 'mutation')
def test_shadows_and_conflicts_that_disagree_with_the_classification_are_refused(change):
    value = graph()
    change(value)
    with pytest.raises(PlayerError, match='unsupported delivered knowledge'):
        Knowledge.from_dict(value)


def test_the_full_graph_fixture_refuses_a_cleared_shadow():
    value = json.loads(FULL.read_text())
    Knowledge.from_dict(value)
    next(f for f in value['facts'] if f['id'] == 'fire-rule')['shadowed_by'] = []
    with pytest.raises(PlayerError, match='unsupported delivered knowledge'):
        Knowledge.from_dict(value)


@pytest.mark.parametrize('change', [
    # A revision later than the file, and a history revision not strictly earlier than the delivered one.
    lambda d: d.update(version='v1'),
    lambda d: d['articles'][0].update(revision='guide@v4'),
    lambda d: d['history']['replaced'].update({'guide@v2': dict(reason='restated', by=['guide'])}),
    lambda d: d['history']['replaced'].update({'guide@v3': dict(reason='restated', by=['guide'])}),
    # Derived graph fields that disagree with citations, links or `contradicts` edges.
    lambda d: d['facts'][0].update(cited_by_articles=[]),
    lambda d: d['facts'][1].update(cited_by_articles=['guide']),
    lambda d: d['facts'][0].update(backlinks=[]),
    lambda d: d['facts'][0]['backlinks'].append(dict(rel='see_also', source='fact-b')),
    lambda d: d['facts'][1]['backlinks'].append(dict(rel='contradicts', source='fact-a')),
    lambda d: d['facts'][0].update(backlinks=[dict(rel='depends_on', source='fact-b')]),
    lambda d: d['facts'][1].update(shadowed_by=['guide']),
    lambda d: d['articles'][0].update(contradicted_by=['fact-a']),
    # Uncertainty a record or article suppresses.
    lambda d: bound(d['facts'][0], 'unknown', unverified_branch=False),
    lambda d: d['facts'][0].update(condition_unverified=True),
    lambda d: d['articles'][0].update(condition_unverified=True),
    lambda d: (bound(d['articles'][0]), bound(d['facts'][0], unverified_branch=True)),
    lambda d: d['facts'][0].update(lifecycle_state='contested'),
    # Unhashable or non-string JSON where a string is required: refused, never a `TypeError`.
    lambda d: d['articles'][0].update(revision=[]),
    lambda d: d['articles'][0].update(id=[]),
    lambda d: d['facts'][0].update(claim_kind={}),
    lambda d: d['facts'][0].update(evidence_basis=[]),
    lambda d: d['facts'][0].update(lifecycle_state={}),
    lambda d: bound(d['facts'][0], []),
    lambda d: d['facts'][0].update(links=[{}]),
    lambda d: d['facts'][1].update(links=[dict(rel=[], target='fact-a')]),
    lambda d: d['facts'][0].update(stale_citations=[[]]),
    lambda d: d['history']['replaced'].update({'old-fact': dict(reason=[], by=['fact-a'])}),
    lambda d: d['history'].update(ended=[{}]),
], ids=lambda _: 'mutation')
def test_inconsistent_derived_fields_suppressed_flags_and_unhashable_values_are_refused(change):
    value = graph()
    change(value)
    with pytest.raises(PlayerError, match='unsupported delivered knowledge'):
        Knowledge.from_dict(value)


def test_the_caller_changing_its_dict_after_from_dict_changes_nothing():
    value = graph()
    knowledge = Knowledge.from_dict(value)
    value['facts'][0]['text'] = 'Zebra.'
    value['articles'].clear()
    value['history']['replaced'].clear()
    assert knowledge.read('guide')['records'][0]['id'] == 'guide'
    assert knowledge.read('guide@v1')['resolution'] == 'revision'
    assert knowledge.read('fact-a')['records'][0]['text'] == 'A claim.'
    assert ids(knowledge.query('zebra')) == []


def test_safe_integer_version_revision_and_step_guards_avoid_int_str_limit():
    huge = '9' * 5000
    assert version_number('v0') == 0
    assert version_number(f'v{MAX_SAFE_INT}') == MAX_SAFE_INT
    assert version_number(f'v{MAX_SAFE_INT + 1}') is None
    assert version_number(f'v{huge}') is None
    assert version_number('v1\n') is None
    assert revision_parts(f'guide@v{MAX_SAFE_INT}') == ('guide', MAX_SAFE_INT)
    assert revision_parts(f'guide@v{MAX_SAFE_INT + 1}') is None
    assert revision_parts(f'guide@v{huge}') is None
    assert revision_parts('guide@v1\n') is None

    # Safe non-negative integral JSON numbers are accepted; booleans, negatives, fractions, NaN/Inf and >=2**53 are refused.
    base = document([article('guide', 'Guide', 'Lead.', ('Claim.', ['fact-a']))], [fact('fact-a', 'A claim.')])
    base['coverage'] = dict(schema='curator-coverage/2', session='s01', actor='001', last_step=0.0)
    base['facts'][0]['seen']['step'] = float(MAX_SAFE_INT)
    base['facts'][0]['seen']['order'] = [0.0, '001', float(MAX_SAFE_INT)]
    Knowledge.from_dict(base)
    for bad in (True, False, -1, -1.0, 1.5, float('nan'), float('inf'), MAX_SAFE_INT + 1, float(MAX_SAFE_INT + 1)):
        for mut in (
            lambda d, v=bad: d['coverage'].update(last_step=v),
            lambda d, v=bad: d['facts'][0]['seen'].update(step=v),
            lambda d, v=bad: d['facts'][0]['seen']['order'].__setitem__(0, v),
            lambda d, v=bad: d['facts'][0]['seen']['order'].__setitem__(2, v),
        ):
            value = copy.deepcopy(base)
            mut(value)
            assert not _valid(value), bad


# `player-knowledge/3` reads, in table order.

def read(knowledge: Knowledge, identity: str, **options) -> tuple[str, str | None, list[str]]:
    result = knowledge.read(identity, **options)
    assert set(result) == {'schema', 'version', 'grants_authority', 'identity', 'resolution', 'resolved_from', 'records'}
    assert (result['schema'], result['grants_authority'], result['identity']) == (RESULT, False, identity)
    return result['resolution'], result['resolved_from'], ids(result)


def test_every_resolution_on_the_shared_full_graph_fixture():
    knowledge = Knowledge(FULL)
    assert RESULT == 'player-knowledge/3'
    assert read(knowledge, 'camp-water') == ('current', None, ['camp-water'])
    assert read(knowledge, 'boil-water') == ('current', None, ['boil-water'])
    assert read(knowledge, 'camp-water@v12') == ('revision', 'camp-water@v12', ['camp-water'])
    assert read(knowledge, 'camp-water@v4') == ('revision', 'camp-water@v4', ['camp-water'])
    assert read(knowledge, 'old-water-fact') == ('restated', 'old-water-fact', ['boil-water'])
    assert read(knowledge, 'broad-fire-claim') == ('narrowed', 'broad-fire-claim', ['fire-rule-standard', 'fire-rule-camp'])
    assert read(knowledge, 'broken-tank-claim') == ('corrected', 'broken-tank-claim', ['tank-empty'])
    assert read(knowledge, 'ended-fire') == ('ended', 'ended-fire', [])
    assert read(knowledge, 'retired-guide') == ('ended', 'retired-guide', [])
    assert read(knowledge, 'wrong-fact') == ('retracted', 'wrong-fact', [])
    assert read(knowledge, 'Camp water') == ('title', None, ['camp-water'])
    assert read(knowledge, 'camp water') == ('title', None, ['camp-water'])
    assert read(knowledge, 'CAMP WATER') == ('title', None, ['camp-water'])
    assert read(knowledge, 'Camp water', by='id') == ('unknown', None, [])
    assert read(knowledge, 'camp water', by='id') == ('unknown', None, [])
    for missing in ('camp-water@v5', 'unicorn', ''):
        assert read(knowledge, missing) == ('unknown', None, [])
    assert knowledge.read('camp-water')['version'] == knowledge.value['version']


def test_casefolded_title_lookup_prefers_exact_literal_breaks_ties_in_delivered_order_and_respects_by_id():
    knowledge = store([
        article('first-upper', 'CAMP WATER', 'Lead 1.', ('Claim 1.', ['fact-a'])),
        article('second-mixed', 'Camp water', 'Lead 2.', ('Claim 2.', ['fact-a'])),
        article('unicode-title', 'Straße', 'Lead 3.', ('Claim 3.', ['fact-a'])),
    ], [fact('fact-a', 'A claim.')])
    # Exact literal title wins over an earlier casefolded-equivalent title.
    assert read(knowledge, 'Camp water') == ('title', None, ['second-mixed'])
    assert read(knowledge, 'CAMP WATER') == ('title', None, ['first-upper'])
    # When no literal title matches, casefold tie-breaks by first in delivered order.
    assert read(knowledge, 'camp water') == ('title', None, ['first-upper'])
    assert read(knowledge, 'cAmP wAtEr') == ('title', None, ['first-upper'])
    # Full Unicode casefolding matches `Straße` and `STRASSE`.
    assert read(knowledge, 'STRASSE') == ('title', None, ['unicode-title'])
    # `by='id'` never falls back to exact or casefolded title lookup.
    for title in ('Camp water', 'CAMP WATER', 'camp water', 'STRASSE'):
        assert read(knowledge, title, by='id') == ('unknown', None, [])


def test_an_identifier_wins_over_an_equal_title_and_by_id_never_falls_back_to_a_title():
    # An article titled with another record's fact ID, and articles titled with old identifiers.
    knowledge = store([article('guide', 'fact-a', 'Lead.', ('Claim.', ['fact-a'])),
                       article('notes', 'old-fact', 'Lead.', ('Claim.', ['fact-a'])),
                       article('later', 'gone-fact', 'Lead.', ('Claim.', ['fact-a'])),
                       article('other', 'withheld-fact', 'Lead.', ('Claim.', ['fact-a']))],
                      [fact('fact-a', 'A claim.')],
                      dict(replaced={'old-fact': dict(reason='corrected', by=['fact-a'])}, ended=['gone-fact'], retracted=[]))
    assert read(knowledge, 'fact-a') == ('current', None, ['fact-a'])
    assert read(knowledge, 'old-fact') == ('corrected', 'old-fact', ['fact-a'])
    assert read(knowledge, 'gone-fact') == ('ended', 'gone-fact', [])
    # A withheld end reads as an unrelated article's title only when the title fallback is allowed.
    assert read(knowledge, 'withheld-fact') == ('title', None, ['other'])
    assert read(knowledge, 'withheld-fact', by='id') == ('unknown', None, [])
    assert read(knowledge, 'fact-a', by='id') == ('current', None, ['fact-a'])
    for bad in ('title', 'ID', None):
        with pytest.raises(PlayerError, match='`by`'):
            knowledge.read('fact-a', by=bad)


def test_read_records_are_closed_delivered_copies():
    knowledge = Knowledge(FULL)
    record = knowledge.read('camp-water')['records'][0]
    assert record == knowledge.value['articles'][0] and 'status' not in record and 'resolved_from' not in record
    record['title'] = 'changed'
    knowledge.read('broad-fire-claim')['records'][0]['text'] = 'changed'
    assert knowledge.read('camp-water')['records'][0]['title'] == 'Camp water'
    assert knowledge.value == json.loads(FULL.read_text())


# `bm25_1hop` ranking: synthetic corpora that always run.

# A synthetic multi-article corpus written for this test. Its articles are not records of any delivered
# version; they only give the two query strings below, which a #896-b player sent, something to rank.
FIELD = store([
    article('article-food', 'Food and consumption',
            'Use the Consume menu to inspect nutrition and freshness before eating.',
            ('Consume shows food, freshness, calories and quench; cooked greens and a raw stalk were eaten.', ['fact-consume'])),
    article('article-brazier', 'Brazier fires',
            'An existing brazier can hold a wood fire for nearby cooking recipes.',
            ('A matchbook lit wood in a brazier and a roasting recipe then showed a nearby fire as its cooking tool.',
             ['fact-brazier'])),
    article('article-bed', 'Bed construction',
            'Compare bedding construction and crafting options and check materials before gathering supplies.',
            ('A straw bed needs straw; withered plants and tall grass were harvested for bedding.', ['fact-bed'])),
    article('article-cattail', 'Cattail foraging',
            'Cattails at a lakeshore can yield food; examine the plant from an adjacent tile.',
            ('The harvest yielded a fresh rhizome and stalks, eaten raw or cooked with suitable equipment.', ['fact-cattail'])),
    article('article-setup', 'Wilderness character setup',
            'Choose Wilderness and verify the profession and starting location before finishing.',
            ('The scenario lists Survivor as its default profession.', ['fact-pointpool'])),
], [
    fact('fact-consume', 'The Consume menu lists freshness and calories.', 'Consume menu'),
    fact('fact-brazier', 'A brazier holds a fire lit with a matchbook.', 'Brazier'),
    fact('fact-bed', 'A straw bed construction needs straw.', 'Straw bed'),
    fact('fact-cattail', 'Cattail rhizomes are edible.', 'Cattail'),
    fact('fact-pointpool', "The character editor's point-pool screen says no point limits are enforced.", 'Survivor point pool'),
    fact('fact-door', 'The cabin door was locked from outside.', 'Cabin door'),
])


def test_two_896_b_query_strings_rank_the_relevant_articles_of_a_synthetic_corpus_first():
    cooking = ids(FIELD.query('food cooking roasting stick makeshift cooking tool campfire'))
    assert set(cooking[:3]) == {'article-brazier', 'article-food', 'article-cattail'}, cooking
    assert 'fact-door' not in cooking
    straw = ids(FIELD.query('straw withered plants harvest tall grass grass straw'))
    assert straw[0] == 'article-bed', straw
    assert 'article-cattail' in straw and 'fact-door' not in straw


def test_a_record_need_not_hold_every_term_and_a_better_match_ranks_higher():
    # The brazier fact holds the word itself; the article ranks first on its title and its lift from the fact.
    assert ids(FIELD.query('brazier unicorn')) == ['article-brazier', 'fact-brazier']
    assert set(ids(FIELD.query('straw bed'))[:2]) == {'article-bed', 'fact-bed'}
    # A title word outranks the same word only in a body.
    titled = store([article('a-body', 'Shelter', 'Pitch it.', ('A tent stands here.', ['f'])),
                    article('a-title', 'Tent', 'Pitch it.', ('It stands here.', ['f']))], [fact('f', 'Stakes hold.')])
    assert ids(titled.query('tent'))[:2] == ['a-title', 'a-body']


def test_tags_match_at_lead_weight_a_hyphen_separates_words_and_claim_kind_is_not_indexed():
    tagged = store([], [fact('fact-door', 'The cabin door was locked.', 'Cabin door', kind='interface', tags=['door-control']),
                        fact('fact-recipe', 'Needs two sticks and a rock.', 'Stone knife', tags=['crafting-recipe']),
                        fact('fact-rain', 'Rain fell at dusk.', kind='instance_state',
                             scope=dict(game='example', world=None), branch_relation='same')])
    # Neither the subject nor the text of these facts holds the query word; only a tag does.
    assert ids(tagged.query('control')) == ['fact-door']
    assert ids(tagged.query('crafting')) == ['fact-recipe']
    assert ids(tagged.query('recipe')) == ['fact-recipe']
    assert ids(tagged.query('interface')) == [] and ids(tagged.query('instance state')) == []
    # A tag on an article counts with its lead, below its title.
    articles = store([article('by-tag', 'Shelter', 'Pitch it.', ('Here.', ['f']), tags=['tent']),
                      article('by-title', 'Tent', 'Pitch it.', ('Here.', ['f']))], [fact('f', 'Stakes hold.')])
    assert ids(articles.query('tent'))[:2] == ['by-title', 'by-tag']


def test_one_hop_lifts_cited_and_linked_neighbours_without_reaching_unrelated_records():
    knowledge = store([article('water', 'Water treatment', 'Boil before drinking.', ('Boiling works.', ['boil'])),
                       article('fire', 'Fire starting', 'Use a bow drill.', ('A drill lights tinder.', ['drill']),
                               links=[dict(rel='depends_on', target='water')])],
                      [fact('boil', 'A pot on a fire boils murky liquid.', 'Pot'),
                       fact('drill', 'The bow drill needs cordage.', 'Bow drill'),
                       fact('alone', 'Murky liquid sits in the pond.', 'Pond'),
                       fact('unrelated', 'Snow fell.', 'Weather')])
    # `murky` is only in two facts. The isolated one takes no seed slot; the cited one lifts its article, which
    # (now positive) is not a seed and so does not lift the linked article in turn.
    result = ids(knowledge.query('murky'))
    assert set(result) == {'boil', 'alone', 'water'} and result.index('water') > result.index('boil'), result
    # A link is an undirected edge: a query that reaches only the fire article lifts the linked water article.
    assert ids(knowledge.query('tinder'))[:2] == ['fire', 'water']
    assert 'unrelated' not in ids(knowledge.query('murky tinder drill water'))


def test_a_lower_scoring_connected_record_takes_a_seed_slot_over_ten_better_isolated_matches():
    isolated = [fact(f'isolated-{n:02}', 'Zebra zebra.', step=n + 2) for n in range(10)]
    knowledge = store([article('guide', 'Guide', 'Lead.', ('Claim.', ['seed']))],
                      [fact('seed', 'A zebra crossed near the old mill road at dusk.'), *isolated])
    scores = knowledge._bm25('zebra')
    seed, guide = knowledge._position['seed'], knowledge._position['guide']
    assert scores[guide] == 0 and all(scores[knowledge._position[f['id']]] > scores[seed] > 0 for f in isolated)
    # The connected seed is the eleventh-best match yet the only one with a neighbour, so it lifts its article.
    assert knowledge._one_hop('zebra')[guide] == pytest.approx(0.35 * scores[seed] * 1.25)


def test_the_hop_follows_the_formula_and_an_article_neighbour_gains_more_than_a_fact():
    knowledge = store([article('guide', 'Guide', 'Lead.', ('Claim.', ['seed']))],
                      [fact('seed', 'Zebra crossing.', links=[dict(rel='see_also', target='peer')]),
                       fact('peer', 'Other text.')])
    scores = knowledge._bm25('zebra')
    assert scores[0] == 0 and scores[2] == 0 and scores[1] > 0
    # The seed has two neighbours (the citing article and the linked fact); its own score is unchanged.
    spread = 0.35 * scores[1] / math.sqrt(2)
    assert knowledge._one_hop('zebra') == pytest.approx([spread * 1.25, scores[1], spread * 0.70])
    assert ids(knowledge.query('zebra')) == ['seed', 'guide', 'peer']


def test_no_coverage_skip_keeps_a_cited_fact_beside_its_article():
    """#936 dropped the rank-order coverage skip: a direct-answer fact stays in the top results with its article."""
    knowledge = store([article('spear', 'Wooden spear pointy stick', 'Craft a spear from a pointy stick.',
                               ('The spear has reach.', ['stick-pierce']))],
                      [fact('stick-pierce', 'A long pointy stick does pierce 9.', 'Long pointy stick')])
    assert ids(knowledge.query('what pierce damage does a long pointy stick do')) == ['stick-pierce', 'spear']
    assert ids(knowledge.query('wooden spear pointy stick')) == ['spear', 'stick-pierce']


def test_no_match_or_no_words_returns_no_hits_with_the_current_envelope():
    for query in ('unicorn', '   ', '?!'):
        assert FIELD.query(query) == dict(schema=RESULT, version='v1', grants_authority=False, identity=query,
                                          resolution='query', resolved_from=None, hits=[])
    assert Knowledge.from_dict(empty()).query('water')['hits'] == []


def test_ties_keep_delivered_order_the_result_is_capped_and_hits_are_copies():
    many = store([], [fact(f'fact-{n:02}', 'Claim about water.', step=n + 1, tags=['water']) for n in range(QUERY_LIMIT + 5)])
    assert ids(many.query('water')) == [f'fact-{n:02}' for n in range(QUERY_LIMIT)]
    hit = many.query('water')['hits'][0]
    hit['snippet'] = 'changed'
    hit['scope']['game'] = 'changed'
    hit['cited_by_articles'].append('changed')
    fresh = many.query('water')['hits'][0]
    assert fresh['snippet'] == 'Claim about water.' and fresh['scope'] == {'game': 'example'} and fresh['cited_by_articles'] == []


def test_compact_query_hits_shape_via_status_clipping_and_cited_by_cap():
    long_lead = ('alpha ' * 60).strip()
    long_text = 'x' * (SNIPPET_LIMIT - 2) + '   tail'
    arts = [
        article('art-direct', 'Zebra guide', long_lead, ('C.', ['fact-hop']), tags=['zebra'],
                scope=dict(game='example', world=None), branch_relation='same', lifecycle_state='contested',
                unverified_branch=True, needs_review=True, condition_unverified=True),
        *[article(f'ref-{c}', f'Ref {c}', 'Short lead.', ('C.', ['fact-hop']),
                  scope=dict(game='example', world=None), branch_relation='same', lifecycle_state='contested',
                  unverified_branch=True, condition_unverified=True) for c in ('d', 'b', 'a', 'c')],
        article('art-clean', 'Zebra clean', 'Exact length lead.', ('C.', ['fact-clean']), tags=['zebra']),
    ]
    facts = [
        fact('fact-hop', long_text, subject=None, step=1, scope=dict(game='example', world=None),
             branch_relation='unknown', unverified_branch=True, needs_review=True, condition_unverified=True,
             links=[dict(rel='contradicts', target='fact-conflict')], contradicted_by=['fact-conflict'],
             lifecycle_state='contested'),
        fact('fact-conflict', 'Opposing claim.', subject='Other', step=2,
             scope=dict(game='example', world=None), branch_relation='same', contradicted_by=['fact-hop'],
             lifecycle_state='contested'),
        fact('fact-clean', 'Plain active fact.', subject='Plain', step=3),
    ]
    compact_store = store(arts, facts)
    result = compact_store.query('zebra')
    assert set(result) == {'schema', 'version', 'grants_authority', 'identity', 'resolution', 'resolved_from', 'hits'}
    assert result['schema'] == RESULT and result['resolution'] == 'query'
    by_id = {h['id']: h for h in result['hits']}
    assert set(by_id['art-direct']) == {'id', 'kind', 'revision', 'title', 'snippet', 'tags', 'via', 'status'}
    assert by_id['art-direct']['kind'] == 'article' and by_id['art-direct']['via'] == 'match'
    assert len(by_id['art-direct']['snippet']) <= SNIPPET_LIMIT and by_id['art-direct']['snippet'].endswith('…')
    assert not by_id['art-direct']['snippet'][:-1].endswith(' ')
    assert by_id['art-direct']['status'] == ['contested', 'unverified_branch', 'needs_review', 'condition_unverified']
    # Plainly active article omits `status`.
    assert set(by_id['art-clean']) == {'id', 'kind', 'revision', 'title', 'snippet', 'tags', 'via'}
    assert 'status' not in by_id['art-clean'] and by_id['art-clean']['snippet'] == 'Exact length lead.'
    # 1-hop fact carries `via: 'hop'`, explicit `subject: None`, clipped snippet, sorted capped `cited_by_articles` (3),
    # and status markers in contract order.
    assert set(by_id['fact-hop']) == {
        'id', 'kind', 'subject', 'claim_kind', 'scope', 'snippet', 'cited_by_articles', 'via', 'status'
    }
    assert by_id['fact-hop']['kind'] == 'fact' and by_id['fact-hop']['via'] == 'hop'
    assert by_id['fact-hop']['subject'] is None
    assert len(by_id['fact-hop']['snippet']) <= SNIPPET_LIMIT and by_id['fact-hop']['snippet'].endswith('…')
    assert not by_id['fact-hop']['snippet'][:-1].endswith(' ')
    assert by_id['fact-hop']['cited_by_articles'] == ['art-direct', 'ref-a', 'ref-b']
    assert len(by_id['fact-hop']['cited_by_articles']) == HIT_CITED_BY_LIMIT
    assert by_id['fact-hop']['status'] == ['contested', 'unverified_branch', 'needs_review', 'condition_unverified']
    # Plainly active 1-hop fact omits `status` and preserves non-null subject.
    assert 'status' not in by_id['fact-clean'] and by_id['fact-clean']['subject'] == 'Plain'
    assert by_id['fact-clean']['via'] == 'hop'
    assert actor_result(result) == result


def test_terms_fold_case_punctuation_and_one_regular_inflection_alike_for_query_and_record():
    assert terms_of('Plants, harvested; COOKING berries grass!') == ['plant', 'harvest', 'cook', 'berry', 'grass']
    assert terms_of('bed is gas') == ['bed', 'is', 'gas']
    assert {'article-bed', 'article-cattail'} <= set(ids(FIELD.query('plant')))


# Callers: the tool schema, the application and the player view.

def test_the_read_tool_takes_an_optional_by_and_the_application_passes_it(tmp_path):
    # `actor_result` rejects a revision read newer than the returned article's own revision.
    newer_rev = dict(Knowledge(FULL).read('article-camp@v1'), version='v3', identity='article-camp@v2',
                     resolved_from='article-camp@v2')
    with pytest.raises(UnsupportedResult):
        actor_result(newer_rev)
    _, schema = tool_specs()['player_knowledge_read']
    assert schema['properties']['by'] == dict(type='string', enum=['any', 'id'])
    assert 'by' not in schema['required'] and 'id_or_title' in schema['required']
    query_desc, _ = tool_specs()['player_knowledge_query']
    assert 'compact hits' in query_desc and 'player_knowledge_read' in query_desc
    runtime, _, actor = make_runtime(tmp_path)
    journal = Journal(tmp_path / 'player.sqlite3')
    app = Application(runtime, journal, tmp_path / 'contexts', knowledge=FULL)
    try:
        def call(name, **args):
            return app.call(actor['token'], name, dict(args, intent='look up knowledge'), uuid.uuid4().hex)[0]
        assert call('player_knowledge_read', id_or_title='Camp water')['resolution'] == 'title'
        assert call('player_knowledge_read', id_or_title='camp water')['resolution'] == 'title'
        assert call('player_knowledge_read', id_or_title='Camp water', by='id')['resolution'] == 'unknown'
        assert call('player_knowledge_read', id_or_title='camp water', by='id')['resolution'] == 'unknown'
        assert call('player_knowledge_read', id_or_title='old-water-fact', by='any')['records'][0]['id'] == 'boil-water'
        query = call('player_knowledge_query', query='camp water')
        assert query['schema'] == RESULT and query['resolution'] == 'query' and 'hits' in query and 'records' not in query
        with pytest.raises(PlayerError, match='`by`'):
            call('player_knowledge_read', id_or_title='camp-water', by='title')
        with pytest.raises(PlayerError, match='optional by'):
            call('player_knowledge_read', id_or_title='camp-water', extra=1)
        with pytest.raises(ControlError):
            call('player_knowledge_query', query='water', by='id')
    finally:
        runtime.close(); journal.close()


def test_the_player_view_projects_only_the_current_knowledge_result():
    knowledge = Knowledge(FULL)
    for result in (knowledge.read('old-water-fact'), knowledge.read('unicorn'), knowledge.query('camp water')):
        assert actor_result(result) == result
    for fixture_name in ('read-article.json', 'query-compact-hits.json'):
        fixture = json.loads((PK3_FIXTURES / fixture_name).read_text())
        assert actor_result(fixture) == fixture
    for bad in (dict(knowledge.read('camp-water'), schema='player-knowledge/1'),
                dict(knowledge.read('camp-water'), schema='player-knowledge/2'),
                dict(knowledge.query('camp water'), schema='player-knowledge/2'),
                dict(knowledge.read('camp-water'), resolution='guess'),
                dict(knowledge.read('camp-water'), grants_authority=True),
                {k: v for k, v in knowledge.read('camp-water').items() if k != 'resolved_from'}):
        with pytest.raises(UnsupportedResult):
            actor_result(bad)


def _changed(result: dict, change) -> dict:
    result = copy.deepcopy(result)
    change(result)
    return result


def test_the_player_view_projects_every_resolution_of_the_read_table():
    knowledge = Knowledge(FULL)
    for identity in ('camp-water', 'boil-water', 'camp-water@v12', 'camp-water@v4', 'old-water-fact', 'broad-fire-claim',
                     'broken-tank-claim', 'ended-fire', 'wrong-fact', 'Camp water', 'camp water', 'unicorn'):
        assert actor_result(knowledge.read(identity)) == knowledge.read(identity)
    for result in (Knowledge.from_dict(empty()).read('water'), Knowledge.from_dict(empty()).query('water')):
        assert actor_result(result) == result
    # Every ranked compact hit is checked as well: one raw world label refuses the whole query result.
    query = knowledge.query('camp water')
    fact_index = next(i for i, h in enumerate(query['hits']) if h['kind'] == 'fact')
    assert len(query['hits']) > 1
    with pytest.raises(UnsupportedResult):
        actor_result(_changed(query, lambda r: r['hits'][fact_index]['scope'].update(world='world-alpha')))


@pytest.mark.parametrize('identity, change', [
    # The version.
    ('camp-water', lambda r: r.update(version='v12\n')),
    ('camp-water', lambda r: r.update(version=12)),
    ('unicorn', lambda r: r.update(version=[])),
    ('boil-water', lambda r: r.update(version=None)),
    # A resolution's record count, record kind or `resolved_from` outside its row of the table.
    ('camp-water', lambda r: r.update(records=[])),
    ('camp-water', lambda r: r.update(resolved_from='camp-water')),
    ('camp-water', lambda r: r['records'].append(copy.deepcopy(r['records'][0]))),
    ('camp-water', lambda r: r.update(resolution=[])),
    ('camp-water@v12', lambda r: r.update(resolved_from=None)),
    ('camp-water@v12', lambda r: r.update(resolved_from='camp-water')),
    ('camp-water@v12', lambda r: r.update(records=Knowledge(FULL).read('boil-water')['records'])),
    ('old-water-fact', lambda r: r.update(records=[])),
    ('old-water-fact', lambda r: r.update(resolved_from=' ')),
    ('old-water-fact', lambda r: r.update(resolved_from=None)),
    ('ended-fire', lambda r: r.update(records=Knowledge(FULL).read('boil-water')['records'])),
    ('wrong-fact', lambda r: r.update(resolved_from=None)),
    ('Camp water', lambda r: r.update(records=Knowledge(FULL).read('boil-water')['records'])),
    ('Camp water', lambda r: r.update(resolved_from='Camp water')),
    ('unknown-id', lambda r: r.update(records=Knowledge(FULL).read('boil-water')['records'])),
    ('unknown-id', lambda r: r.update(resolved_from='unknown-id')),
    # The empty file's null version answers only `unknown` and `query`.
    ('ended-fire', lambda r: r.update(version=None)),
    ('wrong-fact', lambda r: r.update(version=None)),
    ('unknown-id', lambda r: r.update(version=None, resolved_from='unknown-id')),
    # Records and `resolved_from` that do not answer the identity asked for.
    ('camp-water', lambda r: r.update(identity='boil-water')),
    ('camp-water@v12', lambda r: r.update(identity='boil-water@v12', resolved_from='boil-water@v12')),
    ('camp-water@v4', lambda r: r.update(resolved_from='camp-water@v12')),
    ('old-water-fact', lambda r: r.update(resolved_from='other-fact')),
    ('old-water-fact', lambda r: r.update(records=Knowledge(FULL).read('camp-water')['records'])),
    ('broad-fire-claim', lambda r: r['records'].append(Knowledge(FULL).read('camp-water')['records'][0])),
    ('ended-fire', lambda r: r.update(resolved_from='wrong-fact')),
    ('Camp water', lambda r: r.update(identity='Other title')),
    # A record that is not a closed, blinded delivered record.
    ('camp-water', lambda r: r['records'][0].update(status=['contested'])),
    ('camp-water', lambda r: r['records'][0]['scope'].update(world='world-alpha')),
    ('camp-water', lambda r: r['records'][0]['last_confirmed'].update(session='2026-11-24-session')),
    ('camp-water', lambda r: r['records'][0].update(revision='camp-water@v13')),
    ('camp-water', lambda r: r['records'][0].update(unverified_branch=False)),
    ('camp-water', lambda r: r['records'][0].update(revision=[])),
    ('boil-water', lambda r: r['records'][0].update(claim_kind={})),
    ('boil-water', lambda r: r['records'][0].pop('seen')),
    ('boil-water', lambda r: r['records'][0]['seen'].update(session='s1')),
    ('boil-water', lambda r: r['records'][0].update(links=[{}])),
    ('boil-water', lambda r: r.update(records=[1])),
], ids=lambda value: value if isinstance(value, str) else 'mutation')
def test_the_player_view_refuses_an_inconsistent_or_unblinded_knowledge_result(identity, change):
    result = Knowledge(FULL).read(identity)
    with pytest.raises(UnsupportedResult):
        actor_result(_changed(result, change))


def test_the_player_view_refuses_malformed_or_oversized_compact_query_results():
    from harness.jsonio import canonical
    query = Knowledge(FULL).query('camp water')
    article_hit = next(h for h in query['hits'] if h['kind'] == 'article')
    fact_hit = next(h for h in query['hits'] if h['kind'] == 'fact')
    full = _changed(query, lambda r: r.update(hits=[dict(fact_hit, id=f'fact-{i}') for i in range(QUERY_LIMIT)]))
    assert actor_result(full) == full
    # Supplementary Unicode at the 240-char snippet clipping boundary stays valid UTF-8.
    base_doc = json.loads(FULL.read_text())
    emoji_lead = 'a' * 238 + '😀' + 'tail'
    emoji_doc = copy.deepcopy(base_doc)
    emoji_doc['articles'][0]['lead'] = emoji_lead
    emoji_query = Knowledge.from_dict(emoji_doc).query('camp water')
    assert actor_result(emoji_query) == emoji_query
    assert canonical(emoji_query).encode('utf-8')
    # Lone surrogate in delivered text is rejected before query/serialization.
    surrogate_doc = copy.deepcopy(base_doc)
    surrogate_doc['articles'][0]['lead'] = 'bad \ud800 lead'
    with pytest.raises(PlayerError):
        Knowledge.from_dict(surrogate_doc)
    for bad in (
        _changed(full, lambda r: r['hits'].append(dict(fact_hit, id='fact-extra'))),
        _changed(query, lambda r: r.update(hits=[fact_hit, fact_hit])),
        _changed(query, lambda r: r.update(resolved_from='camp water')),
        # Discriminated envelope: `query` cannot carry `records`, and `read` cannot carry `hits`.
        _changed(query, lambda r: (r.update(records=[]), r.pop('hits'))),
        _changed(query, lambda r: r.update(records=[])),
        _changed(Knowledge(FULL).read('camp-water'), lambda r: (r.update(hits=[]), r.pop('records'))),
        _changed(Knowledge(FULL).read('camp-water'), lambda r: r.update(hits=[])),
        # Closed per-kind compact hit validation.
        _changed(query, lambda r: r.update(hits=[dict(article_hit, status=[])])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, status=['needs_review', 'contested'])])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, status=['contested', 'contested'])])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, via='direct')])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, snippet='x' * (SNIPPET_LIMIT + 1))])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, snippet='   ')])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, snippet='bad \ud800 snippet')])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, revision='camp-water@v99')])),
        _changed(query, lambda r: r.update(hits=[dict(article_hit, extra=1)])),
        _changed(query, lambda r: r.update(hits=[dict(fact_hit, status=[])])),
        _changed(query, lambda r: r.update(hits=[dict(fact_hit, cited_by_articles=['a', 'b', 'c', 'd'])])),
        _changed(query, lambda r: r.update(hits=[dict(fact_hit, cited_by_articles=['b', 'a'])])),
        _changed(query, lambda r: r.update(hits=[dict(fact_hit, cited_by_articles=[fact_hit['id']])])),
        _changed(query, lambda r: r.update(hits=[dict(fact_hit, scope={'game': 'example'}, status=['unverified_branch'])])),
        _changed(query, lambda r: r.update(hits=[dict(fact_hit, claim_kind='instance_state', scope={'game': 'example'})])),
        _changed(query, lambda r: r.update(hits=[dict(fact_hit, kind='other')])),
        _changed(query, lambda r: r.update(hits=[{k: v for k, v in fact_hit.items() if k != 'subject'}])),
        _changed(query, lambda r: r.update(version=None)),
    ):
        with pytest.raises(UnsupportedResult):
            actor_result(bad)


# Gate 9: the #924 queries on test-only projections of sealed files into `delivered-knowledge/3`.

def _sealed(corpus: str) -> Path:
    """The sealed file, or a skip when this checkout holds no store. A clone recorded as holding the store
    (`enactive.evidenceStore = expected`) fails instead when the file is missing, so a lost store or a lost sealed
    file cannot pass Gate 9 as a skip."""
    from tools.evidence import default_store, store_expected
    from tools.knowledge_retrieval_benchmark import CORPORA
    store_root = default_store()
    path = store_root / CORPORA[corpus]
    if not path.is_file():
        if store_expected():
            pytest.fail(f'missing sealed corpus {path}')
        pytest.skip(f'sealed {corpus} is not in this checkout\'s evidence store')
    return path


def project(old: dict) -> dict:
    """A sealed `delivered-knowledge/2` file in the new closed form, for this test only and never a runtime reader.

    The old ID stands in for the slug, and a link (a title) resolves to the article with that title as `see_also`.
    The old `type`, kebab-cased, becomes the one tag, so it keeps the weight-2 slot #936 measured. Session names
    become aliases; source IDs are synthetic in the canonical form."""
    aliases: dict[str, str] = {}

    def alias(where: dict) -> dict:
        return dict(where, session=aliases.setdefault(where['session'], f's{len(aliases) + 1:02}'))

    titles = {a['title']: a['id'] for a in old['articles']}
    articles = []
    for a in old['articles']:
        links = [dict(rel='see_also', target=titles[t]) for t in dict.fromkeys(a['links']) if titles[t] != a['id']]
        articles.append(dict(id=a['id'], revision=f"{a['id']}@{old['version']}", title=a['title'], lead=a['lead'],
                             body=a['body'], last_confirmed=alias(a['last_confirmed']), **flags(links=links)))
    facts = []
    for n, f in enumerate(old['facts'], 1):
        facts.append(dict(id=f['id'], claim_kind='mechanic', evidence_basis='observed', text=f['text'],
                          cited_by_articles=[], citation_source_ids=[f'{n:032x}-1'], seen=alias(f['seen']),
                          **({} if 'subject' not in f else dict(subject=f['subject'])),
                          **flags(tags=[f['type'].replace('_', '-')])))
    value = document(articles, facts, version=old['version'])
    value.update(commit=old['commit'], repository_id=old['repository_id'],
                 coverage=None if old['coverage'] is None else alias(old['coverage']))
    return value


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


# #936's #920 baseline (prod_bm25) on the same queries: Hit@5 and article MRR@5.
BASELINE = {'v91': (1.000, 0.700), 'v17': (1.000, 0.650)}


@pytest.mark.parametrize('corpus', ['v91', 'v17'])
def test_gate_9_bm25_1hop_meets_the_920_baseline_on_projected_sealed_files(corpus):
    path = _sealed(corpus)
    from tools.knowledge_retrieval_benchmark import CUT, QUERIES
    knowledge = Knowledge.from_dict(project(json.loads(path.read_text())), str(path))
    cites = {a['id']: {f for c in a['body'] for f in c['facts']} for a in knowledge.value['articles']}
    queries = [q for q in QUERIES if q.corpus == corpus]
    hits, reciprocal = [], []
    for q in queries:
        top = ids(knowledge.query(q.text))[:CUT]
        wanted = set(q.gold) | {f for g in q.gold for f in cites[g]}
        hits.append(float(any(r in wanted for r in top)))
        reciprocal.append(next((1 / (rank + 1) for rank, r in enumerate(top) if r in q.gold), 0.0))
    samples = []
    for _ in range(50):
        for q in queries:
            start = time.perf_counter()
            knowledge.query(q.text)
            samples.append((time.perf_counter() - start) * 1000)
    hit, mrr, p95 = sum(hits) / len(hits), sum(reciprocal) / len(reciprocal), _percentile(samples, 0.95)
    print(f'{corpus}: Hit@5 {hit:.3f} ArtMRR@5 {mrr:.3f} p95 {p95:.3f} ms over {len(samples)} samples')
    assert hit >= BASELINE[corpus][0] and mrr >= BASELINE[corpus][1], (hit, mrr)
    assert p95 < 5.0, p95
