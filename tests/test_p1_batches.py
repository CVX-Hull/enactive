"""The P1 judges' input batches and their parsing (#518): synthetic probes, evidence, deliveries and judge files only."""
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import p1_analysis as analysis
from tools import p1_batches as batches
from tools.curator_host import p1_arms as arms
from tools.curator_host import p1_replay as replay
from tools.probe_validation import HELD_OUT_STUDIES

LINEAGES = tuple(analysis.HELD_OUT)
HOST = 'host 9.9'
CANARY_TEXT = 'DELIVERED-CANARY'
CANARY_WORDS = 'CANARY-WHY'
ARM_KEYS = (('A', 1), ('B', 1), ('B', 2))


def spread_hash(rng: random.Random) -> str:
    return format(rng.getrandbits(256), '064x')


def write_frozen(directory: Path, probes: list[dict], candidates: list[dict], plan: dict) -> Path:
    directory.mkdir(parents=True)
    files = {}
    for name, text in (('probes.jsonl', ''.join(json.dumps(r, sort_keys=True) + '\n' for r in probes)),
                       ('candidates.json', json.dumps(dict(candidates=candidates))),
                       ('ledger-plan.json', json.dumps(dict(lineages=plan)))):
        (directory/name).write_text(text)
        files[name] = analysis.file_sha256(directory/name)
    (directory/'frozen.json').write_text(json.dumps(dict(schema=analysis.FROZEN_SCHEMA, files=files)))
    return directory/'probes.jsonl'


def build_world(root: Path, *, items_per_row: int = 3, units: int = 5) -> SimpleNamespace:
    """Four held-out lineages in two frozen directories, a sealed evidence tree, timelines and a delivery."""
    rng = random.Random(7)
    evidence, timelines = root/'evidence', root/'timelines'
    timelines.mkdir()
    by_directory: dict[str, tuple[list, list, dict]] = {'held-out': ([], [], {}), 'held-out-lh4': ([], [], {})}
    delivered = []
    for lineage in LINEAGES:
        runs = analysis.HELD_OUT[lineage]
        study = HELD_OUT_STUDIES[lineage]
        for run in runs:
            sources = evidence/study/'computer-sessions'/run/'sources'
            sources.mkdir(parents=True)
            for n in range(40):
                (sources/f'{run}-{n}.png').write_bytes(b'png')
        run0, run1 = runs[0], runs[1]
        before, after = f'{run0}-001', f'{run1}-001'
        boundary = f'{before}>{after}'
        probes, candidates = by_directory['held-out-lh4' if lineage == 'lh4' else 'held-out'][:2]
        for n in range(1, units + 1):
            pid = f'{lineage}-p{n:04d}'
            probes.append(dict(schema=analysis.PROBES_SCHEMA, id=pid, lineage=lineage, boundary=boundary,
                               later=f'{run1}-{n}', earlier=f'{run0}-{20 + n}', earlier_dhash=spread_hash(rng),
                               confirmed=True, informative=True, what='x'))
            candidates.append(dict(id=pid, lineage=lineage,
                                   earlier_path=f'{study}/computer-sessions/{run0}/sources/{run0}-{20 + n}.png'))
        plan = by_directory['held-out-lh4' if lineage == 'lh4' else 'held-out'][2]
        plan[lineage] = dict(chunks=[dict(chunk=name, timeline=f'{name}.md', required_frames=[f'{name[:-4]}-1', f'{name[:-4]}-2'],
                                          incoming_boundary=None) for name in (before, after)])
        for name in (before, after):
            (timelines/f'{name}.md').write_text(f'timeline of {name}')
        received = f'{CANARY_TEXT} received by {after}'
        marker = arms.Boundary(name=boundary, kind='handoff', predecessor=before, successor=after, cutoff=1.0,
                               admission=1, received_path=Path('unused'))
        sha = 'f' * 64
        delivered.append(replay._row(lineage, marker, 'R', 1, received, sha, None))
        for arm, repeat in ARM_KEYS:
            word = 'alpha' if arm == 'A' else ('beta' if repeat == 1 else 'gamma')    # the statement never names its arm
            items = [arms.Item('note', f'{lineage} {word} statement {k}',
                               cites=(f'{run0}-{1 + k % 3}', 'unsealed-frame-9')) for k in range(items_per_row)]
            delivered.append(replay._row(lineage, marker, arm, repeat, received, sha, arms.render(items)))
    rows = by_directory['held-out'][0] + by_directory['held-out-lh4'][0]
    paths = [write_frozen(root/name, *parts) for name, parts in by_directory.items()]
    path = root/'delivered.jsonl'
    path.write_text(''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in delivered))
    return SimpleNamespace(root=root, evidence=evidence, timelines=timelines, probes=paths, delivered=path,
                           rows=[r for r in rows], delivered_rows=delivered)


