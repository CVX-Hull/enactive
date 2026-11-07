"""Incremental evaluation of the live run into its `live` store, about once a second.

This is the viewer's only write: the live run's own `live` evaluation store under the evaluation root. A
`final` store of the same versions is never touched, and the live run directory is only read. A pass that
fails is recorded in `status` and retried on the next tick; it never stops the viewer.
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from typing import Any

from harness.evaluation.core.pipeline import evaluate, existing_state
from harness.evaluation.core.records import EvaluationError, RecordWriter, record_path


class LiveEvaluator:
    def __init__(self, run_dir: Path, root: Path, binding: Any, interval: float = 1.0) -> None:
        self.run_dir, self.root, self.binding, self.interval = Path(run_dir), Path(root), binding, interval
        self.status: dict = dict(running=False, passes=0, error=None, last_pass_wall=None, last_seq=None, finished=False)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def session(self) -> str | None:
        try:
            value = json.loads((self.run_dir / 'manifest.json').read_text()).get('session')
        except (OSError, ValueError):
            return None
        return value if isinstance(value, str) else None

    def record(self) -> Path | None:
        session = self.session()
        return None if session is None else record_path(self.root, session, self.binding.binding_id, self.binding.binding_version)

    def step(self) -> None:
        """One pass: a full live pass the first time (or when the store cannot be continued), else incremental."""
        path = self.record()
        if path is None:
            raise EvaluationError(f'{self.run_dir}: no manifest with a session yet')
        state = existing_state(path)
        if state == 'final':
            self.status.update(finished=True, error=None)
            return
        if state == 'live':
            try:
                with RecordWriter.open(path) as writer:
                    last = writer.metadata().get('last_seq')
                evaluate(self.run_dir, self.binding, self.root, after_seq=last, state='live')
            except EvaluationError:
                evaluate(self.run_dir, self.binding, self.root, state='live', replace=True)
        else:
            evaluate(self.run_dir, self.binding, self.root, state='live', replace=True)
        with RecordWriter.open(path) as writer:
            self.status.update(last_seq=writer.metadata().get('last_seq'))

    def tick(self) -> None:
        try:
            self.step()
            self.status.update(error=None, passes=self.status['passes'] + 1, last_pass_wall=time.time())
        except Exception as exc:  # a failed pass is retried; the viewer keeps serving what is recorded
            self.status.update(error=f'{type(exc).__name__}: {exc}')

    def _run(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.interval)
        self.status.update(running=False)

    def start(self) -> None:
        self.status.update(running=True)
        self._thread = threading.Thread(target=self._run, name='live-evaluator', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
