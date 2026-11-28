"""Frozen same-lineage ancestor source index (`player-source-index/1`) and agenda continuation validation (`player-agenda-continuation/1`).

Pure player-domain data/verification helpers with no custody, server, evaluation, or curator imports.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any

from harness.computer.protocol import ControlError, source as validate_computer_source
from harness.jsonio import canonical, strict_loads

SOURCE_INDEX_SCHEMA = 'player-source-index/1'
AGENDA_SCHEMA = 'player-agenda-continuation/1'
SOURCE_READ_SCHEMA = 'player-source-read/2'

IMAGE_LIMIT = 16 * 1024 * 1024
AGENDA_MAX_BYTES = 3072
AGENDA_MAX_ACTIVE = 8
AGENDA_MAX_THREADS = 16
AGENDA_MAX_SUB_ITEMS = 6
AGENDA_MAX_REFS = 8

_HEX32 = re.compile(r'[0-9a-f]{32}')
_HEX64 = re.compile(r'[0-9a-f]{64}')
_ALIAS = re.compile(r's(?:0[1-9]|[1-9][0-9]+)')
_SOURCE_ID = re.compile(r'[0-9a-f]{32}-[1-9][0-9]*')
_THREAD_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
_LABEL = re.compile(r'[ -~]{1,40}')
_PROVENANCE_KINDS = frozenset(('sealed-evidence', 'closed-session'))
_THREAD_STATUSES = frozenset(('active', 'paused', 'done', 'dropped'))
_UNAVAILABLE_REASONS = frozenset(('unknown-or-out-of-scope', 'missing', 'integrity-failed', 'image-limit'))


class SourceIndexError(ValueError):
    """Raised when a frozen `player-source-index/1` or `player-agenda-continuation/1` document is malformed."""


class SourceUnavailable(Exception):
    """Raised when an eligible disclosed ancestor frame cannot be read cleanly without tripping live runtime stop."""

    def __init__(self, reason: str, detail: str = '') -> None:
        if reason not in _UNAVAILABLE_REASONS:
            raise ValueError(f'Unknown source unavailable reason: {reason!r}')
        super().__init__(detail or reason)
        self.reason = reason


def empty_source_index(world: str | None = None, lineage: str | None = None) -> dict[str, Any]:
    return dict(schema=SOURCE_INDEX_SCHEMA, world=world, lineage=lineage, roots={}, sources={})


def empty_agenda() -> dict[str, Any]:
    return dict(schema=AGENDA_SCHEMA, cut_count=0, threads=[])


def _nonblank(value: object, max_len: int) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= max_len and bool(value.strip())


def validate_agenda(value: object) -> dict[str, Any]:
    """Validate a closed `player-agenda-continuation/1` document."""
    if not isinstance(value, dict) or set(value) != {'schema', 'cut_count', 'threads'}:
        raise SourceIndexError(f'Expected closed {AGENDA_SCHEMA} object')
    if value['schema'] != AGENDA_SCHEMA:
        raise SourceIndexError(f'Unsupported agenda schema {value["schema"]!r}; expected {AGENDA_SCHEMA}')
    cut_count = value['cut_count']
    if type(cut_count) is not int or cut_count < 0:
        raise SourceIndexError('Agenda cut_count must be a non-negative integer')
    threads = value['threads']
    if not isinstance(threads, list) or len(threads) > AGENDA_MAX_THREADS:
        raise SourceIndexError(f'Agenda threads must be a list of at most {AGENDA_MAX_THREADS} items')
    seen_ids: set[str] = set()
    active_count = 0
    for thread in threads:
        if not isinstance(thread, dict):
            raise SourceIndexError('Agenda thread must be an object')
        required = {'id', 'title', 'status', 'created_at_cut', 'updated_at_cut'}
        optional = {'notes', 'stop_when', 'drop_reason', 'sub_items', 'refs'}
        if not required <= set(thread) or not set(thread) <= (required | optional):
            raise SourceIndexError('Agenda thread has missing or unexpected fields')
        tid = thread['id']
        if not isinstance(tid, str) or _THREAD_ID.fullmatch(tid) is None or tid in seen_ids:
            raise SourceIndexError(f'Invalid or duplicate agenda thread id {tid!r}')
        seen_ids.add(tid)
        if not _nonblank(thread['title'], 120):
            raise SourceIndexError(f'Agenda thread {tid!r} has invalid title')
        status = thread['status']
        if status not in _THREAD_STATUSES:
            raise SourceIndexError(f'Agenda thread {tid!r} has invalid status {status!r}')
        if status in ('active', 'paused'):
            active_count += 1
        created = thread['created_at_cut']
        updated = thread['updated_at_cut']
        if type(created) is not int or type(updated) is not int or created < 0 or updated < created or updated > cut_count:
            raise SourceIndexError(f'Agenda thread {tid!r} has invalid cut stamps')
        if 'notes' in thread and not _nonblank(thread['notes'], 240):
            raise SourceIndexError(f'Agenda thread {tid!r} has invalid notes')
        if 'stop_when' in thread and not _nonblank(thread['stop_when'], 160):
            raise SourceIndexError(f'Agenda thread {tid!r} has invalid stop_when')
        if status == 'dropped':
            if 'drop_reason' not in thread or not _nonblank(thread['drop_reason'], 160):
                raise SourceIndexError(f'Dropped agenda thread {tid!r} requires drop_reason')
        elif 'drop_reason' in thread and not _nonblank(thread['drop_reason'], 160):
            raise SourceIndexError(f'Agenda thread {tid!r} has invalid drop_reason')
        if 'sub_items' in thread:
            items = thread['sub_items']
            if not isinstance(items, list) or len(items) > AGENDA_MAX_SUB_ITEMS:
                raise SourceIndexError(f'Agenda thread {tid!r} has invalid sub_items')
            for item in items:
                if (not isinstance(item, dict) or set(item) != {'text', 'done'}
                        or not _nonblank(item['text'], 100) or type(item['done']) is not bool):
                    raise SourceIndexError(f'Agenda thread {tid!r} has invalid sub_item')
        if 'refs' in thread:
            refs = thread['refs']
            if (not isinstance(refs, list) or len(refs) > AGENDA_MAX_REFS
                    or len(set(refs)) != len(refs) or any(not _nonblank(r, 128) for r in refs)):
                raise SourceIndexError(f'Agenda thread {tid!r} has invalid refs')
    if active_count > AGENDA_MAX_ACTIVE:
        raise SourceIndexError(f'Agenda exceeds maximum of {AGENDA_MAX_ACTIVE} active/paused threads')
    if len(canonical(value).encode('utf-8')) > AGENDA_MAX_BYTES:
        raise SourceIndexError(f'Agenda exceeds serialized bound of {AGENDA_MAX_BYTES} UTF-8 bytes')
    return value


def agenda_refs(agenda: dict[str, Any]) -> set[str]:
    """Return every reference carried on active or paused threads of a validated agenda."""
    refs: set[str] = set()
    for thread in agenda.get('threads', ()):
        if thread.get('status') in ('active', 'paused'):
            refs.update(thread.get('refs', ()))
    return refs


def _safe_rel_parts(rel: str, *, require_prefix: tuple[str, ...] | None = None) -> tuple[str, ...]:
    if not isinstance(rel, str) or not rel or rel.startswith('/') or '\\' in rel or '\x00' in rel:
        raise SourceIndexError(f'Invalid relative path {rel!r}')
    parts = tuple(rel.split('/'))
    if any(part in ('', '.', '..') for part in parts):
        raise SourceIndexError(f'Relative path must not traverse or contain empty segments: {rel!r}')
    if require_prefix is not None and parts[:len(require_prefix)] != require_prefix:
        raise SourceIndexError(f'Path {rel!r} must live under {"/".join(require_prefix)}/')
    return parts


def validate_source_index(
    value: object,
    *,
    root_dir: Path | None = None,
    expected_world: str | None = None,
    expected_lineage: str | None = None,
    check_labels: bool = False,
) -> dict[str, Any]:
    """Validate a closed `player-source-index/1` sidecar."""
    if not isinstance(value, dict) or set(value) != {'schema', 'world', 'lineage', 'roots', 'sources'}:
        raise SourceIndexError(f'Expected closed {SOURCE_INDEX_SCHEMA} object')
    if value['schema'] != SOURCE_INDEX_SCHEMA:
        raise SourceIndexError(f'Unsupported source index schema {value["schema"]!r}; expected {SOURCE_INDEX_SCHEMA}')
    world, lineage = value['world'], value['lineage']
    for name, label in (('world', world), ('lineage', lineage)):
        if label is not None and (not isinstance(label, str) or _LABEL.fullmatch(label) is None):
            raise SourceIndexError(f'Invalid {name} label in source index')
    if lineage is not None and world is None:
        raise SourceIndexError('Source index lineage requires a world')
    if check_labels and (world != expected_world or lineage != expected_lineage):
        raise SourceIndexError('Source index world/lineage differs from package labels')
    roots = value['roots']
    sources = value['sources']
    if not isinstance(roots, dict) or not isinstance(sources, dict):
        raise SourceIndexError('Source index roots and sources must be objects')
    if lineage is None and (roots or sources):
        raise SourceIndexError('Source index without a lineage must have empty roots and sources')

    seen_sessions: set[str] = set()
    root_fields = {'path', 'provenance', 'session_id', 'admission', 'evidence_manifest_sha256'}
    for alias, entry in roots.items():
        if not isinstance(alias, str) or _ALIAS.fullmatch(alias) is None:
            raise SourceIndexError(f'Invalid ancestor root alias {alias!r}')
        if not isinstance(entry, dict) or set(entry) != root_fields:
            raise SourceIndexError(f'Ancestor root {alias!r} has invalid fields')
        _safe_rel_parts(entry['path'], require_prefix=('.runtime',))
        prov = entry['provenance']
        if prov not in _PROVENANCE_KINDS:
            raise SourceIndexError(f'Ancestor root {alias!r} has invalid provenance {prov!r}')
        sid = entry['session_id']
        if not isinstance(sid, str) or _HEX32.fullmatch(sid) is None or sid in seen_sessions:
            raise SourceIndexError(f'Ancestor root {alias!r} has invalid or duplicate session_id')
        seen_sessions.add(sid)
        adm = entry['admission']
        if type(adm) is not int or not 1 <= adm <= 10000:
            raise SourceIndexError(f'Ancestor root {alias!r} has invalid admission number')
        ev_sha = entry['evidence_manifest_sha256']
        if prov == 'sealed-evidence':
            if not isinstance(ev_sha, str) or _HEX64.fullmatch(ev_sha) is None:
                raise SourceIndexError(f'Sealed-evidence root {alias!r} requires evidence_manifest_sha256')
        elif ev_sha is not None:
            raise SourceIndexError(f'Closed-session root {alias!r} must have null evidence_manifest_sha256')
        if root_dir is not None:
            resolved_root = (root_dir / '.runtime').resolve()
            candidate = (root_dir / entry['path']).resolve()
            if not candidate.is_relative_to(resolved_root):
                raise SourceIndexError(f'Ancestor root {alias!r} escapes .runtime/')

    source_fields = {'root', 'relpath', 'source', 'actor', 'step'}
    for source_id, entry in sources.items():
        if not isinstance(source_id, str) or _SOURCE_ID.fullmatch(source_id) is None:
            raise SourceIndexError(f'Invalid ancestor source_id {source_id!r}')
        if not isinstance(entry, dict) or set(entry) != source_fields:
            raise SourceIndexError(f'Ancestor source {source_id!r} has invalid fields')
        root_alias = entry['root']
        if root_alias not in roots:
            raise SourceIndexError(f'Ancestor source {source_id!r} names unknown root {root_alias!r}')
        if not source_id.startswith(roots[root_alias]['session_id'] + '-'):
            raise SourceIndexError(f'Ancestor source {source_id!r} session prefix differs from root {root_alias!r}')
        parts = _safe_rel_parts(entry['relpath'])
        if parts[0] not in ('sources', 'frames') or not parts[-1].endswith('.png'):
            raise SourceIndexError(f'Ancestor source {source_id!r} relpath must point to a PNG under sources/ or frames/')
        try:
            meta = validate_computer_source(entry['source'])
        except (ControlError, ValueError, TypeError) as exc:
            raise SourceIndexError(f'Ancestor source {source_id!r} has invalid computer-source/1 metadata: {exc}') from exc
        if meta['source_id'] != source_id or meta['session'] != roots[root_alias]['session_id']:
            raise SourceIndexError(f'Ancestor source {source_id!r} metadata identity differs from index entry')
        if not _nonblank(entry['actor'], 64):
            raise SourceIndexError(f'Ancestor source {source_id!r} has invalid actor')
        step = entry['step']
        if step is not None and (type(step) is not int or step < 0):
            raise SourceIndexError(f'Ancestor source {source_id!r} has invalid step')
    return value


def _open_nofollow_file(base: Path, parts: tuple[str, ...]) -> int:
    """Walk every path component from `base` using O_NOFOLLOW; refuse symlinks and non-regular files."""
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
    dfd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_CLOEXEC', 0))
    try:
        for segment in parts[:-1]:
            try:
                nxt = os.open(segment, dir_flags, dir_fd=dfd)
            except FileNotFoundError as exc:
                raise SourceUnavailable('missing', f'Missing directory segment {segment!r}') from exc
            except OSError as exc:
                raise SourceUnavailable('integrity-failed', f'Refused directory segment {segment!r}: {exc}') from exc
            os.close(dfd)
            dfd = nxt
        try:
            ffd = os.open(parts[-1], file_flags, dir_fd=dfd)
        except FileNotFoundError as exc:
            raise SourceUnavailable('missing', f'Missing ancestor frame {parts[-1]!r}') from exc
        except OSError as exc:
            raise SourceUnavailable('integrity-failed', f'Refused ancestor frame {parts[-1]!r}: {exc}') from exc
        return ffd
    finally:
        os.close(dfd)


class SourceIndex:
    """Read-only verified reader for a frozen `player-source-index/1` sidecar."""

    def __init__(self, value: dict[str, Any], *, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.value = validate_source_index(value, root_dir=self.root_dir)
        self.roots: dict[str, dict[str, Any]] = self.value['roots']
        self.sources: dict[str, dict[str, Any]] = self.value['sources']

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        root_dir: Path,
        expected_world: str | None = None,
        expected_lineage: str | None = None,
        check_labels: bool = False,
    ) -> SourceIndex:
        try:
            raw = path.read_bytes()
            data = strict_loads(raw)
        except (OSError, ValueError, RecursionError) as exc:
            raise SourceIndexError(f'Unreadable source index {path}: {exc}') from exc
        validate_source_index(
            data,
            root_dir=root_dir,
            expected_world=expected_world,
            expected_lineage=expected_lineage,
            check_labels=check_labels,
        )
        return cls(data, root_dir=root_dir)

    def contains(self, source_id: str) -> bool:
        return isinstance(source_id, str) and source_id in self.sources

    def read_verified(
        self,
        source_id: str,
        *,
        max_bytes: int = IMAGE_LIMIT,
    ) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
        """Read and verify an eligible ancestor frame with O_NOFOLLOW, regular-file, size, and SHA-256 checks."""
        if not self.contains(source_id):
            raise SourceUnavailable('unknown-or-out-of-scope')
        entry = self.sources[source_id]
        root_alias = entry['root']
        root = self.roots[root_alias]
        parts = _safe_rel_parts(root['path'], require_prefix=('.runtime',)) + _safe_rel_parts(entry['relpath'])
        fd = _open_nofollow_file(self.root_dir, parts)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise SourceUnavailable('integrity-failed', 'Ancestor frame is not a regular file')
            if st.st_size > max_bytes:
                raise SourceUnavailable('image-limit', 'Ancestor frame exceeds image byte cap')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                png = stream.read(max_bytes + 1)
        finally:
            os.close(fd)
        if len(png) > max_bytes:
            raise SourceUnavailable('image-limit', 'Ancestor frame exceeds image byte cap')
        if not png.startswith(b'\x89PNG\r\n\x1a\n'):
            raise SourceUnavailable('integrity-failed', 'Ancestor frame is not valid PNG bytes')
        digest = hashlib.sha256(png).hexdigest()
        meta = dict(entry['source'])
        if digest != meta['sha256']:
            raise SourceUnavailable('integrity-failed', 'Ancestor frame SHA-256 differs from frozen index')
        origin = dict(admission=root_alias, actor=entry['actor'], step=entry['step'])
        return meta, png, origin
