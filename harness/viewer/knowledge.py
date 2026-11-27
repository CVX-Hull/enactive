"""Bounded public projection of one actor's recorded knowledge and reports."""
from __future__ import annotations

from itertools import islice
import json
import re

from harness.evaluation.core import context
from harness.evaluation.core.host import host_facts, record_ids, returned_hits
from harness.evaluation.core.records import EvaluationError, loads
from harness.evaluation.core.sources import MANIFEST_SCHEMA, read_manifest, read_operations
from .catalog import ID_LIMIT, LIST_LIMIT, TEXT_LIMIT, ViewError
from .curator import read_rooted
from . import frame, views

#: A delivered position names only an opaque session alias, and a citation only a frame `<session>-<n>`.
#: These are the player's own `harness.player.knowledge.ALIAS` and `SOURCE`, which the viewer may not import: a session
#: that is no alias (a raw admission or world label) is withheld, and a citation that is no frame is omitted.
ALIAS = re.compile(r's(?:0[1-9]|[1-9][0-9]+)')
SOURCE = re.compile(r'[0-9a-f]{32}-[1-9][0-9]*')
STATE_KEY = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
CLOCK_CONTROL = re.compile(r'[\x00-\x1f\x7f\ud800-\udfff]')
HISTORY_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}(?:@v(?:0|[1-9][0-9]{0,15}))?')
STATEMENT_KINDS = ('observation', 'state', 'outcome', 'inference', 'synthesis')
STATUS_MARKERS = ('contested', 'unverified_branch', 'needs_review')
FACT_FIELDS = ('statement_kind', 'state_key', 'anchor', 'anchor_display', 'when', 'depiction_source_id')
ARCHIVED_FACT_FIELDS = ('claim_kind', 'evidence_basis')
#: A current entry resolves at most this many distinct cited frames; the rest are counted in `anchors_omitted`.
ANCHOR_LIMIT = 20
HIT_LIMIT = 20
HIT_FIELDS = ('id', 'kind', 'title', 'subject', 'via', 'snippet')

#: The versions of an actor's frozen inputs and delivered knowledge: the current ones for a current run, and
#: the ones the sealed sessions of the archive index carry (S-MIGRATION, closed archive reads).
CURRENT_SNAPSHOT = ('player-host-inputs/5', 'delivered-knowledge/4')
LEGACY_SNAPSHOT = ('player-host-inputs/3', 'delivered-knowledge/1')
SNAPSHOTS_BY_MANIFEST = {
    MANIFEST_SCHEMA: CURRENT_SNAPSHOT,
    'campaign-run/13': ('player-host-inputs/4', 'delivered-knowledge/3'),
}
#: Sealed `#889` packages: their delivered knowledge is `delivered-knowledge/2`, which nothing reads any more, so their
#: snapshot is `hash_unavailable` and never misread as the archived `delivered-knowledge/1`.
UNREAD_SNAPSHOT_MANIFESTS = frozenset(('campaign-run/12',))
#: A delivered scope's axes that are never shown: a world-bound record's world label is withheld (delivered as null),
#: `game` is the scope class itself, and a lineage is never an axis.
WITHHELD_AXES = frozenset(('game', 'world', 'lineage'))
AXIS_LIMIT = 8
AXIS_CHARACTERS = 64
#: The delivered record's scalar state, shared by articles and facts.
RECORD_STATE = ('branch_relation', 'lifecycle_state', 'needs_review', 'unverified_branch')
#: The rows of a delivery's text: a briefing's or reminder's leads and index, an update's difference.
DELIVERY_ROWS = ('leads', 'index', 'added', 'updated', 'removed')
ID_FIELDS = frozenset(('id', 'request_id', 'recall_request_id', 'receiving_player_request_id',
                       'tool_call_id', 'source_id', 'operation_id', 'actor_id', 'state_key', 'anchor',
                       'depiction_source_id', 'resolved_from'))


def fields(value, names):
    """Public scalar fields, with explicit omissions; identifiers are never truncated."""
    result, omitted = {}, {}
    for name in names:
        if name not in value:
            continue
        item = value[name]
        if isinstance(item, str):
            limit = ID_LIMIT if name in ID_FIELDS else TEXT_LIMIT
            if len(item) > limit:
                omitted[name] = len(item) if name in ID_FIELDS else len(item) - limit
                item = None if name in ID_FIELDS else item[:limit]
        elif item is not None and type(item) not in (bool, int, float):
            item = None
        result[name] = item
    if omitted:
        result['omitted_characters'] = omitted
    return result


