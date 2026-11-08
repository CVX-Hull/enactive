"""Container manifests and sidecar indexes over sealed evidence (ADR 009 D17; #452).

One manifest shape, `container-manifest/1`, describes every container kind. It records
identity, kind, owner role, inputs and pinned versions, budgets, lifecycle state, provenance
and retention. Sealed directories are never rewritten: their manifests live in a separate
index (`data/containers/<study>.json`), generated from the sealed files and checkable
against them.

  python -m harness.trace.sidecar <evidence-study-dir> --study NAME --out data/containers/NAME.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

SCHEMA = 'container-manifest/1'
INDEX_SCHEMA = 'container-index/1'
KINDS = {
    'actor-session': ('sealed',),
    'curator-session': ('created', 'active', 'closed', 'sealed', 'aborted'),
    'submission': ('proposed', 'gated', 'published', 'rejected'),
    'draft': ('open', 'stale', 'promoted', 'abandoned'),
}
FIELDS = ('schema', 'id', 'kind', 'owner_role', 'inputs', 'pinned', 'budgets', 'lifecycle', 'provenance',
          'retention')


class ManifestError(ValueError):
    """A manifest does not follow container-manifest/1."""


def validate(manifest: dict) -> dict:
    if not isinstance(manifest, dict) or tuple(sorted(manifest)) != tuple(sorted(FIELDS)):
        raise ManifestError(f'manifest fields must be exactly {FIELDS}')
    if manifest['schema'] != SCHEMA:
        raise ManifestError(f'unsupported manifest schema {manifest["schema"]!r}')
    if manifest['kind'] not in KINDS:
        raise ManifestError(f'unknown container kind {manifest["kind"]!r}')
    state = manifest['lifecycle'].get('state') if isinstance(manifest['lifecycle'], dict) else None
    if state not in KINDS[manifest['kind']]:
        raise ManifestError(f'{manifest["kind"]} cannot be in state {state!r}')
    if not isinstance(manifest['id'], str) or not manifest['id']:
        raise ManifestError('manifest needs an id')
    for name in ('inputs', 'pinned', 'budgets', 'provenance', 'retention'):
        if not isinstance(manifest[name], dict):
            raise ManifestError(f'{name} must be an object')
    return manifest


def _session_id(path: Path) -> str:
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        return json.loads(dict(db.execute('SELECT key, value FROM metadata'))['session'])


def actor_sessions(study_dir: Path, study: str) -> list[dict]:
    """Sidecar manifests for every sealed actor session in an evidence study."""
    manifests = []
    for session in sorted((study_dir/'computer-sessions').iterdir()):
        if not (session/'session.sqlite3').is_file():
            continue
        actors = []
        for directory in sorted((session/'actors').iterdir()):
            frozen = json.loads((directory/'frozen.json').read_text()) if (directory/'frozen.json').exists() else {}
            # Digests of what the actor was given; never of files that hold custody or routes.
            given = {k: v for k, v in frozen.get('files', {}).items() if k in ('prompt.txt', 'context.txt')}
            actors.append(dict(directory=directory.name, actor_id=frozen.get('actor_id'), given_sha256=given))
        manifest_path = session/'manifest.json'
        package = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        limits = {k: package[k] for k in ('limits', 'wall_seconds', 'host_seconds', 'total_host_seconds',
                                          'max_http_attempts', 'max_hosts') if k in package}
        manifests.append(validate(dict(
            schema=SCHEMA, id=f'{study}/{session.name}', kind='actor-session', owner_role='actor',
            inputs=dict(session_id=_session_id(session/'session.sqlite3'), actors=actors),
            pinned=dict(source_commit=package.get('source_commit'),
                        run_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                        if manifest_path.is_file() else None),
            budgets=limits, lifecycle=dict(state='sealed'),
            provenance=dict(evidence_study=study, path=f'computer-sessions/{session.name}'),
            retention=dict(policy='evidence', note='sealed; described by this sidecar, never rewritten'))))
    return manifests


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('study_dir', type=Path)
    parser.add_argument('--study', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    index = dict(schema=INDEX_SCHEMA, study=args.study, containers=actor_sessions(args.study_dir, args.study))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=1, sort_keys=True) + '\n')
    print(f'{args.out}: {len(index["containers"])} containers')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
