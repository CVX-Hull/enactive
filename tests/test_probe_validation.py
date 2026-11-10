"""The #490 recall check: the fixed candidate rule and the captured test, on synthetic hashes and labels."""
import json
from pathlib import Path
import random
import re
import sqlite3

import pytest

from tools import p1_analysis
from tools import probe_validation as validation

FULL = (1 << 256) - 1


def flip(base: int, bits: int) -> int:
    """`base` with its lowest `bits` bits inverted: exactly `bits` bits away."""
    return base ^ ((1 << bits) - 1)


def test_a_new_screen_after_a_boundary_matching_an_earlier_chunk_is_a_candidate():
    menu, field = 0, FULL                  # two screens far apart (256 bits)
    hashes = {'s-1': field, 's-2': menu, 's-3': field, 's-4': flip(menu, 10), 's-5': field, 's-6': flip(menu, 40)}
    chunks = [('r-001', 'r', ['s-1', 's-2']), ('r-002', 'r', ['s-3', 's-4', 's-5', 's-6'])]
    found = validation.find_candidates(chunks, hashes)
    # s-4 re-opens the earlier menu (10 bits). s-5, back to the main view, also matches an earlier
    # frame: the rule keeps such pairs and the blinded judge rejects mere "same view" matches.
    # s-6 is a new screen but 40 bits from anything earlier.
    assert [(c['later'], c['earlier'], c['distance']) for c in found] == [('s-4', 's-2', 10), ('s-5', 's-1', 0)]


def test_the_first_chunk_and_screens_that_did_not_change_are_never_candidates():
    hashes = {'s-1': 0, 's-2': FULL, 's-3': flip(FULL, 3), 's-4': flip(FULL, 5)}
    chunks = [('r-001', 'r', ['s-1', 's-2']), ('r-002', 'r', ['s-3', 's-4'])]
    # s-3 starts its chunk (no previous frame in the chunk); s-4 differs from s-3 by too little.
    assert validation.find_candidates(chunks, hashes) == []


def test_one_reopened_screen_counts_once_within_the_cluster():
    menu, field = 0, FULL
    later = ['s-10', 's-11', 's-12', 's-13']
    hashes = {'s-1': field, 's-2': menu, 's-10': field, 's-11': flip(menu, 2), 's-12': field, 's-13': flip(menu, 3)}
    found = validation.find_candidates([('r-001', 'r', ['s-1', 's-2']), ('r-002', 'r', later)], hashes)
    # s-13 re-opens the same earlier menu within the cluster and is dropped; s-12 matches another
    # earlier frame (the main view) and is kept.
    assert [c['later'] for c in found] == ['s-11', 's-12']


def ledger(events):
    return {'r-001': [dict(type='fact', id='F1', statement='s', category='item', observed='x-5', stored=None),
                      dict(type='end')],
            'r-002': [*events, dict(type='end')]}


@pytest.mark.parametrize('event, expected', [
    (dict(type='event', fact='F1', event='rediscovered', frame='x-110'), True),
    (dict(type='event', fact='F1', event='needed', frame='x-90'), True),
    (dict(type='event', fact='F1', event='used', frame='x-100'), False),        # not a need
    (dict(type='event', fact='F1', event='needed', frame='x-130'), False),      # outside the window
    (dict(type='event', fact='F1', event='needed', frame='y-100'), False),      # another session
    (dict(type='event', fact='F9', event='needed', frame='x-100'), False),      # not an earlier fact
])
def test_captured_needs_a_nearby_need_on_an_earlier_fact(event, expected):
    pair = dict(later_chunk='r-002', later='x-100')
    assert validation.captured(pair, ledger([event]), ['r-001', 'r-002']) is expected


def query_case(coverage):
    data = dict(pairs=[dict(id='p1', lineage='397'), dict(id='p2', lineage='397'), dict(id='p3', lineage='372'),
                       dict(id='p4', lineage='372')])
    verdicts = dict(p1=dict(what='recipe for a spear'), p2=dict(what='Empty Favorite tab, 0 in category'),
                    p3=dict(what='overmap shelter label'), p4=dict(what='a different screen'))
    fact_pairs = [dict(id='p1', confirmed=True, captured=False), dict(id='p2', confirmed=True, captured=True),
                  dict(id='p3', confirmed=True, captured=False), dict(id='p4', confirmed=False)]
    return validation.query_figures(data, verdicts, fact_pairs, coverage)


def test_query_recall_union_and_informative_figures():
    result = query_case([dict(id='p1', covered=True), dict(id='p2', covered=False), dict(id='p3', covered=False)])
    assert result['pooled'] == dict(confirmed=3, query=1, fact=1, union=2, query_recall=0.333, union_recall=0.667)
    assert result['lineages']['372'] == dict(confirmed=1, query=0, fact=0, union=0, query_recall=0.0,
                                             union_recall=0.0)
    # p2's judge note marks an empty menu: left out of the descriptive "informative" figures only.
    assert result['trivial'] == ['p2']
    assert result['informative']['confirmed'] == 2
    assert result['decision'] == 'below the bar: the probe design went back to the owner'


def test_query_recall_at_the_bar_adopts_query_probes():
    result = query_case([dict(id='p1', covered=True), dict(id='p2', covered=True), dict(id='p3', covered=False)])
    assert result['pooled']['query_recall'] == 0.667
    assert result['decision'] == 'query probes adopted'


@pytest.mark.parametrize('coverage', [
    [dict(id='p1', covered=True), dict(id='p2', covered=True)],                                     # one missing
    [dict(id=i, covered=True) for i in ('p1', 'p2', 'p3', 'p4')],                                   # unconfirmed
])
def test_query_coverage_must_judge_exactly_the_confirmed_pairs(coverage):
    with pytest.raises(SystemExit, match='exactly the confirmed'):
        query_case(coverage)


