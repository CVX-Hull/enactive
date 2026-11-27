"""Knowledge repository and gate v0 (#453): publication, rejection and atomicity.

Portable: real Git in tmp_path repositories, no game, no provider.
"""
from __future__ import annotations

from copy import deepcopy
import json
import fcntl
import os
import random
from pathlib import Path
import subprocess
import sys
import zlib

import pytest

from harness.curator import check, containers, knowledge, sandbox, session
from harness.curator.containers import Drafts, UnsafeTree, copy_tree
from harness.curator.gate import _history, current, gate, restore
from harness.curator.knowledge import KnowledgeError, Repository
from harness.curator.validate import validate
from tests.synthetic_knowledge_repo import build_cycle_and_withholding_repo, position

SEALED = '1' * 32
FRAME1 = f'{SEALED}-1'
FRAME2 = f'{SEALED}-2'
FRAME3 = f'{SEALED}-3'
FRAMES = {FRAME1, FRAME2}


def make_repo(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / 'knowledge', 'cdda')
    repo.ensure()
    return repo


def fact(fact_id='f1', citations=None, **extra):
    return dict(schema='curator-fact/6', record='fact', id=fact_id, statement_kind='observation', text=f'text {fact_id}', scope={}, tags=['mechanic'], links=[],
                citations=list(citations if citations is not None else [FRAME1]), subject='a thing') | extra


def article(slug='guide', title='A subject', facts=('f1',), **extra):
    return dict(schema='curator-fact/6', record='article', slug=slug, title=title,
                lead='A hypothesis.', body=[dict(text='An arbitrary claim.', facts=list(facts))],
                links=[], tags=[]) | extra


def submission(tmp_path: Path, changes, name='s1', **top) -> Path:
    body = {'schema': 'curator-submission/3', 'base_version': 'v0', 'summary': 'sum',
            'changes': changes, **top}
    directory = tmp_path / 'submissions' / name
    directory.mkdir(parents=True)
    (directory / 'submission.json').write_text(json.dumps(body))
    return directory


COVERAGE = {'schema': 'curator-coverage/2', 'session': 's1', 'actor': '001', 'last_step': 20,}


def run(repo, directory, frames=FRAMES, coverage=COVERAGE, session_kind='admission', *, session_labels=None):
    positions = frames if isinstance(frames, dict) else {frame: dict(session=(session_labels or {}).get(frame.partition('-')[0], {}).get('name', 's1'),
                             actor='001', step=index, order=[1, '001', index])
                 for index, frame in enumerate(sorted(frames), 1)}
    return gate(repo, directory, session_id='sess', window_frames=positions, coverage=coverage,
                session_kind=session_kind, session_labels=session_labels)


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo.path, capture_output=True, text=True,
                          check=True).stdout


def snapshot(repo):
    return git(repo, 'rev-parse', 'HEAD'), git(repo, 'tag', '--list'), git(repo, 'status',
                                                                          '--porcelain')


def seeded(tmp_path: Path) -> Repository:
    """A repository at v1 holding fact f1."""
    repo = make_repo(tmp_path)
    directory = submission(tmp_path, [dict(op='add_fact', fact=fact())], name='seed')
    assert run(repo, directory)['version'] == 'v1'
    return repo


def assert_history_rejected(repo, tmp_path, base, diagnostic):
    directory = submission(tmp_path, [change_fact('fresh')], name='rejected-history', base_version=base)
    before = snapshot(repo)
    for reader in (repo, Repository(repo.path.parent, repo.game)):
        assert reader.published() == base
        result = run(reader, directory)
        assert result['status'] == 'rejected' and result['version'] is None
        assert result['diagnostics'][0].startswith('publication failed: incompatible history at ')
        assert diagnostic in result['diagnostics'][0]
        restored = restore(reader, expected_base=base, target='v0')
        assert restored['status'] == 'rejected' and restored['version'] is None
        assert restored['diagnostics'] == ['incompatible or unavailable history']
        assert snapshot(reader) == before


def test_repointed_historical_tag_with_identical_snapshot_is_rejected(tmp_path):
    repo = seeded(tmp_path)
    assert restore(repo, expected_base='v1', target='v0')['version'] == 'v2'
    snapshots, _, _, _ = _history(repo)
    tree = git(repo, 'rev-parse', 'v1^{tree}').strip()
    replacement = knowledge._git(repo.path, 'commit-tree', tree, '-p', 'v0', '-m', 'different commit').decode().strip()
    git(repo, 'update-ref', 'refs/tags/v1', replacement)
    assert repo.snapshot('v1') == snapshots['v1']
    assert_history_rejected(repo, tmp_path, 'v2', 'consecutive commit history')


@pytest.mark.parametrize('revision, kind, old, new', [
    ('v1', 'commit', b'Publish v1', b'Rewrite v1'),
    ('v1^{tree}', 'tree', b'facts.jsonl', b'Facts.jsonl'),
    ('v1:facts.jsonl', 'blob', b'text f1', b'fake f1'),
    ('v1:provenance.json', 'blob', b'"step": 1', b'"step": 9'),
])
def test_mutated_git_object_with_unchanged_oid_is_rejected(tmp_path, revision, kind, old, new):
    repo = seeded(tmp_path)
    assert restore(repo, expected_base='v1', target='v0')['version'] == 'v2'
    _history(repo)
    oid = git(repo, 'rev-parse', revision).strip()
    data = knowledge._git(repo.path, 'cat-file', kind, oid)
    assert old in data
    changed = data.replace(old, new, 1)
    replacement = tmp_path / 'replaced-object'
    replacement.write_bytes(zlib.compress(f'{kind} {len(changed)}\0'.encode() + changed))
    replacement.replace(repo.path / '.git' / 'objects' / oid[:2] / oid[2:])
    assert_history_rejected(repo, tmp_path, 'v2', 'Git object hash mismatch')


@pytest.mark.parametrize('symlink, reason', [
    (False, 'unsupported snapshot layout'),
    (True, 'snapshot contains a non-regular file'),
])
def test_gate_and_restore_reject_bad_layout_in_an_older_tag(tmp_path, symlink, reason):
    repo = seeded(tmp_path)
    _history(repo)
    extra = repo.path / 'tests' / 'extra'
    if symlink:
        extra.symlink_to('../facts.jsonl')
    else:
        extra.write_bytes(b'extra')
    knowledge._git(repo.path, 'add', '-A')
    knowledge._git(repo.path, 'commit', '-m', 'invalid snapshot')
    knowledge._git(repo.path, 'tag', 'v2')
    extra.unlink()
    knowledge._git(repo.path, 'add', '-A')
    knowledge._git(repo.path, 'commit', '-m', 'valid snapshot after invalid history')
    knowledge._git(repo.path, 'tag', 'v3')
    assert_history_rejected(repo, tmp_path, 'v3', f'v2: {reason}')


@pytest.mark.parametrize('origin', [{'published_in': 'v0'}, {'published_in': 'v2'}, {'session': 'rewritten'}])
def test_gate_and_restore_reject_a_forged_record_origin_in_an_older_tag(tmp_path, origin):
    repo = seeded(tmp_path)
    original = repo.snapshot('v1')
    _history(repo)
    record = repo.records()[0] | origin
    check.validate_snapshot([record], repo.provenance(), repo.game, 'v2')
    assert repo.commit({'facts.jsonl': (json.dumps(record) + '\n').encode()}, 'invalid origin') == 'v2'
    assert repo.commit_snapshot(original, 'valid snapshot after invalid history') == 'v3'
    assert_history_rejected(repo, tmp_path, 'v3', 'v2: invalid record origin')


def test_cold_history_schema_dedup_still_checks_cross_snapshot_provenance(tmp_path):
    repo = seeded(tmp_path)
    original_fact_bytes = repo.snapshot('v1')['facts.jsonl']
    empty_prov = json.dumps({'frames': {}, 'sessions': {}, 'branches': {}, 'restores': []}).encode()
    assert repo.commit({'facts.jsonl': original_fact_bytes, 'provenance.json': empty_prov}, 'dropped provenance') == 'v2'
    assert_history_rejected(repo, tmp_path, 'v2', 'has no recorded provenance')


def test_warm_history_cache_rejects_consistent_rewrite_of_cached_tag(tmp_path):
    repo = seeded(tmp_path)
    _history(repo)
    (repo.path / 'tests' / '.keep').write_bytes(b'payload')
    knowledge._git(repo.path, 'add', 'tests/.keep')
    knowledge._git(repo.path, 'commit', '--amend', '--no-edit')
    knowledge._git(repo.path, 'tag', '-f', 'v1')
    directory = submission(tmp_path, [change_fact('fresh')], name='warm-rewrite', base_version='v1')
    before = snapshot(repo)

    assert repo.published() == 'v1'
    warm_gate = run(repo, directory)
    assert warm_gate['status'] == 'rejected' and warm_gate['version'] is None
    assert 'incompatible history at v1: published commit changed' in warm_gate['diagnostics'][0]
    warm_restore = restore(repo, expected_base='v1', target='v0')
    assert warm_restore['status'] == 'rejected' and warm_restore['version'] is None
    assert warm_restore['diagnostics'] == ['incompatible or unavailable history']

    cold = Repository(repo.path.parent, repo.game)
    assert cold.published() == 'v1'
    cold_gate = run(cold, directory)
    assert cold_gate['status'] == 'rejected' and cold_gate['version'] is None
    assert 'v1: unsupported program or test content' in cold_gate['diagnostics'][0]
    cold_restore = restore(cold, expected_base='v1', target='v0')
    assert cold_restore['status'] == 'rejected' and cold_restore['version'] is None
    assert cold_restore['diagnostics'] == ['incompatible or unavailable history']
    assert snapshot(cold) == before


