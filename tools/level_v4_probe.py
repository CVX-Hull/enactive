#!/usr/bin/env python3
"""Engineering probe: the level v4 replay probe (#352), recorded runs through the real recorder and level hosts.

An engineering probe of the integrated v4 candidate: whether the recorder and level interfaces can be called correctly
on the production route, and whether the intent tail supplies anything the actor lacked. Every #345 episode is
development data, so no result here is evidence about recorder quality or play; the report is labelled
`engineering-probe` and excluded from evidence. The frozen spec is `protocol.md` and the thresholds file beside it; this
tool computes G1 to G6 exactly as they define them and records both digests.

Stages (all inputs are recorded; no game, no live session):

1. **Recorder, two families.** Every #345 episode with a subgoal plus the subgoal-free episodes whose
   `int(sha256(run|index), 16)` is smallest. For each, a fresh read-only replay store of the run's operations and frames
   up to the episode's end is built through the store API (as `tools/level_probe.py` does). The episode's subgoal is
   inserted through the custodian's append path, the episode is bound with `bind_episode` and pushed with the driver's own
   `episode_push` and `recorder_document`, and the real recorder host (`player-host/6`, frozen `episode-v1`) runs once per
   family route. F1 is the production route and F2 the second family, both given as explicit `player-host/6` files.
2. **Level.** The driver's offline replay (cutter closes, recorder backlog and the real `LevelSchedule` wakes) runs over
   every run with #345's R1 records, each turned into a trusted `player-episode/1` settle through the custodian's own
   `episode_call`. From all wake points, a sample chosen by the same hash rule gets the driver's real `level_push` and
   `level_text` input and runs once through the real level host on F1.
3. **Manipulation check ($0).** At each recorded actor request the real `intent()` gives the v4 tail over the replay store
   as of that request; the real host formatter decides which recall lines are shown; a shown recall item is marginal
   when its source frame is not among the images the actor held, read from the recorded host trace's
   `context-image-projection` and `tool-result` events. A run whose trace lacks those events is excluded and reported.

Statistics are run-cluster percentile bootstraps over the recorded run. Spend: `--max-usd` is required and is a hard cap
on the charged cost, enforced up front across both stages as `tools/level_probe.py` does; the credential is read only from
the Keychain and passed only in each host's environment. Nothing is written outside `.runtime/probes`.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import concurrent.futures
import contextlib
import hashlib
import json
import math
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness import application as application_module
from harness.computer.launch import close_group
from harness.computer.protocol import ControlError
from harness.player import memory as memory_module
from harness.player.contracts import LEVEL_CONTRACT
from harness.player.memory import Memory
from harness.player.contracts import PlayerError
from harness.server import serve
from tools import level_offline
from tools.campaign_package import EPISODE_ROLE, FROZEN_ROLE_SHA256, LEVEL_ROLE, level_profile
from tools.campaign_player import episode_push, level_push, level_text, recorder_document, write_new
from tools.configure_player_tools import configuration
from tools.episode_cutter import Episode, distance, thumbnail
from tools.level_probe import add_operation, classify, git_state, keychain_secret, load_route, open_replay, sha256_file, watch_host
from tools.level_schedule import LevelSchedule

LABEL = 'engineering-probe'
SCHEMA = 'level-v4-probe/1'
THRESHOLDS_SCHEMA = 'level-v4-probe-thresholds/1'
PROBE_ROOT = ROOT / '.runtime' / 'probes'
DEFAULT_SAMPLE_ESTIMATE_USD = 0.12
STATUSES = ('seen', 'not_yet', 'contradicted')
# #345's persistent lineage: sessions that share one player memory in this order (each carries the last subgoal and recalls
# the earlier sessions' recorded episodes). Every other run is its own lineage.
LINEAGE = tuple(f'persistent329-{number:02d}' for number in range(1, 6))
# #345's scripted start and end episodes and its tail close are session edges for the driver's recorder document.
CLOSED_BY = {'content': 'content', 'cap': 'cap', 'tail': 'edge', 'scripted_start': 'edge', 'scripted_end': 'edge'}
THRESHOLD_KEYS = {'schema', 'unit', 'interval', 'recorder_valid_terminal_rate_lower_at_least', 'recorder_record_share_lower_at_least',
                  'level_valid_terminal_rate_lower_at_least', 'repeated_identical_refusal_at_most', 'cross_family_kappa_point_at_least',
                  'cross_family_kappa_lower_at_least', 'marginal_coverage_lower_above', 'max_usd'}
# What the probe cannot reproduce or had to decide, stated in every report.
LIMITS = (
    'Recorded runs are v3-era development data (campaign-run/3 and /4, player-host/2 to /5); they are test inputs, not a '
    'supported format. Nothing here is evidence about recorder quality, intent quality or play.',
    'Stage 1 uses #345\'s episode boundaries (including its scripted start and end episodes, shown to the recorder as closed '
    'by `edge`), not the driver cutter\'s; the number of episodes whose cut differs under the driver\'s capture-less-input '
    'distance rule is reported.',
    'Stage 1 replays one episode against a fresh store holding only the run\'s operations up to the episode end and the '
    'episode\'s subgoal: no earlier episodes, no recall, no other subgoals.',
    'Stages 2 and 3 replay each run with #345\'s R1 records as settles, the recorded level commits as the subgoal timeline, '
    'and recorder and level pass durations drawn from the runs\' own recorded request latencies (seeded); only runs that '
    'have R1 records for every episode are replayed. Persistent runs share one memory in order, so later sessions recall '
    'the earlier ones; every other run is its own store.',
    'The level commits the probe replays are the recorded v3-era ones; the replay\'s own level pass is read-only evidence '
    'of interface correctness and its commit is not applied to later wake points.',
    'The tail audience is `tail` (the custodian\'s name for the actor\'s request-only tail); the protocol\'s `actor` is not '
    'a custodian audience.',
    'Whether a recall item is shown is decided by the real host formatter (`formatIntentTail`), over the real `intent()` value.',
    'Provider behavior at the replay moment, not the recorded run\'s: no outcome is play evidence.',
)


# --- thresholds, digests, sampling -----------------------------------------------------------------------------

def load_thresholds(path: Path) -> dict:
    """The frozen pass criteria: a closed JSON file, never constants in this tool."""
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or set(value) != THRESHOLD_KEYS or value['schema'] != THRESHOLDS_SCHEMA:
        raise ValueError(f'Thresholds must be a closed {THRESHOLDS_SCHEMA} object with exactly {sorted(THRESHOLD_KEYS - {"schema"})}')
    interval = value['interval']
    if (not isinstance(interval, dict) or set(interval) != {'method', 'level', 'resamples', 'seed'}
            or interval['method'] != 'run-cluster percentile bootstrap' or not 0 < interval['level'] < 1
            or type(interval['resamples']) is not int or interval['resamples'] < 1 or type(interval['seed']) is not int):
        raise ValueError('The interval must be a run-cluster percentile bootstrap with level, resamples and seed')
    if value['unit'] != 'recorded run':
        raise ValueError('The unit must be the recorded run')
    for key in THRESHOLD_KEYS - {'schema', 'unit', 'interval'}:
        if type(value[key]) not in (int, float) or isinstance(value[key], bool):
            raise ValueError(f'{key} must be a number')
    if not 0 < value['max_usd']:
        raise ValueError('max_usd must be positive')
    return value


def sample_key(run: str, index: int) -> int:
    """The protocol's sampling key: `int(sha256(f"{run}|{index}"), 16)`, smallest first."""
    return int(hashlib.sha256(f'{run}|{index}'.encode()).hexdigest(), 16)


def sample_episodes(episodes: list[dict], no_subgoal: int) -> list[dict]:
    """Every episode with a subgoal, plus the `no_subgoal` subgoal-free ones with the smallest key; ordered by key."""
    withs = [e for e in episodes if e['subgoal']]
    withouts = sorted((e for e in episodes if not e['subgoal']), key=lambda e: sample_key(e['run'], e['index']))
    return sorted(withs + withouts[:no_subgoal], key=lambda e: sample_key(e['run'], e['index']))


def sample_wakes(wakes: list[dict], count: int) -> list[dict]:
    """`count` wake points chosen by the same rule over (run, pass index), ordered by key."""
    return sorted(wakes, key=lambda w: sample_key(w['run'], w['index']))[:count]


# --- statistics ------------------------------------------------------------------------------------------------

def agreement(pairs: list[tuple[str, str]], categories: tuple[str, ...] = STATUSES) -> dict:
    """Cohen's kappa and Gwet's AC1 for two raters over a fixed category set (None where undefined)."""
    n = len(pairs)
    if n == 0:
        return dict(n=0, agreement=None, kappa=None, ac1=None)
    po = sum(a == b for a, b in pairs) / n
    first, second = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(first[k] * second[k] for k in categories) / (n * n)
    kappa = (po - pe) / (1 - pe) if pe < 1 else None
    pi = {k: (first[k] + second[k]) / (2 * n) for k in categories}
    pe_gwet = sum(pi[k] * (1 - pi[k]) for k in categories) / (len(categories) - 1)
    ac1 = (po - pe_gwet) / (1 - pe_gwet) if pe_gwet < 1 else None
    return dict(n=n, agreement=po, kappa=kappa, ac1=ac1)


