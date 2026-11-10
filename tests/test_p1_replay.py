"""The P1 offline replay: arm B's schedule, the delivered rows, the held-out freeze and the memory cutoff (#462).

No model call is made. Arm B's curator session is a local fake that publishes one fact, run through
the same `shadow.run_one` seam the real runner uses, so the schedule and the memory cutoff are
exercised end to end on synthetic sessions. The freeze is exercised in a temporary Git repository.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

from harness.curator import session as curator_session
from harness.curator.knowledge import Repository
from harness.trace import projection
from harness.trace.projection import project
from tests.test_p1_arms import GAME, LAYOUT, fact, make_memory, make_sessions, publish
from tests.test_trace_projection import make_session, make_store
from tools import p1_analysis
from tools.curator_host import p1_arms as arms
from tools.curator_host import p1_replay as replay
from tools.curator_host import shadow

PRICES = shadow.DEFAULT_PRICES
ROW_FIELDS = {'schema', 'lineage', 'boundary', 'kind', 'arm', 'repeat', 'text', 'tokens', 'items', 'dropped',
              'received_sha256', 'complete'}
MEMORY = [dict(id='r1', wall=5., text='alpha-note', kind='claim'),
          dict(id='r2', wall=25., text='beta-note', data={'k': 1}),
          dict(id='r3', wall=50., text='gamma-note corrects alpha', kind='correction', supersedes='r1'),
          dict(id='r4', wall=110., text='delta-note')]


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A synthetic one-lineage evidence tree under a temporary runtime root."""
    runtime = tmp_path.resolve()/'runtime'
    evidence = tmp_path.resolve()/'evidence'
    make_sessions(evidence/'syn'/'computer-sessions', LAYOUT)
    make_memory(evidence/'syn'/'player-memory-syn.sqlite3', MEMORY)
    monkeypatch.setitem(replay.LINEAGES, 'syn', replay.Lineage('syn', ('t1', 't2'), 'player-memory-syn.sqlite3'))
    return runtime, evidence


def add_second_lineage(evidence, monkeypatch):
    make_sessions(evidence/'syn2'/'computer-sessions', {'u1': {'001': [10., 20.]}, 'u2': {'001': [100., 110.]}})
    make_memory(evidence/'syn2'/'player-memory-syn2.sqlite3', [dict(id='q1', wall=5., text='other')])
    monkeypatch.setitem(replay.LINEAGES, 'syn2', replay.Lineage('syn2', ('u1', 'u2'), 'player-memory-syn2.sqlite3'))


def b_args(runtime, evidence, *extra, stage='dev', repeat=1, cap='100', lineage=('syn',)):
    args = replay.parser().parse_args(['b', '--stage', stage, '--repeat', str(repeat), '--lineage', *lineage, '--cap-usd', cap,
                                       '--runtime-root', str(runtime), '--evidence-root', str(evidence), *extra])
    return args


class FakeCurator:
    """Stands in for the sandboxed host: each session publishes one fact and records what it was given."""

    def __init__(self, monkeypatch, cost='1', states=None):
        self.cuts, self.caps, self.budgets, self.on_disk, self.cost = [], [], [], [], cost
        self.states = states or {}
        monkeypatch.setattr(shadow, 'host_tools', lambda extra=(): dict(node=Path('node'), python=Path('python'), roots=(), env={}))
        monkeypatch.setattr(shadow, 'host_identity', lambda host, model_config: dict(name='fake'))
        monkeypatch.setattr(shadow, 'run_session', lambda repo, traces, config, **kw: self.cuts.append(kw.get('memory_until')))
        monkeypatch.setattr(shadow, 'run_one', self.run_one)

    def run_one(self, **kw):
        repo = kw['repo']
        before = repo.published()
        schedule = kw['out']/'schedule.json'
        self.on_disk.append(sum(len(entry['sessions']) for entry in json.loads(schedule.read_text())['lineages'].values())
                            if schedule.exists() else None)
        self.caps.append(kw['cap'])
        self.budgets.append(float(kw['cap'] * shadow.HOST_BUDGET_SHARE))
        shadow.run_session(repo, [kw['trace']], None, memory=kw['memory'], memory_until=kw['memory_until'],
                           session_id='fake')
        facts = repo.facts()
        publish(repo, [*facts, fact(f'f{len(facts) + 1}', f'curated from {kw["name"]}', published_in=f'v{int(before[1:]) + 1}')])
        return dict(run_state='completed', session_state=self.states.get(kw['name'], 'sealed'), cost_usd=self.cost,
                    published_before=before, stopped_by_cap=False, proxy=dict(revoked=False, breaches=0),
                    accepted=1, rejected=0, requests=3)


def deliver_args(runtime, evidence, out, *schedules, lineage='syn'):
    return replay.parser().parse_args(['deliver', '--lineage', lineage, '--runtime-root', str(runtime),
                                       '--evidence-root', str(evidence), '--out', str(out),
                                       *(['--schedule', *map(str, schedules)] if schedules else [])])


