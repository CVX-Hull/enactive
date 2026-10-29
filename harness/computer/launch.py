"""Exact owned target/process groups and inherited mechanical descriptors."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import time
from typing import Any

from .channel import NativeChannel
from .protocol import ControlError, canonical


def group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid,0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Signal zero may be denied for an existing group. It cannot prove
        # absence; retain the group and let exact cleanup report any denial.
        return True


def close_group(child: subprocess.Popen, *, native: bool = False) -> dict[str, Any]:
    """Close only the process group created with this exact Popen handle."""
    signals=[]
    before=child.poll()
    if native and before is None:
        try:
            child.wait(timeout=1.)
        except subprocess.TimeoutExpired:
            pass
    normal_before_signal=child.poll()==0
    sequence=((signal.SIGTERM,2.),(signal.SIGKILL,2.)) if native else (
        (signal.SIGINT,3.),(signal.SIGTERM,2.),(signal.SIGKILL,2.))
    for sig,seconds in sequence:
        if not group_alive(child.pid):
            break
        try:
            os.killpg(child.pid,sig)
            signals.append(sig.name)
        except ProcessLookupError:
            break
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            child.poll()
            if not group_alive(child.pid):
                break
            time.sleep(.02)
    try:
        child.wait(timeout=.2)
    except subprocess.TimeoutExpired:
        pass
    return dict(pid=child.pid,pgid=child.pid,returncode=child.poll(),signals=signals,
                normal_exit_zero_before_forced_signal=normal_before_signal,
                process_absent=child.poll() is not None,group_absent=not group_alive(child.pid))


class OwnedTarget:
    """Reserve once, then launch once; no adoption from existing files or PIDs."""
    def __init__(self, directory: Path, session: str, target: dict[str, Any], library: Path,
                 shared_lock: Path, deadline: float) -> None:
        self.directory,self.session,self.target=directory,session,target
        self.library,self.shared_lock,self.deadline=library,shared_lock,deadline
        self.lock=None
        self.process: subprocess.Popen | None=None
        self.channel: NativeChannel | None=None
        self.console=None
        self._reserved=False
        self._started=False
        self._closed=False
        self.receipt=None

    def reserve(self) -> None:
        if self._reserved or self._started or self._closed:
            raise ControlError('Owned launch is one-shot')
        self.shared_lock.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(self.shared_lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        self.lock=os.fdopen(fd,'a')
        try:
            if not stat.S_ISREG(os.fstat(self.lock.fileno()).st_mode):
                raise ControlError('Shared lock must be a regular file')
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            # The marker survives even a failure before any session DB exists.
            with (self.directory/'started.json').open('x') as stream:
                stream.write(canonical(dict(schema='computer-start/1',session=self.session,
                    started_wall=time.time(),deadline_monotonic=self.deadline))+'\n')
            self._reserved=True
        except BaseException:
            self.lock.close();self.lock=None
            raise

    def start(self) -> NativeChannel:
        if not self._reserved or self._started or self._closed:
            raise ControlError('Only this reserved fresh owner may launch')
        if time.monotonic()>=self.deadline:
            raise ControlError('Original deadline exhausted before launch')
        self._started=True
        parent,child=socket.socketpair()
        base=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),LANG='en_US.UTF-8')
        base.update(self.target['env'])
        env=dict(base,ENACTIVE_COMPUTER_LIBRARY=str(self.library),DYLD_INSERT_LIBRARIES=str(self.library),
            ENACTIVE_COMPUTER_FD=str(child.fileno()),ENACTIVE_COMPUTER_SESSION=self.session,
            ENACTIVE_COMPUTER_LOCK_FD=str(self.lock.fileno()),ENACTIVE_COMPUTER_LOCK_FILE=str(self.shared_lock))
        try:
            self.console=(self.directory/'native-console.log').open('x')
            self.process=subprocess.Popen(self.target['argv'],cwd=self.target['cwd'],env=env,
                stdin=subprocess.DEVNULL,stdout=self.console,stderr=self.console,
                pass_fds=(self.lock.fileno(),child.fileno()),start_new_session=True)
            self.channel=NativeChannel(parent,self.session,self.process.pid)
            with (self.directory/'native-process.json').open('x') as stream:
                stream.write(canonical(dict(schema='computer-process/1',pid=self.process.pid,pgid=self.process.pid,
                    session=self.session,argv=self.target['argv'],cwd=self.target['cwd'],
                    environment=env,provider_credentials_inherited=False))+'\n')
            return self.channel
        except BaseException:
            if self.channel is None:
                parent.close()
            raise
        finally:
            child.close()

    def wait_target(self) -> None:
        if self.channel is None or self.process is None:
            raise ControlError('Owned target has not started')
        end=min(self.deadline,time.monotonic()+60)
        while time.monotonic()<end:
            if self.process.poll() is not None or self.channel.stopped.is_set() or self.channel.fault:
                raise ControlError('Owned native launch exited or refused control')
            target=self.channel.target()
            if target and target['window_id']>0:
                return
            time.sleep(.02)
        raise ControlError('Owned mechanical target did not establish within original launch bound')

    def close(self) -> dict[str, Any]:
        if self._closed:
            return self.receipt
        self._closed=True
        result=dict(schema='computer-cleanup/1',session=self.session,
                    native_absence_verified=self.process is None,normal_native_exit_zero=False)
        try:
            if self.channel is not None:
                try:
                    self.channel.close()
                except Exception as exc:
                    result['channel_cleanup_error']=type(exc).__name__
            if self.process is not None:
                cleanup=close_group(self.process,native=True)
                result['native']=cleanup
                result['native_absence_verified']=cleanup['process_absent'] and cleanup['group_absent']
                result['normal_native_exit_zero']=cleanup['normal_exit_zero_before_forced_signal']
        finally:
            if self.console is not None:
                self.console.close()
            if self.lock is not None:
                # Close this reference, never unlock the child's shared lock.
                self.lock.close()
            self.receipt=result
        return result
