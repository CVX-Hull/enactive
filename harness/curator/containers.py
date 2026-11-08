"""Draft containers for curator sessions (ADR 009 D17; #453).

A draft is work in progress the curator carries between sessions. Software, not the curator,
lists drafts, surfaces open and stale ones, renews a draft a session writes to, ages the
others, and archives one that is abandoned or promoted. Each draft is a directory with a
`container-manifest/1` manifest (kind `draft`) kept beside its files, outside the workspace.

Lifecycle: `open` → `stale` after STALE_AFTER untouched sessions → `abandoned` after
ABANDON_AFTER more, then archived. A write renews it to `open`. A submission accepted with
`from_drafts` promotes it, and it is archived.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

from harness.trace.sidecar import validate

STALE_AFTER = 3
ABANDON_AFTER = 3
DRAFT_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
MAX_DRAFT_BYTES = 4 << 20


class UnsafeTree(ValueError):
    """A tree the curator wrote holds a link, a special file or an unreadable entry."""


MAX_ENTRIES = 10_000
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def open_directory(name: str | os.PathLike, dir_fd: int | None = None) -> int:
    """Open a directory without following a link at its last component; refuse anything else."""
    try:
        fd = os.open(name, _DIRECTORY, dir_fd=dir_fd)
    except OSError as exc:
        raise UnsafeTree(f'{os.fsdecode(name)!r}: not a plain, readable directory ({type(exc).__name__})') from exc
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise UnsafeTree(f'{os.fsdecode(name)!r}: not a directory')
    return fd


def read_tree(root: str | os.PathLike, *, limit: int, file_limit: int | None = None, dir_fd: int | None = None,
              max_entries: int = MAX_ENTRIES) -> dict[str, bytes]:
    """Every regular file under `root`, by relative POSIX path, read through directory descriptors.

    Each component is opened relative to its parent's descriptor with `O_NOFOLLOW`, and each
    opened object is checked with `fstat`, so a writer that swaps a directory for a link while
    this runs cannot redirect the walk outside `root`. A link, a special file, an unreadable
    entry, more than `max_entries` entries, a file over `file_limit` or a total over `limit`
    refuses the whole tree; nothing is truncated.
    """
    file_limit = limit if file_limit is None else file_limit
    files: dict[str, bytes] = {}
    total = entries = 0
    stack = [(open_directory(root, dir_fd), '')]
    try:
        while stack:
            directory, prefix = stack.pop()
            try:
                with os.scandir(directory) as listing:
                    names = [(entry.name, entry.stat(follow_symlinks=False).st_mode) for entry in listing]
                for name, mode in names:
                    entries += 1
                    if entries > max_entries:
                        raise UnsafeTree(f'more than {max_entries} entries')
                    relative = prefix + name
                    if stat.S_ISDIR(mode):
                        stack.append((open_directory(name, directory), relative + '/'))
                        continue
                    if not stat.S_ISREG(mode):
                        raise UnsafeTree(f'{relative!r}: a link or special file')
                    fd = os.open(name, _FILE, dir_fd=directory)
                    try:
                        size = os.fstat(fd)
                        if not stat.S_ISREG(size.st_mode):
                            raise UnsafeTree(f'{relative!r}: not a regular file')
                        if size.st_size > file_limit or total + size.st_size > limit:
                            raise UnsafeTree(f'{relative!r}: over the size limit')
                        with os.fdopen(fd, 'rb', closefd=False) as stream:
                            content = stream.read(min(file_limit, limit - total) + 1)
                    finally:
                        os.close(fd)
                    total += len(content)
                    if len(content) > file_limit or total > limit:
                        raise UnsafeTree(f'{relative!r}: over the size limit')
                    files[relative] = content
            finally:
                os.close(directory)
    except OSError as exc:
        raise UnsafeTree(f'unreadable entry ({type(exc).__name__})') from exc
    finally:
        for directory, _ in stack:
            os.close(directory)
    return dict(sorted(files.items()))


def write_tree(files: dict[str, bytes], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        (dest/relative).parent.mkdir(parents=True, exist_ok=True)
        (dest/relative).write_bytes(content)


def copy_tree(source: Path, dest: Path, *, limit: int = MAX_DRAFT_BYTES, file_limit: int | None = None) -> None:
    """Copy a plain tree of regular files, never following links; refuse it over the limits."""
    write_tree(read_tree(source, limit=limit, file_limit=file_limit), dest)


def digest(files: dict[str, bytes]) -> str:
    """A content digest of a draft's files (length-prefixed names and bytes), ignoring the manifest."""
    h = hashlib.sha256()
    for relative, content in sorted(files.items()):
        if relative == 'manifest.json':
            continue
        name = relative.encode()
        h.update(len(name).to_bytes(8, 'big') + name + len(content).to_bytes(8, 'big') + content)
    return h.hexdigest()


def _digest(directory: Path) -> str:
    return digest(read_tree(directory, limit=MAX_DRAFT_BYTES))


