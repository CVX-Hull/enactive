"""Baseline probe figures from the tracked annotations (probe-protocol/1; #449).

  python -m tools.probe_baseline [--probes data/evaluation/probes] [--out data/evaluation/probes/baseline.json]

For each annotated lineage it derives probes, carry rates per boundary kind, rediscoveries per
in-play game hour (from the tracked run ledger), frames viewed and annotation cost. For #397 it
reports the blinded annotation and, separately, the annotation plus the lead's unblinded
adjudication of the four known episodes. It also computes the inter-rater agreement on the
seeded sample. Nothing here judges a fact; it only counts labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.evaluation.core.probes import NEED, Lineage, ProbeError, agreement, summary

ROOT = Path(__file__).resolve().parents[1]
LINEAGES = {'397': [f'sd1a{n}-{a}' for n in range(1, 8) for a in ('001', '002')]}
for _run in ('aidB3', 'ceil09', 'ceil07', 'ceil05', 'aidB9', 'aidA5'):
    LINEAGES[_run] = [f'{_run}-001', f'{_run}-002']
RUNS = {'397': [f'sd1a{n}' for n in range(1, 8)], **{run: [run] for run in LINEAGES if run != '397'}}
INTER_RATER = ('sd1a3-001', 'sd1a7-002', 'sd1a2-001')  # random.Random(4492).sample of the #397 order


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _lineage(probes: Path, name: str, adjudicated: bool = False) -> Lineage:
    extra = _lines(probes/name/'adjudication.jsonl') if adjudicated and (probes/name/'adjudication.jsonl').is_file() else []
    unmatched = sorted({row.get('chunk') for row in extra} - set(LINEAGES[name]), key=str)
    if unmatched:
        raise ProbeError(f'{name}: adjudication rows name no chunk of the lineage: {unmatched}')
    ordered = []
    for chunk in LINEAGES[name]:
        lines = _lines(probes/name/f'{chunk}.jsonl')
        added = [{k: v for k, v in row.items() if k != 'chunk'} for row in extra if row['chunk'] == chunk]
        ordered.append((chunk, lines[:-1] + added + lines[-1:]))
    return Lineage.from_lines(ordered)


def _hours() -> dict[str, float]:
    rows = [json.loads(line) for line in (ROOT/'data'/'evaluation'/'run-metrics.jsonl').read_text().splitlines()]
    # A run that never reached play (an infrastructure loss) has no game hours.
    return {row['run']: row['metrics']['survival.game_hours']['hours'] for row in rows
            if row['metrics'].get('survival.game_hours')}


def _costs(probes: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in _lines(probes/'annotation-costs.jsonl'):
        lineage = '397' if row['chunk'].startswith('sd1a') else row['chunk'].split('-')[0]
        entry = out.setdefault(f"{lineage}:{row['rater']}", dict(chunks=0, tokens=0, unrecorded_attempts=0,
                                                                  seconds=0.0, deviations=0))
        if row['tokens'] is None:
            entry['unrecorded_attempts'] += 1
            continue
        entry['chunks'] += 1
        entry['tokens'] += row['tokens']
        entry['seconds'] += row['ms'] / 1000
        entry['deviations'] += row['deviation'] not in (None, 'retry after the interrupted attempt')
    return out


def _inter_rater(probes: Path) -> list[dict]:
    rows = []
    for chunk in INTER_RATER:
        path_b = probes/'397'/f'{chunk}.B.jsonl'
        if not path_b.is_file():
            rows.append(dict(chunk=chunk, missing=True))
            continue
        a, b = _lines(probes/'397'/f'{chunk}.jsonl'), _lines(path_b)
        ca = {r['fact']: r['carried'] for r in a if r['type'] == 'carry'}
        cb = {r['fact']: r['carried'] for r in b if r['type'] == 'carry'}
        shared = sorted(set(ca) & set(cb), key=lambda f: int(f[1:]))
        na = {r['fact'] for r in a if r['type'] == 'event' and r['event'] in NEED and r['fact'] in ca}
        nb = {r['fact'] for r in b if r['type'] == 'event' and r['event'] in NEED and r['fact'] in cb}
        rows.append(dict(chunk=chunk, carry=agreement([(ca[f], cb[f]) for f in shared]),
                         needed=agreement([(f in na, f in nb) for f in shared]),
                         new_facts=dict(A=sum(r['type'] == 'fact' for r in a), B=sum(r['type'] == 'fact' for r in b))))
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--probes', type=Path, default=ROOT/'data'/'evaluation'/'probes')
    parser.add_argument('--out', type=Path, default=ROOT/'data'/'evaluation'/'probes'/'baseline.json')
    args = parser.parse_args(argv)
    hours = _hours()
    lineages = []
    for name in LINEAGES:
        game_hours = round(sum(hours[run] for run in RUNS[name]), 3)
        lineages.append(dict(summary(name, _lineage(args.probes, name), game_hours), annotation='blinded'))
        if (args.probes/name/'adjudication.jsonl').is_file():
            lineages.append(dict(summary(name, _lineage(args.probes, name, True), game_hours),
                                 annotation='blinded plus unblinded adjudication of the four known episodes'))
    result = dict(schema='probe-baseline-set/1', protocol='probe-protocol/1', lineages=lineages,
                  inter_rater=_inter_rater(args.probes), annotation_costs=_costs(args.probes))
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    for row in lineages:
        label = 'blinded' if row['annotation'] == 'blinded' else 'adjudicated'
        print(f"{row['lineage']:7s} {label:11s} probes {row['probes']['total']:3d} failing "
              f"{row['probes']['failing']:3d} carry {row['carry']['pooled']['carry_rate']:.2f} "
              f"retention {row['carry']['pooled']['retention_rate']:.2f} "
              f"rediscovery/h {row['rediscoveries_per_game_hour']:.2f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
