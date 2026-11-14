"""The memory measure's tooling on fixtures built here (#386): packets cut to a token budget, the facts to judge,
judge events and the standing use measures. No game, no model and no sealed evidence is read. The anchor and the
prompt-change check are in test_memory_measure_checks.py, the simulation in test_memory_measure_withholding.py."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from harness.evaluation.core import judge
from harness.evaluation.core.records import EvaluationError, EventRow
from harness.trace.projection import project
from tools import memory_measure
from tools.memory_measure import (ANNOTATE_INSTRUCTIONS, JUDGE_INSTRUCTIONS, Frame, MeasureError, StartBootstrap, agreement,
    annotate_packets, binomial_interval, build_items, cohen_kappa, cut, describe, every_nth_changed, fact_packets,
    image_tokens, judge_events, main, measure, recorded_frames, text_tokens)

BASE = 4_000_000_000.0


def png(shade: int, size=(8, 8)) -> bytes:
    stream = io.BytesIO()
    Image.new('RGB', size, (shade * 40 % 256, shade * 90 % 256, shade * 150 % 256)).save(stream, format='PNG')
    return stream.getvalue()


def admission(root: Path, name: str, tag: str, shades: list, size=(8, 8)) -> Path:
    """One admission. Each entry of `shades` is one decision: a number presses a key, with a stated intent and a
    cited fact, and returns a frame of that shade (the same shade twice is an unchanged frame); None writes a
    record and returns no frame; 'lost' presses a key whose frame never came back; 'handoff' starts the next actor."""
    run, wall, number, actor = root / name, BASE, 0, 0
    (run / 'sources').mkdir(parents=True)
    groups = [[]]
    for shade in shades:
        if shade == 'handoff':
            groups.append([])
        else:
            groups[-1].append(shade)
    for group in groups:
        actor += 1
        directory = run / 'actors' / f'{actor:03d}'
        directory.mkdir(parents=True)
        events = [dict(type='host-start', schema='player-host/5', telemetry_version=5, session=tag * 32,
            actor_id=(tag + str(actor)) * 16, wall_time=datetime.fromtimestamp(wall, timezone.utc).isoformat(), monotonic_ms=0)]
        for shade in group:
            wall, number = wall + 1, number + 1
            common = dict(wall_time=datetime.fromtimestamp(wall, timezone.utc).isoformat(), monotonic_ms=number * 1000.0,
                request_id=f'request-{number}')
            if shade is None:
                tool, arguments, result = 'player_memory_append', dict(record=dict(text='SECRET RECORD')), dict(id='5' * 32)
            else:
                source = f'{tag * 8}-{number}'
                tool = 'computer_input'
                arguments = dict(actions=[dict(type='key', key=f'k{number}', modifiers=[])], intent=f'INTENT-MARK {number}',
                    cites=['CITES-MARK'])
                result = dict(operation_id=f'{number:032x}')
                if shade != 'lost':
                    (run / 'sources' / f'{source}.png').write_bytes(png(shade, size))
                    result['source'] = dict(source_id=source)
            events += [dict(common, type='request-start', logical_request_id=common['request_id']),
                dict(common, type='response-complete', stop_reason='toolUse', usage_available=True,
                    usage=dict(input=3, output=20, cacheRead=0, cacheWrite=10, cost=dict(total=0.01, cacheWrite=0.001))),
                dict(common, type='tool-start', tool_call_id='call', tool=tool, arguments=arguments),
                dict(common, type='tool-result', tool_call_id='call', tool=tool,
                    result=dict(content=[dict(type='text', text=json.dumps(result))], isError=False))]
        (directory / 'host.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in events))
        (directory / 'player-final.txt').write_text('SECRET REPORT')
    return run


def save(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def fact(identity: str, **more) -> dict:
    return dict(id=identity, text='A useful observed fact.', **more)


#: What was delivered to each actor of three admissions, as delivery would write it. Every marker in capitals is
#: something a blind packet must not hold.
FACTS = dict(schema='judged-facts/1', admissions={
    'run-e': {'001': dict(lead=[fact('lead-1'), fact('lead-2')], read=[fact('read-1', from_decision=6)], index=[fact('index-1')],
        withheld=[fact('held-1')], briefing='BRIEFING-MARK lead-1 lead-2', reminders=[dict(decision=3, text='REMINDER-MARK')])},
    'run-f': {'001': dict(lead=[fact('lead-1'), fact('lead-2')], read=[fact('read-1')], index=[fact('index-1')],
        withheld=[fact('held-2')], briefing='BRIEFING-MARK lead-1 lead-2')},
    'run-g': {'001': dict(lead=[fact('lead-1')], read=[fact('read-2')], withheld=[fact('held-1')])}})
#: Per admission and fact, (label, holds) of each judge. The first two differ on one label and on one `holds`; the
#: third judge answers that admission's packet.
SAME = {('run-e', 'lead-1'): ('in_line', 'held'), ('run-e', 'lead-2'): ('found_again', 'held'),
    ('run-e', 'read-1'): ('in_line', 'stale_or_false'), ('run-e', 'index-1'): ('did_not_apply', 'cannot_tell'),
    ('run-f', 'read-1'): ('did_not_apply', 'cannot_tell'), ('run-f', 'index-1'): ('found_again', 'held'),
    ('run-g', 'lead-1'): ('cannot_tell', 'cannot_tell'), ('run-g', 'read-2'): ('in_line', 'held')}
VERDICTS = {
    'judge-a': {**SAME, ('run-f', 'lead-1'): ('against', 'held'), ('run-f', 'lead-2'): ('in_line', 'held')},
    'judge-b': {**SAME, ('run-f', 'lead-1'): ('in_line', 'held'), ('run-f', 'lead-2'): ('in_line', 'cannot_tell')},
    'judge-c': {('run-f', 'lead-1'): ('against', 'held'), ('run-f', 'lead-2'): ('in_line', 'held'),
        ('run-f', 'read-1'): ('did_not_apply', 'cannot_tell'), ('run-f', 'index-1'): ('found_again', 'held')},
    'judge-d': {('run-f', 'lead-1'): ('found_again', 'held'), ('run-f', 'lead-2'): ('in_line', 'held'),  # sides with neither
        ('run-f', 'read-1'): ('did_not_apply', 'cannot_tell'), ('run-f', 'index-1'): ('found_again', 'held')}}


def evidence(tmp_path: Path, size=(8, 8)) -> list[Path]:
    root = tmp_path / 'evidence'
    return [admission(root, 'run-e', 'e', [20, 21, 22, None, 23, 24, 25, 26], size),
        admission(root, 'run-f', 'f', [30, 31, 32, 33, 34], size), admission(root, 'run-g', 'g', [40, 41, 42], size)]


def packed(tmp_path: Path, kind='use', **options) -> Path:
    """A run directory with judge packets over three admissions, one window each at the default budget."""
    run = tmp_path / 'memory-measure' / 'study'
    run.mkdir(parents=True)
    fact_packets(run, evidence(tmp_path), save(tmp_path / 'facts.json', FACTS), kind, **dict(dict(every=1, seed=7), **options))
    return run


def mapping_of(run: Path) -> dict:
    return json.loads((run / 'private' / 'judge-mapping.json').read_text())


def answers(run: Path, name: str, verdicts=None, change=None) -> list[Path]:
    """A judge's answer files for the packets whose admission its verdicts name; `change` edits each value first."""
    verdicts, files = VERDICTS[name] if verdicts is None else verdicts, []
    for packet in mapping_of(run)['packets']:
        if not any(start == packet['start'] for start, _ in verdicts):
            continue
        value = dict(packet=packet['packet'], answers=[dict(fact=opaque, label=verdicts[(packet['start'], identity)][0],
            holds=verdicts[(packet['start'], identity)][1],
            frames=[packet['available_from'].get(identity, 'f001')] if verdicts[(packet['start'], identity)][0] in judge.APPLIED else [], note='seen')
            for opaque, identity in packet['fact_ids'].items()])
        if change:
            change(value)
        files.append(save(run / 'answers' / name / f"{packet['packet']}.json", value))
    return files


def judged(tmp_path: Path, kind='use') -> Path:
    run = packed(tmp_path, kind)
    for name in ('judge-a', 'judge-b', 'judge-c'):
        judge_events(run, name, 'model-x', answers(run, name, blind_verdicts(run, name) if kind == 'blind' else None))
    return run


def blind_verdicts(run: Path, name: str) -> dict:
    """The same verdicts with the withheld facts of a blind packet added, found again by both judges."""
    held = {(packet['start'], identity): ('found_again', 'held') for packet in mapping_of(run)['packets']
        for identity, route in packet['facts'].items() if route == 'withheld'}
    return {**{key: value for key, value in held.items() if any(start == key[0] for start, _ in VERDICTS[name])}, **VERDICTS[name]}


def packet_text(directory: Path) -> bytes:
    return b''.join(path.read_bytes() for path in sorted(directory.rglob('*')) if path.is_file() and path.suffix != '.png')


# --- the token budget ---------------------------------------------------------------------------------------------------

def test_tokens_are_estimated_from_pixel_size_and_text_length():
    assert image_tokens(960, 640) == 820 and image_tokens(8, 8) == 1
    assert image_tokens(3136, 2000) == image_tokens(1568, 1000)  # a long edge over 1568 px is scaled down to it first
    assert text_tokens('a' * 300) == 100 and text_tokens('a' * 301) == 101


