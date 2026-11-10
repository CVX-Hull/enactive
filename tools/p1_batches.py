"""The P1 offline study's judge batches and their parsing (pre-registration p1-study/2, docs/design/p1-study-2.md, "Judges"; #518).

  python -m tools.p1_analysis batches scoring --probes <p1-probes/1>... --delivered <delivered.jsonl>... --out DIR --host-version V
  python -m tools.p1_analysis batches rejudge --probes <p1-probes/1>... --delivered <delivered.jsonl>... --out DIR --host-version V
  python -m tools.p1_analysis batches audit   --probes <p1-probes/1>... --delivered <delivered.jsonl>... --out DIR --host-version V
  python -m tools.p1_analysis batches guess   --delivered <delivered.jsonl>... --out DIR --host-version V
  python -m tools.p1_analysis parse {scoring,rejudge,audit,guess} --batches DIR --answers DIR --out FILE

`batches` writes, under `--out`, the judge-facing files `batches/<kind>-NNN.json` (the frozen brief, word for
word, and items that carry an opaque `id` and what the brief names) and, apart from them, `keys/<kind>.json`,
which maps each opaque id to what only the analysis may know (arm, repeat, probe) and is never given to a
judge. The judge files hold absolute frame paths, so `--out` must lie under the repository's `.runtime/`. The
same inputs give byte-identical files. An opaque id is `<letter><8 hex of the build digest>-<counter>`, the
build digest being a sha256 over the kind, this module's own sha256, the kind's seeds and the sorted digests of
the inputs, and the key holds each batch
file's sha256, so output from another build, or for an altered batch file, is refused.

`parse` reads one judge output file per batch (`<batch>.jsonl` in `--answers`, one directory per kind) and
writes the `p1-score/1` rows `tools.p1_analysis score` takes: `label` rows (`rejudge` true for the second
pass), `audit` rows and `guess` rows. It refuses anything that is not exactly the brief's JSON shape.

Nothing here prints a delivered text, a frame path, a source id or a judge's words: only counts and digests.
Error messages name files, line numbers and opaque ids.
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

from harness.jsonio import file_sha256
from tools import p1_analysis as analysis
from tools.probe_validation import HELD_OUT_STUDIES

ROOT = analysis.ROOT
STUDY_DOC = ROOT/'docs'/'design'/'p1-study-2.md'
BATCH_SCHEMA = 'p1-judge-batch/1'
KEY_SCHEMA = 'p1-judge-key/1'
DELIVERED_SCHEMA = 'p1-delivered/2'
BATCH_SIZE = 10          # items per scoring, re-judging and audit batch (Judges)
SCORING_SEED = 4911      # the scoring judges' mixed order (Judges, "Mixing")
AUDIT_SEED = 4913        # the audit's draw of (working-set item, boundary) pairs (Judges)
AUDIT_SAMPLE = 40        # per arm and repeat, at most

# What the pre-registration leaves open, as the owner decided on 10 November 2026.
REJUDGE_ORDER_SEED = SCORING_SEED   # Owner decision, 10 November 2026: the re-judging batches' order is Random(4911); Random(4912) only draws the sample
AUDIT_ORDER_SEED = AUDIT_SEED       # Owner decision, 10 November 2026: Random(4913) mixes the three arms' audit pairs into batches
GUESS_SEED = 4914                   # Owner decision, 10 November 2026: one Random(4914) shuffle of the 30 sorted guess items
GUESS_B_REPEAT = 1                  # Owner decision, 10 November 2026: the guess check uses A repeat 1 and B repeat 1
DROP_UNRESOLVED_CITES = True        # Owner decision, 10 November 2026: a cited frame that is not sealed is dropped and counted per arm
PACKING = 'first-fit'               # Owner decision, 10 November 2026: each text goes to the earliest batch with room and no text of its unit

# kind -> file prefix, opaque-id letter and the frozen brief it carries
KINDS = {'scoring': dict(prefix='score', letter='s', brief='Scoring'),
         'rejudge': dict(prefix='rejudge', letter='r', brief='Scoring'),
         'audit': dict(prefix='audit', letter='a', brief='Audit'),
         'guess': dict(prefix='guess', letter='g', brief='Arm guess')}
_SOURCE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*')


class BatchError(ValueError):
    """A batch cannot be built, or a judge's output is not what the brief asked for."""


