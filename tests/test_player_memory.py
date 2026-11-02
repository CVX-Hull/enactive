"""Current player storage integration; no native/game outcome evidence."""
import hashlib
import io
import sqlite3

import pytest
from PIL import Image

from harness.player.contracts import PlayerError
from harness.player.memory import Memory


def capture(color=(255, 0, 0, 128), size=(4, 2), capture_id=1):
    stream = io.BytesIO()
    Image.new('RGBA', size, color).save(stream, format='PNG')
    png = stream.getvalue()
    session = 'a' * 32
    metadata = dict(schema='computer-source/1', source_id=f'{session}-{capture_id}',
                    session=session, capture_id=capture_id, sha256=hashlib.sha256(png).hexdigest(),
                    media_type='image/png', presented_ms=123, received_wall=456.0,
                    width=size[0], height=size[1], window_width=size[0], window_height=size[1],
                    viewport=[0, 0, *size])
    return metadata, png


def record(kind='claim', **changes):
    return {**dict(schema='player-record/1', kind=kind, text='fallible observation', data={},
                   sources=[], supports=[], supersedes=None, applicability=None, program_id=None), **changes}


def test_durable_corrections_and_supports(tmp_path):
    path = tmp_path / 'memory.sqlite3'
    with Memory(path) as memory:
        metadata, png = capture()
        memory.register_source(metadata, png)
        first = memory.append('actor', record(sources=[metadata['source_id']]))
        correction = memory.append('next-actor', record('correction', supersedes=first['id'],
                                                       supports=[first['id']]))
        assert memory.query() == [correction]
        assert memory.query(include_superseded=True) == [correction, first]
        assert memory.read(first['id']) == first
        with pytest.raises(PlayerError):
            memory.append('actor', record(supports=['absent']))
        with pytest.raises(PlayerError):
            memory.append('actor', record('correction'))
        assert memory.query(limit=1) == [correction]
        with pytest.raises(PlayerError):
            memory.query(limit=51)
    with Memory(path) as memory:
        assert memory.read_source(metadata['source_id']) == (metadata, png)
        assert memory.read(correction['id']) == correction


def test_closed_current_formats_capacity_and_original_time(tmp_path):
    metadata, png = capture()
    with Memory(tmp_path / 'memory', max_source_bytes=len(png)) as memory:
        memory.register_source(metadata, png)
        memory.register_source(metadata, png)  # exact duplicate consumes no capacity
        with pytest.raises(PlayerError):
            memory.register_source({**metadata, 'received_wall': 999}, png)
        other, other_png = capture(capture_id=2)
        with pytest.raises(PlayerError):
            memory.register_source(other, other_png)
        assert memory.read_source(metadata['source_id'])[0]['received_wall'] == 456
        for bad in (record(schema='campaign-memory/6'), record(extra=True), record(data={'x': float('nan')}),
                    record(sources=['not-registered']), record(text='x' * 8193)):
            with pytest.raises(PlayerError):
                memory.append('actor', bad)
        assert memory.query() == []
        assert memory._db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    old = tmp_path / 'old'
    db = sqlite3.connect(old)
    db.execute('CREATE TABLE old_memory (id TEXT)')
    db.close()
    with pytest.raises(PlayerError):
        Memory(old)


def test_source_integrity_and_caller_copy_isolation(tmp_path):
    metadata, png = capture()
    with Memory(tmp_path / 'memory') as memory:
        with pytest.raises(PlayerError):
            memory.register_source(metadata, png + b'changed')
        memory.register_source(metadata, png)
        r = memory.append('actor', record(data={'quantity': 3}, sources=[metadata['source_id']]))
        r['data']['quantity'] = 99
        assert memory.read(r['id'])['data']['quantity'] == 3
        memory._db.execute('UPDATE sources SET png=? WHERE id=?', (png + b'x', metadata['source_id']))
        memory._db.commit()
        with pytest.raises(PlayerError):
            memory.read_source(metadata['source_id'])


def test_multi_record_append_is_one_transaction_with_derived_ids(tmp_path):
    with Memory(tmp_path / 'player.sqlite3') as memory:
        prior = memory.append('b' * 32, record('work'))
        request = 'c' * 32
        first, second = Memory.batch_ids(request, 2)
        batch = [record('work', text='replacement'),
                 record('correction', supersedes=prior['id'], supports=[first])]
        stored = memory.append_many('d' * 32, batch, request_id=request)
        assert [r['id'] for r in stored] == [first, second]
        assert [r['id'] for r in memory.current('work')] == [first]
        assert memory.append_many('d' * 32, batch, request_id=request) == stored
        with pytest.raises(PlayerError, match='conflicts'):
            memory.append_many('e' * 32, batch, request_id=request)
        # A failing later record rolls back the earlier one in the same batch.
        with pytest.raises(PlayerError, match='Missing records reference'):
            memory.append_many('d' * 32, [record('work', text='orphan'), record('correction', supersedes='missing')],
                               request_id='f' * 32)
        assert memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0] == 3
        for count in (0, 17):
            with pytest.raises(PlayerError):
                memory.append_many('d' * 32, [record()] * count, request_id='0' * 32)


