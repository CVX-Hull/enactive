"""Read-only browser over the knowledge versions exported for a run's player (`delivered-knowledge/3`).

It reads only files of the run's own package, without following a symlink: the version the run started with
(`delivered-knowledge.json`, shown as `initial`) and the versions exported during play (`curator-runner/delivered/vN.json`).
No curator repository, private export, alias map or withheld-unit file is read, and nothing is written. An exported
version is not thereby a delivered one: only the host trace says what reached the player.

The format is blinded: a world-bound record's scope holds `world: null`, never the label, and positions name opaque
session aliases (`s01`). So a record's scope is shown as its class (`world` or `game`) with its other axes, and its
anchor comes from the frames it cites: a `citation_source_ids` entry of this run's own session resolves to that step,
and one of another session to nothing.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import threading

from .catalog import ID_LIMIT, RunInfo, ViewError
from .curator import read_rooted, rooted_entries, rooted_status
from .knowledge import add_ids, fields, marker, record, scope_class, when
from .telemetry import HostProjection, Steps, identifier, read

SCHEMA = 'delivered-knowledge/3'
INITIAL = 'initial'
STARTING = ('delivered-knowledge.json',)
EXPORTS = ('curator-runner', 'delivered')
VERSION_FILE = re.compile(r'v(0|[1-9][0-9]{0,8})\.json')
SCOPES = ('all', 'world', 'game')
MAX_VERSIONS = 500
MAX_ARTICLES = 200
BODY_LIMIT = 50
QUERY_LIMIT = 200
#: The tag summary keeps the most used tags; a valid file has five claim kinds.
TAG_LIMIT = 200
KIND_LIMIT = 20
#: A listing keeps its text under the response ceiling; what does not fit is counted as omitted.
TEXT_BYTES = 2 * 1024 * 1024
SEEN_FIELDS = ('session', 'actor', 'step')

_lock = threading.Lock()
_cache: dict[tuple, tuple[tuple, tuple[str, dict | None]]] = {}
CACHED_FILES = 128
#: A file of the run package, as the components of its path.
Parts = tuple[str, ...]


def load(run_dir: Path, parts: Parts) -> tuple[str, dict | None]:
    """(`available`, the document) or (why not, None), once per state of the file."""
    status = rooted_status(run_dir, *parts)
    if status is None:
        return 'missing', None
    stamp = (status.st_mode, status.st_ino, status.st_mtime_ns, status.st_size)
    key = (run_dir, parts)
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
            if (not isinstance(document, dict) or document.get('schema') != SCHEMA
                    or not isinstance(document.get('articles'), list) or not isinstance(document.get('facts'), list)):
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


def version_row(name: str, run_dir: Path, parts: Parts) -> dict:
    state, document = load(run_dir, parts)
    if document is None:
        return dict(version=name, status=state, recorded_version=None, articles_count=None, facts_count=None, coverage=None)
    return dict(version=name, status=state, recorded_version=identifier(document.get('version')),
        articles_count=len(document['articles']), facts_count=len(document['facts']), coverage=marker(document.get('coverage')))


def citations(value: object) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


class Anchors:
    """Resolves a cited frame to a step of this run: only a source ID of this run's own session (`<session>-<n>`) that
    one of its steps recorded. Another session's frame has no anchor here."""

    def __init__(self, info: RunInfo, connection: sqlite3.Connection, facts: list) -> None:
        self.steps = Steps(connection)
        prefix = f'{info.session}-'
        self.frames = {s.source_id: s for s in self.steps.rows if isinstance(s.source_id, str) and s.source_id.startswith(prefix)}
        self.facts = {f['id']: f for f in facts if isinstance(f, dict) and isinstance(f.get('id'), str)}

    def step(self, source_id: str) -> dict | None:
        found = self.frames.get(source_id)
        return None if found is None else dict(seq=found.seq, source_id=found.source_id)

    def latest(self, source_ids: list[str]) -> dict | None:
        """The latest step of this run among the cited frames."""
        found = [self.frames[s] for s in source_ids if s in self.frames]
        last = max(found, key=lambda s: s.seq, default=None)
        return None if last is None else dict(seq=last.seq, source_id=last.source_id)

    def article(self, article: dict) -> dict | None:
        body = article.get('body') if isinstance(article.get('body'), list) else []
        cited = [f for part in body if isinstance(part, dict) and isinstance(part.get('facts'), list) for f in part['facts']]
        return self.latest([s for f in cited if isinstance(f, str) and f in self.facts
                            for s in citations(self.facts[f].get('citation_source_ids'))])


def contains(query: str, *values: object) -> bool:
    return not query or any(isinstance(v, str) and query in v.casefold() for v in values)


def tags_of(value: dict) -> list:
    return value['tags'] if isinstance(value.get('tags'), list) else []


def article_text(article: dict) -> list:
    body = article.get('body') if isinstance(article.get('body'), list) else []
    return [article.get('id'), article.get('title'), article.get('lead'), *tags_of(article),
            *(p.get('text') for p in body if isinstance(p, dict))]


def fact_text(fact: dict) -> list:
    return [fact.get('id'), fact.get('claim_kind'), fact.get('subject'), fact.get('text'), *tags_of(fact)]


