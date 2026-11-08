"""Trace projection and the sealed-memory evidence reader (#452).

The synthetic fixture is portable. The real-evidence scan projects the sealed #397 lineage
and skips when the evidence store is absent from this checkout.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3

from PIL import Image
import pytest

from harness.trace import memory_reader
from harness.trace.projection import ProjectionError, project

ROOT = Path(__file__).resolve().parents[1]
# A worktree has no evidence store; ENACTIVE_EVIDENCE_ROOT points at a checkout's sealed store.
EVIDENCE = Path(os.environ.get('ENACTIVE_EVIDENCE_ROOT', ROOT/'.runtime'/'evidence'))/'397-seven-day'
TOKEN = 'secret-custody-token-0123456789abcdef'
BASE_URL = 'http://127.0.0.1:52341'
ROUTE_KEY = 'provider-route-key-should-never-appear'


def png(color) -> bytes:
    stream = io.BytesIO()
    Image.new('RGB', (4, 4), color).save(stream, format='PNG')
    return stream.getvalue()


def make_session(root: Path, name='s1') -> Path:
    session = root/name
    (session/'sources').mkdir(parents=True)
    (session/'contexts').mkdir()
    actor_dir = session/'actors'/'001'
    actor_dir.mkdir(parents=True)
    db = sqlite3.connect(session/'session.sqlite3')
    db.executescript('''
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources(id TEXT PRIMARY KEY, metadata TEXT NOT NULL, bytes INTEGER NOT NULL);
        CREATE TABLE operations(id TEXT PRIMARY KEY, actor TEXT NOT NULL, kind TEXT NOT NULL, created_wall REAL NOT NULL,
            deadline REAL NOT NULL, input_json TEXT NOT NULL, final_json TEXT);
        CREATE TABLE native_intents(id TEXT PRIMARY KEY, operation TEXT NOT NULL, receipt TEXT, source TEXT, timing TEXT NOT NULL);
        CREATE TABLE collections(native_id TEXT PRIMARY KEY, receipt TEXT NOT NULL, source TEXT);''')
    db.execute("INSERT INTO metadata VALUES('session', ?)", (json.dumps('a'*32),))
    for i, color in ((2, 'red'), (3, 'blue')):
        sid = f'{"a"*32}-{i}'
        data = png(color)
        (session/'sources'/f'{sid}.png').write_bytes(data)
        db.execute('INSERT INTO sources VALUES(?,?,?)',
                   (sid, json.dumps(dict(source_id=sid, sha256=hashlib.sha256(data).hexdigest())), len(data)))
    db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', ('op1', 'b'*32, 'observe', 1.0, 9.0, '[]',
               json.dumps(dict(status='completed', token=TOKEN))))
    db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', ('op2', 'b'*32, 'input', 2.0, 9.0,
               json.dumps([dict(type='key', key='RIGHT', modifiers=[], secret=TOKEN)]), None))
    db.execute("INSERT INTO native_intents VALUES('n1','op1',NULL,?, 't')", (f'{"a"*32}-2',))
    db.execute("INSERT INTO native_intents VALUES('n2','op2',NULL,?, 't')", (f'{"a"*32}-3',))
    db.commit()
    db.close()
    (actor_dir/'actor.json').write_text(json.dumps(dict(token=TOKEN, base_url=BASE_URL, actor_id='b'*32)))
    (actor_dir/'route.json').write_text(json.dumps(dict(provider=dict(api_key=ROUTE_KEY, base_url=BASE_URL))))
    (actor_dir/'frozen.json').write_text(json.dumps(dict(actor_id='b'*32)))
    (actor_dir/'host-process.json').write_text(json.dumps(dict(pid=1, argv=['host', TOKEN])))
    (actor_dir/'prompt.txt').write_text('Play the game.')
    events = [
        dict(type='tool-start', tool_call_id='c1', tool='computer_input',
             arguments=dict(actions=[dict(type='key', key='RIGHT', modifiers=[])], authorization=TOKEN)),
        dict(type='tool-result', tool_call_id='c1', tool='computer_input', wall_time='t',
             result=dict(isError=False, content=[dict(type='text', text=json.dumps(dict(
                 schema='player-computer-result/1', operation_id='op2', status='completed', token=TOKEN,
                 base_url=BASE_URL, source=dict(source_id=f'{"a"*32}-3'))))])),
        dict(type='response-complete', usage=dict(input=1), route=BASE_URL),
    ]
    (actor_dir/'host.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    (session/'contexts'/'ctx.json').write_text(json.dumps(dict(
        schema='player-handoff-context/1', context_id='ctx', summary='carry on', knowledge={}, token=TOKEN)))
    (session/'custodian-stdout.txt').write_text(TOKEN)
    return session


def all_bytes(root: Path) -> bytes:
    return b''.join(p.read_bytes() for p in root.rglob('*') if p.is_file())


def test_projection_keeps_what_the_actor_saw_and_drops_every_secret(tmp_path):
    session = make_session(tmp_path)
    out = tmp_path/'trace'
    manifest = project([session], out)
    data = all_bytes(out)
    for secret in (TOKEN, BASE_URL, ROUTE_KEY):
        assert secret.encode() not in data
    steps = [json.loads(line) for line in (out/'s1'/'001'/'steps.jsonl').read_text().splitlines()]
    assert [s['kind'] for s in steps] == ['observe', 'input'] and steps[1]['actions'] == [
        dict(type='key', key='RIGHT', modifiers=[])]
    assert steps[0]['status'] == 'completed' and steps[1]['frame'] == f'{"a"*32}-3'
    tool = json.loads((out/'s1'/'001'/'tools.jsonl').read_text())
    assert tool['arguments'] == dict(actions=[dict(type='key', key='RIGHT', modifiers=[])])
    assert tool['outcome'] == dict(error=False, schema='player-computer-result/1', operation_id='op2',
                                   status='completed', source_id=f'{"a"*32}-3')
    assert (out/'s1'/'001'/'received.txt').read_text() == 'Play the game.'
    assert json.loads((out/'s1'/'handoffs'/'ctx.json').read_text())['summary'] == 'carry on'
    names = {p.name for p in out.rglob('*')}
    assert not names & {'actor.json', 'route.json', 'host-process.json', 'custodian-stdout.txt', 'host.jsonl'}
    assert manifest['sessions'][0]['actors'][0]['frames'] == 2
    for relative, digest in manifest['files'].items():
        assert hashlib.sha256((out/relative).read_bytes()).hexdigest() == digest


def test_a_frame_that_differs_from_its_sealed_hash_is_refused(tmp_path):
    session = make_session(tmp_path)
    (session/'sources'/f'{"a"*32}-3.png').write_bytes(png('green'))
    with pytest.raises(ProjectionError, match='SHA-256'):
        project([session], tmp_path/'trace')


def test_projection_never_overwrites_an_existing_target(tmp_path):
    session = make_session(tmp_path)
    (tmp_path/'trace').mkdir()
    with pytest.raises(ProjectionError, match='must not exist'):
        project([session], tmp_path/'trace')


def make_store(path: Path, schema='player-memory/2'):
    db = sqlite3.connect(path)
    db.executescript('''
        CREATE TABLE metadata (schema TEXT NOT NULL);
        CREATE TABLE sources (id TEXT PRIMARY KEY, metadata TEXT NOT NULL, png BLOB);
        CREATE TABLE programs (id TEXT PRIMARY KEY, document TEXT NOT NULL, parent_id TEXT);
        CREATE TABLE records (id TEXT PRIMARY KEY, document TEXT NOT NULL, kind TEXT NOT NULL, supersedes TEXT,
            program_id TEXT);
        CREATE TABLE record_sources (owner TEXT NOT NULL, target TEXT NOT NULL, PRIMARY KEY(owner,target));
        CREATE TABLE record_supports (owner TEXT NOT NULL, target TEXT NOT NULL, PRIMARY KEY(owner,target));''')
    db.execute('INSERT INTO metadata VALUES (?)', (schema,))
    db.execute('INSERT INTO records VALUES (?,?,?,?,?)', ('r1', json.dumps(dict(actor_id='x', created_wall=1,
               text='tank holds water', data={})), 'claim', None, None))
    db.execute('INSERT INTO records VALUES (?,?,?,?,?)', ('r2', json.dumps(dict(actor_id='y', created_wall=2,
               text='correction', data={})), 'correction', 'r1', None))
    db.execute("INSERT INTO record_supports VALUES ('r2','r1')")
    db.commit()
    db.close()


def test_evidence_reader_reads_a_sealed_store_without_writing_beside_it(tmp_path):
    make_store(tmp_path/'m.sqlite3')
    before = sorted(p.name for p in tmp_path.iterdir())
    store = memory_reader.read(tmp_path/'m.sqlite3')
    assert [r['id'] for r in store['records']] == ['r1', 'r2']
    assert store['records'][1]['supersedes'] == 'r1' and store['records'][1]['supports'] == ['r1']
    assert sorted(p.name for p in tmp_path.iterdir()) == before


@pytest.mark.parametrize('schema', ['player-memory/1', 'player-memory/3'])
def test_evidence_reader_refuses_other_schemas(tmp_path, schema):
    make_store(tmp_path/'m.sqlite3', schema)
    with pytest.raises(memory_reader.StoreError, match='expected player-memory/2'):
        memory_reader.read(tmp_path/'m.sqlite3')


def secrets_of(sessions) -> set[str]:
    secrets = set()
    for session in sessions:
        for path in session.glob('actors/*/actor.json'):
            value = json.loads(path.read_text())
            secrets |= {value['token'], value['base_url']}
        routes = list(session.glob('actors/*/route.json'))
        stack = [json.loads(path.read_text()) for path in routes]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, str) and len(item) >= 12 and ('://' in item or 'key' in item.lower()):
                secrets.add(item)
    return secrets


# Development lineages only: #382's lh1–lh3 are held out and never projected here (owner
# decision, 8 November 2026). The #372 runs are the seeded sample of docs/design/probe-protocol.md.
SAMPLE_372 = ('aidB3', 'ceil09', 'ceil07', 'ceil05', 'aidB9', 'aidA5')
DEV_LOOP = EVIDENCE.parent/'372-382-dev-loop'


@pytest.mark.skipif(not (DEV_LOOP/'computer-sessions').is_dir(), reason='sealed #372 evidence not on this checkout')
@pytest.mark.parametrize('run', SAMPLE_372)
def test_real_372_projection_carries_no_token_route_or_key(tmp_path, run):
    session = DEV_LOOP/'computer-sessions'/run
    project([session], tmp_path/'trace', memory=DEV_LOOP/f'player-memory-{run}.sqlite3')
    secrets = secrets_of([session])
    data = all_bytes(tmp_path/'trace')
    assert len(secrets) >= 2 and not [s for s in secrets if s.encode() in data]
    assert not re.search(rb'sk-[A-Za-z0-9_-]{16,}|Bearer [A-Za-z0-9]{16,}', data)


@pytest.mark.skipif(not (EVIDENCE/'computer-sessions').is_dir(), reason='sealed #397 evidence not on this checkout')
def test_real_397_projection_carries_no_token_route_or_key(tmp_path):
    out = tmp_path/'trace'
    sessions = sorted((EVIDENCE/'computer-sessions').glob('sd1a*'))
    manifest = project(sessions, out, memory=EVIDENCE/'player-memory-sd1.sqlite3')
    secrets = secrets_of(sessions)
    data = all_bytes(out)
    assert len(secrets) > 14 and not [s for s in secrets if s.encode() in data]
    assert not re.search(rb'sk-[A-Za-z0-9_-]{16,}|Bearer [A-Za-z0-9]{16,}', data)
    assert len(manifest['sessions']) == 7 and len(memory_reader.read(EVIDENCE/'player-memory-sd1.sqlite3')['records']) == 11


from harness.trace import sidecar  # noqa: E402


def manifest(**changes):
    value = dict(schema='container-manifest/1', id='study/s1', kind='draft', owner_role='curator', inputs={},
                 pinned={}, budgets={}, lifecycle=dict(state='open'), provenance={}, retention={})
    value.update(changes)
    return value


@pytest.mark.parametrize('change', [dict(kind='cache'), dict(lifecycle=dict(state='published')),
                                    dict(schema='container-manifest/2'), dict(id=''), dict(inputs=[]),
                                    dict(extra=1)])
def test_container_manifests_are_validated(change):
    with pytest.raises(sidecar.ManifestError):
        sidecar.validate(manifest(**change))
    assert sidecar.validate(manifest())['kind'] == 'draft'


@pytest.mark.skipif(not (EVIDENCE/'computer-sessions').is_dir(), reason='sealed #397 evidence not on this checkout')
def test_tracked_397_sidecar_index_matches_the_sealed_sessions():
    tracked = json.loads((ROOT/'data'/'containers'/'397-seven-day.json').read_text())
    assert tracked['containers'] == sidecar.actor_sessions(EVIDENCE, '397-seven-day')
    text = json.dumps(tracked)
    assert 'actor.json' not in text and 'route.json' not in text
