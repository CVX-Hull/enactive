"""Actual V8/Pillow and fake mechanical port; no native acceptance."""
import hashlib
from unittest.mock import patch

import pytest

from harness.player.contracts import PlayerError
from harness.player.images import program_view
from harness.player.memory import Memory
from harness.player.programs import ProgramRepository, ProgramRunner
from test_player_context import program
from test_player_memory import capture, record


def test_program_lineage_and_immutable_support(tmp_path):
    with Memory(tmp_path / 'memory') as memory:
        repo = ProgramRepository(memory)
        r = memory.append('actor', record())
        root = repo.save('actor', program(record_ids=[r['id']]))
        child = repo.save('actor', program(parent_id=root['id']))
        assert child['sha256'] == hashlib.sha256(child['code'].encode()).hexdigest()
        assert repo.read(child['id']) == child
        for bad in (program(parent_id='missing'), program(record_ids=['missing']),
                    program(schema='procedure/3'), program(code='x' * 32769)):
            with pytest.raises(PlayerError):
                repo.save('actor', bad)
        sibling = repo.save('actor', program(parent_id=root['id']))
        assert sibling['id'] != child['id']
        assert repo.read(child['id'])['parent_id'] == repo.read(sibling['id'])['parent_id']


def test_actual_image_crop_sampling_alpha_and_full_reference():
    metadata, png = capture(size=(8, 4))
    view = program_view(metadata, png, {'crop': [2, 1, 4, 2], 'size': [2, 2]}, {'guess': 'red'}, {'seconds': 5})
    assert view['schema'] == 'program-view/3'
    assert view['source'] == metadata
    assert view['image']['width'] == 2 and view['image']['height'] == 1
    assert view['image']['rgb'] == [128, 0, 0] * 2
    assert view['image']['crop'] == [2, 1, 4, 2]
    assert view['image']['sampling'] == 'nearest'
    assert view['image']['alpha'] == 'composited-on-black'
    assert view['image']['omissions']
    assert view['interpretation'] == {'guess': 'red'}
    for selection in ({'crop': [7, 0, 2, 1], 'size': [1, 1]}, {'crop': None, 'size': [97, 1]},
                      {'crop': None, 'size': [True, 1]}, {'crop': None, 'size': [1, 1], 'other': 1}):
        with pytest.raises(PlayerError):
            program_view(metadata, png, selection, {}, {})
    with pytest.raises(PlayerError):
        program_view(metadata, png + b'corrupt', {'crop': None, 'size': [1, 1]}, {}, {})


class Port:
    def __init__(self, status='completed'):
        self.calls = []
        self.status = status

    def result(self, kind):
        metadata, png = capture(capture_id=len(self.calls))
        return dict(operation_id=str(len(self.calls)), source=metadata, status=self.status,
                    kind=kind, remaining={'seconds': 19}), png

    def observe(self, actor_id, *, deadline_monotonic=None):
        self.calls.append(('observe', actor_id, deadline_monotonic))
        return self.result('observe')

    def input(self, actor_id, actions, *, source_id=None, deadline_monotonic=None):
        self.calls.append(('input', actor_id, actions, source_id, deadline_monotonic))
        return self.result('input')


def test_runner_consumes_actual_initial_and_post_input_captures(tmp_path):
    with Memory(tmp_path / 'memory') as memory:
        repo = ProgramRepository(memory)
        p = repo.save('a', program(code="""function step(v,s){
          const n=(s.n||0)+1;
          return {status:n===3?'done':'act',state:{n,capture:v.source.capture_id},
                  actions:n===3?null:[{type:'key',key:'x',modifiers:[]}],reason:'player choice'};
        }"""))
        port = Port()
        run = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [4, 4]})
        assert [c[0] for c in port.calls] == ['observe', 'input', 'input']
        assert run['status'] == 'done' and run['final_state'] == {'n': 3, 'capture': 3}
        assert [s['source']['capture_id'] for s in run['steps']] == [1, 2, 3]
        assert len(run['operations']) == 3
        assert port.calls[0][2] == port.calls[1][4] == port.calls[2][4]
        assert memory._db.execute('SELECT COUNT(*) FROM sources').fetchone()[0] == 0


