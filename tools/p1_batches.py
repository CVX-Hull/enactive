"""The P1 offline study's answer-key chain: batches, parsing and the question screen (pre-registration p1-study/3,
docs/design/p1-study-3.md, "The measurement chain"; #529).

  python -m tools.p1_analysis batches question   {--probes <p1-probes/1>... | --development UNITS} --out DIR --host-version V
                                                 [--rewrite FLAGGED --questions Q]
  python -m tools.p1_analysis batches screen     --questions Q [--only IDS] --out DIR --host-version V
  python -m tools.p1_analysis batches paraphrase --questions Q [--only IDS] --out DIR --host-version V
  python -m tools.p1_analysis batches reader     {--probes ... | --development UNITS} --delivered <p1-delivered/2>...
                                                 --questions Q [--sentences S | --rejudge] --out DIR --host-version V
  python -m tools.p1_analysis batches grader     --answers <p1-answer/1>... --questions Q [--development UNITS] --out DIR --host-version V
  python -m tools.p1_analysis batches audit      --probes <p1-probes/1>... --delivered <delivered.jsonl>... --out DIR --host-version V
  python -m tools.p1_analysis parse {question,screen,paraphrase,reader,grader,audit} --batches DIR --answers DIR --out FILE
                                                 [--base Q]          # question: the rewrite replaces the flagged rows
                                                 [--questions Q]     # the others: refused if Q is not the file the batches used
  python -m tools.p1_analysis screen --questions Q [--graded <p1-check/1>] [--previous FLAGGED] --out DIR
  python -m tools.p1_analysis sentences --paraphrases P --checks C [--paraphrases P2 --checks C2] --out DIR
  python -m tools.p1_analysis questions-freeze --questions Q --frozen DATE --probes <p1-probes/1>... --screen COUNTS

`batches` writes, under `--out`, the judge-facing files `batches/<kind>-NNN.json` (the frozen brief, word for word, and
items that carry an opaque `id` and what the brief names) and, apart from them, `keys/<kind>.json`, which maps each opaque
id to what only the analysis may know (arm, repeat, probe) and is never given to a judge. One directory holds one build of
one kind, so every step (a rewrite, the screen's answers, the paraphrase check, the readers, the re-judging) has its own.
The judge files hold absolute frame paths, so `--out` must lie under the repository's `.runtime/`. The same inputs give
byte-identical files. An opaque id is `<letter><8 hex of the build digest>-<counter>`, the build digest being a sha256 over
the kind, this module's own sha256, the kind's seeds and the sorted digests of the inputs, and the key holds each batch
file's sha256, so output from another build, or for an altered batch file, is refused. A key made from a questions file
records that file's sha256 (`questions_sha256`), and `parse` refuses a questions file (`--base`, `--questions`) that differs.

A questions file is verified against its `frozen.json` wherever one is required: held-out `reader` builds, `grader` builds
over a reader's answers (unless `--development` names the development units) and `score`. The pre-freeze steps (the
rewrite, `screen`, `paraphrase`, the paraphrase check's graders) and development runs need none. `questions-freeze` writes
only under data/evaluation/p1/questions/, for questions that cover exactly the frozen held-out probes' units, and copies the
screen's counts beside them as `screen.json`, listed in `frozen.json`, which `score --screen` must then match.

`parse` reads one judge output file per batch (`<batch>.jsonl` in `--answers`) and writes the rows the next step takes:
`p1-question/1` (`questions.jsonl`), `p1-answer/1` (a reader's, the no-text answerer's or a paraphraser's answers),
`p1-score/1` label rows (a grader over readers' answers: `stated` is "correct", `answered` false for the mechanical
"not stated") or `p1-check/1` rows (a grader over the screen's answers or a paraphrase check), and the audit's rows. It
refuses anything that is not exactly the brief's JSON shape.

Nothing here prints a question, a key, an answer, a delivered text, a frame path, a source id or a judge's words: only
counts and digests. Error messages name files, line numbers and opaque ids.
"""
from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
from typing import NamedTuple

from harness.jsonio import file_sha256
from tools import p1_analysis as analysis
from tools.probe_validation import HELD_OUT_DIR, HELD_OUT_LH4_DIR, HELD_OUT_STUDIES

ROOT = analysis.ROOT
STUDY_DOC = ROOT/'docs'/'design'/'p1-study-3.md'
BATCH_SCHEMA = 'p1-judge-batch/1'
KEY_SCHEMA = 'p1-judge-key/1'
DELIVERED_SCHEMA = 'p1-delivered/2'
ANSWER_SCHEMA = 'p1-answer/1'        # a reader's, the no-text answerer's or a paraphraser's answer, before grading
CHECK_SCHEMA = 'p1-check/1'          # a grader's verdict on the screen's answer or a paraphrase: not a `score` row
SENTENCE_SCHEMA = 'p1-sentence/1'    # the paraphrase used for the positive control, with its attempts
BATCH_SIZE = 10          # items per question, screen, paraphrase, grader and audit batch (The measurement chain)
GRADER_SEED = 4915       # the grader batches' mixed order (Grader)
AUDIT_SEED = 4913        # the audit's draw of (working-set item, boundary) pairs
AUDIT_SAMPLE = 40        # per arm and repeat, at most
QUESTIONS_DIR = ('data', 'evaluation', 'p1', 'questions')   # under the repository root: where a questions freeze may be written
READER_SEED = 4916       # Owner decision, 10 November 2026: Random(4916) numbers the reader items and names their files, so neither follows the arm

# What the pre-registration leaves open, as the owner decided on 10 November 2026.
AUDIT_ORDER_SEED = AUDIT_SEED       # Owner decision, 10 November 2026: Random(4913) mixes the three arms' audit pairs into batches
DROP_UNRESOLVED_CITES = True        # Owner decision, 10 November 2026: a cited frame that is not sealed is dropped and counted per arm
PACKING = 'first-fit'               # Owner decision, 10 November 2026: each answer goes to the earliest batch with room and none for its probe

# The mechanical screen (The measurement chain, "The screen")
MAX_ENTRIES = 5          # a key with more entries is flagged
MIN_LETTERS = 4          # a run of letters this long, or any run of digits, counts as a token

# The grader's order of texts within a probe: the arms, the controls, then the screen's and the paraphrase's answers.
TEXT_ORDER = ('A', 'B', 'R', 'PW', 'PP', 'N', 'S')
SOURCES = {'reader': ('A', 'B', 'R', 'PW', 'PP'), 'screen': ('N',), 'paraphrase': ('S',)}

# kind -> file prefix, opaque-id letter and the frozen brief it carries
KINDS = {'question': dict(prefix='question', letter='q', brief='Question'),
         'screen': dict(prefix='screen', letter='n', brief='Guess'),
         'paraphrase': dict(prefix='paraphrase', letter='p', brief='Paraphrase'),
         'reader': dict(prefix='reader', letter='r', brief='Reader'),
         'grader': dict(prefix='grader', letter='g', brief='Grader'),
         'audit': dict(prefix='audit', letter='a', brief='Audit')}
_SOURCE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*')


class BatchError(ValueError):
    """A batch cannot be built, or a judge's output is not what the brief asked for."""


def _evidence_default() -> Path:
    return Path(os.environ.get('ENACTIVE_EVIDENCE_ROOT', ROOT/'.runtime'/'evidence'))


def _digest(path: Path) -> str:
    try:
        return file_sha256(Path(path))
    except OSError:
        raise BatchError(f'{Path(path).name}: unreadable file') from None


def _jsonl(path: Path) -> list:
    try:
        return analysis._lines(Path(path))
    except (OSError, ValueError):
        raise BatchError(f'{Path(path).name}: unreadable JSON Lines file') from None


