"""Read only the delivered subset: the frozen file, or a newer version adopted during play. No curator or evaluation dependency."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import re

from .contracts import PlayerError

SCHEMA = 'delivered-knowledge/3'
RESULT = 'player-knowledge/2'
FIELDS = frozenset(('schema', 'version', 'commit', 'repository_id', 'coverage', 'articles', 'facts', 'history'))
# `\Z`, never `$`: `$` also matches before a final newline, so `fullmatch` alone would not refuse `v1\n`.
VERSION = re.compile(r'v(0|[1-9][0-9]*)\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')
IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')
REVISION = re.compile(r'([a-z0-9][a-z0-9-]{0,63})@v(?:0|[1-9][0-9]*)\Z')
SOURCE = re.compile(r'[0-9a-f]{32}-[1-9][0-9]*\Z')
ALIAS = re.compile(r's(?:0[1-9]|[1-9][0-9]+)\Z')
TAG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
AXIS = re.compile(r'[a-z][a-z0-9_]{0,31}\Z')
ASCII = re.compile(r'[ -~]{1,64}\Z')
CLAIM_KINDS = frozenset(('interface', 'mechanic', 'entity_property', 'instance_state', 'strategy'))
EVIDENCE_BASES = frozenset(('observed', 'inferred', 'hinted'))
LIFECYCLE_STATES = frozenset(('active', 'contested'))
BRANCH_RELATIONS = frozenset(('same', 'inherited', 'unknown'))
RELATIONS = frozenset(('depends_on', 'contradicts', 'part_of', 'see_also'))
REASONS = frozenset(('restated', 'narrowed', 'corrected'))
READ_BY = ('any', 'id')
EMPTY_HISTORY = {'replaced': {}, 'ended': [], 'retracted': []}


def empty() -> dict:
    return dict(schema=SCHEMA, version=None, commit=None, repository_id=None, coverage=None, articles=[], facts=[],
                history=copy.deepcopy(EMPTY_HISTORY))


def version_number(version: object) -> int | None:
    """The number N of a published version `vN`, else None."""
    return int(version[1:]) if isinstance(version, str) and VERSION.fullmatch(version) else None


# The public record forms `tools/knowledge_export.py` writes; `tools/player_host/knowledge.mjs` checks the same ones,
# and both readers are held to the shared fixtures in `tests/fixtures/delivered-knowledge-3/`.
COVERAGE_FIELDS = frozenset(('schema', 'session', 'actor', 'last_step'))
POSITION_FIELDS = frozenset(('session', 'actor', 'step', 'order'))
FLAGS = ('needs_review', 'condition_unverified', 'unverified_branch')
SHARED_FIELDS = frozenset(('id', 'tags', 'scope', 'branch_relation', 'lifecycle_state', 'stale_citations', *FLAGS,
                           'links', 'backlinks', 'shadowed_by', 'contradicted_by'))
ARTICLE_FIELDS = SHARED_FIELDS | {'revision', 'title', 'lead', 'body', 'last_confirmed'}
FACT_REQUIRED = SHARED_FIELDS | {'claim_kind', 'evidence_basis', 'text', 'cited_by_articles', 'citation_source_ids', 'seen'}
FACT_FIELDS = FACT_REQUIRED | {'subject', 'when'}


def _matches(pattern: re.Pattern, value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _distinct(value: object, allowed=None, *, nonempty: bool = False) -> bool:
    """A list of distinct strings, each in `allowed` when given (a set, or a predicate)."""
    if not isinstance(value, list) or (nonempty and not value) or not all(isinstance(v, str) for v in value):
        return False
    if len(set(value)) != len(value):
        return False
    return allowed is None or all((allowed(v) if callable(allowed) else v in allowed) for v in value)


def _coverage(value: object) -> bool:
    return value is None or (
        isinstance(value, dict) and set(value) == COVERAGE_FIELDS and value['schema'] == 'curator-coverage/2'
        and _matches(ALIAS, value['session']) and (value['actor'] is None or _nonblank(value['actor']))
        and (value['last_step'] is None or type(value['last_step']) is int))


def _position(value: object) -> bool:
    return (isinstance(value, dict) and set(value) == POSITION_FIELDS
            and _matches(ALIAS, value['session']) and _nonblank(value['actor']) and type(value['step']) is int
            and isinstance(value['order'], list) and len(value['order']) == 3
            and type(value['order'][0]) is int and isinstance(value['order'][1], str) and type(value['order'][2]) is int)


def _tags(value: object) -> bool:
    return _distinct(value, lambda t: len(t) <= 32 and TAG.fullmatch(t) is not None) and len(value) <= 8


def _scope(value: object) -> bool:
    """1..8 axes including `game`; a world-bound record's `world` is delivered as null, never as its label."""
    return (isinstance(value, dict) and 1 <= len(value) <= 8 and 'game' in value
            and all(_matches(AXIS, k) and (v is None if k == 'world' else _matches(ASCII, v)) for k, v in value.items()))


