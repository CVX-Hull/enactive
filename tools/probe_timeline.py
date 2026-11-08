"""Read-only annotation timelines over sealed runs, for the probe protocol (#449).

For one sealed session directory this writes a Markdown timeline per actor: what the actor
received (prompt), each operation in order with its decision index, game clock, input and frame
path, the memory records it wrote, its handoff packet (summary, resolved records, omissions)
and its final report. Annotators work from these files and the frames they point to; nothing
here interprets the game.

Usage: python -m tools.probe_timeline <session-dir> <out-dir> [--evaluation STORE] [--memory STORE]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3


def connect(path: Path) -> sqlite3.Connection:
    """Open a sealed store without writing anything beside it."""
    if not path.is_file():
        raise SystemExit(f'Missing store: {path}')
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)


def clock(seconds: int | None, start: int | None) -> str:
    if seconds is None or start is None:
        return '—'
    elapsed = seconds - start
    return f'+{elapsed // 3600}:{elapsed % 3600 // 60:02d}:{elapsed % 60:02d}'


def summarise_input(kind: str, payload: str) -> str:
    if kind != 'input':
        return kind
    try:
        actions = json.loads(payload)
    except ValueError:
        return 'input (unreadable)'
    parts = []
    for action in actions if isinstance(actions, list) else []:
        if action.get('type') == 'key':
            mods = '+'.join(action.get('modifiers') or [])
            parts.append(f"{mods + '+' if mods else ''}{action.get('key')}")
        elif action.get('type') == 'text':
            parts.append(repr(action.get('text')))
        else:
            parts.append(str(action.get('type')))
    return ' '.join(parts) or 'input'


def records_by_actor(memory: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    with connect(memory) as db:
        for rid, kind, document, supersedes in db.execute('SELECT id, kind, document, supersedes FROM records'):
            doc = json.loads(document)
            out.setdefault(doc.get('actor_id', ''), []).append(dict(id=rid, kind=kind, supersedes=supersedes,
                                                                    created_wall=doc.get('created_wall'),
                                                                    data=doc.get('data')))
    return out


def all_records(memory: Path) -> dict[str, dict]:
    return {r['id']: r for rs in records_by_actor(memory).values() for r in rs}


def write_timelines(session: Path, evaluation: Path, memory: Path | None, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    with connect(session/'session.sqlite3') as db:
        ops = {oid: (actor, kind, payload) for oid, actor, kind, payload in
               db.execute('SELECT id, actor, kind, input_json FROM operations')}
    if evaluation is not None:
        with connect(evaluation) as db:
            steps = list(db.execute('SELECT seq, operation_id, actor, kind, decision, game_time, source_id, '
                                    'frame_changed FROM steps ORDER BY seq'))
    else:
        # No sealed evaluator record: order operations by creation and take each one's last
        # captured frame. There is then no game clock, decision index or change flag.
        with connect(session/'session.sqlite3') as db:
            rows = db.execute(
                'SELECT o.id, o.actor, o.kind, COALESCE(c.source, n.source) FROM operations o '
                'LEFT JOIN native_intents n ON n.operation = o.id LEFT JOIN collections c ON c.native_id = n.id '
                'ORDER BY o.created_wall').fetchall()
        last: dict[str, tuple] = {}
        for op_id, actor, kind, source in rows:
            previous = last.get(op_id)
            if previous is None:
                last[op_id] = (op_id, actor, kind, source)
            elif source is not None and (previous[3] is None or int(source.rsplit('-', 1)[1]) >
                                         int(previous[3].rsplit('-', 1)[1])):
                last[op_id] = (op_id, actor, kind, source)
        steps = [(i + 1, op, actor, kind, None, None, source, None)
                 for i, (op, actor, kind, source) in enumerate(last.values())]
    start = next((s[5] for s in steps if s[5] is not None), None)
    records = records_by_actor(memory) if memory else {}
    known = all_records(memory) if memory else {}
    contexts = {}
    for path in sorted((session/'contexts').glob('*.json')):
        doc = json.loads(path.read_text())
        contexts[doc.get('actor_id')] = doc
    written = []
    actors = sorted((session/'actors').iterdir())
    for directory in actors:
        actor_id = json.loads((directory/'frozen.json').read_text()).get('actor_id') if (directory/'frozen.json').exists() else None
        rows = [s for s in steps if actor_id is None or s[2] == actor_id]
        lines = [f'# {session.name} actor {directory.name}', '',
                 f'Actor ID `{actor_id}`. Game clock is elapsed time from the run\'s first read clock.', '',
                 '## What this actor received', '', '```', (directory/'prompt.txt').read_text(errors='replace').strip(),
                 '```', '', '## Operations', '',
                 '"changed" is the evaluator\'s mechanical frame-difference flag: `no` means the frame '
                 'matches the previous one.', '',
                 '| seq | decision | game clock | operation | changed | frame |',
                 '| ---: | ---: | --- | --- | --- | --- |']
        for seq, op_id, _actor, kind, decision, game_time, source, changed in rows:
            _a, op_kind, payload = ops.get(op_id, (None, kind, '[]'))
            frame = str(session/'sources'/f'{source}.png') if source and (session/'sources'/f'{source}.png').exists() else ''
            flag = {1: 'yes', 0: 'no'}.get(changed, '')
            lines.append(f'| {seq} | {decision if decision is not None else ""} | {clock(game_time, start)} | '
                         f'{summarise_input(op_kind, payload).replace("|", "/")} | {flag} | {frame} |')
        lines += ['', '## Memory records this actor wrote', '']
        for record in sorted(records.get(actor_id, []), key=lambda r: r['created_wall'] or 0):
            lines += [f"- `{record['id'][:6]}` ({record['kind']}): {json.dumps(record['data'], ensure_ascii=False)}"]
        context = contexts.get(actor_id)
        lines += ['', '## Handoff packet this actor sealed', '']
        if context:
            lines.append(f"Summary: {context.get('summary')}")
            knowledge = context.get('knowledge') or {}
            for rid in knowledge.get('roots', []):
                record = known.get(rid)
                lines.append(f"- root `{rid[:6]}`: " + (json.dumps(record['data'], ensure_ascii=False) if record
                                                     else 'not a stored record'))
            for omission in knowledge.get('omissions', []):
                lines.append(f"- omission: {omission.get('reason')}")
        else:
            lines.append('None.')
        final = directory/'player-final.txt'
        lines += ['', '## Final report', '', final.read_text(errors='replace').strip() if final.exists() else 'None.', '']
        target = out/f'{session.name}-{directory.name}.md'
        target.write_text('\n'.join(lines))
        written.append(target)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--evaluation', type=Path, help='sealed evaluator store, when one exists')
    parser.add_argument('--memory', type=Path, help='sealed player-memory/2 store')
    args = parser.parse_args(argv)
    for path in write_timelines(args.session, args.evaluation, args.memory, args.out):
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
