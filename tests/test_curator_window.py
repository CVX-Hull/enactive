"""Windows of decisions (#460): what a session over a range of one actor's steps is given.

Portable: synthetic sealed sessions projected to a temporary directory; no sandbox, no provider.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.curator.window import FULL, Window, WindowError, coverage, restrict
from harness.trace.projection import project
from tests.curator_trace import frame_id, make_long_session


def steps(out: Path, actor='001', session='s1') -> list[dict]:
    return [json.loads(line) for line in (out/session/actor/'steps.jsonl').read_text().splitlines()]


def tools(out: Path, actor='001', session='s1') -> list[dict]:
    return [json.loads(line) for line in (out/session/actor/'tools.jsonl').read_text().splitlines()]


def narrowed(tmp_path: Path, window: Window, **kw) -> tuple[Path, dict]:
    session = make_long_session(tmp_path/'evidence', **kw)
    out = tmp_path/'trace'
    return out, restrict(out, project([session], out), window)


def test_a_window_holds_only_its_steps_their_tool_calls_and_their_frames(tmp_path):
    out, manifest = narrowed(tmp_path, Window('s1', '001', 4, 6))
    assert [s['seq'] for s in steps(out)] == [4, 5, 6]
    frames = sorted(p.stem for p in (out/'frames').iterdir())
    assert frames == [frame_id(1, n) for n in (4, 5, 6)]
    assert [s['frame'] for s in steps(out)] == frames
    calls = tools(out)
    # three computer calls named by their operations, plus the memory read made just before step 6
    assert [c['tool'] for c in calls] == ['computer_input', 'computer_input', 'player_memory_read', 'computer_input']
    assert [c['outcome'].get('operation_id') for c in calls if c['tool'] == 'computer_input'] == [
        'op-1-4', 'op-1-5', 'op-1-6']
    assert manifest['sessions'][0]['actors'] == [dict(directory='001', actor_id='1' * 32, steps=3, frames=3, tool_calls=4)]
    assert sorted(manifest['files']) == sorted(
        [f'frames/{f}.png' for f in frames] + ['s1/001/steps.jsonl', 's1/001/tools.jsonl', 's1/001/received.txt'])


def test_the_manifest_says_what_the_window_is_and_what_it_dropped(tmp_path):
    out, manifest = narrowed(tmp_path, Window('s1', '001', 4, 6, game_time='day 2 08:15'))
    assert manifest['window'] == dict(session='s1', actor='001', first=4, last=6, game_time='day 2 08:15',
                                      steps_available=12)
    assert 'steps, tool calls and frames outside the window' in manifest['dropped']
    assert json.loads((out/'manifest.json').read_text()) == manifest
    for relative, digest in manifest['files'].items():
        assert hashlib.sha256((out/relative).read_bytes()).hexdigest() == digest


def test_a_window_drops_other_actors_handoffs_memory_and_the_final_report(tmp_path):
    out, manifest = narrowed(tmp_path, Window('s1', '002', 1, 2))
    assert sorted(p.name for p in (out/'s1').iterdir()) == ['002']
    assert not (out/'s1'/'002'/'final.txt').exists() and (out/'s1'/'002'/'received.txt').exists()
    assert not (out/'memory.json').exists() and manifest['sessions'][0]['handoffs'] == []
    assert sorted(p.stem for p in (out/'frames').iterdir()) == [frame_id(2, 1), frame_id(2, 2)]


def test_tool_calls_that_name_no_step_follow_the_next_step_and_the_last_call_the_last_step(tmp_path):
    out, _ = narrowed(tmp_path, Window('s1', '001', 3, 3))
    assert [c['tool'] for c in tools(out)] == ['player_memory_read', 'computer_input']  # the read before step 3
    out2, _ = narrowed(tmp_path/'again', Window('s1', '001', 12, 12))
    assert [c['tool'] for c in tools(out2)] == ['player_memory_read', 'computer_input']
    out3, _ = narrowed(tmp_path/'third', Window('s1', '001', 7, 8))
    assert [c['tool'] for c in tools(out3)] == ['computer_input', 'computer_input']  # no read before 7 or 8


def test_a_window_past_the_end_is_clamped_and_one_that_starts_after_it_is_refused(tmp_path):
    out, manifest = narrowed(tmp_path, Window('s1', '001', 10, 40))
    assert [s['seq'] for s in steps(out)] == [10, 11, 12]
    assert manifest['window']['last'] == 12 and manifest['window']['steps_available'] == 12
    with pytest.raises(WindowError, match='starts at 13'):
        narrowed(tmp_path/'late', Window('s1', '001', 13, 20))


def test_a_window_must_fit_the_trace_it_is_given(tmp_path):
    with pytest.raises(WindowError, match='no actor'):
        narrowed(tmp_path/'a', Window('s1', '009', 1, 2))
    with pytest.raises(WindowError, match='exactly the one session'):
        narrowed(tmp_path/'b', Window('other', '001', 1, 2))


@pytest.mark.parametrize('arguments', [
    dict(session='s1'), dict(actor='001'), dict(session='s1', actor='001'),
    dict(session='s1', actor='001', first=0, last=3), dict(session='s1', actor='001', first=5, last=4),
    dict(session='s1', actor='001', first=True, last=3), dict(session='s1', actor='001', first=1.5, last=3),
    dict(session='s1', actor='001', first=1, last=3, game_time=9), dict(first=2), dict(game_time='day 1'),
    dict(session='../x', actor='001', first=1, last=3), dict(session='s 1', actor='001', first=1, last=3),
    dict(session='', actor='001', first=1, last=3), dict(session='s1', actor='a/b', first=1, last=3),
    dict(session='s1', actor='001\n', first=1, last=3), dict(session=5, actor='001', first=1, last=3),
    dict(session='s1', actor=['001'], first=1, last=3), dict(session='s1', actor='001', first='1', last=3),
    dict(session='s1', actor='001', first=1, last=None)])
def test_a_window_with_a_bad_range_or_half_a_name_is_refused(arguments):
    with pytest.raises(WindowError):
        Window(**arguments)


def test_the_full_window_changes_nothing_and_takes_the_same_path(tmp_path):
    session = make_long_session(tmp_path/'evidence')
    plain = project([session], tmp_path/'plain')
    out = tmp_path/'full'
    full = restrict(out, project([session], out), FULL)
    assert full == plain and 'window' not in full and FULL.full and FULL.record() == {}
    assert sorted(p.name for p in (out/'s1').iterdir()) == ['001', '002', 'handoffs']
    assert (out/'s1'/'001'/'final.txt').exists() and len(list((out/'frames').iterdir())) == 24


def test_windows_are_read_from_rows_and_unknown_keys_are_refused():
    assert Window.read(dict(session='s1', actor='001', first=1, last=20)) == Window('s1', '001', 1, 20)
    with pytest.raises(WindowError):
        Window.read(dict(session='s1', actor='001', first=1, last=20, extra=1))
    with pytest.raises(WindowError):
        Window.read([1, 2])


def test_coverage_names_the_session_actor_last_step_read_and_game_time(tmp_path):
    out, manifest = narrowed(tmp_path, Window('s1', '001', 10, 40, game_time='day 3'))
    assert coverage(Window('s1', '001', 10, 40, game_time='day 3'), ['s1'], manifest) == {
        'schema': 'curator-coverage/1', 'session': 's1', 'actor': '001', 'last_step': 12, 'game_time': 'day 3'}
    whole = coverage(FULL, ['sd1a1', 'sd1a2'], {})
    assert whole == {'schema': 'curator-coverage/1', 'session': 'sd1a1,sd1a2', 'actor': None, 'last_step': None,
                     'game_time': None}
