#!/usr/bin/env python3
"""Offline retrieval benchmark for Wave 3 (#936) and #1046/#1023 on sealed delivered knowledge. Read-only, `$0`.

  python tools/knowledge_retrieval_benchmark.py [--evidence DIR] [--repeat N] [--porter2] [--json | --markdown]

Outputs `knowledge-retrieval-benchmark/2`. In addition to replaying the 30 #924 queries (20 on `#896-b v91`,
10 on `#889 v17`) and the two live `#896-b` queries (`A01 v3`, `A03 v38`), it evaluates the four pinned `#998`
diagnostic probes (`PROBES_998`: `start-time`, `fire-ring`, `rv-door`, `crafting-filter`) on sealed `#998 v97`
and read-only tag-exported `#998 v101`.

- `prod_bm25`: production BM25 scores on the projected records, ordered without graph expansion.
- `bm25_1hop`: the same scores with production one-hop expansion through claim citations and title-resolved links.
- `bm25_1hop_skip`: the identical order walked with the rank-order coverage skip: a fact that an article already
  kept cites is skipped, and the walk stops at 10 records.

In the sealed delivered-knowledge/2 projection, the old ID stands in for the slug, links resolve by article title,
and the old type becomes a tag to keep its weight of two.

The paired coverage-skip comparison runs on the labelled direct-answer subset in DIRECT_ANSWERS: explicit questions,
separate from the 30 #924 queries. Each label names gold facts and a detail string; the script checks that the
question's terms include the detail's words, that the detail is in every gold fact's text and in no citing
article's prose (`lead` and `body[*].text`), and that the skip suppresses at least one gold fact, so a label whose
premise is false stops the run. Read counting is in `reads_to_answer`. The Gate 9 decision keeps the skip only if
it raises distinct records reached in the top 10, lowers neither direct-answer fact Recall@5 nor fact MRR@5, and
adds no `player_knowledge_read` call counted over either the top 5 or the top 10.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import json
import math
import re
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.jsonio import canonical  # noqa: E402
from harness.player import knowledge as production  # noqa: E402

LIMIT = production.QUERY_LIMIT
CUT = 5
METHODS = ('prod_bm25', 'bm25_1hop', 'bm25_1hop_skip')
PORTER2 = 'bm25_1hop_porter2'
FOLDING_PAIRS = (('zombie', 'zombies'), ('speed', 'speeds'), ('focus', 'focused'),
                 ('spring', 'springs'), ('bleed', 'bleeding'))
LEGACY_CLAIM_KINDS = {
    'instance_state': 'state', 'interface': 'observation', 'entity_property': 'observation',
    'mechanic': 'observation', 'strategy': 'inference',
}
CORPORA = {
    'v91': 'seven-day-896-b-admission-10/run/curator-runner/delivered/v91.json',
    'v17': 'live-validation-run-889/run/curator-runner/delivered/v17.json',
    'v3': 'seven-day-896-b-admission-01/run/curator-runner/delivered/v3.json',
    'v38': 'seven-day-896-b-admission-03/run/curator-runner/delivered/v38.json',
}
CORPUS_NAMES = {'v91': '#896-b v91', 'v17': '#889 v17', 'v3': '#896-b A01 v3', 'v38': '#896-b A03 v38'}


@dataclass(frozen=True)
class Query:
    corpus: str
    label: str
    group: str
    text: str
    gold: tuple[str, ...]


# The #924 record's queries and gold articles, verbatim
# (docs/acceptance/2026-11-23-knowledge-retrieval-ablation-924.md).
QUERIES = (
    Query('v91', 'Q01', 'real_896b', 'food cooking roasting stick makeshift cooking tool campfire',
          ('article-basic-tools-groom40', 'article-brazier-fires-groom27', 'article-cattail-stalk-cooking-groom27',
           'article-fire-reliability-groom39')),
    Query('v91', 'Q02', 'real_896b', 'straw withered plants harvest tall grass grass straw',
          ('article-bed-construction-grass-a02', 'article-grass-yarn-sheets-groom39', 'article-storage-clothing-groom39')),
    Query('v91', 'Q03', 'direct', 'boil murky water filtration wood stove clean water',
          ('article-murky-filtration-a06', 'article-water-fire-toilet-a03', 'article-wood-stove-water-groom59')),
    Query('v91', 'Q04', 'direct', 'how to start fire bow drill tinder brazier',
          ('article-bow-fire-drill-groom27', 'article-brazier-fires-groom27')),
    Query('v91', 'Q05', 'direct', 'sleep in tent bed wait fatigue warmth',
          ('article-bed-construction-grass-a02', 'article-bed-wait-groom59', 'article-tent-sleep-corrected-a06')),
    Query('v91', 'Q06', 'direct', 'wooden spear pointy stick weapon melee reach', ('article-wooden-spear-pointy-a03',)),
    Query('v91', 'Q07', 'direct', 'foraging cattail stalks rhizome jelly seeds',
          ('article-cattail-foraging-raw-stalk-a07', 'article-cattail-jelly-seeds-groom48',
           'article-cattail-stalk-cooking-groom27')),
    Query('v91', 'Q08', 'direct', 'reading nearby books skill training light', ('article-books-reading-a06',)),
    Query('v91', 'Q09', 'direct', 'craft backpack improvised storage grass clothing',
          ('article-backpack-recipes-groom59', 'article-storage-clothing-groom39')),
    Query('v91', 'Q10', 'direct', 'butcher painted turtle meat snails gastropods',
          ('article-painted-turtle-butchery-a07', 'article-snails-gastropods-a07')),
    Query('v91', 'Q11', 'direct', 'ferns fiddleheads burdock cooked acorns wild vegetables',
          ('article-burdock-fire-out-a06', 'article-cooked-acorns-a07', 'article-fern-fiddleheads-groom59',
           'article-underbrush-wild-vegetables-a06-late')),
    Query('v91', 'Q12', 'direct', 'pickup nested liquid containers household water',
          ('article-household-pickup-groom48', 'article-household-water-groom59', 'article-pickup-storage-groom48')),
    Query('v91', 'Q13', 'multihop', 'safe indoor heat source to purify drinking supply without smoke',
          ('article-brazier-fires-groom27', 'article-craftable-braziers-a04', 'article-water-fire-toilet-a03',
           'article-wood-stove-water-groom59')),
    Query('v91', 'Q14', 'multihop', 'sewing needle cordage fiber to repair or craft gear',
          ('article-grass-yarn-sheets-groom39', 'article-needle-plant-string-groom17', 'article-storage-clothing-groom39')),
    Query('v91', 'Q15', 'multihop', 'batch crafting search filter resume interrupted recipe',
          ('article-crafting-selection-groom50', 'article-crafting-workflow-groom40', 'article-fire-reliability-groom39')),
    Query('v91', 'Q16', 'multihop', 'scouting overmap distance binoculars vehicle electronic doors',
          ('article-binoculars-flaregun-groom17', 'article-electronic-door-groom59', 'article-inspection-travel-groom40',
           'article-vehicle-inspection-groom17')),
    Query('v91', 'Q17', 'multihop', 'hydration vitamin morale warm tea juice',
          ('article-bee-balm-tea-consumed-a09', 'article-field-nutrition-groom59', 'article-fruit-juice-groom48')),
    Query('v91', 'Q18', 'multihop', 'window curtains line of sight monsters inside house',
          ('article-curtains-threats-groom48',)),
    Query('v91', 'Q19', 'multihop', 'river crossing deep water swimming hazard movement',
          ('article-salvage-movement-groom39', 'article-water-traversal')),
    Query('v91', 'Q20', 'multihop', 'eating raw forage versus cooked meal hunger calories',
          ('article-cattail-foraging-raw-stalk-a07', 'article-cattail-stalk-cooking-groom27',
           'article-food-consumption-raw-stalk-a07')),
    Query('v17', 'Q01', 'direct', 'wooden spear crafting pointy stick', ('article-wooden-spear-v3',)),
    Query('v17', 'Q02', 'direct', 'water treatment boiling clean water recipes', ('article-water-treatment-recipes-v5',)),
    Query('v17', 'Q03', 'direct', 'cotton patch bleeding emergency bandage treatment', ('article-emergency-patches',)),
    Query('v17', 'Q04', 'direct', 'brazier fire wait fuel cooking', ('article-brazier-fire-and-wait',)),
    Query('v17', 'Q05', 'direct', 'digging stick clay extraction', ('article-digging-stick', 'article-extracting-clay')),
    Query('v17', 'Q06', 'direct', 'hickory nuts foraging calories', ('article-hickory-nuts',)),
    Query('v17', 'Q07', 'direct', 'sleeping fatigue rest shelter', ('article-sleeping',)),
    Query('v17', 'Q08', 'direct', 'nearby items threats enemies V list',
          ('article-exploration-controls-v2', 'article-nearby-threats')),
    Query('v17', 'Q09', 'direct', 'wilderness scenario character creation survivor profession',
          ('article-creation-v2', 'article-survivor', 'article-wilderness-v2')),
    Query('v17', 'Q10', 'direct', 'ground stick salvage firewood', ('article-stick-salvage',)),
)
LIVE = (
    Query('v3', 'A01 v3', 'live', 'food cooking roasting stick makeshift cooking tool campfire', ()),
    Query('v38', 'A03 v38', 'live', 'straw withered plants harvest tall grass grass straw', ()),
)


@dataclass(frozen=True)
class DirectAnswer:
    corpus: str
    label: str
    topic: str
    text: str
    facts: tuple[str, ...]
    detail: str
    why: str


# Labelled by reading the sealed files: the detail is in each gold fact's text and in no citing article's prose.
# Each query is a question that asks for the detail, so every word of the detail but its number is a query term;
# `topic` names the #924 query whose gold article cites the fact, and `why` says what that article says instead.
# The 30 #924 queries stay unchanged for the overall ranking.
DIRECT_ANSWERS = (
    DirectAnswer('v91', 'long-pointy-stick-pierce', '#924 v91 Q06', 'what pierce damage does a long pointy stick do',
                 ('long-pointy-stick-recipe-reach-a03',), 'pierce 9',
                 'The long pointy stick fact lists pierce 9; the citing article gives only the spear\'s pierce 18.'),
    DirectAnswer('v91', 'cooked-wild-vegetables-kcal', '#924 v91 Q11', 'how many kcal do cooked wild vegetables give',
                 ('cooked-wild-vegetables-inspected-a06',), '34 kcal',
                 'The fact gives the cooked result\'s 34 kcal; the article gives only its 35% vitamin C.'),
    DirectAnswer('v17', 'cotton-patch-improvement', '#924 v17 Q03',
                 'what percent improvement does a cotton patch give on a bleeding wound',
                 ('cotton-patch-bleeding-treatment',), '50% improvement',
                 'The fact gives the menu\'s 50% improvement for a minor bleed; the article says only that one '
                 'patch reduced it.'),
    DirectAnswer('v17', 'desert-island-variants', '#924 v17 Q09',
                 'how many Desert Island variants does the Wilderness start location menu list',
                 ('wilderness-location-choices',), '5 variants',
                 'The fact gives Desert Island 5 variants and 13 random variants; the article gives only '
                 'Campground\'s four.'),
)


def _project_v3_to_v4(snapshot: dict) -> dict:
    """Project a sealed retrieval benchmark input to the current reader contract."""
    if snapshot['schema'] != 'delivered-knowledge/3':
        raise ValueError('expected sealed delivered-knowledge/3 benchmark input')
    value = copy.deepcopy(snapshot)
    value.update(schema=production.SCHEMA, frame_clocks={})
    for record in value['articles'] + value['facts']:
        record.pop('condition_unverified', None)
    for fact in value['facts']:
        fact['statement_kind'] = LEGACY_CLAIM_KINDS[fact.pop('claim_kind')]
        if fact['statement_kind'] == 'state':
            fact['state_key'] = f"legacy-key-{fact['id']}"
        fact.pop('evidence_basis', None)
        when = fact.pop('when', None)
        if when and when['note'].strip():
            fact['when'] = when['note']
    return value


class Corpus:
    """Historical delivered-knowledge/2 corpus with a benchmark-only production reader projection."""

    def __init__(self, name: str, value: dict, where: str = 'delivered knowledge'):
        if (not isinstance(value, dict) or value.get('schema') != 'delivered-knowledge/2'
                or not isinstance(value.get('articles'), list) or not isinstance(value.get('facts'), list)):
            raise ValueError(f'{where}: expected sealed delivered-knowledge/2 benchmark input')
        self.name = name
        self.version = value['version']
        self.article_count = len(value['articles'])
        self.fact_count = len(value['facts'])
        self.records = value['articles'] + value['facts']
        self.position = {r['id']: i for i, r in enumerate(self.records)}
        self.article = [('body' in r) for r in self.records]
        self.links = self.unresolved_links = 0
        self.knowledge = production.Knowledge.from_dict(self._project(value), where)
        self.neighbours = self.knowledge._neighbours
        self.cites = [frozenset(self.position[f] for claim in r.get('body', ()) for f in claim['facts'])
                      for r in self.records]
        self.citing = [[self.position[slug] for slug in r.get('cited_by_articles', ())]
                       for r in self.knowledge.records]

    def _project(self, value: dict) -> dict:
        """Resolve title links and keep legacy type terms at their original weight via tags."""
        aliases: dict[str, str] = {}

        def alias(position: dict) -> dict:
            return dict(position, session=aliases.setdefault(position['session'], f's{len(aliases) + 1:02}'))

        def common(record: dict, *, bound: bool = False) -> dict:
            scope = {'game': 'cdda', 'world': None} if bound else {'game': 'cdda'}
            return dict(id=record['id'], tags=[], scope=scope, branch_relation='same' if bound else None,
                        lifecycle_state='active', needs_review=False, unverified_branch=False,
                        stale_citations=[], links=[], backlinks=[], shadowed_by=[], contradicted_by=[])

        titles = {a['title']: a['id'] for a in value['articles']}
        articles, facts = [], []
        for old in value['articles']:
            article = dict(common(old), revision=f"{old['id']}@{self.version}", title=old['title'], lead=old['lead'],
                           body=old['body'], last_confirmed=alias(old['last_confirmed']))
            targets = []
            for title in old.get('links', ()):
                self.links += 1
                target = titles.get(title)
                if target is None:
                    self.unresolved_links += 1
                elif target != old['id']:
                    targets.append(target)
            article['links'] = [dict(rel='see_also', target=target) for target in dict.fromkeys(targets)]
            articles.append(article)
        for n, old in enumerate(value['facts'], 1):
            bound = old['type'] == 'world_observation'
            fact = dict(common(old, bound=bound), statement_kind='state' if bound else 'observation',
                        tags=[old['type'].replace('_', '-')], text=old['text'], seen=alias(old['seen']),
                        cited_by_articles=[], citation_source_ids=[f'{n:032x}-1'])
            if 'subject' in old:
                fact['subject'] = old['subject']
            if bound:
                fact['state_key'] = f"legacy-v2-key-{n}"
            facts.append(fact)
        by_id = {record['id']: record for record in articles + facts}
        for article in articles:
            for link in article['links']:
                by_id[link['target']]['backlinks'].append(dict(rel=link['rel'], source=article['id']))
            for identity in dict.fromkeys(f for claim in article['body'] for f in claim['facts']):
                by_id[identity]['cited_by_articles'].append(article['id'])
        return dict(production.empty(), version=self.version, commit=value['commit'],
                    repository_id=value['repository_id'], coverage=alias(value['coverage']) if value['coverage'] else None,
                    articles=articles, facts=facts)

    @classmethod
    def load(cls, name: str, path: Path) -> 'Corpus':
        return cls(name, json.loads(path.read_text()), str(path))

    def bm25(self, query: str) -> list[float]:
        return self.knowledge._bm25(query)

    def ordered(self, scores: list[float]) -> list[int]:
        return [i for _, i in sorted((-s, i) for i, s in enumerate(scores) if s > 0)]

    def walk(self, order: list[int], skip: bool) -> list[int]:
        if not skip:
            return order[:LIMIT]
        kept: list[int] = []
        covered: set[int] = set()
        for i in order:
            if len(kept) == LIMIT:
                break
            if not self.article[i] and i in covered:
                continue
            kept.append(i)
            covered |= self.cites[i]
        return kept

    def rank(self, method: str, query: str) -> list[int]:
        if method == 'prod_bm25':
            return self.ordered(self.bm25(query))[:LIMIT]
        order = self.ordered(self.knowledge._one_hop(query))
        return self.walk(order, skip=method == 'bm25_1hop_skip')

    def query(self, method: str, query: str) -> list[dict]:
        """The full result a player would receive, deep-copied as the production reader does; used for timing."""
        return [copy.deepcopy(self.records[i]) for i in self.rank(method, query)]

    def ids(self, positions: list[int]) -> list[str]:
        return [self.records[i]['id'] for i in positions]

    def prose(self, article: int) -> str:
        record = self.records[article]
        return ' '.join([record['lead'], *(claim['text'] for claim in record['body'])])


# Metrics. Ranks are 1-based positions in the mixed list of articles and facts.

def hit(corpus: Corpus, top: list[int], gold: tuple[str, ...]) -> float:
    """1 when a gold article or a fact a gold article cites is in the top CUT, as the #924 record scored it."""
    wanted = {corpus.position[g] for g in gold}
    wanted |= {f for g in wanted for f in corpus.cites[g]}
    return float(any(i in wanted for i in top[:CUT]))


