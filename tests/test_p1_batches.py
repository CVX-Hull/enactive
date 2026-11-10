"""The P1 answer-key chain's batches, screen and parsing (#529): synthetic probes, evidence, deliveries and judge files only."""
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
CANARY_Q = 'QUESTION-ZEBRA'
CANARY_K = 'KEY-GIRAFFE'
CANARY_A = 'ANSWER-PELICAN'
ARM_KEYS = (('A', 1), ('B', 1), ('B', 2))
DEV_KEYS = (('A', 1), ('B', 1))                 # a development delivery has one B repeat
TEXTS = (*ARM_KEYS, ('R', 1), ('PW', 1), ('PP', 1))
QUESTIONS_DIR = ('data', 'evaluation', 'p1', 'questions')   # the only place a questions freeze may be written


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


def build_world(root: Path, *, items_per_row: int = 3, units: int = 5, late: bool = False,
                required: tuple[int, ...] = (1, 2)) -> SimpleNamespace:
    """Four held-out lineages in two frozen directories, a sealed evidence tree and a delivery.

    `required` are the capture ids of each chunk's coverage-rule frames, in the plan's order. With `late`, lh1's
    boundary is between its second and third sessions and its items also cite a frame of the first."""
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
        shift = 1 if late and lineage == 'lh1' else 0
        run0, run1 = runs[shift], runs[shift + 1]
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
        plan[lineage] = dict(chunks=[dict(chunk=name, timeline=f'{name}.md', required_frames=[f'{name[:-4]}-{n}' for n in required],
                                          incoming_boundary=incoming) for name, incoming in ((before, None), (after, boundary))])
        received = f'{CANARY_TEXT} received by {after}'
        marker = arms.Boundary(name=boundary, kind='handoff', predecessor=before, successor=after, cutoff=1.0,
                               admission=1, received_path=Path('unused'))
        sha = 'f' * 64
        delivered.append(replay._row(lineage, marker, 'R', 1, received, sha, None))
        for arm, repeat in ARM_KEYS:
            word = 'alpha' if arm == 'A' else ('beta' if repeat == 1 else 'gamma')    # the statement never names its arm
            items = [arms.Item('note', f'{lineage} {word} statement {k}',
                               cites=(f'{run0}-{1 + k % 3}', 'unsealed-frame-9', *((f'{runs[0]}-5',) if shift else ())))
                     for k in range(items_per_row)]
            delivered.append(replay._row(lineage, marker, arm, repeat, received, sha, arms.render(items)))
    rows = by_directory['held-out'][0] + by_directory['held-out-lh4'][0]
    paths = [write_frozen(root/name, *parts) for name, parts in by_directory.items()]
    path = root/'delivered.jsonl'
    path.write_text(''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in delivered))
    return SimpleNamespace(root=root, evidence=evidence, probes=paths, delivered=path,
                           rows=[r for r in rows], delivered_rows=delivered,
                           units=analysis.units(analysis.primary_probes(rows)))


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


def cli(*args) -> int:
    return analysis.main([str(a) for a in args])


