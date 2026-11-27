"""Build frozen `player-source-index/1` sidecars from verified sealed-evidence or closed-session ancestors (#1025)."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Sequence

from harness.jsonio import file_sha256, strict_loads
from harness.player.source_index import (
    IMAGE_LIMIT,
    SOURCE_INDEX_SCHEMA,
    SourceIndexError,
    empty_source_index,
    validate_source_index,
)
from harness.trace.projection import PACKAGE_LABELS


def _read_json(path: Path, limit: int = 4 * 1024 * 1024) -> tuple[bytes, dict]:
    if path.is_symlink() or not path.is_file():
        raise SourceIndexError(f'{path}: missing or symlink')
    data = path.read_bytes()
    if len(data) > limit:
        raise SourceIndexError(f'{path}: exceeds byte limit')
    value = strict_loads(data)
    if not isinstance(value, dict):
        raise SourceIndexError(f'{path}: expected JSON object')
    return data, value


def _verified_run_root(
    run_dir: Path,
    *,
    root: Path,
    world: str,
    lineage: str,
    before_admission: int | None,
    provenance: str,
    evidence_manifest_sha256: str | None,
) -> tuple[int, str, dict, list[tuple[str, dict]]] | None:
    """Return `(admission, session_id, root_entry, [(source_id, source_entry), ...])` or None if ineligible."""
    run_dir = run_dir.resolve()
    runtime_root = (root / '.runtime').resolve()
    if not run_dir.is_relative_to(runtime_root) or not run_dir.is_dir():
        return None
    try:
        manifest_bytes, manifest = _read_json(run_dir / 'manifest.json')
        _, watch_start = _read_json(run_dir / 'watch-start.json', 65536)
    except (OSError, ValueError, SourceIndexError):
        return None

    schema = manifest.get('schema')
    session_id = manifest.get('session')
    if schema not in (*PACKAGE_LABELS, 'campaign-run/14') or not isinstance(session_id, str):
        return None
    if (watch_start.get('schema') != 'campaign-watch-start/4'
            or watch_start.get('session') != session_id
            or watch_start.get('manifest_sha256') != hashlib.sha256(manifest_bytes).hexdigest()):
        return None

    labels = manifest.get('labels')
    if not isinstance(labels, dict):
        return None
    if labels.get('world') != world or labels.get('lineage') != lineage:
        return None
    admission = labels.get('admission')
    if type(admission) is not int or admission < 1:
        return None
    if before_admission is not None and admission >= before_admission:
        return None

    if provenance == 'closed-session':
        # Never rely on `store-closing.json` alone; require sealed receipt.json + closed non-WAL DB.
        try:
            _, receipt = _read_json(run_dir / 'receipt.json')
        except (OSError, ValueError, SourceIndexError):
            return None
        if receipt.get('session') != session_id or 'ended_wall' not in receipt:
            return None

    db_path = run_dir / 'session.sqlite3'
    if db_path.is_symlink() or not db_path.is_file():
        return None
    wal_path = run_dir / 'session.sqlite3-wal'
    if wal_path.exists() and wal_path.stat().st_size > 0:
        # Never open an ancestor WAL database with uncheckpointed data.
        return None

    # Read sources and actor/step mapping from immutable closed SQLite store.
    sources_rows: list[tuple[str, dict]] = []
    uri = f'file:{db_path}?mode=ro&immutable=1'
    with closing(sqlite3.connect(uri, uri=True, timeout=1.0)) as conn:
        actor_dirs: dict[str, str] = {}
        for idx, (aid,) in enumerate(conn.execute('SELECT id FROM actors ORDER BY rowid').fetchall(), 1):
            actor_dirs[aid] = f'{idx:03d}'
        source_origin: dict[str, tuple[str, int]] = {}
        op_counts: dict[str, int] = {}
        for op_id, actor_id, final_json in conn.execute(
            'SELECT id, actor, final_json FROM operations ORDER BY created_wall, id'
        ).fetchall():
            op_counts[actor_id] = op_counts.get(actor_id, 0) + 1
            step = op_counts[actor_id]
            actor_label = actor_dirs.get(actor_id, actor_id[:8])
            if final_json:
                try:
                    final = json.loads(final_json)
                    src = final.get('source') if isinstance(final, dict) else None
                    if isinstance(src, dict) and isinstance(src.get('source_id'), str):
                        source_origin.setdefault(src['source_id'], (actor_label, step))
                except ValueError:
                    pass
            for (src_id,) in conn.execute(
                'SELECT source FROM native_intents WHERE operation=? AND source IS NOT NULL ORDER BY rowid',
                (op_id,),
            ).fetchall():
                source_origin.setdefault(src_id, (actor_label, step))
            for (src_id,) in conn.execute(
                'SELECT source FROM collections WHERE native_id IN '
                '(SELECT id FROM native_intents WHERE operation=?) AND source IS NOT NULL ORDER BY rowid',
                (op_id,),
            ).fetchall():
                source_origin.setdefault(src_id, (actor_label, step))

        for src_id, meta_json in conn.execute('SELECT id, metadata FROM sources ORDER BY rowid').fetchall():
            if not isinstance(src_id, str) or not src_id.startswith(session_id + '-'):
                continue
            try:
                meta = json.loads(meta_json)
            except ValueError:
                continue
            rel = f'sources/{src_id}.png'
            png_path = run_dir / rel
            if png_path.is_symlink() or not png_path.is_file():
                continue
            st = png_path.stat()
            if st.st_size > IMAGE_LIMIT or file_sha256(png_path) != meta.get('sha256'):
                continue
            actor_label, step = source_origin.get(src_id, ('001', None))
            sources_rows.append((
                src_id,
                dict(
                    relpath=rel,
                    source=meta,
                    actor=actor_label,
                    step=step,
                ),
            ))

    rel_root = run_dir.relative_to(root).as_posix()
    root_entry = dict(
        path=rel_root,
        provenance=provenance,
        session_id=session_id,
        admission=admission,
        evidence_manifest_sha256=evidence_manifest_sha256,
    )
    return admission, session_id, root_entry, sources_rows


def build_source_index(
    *,
    root: Path,
    world: str | None,
    lineage: str | None,
    before_admission: int | None = None,
    extra_runs: Sequence[Path] = (),
    include_sealed_evidence: bool = True,
) -> dict:
    """Build a frozen `player-source-index/1` dict for `(world, lineage)` before `before_admission`.

    Uses canonical `.runtime/` ancestor roots backed by explicit sealed-evidence manifests or
    verified closed-session checkpoints (`receipt.json` + `watch-start.json`, non-WAL DB).
    Never copies PNGs and never opens live WAL SQLite databases.
    """
    root = root.resolve()
    if world is None or lineage is None:
        return empty_source_index(world, lineage)

    candidates: list[tuple[int, str, dict, list[tuple[str, dict]]]] = []
    seen_sessions: set[str] = set()

    if include_sealed_evidence:
        ev_index_path = root / 'data' / 'evidence' / 'index.json'
        if ev_index_path.is_file():
            try:
                _, ev_index = _read_json(ev_index_path, 16 * 1024 * 1024)
            except (OSError, ValueError, SourceIndexError):
                ev_index = {}
            for name, entry in sorted((ev_index.get('studies') or {}).items()):
                if not isinstance(entry, dict):
                    continue
                ev_sha = entry.get('manifest_sha256')
                if not isinstance(ev_sha, str) or len(ev_sha) != 64:
                    continue
                bundle_dir = root / '.runtime' / 'evidence' / name
                run_dir = bundle_dir / 'run' if (bundle_dir / 'run' / 'manifest.json').is_file() else bundle_dir
                found = _verified_run_root(
                    run_dir,
                    root=root,
                    world=world,
                    lineage=lineage,
                    before_admission=before_admission,
                    provenance='sealed-evidence',
                    evidence_manifest_sha256=ev_sha,
                )
                if found is not None and found[1] not in seen_sessions:
                    seen_sessions.add(found[1])
                    candidates.append(found)

    for extra in extra_runs:
        found = _verified_run_root(
            Path(extra),
            root=root,
            world=world,
            lineage=lineage,
            before_admission=before_admission,
            provenance='closed-session',
            evidence_manifest_sha256=None,
        )
        if found is not None and found[1] not in seen_sessions:
            seen_sessions.add(found[1])
            candidates.append(found)

    candidates.sort(key=lambda item: (item[0], item[1]))
    roots: dict[str, dict] = {}
    sources: dict[str, dict] = {}
    for index, (_, _, root_entry, rows) in enumerate(candidates, 1):
        alias = f's{index:02d}'
        roots[alias] = root_entry
        for src_id, src_entry in rows:
            sources[src_id] = dict(root=alias, **src_entry)

    result = dict(schema=SOURCE_INDEX_SCHEMA, world=world, lineage=lineage, roots=roots, sources=sources)
    return validate_source_index(result, root_dir=root, expected_world=world, expected_lineage=lineage, check_labels=True)