def _evidence_default() -> Path:
    return Path(os.environ.get('ENACTIVE_EVIDENCE_ROOT', ROOT/'.runtime'/'evidence'))


# ------------------------------------------------------------------ the frozen briefs
def frozen_brief(label: str, doc: Path = STUDY_DOC) -> str:
    """The pre-registration's frozen brief `label`: the quote lines from `> **<label>.**` to the next
    blank line, joined by single spaces, without the leading label (the Scoring brief begins "You check")."""
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
        'scoring': dict(order_seed=SCORING_SEED),
        'rejudge': dict(order_seed=REJUDGE_ORDER_SEED, sample_seed=analysis.REJUDGE_SEED, share=analysis.REJUDGE_SHARE),
        'audit': dict(order_seed=AUDIT_ORDER_SEED, draw_seed=AUDIT_SEED, sample=AUDIT_SAMPLE,
                      drop_unresolved=DROP_UNRESOLVED_CITES),
        'guess': dict(order_seed=GUESS_SEED, b_repeat=GUESS_B_REPEAT, guesses=analysis.GUESSES)}[kind])


def build_digest(kind: str, inputs: Sequence[str]) -> str:
    """sha256 over the kind, this module's and the analysis module's own sha256 (the latter decides which units and
    re-judged items exist), the kind's seed and packing constants and the sorted digests of the inputs (the
    delivered files and the frozen probes): a change of code or seed changes every opaque id."""
    parts = [kind, file_sha256(Path(__file__)), file_sha256(Path(analysis.__file__)),
             json.dumps(_constants(kind), sort_keys=True), *sorted(inputs)]
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()


def write_batches(kind: str, out: Path, batches: list[list[dict]], *, seed: int | str, host_version: str,
                  inputs: Sequence[str], extra: dict | None = None) -> dict:
    """Write the judge files and the key. Each entry has `public` (the item minus its id) and `key`."""
    spec = KINDS[kind]
    out = _check_out(out)
    key_path = out/'keys'/f'{kind}.json'
    if key_path.exists() or any((out/'batches').glob(f'{spec["prefix"]}-*.json')):
        raise BatchError(f'{kind} batches exist under the output directory: they are written once')
    brief = frozen_brief(spec['brief'])
    build = build_digest(kind, inputs)
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


# ------------------------------------------------------------------ scoring and re-judging batches
def _frame(evidence: Path, relative: object) -> str | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    path = (evidence/relative).resolve()
    return str(path) if path.is_relative_to(evidence) and path.is_file() else None


def reobservation_entries(frozen: Frozen, delivered: dict, evidence: Path, wanted: set[tuple] | None) -> list[dict]:
    """One entry per (unit, arm, repeat) of A1, B1 and B2, or only those in `wanted` (the re-judged sample)."""
    earlier = {}
    for lineage in frozen.where:
        earlier.update({c['id']: c.get('earlier_path') for c in frozen.document(lineage, 'candidates.json')['candidates']
                        if c.get('lineage') == lineage})
    entries, missing, absent, partial = [], 0, 0, 0
    for unit in frozen.units:
        frame = _frame(evidence, earlier.get(unit['probe']))
        for arm, repeats in analysis.ARMS.items():
            for repeat in repeats:
                if wanted is not None and ('reobservation', arm, repeat, unit['probe']) not in wanted:
                    continue
                row = delivered.get((unit['lineage'], unit['boundary'], arm, repeat))
                if row is None:
                    missing += 1
                elif not row['complete']:
                    partial += 1
                elif frame is None:
                    absent += 1
                else:
                    entries.append(dict(sort=(unit['probe'], arm, repeat), unit=unit['probe'],
                                        public=dict(frame=frame, text=row['text']),
                                        key=dict(kind='reobservation', arm=arm, repeat=repeat, item=unit['probe'])))
    if missing or absent or partial:
        raise BatchError(f'cannot build the items: {missing} delivered texts missing, {partial} incomplete, '
                         f'{absent} earlier frames missing under the evidence root')
    return entries