def test_cut_keeps_within_the_budget_cuts_only_between_decisions_and_evens_the_parts():
    frames = [Frame('run', '001', f's{number}', decision, Path('x'), ()) for number, decision in
        enumerate([1, 2, 2, 3, 4, 5, 6, 6, 6, 7])]
    parts = cut(frames, lambda frame: 10, 35)
    assert [[frame.decision for frame in part] for part in parts] == [[1, 2, 2], [3, 4, 5], [6, 6, 6], [7]]
    assert all(len(part) * 10 <= 35 for part in parts)
    assert all(a[-1].decision != b[0].decision for a, b in zip(parts, parts[1:]))  # no decision is split
    # six frames of 10 in a budget of 50: two parts of three, not five and a tail of one
    even = cut([Frame('run', '001', f's{number}', number, Path('x'), ()) for number in range(6)], lambda frame: 10, 50)
    assert [len(part) for part in even] == [3, 3]
    # one decision larger than the budget is a part by itself, never dropped
    assert [len(part) for part in cut(frames[5:9], lambda frame: 10, 25)] == [1, 3]


def test_judge_packets_are_cut_to_the_token_budget_and_record_it(tmp_path):
    runs = evidence(tmp_path, size=(750, 400))  # 400 image tokens a frame
    facts = save(tmp_path / 'facts.json', FACTS)
    wide, narrow = tmp_path / 'memory-measure' / 'wide', tmp_path / 'memory-measure' / 'narrow'
    for run in (wide, narrow):
        run.mkdir(parents=True)
    fact_packets(wide, runs, facts, 'use', every=1, seed=1)
    assert [(p['window'], len(p['frames'])) for p in mapping_of(wide)['packets']] == [
        ('run-e/001:1-8', 7), ('run-f/001:1-5', 5), ('run-g/001:1-3', 3)]
    budget = 3600
    fact_packets(narrow, runs, facts, 'use', budget=budget, every=1, seed=1)
    mapping = mapping_of(narrow)
    assert mapping['budget_tokens'] == budget
    by_start = {}
    for packet in mapping['packets']:
        by_start.setdefault(packet['start'], []).append(packet)
        manifest = json.loads((narrow / 'judge-packets' / packet['packet'] / 'manifest.json').read_text())
        estimate = manifest['budget']
        assert estimate['tokens'] == budget and not estimate['over'] and estimate['estimated']['total'] <= budget
        assert estimate['estimated']['images'] == 400 * len(manifest['frames'])
        assert estimate['estimated']['text'] > text_tokens(JUDGE_INSTRUCTIONS['use'])  # instructions, facts and rows are counted
        assert packet['estimated_tokens'] == estimate['estimated']['total'] and manifest['decisions'] == packet['decisions']
    assert len(by_start['run-e']) > 1  # the budget, not a count of decisions or frames, ends a window
    for windows in by_start.values():  # an actor's windows follow one another and cover all its decisions
        assert windows[0]['first'] == 1 and all(a['last'] + 1 == b['first'] for a, b in zip(windows, windows[1:]))
    assert [windows[-1]['last'] for windows in by_start.values()] == [8, 5, 3]
    with pytest.raises(MeasureError, match='leaves no room for frames'):
        fact_packets(tmp_path / 'memory-measure' / 'tiny', runs, facts, 'use', budget=500, every=1)
    assert not (tmp_path / 'memory-measure' / 'tiny').exists()


def test_a_long_fact_list_is_split_over_packets_of_the_same_window(tmp_path):
    many = dict(schema='judged-facts/1', admissions={'run-g': {'001': dict(index=[dict(id=f'fact-{number:03d}', text='x' * 300)
        for number in range(40)])}})
    run = tmp_path / 'memory-measure' / 'many'
    run.mkdir(parents=True)
    fact_packets(run, evidence(tmp_path)[2:], save(tmp_path / 'many.json', many), 'use', budget=6000, every=1, seed=3)
    packets = mapping_of(run)['packets']
    assert len(packets) > 1 and {packet['window'] for packet in packets} == {'run-g/001:1-3'}
    listed = [identity for packet in packets for identity in packet['facts']]
    assert sorted(listed) == [f'fact-{number:03d}' for number in range(40)]  # every fact once: a pair is judged once
    assert all(packet['estimated_tokens'] <= 6000 for packet in packets)


def test_annotate_packets_are_cut_to_the_budget_with_the_inputs_before_each_frame(tmp_path):
    run = tmp_path / 'memory-measure' / 'study'
    run.mkdir(parents=True)
    early = [admission(tmp_path / 'evidence', 'run-a', 'a', [1, 2, 2, 3, None, 4, 5, 6, 7, 8], (750, 400)),
        admission(tmp_path / 'evidence', 'run-b', 'b', [10, 11, 12, 13], (750, 400))]
    budget = memory_measure.MANIFEST_HEAD_TOKENS + text_tokens(ANNOTATE_INSTRUCTIONS) + 1000  # room for two frames
    index = annotate_packets(run, early, every=3, budget=budget)
    # run-a: shades 1 2 2 3 - 4 5 6 7 8 at decisions 1-10; the third frame repeats the second, so it is not changed.
    # Its changed frames are those of decisions 1 2 4 6 7 8 9 10; every third is 1, 6 and 9.
    assert index['frames'] == dict(recorded=13, changed=12, kept=5) and index['budget_tokens'] == budget
    a, b = 'a' * 8, 'b' * 8
    assert [(p['packet'], p['admission'], p['frames']) for p in index['packets']] == [
        ('packet-01', 'run-a', [f'{a}-1', f'{a}-6']), ('packet-02', 'run-a', [f'{a}-9']), ('packet-03', 'run-b', [f'{b}-1', f'{b}-4'])]
    first = run / 'annotate' / 'packet-01'
    manifest = json.loads((first / 'manifest.json').read_text())
    assert manifest['budget']['tokens'] == budget and manifest['budget']['estimated']['images'] == 800 and not manifest['budget']['over']
    assert sorted(str(p.relative_to(first)) for p in first.rglob('*') if p.is_file()) == sorted(
        ['manifest.json', 'instructions.md', *(f'frames/{frame}.png' for frame in index['packets'][0]['frames'])])
    # every input since the packet's previous frame is carried, also those of frames left out
    assert manifest['frames'][1]['inputs_before'] == ['k2', 'k3', 'k4', 'k6']
    everything = b''.join(p.read_bytes() for p in (run / 'annotate').rglob('*') if p.is_file() and p.suffix != '.png')
    for hidden in (b'SECRET', b'INTENT-MARK', b'CITES-MARK'):  # no player record, no report, nothing the player stated
        assert hidden not in everything
    with pytest.raises(MeasureError, match='made once'):
        annotate_packets(run, early)
    assert main(['packets', 'annotate', str(tmp_path / 'elsewhere'), '--runs', str(early[0])]) == 2


def test_every_nth_changed_the_changed_rule_and_actor_spans(tmp_path):
    frames, spans = recorded_frames([admission(tmp_path, 'run-x', 'x', [1, 1, 2, None, 2, 'handoff', 3, 3, 4])])
    assert spans == {'run-x': {'001': (1, 5), '002': (6, 8)}}
    found = frames['run-x']
    assert [(f.actor, f.decision, f.changed) for f in found] == [('001', 1, True), ('001', 2, False), ('001', 3, True),
        ('001', 5, False), ('002', 6, True), ('002', 7, False), ('002', 8, True)]
    assert found[0].stated == (dict(tool='computer_input', intent='INTENT-MARK 1', cites=['CITES-MARK']),)
    kept = every_nth_changed(found[:4], 2)
    assert [f.decision for f in kept] == [1] and len(kept[0].inputs) == 1
    kept = every_nth_changed(found, 2)
    assert [f.decision for f in kept] == [1, 6] and len(kept[1].inputs) == 4 and len(kept[1].stated) == 4
    # what one actor sent and said after its last frame is not put before the next actor's first frame
    frames, _ = recorded_frames([admission(tmp_path, 'run-y', 'y', [1, 'lost', 'handoff', 2])])
    first, second = frames['run-y']
    assert (second.actor, second.decision, len(second.inputs)) == ('002', 3, 1)
    assert second.stated == (dict(tool='computer_input', intent='INTENT-MARK 3', cites=['CITES-MARK']),)


# --- game-neutral wording -------------------------------------------------------------------------------------------------

def test_the_instructions_name_no_kind_of_thing_in_a_game_and_give_the_five_labels():
    for words in (ANNOTATE_INSTRUCTIONS, *JUDGE_INSTRUCTIONS.values()):
        lowered = words.lower()
        for word in ('place', 'goods', 'item', 'loot', 'map', 'building', 'weapon', 'food', 'monster', 'inventory', 'known item'):
            assert word not in lowered, word
    assert 'every fact the frames show that a later player of the same session could use' in ANNOTATE_INSTRUCTIONS
    for words in JUDGE_INSTRUCTIONS.values():
        for label in judge.USE_LABELS:
            assert f'`{label}`' in words
        for label, phrase in judge.USE_LABEL_TEXT.items():
            if label not in ('cannot_tell', 'found_again'):
                assert phrase in words.lower()
        assert all(f'`{value}`' in words for value in judge.HOLDS) and 'not one step' in words
    assert judge.USE_LABELS == ('in_line', 'against', 'found_again', 'did_not_apply', 'cannot_tell')
    assert judge.USE_LABEL_TEXT == dict(in_line='acted in line with it', against='acted against it',
        found_again='found it again', did_not_apply='did not apply', cannot_tell='cannot tell')


