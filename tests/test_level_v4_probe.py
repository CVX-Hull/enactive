"""The level v4 replay probe: statistics on known inputs, gates on synthetic records, and the three stages against a
recorded-run fixture, the real hosts and a scripted fake provider on loopback.

No real provider, credential, game or live session is involved.
"""
import collections
import hashlib
import io
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import pytest

from harness.computer.store import SessionStore
from tools import level_probe, level_v4_probe as probe_module
from tools.campaign_package import EPISODE_ROLE, FROZEN_ROLE_SHA256, LEVEL_ROLE
from tools.level_v4_probe import (Spend, actor_projection, agreement, bootstrap, evaluate, load_thresholds, probe, sample_episodes,
                                  sample_key, sample_wakes)
from test_level_probe import HOST, KEY, Provider, route_file

ROOT = Path(__file__).resolve().parents[1]
ACTOR = 'a1' * 16
GUIDE = 'Frozen guide for the probe.'
SUBGOAL = dict(id='a' * 32, text='Open the door', expected_observations=[
    dict(predicate='door open', kind='state', window='during', evidence='The door is visibly open')],
    confidence=.8, commit_position=3, origin='replace')
PROFILE = dict(mode='shadow', episode_cap=10, staleness_inputs=10, budget_fractions=[.25, .5, .75], intent_tail_bytes=1024,
               max_http_attempts=60, pass_max_requests=4, pass_seconds=60, theta=0.1251514705882353, theta_fitting_sha256='a' * 64,
               min_episode_inputs=2, stall_settles=3, confidence_floor=0.0, recall=dict(tail_top=2, tail_exploration=1, level_items=10),
               recorder=dict(max_http_attempts=60, pass_max_requests=4, pass_seconds=60, backlog=3))
THRESHOLDS = {
    'schema': 'level-v4-probe-thresholds/1', 'unit': 'recorded run',
    'interval': {'method': 'run-cluster percentile bootstrap', 'level': 0.95, 'resamples': 200, 'seed': 20261102},
    'recorder_valid_terminal_rate_lower_at_least': 0.85, 'recorder_record_share_lower_at_least': 0.50,
    'level_valid_terminal_rate_lower_at_least': 0.85, 'repeated_identical_refusal_at_most': 1,
    'cross_family_kappa_point_at_least': 0.60, 'cross_family_kappa_lower_at_least': 0.40, 'marginal_coverage_lower_above': 0.0,
    'max_usd': 6.0}
pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='Node.js is required for the hosts')


@pytest.fixture(autouse=True)
def clean_checkout(monkeypatch):
    monkeypatch.setattr(probe_module, 'git_state', lambda root=None: ('d' * 40, False))


def stamp(wall: float) -> str:
    return datetime.fromtimestamp(wall, timezone.utc).isoformat().replace('+00:00', 'Z')


def png(number: int) -> bytes:
    out = io.BytesIO()
    Image.new('RGB', (4, 4), (number * 18 % 256, 40, 90)).save(out, format='PNG')
    return out.getvalue()


def build_run(root: Path, name: str, session: str, *, projection: bool = True) -> None:
    """A recorded single-actor run of 13 operations, a recorded actor trace and one recorded level replace."""
    directory = root / name
    directory.mkdir()
    limits = dict(max_inputs=100, max_requests=100, max_frames=100, max_bytes=2 ** 30)
    store = SessionStore(directory, session, limits, 1e9)
    store.add_actor(ACTOR, 'h' * 64)
    for number in range(1, 14):
        identity = f'{number:032x}'
        kind = 'observe' if number == 1 else 'input'
        actions = [] if kind == 'observe' else [dict(type='key', key='x', modifiers=[])]
        store.begin(dict(operation_id=identity, actor_id=ACTOR, kind=kind, created_wall=1000. + number, deadline_monotonic=1e8),
                    actions, len(actions))
        image = png(number)
        metadata = dict(schema='computer-source/1', source_id=f'{session}-{number}', session=session, capture_id=number,
                        sha256=hashlib.sha256(image).hexdigest(), media_type='image/png', presented_ms=1000 + number,
                        received_wall=1000. + number, window_width=4, viewport=[0, 0, 4, 4], width=4, window_height=4, height=4)
        store.put_source(metadata, image, ACTOR)
        store.finish(dict(schema='computer-operation/1', operation_id=identity, session=session, actor_id=ACTOR, kind=kind,
                          status='completed', created_wall=1000. + number, deadline_monotonic=1e8, receipts=[], source=metadata,
                          remaining={}, reason='ok', handoff=None))
    store.close()
    (directory / 'prompt.txt').write_text('Mission: survive and report.')
    (directory / 'context.txt').write_text(GUIDE)
    actors = directory / 'actors' / '001'
    (actors / 'level' / '001').mkdir(parents=True)
    events = []
    for k in range(1, 14):
        wall = 999.5 + k
        if k > 1 and projection:
            sha = hashlib.sha256(png(k - 1)).hexdigest()
            events.append(dict(type='tool-result', request_id=f'request-{k - 1}', tool_call_id=f'call-{k - 1}', tool='computer_observe',
                               result=dict(content=[dict(type='text', text='{}'), dict(type='image_reference', media_type='image/png',
                                                                                      bytes=1, sha256=sha, image_index=0)], isError=False)))
        if projection:
            held = min(k - 1, 4)
            omitted = k - 1 - held
            events.append(dict(type='context-image-projection', wall_time=stamp(wall), request_id=f'request-{k}', max_context_images=4,
                               context_image_block=1, input_images=k - 1, protected_images=min(1, k - 1), retained_images=held,
                               omitted_images=omitted, blocked=False,
                               omissions=[dict(tool_call_id=f'call-{i}', image_index=0, sha256='x') for i in range(1, min(omitted, 16) + 1)]))
        events.append(dict(type='request-start', wall_time=stamp(wall), request_id=f'request-{k}'))
        events.append(dict(type='response-complete', wall_time=stamp(wall + .4), request_id=f'request-{k}'))
    (actors / 'host.jsonl').write_text('\n'.join(json.dumps(e) for e in events) + '\n')
    commit = [dict(type='tool-start', tool='player_level_replace', tool_call_id='c1', arguments=dict(
                  text=SUBGOAL['text'], expected_observations=['door open'], observation_kinds=['state'],
                  observation_windows=['during'], observation_evidence=['The door is visibly open'],
                  confidence=.8, status='open', sources=[], previous_outcome='none', previous_reason='')),
              dict(type='level-commit', receipt_schema='player-level-commit/6', wall_time=stamp(1003.2),
                   tool_call_id='c1', action='replace', position=3, record_ids=['a' * 32])]
    (actors / 'level' / '001' / 'host.jsonl').write_text('\n'.join(json.dumps(e) for e in commit) + '\n')


