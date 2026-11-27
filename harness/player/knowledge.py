"""Read only the delivered subset: the frozen file, or a newer version adopted during play. No curator or evaluation dependency."""
from __future__ import annotations

from collections import defaultdict
import copy
import json
import math
from pathlib import Path
import re

from .contracts import PlayerError

SCHEMA = 'delivered-knowledge/4'
RESULT = 'player-knowledge/4'
MAX_SAFE_INT = (1 << 53) - 1
SNIPPET_LIMIT = 240
HIT_CITED_BY_LIMIT = 3
STATUS_MARKERS = ('contested', 'unverified_branch', 'needs_review')
HIT_VIA = frozenset(('match', 'hop', 'fuzzy'))
FIELDS = frozenset(('schema', 'version', 'commit', 'repository_id', 'coverage', 'frame_clocks', 'articles', 'facts', 'history'))
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
CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]')
STATEMENT_KINDS = frozenset(('observation', 'state', 'outcome', 'inference', 'synthesis'))
LIFECYCLE_STATES = frozenset(('active', 'contested'))
BRANCH_RELATIONS = frozenset(('same', 'inherited', 'unknown'))
RELATIONS = frozenset(('depends_on', 'contradicts', 'part_of', 'see_also'))
REASONS = frozenset(('restated', 'narrowed', 'corrected', 'changed'))
READ_BY = ('any', 'id')
EMPTY_HISTORY = {'replaced': {}, 'ended': [], 'retracted': []}


def empty() -> dict:
    return dict(schema=SCHEMA, version=None, commit=None, repository_id=None, coverage=None, frame_clocks={},
                articles=[], facts=[], history=copy.deepcopy(EMPTY_HISTORY))


def _safe_digits(digits: str) -> int | None:
    if len(digits) > 16:
        return None
    number = int(digits)
    return number if 0 <= number <= MAX_SAFE_INT else None


def _safe_nonneg_int(value: object) -> bool:
    if type(value) is int:
        return 0 <= value <= MAX_SAFE_INT
    if isinstance(value, float):
        return math.isfinite(value) and value.is_integer() and 0.0 <= value <= MAX_SAFE_INT and 0 <= int(value) <= MAX_SAFE_INT
    return False


def version_number(version: object) -> int | None:
    """The number N of a published version `vN` within 0..2**53-1, else None."""
    if not isinstance(version, str):
        return None
    match = VERSION.fullmatch(version)
    return _safe_digits(match.group(1)) if match is not None else None


def revision_parts(value: object) -> tuple[str, int] | None:
    """The `(slug, number)` of `<slug>@vM` with `0 <= M <= 2**53-1`, else None."""
    if not isinstance(value, str):
        return None
    match = REVISION.fullmatch(value)
    if match is None:
        return None
    number = _safe_digits(match.group(2))
    return None if number is None else (match.group(1), number)


# The public record forms `tools/knowledge_export.py` writes; `tools/player_host/knowledge.mjs` checks the same ones,
# and both readers are held to the shared fixtures in `tests/fixtures/delivered-knowledge-4/`.
COVERAGE_FIELDS = frozenset(('schema', 'session', 'actor', 'last_step'))
POSITION_REQUIRED = frozenset(('session', 'actor', 'step', 'order'))
POSITION_FIELDS = POSITION_REQUIRED | {'clock_label', 'prior_clock'}
FLAGS = ('needs_review', 'unverified_branch')
SHARED_FIELDS = frozenset(('id', 'tags', 'scope', 'branch_relation', 'lifecycle_state', 'stale_citations', *FLAGS,
                           'links', 'backlinks', 'shadowed_by', 'contradicted_by'))
ARTICLE_FIELDS = SHARED_FIELDS | {'revision', 'title', 'lead', 'body', 'last_confirmed'}
FACT_REQUIRED = SHARED_FIELDS | {'statement_kind', 'text', 'cited_by_articles', 'citation_source_ids', 'seen'}
FACT_FIELDS = FACT_REQUIRED | {'subject', 'when', 'state_key', 'anchor', 'anchor_display', 'depiction_source_id'}
ARTICLE_HIT_REQUIRED = frozenset(('id', 'kind', 'revision', 'title', 'snippet', 'tags', 'via'))
FACT_HIT_REQUIRED = frozenset(('id', 'kind', 'subject', 'statement_kind', 'scope', 'snippet', 'cited_by_articles', 'via'))
FACT_HIT_OPTIONAL = frozenset(('status', 'when', 'state_key', 'anchor', 'anchor_display', 'depiction_source_id'))


