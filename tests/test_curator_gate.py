"""Knowledge repository and gate v0 (#453): publication, rejection and atomicity.

Portable: real Git in tmp_path repositories, no game, no provider.
"""
from __future__ import annotations

import json
import fcntl
import os
from pathlib import Path
import subprocess
import sys

import pytest

from harness.curator import containers, gate as gate_module, knowledge, sandbox, session
from harness.curator.containers import Drafts, UnsafeTree, copy_tree
from harness.curator.gate import _history, gate, restore
from harness.curator.knowledge import KnowledgeError, Repository

FRAMES = {'frame-1', 'frame-2'}


def make_repo(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / 'knowledge', 'cdda')
    repo.ensure()
    return repo


def fact(fact_id='f1', type_name='mechanic', game='cdda', citations=('frame-1',), *,
         known='observed', level='game', **extra):
    return {'schema': 'curator-fact/4', 'record': 'fact', 'id': fact_id, 'type': type_name,
            'text': f'text {fact_id}', 'known': known, 'scope': {'game': game, 'level': level},
            'citations': list(citations), 'subject': 'a thing', **extra}


def kind(name='mechanic', *, identity=(), reason='Define the observed relation.'):
    return {'schema': 'curator-type/2', 'name': name, 'description': 'd', 'fields': ['a'],
            'identity': list(identity), 'reason': reason}


def submission(tmp_path: Path, changes, name='s1', **top) -> Path:
    body = {'schema': 'curator-submission/1', 'base_version': 'v0', 'summary': 'sum',
            'changes': changes, **top}
    directory = tmp_path / 'submissions' / name
    directory.mkdir(parents=True)
    (directory / 'submission.json').write_text(json.dumps(body))
    return directory


COVERAGE = {'schema': 'curator-coverage/2', 'session': 's1', 'actor': '001', 'last_step': 20,}


def run(repo, directory, frames=FRAMES, coverage=COVERAGE, session_kind='admission', *, session_labels=None):
    positions = {frame: dict(session=(session_labels or {}).get(frame.partition('-')[0], {}).get('name', 's1'),
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
    """A repository at v1 holding type 'mechanic' and fact f1."""
    repo = make_repo(tmp_path)
    directory = submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                      {'op': 'add_fact', 'fact': fact()}], name='seed')
    assert run(repo, directory)['version'] == 'v1'
    return repo


def test_restore_exact_v0_and_reserves_historical_identity(tmp_path):
    repo = seeded(tmp_path)
    before = repo.snapshot('v0')
    result = restore(repo, expected_base='v1', target='v0')
    assert result['status'] == 'published' and result['version'] == 'v2'
    assert repo.snapshot('v2') == before and not (repo.path/'coverage.json').exists()
    repeated = restore(repo, expected_base='v2', target='v0')
    assert repeated['status'] == 'unchanged' and repeated['version'] == 'v2'
    again = run(repo, submission(tmp_path, [dict(op='add_type', type=kind()),
                dict(op='add_fact', fact=fact())], name='reuse', base_version='v2'))
    assert again['status'] == 'rejected' and any('not new' in d for d in again['diagnostics'])


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


def test_restored_export_preserves_ages_and_existing_delivery(tmp_path):
    from tools.knowledge_export import export, published
    repo = seeded(tmp_path)
    original = published(repo.path, 'v1')
    export(tmp_path/'frozen', original)
    frozen = (tmp_path/'frozen'/'delivered-knowledge.json').read_bytes()
    newer = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('f2'))],
                                     name='newer', base_version='v1'))
    assert newer['status'] == 'published'
    result = restore(repo, expected_base='v2', target='v1')
    assert result['status'] == 'published' and result['version'] == 'v3'
    restored = published(repo.path, 'v3')
    assert restored['version'] == 'v3'
    assert {key: restored[key] for key in ('coverage', 'articles', 'facts')} == {
        key: original[key] for key in ('coverage', 'articles', 'facts')}
    assert (tmp_path/'frozen'/'delivered-knowledge.json').read_bytes() == frozen


def test_ensure_is_idempotent_and_starts_at_v0(tmp_path):
    repo = Repository(tmp_path / 'knowledge', 'cdda')
    assert repo.ensure() == 'v0'
    before = snapshot(repo)
    assert repo.ensure() == 'v0'
    assert snapshot(repo) == before
    assert repo.published() == 'v0'
    assert repo.facts() == [] and repo.types() == []
    assert json.loads((repo.path / 'knowledge.json').read_text()) == {
        'schema': 'curator-knowledge/3', 'game': 'cdda'}
    assert repo.provenance() == {'frames': {}, 'sessions': {}}
    assert (repo.path / 'programs' / '.keep').exists() and (repo.path / 'tests' / '.keep').exists()
    assert repo.state == tmp_path / 'knowledge' / 'cdda.state'


def test_valid_submission_is_accepted_and_versions_are_exportable(tmp_path):
    repo = make_repo(tmp_path)
    directory = submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                      {'op': 'add_fact', 'fact': fact()}],
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
    assert [item['name'] for item in repo.types()] == ['mechanic']
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
    changes = [{'op': 'add_type', 'type': kind()},
               {'op': 'add_fact', 'fact': fact(citations=('frame-1', 'elsewhere'))}]
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, changes))
    assert not (verdict['status'] == 'published')
    assert any('elsewhere' in line for line in verdict['diagnostics'])
    assert snapshot(repo) == before


def test_unknown_type_rejected_and_accepted_when_added_in_the_submission(tmp_path):
    repo = make_repo(tmp_path)
    bad = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}]))
    assert not (bad['status'] == 'published') and any('unknown type' in line for line in bad['diagnostics'])
    good = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()},
                                           {'op': 'add_type', 'type': kind()}], name='s2'))
    assert (good['status'] == 'published') and repo.published() == 'v1'


def test_supersede_marks_the_old_fact(tmp_path):
    repo = seeded(tmp_path)
    directory = submission(tmp_path, [{'op': 'supersede_fact', 'ids': ['f1'], 'fact': fact('f2')}],
                           base_version='v1')
    assert run(repo, directory)['version'] == 'v2'
    by_id = {item['id']: item for item in repo.facts()}
    assert by_id['f1']['superseded_by'] == 'f2' and 'superseded_by' not in by_id['f2']
    assert 'superseded_by' not in {key for item in repo.facts('v1') for key in item}


