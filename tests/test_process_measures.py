"""Portable process evidence checks (#620): R-FALSE-CLAIM, R-EVIDENCE-LOSS and R-GAME-COUPLING.

Synthetic traces exercise packet isolation, sampling, frozen goals and judge ingress. They establish no real
play outcome or judge quality; independent prompt review and sealed-lineage judging belong to the lead.
"""
from copy import deepcopy
from dataclasses import replace
import json

import numpy as np
import pytest

from harness.evaluation.core import judge, records
from tools import process_measures as pm
from tools.memory_measure import MeasureError, recorded_frames, verify_packet
from test_memory_measure import admission, save


MILESTONES = [dict(id=f'milestone-{i}', text=f'Observable objective {i}.') for i in range(1, 4)]


def evidence(tmp_path, name='admission-a', repeated=False, decisions=6, size=(8, 8)):
    source = admission(tmp_path / 'evidence', name, name[-1],
        [1] * decisions if repeated else list(range(1, decisions + 1)), size)
    (source / 'prompt.txt').write_text('Reach the destination and gather supplies. Remain alive.')
    for actor in (source / 'actors').iterdir():
        (actor / 'prompt.txt').write_text('Continue the mission. FALLIBLE HANDOFF GOAL.')
        path = actor / 'host.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        output = []
        for row in rows:
            if repeated and row['type'] == 'tool-start':
                row['arguments']['actions'][0]['key'] = 'same'
            output.append(row)
            if row['type'] == 'response-complete':
                output.append(dict(row, type='assistant-text', text='I reached shelter. Next, get supplies! Is it safe?', omitted_bytes=0))
        path.write_text(''.join(json.dumps(row) + '\n' for row in output))
        (actor / 'player-final.txt').write_text('I obtained supplies. Still alive.')
    return source


def frozen(tmp_path, runs):
    run = tmp_path / 'memory-measure' / 'process'
    index = pm.milestones_packets(run, runs)
    answers = [save(tmp_path / f'goals-{i}.json', dict(packet=p['packet'], packet_sha256=p['sha256'],
        milestones=MILESTONES)) for i, p in enumerate(index['packets'])]
    pm.milestones_events(run, 'goals-judge', 'host-goal-model', answers)
    return run


def packed(tmp_path, **options):
    runs = [evidence(tmp_path, 'admission-a', True), evidence(tmp_path, 'admission-b'),
        evidence(tmp_path, 'admission-c'), evidence(tmp_path, 'admission-d')]
    run = frozen(tmp_path, runs)
    return run, pm.packets(run, runs, **options)


def answer_files(tmp_path, mapping, judge_name, override=None, selected=None):
    files = []
    for packet in mapping['packets']:
        if selected is not None and packet['packet'] not in selected:
            continue
        frames = list(packet['frames'])
        answers = []
        for kind, item in pm.questions(packet):
            default = {judge.STUCK: 'stuck' if packet.get('flag') else 'progressing',
                judge.RETRY: 'repeated_failed_approach' if packet.get('flag') else 'no_repeat',
                judge.MILESTONE: 'reached', judge.CLAIM: 'supported'}[kind]
            label = override(packet, kind, item, default) if override else default
            row = dict(kind=kind, label=label, frames=frames[:2])
            if kind == judge.MILESTONE:
                row['milestone'] = item
            elif kind == judge.CLAIM:
                row['claim'] = item
            answers.append(row)
        files.append(save(tmp_path / judge_name / f"{packet['packet']}.json", dict(packet=packet['packet'],
            packet_sha256=packet['sha256'], answers=answers)))
    return files


def judged(tmp_path, override_b=None, **options):
    run, mapping = packed(tmp_path, **options)
    for name, override in [('judge-a', None), ('judge-b', override_b)]:
        pm.judge_events(run, name, 'host-model', answer_files(tmp_path, mapping, name, override))
    return run, mapping


@pytest.mark.parametrize('kind,cls,extra,positive', [
    (judge.STUCK, judge.StuckVerdict, dict(window='admission/001:1-6'), 'stuck'),
    (judge.RETRY, judge.RetryVerdict, dict(window='admission/001:1-6'), 'repeated_failed_approach'),
    (judge.MILESTONE, judge.MilestoneVerdict, dict(milestone='goal'), 'reached'),
    (judge.CLAIM, judge.ClaimVerdict, dict(window='admission/001:1-6', claim='claim-0001'), 'unsupported'),
])
def test_new_event_kinds_reject_malformed_and_duplicate_pairs(tmp_path, kind, cls, extra, positive):
    event = cls(**extra, label=positive, cited_frames=('frame-a', 'frame-b'), judge='judge-a', model='host',
        packet='packet', packet_sha256='a' * 64)
    assert judge.parse(judge.envelope(event)) == event
    for fields in [dict(label='invented'), dict(cited_frames=()), dict(packet_sha256='wrong')]:
        with pytest.raises(records.EvaluationError):
            replace(event, **fields)
    if kind == judge.RETRY:
        with pytest.raises(records.EvaluationError, match='two frames'):
            replace(event, cited_frames=('frame-a',))
    with pytest.raises(records.EvaluationError, match='more than once'):
        judge.write_events(tmp_path / f'{kind}.jsonl', [event, event])
    envelope = judge.envelope(event)
    envelope['confidence'] = 0.9
    with pytest.raises(records.EvaluationError, match='no confidence'):
        judge.parse(envelope)


