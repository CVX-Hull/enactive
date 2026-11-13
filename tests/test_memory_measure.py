"""The measure gate's tooling on fixtures built here (#386): packets, the known-item list, judge events, the
labelling page and the statistics. No game, no model and no sealed evidence is read."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading
import urllib.error
import urllib.request

import numpy as np
from PIL import Image
import pytest

from harness.evaluation.core import judge
from harness.evaluation.core.records import EvaluationError, EventRow
from harness.trace.projection import project
from tools import memory_measure
from tools.memory_measure import (APPENDIX_ROWS, MeasureError, agreement, annotate_packets, binomial_interval, build_items,
    cohen_kappa, describe, draw_engaged, draw_sample, every_nth_changed, judge_events, judge_packets, label_server,
    load_items, main, measure, p_values, recorded_frames, simulate)

BASE = 4_000_000_000.0


def png(shade: int) -> bytes:
    stream = io.BytesIO()
    Image.new('RGB', (8, 8), (shade * 40 % 256, shade * 90 % 256, shade * 150 % 256)).save(stream, format='PNG')
    return stream.getvalue()


def admission(root: Path, name: str, tag: str, shades: list) -> Path:
    """One admission with one actor. Each entry of `shades` is one decision: a number presses a key and returns a
    frame of that shade (the same shade twice is an unchanged frame); None writes a record and returns no frame."""
    run, wall = root / name, BASE
    (run / 'sources').mkdir(parents=True)
    (run / 'actors' / '001').mkdir(parents=True)
    events = [dict(type='host-start', schema='player-host/4', telemetry_version=4, session=tag * 32, actor_id=tag * 32,
        wall_time=datetime.fromtimestamp(wall, timezone.utc).isoformat(), monotonic_ms=0)]
    for number, shade in enumerate(shades, 1):
        wall += 1
        common = dict(wall_time=datetime.fromtimestamp(wall, timezone.utc).isoformat(), monotonic_ms=number * 1000.0,
            request_id=f'request-{number}')
        if shade is None:
            tool, arguments, result = 'player_memory_append', dict(record=dict(text='SECRET RECORD')), dict(id='5' * 32)
        else:
            source = f'{tag * 8}-{number}'
            (run / 'sources' / f'{source}.png').write_bytes(png(shade))
            tool, arguments = 'computer_input', dict(actions=[dict(type='key', key=f'k{number}', modifiers=[])])
            result = dict(operation_id=f'{number:032x}', source=dict(source_id=source))
        events += [dict(common, type='request-start', logical_request_id=common['request_id']),
            dict(common, type='response-complete', stop_reason='toolUse', usage_available=True,
                usage=dict(input=3, output=20, cacheRead=0, cacheWrite=10, cost=dict(total=0.01, cacheWrite=0.001))),
            dict(common, type='tool-start', tool_call_id='call', tool=tool, arguments=arguments),
            dict(common, type='tool-result', tool_call_id='call', tool=tool,
                result=dict(content=[dict(type='text', text=json.dumps(result))], isError=False))]
    (run / 'actors' / '001' / 'host.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in events))
    (run / 'actors' / '001' / 'player-final.txt').write_text('SECRET REPORT')
    return run


def save(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


A, B = 'a' * 8, 'b' * 8
ANNOTATIONS = {
    'ann-a': {'packet-01': [dict(place='Garage shelf', what='tools', frames=[f'{A}-1']),
                            dict(place='Kitchen', what='cans', frames=[f'{A}-6'])],
              'packet-02': [dict(place='Garage shelf', what='tools', frames=[f'{A}-9'])],
              'packet-03': [dict(place='Pond', what='water', frames=[f'{B}-4'])]},
    'ann-b': {'packet-01': [dict(place='garage shelves', what='hammer', frames=[f'{A}-1', f'{A}-6'])],
              'packet-02': [],
              'packet-03': [dict(place='pond north', what='fresh water', frames=[f'{B}-1']),
                            dict(place='Shed', what='rope', frames=[f'{B}-4'])]}}
MATCHES = [['packet-01#1', 'packet-01#1'], ['packet-02#1', 'packet-01#1'], ['packet-03#1', 'packet-03#1']]
#: Per stretch, the labels of item-01 and item-02: the judges differ on one pair, which the third settles.
VERDICTS = {
    'judge-a': {'run-e:1-5': ('straight', 'missed'), 'run-e:6-8': ('not_engaged', 'missed'), 'run-f:1-5': ('missed', 'cannot_tell')},
    'judge-b': {'run-e:1-5': ('straight', 'missed'), 'run-e:6-8': ('not_engaged', 'missed'), 'run-f:1-5': ('straight', 'cannot_tell')},
    'judge-c': {'run-f:1-5': ('missed', 'cannot_tell')},
    'judge-d': {'run-f:1-5': ('not_engaged', 'cannot_tell')}}  # a third judge who sides with neither


def annotated(tmp_path: Path) -> tuple[Path, Path]:
    """The run directory after `packets annotate`, with both annotators' answers and the lead's matches saved."""
    run, evidence = tmp_path / 'memory-measure' / 'gate', tmp_path / 'evidence'
    run.mkdir(parents=True)
    early = [admission(evidence, 'run-a', 'a', [1, 2, 2, 3, None, 4, 5, 6, 7, 8]),
        admission(evidence, 'run-b', 'b', [10, 11, 12, 13])]
    annotate_packets(run, early, every=3, per_packet=2)
    for name, packets in ANNOTATIONS.items():
        for packet, entries in packets.items():
            save(run / 'annotations' / name / f'{packet}.json', dict(packet=packet, entries=entries))
    # `groups` is the lead's own note; any top-level key but `matches` is ignored
    return run, save(tmp_path / 'matches.json', dict(matches=MATCHES, groups=[dict(name='garage', entries=3)]))


def gate(tmp_path: Path) -> Path:
    """The run directory after the item list is frozen and the judge packets are made."""
    run, matches = annotated(tmp_path)
    build_items(run, ['ann-a', 'ann-b'], matches)
    evidence = tmp_path / 'evidence'
    late = [admission(evidence, 'run-e', 'e', [20, 21, 22, None, 23, 24, 25, 26]),
        admission(evidence, 'run-f', 'f', [30, 31, 32, 33, 34])]
    judge_packets(run, late, stretch=5, every=2, seed=7)
    return run


def answers(run: Path, name: str, change=None) -> list[Path]:
    """A judge's answer files for the stretches `VERDICTS` gives it; `change` edits each file's value first."""
    files = []
    for packet in json.loads((run / 'private' / 'judge-mapping.json').read_text())['packets']:
        labels = VERDICTS[name].get(packet['start'])
        if labels is None:
            continue
        value = dict(packet=packet['packet'], answers=[dict(item=f'item-0{number}', label=label,
            frames=['f001'] if label in judge.TOUCHED else [], note='seen') for number, label in enumerate(labels, 1)])
        if change:
            change(value)
        files.append(save(run / 'answers' / name / f"{packet['packet']}.json", value))
    return files


def judged(tmp_path: Path) -> Path:
    run = gate(tmp_path)
    for name in VERDICTS:
        judge_events(run, name, 'model-x', answers(run, name))
    return run


def test_annotate_packets_take_every_third_changed_frame_with_the_inputs_before_it(tmp_path):
    run, _ = annotated(tmp_path)
    index = json.loads((run / 'annotate' / 'packets.json').read_text())
    # run-a: shades 1 2 2 3 - 4 5 6 7 8 at decisions 1-10; the third frame repeats the second, so it is not changed.
    # Its changed frames are those of decisions 1 2 4 6 7 8 9 10; every third is 1, 6 and 9.
    assert index['frames'] == dict(recorded=13, changed=12, kept=5)
    assert [(p['packet'], p['admission'], p['frames']) for p in index['packets']] == [
        ('packet-01', 'run-a', [f'{A}-1', f'{A}-6']), ('packet-02', 'run-a', [f'{A}-9']),
        ('packet-03', 'run-b', [f'{B}-1', f'{B}-4'])]
    first = run / 'annotate' / 'packet-01'
    manifest = json.loads((first / 'manifest.json').read_text())
    assert sorted(str(p.relative_to(first)) for p in first.rglob('*') if p.is_file()) == sorted(
        ['manifest.json', 'instructions.md', *(f"frames/{frame}.png" for frame in index['packets'][0]['frames'])])
    kept = manifest['frames']
    assert kept[0]['frame'] == f'{A}-1' and len(kept[0]['inputs_before']) == 1
    # every input since the packet's previous frame is carried, also those of frames left out
    assert kept[1]['inputs_before'] == ['k2', 'k3', 'k4', 'k6']  # one entry per batch of inputs
    assert (first / 'frames' / f'{A}-1.png').read_bytes() == png(1)
    everything = b''.join(p.read_bytes() for p in (run / 'annotate').rglob('*') if p.is_file())
    assert b'SECRET' not in everything  # no player record and no final report
    with pytest.raises(MeasureError, match='made once'):
        annotate_packets(run, [tmp_path / 'evidence' / 'run-a'])
    assert main(['packets', 'annotate', str(tmp_path / 'elsewhere'), '--runs', str(tmp_path / 'evidence' / 'run-a')]) == 2


def test_every_nth_changed_and_the_changed_rule(tmp_path):
    frames, decisions = recorded_frames([admission(tmp_path, 'run-x', 'x', [1, 1, 2, None, 2, 3])])
    assert decisions == {'run-x': 6}
    assert [(f.decision, f.changed) for f in frames['run-x']] == [(1, True), (2, False), (3, True), (5, False), (6, True)]
    kept = every_nth_changed(frames['run-x'], 2)
    assert [f.decision for f in kept] == [1, 6] and len(kept[1].inputs) == 4


def test_an_item_only_one_annotator_listed_is_dropped_and_the_list_is_frozen(tmp_path, capsys):
    run, matches = annotated(tmp_path)
    assert main(['items', str(run), '--annotators', 'ann-a', 'ann-b', '--list']) == 0
    assert 'ann-a packet-01#2: Kitchen | cans' in capsys.readouterr().out and not (run / 'items.json').exists()
    value = build_items(run, ['ann-a', 'ann-b'], matches)
    assert [(i['id'], i['place'], i['first_frame'], i['frames']) for i in value['items']] == [
        ('item-01', 'Garage shelf', f'{A}-1', [f'{A}-1', f'{A}-6', f'{A}-9']), ('item-02', 'Pond', f'{B}-1', [f'{B}-1', f'{B}-4'])]
    places = json.dumps(value['items'])
    assert 'Kitchen' not in places and 'Shed' not in places  # each was listed by one annotator only
    assert value['counts'] == {'ann-a': dict(entries=4, in_an_item=3, dropped=1), 'ann-b': dict(entries=3, in_an_item=2, dropped=1)}
    items, sha = load_items(run)
    assert sha == value['sha256'] == (run / 'items.json.sha256').read_text().strip() and len(items) == 2
    assert (run / items[0]['first_frame_file']).read_bytes() == png(1)
    with pytest.raises(MeasureError, match='frozen'):
        build_items(run, ['ann-a', 'ann-b'], matches)
    other, matches = annotated(tmp_path / 'by-command')
    assert main(['items', str(other), '--annotators', 'ann-a', 'ann-b', '--matches', str(matches)]) == 0
    out = capsys.readouterr().out  # one place seen in two packets: allowed, and printed
    assert 'item-01 holds 2 entries of ann-a: packet-01#1 packet-02#1' in out and out.count(' holds ') == 1
    (run / 'items.json').write_text((run / 'items.json').read_text().replace('Pond', 'Lake'))
    with pytest.raises(MeasureError, match='recorded hash'):
        load_items(run)


@pytest.mark.parametrize('matches, message', [([['packet-01#9', 'packet-01#1']], 'must pair an entry'),
    ([['packet-01#1']], 'must pair an entry'), ([[['packet-01#1'], 'packet-01#1']], 'must pair an entry'),
    ('none', 'expected'), ([], 'at least one match')])
def test_matches_that_name_no_entry_are_refused(tmp_path, matches, message):
    run, _ = annotated(tmp_path)
    with pytest.raises(MeasureError, match=message):
        build_items(run, ['ann-a', 'ann-b'], save(tmp_path / 'bad.json', dict(matches=matches)))
    assert not (run / 'items.json').exists()


def test_an_annotation_citing_a_frame_outside_its_packet_is_refused(tmp_path):
    run, matches = annotated(tmp_path)
    save(run / 'annotations' / 'ann-b' / 'packet-02.json', dict(packet='packet-02',
        entries=[dict(place='Attic', what='rope', frames=[f'{A}-1'])]))
    with pytest.raises(MeasureError, match='outside its packet'):
        build_items(run, ['ann-a', 'ann-b'], matches)


def test_judge_packets_cut_stretches_shuffle_names_and_hold_frames_and_items_only(tmp_path):
    run = gate(tmp_path)
    mapping = json.loads((run / 'private' / 'judge-mapping.json').read_text())
    assert [(p['start'], p['decisions'], p['short'], len(p['frames'])) for p in mapping['packets']] == [
        ('run-e:1-5', 5, False, 2), ('run-e:6-8', 3, True, 2), ('run-f:1-5', 5, False, 3)]
    assert mapping['seed'] == 7 and mapping['items_sha256'] == load_items(run)[1]
    assert sorted(p.name for p in (run / 'judge-packets').iterdir()) == sorted(p['packet'] for p in mapping['packets'])
    for packet in mapping['packets']:
        directory = run / 'judge-packets' / packet['packet']
        manifest = json.loads((directory / 'manifest.json').read_text())
        assert manifest['short'] == packet['short'] and manifest['labels'] == list(judge.LABELS)
        assert [row['frame'] for row in manifest['frames']] == list(packet['frames'])
        names = sorted(str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file())
        assert names == sorted(['manifest.json', 'instructions.md', 'items.json', 'items/item-01.png', 'items/item-02.png',
            *(f'frames/{f}.png' for f in packet['frames'])])
        assert (directory / 'items' / 'item-01.png').read_bytes() == png(1)  # the frame the owner's page shows for it
        text = b''.join((directory / name).read_bytes() for name in ('manifest.json', 'instructions.md', 'items.json'))
        for hidden in (b'run-e', b'run-f', b'eeeeeeee', b'ffffffff', b'aaaaaaaa', b'ann-a', b'SECRET', b'mapping', b'arm'):
            assert hidden not in text.replace(b'harm', b'')  # no admission, source ID, annotator, record or arm
        assert json.loads((directory / 'items.json').read_text())['items'] == [
            dict(id='item-01', place='Garage shelf', what='tools'), dict(id='item-02', place='Pond', what='water')]
    first = json.loads((run / 'judge-packets' / mapping['packets'][0]['packet'] / 'manifest.json').read_text())
    assert [(row['frame'], row['decision']) for row in first['frames']] == [('f001', 1), ('f002', 3)]
    assert list(mapping['packets'][0]['frames'].values()) == ['eeeeeeee-1', 'eeeeeeee-3']
    with pytest.raises(MeasureError, match='made once'):
        judge_packets(run, [tmp_path / 'evidence' / 'run-e'])


def test_judge_packets_are_written_in_shuffled_name_order(tmp_path, monkeypatch):
    made, real = [], memory_measure.seal_packet
    monkeypatch.setattr(memory_measure, 'seal_packet', lambda directory, *rest: made.append(directory.name) or real(directory, *rest))
    run = gate(tmp_path)
    written = [name for name in made if not name.startswith('packet-')]  # the annotators' packets are named packet-NN
    lineage = [packet['packet'] for packet in json.loads((run / 'private' / 'judge-mapping.json').read_text())['packets']]
    assert written == sorted(lineage) and written != lineage  # the mapping keeps lineage order; the disk does not


def test_item_frames_are_in_the_packet_unless_left_out(tmp_path):
    run, matches = annotated(tmp_path)
    build_items(run, ['ann-a', 'ann-b'], matches)
    late = admission(tmp_path / 'evidence', 'run-g', 'g', [1, 2])
    assert main(['packets', 'judge', str(run), '--runs', str(late), '--seed', '1', '--no-item-frames']) == 0
    mapping = json.loads((run / 'private' / 'judge-mapping.json').read_text())
    directory = run / 'judge-packets' / mapping['packets'][0]['packet']
    assert mapping['item_frames'] is False and not (directory / 'items').exists()
    assert not any(name.startswith('items/') for name in json.loads((directory / 'manifest.json').read_text())['files'])
    assert mapping['packets'][0]['short'] and 'first showed each item' not in (directory / 'instructions.md').read_text()
    other, matches = annotated(tmp_path / 'default')
    build_items(other, ['ann-a', 'ann-b'], matches)
    assert main(['packets', 'judge', str(other), '--runs', str(late), '--seed', '1']) == 0
    directory = next((other / 'judge-packets').iterdir())
    assert 'items/item-02.png' in json.loads((directory / 'manifest.json').read_text())['files']
    assert 'first showed each item' in (directory / 'instructions.md').read_text()


def test_the_held_out_lineage_is_refused(tmp_path, capsys):
    held = admission(tmp_path / '522-held-out' / 'computer-sessions', 'run-h', 'h', [1, 2])
    with pytest.raises(MeasureError, match='held-out lineage is not read'):
        recorded_frames([held])
    run = tmp_path / 'memory-measure' / 'gate'
    assert main(['packets', 'annotate', str(run), '--runs', str(held)]) == 2 and not run.exists()
    assert 'held-out' in capsys.readouterr().err


@pytest.mark.parametrize('value', [[1, 2], dict(packet=['x'], answers=[]), dict(packet='PACKET', answers='none'),
    dict(packet='PACKET', answers=[dict(item=['item-01'], label='missed')]), dict(packet='PACKET', answers=[['item-01', 'missed']])])
def test_json_of_another_shape_is_refused_without_a_traceback(tmp_path, capsys, value):
    run = gate(tmp_path)
    packet = json.loads((run / 'private' / 'judge-mapping.json').read_text())['packets'][0]['packet']
    answer = save(tmp_path / 'answer.json', json.loads(json.dumps(value).replace('PACKET', packet)))
    assert main(['events', str(run), '--judge', 'judge-a', '--model', 'model-x', str(answer)]) == 2
    assert capsys.readouterr().err.startswith('memory_measure: ') and not (run / 'events').exists()


def test_a_tool_file_of_another_shape_is_refused_without_a_traceback(tmp_path, capsys):
    run = gate(tmp_path)
    save(run / 'adjudicated.json', [])
    assert main(['measure', str(run)]) == 2
    assert 'does not have the expected shape' in capsys.readouterr().err
    save(run / 'sample.json', dict(pairs='none'))
    assert main(['label-server', str(run), '--port', '0']) == 2
    assert 'does not have the expected shape' in capsys.readouterr().err


def test_events_are_validated_judge_events_under_the_run_directory(tmp_path):
    run = judged(tmp_path)
    events = judge.read_events(run / 'events' / 'judge-a.jsonl')
    assert [(e.start, e.item, e.label) for e in events][:2] == [('run-e:1-5', 'item-01', 'straight'), ('run-e:1-5', 'item-02', 'missed')]
    first = events[0]
    packet = json.loads((run / 'private' / 'judge-mapping.json').read_text())['packets'][0]
    assert (first.cited_frames, first.judge, first.model, first.packet, first.packet_sha256) == (
        ('eeeeeeee-1',), 'judge-a', 'model-x', packet['packet'], packet['sha256'])
    line = json.loads((run / 'events' / 'judge-a.jsonl').read_text().splitlines()[0])
    assert (line['schema'], line['kind'], line['source'], line['confidence']) == ('judge-events/1', 'known_item_verdict', 'judge', None)
    assert 'note' not in line['payload']
    assert len(judge.read_events(run / 'events' / 'judge-c.jsonl')) == 2  # a third judge answers only some packets
    with pytest.raises(MeasureError, match='written once'):
        judge_events(run, 'judge-a', 'model-x', answers(run, 'judge-a'))


def drop_one(value):
    value['answers'].pop()


def cite_outside(value):
    value['answers'][0].update(label='missed', frames=['f099'])


def cite_source_id(value):
    value['answers'][0].update(label='missed', frames=['eeeeeeee-1'])


@pytest.mark.parametrize('change, message', [
    (drop_one, 'no answer for item-02'),
    (cite_outside, 'cites a frame outside the packet'),
    (cite_source_id, 'cites a frame outside the packet'),
    (lambda value: value['answers'].append(dict(value['answers'][0])), 'item-01 answered 2 times'),
    (lambda value: value['answers'][0].update(label='probably'), 'is not one of straight, missed, not_engaged, cannot_tell'),
    (lambda value: value['answers'][0].update(label='straight', frames=[]), 'must cite a frame'),
    (lambda value: value['answers'].append(dict(item='item-09', label='not_engaged')), 'is not a known item'),
    (lambda value: value.update(packet='s0000000000'), 'a packet of this run')])
def test_a_judge_answer_that_does_not_fit_its_packet_is_refused(tmp_path, change, message):
    run = gate(tmp_path)
    with pytest.raises(MeasureError, match=message):
        judge_events(run, 'judge-a', 'model-x', answers(run, 'judge-a', change))
    assert not (run / 'events').exists()


def test_a_changed_packet_and_a_bad_judge_name_are_refused(tmp_path):
    run = gate(tmp_path)
    files = answers(run, 'judge-a')
    with pytest.raises(MeasureError, match='lowercase'):
        judge_events(run, '../x', 'model-x', files)
    packet = json.loads(files[0].read_text())['packet']
    manifest = run / 'judge-packets' / packet / 'manifest.json'
    manifest.write_text(manifest.read_text() + ' ')
    with pytest.raises(MeasureError, match='not the packet that was made'):
        judge_events(run, 'judge-a', 'model-x', files)


def test_the_judge_event_validator_and_the_record_that_refuses_the_source(tmp_path):
    good = judge.JudgeEvent('s:1-2', 'item-01', 'missed', ('x-1',), 'judge-a', 'model-x', 'p', '0' * 64)
    assert judge.parse(good.envelope()) == good
    for change in (dict(source='human'), dict(confidence=0.9), dict(kind='milestone'), dict(extra=1)):
        with pytest.raises(EvaluationError):
            judge.parse(dict(good.envelope(), **change))
    for change in (dict(label='maybe'), dict(cited_frames=[]), dict(packet_sha256='abc'), dict(judge=''), dict(note='x')):
        with pytest.raises(EvaluationError):
            judge.parse(dict(good.envelope(), payload=dict(good.envelope()['payload'], **change)))
    judge.write_events(tmp_path / 'one.jsonl', [good])
    with pytest.raises(FileExistsError):
        judge.write_events(tmp_path / 'one.jsonl', [good])
    with pytest.raises(EvaluationError, match='more than once'):
        judge.write_events(tmp_path / 'two.jsonl', [good, good])
    # an evaluation record never holds a judge event, so the viewer, which serves records only, cannot show one
    with pytest.raises(ValueError, match='unknown event source'):
        EventRow(1, 1, 'milestone', 'judge', None, {})


def test_nothing_the_judge_produces_reaches_the_curator_trace_or_the_player(tmp_path):
    """The curator's trace is `harness.trace.projection.project` over named session directories, by allowlist; a
    run package freezes a closed set of files (`tools.campaign_package.FILES`). Neither names the measure gate's
    directory, and the import contracts forbid the player, the curator and the trace from importing evaluation or
    tools. The projection is run here with judge output planted inside the session it projects."""
    from test_trace_projection import make_session
    run = judged(tmp_path)
    session = make_session(tmp_path / 'sessions')
    planted = (run / 'events' / 'judge-a.jsonl').read_bytes()
    (session / 'memory-measure' / 'gate' / 'events').mkdir(parents=True)
    (session / 'memory-measure' / 'gate' / 'events' / 'judge-a.jsonl').write_bytes(planted)
    (session / 'actors' / '001' / 'judge-a.jsonl').write_bytes(planted)
    project([session], tmp_path / 'trace')
    written = b''.join(p.read_bytes() for p in (tmp_path / 'trace').rglob('*') if p.is_file())
    assert b'known_item_verdict' not in written and b'judge' not in written
    root = Path(memory_measure.__file__).resolve().parents[1]
    readers = [*(root / 'harness' / 'player').rglob('*.py'), *(root / 'harness' / 'curator').rglob('*.py'),
        *(root / 'harness' / 'trace').rglob('*.py'), *(root / 'harness').glob('player_*.py'),
        *(root / 'tools' / 'curator_host').glob('*.*'), *(root / 'tools' / 'player_host').glob('*.mjs'),
        root / 'tools' / 'campaign_package.py', root / 'tools' / 'campaign_player.py', root / 'tools' / 'campaign_run.py']
    assert len(readers) > 20
    for path in readers:
        source = path.read_text(errors='replace')
        for word in ('memory-measure', 'memory_measure', 'judge-events', 'evaluation.core.judge', 'known_item_verdict'):
            assert word not in source, f'{path} names {word}'


def test_the_sample_is_drawn_once_with_its_seed_and_reads_no_verdict(tmp_path):
    run = gate(tmp_path)
    value = draw_sample(run, 4, seed=11)
    assert (value['seed'], value['count'], value['population'], value['verdicts_existed']) == (11, 4, 6, False)
    drawn = [(pair['start'], pair['item']) for pair in value['pairs']]
    assert len(set(drawn)) == 4 and set(drawn) <= set(memory_measure.all_pairs(run))
    assert [pair['index'] for pair in value['pairs']] == [0, 1, 2, 3]
    assert json.loads((run / 'sample.json').read_text()) == value
    with pytest.raises(MeasureError, match='drawn once'):
        draw_sample(run, 4, seed=12)
    other = gate(tmp_path / 'again')
    assert draw_sample(other, 4, seed=11)['pairs'] == value['pairs']  # the seed fixes the draw
    with pytest.raises(MeasureError, match='cannot draw'):
        draw_sample(gate(tmp_path / 'small'), 7)


def call(port: int, path: str, body=None, kind='application/json', host=None):
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=None if body is None else json.dumps(body).encode(),
        headers=dict({'Content-Type': kind} if body is not None else {}, **({'Host': host} if host else {})))
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.headers.get('Content-Type'), response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get('Content-Type'), error.read()


class Serving:
    def __init__(self, run: Path) -> None:
        self.server = label_server(run, 0)

    def __enter__(self) -> int:
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.server.server_address[1]

    def __exit__(self, *_) -> None:
        self.server.shutdown()
        self.server.server_close()


def sampled(run: Path, pairs: list) -> None:
    """A random sample of exactly these (start, item) pairs, as `draw_sample` writes it."""
    save(run / 'sample.json', dict(schema='calibration-sample/1', seed=0, count=len(pairs), population=6,
        pairs=[dict(index=index, start=start, item=item) for index, (start, item) in enumerate(pairs)]))


def owner_run(tmp_path: Path) -> Path:
    """Judged and adjudicated (the third judge settles run-f:1-5 / item-01 as missed), with two random pairs, 0 and 1,
    and the engaged supplement drawn after them: pairs 2, 3 and 4. The judges' notes are in `answers/`."""
    run = judged(tmp_path)
    agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=200)
    sampled(run, [('run-e:1-5', 'item-01'), ('run-f:1-5', 'item-01')])
    draw_engaged(run, 3, seed=9)
    return run