def test_supersede_unknown_or_already_superseded_is_rejected(tmp_path):
    repo = seeded(tmp_path)
    unknown = run(repo, submission(
        tmp_path, [{'op': 'supersede_fact', 'ids': ['nope'], 'fact': fact('f2')}],
        base_version='v1'))
    assert not (unknown['status'] == 'published') and any('does not exist' in x for x in unknown['diagnostics'])
    run(repo, submission(tmp_path, [{'op': 'supersede_fact', 'ids': ['f1'], 'fact': fact('f2')}],
                         name='s3', base_version='v1'))
    again = run(repo, submission(
        tmp_path, [{'op': 'supersede_fact', 'ids': ['f1'], 'fact': fact('f3')}], name='s4',
        base_version='v2'))
    assert not (again['status'] == 'published') and any('already superseded' in x for x in again['diagnostics'])
    twice = run(repo, submission(
        tmp_path, [{'op': 'supersede_fact', 'ids': ['f2'], 'fact': fact('f4')},
                   {'op': 'supersede_fact', 'ids': ['f2'], 'fact': fact('f5')}], name='s5',
        base_version='v2'))
    assert not (twice['status'] == 'published')


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


def test_wrong_scope_game_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                              {'op': 'add_fact', 'fact': fact(game='other')}]))
    assert not (verdict['status'] == 'published') and any('scope game' in x for x in verdict['diagnostics'])


def malformed_cases():
    good = {'op': 'add_fact', 'fact': fact()}
    return {
        'extra fact field': [{'op': 'add_fact', 'fact': fact(note='x')}],
        'extra change field': [{**good, 'more': 1}],
        'unknown op': [{'op': 'delete_fact', 'id': 'f1'}],
        'wrong fact schema': [{'op': 'add_fact', 'fact': {**fact(), 'schema': 'curator-fact/2'}}],
        'empty citations': [{'op': 'add_fact', 'fact': fact(citations=())}],
        'scope not object': [{'op': 'add_fact', 'fact': {**fact(), 'scope': 'cdda'}}],
        'extra type field': [{'op': 'add_type', 'type': {**kind(), 'x': 1}}],
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
    change = [{'op': 'add_type', 'type': kind()}]
    cases = {
        'schema': submission(tmp_path, change, name='a', schema='curator-submission/2'),
        'extra': submission(tmp_path, change, name='b', surprise=1),
        'base': submission(tmp_path, change, name='c', base_version='3'),
    }
    huge = submission(tmp_path, change, name='d')
    (huge / 'submission.json').write_text(json.dumps(
        {'schema': 'curator-submission/1', 'base_version': 'v0', 'summary': 'x' * 300_000,
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
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                              {'op': 'add_fact', 'fact': fact()}]))
    monkeypatch.setattr(knowledge, '_git', real)
    assert not (verdict['status'] == 'published') and verdict['version'] is None
    assert any('forced tag failure' in x for x in verdict['diagnostics'])
    assert repo.published() == 'v0'
    assert snapshot(repo) == before
    assert repo.facts() == []
    retry = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                            {'op': 'add_fact', 'fact': fact()}], name='s2'))
    assert (retry['status'] == 'published') and repo.published() == 'v1'


def test_gate_log_gains_one_line_per_call(tmp_path):
    repo = make_repo(tmp_path)
    run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}]))
    run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}], name='s2'))
    run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}], name='s3'))
    lines = (repo.state / 'gate.jsonl').read_text().splitlines()
    assert [json.loads(line)['status'] for line in lines] == ['rejected', 'published', 'rejected']
    assert [json.loads(line)['submission'] for line in lines] == ['s1', 's2', 's3']


def test_the_gate_reads_neither_links_nor_special_files(tmp_path):
    repo = make_repo(tmp_path)
    secret = tmp_path / 'secret.json'
    secret.write_text(json.dumps({'schema': 'curator-submission/1', 'base_version': 'v0', 'summary': 's',
                                  'changes': [{'op': 'add_type', 'type': kind()}]}))
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
    surrogate = submission(tmp_path, [{'op': 'add_type', 'type': {**kind(), 'description': 'x'}}], name='sur')
    (surrogate / 'submission.json').write_text(
        (surrogate / 'submission.json').read_text().replace('"x"', '"\\ud800"'))
    bad_drafts = submission(tmp_path, [{'op': 'add_type', 'type': kind()}], name='drafts',
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
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}]))
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
    good = submission(workspace, [{'op': 'add_type', 'type': kind()}])
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
    submission(workspace, [{'op': 'add_type', 'type': kind()}])
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
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}],
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


def without(item: dict, key: str) -> dict:
    return {k: v for k, v in item.items() if k != key}


FACT_RULES = {
    'blank subject': (fact(subject='  '), 'subject must be a non-empty string'),
    'subject not text': (fact(subject=['a thing']), 'subject must be a non-empty string'),
    'old schema': (fact(schema='curator-fact/3'), "schema must be 'curator-fact/4'"),
    'missing known': (without(fact(), 'known'), "missing field 'known'"),
    'invalid known': (fact(known='certain'), 'known must be'),
    'missing record': (without(fact(), 'record'), "missing field 'record'"),
    'wrong record': (fact(record='article'), 'record must be fact'),
    'missing text': (without(fact(), 'text'), "missing field 'text'"),
    'blank text': (fact(text=' '), 'text must be a non-empty string'),
    'duplicate citations': (fact(citations=['frame-1', 'frame-1']), 'citations must be'),
    'blank scope': (fact(scope={'game': ' '}), 'scope must be'),
    'invalid scope level': (fact(level='local'), 'scope must be'),
    'submitted world': (fact(scope={'game': 'cdda', 'level': 'world', 'world': 'pond'}), 'scope must be'),
    'model seen': (fact(seen=50), "unexpected field 'seen'"),
    **{f'removed {key}': (fact(**{key: 'x'}), f"unexpected field '{key}'")
       for key in ('kind', 'place', 'game_time', 'statement')},
    'a coverage key in a fact': (fact(coverage=COVERAGE), "unexpected field 'coverage'"),
}


@pytest.mark.parametrize('name', list(FACT_RULES))
def test_each_fact_rule_rejects_with_its_own_diagnostic_at_the_well_formed_stage(tmp_path, name):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    bad, expected = FACT_RULES[name]
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}, {'op': 'add_fact', 'fact': bad}]))
    assert not (verdict['status'] == 'published')
    assert len(verdict['diagnostics']) == 1 and expected in verdict['diagnostics'][0], verdict['diagnostics']
    assert snapshot(repo) == before


def test_subject_is_optional_and_seen_is_the_latest_cited_position(tmp_path):
    repo = make_repo(tmp_path)
    item = without(fact(citations=['frame-2', 'frame-1']), 'subject')
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}, {'op': 'add_fact', 'fact': item}]))
    assert (verdict['status'] == 'published'), verdict['diagnostics']
    assert repo.facts()[0]['seen'] == dict(session='s1', actor='001', step=2, order=[1, '001', 2])


