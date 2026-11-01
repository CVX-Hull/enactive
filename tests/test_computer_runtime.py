"""SQLite/control integration fixtures; these are not game/native qualification."""
import hashlib
import io
import threading
import time
from unittest.mock import patch

from PIL import Image
import pytest

from harness.computer.protocol import ControlError
from harness.computer.runtime import ComputerRuntime


class Process:
    def poll(self):
        return None


class Channel:
    """Explicit receiver double; real SDL behavior has a separate native lane."""
    def __init__(self):
        self.stopped = threading.Event()
        self.fault = None
        self.calls = []
        self.capture = 1
        self.unknown = False
        self.late = {}
        self.pending = {}
        self.times = {}
        self.before_request = None
        image = Image.new('RGB', (4, 4), 'red')
        out = io.BytesIO(); image.save(out, format='PNG'); self.png = out.getvalue()

    def target(self):
        return dict(window_id=1, paused=self.stopped.is_set())

    def stop(self, reason):
        self.stopped.set()
        return dict(stop_requested=True, native_pause_confirmed=False, reason=reason)

    def stop_status(self):
        return dict(stop_requested=self.stopped.is_set(), native_pause_confirmed=False)

    def request(self, kind, value, deadline, identity):
        if self.before_request:
            self.before_request()
        self.calls.append((kind, value, deadline, identity))
        self.times[identity] = dict(receipt_received_wall=time.time(),receipt_received_monotonic=time.monotonic())
        if self.unknown:
            self.stopped.set()
            return dict(schema='computer-transport/2', id=identity, session='a'*32,
                disposition='unknown', emitted_events=None, reason='lost original receipt', frame=None), None
        frame = None
        if kind == 'observe':
            frame = dict(name=f'frame-{self.capture}.png', capture_id=self.capture, presented_ms=1000,
                width=4, height=4, window_width=4, window_height=4, viewport=[0, 0, 4, 4])
        value = dict(schema='computer-receipt/2', id=identity, session='a'*32,
            disposition='delivered', emitted_events=2 if kind == 'input' else 0,
            reason='delivered only', frame=frame), self.png if frame else None
        self.pending[identity] = value
        return value

    def timing(self, identity):
        return self.times.get(identity,{}).copy()

    def release(self, identity):
        self.late.pop(identity, None)
        self.pending.pop(identity,None)

    def collect(self, identity):
        return self.late.get(identity) or self.pending.get(identity)

    def close(self):
        self.stop('closed')


def make_runtime(tmp_path, *, mint=True, **limits):
    """mint=False leaves minting to a composition that registers the actor's tool profile."""
    channel = Channel()
    values = dict(max_inputs=20, max_requests=30, max_frames=40, max_bytes=2**30)
    values.update(limits)
    runtime = ComputerRuntime(tmp_path, 'a'*32, channel, Process(), time.monotonic()+60, values)
    actor = runtime.add_actor() if mint else None
    return runtime, channel, actor


def key(value='x'):
    return dict(type='key', key=value, modifiers=[])


def test_sealed_actor_stop_bypasses_quiescence_database_wait(tmp_path):
    runtime,channel,actor=make_runtime(tmp_path)
    identity='f'*32
    runtime.seal_actor(actor['actor_id'],identity,'e'*32,'d'*64)
    entered=threading.Event();errors=[]
    original=runtime.store.set_actor_stage
    def write(*args):entered.set();return original(*args)
    def confirm():
        try:runtime.confirm_quiescent(actor['actor_id'],identity,host_quiescent=True)
        except ControlError as exc:errors.append(exc)
    try:
        with patch.object(runtime.store,'set_actor_stage',side_effect=write):
            with runtime.store.lock:
                thread=threading.Thread(target=confirm);thread.start()
                assert entered.wait(1)
                started=time.monotonic()
                assert runtime.stop_actor(actor['token'],'Cancelled during quiescence')['stop_requested']
                assert channel.stopped.is_set() and time.monotonic()-started<.25
            thread.join(2)
        assert not thread.is_alive() and errors
        with pytest.raises(ControlError):runtime.add_actor()
    finally:runtime.close()