def click(port: int, position: int, step: str, label=None, keep=False):
    """One click on the page: the pair is named by its display position, never by its index."""
    return call(port, '/api/label', dict(position=position, step=step, **({'label': label} if label else {}),
        **({'keep': True} if keep else {})))


def order_of(run: Path) -> list:
    return json.loads((run / 'sample-engaged.json').read_text())['display']['order']


BLIND = ['straight', 'missed', 'not_engaged', 'cannot_tell', 'missed']  # by display position


def blind_all(port: int, labels=BLIND, stop: int | None = None) -> None:
    for position, label in enumerate(labels[:stop]):
        assert click(port, position, 'blind', label)[0] == 200


def test_the_engaged_draw_leaves_out_the_random_pairs_and_those_no_judge_called_engaged(tmp_path):
    run = judged(tmp_path)
    sampled(run, [('run-e:1-5', 'item-01'), ('run-f:1-5', 'item-01')])
    # run-e:6-8 / item-01 is not_engaged for both judges that answered it; the other three pairs outside the random draw
    # were each called straight, missed or cannot_tell by some judge
    with pytest.raises(MeasureError, match='Only 3 pairs outside the random draw'):
        draw_engaged(run, 4, seed=1)
    value = draw_engaged(run, 3, seed=1)
    pairs = [(pair['start'], pair['item']) for pair in value['pairs']]
    assert sorted(pairs) == [('run-e:1-5', 'item-02'), ('run-e:6-8', 'item-02'), ('run-f:1-5', 'item-02')]
    assert [pair['index'] for pair in value['pairs']] == [2, 3, 4]  # numbered on from the random pairs
    assert (value['seed'], value['count'], value['eligible'], value['population']) == (1, 3, 3, 6)
    assert value['judges'] == ['judge-a', 'judge-b', 'judge-c', 'judge-d']
    assert value['random_sample_sha256'] == memory_measure.file_sha256(run / 'sample.json')
    assert json.loads((run / 'sample-engaged.json').read_text()) == value and value['schema'] == 'engaged-sample/1'
    # the display order is drawn with the supplement, from the recorded seed, over all five pairs
    assert value['display']['seed'] == 1 and sorted(value['display']['order']) == [0, 1, 2, 3, 4]
    with pytest.raises(MeasureError, match='drawn once'):
        draw_engaged(run, 3, seed=2)
    # a pair counts when any judge, the third included, called it engaged
    other = judged(tmp_path / 'again')
    sampled(other, [('run-e:1-5', 'item-01'), ('run-e:1-5', 'item-02'), ('run-e:6-8', 'item-02')])
    assert sorted((p['start'], p['item']) for p in draw_engaged(other, 2, seed=4)['pairs']) == [
        ('run-f:1-5', 'item-01'), ('run-f:1-5', 'item-02')]
    # the seed fixes the draw and the order
    third, fourth = judged(tmp_path / 'third'), judged(tmp_path / 'fourth')
    sampled(third, [('run-e:1-5', 'item-01')])
    sampled(fourth, [('run-e:1-5', 'item-01')])
    again, same = draw_engaged(third, 2, seed=8), draw_engaged(fourth, 2, seed=8)
    assert again['pairs'] == same['pairs'] and again['display'] == same['display']
    assert main(['sample', str(run), '--engaged', '3']) == 2  # drawn once


