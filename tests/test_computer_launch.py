"""Owned process cleanup and one-shot reservation; no game qualification."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from harness.computer.launch import OwnedTarget, close_group
from harness.computer.protocol import ControlError


def owner(path):
    path.mkdir()
    return OwnedTarget(path, 'a'*32, dict(argv=[sys.executable, '-c', 'pass'],
        cwd=str(path), env={}), path/'bridge.dylib', path.parent/'shared.lock', time.monotonic()+10)


def test_marker_precedes_launch_and_cannot_be_reopened(tmp_path):
    first=owner(tmp_path/'first')
    first.reserve()
    assert (first.directory/'started.json').is_file()
    assert not (first.directory/'session.sqlite3').exists()
    second=owner(tmp_path/'second')
    try:
        with pytest.raises(BlockingIOError):second.reserve()
        assert not (second.directory/'started.json').exists()
    finally:first.close();second.close()
    reopened=OwnedTarget(first.directory, 'b'*32, first.target, first.library,
        first.shared_lock, time.monotonic()+10)
    with pytest.raises(FileExistsError):reopened.reserve()
    assert reopened.process is None
    reopened.close()
    with pytest.raises(ControlError):first.reserve()


def test_prelaunch_failure_closes_socket_and_keeps_original_marker(tmp_path):
    selected=owner(tmp_path/'failed');selected.reserve()
    captured={}
    def fail(*args, **kwargs):
        captured.update(kwargs)
        # Actual inherited descriptors exist at the one launch boundary.
        assert all(os.fstat(fd) for fd in kwargs['pass_fds'])
        raise OSError('fixture launch failure')
    try:
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':'fixture-secret','UNRELATED_SECRET':'fixture-secret'}):
            with patch('harness.computer.launch.subprocess.Popen', side_effect=fail):
                with pytest.raises(OSError):selected.start()
        assert not any('SECRET' in key or 'API_KEY' in key for key in captured['env'])
        assert captured['start_new_session'] is True and len(captured['pass_fds'])==2
        with pytest.raises(OSError):os.fstat(captured['pass_fds'][1])
        with pytest.raises(ControlError):selected.start()
    finally:selected.close()
    assert (selected.directory/'started.json').is_file()
    with selected.shared_lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)


def test_normal_exit_is_distinct_from_forced_owned_cleanup(tmp_path):
    normal=subprocess.Popen([sys.executable,'-c','pass'],start_new_session=True)
    normal.wait(timeout=5)
    receipt=close_group(normal,native=True)
    assert receipt['normal_exit_zero_before_forced_signal'] and receipt['signals']==[]
    live=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
    try:
        receipt=close_group(live,native=True)
        assert receipt['process_absent'] and receipt['group_absent']
        assert receipt['signals'] and not receipt['normal_exit_zero_before_forced_signal']
    finally:
        if live.poll() is None:live.kill();live.wait(timeout=5)