def recall(corpus: Corpus, top: list[int], gold: tuple[str, ...]) -> float:
    wanted = {corpus.position[g] for g in gold}
    return len(wanted & set(top[:CUT])) / len(wanted)


def reciprocal_rank(corpus: Corpus, top: list[int], gold: tuple[str, ...]) -> float:
    wanted = {corpus.position[g] for g in gold}
    return next((1 / (rank + 1) for rank, i in enumerate(top[:CUT]) if i in wanted), 0.0)


def first_rank(corpus: Corpus, top: list[int], gold: tuple[str, ...]) -> int | None:
    wanted = {corpus.position[g] for g in gold}
    return next((rank + 1 for rank, i in enumerate(top[:CUT]) if i in wanted), None)


def reached(corpus: Corpus, top: list[int]) -> int:
    """Distinct records a result reaches: each returned record and every fact a returned article cites."""
    found = set(top[:LIMIT])
    for i in top[:LIMIT]:
        found |= corpus.cites[i]
    return len(found)


def reads_to_answer(corpus: Corpus, top: list[int], facts: tuple[str, ...], cut: int) -> int | None:
    """`player_knowledge_read` calls after the query to hold a gold fact's record, looking at the first `cut` results.

    0 when a gold fact is itself among them; 1 when it is not but an article among them cites it (the player reads
    the fact ID in that article's `body[*].facts` and calls `player_knowledge_read` once); None (unreached) when
    neither holds, because the query alone gives no ID to read. Unreached ranks worse than any count.
    """
    wanted = {corpus.position[f] for f in facts}
    shown = top[:cut]
    if wanted & set(shown):
        return 0
    if any(corpus.cites[i] & wanted for i in shown):
        return 1
    return None


def percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def timing(corpus: Corpus, method: str, queries: list[str], repeat: int) -> dict:
    samples = []
    for _ in range(repeat):
        for text in queries:
            start = time.perf_counter()
            corpus.query(method, text)
            samples.append((time.perf_counter() - start) * 1000)
    return dict(avg_ms=round(statistics.fmean(samples), 3), p95_ms=round(percentile(samples, 0.95), 3),
                samples=len(samples))


def folding_pairs(porter2=None) -> list[dict]:
    rows = []
    for pair in FOLDING_PAIRS:
        old = [production._fold(word) for word in pair]
        new = [porter2(word) for word in pair] if porter2 is not None else None
        rows.append(dict(words=list(pair), original=old, original_conflates=old[0] == old[1],
                         porter2=new, porter2_conflates=None if new is None else new[0] == new[1]))
    return rows


def query_envelopes(corpus: Corpus, query: str) -> tuple[dict, dict]:
    scores = corpus.bm25(query)
    order = corpus.ordered(corpus.knowledge._one_hop(query, scores))[:LIMIT]
    # Use identical ranking for both envelopes so the measurement isolates serialization.
    full = dict(schema='player-knowledge/2', version=corpus.version, grants_authority=False,
                identity=query, resolution='query', resolved_from=None,
                records=[copy.deepcopy(corpus.records[i]) for i in order])
    compact = corpus.knowledge._query_result(
        query, [production._hit(corpus.knowledge.records[i], 'match' if scores[i] > 0 else 'hop') for i in order])
    return full, compact


