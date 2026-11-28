"""Read-only browser over the knowledge versions exported for a run's player.

It reads only files of the run's own package, without following a symlink: the version the run started with
(`delivered-knowledge.json`, shown as `initial`) and the versions exported during play (`curator-runner/delivered/vN.json`).
No curator repository, private export, alias map or withheld-unit file is read, and nothing is written. An exported
version is not thereby a delivered one: only the host trace says what reached the player.

The format is blinded: a world-bound record's scope holds `world: null`, never the label, and positions name opaque
session aliases (`s01`); a session that is no alias is withheld. So a record's scope is shown as its class (`world` or
`game`) with its other axes, and its anchor comes from the frames it cites: a `citation_source_ids` entry of this run's
own session resolves to that step when the frame route would serve it, and one of another session to nothing.
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
    CURRENT_SNAPSHOT, SOURCE, add_fact_fields, add_ids, citations, delivered_shape, fields, frame_clocks, history,
    manifest_schema_for, marker, record, scope_class, snapshot_schemas,
)
from .telemetry import HostProjection, Steps, identifier, read
from . import views

SCHEMA = CURRENT_SNAPSHOT[1]
INITIAL = 'initial'
STARTING = ('delivered-knowledge.json',)
EXPORTS = ('curator-runner', 'delivered')
VERSION_FILE = re.compile(r'v(0|[1-9][0-9]{0,8})\.json')
#: `unrecorded` lists the facts that state no scope, the ones `scope_counts` counts as such.
SCOPES = ('all', 'world', 'game', 'unrecorded')
MAX_VERSIONS = 500
MAX_ARTICLES = 200
BODY_LIMIT = 50
QUERY_LIMIT = 200
#: The tag summary keeps the most used tags.
TAG_LIMIT = 200
KIND_LIMIT = 20
#: A listing keeps its text under the response ceiling; what does not fit is counted as omitted.
TEXT_BYTES = 2 * 1024 * 1024

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
    """Resolves a cited frame to a step of this run: only a source ID of this run's own session (`<session>-<n>`) that
    one of its steps recorded and whose frame the per-run frame route serves (its PNG present, its SHA-256 the
    recorded one). Another session's frame, or one that route refuses, has no anchor here."""

    def __init__(self, catalog: Catalog, info: RunInfo, connection: sqlite3.Connection, facts: list) -> None:
        self.catalog, self.info, self.connection = catalog, info, connection
        self.steps = Steps(connection)
        prefix = f'{info.session}-'
        self.frames = {s.source_id: s for s in self.steps.rows if isinstance(s.source_id, str) and s.source_id.startswith(prefix)}
        self.facts = {f['id']: f for f in facts if isinstance(f, dict) and isinstance(f.get('id'), str)}
        self.served: dict[str, bool] = {}      # each frame is read and hashed once per listing

    def verified(self, source_id: str) -> bool:
        if source_id not in self.frames:
            return False
        if source_id not in self.served:
            try:
                views.frame(self.catalog, self.info, self.connection, source_id)
            except ViewError:
                self.served[source_id] = False
            else:
                self.served[source_id] = True
        return self.served[source_id]

    def step(self, source_id: str) -> dict | None:
        if not self.verified(source_id):
            return None
        found = self.frames[source_id]
        return dict(seq=found.seq, source_id=found.source_id)

    def latest(self, source_ids: list[str]) -> dict | None:
        """The latest step of this run among the cited frames that the frame route serves."""
        cited = {s: self.frames[s] for s in source_ids if s in self.frames}
        for found in sorted(cited.values(), key=lambda s: s.seq, reverse=True):
            if self.verified(found.source_id):
                return dict(seq=found.seq, source_id=found.source_id)
        return None

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


def bounded(rows: list[dict]) -> tuple[list[dict], int]:
    """The rows that fit the listing's text bound, and how many were left out."""
    size = 0
    for index, row in enumerate(rows):
        size += len(json.dumps(row, separators=(',', ':'), default=str))
        if size > TEXT_BYTES and index:
            return rows[:index], len(rows) - index
    return rows, 0