def test_the_engaged_pairs_are_among_the_random_ones_in_the_display_order_and_vary_by_seed(tmp_path):
    positions = set()
    for seed in range(12):
        run = judged(tmp_path / f'seed{seed}')
        sampled(run, [('run-e:1-5', 'item-01'), ('run-f:1-5', 'item-01')])
        order = draw_engaged(run, 3, seed=seed)['display']['order']
        assert sorted(order) == [0, 1, 2, 3, 4]
        positions.add(tuple(position for position, index in enumerate(order) if index >= 2))  # where the engaged pairs sit
    assert len(positions) > 3 and any(max(p) < 4 for p in positions)  # not always last: the groups are interleaved


def test_the_engaged_draw_is_made_by_the_command_and_needs_the_verdicts_and_no_labels(tmp_path, capsys):
    run = gate(tmp_path)
    draw_sample(run, 2, seed=3)
    assert main(['sample', str(run), '--engaged', '1', '--seed', '5']) == 2
    assert 'no judge events' in capsys.readouterr().err and not (run / 'sample-engaged.json').exists()
    for name in VERDICTS:
        judge_events(run, name, 'model-x', answers(run, name))
    save(run / 'labels.json', dict(schema='owner-labels/2', labels={}))
    assert main(['sample', str(run), '--engaged', '2', '--seed', '5']) == 2  # the owner has begun labelling
    assert 'has begun labelling' in capsys.readouterr().err and not (run / 'sample-engaged.json').exists()
    (run / 'labels.json').unlink()
    assert main(['sample', str(run), '--engaged', '2', '--seed', '5']) == 0
    out = capsys.readouterr().out
    assert 'drawn with seed 5 into' in out and 'judges judge-a, judge-b, judge-c, judge-d' in out
    value = json.loads((run / 'sample-engaged.json').read_text())
    assert value['seed'] == 5 and [p['index'] for p in value['pairs']] == [2, 3]
    random_pairs = {(p['start'], p['item']) for p in json.loads((run / 'sample.json').read_text())['pairs']}
    assert not random_pairs & {(p['start'], p['item']) for p in value['pairs']}