def test_misplaced_parent_header_after_committer_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    v0 = git(repo, 'rev-parse', 'v0').strip()
    tree = git(repo, 'rev-parse', 'v0^{tree}').strip()
    raw = (
        f'tree {tree}\n'
        'author Test <test@example.com> 1700000000 +0000\n'
        'committer Test <test@example.com> 1700000000 +0000\n'
        f'parent {v0}\n\n'
        'misplaced parent\n'
    ).encode()
    forged = subprocess.run(
        ['git', '-C', str(repo.path), 'hash-object', '-t', 'commit', '--literally', '-w', '--stdin'],
        input=raw,
        capture_output=True,
        check=True,
    ).stdout.decode().strip()
    git(repo, 'tag', 'v1', forged)
    assert_history_rejected(repo, tmp_path, 'v1', 'consecutive commit history')


def test_ensure_refuses_existing_git_head_without_v0(tmp_path):
    repo = Repository(tmp_path / 'knowledge', 'cdda')
    repo.path.mkdir(parents=True)
    knowledge._git(repo.path, 'init', '-q', '-b', knowledge.BRANCH)
    knowledge._git(repo.path, 'commit', '--allow-empty', '-m', 'stray root')
    with pytest.raises(KnowledgeError, match='has commits without v0'):
        repo.ensure()


def test_validate_snapshot_rejects_mismatched_raw_lines(tmp_path):
    repo = seeded(tmp_path)
    with pytest.raises(ValueError, match='mismatched raw fact lines'):
        check.validate_snapshot(repo.records(), repo.provenance(), repo.game, 'v1', _raw_lines=[], _schema_valid=set())


def test_restore_exact_v0_and_reserves_historical_identity(tmp_path):
    repo = seeded(tmp_path)
    before = repo.snapshot('v0')
    result = restore(repo, expected_base='v1', target='v0')
    assert result['status'] == 'published' and result['version'] == 'v2'
    assert repo.snapshot('v2') == before and not (repo.path/'coverage.json').exists()
    repeated = restore(repo, expected_base='v2', target='v0')
    assert repeated['status'] == 'unchanged' and repeated['version'] == 'v2'
    again = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact())], name='reuse', base_version='v2'))
    assert again['status'] == 'rejected' and any('not new' in d for d in again['diagnostics'])


def test_repeated_restore_reserves_ids_and_slugs_from_both_discarded_histories(tmp_path):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact(), change_article()])['version'] == 'v1'
    assert restore(repo, expected_base='v1', target='v0')['version'] == 'v2'
    assert publish(repo, tmp_path, [change_fact('later'), change_article('later-guide', facts=['later'])])['version'] == 'v3'
    assert restore(repo, expected_base='v3', target='v0')['version'] == 'v4'
    for identity, changes in [
        ('f1', [change_fact()]),
        ('later', [change_fact('later')]),
        ('guide', [change_fact('fresh'), change_article(facts=['fresh'])]),
        ('later-guide', [change_fact('fresh'), change_article('later-guide', facts=['fresh'])]),
    ]:
        rejected = publish(repo, tmp_path, changes, name=f'reuse-{identity}')
        assert rejected['status'] == 'rejected' and f"identifier {identity!r} is not new" in rejected['diagnostics'][0]
    assert repo.snapshot('v4') == repo.snapshot('v0') and not (repo.path / 'coverage.json').exists()


def test_historical_session_label_conflict_after_restore_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact()], session_labels={SEALED: labels()})['version'] == 'v1'
    assert restore(repo, expected_base='v1', target='v0')['version'] == 'v2'
    _history(repo)
    provenance = dict(repo.provenance(), sessions={SEALED: labels(world='different')})
    check.validate_snapshot([], provenance, repo.game, 'v3')
    assert repo.commit({'provenance.json': json.dumps(provenance).encode()}, 'conflicting session labels') == 'v3'
    assert_history_rejected(repo, tmp_path, 'v3', 'different recorded labels')


def test_restore_refuses_stale_or_legacy_before_mutation(tmp_path):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    result = restore(repo, expected_base='v0', target='v0')
    assert result['status'] == 'rejected' and snapshot(repo) == before
    with (repo.state/'gate.jsonl').open('a') as log:
        log.write('{"schema":"curator-gate/1"}\n')
    with pytest.raises(KnowledgeError, match='unsupported active gate journal'):
        restore(repo, expected_base='v1', target='v0')
    with pytest.raises(KnowledgeError, match='unsupported active gate journal'):
        session.brief(repo, 'v1', {'sessions': []}, [])
    with pytest.raises(KnowledgeError, match='unsupported active gate journal'):
        session.run_session(repo, [], session.SessionConfig(argv=('unused',)))
    assert snapshot(repo) == before


def test_restore_refuses_missing_or_unsupported_payload(tmp_path):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    assert restore(repo, expected_base='v1', target='v12')['status'] == 'rejected'
    assert snapshot(repo) == before
    repo.commit({'programs/unsupported.py': b'pass\n'}, 'unsupported program')
    before = snapshot(repo)
    assert restore(repo, expected_base='v2', target='v0')['status'] == 'rejected'
    assert snapshot(repo) == before


@pytest.mark.parametrize('files', [
    {'knowledge.json': b'{"schema":"curator-knowledge/2","game":"foreign"}\n'},
    {'provenance.json': b'{"frames":{"frame-1":{"order":1}}}\n'},
    {'tests/payload': b'not a placeholder'},
])
def test_restore_refuses_incompatible_published_history(tmp_path, files):
    repo = seeded(tmp_path)
    repo.commit(files, 'incompatible history')
    before = snapshot(repo)
    result = restore(repo, expected_base='v2', target='v0')
    assert result['status'] == 'rejected'
    assert result['diagnostics'] == ['incompatible or unavailable history']
    assert snapshot(repo) == before


def test_restore_refuses_non_regular_snapshot_entries(tmp_path):
    repo = seeded(tmp_path)
    (repo.path/'tests'/'link').symlink_to('../facts.jsonl')
    knowledge._git(repo.path, 'add', '-A')
    knowledge._git(repo.path, 'commit', '-m', 'unsupported symlink')
    knowledge._git(repo.path, 'tag', 'v2')
    before = snapshot(repo)
    result = restore(repo, expected_base='v2', target='v0')
    assert result['status'] == 'rejected' and snapshot(repo) == before


def test_restore_cli_accepts_only_version_selection(tmp_path):
    repo = seeded(tmp_path)
    result = subprocess.run([sys.executable, '-m', 'harness.curator.gate', 'restore', str(repo.path.parent),
                             '--game', repo.game, '--expected-base', 'v1', '--target', 'v0'],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)['status'] == 'published' and repo.published() == 'v2'
    before = snapshot(repo)
    refused = subprocess.run([sys.executable, '-m', 'harness.curator.gate', 'restore', str(repo.path.parent),
                              '--game', repo.game, '--expected-base', 'v2', '--target', 'v1', '--reason', 'advice'],
                             capture_output=True, text=True, check=False)
    assert refused.returncode != 0 and snapshot(repo) == before


def test_restore_respects_session_lock(tmp_path):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    with (repo.state/'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(KnowledgeError, match='Another curator session'):
            restore(repo, expected_base='v1', target='v0')
    assert snapshot(repo) == before


@pytest.mark.parametrize('failed_command', ['commit', 'tag'])
def test_restore_reconciles_untagged_commit_and_reports_publication_failure(tmp_path, monkeypatch, failed_command):
    repo = seeded(tmp_path)
    knowledge._git(repo.path, 'commit', '--allow-empty', '-m', 'interrupted')
    original = knowledge._git
    def fail_publish(path, *args):
        if args[0] == failed_command and (failed_command == 'commit' or args[-1] == 'v2'):
            raise KnowledgeError('publication failure')
        return original(path, *args)
    monkeypatch.setattr(knowledge, '_git', fail_publish)
    result = restore(repo, expected_base='v1', target='v0')
    assert result['status'] == 'rejected' and repo.published() == 'v1'
    assert git(repo, 'rev-parse', 'HEAD').strip() == git(repo, 'rev-parse', 'v1').strip()
    assert (repo.path/'coverage.json').read_bytes() == repo.snapshot('v1')['coverage.json']
    assert git(repo, 'status', '--porcelain') == ''


def test_restore_reports_known_tag_when_result_append_fails(tmp_path, monkeypatch):
    repo = seeded(tmp_path)
    open_path = Path.open
    def failing_append(path, mode='r', *args, **kwargs):
        if path == repo.state/'gate.jsonl' and mode == 'a':
            raise OSError('cannot append')
        return open_path(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', failing_append)
    result = restore(repo, expected_base='v1', target='v0')
    assert result['status'] == 'unknown' and result['version'] == 'v2'
    assert repo.published() == 'v2' and repo.snapshot('v2') == repo.snapshot('v0')


def test_restore_keeps_tag_if_tag_command_reports_failure_after_creation(tmp_path, monkeypatch):
    repo = seeded(tmp_path)
    original = knowledge._git
    def tag_then_fail(path, *args):
        value = original(path, *args)
        if args == ('tag', 'v2'):
            raise KnowledgeError('tag outcome reported late')
        return value
    monkeypatch.setattr(knowledge, '_git', tag_then_fail)
    result = restore(repo, expected_base='v1', target='v0')
    assert result['status'] == 'unknown' and result['version'] == 'v2'
    assert repo.published() == 'v2' and repo.snapshot('v2') == repo.snapshot('v0')


@pytest.mark.parametrize('operation', ['restore', 'submission'])
def test_post_tag_lookup_failure_keeps_an_unresolved_result(tmp_path, monkeypatch, operation):
    from tools.curator_host.shadow import verdict_summary
    repo = seeded(tmp_path)
    original = knowledge._git
    failed_reads = 0
    tagged = False
    def uncertain_tag(path, *args):
        nonlocal failed_reads, tagged
        if tagged and args == ('tag', '--list', 'v*') and failed_reads < 2:
            failed_reads += 1
            raise KnowledgeError('temporarily unavailable tag lookup')
        value = original(path, *args)
        if args == ('tag', 'v2'):
            tagged = True
            raise KnowledgeError('tag command reported late failure')
        return value
    monkeypatch.setattr(knowledge, '_git', uncertain_tag)
    if operation == 'restore':
        result = restore(repo, expected_base='v1', target='v0')
    else:
        result = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('new'))],
                                      name='new', base_version='v1'))
    assert result['status'] == 'unknown' and result['version'] is None
    assert verdict_summary([result])['unresolved']
    assert repo.published() == 'v2'
    assert git(repo, 'rev-parse', 'HEAD').strip() == git(repo, 'rev-parse', 'v2').strip()


