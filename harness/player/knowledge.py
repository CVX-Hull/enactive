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
REVISION = re.compile(r'([a-z0-9][a-z0-9-]{0,63})@v(0|[1-9][0-9]*)\Z')
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


def _member(value: object, allowed: frozenset[str]) -> bool:
    """A string in `allowed`. The type is checked first, so an unhashable JSON value is refused, never a `TypeError`."""
    return isinstance(value, str) and value in allowed


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _identifier(value: str) -> bool:
    return IDENTIFIER.fullmatch(value) is not None


def _historical(value: str) -> bool:
    """A name the public history set can hold: an old fact ID or slug, or an earlier article revision."""
    return IDENTIFIER.fullmatch(value) is not None or REVISION.fullmatch(value) is not None


def _distinct(value: object, allowed=None, *, nonempty: bool = False) -> bool:
    """A list of distinct strings, each in `allowed` when given (a set, or a predicate). Strings are checked before
    the set is built, so an unhashable member is refused, never a `TypeError`."""
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


def _links(value: object, end: str, owner: str, public) -> bool:
    """Distinct typed links to other records, each end passing the predicate `public`."""
    if not isinstance(value, list):
        return False
    pairs = set()
    for link in value:
        if (not isinstance(link, dict) or set(link) != {'rel', end} or not _member(link['rel'], RELATIONS)
                or not isinstance(link[end], str) or link[end] == owner or not public(link[end])):
            return False
        pairs.add((link['rel'], link[end]))
    return len(pairs) == len(value)


def _record(value: dict, public, history) -> bool:
    """The fields articles and facts share, checked against predicates for the public set `P` and the public history
    set `H`. A world-bound record of unknown lineage is always delivered `unverified_branch`."""
    owner = value['id']
    if not _matches(IDENTIFIER, owner):
        return False
    bound = isinstance(value['scope'], dict) and 'world' in value['scope']

    def others(other: str) -> bool:
        return other != owner and public(other)
    return (_tags(value['tags']) and _scope(value['scope'])
            and (_member(value['branch_relation'], BRANCH_RELATIONS) if bound
                 else value['branch_relation'] is None and value['unverified_branch'] is False)
            and _member(value['lifecycle_state'], LIFECYCLE_STATES) and all(type(value[flag]) is bool for flag in FLAGS)
            and (value['branch_relation'] != 'unknown' or value['unverified_branch'] is True)
            and _distinct(value['stale_citations'], history)
            and _links(value['links'], 'target', owner, public) and _links(value['backlinks'], 'source', owner, public)
            and _distinct(value['shadowed_by'], others) and _distinct(value['contradicted_by'], others))


def _article(value: object, facts, public, history, version: int) -> bool:
    """An article whose revision `<slug>@vM` is no later than the file's version `vN` (M <= N)."""
    if not isinstance(value, dict) or set(value) != ARTICLE_FIELDS:
        return False
    revision = REVISION.fullmatch(value['revision']) if isinstance(value['revision'], str) else None
    return (revision is not None and revision.group(1) == value['id'] and int(revision.group(2)) <= version
            and _nonblank(value['title']) and _nonblank(value['lead']) and _position(value['last_confirmed'])
            and isinstance(value['body'], list) and bool(value['body'])
            and all(isinstance(c, dict) and set(c) == {'text', 'facts'} and _nonblank(c['text'])
                    and _distinct(c['facts'], facts, nonempty=True) for c in value['body'])
            and _record(value, public, history))


def _fact(value: object, articles, public, history) -> bool:
    if not isinstance(value, dict) or not FACT_REQUIRED <= set(value) <= FACT_FIELDS:
        return False
    bound = isinstance(value['scope'], dict) and 'world' in value['scope']
    return (_member(value['claim_kind'], CLAIM_KINDS) and _member(value['evidence_basis'], EVIDENCE_BASES)
            and (value['claim_kind'] != 'instance_state' or bound)
            and _nonblank(value['text']) and ('subject' not in value or _nonblank(value['subject']))
            and ('when' not in value or _when(value['when'])) and _position(value['seen'])
            and _distinct(value['cited_by_articles'], articles)
            and _distinct(value['citation_source_ids'], lambda s: SOURCE.fullmatch(s) is not None, nonempty=True)
            and _record(value, public, history))


def _history(value: object, articles: set[str], facts: set[str], revisions: dict[str, int]) -> bool:
    """Old identifiers name only public replacements; `ended` and `retracted` name fact IDs and retired slugs. An
    earlier revision `<slug>@vK` is strictly earlier than the delivered `<slug>@vM` (K < M); `revisions` maps each
    delivered slug to M."""
    if not isinstance(value, dict) or set(value) != set(EMPTY_HISTORY):
        return False
    replaced, ended, retracted = value['replaced'], value['ended'], value['retracted']
    public = articles | facts
    if not isinstance(replaced, dict) or not _distinct(ended, _identifier) or not _distinct(retracted, _identifier):
        return False
    gone = set(ended) | set(retracted)
    if set(ended) & set(retracted) or gone & public:
        return False
    for key, entry in replaced.items():
        if (not isinstance(key, str) or key in public or key in gone or not isinstance(entry, dict)
                or set(entry) != {'reason', 'by'} or not _distinct(entry['by'], nonempty=True)):
            return False
        revision = REVISION.fullmatch(key)
        if revision is not None:  # An earlier revision of a delivered slug redirects to that slug alone.
            slug = revision.group(1)
            if (entry['reason'] != 'restated' or entry['by'] != [slug] or slug not in articles
                    or slug not in revisions or int(revision.group(2)) >= revisions[slug]):
                return False
        elif not _identifier(key) or not _member(entry['reason'], REASONS) or not set(entry['by']) <= facts:
            return False
    return True


