"""Prepare and execute bounded P1 handouts; candidate outputs require separate review.

A controller hard-kill or a child escaping its process group can evade cleanup.
This module cannot enforce a budget shared with other handouts or processes.
Image custody must stay immutable during CLI loading: pre/post hashes do not
prevent temporary replacement between checks or establish OS confinement.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from tools import p1_batches as batches
from tools import p1_codex_input as inputs


class HandoutError(ValueError):
    """A handout or attempt cannot be safely continued."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def metadata(prepared):
    return [dict(path=str(i.path), sha256=i.sha256, associations=[list(a) for a in i.associations])
            for i in prepared.images]


def source_receipt():
    return {str(Path(module.__file__).resolve()): digest(Path(module.__file__).read_bytes())
            for module in (inputs, batches, batches.analysis)}


def checked_receipt(prepared):
    return {key: value for key, value in prepared.check().items()
            if key not in ('prompt', 'exec_argv', 'render_argv')}


def prepare(kind, build, expected_key_sha256, out):
    out, build = Path(out).resolve(), Path(build).resolve()
    runtime = (batches.ROOT / '.runtime').resolve()
    if not out.is_relative_to(runtime) or out == runtime or out.exists():
        raise HandoutError('handout must be a fresh project runtime directory')
    if kind not in batches.KINDS:
        raise HandoutError('unknown kind')
    if digest((build / 'keys' / f'{kind}.json').read_bytes()) != expected_key_sha256:
        raise HandoutError('key digest mismatch')
    key = batches._load_key(build, kind)
    batches._verify_build(build, key, kind)
    out.mkdir(parents=True)
    (out / 'prompts').mkdir()
    (out / 'attempts').mkdir()
    (out / 'candidates').mkdir()
    records = {}
    for entry in key['batches']:
        name = entry['name']
        prepared = inputs.prepare(build, kind, name, out / name, expected_key_sha256=expected_key_sha256)
        receipt = checked_receipt(prepared)
        prompt_path = out / 'prompts' / f'{name}.txt'
        prompt_path.write_text(prepared.prompt, encoding='utf-8')
        records[name] = dict(batch_sha256=prepared.batch_sha256, prompt_sha256=digest(prepared.prompt.encode()),
                             images=metadata(prepared), receipt=receipt)
    write_json(out / 'manifest.json', dict(schema='p1-codex-handout/1', kind=kind, build=str(build),
                                           key_sha256=expected_key_sha256, source_files=source_receipt(), executor_sha256=digest(Path(__file__).read_bytes()),
                                           batches=records))
    return dict(batches=len(records), inference_calls=0)


def _reconstruct(out, manifest, name):
    kind, build, key_hash = manifest['kind'], Path(manifest['build']), manifest['key_sha256']
    record = manifest['batches'][name]
    runtime = (batches.ROOT / '.runtime').resolve()
    temporary = Path(tempfile.mkdtemp(prefix='p1-input-recheck-', dir=runtime))
    try:
        fresh = inputs.prepare(build, kind, name, temporary / name, expected_key_sha256=key_hash)
        leaf = out / name
        batch = leaf / f'{name}.json'
        expected_prompt = fresh.prompt.replace(str(fresh.batch), str(batch))
        prompt = (out / 'prompts' / f'{name}.txt').read_text(encoding='utf-8')
        if (prompt != expected_prompt or digest(prompt.encode()) != record['prompt_sha256']
                or fresh.batch_sha256 != record['batch_sha256'] or metadata(fresh) != record['images']
                or batch.read_bytes() != fresh.batch.read_bytes()):
            raise HandoutError('handout input differs from the verified build')
        prepared = replace(fresh, leaf=leaf, batch=batch, prompt=expected_prompt)
        receipt = checked_receipt(prepared)
        if json.loads(json.dumps(receipt)) != record['receipt']:
            raise HandoutError('local input receipt or CLI version changed')
        return prepared
    finally:
        shutil.rmtree(temporary)


def _ids(prepared):
    return [item['id'] for item in json.loads(prepared.batch.read_text())['items']]


def _candidate(out, name, prepared):
    directory = out / 'attempts' / name
    candidate = out / 'candidates' / f'{name}.jsonl'
    complete = directory / 'complete.json'
    if not directory.exists() and not candidate.exists():
        return False
    if (not complete.is_file() or not candidate.is_file()
            or any(not (directory / name).is_file() for name in ('stdout.jsonl', 'stderr.txt', 'launched.json'))):
        raise HandoutError('an attempt is incomplete and cannot be renewed')
    record = json.loads(complete.read_text())
    if (digest(candidate.read_bytes()) != record.get('candidate_sha256')
            or digest((directory / 'launched.json').read_bytes()) != record.get('launched_sha256')):
        raise HandoutError('candidate differs from its completion receipt')
    batches._answers(candidate, _ids(prepared), {}, prepared.kind)
    return True