def write_jsonl(path: Path, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    return path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def key_of(out: Path, kind: str) -> dict:
    return json.loads((out/'keys'/f'{kind}.json').read_text())


def batch_files(out: Path, kind: str) -> list[dict]:
    prefix = batches.KINDS[kind]['prefix']
    return [json.loads(p.read_text()) for p in sorted((out/'batches').glob(f'{prefix}-*.json'))]


def ordered_items(out: Path, kind: str) -> list[tuple[dict, dict]]:
    """(the judge-facing item, the key's record of it) in batch order."""
    key = key_of(out, kind)
    return [(item, key['items'][item['id']]) for batch in batch_files(out, kind) for item in batch['items']]


# ------------------------------------------------------------------ synthetic inputs
def question_of(probe: str) -> dict:
    return dict(schema=analysis.QUESTION_SCHEMA, probe=probe, question=f'{CANARY_Q} which entries does list {probe[-2:]} show?',
                key=f'{CANARY_K} bolt, saw')


def screen_counts(world, flagged_twice: int = 0) -> Path:
    """The screen's counts file: what `screen` wrote, as far as the freeze reads it."""
    path = world.root/'screen-counts.json'
    path.write_text(json.dumps(dict(questions=20, flagged=flagged_twice, flagged_twice=flagged_twice)))
    return path


def freeze_args(world, path: Path) -> list:
    """`questions-freeze` over the held-out world's frozen probes and a screen's counts."""
    probes = [a for p in world.probes for a in ('--probes', p)]
    return ['questions-freeze', '--questions', path, '--frozen', '2026-11-11', *probes, '--screen', screen_counts(world)]


def write_questions(world, name: str = 'questions', *, freeze: bool | str = True, skip: int | None = None) -> Path:
    """A questions file for every unit (one unit's question left out with `skip`) under the questions directory,
    frozen by the command; `freeze='by hand'` writes a `frozen.json` the command would refuse to."""
    path = world.root.joinpath(*QUESTIONS_DIR)/name/'questions.jsonl'
    if not path.exists():
        write_jsonl(path, [question_of(u['probe']) for n, u in enumerate(world.units) if n != skip])
    if freeze and not (path.parent/'frozen.json').exists():
        if freeze == 'by hand':
            (path.parent/'frozen.json').write_text(json.dumps(dict(schema=analysis.FROZEN_SCHEMA,
                                                                  files={path.name: analysis.file_sha256(path)})))
        else:
            assert cli(*freeze_args(world, path)) == 0
    return path


def write_sentences(world) -> Path:
    rows = [dict(schema=batches.SENTENCE_SCHEMA, probe=u['probe'], sentence=f'It holds bolt and saw ({n}).', attempts=1, correct=True)
            for n, u in enumerate(world.units)]
    return write_jsonl(world.root/'sentences.jsonl', rows)


def answer_row(probe, arm, repeat, answer, *, source='reader', rejudge=False) -> dict:
    return dict(schema=batches.ANSWER_SCHEMA, source=source, probe=probe, arm=arm, repeat=repeat, rejudge=rejudge, answer=answer)


def reader_answers(world, answer=lambda probe, arm, repeat: f'{CANARY_A} {arm}{repeat}', rejudge=False) -> Path:
    sample = analysis.rejudge_sample(world.units)
    rows = [answer_row(u['probe'], arm, repeat, answer(u['probe'], arm, repeat), rejudge=rejudge)
            for u in world.units for arm, repeat in TEXTS if not rejudge or (analysis.KIND, arm, repeat, u['probe']) in sample]
    return write_jsonl(world.root/('answers-rejudge.jsonl' if rejudge else 'answers.jsonl'), rows)


def build(world, kind: str, name: str | None = None, *extra) -> Path:
    """`batches <kind>` over the held-out world with the inputs the kind needs."""
    out = world.root/'.runtime'/'out'/(name or kind)
    assert run(world, kind, out, *extra) == 0
    return out


def run(world, kind: str, out: Path, *extra) -> int:
    probes = [a for p in world.probes for a in ('--probes', p)]
    base = ['--evidence-root', world.evidence, '--out', out, '--host-version', HOST]
    if kind == 'audit':
        return cli('batches', kind, *probes, '--delivered', world.delivered, *base, *extra)
    if kind == 'question':
        return cli('batches', kind, *probes, *base, *extra)
    if kind == 'reader':
        return cli('batches', kind, *probes, '--delivered', world.delivered, *base, *extra)
    return cli('batches', kind, *base, *extra)


def reader_build(world, name: str = 'reader', *, questions=None, sentences=None, rejudge=False) -> Path:
    questions = questions or write_questions(world)
    extra = ['--rejudge'] if rejudge else ['--sentences', sentences or write_sentences(world)]
    return build(world, 'reader', name, '--questions', questions, *extra)


def grader_build(world, answers: Path, questions: Path, name: str = 'grader') -> Path:
    return build(world, 'grader', name, '--answers', answers, '--questions', questions)


def answers_for(out: Path, kind: str, make, name: str = 'answers') -> Path:
    key = key_of(out, kind)
    dest = out.parent/f'{out.name}-{name}'
    dest.mkdir(parents=True)
    for batch in key['batches']:
        (dest/f'{batch["name"]}.jsonl').write_text(
            ''.join(json.dumps(make(i, key['items'][i])) + '\n' for i in batch['ids']))
    return dest


def parsed(out: Path, kind: str, make, tmp_path: Path, *extra) -> Path:
    answers = answers_for(out, kind, make)
    rows_file = tmp_path/f'{out.name}-rows.jsonl'
    assert cli('parse', kind, '--batches', out, '--answers', answers, '--out', rows_file, *extra) == 0
    return rows_file


# ------------------------------------------------------------------ the frozen briefs
def page_brief(label: str) -> str:
    text = (analysis.ROOT/'docs'/'design'/'p1-study-3.md').read_text()
    paragraph = next(p for p in text.split('\n\n') if p.startswith(f'> **{label}.**'))
    joined = ' '.join(line[1:].strip() for line in paragraph.splitlines())
    assert joined.startswith(f'**{label}.** ')
    return joined[len(f'**{label}.** '):]


@pytest.mark.parametrize('label, start, end', [
    ('Question', 'You write one question about each screenshot for a memory study.',
     '{"id":"<id>","question":"<one question>","key":"<the answer, as the image shows it>"}.'),
    ('Reader', 'You answer questions from a text.', '{"id":"<id>","answer":"<one sentence, or not stated>"}.'),
    ('Grader', 'You check answers against an answer key.', '{"id":"<id>","correct":true|false,"why":"<one line>"}.'),
    ('Guess', 'You answer questions about a computer game from what you already know.',
     '{"id":"<id>","answer":"<one sentence, or not stated>"}.'),
    ('Paraphrase', 'You restate answers as sentences.', '{"id":"<id>","sentence":"<one sentence>"}.'),
    ('Audit', 'You check statements against recorded screenshots.', '"why":"<one line>"}.')])
def test_the_frozen_briefs_are_the_pre_registrations_text_word_for_word(label, start, end):
    brief = batches.frozen_brief(label)
    assert brief == page_brief(label)
    assert brief.startswith(start) and brief.endswith(end) and '**' not in brief and '\n' not in brief


def test_the_retired_briefs_are_gone_and_guess_is_not_the_arm_guess_brief():
    for label in ('Scoring', 'Arm guess'):
        with pytest.raises(batches.BatchError, match='brief was not found'):
            batches.frozen_brief(label)
    assert not (analysis.ROOT/'docs'/'design'/'p1-study-3.md').read_text().count('Arm guess')
    assert batches.frozen_brief('Guess').startswith('You answer questions about a computer game')


def test_a_brief_the_page_does_not_have_is_refused(tmp_path):
    doc = tmp_path/'page.md'
    doc.write_text('> **Confirmation.** something\n')
    with pytest.raises(batches.BatchError, match='Grader brief was not found'):
        batches.frozen_brief('Grader', doc)


def test_every_kind_carries_its_own_brief():
    assert {kind: spec['brief'] for kind, spec in batches.KINDS.items()} == dict(
        question='Question', screen='Guess', paraphrase='Paraphrase', reader='Reader', grader='Grader', audit='Audit')
    assert len({spec['letter'] for spec in batches.KINDS.values()}) == 6


# ------------------------------------------------------------------ question batches
def test_question_batches_hold_one_item_per_unit_with_an_id_and_a_frame_in_probe_order(world, capsys):
    out = build(world, 'question')
    summary = json.loads(capsys.readouterr().out)
    files, key = batch_files(out, 'question'), key_of(out, 'question')
    assert len(world.units) == 20 and summary['items'] == 20 and summary['batches'] == 2 == len(files)
    assert set(summary) == {'kind', 'items', 'batches', 'key_sha256', 'batches_sha256'}
    assert [len(b['items']) for b in files] == [10, 10]
    items = [i for b in files for i in b['items']]
    assert [key['items'][i['id']]['item'] for i in items] == sorted(u['probe'] for u in world.units)    # no shuffle
    for batch in files:
        assert set(batch) == {'schema', 'brief', 'items'} and batch['brief'] == batches.frozen_brief('Question')
    for item in items:
        assert set(item) == {'id', 'frame'} and re.fullmatch(r'q[0-9a-f]{8}-[0-9]{4}', item['id'])
        lineage, rest = key['items'][item['id']]['item'].split('-p')
        run0, study = analysis.HELD_OUT[lineage][0], HELD_OUT_STUDIES[lineage]
        expected = world.evidence/study/'computer-sessions'/run0/'sources'/f'{run0}-{20 + int(rest)}.png'
        assert Path(item['frame']) == expected.resolve() and Path(item['frame']).is_file()
    assert key['batch_files'] == {b['name']: analysis.file_sha256(out/'batches'/f'{b["name"]}.json') for b in key['batches']}


def test_a_rewrite_batch_is_the_flagged_units_with_their_rejected_question(world, tmp_path, capsys):
    questions = write_questions(world, freeze=False)
    flagged = tmp_path/'flagged.txt'
    chosen = [world.units[3]['probe'], world.units[0]['probe']]
    flagged.write_text('\n'.join(chosen) + '\n\n')
    out = build(world, 'question', 'rewrite', '--rewrite', flagged, '--questions', questions)
    (batch,) = batch_files(out, 'question')
    key = key_of(out, 'question')
    assert [key['items'][i['id']]['item'] for i in batch['items']] == sorted(chosen)
    for item in batch['items']:
        assert set(item) == {'id', 'frame', 'rejected'}
        assert item['rejected'] == question_of(key['items'][item['id']]['item'])['question']
    assert key['rewrite'] is True and not key_of(build(world, 'question', 'plain'), 'question')['rewrite']
    for number_, (ids, message) in enumerate((('lh1-p9999\n', 'units that have a question'), ('\n\n', 'at least one probe id'))):
        flagged.write_text(ids)
        assert run(world, 'question', tmp_path/'.runtime'/f'x{number_}', '--rewrite', flagged, '--questions', questions) == 2
        assert message in capsys.readouterr().err
    assert run(world, 'question', tmp_path/'.runtime'/'y', '--rewrite', flagged) == 2         # the rejected need --questions


def test_question_batches_refuse_a_missing_frame_naming_a_count_only(world, tmp_path, capsys):
    next(iter((world.evidence/HELD_OUT_STUDIES['lh2']/'computer-sessions').rglob('lh2a1-21.png'))).unlink()
    assert run(world, 'question', tmp_path/'.runtime'/'o') == 2
    error = capsys.readouterr().err
    assert '1 earlier frames missing' in error and 'lh2a1-21' not in error and not (tmp_path/'.runtime'/'o').exists()


# ------------------------------------------------------------------ development units
def dev_world(root: Path, units: int = 4) -> SimpleNamespace:
    """A units file of development lineages, tiny frames and a delivery with a development lineage's rows."""
    rows, delivered = [], []
    for n in range(units):
        frame = root/'evidence'/'dev'/f'f{n}.png'
        frame.parent.mkdir(parents=True, exist_ok=True)
        frame.write_bytes(b'png')
        lineage = '397' if n % 2 == 0 else '372'
        rows.append(dict(probe=f'pair-{n:02d}', lineage=lineage, boundary=f'b{n}', frame=f'dev/f{n}.png'))
        for arm, repeat in (('R', 1), *DEV_KEYS):       # A repeat 1 and B repeat 1: development has no second B repeat
            delivered.append(dict(schema='p1-delivered/2', lineage=lineage, boundary=f'b{n}', arm=arm, repeat=repeat,
                                  text=f'{arm}{repeat} text {n}', items=0, complete=True))
    return SimpleNamespace(root=root, evidence=root/'evidence', rows=rows, delivered_rows=delivered,
                           units_file=write_jsonl(root/'units.jsonl', rows[::-1]),    # not in probe order
                           delivered=write_jsonl(root/'dev-delivered.jsonl', delivered), units=[dict(probe=r['probe'], lineage=r['lineage'],
                                                 boundary=r['boundary'], cluster=r['probe']) for r in rows])


def dev_questions(dev) -> Path:
    return write_jsonl(dev.root/'dev-questions.jsonl', [question_of(r['probe']) for r in dev.rows])


def test_development_question_batches_read_the_units_file_in_probe_order_without_the_held_out_probes(tmp_path):
    dev = dev_world(tmp_path)
    out = tmp_path/'.runtime'/'dq'
    assert cli('batches', 'question', '--development', dev.units_file, '--evidence-root', dev.evidence, '--out', out,
               '--host-version', HOST) == 0
    key = key_of(out, 'question')
    items = [i for b in batch_files(out, 'question') for i in b['items']]
    assert [key['items'][i['id']]['item'] for i in items] == [f'pair-{n:02d}' for n in range(4)]
    assert [Path(i['frame']) for i in items] == [(dev.evidence/'dev'/f'f{n}.png').resolve() for n in range(4)]


@pytest.mark.parametrize('mutate, message', [
    (lambda rows: rows + [dict(rows[0], probe='x', lineage='lh2')], 'development lineages only; lh2 is held out'),
    (lambda rows: rows + [dict(rows[0])], 'repeats a probe'),
    (lambda rows: [{k: v for k, v in rows[0].items() if k != 'frame'}], 'is not a development unit'),
    (lambda rows: [dict(rows[0], frame='')], 'is not a development unit'),
    (lambda rows: [], 'no development units')])
def test_a_development_units_file_that_is_not_development_units_is_refused(tmp_path, capsys, mutate, message):
    dev = dev_world(tmp_path)
    bad = write_jsonl(tmp_path/'bad.jsonl', mutate(dev.rows))
    assert cli('batches', 'question', '--development', bad, '--evidence-root', dev.evidence, '--out', tmp_path/'.runtime'/'o',
               '--host-version', HOST) == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize('frame', ['lh2a1/sources/lh2a1-5.png', 'x/lh1/f.png', '522-held-out/computer-sessions/lh4b3/sources/f.png',
                                   'held-out/f.png', 'held-out-lh4/f.png', 'dev/../lh3a2/f.png', 'a/lh4b7/b/f.png'])
def test_a_development_frame_may_not_lie_under_a_held_out_session_directory(tmp_path, capsys, frame):
    dev = dev_world(tmp_path)
    bad = write_jsonl(tmp_path/'bad.jsonl', [dict(dev.rows[0], frame=frame)])
    assert cli('batches', 'question', '--development', bad, '--evidence-root', dev.evidence, '--out', tmp_path/'.runtime'/'o',
               '--host-version', HOST) == 2
    error = capsys.readouterr().err
    assert 'under a held-out session directory' in error and frame not in error and not (tmp_path/'.runtime'/'o').exists()


def test_a_run_takes_the_held_out_probes_or_a_development_file_not_both_and_not_neither(world, tmp_path, capsys):
    dev = dev_world(tmp_path/'dev')
    assert cli('batches', 'question', '--development', dev.units_file, '--probes', world.probes[0], '--evidence-root', world.evidence,
               '--out', tmp_path/'.runtime'/'a', '--host-version', HOST) == 2
    assert 'alternatives' in capsys.readouterr().err
    assert cli('batches', 'question', '--evidence-root', world.evidence, '--out', tmp_path/'.runtime'/'b', '--host-version', HOST) == 2
    assert 'need --probes (or --development)' in capsys.readouterr().err


# ------------------------------------------------------------------ the mechanical screen
@pytest.mark.parametrize('question, key, flags', [
    ('Which axe is here?', 'axe', set()),                               # a three-letter token does not count
    ('Which tool is here?', 'Tool', {'token'}),                         # four letters do, whatever the case
    ('Which room is it?', 'the Room beside', {'token'}),
    ('How many steps?', 'seven', set()),
    ('Which floor holds item 7?', '7 steps', {'token'}),                # a run of digits counts, of any length
    ('Which room is 12?', '120', set()),                                # a different run of digits
    ('What is on abc7?', '7', {'token'}),                               # letters and digits are separate runs: 7 is shared
    ('What is on abc7?', 'abc', set()),                                 # abc is three letters
    ('Which list?', 'a, b, c, d, e', set()),                            # five entries
    ('Which list?', 'a, b, c, d, e, f', {'entries'}),                   # six
    ('Which list?', 'a;b\nc,d;e\nf', {'entries'}),                      # commas, semicolons and line breaks
    ('Which list?', 'a, b, c, d, e,', set()),                           # an empty entry is not counted
    ('Which list?', 'a,, b', set()),
    ('Which list?', '', {'empty_key'}),
    ('Which list?', '  \n ', {'empty_key'}),
    ('Which tool?', 'tool, a, b, c, d, e', {'token', 'entries'})])
def test_the_mechanical_screen_rule_at_each_boundary(question, key, flags):
    assert batches.mechanical_flags(question, key) == flags


def test_tokens_are_lower_cased_runs_of_letters_or_digits_of_the_counted_length():
    assert batches.tokens('The AXE and 7 Bolts; room12, Ab1c') == {'bolts', 'room', '7', '12', '1'}
    assert batches.MAX_ENTRIES == 5 and batches.MIN_LETTERS == 4


def checks_file(path: Path, purpose: str, correct: dict[str, bool]) -> Path:
    return write_jsonl(path, [dict(schema=batches.CHECK_SCHEMA, purpose=purpose, probe=p, correct=c, answered=True)
                              for p, c in correct.items()])


def screen_questions(tmp_path) -> Path:
    rows = [dict(schema=analysis.QUESTION_SCHEMA, probe=f'p{n}', question=f'{CANARY_Q} what is held in box {chr(97 + n)}?', key=key)
            for n, key in enumerate(['', f'{CANARY_K} a, b, c, d, e, f, g', f'{CANARY_K} held', f'{CANARY_K} bolt', f'{CANARY_K} saw',
                                     f'{CANARY_K} held'])]
    return write_jsonl(tmp_path/'screen-questions.jsonl', rows)


def test_the_screen_flags_by_each_rule_and_prints_counts_only(tmp_path, capsys):
    questions = screen_questions(tmp_path)    # p0 empty key, p1 seven entries, p2 and p5 share a token, p3 and p4 clean
    graded = checks_file(tmp_path/'graded.jsonl', 'screen', {'p0': False, 'p1': False, 'p2': False, 'p3': False, 'p4': True, 'p5': True})
    out = tmp_path/'.runtime'/'screen-1'
    assert cli('screen', '--questions', questions, '--graded', graded, '--out', out) == 0
    printed = capsys.readouterr().out
    counts = json.loads(printed)
    assert counts == dict(questions=6, flagged_by=dict(empty_key=1, entries=1, token=2, no_text=2), flagged=5, flagged_twice=None)
    assert all(word not in printed for word in (CANARY_Q, CANARY_K, 'bolt', 'p0'))
    assert (out/'flagged.txt').read_text() == 'p0\np1\np2\np4\np5\n'      # probe ids only
    assert json.loads((out/'counts.json').read_text()) == counts
    assert cli('screen', '--questions', questions, '--graded', graded, '--out', out) == 2    # written once
    assert 'written once' in capsys.readouterr().err


def test_the_second_screen_run_counts_the_questions_flagged_again(tmp_path, capsys):
    questions = screen_questions(tmp_path)
    first = tmp_path/'.runtime'/'screen-1'
    graded = checks_file(tmp_path/'g1.jsonl', 'screen', {f'p{n}': n == 4 for n in range(6)})
    assert cli('screen', '--questions', questions, '--graded', graded, '--out', first) == 0
    ids = ['p0', 'p1', 'p2', 'p4', 'p5']      # the five flagged; a writer rewrote them: p0 is fixed, p4 is answerable again
    rows = [json.loads(line) for line in questions.read_text().splitlines()]
    rows[0]['key'] = f'{CANARY_K} bolt'
    rewritten = write_jsonl(tmp_path/'q2.jsonl', rows)
    second = tmp_path/'.runtime'/'screen-2'
    graded2 = checks_file(tmp_path/'g2.jsonl', 'screen', {p: p == 'p4' for p in ids})
    capsys.readouterr()
    assert cli('screen', '--questions', rewritten, '--graded', graded2, '--previous', first/'flagged.txt', '--out', second) == 0
    counts = json.loads(capsys.readouterr().out)
    assert counts['questions'] == 5 and counts['flagged_twice'] == counts['flagged'] == 4      # all but p0
    assert (second/'flagged.txt').read_text() == 'p1\np2\np4\np5\n'


def test_a_first_screen_run_that_flags_nothing_has_nothing_flagged_twice(tmp_path, capsys):
    rows = [dict(schema=analysis.QUESTION_SCHEMA, probe='p0', question='Which list is it?', key='bolt, saw')]
    questions = write_jsonl(tmp_path/'q.jsonl', rows)
    graded = checks_file(tmp_path/'g.jsonl', 'screen', {'p0': False})
    assert cli('screen', '--questions', questions, '--graded', graded, '--out', tmp_path/'.runtime'/'s') == 0
    assert json.loads(capsys.readouterr().out)['flagged_twice'] == 0


def test_the_screen_refuses_verdicts_that_do_not_cover_the_questions_without_printing_any(tmp_path, capsys):
    questions = screen_questions(tmp_path)
    partial = checks_file(tmp_path/'g.jsonl', 'screen', {'p0': False})
    assert cli('screen', '--questions', questions, '--graded', partial, '--out', tmp_path/'.runtime'/'a') == 2
    wrong = checks_file(tmp_path/'w.jsonl', 'paraphrase', {f'p{n}': False for n in range(6)})
    assert cli('screen', '--questions', questions, '--graded', wrong, '--out', tmp_path/'.runtime'/'b') == 2
    assert cli('screen', '--questions', questions, '--out', tmp_path/'.runtime'/'c') == 2
    captured = capsys.readouterr()
    assert captured.out == '' and 'cover exactly the 6 questions' in captured.err and 'screen needs --graded' in captured.err
    assert CANARY_Q not in captured.err and CANARY_K not in captured.err


def test_no_text_batches_hold_only_an_id_and_the_question_in_probe_order_under_the_guess_brief(world, tmp_path):
    questions = write_questions(world, freeze=False)
    out = build(world, 'screen', 'screen', '--questions', questions)
    files, key = batch_files(out, 'screen'), key_of(out, 'screen')
    assert [len(b['items']) for b in files] == [10, 10]
    assert all(b['brief'] == batches.frozen_brief('Guess') for b in files)
    items = [i for b in files for i in b['items']]
    assert all(set(i) == {'id', 'question'} and re.fullmatch(r'n[0-9a-f]{8}-[0-9]{4}', i['id']) for i in items)
    assert [key['items'][i['id']] for i in items] == [dict(item=u['probe']) for u in world.units]
    assert CANARY_K not in json.dumps(files) and 'bolt' not in json.dumps(files)        # never the key
    only = tmp_path/'only.txt'
    only.write_text(f'{world.units[7]["probe"]}\n{world.units[2]["probe"]}\n')
    (batch,) = batch_files(build(world, 'screen', 'again', '--questions', questions, '--only', only), 'screen')
    assert [i['question'] for i in batch['items']] == [question_of(world.units[n]['probe'])['question'] for n in (2, 7)]


# ------------------------------------------------------------------ paraphrase batches and the sentences
def test_paraphrase_batches_hold_an_id_the_question_and_the_key_in_probe_order(world):
    questions = write_questions(world, freeze=False)
    out = build(world, 'paraphrase', 'paraphrase', '--questions', questions)
    files, key = batch_files(out, 'paraphrase'), key_of(out, 'paraphrase')
    assert [len(b['items']) for b in files] == [10, 10] and all(b['brief'] == batches.frozen_brief('Paraphrase') for b in files)
    items = [i for b in files for i in b['items']]
    assert all(set(i) == {'id', 'question', 'key'} for i in items)
    assert [key['items'][i['id']]['item'] for i in items] == [u['probe'] for u in world.units]
    assert [(i['question'], i['key']) for i in items] == [(question_of(u['probe'])['question'], question_of(u['probe'])['key'])
                                                          for u in world.units]


def test_sentences_are_rewritten_once_checked_again_and_a_second_failure_is_used_as_is_and_counted(tmp_path, capsys):
    ids = ['p0', 'p1', 'p2', 'p3']
    first = write_jsonl(tmp_path/'p1.jsonl', [answer_row(p, 'S', 1, f'first {p}', source='paraphrase') for p in ids])
    checks1 = checks_file(tmp_path/'c1.jsonl', 'paraphrase', {'p0': True, 'p1': False, 'p2': True, 'p3': False})
    out1 = tmp_path/'.runtime'/'s1'
    assert cli('sentences', '--paraphrases', first, '--checks', checks1, '--out', out1) == 0
    assert json.loads(capsys.readouterr().out) == dict(units=4, stages=1, rewritten=0, failed=2)
    assert (out1/'failed.txt').read_text() == 'p1\np3\n'      # the ids for the rewrite batch
    second = write_jsonl(tmp_path/'p2.jsonl', [answer_row(p, 'S', 1, f'second {p}', source='paraphrase') for p in ('p1', 'p3')])
    checks2 = checks_file(tmp_path/'c2.jsonl', 'paraphrase', {'p1': True, 'p3': False})
    out2 = tmp_path/'.runtime'/'s2'
    assert cli('sentences', '--paraphrases', first, '--checks', checks1, '--paraphrases', second, '--checks', checks2,
               '--out', out2) == 0
    assert json.loads(capsys.readouterr().out) == dict(units=4, stages=2, rewritten=2, failed=1)
    rows = {r['probe']: r for r in read_jsonl(out2/'sentences.jsonl')}
    assert {p: (r['sentence'], r['attempts'], r['correct']) for p, r in rows.items()} == {
        'p0': ('first p0', 1, True), 'p1': ('second p1', 2, True), 'p2': ('first p2', 1, True), 'p3': ('second p3', 2, False)}
    assert (out2/'failed.txt').read_text() == 'p3\n'
    stray = write_jsonl(tmp_path/'p3.jsonl', [answer_row('p0', 'S', 1, 'x', source='paraphrase')])
    for pairs in ([stray, checks_file(tmp_path/'c3.jsonl', 'paraphrase', {'p0': True})],):     # not the failed ids
        assert cli('sentences', '--paraphrases', first, '--checks', checks1, '--paraphrases', pairs[0], '--checks', pairs[1],
                   '--out', tmp_path/'.runtime'/'s3') == 2
    assert cli('sentences', '--paraphrases', first, '--out', tmp_path/'.runtime'/'s4') == 2      # a check for every stage


# ------------------------------------------------------------------ reader batches
def test_a_reader_batch_is_one_file_per_item_with_an_id_a_text_and_a_question_in_a_seeded_shuffle(world, capsys):
    out = reader_build(world)
    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    files, key = batch_files(out, 'reader'), key_of(out, 'reader')
    assert summary['items'] == 120 == summary['batches'] == len(files) and all(len(b['items']) == 1 for b in files)
    delivered = {(r['lineage'], r['boundary'], r['arm'], r['repeat']): r for r in world.delivered_rows}
    sentences = {r['probe']: r['sentence'] for r in read_jsonl(world.root/'sentences.jsonl')}
    by_probe = {u['probe']: u for u in world.units}
    seen = []
    for batch in files:
        assert set(batch) == {'schema', 'brief', 'items'} and batch['brief'] == batches.frozen_brief('Reader')
        (item,) = batch['items']
        assert set(item) == {'id', 'text', 'question'} and re.fullmatch(r'r[0-9a-f]{8}-[0-9]{4}', item['id'])
        meta = key['items'][item['id']]
        unit = by_probe[meta['item']]
        assert item['question'] == question_of(meta['item'])['question']
        received = delivered[(unit['lineage'], unit['boundary'], 'R', 1)]['text']
        expected = {'A': lambda: delivered[(unit['lineage'], unit['boundary'], 'A', 1)]['text'],
                    'B': lambda: delivered[(unit['lineage'], unit['boundary'], 'B', meta['repeat'])]['text'],
                    'R': lambda: received,
                    'PW': lambda: f'{received}\n- {question_of(meta["item"])["question"]} {question_of(meta["item"])["key"]}',
                    'PP': lambda: f'{received}\n- {sentences[meta["item"]]}'}[meta['arm']]()
        assert item['text'] == expected                                # byte for byte
        if meta['arm'] in ('A', 'B', 'R'):
            assert CANARY_K not in item['text']                        # a reader never sees the answer key but in PW
        seen.append((meta['item'], meta['arm'], meta['repeat']))
    in_order = sorted(seen, key=lambda m: (m[0], batches.TEXT_ORDER.index(m[1]), m[2]))
    shuffled = list(in_order)
    random.Random(4916).shuffle(shuffled)                                          # Owner decision, 10 November 2026
    assert seen == shuffled and seen != in_order and batches.READER_SEED == 4916
    assert set(seen) == {(u['probe'], arm, repeat) for u in world.units for arm, repeat in TEXTS}
    assert key['rejudge'] is False and key['seed'] == 4916 and key['development'] is False
    assert key['questions_sha256'] == analysis.file_sha256(write_questions(world))


def test_reader_ids_and_file_names_do_not_follow_the_arm_and_are_reproducible(world):
    out, again = reader_build(world), reader_build(world, 'again')
    assert read_all(out) == read_all(again)                                        # the same inputs, the same files
    rank = {'A': 0, 'B': 1, 'R': 2, 'PW': 3, 'PP': 4}
    arms = [(number(item['id']), meta['arm']) for item, meta in ordered_items(out, 'reader')]
    assert [n for n, _ in arms] == list(range(1, 121))                              # numbered in the file order
    runs = [arm for _, arm in arms]
    assert runs != sorted(runs, key=rank.get)
    assert len({arm for arm in runs[:10]}) > 1                                      # the first files hold different texts
    assert key_of(out, 'reader')['seed'] == 4916
    rejudge = reader_build(world, 'rejudge', rejudge=True)                          # the re-judging has its own list, same seed
    sample = sorted(analysis.rejudge_sample(world.units))
    items = [(m['item'], m['arm'], m['repeat']) for _, m in ordered_items(rejudge, 'reader')]
    expected = sorted(((k[3], k[1], k[2]) for k in sample), key=lambda m: (m[0], batches.TEXT_ORDER.index(m[1]), m[2]))
    random.Random(4916).shuffle(expected)
    assert items == expected


@pytest.mark.parametrize('received, line, expected', [
    ('R text', 'a b', 'R text\n- a b'),
    ('R text\n', 'a b', 'R text\n- a b'),            # a text that ends in a line break gets no blank line
    ('', 'a b', '- a b'),
    ('R\ntext', 'a b', 'R\ntext\n- a b')])
def test_the_new_last_line_follows_the_text_on_a_line_of_its_own(received, line, expected):
    assert batches.appended(received, line) == expected


@pytest.mark.parametrize('key, line', [
    ('bolt,\n saw ;  nail', 'bolt; saw ; nail'),              # a line break is `; `, never doubled; other whitespace runs are one space
    ('bolt;\nsaw,\n', 'bolt; saw'),
    ('bolt\nsaw\r\nnail', 'bolt; saw; nail'),
    ('\n\n  bolt  \n\n\n saw\n', 'bolt; saw'),                # blank lines and leading or trailing breaks leave no separator
    ('bolt  saw', 'bolt saw'), ('', ''), (' \n ', '')])
def test_the_word_for_word_line_has_single_spaces_and_one_line_with_the_keys_lines_joined_by_semicolons(world, key, line):
    rows = [dict(question_of(u['probe']), question=' Which  list?\n', key=key) for u in world.units]
    path = world.root.joinpath(*QUESTIONS_DIR)/f'multi-{abs(hash(key))}'/'questions.jsonl'
    write_jsonl(path, rows)
    assert cli(*freeze_args(world, path)) == 0
    out = reader_build(world, questions=path)
    texts = [item['text'] for item, meta in ordered_items(out, 'reader') if meta['arm'] == 'PW']
    expected = f'\n- Which list? {line}'.rstrip(' ')
    assert texts and all(t.endswith(expected) and t.count('\n- ') == 1 for t in texts)


def test_the_reference_text_is_the_received_text_alone_from_its_delivered_row(world):
    out = reader_build(world)
    for item, meta in ordered_items(out, 'reader'):
        if meta['arm'] == 'R':
            assert item['text'].startswith(CANARY_TEXT) and '\n' not in item['text']
            assert 'Notes from earlier play' not in item['text']


def test_a_reader_build_needs_exactly_one_of_sentences_or_rejudge_and_one_row_per_unit(world, tmp_path, capsys):
    questions = write_questions(world)
    assert run(world, 'reader', tmp_path/'.runtime'/'a', '--questions', questions) == 2
    assert run(world, 'reader', tmp_path/'.runtime'/'b', '--questions', questions, '--rejudge', '--sentences', write_sentences(world)) == 2
    assert capsys.readouterr().err.count('not both') == 2
    short = write_jsonl(tmp_path/'short.jsonl', read_jsonl(write_sentences(world))[1:])
    assert run(world, 'reader', tmp_path/'.runtime'/'c', '--questions', questions, '--sentences', short) == 2
    assert f'not one {batches.SENTENCE_SCHEMA} row for each unit' in capsys.readouterr().err


def test_held_out_readers_need_the_frozen_questions_and_one_for_every_unit(world, tmp_path, capsys):
    questions = write_questions(world)
    questions.write_text(questions.read_text().replace('bolt', 'nail'))           # differs from its freeze
    assert run(world, 'reader', tmp_path/'.runtime'/'a', '--questions', questions, '--sentences', write_sentences(world)) == 2
    assert 'not a frozen questions file' in capsys.readouterr().err
    unfrozen = write_questions(world, 'unfrozen', freeze=False)
    assert run(world, 'reader', tmp_path/'.runtime'/'b', '--questions', unfrozen, '--sentences', write_sentences(world)) == 2
    assert 'not a frozen questions file' in capsys.readouterr().err
    missing = write_questions(world, 'missing', skip=3, freeze='by hand')       # the command would not freeze it
    assert run(world, 'reader', tmp_path/'.runtime'/'c', '--questions', missing, '--sentences', write_sentences(world)) == 2
    assert '1 units have none' in capsys.readouterr().err
    extra = write_jsonl(world.root.joinpath(*QUESTIONS_DIR)/'extra'/'questions.jsonl',
                        [*(question_of(u['probe']) for u in world.units), question_of('zz-p0001')])
    write_questions(world, 'extra', freeze='by hand')
    assert run(world, 'reader', tmp_path/'.runtime'/'d', '--questions', extra, '--sentences', write_sentences(world)) == 2
    assert '1 questions belong to no unit' in capsys.readouterr().err


def test_a_held_out_reader_build_still_needs_b_repeat_1_and_2_and_a_development_one_has_only_b_1(world, tmp_path, capsys):
    questions, sentences = write_questions(world), write_sentences(world)
    for gone in (('B', 1), ('B', 2)):
        rows = [r for r in world.delivered_rows if (r['arm'], r['repeat']) != gone]
        world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        assert run(world, 'reader', tmp_path/'.runtime'/f'held{gone[1]}', '--questions', questions, '--sentences', sentences) == 2
        assert '20 delivered texts missing' in capsys.readouterr().err               # five units in each of four lineages
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in world.delivered_rows))
    out = reader_build(world, questions=questions, sentences=sentences)
    assert {(m['arm'], m['repeat']) for _, m in ordered_items(out, 'reader')} == set(TEXTS)