def test_annotated_facts_are_matched_from_two_lists_and_frozen(tmp_path, capsys):
    run = tmp_path / 'memory-measure' / 'study'
    run.mkdir(parents=True)
    a, b = 'a' * 8, 'b' * 8
    index = annotate_packets(run, [admission(tmp_path / 'evidence', 'run-a', 'a', [1, 2, 3, 4]),
        admission(tmp_path / 'evidence', 'run-b', 'b', [10, 11])], every=1)
    assert [(p['packet'], len(p['frames'])) for p in index['packets']] == [('packet-01', 4), ('packet-02', 2)]
    listed = {'ann-a': {'packet-01': [dict(fact='The lever opens the gate', frames=[f'{a}-1']), dict(fact='Only A saw this', frames=[f'{a}-2']),
                dict(fact='The lever opens the gate', frames=[f'{a}-3'])],
            'packet-02': [dict(fact='Water is north', frames=[f'{b}-1'])]},
        'ann-b': {'packet-01': [dict(fact='Pulling the lever opens a gate', frames=[f'{a}-1', f'{a}-2'])],
            'packet-02': [dict(fact='There is water to the north', frames=[f'{b}-1']), dict(fact='Only B saw this', frames=[f'{b}-2'])]}}
    for name, packets in listed.items():
        for packet, entries in packets.items():
            save(run / 'annotations' / name / f'{packet}.json', dict(packet=packet, entries=entries))
    matches = save(tmp_path / 'matches.json', dict(matches=[['packet-01#1', 'packet-01#1'], ['packet-01#3', 'packet-01#1'],
        ['packet-02#1', 'packet-02#1']], groups='the lead\'s own note'))
    assert main(['items', str(run), '--annotators', 'ann-a', 'ann-b', '--list']) == 0
    assert 'ann-a packet-01#2: Only A saw this' in capsys.readouterr().out and not (run / 'annotated-facts.json').exists()
    value = build_items(run, ['ann-a', 'ann-b'], matches)
    assert [(i['id'], i['text'], i['first_frame'], i['frames']) for i in value['facts']] == [
        ('seen-01', 'The lever opens the gate', f'{a}-1', [f'{a}-1', f'{a}-2', f'{a}-3']), ('seen-02', 'Water is north', f'{b}-1', [f'{b}-1'])]
    assert 'Only' not in json.dumps(value['facts'])  # each was listed by one annotator only
    assert value['counts'] == {'ann-a': dict(entries=4, in_a_fact=3, dropped=1), 'ann-b': dict(entries=3, in_a_fact=2, dropped=1)}
    assert value['sha256'] == (run / 'annotated-facts.json.sha256').read_text().strip() and value['schema'] == 'annotated-facts/1'
    assert (run / value['facts'][0]['first_frame_file']).read_bytes() == png(1)
    with pytest.raises(MeasureError, match='frozen'):
        build_items(run, ['ann-a', 'ann-b'], matches)
    (run / 'annotated-facts.json').unlink()
    (run / 'annotated-facts.json.sha256').unlink()
    save(run / 'annotations' / 'ann-b' / 'packet-02.json', dict(packet='packet-02', entries=[dict(fact='x', frames=[f'{a}-1'])]))
    with pytest.raises(MeasureError, match='outside its packet'):
        build_items(run, ['ann-a', 'ann-b'], matches)
    save(run / 'annotations' / 'ann-b' / 'packet-02.json', dict(packet='packet-02', entries=[dict(place='Attic', what='rope', frames=[f'{b}-1'])]))
    with pytest.raises(MeasureError, match='entry 1 fact'):  # an entry of a spot and what lies there, the old shape, is not read
        build_items(run, ['ann-a', 'ann-b'], matches)


# --- the facts to judge and the two kinds of packet -----------------------------------------------------------------------

def test_use_packets_show_route_briefing_reminders_and_what_the_player_stated(tmp_path):
    run = packed(tmp_path)
    mapping = mapping_of(run)
    assert (mapping['schema'], mapping['kind'], mapping['seed']) == ('judge-mapping/2', 'use', 7)
    assert mapping['facts_sha256'] == memory_measure.file_sha256(tmp_path / 'facts.json')
    assert [(p['window'], p['start'], p['actor'], p['facts']) for p in mapping['packets']] == [
        ('run-e/001:1-8', 'run-e', '001', {'index-1': 'index', 'lead-1': 'lead', 'lead-2': 'lead', 'read-1': 'read'}),
        ('run-f/001:1-5', 'run-f', '001', {'index-1': 'index', 'lead-1': 'lead', 'lead-2': 'lead', 'read-1': 'read'}),
        ('run-g/001:1-3', 'run-g', '001', {'lead-1': 'lead', 'read-2': 'read'})]
    assert sorted(p.name for p in (run / 'judge-packets').iterdir()) == sorted(p['packet'] for p in mapping['packets'])
    first = run / 'judge-packets' / mapping['packets'][0]['packet']
    assert sorted(str(p.relative_to(first)) for p in first.rglob('*') if p.is_file()) == sorted(['manifest.json', 'instructions.md',
        'facts.json', 'delivered.json', *(f'frames/f{number:03d}.png' for number in range(1, 8))])
    assert (first / 'instructions.md').read_text() == JUDGE_INSTRUCTIONS['use']
    shown = json.loads((first / 'facts.json').read_text())['facts']
    assert shown[1] == dict(id='lead-1', text='A useful observed fact.', route='lead', available_from='f001') and 'held-1' not in json.dumps(shown)  # withheld: never shown
    assert json.loads((first / 'delivered.json').read_text()) == dict(briefing='BRIEFING-MARK lead-1 lead-2',
        reminders=[dict(text='REMINDER-MARK', decision=3)])
    manifest = json.loads((first / 'manifest.json').read_text())
    assert (manifest['schema'], manifest['labels'], manifest['holds']) == ('judge-packet/2', list(judge.USE_LABELS), list(judge.HOLDS))
    assert [(row['frame'], row['decision']) for row in manifest['frames']][:4] == [('f001', 1), ('f002', 2), ('f003', 3), ('f004', 5)]
    assert manifest['frames'][3]['stated_before'] == [dict(tool='computer_input', intent='INTENT-MARK 5', cites=['CITES-MARK'])]
    assert list(mapping['packets'][0]['frames'].values())[:2] == ['eeeeeeee-1', 'eeeeeeee-2']
    for packet in mapping['packets']:  # no admission, source ID, record, report or arm in what a judge reads
        for hidden in (b'run-e', b'run-f', b'run-g', b'eeeeeeee', b'ffffffff', b'SECRET', b'mapping', b'arm', b'withheld'):
            assert hidden not in packet_text(run / 'judge-packets' / packet['packet']).replace(b'harm', b'')
    with pytest.raises(MeasureError, match='made once'):
        fact_packets(run, evidence(tmp_path / 'again'), tmp_path / 'facts.json', 'use')


def test_a_use_packet_leaves_out_a_fact_that_reached_the_player_after_its_window(tmp_path):
    runs = evidence(tmp_path, size=(750, 400))
    run = tmp_path / 'memory-measure' / 'narrow'
    run.mkdir(parents=True)
    fact_packets(run, runs[:1], save(tmp_path / 'facts.json', dict(FACTS, admissions={'run-e': FACTS['admissions']['run-e']})),
        'use', budget=3600, every=1, seed=1)
    windows = mapping_of(run)['packets']
    assert len(windows) > 1 and windows[0]['last'] < 6  # read-1 was read at decision 6
    assert 'read-1' not in windows[0]['facts'] and windows[-1]['facts']['read-1'] == 'read'
    delivered = [json.loads((run / 'judge-packets' / w['packet'] / 'delivered.json').read_text())['reminders'] for w in windows]
    assert delivered[-1] == [dict(text='REMINDER-MARK', decision=None)]  # it arrived before the last window and stays in the history


def test_a_blind_packet_holds_frames_inputs_and_fact_text_only(tmp_path):
    """The benefit measure's packets: nothing delivered or stated may leak, and nothing may tell a delivered fact
    from a withheld one. The same fixture's use packets hold every one of these markers."""
    use, blind = packed(tmp_path / 'use'), packed(tmp_path / 'blind', 'blind')
    leaks = (b'BRIEFING-MARK', b'REMINDER-MARK', b'INTENT-MARK', b'CITES-MARK', b'stated_before', b'briefing', b'reminder',
        b'delivered', b'route', b'"lead"', b'"read"', b'"index"', b'withheld', b'intent', b'cites')
    held = b''.join(packet_text(use / 'judge-packets' / packet['packet']) for packet in mapping_of(use)['packets'])
    for leak in leaks[:10]:
        assert leak in held, leak  # the check below is not passing on an empty fixture
    mapping = mapping_of(blind)
    assert mapping['kind'] == 'blind'
    for packet in mapping['packets']:
        directory = blind / 'judge-packets' / packet['packet']
        words = packet_text(directory)
        for leak in (*leaks, b'decision', *(identity.encode() for identity in packet['facts'])):
            assert leak not in words, leak
        assert sorted(p.name for p in directory.iterdir()) == ['facts.json', 'frames', 'instructions.md', 'manifest.json']
        assert (directory / 'instructions.md').read_text() == JUDGE_INSTRUCTIONS['blind']
        shown = json.loads((directory / 'facts.json').read_text())['facts']
        assert all(set(row) == {'id', 'text'} for row in shown) and {row['id'] for row in shown} == set(packet['fact_ids'])
        rows = json.loads((directory / 'manifest.json').read_text())['frames']
        assert all(set(row) == {'frame', 'file', 'sha256', 'inputs_before'} for row in rows) and rows[0]['inputs_before'] == ['k1']
    # the route is known to the tooling alone, withheld facts included
    assert mapping['packets'][0]['facts'] == {'held-1': 'withheld', 'index-1': 'index', 'lead-1': 'lead', 'lead-2': 'lead', 'read-1': 'read'}