@pytest.mark.parametrize('first_step, replay_step', [(41, 42), (42, 41)])
def test_shared_frame_keeps_its_first_published_position_across_windows(tmp_path, first_step, replay_step):
    repo = make_repo(tmp_path)
    windows = [('frame-1', first_step), ('frame-1', replay_step), ('next-frame', 43)]
    expected_positions = {}
    for index, (frame, step) in enumerate(windows, 1):
        position = dict(session='s1', actor='001', step=step, order=[1, '001', step])
        expected_positions.setdefault(frame, position)
        changes = [dict(op='add_fact', fact=fact(f'f{index}', citations=[frame]))]
        if index == 1:
            changes.insert(0, dict(op='add_type', type=kind()))
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
    directory = submission(tmp_path, [dict(op='add_fact', fact=fact('f2', citations=['new-frame']))], base_version='v1')
    verdict = gate(repo, directory, session_id='sess', window_frames={'new-frame': position},
                   coverage={**COVERAGE, 'last_step': 42}, session_kind='admission')
    assert (verdict['status'], verdict['version']) == ('rejected', None)
    assert verdict['diagnostics'] == ['publication failed: invalid candidate snapshot: invalid frame position']
    assert snapshot(repo) == before


def test_the_gate_rejects_a_candidate_that_changes_a_record_origin(tmp_path, monkeypatch):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    publication = gate_module._publication

    def wrong_origin(repo, records, *args):
        records[0] = dict(records[0], session='different-session')
        return publication(repo, records, *args)

    monkeypatch.setattr(gate_module, '_publication', wrong_origin)
    monkeypatch.setattr(repo, 'commit', lambda *args: pytest.fail('invalid candidate reached commit'))
    verdict = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('f2'))], base_version='v1'))
    assert (verdict['status'], verdict['version']) == ('rejected', None)
    assert verdict['diagnostics'] == ['publication failed: invalid candidate snapshot: invalid record origin']
    assert snapshot(repo) == before


def old_contract_repository(tmp_path):
    repo = make_repo(tmp_path)
    old = {'schema': 'curator-fact/2', 'id': 'old', 'type': 'mechanic', 'statement': 's', 'scope': {'game': 'cdda'},
           'citations': ['frame-1'], 'published_in': 'v1', 'session': 'x'}
    repo.commit({'facts.jsonl': (json.dumps(old) + '\n').encode(),
                 'ontology/types.json': (json.dumps([kind()]) + '\n').encode()}, 'Publish v1')
    return repo


@pytest.mark.parametrize('change', [
    lambda: {'op': 'supersede_fact', 'ids': ['old'], 'fact': fact('new')},
    lambda: {'op': 'add_fact', 'fact': fact('new')}])
def test_the_gate_does_not_publish_into_a_repository_holding_facts_of_another_contract(tmp_path, change):
    repo = old_contract_repository(tmp_path)
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, [change()], base_version='v1'))
    assert not (verdict['status'] == 'published') and len(verdict['diagnostics']) == 1
    assert verdict['diagnostics'] == ['publication failed: incompatible history at v1']
    assert snapshot(repo) == before and repo.published() == 'v1'


def test_the_coverage_stamp_is_published_with_the_version_and_changes_with_it(tmp_path):
    repo = make_repo(tmp_path)
    assert not (repo.path / 'coverage.json').exists()
    first = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}]))
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
    changes = [{'op': 'add_type', 'type': kind()}, {'op': 'add_fact', 'fact': fact()}]
    top = {}
    if where == 'top':
        top['coverage'] = {**COVERAGE, 'last_step': 999}
    elif where == 'change':
        changes[1]['coverage'] = COVERAGE
    else:
        changes[1]['fact']['coverage'] = COVERAGE
    verdict = run(repo, submission(tmp_path, changes, **top))
    assert not (verdict['status'] == 'published') and any('unexpected field' in d and 'coverage' in d for d in verdict['diagnostics'])
    assert snapshot(repo) == before


@pytest.mark.parametrize('stamp', [None, {}, {**COVERAGE, 'extra': 1}, {**COVERAGE, 'schema': 'curator-coverage/0'},
                                   {**COVERAGE, 'last_step': '20'}, {**COVERAGE, 'session': ''}])
def test_a_bad_stamp_from_the_runner_publishes_nothing(tmp_path, stamp):
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}]), coverage=stamp)
    assert not (verdict['status'] == 'published') and any('coverage' in d for d in verdict['diagnostics'])
    assert snapshot(repo) == before


def article(identity='a1', title='A subject', facts=('f1',), **extra):
    return dict(schema='curator-fact/4', record='article', id=identity, title=title,
                lead='A hypothesis. Check before relying on it.',
                body=[dict(text='An arbitrary claim, never judged by the gate.', facts=list(facts))], links=[]) | extra


def grooming(repo, tmp_path, changes, *, frames=FRAMES, session_labels=None, **kw):
    return run(repo, submission(tmp_path, changes, base_version=repo.published(), **kw),
               session_kind='grooming', frames=frames, session_labels=session_labels)


def test_supersede_merges_several_facts_and_retirement_preserves_evidence(tmp_path):
    repo = seeded(tmp_path)
    added = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact('f2')}], base_version='v1'))
    assert (added['status'] == 'published')
    merged = run(repo, submission(tmp_path, [{'op': 'supersede_fact', 'ids': ['f1', 'f2'], 'fact': fact('merged')}],
                                  name='merge', base_version='v2'))
    assert (merged['status'] == 'published'), merged
    assert [f['superseded_by'] for f in repo.facts()[:2]] == ['merged', 'merged']
    retired = run(repo, submission(tmp_path, [dict(op='retire_fact', id='merged', reason='contradicted',
                                                 citations=['frame-2'])], name='retire', base_version='v3'))
    assert (retired['status'] == 'published'), retired
    assert repo.facts()[-1]['retired']['reason'] == 'contradicted'
    assert repo.facts()[-1]['retired']['citations'] == ['frame-2']
    assert 'retired' not in repo.facts('v3')[-1]


@pytest.mark.parametrize('changes, expected', [
    ([dict(op='supersede_fact', ids=[], fact=fact('f2'))], 'ids must be'),
    ([dict(op='supersede_fact', ids=['f1', 'f1'], fact=fact('f2'))], 'ids must be'),
    ([dict(op='retire_fact', id='f1', reason='', citations=['frame-1'])], 'reason must be'),
    ([dict(op='retire_fact', id='f1', reason='x', citations=[])], 'citations must be'),
    ([dict(op='retire_fact', id='f1', reason='x', citations=['frame-1', 'frame-1'])], 'citations must be'),
    ([dict(op='retire_article', id='a1', reason=' ')], 'reason must be'),
    ([dict(op='retire_fact', id='f1', reason='x', citations=['outside'])], 'outside the trace window'),
    ([dict(op='retire_fact', id='unknown', reason='x', citations=['frame-1'])], 'does not exist'),
    ([dict(op='retire_fact', id='f1', reason='x', citations=['frame-1'])] * 2, 'already superseded or retired'),
])
def test_merge_and_retirement_rules_are_independently_rejected(tmp_path, changes, expected):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, changes, base_version='v1'))
    assert not (verdict['status'] == 'published') and any(expected in d for d in verdict['diagnostics']), verdict
    assert snapshot(repo) == before


