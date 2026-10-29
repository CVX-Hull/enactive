"""Whole-node bounded support/lineage projection; never game certification."""
from __future__ import annotations

from collections import deque
import sqlite3

from harness.computer.protocol import source as validate_source
from .contracts import PlayerError, bounded_integer, canonical, identity, json_object

_MAX_NODES = 128


def build_context(memory, ids: list[str], *, max_bytes: int = 65536) -> dict:
    bounded_integer(max_bytes, 1, 65536)
    if type(ids) is not list or len(ids) > 32:
        raise PlayerError('Context selects at most 32 roots')
    for item_id in ids:
        identity(item_id)
    packet = dict(schema='player-context/1', roots=list(ids), records=[], programs=[], sources=[], omissions=[])
    # Reserve a whole omission for every root. If even that cannot fit, refuse
    # explicitly instead of silently returning an incomplete envelope.
    minimal = dict(packet, records=[], programs=[], sources=[],
                   omissions=[dict(id=i, reason='byte limit; dependencies not expanded') for i in dict.fromkeys(ids)])
    if len(canonical(minimal).encode('utf-8')) > max_bytes:
        raise PlayerError('Context byte limit cannot hold explicit root omissions')
    queue = deque((None, i) for i in dict.fromkeys(ids))
    seen = set()
    count = 0

    def fits(candidate):
        return len(canonical(candidate).encode('utf-8')) <= max_bytes

    def omit(item_id, reason):
        packet['omissions'].append(dict(id=item_id, reason=reason))

    try:
        # One consistent SQLite read snapshot across the projection.
        with memory._db:
            memory._db.execute('BEGIN')
            while queue:
                kind, item_id = queue.popleft()
                if (kind, item_id) in seen:
                    continue
                seen.add((kind, item_id))
                if kind is None:
                    row = memory._db.execute('SELECT 1 FROM records WHERE id=?', (item_id,)).fetchone()
                    kind = 'record' if row else 'program'
                    if (kind, item_id) in seen:
                        continue
                    seen.add((kind, item_id))
                if count >= _MAX_NODES:
                    omit(item_id, 'closure limit; dependencies not expanded')
                    continue
                count += 1
                if kind == 'correction-overflow':
                    omit(item_id, 'additional corrections omitted beyond closure bound')
                    continue
                refs = []
                try:
                    if kind == 'source':
                        row = memory._db.execute('SELECT metadata,png IS NOT NULL FROM sources WHERE id=?', (item_id,)).fetchone()
                        if row is None:
                            raise PlayerError('Source reference unavailable')
                        metadata = json_object(row[0])
                        validate_source(metadata)
                        if metadata['source_id'] != item_id:
                            raise PlayerError('Source identity differs')
                        node = dict(source=metadata, available=bool(row[1]), read_verified=False)
                        field = 'sources'
                    else:
                        node = memory._document('records' if kind == 'record' else 'programs', item_id)
                        field = 'records' if kind == 'record' else 'programs'
                        if kind == 'record':
                            refs.extend(('record', ref) for ref in node['supports'])
                            if node['supersedes']:
                                refs.append(('record', node['supersedes']))
                            if node['program_id']:
                                refs.append(('program', node['program_id']))
                            refs.extend(('source', ref) for ref in node['sources'])
                            # Retain contradictions to selected prior claims; bounded
                            # forward expansion never chooses a "true" correction.
                            rows = memory._db.execute('SELECT id FROM records WHERE supersedes=? ORDER BY rowid LIMIT ?',
                                                      (item_id, _MAX_NODES + 1)).fetchall()
                            refs.extend(('record', row[0]) for row in rows[:_MAX_NODES])
                            if len(rows) > _MAX_NODES:
                                refs.append(('correction-overflow', item_id))
                        else:
                            if node['parent_id']:
                                refs.append(('program', node['parent_id']))
                            refs.extend(('record', ref) for ref in node['record_ids'])
                            refs.extend(('source', ref) for ref in node['source_ids'])
                except (PlayerError, ValueError) as exc:
                    omit(item_id, str(exc))
                    continue
                candidate = {**packet, field: packet[field] + [node]}
                # Reserve omission bytes for the bounded frontier before including
                # a whole record/program. Dependencies remain exact in that node.
                future = list(dict.fromkeys(list(queue) + refs))
                reserve = [dict(id=i, reason='byte limit; dependencies not expanded')
                           for k, i in future if (k, i) not in seen]
                candidate['omissions'] = packet['omissions'] + reserve
                if not fits(candidate):
                    omit(item_id, 'byte limit; dependencies not expanded')
                    continue
                packet[field].append(node)
                queue.extend(refs)
                if kind == 'source' and not node['available']:
                    omit(item_id, 'source bytes unavailable; reference is not read proof')
            if not fits(packet):
                # Diagnostics themselves can exceed a tiny requested bound. Return
                # explicit root omissions, never truncated records or code.
                return minimal
            return packet
    except sqlite3.Error as exc:
        raise PlayerError(f'Cannot construct player context: {exc}') from exc
