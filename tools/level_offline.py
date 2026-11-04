#!/usr/bin/env python3
"""#329 stage 1: level v4's offline fixtures on recorded traces ($0, no provider, no game).

Recorded runs are test inputs, not a supported format. Each run's operations are copied
through the current store API into a fresh store, and the current log projection reads them
back. The production episode cutter then cuts the recorded timeline into episodes from the
run's retained captures, and the recorder backlog and the level's wake rules replay over it,
with each pass's request latencies drawn from the runs' own recorded provider latencies, to
estimate backlog drops, commit and discard rates for given theta, m, C, S and backlog. This
measures mechanism coupling only; it says nothing about intent quality or play.
"""
from __future__ import annotations

import argparse
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
from tools.episode_cutter import Episode, EpisodeCutter, thumbnail


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
    return dict(run=run.name, run_directory=run, rows=rows, request_walls=sorted(starts.values()), latencies=latencies,
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


def cut_run(recorded: dict, *, theta: float, m: int, cap: int) -> list[tuple[Episode, float]]:
    """Cut a recorded run into episodes with the production cutter; each with the wall time it closed.

    The thumbnails come from the run's retained captures. A content cut closes when the crossing input's result
    arrives, a cap cut at the capping input, and the session edge at the last operation.
    """
    sources = recorded['run_directory'] / 'sources'
    thumbs: dict[str, bytes] = {}

    def thumb(source_id: str) -> bytes:
        if source_id not in thumbs:
            thumbs[source_id] = thumbnail((sources / f'{source_id}.png').read_bytes())
        return thumbs[source_id]
    cutter = EpisodeCutter(theta, m, cap, thumb)
    closed: list[tuple[Episode, float]] = []
    for position, (_, _, kind, created, _, _, final) in enumerate(recorded['rows'], 1):
        source = (json.loads(final).get('source') or {}).get('source_id') if final else None
        closed += [(episode, created) for episode in cutter.feed(dict(position=position, kind=kind, source_id=source), None)]
    tail = cutter.flush()
    if tail is not None:
        closed.append((tail, recorded['rows'][-1][3]))
    return closed


def simulate(recorded: dict, pool: list[float], *, theta: float, m: int, cap: int, s: int, backlog: int,
             recorder_requests: int, level_requests: int, rng: random.Random,
             episodes: list[tuple[Episode, float]] | None = None) -> dict:
    """Replay level v4's mechanism over one recorded timeline: cutter, recorder queue and level wakes.

    A closed episode joins the recorder's FIFO backlog; one recorder pass runs at a time and takes the sum of
    `recorder_requests` latencies drawn from `pool`, and the oldest waiting episode settles as dropped when more than
    `backlog` wait. Every settle wakes the level (coalescing while a pass runs; the budget fractions only name a wake
    that a settle already caused, so they add none). A level pass binds the furthest settled episode end when it
    starts and commits after `level_requests` latencies; the commit lands when fewer than `s` actor inputs have moved
    past that bound. No host-startup term is added: the recordings hold no recorder or level host.
    """
    rows = recorded['rows']
    input_walls = [(position, r[3]) for position, r in enumerate(rows, 1) if r[2] == 'input']
    cuts = cut_run(recorded, theta=theta, m=m, cap=cap) if episodes is None else episodes
    end = input_walls[-1][1]

    def moved_past(position: int, at: float) -> int:
        return sum(p > position and w <= at for p, w in input_walls)

    def draw(count: int) -> float:
        return sum(rng.choice(pool) for _ in range(count))
    queue: list[Episode] = []
    recorder: tuple[float, Episode] | None = None
    level: tuple[float, int] | None = None
    recorder_passes = dropped = settled_end = level_passes = censored = 0
    pending_wake = False
    passes: list[bool] = []
    moved: list[int] = []
    timeline = sorted(((w, e) for e, w in cuts), key=lambda item: item[0])
    index = 0

    def start_recorder(now: float) -> None:
        nonlocal recorder, recorder_passes
        if recorder is None and queue:
            recorder_passes += 1
            recorder = (now + draw(recorder_requests), queue.pop(0))

    def wake(now: float) -> None:
        nonlocal pending_wake, level, level_passes
        if level is not None:
            pending_wake = True
            return
        pending_wake = False
        level_passes += 1
        level = (now + draw(level_requests), settled_end)

    while True:
        # The next event: a close, the recorder finishing or the level committing (a close sorts first on a tie).
        upcoming = []
        if index < len(timeline):
            upcoming.append((timeline[index][0], 0))
        if recorder is not None:
            upcoming.append((recorder[0], 1))
        if level is not None:
            upcoming.append((level[0], 2))
        if not upcoming:
            break
        now, which = min(upcoming)
        if which == 0:
            queue.append(timeline[index][1])
            index += 1
            while len(queue) > backlog:
                settled_end = max(settled_end, queue.pop(0).last_position)
                dropped += 1
                wake(now)
            start_recorder(now)
        elif which == 1:
            settled_end = max(settled_end, recorder[1].last_position)
            recorder = None
            wake(now)
            start_recorder(now)
        else:
            commit, bound = level
            level = None
            if commit > end:
                # The recording ends before this commit; its staleness is unobserved, not zero.
                censored += 1
            else:
                during = moved_past(bound, commit)
                moved.append(during)
                passes.append(during < s)
            if pending_wake:
                wake(commit)
    return dict(episodes=len(cuts), recorder_passes=recorder_passes, dropped=dropped,
                dropped_share=dropped / len(cuts) if cuts else 0., passes=len(passes), commits=sum(passes),
                discards=len(passes) - sum(passes), censored=censored, moved=moved,
                level_requests=(len(passes) + censored) * level_requests, recorder_requests=recorder_passes * recorder_requests,
                actor_requests=len(recorded['request_walls']))


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def stage(runs: list[Path], *, theta: float, m: int, cap: int, s: int, backlog: int, recorder_requests: int,
          level_requests: int, replicates: int, seed: int, latency_scale: float = 1.) -> dict:
    """`latency_scale` multiplies recorded actor latencies, since reader requests may write longer proposals."""
    recorded = [load(run) for run in runs]
    pool = [latency * latency_scale for r in recorded for latency in r['latencies']]
    result = dict(schema='level-offline-stage/3', parameters=dict(theta=theta, m=m, cap=cap, s=s, backlog=backlog,
                  recorder_requests=recorder_requests, level_requests=level_requests, replicates=replicates, seed=seed,
                  latency_scale=latency_scale),
                  latency_pool=dict(count=len(pool), median=statistics.median(pool), p95=quantile(pool, .95)),
                  runs=[])
    rng = random.Random(seed)
    for r in recorded:
        cuts = cut_run(r, theta=theta, m=m, cap=cap)
        sims = [simulate(r, pool, theta=theta, m=m, cap=cap, s=s, backlog=backlog, recorder_requests=recorder_requests,
                         level_requests=level_requests, rng=rng, episodes=cuts) for _ in range(replicates)]
        rates = [x['commits'] / x['passes'] for x in sims if x['passes']]
        moved = [v for x in sims for v in x['moved']]
        inputs = sum(row[2] == 'input' for row in r['rows'])
        span = r['rows'][-1][3] - r['rows'][0][3]
        result['runs'].append(dict(run=r['run'], inputs=r['inputs'], projection=projection_check(r),
            actor_inputs=inputs, actor_requests=len(r['request_walls']), episodes=len(cuts),
            mean_episode_inputs=statistics.fmean(e.inputs for e, _ in cuts) if cuts else None,
            input_interval_seconds=span / max(1, inputs - 1),
            passes_mean=statistics.fmean(x['passes'] for x in sims),
            censored_mean=statistics.fmean(x['censored'] for x in sims),
            dropped_share=statistics.fmean(x['dropped_share'] for x in sims),
            commit_rate=dict(mean=statistics.fmean(rates) if rates else None, p05=quantile(rates, .05),
                             p95=quantile(rates, .95)),
            inputs_during_pass=dict(median=quantile(moved, .5), p95=quantile(moved, .95), max=max(moved, default=None)),
            reader_request_overhead=statistics.fmean(
                (x['level_requests'] + x['recorder_requests']) / max(1, x['actor_requests']) for x in sims)))
    commits = sum(x['commit_rate']['mean'] * x['passes_mean'] for x in result['runs'] if x['commit_rate']['mean'] is not None)
    total = sum(x['passes_mean'] for x in result['runs'])
    result['pooled_commit_rate'] = commits / total if total else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True, help='A recorded single-actor run directory')
    parser.add_argument('--theta', type=float, required=True, help="The fitted episode threshold (#345's calibration)")
    parser.add_argument('--m', type=int, default=2)
    parser.add_argument('--cap', type=int, default=10, help='The episode cap C, which equals K')
    parser.add_argument('--s', type=int, default=10)
    parser.add_argument('--backlog', type=int, default=3)
    parser.add_argument('--recorder-requests', type=int, default=2)
    parser.add_argument('--level-requests', type=int, default=3)
    parser.add_argument('--replicates', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=329)
    parser.add_argument('--latency-scale', type=float, default=1.)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.runtime'):
        parser.error('Write offline-stage outputs under the project .runtime directory')
    value = stage(args.run, theta=args.theta, m=args.m, cap=args.cap, s=args.s, backlog=args.backlog,
                  recorder_requests=args.recorder_requests, level_requests=args.level_requests,
                  replicates=args.replicates, seed=args.seed, latency_scale=args.latency_scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(output=str(output), pooled_commit_rate=value['pooled_commit_rate']), indent=2))


if __name__ == '__main__':
    main()
