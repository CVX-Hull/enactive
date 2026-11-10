"""Check blinded probe recall against independently found re-observations (probe-protocol/1; #490).

  python -m tools.probe_validation candidates [--evidence-root DIR] [--out data/evaluation/probes/validation]
  python -m tools.probe_validation recall [--out data/evaluation/probes/validation]
  python -m tools.probe_validation held-out-candidates [--evidence-root DIR] [--out data/evaluation/p1/held-out]
  python -m tools.probe_validation held-out-batches --judge-dir DIR [--evidence-root DIR] [--out ...]
  python -m tools.probe_validation held-out-probes [--out ...]
  python -m tools.probe_validation held-out-timelines --to DIR [--evidence-root DIR] [--out ...]
  python -m tools.probe_validation held-out-freeze [--out ...] [--frozen YYYY-MM-DD]

The `held-out-*` steps build #178's held-out probes and ledgers (docs/design/p1-study-2.md, "Held-out
handling"). They print only counts, digests and cluster-size tables, never a frame id, a judge's
text, a timeline, a fact or a query; the files they write may hold content. They take
`--lineages` (default lh1 lh2 lh3, read from study 372-382-dev-loop and written to
data/evaluation/p1/held-out); `--lineages lh4` reads study 522-held-out and writes
data/evaluation/p1/held-out-lh4, never the lh1-lh3 directory.

`candidates` applies the rule the protocol fixed in advance ("Recall check against independently
found re-observations"): over each development lineage's sealed frames it finds new screens after
a boundary that are near-duplicates of a frame from an earlier chunk, and draws the seeded sample
the blinded judge sees. `recall` reads the judge's verdicts and counts how many confirmed
re-observations the blinded ledger (without the adjudication layer) captured. Nothing here looks
at what a frame shows; it compares hashes and counts labels. #382's held-out lineages are refused.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import datetime
import json
import os
from pathlib import Path
import random
import re

from harness.evaluation.core.probes import Lineage, ProbeError
from harness.jsonio import file_sha256
from harness.trace.images import dhash, hamming, load
from tools import p1_analysis
from tools.probe_baseline import LINEAGES, _lines
from tools.probe_timeline import connect, write_timelines

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'probe-validation/1'
HASH_SIZE = 16           # 256-bit difference hash
NEW_SCREEN = 64          # bits from the previous frame in the same chunk
NEAR = 16                # bits to a frame of an earlier chunk
CLUSTER = 20             # frames within which one earlier match counts once
WINDOW = 15              # frame-number window for a captured event
SAMPLE = {'397': 40, '372': 20}
SEED = 490
STUDIES = {'397': '397-seven-day', '372': '372-382-dev-loop'}
HELD_OUT = ('lh1', 'lh2', 'lh3', 'lh4')

# #178's held-out probes (docs/design/p1-study-2.md). Each lineage is one group across its sessions.
HELD_OUT_RUNS = p1_analysis.HELD_OUT      # lineage -> its sessions, in order (lh4 once #178 names its admissions)
HELD_OUT_STUDY = '372-382-dev-loop'
HELD_OUT_STUDIES = {'lh1': HELD_OUT_STUDY, 'lh2': HELD_OUT_STUDY, 'lh3': HELD_OUT_STUDY, 'lh4': '522-held-out'}
DEFAULT_LINEAGES = ('lh1', 'lh2', 'lh3')  # p1-study/1's lineages: what the held-out steps do without --lineages
HELD_OUT_DIR = ROOT/'data'/'evaluation'/'p1'/'held-out'
HELD_OUT_LH4_DIR = ROOT/'data'/'evaluation'/'p1'/'held-out-lh4'
STUDY_DOC = ROOT/'docs'/'design'/'p1-study-2.md'   # its frozen briefs are p1-study/1's, word for word
CANDIDATES_SCHEMA = 'p1-held-out-candidates/1'
BATCH_SCHEMA = 'p1-held-out-batch/1'
PLAN_SCHEMA = 'p1-held-out-ledger-plan/1'
FROZEN_SCHEMA = 'p1-held-out-frozen/1'
BATCH_SIZE = 15          # pairs per confirmation batch
MAX_QUERIES = 40         # per chunk (probe-protocol/1, "Query probes")


def development() -> dict[str, list[str]]:
    """The annotated development lineages and their chunks; any held-out name is refused."""
    if any(name.startswith(HELD_OUT) or any(c.startswith(HELD_OUT) for c in chunks)
           for name, chunks in LINEAGES.items()):
        raise SystemExit('held-out lineages are never used')
    return LINEAGES


def lineage_runs() -> dict[str, list[str]]:
    """Each development lineage's runs in order: #397's admissions, then the six #372 sample runs."""
    lineages = development()
    return {'397': sorted({chunk.rsplit('-', 1)[0] for chunk in lineages['397']}),
            '372': [name for name in lineages if name != '397']}


