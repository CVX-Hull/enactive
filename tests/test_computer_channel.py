"""Actual local sockets plus one injected partial-send fault; no native/game proof."""
import socket
import struct
import threading
import time
import sys

import pytest

from harness.computer.channel import NativeChannel
from harness.computer.protocol import NoDispatch,decode_json,encode_packet


def receive_packet(link):
    def take(size):
        data=b''
        while len(data)<size:
            part=link.recv(size-len(data))
            assert part
            data+=part
        return data
    size=struct.unpack('!I',take(4))[0]
    header=decode_json(take(size))
    payload=take(header['payload_bytes']) if header['payload_bytes'] else b''
    return header,payload


class Link:
    def __init__(self,link,*,interrupt=False,fragment=False):
        self.link=link;self.interrupt=interrupt;self.fragment=fragment
        self.sends=[];self.reads=0;self.shutdowns=[]
    def fileno(self):return self.link.fileno()
    def setblocking(self,value):self.link.setblocking(value)
    def recv(self,size):
        self.reads+=1
        return self.link.recv(min(size,3) if self.fragment else size)
    def send(self,data):
        if self.interrupt and self.sends:
            raise OSError('Injected interruption after documented partial send')
        sent=self.link.send(data[:7] if self.interrupt else data)
        self.sends.append(sent)
        return sent
    def shutdown(self,how):
        self.shutdowns.append(how);self.link.shutdown(how)
    def close(self):self.link.close()


def native_receipt(identity,**changes):
    return dict(dict(schema='computer-receipt/2',id=identity,session='a'*32,
        disposition='delivered',emitted_events=2,reason='fixture event handoff only',frame=None),**changes)


def test_interrupted_framing_half_closes_before_any_pause_packet():
    left,right=socket.socketpair();link=Link(left,interrupt=True)
    channel=NativeChannel(link,'a'*32,123)
    right.settimeout(1)
    try:
        result,_=channel.request('input',{'type':'key','key':'x','modifiers':[]},time.monotonic()+1,'b'*32)
        assert result['disposition']=='unknown' and channel.stopped.is_set()
        assert len(right.recv(4096))==7
        assert right.recv(4096)==b''
        assert link.sends==[7] and socket.SHUT_WR in link.shutdowns
        with pytest.raises(NoDispatch):
            channel.request('input',{},time.monotonic()+1,'c'*32)
    finally:
        channel.close();right.close()


@pytest.mark.parametrize('seconds,start,continuation', [(12,5.,11.75),(3,3.,2.75),(.6,.6,.6)])
def test_request_carries_start_and_continuation_bounds(seconds,start,continuation):
    """#396: the first event within 5 s; the rest until the operation deadline less 250 ms."""
    left,right=socket.socketpair();channel=NativeChannel(left,'a'*32,123);result=[]
    try:
        before=time.time()
        thread=threading.Thread(target=lambda:result.append(channel.request('input',{},time.monotonic()+seconds,'b'*32)))
        thread.start();header,_=receive_packet(right)
        value=header['value']
        assert value['schema']=='computer-request/3'
        assert value['expires_ms']<=value['continue_ms']
        assert abs(value['expires_ms']/1000-before-start)<.1
        assert abs(value['continue_ms']/1000-before-max(start,continuation))<.1
        right.sendall(encode_packet('receipt',native_receipt('b'*32)))
        thread.join(2);assert result[0][0]['disposition']=='delivered'
        channel.release('b'*32)
    finally:
        channel.close();right.close()


def test_pause_has_no_continuation():
    left,right=socket.socketpair();channel=NativeChannel(left,'a'*32,123)
    try:
        channel.stop('Operator Pause');header,_=receive_packet(right)
        value=header['value']
        assert value['kind']=='pause' and value['continue_ms']==value['expires_ms']
    finally:
        channel.close();right.close()


def test_first_stop_origin_survives_later_adapter_cleanup():
    left,right=socket.socketpair();channel=NativeChannel(left,'a'*32,123)
    try:
        before=time.monotonic()
        channel.stop('Operator Pause')
        origin=channel.stop_origin()
        channel.stop('Actor adapter closed')
        assert channel.stop_origin()==origin
        assert origin['reason']=='Operator Pause' and before<=origin['requested_monotonic']<=time.monotonic()
        assert channel.stopped.is_set()
    finally:
        channel.close();right.close()


def test_visible_fence_has_published_origin_before_later_cleanup():
    from tools.campaign_player import finish_interruption
    left,right=socket.socketpair();channel=NativeChannel(left,'a'*32,123)
    fenced,release=threading.Event(),threading.Event()
    def trace(frame,event,arg):
        if (event=='line' and frame.f_code is NativeChannel.stop.__code__
                and channel.stopped.is_set() and not fenced.is_set()):
            # Suspend after the fence and origin publication lock is released.
            if not channel._stop_origin_lock.locked():
                fenced.set();assert release.wait(2)
        return trace
    def pause():
        sys.settrace(trace)
        try:channel.stop('Operator Pause')
        finally:sys.settrace(None)
    worker=threading.Thread(target=pause)
    try:
        worker.start();assert fenced.wait(2)
        channel.stop('Actor adapter closed')
        assert finish_interruption(channel)['stop']['reason']=='Operator Pause'
    finally:
        release.set();worker.join(2);channel.close();right.close()
    assert not worker.is_alive()