def rows_of(out: Path) -> list[dict]:
    return [json.loads(line) for line in (out/'delivered.jsonl').read_text().splitlines()]


def schedule_of(runtime, stage='dev', repeat=1) -> Path:
    return runtime/'curator-shadow'/'p1'/stage/f'r{repeat}'/'schedule.json'


# ------------------------------------------------------------------ arm B's sessions and their schedule
def test_b_runs_one_session_per_admission_and_records_the_versions_caps_and_cutoffs(world, monkeypatch):
    runtime, evidence = world
    fake = FakeCurator(monkeypatch)
    run = replay.run_b(b_args(runtime, evidence), 'key')
    assert fake.cuts == [100., None]    # the next admission's first operation; the last admission sees the whole store
    assert run['complete'] is True and run['stopped'] is None and run['total_cost_usd'] == '2'
    assert run['cap_usd'] == '100.0' and run['session_cap_usd'] == '12' and run['lineages'] == ['syn']
    schedule = json.loads(schedule_of(runtime).read_text())
    assert schedule['schema'] == 'p1-schedule/1' and schedule['repeat'] == 1 and schedule['knowledge'] == 'knowledge/p1/dev/r1'
    assert (schedule['cap_usd'], schedule['session_cap_usd'], schedule['lineage_order']) == ('100.0', '12', ['syn'])
    sessions = schedule['lineages']['syn']['sessions']
    assert [(s['session'], s['published_before'], s['published_after'], s['memory_until'], s['cap_usd'], s['session_state'])
            for s in sessions] == [('t1', 'v0', 'v1', 100., '12', 'sealed'), ('t2', 'v1', 'v2', None, '12', 'sealed')]
    assert json.loads((schedule_of(runtime).parent/'summary.json').read_text())['schema'] == 'curator-shadow/1'
    assert Repository(runtime/'knowledge'/'p1'/'dev'/'r1'/'syn', GAME).published() == 'v2'
    with pytest.raises(replay.ReplayError, match='exists'):   # every repeat starts fresh directories
        replay.run_b(b_args(runtime, evidence), 'key')


def test_the_schedule_is_written_after_every_session(world, monkeypatch):
    runtime, evidence = world
    fake = FakeCurator(monkeypatch)
    replay.run_b(b_args(runtime, evidence), 'key')
    assert fake.on_disk == [None, 1]    # the second session starts with the first already on disk


def test_a_session_budget_is_fixed_and_independent_of_lineage_order_and_an_ample_stage_cap(world, monkeypatch):
    runtime, evidence = world
    add_second_lineage(evidence, monkeypatch)
    seen = {}
    fake = FakeCurator(monkeypatch)
    original = shadow.host_configuration

    def spy(*a, **kw):
        seen.setdefault('budgets', []).append(kw['budget_usd'])
        return original(*a, **kw)

    monkeypatch.setattr(shadow, 'host_configuration', spy)
    replay.run_b(b_args(runtime, evidence, stage='one', lineage=('syn', 'syn2'), cap='500'), 'key')
    first = (list(fake.caps), list(fake.budgets))
    fake.caps.clear(), fake.budgets.clear()
    replay.run_b(b_args(runtime, evidence, stage='two', lineage=('syn2', 'syn'), cap='60'), 'key')
    assert first[0] == fake.caps == [Decimal(12)] * 4
    assert first[1] == fake.budgets == [pytest.approx(10.2)] * 4          # 0.85 of the session cap, as shadow does
    assert seen['budgets'] == [pytest.approx(10.2)] * 2                   # and the written host configuration too
    schedule = json.loads(schedule_of(runtime, 'two').read_text())
    assert schedule['lineage_order'] == ['syn2', 'syn'] and schedule['cap_usd'] == '60.0'
    # less than a session's cap left: the session gets what remains
    fake.caps.clear()
    replay.run_b(b_args(runtime, evidence, stage='three', lineage=('syn', 'syn2'), cap='3.5'), 'key')
    assert fake.caps == [Decimal('3.5'), Decimal('2.5'), Decimal('1.5'), Decimal('0.5')]


def test_b_uses_the_pre_registered_settings_and_a_whole_stage_cap(world, monkeypatch):
    runtime, evidence = world
    seen = {}
    fake = FakeCurator(monkeypatch)
    original = shadow.host_configuration

    def spy(*a, **kw):
        seen.update(kw)
        return original(*a, **kw)

    monkeypatch.setattr(shadow, 'host_configuration', spy)
    replay.run_b(b_args(runtime, evidence, cap='1'), 'key')   # the first session settles at the whole cap
    assert (seen['effort'], seen['max_requests'], seen['max_context_images'], seen['context_image_block']) == ('medium', 120, 24, 12)
    schedule = json.loads(schedule_of(runtime).read_text())
    assert schedule['stopped'] == 'cap-reached' and len(schedule['lineages']['syn']['sessions']) == 1
    assert fake.cuts == [100.] and replay.SETTINGS['session_cap_usd'] == 12
    for flag in ('--effort', '--max-requests', '--max-context-images', '--session-cap-usd'):
        with pytest.raises(SystemExit):                     # the settings are not options
            b_args(runtime, evidence, flag, '1')