def test_a_development_delivery_with_a_second_b_repeat_is_refused_as_unexpected(tmp_path, capsys):
    dev = dev_world(tmp_path)
    questions = dev_questions(dev)
    sentences = write_jsonl(tmp_path/'dev-sentences.jsonl', [dict(schema=batches.SENTENCE_SCHEMA, probe=r['probe'], sentence='s',
                                                                  attempts=1, correct=True) for r in dev.rows])
    common = ['--development', dev.units_file, '--questions', questions, '--host-version', HOST]
    extra = dict(next(r for r in dev.delivered_rows if (r['arm'], r['repeat']) == ('B', 1)), repeat=2)
    both = write_jsonl(tmp_path/'both.jsonl', dev.delivered_rows + [extra])
    for number_, mode in enumerate((['--sentences', sentences], ['--rejudge'])):
        assert cli('batches', 'reader', *common, '--delivered', both, *mode, '--out', tmp_path/'.runtime'/f'b{number_}') == 2
        error = capsys.readouterr().err
        assert '1 delivered rows are unexpected' in error and 'second B repeat' in error
    assert cli('batches', 'reader', *common, '--delivered', dev.delivered, '--sentences', sentences,
               '--out', tmp_path/'.runtime'/'ok') == 0


def test_reader_builds_refuse_missing_or_incomplete_delivered_texts_without_printing_any(world, tmp_path, capsys):
    questions, sentences = write_questions(world), write_sentences(world)
    rows = [r for r in world.delivered_rows if (r['lineage'], r['arm'], r['repeat']) != ('lh3', 'R', 1)]
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert run(world, 'reader', tmp_path/'.runtime'/'a', '--questions', questions, '--sentences', sentences) == 2
    error = capsys.readouterr().err
    assert '15 delivered texts missing' in error and CANARY_TEXT not in error     # R, PW and PP of lh3's five units
    rows = [dict(r, complete=False) if r['arm'] == 'B' and r['repeat'] == 2 else r for r in world.delivered_rows]
    world.delivered.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert run(world, 'reader', tmp_path/'.runtime'/'b', '--questions', questions, '--sentences', sentences) == 2
    assert '20 incomplete' in capsys.readouterr().err


