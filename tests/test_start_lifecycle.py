"""Reusable starts protect R-SAVE-LOSS / R-EVIDENCE-LOSS with temporary roots only.

These are file lifecycle and process-exclusion tests, not game load evidence.
"""
from __future__ import annotations

import builtins
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from harness.prepared_app import game_lock
from tools import evidence, starts

NAME = 'seven-day-end-01'
CITED = ['docs/overview.md']


@pytest.fixture
def manager(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    source = tmp_path / 'source'
    (source / 'user' / 'save' / 'A world').mkdir(parents=True)
    (source / 'user' / 'save' / 'A world' / 'survivor.sav').write_bytes(b'final saved game')
    (source / 'user' / 'config').mkdir()
    (source / 'user' / 'config' / 'options.json').write_text('{}')
    (source / 'user' / 'empty').mkdir()
    (source / starts.PLAYER_STORE).write_bytes(b'player database bytes')
    store, manifests = root / '.runtime' / 'evidence', root / 'data' / 'evidence'
    evidence.seal(starts.STUDY, [('.', source, 'fixture')], CITED, 'fixture', store=store, manifests=manifests)
    manager = starts.Starts(root=root, store=store, manifests=manifests)
    # Avoid depending on the machine's process table; process parsing is exercised below.
    monkeypatch.setattr(starts, 'refuse_game', lambda userdir: None)
    return manager


def test_copy_matches_every_manifest_hash_and_never_opens_sealed_original_for_writing(manager, monkeypatch):
    source = manager.store / starts.STUDY
    before = starts.inventory(source)
    modes = {p: (source / p).stat().st_mode for p in before}
    original_open, path_open = builtins.open, Path.open
    reads = set()

    def assert_read_only(file, mode):
        if isinstance(file, (str, Path)) and Path(file).is_relative_to(source):
            assert not set(mode) & set('wax+'), (file, mode)
            reads.add(str(file))

    def checked_open(file, mode='r', *args, **kwargs):
        assert_read_only(file, mode)
        return original_open(file, mode, *args, **kwargs)

    def checked_path_open(path, mode='r', *args, **kwargs):
        assert_read_only(path, mode)
        return path_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', checked_open)
    monkeypatch.setattr(Path, 'open', checked_path_open)
    description = manager.create(NAME)
    target = manager.starts / NAME
    manifest = json.loads((target / 'manifest.json').read_text())
    assert manifest['schema'] == 'start-manifest/1'
    assert manifest['lineage'] == 397 and manifest['source_study'] == starts.STUDY
    assert manifest['source_manifest_sha256'] == evidence.file_sha256(manager.manifests / f'{starts.STUDY}.sha256')
    assert manifest['files'] == before
    assert manifest['held_out'] is False and manifest['created']
    assert description['manifest_sha256'] == evidence.file_sha256(target / 'manifest.json')
    assert description['player_store'] == str(manager.root / manager.player_store(NAME))
    assert manager.payload(target) == before and reads
    assert starts.inventory(source) == before
    assert {p: (source / p).stat().st_mode for p in before} == modes
    assert manager.list() == [description]
    assert not manager.user.exists() and not (target / 'work').exists()
    with pytest.raises(ValueError, match='already exists'):
        manager.create(NAME)


@pytest.mark.parametrize('damage', ['changed', 'missing', 'extra', 'database-sidecar'])
def test_refuses_changed_missing_extra_source_files(manager, damage):
    source = manager.store / starts.STUDY
    evidence._writable(source)  # damage only the temporary fixture
    save = source / 'user' / 'save' / 'A world' / 'survivor.sav'
    if damage == 'changed':
        save.write_bytes(b'damaged save')
    elif damage == 'missing':
        save.unlink()
    elif damage == 'extra':
        (save.parent / 'extra.sav').write_bytes(b'extra save')
    else:
        (source / (starts.PLAYER_STORE + '-wal')).write_bytes(b'unsealed state')
    with pytest.raises(ValueError, match='missing .*extra .*changed'):
        manager.create(NAME)
    assert not (manager.starts / NAME).exists()


def test_refuses_corrupted_copy_even_when_original_matches(manager, monkeypatch):
    original_copy = shutil.copyfile

    def corrupt(source, target, **kwargs):
        result = original_copy(source, target, **kwargs)
        if Path(target).name == starts.PLAYER_STORE:
            Path(target).write_bytes(b'bad copy')
        return result

    monkeypatch.setattr(shutil, 'copyfile', corrupt)
    with pytest.raises(ValueError, match='changed'):
        manager.create(NAME)
    assert not (manager.starts / NAME).exists()


def old_user(manager):
    (manager.user / 'save').mkdir(parents=True)
    (manager.user / 'save' / 'previous.sav').write_bytes(b'previous play')
    return starts.inventory(manager.user)


def test_install_archives_and_verifies_before_replacing_then_uses_writable_store(manager, monkeypatch):
    description = manager.create(NAME)
    previous = old_user(manager)
    rmtree = shutil.rmtree
    checked_removal = []

    def assert_archive_before_remove(path, *args, **kwargs):
        if Path(path) == manager.user:
            archives = list(manager.archive.glob('userdir-*'))
            assert len(archives) == 1
            starts.check_files(archives[0] / 'user', previous)
            assert (archives[0] / 'manifest.json').is_file()
            checked_removal.append(path)
        return rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, 'rmtree', assert_archive_before_remove)
    receipt = manager.install(NAME)
    assert checked_removal
    starts.check_files(Path(receipt['archive']) / 'user', previous)
    assert starts.inventory(manager.user) == starts.inventory(manager.starts / NAME / 'user')
    assert Path(description['player_store']).read_bytes() == (manager.starts / NAME / starts.PLAYER_STORE).read_bytes()
    Path(description['player_store']).write_bytes(b'ordinary working memory')
    assert (manager.user / 'save' / 'A world' / 'survivor.sav').stat().st_mode & 0o200
    manager.create('seven-day-end-02')
    with pytest.raises(ValueError, match='dispose'):
        manager.install('seven-day-end-02')