def compact_serialization(corpus: Corpus, queries: list[Query], repeat: int) -> dict:
    rows = [dict(label=q.label) for q in queries]
    variants = list(zip(*(query_envelopes(corpus, q.text) for q in queries)))
    measurements = {}
    for name, envelopes in zip(('full', 'compact'), variants):
        sizes = [len(canonical(envelope).encode('utf-8')) for envelope in envelopes]
        for row, size in zip(rows, sizes):
            row[f'{name}_bytes'] = size
        samples = []
        for _ in range(repeat):
            for envelope in envelopes:
                start = time.perf_counter()
                canonical(envelope).encode('utf-8')
                samples.append((time.perf_counter() - start) * 1000)
        measurements[name] = dict(total_bytes=sum(sizes), median_bytes=statistics.median(sizes),
                                  max_bytes=max(sizes), avg_ms=round(statistics.fmean(samples), 4),
                                  p95_ms=round(percentile(samples, 0.95), 4), samples=len(samples))
    return dict(corpus=corpus.name, queries=len(queries), rows=rows, **measurements)


# Evaluation.

def check_label(corpus: Corpus, label: DirectAnswer) -> None:
    """Stop when a label's premise is false: the query asks for the detail, which is in each gold fact and in no
    citing article's prose."""
    detail = label.detail.casefold()
    asked = {t for t in production.terms_of(label.detail) if not re.fullmatch(r'\d+(?:\.\d+)?', t)}
    if not asked or not asked <= set(production.terms_of(label.text)):
        raise ValueError(f'{label.label}: the query does not ask for {label.detail!r}')
    for fact in label.facts:
        i = corpus.position.get(fact)
        if i is None or corpus.article[i]:
            raise ValueError(f'{label.label}: {fact} is not a delivered fact')
        if detail not in corpus.records[i]['text'].casefold():
            raise ValueError(f'{label.label}: {label.detail!r} is not in {fact}')
        if not corpus.citing[i]:
            raise ValueError(f'{label.label}: no article cites {fact}')
        for article in corpus.citing[i]:
            if detail in corpus.prose(article).casefold():
                raise ValueError(f'{label.label}: {corpus.records[article]["id"]} prose states {label.detail!r}')


def retrieval(corpus: Corpus, queries: list[Query], repeat: int, methods: tuple[str, ...] = METHODS) -> dict:
    rows, summary = [], {}
    for method in methods:
        tops = [corpus.rank(method, q.text) for q in queries]
        summary[method] = dict(
            hit_at_5=round(statistics.fmean(hit(corpus, t, q.gold) for t, q in zip(tops, queries)), 3),
            article_recall_at_5=round(statistics.fmean(recall(corpus, t, q.gold) for t, q in zip(tops, queries)), 3),
            article_mrr_at_5=round(statistics.fmean(reciprocal_rank(corpus, t, q.gold) for t, q in zip(tops, queries)), 3),
            reached_at_10=round(statistics.fmean(reached(corpus, t) for t in tops), 2),
            **timing(corpus, method, [q.text for q in queries], repeat))
    for q in queries:
        rows.append(dict(label=q.label, group=q.group, query=q.text, gold=list(q.gold),
                         ranks={m: first_rank(corpus, corpus.rank(m, q.text), q.gold) for m in methods},
                         top5={m: corpus.ids(corpus.rank(m, q.text)[:CUT]) for m in methods}))
    return dict(corpus=corpus.name, articles=corpus.article_count,
                facts=corpus.fact_count, edges=sum(map(len, corpus.neighbours)) // 2,
                queries=len(queries), methods=summary, rows=rows)


def direct_answer_arm(corpus: Corpus, label: DirectAnswer, method: str) -> dict:
    top = corpus.rank(method, label.text)
    wanted = {corpus.position[f] for f in label.facts}
    rank = next((r + 1 for r, i in enumerate(top) if i in wanted), None)
    return dict(reached_at_10=reached(corpus, top),
                fact_recall_at_5=len(wanted & set(top[:CUT])) / len(wanted),
                fact_mrr_at_5=1 / rank if rank is not None and rank <= CUT else 0.0,
                fact_rank_at_10=rank, reads_at_5=reads_to_answer(corpus, top, label.facts, CUT),
                reads_at_10=reads_to_answer(corpus, top, label.facts, LIMIT))