def test_a_blind_packet_shows_every_fact_in_every_window(tmp_path):
    """A fact that appeared only from the decision it was read at would be known to be delivered."""
    runs = evidence(tmp_path, size=(750, 400))
    run = tmp_path / 'memory-measure' / 'narrow'
    run.mkdir(parents=True)
    fact_packets(run, runs[:1], save(tmp_path / 'facts.json', dict(FACTS, admissions={'run-e': FACTS['admissions']['run-e']})),
        'blind', budget=3600, every=1, seed=1)
    windows = mapping_of(run)['packets']
    assert len(windows) > 1 and all(sorted(w['facts']) == ['held-1', 'index-1', 'lead-1', 'lead-2', 'read-1'] for w in windows)


def test_judge_packets_are_written_in_shuffled_name_order(tmp_path, monkeypatch):
    made, real = [], memory_measure.seal_packet
    monkeypatch.setattr(memory_measure, 'seal_packet', lambda directory, *rest: made.append(directory.name) or real(directory, *rest))
    lineage = [packet['packet'] for packet in mapping_of(packed(tmp_path))['packets']]
    assert made == sorted(lineage) and made != lineage  # the mapping keeps lineage order; the disk does not


@pytest.mark.parametrize('change, message', [
    (lambda value: value.update(schema='judged-facts/0'), 'no other version is read'),
    (lambda value: value['admissions'].update({'run-z': {}}), 'does not select: run-z'),
    (lambda value: value['admissions']['run-e'].update({'009': {}}), 'must map its actors'),
    (lambda value: value['admissions']['run-e']['001'].update(index=[fact('lead-1')]), 'listed more than once'),
    (lambda value: value['admissions']['run-e']['001'].update(annotated=[fact('x')]), 'expected the keys'),
    (lambda value: value['admissions']['run-e']['001'].update(lead=[dict(id='x', text='')]), 'must be a non-empty string'),
    (lambda value: value['admissions']['run-e']['001'].update(lead=[dict(id='x', text='t', route='lead')]), 'a fact is'),
    (lambda value: value['admissions']['run-e']['001'].update(read=[fact('x', from_decision=0)]), 'from_decision'),
    (lambda value: value['admissions']['run-e']['001'].update(reminders=[dict(text='t')]), 'reminders are'),
    (lambda value: value.update(admissions={'run-e': {'001': dict(briefing='only')}}), 'names no fact')])
def test_a_facts_file_that_does_not_fit_the_format_is_refused(tmp_path, change, message):
    value = json.loads(json.dumps(FACTS))
    change(value)
    run = tmp_path / 'memory-measure' / 'study'
    run.mkdir(parents=True)
    with pytest.raises(MeasureError, match=message):
        fact_packets(run, evidence(tmp_path), save(tmp_path / 'facts.json', value), 'use')
    assert not (run / 'judge-packets').exists() and not (run / 'private').exists()


def test_the_held_out_lineage_is_refused(tmp_path, capsys):
    held = admission(tmp_path / '522-held-out' / 'computer-sessions', 'run-h', 'h', [1, 2])
    with pytest.raises(MeasureError, match='held-out lineage is not read'):
        recorded_frames([held])
    run = tmp_path / 'memory-measure' / 'study'
    facts = save(tmp_path / 'facts.json', dict(schema='judged-facts/1', admissions={'run-h': {'001': dict(lead=[fact('x')])}}))
    assert main(['packets', 'annotate', str(run), '--runs', str(held)]) == 2 and not run.exists()
    assert main(['packets', 'blind', str(run), '--runs', str(held), '--facts', str(facts)]) == 2 and not run.exists()
    assert 'held-out' in capsys.readouterr().err


# --- judge events -----------------------------------------------------------------------------------------------------

def test_the_judge_event_validator_reads_version_2_only(tmp_path):
    use = judge.FactUseVerdict('run:1-2', 'fact-1', 'lead', 'against', 'held', ('x-1',), 'judge-a', 'model-x', 'p', '0' * 64)
    anchor = judge.AnchorVerdict('run:1-2', 'item-01', 'missed', ('x-1',), 'judge-a', 'model-x', 'p', '0' * 64)
    assert judge.parse(judge.envelope(use)) == use and judge.parse(judge.envelope(anchor)) == anchor
    assert (judge.envelope(use)['schema'], judge.envelope(use)['kind'], judge.envelope(anchor)['kind']) == (
        'judge-events/2', 'fact_use_verdict', 'anchor_verdict')
    # the measure gate's format: the same anchor payload under judge-events/1 and its kind is refused, not converted
    old = dict(judge.envelope(anchor), schema='judge-events/1', kind='known_item_verdict')
    with pytest.raises(EvaluationError, match='no other version is read'):
        judge.parse(old)
    with pytest.raises(EvaluationError):
        judge.parse(dict(judge.envelope(anchor), schema='judge-events/1'))
    for change in (dict(source='human'), dict(confidence=0.9), dict(kind='milestone'), dict(extra=1)):
        with pytest.raises(EvaluationError):
            judge.parse(dict(judge.envelope(use), **change))
    for change in (dict(label='straight'), dict(label='maybe'), dict(holds='true'), dict(route='briefing'), dict(cited_frames=[]),
            dict(packet_sha256='abc'), dict(judge=''), dict(note='x'), dict(window='')):
        with pytest.raises(EvaluationError):
            judge.parse(dict(judge.envelope(use), payload=dict(judge.envelope(use)['payload'], **change)))
    for label in judge.APPLIED:  # each says the fact mattered, and must show where
        with pytest.raises(EvaluationError, match='must cite at least one frame'):
            judge.FactUseVerdict('w', 'f', 'lead', label, 'held', (), 'judge-a', 'model-x', 'p', '0' * 64)
    for label in ('did_not_apply', 'cannot_tell'):
        judge.FactUseVerdict('w', 'f', 'withheld', label, 'cannot_tell', (), 'judge-a', 'model-x', 'p', '0' * 64)
    for change in (dict(label='in_line'), dict(holds='held'), dict(route='lead')):  # an anchor verdict is the gate's question only
        with pytest.raises(EvaluationError):
            judge.parse(dict(judge.envelope(anchor), payload=dict(judge.envelope(anchor)['payload'], **change)))
    judge.write_events(tmp_path / 'one.jsonl', [use])
    with pytest.raises(FileExistsError):
        judge.write_events(tmp_path / 'one.jsonl', [use])
    with pytest.raises(EvaluationError, match='more than once'):
        judge.write_events(tmp_path / 'two.jsonl', [use, use])
    with pytest.raises(EvaluationError, match='one kind'):
        judge.write_events(tmp_path / 'three.jsonl', [use, anchor])
    with pytest.raises(EvaluationError, match='one kind'):
        judge.read_events(tmp_path / 'one.jsonl', judge.ANCHOR)
    # an evaluation record never holds a judge event, so the viewer, which serves records only, cannot show one
    with pytest.raises(ValueError, match='unknown event source'):
        EventRow(1, 1, 'milestone', 'judge', None, {})


def test_events_carry_the_route_the_tooling_set_and_never_one_from_the_answer(tmp_path):
    run = packed(tmp_path)

    def claim_a_route(value):
        for row in value['answers']:
            row['route'] = 'withheld'

    events = judge_events(run, 'judge-a', 'model-x', answers(run, 'judge-a', change=claim_a_route))
    assert [(e.window, e.fact, e.route, e.label, e.holds) for e in events][:3] == [
        ('run-e/001:1-8', 'index-1', 'index', 'did_not_apply', 'cannot_tell'), ('run-e/001:1-8', 'lead-1', 'lead', 'in_line', 'held'),
        ('run-e/001:1-8', 'lead-2', 'lead', 'found_again', 'held')]
    assert {event.route for event in events} == {'lead', 'read', 'index'}
    packet = mapping_of(run)['packets'][0]
    second = events[1]
    assert (second.cited_frames, second.judge, second.model, second.packet, second.packet_sha256) == (
        ('eeeeeeee-1',), 'judge-a', 'model-x', packet['packet'], packet['sha256'])
    line = json.loads((run / 'events' / 'judge-a.jsonl').read_text().splitlines()[0])
    assert (line['schema'], line['kind'], line['source'], line['confidence']) == ('judge-events/2', 'fact_use_verdict', 'judge', None)
    assert 'note' not in line['payload'] and judge.read_events(run / 'events' / 'judge-a.jsonl', judge.FACT_USE) == events
    assert len(judge_events(run, 'judge-c', 'model-x', answers(run, 'judge-c'))) == 4  # a third judge answers only some packets
    with pytest.raises(MeasureError, match='written once'):
        judge_events(run, 'judge-a', 'model-x', answers(run, 'judge-a'))