@pytest.fixture
def world(tmp_path):
    return build_world(tmp_path)


def read_all(directory: Path) -> dict[str, bytes]:
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in sorted(directory.rglob('*')) if p.is_file()}


def run(world, kind: str, out: Path, *extra: str, capsys=None) -> int:
    probes = [a for p in world.probes for a in ('--probes', str(p))] if kind != 'guess' else []
    return analysis.main(['batches', kind, *probes, '--delivered', str(world.delivered), '--evidence-root', str(world.evidence),
                          '--out', str(out), '--host-version', HOST, *extra])


def build(world, kind: str, name: str | None = None, *extra: str) -> Path:
    out = world.root/'out'/(name or kind)
    assert run(world, kind, out, '--timelines', str(world.timelines), *extra) == 0
    return out


def key_of(out: Path, kind: str) -> dict:
    return json.loads((out/'keys'/f'{kind}.json').read_text())


def batch_files(out: Path, kind: str) -> list[dict]:
    prefix = batches.KINDS[kind]['prefix']
    return [json.loads(p.read_text()) for p in sorted((out/'batches').glob(f'{prefix}-*.json'))]


# ------------------------------------------------------------------ the frozen briefs
def page_brief(label: str) -> str:
    text = (analysis.ROOT/'docs'/'design'/'p1-study-2.md').read_text()
    paragraph = next(p for p in text.split('\n\n') if p.startswith(f'> **{label}.**'))
    joined = ' '.join(line[1:].strip() for line in paragraph.splitlines())
    assert joined.startswith(f'**{label}.** ')
    return joined[len(f'**{label}.** '):]


@pytest.mark.parametrize('label, start, end', [
    ('Scoring', 'You check whether a text states what a screenshot shows.', '{"id":"<id>","stated":true|false,"why":"<one line>"}.'),
    ('Audit', 'You check statements against recorded screenshots.', '"why":"<one line>"}.'),
    ('Arm guess', 'Each text in the file [batch] was produced by one of two systems', '{"id":"<id>","system":"1"|"2"}.')])
def test_the_frozen_briefs_are_the_pre_registrations_text_word_for_word(label, start, end):
    brief = batches.frozen_brief(label)
    assert brief == page_brief(label)
    assert brief.startswith(start) and brief.endswith(end) and '**' not in brief and '\n' not in brief


def test_a_brief_the_page_does_not_have_is_refused(tmp_path):
    doc = tmp_path/'page.md'
    doc.write_text('> **Confirmation.** something\n')
    with pytest.raises(batches.BatchError, match='Scoring brief was not found'):
        batches.frozen_brief('Scoring', doc)