def build_ladder(root: Path, runs: dict[str, str]) -> Path:
    """#345's episodes and R1 records for the fixture runs (five episodes each, three of them with the subgoal)."""
    ladder = root / 'ladder'
    ladder.mkdir()
    shape = [('start', 'scripted_start', 1, 3, 2, None), ('mid', 'content', 4, 6, 3, SUBGOAL), ('mid', 'cap', 7, 9, 3, SUBGOAL),
             ('mid', 'tail', 10, 12, 3, SUBGOAL), ('end', 'scripted_end', 13, 13, 1, None)]
    episodes, records = [], []
    for name, session in runs.items():
        for index, (kind, closed, first, last, inputs, subgoal) in enumerate(shape):
            episodes.append(dict(run=name, group='C', index=index, kind=kind, closed_by=closed, start_pos=first, end_pos=last,
                                 n_inputs=inputs, subgoal=subgoal))
            records.append(dict(schema='level-replay-record/2', recorder='R1', retest=False, status='record',
                final=True, run=name, episode=index, parsed=dict(
                attempted='Pressed x', counterpart='', observation_status=['seen'] if subgoal else [],
                observation_source_first=[f'{session}-{first}'] if subgoal else [],
                observation_source_second=[''] if subgoal else [],
                changed='', residual='nothing else', confidence=.9, sources=[f'{session}-{first}'])))
    (ladder / 'episodes.json').write_text(json.dumps(dict(schema='level-replay-episodes/2', theta=PROFILE['theta'], m=2, cap=10, n_start=1,
                                                          n_end=1, sessions=runs, episodes=episodes)))
    (ladder / 'records.jsonl').write_text('\n'.join(json.dumps(r) for r in records) + '\n')
    return ladder


def test_current_replay_refuses_archived_episode_ladder_before_reading_records(tmp_path):
    from tools.level_v4_probe import load_ladder

    (tmp_path / 'episodes.json').write_text(json.dumps(dict(schema='ladder345-episodes/1')))
    with pytest.raises(ValueError, match='level-replay-episodes/2'):
        load_ladder(tmp_path)


@pytest.fixture
def world(tmp_path):
    """Two fixture runs, their ladder, the frozen files and routes (cost configured nonzero)."""
    runs = {'fx-01': '1' * 32, 'fx-02': '2' * 32}
    root = tmp_path / 'runs'
    root.mkdir()
    for name, session in runs.items():
        build_run(root, name, session)
    files = tmp_path / 'files'
    files.mkdir()
    (files / 'protocol.md').write_text('# protocol')
    (files / 'amendment-1.md').write_text('# amendment')
    (files / 'thresholds.json').write_text(json.dumps(THRESHOLDS))
    (files / 'profile.json').write_text(json.dumps(PROFILE))
    return dict(root=root, runs=runs, ladder=build_ladder(tmp_path, runs), files=files, tmp=tmp_path)


def routes(world, port, cost=1.0, **limits):
    first = Path(route_file(world['files'], port, cost=cost, **limits))
    document = json.loads(first.read_text())
    first.rename(world['files'] / 'f1.json')
    second = dict(document, model=dict(document['model'], id='fixture-model-2', name='Fixture 2'))
    (world['files'] / 'f2.json').write_text(json.dumps(second))
    return {'F1': world['files'] / 'f1.json', 'F2': world['files'] / 'f2.json'}


@pytest.mark.parametrize('context,inputs', [(False, 9), (True, 9), (True, 10)])
def test_planner_polls_fractions_without_settles_and_replays_real_skip_eligibility(world, monkeypatch, context, inputs):
    name, session = next(iter(world['runs'].items()))
    run = probe_module.load_run(world['root'], name, session)
    run['rows'] = run['rows'][:inputs + 1]
    run['request_walls'] = [1020. + i for i in range(1, 14)]
    commit = dict(wall=1000., action='replace', id='a' * 32, position=0,
                  arguments=dict(text='Inspect the door', expected_observations=['door inspected'],
                                 observation_kinds=['state'], observation_windows=['during'],
                                 observation_evidence=['The door inspection is visible'], confidence=.8,
                                 status='open', sources=[], previous_outcome='revised', previous_reason='Refocus'))
    monkeypatch.setattr(probe_module, 'level_commits', lambda _: [commit] if context else [])
    planning = probe_module.Lineage(world['tmp'] / f'planning-{context}-{inputs}')
    try:
        plan = probe_module.plan_run(run, [], {}, pool=[.1], level=PROFILE, actor_allowance=13, lineage=planning,
                                    seed=329, recorder_requests=2, level_requests=2)
    finally:
        planning.close()
    expected = ['start', 'budget-0.25', 'budget-0.5', 'budget-0.75'] if context and inputs == 9 else ['start'] if context else []
    assert [w['reason'] for w in plan['wakes']] == expected
    assert len(plan['wake_skips']) == (0 if context and inputs == 9 else 3)
    if plan['wake_skips']:
        assert {s['skip'] for s in plan['wake_skips']} == {
            'settled evidence bound already stale' if context else 'no meaningful context'}
        assert {s['inputs_since'] for s in plan['wake_skips']} == {inputs}
    static = probe_module.Lineage(world['tmp'] / f'static-{context}-{inputs}')
    try:
        replayed = probe_module.replay(run, plan, [], {}, static, PROFILE)
        replayed['runtime'].close()
    finally:
        static.close()


def test_planning_coalesces_equal_time_settle_operation_and_fraction_before_binding(world, monkeypatch):
    name, session = next(iter(world['runs'].items()))
    run = probe_module.load_run(world['root'], name, session)
    run['request_walls'] = [1001.1, 1003., 1005., 1007.]
    monkeypatch.setattr(probe_module, 'level_commits', lambda _: [])
    episode = dict(run=name, index=0, kind='mid', closed_by='cap', start_pos=1, end_pos=1, n_inputs=0, subgoal=None)
    profile = dict(PROFILE, budget_fractions=[.5])
    planning = probe_module.Lineage(world['tmp'] / 'tie-planning')
    try:
        plan = probe_module.plan_run(run, [episode], {}, pool=[2.], level=profile, actor_allowance=4,
                                    lineage=planning, seed=329, recorder_requests=1, level_requests=1)
    finally:
        planning.close()
    assert plan['wake_skips'] == []
    assert [(w['time'], w['reason']) for w in plan['wakes']] == [(1003., 'budget-0.5')]
    static = probe_module.Lineage(world['tmp'] / 'tie-static')
    try:
        state = probe_module.replay(run, plan, [episode], {}, static, profile)
        state['runtime'].close()
    finally:
        static.close()