def test_freeze_digests_both_ledgers_per_lineage(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, 'LINEAGES', {'397': ['a-001', 'a-002'], 'r1': ['r1-001', 'r1-002']})
    for name, chunks in (('397', ['a-001', 'a-002']), ('r1', ['r1-001', 'r1-002'])):
        (tmp_path/name).mkdir()
        for chunk in chunks:
            (tmp_path/name/f'{chunk}.jsonl').write_text(f'{chunk}\n')
    (tmp_path/'397'/'adjudication.jsonl').write_text('adjudicated\n')
    for group, chunk in (('397', 'a-001'), ('372', 'r1-001'), ('372', 'other-001')):
        (tmp_path/'queries'/group).mkdir(parents=True, exist_ok=True)
        (tmp_path/'queries'/group/f'{chunk}.jsonl').write_text(f'q {chunk}\n')
    ledger = validation.freeze(tmp_path)
    assert ledger['schema'] == 'probe-ledger/1'
    assert set(ledger['lineages']['397']['fact_chunks']) == {'a-001', 'a-002'}
    assert set(ledger['lineages']['397']['queries']) == {'a-001'}
    # A #372 run keeps only the query files of its own chunks.
    assert set(ledger['lineages']['r1']['queries']) == {'r1-001'}
    assert ledger['lineages']['r1']['adjudication'] is None
    assert len(ledger['lineages']['397']['adjudication']) == 64
    # Changing a frozen file changes its digest.
    before = ledger['lineages']['397']['fact_chunks']['a-001']
    (tmp_path/'397'/'a-001.jsonl').write_text('edited\n')
    assert validation.freeze(tmp_path)['lineages']['397']['fact_chunks']['a-001'] != before


def test_freeze_refuses_a_query_file_set_that_does_not_match_the_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, 'LINEAGES', {'397': ['a-001', 'a-002']})
    (tmp_path/'397').mkdir()
    for chunk in ('a-001', 'a-002'):
        (tmp_path/'397'/f'{chunk}.jsonl').write_text('x\n')
    (tmp_path/'queries'/'397').mkdir(parents=True)
    (tmp_path/'queries'/'397'/'a-002.jsonl').write_text('q\n')     # the last chunk precedes no boundary
    with pytest.raises(SystemExit, match='exactly the chunks before a boundary'):
        validation.freeze(tmp_path)


@pytest.mark.parametrize('step', ['lineage_runs', 'freeze', 'recall'])
def test_held_out_lineages_are_refused(monkeypatch, tmp_path, step):
    monkeypatch.setitem(validation.LINEAGES, 'lh1', ['lh1-001'])
    call = {'lineage_runs': lambda: validation.lineage_runs(), 'freeze': lambda: validation.freeze(tmp_path),
            'recall': lambda: validation.recall(tmp_path)}[step]
    (tmp_path/'candidates.json').write_text('{"pairs": []}')
    (tmp_path/'judgments.jsonl').write_text('')
    with pytest.raises(SystemExit, match='held-out'):
        call()


def test_the_tracked_figures_and_ledger_reproduce_from_their_inputs(tmp_path):
    import json
    import shutil
    probes = validation.ROOT/'data'/'evaluation'/'probes'
    copy = tmp_path/'probes'
    shutil.copytree(probes, copy)
    assert validation.freeze(copy) == json.loads((probes/'ledger.json').read_text())
    validation.ROOT, root = tmp_path, validation.ROOT
    try:
        (tmp_path/'data'/'evaluation').mkdir(parents=True)
        (copy).rename(tmp_path/'data'/'evaluation'/'probes')
        result = validation.recall(tmp_path/'data'/'evaluation'/'probes'/'validation')
    finally:
        validation.ROOT = root
    assert result == json.loads((probes/'validation'/'recall.json').read_text())


# ---------------------------------------------------------------------------------------------
# #178: held-out candidates, confirmation batches, probes, ledgers and the freeze, on synthetic
# sealed sessions. Frames are empty files; the image hash is patched to a table.

RUNS = {'lh1': ('lh1a1', 'lh1a2'), 'lh2': ('lh2a1',), 'lh3': ('lh3a1',)}


class World:
    pass


def build_session(study, run, actors, flags=None):
    """A sealed session with one operation per frame, one actor directory per chunk; `flags` (source ->
    changed 0/1) also seals an evaluation store."""
    session = study/'computer-sessions'/run
    (session/'sources').mkdir(parents=True)
    db = sqlite3.connect(session/'session.sqlite3')
    db.executescript('CREATE TABLE operations(id TEXT, actor TEXT, kind TEXT, input_json TEXT, created_wall REAL);'
                     'CREATE TABLE native_intents(id TEXT, operation TEXT, source TEXT);'
                     'CREATE TABLE collections(native_id TEXT, source TEXT);')
    wall, steps = 0, []
    for directory, sources in actors.items():
        actor = f'actor-{run}-{directory}'
        (session/'actors'/directory).mkdir(parents=True)
        (session/'actors'/directory/'frozen.json').write_text(json.dumps({'actor_id': actor}))
        (session/'actors'/directory/'prompt.txt').write_text('prompt')
        for source in sources:
            wall += 1
            db.execute('INSERT INTO operations VALUES (?,?,?,?,?)',
                       (f'op-{source}', actor, 'input', '[{"type":"key","key":"a"}]', wall))
            db.execute('INSERT INTO native_intents VALUES (?,?,?)', (f'n-{source}', f'op-{source}', source))
            (session/'sources'/f'{source}.png').write_bytes(b'x')
            steps.append((wall, f'op-{source}', actor, 'input', wall, 1000 + wall, source, (flags or {}).get(source)))
    db.commit()
    db.close()
    (session/'manifest.json').write_text(json.dumps({'session': f'sid-{run}'}))
    if flags is not None:
        store = study/'evaluations'/f'sid-{run}'/'2-cdda-2.sqlite3'
        store.parent.mkdir(parents=True)
        db = sqlite3.connect(store)
        db.execute('CREATE TABLE steps(seq INTEGER, operation_id TEXT, actor TEXT, kind TEXT, decision INTEGER, '
                   'game_time INTEGER, source_id TEXT, frame_changed INTEGER)')
        db.executemany('INSERT INTO steps VALUES (?,?,?,?,?,?,?,?)', steps)
        db.commit()
        db.close()


