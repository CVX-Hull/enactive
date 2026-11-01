#!/usr/bin/env python3
"""#329 stage 1: the subgoal level's offline fixtures on recorded traces ($0, no provider, no game).

Recorded runs are test inputs, not a supported format. Each run's operations are copied
through the current store API into a fresh `computer-session/2` store, and the current
log projection reads them back. The current wake rules then replay over the recorded
timeline, with each pass's request latencies drawn from the runs' own recorded provider
latencies, to estimate pass, commit and discard rates for given K, S and fractions. This
measures mechanism coupling only; it says nothing about intent quality or play.
"""
from __future__ import annotations

import argparse
import bisect
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.computer.protocol import canonical
from harness.computer.store import SessionStore
from tools.level_schedule import LevelSchedule


def wall(value: str) -> float:
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(run: Path) -> dict:
    """One recorded single-actor run, read-only and immutable."""
    database = sqlite3.connect(f'file:{run / "session.sqlite3"}?mode=ro&immutable=1', uri=True)
    try:
        rows = database.execute('SELECT id,actor,kind,created_wall,deadline,input_json,final_json '
                                'FROM operations ORDER BY rowid').fetchall()
    finally:
        database.close()
    if len({row[1] for row in rows}) != 1:
        raise ValueError(f'{run}: expected one actor')
    events = [json.loads(line) for line in (run / 'actors/001/host.jsonl').read_text().splitlines() if line.strip()]
    starts = {e['request_id']: wall(e['wall_time']) for e in events if e.get('type') == 'request-start'}
    ends = {e['request_id']: wall(e['wall_time']) for e in events if e.get('type') == 'response-complete'}
    latencies = [ends[r] - starts[r] for r in starts if r in ends]
    return dict(run=run.name, rows=rows, request_walls=sorted(starts.values()), latencies=latencies,
                inputs=dict(database=sha256(run / 'session.sqlite3'), trace=sha256(run / 'actors/001/host.jsonl')))


def projection_check(recorded: dict) -> dict:
    """Copy the operations into a current store and read them back through the real projection."""
    rows = recorded['rows']
    with tempfile.TemporaryDirectory(prefix='level-offline-') as temporary:
        directory = Path(temporary)
        limits = dict(max_inputs=10 ** 6, max_requests=10 ** 6, max_frames=10 ** 6, max_bytes=2 ** 40)
        store = SessionStore(directory, 'f' * 32, limits, 1e12)
        try:
            actor = rows[0][1]
            store.add_actor(actor, 'fixture-token-hash')
            for identity, _, kind, created, deadline, actions, final in rows:
                decoded = json.loads(actions)
                operation = dict(operation_id=identity, actor_id=actor, kind=kind, created_wall=created,
                                 deadline_monotonic=deadline)
                store.begin(operation, decoded, sum(a['type'] != 'wait' for a in decoded or []))
                if final is not None:
                    store.finish(json.loads(final))
            entries, after = [], 0
            while True:
                page = store.actor_log(actor, after, 50)
                if not page:
                    break
                entries.extend(page)
                after = page[-1]['position']
            counts = store.actor_counts(actor)
        finally:
            store.close()
    expected = [(r[0], r[2], json.loads(r[6])['source']['source_id'] if r[6] and json.loads(r[6]).get('source') else None)
                for r in rows]
    observed = [(e['operation_id'], e['kind'], e['source_id']) for e in entries]
    page_bytes = [len(canonical(entries[i:i + 50]).encode()) for i in range(0, len(entries), 50)]
    return dict(operations=len(rows), entries=len(entries), counts=list(counts), matches_recorded=observed == expected,
                positions_contiguous=[e['position'] for e in entries] == list(range(1, len(entries) + 1)),
                pending=sum(e['status'] == 'pending' for e in entries), max_page_bytes=max(page_bytes, default=0))


