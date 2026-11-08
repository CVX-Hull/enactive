"""The P1 offline study's frozen analysis (ADR 009; pre-registration in docs/design/p1-study.md, #491).

  python -m tools.p1_analysis simulate [--out data/evaluation/p1/power.json]
  python -m tools.p1_analysis score --probes <p1-probes/1> --scores <p1-score/1> --hours <JSON> [--out ...]

`simulate` checks before any spend that the decision rule detects the effect of interest and
rarely fires without one. Its inputs are development data and aggregates only: #397's sampled
re-observation candidates and needed-fact carry rates (#449, #490), and each held-out lineage's game
hours from the tracked run ledger.

`score` computes every pre-registered figure and the decision from the confirmed re-observation
probes, the blinded judges' labels, the false-fact audit and the settled costs. It refuses an
incomplete study: every primary probe must be judged for every arm and repeat. Nothing here
judges text; it only counts labels.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROBES_SCHEMA = 'p1-probes/1'
SCORE_SCHEMA = 'p1-score/1'
RESULT_SCHEMA = 'p1-result/1'
POWER_SCHEMA = 'p1-power/1'
SEED = 491

# Pre-registered decision rule (docs/design/p1-study.md#decision-rule). Changing one is a deviation.
EFFECT = 0.15            # pooled re-observation recall, B minus A, in every curator repeat
MIN_PROBES = 20          # a lineage with at least this many primary probes must show B above A
BOOTSTRAP = 2000         # boundary resamples within lineage
LOWER_QUANTILE = 0.05    # the one-sided 95% bound of the pooled difference must exceed 0
FALSE_FACT_CAP = 0.10    # B's audited false-fact rate, and at most A's plus the margin
FALSE_FACT_MARGIN = 0.05
COST_CAP = 1.0           # curator settled dollars over actor dollars, per repeat
ARMS = {'A': (1,), 'B': (1, 2)}
HELD_OUT = {'lh1': ('lh1a1', 'lh1a2', 'lh1a3'), 'lh2': ('lh2a1', 'lh2a2'), 'lh3': ('lh3a1', 'lh3a2')}
KINDS = ('reobservation', 'fact', 'query')   # primary, then the two descriptive ledgers


class ScoreError(ValueError):
    """The labels do not cover the study, or a row does not follow its schema."""


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _rate(numerator: float, denominator: float) -> float | None:
    return None if not denominator else numerator / denominator


# ---------------------------------------------------------------------------------------------
# Scoring


def primary_probes(rows: list[dict]) -> list[dict]:
    """Confirmed, informative re-observations: the primary probes (p1-probes/1)."""
    seen, out = set(), []
    for row in rows:
        if row.get('schema') != PROBES_SCHEMA or row.get('lineage') not in HELD_OUT:
            raise ScoreError(f'not a held-out {PROBES_SCHEMA} row: {row}')
        if row['id'] in seen:
            raise ScoreError(f'probe listed twice: {row["id"]}')
        seen.add(row['id'])
        if not (isinstance(row['confirmed'], bool) and isinstance(row['informative'], bool)):
            raise ScoreError(f'confirmed and informative must be true or false: {row}')
        if row['confirmed'] and row['informative']:
            out.append(row)
    return out


def labels(rows: list[dict], rejudged: bool) -> dict[tuple, bool]:
    """(kind, arm, repeat, item) -> stated. Re-judged labels replace the first ones."""
    first, second = {}, {}
    for row in rows:
        if row.get('type') != 'label':
            continue
        if (row.get('schema') != SCORE_SCHEMA or row['arm'] not in ARMS or row['repeat'] not in ARMS[row['arm']]
                or row['kind'] not in KINDS or not isinstance(row['stated'], bool)):
            raise ScoreError(f'label row outside the study: {row}')
        key = (row['kind'], row['arm'], row['repeat'], row['item'])
        target = second if row.get('rejudge') else first
        if key in target:
            raise ScoreError(f'item judged twice in one pass: {key}')
        target[key] = row['stated']
    if second.keys() - first.keys():
        raise ScoreError(f're-judged items that were never judged: {sorted(second.keys() - first.keys())[:3]}')
    return {**first, **second} if rejudged else first


def figures(probes: list[dict], hours: dict[str, float], rows: list[dict], rejudged: bool = False) -> dict:
    stated = labels(rows, rejudged)
    wanted = {('reobservation', arm, rep, p['id']) for p in probes for arm, reps in ARMS.items() for rep in reps}
    have = {key for key in stated if key[0] == 'reobservation'}
    if wanted != have:
        raise ScoreError(f'primary labels do not cover the study: {len(wanted - have)} missing, '
                         f'{len(have - wanted)} unexpected; first missing {sorted(wanted - have)[:3]}')
    total_hours = sum(hours[name] for name in HELD_OUT)
    out = {}
    for arm, reps in ARMS.items():
        for rep in reps:
            boundary: dict[tuple, dict] = {}
            for p in probes:
                entry = boundary.setdefault((p['lineage'], p['boundary']), dict(lineage=p['lineage'], n=0, stated=0))
                entry['n'] += 1
                entry['stated'] += stated[('reobservation', arm, rep, p['id'])]
            rows_b = sorted(boundary.values(), key=lambda r: r['lineage'])
            n, hit = sum(r['n'] for r in rows_b), sum(r['stated'] for r in rows_b)
            secondary = {}
            for kind in KINDS[1:]:
                judged = [v for (k, a, r, _), v in stated.items() if (k, a, r) == (kind, arm, rep)]
                secondary[kind] = dict(judged=len(judged), stated=sum(judged), recall=_rate(sum(judged), len(judged)))
            out[f'{arm}{rep}'] = dict(boundaries=rows_b, probes=n, stated=hit, recall=_rate(hit, n),
                                      undelivered_per_game_hour=_rate(n - hit, total_hours), secondary=secondary)
    for row in rows:
        if row.get('type') == 'audit':
            entry = out[f"{row['arm']}{row['repeat']}"].setdefault('audit', dict(audited=0, false=0))
            entry['audited'] += 1
            entry['false'] += row['false'] is True
        elif row.get('type') == 'cost':
            entry = out[f"B{row['repeat']}"].setdefault('cost', dict(curator_dollars=0.0, actor_dollars=0.0))
            entry['curator_dollars'] += row['curator_dollars']
            entry['actor_dollars'] += row['actor_dollars']
    for entry in out.values():
        if 'audit' in entry:
            entry['audit']['rate'] = _rate(entry['audit']['false'], entry['audit']['audited'])
        if 'cost' in entry:
            entry['cost']['ratio'] = _rate(entry['cost']['curator_dollars'], entry['cost']['actor_dollars'])
    return out


def lower_bound(a_rows: list[dict], b_rows: list[dict], seed: int = SEED, draws: int = BOOTSTRAP) -> float:
    """One-sided 95% bound of pooled B-minus-A recall, resampling boundaries within each lineage."""
    rng = np.random.default_rng(seed)
    n = np.array([r['n'] for r in a_rows])
    a, b = np.array([r['stated'] for r in a_rows]), np.array([r['stated'] for r in b_rows])
    groups: dict[str, list[int]] = {}
    for i, row in enumerate(a_rows):
        groups.setdefault(row['lineage'], []).append(i)
    picks = np.concatenate([rng.choice(np.array(idx), size=(draws, len(idx))) for idx in groups.values()], axis=1)
    totals = n[picks].sum(axis=1)
    delta = (b[picks].sum(axis=1) - a[picks].sum(axis=1)) / np.maximum(totals, 1)
    return float(np.quantile(delta, LOWER_QUANTILE))


def primary(a: dict, bs: list[dict]) -> dict:
    """The pre-registered primary criterion over B's curator repeats, against A.

    B's boundary counts are averaged over its repeats. It holds when:
    - the mean pooled difference is at least EFFECT;
    - every repeat is above A;
    - every lineage with MIN_PROBES or more probes is above A on the mean;
    - the one-sided 95% boundary-bootstrap bound of the mean difference is above 0."""
    shape = [(r['lineage'], r['n']) for r in a['boundaries']]
    if any([(r['lineage'], r['n']) for r in b['boundaries']] != shape for b in bs):
        raise ScoreError('arms must be scored on the same probes')
    mean = [dict(lineage=r['lineage'], n=r['n'], stated=sum(b['boundaries'][i]['stated'] for b in bs) / len(bs))
            for i, r in enumerate(a['boundaries'])]
    total = sum(r['n'] for r in mean)
    delta = (sum(r['stated'] for r in mean) - sum(r['stated'] for r in a['boundaries'])) / total
    repeats = [b['recall'] - a['recall'] for b in bs]
    per_lineage = {}
    for name in sorted({r['lineage'] for r in mean}):
        n = sum(r['n'] for r in mean if r['lineage'] == name)
        if n >= MIN_PROBES:
            per_lineage[name] = (sum(r['stated'] for r in mean if r['lineage'] == name)
                                 - sum(r['stated'] for r in a['boundaries'] if r['lineage'] == name)) / n
    bound = lower_bound(a['boundaries'], mean)
    return dict(delta=delta, repeats=repeats, per_lineage=per_lineage, lower_bound=bound,
                holds=(delta >= EFFECT and all(d > 0 for d in repeats) and bool(per_lineage)
                       and all(d > 0 for d in per_lineage.values()) and bound > 0))


def guards(a: dict, b: dict) -> dict:
    audit_a, audit_b = a.get('audit', {}).get('rate'), b.get('audit', {}).get('rate')
    ratio = b.get('cost', {}).get('ratio')
    checks = dict(false_facts=audit_a is not None and audit_b is not None and audit_b <= FALSE_FACT_CAP
                  and audit_b <= audit_a + FALSE_FACT_MARGIN,
                  cost=ratio is not None and ratio <= COST_CAP)
    return dict(checks=checks, holds=all(checks.values()))


def decide(figs: dict, rejudged_figs: dict | None) -> dict:
    """Go only if the primary criterion holds and survives re-judging, and every guard holds in every repeat."""
    bs = [figs[f'B{rep}'] for rep in ARMS['B']]
    main = primary(figs['A1'], bs)
    repeats = {rep: guards(figs['A1'], figs[f'B{rep}']) for rep in ARMS['B']}
    robust = None if rejudged_figs is None else primary(
        rejudged_figs['A1'], [rejudged_figs[f'B{rep}'] for rep in ARMS['B']])['holds']
    mean_delta = main['delta']
    primary_holds = main['holds'] and robust is not False
    go = primary_holds and all(g['holds'] for g in repeats.values())
    if go:
        outcome = 'go: B delivers more of what the successor re-observed, within every guard'
    elif mean_delta <= 0:
        outcome = 'negative: B does not deliver more than A'
    elif primary_holds:
        outcome = 'guard failed: the primary criterion held but a guard did not'
    else:
        outcome = 'inconclusive: B is above A on average but the criterion did not hold'
    return dict(go=go, outcome=outcome, mean_delta=mean_delta, robust_to_rejudging=robust, primary=main,
                guards={str(k): v for k, v in repeats.items()})


def score(probe_rows: list[dict], hours: dict[str, float], rows: list[dict]) -> dict:
    probes = primary_probes(probe_rows)
    figs = figures(probes, hours, rows)
    rejudged = any(row.get('rejudge') for row in rows if row.get('type') == 'label')
    rejudged_figs = figures(probes, hours, rows, rejudged=True) if rejudged else None
    slim = {k: {key: val for key, val in v.items() if key != 'boundaries'} for k, v in figs.items()}
    return dict(schema=RESULT_SCHEMA, figures=slim, decision=decide(figs, rejudged_figs),
                probes=dict(listed=len(probe_rows), primary=len(probes)),
                thresholds=dict(effect=EFFECT, min_probes=MIN_PROBES, lower_quantile=LOWER_QUANTILE,
                                false_fact_cap=FALSE_FACT_CAP, false_fact_margin=FALSE_FACT_MARGIN, cost_cap=COST_CAP))


# ---------------------------------------------------------------------------------------------
# Power by simulation

# Assumptions, fixed with the rule (docs/design/p1-study.md#power).
LINEAGE_SD = 0.10        # lineage-level shift of the delivery rate
EFFECT_SD = 0.05         # lineage-level heterogeneity of the effect
REPEAT_SD = 0.05         # boundary-level curator variation between repeats
FLIP = 0.05              # judge error per label
DELTAS = (0.0, 0.10, 0.15, 0.20, 0.25, 0.30)
SIMULATIONS = 2000
DEV_HOURS, DEV_BOUNDARIES, DEV_CANDIDATES = 47.791, 13, 197   # #397 (#449, #490)


def development() -> dict:
    """#397's per-boundary sampled candidates and informative-confirmed share (#490), and its
    needed-fact carry rates (#449) as the stand-in distribution of a boundary's delivery rate."""
    probes = ROOT/'data'/'evaluation'/'probes'
    data = json.loads((probes/'validation'/'candidates.json').read_text())
    sampled = [p for p in data['pairs'] if p['lineage'] == '397']
    verdicts = {r['id']: r for r in _lines(probes/'validation'/'judgments.jsonl')}
    trivial = set(json.loads((probes/'validation'/'recall.json').read_text())['query_probes']['trivial'])
    informative = sum(1 for p in sampled if verdicts[p['id']]['same'] is True and p['id'] not in trivial)
    per_boundary: dict[str, int] = {}
    for p in sampled:
        per_boundary[p['later_chunk']] = per_boundary.get(p['later_chunk'], 0) + 1
    scale = DEV_CANDIDATES / len(sampled)
    counts = [round(c * scale) for c in per_boundary.values()] + [0] * (DEV_BOUNDARIES - len(per_boundary))
    baseline = json.loads((probes/'baseline.json').read_text())
    blinded = next(s for s in baseline['lineages'] if s['lineage'] == '397' and s['annotation'] == 'blinded')
    rates = [r['needed_carried'] / r['needed'] for r in blinded['boundaries'] if r['needed']]
    return dict(candidates_per_boundary=counts, informative_share=informative / len(sampled), delivery_rates=rates)


def held_out_shape() -> dict[str, int]:
    """Boundaries per held-out lineage, from game hours in the tracked run ledger only (aggregates)."""
    rows = [json.loads(line) for line in (ROOT/'data'/'evaluation'/'run-metrics.jsonl').read_text().splitlines()]
    hours = {row['run']: row['metrics']['survival.game_hours']['hours'] for row in rows}
    per_boundary = DEV_HOURS / DEV_BOUNDARIES
    return {name: max(len(runs) - 1, round(sum(hours[r] for r in runs) / per_boundary))
            for name, runs in HELD_OUT.items()}


def simulate(simulations: int = SIMULATIONS, seed: int = SEED) -> dict:
    dev, shape = development(), held_out_shape()
    rng = random.Random(seed)

    def clamp(p):
        return min(1.0, max(0.0, p))

    def judged(n, p):
        return sum((rng.random() < p) != (rng.random() < FLIP) for _ in range(n))

    results, probe_counts = {}, []
    for delta in DELTAS:
        go = 0
        for _ in range(simulations):
            a_rows, b_rows = [], {rep: [] for rep in ARMS['B']}
            for name, count in shape.items():
                shift, effect = rng.gauss(0, LINEAGE_SD), delta + rng.gauss(0, EFFECT_SD)
                for _ in range(count):
                    n = sum(rng.random() < dev['informative_share'] for _ in range(rng.choice(dev['candidates_per_boundary'])))
                    if n == 0:
                        continue
                    base = rng.choice(dev['delivery_rates'])
                    a_rows.append(dict(lineage=name, n=n, stated=judged(n, clamp(base + shift))))
                    for rep in ARMS['B']:
                        p = clamp(base + shift + effect + rng.gauss(0, REPEAT_SD))
                        b_rows[rep].append(dict(lineage=name, n=n, stated=judged(n, p)))
            total = sum(r['n'] for r in a_rows)
            if delta == 0:
                probe_counts.append(total)
            if not total:
                continue

            def as_figs(rows):
                return dict(boundaries=rows, recall=sum(r['stated'] for r in rows) / total)
            go += primary(as_figs(a_rows), [as_figs(b_rows[rep]) for rep in ARMS['B']])['holds']
        results[f'{delta:.2f}'] = round(go / simulations, 3)
    counts = sorted(probe_counts)
    return dict(schema=POWER_SCHEMA, seed=seed, simulations=simulations, shape=shape,
                development={k: v for k, v in dev.items()},
                assumptions=dict(lineage_sd=LINEAGE_SD, effect_sd=EFFECT_SD, repeat_sd=REPEAT_SD, flip=FLIP),
                primary_probes=dict(median=counts[len(counts) // 2], p10=counts[len(counts) // 10],
                                    p90=counts[len(counts) * 9 // 10]),
                probability_of_go=results,
                note='Primary criterion only, in both curator repeats; guards and re-judging are not simulated.')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=('simulate', 'score'))
    parser.add_argument('--probes', type=Path)
    parser.add_argument('--scores', type=Path)
    parser.add_argument('--hours', type=Path, help='JSON object: held-out lineage -> in-play game hours')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    if args.step == 'simulate':
        result = simulate()
        out = args.out or ROOT/'data'/'evaluation'/'p1'/'power.json'
        summary = result['probability_of_go']
    else:
        if not (args.probes and args.scores and args.hours):
            parser.error('score needs --probes, --scores and --hours')
        result = score(_lines(args.probes), json.loads(args.hours.read_text()), _lines(args.scores))
        out = args.out or ROOT/'data'/'evaluation'/'p1'/'result.json'
        summary = result['decision']['outcome']
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
