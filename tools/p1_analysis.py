"""The P1 offline study's frozen analysis (ADR 009; pre-registration p1-study/3 in docs/design/p1-study-3.md,
which keeps p1-study/1's rule from docs/design/p1-study.md; #491, #178).

  python -m tools.p1_analysis simulate [--probes <held-out p1-probes/1>]... [--out data/evaluation/p1/power.json]
  python -m tools.p1_analysis simulate ... --flip E | --sensitivity SA SB --out <path outside data/>   # the chain's measured values
  python -m tools.p1_analysis plan --probes <#382 held-out p1-probes/1>  # p1-study/2's planning, power-study-2.json
  python -m tools.p1_analysis units --probes <p1-probes/1>...   # the probes the chain scores
  python -m tools.p1_analysis rejudge --probes <p1-probes/1>... # the items read and graded a second time
  python -m tools.p1_analysis score --probes <p1-probes/1>... --scores <p1-score/1> --hours <JSON>
                                    --questions <questions.jsonl> --screen <screen.json> --sentences-counts <counts.json> [--out ...]
  python -m tools.p1_analysis development --scores <development p1-score/1 rows> --out <path under .runtime/>
  python -m tools.p1_analysis batches|parse|screen|sentences|questions-freeze ...   # the answer-key chain (tools/p1_batches.py)

`--probes` may be given once per held-out directory (rows are concatenated in the order given) for
`simulate`, `units`, `rejudge` and `score`. Each file must have a digest in the `frozen.json` beside it
(`tools.probe_validation held-out-freeze`) and is recorded, with its sha256, under `probe_files`;
`score --questions` is checked the same way and recorded under `question_file`, and `score --screen` must be
the `screen.json` that `questions-freeze` copied beside the questions (recorded under `screen_file`).
`development` reads the development chain's labels and prints the two development checks' figures, nothing else.
With several files `simulate` writes power-held-out-study-2.json and never p1-study/1's power-held-out.json.

`simulate` checks, before any spend, that the decision rule detects the effect of interest and
rarely fires without one. Without `--probes` it uses development data and aggregates only: #397's
sampled re-observation candidates and needed-fact carry rates (#449, #490), and each held-out
lineage's game hours from the tracked run ledger. With the held-out probe file it uses that file's
actual unit and cluster structure: the gate before replay. `--flip` replaces the label error and
`--sensitivity` keeps every label made stated with the given probability per arm (A, then B); both
are off by default, and a run that uses either writes only outside `data/`.

`score` computes every pre-registered figure and the decision from the confirmed re-observation
probes, the answer-key chain's labels, the seeded re-judging, the false-fact audit and the settled
costs, and reports the Reference, the bias control and the positive control. It refuses an
incomplete study. Nothing here judges text; it only counts labels.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from scipy.stats import beta

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
BIAS_LIMIT = 0.10        # the bias control's flag: |B - A| over the Reference-correct units, reported, decides nothing
BIAS_MIN_UNITS = 20      # ... and it applies only over at least this many such units
FALSE_FACT_CAP = 0.10    # B's audited false-fact rate (point), its one-sided 95% upper bound,
FALSE_FACT_BOUND = 0.20  # and at most A's plus the margin
FALSE_FACT_MARGIN = 0.05
COST_CAP = 1.0           # curator settled dollars over actor dollars, per repeat
NEAR = 16                # bits between earlier frames of one information cluster (probe-protocol/1)
ARMS = {'A': (1,), 'B': (1, 2)}
CONTROLS = ('R', 'PW', 'PP')       # the Reference and the positive control's two forms: repeat 1 each, outside the rule
ARM_REPEATS = dict(ARMS, **{name: (1,) for name in CONTROLS})
DEVELOPMENT_ARMS = {'A': (1,), 'B': (1,)}   # a development delivery has A repeat 1 and B repeat 1 only: no second B repeat
NOISE_LIMIT = 0.10                # development's chain noise: the pooled repeat disagreement d, at most
SENSITIVITY_FLOOR = 0.85          # development's positive control: each form correct on at least this share of units
STUDY_1_HELD_OUT = {'lh1': ('lh1a1', 'lh1a2', 'lh1a3'), 'lh2': ('lh2a1', 'lh2a2'), 'lh3': ('lh3a1', 'lh3a2')}
# lh4's admissions (study 522-held-out), as #522 ran them: lh4b1-lh4b7. The lost lh4a1 is not part of
# the lineage (docs/acceptance/2026-11-09-held-out-lineage-522.md). With an empty tuple lh4 would not
# be a held-out lineage anywhere, and HELD_OUT would be exactly p1-study/1's.
LH4_ADMISSIONS: tuple[str, ...] = tuple(f'lh4b{n}' for n in range(1, 8))
HELD_OUT = dict(STUDY_1_HELD_OUT, lh4=LH4_ADMISSIONS) if LH4_ADMISSIONS else dict(STUDY_1_HELD_OUT)   # lineage -> admissions
STUDY_1_BOUNDARIES = {'lh1': 4, 'lh2': 3, 'lh3': 3}   # boundaries per #382 lineage (the #178 gate record); fixed, as `plan` resamples them
KIND = 'reobservation'   # the only label kind: needed-fact recall and query coverage are not scored (p1-study/3)
QUESTION_SCHEMA = 'p1-question/1'


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


def frozen_file(path: Path, what: str = 'held-out probes') -> tuple[list[dict], dict]:
    """(rows, record) of a JSON Lines file the `frozen.json` beside it (`p1-held-out-frozen/1`) lists a matching
    digest for: its repository-relative path and sha256, and the freeze's. Refused otherwise; errors name only the file."""
    path = Path(path)
    name = _relative(path)
    frozen = path.parent/'frozen.json'
    try:
        document = json.loads(frozen.read_text())
        digest = document['files'][path.name] if document.get('schema') == FROZEN_SCHEMA else None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        digest = None
    if not path.is_file() or digest is None or file_sha256(path) != digest:
        raise ScoreError(f'{name}: not a frozen {what} file (no matching digest in its directory\'s frozen.json)')
    return _lines(path), dict(path=name, sha256=digest, frozen=_relative(frozen), frozen_sha256=file_sha256(frozen))