def run_probe(world, paths, name='probe', *, secret=KEY, dry_run=False, **kwargs):
    arguments = dict(ladder_dir=world['ladder'], runs_root=world['root'], protocol=world['files'] / 'protocol.md',
                     amendment=world['files'] / 'amendment-1.md',
                     thresholds_path=world['files'] / 'thresholds.json', route_paths=paths, profile_path=world['files'] / 'profile.json',
                     name=name, max_usd=5., read_secret=None if dry_run else (lambda: secret), host_argv=HOST, no_subgoal=1, wake_count=3, effort='off',
                     workers=2, dry_run=dry_run, probe_root=world['tmp'] / 'probes', node=shutil.which('node'))
    arguments.update(kwargs)
    return probe(**arguments)


def scripted(number, payload):
    """A recorder asked to record the pushed episode, a level asked to abstain."""
    text = json.dumps(payload['messages'])
    if 'Citable source ids' in text:
        sources = re.search(r'Citable source ids: ([^\\"]+?)(?:\\n|\\")', text).group(1).split(', ')
        expected = 0 if 'Subgoal current when the episode began: none' in text else 1
        return [('player_episode_record', dict(attempted='Pressed x', counterpart='', observation_status=['seen'] * expected,
                                               observation_source_first=sources[-1:] * expected,
                                               observation_source_second=[''] * expected,
                                               changed='', residual='', confidence=.8, sources=sources[:1]))]
    return [('player_level_abstain', dict(reason_code='no_change_needed', reason='Nothing to change', sources=[]))]


# --- sampling -----------------------------------------------------------------------------------------------------

def test_the_sampling_key_is_the_protocols_hash_and_the_sample_is_deterministic():
    assert sample_key('fx-01', 3) == int(hashlib.sha256(b'fx-01|3').hexdigest(), 16)
    episodes = [dict(run=f'r{r}', index=i, subgoal=SUBGOAL if i % 4 == 0 else None) for r in range(6) for i in range(10)]
    first = sample_episodes(episodes, 7)
    assert first == sample_episodes(list(reversed(episodes)), 7)
    assert sum(bool(e['subgoal']) for e in first) == sum(bool(e['subgoal']) for e in episodes) and len(first) == len(
        [e for e in episodes if e['subgoal']]) + 7
    keyless = sorted((e for e in episodes if not e['subgoal']), key=lambda e: sample_key(e['run'], e['index']))[:7]
    assert {(e['run'], e['index']) for e in first if not e['subgoal']} == {(e['run'], e['index']) for e in keyless}
    assert [sample_key(e['run'], e['index']) for e in first] == sorted(sample_key(e['run'], e['index']) for e in first)
    wakes = [dict(run='r', index=i) for i in range(1, 30)]
    assert sample_wakes(wakes, 5) == sample_wakes(wakes[::-1], 5) and len(sample_wakes(wakes, 5)) == 5


# --- statistics -----------------------------------------------------------------------------------------------------

def test_kappa_and_ac1_on_known_tables():
    perfect = [('seen', 'seen'), ('not_yet', 'not_yet'), ('contradicted', 'contradicted'), ('seen', 'seen')]
    assert agreement(perfect)['kappa'] == pytest.approx(1.) and agreement(perfect)['ac1'] == pytest.approx(1.)
    # 50 pairs: 20 seen/seen, 5 seen/not_yet, 10 not_yet/seen, 15 not_yet/not_yet: po = .7, pe = .5, kappa = .4
    pairs = [('seen', 'seen')] * 20 + [('seen', 'not_yet')] * 5 + [('not_yet', 'seen')] * 10 + [('not_yet', 'not_yet')] * 15
    value = agreement(pairs)
    assert value['n'] == 50 and value['agreement'] == pytest.approx(.7)
    # Gwet: pi = (.55, .45, 0), chance = (.55 * .45 * 2) / 2 = .2475, AC1 = (.7 - .2475) / (1 - .2475)
    assert value['kappa'] == pytest.approx(.4) and value['ac1'] == pytest.approx((.7 - .165) / (1 - .165))
    # Chance agreement of 1 leaves kappa undefined, never zero or one by default.
    assert agreement([('seen', 'seen')] * 4)['kappa'] is None and agreement([])['kappa'] is None


def test_the_cluster_bootstrap_resamples_runs_deterministically_and_reads_percentiles():
    runs = {'a': (1, 1), 'b': (0, 1)}
    value = bootstrap(runs, lambda parts: sum(n for n, _ in parts) / sum(d for _, d in parts), seed=20261102, resamples=2000, level=.95)
    assert value['point'] == .5 and value['runs'] == 2 and value['lower'] == 0. and value['upper'] == 1.
    assert value == bootstrap(runs, lambda parts: sum(n for n, _ in parts) / sum(d for _, d in parts), seed=20261102, resamples=2000, level=.95)
    # Identical runs give a degenerate interval; fewer than two runs gives none.
    same = bootstrap({r: (3, 4) for r in 'abcd'}, lambda parts: sum(n for n, _ in parts) / sum(d for _, d in parts), seed=1, resamples=100, level=.95)
    assert (same['lower'], same['upper']) == (.75, .75)
    assert bootstrap({'a': (1, 1)}, lambda parts: 1., seed=1, resamples=10, level=.95)['lower'] is None
    # An undefined statistic in most resamples leaves the interval undefined.
    flaky = bootstrap({'a': 1, 'b': 2, 'c': 3}, lambda parts: None, seed=1, resamples=50, level=.95)
    assert flaky['lower'] is None and flaky['defined_resamples'] == 0


def records(family, run, count, *, valid=1., record=1., repeat=0, status=('seen', 'not_yet', 'contradicted', 'seen'), start=0):
    items = []
    for i in range(count):
        good = i < valid * count
        terminal = ('record' if i < record * count else 'abstain') if good else None
        items.append(dict(run=run, episode=start + i, family=family, valid=good, terminal=terminal, max_repeat=repeat,
                          observation_status=list(status) if terminal == 'record' else None))
    return items


def gates_of(f1, f2=(), level=(), tails=()):
    return evaluate(THRESHOLDS, list(f1), list(f2), list(level), list(tails))


def level_items(run, count, *, valid=1., repeat=0):
    return [dict(run=run, wake=i, valid=i < valid * count, max_repeat=repeat) for i in range(count)]


def tail(run, shown, marginal):
    return [dict(run=run, shown=shown, marginal=marginal)]


RUNS = ['r1', 'r2', 'r3', 'r4']


def healthy():
    f1 = [i for r in RUNS for i in records('F1', r, 10, status=('seen', 'not_yet', 'contradicted', 'seen'))]
    f2 = [dict(i, family='F2') for i in f1]
    level = [i for r in RUNS for i in level_items(r, 5)]
    tails = [i for r in RUNS for i in tail(r, 3, 1)]
    return f1, f2, level, tails