# ------------------------------------------------------------------ scoring batches
def test_scoring_batches_hold_one_item_per_unit_arm_and_repeat_with_only_an_id_a_frame_and_a_text(world, capsys):
    out = build(world, 'scoring')
    summary = json.loads(capsys.readouterr().out)
    files, key = batch_files(out, 'scoring'), key_of(out, 'scoring')
    units = analysis.units(analysis.primary_probes(world.rows))
    assert len(units) == 20 and summary['items'] == 60 == len(key['items']) and summary['batches'] == len(files)
    assert set(summary) == {'kind', 'items', 'batches', 'key_sha256', 'batches_sha256'}
    brief = batches.frozen_brief('Scoring')
    delivered = {(r['lineage'], r['boundary'], r['arm'], r['repeat']): r for r in world.delivered_rows}
    by_probe = {u['probe']: u for u in units}
    seen = set()
    for batch in files:
        assert set(batch) == {'schema', 'brief', 'items'} and batch['brief'] == brief
        assert 0 < len(batch['items']) <= 10
        in_batch = []
        for item in batch['items']:
            assert set(item) == {'id', 'frame', 'text'}                     # never the arm, repeat, lineage or probe
            meta = key['items'][item['id']]
            assert meta['kind'] == 'reobservation' and (meta['arm'], meta['repeat']) in ARM_KEYS
            unit = by_probe[meta['item']]
            assert item['text'] == delivered[(unit['lineage'], unit['boundary'], meta['arm'], meta['repeat'])]['text']
            assert Path(item['frame']).is_absolute() and Path(item['frame']).is_file()
            assert Path(item['frame']).is_relative_to(world.evidence.resolve())
            in_batch.append(meta['item'])
            seen.add((meta['arm'], meta['repeat'], meta['item']))
        assert len(set(in_batch)) == len(in_batch)                         # no two texts for one unit in a batch
        raw = json.dumps(batch)
        assert not any(u['probe'] in raw for u in units) and '"arm"' not in raw and 'repeat' not in raw
    assert seen == {(arm, repeat, u['probe']) for u in units for arm, repeat in ARM_KEYS}
    assert key['schema'] == batches.KEY_SCHEMA and key['host_version'] == HOST and key['seed'] == 4911
    assert [b['name'] for b in key['batches']] == [f'score-{n:03d}' for n in range(1, len(files) + 1)]
    assert all(i.startswith('s') for i in key['items'])
    assert len({k['arm'] for b in files[:1] for k in (key['items'][i['id']] for i in b['items'])}) > 1   # mixed, not by arm


def test_the_unit_frame_is_the_probes_earlier_frame_under_the_evidence_root(world):
    out = build(world, 'scoring')
    key = key_of(out, 'scoring')
    for batch in batch_files(out, 'scoring'):
        for item in batch['items']:
            lineage = key['items'][item['id']]['item'].split('-')[0]
            run = analysis.HELD_OUT[lineage][0]
            number = int(key['items'][item['id']]['item'].rsplit('p', 1)[1])
            expected = world.evidence/HELD_OUT_STUDIES[lineage]/'computer-sessions'/run/'sources'/f'{run}-{20 + number}.png'
            assert Path(item['frame']) == expected.resolve()


def test_batches_are_reproducible_byte_for_byte_and_follow_the_seed(world, monkeypatch):
    first, second = build(world, 'scoring', 'one'), build(world, 'scoring', 'two')
    assert read_all(first) == read_all(second) and read_all(first)
    monkeypatch.setattr(batches, 'SCORING_SEED', 4912)
    other = build(world, 'scoring', 'three')
    assert read_all(other)['batches/score-001.json'] != read_all(first)['batches/score-001.json']
    for kind in ('rejudge', 'audit'):
        assert read_all(build(world, kind, f'{kind}-1')) == read_all(build(world, kind, f'{kind}-2'))


def test_the_order_is_a_seeded_shuffle_of_the_sorted_items_with_random_4911(world):
    out = build(world, 'scoring')
    key = key_of(out, 'scoring')
    units = analysis.units(analysis.primary_probes(world.rows))
    expected = sorted((u['probe'], arm, repeat) for u in units for arm, repeat in ARM_KEYS)
    random.Random(4911).shuffle(expected)
    ordered = [key['items'][i] for b in key['batches'] for i in b['ids']]
    got = [(m['item'], m['arm'], m['repeat']) for m in ordered]
    assert sorted(got) == sorted(expected) and got != sorted(got)
    # the first batch is the first ten of the shuffle that do not share a unit
    assert got[:3] == expected[:3]


def test_a_batch_never_holds_two_texts_of_one_unit_even_when_a_unit_would_straddle_a_boundary(world):
    entries = [dict(sort=(n, arm), unit=n, public={}, key={}) for n in range(4) for arm in 'abc']
    for seed in range(20):
        for batch in batches.pack(entries, seed):
            assert len(batch) <= 10 and len({e['unit'] for e in batch}) == len(batch)
    assert sum(map(len, batches.pack(entries, 1))) == 12


