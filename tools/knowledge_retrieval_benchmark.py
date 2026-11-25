#!/usr/bin/env python3
"""Offline retrieval benchmark for Wave 3 (#936) on sealed delivered knowledge. Read-only, `$0`.

  python tools/knowledge_retrieval_benchmark.py [--evidence DIR] [--repeat N] [--porter2] [--json | --markdown]

It replays the 30 #924 queries (20 on `#896-b v91`, 10 on `#889 v17`) and the two live `#896-b` queries on the
versions the player held (`A01 v3`, `A03 v38`) under three rankings:

- `prod_bm25`: `harness.player.knowledge.Knowledge(path).query(q)`, #920's merged field-weighted BM25, called as is.
- `bm25_1hop`: the same BM25 scores (recomputed with the production index, terms and constants, and checked
  against the production order on every query), plus one hop over an undirected graph of claim citations and
  title-resolved links: each of the 10 best records `u` with score `s > 0` and degree above 0 adds
  `0.35 * s / sqrt(deg(u))` to each neighbour, times `1.25` for an article and `0.70` for a fact; records with a
  positive combined score are ordered by score, ties by delivered order; the first 10 are returned.
- `bm25_1hop_skip`: the identical order walked with the rank-order coverage skip: a fact that an article already
  kept cites is skipped, and the walk stops at 10 records.

The graph is the test-only projection that Gate 9 names: the old ID stands in for the slug, and a link (a title in
`delivered-knowledge/2`) resolves to the article with that title. The old `type` stays indexed at weight 2, in the
slot that tags take in `delivered-knowledge/3`, because the sealed files carry no tags.

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
SEEDS = 10
HOP, ARTICLE_WEIGHT, FACT_WEIGHT = 0.35, 1.25, 0.70
METHODS = ('prod_bm25', 'bm25_1hop', 'bm25_1hop_skip')
PORTER2 = 'bm25_1hop_porter2'
FOLDING_PAIRS = (('zombie', 'zombies'), ('speed', 'speeds'), ('focus', 'focused'),
                 ('spring', 'springs'), ('bleed', 'bleeding'))
LEGACY_CLAIM_KINDS = {
    'control': 'interface', 'world_observation': 'instance_state', 'crafting_recipe': 'mechanic',
    'item_property': 'entity_property', 'construction_project': 'mechanic',
    'creation_option_property': 'entity_property',
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


def _v2_weighted_terms(record: dict) -> tuple[dict[str, int], int]:
    """Historical #920 field-weighted BM25 index over sealed `delivered-knowledge/2` records."""
    if 'body' in record:
        fields = ((3, record['title']), (2, record['lead']), (1, ' '.join(c['text'] for c in record['body'])))
    else:
        fields = ((3, record.get('subject', '')), (2, record.get('type', '')), (1, record['text']))
    weights: dict[str, int] = {}
    length = 0
    for weight, text in fields:
        for term in production.terms_of(text):
            weights[term] = weights.get(term, 0) + weight
            length += weight
    return weights, length