def test_bad_archive_copy_refuses_replacement_and_preserves_original(manager, monkeypatch):
    manager.create(NAME)
    previous = old_user(manager)
    copy = starts.copy_tree

    def damage_archive(source, target):
        copy(source, target)
        if target.parent.parent == manager.archive:
            (target / 'save' / 'previous.sav').write_bytes(b'corrupt archive')

    monkeypatch.setattr(starts, 'copy_tree', damage_archive)
    with pytest.raises(ValueError, match='changed'):
        manager.install(NAME)
    starts.check_files(manager.user, previous)
    assert not manager.installed.exists()


def test_shared_game_lock_refuses_install_restore_and_dispose(manager):
    manager.create(NAME)
    with game_lock(manager.runtime):
        for operation in (lambda: manager.install(NAME), lambda: manager.restore_userdir('userdir-example'),
                          lambda: manager.dispose(NAME, 'test-outputs', CITED, 'test')):
            with pytest.raises(ValueError, match='game lock'):
                operation()
    assert (manager.starts / NAME).exists() and not manager.user.exists()


@pytest.mark.parametrize('argument', ['{path}/', '"{path}/"', "'{path}/'", '={path}/'])
def test_process_check_refuses_a_game_for_the_exact_userdir(tmp_path, monkeypatch, argument):
    user = tmp_path / 'project with spaces' / '.runtime' / 'user'
    separator = '' if argument.startswith('=') else ' '
    output = '123 ./cataclysm-tiles --userdir' + separator + argument.format(path=user) + '\n'
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 0, output, ''))
    with pytest.raises(ValueError, match='game is running'):
        starts.refuse_game(user)
    starts.refuse_game(user.parent / 'user-other')


def test_detected_game_prevents_any_userdir_mutation(manager, monkeypatch):
    manager.create(NAME)
    previous = old_user(manager)
    def running(user):
        raise ValueError('game is running')
    monkeypatch.setattr(starts, 'refuse_game', running)
    with pytest.raises(ValueError, match='game is running'):
        manager.install(NAME)
    starts.check_files(manager.user, previous)
    assert not manager.archive.exists()


