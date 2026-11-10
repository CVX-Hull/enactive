"""The P1 judges' input batches and their parsing (#518): synthetic probes, evidence, deliveries and judge files only."""
import json
import random
import re
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
    evidence = root/'evidence'
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
                                          incoming_boundary=incoming) for name, incoming in ((before, None), (after, boundary))])
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
    return SimpleNamespace(root=root, evidence=evidence, probes=paths, delivered=path,
                           rows=[r for r in rows], delivered_rows=delivered)


@pytest.fixture(autouse=True)
def runtime(tmp_path, monkeypatch):
    """The judge files stay under the repository's .runtime/: a temporary repository root for every test."""
    monkeypatch.setattr(batches, 'ROOT', tmp_path)
    return tmp_path/'.runtime'


@pytest.fixture
def world(tmp_path):
    return build_world(tmp_path)


def number(opaque: str) -> int:
    """The counter of an opaque id `<letter><8 hex>-<counter>`."""
    return int(opaque.rsplit('-', 1)[1])


def read_all(directory: Path) -> dict[str, bytes]:
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in sorted(directory.rglob('*')) if p.is_file()}


def run(world, kind: str, out: Path, *extra: str, capsys=None) -> int:
    probes = [a for p in world.probes for a in ('--probes', str(p))] if kind != 'guess' else []
    return analysis.main(['batches', kind, *probes, '--delivered', str(world.delivered), '--evidence-root', str(world.evidence),
                          '--out', str(out), '--host-version', HOST, *extra])


def build(world, kind: str, name: str | None = None, *extra: str) -> Path:
    out = world.root/'.runtime'/'out'/(name or kind)
    assert run(world, kind, out, *extra) == 0
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
    assert all(re.fullmatch(r's[0-9a-f]{8}-[0-9]{4}', i) for i in key['items'])
    assert all(i.startswith('s' + key['build_sha256'][:8] + '-') for i in key['items'])
    assert key['batch_files'] == {name: analysis.file_sha256(out/'batches'/f'{name}.json')
                                  for name in (b['name'] for b in key['batches'])}
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
    assert key['build_sha256'] != key_of(scoring, 'scoring')['build_sha256']       # the kind is part of the build digest
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
    assert summary['unresolved_cites'] == {'A1': 40, 'B1': 40, 'B2': 40}       # each pair cites one unsealed frame
    key = key_of(out, 'audit')
    assert key['unresolved_cites'] == summary['unresolved_cites'] and key['drawn'] == summary['drawn']
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


def test_audit_items_show_the_statement_and_frames_only_never_the_timeline_or_the_arm(world, capsys):
    out = build(world, 'audit')
    summary = json.loads(capsys.readouterr().out)
    key = key_of(out, 'audit')
    delivered = {(r['lineage'], r['boundary'], r['arm'], r['repeat']): r for r in world.delivered_rows}
    files = batch_files(out, 'audit')
    assert summary['batches'] == len(files) and all(0 < len(b['items']) <= 10 for b in files)
    assert summary['unresolved_cites'] == {'A1': 12, 'B1': 12, 'B2': 12}   # each pair cites one frame that is not sealed
    mixed = [(key['items'][i['id']]['arm'], key['items'][i['id']]['repeat']) for b in files[:1] for i in b['items']]
    assert len(set(mixed)) > 1
    for batch in files:
        assert batch['brief'] == batches.frozen_brief('Audit') and set(batch) == {'schema', 'brief', 'items'}
        for item in batch['items']:
            assert set(item) == {'id', 'statement', 'cited_frames', 'coverage_frames'}    # no timeline file
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
            assert [f['source'] for f in item['coverage_frames']] == [f'{runs[0]}-1', f'{runs[0]}-2']   # the predecessor chunk's
            assert all(Path(f['frame']).is_absolute() and Path(f['frame']).is_file() for f in item['coverage_frames'])
            assert set(meta) == {'arm', 'repeat', 'item'}
            raw = json.dumps(item)
            assert '"arm"' not in raw and '"repeat"' not in raw and 'timeline' not in raw and '.md' not in raw


