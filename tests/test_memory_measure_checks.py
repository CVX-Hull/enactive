"""The two checks of a changed judge (#386): the anchor, which re-judges the measure gate's owner-labelled pairs
with the gate's frozen prompt when a judge's model changes, and the prompt-change check, which compares the first
two judges' agreement on a frozen set of stretches. The gate here is a fixture in the sealed gate's formats."""
import hashlib
import json
from pathlib import Path

import pytest

from harness.evaluation.core import judge
from test_memory_measure import VERDICTS, answers, judged, mapping_of, png, save
from tools import memory_measure
from tools.memory_measure import (ANCHOR_INSTRUCTIONS, ANCHOR_PROMPT_SHA256, JUDGE_INSTRUCTIONS, MeasureError, anchor_events,
    anchor_packets, anchor_report, binomial_interval, judge_events, main, prompt_packets, prompt_report, read_owner_labels)

ITEMS = [dict(id='item-01', place='Garage shelf', what='tools'), dict(id='item-02', place='Pond', what='water')]
#: (index, group, stretch, item, the owner's blind and checked labels, judge-a, judge-b, the gate's adjudicated label)
PAIRS = [(0, 'random', 'run-e:1-5', 'item-01', 'straight', 'straight', 'straight', 'straight', 'straight'),
    (1, 'random', 'run-e:1-5', 'item-02', 'not_engaged', 'missed', 'missed', 'not_engaged', 'missed'),
    (2, 'random', 'run-f:1-5', 'item-01', 'not_engaged', 'not_engaged', 'not_engaged', 'not_engaged', 'not_engaged'),
    (3, 'engaged', 'run-f:1-5', 'item-02', 'missed', 'missed', 'missed', 'missed', 'missed')]
#: What a new judge answers: it differs from the gate's adjudicated label on pairs 1 and 3.
NEW = {('run-e:1-5', 'item-01'): 'straight', ('run-e:1-5', 'item-02'): 'not_engaged', ('run-f:1-5', 'item-01'): 'not_engaged',
    ('run-f:1-5', 'item-02'): 'straight'}


@pytest.fixture(autouse=True)
def fixture_evidence_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_measure, 'GATE_EVIDENCE_MANIFEST', tmp_path / 'sealed-evidence.sha256')


def seal_gate_evidence(gate: Path) -> None:
    memory_measure.GATE_EVIDENCE_MANIFEST.write_text(''.join(
        f'{memory_measure.file_sha256(path)}  memory-measure/{path.relative_to(gate)}\n'
        for path in sorted(gate.rglob('*')) if path.is_file()))


