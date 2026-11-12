import hashlib
import json
import subprocess
from pathlib import Path
import threading
import time

import pytest

from tools import p1_batches as batches
from tools.coding_host import p1 as runner
from tools.coding_host import p1_input as inputs


@pytest.fixture
def handout(tmp_path, monkeypatch):
    monkeypatch.setattr(batches, 'ROOT', tmp_path)
    monkeypatch.setattr(batches, 'frozen_brief', lambda label: f'{label} [batch]')
    runtime = tmp_path / '.runtime'
    runtime.mkdir()
    image = runtime / 'frame.png'
    image.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')
    build = runtime / 'build'
    entries = [dict(public={'frame': str(image)}, key={'synthetic': n}) for n in range(3)]
    info = batches.write_batches('question', build, [[entry] for entry in entries], seed=None,
                                 host_version='test', inputs=[])
    version = ['version-one']
    def check(self, timeout=30):
        assert hashlib.sha256(self.batch.read_bytes()).hexdigest() == self.batch_sha256
        for img in self.images:
            assert hashlib.sha256(img.path.read_bytes()).hexdigest() == img.sha256
        return {'cli_version': version[0], 'batch_sha256': self.batch_sha256,
                'prompt_sha256': hashlib.sha256(self.prompt.encode()).hexdigest()}
    monkeypatch.setattr(inputs.PreparedInput, 'check', check)
    out = runtime / 'handout'
    runner.prepare('question', build, info['key_sha256'], out)
    return out, build, image, version


class Child:
    counter = 100
    def __init__(self, argv, **kwargs):
        self.argv, self.cwd = argv, kwargs['cwd']
        Child.counter += 1
        self.pid = Child.counter
        self.returncode = 0
    def communicate(self, prompt, timeout):
        assert timeout == 900
        self.prompt = prompt
        batch = next(self.cwd.glob('question-*.json'))
        item = json.loads(batch.read_text())['items'][0]
        (self.cwd / 'answer.jsonl').write_text(json.dumps({'id': item['id'], 'key': 'x', 'question': 'x'}) + '\n')
    def poll(self):
        return self.returncode
    def wait(self, timeout):
        return self.returncode


def fakes(monkeypatch, child=Child):
    calls = []
    def launch(argv, **kwargs):
        instance = child(argv, **kwargs)
        calls.append(instance)
        return instance
    monkeypatch.setattr(runner.subprocess, 'Popen', launch)
    monkeypatch.setattr(runner, '_cleanup', lambda child: None)
    return calls


def test_success_sends_exact_prepared_images_and_keeps_candidates_separate(handout, monkeypatch):
    out, _, image, _ = handout
    calls = fakes(monkeypatch)
    result = runner.run(out, 1, only=['question-001'])
    assert result == dict(launched=1, done=1, skipped=0, failed=0, stopped=False)
    assert len(calls) == 1 and calls[0].argv[calls[0].argv.index('--image') + 1] == str(image)
    assert calls[0].prompt == (out / 'prompts/question-001.txt').read_text()
    assert calls[0].argv[-1] == '-' and (out / 'candidates/question-001.jsonl').is_file()
    assert calls[0].argv[calls[0].argv.index('-m') + 1] == 'gpt-6.1-sol'
    assert 'model_reasoning_effort=high' in calls[0].argv
    assert (out / 'attempts/question-001/stdout.jsonl').exists()
    assert (out / 'attempts/question-001/stderr.txt').exists()
    assert runner.run(out, 1, only=['question-001'])['skipped'] == 1
    assert len(calls) == 1


@pytest.mark.parametrize('mutation', ['image', 'batch', 'key', 'prompt', 'version', 'source'])
def test_mutation_blocks_all_launches(handout, monkeypatch, mutation):
    out, build, image, version = handout
    calls = fakes(monkeypatch)
    if mutation == 'image':
        image.unlink()
    elif mutation == 'batch':
        (out / 'question-001/question-001.json').write_text('{}')
    elif mutation == 'key':
        key = build / 'keys/question.json'
        key.write_text(key.read_text() + ' ')
    elif mutation == 'prompt':
        (out / 'prompts/question-001.txt').write_text('changed')
    elif mutation == 'version':
        version[0] = 'version-two'
    else:
        manifest = out / 'manifest.json'
        data = json.loads(manifest.read_text())
        data['executor_sha256'] = 'changed'
        manifest.write_text(json.dumps(data))
    with pytest.raises((runner.HandoutError, inputs.InputError, batches.BatchError, OSError)):
        runner.run(out, 3)
    assert calls == []