def bootstrap(summaries: dict, combine, *, seed: int, resamples: int, level: float) -> dict:
    """A percentile bootstrap that resamples the recorded runs with replacement.

    `summaries` maps each run to a sufficient summary of its items and `combine(list_of_summaries)` returns the pooled
    statistic or None. The interval takes order statistics `int(alpha * n)` and `int((1 - alpha) * n)` of the sorted
    resampled values, `alpha` being half of `1 - level`; resamples where the statistic is undefined are skipped, and
    fewer than half defined (or fewer than two runs) leaves the interval undefined. One generator seeded with `seed` per
    statistic, so a statistic's interval does not depend on the others.
    """
    names = sorted(summaries)
    point = combine([summaries[n] for n in names]) if names else None
    result = dict(point=point, lower=None, upper=None, runs=len(names), resamples=resamples, defined_resamples=0)
    if len(names) < 2:
        return result
    rng = random.Random(seed)
    values = []
    for _ in range(resamples):
        value = combine([summaries[names[rng.randrange(len(names))]] for _ in names])
        if value is not None:
            values.append(value)
    result['defined_resamples'] = len(values)
    if len(values) * 2 < resamples:
        return result
    values.sort()
    alpha = (1 - level) / 2
    result.update(lower=values[int(alpha * len(values))], upper=values[min(len(values) - 1, int((1 - alpha) * len(values)))])
    return result


def _ratio(parts: list[tuple[int, int]]) -> float | None:
    den = sum(d for _, d in parts)
    return sum(n for n, _ in parts) / den if den else None


def _kappa_of(tables: list[collections.Counter]) -> float | None:
    total = collections.Counter()
    for table in tables:
        total.update(table)
    return agreement([pair for pair, count in total.items() for _ in range(count)])['kappa']


def _by_run(items: list[dict], summary) -> dict:
    grouped = collections.defaultdict(list)
    for item in items:
        grouped[item['run']].append(item)
    return {run: summary(group) for run, group in grouped.items()}


def family_gates(recorder: list[dict]) -> dict:
    """G1 and G2 inputs for one family's recorder passes, plus the repeated-refusal maximum (G4)."""
    return dict(
        valid=_by_run(recorder, lambda g: (sum(i['valid'] for i in g), len(g))),
        records=_by_run([i for i in recorder if i['valid']], lambda g: (sum(i['terminal'] == 'record' for i in g), len(g))),
        max_repeat=max((i['max_repeat'] for i in recorder), default=0))


def kappa_tables(f1: list[dict], f2: list[dict]) -> dict:
    """Per run, the confusion table of F1 against F2 over per-observation statuses where both recorded."""
    second = {(i['run'], i['episode']): i for i in f2 if i['terminal'] == 'record' and i['observation_status']}
    tables = collections.defaultdict(collections.Counter)
    for item in f1:
        other = second.get((item['run'], item['episode']))
        if item['terminal'] != 'record' or not item['observation_status'] or other is None:
            continue
        if len(item['observation_status']) != len(other['observation_status']):
            continue
        tables[item['run']].update(zip(item['observation_status'], other['observation_status'], strict=True))
    return dict(tables)


def evaluate(thresholds: dict, f1: list[dict], f2: list[dict], level: list[dict], tails: list[dict]) -> dict:
    """G1 to G6 exactly as the protocol defines them, with F2's G1 to G4 values reported beside (not gating)."""
    interval = thresholds['interval']
    boot = dict(seed=interval['seed'], resamples=interval['resamples'], level=interval['level'])
    gates = {}

    def gate(name, statistic, summaries, combine, rule, **conditions):
        measured = bootstrap(summaries, combine, **boot)
        passed = all(condition(measured) for condition in conditions.values())
        gates[name] = dict(statistic=statistic, rule=rule, passed=passed, **measured)

    mine = family_gates(f1)
    gate('G1', 'F1 recorder valid terminal rate (passes ending in exactly one accepted record or abstain)', mine['valid'], _ratio,
         f'lower bound >= {thresholds["recorder_valid_terminal_rate_lower_at_least"]}',
         lower=lambda m: m['lower'] is not None and m['lower'] >= thresholds['recorder_valid_terminal_rate_lower_at_least'])
    gate('G2', 'F1 record share among valid recorder passes (record / (record + abstain))', mine['records'], _ratio,
         f'lower bound >= {thresholds["recorder_record_share_lower_at_least"]}',
         lower=lambda m: m['lower'] is not None and m['lower'] >= thresholds['recorder_record_share_lower_at_least'])
    gate('G3', 'Level valid terminal rate (passes ending in an accepted keep, replace, close or abstain)',
         _by_run(level, lambda g: (sum(i['valid'] for i in g), len(g))), _ratio,
         f'lower bound >= {thresholds["level_valid_terminal_rate_lower_at_least"]}',
         lower=lambda m: m['lower'] is not None and m['lower'] >= thresholds['level_valid_terminal_rate_lower_at_least'])
    worst = max(mine['max_repeat'], max((i['max_repeat'] for i in level), default=0))
    gates['G4'] = dict(statistic='Largest count of repeated identical refusals in any F1 recorder or level pass', point=worst,
                       lower=None, upper=None, rule=f'<= {thresholds["repeated_identical_refusal_at_most"]}',
                       passed=worst <= thresholds['repeated_identical_refusal_at_most'], runs=None)
    tables = kappa_tables(f1, f2)
    gate('G5', "Cohen's kappa, F1 against F2, per-observation status over episodes where both recorded", tables, _kappa_of,
         f'point >= {thresholds["cross_family_kappa_point_at_least"]} and lower bound >= {thresholds["cross_family_kappa_lower_at_least"]}',
         point=lambda m: m['point'] is not None and m['point'] >= thresholds['cross_family_kappa_point_at_least'],
         lower=lambda m: m['lower'] is not None and m['lower'] >= thresholds['cross_family_kappa_lower_at_least'])
    gate('G6', 'Marginal coverage: share of shown recall items whose source frame the actor did not hold, pooled',
         _by_run(tails, lambda g: (sum(i['marginal'] for i in g), sum(i['shown'] for i in g))), _ratio,
         f'lower bound > {thresholds["marginal_coverage_lower_above"]}',
         lower=lambda m: m['lower'] is not None and m['lower'] > thresholds['marginal_coverage_lower_above'])
    pooled = collections.Counter()
    for table in tables.values():
        pooled.update(table)
    gates['G5']['agreement'] = agreement([pair for pair, count in pooled.items() for _ in range(count)])
    other = family_gates(f2)
    reported = dict(
        f2_g1=bootstrap(other['valid'], _ratio, **boot), f2_g2=bootstrap(other['records'], _ratio, **boot),
        f2_g4_max_repeated_identical_refusal=other['max_repeat'])
    return dict(gates=gates, f2=reported, all_passed=all(g['passed'] for g in gates.values()))


# --- the recorded data -----------------------------------------------------------------------------------------

def iso(value: str) -> float:
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def load_ladder(directory: Path) -> dict:
    """#345's episodes and R1 records (first calls only, retests excluded), with their digests."""
    episodes_path, records_path = directory / 'episodes.json', directory / 'records.jsonl'
    document = json.loads(episodes_path.read_text())
    if document.get('schema') != 'ladder345-episodes/1':
        raise ValueError(f'{episodes_path} is not ladder345-episodes/1')
    records = {}
    for line in records_path.read_text().splitlines():
        value = json.loads(line)
        if value['recorder'] == 'R1' and not value['retest'] and value['status'] == 'record' and value['final']:
            records[(value['run'], value['episode'])] = value
    return dict(document=document, records=records, theta=document['theta'], m=document['m'], cap=document['cap'],
                digests=dict(episodes=sha256_file(episodes_path), records=sha256_file(records_path)))


def episodes_by_run(document: dict) -> dict[str, list[dict]]:
    grouped = collections.defaultdict(list)
    for episode in document['episodes']:
        grouped[episode['run']].append(episode)
    return {run: sorted(group, key=lambda e: e['index']) for run, group in grouped.items()}


def load_run(root: Path, name: str, session: str) -> dict:
    """One recorded single-actor run: operations, request walls and latencies, frames, brief and context."""
    directory = (root / name).resolve(strict=True)
    recorded = level_offline.load(directory)
    database = sqlite3.connect(f'file:{directory / "session.sqlite3"}?mode=ro&immutable=1', uri=True)
    try:
        frames = {row[0]: row[1] for row in database.execute('SELECT id,metadata FROM sources')}
        stored_session = json.loads(database.execute("SELECT value FROM metadata WHERE key='session'").fetchone()[0])
    finally:
        database.close()
    if stored_session != session:
        raise ValueError(f'{name}: the recording is session {stored_session}, the ladder names {session}')
    rows = recorded['rows']
    sources = []
    for row in rows:
        final = json.loads(row[6]) if row[6] else None
        sources.append(((final or {}).get('source') or {}).get('source_id'))
    return dict(name=name, directory=directory, session=session, rows=rows, sources=sources, frames=frames,
                request_walls=recorded['request_walls'], latencies=recorded['latencies'], inputs=recorded['inputs'],
                brief=(directory / 'prompt.txt').read_text(), context=(directory / 'context.txt').read_text())