def test_restore_refuses_a_record_absent_from_its_claimed_publication(tmp_path):
    repo = seeded(tmp_path)
    record = dict(repo.records()[0], published_in='v0')
    repo.commit({'facts.jsonl': (json.dumps(record) + '\n').encode()}, 'invalid publication reference')
    before = snapshot(repo)
    result = restore(repo, expected_base='v2', target='v2')
    assert result['status'] == 'rejected' and snapshot(repo) == before


def test_submission_reconciles_untagged_commit_before_publication(tmp_path):
    repo = seeded(tmp_path)
    knowledge._git(repo.path, 'commit', '--allow-empty', '-m', 'interrupted')
    result = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('new'))],
                                  name='new', base_version='v1'))
    assert result['status'] == 'published' and result['version'] == 'v2'
    assert git(repo, 'rev-parse', 'v2^').strip() == git(repo, 'rev-parse', 'v1').strip()


def test_restoring_a_tag_preserves_its_record_ages_and_exact_bytes(tmp_path):
    repo = seeded(tmp_path)
    odd_bytes = {name: b' \n' + data + b'\n ' for name, data in repo.snapshot('v1').items()
                 if name in ('facts.jsonl', 'provenance.json', 'coverage.json')}
    assert repo.commit(odd_bytes, 'different JSON whitespace') == 'v2'
    original = repo.snapshot('v2')
    _history(repo)
    newer = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('f2'))],
                                     name='newer', base_version='v2'))
    assert newer['status'] == 'published'
    result = restore(repo, expected_base='v3', target='v2')
    assert result['status'] == 'published' and result['version'] == 'v4'
    assert repo.snapshot('v4') == original
    assert repo.records()[0]['published_in'] == 'v1'


def test_ensure_is_idempotent_and_starts_at_v0(tmp_path):
    repo = Repository(tmp_path / 'knowledge', 'cdda')
    assert repo.ensure() == 'v0'
    before = snapshot(repo)
    assert repo.ensure() == 'v0'
    assert snapshot(repo) == before
    assert repo.published() == 'v0'
    assert repo.records() == []
    assert json.loads((repo.path / 'knowledge.json').read_text()) == {
        'schema': 'curator-knowledge/5', 'game': 'cdda'}
    assert repo.provenance() == {'frames': {}, 'frame_clocks': {}, 'sessions': {}, 'branches': {}, 'restores': []}
    assert 'ontology/types.json' not in repo.snapshot('v0')
    assert (repo.path / 'programs' / '.keep').exists() and (repo.path / 'tests' / '.keep').exists()
    assert repo.state == tmp_path / 'knowledge' / 'cdda.state'


def test_valid_submission_is_accepted_and_versions_are_exportable(tmp_path):
    repo = make_repo(tmp_path)
    directory = submission(tmp_path, [dict(op='add_fact', fact=fact())],
                           from_drafts=['d1'])
    verdict = run(repo, directory)
    operation_id = verdict['operation_id']
    assert operation_id
    assert {k: v for k, v in verdict.items() if k != 'operation_id'} == {'schema': 'curator-gate/2', 'operation': 'submission', 'status': 'published',
                       'submission': 's1', 'session': 'sess', 'restored_from': None,
                       'base_version': 'v0', 'version': 'v1', 'from_drafts': ['d1'], 'diagnostics': []}
    assert repo.published() == 'v1'
    stored = repo.facts()
    assert stored[0]['id'] == 'f1' and stored[0]['published_in'] == 'v1'
    assert stored[0]['session'] == 'sess'
    assert stored[0]['tags'] == ['mechanic']
    new, old = tmp_path / 'at-v1', tmp_path / 'at-v0'
    repo.export('v1', new)
    repo.export('v0', old)
    assert 'f1' in (new / 'facts.jsonl').read_text()
    assert (old / 'facts.jsonl').read_text() == ''
    assert not (new / '.git').exists()
    with pytest.raises(KnowledgeError):
        repo.export('v1', new)
    message = git(repo, 'log', '-1', '--format=%B')
    assert 'sess' in message and 's1' in message
    assert git(repo, 'log', '-1', '--format=%an %ae').strip() == 'enactive-gate gate@localhost'
    lines = (repo.state / 'gate.jsonl').read_text().splitlines()
    assert json.loads(lines[-1]) == verdict


def test_stale_base_is_rejected_with_the_current_version(tmp_path):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact('f2')}]))
    assert not (verdict['status'] == 'published') and verdict['version'] is None
    assert any('v1' in line and 'stale' in line for line in verdict['diagnostics'])
    assert snapshot(repo) == before


def test_out_of_window_citation_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    changes = [{'op': 'add_fact', 'fact': fact(citations=(FRAME1, FRAME3))}]
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, changes))
    assert not (verdict['status'] == 'published')
    assert any(FRAME3 in line and 'outside' in line for line in verdict['diagnostics'])
    assert snapshot(repo) == before


def test_duplicate_fact_ids_are_rejected(tmp_path):
    repo = seeded(tmp_path)
    existing = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact('f1')}],
                                    base_version='v1'))
    assert not (existing['status'] == 'published') and any('not new' in x for x in existing['diagnostics'])
    within = run(repo, submission(
        tmp_path, [{'op': 'add_fact', 'fact': fact('f9')}, {'op': 'add_fact', 'fact': fact('f9')}],
        name='s2', base_version='v1'))
    assert not (within['status'] == 'published')
    assert repo.published() == 'v1'


def malformed_cases():
    good = {'op': 'add_fact', 'fact': fact()}
    return {
        'extra fact field': [{'op': 'add_fact', 'fact': fact(note='x')}],
        'extra change field': [{**good, 'more': 1}],
        'unknown op': [{'op': 'delete_fact', 'id': 'f1'}],
        'wrong fact schema': [{'op': 'add_fact', 'fact': {**fact(), 'schema': 'curator-fact/2'}}],
        'empty citations': [{'op': 'add_fact', 'fact': fact(citations=())}],
        'scope not object': [{'op': 'add_fact', 'fact': {**fact(), 'scope': 'cdda'}}],
        'obsolete type operation': [dict(op='add_type', type={})],
        'no changes': [],
        'too many changes': [{'op': 'add_fact', 'fact': fact(f'f{i}')} for i in range(201)],
    }


@pytest.mark.parametrize('name', list(malformed_cases()))
def test_malformed_submissions_are_rejected_and_leave_the_repository_alone(tmp_path, name):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, malformed_cases()[name]))
    assert not (verdict['status'] == 'published') and verdict['diagnostics']
    assert snapshot(repo) == before


def test_envelope_problems_are_rejected(tmp_path):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    change = [dict(op='add_fact', fact=fact('seed-fact'))]
    cases = {
        'schema': submission(tmp_path, change, name='a', schema='curator-submission/1'),
        'extra': submission(tmp_path, change, name='b', surprise=1),
        'base': submission(tmp_path, change, name='c', base_version='3'),
    }
    huge = submission(tmp_path, change, name='d')
    (huge / 'submission.json').write_text(json.dumps(
        {'schema': 'curator-submission/3', 'base_version': 'v0', 'summary': 'x' * 300_000,
         'changes': change}))
    garbage = tmp_path / 'submissions' / 'e'
    garbage.mkdir()
    (garbage / 'submission.json').write_text('{not json')
    empty = tmp_path / 'submissions' / 'f'
    empty.mkdir()
    cases.update(oversize=huge, garbage=garbage, missing=empty)
    for name, directory in cases.items():
        verdict = run(repo, directory)
        assert not (verdict['status'] == 'published'), name
        assert verdict['submission'] == directory.name
    assert snapshot(repo) == before


def test_failed_commit_leaves_published_unchanged(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    real = knowledge._git

    def failing(cwd, *args):
        if args[0] == 'tag':
            raise KnowledgeError('forced tag failure')
        return real(cwd, *args)

    monkeypatch.setattr(knowledge, '_git', failing)
    verdict = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}]))
    monkeypatch.setattr(knowledge, '_git', real)
    assert not (verdict['status'] == 'published') and verdict['version'] is None
    assert any('forced tag failure' in x for x in verdict['diagnostics'])
    assert repo.published() == 'v0'
    assert snapshot(repo) == before
    assert repo.facts() == []
    retry = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}], name='s2'))
    assert (retry['status'] == 'published') and repo.published() == 'v1'


def test_gate_log_gains_one_line_per_call(tmp_path):
    repo = make_repo(tmp_path)
    run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact(citations=[FRAME3]))]))
    run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact())], name='s2'))
    run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))], name='s3'))
    lines = (repo.state / 'gate.jsonl').read_text().splitlines()
    assert [json.loads(line)['status'] for line in lines] == ['rejected', 'published', 'rejected']
    assert [json.loads(line)['submission'] for line in lines] == ['s1', 's2', 's3']


def test_the_gate_reads_neither_links_nor_special_files(tmp_path):
    repo = make_repo(tmp_path)
    secret = tmp_path / 'secret.json'
    secret.write_text(json.dumps({'schema': 'curator-submission/3', 'base_version': 'v0', 'summary': 's',
                                  'changes': [dict(op='add_fact', fact=fact('seed-fact'))]}))
    linked = tmp_path / 'submissions' / 'link'
    linked.mkdir(parents=True)
    (linked / 'submission.json').symlink_to(secret)
    fifo = tmp_path / 'submissions' / 'fifo'
    fifo.mkdir()
    os.mkfifo(fifo / 'submission.json')  # a blocking open here would hang the gate
    for directory in (linked, fifo):
        verdict = run(repo, directory)
        assert not (verdict['status'] == 'published') and 'not a regular file' in verdict['diagnostics'][0]
    assert repo.published() == 'v0'