def test_a_rejudging_reader_build_is_exactly_the_seeded_sample_of_a_and_b_with_ids_of_its_own(world):
    first, again = reader_build(world), reader_build(world, 'rejudge', rejudge=True)
    key = key_of(again, 'reader')
    got = {(analysis.KIND, m['arm'], m['repeat'], m['item']) for m in key['items'].values()}
    assert got == analysis.rejudge_sample(world.units) and len(got) == 12 and key['rejudge'] is True
    assert key['sample_seed'] == 4912 and all(i.startswith('r') for i in key['items'])
    assert not set(key['items']) & set(key_of(first, 'reader')['items'])       # the same inputs, another build
    assert {m['arm'] for m in key['items'].values()} <= {'A', 'B'}             # the controls are not re-judged
    assert all(len(b['items']) == 1 for b in batch_files(again, 'reader'))


def test_a_development_run_reads_every_a_and_b_label_twice_and_needs_no_freeze_or_held_out_probes(tmp_path, capsys):
    dev = dev_world(tmp_path)
    questions = dev_questions(dev)
    sentences = write_jsonl(tmp_path/'dev-sentences.jsonl', [dict(schema=batches.SENTENCE_SCHEMA, probe=r['probe'], sentence='s',
                                                                  attempts=1, correct=True) for r in dev.rows])
    common = ['--development', dev.units_file, '--delivered', dev.delivered, '--questions', questions, '--host-version', HOST]
    first, again = tmp_path/'.runtime'/'first', tmp_path/'.runtime'/'again'
    assert cli('batches', 'reader', *common, '--sentences', sentences, '--out', first) == 0
    assert cli('batches', 'reader', *common, '--rejudge', '--out', again) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[0])['items'] == 20             # four units, five texts: A1, B1, R, PW, PP
    key = key_of(again, 'reader')
    assert key['development'] is True and len(key['items']) == 8
    assert {(m['item'], m['arm'], m['repeat']) for m in key['items'].values()} == {
        (r['probe'], arm, repeat) for r in dev.rows for arm, repeat in DEV_KEYS}              # every label, not a sample
    assert {(m['arm'], m['repeat']) for _, m in ordered_items(first, 'reader')} == {*DEV_KEYS, ('R', 1), ('PW', 1), ('PP', 1)}
    texts = {meta['item']: item['text'] for item, meta in ordered_items(first, 'reader') if (meta['arm'], meta['repeat']) == ('PW', 1)}
    assert texts['pair-01'] == f'R1 text 1\n- {question_of("pair-01")["question"]} {question_of("pair-01")["key"]}'
    held = dev.delivered_rows + [dict(dev.delivered_rows[0], lineage='lh2')]
    write_jsonl(dev.delivered, held)
    assert cli('batches', 'reader', *common, '--rejudge', '--out', tmp_path/'.runtime'/'held') == 2
    assert 'held-out lineages given: lh2' in capsys.readouterr().err


# ------------------------------------------------------------------ grader batches
@pytest.mark.parametrize('answer', ['not stated', 'Not stated', 'NOT STATED.', '  not stated.  ', 'not stated.\n', '\tNot Stated'])
def test_an_answer_that_is_exactly_not_stated_is_labelled_incorrect_without_a_grader(answer):
    assert batches.not_stated(answer) is True


@pytest.mark.parametrize('answer', ['not stated..', 'not stated!', 'Not stated in the text.', 'not  stated', 'stated', '', 'not stated, a bolt',
                                    'it is not stated', 'not stated. Bolt'])
def test_any_other_answer_goes_to_a_grader(answer):
    assert batches.not_stated(answer) is False


def synthetic_grader_inputs(world, *, every=3):
    """Answers of every text of every unit, every `every`th one "not stated"."""
    counter = iter(range(10 ** 6))
    return reader_answers(world, answer=lambda p, a, r: 'Not stated.' if next(counter) % every == 0 else f'{CANARY_A} {a}{r}')