def test_b_refuses_unknown_and_bad_arguments_before_any_directory_exists(world, monkeypatch):
    runtime, evidence = world
    FakeCurator(monkeypatch)
    with pytest.raises(replay.ReplayError):
        replay.run_b(b_args(runtime, evidence, stage='Bad Stage'), 'key')
    args = b_args(runtime, evidence)
    args.upstream = 'https://example.invalid'
    with pytest.raises(replay.ReplayError, match='upstream'):
        replay.run_b(args, 'key')
    args = b_args(runtime, evidence)
    args.lineage = ['nope']
    with pytest.raises(replay.ReplayError, match='unknown lineage'):
        replay.run_b(args, 'key')
    assert not (runtime/'curator-shadow').exists() and not (runtime/'knowledge').exists()


# ------------------------------------------------------------------ memory seen by A and by the curator
def test_a_record_written_between_two_admissions_is_seen_by_arm_a_and_by_the_curator_session_of_the_first(world):
    runtime, evidence = world
    sessions = [evidence/'syn'/'computer-sessions'/name for name in ('t1', 't2')]
    store = arms.read_store(evidence/'syn'/'player-memory-syn.sqlite3')
    (admission,) = [b for b in arms.boundaries(sessions) if b.kind == 'admission']
    cut = arms.curator_cutoffs(sessions)[0]
    assert cut == admission.cutoff == 100.            # the same instant
    # r3 was written at 50: after t1's last operation (40) and before t2's first (100)
    assert 40. < 50. < 100.
    a_sees = {i.statement for i in arms.arm_a_items(store, admission.cutoff)}
    b_sees = {r['id'] for r in projection._cut(store, cut)['records']}
    assert 'gamma-note corrects alpha' in a_sees and 'r3' in b_sees
    assert b_sees == {'r1', 'r2', 'r3'}                # r4 (110) is written during the second admission
    assert projection._cut(store, None)['records'] == store['records']   # the last admission sees all of it


# ------------------------------------------------------------------ delivered text
def test_deliver_writes_every_arm_at_every_boundary_with_the_same_received_text(world, monkeypatch, capsys):
    runtime, evidence = world
    FakeCurator(monkeypatch)
    for repeat in (1, 2):
        replay.run_b(b_args(runtime, evidence, stage=f'dev{repeat}', repeat=repeat), 'key')
    schedules = [schedule_of(runtime, f'dev{r}', r) for r in (1, 2)]
    out = runtime/'p1-delivered'/'dev'
    capsys.readouterr()   # the sessions' own progress lines
    code = replay.main(['deliver', '--lineage', 'syn', '--runtime-root', str(runtime), '--evidence-root', str(evidence),
                        '--out', str(out), '--schedule', *map(str, schedules)])
    printed = capsys.readouterr().out
    assert code == 0 and json.loads(printed) == {'syn': {'R': 3, 'A': 3, 'B1': 3, 'B2': 3}}
    assert 'note' not in printed and 'curated' not in printed          # counts only, never texts
    rows = rows_of(out)
    assert len(rows) == 12 and all(set(r) == ROW_FIELDS and r['schema'] == 'p1-delivered/1' for r in rows)
    assert all(r['complete'] is True for r in rows)
    names = ['t1-001>t1-002', 't1-002>t2-001', 't2-001>t2-002']
    by = {(r['boundary'], r['arm'], r['repeat']): r for r in rows}
    assert sorted({b for b, _, _ in by}) == sorted(names)
    for name in names:
        received = by[(name, 'R', 1)]['text']
        successor = name.split('>')[1]
        assert received == f'prompt of {successor}'
        for key in ((name, 'A', 1), (name, 'B', 1), (name, 'B', 2)):
            assert by[key]['received_sha256'] == hashlib.sha256(received.encode()).hexdigest()
            assert by[key]['text'].startswith(received) and by[key]['lineage'] == 'syn'
        assert (by[(name, 'R', 1)]['tokens'], by[(name, 'R', 1)]['items']) == (0, 0)
    assert [by[(n, 'R', 1)]['kind'] for n in names] == ['handoff', 'admission', 'handoff']


