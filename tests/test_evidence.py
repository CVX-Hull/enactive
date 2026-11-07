"""The retained-evidence store: sealing once, read-only copies and verification against tracked manifests."""
from __future__ import annotations

import json
import stat
import subprocess

import pytest

from tools import evidence
from tools.evidence import EvidenceError, seal, verify

CITED = ['docs/overview.md']


def sources(tmp_path):
    run = tmp_path / 'src' / 'runtime'
    (run / 'computer-sessions' / 'r1').mkdir(parents=True)
    (run / 'computer-sessions' / 'r1' / 'receipt.json').write_text('{"a": 1}')
    (run / 'computer-sessions' / 'r1' / 'frame.png').write_bytes(b'\x89PNG' * 10)
    (run / 'player-memory-r1.sqlite3').write_bytes(b'db')
    for excluded in ('Cataclysm.app', '__pycache__'):
        (run / excluded).mkdir()
        (run / excluded / 'big').write_bytes(b'x')
    (run / 'credentials.json').write_text('{"item": "secret-name"}')
    ledger = tmp_path / 'src' / 'ledger.jsonl'
    ledger.write_text('{"run": "r1"}\n')
    return run, ledger


def test_seal_copies_once_excludes_non_evidence_and_verifies_with_stock_shasum(tmp_path):
    run, ledger = sources(tmp_path)
    store, manifests = tmp_path / 'store', tmp_path / 'manifests'
    entry = seal('s1', [('.', run), ('operator', ledger)], CITED, 'test', store=store, manifests=manifests)
    assert entry['files'] == 4 and entry['visibility'] == 'private' and entry['cited_by'] == CITED
    paths = evidence.listing(store / 's1')
    assert paths == ['computer-sessions/r1/frame.png', 'computer-sessions/r1/receipt.json', 'operator/ledger.jsonl',
                     'player-memory-r1.sqlite3']  # no build, cache or credentials
    assert not (store / 's1' / 'computer-sessions' / 'r1' / 'receipt.json').stat().st_mode & stat.S_IWUSR
    shasum = subprocess.run(['shasum', '-a', '256', '-c', str(manifests / 's1.sha256')], cwd=store / 's1',
                            capture_output=True, text=True)
    assert shasum.returncode == 0, shasum.stdout + shasum.stderr
    assert verify(full=True, store=store, manifests=manifests) == ([], ['s1: 4 files verified (hashes)'])
    with pytest.raises(EvidenceError, match='never rewritten'):
        seal('s1', [('.', run)], CITED, 'again', store=store, manifests=manifests)


def test_verify_reports_missing_extra_changed_and_tampered_evidence(tmp_path):
    run, ledger = sources(tmp_path)
    store, manifests = tmp_path / 'store', tmp_path / 'manifests'
    seal('s1', [('.', run)], CITED, 'test', store=store, manifests=manifests)
    receipt = store / 's1' / 'computer-sessions' / 'r1' / 'receipt.json'
    receipt.parent.chmod(0o755)
    receipt.chmod(0o644)
    receipt.write_text('{"a": 2}')  # same size: only the full check sees it
    assert verify(full=False, store=store, manifests=manifests)[0] == []
    assert 'files changed' in verify(full=True, store=store, manifests=manifests)[0][0]
    (receipt.parent / 'extra.txt').write_text('x')
    assert '1 unexpected' in verify(full=False, store=store, manifests=manifests)[0][0]
    (manifests / 's1.sha256').chmod(0o644)
    with (manifests / 's1.sha256').open('a') as stream:
        stream.write('0' * 64 + '  forged\n')
    assert verify(full=False, store=store, manifests=manifests)[0] == ['s1: manifest missing or changed since sealing']


def test_absent_store_is_a_note_and_bad_inputs_are_refused(tmp_path):
    run, _ = sources(tmp_path)
    store, manifests = tmp_path / 'store', tmp_path / 'manifests'
    seal('s1', [('.', run)], CITED, 'test', store=store, manifests=manifests)
    assert verify(full=True, store=tmp_path / 'elsewhere', manifests=manifests) == (
        [], ['s1: store not present on this checkout (3 files)'])
    (run / 'link').symlink_to(run / 'player-memory-r1.sqlite3')
    with pytest.raises(EvidenceError, match='links are not evidence'):
        seal('s2', [('.', run)], CITED, 'test', store=store, manifests=manifests)
    assert not (store / 's2').exists()  # a failed seal leaves nothing behind
    with pytest.raises(EvidenceError, match='cited records must exist'):
        seal('s3', [('.', run)], ['docs/none.md'], 'test', store=store, manifests=manifests)
    with pytest.raises(EvidenceError, match='lower-case'):
        seal('Bad', [('.', run)], CITED, 'test', store=store, manifests=manifests)
    (manifests / 'index.json').write_text(json.dumps({'schema': 'evidence-index/0', 'studies': {}}))
    with pytest.raises(EvidenceError, match='unsupported index version'):
        verify(full=False, store=store, manifests=manifests)


def test_tracked_manifests_match_their_index():
    errors, _ = verify(full=False, store=evidence.ROOT / '.no-store-in-tests', manifests=evidence.MANIFESTS)
    assert errors == []
