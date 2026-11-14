"""Reusable starts protect R-SAVE-LOSS / R-EVIDENCE-LOSS with temporary roots only.

These are file lifecycle and process-exclusion tests, not game load evidence.
"""
from __future__ import annotations

import builtins
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from harness.prepared_app import game_lock
from tools import evidence, starts

NAME = 'seven-day-end-01'
CITED = ['docs/overview.md']
REFUSE_GAME = starts.refuse_game


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
    monkeypatch.setattr(starts, 'refuse_game', lambda: None)
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


@pytest.mark.parametrize('executable,arguments', [
    ('/project/cataclysm-tiles.official', '--userdir /other/user/'),
    ('./cataclysm-tiles', '--userdir .runtime/user/'),
    ('/project/cataclysm-tiles', '--userdir /project/user/../user/'),
    ('/project/Contents/MacOS/Cataclysm', ''),
])
def test_process_check_uses_executable_independently_of_arguments(monkeypatch, executable, arguments):
    # ps comm is the executable alone, including paths with spaces; argv's
    # userdir spelling cannot hide a game or make an unrelated process a game.
    def processes(command, **kwargs):
        process = executable if command[-1] == 'pid=,comm=' else f'{executable} {arguments}'
        return subprocess.CompletedProcess(command, 0, f'123 {process}\n456 /usr/bin/python\n', '')
    monkeypatch.setattr(subprocess, 'run', processes)
    with pytest.raises(ValueError, match='game is running'):
        REFUSE_GAME()


@pytest.mark.parametrize('operation', ['install', 'restore', 'dispose'])
def test_any_game_blocks_all_mutating_commands(manager, monkeypatch, operation):
    manager.create(NAME)
    previous = old_user(manager)
    monkeypatch.setattr(starts, 'refuse_game', REFUSE_GAME)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(
        a, 0, '123 /elsewhere with spaces/Contents/MacOS/Cataclysm\n', ''))
    calls = dict(install=lambda: manager.install(NAME),
                 restore=lambda: manager.restore_userdir('userdir-example'),
                 dispose=lambda: manager.dispose(NAME, 'game-blocked', CITED, ''))
    with pytest.raises(ValueError, match='game is running'):
        calls[operation]()
    starts.check_files(manager.user, previous)
    assert not manager.archive.exists()
    assert not (manager.store / 'game-blocked').exists()


def test_detected_game_prevents_any_userdir_mutation(manager, monkeypatch):
    manager.create(NAME)
    previous = old_user(manager)
    def running():
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


@pytest.mark.parametrize('relative', ['working.lock', '.DS_Store', 'node_modules/nested.txt'])
def test_excluded_output_is_refused_before_sealing(manager, monkeypatch, relative):
    manager.create(NAME)
    target = manager.starts / NAME
    output = target / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b'only copy')
    monkeypatch.setattr(evidence, 'seal', lambda *a, **kw: pytest.fail('must refuse before seal'))
    with pytest.raises(ValueError, match='excluded from evidence') as error:
        manager.dispose(NAME, 'excluded-output', CITED, '')
    assert str(output) in str(error.value)
    assert output.read_bytes() == b'only copy'
    assert not (manager.store / 'excluded-output').exists()


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


@pytest.mark.parametrize('dangling', [False, True])
@pytest.mark.parametrize('operation,relative', [
    ('create', 'starts/' + NAME),
    ('install', 'starts/installed.json'),
    ('install', f'starts/{NAME}/work'),
    ('install', f'starts/{NAME}/manifest.json'),
    ('install', 'archive'),
    ('install', 'user'),
    ('dispose', f'starts/{NAME}/installation.json'),
    ('dispose', f'starts/{NAME}/disposal.json'),
    ('dispose', f'starts/{NAME}/work/linked-output'),
    ('dispose', 'starts/installed.json.tmp'),
    ('restore', 'archive/userdir-example/manifest.json'),
    ('restore', 'archive/userdir-example/user'),
])
def test_symlink_receipts_and_outputs_refuse_before_any_write(manager, tmp_path, monkeypatch,
                                                            operation, relative, dangling):
    if operation != 'create':
        manager.create(NAME)
    if operation == 'dispose':
        manager.install(NAME)
    outside = tmp_path / 'outside'
    if not dangling:
        outside.write_bytes(b'untouched destination')
    link = manager.runtime / relative
    if link.is_dir():
        shutil.rmtree(link)
    elif link.exists():
        link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    monkeypatch.setattr(starts, 'game_lock', lambda *a: pytest.fail('must reject before lock or any write'))
    calls = dict(create=lambda: manager.create(NAME), install=lambda: manager.install(NAME),
                 dispose=lambda: manager.dispose(NAME, 'link-output', CITED, ''),
                 restore=lambda: manager.restore_userdir('userdir-example'))
    with pytest.raises(ValueError, match='links'):
        calls[operation]()
    assert link.is_symlink()
    assert not outside.exists() if dangling else outside.read_bytes() == b'untouched destination'