def test_deliver_applies_arm_a_cutoffs_and_arm_bs_d2_schedule(world, monkeypatch):
    runtime, evidence = world
    FakeCurator(monkeypatch)
    replay.run_b(b_args(runtime, evidence), 'key')
    out = runtime/'p1-delivered'/'dev'
    replay.deliver(deliver_args(runtime, evidence, out, schedule_of(runtime)))
    by = {(r['boundary'], r['arm']): r for r in rows_of(out)}
    first, second, third = ('t1-001>t1-002', 't1-002>t2-001', 't2-001>t2-002')
    tail = lambda key: by[key]['text'].split('\n\n', 1)[1]  # noqa: E731
    # A: records before each successor's first operation (30, 100, 120), live, newest first; data folded into prose
    assert tail((first, 'A')).splitlines()[1:] == ['- beta-note. k: 1', '- alpha-note']
    assert tail((second, 'A')).splitlines()[1:] == ['- gamma-note corrects alpha', '- beta-note. k: 1']
    assert tail((third, 'A')).splitlines()[1:] == ['- delta-note', '- gamma-note corrects alpha', '- beta-note. k: 1']
    # B: nothing inside the first admission; later boundaries get admission 1's predecessor's snapshot (v1)
    assert by[(first, 'B')]['text'] == by[(first, 'R')]['text'] and by[(first, 'B')]['items'] == 0
    for name in (second, third):
        assert tail((name, 'B')).splitlines() == [arms.HEADER, '- curated from t1']
        assert by[(name, 'B')]['items'] == 1
    blob = json.dumps(list(by.values()))
    for private in ('curated from t2', 'frame-private-1', 'curator-private', 'src-private-1', 'actor_id', '(claim)', '(observation)'):
        assert private not in blob
    # one renderer: the same header and line format whichever arm produced the item
    assert tail((second, 'A')).splitlines()[0] == tail((second, 'B')).splitlines()[0] == arms.HEADER


def test_deliver_without_a_schedule_makes_only_the_reference_and_arm_a(world, capsys):
    runtime, evidence = world
    out = runtime/'p1-delivered'/'a-only'
    assert replay.main(['deliver', '--lineage', 'syn', '--runtime-root', str(runtime), '--evidence-root', str(evidence),
                        '--out', str(out)]) == 0
    assert json.loads(capsys.readouterr().out) == {'syn': {'R': 3, 'A': 3}}
    assert {r['arm'] for r in rows_of(out)} == {'R', 'A'} and all(r['complete'] for r in rows_of(out))


def test_deliver_refuses_an_incomplete_schedule_a_stray_out_and_an_existing_directory(world, monkeypatch):
    runtime, evidence = world
    FakeCurator(monkeypatch)
    replay.run_b(b_args(runtime, evidence, cap='1'), 'key')              # stopped by the cap after one session
    with pytest.raises(replay.ReplayError, match='no complete schedule'):
        replay.deliver(deliver_args(runtime, evidence, runtime/'p1-delivered'/'x', schedule_of(runtime)))
    with pytest.raises(replay.ReplayError, match='must be inside'):
        replay.deliver(deliver_args(runtime, evidence, runtime/'elsewhere'))
    done = runtime/'p1-delivered'/'done'
    replay.deliver(deliver_args(runtime, evidence, done))
    with pytest.raises(replay.ReplayError, match='exists'):
        replay.deliver(deliver_args(runtime, evidence, done))
    bad = runtime/'bad.json'
    bad.write_text('{"schema": "other/1"}')
    with pytest.raises(replay.ReplayError, match='not a p1-schedule/1'):
        replay.deliver(deliver_args(runtime, evidence, runtime/'p1-delivered'/'y', bad))


@pytest.mark.parametrize('how', ['cap', 'aborted'])
def test_an_incomplete_development_repeat_is_delivered_marked_incomplete(world, monkeypatch, how):
    runtime, evidence = world
    # 'cap': the last session reaches the stage cap, so every session is listed but the stage stopped
    FakeCurator(monkeypatch, states={'t2': 'aborted'} if how == 'aborted' else None)
    replay.run_b(b_args(runtime, evidence, cap='2' if how == 'cap' else '100'), 'key')
    assert json.loads(schedule_of(runtime).read_text())['stopped'] == ('cap-reached' if how == 'cap' else None)
    out = runtime/'p1-delivered'/'partial'
    replay.deliver(deliver_args(runtime, evidence, out, schedule_of(runtime)))
    rows = rows_of(out)
    assert {r['arm']: r['complete'] for r in rows if r['arm'] != 'B'} == {'R': True, 'A': True}
    assert [r['complete'] for r in rows if r['arm'] == 'B'] == [False] * 3