@pytest.mark.parametrize('change, message', [
    (lambda value: value['answers'].pop(), 'no answer for'),
    (lambda value: value['answers'][0].update(label='against', frames=['f099']), 'cites a frame outside the packet'),
    (lambda value: value['answers'][0].update(label='against', frames=['eeeeeeee-1']), 'cites a frame outside the packet'),
    (lambda value: value['answers'].append(dict(value['answers'][0])), 'answered 2 times'),
    (lambda value: value['answers'][0].update(label='straight'), 'is not one of in_line, against, found_again, did_not_apply, cannot_tell'),
    (lambda value: value['answers'][0].update(label='found_again', frames=[]), 'must cite a frame'),
    (lambda value: value['answers'][0].update(holds='maybe'), 'is not one of held, stale_or_false, cannot_tell'),
    (lambda value: value['answers'][0].pop('holds'), 'is not one of held, stale_or_false, cannot_tell'),
    (lambda value: value['answers'].append(dict(fact='fact-9', label='cannot_tell', holds='cannot_tell')), 'is not a fact of the packet'),
    (lambda value: value.update(packet='s0000000000'), 'a packet of this run')])
def test_a_judge_answer_that_does_not_fit_its_packet_is_refused(tmp_path, change, message):
    run = packed(tmp_path)
    with pytest.raises(MeasureError, match=message):
        judge_events(run, 'judge-a', 'model-x', answers(run, 'judge-a', change=change))
    assert not (run / 'events').exists()


def test_a_changed_packet_and_a_bad_judge_name_are_refused(tmp_path):
    run = packed(tmp_path)
    files = answers(run, 'judge-a')
    with pytest.raises(MeasureError, match='lowercase'):
        judge_events(run, '../x', 'model-x', files)
    packet = json.loads(files[0].read_text())['packet']
    manifest = run / 'judge-packets' / packet / 'manifest.json'
    manifest.write_text(manifest.read_text() + ' ')
    with pytest.raises(MeasureError, match='not the packet that was made'):
        judge_events(run, 'judge-a', 'model-x', files)


@pytest.mark.parametrize('value', [[1, 2], dict(packet=['x'], answers=[]), dict(packet='PACKET', answers='none'),
    dict(packet='PACKET', answers=[dict(fact=['lead-1'], label='against')]), dict(packet='PACKET', answers=[['lead-1', 'against']])])
def test_json_of_another_shape_is_refused_without_a_traceback(tmp_path, capsys, value):
    run = packed(tmp_path)
    answer = save(tmp_path / 'answer.json', json.loads(json.dumps(value).replace('PACKET', mapping_of(run)['packets'][0]['packet'])))
    assert main(['events', str(run), '--judge', 'judge-a', '--model', 'model-x', str(answer)]) == 2
    assert capsys.readouterr().err.startswith('memory_measure: ') and not (run / 'events').exists()
    save(run / 'adjudicated.json', [])
    assert main(['measure', str(run)]) == 2
    assert 'does not have the expected shape' in capsys.readouterr().err
    save(run / 'private' / 'judge-mapping.json', dict(schema='judge-mapping/1', packets=[]))  # the measure gate's mapping
    assert main(['agreement', str(run), '--judges', 'judge-a', 'judge-b']) == 2
    assert 'no other version is read' in capsys.readouterr().err


# --- isolation ----------------------------------------------------------------------------------------------------------

def test_nothing_the_judge_produces_reaches_the_curator_trace_or_the_player(tmp_path):
    """The curator's trace is `harness.trace.projection.project` over named session directories, by allowlist; a
    run package freezes a closed set of files (`tools.campaign_package.FILES`). Neither names the measure's
    directory, and the import contracts forbid the player, the curator and the trace from importing evaluation or
    tools. The projection is run here with judge output planted inside the session it projects."""
    from test_trace_projection import make_session
    run = judged(tmp_path)
    agreement(run, ['judge-a', 'judge-b'], 'judge-c')
    measure(run, seed=1, draws=50)
    session = make_session(tmp_path / 'sessions')
    for name in ('events/judge-a.jsonl', 'adjudicated.json', 'measure.json'):
        planted = (run / name).read_bytes()
        (session / 'memory-measure' / 'study' / name).parent.mkdir(parents=True, exist_ok=True)
        (session / 'memory-measure' / 'study' / name).write_bytes(planted)
        (session / 'actors' / '001' / Path(name).name).write_bytes(planted)
    project([session], tmp_path / 'trace')
    written = b''.join(p.read_bytes() for p in (tmp_path / 'trace').rglob('*') if p.is_file())
    for word in (b'fact_use_verdict', b'judge', b'memory-use', b'adjudicated'):
        assert word not in written
    root = Path(memory_measure.__file__).resolve().parents[1]
    readers = [*(root / 'harness' / 'player').rglob('*.py'), *(root / 'harness' / 'curator').rglob('*.py'),
        *(root / 'harness' / 'trace').rglob('*.py'), *(root / 'harness').glob('player_*.py'),
        *(root / 'tools' / 'curator_host').glob('*.*'), *(root / 'tools' / 'player_host').glob('*.mjs'),
        root / 'tools' / 'campaign_package.py', root / 'tools' / 'campaign_player.py', root / 'tools' / 'campaign_run.py']
    assert len(readers) > 20
    for path in readers:
        source = path.read_text(errors='replace')
        for word in ('memory-measure', 'memory_measure', 'judge-events', 'evaluation.core.judge', 'fact_use_verdict',
                'anchor_verdict', 'judge-adjudicated', 'memory-use/'):
            assert word not in source, f'{path} names {word}'


def test_every_output_is_written_under_the_measure_run_directory_only(tmp_path, capsys):
    run = judged(tmp_path)
    before = {path for path in tmp_path.rglob('*') if not path.is_relative_to(run)}
    agreement(run, ['judge-a', 'judge-b'], 'judge-c')
    measure(run, seed=1, draws=50)
    assert {path for path in tmp_path.rglob('*') if not path.is_relative_to(run)} == before
    facts = str(tmp_path / 'facts.json')
    for elsewhere in (tmp_path / 'evidence' / 'run-e', tmp_path / 'knowledge' / 'study'):  # a session, a store: any other parent
        assert main(['packets', 'use', str(elsewhere), '--runs', str(tmp_path / 'evidence' / 'run-f'), '--facts', facts]) == 2
        assert main(['measure', str(elsewhere)]) == 2 and main(['agreement', str(elsewhere), '--judges', 'a', 'b']) == 2
        assert 'must sit in a directory named memory-measure' in capsys.readouterr().err
    assert not (tmp_path / 'knowledge').exists() and not (tmp_path / 'evidence' / 'run-e' / 'judge-packets').exists()


def test_the_owner_page_and_the_comparison_between_arms_are_gone(capsys):
    for name in ('label_server', 'LabelStore', 'PAGE', 'draw_sample', 'draw_engaged', 'simulate', 'p_values', 'APPENDIX_ROWS',
            'simulate_commands', 'judge_packets'):
        assert not hasattr(memory_measure, name), name
    for command in (['label-server', 'x'], ['sample', 'x'], ['simulate'], ['packets', 'judge', 'x', '--runs', 'y']):
        with pytest.raises(SystemExit):
            main(command)
    capsys.readouterr()


# --- adjudication and the standing use measures ---------------------------------------------------------------------------

def test_describe_names_keys_text_and_repeats():
    assert describe([[dict(type='key', key='RIGHT', modifiers=[])], [dict(type='key', key='RIGHT', modifiers=[]),
        dict(type='key', key='a', modifiers=['ctrl']), dict(type='text', text='hi'), dict(type='click', x=3, y=4)]]) \
        == 'RIGHT ×2 ctrl+a "hi" click at 3,4'


def test_kappa_and_the_exact_interval_on_hand_computed_tables():
    # 20 both yes, 5 yes/no, 10 no/yes, 15 both no: observed 0.7, chance 0.5 * 0.6 + 0.5 * 0.4 = 0.5, kappa 0.4
    first = [0] * 25 + [1] * 25
    second = [0] * 20 + [1] * 5 + [0] * 10 + [1] * 15
    assert cohen_kappa(first, second, 2) == pytest.approx(0.4)
    assert cohen_kappa([0, 1, 2, 3], [0, 1, 2, 3], 4) == pytest.approx(1.0)
    assert cohen_kappa([0, 0, 0], [0, 0, 0], 4) is None  # chance agreement is certain
    assert cohen_kappa([], [], 4) is None
    assert binomial_interval(18, 20) == pytest.approx([0.6830, 0.9877], abs=5e-4)  # Clopper-Pearson
    assert binomial_interval(20, 20) == pytest.approx([0.8316, 1.0], abs=5e-4)
    assert binomial_interval(0, 20)[0] == 0.0


def test_the_bootstrap_resamples_whole_starts_and_not_pairs():
    """Two starts with the same rate: every resample of starts gives that rate, so the interval has no width. A
    bootstrap over the 40 pairs would spread it. One start alone gives no interval."""
    rows = [dict(start=start, hit=number % 2 == 0) for start in ('s1', 's2') for number in range(20)]
    boot = StartBootstrap([row['start'] for row in rows], seed=1, draws=500)
    hits, count = boot.sums(rows, lambda row: float(row['hit'])), boot.sums(rows, lambda row: 1.0)
    assert list(hits) == [10, 10] and boot.interval(memory_measure._ratio, hits, count) == [0.5, 0.5]
    uneven = [dict(start='s1', hit=True)] * 10 + [dict(start='s2', hit=False)] * 10 + [dict(start='s3', hit=True)] * 5
    boot = StartBootstrap([row['start'] for row in uneven], seed=1, draws=2000)
    low, high = boot.interval(memory_measure._ratio, boot.sums(uneven, lambda row: float(row['hit'])), boot.sums(uneven, lambda row: 1.0))
    assert low == 0.0 and high == 1.0  # all of one start or none of it: the clusters, not the pairs, set the spread
    alone = StartBootstrap(['s1'] * 5, seed=1, draws=100)
    assert alone.interval(memory_measure._ratio, np.array([2.0]), np.array([5.0])) is None