def sealed_gate(tmp_path: Path, instructions: str = ANCHOR_INSTRUCTIONS) -> Path:
    """A finished measure gate in the formats the sealed one holds: judge-packet/1 packets with their mapping, the
    two samples, the owner's labels (owner-labels/2) and the adjudicated labels (judge-adjudicated/1). The third
    stretch holds no owner-labelled pair."""
    gate = tmp_path / 'memory-measure' / 'gate'
    packets = []
    for name, start in (('s00000000aa', 'run-e:1-5'), ('s00000000bb', 'run-f:1-5'), ('s00000000cc', 'run-g:1-3')):
        directory = gate / 'judge-packets' / name
        (directory / 'frames').mkdir(parents=True)
        (directory / 'items').mkdir()
        rows = []
        for number in (1, 2):
            (directory / 'frames' / f'f00{number}.png').write_bytes(png(number + len(packets) * 2))
            rows.append(dict(frame=f'f00{number}', file=f'frames/f00{number}.png', inputs_before=['k'], decision=number,
                sha256=memory_measure.file_sha256(directory / 'frames' / f'f00{number}.png')))
        for item in ITEMS:
            (directory / 'items' / f"{item['id']}.png").write_bytes(png(9))
        save(directory / 'items.json', dict(schema='known-items/1', sha256='0' * 64, items=ITEMS))
        sha, size = memory_measure.seal_packet(directory, dict(schema='judge-packet/1', packet=name, decisions=5, short=False,
            labels=list(judge.ANCHOR_LABELS), items_sha256='0' * 64, frames=rows), instructions)
        packets.append(dict(packet=name, start=start, sha256=sha, bytes=size, frames={f'f00{n}': f'{name}-source-{n}' for n in (1, 2)}))
    save(gate / 'private' / 'judge-mapping.json', dict(schema='judge-mapping/1', seed=1, stretch=5, packets=packets))
    for name, group in (('sample.json', 'random'), ('sample-engaged.json', 'engaged')):
        save(gate / name, dict(pairs=[dict(index=pair[0], start=pair[2], item=pair[3]) for pair in PAIRS if pair[1] == group]))
    save(gate / 'labels.json', dict(schema='owner-labels/2', sample_sha256=memory_measure.file_sha256(gate / 'sample.json'),
        engaged_sha256=memory_measure.file_sha256(gate / 'sample-engaged.json'), history=[],
        labels={str(pair[0]): dict(index=pair[0], start=pair[2], item=pair[3], blind=pair[4], checked=pair[5]) for pair in PAIRS}))
    rows = [dict(start=pair[2], item=pair[3], label=pair[8], by='agreement', labels={'judge-a': pair[6], 'judge-b': pair[7]}) for pair in PAIRS]
    rows += [dict(start='run-g:1-3', item=item['id'], label='not_engaged', by='agreement',
        labels={'judge-a': 'not_engaged', 'judge-b': 'not_engaged'}) for item in ITEMS]
    save(gate / 'adjudicated.json', dict(schema='judge-adjudicated/1', judges=['judge-a', 'judge-b'], third='judge-c', unresolved=0, pairs=rows))
    seal_gate_evidence(gate)
    return gate


def anchor_answers(run: Path, labels=NEW, change=None) -> list[Path]:
    files = []
    for packet in json.loads((run / 'private' / 'anchor.json').read_text())['packets']:
        value = dict(packet=packet['packet'], answers=[dict(item=item, label=labels[(packet['start'], item)],
            frames=['f001'] if labels[(packet['start'], item)] in judge.ANCHOR_TOUCHED else []) for item in packet['items']])
        if change:
            change(value)
        files.append(save(run / 'answers' / f"{packet['packet']}.json", value))
    return files


def tree(directory: Path) -> dict:
    return {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob('*')) if path.is_file()}


# --- the anchor -----------------------------------------------------------------------------------------------------------

def test_the_frozen_anchor_prompt_is_the_measure_gates_and_is_never_edited():
    """The hash is that of `instructions.md` in every sealed judge packet of the measure gate. An edit to the text
    in the tool fails here; `anchor packets` compares the same hash with the gate's packets."""
    assert ANCHOR_PROMPT_SHA256 == '14c7d5932c044f2ac3e6b6e0a60bbb45ece3598d87a3e60aea4f94ad68c6af24'
    assert hashlib.sha256(ANCHOR_INSTRUCTIONS.encode()).hexdigest() == ANCHOR_PROMPT_SHA256
    assert judge.ANCHOR_LABELS == ('straight', 'missed', 'not_engaged', 'cannot_tell')
    assert all(f'`{label}`' in ANCHOR_INSTRUCTIONS for label in judge.ANCHOR_LABELS)
    assert ANCHOR_INSTRUCTIONS not in JUDGE_INSTRUCTIONS.values()  # it is not the standing, game-neutral prompt


