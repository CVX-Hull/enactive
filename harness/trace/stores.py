"""Open sealed SQLite evidence without writing beside it (#452)."""
from __future__ import annotations

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3


class SealedStoreError(ValueError):
    """A sealed store is missing or cannot be read completely."""


@contextmanager
def sealed(path: Path):
    """An immutable read-only connection, closed on exit.

    SQLite's immutable mode ignores a write-ahead log, so a store sealed before its log was
    checkpointed would read incomplete. Such a store is refused, never read partially.
    """
    if not path.is_file():
        raise SealedStoreError(f'{path}: missing store')
    wal = path.with_name(path.name + '-wal')
    if wal.is_file() and wal.stat().st_size > 0:
        raise SealedStoreError(f'{path}: un-checkpointed write-ahead log; the sealed store would read incomplete')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        yield db