def test_pathological_json_is_rejected_not_raised(tmp_path):
    repo = make_repo(tmp_path)
    deep = tmp_path / 'submissions' / 'deep'
    deep.mkdir(parents=True)
    (deep / 'submission.json').write_text('[' * 100_000 + ']' * 100_000)
    surrogate = submission(tmp_path, [dict(op='add_fact', fact=fact(text='x'))], name='sur')
    (surrogate / 'submission.json').write_text(
        (surrogate / 'submission.json').read_text().replace('"x"', '"\\ud800"'))
    bad_drafts = submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))], name='drafts',
                            from_drafts=['../../etc'])
    for directory in (deep, surrogate, bad_drafts):
        verdict = run(repo, directory)
        assert not (verdict['status'] == 'published') and verdict['diagnostics'], directory.name
        assert verdict['from_drafts'] == []
    assert repo.published() == 'v0'


def test_an_inherited_git_environment_cannot_redirect_the_repository(tmp_path, monkeypatch):
    other = tmp_path / 'other'
    other.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=other, check=True)
    monkeypatch.setenv('GIT_DIR', str(other / '.git'))
    monkeypatch.setenv('GIT_WORK_TREE', str(other))
    repo = make_repo(tmp_path)
    verdict = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))]))
    monkeypatch.delenv('GIT_DIR')
    monkeypatch.delenv('GIT_WORK_TREE')
    assert (verdict['status'] == 'published') and repo.published() == 'v1'
    assert subprocess.run(['git', 'tag'], cwd=other, capture_output=True, text=True).stdout == ''


def test_draft_trees_refuse_links_and_special_files(tmp_path):
    secret = tmp_path / 'host-secrets'
    secret.mkdir()
    (secret / 'key').write_text('do not copy')
    for name, build in {
        'root-link': lambda d: d.symlink_to(secret, target_is_directory=True),
        'inner-link': lambda d: (d.mkdir(), (d / 'k').symlink_to(secret / 'key')),
        'fifo': lambda d: (d.mkdir(), os.mkfifo(d / 'pipe')),
    }.items():
        directory = tmp_path / name
        build(directory)
        with pytest.raises(UnsafeTree):
            copy_tree(directory, tmp_path / f'{name}-copy')
        assert not (tmp_path / f'{name}-copy').exists()


def test_collect_refuses_linked_and_special_drafts_and_promote_validates_ids(tmp_path):
    secret = tmp_path / 'host-secrets'
    secret.mkdir()
    (secret / 'key').write_text('do not copy')
    drafts = Drafts(tmp_path / 'state')
    source = tmp_path / 'workspace-drafts'
    source.mkdir()
    (source / 'linked').symlink_to(secret, target_is_directory=True)
    (source / 'inner').mkdir()
    (source / 'inner' / 'k').symlink_to(secret / 'key')
    (source / 'plain').mkdir()
    (source / 'plain' / 'notes.md').write_text('ok')
    report = drafts.collect(source, 'sess', {})
    assert report['created'] == ['plain']
    assert sorted(r['id'] for r in report['refused']) == ['inner', 'linked']
    stored = sorted(p.name for p in (tmp_path / 'state' / 'drafts').iterdir())
    assert stored == ['plain']
    assert not any('do not copy' in p.read_text() for p in (tmp_path / 'state').rglob('*') if p.is_file())
    (tmp_path / 'state' / 'outside').mkdir()
    (tmp_path / 'state' / 'outside' / 'manifest.json').write_text('{}')
    assert drafts.promote(['../outside', 'plain'], 'sess') == ['plain']
    assert (tmp_path / 'state' / 'outside' / 'manifest.json').read_text() == '{}'


def test_an_aborted_collect_does_not_age_drafts(tmp_path):
    drafts = Drafts(tmp_path / 'state')
    source = tmp_path / 'ws'
    (source / 'plan').mkdir(parents=True)
    (source / 'plan' / 'n').write_text('1')
    drafts.collect(source, 's0', {})
    before = drafts.checkout(tmp_path / 'ws2')
    assert drafts.collect(tmp_path / 'ws2', 's1', before, age=False)['aged'] == []
    assert drafts.list()[0]['lifecycle']['untouched_sessions'] == 0
    assert drafts.collect(tmp_path / 'ws2', 's2', before)['aged'] == ['plan']


def test_the_brief_escapes_names_the_curator_chose(tmp_path):
    repo = make_repo(tmp_path)
    directory = submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}], name='s1\n# Injected heading')
    run(repo, directory)
    text = session.brief(repo, 'v0', {'sessions': []}, [])
    assert '\n# Injected heading' not in text and "'s1\\n# Injected heading'" in text


def test_surviving_host_processes_stop_collection(tmp_path):
    repo = make_repo(tmp_path)
    workspace = tmp_path / 'ws'
    for name in session.WRITABLE:
        (workspace / name).mkdir(parents=True)
    (workspace / 'drafts' / 'plan').mkdir()
    (workspace / 'drafts' / 'plan' / 'n').write_text('x')
    good = submission(workspace, [dict(op='add_fact', fact=fact('seed-fact'))])
    assert good.parent == workspace / 'submissions'
    record_dir = tmp_path / 'record'
    record_dir.mkdir()
    result = sandbox.Result(0, None, 0, 0, 0.1, [4242])
    drafts = Drafts(repo.state)
    record = session._close_out(repo, 'sess', record_dir, workspace, None, result, [], FRAMES, COVERAGE, drafts, {})
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and life['survivors'] == [4242] and 'survived' in life['errors'][0]
    assert record['verdicts'] == [] and record['drafts'] == {} and repo.published() == 'v0'
    assert not (record_dir / 'submissions').exists() and drafts.list() == []


@pytest.mark.skipif(not hasattr(os, 'chflags'), reason='BSD file flags only')
def test_remove_clears_immutable_and_unreadable_entries(tmp_path):
    import stat
    tree = tmp_path / 'ws'
    (tree / 'a' / 'b').mkdir(parents=True)
    (tree / 'a' / 'b' / 'f').write_text('x')
    os.chflags(tree / 'a' / 'b' / 'f', stat.UF_IMMUTABLE)
    os.chmod(tree / 'a' / 'b', 0)
    (tree / 'link').symlink_to(tmp_path / 'elsewhere')
    session._remove(tree)
    assert not tree.exists()


def test_a_directory_swapped_for_a_link_during_the_walk_is_refused(tmp_path, monkeypatch):
    secret = tmp_path / 'host-secrets'
    secret.mkdir()
    (secret / 'key').write_text('do not copy')
    tree = tmp_path / 'tree'
    (tree / 'a').mkdir(parents=True)
    (tree / 'a' / 'f').write_text('fine')
    real = containers.open_directory

    def racing(name, dir_fd=None):
        if dir_fd is not None and name == 'a':  # a surviving writer swaps 'a' after it was listed
            os.rename('a', 'a-moved', src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            os.symlink(secret, 'a', dir_fd=dir_fd)
        return real(name, dir_fd)

    monkeypatch.setattr(containers, 'open_directory', racing)
    with pytest.raises(UnsafeTree):
        containers.read_tree(tree, limit=1 << 20)


def test_tree_limits_refuse_before_reading_and_never_truncate(tmp_path):
    sparse = tmp_path / 'sparse'
    sparse.mkdir()
    with open(sparse / 'big', 'wb') as handle:
        handle.truncate(1 << 30)  # 1 GiB apparent, almost no blocks: refused from fstat alone
    with pytest.raises(UnsafeTree, match='size limit'):
        containers.read_tree(sparse, limit=4 << 20)
    exact = tmp_path / 'exact'
    exact.mkdir()
    (exact / 'f').write_bytes(b'12345')
    with pytest.raises(UnsafeTree, match='size limit'):
        containers.read_tree(exact, limit=4)
    assert containers.read_tree(exact, limit=5) == {'f': b'12345'}
    many = tmp_path / 'many'
    many.mkdir()
    for index in range(6):
        (many / f'f{index}').write_text('x')
    with pytest.raises(UnsafeTree, match='entries'):
        containers.read_tree(many, limit=1 << 20, max_entries=5)


def test_an_unreadable_file_refuses_only_its_draft(tmp_path):
    drafts = Drafts(tmp_path / 'state')
    source = tmp_path / 'ws'
    (source / 'locked').mkdir(parents=True)
    (source / 'locked' / 'f').write_text('x')
    os.chmod(source / 'locked' / 'f', 0)
    (source / 'open').mkdir()
    (source / 'open' / 'f').write_text('y')
    try:
        report = drafts.collect(source, 'sess', {})
    finally:
        os.chmod(source / 'locked' / 'f', 0o600)
    assert report['created'] == ['open'] and [r['id'] for r in report['refused']] == ['locked']


def test_a_failure_while_collecting_submissions_is_sealed(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    workspace = tmp_path / 'ws'
    for name in session.WRITABLE:
        (workspace / name).mkdir(parents=True)
    submission(workspace, [dict(op='add_fact', fact=fact('seed-fact'))])
    record_dir = tmp_path / 'record'
    record_dir.mkdir()

    def exhausted(*_args, **_kwargs):
        raise MemoryError

    monkeypatch.setattr(session, 'read_tree', exhausted)
    result = sandbox.Result(0, None, 0, 0, 0.1, [])
    record = session._close_out(repo, 'sess', record_dir, workspace, None, result, [], FRAMES, COVERAGE,
                                Drafts(repo.state), {})
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and any('MemoryError' in e for e in life['errors'])
    assert record['verdicts'] == [] and (record_dir / 'close-out.json').is_file()


def test_submission_names_cannot_add_lines_to_the_commit_message(tmp_path):
    repo = make_repo(tmp_path)
    verdict = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))],
                                   name='s1\nCo-Authored-By: someone <x@example.com>'))
    assert (verdict['status'] == 'published')
    message = git(repo, 'log', '-1', '--format=%B')
    assert not any(line.startswith('Co-Authored-By') for line in message.splitlines())


