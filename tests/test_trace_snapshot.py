"""Snapshots of a growing session store, read beside a live writer process (#837). No game, no provider.

Each test runs `tests.curator_trace.LiveWriter`: a real `SessionStore` in write-ahead-log mode in a child
process, with the driver's files and the host's log beside it. The step numbers of every snapshot are
compared with those of the same session once the writer has closed it and `sealed()` reads it.
"""
from __future__ import annotations

from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from harness.trace import snapshot
from harness.trace.projection import project
from harness.trace.snapshot import TRANSACTION_BOUND_SECONDS, BoundExceeded, ReadRefused, SnapshotError, stage
from harness.trace.stores import CURATOR_READ_LOCK, READ_HOLD_BOUND_SECONDS, sealed
from tests.curator_trace import SESSION_ID, LiveWriter, png

ENDLESS = 'WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT x FROM c'


def _open_store_files(run: Path) -> int:
    """How many of this process's file descriptors refer to the store, its log or its shared memory."""
    files = {(p.stat().st_dev, p.stat().st_ino) for p in run.glob('session.sqlite3*')}
    count = 0
    for name in os.listdir('/dev/fd'):
        try:
            status = os.fstat(int(name))
        except OSError:
            continue
        count += (status.st_dev, status.st_ino) in files
    return count


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _project(session: Path, out: Path) -> tuple[dict, dict[str, list[dict]], dict[str, list[dict]]]:
    manifest = project([session], out)
    actors = [a['directory'] for a in manifest['sessions'][0]['actors']]
    return (manifest, {a: _jsonl(out/session.name/a/'steps.jsonl') for a in actors},
            {a: _jsonl(out/session.name/a/'tools.jsonl') for a in actors})


class Stager:
    """Stage each snapshot into a fresh parent directory under `root`."""

    def __init__(self, root: Path):
        self.root, self.count = root, 0

    def parent(self) -> Path:
        self.count += 1
        path = self.root/f'snapshot-{self.count}'
        path.mkdir(parents=True)
        return path

    def __call__(self, run: Path, **kwargs) -> snapshot.Snapshot:
        return stage(run, self.parent(), **kwargs)


def test_at_the_writers_start_a_snapshot_holds_only_actors_with_frozen_inputs(tmp_path):
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        empty = take(writer.run)
        assert (empty.actors, empty.excluded) == ((), ())
        manifest, steps, _ = _project(empty.directory, tmp_path/'empty')
        assert steps == {} and manifest['sessions'][0]['label_error'] is None
        actor = writer(op='new_actor', frozen=False)
        unfrozen = take(writer.run)
        assert unfrozen.actors == ()
        assert unfrozen.excluded == ('actors/001: no frozen manifest yet',
                                     f"actor {actor['actor_id']}: in the store with no frozen manifest yet")
        assert not (unfrozen.directory/'actors'/'001').exists()
        writer(op='freeze')
        operation = writer(op='step')['operation_id']
        frozen = take(writer.run)
        assert [(a.directory, a.steps, a.last_operation, a.ended) for a in frozen.actors] == [
            ('001', 1, operation, False)]
        assert {p.name for p in frozen.directory.iterdir()} == {
            'session.sqlite3', 'sources', 'actors', 'manifest.json', 'watch-start.json'}
        assert {p.name for p in (frozen.directory/'actors'/'001').iterdir()} == {
            'frozen.json', 'prompt.txt', 'context.txt', 'actor.json', 'route.json', 'mcp.json', 'host.jsonl'}
        assert writer(op='close')['busy'] == 0