def id_list(value, limit=LIST_LIMIT, pattern=None):
    """The first `limit` IDs that are strings within the ID bound (and match `pattern`), and how many are left out."""
    rows = value if isinstance(value, list) else []
    kept = [v for v in rows[:limit] if isinstance(v, str) and len(v) <= ID_LIMIT and (pattern is None or pattern.fullmatch(v))]
    return kept, len(rows)-len(kept)


def add_ids(target, name, value, limit=LIST_LIMIT, pattern=None):
    target[name], target[name + '_omitted'] = id_list(value, limit, pattern)


def delivered_shape(value, schema):
    """The container shape needed for a bounded spectator read, including the current clock map."""
    return (isinstance(value, dict) and value.get('schema') == schema
            and isinstance(value.get('articles'), list) and isinstance(value.get('facts'), list)
            and (schema != CURRENT_SNAPSHOT[1] or isinstance(value.get('frame_clocks'), dict)))


def add_fact_fields(target, value, current, *, hit=False):
    """Public fact metadata. A delivered depiction must point to one of the fact's cited frames."""
    if not current:
        names = ARCHIVED_FACT_FIELDS
        public = value
        target['when'] = archived_when(value.get('when'))
    else:
        names = FACT_FIELDS
        public = current_fact_fields(value, hit)
    projected = fields(public, names)
    if omitted := projected.pop('omitted_characters', None):
        target.setdefault('omitted_characters', {}).update(omitted)
    target.update(projected)


def current_fact_fields(value, hit):
    public = {name: value[name] for name in FACT_FIELDS
              if isinstance(value.get(name), str) and value[name].strip()}
    if public.get('statement_kind') not in STATEMENT_KINDS:
        public.pop('statement_kind', None)
    for name in ('state_key', 'anchor'):
        if name in public and not STATE_KEY.fullmatch(public[name]):
            del public[name]
    if 'anchor' not in public:
        public.pop('anchor_display', None)
    depiction = public.get('depiction_source_id')
    if depiction and (not SOURCE.fullmatch(depiction) or
                      (not hit and depiction not in citations(value.get('citation_source_ids'), limit=None))):
        del public['depiction_source_id']
    return public


def compact_hit(hit, current=False, archived=False):
    projected = fields({name: hit[name] for name in HIT_FIELDS
        if name in hit and (hit[name] is None or isinstance(hit[name], str))}, HIT_FIELDS)
    if hit.get('kind') == 'fact' and (current or archived):
        add_fact_fields(projected, hit, current, hit=True)
    status = hit.get('status')
    if not archived and isinstance(status, list):
        markers, _ = id_list(status)
        projected['status'] = [item for item in markers if item in STATUS_MARKERS]
        projected['status_omitted'] = len(status) - len(projected['status'])
    else:
        add_ids(projected, 'status', status)
    add_ids(projected, 'cited_by_articles', hit.get('cited_by_articles'))
    return projected


def citations(value, limit=LIST_LIMIT):
    """A delivered record's cited frames: its `citation_source_ids` that are frame source IDs."""
    return id_list(value, limit, SOURCE)[0]


def blind(value):
    """A delivered position or coverage stamp with a `session` that is no opaque alias withheld (null), never echoed."""
    if isinstance(value, dict) and 'session' in value and not (isinstance(value['session'], str) and ALIAS.fullmatch(value['session'])):
        return dict(value, session=None)
    return value


def clock_label(value):
    return isinstance(value, str) and 0 < len(value) <= 64 and value.strip() and not CLOCK_CONTROL.search(value)


def frame_clocks(document, sources):
    """Direct clock labels for the cited frames shown on the page."""
    clocks = document.get('frame_clocks', {})
    return {source: clocks[source] for source in dict.fromkeys(sources) if clock_label(clocks.get(source))}


def history(document):
    """Bounded public replacement and retirement history."""
    value = document.get('history')
    if not isinstance(value, dict):
        return None
    result = {}
    replaced = value.get('replaced')
    reasons = ('restated', 'narrowed', 'corrected', 'changed')
    rows = islice(replaced.items(), LIST_LIMIT) if isinstance(replaced, dict) else ()
    result['replaced'] = {}
    for identity, row in rows:
        if HISTORY_ID.fullmatch(identity) and isinstance(row, dict) and row.get('reason') in reasons:
            item = dict(reason=row['reason'])
            add_ids(item, 'by', row.get('by'), pattern=STATE_KEY)
            result['replaced'][identity] = item
    result['replaced_omitted'] = len(replaced) - len(result['replaced']) if isinstance(replaced, dict) else 0
    for name in ('ended', 'retracted'):
        add_ids(result, name, value.get(name), pattern=STATE_KEY)
    return result


