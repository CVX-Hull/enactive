"""Read-only, bounded projection of the curator runner's status file (current /2 and archived /1).

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

from .catalog import ID_LIMIT, LIST_LIMIT
from .curator import read_file, read_rooted
from .telemetry import usd

SCHEMA = 'curator-runner-status/2'
ARCHIVED_SCHEMA = 'curator-runner-status/1'
OWN = ('curator-runner', 'status.json')  # where the runner writes it in a run package
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
EXAMINED = {'session_kind': _text, 'label': _text, 'window': WINDOW, 'session_id': _text, 'outcome': _text, 'advanced': _flag,
            'started_wall': _number, 'ended_wall': _number}
RANGE = {'actor': _text, 'first': _count, 'last': _count}
STATUS = {
    'session': _text, 'state': _state, 'updated_wall': _number, 'stop_reason': _text, 'look_error': _text,
    'settings': {'trigger_steps': _count, 'ceiling_steps': _count, 'poll_seconds': _number, 'watch_seconds': _number},
    'position': POSITION, 'as_of': POSITION,
    'snapshot': {'hold_seconds': _number, 'transaction_seconds': _number, 'staging_seconds': _number,
                 'read_wall': WALLS},
    'current': {'session_kind': _text, 'label': _text, 'window': WINDOW, 'started_wall': _number},
    'covered_prefix': {'end': PLACE, 'restore': {'version': _text, 'restored_from': _text, 'counted_through': _text}},
    'lag': _count, 'stamp_distance': _count, 'backlog': _count,
    'last_confirmed': {'version': _text, 'label': _text, 'window': WINDOW, 'coverage': STAMP},
    'latest_version': {'version': _text, 'coverage': STAMP},
    'failures': {'sessions': _count, 'snapshots': _count},
}


def _money(value):
    return value if usd(value) is not None else UNKNOWN


def _share(value):
    amount = usd(value)
    return value if amount is not None and amount <= 1 else UNKNOWN


def _tier(value):
    return value if value in ('default', 'priority', 'flex') else UNKNOWN


LIMITS = {'cap_usd': _money, 'session_cap_usd': _money, 'service_tier': _tier, 'flex_deferral_limit': _count,
          'hygiene': {'enabled': _flag, 'min_windows': _count, 'max_unexamined_steps': _count,
                      'pass_cap_usd': _money, 'max_spend_share': _share, 'max_requests': _count,
                      'wall_seconds': _number, 'host_wall_seconds': _number, 'max_consecutive_failures': _count}}


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
        item = value.get(key, None if key == 'session_kind' else UNKNOWN)
        if _withheld(item):
            omitted[key], out[key] = len(item), None
        else:
            out[key] = _project(item, sub)
    if omitted:
        out['omitted_characters'] = omitted
    return out


def _rows(value, kind, *, last: bool) -> dict:
    """A bounded list: at most `LIST_LIMIT` rows (the latest when `last`), with the total and how many were left out.
    A null list (not provided by the runner) keeps null counts; anything else that is not a list is unknown. A row
    that is not an object is a row whose every field is unknown."""
    if value is None:
        return dict(items=None, total=None, omitted=None)
    if not isinstance(value, list):
        return dict(items=UNKNOWN, total=UNKNOWN, omitted=UNKNOWN)
    kept = value[-LIST_LIMIT:] if last else value[:LIST_LIMIT]
    return dict(items=[_project(row if isinstance(row, dict) else {}, kind) for row in kept], total=len(value),
                omitted=len(value) - len(kept))


def _baselines(document: dict) -> dict:
    """Each version's `baseline` flag, from the status file's own list of versions."""
    versions = document.get('versions')
    if not isinstance(versions, list):
        return {}
    return {row['version']: row.get('baseline') for row in versions
            if isinstance(row, dict) and isinstance(row.get('version'), str)}


def projection(document: dict) -> dict:
    current = document['schema'] == SCHEMA
    shape = dict(STATUS, failures=dict(STATUS['failures'], hygiene=_count, flex_deferrals=_count))
    out = _project(document, shape)
    out['status_schema'] = document['schema']
    out['limits'] = _project(document.get('limits'), LIMITS) if current else None
    if not isinstance(out['failures'], dict):
        out['failures'] = dict.fromkeys(shape['failures'], out['failures'])
    if not current:
        out['failures'].update(hygiene=None, flex_deferrals=None)
    # The runner writes only `unknown` here: steps finished after its last read are never known to it.
    out['after_last_read'] = UNKNOWN
    baselines = _baselines(document)
    for key in ('last_confirmed', 'latest_version'):
        if isinstance(out[key], dict):
            out[key]['baseline'] = _flag(baselines.get(out[key]['version'], UNKNOWN))
    out['examined'] = _rows(document.get('examined', UNKNOWN), EXAMINED, last=True)
    # Unexamined ranges are written only once the runner has stopped or ended; null before that.
    out['unexamined'] = _rows(document.get('unexamined', UNKNOWN), RANGE, last=False)
    unconfirmed = document.get('unconfirmed', UNKNOWN)
    out['unconfirmed'] = len(unconfirmed) if isinstance(unconfirmed, list) else UNKNOWN
    return out


def status(path: Path | None, now: float, *, examined_ids: set[str] | None = None) -> dict:
    """The payload of the configured status file. One in a run package's own place is read from that package's root."""
    if path is None:
        return dict(source_status='not_configured', snapshot=None, read_wall=now, status=None)
    if path.parts[-2:] == OWN:
        return run_status(path.parent.parent, now, examined_ids=examined_ids)
    return payload(*read_file(path), now, examined_ids=examined_ids)


def run_status(run_dir: Path, now: float, *, examined_ids: set[str] | None = None) -> dict:
    """The payload of a run package's own status file."""
    return payload(*read_rooted(run_dir, *OWN), now, examined_ids=examined_ids)


def payload(state: str, snapshot: dict | None, data: bytes | None, now: float, *,
            examined_ids: set[str] | None = None) -> dict:
    """The route's payload: `source_status`, the bytes read (`snapshot`), when this read happened and the projection."""
    if state != 'available' or data is None:
        return dict(source_status=state, snapshot=snapshot, read_wall=now, status=None)
    try:
        document = json.loads(data.decode('utf-8'))
    except (ValueError, UnicodeError, RecursionError):
        return dict(source_status='malformed', snapshot=snapshot, read_wall=now, status=None)
    if not isinstance(document, dict) or document.get('schema') not in (SCHEMA, ARCHIVED_SCHEMA):
        return dict(source_status='unsupported', snapshot=snapshot, read_wall=now, status=None)
    examined = document.get('examined')
    if examined_ids is not None and isinstance(examined, list):
        examined_ids.update(value for row in examined if isinstance(row, dict)
                            if isinstance(value := row.get('session_id'), str) and value not in ('', UNKNOWN)
                            and not _withheld(value))
    return dict(source_status='available', snapshot=snapshot, read_wall=now, status=projection(document))
