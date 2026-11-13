"""What the player did after each memory read, from sealed host traces (#594). Read-only.

  python -m tools.memory_reads RUNS... [--records ROOT] [--store FILE] [--probes DIR] [--before N] [--after N] [--json]

RUNS are run directories (each holds `actors/NNN/host.jsonl`), or directories whose children are run directories,
taken in the order given and then by name. For every `player_memory_query`, `player_memory_read` and
`player_memory_context` call the listing gives the actor's request number, the wall time, the arguments, each
returned record (its author, its age at the read, and whether the actor already held it) and the actor's calls
before and after the read. A reference marks a later call that types text found in a returned record, reads a
source the record cites, or names the record; `repeated` means the actor had done the same before the read.

--records ROOT adds the evaluator's game clock from the evaluation records `ROOT/<session>/*.sqlite3`.
--store FILE reads the lineage's player-memory/2 store and lists every stored record with how it was delivered.
--probes DIR joins the probe annotations of one lineage (`<run>-<actor>.jsonl`, probe-protocol/1): for each
rediscovery of a fact that names a stored record, whether the rediscovering actor had been given that record.

It counts and lists. It never judges whether a record was used: that is a reviewer's reading of this output.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from harness.evaluation.core.host import (MEMORY_READ_TOOLS, ToolCall, frame_source, host_facts, memory_reads,
    record_ids, typed_text)
from harness.evaluation.core.records import open_readonly, read_steps
from harness.evaluation.core.sources import read_carry, read_host, read_memory, run_archive_entry

MEMORY_TOOLS = ('player_memory_append', *MEMORY_READ_TOOLS)


def run_dirs(paths: list[Path]) -> list[Path]:
    found = []
    for path in paths:
        if (path / 'actors').is_dir():
            found.append(path)
        elif path.is_dir():
            found.extend(sorted(child for child in path.iterdir() if (child / 'actors').is_dir()))
        else:
            raise ValueError(f'{path}: not a run directory or a directory of run directories')
    if not found:
        raise ValueError('No run directory selected')
    return found


def game_clock(root: Path | None):
    """Map a wall time to the evaluator's game time at the last step at or before it, over every record in `root`."""
    steps = []
    for record in sorted(root.glob('*/*.sqlite3')) if root else ():
        connection = open_readonly(record)
        try:
            steps.extend((step.wall, step.game_time) for step in read_steps(connection) if step.game_time is not None)
        finally:
            connection.close()
    steps.sort()
    walls = [wall for wall, _ in steps]

    def at(wall: float | None) -> int | None:
        position = bisect_right(walls, wall) - 1 if wall is not None else -1
        return steps[position][1] if position >= 0 else None
    return at