def level_commits(run: dict) -> list[dict]:
    """The recorded level's subgoal replaces and closes with their wall times, from its pass traces, oldest first."""
    found = []
    for trace in sorted((run['directory'] / 'actors/001/level').glob('[0-9][0-9][0-9]/host.jsonl')):
        starts = {}
        for line in trace.read_text().splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get('type') == 'tool-start' and str(event.get('tool', '')).startswith('player_level_'):
                starts[event.get('tool_call_id')] = event.get('arguments') or {}
            elif event.get('type') == 'level-commit' and event.get('action') in ('replace', 'close'):
                found.append(dict(wall=iso(event['wall_time']), action=event['action'], position=event.get('position'),
                                  id=(event.get('record_ids') or [None])[0], arguments=starts.get(event.get('tool_call_id'), {})))
    return sorted(found, key=lambda e: e['wall'])


def actor_projection(run: dict) -> dict:
    """The recorded actor host's requests with the images held at each, from its projection and tool-result events.

    An image is held at a request when a tool result before it carried it (`image_reference`) and the request's
    `context-image-projection` event did not omit that (tool call, image index). `exclusion` names why a run cannot
    serve the check; `mismatched` counts requests whose derived image counts differ from the event's own counts.
    """
    images, requests, mismatched, seen_projection = {}, [], 0, False
    for line in (run['directory'] / 'actors/001/host.jsonl').read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get('type')
        if kind == 'tool-result':
            for part in (event.get('result') or {}).get('content', []):
                if part.get('type') == 'image_reference' and isinstance(part.get('sha256'), str):
                    images[(event.get('tool_call_id'), part.get('image_index'))] = part['sha256']
        elif kind == 'context-image-projection':
            seen_projection = True
            # The host omits the oldest images first (an actor pins none) and lists only the first 16 omissions, so the
            # held images are the images in order after the first `omitted_images`; the listed omissions check that order.
            order = list(images)
            count = event.get('omitted_images', 0)
            listed = [(o.get('tool_call_id'), o.get('image_index')) for o in event.get('omissions', [])]
            held = order[count:]
            consistent = (len(order) == event.get('input_images') and len(held) == event.get('retained_images')
                          and event.get('pinned_images', 0) == 0 and order[:len(listed)] == listed)
            mismatched += not consistent
            requests.append(dict(request_id=event.get('request_id'), wall=iso(event['wall_time']),
                                 held={images[key] for key in held}, consistent=consistent))
    exclusion = None
    if not seen_projection:
        exclusion = 'the actor trace has no context-image-projection events'
    elif not images:
        exclusion = 'the actor trace has no tool-result image references'
    return dict(requests=requests, exclusion=exclusion, mismatched=mismatched)


def thumbnails(run: dict) -> dict[int, bytes]:
    """32 x 20 thumbnails of the run's result captures by position, from the retained captures."""
    cache = run.setdefault('_thumbnails', {})
    if not cache:
        for position, source in enumerate(run['sources'], 1):
            if source:
                cache[position] = thumbnail((run['directory'] / 'sources' / f'{source}.png').read_bytes())
    return cache


def driver_distances(run: dict) -> dict[int, float | None]:
    """Each input's distance under the driver's rule: against the previous input that has a result capture."""
    thumbs, previous, result = thumbnails(run), None, {}
    for position, row in enumerate(run['rows'], 1):
        if row[2] != 'input':
            continue
        thumb = thumbs.get(position)
        result[position] = distance(previous, thumb) if thumb is not None and previous is not None else None
        if thumb is not None:
            previous = thumb
    return result


def ladder_distances(run: dict) -> dict[int, float | None]:
    """The same distances under #345's recorded rule: against the previous input, none when that input has no capture."""
    thumbs, previous, seen, result = thumbnails(run), None, False, {}
    for position, row in enumerate(run['rows'], 1):
        if row[2] != 'input':
            continue
        thumb = thumbs.get(position)
        result[position] = distance(previous, thumb) if seen and previous is not None and thumb is not None else None
        previous, seen = thumb, True
    return result


def ladder_cut(kinds: list[str], distances: dict[int, float | None], *, theta: float, m: int, cap: int, n_start: int,
               n_end: int) -> list[tuple[int, int]]:
    """#345's cut of a run into (first, last) 1-based positions: scripted start and end episodes, content, cap and tail."""
    n = len(kinds)
    ns, ne = min(n_start, n), min(n_end, n - min(n_start, n))
    episodes = [(1, ns)] if ns else []
    first, inputs = None, 0
    for i in range(ns + 1, n - ne + 1):
        d = distances.get(i)
        if kinds[i - 1] == 'input' and d is not None and d >= theta and first is not None and inputs >= m:
            episodes.append((first, i - 1))
            first, inputs = None, 0
        if first is None:
            first, inputs = i, 0
        if kinds[i - 1] == 'input':
            inputs += 1
            if inputs >= cap:
                episodes.append((first, i))
                first, inputs = None, 0
    if first is not None:
        episodes.append((first, n - ne))
    if ne:
        episodes.append((n - ne + 1, n))
    return episodes


def cut_differences(run: dict, episodes: list[dict], ladder: dict) -> dict:
    """How many of #345's episodes of a run are cut differently under the driver's capture-less-input distance rule.

    The cut is first recomputed under #345's own rule, which must reproduce the recorded episodes (`reproduces`); the
    count is then of recorded episodes absent from the cut under the driver's rule.
    """
    document = ladder['document']
    kinds = [row[2] for row in run['rows']]
    settings = dict(theta=ladder['theta'], m=ladder['m'], cap=ladder['cap'], n_start=document['n_start'], n_end=document['n_end'])
    recorded = [(e['start_pos'], e['end_pos']) for e in episodes]
    own = ladder_cut(kinds, ladder_distances(run), **settings)
    driver = ladder_cut(kinds, driver_distances(run), **settings)
    return dict(episodes=len(recorded), reproduces=own == recorded, differ=sum(pair not in set(driver) for pair in recorded),
                driver_episodes=len(driver))


# --- the offline replay plan -----------------------------------------------------------------------------------

def close_wall(run: dict, episode: dict) -> float:
    """When #345's episode closes: at the crossing input for a content cut, else at its last operation."""
    rows = run['rows']
    if episode['closed_by'] == 'content' and episode['end_pos'] < len(rows):
        return rows[episode['end_pos']][3]
    return rows[episode['end_pos'] - 1][3]


def plan_run(run: dict, episodes: list[dict], records: dict, *, pool: list[float], level: dict, actor_allowance: int,
             carried: int, seed: int, recorder_requests: int, level_requests: int) -> dict:
    """The driver's offline replay of cutter closes, recorder backlog and level wakes over one recorded timeline.

    Closed episodes join the recorder's FIFO backlog (the oldest settles `dropped` when more than the backlog wait); one
    recorder pass runs at a time and takes the sum of `recorder_requests` latencies drawn from `pool`, and an R1 record
    is its settle (an episode with no record settles `failed`). The real `LevelSchedule` decides the level's wakes, which
    are polled at every event as the driver polls; a pass takes `level_requests` latencies and the level stops with its
    actor. Allowances are charged as the driver charges lanes. Returns the ordered `events` and the `wakes`.
    """
    rng = random.Random(f'{seed}|plan|{run["name"]}')
    walls = sorted(run['request_walls'])
    end = max(walls[-1] if walls else 0., run['rows'][-1][3])
    schedule = LevelSchedule(tuple(level['budget_fractions']), actor_allowance)
    closes = sorted(((close_wall(run, e), e['index'], e) for e in episodes), key=lambda item: item[:2])
    backlog, recorder_left, level_left = level['recorder']['backlog'], level['recorder']['max_http_attempts'], level['max_http_attempts']
    queue, recorder, busy_until, index, pass_index = [], None, None, 0, 0
    settled_total, started = 0, False
    events, wakes = [], []

    def draw(count: int) -> float:
        return sum(rng.choice(pool) for _ in range(count))

    def settle(now: float, episode: dict, kind: str, reason: str) -> None:
        nonlocal settled_total
        settled_total += 1
        events.append((now, 3, 'settle', dict(episode=episode, outcome=kind, reason=reason)))

    def start_recorder(now: float) -> None:
        nonlocal recorder, recorder_left
        while queue and recorder is None:
            if recorder_left < 1:
                settle(now, queue.pop(0), 'failed', 'The recorder allowance is exhausted')
                continue
            recorder_left -= recorder_requests
            recorder = (now + draw(recorder_requests), queue.pop(0))

    while True:
        upcoming = []
        if index < len(closes):
            upcoming.append((closes[index][0], 0))
        if recorder is not None:
            upcoming.append((recorder[0], 1))
        if busy_until is not None:
            upcoming.append((busy_until, 2))
        if walls and not started:
            upcoming.append((walls[0], 3))
        if not upcoming:
            break
        now, which = min(upcoming)
        if which == 0:
            episode = closes[index][2]
            index += 1
            queue.append(episode)
            while len(queue) > backlog:
                settle(now, queue.pop(0), 'dropped', f'Recorder backlog: more than {backlog} closed episodes were waiting')
            start_recorder(now)
        elif which == 1:
            episode = recorder[1]
            recorder = None
            if (episode['run'], episode['index']) in records:
                settle(now, episode, 'recorded', 'R1 record')
            else:
                settle(now, episode, 'failed', 'The recorder pass ended without settling the episode (no R1 record)')
            start_recorder(now)
        elif which == 2:
            busy_until = None
        else:
            started = True
        # The driver polls between passes: a wake needs a free level, a started actor and an unspent allowance.
        if busy_until is None and walls and now >= walls[0] and now < end and level_left >= 1:
            attempts = bisect.bisect_right(walls, now)
            reason = schedule.due(settled=settled_total, attempts=attempts, carried=0 if schedule.started else carried)
            if reason is not None:
                pass_index += 1
                level_left -= level_requests
                busy_until = now + draw(level_requests)
                allowance = min(level['pass_max_requests'], level_left + level_requests)
                wake = dict(run=run['name'], index=pass_index, time=now, reason=reason, settled_episodes=settled_total,
                            allowance_requests=allowance, allowance_seconds=int(level['pass_seconds']))
                wakes.append(wake)
                events.append((now, 4, 'wake', wake))
    settles = collections.Counter(e[3]['outcome'] for e in events if e[2] == 'settle')
    return dict(events=events, wakes=wakes, settles=dict(settles), end=end, closed=len(closes))


