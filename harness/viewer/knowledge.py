"""Bounded public projection of one actor's recorded knowledge and reports."""
from __future__ import annotations

import json

from harness.jsonio import file_sha256

from harness.evaluation.core import context
from harness.evaluation.core.host import host_facts, returned_records
from harness.evaluation.core.records import EvaluationError
from harness.evaluation.core.sources import MANIFEST_SCHEMA, read_json_file, read_manifest, read_operations
from .catalog import ID_LIMIT, LIST_LIMIT, TEXT_LIMIT, ViewError
from . import frame, views

#: The versions of an actor's frozen inputs and delivered knowledge: the current ones for a current run, and
#: the ones the sealed sessions of the archive index carry (S-MIGRATION, closed archive reads).
CURRENT_SNAPSHOT = ('player-host-inputs/4', 'delivered-knowledge/3')
ARCHIVED_SNAPSHOT = ('player-host-inputs/3', 'delivered-knowledge/1')
#: Sealed `#889` packages: their delivered knowledge is `delivered-knowledge/2`, which nothing reads any more, so their
#: snapshot is `hash_unavailable` and never misread as the archived `delivered-knowledge/1`.
UNREAD_SNAPSHOT_MANIFESTS = frozenset(('campaign-run/12',))
#: A delivered scope's axes that are never shown: a world-bound record's world label is withheld (delivered as null),
#: `game` is the scope class itself, and a lineage is never an axis.
WITHHELD_AXES = frozenset(('game', 'world', 'lineage'))
AXIS_LIMIT = 8
AXIS_CHARACTERS = 64
#: The delivered record's scalar state, shared by articles and facts.
RECORD_STATE = ('branch_relation', 'lifecycle_state', 'needs_review', 'condition_unverified', 'unverified_branch')
#: The rows of a delivery's text: a briefing's or reminder's leads and index, an update's difference.
DELIVERY_ROWS = ('leads', 'index', 'added', 'updated', 'removed')
ID_FIELDS = frozenset(('id', 'request_id', 'recall_request_id', 'receiving_player_request_id',
                       'tool_call_id', 'source_id', 'operation_id', 'actor_id'))


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


def id_list(value, limit=LIST_LIMIT):
    rows = value if isinstance(value, list) else []
    kept = [v for v in rows[:limit] if isinstance(v, str) and len(v) <= ID_LIMIT]
    return kept, len(rows)-len(kept)


def add_ids(target, name, value, limit=LIST_LIMIT):
    target[name], target[name + '_omitted'] = id_list(value, limit)


def marker(value):
    if not isinstance(value, dict):
        return None
    result = fields(value, ('schema', 'session', 'actor', 'step', 'last_step', 'source_id'))
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


def when(value):
    """A fact's stated condition: its note and the axes it requires."""
    if not isinstance(value, dict):
        return None
    return dict(fields(value, ('note',)), requires=axes(value.get('requires')))


def record(target, value, typed=True):
    """The fields a delivered article and fact share: tags, the scope class and its other axes, lifecycle and review
    flags, citations that went stale, and typed links both ways. `typed` is false for an archived format whose links
    are plain IDs."""
    target.update(dict.fromkeys(RECORD_STATE), **fields(value, RECORD_STATE))
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