def test_process_verdicts_are_sibling_dataclasses():
    assert judge.RetryVerdict.__bases__ == (object,)
    assert judge.ClaimVerdict.__bases__ == (object,)


def test_goal_packet_contains_only_admission_mission(tmp_path):
    source = admission(tmp_path / 'evidence', 'handoff-run', 'h', [1, 2, 'handoff', 3, 4])
    mission = 'Reach the destination. Previous admission reported that supplies were scarce.'
    (source / 'prompt.txt').write_text(mission)
    for actor in (source / 'actors').iterdir():
        (actor / 'prompt.txt').write_text('Later actor HANDOFF OUTCOME.\n'
            '<player-context>PLAYER CONTEXT OUTCOME</player-context>\n<knowledge>KNOWLEDGE OUTCOME</knowledge>')
        (actor / 'context.txt').write_text('PRIVATE CONTEXT')
    run = tmp_path / 'memory-measure' / 'goals'
    packet = pm.milestones_packets(run, [source])['packets'][0]
    directory = run / 'milestone-packets' / packet['packet']
    assert json.loads((directory / 'goals.json').read_text()) == dict(mission=mission)
    contents = '\n'.join(path.read_text() for path in directory.iterdir())
    for excluded in ('HANDOFF OUTCOME', 'PLAYER CONTEXT OUTCOME', 'KNOWLEDGE OUTCOME', 'PRIVATE CONTEXT',
                     'player-context', '<knowledge>'):
        assert excluded not in contents


def test_default_sample_judges_unflagged_windows_without_flags(tmp_path):
    runs = [evidence(tmp_path, f'admission-{i}') for i in range(12)]
    run = frozen(tmp_path, runs)
    mapping = pm.packets(run, runs)
    assert mapping['sample_unflagged'] == 10
    assert mapping['sampling'] == dict(flagged=0, unflagged=12, sampled_unflagged=10, unflagged_fraction=10 / 12)
    assert sum(packet['mode'] == 'window' for packet in mapping['packets']) == 10


def test_milestones_required_frozen_once_and_hash_checked(tmp_path):
    source = evidence(tmp_path)
    run = tmp_path / 'memory-measure' / 'process'
    with pytest.raises(MeasureError, match='missing'):
        pm.packets(run, [source])
    index = pm.milestones_packets(run, [source])
    with pytest.raises(MeasureError, match='freeze milestones'):
        pm.packets(run, [source])
    packet = index['packets'][0]
    value = dict(packet=packet['packet'], packet_sha256=packet['sha256'], milestones=MILESTONES)
    answer = save(tmp_path / 'goals.json', value)
    value['packet_sha256'] = '0' * 64
    bad = save(tmp_path / 'bad.json', value)
    with pytest.raises(MeasureError, match='wrong packet hash'):
        pm.milestones_events(run, 'goals', 'host', [bad])
    pm.milestones_events(run, 'goals', 'host', [answer])
    with pytest.raises(MeasureError, match='written once'):
        pm.milestones_events(run, 'goals', 'host', [answer])
    pm.packets(run, [source], sample_unflagged=1)
    path = run / 'milestones' / f'{source.name}.json'
    original = path.read_text()
    path.write_text(original.replace('Observable', 'Changed'))
    with pytest.raises(MeasureError, match='changed'):
        pm.load_mapping(run)


@pytest.mark.parametrize('rows', [MILESTONES[:2], MILESTONES * 3, [MILESTONES[0]] * 3,
    [dict(id='Bad ID', text='x'), *MILESTONES[:2]], [dict(id='goal', text=''), *MILESTONES[:2]]])
def test_malformed_milestone_answers(tmp_path, rows):
    source = evidence(tmp_path)
    run = tmp_path / 'memory-measure' / 'process'
    packet = pm.milestones_packets(run, [source])['packets'][0]
    answer = save(tmp_path / 'answer.json', dict(packet=packet['packet'], packet_sha256=packet['sha256'], milestones=rows))
    with pytest.raises(MeasureError):
        pm.milestones_events(run, 'goals', 'host', [answer])
    assert not (run / 'milestones').exists()


def test_repeat_filter_uses_identical_inputs_and_changed_marks(tmp_path):
    repeated = evidence(tmp_path, repeated=True)
    frames = recorded_frames([repeated])[0][repeated.name]
    assert pm.repeat_flag(frames)
    assert not pm.repeat_flag(frames[:3])  # first frame establishes the baseline; only two unchanged attempts
    assert not pm.repeat_flag([frames[0], frames[1], replace(frames[2], changed=True), frames[3]])
    changing = evidence(tmp_path, 'admission-b')
    assert not pm.repeat_flag(recorded_frames([changing])[0][changing.name])
    differing = [replace(f, inputs=([dict(type='key', key=str(i))],)) for i, f in enumerate(frames)]
    assert not pm.repeat_flag(differing)