ARTICLE_RULES = {
    'non-object': ([], 'must be an object'),
    'blank id': (dict(article(), id=' '), 'id must be'),
    'blank link': (dict(article(), links=[' ']), 'links must be'),
    'duplicate claim facts': (dict(article(), body=[dict(text='x', facts=['f1', 'f1'])]), 'body must be'),
    'old schema': (dict(article(), schema='curator-fact/2'), 'schema must be'),
    'wrong record': (dict(article(), record='fact'), 'record must be article'),
    'missing record': (without(article(), 'record'), "missing field 'record'"),
    'blank title': (dict(article(), title=' '), 'title must be'),
    'blank lead': (dict(article(), lead=''), 'lead must be'),
    'no body': (dict(article(), body=[]), 'body must be'),
    'uncited claim': (dict(article(), body=[dict(text='x', facts=[])]), 'body must be'),
    'blank claim': (dict(article(), body=[dict(text=' ', facts=['f1'])]), 'body must be'),
    'extra claim key': (dict(article(), body=[dict(text='x', facts=['f1'], extra='x')]), 'body must be'),
    'invalid links': (dict(article(), links='x'), 'links must be'),
    'duplicate links': (dict(article(), links=['A', 'A']), 'links must be'),
    'model timestamp': (dict(article(), last_confirmed=99), "unexpected field 'last_confirmed'"),
}


@pytest.mark.parametrize('name', list(ARTICLE_RULES))
def test_each_article_shape_rule_rejects_on_its_own(tmp_path, name):
    repo = seeded(tmp_path)
    value, expected = ARTICLE_RULES[name]
    verdict = grooming(repo, tmp_path, [dict(op='add_article', article=value)])
    assert not (verdict['status'] == 'published')
    assert len(verdict['diagnostics']) == 1 and expected in verdict['diagnostics'][0], verdict


def test_article_citations_links_and_last_confirmed_resolve_the_final_snapshot(tmp_path):
    repo = seeded(tmp_path)
    verdict = grooming(repo, tmp_path, [dict(op='add_fact', fact=fact('f2', citations=['frame-2'])),
                                       dict(op='add_article', article=article(links=['Other'])),
                                       dict(op='add_article', article=article('a2', 'Other', ['f1', 'f2']))])
    assert (verdict['status'] == 'published'), verdict
    assert repo.articles()[1]['last_confirmed']['step'] == 2
    assert all(r['schema'] == 'curator-fact/4' for r in repo.records())
    # Replace both articles together; neither stale citations nor incoming links survive.
    verdict = grooming(repo, tmp_path, [dict(op='supersede_fact', ids=['f1', 'f2'], fact=fact('merged')),
                                       dict(op='revise_article', id='a1', article=article('a3', 'Combined', ['merged'])),
                                       dict(op='retire_article', id='a2', reason='merged')], name='revise')
    assert (verdict['status'] == 'published'), verdict
    assert repo.articles()[0]['superseded_by'] == 'a3'
    assert repo.articles()[1]['retired']['reason'] == 'merged'


@pytest.mark.parametrize('changes, expected', [
    ([dict(op='add_article', article=article(facts=['unknown']))], 'is not current'),
    ([dict(op='add_article', article=article(links=['Missing']))], 'does not resolve'),
    ([dict(op='add_article', article=article()), dict(op='add_article', article=article('a2'))], 'titles must be unique'),
    ([dict(op='add_article', article=article('f1'))], 'is not new'),
    ([dict(op='add_type', type=kind('other'))], 'unfiled current facts'),
])
def test_each_article_reference_and_filing_rule_rejects(tmp_path, changes, expected):
    repo = seeded(tmp_path)
    before = snapshot(repo)
    verdict = grooming(repo, tmp_path, changes)
    assert not (verdict['status'] == 'published') and any(expected in d for d in verdict['diagnostics']), verdict
    assert snapshot(repo) == before


def test_retired_and_superseded_facts_cannot_support_current_articles(tmp_path):
    repo = seeded(tmp_path)
    assert grooming(repo, tmp_path, [dict(op='add_article', article=article())])['status'] == 'published'
    for name, change in [('retire', dict(op='retire_fact', id='f1', reason='x', citations=['frame-1'])),
                         ('replace', dict(op='supersede_fact', ids=['f1'], fact=fact('f2')))]:
        verdict = run(repo, submission(tmp_path, [change], name=name, base_version='v2'))
        assert not (verdict['status'] == 'published') and any("fact 'f1' is not current" in d for d in verdict['diagnostics']), verdict
    # The fact itself stays current because both rejected publications were atomic.
    assert 'retired' not in repo.facts()[0]


def test_removing_a_link_target_requires_repairing_incoming_links(tmp_path):
    repo = seeded(tmp_path)
    assert grooming(repo, tmp_path, [dict(op='add_article', article=article(links=['Other'])),
                                     dict(op='add_article', article=article('a2', 'Other'))])['status'] == 'published'
    verdict = run(repo, submission(tmp_path, [dict(op='retire_article', id='a2', reason='x')],
                                   name='retire', base_version='v2'))
    assert not (verdict['status'] == 'published') and any('does not resolve' in d for d in verdict['diagnostics'])


def test_every_type_revision_publishes_a_new_version_and_keeps_current_types(tmp_path):
    repo = seeded(tmp_path)
    revisions = [
        dict(action='rename', names=['mechanic'], types=[kind('relation')], assignments={'f1': 'relation'}),
        dict(action='split', names=['relation'], types=[kind('observed'), kind('inferred')], assignments={'f1': 'observed'}),
        dict(action='merge', names=['observed', 'inferred'], types=[kind('relation')], assignments={'f1': 'relation'}),
        dict(action='deprecate', names=['relation'], types=[], assignments={}),
    ]
    for index, revision in enumerate(revisions):
        changes = [dict(op='revise_types', **revision)]
        if index == 0:
            changes.append(dict(op='add_article', article=article()))
        if index == 3:
            changes += [dict(op='retire_fact', id='f1', reason='contradicted', citations=['frame-1']),
                        dict(op='retire_article', id='a1', reason='no current evidence')]
        verdict = grooming(repo, tmp_path, changes, name=f'revision-{revision["action"]}')
        assert (verdict['status'] == 'published') and verdict['version'] == f'v{index + 2}', verdict
    assert repo.types() == [] and repo.types('v1') == [dict(kind(), published_in='v1')]
    assert repo.facts('v3')[0]['type'] == 'observed'