def frozen_probes(paths: list[Path]) -> tuple[list[dict], list[dict]]:
    """(rows, probe_files): the rows of each held-out probes file, concatenated in the order given, and each
    file's record (`frozen_file`)."""
    rows, files = [], []
    for path in paths:
        more, record = frozen_file(path)
        rows += more
        files.append(record)
    return rows, files


def frozen_screen(questions: Path, screen: Path) -> dict:
    """The record of the screen's counts file: `questions-freeze` copied it beside the questions as `screen.json` and
    listed it in `frozen.json`, and `screen` must be those bytes. Errors name only the file."""
    frozen = Path(questions).parent/'frozen.json'
    try:
        digest = json.loads(frozen.read_text())['files']['screen.json']
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        digest = None
    if digest is None or not Path(screen).is_file() or file_sha256(screen) != digest:
        raise ScoreError(f'{_relative(screen)}: not the screen counts the questions were frozen with '
                         '(no matching screen.json digest in the questions\' frozen.json)')
    return dict(path=_relative(screen), sha256=digest)


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def question_rows(rows: list[dict], unit_rows: list[dict] | None = None) -> dict[str, dict]:
    """Probe id -> `p1-question/1` row; with `unit_rows`, exactly one question per unit. Errors give counts only."""
    out: dict[str, dict] = {}
    for row in rows:
        if (not isinstance(row, dict) or row.get('schema') != QUESTION_SCHEMA
                or set(row) != {'schema', 'probe', 'question', 'key'}
                or not all(isinstance(row[k], str) for k in ('probe', 'question', 'key')) or not row['question'].strip()):
            raise ScoreError(f'a question row is not a {QUESTION_SCHEMA} row')
        if row['probe'] in out:
            raise ScoreError('a probe has two questions')
        out[row['probe']] = row
    if unit_rows is not None and set(out) != {u['probe'] for u in unit_rows}:
        wanted = {u['probe'] for u in unit_rows}
        raise ScoreError(f'questions do not cover the units: {len(wanted - set(out))} units have none, '
                         f'{len(set(out) - wanted)} questions belong to no unit')
    return out


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


