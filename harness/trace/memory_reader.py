"""Read-only evidence reader for sealed `player-memory/2` stores (#452).

This is an evidence reader, not the player's memory contract. It reads the stored rows as
data so that a sealed store stays readable after the live contract migrates (S-MIGRATION
governs the live store, not sealed evidence). It never writes, never creates `-wal` or
`-shm` files beside the store, and accepts only the one schema it knows.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

SCHEMA = 'player-memory/2'


class StoreError(ValueError):
    """The sealed store is missing, unreadable or of another schema."""


def _connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise StoreError(f'{path}: missing store')
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)


def _document(text: str, where: str) -> dict:
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise StoreError(f'{where}: unreadable document') from exc
    if not isinstance(value, dict):
        raise StoreError(f'{where}: document is not an object')
    return value


def read(path: Path) -> dict:
    """Records, programs and source metadata (no PNG bytes) as plain data."""
    with _connect(path) as db:
        try:
            schemas = [row[0] for row in db.execute('SELECT schema FROM metadata')]
            if schemas != [SCHEMA]:
                raise StoreError(f'{path}: schema {schemas!r}, expected {SCHEMA}')
            supports: dict[str, list[str]] = {}
            for owner, target in db.execute('SELECT owner, target FROM record_supports ORDER BY rowid'):
                supports.setdefault(owner, []).append(target)
            sources_of: dict[str, list[str]] = {}
            for owner, target in db.execute('SELECT owner, target FROM record_sources ORDER BY rowid'):
                sources_of.setdefault(owner, []).append(target)
            records = []
            for rid, document, kind, supersedes, program_id in db.execute(
                    'SELECT id, document, kind, supersedes, program_id FROM records ORDER BY rowid'):
                doc = _document(document, f'record {rid}')
                records.append(dict(id=rid, kind=kind, supersedes=supersedes, program_id=program_id,
                                    actor_id=doc.get('actor_id'), created_wall=doc.get('created_wall'),
                                    text=doc.get('text'), data=doc.get('data'),
                                    applicability=doc.get('applicability'),
                                    supports=supports.get(rid, []), sources=sources_of.get(rid, [])))
            programs = []
            for pid, document, parent in db.execute('SELECT id, document, parent_id FROM programs ORDER BY rowid'):
                doc = _document(document, f'program {pid}')
                programs.append(dict(id=pid, parent_id=parent, actor_id=doc.get('actor_id'),
                                     created_wall=doc.get('created_wall'), reason=doc.get('reason'),
                                     code=doc.get('code'), record_ids=doc.get('record_ids', []),
                                     source_ids=doc.get('source_ids', [])))
            sources = [dict(id=sid, metadata=_document(metadata, f'source {sid}'), has_png=bool(has))
                       for sid, metadata, has in db.execute(
                           'SELECT id, metadata, png IS NOT NULL FROM sources ORDER BY rowid')]
        except sqlite3.Error as exc:
            raise StoreError(f'{path}: {exc}') from exc
    return dict(schema=SCHEMA, records=records, programs=programs, sources=sources)