def test_a_held_out_lineage_refuses_an_incomplete_repeat(world, monkeypatch):
    runtime, evidence = world
    FakeCurator(monkeypatch, states={'t2': 'aborted'})
    replay.run_b(b_args(runtime, evidence), 'key')
    monkeypatch.setitem(replay.LINEAGES, 'syn', replay.Lineage('syn', ('t1', 't2'), 'player-memory-syn.sqlite3', held_out=True))
    schedule = replay.load_schedule(schedule_of(runtime))
    with pytest.raises(replay.ReplayError, match='incomplete'):
        replay.lineage_rows('syn', evidence, runtime, [schedule])
    schedule['lineages']['syn']['sessions'][1]['session_state'] = 'sealed'      # sealed and not stopped: delivered
    assert {r['complete'] for r in replay.lineage_rows('syn', evidence, runtime, [schedule])} == {True}


@pytest.mark.parametrize('recorded', ['/tmp/elsewhere', 'knowledge/p1/../../outside', '../outside', 'knowledge', ''])
def test_a_schedule_cannot_point_the_repository_outside_the_p1_knowledge_directory(world, monkeypatch, recorded):
    runtime, evidence = world
    FakeCurator(monkeypatch)
    replay.run_b(b_args(runtime, evidence), 'key')
    schedule = replay.load_schedule(schedule_of(runtime))
    schedule['knowledge'] = recorded
    with pytest.raises(replay.ReplayError, match='not inside'):
        replay.lineage_rows('syn', evidence, runtime, [schedule])
    schedule['knowledge'] = 'knowledge/p1/dev/r1'
    assert replay.knowledge_root(runtime, schedule, 'syn') == runtime/'knowledge'/'p1'/'dev'/'r1'/'syn'


def test_the_cap_applies_to_delivered_working_sets(world):
    runtime, evidence = world
    path = evidence/'syn'/'player-memory-syn.sqlite3'
    path.unlink()
    make_memory(path, [dict(id=f'r{n}', wall=float(n), text=f'note {n} ' + 'v' * 400) for n in range(1, 21)])
    out = runtime/'p1-delivered'/'capped'
    replay.deliver(deliver_args(runtime, evidence, out))
    a = [r for r in rows_of(out) if r['arm'] == 'A']
    assert [r['items'] + r['dropped'] for r in a] == [20, 20, 20]   # every record is live and older than each boundary
    assert all(0 < r['items'] < 20 and r['dropped'] > 0 and 0 < r['tokens'] <= 2000 for r in a)


# ------------------------------------------------------------------ held-out lineages and the freeze
def run_git(repo: Path, *args: str) -> str:
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    done = subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@localhost', '-c', 'commit.gpgsign=false',
                           '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args],
                          capture_output=True, text=True, check=True, env=environment)
    return done.stdout.strip()


@pytest.fixture
def frozen_repo(tmp_path, monkeypatch):
    """A temporary Git repository standing in for the project: arms files, prices, an ignored Node install
    record, and a committed freeze file. Returns (repo, freeze file, prices)."""
    repo = tmp_path.resolve()/'repo'
    names = ('tools/curator_host/p1_arms.py', 'tools/curator_host/p1_replay.py', 'harness/jsonio.py', replay.NODE_LOCK)
    for name in names:
        (repo/name).parent.mkdir(parents=True, exist_ok=True)
        (repo/name).write_text(f'# {name}\n')
    (repo/'data'/'curator').mkdir(parents=True)
    prices = repo/'data'/'curator'/'prices.json'
    prices.write_text(PRICES.read_text())
    (repo/'.gitignore').write_text('node_modules/\n')
    run_git(repo, 'init', '-q', '-b', 'main')
    monkeypatch.setattr(replay, 'ROOT', repo)
    monkeypatch.setattr(replay, 'FROZEN_FILES', names)
    run_git(repo, 'add', '-A')
    run_git(repo, 'commit', '-q', '-m', 'arms')
    out = repo/'data'/'evaluation'/'p1'/'arms-frozen.json'
    replay.freeze(out, prices)
    run_git(repo, 'add', '-A')
    run_git(repo, 'commit', '-q', '-m', 'freeze')
    return repo, out, prices


def test_held_out_lineages_are_refused_without_a_freeze(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shadow, 'credential', lambda *a, **k: pytest.fail('the key must not be read'))
    for name in ('lh1', 'lh2', 'lh3'):
        with pytest.raises(replay.ReplayError, match='--frozen'):
            replay.select([name], None, PRICES)
        for command, extra in (('b', ['--stage', 'x', '--repeat', '1', '--cap-usd', '1']),
                               ('deliver', ['--out', str(tmp_path/'runtime'/'p1-delivered'/'x')])):
            code = replay.main([command, '--lineage', name, *extra, '--runtime-root', str(tmp_path/'runtime'),
                                '--evidence-root', str(tmp_path/'evidence')])
            assert code == 2 and 'frozen' in capsys.readouterr().err
    assert not (tmp_path/'runtime').exists()
    with pytest.raises(replay.ReplayError, match='unknown lineage'):
        replay.select(['lh9'], None, PRICES)