def test_yield_fault_unknown_and_original_time_leave_no_helper_authority(tmp_path):
    with Memory(tmp_path / 'memory') as memory:
        repo = ProgramRepository(memory)
        for code, status in ((program()['code'], 'yield'), ('function step(){throw Error("bad")}', 'fault')):
            port = Port()
            p = repo.save('a', program(code=code))
            run = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [1, 1]})
            assert run['status'] == status
            assert [c[0] for c in port.calls] == ['observe']
            port.input('a', [{'type': 'key', 'key': 'x', 'modifiers': []}])
        p = repo.save('a', program(code="function step(v,s){return {status:'act',state:s,actions:[{type:'wait',seconds:0}],reason:'try'}}"))
        port = Port('unknown')
        run = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [1, 1]})
        assert run['status'] == 'unknown' and len(port.calls) == 1
        port = Port()
        with patch('harness.player.programs.monotonic', side_effect=[10, 10, 10, 31, 31]):
            run = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [1, 1]}, max_seconds=20)
        assert run['status'] == 'limit' and len(port.calls) == 1
        for kwargs in ({'max_steps': 65}, {'max_seconds': 21}, {'max_seconds': float('nan')}):
            port = Port()
            result = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [1, 1]}, **kwargs)
            assert result['status'] == 'fault' and port.calls == []


def test_runner_retains_uncertain_input_without_replay(tmp_path):
    class Uncertain(Port):
        def input(self, actor_id, actions, *, source_id=None, deadline_monotonic=None):
            operation, png = super().input(actor_id, actions, source_id=source_id,
                                           deadline_monotonic=deadline_monotonic)
            operation['status'] = self.delivery
            return operation, png

    with Memory(tmp_path / 'memory') as memory:
        repo = ProgramRepository(memory)
        p = repo.save('a', program(code="function step(v,s){return {status:'act',state:s,actions:[{type:'text',text:'try'}],reason:'choice'}}"))
        for delivery in ('partial', 'unknown', 'refused'):
            port = Uncertain()
            port.delivery = delivery
            run = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [1, 1]})
            assert run['status'] == delivery
            assert [c[0] for c in port.calls] == ['observe', 'input']
            assert run['operations'][-1]['operation_id'] == '2'
            assert run['steps'][0]['input_operation']['status'] == delivery


def test_runner_reobserves_only_when_input_returns_no_capture_and_never_renews(tmp_path):
    class MissingCapture(Port):
        def input(self, actor_id, actions, *, source_id=None, deadline_monotonic=None):
            operation, _ = super().input(actor_id, actions, source_id=source_id,
                                         deadline_monotonic=deadline_monotonic)
            operation['source'] = None
            return operation, None

    with Memory(tmp_path / 'memory') as memory:
        repo = ProgramRepository(memory)
        p = repo.save('a', program(code="function step(v,s){return {status:s.n?'done':'act',state:{n:1},actions:s.n?null:[{type:'wait',seconds:0}],reason:'choice'}}"))
        port = MissingCapture()
        run = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [1, 1]})
        assert run['status'] == 'done'
        assert [c[0] for c in port.calls] == ['observe', 'input', 'observe']
        assert port.calls[0][2] == port.calls[1][4] == port.calls[2][2]
        port = Port()
        clock = iter([10, 10, 10, 10, 31, 31])
        with patch('harness.player.programs.monotonic', side_effect=lambda: next(clock, 31)):
            run = ProgramRunner(repo, port).run(p['id'], 'a', {}, {}, {'crop': None, 'size': [1, 1]}, max_seconds=20)
        assert run['status'] == 'limit'
        assert [c[0] for c in port.calls] == ['observe']  # evaluation consumed original allowance