def _matches(pattern: re.Pattern, value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _member(value: object, allowed: frozenset[str]) -> bool:
    """A string in `allowed`. The type is checked first, so an unhashable JSON value is refused, never a `TypeError`."""
    return isinstance(value, str) and value in allowed


def _valid_utf8(value: str) -> bool:
    """Reject unpaired UTF-16 surrogates (which JSON `\\uD800` escapes allow but UTF-8 encoding rejects)."""
    return not any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and _valid_utf8(value)


def _clock_label(value: object) -> bool:
    return (_nonblank(value) and 1 <= len(value) <= 64 and CONTROL_CHARS.search(value) is None)


def _prior_clock(value: object) -> bool:
    return (isinstance(value, dict) and set(value) == {'label', 'step_offset'}
            and _clock_label(value['label'])
            and _safe_nonneg_int(value['step_offset']) and int(value['step_offset']) >= 1)


def _identifier(value: str) -> bool:
    return IDENTIFIER.fullmatch(value) is not None


def _historical(value: str) -> bool:
    """A name the public history set can hold: an old fact ID or slug, or an earlier article revision."""
    return IDENTIFIER.fullmatch(value) is not None or revision_parts(value) is not None


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
        and (value['last_step'] is None or _safe_nonneg_int(value['last_step'])))


def _position(value: object) -> bool:
    if not isinstance(value, dict) or not POSITION_REQUIRED <= set(value) <= POSITION_FIELDS:
        return False
    if 'clock_label' in value and 'prior_clock' in value:
        return False
    if 'clock_label' in value and not _clock_label(value['clock_label']):
        return False
    if 'prior_clock' in value and not _prior_clock(value['prior_clock']):
        return False
    return (_matches(ALIAS, value['session']) and _nonblank(value['actor']) and _safe_nonneg_int(value['step'])
            and isinstance(value['order'], list) and len(value['order']) == 3
            and _safe_nonneg_int(value['order'][0]) and _valid_utf8(value['order'][1])
            and _safe_nonneg_int(value['order'][2]))


def _frame_clocks(value: object, cited_sources: set[str] | None = None) -> bool:
    if not isinstance(value, dict):
        return False
    for frame_id, label in value.items():
        if not _matches(SOURCE, frame_id) or not _clock_label(label):
            return False
        if cited_sources is not None and frame_id not in cited_sources:
            return False
    return True


def _tags(value: object) -> bool:
    return _distinct(value, lambda t: len(t) <= 32 and TAG.fullmatch(t) is not None) and len(value) <= 8


def _scope(value: object) -> bool:
    """1..8 axes including `game`; a world-bound record's `world` is delivered as null, and `lineage` is reserved."""
    return (isinstance(value, dict) and 1 <= len(value) <= 8 and 'game' in value
            and all(_matches(AXIS, k) and k != 'lineage' and (v is None if k == 'world' else _matches(ASCII, v))
                    for k, v in value.items()))


def _links(value: object, end: str, owner: str, public, *, delivered_keys=None, own_key: str | None = None) -> bool:
    """Distinct typed links to other records (or `state_key`s for outgoing `depends_on`)."""
    if not isinstance(value, list):
        return False
    pairs = set()
    for link in value:
        if (not isinstance(link, dict) or set(link) != {'rel', end} or not _member(link['rel'], RELATIONS)
                or not isinstance(link[end], str) or link[end] == owner):
            return False
        target = link[end]
        if end == 'target' and link['rel'] == 'depends_on' and delivered_keys is not None:
            if target == own_key:
                return False
            if not (public(target) or delivered_keys(target)):
                return False
        elif not public(target):
            return False
        pairs.add((link['rel'], target))
    return len(pairs) == len(value)


