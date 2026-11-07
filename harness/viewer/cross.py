"""Cross-run payloads: change records, failure modes, survival comparison and cohort exploration.

Everything reads the evaluation stores and the git-tracked human data under `data/evaluation/`. Statistics come
from `harness.evaluation.core.survival` (Kaplan-Meier with Greenwood bounds, restricted mean, bootstrap) and numpy
(seeded bootstrap of means and medians). Lost runs (provider or custody losses) are excluded from scored
comparisons and listed. Nothing here writes or gates anything.
"""
from __future__ import annotations

from fnmatch import fnmatch
import statistics
from typing import Callable, Sequence

import numpy as np

from harness.evaluation.core.records import loads
from harness.evaluation.core.survival import Observation, bootstrap_rmst, kaplan_meier, restricted_mean

from .catalog import Catalog, RunInfo, ViewError
from .views import run_row, scalar

SEED = 383
RESAMPLES = 4000
MIN_MEDIAN_N = 5
DERIVED_FAILURES = {'stall': 'stall', 'ineffective_repeat': 'ineffective_repeat', 'tool_refused': 'tool_refused', 'death': 'death'}
PRE_DEATH_DECISIONS = 12


def matches(info: RunInfo, patterns: Sequence[str]) -> bool:
    return any(fnmatch(info.run, p) or fnmatch(info.session, p) for p in patterns)


def metric_value(info: RunInfo, name: str, key: str = '') -> float | None:
    return scalar(info.metric(name, key))


def quartiles(values: Sequence[float]) -> tuple[float, float]:
    low, _, high = np.percentile(values, [25, 50, 75])
    return float(low), float(high)


def bootstrap_difference(a: Sequence[float], b: Sequence[float]) -> dict:
    """Mean of `a` minus mean of `b` with a seeded percentile bootstrap interval."""
    if not a or not b:
        return dict(difference=None, low=None, high=None, resamples=0)
    rng = np.random.default_rng(SEED)
    first, second = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    draws = rng.choice(first, (RESAMPLES, len(first))).mean(axis=1) - rng.choice(second, (RESAMPLES, len(second))).mean(axis=1)
    low, high = np.percentile(draws, [2.5, 97.5])
    return dict(difference=float(first.mean() - second.mean()), low=float(low), high=float(high), resamples=RESAMPLES)


def bootstrap_median(values: Sequence[float]) -> dict:
    rng = np.random.default_rng(SEED)
    data = np.asarray(values, dtype=float)
    medians = np.median(rng.choice(data, (RESAMPLES, len(data))), axis=1)
    low, high = np.percentile(medians, [2.5, 97.5])
    return dict(low=float(low), high=float(high), resamples=RESAMPLES)


def group_stats(items: list[tuple[RunInfo, float | None]]) -> dict:
    values = [v for _, v in items if v is not None]
    return dict(runs=[dict(run=i.run, session=i.session, value=v) for i, v in items], n=len(values),
        mean=float(np.mean(values)) if values else None, median=float(np.median(values)) if values else None)


def computed_verdict(change: dict, arm: dict, base: dict, diff: dict, uptake: dict | None) -> str:
    """`untested` without uptake; `moved` or `wrong_way` when the interval excludes zero; else `no_effect_detected`."""
    if change.get('uptake_metric') is None or uptake is None or not uptake['total']:
        return 'untested'
    if diff['low'] is None or arm['n'] < 2 or base['n'] < 2:
        return 'no_effect_detected'
    better_low = change['target_metric']['direction'] == 'lower'
    if diff['high'] < 0 or diff['low'] > 0:
        improved = diff['high'] < 0 if better_low else diff['low'] > 0
        return 'moved' if improved else 'wrong_way'
    return 'no_effect_detected'


def changes(catalog: Catalog, runs: list[RunInfo]) -> dict:
    out = []
    for change in catalog.changes():
        target = change['target_metric']
        keep_lost = target['name'].startswith('run.')

        def pick(patterns: Sequence[str], name: str, key: str = '') -> list[tuple[RunInfo, float | None]]:
            return [(r, metric_value(r, name, key)) for r in runs if matches(r, patterns) and (keep_lost or not r.lost)]
        arm_items = pick(change.get('arms', []), target['name'], target.get('key', ''))
        base_items = pick(change.get('baseline', []), target['name'], target.get('key', ''))
        arm, base = group_stats(arm_items), group_stats(base_items)
        diff = bootstrap_difference([v for _, v in arm_items if v is not None], [v for _, v in base_items if v is not None])
        uptake = None
        uptake_spec = change.get('uptake_metric')
        if uptake_spec is not None:
            per = [(r, metric_value(r, uptake_spec['name'], uptake_spec.get('key', '')) or 0.0)
                for r in runs if matches(r, change.get('arms', [])) and not r.lost]
            uptake = dict(metric=uptake_spec, runs=[dict(run=r.run, value=v) for r, v in per], n=len(per),
                with_uptake=sum(1 for _, v in per if v > 0), total=sum(v for _, v in per))
        guards = []
        for guard in change.get('guards', []):
            name, key = guard['name'], guard.get('key', '')
            guards.append(dict(metric=guard, arm=group_stats(pick(change.get('arms', []), name, key)),
                baseline=group_stats(pick(change.get('baseline', []), name, key))))
        lost = [r.run for r in runs if r.lost and matches(r, [*change.get('arms', []), *change.get('baseline', [])])]
        out.append(dict(change, target=dict(metric=target, arm=arm, baseline=base, difference=diff,
            excluded=[] if keep_lost else lost), uptake=uptake, guard_values=guards,
            computed_verdict=computed_verdict(change, arm, base, diff, uptake)))
    return dict(changes=out, seed=SEED, resamples=RESAMPLES)