def test_grader_batches_hold_graded_answers_only_mixed_with_random_4915_and_packed_first_fit(world, capsys):
    answers, questions = synthetic_grader_inputs(world), write_questions(world)
    out = grader_build(world, answers, questions)
    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    key, files = key_of(out, 'grader'), batch_files(out, 'grader')
    rows = read_jsonl(answers)
    mechanical = [r for r in rows if batches.not_stated(r['answer'])]
    assert len(rows) == 120 and summary['mechanical'] == len(mechanical) == 40 and summary['items'] == 80
    assert len(key['mechanical']) == 40 and key['source'] == 'reader' and key['rejudge'] is False and key['seed'] == 4915
    graded = [(r['probe'], batches.TEXT_ORDER.index(r['arm']), r['repeat']) for r in rows if not batches.not_stated(r['answer'])]
    expected = sorted(graded)
    random.Random(4915).shuffle(expected)
    plan: list[list[tuple]] = []                                         # first-fit, written out independently
    for entry in expected:
        for batch in plan:
            if len(batch) < 10 and all(other[0] != entry[0] for other in batch):
                batch.append(entry)
                break
        else:
            plan.append([entry])
    got = [[(m['item'], batches.TEXT_ORDER.index(m['arm']), m['repeat']) for m in (key['items'][i['id']] for i in b['items'])] for b in files]
    assert got == plan
    for batch in files:
        assert set(batch) == {'schema', 'brief', 'items'} and batch['brief'] == batches.frozen_brief('Grader')
        assert 0 < len(batch['items']) <= 10
        assert all(set(i) == {'id', 'question', 'key', 'answer'} for i in batch['items'])
        assert not any(batches.not_stated(i['answer']) for i in batch['items'])
        probes = [key['items'][i['id']]['item'] for i in batch['items']]
        assert len(set(probes)) == len(probes)                             # no two answers to one question in a batch
        raw = json.dumps(batch)
        assert '"arm"' not in raw and 'repeat' not in raw                    # the grader is not told which text an answer came from
    by_id = {i['id']: i for b in files for i in b['items']}
    for opaque, meta in key['items'].items():
        assert by_id[opaque]['question'] == question_of(meta['item'])['question'] and by_id[opaque]['key'] == question_of(meta['item'])['key']
        assert by_id[opaque]['answer'] == f'{CANARY_A} {meta["arm"]}{meta["repeat"]}'


def test_grader_batches_follow_their_seed_and_are_reproducible(world, monkeypatch):
    answers, questions = synthetic_grader_inputs(world), write_questions(world)
    one, two = grader_build(world, answers, questions, 'one'), grader_build(world, answers, questions, 'two')
    assert read_all(one) == read_all(two) and read_all(one)
    monkeypatch.setattr(batches, 'GRADER_SEED', 4916)
    other = grader_build(world, answers, questions, 'three')
    assert read_all(other)['batches/grader-001.json'] != read_all(one)['batches/grader-001.json']
    assert not set(key_of(other, 'grader')['items']) & set(key_of(one, 'grader')['items'])
    monkeypatch.setattr(batches, 'GRADER_SEED', 4915)
    assert read_all(reader_build(world, 'reader-1')) == read_all(reader_build(world, 'reader-2'))
    assert read_all(build(world, 'question', 'question-1')) == read_all(build(world, 'question', 'question-2'))


def test_a_grader_build_with_only_not_stated_answers_has_no_batch_and_still_parses(world, tmp_path):
    answers = reader_answers(world, answer=lambda p, a, r: 'not stated')
    out = grader_build(world, answers, write_questions(world))
    assert batch_files(out, 'grader') == [] and key_of(out, 'grader')['items'] == {}
    (tmp_path/'none').mkdir()
    rows = batches.parse('grader', out, tmp_path/'none')
    assert len(rows) == 120 and all(r['stated'] is False and r['answered'] is False for r in rows)


def test_grader_answers_of_one_source_and_pass_for_probes_that_have_a_question_are_the_only_input(world, tmp_path, capsys):
    questions = write_questions(world)
    good = reader_answers(world)
    rows = read_jsonl(good)
    cases = {'mixed source': rows + [answer_row('x', 'N', 1, 'a', source='screen')],
             'mixed pass': rows[:-1] + [dict(rows[-1], rejudge=True)],
             'no question': rows + [answer_row('zz-p0001', 'A', 1, 'a')],
             'repeated': rows + [rows[0]],
             'wrong arm': [dict(rows[0], arm='C')] + rows[1:],
             'a screen answer that is a reader arm': [answer_row('p', 'A', 1, 'a', source='screen')],
             'extra field': [dict(rows[0], why='x')] + rows[1:]}
    for number_, (name, bad) in enumerate(cases.items()):
        assert run(world, 'grader', tmp_path/'.runtime'/f'g{number_}', '--answers', write_jsonl(tmp_path/f'bad{number_}.jsonl', bad),
                   '--questions', questions) == 2, name
    error = capsys.readouterr().err
    assert CANARY_A not in error and CANARY_Q not in error and CANARY_K not in error


def test_a_grader_build_over_a_rejudging_readers_answers_labels_its_rows_rejudge(world, tmp_path):
    questions = write_questions(world)
    out = grader_build(world, reader_answers(world, rejudge=True), questions)
    key = key_of(out, 'grader')
    assert key['rejudge'] is True and len(key['items']) + len(key['mechanical']) == 12
    rows = read_jsonl(parsed(out, 'grader', lambda i, m: dict(id=i, correct=True, why=CANARY_WORDS), tmp_path))
    assert len(rows) == 12 and all(r['type'] == 'label' and r['rejudge'] is True and r['answered'] is True for r in rows)


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
            assert set(item) == {'id', 'statement', 'frames'}    # one chronological frame list, no timeline file
            meta = key['items'][item['id']]
            lineage, rest = meta['item'].split('/')
            boundary, position = rest.rsplit('#', 1)
            row = delivered[(lineage, boundary, meta['arm'], meta['repeat'])]
            shown = row['working_set'][int(position)]
            assert item['statement'] == f'- {shown["statement"]}'
            assert item['statement'] in row['text'].splitlines()          # the line as the successor's text has it
            runs = analysis.HELD_OUT[lineage]
            study = world.evidence/HELD_OUT_STUDIES[lineage]/'computer-sessions'/runs[0]/'sources'
            cited = shown['cites'][0]       # the unsealed second cite is dropped
            wanted = sorted({f'{runs[0]}-1', f'{runs[0]}-2', cited}, key=lambda s: int(s.rsplit('-', 1)[1]))
            assert [f['source'] for f in item['frames']] == wanted         # coverage frames and the cited one, once each
            assert {f['source'] for f in item['frames'] if f['cited']} == {cited}
            assert all(set(f) == {'source', 'frame', 'cited'} and Path(f['frame']) == (study/f'{f["source"]}.png').resolve()
                       and Path(f['frame']).is_absolute() and Path(f['frame']).is_file() for f in item['frames'])
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


def audit_items(out: Path) -> list[tuple[dict, dict]]:
    return ordered_items(out, 'audit')


def capture(source: str) -> int:
    return int(source.rsplit('-', 1)[1])


def test_audit_frames_are_listed_in_capture_order_so_the_last_listed_is_the_latest(tmp_path):
    world = build_world(tmp_path, required=(1, 4, 7, 10, 6, 8, 9))     # the plan lists them out of order
    out = build(world, 'audit')
    for item, meta in audit_items(out):
        numbers = [capture(f['source']) for f in item['frames']]
        assert numbers == sorted(numbers) and len(numbers) == len(set(numbers))
        assert {1, 4, 6, 7, 8, 9, 10} <= set(numbers)
        assert numbers[-1] == max(numbers)
        assert [n for n in numbers if n in (1, 4, 6, 7, 8, 9, 10)] == [1, 4, 6, 7, 8, 9, 10]    # 10 after 9, not after 1
        assert sum(f['cited'] for f in item['frames']) == 1


def test_cited_frames_of_an_earlier_session_come_first(tmp_path):
    world = build_world(tmp_path, late=True, required=(1, 4, 7, 10, 6, 8, 9))
    out = build(world, 'audit')
    late = [item for item, meta in audit_items(out) if meta['item'].startswith('lh1/')]
    assert late
    for item in late:
        sources = [f['source'] for f in item['frames']]
        assert sources[0] == 'lh1a1-5' and item['frames'][0]['cited'] is True      # the first session's frame
        assert all(s.startswith('lh1a2-') for s in sources[1:])                    # then the predecessor's own session
        numbers = [capture(s) for s in sources[1:]]
        assert numbers == sorted(numbers) and sources[-1] == f'lh1a2-{max(numbers)}'
        assert Path(item['frames'][0]['frame']).parent.parent.name == 'lh1a1'
    other = [item for item, meta in audit_items(out) if not meta['item'].startswith('lh1/')]
    assert other and all(f['source'].startswith(('lh2', 'lh3', 'lh4')) for item in other for f in item['frames'])


def test_a_frame_that_is_cited_and_a_coverage_frame_is_listed_once_as_cited_and_a_later_session_sorts_after():
    coverage = [('s-1', 'p1', 0), ('s-10', 'p10', 0), ('s-9', 'p9', 0), ('s-2', 'p2', 0)]
    cited = [('s-9', 'p9', 0), ('r-3', 'q3', 1), ('q-3', 'z3', 0)]
    frames = batches.chronological(cited, coverage)
    assert [(f['source'], f['cited']) for f in frames] == [('s-1', False), ('s-2', False), ('q-3', True), ('s-9', True),
                                                           ('s-10', False), ('r-3', True)]
    with pytest.raises(batches.BatchError, match='numeric capture id'):
        batches.chronological([('no-digits-x', 'p', 0)], [])


# ------------------------------------------------------------------ packing
def test_a_batch_never_holds_two_answers_to_one_question_even_when_a_unit_would_straddle_a_boundary():
    entries = [dict(sort=(n, arm), unit=n, public={}, key={}) for n in range(4) for arm in 'abc']
    for seed in range(20):
        for batch in batches.pack(entries, seed):
            assert len(batch) <= 10 and len({e['unit'] for e in batch}) == len(batch)
    assert sum(map(len, batches.pack(entries, 1))) == 12
    twenty = [dict(sort=n, unit=n, public={}, key={}) for n in range(25)]
    assert [len(b) for b in batches.pack(twenty, 3)] == [10, 10, 5]


# ------------------------------------------------------------------ the build digest
@pytest.mark.parametrize('kind, constant', [('grader', 'GRADER_SEED'), ('grader', 'BATCH_SIZE'), ('grader', 'PACKING'),
                                            ('question', 'BATCH_SIZE'), ('screen', 'BATCH_SIZE'), ('paraphrase', 'PACKING'),
                                            ('reader', 'TEXT_ORDER'), ('reader', 'READER_SEED'),
                                            ('audit', 'AUDIT_ORDER_SEED'), ('audit', 'AUDIT_SEED'),
                                            ('audit', 'AUDIT_SAMPLE')])
def test_the_build_digest_covers_the_kinds_seeds_so_a_changed_seed_changes_every_opaque_id(kind, constant, monkeypatch):
    before = batches.build_digest(kind, ['a', 'b'])
    assert batches.build_digest(kind, ['b', 'a']) == before                      # the inputs' order does not matter
    assert batches.build_digest(kind, ['a']) != before and batches.build_digest('audit' if kind != 'audit' else 'grader',
                                                                              ['a', 'b']) != before
    assert batches.build_digest(kind, ['a', 'b'], 'rejudge') != before           # the re-judging build has ids of its own
    value = getattr(batches, constant)
    monkeypatch.setattr(batches, constant, value + 1 if isinstance(value, int) else (*value, 'X') if isinstance(value, tuple)
                        else value + '-changed')
    assert batches.build_digest(kind, ['a', 'b']) != before