def test_the_draft_digest_separates_names_from_contents(tmp_path):
    one, two = tmp_path / 'one', tmp_path / 'two'
    one.mkdir()
    two.mkdir()
    (one / 'a').write_bytes(b'1\x00b\x002')  # equal to two's files under a NUL-separated digest
    (two / 'a').write_bytes(b'1')
    (two / 'b').write_bytes(b'2')
    assert containers._digest(one) != containers._digest(two)


def test_subject_is_optional_and_seen_is_the_latest_cited_position(tmp_path):
    repo = make_repo(tmp_path)
    item = fact(citations=[FRAME2, FRAME1])
    del item['subject']
    verdict = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': item}]))
    assert (verdict['status'] == 'published'), verdict['diagnostics']
    assert repo.facts()[0]['seen'] == dict(session='s1', actor='001', step=2, order=[1, '001', 2])


@pytest.mark.parametrize('first_step, replay_step', [(41, 42), (42, 41)])
def test_shared_frame_keeps_its_first_published_position_across_windows(tmp_path, first_step, replay_step):
    repo = make_repo(tmp_path)
    windows = [(FRAME1, first_step), (FRAME1, replay_step), (FRAME2, 43)]
    expected_positions = {}
    for index, (frame, step) in enumerate(windows, 1):
        position = dict(session='s1', actor='001', step=step, order=[1, '001', step])
        expected_positions.setdefault(frame, position)
        changes = [dict(op='add_fact', fact=fact(f'f{index}', citations=[frame]))]
        directory = submission(tmp_path, changes, name=f'window-{index}', base_version=f'v{index - 1}')
        verdict = gate(repo, directory, session_id=f'curator-{index}', window_frames={frame: position},
                       coverage={**COVERAGE, 'last_step': step}, session_kind='admission')
        version = f'v{index}'
        assert (verdict['status'], verdict['version']) == ('published', version), verdict['diagnostics']
        assert repo.provenance(version)['frames'] == expected_positions
        assert [item['seen'] for item in repo.facts(version)] == [expected_positions[frame] for frame, _ in windows[:index]]

    assert set(_history(repo)[0]) == {'v0', 'v1', 'v2', 'v3'}


def test_the_gate_rejects_invalid_candidate_frame_positions_before_commit(tmp_path, monkeypatch):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    monkeypatch.setattr(repo, 'commit', lambda *args: pytest.fail('invalid candidate reached commit'))
    position = dict(session='s1', actor='001', step='42', order=[1, '001', 42])
    directory = submission(tmp_path, [dict(op='add_fact', fact=fact('f2', citations=[FRAME3]))], base_version='v1')
    verdict = gate(repo, directory, session_id='sess', window_frames={FRAME3: position},
                   coverage={**COVERAGE, 'last_step': 42}, session_kind='admission')
    assert (verdict['status'], verdict['version']) == ('rejected', None)
    assert verdict['diagnostics'] == ['invalid candidate snapshot: invalid frame position']
    assert snapshot(repo) == before


def old_contract_repository(tmp_path):
    repo = make_repo(tmp_path)
    old = {'schema': 'curator-fact/2', 'id': 'old', 'type': 'mechanic', 'statement': 's', 'scope': {'game': 'cdda'},
           'citations': ['frame-1'], 'published_in': 'v1', 'session': 'x'}
    repo.commit({'facts.jsonl': (json.dumps(old) + '\n').encode()}, 'Publish v1')
    return repo


@pytest.mark.parametrize('change', [
    lambda: {'op': 'supersede_fact', 'ids': ['old'], 'reason_kind': 'restated', 'fact': fact('new')},
    lambda: {'op': 'add_fact', 'fact': fact('new')}])
def test_the_gate_does_not_publish_into_a_repository_holding_facts_of_another_contract(tmp_path, change):
    repo = old_contract_repository(tmp_path)
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, [change()], base_version='v1'))
    assert not (verdict['status'] == 'published') and len(verdict['diagnostics']) == 1
    assert verdict['diagnostics'][0].startswith('publication failed: incompatible history at v1:')
    assert snapshot(repo) == before and repo.published() == 'v1'


def test_the_coverage_stamp_is_published_with_the_version_and_changes_with_it(tmp_path):
    repo = make_repo(tmp_path)
    assert not (repo.path / 'coverage.json').exists()
    first = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))]))
    assert (first['status'] == 'published')
    assert json.loads(git(repo, 'show', 'v1:coverage.json')) == COVERAGE
    later = {**COVERAGE, 'last_step': 40}
    second = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}], name='s2', base_version='v1'),
                 coverage=later)
    assert (second['status'] == 'published')
    assert json.loads(git(repo, 'show', 'v2:coverage.json')) == later
    assert json.loads(git(repo, 'show', 'v1:coverage.json')) == COVERAGE  # each version keeps its own


@pytest.mark.parametrize('where', ['top', 'change', 'fact'])
def test_a_submission_cannot_set_the_coverage_stamp(tmp_path, where):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    changes = [{'op': 'add_fact', 'fact': fact()}]
    top = {}
    if where == 'top':
        top['coverage'] = {**COVERAGE, 'last_step': 999}
    elif where == 'change':
        changes[0]['coverage'] = COVERAGE
    else:
        changes[0]['fact']['coverage'] = COVERAGE
    verdict = run(repo, submission(tmp_path, changes, **top))
    assert not (verdict['status'] == 'published') and any('Additional properties' in d and 'coverage' in d for d in verdict['diagnostics'])
    assert snapshot(repo) == before


@pytest.mark.parametrize('stamp', [None, {}, {**COVERAGE, 'extra': 1}, {**COVERAGE, 'schema': 'curator-coverage/0'},
                                   {**COVERAGE, 'last_step': '20'}, {**COVERAGE, 'session': ''}])
def test_a_bad_stamp_from_the_runner_publishes_nothing(tmp_path, stamp):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))]), coverage=stamp)
    assert not (verdict['status'] == 'published') and any('coverage' in d for d in verdict['diagnostics'])
    assert snapshot(repo) == before


@pytest.mark.parametrize('schema', ['curator-knowledge/3', 'curator-knowledge/4', None])
def test_repository_refuses_other_layout_schemas_for_every_reader_and_writer(tmp_path, schema):
    repo = make_repo(tmp_path)
    repo.commit({'knowledge.json': json.dumps(dict(schema=schema, game='cdda')).encode()}, 'foreign layout')
    before = snapshot(repo)
    for action in [repo.ensure, repo.published, repo.records, repo.provenance,
                   lambda: repo.export('v1', tmp_path/'export'), lambda: repo.commit({}, 'forbidden')]:
        with pytest.raises(KnowledgeError, match='expected curator-knowledge/5; start a new repository'):
            action()
    verdict = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))], base_version='v1'))
    assert not (verdict['status'] == 'published') and 'start a new repository' in verdict['diagnostics'][0]
    assert snapshot(repo) == before


def test_gate_requires_an_explicit_session_kind():
    import inspect
    assert inspect.signature(gate).parameters['session_kind'].default is inspect.Parameter.empty


@pytest.mark.parametrize('options, expected', [
    ({'session_kind': 'unknown'}, 'unknown session kind'),
    ({'session_kind': 'grooming', 'window': session.Window('s1', '001', 1, 2)}, 'not a window'),
])
def test_run_session_refuses_invalid_session_selection(tmp_path, options, expected):
    with pytest.raises(session.SessionError, match=expected):
        session.run_session(make_repo(tmp_path), [], session.SessionConfig(argv=('unused',)), **options)


@pytest.mark.parametrize('problem, expected', [
    ('no-admission', 'grooming needs a published admission'),
    ('wrong-trace', 'grooming trace must be the last admission'),
    ('old-record', 'curator-fact/6'),
    ('old-layout-file', 'unsupported snapshot layout'),
    ('old-layout', 'expected curator-knowledge/5; start a new repository'),
])
def test_session_preparation_refuses_invalid_grooming_inputs_before_starting_a_host(tmp_path, monkeypatch, problem, expected):
    from tests.curator_trace import make_long_session

    repo = make_repo(tmp_path) if problem == 'no-admission' else seeded(tmp_path)
    if problem == 'old-record':
        repo.commit({'facts.jsonl': (json.dumps(fact(schema='curator-fact/5'))+'\n').encode()}, 'old record')
    elif problem == 'old-layout-file':
        repo.commit({'ontology/types.json': b'[]'}, 'obsolete layout file')
    if problem == 'old-layout':
        repo.commit({'knowledge.json': json.dumps(dict(schema='curator-knowledge/2', game='cdda')).encode()}, 'old layout')
    trace = make_long_session(tmp_path/'evidence', name='other' if problem == 'wrong-trace' else 's1')
    def forbidden(*args, **kwargs):
        pytest.fail('invalid session inputs must not start a host')
    monkeypatch.setattr(sandbox, 'run', forbidden)
    record = session.run_session(repo, [trace], session.SessionConfig(argv=('unused',)), session_kind='grooming')
    assert record['manifest']['lifecycle']['state'] == 'aborted'
    assert any(expected in e for e in record['manifest']['lifecycle']['errors']), record
    assert record['verdicts'] == []


