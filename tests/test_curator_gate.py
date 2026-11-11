"""Knowledge repository and gate v0 (#453): publication, rejection and atomicity.

Portable: real Git in tmp_path repositories, no game, no provider.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from harness.curator import containers, knowledge, sandbox, session
from harness.curator.containers import Drafts, UnsafeTree, copy_tree
from harness.curator.gate import gate
from harness.curator.knowledge import KnowledgeError, Repository

FRAMES = {'frame-1', 'frame-2'}


def make_repo(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / 'knowledge', 'cdda')
    repo.ensure()
    return repo


def fact(fact_id='f1', kind='mechanic', game='cdda', citations=('frame-1',), **extra):
    return {'schema': 'curator-fact/1', 'id': fact_id, 'type': kind,
            'statement': f'statement {fact_id}', 'scope': {'game': game},
            'citations': list(citations), **extra}


def kind(name='mechanic'):
    return {'schema': 'curator-type/1', 'name': name, 'description': 'd', 'fields': ['a']}


def submission(tmp_path: Path, changes, name='s1', **top) -> Path:
    body = {'schema': 'curator-submission/1', 'base_version': 'v0', 'summary': 'sum',
            'changes': changes, **top}
    directory = tmp_path / 'submissions' / name
    directory.mkdir(parents=True)
    (directory / 'submission.json').write_text(json.dumps(body))
    return directory


def run(repo, directory, frames=FRAMES):
    return gate(repo, directory, session_id='sess', window_frames=set(frames))


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


def test_ensure_is_idempotent_and_starts_at_v0(tmp_path):
    repo = Repository(tmp_path / 'knowledge', 'cdda')
    assert repo.ensure() == 'v0'
    before = snapshot(repo)
    assert repo.ensure() == 'v0'
    assert snapshot(repo) == before
    assert repo.published() == 'v0'
    assert repo.facts() == [] and repo.types() == []
    assert json.loads((repo.path / 'knowledge.json').read_text()) == {
        'schema': 'curator-knowledge/1', 'game': 'cdda'}
    assert (repo.path / 'programs' / '.keep').exists() and (repo.path / 'tests' / '.keep').exists()
    assert repo.state == tmp_path / 'knowledge' / 'cdda.state'


def test_valid_submission_is_accepted_and_versions_are_exportable(tmp_path):
    repo = make_repo(tmp_path)
    directory = submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                      {'op': 'add_fact', 'fact': fact()}],
                           from_drafts=['d1'])
    verdict = run(repo, directory)
    assert verdict == {'schema': 'curator-gate/1', 'submission': 's1', 'session': 'sess',
                       'accepted': True, 'base_version': 'v0', 'version': 'v1',
                       'from_drafts': ['d1'], 'diagnostics': []}
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
    assert not verdict['accepted'] and verdict['version'] is None
    assert any('v1' in line and 'stale' in line for line in verdict['diagnostics'])
    assert snapshot(repo) == before


def test_out_of_window_citation_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    changes = [{'op': 'add_type', 'type': kind()},
               {'op': 'add_fact', 'fact': fact(citations=('frame-1', 'elsewhere'))}]
    before = snapshot(repo)
    verdict = run(repo, submission(tmp_path, changes))
    assert not verdict['accepted']
    assert any('elsewhere' in line for line in verdict['diagnostics'])
    assert snapshot(repo) == before


def test_unknown_type_rejected_and_accepted_when_added_in_the_submission(tmp_path):
    repo = make_repo(tmp_path)
    bad = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}]))
    assert not bad['accepted'] and any('unknown type' in line for line in bad['diagnostics'])
    good = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()},
                                           {'op': 'add_type', 'type': kind()}], name='s2'))
    assert good['accepted'] and repo.published() == 'v1'


def test_supersede_marks_the_old_fact(tmp_path):
    repo = seeded(tmp_path)
    directory = submission(tmp_path, [{'op': 'supersede_fact', 'id': 'f1', 'fact': fact('f2')}],
                           base_version='v1')
    assert run(repo, directory)['version'] == 'v2'
    by_id = {item['id']: item for item in repo.facts()}
    assert by_id['f1']['superseded_by'] == 'f2' and 'superseded_by' not in by_id['f2']
    assert 'superseded_by' not in {key for item in repo.facts('v1') for key in item}


def test_supersede_unknown_or_already_superseded_is_rejected(tmp_path):
    repo = seeded(tmp_path)
    unknown = run(repo, submission(
        tmp_path, [{'op': 'supersede_fact', 'id': 'nope', 'fact': fact('f2')}],
        base_version='v1'))
    assert not unknown['accepted'] and any('does not exist' in x for x in unknown['diagnostics'])
    run(repo, submission(tmp_path, [{'op': 'supersede_fact', 'id': 'f1', 'fact': fact('f2')}],
                         name='s3', base_version='v1'))
    again = run(repo, submission(
        tmp_path, [{'op': 'supersede_fact', 'id': 'f1', 'fact': fact('f3')}], name='s4',
        base_version='v2'))
    assert not again['accepted'] and any('already superseded' in x for x in again['diagnostics'])
    twice = run(repo, submission(
        tmp_path, [{'op': 'supersede_fact', 'id': 'f2', 'fact': fact('f4')},
                   {'op': 'supersede_fact', 'id': 'f2', 'fact': fact('f5')}], name='s5',
        base_version='v2'))
    assert not twice['accepted']


def test_duplicate_fact_ids_are_rejected(tmp_path):
    repo = seeded(tmp_path)
    existing = run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact('f1')}],
                                    base_version='v1'))
    assert not existing['accepted'] and any('not new' in x for x in existing['diagnostics'])
    within = run(repo, submission(
        tmp_path, [{'op': 'add_fact', 'fact': fact('f9')}, {'op': 'add_fact', 'fact': fact('f9')}],
        name='s2', base_version='v1'))
    assert not within['accepted']
    assert repo.published() == 'v1'


def test_wrong_scope_game_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                              {'op': 'add_fact', 'fact': fact(game='other')}]))
    assert not verdict['accepted'] and any('scope game' in x for x in verdict['diagnostics'])


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
    assert not verdict['accepted'] and verdict['diagnostics']
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
        assert not verdict['accepted'], name
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
    assert not verdict['accepted'] and verdict['version'] is None
    assert any('forced tag failure' in x for x in verdict['diagnostics'])
    assert repo.published() == 'v0'
    assert snapshot(repo) == before
    assert repo.facts() == []
    retry = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()},
                                            {'op': 'add_fact', 'fact': fact()}], name='s2'))
    assert retry['accepted'] and repo.published() == 'v1'


def test_gate_log_gains_one_line_per_call(tmp_path):
    repo = make_repo(tmp_path)
    run(repo, submission(tmp_path, [{'op': 'add_fact', 'fact': fact()}]))
    run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}], name='s2'))
    run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}], name='s3'))
    lines = (repo.state / 'gate.jsonl').read_text().splitlines()
    assert [json.loads(line)['accepted'] for line in lines] == [False, True, False]
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
        assert not verdict['accepted'] and 'not a regular file' in verdict['diagnostics'][0]
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
        assert not verdict['accepted'] and verdict['diagnostics'], directory.name
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
    assert verdict['accepted'] and repo.published() == 'v1'
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
    result = sandbox.Result(0, None, 0, 0, 0.1, [4242], {})
    drafts = Drafts(repo.state)
    record = session._close_out(repo, 'sess', record_dir, workspace, None, result, [], FRAMES, drafts, {})
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
    result = sandbox.Result(0, None, 0, 0, 0.1, [], {})
    record = session._close_out(repo, 'sess', record_dir, workspace, None, result, [], FRAMES,
                                Drafts(repo.state), {})
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and any('MemoryError' in e for e in life['errors'])
    assert record['verdicts'] == [] and (record_dir / 'close-out.json').is_file()


def test_submission_names_cannot_add_lines_to_the_commit_message(tmp_path):
    repo = make_repo(tmp_path)
    verdict = run(repo, submission(tmp_path, [{'op': 'add_type', 'type': kind()}],
                                   name='s1\nCo-Authored-By: someone <x@example.com>'))
    assert verdict['accepted']
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