def test_agreement_adjudicates_labels_and_holds_with_a_third_judge_on_disputes(tmp_path, capsys):
    run = packed(tmp_path)
    for name in ('judge-a', 'judge-b', 'judge-c', 'judge-d'):
        judge_events(run, name, 'model-x', answers(run, name))
    value = agreement(run, ['judge-a', 'judge-b'])
    assert (value['pairs'], value['disputed'], value['unresolved'], value['dispute_rate']) == (10, 1, 2, 0.1)
    disputed = next(packet['packet'] for packet in mapping_of(run)['packets'] if packet['start'] == 'run-f')
    assert value['third_judge_packets'] == [disputed]
    # the first two judges differ on `holds` of one pair whose label they share: with no third verdict it is cannot_tell
    assert next(row['holds'] for row in value['rows'] if (row['start'], row['fact']) == ('run-f', 'lead-2')) == 'cannot_tell'
    with pytest.raises(MeasureError, match='2 pairs are not adjudicated'):
        measure(run)
    value = agreement(run, ['judge-a', 'judge-b'], 'judge-c')
    rows = {(row['start'], row['fact']): row for row in value['rows']}
    assert value == json.loads((run / 'adjudicated.json').read_text()) and value['schema'] == 'judge-adjudicated/2'
    assert (value['unresolved'], value['third_alone'], value['kind']) == (0, 0, 'use')
    assert (rows[('run-f', 'lead-1')]['label'], rows[('run-f', 'lead-1')]['by']) == ('against', 'third')
    assert rows[('run-f', 'lead-1')]['labels'] == {'judge-a': 'against', 'judge-b': 'in_line', 'judge-c': 'against'}
    # the first two judges differ on `holds` alone: the third sides with one of them, which settles it
    assert (rows[('run-f', 'lead-2')]['label'], rows[('run-f', 'lead-2')]['by'], rows[('run-f', 'lead-2')]['holds']) == ('in_line', 'agreement', 'held')
    assert rows[('run-e', 'read-1')]['route'] == 'read' and rows[('run-e', 'read-1')]['window'] == 'run-e/001:1-8'
    codes = [[judge.USE_LABELS.index(VERDICTS[name][key][0]) for key in VERDICTS['judge-a']] for name in ('judge-a', 'judge-b')]
    assert value['kappa'] == pytest.approx(cohen_kappa(*codes, 5)) and value['agreement'] == pytest.approx(0.9)
    # a third judge whose label matches neither of the first two: its label is taken and the pair is marked
    alone = agreement(run, ['judge-a', 'judge-b'], 'judge-d')
    rows = {(row['start'], row['fact']): row for row in alone['rows']}
    assert (rows[('run-f', 'lead-1')]['label'], rows[('run-f', 'lead-1')]['by'], alone['third_alone']) == ('found_again', 'third_alone', 1)
    assert main(['agreement', str(run), '--judges', 'judge-a', 'judge-b', '--third', 'judge-d']) == 0
    out = capsys.readouterr().out
    assert 'third_alone): 1' in out and 'run-f/001:1-5 / lead-1: judge-a against, judge-b in_line, judge-d found_again' in out
    (run / 'events' / 'judge-b.jsonl').write_text('\n'.join((run / 'events' / 'judge-b.jsonl').read_text().splitlines()[:-1]) + '\n')
    with pytest.raises(MeasureError, match='1 pairs lack a verdict'):
        agreement(run, ['judge-a', 'judge-b'], 'judge-c')


def test_the_use_measures_carry_the_judges_agreement_dispute_rate_and_an_interval_over_starts(tmp_path, capsys):
    run = judged(tmp_path)
    agreement(run, ['judge-a', 'judge-b'], 'judge-c')
    report = measure(run, seed=5, draws=2000)
    assert report == json.loads((run / 'measure.json').read_text()) and report['schema'] == 'memory-use/1'
    assert 'not corrected against a human truth' in report['not_corrected']
    assert report['bootstrap'] == dict(seed=5, draws=2000, starts=3, note=memory_measure.BOOTSTRAP_NOTE)
    assert report['labels_by_route']['lead'] == dict(pairs=5, in_line=2, against=1, found_again=1, did_not_apply=0, cannot_tell=1)
    assert report['labels_by_route']['withheld']['pairs'] == 0
    measures = report['measures']
    # lead pairs: e in_line, e found_again, f against (third), f in_line, g cannot_tell: four applied
    use = measures['use_rate_delivered']
    assert (use['numerator'], use['denominator'], use['value']) == (2, 4, 0.5)
    assert (measures['rediscovery']['numerator'], measures['rediscovery']['denominator']) == (1, 4)
    # in line with a fact it had: e lead-1 (held), e read-1 (stale), f lead-2 (held), g read-2 (held)
    stale = measures['stale_or_false_acted']
    assert (stale['numerator'], stale['denominator'], stale['value']) == (1, 4, 0.25)
    # three facts read (e read-1, f read-1, g read-2); the player acted in line with two of them
    read = measures['read_then_in_line']
    assert (read['numerator'], read['denominator']) == (2, 3) and read['value'] == pytest.approx(2 / 3)
    # beside each rate: the first two judges on the pairs it is taken from
    lead = [key for key in VERDICTS['judge-a'] if key[1].startswith('lead')]
    codes = [[judge.USE_LABELS.index(VERDICTS[name][key][0]) for key in lead] for name in ('judge-a', 'judge-b')]
    beside = use['judges_route']
    assert (beside['pairs'], beside['on'], beside['agreement'], beside['dispute_rate']['value']) == (5, 'label', 0.8, 0.2)
    assert beside['kappa']['value'] == pytest.approx(cohen_kappa(*codes, 5))
    assert measures['rediscovery']['judges_route'] == beside
    assert (read['judges_route']['pairs'], read['judges_route']['dispute_rate']['value'], read['judges_route']['kappa']['value']) == (3, 0.0, 1.0)
    # the stale rate rests on `holds`: the two judges gave it differently once in ten pairs
    assert (stale['judges_route']['pairs'], stale['judges_route']['on'], stale['judges_route']['agreement']) == (10, 'holds', 0.9)
    assert report['judges_overall']['pairs'] == 10 and report['judges_overall']['dispute_rate']['value'] == 0.1
    # an interval over the three starts. The use rate is one half in each start that has an applied lead fact, so
    # resampling starts cannot move it; the other rates differ between starts.
    assert use['interval'] == [0.5, 0.5]
    for part in (measures['rediscovery'], stale, read):
        low, high = part['interval']
        assert 0 <= low <= part['value'] <= high <= 1 and low < high
        assert part['judges_route']['dispute_rate']['interval'] is not None and part['definition']
    assert measure(run, seed=5, draws=2000) == report  # the seed fixes it
    assert main(['measure', str(run), '--seed', '5', '--draws', '200']) == 0
    out = capsys.readouterr().out
    assert out.startswith('These rates rest on the adjudicated labels of model judges')
    assert 'use_rate_delivered: 2 of 4 = 0.500 (95% interval over starts' in out
    assert 'first two judges on 5 pairs (label): agreement 0.800, kappa' in out and 'dispute rate 0.200' in out


def test_one_start_gives_rates_without_intervals_and_a_blind_run_gives_no_use_measure(tmp_path):
    run = tmp_path / 'memory-measure' / 'one'
    run.mkdir(parents=True)
    only = dict(FACTS, admissions={'run-g': FACTS['admissions']['run-g']})
    fact_packets(run, evidence(tmp_path)[2:], save(tmp_path / 'one.json', only), 'use', every=1, seed=2)
    for name in ('judge-a', 'judge-b'):
        judge_events(run, name, 'model-x', answers(run, name, {key: value for key, value in VERDICTS[name].items() if key[0] == 'run-g'}))
    agreement(run, ['judge-a', 'judge-b'])
    report = measure(run, seed=1, draws=100)
    read = report['measures']['read_then_in_line']
    assert (read['value'], read['interval'], read['judges_route']['kappa']['interval'], report['bootstrap']['starts']) == (1.0, None, None, 1)
    use = report['measures']['use_rate_delivered']  # the one lead pair is cannot_tell: nothing applied, so no rate
    assert (use['numerator'], use['denominator'], use['value'], use['interval']) == (0, 0, None, None)
    blind = judged(tmp_path / 'blind', 'blind')
    value = agreement(blind, ['judge-a', 'judge-b'], 'judge-c')
    assert value['kind'] == 'blind' and value['pairs'] == 13
    report = measure(blind, seed=1, draws=100)
    assert report['measures'] is None and report['labels_by_route']['withheld'] == dict(pairs=3, in_line=0, against=0,
        found_again=3, did_not_apply=0, cannot_tell=0)
    assert 'not taken from blind packets' in memory_measure.render_measure(report)