@pytest.mark.parametrize('revision, expected', [
    (dict(action='rename', names=['mechanic'], types=[kind('renamed')], assignments={}), 'unknown type'),
    (dict(action='rename', names=['unknown'], types=[kind('renamed')], assignments={}), 'unknown type'),
    (dict(action='rename', names=['mechanic'], types=[kind('renamed')], assignments={'missing': 'renamed'}), 'is not current'),
    (dict(action='merge', names=['mechanic', 'mechanic'], types=[kind('renamed')], assignments={}), 'names must be'),
    (dict(action='rename', names=['mechanic'], types=[None], assignments={}), 'must be an object'),
    (dict(action='rename', names=['mechanic'], types=[kind('renamed')], assignments={'': 'renamed'}), 'assignments must map'),
    (dict(action='rename', names=['mechanic'], types=[kind('renamed')], assignments={'f1': ' '}), 'assignments must map'),
    (dict(action='rename', names=[], types=[kind('renamed')], assignments={}), 'names must be'),
    (dict(action='rename', names=['mechanic'], types='bad', assignments={}), 'types must be'),
    (dict(action='rename', names=['mechanic'], types=[kind('renamed')], assignments=[]), 'assignments must map'),
    (dict(action='unknown', names=['mechanic'], types=[], assignments={}), 'unknown type revision action'),
    (dict(action='merge', names=['mechanic'], types=[kind('renamed')], assignments={}), 'cardinality'),
    (dict(action='split', names=['mechanic'], types=[kind('renamed')], assignments={}), 'cardinality'),
    (dict(action='rename', names=['mechanic'], types=[], assignments={}), 'cardinality'),
    (dict(action='deprecate', names=['mechanic'], types=[kind('renamed')], assignments={}), 'cardinality'),
])
def test_each_type_revision_rule_rejects(tmp_path, revision, expected):
    repo = seeded(tmp_path)
    verdict = grooming(repo, tmp_path, [dict(op='revise_types', **revision), dict(op='add_article', article=article())])
    assert not (verdict['status'] == 'published') and any(expected in d for d in verdict['diagnostics']), verdict


def test_type_revisions_need_grooming_and_separate_versions(tmp_path):
    repo = seeded(tmp_path)
    revision = dict(op='revise_types', action='rename', names=['mechanic'], types=[kind('renamed')],
                    assignments={'f1': 'renamed'})
    verdict = run(repo, submission(tmp_path, [revision], base_version='v1'))
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == ['changes[0]: type revisions require a grooming session']
    verdict = grooming(repo, tmp_path, [revision, revision], name='twice')
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == ['submission: each type revision needs its own published version']



def test_bad_frame_provenance_with_an_article_rejects_before_deriving_confirmation(tmp_path):
    repo = make_repo(tmp_path)
    changes = [dict(op='add_type', type=kind()), dict(op='add_fact', fact=fact(citations=['outside'])),
               dict(op='add_article', article=article())]
    verdict = run(repo, submission(tmp_path, changes))
    assert not (verdict['status'] == 'published')
    assert verdict['diagnostics'] == ["changes[1]: citation 'outside' is outside the trace window"]
    assert repo.published() == 'v0'


@pytest.mark.parametrize('field', ['schema', 'id', 'title', 'lead', 'body', 'links'])
def test_required_article_fields_are_individually_checked(tmp_path, field):
    repo = seeded(tmp_path)
    verdict = grooming(repo, tmp_path, [dict(op='add_article', article=without(article(), field))])
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == [f"changes[0].article: missing field '{field}'"]


@pytest.mark.parametrize('op', ['revise_article', 'retire_article'])
def test_article_operations_require_a_current_article_target(tmp_path, op):
    repo = seeded(tmp_path)
    change = dict(op=op, id='f1')
    change.update(article=article()) if op == 'revise_article' else change.update(reason='x')
    verdict = run(repo, submission(tmp_path, [change], base_version='v1'))
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == ["changes[0]: article 'f1' does not exist"]


def test_ontology_revision_cannot_reuse_another_current_type_name(tmp_path):
    repo = seeded(tmp_path)
    changes = [dict(op='add_type', type=kind('existing')),
               dict(op='revise_types', action='rename', names=['mechanic'], types=[kind('existing')],
                    assignments={'f1': 'existing'}), dict(op='add_article', article=article())]
    verdict = grooming(repo, tmp_path, changes)
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == ["changes[1]: type 'existing' already exists"]


@pytest.mark.parametrize('citations', [['frame-1', 'frame-2'], ['frame-1', 'frame-2', 'current']])
def test_grooming_merge_inherits_older_evidence_and_uses_its_recorded_seen(tmp_path, citations):
    repo = make_repo(tmp_path)
    changes = [dict(op='add_type', type=kind()),
               dict(op='add_fact', fact=fact('f1')),
               dict(op='add_fact', fact=fact('f2', citations=['frame-2']))]
    assert run(repo, submission(tmp_path, changes, name='older'))['status'] == 'published'
    positions = {'current': dict(session='s2', actor='001', step=1, order=[2, '001', 1])}
    stamp = {**COVERAGE, 'session': 's2'}
    assert gate(repo, submission(tmp_path, [dict(op='add_type', type=kind('new'))], name='latest', base_version='v1'),
                session_id='latest', window_frames=positions, coverage=stamp, session_kind='admission')['status'] == 'published'
    changes = [dict(op='supersede_fact', ids=['f1', 'f2'], fact=fact('merged', citations=citations)),
               dict(op='add_article', article=article(facts=['merged']))]
    verdict = gate(repo, submission(tmp_path, changes, name='merge', base_version='v2'), session_id='groom',
                   window_frames=positions, coverage=stamp, session_kind='grooming')
    assert (verdict['status'] == 'published'), verdict
    expected = positions['current'] if 'current' in citations else repo.provenance()['frames']['frame-2']
    assert repo.facts()[-1]['seen'] == expected
    assert repo.articles()[0]['last_confirmed'] == expected


@pytest.mark.parametrize('session_kind, citation', [('admission', 'frame-1'), ('grooming', 'unrelated'), ('grooming', 'unknown')])
def test_replacement_cannot_inherit_unrelated_citations_or_inherit_during_admission(tmp_path, session_kind, citation):
    repo = make_repo(tmp_path)
    assert run(repo, submission(tmp_path, [dict(op='add_type', type=kind()), dict(op='add_fact', fact=fact()),
                                          dict(op='add_fact', fact=fact('other', citations=['unrelated']))], name='seed'),
               frames={'frame-1', 'unrelated'})['status'] == 'published'
    changes = [dict(op='supersede_fact', ids=['f1'], fact=fact('replacement', citations=[citation])),
               dict(op='add_article', article=article(facts=['replacement', 'other']))]
    verdict = run(repo, submission(tmp_path, changes, base_version='v1'), frames={'current'}, session_kind=session_kind)
    assert not (verdict['status'] == 'published')
    assert len(verdict['diagnostics']) == 1 and f"citation {citation!r} is outside" in verdict['diagnostics'][0]