# ------------------------------------------------------------------ the frozen briefs
def frozen_brief(label: str, doc: Path = STUDY_DOC) -> str:
    """The pre-registration's frozen brief `label`: the quote lines from `> **<label>.**` to the next
    blank line, joined by single spaces, without the leading label (the Grader brief begins "You check")."""
    lines = Path(doc).read_text(encoding='utf-8').splitlines()
    opening = f'> **{label}.**'
    start = next((i for i, line in enumerate(lines) if line.startswith(opening)), None)
    if start is None:
        raise BatchError(f'the {label} brief was not found in {Path(doc).name}')
    quote = []
    for line in lines[start:]:
        if not line.startswith('>') or not line[1:].strip():
            break
        quote.append(line[1:].strip())
    return ' '.join(quote).removeprefix(f'**{label}.** ')


# ------------------------------------------------------------------ inputs
def read_delivered(paths: Sequence[Path]) -> dict[tuple, dict]:
    """(lineage, boundary, arm, repeat) -> row of every `p1-delivered/2` file given."""
    out: dict[tuple, dict] = {}
    for path in map(Path, paths):
        try:
            rows = analysis._lines(path)
        except (OSError, ValueError):
            raise BatchError(f'{path.name}: unreadable delivered file') from None
        for number, row in enumerate(rows, 1):
            if (not isinstance(row, dict) or row.get('schema') != DELIVERED_SCHEMA
                    or not all(isinstance(row.get(k), str) for k in ('lineage', 'boundary', 'text', 'arm'))
                    or row['arm'] not in ('R', 'A', 'B') or isinstance(row.get('repeat'), bool)
                    or not isinstance(row.get('repeat'), int) or not isinstance(row.get('complete'), bool)
                    or not isinstance(row.get('items'), int)):
                raise BatchError(f'{path.name}: row {number} is not a {DELIVERED_SCHEMA} row')
            key = (row['lineage'], row['boundary'], row['arm'], row['repeat'])
            if key in out:
                raise BatchError(f'{path.name}: row {number} repeats a delivered text of an earlier row')
            out[key] = row
    return out


def _sibling(probes: Path, name: str) -> dict:
    """A file beside a frozen probes file, read only if the directory's frozen.json lists its digest."""
    probes = Path(probes)
    path = probes.parent/name
    try:
        digest = json.loads((probes.parent/'frozen.json').read_text())['files'][name]
    except (OSError, ValueError, KeyError, TypeError):
        digest = None
    if not path.is_file() or digest is None or file_sha256(path) != digest:
        raise BatchError(f'{analysis._relative(path)}: not a frozen file (no matching digest in its directory\'s frozen.json)')
    return json.loads(path.read_text(encoding='utf-8'))


class Frozen:
    """The frozen held-out probes and what sits beside them: the units, and per lineage the directory's files."""

    def __init__(self, paths: Sequence[Path]):
        if not paths:
            raise BatchError('--probes is required (once per held-out directory)')
        self.rows: list[dict] = []
        self.where: dict[str, Path] = {}      # lineage -> its probes file
        self.digests: list[str] = []          # the probes files' and their freezes' sha256, for the build digest
        for path in map(Path, paths):
            try:
                rows, files = analysis.frozen_probes([path])
            except analysis.ScoreError as error:
                raise BatchError(str(error)) from None
            self.digests += [d for f in files for d in (f['sha256'], f['frozen_sha256'])]
            for row in rows:
                self.where.setdefault(row.get('lineage'), path)
            self.rows += rows
        if set(self.where) != set(analysis.HELD_OUT):
            raise BatchError(f'the probes must cover exactly the held-out lineages: {", ".join(analysis.HELD_OUT)}')
        try:
            self.units = analysis.units(analysis.primary_probes(self.rows))
        except analysis.ScoreError as error:
            raise BatchError(str(error)) from None
        self._cache: dict[tuple, dict] = {}

    def document(self, lineage: str, name: str) -> dict:
        path = self.where[lineage]
        if (path, name) not in self._cache:
            self._cache[(path, name)] = _sibling(path, name)
        return self._cache[(path, name)]


class Units(NamedTuple):
    """What the question, reader and rewrite steps need of the units: who they are, where each earlier frame is
    (relative to the evidence root) and the digests of what they came from."""
    units: list[dict]
    frames: dict[str, object]
    digests: list[str]
    development: bool


def frozen_units(frozen: Frozen) -> Units:
    """The held-out units, with each one's earlier frame from its directory's frozen candidates file."""
    earlier = {}
    for lineage in frozen.where:
        earlier.update({c['id']: c.get('earlier_path') for c in frozen.document(lineage, 'candidates.json')['candidates']
                        if c.get('lineage') == lineage})
    return Units(frozen.units, {u['probe']: earlier.get(u['probe']) for u in frozen.units}, frozen.digests, False)


def held_out_names() -> set[str]:
    """The directory names that mark held-out content: the lineages, their admissions (session directories), the
    evidence studies they sit in and the tracked held-out directories. Names only; nothing is opened to find them."""
    return (set(analysis.HELD_OUT) | {run for runs in analysis.HELD_OUT.values() for run in runs}
            | set(HELD_OUT_STUDIES.values()) | {HELD_OUT_DIR.name, HELD_OUT_LH4_DIR.name})


def development_units(path: Path) -> Units:
    """Development units from a JSON Lines file of `probe`, `lineage`, `boundary` and `frame` (the earlier frame's path
    under the evidence root): the #490 pairs the development check uses. A held-out lineage is refused, and so is a frame
    whose path has a held-out lineage, admission or study directory among its components."""
    units, frames = [], {}
    for number, row in enumerate(_jsonl(path), 1):
        if (not isinstance(row, dict) or set(row) != {'probe', 'lineage', 'boundary', 'frame'}
                or not all(isinstance(v, str) and v for v in row.values())):
            raise BatchError(f'{Path(path).name}: line {number} is not a development unit (probe, lineage, boundary, frame)')
        if row['lineage'] in analysis.HELD_OUT:
            raise BatchError(f'--development takes development lineages only; {row["lineage"]} is held out')
        if held_out_names() & set(Path(os.path.normpath(row['frame'])).parts):
            raise BatchError(f'{Path(path).name}: line {number} has a frame under a held-out session directory')
        if row['probe'] in frames:
            raise BatchError(f'{Path(path).name}: line {number} repeats a probe')
        frames[row['probe']] = row['frame']
        units.append(dict(lineage=row['lineage'], boundary=row['boundary'], cluster=row['probe'], probe=row['probe']))
    if not units:
        raise BatchError(f'{Path(path).name}: no development units')
    return Units(sorted(units, key=lambda u: u['probe']), frames, [_digest(path)], True)


def load_units(probes: Sequence[Path] | None, development: Path | None) -> Units:
    if probes and development:
        raise BatchError('--probes and --development are alternatives')
    if development:
        return development_units(development)
    return frozen_units(Frozen(probes or []))


def load_questions(path: Path, study: Units | None = None, *, frozen: bool = False) -> dict[str, dict]:
    """Probe id -> question row. With `study`, exactly one per unit. With `frozen`, held-out only (a development
    run needs no freeze): the file must match the digest in the `frozen.json` beside it."""
    try:
        if frozen and not (study and study.development):
            rows, _ = analysis.frozen_file(path, 'questions')
        else:
            rows = _jsonl(path)
        return analysis.question_rows(rows, study.units if study else None)
    except analysis.ScoreError as error:
        raise BatchError(f'{Path(path).name}: {error}') from None


