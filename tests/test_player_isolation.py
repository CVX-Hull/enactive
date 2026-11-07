"""The player driver and host never name the evaluator, the viewer or their stores (ADR008 item 4).

Import-linter covers only the `harness` package. These files live outside it, so a
reference test checks their text instead: nothing in them can import, spawn, read or
write evaluation output, which therefore cannot reach a player context.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ('harness.evaluation', 'harness/evaluation', 'harness.viewer', 'harness/viewer',
             '.runtime/evaluations', 'data/evaluation')


def player_files():
    files = [ROOT/'tools'/'campaign_player.py']
    files += sorted(path for path in (ROOT/'tools'/'player_host').rglob('*')
                    if path.is_file() and 'node_modules' not in path.relative_to(ROOT).parts)
    return files


def test_the_reference_set_is_not_empty():
    names = {path.relative_to(ROOT).as_posix() for path in player_files()}
    assert 'tools/campaign_player.py' in names
    assert {'tools/player_host/host.mjs', 'tools/player_host/run.mjs'} <= names
    assert not any('node_modules' in name for name in names)


@pytest.mark.parametrize('path', player_files(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_player_files_never_mention_evaluation_or_viewer(path):
    text = path.read_bytes().decode('utf-8', errors='replace')
    found = [needle for needle in FORBIDDEN if needle in text]
    assert not found, f'{path.relative_to(ROOT)} names {found}'