@pytest.fixture
def world(tmp_path, monkeypatch):
    w = World()
    w.root, w.out, w.to = tmp_path/'evidence', tmp_path/'held-out', tmp_path/'timelines'
    study = w.root/validation.HELD_OUT_STUDY
    rng = random.Random(7)
    w.hashes, w.frames = {}, {}

    def chunk(run, directory, values):
        sources = [f's-{run}-{len(w.hashes) + i}' for i in range(len(values))]
        w.hashes.update(zip(sources, values))
        w.frames[f'{run}-{directory}'] = sources
        return sources
    menu, field = 0, FULL
    build_session(study, 'lh1a1', {'001': chunk('lh1a1', '001', [menu, field]),
                                   '002': chunk('lh1a1', '002', [field, flip(menu, 5)])})
    build_session(study, 'lh1a2', {'001': chunk('lh1a2', '001', [field, flip(menu, 3)])})
    # lh2: 45 distinct earlier screens, each re-opened once in the second chunk (more than the old sample of 40).
    earlier = [rng.getrandbits(256) for _ in range(45)]
    build_session(study, 'lh2a1', {'001': chunk('lh2a1', '001', earlier),
                                   '002': chunk('lh2a1', '002', [v for k, e in enumerate(earlier)
                                                                  for v in (rng.getrandbits(256), flip(e, 3))])})
    # lh3: one chunk, with sealed change flags.
    values = [rng.getrandbits(256) for _ in range(8)]
    sources = chunk('lh3a1', '001', values)
    build_session(study, 'lh3a1', {'001': sources}, flags=dict(zip(sources, [1, 1, 0, 1, 0, 1, 1, 1])))
    for lineage in RUNS:
        db = sqlite3.connect(study/f'player-memory-{lineage}.sqlite3')
        db.execute('CREATE TABLE records(id TEXT, kind TEXT, document TEXT, supersedes TEXT)')
        db.commit()
        db.close()
    monkeypatch.setattr(validation, 'HELD_OUT_RUNS', RUNS)
    monkeypatch.setattr(validation, 'load', lambda path: path)
    monkeypatch.setattr(validation, 'dhash', lambda image, size: w.hashes[Path(image).stem])
    w.secrets = list(w.hashes) + [str(tmp_path), 'SECRET']

    w.judge = tmp_path/'judge'

    def run(*step, judge=None):
        extra = ['--judge-dir', str(judge or w.judge)] if step[0] == 'held-out-batches' else []
        return validation.main([*step, '--evidence-root', str(w.root), '--out', str(w.out), *extra])
    w.run = run
    return w


def quiet(capsys, w):
    """Everything a held-out command printed is JSON of counts and digests: no frame id, path or judge text."""
    out = capsys.readouterr().out
    json.loads(out)
    for secret in [*w.secrets, *(row['id'] for row in json.loads((w.out/'candidates.json').read_text())['candidates'])]:
        assert secret not in out
    return json.loads(out)


def candidates_of(w):
    return json.loads((w.out/'candidates.json').read_text())['candidates']


def test_held_out_candidates_are_every_candidate_numbered_in_sort_order(world, capsys):
    assert world.run('held-out-candidates') == 0
    assert quiet(capsys, world) == {'lh1': dict(chunks=3, candidates=2), 'lh2': dict(chunks=2, candidates=45),
                                    'lh3': dict(chunks=1, candidates=0)}
    data = json.loads((world.out/'candidates.json').read_text())
    assert data['schema'] == 'p1-held-out-candidates/1'
    rows = data['candidates']
    assert len(rows) == 47 > validation.SAMPLE['397']                 # nothing is sampled
    for lineage in ('lh1', 'lh2'):
        mine = [r for r in rows if r['lineage'] == lineage]
        assert [r['id'] for r in mine] == [f'{lineage}-p{n:04d}' for n in range(1, len(mine) + 1)]
        assert [(r['later_chunk'], r['later']) for r in mine] == sorted((r['later_chunk'], r['later']) for r in mine)
    assert [r['id'] for r in rows] == sorted(r['id'] for r in rows)
    assert {r['id'] for r in rows if r['lineage'] == 'lh3'} == set()


def test_boundary_is_the_chunk_before_the_later_chunk_across_a_session_change_and_a_handoff(world):
    world.run('held-out-candidates')
    lh1 = {r['id']: r for r in candidates_of(world) if r['lineage'] == 'lh1'}
    handoff, admission = lh1['lh1-p0001'], lh1['lh1-p0002']
    assert (handoff['boundary'], handoff['earlier_chunk'], handoff['distance']) == (
        'lh1a1-001>lh1a1-002', 'lh1a1-001', 5)
    # The later chunk starts a new session; its earlier match is in the chunk before it, not the first one.
    assert (admission['boundary'], admission['later_chunk'], admission['earlier_chunk'], admission['distance']) == (
        'lh1a1-002>lh1a2-001', 'lh1a2-001', 'lh1a1-002', 2)
    assert {r['boundary'] for r in candidates_of(world) if r['lineage'] == 'lh2'} == {'lh2a1-001>lh2a1-002'}