# ------------------------------------------------------------------ re-judge batches
def test_rejudge_batches_hold_exactly_the_seeded_sample_with_fresh_ids_and_their_own_key(world):
    scoring, rejudge = build(world, 'scoring'), build(world, 'rejudge')
    units = analysis.units(analysis.primary_probes(world.rows))
    key = key_of(rejudge, 'rejudge')
    got = {('reobservation', m['arm'], m['repeat'], m['item']) for m in key['items'].values()}
    assert got == analysis.rejudge_sample(units) and len(got) == 12 and key['sample_seed'] == 4912
    assert all(i.startswith('r') for i in key['items']) and not set(key['items']) & set(key_of(scoring, 'scoring')['items'])
    for batch in batch_files(rejudge, 'rejudge'):
        assert batch['brief'] == batches.frozen_brief('Scoring') and len(batch['items']) <= 10
        assert all(set(i) == {'id', 'frame', 'text'} for i in batch['items'])
        units_here = [key['items'][i['id']]['item'] for i in batch['items']]
        assert len(set(units_here)) == len(units_here)
    assert [b['name'] for b in key['batches']][0] == 'rejudge-001'


# ------------------------------------------------------------------ audit batches
def test_audit_batches_draw_up_to_forty_pairs_per_arm_and_repeat_with_random_4913(tmp_path, capsys):
    big = build_world(tmp_path, items_per_row=15)
    out = build(big, 'audit')
    summary = json.loads(capsys.readouterr().out)
    assert summary['drawn'] == {'A1': 40, 'B1': 40, 'B2': 40} and summary['items'] == 120
    key = key_of(out, 'audit')
    for arm, repeat in ARM_KEYS:
        universe = [(lineage, big_boundary(lineage), n) for lineage in LINEAGES for n in range(15)]
        expected = {f'{lineage}/{boundary}#{n}' for lineage, boundary, n in random.Random(4913).sample(universe, 40)}
        assert {m['item'] for m in key['items'].values() if (m['arm'], m['repeat']) == (arm, repeat)} == expected
    assert key['draw_seed'] == 4913 and key['seed'] == 4913


def big_boundary(lineage: str) -> str:
    runs = analysis.HELD_OUT[lineage]
    return f'{runs[0]}-001>{runs[1]}-001'


def test_an_arm_with_fewer_than_forty_delivered_items_is_audited_in_full(world, capsys):
    build(world, 'audit')
    assert json.loads(capsys.readouterr().out)['drawn'] == {'A1': 12, 'B1': 12, 'B2': 12}


def test_audit_items_show_the_statement_its_cited_frames_and_the_predecessors_timeline_without_the_arm(world, capsys):
    out = build(world, 'audit')
    summary = json.loads(capsys.readouterr().out)
    key = key_of(out, 'audit')
    delivered = {(r['lineage'], r['boundary'], r['arm'], r['repeat']): r for r in world.delivered_rows}
    files = batch_files(out, 'audit')
    assert summary['batches'] == len(files) and all(0 < len(b['items']) <= 10 for b in files)
    assert summary['unresolved_cites'] == 36                 # each of the 36 pairs cites one frame that is not sealed
    mixed = [(key['items'][i['id']]['arm'], key['items'][i['id']]['repeat']) for b in files[:1] for i in b['items']]
    assert len(set(mixed)) > 1
    for batch in files:
        assert batch['brief'] == batches.frozen_brief('Audit') and set(batch) == {'schema', 'brief', 'items'}
        for item in batch['items']:
            assert set(item) == {'id', 'statement', 'cited_frames', 'timeline', 'timeline_frames'}
            meta = key['items'][item['id']]
            lineage, rest = meta['item'].split('/')
            boundary, position = rest.rsplit('#', 1)
            row = delivered[(lineage, boundary, meta['arm'], meta['repeat'])]
            shown = row['working_set'][int(position)]
            assert item['statement'] == f'- {shown["statement"]}'
            assert item['statement'] in row['text'].splitlines()          # the line as the successor's text has it
            runs = analysis.HELD_OUT[lineage]
            study = world.evidence/HELD_OUT_STUDIES[lineage]/'computer-sessions'/runs[0]/'sources'
            assert [f['source'] for f in item['cited_frames']] == [shown['cites'][0]]   # the unsealed one is dropped
            assert all(Path(f['frame']) == (study/f'{f["source"]}.png').resolve() for f in item['cited_frames'])
            assert Path(item['timeline']) == (world.timelines/f'{runs[0]}-001.md').resolve()
            assert [f['source'] for f in item['timeline_frames']] == [f'{runs[0]}-1', f'{runs[0]}-2']
            assert set(meta['frames']) == {f['source'] for f in item['cited_frames'] + item['timeline_frames']}
            raw = json.dumps(item)
            assert '"arm"' not in raw and '"repeat"' not in raw