def _when(value: object) -> bool:
    return (isinstance(value, dict) and set(value) == {'note', 'requires'} and _nonblank(value['note'])
            and isinstance(value['requires'], dict) and len(value['requires']) <= 8
            and all(_matches(AXIS, k) and k not in ('game', 'world') and _matches(ASCII, v)
                    for k, v in value['requires'].items()))


def _links(value: object, end: str, owner: str, public: set[str]) -> bool:
    if not isinstance(value, list):
        return False
    pairs = set()
    for link in value:
        if (not isinstance(link, dict) or set(link) != {'rel', end} or link['rel'] not in RELATIONS
                or not isinstance(link[end], str) or link[end] == owner or link[end] not in public):
            return False
        pairs.add((link['rel'], link[end]))
    return len(pairs) == len(value)


def _record(value: dict, public: set[str], history: set[str]) -> bool:
    """The fields articles and facts share, checked against the public set `P` and the public history set `H`."""
    owner = value['id']
    bound = isinstance(value['scope'], dict) and 'world' in value['scope']
    others = public - {owner}
    return (_tags(value['tags']) and _scope(value['scope'])
            and (value['branch_relation'] in BRANCH_RELATIONS if bound
                 else value['branch_relation'] is None and value['unverified_branch'] is False)
            and value['lifecycle_state'] in LIFECYCLE_STATES and all(type(value[flag]) is bool for flag in FLAGS)
            and _distinct(value['stale_citations'], history)
            and _links(value['links'], 'target', owner, public) and _links(value['backlinks'], 'source', owner, public)
            and _distinct(value['shadowed_by'], others) and _distinct(value['contradicted_by'], others))