def scoring_batches(frozen: Frozen, delivered: dict, evidence: Path, out: Path, host_version: str,
                    inputs: Sequence[str]) -> dict:
    entries = reobservation_entries(frozen, delivered, evidence, None)
    return write_batches('scoring', out, pack(entries, SCORING_SEED), seed=SCORING_SEED, host_version=host_version,
                         inputs=inputs)


def rejudge_batches(frozen: Frozen, delivered: dict, evidence: Path, out: Path, host_version: str,
                    inputs: Sequence[str]) -> dict:
    wanted = analysis.rejudge_sample(frozen.units)
    entries = reobservation_entries(frozen, delivered, evidence, wanted)
    return write_batches('rejudge', out, pack(entries, REJUDGE_ORDER_SEED), seed=REJUDGE_ORDER_SEED,
                         host_version=host_version, inputs=inputs, extra=dict(sample_seed=analysis.REJUDGE_SEED))


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
    chunks: dict[tuple, dict] = {}
    planned: set[tuple] = set()      # (lineage, boundary) of every held-out lineage, from the digest-checked plans
    for lineage in frozen.where:
        for entry in frozen.document(lineage, 'ledger-plan.json')['lineages'][lineage]['chunks']:
            chunks[(lineage, entry['chunk'])] = entry
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
            chunk = chunks.get((lineage, predecessor))
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


# ------------------------------------------------------------------ the arm-guess batch
def guess_batches(delivered: dict, out: Path, host_version: str, inputs: Sequence[str]) -> dict:
    """Owner decision, 10 November 2026: the 30 texts are every boundary of the delivered development rows given,
    once per arm (A repeat 1 and B repeat GUESS_B_REPEAT), so exactly 15 each; one Random(GUESS_SEED) shuffle
    of the sorted items; one batch. Development rows only (a held-out lineage is refused), and A and B at the same
    (lineage, boundary) set."""
    half = analysis.GUESSES // 2
    held_out = sorted({lineage for lineage, _, _, _ in delivered if lineage in analysis.HELD_OUT})
    if held_out:
        raise BatchError(f'the arm-guess check uses development rows only; held-out lineages given: {", ".join(held_out)}')
    chosen = []
    for arm, repeat in (('A', 1), ('B', GUESS_B_REPEAT)):
        rows = [row for key, row in sorted(delivered.items()) if key[2:] == (arm, repeat)]
        if len(rows) != half:
            raise BatchError(f'{arm}{repeat} has {len(rows)} delivered boundaries; the check needs exactly {half}')
        if any(not row['complete'] for row in rows):
            raise BatchError(f'delivered texts of {arm}{repeat} are incomplete')
        chosen += [(row['lineage'], row['boundary'], arm, row) for row in rows]
    where = {arm: {c[:2] for c in chosen if c[2] == arm} for arm in ('A', 'B')}
    if where['A'] != where['B']:     # both arms at the same boundaries, so the texts differ by arm and nothing else
        only_a, only_b = sorted(where['A'] - where['B']), sorted(where['B'] - where['A'])
        raise BatchError(f'A1 and B{GUESS_B_REPEAT} are not at the same boundaries ({len(only_a)} only in A1, e.g. '
                         f'{only_a[:3]}; {len(only_b)} only in B{GUESS_B_REPEAT}, e.g. {only_b[:3]})')
    chosen.sort(key=lambda c: c[:3])
    random.Random(GUESS_SEED).shuffle(chosen)
    entries = [dict(sort=n, unit=n, public=dict(text=row['text']), key=dict(arm=arm))
               for n, (_, _, arm, row) in enumerate(chosen)]
    return write_batches('guess', out, [entries], seed=GUESS_SEED, host_version=host_version, inputs=inputs,
                         extra=dict(b_repeat=GUESS_B_REPEAT))


# ------------------------------------------------------------------ parsing the judges' files
def _boolean(value: object) -> bool:
    return isinstance(value, bool)


