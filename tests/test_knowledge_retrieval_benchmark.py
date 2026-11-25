"""The #936 retrieval benchmark and curator recount on synthetic fixtures; neither test reads the sealed store."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from tools import curator_history_recount as recount
from tools import knowledge_retrieval_benchmark as bench

SEEN = {'session': 's', 'actor': '001', 'step': 1, 'order': [1, '001', 1]}


def delivered(articles: list[dict], facts: list[dict]) -> dict:
    return dict(schema='delivered-knowledge/2', version='v1', commit='a' * 40, repository_id='b' * 40,
                coverage=None, articles=articles, facts=facts)


def article(id: str, title: str, lead: str, body: list[tuple[str, list[str]]], links: list[str] = ()) -> dict:
    return dict(id=id, title=title, lead=lead, body=[dict(text=t, facts=f) for t, f in body], links=list(links),
                last_confirmed=SEEN)


def fact(id: str, subject: str, text: str, type: str = 'observation') -> dict:
    return dict(id=id, type=type, subject=subject, text=text, seen=SEEN)


@pytest.fixture
def corpus() -> bench.Corpus:
    return bench.Corpus('s', delivered(
        [article('water', 'Water boiling', 'Boil water before drinking.',
                 [('Boiling water makes it safe.', ['boil-time'])], ['Fire starting', 'Missing title']),
         article('fire', 'Fire starting', 'Light a fire first.', [('A matchbook lights a fire.', ['matchbook'])])],
        [fact('boil-time', 'Boiling', 'Boiling water takes 25 minutes on a stove.', 'recipe'),
         fact('matchbook', 'Matchbook', 'The matchbook lights a fire.', 'control'),
         fact('snow', 'Snow', 'Snow fell on the lake.')]))


def test_recomputed_scores_keep_the_production_order(corpus):
    for query in ('boiling water', 'matchbook fire', 'snow lake', 'nothing matches'):
        assert corpus.rank('prod_bm25', query) == corpus.ordered(corpus.bm25(query))[:bench.LIMIT]


def test_graph_joins_citations_and_title_links_and_counts_unresolved_ones(corpus):
    position = corpus.position
    assert corpus.neighbours[position['water']] == sorted([position['fire'], position['boil-time']])
    assert corpus.neighbours[position['fire']] == sorted([position['water'], position['matchbook']])
    assert corpus.unresolved_links == 1


def test_one_hop_reaches_a_seed_neighbour_but_never_an_unreached_record(corpus):
    assert corpus.ids(corpus.rank('bm25_1hop', 'boiling water')) == ['water', 'boil-time', 'fire']
    assert 'fire' not in corpus.ids(corpus.rank('prod_bm25', 'boiling water'))
    assert corpus.rank('bm25_1hop', 'nothing matches') == []


def test_an_isolated_record_takes_no_seed_slot(corpus, monkeypatch):
    monkeypatch.setattr(bench, 'SEEDS', 1)
    scores = corpus.bm25('snow lake water')
    snow, water = corpus.position['snow'], corpus.position['water']
    assert not corpus.neighbours[snow] and max(range(len(scores)), key=scores.__getitem__) == snow
    assert scores[corpus.position['fire']] == 0
    assert corpus.ids(corpus.rank('bm25_1hop', 'snow lake water'))[:2] == ['snow', 'water']
    assert 'fire' in corpus.ids(corpus.rank('bm25_1hop', 'snow lake water'))
    assert scores[water] > 0


def test_the_skip_drops_only_a_fact_that_a_kept_article_cites(corpus):
    water, boil = corpus.position['water'], corpus.position['boil-time']
    assert corpus.walk([water, boil], skip=True) == [water]
    assert corpus.walk([boil, water], skip=True) == [boil, water]
    assert corpus.ids(corpus.rank('bm25_1hop_skip', 'boiling water')) == ['water', 'fire']


def test_reads_count_zero_for_a_shown_fact_one_through_a_citing_article_and_none_otherwise(corpus):
    water, boil, snow = (corpus.position[i] for i in ('water', 'boil-time', 'snow'))
    assert bench.reads_to_answer(corpus, [boil], ('boil-time',), 5) == 0
    assert bench.reads_to_answer(corpus, [water], ('boil-time',), 5) == 1
    assert bench.reads_to_answer(corpus, [snow], ('boil-time',), 5) is None
    assert bench.reached(corpus, [water, snow]) == 3


def test_a_label_whose_detail_the_citing_prose_states_is_refused(corpus):
    stated = bench.DirectAnswer('s', 'T', 'test', 'boiling water', ('boil-time',), 'water', 'stated')
    with pytest.raises(ValueError, match='prose states'):
        bench.check_label(corpus, stated)
    absent = bench.DirectAnswer('s', 'T', 'test', 'how many minutes to boil water', ('boil-time',), '99 minutes',
                                'absent')
    with pytest.raises(ValueError, match='is not in'):
        bench.check_label(corpus, absent)
    unasked = bench.DirectAnswer('s', 'T', 'test', 'boiling water', ('boil-time',), '25 minutes', 'not asked')
    with pytest.raises(ValueError, match='does not ask'):
        bench.check_label(corpus, unasked)


def test_the_paired_comparison_drops_a_skip_that_hides_the_direct_answer(corpus):
    label = bench.DirectAnswer('s', 'T', 'test', 'minutes to boil water before drinking', ('boil-time',),
                               '25 minutes', 'omitted')
    result = bench.paired_skip({'s': corpus}, (label,))
    assert result['suppressed'] == 1
    assert result['no_skip']['fact_recall_at_5'] == 1.0 and result['skip']['fact_recall_at_5'] == 0.0
    assert (result['no_skip']['reads_at_5'], result['skip']['reads_at_5']) == (0, 1)
    assert result['decision'] == 'DROP coverage skip'
    with pytest.raises(ValueError, match='empty'):
        bench.paired_skip({'s': corpus}, ())


def test_suppressing_a_gold_fact_ranked_six_to_ten_adds_a_read(monkeypatch):
    fillers = [fact(f'filler-{n}', 'Filler', f'Filler record {n}.') for n in range(10)]
    wide = bench.Corpus('w', delivered(
        [article('guide', 'Guide', 'A guide.', [('The guide cites the boiling time.', ['gold'])])],
        [fact('gold', 'Boiling', 'Boiling water takes 25 minutes.'), *fillers]))
    position = wide.position
    order = [position[i] for i in ('guide', *(f'filler-{n}' for n in range(4)), 'gold',
                                   *(f'filler-{n}' for n in range(4, 10)))]
    monkeypatch.setattr(wide, 'rank', lambda method, query: wide.walk(order, skip=method == 'bm25_1hop_skip'))
    label = bench.DirectAnswer('w', 'T', 'test', 'how many minutes', ('gold',), '25 minutes', 'rank six')
    result = bench.paired_skip({'w': wide}, (label,))
    assert result['rows'][0]['no_skip']['fact_rank_at_10'] == 6 and result['suppressed'] == 1
    assert (result['no_skip']['reads_at_5'], result['skip']['reads_at_5']) == (1, 1)
    assert (result['no_skip']['reads_at_10'], result['skip']['reads_at_10']) == (0, 1)
    assert result['adds_reads'] == {'at_5': False, 'at_10': True}
    conditions = result['conditions']
    assert conditions['raises_reached_at_10'] and conditions['keeps_fact_recall_at_5']
    assert conditions['keeps_fact_mrr_at_5'] and conditions['adds_no_reads'] is False
    assert result['decision'] == 'DROP coverage skip'


def test_the_shipped_labels_are_explicit_questions_beside_the_frozen_924_queries():
    queries = {(q.corpus, q.label): q.text for q in bench.QUERIES}
    assert len(bench.QUERIES) == 30 and len(bench.LIVE) == 2
    assert bench.DIRECT_ANSWERS
    for label in bench.DIRECT_ANSWERS:
        corpus, _, number = label.topic.rpartition(' ')
        assert (label.corpus, number) in queries and corpus == f'#924 {label.corpus}'
        assert label.text not in queries.values()


# The recount, on a two-version synthetic history with one admission, one grooming and one aborted admission.

def git(cwd: Path, *arguments: str) -> str:
    return subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                           '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', *arguments],
                          cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def stored_fact(id: str, citations: list[str], level: str = 'game', **extra) -> dict:
    return dict(schema='curator-fact/4', record='fact', id=id, type='control', subject='S', text=f'{id} text',
                known='observed', scope=dict(game='cdda', level=level), citations=citations, **extra)


def stored_article(id: str, body: list[tuple[str, list[str]]], **extra) -> dict:
    return dict(schema='curator-fact/4', record='article', id=id, title=id, lead='Lead.',
                body=[dict(text=t, facts=f) for t, f in body], links=[], **extra)


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value))


def jsonl(rows: list[dict]) -> str:
    return ''.join(json.dumps(r) + '\n' for r in rows)


def session(state: Path, name: str, kind: str, base: str, window: str, sealed: bool, log: list[dict],
            submissions: dict[str, list[dict]]) -> None:
    write(state / 'sessions' / name / 'manifest.json', dict(
        inputs=dict(session_kind=kind, window=dict(session=window)),
        lifecycle=dict(state='sealed' if sealed else 'aborted', started_wall=len(name)),
        pinned=dict(knowledge_version=base, host=dict(max_requests=120))))
    write(state / 'sessions' / name / 'host-output.log', jsonl(log))
    for submission, changes in submissions.items():
        write(state / 'sessions' / name / 'submissions' / submission / 'submission.json',
              dict(schema='curator-submission/1', base_version=base, changes=changes))


@pytest.fixture
def history(tmp_path) -> Path:
    evidence = tmp_path / 'evidence'
    final = evidence / recount.FINAL / 'knowledge'
    repo, state = final / 'cdda', final / 'cdda.state'
    repo.mkdir(parents=True)
    git(repo, 'init', '-q', '-b', 'main')
    f1, f2 = stored_fact('f1', ['c1', 'c2']), stored_fact('f2', ['c3'], level='world')
    a1 = stored_article('a1', [('x', ['f1']), ('y', ['f2'])])
    f1b, a2 = stored_fact('f1b', ['c1']), stored_article('a2', [('x2', ['f1b'])])
    for version, records, types in (('v0', [], []), ('v1', [f1, f2, a1], [{'name': 'control'}]),
                                    ('v2', [dict(f1, superseded_by='f1b'), f2, dict(a1, superseded_by='a2'), f1b, a2],
                                     [{'name': 'control'}])):
        write(repo / 'facts.jsonl', jsonl(records))
        write(repo / 'ontology' / 'types.json', types)
        git(repo, 'add', '-A')
        git(repo, 'commit', '-q', '--allow-empty', '-m', version)
        git(repo, 'tag', version)
    write(state / 'gate.jsonl', jsonl([
        dict(operation='submission', session='s1', submission='one', status='published', version='v1',
             diagnostics=[], restored_from=None),
        dict(operation='submission', session='groom-seven-day-896-b-a01-x-1', submission='two', status='published',
             version='v2', diagnostics=[], restored_from=None)]))
    ok = lambda prompt, completion: dict(type='request-end', status=200, prompt_tokens=prompt,  # noqa: E731
                                          completion_tokens=completion)
    session(state, 's1', 'admission', 'v0', 'seven-day-896-b-a01-x', True,
            [ok(1000, 10), dict(type='host-end', reason='finished')],
            {'one': [dict(op='add_fact', fact=f1), dict(op='add_fact', fact=f2), dict(op='add_article', article=a1)]})
    session(state, 'groom-seven-day-896-b-a01-x-1', 'grooming', 'v1', 'seven-day-896-b-a01-x', True,
            [ok(2000, 20), *(dict(type='tool-call', name='read_file', bytes=n) for n in (5, 300, 200, 100)),
             dict(type='host-end', reason='finished')],
            {'two': [dict(op='supersede_fact', ids=['f1'], fact=f1b), dict(op='revise_article', id='a1', article=a2)]})
    session(state, 's2-lost', 'admission', 'v2', 'seven-day-896-b-a02-y', False,
            [dict(type='request-end', status=429, prompt_tokens=None, completion_tokens=None),
             dict(type='host-end', reason='provider-error')],
            {'lost': [dict(op='add_fact', fact=stored_fact('f9', ['c9']))]})
    for n, ends in ((1, [dict(event='end', session_id='s1', outcome='accepted')]),
                    (2, [dict(event='end', session_id='s2-lost', outcome='aborted', stop='spend-reservation-refused')])):
        write(evidence / f'{recount.LINEAGE}-admission-{n:02d}' / 'run' / 'curator-runner' / 'examined.jsonl', jsonl(ends))
    write(evidence / f'{recount.LINEAGE}-admission-02' / 'run' / 'curator-runner' / 'status.json', dict(
        state='stopped', stop_reason='spend-reservation-refused', backlog=7))
    write(evidence / f'{recount.LINEAGE}-admission-01' / 'grooming' / 'grooming-summary.json', dict(
        status='completed', reason=None, published_before='v1', published_after='v2', cost_usd='0.10',
        cap_usd='2.50', proxy=dict(max_reserved_usd='1.00', refusals=0, refusal_reasons=[])))
    return evidence


def snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def test_the_recount_reads_tags_gates_and_sessions_and_writes_nothing(history):
    before = snapshot(history)
    result = recount.recount(history)
    assert snapshot(history) == before
    assert result['versions'] == dict(tags=3, first='v0', last='v2', published=2)
    assert result['gate']['statuses'] == {'published': 2}
    assert result['operations'] == {'add_article': 1, 'add_fact': 2, 'revise_article': 1, 'supersede_fact': 1}
    assert result['facts']['current'] == 2 and result['facts']['scope'] == {'world': 1, 'game': 1}
    assert result['restatements'] == dict(count=1, replaced=1, merges=0, by_replaced={1: 1}, reused_all=0,
                                          omitted_some=1, omitted_citations=1)
    assert result['articles']['revisions'] == 1
    assert result['articles']['dropped_facts'] == {'cited_elsewhere': 0, 'orphaned': 1, 'superseded': 1}
    assert result['articles']['dropped_total'] == 2
    assert [(d['fact'], d['to'], d['superseded_later_in']) for d in result['articles']['unaccounted_drops']] == [
        ('f2', 'a2', None)]
    assert result['lost_submissions'] == 1
    assert [(x['id'], x['failed_status'], x['stop']) for x in result['aborted']] == [
        ('s2-lost', 429, 'spend-reservation-refused')]
    assert result['admission_tokens'] == dict(prompt=1000, completion=10, ratio=100.0)
    assert (result['per_admission'][2]['runner_backlog'], result['per_admission'][2]['runner_stop']) == (
        7, 'spend-reservation-refused')
    assert result['per_admission'][1]['runner_backlog'] is None
    base = len(jsonl([stored_fact('f1', ['c1', 'c2']), stored_fact('f2', ['c3'], level='world'),
                      stored_article('a1', [('x', ['f1']), ('y', ['f2'])])]).encode())
    assert [(g['admission'], g['status'], g['published'], g['read_file_bytes'], g['largest_three_read_bytes'],
             g['facts_jsonl_bytes'], g['largest_three_over_facts_jsonl']) for g in result['grooming']] == [
        (1, 'completed', 1, 605, 600, base, 600 - base)]
    text = recount.markdown(result)
    assert '| Published versions | `2` |' in text and '| `a02` | `1` | `1` | no | `stopped` / ' in text


def test_original_folding_misses_each_of_the_five_pairs():
    pairs = bench.folding_pairs()
    assert [tuple(row['words']) for row in pairs] == [
        ('zombie', 'zombies'), ('speed', 'speeds'), ('focus', 'focused'), ('spring', 'springs'), ('bleed', 'bleeding')]
    assert all(not row['original_conflates'] and row['porter2_conflates'] is None for row in pairs)


def test_optional_english_porter2_conflates_the_five_pairs():
    snowball = pytest.importorskip('snowballstemmer')
    english = snowball.stemmer('english')
    results = bench.folding_pairs(lambda word: english.stemWord(word.casefold()))
    assert all(row['porter2_conflates'] for row in results)


def test_porter2_arm_rebuilds_the_index_and_restores_the_original_fold(monkeypatch):
    value = delivered([article('guide', 'Zombie', 'A warning.', [])], [])
    query = bench.Query('v91', 'query-label', 'group', 'zombies', ('guide',))
    original = bench.retrieval(bench.Corpus('v91', value), [query], 1)
    monkeypatch.setattr(bench, 'QUERIES', (query,))
    monkeypatch.setattr(bench.Corpus, 'load', lambda name, path: bench.Corpus(name, value))
    saved = bench.production._fold
    gate = bench.compare_porter2(Path('.'), {'v91': original}, 1,
                                 lambda word: 'zombi' if word in ('zombie', 'zombies') else saved(word))
    assert original['rows'][0]['ranks']['bm25_1hop'] is None
    assert original['rows'][0]['ranks'][bench.PORTER2] == 1
    assert all(gate['v91'].values()) and bench.production._fold is saved


def test_compact_hits_use_exact_envelopes_canonical_bytes_and_sorted_distinct_citations():
    from harness.jsonio import canonical

    unicode_text = 'é' * 245
    articles = [article(rid, rid, 'A short lead.', [('An indirect citation.', ['match'])])
                for rid in ('z-article', 'a-article', 'm-article', 'b-article')]
    value = delivered(articles, [fact('match', 'Water', unicode_text, 'control')])
    corpus = bench.Corpus('v91', value)
    query = bench.Query('v91', 'query-label', 'group', 'water', ('a-article',))
    full, compact = bench.query_envelopes(corpus, query.text)
    assert full == dict(schema='player-knowledge/2', version='v1', grants_authority=False, identity='water',
                        resolution='query', resolved_from=None,
                        records=[value['facts'][0], *articles])
    assert compact['schema'] == 'player-knowledge/3' and 'records' not in compact
    assert compact['hits'][0] == dict(id='match', kind='fact', subject='Water', claim_kind='interface',
                                     scope={'game': 'cdda'}, snippet='é' * 240,
                                     cited_by_articles=['a-article', 'b-article', 'm-article'], via='match')
    assert compact['hits'][1] == dict(id='z-article', kind='article', revision='z-article@v1', title='z-article',
                                     snippet='A short lead.', tags=[], via='hop')
    measured = bench.compact_serialization(corpus, [query], 2)
    for name, envelope in (('full', full), ('compact', compact)):
        assert measured[name]['total_bytes'] == len(canonical(envelope).encode('utf-8'))
        assert measured[name]['total_bytes'] > len(canonical(envelope))
        assert measured[name]['samples'] == 2