def test_the_build_digest_covers_the_code_and_a_seed_change_alters_the_ids_with_unchanged_inputs(world, monkeypatch):
    answers, questions = synthetic_grader_inputs(world), write_questions(world)
    first = key_of(grader_build(world, answers, questions, 'one'), 'grader')
    again = key_of(grader_build(world, answers, questions, 'two'), 'grader')
    assert list(first['items']) == list(again['items'])                           # unchanged inputs: the same ids
    monkeypatch.setattr(batches, 'GRADER_SEED', 4916)
    changed = key_of(grader_build(world, answers, questions, 'three'), 'grader')
    assert changed['build_sha256'] != first['build_sha256'] and not set(changed['items']) & set(first['items'])
    monkeypatch.setattr(batches, 'GRADER_SEED', 4915)
    unchanged = batches.build_digest('grader', ['a'])
    real = batches.file_sha256
    monkeypatch.setattr(batches, 'file_sha256',
                        lambda path: 'code-changed' if Path(path) == Path(batches.__file__) else real(path))
    assert batches.build_digest('grader', ['a']) != unchanged                 # the module's own sha256 is an input


# ------------------------------------------------------------------ refusals when building
def test_the_commands_print_only_counts_and_digests(world, tmp_path, capsys):
    questions, sentences = write_questions(world), write_sentences(world)
    build(world, 'question')
    build(world, 'screen', 'screen', '--questions', questions)
    build(world, 'paraphrase', 'paraphrase', '--questions', questions)
    reader_build(world, questions=questions, sentences=sentences)
    reader_build(world, 'again', questions=questions, rejudge=True)
    grader_build(world, synthetic_grader_inputs(world), questions)
    build(world, 'audit')
    printed = capsys.readouterr().out
    for private in (CANARY_TEXT, CANARY_Q, CANARY_K, CANARY_A, 'png', 'statement', '/', 'lh1-p0001', 'unsealed-frame', 'bolt'):
        assert private not in printed
    assert all(json.loads(line) for line in printed.splitlines())


def test_building_refuses_an_incomplete_delivery_a_changed_probes_file_and_a_second_write(world, tmp_path, capsys):
    out = build(world, 'question')
    capsys.readouterr()
    assert run(world, 'question', out) == 2 and 'written once' in capsys.readouterr().err
    with world.probes[0].open('a') as stream:
        stream.write('\n')
    assert run(world, 'question', tmp_path/'.runtime'/'o3') == 2
    assert 'not a frozen held-out probes file' in capsys.readouterr().err


def test_a_candidates_file_that_differs_from_its_freeze_is_refused(world, tmp_path, capsys):
    (world.probes[0].parent/'candidates.json').write_text(json.dumps(dict(candidates=[])))
    assert run(world, 'question', tmp_path/'.runtime'/'o') == 2 and 'not a frozen file' in capsys.readouterr().err


def test_the_probes_must_cover_every_held_out_lineage(world, tmp_path, capsys):
    code = cli('batches', 'question', '--probes', world.probes[0], '--evidence-root', world.evidence, '--out', tmp_path/'.runtime'/'o',
               '--host-version', HOST)
    assert code == 2 and 'exactly the held-out lineages' in capsys.readouterr().err


def test_the_judge_files_hold_absolute_paths_so_the_output_must_be_under_the_repositorys_runtime_directory(world, tmp_path, capsys):
    for elsewhere in (tmp_path/'data'/'p1-batches-test', tmp_path.parent/'p1-batches-elsewhere', tmp_path/'.runtimes'/'x'):
        assert run(world, 'question', elsewhere) == 2
        assert "must be under the repository's .runtime/" in capsys.readouterr().err
        assert not elsewhere.exists()
    assert run(world, 'question', tmp_path/'.runtime'/'fine') == 0


def test_the_removed_kinds_are_not_commands(world, tmp_path):
    for kind in ('scoring', 'rejudge', 'guess'):
        with pytest.raises(SystemExit):
            cli('batches', kind, '--out', tmp_path/'.runtime'/'x', '--host-version', HOST)
        with pytest.raises(SystemExit):
            cli('parse', kind, '--batches', tmp_path, '--answers', tmp_path, '--out', tmp_path/'rows')


def test_missing_arguments_are_refused_by_kind(world, tmp_path, capsys):
    out = tmp_path/'.runtime'/'o'
    for kind, message in (('screen', 'need --questions'), ('paraphrase', 'need --questions'), ('grader', 'need --answers, --questions'),
                          ('reader', 'need --delivered, --questions, --probes (or --development)')):
        assert cli('batches', kind, '--out', out, '--host-version', HOST) == 2
        assert message in capsys.readouterr().err


# ------------------------------------------------------------------ the questions freeze
def test_the_questions_freeze_is_the_probes_format_copies_the_screen_beside_it_and_is_written_once(world, capsys):
    path = write_questions(world, freeze=False)
    counts = screen_counts(world, 3)
    capsys.readouterr()
    assert cli(*freeze_args(world, path)) == 0
    printed = json.loads(capsys.readouterr().out)
    document = json.loads((path.parent/'frozen.json').read_text())
    screen = path.parent/'screen.json'
    assert screen.read_bytes() == counts.read_bytes()                                   # copied beside the questions
    assert document == dict(schema='p1-held-out-frozen/1', protocol='p1-study/3', frozen='2026-11-11',
                            files={'questions.jsonl': analysis.file_sha256(path), 'screen.json': analysis.file_sha256(screen)})
    assert printed == dict(questions=20, sha256=analysis.file_sha256(path), screen_sha256=analysis.file_sha256(screen),
                           frozen_sha256=analysis.file_sha256(path.parent/'frozen.json'))
    rows, record = analysis.frozen_file(path, 'questions')               # the same verifier the probes use
    assert len(rows) == 20 and record['sha256'] == analysis.file_sha256(path)
    assert analysis.frozen_screen(path, screen)['sha256'] == analysis.file_sha256(screen)
    assert cli(*freeze_args(world, path)) == 2                                          # written once
    assert 'written once' in capsys.readouterr().err
    bad = write_jsonl(world.root.joinpath(*QUESTIONS_DIR)/'bad'/'questions.jsonl', [dict(question_of('a'), extra=1)])
    assert cli(*freeze_args(world, bad)) == 2
    assert not (bad.parent/'frozen.json').exists() and not (bad.parent/'screen.json').exists()


def test_the_questions_freeze_refuses_a_file_outside_the_questions_directory_and_questions_that_miss_the_units(world, capsys):
    outside = write_jsonl(world.root/'elsewhere'/'questions.jsonl', [question_of(u['probe']) for u in world.units])
    assert cli(*freeze_args(world, outside)) == 2
    assert 'under data/evaluation/p1/questions/ only' in capsys.readouterr().err
    sibling = write_jsonl(world.root/'data'/'evaluation'/'p1'/'questions-x'/'questions.jsonl', [question_of(u['probe']) for u in world.units])
    assert cli(*freeze_args(world, sibling)) == 2                                         # a name that only starts like the directory
    for name, rows, message in (('short', [question_of(u['probe']) for u in world.units][1:], '1 units have none'),
                                ('extra', [*(question_of(u['probe']) for u in world.units), question_of('zz-p0001')],
                                 '1 questions belong to no unit')):
        path = write_jsonl(world.root.joinpath(*QUESTIONS_DIR)/name/'questions.jsonl', rows)
        assert cli(*freeze_args(world, path)) == 2 and message in capsys.readouterr().err
        assert not (path.parent/'frozen.json').exists() and not (path.parent/'screen.json').exists()
    path = write_questions(world, 'whole', freeze=False)
    probes = [a for p in world.probes[:1] for a in ('--probes', p)]                       # probes that leave a lineage out
    assert cli('questions-freeze', '--questions', path, '--frozen', 'x', *probes, '--screen', screen_counts(world)) == 2
    assert 'exactly the held-out lineages' in capsys.readouterr().err
    assert cli('questions-freeze', '--questions', path, '--frozen', 'x', '--screen', screen_counts(world)) == 2      # no probes
    assert cli('questions-freeze', '--questions', path, '--frozen', 'x', *[a for p in world.probes for a in ('--probes', p)]) == 2
    assert 'needs --probes' in capsys.readouterr().err
    assert not (path.parent/'frozen.json').exists()


@pytest.mark.parametrize('content', ['{}', '{"flagged_twice": null}', '{"flagged_twice": -1}', '{"flagged_twice": true}',
                                     '{"flagged_twice": 1.5}', '[1]', 'not json'])
def test_the_questions_freeze_needs_the_screens_integer_flagged_twice(world, capsys, content):
    path = write_questions(world, freeze=False)
    counts = world.root/'bad-counts.json'
    counts.write_text(content)
    probes = [a for p in world.probes for a in ('--probes', p)]
    assert cli('questions-freeze', '--questions', path, '--frozen', 'x', *probes, '--screen', counts) == 2
    assert 'bad-counts.json' in capsys.readouterr().err
    assert not (path.parent/'frozen.json').exists() and not (path.parent/'screen.json').exists()


def test_a_grader_build_over_held_out_reader_answers_needs_the_frozen_questions(world, tmp_path, capsys):
    answers = reader_answers(world)
    frozen = write_questions(world)
    assert run(world, 'grader', tmp_path/'.runtime'/'ok', '--answers', answers, '--questions', frozen) == 0
    unfrozen = write_questions(world, 'unfrozen', freeze=False)
    edited = write_questions(world, 'edited')
    edited.write_text(edited.read_text().replace('saw', 'nail'))                  # one edit after the freeze
    for name, questions in (('unfrozen', unfrozen), ('edited', edited)):
        capsys.readouterr()
        assert run(world, 'grader', tmp_path/'.runtime'/name, '--answers', answers, '--questions', questions) == 2
        error = capsys.readouterr().err
        assert 'not a frozen questions file' in error and 'nail' not in error and not (tmp_path/'.runtime'/name).exists()
    # before the freeze the screen's and the paraphrase check's graders take the questions as they are
    for source, arm in (('screen', 'N'), ('paraphrase', 'S')):
        rows = [answer_row(u['probe'], arm, 1, f'{CANARY_A} {n}', source=source) for n, u in enumerate(world.units)]
        assert run(world, 'grader', tmp_path/'.runtime'/f'pre-{source}', '--answers', write_jsonl(tmp_path/f'{source}.jsonl', rows),
                   '--questions', unfrozen) == 0


def test_a_development_grader_build_names_the_development_units_and_needs_no_freeze(tmp_path, capsys):
    dev = dev_world(tmp_path)
    questions = dev_questions(dev)                                  # never frozen
    rows = [answer_row(r['probe'], arm, repeat, f'{CANARY_A} {arm}', rejudge=False) for r in dev.rows for arm, repeat in DEV_KEYS]
    answers = write_jsonl(tmp_path/'dev-answers.jsonl', rows)
    common = ['--answers', answers, '--questions', questions, '--host-version', HOST]
    assert cli('batches', 'grader', *common, '--out', tmp_path/'.runtime'/'plain') == 2          # held-out unless it says otherwise
    assert 'not a frozen questions file' in capsys.readouterr().err
    assert cli('batches', 'grader', *common, '--development', dev.units_file, '--out', tmp_path/'.runtime'/'dev') == 0
    assert key_of(tmp_path/'.runtime'/'dev', 'grader')['questions_sha256'] == analysis.file_sha256(questions)
    outside = write_jsonl(tmp_path/'outside.jsonl', rows + [answer_row('lh1-p0001', 'A', 1, 'x')])
    assert cli('batches', 'grader', '--answers', outside, '--questions', questions, '--host-version', HOST,
               '--development', dev.units_file, '--out', tmp_path/'.runtime'/'out') == 2
    assert 'outside the development units' in capsys.readouterr().err
    held = write_jsonl(tmp_path/'held-units.jsonl', [dict(dev.rows[0], lineage='lh1')])
    assert cli('batches', 'grader', *common, '--development', held, '--out', tmp_path/'.runtime'/'held') == 2
    assert 'held out' in capsys.readouterr().err
    for kind in ('screen', 'paraphrase'):
        assert cli('batches', kind, '--questions', questions, '--development', dev.units_file, '--out', tmp_path/'.runtime'/kind,
                   '--host-version', HOST) == 2
        assert 'is for question, reader and grader builds' in capsys.readouterr().err