def test_audit_refuses_a_missing_timeline_a_missing_arm_and_an_incomplete_row(world, tmp_path):
    frozen = batches.Frozen(world.probes)
    delivered = batches.read_delivered([world.delivered])
    (world.timelines/f'{analysis.HELD_OUT["lh1"][0]}-001.md').unlink()
    with pytest.raises(batches.BatchError, match='no timeline'):
        batches.audit_batches(frozen, delivered, world.evidence.resolve(), world.timelines, tmp_path/'o1', HOST)
    (world.timelines/f'{analysis.HELD_OUT["lh1"][0]}-001.md').write_text('t')
    without = {k: v for k, v in delivered.items() if k[2:] != ('B', 2)}
    with pytest.raises(batches.BatchError, match='A1, B1 and B2'):
        batches.audit_batches(frozen, without, world.evidence.resolve(), world.timelines, tmp_path/'o2', HOST)
    broken = {k: dict(v, complete=False) if k[2] == 'A' else v for k, v in delivered.items()}
    with pytest.raises(batches.BatchError, match='incomplete'):
        batches.audit_batches(frozen, broken, world.evidence.resolve(), world.timelines, tmp_path/'o3', HOST)


# ------------------------------------------------------------------ arm-guess batch
def dev_delivered(boundaries=20, empty=0, repeats=(1, 2)) -> dict:
    out = {}
    for n in range(boundaries):
        for arm, repeat in (('R', 1), ('A', 1), *(('B', r) for r in repeats)):
            items = 0 if arm == 'R' or n < empty else 2
            out[('397', f'b{n:02d}', arm, repeat)] = dict(schema='p1-delivered/2', lineage='397', boundary=f'b{n:02d}',
                                                         arm=arm, repeat=repeat, text=f'{arm}{repeat} text {n}',
                                                         items=items, complete=True)
    return out


def test_the_guess_batch_has_15_texts_from_each_arm_in_a_seeded_order_with_ids_and_texts_only(tmp_path):
    out = tmp_path/'g'
    summary = batches.guess_batches(dev_delivered(), out, HOST)
    (batch,) = batch_files(out, 'guess')
    key = key_of(out, 'guess')
    assert summary['items'] == 30 and summary['batches'] == 1
    assert batch['brief'] == batches.frozen_brief('Arm guess') and len(batch['items']) == 30
    assert all(set(i) == {'id', 'text'} and i['id'].startswith('g') for i in batch['items'])
    arms_ = [key['items'][i['id']]['arm'] for i in batch['items']]
    assert (arms_.count('A'), arms_.count('B')) == (15, 15) and arms_ != sorted(arms_)
    texts = {i['text'] for i in batch['items']}
    assert all(t.startswith(('A1', 'B1')) for t in texts)          # B's repeat 1, never R and never B2
    assert key['b_repeat'] == 1 and key['seed'] == 4914
    again = tmp_path/'g2'
    batches.guess_batches(dev_delivered(), again, HOST)
    assert read_all(out) == read_all(again)


def test_the_guess_batch_draws_only_texts_with_a_working_set_and_needs_15_of_them(tmp_path):
    batches.guess_batches(dev_delivered(boundaries=20, empty=5), tmp_path/'ok', HOST)
    (batch,) = batch_files(tmp_path/'ok', 'guess')
    assert all(int(i['text'].split()[-1]) >= 5 for i in batch['items'])
    with pytest.raises(batches.BatchError, match='needs 15'):
        batches.guess_batches(dev_delivered(boundaries=20, empty=6), tmp_path/'few', HOST)
    incomplete = dev_delivered()
    incomplete[('397', 'b00', 'A', 1)]['complete'] = False
    with pytest.raises(batches.BatchError, match='incomplete'):
        batches.guess_batches(incomplete, tmp_path/'partial', HOST)


def test_the_guess_command_needs_only_the_delivery(tmp_path, capsys):
    delivered = tmp_path/'delivered.jsonl'
    delivered.write_text(''.join(json.dumps(r) + '\n' for r in dev_delivered().values()))
    assert analysis.main(['batches', 'guess', '--delivered', str(delivered), '--out', str(tmp_path/'g'),
                          '--host-version', HOST]) == 0
    assert json.loads(capsys.readouterr().out)['items'] == 30