def iso(wall: float | None) -> str | None:
    return None if wall is None else datetime.fromtimestamp(wall, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def describe(call: ToolCall, first: int) -> dict:
    """One call as a reviewer reads it: keys and typed text of an input, else the arguments."""
    if call.tool == 'computer_input':
        parts = []
        for action in call.arguments.get('actions') or ():
            kind = action.get('type') if isinstance(action, dict) else None
            parts.append('+'.join([*action.get('modifiers', ()), str(action.get('key'))]) if kind == 'key'
                else json.dumps(action.get('text'), ensure_ascii=False) if kind == 'text' else str(kind))
        did: object = ' '.join(parts)
    else:
        did = call.arguments
    return dict(request=None if call.decision is None else call.decision - first + 1, tool=call.tool, did=did,
        typed=typed_text(call), frame=frame_source(call), error=call.error or call.refused or not call.finished)


def read_runs(runs: list[Path], clock, before: int, after: int) -> dict:
    """The reads of every selected run, in order, with the counts a record needs."""
    reads, authors, tools, delivered = [], {}, Counter(), {}
    traces = calls = handoffs = carrying = responses = with_text = with_reasoning = 0
    held_at: dict[tuple[str, str], list[tuple[int | None, set[str]]]] = {}
    for run in runs:
        entry = run_archive_entry(run)
        host, names = {}, {}
        for directory in sorted(p for p in (run / 'actors').iterdir() if (p / 'host.jsonl').is_file()):
            actor, events = read_host(directory / 'host.jsonl', directory.name, entry)
            host[actor], names[actor] = events, directory.name
            authors[actor] = f'{run.name}/{directory.name}'
            for event in events:  # what the model wrote besides its tool calls: counted by the host, never kept
                progress = event.fields.get('response_progress') if event.type == 'response-complete' else None
                if isinstance(progress, dict):
                    responses += 1
                    with_text += bool(progress.get('content_bytes'))
                    with_reasoning += bool(progress.get('reasoning_bytes'))
        carry = read_carry(run)
        facts = host_facts(tuple(host), host)
        traces += len(host)
        calls += len(facts.calls)
        handoffs += len(carry)
        carrying += sum(bool(ids) for ids in carry.values())
        tools.update(call.tool for call in facts.calls if call.tool in MEMORY_TOOLS)
        order = list(host)
        for giver, taker in zip(order, order[1:]):
            held_at.setdefault((run.name, names[taker]), []).append((None, set(carry.get(giver, ()))))
        for call in facts.calls:  # what each actor wrote itself, and when
            value = call.result if isinstance(call.result, dict) else {}
            if call.tool == 'player_memory_append' and call.finished and not call.error and isinstance(value.get('id'), str):
                held_at.setdefault((run.name, names[call.actor]), []).append((call.index, {value['id']}))
        finishes = {event.actor: event.fields for event in facts.finishes}
        for read in memory_reads(facts, carry):
            call = read.call
            first = (call.decision or 0) - (read.request or 0) + 1
            held_at.setdefault((run.name, names[call.actor]), []).append((call.index, set(record_ids(call))))
            records = []
            for record in read.records:
                created = record.get('created_wall')
                age = call.wall - created if type(created) in (int, float) and call.wall is not None else None
                written, now = clock(created), clock(call.wall)
                records.append(dict(id=record['id'], kind=record.get('kind'), author=authors.get(record.get('actor_id'),
                    record.get('actor_id')), created=iso(created), age_seconds=None if age is None else round(age),
                    age_game_seconds=None if written is None or now is None else now - written,
                    held=record['id'] in read.held, sources=len(record.get('sources') or ()),
                    supports=record.get('supports'), text=record.get('text'), data=record.get('data')))
                delivered.setdefault(record['id'], []).append(dict(run=run.name, actor=names[call.actor],
                    request=read.request, age_seconds=records[-1]['age_seconds'],
                    age_game_seconds=records[-1]['age_game_seconds']))
            finish = finishes.get(call.actor)
            reads.append(dict(run=run.name, actor=names[call.actor], successor=order.index(call.actor) > 0,
                tool=call.tool, arguments=call.arguments, request=read.request, actor_requests=read.actor_requests,
                wall=iso(call.wall), game_time=clock(call.wall), records=records,
                references=[dict(request=None if r.call.decision is None else r.call.decision - first + 1,
                    record=r.record_id, how=r.how, detail=r.detail, repeated=r.repeated) for r in read.references],
                before=[describe(c, first) for c in read.before[-before:]] if before else [],
                after=[describe(c, first) for c in read.after[:after]], calls_after=len(read.after),
                finish=None if finish is None else dict(disposition=finish.get('disposition'), report=finish.get('report'))))
    returned = [record for read in reads for record in read['records']]
    return dict(runs=len(runs), traces=traces, tool_calls=calls, memory_calls=dict(sorted(tools.items())),
        responses=responses, responses_with_text=with_text, responses_with_reasoning=with_reasoning,
        reads_by_first_actors=sum(not read['successor'] for read in reads),
        reads_by_successors=sum(read['successor'] for read in reads),
        handoff_contexts=handoffs, handoff_contexts_carrying_records=carrying, reads=reads,
        records_returned=len(returned), distinct_records_returned=len({r['id'] for r in returned}),
        returned_already_held=sum(r['held'] for r in returned), first_read=delivered, _held=held_at, _authors=authors)


def store_rows(path: Path, result: dict) -> list[dict]:
    """Every stored record with how it reached a later actor: returned by a read, carried by a handoff, or neither."""
    carried = {record for moments in result['_held'].values() for index, ids in moments if index is None for record in ids}
    rows = []
    for identity, record in read_memory(path).records.items():
        reads = result['first_read'].get(identity, [])
        rows.append(dict(id=identity, kind=record.get('kind'), author=result['_authors'].get(record.get('actor_id'),
            record.get('actor_id')), created=iso(record.get('created_wall')), returned_by_reads=len(reads),
            first_read=reads[0] if reads else None, carried_by_handoff=identity in carried))
    return rows


def rediscoveries(probes: Path, runs: list[Path], result: dict, store: Path | None) -> list[dict]:
    """Each rediscovery of a fact that names a stored record, with whether its actor had been given the record.

    `given` lists how the actor held the record before the rediscovered frame: `handoff` (its starting context
    carried it) or `own write or read`. `existed` says the record was written before that frame; it needs the store
    and is None without it, or when no call of the actor returned the frame."""
    created = {identity: record.get('created_wall') for identity, record in read_memory(store).records.items()} if store else {}
    facts, rows = {}, []
    frames: dict[tuple[str, str], dict[str, ToolCall]] = {}
    for run in runs:
        entry = run_archive_entry(run)
        for directory in sorted(p for p in (run / 'actors').iterdir() if (p / 'host.jsonl').is_file()):
            actor, events = read_host(directory / 'host.jsonl', directory.name, entry)
            calls = host_facts((actor,), {actor: events}).calls
            frames[(run.name, directory.name)] = {source: c for c in calls if (source := frame_source(c))}
    for (run, actor) in frames:
        path = probes / f'{run}-{actor}.jsonl'
        lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
        facts.update({line['id']: line for line in lines if line.get('type') == 'fact'})
        for line in lines:
            fact = facts.get(line.get('fact'), {})
            if line.get('type') != 'event' or line.get('event') != 'rediscovered' or not fact.get('stored'):
                continue
            call = frames[(run, actor)].get(line.get('frame'))
            given = sorted({'handoff' if index is None else 'own write or read'
                for index, ids in result['_held'].get((run, actor), ())
                if any(identity.startswith(fact['stored']) for identity in ids)
                and (index is None or call is None or index < call.index)})
            written = next((wall for identity, wall in created.items() if identity.startswith(fact['stored'])), None)
            rows.append(dict(run=run, actor=actor, first_actor=actor == min(a for r, a in frames if r == run),
                fact=line['fact'], category=fact.get('category'), record=fact['stored'], frame=line.get('frame'),
                statement=fact.get('statement'), note=line.get('note'), given=given,
                existed=None if written is None or call is None or call.wall is None else written < call.wall))
    return rows


def render(result: dict) -> str:
    lines = [f"{result['runs']} runs, {result['traces']} traces, {result['tool_calls']} tool calls; memory calls "
        f"{result['memory_calls']}; {result['handoff_contexts_carrying_records']} of {result['handoff_contexts']} "
        f"handoff contexts carried records", f"{result['responses']} responses: {result['responses_with_text']} "
        f"with text besides tool calls, {result['responses_with_reasoning']} with reasoning the trace counts but "
        f"does not keep", f"{len(result['reads'])} reads ({result['reads_by_first_actors']} by the "
        f"{result['runs']} first actors, {result['reads_by_successors']} by the {result['traces'] - result['runs']} "
        f"successors) returned {result['records_returned']} "
        f"records ({result['distinct_records_returned']} distinct), {result['returned_already_held']} already held"]
    for read in result['reads']:
        lines.append(f"\n== {read['run']}/{read['actor']} request {read['request']} of {read['actor_requests']} "
            f"{read['wall']} game time {read['game_time']} {read['tool']} {json.dumps(read['arguments'])} "
            f"successor={read['successor']} calls after={read['calls_after']}")
        for record in read['records']:
            lines.append(f"  record {record['id'][:6]} {record['kind']} by {record['author']} age {record['age_seconds']} s"
                f" (game {record['age_game_seconds']} s) held={record['held']}: {record['text']}"
                f" DATA {json.dumps(record['data'], ensure_ascii=False)}")
        for ref in read['references']:
            lines.append(f"  reference request {ref['request']} {ref['how']} {ref['detail']!r} -> {ref['record'][:6]}"
                f"{' (repeated)' if ref['repeated'] else ''}")
        for label in ('before', 'after'):
            for call in read[label]:
                did = call['did'] if isinstance(call['did'], str) else json.dumps(call['did'], ensure_ascii=False)
                lines.append(f"  {label} {call['request']} {call['tool']} {did} frame={call['frame']}"
                    f"{' ERROR' if call['error'] else ''}")
        if read['finish']:
            lines.append(f"  finish {read['finish']['disposition']}: {read['finish']['report']}")
    for row in result.get('store', ()):
        lines.append(f"store {row['id'][:6]} {row['kind']} by {row['author']} {row['created']} returned by "
            f"{row['returned_by_reads']} reads, first {row['first_read']}, carried by a handoff={row['carried_by_handoff']}")
    if 'rediscoveries' in result:
        rows = result['rediscoveries']
        existed = [row for row in rows if row['existed']]
        missed = [row for row in existed if not row['given']]
        lines.append(f"{len(rows)} rediscoveries of facts with a stored record; in {len(existed)} the record had "
            f"been written; in {len(missed)} of those the actor had not been given it "
            f"({sum(row['first_actor'] for row in missed)} by the first actor of an admission; by category "
            f"{dict(sorted(Counter(row['category'] for row in missed).items()))}; by record "
            f"{dict(sorted(Counter(row['record'] for row in missed).items()))})")
        lines.extend(f"rediscovery {row['run']}/{row['actor']} {row['fact']} {row['category']} record {row['record']} "
            f"existed={row['existed']} given={row['given'] or 'no'} frame={row['frame']}: {row['note']}" for row in rows)
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--records', type=Path, help='evaluation records root, for game time')
    parser.add_argument('--store', type=Path, help='the lineage player-memory/2 store')
    parser.add_argument('--probes', type=Path, help='probe annotations of the lineage')
    parser.add_argument('--before', type=int, default=8, help='calls listed before each read')
    parser.add_argument('--after', type=int, default=40, help='calls listed after each read')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    runs = run_dirs(args.runs)
    result = read_runs(runs, game_clock(args.records), args.before, args.after)
    if args.store:
        result['store'] = store_rows(args.store, result)
    if args.probes:
        result['rediscoveries'] = rediscoveries(args.probes, runs, result, args.store)
    result = {key: value for key, value in result.items() if not key.startswith('_')}
    print(json.dumps(result, indent=1, ensure_ascii=False) if args.json else render(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