def test_candidate_rows_carry_the_hash_the_paths_and_the_seeded_order(world):
    world.run('held-out-candidates')
    rows = candidates_of(world)
    for row in rows:
        assert re.fullmatch(r'[0-9a-f]{64}', row['earlier_dhash'])
        assert int(row['earlier_dhash'], 16) == world.hashes[row['earlier']]
        # Frame paths are relative to the evidence root: nothing tracked names the local home directory.
        assert not Path(row['earlier_path']).is_absolute() and Path(row['earlier_path']).stem == row['earlier']
        assert row['later_path'].startswith('372-382-dev-loop/computer-sessions/')
        assert Path(row['later_path']).stem == row['later'] and (world.root/row['later_path']).is_file()
        order = random.Random(f'490:{row["later"]}').random() < 0.5
        assert row['shown'] == (['earlier', 'later'] if order else ['later', 'earlier'])
    assert {tuple(r['shown']) for r in rows} == {('earlier', 'later'), ('later', 'earlier')}   # both orders occur
    probes = [dict(r, confirmed=True, informative=True) for r in rows]
    names = p1_analysis.clusters(probes)                               # parses earlier_dhash with int(x, 16)
    assert set(names) == {r['id'] for r in rows}


def test_held_out_candidates_are_computed_once(world):
    world.run('held-out-candidates')
    with pytest.raises(SystemExit, match='computed once'):
        world.run('held-out-candidates')


def expected_brief():
    # p1-study/1's brief, the one lh1-lh3's judges used: p1-study/2 must keep it word for word.
    text = (validation.ROOT/'docs'/'design'/'p1-study.md').read_text()
    paragraph = next(p for p in text.split('\n\n') if p.startswith('> **Confirmation.**'))
    joined = ' '.join(line[1:].strip() for line in paragraph.splitlines())
    assert joined.startswith('**Confirmation.** ')
    return joined[len('**Confirmation.** '):]


def test_the_confirmation_brief_is_read_verbatim_from_the_pre_registration():
    brief = validation.confirmation_brief()
    assert brief == expected_brief()
    assert brief.startswith('You compare pairs of screenshots for a study.') and '**' not in brief
    assert 'The file [batch] lists pairs' in brief               # the placeholder is kept for the launcher
    assert brief.endswith('"informative":true|false,"what":"<one line>"}.')
    assert 'Scoring' not in brief and '\n' not in brief


def test_the_brief_is_refused_when_it_cannot_be_found(tmp_path):
    doc = tmp_path/'p1-study.md'
    doc.write_text('> **Scoring.** something\n')
    with pytest.raises(SystemExit, match='not found'):
        validation.confirmation_brief(doc)


def test_batches_hold_at_most_fifteen_pairs_in_id_order_with_the_brief(world, capsys):
    world.run('held-out-candidates')
    capsys.readouterr()
    assert world.run('held-out-batches') == 0
    assert quiet(capsys, world) == dict(candidates=47, batches=4)
    files = sorted((world.out/'batches').glob('confirm-*.json'))
    assert [f.name for f in files] == [f'confirm-{n:03d}.json' for n in range(1, 5)]
    rows = {r['id']: r for r in candidates_of(world)}
    seen = []
    for path in files:
        batch = json.loads(path.read_text())
        assert batch['schema'] == 'p1-held-out-batch/1' and batch['brief'] == expected_brief()
        assert 0 < len(batch['pairs']) <= 15
        for pair in batch['pairs']:
            row = rows[pair['id']]
            assert set(pair) == {'id', 'A', 'B'} and not Path(pair['A']).is_absolute()
            assert [pair['A'], pair['B']] == [row[f'{side}_path'] for side in row['shown']]
        seen += [p['id'] for p in batch['pairs']]
        # The judge copy has the same brief, ids and pair order, with absolute paths that exist.
        copy = json.loads((world.judge/path.name).read_text())
        assert copy['brief'] == batch['brief'] and copy['schema'] == batch['schema']
        assert [p['id'] for p in copy['pairs']] == [p['id'] for p in batch['pairs']]
        for tracked, judge_pair in zip(batch['pairs'], copy['pairs']):
            assert judge_pair['A'] == str(world.root.resolve()/tracked['A'])
            assert judge_pair['B'] == str(world.root.resolve()/tracked['B'])
            assert Path(judge_pair['A']).is_file() and Path(judge_pair['B']).is_file()
    assert seen == sorted(rows) and len(seen) == 47
    assert len(list(world.judge.glob('confirm-*.json'))) == 4
    with pytest.raises(SystemExit, match='written once'):
        world.run('held-out-batches')


@pytest.mark.parametrize('place', ['data/evaluation/p1/held-out/judge', 'tools/judge', 'judge'])
def test_the_judge_directory_may_not_be_inside_the_tracked_tree(world, place):
    world.run('held-out-candidates')
    with pytest.raises(SystemExit, match='outside the repository or under .runtime'):
        world.run('held-out-batches', judge=validation.ROOT/place)
    assert not (validation.ROOT/place).exists() and not list((world.out/'batches').glob('*'))


def test_the_judge_directory_may_be_under_runtime(world):
    world.run('held-out-candidates')
    assert validation._check_judge_dir(validation.ROOT/'.runtime'/'judge') == (validation.ROOT/'.runtime'/'judge').resolve()
    assert validation._check_judge_dir(world.judge) == world.judge.resolve()


def test_held_out_batches_needs_a_judge_directory(world):
    world.run('held-out-candidates')
    with pytest.raises(SystemExit):
        validation.main(['held-out-batches', '--evidence-root', str(world.root), '--out', str(world.out)])


def test_batches_need_the_candidates(world):
    with pytest.raises(SystemExit, match='held-out-candidates'):
        world.run('held-out-batches')