def _record(value: dict, public, history, *, delivered_keys=None) -> bool:
    """The fields articles and facts share, checked against predicates for the public set `P` and the public history
    set `H`. A world-bound record of unknown lineage is always delivered `unverified_branch`."""
    owner = value['id']
    if not _matches(IDENTIFIER, owner):
        return False
    bound = isinstance(value['scope'], dict) and 'world' in value['scope']
    own_key = value.get('state_key') if isinstance(value.get('state_key'), str) else None

    def others(other: str) -> bool:
        return other != owner and public(other)
    return (_tags(value['tags']) and _scope(value['scope'])
            and (_member(value['branch_relation'], BRANCH_RELATIONS) if bound
                 else value['branch_relation'] is None and value['unverified_branch'] is False)
            and _member(value['lifecycle_state'], LIFECYCLE_STATES) and all(type(value[flag]) is bool for flag in FLAGS)
            and (value['branch_relation'] != 'unknown' or value['unverified_branch'] is True)
            and _distinct(value['stale_citations'], history)
            and _links(value['links'], 'target', owner, public, delivered_keys=delivered_keys, own_key=own_key)
            and _links(value['backlinks'], 'source', owner, public)
            and _distinct(value['shadowed_by'], others) and _distinct(value['contradicted_by'], others))


def _article(value: object, facts, public, history, version: int, *, delivered_keys=None) -> bool:
    """An article whose revision `<slug>@vM` is no later than the file's version `vN` (M <= N)."""
    if not isinstance(value, dict) or set(value) != ARTICLE_FIELDS:
        return False
    revision = revision_parts(value['revision'])
    return (revision is not None and revision[0] == value['id'] and revision[1] <= version
            and _nonblank(value['title']) and _nonblank(value['lead']) and _position(value['last_confirmed'])
            and isinstance(value['body'], list) and bool(value['body'])
            and all(isinstance(c, dict) and set(c) == {'text', 'facts'} and _nonblank(c['text'])
                    and _distinct(c['facts'], facts, nonempty=True) for c in value['body'])
            and _record(value, public, history, delivered_keys=delivered_keys))


def _fact(value: object, articles, public, history, *, delivered_keys=None) -> bool:
    if not isinstance(value, dict) or not FACT_REQUIRED <= set(value) <= FACT_FIELDS:
        return False
    bound = isinstance(value['scope'], dict) and 'world' in value['scope']
    kind = value['statement_kind']
    if not _member(kind, STATEMENT_KINDS):
        return False
    if kind == 'state' and (not bound or 'state_key' not in value):
        return False
    if 'state_key' in value:
        if not bound or kind not in ('state', 'synthesis') or not _matches(IDENTIFIER, value['state_key']):
            return False
    if 'anchor' in value:
        if (not bound or not _matches(IDENTIFIER, value['anchor'])
                or value['anchor'] == value.get('state_key')
                or 'anchor_display' not in value or not _nonblank(value['anchor_display'])):
            return False
    elif 'anchor_display' in value:
        return False
    if 'depiction_source_id' in value:
        if not _matches(SOURCE, value['depiction_source_id']):
            return False
        if not isinstance(value['citation_source_ids'], list) or value['depiction_source_id'] not in value['citation_source_ids']:
            return False
    return (_nonblank(value['text']) and ('subject' not in value or _nonblank(value['subject']))
            and ('when' not in value or _nonblank(value['when'])) and _position(value['seen'])
            and _distinct(value['cited_by_articles'], articles)
            and _distinct(value['citation_source_ids'], lambda s: SOURCE.fullmatch(s) is not None, nonempty=True)
            and _record(value, public, history, delivered_keys=delivered_keys))


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
        revision = revision_parts(key)
        if revision is not None:  # An earlier revision of a delivered slug redirects to that slug alone.
            slug, number = revision
            if (entry['reason'] != 'restated' or entry['by'] != [slug] or slug not in articles
                    or slug not in revisions or number >= revisions[slug]):
                return False
        elif not _identifier(key) or not _member(entry['reason'], REASONS) or not set(entry['by']) <= facts:
            return False
    return True


