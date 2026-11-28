"""Read-only browser over the knowledge versions exported for a run's player.

It reads only files of the run's own package, without following a symlink: the version the run started with
(`delivered-knowledge.json`, shown as `initial`) and the versions exported during play (`curator-runner/delivered/vN.json`).
No curator repository, private export, alias map or withheld-unit file is read, and nothing is written. An exported
version is not thereby a delivered one: only the host trace says what reached the player.

The format is blinded: a world-bound record's scope holds `world: null`, never the label, and positions name opaque
session aliases (`s01`); a session that is no alias is withheld. So a record's scope is shown as its class (`world` or
`game`) with its other axes, and its anchor comes from the frames it cites: a `citation_source_ids` entry of this run's
session resolves through the catalog and the same verification as the frame route.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import threading

from .catalog import ID_LIMIT, Catalog, RunInfo, ViewError
from .curator import read_rooted, rooted_entries, rooted_status
from .knowledge import (
    CURRENT_SNAPSHOT, SOURCE, STATE_KEY, add_fact_fields, add_ids, citations, delivered_shape, fields, frame_clocks, history,
    manifest_schema_for, marker, record, scope_class, snapshot_schemas,
)
from .telemetry import HostProjection, Steps, identifier, read
from . import frame

SCHEMA = CURRENT_SNAPSHOT[1]
INITIAL = 'initial'
STARTING = ('delivered-knowledge.json',)
EXPORTS = ('curator-runner', 'delivered')
VERSION_FILE = re.compile(r'v(0|[1-9][0-9]{0,8})\.json')
#: `unrecorded` lists the facts that state no scope, the ones `scope_counts` counts as such.
SCOPES = ('all', 'world', 'game', 'unrecorded')
MAX_VERSIONS = 500
MAX_VERSION_DELIVERIES = 8
GROUP_BYTES = 384 * 1024
MAX_ARTICLES = 200
BODY_LIMIT = 50
QUERY_LIMIT = 200
#: The tag summary keeps the most used tags.
TAG_LIMIT = 200
KIND_LIMIT = 20
#: A listing keeps its text under the response ceiling; what does not fit is counted as omitted.
TEXT_BYTES = 1024 * 1024
KIND = re.compile(rf'[A-Za-z0-9_-]{{1,{ID_LIMIT}}}')
VERSION = re.compile(r'v(0|[1-9][0-9]{0,8})')
DEFAULT_LIMIT = 100

_lock = threading.Lock()
_cache: dict[tuple, tuple[tuple, tuple[str, dict | None]]] = {}
CACHED_FILES = 128
#: A file of the run package, as the components of its path.
Parts = tuple[str, ...]


def load(run_dir: Path, parts: Parts, knowledge_schema: str | None) -> tuple[str, dict | None]:
    """(`available`, the document) or (why not, None), once per state of the file."""
    status = rooted_status(run_dir, *parts)
    if status is None:
        return 'missing', None
    if knowledge_schema is None:
        return 'unsupported', None
    stamp = (status.st_mode, status.st_ino, status.st_mtime_ns, status.st_size)
    key = (run_dir, parts, knowledge_schema)
    with _lock:
        cached = _cache.get(key)
        if cached is not None and cached[0] == stamp:
            return cached[1]
    state, _, data = read_rooted(run_dir, *parts)
    document = None
    if state == 'available':
        try:
            document = json.loads(data.decode('utf-8'))
        except (ValueError, UnicodeError, RecursionError):
            state = 'malformed'
        else:
            if not delivered_shape(document, knowledge_schema):
                state, document = 'unsupported', None
    with _lock:
        _cache.pop(key, None)
        _cache[key] = (stamp, (state, document))
        while len(_cache) > CACHED_FILES:
            _cache.pop(next(iter(_cache)))
    return state, document


def version_files(run_dir: Path) -> list[tuple[str, Parts]]:
    """(version name, file), the starting version first and then the exported ones by number. A symlink is listed, and
    then found unreadable."""
    found: list[tuple[int, Parts]] = []
    try:
        for name, _ in rooted_entries(run_dir, *EXPORTS):
            match = VERSION_FILE.fullmatch(name)
            if match:
                found.append((int(match[1]), (*EXPORTS, name)))
    except OSError:
        pass
    rows = [(f'v{number}', parts) for number, parts in sorted(found)[-MAX_VERSIONS:]]
    return ([(INITIAL, STARTING)] if rooted_status(run_dir, *STARTING) is not None else []) + rows


def version_row(name: str, run_dir: Path, parts: Parts, knowledge_schema: str | None) -> dict:
    state, document = load(run_dir, parts, knowledge_schema)
    if document is None:
        return dict(version=name, status=state, recorded_version=None, articles_count=None, facts_count=None, coverage=None)
    return dict(version=name, status=state, recorded_version=identifier(document.get('version')),
        articles_count=len(document['articles']), facts_count=len(document['facts']),
        coverage=marker(document.get('coverage'), blinded=True))


class Anchors:
    """A citation uses its real catalog admission and the frame route's verification."""

    def __init__(self, catalog: Catalog, info: RunInfo, connection: sqlite3.Connection, facts: list) -> None:
        self.catalog, self.info, self.connection = catalog, info, connection
        self.runs = catalog.runs()
        self.by_session = {r.session: r for r in self.runs}
        self.facts = {f['id']: f for f in facts if isinstance(f, dict) and isinstance(f.get('id'), str)}
        self.locations: dict[str, dict | None] = {}

    def step(self, source_id: str) -> dict | None:
        if source_id not in self.locations:
            owner = self.by_session.get(source_id.rpartition('-')[0])
            if owner is None:
                value = None
            elif owner.session == self.info.session:
                found = frame.source_location(self.catalog, self.runs, owner, source_id, self.connection)
                value = dict(seq=found['seq'], source_id=source_id) if found['available'] else None
            else:
                value = frame.source_location(self.catalog, self.runs, owner, source_id)
            self.locations[source_id] = value
        return self.locations[source_id]

    def latest(self, source_ids: list[str]) -> dict | None:
        found = [location for source in dict.fromkeys(source_ids) if (location := self.step(source)) is not None]
        own = [location for location in found if 'run' not in location]
        if own:
            return max(own, key=lambda item: item['seq'])
        other = [location for location in found if location['available']]
        return (other or found or [None])[-1]

    def article(self, article: dict) -> dict | None:
        body = article.get('body') if isinstance(article.get('body'), list) else []
        cited = [f for part in body if isinstance(part, dict) and isinstance(part.get('facts'), list) for f in part['facts']]
        return self.latest([s for f in cited if isinstance(f, str) and f in self.facts
                            for s in citations(self.facts[f].get('citation_source_ids'), None)])