def judge(w, same=lambda n: n % 3 != 0, informative=lambda n: n % 2 == 0):
    """Write a judgment file per batch, in batch order."""
    (w.out/'judgments').mkdir(exist_ok=True)
    count = 0
    for path in sorted((w.out/'batches').glob('confirm-*.json')):
        lines = []
        for pair in json.loads(path.read_text())['pairs']:
            count += 1
            lines.append(json.dumps(dict(id=pair['id'], same=same(count), informative=informative(count),
                                         what=f'SECRET text for {pair["id"]}')))
        (w.out/'judgments'/f'{path.stem}.jsonl').write_text('\n'.join(lines) + '\n')


@pytest.fixture
def judged(world):
    world.run('held-out-candidates')
    world.run('held-out-batches')
    judge(world)
    return world


def test_probes_are_one_p1_row_per_candidate_and_primary_probes_accepts_them(judged, capsys):
    capsys.readouterr()
    assert judged.run('held-out-probes') == 0
    figures = quiet(capsys, judged)
    rows = [json.loads(line) for line in (judged.out/'probes.jsonl').read_text().splitlines()]
    assert [r['id'] for r in rows] == [c['id'] for c in candidates_of(judged)]
    cands = {c['id']: c for c in candidates_of(judged)}
    for n, row in enumerate(rows, 1):
        assert set(row) == {'schema', 'id', 'lineage', 'boundary', 'later', 'earlier', 'earlier_dhash', 'confirmed',
                            'informative', 'what'}
        assert row['schema'] == 'p1-probes/1' and row['what'] == f'SECRET text for {row["id"]}'
        assert row['confirmed'] is (n % 3 != 0)
        assert row['informative'] is (row['confirmed'] and n % 2 == 0)
        assert row['boundary'] == cands[row['id']]['boundary'] and row['earlier_dhash'] == cands[row['id']]['earlier_dhash']
    primary = p1_analysis.primary_probes(rows)
    assert len(primary) == sum(r['informative'] for r in rows) > 0
    units = p1_analysis.units(primary)
    assert figures['units'] == len(units)
    assert figures['clusters'] == len({(u['lineage'], u['cluster']) for u in units})
    assert figures['cluster_sizes'] == p1_analysis.cluster_sizes(units)
    assert figures['lineages']['lh1'] == dict(candidates=2, confirmed=sum(r['confirmed'] for r in rows[:2]),
                                              primary=sum(r['informative'] for r in rows[:2]),
                                              units=sum(u['lineage'] == 'lh1' for u in units))
    assert figures['lineages']['lh3'] == dict(candidates=0, confirmed=0, primary=0, units=0)
    assert figures['probes_sha256'] == validation.file_sha256(judged.out/'probes.jsonl')


def edit(w, name, change):
    path = w.out/'judgments'/name
    lines = path.read_text().splitlines()
    result = change(lines)
    path.write_text('\n'.join(result) + '\n')


@pytest.mark.parametrize('change, message', [
    (lambda lines: lines[1:], 'missing ids'),
    (lambda lines: [*lines, lines[0]], 'duplicated id'),
    (lambda lines: [lines[0], lines[0], *lines[2:]], 'duplicated id'),
    (lambda lines: [json.dumps(dict(json.loads(lines[0]), id='lh9-p0001')), *lines[1:]], 'unknown id'),
    (lambda lines: [json.dumps(dict(json.loads(lines[0]), same='yes')), *lines[1:]], 'booleans'),
    (lambda lines: [json.dumps(dict(json.loads(lines[0]), informative=None)), *lines[1:]], 'booleans'),
    (lambda lines: [json.dumps({k: v for k, v in json.loads(lines[0]).items() if k != 'same'}), *lines[1:]], 'booleans'),
    (lambda lines: [json.dumps(dict(json.loads(lines[0]), what=3)), *lines[1:]], 'what'),
    (lambda lines: [lines[1], lines[0], *lines[2:]], 'batch order'),
    (lambda lines: [*lines[:-1], 'not json'], 'not JSON'),
])
def test_probe_rows_are_refused_when_a_judgment_is_wrong(judged, change, message):
    edit(judged, 'confirm-001.jsonl', change)
    with pytest.raises(SystemExit, match=message):
        judged.run('held-out-probes')


def test_an_id_from_another_batch_is_unknown_to_this_one(judged):
    other = json.loads((judged.out/'judgments'/'confirm-002.jsonl').read_text().splitlines()[0])
    edit(judged, 'confirm-001.jsonl', lambda lines: [json.dumps(other), *lines[1:]])
    with pytest.raises(SystemExit, match='unknown id'):
        judged.run('held-out-probes')


def test_a_batch_without_output_and_output_without_a_batch_are_refused(judged):
    (judged.out/'judgments'/'confirm-004.jsonl').rename(judged.out/'judgments'/'confirm-009.jsonl')
    with pytest.raises(SystemExit, match='confirm-004: the batch has no judgments'):
        judged.run('held-out-probes')
    (judged.out/'judgments'/'confirm-009.jsonl').rename(judged.out/'judgments'/'confirm-004.jsonl')
    (judged.out/'judgments'/'confirm-009.jsonl').write_text('')
    with pytest.raises(SystemExit, match='without a batch'):
        judged.run('held-out-probes')


