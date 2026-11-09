"""Allowlisted projection of sealed session stores into a curator `trace/` (#452).

The projection copies what the actor saw and did, and nothing else. Each structured field
is named here; a session directory is never copied wholesale. Never projected: custody
tokens (`actor.json`), routes and provider settings (`route.json`), MCP and host
configuration, process records, custodian, viewer and watch files, receipts and logs.
Identities that grant nothing (session, actor and operation IDs) are kept, because they are
how frames and steps are cited. Frames are copied byte for byte after their SHA-256 matches
the sealed source metadata.

Some channels are free text the actor or a service wrote: its report, handoff summaries and
knowledge, memory records, and error reasons. An allowlist cannot vet free text, so every
projection ends with a **fail-closed secret guard**: the written bytes are scanned for every
value of the sessions' custody and route files and for key-like patterns. On any hit,
nothing is published. The projection is built in a sibling directory and renamed into place
only when complete, so a failure never leaves a partial `trace/`.

Layout written under `out`:
  manifest.json                          trace-projection/1: what was projected, with hashes
  frames/<source_id>.png                 frames, verified
  <session>/<actor>/steps.jsonl          operations in order: kind, input actions, status, frame
  <session>/<actor>/tools.jsonl          tool calls: name, allowlisted arguments, outcome
  <session>/<actor>/received.txt         the actor's prompt
  <session>/<actor>/guide.txt            the working guide it was given
  <session>/<actor>/final.txt            its final report, when one exists
  <session>/handoffs/<context_id>.json   sealed handoff packets: summary and knowledge
  memory.json                            the sealed player-memory/2 store, via the evidence reader

Traces recorded before ADR 009 have no emissions or hints; the manifest says so instead of
writing empty files. What the projection drops is listed in the manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import uuid

from . import memory_reader
from .stores import SealedStoreError, sealed

SCHEMA = 'trace-projection/1'
ACTION_FIELDS = ('type', 'key', 'modifiers', 'text', 'seconds', 'x', 'y', 'button')
RECORD_FIELDS = ('kind', 'text', 'data', 'sources', 'supports', 'supersedes', 'applicability', 'program_id')
TOOL_ARGUMENTS = {
    'computer_input': ('actions', 'source_id'),
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
         'session.sqlite3 (raw)')
DROPPED = ('host request and response telemetry', 'contents returned by memory queries and player_result '
           '(the records themselves are in memory.json)', 'receipts and timing of native intents')
KEY_PATTERN = re.compile(rb'sk-[A-Za-z0-9_-]{16,}|Bearer [A-Za-z0-9._-]{16,}')
SECRET_FILES = ('actor.json', 'route.json', 'mcp.json', 'mcp-template.json', 'host-process.json')
GRANTS_NOTHING = ('actor_id', 'session', 'schema')


class ProjectionError(ValueError):
    """A sealed input is missing or inconsistent, or the projection would carry a secret."""


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


def _json(path: Path):
    if path.is_symlink():
        raise ProjectionError(f'{path}: symbolic link in sealed evidence')
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ProjectionError(f'{path}: unreadable JSON') from exc


def _copy(source: Path, dest: Path) -> None:
    if source.is_symlink():
        raise ProjectionError(f'{source}: symbolic link in sealed evidence')
    shutil.copyfile(source, dest)


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')


SECRET_KEY = re.compile(r'token|key|secret|auth|password|credential|url|endpoint', re.IGNORECASE)


def _secrets(session: Path) -> set[bytes]:
    """Every value the guard must not find: custody tokens, custodian URLs, routes, keys.

    Values under credential- or address-like keys, and any URL anywhere, in the session's
    custody, route, MCP and process files. Identities the projection keeps by design (session
    and actor IDs) are excluded, so the guard does not fire on its own citations.
    """
    found: set[bytes] = set()
    for name in SECRET_FILES:
        for path in session.glob(f'actors/*/{name}'):
            try:
                stack = [(None, json.loads(path.read_text()))]
            except (OSError, ValueError):
                continue
            while stack:
                key, item = stack.pop()
                if isinstance(item, dict):
                    stack.extend((k, v) for k, v in item.items() if k not in GRANTS_NOTHING)
                elif isinstance(item, list):
                    stack.extend((key, v) for v in item)
                elif isinstance(item, str) and len(item) >= 8 and (
                        '://' in item or (key is not None and SECRET_KEY.search(key))):
                    found.add(item.encode())
    try:
        with sealed(session/'session.sqlite3') as db:
            keep = {json.loads(dict(db.execute('SELECT key, value FROM metadata'))['session'])}
            keep |= {row[0] for row in db.execute('SELECT id FROM actors')}
    except (SealedStoreError, sqlite3.Error, ValueError, KeyError):
        keep = set()
    return {s for s in found if s.decode() not in keep}


def _steps(session: Path, session_id: str) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    frame_id = re.compile(re.escape(session_id) + r'-([0-9]+)')
    try:
        with sealed(session/'session.sqlite3') as db:
            sources = {sid: json.loads(meta) for sid, meta in db.execute('SELECT id, metadata FROM sources')}
            rows = db.execute(
                'SELECT o.id, o.actor, o.kind, o.created_wall, o.input_json, o.final_json, '
                'COALESCE(c.source, n.source) FROM operations o '
                'LEFT JOIN native_intents n ON n.operation = o.id LEFT JOIN collections c ON c.native_id = n.id '
                'ORDER BY o.created_wall, o.id').fetchall()
    except (SealedStoreError, sqlite3.Error, ValueError) as exc:
        raise ProjectionError(f'{session}: unreadable session store: {exc}') from exc
    by_operation: dict[str, dict] = {}
    for op_id, actor, kind, wall, payload, final, source in rows:
        if source is not None and frame_id.fullmatch(source) is None:
            raise ProjectionError(f'{session}: frame id outside this session: {source!r}')
        step = by_operation.get(op_id)
        if step is None:
            try:
                actions = json.loads(payload)
                status = json.loads(final).get('status') if final else None
            except (ValueError, AttributeError) as exc:
                raise ProjectionError(f'{session}: unreadable operation {op_id}') from exc
            step = by_operation[op_id] = dict(
                operation_id=op_id, actor_id=actor, kind=kind, created_wall=wall, status=status, frame=None,
                actions=[a for a in map(_action, actions if isinstance(actions, list) else []) if a is not None])
        if source and (step['frame'] is None
                       or int(frame_id.fullmatch(source)[1]) > int(frame_id.fullmatch(step['frame'])[1])):
            step['frame'] = source
    per_actor: dict[str, list[dict]] = {}
    for step in by_operation.values():
        per_actor.setdefault(step['actor_id'], []).append(step)
    for steps in per_actor.values():
        steps.sort(key=lambda s: (s['created_wall'], s['operation_id']))
        for seq, step in enumerate(steps, 1):
            step['seq'] = seq
    return per_actor, sources


def _tools(host: Path) -> list[dict]:
    if not host.is_file():
        return []
    if host.is_symlink():
        raise ProjectionError(f'{host}: symbolic link in sealed evidence')
    starts, calls = {}, []
    for number, line in enumerate(host.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise ProjectionError(f'{host}:{number}: unreadable event') from exc
        kind = event.get('type')
        if kind == 'tool-start':
            starts[event.get('tool_call_id')] = event
        elif kind in ('tool-result', 'tool-refused'):
            start = starts.pop(event.get('tool_call_id'), {})
            tool = event.get('tool') or start.get('tool')
            outcome = _result(event.get('result')) if kind == 'tool-result' else dict(
                refused=True, reason=event.get('reason') if isinstance(event.get('reason'), str) else None)
            calls.append(dict(tool=tool, wall_time=event.get('wall_time'),
                              arguments=_arguments(tool, start.get('arguments')), outcome=outcome))
    for start in starts.values():  # started but never answered
        calls.append(dict(tool=start.get('tool'), wall_time=start.get('wall_time'),
                          arguments=_arguments(start.get('tool'), start.get('arguments')),
                          outcome=dict(unfinished=True)))
    return calls


def _cut(store: dict, until: float | None) -> dict:
    """The store with only what existed strictly before `until` (wall clock).

    `None` keeps everything. Records and programs need a numeric `created_wall` below the cutoff;
    a row without one cannot be placed before it, so a cut store drops it. A source is kept when its
    `metadata.received_wall` is a number below the cutoff. A source without a numeric
    `received_wall` is kept only when a kept record (`sources`) or program (`source_ids`) cites it."""
    if until is None:
        return store

    def number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def written(row: dict) -> bool:
        return number(row.get('created_wall')) and row['created_wall'] < until

    records = [r for r in store['records'] if written(r)]
    programs = [p for p in store['programs'] if written(p)]
    cited = {s for r in records for s in r.get('sources') or []} | {s for p in programs for s in p.get('source_ids') or []}

    def seen(source: dict) -> bool:
        wall = (source.get('metadata') or {}).get('received_wall')
        return wall < until if number(wall) else source['id'] in cited

    return dict(store, records=records, programs=programs, sources=[s for s in store['sources'] if seen(s)])


def _project_into(sessions: list[Path], out: Path, memory: Path | None, memory_until: float | None = None) -> dict:
    (out/'frames').mkdir(parents=True)
    hashes: dict[str, str] = {}

    def record_file(path: Path):
        hashes[str(path.relative_to(out))] = hashlib.sha256(path.read_bytes()).hexdigest()

    if len({s.name for s in sessions}) != len(sessions):
        raise ProjectionError('Two sessions share a name')
    projected = []
    for session in sessions:
        try:
            with sealed(session/'session.sqlite3') as db:
                session_id = json.loads(dict(db.execute('SELECT key, value FROM metadata'))['session'])
        except (SealedStoreError, sqlite3.Error, ValueError, KeyError) as exc:
            raise ProjectionError(f'{session}: unreadable session identity') from exc
        per_actor, sources = _steps(session, session_id)
        actors = []
        for directory in sorted(p for p in (session/'actors').iterdir() if p.is_dir() and not p.is_symlink()):
            if not (directory/'frozen.json').is_file():
                raise ProjectionError(f'{directory}: no frozen inputs, so the actor cannot be identified')
            actor_id = _json(directory/'frozen.json').get('actor_id')
            steps = per_actor.get(actor_id, [])
            target = out/session.name/directory.name
            target.mkdir(parents=True)
            frames = 0
            for step in steps:
                sid = step['frame']
                if sid is None or (out/'frames'/f'{sid}.png').exists():
                    continue
                png, meta = session/'sources'/f'{sid}.png', sources.get(sid)
                if png.is_symlink() or not png.is_file() or meta is None:
                    step['frame'] = None  # referenced but not sealed: never invent one
                    continue
                if hashlib.sha256(png.read_bytes()).hexdigest() != meta.get('sha256'):
                    raise ProjectionError(f'{png}: SHA-256 differs from sealed metadata')
                _copy(png, out/'frames'/f'{sid}.png')
                record_file(out/'frames'/f'{sid}.png')
                frames += 1
            _write_jsonl(target/'steps.jsonl', ({k: s[k] for k in ('seq', 'operation_id', 'kind', 'created_wall',
                                                                    'actions', 'status', 'frame')} for s in steps))
            record_file(target/'steps.jsonl')
            tools = _tools(directory/'host.jsonl')
            _write_jsonl(target/'tools.jsonl', tools)
            record_file(target/'tools.jsonl')
            for name, out_name in (('prompt.txt', 'received.txt'), ('context.txt', 'guide.txt'),
                                   ('player-final.txt', 'final.txt')):
                if (directory/name).is_file() or (directory/name).is_symlink():
                    _copy(directory/name, target/out_name)
                    record_file(target/out_name)
            actors.append(dict(directory=directory.name, actor_id=actor_id, steps=len(steps), frames=frames,
                               tool_calls=len(tools)))
        handoffs = []
        for path in sorted((session/'contexts').glob('*.json')) if (session/'contexts').is_dir() else []:
            kept = _pick(_json(path), ('schema', 'context_id', 'session', 'actor_id', 'summary', 'knowledge',
                                       'created_wall', 'grants_authority'))
            target = out/session.name/'handoffs'/f'{path.stem}.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(kept, sort_keys=True, ensure_ascii=False, indent=1))
            record_file(target)
            handoffs.append(path.stem)
        projected.append(dict(name=session.name, session_id=session_id, actors=actors, handoffs=handoffs))
    if memory is not None:
        try:
            store = _cut(memory_reader.read(memory), memory_until)
        except memory_reader.StoreError as exc:
            raise ProjectionError(str(exc)) from exc
        (out/'memory.json').write_text(json.dumps(store, sort_keys=True, ensure_ascii=False, indent=1))
        record_file(out/'memory.json')
    manifest = dict(schema=SCHEMA, sessions=projected, files=hashes, never_projected=list(NEVER),
                    dropped=list(DROPPED), secret_guard='passed',
                    emissions='none recorded (traces predate ADR 009 emissions)',
                    hints='none recorded (traces predate ADR 009 hints)')
    (out/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=1))
    return manifest


def guard(out: Path, secrets: set[bytes]) -> None:
    """Fail closed: raise if any written byte carries a known secret or a key-like string."""
    for path in sorted(p for p in out.rglob('*') if p.is_file()):
        data = path.read_bytes()
        if any(secret in data for secret in secrets) or KEY_PATTERN.search(data):
            raise ProjectionError(f'Secret guard: {path.relative_to(out)} carries a custody, route or key value; '
                                  'nothing was projected')


def project(sessions: list[Path], out: Path, *, memory: Path | None = None, memory_until: float | None = None) -> dict:
    """Project sealed sessions into `out` (which must not exist). Returns the manifest.

    `memory_until` keeps only the memory records, programs and sources written strictly before it."""
    if out.exists():
        raise ProjectionError(f'{out}: projection target must not exist')
    partial = out.with_name(f'.{out.name}.partial-{uuid.uuid4().hex[:8]}')
    try:
        manifest = _project_into(sessions, partial, memory, memory_until)
        guard(partial, set().union(*(_secrets(s) for s in sessions)) if sessions else set())
        partial.rename(out)
        return manifest
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
