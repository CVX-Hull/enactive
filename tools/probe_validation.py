"""Check blinded probe recall against independently found re-observations (probe-protocol/1; #490).

  python -m tools.probe_validation candidates [--evidence-root DIR] [--out data/evaluation/probes/validation]
  python -m tools.probe_validation recall [--out data/evaluation/probes/validation]

`candidates` applies the rule the protocol fixed in advance ("Recall check against independently
found re-observations"): over each development lineage's sealed frames it finds new screens after
a boundary that are near-duplicates of a frame from an earlier chunk, and draws the seeded sample
the blinded judge sees. `recall` reads the judge's verdicts and counts how many confirmed
re-observations the blinded ledger (without the adjudication layer) captured. Nothing here looks
at what a frame shows; it compares hashes and counts labels. #382's held-out lineages are refused.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random

from harness.trace.images import dhash, hamming, load
from tools.probe_baseline import LINEAGES, _lines
from tools.probe_timeline import connect

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
HELD_OUT = ('lh1', 'lh2', 'lh3')


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
    import hashlib

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    lineages = {}
    for name, chunks in development().items():
        group = '397' if name == '397' else '372'
        facts = {chunk: digest(probes/name/f'{chunk}.jsonl') for chunk in chunks}
        adjudication = probes/name/'adjudication.jsonl'
        queries = {path.stem: digest(path) for path in sorted((probes/'queries'/group).glob('*.jsonl'))
                   if path.stem in chunks}
        if set(queries) != set(chunks[:-1]):
            raise SystemExit(f'{name}: query files must be exactly the chunks before a boundary; '
                             f'have {sorted(queries)}, want {chunks[:-1]}')
        lineages[name] = dict(fact_chunks=facts, queries=queries,
                              adjudication=digest(adjudication) if adjudication.is_file() else None)
    ledger = dict(schema=LEDGER_SCHEMA, protocol='probe-protocol/1', frozen='2026-11-08', lineages=lineages,
                  note='Both blinded ledgers, frozen for P1\'s secondary, descriptive figures (owner decision, '
                       '#490). Each missed the 0.6 recall bar; P1\'s primary probes are confirmed '
                       're-observations. See docs/design/probe-protocol.md.')
    (probes/'ledger.json').write_text(json.dumps(ledger, indent=1, sort_keys=True) + '\n')
    return ledger


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=('candidates', 'recall', 'freeze'))
    parser.add_argument('--evidence-root', type=Path,
                        default=Path(os.environ.get('ENACTIVE_EVIDENCE_ROOT', ROOT/'.runtime'/'evidence')))
    parser.add_argument('--out', type=Path, default=ROOT/'data'/'evaluation'/'probes'/'validation')
    args = parser.parse_args(argv)
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