def contains(query: str, *values: object) -> bool:
    return not query or any(isinstance(v, str) and query in v.casefold() for v in values)


def tags_of(value: dict) -> list:
    return value['tags'] if isinstance(value.get('tags'), list) else []


def article_text(article: dict) -> list:
    body = article.get('body') if isinstance(article.get('body'), list) else []
    return [article.get('id'), article.get('title'), article.get('lead'), *tags_of(article),
            *(p.get('text') for p in body if isinstance(p, dict))]


def fact_text(fact: dict, current: bool) -> list:
    common = [fact.get('id'), fact.get('subject'), fact.get('text'), *tags_of(fact)]
    if current:
        return [*common, fact.get('statement_kind'), fact.get('anchor_display'), fact.get('when')]
    return [*common, fact.get('claim_kind')]


def article_row(article: dict, anchors: Anchors, current: bool) -> dict:
    out = dict(dict.fromkeys(('id', 'revision', 'title', 'lead')), **fields(article, ('id', 'revision', 'title', 'lead')))
    body = article.get('body') if isinstance(article.get('body'), list) else []
    out['body'] = []
    for part in body[:BODY_LIMIT]:
        if isinstance(part, dict):
            row = fields(part, ('text',))
            add_ids(row, 'facts', part.get('facts'))
            out['body'].append(row)
    out['body_omitted'] = len(body) - len(out['body'])
    record(out, article, legacy=not current)
    out['last_confirmed'] = marker(article.get('last_confirmed'), blinded=True, clocks=current)
    out['anchor'] = anchors.article(article)
    return out


def fact_row(fact: dict, anchors: Anchors, current: bool) -> dict:
    names = ('id', 'subject', 'text')
    out = dict(dict.fromkeys(names), **fields(fact, names))
    record(out, fact, legacy=not current)
    add_fact_fields(out, fact, current)
    add_ids(out, 'cited_by_articles', fact.get('cited_by_articles'))
    add_ids(out, 'citation_source_ids', fact.get('citation_source_ids'), pattern=SOURCE)
    out['citation_anchors'] = [anchors.step(s) for s in out['citation_source_ids']]
    out['seen'] = marker(fact.get('seen'), blinded=True, clocks=current)
    out['frame_anchor' if current else 'anchor'] = anchors.latest(citations(fact.get('citation_source_ids'), None))
    return out