def test_audit_refuses_a_missing_arm_an_incomplete_row_and_a_delivery_that_does_not_cover_every_planned_boundary(world, tmp_path):
    frozen = batches.Frozen(world.probes)
    delivered = batches.read_delivered([world.delivered])
    evidence, out = world.evidence.resolve(), tmp_path/'.runtime'/'o'
    without = {k: v for k, v in delivered.items() if k[2:] != ('B', 2)}
    with pytest.raises(batches.BatchError, match='A1, B1 and B2'):
        batches.audit_batches(frozen, without, evidence, out/'1', HOST, ['x'])
    broken = {k: dict(v, complete=False) if k[2] == 'A' else v for k, v in delivered.items()}
    with pytest.raises(batches.BatchError, match='incomplete'):
        batches.audit_batches(frozen, broken, evidence, out/'2', HOST, ['x'])
    # dropping one lineage's rows from one arm and repeat: refused, naming only the lineage and the boundary
    short = {k: v for k, v in delivered.items() if k[:1] + k[2:] != ('lh3', 'B', 1)}
    with pytest.raises(batches.BatchError, match=r'B1: the delivered boundaries differ from the ledger plans \(1 missing') as raised:
        batches.audit_batches(frozen, short, evidence, out/'3', HOST, ['x'])
    assert "'lh3'" in str(raised.value) and CANARY_TEXT not in str(raised.value) and 'statement' not in str(raised.value)
    # the same through the command, and a boundary the plans do not know is refused too
    rows = [r for r in world.delivered_rows if (r['lineage'], r['arm'], r['repeat']) != ('lh3', 'A', 1)]
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert run(world, 'audit', out/'4') == 2
    extra = dict(next(r for r in world.delivered_rows if (r['lineage'], r['arm']) == ('lh1', 'A')), boundary='x>y')
    with pytest.raises(batches.BatchError, match='1 unexpected'):
        batches.audit_batches(frozen, {**delivered, ('lh1', 'x>y', 'A', 1): extra}, evidence, out/'5', HOST, ['x'])


# ------------------------------------------------------------------ arm-guess batch
def dev_delivered(boundaries=15, empty=0, repeats=(1, 2)) -> dict:
    out = {}
    for n in range(boundaries):
        for arm, repeat in (('R', 1), ('A', 1), *(('B', r) for r in repeats)):
            items = 0 if arm == 'R' or n < empty else 2
            out[('397', f'b{n:02d}', arm, repeat)] = dict(schema='p1-delivered/2', lineage='397', boundary=f'b{n:02d}',
                                                         arm=arm, repeat=repeat, text=f'{arm}{repeat} text {n}',
                                                         items=items, complete=True)
    return out


def test_the_guess_batch_is_every_boundary_once_per_arm_in_one_seeded_shuffle_with_ids_and_texts_only(tmp_path):
    out = tmp_path/'.runtime'/'g'
    summary = batches.guess_batches(dev_delivered(empty=4), out, HOST, ['x'])      # empty working sets are not filtered out
    (batch,) = batch_files(out, 'guess')
    key = key_of(out, 'guess')
    assert summary['items'] == 30 and summary['batches'] == 1
    assert batch['brief'] == batches.frozen_brief('Arm guess') and len(batch['items']) == 30
    assert all(set(i) == {'id', 'text'} and i['id'].startswith('g') for i in batch['items'])
    arms_ = [key['items'][i['id']]['arm'] for i in batch['items']]
    assert (arms_.count('A'), arms_.count('B')) == (15, 15) and arms_ != sorted(arms_)
    texts = [i['text'] for i in batch['items']]
    expected = sorted([f'A1 text {n}' for n in range(15)] + [f'B1 text {n}' for n in range(15)])    # B's repeat 1, never R or B2
    assert sorted(texts) == expected
    ordered = sorted(((('397', f'b{int(t.split()[-1]):02d}', t[0]), t) for t in expected))   # the sorted items
    random.Random(4914).shuffle(ordered)
    assert texts == [t for _, t in ordered]
    assert key['b_repeat'] == 1 and key['seed'] == 4914
    again = tmp_path/'.runtime'/'g2'
    batches.guess_batches(dev_delivered(empty=4), again, HOST, ['x'])
    assert read_all(out) == read_all(again)


def test_the_guess_batch_needs_exactly_15_complete_boundaries_per_arm(tmp_path):
    out = tmp_path/'.runtime'
    for boundaries in (14, 16):
        with pytest.raises(batches.BatchError, match=f'{boundaries} delivered boundaries; the check needs exactly 15'):
            batches.guess_batches(dev_delivered(boundaries=boundaries), out/f'n{boundaries}', HOST, ['x'])
    incomplete = dev_delivered()
    incomplete[('397', 'b00', 'B', 1)]['complete'] = False
    with pytest.raises(batches.BatchError, match='incomplete'):
        batches.guess_batches(incomplete, out/'partial', HOST, ['x'])
    uneven = {k: v for k, v in dev_delivered().items() if k[2:] != ('A', 1) or k[1] != 'b00'}
    with pytest.raises(batches.BatchError, match='A1 has 14 delivered boundaries'):
        batches.guess_batches(uneven, out/'uneven', HOST, ['x'])