def test_no_judge_work_is_in_any_response_until_every_pair_has_a_blind_label(tmp_path):
    run = owner_run(tmp_path)  # judges, notes and cited frames all exist on disk
    words = (b'judge', b'model-x', b'seen', b'adjudicated', b'cited', b'note')  # the notes say "seen"
    with Serving(run) as port:
        status, _, body = call(port, '/api/state')
        state = json.loads(body)
        assert status == 200 and state['total'] == 5 and state['blind'] == {} and state['checked'] == {}
        assert state['reveals'] == {} and state['pass_two'] is False
        assert [pair['position'] for pair in state['pairs']] == [0, 1, 2, 3, 4] and not any(word in body for word in words)
        for pair in state['pairs']:  # every image the state names is served, and holds no verdict
            assert call(port, pair['image'])[2].startswith(b'\x89PNG')
            assert all(call(port, frame['image'])[2].startswith(b'\x89PNG') for frame in pair['frames'])
        for path in ('/api/reveal/0', '/api/reveal', '/adjudicated.json', '/events/judge-a.jsonl', '/answers/judge-a/x.json',
                '/private/judge-mapping.json', '/labels.json', '/sample-engaged.json'):
            assert call(port, path)[0] == 404
        # a check before pass one is complete is refused, and reveals nothing
        for position in (0, 1):
            status, _, body = click(port, position, 'checked', keep=True)
            assert status == 409 and not any(word in body for word in words)
        # four of five pairs labelled: no response holds a verdict, a note or a cited frame, for any pair
        for position, label in enumerate(BLIND[:4]):
            status, _, body = click(port, position, 'blind', label)
            answer = json.loads(body)
            assert status == 200 and answer['reveals'] == {} and answer['pass_two'] is False
            assert not any(word in body for word in words) and set(answer['blind']) == {str(p) for p in range(position + 1)}
            assert not any(word in call(port, '/api/state')[2] for word in words)
        assert click(port, 0, 'checked', keep=True)[0] == 409  # still pass one
        # the fifth blind label opens pass two: now every pair's evidence is sent
        status, _, body = click(port, 4, 'blind', BLIND[4])
        after = json.loads(body)
        assert status == 200 and after['pass_two'] is True and set(after['reveals']) == {'0', '1', '2', '3', '4'}
        index = order_of(run).index(0)  # the pair run-e:1-5 / item-01 sits at this display position
        shown = after['reveals'][str(index)]
        assert (shown['adjudicated'], shown['by'], shown['screens']) == ('straight', 'agreement', [1])
        assert [(j['name'], j['label'], j['note'], j['screens']) for j in shown['judges']] == [
            ('judge-a', 'straight', 'seen', [1]), ('judge-b', 'straight', 'seen', [1])]
        third = after['reveals'][str(order_of(run).index(1))]  # run-f:1-5 / item-01, settled by the third judge
        assert [(j['name'], j['label']) for j in third['judges']] == [
            ('judge-a', 'missed'), ('judge-b', 'straight'), ('judge-c', 'missed')]
        assert (third['adjudicated'], third['by']) == ('missed', 'third')


def test_the_page_names_pairs_by_display_position_and_the_server_alone_maps_them_to_indexes(tmp_path):
    run = owner_run(tmp_path)
    order = order_of(run)
    assert order != [0, 1, 2, 3, 4]  # seed 9: otherwise this test would show nothing
    pairs = {p['index']: p for p in [*json.loads((run / 'sample.json').read_text())['pairs'],
        *json.loads((run / 'sample-engaged.json').read_text())['pairs']]}
    with Serving(run) as port:
        state = json.loads(call(port, '/api/state')[2])
        for position, pair in enumerate(state['pairs']):
            assert set(pair) == {'position', 'place', 'what', 'image', 'aspect', 'decisions', 'short', 'frames'}
            assert pair['position'] == position and pair['image'] == f'/item/{position}.png'
            assert all(frame['image'].startswith(f'/frame/{position}/') for frame in pair['frames'])
            assert call(port, f'/item/{position}.png')[0] == 200
        for word in ('index', 'engaged', 'random', 'run-e', 'run-f', 'item-0'):
            assert word not in json.dumps(state['pairs'])  # no index, group, stretch or item ID anywhere in a pair
        for position in range(5):
            assert click(port, position, 'blind', BLIND[position])[0] == 200
    saved = json.loads((run / 'labels.json').read_text())['labels']
    for position in range(5):  # the label of the pair at a position is kept under that pair's index
        entry = saved[str(order[position])]
        assert (entry['start'], entry['item'], entry['blind']) == (
            pairs[order[position]]['start'], pairs[order[position]]['item'], BLIND[position])
    assert [h['index'] for h in json.loads((run / 'labels.json').read_text())['history']] == order


def test_the_label_server_records_two_passes_and_binds_to_loopback_only(tmp_path):
    run = owner_run(tmp_path)
    order = order_of(run)
    serving = Serving(run)
    assert serving.server.server_address[0] == '127.0.0.1'
    with serving as port:
        status, kind, page = call(port, '/')
        assert status == 200 and kind.startswith('text/html')
        for outside in (b'http://', b'https://', b'src="//', b'@import', b'url('):
            assert outside not in page  # no external asset
        assert b'prefers-color-scheme: dark' in page and b'<input' not in page and b'<textarea' not in page
        assert b'Pass 1 of 2: your own answer' in page and b'Pass 2 of 2: check against the judges' in page
        state = json.loads(call(port, '/api/state')[2])
        assert [c[0] for c in state['choices']] == list(judge.LABELS)
        assert [c[1] for c in state['choices']] == ['Went straight to it', 'Missed it (looked elsewhere or got it another way)',
            'Not engaged', 'Cannot tell']
        assert state['pairs'][0]['aspect'] == '8 / 8'
        for hidden in ('judge', 'run-e', 'run-f', 'straight"', 'model-x'):
            assert hidden not in json.dumps(state['pairs'])  # no verdict, judge or admission
        frame = state['pairs'][0]['frames'][0]
        assert frame['inputs'].startswith('k') and call(port, frame['image'])[2].startswith(b'\x89PNG')
        assert call(port, state['pairs'][0]['image'])[1] == 'image/png'
        assert call(port, '/frame/0/../../private/judge-mapping.json')[0] == 404
        # pass one: a blind label once, never changed
        blind_all(port)
        status, _, body = click(port, 1, 'blind', 'straight')
        assert status == 409 and b'not changed' in body
        assert json.loads(call(port, '/api/state')[2])['blind']['1'] == 'missed'
        # pass two: position 0 keep; position 1 change, change again, then keep (which goes back to the blind label)
        assert click(port, 0, 'checked', keep=True)[0] == 200
        answer = json.loads(click(port, 1, 'checked', 'cannot_tell')[2])
        assert answer['blind'] == {str(p): BLIND[p] for p in range(5)}
        assert answer['checked'] == {'0': 'straight', '1': 'cannot_tell'}
        assert json.loads(click(port, 1, 'checked', 'not_engaged')[2])['checked']['1'] == 'not_engaged'
        assert click(port, 1, 'checked', keep=True)[0] == 200
        assert json.loads(call(port, '/api/state')[2])['checked']['1'] == 'missed'
        for bad in (dict(position=2, step='blind', label='maybe'), dict(position=9, step='blind', label='missed'),
                dict(position=2, step='first', label='missed'), dict(position=2, label='missed'), dict(position=2, step='blind'),
                dict(position=2, step='blind', keep=True), dict(position=0, step='checked', keep=True, label='missed'),
                dict(position=0, step='checked', keep='yes'), dict(position=True, step='blind', label='missed'),
                dict(index=2, step='blind', label='missed')):
            assert call(port, '/api/label', bad)[0] == 400, bad
        assert call(port, '/api/label', dict(position=2, step='checked', label='missed'), kind='text/plain')[0] == 404
        assert call(port, '/api/label', dict(position=2, step='checked', label='missed'), host='labels.example:8765')[0] == 403
        assert call(port, '/api/label', dict(position=2, step='checked', label='missed'), host=f'localhost:{port}')[0] == 200
    saved = json.loads((run / 'labels.json').read_text())
    engaged = json.loads((run / 'sample-engaged.json').read_text())
    assert saved['schema'] == 'owner-labels/2' and saved['sample_sha256'] == memory_measure.file_sha256(run / 'sample.json')
    assert saved['engaged_sha256'] == memory_measure.file_sha256(run / 'sample-engaged.json')
    assert {k: (v['blind'], v['checked']) for k, v in saved['labels'].items()} == {
        str(order[0]): ('straight', 'straight'), str(order[1]): ('missed', 'missed'), str(order[2]): ('not_engaged', 'missed'),
        str(order[3]): ('cannot_tell', None), str(order[4]): ('missed', None)}
    steps = [(h['index'], h['step'], h['label']) for h in saved['history']]
    assert steps == [(order[p], 'blind', BLIND[p]) for p in range(5)] + [
        (order[0], 'keep', 'straight'), (order[1], 'change', 'cannot_tell'), (order[1], 'change', 'not_engaged'),
        (order[1], 'keep', 'missed'), (order[2], 'change', 'missed')]  # the refused clicks wrote nothing
    assert saved['labels'][str(order[0])]['blind_time'].endswith('+00:00') and engaged['display']['order'] == order


