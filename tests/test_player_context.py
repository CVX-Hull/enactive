"""Bounded complete records and explicit omitted provenance."""
import pytest

from harness.player.contracts import PlayerError, canonical
from harness.player.memory import Memory
from harness.player.programs import ProgramRepository
from test_player_memory import capture, record


def program(**changes):
    return {**dict(schema='player-program/1', code="function step(v,s){return {status:'yield',state:s,actions:null,reason:'inspect'}}",
                  parent_id=None, reason='candidate', source_ids=[], record_ids=[], applicability=None), **changes}


def test_context_closes_correction_support_program_and_sources(tmp_path):
    with Memory(tmp_path / 'memory') as memory:
        metadata, png = capture()
        memory.register_source(metadata, png)
        claim = memory.append('a', record(sources=[metadata['source_id']]))
        repo = ProgramRepository(memory)
        parent = repo.save('a', program(record_ids=[claim['id']]))
        child = repo.save('a', program(parent_id=parent['id']))
        decision = memory.append('a', record('decision', program_id=child['id']))
        correction = memory.append('a', record('correction', supersedes=claim['id']))
        context = memory.context([decision['id']])
        assert {r['id'] for r in context['records']} == {decision['id'], claim['id'], correction['id']}
        assert {p['id'] for p in context['programs']} == {parent['id'], child['id']}
        assert context['sources'][0]['source'] == metadata
        assert context['sources'][0]['read_verified'] is False
        assert context['omissions'] == []
        assert memory.context([child['id']])['programs']


def test_context_omits_whole_large_record_or_code(tmp_path):
    with Memory(tmp_path / 'memory') as memory:
        big = memory.append('a', record(text='x' * 8192))
        p = ProgramRepository(memory).save('a', program(code='//' + 'x' * 32000))
        for identity in (big['id'], p['id']):
            context = memory.context([identity], max_bytes=1024)
            assert not context['records'] and not context['programs']
            assert context['omissions'][0]['id'] == identity
            assert len(canonical(context).encode()) <= 1024
        with pytest.raises(PlayerError):
            memory.context([big['id']] * 33)
        with pytest.raises(PlayerError):
            memory.context([], max_bytes=65537)
        context = memory.context(['missing'])
        assert context['omissions'][0]['id'] == 'missing'


def test_context_reports_source_loss_and_bounds_deep_ancestry(tmp_path):
    with Memory(tmp_path / 'memory') as memory:
        metadata, png = capture()
        memory.register_source(metadata, png)
        first = memory.append('a', record(sources=[metadata['source_id']]))
        memory._db.execute('UPDATE sources SET png=NULL WHERE id=?', (metadata['source_id'],))
        memory._db.commit()
        context = memory.context([first['id']])
        assert context['sources'][0]['available'] is False
        assert any(o['id'] == metadata['source_id'] for o in context['omissions'])
        near_limit = len(canonical(context).encode('utf-8')) - 1
        bounded_loss = memory.context([first['id']], max_bytes=near_limit)
        assert len(canonical(bounded_loss).encode('utf-8')) <= near_limit
        assert bounded_loss['omissions']
        last = first
        for _ in range(150):
            last = memory.append('a', record(supports=[last['id']]))
        bounded = memory.context([last['id']])
        assert len(canonical(bounded).encode()) <= 65536
        assert bounded['omissions']
