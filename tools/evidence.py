#!/usr/bin/env python3
"""Retained run evidence: a project-local, read-only store with tracked SHA-256 manifests.

Raw run evidence (packages, frames, traces, records, memory stores, archived userdirs) lives under the
git-ignored `.runtime/evidence/<study>/`. Git tracks `data/evidence/<study>.sha256`, one
`<sha256>  <relative path>` line per file in `shasum -a 256` format (so `shasum -a 256 -c` verifies it with
stock tools), and `data/evidence/index.json` (`evidence-index/1`): per study the citing records, file count,
bytes, manifest hash and visibility. See docs/operations/evidence-cleanup.md.

seal copies a study's files into the store once, checks every copy against its source by hash, writes the
manifest and index entry, then makes the study read-only; a sealed study is never rewritten. verify checks
every study whose store is present against its manifest (file set and bytes; hashes with --full) and reports
studies absent from this checkout, which is normal for a fresh clone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / '.runtime' / 'evidence'
MANIFESTS = ROOT / 'data' / 'evidence'
SCHEMA = 'evidence-index/1'
# Never evidence: reproducible game builds, locks, credentials, environments and caches.
EXCLUDE = frozenset({'Cataclysm.app', 'bridge', 'credentials.json', '.venv', '__pycache__', 'node_modules', '.DS_Store'})
STUDY = re.compile(r'[a-z0-9][a-z0-9-]*')


class EvidenceError(ValueError):
    pass


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def listing(root: Path) -> list[str]:
    """Every regular file below root as a sorted POSIX path; links and special files are refused."""
    found = []
    for directory, names, files in os.walk(root):
        for name in names + files:
            path = Path(directory) / name
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise EvidenceError(f'{path}: links and special files are not evidence')
        found += [(Path(directory) / name).relative_to(root).as_posix() for name in files]
    return sorted(found)


def read_index(directory: Path = MANIFESTS) -> dict:
    path = directory / 'index.json'
    if not path.is_file():
        return {'schema': SCHEMA, 'studies': {}}
    index = json.loads(path.read_text())
    if not isinstance(index, dict) or index.get('schema') != SCHEMA or not isinstance(index.get('studies'), dict):
        raise EvidenceError(f'{path.name}: unsupported index version {index.get("schema") if isinstance(index, dict) else None!r}')
    return index


def read_manifest(path: Path) -> dict[str, str]:
    entries = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        match = re.fullmatch(r'([0-9a-f]{64})  (\S.*)', line)
        if not match or match.group(2) in entries or match.group(2).startswith('/') or '..' in match.group(2).split('/'):
            raise EvidenceError(f'{path.name}:{number}: not a relative shasum line, or a repeated path')
        entries[match.group(2)] = match.group(1)
    return entries


def _copy(source: Path, target: Path) -> None:
    if source.name in EXCLUDE:
        return
    if source.is_symlink():
        raise EvidenceError(f'{source}: links are not evidence')
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir()):
            _copy(child, target / child.name)
    elif source.is_file():
        if target.exists():
            raise EvidenceError(f'{target}: two sources map to the same path')
        shutil.copy2(source, target)
        if sha256(source) != sha256(target):
            raise EvidenceError(f'{source}: copy does not match its source')
    else:
        raise EvidenceError(f'{source}: special files are not evidence')


def seal(study: str, sources: list[tuple[str, Path]], cited_by: list[str], note: str, *,
         store: Path = STORE, manifests: Path = MANIFESTS) -> dict:
    """Copy each source directory's children (or a single file) into store/study/SUBDIR, then seal it."""
    if not STUDY.fullmatch(study):
        raise EvidenceError(f'study name {study!r} must be lower-case letters, digits and hyphens')
    index = read_index(manifests)
    target = store / study
    if study in index['studies'] or target.exists() or (manifests / f'{study}.sha256').exists():
        raise EvidenceError(f'{study} is already sealed; a sealed study is never rewritten')
    missing = [record for record in cited_by if not (ROOT / record).is_file()]
    if missing or not cited_by:
        raise EvidenceError(f'cited records must exist: {missing or "none given"}')
    try:
        for subdir, source in sources:
            destination = target if subdir == '.' else target / subdir
            if source.is_dir():
                for child in sorted(source.iterdir()):
                    _copy(child, destination / child.name)
            else:
                destination.mkdir(parents=True, exist_ok=True)
                _copy(source, destination / source.name)
        paths = listing(target)
        if not paths:
            raise EvidenceError(f'{study}: no files to seal')
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    text = ''.join(f'{sha256(target / path)}  {path}\n' for path in paths)
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / f'{study}.sha256').write_text(text)
    entry = dict(cited_by=sorted(cited_by), files=len(paths), bytes=sum((target / p).stat().st_size for p in paths),
                 manifest_sha256=hashlib.sha256(text.encode()).hexdigest(), visibility='private', note=note)
    index['studies'][study] = entry
    (manifests / 'index.json').write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')
    for directory, names, files in os.walk(target, topdown=False):
        for name in files:
            (Path(directory) / name).chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        Path(directory).chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    return entry