def test_a_reload_resumes_mid_pass_and_a_repeated_check_is_one_action(tmp_path):
    run = owner_run(tmp_path)
    with Serving(run) as port:
        blind_all(port, stop=3)  # the page is closed in pass one
    with Serving(run) as port:
        state = json.loads(call(port, '/api/state')[2])
        assert set(state['blind']) == {'0', '1', '2'} and state['reveals'] == {} and state['pass_two'] is False
        for position in (3, 4):
            assert click(port, position, 'blind', BLIND[position])[0] == 200
    with Serving(run) as port:  # pass one is complete: a new server shows pass two's evidence, with nothing checked yet
        state = json.loads(call(port, '/api/state')[2])
        assert state['pass_two'] is True and state['checked'] == {} and len(state['reveals']) == 5
        assert click(port, 0, 'checked', keep=True)[0] == 200
        assert click(port, 1, 'checked', 'cannot_tell')[0] == 200
        assert click(port, 1, 'checked', 'cannot_tell')[0] == 200  # a repeated click changes nothing
        assert click(port, 1, 'blind', 'straight')[0] == 409
    saved = json.loads((run / 'labels.json').read_text())
    order = order_of(run)
    assert [(h['index'], h['step'], h['label']) for h in saved['history'][5:]] == [
        (order[0], 'keep', 'straight'), (order[1], 'change', 'cannot_tell')]


def test_a_failed_write_leaves_the_held_labels_and_the_file_as_they_were(tmp_path, monkeypatch):
    run = owner_run(tmp_path)
    store = memory_measure.LabelStore(run)
    store.record(0, 'blind', 'straight')
    held = json.dumps(store.saved, sort_keys=True)
    on_disk = (run / 'labels.json').read_text()
    real = memory_measure.write_json

    def failing(path, value, **kwargs):
        raise OSError('disk full')

    monkeypatch.setattr(memory_measure, 'write_json', failing)
    with pytest.raises(OSError):
        store.record(1, 'blind', 'missed')
    assert json.dumps(store.saved, sort_keys=True) == held and (run / 'labels.json').read_text() == on_disk
    assert store.state()['blind'] == {'0': 'straight'}
    monkeypatch.setattr(memory_measure, 'write_json', real)
    store.record(1, 'blind', 'missed')  # the same click, once the disk has room, is recorded
    assert store.state()['blind'] == {'0': 'straight', '1': 'missed'}


def test_labels_of_another_sample_or_format_are_refused(tmp_path):
    run = owner_run(tmp_path)
    with Serving(run) as port:
        click(port, 0, 'blind', 'straight')
    saved = json.loads((run / 'labels.json').read_text())
    save(run / 'labels.json', dict(saved, schema='owner-labels/1'))
    with pytest.raises(MeasureError, match='not owner-labels/2'):
        label_server(run, 0)
    save(run / 'labels.json', dict(saved, engaged_sha256='0' * 64))
    with pytest.raises(MeasureError, match='another sample'):
        label_server(run, 0)
    save(run / 'labels.json', saved)
    label_server(run, 0).server_close()
    engaged = json.loads((run / 'sample-engaged.json').read_text())
    save(run / 'sample-engaged.json', dict(engaged, display=dict(engaged['display'], order=[0, 0, 1, 2, 3])))
    save(run / 'labels.json', dict(saved, engaged_sha256=memory_measure.file_sha256(run / 'sample-engaged.json')))
    with pytest.raises(MeasureError, match='not a permutation'):
        label_server(run, 0)
    save(run / 'sample-engaged.json', engaged)
    (run / 'adjudicated.json').unlink()
    with pytest.raises(MeasureError, match='run `events` for each judge and `agreement`'):
        label_server(run, 0)



def test_describe_names_keys_text_and_repeats():
    assert describe([[dict(type='key', key='RIGHT', modifiers=[])], [dict(type='key', key='RIGHT', modifiers=[]),
        dict(type='key', key='a', modifiers=['ctrl']), dict(type='text', text='hi'), dict(type='click', x=3, y=4)]]) \
        == 'RIGHT ×2 ctrl+a "hi" click at 3,4'


def test_kappa_and_the_exact_interval_on_hand_computed_tables():
    # 20 both yes, 5 yes/no, 10 no/yes, 15 both no: observed 0.7, chance 0.5 * 0.6 + 0.5 * 0.4 = 0.5, kappa 0.4
    first = [0] * 25 + [1] * 25
    second = [0] * 20 + [1] * 5 + [0] * 10 + [1] * 15
    assert cohen_kappa(first, second) == pytest.approx(0.4)
    assert cohen_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
    assert cohen_kappa([0, 0, 0], [0, 0, 0]) is None  # chance agreement is certain
    assert binomial_interval(18, 20) == pytest.approx([0.6830, 0.9877], abs=5e-4)  # Clopper-Pearson
    assert binomial_interval(20, 20) == pytest.approx([0.8316, 1.0], abs=5e-4)
    assert binomial_interval(0, 20)[0] == 0.0


def test_agreement_reports_each_number_with_an_interval_and_the_thresholds(tmp_path, monkeypatch, capsys):
    run = judged(tmp_path)
    report = agreement(run, ['judge-a', 'judge-b'], seed=3, draws=2000)
    # five of six pairs agree; chance (1*2 + 3*2 + 1*1 + 1*1) / 36, so kappa (5/6 - 10/36) / (26/36)
    assert report['pairs'] == 6 and report['agreement']['value'] == pytest.approx(5 / 6)
    assert report['kappa']['value'] == pytest.approx((5 / 6 - 10 / 36) / (26 / 36))
    assert report['cannot_tell']['value'] == pytest.approx(1 / 6)
    for name in ('agreement', 'kappa', 'cannot_tell'):
        low, high = report[name]['interval']
        assert low <= report[name]['value'] <= high
    assert (report['bootstrap']['seed'], report['bootstrap']['draws']) == (3, 2000) and 'independent' in report['bootstrap']['note']
    assert report['unresolved'] == 1 and report['pass'] is None and report['third_alone'] == 0
    # the decision rule's share: cannot_tell over straight + missed + cannot_tell; the open pair is not yet adjudicated
    assert report['cannot_tell_of_touched'] == {'judge-a': dict(cannot_tell=1, of=5, value=0.2),
        'judge-b': dict(cannot_tell=1, of=5, value=0.2), 'adjudicated': dict(cannot_tell=1, of=4, value=0.25)}
    assert [(d['start'], d['item'], d['adjudicated']) for d in report['disputed']] == [('run-f:1-5', 'item-01', None)]
    assert len(report['third_judge_packets']) == 1
    with pytest.raises(MeasureError, match='not adjudicated'):
        measure(run)
    draw_sample(run, 4, seed=11)
    monkeypatch.setattr(memory_measure, 'OWNER_PAIRS', 4)
    monkeypatch.setattr(memory_measure, 'MIN_OWNER_MATCH', 3)
    report = agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=2000)
    adjudicated = {(row['start'], row['item']): row for row in json.loads((run / 'adjudicated.json').read_text())['pairs']}
    assert adjudicated[('run-f:1-5', 'item-01')]['label'] == 'missed' and adjudicated[('run-f:1-5', 'item-01')]['by'] == 'third'
    assert report['unresolved'] == 0 and report['owner']['compared'] == 0 and report['pass'] is None
    with Serving(run) as port:  # the owner agrees with the adjudicated label on three of the four pairs
        sample = json.loads((run / 'sample.json').read_text())['pairs']  # no supplement: positions are indexes
        for pair in sample:
            label = adjudicated[(pair['start'], pair['item'])]['label']
            wrong = next(other for other in judge.LABELS if other != label)
            assert click(port, pair['index'], 'blind', wrong if pair['index'] == 0 else label)[0] == 200
        for pair in sample:  # pass two opens when every pair has a blind label
            assert click(port, pair['index'], 'checked', keep=True)[0] == 200
    assert main(['agreement', str(run), '--judges', 'judge-a', 'judge-b', '--third', 'judge-c', '--seed', '3']) == 0
    report = json.loads((run / 'agreement.json').read_text())
    assert (report['owner']['matched'], report['owner']['compared']) == (3, 4)
    assert report['owner']['interval'] == pytest.approx(binomial_interval(3, 4))
    assert report['passes'] == dict(agreement=True, kappa=True, owner=True) and report['pass'] is True
    out = capsys.readouterr().out
    assert 'agreement 0.833 (95% interval' in out and 'pass against at least 0.8' in out
    assert 'resamples pairs as if they were independent, although a judge reads a whole packet' in out
    assert 'judge-a 1 of 5 = 0.200; judge-b 1 of 5 = 0.200; adjudicated 1 of 5 = 0.200' in out
    assert "adjudicated label against the owner's: 3 of 4 compared (exact 95% interval" in out
    assert out.strip().endswith('judge calibration: pass')
    with pytest.raises(MeasureError, match='pairs lack a verdict'):
        agreement(run, ['judge-a', 'judge-c'])


