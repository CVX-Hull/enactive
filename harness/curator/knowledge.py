"""The curator's knowledge repository: one Git repository per game (ADR 009's
one-repository-per-game direction; #453).

Only the gate commits (see `gate.py`). A publish is one commit on `main` and one tag `v<N>`;
the highest tag is the published version, so a commit that fails before its tag leaves the
published version unchanged. Nothing here runs anything the repository contains.
"""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

SCHEMA = 'curator-knowledge/1'
BRANCH = 'main'
IDENTITY = ('-c', 'user.name=enactive-gate', '-c', 'user.email=gate@localhost',
            '-c', 'commit.gpgsign=false', '-c', 'tag.gpgsign=false', '-c', 'core.hooksPath=/dev/null')
_VERSION = re.compile(r'v(0|[1-9][0-9]*)')


class KnowledgeError(ValueError):
    """The repository could not be read or published."""


def _environment() -> dict[str, str]:
    # An inherited GIT_DIR, GIT_INDEX_FILE or GIT_WORK_TREE (from a hook running the suite, for
    # example) would point every command, rollback's clean included, at another repository.
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    environment['GIT_CONFIG_GLOBAL'] = '/dev/null'
    environment['GIT_CONFIG_SYSTEM'] = '/dev/null'
    environment['GIT_TERMINAL_PROMPT'] = '0'
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


class Repository:
    def __init__(self, root: Path, game: str):
        if not game or '/' in game or game.startswith('.'):
            raise KnowledgeError(f'bad game name: {game!r}')
        self.game = game
        self.path = Path(root) / game
        self.state = Path(root) / f'{game}.state'

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
        files = {
            'knowledge.json': _dump({'schema': SCHEMA, 'game': self.game}),
            'facts.jsonl': b'',
            'ontology/types.json': b'[]\n',
            'programs/.keep': b'',
            'tests/.keep': b'',
        }
        self._publish(files, f'Initialize {self.game} knowledge repository', 'v0')
        return self.published()

    def published(self) -> str:
        tags = self._tags()
        if not tags:
            raise KnowledgeError(f'{self.path} has no published version; call ensure()')
        return f'v{max(_number(tag) for tag in tags)}'

    def _resolve(self, version: str | None) -> str:
        version = self.published() if version is None else version
        _number(version)
        if version not in self._tags():
            raise KnowledgeError(f'unknown version {version}')
        return version

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

    def facts(self, version: str | None = None) -> list[dict]:
        text = self._show(self._resolve(version), 'facts.jsonl').decode('utf-8')
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def types(self, version: str | None = None) -> list[dict]:
        return json.loads(self._show(self._resolve(version), 'ontology/types.json'))

    def commit(self, files: dict[str, bytes], message: str) -> str:
        """Write `files`, commit and tag the next version; on any failure restore the tree."""
        next_version = f'v{_number(self.published()) + 1}'
        self._publish(files, message, next_version)
        return next_version

    def _publish(self, files: dict[str, bytes], message: str, tag: str) -> None:
        targets = {_safe(name): data for name, data in files.items()}
        try:
            head = _git(self.path, 'rev-parse', '--verify', '-q', 'HEAD').decode().strip()
        except KnowledgeError:
            head = None
        try:
            for relative, data in targets.items():
                target = self.path.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            _git(self.path, 'add', '-A')
            _git(self.path, 'commit', '-q', '--no-verify', '-m', message)
            _git(self.path, 'tag', tag)
        except BaseException:
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