def _classified(records: list[dict], links: set[tuple[str, str, str]]) -> tuple[dict, dict]:
    """`shadowed_by` and `contradicted_by` derived from delivered `contradicts` pairs."""
    by_id = {r['id']: r for r in records}
    shadowed: dict[str, set[str]] = {r['id']: set() for r in records}
    contradicted: dict[str, set[str]] = {r['id']: set() for r in records}
    for pair in {frozenset((source, target)) for source, rel, target in links if rel == 'contradicts'}:
        a, b = (by_id[i] for i in sorted(pair))
        left, right = a['scope'], b['scope']
        if any(left[k] != right[k] for k in left.keys() & right.keys()):
            continue
        general, specific = left.items(), right.items()
        if general < specific:
            shadowed[a['id']].add(b['id'])
        elif specific < general:
            shadowed[b['id']].add(a['id'])
        else:
            contradicted[a['id']].add(b['id'])
            contradicted[b['id']].add(a['id'])
    return shadowed, contradicted


def _derived(articles: list[dict], facts: list[dict]) -> bool:
    """The derived fields agree with what they derive from: `cited_by_articles`, `backlinks` (including expanded
    `state_key` `depends_on` targets), `shadowed_by`, `contradicted_by`, `lifecycle_state`, and inherited
    `unverified_branch` on articles."""
    records = articles + facts
    by_state_key: dict[str, set[str]] = defaultdict(set)
    for f in facts:
        if 'state_key' in f:
            by_state_key[f['state_key']].add(f['id'])
    expected_backlinks: set[tuple[str, str, str]] = set()
    record_links: set[tuple[str, str, str]] = set()
    for r in records:
        for link in r['links']:
            rel, target = link['rel'], link['target']
            if rel == 'depends_on' and target in by_state_key:
                for fid in by_state_key[target]:
                    expected_backlinks.add((r['id'], rel, fid))
            else:
                expected_backlinks.add((r['id'], rel, target))
                record_links.add((r['id'], rel, target))
    if expected_backlinks != {(back['source'], back['rel'], r['id']) for r in records for back in r['backlinks']}:
        return False
    shadowed, contradicted = _classified(records, record_links)
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
        if any(f['unverified_branch'] for f in cited) and a['unverified_branch'] is not True:
            return False
        if any(f['id'] in contested for f in cited):
            contested.add(a['id'])
    if any(set(f['cited_by_articles']) != citing[f['id']] for f in facts):
        return False
    return all(r['lifecycle_state'] == ('contested' if r['id'] in contested else 'active') for r in records)


def status_of(record: dict) -> list[str]:
    """Status markers that hold for a delivered record, in contract order; empty when plainly active."""
    markers = []
    if record['lifecycle_state'] == 'contested':
        markers.append('contested')
    if record['unverified_branch'] is True:
        markers.append('unverified_branch')
    if record['needs_review'] is True:
        markers.append('needs_review')
    return markers


def _valid_status(value: object) -> bool:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        return False
    return value == [marker for marker in STATUS_MARKERS if marker in value]


