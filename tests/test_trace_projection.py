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


def no_output(tmp_path) -> bool:
    return not (tmp_path/'trace').exists() and not list(tmp_path.glob('.trace.partial-*'))


def test_a_frame_that_differs_from_its_sealed_hash_is_refused_and_leaves_nothing(tmp_path):
    session = make_session(tmp_path)
    (session/'sources'/f'{"a"*32}-3.png').write_bytes(png('green'))
    with pytest.raises(ProjectionError, match='SHA-256'):
        project([session], tmp_path/'trace')
    assert no_output(tmp_path)


@pytest.mark.parametrize('channel', ['final report', 'handoff knowledge', 'handoff summary', 'memory record',
                                     'error reason', 'key pattern'])
def test_the_secret_guard_fails_closed_on_free_text_channels(tmp_path, channel):
    session = make_session(tmp_path)
    actor = session/'actors'/'001'
    memory = None
    if channel == 'final report':
        (actor/'player-final.txt').write_text(f'Done. My token was {TOKEN}.')
    elif channel == 'handoff knowledge':
        (session/'contexts'/'ctx.json').write_text(json.dumps(dict(
            schema='player-handoff-context/1', context_id='ctx', summary='carry on',
            knowledge=dict(records=[dict(text=f'connect to {BASE_URL}')]))))
    elif channel == 'handoff summary':
        (session/'contexts'/'ctx.json').write_text(json.dumps(dict(
            schema='player-handoff-context/1', context_id='ctx', summary=f'route key {ROUTE_KEY}', knowledge={})))
    elif channel == 'memory record':
        memory = tmp_path/'m.sqlite3'
        make_store(memory)
        db = sqlite3.connect(memory)
        db.execute('UPDATE records SET document=? WHERE id=?',
                   (json.dumps(dict(actor_id='x', created_wall=1, text=TOKEN, data={})), 'r1'))
        db.commit()
        db.close()
    elif channel == 'error reason':
        events = [json.loads(line) for line in (actor/'host.jsonl').read_text().splitlines()]
        events[1]['result']['content'][0]['text'] = json.dumps(dict(status='failed', reason=f'cannot reach {BASE_URL}'))
        (actor/'host.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    else:
        (actor/'player-final.txt').write_text('debug: Bearer abcdefghijklmnopqrstuvwxyz0123')
    with pytest.raises(ProjectionError, match='Secret guard'):
        project([session], tmp_path/'trace', memory=memory)
    assert no_output(tmp_path)


def test_wait_durations_input_sources_and_refused_or_unfinished_calls_are_kept(tmp_path):
    session = make_session(tmp_path)
    db = sqlite3.connect(session/'session.sqlite3')
    db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', ('op3', 'b'*32, 'input', 3.0, 9.0,
               json.dumps([dict(type='wait', seconds=2.5)]), None))
    db.commit()
    db.close()
    actor = session/'actors'/'001'
    events = [json.loads(line) for line in (actor/'host.jsonl').read_text().splitlines()]
    events[0]['arguments']['source_id'] = f'{"a"*32}-2'
    events += [dict(type='tool-start', tool_call_id='c2', tool='computer_input', arguments=dict(actions=[])),
               dict(type='tool-refused', tool_call_id='c2', tool='computer_input', reason='orderly-stop'),
               dict(type='tool-start', tool_call_id='c3', tool='computer_observe', arguments={})]
    (actor/'host.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    project([session], tmp_path/'trace')
    steps = [json.loads(line) for line in (tmp_path/'trace'/'s1'/'001'/'steps.jsonl').read_text().splitlines()]
    assert steps[2]['actions'] == [dict(type='wait', seconds=2.5)]
    tools = [json.loads(line) for line in (tmp_path/'trace'/'s1'/'001'/'tools.jsonl').read_text().splitlines()]
    assert tools[0]['arguments']['source_id'] == f'{"a"*32}-2'
    assert tools[1]['outcome'] == dict(refused=True, reason='orderly-stop')
    assert tools[2]['tool'] == 'computer_observe' and tools[2]['outcome'] == dict(unfinished=True)


@pytest.mark.parametrize('damage', ['foreign frame id', 'symlinked prompt', 'no frozen inputs', 'bad event'])
def test_damaged_sealed_inputs_are_refused(tmp_path, damage):
    session = make_session(tmp_path)
    actor = session/'actors'/'001'
    if damage == 'foreign frame id':
        db = sqlite3.connect(session/'session.sqlite3')
        db.execute("UPDATE native_intents SET source='../../escape-2' WHERE id='n1'")
        db.commit()
        db.close()
    elif damage == 'symlinked prompt':
        (actor/'prompt.txt').unlink()
        (actor/'prompt.txt').symlink_to(actor/'actor.json')
    elif damage == 'no frozen inputs':
        (actor/'frozen.json').unlink()
    else:
        (actor/'host.jsonl').write_text('{"type": "tool-start"')
    with pytest.raises(ProjectionError):
        project([session], tmp_path/'trace')
    assert no_output(tmp_path)


def test_stray_files_in_the_actors_directory_are_ignored(tmp_path):
    session = make_session(tmp_path)
    (session/'actors'/'.DS_Store').write_bytes(b'x')
    manifest = project([session], tmp_path/'trace')
    assert [a['directory'] for a in manifest['sessions'][0]['actors']] == ['001']


def test_workbench_commands_over_a_projection(tmp_path):
    from harness.trace import workbench
    project([make_session(tmp_path)], tmp_path/'trace')

    def run(*args):
        out = io.StringIO()
        workbench.main([*args], out=out)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    trace = str(tmp_path/'trace')
    assert [s['seq'] for s in run('steps', trace, '--kind', 'input')] == [2]
    frames = run('frames', trace, '--actor', 's1/001')
    assert [f['frame'] for f in frames] == [f'{"a"*32}-2', f'{"a"*32}-3']
    assert run('tools', trace, '--tool', 'computer_input')[0]['outcome']['status'] == 'completed'
    cells = run('diff', trace, frames[0]['frame'], frames[1]['frame'], '--grid', '2x2')
    assert len(cells) == 4 and all(c['changed_fraction'] == 1.0 for c in cells)
    assert [n['frame'] for n in run('similar', trace, frames[0]['frame'], '--k', '1')] == [frames[1]['frame']]
    for bad in (['diff', trace, '../manifest', frames[0]['frame']], ['similar', trace, '..']):
        with pytest.raises(SystemExit):
            run(*bad)


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
    db = sqlite3.connect(tmp_path/'m.sqlite3')
    db.execute('PRAGMA journal_mode=WAL')  # a WAL store: a plain read-only open would create -shm
    db.close()
    before = sorted(p.name for p in tmp_path.iterdir())
    store = memory_reader.read(tmp_path/'m.sqlite3')
    assert [r['id'] for r in store['records']] == ['r1', 'r2']
    assert store['records'][1]['supersedes'] == 'r1' and store['records'][1]['supports'] == ['r1']
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_evidence_reader_refuses_an_unchecked_write_ahead_log(tmp_path):
    make_store(tmp_path/'m.sqlite3')
    (tmp_path/'m.sqlite3-wal').write_bytes(b'unapplied rows')
    with pytest.raises(memory_reader.StoreError, match='write-ahead log'):
        memory_reader.read(tmp_path/'m.sqlite3')


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


def test_sidecar_cli_writes_a_valid_index_without_secret_file_digests(tmp_path):
    study = tmp_path/'study'
    (study/'computer-sessions').mkdir(parents=True)
    session = make_session(study/'computer-sessions')
    (session/'actors'/'001'/'frozen.json').write_text(json.dumps(dict(
        actor_id='b'*32, files={'actor.json': 'a'*64, 'route.json': 'b'*64, 'prompt.txt': 'c'*64})))
    sidecar.main([str(study), '--study', 'study', '--out', str(tmp_path/'index.json')])
    index = json.loads((tmp_path/'index.json').read_text())
    assert index['schema'] == 'container-index/1' and len(index['containers']) == 1
    manifest = sidecar.validate(index['containers'][0])
    assert manifest['inputs']['actors'][0]['given_sha256'] == {'prompt.txt': 'c'*64}
    assert 'a'*64 not in json.dumps(index) and 'b'*64 not in json.dumps(index)


@pytest.mark.skipif(not (EVIDENCE/'computer-sessions').is_dir(), reason='sealed #397 evidence not on this checkout')
def test_tracked_397_sidecar_index_matches_the_sealed_sessions():
    tracked = json.loads((ROOT/'data'/'containers'/'397-seven-day.json').read_text())
    assert tracked['containers'] == sidecar.actor_sessions(EVIDENCE, '397-seven-day')
    text = json.dumps(tracked)
    assert 'actor.json' not in text and 'route.json' not in text