def test_everything_the_arms_run_is_in_the_frozen_file_list():
    for name in ('tools/curator_host/p1_arms.py', 'tools/curator_host/p1_replay.py', 'tools/curator_host/shadow.py',
                 'harness/curator/session.py', 'harness/curator/gate.py', 'harness/trace/projection.py',
                 'harness/trace/sidecar.py', 'harness/trace/stores.py', 'tools/probe_timeline.py', 'harness/jsonio.py',
                 'harness/curator/__init__.py', 'harness/trace/__init__.py', 'tools/curator_host/package-lock.json',
                 'tools/curator_host/node_modules/.package-lock.json'):
        assert name in replay.FROZEN_FILES, name
    # the whole curator and trace packages: the session copies the trace package into the workbench
    tracked = subprocess.run(['git', '-C', str(replay.ROOT), 'ls-files', 'harness/trace', 'harness/curator'],
                             capture_output=True, text=True, check=True).stdout.split()
    assert tracked and set(tracked) <= set(replay.FROZEN_FILES), sorted(set(tracked) - set(replay.FROZEN_FILES))
    assert replay.SETTINGS['arm'] == 'terra' and replay.SETTINGS['max_requests'] == 120
    assert (replay.SETTINGS['max_context_images'], replay.SETTINGS['context_image_block'], replay.SETTINGS['cap_tokens'],
            replay.SETTINGS['session_cap_usd']) == (24, 12, 2000, 12)


def test_freeze_records_the_commit_digests_and_settings_and_is_written_once(frozen_repo, capsys):
    repo, out, prices = frozen_repo
    frozen = json.loads(out.read_text())
    assert frozen['schema'] == 'p1-arms-frozen/1' and frozen['settings'] == replay.SETTINGS
    assert frozen['commit'] == run_git(repo, 'rev-parse', 'HEAD~1')           # HEAD when the freeze was written
    assert sorted(frozen['files']) == sorted([*replay.FROZEN_FILES, 'data/curator/prices.json'])
    assert frozen['files']['tools/curator_host/p1_arms.py'] == hashlib.sha256(
        (repo/'tools/curator_host/p1_arms.py').read_bytes()).hexdigest()
    other = repo/'other.json'
    assert replay.main(['freeze', '--out', str(other), '--prices', str(prices)]) == 0
    assert json.loads(capsys.readouterr().out)['files'] == len(replay.FROZEN_FILES) + 1  # and the prices file
    assert replay.main(['freeze', '--out', str(other), '--prices', str(prices)]) == 2 and 'exists' in capsys.readouterr().err


def test_a_matching_committed_freeze_accepts_held_out_names(frozen_repo):
    repo, out, prices = frozen_repo
    assert replay.select(['lh1', 'lh3'], out, prices) == ['lh1', 'lh3']       # the ignored Node record need not be tracked
    assert replay.select(['397'], None, prices) == ['397']                    # development needs no freeze
    (repo/'later.txt').write_text('a later, unrelated commit')
    run_git(repo, 'add', '-A')
    run_git(repo, 'commit', '-q', '-m', 'later')
    assert replay.select(['lh2'], out, prices) == ['lh2']                     # HEAD descends from the frozen commit


def test_any_change_to_a_frozen_file_or_setting_refuses_held_out_names(frozen_repo, tmp_path):
    repo, out, prices = frozen_repo

    def refused(match, unlist=None, **change):
        data = dict(json.loads(out.read_text()), **change)
        if unlist:
            del data['files'][unlist]
        bad = tmp_path/'bad.json'
        bad.write_text(json.dumps(data))
        with pytest.raises(replay.ReplayError, match=match):
            replay.select(['lh2'], bad, prices)

    refused('settings', settings={**replay.SETTINGS, 'max_requests': 121})
    refused('settings', settings={**replay.SETTINGS, 'session_cap_usd': 13})
    refused('not a p1-arms-frozen/1', schema='p1-arms-frozen/2')
    refused('p1_replay.py: not frozen', unlist='tools/curator_host/p1_replay.py')
    (repo/'tools/curator_host/p1_arms.py').write_text('# edited after the freeze\n')
    with pytest.raises(replay.ReplayError, match='p1_arms.py: changed since the freeze'):
        replay.select(['lh2'], out, prices)
    (repo/replay.NODE_LOCK).write_text('{}')                                  # the installed tree changed too
    with pytest.raises(replay.ReplayError, match='node_modules/.package-lock.json: changed since the freeze'):
        replay.select(['lh2'], out, prices)
    with pytest.raises(replay.ReplayError, match='not frozen'):               # other prices than the frozen ones
        replay.select(['lh2'], out, tmp_path/'other-prices.json')
    with pytest.raises(replay.ReplayError, match='unreadable'):
        replay.select(['lh2'], tmp_path/'missing.json', prices)


