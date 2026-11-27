"""Validate the ordered prefix of submissions in a staged curator workspace."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import check


def validate(workspace: Path, submission: str) -> dict:
    if Path(submission).name != submission or submission in ('', '.', '..'):
        raise ValueError('submission must be a directory name')
    knowledge = workspace / 'knowledge'
    context = json.loads((knowledge / 'validation-context.json').read_bytes())
    metadata = json.loads((knowledge / 'knowledge.json').read_bytes())
    if metadata['schema'] != 'curator-knowledge/5':
        raise ValueError('expected curator-knowledge/5')
    records = [json.loads(line) for line in (knowledge / 'facts.jsonl').read_text(encoding='utf-8').split('\n')
               if line.strip()]
    provenance = json.loads((knowledge / 'provenance.json').read_bytes())
    base = context['base_version']
    reserved_ids = set(context['reserved_ids'])
    reserved_state_keys = set(context.get('reserved_state_keys', ()))
    reservations = context['reserved_sessions']
    session_id = context.get('session_id', workspace.name)
    labels = context['session_labels']
    frames = context['window_frames']
    kind = context['session_kind']
    axes = set(context['declared_axes'])
    if (not check.VERSION.fullmatch(base) or kind not in check.SESSION_KINDS
            or not all(isinstance(value, dict) for value in (reservations, labels, frames))
            or set(reservations) != set(check.empty_reservations())):
        raise ValueError('invalid validation context')
    check.validate_snapshot(records, provenance, metadata['game'], base)
    folder = os.open(workspace / 'submissions', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return _prefix(folder, submission, records, provenance, metadata['game'], base,
                       reserved_ids, reserved_state_keys, reservations, session_id, labels, frames, kind, axes)
    finally:
        os.close(folder)


def _prefix(folder: int, submission: str, records: list, provenance: dict, game: str, base: str,
            reserved_ids: set, reserved_state_keys: set, reservations: dict, session_id: str,
            labels: dict, frames: dict, kind: str, axes: set) -> dict:
    with os.scandir(folder) as entries:
        directories = sorted(entry.name for entry in entries
                             if entry.is_dir(follow_symlinks=False) or entry.is_symlink())
    prefix = []
    for name in directories:
        data, diagnostics, digest = check.read_submission(name, dir_fd=folder)
        candidate = None
        if not diagnostics:
            candidate, diagnostics = check.evaluate(
                data, base_records=records, base_provenance=provenance, game=game,
                base_version=base, reserved_ids=reserved_ids, reserved_sessions=reservations, session_id=session_id,
                window_frames=frames, session_kind=kind, session_labels=labels, declared_axes=axes,
                reserved_state_keys=reserved_state_keys)
        row = dict(id=name, path=f'submissions/{name}/submission.json',
                   sha256=digest, status='passed' if candidate else 'rejected',
                   base_version=base, candidate_version=candidate.version if candidate else None,
                   diagnostics=diagnostics, scope_changes=candidate.scope_changes if candidate else [])
        prefix.append(row)
        if name == submission:
            return dict(ok=candidate is not None, all_passed=all(r['status'] == 'passed' for r in prefix),
                        submission=submission, prefix=prefix, diagnostics=diagnostics, scope_changes=row['scope_changes'])
        if candidate:
            records, provenance, reservations = candidate.records, candidate.provenance, candidate.reservations
            reserved_ids.update(check.owner(record) for record in records)
            reserved_state_keys.update(check.state_keys(records))
            base = candidate.version
    raise ValueError(f'submission {submission!r} is missing')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--submission', required=True)
    args = parser.parse_args()
    try:
        result = validate(args.workspace, args.submission)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