def paired_skip(corpora: dict[str, Corpus], labels: tuple[DirectAnswer, ...] = DIRECT_ANSWERS) -> dict:
    if not labels:
        raise ValueError('the direct-answer subset is empty')
    rows = []
    for label in labels:
        corpus = corpora[label.corpus]
        check_label(corpus, label)
        off, on = (direct_answer_arm(corpus, label, m) for m in ('bm25_1hop', 'bm25_1hop_skip'))
        suppressed = off['fact_rank_at_10'] is not None and on['fact_rank_at_10'] is None
        rows.append(dict(corpus=label.corpus, label=label.label, topic=label.topic, query=label.text,
                         facts=list(label.facts), detail=label.detail, why=label.why, suppressed=suppressed,
                         no_skip=off, skip=on))
    if not any(r['suppressed'] for r in rows):
        raise ValueError('no direct-answer query has a gold fact that the skip suppresses')

    def arm(name: str) -> dict:
        values = [r[name] for r in rows]
        unreached = {cut: sum(v[f'reads_at_{cut}'] is None for v in values) for cut in (CUT, LIMIT)}
        return dict(reached_at_10=round(statistics.fmean(v['reached_at_10'] for v in values), 2),
                    fact_recall_at_5=round(statistics.fmean(v['fact_recall_at_5'] for v in values), 3),
                    fact_mrr_at_5=round(statistics.fmean(v['fact_mrr_at_5'] for v in values), 3),
                    reads_at_5=sum(v['reads_at_5'] or 0 for v in values), unreached_at_5=unreached[CUT],
                    reads_at_10=sum(v['reads_at_10'] or 0 for v in values), unreached_at_10=unreached[LIMIT])

    off, on = arm('no_skip'), arm('skip')

    def more_reads(cut: int) -> bool:
        worse = lambda a, b: (b is None and a is not None) or (a is not None and b is not None and b > a)  # noqa: E731
        return any(worse(r['no_skip'][f'reads_at_{cut}'], r['skip'][f'reads_at_{cut}']) for r in rows)

    conditions = dict(raises_reached_at_10=on['reached_at_10'] > off['reached_at_10'],
                      keeps_fact_recall_at_5=on['fact_recall_at_5'] >= off['fact_recall_at_5'],
                      keeps_fact_mrr_at_5=on['fact_mrr_at_5'] >= off['fact_mrr_at_5'],
                      adds_no_reads=not more_reads(CUT) and not more_reads(LIMIT))
    return dict(queries=len(rows), suppressed=sum(r['suppressed'] for r in rows), rows=rows,
                no_skip=off, skip=on, conditions=conditions,
                adds_reads={f'at_{CUT}': more_reads(CUT), f'at_{LIMIT}': more_reads(LIMIT)},
                decision='KEEP coverage skip' if all(conditions.values()) else 'DROP coverage skip')


def omission_scan(corpus: Corpus, queries: list[Query]) -> dict:
    """How the labels were found: top-10 `bm25_1hop` facts whose text holds a number no citing article states."""
    words = dict(one='1', two='2', three='3', four='4', five='5', six='6', seven='7', eight='8', nine='9', ten='10')

    def numbers(text: str) -> set[str]:
        text = text.casefold()
        for word, digit in words.items():
            text = re.sub(rf'\b{word}\b', digit, text)
        return set(re.findall(r'\d+(?:\.\d+)?%?', text))

    appearances = skipped = 0
    distinct: set[int] = set()
    distinct_skipped: set[int] = set()
    for q in queries:
        top = corpus.rank('bm25_1hop', q.text)
        kept = set(corpus.rank('bm25_1hop_skip', q.text))
        for i in top:
            if corpus.article[i] or not corpus.citing[i]:
                continue
            missing = numbers(corpus.records[i]['text'])
            for article in corpus.citing[i]:
                missing -= numbers(corpus.prose(article))
            if missing:
                appearances += 1
                distinct.add(i)
                if i not in kept:
                    skipped += 1
                    distinct_skipped.add(i)
    return dict(corpus=corpus.name, appearances=appearances, appearances_skipped=skipped,
                distinct_facts=len(distinct), distinct_facts_skipped=len(distinct_skipped))


def overall_gate(results: dict) -> dict:
    gate = {}
    for name in ('v91', 'v17'):
        methods = results[name]['methods']
        base = methods['prod_bm25']
        for method in ('bm25_1hop', 'bm25_1hop_skip'):
            m = methods[method]
            gate[f'{name}:{method}'] = dict(hit_at_5=m['hit_at_5'] >= base['hit_at_5'],
                                            article_mrr_at_5=m['article_mrr_at_5'] >= base['article_mrr_at_5'],
                                            p95_under_5_ms=m['p95_ms'] < 5.0)
    return gate


def compare_porter2(evidence: Path, results: dict, repeat: int, fold) -> dict:
    gates = {}
    with patch.object(production, '_fold', fold):
        for name, original in results.items():
            corpus = Corpus.load(name, evidence / CORPORA[name])
            arm = retrieval(corpus, [q for q in QUERIES if q.corpus == name], repeat, (PORTER2,))
            original['methods'].update(arm['methods'])
            for row, alternative in zip(original['rows'], arm['rows']):
                row['ranks'].update(alternative['ranks'])
                row['top5'].update(alternative['top5'])
            before = [r['ranks']['bm25_1hop'] for r in original['rows']]
            after = [r['ranks'][PORTER2] for r in original['rows']]
            gates[name] = dict(hit_at_5=arm['methods'][PORTER2]['hit_at_5'] >= original['methods']['bm25_1hop']['hit_at_5'],
                               article_mrr_at_5=math.fsum(1 / r for r in after if r)
                               >= math.fsum(1 / r for r in before if r))
    return gates


@dataclass(frozen=True)
class Probe998:
    label: str
    group: str
    text: str
    as_of_status: str
    gold_articles: tuple[str, ...]
    gold_facts: tuple[str, ...]
    latest_facts: tuple[str, ...]
    snippet_all: tuple[str, ...]
    snippet_any: tuple[str, ...]
    note: str