def test_every_gate_passes_on_healthy_synthetic_records_and_the_run_passes():
    f1, f2, level, tails = healthy()
    result = gates_of(f1, f2, level, tails)
    assert set(result['gates']) == {'G1', 'G2', 'G3', 'G4', 'G5', 'G6'}
    assert all(g['passed'] for g in result['gates'].values()) and result['all_passed']
    assert result['gates']['G1']['point'] == 1. and result['gates']['G4']['point'] == 0
    assert result['gates']['G5']['point'] == pytest.approx(1.) and result['gates']['G6']['point'] == pytest.approx(1 / 3)
    assert result['f2']['f2_g4_max_repeated_identical_refusal'] == 0 and result['f2']['f2_g1']['point'] == 1.


@pytest.mark.parametrize('gate,change', [
    ('G1', dict(f1=lambda f1, f2, level, tails: ([i for r in RUNS for i in records('F1', r, 10, valid=.6)], f2, level, tails))),
    ('G2', dict(f1=lambda f1, f2, level, tails: ([i for r in RUNS for i in records('F1', r, 10, record=.2)], f2, level, tails))),
    ('G3', dict(f1=lambda f1, f2, level, tails: (f1, f2, [i for r in RUNS for i in level_items(r, 5, valid=.4)], tails))),
    ('G4', dict(f1=lambda f1, f2, level, tails: (f1, f2, [i for r in RUNS for i in level_items(r, 5, repeat=2)], tails))),
    ('G5', dict(f1=lambda f1, f2, level, tails: (f1, [dict(i, observation_status=['not_yet', 'seen', 'seen', 'not_yet']) if i['observation_status']
                                                   else i for i in f2], level, tails))),
    ('G6', dict(f1=lambda f1, f2, level, tails: (f1, f2, level, [i for r in RUNS for i in tail(r, 3, 0)])))])
def test_each_gate_fails_on_its_failing_synthetic_records_and_only_that_gate(gate, change):
    f1, f2, level, tails = change['f1'](*healthy())
    result = gates_of(f1, f2, level, tails)
    failed = {name for name, g in result['gates'].items() if not g['passed']}
    assert gate in failed and not result['all_passed']
    # Only the changed statistic fails, apart from G2 which needs valid passes and G1 failing alone.
    assert failed == {gate}


def test_g4_counts_the_largest_repeat_in_either_role_and_a_single_refusal_is_allowed():
    f1, f2, level, tails = healthy()
    f1[3] = dict(f1[3], max_repeat=1)
    assert gates_of(f1, f2, level, tails)['gates']['G4']['passed'] is True
    f1[3] = dict(f1[3], max_repeat=2)
    assert gates_of(f1, f2, level, tails)['gates']['G4']['point'] == 2
    # F2's repeats are reported, never gating.
    f1, f2, level, tails = healthy()
    f2[0] = dict(f2[0], max_repeat=5)
    result = gates_of(f1, f2, level, tails)
    assert result['gates']['G4']['passed'] and result['f2']['f2_g4_max_repeated_identical_refusal'] == 5


def test_g5_uses_the_point_and_the_lower_bound_and_an_undefined_kappa_fails():
    f1, f2, level, tails = healthy()
    # All one status: chance agreement is 1, kappa is undefined, the gate cannot pass.
    flat = [dict(i, observation_status=['seen'] * 4 if i['observation_status'] else None) for i in f1]
    undefined = gates_of(flat, [dict(i, family='F2') for i in flat], level, tails)
    assert undefined['gates']['G5']['point'] is None and undefined['gates']['G5']['passed'] is False
    # No tail items at all: marginal coverage is undefined and G6 fails.
    assert gates_of(f1, f2, level, [])['gates']['G6']['passed'] is False


# --- spend ------------------------------------------------------------------------------------------------------------

def test_the_cap_is_a_hard_up_front_reservation_across_workers():
    spend = Spend(1.)
    assert spend.reserve(4, .125) == (4, .5)
    assert spend.reserve(4, .125) == (4, .5)
    # Nothing is left unreserved: a third pass is skipped, not started.
    assert spend.reserve(4, .125) == (0, 0.) and spend.skipped == 1
    spend.release(.5, .2, .25)
    # The dearest request seen now sets the step: the $0.3 not spent or held covers one request at $0.25, but a pass is all or
    # nothing, so a four-request pass is skipped rather than launched with the one request that fits.
    assert spend.reserve(4, .125) == (0, 0.) and spend.skipped == 2
    assert spend.reserve(1, .125) == (1, .25)
    nothing = Spend(.01)
    assert nothing.reserve(4, .02) == (0, 0.)


def test_a_pass_is_reserved_in_full_or_skipped_and_never_truncated():
    spend = Spend(1.)
    # Three of four requests would fit ($0.75 of $1.00 at $0.25): the pass is skipped whole, nothing is held.
    assert spend.reserve(5, .25) == (0, 0.) and spend.skipped == 1 and spend.reserved == 0.
    assert spend.reserve(4, .25) == (4, 1.) and spend.reserved == 1.
    assert spend.reserve(1, .25) == (0, 0.) and spend.skipped == 2
    # A faulted pass's charge is unknown: its whole hold stays against the cap and is reported as an upper bound.
    spend.forfeit(1.)
    assert spend.reserved == 0. and spend.unaccounted == 1. and spend.spent == 0.
    assert spend.reserve(1, .25) == (0, 0.)


def test_a_cap_over_the_thresholds_or_not_positive_is_refused_before_anything_is_written(world):
    paths = routes(world, 9)
    for cap in (0, -1, 6.01):
        with pytest.raises(ValueError, match='max-usd'):
            run_probe(world, paths, max_usd=cap)
    assert not (world['tmp'] / 'probes').exists()
    with pytest.raises(SystemExit):
        probe_module.main(['--ladder', str(world['ladder']), '--runs-root', str(world['root']), '--protocol', 'p', '--thresholds', 't',
                           '--route-f1', 'a', '--route-f2', 'b', '--profile', 'c', '--name', 'x'])


def test_thresholds_are_a_closed_file(world):
    path = world['files'] / 'thresholds.json'
    for bad in (dict(THRESHOLDS, extra=1), dict(THRESHOLDS, schema='level-v4-probe-thresholds/0'),
                {k: v for k, v in THRESHOLDS.items() if k != 'max_usd'}, dict(THRESHOLDS, unit='episode'),
                dict(THRESHOLDS, interval=dict(THRESHOLDS['interval'], method='bca'))):
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match='hreshold|must be|interval|unit'):
            load_thresholds(path)


# --- the recorded actor trace -----------------------------------------------------------------------------------------