def test_the_guess_command_needs_only_the_delivery(tmp_path, capsys):
    delivered = tmp_path/'delivered.jsonl'
    delivered.write_text(''.join(json.dumps(r) + '\n' for r in dev_delivered().values()))
    assert analysis.main(['batches', 'guess', '--delivered', str(delivered), '--out', str(tmp_path/'.runtime'/'g'),
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
    assert run(world, 'scoring', tmp_path/'.runtime'/'o') == 2
    error = capsys.readouterr().err
    assert '3 earlier frames missing' in error and CANARY_TEXT not in error and 'lh2a1-21' not in error   # A1, B1, B2
    rows = [r for r in world.delivered_rows if (r['lineage'], r['arm'], r['repeat']) != ('lh3', 'B', 2)]
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert run(world, 'scoring', tmp_path/'.runtime'/'q') == 2 and '5 delivered texts missing' in capsys.readouterr().err


def test_building_refuses_an_incomplete_delivery_a_changed_probes_file_and_a_second_write(world, tmp_path, capsys):
    out = build(world, 'scoring')
    capsys.readouterr()
    assert run(world, 'scoring', out) == 2 and 'written once' in capsys.readouterr().err
    rows = [dict(r, complete=False) if r['arm'] == 'B' else r for r in world.delivered_rows]
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert run(world, 'scoring', tmp_path/'.runtime'/'o2') == 2 and 'incomplete' in capsys.readouterr().err
    with world.probes[0].open('a') as stream:
        stream.write('\n')
    assert run(world, 'scoring', tmp_path/'.runtime'/'o3') == 2
    assert 'not a frozen held-out probes file' in capsys.readouterr().err


def test_a_candidates_file_that_differs_from_its_freeze_is_refused(world, tmp_path, capsys):
    (world.probes[0].parent/'candidates.json').write_text(json.dumps(dict(candidates=[])))
    assert run(world, 'scoring', tmp_path/'.runtime'/'o') == 2 and 'not a frozen file' in capsys.readouterr().err


def test_the_probes_must_cover_every_held_out_lineage(world, tmp_path, capsys):
    code = analysis.main(['batches', 'scoring', '--probes', str(world.probes[0]), '--delivered', str(world.delivered),
                          '--evidence-root', str(world.evidence), '--out', str(tmp_path/'.runtime'/'o'), '--host-version', HOST])
    assert code == 2 and 'exactly the held-out lineages' in capsys.readouterr().err


def test_the_judge_files_hold_absolute_paths_so_the_output_must_be_under_the_repositorys_runtime_directory(world, tmp_path, capsys):
    for elsewhere in (tmp_path/'data'/'p1-batches-test', tmp_path.parent/'p1-batches-elsewhere', tmp_path/'.runtimes'/'x'):
        assert run(world, 'scoring', elsewhere) == 2
        assert "must be under the repository's .runtime/" in capsys.readouterr().err
        assert not elsewhere.exists()
    assert run(world, 'scoring', tmp_path/'.runtime'/'fine') == 0


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
    return dict(id=opaque, stated=number(opaque) % 3 != 0, why=CANARY_WORDS)


def audit_answer(opaque, meta):
    n = number(opaque)      # null, "null" or a source id, as the brief's `<source id or null>` may be written
    frame = 'lh1a1-7' if n % 5 == 0 else (None if n % 2 else 'null')
    return dict(id=opaque, false=n % 5 == 0, frame=frame, why=CANARY_WORDS)


def guess_answer(opaque, meta):
    even = number(opaque) % 2 == 0     # right for exactly half of the 30
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
    assert {r['frame'] for r in audits} == {None, 'lh1a1-7'}               # "null" is stored as null
    assert len(guesses) == 30 and all(r['type'] == 'guess' and r['guess'] in '12' for r in guesses)
    assert CANARY_WORDS not in json.dumps([first, second, audits, guesses])
    costs = [dict(type='cost', schema=analysis.SCORE_SCHEMA, repeat=r, lineage='lh1', curator_dollars=1.0, actor_dollars=2.0,
                  stopped_by_cap=False) for r in (1, 2)]
    result = analysis.score(world.rows, {name: 10.0 for name in LINEAGES}, first + second + audits + guesses + costs)
    assert result['probes']['units'] == 20 and result['judge_agreement']['n'] == 12
    assert result['arm_guessing'] == dict(n=30, correct=15, limit=analysis.guess_limit(), leaks=False)
    assert {'A1', 'B1', 'B2'} <= set(result['figures'])


def build_guess(tmp_path: Path) -> Path:
    out = tmp_path/'.runtime'/'out'/'guess'
    batches.guess_batches(dev_delivered(), out, HOST, ['x'])
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


def test_audit_frame_is_null_the_string_null_or_a_syntactically_valid_source_id(world, tmp_path):
    out = build(world, 'audit')
    answers = answers_for(out, 'audit', audit_answer)
    first = json.loads(lines_of(answers, 'audit-001.jsonl')[0])
    rest = lines_of(answers, 'audit-001.jsonl')[1:]
    for bad in ('SECRET FRAME', '../etc/passwd', '', 7, ['x'], {'frame': 1}):
        rewrite(answers, [json.dumps(dict(first, frame=bad)), *rest], 'audit-001.jsonl')
        with pytest.raises(batches.BatchError, match=r'audit-001.jsonl:1: frame \(id a') as raised:
            batches.parse('audit', out, answers)
        assert 'SECRET' not in str(raised.value) and 'passwd' not in str(raised.value)
    for good, stored in ((None, None), ('null', None), ('lh2a1-3', 'lh2a1-3'), ('any-valid.id_9', 'any-valid.id_9')):
        rewrite(answers, [json.dumps(dict(first, frame=good)), *rest], 'audit-001.jsonl')
        assert batches.parse('audit', out, answers)[0]['frame'] == stored      # not checked against the item's listed frames


def test_only_scoring_and_rejudging_need_the_given_order_audit_and_guess_need_each_id_once(world, tmp_path):
    audit, guess = build(world, 'audit'), build_guess(tmp_path)
    for out, kind, make, batch in ((audit, 'audit', audit_answer, 'audit-001.jsonl'), (guess, 'guess', guess_answer, 'guess-001.jsonl')):
        answers = answers_for(out, kind, make)
        expected = batches.parse(kind, out, answers)
        lines = lines_of(answers, batch)
        rewrite(answers, lines[::-1], batch)
        assert batches.parse(kind, out, answers) == expected          # reversed output: the same rows, in the key's order
        rewrite(answers, [lines[0], *lines[:-1]], batch)               # an id twice (and one missing) is still refused
        with pytest.raises(batches.BatchError, match='duplicated id'):
            batches.parse(kind, out, answers)
        rewrite(answers, lines[:-1], batch)
        with pytest.raises(batches.BatchError, match='ids missing'):
            batches.parse(kind, out, answers)
    scoring = build(world, 'scoring')
    answers = answers_for(scoring, 'scoring', label_answer)
    lines = lines_of(answers)
    rewrite(answers, lines[::-1])
    with pytest.raises(batches.BatchError, match='not in batch order'):
        batches.parse('scoring', scoring, answers)


def test_answers_from_another_build_are_refused(world, tmp_path):
    one = build(world, 'scoring', 'one')
    delivered = [dict(r, text=r['text'] + ' changed') if r['arm'] == 'A' else r for r in world.delivered_rows]
    world.delivered.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in delivered))
    two = build(world, 'scoring', 'two')
    assert key_of(one, 'scoring')['build_sha256'] != key_of(two, 'scoring')['build_sha256']
    assert not set(key_of(one, 'scoring')['items']) & set(key_of(two, 'scoring')['items'])    # no id is shared
    mine = answers_for(one, 'scoring', label_answer)
    theirs = answers_for(two, 'scoring', label_answer)
    assert len(batches.parse('scoring', one, mine)) == 60
    with pytest.raises(batches.BatchError, match="id is not in the batch's key"):
        batches.parse('scoring', one, theirs)
    with pytest.raises(batches.BatchError, match="id is not in the batch's key"):
        batches.parse('scoring', two, mine)