@pytest.mark.parametrize('cause', ['takeover', 'partial', 'unknown'])
def test_native_fence_origin_survives_cleanup_and_late_collection(cause):
    from tools.campaign_player import finish_interruption
    from harness.player_client import ADAPTER_CLOSE_REASON
    left,right=socket.socketpair();channel=NativeChannel(left,'a'*32,123)
    request=None;result=[]
    reason='Native human takeover' if cause=='takeover' else 'Native delivery '+cause
    try:
        before=time.monotonic()
        if cause=='takeover':
            value=dict(schema='computer-target/2',session='a'*32,pid=123,
                window_id=1,paused=True,takeover_generation=1,latest_frame=None,error=reason)
            right.sendall(encode_packet('state',value))
        else:
            request=threading.Thread(target=lambda:result.append(
                channel.request('input',{},time.monotonic()+2,'b'*32)))
            request.start();receive_packet(right)
            value=native_receipt('b'*32,disposition=cause,reason=reason)
            right.sendall(encode_packet('receipt',value))
        assert channel.stopped.wait(2)
        origin=channel.stop_origin()
        assert origin['reason']==reason
        assert before<=origin['requested_monotonic']<=time.monotonic()
        assert origin['requested_wall'] is not None
        channel.stop(ADAPTER_CLOSE_REASON)
        assert channel.stop_origin()==origin
        assert finish_interruption(channel)['stop']==origin
        with pytest.raises(NoDispatch):
            channel.request('input',{},time.monotonic()+1,'c'*32)
        if request:
            request.join(2);assert not request.is_alive()
            assert result[0][0]==value and channel.collect('b'*32)[0]==value
    finally:
        channel.close();right.close()
        if request:request.join(2)


def test_native_fence_and_concurrent_cleanup_publish_one_origin_without_deadlock():
    from tools.campaign_player import finish_interruption
    from harness.player_client import ADAPTER_CLOSE_REASON
    left,right=socket.socketpair();channel=NativeChannel(left,'a'*32,123)
    fenced,release=threading.Event(),threading.Event()
    errors=[]
    def trace(frame,event,arg):
        if event=='return' and frame.f_code is NativeChannel._latch_stop.__code__:
            fenced.set()
            if not release.wait(2):errors.append('native receive did not resume')
        return trace
    value=dict(schema='computer-target/2',session='a'*32,pid=123,
        window_id=1,paused=True,takeover_generation=1,latest_frame=None,error='Native human takeover')
    def native_state():
        sys.settrace(trace)
        try:channel._accept(dict(kind='state',value=value),b'',time.time(),time.monotonic())
        finally:sys.settrace(None)
    receiver=threading.Thread(target=native_state)
    cleanup=threading.Thread(target=lambda:channel.stop(ADAPTER_CLOSE_REASON))
    try:
        receiver.start();assert fenced.wait(2)
        cleanup.start()
        assert finish_interruption(channel)['stop']['reason']=='Native human takeover'
    finally:
        release.set();receiver.join(2)
        if cleanup.ident is not None:cleanup.join(2)
        channel.close();right.close()
    assert not receiver.is_alive() and not cleanup.is_alive() and not errors
    assert channel.stop_origin()['reason']=='Native human takeover'


def test_fragmented_receipt_keeps_exact_identity_and_arrival_clock():
    left,right=socket.socketpair();link=Link(left,fragment=True)
    channel=NativeChannel(link,'a'*32,123);result=[]
    try:
        before=time.time()
        thread=threading.Thread(target=lambda:result.append(channel.request('input',{},time.monotonic()+2,'b'*32)))
        thread.start()
        header,_=receive_packet(right)
        assert header['value']['id']=='b'*32
        right.sendall(encode_packet('receipt',native_receipt('b'*32)))
        thread.join(2)
        assert not thread.is_alive() and result[0][0]['id']=='b'*32
        timing=channel.timing('b'*32)
        assert before<=timing['receipt_received_wall']<=time.time()
        assert timing['send_started_monotonic']<=timing['receipt_received_monotonic']
        assert link.reads>10
        channel.release('b'*32)
    finally:
        channel.close();right.close()


def test_late_original_receipt_is_collectible_without_any_resubmission():
    left,right=socket.socketpair();channel=NativeChannel(left,'a'*32,123);result=[]
    try:
        thread=threading.Thread(target=lambda:result.append(channel.request('input',{},time.monotonic()+.1,'b'*32)))
        thread.start();header,_=receive_packet(right)
        thread.join(1)
        assert result[0][0]['disposition']=='unknown'
        pause,_=receive_packet(right)
        assert pause['value']['kind']=='pause'
        right.sendall(encode_packet('receipt',native_receipt(header['value']['id'])))
        end=time.monotonic()+1
        while channel.collect('b'*32) is None and time.monotonic()<end:time.sleep(.001)
        assert channel.collect('b'*32)[0]['disposition']=='delivered'
        assert channel.stopped.is_set()
        with pytest.raises(NoDispatch):channel.request('input',{},time.monotonic()+1,'c'*32)
    finally:
        channel.close();right.close()