# ------------------------------------------------------------------ refusals when building
def test_the_commands_print_only_counts_and_digests(world, capsys):
    for kind in ('scoring', 'rejudge', 'audit'):
        build(world, kind)
    printed = capsys.readouterr().out
    for private in (CANARY_TEXT, 'png', 'statement', '/', 'lh1-p0001', 'unsealed-frame'):
        assert private not in printed
    assert all(json.loads(line) for line in printed.splitlines())


def test_building_refuses_missing_inputs_and_prints_no_content(world, tmp_path, capsys):
    next(iter((world.evidence/HELD_OUT_STUDIES['lh2']/'computer-sessions').rglob('lh2a1-21.png'))).unlink()
    assert run(world, 'scoring', tmp_path/'o') == 2
    error = capsys.readouterr().err
    assert '3 earlier frames missing' in error and CANARY_TEXT not in error and 'lh2a1-21' not in error   # A1, B1, B2
    rows = [r for r in world.delivered_rows if (r['lineage'], r['arm'], r['repeat']) != ('lh3', 'B', 2)]
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert run(world, 'scoring', tmp_path/'q') == 2 and '5 delivered texts missing' in capsys.readouterr().err


def test_building_refuses_an_incomplete_delivery_a_changed_probes_file_and_a_second_write(world, tmp_path, capsys):
    out = build(world, 'scoring')
    capsys.readouterr()
    assert run(world, 'scoring', out) == 2 and 'written once' in capsys.readouterr().err
    rows = [dict(r, complete=False) if r['arm'] == 'B' else r for r in world.delivered_rows]
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert run(world, 'scoring', tmp_path/'o2') == 2 and 'incomplete' in capsys.readouterr().err
    with world.probes[0].open('a') as stream:
        stream.write('\n')
    assert run(world, 'scoring', tmp_path/'o3') == 2
    assert 'not a frozen held-out probes file' in capsys.readouterr().err


def test_a_candidates_file_that_differs_from_its_freeze_is_refused(world, tmp_path, capsys):
    (world.probes[0].parent/'candidates.json').write_text(json.dumps(dict(candidates=[])))
    assert run(world, 'scoring', tmp_path/'o') == 2 and 'not a frozen file' in capsys.readouterr().err


def test_the_probes_must_cover_every_held_out_lineage(world, tmp_path, capsys):
    code = analysis.main(['batches', 'scoring', '--probes', str(world.probes[0]), '--delivered', str(world.delivered),
                          '--evidence-root', str(world.evidence), '--out', str(tmp_path/'o'), '--host-version', HOST])
    assert code == 2 and 'exactly the held-out lineages' in capsys.readouterr().err


def test_the_judge_files_hold_absolute_paths_so_the_output_must_stay_out_of_the_tracked_tree(world, capsys):
    assert run(world, 'scoring', analysis.ROOT/'data'/'p1-batches-test') == 2
    assert 'outside the repository' in capsys.readouterr().err
    assert not (analysis.ROOT/'data'/'p1-batches-test').exists()


# ------------------------------------------------------------------ parsing
def answers_for(out: Path, kind: str, make, name: str = 'answers') -> Path:
    key = key_of(out, kind)
    dest = out.parent/f'{out.name}-{name}'
    dest.mkdir(parents=True)
    for batch in key['batches']:
        (dest/f'{batch["name"]}.jsonl').write_text(
            ''.join(json.dumps(make(i, key['items'][i])) + '\n' for i in batch['ids']))
    return dest


def label_answer(opaque, meta):
    return dict(id=opaque, stated=int(opaque[1:]) % 3 != 0, why=CANARY_WORDS)


def audit_answer(opaque, meta):
    number = int(opaque[1:])
    return dict(id=opaque, false=number % 5 == 0, frame=meta['frames'][0] if number % 5 == 0 else None, why=CANARY_WORDS)


def guess_answer(opaque, meta):
    even = int(opaque[1:]) % 2 == 0     # right for exactly half of the 30
    return dict(id=opaque, system=('1' if meta['arm'] == 'A' else '2') if even else ('2' if meta['arm'] == 'A' else '1'))


