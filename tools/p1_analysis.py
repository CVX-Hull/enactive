"""The P1 offline study's frozen analysis (ADR 009; pre-registration p1-study/2 in docs/design/p1-study-2.md,
which keeps p1-study/1's rule from docs/design/p1-study.md; #491, #178).

  python -m tools.p1_analysis simulate [--probes <held-out p1-probes/1>]... [--out data/evaluation/p1/power.json]
  python -m tools.p1_analysis plan --probes <#382 held-out p1-probes/1>  # p1-study/2's planning, power-study-2.json
  python -m tools.p1_analysis units --probes <p1-probes/1>...   # the probes the judges score
  python -m tools.p1_analysis rejudge --probes <p1-probes/1>... # the items judged a second time
  python -m tools.p1_analysis score --probes <p1-probes/1>... --scores <p1-score/1> --hours <JSON> [--out ...]

`--probes` may be given once per held-out directory (rows are concatenated in the order given) for
`simulate`, `units`, `rejudge` and `score`. Each file must have a digest in the `frozen.json` beside it
(`tools.probe_validation held-out-freeze`) and is recorded, with its sha256, under `probe_files`.
With several files `simulate` writes power-held-out-study-2.json and never p1-study/1's power-held-out.json.

`simulate` checks, before any spend, that the decision rule detects the effect of interest and
rarely fires without one. Without `--probes` it uses development data and aggregates only: #397's
sampled re-observation candidates and needed-fact carry rates (#449, #490), and each held-out
lineage's game hours from the tracked run ledger. With the held-out probe file it uses that file's
actual unit and cluster structure: the gate before replay.

`score` computes every pre-registered figure and the decision from the confirmed re-observation
probes, the blinded judges' labels, the seeded re-judging, the false-fact audit and the settled
costs. It refuses an incomplete study. Nothing here judges text; it only counts labels.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
from scipy.stats import beta, binom

from harness.evaluation.core.probes import kappa
from harness.jsonio import file_sha256

ROOT = Path(__file__).resolve().parents[1]
PROBES_SCHEMA = 'p1-probes/1'
SCORE_SCHEMA = 'p1-score/1'
RESULT_SCHEMA = 'p1-result/1'
POWER_SCHEMA = 'p1-power/1'
SEED = 491
REJUDGE_SEED, REJUDGE_SHARE = 4912, 0.2

# Pre-registered decision rule (docs/design/p1-study.md#decision-rule). Changing one is a deviation.
EFFECT = 0.15            # mean pooled unit recall, B minus A
MIN_UNITS = 20           # a lineage with at least this many units must show B above A
BOOTSTRAP = 2000         # cluster resamples within lineage
LOWER_QUANTILE = 0.025   # the one-sided 97.5% bound of the mean difference must exceed 0
INTEREST = 0.30          # the effect of interest: the gate needs P(go) >= 0.80 there and <= 0.05 at none
GUESSES = 30             # the arm-guessing check: 15 texts per arm, seeded order
GUESS_ALPHA = 0.05       # scoring stops if the better label mapping is right this improbably often by chance
FALSE_FACT_CAP = 0.10    # B's audited false-fact rate (point), its one-sided 95% upper bound,
FALSE_FACT_BOUND = 0.20  # and at most A's plus the margin
FALSE_FACT_MARGIN = 0.05
COST_CAP = 1.0           # curator settled dollars over actor dollars, per repeat
NEAR = 16                # bits between earlier frames of one information cluster (probe-protocol/1)
ARMS = {'A': (1,), 'B': (1, 2)}
STUDY_1_HELD_OUT = {'lh1': ('lh1a1', 'lh1a2', 'lh1a3'), 'lh2': ('lh2a1', 'lh2a2'), 'lh3': ('lh3a1', 'lh3a2')}
# lh4's admissions (study 522-held-out), as #522 ran them: lh4b1-lh4b7. The lost lh4a1 is not part of
# the lineage (docs/acceptance/2026-11-09-held-out-lineage-522.md). With an empty tuple lh4 would not
# be a held-out lineage anywhere, and HELD_OUT would be exactly p1-study/1's.
LH4_ADMISSIONS: tuple[str, ...] = tuple(f'lh4b{n}' for n in range(1, 8))
HELD_OUT = dict(STUDY_1_HELD_OUT, lh4=LH4_ADMISSIONS) if LH4_ADMISSIONS else dict(STUDY_1_HELD_OUT)   # lineage -> admissions
STUDY_1_BOUNDARIES = {'lh1': 4, 'lh2': 3, 'lh3': 3}   # boundaries per #382 lineage (the #178 gate record); fixed, as `plan` resamples them
KINDS = ('reobservation', 'fact', 'query')   # primary, then the two descriptive ledgers


class ScoreError(ValueError):
    """The labels do not cover the study, or a row does not follow its schema."""


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


FROZEN_SCHEMA = 'p1-held-out-frozen/1'   # written by tools/probe_validation.py held-out-freeze
POWER_STUDY_2 = ROOT/'data'/'evaluation'/'p1'/'power-held-out-study-2.json'
POWER_STUDY_1 = ROOT/'data'/'evaluation'/'p1'/'power-held-out.json'


def _relative(path: Path) -> str:
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def frozen_probes(paths: list[Path]) -> tuple[list[dict], list[dict]]:
    """(rows, probe_files): the rows of each held-out probes file, concatenated in the order given, and each
    file's repository-relative path and sha256. A file is refused unless the `frozen.json` beside it
    (`p1-held-out-frozen/1`) lists a digest for it that matches. Errors name only the file."""
    rows, files = [], []
    for path in map(Path, paths):
        name = _relative(path)
        frozen = path.parent/'frozen.json'
        try:
            document = json.loads(frozen.read_text())
            digest = document['files'][path.name] if document.get('schema') == FROZEN_SCHEMA else None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            digest = None
        if not path.is_file() or digest is None or file_sha256(path) != digest:
            raise ScoreError(f'{name}: not a frozen held-out probes file (no matching digest in its directory\'s frozen.json)')
        rows += _lines(path)
        files.append(dict(path=name, sha256=digest))
    return rows, files


def _rate(numerator: float, denominator: float) -> float | None:
    return None if not denominator else numerator / denominator


# ---------------------------------------------------------------------------------------------
# Probes, information clusters and scoring units


def primary_probes(rows: list[dict]) -> list[dict]:
    """Confirmed, informative re-observations: the primary probes (p1-probes/1)."""
    seen, out = set(), []
    for row in rows:
        if row.get('schema') != PROBES_SCHEMA or row.get('lineage') not in HELD_OUT:
            # Held-out rows carry a judge's description of the frame; errors name only the probe id.
            raise ScoreError(f'not a held-out {PROBES_SCHEMA} row: {row.get("id")!r}')
        if row['id'] in seen:
            raise ScoreError(f'probe listed twice: {row["id"]}')
        seen.add(row['id'])
        if not (isinstance(row['confirmed'], bool) and isinstance(row['informative'], bool)
                and isinstance(row.get('earlier_dhash'), str)):
            raise ScoreError(f'confirmed, informative and earlier_dhash are required: {row["id"]!r}')
        if row['confirmed'] and row['informative']:
            out.append(row)
    return out


def clusters(probes: list[dict]) -> dict[str, str]:
    """Probe id -> information cluster, within one lineage, by complete linkage: in probe-id order, a
    probe joins the first cluster whose every earlier frame is within NEAR bits of its own, else it
    starts one. Nothing chains: two frames 16 bits apart can show different lists (#490), so a cluster
    never joins frames that are not all near each other. The cluster is named by its first probe."""
    out: dict[str, str] = {}
    groups: dict[str, list[tuple[str, list[int]]]] = {}
    for p in sorted(probes, key=lambda p: p['id']):
        h = int(p['earlier_dhash'], 16)
        for name, members in groups.setdefault(p['lineage'], []):
            if all((h ^ m).bit_count() <= NEAR for m in members):
                members.append(h)
                out[p['id']] = name
                break
        else:
            groups[p['lineage']].append((p['id'], [h]))
            out[p['id']] = p['id']
    return out


def units(probes: list[dict]) -> list[dict]:
    """One scoring unit per (lineage, boundary, cluster): the same information re-observed several
    times after one boundary counts once. The unit's probe is the lowest probe id; only it is judged."""
    cluster = clusters(probes)
    chosen: dict[tuple, dict] = {}
    for p in sorted(probes, key=lambda p: p['id']):
        chosen.setdefault((p['lineage'], p['boundary'], cluster[p['id']]), p)
    return [dict(lineage=k[0], boundary=k[1], cluster=k[2], probe=p['id']) for k, p in sorted(chosen.items())]


def cluster_sizes(unit_rows: list[dict]) -> dict[str, int]:
    """How many clusters have each number of units: the clustering the power check depends on."""
    sizes: dict[tuple, int] = {}
    for u in unit_rows:
        sizes[(u['lineage'], u['cluster'])] = sizes.get((u['lineage'], u['cluster']), 0) + 1
    out: dict[str, int] = {}
    for size in sizes.values():
        out[str(size)] = out.get(str(size), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def rejudge_sample(unit_rows: list[dict]) -> set[tuple]:
    """The seeded 20% of primary labels that fresh judges score a second time."""
    keys = sorted(('reobservation', arm, rep, u['probe']) for u in unit_rows for arm, reps in ARMS.items()
                  for rep in reps)
    return set(random.Random(REJUDGE_SEED).sample(keys, math.ceil(REJUDGE_SHARE * len(keys)))) if keys else set()


def labels(rows: list[dict]) -> tuple[dict[tuple, bool], dict[tuple, bool]]:
    """(kind, arm, repeat, item) -> stated, for the first pass and for the re-judging."""
    first, second = {}, {}
    for row in rows:
        if row.get('type') != 'label':
            continue
        if (row.get('schema') != SCORE_SCHEMA or row.get('arm') not in ARMS or row.get('repeat') not in ARMS[row['arm']]
                or row.get('kind') not in KINDS or not isinstance(row.get('stated'), bool)):
            raise ScoreError(f'label row outside the study: {row}')
        key = (row['kind'], row['arm'], row['repeat'], row['item'])
        target = second if row.get('rejudge') else first
        if key in target:
            raise ScoreError(f'item judged twice in one pass: {key}')
        target[key] = row['stated']
    return first, second


def _validated(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    audits, costs = [], []
    for row in rows:
        if row.get('type') == 'audit':
            if (row.get('schema') != SCORE_SCHEMA or row.get('arm') not in ARMS or row.get('repeat') not in ARMS[row['arm']]
                    or not isinstance(row.get('false'), bool) or not isinstance(row.get('item'), str)):
                raise ScoreError(f'audit row outside the study: {row}')
            audits.append(row)
        elif row.get('type') == 'cost':
            if (row.get('schema') != SCORE_SCHEMA or row.get('repeat') not in ARMS['B'] or row.get('lineage') not in HELD_OUT
                    or not isinstance(row.get('stopped_by_cap'), bool)
                    or not all(isinstance(row.get(k), (int, float)) and row[k] >= 0
                               for k in ('curator_dollars', 'actor_dollars'))):
                raise ScoreError(f'cost row outside the study: {row}')
            costs.append(row)
        elif row.get('type') != 'label':
            raise ScoreError(f'unknown row type: {row}')
    return audits, costs


def figures(unit_rows: list[dict], hours: dict[str, float], stated: dict[tuple, bool], audits, costs) -> dict:
    wanted = {('reobservation', arm, rep, u['probe']) for u in unit_rows for arm, reps in ARMS.items() for rep in reps}
    have = {key for key in stated if key[0] == 'reobservation'}
    if wanted != have:
        raise ScoreError(f'primary labels do not cover the study: {len(wanted - have)} missing, '
                         f'{len(have - wanted)} unexpected; first missing {sorted(wanted - have)[:3]}')
    if set(hours) != set(HELD_OUT):
        raise ScoreError(f'--hours must give in-play game hours for exactly the held-out lineages: {", ".join(HELD_OUT)}')
    total_hours = sum(hours[name] for name in HELD_OUT)
    out = {}
    for arm, reps in ARMS.items():
        for rep in reps:
            rows = [dict(lineage=u['lineage'], cluster=u['cluster'], stated=stated[('reobservation', arm, rep, u['probe'])])
                    for u in unit_rows]
            n, hit = len(rows), sum(r['stated'] for r in rows)
            secondary = {}
            for kind in KINDS[1:]:
                judged = [v for (k, a, r, _), v in stated.items() if (k, a, r) == (kind, arm, rep)]
                secondary[kind] = dict(judged=len(judged), stated=sum(judged), recall=_rate(sum(judged), len(judged)))
            out[f'{arm}{rep}'] = dict(units=rows, n=n, stated=hit, recall=_rate(hit, n),
                                      undelivered_per_game_hour=_rate(n - hit, total_hours), secondary=secondary)
    for row in audits:
        entry = out[f"{row['arm']}{row['repeat']}"].setdefault('audit', dict(audited=0, false=0))
        entry['audited'] += 1
        entry['false'] += row['false']
    for row in costs:
        entry = out[f"B{row['repeat']}"].setdefault('cost', dict(curator_dollars=0.0, actor_dollars=0.0))
        entry['curator_dollars'] += row['curator_dollars']
        entry['actor_dollars'] += row['actor_dollars']
    for entry in out.values():
        if 'audit' in entry:
            k, n = entry['audit']['false'], entry['audit']['audited']
            entry['audit'].update(rate=_rate(k, n), upper_95=1.0 if k == n else float(beta.ppf(0.95, k + 1, n - k)))
        if 'cost' in entry:
            entry['cost']['ratio'] = _rate(entry['cost']['curator_dollars'], entry['cost']['actor_dollars'])
    return out


def _clustered(a_units: list[dict], b_units: list[list[dict]]) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    """Per cluster: its lineage, unit count, A's stated count and B's stated count averaged over repeats."""
    index: dict[tuple, int] = {}
    for u in a_units:
        index.setdefault((u['lineage'], u['cluster']), len(index))
    lineage = [key[0] for key in index]
    n, a, b = np.zeros(len(index)), np.zeros(len(index)), np.zeros(len(index))
    for i, u in enumerate(a_units):
        c = index[(u['lineage'], u['cluster'])]
        n[c] += 1
        a[c] += u['stated']
        b[c] += sum(rows[i]['stated'] for rows in b_units) / len(b_units)
    return lineage, n, a, b


def lower_bound(lineage, n, a, b, seed: int = SEED, draws: int = BOOTSTRAP) -> float:
    """One-sided 97.5% bound of the pooled difference, resampling information clusters within each lineage."""
    rng = np.random.default_rng(seed)
    groups: dict[str, list[int]] = {}
    for i, name in enumerate(lineage):
        groups.setdefault(name, []).append(i)
    picks = np.concatenate([rng.choice(np.array(idx), size=(draws, len(idx))) for idx in groups.values()], axis=1)
    delta = (b[picks].sum(axis=1) - a[picks].sum(axis=1)) / np.maximum(n[picks].sum(axis=1), 1)
    return float(np.quantile(delta, LOWER_QUANTILE))


def primary(a: dict, bs: list[dict], *, bound_if_needed: bool = False) -> dict:
    """The pre-registered primary criterion over B's curator repeats, against A.

    It holds when:
    - the mean pooled difference (B's repeats averaged per unit) is at least EFFECT;
    - every repeat is above A;
    - every lineage with MIN_UNITS or more units is above A on the mean;
    - the one-sided 97.5% cluster-bootstrap bound of the mean difference is above 0.

    With `bound_if_needed`, the bootstrap runs only when the other conditions hold (else
    `lower_bound` is None). The bootstrap draws from its own fixed seed, so skipping it changes
    no other value; the power simulation uses this, and scoring always computes the bound."""
    shape = [(u['lineage'], u['cluster']) for u in a['units']]
    if any([(u['lineage'], u['cluster']) for u in b['units']] != shape for b in bs):
        raise ScoreError('arms must be scored on the same units')
    lineage, n, sa, sb = _clustered(a['units'], [b['units'] for b in bs])
    delta = (sb.sum() - sa.sum()) / n.sum()
    repeats = [b['recall'] - a['recall'] for b in bs]
    per_lineage = {}
    for name in sorted(set(lineage)):
        mask = np.array([x == name for x in lineage])
        if n[mask].sum() >= MIN_UNITS:
            per_lineage[name] = float((sb[mask].sum() - sa[mask].sum()) / n[mask].sum())
    rest = bool(delta >= EFFECT and all(d > 0 for d in repeats) and per_lineage
                and all(d > 0 for d in per_lineage.values()))
    bound = lower_bound(lineage, n, sa, sb) if rest or not bound_if_needed else None
    return dict(delta=float(delta), repeats=repeats, per_lineage=per_lineage, lower_bound=bound,
                holds=rest and bound > 0)


def guards(a: dict, b: dict) -> dict:
    audit_a, audit_b = a.get('audit'), b.get('audit')
    ratio = b.get('cost', {}).get('ratio')
    checks = dict(false_facts=bool(audit_a and audit_b and audit_b['rate'] <= FALSE_FACT_CAP
                                   and audit_b['upper_95'] <= FALSE_FACT_BOUND
                                   and audit_b['rate'] <= audit_a['rate'] + FALSE_FACT_MARGIN),
                  cost=ratio is not None and ratio <= COST_CAP)
    return dict(checks=checks, holds=all(checks.values()))


def agreement(first: dict, second: dict) -> dict:
    pairs = [(first[k], second[k]) for k in sorted(second)]
    return dict(n=len(pairs), percent=_rate(sum(x == y for x, y in pairs), len(pairs)), kappa=kappa(pairs))


def guess_limit(n: int = GUESSES) -> int:
    """Correct guesses (under the better of the two label mappings) at which scoring stops: the
    smallest k with P(max(X, n - X) >= k) <= GUESS_ALPHA for X ~ Binomial(n, 1/2), i.e. no leak."""
    return next(k for k in range(n // 2 + 1, n + 1) if 2 * binom.sf(k - 1, n, 0.5) <= GUESS_ALPHA)


def arm_guessing(rows: list[dict]) -> dict:
    """The guesser labels each text "1" or "2"; the better mapping of labels to arms is scored."""
    if (len(rows) != GUESSES or any(r.get('arm') not in ('A', 'B') or r.get('guess') not in ('1', '2') for r in rows)
            or sum(r['arm'] == 'A' for r in rows) != GUESSES // 2):
        raise ScoreError(f'the arm-guessing check needs exactly {GUESSES} guesses, half per arm')
    agree = sum((r['arm'] == 'A') == (r['guess'] == '1') for r in rows)
    best = max(agree, len(rows) - agree)
    return dict(n=len(rows), correct=best, limit=guess_limit(), leaks=best >= guess_limit())


def score(probe_rows: list[dict], hours: dict[str, float], rows: list[dict]) -> dict:
    guessing = arm_guessing([row for row in rows if row.get('type') == 'guess'])
    if guessing['leaks']:
        raise ScoreError(f"the arm can be guessed from the text ({guessing['correct']} of {guessing['n']}); "
                         'fix the rendering first')
    rows = [row for row in rows if row.get('type') != 'guess']
    audits, costs = _validated(rows)
    unit_rows = units(primary_probes(probe_rows))
    base = dict(schema=RESULT_SCHEMA, probes=dict(listed=len(probe_rows), units=len(unit_rows),
                                                  clusters=len({(u['lineage'], u['cluster']) for u in unit_rows}),
                                                  cluster_sizes=cluster_sizes(unit_rows)),
                thresholds=dict(effect=EFFECT, min_units=MIN_UNITS, lower_quantile=LOWER_QUANTILE, interest=INTEREST,
                                false_fact_cap=FALSE_FACT_CAP, false_fact_bound=FALSE_FACT_BOUND,
                                false_fact_margin=FALSE_FACT_MARGIN, cost_cap=COST_CAP))
    capped = sorted({row['repeat'] for row in costs if row['stopped_by_cap']})
    if capped:
        # A held-out repeat that reached its cap has failed the cost guard; its partial labels decide nothing.
        return dict(base, decision=dict(go=False, outcome=f'guard failed: held-out repeat {capped} reached its cap'))
    first, second = labels(rows)
    if set(second) != rejudge_sample(unit_rows):
        raise ScoreError('re-judged labels must be exactly the seeded sample (tools.p1_analysis rejudge)')
    figs = figures(unit_rows, hours, first, audits, costs)
    refigs = figures(unit_rows, hours, {**first, **second}, audits, costs)
    bs = [figs[f'B{rep}'] for rep in ARMS['B']]
    main = primary(figs['A1'], bs)
    robust = primary(refigs['A1'], [refigs[f'B{rep}'] for rep in ARMS['B']])['holds']
    guard = {str(rep): guards(figs['A1'], figs[f'B{rep}']) for rep in ARMS['B']}
    primary_holds = main['holds'] and robust
    go = primary_holds and all(g['holds'] for g in guard.values())
    if go:
        outcome = 'go: B delivers more of what the successor re-observed, within every guard'
    elif main['delta'] <= 0:
        outcome = 'negative: B does not deliver more than A'
    elif primary_holds:
        outcome = 'guard failed: the primary criterion held but a guard did not'
    else:
        outcome = 'inconclusive: B is above A on average but the criterion did not hold'
    slim = {k: {key: val for key, val in v.items() if key != 'units'} for k, v in figs.items()}
    return dict(base, figures=slim, judge_agreement=agreement(first, second),
                arm_guessing=guessing,
                decision=dict(go=go, outcome=outcome, mean_delta=main['delta'], robust_to_rejudging=robust,
                              primary=main, guards=guard))


# ---------------------------------------------------------------------------------------------
# Power by simulation

# Assumptions, fixed with the rule (docs/design/p1-study.md#power).
LINEAGE_SD = 0.10        # lineage-level shift of the delivery rate
EFFECT_SD = 0.05         # lineage-level heterogeneity of the effect
REPEAT_SD = 0.05         # cluster-level curator variation between repeats
FLIP = 0.05              # judge error per label
CLUSTER_MEAN = 3.0       # planning assumption: units per information cluster (#397's sample: 1.4)
VARIANTS = ((1.4, 0.0), (3.0, 0.0), (6.0, 0.0), (3.0, 0.05))   # (cluster mean, judge bias toward B)
DELTAS = (0.0, 0.10, 0.15, 0.20, 0.25, 0.30)
SIMULATIONS = 5000
DEV_HOURS, DEV_BOUNDARIES, DEV_CANDIDATES = 47.791, 13, 197   # #397 (#449, #490)


def development() -> dict:
    """#397's per-boundary sampled candidates and informative-confirmed share (#490), and its
    needed-fact carry rates (#449) as the stand-in distribution of a cluster's delivery rate."""
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
    # A run that never reached play (an infrastructure loss) has no game hours and is no admission of a lineage.
    hours = {row['run']: row['metrics']['survival.game_hours']['hours'] for row in rows
             if row['metrics'].get('survival.game_hours')}
    per_boundary = DEV_HOURS / DEV_BOUNDARIES
    return {name: max(len(runs) - 1, round(sum(hours[r] for r in runs) / per_boundary))
            for name, runs in STUDY_1_HELD_OUT.items()}   # p1-study/1's planning; lh4 does not change it


def _generated(rng: random.Random, dev: dict, shape: dict[str, int], cluster_mean: float) -> list[tuple[str, str]]:
    """(lineage, cluster) per unit: each unit after a boundary is new information with probability
    1/cluster_mean, otherwise a cluster already seen at an earlier boundary of its lineage."""
    out = []
    for name, count in shape.items():
        seen: list[str] = []
        for b in range(count):
            here: set[str] = set()
            n = sum(rng.random() < dev['informative_share'] for _ in range(rng.choice(dev['candidates_per_boundary'])))
            for _ in range(n):
                old = [c for c in seen if c not in here]
                c = rng.choice(old) if old and rng.random() >= 1 / cluster_mean else f'{name}-{len(seen)}'
                if c not in seen:
                    seen.append(c)
                here.add(c)
                out.append((name, c))
    return out


def _power(rng: random.Random, dev: dict, structure, cluster_mean: float | None, bias: float, delta: float) -> bool:
    shape = structure if cluster_mean is not None else None
    layout = _generated(rng, dev, shape, cluster_mean) if shape is not None else structure
    if not layout:
        return False
    clamp = lambda p: min(1.0, max(0.0, p))  # noqa: E731
    lineage_shift = {name: (rng.gauss(0, LINEAGE_SD), delta + rng.gauss(0, EFFECT_SD)) for name, _ in layout}
    latent: dict[tuple, dict] = {}
    for name, c in layout:
        if (name, c) not in latent:
            shift, effect = lineage_shift[name]
            base = rng.choice(dev['delivery_rates'])
            latent[(name, c)] = {'A1': rng.random() < clamp(base + shift),
                                 **{f'B{r}': rng.random() < clamp(base + shift + effect + rng.gauss(0, REPEAT_SD))
                                    for r in ARMS['B']}}

    def judged(key, truth):
        label = truth != (rng.random() < FLIP)
        return label or (key.startswith('B') and rng.random() < bias)
    figs = {}
    for key in ('A1', *(f'B{r}' for r in ARMS['B'])):
        rows = [dict(lineage=name, cluster=c, stated=judged(key, latent[(name, c)][key])) for name, c in layout]
        figs[key] = dict(units=rows, recall=sum(r['stated'] for r in rows) / len(rows))
    return primary(figs['A1'], [figs[f'B{r}'] for r in ARMS['B']], bound_if_needed=True)['holds']


def simulate(simulations: int = SIMULATIONS, seed: int = SEED, layout: list[tuple[str, str]] | None = None) -> dict:
    dev = development()
    rng = random.Random(seed)
    if layout is not None:
        variants = {'held-out structure': {f'{d:.2f}': round(sum(_power(rng, dev, layout, None, 0.0, d)
                                                                  for _ in range(simulations)) / simulations, 3)
                                           for d in DELTAS}}
        return dict(schema=POWER_SCHEMA, seed=seed, simulations=simulations, units=len(layout),
                    clusters=len(set(layout)),
                    cluster_sizes=cluster_sizes([dict(lineage=name, cluster=c) for name, c in layout]),
                    probability_of_go=variants,
                    gate=gate(variants['held-out structure']))
    shape = held_out_shape()
    variants = {}
    for mean, bias in VARIANTS:
        variants[f'cluster_mean={mean}, judge_bias={bias}'] = {
            f'{d:.2f}': round(sum(_power(rng, dev, shape, mean, bias, d) for _ in range(simulations)) / simulations, 3)
            for d in DELTAS}
    return dict(schema=POWER_SCHEMA, seed=seed, simulations=simulations, shape=shape, development=dev,
                assumptions=dict(lineage_sd=LINEAGE_SD, effect_sd=EFFECT_SD, repeat_sd=REPEAT_SD, flip=FLIP,
                                 planning=f'cluster_mean={CLUSTER_MEAN}, judge_bias=0.0'),
                probability_of_go=variants, gate=gate(variants[f'cluster_mean={CLUSTER_MEAN}, judge_bias=0.0']),
                note='Primary criterion only; guards and re-judging are not simulated.')


# p1-study/2's planning simulation (docs/design/p1-study-2.md#power): #382's frozen held-out
# structure plus one new held-out lineage, lh4, run to a planned number of boundaries. Planning
# only; the gate before held-out replay is `simulate --probes` on all four lineages' actual probes.
PLAN_SIMULATIONS = 2000
PLAN_BOUNDARIES = (8, 10, 12, 14)       # lh4's boundaries (the stop rule counts these)
PLAN_CLUSTER_MEANS = (1.04, 1.4, 3.0)   # lh1-lh3 as measured; #397's 20% sample; p1-study/1's planning value
PLAN_TARGET, PLAN_MEAN = 12, 1.04       # the planning assumption: the size rule's target, clustered as lh1-lh3


def boundary_units(unit_rows: list[dict]) -> list[int]:
    """Scoring units at each #382 boundary, including the boundaries that yielded none: a count
    per boundary, the only held-out quantity the plan resamples."""
    counts: dict[tuple, int] = {}
    for u in unit_rows:
        counts[(u['lineage'], u['boundary'])] = counts.get((u['lineage'], u['boundary']), 0) + 1
    out = []
    for name, total in STUDY_1_BOUNDARIES.items():
        here = sorted(c for (lineage, _), c in counts.items() if lineage == name)
        if len(here) > total:
            raise ScoreError(f'{name} has units at more boundaries than it has')
        out += [0] * (total - len(here)) + here
    return out


def _new_lineage(rng: random.Random, name: str, per_boundary: list[int], boundaries: int,
                 cluster_mean: float) -> list[tuple[str, str]]:
    """(lineage, cluster) per unit of a new lineage with `boundaries` boundaries: each boundary's
    unit count is drawn from `per_boundary`; each unit is new information with probability
    1/cluster_mean, otherwise it repeats a cluster of an earlier boundary (as `_generated` does)."""
    seen: list[str] = []
    out = []
    for _ in range(boundaries):
        here: set[str] = set()
        for _ in range(rng.choice(per_boundary)):
            old = [c for c in seen if c not in here]
            if old and rng.random() >= 1 / cluster_mean:
                cluster = rng.choice(old)
            else:
                cluster = f'{name}-{len(seen)}'
                seen.append(cluster)
            here.add(cluster)
            out.append((name, cluster))
    return out


def plan(held_out: list[dict], simulations: int = PLAN_SIMULATIONS, seed: int = SEED) -> dict:
    dev = development()
    unit_rows = units(primary_probes(held_out))
    base = [(u['lineage'], u['cluster']) for u in unit_rows]
    per_boundary = boundary_units(unit_rows)
    variants, short = {}, {}
    for mean in PLAN_CLUSTER_MEANS:
        for count in PLAN_BOUNDARIES:
            key = f'lh4_boundaries={count}, cluster_mean={mean}'
            rng = random.Random(f'{seed}:{key}')   # one stream per variant: adding a variant moves no figure
            draws = [_new_lineage(rng, 'lh4', per_boundary, count, mean) for _ in range(simulations)]
            short[key] = round(sum(len(d) < MIN_UNITS for d in draws) / simulations, 3)
            variants[key] = {f'{d:.2f}': round(sum(_power(rng, dev, base + draw, None, 0.0, d)
                                                   for draw in draws) / simulations, 3)
                             for d in DELTAS}
    planning = f'lh4_boundaries={PLAN_TARGET}, cluster_mean={PLAN_MEAN}'
    return dict(schema=POWER_SCHEMA, seed=seed, simulations=simulations, new_lineage='lh4',
                held_out=dict(units=len(base), clusters=len(set(base)), boundaries=len(per_boundary),
                              cluster_sizes=cluster_sizes(unit_rows)),
                planning=planning, probability_of_go=variants, lh4_under_min_units=short,
                gate=gate(variants[planning]),
                note='Planning for p1-study/2; primary criterion only. The gate before replay re-runs on actual probes.')


def gate(probabilities: dict[str, float]) -> dict:
    """The gate before spend: rarely a go with no effect, usually a go at the effect of interest."""
    none, interest = probabilities['0.00'], probabilities[f'{INTEREST:.2f}']
    return dict(no_effect=none, at_interest=interest, passes=none <= 0.05 and interest >= 0.80)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=('simulate', 'plan', 'units', 'rejudge', 'score'))
    parser.add_argument('--probes', type=Path, action='append',
                        help='a held-out p1-probes/1 file; simulate, units, rejudge and score take one per held-out '
                             'directory (each must match its frozen.json), plan takes exactly one')
    parser.add_argument('--scores', type=Path)
    parser.add_argument('--hours', type=Path, help='JSON object: held-out lineage -> in-play game hours')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    probe_paths = args.probes or []
    probe_files = None
    try:
        if probe_paths and args.step != 'plan':
            probe_rows, probe_files = frozen_probes(probe_paths)
        elif probe_paths:
            probe_rows = _lines(probe_paths[0])
    except ScoreError as error:
        parser.error(str(error))
    if args.step == 'simulate':
        layout = None
        if probe_paths:
            layout = [(u['lineage'], u['cluster']) for u in units(primary_probes(probe_rows))]
        if args.out:
            out = args.out
        elif not probe_paths:
            out = ROOT/'data'/'evaluation'/'p1'/'power.json'
        else:
            out = POWER_STUDY_2 if len(probe_paths) > 1 else POWER_STUDY_1
        if len(probe_paths) > 1 and out.resolve() == POWER_STUDY_1.resolve():
            parser.error(f'{_relative(POWER_STUDY_1)} is p1-study/1\'s gate; with several --probes files write '
                         f'{_relative(POWER_STUDY_2)}')
        result = simulate(layout=layout)
        if probe_files:
            result['probe_files'] = probe_files
        summary = result['probability_of_go']
    elif args.step == 'plan':
        if len(probe_paths) != 1:
            parser.error('plan needs exactly one --probes (the frozen #382 held-out probes)')
        result = plan(probe_rows)
        out = args.out or ROOT/'data'/'evaluation'/'p1'/'power-study-2.json'
        summary = result['gate']
    elif args.step in ('units', 'rejudge'):
        if not probe_paths:
            parser.error(f'{args.step} needs --probes')
        unit_rows = units(primary_probes(probe_rows))
        for row in (unit_rows if args.step == 'units' else
                    [dict(kind=k, arm=a, repeat=r, item=i) for k, a, r, i in sorted(rejudge_sample(unit_rows))]):
            print(json.dumps(row))
        return 0
    else:
        if not (probe_paths and args.scores and args.hours):
            parser.error('score needs --probes, --scores and --hours')
        result = dict(score(probe_rows, json.loads(args.hours.read_text()), _lines(args.scores)), probe_files=probe_files)
        out = args.out or ROOT/'data'/'evaluation'/'p1'/'result.json'
        summary = result['decision']['outcome']
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