# Review regressions for R-FALSE-CLAIM: a small fixture per claim; no provider or gameplay cost.
@pytest.mark.parametrize('route', ['lead', 'read'])
@pytest.mark.parametrize('label', judge.APPLIED)
def test_action_before_delivery_or_read_cannot_count(tmp_path, route, label):
    run = tmp_path / 'memory-measure' / 'timed'
    facts = dict(schema='judged-facts/1', admissions={'run-e': {'001': {route: [fact('late', from_decision=6)]}}})
    fact_packets(run, evidence(tmp_path)[:1], save(tmp_path / 'late.json', facts), 'use', every=1, seed=3)
    packet = mapping_of(run)['packets'][0]
    directory = run / 'judge-packets' / packet['packet']
    listed = json.loads((directory / 'facts.json').read_text())['facts'][0]
    assert listed['available_from'] == 'f006'
    assert 'Earlier action does' in (directory / 'instructions.md').read_text()
    answer = save(run / 'answer.json', dict(packet=packet['packet'], answers=[dict(fact='late', label=label,
        holds='held', frames=['f005'])]))
    with pytest.raises(MeasureError, match='before available_from f006'):
        judge_events(run, 'judge-a', 'model-x', [answer])
    assert not (run / 'events').exists()
    # Evidence only of action before the read gets no credit in the standing measure.
    value = json.loads(answer.read_text())
    value['answers'][0].update(label='did_not_apply')
    save(answer, value)
    for name in ('judge-a', 'judge-b'):
        judge_events(run, name, 'model-x', [answer])
    agreement(run, ['judge-a', 'judge-b'])
    report = measure(run, seed=3, draws=20)
    if route == 'read':
        assert (report['measures']['read_then_in_line']['numerator'],
            report['measures']['read_then_in_line']['denominator']) == (0, 1)
    # The first available frame is accepted as evidence, as are later frames.
    value['answers'][0].update(label=label, frames=['f001', 'f006'])
    save(answer, value)
    assert judge_events(run, 'judge-c', 'model-x', [answer])[0].label == label


def test_blind_ids_and_grouping_are_independent_of_routes_and_unique_per_packet(tmp_path):
    runs = evidence(tmp_path, size=(750, 400))[:1]
    entries = [dict(id='canonical-secret-a', text='A door is open.'), dict(id='canonical-secret-b', text='A tool is useful.')]
    mappings, payloads = [], []
    for number, (lead, withheld) in enumerate((entries, entries[::-1])):
        run = tmp_path / 'memory-measure' / f'blind-{number}'
        facts = dict(schema='judged-facts/1', admissions={'run-e': {'001': dict(lead=[lead], withheld=[withheld])}})
        mapping = fact_packets(run, runs, save(tmp_path / f'facts-{number}.json', facts), 'blind', budget=3600, every=1, seed=7)
        mappings.append(mapping)
        payloads.append([packet_text(run / 'judge-packets' / packet['packet']) for packet in mapping['packets']])
    assert payloads[0] == payloads[1]
    assert len(payloads[0]) > 1
    for payload in payloads[0]:
        assert b'canonical-secret' not in payload and b'decision' not in payload
    ids = [set(packet['fact_ids']) for packet in mappings[0]['packets']]
    assert len(set.union(*ids)) == sum(map(len, ids))


@pytest.mark.parametrize('kind', ['use', 'blind', 'annotate'])
def test_token_accounting_matches_every_serialized_file_and_flags_oversize(tmp_path, kind):
    run = tmp_path / 'memory-measure' / 'sized'
    runs = [admission(tmp_path / 'evidence', 'run-g', 'g', [1, 2], (1500, 1500))]
    if kind == 'annotate':
        mapping = annotate_packets(run, runs, every=1, budget=3600)
        root = run / 'annotate'
    else:
        mapping = fact_packets(run, runs, save(tmp_path / 'facts.json', dict(FACTS,
            admissions={'run-g': FACTS['admissions']['run-g']})), kind, every=1, budget=3600)
        root = run / 'judge-packets'
    assert len(mapping['packets']) == 2  # an oversized decision is retained and declared
    for packet in mapping['packets']:
        directory = root / packet['packet']
        manifest = json.loads((directory / 'manifest.json').read_text())
        actual_text = sum(text_tokens(path.read_text()) for path in directory.rglob('*') if path.is_file() and path.suffix != '.png')
        estimate = manifest['budget']
        assert estimate['estimated']['text'] == actual_text
        assert estimate['estimated']['total'] == actual_text + 3000
        assert estimate['over'] == packet['over_budget'] == (actual_text + 3000 > 3600)
        assert packet['estimated_tokens'] == actual_text + 3000


def test_fixed_delivery_payload_must_leave_a_quarter_of_the_budget_for_facts(tmp_path):
    run = tmp_path / 'memory-measure' / 'fixed'
    facts = dict(schema='judged-facts/1', admissions={'run-g': {'001': dict(
        lead=[fact(f'fact-{number}') for number in range(20)], briefing='x' * 10500)}})
    with pytest.raises(MeasureError, match='less than a quarter for facts'):
        fact_packets(run, evidence(tmp_path)[2:], save(tmp_path / 'facts.json', facts), 'use', budget=6000)
    assert not (run / 'judge-packets').exists()


def test_holds_only_dispute_requires_a_third_judge_and_uses_its_own_dispute_rate(tmp_path):
    run = packed(tmp_path)
    for name in ('judge-a', 'judge-b'):
        verdicts = dict(VERDICTS['judge-a'])
        if name == 'judge-b':
            verdicts[('run-f', 'lead-2')] = ('in_line', 'stale_or_false')
        judge_events(run, name, 'model-x', answers(run, name, verdicts))
    unresolved = agreement(run, ['judge-a', 'judge-b'])
    packet = next(packet for packet in mapping_of(run)['packets'] if packet['start'] == 'run-f')
    assert (unresolved['disputed'], unresolved['dispute_rate'], unresolved['holds_disputed'],
        unresolved['holds_dispute_rate'], unresolved['unresolved']) == (0, 0, 1, 0.1, 1)
    assert unresolved['third_judge_packets'] == [packet['packet']]
    with pytest.raises(MeasureError, match='1 pairs are not adjudicated'):
        measure(run)
    judge_events(run, 'judge-c', 'model-x', answers(run, 'judge-c'))
    assert agreement(run, ['judge-a', 'judge-b'], 'judge-c')['unresolved'] == 0
    report = measure(run, seed=1, draws=20)
    assert report['judges_overall']['dispute_rate']['value'] == 0
    assert report['measures']['stale_or_false_acted']['judges_route']['dispute_rate']['value'] == 0.1


def test_rate_agreement_selects_pairs_from_either_initial_judge_before_adjudication(tmp_path):
    run = packed(tmp_path)
    for name in ('judge-a', 'judge-b', 'judge-c'):
        verdicts = dict(VERDICTS[name])
        if name == 'judge-c':
            verdicts[('run-f', 'lead-1')] = ('cannot_tell', 'held')
        judge_events(run, name, 'model-x', answers(run, name, verdicts))
    agreement(run, ['judge-a', 'judge-b'], 'judge-c')
    rates = measure(run, seed=1, draws=100)['measures']
    use = rates['use_rate_delivered']
    assert (use['denominator'], use['judges_route']['pairs'], use['judges_rate_pairs']['pairs']) == (3, 5, 4)
    assert use['judges_rate_pairs']['agreement'] == 0.75
    assert use['judges_rate_pairs']['dispute_rate']['value'] == 0.25
    assert use['judges_rate_pairs']['kappa']['value'] is not None
    stale = rates['stale_or_false_acted']
    assert (stale['denominator'], stale['judges_route']['pairs'], stale['judges_rate_pairs']['pairs']) == (4, 10, 5)
    assert stale['judges_rate_pairs']['dispute_rate']['value'] == 0.2


@pytest.mark.parametrize('target', ['instructions.md', 'frame'])
def test_answer_import_checks_packet_contents_not_just_manifest(tmp_path, target):
    run = packed(tmp_path)
    files = answers(run, 'judge-a')
    packet = mapping_of(run)['packets'][0]
    directory = run / 'judge-packets' / packet['packet']
    path = next((directory / 'frames').iterdir()) if target == 'frame' else directory / target
    path.write_bytes(path.read_bytes() + b'tampered')
    with pytest.raises(MeasureError, match='changed since the packet was made'):
        judge_events(run, 'judge-a', 'model-x', files)
    assert not (run / 'events').exists()


def test_actors_with_facts_and_no_kept_frames_are_listed_in_mapping_and_report(tmp_path):
    runs = [admission(tmp_path / 'evidence', 'run-g', 'g', [None, None])]
    run = tmp_path / 'memory-measure' / 'no-frames'
    mapping = fact_packets(run, runs, save(tmp_path / 'facts.json', dict(FACTS,
        admissions={'run-g': FACTS['admissions']['run-g']})), 'use')
    assert mapping['no_frames'] == ['run-g/001'] and mapping['packets'] == []
    (run / 'events').mkdir()
    for name in ('judge-a', 'judge-b'):
        judge.write_events(run / 'events' / f'{name}.jsonl', [])
    agreement(run, ['judge-a', 'judge-b'])
    assert measure(run, seed=1, draws=20)['no_frames'] == ['run-g/001']
    assert main(['agreement', str(run), '--judges', 'judge-a', 'judge-b']) == 0
    assert main(['measure', str(run), '--seed', '1', '--draws', '20']) == 0


def test_manifest_sizes_itself_exactly_at_budget_and_rounding_boundaries():
    for extra in range(4):
        contents = {'instructions.md': 'x' * (300 + extra)}
        for budget in range(190, 230):
            manifest = dict(schema='judge-packet/2', packet='packet', budget=memory_measure.budget_entry(budget, 0, []), frames=[])
            serialized = memory_measure.manifest_text(manifest, contents)
            actual = text_tokens(serialized) + sum(text_tokens(value) for value in contents.values())
            assert manifest['budget']['estimated']['total'] == actual
            assert manifest['budget']['over'] == (actual > budget)