def test_timelines_and_the_ledger_plan(judged, capsys):
    capsys.readouterr()
    assert judged.run('held-out-timelines', '--to', str(judged.to)) == 0
    assert quiet(capsys, judged) == {
        'lh1': dict(annotate=3, queries=2, required_frames=judged_required(judged, 'lh1')),
        'lh2': dict(annotate=2, queries=1, required_frames=judged_required(judged, 'lh2')),
        'lh3': dict(annotate=1, queries=0, required_frames=judged_required(judged, 'lh3'))}
    plan = json.loads((judged.out/'ledger-plan.json').read_text())
    assert plan['schema'] == 'p1-held-out-ledger-plan/1'
    lh1 = plan['lineages']['lh1']
    assert lh1['annotate'] == ['lh1a1-001', 'lh1a1-002', 'lh1a2-001']
    assert lh1['queries'] == ['lh1a1-001', 'lh1a1-002']                # every chunk before a boundary
    assert [c['incoming_boundary'] for c in lh1['chunks']] == [None, 'lh1a1-001>lh1a1-002', 'lh1a1-002>lh1a2-001']
    # A timeline is named by file name, relative to the --to directory.
    assert all(c['timeline'] == f'{c["chunk"]}.md' and (judged.to/c['timeline']).is_file()
               for v in plan['lineages'].values() for c in v['chunks'])
    assert plan['lineages']['lh3']['queries'] == []
    # lh1 and lh2 have no change flags: every third frame, plus the last five operations.
    lh2 = {c['chunk']: c for c in plan['lineages']['lh2']['chunks']}
    frames = judged.frames['lh2a1-002']
    assert lh2['lh2a1-002']['required_frames'] == list(dict.fromkeys(frames[::3] + frames[-5:]))
    # lh3's sealed flags are [1, 1, 0, 1, 0, 1, 1, 1]: the changed frames are 0, 1, 3, 5, 6, 7.
    g = judged.frames['lh3a1-001']
    assert plan['lineages']['lh3']['chunks'][0]['required_frames'] == [g[0], g[5], g[3], g[4], g[6], g[7]]
    # The timeline files themselves hold content and are not printed.
    assert (judged.to/'lh1a1-001.md').read_text().startswith('# lh1a1 actor 001')


def judged_required(w, lineage):
    first = {'lh1': ['lh1a1-001', 'lh1a1-002', 'lh1a2-001'], 'lh2': ['lh2a1-001', 'lh2a1-002'],
             'lh3': ['lh3a1-001']}[lineage]
    total = 0
    for name in first:
        frames = w.frames[name]
        if name == 'lh3a1-001':
            total += len(dict.fromkeys([frames[0], frames[5], *frames[3:]]))
        else:
            total += len(dict.fromkeys(frames[::3] + frames[-5:]))
    return total


def test_required_frames_follow_the_coverage_rule():
    def timeline(rows):
        table = ''.join(f'| {i} | {i} | +0:00:0{i} | key | {flag} | /x/{src}.png |\n' if src else
                        f'| {i} | {i} | +0:00:0{i} | key | {flag} |  |\n' for i, (flag, src) in enumerate(rows, 1))
        return (f'# t\n\n## What this actor received\n\n```\n| 1 | fake | row | key | yes | /x/bogus.png |\n```\n\n'
                f'## Operations\n\n| seq | decision |\n| ---: | ---: |\n{table}\n## Memory records this actor wrote\n')
    flagged = [('yes', 'a'), ('no', 'b'), ('yes', 'c'), ('yes', 'd'), ('no', 'e'), ('yes', 'f'), ('yes', 'g'),
               ('yes', 'h'), ('no', None), ('yes', 'i')]
    # Changed frames: a c d f g h i, so every third from the first is a, f, i. The last five operations
    # are f, g, h, one with no frame, and i. A row inside the prompt block is not an operation.
    assert validation.required_frames(timeline(flagged)) == ['a', 'f', 'i', 'g', 'h']
    unflagged = [('', c) for c in 'abcdefgh']                        # no change flags: every third frame
    assert validation.required_frames(timeline(unflagged)) == ['a', 'd', 'g', 'e', 'f', 'h']
    with pytest.raises(SystemExit, match='Operations'):
        validation.required_frames('# nothing')


def annotate(w):
    """Valid annotation and query files for every chunk the plan names."""
    plan = json.loads((w.out/'ledger-plan.json').read_text())
    for lineage, value in plan['lineages'].items():
        (w.out/'ledgers'/lineage).mkdir(parents=True, exist_ok=True)
        (w.out/'queries'/lineage).mkdir(parents=True, exist_ok=True)
        for index, chunk in enumerate(value['chunks']):
            viewed = len(chunk['required_frames'])
            lines = [dict(type='fact', id='F1', statement='s', category='place', observed='text', stored=None)] \
                if index == 0 else [dict(type='carry', fact='F1', boundary=chunk['incoming_boundary'],
                                         carried=False, where=None)]
            (w.out/'ledgers'/lineage/f'{chunk["chunk"]}.jsonl').write_text(
                '\n'.join(json.dumps(line) for line in [*lines, dict(type='end', frames_viewed=viewed)]) + '\n')
            if chunk['chunk'] in value['queries']:
                query = dict(type='query', id='Q1', question='q', answer='a', frame='f-1', category='place')
                (w.out/'queries'/lineage/f'{chunk["chunk"]}.jsonl').write_text(
                    '\n'.join(json.dumps(line) for line in [query, dict(type='end', frames_viewed=viewed)]) + '\n')


@pytest.fixture
def ready(judged, capsys):
    judged.run('held-out-probes')
    judged.run('held-out-timelines', '--to', str(judged.to))
    annotate(judged)
    capsys.readouterr()
    return judged


def test_freeze_digests_every_file_and_prints_only_counts(ready, capsys):
    assert ready.run('held-out-freeze', '--frozen', '2026-11-10') == 0
    figures = quiet(capsys, ready)
    frozen = json.loads((ready.out/'frozen.json').read_text())
    assert frozen['schema'] == 'p1-held-out-frozen/1' and frozen['frozen'] == '2026-11-10'
    files = frozen['files']
    assert {k for k in files if k.startswith('batches/')} == {f'batches/confirm-{n:03d}.json' for n in range(1, 5)}
    assert {k for k in files if k.startswith('judgments/')} == {f'judgments/confirm-{n:03d}.jsonl' for n in range(1, 5)}
    assert {k for k in files if not k.startswith(('batches/', 'judgments/', 'ledgers/', 'queries/'))} == {
        'candidates.json', 'ledger-plan.json', 'probes.jsonl'}
    assert sum(k.startswith('ledgers/') for k in files) == 6 and sum(k.startswith('queries/') for k in files) == 3
    for name, digest in files.items():
        assert validation.file_sha256(ready.out/name) == digest
    assert figures == dict(frozen_sha256=validation.file_sha256(ready.out/'frozen.json'), files=len(files),
                           batches=4, ledgers=6, queries=3)
    with pytest.raises(SystemExit, match='frozen once'):
        ready.run('held-out-freeze')