def _article(value: object, facts: set[str], public: set[str], history: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != ARTICLE_FIELDS:
        return False
    revision = REVISION.fullmatch(value['revision']) if isinstance(value['revision'], str) else None
    return (revision is not None and revision.group(1) == value['id']
            and _nonblank(value['title']) and _nonblank(value['lead']) and _position(value['last_confirmed'])
            and isinstance(value['body'], list) and bool(value['body'])
            and all(isinstance(c, dict) and set(c) == {'text', 'facts'} and _nonblank(c['text'])
                    and _distinct(c['facts'], facts, nonempty=True) for c in value['body'])
            and _record(value, public, history))


def _fact(value: object, articles: set[str], public: set[str], history: set[str]) -> bool:
    if not isinstance(value, dict) or not FACT_REQUIRED <= set(value) <= FACT_FIELDS:
        return False
    bound = isinstance(value['scope'], dict) and 'world' in value['scope']
    return (value['claim_kind'] in CLAIM_KINDS and value['evidence_basis'] in EVIDENCE_BASES
            and (value['claim_kind'] != 'instance_state' or bound)
            and _nonblank(value['text']) and ('subject' not in value or _nonblank(value['subject']))
            and ('when' not in value or _when(value['when'])) and _position(value['seen'])
            and _distinct(value['cited_by_articles'], articles)
            and _distinct(value['citation_source_ids'], lambda s: SOURCE.fullmatch(s) is not None, nonempty=True)
            and _record(value, public, history))


def _history(value: object, articles: set[str], facts: set[str], revisions: set[str]) -> bool:
    """Old identifiers name only public replacements; `ended` and `retracted` name fact IDs and retired slugs."""
    if not isinstance(value, dict) or set(value) != set(EMPTY_HISTORY):
        return False
    replaced, ended, retracted = value['replaced'], value['ended'], value['retracted']
    public = articles | facts
    if not isinstance(replaced, dict) or not _distinct(ended, IDENTIFIER.fullmatch) or not _distinct(retracted, IDENTIFIER.fullmatch):
        return False
    gone = set(ended) | set(retracted)
    if set(ended) & set(retracted) or gone & public:
        return False
    for key, entry in replaced.items():
        if (not isinstance(key, str) or key in public or key in revisions or key in gone or not isinstance(entry, dict)
                or set(entry) != {'reason', 'by'} or not _distinct(entry['by'], nonempty=True)):
            return False
        revision = REVISION.fullmatch(key)
        if revision is not None:  # An earlier revision of a delivered slug redirects to that slug alone.
            if entry['reason'] != 'restated' or entry['by'] != [revision.group(1)] or revision.group(1) not in articles:
                return False
        elif IDENTIFIER.fullmatch(key) is None or entry['reason'] not in REASONS or not set(entry['by']) <= facts:
            return False
    return True


def _valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA:
        return False
    if not all(isinstance(value[name], list) for name in ('articles', 'facts')):
        return False
    # The empty file names no version, commit, repository, coverage, record or history.
    if value['version'] is None:
        return (value['commit'] is None and value['repository_id'] is None and value['coverage'] is None
                and value['articles'] == [] and value['facts'] == [] and value['history'] == EMPTY_HISTORY)
    if version_number(value['version']) is None or not _matches(COMMIT, value['commit']):
        return False
    if not _matches(COMMIT, value['repository_id']) or not _coverage(value['coverage']):
        return False
    records = value['articles'] + value['facts']
    if not all(isinstance(r, dict) and _matches(IDENTIFIER, r.get('id')) for r in records):
        return False
    articles, facts = {a['id'] for a in value['articles']}, {f['id'] for f in value['facts']}
    if len(articles | facts) != len(records):
        return False
    revisions = {a.get('revision') for a in value['articles']} - {None}
    if not _history(value['history'], articles, facts, revisions):
        return False
    history = value['history']
    public_history = set(history['replaced']) | set(history['ended']) | set(history['retracted'])
    public = articles | facts
    return (all(_article(a, facts, public, public_history) for a in value['articles'])
            and all(_fact(f, articles, public, public_history) for f in value['facts']))


class Knowledge:
    """One delivered version. Never changed after it is read; a newer version is another object."""

    def __init__(self, path: Path):
        self._set(json.loads(path.read_text()), str(path))

    @classmethod
    def from_dict(cls, value: object, where: str = 'delivered knowledge') -> 'Knowledge':
        knowledge = cls.__new__(cls)
        knowledge._set(value, where)
        return knowledge

    def _set(self, value: object, where: str) -> None:
        if not _valid(value):
            raise PlayerError(f'{where}: unsupported delivered knowledge')
        self.value = value
        self.records = value['articles'] + value['facts']
        self._index = [_weighted_terms(r) for r in self.records]
        self._position = {r['id']: i for i, r in enumerate(self.records)}
        self._revisions = {a['revision']: a for a in value['articles']}
        self._titles: dict[str, dict] = {}
        for a in value['articles']:
            self._titles.setdefault(a['title'], a)
        self._neighbours = _graph(self.records, self._position)

    def _result(self, identity: str, resolution: str, resolved_from: str | None, records: list[dict]) -> dict:
        return dict(schema=RESULT, version=self.value['version'], grants_authority=False, identity=identity,
                    resolution=resolution, resolved_from=resolved_from, records=copy.deepcopy(records))

    def read(self, identity: str, *, by: str = 'any') -> dict:
        """One delivered record, or where an old identifier went. Rows are tried in this order, so an ID or slug
        wins over an equal title; `by='id'` skips the title row."""
        if by not in READ_BY:
            raise PlayerError('Knowledge read `by` must be "any" or "id"')
        history = self.value['history']
        if identity in self._position:
            return self._result(identity, 'current', None, [self.records[self._position[identity]]])
        if identity in self._revisions:
            return self._result(identity, 'revision', identity, [self._revisions[identity]])
        if identity in history['replaced']:
            entry = history['replaced'][identity]
            revision = REVISION.fullmatch(identity)
            resolution = 'revision' if revision is not None else entry['reason']
            return self._result(identity, resolution, identity,
                                [self.records[self._position[rid]] for rid in entry['by']])
        for resolution in ('ended', 'retracted'):
            if identity in history[resolution]:
                return self._result(identity, resolution, identity, [])
        if by == 'any' and identity in self._titles:
            return self._result(identity, 'title', None, [self._titles[identity]])
        return self._result(identity, 'unknown', None, [])

    def query(self, query: str) -> dict:
        """`bm25_1hop`: BM25 seeds lift their graph neighbours one hop, best first. A record need not hold every
        term, and a record no query term reaches through a seed is never returned."""
        order = sorted((-s, i) for i, s in enumerate(self._one_hop(query)) if s > 0)
        return self._result(query, 'query', None, [self.records[i] for _, i in order[:QUERY_LIMIT]])

    def _one_hop(self, query: str) -> list[float]:
        scores = self._bm25(query)
        combined = list(scores)
        seeds = sorted((-s, i) for i, s in enumerate(scores) if s > 0 and self._neighbours[i])[:SEEDS]
        for negative, u in seeds:
            spread = HOP * -negative / math.sqrt(len(self._neighbours[u]))
            for v in self._neighbours[u]:
                combined[v] += spread * (HOP_ARTICLE if 'body' in self.records[v] else HOP_FACT)
        return combined

    def _bm25(self, query: str) -> list[float]:
        terms = list(dict.fromkeys(terms_of(query)))
        count = len(self._index)
        average = sum(length for _, length in self._index) / count if count else 0.0
        frequency = {t: sum(1 for weights, _ in self._index if t in weights) for t in terms}
        scores = []
        for weights, length in self._index:
            score = 0.0
            for term in terms:
                tf = weights.get(term, 0)
                if tf:
                    idf = math.log(1 + (count - frequency[term] + 0.5) / (frequency[term] + 0.5))
                    score += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * length / average))
            scores.append(score)
        return scores


