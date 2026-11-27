"""The curator's knowledge repository: one Git repository per game (ADR 009's
one-repository-per-game direction; #453).

Only the gate commits (see `gate.py`). A publish is one commit on `main` and one tag `v<N>`;
the highest tag is the published version, so a commit that fails before its tag leaves the
published version unchanged. Nothing here runs anything the repository contains.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import BinaryIO

SCHEMA = 'curator-knowledge/5'
BRANCH = 'main'
IDENTITY = ('-c', 'user.name=enactive-gate', '-c', 'user.email=gate@localhost',
            '-c', 'commit.gpgsign=false', '-c', 'tag.gpgsign=false', '-c', 'core.hooksPath=/dev/null')
_VERSION = re.compile(r'v(0|[1-9][0-9]*)')
_OID = re.compile(rb'(?:[0-9a-f]{40}|[0-9a-f]{64})')
_SCHEMA_ERROR = f'unsupported knowledge schema: expected {SCHEMA}; start a new repository'


class KnowledgeError(ValueError):
    """The repository could not be read or published."""


def _environment() -> dict[str, str]:
    # An inherited GIT_DIR, GIT_INDEX_FILE or GIT_WORK_TREE (from a hook running the suite, for
    # example) would point every command, rollback's clean included, at another repository.
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    environment['GIT_CONFIG_GLOBAL'] = '/dev/null'
    environment['GIT_CONFIG_SYSTEM'] = '/dev/null'
    environment['GIT_TERMINAL_PROMPT'] = '0'
    environment['GIT_NO_REPLACE_OBJECTS'] = '1'
    return environment


def _git(cwd: Path, *args: str) -> bytes:
    try:
        done = subprocess.run(['git', *IDENTITY, *args], cwd=cwd, env=_environment(),
                              capture_output=True, check=False)
    except OSError as error:
        raise KnowledgeError(f'git {args[0]} could not run: {error}') from error
    if done.returncode != 0:
        detail = done.stderr.decode('utf-8', 'replace').strip()
        raise KnowledgeError(f'git {args[0]} failed ({done.returncode}): {detail}')
    return done.stdout


def _number(version: str) -> int:
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise KnowledgeError(f'not a version: {version!r}')
    return int(version[1:])


def _safe(relative: str) -> PurePosixPath:
    path = PurePosixPath(relative)
    if (not relative or path.is_absolute() or '\\' in relative
            or any(part in ('', '.', '..', '.git') for part in path.parts)):
        raise KnowledgeError(f'unsafe repository path: {relative!r}')
    return path


class _GitObjects:
    """Read raw objects from one Git process, checking the hash of each distinct object."""

    def __init__(self, requests: BinaryIO, responses: BinaryIO):
        self.requests, self.responses = requests, responses
        self.objects: dict[bytes, tuple[bytes, bytes]] = {}

    def _read(self, oid: bytes) -> tuple[bytes, bytes]:
        self.requests.write(oid + b'\n')
        self.requests.flush()
        header = self.responses.readline().split()
        if len(header) != 3 or header[0] != oid or not header[2].isdigit():
            raise KnowledgeError(f'missing or unreadable Git object {oid.decode()}')
        kind, size = header[1], int(header[2])
        body = self.responses.read(size)
        if len(body) != size or self.responses.read(1) != b'\n':
            raise KnowledgeError(f'incomplete Git object {oid.decode()}')
        return kind, body

    def read(self, oid: bytes, expected_kind: bytes) -> bytes:
        if oid not in self.objects:
            if not _OID.fullmatch(oid):
                raise KnowledgeError('invalid Git object ID')
            kind, body = self._read(oid)
            digest = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
            digest.update(kind + b' ' + str(len(body)).encode() + b'\0')
            digest.update(body)
            if digest.hexdigest().encode() != oid:
                raise KnowledgeError(f'Git object hash mismatch for {oid.decode()}')
            self.objects[oid] = kind, body
        kind, body = self.objects[oid]
        if kind != expected_kind:
            raise KnowledgeError(f'unexpected Git object type for {oid.decode()}')
        return body

    def snapshot(self, oid: bytes) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        self._read_tree(oid, '', files)
        return files

    def _read_tree(self, oid: bytes, prefix: str, files: dict[str, bytes]) -> None:
        tree = self.read(oid, b'tree')
        if not tree:
            raise KnowledgeError('unsupported snapshot layout')
        width = len(oid) // 2
        cursor, names = 0, set()
        while cursor < len(tree):
            end = tree.find(b'\0', cursor)
            if end < 0 or end + 1 + width > len(tree):
                raise KnowledgeError('invalid Git tree entry')
            mode, sep, raw = tree[cursor:end].partition(b' ')
            cursor = end + 1 + width
            if not sep:
                raise KnowledgeError('invalid Git tree entry')
            name = raw.decode()
            if '/' in name or name in ('.', '..') or name in names:
                raise KnowledgeError(f'unsafe repository path: {name!r}')
            _safe(name)
            names.add(name)
            child = tree[end + 1:cursor].hex().encode()
            if mode == b'40000':
                self._read_tree(child, prefix + name + '/', files)
            elif mode == b'100644':
                files[prefix + name] = self.read(child, b'blob')
            else:
                raise KnowledgeError('snapshot contains a non-regular file')


@contextmanager
def _git_objects(path: Path) -> Iterator[_GitObjects]:
    try:
        with subprocess.Popen(['git', *IDENTITY, 'cat-file', '--batch'], cwd=path, env=_environment(),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            yield _GitObjects(process.stdin, process.stdout)
    except OSError as error:
        raise KnowledgeError(f'git cat-file failed: {error}') from error
    if process.returncode:
        raise KnowledgeError(f'git cat-file failed ({process.returncode})')


def _knowledge_metadata(data: bytes) -> dict:
    try:
        metadata = json.loads(data)
    except (ValueError, RecursionError) as error:
        raise KnowledgeError(_SCHEMA_ERROR) from error
    if not isinstance(metadata, dict) or metadata.get('schema') != SCHEMA:
        raise KnowledgeError(_SCHEMA_ERROR)
    return metadata


class Repository:
    def __init__(self, root: Path, game: str):
        if not game or '/' in game or game.startswith('.'):
            raise KnowledgeError(f'bad game name: {game!r}')
        self.game = game
        self.path = Path(root) / game
        self.state = Path(root) / f'{game}.state'
        self._validated_history = None

    def _tags(self) -> list[str]:
        if not (self.path / '.git').exists():
            return []
        out = _git(self.path, 'tag', '--list', 'v*').decode('utf-8')
        return [line for line in out.splitlines() if _VERSION.fullmatch(line)]

    def ensure(self) -> str:
        """Create the repository at v0 if absent. Idempotent; returns the published version."""
        if 'v0' in self._tags():
            return self.published()
        self.path.mkdir(parents=True, exist_ok=True)
        if not (self.path / '.git').exists():
            _git(self.path, 'init', '-q', '-b', BRANCH)
        else:
            try:
                _git(self.path, 'rev-parse', '--verify', '-q', 'HEAD')
            except KnowledgeError:
                pass
            else:
                raise KnowledgeError(f'{self.path} has commits without v0; start a fresh repository')
        files = {
            'knowledge.json': _dump({'schema': SCHEMA, 'game': self.game}),
            'facts.jsonl': b'',
            'provenance.json': _dump({'frames': {}, 'frame_clocks': {}, 'sessions': {}, 'branches': {}, 'restores': []}),
            'programs/.keep': b'',
            'tests/.keep': b'',
        }
        self._publish(files, f'Initialize {self.game} knowledge repository', 'v0')
        return self.published()

    def published(self) -> str:
        tags = self._tags()
        if not tags:
            raise KnowledgeError(f'{self.path} has no published version; call ensure()')
        version = f'v{max(_number(tag) for tag in tags)}'
        self._check_schema(version)
        return version

    def _resolve(self, version: str | None) -> str:
        if version is None:
            return self.published()
        _number(version)
        if version not in self._tags():
            raise KnowledgeError(f'unknown version {version}')
        self._check_schema(version)
        return version

    def _check_schema(self, version: str) -> None:
        try:
            data = self._show(version, 'knowledge.json')
        except KnowledgeError as error:
            raise KnowledgeError(_SCHEMA_ERROR) from error
        _knowledge_metadata(data)

    def _show(self, version: str, relative: str) -> bytes:
        return _git(self.path, 'show', f'{version}:{relative}')

    def export(self, version: str, dest: Path) -> None:
        """Write the files at `version` into the new directory `dest`, without `.git`."""
        version = self._resolve(version)
        dest = Path(dest)
        if dest.exists():
            raise KnowledgeError(f'export destination exists: {dest}')
        names = _git(self.path, 'ls-tree', '-r', '-z', '--name-only', version)
        dest.mkdir(parents=True)
        for raw in names.decode('utf-8').split('\0'):
            if not raw:
                continue
            target = dest.joinpath(*_safe(raw).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self._show(version, raw))

    def records(self, version: str | None = None) -> list[dict]:
        text = self._show(self._resolve(version), 'facts.jsonl').decode('utf-8')
        return [json.loads(line) for line in text.split('\n') if line.strip()]

    def facts(self, version: str | None = None) -> list[dict]:
        return [item for item in self.records(version) if item.get('record') == 'fact']

    def articles(self, version: str | None = None) -> list[dict]:
        return [item for item in self.records(version) if item.get('record') == 'article']

    def provenance(self, version: str | None = None) -> dict:
        return json.loads(self._show(self._resolve(version), 'provenance.json'))

    def commit(self, files: dict[str, bytes], message: str) -> str:
        """Write `files`, commit and tag the next version; on any failure restore the tree."""
        next_version = f'v{_number(self.published()) + 1}'
        self._publish(files, message, next_version)
        return next_version

    def snapshot(self, version: str) -> dict[str, bytes]:
        """Read a published tree, refusing non-regular Git entries."""
        version = self._resolve(version)
        tree = _git(self.path, 'rev-parse', '--verify', f'refs/tags/{version}^{{tree}}').strip()
        with _git_objects(self.path) as objects:
            return objects.snapshot(tree)

    def _verified_snapshots(self) -> Iterator[tuple[str, bytes, dict[str, bytes]]]:
        """Read version tags by object ID and verify the chain of published commits."""
        if not (self.path / '.git').exists():
            return
        refs = _git(self.path, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/tags', 'refs/replace')
        tags = {}
        for line in refs.splitlines():
            ref, oid = line.rsplit(b' ', 1)
            if ref.startswith(b'refs/replace/'):
                raise KnowledgeError('incompatible or unavailable history: Git replacement refs')
            version = ref.removeprefix(b'refs/tags/').decode('utf-8')
            if _VERSION.fullmatch(version):
                tags[version] = oid
        with _git_objects(self.path) as objects:
            parents = []
            for number, version in enumerate(sorted(tags, key=_number)):
                oid = tags[version]
                try:
                    commit = objects.read(oid, b'commit')
                    headers = commit.split(b'\n\n', 1)[0].split(b'\n')
                    commit_parents = []
                    for line in headers[1:]:
                        if not line.startswith(b'parent '):
                            break
                        commit_parents.append(line[7:])
                    if version != f'v{number}' or not headers[0].startswith(b'tree ') or commit_parents != parents:
                        raise KnowledgeError('version tags do not form a consecutive commit history')
                    files = objects.snapshot(headers[0][5:])
                except (ValueError, OSError, RecursionError) as error:
                    raise KnowledgeError(f'incompatible history at {version}: {error}') from error
                yield version, oid, files
                parents = [oid]

    def reconcile(self) -> None:
        """Discard unpublished work and return the writer to the highest tag."""
        version = self.published()
        _git(self.path, 'reset', '-q', '--hard', version)
        _git(self.path, 'clean', '-fdxq')

    def commit_snapshot(self, files: dict[str, bytes], message: str) -> str:
        """Publish an exact tree, removing files omitted from the snapshot."""
        current = self.snapshot(self.published())
        next_version = f'v{_number(self.published()) + 1}'
        self._publish(files, message, next_version, delete=set(current) - set(files))
        return next_version

    def _publish(self, files: dict[str, bytes], message: str, tag: str, *, delete: set[str] = frozenset()) -> None:
        targets = {_safe(name): data for name, data in files.items()}
        try:
            head = _git(self.path, 'rev-parse', '--verify', '-q', 'HEAD').decode().strip()
        except KnowledgeError:
            head = None
        try:
            for name in delete:
                self.path.joinpath(*_safe(name).parts).unlink()
            for relative, data in targets.items():
                target = self.path.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            _git(self.path, 'add', '-A')
            _git(self.path, 'commit', '-q', '--no-verify', '-m', message)
            _git(self.path, 'tag', tag)
        except BaseException:
            # A tag may have been created even if the tagging command reported failure.
            # Never reset the branch away from a known published commit.
            try:
                published = tag in self._tags()
            except KnowledgeError:
                published = None
            if published is False:
                self._rollback(head)
            raise

    def _rollback(self, head: str | None) -> None:
        """Best effort: return the branch, index and tree to `head`. The tag is the last step,
        so a failure never leaves a new version published."""
        try:
            if head is None:
                subprocess.run(['git', 'update-ref', '-d', 'HEAD'], cwd=self.path,
                               env=_environment(), capture_output=True, check=False)
                subprocess.run(['git', 'read-tree', '--empty'], cwd=self.path,
                               env=_environment(), capture_output=True, check=False)
            else:
                subprocess.run(['git', 'reset', '-q', '--hard', head], cwd=self.path,
                               env=_environment(), capture_output=True, check=False)
            subprocess.run(['git', 'clean', '-fdxq'], cwd=self.path, env=_environment(),
                           capture_output=True, check=False)
        except OSError:
            pass


def _dump(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