PROBES_998 = (
    Probe998(
        label='start-time', group='live_998_a04',
        text='Rowan starting time spring day 61 72 hours character creation clock',
        as_of_status='current', gold_articles=('wilderness-start',),
        gold_facts=('wilderness-default-calendar', 'rowan-starting-water-frozen'),
        latest_facts=('wilderness-default-calendar',), snippet_all=('8:00 am',), snippet_any=(),
        note='Verbatim live #998 A04 request-107; wilderness-default-calendar ranked 18th in v97 while wilderness-start lead omits 8:00 AM.',
    ),
    Probe998(
        label='fire-ring', group='live_998_a03', text='fire ring fire fuel haul stick wood camp Rowan',
        as_of_status='mixed-stale', gold_articles=('rowan-campground-spawn',),
        gold_facts=('rowan-day-63-ring-fiddlehead-meal', 'rowan-day-63-bough-fire-craft-interruption',
                    'rowan-day-62-existing-fire-ring', 'rowan-day-62-ring-fire-road',
                    'rowan-day-62-fire-fuel-water-warning', 'rowan-day-62-outdoor-water-and-stick-menu',
                    'rowan-day-62-hauled-stick-ring-filter', 'rowan-day-62-acorn-fire-rejected',
                    'matchbook-stick-fire-ring-cooking', 'pine-bough-fire-ring-interrupted-cooking'),
        latest_facts=('rowan-day-63-ring-fiddlehead-meal', 'rowan-day-63-bough-fire-craft-interruption'),
        snippet_all=('fire ring',), snippet_any=(),
        note='Verbatim live #998 A03 request-257; Day-62 fire-ring readings are stale at Day 64, Day-63 readings are latest, and rowan-campground-spawn lead mentions only the Day-64 brazier.',
    ),
    Probe998(
        label='rv-door', group='diagnostic_998', text='Luxury RV door enter west side driver door',
        as_of_status='partial-stale', gold_articles=('rowan-campground-spawn',),
        gold_facts=('rowan-rv-access-and-condition', 'rowan-returned-rv-rear-bed'),
        latest_facts=('rowan-rv-access-and-condition', 'rowan-returned-rv-rear-bed'),
        snippet_all=('west-side', 'door'), snippet_any=(),
        note='Battery/inventory readings in both facts became stale by Day 64 while the west-side driver door still held; rowan-campground-spawn lead omits RV door.',
    ),
    Probe998(
        label='crafting-filter', group='diagnostic_998', text='crafting screen recipe filter reset clear query',
        as_of_status='current', gold_articles=('crafting-controls',),
        gold_facts=('crafting-filter-controls', 'crafting-replace-filter-and-prefixes',
                    'crafting-filter-control-u', 'crafting-filter-control-backspace-appends'),
        latest_facts=('crafting-filter-controls', 'crafting-replace-filter-and-prefixes',
                      'crafting-filter-control-u', 'crafting-filter-control-backspace-appends'),
        snippet_all=(), snippet_any=('ctrl-u', 'backspace', 'r to reset', 'r resets'),
        note='Game-wide crafting filter controls; crafting-controls lead omits all reset/clear keys (Ctrl-U, Backspace, r).',
    ),
)


def snippet_matches(snippet: str, probe: Probe998) -> bool:
    folded = snippet.casefold()
    return (all(term.casefold() in folded for term in probe.snippet_all)
            and (not probe.snippet_any or any(term.casefold() in folded for term in probe.snippet_any)))


def evaluate_probes_998(knowledge: production.Knowledge, probes: tuple[Probe998, ...],
                        repeat: int, *, label: str) -> dict:
    repeat = max(1, repeat)
    rows, samples = [], []
    for probe in probes:
        for _ in range(repeat):
            start = time.perf_counter()
            hits = knowledge.query(probe.text)['hits']
            samples.append((time.perf_counter() - start) * 1000)
        top5 = hits[:5]
        article_rank = next((i for i, h in enumerate(top5, 1) if h['id'] in probe.gold_articles), None)
        fact_rank = next((i for i, h in enumerate(hits, 1) if h['id'] in probe.gold_facts), None)
        latest_rank = next((i for i, h in enumerate(hits, 1) if h['id'] in probe.latest_facts), None)
        full_rank = latest_rank
        if full_rank is None:
            scores = knowledge._one_hop(probe.text, knowledge._bm25(probe.text))
            order = sorted((-score, i) for i, score in enumerate(scores) if score > 0)
            full_rank = next((rank for rank, (_, i) in enumerate(order, 1)
                              if knowledge.records[i]['id'] in probe.latest_facts), None)
        rows.append(dict(
            label=probe.label, group=probe.group, as_of_status=probe.as_of_status, query=probe.text,
            gold_articles=list(probe.gold_articles), gold_facts=list(probe.gold_facts),
            latest_facts=list(probe.latest_facts),
            hit_at_5=float(article_rank is not None or (fact_rank is not None and fact_rank <= 5)),
            article_rank_at_5=article_rank, article_mrr_at_5=1 / article_rank if article_rank else 0.0,
            fact_rank_at_10=fact_rank, latest_fact_rank_at_10=latest_rank, latest_fact_full_rank=full_rank,
            top5_snippet_pass=any(snippet_matches(h['snippet'], probe) for h in top5),
            gold_article_snippet_pass=any(h['id'] in probe.gold_articles and snippet_matches(h['snippet'], probe)
                                          for h in top5),
            top5_hits=[{k: h[k] for k in ('id', 'kind', 'via', 'snippet')} for h in top5],
        ))
    return dict(corpus=label, rows=rows, queries=len(rows), articles=len(knowledge.value['articles']),
                facts=len(knowledge.value['facts']),
                hit_at_5=statistics.fmean(row['hit_at_5'] for row in rows),
                article_mrr_at_5=statistics.fmean(row['article_mrr_at_5'] for row in rows),
                top5_snippet_pass_count=sum(row['top5_snippet_pass'] for row in rows),
                gold_article_snippet_pass_count=sum(row['gold_article_snippet_pass'] for row in rows),
                avg_ms=round(statistics.fmean(samples), 3), p95_ms=round(percentile(samples, 0.95), 3),
                samples=len(samples))