def test_packets_hide_filter_shuffle_frame_order_and_cap_claims(tmp_path):
    run, mapping = packed(tmp_path, claims_per_window=2, sample_unflagged=1)
    assert mapping['sampling'] == dict(flagged=1, unflagged=3, sampled_unflagged=1, unflagged_fraction=1 / 3)
    assert sum(row['judged'] for row in mapping['windows']) == 2
    assert all(row['first'] < row['last'] for row in mapping['windows'])
    assert all(len(row['claims']) == 2 and row['claims_cut'] == 18 for row in mapping['windows'])
    for packet in mapping['packets']:
        directory = run / 'process-packets' / packet['packet']
        manifest = verify_packet(directory, packet['sha256'])
        content = '\n'.join(p.read_text() for p in directory.iterdir() if p.is_file())
        for secret in ('admission-a', 'INTENT-MARK', 'CITES-MARK', 'FALLIBLE HANDOFF GOAL',
                       'sampling_fraction', 'claims_cut', '"flag"', '"decision"', 'aaaaaaa-'):
            assert secret not in content
        for path in directory.glob('*.json'):
            assert 'decision' not in path.read_text()
        assert manifest['budget']['estimated']['total'] <= mapping['budget_tokens']
        assert not manifest['budget']['over']
        if packet['mode'] == 'milestones':
            assert all(set(row) == {'frame', 'file', 'sha256'} for row in manifest['frames'])
            assert json.loads((directory / 'milestones.json').read_text()) == MILESTONES
            original = [f'{packet["admission"][-1] * 8}-{i}' for i in range(1, 7)]
            assert list(packet['frames'].values()) != original
        else:
            claims = json.loads((directory / 'claims.json').read_text())
            assert claims == [dict(id='claim-0001', text='I reached shelter.'), dict(id='claim-0002', text='Next, get supplies!')]
            assert 'I obtained supplies.' in (directory / 'player-text.json').read_text()
            assert all(set(row) == {'position', 'text', 'after_frame'}
                for row in json.loads((directory / 'player-text.json').read_text()))
    for packet in (run / 'milestone-packets').iterdir():
        assert not (packet / 'frames').exists()
        assert set(json.loads((packet / 'goals.json').read_text())) == {'mission'}


def test_window_budget_counts_serialized_text_and_never_splits_decisions(tmp_path):
    source = evidence(tmp_path, decisions=15, size=(960, 640))
    run = frozen(tmp_path, [source])
    frames = recorded_frames([source])[0][source.name]
    own = pm.player_text([source])[0][source.name, '001']
    contents = pm.window_contents(own, 1, 4, 12, {f.source: f'{i:016x}' for i, f in enumerate(frames[:4])})
    budget = pm.candidate(frames[:4], 60000, contents, pm.WINDOW_INSTRUCTIONS)['budget']['estimated']['total'] + 2
    mapping = pm.packets(run, [source], budget=budget, sample_unflagged=100)
    spans = [(row['first'], row['last']) for row in mapping['windows']]
    assert len(spans) > 1 and spans[0][0] == 1 and spans[-1][1] == 15
    assert all(a < b for a, b in spans)
    assert all(b + 1 == c for (_, b), (c, _) in zip(spans, spans[1:]))
    assert all(p['estimated_tokens'] <= budget for p in mapping['packets'])
    assert len([p for p in mapping['packets'] if p['mode'] == 'milestones']) > 1
    assert all(p['milestones'] == [m['id'] for m in MILESTONES]
        for p in mapping['packets'] if p['mode'] == 'milestones')
    with pytest.raises(MeasureError, match='at least two'):
        pm.window_parts(frames[:2], 1, 2, 1, lambda part, lo, hi: len(part) * 10)
    # The balanced cut leaves one step; the feasible partition repair moves a boundary instead.
    parts = pm.window_parts(frames[:7], 1, 7, 3, lambda part, lo, hi: len(part))
    assert [len(part) for part, _, _ in parts] == [3, 2, 2]


@pytest.mark.parametrize('kind', pm.KINDS)
@pytest.mark.parametrize('bad', ['label', 'citations', 'foreign_frame', 'pair_twice', 'omitted', 'hash', 'row_hash'])
def test_answer_ingress_rejects_each_malformed_kind(tmp_path, kind, bad):
    run, mapping = packed(tmp_path)
    paths = answer_files(tmp_path, mapping, 'judge-a')
    path = next(path for path in paths if any(row['kind'] == kind for row in json.loads(path.read_text())['answers']))
    value = json.loads(path.read_text())
    row = next(row for row in value['answers'] if row['kind'] == kind)
    if bad == 'label':
        row['label'] = 'invented'
    elif bad == 'citations':
        row['label'] = pm.DRIVING[kind][0]
        row['frames'] = []
    elif bad == 'pair_twice':
        value['answers'].append(deepcopy(row))
    elif bad == 'omitted':
        value['answers'].remove(row)
    elif bad == 'foreign_frame':
        row['frames'] = ['foreign-frame']
    elif bad == 'row_hash':
        row['packet_sha256'] = '0' * 64
    else:
        value['packet_sha256'] = '0' * 64
    save(path, value)
    with pytest.raises((MeasureError, records.EvaluationError)):
        pm.judge_events(run, 'judge-a', 'host-model', paths)
    assert not (run / 'process-events').exists()