def test_under_sustained_writes_every_snapshot_is_a_prefix_numbered_as_the_sealed_trace(tmp_path):
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        writer.send(op='play', seconds=.6, handoffs=1)
        snapshots = []
        while not writer.answered():
            snapshots.append(take(writer.run))
        played = writer.answer()
        closed = writer(op='close')
    assert played['busy'] == 0 and closed['busy'] == 0  # the writer's quarter-second timeout was never hit
    assert closed['errors'] == {} and closed['wal'] == 0
    _, final, _ = _project(writer.run, tmp_path/'sealed')
    assert min(len(final['001']), len(final['002'])) >= 50

    reads = [s.transaction_seconds for s in snapshots]
    holds = [s.hold_seconds for s in snapshots]
    print(f'\n{len(snapshots)} snapshots beside {played["steps"]} steps; read transaction '
          f'max {max(reads) * 1000:.1f} ms, mean {sum(reads) / len(reads) * 1000:.1f} ms; '
          f'lock held max {max(holds) * 1000:.1f} ms, mean {sum(holds) / len(holds) * 1000:.1f} ms')
    assert len(snapshots) >= 5 and max(reads) < TRANSACTION_BOUND_SECONDS and max(holds) < READ_HOLD_BOUND_SECONDS
    assert any(a.directory == '002' and a.steps for s in snapshots for a in s.actors)
    assert any(a.directory == '001' and a.ended for s in snapshots for a in s.actors)
    for number, taken in enumerate(snapshots):
        assert not (taken.directory/'session.sqlite3-wal').exists()
        _, steps, tools = _project(taken.directory, tmp_path/'projected'/str(number))
        for actor in taken.actors:
            assert steps[actor.directory] == final[actor.directory][:actor.steps]
            named = {t['outcome'].get('operation_id') for t in tools[actor.directory]} - {None}
            assert named <= {s['operation_id'] for s in steps[actor.directory]}
            if not actor.ended:
                assert not any(t['outcome'].get('unfinished') for t in tools[actor.directory])


def test_the_cutoff_waits_for_the_hosts_whole_result_and_for_an_outstanding_collection(tmp_path):
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        first = [writer(op='step', hint=True)['operation_id'] for _ in range(2)]
        mid_line = writer(op='step', partial=True)['operation_id']
        held = take(writer.run)
        assert [(a.steps, a.last_operation, a.held_back) for a in held.actors] == [(2, first[-1], 1)]
        log = (held.directory/'actors'/'001'/'host.jsonl').read_bytes()
        assert log.endswith(b'\n') and mid_line.encode() not in log
        events = [json.loads(line) for line in log.splitlines()]
        assert sum(e['type'] == 'tool-start' for e in events) == sum(e['type'] == 'tool-result' for e in events)

        writer(op='finish_line')
        assert take(writer.run).actors[0].steps == 3
        unknown = writer(op='step', unknown=True)['operation_id']
        writer(op='step')
        blocked = take(writer.run)
        assert (blocked.actors[0].steps, blocked.actors[0].held_back) == (3, 2)
        source = writer(op='collect', operation_id=unknown)['source_id']
        collected = take(writer.run)
        assert collected.actors[0].steps == 5
        _, steps, _ = _project(collected.directory, tmp_path/'collected')
        assert (steps['001'][3]['operation_id'], steps['001'][3]['frame']) == (unknown, source)
        assert [s['seq'] for s in steps['001']] == [1, 2, 3, 4, 5]
        assert writer(op='close')['busy'] == 0


def test_a_read_admitted_before_the_closing_marker_is_waited_for_and_the_store_then_seals(tmp_path, monkeypatch):
    inside, real = threading.Event(), snapshot._rows

    def slow(db):
        rows = real(db)
        inside.set()
        time.sleep(.4)
        return rows

    monkeypatch.setattr(snapshot, '_rows', slow)
    take, outcome = Stager(tmp_path/'snapshots'), {}
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        writer(op='step')
        reader = threading.Thread(target=lambda: outcome.update(taken=take(writer.run)))
        reader.start()
        assert inside.wait(5)
        closed = writer(op='close')
        reader.join()
    assert closed['errors'] == {} and .2 < closed['waited'] < READ_HOLD_BOUND_SECONDS
    assert closed['wal'] == 0 and closed['busy'] == 0
    assert outcome['taken'].actors[0].steps == 1
    with sealed(writer.run/'session.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM operations').fetchone() == (1,)
    parent = take.parent()
    with pytest.raises(ReadRefused) as refused:
        stage(writer.run, parent)
    assert refused.value.reason == 'closing' and list(parent.iterdir()) == []


class _Broken(Exception):
    pass