def marker(value, blinded=False, clocks=False):
    """A position or coverage stamp; `blinded` for a delivered one whose session must be an alias
    and whose closed shape has no `source_id`."""
    if not isinstance(value, dict):
        return None
    if blinded:
        value = blind(value)
    allowed = ('schema', 'session', 'actor', 'step', 'last_step') if blinded else ('schema', 'session', 'actor', 'step', 'last_step', 'source_id')
    result = fields(value, allowed)
    if clocks:
        prior = value.get('prior_clock')
        if clock_label(value.get('clock_label')) and 'prior_clock' not in value:
            result['clock_label'] = value['clock_label']
        elif 'clock_label' not in value and isinstance(prior, dict) and clock_label(prior.get('label')):
            offset = prior.get('step_offset')
            if type(offset) is int and 1 <= offset <= (2**53 - 1):
                result['prior_clock'] = dict(label=prior['label'], step_offset=offset)
    order = value.get('order') if isinstance(value.get('order'), list) else []
    parts = [fields({'value': v}, ('value',)) for v in order[:8]]
    result['order'] = [v['value'] for v in parts]
    result['order_omitted'] = max(0, len(order)-8)
    result['order_omitted_characters'] = {str(i): v['omitted_characters']['value'] for i, v in enumerate(parts) if 'omitted_characters' in v}
    return result


def scope_class(value):
    """`world` for a world-bound delivered record (its world label withheld), `game` for one bound to no world, and
    None where the record states no scope."""
    if not isinstance(value, dict):
        return None
    return 'world' if 'world' in value else 'game'


def axes(value):
    """A delivered scope's or condition's other axes, bounded; never a world or a lineage."""
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in list(value.items())[:AXIS_LIMIT] if isinstance(k, str) and len(k) <= ID_LIMIT
            and k not in WITHHELD_AXES and isinstance(v, str) and len(v) <= AXIS_CHARACTERS}


def typed_links(target, name, value, end, limit=LIST_LIMIT):
    """Typed links `{rel, <end>}` to other records, bounded like an ID list."""
    rows = value if isinstance(value, list) else []
    target[name] = [{'rel': v['rel'], end: v[end]} for v in rows[:limit] if isinstance(v, dict)
                    and isinstance(v.get('rel'), str) and len(v['rel']) <= ID_LIMIT and isinstance(v.get(end), str) and len(v[end]) <= ID_LIMIT]
    target[name + '_omitted'] = len(rows) - len(target[name])


def archived_when(value):
    """A fact's stated condition: its note and the axes it requires."""
    if not isinstance(value, dict):
        return None
    return dict(fields(value, ('note',)), requires=axes(value.get('requires')))


def record(target, value, typed=True, legacy=False):
    """The fields a delivered article and fact share: tags, the scope class and its other axes, lifecycle and review
    flags, citations that went stale, and typed links both ways. `typed` is false for an archived format whose links
    are plain IDs."""
    names = (*RECORD_STATE, 'condition_unverified') if legacy else RECORD_STATE
    target.update(dict.fromkeys(names), **fields(value, names))
    target['scope'], target['scope_axes'] = scope_class(value.get('scope')), axes(value.get('scope'))
    for name in ('tags', 'stale_citations', 'shadowed_by', 'contradicted_by'):
        add_ids(target, name, value.get(name))
    if typed:
        typed_links(target, 'links', value.get('links'), 'target')
        typed_links(target, 'backlinks', value.get('backlinks'), 'source')
    else:
        add_ids(target, 'links', value.get('links'))


def source_anchor(catalog, runs, source_id):
    found = frame.resolve(catalog, runs, [], dict(chunk='-', frame=source_id))
    return {k: found[k] for k in ('run', 'source_id', 'available', 'reason')}


def anchors(catalog, runs, values):
    return [source_anchor(catalog, runs, v) for v in dict.fromkeys(values)]


def cited_facts(body):
    """The fact IDs an article's body cites, in order, once each."""
    return list(dict.fromkeys(f for part in body if isinstance(part, dict) and isinstance(part.get('facts'), list)
                              for f in part['facts'] if isinstance(f, str)))


