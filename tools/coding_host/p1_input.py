"""Prepare and locally verify the inputs to one P1 Codex session; never run a model."""

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess

from tools import p1_batches as batches


class InputError(ValueError):
    """The prepared input or its local rendering cannot be verified."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ImageInput:
    path: Path
    sha256: str
    # (item id, source id, cited); the batch remains authoritative for ordering.
    associations: tuple[tuple[str, str | None, bool | None], ...]


@dataclass(frozen=True)
class PreparedInput:
    kind: str
    leaf: Path
    batch: Path
    prompt: str
    images: tuple[ImageInput, ...]
    key_sha256: str
    batch_sha256: str

    def __post_init__(self) -> None:
        if self.kind not in batches.KINDS or bool(self.images) != (self.kind in ('question', 'audit')):
            raise InputError('image inputs do not match this role')

    def _images_argv(self) -> list[str]:
        return [part for image in self.images for part in ('--image', str(image.path))]

    def exec_argv(self) -> list[str]:
        return ['codex', 'exec', '--ephemeral', '--skip-git-repo-check', '--json', '-s', 'workspace-write',
                '-C', str(self.leaf), '-m', 'gpt-6.1-sol', '-c', 'model_reasoning_effort=high',
                *self._images_argv(), '-']

    def render_argv(self) -> list[str]:
        return ['codex', 'debug', 'prompt-input', '-c', 'model="gpt-6.1-sol"',
                '-c', 'model_reasoning_effort="high"', '-c', 'sandbox_mode="workspace-write"',
                *self._images_argv(), '--', self.prompt]

    def verify_render(self, rendered: object) -> None:
        found = []
        user_text = []
        user_types = []

        def visit(value: object) -> None:
            if isinstance(value, dict):
                if value.get('type') == 'message' and value.get('role') == 'user':
                    blocks = value.get('content')
                    if not isinstance(blocks, list) or any(not isinstance(block, dict) for block in blocks):
                        raise InputError('invalid rendered user content')
                    user_types.append([block.get('type') for block in blocks])
                    user_text.append([block.get('text') for block in blocks if block.get('type') == 'input_text'])
                if value.get('type') == 'input_image':
                    found.append(value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(rendered)
        expected_text = []
        for index, image in enumerate(self.images, 1):
            expected_text.extend([f'<image name=[Image #{index}] path="{image.path}">', '</image>'])
        expected_text.append(self.prompt)
        expected_types = ['input_text', 'input_image', 'input_text'] * len(self.images) + ['input_text']
        if not user_text or user_text[-1] != expected_text or user_types[-1] != expected_types:
            raise InputError('rendered user text differs from prepared prompt')
        if len(found) != len(self.images):
            raise InputError('rendered image count differs from prepared input')
        for block, expected in zip(found, self.images):
            url = block.get('image_url')
            if block.get('detail') not in ('auto', 'high') or not isinstance(url, str) or not url.startswith('data:image/png;base64,'):
                raise InputError('invalid rendered PNG image block')
            try:
                payload = base64.b64decode(url.removeprefix('data:image/png;base64,'), validate=True)
            except (binascii.Error, ValueError):
                raise InputError('invalid rendered PNG encoding') from None
            if _sha(payload) != expected.sha256:
                raise InputError('rendered PNG payload differs from prepared input')

    def check(self, timeout: float = 30) -> dict:
        """Run only the local CLI version and debug renderer, returning a receipt."""
        try:
            for image in self.images:
                if _sha(image.path.read_bytes()) != image.sha256:
                    raise InputError('source PNG changed after preparation')
            if _sha(self.batch.read_bytes()) != self.batch_sha256:
                raise InputError('copied batch changed after preparation')
            version = subprocess.run(['codex', '--version'], cwd=self.leaf, capture_output=True, text=True,
                                     check=True, timeout=timeout).stdout.strip()
            rendered = subprocess.run(self.render_argv(), cwd=self.leaf, capture_output=True, text=True,
                                      check=True, timeout=timeout).stdout
            self.verify_render(json.loads(rendered))
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            if isinstance(exc, InputError):
                raise
            raise InputError('local Codex input check failed') from None
        if not version:
            raise InputError('local Codex version is empty')
        return dict(kind=self.kind, leaf=str(self.leaf), batch=str(self.batch), image_count=len(self.images),
                    images=[dict(path=str(i.path), sha256=i.sha256, associations=i.associations) for i in self.images],
                    key_sha256=self.key_sha256, batch_sha256=self.batch_sha256,
                    prompt_sha256=_sha(self.prompt.encode()),
                    exec_argv_sha256=_sha(json.dumps(self.exec_argv()).encode()),
                    source_files={name: _sha(path.read_bytes()) for name, path in
                                  (('tools/coding_host/p1_input.py', Path(__file__)),
                                   ('tools/p1_batches.py', Path(batches.__file__)),
                                   ('tools/p1_analysis.py', Path(batches.analysis.__file__)))},
                    cli_version=version, inference_calls=0)


def prepare(build: Path, kind: str, batch_name: str, leaf: Path, *, expected_key_sha256: str) -> PreparedInput:
    if kind not in batches.KINDS:
        raise InputError('unknown batch kind')
    build, leaf = Path(build), Path(leaf).resolve()
    if not leaf.is_relative_to((batches.ROOT / '.runtime').resolve()) or leaf == (batches.ROOT / '.runtime').resolve():
        raise InputError('leaf must be under project .runtime')
    if leaf.exists():
        raise InputError('leaf already exists')
    try:
        key_hash = _sha((build / 'keys' / f'{kind}.json').read_bytes())
    except OSError:
        raise InputError('key cannot be read') from None
    if key_hash != expected_key_sha256:
        raise InputError('key differs from the expected digest')
    key = batches._load_key(build, kind)
    batches._verify_build(build, key, kind)
    if batch_name not in key['batch_files']:
        raise InputError('batch is not in the verified build')
    source = build / 'batches' / f'{batch_name}.json'
    try:
        raw = source.read_bytes()
        batch = json.loads(raw)
        brief = batches.frozen_brief(batches.KINDS[kind]['brief'])
        entry = next(b for b in key['batches'] if b['name'] == batch_name)
        if (batch['schema'] != batches.BATCH_SCHEMA or batch['brief'] != brief
                or (kind == 'reader' and len(batch['items']) != 1)
                or [item['id'] for item in batch['items']] != entry['ids']
                or any(item['id'] not in key['items'] for item in batch['items'])):
            raise InputError('batch content does not match its key or frozen brief')
        paths = []
        audit_indexes = {}
        for item in batch['items']:
            frames = ([{'frame': item['frame']}] if kind == 'question' else
                      item['frames'] if kind == 'audit' else [])
            for frame in frames:
                path = Path(frame['frame'])
                if not path.is_absolute() or path.suffix.lower() != '.png':
                    raise InputError('image source must be an absolute PNG path')
                path = path.resolve()
                payload = path.read_bytes()
                if not payload.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise InputError('image source is not a PNG')
                association = (item['id'], frame.get('source'), frame.get('cited'))
                if kind == 'audit' and path in audit_indexes:
                    paths[audit_indexes[path]][2].append(association)
                else:
                    audit_indexes[path] = len(paths)
                    paths.append((path, _sha(payload), [association]))
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError('batch or image source cannot be prepared') from None
    images = tuple(ImageInput(path, digest, tuple(associations)) for path, digest, associations in paths)
    leaf.mkdir(parents=True, exist_ok=False)
    copied = leaf / f'{batch_name}.json'
    copied.write_bytes(raw)
    prompt = brief if kind == 'reader' else brief.replace('[batch]', str(copied))
    prompt += f'\n\nRead the batch file at {copied}. '
    if images:
        prompt += ('Use the attached original images in attachment order; '
                   'the batch remains authoritative for each item and its frame order. ')
    prompt += ('Codex host mechanics permit only local file operations needed to read this named batch '
               + ('and view its named images, ' if images else '')
               + 'and write the named answer file. Do not read other files, run other commands, '
               'use the network or spawn agents. '
               'Write your answers as JSON Lines to answer.jsonl in the current directory. '
               'Then reply with only the number of lines you wrote.')
    prompt += '\n\nExact public batch JSON follows:\n' + raw.decode('utf-8')
    return PreparedInput(kind, leaf, copied, prompt, images, key_hash, _sha(raw))