@pytest.mark.parametrize('removal', ['unrelated-type', 'retire_fact', 'supersede_fact'])
def test_retype_assignments_require_a_source_type_and_a_surviving_fact(tmp_path, removal):
    repo = seeded(tmp_path)
    if removal == 'unrelated-type':
        assert run(repo, submission(tmp_path, [dict(op='add_type', type=kind('other')),
                                              dict(op='add_fact', fact=fact('f2', type_name='other'))],
                                   name='extra', base_version='v1'))['status'] == 'published'
        assignments, facts = {'f1': 'renamed', 'f2': 'renamed'}, ['f1', 'f2']
        changes, expected = [], 'type outside names before the revision'
    else:
        assignments = {'f1': 'renamed'}
        if removal == 'retire_fact':
            changes, facts = [dict(op=removal, id='f1', reason='contradicted', citations=['frame-1'])], []
        else:
            changes, facts = [dict(op=removal, ids=['f1'], fact=fact('f2', type_name='renamed'))], ['f2']
        expected = 'retired or superseded in this submission'
    changes.insert(0, dict(op='revise_types', action='rename', names=['mechanic'], types=[kind('renamed')],
                           assignments=assignments))
    if facts:
        changes.append(dict(op='add_article', article=article(facts=facts)))
    verdict = grooming(repo, tmp_path, changes)
    assert not (verdict['status'] == 'published') and len(verdict['diagnostics']) == 1
    assert expected in verdict['diagnostics'][0], verdict


def test_retyping_records_software_history_and_preserves_prior_versions(tmp_path):
    repo = seeded(tmp_path)
    for old, new, version in [('mechanic', 'relation', 'v2'), ('relation', 'observed', 'v3')]:
        changes = [dict(op='revise_types', action='rename', names=[old], types=[kind(new)], assignments={'f1': new})]
        if version == 'v2':
            changes.append(dict(op='add_article', article=article()))
        assert grooming(repo, tmp_path, changes, name=new)['version'] == version
    assert [
        {'from': 'mechanic', 'to': 'relation', 'version': 'v2'},
        {'from': 'relation', 'to': 'observed', 'version': 'v3'}] == repo.facts()[0]['retyped']
    assert 'retyped' not in repo.facts('v1')[0]
    assert len(repo.facts('v2')[0]['retyped']) == 1
    verdict = run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('forged', type_name='observed', retyped=[]))],
                                   name='forged', base_version='v3'))
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == ["changes[0].fact: unexpected field 'retyped'"]


def test_article_cannot_link_to_itself(tmp_path):
    repo = seeded(tmp_path)
    verdict = grooming(repo, tmp_path, [dict(op='add_article', article=article(links=['A subject']))])
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == ["article 'a1': link to itself is not allowed"]


@pytest.mark.parametrize('first, second', [('retire_article', 'retire_article'), ('retire_article', 'revise_article'),
                                          ('revise_article', 'retire_article'), ('revise_article', 'revise_article')])
@pytest.mark.parametrize('same_submission', [True, False])
def test_article_target_cannot_be_changed_twice_or_after_retirement(tmp_path, first, second, same_submission):
    repo = seeded(tmp_path)
    assert grooming(repo, tmp_path, [dict(op='add_article', article=article())], name='article')['status'] == 'published'
    def change(op, identity):
        return dict(op=op, id='a1', **(dict(reason='no longer useful') if op == 'retire_article' else
                                      dict(article=article(identity, title=identity))))
    changes = [change(first, 'a2'), change(second, 'a3')]
    if not same_submission:
        assert run(repo, submission(tmp_path, changes[:1], name='first', base_version='v2'))['status'] == 'published'
        changes = changes[1:]
    verdict = run(repo, submission(tmp_path, changes, name='again', base_version=repo.published()))
    assert not (verdict['status'] == 'published') and len(verdict['diagnostics']) == 1
    assert 'already superseded or retired' in verdict['diagnostics'][0]


@pytest.mark.parametrize('op', ['retire_fact', 'supersede_fact'])
def test_fact_operations_cannot_target_articles(tmp_path, op):
    repo = seeded(tmp_path)
    assert grooming(repo, tmp_path, [dict(op='add_article', article=article())], name='article')['status'] == 'published'
    change = dict(op=op, **(dict(id='a1', reason='x', citations=['frame-1']) if op == 'retire_fact' else
                            dict(ids=['a1'], fact=fact('f2'))))
    verdict = run(repo, submission(tmp_path, [change], base_version='v2'))
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == ["changes[0]: fact 'a1' does not exist"]


@pytest.mark.parametrize('schema', ['curator-knowledge/2', 'curator-knowledge/4', None])
def test_repository_refuses_other_layout_schemas_for_every_reader_and_writer(tmp_path, schema):
    repo = make_repo(tmp_path)
    repo.commit({'knowledge.json': json.dumps(dict(schema=schema, game='cdda')).encode()}, 'foreign layout')
    before = snapshot(repo)
    for action in [repo.ensure, repo.published, repo.records, repo.types, repo.provenance,
                   lambda: repo.export('v1', tmp_path/'export'), lambda: repo.commit({}, 'forbidden')]:
        with pytest.raises(KnowledgeError, match='expected curator-knowledge/3; start a new repository'):
            action()
    verdict = run(repo, submission(tmp_path, [dict(op='add_type', type=kind())], base_version='v1'))
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
    ('old-record', 'published store is not curator-fact/4'),
    ('old-type', 'published types are not curator-type/2'),
    ('old-layout', 'expected curator-knowledge/3; start a new repository'),
])
def test_session_preparation_refuses_invalid_grooming_inputs_before_starting_a_host(tmp_path, monkeypatch, problem, expected):
    from tests.curator_trace import make_long_session

    repo = make_repo(tmp_path) if problem == 'no-admission' else seeded(tmp_path)
    if problem == 'old-record':
        repo.commit({'facts.jsonl': (json.dumps(fact(schema='curator-fact/3'))+'\n').encode()}, 'old record')
    elif problem == 'old-type':
        repo.commit({'ontology/types.json': json.dumps([dict(kind(), schema='curator-type/1')]).encode()}, 'old type')
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


def test_inherited_citations_require_recorded_frame_positions(tmp_path):
    repo = seeded(tmp_path)
    provenance = repo.provenance()
    provenance['frames'].pop('frame-1')
    repo.commit({'provenance.json': json.dumps(provenance).encode()}, 'missing recorded position')
    verdict = run(repo, submission(tmp_path, [dict(op='supersede_fact', ids=['f1'], fact=fact('replacement')),
                                             dict(op='add_article', article=article(facts=['replacement']))],
                                   base_version='v2'), frames=set(), session_kind='grooming')
    assert verdict['status'] == 'rejected' and verdict['diagnostics'] == [
        'publication failed: incompatible history at v2']