def entry(value, kind, catalog, runs, schema=CURRENT_SNAPSHOT[1], facts=None):
    """One snapshot entry. Versions /4 and /3 cite frames only by `citation_source_ids` and link
    by type: a fact's anchors are its own cited frames, an article's those of the facts its body cites, looked up in
    `facts` (the whole file's facts by ID). Its positions name session aliases, and any other session is withheld. An
    archived (`delivered-knowledge/1`) entry names `source_ids`, positions with a source ID, and plain links."""
    current = schema == CURRENT_SNAPSHOT[1]
    blinded = schema != LEGACY_SNAPSHOT[1]
    names = ('id', 'revision', 'title', 'subject', 'text', 'lead')
    if not blinded:
        names = (*names, 'type')
    result = fields(value, names)
    result['kind'] = kind
    result['seen'] = marker(value.get('seen'), blinded=blinded, clocks=current)
    result['last_confirmed'] = marker(value.get('last_confirmed'), blinded=blinded, clocks=current)
    record(result, value, typed=blinded, legacy=not current)
    if kind == 'fact':
        add_fact_fields(result, value, current)
        add_ids(result, 'cited_by_articles', value.get('cited_by_articles'))
    body = value.get('body') if isinstance(value.get('body'), list) else []
    if blinded:
        add_ids(result, 'citation_source_ids', value.get('citation_source_ids'), 20, SOURCE)
        result['source_ids'], result['source_ids_omitted'] = [], 0     # the current format has no `source_ids`
        if kind == 'article':
            held = facts or {}
            raw = [s for f in cited_facts(body) if f in held for s in citations(held[f].get('citation_source_ids'), limit=None)]
        else:
            raw = citations(value.get('citation_source_ids'), limit=None)
        distinct = list(dict.fromkeys(raw))
        sources, result['anchors_omitted'] = distinct[:ANCHOR_LIMIT], max(0, len(distinct) - ANCHOR_LIMIT)
    else:
        add_ids(result, 'citation_source_ids', value.get('citation_source_ids'), 20)
        add_ids(result, 'source_ids', value.get('source_ids'), 20)
        sources = [*result['citation_source_ids'], *result['source_ids']]
        for name in ('seen', 'last_confirmed'):
            if result[name] and result[name].get('source_id'):
                sources.append(result[name]['source_id'])
        result['anchors_omitted'] = 0
    result['body'] = []
    for part in body[:20]:
        if not isinstance(part, dict):
            continue
        projected = fields(part, ('text',))
        add_ids(projected, 'facts', part.get('facts'))
        result['body'].append(projected)
    result['body_omitted'] = len(body)-len(result['body'])
    result['anchors'] = anchors(catalog, runs, sources)
    return result


def manifest_schema_for(directory, session):
    try:
        manifest = read_manifest(directory)
    except EvaluationError:
        return None
    return manifest['schema'] if manifest.get('session') == session else None


def snapshot_schemas(manifest_schema):
    if manifest_schema is None or manifest_schema in UNREAD_SNAPSHOT_MANIFESTS:
        return None, None
    return SNAPSHOTS_BY_MANIFEST.get(manifest_schema, LEGACY_SNAPSHOT)


def frozen_snapshot(directory, actor_parts, frozen_schema, knowledge_schema, actor, session):
    """(`snapshot_status`, the delivered-knowledge document when `verified`) of an actor's frozen snapshot.

    Each file of the run package is read once, without following a symlink and bounded at 16 MiB; the digest compared
    with `frozen.json` and the document served are of the same bytes, so nothing is reopened after it is verified."""
    knowledge = (*actor_parts, 'delivered-knowledge.json')
    state, snapshot, data = read_rooted(directory, *knowledge)
    if state != 'available':
        return 'unavailable', None     # absent, or no regular file of the package
    frozen_parts = (*actor_parts, 'frozen.json')
    frozen_state, _, frozen_data = read_rooted(directory, *frozen_parts)
    try:
        frozen = loads(frozen_data, '/'.join(frozen_parts)) if frozen_state == 'available' else None
    except EvaluationError:
        frozen = None
    files = frozen.get('files') if isinstance(frozen, dict) else None
    expected = files.get('delivered-knowledge.json') if isinstance(files, dict) else None
    if (frozen_schema is None or not isinstance(expected, str) or frozen.get('schema') != frozen_schema
            or frozen.get('actor_id') != actor or frozen.get('session') != session):
        return 'hash_unavailable', None
    if snapshot['sha256'] != expected:
        return 'hash_mismatch', None
    value = loads(data, '/'.join(knowledge))
    if not delivered_shape(value, knowledge_schema):
        raise ViewError(409, 'unsupported_knowledge')
    return 'verified', value


