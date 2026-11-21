"""Open sealed SQLite evidence without writing beside it (#452)."""
from __future__ import annotations

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3


# The read admission between a curator snapshot reader and the custodian's close (#837, #850),
# all in the live run directory beside `session.sqlite3`. The lock exists only when a reader is
# configured; the custodian writes the marker in close-out and waits at most the hold bound for
# an exclusive lock, and a reader's whole hold of the shared lock fits that bound.
CURATOR_READ_LOCK = 'curator-read.lock'
STORE_CLOSING_MARKER = 'store-closing.json'
READ_HOLD_BOUND_SECONDS = 2.0


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
