"""Construct historical SQL evidence fixtures, never an active player writer."""
import json
from pathlib import Path
import sqlite3


def write_memory(path: Path, records=(), programs=()) -> Path:
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=2')
        db.execute('CREATE TABLE metadata(schema TEXT)')
        db.execute("INSERT INTO metadata VALUES ('player-memory/2')")
        db.execute('CREATE TABLE sources(id TEXT PRIMARY KEY, metadata TEXT, png BLOB)')
        db.execute('CREATE TABLE records(id TEXT PRIMARY KEY, document TEXT, kind TEXT, supersedes TEXT, program_id TEXT)')
        db.execute('CREATE TABLE programs(id TEXT PRIMARY KEY, document TEXT, parent_id TEXT)')
        for table in ('record_sources', 'record_supports', 'program_sources', 'program_records'):
            db.execute(f'CREATE TABLE {table}(owner TEXT, target TEXT)')
        for row in records:
            db.execute('INSERT INTO records VALUES(?,?,?,?,?)',
                       (row['id'], json.dumps(row), row['kind'], row.get('supersedes'), row.get('program_id')))
            for table, key in (('record_sources', 'sources'), ('record_supports', 'supports')):
                db.executemany(f'INSERT INTO {table} VALUES(?,?)', [(row['id'], ref) for ref in row.get(key, ())])
        for row in programs:
            db.execute('INSERT INTO programs VALUES(?,?,?)', (row['id'], json.dumps(row), row.get('parent_id')))
    return path


import pytest


@pytest.fixture
def legacy_player_archive(tmp_path, monkeypatch):
    """Explicitly allow the two synthetic historical sessions for reader tests only."""
    from harness.evaluation.core import sources
    archive = json.loads(sources.ARCHIVE_INDEX.read_text())
    versions = dict(manifest='campaign-run/7', receipt='campaign-receipt/5', driver='player-driver/5',
                    host='player-host/5', host_telemetry=5, run_ending='campaign-watch-terminal/4')
    for session in ('a'*32, 'c'*32):
        archive['sessions'][session] = dict(study='historical-fixture', run='fixture', versions=versions)
    path = tmp_path/'historical-archive.json'
    path.write_text(json.dumps(archive))
    monkeypatch.setattr(sources, 'ARCHIVE_INDEX', path)
