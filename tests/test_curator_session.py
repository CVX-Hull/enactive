"""Curator sessions end to end with scripted hosts under the real sandbox (#453).

Each test runs a short Python "host" inside the macOS Seatbelt sandbox over a synthetic sealed
trace window. It is a native lane: it skips off macOS, where the sandbox does not exist.
"""
from __future__ import annotations

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
json.dump(dict(schema='curator-submission/1', base_version=version, summary='first fact',
               from_drafts=[d for d in os.listdir('drafts')],
               changes=[dict(op='add_type', type=dict(schema='curator-type/1', name='container',
                                                    description='a place that holds items', fields=['holds'])),
                        dict(op='add_fact', fact=dict(schema='curator-fact/1', id='f1', type='container',
                                                      statement='the cupboard holds bottles',
                                                      scope=dict(game='testgame'), citations=[cite]))]),
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
    volume = record['manifest']['provenance']['volume_space']
    assert volume['floor_bytes'] == volume['initial_free_bytes'] - (2 << 30)
    assert volume['minimum_free_bytes'] <= min(volume['initial_free_bytes'], volume['last_free_bytes'])
    assert [v['accepted'] for v in record['verdicts']] == [True] and record['published_after'] == 'v1'
    assert [f['statement'] for f in repo.facts('v1')] == ['the cupboard holds bottles']
    assert record['drafts']['created'] == ['plan']
    assert not any((repo.state/'workspaces').iterdir())  # the workspace is gone
    second = run_session(repo, trace, host(tmp_path, 'idle', IDLE))
    brief = (repo.state/'sessions'/second['manifest']['id']/'brief.md').read_text()
    assert '`v1`' in brief and '`plan`' in brief and 'accepted as `v1`' in brief


def test_out_of_window_citations_are_rejected_and_reported_in_the_next_brief(tmp_path, world):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'outside', SUBMIT, 'f'*32 + '-9'))
    assert record['verdicts'][0]['accepted'] is False and repo.published() == 'v0'
    assert any('window' in d for d in record['verdicts'][0]['diagnostics'])
    second = run_session(repo, trace, host(tmp_path, 'idle', IDLE))
    assert 'rejected:' in (repo.state/'sessions'/second['manifest']['id']/'brief.md').read_text()


def test_a_second_submission_on_the_same_base_is_stale(tmp_path, world):
    repo, trace = world
    record = run_session(repo, trace, host(tmp_path, 'two', TWO_STALE))
    assert [v['accepted'] for v in record['verdicts']] == [True, False]
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
    assert record['verdicts'][0]['accepted'] and record['verdicts'][0]['from_drafts'] == ['plan']
    assert (repo.state/'drafts-archive'/'plan').exists() and not (repo.state/'drafts'/'plan').exists()
    manifest = json.loads((repo.state/'drafts-archive'/'plan'/'manifest.json').read_text())
    assert manifest['lifecycle']['state'] == 'promoted'


def test_the_workspace_cannot_write_published_knowledge_or_the_trace(tmp_path, world):
    repo, trace = world
    attack = ("import json\nfor p in ('knowledge/facts.jsonl','trace/manifest.json','brief.md'):\n"
              "    try: open(p,'a').write('x'); print('WROTE', p)\n"
              "    except OSError: print('denied', p)\n")
    record = run_session(repo, trace, host(tmp_path, 'attack', attack))
    log = (repo.state/'sessions'/record['manifest']['id']/'host-output.log').read_text()
    assert 'WROTE' not in log and log.count('denied') == 3


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