def load_corpora_998(admission: Path) -> dict[str, production.Knowledge]:
    from tools.player_host_replay_benchmark import export_sealed_v3_tag

    run = admission / 'run'
    path = run / 'curator-runner' / 'delivered' / 'v97.json'
    selection = json.loads((run / 'private' / 'knowledge-full.json').read_text(encoding='utf-8'))['selection']
    latest = export_sealed_v3_tag(admission / 'knowledge' / 'cdda' / 'cdda', 'v101', selection)
    return {'998_v97': production.Knowledge.from_dict(_project_v3_to_v4(json.loads(path.read_text(encoding='utf-8'))), str(path)),
            '998_v101': production.Knowledge.from_dict(_project_v3_to_v4(latest))}


def benchmark(evidence: Path, repeat: int, *, porter2=None, include_998=True) -> dict:
    corpora = {name: Corpus.load(name, evidence / path) for name, path in CORPORA.items()}
    results = {name: retrieval(corpora[name], [q for q in QUERIES if q.corpus == name], repeat)
               for name in ('v91', 'v17')}
    # Guard against accidental drift in the historical #920 baseline scorer.
    expected_baseline = {'v91': (1.0, 0.7), 'v17': (1.0, 0.65)}
    for name, (hit5, mrr5) in expected_baseline.items():
        actual = results[name]['methods']['prod_bm25']
        if (actual['hit_at_5'], actual['article_mrr_at_5']) != (hit5, mrr5):
            raise ValueError(f'{name}: #920 baseline metrics drifted: {(actual["hit_at_5"], actual["article_mrr_at_5"])} != {(hit5, mrr5)}')
    live = [dict(label=q.label, corpus=q.corpus, query=q.text,
                 top5={m: corpora[q.corpus].ids(corpora[q.corpus].rank(m, q.text)[:CUT]) for m in METHODS})
            for q in LIVE]
    gate = overall_gate(results)
    pairs = folding_pairs(porter2)
    porter2_gate = compare_porter2(evidence, results, repeat, porter2) if porter2 is not None else None
    admission = evidence / 'multi-day-standard-build-998-admission-04'
    probes_998 = ({name.removeprefix('998_'): evaluate_probes_998(knowledge, PROBES_998, repeat, label=name)
                   for name, knowledge in load_corpora_998(admission).items()}
                  if include_998 and admission.is_dir() else None)
    return dict(schema='knowledge-retrieval-benchmark/2', repeat=repeat, probes_998=probes_998,
                corpora={name: dict(path=CORPORA[name], articles=c.article_count,
                                    facts=c.fact_count, edges=sum(map(len, c.neighbours)) // 2,
                                    links=c.links, unresolved_links=c.unresolved_links)
                         for name, c in corpora.items()},
                retrieval=results, live=live, overall_gate=gate,
                omission_scan=[omission_scan(corpora[n], [q for q in QUERIES if q.corpus == n]) for n in ('v91', 'v17')],
                paired_skip=paired_skip(corpora), folding_pairs=pairs,
                porter2=dict(gates=porter2_gate, passes=all(all(g.values()) for g in porter2_gate.values())
                             and all(row['porter2_conflates'] for row in pairs)) if porter2_gate is not None else None,
                compact_serialization=compact_serialization(corpora['v91'], [q for q in QUERIES if q.corpus == 'v91'],
                                                            repeat))


# Output.

def _cell(value: object) -> str:
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, float):
        return f'`{value:.3f}`'
    return f'`{value}`'