def parsed(out: Path, kind: str, make, tmp_path: Path) -> list[dict]:
    answers = answers_for(out, kind, make)
    rows_file = tmp_path/f'{kind}-rows.jsonl'
    assert analysis.main(['parse', kind, '--batches', str(out), '--answers', str(answers), '--out', str(rows_file)]) == 0
    return [json.loads(line) for line in rows_file.read_text().splitlines()]


def test_parsed_rows_are_in_the_shapes_the_analysis_accepts_and_the_whole_study_scores(world, tmp_path, capsys):
    scoring, rejudge = build(world, 'scoring'), build(world, 'rejudge')
    audit = build(world, 'audit')
    guess = build_guess(tmp_path)
    capsys.readouterr()
    first, second = parsed(scoring, 'scoring', label_answer, tmp_path), parsed(rejudge, 'rejudge', label_answer, tmp_path)
    audits, guesses = parsed(audit, 'audit', audit_answer, tmp_path), parsed(guess, 'guess', guess_answer, tmp_path)
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == dict(
        kind='guess', rows=30, rows_sha256=analysis.file_sha256(tmp_path/'guess-rows.jsonl'))
    assert len(first) == 60 and all(r['type'] == 'label' and r['kind'] == 'reobservation' and 'rejudge' not in r for r in first)
    assert len(second) == 12 and all(r['rejudge'] is True for r in second)
    assert {(r['arm'], r['repeat']) for r in first} == set(ARM_KEYS) and all(isinstance(r['stated'], bool) for r in first)
    assert len(audits) == 36 and all(r['type'] == 'audit' and isinstance(r['false'], bool) for r in audits)
    assert len(guesses) == 30 and all(r['type'] == 'guess' and r['guess'] in '12' for r in guesses)
    assert CANARY_WORDS not in json.dumps([first, second, audits, guesses])
    costs = [dict(type='cost', schema=analysis.SCORE_SCHEMA, repeat=r, lineage='lh1', curator_dollars=1.0, actor_dollars=2.0,
                  stopped_by_cap=False) for r in (1, 2)]
    result = analysis.score(world.rows, {name: 10.0 for name in LINEAGES}, first + second + audits + guesses + costs)
    assert result['probes']['units'] == 20 and result['judge_agreement']['n'] == 12
    assert result['arm_guessing'] == dict(n=30, correct=15, limit=analysis.guess_limit(), leaks=False)
    assert {'A1', 'B1', 'B2'} <= set(result['figures'])


def build_guess(tmp_path: Path) -> Path:
    out = tmp_path/'out'/'guess'
    batches.guess_batches(dev_delivered(), out, HOST)
    return out


def broken_scoring(world, mutate, tmp_path):
    out = build(world, 'scoring')
    answers = answers_for(out, 'scoring', label_answer)
    mutate(answers, key_of(out, 'scoring'))
    with pytest.raises(batches.BatchError) as raised:
        batches.parse('scoring', out, answers)
    assert 'SECRET' not in str(raised.value) and CANARY_WORDS not in str(raised.value)
    return str(raised.value)


def lines_of(answers: Path, name: str = 'score-001.jsonl') -> list[str]:
    return (answers/name).read_text().splitlines()


def rewrite(answers: Path, lines: list[str], name: str = 'score-001.jsonl') -> None:
    (answers/name).write_text('\n'.join(lines) + '\n')