def test_anchor_packets_are_the_gates_packets_unchanged_and_the_gate_is_only_read(tmp_path, capsys):
    gate = sealed_gate(tmp_path)
    sealed = tree(gate)
    run = tmp_path / 'memory-measure' / 'new-model'
    assert main(['anchor', 'packets', str(run), '--gate', str(gate), '--dry-run']) == 0
    out = capsys.readouterr().out
    assert f'frozen prompt, sha256 {ANCHOR_PROMPT_SHA256}' in out and 'dry run: nothing written' in out
    assert not run.exists() and tree(gate) == sealed
    value = anchor_packets(run, gate)
    assert tree(gate) == sealed
    # only the two stretches that hold an owner-labelled pair, byte for byte, with the gate's own packet hashes
    assert sorted(p.name for p in (run / 'anchor' / 'packets').iterdir()) == ['s00000000aa', 's00000000bb']
    for name in ('s00000000aa', 's00000000bb'):
        assert tree(run / 'anchor' / 'packets' / name) == tree(gate / 'judge-packets' / name)
        assert (run / 'anchor' / 'packets' / name / 'instructions.md').read_text() == ANCHOR_INSTRUCTIONS
    assert value == json.loads((run / 'private' / 'anchor.json').read_text())
    assert (value['schema'], value['gate'], value['prompt_sha256'], value['gate_judges']) == ('anchor-set/1', 'gate',
        ANCHOR_PROMPT_SHA256, ['judge-a', 'judge-b'])
    assert value['sources']['labels.json'] == memory_measure.file_sha256(gate / 'labels.json')
    assert [(pair['index'], pair['group'], pair['blind'], pair['checked']) for pair in value['pairs']] == [
        (0, 'random', 'straight', 'straight'), (1, 'random', 'not_engaged', 'missed'), (2, 'random', 'not_engaged', 'not_engaged'),
        (3, 'engaged', 'missed', 'missed')]
    assert len(value['gate_labels']) == 4 and value['gate_labels'][1] == dict(start='run-e:1-5', item='item-02',
        adjudicated='missed', labels={'judge-a': 'missed', 'judge-b': 'not_engaged'})
    with pytest.raises(MeasureError, match='made once'):
        anchor_packets(run, gate)
    with pytest.raises(MeasureError, match='never into the gate'):
        anchor_packets(gate, gate)
    assert tree(gate) == sealed


def test_a_gate_whose_prompt_or_packets_differ_from_what_it_recorded_is_refused(tmp_path, monkeypatch):
    run = tmp_path / 'memory-measure' / 'new-model'
    other = sealed_gate(tmp_path / 'other-prompt', ANCHOR_INSTRUCTIONS.replace('straight', 'direct'))
    with pytest.raises(MeasureError, match="is not the frozen prompt's"):
        anchor_packets(run, other, dry_run=True)
    gate = sealed_gate(tmp_path)
    frame = gate / 'judge-packets' / 's00000000aa' / 'frames' / 'f001.png'
    frame.write_bytes(png(77))
    with pytest.raises(MeasureError, match='f001.png: changed since the packet was made'):
        anchor_packets(run, gate)
    assert not run.exists()
    gate = sealed_gate(tmp_path / 'edited')
    manifest = gate / 'judge-packets' / 's00000000bb' / 'manifest.json'
    manifest.write_text(manifest.read_text() + ' ')
    with pytest.raises(MeasureError, match='not the packet that was made'):
        anchor_packets(run, gate)
    # the tool's own copy of the prompt, edited: refused before any gate is trusted
    monkeypatch.setattr(memory_measure, 'ANCHOR_INSTRUCTIONS', ANCHOR_INSTRUCTIONS + ' ')
    with pytest.raises(MeasureError, match='was edited'):
        anchor_packets(run, sealed_gate(tmp_path / 'good'), dry_run=True)


def test_owner_labels_of_another_format_or_sample_are_refused(tmp_path):
    gate = sealed_gate(tmp_path)
    assert [(pair['index'], pair['group']) for pair in read_owner_labels(gate)] == [(0, 'random'), (1, 'random'), (2, 'random'), (3, 'engaged')]
    saved = json.loads((gate / 'labels.json').read_text())
    save(gate / 'labels.json', dict(saved, schema='owner-labels/1'))
    with pytest.raises(MeasureError, match='not owner-labels/2'):
        read_owner_labels(gate)
    save(gate / 'labels.json', dict(saved, sample_sha256='0' * 64))
    with pytest.raises(MeasureError, match='another sample'):
        read_owner_labels(gate)
    save(gate / 'labels.json', dict(saved, labels={key: dict(entry, checked=None) for key, entry in saved['labels'].items()}))
    with pytest.raises(MeasureError, match="lacks the owner's blind and checked labels"):
        read_owner_labels(gate)