def test_events_verify_all_packet_files_and_translate_citations(tmp_path):
    run, mapping = packed(tmp_path)
    paths = answer_files(tmp_path, mapping, 'judge-a')
    events = pm.judge_events(run, 'judge-a', 'host-model', paths)
    assert set(event.kind for event in events) == set(pm.KINDS)
    for event in events:
        packet = next(p for p in mapping['packets'] if p['packet'] == event.packet)
        assert event.cited_frames == tuple(packet['frames'][f] for f in list(packet['frames'])[:2])
    packet = mapping['packets'][0]
    (run / 'process-packets' / packet['packet'] / 'added.json').write_text('{}')
    with pytest.raises(MeasureError, match='files changed'):
        pm.judge_events(run, 'judge-b', 'host-model', paths)


def test_adjudication_third_and_third_alone(tmp_path):
    def different(packet, kind, item, default):
        return 'looping' if kind == judge.STUCK and packet.get('flag') else default
    run, mapping = judged(tmp_path, different)
    unresolved = pm.agreement(run, ['judge-a', 'judge-b'], draws=50)
    assert unresolved['unresolved'] == 1
    with pytest.raises(MeasureError, match='third judge'):
        pm.measure(run, draws=50)
    paths = answer_files(tmp_path, mapping, 'judge-c', selected=unresolved['third_judge_packets'])
    pm.judge_events(run, 'judge-c', 'host-model', paths)
    result = pm.agreement(run, ['judge-a', 'judge-b'], 'judge-c', draws=50)
    disputed = next(row for row in result['rows'] if row['by'] == 'third')
    assert disputed['label'] == 'stuck'
    assert result['statistics'][judge.STUCK]['all_pairs']['agreement'] == 0.75
    binary = result['statistics'][judge.STUCK]['binary']
    assert binary['pairs'] == 4 and binary['kappa']['value'] == 1
    assert binary['agreement'] == binary['positive_specific_agreement'] == 1
    stuck = pm.measure(run, draws=20)['measures']['stuck']
    assert stuck['kept'] and stuck['reason'] is None
    # A third label neither first judge gave is retained and explicitly marked, just as memory agreement.
    run2 = tmp_path / 'memory-measure' / 'third-alone'
    run.rename(run2)
    c = run2 / 'process-events' / judge.STUCK / 'judge-c.jsonl'
    raw = judge.read_events(c)[0]
    c.unlink()
    judge.write_events(c, [replace(raw, label='progressing')])
    result = pm.agreement(run2, ['judge-a', 'judge-b'], 'judge-c', draws=50)
    assert result['third_alone'] == 1
    assert next(row for row in result['rows'] if row['by'] == 'third_alone')['label'] == 'progressing'


def test_sampling_weighting_cap_counts_and_unestimable_unsampled_stratum(tmp_path):
    run, mapping = judged(tmp_path, claims_per_window=2, sample_unflagged=1)
    pm.agreement(run, ['judge-a', 'judge-b'], draws=50)
    report = pm.measure(run, seed=1, draws=100)
    stuck = report['measures']['stuck']
    assert stuck['value'] == 1 / 2
    assert stuck['flagged']['value'] == 1
    assert stuck['sampled_unflagged']['value'] == 0
    assert stuck['flagged']['interval'] is None
    assert stuck['sampled_unflagged']['interval'] is None
    assert stuck['weighted']['value'] == 1 / 4
    assert stuck['weighted']['denominator'] == 4
    assert report['measures']['retry']['weighted']['value'] == 1 / 4
    assert report['measures']['milestone']['value'] == 1
    assert set(report['measures']['milestone']['per_admission']) == set(mapping['admissions'])
    assert report['claims']['cut'] == 72 and report['claims']['judged_cut'] == 36
    assert report['filter']['agreement'] == 1
    assert report['binding'] is None and '--records' in report['binding_reason']
    assert report == json.loads((run / 'process.json').read_text())
    assert stuck['interval'] is not None
    assert 'not corrected' in report['not_corrected']
    # No unflagged sample: refuse to extrapolate the flagged observations to unobserved strata.
    other = tmp_path / 'no-sample'
    other.mkdir()
    run, _ = judged(other, sample_unflagged=0)
    pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    value = pm.measure(run, draws=20)['measures']['stuck']['weighted']
    assert value['value'] is None and 'not estimable' in value['reason']


def test_kappa_floor_drops_measure_using_binary_all_pairs_before_adjudication(tmp_path):
    def second(packet, kind, item, default):
        if kind == judge.STUCK:
            return 'progressing' if packet.get('flag') else 'stuck'
        return default
    run, mapping = judged(tmp_path, second, sample_unflagged=1)
    result = pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    pm.judge_events(run, 'judge-c', 'host-model', answer_files(tmp_path, mapping, 'judge-c', selected=result['third_judge_packets']))
    pm.agreement(run, ['judge-a', 'judge-b'], 'judge-c', draws=20)
    result = pm.measure(run, draws=20)
    stuck = result['measures']['stuck']
    assert not stuck['kept'] and 'below 0.845' in stuck['reason']
    assert result['kappa_floor'] == 0.845
    assert stuck['judges']['binary']['kappa']['value'] == -1
    assert stuck['judges']['binary']['positive_specific_agreement'] == 0
    assert stuck['judges']['driving_pairs']['pairs'] == 2
    assert stuck['judges']['driving_pairs']['kappa']['value'] == -1
    assert not result['measures']['milestone']['kept']  # all-positive pairs cannot identify kappa
    assert 'undefined' in result['measures']['milestone']['reason']