class Corpus:
    """One sealed `delivered-knowledge/2` file with the #920 BM25 baseline index and the projected one-hop graph."""

    def __init__(self, name: str, value: dict, where: str = 'delivered knowledge'):
        if (not isinstance(value, dict) or value.get('schema') != 'delivered-knowledge/2'
                or not isinstance(value.get('articles'), list) or not isinstance(value.get('facts'), list)):
            raise ValueError(f'{where}: expected sealed delivered-knowledge/2 benchmark input')
        self.name = name
        self.version = value['version']
        self.article_count = len(value['articles'])
        self.fact_count = len(value['facts'])
        self.records = list(value['articles']) + list(value['facts'])
        self.index = [_v2_weighted_terms(r) for r in self.records]
        self.position = {r['id']: i for i, r in enumerate(self.records)}
        self.article = [('body' in r) for r in self.records]
        titles = {r['title']: i for i, r in enumerate(self.records) if 'body' in r}
        self.cites: list[frozenset[int]] = []
        neighbours: list[set[int]] = [set() for _ in self.records]
        self.links = self.unresolved_links = 0
        for i, record in enumerate(self.records):
            cited = frozenset(self.position[f] for claim in record.get('body', ()) for f in claim['facts'])
            self.cites.append(cited)
            targets = set(cited)
            for link in record.get('links', ()):
                self.links += 1
                if link in titles:
                    targets.add(titles[link])
                else:
                    self.unresolved_links += 1
            targets.discard(i)
            for j in targets:
                neighbours[i].add(j)
                neighbours[j].add(i)
        self.neighbours = [sorted(n) for n in neighbours]
        self.citing: list[list[int]] = [[] for _ in self.records]
        for i, cited in enumerate(self.cites):
            for j in sorted(cited):
                self.citing[j].append(i)

    @classmethod
    def load(cls, name: str, path: Path) -> 'Corpus':
        return cls(name, json.loads(path.read_text()), str(path))

    def bm25(self, query: str) -> list[float]:
        """The production scores, in the production order of operations so ties fall the same way."""
        terms = list(dict.fromkeys(production.terms_of(query)))
        count = len(self.index)
        average = sum(length for _, length in self.index) / count if count else 0.0
        frequency = {t: sum(1 for weights, _ in self.index if t in weights) for t in terms}
        scores = []
        k1, b = production.BM25_K1, production.BM25_B
        for weights, length in self.index:
            score = 0.0
            for term in terms:
                tf = weights.get(term, 0)
                if tf:
                    idf = math.log(1 + (count - frequency[term] + 0.5) / (frequency[term] + 0.5))
                    score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / average))
            scores.append(score)
        return scores

    def one_hop(self, scores: list[float]) -> list[float]:
        """Spread from the SEEDS best records with a positive score and a neighbour; an isolated record takes no slot."""
        combined = list(scores)
        seeds = sorted((-s, i) for i, s in enumerate(scores) if s > 0 and self.neighbours[i])[:SEEDS]
        for negative, u in seeds:
            spread = HOP * -negative / math.sqrt(len(self.neighbours[u]))
            for v in self.neighbours[u]:
                combined[v] += spread * (ARTICLE_WEIGHT if self.article[v] else FACT_WEIGHT)
        return combined

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
        order = self.ordered(self.one_hop(self.bm25(query)))
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
    order = corpus.ordered(corpus.one_hop(scores))[:LIMIT]
    # Historical `player-knowledge/2` full-record baseline vs. production `player-knowledge/3` compact hits.
    full = dict(schema='player-knowledge/2', version=corpus.version, grants_authority=False,
                identity=query, resolution='query', resolved_from=None,
                records=[copy.deepcopy(corpus.records[i]) for i in order])
    clip = getattr(production, '_clip_snippet', lambda text: text if len(text) <= 240 else text[:239].rstrip() + '…')
    hits = []
    for i in order:
        item = corpus.records[i]
        via = 'match' if scores[i] > 0 else 'hop'
        if corpus.article[i]:
            # The archive has no revisions or tags. Use the snapshot tag as an as-of revision.
            hit = dict(id=item['id'], kind='article', revision=f"{item['id']}@{corpus.version}",
                       title=item['title'], snippet=clip(item['lead']), tags=[], via=via)
        else:
            kind = LEGACY_CLAIM_KINDS[item['type']]
            scope = {'game': 'cdda'}
            if kind == 'instance_state':
                scope['world'] = None
            hit = dict(id=item['id'], kind='fact', subject=item.get('subject'), claim_kind=kind, scope=scope,
                       snippet=clip(item['text']), cited_by_articles=sorted(set(corpus.ids(corpus.citing[i])))[:3],
                       via=via)
        hits.append(hit)
    compact = dict(schema='player-knowledge/3', version=corpus.version, grants_authority=False,
                   identity=query, resolution='query', resolved_from=None, hits=hits)
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


def benchmark(evidence: Path, repeat: int, *, porter2=None) -> dict:
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
    return dict(schema='knowledge-retrieval-benchmark/1', repeat=repeat,
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
           f'Timing: {result["repeat"]} repetitions of every query; production order parity checked on all 32 queries; '
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