def test_no_file_under_the_output_root_names_a_local_path(ready):
    ready.run('held-out-freeze')
    files = [p for p in ready.out.rglob('*') if p.is_file()]
    assert len(files) > 20
    forbidden = {str(ready.root), str(ready.root.resolve()), str(ready.out.parent), str(ready.out.parent.resolve()),
                 str(Path.home()), str(ready.to)}
    for path in files:
        text = path.read_text(encoding='utf-8')
        assert not any(bad in text for bad in forbidden), path.name
        assert not re.search(r'"/(Users|home|private|var|tmp)/', text), path.name
    # The judge copies, which do hold absolute paths, are the only files that name the evidence root.
    assert str(ready.root.resolve()) in (ready.judge/'confirm-001.json').read_text()
    assert ready.judge.resolve() not in [p.resolve() for p in ready.out.rglob('*')]


def drop(path):
    return lambda w: (w.out/path).unlink()


def rewrite(path, change):
    def apply(w):
        file = w.out/path
        file.write_text('\n'.join(change(file.read_text().splitlines())) + '\n')
    return apply


@pytest.mark.parametrize('damage, message', [
    (drop('ledgers/lh1/lh1a1-002.jsonl'), 'ledgers: 1 missing'),
    (drop('queries/lh1/lh1a1-001.jsonl'), 'queries: 1 missing'),
    (lambda w: (w.out/'queries'/'lh3'/'lh3a1-001.jsonl').write_text('{"type":"end","frames_viewed":9}\n'),
     'queries: 0 missing, 1 unexpected'),                                           # the last chunk precedes no boundary
    (lambda w: (w.out/'ledgers'/'lh3'/'extra.jsonl').write_text('{}\n'), 'unexpected'),
    (drop('ledger-plan.json'), 'Missing ledger-plan.json'),
    (drop('probes.jsonl'), 'Missing probes.jsonl'),
    (drop('judgments/confirm-002.jsonl'), 'confirm-002: the batch has no judgments'),
    (rewrite('probes.jsonl', lambda lines: lines[1:]), 'does not match the batches'),
    (rewrite('ledgers/lh1/lh1a1-002.jsonl', lambda lines: lines[-1:]), 'without a carry line'),
    (rewrite('ledgers/lh1/lh1a1-002.jsonl', lambda lines: lines[:-1]), 'missing end line'),
    (rewrite('ledgers/lh1/lh1a1-001.jsonl', lambda lines: [*lines[:-1], '{"type":"end"}']), 'frames_viewed is below'),
    (rewrite('ledgers/lh1/lh1a1-001.jsonl', lambda lines: [*lines[:-1], '{"type":"end","frames_viewed":0}']),
     'frames_viewed is below'),
    (rewrite('queries/lh1/lh1a1-001.jsonl', lambda lines: lines[:-1]), 'must end with frames_viewed'),
    (rewrite('queries/lh1/lh1a1-001.jsonl', lambda lines: [lines[0], lines[0], lines[1]]), 'unique id'),
    (rewrite('queries/lh1/lh1a1-001.jsonl', lambda lines: [lines[0].replace('"answer": "a"', '"answer": ""')
                                                          .replace('"answer":"a"', '"answer":""'), lines[1]]), 'unique id'),
    (rewrite('queries/lh1/lh1a1-001.jsonl', lambda lines: [lines[0]] * 41 + [lines[1]]), 'more than 40'),
])
def test_freeze_refuses_incompleteness(ready, damage, message):
    damage(ready)
    with pytest.raises(SystemExit, match=message):
        ready.run('held-out-freeze')
    assert not (ready.out/'frozen.json').exists()


def test_freeze_refuses_a_plan_for_other_chunks(ready):
    plan = json.loads((ready.out/'ledger-plan.json').read_text())
    plan['lineages']['lh3']['chunks'][0]['chunk'] = 'lh3a1-009'
    (ready.out/'ledger-plan.json').write_text(json.dumps(plan))
    with pytest.raises(SystemExit, match='different chunks'):
        ready.run('held-out-freeze')


def test_the_existing_development_commands_still_take_their_old_default_output(monkeypatch, tmp_path, capsys):
    seen = {}
    monkeypatch.setattr(validation, 'candidates', lambda evidence, out: seen.update(out=out) or {'lineages': {}})
    assert validation.main(['candidates', '--evidence-root', str(tmp_path)]) == 0
    assert seen['out'] == validation.ROOT/'data'/'evaluation'/'probes'/'validation'
    assert validation.HELD_OUT_DIR == validation.ROOT/'data'/'evaluation'/'p1'/'held-out'


# ---------------------------------------------------------------------------------------------
# p1-study/2: lh4 is a held-out lineage of study 522-held-out, written beside lh1-lh3's directory.