def test_the_projection_derives_held_images_and_a_run_without_projection_events_is_excluded(world):
    run = dict(directory=world['root'] / 'fx-01')
    value = actor_projection(run)
    assert value['exclusion'] is None and value['mismatched'] == 0 and len(value['requests']) == 13
    last = value['requests'][-1]
    # Request 13 held the newest four of twelve images; the others were omitted by the host's oldest-first policy.
    assert last['held'] == {hashlib.sha256(png(n)).hexdigest() for n in (9, 10, 11, 12)}
    build_run(world['root'], 'fx-bare', '3' * 32, projection=False)
    bare = actor_projection(dict(directory=world['root'] / 'fx-bare'))
    assert bare['exclusion'] and 'context-image-projection' in bare['exclusion'] and bare['requests'] == []


def test_a_run_with_no_projection_events_is_excluded_and_reported_by_the_dry_run(world):
    build_run(world['root'], 'fx-03', '3' * 32, projection=False)
    second = world['tmp'] / 'second'
    second.mkdir()
    world = dict(world, ladder=build_ladder(second, dict(world['runs'], **{'fx-03': '3' * 32})))
    report = run_probe(world, routes(world, 9), dry_run=True)
    stage3 = report['stage3']
    assert stage3['exclusions'] == {'fx-03': 'the actor trace has no context-image-projection events'}
    assert stage3['runs_included'] == ['fx-01', 'fx-02'] and stage3['requests'] == 26


# --- the stages ---------------------------------------------------------------------------------------------------------

def test_the_dry_run_resolves_every_input_and_counts_without_a_host_or_a_credential(world):
    report = run_probe(world, routes(world, 9), dry_run=True)
    counts = report['counts']
    assert report['label'] == 'engineering-probe' and report['excluded_from_evidence'] is True and report['status'] == 'dry-run'
    assert counts['runs_replayable'] == 2 and counts['episodes_in_runs'] == 10
    # Six episodes carry the subgoal; one subgoal-free episode of each... the rule draws one of the four by hash.
    assert counts['stage1_with_subgoal'] == 6 and counts['stage1_without_subgoal'] == 1 and counts['stage1_episodes'] == 7
    assert counts['stage1_passes_planned'] == 14 and counts['wake_points'] >= 2 and counts['stage2_sampled'] == 3
    assert counts['actor_requests'] == 26 and counts['actor_requests_with_tail'] > 0 and counts['cut_rule_reproduced_runs'] in (0, 1, 2)
    stage3 = report['stage3']
    assert stage3['conversion_failures'] == [] and stage3['formatter_failures'] == 0
    # The reconstruction report: nothing inconsistent in the fixture, every shown source has a stored sha, no request omits over 16.
    reconstruction = stage3['reconstruction']
    assert reconstruction['requests'] == 26 and reconstruction['requests_inconsistent'] == 0
    assert reconstruction['shown_items_in_inconsistent_requests'] == 0 and reconstruction['requests_over_16_omissions'] == 0
    assert reconstruction['shown_items_unknown_sha'] == 0 and reconstruction['requests_with_unknown_sha'] == 0
    breakdown = report['exploratory_not_gating']['marginal_coverage_by_item_kind']
    assert set(breakdown) == {'note', 'ranked', 'exploration'} and 'gates nothing' in breakdown['note']
    assert breakdown['ranked']['shown'] + breakdown['exploration']['shown'] == stage3['shown_items']
    assert breakdown['ranked']['marginal'] + breakdown['exploration']['marginal'] == stage3['marginal_items']
    assert 'exploratory_not_gating' not in report.get('gates', {})
    assert stage3['shown_items'] > 0 and 0 < stage3['marginal_items'] <= stage3['shown_items']
    assert report['spend'] == dict(charged_usd=0., max_usd=5.)
    assert all(i['bytes'] < 1048576 and i['frames'] >= 1 for i in report['stage1_inputs'])
    assert report['inputs']['protocol'] == hashlib.sha256((world['files'] / 'protocol.md').read_bytes()).hexdigest()
    assert report['inputs']['amendment'] == hashlib.sha256((world['files'] / 'amendment-1.md').read_bytes()).hexdigest()
    assert report['inputs']['thresholds'] == report['thresholds']['file_sha256']
    # Each run's recorded level-pass traces and every source capture read are digested.
    for name in world['runs']:
        recorded = report['inputs']['runs'][name]
        trace = world['root'] / name / 'actors/001/level/001/host.jsonl'
        assert recorded['level_traces'] == {'actors/001/level/001/host.jsonl': hashlib.sha256(trace.read_bytes()).hexdigest()}
        listing = '\n'.join(f'{world["runs"][name]}-{n} {hashlib.sha256(png(n)).hexdigest()}'
                            for n in sorted(range(1, 14), key=lambda n: f'{world["runs"][name]}-{n}'))
        assert recorded['source_pngs'] == dict(count=13, digest=hashlib.sha256(listing.encode()).hexdigest())
    assert report['interface']['role_prompts'] == {r.name: hashlib.sha256(r.read_bytes()).hexdigest() for r in (LEVEL_ROLE, EPISODE_ROLE)}
    assert all(report['interface']['role_prompts'][n] == FROZEN_ROLE_SHA256[n] for n in FROZEN_ROLE_SHA256)
    # A report is written once and a name is never reused.
    with pytest.raises(FileExistsError):
        run_probe(world, routes(world, 9), dry_run=True)


def test_a_dirty_checkout_is_refused_for_a_paid_run_but_not_a_dry_run(world, monkeypatch):
    monkeypatch.setattr(probe_module, 'git_state', lambda root=None: ('e' * 40, True))
    with pytest.raises(ValueError, match='clean commit'):
        run_probe(world, routes(world, 9))
    assert not (world['tmp'] / 'probes').exists()
    assert run_probe(world, routes(world, 9), dry_run=True)['source'] == dict(commit='e' * 40, clean=False)


def test_a_route_that_is_not_player_host_6_or_has_too_few_images_is_refused(world):
    paths = routes(world, 9)
    document = json.loads(paths['F2'].read_text())
    paths['F2'].write_text(json.dumps(dict(document, schema='player-host/5')))
    with pytest.raises(ValueError, match='must be player-host/8'):
        run_probe(world, paths)
    paths['F2'].write_text(json.dumps(dict(document, max_context_images=7)))
    with pytest.raises(ValueError, match='max_context_images'):
        run_probe(world, paths)
    assert not (world['tmp'] / 'probes').exists()


def provider_world(world, provider, **kwargs):
    return run_probe(world, routes(world, provider.port), **kwargs)