def article_row(article: dict, anchors: Anchors) -> dict:
    out = dict(dict.fromkeys(('id', 'revision', 'title', 'lead')), **fields(article, ('id', 'revision', 'title', 'lead')))
    body = article.get('body') if isinstance(article.get('body'), list) else []
    out['body'] = []
    for part in body[:BODY_LIMIT]:
        if isinstance(part, dict):
            row = fields(part, ('text',))
            add_ids(row, 'facts', part.get('facts'))
            out['body'].append(row)
    out['body_omitted'] = len(body) - len(out['body'])
    record(out, article)
    out['last_confirmed'] = marker(article.get('last_confirmed'))
    out['anchor'] = anchors.article(article)
    return out


def fact_row(fact: dict, anchors: Anchors) -> dict:
    names = ('id', 'claim_kind', 'evidence_basis', 'subject', 'text')
    out = dict(dict.fromkeys(names), **fields(fact, names))
    record(out, fact)
    out['when'] = when(fact.get('when'))
    add_ids(out, 'cited_by_articles', fact.get('cited_by_articles'))
    add_ids(out, 'citation_source_ids', fact.get('citation_source_ids'))
    out['citation_anchors'] = [anchors.step(s) for s in out['citation_source_ids']]
    seen = fact.get('seen')
    out['seen'] = fields(seen, SEEN_FIELDS) if isinstance(seen, dict) else None
    out['anchor'] = anchors.latest(citations(fact.get('citation_source_ids')))
    return out


def summary(document: dict) -> tuple[list[dict], int, dict]:
    """The tag view counted from the delivered records (most used first), how many tags it leaves out, and the facts
    counted by `claim_kind`."""
    records = [r for r in document['articles'] + document['facts'] if isinstance(r, dict)]
    tags = Counter(t for r in records for t in {t for t in tags_of(r) if isinstance(t, str) and len(t) <= ID_LIMIT})
    ranked = sorted(tags.items(), key=lambda item: (-item[1], item[0]))
    kinds = Counter(f.get('claim_kind') for f in document['facts'] if isinstance(f, dict)
                    and isinstance(f.get('claim_kind'), str) and len(f['claim_kind']) <= ID_LIMIT)
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


def browse(info: RunInfo, connection: sqlite3.Connection, version: str | None, query: str | None,
           scope: str | None, after: int, limit: int) -> dict:
    scope = scope or 'all'
    if scope not in SCOPES:
        raise ViewError(400, 'bad_scope', 'scope must be all, world or game')
    if query is not None and len(query) > QUERY_LIMIT:
        raise ViewError(400, 'bad_q', f'q must be at most {QUERY_LIMIT} characters')
    files = [] if info.run_dir is None else version_files(info.run_dir)
    if version is not None and (len(version) > ID_LIMIT or version not in dict(files)):
        raise ViewError(404, 'unknown_version', version[:ID_LIMIT])
    empty = dict(source_status='unavailable', versions=[], selected_version=None, recorded_version=None, coverage=None,
        delivery=None, articles=[], articles_total=0, articles_omitted=0, scope_recorded=False,
        scope_counts=dict(world=0, game=0, unrecorded=0), tag_counts=[], tag_counts_omitted=0, claim_kind_counts={},
        facts=dict(items=[], total=0, next=None, limit=limit))
    if info.run_dir is None or not files:
        return empty
    rows = [version_row(name, info.run_dir, parts) for name, parts in files]
    selected = version or next((r['version'] for r in reversed(rows) if r['status'] == 'available'), rows[-1]['version'])
    state, document = load(info.run_dir, dict(files)[selected])
    if document is None:
        if version is not None:
            raise ViewError(409, 'unsupported_knowledge', f'{selected}: {state}')
        return dict(empty, versions=rows, selected_version=selected)
    host = read(info)
    anchors = Anchors(info, connection, document['facts'])
    needle = (query or '').strip().casefold()
    articles = [a for a in document['articles'] if isinstance(a, dict) and contains(needle, *article_text(a))]
    facts = [f for f in document['facts'] if isinstance(f, dict) and contains(needle, *fact_text(f))]
    classes = Counter(scope_class(f.get('scope')) for f in facts)
    if scope != 'all':
        facts = [f for f in facts if scope_class(f.get('scope')) == scope]
    shown, omitted = bounded([article_row(a, anchors) for a in articles[:MAX_ARTICLES]])
    window, cut = bounded([fact_row(f, anchors) for f in facts[after:after + limit]])
    end = after + len(window)
    chosen = next(r for r in rows if r['version'] == selected)
    delivery = delivery_for(host, anchors.steps, selected, chosen['recorded_version'])
    tags, tags_omitted, kinds = summary(document)
    return dict(source_status='available', versions=rows, selected_version=selected, recorded_version=chosen['recorded_version'],
        coverage=chosen['coverage'], delivery=delivery, articles=shown, articles_total=len(articles),
        articles_omitted=omitted + max(0, len(articles) - MAX_ARTICLES),
        scope_recorded=True, scope_counts=dict(world=classes['world'], game=classes['game'], unrecorded=classes[None]),
        tag_counts=tags, tag_counts_omitted=tags_omitted, claim_kind_counts=kinds,
        facts=dict(items=window, total=len(facts), next=end if window and end < len(facts) else None, limit=limit))