def test_anchor_events_are_anchor_verdicts_in_the_gates_labels(tmp_path):
    run = tmp_path / 'memory-measure' / 'new-model'
    anchor_packets(run, sealed_gate(tmp_path))
    events = anchor_events(run, 'judge-n', 'model-y', anchor_answers(run))
    assert [(e.start, e.item, e.label, e.cited_frames) for e in events] == [
        ('run-e:1-5', 'item-01', 'straight', ('s00000000aa-source-1',)), ('run-e:1-5', 'item-02', 'not_engaged', ()),
        ('run-f:1-5', 'item-01', 'not_engaged', ()), ('run-f:1-5', 'item-02', 'straight', ('s00000000bb-source-1',))]
    line = json.loads((run / 'anchor' / 'events' / 'judge-n.jsonl').read_text().splitlines()[0])
    assert (line['schema'], line['kind'], line['payload']['model']) == ('judge-events/2', 'anchor_verdict', 'model-y')
    assert not (run / 'events').exists()  # never among the standing measure's events
    with pytest.raises(MeasureError, match='written once'):
        anchor_events(run, 'judge-n', 'model-y', anchor_answers(run))
    for change, message in ((lambda value: value['answers'][0].update(label='in_line'), 'is not one of straight, missed, not_engaged, cannot_tell'),
            (lambda value: value['answers'][0].update(label='missed', frames=[]), 'must cite a frame'),
            (lambda value: value['answers'].pop(), 'no answer for item-02')):
        with pytest.raises(MeasureError, match=message):
            anchor_events(run, 'judge-m', 'model-y', anchor_answers(run, change=change))


def test_the_anchor_report_compares_a_new_judge_with_the_owner_beside_the_gates_judges(tmp_path, capsys):
    run = tmp_path / 'memory-measure' / 'new-model'
    anchor_packets(run, sealed_gate(tmp_path))
    with pytest.raises(MeasureError, match='missing; run `events` for judge-n first'):
        anchor_report(run, 'judge-n')
    anchor_events(run, 'judge-n', 'model-y', anchor_answers(run))
    report = anchor_report(run, 'judge-n')
    assert report == json.loads((run / 'anchor' / 'report-judge-n.json').read_text())
    assert (report['schema'], report['judge'], report['model'], report['owner_pairs'], report['prompt_sha256']) == (
        'anchor-report/1', 'judge-n', 'model-y', 4, ANCHOR_PROMPT_SHA256)

    def matched(figures: dict) -> dict:
        return {which: {group: (part['matched'], part['compared']) for group, part in groups.items()} for which, groups in figures.items()}

    # blind: the new judge matches the owner on pairs 0, 1, 2; the gate's adjudicated label on 0, 2, 3
    assert matched(report['against_owner']['new']) == dict(blind=dict(all=(3, 4), random=(3, 3)), checked=dict(all=(2, 4), random=(2, 3)))
    assert matched(report['against_owner']['gate']['adjudicated']) == dict(blind=dict(all=(3, 4), random=(2, 3)),
        checked=dict(all=(4, 4), random=(3, 3)))
    assert matched(report['against_owner']['gate']['judge-a'])['blind'] == dict(all=(3, 4), random=(2, 3))
    assert matched(report['against_owner']['gate']['judge-b'])['blind'] == dict(all=(4, 4), random=(3, 3))
    assert report['against_owner']['new']['blind']['all']['interval'] == binomial_interval(3, 4)
    assert report['shift'] == dict(blind=dict(all=0, random=1), checked=dict(all=-2, random=-1))
    # they agree on 2 of 4; by chance 0.5 * 0.25 (straight) + 0.5 * 0.25 (not engaged) = 0.25; kappa 0.25 / 0.75
    assert report['all_pairs']['new_with_adjudicated'] == dict(pairs=4, agreement=0.5, kappa=pytest.approx(1 / 3))
    assert report['all_pairs']['gate_first_two']['agreement'] == 0.75 and report['all_pairs']['new_with_judge-b']['agreement'] == 0.75
    assert [(row['item'], row['group'], row['new'], row['adjudicated']) for row in report['differing']] == [
        ('item-02', 'random', 'not_engaged', 'missed'), ('item-02', 'engaged', 'straight', 'missed')]
    assert main(['anchor', 'report', str(run), '--judge', 'judge-n']) == 0
    out = capsys.readouterr().out
    assert "matches with the owner's blind labels, the random draw: new judge 3 of 3" in out and 'gate adjudicated 2 of 3' in out
    assert 'shift +1' in out and 'shift -2' in out and 'not independent' in out
    partial = tmp_path / 'memory-measure' / 'partial'
    anchor_packets(partial, tmp_path / 'memory-measure' / 'gate')
    anchor_events(partial, 'judge-n', 'model-y', anchor_answers(partial)[:1])
    with pytest.raises(MeasureError, match='2 owner-labelled pairs lack a verdict'):
        anchor_report(partial, 'judge-n')