def rejudge_sample(unit_rows: list[dict], share: float = REJUDGE_SHARE) -> set[tuple]:
    """The seeded 20% of A's and B's labels that a fresh reader and grader repeat (the controls' labels are not
    in it). `share` 1.0 is every such label: development re-judges all of them."""
    keys = sorted((KIND, arm, rep, u['probe']) for u in unit_rows for arm, reps in ARMS.items() for rep in reps)
    return set(random.Random(REJUDGE_SEED).sample(keys, math.ceil(share * len(keys)))) if keys else set()


def labels(rows: list[dict]) -> tuple[dict[tuple, tuple[bool, bool]], dict[tuple, tuple[bool, bool]]]:
    """(kind, arm, repeat, item) -> (stated, answered), for the first pass and for the re-judging. The arms are
    A, B and the controls R, PW and PP; `answered` is false for a reader answer that was mechanically "not stated"."""
    first, second = {}, {}
    for row in rows:
        if row.get('type') != 'label':
            continue
        if (row.get('schema') != SCORE_SCHEMA or row.get('repeat') not in ARM_REPEATS.get(row.get('arm'), ())
                or row.get('kind') != KIND or not isinstance(row.get('item'), str)
                or not all(isinstance(row.get(k), bool) for k in ('stated', 'answered'))):
            raise ScoreError(f'label row outside the study: {row}')
        key = (row['kind'], row['arm'], row['repeat'], row['item'])
        target = second if row.get('rejudge') else first
        if key in target:
            raise ScoreError(f'item judged twice in one pass: {key}')
        target[key] = (row['stated'], row['answered'])
    return first, second


def _stated(found: dict[tuple, tuple[bool, bool]]) -> dict[tuple, bool]:
    return {key: value[0] for key, value in found.items()}


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
    wanted = {(KIND, arm, rep, u['probe']) for u in unit_rows for arm, reps in ARMS.items() for rep in reps}
    have = set(stated)
    if wanted != have:
        raise ScoreError(f'primary labels do not cover the study: {len(wanted - have)} missing, '
                         f'{len(have - wanted)} unexpected; first missing {sorted(wanted - have)[:3]}')
    if set(hours) != set(HELD_OUT):
        raise ScoreError(f'--hours must give in-play game hours for exactly the held-out lineages: {", ".join(HELD_OUT)}')
    total_hours = sum(hours[name] for name in HELD_OUT)
    out = {}
    for arm, reps in ARMS.items():
        for rep in reps:
            rows = [dict(lineage=u['lineage'], cluster=u['cluster'], stated=stated[(KIND, arm, rep, u['probe'])])
                    for u in unit_rows]
            n, hit = len(rows), sum(r['stated'] for r in rows)
            out[f'{arm}{rep}'] = dict(units=rows, n=n, stated=hit, recall=_rate(hit, n),
                                      undelivered_per_game_hour=_rate(n - hit, total_hours))
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


def agreement(first: dict, second: dict, arms: tuple[str, ...] | None = None) -> dict:
    """The chain's repeat variance over the re-judged labels (of `arms`, if given): percent and Cohen's kappa, and
    percent over the items that either pass answered (a reader answer that was not mechanically "not stated")."""
    keys = [k for k in sorted(second) if arms is None or k[1] in arms]
    pairs = [(first[k][0], second[k][0]) for k in keys]
    either = [(first[k][0], second[k][0]) for k in keys if first[k][1] or second[k][1]]
    return dict(n=len(pairs), percent=_rate(sum(x == y for x, y in pairs), len(pairs)), kappa=kappa(pairs),
                answered_either=dict(n=len(either), percent=_rate(sum(x == y for x, y in either), len(either))))