@pytest.mark.parametrize('kind', [judge.RETRY, judge.MILESTONE, judge.CLAIM])
@pytest.mark.parametrize('disagree', [False, True])
def test_single_driving_label_can_pass_binary_floor_or_drop_below_it(tmp_path, kind, disagree):
    run, mapping = packed(tmp_path)
    def first(packet, current, item, default):
        if current == kind:
            return pm.DRIVING[kind][0] if packet['admission'] == 'admission-a' else 'cannot_tell'
        return default
    def second(packet, current, item, default):
        if disagree and current == kind and packet['admission'] == 'admission-b':
            return pm.DRIVING[kind][0]
        return first(packet, current, item, default)
    for name, labels in [('judge-a', first), ('judge-b', second)]:
        pm.judge_events(run, name, 'host-model', answer_files(tmp_path, mapping, name, labels))
    result = pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    if disagree:
        pm.judge_events(run, 'judge-c', 'host-model', answer_files(tmp_path, mapping, 'judge-c', first,
            selected=result['third_judge_packets']))
        pm.agreement(run, ['judge-a', 'judge-b'], 'judge-c', draws=20)
    value = pm.measure(run, draws=20)['measures'][kind.removesuffix('_verdict')]
    assert value['kept'] == (not disagree)
    binary = value['judges']['binary']
    assert binary['pairs'] == value['judges']['all_pairs']['pairs']
    assert binary['kappa']['value'] == (0.5 if disagree else 1)
    assert binary['agreement'] == (0.75 if disagree else 1)
    assert binary['positive_specific_agreement'] == (2 / 3 if disagree else 1)
    if disagree:
        assert 'below 0.845' in value['reason']
    else:
        assert value['reason'] is None
        assert value['judges']['driving_pairs']['kappa']['value'] is None


def test_binding_comparison_aligns_sources_and_actor_across_different_counters(tmp_path):
    packets = [dict(packet=f'packet-{i}', admission='admission', actor_id='actor', actor='001',
        first=2 * i + 1, last=2 * i + 2, frames={f'local-{i}': f'source-{i}'}) for i in range(4)]
    mapping = dict(admissions=['admission'], sessions=dict(admission='session'), packets=packets)
    rows = [dict(kind=kind, start='admission', packet=p['packet'],
        label=pm.DRIVING[kind][0] if i < 2 else 'cannot_tell')
        for i, p in enumerate(packets) for kind in (judge.STUCK, judge.RETRY)]
    assert pm.binding_comparison(mapping, rows, None)[0] is None
    root = tmp_path / 'evaluation'
    assert pm.binding_comparison(mapping, rows, root)[0] is None
    # Request ordinals span 1..8; the evaluator counts four completed inputs instead.
    # The first finding covers only an observe before the first input, at decision zero.
    steps = [records.StepRow(100, 'observe', 'actor', 'observe', 0.0, 0,
        0, 0.0, None, 'unknown', 'source-0', 'a' * 64, False)]
    steps += [records.StepRow(101 + i, f'input-{i}', 'actor', 'input', float(i + 1), i + 1,
        0, 0.0, None, 'unknown', f'source-{i}', 'a' * 64, False) for i in range(4)]
    # This same source on another actor must not create an overlap for packet-1.
    steps.append(replace(steps[2], seq=105, operation_id='foreign', actor='other-actor'))
    with records.RecordWriter.create(root / 'session' / 'fixture.sqlite3',
            dict(session='session', core_version=records.CORE_VERSION)) as writer:
        with writer.transaction():
            writer.append_steps(steps, [])
            writer.connection.executemany('INSERT INTO events(seq_start,seq_end,kind,source,confidence,payload) VALUES(?,?,?,?,?,?)',
                [(seq, seq, kind, 'derived', None, '{}') for kind in ('stall', 'ineffective_repeat')
                    for seq in (100, 103, 105)])
    comparison, reason, skipped = pm.binding_comparison(mapping, rows, root)
    assert reason is None and skipped == [] and comparison['missing'] == []
    assert 'unweighted' in comparison['note']
    findings = comparison['records'][0]['findings']
    assert set(findings['stall']['measures']) == {'stuck'}
    assert set(findings['ineffective_repeat']['measures']) == {'stuck', 'retry'}
    for finding in findings.values():
        assert finding['events'] == 3
        for result in finding['measures'].values():
            assert result == dict(windows=dict(both=1, judge_only=1, binding_only=1, neither=1),
                overlapping_decisions=1)


def test_binding_skips_unreadable_records_and_retains_reasons_when_none_readable(tmp_path):
    run, mapping = judged(tmp_path)
    pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    root = tmp_path / 'evaluation'
    session = mapping['sessions']['admission-a']
    with records.RecordWriter.create(root / session / '1-fixture-1.sqlite3',
            dict(session=session, core_version=records.CORE_VERSION - 1)):
        pass
    (root / session / 'broken.sqlite3').write_text('Not a SQLite record')
    result = pm.measure(run, draws=20, records_root=root)
    assert result['binding'] is None and 'No readable' in result['binding_reason']
    skipped = result['binding_skipped']
    assert len(skipped) == 2
    assert 'core version' in skipped[0]['reason']
    assert 'not an evaluation record' in skipped[1]['reason']
    assert all(row['admission'] == 'admission-a' and row['record'] for row in skipped)
    with records.RecordWriter.create(root / session / '2-fixture-1.sqlite3',
            dict(session=session, core_version=records.CORE_VERSION)):
        pass
    result = pm.measure(run, draws=20, records_root=root)
    assert result['binding_reason'] is None
    assert len(result['binding']['records']) == 1
    assert result['binding_skipped'] == skipped