def test_the_three_stages_run_the_real_hosts_and_the_credential_never_reaches_an_output(world, provider_factory):
    fake = provider_factory(scripted)
    report = provider_world(world, fake)
    assert report['status'] == 'complete' and report['schema'] == 'level-v4-probe/4' and report['label'] == 'engineering-probe'
    recorder = report['recorder']
    assert recorder['F1']['passes'] == 7 and recorder['F1']['valid'] == 7 and recorder['F2']['valid'] == 7
    assert recorder['F1']['terminals'] == {'record': 7} and report['level']['passes'] == 3 and report['level']['valid'] == 3
    assert report['level']['terminals'] == {'abstain:no_change_needed': 3}
    assert set(report['gates']) == {'G1', 'G2', 'G3', 'G4', 'G5', 'G6'} and report['spend']['charged_usd'] > 0
    stored = [p['store'] for p in report['passes']['recorder'] if p['ran'] and p['with_subgoal']]
    assert stored and all(s['settled'] == 'recorded' for s in stored)
    assert all(p['observation_status'] == ['seen'] for p in report['passes']['recorder'] if p['with_subgoal'])
    # F1 and F2 reach the provider under their own model ids; the recorder lane has no guide and the level lane has it.
    payloads = [json.dumps(p) for p in fake.payloads]
    assert any('fixture-model-2' in p for p in payloads) and any('"fixture-model"' in p for p in payloads)
    recorder_payloads = [p for p in payloads if 'Citable source ids' in p]
    level_payloads = [p for p in payloads if 'Citable source ids' not in p]
    assert recorder_payloads and not any(GUIDE in p for p in recorder_payloads)
    assert level_payloads and all(GUIDE in p for p in level_payloads)
    assert all('Episodes settled since your last pass' in p for p in level_payloads)
    out = world['tmp'] / 'probes' / 'probe'
    assert (out / 'report.json').is_file() and not (out / 'work').exists()
    for path in out.rglob('*'):
        if path.is_file():
            assert KEY not in path.read_text(errors='ignore'), path
    assert KEY not in json.dumps(report, default=str)
    assert len(list((out / 'samples').glob('*.host.jsonl'))) == 17


def test_the_cap_stops_passes_up_front_and_the_report_is_incomplete_not_passed(world, provider_factory):
    fake = provider_factory(scripted)
    # Each request costs $1.10 at 50000 USD per million tokens and the bound is $1.20: $5.50 holds one four-request pass
    # ($4.80) and, once it has charged one request, not another, so every other pass is skipped rather than truncated.
    paths = routes(world, fake.port, cost=50000., context_window=13, max_tokens=11)
    report = run_probe(world, paths, max_usd=5.5, max_request_usd=1.2, workers=1)
    assert report['status'] == 'incomplete' and report['passed'] is False
    assert report['spend']['skipped_passes'] > 0 and report['spend']['charged_usd'] <= 5.5
    assert report['spend']['stopped_by_spend_guard'] is True
    ran = [p for p in [*report['passes']['recorder'], *report['passes']['level']] if p['ran']]
    assert len(ran) == 1 and ran[0]['allowance'] == PROFILE['pass_max_requests'] == 4
    skipped = [p for p in [*report['passes']['recorder'], *report['passes']['level']] if not p['ran']]
    assert skipped and all('full allowance' in p['skipped'] for p in skipped)
    nothing = run_probe(world, routes(world, fake.port, cost=50000.), name='tiny', max_usd=.01, max_request_usd=.02)
    assert nothing['spend']['passes_run'] == 0 and nothing['status'] == 'incomplete'


def test_main_never_reads_the_keychain_in_a_dry_run(world, monkeypatch, capsys):
    def refuse():
        raise AssertionError('the Keychain must not be read')
    monkeypatch.setattr(probe_module, 'keychain_secret', refuse)
    paths = routes(world, 9)
    # The command line writes under the project's probes directory (ignored by git); the test removes its own output.
    shutil.rmtree(probe_module.PROBE_ROOT / 'cli', ignore_errors=True)
    assert probe_module.main(['--ladder', str(world['ladder']), '--runs-root', str(world['root']), '--protocol', str(world['files'] / 'protocol.md'),
                              '--amendment', str(world['files'] / 'amendment-1.md'),
                              '--thresholds', str(world['files'] / 'thresholds.json'), '--route-f1', str(paths['F1']),
                              '--route-f2', str(paths['F2']), '--profile', str(world['files'] / 'profile.json'), '--name', 'cli',
                              '--max-usd', '5', '--dry-run', '--no-subgoal', '1', '--wakes', '2']) == 0
    assert '"status": "dry-run"' in capsys.readouterr().out
    shutil.rmtree(probe_module.PROBE_ROOT / 'cli', ignore_errors=True)


class Secret:
    """A credential reader that records how often it was called."""
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return KEY


def test_the_credential_is_read_once_and_only_after_every_validation_has_passed(world, tmp_path):
    spy = Secret()
    paths = routes(world, 9)
    cases = [
        dict(max_usd=6.5),                                   # a cap over the thresholds
        dict(max_request_usd=-1.),                           # no usable per-request bound
        dict(runs=['nope']),                                 # a run the ladder does not hold
    ]
    for kwargs in cases:
        with pytest.raises(ValueError):
            run_probe(world, paths, read_secret=spy, **kwargs)
    # A route over the image limit, a dirty checkout, a missing Node.js.
    document = json.loads(paths['F2'].read_text())
    paths['F2'].write_text(json.dumps(dict(document, max_context_images=7)))
    with pytest.raises(ValueError, match='max_context_images'):
        run_probe(world, paths, read_secret=spy)
    paths['F2'].write_text(json.dumps(document))
    with pytest.raises(ValueError, match='Node.js'):
        run_probe(world, paths, read_secret=spy, node=None)
    # A capture that differs from the sha256 the recording stored.
    capture = world['root'] / 'fx-02' / 'sources' / f'{world["runs"]["fx-02"]}-5.png'
    original = capture.read_bytes()
    capture.write_bytes(png(99))
    with pytest.raises(ValueError, match='differs from its recorded sha256'):
        run_probe(world, paths, read_secret=spy)
    capture.write_bytes(original)
    assert spy.calls == 0 and not (world['tmp'] / 'probes').exists()
    # A dry run never reads it either; a paid run that passes everything reads it exactly once, before any host.
    run_probe(world, paths, dry_run=True)
    assert spy.calls == 0


def test_a_capture_missing_from_the_recording_refuses_before_anything_is_written(world):
    paths = routes(world, 9)
    capture = world['root'] / 'fx-01' / 'sources' / f'{world["runs"]["fx-01"]}-3.png'
    capture.unlink()
    with pytest.raises(FileNotFoundError):
        run_probe(world, paths, dry_run=True)
    assert not (world['tmp'] / 'probes').exists()