def test_partial_or_wrong_output_stops_and_cannot_resume(handout, monkeypatch):
    out, _, _, _ = handout
    class Wrong(Child):
        def communicate(self, prompt, timeout):
            (self.cwd / 'answer.jsonl').write_text('{}\n')
    calls = fakes(monkeypatch, Wrong)
    result = runner.run(out, 3, workers=1)
    assert result['stopped'] and result['failed'] == 1 and len(calls) == 1
    with pytest.raises(runner.HandoutError):
        runner.run(out, 3)
    assert len(calls) == 1


def test_reservation_without_completion_is_never_renewed(handout, monkeypatch):
    out, _, _, _ = handout
    calls = fakes(monkeypatch)
    (out / 'attempts/question-001').mkdir()
    with pytest.raises(runner.HandoutError):
        runner.run(out, 3, only=['question-002'])
    assert calls == []


def test_budget_and_concurrency_limit(handout, monkeypatch):
    out, _, _, _ = handout
    guard = threading.Lock()
    state = {'active': 0, 'peak': 0}
    class Slow(Child):
        def communicate(self, prompt, timeout):
            with guard:
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
            time.sleep(0.05)
            super().communicate(prompt, timeout)
            with guard:
                state['active'] -= 1
    calls = fakes(monkeypatch, Slow)
    result = runner.run(out, 2, workers=2)
    assert len(calls) == 2 and state['peak'] <= 2
    assert result['done'] == 2 and result['stopped']
    with pytest.raises(runner.HandoutError):
        runner.run(out, 2, only=['question-001'])


def test_nonzero_blocks_queued_launch(handout, monkeypatch):
    out, _, _, _ = handout
    class Failed(Child):
        def communicate(self, prompt, timeout):
            self.returncode = 1
    calls = fakes(monkeypatch, Failed)
    result = runner.run(out, 3, workers=1)
    assert result['stopped'] and result['failed'] == 1 and len(calls) == 1


def test_timeout_latches_and_cleans_up_before_return(handout, monkeypatch):
    out, _, _, _ = handout
    class TimedOut(Child):
        def communicate(self, prompt, timeout):
            raise subprocess.TimeoutExpired(self.argv, timeout)
    calls = fakes(monkeypatch, TimedOut)
    cleaned = []
    monkeypatch.setattr(runner, '_cleanup', lambda child: cleaned.append(child.pid))
    result = runner.run(out, 3)
    assert result['stopped'] and result['failed'] == 1 and len(calls) == 1
    assert cleaned == [calls[0].pid]
    with pytest.raises(runner.HandoutError):
        runner.run(out, 3)


def test_cleanup_kills_stubborn_owned_process_group():
    import os
    import signal
    import sys

    script = ('import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
              'print("ready", flush=True); time.sleep(60)')
    child = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, text=True,
                             start_new_session=True)
    try:
        assert child.stdout.readline().strip() == 'ready'
        runner._cleanup(child)
        assert child.returncode == -signal.SIGKILL
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
        child.stdout.close()


def test_limit_is_fixed_across_healthy_partial_runs(handout, monkeypatch):
    out, _, _, _ = handout
    calls = fakes(monkeypatch)
    assert not runner.run(out, 3, only=['question-001'])['stopped']
    with pytest.raises(runner.HandoutError):
        runner.run(out, 4, only=['question-002'])
    assert len(calls) == 1
    with pytest.raises(runner.HandoutError):
        runner.run(out, 3, only=['question-002'])