def chunk_frames(session: Path) -> list[tuple[str, list[str]]]:
    """(actor directory, source ids in operation order) for each actor of a sealed session."""
    with connect(session/'session.sqlite3') as db:
        rows = db.execute(
            'SELECT o.id, o.actor, COALESCE(c.source, n.source) FROM operations o '
            'LEFT JOIN native_intents n ON n.operation = o.id LEFT JOIN collections c ON c.native_id = n.id '
            'ORDER BY o.created_wall').fetchall()
    order, last = [], {}
    for op_id, actor, source in rows:
        if op_id not in last:
            order.append(op_id)
            last[op_id] = (actor, source)
        elif source is not None and (last[op_id][1] is None
                                     or int(source.rsplit('-', 1)[1]) > int(last[op_id][1].rsplit('-', 1)[1])):
            last[op_id] = (actor, source)
    out = []
    for directory in sorted((session/'actors').iterdir()):
        frozen = directory/'frozen.json'
        actor_id = json.loads(frozen.read_text()).get('actor_id') if frozen.exists() else None
        sources = [last[op][1] for op in order if last[op][1] is not None and last[op][0] == actor_id]
        out.append((directory.name, list(dict.fromkeys(sources))))
    return out


def find_candidates(chunks: list[tuple[str, str, list[str]]], hashes: dict[str, int]) -> list[dict]:
    """Apply the fixed rule to (chunk name, run, frames) in lineage order."""
    candidates = []
    earlier: list[tuple[str, str]] = []   # (chunk, source) of every frame before the current chunk
    for index, (chunk, run, frames) in enumerate(chunks):
        used: dict[str, int] = {}
        for position, source in enumerate(frames):
            if index == 0 or position == 0 or source not in hashes or frames[position - 1] not in hashes:
                continue
            if hamming(hashes[source], hashes[frames[position - 1]]) < NEW_SCREEN:
                continue
            best = min(((hamming(hashes[source], hashes[s]), c, s) for c, s in earlier if s in hashes), default=None)
            if best is None or best[0] > NEAR:
                continue
            if best[2] in used and position - used[best[2]] <= CLUSTER:
                continue
            used[best[2]] = position
            candidates.append(dict(later_chunk=chunk, later=source, earlier_chunk=best[1], earlier=best[2],
                                   distance=best[0], run=run))
        earlier.extend((chunk, s) for s in frames)
    return candidates


def candidates(evidence: Path, out: Path) -> dict:
    result = dict(schema=SCHEMA, rule=dict(hash_size=HASH_SIZE, new_screen=NEW_SCREEN, near=NEAR, cluster=CLUSTER,
                                           window=WINDOW, sample=SAMPLE, seed=SEED), lineages={})
    pairs = []
    for lineage, runs in lineage_runs().items():
        study = evidence/STUDIES[lineage]/'computer-sessions'
        found = []
        groups = [runs] if lineage == '397' else [[run] for run in runs]   # #372 runs are separate lineages
        for group in groups:
            chunks, hashes = [], {}
            for run in group:
                session = study/run
                for directory, frames in chunk_frames(session):
                    chunks.append((f'{run}-{directory}', run, frames))
                    for source in frames:
                        path = session/'sources'/f'{source}.png'
                        if path.is_file():
                            hashes[source] = dhash(load(path), HASH_SIZE)
            found.extend(find_candidates(chunks, hashes))
        found.sort(key=lambda c: (c['later_chunk'], c['later']))
        sample = random.Random(SEED).sample(found, min(SAMPLE[lineage], len(found)))
        sample.sort(key=lambda c: (c['later_chunk'], c['later']))
        result['lineages'][lineage] = dict(candidates=len(found), sampled=len(sample))
        for c in sample:
            # The judge sees the two frames in a seeded order, never told which came first.
            order = random.Random(f'{SEED}:{c["later"]}').random() < 0.5
            pairs.append(dict(c, lineage=lineage, id=f'p{len(pairs) + 1:03d}',
                              shown=['earlier', 'later'] if order else ['later', 'earlier']))
    result['pairs'] = pairs
    out.mkdir(parents=True, exist_ok=True)
    (out/'candidates.json').write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    return result


def _number(source: str) -> int:
    return int(source.rsplit('-', 1)[1])


def captured(pair: dict, ledger: dict[str, list[dict]], order: list[str]) -> bool:
    """A blinded need or re-observation event near the later frame, on a fact from an earlier chunk."""
    later_index = order.index(pair['later_chunk'])
    earlier_facts = {row['id'] for chunk in order[:later_index] for row in ledger[chunk] if row['type'] == 'fact'}
    session, number = pair['later'].rsplit('-', 1)[0], _number(pair['later'])
    for row in ledger[pair['later_chunk']]:
        if (row['type'] == 'event' and row['event'] in ('rediscovered', 'needed') and row['fact'] in earlier_facts
                and isinstance(row.get('frame'), str) and row['frame'].rsplit('-', 1)[0] == session
                and abs(_number(row['frame']) - number) <= WINDOW):
            return True
    return False


