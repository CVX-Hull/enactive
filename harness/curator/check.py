"""Shared, Git-free submission and snapshot checks for curator knowledge (`curator-knowledge/5`)."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from jsonschema import Draft202012Validator

SUBMISSION = 'curator-submission/3'
FACT = 'curator-fact/6'
MAX_BYTES = 256 * 1024
VERSION = re.compile(r'v(0|[1-9][0-9]*)')
DRAFT_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
SESSION_KINDS = frozenset(('admission', 'grooming', 'hygiene'))
_AXIS = re.compile(r'[a-z][a-z0-9_]{0,31}')
_LABEL = re.compile(r'[ -~]{1,40}')
_FRAME_ID = re.compile(r'[0-9a-f]{32}-[1-9][0-9]*')
_CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]')
_SESSION_FIELDS = ('name', 'world', 'lineage', 'admission', 'context')
_ROOT_BRANCH = dict(parent=None, fork_at=None, fork_version=None)
_SCHEMA_DIR = Path(__file__).resolve().parents[2] / 'schemas'


@lru_cache
def _validator(name: str, definition: str | None = None) -> Draft202012Validator:
    schema = json.loads((_SCHEMA_DIR / name).read_text(encoding='utf-8'))
    if definition is not None:
        schema = {'$defs': schema['$defs'], '$ref': f'#/$defs/{definition}'}
    return Draft202012Validator(schema)


def _json_error(value: str) -> None:
    raise ValueError(f'invalid JSON constant {value}')


def valid_clock_label(value: object) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= 64
            and bool(value.strip()) and _CONTROL_CHARS.search(value) is None)


def read_submission(directory: Path | str, *, dir_fd: int | None = None) -> tuple[object, list[str], str | None]:
    """Read and validate the same bytes that will be named in a validation event."""
    try:
        folder = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
        try:
            fd = os.open('submission.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise OSError('not a regular file')
                raw = stream.read(MAX_BYTES + 1)
        finally:
            os.close(folder)
    except OSError:
        return None, ['submission.json is missing, unreadable or not a regular file'], None
    if len(raw) > MAX_BYTES:
        return None, [f'submission.json exceeds the limit of {MAX_BYTES} bytes'], None
    digest = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw.decode('utf-8'), parse_constant=_json_error)
        json.dumps(data, ensure_ascii=False).encode('utf-8')
        errors = list(_validator('curator-submission.schema.json').iter_errors(data))
    except (ValueError, RecursionError, UnicodeError) as error:
        return None, [f'submission.json is not valid JSON: {type(error).__name__}'], digest
    diagnostics = []
    for error in errors:
        path = list(error.path)
        if error.validator == 'oneOf' and path[:1] == ['changes'] and isinstance(error.instance, dict):
            op = error.instance.get('op')
            if op == 'retire_fact':
                reason_kind = error.instance.get('reason_kind')
                if reason_kind not in ('wrong', 'ended'):
                    diagnostics.append(_diagnostic(path + ['reason_kind'],
                                                   "reason_kind must be 'wrong' or 'ended'"))
                    continue
                op = f'{op}_{reason_kind}'
            if isinstance(op, str) and f'op_{op}' in _validator('curator-submission.schema.json').schema['$defs']:
                shape = _validator('curator-submission.schema.json', f'op_{op}')
                for problem in shape.iter_errors(error.instance):
                    diagnostics.append(_diagnostic(path + list(problem.path), problem.message))
                continue
            diagnostics.append(_diagnostic(path, f'unknown operation {op!r}'))
        else:
            diagnostics.append(_diagnostic(path, error.message))
    return data, diagnostics, digest


def _diagnostic(path: list, message: str) -> str:
    label = 'submission'
    for key in path:
        label += f'[{key}]' if isinstance(key, int) else f'.{key}'
    return f'{label}: {message}'


def base_diagnostics(data: dict, base_version: str) -> list[str]:
    if data['base_version'] != base_version:
        return [f'stale base: submission is based on {data["base_version"]} but the published version is {base_version}']
    return []


def current(record: dict) -> bool:
    return 'superseded_by' not in record and 'retired' not in record


def owner(record: dict) -> str:
    return record['slug'] if record['record'] == 'article' else record['id']


def cited_facts(article: dict) -> set[str]:
    return {identity for claim in article['body'] for identity in claim['facts']}


def state_keys(records: list[dict]) -> set[str]:
    return {row['state_key'] for row in records if row.get('record') == 'fact' and 'state_key' in row}


def _axes(scope: dict) -> dict:
    return {key: value for key, value in scope.items() if key not in ('game', 'world', 'lineage')}


def _join(left: dict, right: dict) -> dict:
    if any(left[key] != right[key] for key in left.keys() & right.keys()):
        raise ValueError('incompatible scopes give one axis two values')
    return left | right


def _validate_axes(scope: dict, declared: set[str]) -> None:
    unknown = scope.keys() - declared
    if unknown:
        raise ValueError(f'undeclared scope axes {sorted(unknown)!r}; declared axes: {sorted(declared)!r}')


def _position(value: object) -> bool:
    validator = _validator('curator-fact.schema.json', 'position')
    return (validator.is_valid(value) and type(value['step']) is int
            and type(value['order'][0]) is int and type(value['order'][2]) is int)


def _version_or_null(value: object) -> bool:
    return value is None or isinstance(value, str) and VERSION.fullmatch(value) is not None


def empty_reservations() -> dict:
    return dict(sessions={}, branches={}, restores=[])


def _merge_sessions(reserved: dict, incoming: dict) -> None:
    """Merge trace identities and timeline labels reserved across published versions."""
    recorded = reserved['sessions']
    names = {row['name']: sid for sid, row in recorded.items()}
    worlds = {row['lineage']: row['world'] for row in recorded.values() if row['lineage'] is not None}
    slots = {(row['lineage'], row['admission']): sid for sid, row in recorded.items()
             if row['lineage'] is not None}
    for sid, row in incoming['sessions'].items():
        if (not re.fullmatch(r'[0-9a-f]{32}', sid) or not isinstance(row, dict)
                or set(row) != set(_SESSION_FIELDS)):
            raise ValueError('invalid session provenance')
        name, world, lineage, admission, context = (row[k] for k in _SESSION_FIELDS)
        if (not isinstance(name, str) or not name.strip()
                or any(v is not None and (not isinstance(v, str) or not _LABEL.fullmatch(v))
                       for v in (world, lineage))
                or (lineage is None) != (admission is None)
                or (admission is not None and (type(admission) is not int or not 1 <= admission <= 10000))):
            raise ValueError('invalid session labels')
        if (not isinstance(context, dict) or len(context) > 8
                or any(not _AXIS.fullmatch(key) or key in ('game', 'world', 'lineage') or not isinstance(value, str)
                       or not re.fullmatch(r'[ -~]{1,64}', value) for key, value in context.items())):
            raise ValueError('invalid session context')
        if sid in recorded and recorded[sid] != row:
            raise ValueError(f'session {sid!r} has different recorded labels or name')
        if name in names and names[name] != sid:
            raise ValueError(f'session directory {name!r} has two sealed identifiers')
        if lineage is not None:
            slot = lineage, admission
            if slot in slots and slots[slot] != sid:
                raise ValueError(f'lineage {lineage!r} admission {admission} has two sealed identifiers')
            if lineage in worlds and worlds[lineage] != world:
                raise ValueError(f'lineage {lineage!r} has two different worlds')
            slots[slot], worlds[lineage] = sid, world
        names[name], recorded[sid] = sid, row
    branches = reserved['branches']
    for lineage, branch in incoming['branches'].items():
        if (not _LABEL.fullmatch(lineage) or not isinstance(branch, dict) or set(branch) != set(_ROOT_BRANCH)
                or (branch['parent'] is not None and
                    (not isinstance(branch['parent'], str) or not _LABEL.fullmatch(branch['parent'])))
                or (branch['fork_at'] is not None and not _position(branch['fork_at']))
                or not _version_or_null(branch['fork_version'])):
            raise ValueError('invalid branch provenance')
        if lineage in branches and branches[lineage] != branch:
            raise ValueError(f'lineage {lineage!r} has conflicting parent, fork_at or fork_version')
        branches[lineage] = branch
    checked = set()
    for lineage in branches:
        visited = set()
        while lineage in branches and lineage not in checked:
            if lineage in visited:
                raise ValueError(f'branch parent cycle at {lineage!r}')
            visited.add(lineage)
            lineage = branches[lineage]['parent']
        checked.update(visited)
    restores = {(r['lineage'], tuple(r['restored_at']['order'])): r for r in reserved['restores']}
    for row in incoming['restores']:
        if (not isinstance(row, dict)
                or set(row) != {'lineage', 'restored_at', 'saved_at', 'restored_version', 'saved_version'}
                or not isinstance(row['lineage'], str) or not _LABEL.fullmatch(row['lineage'])
                or not _position(row['restored_at'])
                or not _version_or_null(row['restored_version']) or not _version_or_null(row['saved_version'])
                or (row['saved_at'] is not None and (not _position(row['saved_at'])
                    or row['saved_at']['order'] >= row['restored_at']['order']))):
            raise ValueError('invalid restore provenance')
        key = row['lineage'], tuple(row['restored_at']['order'])
        if key in restores and restores[key] != row:
            raise ValueError(f'conflicting restore provenance for lineage {row["lineage"]!r}')
        restores[key] = row
    reserved['restores'] = list(restores.values())


def _incoming_provenance(labels: dict, reserved: dict) -> dict:
    incoming = empty_reservations()
    for identity, row in labels.items():
        incoming['sessions'][identity] = {key: row.get(key, {} if key == 'context' else None)
                                          for key in _SESSION_FIELDS}
        lineage = row.get('lineage')
        branches = row.get('branches', {})
        if lineage is not None and lineage not in branches:
            branches = {lineage: row.get('branch', reserved['branches'].get(lineage, _ROOT_BRANCH))} | branches
        for key, branch in branches.items():
            if key in incoming['branches'] and incoming['branches'][key] != branch:
                raise ValueError(f'lineage {key!r} has conflicting parent, fork_at or fork_version')
            incoming['branches'][key] = branch
        incoming['restores'].extend(row.get('restores', []))
    return incoming


def declared_axes(reserved: dict, labels: dict) -> set[str]:
    return {key for row in [*reserved['sessions'].values(), *labels.values()]
            for key in row.get('context', {})}


def _labels(frame: str, provenance: dict) -> dict:
    return provenance['sessions'].get(frame.partition('-')[0], {})


def _citation_world(citations: list[str], provenance: dict) -> str:
    worlds = set()
    for frame in citations:
        world = _labels(frame, provenance).get('world')
        if world is None:
            raise ValueError(f'citation {frame!r} has no recorded world')
        worlds.add(world)
    if len(worlds) != 1:
        raise ValueError('citations span two worlds')
    return worlds.pop()


def _lineages(citations: list[str], provenance: dict) -> list:
    labels = {_labels(frame, provenance).get('lineage') for frame in citations}
    return sorted(labels, key=lambda label: (label is None, label or ''))


def _frame_positions(citations: list[str], provenance: dict) -> list[dict]:
    for frame in citations:
        if frame not in provenance['frames']:
            raise ValueError(f'citation {frame!r} has no recorded provenance')
    return [provenance['frames'][frame] for frame in citations]


def _order(position: dict) -> list:
    return position['order']


def _lineage(position: dict, provenance: dict) -> str | None:
    return next((s['lineage'] for s in provenance['sessions'].values() if s['name'] == position['session']), None)


def _timeline(lineage: str | None, provenance: dict) -> dict:
    """Map each lineage on the path to the last shared position at its child fork."""
    result, cut = {}, None
    while lineage is not None:
        result[lineage] = cut
        branch = provenance['branches'].get(lineage, _ROOT_BRANCH)
        if branch['fork_at'] is None:
            break
        lineage, cut = branch['parent'], branch['fork_at']
    return result


def _on_timeline(position: dict, lineage: str | None, timeline: dict, provenance: dict) -> bool:
    if lineage not in timeline:
        return False
    cut = timeline[lineage]
    if cut is not None and _order(position) > _order(cut):
        return False
    return not any(row['saved_at'] is not None
                   and _order(row['saved_at']) < _order(position) < _order(row['restored_at'])
                   for row in _segment_restores(lineage, cut, provenance))


def _segment_restores(lineage: str, cut: dict | None, provenance: dict):
    return (row for row in provenance['restores'] if row['lineage'] == lineage
            and (cut is None or _order(row['restored_at']) <= _order(cut)))


def _end_on_timeline(seen: dict, end: dict, lineage: str, provenance: dict) -> bool:
    timeline = _timeline(lineage, provenance)
    first = _lineage(seen, provenance)
    last = _lineage(end, provenance)
    if (not _on_timeline(seen, first, timeline, provenance)
            or not _on_timeline(end, last, timeline, provenance)):
        return False
    path = list(timeline)
    if path.index(first) < path.index(last) or (first == last and _order(seen) >= _order(end)):
        return False
    for segment in path[path.index(last):path.index(first) + 1]:
        stop = end if segment == last else timeline[segment]
        for row in _segment_restores(segment, stop, provenance):
            if row['saved_at'] is None and (segment != first or _order(seen) < _order(row['restored_at'])):
                return False
    return True


def _visible_end(fact: dict, lineage: str, provenance: dict, by_id: dict[str, dict] | None = None) -> bool:
    if 'retired' in fact and any(
            all(_end_on_timeline(fact['seen'], p, lineage, provenance)
                for p in _frame_positions(event['end_citations'], provenance))
            for event in fact['retired']['events']):
        return True
    if fact.get('superseded_reason') == 'changed' and by_id is not None:
        for succ_id in fact.get('superseded_by', ()):
            succ = by_id.get(succ_id)
            if succ is not None and any(
                    _end_on_timeline(fact['seen'], p, lineage, provenance)
                    for p in _frame_positions(succ['citations'], provenance)):
                return True
    return False


def ended_still_alive(fact: dict, labels: dict, provenance: dict, by_id: dict[str, dict] | None = None) -> bool:
    if (fact['record'] != 'fact' or fact['lifecycle_state'] != 'ended'
            or labels.get('lineage') is None or labels.get('world') != fact['scope'].get('world')
            or 'world' not in fact['scope']):
        return False
    lineage = labels['lineage']
    return (_on_timeline(fact['seen'], _lineage(fact['seen'], provenance), _timeline(lineage, provenance), provenance)
            and not _visible_end(fact, lineage, provenance, by_id))


def _end_event_time(fact: dict, event: dict, provenance: dict) -> dict | None:
    ends = _frame_positions(event['end_citations'], provenance)
    if 'world' not in fact['scope']:
        if any(_order(p) <= _order(fact['seen']) for p in ends):
            raise ValueError('end citations must be strictly after seen')
        return None
    lineages = _lineages(event['end_citations'], provenance)
    if len(lineages) != 1 or lineages[0] is None:
        raise ValueError('end citations must share one known lineage')
    lineage = lineages[0]
    if not all(_end_on_timeline(fact['seen'], p, lineage, provenance) for p in ends):
        raise ValueError('end citations must be after seen on a surviving timeline')
    latest = max(ends, key=_order)
    if not all(_end_on_timeline(p, latest, lineage, provenance)
               for p in _frame_positions(fact['citations'], provenance)):
        return None
    return (max if event['end'] == 'transition' else min)(ends, key=_order)


def _changed_valid_to(target: dict, successor: dict, provenance: dict) -> dict | None:
    """Validate that `successor` cites a frame strictly after `target.seen` on a surviving timeline."""
    new_positions = _frame_positions(successor['citations'], provenance)
    t_lineages = target.get('lineages', [])
    s_lineages = successor.get('lineages', [])
    known_s = [lin for lin in s_lineages if lin is not None]
    if len(t_lineages) == 1 and t_lineages[0] is not None:
        if not known_s or not any(_end_on_timeline(target['seen'], p, lin, provenance)
                                  for lin in known_s for p in new_positions):
            raise ValueError(f'changed supersession of {target["id"]!r} requires a citation strictly after seen on a surviving timeline')
        if (len(s_lineages) == 1 and s_lineages[0] == t_lineages[0]
                and _end_on_timeline(target['seen'], successor['valid_from'], t_lineages[0], provenance)
                and all(_end_on_timeline(p, successor['valid_from'], t_lineages[0], provenance)
                        for p in _frame_positions(target['citations'], provenance))):
            return successor['valid_from']
        return None
    if not any(_order(p) > _order(target['seen']) for p in new_positions):
        raise ValueError(f'changed supersession of {target["id"]!r} requires a citation strictly after seen')
    return None


def _conflict(left: dict, right: dict) -> bool:
    left_scope, right_scope = left['scope'], right['scope']
    if any(left_scope[key] != right_scope[key] for key in left_scope.keys() & right_scope.keys()):
        return False
    return not (left_scope.items() < right_scope.items() or right_scope.items() < left_scope.items())


def _dependencies(row: dict) -> set[str]:
    targets = {link['target'] for link in row['links'] if link['rel'] == 'depends_on'}
    if row['record'] == 'article':
        targets.update(cited_facts(row))
    return targets


def _incoming_edges(records: list[dict]) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = defaultdict(set)
    for row in records:
        if row['record'] == 'fact':
            for successor in row.get('superseded_by', ()):
                incoming[successor].add(row['id'])
    return incoming


def restated_terminal(identity: str, facts_by_id: dict[str, dict], incoming: dict[str, set[str]]) -> str | None:
    """Follow a verified 1-to-1 same-reading `restated` chain to a current fact, or return None."""
    node = identity
    visited = set()
    while node in facts_by_id and node not in visited:
        visited.add(node)
        row = facts_by_id[node]
        if current(row):
            return node
        successors = row.get('superseded_by', ())
        if (row.get('superseded_reason') != 'restated' or row['lifecycle_state'] != 'superseded'
                or len(successors) != 1):
            return None
        nxt = successors[0]
        if incoming.get(nxt) != {node}:
            return None
        node = nxt
    return None


def _propagate(dependents: dict, seeds: set[str]) -> set[str]:
    flagged = set(seeds)
    pending = list(seeds)
    while pending:
        new = dependents.get(pending.pop(), set()) - flagged
        pending.extend(new)
        flagged.update(new)
    return flagged


def stale_review_sources(active: list[dict]) -> set[str]:
    """Find records whose review flags can be explained by stale citations."""
    dependents = defaultdict(set)
    for row in active:
        for target in _dependencies(row):
            dependents[target].add(owner(row))
    return _propagate(dependents, {owner(row) for row in active if row['stale_citations']})


def recompute_flags(records: list[dict]) -> None:
    """Classify conflicts and propagate two-strength `depends_on` review to the least fixed point."""
    facts_by_id = {row['id']: row for row in records if row['record'] == 'fact'}
    incoming = _incoming_edges(records)
    active = {owner(r): r for r in records if current(r)}
    all_keys = state_keys(records)
    active_by_key: dict[tuple[str | None, str], list[str]] = defaultdict(list)
    active_any_key: dict[str, list[str]] = defaultdict(list)
    for key, row in active.items():
        if row['record'] == 'fact' and 'state_key' in row:
            active_by_key[(row['scope'].get('world'), row['state_key'])].append(key)
            active_any_key[row['state_key']].append(key)

    contested = set()
    for key, row in active.items():
        for link in row['links']:
            target = link['target']
            if link['rel'] == 'contradicts' and target in active and _conflict(row, active[target]):
                contested.update((key, target))
    for key, row in active.items():
        if row['record'] == 'article' and cited_facts(row) & contested:
            contested.add(key)

    dependents = defaultdict(set)
    flagged = set()
    for key, row in active.items():
        row['lifecycle_state'] = 'contested' if key in contested else 'active'
        stale: set[str] = set()
        uncertain_dep = False
        world = row['scope'].get('world')

        # 1. Article claim citations (always reading-level, direct evidence).
        if row['record'] == 'article':
            for fid in cited_facts(row):
                if fid in active:
                    dependents[fid].add(key)
                    if fid in contested:
                        uncertain_dep = True
                else:
                    stale.add(fid)

        # 2. Explicit two-strength `depends_on` links.
        for link in row['links']:
            if link['rel'] != 'depends_on':
                continue
            target = link['target']
            if target in all_keys:
                # Entity-existence pin: quiet while at least one active or contested reading carries `target`.
                readings = active_by_key.get((world, target), []) if world is not None else active_any_key.get(target, [])
                if not readings:
                    stale.add(target)
                continue
            # Reading pin: follows verified 1-to-1 same-reading restatement chains silently.
            if target in active:
                resolved = target
            elif target in facts_by_id:
                resolved = restated_terminal(target, facts_by_id, incoming)
            else:
                resolved = None
            if resolved is None:
                stale.add(target)
            else:
                dependents[resolved].add(key)
                if resolved in contested:
                    uncertain_dep = True

        row['stale_citations'] = sorted(stale)
        if stale or uncertain_dep:
            flagged.add(key)

    flagged = _propagate(dependents, flagged)
    for key, row in active.items():
        row['needs_review'] = key in flagged


def _article_fields(article: dict, facts: dict, provenance: dict) -> dict:
    cited = sorted(cited_facts(article))
    for identity in cited:
        if identity not in facts:
            raise ValueError(f'article {article["slug"]!r} cites unknown fact {identity!r}')
    scope = {}
    for identity in cited:
        scope = _join(scope, facts[identity]['scope'])
    scope = _join(scope, _axes(article['scope']))
    fields = dict(scope=scope, last_confirmed=max((facts[i]['seen'] for i in cited), key=_order),
                  valid_from=max((facts[i]['valid_from'] for i in cited), key=_order))
    if 'world' in scope:
        fields['lineages'] = _lineages([frame for i in cited for frame in facts[i]['citations']], provenance)
    return fields


def _validate_successors(row: dict, replacements: list[dict], provenance: dict, version: str,
                         facts_by_id: dict[str, dict] | None = None) -> None:
    if not replacements:
        return
    identity = row['id']
    if row['record'] == 'article':
        if owner(row) != owner(replacements[0]):
            raise ValueError(f'{identity!r} changes slug across revisions')
        return
    reason = row.get('superseded_reason')
    if reason == 'changed':
        if (row['lifecycle_state'] != 'ended' or 'world' not in row['scope']
                or row.get('state_key') is None):
            raise ValueError(f'{identity!r} has an invalid changed supersession')
        for successor in replacements:
            if row['scope'] != successor['scope'] or row['state_key'] != successor.get('state_key'):
                raise ValueError(f'{identity!r} has an invalid changed supersession')
        if 'retired' in row or len(replacements) > 1:
            if row['valid_to'] is not None:
                raise ValueError(f'{identity!r} multi-end changed supersession must have null valid_to')
        earlier_events = [
            ev for ev in row.get('retired', {}).get('events', ())
            if int(ev['published_in'][1:]) < int(version[1:])
        ]
        earlier_changed = [
            s['id'] for s in replacements
            if int(s['published_in'][1:]) < int(version[1:])
        ]
        for successor in replacements:
            if successor['published_in'] == version:
                expected_valid_to = _changed_valid_to(row, successor, provenance)
                if len(replacements) == 1 and 'retired' not in row and row['valid_to'] != expected_valid_to:
                    raise ValueError(f'{identity!r} has incorrect changed valid_to')
                if earlier_events or earlier_changed:
                    s_lineages = successor.get('lineages', [])
                    if len(s_lineages) != 1 or s_lineages[0] is None:
                        raise ValueError(f'{identity!r} multi-end changed successor requires a single known lineage')
                    prior = dict(row)
                    if earlier_events:
                        prior['retired'] = {'reason_kind': 'ended', 'events': earlier_events}
                    else:
                        prior.pop('retired', None)
                    if earlier_changed:
                        prior['superseded_by'] = earlier_changed
                        prior['superseded_reason'] = 'changed'
                    else:
                        prior.pop('superseded_by', None)
                        prior.pop('superseded_reason', None)
                    if _visible_end(prior, s_lineages[0], provenance, facts_by_id):
                        raise ValueError(f'{identity!r} duplicate visible changed end on lineage {s_lineages[0]!r}')
        return
    if len(replacements) == 1:
        successor = replacements[0]
        if row['scope'] != successor['scope']:
            raise ValueError(f'{identity!r} changes fact scope across supersession')
        if reason == 'restated':
            if (row['statement_kind'] != successor['statement_kind']
                    or row.get('state_key') != successor.get('state_key')
                    or row.get('anchor') != successor.get('anchor')
                    or row.get('when') != successor.get('when')
                    or not set(row['citations']) <= set(successor['citations'])):
                raise ValueError(f'{identity!r} loses its kind, key, anchor, condition or evidence in a restatement')
        elif reason == 'corrected':
            if row['lifecycle_state'] != 'retracted':
                raise ValueError(f'{identity!r} corrected supersession must be retracted')
        else:
            raise ValueError(f'{identity!r} has invalid superseded_reason {reason!r}')
        return
    if reason != 'narrowed':
        raise ValueError(f'{identity!r} multi-successor supersession must use narrowed')
    if (any(not row['scope'].items() < child['scope'].items() or not _keeps_when(row, child)
            for child in replacements)
            or not set(row['citations']) <= {frame for child in replacements for frame in child['citations']}):
        raise ValueError(f'{identity!r} has an invalid narrowing')


def _stale_pairs(records: list[dict]) -> set[tuple[str, str]]:
    return {(owner(row), target) for row in records if current(row) for target in row['stale_citations']}


def _survives_on_lineage(row: dict, lineage: str, provenance: dict) -> bool:
    lineages = row.get('lineages', [])
    if len(lineages) != 1 or lineages[0] is None:
        return True
    src = lineages[0]
    timeline = _timeline(lineage, provenance)
    if src not in timeline:
        return False
    return all(_on_timeline(p, src, timeline, provenance)
               for p in _frame_positions(row['citations'], provenance))


def _alive_on_lineage(row: dict, lineage: str, provenance: dict, by_id: dict[str, dict] | None = None) -> bool:
    if row['lifecycle_state'] in ('superseded', 'retracted'):
        return False
    if row['lifecycle_state'] == 'ended':
        lineages = row.get('lineages', [])
        if len(lineages) != 1 or lineages[0] is None:
            return False
        if _visible_end(row, lineage, provenance, by_id):
            return False
    return _survives_on_lineage(row, lineage, provenance)


def _co_live_on_timeline(left: dict, right: dict, provenance: dict, by_id: dict[str, dict] | None = None) -> bool:
    """Whether two world-bound facts can coexist alive on any surviving timeline."""
    ll, rl = left.get('lineages', []), right.get('lineages', [])
    if current(left) and current(right) and (len(ll) != 1 or ll[0] is None or len(rl) != 1 or rl[0] is None):
        return True
    world = left['scope'].get('world')
    candidates = {lin for lin in (*ll, *rl) if lin is not None}
    for sess in provenance['sessions'].values():
        if sess.get('lineage') is not None and (world is None or sess.get('world') == world):
            candidates.add(sess['lineage'])
    if not candidates:
        return current(left) and current(right)
    return any(_alive_on_lineage(left, lin, provenance, by_id) and _alive_on_lineage(right, lin, provenance, by_id)
               for lin in candidates)


def _validate_keyed_uniqueness(records: list[dict], provenance: dict) -> None:
    """Enforce at most one active uncontested reading per `(world, surviving timeline, state_key)`."""
    facts_by_id = {row['id']: row for row in records if row['record'] == 'fact'}
    candidate_facts = [
        row for row in facts_by_id.values()
        if 'world' in row['scope'] and (current(row) or row['lifecycle_state'] == 'ended')
    ]
    contradicts: set[tuple[str, str]] = set()
    for row in candidate_facts:
        for link in row['links']:
            if link['rel'] == 'contradicts':
                contradicts.add((row['id'], link['target']))
                contradicts.add((link['target'], row['id']))
    by_world_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in candidate_facts:
        if 'state_key' in row:
            by_world_key[(row['scope']['world'], row['state_key'])].append(row)
    for (world, key), group in by_world_key.items():
        if len(group) < 2:
            continue
        for i, left in enumerate(group):
            for right in group[i + 1:]:
                if (left['id'], right['id']) not in contradicts and _co_live_on_timeline(left, right, provenance, facts_by_id):
                    raise ValueError(
                        f'duplicate active state_key {key!r} in world {world!r}: '
                        f'{left["id"]!r} and {right["id"]!r} must be transitioned via changed or linked with contradicts'
                    )


def _validate_anchors(records: list[dict]) -> None:
    """Validate same-world resolution and acyclicity of the `anchor` kinematic forest."""
    world_keys: dict[str, set[str]] = defaultdict(set)
    for row in records:
        if row['record'] == 'fact' and 'state_key' in row and 'world' in row['scope']:
            world_keys[row['scope']['world']].add(row['state_key'])
    edges: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in records:
        if row['record'] != 'fact' or 'anchor' not in row:
            continue
        world = row['scope'].get('world')
        anchor = row['anchor']
        if world is None or anchor not in world_keys[world]:
            raise ValueError(f'{row["id"]!r}: anchor {anchor!r} does not resolve to a state_key in world {world!r}')
        key = row.get('state_key')
        if key == anchor:
            raise ValueError(f'{row["id"]!r}: cannot anchor to its own state_key {anchor!r}')
        if current(row) and key is not None:
            edges[world][key].add(anchor)
    for world, graph in edges.items():
        state: dict[str, int] = {}

        def dfs(node: str) -> None:
            state[node] = 1
            for parent in graph.get(node, ()):
                if state.get(parent) == 1:
                    raise ValueError(f'anchor cycle detected in world {world!r} involving {parent!r}')
                if state.get(parent, 0) == 0:
                    dfs(parent)
            state[node] = 2

        for start in list(graph):
            if state.get(start, 0) == 0:
                dfs(start)


def _validate_depends_on_acyclicity(records: list[dict], provenance: dict) -> None:
    """Enforce surviving-timeline `depends_on` acyclicity across current records."""
    active = {owner(r): r for r in records if current(r)}
    facts_by_id = {row['id']: row for row in records if row['record'] == 'fact'}
    incoming = _incoming_edges(records)
    all_keys = state_keys(records)
    active_by_key: dict[tuple[str | None, str], list[str]] = defaultdict(list)
    active_any_key: dict[str, list[str]] = defaultdict(list)
    for key, row in active.items():
        if row['record'] == 'fact' and 'state_key' in row:
            active_by_key[(row['scope'].get('world'), row['state_key'])].append(key)
            active_any_key[row['state_key']].append(key)

    graph: dict[str, set[str]] = defaultdict(set)
    for key, row in active.items():
        world = row['scope'].get('world')
        if row['record'] == 'article':
            for fid in cited_facts(row):
                if fid in active:
                    graph[key].add(fid)
        for link in row['links']:
            if link['rel'] != 'depends_on':
                continue
            target = link['target']
            if target in all_keys:
                targets = active_by_key.get((world, target), []) if world is not None else active_any_key.get(target, [])
                for dst in targets:
                    if world is None or _co_live_on_timeline(row, active[dst], provenance, facts_by_id):
                        graph[key].add(dst)
            else:
                resolved = target if target in active else (
                    restated_terminal(target, facts_by_id, incoming) if target in facts_by_id else None)
                if resolved is not None and resolved in active:
                    if (world is None or 'world' not in active[resolved]['scope']
                            or _co_live_on_timeline(row, active[resolved], provenance, facts_by_id)):
                        graph[key].add(resolved)

    color: dict[str, int] = {}

    def dfs(node: str) -> None:
        color[node] = 1
        for nxt in graph.get(node, ()):
            if color.get(nxt) == 1:
                raise ValueError(f'depends_on cycle detected involving {nxt!r}')
            if color.get(nxt, 0) == 0:
                dfs(nxt)
        color[node] = 2

    for start in sorted(active):
        if color.get(start, 0) == 0:
            dfs(start)


@dataclass
class Candidate:
    version: str
    records: list[dict]
    provenance: dict
    reservations: dict
    admission_citations: set[str] = field(default_factory=set)
    scope_changes: list[dict] = field(default_factory=list)


def _keeps_when(parent: dict, child: dict) -> bool:
    previous = parent.get('when')
    if previous is None:
        return True
    return child.get('when') == previous


def _edit_article(article: dict, change: dict) -> None:
    body = article['body']
    replacements = {}
    for key in ('replace_claims', 'remove_claims'):
        for claim in change.get(key, []):
            index = claim['index']
            if index >= len(body):
                raise ValueError(f'claim index {index} is out of range')
            if index in replacements:
                raise ValueError(f'duplicate claim index {index}')
            if body[index] != {'text': claim['old_text'], 'facts': claim['old_facts']}:
                raise ValueError(f'claim index {index}: old_text or old_facts does not match')
            replacements[index] = {'text': claim['text'], 'facts': claim['facts']} if key == 'replace_claims' else None
    edited = [replacements.get(i, claim) for i, claim in enumerate(body) if replacements.get(i, claim) is not None]
    article['body'] = edited + change.get('add_claims', [])
    if not article['body']:
        raise ValueError('the article body would be empty; use retire_article')
    for key in ('title', 'lead', 'scope'):
        if f'set_{key}' in change:
            article[key] = change[f'set_{key}']
    for key in ('links', 'tags'):
        remove = change.get(f'remove_{key}', [])
        add = change.get(f'add_{key}', [])
        before = article[key]
        if any(item not in before for item in remove):
            raise ValueError(f'cannot remove missing {key}')
        remaining = [item for item in before if item not in remove]
        if any(item in remaining for item in add):
            raise ValueError(f'cannot add duplicate {key}')
        article[key] = remaining + add
    if len(article['tags']) > 8:
        raise ValueError('an article can have at most 8 tags')


def _retag(record: dict, tags: list, version: str) -> None:
    record.setdefault('retagged', []).append({'from': record['tags'], 'to': tags, 'version': version})
    record['tags'] = tags


class _Batch:
    def __init__(self, candidate: Candidate, game: str, session_id: str, session_kind: str, window_frames: dict,
                 reserved_ids: set[str], reserved_state_keys: set[str], axes: set[str], base_records: list[dict]):
        self.candidate = candidate
        self.metadata = dict(published_in=candidate.version, session=session_id)
        self.game = game
        self.session_kind = session_kind
        self.frames = window_frames
        self.axes = axes
        self.ids = reserved_ids | {owner(row) for row in candidate.records}
        self.state_keys = reserved_state_keys | state_keys(candidate.records)
        self.facts = {row['id']: row for row in candidate.records if row['record'] == 'fact'}
        self.base_facts = {row['id']: row for row in base_records if row['record'] == 'fact'}
        self.base_articles = {row['slug']: row for row in candidate.records
                              if row['record'] == 'article' and current(row)}
        self.articles = {}
        self.substantive = set()
        self.edited_or_revised_articles = set()
        self.retired_articles = set()
        self.fact_targets = set()
        self.changed_or_ended_world_facts = set()
        self.incoming_edges = defaultdict(set)
        self.base_inbound_fact_pins: dict[str, set[str]] = defaultdict(set)
        for row in base_records:
            if not current(row):
                continue
            for link in row['links']:
                if link['rel'] == 'depends_on' and link['target'] in self.base_facts:
                    self.base_inbound_fact_pins[link['target']].add(owner(row))

    def reserve(self, identity: str) -> None:
        if identity in self.ids or identity in self.state_keys:
            raise ValueError(f'identifier {identity!r} is not new (already reserved as a record ID, slug, or state_key)')
        self.ids.add(identity)

    def reserve_state_key(self, key: str) -> None:
        if key in self.ids:
            raise ValueError(f'state_key {key!r} collides with a reserved record ID or article slug')
        self.state_keys.add(key)

    def citations(self, citations: list, inherited=()) -> list[dict]:
        new = set(citations).difference(inherited)
        for frame in sorted(new):
            if frame not in self.frames:
                raise ValueError(f'citation {frame!r} is outside the trace window')
        self.candidate.admission_citations.update(new)
        return _frame_positions(citations, self.candidate.provenance)

    def make_fact(self, submitted: dict, inherited=()) -> dict:
        identity = submitted['id']
        self.reserve(identity)
        if 'state_key' in submitted:
            self.reserve_state_key(submitted['state_key'])
        row = {key: value for key, value in submitted.items() if key != 'binds'}
        _validate_axes(row['scope'], self.axes)
        row['scope'] = dict(game=self.game, **row['scope'])
        positions = self.citations(row['citations'], inherited)
        if 'depiction_source_id' in row and row['depiction_source_id'] not in row['citations']:
            raise ValueError('depiction_source_id must be a member of citations')
        if submitted.get('binds'):
            row['scope']['world'] = _citation_world(row['citations'], self.candidate.provenance)
            row['lineages'] = _lineages(row['citations'], self.candidate.provenance)
        else:
            if row['statement_kind'] == 'state':
                raise ValueError('statement_kind "state" requires binds: ["world"]')
            if 'state_key' in row or 'anchor' in row:
                raise ValueError('state_key and anchor require binds: ["world"]')
        row.update(self.metadata, seen=max(positions, key=_order), valid_from=min(positions, key=_order),
                   valid_to=None, lifecycle_state='active', stale_citations=[], needs_review=False)
        self.facts[identity] = row
        self.candidate.records.append(row)
        return row

    def fact_target(self, identity: str, *, allow_ended: bool = False) -> dict:
        target = self.facts.get(identity)
        if target is None:
            raise ValueError(f'fact {identity!r} does not exist')
        if (identity in self.fact_targets or target['published_in'] == self.candidate.version
                or not current(target) and not (allow_ended and target['lifecycle_state'] == 'ended'
                                                and 'world' in target['scope'])):
            raise ValueError(f'fact {identity!r} is not current or already changed in this submission')
        self.fact_targets.add(identity)
        return target

    def supersede(self, change: dict) -> None:
        reason_kind = change['reason_kind']
        if self.session_kind == 'hygiene' and reason_kind in ('corrected', 'changed'):
            raise ValueError(f'hygiene session forbids {reason_kind!r} supersession')
        targets = [self.fact_target(identity, allow_ended=(reason_kind == 'changed')) for identity in change['ids']]
        target_ids = {t['id'] for t in targets}
        scope = targets[0]['scope']
        if any(target['scope'] != scope for target in targets):
            raise ValueError('supersession requires the same fact scope')
        fact = dict(change['fact'])
        axes = _axes(scope)
        if 'scope' in fact:
            _validate_axes(fact['scope'], self.axes)
        binds = ['world'] if 'world' in scope else []
        if fact.get('scope', axes) != axes or fact.get('binds', binds) != binds:
            raise ValueError('supersession requires the same fact scope and world binding')
        fact.update(scope=axes, binds=binds)
        origins = list(dict.fromkeys(c for target in targets for c in target['citations']))

        if reason_kind == 'restated':
            if any(target['lifecycle_state'] == 'contested' for target in targets):
                raise ValueError('restated supersession cannot clear contested facts')
            if any(target['statement_kind'] != fact['statement_kind']
                   or target.get('state_key') != fact.get('state_key')
                   or target.get('anchor') != fact.get('anchor')
                   or target.get('when') != fact.get('when') for target in targets):
                raise ValueError('restated supersession must keep statement_kind, state_key, anchor, and when equal')
            required_links = {
                (lk['rel'], lk['target']) for t in targets for lk in t['links']
                if lk['rel'] in ('depends_on', 'contradicts') and lk['target'] not in target_ids
            }
            new_links = {(lk['rel'], lk['target']) for lk in fact['links']}
            if not required_links <= new_links:
                raise ValueError('restated supersession must preserve outgoing depends_on and contradicts links')
            if self.session_kind == 'hygiene' and any('state_key' in t or 'world' in t['scope'] for t in targets):
                raise ValueError('hygiene session cannot merge or alter keyed or world-bound facts')
            if self.session_kind in ('grooming', 'hygiene') and len(targets) > 1:
                if 'world' in scope or any('state_key' in t for t in targets):
                    raise ValueError('autonomous N->1 merge is limited to unkeyed game-wide facts')
                pinned = {pin for tid in target_ids for pin in self.base_inbound_fact_pins.get(tid, ())}
                if pinned:
                    raise ValueError(f'autonomous N->1 merge rejected due to inbound fact-ID depends_on pin(s) from {sorted(pinned)!r}')
            fact['citations'] = list(dict.fromkeys([*origins, *fact['citations']]))
            new = self.make_fact(fact, origins)
            if new['scope'] != scope:
                raise ValueError('supersession requires the same fact scope')
            for target in targets:
                target.update(lifecycle_state='superseded', superseded_by=[new['id']], superseded_reason='restated')
        elif reason_kind == 'changed':
            if 'world' not in scope:
                raise ValueError('changed supersession requires world-bound keyed facts')
            key = fact.get('state_key')
            if key is None or any(target.get('state_key') != key for target in targets):
                raise ValueError('changed supersession requires matching state_key on targets and replacement')
            new = self.make_fact(fact)
            if new['scope'] != scope:
                raise ValueError('supersession requires the same fact scope')
            provenance = self.candidate.provenance
            new_lineages = new.get('lineages', [])
            for target in targets:
                if target['lifecycle_state'] == 'ended':
                    if len(new_lineages) != 1 or new_lineages[0] is None:
                        raise ValueError(
                            f'fact {target["id"]!r} is already ended and requires a single known lineage where it is still alive'
                        )
                    lin = new_lineages[0]
                    if not ended_still_alive(target, {'world': scope['world'], 'lineage': lin}, provenance, self.facts):
                        raise ValueError(f'fact {target["id"]!r} already has a visible end on lineage {lin!r}')
                valid_to = _changed_valid_to(target, new, provenance)
                succs = list(target.get('superseded_by', ()))
                succs.append(new['id'])
                target.update(
                    lifecycle_state='ended',
                    valid_to=valid_to if len(succs) == 1 and 'retired' not in target else None,
                    superseded_by=succs,
                    superseded_reason='changed',
                )
                self.changed_or_ended_world_facts.add(target['id'])
        else:
            if not set(fact['citations']).difference(origins):
                raise ValueError('a correction requires at least one new frame')
            new = self.make_fact(fact)
            if new['scope'] != scope:
                raise ValueError('supersession requires the same fact scope')
            for target in targets:
                target.update(lifecycle_state='retracted', superseded_by=[new['id']], superseded_reason='corrected')

    def narrow(self, change: dict) -> None:
        parent = self.fact_target(change['id'])
        carried = {frame for fact in change['facts'] for frame in fact['citations']}
        if not set(parent['citations']) <= carried:
            raise ValueError('narrow_fact must carry over all original citations')
        for fact in change['facts']:
            child = self.make_fact(fact, parent['citations'])
            if not parent['scope'].items() < child['scope'].items():
                raise ValueError('each child must keep the parent scope and strictly narrow it')
            if not _keeps_when(parent, child):
                raise ValueError('each child must preserve the parent when')
        parent.update(lifecycle_state='superseded', superseded_by=[child['id'] for child in change['facts']],
                      superseded_reason='narrowed')

    def retire_fact(self, change: dict) -> None:
        ended = change['reason_kind'] == 'ended'
        fact = self.fact_target(change['id'], allow_ended=ended)
        if self.session_kind == 'hygiene' and 'world' in fact['scope'] and current(fact):
            raise ValueError('hygiene session cannot retire active world-bound facts')
        provenance = self.candidate.provenance
        citations = change.get('citations', [])
        ends = change.get('end_citations', [])
        evidence = citations + ends
        self.citations(evidence)
        if 'world' in fact['scope'] and _citation_world(evidence, provenance) != fact['scope']['world']:
            raise ValueError("retirement citations must belong to the fact's world")
        reason = change['reason']
        if not ended:
            fact.update(lifecycle_state='retracted', valid_to=None,
                        retired=dict(reason=reason, reason_kind='wrong', citations=citations, **self.metadata))
            return
        if set(ends).intersection(fact['citations'] + citations):
            raise ValueError('end_citations must be disjoint from stored and supporting citations')
        event = dict(reason=reason, end=change['end'], end_citations=ends, citations=citations, **self.metadata)
        event['valid_to'] = _end_event_time(fact, event, provenance)
        if fact['lifecycle_state'] == 'ended':
            lineage = _lineages(ends, provenance)[0]
            if _visible_end(fact, lineage, provenance, self.facts):
                raise ValueError(f'fact {fact["id"]!r} already has a visible end on lineage {lineage!r}')
        fact.setdefault('retired', dict(reason_kind='ended', events=[]))['events'].append(event)
        fact.update(lifecycle_state='ended', valid_to=_fact_end_time(fact))
        if 'world' in fact['scope']:
            self.changed_or_ended_world_facts.add(fact['id'])

    def working_article(self, slug: str) -> dict:
        if slug not in self.articles:
            if slug not in self.base_articles:
                raise ValueError(f'article {slug!r} is not current')
            row = deepcopy(self.base_articles[slug])
            minimum = _article_fields(dict(row, scope={}), self.facts, self.candidate.provenance)['scope']
            row['scope'] = {key: value for key, value in row['scope'].items() if key not in minimum}
            self.articles[slug] = row
        return self.articles[slug]

    def _restated_reaches(self, source: str, target: str) -> bool:
        """Follow restated supersession edges (including N->1 restated merges) for article citation remapping."""
        node = source
        visited = set()
        while node in self.facts and node not in visited:
            visited.add(node)
            fact = self.facts[node]
            successors = fact.get('superseded_by', ())
            if (fact['lifecycle_state'] != 'superseded' or fact.get('superseded_reason') != 'restated'
                    or len(successors) != 1):
                break
            node = successors[0]
        return node != source and node == target and target in self.facts and current(self.facts[target])

    def remap(self, change: dict) -> None:
        sources, target = change['from'], change['to']
        for source in sources:
            if not self._restated_reaches(source, target):
                raise ValueError(f'{target!r} must end a restated chain from {source!r}')
        source_set = set(sources)
        for slug in change['in']:
            article = self.working_article(slug)
            cited = cited_facts(article)
            matched = source_set & cited
            if not matched:
                raise ValueError(f'article {slug!r} does not cite any of {sources!r}')
            new_body = []
            for claim in article['body']:
                if source_set & set(claim['facts']):
                    remapped = []
                    for identity in claim['facts']:
                        replacement = target if identity in source_set else identity
                        if replacement not in remapped:
                            remapped.append(replacement)
                    new_body.append(dict(claim, facts=remapped))
                else:
                    new_body.append(claim)
            article['body'] = new_body
            self.substantive.add(slug)

    def article_change(self, change: dict) -> None:
        op = change['op']
        if op == 'remap_citations':
            self.remap(change)
            return
        if op == 'add_article':
            article = dict(change['article'])
            slug = article['slug']
            self.reserve(slug)
            article.setdefault('scope', {})
            self.articles[slug] = article
        else:
            slug = change['slug']
            article = self.working_article(slug)
            if op == 'retire_article':
                kind = change['reason_kind']
                self.base_articles[slug].update(lifecycle_state='retracted' if kind == 'wrong' else 'ended',
                                                retired=dict(reason=change['reason'], reason_kind=kind, **self.metadata))
                del self.articles[slug]
                self.retired_articles.add(slug)
                return
            if op == 'edit_article':
                _edit_article(article, change)
            else:
                article.update({key: value for key, value in change.items() if key not in ('op', 'slug')})
            self.edited_or_revised_articles.add(slug)
        _validate_axes(article['scope'], self.axes)
        _article_fields(article, self.facts, self.candidate.provenance)
        self.substantive.add(slug)

    def retag(self, change: dict) -> None:
        for identity, tags in change['assignments'].items():
            if identity in self.facts:
                target = self.fact_target(identity)
            else:
                target = self.working_article(identity)
            _retag(target, tags, self.candidate.version)

    def finish_articles(self) -> None:
        for slug, article in self.articles.items():
            previous = self.base_articles.get(slug)
            fields = _article_fields(article, self.facts, self.candidate.provenance)
            if slug in self.substantive:
                if previous is not None and previous['scope'] != fields['scope']:
                    self.candidate.scope_changes.append(dict(slug=slug, **{'from': previous['scope'], 'to': fields['scope']}))
                identity = f'{slug}@{self.candidate.version}'
                article.pop('lineages', None)
                article.update(self.metadata, **fields, id=identity, valid_to=None,
                               lifecycle_state='active', stale_citations=[], needs_review=False)
                if previous is not None:
                    previous.update(lifecycle_state='superseded', superseded_by=[identity])
                self.candidate.records.append(article)
            else:
                previous.update(tags=article['tags'], retagged=article['retagged'])

    def check_world_article_invariants(self) -> None:
        """Enforce atomic live world-article repair and no-silent-omission of active world facts (#1020)."""
        post_world_articles = [
            row for row in self.candidate.records
            if row['record'] == 'article' and current(row) and 'world' in row['scope']
        ]
        # 1. Atomic live repair: changed/ended world facts previously cited by a world article cannot stay cited.
        for fid in sorted(self.changed_or_ended_world_facts):
            still_citing = sorted(a['slug'] for a in post_world_articles if fid in cited_facts(a))
            if still_citing:
                raise ValueError(
                    f'world fact {fid!r} changed or ended without repairing citing world article(s) {still_citing!r} in the same submission'
                )
        # 2. No silent omission: editing/revising (or retiring in hygiene) a world article cannot drop active world facts.
        post_cited_world = {fid for a in post_world_articles for fid in cited_facts(a)}
        checked_slugs = set(self.edited_or_revised_articles)
        if self.session_kind == 'hygiene':
            checked_slugs.update(self.retired_articles)
        for slug in sorted(checked_slugs):
            prev = self.base_articles.get(slug)
            if prev is None or 'world' not in prev['scope']:
                continue
            dropped = sorted(
                fid for fid in cited_facts(prev)
                if fid in self.facts and 'world' in self.facts[fid]['scope']
                and current(self.facts[fid]) and fid not in post_cited_world
            )
            if dropped:
                raise ValueError(
                    f'world article {slug!r} silently drops active world fact(s) {dropped!r}; '
                    'end, supersede, or move them to another current world article in the same submission'
                )


def _fact_end_time(fact: dict) -> dict | None:
    if 'superseded_by' in fact:
        return None
    events = fact['retired']['events']
    return events[0]['valid_to'] if len(events) == 1 and len(fact.get('lineages', [])) == 1 else None


def _article_retirement_conflicts(changes: list) -> None:
    article_ops = defaultdict(list)
    for change in changes:
        op = change['op']
        slugs = {
            'add_article': lambda: [change['article']['slug']],
            'remap_citations': lambda: change['in'],
            'retag': lambda: change['assignments'],
        }
        targets = slugs[op]() if op in slugs else [change['slug']] if 'slug' in change else []
        for slug in targets:
            article_ops[slug].append(op)
    for slug, ops in article_ops.items():
        if 'retire_article' in ops and len(ops) > 1:
            others = list(ops)
            others.remove('retire_article')
            raise ValueError(f'retire_article for {slug!r} cannot be combined with {", ".join(others)}')


def evaluate(data: dict, *, base_records: list[dict], base_provenance: dict, game: str, base_version: str,
             reserved_ids: set[str], reserved_sessions: dict, session_id: str, window_frames: dict,
             session_kind: str, session_labels: dict, declared_axes: set[str],
             reserved_state_keys: set[str] | None = None) -> tuple[Candidate | None, list[str]]:
    """Evaluate a well-formed submission without mutating the base or its reservations."""
    diagnostics = base_diagnostics(data, base_version)
    if diagnostics:
        return None, diagnostics
    if session_kind not in SESSION_KINDS:
        return None, [f'invalid session_kind {session_kind!r}']
    try:
        version = f'v{int(base_version[1:]) + 1}'
        provenance, reservations = deepcopy(base_provenance), deepcopy(reserved_sessions)
        provenance.setdefault('frame_clocks', {})
        incoming = _incoming_provenance(session_labels, reservations)
        _merge_sessions(reservations, incoming)
        _merge_sessions(provenance, incoming)
        # Keep known timeline labels across a knowledge restore without restoring its discarded records.
        _merge_sessions(provenance, reservations)
        for frame, position in window_frames.items():
            provenance['frames'].setdefault(frame, position)
        for frame, label in data.get('frame_clocks', {}).items():
            if frame not in window_frames:
                raise ValueError(f'frame_clocks[{frame!r}] is outside the trace window')
            if not valid_clock_label(label):
                raise ValueError(f'frame_clocks[{frame!r}] is not a valid clock_label')
            existing = provenance['frame_clocks'].get(frame)
            if existing is not None and existing != label:
                raise ValueError(f'frame_clocks[{frame!r}] conflicts with already-recorded label {existing!r}')
            provenance['frame_clocks'][frame] = label

        candidate = Candidate(version, deepcopy(base_records), provenance, reservations)
        batch = _Batch(candidate, game, session_id, session_kind, window_frames,
                       reserved_ids, set(reserved_state_keys or ()), declared_axes, base_records)
        changes = data['changes']
        _article_retirement_conflicts(changes)
        handlers = {
            'add_fact': lambda change: batch.make_fact(change['fact']),
            'supersede_fact': batch.supersede,
            'narrow_fact': batch.narrow,
            'retire_fact': batch.retire_fact,
        }
        # Resolve immutable fact IDs before composing article edits, including forward references in a batch.
        for index, change in enumerate(changes):
            op = change['op']
            if op in handlers:
                try:
                    handlers[op](change)
                except ValueError as error:
                    raise ValueError(f'changes[{index}] {op}: {error}') from error
        for row in batch.facts.values():
            for successor in row.get('superseded_by', []):
                batch.incoming_edges[successor].add(row['id'])
        for index, change in enumerate(changes):
            op = change['op']
            if op in handlers:
                continue
            try:
                if op == 'retag':
                    if session_kind not in ('grooming', 'hygiene'):
                        raise ValueError('retag requires a grooming or hygiene session')
                    batch.retag(change)
                else:
                    batch.article_change(change)
            except ValueError as error:
                raise ValueError(f'changes[{index}] {op}: {error}') from error
        batch.finish_articles()
        batch.check_world_article_invariants()
        recompute_flags(candidate.records)
        validate_snapshot(candidate.records, provenance, game, version)
        if session_kind in ('grooming', 'hygiene'):
            added = _stale_pairs(candidate.records) - _stale_pairs(base_records)
            if added:
                raise ValueError(f'{session_kind} introduces stale citations {sorted(added)!r}')
        return candidate, []
    except (ValueError, KeyError, TypeError, RecursionError) as error:
        return None, [f'invalid candidate snapshot: {error}']


def _validate_retirement(row: dict, provenance: dict, version: str, facts_by_id: dict[str, dict] | None = None) -> None:
    retired = row['retired']
    if retired['reason_kind'] != 'ended':
        events = [retired]
    else:
        events = retired['events']
        if row['valid_to'] != _fact_end_time(row) or ('world' not in row['scope'] and len(events) != 1):
            raise ValueError('invalid fact end time or number of end events')
    last_version = int(row['published_in'][1:])
    earlier_events = []
    earlier_changed = [
        sid for sid in row.get('superseded_by', ())
        if row.get('superseded_reason') == 'changed' and facts_by_id is not None and sid in facts_by_id
        and int(facts_by_id[sid]['published_in'][1:]) < int(version[1:])
    ]
    for event in events:
        event_version = int(event['published_in'][1:])
        if not last_version < event_version <= int(version[1:]):
            raise ValueError('invalid retirement publication version')
        last_version = event_version
        citations, ends = event.get('citations', []), event.get('end_citations', [])
        evidence = citations + ends
        _frame_positions(evidence, provenance)
        if evidence and 'world' in row['scope'] and _citation_world(evidence, provenance) != row['scope']['world']:
            raise ValueError("retirement citations must belong to the fact's world")
        if not ends:
            continue
        if set(ends).intersection(row['citations'] + citations):
            raise ValueError('end_citations must be disjoint from stored and supporting citations')
        # A subsequent restore can abandon previously valid evidence. History checks the event
        # against the timeline recorded at its publication, before those later labels existed.
        if event['published_in'] == version:
            if event['valid_to'] != _end_event_time(row, event, provenance):
                raise ValueError('incorrect end event valid_to')
            if earlier_events or earlier_changed:
                prior = dict(row)
                if earlier_events:
                    prior['retired'] = {'reason_kind': 'ended', 'events': earlier_events}
                else:
                    prior.pop('retired', None)
                if earlier_changed:
                    prior['superseded_by'] = earlier_changed
                    prior['superseded_reason'] = 'changed'
                else:
                    prior.pop('superseded_by', None)
                    prior.pop('superseded_reason', None)
                if _visible_end(prior, _lineages(ends, provenance)[0], provenance, facts_by_id):
                    raise ValueError('duplicate visible end event')
        earlier_events.append(event)


def validate_snapshot(records: list[dict], provenance: dict, game: str, version: str, *,
                      _raw_lines: list[str] | None = None,
                      _schema_valid: set[str] | None = None) -> dict[str, dict]:
    """Validate a complete stored snapshot, including derived positions, keys, anchors, references and flags."""
    if (not isinstance(provenance, dict) or not set(provenance) <=
            {'frames', 'frame_clocks', 'sessions', 'branches', 'restores', 'last_admission'}
            or any(not isinstance(provenance.get(key), dict) for key in ('frames', 'sessions', 'branches'))
            or not isinstance(provenance.get('restores'), list)
            or ('frame_clocks' in provenance and not isinstance(provenance['frame_clocks'], dict))):
        raise ValueError('invalid provenance')
    _merge_sessions(empty_reservations(), provenance)
    frames = provenance['frames']
    for frame, position in frames.items():
        if not _FRAME_ID.fullmatch(frame) or not _position(position):
            raise ValueError('invalid frame position')
        labels = _labels(frame, provenance)
        if labels and position['session'] != labels['name']:
            raise ValueError('frame position has a different session name from its sealed identifier')
    for frame, label in provenance.get('frame_clocks', {}).items():
        if not _FRAME_ID.fullmatch(frame) or frame not in frames or not valid_clock_label(label):
            raise ValueError(f'invalid frame_clocks entry for {frame!r}')
    by_id, namespace = {}, {}
    all_keys: set[str] = set()
    active_titles, active_slugs = set(), set()
    axes = declared_axes(provenance, {})
    if _raw_lines is not None and len(_raw_lines) != len(records):
        raise ValueError('mismatched raw fact lines')
    validator = _validator('curator-fact.schema.json')
    for index, row in enumerate(records):
        raw = _raw_lines[index] if _raw_lines is not None else None
        if raw is None or _schema_valid is None or raw not in _schema_valid:
            if not validator.is_valid(row):
                definition = 'stored_article' if isinstance(row, dict) and row.get('record') == 'article' else 'stored_fact'
                errors = _validator('curator-fact.schema.json', definition).iter_errors(row)
                error = next(errors)
                raise ValueError(f'{FACT} {_diagnostic(list(error.path), error.message)}')
            if raw is not None and _schema_valid is not None:
                _schema_valid.add(raw)
        identity, public_id, kind = row['id'], owner(row), row['record']
        if identity in by_id or namespace.get(public_id, kind) != kind:
            raise ValueError(f'duplicate record identity {public_id!r}')
        by_id[identity], namespace[public_id] = row, kind
        if row['scope']['game'] != game or int(row['published_in'][1:]) > int(version[1:]):
            raise ValueError(f'{identity!r} has an invalid scope game or publication version')
        _validate_axes(_axes(row['scope']), axes)
        if kind == 'fact':
            if 'state_key' in row:
                all_keys.add(row['state_key'])
            if 'depiction_source_id' in row and row['depiction_source_id'] not in row['citations']:
                raise ValueError(f'{identity!r}: depiction_source_id must be in citations')
            positions = _frame_positions(row['citations'], provenance)
            if (row['seen'] != max(positions, key=_order) or row['valid_from'] != min(positions, key=_order)):
                raise ValueError(f'{identity!r} has invalid fact positions')
            if 'world' in row['scope'] and (row['scope']['world'] != _citation_world(row['citations'], provenance)
                                            or row['lineages'] != _lineages(row['citations'], provenance)):
                raise ValueError(f'{identity!r} has invalid world or lineage provenance')
        else:
            if identity != f'{public_id}@{row["published_in"]}':
                raise ValueError(f'{identity!r} does not match its article revision')
            if current(row):
                if row['title'] in active_titles or public_id in active_slugs:
                    raise ValueError('current article titles and slugs must be unique')
                active_titles.add(row['title'])
                active_slugs.add(public_id)
    overlap = namespace.keys() & all_keys
    if overlap:
        raise ValueError(f'state_key collides with record ID or article slug: {sorted(overlap)!r}')
    facts = {identity: row for identity, row in by_id.items() if row['record'] == 'fact'}
    for row in records:
        identity = row['id']
        if 'retired' in row:
            _validate_retirement(row, provenance, version, facts)
        if row['record'] == 'article':
            derived = _article_fields(row, facts, provenance)
            if any(row.get(key) != value for key, value in derived.items()):
                raise ValueError(f'{identity!r} has invalid derived article fields')
        for link in row['links']:
            target = link['target']
            if target == owner(row):
                raise ValueError(f'{identity!r} cannot link to itself')
            if link['rel'] == 'depends_on':
                if target == row.get('state_key'):
                    raise ValueError(f'{identity!r} cannot depend on its own state_key')
                if target not in namespace and target not in all_keys:
                    raise ValueError(f'{identity!r} links to unknown target {target!r}')
            elif target not in namespace:
                raise ValueError(f'{identity!r} links to unknown record {target!r}')
        replacements = []
        for successor in row.get('superseded_by', []):
            replacement = by_id.get(successor)
            if (replacement is None or replacement['record'] != row['record']
                    or int(replacement['published_in'][1:]) <= int(row['published_in'][1:])):
                raise ValueError(f'{identity!r} has invalid supersession')
            replacements.append(replacement)
        _validate_successors(row, replacements, provenance, version, facts)
    _validate_keyed_uniqueness(records, provenance)
    _validate_anchors(records)
    _validate_depends_on_acyclicity(records, provenance)
    recomputed = [dict(row) for row in records]
    recompute_flags(recomputed)
    for row, expected in zip(records, recomputed):
        for key in ('lifecycle_state', 'stale_citations', 'needs_review'):
            if row[key] != expected[key]:
                raise ValueError(f'{row["id"]!r} has incorrect stored {key}')
    return by_id