def read_ids(path: Path) -> list[str]:
    """Probe ids, one per line (blank lines ignored)."""
    try:
        ids = [line.strip() for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    except (OSError, UnicodeError):
        raise BatchError(f'{Path(path).name}: unreadable ids file') from None
    if not ids or len(set(ids)) != len(ids):
        raise BatchError(f'{Path(path).name}: needs at least one probe id, each once')
    return sorted(ids)


# ------------------------------------------------------------------ mixing and writing
def pack(entries: Iterable[dict], seed: int | str) -> list[list[dict]]:
    """Entries (each with `sort` and `unit`) in a seeded order, at most BATCH_SIZE to a batch and no batch with
    two entries of one unit: each goes to the earliest batch that has room and no entry of its unit."""
    ordered = sorted(entries, key=lambda e: e['sort'])
    random.Random(seed).shuffle(ordered)
    batches: list[list[dict]] = []
    for entry in ordered:
        for batch in batches:
            if len(batch) < BATCH_SIZE and all(other['unit'] != entry['unit'] for other in batch):
                batch.append(entry)
                break
        else:
            batches.append([entry])
    return batches


def chunks(entries: list[dict]) -> list[list[dict]]:
    """Entries in the order given, BATCH_SIZE to a batch (no shuffle)."""
    return [entries[i:i + BATCH_SIZE] for i in range(0, len(entries), BATCH_SIZE)]


def _dump(value: object) -> str:
    return json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + '\n'


def _check_out(out: Path) -> Path:
    """The judge files hold absolute paths: they stay under the repository's `.runtime/` (not tracked)."""
    resolved = Path(out).resolve()
    if not resolved.is_relative_to((ROOT/'.runtime').resolve()):
        raise BatchError('--out holds absolute paths: it must be under the repository\'s .runtime/')
    return resolved


def _constants(kind: str) -> dict:
    """The seeds, limits and packing that shape a kind's batches, read when the digest is made."""
    shared = dict(batch_size=BATCH_SIZE, packing=PACKING)
    return dict(shared, **{
        'question': {}, 'screen': {}, 'paraphrase': {},
        'reader': dict(texts=TEXT_ORDER, sample_seed=analysis.REJUDGE_SEED, share=analysis.REJUDGE_SHARE,
                       order_seed=READER_SEED, development_arms=analysis.DEVELOPMENT_ARMS),
        'grader': dict(order_seed=GRADER_SEED, texts=TEXT_ORDER),
        'audit': dict(order_seed=AUDIT_ORDER_SEED, draw_seed=AUDIT_SEED, sample=AUDIT_SAMPLE,
                      drop_unresolved=DROP_UNRESOLVED_CITES)}[kind])


def build_digest(kind: str, inputs: Sequence[str], variant: str = '') -> str:
    """sha256 over the kind, this module's and the analysis module's own sha256 (the latter decides which units and
    re-judged items exist), the kind's seed and packing constants, the `variant` (the re-judging reader build) and the
    sorted digests of the inputs: a change of code or seed changes every opaque id."""
    parts = [kind, file_sha256(Path(__file__)), file_sha256(Path(analysis.__file__)),
             json.dumps(_constants(kind), sort_keys=True), variant, *sorted(inputs)]
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()


def write_batches(kind: str, out: Path, batches: list[list[dict]], *, seed: int | str | None, host_version: str,
                  inputs: Sequence[str], extra: dict | None = None, variant: str = '') -> dict:
    """Write the judge files and the key. Each entry has `public` (the item minus its id) and `key`."""
    spec = KINDS[kind]
    out = _check_out(out)
    key_path = out/'keys'/f'{kind}.json'
    if key_path.exists() or any((out/'batches').glob(f'{spec["prefix"]}-*.json')):
        raise BatchError(f'{kind} batches exist under the output directory: they are written once')
    brief = frozen_brief(spec['brief'])
    build = build_digest(kind, inputs, variant)
    names, items, files = [], {}, {}
    counter = 0
    for number, batch in enumerate(batches, 1):
        name = f'{spec["prefix"]}-{number:03d}'
        listed = []
        for entry in batch:
            counter += 1
            opaque = f'{spec["letter"]}{build[:8]}-{counter:04d}'
            listed.append(dict(entry['public'], id=opaque))
            items[opaque] = entry['key']
        names.append(dict(name=name, ids=[i['id'] for i in listed]))
        files[name] = _dump(dict(schema=BATCH_SCHEMA, brief=brief, items=listed))
    key = _dump(dict(schema=KEY_SCHEMA, kind=kind, seed=seed, host_version=host_version, build_sha256=build,
                     batch_files={name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
                     batches=names, items=items, **(extra or {})))
    for name, text in files.items():
        (out/'batches').mkdir(parents=True, exist_ok=True)
        (out/'batches'/f'{name}.json').write_text(text, encoding='utf-8')
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(key, encoding='utf-8')
    listing = ''.join(f'{name} {hashlib.sha256(text.encode()).hexdigest()}\n' for name, text in sorted(files.items()))
    return dict(kind=kind, items=counter, batches=len(batches), key_sha256=file_sha256(key_path),
                batches_sha256=hashlib.sha256(listing.encode()).hexdigest())


# ------------------------------------------------------------------ question, screen and paraphrase batches
def _frame(evidence: Path, relative: object) -> str | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    path = (evidence/relative).resolve()
    return str(path) if path.is_relative_to(evidence) and path.is_file() else None


def _recorded(questions_sha256: str | None) -> dict:
    """What a key records of the questions file its build used: its sha256 (`parse` refuses a different file)."""
    return {} if questions_sha256 is None else dict(questions_sha256=questions_sha256)


def question_batches(study: Units, evidence: Path, out: Path, host_version: str, inputs: Sequence[str],
                     rewrite: list[str] | None = None, questions: dict[str, dict] | None = None,
                     questions_sha256: str | None = None) -> dict:
    """One item per unit: its id and its earlier frame; at most 10 to a batch, in probe-id order, no shuffle. A rewrite
    batch is the flagged units only, each with `rejected`, the question that was turned down."""
    wanted = {u['probe'] for u in study.units} if rewrite is None else set(rewrite)
    if rewrite is not None and (not questions or wanted - {u['probe'] for u in study.units} or wanted - set(questions)):
        raise BatchError('the flagged ids must be units that have a question')
    entries, absent = [], 0
    for unit in sorted(study.units, key=lambda u: u['probe']):
        if unit['probe'] not in wanted:
            continue
        frame = _frame(evidence, study.frames.get(unit['probe']))
        absent += frame is None
        public = dict(frame=frame)
        if rewrite is not None:
            public['rejected'] = questions[unit['probe']]['question']
        entries.append(dict(public=public, key=dict(item=unit['probe'])))
    if absent:
        raise BatchError(f'cannot build the items: {absent} earlier frames missing under the evidence root')
    return write_batches('question', out, chunks(entries), seed=None, host_version=host_version, inputs=inputs,
                         extra=dict(rewrite=rewrite is not None, **_recorded(questions_sha256)))


def _question_entries(questions: dict[str, dict], only: list[str] | None, fields: tuple[str, ...]) -> list[dict]:
    chosen = sorted(questions) if only is None else only
    if set(chosen) - set(questions):
        raise BatchError('the ids file names probes that have no question')
    return [dict(public={f: questions[p][f] for f in fields}, key=dict(item=p)) for p in chosen]


def screen_batches(questions: dict[str, dict], only: list[str] | None, out: Path, host_version: str,
                   inputs: Sequence[str], questions_sha256: str | None = None) -> dict:
    """The no-text answerer's batches: id and question only, at most 10 to a batch, in probe-id order (the Guess brief)."""
    return write_batches('screen', out, chunks(_question_entries(questions, only, ('question',))), seed=None,
                         host_version=host_version, inputs=inputs, extra=_recorded(questions_sha256))


def paraphrase_batches(questions: dict[str, dict], only: list[str] | None, out: Path, host_version: str,
                       inputs: Sequence[str], questions_sha256: str | None = None) -> dict:
    """The paraphrasers' batches: id, question and key, at most 10 to a batch, in probe-id order."""
    return write_batches('paraphrase', out, chunks(_question_entries(questions, only, ('question', 'key'))), seed=None,
                         host_version=host_version, inputs=inputs, extra=_recorded(questions_sha256))


# ------------------------------------------------------------------ the mechanical screen
# Owner decision, 10 November 2026: letters and digits are separate token runs ("abc7" is "abc" and "7"), and a single
# digit counts as a token.
_TOKENS = re.compile(r'[^\W\d_]+|\d+')


def tokens(text: str) -> set[str]:
    """Lower-cased runs of letters or of digits; only a run of digits or of MIN_LETTERS letters or more counts."""
    return {t for t in _TOKENS.findall(text.lower()) if t.isdecimal() or len(t) >= MIN_LETTERS}


def mechanical_flags(question: str, key: str) -> set[str]:
    """The rules of "The screen" that flag a question: `empty_key`, `entries` (more than MAX_ENTRIES, the key split
    on commas, semicolons and line breaks; empty entries are not counted) and `token` (the key shares a token with
    the question)."""
    flags = set()
    if not key.strip():
        flags.add('empty_key')
    # Owner decision, 10 November 2026: empty key entries ("a,, b", a trailing comma) are not counted.
    if len([e for e in re.split(r'[,;\r\n]', key) if e.strip()]) > MAX_ENTRIES:
        flags.add('entries')
    if tokens(question) & tokens(key):
        flags.add('token')
    return flags


def not_stated(answer: str) -> bool:
    """An answer that is exactly "not stated", ignoring case, surrounding whitespace and one final full stop."""
    # Owner decision, 10 November 2026: "not stated" also ignores surrounding whitespace.
    text = answer.strip().lower()
    return (text[:-1] if text.endswith('.') else text) == 'not stated'


def read_checks(path: Path, purpose: str) -> dict[str, dict]:
    """Probe id -> `p1-check/1` row of a grader's verdicts on the screen's answers or on a paraphrase check."""
    out = {}
    for number, row in enumerate(_jsonl(path), 1):
        if (not isinstance(row, dict) or set(row) != {'schema', 'purpose', 'probe', 'correct', 'answered'}
                or row['schema'] != CHECK_SCHEMA or row['purpose'] != purpose or not isinstance(row['probe'], str)
                or not isinstance(row['correct'], bool) or not isinstance(row['answered'], bool)):
            raise BatchError(f'{Path(path).name}: line {number} is not a {CHECK_SCHEMA} {purpose} row')
        if row['probe'] in out:
            raise BatchError(f'{Path(path).name}: line {number} repeats a probe')
        out[row['probe']] = row
    return out


def screen(questions: dict[str, dict], checks: dict[str, dict], previous: list[str] | None) -> tuple[list[str], dict]:
    """(flagged probe ids, counts) of the question screen. The first run screens every question; with `previous` (the
    ids the first run flagged and a fresh writer rewrote) it screens those again, and what is flagged again stays: those
    are the questions flagged twice. The no-text check needs a verdict for each question screened, none for another."""
    screened = sorted(questions) if previous is None else previous
    if set(screened) - set(questions) or set(checks) != set(screened):
        raise BatchError(f'the no-text verdicts must cover exactly the {len(screened)} questions screened')
    by_rule = {rule: [p for p in screened if rule in mechanical_flags(questions[p]['question'], questions[p]['key'])]
               for rule in ('empty_key', 'entries', 'token')}
    by_rule['no_text'] = [p for p in screened if checks[p]['correct']]
    flagged = sorted({p for ids in by_rule.values() for p in ids})
    # Flagged twice: what the second run flags again. A first run that flags nothing needs no second run: none.
    twice = len(flagged) if previous is not None else (0 if not flagged else None)
    counts = dict(questions=len(screened), flagged_by={rule: len(ids) for rule, ids in by_rule.items()},
                  flagged=len(flagged), flagged_twice=twice)
    return flagged, counts


# ------------------------------------------------------------------ paraphrases
def read_answers(paths: Sequence[Path]) -> list[dict]:
    """`p1-answer/1` rows of every file given: one source and one pass (first or re-judging) in all of them."""
    rows, seen = [], set()
    for path in map(Path, paths):
        for number, row in enumerate(_jsonl(path), 1):
            ok = (isinstance(row, dict) and set(row) == {'schema', 'source', 'probe', 'arm', 'repeat', 'rejudge', 'answer'}
                  and row['schema'] == ANSWER_SCHEMA and row['source'] in tuple(SOURCES) and row['arm'] in SOURCES[row['source']]
                  and isinstance(row['probe'], str) and isinstance(row['answer'], str) and isinstance(row['rejudge'], bool)
                  and row['repeat'] in analysis.ARM_REPEATS.get(row['arm'], (1,)) and not isinstance(row['repeat'], bool))
            if not ok:
                raise BatchError(f'{path.name}: line {number} is not a {ANSWER_SCHEMA} row')
            key = (row['probe'], row['arm'], row['repeat'])
            if key in seen:
                raise BatchError(f'{path.name}: line {number} repeats an answer')
            seen.add(key)
            rows.append(row)
    if len({(r['source'], r['rejudge']) for r in rows}) > 1:
        raise BatchError('the answers must be of one source and one pass')
    return rows


def resolve_sentences(paraphrases: list[list[dict]], checks: list[dict[str, dict]]) -> tuple[list[dict], list[str]]:
    """(sentence rows, ids still failing) from one or two stages of paraphrase and check. A sentence is checked as an
    answer to its question; one marked not correct is rewritten once, from a second batch of exactly those ids, and
    checked again; one that fails twice is used as it is and counted (Owner decision, 10 November 2026)."""
    if not 1 <= len(paraphrases) == len(checks) <= 2:
        raise BatchError('sentences takes one or two pairs of --paraphrases and --checks')
    final: dict[str, dict] = {}
    failing: list[str] | None = None
    for stage, (rows, verdicts) in enumerate(zip(paraphrases, checks), 1):
        got = {r['probe']: r['answer'] for r in rows}
        if set(got) != set(verdicts) or (failing is not None and set(got) != set(failing)):
            raise BatchError(f'stage {stage}: the paraphrases, their checks and the ids to rewrite must be the same probes')
        for probe, sentence in got.items():
            final[probe] = dict(schema=SENTENCE_SCHEMA, probe=probe, sentence=sentence, attempts=stage,
                                correct=verdicts[probe]['correct'])
        failing = sorted(p for p, v in verdicts.items() if not v['correct'])
    return [final[p] for p in sorted(final)], failing or []


def read_sentences(path: Path, study: Units) -> dict[str, str]:
    rows = _jsonl(path)
    if (not all(isinstance(r, dict) and set(r) == {'schema', 'probe', 'sentence', 'attempts', 'correct'}
                and r['schema'] == SENTENCE_SCHEMA and isinstance(r['probe'], str) and isinstance(r['sentence'], str)
                for r in rows) or sorted(r['probe'] for r in rows) != sorted(u['probe'] for u in study.units)):
        raise BatchError(f'{Path(path).name}: not one {SENTENCE_SCHEMA} row for each unit')
    return {r['probe']: r['sentence'] for r in rows}


# ------------------------------------------------------------------ reader batches
def _line(text: str) -> str:
    """One line: runs of whitespace as single spaces."""
    return ' '.join(text.split())


def _key_line(key: str) -> str:
    """A key on one line: its entries on separate lines are joined with `; ` (Owner decision, 10 November 2026), the
    whitespace within an entry collapses to single spaces and no separator leads or trails. A comma or semicolon
    that ends a line is dropped, so the join never doubles a separator (`bolt,` then `saw` is `bolt; saw`)."""
    return '; '.join(entry for entry in (_line(part).rstrip(',; ') for part in re.split(r'[\r\n]+', key)) if entry)


def appended(text: str, line: str) -> str:
    """The text with a new last line `- <line>` (The positive control)."""
    return f'{text}{"" if not text or text.endswith(chr(10)) else chr(10)}- {line}'


def reader_batches(study: Units, delivered: dict, questions: dict[str, dict], sentences: dict[str, str] | None,
                   out: Path, host_version: str, inputs: Sequence[str], rejudge: bool = False,
                   questions_sha256: str | None = None) -> dict:
    """One item per file, each a fresh reader's: `id`, `text` and `question`. Per unit the texts are A repeat 1, B
    repeats 1 and 2, `R` (the received text alone), `PW` (R with the new last line `- <question> <key>`, the key's
    entries on separate lines joined with `; `) and `PP` (R with `- <sentence>`). A development unit has B repeat 1 only
    (`DEVELOPMENT_ARMS`). The items are sorted by probe id, then text (A, B, R, PW, PP), then repeat, and numbered and
    filed in a Random(READER_SEED) shuffle of that list, so neither the id nor the file name follows the arm. A
    re-judging build has only the seeded sample of A's and B's labels (every one in development), shuffled with the
    same seed over its own list."""
    arms = analysis.DEVELOPMENT_ARMS if study.development else analysis.ARMS
    study_arms = [(arm, repeat) for arm, reps in arms.items() for repeat in reps]
    if study.development:      # every A and B label, not a sample (rejudge_sample is the held-out sample's)
        sample = {(analysis.KIND, arm, repeat, u['probe']) for u in study.units for arm, repeat in study_arms} if rejudge else None
    else:
        sample = analysis.rejudge_sample(study.units, analysis.REJUDGE_SHARE) if rejudge else None
    entries, missing, partial = [], 0, 0
    for unit in sorted(study.units, key=lambda u: u['probe']):
        probe, q = unit['probe'], questions[unit['probe']]
        row = lambda arm, repeat: delivered.get((unit['lineage'], unit['boundary'], arm, repeat))  # noqa: E731
        texts = [(arm, repeat, row(arm, repeat)) for arm, repeat in study_arms
                 if sample is None or (analysis.KIND, arm, repeat, probe) in sample]
        if not rejudge:
            texts.append(('R', 1, row('R', 1)))
            received = row('R', 1)
            for arm, line in (('PW', _line(f'{_line(q["question"])} {_key_line(q["key"])}')), ('PP', _line(sentences[probe]))):
                texts.append((arm, 1, None if received is None else dict(received, text=appended(received['text'], line))))
        for arm, repeat, found in texts:
            if found is None:
                missing += 1
            elif not found['complete']:
                partial += 1
            else:
                entries.append(dict(sort=(probe, TEXT_ORDER.index(arm), repeat), public=dict(text=found['text'], question=q['question']),
                                    key=dict(arm=arm, repeat=repeat, item=probe)))
    if missing or partial:
        raise BatchError(f'cannot build the items: {missing} delivered texts missing, {partial} incomplete')
    entries.sort(key=lambda e: e['sort'])
    random.Random(READER_SEED).shuffle(entries)     # Owner decision, 10 November 2026: ids and file names do not follow the arm
    return write_batches('reader', out, [[e] for e in entries], seed=READER_SEED, host_version=host_version, inputs=inputs,
                         extra=dict(rejudge=rejudge, sample_seed=analysis.REJUDGE_SEED if rejudge else None,
                                    development=study.development, **_recorded(questions_sha256)),
                         variant='rejudge' if rejudge else '')


# ------------------------------------------------------------------ grader batches
def grader_batches(answers: list[dict], questions: dict[str, dict], out: Path, host_version: str,
                   inputs: Sequence[str], questions_sha256: str | None = None) -> dict:
    """Items `id`, `question`, `key` and `answer`. An answer that is exactly "not stated" never enters a batch: it is
    recorded in the key as incorrect. The rest are sorted by probe, then text (A, B, R, PW, PP), then repeat, mixed with
    Random(GRADER_SEED) and packed first-fit, at most 10 to a batch and no two answers to one probe in a batch."""
    if not answers:
        raise BatchError('no answers to grade')
    if {r['probe'] for r in answers} - set(questions):
        raise BatchError('some answers belong to probes that have no question')
    order = lambda r: (r['probe'], TEXT_ORDER.index(r['arm']), r['repeat'])  # noqa: E731
    entries, mechanical = [], []
    for row in sorted(answers, key=order):
        meta = dict(arm=row['arm'], repeat=row['repeat'], item=row['probe'])
        if not_stated(row['answer']):
            mechanical.append(meta)
            continue
        q = questions[row['probe']]
        entries.append(dict(sort=order(row), unit=row['probe'], key=meta,
                            public=dict(question=q['question'], key=q['key'], answer=row['answer'])))
    first = answers[0]
    result = write_batches('grader', out, pack(entries, GRADER_SEED), seed=GRADER_SEED, host_version=host_version,
                           inputs=inputs, extra=dict(source=first['source'], rejudge=first['rejudge'], mechanical=mechanical,
                                                     **_recorded(questions_sha256)))
    return dict(result, mechanical=len(mechanical))


# ------------------------------------------------------------------ audit batches
def _resolve_cites(evidence: Path, lineage: str, cites: object) -> tuple[list[tuple[str, str, int]], int]:
    """([(source id, absolute path, the session's place in the lineage)] sealed in the lineage's sessions, count of
    cited ids that are not found)."""
    study = evidence/HELD_OUT_STUDIES[lineage]/'computer-sessions'
    found, unresolved = [], 0
    for source in cites if isinstance(cites, list) else []:
        hits = []
        if isinstance(source, str) and _SOURCE_ID.fullmatch(source):
            hits = [(p, place) for place, run in enumerate(analysis.HELD_OUT[lineage])
                    if (p := study/run/'sources'/f'{source}.png').is_file()]
        if len(hits) > 1:
            raise BatchError(f'{lineage}: a cited frame id is sealed in more than one session')
        if hits:
            found.append((source, str(hits[0][0].resolve()), hits[0][1]))
        else:
            unresolved += 1
    return found, unresolved


def _capture(source: str) -> int:
    """The numeric capture id at the end of a source id, `<session>-<capture id>`."""
    tail = source.rsplit('-', 1)[-1]
    if not tail.isdigit():
        raise BatchError('a source id does not end in a numeric capture id')
    return int(tail)


def chronological(cited: list[tuple[str, str, int]], coverage: list[tuple[str, str, int]]) -> list[dict]:
    """Frames in capture order: by the session's place in the lineage, then by the capture id. A frame that is
    cited and also a coverage frame appears once, with `cited` true. The Audit brief judges "by the last listed
    frame", so the last one listed is the latest."""
    frames: dict[str, tuple] = {}
    for is_cited, group in ((False, coverage), (True, cited)):
        for source, path, place in group:
            frames[source] = (place, _capture(source), source, path, is_cited or (source in frames and frames[source][4]))
    return [dict(source=source, frame=path, cited=is_cited) for _, _, source, path, is_cited in sorted(frames.values())]


def audit_batches(frozen: Frozen, delivered: dict, evidence: Path, out: Path, host_version: str,
                  inputs: Sequence[str]) -> dict:
    chunks_of: dict[tuple, dict] = {}
    planned: set[tuple] = set()      # (lineage, boundary) of every held-out lineage, from the digest-checked plans
    for lineage in frozen.where:
        for entry in frozen.document(lineage, 'ledger-plan.json')['lineages'][lineage]['chunks']:
            chunks_of[(lineage, entry['chunk'])] = entry
            if entry.get('incoming_boundary'):
                planned.add((lineage, entry['incoming_boundary']))
    pairs: dict[tuple, list[tuple]] = {}
    covered: dict[tuple, set] = {}
    for (lineage, boundary, arm, repeat), row in sorted(delivered.items()):
        if arm == 'R' or lineage not in analysis.HELD_OUT or repeat not in analysis.ARMS.get(arm, ()):
            continue
        covered.setdefault((arm, repeat), set()).add((lineage, boundary))
        if not row['complete'] or not isinstance(row.get('working_set'), list):
            raise BatchError(f'a delivered row of {lineage} {arm}{repeat} is incomplete or has no working_set')
        pairs.setdefault((arm, repeat), []).extend((lineage, boundary, n) for n in range(len(row['working_set'])))
    if set(pairs) != {(arm, rep) for arm, reps in analysis.ARMS.items() for rep in reps}:
        raise BatchError('the delivered files must hold A1, B1 and B2')
    for (arm, repeat), have in sorted(covered.items()):
        if have != planned:    # every boundary of every held-out lineage, for each arm and repeat
            lost, extra = sorted(planned - have), sorted(have - planned)
            raise BatchError(f'{arm}{repeat}: the delivered boundaries differ from the ledger plans '
                             f'({len(lost)} missing, e.g. {lost[:3]}; {len(extra)} unexpected, e.g. {extra[:3]})')
    entries, unresolved, drawn = [], {}, {}
    for (arm, repeat), universe in sorted(pairs.items()):
        # Owner decision, 10 November 2026: a fresh Random(4913) for each (arm, repeat), as the page words it
        # ("For each arm and each repeat, Random(4913) draws"), up to 40 pairs of all the arm and repeat's delivered items.
        sample = random.Random(AUDIT_SEED).sample(universe, min(AUDIT_SAMPLE, len(universe)))
        drawn[f'{arm}{repeat}'] = len(sample)
        unresolved[f'{arm}{repeat}'] = 0
        for lineage, boundary, position in sample:
            item = delivered[(lineage, boundary, arm, repeat)]['working_set'][position]
            if not isinstance(item, dict) or not isinstance(item.get('statement'), str):
                raise BatchError(f'a delivered working_set item of {lineage} {arm}{repeat} is malformed')
            predecessor = boundary.split('>')[0]
            chunk = chunks_of.get((lineage, predecessor))
            if chunk is None:
                raise BatchError(f'{lineage}: the predecessor chunk of boundary {boundary} is not in the ledger plan')
            run = predecessor.rsplit('-', 1)[0]
            if run not in analysis.HELD_OUT[lineage]:
                raise BatchError(f'{lineage}: the predecessor chunk of boundary {boundary} is in no session of the lineage')
            place, session = analysis.HELD_OUT[lineage].index(run), evidence/HELD_OUT_STUDIES[lineage]/'computer-sessions'/run
            coverage = [(s, str((session/'sources'/f'{s}.png').resolve()), place) for s in chunk['required_frames']]
            if not all(Path(path).is_file() for _, path, _ in coverage):
                raise BatchError(f'{lineage}: a coverage frame of a predecessor chunk is missing under the evidence root')
            cited, lost = _resolve_cites(evidence, lineage, item.get('cites'))
            if lost and not DROP_UNRESOLVED_CITES:
                raise BatchError(f'{lineage}: a cited frame is not sealed')
            unresolved[f'{arm}{repeat}'] += lost
            entries.append(dict(
                sort=(arm, repeat, lineage, boundary, position), unit=(arm, repeat, lineage, boundary, position),
                # The statement as the arm-blind judges see it (one `- ` line), then frames only, in capture order:
                # the frames it cites and the predecessor chunk's coverage-rule frames. Never the timeline text,
                # which holds the predecessor's memory records. No arm, repeat or lineage.
                public=dict(statement=f'- {item["statement"]}', frames=chronological(cited, coverage)),
                key=dict(arm=arm, repeat=repeat, item=f'{lineage}/{boundary}#{position}')))
    return dict(write_batches('audit', out, pack(entries, AUDIT_ORDER_SEED), seed=AUDIT_ORDER_SEED,
                              host_version=host_version, inputs=inputs,
                              extra=dict(draw_seed=AUDIT_SEED, drawn=drawn, unresolved_cites=unresolved)),
                drawn=drawn, unresolved_cites=unresolved)


# ------------------------------------------------------------------ parsing the judges' files
def _boolean(value: object) -> bool:
    return isinstance(value, bool)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


# kind -> (the exact keys of a line, the checks of its values)
SHAPES = {
    'question': (('id', 'key', 'question'), {'key': lambda v: isinstance(v, str), 'question': _text}),
    'screen': (('answer', 'id'), {'answer': _text}),
    'reader': (('answer', 'id'), {'answer': _text}),
    'paraphrase': (('id', 'sentence'), {'sentence': _text}),
    'grader': (('correct', 'id', 'why'), {'correct': _boolean, 'why': lambda v: isinstance(v, str)}),
    'audit': (('false', 'frame', 'id', 'why'), {'false': _boolean, 'why': lambda v: isinstance(v, str)}),
}


def _load_key(run: Path, kind: str) -> dict:
    path = Path(run)/'keys'/f'{kind}.json'
    try:
        key = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise BatchError(f'{path.name}: no readable key file for {kind} under --batches') from None
    if (not isinstance(key, dict) or key.get('schema') != KEY_SCHEMA or key.get('kind') != kind
            or not isinstance(key.get('batches'), list) or not isinstance(key.get('items'), dict)):
        raise BatchError(f'{path.name}: not a {KEY_SCHEMA} file for {kind}')
    return key


def _answers(path: Path, ids: list[str], key: dict, kind: str) -> dict[str, dict]:
    keys, checks = SHAPES[kind]
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        raise BatchError(f'{path.name}: unreadable output file') from None
    got: dict[str, dict] = {}
    for number, line in enumerate(text.splitlines(), 1):
        where = f'{path.name}:{number}'
        try:
            row = json.loads(line)
        except ValueError:
            raise BatchError(f'{where}: not JSON') from None
        if not isinstance(row, dict) or tuple(sorted(row)) != keys:
            raise BatchError(f'{where}: not exactly the brief\'s JSON shape (keys {", ".join(keys)})')
        if not isinstance(row['id'], str) or row['id'] not in ids:
            raise BatchError(f'{where}: id is not in the batch\'s key')
        if row['id'] in got:
            raise BatchError(f'{where}: duplicated id {row["id"]}')
        for field, valid in checks.items():
            if not valid(row[field]):
                raise BatchError(f'{where}: field {field} (id {row["id"]}) has the wrong type or value')
        if kind == 'audit':
            frame = row['frame']
            if frame is None or frame == 'null':     # the brief's `<source id or null>`, written either way
                row['frame'] = None
            elif not isinstance(frame, str) or _SOURCE_ID.fullmatch(frame) is None:
                raise BatchError(f'{where}: frame (id {row["id"]}) is not null or a source id')
        got[row['id']] = row
    if len(got) != len(ids):
        missing = [i for i in ids if i not in got]
        raise BatchError(f'{path.name}: {len(missing)} ids missing (first {", ".join(missing[:3])})')
    # Every brief but the audit's says "one per item in the given order".
    if kind != 'audit' and list(got) != ids:
        raise BatchError(f'{path.name}: not in batch order')
    return got


def _verify_build(run: Path, key: dict, kind: str) -> None:
    """Every batch file under --batches is the one the key was made for: same files, same sha256."""
    directory = Path(run)/'batches'
    digests = key.get('batch_files')
    if not isinstance(digests, dict) or set(digests) != {b.get('name') for b in key['batches']}:
        raise BatchError(f'keys/{kind}.json: records no batch file digests')
    prefix = KINDS[kind]['prefix']
    present = {p.stem: p for p in directory.glob(f'{prefix}-*.json')} if directory.is_dir() else {}
    if set(present) != set(digests):
        raise BatchError(f'batches/ does not hold exactly the {kind} batch files of the key: '
                         f'{", ".join(sorted(set(present) ^ set(digests)))}')
    changed = sorted(name for name, path in present.items() if file_sha256(path) != digests[name])
    if changed:
        raise BatchError(f'batch files differ from the build the key was made for: {", ".join(changed)}')


def _row(kind: str, key: dict, item: dict, row: dict) -> dict:
    """The row one judge line makes, from the key's record of its item."""
    if kind == 'question':
        return dict(schema=analysis.QUESTION_SCHEMA, probe=item['item'], question=row['question'], key=row['key'])
    if kind in ('screen', 'paraphrase', 'reader'):
        source = 'reader' if kind == 'reader' else kind
        return dict(schema=ANSWER_SCHEMA, source=source, probe=item['item'], arm=item.get('arm', SOURCES[source][0]),
                    repeat=item.get('repeat', 1), rejudge=bool(key.get('rejudge')),
                    answer=row['answer'] if kind != 'paraphrase' else row['sentence'])
    if kind == 'audit':
        return dict(type='audit', schema=analysis.SCORE_SCHEMA, arm=item['arm'], repeat=item['repeat'],
                    item=item['item'], false=row['false'], frame=row['frame'])
    return graded(key, item, row['correct'], True)


def graded(key: dict, item: dict, correct: bool, answered: bool) -> dict:
    """A grader's verdict as a row: a `p1-score/1` label for a reader's answer, a `p1-check/1` row for the screen's
    answer or a paraphrase."""
    if key['source'] == 'reader':
        made = dict(type='label', schema=analysis.SCORE_SCHEMA, kind=analysis.KIND, arm=item['arm'], repeat=item['repeat'],
                    item=item['item'], stated=correct, answered=answered)
        return dict(made, rejudge=True) if key['rejudge'] else made
    return dict(schema=CHECK_SCHEMA, purpose=key['source'], probe=item['item'], correct=correct, answered=answered)


def _check_questions(key: dict, kind: str, path: Path | None) -> None:
    """A questions file given to `parse` is the one the batches were built from: the key records its sha256."""
    if path is None:
        return
    recorded = key.get('questions_sha256')
    if recorded is None:
        raise BatchError(f'the {kind} batches were built without a questions file')
    if _digest(path) != recorded:
        raise BatchError(f'{Path(path).name}: not the questions file the {kind} batches were built from (sha256 differs)')


def parse(kind: str, run: Path, answers: Path, base: Path | None = None, questions: Path | None = None) -> list[dict]:
    """The rows of one kind's judge output files, refusing anything not exactly as asked. A grader's rows include the
    mechanical "not stated" labels the key recorded. Question rows with `base` (the questions the rewrite was built from)
    replace the base's rows for those probes; for the other kinds `questions`, if given, must be the file the key records."""
    key = _load_key(run, kind)
    _verify_build(run, key, kind)
    if kind != 'question' and base is not None:
        raise BatchError('--base is for the question rewrite; the other kinds take --questions')
    if kind == 'question' and questions is not None:
        raise BatchError('the question rewrite takes --base, not --questions')
    _check_questions(key, kind, base if kind == 'question' else questions)
    expected = {f'{b["name"]}.jsonl': b for b in key['batches']}
    answers = Path(answers)
    if not answers.is_dir():
        raise BatchError('--answers is not a directory')
    present = {p.name for p in answers.iterdir() if not p.name.startswith('.')}
    if expected.keys() - present:
        raise BatchError(f'missing batch outputs: {", ".join(sorted(expected.keys() - present))}')
    if present - expected.keys():
        raise BatchError(f'files that belong to no batch: {", ".join(sorted(present - expected.keys()))}')
    rows = []
    for name, batch in expected.items():
        got = _answers(answers/name, batch['ids'], key, kind)
        for opaque in batch['ids']:     # the key's order, whatever order the audit judge wrote
            rows.append(_row(kind, key, key['items'][opaque], got[opaque]))
    if kind == 'grader':
        rows += [graded(key, meta, False, False) for meta in key['mechanical']]
    try:    # exactly the shapes the analysis accepts
        if kind == 'grader' and key['source'] == 'reader':
            analysis.labels(rows)
        elif kind == 'audit':
            analysis._validated(rows)
        elif kind == 'question':
            rows = _replaced(analysis.question_rows(rows), base)
    except analysis.ScoreError:
        raise BatchError(f'the {kind} rows do not satisfy the analysis\' shapes') from None
    return rows


def _replaced(found: dict[str, dict], base: Path | None) -> list[dict]:
    """The questions of `base` with the rewritten ones in place of those they replace (every rewritten probe is in it)."""
    if base is None:
        return [found[p] for p in sorted(found)]
    try:
        old = analysis.question_rows(_jsonl(base))
    except analysis.ScoreError:
        raise BatchError(f'{Path(base).name}: not a questions file') from None
    if set(found) - set(old):
        raise BatchError('the rewrite holds probes that --base has no question for')
    return [{**old, **found}[p] for p in sorted(old)]


# ------------------------------------------------------------------ command line
def _write_rows(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    return file_sha256(path)


def _fresh(*paths: Path) -> None:
    if any(Path(p).exists() for p in paths):
        raise BatchError('the output exists: it is written once')


def build_command(args: argparse.Namespace) -> dict:
    kind = args.kind
    _check_out(args.out)
    wants = {'question': (), 'screen': ('questions',), 'paraphrase': ('questions',), 'reader': ('delivered', 'questions'),
             'grader': ('answers', 'questions'), 'audit': ('probes', 'delivered')}[kind]
    missing = [name for name in wants if not getattr(args, name)]
    if kind in ('question', 'reader') and not (args.probes or args.development):
        missing.append('probes (or --development)')
    if missing:
        raise BatchError(f'{kind} batches need --{", --".join(missing)}')
    inputs = [_digest(p) for p in (args.delivered or []) + (args.answers or [])]
    inputs += [_digest(p) for p in (args.questions, args.sentences, args.only, args.rewrite) if p]
    host = args.host_version
    recorded = _digest(args.questions) if args.questions else None
    if kind == 'audit':
        frozen = Frozen(args.probes or [])
        evidence = Path(args.evidence_root or _evidence_default()).resolve()
        return audit_batches(frozen, read_delivered(args.delivered), evidence, args.out, host, inputs + frozen.digests)
    if args.development and kind in ('screen', 'paraphrase'):
        raise BatchError(f'--development is for question, reader and grader builds, not {kind}')
    if kind in ('screen', 'paraphrase', 'grader'):
        only = read_ids(args.only) if args.only else None
        if kind != 'grader':    # the pre-freeze steps: no freeze exists yet
            return (screen_batches if kind == 'screen' else paraphrase_batches)(
                load_questions(args.questions), only, args.out, host, inputs, recorded)
        answers = read_answers(args.answers)
        if not answers:
            raise BatchError('no answers to grade')
        study = development_units(args.development) if args.development else None
        if study is not None:
            inputs += study.digests
            if {r['probe'] for r in answers} - {u['probe'] for u in study.units}:
                raise BatchError('some answers belong to probes outside the development units')
        # A reader's answers are held-out unless --development says otherwise, and held-out questions must be the
        # frozen file; the screen's and the paraphrase check's graders run before the freeze.
        questions = load_questions(args.questions, study, frozen=answers[0]['source'] == 'reader' and study is None)
        return grader_batches(answers, questions, args.out, host, inputs, recorded)
    study = load_units(args.probes, args.development)
    inputs += study.digests
    if kind == 'question':
        evidence = Path(args.evidence_root or _evidence_default()).resolve()
        rewrite = read_ids(args.rewrite) if args.rewrite else None
        if rewrite is not None and not args.questions:
            raise BatchError('a rewrite needs --questions (the flagged questions are the rejected ones)')
        questions = load_questions(args.questions) if args.questions else None
        return question_batches(study, evidence, args.out, host, inputs, rewrite, questions, recorded)
    delivered = read_delivered(args.delivered)
    held = sorted({lineage for lineage, *_ in delivered if lineage in analysis.HELD_OUT})
    if study.development and held:
        raise BatchError(f'a development run takes development rows only; held-out lineages given: {", ".join(held)}')
    if study.development:
        allowed = {(arm, repeat) for arm, reps in analysis.DEVELOPMENT_ARMS.items() for repeat in reps} | {('R', 1)}
        other = sum(key[2:] not in allowed for key in delivered)
        if other:
            raise BatchError(f'a development delivery has A repeat 1, B repeat 1 and the received text only: '
                             f'{other} delivered rows are unexpected (development has no second B repeat)')
    if bool(args.rejudge) == bool(args.sentences):
        raise BatchError('reader batches need --sentences (the first pass) or --rejudge (the re-judging), not both')
    questions = load_questions(args.questions, study, frozen=True)
    sentences = read_sentences(args.sentences, study) if args.sentences else None
    return reader_batches(study, delivered, questions, sentences, args.out, host, inputs, bool(args.rejudge), recorded)


def screen_command(args: argparse.Namespace) -> dict:
    out = _check_out(args.out)
    _fresh(out/'flagged.txt', out/'counts.json')
    questions = load_questions(args.questions)
    previous = read_ids(args.previous) if args.previous else None
    checks = read_checks(args.graded, 'screen') if args.graded else None
    if checks is None:
        raise BatchError('screen needs --graded (the grader\'s verdicts on the no-text answers)')
    flagged, counts = screen(questions, checks, previous)
    out.mkdir(parents=True, exist_ok=True)
    (out/'flagged.txt').write_text(''.join(f'{p}\n' for p in flagged), encoding='utf-8')
    (out/'counts.json').write_text(_dump(counts), encoding='utf-8')
    return counts


def sentences_command(args: argparse.Namespace) -> dict:
    out = _check_out(args.out)
    _fresh(out/'sentences.jsonl', out/'failed.txt', out/'counts.json')
    stages = [read_answers([p]) for p in args.paraphrases or []]
    if any(r['source'] != 'paraphrase' for rows in stages for r in rows):
        raise BatchError('--paraphrases takes the parsed paraphrase answers')
    rows, failing = resolve_sentences(stages, [read_checks(p, 'paraphrase') for p in args.checks or []])
    _write_rows(out/'sentences.jsonl', rows)
    (out/'failed.txt').write_text(''.join(f'{p}\n' for p in failing), encoding='utf-8')
    counts = dict(units=len(rows), stages=len(stages), rewritten=len(stages[1]) if len(stages) > 1 else 0, failed=len(failing))
    (out/'counts.json').write_text(_dump(counts), encoding='utf-8')      # `score --sentences-counts` takes this file
    return counts


def freeze_questions(args: argparse.Namespace) -> dict:
    """`frozen.json` beside a questions file, in the format the probes' freeze uses (`p1-held-out-frozen/1`). The file
    must lie under data/evaluation/p1/questions/ and cover exactly the units of the frozen held-out probes given; the
    screen's counts (`flagged_twice`) are copied beside it as `screen.json` and listed in `frozen.json` too."""
    path = Path(args.questions)
    if not path.resolve().is_relative_to(ROOT.joinpath(*QUESTIONS_DIR).resolve()):
        raise BatchError(f'a questions freeze is written under {"/".join(QUESTIONS_DIR)}/ only')
    if not args.probes or not args.screen:
        raise BatchError('questions-freeze needs --probes (the frozen held-out probes) and --screen (the screen\'s counts)')
    target, screen_target = path.parent/'frozen.json', path.parent/'screen.json'
    _fresh(target, screen_target)
    try:
        counts = json.loads(Path(args.screen).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise BatchError(f'{Path(args.screen).name}: unreadable screen counts') from None
    if not (isinstance(counts, dict) and analysis._count(counts.get('flagged_twice'))):
        raise BatchError(f'{Path(args.screen).name}: the screen counts need an integer flagged_twice (the second run\'s)')
    study = Frozen(args.probes)      # refuses probes that are not frozen or do not cover the held-out lineages
    try:
        rows = analysis.question_rows(_jsonl(path), study.units)
    except analysis.ScoreError as error:
        raise BatchError(f'{path.name}: {error}') from None
    screen_target.write_bytes(Path(args.screen).read_bytes())
    document = dict(schema=analysis.FROZEN_SCHEMA, protocol='p1-study/3', frozen=args.frozen,
                    files={path.name: _digest(path), screen_target.name: _digest(screen_target)})
    target.write_text(_dump(document), encoding='utf-8')
    return dict(questions=len(rows), sha256=document['files'][path.name], screen_sha256=document['files'][screen_target.name],
                frozen_sha256=file_sha256(target))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='p1_analysis', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('batches', help='write the judge batches and their key')
    build.add_argument('kind', choices=tuple(KINDS))
    build.add_argument('--probes', type=Path, action='append', help='a frozen held-out p1-probes/1 file, once per directory')
    build.add_argument('--development', type=Path, help='development units: JSON Lines of probe, lineage, boundary, frame '
                                                        '(question, reader; grader over a reader\'s development answers, which then needs no freeze)')
    build.add_argument('--delivered', type=Path, action='append', help='a p1-delivered/2 file')
    build.add_argument('--questions', type=Path, help='the p1-question/1 file (frozen.json beside it for held-out readers '
                                                      'and for graders over a reader\'s held-out answers)')
    build.add_argument('--sentences', type=Path, help='reader: the final p1-sentence/1 file (`sentences`)')
    build.add_argument('--answers', type=Path, action='append', help='grader: a p1-answer/1 file from `parse`')
    build.add_argument('--only', type=Path, help='screen, paraphrase: a file of probe ids, one per line')
    build.add_argument('--rewrite', type=Path, help='question: a file of flagged probe ids, one per line')
    build.add_argument('--rejudge', action='store_true', help='reader: the re-judged sample (every A and B label in development)')
    build.add_argument('--evidence-root', type=Path, default=None)
    build.add_argument('--out', type=Path, required=True, help='a new directory under the repository\'s .runtime/')
    build.add_argument('--host-version', required=True, help='the coding host\'s version, recorded with each batch')
    read = sub.add_parser('parse', help='turn the judges\' output files into the next step\'s rows')
    read.add_argument('kind', choices=tuple(KINDS))
    read.add_argument('--batches', type=Path, required=True, help='the --out of `batches`')
    read.add_argument('--answers', type=Path, required=True, help='the directory of <batch>.jsonl files of this kind')
    read.add_argument('--base', type=Path, help='question: the questions the rewrite replaces rows of (the file the batches used)')
    read.add_argument('--questions', type=Path, help='the other kinds: the questions file the batches used; refused if it differs')
    read.add_argument('--out', type=Path, required=True, help='the rows file to write')
    check = sub.add_parser('screen', help='flag questions: the mechanical rule and the no-text answers (counts only)')
    check.add_argument('--questions', type=Path, required=True)
    check.add_argument('--graded', type=Path, help='the p1-check/1 rows of the graded no-text answers')
    check.add_argument('--previous', type=Path, help='the second run: the ids the first run flagged (flagged.txt)')
    check.add_argument('--out', type=Path, required=True, help='a new directory under .runtime/: flagged.txt, counts.json')
    final = sub.add_parser('sentences', help='the paraphrases to use, after one or two stages of check')
    final.add_argument('--paraphrases', type=Path, action='append')
    final.add_argument('--checks', type=Path, action='append')
    final.add_argument('--out', type=Path, required=True, help='a new directory under .runtime/: sentences.jsonl, failed.txt')
    freeze = sub.add_parser('questions-freeze', help='write frozen.json beside a questions file under data/evaluation/p1/questions/')
    freeze.add_argument('--questions', type=Path, required=True)
    freeze.add_argument('--frozen', required=True, help='the freeze date, recorded')
    freeze.add_argument('--probes', type=Path, action='append', help='a frozen held-out p1-probes/1 file, once per directory; '
                                                                    'the questions must cover exactly their units')
    freeze.add_argument('--screen', type=Path, help='the screen\'s counts.json (flagged_twice); copied beside the questions as screen.json')
    args = parser.parse_args(argv)
    try:
        if args.command == 'parse':
            if args.out.exists():
                raise BatchError('--out exists: the rows are written once')
            rows = parse(args.kind, args.batches, args.answers, args.base, args.questions)
            result = dict(kind=args.kind, rows=len(rows), rows_sha256=_write_rows(args.out, rows))
        elif args.command == 'screen':
            result = screen_command(args)
        elif args.command == 'sentences':
            result = sentences_command(args)
        elif args.command == 'questions-freeze':
            result = freeze_questions(args)
        else:
            result = build_command(args)
    except (BatchError, analysis.ScoreError) as error:
        print(f'p1_batches: {error}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