def recall(out: Path) -> dict:
    data = json.loads((out/'candidates.json').read_text())
    verdicts = {row['id']: row for row in _lines(out/'judgments.jsonl')}
    probes = ROOT/'data'/'evaluation'/'probes'
    lineages = development()
    result = dict(schema=SCHEMA, kind='recall', lineages={}, pairs=[])
    totals = dict(judged=0, confirmed=0, captured=0)
    for lineage in ('397', '372'):
        rows = [p for p in data['pairs'] if p['lineage'] == lineage]
        figures = dict(judged=0, confirmed=0, captured=0)
        for pair in rows:
            verdict = verdicts.get(pair['id'])
            if verdict is None:
                continue
            figures['judged'] += 1
            if verdict['same'] is not True:
                result['pairs'].append(dict(id=pair['id'], confirmed=False))
                continue
            name = '397' if lineage == '397' else pair['run']
            order = lineages[name]
            ledger = {chunk: _lines(probes/name/f'{chunk}.jsonl') for chunk in order}
            hit = captured(pair, ledger, order)
            figures['confirmed'] += 1
            figures['captured'] += hit
            result['pairs'].append(dict(id=pair['id'], confirmed=True, captured=hit))
        figures['recall'] = round(figures['captured'] / figures['confirmed'], 3) if figures['confirmed'] else None
        result['lineages'][lineage] = figures
        for key in totals:
            totals[key] += figures[key]
    totals['recall'] = round(totals['captured'] / totals['confirmed'], 3) if totals['confirmed'] else None
    result['pooled'] = totals
    result['decision'] = None if totals['recall'] is None else (
        'fact-label protocol stands' if totals['recall'] >= 0.6 else 'switch to query-style probes')
    coverage_file = out/'query-coverage.jsonl'
    content_file = out/'fact-content.jsonl'
    if coverage_file.is_file():
        result['query_probes'] = query_figures(data, verdicts, result['pairs'], _lines(coverage_file),
                                               _lines(content_file) if content_file.is_file() else None)
    (out/'recall.json').write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    return result


# Words in the pairwise judge's note that mark a match carrying no durable information (an empty
# menu, a search prompt or a loading screen). Used only for the descriptive "informative" figures,
# which were not pre-registered; the decision uses every confirmed pair.
TRIVIAL = ('empty', '0 in category', 'loading', 'search help', 'search-help')


def query_figures(data: dict, verdicts: dict, fact_pairs: list[dict], coverage: list[dict],
                  fact_content: list[dict] | None = None) -> dict:
    """Query-probe recall (pre-registered bar 0.6) and, descriptively, the union with the fact ledger.

    The pre-registered fact rule counts any nearby need on any earlier fact, whatever it says.
    `fact_content` (post hoc, after review) holds a blinded judge's verdict on whether one of those
    nearby facts states what the earlier frame shows; with it, `fact_content` and `union_content`
    count content-matched captures, comparable with query coverage."""
    covered = {row['id']: row['covered'] is True for row in coverage}
    captured = {row['id']: row['captured'] for row in fact_pairs if row.get('confirmed')}
    lineage = {pair['id']: pair['lineage'] for pair in data['pairs']}
    trivial = {i for i in captured if any(word in verdicts[i]['what'].lower() for word in TRIVIAL)}
    if set(covered) != set(captured):
        raise SystemExit('query coverage must judge exactly the confirmed pairs')
    content = None
    if fact_content is not None:
        content = {row['id']: row['covered'] is True for row in fact_content}
        if set(content) != {i for i, hit in captured.items() if hit}:
            raise SystemExit('fact content must judge exactly the captured pairs')

    def figures(ids):
        n = len(ids)
        out = dict(confirmed=n, query=sum(covered[i] for i in ids), fact=sum(captured[i] for i in ids),
                   union=sum(covered[i] or captured[i] for i in ids),
                   query_recall=round(sum(covered[i] for i in ids) / n, 3) if n else None,
                   union_recall=round(sum(covered[i] or captured[i] for i in ids) / n, 3) if n else None)
        if content is not None:
            matched = sum(content.get(i, False) for i in ids)
            either = sum(covered[i] or content.get(i, False) for i in ids)
            out.update(fact_content=matched, union_content=either,
                       union_content_recall=round(either / n, 3) if n else None)
        return out

    ids = sorted(captured)
    pooled = figures(ids)
    return dict(lineages={name: figures([i for i in ids if lineage[i] == name]) for name in ('397', '372')},
                pooled=pooled, informative=figures([i for i in ids if i not in trivial]), trivial=sorted(trivial),
                decision='query probes adopted' if pooled['query_recall'] >= 0.6 else
                'below the bar: the probe design went back to the owner')


LEDGER_SCHEMA = 'probe-ledger/1'


