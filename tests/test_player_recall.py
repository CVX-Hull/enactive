"""Recall ranking (BM25 x confidence x residual), exploration, trust and `player-intent/2`.

The ranking module is pure; the intent tests use the actual composition over the receiver double.
"""
from collections import Counter
import hashlib
import math
import random

import pytest

from episode_support import act, bind, call, commit_first, episode, mint, put, replace, request_id, sync
from harness.application import Application
from harness.player import recall
from harness.player.episodes import claim_data
from harness.player.memory import Memory
from test_computer_runtime import make_runtime


def candidate(index, attempted, *, confidence=1., residual='', counterpart='', changed='', session='old'):
    return dict(record_id=f'r{index}', session=session, attempted=attempted, counterpart=counterpart, residual=residual,
                changed=changed, confidence=confidence, sources=[], created_wall=float(index))


def test_bm25_matches_the_standard_formula_with_k1_1_2_and_b_0_75():
    assert (recall.K1, recall.B, recall.RESIDUAL_WEIGHT) == (1.2, .75, 1.5)
    documents = [['door', 'door', 'key'], ['key', 'wall'], ['floor', 'floor', 'floor', 'floor']]
    scores = recall.bm25('door key', documents)
    average = (3 + 2 + 4) / 3
    idf = lambda n: math.log(1 + (3 - n + .5) / (n + .5))  # noqa: E731

    def expected(document):
        total = 0.
        for term, n in (('door', 1), ('key', 2)):
            tf = document.count(term)
            if tf:
                total += idf(n) * tf * 2.2 / (tf + 1.2 * (.25 + .75 * len(document) / average))
        return total
    assert scores == pytest.approx([expected(d) for d in documents])
    assert scores[2] == 0 and scores[0] > scores[1] > 0
    assert recall.bm25('door', []) == []


def test_a_longer_document_scores_lower_for_the_same_term_frequency():
    scores = recall.bm25('door', [['door', 'x'], ['door'] + ['x'] * 20, ['y', 'z']])
    assert scores[0] > scores[1] > 0


def test_tokens_are_lowercase_word_characters():
    assert recall.tokens("Open the DOOR, then the Key-card (2)!") == ['open', 'the', 'door', 'then', 'the', 'key', 'card', '2']


def test_rank_multiplies_by_confidence_and_one_and_a_half_for_a_residual():
    same = 'opened the door'
    items = [candidate(0, same, confidence=.4), candidate(1, same, confidence=.8),
             candidate(2, same, confidence=.4, residual='a surprise'), candidate(3, same, confidence=.8, residual='  ')]
    ranked = recall.rank(items, 'open the door')
    by = {r['episode']['record_id']: r['score'] for r in ranked}
    assert by['r1'] == pytest.approx(2 * by['r0']) and by['r3'] == pytest.approx(by['r1'])
    # The residual text is searchable too, so compare against the relevance of the same tokens.
    relevance = recall.bm25('open the door', [recall.tokens(' '.join(i[f] for f in recall.TEXT_FIELDS)) for i in items])
    assert by['r2'] == pytest.approx(relevance[2] * .4 * 1.5) and by['r0'] == pytest.approx(relevance[0] * .4)
    assert by['r3'] == pytest.approx(relevance[3] * .8)
    # A residual raises a record's rank: r2 (relevance x 0.4 x 1.5) overtakes an otherwise identical 0.5 record.
    contest = recall.rank([candidate(0, same, confidence=.5), candidate(1, same, confidence=.4, residual='x')], 'open the door')
    assert contest[0]['episode']['record_id'] == 'r1'
    # Ties go to the newer record.
    assert [r['episode']['record_id'] for r in recall.rank([candidate(0, same), candidate(1, same)], 'door')] == ['r1', 'r0']


