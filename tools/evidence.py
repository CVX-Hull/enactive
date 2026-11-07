#!/usr/bin/env python3
"""Retained run evidence: a project-local, read-only store with tracked SHA-256 manifests.

Raw run evidence (packages, frames, traces, records, memory stores, userdirs) that a dated record cites is
sealed under the git-ignored `.runtime/evidence/<study>/`. Git tracks `data/evidence/<study>.sha256`, one
`<sha256>  <relative path>` line per file in `shasum -a 256` format (so `shasum -a 256 -c` verifies it with
stock tools), and `data/evidence/index.json` (`evidence-index/1`): per study the citing records, the origin
of each part, file count, bytes, manifest hash, visibility and availability. See
docs/operations/evidence-cleanup.md.

seal copies a study's files into the store once, refusing names the manifest format cannot hold, checks every
copy against its source by hash, writes the manifest and then the index entry, and clears write permission; a
failed seal leaves nothing behind, and a sealed study is never rewritten. verify checks every present study
against its manifest (file set and total bytes; every hash with --full). A study missing from a present store
is an error; a store root that is absent altogether (a fresh clone or CI) is reported as not present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / '.runtime' / 'evidence'
MANIFESTS = ROOT / 'data' / 'evidence'
SCHEMA = 'evidence-index/1'
# Never evidence, at any depth: reproducible game builds, credentials, environments and caches, plus locks.
EXCLUDE_NAMES = frozenset({'Cataclysm.app', 'credentials.json', '.env', '.venv', '__pycache__', 'node_modules',
                           '.DS_Store'})
EXCLUDE_SUFFIXES = ('.lock',)
STUDY = re.compile(r'[a-z0-9][a-z0-9-]*')
LINE = re.compile(r'([0-9a-f]{64})  ([^\x00-\x20\x7f\\][^\x00-\x1f\x7f\\]*)')


class EvidenceError(ValueError):
    pass


def excluded(name: str) -> bool:
    return name in EXCLUDE_NAMES or name.endswith(EXCLUDE_SUFFIXES)


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def listing(root: Path) -> list[str]:
    """Every regular file below root as a sorted POSIX path; links, special files and names the shasum line
    format cannot hold (newline, backslash, leading whitespace) are refused."""
    found = []
    for directory, names, files in os.walk(root):
        for name in names + files:
            path = Path(directory) / name
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise EvidenceError(f'{path}: links and special files are not evidence')
            if (name.splitlines() != [name] or '\\' in name or name != name.lstrip()
                    or any(ord(character) < 32 or ord(character) == 127 for character in name)):
                raise EvidenceError(f'{path}: the name cannot be written in a shasum manifest')
        found += [(Path(directory) / name).relative_to(root).as_posix() for name in files]
    return sorted(found)


def read_index(directory: Path = MANIFESTS) -> dict:
    path = directory / 'index.json'
    if not path.is_file():
        return {'schema': SCHEMA, 'studies': {}}
    index = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(index, dict) or index.get('schema') != SCHEMA or not isinstance(index.get('studies'), dict):
        raise EvidenceError(f'{path.name}: unsupported index version {index.get("schema") if isinstance(index, dict) else None!r}')
    return index


def read_manifest(path: Path) -> dict[str, str]:
    entries = {}
    text = path.read_bytes().decode('utf-8')
    if text and not text.endswith('\n'):
        raise EvidenceError(f'{path.name}: does not end with a newline')
    for number, line in enumerate(text.split('\n')[:-1] if text else [], 1):
        match = LINE.fullmatch(line)
        if (not match or match.group(2) in entries or match.group(2).startswith('/')
                or '..' in match.group(2).split('/') or match.group(2).splitlines() != [match.group(2)]):
            raise EvidenceError(f'{path.name}:{number}: not a relative shasum line, or a repeated path')
        entries[match.group(2)] = match.group(1)
    return entries


def _copy(source: Path, target: Path, skipped: list[str], origin: Path) -> None:
    if excluded(source.name):
        skipped.append(source.relative_to(origin).as_posix() or source.name)
        return
    if source.is_symlink():
        raise EvidenceError(f'{source}: links are not evidence')
    if source.is_dir():
        for child in sorted(source.iterdir()):
            _copy(child, target / child.name, skipped, origin)
    elif source.is_file():
        if target.exists():
            raise EvidenceError(f'{target}: two sources map to the same path')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha256(source) != sha256(target):
            raise EvidenceError(f'{source}: copy does not match its source')
    else:
        raise EvidenceError(f'{source}: special files are not evidence')


def _writable(root: Path) -> None:
    for directory, _, files in os.walk(root):
        Path(directory).chmod(Path(directory).stat().st_mode | 0o700)
        for name in files:
            (Path(directory) / name).chmod((Path(directory) / name).stat().st_mode | 0o200)


def _read_only(root: Path) -> None:
    for directory, _, files in os.walk(root, topdown=False):
        for name in files:
            path = Path(directory) / name
            path.chmod(path.stat().st_mode & ~0o222)
        Path(directory).chmod(Path(directory).stat().st_mode & ~0o222)


def seal(study: str, sources: list[tuple[str, Path, str]], cited_by: list[str], note: str, *,
         store: Path = STORE, manifests: Path = MANIFESTS) -> dict:
    """Copy each source's children (or the single file) into store/study/SUBDIR, then seal it. Each source is
    (SUBDIR, PATH, ORIGIN), where ORIGIN is a repository-relative description such as `.runtime/x@commit`."""
    if not STUDY.fullmatch(study):
        raise EvidenceError(f'study name {study!r} must be lower-case letters, digits and hyphens')
    index = read_index(manifests)
    target, manifest = store / study, manifests / f'{study}.sha256'
    if study in index['studies'] or target.exists() or manifest.exists():
        raise EvidenceError(f'{study} is already sealed, or a failed seal left files behind; a sealed study is never rewritten')
    missing = [record for record in cited_by if not (ROOT / record).is_file()]
    if missing or not cited_by:
        raise EvidenceError(f'cited records must exist: {missing or "none given"}')
    # The index records one origin per subdir; it is the only tracked provenance once originals are removed.
    origins: dict[str, str] = {}
    for subdir, _, origin in sources:
        if origins.setdefault(subdir, origin) != origin:
            raise EvidenceError(f'{subdir}: sources with different origins share this subdir; '
                                'give them their common folder as the origin, or separate subdirs')
    skipped: list[str] = []
    try:
        for subdir, source, _ in sources:
            if excluded(source.name):
                raise EvidenceError(f'{source}: an excluded name cannot be a source')
            destination = target if subdir == '.' else target / subdir
            if source.is_dir():
                for child in sorted(source.iterdir()):
                    _copy(child, destination / child.name, skipped, source)
            else:
                _copy(source, destination / source.name, skipped, source.parent)
        paths = listing(target) if target.is_dir() else []
        if not paths:
            raise EvidenceError(f'{study}: no files to seal')
        text = ''.join(f'{sha256(target / path)}  {path}\n' for path in paths)
        manifests.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(text.encode('utf-8'))
        entry = dict(cited_by=sorted(cited_by), files=len(paths),
                     bytes=sum((target / p).stat().st_size for p in paths),
                     manifest_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
                     sources=origins,
                     visibility='private', availability='present', note=note)
        index['studies'][study] = entry
        temporary = manifests / 'index.json.tmp'
        temporary.write_bytes((json.dumps(index, indent=2, sort_keys=True) + '\n').encode('utf-8'))
        os.replace(temporary, manifests / 'index.json')
    except BaseException:
        if target.exists():
            _writable(target)
            shutil.rmtree(target, ignore_errors=True)
        manifest.unlink(missing_ok=True)
        (manifests / 'index.json.tmp').unlink(missing_ok=True)
        raise
    _read_only(target)
    return entry | {'excluded': skipped}


def verify(*, full: bool, store: Path = STORE, manifests: Path = MANIFESTS,
           root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(errors, notes). Each indexed study's manifest must match its recorded hash and its citing records must
    exist; a present study must hold exactly the manifest's files with the indexed total bytes and no write
    permission, and with --full every file's hash."""
    errors, notes = [], []
    index = read_index(manifests)
    stray = {p.stem for p in manifests.glob('*.sha256')} - set(index['studies'])
    errors += [f'{name}.sha256 has no index entry' for name in sorted(stray)]
    for study, entry in sorted(index['studies'].items()):
        errors += [f'{study}: cited record {record} is missing' for record in entry['cited_by']
                   if not (root / record).is_file()]
        if entry.get('availability') == 'removed':
            notes.append(f'{study}: removed ({entry.get("removed", "no reason recorded")})')
            continue
        path = manifests / f'{study}.sha256'
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['manifest_sha256']:
            errors.append(f'{study}: manifest missing or changed since sealing')
            continue
        try:
            manifest = read_manifest(path)
        except EvidenceError as error:  # one bad manifest must not hide the other studies
            errors.append(f'{study}: {error}')
            continue
        target = store / study
        if not store.is_dir():
            notes.append(f'{study}: store not present on this checkout ({entry["files"]} files)')
            continue
        if not target.is_dir():
            errors.append(f'{study}: sealed evidence is missing from the store (the store is its only copy)')
            continue
        present = listing(target)
        extra, absent = sorted(set(present) - set(manifest)), sorted(set(manifest) - set(present))
        if extra or absent:
            errors.append(f'{study}: {len(absent)} files missing, {len(extra)} unexpected (first: {(absent or extra)[0]})')
            continue
        total = sum((target / p).stat().st_size for p in present)
        if total != entry['bytes'] or len(present) != entry['files']:
            errors.append(f'{study}: {len(present)} files / {total} bytes, sealed {entry["files"]} / {entry["bytes"]}')
            continue
        if any((target / p).stat().st_mode & 0o222 for p in present):
            errors.append(f'{study}: a sealed file has regained write permission')
            continue
        if full:
            changed = [p for p in present if sha256(target / p) != manifest[p]]
            if changed:
                errors.append(f'{study}: {len(changed)} files changed (first: {changed[0]})')
                continue
        notes.append(f'{study}: {entry["files"]} files verified ({"every hash" if full else "file set, total bytes, read-only"})')
    return errors, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    sealing = commands.add_parser('seal', help='copy a study into the store once and seal it')
    sealing.add_argument('study')
    sealing.add_argument('--from', dest='sources', action='append', required=True, metavar='SUBDIR=PATH@ORIGIN',
                         help="copy PATH's children (or the file PATH) into the study's SUBDIR ('.' for its root); "
                              'ORIGIN is a repository-relative description of where it came from, e.g. .runtime/x@abc1234')
    sealing.add_argument('--cited-by', action='append', required=True, help='a tracked record citing this evidence')
    sealing.add_argument('--note', required=True)
    checking = commands.add_parser('verify', help='check present studies against their manifests')
    checking.add_argument('--full', action='store_true', help='hash every file')
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == 'seal':
            sources = []
            for item in arguments.sources:
                subdir, separator, rest = item.partition('=')
                path, at, origin = rest.partition('@')
                if not separator or not subdir or not at or not origin or not Path(path).exists():
                    raise EvidenceError(f'--from expects SUBDIR=EXISTING_PATH@ORIGIN, got {item!r}')
                sources.append((subdir, Path(path).resolve(), origin))
            print(json.dumps(seal(arguments.study, sources, arguments.cited_by, arguments.note), sort_keys=True))
            return 0
        errors, notes = verify(full=arguments.full)
        for note in notes:
            print(f'Evidence: {note}')
        if errors:
            raise EvidenceError('\n'.join(errors))
        print('Evidence store and manifests: consistent.')
        return 0
    except (EvidenceError, OSError, KeyError, json.JSONDecodeError, UnicodeError) as error:
        print(f'Evidence: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
