"""R-SAVE-LOSS: select the matched final save and store from a disposed sealed start."""
import json
from pathlib import Path

import pytest

from test_start_lifecycle import manager, CITED
from tools import evidence, starts


@pytest.mark.parametrize('working', [True, False])
def test_create_from_disposed_start_uses_final_save_and_matching_store(manager, tmp_path, working):
    source = tmp_path / 'disposed'
    (source / 'user/save/world').mkdir(parents=True)
    (source / 'user/save/world/final.sav').write_bytes(b'final saved moment')
    (source / 'start/user/save/world').mkdir(parents=True)
    (source / 'start/user/save/world/original.sav').write_bytes(b'original saved moment')
    (source / 'start' / starts.PLAYER_STORE).write_bytes(b'original store')
    if working:
        (source / 'start/work').mkdir()
        (source / 'start/work' / starts.PLAYER_STORE).write_bytes(b'final store')
    study = 'disposed-saved-moment'
    evidence.seal(study, [('.', source, 'fixture')], CITED, 'fixture', store=manager.store, manifests=manager.manifests)
    before = starts.inventory(manager.store / study)
    description = manager.create('another-saved-moment', study)
    directory = Path(description['directory'])
    assert (directory / 'user/save/world/final.sav').read_bytes() == b'final saved moment'
    assert not (directory / 'user/save/world/original.sav').exists()
    assert (directory / starts.PLAYER_STORE).read_bytes() == (b'final store' if working else b'original store')
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['source_study'] == study
    assert manifest['source_manifest_sha256'] == evidence.file_sha256(manager.manifests / f'{study}.sha256')
    assert manager.describe('another-saved-moment') == description
    assert starts.inventory(manager.store / study) == before
    manager.install('another-saved-moment')
    assert (manager.user / 'save/world/final.sav').read_bytes() == b'final saved moment'
    result = manager.dispose('another-saved-moment', 'disposed-again', CITED, 'fixture')
    assert result['sealed'] == 'disposed-again'


def test_create_refuses_disposed_start_without_final_save(manager, tmp_path):
    source = tmp_path / 'disposed'
    (source / 'start/user/save/world').mkdir(parents=True)
    (source / 'start/user/save/world/original.sav').write_bytes(b'original saved moment')
    (source / 'start/work').mkdir()
    (source / 'start/work' / starts.PLAYER_STORE).write_bytes(b'post-run store')
    study = 'disposed-without-final-save'
    evidence.seal(study, [('.', source, 'fixture')], CITED, 'fixture', store=manager.store, manifests=manager.manifests)
    with pytest.raises(ValueError, match='user/save/'):
        manager.create('refused-saved-moment', study)
    assert not (manager.starts / 'refused-saved-moment').exists()