def test_receipts_are_created_exclusively_without_following_links(tmp_path, monkeypatch):
    path = tmp_path / 'receipt.json'
    real_open = os.open
    flags_seen = []
    def opened(file, flags, *a, **kw):
        flags_seen.append(flags)
        return real_open(file, flags, *a, **kw)
    monkeypatch.setattr(os, 'open', opened)
    starts.write_json(path, {'schema': 'fixture/1'})
    assert flags_seen and all(flags_seen[0] & flag for flag in (os.O_CREAT, os.O_EXCL, os.O_NOFOLLOW))
    with pytest.raises(FileExistsError):
        starts.write_json(path, {'schema': 'replacement/1'})
    assert json.loads(path.read_text()) == {'schema': 'fixture/1'}


@pytest.mark.parametrize('schema', [None, 'start-installation/0'])
def test_active_refuses_unversioned_or_unsupported_installation(manager, schema):
    manager.starts.mkdir(parents=True)
    starts.write_json(manager.installed, {'schema': schema, 'name': NAME})
    with pytest.raises(ValueError, match='installation receipt schema'):
        manager.active()


@pytest.mark.parametrize('failure', ['before-user-removal', 'after-user-removal', 'marker-removal'])
@pytest.mark.parametrize('resume', ['dispose', 'restore'])
def test_disposal_resumes_after_sealing_and_partial_removal(manager, monkeypatch, failure, resume):
    manager.create(NAME)
    previous = old_user(manager)
    installation = manager.install(NAME)
    assert installation['schema'] == 'start-installation/1'
    directory = manager.starts / NAME
    rmtree, unlink = shutil.rmtree, Path.unlink
    def interrupted_remove(path, *a, **kw):
        if ((failure == 'before-user-removal' and Path(path) == manager.user)
                or (failure == 'after-user-removal' and Path(path) == directory)):
            raise OSError('injected removal failure')
        return rmtree(path, *a, **kw)
    def interrupted_unlink(path, *a, **kw):
        if failure == 'marker-removal' and path == manager.installed:
            raise OSError('injected removal failure')
        return unlink(path, *a, **kw)
    with monkeypatch.context() as fault:
        fault.setattr(shutil, 'rmtree', interrupted_remove)
        fault.setattr(Path, 'unlink', interrupted_unlink)
        with pytest.raises(OSError, match='injected removal failure'):
            manager.dispose(NAME, 'resumable-outputs', CITED, '')
    pending = manager.active()['disposal']
    assert pending['study'] == 'resumable-outputs'
    assert pending['manifest_sha256'] == evidence.file_sha256(manager.manifests / 'resumable-outputs.sha256')
    if directory.exists():
        assert starts.read_json(directory / 'disposal.json') == pending
    if failure != 'before-user-removal':
        assert not manager.user.exists()
    monkeypatch.setattr(evidence, 'seal', lambda *a, **kw: pytest.fail('retry must not seal again'))
    verify = evidence.verify
    verifications = []
    def reverified(**kw):
        assert kw['full'] is True
        assert set(evidence.read_index(kw['manifests'])['studies']) == {'resumable-outputs'}
        verifications.append(kw)
        return verify(**kw)
    monkeypatch.setattr(evidence, 'verify', reverified)
    if resume == 'dispose':
        result = manager.dispose(NAME, 'resumable-outputs', CITED, '')
        assert result['manifest_sha256'] == pending['manifest_sha256']
        manager.restore_userdir(installation['archive'])
    else:
        manager.restore_userdir(installation['archive'])
    starts.check_files(manager.user, previous)
    assert not manager.installed.exists() and not directory.exists()
    assert len(verifications) == 1