class Drafts:
    def __init__(self, state: Path):
        self.root = state/'drafts'
        self.archive = state/'drafts-archive'
        self.staging = state/'drafts-staging'
        for directory in (self.root, self.archive, self.staging):
            directory.mkdir(parents=True, exist_ok=True)

    def _manifest(self, draft_id: str) -> dict:
        return json.loads((self.root/draft_id/'manifest.json').read_text())

    def _write(self, draft_id: str, manifest: dict) -> None:
        validate(manifest)
        (self.root/draft_id/'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))

    def list(self, states=('open', 'stale')) -> list[dict]:
        out = []
        for directory in sorted(p for p in self.root.iterdir() if p.is_dir()):
            manifest = self._manifest(directory.name)
            if manifest['lifecycle']['state'] in states:
                out.append(manifest)
        return out

    def checkout(self, target: Path) -> dict[str, str]:
        """Copy open and stale drafts into a workspace's `drafts/`; returns their digests."""
        before = {}
        for manifest in self.list():
            draft_id = manifest['id']
            files = {k: v for k, v in read_tree(self.root/draft_id, limit=MAX_DRAFT_BYTES * 2).items()
                     if k != 'manifest.json'}
            write_tree(files, target/draft_id)
            before[draft_id] = digest(files)
        return before

    def collect(self, source: Path, session_id: str, before: dict[str, str], *, age: bool = True) -> dict:
        """Bring a workspace's drafts back after a session; renew, create, age and archive.

        `source` and every draft are read through directory descriptors without following a
        link (see `read_tree`): a link, a special file or a tree holding one is refused, never
        copied, even if a surviving writer swaps entries during collection. `age=False` (an
        aborted session) collects without ageing. Raises `UnsafeTree` if `source` itself is
        not a plain directory.
        """
        report = dict(created=[], renewed=[], aged=[], stale=[], abandoned=[], refused=[])
        parent = open_directory(source)
        try:
            with os.scandir(parent) as listing:
                names = sorted(entry.name for entry in listing)
            for draft_id in names:
                if not DRAFT_ID.fullmatch(draft_id) or (self.archive/draft_id).exists():
                    report['refused'].append(dict(id=draft_id, reason='invalid or already-archived draft id'))
                    continue
                try:
                    files = read_tree(draft_id, dir_fd=parent, limit=MAX_DRAFT_BYTES)
                except UnsafeTree as exc:
                    report['refused'].append(dict(id=draft_id, reason=str(exc)))
                    continue
                files.pop('manifest.json', None)
                if digest(files) == before.get(draft_id):
                    continue
                staged = self.staging/draft_id
                if staged.exists():
                    shutil.rmtree(staged)
                write_tree(files, staged)
                self._renew(draft_id, staged, session_id, report)
        finally:
            os.close(parent)
        if age:
            self._age(report)
        return report

    def _renew(self, draft_id: str, staged: Path, session_id: str, report: dict) -> None:
        """Replace a draft's files with the staged copy and mark it open (created or renewed)."""
        existing = (self.root/draft_id/'manifest.json').is_file()
        manifest = self._manifest(draft_id) if existing else dict(
            schema='container-manifest/1', id=draft_id, kind='draft', owner_role='curator',
            inputs=dict(created_by_session=session_id), pinned={}, budgets=dict(max_bytes=MAX_DRAFT_BYTES),
            lifecycle={}, provenance=dict(sessions=[]), retention=dict(
                policy=f'stale after {STALE_AFTER} untouched sessions, abandoned after {ABANDON_AFTER} more'))
        if existing:
            shutil.rmtree(self.root/draft_id)
        staged.rename(self.root/draft_id)
        manifest['lifecycle'] = dict(state='open', untouched_sessions=0, last_touched_session=session_id)
        manifest['provenance']['sessions'].append(session_id)
        self._write(draft_id, manifest)
        report['renewed' if existing else 'created'].append(draft_id)

    def _age(self, report: dict) -> None:
        """Age every open or stale draft this session did not write; archive the abandoned."""
        for manifest in self.list():
            draft_id = manifest['id']
            if draft_id in report['created'] or draft_id in report['renewed']:
                continue
            life = manifest['lifecycle']
            life['untouched_sessions'] = life.get('untouched_sessions', 0) + 1
            if life['state'] == 'open' and life['untouched_sessions'] >= STALE_AFTER:
                life['state'] = 'stale'
                report['stale'].append(draft_id)
            elif life['state'] == 'stale' and life['untouched_sessions'] >= STALE_AFTER + ABANDON_AFTER:
                life['state'] = 'abandoned'
                report['abandoned'].append(draft_id)
            else:
                report['aged'].append(draft_id)
            self._write(draft_id, manifest)
            if life['state'] == 'abandoned':
                shutil.move(str(self.root/draft_id), str(self.archive/draft_id))

    def promote(self, draft_ids, session_id: str) -> list[str]:
        promoted = []
        for draft_id in draft_ids:
            if (not isinstance(draft_id, str) or not DRAFT_ID.fullmatch(draft_id)
                    or not (self.root/draft_id/'manifest.json').is_file()):
                continue
            manifest = self._manifest(draft_id)
            manifest['lifecycle'] = dict(manifest['lifecycle'], state='promoted', promoted_by_session=session_id)
            self._write(draft_id, manifest)
            shutil.move(str(self.root/draft_id), str(self.archive/draft_id))
            promoted.append(draft_id)
        return promoted
