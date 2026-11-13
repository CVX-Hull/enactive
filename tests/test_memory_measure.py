"""The measure gate's tooling on fixtures built here (#386): packets, the known-item list, judge events, the
labelling page and the statistics. No game, no model and no sealed evidence is read."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
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
    cohen_kappa, describe, draw_sample, every_nth_changed, judge_events, judge_packets, label_server, load_items, main,
    measure, p_values, recorded_frames, simulate)

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
    'judge-c': {'run-f:1-5': ('missed', 'cannot_tell')}}


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
    return run, save(tmp_path / 'matches.json', dict(matches=MATCHES))


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
    assert [action['key'] for batch in kept[1]['inputs_before'] for action in batch] == ['k2', 'k3', 'k4', 'k6']
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
    (run / 'items.json').write_text((run / 'items.json').read_text().replace('Pond', 'Lake'))
    with pytest.raises(MeasureError, match='recorded hash'):
        load_items(run)


@pytest.mark.parametrize('matches, message', [([['packet-01#9', 'packet-01#1']], 'must pair an entry'),
    ([['packet-01#1']], 'must pair an entry'), ('none', 'expected')])
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
        assert names == sorted(['manifest.json', 'instructions.md', 'items.json', *(f'frames/{f}.png' for f in packet['frames'])])
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


def test_item_frames_are_added_only_when_asked(tmp_path):
    run, matches = annotated(tmp_path)
    build_items(run, ['ann-a', 'ann-b'], matches)
    mapping = judge_packets(run, [admission(tmp_path / 'evidence', 'run-g', 'g', [1, 2])], item_frames=True, seed=1)
    directory = run / 'judge-packets' / mapping['packets'][0]['packet']
    assert (directory / 'items' / 'item-01.png').read_bytes() == png(1)
    assert 'items/item-02.png' in json.loads((directory / 'manifest.json').read_text())['files']
    assert mapping['packets'][0]['short'] and 'first showed each item' in (directory / 'instructions.md').read_text()


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


def call(port: int, path: str, body=None, kind='application/json'):
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': kind} if body is not None else {})
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


def test_the_label_server_records_a_click_survives_a_reload_and_binds_to_loopback_only(tmp_path):
    run = judged(tmp_path)  # verdicts exist, and the page must not show them
    draw_sample(run, 4, seed=11)
    sample = json.loads((run / 'sample.json').read_text())['pairs']
    serving = Serving(run)
    assert serving.server.server_address[0] == '127.0.0.1'
    with serving as port:
        status, kind, page = call(port, '/')
        assert status == 200 and kind.startswith('text/html')
        for outside in (b'http://', b'https://', b'src="//', b'@import', b'url('):
            assert outside not in page  # no external asset
        assert b'prefers-color-scheme: dark' in page and b'<input' not in page and b'<textarea' not in page
        state = json.loads(call(port, '/api/state')[2])
        assert state['total'] == 4 and state['labels'] == {} and [c[0] for c in state['choices']] == list(judge.LABELS)
        assert [c[1] for c in state['choices']] == ['Went straight to it', 'Missed it (looked elsewhere or got it another way)',
            'Not engaged', 'Cannot tell']
        assert set(state['pairs'][0]) == {'index', 'place', 'what', 'image', 'aspect', 'decisions', 'short', 'frames'}
        assert state['pairs'][0]['aspect'] == '8 / 8'
        for hidden in ('judge', 'run-e', 'run-f', 'straight"', 'model-x'):
            assert hidden not in json.dumps(state['pairs'])  # no verdict, judge or admission
        frame = state['pairs'][0]['frames'][0]
        assert frame['inputs'].startswith('k') and call(port, frame['image'])[2].startswith(b'\x89PNG')
        assert call(port, state['pairs'][0]['image'])[1] == 'image/png'
        assert call(port, '/frame/0/../../private/judge-mapping.json')[0] == 404
        assert call(port, '/api/label', dict(index=0, label='missed'))[0] == 200
        assert call(port, '/api/label', dict(index=1, label='straight'))[0] == 200
        answer = json.loads(call(port, '/api/label', dict(index=1, label='cannot_tell'))[2])  # Back, then another answer
        assert answer['labels'] == {'0': 'missed', '1': 'cannot_tell'}
        assert call(port, '/api/label', dict(index=2, label='maybe'))[0] == 400
        assert call(port, '/api/label', dict(index=9, label='missed'))[0] == 400
        assert call(port, '/api/label', dict(index=2, label='missed'), kind='text/plain')[0] == 404
    saved = json.loads((run / 'labels.json').read_text())
    assert {k: (v['start'], v['item'], v['label']) for k, v in saved['labels'].items()} == {
        '0': (sample[0]['start'], sample[0]['item'], 'missed'), '1': (sample[1]['start'], sample[1]['item'], 'cannot_tell')}
    assert len(saved['history']) == 3 and saved['labels']['0']['time'].endswith('+00:00')
    with Serving(run) as port:  # a new server, as after a crash: the labels are still there
        assert json.loads(call(port, '/api/state')[2])['labels'] == {'0': 'missed', '1': 'cannot_tell'}


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
    assert report['bootstrap'] == dict(seed=3, draws=2000) and report['unresolved'] == 1 and report['pass'] is None
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
        for pair in json.loads((run / 'sample.json').read_text())['pairs']:
            label = adjudicated[(pair['start'], pair['item'])]['label']
            wrong = next(other for other in judge.LABELS if other != label)
            assert call(port, '/api/label', dict(index=pair['index'], label=wrong if pair['index'] == 0 else label))[0] == 200
    assert main(['agreement', str(run), '--judges', 'judge-a', 'judge-b', '--third', 'judge-c', '--seed', '3']) == 0
    report = json.loads((run / 'agreement.json').read_text())
    assert (report['owner']['matched'], report['owner']['compared']) == (3, 4)
    assert report['owner']['interval'] == pytest.approx(binomial_interval(3, 4))
    assert report['passes'] == dict(agreement=True, kappa=True, owner=True) and report['pass'] is True
    out = capsys.readouterr().out
    assert 'agreement 0.833 (95% interval' in out and 'pass against at least 0.8' in out
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
    assert report['bootstrap'] == dict(seed=5, draws=2000) and report['judge_error'] is None
    assert [(row['start'], row['short'], row['missed']) for row in report['stretches']] == [
        ('run-e:1-5', False, 1), ('run-e:6-8', True, 1), ('run-f:1-5', False, 1)]
    assert main(['measure', str(run), '--seed', '5']) == 0
    out = capsys.readouterr().out
    assert 'known items touched per 5 decisions 1.54 (95% interval' in out and 'missed share among touched 0.750' in out
    assert 'simulate --touched 1.54 --missed 0.750 --wrong F' in out


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