def test_measure_counts_touched_and_missed_per_stretch_with_intervals(tmp_path, capsys):
    run = judged(tmp_path)
    agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=500)
    report = measure(run, seed=5, draws=2000)
    assert report['labels'] == dict(straight=1, missed=3, not_engaged=1, cannot_tell=1) and report['per_decisions'] == 5
    whole, full = report['all_stretches'], report['full_stretches']
    # 13 decisions touch 4 items, 3 of them missed; the two full stretches hold 10 decisions, 3 touched, 2 missed
    assert (whole['stretches'], whole['decisions'], whole['touched'], whole['missed']) == (3, 13, 4, 3)
    assert whole['touched_per_stretch']['value'] == pytest.approx(5 * 4 / 13) and whole['missed_share']['value'] == 0.75
    assert (full['stretches'], full['touched_per_stretch']['value'], full['missed_share']['value']) == (2, 1.5, pytest.approx(2 / 3))
    for part in (whole, full):
        for name in ('touched_per_stretch', 'missed_share'):
            low, high = part[name]['interval']
            assert low <= part[name]['value'] <= high
    assert report['bootstrap'] == dict(seed=5, draws=2000) and report['judge_error']['all_pairs'] is None
    assert [(row['start'], row['short'], row['missed']) for row in report['stretches']] == [
        ('run-e:1-5', False, 1), ('run-e:6-8', True, 1), ('run-f:1-5', False, 1)]
    # the exact interval for a Poisson count of 4 is 1.0899 to 10.2416, here over 13 decisions and scaled to 5
    assert whole['touched_per_stretch']['exact_poisson_interval'] == pytest.approx([5 * 1.0899 / 13, 5 * 10.2416 / 13], abs=1e-3)
    assert (whole['admissions'], full['admissions']) == (2, 2)
    assert report['cannot_tell_of_touched'] == dict(cannot_tell=1, of=5, value=0.2)
    assert report['calibration']['pass'] is None and report['calibration']['agreement'] == pytest.approx(5 / 6)
    assert main(['measure', str(run), '--seed', '5']) == 0
    out = capsys.readouterr().out
    assert ('known items touched per 5 decisions 1.54; exact Poisson 95% interval 0.42 to 3.94 on 4 touched in 13 decisions; '
        'rough percentile bootstrap over 3 stretches from 2 admissions: ') in out
    assert 'missed share among touched 0.750; rough percentile bootstrap over 3 stretches from 2 admissions: ' in out
    assert 'full stretches only (2 stretches from 2 admissions; 10 decisions, 3 touched, 2 missed):' in out
    assert "cannot_tell among straight, missed and cannot_tell (the decision rule's share; no conclusion above 0.30): 1 of 5 = 0.200" in out
    assert 'judge calibration: not decided; agreement 0.833, kappa 0.769, owner match 0 of 0 compared' in out
    assert 'judge error: no owner comparison yet' in out
    assert 'point values: python -m tools.memory_measure simulate --touched 1.54 --missed 0.750 --wrong F' in out
    assert "items touched at the exact interval's lower end: python -m tools.memory_measure simulate --touched 0.42 " in out
    assert "items touched at the exact interval's upper end: python -m tools.memory_measure simulate --touched 3.94 " in out
    assert "missed share at the bootstrap interval's lower end: python -m tools.memory_measure simulate --touched 1.54 --missed 0.500" in out


def owner_labels(run: Path, labels: list[str]) -> None:
    """The calibration sample as every pair in order, and the owner's label for each, written as the page writes them."""
    pairs = memory_measure.all_pairs(run)
    save(run / 'sample.json', dict(schema='calibration-sample/1', pairs=[dict(index=index, start=start, item=item)
        for index, (start, item) in enumerate(pairs)]))
    write_owner(run, labels, labels)


def write_owner(run: Path, blind: list, checked: list) -> None:
    """The owner's labels for pairs 0, 1, ... as the page writes them; a checked label of None is still to give."""
    save(run / 'labels.json', dict(schema='owner-labels/2', labels={str(index): dict(index=index, blind=label,
        checked=checked[index]) for index, label in enumerate(blind)}))


def test_the_judge_error_is_reported_for_touched_pairs_with_its_interval(tmp_path, monkeypatch, capsys):
    run = judged(tmp_path)
    monkeypatch.setattr(memory_measure, 'OWNER_PAIRS', 6)
    monkeypatch.setattr(memory_measure, 'MIN_OWNER_MATCH', 5)
    # adjudicated: straight missed | not_engaged missed | missed cannot_tell. The owner differs on the fourth pair,
    # calling a missed item not engaged (a false engagement), and on the fifth, straight against missed.
    owner_labels(run, ['straight', 'missed', 'not_engaged', 'not_engaged', 'straight', 'cannot_tell'])
    report = agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=500)
    owner = report['owner']
    assert (owner['matched'], owner['compared'], owner['interval']) == (4, 6, pytest.approx(binomial_interval(4, 6)))
    # touched by either side: pairs one, two, four and five; two of those four match
    assert owner['touched'] == dict(compared=4, matched=2, interval=pytest.approx(binomial_interval(2, 4)))
    assert owner['false_engagement'] == 1 and report['passes']['owner'] is False and report['pass'] is False
    out = '\n'.join(memory_measure.render_agreement(report).splitlines())
    assert 'on pairs the owner or the judges called straight or missed: 2 of 4 compared (exact 95% interval' in out
    assert 'adjudicated straight or missed (false engagement): 1' in out
    result = measure(run, seed=5, draws=500)
    error = result['judge_error']
    low, high = binomial_interval(4, 6)
    assert error['all_pairs'] == dict(compared=6, differ=2, value=pytest.approx(1 / 3), interval=pytest.approx([1 - high, 1 - low]))
    assert error['touched_pairs']['value'] == 0.5 and error['touched_pairs']['compared'] == 4
    assert error['touched_measured'] is False and error['false_engagement'] == 1
    out = memory_measure.render_measure(result)
    assert 'judge calibration: fail; agreement 0.833, kappa 0.769, owner match 4 of 6 compared, third judge alone on 0 pairs' in out
    assert "the judge's error on touched items was not measured: 4 touched pairs were sampled, fewer than 5" in out
    assert 'random pairs, blind labels: 2 of 6 differ, error 0.333 (exact 95% interval' in out
    assert 'the same on the random pairs alone: 2 of 4 differ, error 0.500' in out
    assert 'cannot contain a pair every judge called not engaged, so the pooled error is conditional on a judge noticing' in out
    assert 'point values: python -m tools.memory_measure simulate --touched 1.54 --missed 0.750 --wrong 0.333' in out
    assert f"judge error at its interval's upper bound: python -m tools.memory_measure simulate --touched 1.54 --missed 0.750 --wrong {1 - low:.3f}" in out
    monkeypatch.setattr(memory_measure, 'MIN_TOUCHED_SAMPLED', 4)  # now enough touched pairs were sampled
    out = memory_measure.render_measure(measure(run, seed=5, draws=500))
    assert 'was not measured' not in out and '--wrong 0.333' not in out
    assert 'point values: python -m tools.memory_measure simulate --touched 1.54 --missed 0.750 --wrong 0.500' in out
    assert f"judge error at its interval's upper bound: python -m tools.memory_measure simulate --touched 1.54 --missed 0.750 --wrong {1 - binomial_interval(2, 4)[0]:.3f}" in out


def test_agreement_calibrates_on_blind_labels_only_and_reports_engaged_and_checked_apart(tmp_path, monkeypatch, capsys):
    run = owner_run(tmp_path)
    monkeypatch.setattr(memory_measure, 'OWNER_PAIRS', 2)
    monkeypatch.setattr(memory_measure, 'MIN_OWNER_MATCH', 2)
    adjudicated = {(r['start'], r['item']): r['label'] for r in json.loads((run / 'adjudicated.json').read_text())['pairs']}
    pairs = [(p['start'], p['item']) for p in [*json.loads((run / 'sample.json').read_text())['pairs'],
        *json.loads((run / 'sample-engaged.json').read_text())['pairs']]]
    truth = [adjudicated[pair] for pair in pairs]
    assert truth[:2] == ['straight', 'missed']
    # The owner's blind labels: pair 1 (random) wrong, and the first engaged pair that was adjudicated missed called
    # not_engaged. Then every wrong one is changed to the adjudicated label at the check.
    missed = next(at for at in range(2, 5) if truth[at] == 'missed')
    blind, checked = list(truth), list(truth)
    blind[1], blind[missed] = 'cannot_tell', 'not_engaged'
    write_owner(run, blind, checked)
    report = agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=200)
    owner = report['owner']
    assert (owner['matched'], owner['compared']) == (1, 2)  # the calibration: blind labels, random pairs only
    assert report['passes']['owner'] is False and report['pass'] is False  # the checked labels do not rescue it
    # touched among the random pairs: both (adjudicated straight and missed); one matches
    assert owner['touched'] == dict(compared=2, matched=1, interval=pytest.approx(binomial_interval(1, 2)))
    engaged = owner['engaged']
    assert (engaged['of'], engaged['compared'], engaged['matched']) == (3, 3, 2)
    assert engaged['interval'] == pytest.approx(binomial_interval(2, 3))
    # touched in the engaged pairs: the two adjudicated missed (one matched); the cannot_tell pair is not touched
    assert (engaged['touched']['compared'], engaged['touched']['matched'], engaged['false_engagement']) == (2, 1, 1)
    assert (owner['touched_all']['compared'], owner['touched_all']['matched']) == (4, 2)
    assert owner['touched_all']['interval'] == pytest.approx(binomial_interval(2, 4))
    # checked labels: both changed ones now match; reported apart and labelled
    checked_part = owner['checked']
    assert (checked_part['changed'], checked_part['checked_pairs'], checked_part['labelled']) == (2, 5, 5)
    assert checked_part['random'] == dict(compared=2, matched=2, interval=pytest.approx(binomial_interval(2, 2)))
    assert checked_part['engaged'] == dict(compared=3, matched=3, interval=pytest.approx(binomial_interval(3, 3)))
    assert 'not the calibration' in checked_part['note']
    out = memory_measure.render_agreement(report)
    assert "adjudicated label against the owner's: 1 of 2 compared (exact 95% interval" in out
    assert 'the calibration uses the owner\'s blind labels only' in out
    assert 'engaged pairs, not in the calibration (3 drawn): blind labels against the adjudicated label: 2 of 3 match' in out
    assert 'random and engaged pairs together (blind labels): 2 of 4 match' in out
    assert 'random pairs alone: 1 of 2 match' in out and 'is conditional on a judge noticing engagement and is likely low' in out
    assert 'checked labels, not the calibration' in out