# kind -> (the exact keys of a line, the checks of its values)
SHAPES = {
    'label': (('id', 'stated', 'why'), {'stated': _boolean, 'why': lambda v: isinstance(v, str)}),
    'audit': (('false', 'frame', 'id', 'why'), {'false': _boolean, 'why': lambda v: isinstance(v, str)}),
    'guess': (('id', 'system'), {'system': lambda v: v in ('1', '2')}),
}
SHAPE_OF = {'scoring': 'label', 'rejudge': 'label', 'audit': 'audit', 'guess': 'guess'}


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
    keys, checks = SHAPES[SHAPE_OF[kind]]
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
    # The scoring brief says "one per item in the given order"; the audit and guess briefs ask only for one line per item.
    if kind in ('scoring', 'rejudge') and list(got) != ids:
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


def parse(kind: str, run: Path, answers: Path) -> list[dict]:
    """The `p1-score/1` rows of one kind's judge output files, refusing anything not exactly as asked."""
    key = _load_key(run, kind)
    _verify_build(run, key, kind)
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
        for opaque in batch['ids']:     # the key's order, whatever order the audit or guess judge wrote
            row, item = got[opaque], key['items'][opaque]
            if kind in ('scoring', 'rejudge'):
                made = dict(type='label', schema=analysis.SCORE_SCHEMA, kind=item['kind'], arm=item['arm'],
                            repeat=item['repeat'], item=item['item'], stated=row['stated'])
                if kind == 'rejudge':
                    made['rejudge'] = True
            elif kind == 'audit':
                made = dict(type='audit', schema=analysis.SCORE_SCHEMA, arm=item['arm'], repeat=item['repeat'],
                            item=item['item'], false=row['false'], frame=row['frame'])
            else:
                made = dict(type='guess', schema=analysis.SCORE_SCHEMA, arm=item['arm'], guess=row['system'])
            rows.append(made)
    try:    # exactly the shapes the analysis accepts
        if kind in ('scoring', 'rejudge'):
            analysis.labels(rows)
        elif kind == 'audit':
            analysis._validated(rows)
        else:
            analysis.arm_guessing(rows)
    except analysis.ScoreError:
        raise BatchError(f'the {kind} rows do not satisfy the analysis\' shapes') from None
    return rows


# ------------------------------------------------------------------ command line
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='p1_analysis', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('batches', help='write the judge batches and their key')
    build.add_argument('kind', choices=tuple(KINDS))
    build.add_argument('--probes', type=Path, action='append', help='a frozen held-out p1-probes/1 file, once per directory')
    build.add_argument('--delivered', type=Path, action='append', required=True, help='a p1-delivered/2 file')
    build.add_argument('--evidence-root', type=Path, default=None)
    build.add_argument('--out', type=Path, required=True, help='a new directory under the repository\'s .runtime/')
    build.add_argument('--host-version', required=True, help='the coding host\'s version, recorded with each batch')
    read = sub.add_parser('parse', help='turn the judges\' output files into p1-score/1 rows')
    read.add_argument('kind', choices=tuple(KINDS))
    read.add_argument('--batches', type=Path, required=True, help='the --out of `batches`')
    read.add_argument('--answers', type=Path, required=True, help='the directory of <batch>.jsonl files of this kind')
    read.add_argument('--out', type=Path, required=True, help='the p1-score/1 rows file to write')
    args = parser.parse_args(argv)
    try:
        if args.command == 'parse':
            if args.out.exists():
                raise BatchError('--out exists: the rows are written once')
            rows = parse(args.kind, args.batches, args.answers)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
            print(json.dumps(dict(kind=args.kind, rows=len(rows), rows_sha256=file_sha256(args.out))))
            return 0
        _check_out(args.out)
        delivered = read_delivered(args.delivered)
        evidence = Path(args.evidence_root or _evidence_default()).resolve()
        inputs = [file_sha256(path) for path in args.delivered]
        if args.kind == 'guess':
            result = guess_batches(delivered, args.out, args.host_version, inputs)
        else:
            frozen = Frozen(args.probes or [])
            inputs += frozen.digests
            if args.kind == 'scoring':
                result = scoring_batches(frozen, delivered, evidence, args.out, args.host_version, inputs)
            elif args.kind == 'rejudge':
                result = rejudge_batches(frozen, delivered, evidence, args.out, args.host_version, inputs)
            else:
                result = audit_batches(frozen, delivered, evidence, args.out, args.host_version, inputs)
    except (BatchError, analysis.ScoreError) as error:
        print(f'p1_batches: {error}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