def failures(catalog: Catalog, runs: list[RunInfo]) -> dict:
    """Failure modes from derived events and human labels, with decisions and dollars inside each occurrence."""
    taxonomy = {c['code']: c for c in catalog.taxonomy().get('codes', [])}
    occurrences: dict[str, list[dict]] = {code: [] for code in taxonomy}
    by_session = {r.session: r for r in runs}
    for info in runs:
        connection = catalog.connect(info)
        try:
            kinds = ','.join(repr(k) for k in DERIVED_FAILURES)
            rows = connection.execute(
                f'SELECT e.id, e.seq_start, e.seq_end, e.kind, e.source, e.confidence, a.decision, b.decision, a.dollars, b.dollars '
                f'FROM events e LEFT JOIN steps a ON a.seq=e.seq_start LEFT JOIN steps b ON b.seq=e.seq_end '
                f'WHERE e.kind IN ({kinds}) ORDER BY e.seq_start').fetchall()
        finally:
            connection.close()
        for event_id, start, end, kind, source, confidence, d0, d1, c0, c1 in rows:
            span = kind in ('stall', 'ineffective_repeat')
            occurrences.setdefault(DERIVED_FAILURES[kind], []).append(dict(run=info.run, session=info.session, event_id=event_id,
                seq_start=start, seq_end=end, decision_from=d0, decision_to=d1,
                decisions=(d1 - d0 + 1) if span and d0 is not None and d1 is not None else 0,
                dollars=max(0.0, (c1 or 0.0) - (c0 or 0.0)) if span else 0.0, source=source, confidence=confidence))
        if info.survival and info.survival.get('censor_reason') in ('infrastructure', 'custody'):
            occurrences.setdefault('infrastructure_loss', []).append(dict(run=info.run, session=info.session, event_id=None,
                seq_start=None, seq_end=None, decision_from=0, decision_to=info.decisions, decisions=info.decisions,
                dollars=info.dollars, source='derived', confidence=None, reason=info.survival.get('censor_reason')))
    for label in catalog.labels():
        info = by_session.get(label.get('session'))
        if info is None or label.get('verdict') != 'confirm':
            continue
        occurrences.setdefault(label['code'], []).append(dict(run=info.run, session=info.session, event_id=None,
            seq_start=label.get('seq_start'), seq_end=label.get('seq_end'), decision_from=None, decision_to=None, decisions=0,
            dollars=0.0, source='human', confidence=None, target=label.get('target'), note=label.get('note'),
            label=label['id']))
    modes = []
    for code, rows in occurrences.items():
        entry = taxonomy.get(code, dict(code=code, name=code, definition='', examples=[]))
        modes.append(dict(entry, occurrences=len(rows), runs=len({r['session'] for r in rows}),
            decisions=sum(r['decisions'] for r in rows), dollars=sum(r['dollars'] for r in rows),
            sources=sorted({r['source'] for r in rows}), items=rows))
    modes.sort(key=lambda m: (m['code'] != 'death', -m['dollars'], m['code']))
    return dict(taxonomy_version=catalog.taxonomy().get('version'), failures=modes)


def parse_runs(catalog: Catalog, selector: str | None) -> list[RunInfo]:
    runs = catalog.runs()
    if not selector:
        return runs
    wanted = [s for s in selector.split(',') if s]
    chosen = [r for r in runs if r.session in wanted or r.run in wanted]
    missing = set(wanted) - {r.session for r in chosen} - {r.run for r in chosen}
    if missing:
        raise ViewError(404, 'unknown_run', ','.join(sorted(missing)))
    return chosen