@pytest.mark.parametrize('mutate, message', [
    (lambda a, k: (a/'score-002.jsonl').unlink(), 'missing batch outputs: score-002.jsonl'),
    (lambda a, k: (a/'notes.txt').write_text('x'), 'belong to no batch: notes.txt'),
    (lambda a, k: (a/'score-001.jsonl').with_name('score-001.json').write_text(''), 'belong to no batch: score-001.json'),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), id='SECRET-ID')), *lines_of(a)[1:]]),
     r"score-001.jsonl:1: id is not in the batch's key"),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), id=k['batches'][1]['ids'][0])), *lines_of(a)[1:]]),
     r"score-001.jsonl:1: id is not in the batch's key"),
    (lambda a, k: rewrite(a, [lines_of(a)[0], lines_of(a)[0], *lines_of(a)[2:]]), r'score-001.jsonl:2: duplicated id s'),
    (lambda a, k: rewrite(a, lines_of(a)[:-1]), r'score-001.jsonl: 1 ids missing \(first s'),
    (lambda a, k: rewrite(a, [lines_of(a)[1], lines_of(a)[0], *lines_of(a)[2:]]), 'not in batch order'),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), extra=1)), *lines_of(a)[1:]]),
     r"score-001.jsonl:1: not exactly the brief's JSON shape"),
    (lambda a, k: rewrite(a, [json.dumps({x: y for x, y in json.loads(lines_of(a)[0]).items() if x != 'why'}), *lines_of(a)[1:]]),
     r"score-001.jsonl:1: not exactly the brief's JSON shape"),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), stated='true')), *lines_of(a)[1:]]),
     r'score-001.jsonl:1: field stated \(id s'),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), why=7)), *lines_of(a)[1:]]),
     r'score-001.jsonl:1: field why \(id s'),
    (lambda a, k: rewrite(a, ['SECRET words, not json', *lines_of(a)[1:]]), r'score-001.jsonl:1: not JSON'),
    (lambda a, k: rewrite(a, [lines_of(a)[0], '', *lines_of(a)[1:]]), r'score-001.jsonl:2: not JSON'),
    (lambda a, k: rewrite(a, ['[1, 2]', *lines_of(a)[1:]]), r"score-001.jsonl:1: not exactly the brief's JSON shape"),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), id=7)), *lines_of(a)[1:]]),
     r"score-001.jsonl:1: id is not in the batch's key"),
])
def test_scoring_output_that_is_not_exactly_the_briefs_shape_is_refused_without_judge_text(world, tmp_path, mutate, message):
    import re
    assert re.search(message, broken_scoring(world, mutate, tmp_path))


def test_an_empty_output_file_for_a_batch_is_refused(world, tmp_path):
    out = build(world, 'scoring')
    answers = answers_for(out, 'scoring', label_answer)
    (answers/'score-001.jsonl').write_text('')
    with pytest.raises(batches.BatchError, match=r'score-001.jsonl: \d+ ids missing'):
        batches.parse('scoring', out, answers)


def test_audit_output_must_name_null_or_a_frame_listed_for_that_item(world, tmp_path):
    out = build(world, 'audit')
    answers = answers_for(out, 'audit', audit_answer)
    first = json.loads(lines_of(answers, 'audit-001.jsonl')[0])
    rewrite(answers, [json.dumps(dict(first, frame='SECRET-FRAME')), *lines_of(answers, 'audit-001.jsonl')[1:]], 'audit-001.jsonl')
    with pytest.raises(batches.BatchError, match=r'audit-001.jsonl:1: frame \(id a') as raised:
        batches.parse('audit', out, answers)
    assert 'SECRET' not in str(raised.value)
    mine = key_of(out, 'audit')['items'][first['id']]['frames']
    foreign = next(m['frames'][0] for m in key_of(out, 'audit')['items'].values() if m['frames'][0] not in mine)
    rewrite(answers, [json.dumps(dict(first, frame=foreign)), *lines_of(answers, 'audit-001.jsonl')[1:]], 'audit-001.jsonl')
    with pytest.raises(batches.BatchError, match='not null or a frame listed'):
        batches.parse('audit', out, answers)


def test_guess_output_must_say_system_1_or_2(tmp_path):
    out = build_guess(tmp_path)
    answers = answers_for(out, 'guess', guess_answer)
    lines = lines_of(answers, 'guess-001.jsonl')
    rewrite(answers, [json.dumps(dict(json.loads(lines[0]), system='3')), *lines[1:]], 'guess-001.jsonl')
    with pytest.raises(batches.BatchError, match=r'guess-001.jsonl:1: field system \(id g'):
        batches.parse('guess', out, answers)


def test_the_rows_file_is_written_once_and_a_missing_key_is_refused(world, tmp_path, capsys):
    out = build(world, 'scoring')
    answers = answers_for(out, 'scoring', label_answer)
    rows = tmp_path/'rows.jsonl'
    args = ['parse', 'scoring', '--batches', str(out), '--answers', str(answers), '--out', str(rows)]
    assert analysis.main(args) == 0 and analysis.main(args) == 2
    assert '--out exists' in capsys.readouterr().err
    assert analysis.main(['parse', 'rejudge', '--batches', str(out), '--answers', str(answers), '--out', str(tmp_path/'r2')]) == 2
    assert 'no readable key file for rejudge' in capsys.readouterr().err