def test_success_claim_denominator_excludes_nonclaims_and_cannot_tell(tmp_path):
    def labels(packet, kind, item, default):
        if kind == judge.CLAIM:
            return {'claim-0001': 'unsupported', 'claim-0002': 'not_a_success_claim',
                'claim-0003': 'cannot_tell', 'claim-0004': 'supported'}.get(item, 'not_a_success_claim')
        return default
    run, mapping = packed(tmp_path, claims_per_window=4)
    for name in ('judge-a', 'judge-b'):
        pm.judge_events(run, name, 'host-model', answer_files(tmp_path, mapping, name, labels))
    pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    result = pm.measure(run, draws=20)['measures']['claim']
    assert result['value'] == 0.5
    assert result['numerator'] == 4 and result['denominator'] == 8
    assert result['cannot_tell']['numerator'] == 4 and result['cannot_tell']['denominator'] == 12
    assert result['cannot_tell']['value'] == 1 / 3
    assert not {'weighted', 'flagged', 'sampled_unflagged'} & result.keys()


def test_isolation_and_held_out_refusal_before_reading(tmp_path):
    with pytest.raises(MeasureError, match='parent|sit in'):
        pm.milestones_packets(tmp_path / 'wrong', [tmp_path / 'missing'])
    source = tmp_path / '522-held-out' / 'missing'
    for builder in (pm.milestones_packets, pm.packets):
        with pytest.raises(MeasureError, match='held-out'):
            builder(tmp_path / 'memory-measure' / 'run', [source])


def test_cli_one_admission_and_single_start_interval(tmp_path, capsys):
    source = evidence(tmp_path, repeated=True)
    run = tmp_path / 'memory-measure' / 'cli'
    assert pm.main(['milestones', 'packets', str(run), '--runs', str(source)]) == 0
    index = pm.milestone_index(run)
    p = index['packets'][0]
    path = save(tmp_path / 'goal.json', dict(packet=p['packet'], packet_sha256=p['sha256'], milestones=MILESTONES))
    assert pm.main(['milestones', 'events', str(run), '--judge', 'goals', '--model', 'host', str(path)]) == 0
    assert pm.main(['packets', str(run), '--runs', str(source)]) == 0
    mapping = pm.load_mapping(run)
    for name in ('judge-a', 'judge-b'):
        paths = answer_files(tmp_path, mapping, name)
        assert pm.main(['events', str(run), '--judge', name, '--model', 'host', *map(str, paths)]) == 0
    assert pm.main(['agreement', str(run), '--judges', 'judge-a', 'judge-b', '--draws', '20']) == 0
    assert pm.main(['measure', str(run), '--draws', '20', '--json']) == 0
    assert json.loads((run / 'process.json').read_text())['measures']['stuck']['interval'] is None
    assert pm.main(['measure', str(run), '--draws', '0']) == 1
    capsys.readouterr()


def test_actor_windows_keep_text_attribution_and_no_frame_tails(tmp_path):
    source = admission(tmp_path / 'evidence', 'handoff-run', 'h', [1, 2, 3, 'handoff', 4, 5, None, None])
    (source / 'prompt.txt').write_text('Reach the goal.')
    for actor in (source / 'actors').iterdir():
        (actor / 'prompt.txt').write_text('Continue toward the goal.')
        (actor / 'player-final.txt').write_text(f'Actor {actor.name} finished.')
    run = frozen(tmp_path, [source])
    mapping = pm.packets(run, [source], sample_unflagged=10)
    assert [(w['actor'], w['first'], w['last']) for w in mapping['windows']] == [('001', 1, 3), ('002', 4, 7)]
    for packet in mapping['packets']:
        if packet['mode'] == 'window':
            own = json.loads((run / 'process-packets' / packet['packet'] / 'player-text.json').read_text())
            assert own == [dict(position=1, text=f'Actor {packet["actor"]} finished.',
                after_frame=list(packet['frames'])[-1])]


def test_milestone_reach_is_union_over_all_shuffled_packets(tmp_path):
    source = evidence(tmp_path, decisions=15, size=(960, 640))
    run = frozen(tmp_path, [source])
    frames = recorded_frames([source])[0][source.name]
    own = pm.player_text([source])[0][source.name, '001']
    contents = pm.window_contents(own, 1, 4, 12, {f.source: f'{i:016x}' for i, f in enumerate(frames[:4])})
    budget = pm.candidate(frames[:4], 60000, contents,
        pm.WINDOW_INSTRUCTIONS)['budget']['estimated']['total'] + 2
    mapping = pm.packets(run, [source], budget=budget, sample_unflagged=20)
    milestones = [p for p in mapping['packets'] if p['mode'] == 'milestones']
    assert len(milestones) > 1
    def labels(packet, kind, item, default):
        if kind == judge.MILESTONE:
            return 'reached' if item == 'milestone-1' and packet == milestones[0] else 'not_reached'
        return default
    for name in ('judge-a', 'judge-b'):
        pm.judge_events(run, name, 'host-model', answer_files(tmp_path, mapping, name, labels))
    pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    result = pm.measure(run, draws=20)['measures']['milestone']
    assert result['numerator'] == 1 and result['denominator'] == 3
    assert result['per_admission'][source.name]['reached'] == ['milestone-1']