def test_rank_searches_attempted_counterpart_residual_and_changed():
    items = [candidate(0, 'walked', counterpart='the guard'), candidate(1, 'walked', residual='a bell rang'),
             candidate(2, 'walked', changed='the lamp is lit'), candidate(3, 'walked')]
    for query, expected in (('guard', 'r0'), ('bell', 'r1'), ('lamp', 'r2')):
        assert recall.rank(items, query)[0]['episode']['record_id'] == expected


def test_a_higher_relevance_beats_a_higher_confidence_only_when_the_product_is_larger():
    strong = candidate(0, 'open the door and the door key', confidence=.5)
    weak = candidate(1, 'open the door', confidence=1.)
    padding = [candidate(i, f'unrelated thing {i}') for i in range(2, 8)]
    ranked = recall.rank([strong, weak, *padding], 'open the door')
    scores = {r['episode']['record_id']: r['score'] for r in ranked}
    assert (scores['r0'] > scores['r1']) == (ranked[0]['episode']['record_id'] == 'r0')


def test_no_subgoal_means_the_most_recent_records_and_no_scores():
    ranked = recall.rank([candidate(i, f'step {i}') for i in range(4)], None)
    assert [r['episode']['record_id'] for r in ranked] == ['r3', 'r2', 'r1', 'r0'] and all(r['score'] is None for r in ranked)
    assert recall.rank([], 'x') == [] and recall.rank([], None) == []


def test_the_query_is_the_subgoal_text_and_its_expected_observations():
    subgoal = dict(text='Open the door', data=dict(expected_observations=['The key turns', 'The hinge swings']))
    assert recall.query_text(subgoal) == 'Open the door The key turns The hinge swings'
    assert recall.query_text(None) is None


def ranked_pool(count, session='old'):
    return recall.rank([candidate(i, f'door step {i}', session=session, confidence=1 - i / 100) for i in range(count)],
                       'door')


def test_the_level_sees_the_top_ten_and_the_tail_two_plus_one_exploration_item():
    ranked = ranked_pool(14)
    level = recall.select(ranked, audience='level', session='now', pass_index=0)
    assert [i['episode']['record_id'] for i in level] == [r['episode']['record_id'] for r in ranked[:10]]
    assert not any(i['exploration'] for i in level)
    tail = recall.select(ranked, audience='tail', session='now', pass_index=0)
    assert [i['exploration'] for i in tail] == [False, False, True]
    assert [i['episode']['record_id'] for i in tail[:2]] == [r['episode']['record_id'] for r in ranked[:2]]
    # The exploration item is an earlier-session record outside the top ten.
    outside = {r['episode']['record_id'] for r in ranked[10:]}
    assert tail[2]['episode']['record_id'] in outside
    with pytest.raises(ValueError):
        recall.select(ranked, audience='actor', session='now', pass_index=0)


def test_exploration_is_seeded_by_session_and_pass_and_uniform_over_the_pool():
    ranked = ranked_pool(20)
    pool = [r['episode']['record_id'] for r in ranked[10:]]

    def drawn(session, index):
        return recall.select(ranked, audience='tail', session=session, pass_index=index)[2]['episode']['record_id']
    # Fixed per (session, pass): the same draw however often it is asked.
    assert {drawn('now', 3) for _ in range(5)} == {drawn('now', 3)}
    seed = int.from_bytes(hashlib.sha256(b'now:3').digest()[:8], 'big')
    assert recall.exploration_seed('now', 3) == seed
    ordered = sorted(ranked[10:], key=lambda item: item['age'])
    assert drawn('now', 3) == random.Random(seed).choice(ordered)['episode']['record_id']
    # Different passes and sessions draw differently, covering the whole pool roughly evenly.
    counts = {}
    for index in range(400):
        counts[drawn('now', index)] = counts.get(drawn('now', index), 0) + 1
    assert set(counts) == set(pool) and min(counts.values()) > 400 / 10 / 3
    assert any(drawn('other', i) != drawn('now', i) for i in range(20))


