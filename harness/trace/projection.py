"""Allowlisted projection of sealed session stores into a curator `trace/` (#452).

The projection copies what the actor saw and did, and nothing else. Each output field is
named here; a session directory is never copied wholesale. Never projected: custody tokens
(`actor.json`), routes and provider settings (`route.json`), MCP and host configuration,
process records, custodian, viewer and watch files, receipts and logs. Identities that
grant nothing (session, actor and operation IDs) are kept, because they are how frames and
steps are cited. Frames are copied byte for byte after their SHA-256 is checked against the
sealed source metadata.

Layout written under `out`:
  manifest.json                          trace-projection/1: what was projected, with hashes
  frames/<source_id>.png                 frames, verified
  <session>/<actor>/steps.jsonl          operations in order: kind, input actions, status, frame
  <session>/<actor>/tools.jsonl          tool calls: name, allowlisted arguments, outcome
  <session>/<actor>/received.txt         what the actor was given (its prompt)
  <session>/<actor>/final.txt            its final report, when one exists
  <session>/handoffs/<context_id>.json   sealed handoff packets: summary and knowledge
  memory.json                            the sealed player-memory/2 store, via the evidence reader

There are no emissions or hints in traces recorded before ADR 009; the manifest says so
rather than writing empty files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from . import memory_reader

SCHEMA = 'trace-projection/1'
ACTION_FIELDS = ('type', 'key', 'modifiers', 'text', 'x', 'y', 'button', 'source_id')
RECORD_FIELDS = ('kind', 'text', 'data', 'sources', 'supports', 'supersedes', 'applicability', 'program_id')
TOOL_ARGUMENTS = {
    'computer_input': ('actions',),
    'computer_observe': (),
    'computer_result': ('operation_id',),
    'player_source': ('source_id',),
    'player_result': ('operation_id',),
    'player_handoff': ('ids', 'summary'),
    'player_memory_append': ('record',),
    'player_memory_read': ('ids',),
    'player_memory_query': ('kind', 'limit', 'include_superseded', 'text'),
    'player_memory_context': ('ids', 'max_bytes'),
    'player_program_read': ('program_id',),
    'player_program_run': ('program_id', 'max_steps', 'max_seconds'),
    'player_program_save': ('program',),
}
RESULT_FIELDS = ('schema', 'operation_id', 'kind', 'status', 'reason', 'id', 'error', 'submission')
NEVER = ('actor.json', 'route.json', 'mcp.json', 'mcp-template.json', 'host-process.json', 'frozen.json',
         'driver-receipt.json', 'host-stderr.log', 'host.jsonl (raw)', 'custodian-*', 'native-*', 'viewer-*',
         'watch-*', 'receipt.json', 'started.json', 'ready.json', 'target.json', 'orderly-stop.json',
         'context.txt (host configuration)', 'session.sqlite3 (raw)')


class ProjectionError(ValueError):
    """A sealed input is missing or inconsistent."""


def _connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ProjectionError(f'{path}: missing store')
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)


def _pick(value: dict, fields) -> dict:
    return {k: value[k] for k in fields if k in value}


def _action(value) -> dict | None:
    return _pick(value, ACTION_FIELDS) if isinstance(value, dict) else None


def _arguments(tool: str, arguments) -> dict:
    if not isinstance(arguments, dict):
        return {}
    kept = _pick(arguments, TOOL_ARGUMENTS.get(tool, ()))
    if 'actions' in kept:
        kept['actions'] = [a for a in map(_action, kept['actions'] or []) if a is not None]
    if 'record' in kept and isinstance(kept['record'], dict):
        kept['record'] = _pick(kept['record'], RECORD_FIELDS)
    if 'program' in kept and isinstance(kept['program'], dict):
        kept['program'] = _pick(kept['program'], ('code', 'reason', 'parent_id', 'record_ids', 'source_ids'))
    return kept


def _result(result) -> dict:
    """The outcome of a tool call: error flag plus allowlisted fields of its JSON text."""
    out = dict(error=bool(isinstance(result, dict) and result.get('isError')))
    for part in (result or {}).get('content', []) if isinstance(result, dict) else []:
        if isinstance(part, dict) and part.get('type') == 'text':
            try:
                value = json.loads(part['text'])
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                out.update(_pick(value, RESULT_FIELDS))
                source = value.get('source')
                if isinstance(source, dict) and isinstance(source.get('source_id'), str):
                    out['source_id'] = source['source_id']
    return out


def _write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
            count += 1
    return count


def _steps(session: Path) -> tuple[str, dict[str, list[dict]], dict[str, dict]]:
    with _connect(session/'session.sqlite3') as db:
        session_id = json.loads(dict(db.execute("SELECT key, value FROM metadata"))['session'])
        sources = {sid: json.loads(meta) for sid, meta in db.execute('SELECT id, metadata FROM sources')}
        rows = db.execute(
            'SELECT o.id, o.actor, o.kind, o.created_wall, o.input_json, o.final_json, '
            'COALESCE(c.source, n.source) FROM operations o '
            'LEFT JOIN native_intents n ON n.operation = o.id LEFT JOIN collections c ON c.native_id = n.id '
            'ORDER BY o.created_wall, o.id').fetchall()
    by_operation: dict[str, dict] = {}
    for op_id, actor, kind, wall, payload, final, source in rows:
        step = by_operation.get(op_id)
        if step is None:
            try:
                actions = json.loads(payload)
            except ValueError:
                actions = []
            status = None
            if final:
                try:
                    status = json.loads(final).get('status')
                except (ValueError, AttributeError):
                    status = None
            step = by_operation[op_id] = dict(operation_id=op_id, actor_id=actor, kind=kind, created_wall=wall,
                                              actions=[a for a in map(_action, actions if isinstance(actions, list)
                                                                      else []) if a is not None],
                                              status=status, frame=None)
        if source and (step['frame'] is None or int(source.rsplit('-', 1)[1]) > int(step['frame'].rsplit('-', 1)[1])):
            step['frame'] = source
    per_actor: dict[str, list[dict]] = {}
    for step in by_operation.values():
        per_actor.setdefault(step['actor_id'], []).append(step)
    for steps in per_actor.values():
        steps.sort(key=lambda s: (s['created_wall'], s['operation_id']))
        for seq, step in enumerate(steps, 1):
            step['seq'] = seq
    return session_id, per_actor, sources


def project(sessions: list[Path], out: Path, *, memory: Path | None = None) -> dict:
    """Project sealed sessions into `out` (which must not exist). Returns the manifest."""
    if out.exists():
        raise ProjectionError(f'{out}: projection target must not exist')
    (out/'frames').mkdir(parents=True)
    hashes: dict[str, str] = {}

    def record_file(path: Path):
        hashes[str(path.relative_to(out))] = hashlib.sha256(path.read_bytes()).hexdigest()

    projected = []
    for session in sessions:
        session_id, per_actor, sources = _steps(session)
        actors = []
        for directory in sorted((session/'actors').iterdir()):
            frozen = json.loads((directory/'frozen.json').read_text()) if (directory/'frozen.json').exists() else {}
            actor_id = frozen.get('actor_id')
            steps = per_actor.get(actor_id, [])
            target = out/session.name/directory.name
            target.mkdir(parents=True)
            frames = 0
            for step in steps:
                sid = step['frame']
                if sid is None or (out/'frames'/f'{sid}.png').exists():
                    continue
                png = session/'sources'/f'{sid}.png'
                meta = sources.get(sid)
                if not png.is_file() or meta is None:
                    step['frame'] = None  # referenced but not sealed: never invent one
                    continue
                if hashlib.sha256(png.read_bytes()).hexdigest() != meta.get('sha256'):
                    raise ProjectionError(f'{png}: SHA-256 differs from sealed metadata')
                shutil.copyfile(png, out/'frames'/f'{sid}.png')
                record_file(out/'frames'/f'{sid}.png')
                frames += 1
            _write_jsonl(target/'steps.jsonl', ({k: s[k] for k in ('seq', 'operation_id', 'kind', 'created_wall',
                                                                    'actions', 'status', 'frame')} for s in steps))
            record_file(target/'steps.jsonl')
            tools = []
            host = directory/'host.jsonl'
            if host.is_file():
                starts = {}
                for line in host.read_text().splitlines():
                    event = json.loads(line)
                    if event.get('type') == 'tool-start':
                        starts[event.get('tool_call_id')] = event
                    elif event.get('type') == 'tool-result':
                        start = starts.get(event.get('tool_call_id'), {})
                        tool = event.get('tool') or start.get('tool')
                        tools.append(dict(tool=tool, wall_time=event.get('wall_time'),
                                          arguments=_arguments(tool, start.get('arguments')),
                                          outcome=_result(event.get('result'))))
            _write_jsonl(target/'tools.jsonl', tools)
            record_file(target/'tools.jsonl')
            for name, out_name in (('prompt.txt', 'received.txt'), ('player-final.txt', 'final.txt')):
                if (directory/name).is_file():
                    shutil.copyfile(directory/name, target/out_name)
                    record_file(target/out_name)
            actors.append(dict(directory=directory.name, actor_id=actor_id, steps=len(steps), frames=frames,
                               tool_calls=len(tools)))
        handoffs = []
        for path in sorted((session/'contexts').glob('*.json')) if (session/'contexts').is_dir() else []:
            doc = json.loads(path.read_text())
            kept = _pick(doc, ('schema', 'context_id', 'session', 'actor_id', 'summary', 'knowledge',
                               'created_wall', 'grants_authority'))
            target = out/session.name/'handoffs'/f'{path.stem}.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(kept, sort_keys=True, ensure_ascii=False, indent=1))
            record_file(target)
            handoffs.append(path.stem)
        projected.append(dict(name=session.name, session_id=session_id, actors=actors, handoffs=handoffs))
    if memory is not None:
        store = memory_reader.read(memory)
        (out/'memory.json').write_text(json.dumps(store, sort_keys=True, ensure_ascii=False, indent=1))
        record_file(out/'memory.json')
    manifest = dict(schema=SCHEMA, sessions=projected, files=hashes, never_projected=list(NEVER),
                    emissions='none recorded (traces predate ADR 009 emissions)',
                    hints='none recorded (traces predate ADR 009 hints)')
    (out/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=1))
    return manifest
