"""Read-only, bounded projection of the curator runner's status file (`curator-runner-status/1`).

The runner (`harness/curator/runner.py`) owns the file and its format and replaces it whole at each poll and
at each session's start and end. This reader opens it for reading at request time, with no lock, and writes
nothing; nothing it returns reaches the curator. It shows what the curator has done since the actor's
delivered version, which `knowledge.py` projects separately: the two are never merged.

A value that is absent, the runner's `unknown`, or of a type this projection does not accept is `unknown`; it
is never shown as zero. A null the runner wrote (no session in flight, no stop reason, nothing confirmed yet)
stays null. Identifiers and text that look like paths or exceed the identifier limit are withheld whole with
`omitted_characters`, as the other curator readers do.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .curator import read_file
from .knowledge import ID_LIMIT, LIST_LIMIT

SCHEMA = 'curator-runner-status/1'
UNKNOWN = 'unknown'
STATES = ('polling', 'in-session', 'stopped', 'ended')


def _text(value):
    return value if isinstance(value, str) else UNKNOWN


def _count(value):
    return value if type(value) is int and value >= 0 else UNKNOWN


def _number(value):
    ok = (type(value) is int and value >= 0) or (type(value) is float and math.isfinite(value) and value >= 0)
    return value if ok else UNKNOWN


def _flag(value):
    return value if type(value) is bool else UNKNOWN


def _state(value):
    return value if value in STATES else UNKNOWN


WALLS = {'began': _number, 'ended': _number}
PLACE = {'actor': _text, 'step': _count, 'operation': _text, 'ordinal': _count}
POSITION = {**PLACE, 'read_wall': WALLS}
WINDOW = {'session': _text, 'actor': _text, 'first': _count, 'last': _count}
STAMP = {'session': _text, 'actor': _text, 'last_step': _count}  # a `curator-coverage/2` stamp
EXAMINED = {'label': _text, 'window': WINDOW, 'session_id': _text, 'outcome': _text, 'advanced': _flag,
            'started_wall': _number, 'ended_wall': _number}
RANGE = {'actor': _text, 'first': _count, 'last': _count}
STATUS = {
    'session': _text, 'state': _state, 'updated_wall': _number, 'stop_reason': _text, 'look_error': _text,
    'settings': {'trigger_steps': _count, 'ceiling_steps': _count, 'poll_seconds': _number, 'watch_seconds': _number},
    'position': POSITION, 'as_of': POSITION, 'after_last_read': _count,
    'snapshot': {'hold_seconds': _number, 'transaction_seconds': _number, 'staging_seconds': _number,
                 'read_wall': WALLS},
    'current': {'label': _text, 'window': WINDOW, 'started_wall': _number},
    'covered_prefix': {'end': PLACE, 'restore': {'version': _text, 'restored_from': _text, 'counted_through': _text}},
    'lag': _count, 'stamp_distance': _count, 'backlog': _count,
    'last_confirmed': {'version': _text, 'label': _text, 'window': WINDOW, 'coverage': STAMP},
    'latest_version': {'version': _text, 'coverage': STAMP},
    'failures': {'sessions': _count, 'snapshots': _count},
}


def _withheld(value: object) -> bool:
    return isinstance(value, str) and (len(value) > ID_LIMIT or '/' in value or '\\' in value)


def _project(value, kind):
    """One value by its kind: a projector for a scalar, a dict of kinds for an object."""
    if value is None or value == UNKNOWN:
        return value
    if not isinstance(kind, dict):
        return kind(value)
    if not isinstance(value, dict):
        return UNKNOWN
    out, omitted = {}, {}
    for key, sub in kind.items():
        item = value.get(key, UNKNOWN)
        if _withheld(item):
            omitted[key], out[key] = len(item), None
        else:
            out[key] = _project(item, sub)
    if omitted:
        out['omitted_characters'] = omitted
    return out


def _rows(value, kind, *, last: bool) -> dict:
    """A bounded list: at most `LIST_LIMIT` rows (the latest when `last`), with the total and how many were left out."""
    if value is None or not isinstance(value, list):
        return dict(items=None if value is None else UNKNOWN, total=0 if value is None else UNKNOWN, omitted=0)
    kept = value[-LIST_LIMIT:] if last else value[:LIST_LIMIT]
    return dict(items=[_project(row, kind) for row in kept], total=len(value), omitted=len(value) - len(kept))


def projection(document: dict) -> dict:
    out = _project(document, STATUS)
    out['examined'] = _rows(document.get('examined', UNKNOWN), EXAMINED, last=True)
    # Unexamined ranges are written only once the runner has stopped or ended; null before that.
    out['unexamined'] = _rows(document.get('unexamined', UNKNOWN), RANGE, last=False)
    unconfirmed = document.get('unconfirmed', UNKNOWN)
    out['unconfirmed'] = len(unconfirmed) if isinstance(unconfirmed, list) else UNKNOWN
    return out


def status(path: Path | None, now: float) -> dict:
    """The route's payload: `source_status`, the bytes read (`snapshot`), when this read happened and the projection."""
    if path is None:
        return dict(source_status='not_configured', snapshot=None, read_wall=now, status=None)
    state, snapshot, data = read_file(path)
    if state != 'available':
        return dict(source_status=state, snapshot=snapshot, read_wall=now, status=None)
    try:
        document = json.loads(data.decode('utf-8'))
    except (ValueError, UnicodeError, RecursionError):
        return dict(source_status='malformed', snapshot=snapshot, read_wall=now, status=None)
    if not isinstance(document, dict) or document.get('schema') != SCHEMA:
        return dict(source_status='unsupported', snapshot=snapshot, read_wall=now, status=None)
    return dict(source_status='available', snapshot=snapshot, read_wall=now, status=projection(document))