def test_there_is_no_exploration_item_without_an_earlier_session_record_outside_the_top_ten():
    # Everything fits in the top ten.
    assert [i['exploration'] for i in recall.select(ranked_pool(8), audience='tail', session='now', pass_index=0)] == [False, False]
    # Outside the top ten, but all from this session.
    here = recall.rank([candidate(i, f'door {i}', session='now') for i in range(14)], 'door')
    assert [i['exploration'] for i in recall.select(here, audience='tail', session='now', pass_index=0)] == [False, False]
    # A short list gives fewer than two top items.
    assert len(recall.select(ranked_pool(1), audience='tail', session='now', pass_index=0)) == 1
    assert recall.select([], audience='tail', session='now', pass_index=0) == []


def settle_earlier(app, memory_actor, index, attempted, *, session='z' * 32, confidence=.9, residual='', subgoal_id=None,
                   writer_settled='recorded'):
    """An earlier session's episode claim, written through the custodian settle path as a prior session would have."""
    reader = next(i for i, s in app.readers.items() if s['role'] == 'recorder')
    data = claim_data(session=session, actor_id='y' * 32, first_position=index + 1, last_position=index + 1,
                      subgoal_id=subgoal_id, settled='recorded', attempted=attempted, counterpart='',
                      observation_status=[], residual=residual, changed='', confidence=confidence)
    value = dict(schema='player-record/1', kind='claim', text=attempted, data=data, sources=[], supports=[],
                 supersedes=None, applicability=None, program_id=None)
    return app.memory.append_many(reader, [value], request_id=request_id(), custodian=True)[0]


def test_intent_v2_carries_the_subgoal_with_derived_status_stalled_flag_confidence_age_and_id(level):
    app, channel, actor, reader, recorder = level
    assert call(app, actor, 'player_intent', {})['schema'] == 'player-intent/2'
    empty = app.intent(actor['actor_id'])
    assert empty['subgoal'] is None and empty['age'] is None and empty['grants_authority'] is False
    assert empty['recall'] == dict(basis='recent', items=[]) and empty['audience'] == 'tail'
    work = commit_first(app, actor, reader, recorder, observations=['The door tile is adjacent', 'The key is held'])
    act(app, actor)
    episode(app, actor, recorder, ['seen', 'not_yet'], inputs=1)
    act(app, actor)
    intent = call(app, actor, 'player_intent', {})
    subgoal = intent['subgoal']
    assert subgoal['record_id'] == work['id'] and subgoal['text'] == 'Reach the visible door'
    assert subgoal['status'] == 'open' and subgoal['confidence'] == .4 and subgoal['stalled'] is False
    assert subgoal['expected_observations'] == [dict(text='The door tile is adjacent', status='seen'),
                                                dict(text='The key is held', status='not_yet')]
    assert subgoal['counts']['episodes'] == 1 and subgoal['contradicted'] is False
    assert intent['age']['inputs_since_commit'] == 3 and intent['age']['same_actor'] is True
    assert intent['age']['same_session'] is True and intent['age']['seconds'] >= 0
    assert 'record' not in intent


def test_intent_recall_lists_recorded_episodes_best_first_with_their_first_cited_frame(level):
    app, channel, actor, reader, recorder = level
    first = act(app, actor)
    sync(app, actor, recorder)
    bind(app, reader)
    work = call(app, reader, 'player_level_replace', replace(text='Open the wooden door',
                observations=['The wooden door is open']))['records'][0]
    cited = first['source']['source_id']
    episode(app, actor, recorder, ['not_yet'], sources=[cited], attempted='Pushed the wooden door but it was locked',
            residual='A bell rang')
    episode(app, actor, recorder, ['not_yet'], attempted='Walked around the room')
    intent = app.intent(actor['actor_id'])
    items = intent['recall']['items']
    assert intent['recall']['basis'] == 'ranked' and intent['pass_index'] == 1
    assert [i['attempted'] for i in items] == ['Pushed the wooden door but it was locked', 'Walked around the room']
    top = items[0]
    assert top['first_source'] == cited and top['sources'] == [cited] and top['residual'] == 'A bell rang'
    assert top['same_session'] is True and top['exploration'] is False and top['score'] > items[1]['score'] >= 0
    assert top['subgoal_id'] == work['id'] and set(top) >= {'record_id', 'first_position', 'last_position', 'changed',
                                                             'observation_status', 'confidence', 'counterpart'}
    # Abstained, failed and dropped settles are not recall.
    assert len(app.settled_episodes()) > len(items)


