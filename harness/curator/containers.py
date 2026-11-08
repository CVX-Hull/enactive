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


def safe_files(root: Path) -> list[Path]:
    """Regular files under `root`, relative, refusing anything that is not a plain tree.

    `root` itself and every entry are examined without following links; a symbolic link, a
    FIFO, a device or an unreadable entry anywhere makes the whole tree unsafe.
    """
    try:
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            raise UnsafeTree(f'{root.name}: not a plain directory')
        files: list[Path] = []
        stack = [root]
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    mode = entry.stat(follow_symlinks=False).st_mode
                    if stat.S_ISDIR(mode):
                        stack.append(Path(entry.path))
                    elif stat.S_ISREG(mode):
                        files.append(Path(entry.path).relative_to(root))
                    else:
                        raise UnsafeTree(f'{entry.name}: a link or special file')
    except OSError as exc:
        raise UnsafeTree(f'{root.name}: unreadable ({type(exc).__name__})') from exc
    return sorted(files)


def _read(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise UnsafeTree(f'{path.name}: not a regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read(MAX_DRAFT_BYTES + 1)
    finally:
        os.close(fd)


def copy_tree(source: Path, dest: Path, *, limit: int = MAX_DRAFT_BYTES) -> None:
    """Copy a plain tree of regular files, never following links; refuse it over `limit` bytes."""
    files = safe_files(source)
    data = {rel: _read(source/rel) for rel in files}
    if sum(len(v) for v in data.values()) > limit:
        raise UnsafeTree(f'{source.name}: over the size limit')
    dest.mkdir(parents=True, exist_ok=True)
    for rel, content in data.items():
        (dest/rel).parent.mkdir(parents=True, exist_ok=True)
        (dest/rel).write_bytes(content)


def _digest(directory: Path) -> str:
    """A content digest of a draft's files (length-prefixed names and bytes), ignoring the manifest."""
    h = hashlib.sha256()
    for rel in safe_files(directory):
        if rel.as_posix() == 'manifest.json':
            continue
        name, content = rel.as_posix().encode(), _read(directory/rel)
        h.update(len(name).to_bytes(8, 'big') + name + len(content).to_bytes(8, 'big') + content)
    return h.hexdigest()


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
            copy_tree(self.root/draft_id, target/draft_id)
            manifest_copy = target/draft_id/'manifest.json'
            if manifest_copy.exists():
                manifest_copy.unlink()
            before[draft_id] = _digest(target/draft_id)
        return before

    def collect(self, source: Path, session_id: str, before: dict[str, str], *, age: bool = True) -> dict:
        """Bring a workspace's drafts back after a session; renew, create, age and archive.

        `source` must be a plain directory (the caller lstats it). Each entry is examined
        without following links: a symbolic link, a special file or a tree holding one is
        refused, never copied. `age=False` (an aborted session) collects without ageing.
        """
        report = dict(created=[], renewed=[], aged=[], stale=[], abandoned=[], refused=[])
        try:
            with os.scandir(source) as listing:
                entries = sorted(listing, key=lambda entry: entry.name)
        except OSError:
            entries = []
        for entry in entries:
            draft_id = entry.name
            try:
                plain = stat.S_ISDIR(entry.stat(follow_symlinks=False).st_mode)
            except OSError:
                plain = False
            if not plain:
                report['refused'].append(dict(id=draft_id, reason='not a plain directory'))
                continue
            directory = Path(entry.path)
            if not DRAFT_ID.fullmatch(draft_id) or (self.archive/draft_id).exists():
                report['refused'].append(dict(id=draft_id, reason='invalid or already-archived draft id'))
                continue
            try:
                staged = self.staging/draft_id
                if staged.exists():
                    shutil.rmtree(staged)
                copy_tree(directory, staged)
            except UnsafeTree as exc:
                report['refused'].append(dict(id=draft_id, reason=str(exc)))
                continue
            changed = _digest(staged) != before.get(draft_id)
            if not changed:
                shutil.rmtree(staged)
                continue
            existing = (self.root/draft_id/'manifest.json').is_file()
            manifest = self._manifest(draft_id) if existing else dict(
                schema='container-manifest/1', id=draft_id, kind='draft', owner_role='curator',
                inputs=dict(created_by_session=session_id), pinned={}, budgets=dict(max_bytes=MAX_DRAFT_BYTES),
                lifecycle={}, provenance=dict(sessions=[]), retention=dict(
                    policy=f'stale after {STALE_AFTER} untouched sessions, abandoned after {ABANDON_AFTER} more'))
            if (staged/'manifest.json').exists():
                (staged/'manifest.json').unlink()
            if existing:
                shutil.rmtree(self.root/draft_id)
            staged.rename(self.root/draft_id)
            manifest['lifecycle'] = dict(state='open', untouched_sessions=0, last_touched_session=session_id)
            manifest['provenance']['sessions'].append(session_id)
            self._write(draft_id, manifest)
            report['renewed' if existing else 'created'].append(draft_id)
        if not age:
            return report
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
        return report

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