def chain_controls(unit_rows: list[dict], stated: dict[tuple, bool]) -> dict:
    """The Reference, each arm's recall over the units the Reference got wrong, the bias control and the positive
    control's sensitivity, from first-pass labels (docs/design/p1-study-3.md, "The Reference control", "The positive
    control", "The bias control"). Every unit needs a label for each control, and every label must belong to a unit."""
    probes = [u['probe'] for u in unit_rows]
    wanted = {(KIND, arm, 1, p) for p in probes for arm in CONTROLS}
    have = {key for key in stated if key[1] in CONTROLS}
    if wanted != have:
        raise ScoreError(f'Reference and positive-control labels do not cover the study: {len(wanted - have)} missing, '
                         f'{len(have - wanted)} unexpected')
    got = lambda arm, rep, p: stated[(KIND, arm, rep, p)]  # noqa: E731
    reference = {p: got('R', 1, p) for p in probes}
    wrong, right = [p for p in probes if not reference[p]], [p for p in probes if reference[p]]
    n = len(right)
    a_hits = sum(got('A', 1, p) for p in right)
    b_hits = sum(sum(got('B', r, p) for r in ARMS['B']) / len(ARMS['B']) for p in right)
    difference = (b_hits - a_hits) / n if n else None
    applies = n >= BIAS_MIN_UNITS
    return dict(
        reference=dict(n=len(probes), correct=len(right), recall=_rate(len(right), len(probes))),
        reference_wrong={f'{arm}{rep}': dict(units=len(wrong), stated=sum(got(arm, rep, p) for p in wrong),
                                             recall=_rate(sum(got(arm, rep, p) for p in wrong), len(wrong)))
                         for arm, reps in ARMS.items() for rep in reps},
        bias_control=dict(
            units=n, difference=difference, applies=applies, limit=BIAS_LIMIT, min_units=BIAS_MIN_UNITS,
            # Owner decision, 10 November 2026: only-A and only-B are counted per B repeat (A against B1, A against B2).
            only_a={f'B{r}': sum(got('A', 1, p) and not got('B', r, p) for p in right) for r in ARMS['B']},
            only_b={f'B{r}': sum(got('B', r, p) and not got('A', 1, p) for p in right) for r in ARMS['B']},
            # Owner decision, 10 November 2026: the flag is strictly greater than 0.10 (exactly 0.10 does not flag).
            flag=bool(applies and abs(difference) > BIAS_LIMIT),
            direction=None if not difference else 'B above A' if difference > 0 else 'A above B'),
        positive_control={arm: dict(units=len(probes), correct=sum(got(arm, 1, p) for p in probes),
                                    sensitivity=_rate(sum(got(arm, 1, p) for p in probes), len(probes)))
                          for arm in ('PW', 'PP')})


BIAS_NOTE = 'the received text\'s answer changed by arm'    # stated beside the outcome when the bias control flags