def summary(document: dict, kind_field: str) -> tuple[list[dict], int, dict]:
    """The tag view counted from the delivered records (most used first), how many tags it leaves out, and the facts
    counted by their kind."""
    records = [r for r in document['articles'] + document['facts'] if isinstance(r, dict)]
    tags = Counter(t for r in records for t in {t for t in tags_of(r) if isinstance(t, str) and len(t) <= ID_LIMIT})
    ranked = sorted(tags.items(), key=lambda item: (-item[1], item[0]))
    kinds = Counter(f[kind_field] for f in document['facts'] if isinstance(f, dict)
                    and isinstance(f.get(kind_field), str) and len(f[kind_field]) <= ID_LIMIT)
    return ([dict(tag=t, count=n) for t, n in ranked[:TAG_LIMIT]], max(0, len(ranked) - TAG_LIMIT),
            dict(sorted(kinds.items())[:KIND_LIMIT]))


def bounded(rows: list[dict], byte_limit=TEXT_BYTES) -> tuple[list[dict], int]:
    """The rows that fit the listing's text bound, and how many were left out."""
    size = 0
    for index, row in enumerate(rows):
        size += len(json.dumps(row, separators=(',', ':'), default=str))
        if size > byte_limit and index:
            return rows[:index], len(rows) - index
    return rows, 0


def _delivery(mark, steps):
    near = steps.nearest(mark.wall)
    fields = mark.fields
    return dict(actor=mark.actor, seq=None if near is None else near.seq, **{key: fields[key] for key in
        ('kind', 'delivery_kind', 'outcome', 'request_id', 'knowledge_version', 'previous_version', 'delta_counts',
         'delta_preview', 'leads_count', 'index_count', 'summary')})


def _delivered(item):
    return item['outcome'] == 'delivered'


def delivery_for(deliveries):
    """Prefer a recorded delivery, then the latest explicit refusal, suppression or undelivered entry."""
    return (next((item for item in deliveries if _delivered(item)), None)
            or next((item for item in reversed(deliveries) if item['delivery_kind'] in
                     ('refused', 'empty_suppressed', 'undelivered')), None))


def _published(run_dir):
    status, _, contents = read_rooted(run_dir, 'curator-runner', 'versions.jsonl')
    if status != 'available':
        return {}
    versions = {}
    for line in contents.split(b'\n')[:-1]:
        if len(line) > 64 * 1024:
            continue
        try:
            row = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if (isinstance(row, dict) and row.get('schema') == 'curator-runner-version/1'
                and isinstance(row.get('version'), str) and VERSION.fullmatch(row['version'])):
            versions[row['version']] = row
    return versions


def _version_order(name):
    return -1 if name == INITIAL else int(name[1:])


def version_chain(run_dir, exports, host: HostProjection | None, steps):
    published = _published(run_dir)
    files = {row['version']: row for row in exports}
    initial = files.get(INITIAL, {}).get('recorded_version')
    by_version = {}
    superseded = set()
    for mark in host.deliveries if host is not None else ():
        item = _delivery(mark, steps)
        version = item['knowledge_version']
        name = version if isinstance(version, str) and VERSION.fullmatch(version) else None
        if name and (_delivered(item) or item['delivery_kind'] == 'empty_suppressed'):
            superseded.add(item['previous_version'])
        if name:
            by_version.setdefault(name, []).append(item)
        if (INITIAL in files and version == initial and item['kind'] == 'briefing'
                and item['delivery_kind'] != 'post_cut_briefing'):
            by_version.setdefault(INITIAL, []).append(item)
    names = sorted(set(files) | set(published) | set(by_version), key=_version_order)
    if len(names) > MAX_VERSIONS + 1:
        names = ([INITIAL] if INITIAL in names else []) + names[-MAX_VERSIONS:]
    rows = []
    for name in names:
        exported = name in files
        version = files.get(name, {}).get('recorded_version') if name == INITIAL else name
        publication = published.get(version, {})
        base = files.get(name, dict(version=name, status='missing', recorded_version=version,
                                    articles_count=None, facts_count=None, coverage=None))
        shown = by_version.get(name, [])
        kinds = {item['delivery_kind'] for item in shown}
        if any(_delivered(item) for item in shown):
            delivery_status = 'delivered'
        elif 'refused' in kinds:
            delivery_status = 'refused'
        elif 'empty_suppressed' in kinds:
            delivery_status = 'empty_suppressed'
        elif 'undelivered' in kinds:
            delivery_status = 'undelivered'
        elif version is not None and version in superseded:
            delivery_status = 'superseded'
        elif exported:
            delivery_status = 'exported_not_delivered'
        elif version in published:
            delivery_status = 'published_only'
        else:
            delivery_status = 'trace_only'
        # Keep a delivered example even when later repeats fill the window.
        sample = shown[-MAX_VERSION_DELIVERIES:]
        confirmed = next((item for item in shown if _delivered(item)), None)
        if confirmed is not None and confirmed not in sample:
            sample = [confirmed, *sample[1:]]
        rows.append(dict(base, coverage=base['coverage'] or marker(publication.get('coverage'), blinded=True),
            published=version in published, baseline=publication.get('baseline') if type(publication.get('baseline')) is bool else None,
            exported=exported, delivery_status=delivery_status,
            deliveries=[{k: x[k] for k in ('delivery_kind', 'outcome', 'actor', 'request_id', 'seq', 'summary')} for x in sample],
            deliveries_omitted=len(shown) - len(sample)))
    return rows, by_version