def test_changed_checked_labels_are_counted_and_a_pair_still_to_check_is_left_out_of_the_checked_match(tmp_path, monkeypatch):
    run = owner_run(tmp_path)
    monkeypatch.setattr(memory_measure, 'OWNER_PAIRS', 2)
    adjudicated = {(r['start'], r['item']): r['label'] for r in json.loads((run / 'adjudicated.json').read_text())['pairs']}
    pairs = [(p['start'], p['item']) for p in [*json.loads((run / 'sample.json').read_text())['pairs'],
        *json.loads((run / 'sample-engaged.json').read_text())['pairs']]]
    truth = [adjudicated[pair] for pair in pairs]
    wrong = ['not_engaged' if label != 'not_engaged' else 'cannot_tell' for label in truth]
    # blind labels all match; the owner changes pairs 0 and 3 to wrong ones at the check; pair 4 is not yet checked
    write_owner(run, truth, [wrong[0], truth[1], truth[2], wrong[3], None])
    owner = agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=200)['owner']
    assert (owner['matched'], owner['compared']) == (2, 2) and owner['engaged']['matched'] == 3  # blind: all match
    assert (owner['checked']['changed'], owner['checked']['checked_pairs'], owner['checked']['labelled']) == (2, 4, 5)
    assert owner['checked']['random']['matched'] == 1 and owner['checked']['engaged']['compared'] == 2
    save(run / 'labels.json', dict(schema='owner-labels/1', labels={}))
    with pytest.raises(MeasureError, match='not owner-labels/2'):
        agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=200)


def test_measure_sizes_the_judge_error_on_touched_pairs_random_and_engaged_together(tmp_path, monkeypatch):
    run = owner_run(tmp_path)
    monkeypatch.setattr(memory_measure, 'OWNER_PAIRS', 2)
    adjudicated = {(r['start'], r['item']): r['label'] for r in json.loads((run / 'adjudicated.json').read_text())['pairs']}
    pairs = [(p['start'], p['item']) for p in [*json.loads((run / 'sample.json').read_text())['pairs'],
        *json.loads((run / 'sample-engaged.json').read_text())['pairs']]]
    truth = [adjudicated[pair] for pair in pairs]
    blind = list(truth)
    blind[0] = 'missed'  # a straight pair called missed
    write_owner(run, blind, list(truth))  # the check puts it right; the calibration does not see that
    agreement(run, ['judge-a', 'judge-b'], 'judge-c', seed=3, draws=200)
    error = measure(run, seed=5, draws=200)['judge_error']
    # touched by the owner or the judges: both random pairs and the two engaged pairs adjudicated missed: 4, one differs
    assert error['touched_pairs'] == dict(compared=4, differ=1, value=0.25, interval=pytest.approx(
        [1 - binomial_interval(3, 4)[1], 1 - binomial_interval(3, 4)[0]]))
    assert error['all_pairs']['compared'] == 2 and error['touched_measured'] is False
    out = memory_measure.render_measure(measure(run, seed=5, draws=200))
    assert 'random and engaged pairs together, blind labels: 1 of 4 differ, error 0.250' in out
    assert "the judge's error on touched items was not measured: 4 touched pairs were sampled, fewer than 5" in out
    monkeypatch.setattr(memory_measure, 'MIN_TOUCHED_SAMPLED', 4)
    assert measure(run, seed=5, draws=200)['judge_error']['touched_measured'] is True
    old = json.loads((run / 'agreement.json').read_text())
    save(run / 'agreement.json', dict(old, schema='judge-agreement/1'))
    with pytest.raises(MeasureError, match='run `agreement` again'):
        measure(run)


def test_a_third_label_that_matches_neither_judge_is_marked_and_listed(tmp_path):
    run = judged(tmp_path)
    report = agreement(run, ['judge-a', 'judge-b'], 'judge-d', seed=3, draws=500)
    saved = json.loads((run / 'adjudicated.json').read_text())
    row = next(row for row in saved['pairs'] if (row['start'], row['item']) == ('run-f:1-5', 'item-01'))
    assert (row['label'], row['by']) == ('not_engaged', 'third_alone') and saved['third_alone'] == 1
    assert report['third_alone'] == 1 and report['unresolved'] == 0
    assert json.loads((run / 'agreement.json').read_text())['third_alone'] == 1
    assert [(d['start'], d['item'], d['by']) for d in report['disputed']] == [('run-f:1-5', 'item-01', 'third_alone')]
    out = memory_measure.render_agreement(report)
    assert 'label neither judge gave (third_alone): 1' in out
    assert 'run-f:1-5 / item-01: judge-a missed, judge-b straight, judge-d not_engaged' in out


#: The page's own script under node, against a stub of the few DOM calls it makes and a stub of the server that keeps
#: the same rules: a pair's evidence is in the state only after its blind label, a second blind label is a 409 and a
#: check before the blind label is a 409. `process.argv[3]` is the server's labels at load time (a reload).
PAGE_STUB = r'''
const fs = require('fs'), vm = require('vm');
const page = fs.readFileSync(process.argv[2], 'utf8');
const script = page.slice(page.indexOf('<script>') + 8, page.indexOf('</script>'));
const els = {}, scrolled = [];
const make = id => ({id, hidden: false, style: {}, children: [], disabled: false, offsetHeight: 100, className: '',
  textContent: '', replaceChildren() { this.children = []; }, append(...nodes) { this.children.push(...nodes); },
  scrollIntoView() { scrolled.push(this.id); }});
let now = 1000;
Date.now = () => now;
const server = Object.assign({blind: {}, checked: {}}, JSON.parse(process.argv[3] || '{}'));
const reveal = () => ({adjudicated: 'straight', by: 'agreement', screens: [1],
  judges: [{name: 'judge-a', label: 'straight', note: 'seen', screens: [1]}, {name: 'judge-b', label: 'straight', note: null, screens: []}]});
const passTwo = () => Object.keys(server.blind).length === 3;
const snapshot = () => ({total: 3, blind: {...server.blind}, checked: {...server.checked}, pass_two: passTwo(),
  reveals: passTwo() ? Object.fromEntries(Object.keys(server.blind).map(index => [index, reveal()])) : {},
  choices: [['straight', 'Went straight to it'], ['missed', 'Missed it'], ['not_engaged', 'Not engaged'], ['cannot_tell', 'Cannot tell']],
  pairs: [0, 1, 2].map(index => ({index, place: 'p', what: 'w', image: '/item/' + index + '.png', aspect: '3 / 2', decisions: 5,
    short: false, frames: [{name: 'f001', image: '/frame/' + index + '/f001.png', decision: 1, inputs: 'k'},
      {name: 'f002', image: '/frame/' + index + '/f002.png', decision: 3, inputs: ''}]}))});
const posts = [];
let keydown = null;
globalThis.document = {getElementById: id => els[id] || (els[id] = make(id)), createElement: make,
  querySelector: () => make('main'), addEventListener: (name, handler) => { keydown = handler; }};
globalThis.window = {scrollTo() {}};
globalThis.fetch = async (url, options) => {
  if (options) {
    const body = JSON.parse(options.body);
    posts.push(body);
    if (body.step === 'blind' ? body.position in server.blind : !passTwo()) {
      return {ok: false, status: 409, json: async () => ({})};
    }
    if (body.step === 'blind') server.blind[body.position] = body.label;
    else server.checked[body.position] = body.keep ? server.blind[body.position] : body.label;
  }
  return {ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(snapshot()))};
};
const settle = () => new Promise(resolve => setImmediate(resolve));
const click = button => button.disabled ? undefined : button.onclick();  // a disabled button gets no click
const answer = () => click(els.choices.children[0]);
const start = async () => { for (const id of ['reveal-verdict', 'reveal-judges', 'reveal-screens', 'pass', 'count', 'prompt']) els[id] = make(id);
  vm.runInThisContext(script); await settle(); await settle(); };
'''

ZOOM_HARNESS = PAGE_STUB + r'''
(async () => {
  await start();
  const closers = {close: () => els['zoom-close'].onclick(), image: () => els['zoom-image'].onclick(),
    backdrop: () => els.zoom.onclick({target: els.zoom}), escape: () => keydown({key: 'Escape'})};
  const out = {};
  for (const [name, close] of Object.entries(closers)) {
    now += 1000;                    // well past the guard set when the pair appeared
    els['item-image'].onclick();    // enlarge
    const opened = els.zoom.hidden === false;
    close();
    const closed = els.zoom.hidden === true;
    await answer(); await settle(); // the second click of a double-click lands on an answer button
    els['item-image'].onclick();    // or on a screen beneath, which must not reopen the view
    out[name] = {opened, closed, recorded: posts.length, reopened: els.zoom.hidden === false};
  }
  now += 401;
  await answer(); await settle();
  out.after = posts.length;
  console.log(JSON.stringify(out));
})();
'''