# --- the replay ------------------------------------------------------------------------------------------------

class SimClock:
    """The recorded timeline's wall clock for the custodian's `time.time()`; every other time function is the real one."""
    def __init__(self) -> None:
        self.now = 0.

    def time(self) -> float:
        return self.now

    def __getattr__(self, name):
        import time
        return getattr(time, name)


@contextlib.contextmanager
def simulated_clock():
    clock = SimClock()
    with mock.patch.object(application_module, 'time', clock), mock.patch.object(memory_module, 'time', clock):
        yield clock


def digest32(*parts: str) -> str:
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:32]


def install_subgoal(application, writer_id: str, actor_id: str, session: str, spec: dict, mapping: dict, *, position: int) -> str:
    """Insert one level subgoal through the custodian's append path, as `level_call` writes it, and map its recorded id.

    A current subgoal is superseded by the correction a replace writes. Returns the replay's record id.
    """
    memory = application.memory
    identity = digest32('v4probe-subgoal', session, spec['id'])
    ids = memory.batch_ids(identity, 16)
    common = dict(level='subgoal', level_contract=LEVEL_CONTRACT, actor_id=actor_id, session=session, position=position)
    current = application.level_subgoals()
    values = [dict(schema='player-record/1', kind='work', text=spec['text'],
                   data=dict(common, expected_observations=list(spec['expected_observations']), status=spec.get('status', 'open'),
                             confidence=spec['confidence']),
                   sources=[], supports=[], supersedes=None, applicability=None, program_id=None)]
    if current:
        values.append(dict(schema='player-record/1', kind='correction', text='replay: the recorded level replaced the subgoal',
                           data=dict(common, outcome='revised'), sources=[], supports=[ids[0]], supersedes=current[-1]['id'],
                           applicability=None, program_id=None))
    stored = memory.append_many(writer_id, values, request_id=identity, custodian=True)
    mapping[spec['id']] = stored[0]['id']
    return stored[0]['id']


def close_subgoal(application, writer_id: str, actor_id: str, session: str, recorded_id: str, *, position: int) -> None:
    current = application.level_subgoals()
    if not current:
        return
    identity = digest32('v4probe-close', session, recorded_id)
    data = dict(level='subgoal', level_contract=LEVEL_CONTRACT, actor_id=actor_id, session=session, position=position,
                outcome='abandoned')
    application.memory.append_many(writer_id, [dict(schema='player-record/1', kind='correction',
        text='replay: the recorded level closed the subgoal', data=data, sources=[], supports=[],
        supersedes=current[-1]['id'], applicability=None, program_id=None)], request_id=identity, custodian=True)


def subgoal_spec(episode_subgoal: dict) -> dict:
    return dict(id=episode_subgoal['id'], text=episode_subgoal['text'], expected_observations=episode_subgoal['expected_observations'],
                confidence=episode_subgoal['confidence'], status='open', position=episode_subgoal['commit_position'])


def trusted_arguments(record: dict, sources: list[str]) -> dict:
    """An R1 record as `player_episode_record` arguments (the recorder\'s `changed` field did not exist in #345)."""
    parsed = record['parsed']
    return dict(attempted=parsed['attempted'], counterpart=parsed.get('counterpart', ''), observation_status=list(parsed['observation_status']),
                changed=parsed.get('changed', ''), residual=parsed.get('residual', ''), confidence=parsed['confidence'],
                sources=[s for s in parsed.get('sources', []) if s in sources][:4])


class Lineage:
    """One player memory shared by the sessions that carried it, with the recorded-to-replay subgoal id map."""
    def __init__(self, directory: Path):
        directory.mkdir(parents=True)
        self.memory = Memory(directory / 'player.sqlite3')
        self.mapping: dict[str, str] = {}
        self.directory = directory
        self.sessions = 0
        self.conversion_failures: list[dict] = []

    def close(self) -> None:
        self.memory.close()


def replay(run: dict, plan: dict, episodes: list[dict], records: dict, lineage: Lineage, profile: dict, *, stop_wake: int | None = None,
           tails: list | None = None, projection: dict | None = None) -> dict:
    """Replay one run's timeline into a fresh runtime over the lineage\'s memory, in recorded time order.

    Operations, recorded level commits (the subgoal timeline), episode settles, wakes (the driver\'s real `level_push`) and
    actor requests are applied in time order under a simulated clock. With `stop_wake` the replay stops at that wake and
    returns the live state and its pushed input; with `tails` each recorded actor request that has projection events
    appends its `intent(audience="tail")` value to the list. The caller closes the returned runtime.
    """
    lineage.sessions += 1
    directory = lineage.directory / f'session-{lineage.sessions:02d}-{run["name"]}'
    directory.mkdir()
    rows = [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in run['rows']]
    runtime, _, application, actor = open_replay(directory, run['session'], run['directory'], run['frames'], [], lineage.memory)
    actor_id = actor['actor_id']
    derived = dict(stall_settles=profile['stall_settles'], confidence_floor=profile['confidence_floor'])
    level_reader = application.add_reader(actor_id, 'level', staleness_inputs=profile['staleness_inputs'], **derived)
    recorder_reader = application.add_reader(actor_id, 'recorder', **derived)
    by_index = {e['index']: e for e in episodes}
    timeline = list(plan['events'])
    timeline += [(row[2], 1, 'op', position) for position, row in enumerate(rows, 1)]
    for commit in level_commits(run):
        timeline.append((commit['wall'], 0, 'subgoal', commit))
    if projection is not None:
        timeline += [(r['wall'], 5, 'request', r) for r in projection['requests']]
    timeline.sort(key=lambda item: (item[0], item[1]))
    cursor, mapping, state = None, lineage.mapping, dict(wake=None, pushed=None)

    def ensure(spec_source: dict | None, position: int) -> str | None:
        if spec_source is None:
            return None
        if spec_source['id'] not in mapping:
            install_subgoal(application, level_reader['actor_id'], actor_id, run['session'], subgoal_spec(spec_source), mapping,
                            position=spec_source['commit_position'])
        return mapping[spec_source['id']]

    with simulated_clock() as clock:
        clock.now = (timeline[0][0] if timeline else 0.) - 1.
        # A subgoal carried in from an earlier session is already in the lineage\'s memory; otherwise it is installed first.
        carried = next((e['subgoal'] for e in episodes[:1] if e['subgoal'] and e['subgoal'].get('origin') == 'carried'), None)
        ensure(carried, 0)
        for when, _, kind, payload in timeline:
            clock.now = when
            if kind == 'op':
                add_operation(runtime, actor_id, run['directory'], run['frames'], rows[payload - 1])
            elif kind == 'subgoal':
                if payload['action'] == 'replace':
                    spec = dict(id=payload['id'], text=payload['arguments'].get('text', ''),
                                expected_observations=payload['arguments'].get('expected_observations') or [],
                                confidence=payload['arguments'].get('confidence', .5), status=payload['arguments'].get('status', 'open'))
                    if spec['id'] and spec['text'].strip() and spec['expected_observations'] and spec['id'] not in mapping:
                        install_subgoal(application, level_reader['actor_id'], actor_id, run['session'], spec, mapping,
                                        position=payload['position'] or 0)
                elif payload['action'] == 'close':
                    close_subgoal(application, level_reader['actor_id'], actor_id, run['session'], payload['id'] or 'close',
                                  position=payload['position'] or 0)
            elif kind == 'settle':
                ep = by_index[payload['episode']['index']]
                subgoal = ensure(ep['subgoal'], ep['start_pos'])
                settle_replayed(application, recorder_reader['actor_id'], ep, subgoal, payload, records, lineage, run['name'])
            elif kind == 'wake':
                wake = payload
                with application.serial:
                    pushed, cursor_next, bind = level_push(application, level_reader['actor_id'], actor_id, run['session'], cursor)
                cursor = cursor_next
                if bind['handoff']:
                    raise ValueError('The replayed actor has handed off')
                state.update(wake=wake, pushed=pushed)
                if stop_wake == wake['index']:
                    return dict(runtime=runtime, application=application, actor=actor, level=level_reader, recorder=recorder_reader,
                                wake=wake, pushed=pushed, directory=directory)
            elif kind == 'request' and tails is not None:
                tails.append(dict(request=payload, intent=application.intent(actor_id, audience='tail')))
    if stop_wake is not None:
        runtime.close()
        raise ValueError(f'{run["name"]}: the replay has no wake {stop_wake}')
    return dict(runtime=runtime, application=application, actor=actor, level=level_reader, recorder=recorder_reader,
                wake=state['wake'], pushed=state['pushed'], directory=directory)


