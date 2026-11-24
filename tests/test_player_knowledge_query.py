"""Ranked `player_knowledge_query` over delivered knowledge (#920)."""
from harness.player.knowledge import QUERY_LIMIT, SCHEMA, Knowledge, terms_of


def position(step: int) -> dict:
    return dict(session='s1', actor='001', step=step, order=[1, '001', step])


def article(identity: str, title: str, lead: str, *claims: str) -> dict:
    return dict(id=identity, title=title, lead=lead, links=[], last_confirmed=position(1),
                body=[dict(text=c, facts=[f'{identity}-fact']) for c in claims])


def fact(identity: str, text: str, subject: str | None = None, step: int = 1, kind: str = 'observation') -> dict:
    return dict(id=identity, type=kind, text=text, seen=position(step), **({} if subject is None else dict(subject=subject)))


def store(articles: list[dict], facts: list[dict]) -> Knowledge:
    return Knowledge.from_dict(dict(schema=SCHEMA, version='v1', commit='a' * 40, repository_id='b' * 40,
                                    coverage=None, articles=articles, facts=facts))


# A synthetic multi-article corpus written for this test. Its articles are not records of any delivered
# version; they only give the two query strings below, which a #896-b player sent, something to rank.
FIELD = store([
    article('article-food', 'Food and consumption',
            'Use the Consume menu to inspect nutrition and freshness before eating.',
            'Consume shows food, freshness, calories and quench; cooked greens and a raw stalk were eaten.'),
    article('article-brazier', 'Brazier fires',
            'An existing brazier can hold a wood fire for nearby cooking recipes.',
            'A matchbook lit wood in a brazier and a roasting recipe then showed a nearby fire as its cooking tool.'),
    article('article-bed', 'Bed construction',
            'Compare bedding construction and crafting options and check materials before gathering supplies.',
            'A straw bed needs straw; withered plants and tall grass were harvested for bedding.'),
    article('article-cattail', 'Cattail foraging',
            'Cattails at a lakeshore can yield food; examine the plant from an adjacent tile.',
            'The harvest yielded a fresh rhizome and stalks, eaten raw or cooked with suitable equipment.'),
    article('article-setup', 'Wilderness character setup',
            'Choose Wilderness and verify the profession and starting location before finishing.',
            'The scenario lists Survivor as its default profession.'),
], [
    fact('fact-pointpool', "The character editor's point-pool screen says no point limits are enforced.", 'Survivor point pool'),
    fact('fact-door', 'The cabin door was locked from outside.', 'Cabin door'),
])


def ids(result: dict) -> list[str]:
    return [r['id'] for r in result['records']]


def test_two_896_b_query_strings_rank_the_relevant_articles_of_a_synthetic_corpus_first():
    cooking = ids(FIELD.query('food cooking roasting stick makeshift cooking tool campfire'))
    assert set(cooking[:3]) == {'article-brazier', 'article-food', 'article-cattail'}, cooking
    assert 'fact-door' not in cooking
    straw = ids(FIELD.query('straw withered plants harvest tall grass grass straw'))
    assert straw[0] == 'article-bed', straw
    assert 'article-cattail' in straw and 'fact-door' not in straw


def test_a_record_need_not_hold_every_term_and_a_better_match_ranks_higher():
    result = FIELD.query('brazier unicorn')
    assert ids(result) == ['article-brazier']
    assert ids(FIELD.query('straw bed'))[0] == 'article-bed'
    # A title word outranks the same word only in a body.
    titled = store([article('a-body', 'Shelter', 'Pitch it.', 'A tent stands here.'),
                    article('a-title', 'Tent', 'Pitch it.', 'It stands here.')], [])
    assert ids(titled.query('tent')) == ['a-title', 'a-body']


def test_a_fact_type_alone_matches_and_its_underscore_separates_words():
    typed = store([], [fact('fact-door', 'The cabin door was locked.', 'Cabin door', kind='control'),
                       fact('fact-recipe', 'Needs two sticks and a rock.', 'Stone knife', kind='crafting_recipe'),
                       fact('fact-rain', 'Rain fell at dusk.')])
    # Neither the subject nor the text of these facts holds the query word; only the type does.
    assert ids(typed.query('control')) == ['fact-door']
    assert ids(typed.query('crafting')) == ['fact-recipe']
    assert ids(typed.query('recipe')) == ['fact-recipe']


def test_no_match_or_no_words_returns_no_records_with_the_unchanged_envelope():
    for query in ('unicorn', '   ', '?!'):
        assert FIELD.query(query) == dict(schema='player-knowledge/1', version='v1', grants_authority=False, records=[])


def test_ties_keep_delivered_order_the_result_is_capped_and_records_are_copies():
    many = store([], [fact(f'fact-{n:02}', 'Claim about water.', step=n) for n in range(QUERY_LIMIT + 5)])
    assert ids(many.query('water')) == [f'fact-{n:02}' for n in range(QUERY_LIMIT)]
    record = many.query('water')['records'][0]
    record['text'] = 'changed'
    assert many.query('water')['records'][0]['text'] == 'Claim about water.'


def test_terms_fold_case_punctuation_and_one_regular_inflection_alike_for_query_and_record():
    assert terms_of('Plants, harvested; COOKING berries grass!') == ['plant', 'harvest', 'cook', 'berry', 'grass']
    assert terms_of('bed is gas') == ['bed', 'is', 'gas']
    assert set(ids(FIELD.query('plant'))) == {'article-bed', 'article-cattail'}