def freeze(probes: Path) -> dict:
    """Both blinded ledgers, frozen by digest for P1's secondary figures (owner decision, 8 November 2026).

    Per development lineage: the fact-label chunks with the unblinded adjudication layer kept as a
    separate file, and the query probes of every chunk that precedes a boundary. P1's primary
    probes are confirmed re-observations; nothing here may change after P1's pre-registration."""
    lineages = {}
    for name, chunks in development().items():
        group = '397' if name == '397' else '372'
        facts = {chunk: file_sha256(probes/name/f'{chunk}.jsonl') for chunk in chunks}
        adjudication = probes/name/'adjudication.jsonl'
        queries = {path.stem: file_sha256(path) for path in sorted((probes/'queries'/group).glob('*.jsonl'))
                   if path.stem in chunks}
        if set(queries) != set(chunks[:-1]):
            raise SystemExit(f'{name}: query files must be exactly the chunks before a boundary; '
                             f'have {sorted(queries)}, want {chunks[:-1]}')
        lineages[name] = dict(fact_chunks=facts, queries=queries,
                              adjudication=file_sha256(adjudication) if adjudication.is_file() else None)
    ledger = dict(schema=LEDGER_SCHEMA, protocol='probe-protocol/1', frozen='2026-11-08', lineages=lineages,
                  note='Both blinded ledgers, frozen for P1\'s secondary, descriptive figures (owner decision, '
                       '#490). Each missed the 0.6 recall bar; P1\'s primary probes are confirmed '
                       're-observations. See docs/design/probe-protocol.md.')
    (probes/'ledger.json').write_text(json.dumps(ledger, indent=1, sort_keys=True) + '\n')
    return ledger


# ---------------------------------------------------------------------------------------------
# Held-out probes and ledgers (#178). Nothing below prints a frame id, a judge's text, a timeline,
# a fact or a query; error messages name files, chunks and line numbers only.


def _dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def _jsonl(path: Path) -> list[dict]:
    """Parse a JSON Lines file whose every line is an object; errors name the file and line only."""
    rows = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise SystemExit(f'{path.name}:{number}: not JSON') from None
        if not isinstance(row, dict):
            raise SystemExit(f'{path.name}:{number}: not a JSON object')
        rows.append(row)
    return rows


def held_out_lineages(names: Sequence[str] | None = None) -> list[str]:
    """The held-out lineages a step covers: `names` (a subset of the known held-out lineages, no repeats) or
    lh1-lh3. lh4 is known only once #178 has filled `p1_analysis.LH4_ADMISSIONS`."""
    if names is None:
        return [name for name in HELD_OUT_RUNS if name in DEFAULT_LINEAGES]
    names = list(names)
    for name in names:
        if name not in HELD_OUT_RUNS:
            raise SystemExit(f'{name}: not a held-out lineage with admissions (known: {", ".join(HELD_OUT_RUNS)})'
                             if name in HELD_OUT_STUDIES else f'{name}: not a held-out lineage')
    if not names or len(set(names)) != len(names):
        raise SystemExit('name each held-out lineage once')
    return names


def held_out_output(lineages: Sequence[str], out: Path | None) -> Path:
    """Where a held-out step reads and writes: lh1-lh3's directory as before, lh4's own directory, never lh4
    in lh1-lh3's, and no default for a mix."""
    lh4 = 'lh4' in lineages
    if out is None:
        if lh4 and len(lineages) > 1:
            raise SystemExit('lh4 is kept apart from lh1-lh3: name --out to mix them, or run them separately')
        return HELD_OUT_LH4_DIR if lh4 else HELD_OUT_DIR
    if lh4 and Path(out).resolve() == HELD_OUT_DIR.resolve():
        raise SystemExit(f'lh4 never goes in {HELD_OUT_DIR.name}/; use {HELD_OUT_LH4_DIR.name}/')
    if Path(out).resolve() == HELD_OUT_LH4_DIR.resolve() and list(lineages) != ['lh4']:
        raise SystemExit(f'{HELD_OUT_LH4_DIR.name}/ holds lh4 only; run it with --lineages lh4')
    return Path(out)


def _held_out_chunks(evidence: Path, runs: tuple[str, ...], lineage: str) -> tuple[list, dict[str, int], dict[str, Path]]:
    """(chunk, run, frames) in session then actor-directory order, every frame's hash and its path."""
    study = evidence/HELD_OUT_STUDIES[lineage]/'computer-sessions'
    chunks, hashes, paths = [], {}, {}
    for run in runs:
        session = study/run
        if not session.is_dir():
            raise SystemExit(f'Missing session: {run}')
        for directory, frames in chunk_frames(session):
            chunks.append((f'{run}-{directory}', run, frames))
            for source in frames:
                path = session/'sources'/f'{source}.png'
                if path.is_file():
                    paths[source] = path
                    hashes[source] = dhash(load(path), HASH_SIZE)
    return chunks, hashes, paths