@pytest.mark.parametrize('archived_close', [False, True])
def test_a_superseded_level_commit_refuses_before_credentials_or_output(world, archived_close):
    trace, *_ = probe_module.level_trace_paths(world['root'] / 'fx-01')
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    if archived_close:
        commit = next(event for event in events if event['type'] == 'level-commit')
        commit.update(action='close', receipt_schema='player-level-commit/5')
    else:
        replace_call = next(event for event in events if event.get('tool') == 'player_level_replace')
        del replace_call['arguments']['observation_windows']
    trace.write_text(''.join(json.dumps(event) + '\n' for event in events))
    spy = Secret()
    with pytest.raises(ValueError, match='player-level-commit/6' if archived_close else 'observation_windows'):
        run_probe(world, routes(world, 9), read_secret=spy)
    assert spy.calls == 0
    assert not (world['tmp'] / 'probes').exists()


def test_a_ladder_subgoal_with_too_many_predicates_refuses_before_credentials_or_output(world):
    path = world['ladder'] / 'episodes.json'
    document = json.loads(path.read_text())
    subgoal = next(episode['subgoal'] for episode in document['episodes'] if episode['subgoal'])
    subgoal['expected_observations'] *= 9
    path.write_text(json.dumps(document))
    spy = Secret()
    with pytest.raises(ValueError, match='expected_observations'):
        run_probe(world, routes(world, 9), read_secret=spy)
    assert spy.calls == 0
    assert not (world['tmp'] / 'probes').exists()


def test_a_paid_run_reads_the_credential_once(world, provider_factory):
    spy = Secret()
    report = provider_world(world, provider_factory(scripted), read_secret=spy)
    assert spy.calls == 1 and report['status'] == 'complete'


def test_a_faulting_pass_cancels_the_queue_keeps_its_trace_and_still_writes_an_incomplete_report(world, provider_factory, monkeypatch):
    fake = provider_factory(scripted)
    real = probe_module.classify
    seen = []

    def fault_after_the_host_ran(directory, events, returncode, role='level'):
        seen.append(role)
        real(directory, events, returncode, role=role)
        raise RuntimeError('injected fault')
    monkeypatch.setattr(probe_module, 'classify', fault_after_the_host_ran)
    report = run_probe(world, routes(world, fake.port), workers=1)
    out = world['tmp'] / 'probes' / 'probe'
    assert report['status'] == 'incomplete' and report['passed'] is False
    # One pass launched and faulted; every queued pass, level and recorder, was cancelled and never reached the provider.
    assert seen == ['level'] and len(fake.payloads) == 1
    passes = [*report['passes']['level'], *report['passes']['recorder']]
    assert len(passes) == 3 + 14 and not any(p['ran'] for p in passes)
    faulted = [p for p in passes if p.get('fault')]
    assert len(faulted) == 1 and 'RuntimeError: injected fault' in faulted[0]['fault']
    assert sum('cancelled' in p for p in passes) == 16
    assert report['faults'][0]['fault'] == faulted[0]['fault'] and report['spend']['faulted_passes'] == 1
    assert report['spend']['unaccounted_usd_upper_bound'] > 0 and report['spend']['passes_run'] == 0
    # The report on disk is the same document, and the faulted pass's host trace was copied into samples.
    assert json.loads((out / 'report.json').read_text())['status'] == 'incomplete'
    traces = sorted((out / 'samples').glob('*.host.jsonl'))
    assert [t.name for t in traces] == [f'level-F1-{faulted[0]["run"]}-{faulted[0]["wake"]:03d}.host.jsonl']
    assert traces[0].stat().st_size > 0 and not (out / 'work').exists()


def test_an_exception_in_a_later_phase_leaves_the_finished_passes_in_the_report(world, provider_factory, monkeypatch):
    fake = provider_factory(scripted)
    real = probe_module.run_recorder
    calls = []

    def second_recorder_pass_raises(run, ep, family, route, ctx):
        calls.append((run['name'], ep['index'], family))
        if len(calls) == 2:
            raise OSError('injected recorder fault')
        return real(run, ep, family, route, ctx)
    monkeypatch.setattr(probe_module, 'run_recorder', second_recorder_pass_raises)
    report = run_probe(world, routes(world, fake.port), workers=1)
    assert report['status'] == 'incomplete' and len(calls) == 2
    assert report['level']['ran'] == 3 and report['recorder']['F1']['ran'] + report['recorder']['F2']['ran'] == 1
    assert [f['fault'] for f in report['faults']] == ['OSError: injected recorder fault']
    # The statistics use the passes that ran; the gates are computed, the run cannot pass.
    assert set(report['gates']) == {'G1', 'G2', 'G3', 'G4', 'G5', 'G6'} and report['passed'] is False


def test_run_jobs_cancels_the_queue_on_a_ctrl_c_and_keeps_what_finished():
    import os
    import signal
    import threading
    import time
    release = threading.Event()
    started = []

    def first():
        started.append('first')
        time.sleep(.3)  # the main thread is by now waiting on this future
        os.kill(os.getpid(), signal.SIGINT)
        release.wait(5)
        return dict(done=True, ran=True)

    def never():
        started.append('never')
        return dict(done=True, ran=True)
    results, state = [], dict(faults=[], interrupted=False, aborted=None, stopped=False)
    unlaunched = []
    jobs = [(dict(name='first'), first, ()), (dict(name='second'), never, ()), (dict(name='third'), never, ())]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as executor:
        threading.Timer(.8, release.set).start()
        probe_module.run_jobs(executor, jobs, results, state, unlaunched.append)
    assert state['interrupted'] and started == ['first']
    assert results[0] == dict(done=True, ran=True)
    assert [r['ran'] for r in results] == [True, False, False] and all('cancelled' in r for r in results[1:])
    assert unlaunched == [1, 2]
    # Once stopped, a later phase launches nothing at all.
    later = []
    with ThreadPoolExecutor(max_workers=1) as executor:
        probe_module.run_jobs(executor, jobs, later, state)
    assert started == ['first'] and [r['ran'] for r in later] == [False] * 3


def test_a_faulted_run_jobs_pass_is_recorded_not_run_and_stops_the_rest():
    from concurrent.futures import ThreadPoolExecutor

    def bad():
        raise ValueError('boom')
    ran = []

    def good():
        ran.append(1)
        return dict(ran=True)
    results, state = [], dict(faults=[], interrupted=False, aborted=None, stopped=False)
    with ThreadPoolExecutor(max_workers=1) as executor:
        probe_module.run_jobs(executor, [(dict(name='a'), bad, ()), (dict(name='b'), good, ())], results, state)
    assert results[0]['ran'] is False and results[0]['fault'] == 'ValueError: boom' and results[0]['name'] == 'a'
    assert 'cancelled' in results[1] and ran == [] and state['stopped'] and len(state['faults']) == 1