# --- the prompt-change check ------------------------------------------------------------------------------------------------

def changed_prompt(monkeypatch) -> str:
    new = JUDGE_INSTRUCTIONS['use'] + '\nWhen two labels fit, choose the one the cited frames show most directly.\n'
    monkeypatch.setitem(memory_measure.JUDGE_INSTRUCTIONS, 'use', new)
    return new


def test_prompt_check_packets_are_the_same_frozen_stretches_with_the_new_instructions(tmp_path, monkeypatch):
    before = judged(tmp_path)
    old = mapping_of(before)
    new_text = changed_prompt(monkeypatch)
    after = tmp_path / 'memory-measure' / 'after'
    mapping = prompt_packets(after, before)
    assert mapping == mapping_of(after) and mapping['instructions_sha256'] == hashlib.sha256(new_text.encode()).hexdigest()
    assert mapping['before'] == dict(run='study', mapping_sha256=memory_measure.file_sha256(before / 'private' / 'judge-mapping.json'),
        instructions_sha256=old['instructions_sha256'])
    for mine, theirs in zip(mapping['packets'], old['packets']):
        here, there = after / 'judge-packets' / mine['packet'], before / 'judge-packets' / theirs['packet']
        assert (mine['packet'], mine['window'], mine['facts'], mine['frames']) == (theirs['packet'], theirs['window'], theirs['facts'], theirs['frames'])
        assert mine['stretch_sha256'] == theirs['stretch_sha256'] == memory_measure.stretch_sha256(here)  # the frozen stretch
        assert mine['sha256'] != theirs['sha256'] and mine['sha256'] == memory_measure.file_sha256(here / 'manifest.json')
        assert (here / 'instructions.md').read_text() == new_text
        mine_files, their_files = tree(here), tree(there)
        assert {name for name in mine_files if mine_files[name] != their_files[name]} == {'instructions.md', 'manifest.json'}
        memory_measure.verify_packet(here, mine['sha256'])
        manifest = json.loads((here / 'manifest.json').read_text())
        text_size = sum(memory_measure.text_tokens(path.read_text()) for path in here.rglob('*')
            if path.is_file() and path.suffix != '.png')
        assert manifest['budget']['estimated']['text'] == text_size
        assert mine['estimated_tokens'] == text_size + manifest['budget']['estimated']['images']
    with pytest.raises(MeasureError, match='made once'):
        prompt_packets(after, before)
    with pytest.raises(MeasureError, match='must differ'):
        prompt_packets(before, before)
    frame = next((before / 'judge-packets' / old['packets'][0]['packet'] / 'frames').iterdir())
    frame.write_bytes(png(99))  # a stretch that is no longer the frozen one
    with pytest.raises(MeasureError, match='changed since the packet was made'):
        prompt_packets(tmp_path / 'memory-measure' / 'again', before)
    assert not (tmp_path / 'memory-measure' / 'again').exists()


