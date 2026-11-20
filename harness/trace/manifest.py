"""The current projection manifest shared by the writer and trace readers."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA = 'trace-projection/3'


class ProjectionError(ValueError):
    """A trace is unsupported, incomplete, inconsistent or would carry a secret."""


def require_current(manifest: object) -> None:
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA:
        raise ProjectionError(f'Expected a {SCHEMA} manifest')


def read(trace: Path) -> dict:
    path = trace/'manifest.json'
    if path.is_symlink() or not path.is_file():
        raise ProjectionError(f'{path}: expected a regular projection manifest')
    try:
        manifest = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ProjectionError(f'{path}: unreadable projection manifest') from exc
    require_current(manifest)
    return manifest