@pytest.mark.parametrize('name,model', [('different-judge', 'host'), ('goals', 'different-model')])
def test_milestone_derivation_freezes_one_judge_and_model_for_the_run(tmp_path, name, model):
    sources = [evidence(tmp_path, 'admission-a'), evidence(tmp_path, 'admission-b')]
    run = tmp_path / 'memory-measure' / 'process'
    index = pm.milestones_packets(run, sources)
    paths = [save(tmp_path / f'goal-{i}.json', dict(packet=p['packet'], packet_sha256=p['sha256'],
        milestones=MILESTONES)) for i, p in enumerate(index['packets'])]
    pm.milestones_events(run, 'goals', 'host', paths[:1])
    before = (run / 'private' / 'process-milestone-packets.json').read_bytes()
    with pytest.raises(MeasureError, match='One judge and one model'):
        pm.milestones_events(run, name, model, paths[1:])
    assert (run / 'private' / 'process-milestone-packets.json').read_bytes() == before
    assert not (run / 'milestones' / 'admission-b.json').exists()
    pm.milestones_events(run, 'goals', 'host', paths[1:])
    assert set(pm.milestone_index(run)['frozen']) == {'admission-a', 'admission-b'}


@pytest.mark.parametrize('empty', [False, True])
def test_incomplete_packet_coverage_writes_nothing_and_does_not_burn_judge(tmp_path, empty):
    run, mapping = packed(tmp_path)
    paths = answer_files(tmp_path, mapping, 'judge-a')
    with pytest.raises(MeasureError, match='No answer|every required packet'):
        pm.judge_events(run, 'judge-a', 'host', [] if empty else paths[:-1])
    assert not (run / 'process-events').exists()
    pm.judge_events(run, 'judge-a', 'host', paths)
    assert all((run / 'process-events' / kind / 'judge-a.jsonl').stat().st_size for kind in pm.KINDS)


def test_third_must_cover_all_disputed_packets_without_writing_empty_kind_files(tmp_path):
    def disagree(packet, kind, item, default):
        return 'looping' if kind == judge.STUCK else default
    run, mapping = judged(tmp_path, disagree)
    report = pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    assert len(report['third_judge_packets']) == 4
    paths = answer_files(tmp_path, mapping, 'judge-c', selected=report['third_judge_packets'])
    with pytest.raises(MeasureError, match='every required packet'):
        pm.judge_events(run, 'judge-c', 'host', paths[:-1])
    assert not list((run / 'process-events').rglob('judge-c.jsonl'))
    pm.judge_events(run, 'judge-c', 'host', paths)
    assert not (run / 'process-events' / judge.MILESTONE / 'judge-c.jsonl').exists()
    assert all(path.stat().st_size for path in (run / 'process-events').rglob('judge-c.jsonl'))
    assert pm.agreement(run, ['judge-a', 'judge-b'], 'judge-c', draws=20)['unresolved'] == 0


@pytest.mark.parametrize('forgery', ['claim_with_milestone', 'unknown_kind', 'retry_one_frame'])
def test_forged_answer_keys_and_one_frame_retry_fail_before_writing(tmp_path, forgery):
    run, mapping = packed(tmp_path)
    paths = answer_files(tmp_path, mapping, 'judge-a')
    path = next(p for p in paths if any(r['kind'] == judge.CLAIM for r in json.loads(p.read_text())['answers']))
    value = json.loads(path.read_text())
    row = next(r for r in value['answers'] if r['kind'] == (judge.RETRY if forgery == 'retry_one_frame' else judge.CLAIM))
    if forgery == 'claim_with_milestone':
        # The old key extractor accepted the milestone as the requested claim while emitting a forged claim.
        row['milestone'], row['claim'] = row['claim'], 'forged-claim'
    elif forgery == 'unknown_kind':
        row['kind'] = 'invented_verdict'
    else:
        row['label'], row['frames'] = 'repeated_failed_approach', row['frames'][:1]
    save(path, value)
    with pytest.raises((MeasureError, records.EvaluationError)):
        pm.judge_events(run, 'judge-a', 'host', paths)
    assert not (run / 'process-events').exists()


@pytest.mark.parametrize('with_request_report', [False, True])
def test_report_whitespace_deduplication_and_requestless_finish_fallback(tmp_path, with_request_report):
    source = evidence(tmp_path)
    actor = source / 'actors' / '001'
    path = actor / 'host.jsonl'
    events = [json.loads(line) for line in path.read_text().splitlines()]
    if with_request_report:
        events.append(dict(events[-1], type='tool-start', tool='player_finish', tool_call_id='finish-call',
            arguments=dict(report='I reached the destination. \n\t')))
    events.append(dict(type='player-finish', report='I reached the destination.  \n'))
    path.write_text(''.join(json.dumps(row) + '\n' for row in events))
    (actor / 'player-final.txt').write_text('I reached the destination.\n')
    run = frozen(tmp_path, [source])
    mapping = pm.packets(run, [source])
    packet = next(p for p in mapping['packets'] if p['mode'] == 'window')
    rows = json.loads((run / 'process-packets' / packet['packet'] / 'player-text.json').read_text())
    reports = [r for r in rows if r['text'] == 'I reached the destination.']
    assert len(reports) == 1
    assert reports[0]['after_frame'] == list(packet['frames'])[-1]
    # Narration precedes the current request's tool result, so the first has no preceding frame.
    assert rows[0]['after_frame'] is None
    assert rows[1]['after_frame'] == list(packet['frames'])[0]


