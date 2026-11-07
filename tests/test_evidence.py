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
    (run / 'computer-sessions' / 'r 1').mkdir(parents=True)  # a space, as real userdir names have
    (run / 'computer-sessions' / 'r 1' / 'receipt.json').write_text('{"a": 1}')
    (run / 'computer-sessions' / 'r 1' / 'frame.png').write_bytes(b'\x89PNG' * 10)
    (run / 'a-first-file.sqlite3').write_bytes(b'db')  # sorts before any directory
    (run / 'a-first-file.sqlite3').chmod(0o600)
    for excluded in ('Cataclysm.app', '__pycache__'):
        (run / excluded).mkdir()
        (run / excluded / 'big').write_bytes(b'x')
    (run / 'bridge').mkdir()
    (run / 'bridge' / 'game.lock').write_bytes(b'')
    (run / 'bridge' / 'admissions.json').write_text('{}')
    (run / 'credentials.json').write_text('{"item": "secret-name"}')
    (run / '.env').write_text('KEY=x')
    operator = tmp_path / 'src' / 'operator'
    operator.mkdir()
    (operator / 'ledger.jsonl').write_text('{"run": "r1"}\n')  # a directory holding only a file
    return run, operator


def stores(tmp_path):
    return dict(store=tmp_path / 'store', manifests=tmp_path / 'manifests')


def test_seal_copies_once_excludes_non_evidence_and_verifies_with_stock_shasum(tmp_path):
    run, operator = sources(tmp_path)
    where = stores(tmp_path)
    entry = seal('s1', [('.', run, '.runtime/x@abc1234'), ('operator', operator, '.runtime/ops')], CITED, 'test', **where)
    assert entry['files'] == 5 and entry['visibility'] == 'private' and entry['availability'] == 'present'
    assert entry['sources'] == {'.': '.runtime/x@abc1234', 'operator': '.runtime/ops'}
    assert sorted(entry['excluded']) == ['.env', 'Cataclysm.app', '__pycache__', 'bridge/game.lock', 'credentials.json']
    target = where['store'] / 's1'
    assert evidence.listing(target) == ['a-first-file.sqlite3', 'bridge/admissions.json', 'computer-sessions/r 1/frame.png',
                                        'computer-sessions/r 1/receipt.json', 'operator/ledger.jsonl']
    assert stat.S_IMODE((target / 'a-first-file.sqlite3').stat().st_mode) == 0o400  # never widened
    assert not any((target / p).stat().st_mode & 0o222 for p in evidence.listing(target))
    shasum = subprocess.run(['shasum', '-a', '256', '-c', str(where['manifests'] / 's1.sha256')], cwd=target,
                            capture_output=True, text=True)
    assert shasum.returncode == 0, shasum.stdout + shasum.stderr
    assert verify(full=True, **where) == ([], ['s1: 5 files verified (every hash)'])
    with pytest.raises(EvidenceError, match='never rewritten'):
        seal('s1', [('.', run, 'o')], CITED, 'again', **where)


def test_verify_reports_missing_extra_changed_writable_and_tampered_evidence(tmp_path):
    run, _ = sources(tmp_path)
    where = stores(tmp_path)
    seal('s1', [('.', run, 'o')], CITED, 'test', **where)
    receipt = where['store'] / 's1' / 'computer-sessions' / 'r 1' / 'receipt.json'
    receipt.parent.chmod(0o755)
    receipt.chmod(0o644)
    assert 'regained write permission' in verify(full=False, **where)[0][0]
    receipt.write_text('{"a": 2}')  # same size: only the full check sees the content
    receipt.chmod(0o444)
    assert verify(full=False, **where)[0] == []
    assert 'files changed' in verify(full=True, **where)[0][0]
    (receipt.parent / 'extra.txt').write_text('x')
    assert '1 unexpected' in verify(full=False, **where)[0][0]
    with (where['manifests'] / 's1.sha256').open('a') as stream:
        stream.write('0' * 64 + '  forged\n')
    assert verify(full=False, **where)[0] == ['s1: manifest missing or changed since sealing']