@pytest.mark.parametrize('damage', ['content', 'permissions', 'manifest'])
def test_full_verification_of_only_disposal_study_precedes_removal(manager, monkeypatch, damage):
    manager.create(NAME)
    manager.install(NAME)
    seal, verify = evidence.seal, evidence.verify
    calls = []
    def damaged_seal(*a, **kw):
        entry = seal(*a, **kw)
        sealed = manager.store / 'verify-outputs' / 'start' / starts.PLAYER_STORE
        if damage == 'manifest':
            (manager.manifests / 'verify-outputs.sha256').write_text('changed manifest\n')
        else:
            sealed.chmod(0o644)
            if damage == 'content':
                content = sealed.read_bytes()
                sealed.write_bytes(b'x' * len(content))
                sealed.chmod(0o444)
        return entry
    def scoped_verify(**kw):
        assert kw['full'] is True
        assert set(evidence.read_index(kw['manifests'])['studies']) == {'verify-outputs'}
        calls.append(kw)
        return verify(**kw)
    monkeypatch.setattr(evidence, 'seal', damaged_seal)
    monkeypatch.setattr(evidence, 'verify', scoped_verify)
    with pytest.raises(ValueError, match='disposal verification failed'):
        manager.dispose(NAME, 'verify-outputs', CITED, '')
    assert calls and manager.user.exists() and manager.installed.exists()
    assert (manager.starts / NAME / 'disposal.json').exists()


@pytest.mark.parametrize('source', ['start', 'user'])
def test_source_directories_are_rechecked_after_sealing(manager, monkeypatch, source):
    manager.create(NAME)
    receipt = manager.install(NAME)
    seal = evidence.seal
    target = Path(receipt['player_store']) if source == 'start' else manager.user / 'config' / 'options.json'
    def changed_source(*a, **kw):
        entry = seal(*a, **kw)
        target.write_bytes(b'changed after the copy was sealed')
        return entry
    monkeypatch.setattr(evidence, 'seal', changed_source)
    with pytest.raises(ValueError, match='source changed after sealing'):
        manager.dispose(NAME, 'source-recheck', CITED, '')
    assert target.exists() and manager.installed.exists()


def test_archiving_rechecks_that_original_userdir_has_not_changed(manager, monkeypatch):
    manager.create(NAME)
    previous = old_user(manager)
    copy = starts.copy_tree
    def concurrent_change(source, target):
        copy(source, target)
        if source == manager.user:
            (source / 'save' / 'previous.sav').write_bytes(b'intervening play')
    monkeypatch.setattr(starts, 'copy_tree', concurrent_change)
    with pytest.raises(ValueError, match='changed files'):
        manager.install(NAME)
    assert (manager.user / 'save' / 'previous.sav').read_bytes() == b'intervening play'
    archive = next(manager.archive.iterdir())
    starts.check_files(archive / 'user', previous)
    assert not manager.installed.exists()


def test_work_already_exists_refuses_install_without_archiving(manager):
    manager.create(NAME)
    previous = old_user(manager)
    (manager.starts / NAME / 'work').mkdir()
    with pytest.raises(ValueError, match='working outputs already exist'):
        manager.install(NAME)
    starts.check_files(manager.user, previous)
    assert not manager.archive.exists()


@pytest.mark.parametrize('relative', [False, True])
def test_restore_confines_archives_to_project_archive_directory(manager, tmp_path, relative):
    outside = manager.runtime / 'outside-archive'
    (outside / 'user').mkdir(parents=True)
    starts.write_json(outside / 'manifest.json', dict(schema='userdir-archive/1', files={}))
    previous = old_user(manager)
    argument = '../outside-archive' if relative else str(outside)
    with pytest.raises(ValueError, match='project archive directory'):
        manager.restore_userdir(argument)
    starts.check_files(manager.user, previous)
    assert not manager.archive.exists()