def test_a_batch_file_that_differs_from_the_key_is_refused_before_any_answer_is_read(world, tmp_path):
    out = build(world, 'scoring')
    answers = answers_for(out, 'scoring', label_answer)
    path = out/'batches'/'score-002.json'
    original = path.read_text()
    path.write_text(original.replace('statement', 'altered'))
    with pytest.raises(batches.BatchError, match='differ from the build the key was made for: score-002'):
        batches.parse('scoring', out, answers)
    path.write_text(original)
    (out/'batches'/'score-099.json').write_text('{}')
    with pytest.raises(batches.BatchError, match='does not hold exactly the scoring batch files of the key: score-099'):
        batches.parse('scoring', out, answers)
    (out/'batches'/'score-099.json').unlink()
    path.unlink()
    with pytest.raises(batches.BatchError, match='does not hold exactly'):
        batches.parse('scoring', out, answers)
    path.write_text(original)
    key = out/'keys'/'scoring.json'
    document = json.loads(key.read_text())
    del document['batch_files']
    key.write_text(json.dumps(document))
    with pytest.raises(batches.BatchError, match='records no batch file digests'):
        batches.parse('scoring', out, answers)


def test_dotfiles_in_the_answers_directory_are_ignored(world, tmp_path):
    out = build(world, 'scoring')
    answers = answers_for(out, 'scoring', label_answer)
    (answers/'.DS_Store').write_bytes(b'\x00')
    assert len(batches.parse('scoring', out, answers)) == 60
    (answers/'DS_Store').write_bytes(b'\x00')
    with pytest.raises(batches.BatchError, match='belong to no batch: DS_Store'):
        batches.parse('scoring', out, answers)


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
