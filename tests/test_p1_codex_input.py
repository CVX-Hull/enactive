import base64
import hashlib
import json
import subprocess
from dataclasses import replace

import pytest

from tools import p1_batches as batches
from tools.coding_host import p1_input as inputs


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(batches, 'ROOT', tmp_path)
    monkeypatch.setattr(batches, 'frozen_brief', lambda label: f'{label} [batch]')
    root = tmp_path / '.runtime'
    root.mkdir()
    images = []
    for i in range(3):
        path = root / f'{i}.png'
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + bytes([i]))
        images.append(path)

    def make(kind, items):
        build = root / f'build-{kind}'
        entries = [dict(public=item, key={'synthetic': i}) for i, item in enumerate(items)]
        result = batches.write_batches(kind, build, [entries, entries[:1]], seed=None, host_version='test', inputs=[])
        return build, result['key_sha256']

    def prepare(kind, items):
        build, digest = make(kind, items)
        prepared = inputs.prepare(build, kind, f'{kind}-001', root / f'leaf-{kind}', expected_key_sha256=digest)
        return build, digest, prepared

    return root, images, make, prepare


def rendered(images):
    return {'content': [{'type': 'input_image', 'detail': 'high', 'image_url':
                         'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode()} for p in images]}


def test_question_attachments_and_private_files(setup):
    root, images, _, prepare = setup
    build, _, prepared = prepare('question', [{'frame': str(p)} for p in images])
    assert [i.path for i in prepared.images] == images
    assert set(prepared.leaf.iterdir()) == {prepared.batch}
    assert prepared.batch.read_bytes() == (build / 'batches' / 'question-001.json').read_bytes()
    assert str(prepared.batch) in prepared.prompt
    assert all(f'{n}: {path}' in prepared.prompt for n, path in enumerate(images, 1))
    argv = prepared.exec_argv()
    assert [argv[i + 1] for i, x in enumerate(argv) if x == '--image'] == list(map(str, images))
    assert argv[argv.index('-m') + 1] == 'gpt-6.1-sol'
    assert 'model_reasoning_effort=high' in argv and argv[-1] == '-'
    prepared.verify_render(rendered(images))
    with pytest.raises(inputs.InputError):
        prepared.verify_render(rendered(images[:-1]))


def test_question_attaches_each_item_even_when_frames_repeat(setup):
    _, images, _, prepare = setup
    _, _, prepared = prepare('question', [{'frame': str(images[0])}, {'frame': str(images[0])}])
    assert [i.path for i in prepared.images] == [images[0], images[0]]
    prepared.verify_render(rendered([images[0], images[0]]))


def test_audit_union_preserves_first_appearance_and_associations(setup):
    _, images, _, prepare = setup
    def frame(i):
        return dict(frame=str(images[i]), source=f's{i}', cited=True)
    _, _, prepared = prepare('audit', [{'frames': [frame(1), frame(0)]}, {'frames': [frame(0), frame(2)]}])
    assert [i.path for i in prepared.images] == [images[1], images[0], images[2]]
    assert len(prepared.images[1].associations) == 2
    prepared.verify_render(rendered([images[1], images[0], images[2]]))


def test_reader_has_no_images_even_if_text_contains_paths(setup):
    _, images, _, prepare = setup
    _, _, prepared = prepare('reader', [{'text': str(images[0])}])
    assert not prepared.images
    prepared.verify_render(rendered([]))
    with pytest.raises(inputs.InputError):
        prepared.verify_render(rendered(images[:1]))


def test_render_rejects_truncated_wrong_and_reordered_payloads(setup):
    _, images, _, prepare = setup
    _, _, prepared = prepare('question', [{'frame': str(p)} for p in images[:2]])
    broken = rendered(images[:2])
    broken['content'][0]['image_url'] = 'data:image/png;base64,iVBOR'
    for value in (broken, rendered([images[2], images[1]]), rendered([images[1], images[0]])):
        with pytest.raises(inputs.InputError):
            prepared.verify_render(value)


def test_changed_key_batch_and_existing_leaf_refused(setup):
    root, images, make, _ = setup
    build, digest = make('question', [{'frame': str(images[0])}])
    key = build / 'keys' / 'question.json'
    obj = json.loads(key.read_text())
    obj['host_version'] = 'changed'
    key.write_text(json.dumps(obj))
    with pytest.raises(inputs.InputError):
        inputs.prepare(build, 'question', 'question-001', root / 'bad-key', expected_key_sha256=digest)
    digest = hashlib.sha256(key.read_bytes()).hexdigest()
    batch = build / 'batches' / 'question-001.json'
    batch.write_text(batch.read_text() + ' ')
    with pytest.raises(batches.BatchError):
        inputs.prepare(build, 'question', 'question-001', root / 'bad-batch', expected_key_sha256=digest)
    (root / 'existing').mkdir()
    with pytest.raises(inputs.InputError):
        inputs.prepare(build, 'question', 'question-001', root / 'existing', expected_key_sha256=digest)
    assert not (root / 'bad-key').exists() and not (root / 'bad-batch').exists()


def test_local_check_only_runs_version_and_debug_and_records_version(setup, monkeypatch):
    _, images, _, prepare = setup
    _, digest, prepared = prepare('question', [{'frame': str(images[0])}])
    calls = []
    def fake(argv, **kwargs):
        calls.append((argv, kwargs))
        out = 'codex synthetic-version\n' if argv == ['codex', '--version'] else json.dumps(rendered(images[:1]))
        return subprocess.CompletedProcess(argv, 0, out, '')
    monkeypatch.setattr(inputs.subprocess, 'run', fake)
    receipt = prepared.check()
    assert receipt['cli_version'] == 'codex synthetic-version' and receipt['key_sha256'] == digest
    assert len(calls) == 2 and calls[1][0][:3] == ['codex', 'debug', 'prompt-input']
    assert all(call[1]['cwd'] == prepared.leaf and call[1]['timeout'] == 30 for call in calls)
    assert receipt['image_count'] == 1 and receipt['inference_calls'] == 0
    assert receipt['exec_argv_sha256'] == hashlib.sha256(json.dumps(prepared.exec_argv()).encode()).hexdigest()
    assert set(receipt['source_files']) == {'tools/coding_host/p1_input.py', 'tools/p1_batches.py', 'tools/p1_analysis.py'}
    assert 'prompt' not in receipt and 'render_argv' not in receipt
    with pytest.raises(inputs.InputError):
        replace(prepared, images=()).check()


def test_role_image_policy_cannot_be_bypassed_by_constructing_a_prepared_input(setup):
    _, images, _, prepare = setup
    _, _, visual = prepare('question', [{'frame': str(images[0])}])
    _, _, textual = prepare('reader', [{'text': 'synthetic fixture'}])
    with pytest.raises(inputs.InputError):
        replace(visual, images=())
    with pytest.raises(inputs.InputError):
        replace(textual, images=visual.images)


@pytest.mark.parametrize('name,content', [('missing.png', None), ('bad.png', b'not png'), ('bad.jpg', b'\x89PNG\r\n\x1a\n')])
def test_invalid_image_source_is_rejected(setup, name, content):
    root, _, make, _ = setup
    path = root / name
    if content is not None:
        path.write_bytes(content)
    build, digest = make('question', [{'frame': str(path)}])
    with pytest.raises(inputs.InputError):
        inputs.prepare(build, 'question', 'question-001', root / 'invalid-leaf', expected_key_sha256=digest)
    assert not (root / 'invalid-leaf').exists()
