"""Fixed prepared native launch and bounded waits for one owned child.

The mission writer serializes launch/wait calls. Process state is advisory: even
zero exit requires separate native readiness and ordinary save/menu evidence.
This adapter never adopts a PID, sends input/signals or repairs preparation.
"""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import time
from uuid import uuid4

from .prepared_app import wrapper_source


MAX_NATIVE_BYTES = 512 * 1024 * 1024
MAX_WRAPPER_BYTES = 16 * 1024
MAX_OPTIONS_BYTES = 1024 * 1024


class NativeProcessError(ValueError):
    """Invalid trusted-call arguments, preparation or owned-process operation."""


class _Deadline(Exception):
    pass


class NativeProcess:
    """Own only the child launched through this checkout's prepared wrapper."""

    def __init__(self, root: Path, native_sha256: str, *, clock: Callable[[], float] = time.monotonic):
        if (not isinstance(root, Path) or not callable(clock)
                or not isinstance(native_sha256, str) or len(native_sha256) != 64
                or any(char not in "0123456789abcdef" for char in native_sha256)):
            raise NativeProcessError("Expected trusted project Path, lowercase native SHA256 and clock")
        self._root = root.resolve()
        self._sha256 = native_sha256
        self._clock = clock
        self._last_clock: float | None = None
        self._child: subprocess.Popen | None = None
        self._launch_id: str | None = None

    def status(self) -> dict:
        """Poll only the retained handle; no disk, process scan or readiness check."""
        child = self._child
        code = child.poll() if child is not None else None
        return {"launch_id": self._launch_id, "pid": child.pid if child is not None else None,
            "running": child is not None and code is None, "returncode": code,
            "outcome": "not_launched" if child is None else "running" if code is None else "exited",
            "error": None}

    @staticmethod
    def _deadline(value: float) -> None:
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        except OverflowError:
            valid = False
        if not valid:
            raise NativeProcessError("Expected finite nonbool monotonic deadline")

    def _remaining(self, deadline: float) -> float:
        now = self._clock()
        self._deadline(now)
        if self._last_clock is not None and now < self._last_clock:
            raise NativeProcessError("Invalid or decreasing monotonic clock")
        self._last_clock = now
        remaining = deadline - now
        if remaining <= 0:
            raise _Deadline
        return remaining

    def _interrupted(self, outcome: str) -> dict:
        result = self.status()
        result.update(outcome=outcome, error="Original deadline expired" if outcome == "deadline" else "Wait cancelled")
        return result

    def _path(self, relative: str, *, directory: bool = False, optional: bool = False) -> Path:
        """Check each owned component without resolving away substitutions."""
        path = self._root
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise NativeProcessError("Prepared project root must remain a directory without symlink substitution")
        components = Path(relative).parts
        for index, component in enumerate(components):
            path = path / component
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                if optional and index == len(components) - 1:
                    return path
                raise
            if stat.S_ISLNK(mode):
                raise NativeProcessError(f"Prepared path contains symlink: {path}")
            is_directory = index < len(components) - 1 or directory
            if is_directory and not stat.S_ISDIR(mode):
                raise NativeProcessError(f"Prepared directory required: {path}")
            if not is_directory and not stat.S_ISREG(mode):
                raise NativeProcessError(f"Prepared regular file required: {path}")
        return path

    def _read(self, path: Path, ceiling: int, deadline: float) -> bytes:
        self._remaining(deadline)
        if path.stat().st_size > ceiling:
            raise NativeProcessError(f"Prepared {path.name} size exceeds limit")
        with path.open("rb") as stream:
            value = stream.read(ceiling + 1)
        self._remaining(deadline)
        if len(value) > ceiling:
            raise NativeProcessError(f"Prepared {path.name} size exceeds limit")
        return value

    @staticmethod
    def _executable(path: Path) -> None:
        if not path.stat().st_mode & 0o111 or not os.access(path, os.X_OK):
            raise NativeProcessError(f"Prepared file must be executable: {path}")

    @staticmethod
    def _option_object(pairs: list[tuple[str, object]]) -> dict:
        value = {}
        for key, item in pairs:
            if key in value:
                raise NativeProcessError("Duplicate options JSON key")
            value[key] = item
        return value

    def _validate_preparation(self, deadline: float) -> Path:
        wrapper = self._path(".runtime/Cataclysm.app/Contents/MacOS/Cataclysm.sh")
        native = self._path(".runtime/Cataclysm.app/Contents/Resources/cataclysm-tiles")
        options = self._path(".runtime/user/config/options.json")
        self._path(".runtime/bridge", directory=True)
        self._path(".runtime/logs", directory=True)
        self._path(".runtime/logs/game.log", optional=True)
        self._executable(wrapper)
        self._executable(native)
        try:
            script = self._read(wrapper, MAX_WRAPPER_BYTES, deadline).decode("utf-8")
        except UnicodeError as exc:
            raise NativeProcessError("Prepared wrapper must be UTF-8") from exc
        if script != wrapper_source(self._root):
            raise NativeProcessError("Prepared wrapper differs from this project's fixed wrapper")
        try:
            values = json.loads(self._read(options, MAX_OPTIONS_BYTES, deadline).decode("utf-8"),
                object_pairs_hook=self._option_object)
        except NativeProcessError:
            raise
        except (ValueError, RecursionError) as exc:
            raise NativeProcessError("Invalid prepared options JSON") from exc
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise NativeProcessError("Prepared options must be a list of objects")
        fullscreen = [item for item in values if item.get("name") == "FULLSCREEN"]
        if len(fullscreen) != 1 or fullscreen[0].get("value") != "no":
            raise NativeProcessError("Prepared options require exactly one FULLSCREEN=no")
        mouse = [item for item in values if item.get("name") == "ENABLE_MOUSE"]
        if len(mouse) != 1 or mouse[0].get("value") != "false":
            raise NativeProcessError("Prepared keyboard-driven options require exactly one ENABLE_MOUSE=false")
        if native.stat().st_size > MAX_NATIVE_BYTES:
            raise NativeProcessError("Prepared native size exceeds limit")
        digest = hashlib.sha256()
        size = 0
        with native.open("rb") as stream:
            while True:
                self._remaining(deadline)
                block = stream.read(min(1024 * 1024, MAX_NATIVE_BYTES - size + 1))
                self._remaining(deadline)
                if not block:
                    break
                size += len(block)
                if size > MAX_NATIVE_BYTES:
                    raise NativeProcessError("Prepared native size exceeds limit")
                digest.update(block)
        self._remaining(deadline)
        if digest.hexdigest() != self._sha256:
            raise NativeProcessError("Prepared native SHA256 differs from admission")
        return wrapper

    def _guard(self, deadline: float) -> None:
        timeout = min(1.0, self._remaining(deadline))
        try:
            result = subprocess.run(["/usr/bin/pgrep", "-x", "cataclysm-tiles"],
                capture_output=True, text=True, check=False, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
            raise NativeProcessError(f"Native process guard failed: {exc}") from exc
        if result.returncode != 1 or result.stdout != "" or result.stderr != "":
            raise NativeProcessError("Native process guard found an existing game or uncertain result")

    def launch(self, *, deadline_monotonic: float, cancelled: Callable[[], bool]) -> dict:
        """Validate fixed preparation, reject another game, then retain one child."""
        self._deadline(deadline_monotonic)
        if not callable(cancelled):
            raise NativeProcessError("cancelled must be a callable")
        if self.status()["running"]:
            raise NativeProcessError("Cannot launch with a live owned child")
        try:
            if cancelled():
                return self._interrupted("cancelled")
            self._remaining(deadline_monotonic)
            self._guard(deadline_monotonic)
            self._remaining(deadline_monotonic)
            if cancelled():
                return self._interrupted("cancelled")
            wrapper = self._validate_preparation(deadline_monotonic)
            if cancelled():
                return self._interrupted("cancelled")
            launch_id = uuid4().hex
            self._remaining(deadline_monotonic)
            child = subprocess.Popen([str(wrapper)], cwd=self._root,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Retain custody before any deadline check can return to the caller.
            self._child, self._launch_id = child, launch_id
            if cancelled():
                return self._interrupted("cancelled")
            self._remaining(deadline_monotonic)
        except _Deadline:
            return self._interrupted("deadline")
        except OSError as exc:
            raise NativeProcessError(f"Native launch preparation or exec failed: {exc}") from exc
        return self.status()

    def wait_exit(self, *, deadline_monotonic: float, cancelled: Callable[[], bool]) -> dict:
        """Wait only for the owned child; interruption preserves its handle."""
        self._deadline(deadline_monotonic)
        if not callable(cancelled):
            raise NativeProcessError("cancelled must be a callable")
        while True:
            state = self.status()
            if not state["running"]:
                return state
            if cancelled():
                return self._interrupted("cancelled")
            try:
                timeout = min(0.1, self._remaining(deadline_monotonic))
                try:
                    self._child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    pass
                self._remaining(deadline_monotonic)
            except _Deadline:
                return self._interrupted("deadline")
            except OSError as exc:
                raise NativeProcessError(f"Owned child wait failed: {exc}") from exc
