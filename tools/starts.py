"""Copy, install and retire reusable starts from the sealed seven-day lineage.

Reuse evidence's manifest reader, file inventory, streaming hash and seal operation.
The small remaining lifecycle belongs to development runs (R-SAVE-LOSS and
R-EVIDENCE-LOSS); it neither opens a player database nor edits a run package.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from harness.prepared_app import game_lock
from tools import evidence

SCHEMA = 'start-manifest/1'
STUDY = '397-seven-day'
PLAYER_STORE = 'player-memory-sd1.sqlite3'


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def descriptive_name(name: str) -> str:
    if not evidence.STUDY.fullmatch(name) or not any(c.isalpha() for c in name):
        raise ValueError('name must be descriptive lower-case letters, digits and hyphens')
    return name


def write_json(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def inventory(directory: Path) -> dict[str, str]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f'{directory}: expected a directory, not a link')
    return {p: evidence.file_sha256(directory / p) for p in evidence.listing(directory)}


def check_files(directory: Path, expected: dict[str, str]) -> None:
    actual = inventory(directory)
    missing, extra = set(expected) - set(actual), set(actual) - set(expected)
    if missing or extra:
        raise ValueError(f'{directory}: missing {sorted(missing)}, extra {sorted(extra)}')
    changed = [p for p in expected if actual[p] != expected[p]]
    if changed:
        raise ValueError(f'{directory}: changed files {changed}')


def copy_tree(source: Path, target: Path) -> None:
    # listing rejects links/special files before copytree can follow them. Copies
    # need write permission for subsequent ordinary play, unlike sealed sources.
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f'{source}: expected a directory, not a link')
    evidence.listing(source)
    shutil.copytree(source, target, copy_function=shutil.copyfile)
    evidence._writable(target)


def refuse_game(userdir: Path) -> None:
    """Also catch a manually launched game that did not acquire the shared lock."""
    result = subprocess.run(['ps', '-axo', 'pid=,args='], capture_output=True, text=True,
                            check=True, timeout=10)
    for line in result.stdout.splitlines():
        if not re.search(r'(?:^|[/\s])cataclysm(?:-tiles)?(?:\s|$)', line):
            continue
        if re.search(r'--userdir(?:=|\s+)[\"\']?' + re.escape(str(userdir.resolve()))
                     + r'/?(?:[\"\'\s]|$)', line):
            raise ValueError(f'game is running for {userdir}: {line.strip()}')


class Starts:
    def __init__(self, *, root: Path, store: Path, manifests: Path) -> None:
        self.root, self.store, self.manifests = root, store, manifests
        self.runtime = root / '.runtime'
        self.starts = self.runtime / 'starts'
        self.user = self.runtime / 'user'
        self.archive = self.runtime / 'archive'
        self.installed = self.starts / 'installed.json'

    @contextmanager
    def idle_game(self):
        with game_lock(self.runtime):
            refuse_game(self.user)
            yield

    def source_manifest(self) -> tuple[dict[str, str], str]:
        path = self.manifests / f'{STUDY}.sha256'
        entry = evidence.read_index(self.manifests)['studies'][STUDY]
        digest = evidence.file_sha256(path)
        if entry['availability'] != 'present' or digest != entry['manifest_sha256']:
            raise ValueError('source study is unavailable or its manifest has changed')
        entries = evidence.read_manifest(path)
        selected = {p: h for p, h in entries.items() if p.startswith('user/') or p == PLAYER_STORE}
        if PLAYER_STORE not in selected or not any(p.startswith('user/save/') for p in selected):
            raise ValueError('source study does not contain its saved game and player store')
        return selected, digest

    def payload(self, directory: Path) -> dict[str, str]:
        actual = {'user/' + p: h for p, h in inventory(directory / 'user').items()}
        # Include sidecars or other unexpected entries alongside the source DB.
        for p in directory.glob(PLAYER_STORE + '*'):
            if p.is_symlink() or not p.is_file():
                raise ValueError(f'{p}: expected a regular file')
            actual[p.name] = evidence.file_sha256(p)
        return actual

    def check_payload(self, directory: Path, expected: dict[str, str]) -> None:
        actual = self.payload(directory)
        if actual != expected:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            changed = sorted(p for p in set(actual) & set(expected) if actual[p] != expected[p])
            raise ValueError(f'{directory}: missing {missing}, extra {extra}, changed {changed}')

    def describe(self, name: str) -> dict:
        directory = self.starts / descriptive_name(name)
        path = directory / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        expected, source_hash = self.source_manifest()
        if (manifest['schema'] != SCHEMA or manifest['name'] != name or manifest['lineage'] != 397
                or manifest['source_study'] != STUDY or manifest['source_manifest_sha256'] != source_hash
                or manifest['files'] != expected or manifest['player_store'] != self.player_store(name)
                or manifest['held_out'] is not False):
            raise ValueError(f'{path}: unsupported or changed start manifest')
        self.check_payload(directory, expected)
        return dict(name=name, manifest_sha256=evidence.file_sha256(path),
                    player_store=str(self.root / manifest['player_store']), directory=str(directory))

    def player_store(self, name: str) -> str:
        return f'.runtime/starts/{name}/work/{PLAYER_STORE}'

    def create(self, name: str) -> dict:
        directory = self.starts / descriptive_name(name)
        if directory.exists():
            raise ValueError(f'{name}: start already exists')
        expected, source_hash = self.source_manifest()
        source = self.store / STUDY
        self.check_payload(source, expected)
        self.starts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.creating-', dir=self.starts) as temporary:
            target = Path(temporary) / name
            target.mkdir()
            copy_tree(source / 'user', target / 'user')
            shutil.copyfile(source / PLAYER_STORE, target / PLAYER_STORE)
            self.check_payload(target, expected)
            write_json(target / 'manifest.json', dict(schema=SCHEMA, name=name, lineage=397,
                       source_study=STUDY, source_manifest_sha256=source_hash, files=expected,
                       created=timestamp(), player_store=self.player_store(name), held_out=False))
            target.rename(directory)
        return self.describe(name)

    def archive_userdir(self) -> Path | None:
        if not self.user.exists():
            return None
        expected = inventory(self.user)
        target = self.archive / ('userdir-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        target.mkdir(parents=True)
        copy_tree(self.user, target / 'user')
        check_files(target / 'user', expected)
        check_files(self.user, expected)
        write_json(target / 'manifest.json', dict(schema='userdir-archive/1', created=timestamp(), files=expected))
        return target

    def active(self) -> dict | None:
        return json.loads(self.installed.read_text(encoding='utf-8')) if self.installed.exists() else None

    def install(self, name: str) -> dict:
        with self.idle_game():
            if self.active():
                raise ValueError('dispose the installed start before installing another')
            description = self.describe(name)
            directory = self.starts / name
            work = directory / 'work'
            if work.exists():
                raise ValueError(f'{work}: working outputs already exist')
            # Prepare the replacement before touching the current userdir.
            with tempfile.TemporaryDirectory(prefix='.installing-', dir=self.starts) as temporary:
                staged = Path(temporary) / 'user'
                copy_tree(directory / 'user', staged)
                check_files(staged, inventory(directory / 'user'))
                archive = self.archive_userdir()
                work.mkdir()
                shutil.copyfile(directory / PLAYER_STORE, work / PLAYER_STORE)
                if evidence.file_sha256(work / PLAYER_STORE) != evidence.file_sha256(directory / PLAYER_STORE):
                    raise ValueError('working player store copy changed')
                receipt = description | dict(archive=str(archive) if archive else None, installed=timestamp())
                write_json(self.installed, receipt)
                # Archive is complete and verified before this removal.
                if self.user.exists():
                    shutil.rmtree(self.user)
                staged.rename(self.user)
            return receipt

    def restore_userdir(self, archive: str) -> dict:
        with self.idle_game():
            if self.active():
                raise ValueError('dispose the installed start before restoring a userdir')
            target = Path(archive)
            if not target.is_absolute():
                target = self.archive / target
            target = target.resolve()
            if target.parent != self.archive.resolve() or target.is_symlink():
                raise ValueError('archive must be a userdir archive in the project archive directory')
            manifest = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
            if manifest['schema'] != 'userdir-archive/1':
                raise ValueError('unsupported userdir archive schema')
            check_files(target / 'user', manifest['files'])
            self.starts.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.restoring-', dir=self.starts) as temporary:
                staged = Path(temporary) / 'user'
                copy_tree(target / 'user', staged)
                check_files(staged, manifest['files'])
                displaced = self.archive_userdir()
                if self.user.exists():
                    shutil.rmtree(self.user)
                staged.rename(self.user)
            return dict(restored=str(target), userdir=str(self.user), archive=str(displaced) if displaced else None)

    def dispose(self, name: str, study: str, cited_by: list[str], note: str) -> dict:
        with self.idle_game():
            description = self.describe(name)
            directory = self.starts / name
            active = self.active()
            installed = active is not None and active['name'] == name
            sources = [('start', directory, directory.relative_to(self.root).as_posix())]
            if installed:
                sources += [('user', self.user, self.user.relative_to(self.root).as_posix())]
            # Save the installation receipt with the outputs, including archive location.
            if installed and not (directory / 'installation.json').exists():
                shutil.copyfile(self.installed, directory / 'installation.json')
            expected = {f'{prefix}/{p}': h for prefix, path, _ in sources for p, h in inventory(path).items()}
            entry = evidence.seal(study, sources, cited_by,
                                  f'Copied lineage 397 is no longer held out. Start {name}; '
                                  f'manifest {description["manifest_sha256"]}. {note}',
                                  store=self.store, manifests=self.manifests)
            # seal intentionally excludes locks/caches. Never delete a skipped file's
            # only copy: the exact path/hash comparison must succeed first.
            check_files(self.store / study, expected)
            for prefix, path, _ in sources:
                check_files(path, {p[len(prefix) + 1:]: h for p, h in expected.items() if p.startswith(prefix + '/')})
            if installed:
                shutil.rmtree(self.user)
                self.installed.unlink()
            shutil.rmtree(directory)
            return dict(name=name, sealed=study, manifest_sha256=entry['manifest_sha256'],
                        archive=active['archive'] if installed else None)

    def list(self) -> list[dict]:
        if not self.starts.exists():
            return []
        return [self.describe(p.name) for p in sorted(self.starts.iterdir())
                if p.is_dir() and not p.name.startswith('.')]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('create', 'install'):
        commands.add_parser(command).add_argument('name')
    commands.add_parser('restore-userdir').add_argument('archive')
    disposing = commands.add_parser('dispose')
    disposing.add_argument('name')
    disposing.add_argument('--seal', required=True, dest='study')
    disposing.add_argument('--cited-by', required=True, action='append')
    disposing.add_argument('--note', default='')
    commands.add_parser('list')
    args = parser.parse_args(argv)
    try:
        store = evidence.default_store()
        manager = Starts(root=store.parent.parent, store=store, manifests=evidence.MANIFESTS)
        if args.command == 'create':
            result = manager.create(args.name)
        elif args.command == 'install':
            result = manager.install(args.name)
        elif args.command == 'restore-userdir':
            result = manager.restore_userdir(args.archive)
        elif args.command == 'dispose':
            result = manager.dispose(args.name, args.study, args.cited_by, args.note)
        else:
            result = manager.list()
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'Starts: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
