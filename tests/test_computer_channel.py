"""Actual local sockets plus one injected partial-send fault; no native/game proof."""
import socket
import struct
import threading
import time

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
