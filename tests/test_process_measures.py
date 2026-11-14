"""Portable process evidence checks (#620): R-FALSE-CLAIM, R-EVIDENCE-LOSS and R-GAME-COUPLING.

Synthetic traces exercise packet isolation, sampling, frozen goals and judge ingress. They establish no real
play outcome or judge quality; independent prompt review and sealed-lineage judging belong to the lead.
"""
from copy import deepcopy
from dataclasses import replace
import json

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


def test_packets_hide_filter_memory_and_frame_order_and_cap_claims(tmp_path):
    run, mapping = packed(tmp_path, claims_per_window=2, sample_unflagged=1)
    assert mapping['sampling'] == dict(flagged=1, unflagged=3, sampled_unflagged=1, unflagged_fraction=1 / 3)
    assert sum(row['judged'] for row in mapping['windows']) == 2
    assert all(row['first'] < row['last'] for row in mapping['windows'])
    assert all(len(row['claims']) == 2 and row['claims_cut'] == 18 for row in mapping['windows'])
    for packet in mapping['packets']:
        directory = run / 'process-packets' / packet['packet']
        manifest = verify_packet(directory, packet['sha256'])
        content = '\n'.join(p.read_text() for p in directory.iterdir() if p.is_file())
        for secret in ('admission-a', 'INTENT-MARK', 'CITES-MARK', 'SECRET RECORD', 'SECRET REPORT', 'FALLIBLE HANDOFF GOAL',
                       'sampling_fraction', 'claims_cut', '"flag"', 'decision', 'aaaaaaa-'):
            if secret == 'decision':  # the instructions describe windows, but JSON carries no original decisions
                assert secret not in json.dumps(manifest)
            else:
                assert secret not in content
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
            assert all(set(row) == {'position', 'text'} for row in json.loads((directory / 'player-text.json').read_text()))
    for packet in (run / 'milestone-packets').iterdir():
        assert not (packet / 'frames').exists()
        assert set(json.loads((packet / 'goals.json').read_text())) == {'mission'}


def test_window_budget_counts_serialized_text_and_never_splits_decisions(tmp_path):
    source = evidence(tmp_path, decisions=15, size=(960, 640))
    run = frozen(tmp_path, [source])
    frames = recorded_frames([source])[0][source.name]
    own = pm.player_text([source])[0][source.name, '001']
    contents = pm.window_contents(own, 1, 4, 12)
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
@pytest.mark.parametrize('bad', ['label', 'citations', 'pair_twice', 'hash'])
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
        assert set(event.cited_frames) <= set(packet['frames'].values())
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


def test_binding_comparison_joins_decisions_and_has_null_reason(tmp_path):
    run, mapping = packed(tmp_path)
    def labels(packet, kind, item, default):
        return 'no_repeat' if kind == judge.RETRY else default
    for name in ('judge-a', 'judge-b'):
        pm.judge_events(run, name, 'host-model', answer_files(tmp_path, mapping, name, labels))
    pm.agreement(run, ['judge-a', 'judge-b'], draws=20)
    root = tmp_path / 'evaluation'
    assert pm.measure(run, draws=20, records_root=root)['binding'] is None
    session = mapping['sessions']['admission-a']
    with records.RecordWriter.create(root / session / '2-fixture-1.sqlite3',
            dict(session=session, core_version=records.CORE_VERSION)) as writer:
        with writer.transaction():
            writer.append_steps([records.StepRow(100 + i, f'op-{i}', 'actor', 'input', float(i), i,
                0, 0.0, None, 'unknown', f'source-{i}', 'a' * 64, False) for i in range(1, 7)], [])
            writer.connection.executemany('INSERT INTO events(seq_start,seq_end,kind,source,confidence,payload) VALUES(?,?,?,?,?,?)',
                [(102, 104, kind, 'derived', None, '{}') for kind in ('stall', 'ineffective_repeat')])
    result = pm.measure(run, draws=20, records_root=root)
    assert result['binding_reason'] is None
    binding = result['binding']
    assert len(binding['missing']) == 3
    assert result['binding_skipped'] == []
    assert 'unweighted' in binding['note']
    findings = binding['records'][0]['findings']
    assert set(findings['stall']['measures']) == {'stuck'}
    assert set(findings['ineffective_repeat']['measures']) == {'stuck', 'retry'}
    for finding in findings.values():
        assert finding['events'] == 1
        assert finding['measures']['stuck'] == dict(windows=dict(both=1, judge_only=0, binding_only=0, neither=0),
            overlapping_decisions=3)
    assert findings['ineffective_repeat']['measures']['retry'] == dict(
        windows=dict(both=0, judge_only=0, binding_only=1, neither=0), overlapping_decisions=0)


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
            assert own == [dict(position=1, text=f'Actor {packet["actor"]} finished.')]


def test_milestone_reach_is_union_over_all_shuffled_packets(tmp_path):
    source = evidence(tmp_path, decisions=15, size=(960, 640))
    run = frozen(tmp_path, [source])
    frames = recorded_frames([source])[0][source.name]
    own = pm.player_text([source])[0][source.name, '001']
    budget = pm.candidate(frames[:4], 60000, pm.window_contents(own, 1, 4, 12),
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