def compare(catalog: Catalog, group: str, selector: str | None, horizon: float) -> dict:
    if group not in ('arm', 'start'):
        raise ViewError(400, 'bad_group', 'group must be arm or start')
    if not horizon > 0:
        raise ViewError(400, 'bad_horizon')
    groups: dict[str, list[RunInfo]] = {}
    excluded = []
    for info in parse_runs(catalog, selector):
        label = info.labels.get(group) or 'unlabelled'
        if info.lost or info.survival is None:
            excluded.append(dict(run=info.run, group=label, reason=(info.survival or {}).get('censor_reason') or 'no_survival_reading'))
            continue
        groups.setdefault(str(label), []).append(info)
    out = {}
    for label, members in sorted(groups.items()):
        observations = [Observation(float(m.survival['hours']), m.survival['outcome'] == 'died') for m in members]
        curve = kaplan_meier(observations)
        median = next((t for t, s in zip(curve['times'], curve['survival']) if s <= 0.5), None)
        longest = max(o.time for o in observations)
        if horizon <= longest:
            rmst = dict(horizon=horizon, value=restricted_mean(curve['times'], curve['survival'], horizon),
                **bootstrap_rmst(observations, horizon, resamples=2000, seed=SEED))
        else:
            rmst = dict(horizon=horizon, value=None, reason='horizon_beyond_observed_range', longest=longest)
        out[label] = dict(n=len(members), deaths=sum(o.died for o in observations), censored=sum(not o.died for o in observations),
            curve=dict(curve, times=[0.0, *curve['times']], survival=[1.0, *curve['survival']],
                lower=[1.0, *curve['lower']], upper=[1.0, *curve['upper']]),
            median=median if median is not None else 'not_reached', rmst=rmst, runs=[m.run for m in members],
            versions=dict(source_commits=sorted({str(m.facts.get('source_commit')) for m in members}),
                models=sorted({str(m.facts.get('model')) for m in members}), efforts=sorted({str(m.facts.get('effort')) for m in members}),
                binding_versions=sorted({str(m.meta.get('binding_version')) for m in members}),
                starts={s: sum(1 for m in members if m.labels.get('start') == s)
                    for s in sorted({str(m.labels.get('start')) for m in members})}))
    return dict(group=group, horizon_hours=horizon, groups=out, excluded=excluded, seed=SEED)


def explore(catalog: Catalog, arm: str | None, start: str | None, outcome: str | None, metric: str | None) -> dict:
    runs = catalog.runs()

    def keep(info: RunInfo) -> bool:
        value = info.survival or {}
        state = 'lost' if info.lost else value.get('outcome')
        return (not arm or info.labels.get('arm') == arm) and (not start or info.labels.get('start') == start) \
            and (not outcome or state == outcome or (outcome == 'infra' and info.lost))
    cohort = [r for r in runs if keep(r)]
    name, _, key = (metric or 'survival.game_hours').partition(':')
    values = [(r, metric_value(r, name, key)) for r in cohort]
    numbers = [v for _, v in values if v is not None]
    stats = dict(metric=metric or 'survival.game_hours', n=len(numbers), median=float(np.median(numbers)) if numbers else None)
    if numbers:
        low, high = quartiles(numbers)
        stats.update(iqr=[low, high])
    stats['bootstrap'] = bootstrap_median(numbers) if len(numbers) >= MIN_MEDIAN_N else None
    stats['bootstrap_note'] = None if len(numbers) >= MIN_MEDIAN_N else f'needs n >= {MIN_MEDIAN_N}'
    rows = [dict(run_row(r), value=v) for r, v in values]
    before = []
    for info in cohort:
        if not (info.survival and info.survival.get('outcome') == 'died'):
            continue
        connection = catalog.connect(info)
        try:
            death = connection.execute("SELECT seq_start FROM events WHERE kind='death' ORDER BY seq_start DESC LIMIT 1").fetchone()
            if death is None:
                continue
            decision_rows = connection.execute(
                "SELECT s.decision, MAX(s.seq) FROM steps s WHERE s.seq <= ? AND s.decision IS NOT NULL GROUP BY s.decision "
                "ORDER BY s.decision DESC LIMIT ?", (death[0], PRE_DEATH_DECISIONS + 1)).fetchall()
            sequence = []
            for decision, seq in reversed(decision_rows):
                mode, keys = connection.execute('SELECT s.mode, r.value FROM steps s LEFT JOIN readings r ON r.seq=s.seq AND '
                    "r.reader='core.input' WHERE s.seq=?", (seq,)).fetchone()
                threat = connection.execute("SELECT value FROM readings WHERE seq=? AND reader='threat'", (seq,)).fetchone()
                value = loads(threat[0]) if threat and threat[0] else None
                sequence.append(dict(decision=decision, seq=seq, mode=mode, keys=loads(keys) or [],
                    threat=value.get('bucket') if isinstance(value, dict) else None,
                    creatures=value.get('count') if isinstance(value, dict) else None))
        finally:
            connection.close()
        before.append(dict(run=info.run, session=info.session, start=info.labels.get('start'), decisions=sequence))
    return dict(cohort=rows, stats=stats, before_death=before)
