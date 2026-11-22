"""Read-only browser over the knowledge versions exported for a run's player (`delivered-knowledge/2`).

It reads only files of the run's own package, without following a symlink: the version the run started with
(`delivered-knowledge.json`, shown as `initial`) and the versions exported during play (`curator-runner/delivered/vN.json`).
No curator repository, private export or withheld-unit file is read, and nothing is written. An exported version is not
thereby a delivered one: only the host trace says what reached the player.

The closed format records no scope and no known-by for a fact (`harness/player/knowledge.py`), so every fact's `scope` and
`known` are null here and `scope_recorded` is false, whatever else a file may hold.

A fact's `seen` position names an actor-local step of the session that saw it. It becomes a step of this run only
when that session is this run's own: another admission's step numbers never point into this run's frames.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import threading

from .catalog import ID_LIMIT, RunInfo, ViewError
from .curator import read_rooted, rooted_entries, rooted_status
from .knowledge import add_ids, fields, marker
from .telemetry import HostProjection, Steps, count, identifier, read, session_groups

SCHEMA = 'delivered-knowledge/2'
INITIAL = 'initial'
STARTING = ('delivered-knowledge.json',)
EXPORTS = ('curator-runner', 'delivered')
VERSION_FILE = re.compile(r'v(0|[1-9][0-9]{0,8})\.json')
SCOPES = ('all', 'world', 'game')
MAX_VERSIONS = 500
MAX_ARTICLES = 200
BODY_LIMIT = 50
QUERY_LIMIT = 200
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


class Anchors:
    """Resolves a `seen` position to a step of this run."""

    def __init__(self, info: RunInfo, connection: sqlite3.Connection, host: HostProjection | None) -> None:
        self.steps = Steps(connection)
        self.actors = {} if host is None else dict(host.directories, **{a: a for a in host.actors})
        # The session names a trace of this run carries: its own ID, and the name its curator runner gave it.
        self.sessions = {info.session, *session_groups(info)}

    def resolve(self, position: object) -> dict | None:
        if not isinstance(position, dict) or identifier(position.get('session')) not in self.sessions:
            return None
        actor, number = self.actors.get(identifier(position.get('actor'))), count(position.get('step'))
        step = self.steps.ordinal(actor, number) if actor is not None and number is not None else None
        return None if step is None else dict(seq=step.seq, source_id=step.source_id)


def contains(query: str, *values: object) -> bool:
    return not query or any(isinstance(v, str) and query in v.casefold() for v in values)


def article_text(article: dict) -> list:
    body = article.get('body') if isinstance(article.get('body'), list) else []
    return [article.get('id'), article.get('title'), article.get('lead'), *(p.get('text') for p in body if isinstance(p, dict))]


def article_row(article: dict, anchors: Anchors) -> dict:
    out = fields(article, ('id', 'title', 'lead'))
    body = article.get('body') if isinstance(article.get('body'), list) else []
    out['body'] = []
    for part in body[:BODY_LIMIT]:
        if isinstance(part, dict):
            row = fields(part, ('text',))
            add_ids(row, 'facts', part.get('facts'))
            out['body'].append(row)
    out['body_omitted'] = len(body) - len(out['body'])
    add_ids(out, 'links', article.get('links'))
    out['last_confirmed'] = marker(article.get('last_confirmed'))
    out['anchor'] = anchors.resolve(article.get('last_confirmed'))
    return out


def fact_row(fact: dict, anchors: Anchors) -> dict:
    seen = fact.get('seen')
    out = dict(dict.fromkeys(('id', 'type', 'subject', 'text')), **fields(fact, ('id', 'type', 'subject', 'text')))
    return dict(out, known=None, scope=None, seen=fields(seen, SEEN_FIELDS) if isinstance(seen, dict) else None,
        anchor=anchors.resolve(seen))


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
        scope_counts=dict(world=0, game=0, unrecorded=0), facts=dict(items=[], total=0, next=None, limit=limit))
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
    anchors = Anchors(info, connection, host)
    needle = (query or '').strip().casefold()
    articles = [a for a in document['articles'] if isinstance(a, dict) and contains(needle, *article_text(a))]
    facts = [f for f in document['facts'] if isinstance(f, dict) and contains(needle, f.get('id'), f.get('type'), f.get('subject'), f.get('text'))]
    unrecorded = len(facts)
    if scope != 'all':
        facts = []     # the format records no scope, so no fact is known to have this one
    shown, omitted = bounded([article_row(a, anchors) for a in articles[:MAX_ARTICLES]])
    window, cut = bounded([fact_row(f, anchors) for f in facts[after:after + limit]])
    end = after + len(window)
    chosen = next(r for r in rows if r['version'] == selected)
    delivery = delivery_for(host, anchors.steps, selected, chosen['recorded_version'])
    return dict(source_status='available', versions=rows, selected_version=selected, recorded_version=chosen['recorded_version'],
        coverage=chosen['coverage'], delivery=delivery, articles=shown, articles_total=len(articles),
        articles_omitted=omitted + max(0, len(articles) - MAX_ARTICLES),
        scope_recorded=False, scope_counts=dict(world=0, game=0, unrecorded=unrecorded),
        facts=dict(items=window, total=len(facts), next=end if window and end < len(facts) else None, limit=limit))