def _cleanup(child):
    def send(sig):
        try:
            os.killpg(child.pid, sig)
            return True
        except ProcessLookupError:
            return False
    if send(signal.SIGTERM):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            child.poll()
            if not send(0):
                break
            time.sleep(0.05)
        send(signal.SIGKILL)
    child.wait(timeout=5)


def _unchanged(out, manifest, name, prepared, manifest_sha256, *, render=False):
    record = manifest['batches'][name]
    build = Path(manifest['build'])
    if (digest((out / 'manifest.json').read_bytes()) != manifest_sha256
            or manifest['source_files'] != source_receipt()
            or manifest['executor_sha256'] != digest(Path(__file__).read_bytes())
            or digest((build / 'keys' / f'{prepared.kind}.json').read_bytes()) != prepared.key_sha256
            or digest((build / 'batches' / f'{name}.json').read_bytes()) != prepared.batch_sha256
            or digest(prepared.batch.read_bytes()) != prepared.batch_sha256
            or (out / 'prompts' / f'{name}.txt').read_text() != prepared.prompt
            or any(digest(image.path.read_bytes()) != image.sha256 for image in prepared.images)):
        raise HandoutError('input changed during the pool')
    if render and json.loads(json.dumps(checked_receipt(prepared))) != record['receipt']:
        raise HandoutError('rendered input or CLI version changed during the pool')


def run(out, max_attempts, workers=1, only=None):
    out = Path(out).resolve()
    runtime = (batches.ROOT / '.runtime').resolve()
    if not out.is_relative_to(runtime) or out == runtime or max_attempts < 0 or workers not in (1, 2, 3):
        raise HandoutError('invalid handout or limits')
    with (out / '.run.lock').open('a') as lockfile:
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HandoutError('another controller owns the handout') from None
        if (out / 'stopped.json').exists():
            raise HandoutError('handout was stopped and cannot dispatch again')
        limits = out / 'run-limits.json'
        if limits.exists():
            if json.loads(limits.read_text()).get('max_attempts') != max_attempts:
                write_json(out / 'stopped.json', {'stopped': True})
                raise HandoutError('handout attempt limit cannot change')
        else:
            write_json(limits, {'max_attempts': max_attempts})
        try:
            return _run_locked(out, max_attempts, workers, only)
        except BaseException:
            if not (out / 'stopped.json').exists():
                write_json(out / 'stopped.json', {'stopped': True})
            raise