def test_original_id_duplicate_collects_without_charging_or_redispatch(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        identity = 'b'*32
        first, png = runtime.input(actor['actor_id'], [key()], operation_id=identity)
        assert first['status'] == 'completed' and png == channel.png
        count = len(channel.calls)
        original_remaining = runtime.remaining()['inputs']
        second, png2 = runtime.input(actor['actor_id'], [key('z')], operation_id=identity)
        assert second == first and png2 == png
        assert len(channel.calls) == count
        assert runtime.remaining()['inputs'] == original_remaining
        assert runtime.store.connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    finally:
        runtime.close()


def test_each_receipt_precedes_next_input_and_unchanged_images_do_not_veto_keys(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        def prior_results_retained():
            rows = runtime.store.connection.execute('SELECT receipt FROM native_intents ORDER BY rowid').fetchall()
            assert all(r[0] is not None for r in rows[:-1])
        channel.before_request = prior_results_retained
        first, _ = runtime.observe(actor['actor_id'])
        second, _ = runtime.input(actor['actor_id'], [key(), key('y')])
        assert first['source']['source_id'] == second['source']['source_id']
        assert len([r for r in channel.calls if r[0] == 'input']) == 2
        assert runtime.remaining()['frames'] == 39
    finally:
        runtime.close()


def test_complete_validation_and_frame_capacity_precede_all_events(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path, max_bytes=10)
    try:
        with pytest.raises(ControlError):
            runtime.input(actor['actor_id'], [key(), {'type':'key','key':'bad'}])
        assert channel.calls == []
        with pytest.raises(ControlError, match='capture reservation'):
            runtime.input(actor['actor_id'], [key()])
        assert channel.calls == []
        assert runtime.store.counts()['inputs'] == 0
    finally:
        runtime.close()


def test_pointer_requires_actor_issued_source_and_original_geometry(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        click = dict(type='click', x=1, y=2, button='left')
        with pytest.raises(ControlError):
            runtime.input(actor['actor_id'], [click], source_id='not-issued')
        source, _ = runtime.observe(actor['actor_id'])
        runtime.input(actor['actor_id'], [click], source_id=source['source']['source_id'])
        assert channel.calls[-2][1]['geometry']['viewport'] == [0, 0, 4, 4]
        with pytest.raises(ControlError):
            runtime.input(actor['actor_id'], [dict(click,x=4)], source_id=source['source']['source_id'])
    finally:
        runtime.close()


def test_unknown_is_charged_late_collection_cannot_replay_or_restore(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        channel.unknown = True
        result, _ = runtime.input(actor['actor_id'], [key()])
        assert result['status'] == 'unknown' and runtime.remaining()['inputs'] == 19
        identity = result['receipts'][0]['id']
        channel.late[identity] = (dict(schema='computer-receipt/2', id=identity, session='a'*32,
            disposition='delivered', emitted_events=2, reason='late original', frame=None), None)
        collected, _ = runtime.result(actor['actor_id'], result['operation_id'])
        assert collected['status'] == 'unknown'
        assert [r['schema'] for r in collected['receipts']] == ['computer-transport/2','computer-receipt/2']
        with pytest.raises(ControlError):
            runtime.input(actor['actor_id'], [key()])
        assert len(channel.calls) == 1
    finally:
        runtime.close()


def test_handoff_changes_only_custody_and_keeps_original_resources(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        first, _ = runtime.observe(actor['actor_id'])
        remaining = runtime.remaining()['requests']
        sealed = runtime.seal_actor(actor['actor_id'], 'b'*32, 'c'*32, 'd'*64)
        assert sealed['handoff']['grants_authority'] is False
        assert runtime.authorize(actor['token']) == actor['actor_id']
        with pytest.raises(ControlError):
            runtime.authorize(actor['token'], write=True)
        with pytest.raises(ControlError):
            runtime.add_actor()
        runtime.confirm_quiescent(actor['actor_id'], sealed['operation_id'], host_quiescent=True)
        successor = runtime.add_actor()
        assert runtime.remaining()['requests'] == remaining - 1
        assert successor['actor_id'] != actor['actor_id'] and not channel.stopped.is_set()
        assert runtime.result(actor['actor_id'], first['operation_id'])[0] == first
        with pytest.raises(ControlError):
            runtime.input(actor['actor_id'], [key()])
        with pytest.raises(ControlError):
            runtime.input(successor['actor_id'], [dict(type='click', x=1,y=1,button='left')],
                          source_id=first['source']['source_id'])
    finally:
        runtime.close()


def test_pause_and_smaller_deadline_cannot_become_handoff_or_renewal(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        limit = time.monotonic() + .5
        result, _ = runtime.observe(actor['actor_id'], deadline_monotonic=limit)
        assert result['deadline_monotonic'] == limit
        runtime.stop('user')
        with pytest.raises(ControlError):
            runtime.seal_actor(actor['actor_id'], 'b'*32, 'c'*32, 'd'*64)
        with pytest.raises(ControlError):
            runtime.observe(actor['actor_id'])
    finally:
        runtime.close()


def test_current_source_corruption_stops_input_without_inventing_success(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    try:
        result, _ = runtime.observe(actor['actor_id'])
        metadata = result['source']
        assert metadata['sha256'] == hashlib.sha256(channel.png).hexdigest()
        (tmp_path/'sources'/f"{metadata['source_id']}.png").write_bytes(b'corrupt')
        with pytest.raises(ControlError):
            runtime.source(metadata['source_id'])
        assert channel.stopped.is_set()
    finally:
        runtime.close()


def test_failed_png_publication_keeps_ids_receipts_and_original_receive_time(tmp_path,monkeypatch):
    runtime,channel,actor=make_runtime(tmp_path)
    original=runtime._capture
    try:
        def fail(*args):
            raise OSError('controlled source publication failure')
        monkeypatch.setattr(runtime,'_capture',fail)
        first,_=runtime.input(actor['actor_id'],[key()])
        assert first['status']=='unknown'
        assert len(first['receipts'])==2
        assert all(r['schema']=='computer-receipt/2' for r in first['receipts'])
        capture_id=channel.calls[-1][3]
        received=channel.timing(capture_id)['receipt_received_wall']
        monkeypatch.setattr(runtime,'_capture',original)
        collected,png=runtime.result(actor['actor_id'],first['operation_id'])
        assert len(channel.calls)==2 and png==channel.png
        assert len(collected['receipts'])==2 and collected['status']=='unknown'
        assert collected['source']['received_wall']==received
        assert channel.stopped.is_set()
        with pytest.raises(ControlError):
            runtime.input(actor['actor_id'],[key()])
    finally:
        runtime.close()


def test_corrupt_pointer_source_refuses_before_any_new_effect(tmp_path):
    runtime,channel,actor=make_runtime(tmp_path)
    try:
        frame,_=runtime.observe(actor['actor_id'])
        source_id=frame['source']['source_id']
        (tmp_path/'sources'/f'{source_id}.png').write_bytes(b'corrupt')
        before=len(channel.calls)
        with pytest.raises(ControlError):
            runtime.input(actor['actor_id'],[dict(type='click',x=1,y=1,button='left')],source_id=source_id)
        assert len(channel.calls)==before and channel.stopped.is_set()
    finally:
        runtime.close()