def markdown(result: dict) -> str:
    out = [f'# Knowledge retrieval benchmark (`{result["schema"]}`)', '',
           f'Timing: {result["repeat"]} repetitions of every query; production scoring and graph expansion; '
           'title links resolved: ' + ', '.join(f'`{n}` {x["links"] - x["unresolved_links"]} of {x["links"]}'
                                               for n, x in result['corpora'].items()) + '.', '']
    out += ['| Corpus | Method | Hit@5 | Article Recall@5 | Article MRR@5 | Reached@10 | Avg ms | p95 ms | Samples |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for name, r in result['retrieval'].items():
        for method, m in r['methods'].items():
            out.append(f'| `{CORPUS_NAMES[name]}` ({r["queries"]} queries) | `{method}` | {_cell(m["hit_at_5"])} | '
                       f'{_cell(m["article_recall_at_5"])} | {_cell(m["article_mrr_at_5"])} | '
                       f'{_cell(m["reached_at_10"])} | {_cell(m["avg_ms"])} | {_cell(m["p95_ms"])} | {_cell(m["samples"])} |')
    out += ['', '| Corpus | Sealed file | Articles | Facts | Graph edges |', '| --- | --- | --- | --- | --- |']
    out += [f'| `{CORPUS_NAMES[name]}` | `{c["path"]}` | {_cell(c["articles"])} | {_cell(c["facts"])} | {_cell(c["edges"])} |'
            for name, c in result['corpora'].items()]
    out += ['', '## Gate 9 overall ranking on the projected snapshots', '',
            '| Corpus and arm | Hit@5 ≥ baseline | Article MRR@5 ≥ baseline | p95 < 5 ms |', '| --- | --- | --- | --- |']
    for key, g in result['overall_gate'].items():
        out.append(f'| `{key}` | {_cell(g["hit_at_5"])} | {_cell(g["article_mrr_at_5"])} | {_cell(g["p95_under_5_ms"])} |')
    for name, r in result['retrieval'].items():
        methods = r['methods']
        out += ['', f'## Per-query first gold-article rank in top 5, `{CORPUS_NAMES[name]}`', '',
                '| Query | Group | Text | ' + ' | '.join(f'`{m}`' for m in methods) + ' |',
                '| --- | --- | --- | ' + ' | '.join('---' for _ in methods) + ' |']
        for row in r['rows']:
            out.append(f'| {row["label"]} | `{row["group"]}` | `{row["query"]}` | '
                       + ' | '.join(_cell(row['ranks'][m]) for m in methods) + ' |')
    out += ['', '## Live queries on the versions the player held', '']
    for row in result['live']:
        out.append(f'- **{row["label"]}** `{row["query"]}`')
        for method in METHODS:
            out.append(f'  - `{method}`: ' + (', '.join(f'`{i}`' for i in row['top5'][method]) or '`[]`'))
    paired = result['paired_skip']
    out += ['', '## Paired coverage-skip comparison on the direct-answer subset', '',
            f'{paired["queries"]} labelled queries; the skip suppresses a gold fact from the top 10 in '
            f'{paired["suppressed"]}.', '',
            *(f'- `{row["corpus"]}` {row["label"]} (topic of {row["topic"]}): `{row["query"]}`' for row in paired['rows']),
            '',
            '| Query | Gold facts | Detail | Arm | Reached@10 | Fact Recall@5 | Fact MRR@5 | Fact rank | Reads@5 | Reads@10 |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in paired['rows']:
        for arm, values in (('no skip', row['no_skip']), ('skip', row['skip'])):
            out.append(f'| `{row["corpus"]}` {row["label"]} | ' + ', '.join(f'`{f}`' for f in row['facts'])
                       + f' | `{row["detail"]}` | {arm} | {_cell(values["reached_at_10"])} | '
                       f'{_cell(values["fact_recall_at_5"])} | {_cell(round(values["fact_mrr_at_5"], 3))} | '
                       f'{_cell(values["fact_rank_at_10"])} | {_cell(values["reads_at_5"])} | {_cell(values["reads_at_10"])} |')
    out += ['', '| Arm | Reached@10 | Fact Recall@5 | Fact MRR@5 | Reads@5 | Unreached@5 | Reads@10 | Unreached@10 |',
            '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for arm, values in (('`bm25_1hop`', paired['no_skip']), ('`bm25_1hop_skip`', paired['skip'])):
        out.append(f'| {arm} | ' + ' | '.join(_cell(values[k]) for k in (
            'reached_at_10', 'fact_recall_at_5', 'fact_mrr_at_5', 'reads_at_5', 'unreached_at_5', 'reads_at_10',
            'unreached_at_10')) + ' |')
    out += ['', 'Gate 9 conditions: ' + ', '.join(f'{k} {_cell(v)}' for k, v in paired['conditions'].items()) + '; '
            + 'adds reads ' + ', '.join(f'{k} {_cell(v)}' for k, v in paired['adds_reads'].items()) + '.',
            '', f'**Decision for #937: {paired["decision"]}.**', '',
            'Omission scan (top-10 `bm25_1hop` facts holding a number no citing article states): '
            + '; '.join(f'`{s["corpus"]}` {s["appearances"]} appearances of {s["distinct_facts"]} distinct facts, '
                        f'{s["appearances_skipped"]} appearances of {s["distinct_facts_skipped"]} facts skipped'
                        for s in result['omission_scan']) + '.']
    out += ['', '## English folding pairs', '',
            '| Words | Original forms | Original conflates | Porter2 forms | Porter2 conflates |',
            '| --- | --- | --- | --- | --- |']
    for row in result['folding_pairs']:
        new = ' / '.join(row['porter2']) if row['porter2'] is not None else None
        out.append(f'| {_cell(" / ".join(row["words"]))} | {_cell(" / ".join(row["original"]))} | '
                   f'{_cell(row["original_conflates"])} | {_cell(new)} | {_cell(row["porter2_conflates"])} |')
    porter2 = result['porter2']
    if porter2 is None:
        out += ['', 'Porter2 skipped. Use `--porter2` with the optional `snowballstemmer` package installed.']
    else:
        out += ['', f'**Porter2 gate: {"GO" if porter2["passes"] else "NO-GO"}.**', '',
                '| Corpus | Hit@5 ≥ one-hop baseline | Article MRR@5 ≥ one-hop baseline |', '| --- | --- | --- |']
        for name, gate in porter2['gates'].items():
            out.append(f'| {name} | {_cell(gate["hit_at_5"])} | {_cell(gate["article_mrr_at_5"])} |')
    compact = result['compact_serialization']
    out += ['', f'## Canonical UTF-8 serialization on {compact["queries"]} `v91` queries', '',
            'Envelope construction and scoring take place before this timer starts.', '',
            '| Envelope | Total bytes | Median bytes | Max bytes | Avg ms | p95 ms | Samples |',
            '| --- | --- | --- | --- | --- | --- | --- |']
    for name in ('full', 'compact'):
        row = compact[name]
        out.append(f'| {name} | {row["total_bytes"]:,} | {row["median_bytes"]:,.1f} | {row["max_bytes"]:,} | '
                   f'{row["avg_ms"]:.4f} | {row["p95_ms"]:.4f} | {row["samples"]:,} |')
    if result.get('probes_998'):
        out += ['', '## Sealed #998 retrieval probes', '',
                '| Version | Probe | As of | Hit@5 | Article rank@5 | Latest fact rank | Top-5 snippet | Gold article snippet |',
                '| --- | --- | --- | --- | --- | --- | --- | --- |']
        for version, corpus in result['probes_998'].items():
            for row in corpus['rows']:
                cells = (row[key] for key in ('label', 'as_of_status', 'hit_at_5', 'article_rank_at_5',
                                              'latest_fact_full_rank', 'top5_snippet_pass',
                                              'gold_article_snippet_pass'))
                out.append(f'| {version} | ' + ' | '.join(map(_cell, cells)) + ' |')
    return '\n'.join(out) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--evidence', type=Path, help='the sealed evidence store (default: the main checkout\'s)')
    parser.add_argument('--repeat', type=int, default=50, help='timing repetitions of every query (default 50)')
    parser.add_argument('--porter2', action='store_true', help='also measure the optional English Porter2 arm')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--json', action='store_true')
    output.add_argument('--markdown', action='store_true')
    args = parser.parse_args(argv)
    if args.evidence is None:
        from tools.evidence import default_store
        args.evidence = default_store()
    fold = None
    if args.porter2:
        try:
            import snowballstemmer
        except ModuleNotFoundError as error:
            if error.name != 'snowballstemmer':
                raise
            parser.error('--porter2 requires the optional snowballstemmer package in this Python environment')
        english = snowballstemmer.stemmer('english')

        def fold(word: str) -> str:
            return english.stemWord(word.casefold())

    result = benchmark(args.evidence, max(1, args.repeat), porter2=fold)
    print(json.dumps(result, indent=2) if args.json else markdown(result), end='' if not args.json else '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