def test_a_malformed_manifest_is_reported_without_hiding_other_studies(tmp_path):
    run, _ = sources(tmp_path)
    where = stores(tmp_path)
    seal('s1', [('.', run, 'o')], CITED, 'test', **where)
    seal('s2', [('.', run, 'o')], CITED, 'test', **where)
    bad = b'0' * 64 + b'  odd\rname\n'
    (where['manifests'] / 's1.sha256').write_bytes(bad)
    index = json.loads((where['manifests'] / 'index.json').read_text())
    index['studies']['s1']['manifest_sha256'] = __import__('hashlib').sha256(bad).hexdigest()
    (where['manifests'] / 'index.json').write_text(json.dumps(index))
    errors, notes = verify(full=False, **where)
    assert errors == ['s1: s1.sha256:1: not a relative shasum line, or a repeated path']
    assert notes == ['s2: 4 files verified (file set, total bytes, read-only)']


def test_a_deleted_study_fails_while_an_absent_store_is_only_a_note(tmp_path):
    run, _ = sources(tmp_path)
    where = stores(tmp_path)
    seal('s1', [('.', run, 'o')], CITED, 'test', **where)
    assert verify(full=True, store=tmp_path / 'no-store', manifests=where['manifests']) == (
        [], ['s1: store not present on this checkout (4 files)'])
    evidence._writable(where['store'] / 's1')
    (where['store'] / 's1').rename(tmp_path / 'moved')
    assert verify(full=False, **where)[0] == ['s1: sealed evidence is missing from the store (the store is its only copy)']
    index = json.loads((where['manifests'] / 'index.json').read_text())
    index['studies']['s1'] |= dict(availability='removed', removed='2026-11-07: owner decision on #000')
    (where['manifests'] / 'index.json').write_text(json.dumps(index))
    assert verify(full=False, **where) == ([], ['s1: removed (2026-11-07: owner decision on #000)'])


def test_a_failed_seal_leaves_nothing_and_bad_inputs_are_refused(tmp_path):
    run, _ = sources(tmp_path)
    where = stores(tmp_path)
    where['manifests'].mkdir()
    where['manifests'].chmod(0o555)  # the copy succeeds; writing the manifest fails
    with pytest.raises(PermissionError):
        seal('s2', [('.', run, 'o')], CITED, 'test', **where)
    where['manifests'].chmod(0o755)
    assert not (where['store'] / 's2').exists() and not list(where['manifests'].iterdir())
    seal('s2', [('.', run, 'o')], CITED, 'test', **where)  # a retry succeeds
    (run / 'link').symlink_to(run / 'a-first-file.sqlite3')
    with pytest.raises(EvidenceError, match='links are not evidence'):
        seal('s3', [('.', run, 'o')], CITED, 'test', **where)
    assert not (where['store'] / 's3').exists()
    (run / 'link').unlink()
    for bad in ('bad\\name', 'carriage\rreturn', 'form\x0cfeed', 'line separator'):
        (run / bad).write_text('x')
        with pytest.raises(EvidenceError, match='cannot be written in a shasum manifest'):
            seal('s4', [('.', run, 'o')], CITED, 'test', **where)
        (run / bad).unlink()
    with pytest.raises(EvidenceError, match='excluded name cannot be a source'):
        seal('s5', [('game', run / 'Cataclysm.app', 'o')], CITED, 'test', **where)
    # Two files into one subdir under different origins would leave the index naming only the last one.
    with pytest.raises(EvidenceError, match='different origins share this subdir'):
        seal('s7', [('bridge', run / 'bridge' / 'admissions.json', '.runtime/a.json'),
                    ('bridge', run / 'a-first-file.sqlite3', '.runtime/b.sqlite3')], CITED, 'test', **where)
    assert not (where['store'] / 's7').exists()
    entry = seal('s7', [('bridge', run / 'bridge' / 'admissions.json', '.runtime/run'),
                        ('bridge', run / 'a-first-file.sqlite3', '.runtime/run')], CITED, 'test', **where)
    assert entry['sources'] == {'bridge': '.runtime/run'} and entry['files'] == 2
    with pytest.raises(EvidenceError, match='cited records must exist'):
        seal('s6', [('.', run, 'o')], ['docs/none.md'], 'test', **where)
    with pytest.raises(EvidenceError, match='lower-case'):
        seal('Bad', [('.', run, 'o')], CITED, 'test', **where)
    (where['manifests'] / 'index.json').write_text(json.dumps({'schema': 'evidence-index/0', 'studies': {}}))
    with pytest.raises(EvidenceError, match='unsupported index version'):
        verify(full=False, **where)


def test_tracked_manifests_match_their_index():
    errors, _ = verify(full=False, store=evidence.ROOT / '.no-store-in-tests', manifests=evidence.MANIFESTS)
    assert errors == []