def score(probe_rows: list[dict], hours: dict[str, float], rows: list[dict], questions: list[dict],
          screen: dict, sentences: dict) -> dict:
    audits, costs = _validated(rows)
    unit_rows = units(primary_probes(probe_rows))
    question_rows(questions, unit_rows)
    if not (isinstance(screen, dict) and _count(screen.get('flagged_twice'))):
        raise ScoreError('--screen must be the counts of the screen\'s second run (flagged_twice)')
    if not (isinstance(sentences, dict) and _count(sentences.get('failed'))
            and sentences.get('units', len(unit_rows)) == len(unit_rows)):
        raise ScoreError('--sentences-counts must be the counts of the sentences step, one paraphrase for each unit (failed)')
    base = dict(schema=RESULT_SCHEMA, questions_flagged_twice=screen['flagged_twice'],
                probes=dict(listed=len(probe_rows), units=len(unit_rows),
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
    stated, restated = _stated(first), _stated(second)
    if set(restated) != rejudge_sample(unit_rows):
        raise ScoreError('re-judged labels must be exactly the seeded sample (tools.p1_analysis rejudge)')
    study = {key: value for key, value in stated.items() if key[1] in ARMS}
    figs = figures(unit_rows, hours, study, audits, costs)      # refuses A's and B's labels unless they cover the study
    refigs = figures(unit_rows, hours, {**study, **restated}, audits, costs)
    controls = chain_controls(unit_rows, stated)
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
    controls['positive_control']['paraphrases_failed_twice'] = sentences['failed']
    bias = controls['bias_control']
    # The bias control decides nothing: its flag is stated beside the outcome, whatever the outcome is, and outside
    # `decision`, which the controls never reach.
    note = {'outcome_note': f'{BIAS_NOTE}: {bias["direction"]}'} if bias['flag'] else {}
    return dict(base, figures=slim, judge_agreement=agreement(first, second), **controls, **note,
                decision=dict(go=go, outcome=outcome, mean_delta=main['delta'], robust_to_rejudging=robust,
                              primary=main, guards=guard))


def development_summary(rows: list[dict]) -> dict:
    """The two development checks' figures from the development chain's `p1-score/1` label rows: every unit's first-pass
    labels for A and B (repeat 1 each) and the Reference, PW and PP, and a re-judged twin for every A and B label
    (docs/design/p1-study-3.md, "Checks on development data"). Figures only; it decides nothing."""
    if any(not isinstance(row, dict) or row.get('type') != 'label' for row in rows):
        raise ScoreError('development rows are label rows only')
    names = set(HELD_OUT) | {run for runs in HELD_OUT.values() for run in runs}
    if any(row.get('lineage') in names or any(isinstance(row.get('item'), str) and row['item'].startswith(f'{name}-')
                                              for name in names) for row in rows):
        raise ScoreError('development labels may not belong to a held-out lineage')
    first, second = labels(rows)
    probes = sorted({key[3] for key in first})
    if not probes:
        raise ScoreError('no development labels')
    texts = {**DEVELOPMENT_ARMS, **{name: (1,) for name in CONTROLS}}
    wanted = {(KIND, arm, rep, p) for p in probes for arm, reps in texts.items() for rep in reps}
    if set(first) != wanted:
        raise ScoreError(f'development labels must give every unit one label for each of A, B, R, PW and PP: '
                         f'{len(wanted - set(first))} missing, {len(set(first) - wanted)} unexpected')
    twins = {key for key in wanted if key[1] in DEVELOPMENT_ARMS}
    if set(second) != twins:
        raise ScoreError(f'every A and B label must be re-judged, and nothing else: '
                         f'{len(twins - set(second))} missing, {len(set(second) - twins)} unexpected')

    def disagreement(arms: tuple[str, ...]) -> dict:     # `agreement` over the arms' re-judged labels, as counts and shares
        found = agreement(first, second, arms)
        n, either = found['n'], found['answered_either']
        wrong = n - round(found['percent'] * n)
        wrong_either = either['n'] - round(either['percent'] * either['n']) if either['n'] else None
        return dict(labels=n, disagreements=wrong, d=wrong / n, kappa=found['kappa'],
                    answered_either=dict(labels=either['n'], disagreements=wrong_either,
                                         d=None if wrong_either is None else wrong_either / either['n']))
    noise = {arm: disagreement((arm,)) for arm in DEVELOPMENT_ARMS}
    noise['pooled'] = disagreement(tuple(DEVELOPMENT_ARMS))
    d = noise['pooled']['d']
    # e = (1 - sqrt(1 - 2d)) / 2, the label error that independent errors make of a repeat disagreement d.
    noise['pooled']['label_error'] = (1 - math.sqrt(max(0.0, 1 - 2 * d))) / 2
    count = lambda arm: sum(first[(KIND, arm, 1, p)][0] for p in probes)  # noqa: E731
    n = len(probes)
    return dict(units=n, noise=noise,
                sensitivity={arm: dict(units=n, correct=count(arm), sensitivity=count(arm) / n) for arm in ('PW', 'PP')},
                reference=dict(units=n, correct=count('R'), recall=count('R') / n),
                recall={arm: dict(units=n, stated=count(arm), recall=count(arm) / n) for arm in DEVELOPMENT_ARMS},
                limits=dict(noise=NOISE_LIMIT, sensitivity=SENSITIVITY_FLOOR),
                # Exact integer comparisons (NOISE_LIMIT is 1/10, SENSITIVITY_FLOOR 85/100): d <= 0.10, correct / units >= 0.85.
                noise_ok=bool(noise['pooled']['disagreements'] * 10 <= noise['pooled']['labels']),
                sensitivity_ok=bool(all(count(arm) * 100 >= 85 * n for arm in ('PW', 'PP'))))


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


def _power(rng: random.Random, dev: dict, structure, cluster_mean: float | None, bias: float, delta: float,
           flip: float = FLIP, sensitivity: tuple[float, float] | None = None) -> bool:
    """One simulated study. `flip` is the label error. With `sensitivity` (A's, B's), every label made stated is kept
    with that arm's probability (docs/design/p1-study-3.md, "Power at the measured values"); no draw is made without it,
    so the default stream is unchanged."""
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
        label = truth != (rng.random() < flip)
        if label and sensitivity is not None:
            label = rng.random() < sensitivity[key.startswith('B')]
        return label or (key.startswith('B') and rng.random() < bias)
    figs = {}
    for key in ('A1', *(f'B{r}' for r in ARMS['B'])):
        rows = [dict(lineage=name, cluster=c, stated=judged(key, latent[(name, c)][key])) for name, c in layout]
        figs[key] = dict(units=rows, recall=sum(r['stated'] for r in rows) / len(rows))
    return primary(figs['A1'], [figs[f'B{r}'] for r in ARMS['B']], bound_if_needed=True)['holds']


def simulate(simulations: int = SIMULATIONS, seed: int = SEED, layout: list[tuple[str, str]] | None = None,
             flip: float | None = None, sensitivity: tuple[float, float] | None = None) -> dict:
    """The gate's simulation. `flip` and `sensitivity` are off by default, so every committed figure is unchanged;
    a run that sets either records them under `varied`."""
    dev = development()
    rng = random.Random(seed)
    error = FLIP if flip is None else flip
    varied = {} if flip is None and sensitivity is None else dict(varied=dict(
        flip=error, sensitivity=None if sensitivity is None else list(sensitivity)))
    if layout is not None:
        variants = {'held-out structure': {f'{d:.2f}': round(sum(_power(rng, dev, layout, None, 0.0, d, error, sensitivity)
                                                                  for _ in range(simulations)) / simulations, 3)
                                           for d in DELTAS}}
        return dict(schema=POWER_SCHEMA, seed=seed, simulations=simulations, units=len(layout),
                    clusters=len(set(layout)),
                    cluster_sizes=cluster_sizes([dict(lineage=name, cluster=c) for name, c in layout]),
                    probability_of_go=variants,
                    gate=gate(variants['held-out structure']), **varied)
    shape = held_out_shape()
    variants = {}
    for mean, bias in VARIANTS:
        variants[f'cluster_mean={mean}, judge_bias={bias}'] = {
            f'{d:.2f}': round(sum(_power(rng, dev, shape, mean, bias, d, error, sensitivity)
                                  for _ in range(simulations)) / simulations, 3)
            for d in DELTAS}
    return dict(schema=POWER_SCHEMA, seed=seed, simulations=simulations, shape=shape, development=dev,
                assumptions=dict(lineage_sd=LINEAGE_SD, effect_sd=EFFECT_SD, repeat_sd=REPEAT_SD, flip=FLIP,
                                 planning=f'cluster_mean={CLUSTER_MEAN}, judge_bias=0.0'),
                probability_of_go=variants, gate=gate(variants[f'cluster_mean={CLUSTER_MEAN}, judge_bias=0.0']),
                note='Primary criterion only; guards and re-judging are not simulated.', **varied)


# p1-study/2's planning simulation (docs/design/p1-study-3.md#power): #382's frozen held-out
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
    if any(row.get('lineage') not in STUDY_1_HELD_OUT for row in held_out):
        raise ScoreError("plan takes only #382's held-out probes (lh1-lh3); lh4 is simulated, never read")
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


BATCH_STEPS = ('batches', 'parse', 'screen', 'sentences', 'questions-freeze')   # the answer-key chain: tools/p1_batches.py


def main(argv=None) -> int:
    given = sys.argv[1:] if argv is None else list(argv)
    if given[:1] and given[0] in BATCH_STEPS:
        from tools import p1_batches    # imports this module, so it is loaded only for these steps
        return p1_batches.main(given)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=('simulate', 'plan', 'units', 'rejudge', 'score', 'development'))
    parser.add_argument('--probes', type=Path, action='append',
                        help='a held-out p1-probes/1 file; simulate, units, rejudge and score take one per held-out '
                             'directory (each must match its frozen.json), plan takes exactly one')
    parser.add_argument('--scores', type=Path)
    parser.add_argument('--hours', type=Path, help='JSON object: held-out lineage -> in-play game hours')
    parser.add_argument('--questions', type=Path, help='score: the frozen p1-question/1 file (checked against its frozen.json)')
    parser.add_argument('--screen', type=Path, help='score: the screen.json that questions-freeze copied beside the questions')
    parser.add_argument('--sentences-counts', type=Path, help='score: the counts.json of the `sentences` step')
    parser.add_argument('--flip', type=float, help=f'simulate: the label error instead of {FLIP}')
    parser.add_argument('--sensitivity', type=float, nargs=2, metavar=('A', 'B'),
                        help='simulate: keep every stated label with this probability, for arm A and for arm B')
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
        # The gate file is chosen by the lineages the probes cover, never by how many files were given.
        lineages = {row['lineage'] for row in probe_rows} if probe_paths else set()
        study_1 = bool(lineages) and lineages <= set(STUDY_1_HELD_OUT)
        if args.out:
            out = args.out
        elif not probe_paths:
            out = ROOT/'data'/'evaluation'/'p1'/'power.json'
        else:
            out = POWER_STUDY_1 if study_1 else POWER_STUDY_2
        if probe_paths and out.resolve() == POWER_STUDY_1.resolve() and not study_1:
            parser.error(f'{_relative(POWER_STUDY_1)} is p1-study/1\'s gate (lh1-lh3 only); probes covering lh4 write '
                         f'{_relative(POWER_STUDY_2)}')
        if probe_paths and out.resolve() == POWER_STUDY_2.resolve() and lineages != set(HELD_OUT):
            parser.error(f'{_relative(POWER_STUDY_2)} is p1-study/2\'s gate: the probes must cover exactly '
                         f'{", ".join(HELD_OUT)}')
        varied = {}
        if args.flip is not None:
            varied['flip'] = args.flip
        if args.sensitivity is not None:
            varied['sensitivity'] = tuple(args.sensitivity)
        if varied:    # a variant run never replaces a committed gate: its output goes outside data/
            if not args.out or args.out.resolve().is_relative_to((ROOT/'data').resolve()):
                parser.error('--flip and --sensitivity need --out, outside data/ (they never write a committed gate file)')
            if args.flip is not None and not 0 <= args.flip < 0.5:
                parser.error('--flip must be in [0, 0.5)')
            if args.sensitivity is not None and not all(0 < s <= 1 for s in args.sensitivity):
                parser.error('--sensitivity values must be in (0, 1]')
        result = simulate(layout=layout, **varied)
        if probe_files and not study_1:    # p1-study/1's tracked gate output keeps its recorded shape
            result['probe_files'] = probe_files
        summary = result['probability_of_go']
    elif args.step == 'plan':
        if len(probe_paths) != 1:
            parser.error('plan needs exactly one --probes (the frozen #382 held-out probes)')
        try:
            result = plan(probe_rows)
        except ScoreError as error:
            parser.error(str(error))
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
    elif args.step == 'development':
        if not (args.scores and args.out):
            parser.error('development needs --scores and --out')
        if not args.out.resolve().is_relative_to((ROOT/'.runtime').resolve()):
            parser.error('development --out must be under the repository\'s .runtime/ (its figures stay out of the tracked tree)')
        if args.out.exists():
            parser.error('--out exists: the summary is written once')
        try:
            result = development_summary(_lines(args.scores))
        except ScoreError as error:
            parser.error(str(error))
        out, summary = args.out, result
    else:
        if not (probe_paths and args.scores and args.hours and args.questions and args.screen and args.sentences_counts):
            parser.error('score needs --probes, --scores, --hours, --questions, --screen and --sentences-counts')
        if {row['lineage'] for row in probe_rows} != set(HELD_OUT):
            parser.error(f'score needs probes covering exactly the held-out lineages: {", ".join(HELD_OUT)}')
        try:
            asked, question_file = frozen_file(args.questions, 'questions')
            screen_file = frozen_screen(args.questions, args.screen)
        except ScoreError as error:
            parser.error(str(error))
        result = dict(score(probe_rows, json.loads(args.hours.read_text()), _lines(args.scores), asked,
                            json.loads(args.screen.read_text()), json.loads(args.sentences_counts.read_text())),
                      probe_files=probe_files, question_file=question_file, screen_file=screen_file)
        out = args.out or ROOT/'data'/'evaluation'/'p1'/'result.json'
        summary = result['decision']['outcome']
        if 'outcome_note' in result:
            summary = f'{summary} ({result["outcome_note"]})'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
