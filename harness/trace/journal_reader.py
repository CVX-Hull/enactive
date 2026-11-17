"""Read public data from a sealed player journal without opening the live writer."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from .stores import SealedStoreError, sealed

SCHEMA = 'player-journal/1'
HINT_FIELDS = ('schema', 'id', 'actor_id', 'created_wall', 'text', 'source_ids', 'intent', 'cites')


class StoreError(ValueError):
    """The sealed journal is missing, incomplete or unsupported."""


def _object(text: str, where: str) -> dict:
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise StoreError(f'{where}: unreadable document') from exc
    if not isinstance(value, dict):
        raise StoreError(f'{where}: document is not an object')
    return value


def read(path: Path) -> dict:
    """Return source metadata, public calls and hints, never image bytes."""
    try:
        with sealed(path) as db:
            return read_connection(db, path)
    except SealedStoreError as exc:
        raise StoreError(str(exc)) from exc
    except sqlite3.Error as exc:
        raise StoreError(f'{path}: {exc}') from exc


def read_connection(db: sqlite3.Connection, path: Path) -> dict:
    """Decode current public rows; the caller owns its read-only connection."""
    schemas = [row[0] for row in db.execute('SELECT schema FROM metadata')]
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if schemas != [SCHEMA] or version != 1:
        raise StoreError(f'{path}: schema {schemas!r}, user_version {version}; expected {SCHEMA}, 1')
    sources = [dict(id=sid, metadata=_object(meta, f'source {sid}'))
               for sid, meta in db.execute('SELECT id, metadata FROM sources ORDER BY rowid')]
    calls = [dict(id=cid, actor_id=actor, tool=tool, arguments=_object(args, f'call {cid}'))
             for cid, actor, tool, args in db.execute('SELECT id, actor, tool, args FROM calls ORDER BY rowid')]
    hints = []
    for hid, document in db.execute('SELECT id, document FROM hints ORDER BY rowid'):
        doc = _object(document, f'hint {hid}')
        if doc.get('schema') != 'player-hint/1' or doc.get('id') != hid:
            raise StoreError(f'hint {hid}: unsupported schema or mismatched id')
        hints.append({key: doc[key] for key in HINT_FIELDS if key in doc})
    return dict(schema=SCHEMA, sources=sources, calls=calls, hints=hints)