def entry(value, kind, catalog, runs, current=True):
    """One snapshot entry. A current (`delivered-knowledge/3`) entry cites frames by `citation_source_ids` and links by
    type; an archived one names `source_ids` and plain links."""
    result = fields(value, ('id', 'revision', 'title', 'subject', 'claim_kind', 'evidence_basis', 'text', 'lead'))
    result['kind'] = kind
    result['seen'] = marker(value.get('seen'))
    result['last_confirmed'] = marker(value.get('last_confirmed'))
    record(result, value, typed=current)
    if kind == 'fact':
        result['when'] = when(value.get('when'))
        add_ids(result, 'cited_by_articles', value.get('cited_by_articles'))
    add_ids(result, 'citation_source_ids', value.get('citation_source_ids'), 20)
    add_ids(result, 'source_ids', value.get('source_ids'), 20)
    body = value.get('body') if isinstance(value.get('body'), list) else []
    result['body'] = []
    for part in body[:20]:
        if not isinstance(part, dict):
            continue
        projected = fields(part, ('text',))
        add_ids(projected, 'facts', part.get('facts'))
        result['body'].append(projected)
    result['body_omitted'] = len(body)-len(result['body'])
    sources = [*result['citation_source_ids'], *result['source_ids']]
    for name in ('seen', 'last_confirmed'):
        if result[name] and result[name].get('source_id'):
            sources.append(result[name]['source_id'])
    result['anchors'] = anchors(catalog, runs, sources)
    return result


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
            item['coverage'] = marker(f.get('coverage'))
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
    snapshot_status = 'unavailable'
    path = actor_dir / 'delivered-knowledge.json'
    frozen_path = actor_dir / 'frozen.json'
    try:
        manifest_schema = read_manifest(directory)['schema']
    except EvaluationError:
        manifest_schema = None  # no supported manifest says which versions these files are
    if manifest_schema == MANIFEST_SCHEMA:
        frozen_schema, knowledge_schema = CURRENT_SNAPSHOT
    elif manifest_schema is None or manifest_schema in UNREAD_SNAPSHOT_MANIFESTS:
        frozen_schema = knowledge_schema = None
    else:
        frozen_schema, knowledge_schema = ARCHIVED_SNAPSHOT
    if path.is_file() and frozen_path.is_file():
        try:
            frozen = read_json_file(frozen_path)
            expected = frozen.get('files', {}).get('delivered-knowledge.json') if isinstance(frozen, dict) and isinstance(frozen.get('files'), dict) else None
            if not isinstance(frozen, dict) or frozen_schema is None or frozen.get('schema') != frozen_schema or frozen.get('actor_id') != actor or frozen.get('session') != info.session or not isinstance(expected, str):
                snapshot_status = 'hash_unavailable'
            elif file_sha256(path) != expected:
                snapshot_status = 'hash_mismatch'
            else:
                snapshot_status = 'verified'
        except (OSError, EvaluationError):
            snapshot_status = 'hash_unavailable'
    elif path.is_file():
        snapshot_status = 'hash_unavailable'
    if snapshot_status == 'verified':
        try:
            value = read_json_file(path)
            if not isinstance(value, dict) or value.get('schema') != knowledge_schema:
                raise ViewError(409, 'unsupported_knowledge')
            articles, fact_rows = value.get('articles'), value.get('facts')
            if not isinstance(articles, list) or not isinstance(fact_rows, list):
                raise ViewError(409, 'unsupported_knowledge')
            all_entries = [(v, kind) for kind, rows in (('article', articles), ('fact', fact_rows)) for v in rows if isinstance(v, dict)]
            if entry_id:
                all_entries = [(v, k) for v, k in all_entries if v.get('id') == entry_id]
            snapshot = dict(**fields(value, ('version',)), coverage=marker(value.get('coverage')), entry_id=entry_id,
                items=[entry(v, k, catalog, runs, knowledge_schema == CURRENT_SNAPSHOT[1]) for v, k in all_entries[after:after+limit]], total=len(all_entries), limit=limit,
                next=after+limit if after+limit < len(all_entries) else None)
        except EvaluationError as exc:
            raise ViewError(409, 'knowledge_unavailable', str(exc)) from exc
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
        add_ids(projected, 'returned_ids', [x['id'] for x in returned_records(call)])
        projected['step'] = None if step is None else dict(seq=step[0], **fields({'source_id':step[1]}, ('source_id',)))
        projected['result'] = fields(result, ('status', 'reason', 'delivered', 'operation_id'))
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