def test_service_row_and_records_commit_in_one_transaction(tmp_path):
    with Memory(tmp_path / 'player.sqlite3') as memory:
        request = '1' * 32
        service = ('player_level_replace', dict(text='x'), dict(status='committed'))
        stored = memory.append_many('d' * 32, [record('work')], request_id=request, service=service)
        collected = memory.service_result(request, 'd' * 32)
        assert collected['status'] == 'completed' and collected['value'] == dict(status='committed', records=stored)
        assert memory.append_many('d' * 32, [], request_id='2' * 32, service=service) == []
        assert memory.service_result('2' * 32)['value'] == dict(status='committed', records=[])
        with pytest.raises(PlayerError, match='Missing records reference'):
            memory.append_many('d' * 32, [record('correction', supersedes='missing')], request_id='3' * 32,
                               service=service)
        with pytest.raises(PlayerError, match='Unknown original'):
            memory.service_result('3' * 32)
        # A failing service-row insert rolls back the records already inserted before it.
        assert memory.begin_service('4' * 32, 'd' * 32, 'other_tool', {})
        with pytest.raises(PlayerError, match='Cannot remember'):
            memory.append_many('d' * 32, [record('work')], request_id='4' * 32, service=service)
        assert memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0] == 1


def episode_claim(**changes):
    data = dict(level='episode', level_contract='player-episode/1', settled='failed', writer='software',
                session='s' * 32, actor_id='a' * 32, first_position=1, last_position=1, subgoal_id=None, reason='r')
    return record('claim', data=data | changes)


def test_the_general_append_paths_refuse_reserved_data_and_only_the_custodian_paths_admit_it(tmp_path):
    from harness.player.contracts import RememberError
    with Memory(tmp_path / 'player.sqlite3') as memory:
        for data in (dict(level='episode'), dict(level='subgoal'), dict(writer='recorder'), dict(level_contract='x'),
                     dict(by='software'), dict(level='episode', writer='software')):
            with pytest.raises(PlayerError, match='reserves'):
                memory.append('a' * 32, record(data=data))
            with pytest.raises(PlayerError, match='reserves'):
                memory.append_many('a' * 32, [record(data=data)], request_id='1' * 32)
        assert memory._db.execute('SELECT COUNT(*) FROM records').fetchone()[0] == 0
        # Other data stays admitted.
        memory.append('a' * 32, record(data=dict(note='fine', by='me')))
        with pytest.raises(PlayerError, match='reserves'):
            memory.append('a' * 32, episode_claim())
        (stored,) = memory.append_many('a' * 32, [episode_claim()], request_id='2' * 32, custodian=True)
        assert [(row, r['id']) for row, r in memory.episode_claims()] == [(2, stored['id'])]
        assert memory.rowid(stored['id']) == 2 and memory.revision() == 2
        assert memory.episode_claims(after_row=2) == [] and len(memory.episode_claims(after_row=1)) == 1
        assert [r['id'] for r in memory.level_records('claim', 'episode')] == [stored['id']]
        assert memory.level_records('work', 'subgoal') == []
        with pytest.raises(PlayerError, match='Unknown records identity'):
            memory.rowid('missing')
        assert issubclass(RememberError, PlayerError)


def test_a_storage_fault_or_source_capacity_is_a_remember_error_and_a_refusal_is_not(tmp_path):
    from harness.player.contracts import RememberError
    with Memory(tmp_path / 'player.sqlite3', max_source_bytes=1) as memory:
        metadata, png = capture()
        with pytest.raises(RememberError, match='source capacity exceeded'):
            memory.register_source(metadata, png)
        with pytest.raises(PlayerError) as refused:
            memory.append('a' * 32, record(supports=['missing']))
        assert not isinstance(refused.value, RememberError)
        memory._db.execute('PRAGMA query_only=ON')
        with pytest.raises(RememberError, match='Cannot remember'):
            memory.append('a' * 32, record())


def test_revision_and_rowid_wrap_storage_errors_as_player_errors(tmp_path):
    memory = Memory(tmp_path / 'player.sqlite3')
    stored = memory.append('a' * 32, record())
    assert memory.revision() == 1 and memory.rowid(stored['id']) == 1
    memory._db.close()
    for call in (memory.revision, lambda: memory.rowid(stored['id'])):
        with pytest.raises(PlayerError, match='Cannot query player memory'):
            call()