def settle_replayed(application, recorder_id: str, ep: dict, subgoal: str | None, payload: dict, records: dict, lineage: Lineage,
                    run: str) -> None:
    """Settle one episode as the driver does: a dropped or failed claim from software, a recorded one from its R1 record."""
    first, last = ep['start_pos'], ep['end_pos']
    if payload['outcome'] == 'recorded':
        record = records[(ep['run'], ep['index'])]
        try:
            with application.serial:
                bound = application.bind_episode(recorder_id, first_position=first, last_position=last, subgoal_id=subgoal)
                application.episode_call(recorder_id, 'player_episode_record', trusted_arguments(record, bound['sources']),
                                         digest32('v4probe-settle', run, str(ep['index'])))
            return
        except (PlayerError, ControlError, ValueError, KeyError) as exc:
            lineage.conversion_failures.append(dict(run=run, episode=ep['index'], error=str(exc)[:300]))
            payload = dict(payload, outcome='failed', reason=f'R1 record could not be converted: {str(exc)[:200]}')
    application.settle_episode(recorder_id, first_position=first, last_position=last, subgoal_id=subgoal,
                               settled=payload['outcome'], reason=payload['reason'])


# --- stage 1: the recorder ------------------------------------------------------------------------------------

def episode_object(run: dict, ep: dict, subgoal_id: str | None, distances: dict) -> Episode:
    frames = tuple((position, run['sources'][position - 1]) for position in range(ep['start_pos'], ep['end_pos'] + 1)
                   if run['sources'][position - 1])
    return Episode(first_position=ep['start_pos'], last_position=ep['end_pos'], inputs=ep['n_inputs'], closed_by=CLOSED_BY[ep['closed_by']],
                   subgoal_id=subgoal_id, distances={p: distances.get(p) for p in range(ep['start_pos'], ep['end_pos'] + 1)
                                                      if run['rows'][p - 1][2] == 'input'}, frames=frames)


def recorder_state(run: dict, ep: dict, directory: Path, profile: dict, distances: dict, role_prompt: str, allowance: int) -> dict:
    """A fresh replay store for one episode, with its subgoal inserted, its episode bound and its pushed document built."""
    rows = [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in run['rows'][:ep['end_pos']]]
    directory.mkdir(mode=0o700)
    runtime, memory, application, actor = open_replay(directory, run['session'], run['directory'], run['frames'], rows)
    try:
        derived = dict(stall_settles=profile['stall_settles'], confidence_floor=profile['confidence_floor'])
        level_reader = application.add_reader(actor['actor_id'], 'level', staleness_inputs=profile['staleness_inputs'], **derived)
        recorder = application.add_reader(actor['actor_id'], 'recorder', **derived)
        subgoal = None
        if ep['subgoal']:
            subgoal = install_subgoal(application, level_reader['actor_id'], actor['actor_id'], run['session'],
                                      subgoal_spec(ep['subgoal']), {}, position=ep['subgoal']['commit_position'])
        episode = episode_object(run, ep, subgoal, distances)
        pushed = episode_push(application, recorder['actor_id'], episode)
        wake = dict(reason='episode', pass_index=1, allowance_requests=allowance, allowance_seconds=int(profile['recorder']['pass_seconds']),
                    waiting=0)
        document = recorder_document(role_prompt, wake, pushed)
    except BaseException:
        runtime.close()
        memory.close()
        raise
    return dict(runtime=runtime, memory=memory, application=application, actor=actor, recorder=recorder, episode=episode,
                document=document, pushed=pushed)


