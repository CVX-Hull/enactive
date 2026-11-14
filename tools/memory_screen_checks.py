"""Free checks for the memory screen (#590) on sealed evidence. Read-only: no game, no model call, no git process.

  python -m tools.memory_screen_checks store REPOSITORY... [--find LABEL=REGEX ...] [--runs RUNS...] [--json]
  python -m tools.memory_screen_checks replay RUNS... --loss LABEL:need=FRAME[,record=ID][,fact=ID] ...
        [--records ROOT] [--knowledge REPOSITORY] [--lags N ...] [--json]
  python -m tools.memory_screen_checks cut RUNS... [--lags N ...] [--turn-tokens N] [model options] [--json]

`store` lists every published version of a curator knowledge repository (its facts, articles and the bytes of `facts.jsonl`)
and, for each --find pattern, the facts whose ID or text matches: the version and session that first published
each, the frames it cites and whether a later version changed or dropped it. It reads the repository's loose
objects itself, so nothing is written into a sealed directory; a packed repository is refused.

`replay` places a known loss on the lineage's request sequence: the request that returned the frame at which play
needed the fact, when the player's own record was written, when a briefing at each actor's start would first have
shown it, and when the curator's fact would have reached the actor under sessions at admission boundaries only or
at handoffs too.

`cut` simulates the context design's cut over the recorded request sequences. Every figure it prints except the
`recorded` row is simulated from the model below, not measured.

RUNS are as in `tools.memory_reads`, in lineage order. A lineage request number counts requests over those runs'
actors in order. The context design is docs/design/player-context.md.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Sequence
import zlib

from harness.evaluation.core.host import LARGE_REWRITE_CACHE_TOKENS, HostFacts, frame_source, host_facts, memory_reads
from harness.evaluation.core.metrics import nearest_rank
from harness.evaluation.core.sources import read_carry, read_host, run_archive_entry
from tools.memory_reads import game_clock, run_dirs

LAGS = (10, 20, 47, 94)


# --- the lineage's requests -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Actor:
    """One actor's place in the lineage. `first` is the lineage number of its first request."""

    run: str
    name: str
    actor: str
    first: int
    requests: int
    successor: bool
    wall: float | None


@dataclass(frozen=True)
class Run:
    name: str
    facts: HostFacts
    carry: dict[str, frozenset[str]]
    offset: int  # lineage requests before this run


def read_lineage(runs: Sequence[Path]) -> tuple[list[Run], list[Actor]]:
    lineage, actors, offset = [], [], 0
    for run in runs:
        entry = run_archive_entry(run)
        host, names = {}, {}
        for directory in sorted(p for p in (run / 'actors').iterdir() if (p / 'host.jsonl').is_file()):
            actor, events = read_host(directory / 'host.jsonl', directory.name, entry)
            host[actor], names[actor] = events, directory.name
        facts = host_facts(tuple(host), host)
        lineage.append(Run(run.name, facts, read_carry(run), offset))
        spans: dict[str, list] = {}
        for request in facts.requests:
            span = spans.setdefault(request.actor, [request.decision, request.decision, request.wall])
            span[0], span[1] = min(span[0], request.decision), max(span[1], request.decision)
        for position, actor in enumerate(host):
            if actor in spans:
                low, high, wall = spans[actor]
                actors.append(Actor(run.name, names[actor], actor, offset + low, high - low + 1, position > 0, wall))
        offset += max((request.decision for request in facts.requests), default=0)
    return lineage, actors


def place(actors: Sequence[Actor], number: int) -> dict:
    """A lineage request number as run, actor and the actor's own request number."""
    actor = next(a for a in reversed(actors) if a.first <= number)
    return dict(lineage_request=number, run=actor.run, actor=actor.name, request=number - actor.first + 1,
        actor_requests=actor.requests)


def frame_index(lineage: Sequence[Run]) -> dict[str, tuple[int, float | None]]:
    """Each frame's lineage request number (the request whose call returned it) and wall time."""
    found = {}
    for run in lineage:
        for call in run.facts.calls:
            source = frame_source(call)
            if source is not None and call.decision is not None:
                found.setdefault(source, (run.offset + call.decision, call.wall))
    return found


def day(seconds: int | None) -> str | None:
    return None if seconds is None else f'day {seconds // 86400 + 1} {seconds % 86400 // 3600:02d}:{seconds % 3600 // 60:02d}'


# --- the curator's knowledge repository, read without git ----------------------------------------------------------