def test_the_prompt_check_reports_the_first_two_judges_agreement_before_and_after(tmp_path, monkeypatch, capsys):
    before = judged(tmp_path)
    changed_prompt(monkeypatch)
    after = tmp_path / 'memory-measure' / 'after'
    prompt_packets(after, before)
    # with the new instructions judge-b gives judge-a's label on the disputed pair; judge-a changes one of its own
    now = {'judge-a': {**VERDICTS['judge-a'], ('run-g', 'lead-1'): ('did_not_apply', 'cannot_tell')},
        'judge-b': {**VERDICTS['judge-b'], ('run-f', 'lead-1'): ('against', 'held'), ('run-g', 'lead-1'): ('did_not_apply', 'cannot_tell')}}
    for name in ('judge-a', 'judge-b'):
        judge_events(after, name, 'model-x', answers(after, name, now[name]))
    report = prompt_report(after, before, ['judge-a', 'judge-b'], seed=3, draws=500)
    assert report == json.loads((after / 'prompt-check.json').read_text()) and report['schema'] == 'prompt-check/1'
    assert (report['pairs'], report['stretches'], report['prompt_changed'], report['before_run']) == (10, 3, True, 'study')
    assert report['before']['instructions_sha256'] != report['after']['instructions_sha256']
    assert (report['before']['label']['agreement'], report['before']['label']['dispute_rate']['value']) == (0.9, 0.1)
    assert (report['after']['label']['agreement'], report['after']['label']['dispute_rate']['value'], report['after']['label']['kappa']['value']) == (1.0, 0.0, 1.0)
    assert report['before']['holds']['agreement'] == 0.9 and report['after']['holds']['agreement'] == 0.9
    assert report['shift']['agreement'] == pytest.approx(0.1) and report['shift']['dispute_rate'] == pytest.approx(-0.1)
    assert report['shift']['kappa']['value'] == pytest.approx(1.0 - report['before']['label']['kappa']['value'])
    low, high = report['shift']['kappa']['interval']
    assert 0 <= low <= high
    assert report['relabelled'] == {'judge-a': 0.1, 'judge-b': 0.2}
    assert main(['prompt-check', 'report', str(after), '--before', str(before), '--judges', 'judge-a', 'judge-b', '--seed', '3']) == 0
    out = capsys.readouterr().out
    assert 'the instructions changed' in out and 'shift, after minus before: agreement 0.100' in out
    # a run that was not made from the frozen set, or whose stretch was edited, is refused
    with pytest.raises(MeasureError, match='not made from'):
        prompt_report(before, before, ['judge-a', 'judge-b'])
    packet = mapping_of(after)['packets'][0]['packet']
    facts = after / 'judge-packets' / packet / 'facts.json'
    manifest = after / 'judge-packets' / packet / 'manifest.json'
    manifest.write_text(manifest.read_text().replace(memory_measure.file_sha256(facts), '0' * 64))
    with pytest.raises(MeasureError, match='not the packet that was made'):
        prompt_report(after, before, ['judge-a', 'judge-b'])


def test_the_stretch_hash_leaves_out_the_instructions_and_nothing_else(tmp_path):
    run = judged(tmp_path)
    packet = mapping_of(run)['packets'][0]
    directory = run / 'judge-packets' / packet['packet']
    assert memory_measure.stretch_sha256(directory) == packet['stretch_sha256']
    manifest = json.loads((directory / 'manifest.json').read_text())
    for change in (lambda value: value['files'].update({'facts.json': '0' * 64}), lambda value: value['frames'][0].update(sha256='0' * 64),
            lambda value: value['frames'][0].update(inputs_before=['other']), lambda value: value.update(decisions=99)):
        edited = json.loads(json.dumps(manifest))
        change(edited)
        save(tmp_path / 'edited' / 'manifest.json', edited)
        assert memory_measure.stretch_sha256(tmp_path / 'edited') != packet['stretch_sha256']
    for change in (lambda value: value['files'].update({'instructions.md': '0' * 64}), lambda value: value['budget'].update(tokens=1)):
        edited = json.loads(json.dumps(manifest))
        change(edited)
        save(tmp_path / 'edited' / 'manifest.json', edited)
        assert memory_measure.stretch_sha256(tmp_path / 'edited') == packet['stretch_sha256']


