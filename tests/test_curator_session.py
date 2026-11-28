"""Curator sessions end to end with scripted hosts under the real sandbox (#453).

Each test runs a short Python "host" inside the macOS Seatbelt sandbox over a synthetic sealed
trace window. It is a native lane: it skips off macOS, where the sandbox does not exist.
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
import time

import pytest

from harness.curator import sandbox
from harness.curator.knowledge import Repository
from harness.curator.session import SessionConfig, SessionError, run_session
from harness.curator.window import Window
from tests.curator_trace import SESSION_ID, frame_id, make_long_session, record_package
from tests.test_trace_projection import make_session

PYTHON = Path(os.path.realpath(sys.executable))
PYTHON_ROOT = Path(sys.base_prefix).resolve()
native = pytest.mark.skipif(sys.platform != 'darwin' or not Path(sandbox.SANDBOX_EXEC).exists(),
                            reason='Seatbelt lane: macOS only')
pytestmark = native

SUBMIT = '''
import json, os, sys
manifest = json.load(open('trace/manifest.json'))
frame = sorted(k[7:-4] for k in manifest['files'] if k.startswith('frames/'))[0]
version = open('brief.md').read().split('`')[1]
cite = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != '-' else frame
os.makedirs('submissions/s1')
json.dump(dict(schema='curator-submission/3', base_version=version, summary='first fact',
               from_drafts=[d for d in os.listdir('drafts')],
               changes=[dict(op='add_fact', fact=dict(schema='curator-fact/6', record='fact', id='f1',
                                                      statement_kind='observation', tags=['container'],
                                                      text='the cupboard holds bottles',
                                                      scope={}, links=[], citations=[cite],
                                                      subject='cupboard'))]),
          open('submissions/s1/submission.json', 'w'))
'''
DRAFT = '''
import os
os.makedirs('drafts/plan', exist_ok=True)
open('drafts/plan/notes.md', 'w').write('unfinished idea')
'''
IDLE = 'pass'
WAIT = 'import os, time\nos.makedirs("drafts/kept", exist_ok=True)\nopen("drafts/kept/x","w").write("1")\ntime.sleep(60)'
TWO_STALE = SUBMIT.replace("os.makedirs('submissions/s1')", "os.makedirs('submissions/s1'); os.makedirs('submissions/s2')") + \
    "\nimport shutil\nshutil.copyfile('submissions/s1/submission.json','submissions/s2/submission.json')\n"


def host(tmp_path: Path, name: str, code: str, *args, wall=30.) -> SessionConfig:
    scripts = (tmp_path/'scripts').resolve()
    scripts.mkdir(exist_ok=True)
    (scripts/f'{name}.py').write_text(textwrap.dedent(code))
    return SessionConfig(argv=(str(PYTHON), '-I', str(scripts/f'{name}.py'), *args),
                         tools=(PYTHON_ROOT, scripts), limits=sandbox.Limits(wall_seconds=wall),
                         host=dict(name='scripted', script=name))


@pytest.fixture
def world(tmp_path):
    repo = Repository(tmp_path/'knowledge', 'testgame')
    trace = make_session(tmp_path/'evidence')
    return repo, [trace]


def test_a_scripted_session_submits_a_fact_and_leaves_a_draft(tmp_path, world):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'both', SUBMIT + DRAFT))
    assert record['manifest']['lifecycle']['state'] == 'sealed'
    assert [v['status'] for v in record['verdicts']] == ['published'] and record['published_after'] == 'v1'
    assert [f['text'] for f in repo.facts('v1')] == ['the cupboard holds bottles']
    assert record['drafts']['created'] == ['plan']
    assert not any((repo.state/'workspaces').iterdir())  # the workspace is gone
    second = run_session(repo, trace, host(tmp_path, 'idle', IDLE))
    brief = (repo.state/'sessions'/second['manifest']['id']/'brief.md').read_text()
    assert '`v1`' in brief and '`plan`' in brief and 'published as `v1`' in brief


def test_a_scripted_session_publishes_verified_world_provenance(tmp_path, world):
    repo, traces = world
    trace, = traces
    labels = dict(world='pond', lineage='survivor', admission=1)
    record_package(trace, labels=labels)
    record = run_session(repo, traces, host(tmp_path, 'world', SUBMIT.replace("scope={}", "scope={}, binds=['world']")))
    assert [v['status'] for v in record['verdicts']] == ['published'], record
    assert repo.facts()[0]['scope'] == dict(game='testgame', world='pond')
    assert repo.provenance()['sessions'] == {SESSION_ID: dict(name=trace.name, context={}, **labels)}


def test_out_of_window_citations_are_rejected_and_reported_in_the_next_brief(tmp_path, world):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'outside', SUBMIT, 'f'*32 + '-9'))
    assert record['verdicts'][0]['status'] == 'rejected' and repo.published() == 'v0'
    assert any('window' in d for d in record['verdicts'][0]['diagnostics'])
    second = run_session(repo, trace, host(tmp_path, 'idle', IDLE))
    assert 'rejected:' in (repo.state/'sessions'/second['manifest']['id']/'brief.md').read_text()


@pytest.mark.parametrize('field', ['expected_brief_sha256', 'expected_trace_manifest_sha256'])
def test_retained_input_assertions_pass_real_hosts_and_block_a_changed_input(tmp_path, world, monkeypatch, field):
    repo, trace = world
    config = host(tmp_path, 'retained-idle', IDLE)
    first = run_session(repo, trace, config)
    pinned = first['manifest']['pinned']
    checked = replace(config, expected_brief_sha256=pinned['brief_sha256'],
                      expected_trace_manifest_sha256=pinned['trace_manifest_sha256'])
    assert run_session(repo, trace, checked)['manifest']['lifecycle']['state'] == 'sealed'

    def forbidden(*args, **kwargs):
        raise AssertionError('changed input must not start a host')

    monkeypatch.setattr(sandbox, 'run', forbidden)
    rejected = run_session(repo, trace, replace(checked, **{field: '0'*64}))
    assert rejected['manifest']['lifecycle']['state'] == 'aborted'
    assert any('retained-prefix next' in error for error in rejected['manifest']['lifecycle']['errors'])
    assert rejected['verdicts'] == [] and repo.published() == 'v0'


def test_a_second_submission_on_the_same_base_is_stale(tmp_path, world):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'two', TWO_STALE))
    assert [v['status'] for v in record['verdicts']] == ['published', 'rejected']
    assert any('v1' in d for d in record['verdicts'][1]['diagnostics'])


def test_drafts_go_stale_then_are_abandoned_and_archived(tmp_path, world):
    repo, trace = world
    run_session(repo, trace, host(tmp_path, 'draft', DRAFT))
    idle = host(tmp_path, 'idle', IDLE)
    states = []
    for _ in range(6):
        record = run_session(repo, trace, idle)
        states.append(sorted(record['drafts']['stale'] + record['drafts']['abandoned']))
    assert states == [[], [], ['plan'], [], [], ['plan']]
    assert not (repo.state/'drafts'/'plan').exists() and (repo.state/'drafts-archive'/'plan').exists()


def test_writing_to_a_draft_renews_it(tmp_path, world):
    repo, trace = world
    run_session(repo, trace, host(tmp_path, 'draft', DRAFT))
    for _ in range(2):
        run_session(repo, trace, host(tmp_path, 'idle', IDLE))
    touch = host(tmp_path, 'touch', "open('drafts/plan/notes.md','a').write(' more')")
    assert run_session(repo, trace, touch)['drafts']['renewed'] == ['plan']
    record = run_session(repo, trace, host(tmp_path, 'idle', IDLE))
    assert record['drafts']['stale'] == []


def test_an_aborted_session_keeps_its_drafts_and_gates_nothing(tmp_path, world):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'wait', SUBMIT.replace('first fact', 'x') + WAIT, wall=2.))
    assert record['manifest']['lifecycle']['state'] == 'aborted'
    assert record['manifest']['lifecycle']['stopped'] == 'wall-clock limit'
    assert record['verdicts'] == [] and repo.published() == 'v0'
    assert record['drafts']['created'] == ['kept'] and (repo.state/'drafts'/'kept'/'x').is_file()


def test_accepting_a_submission_promotes_the_drafts_it_names(tmp_path, world):
    repo, trace = world
    run_session(repo, trace, host(tmp_path, 'draft', DRAFT))
    record = run_session(repo, trace, host(tmp_path, 'submit', SUBMIT))
    assert record['verdicts'][0]['status'] == 'published' and record['verdicts'][0]['from_drafts'] == ['plan']
    assert (repo.state/'drafts-archive'/'plan').exists() and not (repo.state/'drafts'/'plan').exists()
    manifest = json.loads((repo.state/'drafts-archive'/'plan'/'manifest.json').read_text())
    assert manifest['lifecycle']['state'] == 'promoted'


def test_the_workspace_cannot_write_published_knowledge_or_the_trace(tmp_path, world):
    repo, trace = world
    attack = ("import os\nfrom pathlib import Path\nbacking = Path(os.environ['CURATOR_KNOWLEDGE_BACKING'])\n"
              "for p in (backing/'facts.jsonl', backing/'validation-context.json', "
              "'knowledge/index.md', 'trace/manifest.json', 'brief.md'):\n"
              "    try: open(p,'a').write('x'); print('WROTE', p)\n"
              "    except OSError: print('denied', p)\n")
    record = run_session(repo, trace, host(tmp_path, 'attack', attack))
    log = (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()
    assert 'WROTE' not in log and log.count('denied') == 5


def test_current_workspace_view_filters_history_without_editing_the_published_store(tmp_path, world):
    repo, trace = world
    run_session(repo, trace, host(tmp_path, 'publish', SUBMIT))
    replacement = SUBMIT + '''
p = 'submissions/s1/submission.json'
with open(p) as stream:
    proposal = json.load(stream)
fact = dict(proposal['changes'][-1]['fact'], id='f2')
proposal['changes'] = [dict(op='supersede_fact', ids=['f1'], reason_kind='restated', fact=fact)]
with open(p, 'w') as stream:
    json.dump(proposal, stream)
'''
    record = run_session(repo, trace, host(tmp_path, 'replace', replacement))
    assert record['published_after'] == 'v2', record
    records = (repo.path/'facts.jsonl').read_bytes()
    verify = '''
import json, os, sys
from pathlib import Path
knowledge = Path('knowledge')
backing = Path(os.environ['CURATOR_KNOWLEDGE_BACKING'])
assert backing.parent == Path.cwd().parent and backing.name == Path.cwd().name + '.backing'
assert {path.name for path in knowledge.iterdir()} <= {
    'index.md', 'records', 'knowledge.json', 'provenance.json', 'coverage.json'}
assert 'Current world state keys' in (knowledge/'index.md').read_text()
assert {path.name for path in (knowledge/'records').iterdir()} == {'f2.json'}
assert (knowledge/'knowledge.json').stat().st_mode & 0o777 == 0o444
history = [json.loads(line) for line in (backing/'facts.jsonl').read_text().splitlines()]
assert [row['id'] for row in history] == ['f1', 'f2']
assert history[0]['superseded_by'] == ['f2']
assert json.loads((knowledge/'records'/'f2.json').read_text()) == history[1]
sys.path[:0] = os.environ['PYTHONPATH'].split(os.pathsep)
from harness.curator.search import main
main(['search', 'cupboard'])
main(['search', 'cupboad hlds botles'])
main(['get', 'f1'])
'''
    record = run_session(repo, trace, host(tmp_path, 'check-current', verify))
    assert record['manifest']['lifecycle']['state'] == 'sealed', record
    session_id = record['manifest']['id']
    output = repo.state/'sessions'/session_id/'host-output.log'
    lexical, fuzzy, historical = map(json.loads, output.read_text().splitlines())
    assert (lexical['id'], lexical['via']) == ('f2', 'match')
    assert (fuzzy['id'], fuzzy['via']) == ('f2', 'fuzzy')
    assert historical['id'] == 'f1'
    assert not (repo.state/'workspaces'/f'{session_id}.backing').exists()
    assert (repo.path/'facts.jsonl').read_bytes() == records
    assert not (repo.path/'current-facts.jsonl').exists()


LINKS = '''
import os, sys
secret_dir, secret_file = sys.argv[1], sys.argv[2]
os.symlink(secret_dir, 'drafts/evil')
os.makedirs('drafts/inner')
os.symlink(secret_file, 'drafts/inner/k')
os.makedirs('drafts/plain')
open('drafts/plain/n', 'w').write('fine')
os.mkfifo('drafts/plain-fifo') if hasattr(os, 'mkfifo') else None
'''
REPLACE = '''
import os, sys
os.rmdir('drafts')
os.symlink(sys.argv[1], 'drafts')
print('replaced drafts')
'''
LINKED_SUBMISSION = SUBMIT + '''
os.makedirs('submissions/s2')
os.symlink(sys.argv[2], 'submissions/s2/submission.json')
'''


@pytest.fixture
def secrets(tmp_path):
    directory = tmp_path/'host-secrets'
    directory.mkdir()
    (directory/'key').write_text('do not copy')
    return directory


def _leaked(repo) -> bool:
    return any('do not copy' in p.read_text(errors='replace')
               for p in repo.state.rglob('*') if p.is_file() and not p.is_symlink())


def test_links_and_special_files_in_drafts_are_refused_not_followed(tmp_path, world, secrets):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'links', LINKS, str(secrets), str(secrets/'key')))
    assert record['drafts']['created'] == ['plain']
    assert sorted(r['id'] for r in record['drafts']['refused']) == ['evil', 'inner', 'plain-fifo']
    assert not _leaked(repo)
    after = run_session(repo, trace, host(tmp_path, 'idle', IDLE))
    assert after['manifest']['inputs']['drafts'] == ['plain']


def test_a_writable_directory_replaced_by_a_link_is_not_collected(tmp_path, world, secrets):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'replace', REPLACE, str(secrets)))
    log = (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()
    if 'replaced drafts' in log:  # the sandbox allowed the swap; close-out must refuse it
        assert any(r.startswith('drafts:') for r in record['manifest']['lifecycle']['refused'])
    assert record['drafts'] == {} or record['drafts']['created'] == []
    assert not _leaked(repo) and secrets.joinpath('key').read_text() == 'do not copy'


def test_a_linked_submission_file_stops_all_gating(tmp_path, world, secrets):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'linksub', LINKED_SUBMISSION, '-', str(secrets/'key')))
    assert record['verdicts'] == [] and repo.published() == 'v0'
    assert any(r.startswith('submissions:') for r in record['manifest']['lifecycle']['refused'])
    assert not _leaked(repo)


def test_the_workbench_and_its_dependencies_run_inside_a_session(tmp_path, world):
    repo, trace = world
    code = ("import os, subprocess, sys\n"
            "python = sys.argv[1]  # the resolved interpreter: Homebrew's sys.executable is a link outside the roots\n"
            "r = subprocess.run([python, '-m', 'harness.trace.workbench', '--help'], cwd='workbench',"
            " capture_output=True, text=True)\n"
            "print('RC', r.returncode); print(r.stderr[-400:])\n"
            "r = subprocess.run([python, '-c', 'import harness.trace.images, numpy, PIL; print(\"IMPORTED\")'],"
            " capture_output=True, text=True)\n"
            "print(r.stdout, r.stderr[-400:])\n")
    record = run_session(repo, trace, host(tmp_path, 'workbench', code, str(PYTHON)))
    log = (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()
    assert 'RC 0' in log and 'IMPORTED' in log, log


def test_a_failure_before_the_host_runs_is_sealed_as_aborted(tmp_path, world):
    repo, _trace = world
    record = run_session(repo, [tmp_path/'no-such-session'], host(tmp_path, 'idle', IDLE))
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and life['errors'] and life['errors'][0].startswith('session:')
    record_dir = repo.state/'sessions'/record['manifest']['id']
    assert json.loads((record_dir/'close-out.json').read_text())['manifest']['lifecycle']['state'] == 'aborted'
    assert not any((repo.state/'workspaces').iterdir())


def test_only_one_session_runs_per_repository(tmp_path, world):
    repo, trace = world
    import fcntl
    repo.ensure()
    repo.state.mkdir(parents=True, exist_ok=True)
    with (repo.state/'lock').open('w') as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(SessionError, match='Another curator session'):
            run_session(repo, trace, host(tmp_path, 'idle', IDLE))


def test_actual_sigint_during_native_execution_retains_abort_and_closes_the_owned_host(tmp_path, world):
    repo, trace = world
    config = host(tmp_path, 'sigint-host', '''
        import os, time
        open('scratch/ready', 'w').write(str(os.getpid()))
        time.sleep(15)
    ''')
    driver = tmp_path/'driver.py'
    driver.write_text('''
import json, sys
from pathlib import Path
from harness.curator.knowledge import Repository
from harness.curator.session import SessionConfig, run_session
from harness.curator.sandbox import Limits
c = json.loads(Path(sys.argv[1]).read_text())
run_session(Repository(Path(c['repo']), 'testgame'), [Path(c['trace'])],
            SessionConfig(argv=tuple(c['argv']), tools=tuple(map(Path, c['tools'])),
                          limits=Limits(wall_seconds=30)), session_id='sigint')
''')
    package = tmp_path/'driver.json'
    package.write_text(json.dumps(dict(repo=str(repo.path.parent), trace=str(trace[0]), argv=config.argv,
                                       tools=list(map(str, config.tools)))))
    ready = repo.state/'workspaces/sigint/scratch/ready'
    log = tmp_path/'driver.log'
    with log.open('wb') as output:
        child = subprocess.Popen([sys.executable, str(driver), str(package)], start_new_session=True,
                                 stdout=output, stderr=output, cwd=Path(__file__).resolve().parents[1],
                                 env=dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'),
                                          PYTHONPATH=str(Path(__file__).resolve().parents[1])))
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            assert ready.exists() and child.poll() is None, log.read_text()
            host_pid = int(ready.read_text())
            child.send_signal(signal.SIGINT)
            assert child.wait(timeout=10) == -signal.SIGINT, log.read_text()
        finally:
            if child.poll() is None:
                sandbox._close(child)
    record = json.loads((repo.state/'sessions/sigint/close-out.json').read_text())
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and life['returncode'] is None and life['survivors'] is None
    assert any('KeyboardInterrupt' in error for error in life['errors'])
    assert not any((repo.state/'workspaces').iterdir())
    with pytest.raises(ProcessLookupError):
        os.kill(host_pid, 0)
    assert run_session(repo, trace, host(tmp_path, 'after-sigint', IDLE))['manifest']['lifecycle']['state'] == 'sealed'


SHOW_TRACE = '''
import json, os
manifest = json.load(open('trace/manifest.json'))
print('WINDOW', json.dumps(manifest.get('window')))
print('FRAMES', json.dumps(sorted(os.listdir('trace/frames'))))
print('ACTORS', json.dumps(sorted(os.listdir('trace/s1'))))
print('STEPS', json.dumps([json.loads(l)['seq'] for l in open('trace/s1/001/steps.jsonl')]))
'''


@pytest.fixture
def long_world(tmp_path):
    return Repository(tmp_path/'knowledge', 'testgame'), [make_long_session(tmp_path/'evidence')]


def _log(repo, record) -> str:
    return (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()


def test_a_window_session_is_given_only_its_steps_and_frames_and_the_brief_says_so(tmp_path, long_world):
    repo, trace = long_world
    window = Window('s1', '001', 4, 6)
    record = run_session(repo, trace, host(tmp_path, 'show', SHOW_TRACE), window=window)
    log = _log(repo, record)
    assert record['manifest']['lifecycle']['state'] == 'sealed', record['manifest']['lifecycle']
    assert 'STEPS [4, 5, 6]' in log and 'ACTORS ["001"]' in log
    assert json.loads(log.split('FRAMES ')[1].splitlines()[0]) == [f'{frame_id(1, n)}.png' for n in (4, 5, 6)]
    assert json.loads(log.split('WINDOW ')[1].splitlines()[0])['last'] == 6
    brief = (repo.state/'sessions'/record['manifest']['id']/'brief.md').read_text()
    assert 'steps 4 to 6 of 12 of actor `001`' in brief
    assert record['manifest']['inputs']['window'] == window.record() and record['manifest']['inputs']['window_frames'] == 3


def test_a_window_session_cannot_cite_a_frame_outside_its_range_and_publishes_its_coverage(tmp_path, long_world):
    repo, trace = long_world
    window = Window('s1', '001', 4, 6)
    outside = run_session(repo, trace, host(tmp_path, 'outside', SUBMIT, frame_id(1, 3)), window=window)
    verdict = outside['verdicts'][0]
    assert verdict['status'] == 'rejected' and repo.published() == 'v0'
    assert any(f'citation {frame_id(1, 3)!r} is outside the trace window' in d for d in verdict['diagnostics'])
    other_actor = run_session(repo, trace, host(tmp_path, 'other', SUBMIT, frame_id(2, 5)), window=window)
    assert other_actor['verdicts'][0]['status'] == 'rejected'
    inside = run_session(repo, trace, host(tmp_path, 'inside', SUBMIT), window=window)
    assert inside['verdicts'][0]['status'] == 'published' and repo.published() == 'v1'
    assert json.loads(subprocess.run(['git', 'show', 'v1:coverage.json'], cwd=repo.path, capture_output=True,
                                     text=True, check=True).stdout) == dict(
        schema='curator-coverage/2', session='s1', actor='001', last_step=6)
    assert inside['manifest']['inputs']['coverage']['last_step'] == 6


def test_a_whole_admission_session_is_the_full_window_and_stamps_no_actor(tmp_path, long_world):
    repo, trace = long_world
    record = run_session(repo, trace, host(tmp_path, 'whole', SUBMIT))
    assert record['verdicts'][0]['status'] == 'published'
    stamp = json.loads(subprocess.run(['git', 'show', 'v1:coverage.json'], cwd=repo.path, capture_output=True,
                                      text=True, check=True).stdout)
    assert stamp == dict(schema='curator-coverage/2', session='s1', actor=None, last_step=None)
    assert record['manifest']['inputs']['window'] == {}
    assert 'This trace is a window' not in (repo.state/'sessions'/record['manifest']['id']/'brief.md').read_text()


def test_a_window_that_does_not_fit_its_trace_aborts_the_session_before_the_host_runs(tmp_path, long_world, monkeypatch):
    repo, trace = long_world
    monkeypatch.setattr(sandbox, 'run', lambda *a, **k: pytest.fail('the host must not start'))
    record = run_session(repo, trace, host(tmp_path, 'idle', IDLE), window=Window('s1', '001', 13, 20))
    life = record['manifest']['lifecycle']
    assert life['state'] == 'aborted' and any('starts at 13' in e for e in life['errors'])


def test_citations_accumulate_across_windows_of_one_admission(tmp_path, long_world):
    repo, trace = long_world
    first = run_session(repo, trace, host(tmp_path, 'first', SUBMIT), window=Window('s1', '001', 1, 2))
    assert first['verdicts'][0]['status'] == 'published', first
    # The next window proposes a distinct fact using the same tag.
    second_code = SUBMIT + '''
p = 'submissions/s1/submission.json'
data = json.load(open(p))
data['changes'][0]['fact']['id'] = 'f2'
json.dump(data, open(p, 'w'))
'''
    second = run_session(repo, trace, host(tmp_path, 'second', second_code), window=Window('s1', '001', 3, 4))
    assert second['verdicts'][0]['status'] == 'published', second
    assert repo.provenance()['last_admission']['citations'] == [frame_id(1, 1), frame_id(1, 3)]
    assert repo.provenance()['last_admission']['coverage']['last_step'] == 4


@pytest.mark.parametrize('edited, published', [(None, 2), ('02', 1), ('01', 0)])
def test_provider_error_seals_only_the_longest_validated_prefix(tmp_path, world, monkeypatch, edited, published):
    from harness.curator.session import PROVIDER_ERROR_EXIT_CODE
    from harness.curator.validate import validate

    repo, traces = world
    drafts_aged = []

    def scripted(_argv, layout, *, stdout, extra_env, **_kwargs):
        workspace = layout.workspace
        backing = Path(extra_env['CURATOR_KNOWLEDGE_BACKING'])
        assert backing in layout.tools
        assert not (workspace/'knowledge'/'validation-context.json').exists()
        monkeypatch.setenv('CURATOR_KNOWLEDGE_BACKING', str(backing))
        frame = next(iter(json.loads((backing/'validation-context.json').read_text())['window_frames']))
        for i in range(1, 4):
            directory = workspace/'submissions'/f'{i:02}'
            directory.mkdir()
            fact = dict(schema='curator-fact/6', record='fact', id=f'f{i}', statement_kind='observation',
                        tags=[], scope={}, links=[], citations=[frame], text='Observed.')
            (directory/'submission.json').write_text(json.dumps(dict(
                schema='curator-submission/3', base_version=f'v{i - 1}', summary='valid prefix',
                changes=[dict(op='add_fact', fact=fact)])))
        for identifier in ('02', '01'):
            result = validate(workspace, identifier)
            assert result['all_passed']
            event = dict(type='submission-validated', all_passed=True, prefix=result['prefix'])
            stdout.write((json.dumps(event) + '\n').encode())
        stdout.write(b'{"type":"submission-validated","all_passed":true,"prefix":[null]}\n')
        if edited:
            path = workspace/'submissions'/edited/'submission.json'
            path.write_text(path.read_text() + '\n')
        return sandbox.Result(PROVIDER_ERROR_EXIT_CODE, None, 0, 0, 0.1, [])

    from harness.curator.containers import Drafts
    original_collect = Drafts.collect

    def collect(self, *args, age=True, **kwargs):
        drafts_aged.append(age)
        return original_collect(self, *args, age=age, **kwargs)

    monkeypatch.setattr(sandbox, 'run', scripted)
    monkeypatch.setattr(Drafts, 'collect', collect)
    result = run_session(repo, traces, SessionConfig(argv=('stand-in',)))
    life = result['manifest']['lifecycle']
    assert life['state'] == 'sealed' and life['stopped'] == 'provider-error', result
    assert [v['status'] for v in result['verdicts']] == ['published'] * published
    assert result['published_after'] == f'v{published}' and drafts_aged == [False]
    record_dir = repo.state/'sessions'/result['manifest']['id']
    assert len(list((record_dir/'submissions').glob('*/submission.json'))) == 3
    assert len(life['refused']) == 3 - published


def test_real_sandbox_can_run_the_staged_validator(tmp_path, world):
    repo, trace = world
    script = SUBMIT + '''
import subprocess
result = subprocess.run([sys.argv[2], '-m', 'harness.curator.validate', '--workspace', os.getcwd(),
                         '--submission', 's1'], cwd='workbench', capture_output=True, text=True)
assert result.returncode == 0, result.stderr
print(result.stdout.strip())
'''
    record = run_session(repo, trace, host(tmp_path, 'validate', script, '-', str(PYTHON)))
    log = (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()
    assert record['published_after'] == 'v1', (record, log)
    assert json.loads(log)['prefix'][0]['candidate_version'] == 'v1'


def test_knowledge_search_only_hops_from_active_eligible_records_and_matches_article_claims():
    from harness.curator.search import search

    def fact(identity, text, **fields):
        return dict(dict(id=identity, record='fact', text=text, tags=[], links=[], scope={'game': 'testgame'},
                         lifecycle_state='active'), **fields)

    records = [
        fact('seed', 'Electrical resistance', when='furnace', lifecycle_state='contested',
             links=[dict(rel='see_also', target='related'), dict(rel='contradicts', target='conflict')]),
        fact('related', 'Voltage'),
        fact('conflict', 'Opposing reading', lifecycle_state='contested'),
        fact('wrong-world', 'furnace', scope={'game': 'testgame', 'world': 'other'}),
        fact('ended', 'furnace', lifecycle_state='ended'),
        fact('shadow', 'furnace', shadowed_by=['seed']),
        dict(id='manual@v1', slug='manual', record='article', title='Manual', tags=[], links=[],
             lead='Technical notes', body=[dict(text='Operate the furnace using insulated controls.', facts=['seed'])],
             scope={'game': 'testgame'}, lifecycle_state='active'),
    ]
    hits = {hit['id']: hit for hit in search(records, {}, 'furnace', world='selected')}
    assert set(hits) == {'seed', 'related', 'manual'}
    assert hits['seed']['status'] == ['contested'] and hits['seed']['contradicts'] == ['conflict']
    assert hits['related']['via'] == 'hop'
    assert hits['manual']['snippet'] == 'Operate the furnace using insulated controls.'