def _constraint(record: dict) -> dict:
    """A record's `scope` joined with its `when.requires`. Delivered world-bound records all hold `world: null`, so
    two of them agree on `world`: they are bound to the one world being played."""
    return {**record['scope'], **record.get('when', {}).get('requires', {})}


def _classified(records: list[dict], links: set[tuple[str, str, str]]) -> tuple[dict, dict]:
    """`shadowed_by` and `contradicted_by` as the scoping contract's table derives them from the delivered
    `contradicts` pairs: disjoint constraints neither shadow nor conflict; compatible constraints with comparable,
    unequal scopes let the specific record shadow the general one; equal or incomparable scopes conflict."""
    by_id = {r['id']: r for r in records}
    shadowed: dict[str, set[str]] = {r['id']: set() for r in records}
    contradicted: dict[str, set[str]] = {r['id']: set() for r in records}
    for pair in {frozenset((source, target)) for source, rel, target in links if rel == 'contradicts'}:
        a, b = (by_id[i] for i in sorted(pair))
        left, right = _constraint(a), _constraint(b)
        if any(left[k] != right[k] for k in left.keys() & right.keys()):
            continue
        general, specific = a['scope'].items(), b['scope'].items()
        if general < specific:
            shadowed[a['id']].add(b['id'])
        elif specific < general:
            shadowed[b['id']].add(a['id'])
        else:
            contradicted[a['id']].add(b['id'])
            contradicted[b['id']].add(a['id'])
    return shadowed, contradicted


def _derived(articles: list[dict], facts: list[dict]) -> bool:
    """The derived fields agree with what they derive from: `cited_by_articles` with citations, `backlinks` with
    `links`, `shadowed_by`, `contradicted_by` and `lifecycle_state` with the classified `contradicts` pairs, and an
    article's inherited flags with the facts it cites (an article is no more certain than its facts, and citing a
    contested fact makes it contested)."""
    records = articles + facts
    links = {(r['id'], link['rel'], link['target']) for r in records for link in r['links']}
    if links != {(back['source'], back['rel'], r['id']) for r in records for back in r['backlinks']}:
        return False
    shadowed, contradicted = _classified(records, links)
    if any(set(r['shadowed_by']) != shadowed[r['id']] or set(r['contradicted_by']) != contradicted[r['id']]
           for r in records):
        return False
    by_id = {f['id']: f for f in facts}
    contested = {r['id'] for r in records if contradicted[r['id']]}
    citing: dict[str, set[str]] = {f['id']: set() for f in facts}
    for a in articles:
        cited = [by_id[f] for claim in a['body'] for f in claim['facts']]
        for f in cited:
            citing[f['id']].add(a['id'])
        if (a['condition_unverified'] is not any(f['condition_unverified'] for f in cited)
                or (any(f['unverified_branch'] for f in cited) and a['unverified_branch'] is not True)):
            return False
        if any(f['id'] in contested for f in cited):
            contested.add(a['id'])
    if any(set(f['cited_by_articles']) != citing[f['id']] for f in facts):
        return False
    return all(r['lifecycle_state'] == ('contested' if r['id'] in contested else 'active') for r in records)


def delivered_record(value: object, version: object) -> bool:
    """One closed delivered article or fact as a read returns it, apart from its file: its closed shape, a blinded
    `world`, aliased positions and a revision no later than `version`. What needs the whole file (public set,
    history, derived fields) was checked when the file was read."""
    number = version_number(version)
    if number is None or not isinstance(value, dict):
        return False
    if 'body' in value:
        return _article(value, _identifier, _identifier, _historical, number)
    return _fact(value, _identifier, _identifier, _historical)


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
    # Only well-formed revisions enter the map; an article with any other `revision` fails its own check below.
    revisions = {m.group(1): int(m.group(2)) for a in value['articles']
                 if isinstance(a.get('revision'), str) and (m := REVISION.fullmatch(a['revision'])) is not None}
    if not _history(value['history'], articles, facts, revisions):
        return False
    history = value['history']
    public_history = set(history['replaced']) | set(history['ended']) | set(history['retracted'])
    public = articles | facts
    number = version_number(value['version'])
    return (all(_article(a, facts, public.__contains__, public_history, number) for a in value['articles'])
            and all(_fact(f, articles, public.__contains__, public_history) for f in value['facts'])
            and _derived(value['articles'], value['facts']))


class Knowledge:
    """One delivered version. Never changed after it is read; a newer version is another object."""

    def __init__(self, path: Path):
        self._set(json.loads(path.read_text()), str(path))

    @classmethod
    def from_dict(cls, value: object, where: str = 'delivered knowledge') -> 'Knowledge':
        knowledge = cls.__new__(cls)
        # A private copy: the caller changing its dict later cannot alter this version or part it from its index.
        knowledge._set(copy.deepcopy(value), where)
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