# R-EVIDENCE-LOSS/R-FALSE-CLAIM: reject changed inputs before any imported answer or report is written.
@pytest.mark.parametrize('target', ['private/judge-mapping.json', 'labels.json', 'adjudicated.json', 'packet'])
def test_anchor_trusts_the_independent_sealed_inventory(tmp_path, target):
    gate = sealed_gate(tmp_path)
    run = tmp_path / 'memory-measure' / 'new-model'
    if target == 'packet':
        directory = gate / 'judge-packets' / 's00000000aa'
        frame = directory / 'frames' / 'f001.png'
        frame.write_bytes(png(88))
        manifest = json.loads((directory / 'manifest.json').read_text())
        manifest['frames'][0]['sha256'] = memory_measure.file_sha256(frame)
        save(directory / 'manifest.json', manifest)
        mapping = json.loads((gate / 'private' / 'judge-mapping.json').read_text())
        mapping['packets'][0]['sha256'] = memory_measure.file_sha256(directory / 'manifest.json')
        save(gate / 'private' / 'judge-mapping.json', mapping)
    else:
        path = gate / target
        path.write_text(path.read_text() + ' ')
    with pytest.raises(MeasureError, match='sealed evidence manifest'):
        anchor_packets(run, gate, dry_run=True)
    assert not run.exists()


@pytest.mark.parametrize('target', ['instructions.md', 'frame'])
def test_anchor_import_verifies_every_packet_file(tmp_path, target):
    run = tmp_path / 'memory-measure' / 'new-model'
    anchor_packets(run, sealed_gate(tmp_path))
    answers = anchor_answers(run)
    packet = json.loads((run / 'private' / 'anchor.json').read_text())['packets'][0]
    directory = run / 'anchor' / 'packets' / packet['packet']
    path = next((directory / 'frames').iterdir()) if target == 'frame' else directory / target
    path.write_bytes(path.read_bytes() + b'tampered')
    with pytest.raises(MeasureError, match='changed since the packet was made'):
        anchor_events(run, 'judge-n', 'model-y', answers)
    assert not (run / 'anchor' / 'events').exists()


def test_anchor_import_rechecks_frozen_prompt_even_if_local_packet_was_resealed(tmp_path):
    run = tmp_path / 'memory-measure' / 'new-model'
    anchor_packets(run, sealed_gate(tmp_path))
    answers = anchor_answers(run)
    anchor = json.loads((run / 'private' / 'anchor.json').read_text())
    packet = anchor['packets'][0]
    directory = run / 'anchor' / 'packets' / packet['packet']
    instructions = directory / 'instructions.md'
    instructions.write_text(instructions.read_text() + ' ')
    manifest = json.loads((directory / 'manifest.json').read_text())
    manifest['files']['instructions.md'] = memory_measure.file_sha256(instructions)
    save(directory / 'manifest.json', manifest)
    packet['sha256'] = memory_measure.file_sha256(directory / 'manifest.json')
    save(run / 'private' / 'anchor.json', anchor)
    with pytest.raises(MeasureError, match='not the frozen prompt'):
        anchor_events(run, 'judge-n', 'model-y', answers)


@pytest.mark.parametrize('side', ['before', 'after'])
@pytest.mark.parametrize('target', ['instructions.md', 'frame'])
def test_prompt_report_verifies_packet_files_on_both_sides(tmp_path, monkeypatch, side, target):
    before = judged(tmp_path)
    changed_prompt(monkeypatch)
    after = tmp_path / 'memory-measure' / 'after'
    prompt_packets(after, before)
    for name in ('judge-a', 'judge-b'):
        judge_events(after, name, 'model-x', answers(after, name))
    run = before if side == 'before' else after
    directory = run / 'judge-packets' / mapping_of(run)['packets'][0]['packet']
    path = next((directory / 'frames').iterdir()) if target == 'frame' else directory / target
    path.write_bytes(path.read_bytes() + b'tampered')
    with pytest.raises(MeasureError, match='changed since the packet was made'):
        prompt_report(after, before, ['judge-a', 'judge-b'])
    assert not (after / 'prompt-check.json').exists()


def test_prompt_check_refuses_changed_models_and_records_both_model_sets(tmp_path, monkeypatch):
    before = judged(tmp_path)
    changed_prompt(monkeypatch)
    after = tmp_path / 'memory-measure' / 'after'
    prompt_packets(after, before)
    for name in ('judge-a', 'judge-b'):
        judge_events(after, name, 'model-changed' if name == 'judge-b' else 'model-x', answers(after, name))
    with pytest.raises(MeasureError, match='same model for each judge before and after'):
        prompt_report(after, before, ['judge-a', 'judge-b'])
    assert not (after / 'prompt-check.json').exists()
    (after / 'events' / 'judge-b.jsonl').unlink()
    judge_events(after, 'judge-b', 'model-x', answers(after, 'judge-b'))
    report = prompt_report(after, before, ['judge-a', 'judge-b'], seed=1, draws=20)
    assert report['before']['models'] == report['after']['models'] == {'judge-a': 'model-x', 'judge-b': 'model-x'}