def held_out_candidates(evidence: Path, out: Path, names: Sequence[str] | None = None) -> dict:
    """Every candidate of protocol steps 1-4 over each held-out lineage; no sampling (#178)."""
    target = out/'candidates.json'
    if target.exists():
        raise SystemExit('candidates.json exists: the held-out candidates are computed once')
    evidence = Path(evidence).resolve()
    lineages, rows = {}, []
    for lineage in held_out_lineages(names):
        runs = HELD_OUT_RUNS[lineage]
        chunks, hashes, paths = _held_out_chunks(evidence, runs, lineage)
        names = [chunk[0] for chunk in chunks]
        before = dict(zip(names[1:], names))
        found = find_candidates(chunks, hashes)
        found.sort(key=lambda c: (c['later_chunk'], c['later']))
        if len(found) >= 10000:
            raise SystemExit(f'{lineage}: too many candidates for four-digit ids')
        for number, c in enumerate(found, 1):
            # The judge sees the two frames in a seeded order, never told which came first (#490).
            order = random.Random(f'{SEED}:{c["later"]}').random() < 0.5
            rows.append(dict(id=f'{lineage}-p{number:04d}', lineage=lineage,
                             boundary=f'{before[c["later_chunk"]]}>{c["later_chunk"]}',
                             later=c['later'], earlier=c['earlier'], later_chunk=c['later_chunk'],
                             earlier_chunk=c['earlier_chunk'], distance=c['distance'],
                             earlier_dhash=f'{hashes[c["earlier"]]:0{HASH_SIZE * HASH_SIZE // 4}x}',
                             earlier_path=paths[c['earlier']].relative_to(evidence).as_posix(),
                             later_path=paths[c['later']].relative_to(evidence).as_posix(),
                             shown=['earlier', 'later'] if order else ['later', 'earlier']))
        lineages[lineage] = dict(runs=list(runs), chunks=names, candidates=len(found))
    result = dict(schema=CANDIDATES_SCHEMA, protocol='probe-protocol/1', lineages=lineages, candidates=rows,
                  rule=dict(hash_size=HASH_SIZE, new_screen=NEW_SCREEN, near=NEAR, cluster=CLUSTER, seed=SEED))
    _dump(target, result)
    return result


def _load_candidates(out: Path) -> dict:
    path = out/'candidates.json'
    if not path.is_file():
        raise SystemExit('Missing candidates.json: run held-out-candidates first')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != CANDIDATES_SCHEMA:
        raise SystemExit(f'candidates.json is not {CANDIDATES_SCHEMA}')
    ids = [row['id'] for row in data['candidates']]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        raise SystemExit('candidates.json ids must be unique and in id order')
    return data


CONFIRMATION_LABEL = '**Confirmation.** '


def confirmation_brief(doc: Path = STUDY_DOC) -> str:
    """The pre-registration's frozen Confirmation brief: the quote lines from `> **Confirmation.**` to the
    next blank line, joined by single spaces, without the leading label (the brief begins "You compare")."""
    lines = doc.read_text(encoding='utf-8').splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith('> **Confirmation.**')), None)
    if start is None:
        raise SystemExit(f'The Confirmation brief was not found in {doc.name}')
    quote = []
    for line in lines[start:]:
        if not line.startswith('>') or not line[1:].strip():
            break
        quote.append(line[1:].strip())
    brief = ' '.join(quote)
    return brief.removeprefix(CONFIRMATION_LABEL)


def _check_judge_dir(judge_dir: Path) -> Path:
    """The judge copies hold absolute paths, so they stay out of the repository's tracked tree: the directory
    must be outside the repository or under its `.runtime/`."""
    resolved = Path(judge_dir).resolve()
    root = ROOT.resolve()
    if resolved.is_relative_to(root) and not resolved.is_relative_to(root/'.runtime'):
        raise SystemExit('the judge directory holds absolute paths: it must be outside the repository or under .runtime/')
    return resolved


def held_out_batches(out: Path, evidence: Path, judge_dir: Path, doc: Path = STUDY_DOC) -> dict[str, int]:
    """Confirmation batch files of at most BATCH_SIZE pairs, in id order, with the frozen brief.

    The tracked batches in `out` name frames relative to the evidence root. The judge copies in `judge_dir`
    hold the same ids, brief and pair order with absolute paths."""
    judge_dir = _check_judge_dir(judge_dir)
    evidence = Path(evidence).resolve()
    brief = confirmation_brief(doc)
    rows = _load_candidates(out)['candidates']
    directory = out/'batches'
    if any(directory.glob('confirm-*.json')):
        raise SystemExit('batches exist: the confirmation batches are written once')
    for row in rows:
        for key in ('earlier_path', 'later_path'):
            if Path(row[key]).is_absolute() or not (evidence/row[key]).is_file():
                raise SystemExit(f'{row["lineage"]}: a candidate frame is missing under the evidence root, '
                                 f'or its stored path is absolute')
    count = 0
    for start in range(0, len(rows), BATCH_SIZE):
        count += 1
        pairs = [dict(id=row['id'], A=row[f'{row["shown"][0]}_path'], B=row[f'{row["shown"][1]}_path'])
                 for row in rows[start:start + BATCH_SIZE]]
        name = f'confirm-{count:03d}.json'
        _dump(directory/name, dict(schema=BATCH_SCHEMA, brief=brief, pairs=pairs))
        _dump(judge_dir/name, dict(schema=BATCH_SCHEMA, brief=brief, pairs=[
            dict(id=p['id'], A=str(evidence/p['A']), B=str(evidence/p['B'])) for p in pairs]))
    return dict(candidates=len(rows), batches=count)


def _batch_files(out: Path) -> list[Path]:
    return sorted((out/'batches').glob('confirm-*.json'))