def test_every_key_made_from_a_questions_file_records_its_digest_and_parse_refuses_a_different_file(world, tmp_path):
    questions, sentences = write_questions(world), write_sentences(world)
    digest = analysis.file_sha256(questions)
    other = write_jsonl(world.root/'other-questions.jsonl', [dict(question_of(u['probe']), key='different') for u in world.units])
    assert analysis.file_sha256(other) != digest
    made = {'screen': build(world, 'screen', 'screen', '--questions', questions),
            'paraphrase': build(world, 'paraphrase', 'paraphrase', '--questions', questions),
            'reader': reader_build(world, questions=questions, sentences=sentences),
            'grader': grader_build(world, reader_answers(world), questions)}
    shapes = dict(screen=lambda i, m: dict(id=i, answer='x'), reader=lambda i, m: dict(id=i, answer='x'),
                  paraphrase=lambda i, m: dict(id=i, sentence='x'), grader=grader_answer)
    for kind, out in made.items():
        assert key_of(out, kind)['questions_sha256'] == digest
        answers = answers_for(out, kind, shapes[kind])
        assert batches.parse(kind, out, answers, questions=questions)                          # the file the batches used
        with pytest.raises(batches.BatchError, match=f'not the questions file the {kind} batches were built from'):
            batches.parse(kind, out, answers, questions=other)
        with pytest.raises(batches.BatchError, match='the other kinds take --questions'):
            batches.parse(kind, out, answers, base=questions)
    rows = tmp_path/'rows.jsonl'
    assert cli('parse', 'reader', '--batches', made['reader'], '--answers', answers_for(made['reader'], 'reader', shapes['reader'], 'cli'),
               '--questions', other, '--out', rows) == 2
    assert not rows.exists()
    # the question rewrite: `--base` is the file it was built from
    flagged = tmp_path/'flagged.txt'
    flagged.write_text(f'{world.units[0]["probe"]}\n')
    rewrite = build(world, 'question', 'rewrite', '--rewrite', flagged, '--questions', questions)
    assert key_of(rewrite, 'question')['questions_sha256'] == digest
    given = answers_for(rewrite, 'question', lambda i, m: dict(id=i, question='A new question?', key='k'))
    assert len(batches.parse('question', rewrite, given, questions)) == 20
    with pytest.raises(batches.BatchError, match='not the questions file the question batches were built from'):
        batches.parse('question', rewrite, given, other)
    with pytest.raises(batches.BatchError, match='the question rewrite takes --base'):
        batches.parse('question', rewrite, given, questions=questions)
    plain = build(world, 'question')                                                           # no questions file used
    assert 'questions_sha256' not in key_of(plain, 'question')
    with pytest.raises(batches.BatchError, match='built without a questions file'):
        batches.parse('question', plain, answers_for(plain, 'question', lambda i, m: dict(id=i, question='q', key='k')), questions)


# ------------------------------------------------------------------ parsing
def grader_answer(opaque, meta):
    return dict(id=opaque, correct=number(opaque) % 3 != 0, why=CANARY_WORDS)


def audit_answer(opaque, meta):
    n = number(opaque)      # null, "null" or a source id, as the brief's `<source id or null>` may be written
    frame = 'lh1a1-7' if n % 5 == 0 else (None if n % 2 else 'null')
    return dict(id=opaque, false=n % 5 == 0, frame=frame, why=CANARY_WORDS)


def test_the_whole_chain_round_trips_into_rows_score_accepts(world, tmp_path, capsys):
    capsys.readouterr()
    # 1. the question writer, then the screen's two checks
    out = build(world, 'question')
    questions_file = parsed(out, 'question', lambda i, m: dict(id=i, question=f'Which entries are on list {number(i)}?', key='bolt, saw'), tmp_path)
    rows = read_jsonl(questions_file)
    assert len(rows) == 20 and all(r['schema'] == 'p1-question/1' and set(r) == {'schema', 'probe', 'question', 'key'} for r in rows)
    assert [r['probe'] for r in rows] == sorted(u['probe'] for u in world.units)
    screening = build(world, 'screen', 'screen', '--questions', questions_file)           # before the freeze: the file as parsed
    no_text = parsed(screening, 'screen', lambda i, m: dict(id=i, answer='Not stated.'), tmp_path, '--questions', questions_file)
    assert all(r['source'] == 'screen' and r['arm'] == 'N' for r in read_jsonl(no_text))
    graded_screen = grader_build(world, no_text, questions_file, 'grader-screen')
    assert batch_files(graded_screen, 'grader') == []                       # "not stated" never reaches a grader
    (tmp_path/'empty').mkdir()
    checks = tmp_path/'screen-checks.jsonl'
    write_jsonl(checks, batches.parse('grader', graded_screen, tmp_path/'empty'))
    assert all(r['schema'] == 'p1-check/1' and r['purpose'] == 'screen' and r['correct'] is False for r in read_jsonl(checks))
    capsys.readouterr()
    assert cli('screen', '--questions', questions_file, '--graded', checks, '--out', tmp_path/'.runtime'/'screen-1') == 0
    counts_path = tmp_path/'.runtime'/'screen-1'/'counts.json'
    assert json.loads(capsys.readouterr().out)['flagged_twice'] == 0
    # 2. the paraphrase and its check
    paraphrase = build(world, 'paraphrase', 'paraphrase', '--questions', questions_file)
    sentences_in = parsed(paraphrase, 'paraphrase', lambda i, m: dict(id=i, sentence=f'List {number(i)} holds bolt and saw.'), tmp_path)
    graded_sentences = grader_build(world, sentences_in, questions_file, 'grader-sentences')
    sentence_checks = parsed(graded_sentences, 'grader', lambda i, m: dict(id=i, correct=number(i) % 5 != 0, why=CANARY_WORDS), tmp_path)
    assert cli('sentences', '--paraphrases', sentences_in, '--checks', sentence_checks, '--out', tmp_path/'.runtime'/'sentences') == 0
    sentences = tmp_path/'.runtime'/'sentences'/'sentences.jsonl'
    assert len(read_jsonl(sentences)) == 20
    sentence_counts = json.loads((tmp_path/'.runtime'/'sentences'/'counts.json').read_text())
    assert sentence_counts == dict(units=20, stages=1, rewritten=0, failed=sum(not r['correct'] for r in read_jsonl(sentence_checks)))
    # the freeze: the questions beside the screen's counts, under the questions directory
    frozen = world.root.joinpath(*QUESTIONS_DIR)/'chain'/'questions.jsonl'
    frozen.parent.mkdir(parents=True)
    frozen.write_text(questions_file.read_text())
    probes = [a for p in world.probes for a in ('--probes', p)]
    assert cli('questions-freeze', '--questions', frozen, '--frozen', '2026-11-11', *probes, '--screen', counts_path) == 0
    # 3. the readers, the graders, then the re-judging
    readers = reader_build(world, questions=frozen, sentences=sentences)
    answers = parsed(readers, 'reader', lambda i, m: dict(id=i, answer='Not stated' if number(i) % 4 == 0 else 'It says bolt and saw.'), tmp_path,
                     '--questions', frozen)
    assert len(read_jsonl(answers)) == 120
    graders = grader_build(world, answers, frozen)
    first = parsed(graders, 'grader', grader_answer, tmp_path)
    labels = read_jsonl(first)
    assert len(labels) == 120 and all(r['type'] == 'label' and r['kind'] == 'reobservation' and 'rejudge' not in r for r in labels)
    assert {r['arm'] for r in labels} == {'A', 'B', 'R', 'PW', 'PP'} and sum(not r['answered'] for r in labels) == 30
    assert all(r['stated'] is False for r in labels if not r['answered'])          # mechanical: incorrect
    assert CANARY_WORDS not in json.dumps(labels)
    again_readers = reader_build(world, 'reader-rejudge', questions=frozen, rejudge=True)
    again_answers = parsed(again_readers, 'reader', lambda i, m: dict(id=i, answer='It says bolt and saw.'), tmp_path)
    again = read_jsonl(parsed(grader_build(world, again_answers, frozen, 'grader-rejudge'), 'grader',
                              lambda i, m: dict(id=i, correct=number(i) % 2 == 0, why='x'), tmp_path))
    assert len(again) == 12 and all(r['rejudge'] is True for r in again)
    # 4. the audit and the cost rows, then the whole study scores
    audits = read_jsonl(parsed(build(world, 'audit'), 'audit', audit_answer, tmp_path))
    costs = [dict(type='cost', schema=analysis.SCORE_SCHEMA, repeat=r, lineage='lh1', curator_dollars=1.0, actor_dollars=2.0,
                  stopped_by_cap=False) for r in (1, 2)]
    questions = read_jsonl(frozen)
    result = analysis.score(world.rows, {name: 10.0 for name in LINEAGES}, labels + again + audits + costs, questions,
                            json.loads((frozen.parent/'screen.json').read_text()), sentence_counts)
    assert result['probes']['units'] == 20 and result['judge_agreement']['n'] == 12
    assert result['reference']['n'] == 20 and result['positive_control']['PW']['units'] == 20
    assert result['positive_control']['paraphrases_failed_twice'] == sentence_counts['failed'] == 4
    assert result['questions_flagged_twice'] == 0 and {'A1', 'B1', 'B2'} <= set(result['figures'])
    assert 'arm_guessing' not in result and all('secondary' not in f for f in result['figures'].values())


def synthetic_graded_labels(world, tmp_path):
    answers, questions = synthetic_grader_inputs(world, every=1000), write_questions(world)
    return grader_build(world, answers, questions)


def broken_grader(world, mutate, tmp_path):
    out = synthetic_graded_labels(world, tmp_path)
    answers = answers_for(out, 'grader', grader_answer)
    mutate(answers, key_of(out, 'grader'))
    with pytest.raises(batches.BatchError) as raised:
        batches.parse('grader', out, answers)
    assert 'SECRET' not in str(raised.value) and CANARY_WORDS not in str(raised.value)
    return str(raised.value)


def lines_of(answers: Path, name: str = 'grader-001.jsonl') -> list[str]:
    return (answers/name).read_text().splitlines()


def rewrite(answers: Path, lines: list[str], name: str = 'grader-001.jsonl') -> None:
    (answers/name).write_text('\n'.join(lines) + '\n')


