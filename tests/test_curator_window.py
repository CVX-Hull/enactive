"""Windows of decisions (#460): what a session over a range of one actor's steps is given.

Portable: synthetic sealed sessions projected to a temporary directory; no sandbox, no provider.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from harness.curator.window import FULL, Window, WindowError, citations_only, coverage, positions, restrict, session_labels
from harness.trace.projection import ProjectionError, project
from tests.curator_trace import SESSION_ID, frame_id, make_long_session, record_package, world_manifest_schema


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
    assert [c['tool'] for c in calls] == ['computer_input', 'computer_input', 'player_hint', 'computer_input']
    assert calls[2]['arguments']['text'] == 'hint at step 6'
    assert 'hint at step 3' not in (out/'s1'/'001'/'tools.jsonl').read_text()
    assert [c['outcome'].get('operation_id') for c in calls if c['tool'] == 'computer_input'] == [
        'op-1-4', 'op-1-5', 'op-1-6']
    assert manifest['sessions'][0]['actors'] == [dict(directory='001', actor_id='1' * 32, steps=3, frames=3, tool_calls=4)]
    assert sorted(manifest['files']) == sorted(
        [f'frames/{f}.png' for f in frames] + ['s1/001/steps.jsonl', 's1/001/tools.jsonl', 's1/001/received.txt'])


def test_the_manifest_says_what_the_window_is_and_what_it_dropped(tmp_path):
    out, manifest = narrowed(tmp_path, Window('s1', '001', 4, 6))
    assert manifest['window'] == dict(session='s1', actor='001', first=4, last=6,
                                      steps_available=12)
    assert 'steps, tool calls and frames outside the window' in manifest['dropped']
    assert manifest['hints'] == 'in-window tool calls only'
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
    assert [c['tool'] for c in tools(out)] == ['player_hint', 'computer_input']  # the read before step 3
    out2, _ = narrowed(tmp_path/'again', Window('s1', '001', 12, 12))
    assert [c['tool'] for c in tools(out2)] == ['player_hint', 'computer_input']
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
    dict(first=2),
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


def test_the_window_refuses_an_old_projection(tmp_path):
    out = tmp_path/'trace'
    manifest = project([make_long_session(tmp_path/'evidence')], out)
    manifest['schema'] = 'trace-projection/2'
    with pytest.raises(ProjectionError, match='Expected a trace-projection/3 manifest'):
        restrict(out, manifest, FULL)
    with pytest.raises(ProjectionError, match='Expected a trace-projection/3 manifest'):
        positions(out, manifest, {})
    with pytest.raises(ProjectionError, match='Expected a trace-projection/3 manifest'):
        coverage(FULL, ['s1'], manifest)
    with pytest.raises(ProjectionError, match='Expected a trace-projection/3 manifest'):
        session_labels(manifest)
    with pytest.raises(ProjectionError, match='Expected a trace-projection/3 manifest'):
        citations_only(out, manifest, {frame_id(1, 1)})


def test_windows_are_read_from_rows_and_unknown_keys_are_refused():
    assert Window.read(dict(session='s1', actor='001', first=1, last=20)) == Window('s1', '001', 1, 20)
    with pytest.raises(WindowError):
        Window.read(dict(session='s1', actor='001', first=1, last=20, extra=1))
    with pytest.raises(WindowError):
        Window.read([1, 2])


def test_coverage_names_the_session_actor_and_last_step_read(tmp_path):
    out, manifest = narrowed(tmp_path, Window('s1', '001', 10, 40))
    assert coverage(Window('s1', '001', 10, 40), ['s1'], manifest) == {
        'schema': 'curator-coverage/2', 'session': 's1', 'actor': '001', 'last_step': 12}
    whole = coverage(FULL, ['sd1a1', 'sd1a2'], manifest)
    assert whole == {'schema': 'curator-coverage/2', 'session': 'sd1a1,sd1a2', 'actor': None, 'last_step': None}


def test_gate_input_keeps_session_labels_separate_from_the_four_frame_position_keys(tmp_path, world_manifest_schema):
    second_id = 'b' * 32
    first = make_long_session(tmp_path, 'pond', steps=1, actors=('001',))
    second = make_long_session(tmp_path, 'forest', steps=1, actors=('001',), session_id=second_id)
    pond = dict(world='pond', lineage='first survivor', admission=9)
    forest = dict(world='forest', lineage='second survivor', admission=3)
    record_package(first, schema=world_manifest_schema, labels=pond)
    record_package(second, schema=world_manifest_schema, session_id=second_id, labels=forest)
    out = tmp_path/'trace'
    manifest = restrict(out, project([first, second], out), FULL)
    gate_input = positions(out, manifest, {})
    assert gate_input.sessions == {
        SESSION_ID: dict(name='pond', **pond, label_check=None, label_error=None),
        second_id: dict(name='forest', **forest, label_check=None, label_error=None),
    }
    assert gate_input == {
        frame_id(1, 1): dict(session='pond', actor='001', step=1, order=[1, '001', 1]),
        frame_id(1, 1, second_id): dict(session='forest', actor='001', step=1, order=[2, '001', 1]),
    }


def test_session_labels_are_available_from_the_manifest_after_copying_positions(tmp_path):
    first = make_long_session(tmp_path, 'pond', steps=1, actors=('001',))
    second_id = 'b' * 32
    second = make_long_session(tmp_path, 'forest', steps=1, actors=('001',), session_id=second_id)
    record_package(second, session_id=second_id, labels=dict(lineage='survivor', admission=3))
    out = tmp_path/'trace'
    manifest = project([first, second], out)
    frame_positions = positions(out, manifest, {})
    assert session_labels(manifest) == frame_positions.sessions == {
        SESSION_ID: dict(name='pond', world=None, lineage=None, admission=None,
                         label_check='manifest-schema', label_error='manifest.json missing or unreadable'),
        second_id: dict(name='forest', world=None, lineage='survivor', admission=3, label_check=None, label_error=None),
    }
    for copy in (dict(frame_positions), frame_positions | {}, json.loads(json.dumps(frame_positions))):
        assert copy == frame_positions
        assert not hasattr(copy, 'sessions')


def test_sightings_follow_trace_order_even_when_windows_are_replayed_backwards(tmp_path, world_manifest_schema):
    trace = make_long_session(tmp_path/'evidence')
    labels = dict(world='pond', lineage='survivor', admission=3)
    record_package(trace, schema=world_manifest_schema, labels=labels)
    later = tmp_path/'later'
    later_manifest = restrict(later, project([trace], later), Window('s1', '001', 7, 9))
    known = positions(later, later_manifest, {})
    earlier = tmp_path/'earlier'
    earlier_manifest = restrict(earlier, project([trace], earlier), Window('s1', '001', 2, 4))
    added = positions(earlier, earlier_manifest, known)
    assert added[frame_id(1, 4)]['order'] < known[frame_id(1, 7)]['order']
    assert positions(later, later_manifest, known | added) == known
    assert added[frame_id(1, 2)] == dict(session='s1', actor='001', step=2, order=[1, '001', 2])
    assert added.sessions == known.sessions == {SESSION_ID: dict(name='s1', **labels, label_check=None, label_error=None)}


@pytest.mark.parametrize('recorded_step', [3, 5])
def test_a_window_preserves_the_recorded_position_of_a_repeated_frame(tmp_path, recorded_step):
    out, manifest = narrowed(tmp_path, Window('s1', '001', 4, 4))
    frame = frame_id(1, 4)
    recorded = dict(session='s1', actor='001', step=recorded_step, order=[1, '001', recorded_step])
    assert positions(out, manifest, {frame: recorded}) == {frame: recorded}


def test_a_new_frame_uses_its_earliest_position_when_it_repeats_in_one_window(tmp_path):
    trace = make_long_session(tmp_path/'evidence', steps=2, actors=('001',))
    frame = frame_id(1, 1)
    with closing(sqlite3.connect(trace/'session.sqlite3')) as db, db:
        db.execute('UPDATE native_intents SET source = ? WHERE operation = ?', (frame, 'op-1-2'))
    out = tmp_path/'trace'
    manifest = restrict(out, project([trace], out), Window('s1', '001', 1, 2))
    assert [step['frame'] for step in steps(out)] == [frame, frame]
    assert positions(out, manifest, {}) == {frame: dict(session='s1', actor='001', step=1, order=[1, '001', 1])}


def test_grooming_projection_keeps_exactly_cited_frames_and_their_steps(tmp_path):
    trace = make_long_session(tmp_path/'evidence')
    record_package(trace, labels=dict(lineage='survivor', admission=3))
    out = tmp_path/'trace'
    from tests.test_trace_projection import make_journal

    journal = tmp_path/'journal.sqlite3'
    make_journal(journal)
    manifest = project([trace], out, journal=journal)
    assert (out/'journal.json').exists()
    cited = {frame_id(1, 3), frame_id(2, 5)}
    reduced = citations_only(out, manifest, cited)
    assert {p.stem for p in (out/'frames').iterdir()} == cited
    assert [s['seq'] for s in steps(out)] == [3]
    assert [s['seq'] for s in steps(out, '002')] == [5]
    assert not (out/'s1'/'001'/'received.txt').exists()
    assert not (out/'s1'/'handoffs').exists()
    assert not (out/'journal.json').exists()
    assert [c['arguments'].get('text') for c in tools(out) if c['tool'] == 'player_hint'] == ['hint at step 3']
    assert 'hint at step 6' not in (out/'s1'/'001'/'tools.jsonl').read_text()
    assert reduced['citations_only'] == sorted(cited)
    gate_input = positions(out, reduced, {})
    assert gate_input.keys() == cited
    assert gate_input.sessions == {
        SESSION_ID: dict(name='s1', world=None, lineage='survivor', admission=3, label_check=None, label_error=None),
    }
    with pytest.raises(WindowError, match='missing from trace'):
        citations_only(out, reduced, {'absent'})


def test_window_removes_entire_journal_and_keeps_only_in_range_hints(tmp_path):
    from tests.test_trace_projection import make_journal

    trace = make_long_session(tmp_path/'evidence')
    journal = tmp_path/'journal.sqlite3'
    make_journal(journal)
    out = tmp_path/'trace'
    manifest = restrict(out, project([trace], out, journal=journal), Window('s1', '001', 4, 6))
    assert not (out/'journal.json').exists() and 'journal.json' not in manifest['files']
    assert [c['arguments']['text'] for c in tools(out) if c['tool'] == 'player_hint'] == ['hint at step 6']
    assert 'out-of-window journal sentinel' not in ''.join(p.read_text() for p in out.rglob('*.json*'))