class StoreError(ValueError):
    """The repository cannot be read without changing it."""


def _object(objects: Path, identity: str) -> tuple[str, bytes]:
    path = objects / identity[:2] / identity[2:]
    if not path.is_file():
        raise StoreError(f'{objects}: object {identity} is not a loose object; packed repositories are not read')
    head, _, body = zlib.decompress(path.read_bytes()).partition(b'\0')
    return head.split()[0].decode(), body


def _entries(objects: Path, tree: str) -> dict[str, str]:
    kind, body = _object(objects, tree)
    if kind != 'tree':
        raise StoreError(f'{objects}: {tree} is a {kind}, not a tree')
    entries, at = {}, 0
    while at < len(body):
        space, end = body.index(b' ', at), body.index(b'\0', at)
        entries[body[space + 1:end].decode()] = body[end + 1:end + 21].hex()
        at = end + 21
    return entries


def read_versions(repository: Path) -> list[dict]:
    """Every published /3 snapshot: facts and articles separately, with its byte size."""
    objects, tags = repository / '.git' / 'objects', repository / '.git' / 'refs' / 'tags'
    if not tags.is_dir():
        raise StoreError(f'{repository}: no loose version tags')
    versions = []
    for tag in sorted((p for p in tags.iterdir() if re.fullmatch(r'v\d+', p.name)), key=lambda p: int(p.name[1:])):
        commit = tag.read_text().strip()
        kind, body = _object(objects, commit)
        if kind != 'commit':
            raise StoreError(f'{repository}: {tag.name} is a {kind}, not a commit')
        files = _entries(objects, body.split(b'\n', 1)[0].split()[1].decode())
        metadata = json.loads(_object(objects, files['knowledge.json'])[1])
        if not isinstance(metadata, dict) or metadata.get('schema') != 'curator-knowledge/2':
            raise StoreError(f'{repository} {tag.name}: expected curator-knowledge/2; start a new repository')
        data = _object(objects, files['facts.jsonl'])[1]
        records = [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
        for record in records:
            if not isinstance(record, dict) or record.get('schema') != 'curator-fact/3':
                raise StoreError(f'{repository} {tag.name}: unsupported record schema; expected curator-fact/3')
            if record.get('record') not in ('fact', 'article'):
                raise StoreError(f'{repository} {tag.name}: unsupported record kind; expected fact or article')
        versions.append(dict(version=tag.name, commit=commit, bytes=len(data),
                             facts=[r for r in records if r['record'] == 'fact'],
                             articles=[r for r in records if r['record'] == 'article']))
    return versions


def session_runs(repository: Path) -> dict[str, list[str]]:
    """The trace sessions each curator session was given, from the session manifests beside the repository."""
    found = {}
    for path in sorted((repository.parent / f'{repository.name}.state' / 'sessions').glob('*/manifest.json')):
        manifest = json.loads(path.read_text())
        found[path.parent.name] = list(manifest.get('inputs', {}).get('trace_sessions') or ())
    return found


def fact_history(versions: Sequence[dict], identity: str) -> dict | None:
    """Where a fact first appears and what later versions did to it."""
    first, changed, dropped, last = None, [], None, None
    for version in versions:
        fact = next((f for f in version['facts'] if f.get('id') == identity), None)
        if fact is None:
            if first is not None and dropped is None:
                dropped = version['version']
            continue
        if first is None:
            first = dict(fact, version=version['version'])
        elif fact != last:
            changed.append(version['version'])
        last = fact
    return None if first is None else dict(id=identity, version=first['version'], session=first.get('session'),
        type=first.get('type'), text=first.get('text'), citations=first.get('citations') or [],
        changed_in=changed, dropped_in=dropped, latest_text=last.get('text'))


def store_report(repositories: Sequence[Path], finds: Sequence[str], runs: Sequence[Path]) -> list[dict]:
    lineage, actors = read_lineage(runs) if runs else ([], [])
    frames = frame_index(lineage)
    reports = []
    for repository in repositories:
        versions, sessions = read_versions(repository), session_runs(repository)
        rows, previous = [], {}
        for version in versions:
            facts = {fact['id']: fact for fact in version['facts']}
            session = next((r.get('session') for r in [*version['facts'], *version['articles']]
                            if r.get('published_in') == version['version']), None)
            rows.append(dict(version=version['version'], session=session, covers=sessions.get(session, []),
                facts=len(facts), articles=len(version['articles']),
                current_facts=sum('superseded_by' not in f and 'retired' not in f for f in facts.values()),
                current_articles=sum('superseded_by' not in a and 'retired' not in a for a in version['articles']),
                bytes=version['bytes'], added=sum(i not in previous for i in facts),
                changed=sorted(i for i in facts if i in previous and facts[i] != previous[i]),
                dropped=sorted(i for i in previous if i not in facts)))
            previous = facts
        found = {}
        for find in finds:
            label, _, pattern = find.partition('=')
            match = re.compile(pattern, re.IGNORECASE)
            ids = dict.fromkeys(fact['id'] for version in versions for fact in version['facts']
                if match.search(f"{fact['id']} {fact.get('text', '')}"))
            found[label] = []
            for identity in ids:
                history = fact_history(versions, identity)
                history['cited'] = [dict(frame=frame, **place(actors, frames[frame][0])) for frame in history['citations']
                    if frame in frames]
                found[label].append(history)
        reports.append(dict(repository=str(repository), versions=rows, found=found))
    return reports


# --- replay of a loss against the design's delivery ---------------------------------------------------------------
def replay(runs: Sequence[Path], losses: Sequence[str], records: Path | None, knowledge: Path | None,
           lags: Sequence[int]) -> list[dict]:
    lineage, actors = read_lineage(runs)
    frames, clock = frame_index(lineage), game_clock(records)
    versions = read_versions(knowledge) if knowledge else []
    sessions = session_runs(knowledge) if knowledge else {}
    written: dict[str, tuple[int, float | None]] = {}  # record ID -> lineage request and wall of its append
    held: dict[tuple[str, str], list[tuple[int, str, str]]] = {}  # (run, actor) -> (lineage request, record ID, how)
    for run in lineage:
        order = list(run.facts.actors)
        start = {a.actor: a for a in actors if a.run == run.name}
        for giver, taker in zip(order, order[1:]):
            if taker in start:
                held.setdefault((run.name, taker), []).extend((start[taker].first, identity, 'handoff')
                    for identity in run.carry.get(giver, ()))
        for call in run.facts.calls:
            value = call.result if isinstance(call.result, dict) else {}
            if call.tool == 'player_memory_append' and call.finished and not call.error and isinstance(value.get('id'), str) \
                    and call.decision is not None:
                written.setdefault(value['id'], (run.offset + call.decision, call.wall))
        for read in memory_reads(run.facts, run.carry):
            if read.call.decision is not None:
                held.setdefault((run.name, read.call.actor), []).extend((run.offset + read.call.decision, record['id'],
                    'read') for record in read.records)

    def moment(number: int, wall: float | None) -> dict:
        return dict(place(actors, number), game_time=day(clock(wall)))

    def start_of(actor: Actor) -> dict:
        return moment(actor.first, actor.wall)

    rows = []
    for loss in losses:
        label, _, rest = loss.partition(':')
        spec = dict(part.split('=', 1) for part in rest.split(','))
        if spec['need'] not in frames:
            raise ValueError(f'{label}: frame {spec["need"]} is not returned by any call of the selected runs')
        need_number, need_wall = frames[spec['need']]
        needing = next(a for a in reversed(actors) if a.first <= need_number)
        row = dict(label=label, need=moment(need_number, need_wall), needing_actor_start=start_of(needing))
        if 'record' in spec:
            identity = next((i for i in written if i.startswith(spec['record'])), None)
            if identity is None:
                raise ValueError(f'{label}: no append of a record starting {spec["record"]} in the selected runs')
            number, wall = written[identity]
            after = [a for a in actors if a.first > number]
            got = sorted((n, how) for moments in held.values() for n, i, how in moments
                if i == identity and n >= needing.first)  # the needing actor or any actor after it
            row['record'] = dict(id=identity[:6], written=moment(number, wall),
                first_briefing=start_of(after[0]) if after else None,
                briefing_to_needing_actor=start_of(needing) if needing.first > number else None,
                requests_before_need=need_number - needing.first if needing.first > number else None,
                recorded=dict(place(actors, got[0][0]), how=got[0][1]) if got else None)
        if 'fact' in spec:
            history = fact_history(versions, spec['fact'])
            if history is None:
                raise ValueError(f'{label}: fact {spec["fact"]} is in no version of {knowledge}')
            covered = sessions.get(history['session'], [])
            cited = sorted(frames[frame] for frame in history['citations'] if frame in frames)
            entry = dict(id=history['id'], text=history['text'], version=history['version'], session=history['session'], covers=covered,
                first_cited=moment(*cited[0]) if cited else None)
            order = [run.name for run in lineage]
            last = max((order.index(name) for name in covered if name in order), default=None)
            later = [] if last is None else [a for a in actors if order.index(a.run) > last]
            entry['at_admission_boundaries'] = start_of(later[0]) if later else None
            entry['boundary_before_need'] = bool(later) and later[0].first <= need_number
            if cited:  # a session at the handoff reads the citing actor's trace; the successor gets the difference
                citing = next(a for a in reversed(actors) if a.first <= cited[0][0])
                following = [a for a in actors if a.first > citing.first]
                entry['with_handoff_sessions'] = []
                for lag in lags:
                    if not following:
                        break
                    successor = following[0]
                    waits = successor.run != citing.run  # an admission boundary: the next admission waits
                    number = successor.first if waits else min(successor.first + lag, successor.first + successor.requests - 1)
                    entry['with_handoff_sessions'].append(dict(lag=lag, **place(actors, number), before_need=number <= need_number))
            row['fact'] = entry
        rows.append(row)
    return rows


# --- simulation of the cut ------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class CutModel:
    """The simulated window. Tokens; the defaults are the context design's fitted figures.

    A turn (a tool call with its short result) costs `turn_tokens` when it carries one image: `image_tokens` for the
    image and the rest for text. A request's prompt is the fixed head, the briefing and the turns still in the
    window. An image the host drops outside a cut leaves `marker_tokens` in its turn. A request that extends the one
    before it writes only the new turn to the cache; a request that cuts or drops images writes everything after
    `cached_head_tokens`. `coverage` says which turns a snapshot covers at lag L when the actor has made t turns:
    `steady` covers the first t - L; `sessions` runs one curator session after another, each L turns long and
    covering what existed when it started, so the first L * (t // L - 1)."""

    head_tokens: int = 4500
    cached_head_tokens: int = 3900
    briefing_tokens: int = 0
    turn_tokens: int = 950
    image_tokens: int = 758
    marker_tokens: int = 100
    high_mark: int = 60000
    low_mark: int = 20000
    image_peak: int = 39
    image_block: int = 20
    min_free: int = 1
    coverage: str = 'steady'


def covered_turns(turns: int, lag: int, coverage: str) -> int:
    return max(0, turns - lag if coverage == 'steady' else lag * (turns // lag - 1))


def simulate(images: Sequence[int], model: CutModel, lag: int | None) -> list[dict]:
    """One actor's requests under the model. `images[i]` is the images the conversation held at request i + 1, kept
    or omitted, so turn i carries `images[i] - images[i - 1]`. `lag` None disables the cut. Each row has the prompt
    tokens, the tokens written to the cache, `freed` (None when no cut was due, 0 when one was held back, else the
    turns removed) and whether an image block was dropped."""
    text = model.turn_tokens - model.image_tokens
    window: deque[list] = deque()  # [turn number, images, images dropped]
    tokens, held, rows = model.head_tokens + model.briefing_tokens, 0, []

    def cost(turn: list) -> int:
        return text + turn[1] * (model.marker_tokens if turn[2] else model.image_tokens)

    for index in range(len(images)):
        added = 0
        if index:
            turn = [index, max(0, images[index] - images[index - 1]), False]
            window.append(turn)
            added = cost(turn)
            tokens += added
            held += turn[1]
        freed = None
        if lag is not None and (tokens > model.high_mark or held > model.image_peak):
            limit, plan, after = covered_turns(index, lag, model.coverage), 0, tokens
            for turn in window:
                if after <= model.low_mark or turn[0] > limit:
                    break
                after -= cost(turn)
                plan += 1
            freed = plan if plan >= model.min_free else 0
            for _ in range(freed):
                turn = window.popleft()
                tokens -= cost(turn)
                held -= 0 if turn[2] else turn[1]
        dropped = held > model.image_peak
        if dropped:
            block = model.image_block
            for turn in window:
                if block <= 0:
                    break
                if turn[1] and not turn[2]:
                    turn[2] = True
                    block -= turn[1]
                    held -= turn[1]
                    tokens -= turn[1] * (model.image_tokens - model.marker_tokens)
        rewrite = bool(freed) or dropped
        rows.append(dict(prompt=tokens, freed=freed, image_drop=dropped, rewrite=rewrite,
            write=tokens - model.cached_head_tokens if rewrite else tokens if index == 0 else added))
    return rows


def summarise(label: str, actors: Sequence[Sequence[dict]], recorded_write: float) -> dict:
    """One table row over every actor's requests. A cut is held back when it was due and freed nothing;
    `cuts_held_back` counts each unbroken run of such requests once and `requests_held_back` counts the requests.
    `rewritten` is the part of `cache_write` written by requests that rewrote the conversation."""
    rows = [row for actor in actors for row in actor]
    prompts = [row['prompt'] for row in rows]
    write = sum(row['write'] for row in rows)
    return dict(row=label, requests=len(rows), prompt_p50=nearest_rank(prompts, 0.5), prompt_p95=nearest_rank(prompts, 0.95),
        prompt_max=max(prompts, default=None), cuts=sum(bool(row['freed']) for row in rows),
        cuts_under_ten_turns=sum(bool(row['freed']) and row['freed'] < 10 for row in rows),
        cuts_held_back=sum(row['freed'] == 0 and (not at or actor[at - 1]['freed'] != 0)
            for actor in actors for at, row in enumerate(actor)),
        requests_held_back=sum(row['freed'] == 0 for row in rows), image_drops=sum(row['image_drop'] for row in rows),
        cache_write=round(write), rewritten=round(sum(row['write'] for row in rows if row['rewrite'])),
        cache_write_of_recorded=round(write / recorded_write, 3) if recorded_write else None,
        under_40000=round(sum(p < 40000 for p in prompts) / len(prompts), 3) if prompts else None,
        under_60000=round(sum(p < 60000 for p in prompts) / len(prompts), 3) if prompts else None)


def cut_report(runs: Sequence[Path], model: CutModel, lags: Sequence[int]) -> dict:
    lineage, actors = read_lineage(runs)
    sequences, recorded = [], []
    for run in lineage:
        by_actor: dict[str, dict[int, dict]] = {}
        for request in run.facts.requests:  # a retried request keeps its last attempt
            images = run.facts.images.get((request.actor, request.key))
            omitted = run.facts.omitted.get((request.actor, request.key), 0)
            row = by_actor.setdefault(request.actor, {}).setdefault(request.decision, dict(images=0, omitted=0))
            row.update(images=row['images'] if images is None else images, omitted=omitted)
            if request.usage_available:
                row.update(prompt=(request.input_tokens or 0) + (request.cache_read_tokens or 0)
                    + int(request.cache_write_tokens or 0), write=int(request.cache_write_tokens or 0))
        for requests in by_actor.values():
            ordered = [requests[key] for key in sorted(requests)]
            sequences.append([row['images'] for row in ordered])
            was, actor = 0, []
            for row in ordered:
                if 'prompt' in row:  # a response without usage has no recorded prompt; its turn is still simulated
                    actor.append(dict(prompt=row['prompt'], write=row['write'], freed=None, image_drop=row['omitted'] > was,
                        rewrite=row['write'] > LARGE_REWRITE_CACHE_TOKENS))
                was = row['omitted']
            recorded.append(actor)
    total = sum(row['write'] for actor in recorded for row in actor)
    table = [summarise('recorded', recorded, total)]
    for label, lag in [('no cut', None), *((f'lag {lag}', lag) for lag in lags)]:
        table.append(summarise(label, [simulate(images, model, lag) for images in sequences], total))
    return dict(runs=len(lineage), actors=len(actors), model=asdict(model), rows=table)


# --- rendering ------------------------------------------------------------------------------------------------------

def _where(value: dict | None) -> str:
    if value is None:
        return 'never'
    text = f"{value['run']}/{value['actor']} request {value['request']} of {value['actor_requests']} (lineage request " \
        f"{value['lineage_request']})"
    return text + (f", game {value['game_time']}" if value.get('game_time') else '')


def render_store(reports: Sequence[dict]) -> str:
    lines = []
    for report in reports:
        lines.append(f"== {report['repository']}")
        for row in report['versions']:
            lines.append(f"{row['version']} session {row['session']} covers {','.join(row['covers']) or '-'}: {row['facts']} "
                f"facts ({row['current_facts']} current), {row['articles']} articles ({row['current_articles']} current), "
                f"{row['bytes']} bytes; added {row['added']}, changed {row['changed'] or 'none'}, dropped "
                f"{row['dropped'] or 'none'}")
        for label, found in report['found'].items():
            lines.append(f"find {label}: {len(found)} facts")
            for fact in found:
                cited = '; '.join(f"{c['frame']} = {_where(c)}" for c in fact['cited']) or ', '.join(fact['citations'])
                lines.append(f"  {fact['id']} ({fact['type']}) first in {fact['version']} by {fact['session']}; changed in "
                    f"{fact['changed_in'] or 'none'}; dropped in {fact['dropped_in'] or 'none'}; cites {cited}\n"
                    f"    {fact['text']}")
    return '\n'.join(lines)


def render_replay(rows: Sequence[dict]) -> str:
    lines = []
    for row in rows:
        lines.append(f"== {row['label']}\n  needed at {_where(row['need'])}\n  that actor started at "
            f"{_where(row['needing_actor_start'])}")
        if 'record' in row:
            record = row['record']
            lines.append(f"  player record {record['id']} written at {_where(record['written'])}\n"
                f"    first briefing that would hold it: {_where(record['first_briefing'])}\n"
                f"    briefing to the actor that needed it: {_where(record['briefing_to_needing_actor'])}, "
                f"{record['requests_before_need']} requests before the need\n"
                f"    recorded: from that actor on, first held at {_where(record['recorded'])}"
                f"{' by ' + record['recorded']['how'] if record['recorded'] else ''}")
        if 'fact' in row:
            fact = row['fact']
            lines.append(f"  curator fact {fact['id']} first in {fact['version']} by {fact['session']} (covers "
                f"{','.join(fact['covers']) or '-'}); first cited frame returned at {_where(fact['first_cited'])}\n"
                f"    sessions at admission boundaries only: briefing at {_where(fact['at_admission_boundaries'])}; "
                f"before the need: {fact['boundary_before_need']}")
            for entry in fact.get('with_handoff_sessions', ()):
                lines.append(f"    sessions at handoffs too, lag {entry['lag']}: difference at {_where(entry)}; before the "
                    f"need: {entry['before_need']}")
    return '\n'.join(lines)


def render_cut(report: dict) -> str:
    keys = ('row', 'requests', 'prompt_p50', 'prompt_p95', 'prompt_max', 'cuts', 'cuts_under_ten_turns', 'cuts_held_back',
        'requests_held_back', 'image_drops', 'cache_write', 'rewritten', 'cache_write_of_recorded', 'under_40000',
        'under_60000')
    lines = [f"{report['runs']} runs, {report['actors']} actors; model {json.dumps(report['model'])}",
        'simulated rows are from the model, not measured; `recorded` is from the traces', ' | '.join(keys)]
    lines.extend(' | '.join(str(row[key]) for key in keys) for row in report['rows'])
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    store = commands.add_parser('store', help='versions of a curator knowledge repository and the facts that match')
    store.add_argument('repositories', nargs='+', type=Path)
    store.add_argument('--find', action='append', default=[], metavar='LABEL=REGEX')
    store.add_argument('--runs', nargs='+', type=Path, default=[], help='run directories, to place cited frames')
    again = commands.add_parser('replay', help='a known loss against the briefing and the snapshot differences')
    again.add_argument('runs', nargs='+', type=Path)
    again.add_argument('--loss', action='append', required=True, metavar='LABEL:need=FRAME[,record=ID][,fact=ID]')
    again.add_argument('--records', type=Path, help='evaluation records root, for game time')
    again.add_argument('--knowledge', type=Path, help='the curator knowledge repository that holds each fact=ID')
    again.add_argument('--lags', nargs='+', type=int, default=list(LAGS))
    cut = commands.add_parser('cut', help='simulate the cut over the recorded request sequences')
    cut.add_argument('runs', nargs='+', type=Path)
    cut.add_argument('--lags', nargs='+', type=int, default=list(LAGS))
    for name, value in asdict(CutModel()).items():
        cut.add_argument(f"--{name.replace('_', '-')}", type=type(value), default=value,
            **(dict(choices=('steady', 'sessions')) if name == 'coverage' else {}))
    for command in (store, again, cut):
        command.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'store':
        result, text = store_report(args.repositories, args.find, run_dirs(args.runs) if args.runs else []), render_store
    elif args.command == 'replay':
        result, text = replay(run_dirs(args.runs), args.loss, args.records, args.knowledge, args.lags), render_replay
    else:
        model = CutModel(**{name: getattr(args, name) for name in asdict(CutModel())})
        result, text = cut_report(run_dirs(args.runs), model, args.lags), render_cut
    print(json.dumps(result, indent=1, ensure_ascii=False) if args.json else text(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