# Ranked search: BM25 over casefolded word tokens, a title or subject counting three times a body or fact
# word and a lead or tag twice; an underscore or hyphen separates words, so `crafting_recipe` is `crafting` and
# `recipe`. `claim_kind` is not indexed. Standard BM25 constants; no tuning data exists.
# One hop (`bm25_1hop`, #924, measured by #936): the SEEDS best records with a positive score and a neighbour
# each add HOP * score / sqrt(degree) to every neighbour, times HOP_ARTICLE for an article and HOP_FACT for a
# fact, over the undirected graph of claim citations and typed links. Ties keep delivered order. The first
# QUERY_LIMIT are returned: #936 measured the rank-order coverage skip and dropped it, because it removed every
# direct-answer fact that its citing article's prose omits.
QUERY_LIMIT = 10
SEEDS = 10
HOP, HOP_ARTICLE, HOP_FACT = 0.35, 1.25, 0.70
BM25_K1, BM25_B = 1.2, 0.75
_WORD = re.compile(r'[^\W_]+')
_SUFFIXES = (('ies', 'y'), ('ing', ''), ('ed', ''), ('s', ''))


def _fold(word: str) -> str:
    """One regular English inflection removed, the same way for query and record, so `plants` meets `plant`."""
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and not word.endswith('ss') and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)] + replacement
    return word


def terms_of(text: str) -> list[str]:
    return [_fold(w) for w in _WORD.findall(text.casefold())]


def _weighted_terms(record: dict) -> tuple[dict[str, int], int]:
    tags = ' '.join(record['tags'])
    if 'body' in record:
        fields = ((3, record['title']), (2, f"{record['lead']} {tags}"), (1, ' '.join(c['text'] for c in record['body'])))
    else:
        fields = ((3, record.get('subject', '')), (2, tags), (1, record['text']))
    weights: dict[str, int] = {}
    length = 0
    for weight, text in fields:
        for term in terms_of(text):
            weights[term] = weights.get(term, 0) + weight
            length += weight
    return weights, length


def _graph(records: list[dict], position: dict[str, int]) -> list[list[int]]:
    """Undirected neighbours by delivered position: an article and each fact it cites, a record and each link target."""
    neighbours: list[set[int]] = [set() for _ in records]
    for i, record in enumerate(records):
        targets = {position[f] for claim in record.get('body', ()) for f in claim['facts']}
        targets |= {position[link['target']] for link in record['links']}
        targets.discard(i)
        for j in targets:
            neighbours[i].add(j)
            neighbours[j].add(i)
    return [sorted(n) for n in neighbours]