def test_lh4_is_refused_as_a_development_lineage_and_is_unknown_until_it_has_admissions(monkeypatch, tmp_path):
    # Every refusal below comes before any read; the directories are scratch so a regression could not reach real data.
    monkeypatch.setattr(validation, 'HELD_OUT_DIR', tmp_path/'p1'/'held-out')
    monkeypatch.setattr(validation, 'HELD_OUT_LH4_DIR', tmp_path/'p1'/'held-out-lh4')
    monkeypatch.setenv('ENACTIVE_EVIDENCE_ROOT', str(tmp_path/'no-evidence'))
    assert 'lh4' in validation.HELD_OUT and validation.HELD_OUT_STUDIES['lh4'] == '522-held-out'
    assert {validation.HELD_OUT_STUDIES[n] for n in ('lh1', 'lh2', 'lh3')} == {'372-382-dev-loop'}
    assert validation.HELD_OUT_RUNS['lh4'] == p1_analysis.LH4_ADMISSIONS
    monkeypatch.delitem(validation.HELD_OUT_RUNS, 'lh4')    # as it was before #522 named its admissions
    with pytest.raises(SystemExit, match='lh4'):
        validation.main(['held-out-candidates', '--lineages', 'lh4'])
    with pytest.raises(SystemExit, match='not a held-out lineage'):
        validation.main(['held-out-candidates', '--lineages', 'lh9'])
    for bad in (['lh1', 'lh1'], []):
        with pytest.raises(SystemExit):
            validation.main(['held-out-candidates', '--lineages', *bad])


@pytest.fixture
def lh4(world, monkeypatch, tmp_path):
    """lh4's two admissions in study 522-held-out, with one re-opened screen; the lh1-lh3 directory and lh4's are tmp."""
    monkeypatch.setitem(validation.HELD_OUT_RUNS, 'lh4', ('lh4b1', 'lh4b2'))
    monkeypatch.setitem(p1_analysis.HELD_OUT, 'lh4', ('lh4b1', 'lh4b2'))
    monkeypatch.setattr(validation, 'HELD_OUT_DIR', tmp_path/'p1'/'held-out')
    monkeypatch.setattr(validation, 'HELD_OUT_LH4_DIR', tmp_path/'p1'/'held-out-lh4')
    study = world.root/'522-held-out'
    for run, values in (('lh4b1', [0, FULL]), ('lh4b2', [FULL, flip(0, 5)])):
        sources = [f's-{run}-{i}' for i in range(len(values))]
        world.hashes.update(zip(sources, values))
        build_session(study, run, {'001': sources})
    world.secrets += list(world.hashes)
    world.out = validation.HELD_OUT_LH4_DIR
    return world


def run_lh4(w, *step, extra=()):
    more = ['--judge-dir', str(w.judge)] if step[0] == 'held-out-batches' else []
    return validation.main([*step, '--evidence-root', str(w.root), '--lineages', 'lh4', *more, *extra])


def test_lh4_reads_its_own_study_and_writes_only_under_held_out_lh4(lh4, capsys):
    assert run_lh4(lh4, 'held-out-candidates') == 0
    assert quiet(capsys, lh4) == {'lh4': dict(chunks=2, candidates=1)}
    assert [c['lineage'] for c in candidates_of(lh4)] == ['lh4']
    assert candidates_of(lh4)[0]['later_path'].startswith('522-held-out/computer-sessions/lh4b2/')
    assert run_lh4(lh4, 'held-out-batches') == 0
    capsys.readouterr()
    judge(lh4, same=lambda n: True, informative=lambda n: True)
    assert run_lh4(lh4, 'held-out-probes') == 0
    assert quiet(capsys, lh4)['lineages'] == {'lh4': dict(candidates=1, confirmed=1, primary=1, units=1)}
    assert (lh4.out/'probes.jsonl').is_file()
    assert not validation.HELD_OUT_DIR.exists()          # nothing reaches lh1-lh3's directory
    assert sorted(p.name for p in validation.HELD_OUT_LH4_DIR.parent.iterdir()) == ['held-out-lh4']


def test_lh4_never_goes_in_the_lh1_to_lh3_directory_and_is_never_mixed_without_an_output(lh4, tmp_path):
    with pytest.raises(SystemExit, match='held-out-lh4'):
        run_lh4(lh4, 'held-out-candidates', extra=['--out', str(validation.HELD_OUT_DIR)])
    with pytest.raises(SystemExit, match='kept apart'):
        validation.main(['held-out-candidates', '--evidence-root', str(lh4.root), '--lineages', 'lh1', 'lh4'])
    assert not validation.HELD_OUT_DIR.exists() and not validation.HELD_OUT_LH4_DIR.exists()
    # Mixed with an explicit output, each lineage still reads its own study.
    mixed = tmp_path/'mixed'
    assert validation.main(['held-out-candidates', '--evidence-root', str(lh4.root), '--lineages', 'lh3', 'lh4',
                            '--out', str(mixed)]) == 0
    assert set(json.loads((mixed/'candidates.json').read_text())['lineages']) == {'lh3', 'lh4'}
    # lh4's directory holds lh4 only.
    for lineages in (['lh3'], ['lh3', 'lh4'], []):
        with pytest.raises(SystemExit, match='holds lh4 only'):
            validation.main(['held-out-candidates', '--evidence-root', str(lh4.root),
                             *(['--lineages', *lineages] if lineages else []),
                             '--out', str(validation.HELD_OUT_LH4_DIR)])
    assert not validation.HELD_OUT_LH4_DIR.exists()


def test_the_held_out_steps_default_to_lh1_to_lh3_even_when_lh4_is_known(lh4, tmp_path):
    out = tmp_path/'default'
    assert validation.main(['held-out-candidates', '--evidence-root', str(lh4.root), '--out', str(out)]) == 0
    assert set(json.loads((out/'candidates.json').read_text())['lineages']) == {'lh1', 'lh2', 'lh3'}
    validation.HELD_OUT_DIR.mkdir(parents=True)
    assert validation.main(['held-out-candidates', '--evidence-root', str(lh4.root)]) == 0
    assert (validation.HELD_OUT_DIR/'candidates.json').is_file() and not validation.HELD_OUT_LH4_DIR.exists()