def test_with_no_subgoal_recall_is_the_most_recent_records_and_the_level_sees_ten(level):
    app, channel, actor, reader, recorder = level
    for index in range(12):
        settle_earlier(app, actor, index, f'attempt number {index}')
    intent = app.intent(actor['actor_id'], audience='level')
    assert intent['recall']['basis'] == 'recent' and intent['audience'] == 'level'
    assert [i['attempted'] for i in intent['recall']['items']] == [f'attempt number {i}' for i in range(11, 1, -1)]
    assert all(i['score'] is None and i['same_session'] is False for i in intent['recall']['items'])
    tail = app.intent(actor['actor_id'])['recall']['items']
    assert [i['exploration'] for i in tail] == [False, False, True]
    assert [i['attempted'] for i in tail[:2]] == ['attempt number 11', 'attempt number 10']
    assert tail[2]['attempted'] in {'attempt number 0', 'attempt number 1'}


def test_recall_ranks_earlier_session_records_against_the_current_subgoal(level):
    app, channel, actor, reader, recorder = level
    work = commit_first(app, actor, reader, recorder, text='Open the iron gate', observations=['The iron gate swings open'])
    settle_earlier(app, actor, 0, 'Picked a flower in a garden', confidence=1.)
    settle_earlier(app, actor, 1, 'Pulled the iron gate but it held', confidence=.6)
    settle_earlier(app, actor, 2, 'Pulled the iron gate', confidence=.6, residual='the hinge was rusted')
    intent = app.intent(actor['actor_id'], audience='level')
    items = intent['recall']['items']
    assert [i['attempted'] for i in items] == ['Pulled the iron gate', 'Pulled the iron gate but it held',
                                               'Picked a flower in a garden']
    assert items[0]['same_session'] is False and items[2]['score'] == 0
    assert work['id'] == intent['subgoal']['record_id']


def test_recall_trusts_only_stamped_claims_not_other_records_with_episode_like_text(level):
    app, channel, actor, reader, recorder = level
    commit_first(app, actor, reader, recorder, text='Open the iron gate', observations=['The iron gate swings open'])
    put(app.memory, actor['actor_id'], dict(schema='player-record/1', kind='claim', text='Pulled the iron gate',
        data=dict(attempted='Pulled the iron gate', confidence=1., level_contract='player-episode/1'), sources=[],
        supports=[], supersedes=None, applicability=None, program_id=None))
    assert app.intent(actor['actor_id'])['recall']['items'] == []
    settle_earlier(app, actor, 0, 'Pulled the iron gate')
    assert [i['attempted'] for i in app.intent(actor['actor_id'])['recall']['items']] == ['Pulled the iron gate']


def test_the_exploration_item_is_stable_within_a_pass_and_changes_with_the_pass_index(level):
    app, channel, actor, reader, recorder = level
    for index in range(30):
        settle_earlier(app, actor, index, f'door attempt {index}')
    commit_first(app, actor, reader, recorder, text='Open the door', observations=['The door opens'])
    first = app.intent(actor['actor_id'])
    again = app.intent(actor['actor_id'])
    assert first['recall'] == again['recall'] and first['pass_index'] == 1
    explored = {i['record_id'] for i in first['recall']['items'] if i['exploration']}
    seen = set(explored)
    for _ in range(25):
        bind(app, reader)
        seen |= {i['record_id'] for i in app.intent(actor['actor_id'])['recall']['items'] if i['exploration']}
    assert len(seen) > 5