def test_a_freeze_of_uncommitted_files_is_refused(frozen_repo, monkeypatch):
    repo, _, prices = frozen_repo
    # modified: the recorded commit would not hold the frozen bytes, so the freeze itself is refused
    (repo/'tools/curator_host/p1_arms.py').write_text('# changed, not committed\n')
    with pytest.raises(replay.ReplayError, match='modified against HEAD: tools/curator_host/p1_arms.py'):
        replay.freeze(repo/'modified.json', prices)
    assert not (repo/'modified.json').exists()
    run_git(repo, 'checkout', '-q', 'HEAD', '--', 'tools/curator_host/p1_arms.py')
    # untracked listed file
    (repo/'extra.py').write_text('# never added\n')
    monkeypatch.setattr(replay, 'FROZEN_FILES', (*replay.FROZEN_FILES, 'extra.py'))
    with pytest.raises(replay.ReplayError, match='extra.py: not tracked by Git'):
        replay.freeze(repo/'untracked.json', prices)
    monkeypatch.setattr(replay, 'FROZEN_FILES', replay.FROZEN_FILES[:-1])
    # staged but uncommitted changes count as modified too
    (repo/'harness/jsonio.py').write_text('# staged only\n')
    run_git(repo, 'add', 'harness/jsonio.py')
    with pytest.raises(replay.ReplayError, match='modified against HEAD'):
        replay.freeze(repo/'staged.json', prices)
    run_git(repo, 'reset', '-q', '--hard', 'HEAD')
    # a clean freeze whose own file was never committed is refused when used
    loose = repo/'loose.json'
    replay.freeze(loose, prices)
    with pytest.raises(replay.ReplayError, match='loose.json: not tracked by Git'):
        replay.select(['lh1'], loose, prices)
    # a listed file changed after a committed freeze fails on its digest
    (repo/'harness/jsonio.py').write_text('# edited after the freeze\n')
    with pytest.raises(replay.ReplayError, match='changed since the freeze'):
        replay.select(['lh1'], repo/'data'/'evaluation'/'p1'/'arms-frozen.json', prices)


def test_a_freeze_whose_commit_is_not_an_ancestor_of_head_or_is_missing_is_refused(frozen_repo, tmp_path):
    repo, out, prices = frozen_repo
    tree = subprocess.run(['git', '-C', str(repo), 'hash-object', '-t', 'tree', '-w', '--stdin'], input='', text=True,
                          capture_output=True, check=True).stdout.strip()
    stranger = run_git(repo, 'commit-tree', tree, '-m', 'unrelated history')
    for commit, match in ((stranger, 'does not equal or descend'), (None, 'records no commit'), ('abc', 'records no commit')):
        data = json.loads(out.read_text())
        if commit is None:
            del data['commit']
        else:
            data['commit'] = commit
        out.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n')
        run_git(repo, 'add', '-A')
        run_git(repo, 'commit', '-q', '-m', f'freeze naming {commit}')
        with pytest.raises(replay.ReplayError, match=match):
            replay.select(['lh1'], out, prices)


def test_a_valid_freeze_lets_a_held_out_run_get_as_far_as_the_missing_evidence(frozen_repo, tmp_path, capsys):
    repo, out, prices = frozen_repo
    runtime = tmp_path/'runtime'
    code = replay.main(['deliver', '--lineage', 'lh1', '--frozen', str(out), '--prices', str(prices),
                        '--runtime-root', str(runtime), '--evidence-root', str(tmp_path/'no-evidence'),
                        '--out', str(runtime/'p1-delivered'/'x')])
    assert code == 2 and 'not a sealed session' in capsys.readouterr().err


def test_the_lineages_match_the_pre_registration():
    assert replay.LINEAGES['397'].sessions == tuple(f'sd1a{n}' for n in range(1, 8))
    assert replay.LINEAGES['397'].store == 'player-memory-sd1.sqlite3'
    assert (replay.LINEAGES['aidB3'].sessions, replay.LINEAGES['ceil09'].sessions) == (('aidB3',), ('ceil09',))
    assert replay.LINEAGES['lh1'].sessions == ('lh1a1', 'lh1a2', 'lh1a3')
    assert replay.LINEAGES['lh2'].sessions == ('lh2a1', 'lh2a2') and replay.LINEAGES['lh3'].sessions == ('lh3a1', 'lh3a2')
    assert {n for n, spec in replay.LINEAGES.items() if spec.held_out} == {'lh1', 'lh2', 'lh3', 'lh4'}
    assert all(spec.store == f'player-memory-{n}.sqlite3' for n, spec in replay.LINEAGES.items() if n.startswith('lh'))
    assert replay.LINEAGES['lh4'].directory == '522-held-out'
    assert replay.LINEAGES['lh4'].sessions == p1_analysis.LH4_ADMISSIONS