@pytest.mark.parametrize('stop', ['cancelled', 'exception'])
def test_a_read_stopped_mid_query_at_the_writers_close_lets_the_store_seal(tmp_path, monkeypatch, stop):
    """A statement still mid-result when the read stops is finalized, and the connection really closed,
    before the lock is released; the custodian then closes the store with an empty log. `cancelled`: the
    bound interrupts it. `exception`: Python raises between its rows, which leaves the statement mid-result
    without an SQLite error; a connection closed under such a live cursor stays open underneath."""
    inside, real = threading.Event(), snapshot._rows

    def stopped(db):
        rows = real(db)
        inside.set()
        if stop == 'cancelled':
            snapshot._query(db, ENDLESS)  # returns rows until the read bound cancels it
        time.sleep(.3)

        def broken(cursor, row):
            if row[0] > 10:
                raise _Broken
            return row

        db.row_factory = broken
        snapshot._query(db, ENDLESS)
        return rows

    monkeypatch.setattr(snapshot, '_rows', stopped)
    take, outcome = Stager(tmp_path/'snapshots'), {}
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        for _ in range(50):
            writer(op='step')
        parent = take.parent()

        def read():
            try:
                stage(writer.run, parent, transaction_bound=.3 if stop == 'cancelled' else .5, hold_bound=.6)
            except (BoundExceeded, _Broken) as exc:
                outcome.update(stopped=exc, open_files=_open_store_files(writer.run))

        reader = threading.Thread(target=read)
        reader.start()
        assert inside.wait(5)
        closed = writer(op='close')
        reader.join()
    assert isinstance(outcome['stopped'], BoundExceeded if stop == 'cancelled' else _Broken)
    assert outcome['open_files'] == 0 and list(parent.iterdir()) == []
    assert closed['errors'] == {} and .05 < closed['waited'] < .6
    assert closed['wal'] == 0 and closed['busy'] == 0
    with sealed(writer.run/'session.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM operations').fetchone() == (50,)


def test_a_read_is_refused_while_the_custodian_holds_the_lock_and_without_a_lock_file(tmp_path):
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        descriptor = os.open(writer.run/CURATOR_READ_LOCK, os.O_RDONLY)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        parent = take.parent()
        try:
            with pytest.raises(ReadRefused) as refused:
                stage(writer.run, parent)
        finally:
            os.close(descriptor)
        assert refused.value.reason == 'closing' and list(parent.iterdir()) == []
        assert take(writer.run).actors == ()
        writer(op='close')
    with LiveWriter(tmp_path/'unconfigured', read_lock=False) as writer:
        parent = take.parent()
        with pytest.raises(ReadRefused) as refused:
            stage(writer.run, parent)
        assert refused.value.reason == 'no-read-lock' and list(parent.iterdir()) == []
        assert not (writer.run/CURATOR_READ_LOCK).exists()  # never created by a reader
        assert writer(op='close')['wal'] == 0


@pytest.mark.parametrize('bound', ['read', 'hold'])
def test_a_read_held_past_its_bound_is_cancelled_and_nothing_is_staged(tmp_path, monkeypatch, bound):
    real = snapshot._rows
    monkeypatch.setattr(snapshot, '_rows', lambda db: (time.sleep(.3), real(db))[1])
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        writer(op='step')
        parent = take.parent()
        with pytest.raises(BoundExceeded):
            stage(writer.run, parent, **(dict(transaction_bound=.1) if bound == 'read' else dict(hold_bound=.2)))
        assert list(parent.iterdir()) == [] and _open_store_files(writer.run) == 0
        monkeypatch.undo()
        assert take(writer.run).actors[0].steps == 1  # the cancelled read released its lock
        closed = writer(op='close')
    assert closed['waited'] < .5 and closed['wal'] == 0


def test_the_bound_cancels_a_statement_still_running():
    with closing(sqlite3.connect(':memory:')) as db:
        snapshot._bounded(db, time.monotonic() + .05)
        started = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match='interrupted'):
            snapshot._query(db, ENDLESS)
        assert time.monotonic() - started < 1


@pytest.mark.parametrize('damage', ['frame', 'prompt'])
def test_a_file_that_differs_from_its_recorded_digest_refuses_the_snapshot(tmp_path, damage):
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        writer(op='step')
        if damage == 'frame':
            next((writer.run/'sources').iterdir()).write_bytes(png((1, 2, 3)))
        else:
            (writer.run/'actors'/'001'/'prompt.txt').write_text('another mission')
        parent = take.parent()
        with pytest.raises(SnapshotError, match='SHA-256'):
            stage(writer.run, parent)
        assert list(parent.iterdir()) == []
        writer(op='close')