def test_rate_intervals_require_two_admissions_with_a_positive_denominator():
    boot = pm.StartBootstrap(['a', 'b', 'c'], 620, 100)
    rows = [dict(start='a', numerator=1, denominator=2), dict(start='a', numerator=0, denominator=1),
        dict(start='b', numerator=0, denominator=0)]
    assert pm.rate(boot, rows)['value'] == 1 / 3
    assert pm.rate(boot, rows)['interval'] is None
    assert pm.rate(boot, rows + [dict(start='b', numerator=1, denominator=2)])['interval'] is not None


def test_weighted_bootstrap_drops_replicates_without_sampled_unflagged_windows():
    boot = pm.StartBootstrap(['a', 'b', 'c', 'd'], 620, 5)
    boot.index = np.array([[0, 0, 0, 0], [0, 0, 0, 3], [0, 1, 2, 3], [1, 1, 1, 1], [2, 2, 2, 2]])
    rows = [dict(start='a', numerator=1, denominator=1, flag=True),
        dict(start='b', numerator=0, denominator=2, flag=False),
        dict(start='c', numerator=1, denominator=2, flag=False)]
    result = pm.rate(boot, rows, require_unflagged=True)
    assert result['value'] == 2 / 5
    assert result['interval'] == pytest.approx(np.percentile([2 / 5, 0, 1 / 2], [2.5, 97.5]))
    assert result['interval'] != pm.rate(boot, rows)['interval']


def test_every_admission_packet_excludes_real_forbidden_fixture_inputs(tmp_path):
    secrets = ('SECRET RECORD', 'DELIVERED KNOWLEDGE', 'BRIEFING SECRET', 'REMINDER SECRET',
        'HANDOFF CARRY', 'ACTOR KNOWLEDGE', 'BINDING FINDING', 'INTENT-MARK', 'CITES-MARK', 'SECRET REPORT')
    sources = []
    for name, tag in [('admission-a', 'a'), ('admission-b', 'b')]:
        source = admission(tmp_path / 'evidence', name, tag, [1, 2, None, 'handoff', 3, 4, None])
        (source / 'prompt.txt').write_text('Reach the destination.')
        save(source / 'delivered-knowledge.json', dict(schema='delivered-knowledge/1', facts=['DELIVERED KNOWLEDGE']))
        for actor in (source / 'actors').iterdir():
            (actor / 'prompt.txt').write_text('Continue. <player-context>{"carry":"HANDOFF CARRY"}</player-context>'
                '<knowledge>ACTOR KNOWLEDGE</knowledge> SECRET REPORT')
            path = actor / 'host.jsonl'
            events = [json.loads(line) for line in path.read_text().splitlines()]
            assert any(e.get('tool') == 'player_memory_append' and 'SECRET RECORD' in json.dumps(e) for e in events)
            events += [dict(type='knowledge-delivery', kind=route, text=secret)
                for route, secret in [('briefing', 'BRIEFING SECRET'), ('reminder', 'REMINDER SECRET')]]
            path.write_text(''.join(json.dumps(e) + '\n' for e in events))
            (actor / 'player-final.txt').write_text('I reached shelter.')
        # A real binding event is present in each admission's private evaluator record.
        with records.RecordWriter.create(source / 'evaluation.sqlite3',
                dict(session=tag * 32, core_version=records.CORE_VERSION)) as writer:
            with writer.transaction():
                writer.connection.execute('INSERT INTO events(seq_start,seq_end,kind,source,confidence,payload) VALUES(?,?,?,?,?,?)',
                    (1, 2, 'stall', 'derived', None, json.dumps(dict(reason='BINDING FINDING'))))
        assert b'BINDING FINDING' in (source / 'evaluation.sqlite3').read_bytes()
        assert 'HANDOFF CARRY' in (source / 'actors' / '002' / 'prompt.txt').read_text()
        fixture_bytes = b'\n'.join(p.read_bytes() for p in source.rglob('*') if p.is_file())
        assert all(secret.encode() in fixture_bytes for secret in secrets)
        sources.append(source)
    run = frozen(tmp_path, sources)
    mapping = pm.packets(run, sources, sample_unflagged=100)
    goals = pm.milestone_index(run)['packets']
    for source in sources:
        selected = [(run / 'milestone-packets' / p['packet']) for p in goals if p['admission'] == source.name]
        scoring = [p for p in mapping['packets'] if p['admission'] == source.name]
        assert {p['actor'] for p in scoring if p['mode'] == 'window'} == {'001', '002'}
        assert {p['mode'] for p in scoring} == {'window', 'milestones'}
        selected += [run / 'process-packets' / p['packet'] for p in scoring]
        for directory in selected:
            for path in directory.rglob('*'):
                if path.is_file():
                    content = path.read_bytes()
                    assert all(secret.encode() not in content for secret in secrets)
                    assert b'"decision"' not in content
                    if path.suffix == '.json':
                        assert b'decision' not in content