def derive_probes(out: Path) -> list[dict]:
    """One `p1-probes/1` row per candidate from the judges' files, refusing anything incomplete."""
    candidates = _load_candidates(out)['candidates']
    by_id = {row['id']: row for row in candidates}
    batches = _batch_files(out)
    if not batches:
        raise SystemExit('No batches: run held-out-batches first')
    judged: dict[str, dict] = {}
    batched: list[str] = []
    for path in batches:
        batch = json.loads(path.read_text(encoding='utf-8'))
        if batch.get('schema') != BATCH_SCHEMA:
            raise SystemExit(f'{path.name}: not {BATCH_SCHEMA}')
        wanted = [pair['id'] for pair in batch['pairs']]
        batched += wanted
        verdicts = out/'judgments'/f'{path.stem}.jsonl'
        if not verdicts.is_file():
            raise SystemExit(f'{path.stem}: the batch has no judgments file')
        got = []
        for number, row in enumerate(_jsonl(verdicts), 1):
            where = f'{verdicts.name}: row {number}'
            if not isinstance(row.get('id'), str) or row['id'] not in by_id or row['id'] not in wanted:
                raise SystemExit(f'{where}: unknown id')
            if row['id'] in judged or row['id'] in got:
                raise SystemExit(f'{where}: duplicated id')
            if not (isinstance(row.get('same'), bool) and isinstance(row.get('informative'), bool)):
                raise SystemExit(f'{where}: same and informative must be booleans')
            if not isinstance(row.get('what'), str):
                raise SystemExit(f'{where}: what must be a string')
            got.append(row['id'])
            judged[row['id']] = row
        if len(got) != len(wanted):
            raise SystemExit(f'{verdicts.name}: missing ids ({len(wanted) - len(got)})')
        if got != wanted:
            raise SystemExit(f'{verdicts.name}: not in batch order')
    stray = {p.name for p in (out/'judgments').glob('*') if p.is_file()} - {f'{b.stem}.jsonl' for b in batches}
    if stray:
        raise SystemExit(f'judgments without a batch: {sorted(stray)}')
    if batched != list(by_id):
        raise SystemExit('the batches do not cover every candidate exactly once, in id order')
    return [dict(schema=p1_analysis.PROBES_SCHEMA, id=i, lineage=by_id[i]['lineage'],
                 boundary=by_id[i]['boundary'], later=by_id[i]['later'], earlier=by_id[i]['earlier'],
                 earlier_dhash=by_id[i]['earlier_dhash'], confirmed=judged[i]['same'],
                 informative=judged[i]['same'] and judged[i]['informative'], what=judged[i]['what'])
            for i in by_id]


