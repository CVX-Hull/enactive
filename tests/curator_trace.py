"""A synthetic sealed session with many steps, for the curator's window tests (#460). No game, no provider.

Each actor has `steps` operations, one frame per operation and one `computer_input` tool call per operation
(its result names the operation). Every third operation is preceded by a `player_memory_read` call that names
no operation, the kind of call a window assigns by position. Each actor has a final report; the session has a
handoff packet.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from tests.test_trace_projection import png

SESSION_ID = 'a' * 32


def frame_id(actor: int, step: int) -> str:
    return f'{SESSION_ID}-{actor * 1000 + step}'


def make_long_session(root: Path, name: str = 's1', steps: int = 12, actors: tuple[str, ...] = ('001', '002')) -> Path:
    session = root/name
    (session/'sources').mkdir(parents=True)
    (session/'contexts').mkdir()
    db = sqlite3.connect(session/'session.sqlite3')
    db.executescript('''
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources(id TEXT PRIMARY KEY, metadata TEXT NOT NULL, bytes INTEGER NOT NULL);
        CREATE TABLE operations(id TEXT PRIMARY KEY, actor TEXT NOT NULL, kind TEXT NOT NULL, created_wall REAL NOT NULL,
            deadline REAL NOT NULL, input_json TEXT NOT NULL, final_json TEXT);
        CREATE TABLE native_intents(id TEXT PRIMARY KEY, operation TEXT NOT NULL, receipt TEXT, source TEXT, timing TEXT NOT NULL);
        CREATE TABLE collections(native_id TEXT PRIMARY KEY, receipt TEXT NOT NULL, source TEXT);''')
    db.execute("INSERT INTO metadata VALUES('session', ?)", (json.dumps(SESSION_ID),))
    for number, directory in enumerate(actors, 1):
        actor_id = f'{number:x}' * 32
        actor_dir = session/'actors'/directory
        actor_dir.mkdir(parents=True)
        (actor_dir/'frozen.json').write_text(json.dumps(dict(actor_id=actor_id)))
        (actor_dir/'prompt.txt').write_text(f'Play the game as actor {directory}.')
        (actor_dir/'player-final.txt').write_text(f'Actor {directory} report: everything, including the end.')
        events = []
        for step in range(1, steps + 1):
            sid, op = frame_id(number, step), f'op-{number}-{step}'
            data = png((step * 7 % 256, number * 40, 90))
            (session/'sources'/f'{sid}.png').write_bytes(data)
            db.execute('INSERT INTO sources VALUES(?,?,?)',
                       (sid, json.dumps(dict(source_id=sid, sha256=hashlib.sha256(data).hexdigest())), len(data)))
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', (op, actor_id, 'input', float(number * 1000 + step), 9e9,
                       json.dumps([dict(type='key', key='RIGHT', modifiers=[])]), json.dumps(dict(status='completed'))))
            db.execute('INSERT INTO native_intents VALUES(?,?,NULL,?, ?)', (f'n-{number}-{step}', op, sid, 't'))
            if step % 3 == 0:
                events += [dict(type='tool-start', tool_call_id=f'm{step}', tool='player_memory_read', arguments=dict(record_id=f'r{step}')),
                           dict(type='tool-result', tool_call_id=f'm{step}', tool='player_memory_read', wall_time='t',
                                result=dict(isError=False, content=[dict(type='text', text=json.dumps(dict(records=[])))]))]
            events += [dict(type='tool-start', tool_call_id=f'c{step}', tool='computer_input',
                            arguments=dict(actions=[dict(type='key', key='RIGHT', modifiers=[])])),
                       dict(type='tool-result', tool_call_id=f'c{step}', tool='computer_input', wall_time='t',
                            result=dict(isError=False, content=[dict(type='text', text=json.dumps(dict(
                                schema='player-computer-result/1', operation_id=op, status='completed',
                                source=dict(source_id=sid))))]))]
        (actor_dir/'host.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    db.commit()
    db.close()
    (session/'contexts'/'ctx.json').write_text(json.dumps(dict(
        schema='player-handoff-context/1', context_id='ctx', summary='carry on', knowledge={})))
    return session