def _clip_snippet(text: str, limit: int = SNIPPET_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + '…'


def _article_snippet(record: dict, query_terms: set[str]) -> str:
    """Query-matched body claim snippet when a body claim matches strictly more query terms than `lead` (#1023)."""
    lead = record['lead']
    if not query_terms:
        return lead
    best_overlap = len(query_terms & set(terms_of(lead)))
    best_text = lead
    for claim in record['body']:
        overlap = len(query_terms & set(terms_of(claim['text'])))
        if overlap > best_overlap:
            best_overlap = overlap
            best_text = claim['text']
    return best_text


def _hit(record: dict, via: str, *, snippet: str | None = None) -> dict:
    """Compact `player-knowledge/4` query hit for one delivered article or fact."""
    if 'body' in record:
        hit = dict(id=record['id'], kind='article', revision=record['revision'], title=record['title'],
                   snippet=_clip_snippet(snippet if snippet is not None else record['lead']),
                   tags=list(record['tags']), via=via)
    else:
        hit = dict(id=record['id'], kind='fact', subject=record.get('subject'),
                   statement_kind=record['statement_kind'],
                   scope=copy.deepcopy(record['scope']),
                   snippet=_clip_snippet(snippet if snippet is not None else record['text']),
                   cited_by_articles=sorted(set(record['cited_by_articles']))[:HIT_CITED_BY_LIMIT], via=via)
        for field in ('when', 'state_key', 'anchor', 'anchor_display', 'depiction_source_id'):
            if field in record:
                hit[field] = record[field]
    status = status_of(record)
    if status:
        hit['status'] = status
    return hit


def query_hit(value: object, version: object) -> bool:
    """One closed compact `player-knowledge/4` query hit for `version`."""
    number = version_number(version)
    if number is None or not isinstance(value, dict):
        return False
    kind = value.get('kind')
    if kind == 'article':
        if not ARTICLE_HIT_REQUIRED <= set(value) <= (ARTICLE_HIT_REQUIRED | {'status'}):
            return False
        revision = revision_parts(value['revision'])
        return (_matches(IDENTIFIER, value['id']) and revision is not None and revision[0] == value['id']
                and revision[1] <= number and _nonblank(value['title'])
                and _nonblank(value['snippet']) and len(value['snippet']) <= SNIPPET_LIMIT
                and _tags(value['tags']) and _member(value['via'], HIT_VIA)
                and ('status' not in value or _valid_status(value['status'])))
    if kind == 'fact':
        if not FACT_HIT_REQUIRED <= set(value) <= (FACT_HIT_REQUIRED | FACT_HIT_OPTIONAL):
            return False
        bound = isinstance(value['scope'], dict) and 'world' in value['scope']
        sk = value['statement_kind']
        if not _member(sk, STATEMENT_KINDS):
            return False
        if sk == 'state' and (not bound or 'state_key' not in value):
            return False
        if 'state_key' in value and (not bound or sk not in ('state', 'synthesis') or not _matches(IDENTIFIER, value['state_key'])):
            return False
        if 'anchor' in value:
            if (not bound or not _matches(IDENTIFIER, value['anchor'])
                    or value['anchor'] == value.get('state_key')
                    or 'anchor_display' not in value or not _nonblank(value['anchor_display'])):
                return False
        elif 'anchor_display' in value:
            return False
        if 'when' in value and not _nonblank(value['when']):
            return False
        if 'depiction_source_id' in value and not _matches(SOURCE, value['depiction_source_id']):
            return False
        return (_matches(IDENTIFIER, value['id'])
                and (value['subject'] is None or _nonblank(value['subject']))
                and _scope(value['scope'])
                and _nonblank(value['snippet']) and len(value['snippet']) <= SNIPPET_LIMIT
                and _distinct(value['cited_by_articles'], _identifier)
                and value['id'] not in value['cited_by_articles']
                and len(value['cited_by_articles']) <= HIT_CITED_BY_LIMIT
                and value['cited_by_articles'] == sorted(value['cited_by_articles'])
                and _member(value['via'], HIT_VIA)
                and ('status' not in value or _valid_status(value['status']))
                and (bound or 'unverified_branch' not in value.get('status', ())))
    return False


def delivered_record(value: object, version: object) -> bool:
    """One closed delivered article or fact as a read returns it, apart from its file: its closed shape, a blinded
    `world`, aliased positions and a revision no later than `version`. What needs the whole file (public set,
    history, derived fields) was checked when the file was read."""
    number = version_number(version)
    if number is None or not isinstance(value, dict):
        return False
    if 'body' in value:
        return _article(value, _identifier, _identifier, _historical, number, delivered_keys=_identifier)
    return _fact(value, _identifier, _identifier, _historical, delivered_keys=_identifier)


def _valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA:
        return False
    if not all(isinstance(value[name], list) for name in ('articles', 'facts')):
        return False
    # The empty file names no version, commit, repository, coverage, frame_clocks, record or history.
    if value['version'] is None:
        return (value['commit'] is None and value['repository_id'] is None and value['coverage'] is None
                and value['frame_clocks'] == {} and value['articles'] == [] and value['facts'] == []
                and value['history'] == EMPTY_HISTORY)
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
    delivered_keys = {f['state_key'] for f in value['facts'] if isinstance(f.get('state_key'), str)}
    public = articles | facts
    if delivered_keys & public:
        return False
    # Only well-formed revisions enter the map; an article with any other `revision` fails its own check below.
    revisions = {parts[0]: parts[1] for a in value['articles']
                 if (parts := revision_parts(a.get('revision'))) is not None}
    if not _history(value['history'], articles, facts, revisions):
        return False
    history = value['history']
    public_history = set(history['replaced']) | set(history['ended']) | set(history['retracted'])
    if delivered_keys & public_history:
        return False
    cited_sources = {
        src for f in value['facts']
        if isinstance(f.get('citation_source_ids'), list)
        for src in f['citation_source_ids']
        if isinstance(src, str)
    }
    if not _frame_clocks(value['frame_clocks'], cited_sources):
        return False
    number = version_number(value['version'])
    return (all(_article(a, facts, public.__contains__, public_history, number,
                         delivered_keys=delivered_keys.__contains__) for a in value['articles'])
            and all(_fact(f, articles, public.__contains__, public_history,
                          delivered_keys=delivered_keys.__contains__) for f in value['facts'])
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
        self._trigrams = [_record_trigrams(r) for r in self.records]
        self._position = {r['id']: i for i, r in enumerate(self.records)}
        self._revisions = {a['revision']: a for a in value['articles']}
        self._state_keys: dict[str, list[dict]] = defaultdict(list)
        self._state_key_positions: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(self.records):
            if 'body' not in r and 'state_key' in r:
                self._state_keys[r['state_key']].append(r)
                self._state_key_positions[r['state_key']].append(i)
        self._titles: dict[str, dict] = {}
        self._casefolded_titles: dict[str, dict] = {}
        for a in value['articles']:
            self._titles.setdefault(a['title'], a)
            self._casefolded_titles.setdefault(a['title'].casefold(), a)
        self._neighbours = _graph(self.records, self._position, self._state_key_positions)

    def _result(self, identity: str, resolution: str, resolved_from: str | None, records: list[dict]) -> dict:
        return dict(schema=RESULT, version=self.value['version'], grants_authority=False, identity=identity,
                    resolution=resolution, resolved_from=resolved_from, records=copy.deepcopy(records))

    def _query_result(self, query: str, hits: list[dict]) -> dict:
        return dict(schema=RESULT, version=self.value['version'], grants_authority=False, identity=query,
                    resolution='query', resolved_from=None, hits=hits)

    def read(self, identity: str, *, by: str = 'any') -> dict:
        """One delivered record, where an old identifier went, or all current readings for a `state_key`."""
        if by not in READ_BY:
            raise PlayerError('Knowledge read `by` must be "any" or "id"')
        history = self.value['history']
        if identity in self._position:
            return self._result(identity, 'current', None, [self.records[self._position[identity]]])
        if identity in self._revisions:
            return self._result(identity, 'revision', identity, [self._revisions[identity]])
        if identity in history['replaced']:
            entry = history['replaced'][identity]
            revision = revision_parts(identity)
            resolution = 'revision' if revision is not None else entry['reason']
            return self._result(identity, resolution, identity,
                                [self.records[self._position[rid]] for rid in entry['by']])
        for resolution in ('ended', 'retracted'):
            if identity in history[resolution]:
                return self._result(identity, resolution, identity, [])
        if identity in self._state_keys:
            return self._result(identity, 'state_key', None, self._state_keys[identity])
        if by == 'any':
            if identity in self._titles:
                return self._result(identity, 'title', None, [self._titles[identity]])
            folded = identity.casefold()
            if folded in self._casefolded_titles:
                return self._result(identity, 'title', None, [self._casefolded_titles[folded]])
        return self._result(identity, 'unknown', None, [])

    def query(self, query: str) -> dict:
        """`bm25_1hop` with deterministic pre-read shadow filtering (preserving current `contested`) and
        zero-hit-only char-trigram fallback (`via: "fuzzy"`)."""
        scores = self._bm25(query)
        combined = self._one_hop(query, scores)
        order = sorted(
            (-s, i) for i, s in enumerate(combined)
            if s > 0 and not self.records[i]['shadowed_by']
        )
        if order:
            query_terms = set(terms_of(query))
            hits = [
                _hit(
                    self.records[i],
                    'match' if scores[i] > 0 else 'hop',
                    snippet=_article_snippet(self.records[i], query_terms) if 'body' in self.records[i] else None,
                )
                for _, i in order[:QUERY_LIMIT]
            ]
            return self._query_result(query, hits)
        q_tri = _trigrams(query)
        if not q_tri:
            return self._query_result(query, [])
        fuzzy = []
        for i, rec_tri in enumerate(self._trigrams):
            if self.records[i]['shadowed_by'] or not rec_tri:
                continue
            union = len(q_tri | rec_tri)
            sim = len(q_tri & rec_tri) / union if union else 0.0
            if sim >= FUZZY_THRESHOLD:
                fuzzy.append((-sim, i))
        fuzzy.sort()
        hits = [_hit(self.records[i], 'fuzzy') for _, i in fuzzy[:QUERY_LIMIT]]
        return self._query_result(query, hits)

    def _one_hop(self, query: str, scores: list[float] | None = None) -> list[float]:
        if scores is None:
            scores = self._bm25(query)
        combined = list(scores)
        seeds = sorted(
            (-s, i) for i, s in enumerate(scores)
            if s > 0 and self._neighbours[i] and not self.records[i]['shadowed_by']
        )[:SEEDS]
        for negative, u in seeds:
            spread = HOP * -negative / math.sqrt(len(self._neighbours[u]))
            for v in self._neighbours[u]:
                if not self.records[v]['shadowed_by']:
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


# Ranked search: BM25 over casefolded word tokens, a title or subject counting three times a body, fact or `when`
# word and a lead, tag or resolved `anchor_display` twice. `id`, `state_key`, `statement_kind`, and `clock_label`
# remain display-only. One hop (`bm25_1hop`, #924, #936, #1023) walks claim citations and non-`contradicts` links
# (resolving `depends_on` `state_key` targets to current readings). Zero-hit queries fall back to char-trigram
# similarity (`via: "fuzzy"`).
QUERY_LIMIT = 10
SEEDS = 10
HOP, HOP_ARTICLE, HOP_FACT = 0.35, 1.25, 0.70
BM25_K1, BM25_B = 1.2, 0.75
FUZZY_THRESHOLD = 0.15
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


def _trigrams(text: str) -> set[str]:
    compact = ' '.join(_WORD.findall(text.casefold()))
    if len(compact) < 3:
        return {compact} if compact else set()
    return {compact[i:i + 3] for i in range(len(compact) - 2)}


def _record_trigrams(record: dict) -> set[str]:
    tags = ' '.join(record['tags'])
    if 'body' in record:
        surface = f"{record['title']} {record['lead']} {tags} {' '.join(c['text'] for c in record['body'])}"
    else:
        surface = f"{record.get('subject', '')} {record.get('anchor_display', '')} {tags} {record['text']} {record.get('when', '')}"
    return _trigrams(surface)


def _weighted_terms(record: dict) -> tuple[dict[str, int], int]:
    tags = ' '.join(record['tags'])
    if 'body' in record:
        fields = ((3, record['title']), (2, f"{record['lead']} {tags}"), (1, ' '.join(c['text'] for c in record['body'])))
    else:
        fields = (
            (3, record.get('subject', '')),
            (2, f"{tags} {record.get('anchor_display', '')}"),
            (1, f"{record['text']} {record.get('when', '')}"),
        )
    weights: dict[str, int] = {}
    length = 0
    for weight, text in fields:
        for term in terms_of(text):
            weights[term] = weights.get(term, 0) + weight
            length += weight
    return weights, length


def _graph(records: list[dict], position: dict[str, int],
           state_key_positions: dict[str, list[int]] | None = None) -> list[list[int]]:
    """Undirected neighbours by delivered position: claim citations and non-`contradicts` links (expanding
    `depends_on` `state_key` targets to every delivered reading carrying that key)."""
    neighbours: list[set[int]] = [set() for _ in records]
    key_pos = state_key_positions or {}
    for i, record in enumerate(records):
        targets = {position[f] for claim in record.get('body', ()) for f in claim['facts']}
        for link in record['links']:
            if link['rel'] == 'contradicts':
                continue
            target = link['target']
            if link['rel'] == 'depends_on' and target in key_pos:
                targets.update(key_pos[target])
            elif target in position:
                targets.add(position[target])
        targets.discard(i)
        for j in targets:
            neighbours[i].add(j)
            neighbours[j].add(i)
    return [sorted(n) for n in neighbours]