class Spend:
    """A hard cap on the charged cost across all passes and workers, enforced before a pass launches."""
    def __init__(self, max_usd: float):
        self.max_usd, self.spent, self.reserved, self.dearest, self.skipped = max_usd, 0., 0., 0., 0
        self.lock = threading.Lock()

    def reserve(self, allowance: int, bound: float) -> tuple[int, float]:
        """The requests this pass may use, `min(allowance, floor(unreserved remainder / step))`, and its hold on the cap."""
        with self.lock:
            step = max(bound, self.dearest)
            affordable = int((self.max_usd - self.spent - self.reserved) // step)
            if affordable < 1:
                self.skipped += 1
                return 0, 0.
            used = min(allowance, affordable)
            self.reserved += used * step
            return used, used * step

    def release(self, hold: float, charged: float, dearest: float) -> None:
        with self.lock:
            self.reserved -= hold
            self.spent += charged
            self.dearest = max(self.dearest, dearest)


def lane_context(role: str, run: dict) -> str:
    """The `context.txt` a reader lane\'s host is given, by the driver\'s rule after the no-nudge review.

    The level lane takes the run\'s frozen guide; the recorder lane\'s `context.txt` is empty (no player guide). This must
    track `ReaderLane.start` in `tools/campaign_player.py`; the report records the rule applied.
    """
    return '' if role == 'recorder' else run['context']


def reader_pass(*, role: str, application, reader: dict, session: str, route: dict, context: str, stdin: str | dict, directory: Path,
                out: Path, label: str, allowance: int, seconds: int, effort: str, host_argv: list[str], secret: str, hold: float,
                bound: float) -> dict:
    """Run one reader host (`level` or `recorder`) against a live application and classify what it did.

    The application is served on loopback and the host reaches it through the real MCP adapter. The pushed input is the
    driver\'s own (`level_text` for a level, the closed `player-pass-input/1` document for a recorder).
    """
    kind = 'episode' if role == 'recorder' else 'level'
    directory.mkdir(parents=True, exist_ok=True)
    server, thread = serve(application, 0)
    events = child = None
    try:
        reader_file = directory / 'reader.json'
        write_new(reader_file, dict(schema='player-adapter/1', base_url=f'http://127.0.0.1:{server.server_port}', session=session, **reader))
        selected = dict(route, role=role, intent_tail_bytes=None, max_requests=allowance)
        write_new(directory / 'route.json', selected)
        write_new(directory / 'mcp.json', configuration(str(reader_file), profile=role))
        write_new(directory / 'context.txt', context, text=True)
        name = 'input.txt' if isinstance(stdin, str) else 'input.json'
        write_new(directory / name, stdin, text=isinstance(stdin, str))
        write_new(directory / 'player-final.txt', '', text=True)
        arguments = [*host_argv, 'run', '--config', str(directory / 'route.json'), '--mcp-config', str(directory / 'mcp.json'),
                     '--context', str(directory / 'context.txt'), '--model', route['model']['id'], '--effort', effort,
                     '--timeout-seconds', str(seconds), '-o', str(directory / 'player-final.txt')]
        events, child, stopped = watch_host(directory, arguments, name, selected, secret, seconds, hold, bound)
        cleanup = close_group(child)
        accounting = events.finish()
        record = classify(directory, events, child.returncode, role=kind)
        missing = accounting['missing_usage_attempts']
        costs = [v.get('cost', {}).get('total', 0) for v in events.usage.values()]
        record.update(label=label, missing_usage_attempts=missing, dearest_request_usd=max(costs, default=0),
                      charged_usd=record['configured_cost_usd'] + missing * bound, stopped_by_spend_guard=stopped,
                      cleanup_absent=cleanup['process_absent'] and cleanup['group_absent'], allowance=allowance,
                      uncertain=len(events.uncertain) + len(events.episode_uncertain))
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(directory / 'host.jsonl', out / f'{label}.host.jsonl')
        shutil.copy(directory / name, out / f'{label}.{name}')
        return record
    finally:
        if events is not None:
            events.close()
        if child is not None and child.poll() is None:
            close_group(child)
        server.shutdown()
        server.server_close()
        thread.join(2)


def run_recorder(run: dict, ep: dict, family: str, route: dict, ctx: dict) -> dict:
    """One recorder pass of one episode on one family route: a fresh store, the real host, what it did and what it stored."""
    label = f'recorder-{family}-{run["name"]}-{ep["index"]:03d}'
    work = Path(tempfile.mkdtemp(prefix=f'{label}-', dir=ctx['work']))
    allowance, hold = ctx['spend'].reserve(ctx['profile']['recorder']['pass_max_requests'], ctx['bound'])
    base = dict(role='recorder', run=run['name'], episode=ep['index'], family=family, kind=ep['kind'], group=ep['group'],
                with_subgoal=bool(ep['subgoal']), expected=len(ep['subgoal']['expected_observations']) if ep['subgoal'] else 0)
    if allowance < 1:
        shutil.rmtree(work, ignore_errors=True)
        return dict(base, ran=False, valid=False, terminal=None, observation_status=None, max_repeat=0)
    state = None
    try:
        state = recorder_state(run, ep, work / 'store', ctx['profile'], ctx['distances'][run['name']], ctx['episode_role'], allowance)
        record = reader_pass(role='recorder', application=state['application'], reader=state['recorder'], session=run['session'],
            route=route, context=lane_context('recorder', run), stdin=state['document'], directory=work / 'host', out=ctx['out'] / 'samples',
            label=label, allowance=allowance, seconds=int(ctx['profile']['recorder']['pass_seconds']), effort=ctx['effort'],
            host_argv=ctx['host_argv'], secret=ctx['secret'], hold=hold, bound=ctx['bound'])
        views = [v for v in state['application'].settled_episodes(actor_id=state['actor']['actor_id'])
                 if v['first_position'] == ep['start_pos']]
        stored = views[0] if views else None
        terminal = {'episode-record': 'record', 'episode-abstain': 'abstain'}.get(record['terminal'])
        result = dict(base, ran=True, valid=record['terminal'] is not None and not record['uncertain'], terminal=terminal,
                      outcome=record['outcome'], settled_reason=record['settled_reason'], requests=record['requests'],
                      charged_usd=record['charged_usd'], configured_cost_usd=record['configured_cost_usd'],
                      refusals=record['refusals'], max_repeat=record['repeated_identical_refusal'],
                      missing_usage_attempts=record['missing_usage_attempts'], stopped_by_spend_guard=record['stopped_by_spend_guard'],
                      cleanup_absent=record['cleanup_absent'], uncertain_terminals=record['uncertain'], allowance=allowance,
                      frames=len(state['document']['frames']),
                      store=None if stored is None else dict(settled=stored['settled'], reason_code=stored.get('reason_code')),
                      observation_status=stored['observation_status'] if stored and stored['settled'] == 'recorded' else None,
                      confidence=stored.get('confidence') if stored else None)
        ctx['spend'].release(hold, record['charged_usd'], record['dearest_request_usd'])
        return result
    except BaseException:
        ctx['spend'].release(hold, 0., 0.)
        raise
    finally:
        if state is not None:
            state['runtime'].close()
            state['memory'].close()
        shutil.rmtree(work, ignore_errors=True)


def run_level(prepared: dict, route: dict, ctx: dict) -> dict:
    """One level pass at one sampled wake point, on the live replay state prepared for it."""
    wake = prepared['wake']
    label = f'level-F1-{wake["run"]}-{wake["index"]:03d}'
    work = Path(tempfile.mkdtemp(prefix=f'{label}-', dir=ctx['work']))
    allowance, hold = ctx['spend'].reserve(wake['allowance_requests'], ctx['bound'])
    base = dict(role='level', run=wake['run'], wake=wake['index'], reason=wake['reason'], family='F1',
                episodes_pushed=len(prepared['pushed']['episodes']), had_subgoal=prepared['pushed']['intent']['subgoal'] is not None)
    try:
        if allowance < 1:
            return dict(base, ran=False, valid=False, max_repeat=0)
        record = reader_pass(role='level', application=prepared['application'], reader=prepared['level'], session=prepared['session'],
            route=route, context=prepared['context'], stdin=prepared['text'], directory=work / 'host', out=ctx['out'] / 'samples',
            label=label, allowance=allowance, seconds=int(wake['allowance_seconds']), effort=ctx['effort'], host_argv=ctx['host_argv'],
            secret=ctx['secret'], hold=hold, bound=ctx['bound'])
        ctx['spend'].release(hold, record['charged_usd'], record['dearest_request_usd'])
        hold = 0.
        return dict(base, ran=True, valid=record['terminal'] in ('level-commit', 'level-abstain') and not record['uncertain'],
                    terminal=record['terminal'], outcome=record['outcome'], settled_reason=record['settled_reason'],
                    requests=record['requests'], charged_usd=record['charged_usd'], configured_cost_usd=record['configured_cost_usd'],
                    refusals=record['refusals'], max_repeat=record['repeated_identical_refusal'],
                    missing_usage_attempts=record['missing_usage_attempts'], stopped_by_spend_guard=record['stopped_by_spend_guard'],
                    cleanup_absent=record['cleanup_absent'], uncertain_terminals=record['uncertain'], allowance=allowance)
    finally:
        if hold:
            ctx['spend'].release(hold, 0., 0.)
        prepared['runtime'].close()
        shutil.rmtree(work, ignore_errors=True)


# --- stage 3: the manipulation check ---------------------------------------------------------------------------

TAIL_FORMATTER = '''
import {formatIntentTail, RECALL_LABEL} from %s;
import {readFileSync} from 'node:fs';
const out = [];
for (const line of readFileSync(process.argv[1], 'utf8').split('\\n')) {
  if (!line) continue;
  const value = JSON.parse(line);
  try {
    const tail = formatIntentTail(value, 1024);
    const lines = tail.text.split('\\n'), at = lines.indexOf(RECALL_LABEL);
    out.push({ok: true, shown: at < 0 ? [] : lines.slice(at + 1).map(l => l.split(' ')[0]), subgoal: value.subgoal !== null,
              skipped: tail.skipped_items, bytes: tail.tail_bytes});
  } catch (error) { out.push({ok: false, shown: [], subgoal: false, skipped: 0, bytes: 0}); }
}
process.stdout.write(JSON.stringify(out));
'''


def format_tails(intents: list[dict], node: str, directory: Path) -> list[dict]:
    """The real host formatter over each `player-intent/2` value: which recall source ids are shown, within 1,024 bytes."""
    if not intents:
        return []
    code = TAIL_FORMATTER % json.dumps((ROOT / 'tools/player_host/host.mjs').as_uri())
    with tempfile.TemporaryDirectory(prefix='tails-', dir=directory) as temporary:
        path = Path(temporary) / 'intents.jsonl'
        path.write_text('\n'.join(json.dumps(i) for i in intents))
        result = subprocess.run([node, '--input-type=module', '-e', code, str(path)], capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        raise ValueError(f'The host tail formatter failed: {result.stderr[-600:]}')
    return json.loads(result.stdout)


def tail_items(run: str, entries: list[dict], shas: dict[str, str], node: str, directory: Path) -> dict:
    """Shown recall items and which are marginal, for one run's recorded requests with their intent values."""
    formatted = format_tails([e['intent'] for e in entries], node, directory)
    items, with_tail, unreadable = [], 0, 0
    for entry, tail in zip(entries, formatted, strict=True):
        unreadable += not tail['ok']
        first_sources = {item['first_source'] for item in entry['intent']['recall']['items'] if item['first_source']}
        shown = [source for source in tail['shown'] if source in first_sources]
        with_tail += bool(shown) or tail['subgoal']
        held = entry['request']['held']
        marginal = sum(shas.get(source) not in held for source in shown)
        items.append(dict(run=run, request=entry['request']['request_id'], shown=len(shown), marginal=marginal,
                          subgoal=tail['subgoal'], consistent=entry['request']['consistent']))
    return dict(items=items, requests=len(entries), requests_with_tail=with_tail, unreadable=unreadable)


# --- the probe ---------------------------------------------------------------------------------------------------

def validate_profile(path: Path, theta: float) -> dict:
    value = json.loads(path.read_text())
    level_profile(value, 'narrowed')
    if value['theta'] != theta:
        raise ValueError(f'The profile\'s theta {value["theta"]} is not the ladder\'s {theta}')
    return value


def build_lineages(names: list[str]) -> list[list[str]]:
    """Runs grouped into lineages in replay order: the persistent sessions in sequence, every other run alone."""
    shared = [n for n in LINEAGE if n in names]
    groups = [[n] for n in names if n not in LINEAGE]
    return ([shared] if shared else []) + groups


def probe(*, ladder_dir: Path, runs_root: Path, protocol: Path, thresholds_path: Path, route_paths: dict[str, Path], profile_path: Path,
          name: str, max_usd: float, secret: str | None, host_argv: list[str], runs: list[str] | None = None, no_subgoal: int = 33,
          wake_count: int = 40, effort: str = 'medium', actor_allowance: int = 100, recorder_requests: int = 2, level_requests: int = 3,
          sample_estimate_usd: float = DEFAULT_SAMPLE_ESTIMATE_USD, max_request_usd: float | None = None, workers: int = 4,
          dry_run: bool = False, probe_root: Path = PROBE_ROOT, node: str | None = None) -> dict:
    """Run the three stages and write the labelled report under the probes directory.

    Everything that can refuse does so before anything is written or spent: the cap, the thresholds, a dirty checkout, the
    routes\' schema and cost, the profile and the output location. `dry_run` builds every input (stores, bound episodes,
    recorder documents, wake plans, level inputs, tails) and counts them, with no host, credential or spend.
    """
    thresholds = load_thresholds(thresholds_path)
    if not max_usd > 0 or max_usd > thresholds['max_usd']:
        raise ValueError(f'A positive --max-usd no greater than the thresholds\' {thresholds["max_usd"]} is required')
    if not (max_request_usd if max_request_usd is not None else sample_estimate_usd) > 0:
        raise ValueError('A positive per-request cost bound (--max-request-usd or --sample-estimate-usd) is required')
    commit, dirty = git_state()
    if dirty and not dry_run:
        raise ValueError('The checkout has uncommitted changes to tracked files; a paid probe runs only from a clean commit')
    if set(route_paths) != {'F1', 'F2'}:
        raise ValueError('Give the F1 and F2 routes')
    routes = {family: load_route(path, 1, None) for family, path in route_paths.items()}
    for family, route in routes.items():
        if route.get('max_context_images', 0) < 8:
            raise ValueError(f'{family}: the recorder pins up to 7 frames and reads one more; the route needs max_context_images >= 8')
    for role in (LEVEL_ROLE, EPISODE_ROLE):
        if sha256_file(role) != FROZEN_ROLE_SHA256[role.name]:
            raise ValueError(f'{role.name} differs from its frozen digest')
    ladder = load_ladder(ladder_dir)
    profile = validate_profile(profile_path, ladder['theta'])
    if not dry_run and (secret is None or node is None):
        raise ValueError('A paid run needs the credential and Node.js')
    out = (probe_root / name).resolve()
    if not out.is_relative_to(probe_root.resolve()) or out == probe_root.resolve():
        raise ValueError('Probe outputs are written only under .runtime/probes')
    document = ladder['document']
    names = sorted(runs if runs else document['sessions'])
    unknown = [n for n in names if n not in document['sessions']]
    if unknown:
        raise ValueError(f'Runs the ladder does not hold: {unknown}')
    by_run = episodes_by_run(document)
    probe_root.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    work = out / 'work'
    work.mkdir()
    try:
        return _probe(dict(locals(), thresholds=thresholds, commit=commit, dirty=dirty, ladder=ladder, profile=profile, routes=routes,
                           out=out, work=work, names=names, by_run=by_run, document=document))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _probe(c: dict) -> dict:
    ladder, document, thresholds, profile = c['ladder'], c['document'], c['thresholds'], c['profile']
    names, by_run, out, work, routes = c['names'], c['by_run'], c['out'], c['work'], c['routes']
    seed = thresholds['interval']['seed']
    loaded = {n: load_run(c['runs_root'], n, document['sessions'][n]) for n in sorted(document['sessions'])}
    pool = [latency for n in sorted(loaded) for latency in loaded[n]['latencies']]
    role_prompts = dict(level=LEVEL_ROLE.read_text().strip(), episode=EPISODE_ROLE.read_text().strip())
    records = ladder['records']

    # Inputs and the cut-difference count over the selected runs.
    inputs = dict(protocol=sha256_file(c['protocol']), thresholds=sha256_file(c['thresholds_path']), profile=sha256_file(c['profile_path']),
                  routes={f: sha256_file(p) for f, p in c['route_paths'].items()}, ladder=ladder['digests'],
                  role_prompts={r.name: sha256_file(r) for r in (LEVEL_ROLE, EPISODE_ROLE)},
                  runs={n: dict(loaded[n]['inputs'], prompt=hashlib.sha256(loaded[n]['brief'].encode()).hexdigest(),
                                context=hashlib.sha256(loaded[n]['context'].encode()).hexdigest()) for n in names})
    cuts = {n: cut_differences(loaded[n], by_run[n], ladder) for n in names}

    # Stage 1 sample.
    pool_episodes = [e for n in names for e in by_run[n]]
    sample = sample_episodes(pool_episodes, c['no_subgoal'])
    distances = {n: driver_distances(loaded[n]) for n in {e['run'] for e in sample}}

    # Stages 2 and 3: the plan over every selected run that has R1 records for each of its episodes.
    replayable = [n for n in names if all((n, e['index']) in records for e in by_run[n])]
    plans, lineages, carried = {}, {}, {}
    for group in build_lineages(replayable):
        count, subgoal = 0, 0
        for n in group:
            plans[n] = plan_run(loaded[n], by_run[n], records, pool=pool, level=profile, actor_allowance=c['actor_allowance'],
                                carried=count + subgoal, seed=seed, recorder_requests=c['recorder_requests'], level_requests=c['level_requests'])
            count += plans[n]['settles'].get('recorded', 0)
            subgoal = int(any(e['subgoal'] for e in by_run[n]))
    wakes = [w for n in replayable for w in plans[n]['wakes']]
    wake_sample = sample_wakes(wakes, c['wake_count'])

    result_dir = work / 'lineages'
    result_dir.mkdir()

    def lineage_for(group: list[str]) -> Lineage:
        return Lineage(result_dir / ('-'.join(group) + f'-{len(lineages)}'))

    def prefix(group: list[str], upto: str, lineage: Lineage) -> None:
        for earlier in group[:group.index(upto)]:
            state = replay(loaded[earlier], plans[earlier], by_run[earlier], records, lineage, profile)
            state['runtime'].close()

    # Stage 3 first (free): tails over every replayable run's recorded requests.
    projections, exclusions, tail_runs = {}, {}, {}
    for n in names:
        if n not in replayable:
            exclusions[n] = 'no R1 record for every episode, so the replay has no recorded claims to recall'
            continue
        projections[n] = actor_projection(loaded[n])
        if projections[n]['exclusion']:
            exclusions[n] = projections[n]['exclusion']
    shas = {}
    for n in loaded:
        for source, metadata in loaded[n]['frames'].items():
            shas[source] = json.loads(metadata).get('sha256')
    tail_results, conversion_failures = [], []
    node = c['node'] or shutil.which('node')
    for group in build_lineages(replayable):
        lineage = lineage_for(group)
        lineages[tuple(group)] = lineage
        try:
            for n in group:
                if n in exclusions:
                    state = replay(loaded[n], plans[n], by_run[n], records, lineage, profile)
                    state['runtime'].close()
                    continue
                entries: list = []
                state = replay(loaded[n], plans[n], by_run[n], records, lineage, profile, tails=entries, projection=projections[n])
                state['runtime'].close()
                tail_results.append(tail_items(n, entries, shas, node, work) if node else dict(items=[], requests=len(entries),
                                                                                         requests_with_tail=0, unreadable=0))
            conversion_failures += lineage.conversion_failures
        finally:
            lineage.close()
    tail_flat = [item for result in tail_results for item in result['items']]
    stage3 = dict(runs_included=sorted(n for n in replayable if n not in exclusions), exclusions=exclusions,
                  requests=sum(r['requests'] for r in tail_results), requests_with_tail=sum(r['requests_with_tail'] for r in tail_results),
                  shown_items=sum(i['shown'] for i in tail_flat), marginal_items=sum(i['marginal'] for i in tail_flat),
                  formatter_failures=sum(r['unreadable'] for r in tail_results),
                  requests_without_projection=sum(len(loaded[n]['request_walls']) - len(projections[n]['requests']) for n in projections
                                                  if n not in exclusions),
                  projection_mismatches=sum(projections[n]['mismatched'] for n in projections if n not in exclusions),
                  conversion_failures=conversion_failures)

    # Stage 1 and 2 inputs (the dry run builds and counts them; a paid run also runs the hosts).
    spend = Spend(c['max_usd'])
    bound = c['max_request_usd'] if c['max_request_usd'] is not None else c['sample_estimate_usd'] / profile['pass_max_requests']
    ctx = dict(work=work, out=out, spend=spend, profile=profile, bound=bound, effort=c['effort'], host_argv=c['host_argv'], secret=c['secret'],
               distances=distances, episode_role=role_prompts['episode'])
    stage2_inputs = []

    def prepare_wake(wake: dict) -> dict:
        """The replay stopped at one sampled wake: the live store, the driver\'s level input and the run\'s brief."""
        n = wake['run']
        group = next(g for g in build_lineages(replayable) if n in g)
        lineage = Lineage(result_dir / f'wake-{n}-{wake["index"]:03d}')
        try:
            prefix(group, n, lineage)
            state = replay(loaded[n], plans[n], by_run[n], records, lineage, profile, stop_wake=wake['index'])
        except BaseException:
            lineage.close()
            raise
        note = dict(reason=wake['reason'], pass_index=wake['index'], settled_episodes=wake['settled_episodes'],
                    allowance_requests=wake['allowance_requests'], allowance_seconds=wake['allowance_seconds'])
        text = level_text(role_prompts['level'], loaded[n]['brief'], note, state['pushed'])
        return dict(wake=wake, text=text, pushed=state['pushed'], application=state['application'], runtime=state['runtime'],
                    level=state['level'], session=loaded[n]['session'], context=lane_context('level', loaded[n]), lineage=lineage)

    stage2 = []
    for wake in wake_sample:
        prepared = prepare_wake(wake)
        stage2_inputs.append(dict(run=wake['run'], wake=wake['index'], reason=wake['reason'], bytes=len(prepared['text'].encode()),
                                  episodes_pushed=len(prepared['pushed']['episodes']),
                                  recall_items=len(prepared['pushed']['intent']['recall']['items']),
                                  subgoal=prepared['pushed']['intent']['subgoal'] is not None))
        if c['dry_run']:
            prepared['runtime'].close()
            prepared['lineage'].close()
            continue
        stage2.append(prepared)

    stage1_inputs = []
    for ep in sample:
        for family in ('F1', 'F2'):
            if not c['dry_run']:
                continue
            state = recorder_state(loaded[ep['run']], ep, work / f'dry-{ep["run"]}-{ep["index"]}-{family}', profile, distances[ep['run']],
                                   role_prompts['episode'], profile['recorder']['pass_max_requests'])
            if family == 'F1':
                stage1_inputs.append(dict(run=ep['run'], episode=ep['index'], kind=ep['kind'], subgoal=bool(ep['subgoal']),
                                          frames=len(state['document']['frames']),
                                          bytes=len(json.dumps(state['document']).encode()), sources=len(state['pushed']['sources'])))
            state['runtime'].close()
            state['memory'].close()
            shutil.rmtree(work / f'dry-{ep["run"]}-{ep["index"]}-{family}', ignore_errors=True)

    counts = dict(
        runs_selected=len(names), runs_replayable=len(replayable), episodes_in_runs=len(pool_episodes),
        episodes_with_subgoal=sum(1 for e in pool_episodes if e['subgoal']), stage1_episodes=len(sample),
        stage1_with_subgoal=sum(1 for e in sample if e['subgoal']), stage1_without_subgoal=sum(1 for e in sample if not e['subgoal']),
        stage1_passes_planned=2 * len(sample), wake_points=len(wakes), stage2_sampled=len(wake_sample),
        wake_points_by_run={n: len(plans[n]['wakes']) for n in replayable},
        actor_requests=stage3['requests'], actor_requests_with_tail=stage3['requests_with_tail'],
        cut_differences=sum(v['differ'] for v in cuts.values()), cut_episodes=sum(v['episodes'] for v in cuts.values()),
        cut_rule_reproduced_runs=sum(v['reproduces'] for v in cuts.values()))
    base = dict(schema=SCHEMA, label=LABEL, excluded_from_evidence=True,
        scope='Replays recorded #345 runs through the real recorder and level hosts (and the real intent() over replay stores) to '
              'check that the v4 interfaces can be called correctly on the route and whether the intent tail supplies images the '
              'actor lacked. It says nothing about recorder quality, intent quality, play or outcomes.',
        interface=dict(host='player-host/6', role_prompts={r.name: sha256_file(r) for r in (LEVEL_ROLE, EPISODE_ROLE)},
                       profile=profile, intent_audience='tail'),
        source=dict(commit=c['commit'], clean=not c['dirty']),
        inputs=inputs, parameters=dict(max_usd=c['max_usd'], sample_estimate_usd=c['sample_estimate_usd'], max_request_usd=c['max_request_usd'],
            effort=c['effort'], actor_allowance=c['actor_allowance'], recorder_requests=c['recorder_requests'], level_requests=c['level_requests'],
            no_subgoal=c['no_subgoal'], wake_count=c['wake_count'], workers=c['workers'], runs=names, dry_run=c['dry_run'],
            routes={f: dict(model=r['model']['id'], provider=r['model'].get('provider'),
                            routing=(r['model'].get('compat') or {}).get('openRouterRouting'), cost=r['model']['cost'],
                            max_context_images=r['max_context_images']) for f, r in routes.items()}),
        thresholds=dict(definition=thresholds, file_sha256=inputs['thresholds']), limits=list(LIMITS), counts=counts, cuts=cuts,
        stage3=stage3, stage1_inputs=stage1_inputs, stage2_inputs=stage2_inputs)
    if c['dry_run']:
        base.update(spend=dict(charged_usd=0., max_usd=c['max_usd']), status='dry-run')
        _write(out / 'report.json', base)
        return base

    # Paid: the level passes first (fewest, and each needs a live store), then the recorder in hash order, both families adjacent.
    with concurrent.futures.ThreadPoolExecutor(max_workers=c['workers']) as pool_executor:
        level_futures = [pool_executor.submit(run_level, prepared, routes['F1'], ctx) for prepared in stage2]
        level_results = [f.result() for f in level_futures]
        for prepared in stage2:
            prepared['lineage'].close()
        recorder_futures = [pool_executor.submit(run_recorder, loaded[ep['run']], ep, family, routes[family], ctx)
                            for ep in sample for family in ('F1', 'F2')]
        recorder_results = [f.result() for f in recorder_futures]
    f1 = [r for r in recorder_results if r['family'] == 'F1']
    f2 = [r for r in recorder_results if r['family'] == 'F2']
    # A pass the cap kept from launching is incomplete data, not an invalid pass: the statistics use the passes that ran.
    statistics_ = evaluate(thresholds, [r for r in f1 if r['ran']], [r for r in f2 if r['ran']],
                           [r for r in level_results if r['ran']], tail_flat)
    ran = [r for r in [*recorder_results, *level_results] if r['ran']]
    incomplete = any(not r['ran'] for r in [*recorder_results, *level_results]) or any(r['stopped_by_spend_guard'] for r in ran) \
        or spend.skipped > 0

    def summary(items: list[dict]) -> dict:
        return dict(passes=len(items), ran=sum(i['ran'] for i in items), valid=sum(i['valid'] for i in items),
                    terminals=dict(collections.Counter(i.get('outcome') or 'no-terminal-call' for i in items if i['ran'])),
                    settled_reasons=dict(collections.Counter(str(i.get('settled_reason')) for i in items if i['ran'])),
                    refusals=dict(sum((collections.Counter(i.get('refusals', {})) for i in items), collections.Counter())),
                    requests=sum(i.get('requests', 0) for i in items), charged_usd=sum(i.get('charged_usd', 0) for i in items),
                    configured_cost_usd=sum(i.get('configured_cost_usd', 0) for i in items))
    per_run = {}
    for n in names:
        per_run[n] = dict(recorder_F1=summary([r for r in f1 if r['run'] == n]), recorder_F2=summary([r for r in f2 if r['run'] == n]),
                          level=summary([r for r in level_results if r['run'] == n]),
                          tail=dict(shown=sum(i['shown'] for i in tail_flat if i['run'] == n),
                                    marginal=sum(i['marginal'] for i in tail_flat if i['run'] == n)))
    base.update(
        status='incomplete' if incomplete else 'complete', passed=bool(statistics_['all_passed'] and not incomplete),
        spend=dict(charged_usd=spend.spent, max_usd=c['max_usd'], skipped_passes=spend.skipped, passes_run=len(ran),
                   passes_planned=len(recorder_results) + len(level_results), dearest_request_usd=spend.dearest,
                   missing_usage_attempts=sum(r.get('missing_usage_attempts', 0) for r in ran),
                   stopped_by_spend_guard=any(r['stopped_by_spend_guard'] for r in ran) or spend.skipped > 0),
        gates=statistics_['gates'], family_two=statistics_['f2'],
        recorder=dict(F1=summary(f1), F2=summary(f2)), level=summary(level_results),
        per_run=per_run, passes=dict(recorder=recorder_results, level=level_results))
    _write(out / 'report.json', base)
    return base


def _write(path: Path, value: dict) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, default=str)
        stream.write('\n')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ladder', type=Path, required=True, help="#345's ladder directory (episodes.json, records.jsonl)")
    parser.add_argument('--runs-root', type=Path, required=True, help='The directory of recorded computer sessions')
    parser.add_argument('--protocol', type=Path, required=True, help='The frozen protocol.md (hashed into the report)')
    parser.add_argument('--thresholds', type=Path, required=True, help=f'The frozen {THRESHOLDS_SCHEMA} file')
    parser.add_argument('--route-f1', type=Path, required=True, help='The F1 (production) player-host/6 route')
    parser.add_argument('--route-f2', type=Path, required=True, help='The F2 player-host/6 route, the model block given explicitly')
    parser.add_argument('--profile', type=Path, required=True, help='The level block of a campaign-run/5 profile (pass allowances)')
    parser.add_argument('--name', required=True, help='Output directory name under .runtime/probes')
    parser.add_argument('--max-usd', type=float, required=True, help='Hard spend cap on the charged cost, at most the thresholds\' max_usd')
    parser.add_argument('--dry-run', action='store_true', help='Build and count every input; no host, credential or spend')
    parser.add_argument('--run', dest='runs', action='append', help='Only this recorded run (repeatable)')
    parser.add_argument('--no-subgoal', type=int, default=33)
    parser.add_argument('--wakes', type=int, default=40)
    parser.add_argument('--effort', default='medium')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--actor-allowance', type=int, default=100)
    parser.add_argument('--sample-estimate-usd', type=float, default=DEFAULT_SAMPLE_ESTIMATE_USD,
                        help='A pass\'s estimated cost; divided by the level pass allowance it bounds a request without usage')
    parser.add_argument('--max-request-usd', type=float, help='The route\'s maximum cost of one request; replaces the estimate-derived bound')
    parser.add_argument('--host-node', default=shutil.which('node'))
    args = parser.parse_args(argv)
    if not args.host_node:
        parser.error('Node.js is required to run the hosts')
    report = probe(ladder_dir=args.ladder.resolve(), runs_root=args.runs_root.resolve(), protocol=args.protocol.resolve(),
                   thresholds_path=args.thresholds.resolve(), route_paths={'F1': args.route_f1.resolve(), 'F2': args.route_f2.resolve()},
                   profile_path=args.profile.resolve(), name=args.name, max_usd=args.max_usd,
                   secret=None if args.dry_run else keychain_secret(), host_argv=[args.host_node, str(ROOT / 'tools/player_host/run.mjs')],
                   runs=args.runs, no_subgoal=args.no_subgoal, wake_count=args.wakes, effort=args.effort, actor_allowance=args.actor_allowance,
                   sample_estimate_usd=args.sample_estimate_usd, max_request_usd=args.max_request_usd, workers=args.workers,
                   dry_run=args.dry_run, node=args.host_node)
    print(json.dumps(dict(label=report['label'], output=str(PROBE_ROOT / args.name / 'report.json'), status=report['status'],
                          passed=report.get('passed'), spend=report['spend'], counts=report['counts'],
                          gates={k: dict(point=v['point'], lower=v['lower'], passed=v['passed']) for k, v in report.get('gates', {}).items()}),
                     indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