def projection(catalog, info, connection, actor, request_id, after, limit, entry_id=None):
    directory = catalog.need_run_dir(info)
    actors = [row[0] for row in connection.execute('SELECT DISTINCT actor FROM requests ORDER BY actor')]
    actors, actor_omitted = id_list(actors, 500)
    if not actor:
        return dict(actors=actors, actors_omitted=actor_omitted, actor=None, request_id=None)
    events = views.host_events(catalog, info, actor)
    actor_dir = context._actor_directory(directory, actor)
    if actor_dir is None:
        raise ViewError(404, 'unknown_actor', actor)
    facts = host_facts((actor,), {actor: events})
    requests = [r.key for r in facts.requests]
    if request_id and request_id not in requests:
        raise ViewError(404, 'unknown_request', request_id)
    runs = catalog.runs()
    manifest_schema = manifest_schema_for(directory, info.session)
    frozen_schema, knowledge_schema = snapshot_schemas(manifest_schema)
    blinded_run = manifest_schema in SNAPSHOTS_BY_MANIFEST
    matching = []
    for event in events:
        f = event.fields
        if event.type not in ('knowledge-recall', 'knowledge-delivery', 'knowledge-undelivered'):
            continue
        if request_id and request_id not in (f.get('request_id'), f.get('recall_request_id'), f.get('receiving_player_request_id')):
            continue
        item = fields(f, ('kind', 'status', 'outcome', 'reason', 'version', 'previous_version', 'request_id', 'recall_request_id',
                          'receiving_player_request_id'))
        item.update(type=event.type, line=event.line)
        update = f.get('kind') == 'update'
        for name in ('article_ids', 'fact_ids', 'index_ids', *(('removed_ids',) if update else ())):
            add_ids(item, name, f.get(name))
        if update:
            item['coverage'] = marker(f.get('coverage'), blinded=blinded_run)
        if event.type == 'knowledge-delivery' and isinstance(f.get('text'), str):
            try:
                delivered = json.loads(f['text'].split('\n')[1])
                for name in DELIVERY_ROWS:
                    rows = delivered.get(name) if isinstance(delivered, dict) else None
                    if rows is None and name not in ('leads', 'index'):
                        continue  # only an update states a difference
                    rows = rows if isinstance(rows, list) else []
                    item[name] = [fields(v, ('id', 'title', 'lead', 'index')) for v in rows[:20] if isinstance(v, dict)]
                    item[name + '_omitted'] = len(rows)-len(item[name])
            except (ValueError, IndexError):
                item['delivery_text_unavailable'] = True
        matching.append(item)
    snapshot = None
    if manifest_schema in UNREAD_SNAPSHOT_MANIFESTS:
        snapshot_status, value = 'hash_unavailable', None     # its files are never read, present or not
    else:
        try:
            snapshot_status, value = frozen_snapshot(directory, ('actors', actor_dir.name), frozen_schema, knowledge_schema,
                                                     actor, info.session)
        except EvaluationError as exc:
            raise ViewError(409, 'knowledge_unavailable', str(exc)) from exc
    if value is not None:
        knowledge_schema = value['schema']
        current = knowledge_schema == CURRENT_SNAPSHOT[1]
        blinded = knowledge_schema != LEGACY_SNAPSHOT[1]
        articles, fact_rows = value['articles'], value['facts']
        # An article's anchors come from the facts it cites, wherever they fall in the file, before any selection.
        held = {f['id']: f for f in fact_rows if isinstance(f, dict) and isinstance(f.get('id'), str)} if blinded else None
        all_entries = [(v, kind) for kind, rows in (('article', articles), ('fact', fact_rows)) for v in rows if isinstance(v, dict)]
        if entry_id:
            matched = [(v, k) for v, k in all_entries if v.get('id') == entry_id]
            if not matched and current and STATE_KEY.fullmatch(entry_id):
                matched = [(v, k) for v, k in all_entries if k == 'fact' and v.get('state_key') == entry_id]
            all_entries = matched
        items = [entry(v, k, catalog, runs, knowledge_schema, held) for v, k in all_entries[after:after+limit]]
        snapshot = dict(**fields(value, ('version',)), knowledge_schema=knowledge_schema,
            coverage=marker(value.get('coverage'), blinded=blinded), entry_id=entry_id,
            items=items, total=len(all_entries), limit=limit,
            next=after+limit if after+limit < len(all_entries) else None)
        if current:
            snapshot['frame_clocks'] = frame_clocks(value, (a['source_id'] for item in items for a in item['anchors']))
            snapshot['history'] = history(value)
    operations = {o.operation_id: o for o in read_operations(directory)[1] if o.actor == actor}
    calls = []
    selected_calls = [c for c in facts.calls if not request_id or c.request_id == request_id]
    for call in selected_calls[:100]:
        result = call.result if isinstance(call.result, dict) else {}
        source = result.get('source') if isinstance(result.get('source'), dict) else {}
        step = connection.execute('SELECT seq, source_id FROM steps WHERE operation_id=?', (call.operation_id,)).fetchone() if call.operation_id else None
        operation = operations.get(call.operation_id)
        projected = fields(dict(request_id=call.request_id, tool_call_id=call.tool_call_id, tool=call.tool,
            intent=call.arguments.get('intent'), query=(call.arguments.get('id_or_title') if call.tool == 'player_knowledge_read' else
                   call.arguments.get('query') if call.tool == 'player_knowledge_query' else None),
            operation_id=call.operation_id, source_id=source.get('source_id')), ('request_id', 'tool_call_id', 'tool', 'intent', 'query', 'operation_id', 'source_id'))
        projected['status'] = 'refused' if call.refused else 'error' if call.error else 'finished' if call.finished else 'pending'
        add_ids(projected, 'cites', call.arguments.get('cites'))
        add_ids(projected, 'returned_ids', record_ids(call))
        hits = returned_hits(call)
        current = result.get('schema') == 'player-knowledge/4'
        archived = result.get('schema') == 'player-knowledge/3' and manifest_schema == 'campaign-run/13'
        projected['returned_hits'] = [compact_hit(hit, current, archived) for hit in hits[:HIT_LIMIT]]
        projected['returned_hits_omitted'] = len(hits) - len(projected['returned_hits'])
        projected['step'] = None if step is None else dict(seq=step[0], **fields({'source_id':step[1]}, ('source_id',)))
        projected['result'] = fields(result, ('status', 'reason', 'delivered', 'operation_id'))
        if current or archived:
            projected['result'].update(fields(result, ('resolution', 'resolved_from')))
        projected['operation'] = None if operation is None else dict(**fields(dict(status=operation.status, reason=operation.reason), ('status','reason')),
            receipts=[fields(r, ('status', 'disposition', 'reason')) for r in operation.receipts[:20]], receipts_omitted=max(0,len(operation.receipts)-20))
        source_ids = [x for x in (projected['source_id'], projected['step'].get('source_id') if projected['step'] else None) if x]
        projected['anchors'] = anchors(catalog, runs, source_ids)
        calls.append(projected)
    selected_context = None
    if request_id:
        c = context.request_context(directory, actor, events, request_id)
        selected_context = dict(exact=c['exact'], part_count=c['part_count'], missing=c.get('missing', []))
    store = views.memory_store(catalog, info)
    source_hints = [h for h in (store.hints if store and store.schema == 'player-journal/1' else ()) if h.get('actor_id') == actor]
    hints = []
    for h in source_hints[:100]:
        item = fields(h, ('id', 'actor_id', 'text', 'intent'))
        for name in ('source_ids', 'cites'):
            add_ids(item, name, h.get(name), 20)
        item['anchors'] = anchors(catalog, runs, item['source_ids'])
        hints.append(item)
    finishes = []
    for event in facts.finishes[:100]:
        item = fields(event.fields, ('request_id', 'tool_call_id', 'intent', 'disposition', 'report'))
        for name in ('source_ids', 'cites'):
            add_ids(item, name, event.fields.get(name), 20)
        item['anchors'] = anchors(catalog, runs, item['source_ids'])
        finishes.append(item)
    visible_requests, requests_omitted = id_list(requests, 500)
    return dict(actors=actors, actors_omitted=actor_omitted, actor=actor, request_id=request_id,
        requests=visible_requests, requests_omitted=requests_omitted, events=matching[:100], events_omitted=max(0,len(matching)-100),
        snapshot=snapshot, snapshot_status=snapshot_status, calls=calls, calls_omitted=max(0,len(selected_calls)-100), journal_available=store is not None and store.schema == 'player-journal/1',
        hints=hints, hints_omitted=max(0,len(source_hints)-100), context=selected_context,
        finishes=finishes, finishes_omitted=max(0,len(facts.finishes)-100), outcome=views.run_row(info, None).get('outcome'))