def test_new_codebook_is_verbatim_in_both_instruction_kinds():
    bullet = '''- `found_again`: looked it up. The player spent an action to get information the fact already gave: it
  searched for it, or opened a screen or examined something whose only purpose then was to learn what the fact
  says, or tried several screens to find it. Seeing the fact on a screen the player opened to do something
  else, or in a message the game showed on its own, is not `found_again`.'''
    decision = '''Choose in this order, and stop at the first that holds:

1. Nothing in the window could have made the fact matter to what the player was doing: `did_not_apply`.
2. The player did what the fact advises against, or went for something the fact says is empty or gone:
   `against`.
3. The player spent an action only to learn what the fact says (a search, a description or help screen opened
   and then left without doing anything else with it, the same screen opened again to read the same thing, or
   several screens tried to find it), before acting: `found_again`.
4. The player did what the fact supports: `in_line`. This includes using a screen it opened to do something
   (to make, use, eat or move something) that also shows what the fact says.
5. Otherwise: `cannot_tell`.

Examples:
- The player opens the list of things it can make in order to make one, the list shows the requirements the
  fact states, and it makes it that way: `in_line`, not `found_again`.
- The player types the thing's name into a search, reads its description and closes it before acting:
  `found_again`.
- The game's messages say a companion is helping, as the fact says, while the player does something
  unrelated: `did_not_apply` (or `in_line` if the player relied on the help), never `found_again`.
- The game warns of something the fact already says (that some ground is slow to cross) while the player
  walks on: not `found_again`; judge what the player did.
- The player opens the same screen twice in a row to read the same figures, then acts: `found_again`.'''
    for instructions in JUDGE_INSTRUCTIONS.values():
        assert bullet in instructions and decision in instructions
        assert instructions.index(decision) < instructions.index('Then say whether')


def test_prompt_check_accepts_old_text_in_sealed_pilot_blind_run(tmp_path):
    from tools import evidence
    before = evidence.default_store() / 'withholding-pilot-619/memory-measure/pilot-619-blind'
    if not before.is_dir():
        pytest.skip('sealed pilot evidence is not present in this checkout')
    after = tmp_path / 'memory-measure' / 'updated-pilot-codebook'
    old = mapping_of(before)
    mapping = prompt_packets(after, before)
    assert mapping['instructions_sha256'] != old['instructions_sha256']
    for mine, theirs in zip(mapping['packets'], old['packets']):
        assert mine['stretch_sha256'] == theirs['stretch_sha256']
        assert (mine['window'], mine['frames'], mine['facts']) == (theirs['window'], theirs['frames'], theirs['facts'])
        assert (after / 'judge-packets' / mine['packet'] / 'instructions.md').read_text() == JUDGE_INSTRUCTIONS['blind']
    for name in ('opus-a', 'opus-b'):
        old_events = memory_measure.read_judge(before / 'events', name, judge.FACT_USE)
        paths = []
        for packet in mapping['packets']:
            verdicts = []
            inverse_frames = {source: frame for frame, source in packet['frames'].items()}
            for opaque, identity in packet['fact_ids'].items():
                event = old_events[(packet['window'], identity)]
                verdicts.append(dict(fact=opaque, label=event.label, holds=event.holds,
                    frames=[inverse_frames[source] for source in event.cited_frames]))
            paths.append(save(after / 'answers' / name / f"{packet['packet']}.json",
                              dict(packet=packet['packet'], answers=verdicts)))
        judge_events(after, name, next(iter(old_events.values())).model, paths)
    report = prompt_report(after, before, ['opus-a', 'opus-b'], seed=653, draws=20)
    assert report['prompt_changed'] and report['relabelled'] == {'opus-a': 0, 'opus-b': 0}
    assert report['before']['label']['pairs'] == report['after']['label']['pairs']