def run_page(tmp_path: Path, harness: str, server=None) -> dict:
    """Run the page's script under node with `harness` and return the JSON it prints."""
    (tmp_path / 'page.html').write_text(memory_measure.PAGE)
    (tmp_path / 'harness.js').write_text(harness)
    done = subprocess.run([shutil.which('node'), str(tmp_path / 'harness.js'), str(tmp_path / 'page.html'),
        json.dumps(server or {})], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


SHOWN = r'''
const e = id => els[id] || (els[id] = make(id));
const shown = () => ({pass: e('pass').textContent, count: e('count').textContent, prompt: e('prompt').textContent,
  intro: !e('intro').hidden, work: !e('work').hidden, done: !e('done').hidden, reveal: !e('reveal').hidden,
  keep: !e('keep').hidden, next: !e('forward').hidden, back: !e('back').disabled, verdict: e('reveal-verdict').textContent,
  judges: e('reveal-judges').children.length, screens: e('reveal-screens').textContent,
  cited: e('strip').children.map(figure => figure.className), chosen: e('choices').children.map(button => button.className),
  disabled: e('choices').children.map(button => button.disabled), progress: e('progress').value});
'''

FLOW_HARNESS = PAGE_STUB + SHOWN + r'''
(async () => {
  await start();
  const out = {start: shown()};
  now += 1000;
  // Pass one. The first blind click is a double-click, the second arriving while the first is in flight.
  const first = click(els.choices.children[1]), second = click(els.choices.children[1]);
  await first; await settle();
  out.blind = {posts: posts.slice(), shown: shown(), second: second === undefined};
  await click(els.choices.children[0]); await settle();  // inside the guard: the next pair is not labelled
  out.guarded = posts.length;
  // Back within pass one shows the pair as recorded and cannot change it or show anything of the judges.
  now += 1000;
  click(els.back);
  out.recorded = shown();
  click(els.choices.children[0]);
  out.recordedClick = posts.length;
  click(els.forward);
  now += 1000;
  await click(els.choices.children[3]); await settle();
  out.second = {posts: posts.length, shown: shown()};
  now += 401;
  await click(els.choices.children[0]); await settle();  // the last blind label
  out.intro = {posts: posts.length, shown: shown()};
  click(els['start-pass-two']);                           // the second click of a double-click: inside the guard
  out.introGuarded = shown().intro;
  now += 401;
  click(els['start-pass-two']);
  out.pass2 = shown();
  // Pass two. A double-click on Keep: the second click arrives while the first is in flight.
  now += 401;
  const kept = click(els.keep);
  click(els.keep);
  await kept; await settle();
  out.keep = {posts: posts.slice(3), shown: shown()};
  now += 1000;
  click(els.back);
  out.back = shown();
  now += 401;
  await click(els.choices.children[0]); await settle();
  out.change = {posts: posts.slice(3), shown: shown()};
  now += 1000;
  click(els.back);
  out.again = shown();
  console.log(JSON.stringify(out));
})();
'''


@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
def test_the_page_walks_pass_one_the_start_screen_pass_two_keep_change_and_back(tmp_path):
    out = run_page(tmp_path, FLOW_HARNESS)
    start = out['start']
    assert start['pass'] == 'Pass 1 of 2: your own answer' and start['count'] == 'Pair 1 of 3' and start['reveal'] is False
    assert start['prompt'] == 'What did the player do about this item?' and start['keep'] is False and start['next'] is False
    # a blind click is recorded once and moves on: nothing of the judges is shown
    assert out['blind']['posts'] == [dict(position=0, step='blind', label='missed')] and out['blind']['second'] is True
    assert out['blind']['shown']['count'] == 'Pair 2 of 3' and out['blind']['shown']['reveal'] is False
    assert out['blind']['shown']['progress'] == 1 and out['guarded'] == 1
    # Back within pass one: the recorded answer, fixed, with no reveal and no judge text
    recorded = out['recorded']
    assert recorded['count'] == 'Pair 1 of 3' and recorded['reveal'] is False and recorded['cited'] == ['', '']
    assert recorded['prompt'] == 'Your answer is “Missed it”. It is saved and is not changed in this pass.'
    assert recorded['disabled'] == [True] * 4 and recorded['chosen'] == ['', 'chosen', '', ''] and recorded['next'] is True
    assert recorded['verdict'] == '' and recorded['judges'] == 0 and out['recordedClick'] == 1
    # the third blind label ends pass one: the start screen, with nothing of pass two behind it yet
    assert out['second']['posts'] == 2 and out['second']['shown']['reveal'] is False
    assert out['intro']['posts'] == 3 and out['intro']['shown']['intro'] is True and out['intro']['shown']['work'] is False
    assert out['introGuarded'] is True  # a stray second click does not start pass two
    pass2 = out['pass2']
    assert pass2['pass'] == 'Pass 2 of 2: check against the judges' and pass2['intro'] is False and pass2['count'] == 'Pair 1 of 3'
    assert pass2['reveal'] is True and pass2['keep'] is True and pass2['back'] is False and pass2['progress'] == 0
    assert pass2['verdict'] == 'Adjudicated label: Went straight to it (both judges agree).' and pass2['judges'] == 2
    assert pass2['screens'].startswith('Screens a judge cited: 1.') and pass2['cited'] == ['cited', '']
    assert pass2['prompt'] == 'You answered “Missed it”. Keep your answer, or change it?'
    # one keep, however many clicks
    assert out['keep']['posts'] == [dict(position=0, step='checked', keep=True)]
    assert out['keep']['shown']['count'] == 'Pair 2 of 3' and out['keep']['shown']['progress'] == 1
    # Back in pass two: the pair is done and shows its checked label; changing it records a change
    assert out['back']['count'] == 'Pair 1 of 3' and out['back']['next'] is True and out['back']['keep'] is False
    assert out['back']['reveal'] is True and out['back']['chosen'] == ['', 'chosen', '', '']
    assert out['change']['posts'][1:] == [dict(position=0, step='checked', label='straight')]
    assert out['change']['shown']['count'] == 'Pair 2 of 3'
    assert 'you first answered “Missed it”' in out['again']['prompt'] and out['again']['chosen'] == ['chosen', '', '', '']


@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
@pytest.mark.parametrize('server, expected', [
    (dict(blind={'0': 'straight', '1': 'cannot_tell'}),  # closed in pass one: on the next open pair, nothing revealed
     dict(count='Pair 3 of 3', intro=False, reveal=False, keep=False, pass_='Pass 1 of 2: your own answer', progress=2)),
    (dict(blind={'0': 'straight', '1': 'cannot_tell', '2': 'missed'}),  # pass one done, pass two not started
     dict(intro=True)),
    (dict(blind={'0': 'straight', '1': 'cannot_tell', '2': 'missed'}, checked={'0': 'straight'}),  # mid pass two
     dict(count='Pair 2 of 3', intro=False, reveal=True, keep=True, pass_='Pass 2 of 2: check against the judges', progress=1))])
def test_the_page_reloaded_resumes_where_the_labels_stand(tmp_path, server, expected):
    out = run_page(tmp_path, PAGE_STUB + SHOWN + r'''
(async () => { await start(); console.log(JSON.stringify(shown())); })();''', server=server)
    if expected['intro']:  # the start screen draws no pair: the pair's own parts are not touched and are hidden with it
        assert (out['intro'], out['work'], out['count']) == (True, False, '')
        return
    assert dict(count=out['count'], intro=out['intro'], reveal=out['reveal'], keep=out['keep'], pass_=out['pass'],
        progress=out['progress']) == expected


@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
def test_closing_the_enlarged_view_rearms_the_click_guard(tmp_path):
    """The page's own script runs under node against a stub of the few DOM calls it makes. Each way of closing the
    enlarged view is followed at once by a click on an answer, as the second click of a double-click would be."""
    out = run_page(tmp_path, ZOOM_HARNESS)
    assert out == dict({name: dict(opened=True, closed=True, recorded=0, reopened=False)
        for name in ('close', 'image', 'backdrop', 'escape')}, after=1)  # nothing is recorded until 400 ms after the view closed
    # the view is hidden in two places only: when a pair is drawn, and in the one closing function
    assert memory_measure.PAGE.count("el('zoom').hidden = true") == 2 and memory_measure.PAGE.count('closeZoom') == 5


def test_the_simulation_reproduces_the_appendix_first_row():
    """The protocol's table gives 0.54 for 12 starts, 5 items, missed share 0.7 and judge error 0.1, from 1500
    simulated comparisons: a standard error of 0.013 on each side, so the tolerance here is 0.05."""
    starts, touched, missed, wrong = APPENDIX_ROWS[0]
    values = p_values(np.random.default_rng(590), starts, touched, missed, 0.5, wrong)
    assert float((values <= 0.05).mean()) == pytest.approx(0.54, abs=0.05)
    assert float((values <= 0.025).mean()) == pytest.approx(0.38, abs=0.05)
    null = p_values(np.random.default_rng(591), starts, touched, missed, 1.0, wrong)
    assert float((null <= 0.05).mean()) < 0.08  # the false alarm rate stays near 5%


def test_the_search_finds_the_smallest_comparison_or_says_none_under_the_ceiling(capsys):
    # 30 items a start and little variation between starts: six starts per arm separate 0.7 from 0.35 almost always
    easy = simulate([(6, 30, 0.7, 0.0)], 30, 0.7, 0.0, rho=0.01, sims=200, draws=200, minimum=6, ceiling=8, price=2.0)
    assert easy['table'][0]['halving'] > 0.9 and easy['table'][0]['false_alarm'] < 0.15
    found = easy['search']['smallest']
    assert found['at_0_05'] == dict(starts=6, rate=found['at_0_05']['rate'], two_arms_usd=24.0, three_arms_usd=36.0)
    assert found['at_0_025']['starts'] == 6 and [row['starts'] for row in easy['search']['scanned']] == [6]
    hard = simulate([], 1, 0.5, 0.3, sims=200, draws=200, minimum=4, ceiling=5)
    assert hard['search']['smallest'] == dict(at_0_05=None, at_0_025=None) and len(hard['search']['scanned']) == 2
    assert main(['simulate', '--touched', '1', '--missed', '0.5', '--wrong', '0.3', '--sims', '100', '--draws', '100',
        '--min-starts', '4', '--ceiling', '5']) == 0
    out = capsys.readouterr().out
    assert 'at 0.05: none up to 5 starts per arm' in out and "at Holm's first step, 0.025: none up to 5" in out
    assert main(['simulate', '--missed', '1.0', '--sims', '10', '--draws', '10']) == 2