def simulate(recorded: dict, pool: list[float], *, k: int, s: int, fractions: tuple[float, ...], requests_per_pass: int,
             allowance: int, rng: random.Random) -> dict:
    """Replay the wake rules over one recorded timeline under level interface v2 (#340).

    The driver pushes the log projection at launch, so a pass binds its position when it
    starts (`read = now`), and its commit or abstain lands after its last response with no
    closing turn (`commit = now + sum(latencies)`). `requests_per_pass` is the total request
    count (about 2-3). No host-startup term is added: the recorded traces hold no level host.
    """
    created = [r[3] for r in recorded['rows']]
    is_input = [r[2] == 'input' for r in recorded['rows']]
    input_walls = [w for w, i in zip(created, is_input) if i]
    requests = recorded['request_walls']
    ready = requests[0] if requests else created[0]
    schedule = LevelSchedule(k, fractions, allowance)
    busy_until, passes, moved, censored = ready, [], [], 0
    for index, now in enumerate(created):
        if now < busy_until:
            continue
        entries, inputs = index + 1, sum(is_input[:index + 1])
        attempts = bisect.bisect_right(requests, now)
        reason = schedule.due(entries=entries, inputs=inputs, attempts=attempts, open_records=0)
        if reason is None:
            continue
        latencies = [rng.choice(pool) for _ in range(requests_per_pass)]
        read = now
        commit = busy_until = now + sum(latencies)
        if commit > input_walls[-1]:
            # The recording ends before this commit; its staleness is unobserved, not zero.
            censored += 1
            continue
        bound = bisect.bisect_right(input_walls, read)
        during = bisect.bisect_right(input_walls, commit) - bound
        moved.append(during)
        passes.append(during < s)
    return dict(passes=len(passes), commits=sum(passes), discards=len(passes) - sum(passes), censored=censored,
                moved=moved, level_requests=(len(passes) + censored) * requests_per_pass, actor_requests=len(requests))


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def stage(runs: list[Path], *, k: int, s: int, fractions: tuple[float, ...], requests_per_pass: int,
          replicates: int, seed: int, latency_scale: float = 1.) -> dict:
    """`latency_scale` multiplies recorded actor latencies, since level requests may write longer proposals."""
    recorded = [load(run) for run in runs]
    pool = [latency * latency_scale for r in recorded for latency in r['latencies']]
    result = dict(schema='level-offline-stage/2', parameters=dict(k=k, s=s, fractions=list(fractions),
                  requests_per_pass=requests_per_pass, replicates=replicates, seed=seed, latency_scale=latency_scale),
                  latency_pool=dict(count=len(pool), median=statistics.median(pool), p95=quantile(pool, .95)),
                  runs=[])
    rng = random.Random(seed)
    for r in recorded:
        allowance = max(1, len(r['request_walls']))
        sims = [simulate(r, pool, k=k, s=s, fractions=fractions, requests_per_pass=requests_per_pass,
                         allowance=allowance, rng=rng) for _ in range(replicates)]
        rates = [x['commits'] / x['passes'] for x in sims if x['passes']]
        moved = [m for x in sims for m in x['moved']]
        inputs = sum(row[2] == 'input' for row in r['rows'])
        span = r['rows'][-1][3] - r['rows'][0][3]
        result['runs'].append(dict(run=r['run'], inputs=r['inputs'], projection=projection_check(r),
            actor_inputs=inputs, actor_requests=len(r['request_walls']),
            input_interval_seconds=span / max(1, inputs - 1),
            passes_mean=statistics.fmean(x['passes'] for x in sims),
            censored_mean=statistics.fmean(x['censored'] for x in sims),
            commit_rate=dict(mean=statistics.fmean(rates) if rates else None, p05=quantile(rates, .05),
                             p95=quantile(rates, .95)),
            inputs_during_pass=dict(median=quantile(moved, .5), p95=quantile(moved, .95), max=max(moved, default=None)),
            level_request_overhead=statistics.fmean(x['level_requests'] / max(1, x['actor_requests']) for x in sims)))
    commits = sum(x['commit_rate']['mean'] * x['passes_mean'] for x in result['runs'] if x['commit_rate']['mean'] is not None)
    total = sum(x['passes_mean'] for x in result['runs'])
    result['pooled_commit_rate'] = commits / total if total else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True, help='A recorded single-actor run directory')
    parser.add_argument('--k', type=int, default=10)
    parser.add_argument('--s', type=int, default=10)
    parser.add_argument('--fractions', type=float, nargs='*', default=[.25, .5, .75])
    parser.add_argument('--requests-per-pass', type=int, default=3)
    parser.add_argument('--replicates', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=329)
    parser.add_argument('--latency-scale', type=float, default=1.)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.runtime'):
        parser.error('Write offline-stage outputs under the project .runtime directory')
    value = stage(args.run, k=args.k, s=args.s, fractions=tuple(args.fractions), requests_per_pass=args.requests_per_pass,
                  replicates=args.replicates, seed=args.seed, latency_scale=args.latency_scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(output=str(output), pooled_commit_rate=value['pooled_commit_rate']), indent=2))


if __name__ == '__main__':
    main()