# --- the held-image reconstruction -----------------------------------------------------------------------------------

def trace_run(tmp_path, images, projections):
    """A directory holding an actor trace with `images` tool results and the given `context-image-projection` events."""
    directory = tmp_path / 'trace-run'
    (directory / 'actors' / '001').mkdir(parents=True)
    events = []
    for number in range(images):
        events.append(dict(type='tool-result', tool_call_id=f'call-{number}', result=dict(content=[
            dict(type='image_reference', sha256=f'{number:064x}', image_index=0)])))
    for number, fields in enumerate(projections, 1):
        events.append(dict(type='context-image-projection', wall_time=stamp(1000. + number), request_id=f'request-{number}', **fields))
    (directory / 'actors' / '001' / 'host.jsonl').write_text('\n'.join(json.dumps(e) for e in events) + '\n')
    return dict(directory=directory)


def omissions(count):
    return [dict(tool_call_id=f'call-{i}', image_index=0, sha256='x') for i in range(min(count, 16))]


def test_the_reconstruction_reads_protected_and_pinned_fields_and_flags_a_partial_prefix(tmp_path):
    # The recorded traces carry `protected_images` and no `pinned_images`: an absent pin is zero.
    good = dict(input_images=6, protected_images=1, retained_images=4, omitted_images=2, omissions=omissions(2))
    # Omissions that would reach the protected latest batch are impossible for the host, so they are inconsistent.
    reaches = dict(input_images=3, protected_images=1, retained_images=0, omitted_images=3, omissions=omissions(3))
    pinned = dict(good, pinned_images=1)
    zero_pin = dict(good, pinned_images=0)
    bad_type = dict(good, pinned_images='0')
    wrong_count = dict(good, retained_images=5)
    # More than 16 omissions: the host lists the first 16, so only a prefix of them could be checked.
    many = dict(input_images=21, protected_images=1, retained_images=3, omitted_images=18, omissions=omissions(18))
    exactly = dict(input_images=20, protected_images=1, retained_images=4, omitted_images=16, omissions=omissions(16))
    only_many = actor_projection(trace_run(tmp_path / 'm', 21, [many]))['requests'][0]
    assert only_many['consistent'] is True and only_many['partial_prefix'] is True
    only_exactly = actor_projection(trace_run(tmp_path / 'e', 20, [exactly]))['requests'][0]
    assert only_exactly['consistent'] is True and only_exactly['partial_prefix'] is False
    one = lambda name, images, event: actor_projection(trace_run(tmp_path / name, images, [event]))['requests'][0]['consistent']
    assert one('good', 6, good) and one('zero', 6, zero_pin) and one('absent', 6, {k: v for k, v in good.items() if k != 'protected_images'})
    assert not one('reaches', 3, reaches) and not one('pinned', 6, pinned) and not one('type', 6, bad_type) and not one('count', 6, wrong_count)


def test_the_reconstruction_report_counts_inconsistent_requests_partial_prefixes_and_unknown_shas():
    items = [dict(run='a', shown=2, marginal=1, consistent=True, partial_prefix=False, unknown_sha=0),
             dict(run='a', shown=3, marginal=3, consistent=False, partial_prefix=True, unknown_sha=2),
             dict(run='b', shown=0, marginal=0, consistent=True, partial_prefix=True, unknown_sha=0),
             dict(run='b', shown=1, marginal=1, consistent=True, partial_prefix=False, unknown_sha=1)]
    assert probe_module.reconstruction_counts(items) == dict(
        requests=4, requests_inconsistent=1, shown_items_in_inconsistent_requests=3, requests_over_16_omissions=2,
        shown_items_unknown_sha=3, requests_with_unknown_sha=2)
    # G6 is computed exactly as before from `shown` and `marginal`: an unknown sha still counts as marginal there.
    result = gates_of(*healthy()[:3], items)
    assert result['gates']['G6']['point'] == pytest.approx(5 / 6)


def intent_item(source, *, exploration, attempted='did x'):
    return dict(record_id='r' * 8, session='s', first_position=1, last_position=2, subgoal_id=None, attempted=attempted, counterpart='',
                residual='', changed='something', observation_status=[], confidence=.5, sources=[source], first_source=source,
                same_session=False, score=1., exploration=exploration)


def test_the_tail_items_split_ranked_from_exploration_and_count_unknown_shas(tmp_path):
    intent = dict(schema='player-intent/4', session='s', actor_id='a', audience='tail', pass_index=1, subgoal=None, age=None,
                  recall=dict(basis='recent', items=[intent_item('src-top', exploration=False), intent_item('src-unknown', exploration=False),
                                                     intent_item('src-explore', exploration=True)]), grants_authority=False)
    held = {'sha-top'}
    shas = {'src-top': 'sha-top', 'src-explore': 'sha-other'}
    entry = dict(intent=intent, request=dict(request_id='request-1', held=held, consistent=True, partial_prefix=True))
    result = probe_module.tail_items('run-x', [entry], shas, shutil.which('node'), tmp_path)
    item = result['items'][0]
    # The top item is held (not marginal); the item with no stored sha and the exploration item are marginal.
    assert (item['shown'], item['marginal'], item['unknown_sha']) == (3, 2, 1)
    assert (item['ranked_shown'], item['ranked_marginal'], item['exploration_shown'], item['exploration_marginal']) == (2, 1, 1, 1)
    assert item['partial_prefix'] is True
    split = probe_module.exploratory_breakdown(result['items'], seed=1, resamples=20, level=.95)
    assert split['ranked']['shown'] == 2 and split['ranked']['marginal'] == 1 and split['ranked']['point'] == .5
    assert split['exploration']['shown'] == 1 and split['exploration']['point'] == 1.


def test_a_run_whose_trace_is_inconsistent_is_counted_in_the_dry_run_report(world):
    trace = world['root'] / 'fx-02' / 'actors' / '001' / 'host.jsonl'
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    projections = [e for e in events if e['type'] == 'context-image-projection']
    projections[-1]['retained_images'] += 1
    trace.write_text('\n'.join(json.dumps(e) for e in events) + '\n')
    report = run_probe(world, routes(world, 9), dry_run=True)
    reconstruction = report['stage3']['reconstruction']
    assert reconstruction['requests_inconsistent'] == 1 and reconstruction['requests'] == 26
    # The count is reported; G6 is not recomputed or gated on it (a dry run has no gates).
    assert 'gates' not in report


@pytest.fixture
def provider_factory():
    created = []

    def make(policy, **kwargs):
        value = Provider(policy, **kwargs)
        created.append(value)
        return value
    yield make
    for value in created:
        value.close()