def test_lh4_is_held_out_like_lh1_to_lh3_and_a_lineage_without_admissions_is_refused(monkeypatch):
    assert replay.LINEAGES['lh4'].sessions == tuple(f'lh4b{n}' for n in range(1, 8))   # written out in the frozen file
    with pytest.raises(replay.ReplayError, match='--frozen'):
        replay.select(['lh4'], None, PRICES)
    monkeypatch.setitem(replay.LINEAGES, 'syn', replay.Lineage('syn', (), 'player-memory-syn.sqlite3'))
    with pytest.raises(replay.ReplayError, match='no admissions'):
        replay.select(['syn'], None, PRICES)


# ------------------------------------------------------------------ the memory cutoff
def with_programs_and_sources(path: Path):
    db = sqlite3.connect(path)
    for pid, wall, cited in (('p1', 1.5, ['s-from-program']), ('p2', 3.0, ['s-from-late-program'])):
        db.execute('INSERT INTO programs VALUES (?,?,NULL)',
                   (pid, json.dumps(dict(actor_id='x', created_wall=wall, code='c', source_ids=cited))))
    for sid, metadata in (('s-early', dict(received_wall=0.5)), ('s-late', dict(received_wall=5.0)),
                          ('s-at-cut', dict(received_wall=2.0)), ('s-from-record', {}), ('s-from-program', dict(received_wall='soon')),
                          ('s-from-late-program', {}), ('s-orphan', dict(received_wall=None))):
        db.execute('INSERT INTO sources VALUES (?,?,NULL)', (sid, json.dumps(metadata)))
    db.execute("INSERT INTO record_sources VALUES ('r1','s-from-record')")
    db.execute("INSERT INTO record_sources VALUES ('r2','s-late')")
    db.commit()
    db.close()


def test_projection_keeps_memory_written_strictly_before_the_cutoff(tmp_path):
    session = make_session(tmp_path/'evidence')
    make_store(tmp_path/'m.sqlite3')   # records r1 at 1 and r2 at 2
    with_programs_and_sources(tmp_path/'m.sqlite3')
    memory = tmp_path/'m.sqlite3'
    project([session], tmp_path/'all', memory=memory)
    project([session], tmp_path/'none-given', memory=memory, memory_until=None)
    project([session], tmp_path/'cut', memory=memory, memory_until=2.0)
    project([session], tmp_path/'early', memory=memory, memory_until=1.0)
    project([session], tmp_path/'wide', memory=memory, memory_until=2.5)
    read = lambda name: json.loads((tmp_path/name/'memory.json').read_text())  # noqa: E731
    ids = lambda name, key: [row['id'] for row in read(name)[key]]  # noqa: E731
    assert (tmp_path/'all'/'memory.json').read_bytes() == (tmp_path/'none-given'/'memory.json').read_bytes()
    assert ids('all', 'records') == ['r1', 'r2'] and ids('all', 'programs') == ['p1', 'p2'] and len(ids('all', 'sources')) == 7
    # strictly before: a record or program written exactly at the cutoff is not kept
    assert ids('cut', 'records') == ['r1'] and ids('cut', 'programs') == ['p1']
    assert ids('early', 'records') == [] and ids('early', 'programs') == []
    assert ids('wide', 'records') == ['r1', 'r2'] and ids('wide', 'programs') == ['p1']
    # sources: received before the cutoff, or (without a numeric time) cited by a kept record or program
    assert sorted(ids('cut', 'sources')) == ['s-early', 's-from-program', 's-from-record']   # s-at-cut: 2.0 is not < 2.0
    assert sorted(ids('early', 'sources')) == ['s-early']                                       # nothing kept cites the others
    assert sorted(ids('wide', 'sources')) == ['s-at-cut', 's-early', 's-from-program', 's-from-record']
    manifest = json.loads((tmp_path/'early'/'manifest.json').read_text())
    assert manifest['files']['memory.json'] == hashlib.sha256((tmp_path/'early'/'memory.json').read_bytes()).hexdigest()


def test_run_session_threads_the_cutoff_to_the_projection(tmp_path, monkeypatch):
    seen = []

    def projection_stub(sessions, out, **kw):
        seen.append(kw)
        raise RuntimeError('stop before the host')

    monkeypatch.setattr(curator_session, 'project', projection_stub)
    # The session's own cleanup unlocks files with macOS's chflags; this test checks only the threading,
    # so it stays portable (CI runs on Linux).
    monkeypatch.setattr(curator_session, '_remove', lambda path: shutil.rmtree(path, ignore_errors=True))
    repo = Repository(tmp_path/'k', GAME)
    repo.ensure()
    config = curator_session.SessionConfig(argv=('true',))
    curator_session.run_session(repo, [], config, memory=tmp_path/'m.sqlite3', memory_until=7.5)
    curator_session.run_session(repo, [], config, memory=tmp_path/'m.sqlite3')
    assert [kw['memory_until'] for kw in seen] == [7.5, None]