def test_grooming_without_a_configured_brief_aborts_before_host_start(tmp_path, monkeypatch):
    from tests.curator_trace import frame_id, make_long_session

    repo = make_repo(tmp_path)
    trace = make_long_session(tmp_path/'evidence')
    citation = frame_id(1, 1)
    assert run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact(citations=[citation]))]),
               frames={citation})['status'] == 'published'
    started = []
    def forbidden(*args, **kwargs):
        started.append(True)
        pytest.fail('missing grooming brief must not start a host')
    monkeypatch.setattr(sandbox, 'run', forbidden)
    record = session.run_session(repo, [trace], session.SessionConfig(argv=('unused',)), session_kind='grooming')
    assert record['manifest']['lifecycle']['state'] == 'aborted'
    assert record['manifest']['lifecycle']['errors'] == [
        'session: SessionError: grooming needs a configured grooming brief']
    assert record['verdicts'] == [] and not started
    assert repo.published() == 'v1'


@pytest.mark.parametrize('metadata', [None, b'{', b'\xff'], ids=['missing', 'invalid-json', 'invalid-encoding'])
def test_unreadable_knowledge_metadata_is_an_unsupported_schema_and_gate_rejection(tmp_path, metadata):
    repo = make_repo(tmp_path)
    if metadata is None:
        (repo.path/'knowledge.json').unlink()
        files = {}
    else:
        files = {'knowledge.json': metadata}
    repo.commit(files, 'invalid metadata fixture')
    before = snapshot(repo)
    for read in [repo.published, repo.ensure, repo.records]:
        with pytest.raises(KnowledgeError, match='unsupported knowledge schema:.*start a new repository'):
            read()
    verdict = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('seed-fact'))], base_version='v1'))
    assert not (verdict['status'] == 'published') and len(verdict['diagnostics']) == 1
    assert 'unsupported knowledge schema:' in verdict['diagnostics'][0]
    assert 'start a new repository' in verdict['diagnostics'][0]
    assert snapshot(repo) == before




def change_fact(id='f1', **kwargs):
    return dict(op='add_fact', fact=fact(id, **kwargs))


def change_article(slug='guide', **kwargs):
    return dict(op='add_article', article=article(slug, **kwargs))


def restate(id, replacement, **kwargs):
    return dict(op='supersede_fact', ids=[id], reason_kind='restated',
                fact=fact(replacement, citations=[], **kwargs))


def public_rows(repo):
    return {check.owner(row): row for row in repo.records() if current(row)}


def publish(repo, tmp_path, changes, *, name=None, base=None, **kwargs):
    base = base or repo.published()
    directory = submission(tmp_path, changes, name=name or base, base_version=base)
    return run(repo, directory, **kwargs)


def test_grooming_combines_remap_edit_revise_and_retag_into_one_revision(tmp_path):
    repo = make_repo(tmp_path)
    original_claim = {'text': '  Verbatim  ', 'facts': ['extra']}
    body = [{'text': 'First claim.', 'facts': ['f1']}, original_claim]
    assert publish(repo, tmp_path, [change_fact(), change_fact('extra'),
                                    change_article(body=body)])['status'] == 'published'
    edited = dict(index=0, old_text='First claim.', old_facts=['f2'], text='First edited.', facts=['f2'])
    verdict = publish(repo, tmp_path, [
        restate('f1', 'f2'),
        dict(op='remap_citations', **{'from': ['f1'], 'to': 'f2', 'in': ['guide']}),
        dict(op='edit_article', slug='guide', replace_claims=[edited], add_tags=['fire']),
        dict(op='retag', assignments={'guide': ['cook']}),
        dict(op='revise_article', slug='guide', title='Revised title'),
    ], session_kind='grooming', frames=set())
    assert verdict['status'] == 'published', verdict
    old, new = repo.articles()
    assert old['id'] == 'guide@v1' and old['superseded_by'] == ['guide@v2']
    assert new['id'] == 'guide@v2' and new['title'] == 'Revised title'
    assert new['body'] == [{'text': 'First edited.', 'facts': ['f2']}, original_claim]
    assert new['retagged'] == [{'from': ['fire'], 'to': ['cook'], 'version': 'v2'}]
    assert new['tags'] == ['cook'] and new['stale_citations'] == []
    assert publish(repo, tmp_path, [dict(op='retag', assignments={'guide': ['camp']})],
                   session_kind='grooming')['status'] == 'published'
    assert [row['id'] for row in repo.articles()] == ['guide@v1', 'guide@v2']
    assert repo.articles()[-1]['retagged'][-1] == {'from': ['cook'], 'to': ['camp'], 'version': 'v3'}


@pytest.mark.parametrize('operation, diagnostic', [
    (dict(remove_claims=[dict(index=2, old_text='An arbitrary claim.', old_facts=['f1'])]), 'out of range'),
    (dict(remove_claims=[dict(index=0, old_text='An arbitrary claim.', old_facts=['f2'])]), 'old_text or old_facts'),
    (dict(remove_claims=[dict(index=0, old_text='An arbitrary claim.', old_facts=['f1'])]), 'empty'),
    (dict(remove_claims=[dict(index=0, old_text='An arbitrary claim.', old_facts=['f1'])],
          replace_claims=[dict(index=0, old_text='An arbitrary claim.', old_facts=['f1'],
                               text='Edited.', facts=['f1'])]), 'duplicate claim index'),
])
def test_edit_claim_guards_are_atomic(tmp_path, operation, diagnostic):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact(), change_article()])['status'] == 'published'
    before = repo.snapshot('v1')
    reject = publish(repo, tmp_path, [dict(op='edit_article', slug='guide', **operation)])
    assert reject['status'] == 'rejected' and diagnostic in reject['diagnostics'][0]
    assert repo.snapshot(repo.published()) == before


def test_retired_article_slug_is_reserved_and_retirement_names_conflicting_operation(tmp_path):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact(), change_article()])['status'] == 'published'
    retire = dict(op='retire_article', slug='guide', reason_kind='editorial', reason='Combine the pages.')
    conflict = publish(repo, tmp_path, [retire, dict(op='retag', assignments={'guide': ['camp']})],
                       name='both', session_kind='grooming')
    assert conflict['status'] == 'rejected' and 'retag' in conflict['diagnostics'][0]
    assert publish(repo, tmp_path, [retire])['status'] == 'published'
    assert repo.articles()[0]['lifecycle_state'] == 'ended'
    assert repo.articles()[0]['valid_to'] is None
    reject = publish(repo, tmp_path, [change_fact('guide')])
    assert reject['status'] == 'rejected' and 'not new' in reject['diagnostics'][0]


def test_remaps_support_restated_chains_and_n_to_1_merges_for_articles(tmp_path):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact(), change_fact('other'),
                                    change_article(facts=['f1', 'other'])])['status'] == 'published'
    assert publish(repo, tmp_path, [restate('f1', 'f2')], frames=set())['status'] == 'published'
    assert repo.articles()[-1]['stale_citations'] == ['f1']
    remap = dict(op='remap_citations', **{'from': ['f1', 'other'], 'to': 'f3', 'in': ['guide']})
    merge = dict(restate('f2', 'f3'), ids=['f2', 'other'])
    assert publish(repo, tmp_path, [merge, remap], frames=set(),
                   session_kind='grooming')['status'] == 'published'
    assert public_rows(repo)['guide']['body'] == [{'text': 'An arbitrary claim.', 'facts': ['f3']}]


def test_correction_retracts_and_requires_a_fresh_frame(tmp_path):
    repo = seeded(tmp_path)
    corrected = dict(op='supersede_fact', ids=['f1'], reason_kind='corrected', fact=fact('f2'))
    rejected = publish(repo, tmp_path, [corrected], name='repeat')
    assert 'new frame' in rejected['diagnostics'][0]
    corrected['fact']['citations'] = [FRAME2]
    assert publish(repo, tmp_path, [corrected])['status'] == 'published'
    old, new = repo.facts()
    assert old['lifecycle_state'] == 'retracted' and old['superseded_by'] == ['f2']
    assert new['citations'] == [FRAME2]


def labels(name='s1', *, world='pond', lineage='main', admission=1, **extra):
    return dict(name=name, world=world, lineage=lineage, admission=admission, context={'mode': 'hard'}) | extra


def test_declared_scope_compatibility_world_bindings_and_article_scope(tmp_path):
    repo = make_repo(tmp_path)
    wrong = publish(repo, tmp_path, [change_fact(scope={'weather': 'dry'})], name='axis',
                    session_labels={SEALED: labels()})
    assert "declared axes: ['mode']" in wrong['diagnostics'][0]
    good = publish(repo, tmp_path, [
        change_fact(scope={'mode': 'hard'}, binds=['world'], statement_kind='state', state_key='key-f1'),
        change_article(),
    ], session_labels={SEALED: labels()})
    assert good['status'] == 'published', good
    f1, guide = repo.records()
    assert guide['scope'] == f1['scope'] == dict(game=repo.game, world='pond', mode='hard')
    assert guide['lineages'] == f1['lineages'] == ['main']
    assert guide['valid_from'] == f1['valid_from'] and guide['last_confirmed'] == f1['seen']


@pytest.mark.parametrize('world, diagnostic', [(None, 'no recorded world'), ('forest', 'span two worlds')])
def test_world_bound_fact_refuses_unknown_or_mixed_worlds(tmp_path, world, diagnostic):
    repo = make_repo(tmp_path)
    other = '2' * 32
    frame = f'{other}-1'
    result = publish(repo, tmp_path, [change_fact(citations=[FRAME1, frame], binds=['world'])],
                     frames={FRAME1, frame},
                     session_labels={SEALED: labels(), other: labels('s2', world=world, lineage=None, admission=None)})
    assert result['status'] == 'rejected' and diagnostic in result['diagnostics'][0]