def test_an_actor_that_settles_between_the_transaction_and_the_log_read_keeps_only_what_was_read(
        tmp_path, monkeypatch):
    """Ended is decided from evidence older than the transaction: a host that collects, plays and settles
    after it does not make the transaction's unfinished rows finished, and its later calls are cut."""
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        writer(op='step')
        unknown = writer(op='step', unknown=True)['operation_id']
        writer(op='step')
        real = snapshot._read

        def then_settle(path, deadline):
            read = real(path, deadline)
            writer(op='collect', operation_id=unknown)
            writer(op='step')
            writer(op='handoff')  # its `settled` line and quiescent stage come after the transaction
            return read

        monkeypatch.setattr(snapshot, '_read', then_settle)
        taken = take(writer.run)
        monkeypatch.undo()
        closed = writer(op='close')
    assert closed['errors'] == {} and closed['wal'] == 0 and closed['busy'] == 0
    assert [(a.steps, a.ended, a.held_back) for a in taken.actors] == [(1, False, 2)]
    _, steps, tools = _project(taken.directory, tmp_path/'snapshot')
    _, final, _ = _project(writer.run, tmp_path/'sealed')
    assert steps['001'] == final['001'][:1]
    assert {t['outcome'].get('operation_id') for t in tools['001']} - {None} <= {s['operation_id'] for s in steps['001']}
    assert not any(t['outcome'].get('unfinished') for t in tools['001'])


def test_an_exception_raised_in_the_progress_handler_is_raised_again_once_the_connection_is_closed(
        tmp_path, monkeypatch):
    real = snapshot._rows

    def endless(db):
        rows = real(db)
        snapshot._query(db, ENDLESS)
        return rows

    def interrupted(deadline):
        raise KeyboardInterrupt

    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        writer(op='step')
        monkeypatch.setattr(snapshot, '_rows', endless)
        monkeypatch.setattr(snapshot, '_past', interrupted)
        parent = take.parent()
        with pytest.raises(KeyboardInterrupt):
            stage(writer.run, parent)
        assert list(parent.iterdir()) == [] and _open_store_files(writer.run) == 0
        monkeypatch.undo()
        assert take(writer.run).actors[0].steps == 1
        closed = writer(op='close')
    assert closed['errors'] == {} and closed['wal'] == 0


@pytest.mark.parametrize('created', ['empty file', 'tables', 'identity'])
def test_a_store_still_being_created_is_refused_as_no_store(tmp_path, created):
    from harness.computer.store import SessionStore
    run, store = tmp_path/'run', None
    run.mkdir()
    (run/CURATOR_READ_LOCK).touch()
    if created == 'empty file':
        (run/'session.sqlite3').touch()
    elif created == 'tables':
        with closing(sqlite3.connect(run/'session.sqlite3')) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.commit()
    else:
        store = SessionStore(run, SESSION_ID, dict(max_inputs=1, max_requests=1, max_frames=1, max_bytes=1),
                             time.monotonic() + 60)
        with closing(sqlite3.connect(run/'session.sqlite3')) as db:
            db.execute('DELETE FROM metadata')  # as before the writer's identity commit
            db.commit()
    parent = tmp_path/'snapshot'
    parent.mkdir()
    try:
        with pytest.raises(ReadRefused) as refused:
            stage(run, parent)
    finally:
        if store is not None:
            store.close()
    assert refused.value.reason == 'no-store' and list(parent.iterdir()) == []


def test_an_actor_whose_guard_input_is_not_yet_whole_is_left_out_until_it_is(tmp_path):
    take = Stager(tmp_path/'snapshots')
    with LiveWriter(tmp_path/'run') as writer:
        writer(op='new_actor')
        writer(op='step')
        process = writer.run/'actors'/'001'/'host-process.json'
        process.write_text('{"pid": 1, "argv": ["pla')
        waiting = take(writer.run)
        assert waiting.actors == () and waiting.excluded == ('actors/001: host-process.json not complete yet',)
        assert not (waiting.directory/'actors'/'001').exists()
        process.write_text(json.dumps(dict(pid=1, pgid=1, argv=['player'])) + '\n')
        assert take(writer.run).actors[0].steps == 1
        assert writer(op='close')['errors'] == {}