def test_changed_shared_image_stops_queued_launches_and_publication(handout, monkeypatch):
    out, _, image, _ = handout
    class Changed(Child):
        def communicate(self, prompt, timeout):
            super().communicate(prompt, timeout)
            image.write_bytes(image.read_bytes() + b'changed')
    calls = fakes(monkeypatch, Changed)
    result = runner.run(out, 3, workers=1)
    assert len(calls) == 1 and result['stopped'] and not result['done']
    assert not list((out / 'candidates').iterdir())


def test_published_bytes_are_the_snapshot_that_was_validated(handout, monkeypatch):
    out, _, _, _ = handout
    fakes(monkeypatch)
    original = batches._answers
    validated = []
    def validate(path, *args):
        result = original(path, *args)
        validated.append(Path(path).read_bytes())
        (out / 'question-001/answer.jsonl').write_text('{}\n')
        return result
    monkeypatch.setattr(batches, '_answers', validate)
    result = runner.run(out, 3, only=['question-001'])
    assert not result['stopped'] and result['done'] == 1
    assert (out / 'candidates/question-001.jsonl').read_bytes() == validated[0]
    assert not list((out / 'candidates').glob('.*'))


def test_cleanup_failure_cannot_publish_completion(handout, monkeypatch):
    out, _, _, _ = handout
    calls = fakes(monkeypatch)
    def failed_cleanup(child):
        raise RuntimeError('synthetic cleanup failure')
    monkeypatch.setattr(runner, '_cleanup', failed_cleanup)
    with pytest.raises(runner.HandoutError, match='cleanup'):
        runner.run(out, 3, workers=1)
    assert len(calls) == 1 and (out / 'stopped.json').exists()
    assert not list((out / 'candidates').iterdir())
    assert not list((out / 'attempts').glob('*/complete.json'))


def test_controller_sigterm_closes_an_active_owned_group(handout):
    import os
    import signal
    import sys
    import textwrap

    out, _, _, _ = handout
    marker = out / 'fixture-pids.json'
    script = textwrap.dedent('''
        import hashlib,json,subprocess,sys
        from pathlib import Path
        from tools import p1_batches as b
        from tools.coding_host import p1 as r,p1_input as i
        out,marker=map(Path,sys.argv[1:])
        b.ROOT=out.parent.parent
        b.frozen_brief=lambda label: f'{label} [batch]'
        def check(self,timeout=30):
            return {'cli_version':'version-one','batch_sha256':self.batch_sha256,
                    'prompt_sha256':hashlib.sha256(self.prompt.encode()).hexdigest()}
        i.PreparedInput.check=check
        grand='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(120)'
        fake=('import json,os,subprocess,sys,time; from pathlib import Path; '
              'sys.stdin.read(); p=subprocess.Popen([sys.executable,"-u","-c",'+repr(grand)+'],stdout=subprocess.PIPE,text=True); '
              'assert p.stdout.readline().strip()=="ready"; '
              'Path('+repr(str(marker))+').write_text(json.dumps([os.getpid(),p.pid])); time.sleep(120)')
        i.PreparedInput.exec_argv=lambda self:[sys.executable,'-u','-c',fake]
        try:r.run(out,3,only=['question-001'])
        except KeyboardInterrupt:pass
    ''')
    controller = subprocess.Popen([sys.executable, '-c', script, str(out), str(marker)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  start_new_session=True)
    owned = []
    try:
        deadline = time.monotonic() + 15
        while not marker.exists() and controller.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), 'owned fixture did not start'
        owned = json.loads(marker.read_text())
        controller.send_signal(signal.SIGTERM)
        stdout, stderr = controller.communicate(timeout=20)
        assert controller.returncode == 0, (stdout, stderr)
        assert (out / 'stopped.json').is_file()
        assert not list((out / 'candidates').iterdir())
        for pid in owned:
            state = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
            assert not state or state.startswith('Z')
    finally:
        if owned:
            try:
                os.killpg(owned[0], signal.SIGKILL)
            except ProcessLookupError:
                pass
        if controller.poll() is None:
            os.killpg(controller.pid, signal.SIGKILL)
            controller.communicate(timeout=5)
        controller.stdout.close()
        controller.stderr.close()