def test_grooming_without_a_configured_brief_aborts_before_host_start(tmp_path, monkeypatch):
    from tests.curator_trace import frame_id, make_long_session

    repo = make_repo(tmp_path)
    trace = make_long_session(tmp_path/'evidence')
    citation = frame_id(1, 1)
    assert run(repo, submission(tmp_path, [dict(op='add_type', type=kind()),
                                          dict(op='add_fact', fact=fact(citations=[citation]))]),
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
    verdict = run(repo, submission(tmp_path, [dict(op='add_type', type=kind())], base_version='v1'))
    assert not (verdict['status'] == 'published') and len(verdict['diagnostics']) == 1
    assert 'unsupported knowledge schema:' in verdict['diagnostics'][0]
    assert 'start a new repository' in verdict['diagnostics'][0]
    assert snapshot(repo) == before


@pytest.mark.parametrize('op', ['add_fact', 'retire_fact', 'supersede_fact'])
def test_grooming_citation_diagnostic_mentions_replaced_facts_only_for_superseding(tmp_path, op):
    repo = seeded(tmp_path)
    if op == 'retire_fact':
        change = dict(op=op, id='f1', reason='contradicted', citations=['outside'])
    else:
        change = dict(op=op, fact=fact('f2', citations=['outside']))
        if op == 'supersede_fact':
            change['ids'] = ['f1']
    verdict = grooming(repo, tmp_path, [change])
    suffix = ' and the replaced facts' if op == 'supersede_fact' else ''
    assert not (verdict['status'] == 'published') and verdict['diagnostics'] == [
        "changes[0]: citation 'outside' is outside the trace window" + suffix]


POND_ID = 'a' * 32
FOREST_ID = 'b' * 32
POND_FRAME = f'{POND_ID}-1'
FOREST_FRAME = f'{FOREST_ID}-1'
POND = dict(name='pond-first', world='pond', lineage='pond-lineage', admission=1)
FOREST = dict(name='forest-first', world='forest', lineage='forest-lineage', admission=1)


@pytest.fixture
def world_repo(tmp_path):
    repo = make_repo(tmp_path)
    changes = [dict(op='add_type', type=kind(identity=['a'])),
               dict(op='add_fact', fact=fact(level='world', citations=[POND_FRAME]))]
    verdict = run(repo, submission(tmp_path, changes, name='before-grooming'), frames={POND_FRAME},
                  session_labels={POND_ID: POND})
    assert verdict['status'] == 'published', verdict
    return repo


def test_world_scope_uses_frame_positions_labels_and_grooming_inherits_the_join(tmp_path):
    from harness.curator.window import FramePositions

    repo = make_repo(tmp_path)
    second_id = 'c' * 32
    second_frame = f'{second_id}-2'
    second = dict(POND, name='pond-second', admission=2)
    labels = {POND_ID: POND, second_id: second}
    frames = FramePositions({identity: dict(label, label_check=None, label_error=None)
                             for identity, label in labels.items()})
    frames[POND_FRAME] = dict(session=POND['name'], actor='001', step=1, order=[1, '001', 1])
    frames[second_frame] = dict(session=second['name'], actor='001', step=2, order=[2, '001', 2])
    changes = [dict(op='add_type', type=kind()),
               dict(op='add_fact', fact=fact(level='world', citations=[POND_FRAME, second_frame], known='inferred'))]
    result = gate(repo, submission(tmp_path, changes), session_id='sess', window_frames=frames,
                  coverage=COVERAGE, session_kind='admission')
    assert result['status'] == 'published', result
    assert repo.facts()[0]['scope'] == dict(game='cdda', level='world', world='pond')
    assert repo.facts()[0]['seen'] == frames[second_frame]
    assert repo.provenance()['sessions'] == labels
    replacement = fact('f2', level='world', citations=[POND_FRAME], known='hinted')
    verdict = grooming(repo, tmp_path, [dict(op='supersede_fact', ids=['f1'], fact=replacement)], name='replace',
                       frames={second_frame}, session_labels={second_id: second})
    assert verdict['status'] == 'published', verdict
    assert repo.facts()[1]['seen'] == frames[POND_FRAME]
    assert repo.facts()[1]['known'] == 'hinted'


@pytest.mark.parametrize('forest_world,diagnostic', [(None, 'no recorded world'), ('forest', 'span two worlds')])
def test_world_facts_require_a_single_known_world(tmp_path, forest_world, diagnostic):
    repo = make_repo(tmp_path)
    labels = {POND_ID: POND, FOREST_ID: dict(FOREST, world=forest_world)}
    changes = [dict(op='add_type', type=kind()),
               dict(op='add_fact', fact=fact(level='world', citations=[POND_FRAME, FOREST_FRAME]))]
    result = run(repo, submission(tmp_path, changes), frames={POND_FRAME, FOREST_FRAME}, session_labels=labels)
    assert result['status'] == 'rejected' and diagnostic in result['diagnostics'][0]
    changes[-1]['fact']['scope']['level'] = 'game'
    result = run(repo, submission(tmp_path, changes, name='game'), frames={POND_FRAME, FOREST_FRAME},
                 session_labels=labels)
    assert result['status'] == 'published', result
    assert repo.facts()[0]['scope'] == dict(game='cdda', level='game')


@pytest.mark.parametrize('change,diagnostic', [
    (dict(op='supersede_fact', ids=['f1'], fact=fact('f2', citations=[POND_FRAME])), 'same fact scope'),
    (dict(op='supersede_fact', ids=['f1'], fact=fact('f2', level='world', citations=[FOREST_FRAME])), 'same fact scope'),
    (dict(op='retire_fact', id='f1', reason='changed', citations=[FOREST_FRAME]), 'fact\'s world'),
    (dict(op='add_article', article=article()), 'only game facts'),
])
def test_world_fact_operations_respect_scope(tmp_path, world_repo, change, diagnostic):
    result = grooming(world_repo, tmp_path, [change], frames={POND_FRAME, FOREST_FRAME},
                      session_labels={POND_ID: POND, FOREST_ID: FOREST})
    assert result['status'] == 'rejected' and any(diagnostic in d for d in result['diagnostics']), result


def test_grooming_leaves_world_facts_unfiled_and_can_retire_them_within_their_world(tmp_path, world_repo):
    frames = {POND_FRAME}
    assert grooming(world_repo, tmp_path, [dict(op='add_type', type=kind('other'))],
                    name='keep-world', frames=frames)['status'] == 'published'
    verdict = grooming(world_repo, tmp_path, [dict(op='retire_fact', id='f1', reason='changed', citations=[POND_FRAME])],
                       name='retire-world', frames=frames, session_labels={POND_ID: POND})
    assert verdict['status'] == 'published', verdict


@pytest.mark.parametrize('identity,row,diagnostic', [
    (POND_ID, dict(POND, name='pond-renamed'), 'different recorded labels or name'),
    (POND_ID, dict(POND, world=None), 'different recorded labels or name'),
    (POND_ID, dict(POND, lineage='other'), 'different recorded labels or name'),
    (POND_ID, dict(POND, admission=2), 'different recorded labels or name'),
    (FOREST_ID, dict(POND, name='another-name'), 'admission 1 has two sealed identifiers'),
    (FOREST_ID, dict(POND, name='another-name', admission=2, world='forest'), 'two different worlds'),
    (FOREST_ID, dict(FOREST, name=POND['name']), 'directory'),
])
def test_restore_does_not_free_reserved_session_identity_and_labels(tmp_path, world_repo, identity, row, diagnostic):
    assert restore(world_repo, expected_base='v1', target='v0')['version'] == 'v2'
    result = run(world_repo, submission(tmp_path, [dict(op='add_type', type=kind())], base_version='v2'),
                 frames=set(), session_labels={identity: row})
    assert result['status'] == 'rejected' and diagnostic in result['diagnostics'][0]
    assert world_repo.published() == 'v2'


def test_a_session_recorded_without_world_cannot_acquire_one(tmp_path):
    repo = make_repo(tmp_path)
    changes = [dict(op='add_type', type=kind())]
    unknown = dict(POND, world=None, lineage=None, admission=None)
    assert run(repo, submission(tmp_path, changes), frames=set(),
               session_labels={POND_ID: unknown})['status'] == 'published'
    result = run(repo, submission(tmp_path, [dict(op='add_type', type=kind('other'))], name='relabel', base_version='v1'),
                 frames=set(), session_labels={POND_ID: dict(unknown, world='pond')})
    assert result['status'] == 'rejected' and 'different recorded labels' in result['diagnostics'][0]


@pytest.mark.parametrize('damage', ['article', 'scope', 'supersession', 'retirement', 'session-history', 'type-tag'])
def test_restore_validates_world_and_type_rules_in_tagged_snapshots(tmp_path, world_repo, damage):
    repo = world_repo
    changes = [dict(op='add_fact', fact=fact('f2', citations=[FOREST_FRAME])),
               dict(op='add_article', article=article(facts=['f2']))]
    assert run(repo, submission(tmp_path, changes, base_version='v1'), frames={FOREST_FRAME},
               session_labels={FOREST_ID: FOREST})['status'] == 'published'
    records = repo.records()
    if damage == 'article':
        records[-1]['body'][0]['facts'] = ['f1']
        records[-1]['last_confirmed'] = records[0]['seen']
    elif damage == 'scope':
        records[0]['scope']['world'] = 'forest'
    elif damage == 'supersession':
        records[0]['superseded_by'] = 'f2'
    elif damage == 'retirement':
        records[0]['retired'] = dict(reason='changed', published_in='v3', session='sess', citations=[FOREST_FRAME])
    files = {'facts.jsonl': ''.join(json.dumps(item) + '\n' for item in records).encode()}
    if damage == 'session-history':
        provenance = repo.provenance()
        provenance['sessions'][FOREST_ID] = dict(FOREST, world=None)
        files['provenance.json'] = json.dumps(provenance).encode()
    if damage == 'type-tag':
        types = repo.types()
        types[0]['published_in'] = 'v4'
        files['ontology/types.json'] = json.dumps(types).encode()
    repo.commit(files, 'Invalid stored fixture')
    result = restore(repo, expected_base='v3', target='v1')
    assert result['status'] == 'rejected' and result['diagnostics'] == ['incompatible or unavailable history']


@pytest.mark.parametrize('overrides', [
    {'schema': 'curator-type/1'}, {'identity': ['other']}, {'identity': ['a', 'a']},
    {'identity': [1]}, {'reason': ' '}, {'published_in': 'v1'},
])
def test_submitted_type_fields_are_validated_separately_from_the_software_stamp(tmp_path, overrides):
    repo = make_repo(tmp_path)
    result = run(repo, submission(tmp_path, [dict(op='add_type', type=dict(kind(), **overrides))]))
    assert result['status'] == 'rejected', result


@pytest.mark.parametrize('rewrite', ['revise', 'deprecate-and-add'])
def test_redefining_a_type_requires_assignments_for_survivors_only(tmp_path, rewrite):
    repo = seeded(tmp_path)
    assert run(repo, submission(tmp_path, [dict(op='add_fact', fact=fact('f2')),
                                         dict(op='add_fact', fact=fact('f3'))], base_version='v1'))['status'] == 'published'
    definition = kind(reason='Clarify the relation.', identity=['a'])
    revision = (dict(action='rename', types=[definition]) if rewrite == 'revise'
                else dict(action='deprecate', types=[]))
    change = dict(op='revise_types', **revision, names=['mechanic'], assignments={})
    changes = [change]
    if rewrite == 'deprecate-and-add':
        changes.append(dict(op='add_type', type=definition))
    changes += [dict(op='retire_fact', id='f2', reason='changed', citations=['frame-1']),
                dict(op='supersede_fact', ids=['f3'], fact=fact('f4')),
                dict(op='add_article', article=article(facts=['f1', 'f4']))]
    refused = grooming(repo, tmp_path, changes, name='missing-assignment')
    assert refused['status'] == 'rejected' and 'assignment required' in refused['diagnostics'][0]
    change['assignments'] = {'f1': 'mechanic'}
    verdict = grooming(repo, tmp_path, changes, name='apply-assignment')
    assert verdict['status'] == 'published', verdict
    survivor, retired, superseded, added = repo.facts()
    assert survivor['retyped'] == [dict(version='v3', **{'from': 'mechanic', 'to': 'mechanic'})]
    assert all('retyped' not in item for item in (retired, superseded, added))
    assert repo.types() == [dict(definition, published_in='v3')]
    assert restore(repo, expected_base='v3', target='v2')['version'] == 'v4'
    assert repo.types() == [dict(kind(), published_in='v1')]


@pytest.mark.parametrize('end', ['retire', 'supersede'])
def test_a_fact_added_and_removed_in_one_batch_still_needs_a_final_type(tmp_path, end):
    repo = make_repo(tmp_path)
    added = dict(op='add_fact', fact=fact(type_name='absent'))
    removed = (dict(op='retire_fact', id='f1', reason='changed', citations=['frame-1']) if end == 'retire'
               else dict(op='supersede_fact', ids=['f1'], fact=fact('f2')))
    changes = [dict(op='add_type', type=kind()), added, removed]
    result = run(repo, submission(tmp_path, changes))
    assert result['status'] == 'rejected' and result['diagnostics'] == ["fact 'f1': unknown type 'absent'"]