def test_dispose_seals_outputs_player_store_and_final_save_before_removing_then_restores(manager, monkeypatch):
    manager.create(NAME)
    previous = old_user(manager)
    receipt = manager.install(NAME)
    start = manager.starts / NAME
    (start / 'work' / 'traces').mkdir()
    (start / 'work' / 'traces' / 'host.jsonl').write_bytes(b'trace')
    (start / 'work' / 'evaluation.sqlite3').write_bytes(b'evaluation')
    Path(receipt['player_store']).write_bytes(b'final memory')
    (manager.user / 'save' / 'A world' / 'survivor.sav').write_bytes(b'final played save')
    final_user, outputs = starts.inventory(manager.user), starts.inventory(start / 'work')
    rmtree = shutil.rmtree
    removals = []

    def sealed_before_remove(path, *args, **kwargs):
        if Path(path) in (manager.user, start):
            errors, _ = evidence.verify(full=True, store=manager.store, manifests=manager.manifests)
            assert errors == []
            sealed = manager.store / 'withholding-test-outputs'
            starts.check_files(sealed / 'user', final_user)
            starts.check_files(sealed / 'start' / 'work', outputs)
            assert (sealed / 'start' / 'installation.json').exists()
            removals.append(Path(path))
        return rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, 'rmtree', sealed_before_remove)
    result = manager.dispose(NAME, 'withholding-test-outputs', CITED, 'fixture run')
    assert removals == [manager.user, start]
    assert not start.exists() and not manager.user.exists() and not manager.installed.exists()
    assert result['manifest_sha256'] == evidence.file_sha256(manager.manifests / 'withholding-test-outputs.sha256')
    assert 'no longer held out' in evidence.read_index(manager.manifests)['studies']['withholding-test-outputs']['note']
    restored = manager.restore_userdir(receipt['archive'])
    starts.check_files(manager.user, previous)
    assert restored['archive'] is None
    # Restoring again preserves any intervening play in a new archive.
    (manager.user / 'new.txt').write_bytes(b'new play')
    displaced = starts.inventory(manager.user)
    restored = manager.restore_userdir(Path(receipt['archive']).name)
    starts.check_files(manager.user, previous)
    starts.check_files(Path(restored['archive']) / 'user', displaced)


def test_failed_seal_retains_working_copy_and_active_userdir(manager, monkeypatch):
    manager.create(NAME)
    manager.install(NAME)
    before = starts.inventory(manager.user)
    def failed(*a, **kw):
        raise evidence.EvidenceError('seal failed')
    monkeypatch.setattr(evidence, 'seal', failed)
    with pytest.raises(ValueError, match='seal failed'):
        manager.dispose(NAME, 'failed-seal', CITED, '')
    starts.check_files(manager.user, before)
    assert (manager.starts / NAME).exists() and manager.installed.exists()


def test_excluded_output_is_not_deleted_as_though_it_were_sealed(manager):
    manager.create(NAME)
    target = manager.starts / NAME
    (target / 'working.lock').write_bytes(b'only copy')
    with pytest.raises(ValueError, match='missing'):
        manager.dispose(NAME, 'excluded-output', CITED, '')
    assert (target / 'working.lock').read_bytes() == b'only copy'


def test_restore_refuses_changed_archive_without_replacing_current_userdir(manager):
    manager.create(NAME)
    old_user(manager)
    receipt = manager.install(NAME)
    manager.dispose(NAME, 'restore-fixture', CITED, '')
    archive_user = Path(receipt['archive']) / 'user'
    (archive_user / 'save' / 'previous.sav').write_bytes(b'damaged archive')
    previous = old_user(manager)
    with pytest.raises(ValueError, match='changed'):
        manager.restore_userdir(receipt['archive'])
    starts.check_files(manager.user, previous)


def test_names_and_unsupported_start_versions_are_refused(manager):
    for name in ('01', '../escape', 'UpperCase'):
        with pytest.raises(ValueError, match='descriptive'):
            manager.create(name)
    manager.create(NAME)
    path = manager.starts / NAME / 'manifest.json'
    path.write_text(path.read_text().replace('start-manifest/1', 'start-manifest/0'))
    with pytest.raises(ValueError, match='unsupported'):
        manager.install(NAME)