def verify(*, full: bool, store: Path = STORE, manifests: Path = MANIFESTS) -> tuple[list[str], list[str]]:
    """(errors, notes). Each indexed study's manifest must match its recorded hash; a present store must hold
    exactly the manifest's files with the indexed bytes, and with --full every file's hash."""
    errors, notes = [], []
    index = read_index(manifests)
    stray = {p.stem for p in manifests.glob('*.sha256')} - set(index['studies'])
    errors += [f'{name}.sha256 has no index entry' for name in sorted(stray)]
    for study, entry in sorted(index['studies'].items()):
        path = manifests / f'{study}.sha256'
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['manifest_sha256']:
            errors.append(f'{study}: manifest missing or changed since sealing')
            continue
        manifest = read_manifest(path)
        target = store / study
        if not target.is_dir():
            notes.append(f'{study}: store not present on this checkout ({entry["files"]} files)')
            continue
        present = listing(target)
        extra, absent = sorted(set(present) - set(manifest)), sorted(set(manifest) - set(present))
        if extra or absent:
            errors.append(f'{study}: {len(absent)} files missing, {len(extra)} unexpected '
                          f'(first: {(absent or extra)[0]})')
            continue
        total = sum((target / p).stat().st_size for p in present)
        if total != entry['bytes'] or len(present) != entry['files']:
            errors.append(f'{study}: {len(present)} files / {total} bytes, sealed {entry["files"]} / {entry["bytes"]}')
            continue
        if full:
            changed = [p for p in present if sha256(target / p) != manifest[p]]
            if changed:
                errors.append(f'{study}: {len(changed)} files changed (first: {changed[0]})')
                continue
        notes.append(f'{study}: {entry["files"]} files verified ({"hashes" if full else "set and bytes"})')
    return errors, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    sealing = commands.add_parser('seal', help='copy a study into the store once and seal it')
    sealing.add_argument('study')
    sealing.add_argument('--from', dest='sources', action='append', required=True, metavar='SUBDIR=PATH',
                         help="copy PATH's children (or the file PATH) into the study's SUBDIR ('.' for its root)")
    sealing.add_argument('--cited-by', action='append', required=True, help='a tracked record citing this evidence')
    sealing.add_argument('--note', required=True)
    checking = commands.add_parser('verify', help='check present stores against their manifests')
    checking.add_argument('--full', action='store_true', help='hash every file')
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == 'seal':
            sources = []
            for item in arguments.sources:
                subdir, separator, path = item.partition('=')
                if not separator or not subdir or not Path(path).exists():
                    raise EvidenceError(f'--from expects SUBDIR=EXISTING_PATH, got {item!r}')
                sources.append((subdir, Path(path).resolve()))
            print(json.dumps(seal(arguments.study, sources, arguments.cited_by, arguments.note), sort_keys=True))
            return 0
        errors, notes = verify(full=arguments.full)
        for note in notes:
            print(f'Evidence: {note}')
        if errors:
            raise EvidenceError('\n'.join(errors))
        print('Evidence store and manifests: consistent.')
        return 0
    except (EvidenceError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f'Evidence: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