def test_the_cached_ranking_matches_an_uncached_one_and_is_reused_until_an_episode_settles(level):
    from unittest.mock import patch
    app, channel, actor, reader, recorder = level
    commit_first(app, actor, reader, recorder, text='Open the iron gate', observations=['The iron gate swings open'])
    for index in range(15):
        settle_earlier(app, actor, index, f'Pulled the iron gate {index % 4} and the old door', confidence=.3 + index / 30,
                       residual='rust' if index % 3 == 0 else '')
    episode(app, actor, recorder, ['not_yet'], attempted='Kicked the iron gate')

    def uncached():
        candidates = [v for v in app._episodes() if v['settled'] == 'recorded']
        return recall.rank(candidates, recall.query_text(app.level_subgoals()[0]))
    cached = app._ranking(app.level_subgoals()[0])
    assert [(r['episode']['record_id'], r['score'], r['age']) for r in cached] == [
        (r['episode']['record_id'], r['score'], r['age']) for r in uncached()]
    assert len(cached) == 16 and len(app._prepared) == 16
    # Reused while nothing settles: no re-ranking and no re-tokenising.
    with patch.object(recall, 'rank', wraps=recall.rank) as ranked, patch.object(recall, 'prepare', wraps=recall.prepare) as prepared:
        first = app.intent(actor['actor_id'], audience='level')
        again = app.intent(actor['actor_id'], audience='level')
        assert first['recall'] == again['recall'] and first['subgoal'] == again['subgoal']
        assert ranked.call_count == 0 and prepared.call_count == 0
        # A new episode invalidates the ranking and tokenises only itself.
        episode(app, actor, recorder, ['not_yet'], attempted='Pushed the iron gate again')
        grown = app.intent(actor['actor_id'], audience='level')
        assert ranked.call_count == 1 and prepared.call_count == 1 and len(app._prepared) == 17
    assert [r['episode']['record_id'] for r in app._ranking(app.level_subgoals()[0])] == [
        r['episode']['record_id'] for r in uncached()]
    assert len(grown['recall']['items']) == 10
    # The no-subgoal ranking is cached on its own key.
    assert app._ranking(None)[0]['score'] is None


def test_prepared_documents_give_the_same_bm25_scores_as_token_lists():
    texts = ['door door key', 'key wall', 'floor floor floor floor', '']
    lists = [recall.tokens(t) for t in texts]
    prepared = [(Counter(t), len(t)) for t in lists]
    assert recall.bm25_prepared('door key', prepared) == recall.bm25('door key', lists)
    items = [candidate(i, t) for i, t in enumerate(texts)]
    assert recall.prepare(items[0]) == (Counter(lists[0]), 3)
    assert recall.rank(items, 'door key', [recall.prepare(i) for i in items]) == recall.rank(items, 'door key')


def test_the_intent_audience_is_validated(level):
    app, channel, actor, reader, recorder = level
    with pytest.raises(ValueError, match='audience'):
        app.intent(actor['actor_id'], audience='lead')


def test_intent_without_any_reader_reports_no_derived_status(tmp_path):
    runtime, channel, _ = make_runtime(tmp_path, mint=False)
    memory = Memory(tmp_path / 'player.sqlite3')
    app = Application(runtime, memory, tmp_path / 'contexts')
    try:
        actor = app.add_actor('narrowed')
        put(memory, actor['actor_id'], dict(schema='player-record/1', kind='work', text='A goal', data=dict(
            level='subgoal', level_contract='player-level/4', position=0, session=runtime.session,
            actor_id=actor['actor_id'], expected_observations=['x'], status='open', confidence=.5), sources=[],
            supports=[], supersedes=None, applicability=None, program_id=None))
        subgoal = app.intent(actor['actor_id'])['subgoal']
        assert subgoal['stalled'] is None and subgoal['contradicted'] is None
        assert subgoal['expected_observations'] == [dict(text='x', status=None)]
        assert mint(app, actor)
    finally:
        runtime.close(); memory.close()
