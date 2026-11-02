"""Recall: software ranking of recorded episodes against the current subgoal.

A candidate is a trusted `recorded` episode (see `episodes.episode`). Relevance is BM25 (k1 = 1.2, b = 0.75, the
fixed standard values) over the episode's text fields, with the subgoal's text and expected observations as the
query, multiplied by the recorder's confidence and by 1.5 when the episode has a residual. There is no demotion.
With no subgoal there is no query: recall is the most recent episodes. The level sees the top 10; the actor's tail
sees the top 2 plus one exploration item, an earlier-session episode outside the top 10 drawn uniformly with a seed
fixed per pass. Byte truncation of what is shown belongs to the host, not to this module.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import math
import random
import re
from typing import Any

K1, B = 1.2, 0.75
RESIDUAL_WEIGHT = 1.5
LEVEL_ITEMS = 10
TAIL_TOP_ITEMS = 2
TEXT_FIELDS = ('attempted', 'counterpart', 'residual', 'changed')


def tokens(text: str) -> list[str]:
    return re.findall(r'\w+', text.lower())


def query_text(subgoal: dict | None) -> str | None:
    """The subgoal's text and its expected observations as one query, or None when there is no subgoal."""
    if subgoal is None:
        return None
    return ' '.join([subgoal['text'], *(subgoal['data'].get('expected_observations') or [])])


def prepare(episode: dict) -> tuple[Counter, int]:
    """An episode's term counts and token length over its text fields: computed once, as episodes never change."""
    words = tokens(' '.join(episode[f] for f in TEXT_FIELDS))
    return Counter(words), len(words)


def bm25_prepared(query: str, documents: list[tuple[Counter, int]]) -> list[float]:
    """BM25 of each prepared document `(term counts, length)` against the query, with the non-negative Lucene IDF."""
    terms = set(tokens(query))
    count = len(documents)
    if not count:
        return []
    average = sum(length for _, length in documents) / count or 1.
    frequency = {term: sum(term in counts for counts, _ in documents) for term in terms}
    scores = []
    for counts, length in documents:
        score = 0.
        for term in terms:
            tf = counts.get(term, 0)
            if tf:
                idf = math.log(1 + (count - frequency[term] + .5) / (frequency[term] + .5))
                score += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / average))
        scores.append(score)
    return scores


def bm25(query: str, documents: list[list[str]]) -> list[float]:
    """BM25 of each document (a token list) against the query."""
    return bm25_prepared(query, [(Counter(d), len(d)) for d in documents])


def rank(candidates: list[dict], query: str | None, prepared: list[tuple[Counter, int]] | None = None
         ) -> list[dict[str, Any]]:
    """Candidates (trusted recorded episodes, oldest first) ordered best first as `dict(episode, score, age)`.

    Ties go to the newer episode. With no query the order is recency alone and every score is None. `age` is the
    candidate's index in commit order, which is stable as episodes are added. `prepared` optionally holds each
    candidate's `prepare()` result, so a caller that caches them avoids re-tokenising; the ranking is identical.
    """
    if query is None:
        return [dict(episode=e, score=None, age=i) for i, e in reversed(list(enumerate(candidates)))]
    relevance = bm25_prepared(query, [prepare(e) for e in candidates] if prepared is None else prepared)
    scored = [dict(episode=e, score=r * e['confidence'] * (RESIDUAL_WEIGHT if e['residual'].strip() else 1.), age=i)
              for i, (e, r) in enumerate(zip(candidates, relevance, strict=True))]
    scored.sort(key=lambda item: (-item['score'], -item['age']))
    return scored


def exploration_seed(session: str, pass_index: int) -> int:
    return int.from_bytes(hashlib.sha256(f'{session}:{pass_index}'.encode()).digest()[:8], 'big')


def select(ranked: list[dict[str, Any]], *, audience: str, session: str, pass_index: int) -> list[dict[str, Any]]:
    """The recall a reader sees: the top 10 for the level, or 2 top items plus 1 exploration item for the tail.

    The exploration item is an episode of an earlier session that is not in the top 10, drawn uniformly (in
    commit order, so the pool's order is stable) with a seed from the session id and the pass index; with no such
    episode there is none. Items are `dict(episode, score, age, exploration)`.
    """
    if audience not in ('level', 'tail'):
        raise ValueError('Recall audience is level or tail')
    top = ranked[:LEVEL_ITEMS]
    if audience == 'level':
        return [dict(item, exploration=False) for item in top]
    chosen = [dict(item, exploration=False) for item in top[:TAIL_TOP_ITEMS]]
    pool = [item for item in ranked[LEVEL_ITEMS:] if item['episode']['session'] != session]
    pool.sort(key=lambda item: item['age'])
    if pool:
        chosen.append(dict(random.Random(exploration_seed(session, pass_index)).choice(pool), exploration=True))
    return chosen