def _quality(document):
    articles = [row for row in document['articles'] if isinstance(row, dict)]
    facts = [row for row in document['facts'] if isinstance(row, dict)]
    combined = articles + facts
    state_count = len({key for row in facts if isinstance(key := row.get('state_key'), str) and STATE_KEY.fullmatch(key)})
    when = sum(isinstance(row.get('when'), str) and bool(row['when'].strip()) for row in facts)
    return dict(articles_count=len(articles), facts_count=len(facts), state_count=state_count, when_count=when,
        when_coverage=when / len(facts) if facts else None,
        stale_count=sum(bool(row.get('stale_citations')) for row in combined),
        contested_count=sum(row.get('lifecycle_state') == 'contested' for row in combined),
        unverified_count=sum(row.get('unverified_branch') is True for row in combined),
        needs_review_count=sum(row.get('needs_review') is True for row in combined),
        default_view='articles' if articles else 'state' if state_count else 'facts')


def _groups(facts, window, replaced):
    states, locations = {}, {}
    for fact in facts:
        state = fact.get('state_key')
        anchor = fact.get('anchor')
        if isinstance(state, str) and STATE_KEY.fullmatch(state):
            states.setdefault(state, []).append(fact.get('id'))
        if isinstance(anchor, str) and STATE_KEY.fullmatch(anchor):
            group = locations.setdefault(anchor, dict(anchor=anchor, anchor_display=None, fact_count=0, state_keys=[]))
            display = fact.get('anchor_display')
            if group['anchor_display'] is None and isinstance(display, str):
                group['anchor_display'] = display[:256]
            group['fact_count'] += 1
            if isinstance(state, str) and STATE_KEY.fullmatch(state) and state not in group['state_keys'] and len(group['state_keys']) < 100:
                group['state_keys'].append(state)
    shown = {}
    for fact in window:
        state = fact.get('state_key')
        if state in states:
            row = {key: fact.get(key) for key in ('id', 'subject', 'text', 'statement_kind', 'when',
                   'anchor', 'anchor_display', 'frame_anchor')}
            shown.setdefault(state, []).append(row)
    groups = []
    for state, rows in shown.items():
        ids = {k for k in states[state] if isinstance(k, str)}
        matches = {k: v for k, v in replaced.items() if k == state or k.split('@')[0] in ids
                   or not ids.isdisjoint(v['by']) or state in v['by']}
        groups.append(dict(state_key=state, facts=rows, replaced=matches,
                           count=len(states[state]), facts_omitted=len(states[state]) - len(rows)))
    return bounded(groups, GROUP_BYTES)[0], bounded(list(locations.values())[:100], GROUP_BYTES)[0]