def delivery_for(host: HostProjection | None, steps: Steps, selected: str, recorded: str | None) -> dict | None:
    """The player trace's own confirmation that this version reached the player: a briefing for the starting snapshot
    or a delivered update during play. None when no delivery of this version is recorded."""
    if host is None:
        return None
    names = {v for v in (selected, recorded) if v}
    if selected == INITIAL:
        for mark in host.briefings:
            version = mark.fields.get('knowledge_version')
            if (recorded is not None and version == recorded) or (recorded is None and version is None):
                near = steps.nearest(mark.wall)
                return dict(kind='briefing', actor=mark.actor, request_id=mark.fields.get('request_id'),
                    seq=None if near is None else near.seq, knowledge_version=version)
    for mark in host.updates:
        if mark.fields.get('outcome') == 'delivered' and mark.fields.get('knowledge_version') in names:
            near = steps.nearest(mark.wall)
            return dict(kind='update', actor=mark.actor, request_id=mark.fields.get('request_id'),
                seq=None if near is None else near.seq, previous_version=mark.fields.get('previous_version'),
                summary=mark.fields.get('summary'), knowledge_version=mark.fields.get('knowledge_version'))
    for mark in host.briefings:
        version = mark.fields.get('knowledge_version')
        if version is not None and version in names:
            near = steps.nearest(mark.wall)
            return dict(kind='briefing', actor=mark.actor, request_id=mark.fields.get('request_id'),
                seq=None if near is None else near.seq, knowledge_version=version)
    return None


def browse(catalog: Catalog, info: RunInfo, connection: sqlite3.Connection, version: str | None, query: str | None,
           scope: str | None, after: int, limit: int) -> dict:
    scope = scope or 'all'
    if scope not in SCOPES:
        raise ViewError(400, 'bad_scope', 'scope must be all, world, game or unrecorded')
    if query is not None and len(query) > QUERY_LIMIT:
        raise ViewError(400, 'bad_q', f'q must be at most {QUERY_LIMIT} characters')
    files = [] if info.run_dir is None else version_files(info.run_dir)
    if version is not None and (len(version) > ID_LIMIT or version not in dict(files)):
        raise ViewError(404, 'unknown_version', version[:ID_LIMIT])
    empty = dict(source_status='unavailable', versions=[], selected_version=None, recorded_version=None, coverage=None,
        delivery=None, articles=[], articles_total=0, articles_omitted=0, scope_recorded=False,
        scope_counts=dict(world=0, game=0, unrecorded=0), tag_counts=[], tag_counts_omitted=0, statement_kind_counts={},
        facts=dict(items=[], total=0, next=None, limit=limit))
    if info.run_dir is None or not files:
        return empty
    _, knowledge_schema = snapshot_schemas(manifest_schema_for(info.run_dir, info.session))
    rows = [version_row(name, info.run_dir, parts, knowledge_schema) for name, parts in files]
    selected = version or next((r['version'] for r in reversed(rows) if r['status'] == 'available'), rows[-1]['version'])
    state, document = load(info.run_dir, dict(files)[selected], knowledge_schema)
    if document is None:
        if version is not None:
            raise ViewError(409, 'unsupported_knowledge', f'{selected}: {state}')
        return dict(empty, versions=rows, selected_version=selected)
    host = read(info)
    anchors = Anchors(catalog, info, connection, document['facts'])
    current = document['schema'] == SCHEMA
    needle = (query or '').strip().casefold()
    articles = [a for a in document['articles'] if isinstance(a, dict) and contains(needle, *article_text(a))]
    facts = [f for f in document['facts'] if isinstance(f, dict) and
             (contains(needle, *fact_text(f, current)) or (current and needle == f.get('state_key')))]
    classes = Counter(scope_class(f.get('scope')) for f in facts)
    if scope != 'all':
        wanted = None if scope == 'unrecorded' else scope
        facts = [f for f in facts if scope_class(f.get('scope')) == wanted]
    if current and needle:
        facts.sort(key=lambda f: (f.get('id') != needle, f.get('state_key') != needle))
    shown, omitted = bounded([article_row(a, anchors, current) for a in articles[:MAX_ARTICLES]])
    window, _ = bounded([fact_row(f, anchors, current) for f in facts[after:after + limit]])
    end = after + len(window)
    chosen = next(r for r in rows if r['version'] == selected)
    delivery = delivery_for(host, anchors.steps, selected, chosen['recorded_version'])
    kind_field = 'statement_kind' if current else 'claim_kind'
    tags, tags_omitted, kinds = summary(document, kind_field)
    result = dict(source_status='available', versions=rows, selected_version=selected, recorded_version=chosen['recorded_version'],
        knowledge_schema=document['schema'],
        coverage=chosen['coverage'], delivery=delivery, articles=shown, articles_total=len(articles),
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
    return result