def _render(rows: list[dict]) -> str:
    return ''.join(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n' for row in rows)


def held_out_probes(out: Path, names: Sequence[str] | None = None) -> dict:
    """Write `probes.jsonl`; report counts, units, clusters and the file's digest."""
    lineages = held_out_lineages(names)
    rows = derive_probes(out)
    (out/'probes.jsonl').write_text(_render(rows), encoding='utf-8')
    try:
        primary = p1_analysis.primary_probes(rows)
    except p1_analysis.ScoreError:
        raise SystemExit('probes.jsonl does not satisfy p1-probes/1') from None
    unit_rows = p1_analysis.units(primary)
    figures = {name: dict(candidates=sum(r['lineage'] == name for r in rows),
                          confirmed=sum(r['lineage'] == name and r['confirmed'] for r in rows),
                          primary=sum(r['lineage'] == name for r in primary),
                          units=sum(u['lineage'] == name for u in unit_rows)) for name in lineages}
    return dict(lineages=figures, units=len(unit_rows),
                clusters=len({(u['lineage'], u['cluster']) for u in unit_rows}),
                cluster_sizes=p1_analysis.cluster_sizes(unit_rows),
                probes_sha256=file_sha256(out/'probes.jsonl'))


_OPERATION_ROW = re.compile(r'^\| \d+ \|.* \| (yes|no|) \| ([^|]*) \|$')


def required_frames(timeline: str) -> list[str]:
    """Source ids the frame-coverage rule requires for one chunk, read from its generated timeline: every
    third changed frame from the chunk's first and every frame of its last five operations. Where the
    timeline has no change flags, every third frame."""
    if '\n## Operations\n' not in timeline:
        raise SystemExit('a timeline has no Operations section')
    section = timeline.split('\n## Operations\n', 1)[1].split('\n## ', 1)[0]
    rows = []
    for line in section.splitlines():
        match = _OPERATION_ROW.match(line)
        if match:
            rows.append((match.group(1), Path(match.group(2).strip()).stem if match.group(2).strip() else None))
    flagged = any(flag for flag, _ in rows)
    framed = [(flag, source) for flag, source in rows if source]
    changed = [source for flag, source in framed if flag == 'yes'] if flagged else [source for _, source in framed]
    last_five = [source for _, source in rows[-5:] if source]
    return list(dict.fromkeys(changed[::3] + last_five))


def _evaluation_store(study: Path, session: Path) -> Path | None:
    manifest = session/'manifest.json'
    if not manifest.is_file():
        raise SystemExit(f'Missing manifest: {session.name}')
    root = study/'evaluations'/str(json.loads(manifest.read_text(encoding='utf-8')).get('session'))
    found = sorted(root.glob('*.sqlite3')) if root.is_dir() else []
    if len(found) > 1:
        raise SystemExit(f'{session.name}: more than one evaluation store')
    return found[0] if found else None


def held_out_timelines(evidence: Path, to: Path, out: Path, names: Sequence[str] | None = None) -> dict:
    """Annotation timelines for every held-out chunk and `ledger-plan.json` (chunks to annotate, chunks that
    get a query writer, required frames)."""
    to = Path(to).resolve()
    lineages = {}
    for lineage in held_out_lineages(names):
        runs = HELD_OUT_RUNS[lineage]
        study = Path(evidence).resolve()/HELD_OUT_STUDIES[lineage]
        memory = study/f'player-memory-{lineage}.sqlite3'
        chunks = []
        for run in runs:
            session = study/'computer-sessions'/run
            if not session.is_dir():
                raise SystemExit(f'Missing session: {run}')
            for path in write_timelines(session, _evaluation_store(study, session), memory, to):
                chunks.append((path.stem, path))
        names = [name for name, _ in chunks]
        details = []
        for index, (name, path) in enumerate(chunks):
            frames = required_frames(path.read_text(encoding='utf-8'))
            details.append(dict(chunk=name, timeline=path.name, required_frames=frames,
                                incoming_boundary=f'{names[index - 1]}>{name}' if index else None))
        lineages[lineage] = dict(annotate=names, queries=names[:-1], chunks=details)
    known = out/'candidates.json'
    if known.is_file() and {k: v['chunks'] for k, v in json.loads(known.read_text(encoding='utf-8'))['lineages'].items()} \
            != {k: v['annotate'] for k, v in lineages.items()}:
        raise SystemExit('the timelines\' chunks differ from candidates.json')
    _dump(out/'ledger-plan.json', dict(schema=PLAN_SCHEMA, protocol='probe-protocol/1', lineages=lineages))
    return {name: dict(annotate=len(v['annotate']), queries=len(v['queries']),
                       required_frames=sum(len(c['required_frames']) for c in v['chunks']))
            for name, v in lineages.items()}


def _check_ledgers(out: Path, plan: dict) -> dict[str, str]:
    """Every chunk annotated and valid for its lineage, ending with `frames_viewed`; query files exactly
    the chunks before a boundary. Returns relative path -> sha256 of the ledger and query files."""
    wanted_ledgers = {f'ledgers/{lineage}/{c["chunk"]}.jsonl' for lineage, v in plan['lineages'].items()
                      for c in v['chunks']}
    wanted_queries = {f'queries/{lineage}/{chunk}.jsonl' for lineage, v in plan['lineages'].items()
                      for chunk in v['queries']}
    for kind, wanted in (('ledgers', wanted_ledgers), ('queries', wanted_queries)):
        have = {p.relative_to(out).as_posix() for p in (out/kind).glob('*/*.jsonl')}
        if have != wanted:
            raise SystemExit(f'{kind}: {len(wanted - have)} missing, {len(have - wanted)} unexpected '
                             f'(first missing {sorted(wanted - have)[:3]})')
    files: dict[str, str] = {}
    for lineage, value in plan['lineages'].items():
        required = {c['chunk']: len(c['required_frames']) for c in value['chunks']}
        ordered = [(c['chunk'], _jsonl(out/'ledgers'/lineage/f'{c["chunk"]}.jsonl')) for c in value['chunks']]
        try:
            parsed = Lineage.from_lines(ordered)
        except ProbeError as error:
            raise SystemExit(f'{lineage}: annotation does not validate: {error}') from None
        for chunk in parsed.chunks:
            viewed = chunk.frames_viewed
            if isinstance(viewed, bool) or not isinstance(viewed, int) or viewed < required[chunk.name]:
                raise SystemExit(f'{chunk.name}: frames_viewed is below the {required[chunk.name]} frames the '
                                 f'coverage rule requires')
        if any(row['unlabelled'] for row in parsed.boundary_rows()):
            raise SystemExit(f'{lineage}: a boundary has live facts without a carry line')
        for chunk in value['annotate']:
            files[f'ledgers/{lineage}/{chunk}.jsonl'] = file_sha256(out/'ledgers'/lineage/f'{chunk}.jsonl')
        for chunk in value['queries']:
            relative = f'queries/{lineage}/{chunk}.jsonl'
            lines = _jsonl(out/relative)
            *queries, end = lines or [{}]
            if end.get('type') != 'end' or isinstance(end.get('frames_viewed'), bool) \
                    or not isinstance(end.get('frames_viewed'), int) or end['frames_viewed'] < required[chunk]:
                raise SystemExit(f'{relative}: must end with frames_viewed covering the {required[chunk]} '
                                 f'required frames')
            if len(queries) > MAX_QUERIES:
                raise SystemExit(f'{relative}: more than {MAX_QUERIES} queries')
            if len({q.get('id') for q in queries}) != len(queries) or not all(
                    q.get('type') == 'query' and all(isinstance(q.get(k), str) and q[k]
                                                     for k in ('id', 'question', 'answer', 'frame', 'category'))
                    for q in queries):
                raise SystemExit(f'{relative}: query lines need a unique id, question, answer, frame and category')
            files[relative] = file_sha256(out/relative)
    return files


def held_out_freeze(out: Path, frozen: str) -> dict:
    """Digest everything the held-out replay must not change: `frozen.json` (refused if anything is missing)."""
    target = out/'frozen.json'
    if target.exists():
        raise SystemExit('frozen.json exists: the held-out files are frozen once')
    for name in ('candidates.json', 'ledger-plan.json', 'probes.jsonl'):
        if not (out/name).is_file():
            raise SystemExit(f'Missing {name}')
    plan = json.loads((out/'ledger-plan.json').read_text(encoding='utf-8'))
    if plan.get('schema') != PLAN_SCHEMA:
        raise SystemExit(f'ledger-plan.json is not {PLAN_SCHEMA}')
    known = _load_candidates(out)['lineages']
    if {k: v['chunks'] for k, v in known.items()} != {k: [c['chunk'] for c in v['chunks']]
                                                       for k, v in plan['lineages'].items()}:
        raise SystemExit('ledger-plan.json and candidates.json name different chunks')
    if (out/'probes.jsonl').read_text(encoding='utf-8') != _render(derive_probes(out)):
        raise SystemExit('probes.jsonl does not match the batches and judgments')
    files = _check_ledgers(out, plan)
    for pattern in ('batches/confirm-*.json', 'judgments/confirm-*.jsonl'):
        files.update({p.relative_to(out).as_posix(): file_sha256(p) for p in sorted(out.glob(pattern))})
    for name in ('candidates.json', 'ledger-plan.json', 'probes.jsonl'):
        files[name] = file_sha256(out/name)
    document = dict(schema=FROZEN_SCHEMA, protocol='probe-protocol/1', frozen=frozen, files=dict(sorted(files.items())))
    _dump(target, document)
    return dict(frozen_sha256=file_sha256(target), files=len(files),
                batches=len(_batch_files(out)),
                ledgers=sum(k.startswith('ledgers/') for k in files),
                queries=sum(k.startswith('queries/') for k in files))


HELD_OUT_STEPS = ('held-out-candidates', 'held-out-batches', 'held-out-probes', 'held-out-timelines', 'held-out-freeze')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=('candidates', 'recall', 'freeze', *HELD_OUT_STEPS))
    parser.add_argument('--evidence-root', type=Path,
                        default=Path(os.environ.get('ENACTIVE_EVIDENCE_ROOT', ROOT/'.runtime'/'evidence')))
    parser.add_argument('--out', type=Path, default=None,
                        help='default data/evaluation/probes/validation, or data/evaluation/p1/held-out for held-out '
                             'steps (held-out-lh4 with --lineages lh4)')
    parser.add_argument('--to', type=Path, help='held-out-timelines: the directory for the annotation timelines')
    parser.add_argument('--judge-dir', type=Path,
                        help='held-out-batches: where the judge copies with absolute frame paths go '
                             '(outside the repository or under .runtime/)')
    parser.add_argument('--frozen', default=None, help='held-out-freeze: the freeze date (default today)')
    parser.add_argument('--lineages', nargs='+', default=None,
                        help='held-out steps: the held-out lineages to cover (default lh1 lh2 lh3; lh4 reads '
                             'study 522-held-out and defaults its output to data/evaluation/p1/held-out-lh4)')
    args = parser.parse_args(argv)
    if args.step in HELD_OUT_STEPS:
        names = held_out_lineages(args.lineages)
        out = held_out_output(names, args.out)
        if args.step == 'held-out-candidates':
            result = held_out_candidates(args.evidence_root, out, names)
            print(json.dumps({k: dict(chunks=len(v['chunks']), candidates=v['candidates'])
                              for k, v in result['lineages'].items()}))
        elif args.step == 'held-out-batches':
            if not args.judge_dir:
                parser.error('held-out-batches needs --judge-dir')
            print(json.dumps(held_out_batches(out, args.evidence_root, args.judge_dir)))
        elif args.step == 'held-out-probes':
            print(json.dumps(held_out_probes(out, names)))
        elif args.step == 'held-out-timelines':
            if not args.to:
                parser.error('held-out-timelines needs --to')
            print(json.dumps(held_out_timelines(args.evidence_root, args.to, out, names)))
        else:
            print(json.dumps(held_out_freeze(out, args.frozen or datetime.date.today().isoformat())))
        return 0
    args.out = args.out or ROOT/'data'/'evaluation'/'probes'/'validation'
    if args.step == 'candidates':
        result = candidates(args.evidence_root, args.out)
        print(json.dumps(result['lineages']))
    elif args.step == 'freeze':
        ledger = freeze(args.out.parent)
        print(json.dumps({name: dict(facts=len(v['fact_chunks']), queries=len(v['queries']))
                          for name, v in ledger['lineages'].items()}))
    else:
        result = recall(args.out)
        print(json.dumps(dict(lineages=result['lineages'], pooled=result['pooled'], decision=result['decision'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