def test_narrow_preserves_when_scope_and_evidence_without_booking_inherited_frames(tmp_path):
    repo = make_repo(tmp_path)
    when = '  In this condition.  '
    source_labels = {SEALED: labels(context={'mode': 'hard', 'patch': 'one'})}
    assert publish(repo, tmp_path, [change_fact(when=when, scope={'patch': 'one'})],
                   frames={FRAME1}, session_labels=source_labels)['status'] == 'published'
    children = [fact('hard', citations=[FRAME1], scope={'patch': 'one', 'mode': 'hard'}, when=when),
                fact('easy', citations=[FRAME2], scope={'patch': 'one', 'mode': 'easy'}, when=when)]
    operation = dict(op='narrow_fact', id='f1', facts=children)
    for name, override, diagnostic in [
        ('condition', {'when': 'Different condition.'}, 'preserve the parent when'),
        ('scope', {'scope': {'patch': 'one'}}, 'strictly narrow'),
        ('evidence', {'citations': [FRAME2]}, 'carry over'),
    ]:
        rejected = publish(repo, tmp_path, [dict(operation, facts=[dict(children[0], **override), children[1]])],
                           name=name, frames={FRAME2}, session_labels=source_labels)
        assert diagnostic in rejected['diagnostics'][0]
    result = publish(repo, tmp_path, [operation], frames={FRAME2}, session_labels=source_labels,
                     coverage=dict(COVERAGE, session='s2'))
    assert result['status'] == 'published', result
    old, hard, easy = repo.facts()
    assert old['superseded_by'] == ['hard', 'easy'] and old['lifecycle_state'] == 'superseded'
    assert hard['when'] == easy['when'] == when
    assert repo.provenance()['last_admission']['citations'] == [FRAME2]


def test_grooming_checks_stale_owner_pairs_after_the_batch(tmp_path):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact(), change_fact('other'), change_article(),
                                    change_article('second', title='Second', facts=['other'])])['status'] == 'published'
    assert publish(repo, tmp_path, [restate('f1', 'replacement')])['status'] == 'published'
    revise = dict(op='revise_article', slug='guide', lead='Partial work.')
    assert publish(repo, tmp_path, [revise], session_kind='grooming')['status'] == 'published'
    remap = dict(op='remap_citations', **{'from': ['f1'], 'to': 'replacement', 'in': ['guide']})
    move = dict(op='revise_article', slug='second', body=[dict(text='Move debt.', facts=['f1'])])
    rejection = publish(repo, tmp_path, [remap, move], name='move', session_kind='grooming')
    assert rejection['status'] == 'rejected' and "('second', 'f1')" in rejection['diagnostics'][0]
    assert publish(repo, tmp_path, [remap], session_kind='grooming')['status'] == 'published'
    assert public_rows(repo)['guide']['stale_citations'] == []


def test_fixed_point_is_idempotent_and_order_independent_on_seeded_and_unseeded_cycles(tmp_path):
    fixture = build_cycle_and_withholding_repo(tmp_path)
    repo = Repository(tmp_path, fixture['game'])
    _history(repo)
    rows = repo.records()
    baseline = {row['id']: row for row in rows}
    random.Random(712).shuffle(rows)
    for _ in range(2):
        check.recompute_flags(rows)
        assert {row['id']: row for row in rows} == baseline
    assert not baseline['clean-cycle-a']['needs_review']
    assert baseline['dirty-cycle-b']['needs_review'] and baseline['stale-cycle-b']['needs_review']
    damaged = deepcopy(rows)
    item = next(row for row in damaged if row['id'] == 'clean-cycle-a')
    item['needs_review'] = True
    with pytest.raises(ValueError, match='incorrect stored needs_review'):
        check.validate_snapshot(damaged, repo.provenance(), repo.game, repo.published())


def test_minimal_changes_over_random_sequences(tmp_path):
    repo = make_repo(tmp_path)
    opts = dict(session_labels={SEALED: labels()})
    independent = change_fact('unrelated')
    body = [dict(text='Untouched claim.', facts=['unrelated']), dict(text='Repairable claim.', facts=['f1'])]
    when = 'Only hard.'
    assert publish(repo, tmp_path, [change_fact(scope={'mode': 'hard'}, when=when), independent,
                                    change_article(body=body)], **opts)['status'] == 'published'
    rng = random.Random(937)
    old = 'f1'
    for number in range(12):
        before = public_rows(repo)
        choice = rng.choice(('replace', 'remap', 'edit', 'conflict'))
        if before[old]['lifecycle_state'] == 'contested' and choice in ('replace', 'remap'):
            choice = 'edit'
        new = f'next-{number}'
        if choice in ('replace', 'remap'):
            operations = [
                restate(old, new, scope={'mode': 'hard'}, when=when),
                dict(op='remap_citations', **{'from': [old], 'to': new, 'in': ['guide']}),
            ]
        elif choice == 'edit':
            operations = [dict(op='edit_article', slug='guide', set_lead=f'Changed lead {number}.')]
        else:
            operations = [
                change_fact(new, scope={'mode': 'hard'}, links=[{'rel': 'contradicts', 'target': old}]),
                change_fact(f'disjoint-{number}', scope={'mode': 'easy'},
                            when='Only easy.',
                            links=[{'rel': 'contradicts', 'target': old}]),
            ]
        result = publish(repo, tmp_path, operations, **opts)
        assert result['status'] == 'published', result
        after = public_rows(repo)
        assert json.dumps(after['unrelated']) == json.dumps(before['unrelated'])
        assert json.dumps(after['guide']['body'][0]) == json.dumps(before['guide']['body'][0])
        if choice in ('replace', 'remap'):
            assert set(before[old]['citations']) <= set(after[new]['citations'])
            assert after[new]['scope'] == before[old]['scope']
            old = new
        if choice == 'conflict':
            assert after[old]['lifecycle_state'] == after[new]['lifecycle_state'] == 'contested'
            assert after[f'disjoint-{number}']['lifecycle_state'] == 'active'
            assert after['guide']['lifecycle_state'] == 'contested'


def end_fact(id='f1', *, end='absence', end_citations=(FRAME2,), citations=()):
    return dict(op='retire_fact', id=id, reason_kind='ended', reason='Observed an end.', end=end,
                end_citations=list(end_citations), citations=list(citations))


@pytest.mark.parametrize('end, step', [('absence', 2), ('transition', 3)])
def test_end_time_uses_only_end_evidence_and_keeps_origin(tmp_path, end, step):
    repo = make_repo(tmp_path)
    session_labels = {SEALED: labels()}
    assert publish(repo, tmp_path, [change_fact(binds=['world'])], frames={FRAME1},
                   session_labels=session_labels)['status'] == 'published'
    frame4 = f'{SEALED}-4'
    frames = {f'{SEALED}-{seq}': position('s1', seq) for seq in range(1, 5)}
    overlap = end_fact(end_citations=[FRAME1])
    rejected = publish(repo, tmp_path, [overlap], name='overlap', frames=frames, session_labels=session_labels)
    assert 'disjoint' in rejected['diagnostics'][0]
    evidence = end_fact(end=end, end_citations=[FRAME3, FRAME2], citations=[frame4])
    result = publish(repo, tmp_path, [evidence], frames=frames, session_labels=session_labels)
    assert result['status'] == 'published', result
    record = repo.facts()[0]
    assert record['seen'] == frames[FRAME1] and record['citations'] == [FRAME1]
    assert record['lifecycle_state'] == 'ended' and record['valid_to'] == position('s1', step)
    assert record['retired']['events'][0]['valid_to'] == record['valid_to']
    assert 'already has a visible end' in publish(
        repo, tmp_path, [end_fact(end_citations=[frame4])], frames=frames, session_labels=session_labels)['diagnostics'][0]


def test_a_branch_end_does_not_end_a_fact_on_its_parent(tmp_path):
    repo = make_repo(tmp_path)
    parent = {SEALED: labels()}
    assert publish(repo, tmp_path, [change_fact(binds=['world'])], frames={FRAME1},
                   session_labels=parent)['status'] == 'published'
    child_id = '2' * 32
    child_frame = f'{child_id}-1'
    child = {child_id: labels('s2', lineage='fork', branch={'parent': 'main', 'fork_at': position('s1', 1),
                                                            'fork_version': 'v1'})}
    result = publish(repo, tmp_path, [end_fact(end_citations=[child_frame])],
                     frames={child_frame: position('s2', 1, order_index=2)}, session_labels=child)
    assert result['status'] == 'published', result
    row = repo.facts()[0]
    assert check.ended_still_alive(row, parent[SEALED], repo.provenance())
    assert not check.ended_still_alive(row, child[child_id], repo.provenance())
    again = publish(repo, tmp_path, [end_fact()], frames={FRAME2: position('s1', 2)}, session_labels=parent)
    assert again['status'] == 'published', again
    row = repo.facts()[0]
    assert row['valid_to'] is None and len(row['retired']['events']) == 2
    _history(repo)


@pytest.mark.parametrize('saved_step, seen_step, expected', [(2, 3, 'rejected'), (2, 1, 'published'), (None, 1, 'rejected')])
def test_world_end_checks_restore_segments(tmp_path, saved_step, seen_step, expected):
    repo = make_repo(tmp_path)
    seen_frame = f'{SEALED}-{seen_step}'
    assert publish(repo, tmp_path, [change_fact(citations=[seen_frame], binds=['world'])],
                   frames={seen_frame: position('s1', seen_step)}, session_labels={SEALED: labels()})['status'] == 'published'
    restore_row = dict(lineage='main', restored_at=position('s1', 4), restored_version='v1',
                       saved_at=position('s1', saved_step) if saved_step else None, saved_version='v1' if saved_step else None)
    end_frame = f'{SEALED}-5'
    result = publish(repo, tmp_path, [end_fact(end_citations=[end_frame])],
                     frames={end_frame: position('s1', 5)}, session_labels={SEALED: labels(restores=[restore_row])})
    assert result['status'] == expected, result
    if expected == 'rejected':
        assert 'surviving timeline' in result['diagnostics'][0]