def browse(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection, version: str | None, query: str | None,
           scope: str | None, after: int = 0, limit: int = DEFAULT_LIMIT, *, kind: str | None = None) -> dict:
    scope = scope or 'all'
    if scope not in SCOPES:
        raise ViewError(400, 'bad_scope', 'scope must be all, world, game or unrecorded')
    if query is not None and len(query) > QUERY_LIMIT:
        raise ViewError(400, 'bad_q', f'q must be at most {QUERY_LIMIT} characters')
    if kind is not None and not KIND.fullmatch(kind):
        raise ViewError(400, 'bad_kind')
    files = [] if info.run_dir is None else version_files(info.run_dir)
    if version is not None and version != INITIAL and (len(version) > ID_LIMIT or not VERSION.fullmatch(version)):
        raise ViewError(404, 'unknown_version')
    empty = dict(source_status='unavailable', versions=[], version_chain=[], selected_version=None, recorded_version=None,
        coverage=None, delivery=None, articles=[], articles_total=0, articles_omitted=0, state_groups=[], anchor_groups=[],
        quality=_quality(dict(articles=[], facts=[])), scope_recorded=False,
        scope_counts=dict(world=0, game=0, unrecorded=0), tag_counts=[], tag_counts_omitted=0, statement_kind_counts={},
        facts=dict(items=[], total=0, next=None, limit=limit))
    if info.run_dir is None:
        if version is not None:
            raise ViewError(404, 'unknown_version')
        return empty
    _, knowledge_schema = snapshot_schemas(manifest_schema_for(info.run_dir, info.session))
    rows = [version_row(name, info.run_dir, parts, knowledge_schema) for name, parts in files]
    host = read(info)
    chain, deliveries = version_chain(info.run_dir, rows, host, Steps(connection))
    if version is not None and version not in dict(files) and not any(row['version'] == version for row in chain):
        raise ViewError(404, 'unknown_version')
    selected = version or next((r['version'] for r in reversed(rows) if r['status'] == 'available'),
                               rows[-1]['version'] if rows else None)
    chosen = next((row for row in chain if row['version'] == selected), {})
    parts = dict(files).get(selected)
    state, document = load(info.run_dir, parts, knowledge_schema) if parts is not None else ('missing', None)
    delivery = delivery_for(deliveries.get(selected, []))
    if document is None:
        if version is not None and parts is not None:
            raise ViewError(409, 'unsupported_knowledge', f'{selected}: {state}')
        return dict(empty, versions=rows, version_chain=chain, selected_version=selected,
                    recorded_version=chosen.get('recorded_version'), coverage=chosen.get('coverage'), delivery=delivery)
    anchors = Anchors(catalog, info, connection, document['facts'])
    current = document['schema'] == SCHEMA
    kind_field = 'statement_kind' if current else 'claim_kind'
    needle = (query or '').strip().casefold()
    articles = [a for a in document['articles'] if isinstance(a, dict) and contains(needle, *article_text(a))]
    facts = [f for f in document['facts'] if isinstance(f, dict) and
             (contains(needle, *fact_text(f, current)) or (current and needle == f.get('state_key')))]
    if kind is not None:
        facts = [fact for fact in facts if fact.get(kind_field) == kind]
    classes = Counter(scope_class(f.get('scope')) for f in facts)
    if scope != 'all':
        wanted = None if scope == 'unrecorded' else scope
        facts = [f for f in facts if scope_class(f.get('scope')) == wanted]
    if current and needle:
        facts.sort(key=lambda f: (f.get('id') != needle, f.get('state_key') != needle))
    shown, omitted = bounded([article_row(a, anchors, current) for a in articles[:MAX_ARTICLES]])
    window, _ = bounded([fact_row(f, anchors, current) for f in facts[after:after + limit]])
    end = after + len(window)
    tags, tags_omitted, kinds = summary(document, kind_field)
    result = dict(source_status='available', versions=rows, version_chain=chain, selected_version=selected, recorded_version=chosen['recorded_version'],
        knowledge_schema=document['schema'],
        coverage=chosen['coverage'], delivery=delivery, quality=_quality(document), state_groups=[], anchor_groups=[], articles=shown, articles_total=len(articles),
        articles_omitted=omitted + max(0, len(articles) - MAX_ARTICLES),
        scope_recorded=True, scope_counts=dict(world=classes['world'], game=classes['game'], unrecorded=classes[None]),
        tag_counts=tags, tag_counts_omitted=tags_omitted,
        facts=dict(items=window, total=len(facts), next=end if window and end < len(facts) else None, limit=limit))
    result[f'{kind_field}_counts'] = kinds
    if current:
        shown_sources = (source for row in window for source in row['citation_source_ids'])
        article_sources = (row['anchor']['source_id'] for row in shown if row['anchor'])
        result['frame_clocks'] = frame_clocks(document, (*shown_sources, *article_sources))
        result['history'] = history(document)
        result['state_groups'], result['anchor_groups'] = _groups(facts, window, (result['history'] or {}).get('replaced', {}))
    return result