@pytest.mark.parametrize('mutate, message', [
    (lambda a, k: (a/'grader-002.jsonl').unlink(), 'missing batch outputs: grader-002.jsonl'),
    (lambda a, k: (a/'notes.txt').write_text('x'), 'belong to no batch: notes.txt'),
    (lambda a, k: (a/'grader-001.jsonl').with_name('grader-001.json').write_text(''), 'belong to no batch: grader-001.json'),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), id='SECRET-ID')), *lines_of(a)[1:]]),
     r"grader-001.jsonl:1: id is not in the batch's key"),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), id=k['batches'][1]['ids'][0])), *lines_of(a)[1:]]),
     r"grader-001.jsonl:1: id is not in the batch's key"),
    (lambda a, k: rewrite(a, [lines_of(a)[0], lines_of(a)[0], *lines_of(a)[2:]]), r'grader-001.jsonl:2: duplicated id g'),
    (lambda a, k: rewrite(a, lines_of(a)[:-1]), r'grader-001.jsonl: 1 ids missing \(first g'),
    (lambda a, k: rewrite(a, [lines_of(a)[1], lines_of(a)[0], *lines_of(a)[2:]]), 'not in batch order'),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), extra=1)), *lines_of(a)[1:]]),
     r"grader-001.jsonl:1: not exactly the brief's JSON shape"),
    (lambda a, k: rewrite(a, [json.dumps({x: y for x, y in json.loads(lines_of(a)[0]).items() if x != 'why'}), *lines_of(a)[1:]]),
     r"grader-001.jsonl:1: not exactly the brief's JSON shape"),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), correct='true')), *lines_of(a)[1:]]),
     r'grader-001.jsonl:1: field correct \(id g'),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), why=7)), *lines_of(a)[1:]]),
     r'grader-001.jsonl:1: field why \(id g'),
    (lambda a, k: rewrite(a, ['SECRET words, not json', *lines_of(a)[1:]]), r'grader-001.jsonl:1: not JSON'),
    (lambda a, k: rewrite(a, [lines_of(a)[0], '', *lines_of(a)[1:]]), r'grader-001.jsonl:2: not JSON'),
    (lambda a, k: rewrite(a, ['[1, 2]', *lines_of(a)[1:]]), r"grader-001.jsonl:1: not exactly the brief's JSON shape"),
    (lambda a, k: rewrite(a, [json.dumps(dict(json.loads(lines_of(a)[0]), id=7)), *lines_of(a)[1:]]),
     r"grader-001.jsonl:1: id is not in the batch's key"),
])
def test_grader_output_that_is_not_exactly_the_briefs_shape_is_refused_without_judge_text(world, tmp_path, mutate, message):
    assert re.search(message, broken_grader(world, mutate, tmp_path))


def test_an_empty_output_file_for_a_batch_is_refused(world, tmp_path):
    out = synthetic_graded_labels(world, tmp_path)
    answers = answers_for(out, 'grader', grader_answer)
    (answers/'grader-001.jsonl').write_text('')
    with pytest.raises(batches.BatchError, match=r'grader-001.jsonl: \d+ ids missing'):
        batches.parse('grader', out, answers)


def test_question_reader_and_paraphrase_output_must_be_exactly_the_briefs_shape(world, tmp_path):
    questions = write_questions(world)
    cases = (('question', build(world, 'question'), lambda i: dict(id=i, question='What?', key=''), 'question-001.jsonl',
              [('question', ''), ('question', '  '), ('question', 3), ('key', None), ('key', 7)]),
             ('reader', reader_build(world, questions=questions), lambda i: dict(id=i, answer='x'), 'reader-001.jsonl',
              [('answer', ''), ('answer', 5), ('answer', ['x'])]),
             ('paraphrase', build(world, 'paraphrase', 'paraphrase', '--questions', questions),
              lambda i: dict(id=i, sentence='x'), 'paraphrase-001.jsonl', [('sentence', ' '), ('sentence', None)]))
    for kind, out, make, name, bads in cases:
        answers = answers_for(out, kind, lambda i, m: make(i))
        assert len(batches.parse(kind, out, answers)) >= 1                       # an empty key is a valid answer, flagged by the screen
        lines = lines_of(answers, name)
        for field, bad in bads:
            rewrite(answers, [json.dumps(dict(json.loads(lines[0]), **{field: bad})), *lines[1:]], name)
            with pytest.raises(batches.BatchError, match=rf'{name}:1: field {field} \(id'):
                batches.parse(kind, out, answers)
        rewrite(answers, lines[::-1] if len(lines) > 1 else lines, name)
        if len(lines) > 1:
            with pytest.raises(batches.BatchError, match='not in batch order'):
                batches.parse(kind, out, answers)


def test_a_rewrite_replaces_the_flagged_rows_of_the_questions_it_is_based_on(world, tmp_path):
    base = write_questions(world, freeze=False)
    flagged = tmp_path/'flagged.txt'
    chosen = [world.units[1]['probe'], world.units[4]['probe']]
    flagged.write_text('\n'.join(chosen) + '\n')
    out = build(world, 'question', 'rewrite', '--rewrite', flagged, '--questions', base)
    rows = read_jsonl(parsed(out, 'question', lambda i, m: dict(id=i, question='A new question?', key='a new key'), tmp_path, '--base', base))
    old = {r['probe']: r for r in read_jsonl(base)}
    assert [r['probe'] for r in rows] == [u['probe'] for u in world.units]
    assert {r['probe'] for r in rows if r['question'] == 'A new question?'} == set(chosen)
    assert all(r == old[r['probe']] for r in rows if r['probe'] not in chosen)
    other = write_jsonl(tmp_path/'other.jsonl', [question_of('zz-p0001')])
    answers = answers_for(out, 'question', lambda i, m: dict(id=i, question='q', key='k'), 'again')
    with pytest.raises(batches.BatchError, match='not the questions file the question batches were built from'):
        batches.parse('question', out, answers, other)          # a base the rewrite was not built from
    with pytest.raises(batches.BatchError, match='no question for'):
        batches._replaced(analysis.question_rows(read_jsonl(write_jsonl(tmp_path/'tiny.jsonl', [question_of('a')]))), other)


def test_parsed_answers_carry_their_text_arm_and_repeat_for_the_grader(world, tmp_path):
    questions = write_questions(world)
    readers = reader_build(world, questions=questions)
    rows = read_jsonl(parsed(readers, 'reader', lambda i, m: dict(id=i, answer=f'{m["arm"]}{m["repeat"]}'), tmp_path))
    assert all(r['source'] == 'reader' and r['rejudge'] is False and r['answer'] == f'{r["arm"]}{r["repeat"]}' for r in rows)
    assert {(r['arm'], r['repeat']) for r in rows} == set(TEXTS)
    paraphrase = build(world, 'paraphrase', 'paraphrase', '--questions', questions)
    rows = read_jsonl(parsed(paraphrase, 'paraphrase', lambda i, m: dict(id=i, sentence='x'), tmp_path))
    assert {(r['source'], r['arm'], r['repeat']) for r in rows} == {('paraphrase', 'S', 1)}


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


def test_only_the_audit_may_answer_out_of_order_every_id_exactly_once(world, tmp_path):
    audit = build(world, 'audit')
    answers = answers_for(audit, 'audit', audit_answer)
    expected = batches.parse('audit', audit, answers)
    lines = lines_of(answers, 'audit-001.jsonl')
    rewrite(answers, lines[::-1], 'audit-001.jsonl')
    assert batches.parse('audit', audit, answers) == expected          # reversed output: the same rows, in the key's order
    rewrite(answers, [lines[0], *lines[:-1]], 'audit-001.jsonl')        # an id twice (and one missing) is still refused
    with pytest.raises(batches.BatchError, match='duplicated id'):
        batches.parse('audit', audit, answers)
    rewrite(answers, lines[:-1], 'audit-001.jsonl')
    with pytest.raises(batches.BatchError, match='ids missing'):
        batches.parse('audit', audit, answers)
    grader = synthetic_graded_labels(world, tmp_path)
    given = answers_for(grader, 'grader', grader_answer)
    rewrite(given, lines_of(given)[::-1])
    with pytest.raises(batches.BatchError, match='not in batch order'):
        batches.parse('grader', grader, given)


def test_answers_from_another_build_are_refused(world, tmp_path):
    questions = write_questions(world)
    one = grader_build(world, reader_answers(world), questions, 'one')
    changed = [dict(r, answer=r['answer'] + ' changed') if r['arm'] == 'A' else r for r in read_jsonl(world.root/'answers.jsonl')]
    other = write_jsonl(world.root/'other-answers.jsonl', changed)
    two = grader_build(world, other, questions, 'two')
    assert key_of(one, 'grader')['build_sha256'] != key_of(two, 'grader')['build_sha256']
    assert not set(key_of(one, 'grader')['items']) & set(key_of(two, 'grader')['items'])    # no id is shared
    mine = answers_for(one, 'grader', grader_answer)
    theirs = answers_for(two, 'grader', grader_answer)
    assert len(batches.parse('grader', one, mine)) == 120
    with pytest.raises(batches.BatchError, match="id is not in the batch's key"):
        batches.parse('grader', one, theirs)
    with pytest.raises(batches.BatchError, match="id is not in the batch's key"):
        batches.parse('grader', two, mine)


def test_a_batch_file_that_differs_from_the_key_is_refused_before_any_answer_is_read(world, tmp_path):
    out = synthetic_graded_labels(world, tmp_path)
    answers = answers_for(out, 'grader', grader_answer)
    path = out/'batches'/'grader-002.json'
    original = path.read_text()
    path.write_text(original.replace('answer', 'altered'))
    with pytest.raises(batches.BatchError, match='differ from the build the key was made for: grader-002'):
        batches.parse('grader', out, answers)
    path.write_text(original)
    (out/'batches'/'grader-099.json').write_text('{}')
    with pytest.raises(batches.BatchError, match='does not hold exactly the grader batch files of the key: grader-099'):
        batches.parse('grader', out, answers)
    (out/'batches'/'grader-099.json').unlink()
    path.unlink()
    with pytest.raises(batches.BatchError, match='does not hold exactly'):
        batches.parse('grader', out, answers)
    path.write_text(original)
    key = out/'keys'/'grader.json'
    document = json.loads(key.read_text())
    del document['batch_files']
    key.write_text(json.dumps(document))
    with pytest.raises(batches.BatchError, match='records no batch file digests'):
        batches.parse('grader', out, answers)


def test_dotfiles_in_the_answers_directory_are_ignored(world, tmp_path):
    out = synthetic_graded_labels(world, tmp_path)
    answers = answers_for(out, 'grader', grader_answer)
    (answers/'.DS_Store').write_bytes(b'\x00')
    assert len(batches.parse('grader', out, answers)) == 120
    (answers/'DS_Store').write_bytes(b'\x00')
    with pytest.raises(batches.BatchError, match='belong to no batch: DS_Store'):
        batches.parse('grader', out, answers)


def test_the_rows_file_is_written_once_and_a_missing_key_is_refused(world, tmp_path, capsys):
    out = synthetic_graded_labels(world, tmp_path)
    answers = answers_for(out, 'grader', grader_answer)
    rows = tmp_path/'rows.jsonl'
    args = ['parse', 'grader', '--batches', out, '--answers', answers, '--out', rows]
    assert cli(*args) == 0 and cli(*args) == 2
    assert '--out exists' in capsys.readouterr().err
    assert cli('parse', 'reader', '--batches', out, '--answers', answers, '--out', tmp_path/'r2') == 2
    assert 'no readable key file for reader' in capsys.readouterr().err


def test_a_grader_over_the_screens_answers_makes_check_rows_not_score_rows(world, tmp_path):
    questions = write_questions(world, freeze=False)
    rows = [answer_row(u['probe'], 'N', 1, f'{CANARY_A} {n}', source='screen') for n, u in enumerate(world.units)]
    out = grader_build(world, write_jsonl(tmp_path/'noanswers.jsonl', rows), questions, 'screen-grader')
    checks = read_jsonl(parsed(out, 'grader', lambda i, m: dict(id=i, correct=number(i) % 2 == 0, why='x'), tmp_path))
    assert len(checks) == 20 and all(r['schema'] == 'p1-check/1' and r['purpose'] == 'screen' and 'type' not in r for r in checks)
    with pytest.raises(analysis.ScoreError):
        analysis.score(world.rows, {n: 1.0 for n in LINEAGES}, checks, [], dict(flagged_twice=0), dict(failed=0))      # never a score input
