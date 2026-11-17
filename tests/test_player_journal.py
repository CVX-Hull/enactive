"""Journal persistence and old-store rejection."""
import sqlite3
import pytest
from harness.player.contracts import PlayerError
from harness.player.journal import Journal


def test_journal_reopens_and_preserves_calls_and_hint(tmp_path):
    path = tmp_path/'journal'
    with Journal(path) as journal:
        assert journal.record_call('id', 'actor', 'player_hint', {'intent': 'remember', 'text': 'hello'})
        hint = journal.hint('id', 'actor', 'hello', [], 'remember', [])
    with Journal(path) as journal:
        assert journal.hints() == [hint]
        assert journal.calls() == [dict(id='id', actor_id='actor', tool='player_hint', arguments={'intent': 'remember', 'text': 'hello'})]
        assert not journal.record_call('id', 'actor', 'player_hint', {'text': 'hello', 'intent': 'remember'})
        with pytest.raises(PlayerError, match='conflicts'):
            journal.record_call('id', 'other', 'player_hint', {'intent': 'remember', 'text': 'hello'})


def test_unsupported_store_rejected_without_mutation(tmp_path):
    path = tmp_path/'old'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE metadata(schema TEXT)')
        db.execute("INSERT INTO metadata VALUES ('player-memory/2')")
        db.execute('PRAGMA user_version=2')
    before = path.read_bytes()
    with pytest.raises(PlayerError, match='Unsupported player store'):
        Journal(path)
    assert path.read_bytes() == before


def test_source_integrity_capacity_and_immutability(tmp_path):
    import hashlib
    import io
    from PIL import Image

    stream = io.BytesIO()
    Image.new('RGBA', (4, 2), (255, 0, 0, 128)).save(stream, format='PNG')
    png = stream.getvalue()
    session = 'a' * 32
    metadata = dict(schema='computer-source/1', source_id=f'{session}-1', session=session,
                    capture_id=1, sha256=hashlib.sha256(png).hexdigest(), media_type='image/png',
                    presented_ms=123, received_wall=456.0, width=4, height=2,
                    window_width=4, window_height=2, viewport=[0, 0, 4, 2])
    with Journal(tmp_path/'journal', max_source_bytes=len(png)) as journal:
        with pytest.raises(PlayerError):
            journal.register_source(metadata, png+b'changed')
        journal.register_source(metadata, png)
        journal.register_source(metadata, png)
        with pytest.raises(PlayerError):
            journal.register_source(dict(metadata, received_wall=999), png)
        with pytest.raises(PlayerError, match='capacity'):
            journal.register_source(dict(metadata, source_id=f'{session}-2', capture_id=2), png)
        assert journal.read_source(metadata['source_id']) == (metadata, png)
        journal._db.execute('UPDATE sources SET png=? WHERE id=?', (png+b'x', metadata['source_id']))
        journal._db.commit()
        with pytest.raises(PlayerError):
            journal.read_source(metadata['source_id'])
