"""Ancestry security fixtures, `player-source-read/2` parity, and `#998 v94` 785-ancestor-frame replay (#1025, #1026)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import time

import pytest

from harness.application import Application
from harness.computer.protocol import canonical
from harness.computer.runtime import ComputerRuntime
from harness.player.journal import Journal
from harness.player.knowledge import Knowledge
from harness.player.source_index import (
    AGENDA_MAX_BYTES,
    IMAGE_LIMIT,
    SourceIndex,
    SourceIndexError,
    SourceUnavailable,
    agenda_refs,
    empty_agenda,
    empty_source_index,
    validate_agenda,
    validate_source_index,
)
from harness.player_client import PlayerClient
from harness.player_view import UnsupportedResult, actor_result
from harness.server import serve
from tools.source_index import build_source_index

PNG_1X1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00'
    b'\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82'
)
PNG_ALT = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02'
    b'\x08\x02\x00\x00\x00\xfd\xd4\x9as\x00\x00\x00\x0eIDATx\x9cc``````\x00'
    b'\x00\x00\x10\x00\x01\x0f\x10\x11\x12\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _make_closed_run(
    root: Path,
    rel: str,
    *,
    session: str,
    world: str,
    lineage: str,
    admission: int,
    sources: dict[str, bytes],
    with_receipt: bool = True,
    with_wal: bool = False,
    schema: str = 'campaign-run/14',
) -> Path:
    run_dir = root / rel
    (run_dir / 'sources').mkdir(parents=True, exist_ok=True)
    manifest = {
        'schema': schema,
        'session': session,
        'labels': {'arm': 'base', 'start': 'F1', 'scenario': 's', 'world': world, 'lineage': lineage, 'admission': admission},
        'context': {},
    }
    m_bytes = (canonical(manifest) + '\n').encode('utf-8')
    (run_dir / 'manifest.json').write_bytes(m_bytes)
    watch = {
        'schema': 'campaign-watch-start/4',
        'session': session,
        'manifest_sha256': hashlib.sha256(m_bytes).hexdigest(),
    }
    (run_dir / 'watch-start.json').write_text(canonical(watch) + '\n', encoding='utf-8')
    if with_receipt:
        (run_dir / 'receipt.json').write_text(canonical({'session': session, 'ended_wall': 100.0}) + '\n', encoding='utf-8')
    db = sqlite3.connect(run_dir / 'session.sqlite3')
    try:
        db.execute('CREATE TABLE actors (id TEXT PRIMARY KEY)')
        db.execute('CREATE TABLE operations (id TEXT PRIMARY KEY, actor TEXT, created_wall REAL, final_json TEXT)')
        db.execute('CREATE TABLE native_intents (id TEXT PRIMARY KEY, operation TEXT, source TEXT)')
        db.execute('CREATE TABLE collections (native_id TEXT, value TEXT, source TEXT)')
        db.execute('CREATE TABLE sources (id TEXT PRIMARY KEY, metadata TEXT, bytes INTEGER)')
        db.execute("INSERT INTO actors VALUES ('" + '1' * 32 + "')")
        for step, (sid, png) in enumerate(sources.items(), 1):
            sha = hashlib.sha256(png).hexdigest()
            (run_dir / 'sources' / f'{sid}.png').write_bytes(png)
            meta = {
                'schema': 'computer-source/1',
                'source_id': sid,
                'session': session,
                'capture_id': int(sid.rsplit('-', 1)[1]),
                'media_type': 'image/png',
                'width': 1,
                'height': 1,
                'window_width': 1,
                'window_height': 1,
                'viewport': [0, 0, 1, 1],
                'sha256': sha,
                'presented_ms': step * 1000,
                'received_wall': float(step),
            }
            op_id = f'{step:032x}'
            db.execute('INSERT INTO operations VALUES (?,?,?,?)', (op_id, '1' * 32, float(step), canonical({'source': meta})))
            db.execute('INSERT INTO sources VALUES (?,?,?)', (sid, canonical(meta), len(png)))
        db.commit()
    finally:
        db.close()
    if with_wal:
        (run_dir / 'session.sqlite3-wal').write_bytes(b'non-empty-wal-bytes')
    return run_dir


class _FakeChannel:
    def __init__(self) -> None:
        self.stopped_reasons: list[str] = []
        import threading
        self.stopped = threading.Event()

    def stop(self, reason: str) -> None:
        self.stopped_reasons.append(reason)
        self.stopped.set()


class _FakeProcess:
    def poll(self):
        return None


def _make_delivered_v4(path: Path, cited: list[str], clocks: dict[str, str] | None = None) -> None:
    facts = []
    for idx, src in enumerate(cited, 1):
        facts.append({
            'id': f'f-{idx}',
            'statement_kind': 'observation',
            'tags': ['camp'],
            'text': f'Observed frame {src}.',
            'scope': {'game': 'example', 'world': None},
            'branch_relation': 'same',
            'lifecycle_state': 'active',
            'needs_review': False,
            'stale_citations': [],
            'unverified_branch': False,
            'links': [],
            'backlinks': [],
            'shadowed_by': [],
            'contradicted_by': [],
            'cited_by_articles': [],
            'citation_source_ids': [src],
            'depiction_source_id': src,
            'seen': {'session': 's01', 'actor': '001', 'step': idx, 'order': [1, '001', idx]},
        })
    doc = {
        'schema': 'delivered-knowledge/4',
        'version': 'v1',
        'commit': '1' * 40,
        'repository_id': '2' * 40,
        'coverage': {'schema': 'curator-coverage/2', 'session': 's01', 'actor': '001', 'last_step': len(cited) or None},
        'frame_clocks': clocks or {},
        'articles': [],
        'facts': facts,
        'history': {'replaced': {}, 'ended': [], 'retracted': []},
    }
    path.write_text(canonical(doc) + '\n', encoding='utf-8')


def test_agenda_continuation_validation_and_bounds():
    ag = empty_agenda()
    assert validate_agenda(ag) == ag
    ag_valid = {
        'schema': 'player-agenda-continuation/1',
        'cut_count': 3,
        'threads': [{
            'id': 'boil-water',
            'title': 'Boil clean water',
            'status': 'active',
            'stop_when': 'At least 4 clean water in bottle',
            'sub_items': [{'text': 'Light fire', 'done': True}],
            'refs': ['a' * 32 + '-1', 'rv-battery'],
            'created_at_cut': 1,
            'updated_at_cut': 2,
        }],
    }
    assert validate_agenda(ag_valid) == ag_valid
    assert agenda_refs(ag_valid) == {'a' * 32 + '-1', 'rv-battery'}

    # Dropped requires drop_reason.
    bad_drop = json.loads(json.dumps(ag_valid))
    bad_drop['threads'][0]['status'] = 'dropped'
    with pytest.raises(SourceIndexError, match='drop_reason'):
        validate_agenda(bad_drop)

    # Exceeding 3072 UTF-8 bytes fails closed.
    big = {'schema': 'player-agenda-continuation/1', 'cut_count': 0, 'threads': []}
    for i in range(16):
        big['threads'].append({
            'id': f't-{i}', 'title': 'x' * 120, 'status': 'done', 'notes': 'y' * 240,
            'created_at_cut': 0, 'updated_at_cut': 0,
        })
    assert len(canonical(big).encode('utf-8')) > AGENDA_MAX_BYTES
    with pytest.raises(SourceIndexError, match='serialized bound'):
        validate_agenda(big)


def test_source_index_ancestry_security_disclosure_and_player_source_read_2(tmp_path):
    s_anc = 'a' * 32
    s_other_world = 'b' * 32
    s_other_lineage = 'c' * 32
    s_wal = 'd' * 32
    s_no_receipt = 'e' * 32
    s_cur = 'f' * 32

    anc_disclosed = f'{s_anc}-1'
    anc_undisclosed = f'{s_anc}-2'
    anc_corrupt = f'{s_anc}-3'
    anc_missing = f'{s_anc}-4'
    anc_symlink = f'{s_anc}-5'
    anc_agenda = f'{s_anc}-6'

    run_anc = _make_closed_run(
        tmp_path, '.runtime/computer-sessions/anc-1',
        session=s_anc, world='w1', lineage='lin1', admission=1,
        sources={
            anc_disclosed: PNG_1X1,
            anc_undisclosed: PNG_1X1,
            anc_corrupt: PNG_1X1,
            anc_missing: PNG_1X1,
            anc_symlink: PNG_1X1,
            anc_agenda: PNG_1X1,
        },
    )
    run_wrong_world = _make_closed_run(
        tmp_path, '.runtime/computer-sessions/wrong-world',
        session=s_other_world, world='w2', lineage='lin1', admission=1,
        sources={f'{s_other_world}-1': PNG_1X1},
    )
    run_wrong_lineage = _make_closed_run(
        tmp_path, '.runtime/computer-sessions/wrong-lineage',
        session=s_other_lineage, world='w1', lineage='lin2', admission=1,
        sources={f'{s_other_lineage}-1': PNG_1X1},
    )
    run_wal = _make_closed_run(
        tmp_path, '.runtime/computer-sessions/open-wal',
        session=s_wal, world='w1', lineage='lin1', admission=2,
        sources={f'{s_wal}-1': PNG_1X1}, with_wal=True,
    )
    run_no_receipt = _make_closed_run(
        tmp_path, '.runtime/computer-sessions/unclosed',
        session=s_no_receipt, world='w1', lineage='lin1', admission=2,
        sources={f'{s_no_receipt}-1': PNG_1X1}, with_receipt=False,
    )

    built = build_source_index(
        root=tmp_path, world='w1', lineage='lin1', before_admission=3,
        extra_runs=[run_anc, run_wrong_world, run_wrong_lineage, run_wal, run_no_receipt],
        include_sealed_evidence=False,
    )
    # Only the verified same-world, same-lineage, closed non-WAL ancestor is eligible!
    assert list(built['roots'].keys()) == ['s01']
    assert built['roots']['s01']['session_id'] == s_anc
    assert set(built['sources'].keys()) == {anc_disclosed, anc_undisclosed, anc_corrupt, anc_missing, anc_symlink, anc_agenda}

    # Now mutate disk AFTER freeze to test runtime security checks without tripping runtime.stop!
    (run_anc / 'sources' / f'{anc_corrupt}.png').write_bytes(PNG_ALT)
    (run_anc / 'sources' / f'{anc_missing}.png').unlink()
    outside = tmp_path / 'outside.png'
    outside.write_bytes(PNG_1X1)
    sym_path = run_anc / 'sources' / f'{anc_symlink}.png'
    sym_path.unlink()
    sym_path.symlink_to(outside)

    # Wire live Application + HTTP server + PlayerClient!
    cur_dir = tmp_path / '.runtime/computer-sessions/cur-run'
    cur_dir.mkdir(parents=True)
    k_path = cur_dir / 'delivered-knowledge.json'
    _make_delivered_v4(
        k_path,
        cited=[anc_disclosed, anc_corrupt, anc_missing, anc_symlink],
        clocks={anc_disclosed: 'Spring, day 61 8:00 AM'},
    )
    channel = _FakeChannel()
    runtime = ComputerRuntime(
        cur_dir, s_cur, channel, _FakeProcess(), time.monotonic() + 60,
        dict(max_inputs=10, max_requests=20, max_frames=10, max_bytes=10_000_000), max_actors=1,
    )
    actor = runtime.add_actor()
    journal = Journal(cur_dir / 'journal.sqlite3')
    src_index = SourceIndex(built, root_dir=tmp_path)
    app = Application(
        runtime, journal, cur_dir / 'contexts',
        knowledge=k_path, source_index=src_index, initial_agenda_refs=[anc_agenda],
    )
    server, thread = serve(app, 0)
    try:
        cfg_path = cur_dir / 'actor.json'
        cfg_path.write_text(canonical(dict(
            schema='player-adapter/2',
            base_url=f'http://127.0.0.1:{server.server_port}',
            session=s_cur,
            **actor,
        )), encoding='utf-8')
        client = PlayerClient(cfg_path)

        # 1. Disclosed ancestor frame succeeds: clickable=False, blinded origin s01, direct clock_label, never issued for click!
        val, png, err = client.call('player_source', {'source_id': anc_disclosed, 'intent': 'inspect ancestor'})
        assert err is False and png == PNG_1X1
        view = actor_result(val)
        assert view['schema'] == 'player-source-read/2'
        assert view['status'] == 'available'
        assert view['clickable'] is False
        assert view['origin'] == {'admission': 's01', 'actor': '001', 'step': 1}
        assert view['clock_label'] == 'Spring, day 61 8:00 AM'
        assert not runtime.store.has_source(anc_disclosed, actor['actor_id'])

        # 2. Disclosed via carried #1026 agenda ref also succeeds (no clock_label when absent)!
        val_ag, png_ag, err_ag = client.call('player_source', {'source_id': anc_agenda, 'intent': 'inspect agenda ref'})
        assert err_ag is False and png_ag == PNG_1X1
        view_ag = actor_result(val_ag)
        assert view_ag['status'] == 'available' and view_ag['clickable'] is False and 'clock_label' not in view_ag

        # 3. Eligible but UNDISCLOSED ancestor returns unavailable (unknown-or-out-of-scope), indistinguishable from unknown!
        val_u, png_u, err_u = client.call('player_source', {'source_id': anc_undisclosed, 'intent': 'probe undisclosed'})
        val_x, png_x, err_x = client.call('player_source', {'source_id': f'{s_other_world}-1', 'intent': 'probe wrong world'})
        assert err_u is False and png_u is None and actor_result(val_u)['reason'] == 'unknown-or-out-of-scope'
        assert err_x is False and png_x is None and actor_result(val_x)['reason'] == 'unknown-or-out-of-scope'

        # 4. Integrity failure, missing file, and symlink refusal all return structured unavailable WITHOUT stopping live runtime!
        for sid, expected_reason in (
            (anc_corrupt, 'integrity-failed'),
            (anc_missing, 'missing'),
            (anc_symlink, 'integrity-failed'),
        ):
            v, p, e = client.call('player_source', {'source_id': sid, 'intent': f'check {expected_reason}'})
            assert e is False and p is None
            assert actor_result(v)['status'] == 'unavailable'
            assert actor_result(v)['reason'] == expected_reason
        assert channel.stopped_reasons == [] and not channel.stopped.is_set()

        # 5. Direct /api/player-source enforces the exact same disclosure gate!
        denied = client._post('/api/player-source', {'source_id': anc_undisclosed}, image=True)
        assert isinstance(denied, dict) and denied.get('reason') == 'unknown-or-out-of-scope'

        # 6. Legacy player-source-read/1 is rejected by player_view (S-MIGRATION)!
        with pytest.raises(UnsupportedResult):
            actor_result({'schema': 'player-source-read/1', 'source': view['source'], 'read_wall': 1.0})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        journal.close()
        runtime.store.close()


def test_998_v94_resolves_all_785_ancestor_frames_read_only(tmp_path):
    """Read-only `#998` `v94` replay: all 785 ancestor frames resolve and SHA-verify through Application.read_player_source."""
    from tools.knowledge_retrieval_benchmark import _project_v3_to_v4

    repo_root = Path(__file__).resolve().parents[1]
    if not (repo_root / '.runtime' / 'evidence' / 'multi-day-standard-build-998-admission-04').is_dir():
        alt = repo_root.parents[1] if repo_root.parent.name == 'worktrees' else repo_root
        if (alt.parent / '.runtime' / 'evidence' / 'multi-day-standard-build-998-admission-04').is_dir():
            repo_root = alt.parent
    ev_dir = repo_root / '.runtime' / 'evidence' / 'multi-day-standard-build-998-admission-04'
    if not ev_dir.is_dir():
        pytest.skip('Sealed #998 evidence store not present in this checkout')
    v94_path = ev_dir / 'run' / 'delivered-knowledge.json'
    v94 = json.loads(v94_path.read_text(encoding='utf-8'))
    assert v94['version'] == 'v94'
    a04_session = 'a6979727b98c9fde6e8e0f502fea128d'
    ancestor_cited = sorted({
        src
        for fact in v94['facts']
        for src in fact.get('citation_source_ids', ())
        if not src.startswith(a04_session + '-')
    })
    assert len(ancestor_cited) == 785

    built = build_source_index(
        root=repo_root,
        world='campground-standard-multi-day',
        lineage='campground-standard-multi-day',
        before_admission=4,
    )
    assert set(built['roots'].keys()) == {'s01', 's02', 's03'}
    idx = SourceIndex(built, root_dir=repo_root)

    v94_v4 = _project_v3_to_v4(v94)
    delivered_file = tmp_path / 'v94-delivered.json'
    delivered_file.write_text(json.dumps(v94_v4), encoding='utf-8')
    channel = _FakeChannel()
    (tmp_path / 'computer').mkdir()
    runtime = ComputerRuntime(
        tmp_path / 'computer', a04_session, channel, _FakeProcess(),
        time.monotonic() + 120, dict(max_inputs=10, max_requests=10, max_frames=10, max_bytes=1024 * 1024),
    )
    journal = Journal(tmp_path / 'player.sqlite3')
    try:
        app = Application(runtime, journal, tmp_path / 'contexts', knowledge=delivered_file, source_index=idx)
        seen_roots = set()
        for sid in ancestor_cited:
            env, png = app.read_player_source(sid)
            assert env['schema'] == 'player-source-read/2'
            assert env['status'] == 'available', (sid, env)
            assert env['clickable'] is False
            assert env['source_id'] == sid and env['source']['source_id'] == sid
            assert png is not None and png.startswith(b'\x89PNG\r\n\x1a\n')
            seen_roots.add(env['origin']['admission'])
        assert seen_roots == {'s01', 's02', 's03'}
        assert channel.stopped_reasons == []
    finally:
        journal.close()
        runtime.store.close()


def test_source_index_cli_writes_index_and_carries_prior_agenda(tmp_path, capsys):
    from tools.source_index import main as source_index_main

    run1 = _make_closed_run(
        tmp_path, '.runtime/runs/run1',
        session='1' * 32, world='w1', lineage='lin1', admission=1,
        sources={f"{'1' * 32}-1": PNG_1X1},
    )
    prior = tmp_path / 'agenda-final.json'
    carried = dict(
        schema='player-agenda-continuation/1', cut_count=3,
        threads=[dict(id='t1', title='Carry goal', status='active', created_at_cut=1, updated_at_cut=2)],
    )
    prior.write_text(canonical(carried) + '\n', encoding='utf-8')
    pkg = tmp_path / 'pkg'
    code = source_index_main([
        '--package', str(pkg), '--root', str(tmp_path),
        '--world', 'w1', '--lineage', 'lin1', '--before-admission', '2',
        '--extra-run', str(run1), '--no-sealed-evidence', '--prior-agenda', str(prior),
    ])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {'source-index.json', 'agenda.json'}
    assert hashlib.sha256((pkg / 'source-index.json').read_bytes()).hexdigest() == out['source-index.json']
    assert hashlib.sha256((pkg / 'agenda.json').read_bytes()).hexdigest() == out['agenda.json']
    idx = json.loads((pkg / 'source-index.json').read_text(encoding='utf-8'))
    assert f"{'1' * 32}-1" in idx['sources']
    assert json.loads((pkg / 'agenda.json').read_text(encoding='utf-8')) == carried

    # Invalid prior agenda is refused cleanly.
    bad = tmp_path / 'bad-agenda.json'
    bad.write_text(json.dumps(dict(schema='player-agenda-continuation/99', cut_count=0, threads=[])), encoding='utf-8')
    with pytest.raises(SystemExit) as exc:
        source_index_main(['--package', str(tmp_path / 'pkg2'), '--root', str(tmp_path), '--prior-agenda', str(bad)])
    assert exc.value.code == 1