def _run_locked(out, max_attempts, workers, only):
    manifest = json.loads((out / 'manifest.json').read_text())
    manifest_sha256 = digest((out / 'manifest.json').read_bytes())
    if manifest.get('schema') != 'p1-codex-handout/1':
        raise HandoutError('unsupported handout')
    if manifest.get('source_files') != source_receipt():
        raise HandoutError('input source changed')
    if manifest.get('executor_sha256') != digest(Path(__file__).read_bytes()):
        raise HandoutError('executor source changed')
    names = list(manifest['batches'])
    if any(not isinstance(name, str) or Path(name).name != name for name in names):
        raise HandoutError('invalid batch names')
    if only is not None and (len(set(only)) != len(only) or not set(only) <= set(names)):
        raise HandoutError('unknown or duplicate batch selection')
    selected = names if only is None else [name for name in names if name in only]
    # Validate every reservation, including unselected ones, before any launch.
    reserved = {p.name for p in (out / 'attempts').iterdir()}
    if not reserved <= set(names):
        raise HandoutError('unknown attempt reservation')
    checked = {name: _reconstruct(out, manifest, name) for name in set(selected) | reserved}
    completed = {name for name in reserved if _candidate(out, name, checked[name])}
    if {p.stem for p in (out / 'candidates').iterdir()} != completed:
        raise HandoutError('candidate has no completed reservation')
    for name in selected:
        if name not in reserved and set(checked[name].leaf.iterdir()) != {checked[name].batch}:
            raise HandoutError('unused leaf contains unexpected files')
    lock, stop, active = threading.RLock(), threading.Event(), {}
    counts = dict(launched=len(reserved), done=0, skipped=len(completed & set(selected)), failed=0)

    def latch_stop():
        stop.set()
        marker = out / 'stopped.json'
        if not marker.exists():
            write_json(marker, {'stopped': True})

    def stop_all(latch=True):
        with lock:
            if latch:
                latch_stop()
            children = list(active.values())
        errors = []
        for child in children:
            try:
                _cleanup(child)
            except Exception as error:
                errors.append(type(error).__name__)
        if errors:
            raise HandoutError('owned process cleanup failed')

    def interrupted(signum, frame):
        stop_all()
        raise KeyboardInterrupt

    def task(name):
        if name in completed:
            return
        prepared = checked[name]
        directory = out / 'attempts' / name
        child = None
        failure_recorded = False
        try:
            _unchanged(out, manifest, name, prepared, manifest_sha256, render=True)
            with lock:
                if stop.is_set():
                    return
                if counts['launched'] >= max_attempts:
                    latch_stop()
                    return
                directory.mkdir()
                with (directory / 'stdout.jsonl').open('x') as stdout, (directory / 'stderr.txt').open('x') as stderr:
                    child = subprocess.Popen(prepared.exec_argv(), cwd=prepared.leaf, stdin=subprocess.PIPE,
                                             stdout=stdout, stderr=stderr, text=True, start_new_session=True)
                    active[child.pid] = child
                counts['launched'] += 1
                write_json(directory / 'launched.json', dict(pid=child.pid, started=time.time(),
                           manifest_sha256=digest((out / 'manifest.json').read_bytes()),
                           prompt_sha256=digest(prepared.prompt.encode()),
                           argv_sha256=digest(json.dumps(prepared.exec_argv()).encode())))
            try:
                child.communicate(prepared.prompt, timeout=900)
                if child.returncode != 0:
                    with lock:
                        latch_stop()
            except subprocess.TimeoutExpired:
                with lock:
                    latch_stop()
                raise HandoutError('attempt timed out') from None
            if child.returncode != 0:
                raise HandoutError('attempt failed')
            _cleanup(child)
            with lock:
                active.pop(child.pid, None)
            child = None
            _unchanged(out, manifest, name, prepared, manifest_sha256)
            answer = prepared.leaf / 'answer.jsonl'
            candidate = out / 'candidates' / f'{name}.jsonl'
            data = answer.read_bytes()
            with tempfile.NamedTemporaryFile(dir=out / 'candidates', prefix='.', delete=False) as stream:
                stream.write(data)
                staged = Path(stream.name)
            try:
                staged.chmod(0o400)
                batches._answers(staged, _ids(prepared), {}, prepared.kind)
                os.link(staged, candidate)  # Atomic, exclusive publication of the validated inode.
                write_json(directory / 'complete.json', dict(candidate_sha256=digest(data),
                           launched_sha256=digest((directory / 'launched.json').read_bytes())))
            finally:
                staged.unlink(missing_ok=True)
            with lock:
                counts['done'] += 1
        except BaseException:
            with lock:
                latch_stop()
                counts['failed'] += 1
                failure_recorded = True
        finally:
            if child is not None:
                try:
                    _cleanup(child)
                except BaseException:
                    with lock:
                        latch_stop()
                        if not failure_recorded:
                            counts['failed'] += 1
                else:
                    with lock:
                        active.pop(child.pid, None)

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(task, selected))
    finally:
        try:
            stop_all(latch=False)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return dict(**counts, stopped=stop.is_set())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('kind', choices=sorted(batches.KINDS))
    prep.add_argument('--batches', type=Path, required=True)
    prep.add_argument('--expected-key-sha256', required=True)
    prep.add_argument('--out', type=Path, required=True)
    execute = commands.add_parser('run')
    execute.add_argument('handout', type=Path)
    execute.add_argument('--max-attempts', type=int, required=True)
    execute.add_argument('--workers', type=int, choices=(1, 2, 3), default=1)
    execute.add_argument('--only', nargs='+')
    args = parser.parse_args(argv)
    try:
        result = (prepare(args.kind, args.batches, args.expected_key_sha256, args.out) if args.command == 'prepare'
                  else run(args.handout, args.max_attempts, args.workers, args.only))
    except (HandoutError, inputs.InputError, batches.BatchError, OSError, ValueError, KeyError):
        parser.exit(1, 'Handout verification or execution failed.\n')
    print(json.dumps(result))
    return int(result.get('stopped', False))


if __name__ == '__main__':
    raise SystemExit(main())