def test_unbound_end_is_right_censored_and_requires_later_frames(tmp_path):
    repo = make_repo(tmp_path)
    frames = {FRAME1: position('s1', 3), FRAME2: position('s1', 2), FRAME3: position('s1', 4)}
    assert publish(repo, tmp_path, [change_fact()], frames=frames)['status'] == 'published'
    reject = publish(repo, tmp_path, [end_fact()], name='before', frames=frames)
    assert 'strictly after' in reject['diagnostics'][0]
    assert publish(repo, tmp_path, [end_fact(end_citations=[FRAME3])], frames=frames)['status'] == 'published'
    row = repo.facts()[0]
    assert row['lifecycle_state'] == 'ended' and row['valid_to'] is None
    assert row['retired']['events'][0]['valid_to'] is None


def test_retire_wrong_is_terminal_and_checks_evidence_world(tmp_path):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact(binds=['world'])], session_labels={SEALED: labels()})['status'] == 'published'
    sid = '7' * 32
    frame = f'{sid}-1'
    wrong = dict(op='retire_fact', id='f1', reason_kind='wrong', reason='Corrected evidence.', citations=[frame])
    refusal = publish(repo, tmp_path, [wrong], name='other-world', frames={frame},
                      session_labels={sid: labels('s2', world='other', lineage='elsewhere')})
    assert 'must belong to the fact' in refusal['diagnostics'][0]
    wrong['citations'] = [FRAME2]
    assert publish(repo, tmp_path, [wrong])['status'] == 'published'
    row = repo.facts()[0]
    assert row['lifecycle_state'] == 'retracted' and row['valid_to'] is None
    assert row['retired']['citations'] == [FRAME2]
    assert publish(repo, tmp_path, [end_fact()])['status'] == 'rejected'


def validation_workspace(repo, tmp_path, frames, *, kind='admission', incoming=None):
    workspace = tmp_path / 'sess'
    base = repo.published()
    _, reserved_ids, reservations, reserved_state_keys = _history(repo)
    repo.export(base, workspace / 'knowledge')
    context = dict(base_version=base, reserved_ids=sorted(reserved_ids), reserved_state_keys=sorted(reserved_state_keys), reserved_sessions=reservations,
                   session_kind=kind, window_frames=frames, session_labels=incoming or {},
                   declared_axes=sorted(check.declared_axes(reservations, incoming or {})))
    (workspace/'knowledge'/'validation-context.json').write_text(json.dumps(context))
    return workspace


def test_validation_parity_for_ordered_multi_submission_repairs_with_a_rejected_prefix_file(tmp_path):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact(), change_article()])['status'] == 'published'
    assert publish(repo, tmp_path, [restate('f1', 'new')])['status'] == 'published'
    workspace = validation_workspace(repo, tmp_path, {}, kind='grooming')
    submissions = [
        submission(workspace, [dict(op='revise_article', slug='guide', title='Stale')],
                   name='01', base_version='v1'),
        submission(workspace, [dict(op='revise_article', slug='guide', title='Partial')],
                   name='02', base_version='v2'),
        submission(workspace, [dict(op='remap_citations', **{'from': ['f1'], 'to': 'new', 'in': ['guide']})],
                   name='03', base_version='v3'),
    ]
    result = validate(workspace, '03')
    assert result['ok'] and not result['all_passed']
    assert [entry['candidate_version'] for entry in result['prefix']] == [None, 'v3', 'v4']
    assert repo.published() == 'v2'
    for expected, directory in zip(result['prefix'], submissions):
        assert expected['path'] == f'submissions/{directory.name}/submission.json'
        actual = run(repo, directory, frames={}, session_kind='grooming')
        assert expected['diagnostics'] == actual['diagnostics']
        assert expected['candidate_version'] == actual['version']
    assert public_rows(repo)['guide']['stale_citations'] == []


@pytest.mark.parametrize('different', [
    {'name': 'changed'}, {'world': 'changed'}, {'lineage': 'changed'},
    {'admission': 2}, {'context': {'mode': 'easy'}},
])
def test_validation_and_gate_reserve_session_labels_across_restore(tmp_path, different):
    repo = make_repo(tmp_path)
    assert publish(repo, tmp_path, [change_fact()], session_labels={SEALED: labels()})['status'] == 'published'
    assert restore(repo, expected_base='v1', target='v0')['version'] == 'v2'
    incoming = {SEALED: labels() | different}
    positions = {FRAME1: position(incoming[SEALED]['name'], 1)}
    workspace = validation_workspace(repo, tmp_path, positions, incoming=incoming)
    path = submission(workspace, [change_fact('new')], name='01', base_version='v2')
    result = validate(workspace, '01')
    verdict = run(repo, path, frames=positions, session_labels=incoming)
    assert not result['ok'] and verdict['status'] == 'rejected'
    assert result['diagnostics'] == verdict['diagnostics']
    assert 'different recorded labels' in verdict['diagnostics'][0]


def test_validation_reports_the_derived_scope_change_and_matches_the_published_revision(tmp_path):
    repo = make_repo(tmp_path)
    incoming = {SEALED: labels()}
    assert publish(repo, tmp_path, [change_fact(), change_fact('bound', binds=['world']), change_article()],
                   session_labels=incoming)['status'] == 'published'
    workspace = validation_workspace(repo, tmp_path, {}, incoming=incoming)
    edit = dict(op='revise_article', slug='guide', body=[dict(text='A revised claim.', facts=['bound'])])
    path = submission(workspace, [edit], name='01', base_version='v1')
    result = validate(workspace, '01')
    assert result['all_passed'] and result['scope_changes'] == [
        {'slug': 'guide', 'from': {'game': repo.game}, 'to': {'game': repo.game, 'world': 'pond'}},
    ]
    assert run(repo, path, frames={}, session_labels=incoming)['status'] == 'published'
    assert repo.articles()[-1]['scope'] == result['scope_changes'][0]['to']


def test_unicode_line_separator_in_prose_survives_publication_and_validation(tmp_path):
    repo = make_repo(tmp_path)
    prose = 'An observation.\u2028Its implication.'
    assert publish(repo, tmp_path, [change_fact(text=prose)])['status'] == 'published'
    assert repo.records()[0]['text'] == prose
    workspace = validation_workspace(repo, tmp_path, {})
    path = submission(workspace, [restate('f1', 'new', text=prose)], name='01', base_version='v1')
    assert validate(workspace, '01')['ok']
    assert run(repo, path, frames={})['status'] == 'published'
    assert repo.records()[-1]['text'] == prose


def test_branch_conflicts_and_cycles_are_refused(tmp_path):
    repo = make_repo(tmp_path)
    branch = {'parent': 'main', 'fork_at': position('s1', 1), 'fork_version': 'v1'}
    assert publish(repo, tmp_path, [change_fact()], session_labels={SEALED: labels()})['status'] == 'published'
    sid = '2' * 32
    incoming = {sid: labels('s2', lineage='fork', branch=branch)}
    result = publish(repo, tmp_path, [change_fact('fork-note')], session_labels=incoming)
    assert result['status'] == 'published', result
    conflict = {sid: labels('s2', lineage='fork', branch=dict(branch, fork_version='v0'))}
    reject = publish(repo, tmp_path, [change_fact('changed')], name='conflict', session_labels=conflict)
    assert 'conflicting parent, fork_at or fork_version' in reject['diagnostics'][0]
    cycle = {'x': dict(branch, parent='y'), 'y': dict(branch, parent='x')}
    reject = publish(repo, tmp_path, [change_fact('cycle')], name='cycle',
                     session_labels={sid: labels('s2', lineage='fork', branches=cycle)})
    assert 'branch parent cycle' in reject['diagnostics'][0]


@pytest.mark.parametrize('case, expected', [
    ('unknown', 'unknown target'),
    ('self', 'cannot link to itself'),
    ('titles', 'titles and slugs must be unique'),
    ('scopes', 'incompatible scopes'),
])
def test_candidate_refuses_invalid_article_links_titles_and_citation_join(tmp_path, case, expected):
    repo = make_repo(tmp_path)
    scopes = (dict(mode='hard'), dict(mode='easy')) if case == 'scopes' else ({}, {})
    changes = [change_fact(scope=scopes[0]), change_fact('f2', scope=scopes[1])]
    if case == 'scopes':
        changes.append(change_article(facts=['f1', 'f2']))
    elif case == 'titles':
        changes.extend([change_article(), change_article('another')])
    else:
        changes.append(change_article(links=[dict(rel='depends_on', target='guide' if case == 'self' else 'missing')]))
    result = publish(repo, tmp_path, changes, session_labels={SEALED: labels()})
    assert result['status'] == 'rejected' and expected in result['diagnostics'][0]


def test_only_depends_on_and_body_references_are_stale_in_admission(tmp_path):
    repo = make_repo(tmp_path)
    links = [dict(rel=rel, target=target) for rel, target in (
        ('depends_on', 'f1'), ('see_also', 'also'), ('part_of', 'guide'),
    )]
    assert publish(repo, tmp_path, [change_fact(), change_fact('also'), change_article(),
                                    change_fact('dependent', links=links)])['status'] == 'published'
    # 1-to-1 same-reading restatement is followed silently by fact-ID depends_on pins (#1022).
    assert publish(repo, tmp_path, [
        restate('f1', 'new'), restate('also', 'new-also'),
        dict(op='retire_article', slug='guide', reason='Editorial removal.', reason_kind='editorial'),
    ])['status'] == 'published'
    assert public_rows(repo)['dependent']['stale_citations'] == []
    assert public_rows(repo)['dependent']['needs_review'] is False
    # Correcting the terminal reading invalidates the reading pin; see_also and part_of stay non-stale.
    assert publish(repo, tmp_path, [
        dict(op='supersede_fact', ids=['new'], reason_kind='corrected', fact=fact('corrected-f', citations=[FRAME2])),
    ])['status'] == 'published'
    assert public_rows(repo)['dependent']['stale_citations'] == ['f1']
    assert public_rows(repo)['dependent']['needs_review'] is True