def test_each_judge_event_file_pins_one_model(tmp_path):
    event = judge.FactUseVerdict('w', 'f', 'lead', 'in_line', 'held', ('frame',), 'judge-a', 'model-x', 'p', '0' * 64)
    other = judge.FactUseVerdict('other', 'f', 'lead', 'in_line', 'held', ('frame',), 'judge-a', 'model-y', 'p', '0' * 64)
    with pytest.raises(EvaluationError, match='more than one model'):
        judge.write_events(tmp_path / 'mixed.jsonl', [event, other])
    assert not (tmp_path / 'mixed.jsonl').exists()


# Round-two regressions for R-FALSE-CLAIM: sampled input provenance, honest coverage and comparable windows.
@pytest.mark.parametrize('route', ['lead', 'read'])
@pytest.mark.parametrize('read_decision', [5, 6])
@pytest.mark.parametrize('label', judge.APPLIED)
def test_sampled_inputs_from_before_or_during_a_read_cannot_count(tmp_path, route, read_decision, label):
    admission_dir = admission(tmp_path / 'evidence', 'run-timed', 't', [None, None, 1, 2, 3, 4, 5, 6, 7])
    frames, _ = recorded_frames([admission_dir])
    kept = every_nth_changed(frames['run-timed'], every=3)
    assert [frame.decision for frame in kept] == [3, 6, 9]
    assert [frame.input_decisions for frame in kept] == [(3,), (4, 5, 6), (7, 8, 9)]
    run = tmp_path / 'memory-measure' / 'sampled-timing'
    facts = dict(schema='judged-facts/1', admissions={'run-timed': {'001': {route: [fact('timed', from_decision=read_decision)]}}})
    mapping = fact_packets(run, [admission_dir], save(tmp_path / 'facts.json', facts), 'use', every=3, seed=4)
    packet = mapping['packets'][0]
    assert packet['available_from']['timed'] == 'f003'
    directory = run / 'judge-packets' / packet['packet']
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert [row['decision'] for row in manifest['frames']] == [3, 6, 9]
    assert manifest['frames'][1]['inputs_before'] == ['k4', 'k5', 'k6']
    assert manifest['frames'][2]['inputs_before'] == ['k7', 'k8', 'k9']
    assert json.loads((directory / 'facts.json').read_text())['facts'][0]['available_from'] == 'f003'
    answer = save(run / 'answer.json', dict(packet=packet['packet'], answers=[dict(fact='timed', label=label,
        holds='held', frames=['f002'])]))
    with pytest.raises(MeasureError, match='before available_from f003'):
        judge_events(run, 'judge-a', 'model-x', [answer])
    value = json.loads(answer.read_text())
    value['answers'][0]['frames'] = ['f003']
    save(answer, value)
    event = judge_events(run, 'judge-a', 'model-x', [answer])[0]
    assert event.cited_frames == ('tttttttt-9',)


def test_input_decisions_survive_missing_and_unchanged_frames(tmp_path):
    directory = admission(tmp_path, 'run-inputs', 'i', [1, 'lost', 2, 2, 3, 4, 5])
    frames, _ = recorded_frames([directory])
    kept = every_nth_changed(frames['run-inputs'], every=2)
    assert [frame.decision for frame in kept] == [1, 5, 7]
    assert [frame.input_decisions for frame in kept] == [(1,), (2, 3, 4, 5), (6, 7)]
    assert not memory_measure.available_after(kept[1], 2)
    assert memory_measure.available_after(kept[2], 2)


def test_serialized_packet_cost_evens_windows_and_preserves_decision_groups():
    frames = [Frame('run', '001', f's{number}', number, Path('x'), ()) for number in range(1, 7)]
    parts = cut(frames, lambda frame: 0, 60, packet_cost=lambda part, first, last: 10 + len(part) * 10)
    assert [len(part) for part in parts] == [3, 3]  # greedy fitting alone gives five and a short tail of one
    repeated = [Frame('run', '001', f's{number}', decision, Path('x'), ()) for number, decision in
        enumerate([1, 2, 2, 3, 4, 5, 6, 6, 6, 7])]
    parts = cut(repeated, lambda frame: 0, 45, packet_cost=lambda part, first, last: 10 + len(part) * 10)
    assert all(10 + len(part) * 10 <= 45 for part in parts)
    assert all(a[-1].decision != b[0].decision for a, b in zip(parts, parts[1:]))
    oversize = cut(repeated[5:9], lambda frame: 0, 35, packet_cost=lambda part, first, last: 10 + len(part) * 10)
    assert [len(part) for part in oversize] == [1, 3]


def test_actor_windows_are_evened_and_priced_with_the_bounds_actually_written(tmp_path, monkeypatch):
    runs = [admission(tmp_path / 'evidence', 'run-windowed', 'w', [1] * 12 + ['handoff', 2, 3, 4, 5, 6, 7], (750, 400))]
    facts = save(tmp_path / 'facts.json', dict(schema='judged-facts/1', admissions={'run-windowed': {'002': dict(
        lead=[fact('known')], reminders=[dict(decision=16, text='Remember the observation.')])}}))
    wide = tmp_path / 'memory-measure' / 'wide'
    full = fact_packets(wide, runs, facts, 'use', every=1, seed=2)['packets'][0]
    budget = full['estimated_tokens'] - 200  # five frames fit; six do not
    priced = {}
    real = memory_measure.manifest_text

    def stamp(manifest):
        return manifest['decisions'], json.dumps([{key: value for key, value in row.items() if key != 'sha256'}
            for row in manifest['frames']], sort_keys=True)

    def capture(manifest, contents, image_files=None):
        serialized = real(manifest, contents, image_files)
        if manifest.get('packet') == 's0000000000' and manifest['frames']:
            priced[stamp(manifest)] = manifest['budget']['estimated']['total']
        return serialized

    monkeypatch.setattr(memory_measure, 'manifest_text', capture)
    run = tmp_path / 'memory-measure' / 'evened'
    mapping = fact_packets(run, runs, facts, 'use', every=1, seed=2, budget=budget)
    assert [len(packet['frames']) for packet in mapping['packets']] == [3, 3]
    assert [(packet['first'], packet['last']) for packet in mapping['packets']] == [(13, 15), (16, 18)]
    for packet in mapping['packets']:
        manifest = json.loads((run / 'judge-packets' / packet['packet'] / 'manifest.json').read_text())
        assert priced[stamp(manifest)] == packet['estimated_tokens']
        assert packet['estimated_tokens'] <= budget and not packet['over_budget']


@pytest.mark.parametrize('only_late', [False, True])
def test_facts_without_any_eligible_frame_are_listed_in_mapping_and_report(tmp_path, only_late):
    runs = [admission(tmp_path / 'evidence', 'run-late', 'l', [None, None, 1, 2, 3, 4, 5, 6, 7, None])]
    read = [fact('too-late', from_decision=8), fact('after-last-frame', from_decision=10)]
    if not only_late:
        read.append(fact('shown', from_decision=5))
    facts = save(tmp_path / 'facts.json', dict(schema='judged-facts/1', admissions={'run-late': {'001': dict(read=read)}}))
    run = tmp_path / 'memory-measure' / 'late'
    mapping = fact_packets(run, runs, facts, 'use', every=3)
    expected = [dict(actor='run-late/001', fact='after-last-frame'), dict(actor='run-late/001', fact='too-late')]
    assert mapping['not_shown'] == expected
    assert mapping['no_frames'] == []
    assert {identity for packet in mapping['packets'] for identity in packet['facts']} == (set() if only_late else {'shown'})
    (run / 'events').mkdir()
    for name in ('judge-a', 'judge-b'):
        if only_late:
            judge.write_events(run / 'events' / f'{name}.jsonl', [])
        else:
            judge_events(run, name, 'model-x', answers(run, name, {('run-late', 'shown'): ('in_line', 'held')}))
    agreement(run, ['judge-a', 'judge-b'])
    report = measure(run, seed=1, draws=20)
    assert report['not_shown'] == expected
    rendered = memory_measure.render_measure(report)
    assert 'run-late/001 / too-late' in rendered and 'run-late/001 / after-last-frame' in rendered
    blind = tmp_path / 'memory-measure' / 'blind'
    blind_mapping = fact_packets(blind, runs, facts, 'blind', every=3)
    assert blind_mapping['not_shown'] == []
    assert {identity for packet in blind_mapping['packets'] for identity in packet['facts']} == {row['id'] for row in read}


def test_agreement_reports_holds_agreement_and_kappa_beside_the_labels(tmp_path, capsys):
    run = judged(tmp_path)
    result = agreement(run, ['judge-a', 'judge-b'], 'judge-c')
    assert (result['holds_agreement'], result['holds_dispute_rate']) == (0.9, 0.1)
    # Holds marginals: (held, stale, cannot tell) = (6, 1, 3) vs (5, 1, 4); chance = .43, observed = .9.
    assert result['holds_kappa'] == pytest.approx(47 / 57)
    assert result == json.loads((run / 'adjudicated.json').read_text())
    assert main(['agreement', str(run), '--judges', 'judge-a', 'judge-b', '--third', 'judge-c']) == 0
    rendered = capsys.readouterr().out
    assert 'label agreement 0.900, Cohen\'s kappa' in rendered
    assert 'holds agreement 0.900, Cohen\'s kappa 0.825, dispute rate 0.100' in rendered
