"""The whole live-curator arrangement at zero cost: guardian, writer, reader, runner and stand-in curator (#851).

A script run by hand, not a collected test. No game, no provider, no spend:

    python -m tests.live_curator_stand_in_run --output .runtime/live-curator-stand-in-runs/NAME

It runs the real guardian (`tools.campaign_supervision.run_supervised`, its `supervise` loop, its
teardown and terminal record, and its `--curator-runner` path: the read lock, the runner launched
outside supervision and its termination), the real runner process (`tools.curator_host.live_runner`,
which stages snapshots through `harness.trace.snapshot.stage` and runs windowed sessions through the
sandbox, the Node curator host, the proxy and the gate) over a fresh knowledge repository of its own.
The real gateway, viewer and wake helper run as the guardian starts them; none needs the game.

Substituted, and named as such in the report:

- **the custodian's process.** The guardian's `popen` is wrapped so that the custodian's argv starts
  this module's `writer` instead (`python -m tests.live_curator_stand_in_run writer ...`). It writes
  `started.json`, `ready.json` and a `campaign-receipt/7` receipt as the custodian does, appends finished
  operations to a real `SessionStore` at a set pace through `tests.curator_trace._Writer`, with a
  handoff between two actors, starts and reaps a stand-in native process (`/bin/sleep`) so that the
  receipt's native fields are true of a real process, and closes its store through the custodian's
  own `tools.campaign_run.close_store`. In the driver's place it runs the driver's own
  `tools.campaign_player.LiveKnowledge` at each step and between actors, with an application that only
  records which version it was told to serve;
- **the player host while the run goes on.** No host runs beside the writer. After the run, the real
  host (`tools/player_host`) replays one actor's finished update list with a scripted provider and the
  real application over MCP (`tools/player_host/test/live-update-replay.mjs`);
- **package preflight** (`tools.campaign_supervision.preflight`), since there is no frozen package,
  clean tree or game: it returns a fixed profile and a route naming a dummy credential variable;
- **the route credential**: a dummy value in that dummy variable;
- **the provider**: `tests.curator_stand_in.StandIn` on loopback, with one change made here, in this
  process: each admission submission's fact gets an identity of its own (from the first frame it
  cites) and the `control` type is added only while the base version lacks it. The stand-in as it is
  submits fact `f1` and type `control` every time, the gate rejects the second window as a duplicate,
  and two consecutive rejections stop the runner by its own rule, which would end the measurement
  after the third window.

The writer is also run alone once, with no guardian and no runner, for the pace comparison. All
outputs go under the named output directory (refused if it exists), inside the main checkout's
`.runtime/`, except the runner's knowledge repository: the guardian starts the runner without
`--runtime-root`, so its runtime root is this code checkout's `.runtime/`, and the repository is
made fresh there and copied into the output directory at the end. The viewer the guardian starts
also writes its evaluations under this code checkout's `.runtime/evaluations/<session>`.

Every measure is read from the files a live run writes: the runner's `status.json` (sampled while
it runs), `examined.jsonl`, `versions.jsonl`, `polls.jsonl` and session summaries and proxy
ledgers, the guardian's `watch-terminal.json`, the closing marker and the sealed store. The writer's
own record (busy errors and step times) is the one source a live run does not have. The script writes
`report.json` and `summary.txt` and exits 1 when a required measure fails.

Live delivery of a newer knowledge version (#838) is checked end to end from the same files: the
manifest sets `live_knowledge_updates` over an empty frozen file; the real runner leaves each version
it confirms in `curator-runner/delivered/`; the driver's code lists an adopted version in the running
actor's `knowledge-updates.jsonl` and starts the next actor from the latest; and the host replay
delivers the newest listed version to its next request.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUN_NAME = 'stand-in-admission'
DUMMY_KEY_VARIABLE = 'STAND_IN_RUN_DUMMY_KEY'
DUMMY_KEY = 'synthetic-not-a-provider-key'
WALL_SECONDS = 900  # the profile's custody bound; the run ends well inside it
SAMPLE_SECONDS = .05  # how often the status file is read while the run goes on


def main_checkout() -> Path:
    common = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    return Path(common).parent.resolve()


def source_commit() -> str:
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


# ------------------------------------------------------------------------------------------- the writer
def writer_main(args: argparse.Namespace) -> int:
    """The custodian's substitute: its markers, a growing store at a set pace, its close-out and receipt."""
    from harness.computer.launch import close_group
    from tests.curator_trace import _Writer
    from tools.campaign_package import DELIVERED_DIRECTORY, RUNNER_DIRECTORY
    from tools.campaign_player import UPDATES_FILE, LiveKnowledge, write_new

    run = Path(args.run).resolve(strict=True)
    started_monotonic, started_wall = time.monotonic(), time.time()
    write_new(run/'started.json', dict(schema='computer-start/1', session=args.session, started_wall=started_wall,
                                       deadline_monotonic=started_monotonic + args.wall_seconds))
    native = subprocess.Popen(['/bin/sleep', '3600'], start_new_session=True,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    writer = _Writer(run, args.session)  # the real SessionStore, write-ahead log, quarter-second timeout
    write_new(run/'ready.json', dict(schema='computer-ready/1', session=args.session, pid=native.pid,
                                     viewer_url=f'http://127.0.0.1:{args.port}/', ready_wall=time.time()))
    steps, error = [], None
    first = time.monotonic()
    count = 0
    # The driver's part of live delivery (#838), with the driver's own code: at each step and between actors it
    # looks where the runner leaves versions, lists an adopted one for the running actor and starts the next
    # actor from the latest. The application's part is recorded: which version it was told to serve, and when.
    served, started = [], {}

    class Application:
        def set_knowledge(self, knowledge):
            served.append(dict(version=knowledge.value['version'], wall=time.time()))

    live = LiveKnowledge(run/RUNNER_DIRECTORY/DELIVERED_DIRECTORY, run/'delivered-knowledge.json', session=args.session)
    try:
        for actor in range(args.actors):
            writer.new_actor()
            directory = writer.actor['directory']
            live.poll(Application())  # between actors: adopted for this actor's frozen file
            write_new(directory/UPDATES_FILE, '', text=True)
            data = live.begin(directory)
            (directory/'delivered-knowledge.json').write_bytes(data)
            started[directory.name] = dict(version=json.loads(data)['version'], wall=time.time())
            for _ in range(args.steps):
                due = first + count * args.pace
                pause = due - time.monotonic()
                if pause > 0:
                    time.sleep(pause)
                count += 1
                began_wall, began = time.time(), time.monotonic()
                answer = writer.step(hint=count % 3 == 0, split=count % 5 == 0)
                steps.append(dict(index=count, actor=writer.actor['directory'].name, operation=answer['operation_id'],
                                  began_wall=began_wall, seconds=time.monotonic() - began, late=max(0., -pause)))
                live.poll(Application())
            live.end()
            if actor < args.actors - 1:
                writer.handoff()
    except Exception as exc:  # recorded; the close-out still runs, as the custodian's does
        error = f'{type(exc).__name__}: {exc}'
    # Close-out in the custodian's order: input revoked (there is none to revoke), native cleanup,
    # then the store's close through close_store, then the receipt.
    cleanup = close_group(native, native=True)
    closed = writer.close()
    ended_wall = time.time()
    native_record = {k: cleanup[k] for k in ('pid', 'pgid', 'returncode', 'process_absent', 'group_absent')}
    absent = cleanup['process_absent'] and cleanup['group_absent']
    receipt = dict(schema='campaign-receipt/7', session=args.session, source_commit=args.commit,
                   started_wall=started_wall, ended_wall=ended_wall, elapsed_seconds=time.monotonic() - started_monotonic,
                   outcome='synthetic-writer', substitute='tests.live_curator_stand_in_run writer: no game and no player host',
                   native_absence_verified=absent, deciding_hosts_quiescent=True, input_authority_revoked=True,
                   normal_save_claimed_by_harness=False,
                   cleanup=dict(schema='computer-cleanup/1', session=args.session, native_absence_verified=absent,
                                normal_native_exit_zero=cleanup['returncode'] == 0, native=native_record))
    write_new(run/'receipt.json', receipt)
    Path(args.record).write_text(json.dumps(dict(
        schema='stand-in-writer-record/2', pace_seconds=args.pace, steps_per_actor=args.steps, actors=args.actors,
        steps=steps, busy=writer.busy, error=error, close=closed, native=cleanup,
        live=dict(served=served, started=started, refused=sorted(live.refused))), indent=1) + '\n')
    return 0 if error is None and not closed['errors'] else 1


# ----------------------------------------------------------------------------------- the stand-in curator
def distinct_facts():
    """Give each stand-in window a distinct fact identity."""
    from tests import curator_stand_in

    original = curator_stand_in.script
    rewritten = []

    def script(messages, attack=None, *, unfiled=False):
        calls = original(messages, attack, unfiled=unfiled)
        for index, (name, arguments) in enumerate(calls or ()):
            if name != 'write_file' or arguments.get('path') != 'submissions/stand-in/submission.json':
                continue
            submission = json.loads(arguments['content'])
            facts = [change['fact'] for change in submission['changes'] if change['op'] == 'add_fact']
            for fact in facts:
                if fact['citations']:
                    fact['id'] = 'f-' + fact['citations'][0].rsplit('-', 1)[-1]
            rewritten.append(dict(base_version=submission['base_version'], facts=[fact['id'] for fact in facts]))
            calls[index] = (name, dict(arguments, content=json.dumps(submission)))
        return calls

    curator_stand_in.script = script
    return rewritten


# ------------------------------------------------------------------------------------------- the run
def write_manifest(run: Path, session: str, commit: str) -> None:
    """The run package's manifest under the current contract, as the snapshot, the projection and the runner's
    delivery read it, and the package's frozen knowledge: the empty file, so the first version the runner leaves
    is the first knowledge an actor holds."""
    from harness.player.knowledge import empty

    run.mkdir(parents=True)
    (run/'manifest.json').write_text(json.dumps(dict(schema='campaign-run/12', session=session, source_commit=commit,
                                                     labels=dict(world=None, lineage=None, admission=None),
                                                     live_knowledge_updates=True,
                                                     substitute='no frozen package: tests.live_curator_stand_in_run')))
    (run/'delivered-knowledge.json').write_text(json.dumps(empty()) + '\n')


def writer_argv(run: Path, record: Path, session: str, commit: str, port: int, args: argparse.Namespace) -> list[str]:
    return [sys.executable, '-m', 'tests.live_curator_stand_in_run', 'writer', '--run', str(run), '--record', str(record),
            '--session', session, '--commit', commit, '--port', str(port), '--wall-seconds', str(WALL_SECONDS),
            '--pace', str(args.pace), '--steps', str(args.steps), '--actors', str(args.actors)]


class Sampler(threading.Thread):
    """Reads the runner's status file while the run goes on and keeps every distinct version of it."""

    def __init__(self, status: Path, out: Path):
        super().__init__(name='status-sampler', daemon=True)
        self.status, self.out, self.stop, self.samples = status, out, threading.Event(), []

    def run(self):
        last = None
        with self.out.open('a') as stream:
            while True:
                stopping = self.stop.is_set()
                try:
                    value = json.loads(self.status.read_text())
                except (OSError, ValueError):
                    value = None
                if value is not None and value.get('updated_wall') != last:
                    last = value.get('updated_wall')
                    self.samples.append(value)
                    stream.write(json.dumps(value, sort_keys=True) + '\n')
                    stream.flush()
                if stopping:
                    return
                time.sleep(SAMPLE_SECONDS)


def live_run(out: Path, knowledge_root: Path, args: argparse.Namespace) -> dict:
    """The guardian with the runner, the writer in the custodian's place and the stand-in upstream."""
    from tests.curator_stand_in import StandIn
    from tools import campaign_supervision as guard
    from tools.curator_host import live_runner, shadow

    session, commit = uuid.uuid4().hex, source_commit()
    run = out/'run'/RUN_NAME
    write_manifest(run, session, commit)
    port = guard.free_loopback_port()  # the custodian's own port: nothing listens there in this run
    profile = dict(session=session, source_commit=commit, wall_seconds=WALL_SECONDS, port=port)
    substitutions = []
    rewritten = distinct_facts()
    with StandIn() as stand_in:
        config = out/'runner-config.json'
        config.write_text(json.dumps(dict(
            schema='curator-runner-config/1', knowledge_root=str(knowledge_root), arm=args.arm, cap_usd='1.00',
            session_cap_usd='0.25', upstream=stand_in.url,
            host=dict(max_requests=10, max_output_tokens=4096, wall_seconds=120),
            **({} if args.poll_seconds is None else dict(poll_seconds=args.poll_seconds))), indent=1) + '\n')
        # The only upstream is the loopback stand-in, and the runner presents only the fixed test key.
        checked = live_runner.read_config(config, ROOT/'.runtime')
        if (checked['upstream'] != stand_in.url or not re.fullmatch(r'http://127\.0\.0\.1:[0-9]+', checked['upstream'])
                or shadow.route_key(checked['upstream'], ROOT/'.runtime') != shadow.LOOPBACK_KEY):
            raise SystemExit('refused: the runner configuration names an upstream other than the loopback stand-in')
        try:
            bad = dict(json.loads(config.read_text()), upstream='https://example.com')
            (out/'.refusal-probe.json').write_text(json.dumps(bad))
            live_runner.read_config(out/'.refusal-probe.json', ROOT/'.runtime')
            raise SystemExit('refused: the runner configuration accepted a non-loopback, non-OpenRouter upstream')
        except live_runner.ConfigError:
            pass
        finally:
            (out/'.refusal-probe.json').unlink(missing_ok=True)

        def popen(argv, **kwargs):
            if 'tools.campaign_run' in argv:
                replaced = writer_argv(run, out/'writer-live.json', session, commit, port, args)
                substitutions.append(dict(role='custodian', guardian_argv=list(argv), started_argv=replaced))
                argv = replaced
            return subprocess.Popen(argv, **kwargs)

        guard.preflight = lambda directory: (profile, dict(api_key_env=DUMMY_KEY_VARIABLE), {})
        os.environ[DUMMY_KEY_VARIABLE] = DUMMY_KEY
        sampler = Sampler(run/guard.RUNNER_DIRECTORY/'status.json', out/'status-samples.jsonl')
        sampler.start()
        began = time.time()
        try:
            terminal = guard.run_supervised(run, popen=popen, curator_runner=config)
        finally:
            sampler.stop.set()
            sampler.join()
        requests = [dict(path=r['path'], model=r['body'].get('model')) for r in stand_in.requests]
    (out/'stand-in-requests.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in requests))
    return dict(run=run, session=session, commit=commit, terminal=terminal, substitutions=substitutions,
                requests=requests, rewritten=rewritten, samples=sampler.samples, began_wall=began, ended_wall=time.time(),
                config=json.loads(config.read_text()))


def writer_alone(out: Path, args: argparse.Namespace) -> Path:
    """The writer once more, with no guardian and no runner (so no read lock and no wait at close)."""
    session, commit = uuid.uuid4().hex, source_commit()
    run = out/'writer-alone'/RUN_NAME
    write_manifest(run, session, commit)
    record = out/'writer-alone.json'
    with (run/'writer-stdout.txt').open('xb') as stdout, (run/'writer-stderr.txt').open('xb') as stderr:
        code = subprocess.run(writer_argv(run, record, session, commit, 9, args), cwd=ROOT, stdout=stdout, stderr=stderr,
                              env=dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8')).returncode
    if code != 0:
        raise SystemExit(f'the writer alone exited with {code}; see {run}')
    return record


# ------------------------------------------------------------------------------------------- the measures
def lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []


def spread(values: list[float]) -> dict:
    if not values:
        return dict(count=0)
    ordered = sorted(values)
    return dict(count=len(values), min=round(ordered[0], 4), median=round(statistics.median(ordered), 4),
                p95=round(ordered[min(len(ordered) - 1, int(.95 * len(ordered)))], 4), max=round(ordered[-1], 4))


def sealed_steps(run: Path) -> tuple[dict, dict, dict]:
    """From the sealed store: each actor directory's operations in step order, each operation's created
    wall time, and each operation's frame `received_wall` (where it has a frame)."""
    from harness.trace.stores import sealed

    actors = {}
    for frozen in sorted((run/'actors').glob('*/frozen.json')):
        actors[json.loads(frozen.read_text())['actor_id']] = frozen.parent.name
    with sealed(run/'session.sqlite3') as db:
        rows = db.execute('SELECT id, actor, created_wall FROM operations ORDER BY created_wall, id').fetchall()
        frames = dict(db.execute('SELECT n.operation, json_extract(s.metadata, "$.received_wall") FROM native_intents n '
                                 'JOIN sources s ON s.id = n.source').fetchall())
    order: dict[str, list[str]] = {}
    created = {}
    for operation, actor, wall in rows:
        order.setdefault(actors[actor], []).append(operation)
        created[operation] = wall
    return order, created, frames


def pace(record: dict) -> dict:
    steps = record['steps']
    walls = [s['began_wall'] for s in steps]
    per_minute = (len(walls) - 1) / (walls[-1] - walls[0]) * 60 if len(walls) > 1 else None
    return dict(set_pace_seconds=record['pace_seconds'], steps=len(steps), operations_per_minute=round(per_minute, 2),
                busy=record['busy'], error=record['error'], step_seconds=spread([s['seconds'] for s in steps]),
                late_seconds=spread([s['late'] for s in steps]), close=record['close'])


def measure(out: Path, live: dict, alone_record: Path) -> dict:
    from harness.curator.knowledge import Repository
    from harness.trace.snapshot import TRANSACTION_BOUND_SECONDS
    from harness.trace.stores import READ_HOLD_BOUND_SECONDS, SealedStoreError, sealed
    from tests.curator_stand_in import ROUTE
    from tools.curator_host import shadow

    run = live['run']
    runner_dir = run/'curator-runner'
    terminal = json.loads((run/'watch-terminal.json').read_text())
    status = json.loads((runner_dir/'status.json').read_text())
    examined_rows = lines(runner_dir/'examined.jsonl')
    versions = lines(runner_dir/'versions.jsonl')
    polls = lines(runner_dir/'polls.jsonl')
    marker = json.loads((run/'store-closing.json').read_text()) if (run/'store-closing.json').is_file() else None
    writer_live = json.loads((out/'writer-live.json').read_text())
    writer_solo = json.loads(alone_record.read_text())
    checks, report = {}, {}

    # The guardian, as its own exit status judges it.
    custodian = terminal['cleanup'].get('custodian', {})
    checks['guardian_custodian_terminal'] = (terminal['reason'] == 'custodian_terminal' and terminal['terminal_coverage_verified']
                                             and terminal['cleanup_verified'] and terminal['manifest_unchanged']
                                             and custodian.get('returncode') == 0)
    report['guardian'] = {k: terminal.get(k) for k in ('reason', 'terminal_coverage_verified', 'cleanup_verified',
                                                       'manifest_unchanged', 'error', 'signal')}
    report['guardian']['children'] = {name: dict(supervised=child.get('supervised', True), launch_error=child.get('launch_error'))
                                      for name, child in terminal['children'].items()}

    # The sealed store and the step numbering.
    try:
        order, created, frames = sealed_steps(run)
        wal = run/'session.sqlite3-wal'
        with sealed(run/'session.sqlite3') as db:
            operations = db.execute('SELECT count(*) FROM operations').fetchone()[0]
        report['sealed_store'] = dict(accepted=True, operations=operations, wal_bytes=wal.stat().st_size if wal.exists() else 0,
                                      steps_per_actor={a: len(o) for a, o in order.items()})
        checks['store_sealed_with_empty_log'] = report['sealed_store']['wal_bytes'] == 0
    except (SealedStoreError, OSError) as exc:
        order, created, frames = {}, {}, {}
        report['sealed_store'] = dict(accepted=False, error=f'{type(exc).__name__}: {exc}')
        checks['store_sealed_with_empty_log'] = False

    # Examined windows, in order.
    ends = {row['label']: row for row in examined_rows if row['event'] == 'end'}
    starts = [row for row in examined_rows if row['event'] == 'start']
    windows = []
    for row in starts:
        end = ends.get(row['label'])
        window = row['window']
        actor_ops = order.get(window['actor'], [])
        numbering = (len(actor_ops) >= window['last'] and actor_ops[window['first'] - 1] == row['first_operation']
                     and actor_ops[window['last'] - 1] == row['last_operation'])
        windows.append(dict(label=row['label'], actor=window['actor'], first=window['first'], last=window['last'],
                            steps=window['last'] - window['first'] + 1, outcome=end and end['outcome'],
                            advanced=bool(end and end['advanced']), verdicts=end and end['verdicts'],
                            started_wall=row['started_wall'], ended_wall=end and end['ended_wall'],
                            session_seconds=end and round(end['ended_wall'] - row['started_wall'], 3),
                            numbering_equals_sealed=numbering, summary=end and end['details'].get('summary')))
    report['windows'] = windows
    in_order = True
    reached: dict[str, int] = {}
    actor_names = list(order)
    previous_actor = -1
    for w in windows:
        place = actor_names.index(w['actor']) if w['actor'] in actor_names else -1
        if w['first'] != reached.get(w['actor'], 0) + 1 or place < previous_actor:
            in_order = False
        if w['advanced']:
            reached[w['actor']] = w['last']
        previous_actor = place
    first_actor = actor_names[0] if actor_names else None
    tail = [w for w in windows if w['actor'] == first_actor and w['last'] == len(order.get(first_actor, []))
            and w['first'] > 1 and w['advanced']]
    advanced = [w for w in windows if w['advanced']]
    checks['two_windows_examined_in_order'] = len(advanced) >= 2 and in_order
    checks['handoff_tail_examined'] = bool(tail)
    checks['every_session_accepted'] = bool(windows) and all(w['outcome'] == 'accepted' for w in windows)
    checks['step_numbering_equals_sealed'] = bool(windows) and all(w['numbering_equals_sealed'] for w in windows)

    # The status file at each session's start and end, and over time.
    samples = live['samples']
    keep = ('state', 'position', 'covered_prefix', 'lag', 'stamp_distance', 'backlog', 'cursor', 'last_confirmed',
            'failures', 'updated_wall')
    at = []
    for w in windows:
        start = next((s for s in samples if s['state'] == 'in-session' and (s.get('current') or {}).get('label') == w['label']), None)
        end = next((s for s in samples if any(e['label'] == w['label'] and e['outcome'] != 'in-session'
                                              for e in s['examined'])), None)
        at.append(dict(label=w['label'], start={k: start.get(k) for k in keep} if start else None,
                       end={k: end.get(k) for k in keep} if end else None))
    report['status_at_sessions'] = at
    checks['status_seen_at_each_session_start_and_end'] = bool(at) and all(a['start'] and a['end'] for a in at)
    report['over_time'] = [dict(wall=round(s['updated_wall'] - live['began_wall'], 2), state=s['state'],
                                position=(s['position'] or {}).get('ordinal') if isinstance(s['position'], dict) else s['position'],
                                lag=s['lag'], backlog=s['backlog'],
                                covered=((s['covered_prefix'] or {}).get('end') or {}).get('ordinal'))
                           for s in samples]
    report['final_status'] = {k: status.get(k) for k in ('state', 'stop_reason', 'position', 'covered_prefix', 'lag',
                                                         'stamp_distance', 'backlog', 'unexamined', 'unconfirmed',
                                                         'failures', 'last_confirmed', 'look_error',
                                                         'as_of', 'after_last_read')}
    # The runner cannot know steps finished after its last read; its final status must say so.
    checks['final_status_says_what_it_is_as_of'] = (isinstance(status.get('as_of'), dict)
                                                     and status.get('after_last_read') == 'unknown')
    checks['every_publication_confirmed'] = status.get('unconfirmed') == []
    # The runner's own `unexamined` and `lag` count only what its last snapshot saw; against the
    # sealed store, the steps finished after that snapshot were never examined either.
    cursor = status.get('cursor') or {}
    left = [dict(actor=a, first=cursor.get(a, 0) + 1, last=len(o)) for a, o in order.items() if len(o) > cursor.get(a, 0)]
    finished = [op for o in order.values() for op in o]
    end_op = (((status.get('covered_prefix') or {}).get('end')) or {}).get('operation')
    report['left_at_end_against_sealed_store'] = dict(
        unexamined=left, unexamined_steps=sum(r['last'] - r['first'] + 1 for r in left),
        lag=len(finished) - finished.index(end_op) - 1 if end_op in finished else len(finished),
        finished_operations=len(finished),
        last_snapshot_ordinal=(status.get('position') or {}).get('ordinal') if isinstance(status.get('position'), dict) else None)

    # Snapshots: every read's hold, transaction and staging time, against the read bound.
    reads = [p for p in polls if p['outcome'] == 'read']
    failed = [p for p in polls if p['outcome'] in ('failed', 'over-bound')]
    report['snapshots'] = dict(
        polls=len(polls), reads=len(reads), failed_or_over_bound=len(failed),
        refusals=sorted({p['outcome'] for p in polls if p['outcome'].startswith('refused:')}),
        hold_seconds=spread([p['hold_seconds'] for p in reads]),
        transaction_seconds=spread([p['transaction_seconds'] for p in reads]),
        staging_seconds=spread([p['staging_seconds'] for p in reads]),
        hold_bound_seconds=READ_HOLD_BOUND_SECONDS, transaction_bound_seconds=TRANSACTION_BOUND_SECONDS,
        poll_seconds=status['settings']['poll_seconds'], positions=[(p.get('position') or {}).get('ordinal') for p in reads])
    # A rate over the gaps between poll starts: n polls span n-1 gaps.
    span = (polls[-1]['began_wall'] - polls[0]['began_wall']) / 60 if len(polls) > 1 else None
    report['snapshots']['reads_per_minute'] = round((len(polls) - 1) / span, 2) if span else None
    growing = [p for p in reads if marker is None or p['ended_wall'] < marker['closing_wall']]
    positions = [(p.get('position') or {}).get('ordinal') for p in growing]
    report['snapshots']['reads_while_growing'] = sum(1 for a, b in zip(positions, positions[1:]) if b > a)
    checks['snapshots_within_read_bound'] = bool(reads) and not failed and all(
        p['hold_seconds'] <= READ_HOLD_BOUND_SECONDS and p['transaction_seconds'] <= TRANSACTION_BOUND_SECONDS for p in reads)
    checks['snapshots_taken_while_store_grows'] = report['snapshots']['reads_while_growing'] >= 2

    # The writer: no busy error, its pace with and without the runner, and steps that overlapped a read.
    report['writer'] = dict(with_runner=pace(writer_live), alone=pace(writer_solo))
    intervals = [(p['began_wall'], p['ended_wall']) for p in reads]
    overlap = [s['seconds'] for s in writer_live['steps']
               if any(a <= s['began_wall'] + s['seconds'] and s['began_wall'] <= b for a, b in intervals)]
    report['writer']['steps_overlapping_a_snapshot'] = spread(overlap)
    checks['writer_never_busy'] = writer_live['busy'] == 0 and writer_solo['busy'] == 0 and not writer_live['error']
    checks['writer_close_clean'] = writer_live['close']['errors'] == {} and writer_live['close']['wal'] == 0

    # The closing marker.
    after = [p for p in reads if marker is not None and p['began_wall'] > marker['closing_wall']]
    report['closing'] = dict(marker=marker, close_waited_seconds=round(writer_live['close']['waited'], 4),
                             reads_begun_after_marker=len(after),
                             last_read_ended_before_marker=round(marker['closing_wall'] - reads[-1]['ended_wall'], 3)
                             if marker and reads else None,
                             refused_closing=sum(1 for p in polls if p['outcome'] == 'refused:closing'))
    checks['closing_marker_honoured'] = (marker is not None and marker['session'] == live['session'] and not after
                                         and writer_live['close']['waited'] <= READ_HOLD_BOUND_SECONDS + .1)

    # The runner at teardown.
    cleanup = terminal['cleanup'].get('curator_runner', {})
    guard_wall = terminal['started_wall'] + terminal['guard_terminal_monotonic'] - terminal['started_monotonic']
    report['runner_teardown'] = dict(
        cleanup=cleanup, final_state=status['state'], stop_reason=status['stop_reason'],
        status_written_after_guard_terminal_seconds=round(status['updated_wall'] - guard_wall, 3),
        guardian_teardown_seconds=round(terminal['ended_monotonic'] - terminal['guard_terminal_monotonic'], 3),
        stderr=(run/'curator-runner'/'stderr.txt').read_text()[-600:])
    checks['runner_ended_at_teardown'] = (cleanup.get('launched') is True and cleanup.get('process_absent') is True
                                          and cleanup.get('group_absent') is True and status['state'] == 'ended'
                                          and status['stop_reason'] in ('store-closing', 'interrupted'))

    # Time to publication, from each covered step's frame to the first sight of its version.
    confirmed = {v['version']: v for v in versions if not v['baseline']}
    publication = []
    for w in windows:
        version = next((v['version'] for v in (w['verdicts'] or ()) if v.get('status') == 'published'), None)
        entry = confirmed.get(version)
        if entry is None:
            continue
        received = [frames[op] for op in order.get(w['actor'], [])[w['first'] - 1:w['last']] if frames.get(op) is not None]
        publication.append(dict(label=w['label'], version=version, frames=len(received), steps=w['steps'],
                                first_seen_after_newest_frame=round(entry['first_present_ended_wall'] - max(received), 3)
                                if received else None,
                                first_seen_after_oldest_frame=round(entry['first_present_ended_wall'] - min(received), 3)
                                if received else None,
                                published_after_wall_lower_bound=entry['last_absent_began_wall']))
    report['time_to_publication_seconds'] = publication

    # Cost as the proxy counted it, and new facts per window.
    repo = Repository(Path(live['config']['knowledge_root']), shadow.GAME)
    costs = []
    for w in windows:
        if not w['summary'] or not Path(w['summary']).is_file():
            costs.append(dict(label=w['label'], summary=None))
            continue
        summary = json.loads(Path(w['summary']).read_text())
        version = next((v['version'] for v in (w['verdicts'] or ()) if v.get('status') == 'published'), None)
        new = None
        if version:
            before = {f['id'] for f in repo.facts(f'v{int(version[1:]) - 1}')}
            new = len([f for f in repo.facts(version) if f['id'] not in before])
        costs.append(dict(label=w['label'], cost_usd=summary['cost_usd'], steps=w['steps'],
                          per_examined_step_usd=str(Decimal(summary['cost_usd']) / w['steps']),
                          forwarded=summary['proxy'].get('forwarded'), refusals=summary['proxy'].get('refusals'),
                          usage_missing=summary['proxy'].get('usage_missing'), run_state=summary['run_state'],
                          session_state=summary.get('session_state'), wall_seconds=summary.get('wall_seconds'),
                          version=version, new_facts=new))
    total = sum((Decimal(c['cost_usd']) for c in costs if c.get('cost_usd') is not None), Decimal(0))
    steps = sum(c['steps'] for c in costs if c.get('cost_usd') is not None)
    report['cost'] = dict(note='the stand-in reports a nominal cost per request; it is not money', sessions=costs,
                          total_usd=str(total), per_session_usd=str(total / len(costs)) if costs else None,
                          per_examined_step_usd=str(total / steps) if steps else None)
    checks['cost_counted_for_every_session'] = bool(costs) and all(
        c.get('cost_usd') is not None and c['usage_missing'] == 0 for c in costs)
    forwarded = sum(c.get('forwarded') or 0 for c in costs)
    report['upstream'] = dict(stand_in=live['config']['upstream'], requests=len(live['requests']), proxy_forwarded=forwarded,
                              paths=sorted({r['path'] for r in live['requests']}), rewritten_submissions=live['rewritten'])
    checks['only_the_loopback_stand_in_was_called'] = (len(live['requests']) == forwarded
                                                       and report['upstream']['paths'] in ([ROUTE], []))
    report['new_facts_per_window'] = [dict(label=c['label'], version=c.get('version'), new_facts=c.get('new_facts'))
                                      for c in costs]
    report['knowledge'] = dict(published=repo.published(), root=live['config']['knowledge_root'])

    delivery_checks, report['live_delivery'] = live_delivery(out, run, repo, windows, writer_live, order)
    checks.update(delivery_checks)

    report['not_measured'] = {
        'whether a player uses a delivered update': 'no player model: the host replay answers from a script',
        'an update reaching a host while it plays': 'the host replays the actor\'s finished update list after the run; '
                                                    'tools/player_host/test/live-knowledge-update.test.mjs covers arrival between requests',
        'player pace beside sealed admissions of the same player': 'no player: the writer appends at a set pace',
        'decisions a minute and game time': 'no player and no game: there are no decisions and no game clock',
        'curator dollars beside the player': 'the stand-in reports a nominal cost; no provider and no player spend',
        'session length and output of a real curator': 'the stand-in answers at once with a scripted session',
        'facts later superseded or retired': 'no grooming runs and the stand-in never revises a fact',
        'whether the knowledge helps the player': 'the design does not measure it, and no player reads it here',
        'rate limits shared with the campaign': 'no provider account is used',
    }
    return dict(checks=checks, **report)


def live_delivery(out: Path, run: Path, repo, windows: list[dict], writer_live: dict, order: dict) -> tuple[dict, dict]:
    """Live delivery (#838) from the files the run left: the versions the real runner exported, what the driver's
    own code listed for each actor and told the application to serve, and what the real host delivers from one
    actor's list (replayed offline with a scripted provider: `tools/player_host/test/live-update-replay.mjs`)."""
    import hashlib

    from harness.curator.knowledge import _git
    from harness.player.knowledge import Knowledge, version_number
    from tools.campaign_player import COVERAGE_ENTRY_SCHEMA, UPDATE_ENTRY_SCHEMA
    from tools.curator_host.live_runner import COVERED_PREFIX_FILE, COVERED_PREFIX_SCHEMA, SESSION_ID_RE

    checks = {}
    number = lambda version: -1 if version is None else version_number(version)  # noqa: E731
    published = [v['version'] for w in windows for v in (w['verdicts'] or ()) if v.get('status') == 'published']
    root = _git(repo.path, 'rev-parse', 'v0^{commit}').decode().strip()
    exported = {}
    directory = run/'curator-runner'/'delivered'
    for path in sorted(directory.glob('v*.json'), key=lambda p: number(p.stem)) if directory.is_dir() else ():
        try:
            value = Knowledge.from_dict(json.loads(path.read_text())).value
            commit = _git(repo.path, 'rev-parse', f'{path.stem}^{{commit}}').decode().strip()
            valid = (value['version'], value['commit'], value['repository_id']) == (path.stem, commit, root)
            exported[path.stem] = dict(valid=valid, facts=len(value['facts']), articles=len(value['articles']),
                                       coverage=value['coverage'], sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        except Exception as exc:  # noqa: BLE001 - reported as an invalid export
            exported[path.stem] = dict(valid=False, error=f'{type(exc).__name__}: {exc}')
    recognized = {COVERED_PREFIX_FILE, *(f'{v}.json' for v in exported)}
    leftovers = sorted(p.name for p in directory.iterdir() if p.name not in recognized) if directory.is_dir() else []
    # The runner exports after the poll that confirmed a version, so the last one may be cut by the teardown.
    checks['runner_left_each_confirmed_version_for_the_driver'] = (
        bool(exported) and all(e['valid'] for e in exported.values()) and not leftovers
        and list(exported) in (published, published[:-1]))

    session = json.loads((run/'manifest.json').read_text())['session']
    endpoints = {}
    for window in windows:
        if not window['numbering_equals_sealed']:
            continue
        actor = window['actor']
        actor_id = json.loads((run/'actors'/actor/'actor.json').read_text())['actor_id']
        operation_id = order[actor][window['last']-1]
        if not all(SESSION_ID_RE.fullmatch(value) for value in (session, actor_id, operation_id)):
            continue
        for verdict in window['verdicts'] or ():
            version = verdict.get('version')
            if verdict.get('status') == 'published' and exported.get(version, {}).get('valid'):
                endpoints[version] = dict(schema=COVERED_PREFIX_SCHEMA, session=session, actor=actor, actor_id=actor_id,
                                          operation_id=operation_id, version=version, restored=False)
    try:
        prefix = json.loads((directory/COVERED_PREFIX_FILE).read_text())
    except (OSError, ValueError):
        prefix = None
    checks['runner_left_a_verified_covered_prefix'] = (
        isinstance(prefix, dict) and isinstance(prefix.get('version'), str) and prefix == endpoints.get(prefix['version']))

    record = writer_live['live']
    actors, listed_ok, coverage_ok = {}, True, True
    for actor in sorted(p for p in (run/'actors').iterdir() if p.is_dir()):
        frozen = json.loads((actor/'delivered-knowledge.json').read_text())['version']
        entries = lines(actor/'knowledge-updates.jsonl')
        previous = number(frozen)
        listed, coverage = [], []
        for entry in entries:
            if entry.get('schema') == COVERAGE_ENTRY_SCHEMA:
                version = entry.get('version')
                endpoint = endpoints.get(version) if isinstance(version, str) else None
                expected = None if endpoint is None else dict(schema=COVERAGE_ENTRY_SCHEMA, **{
                    key: endpoint[key] for key in ('session', 'actor_id', 'operation_id', 'version', 'restored')})
                coverage_ok = coverage_ok and expected == entry and number(version) <= previous
                coverage.append(entry)
                continue
            data = (actor/entry['file']).read_bytes() if (actor/entry['file']).is_file() else b''
            listed_ok = listed_ok and (
                entry['schema'] == UPDATE_ENTRY_SCHEMA and entry['file'] == f"knowledge/{entry['version']}.json"
                and hashlib.sha256(data).hexdigest() == entry['sha256'] == exported.get(entry['version'], {}).get('sha256')
                and number(entry['version']) > previous and entry['repository_id'] == root
                and entry['coverage'] == exported[entry['version']]['coverage'])
            previous = number(entry['version'])
            listed.append(entry['version'])
        actors[actor.name] = dict(frozen_version=frozen, listed=listed, coverage=coverage, started=record['started'].get(actor.name))
    checks['driver_listed_a_verified_version_for_a_running_actor'] = listed_ok and any(a['listed'] for a in actors.values())
    checks['driver_forwarded_verified_coverage_after_adoption'] = coverage_ok and any(a['coverage'] for a in actors.values())
    served = [s['version'] for s in record['served']]
    # Each actor starts from the version the application was last told to serve before it started (none: the package's).
    starts = True
    for name, actor in actors.items():
        before = [s['version'] for s in record['served'] if s['wall'] <= actor['started']['wall']]
        starts = starts and actor['frozen_version'] == actor['started']['version'] == (before[-1] if before else None)
    checks['each_actor_started_from_the_latest_adopted_version'] = starts
    # The stand-in application records only the driver's `set_knowledge` calls; the real application's tools
    # answering from the adopted version is tests/test_campaign_player.py's regression.
    checks['driver_handed_every_adopted_version_to_application'] = (
        [number(v) for v in served] == sorted({number(v) for v in served})
        and {v for a in actors.values() for v in a['listed']} <= set(served) and not record['refused'])

    # The host: the first actor that had a version listed, replayed through the real host.
    host = dict(replayed=None)
    chosen = next((name for name, actor in actors.items() if actor['listed']), None)
    if chosen is not None:
        replay = out/'host-delivery'
        (replay/'actors'/'001').mkdir(parents=True)
        shutil.copy(run/'actors'/chosen/'delivered-knowledge.json', replay/'delivered-knowledge.json')
        shutil.copy(run/'actors'/chosen/'knowledge-updates.jsonl', replay/'actors'/'001'/'knowledge-updates.jsonl')
        shutil.copytree(run/'actors'/chosen/'knowledge', replay/'actors'/'001'/'knowledge')
        done = subprocess.run(['node', str(ROOT/'tools'/'player_host'/'test'/'live-update-replay.mjs'), str(replay)],
                              cwd=ROOT, capture_output=True, text=True, timeout=180,
                              env=dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8',
                                       ENACTIVE_TEST_PYTHON=sys.executable))
        host = dict(replayed=chosen, returncode=done.returncode, stderr=done.stderr[-600:])
        if done.returncode == 0:
            host.update(json.loads(done.stdout.strip().splitlines()[-1]))
    newest = actors[chosen]['listed'][-1] if chosen else None
    delivered = [u for u in host.get('updates', ()) if u.get('outcome') == 'delivered']
    others = [u for u in host.get('updates', ()) if u.get('outcome') != 'delivered']
    checks['host_delivered_the_newest_listed_version_to_its_next_request'] = (
        host.get('ok') is True and host.get('host') == dict(schema='player-host/11', telemetry_version=11)
        and len(delivered) == 1 and delivered[0]['type'] == 'knowledge-delivery' and delivered[0]['version'] == newest
        and delivered[0]['previous_version'] == actors[chosen]['frozen_version']
        and delivered[0]['coverage'] == exported[newest]['coverage']
        and delivered[0]['delivered_knowledge_schema'] == 'delivered-knowledge/2'
        and isinstance(delivered[0].get('receiving_player_request_id'), str)
        and all(u.get('reason') == 'superseded' for u in others) and len(others) == len(actors[chosen]['listed']) - 1)
    return checks, dict(published=published, exported=exported, leftovers=leftovers, covered_prefix=prefix, actors=actors,
                        served=record['served'], host=host)


def summarize(result: dict) -> str:
    lines_out = [f"Live curator stand-in run: {'PASS' if result['passed'] else 'FAIL'}", '']
    for name, ok in result['checks'].items():
        lines_out.append(f"  {'pass' if ok else 'FAIL'}  {name}")
    lines_out.append('')
    for w in result['windows']:
        lines_out.append(f"  window {w['actor']} {w['first']}-{w['last']}: {w['outcome']} in {w['session_seconds']} s")
    snap = result['snapshots']
    lines_out += ['', f"  reads {snap['reads']} of {snap['polls']} polls, hold max {snap['hold_seconds'].get('max')} s, "
                      f"transaction max {snap['transaction_seconds'].get('max')} s, staging max {snap['staging_seconds'].get('max')} s",
                  f"  writer with runner {result['writer']['with_runner']['operations_per_minute']} ops/min, "
                  f"alone {result['writer']['alone']['operations_per_minute']} ops/min; step max "
                  f"{result['writer']['with_runner']['step_seconds'].get('max')} s vs {result['writer']['alone']['step_seconds'].get('max')} s",
                  f"  runner's final lag {result['final_status']['lag']}, backlog {result['final_status']['backlog']}, "
                  f"unexamined {result['final_status']['unexamined']}, as of operation "
                  f"{(result['final_status']['as_of'] or {}).get('ordinal')}, after it {result['final_status']['after_last_read']}",
                  f"  against the sealed store: lag {result['left_at_end_against_sealed_store']['lag']}, unexamined "
                  f"{result['left_at_end_against_sealed_store']['unexamined']}",
                  f"  nominal cost {result['cost']['total_usd']} (not money), per examined step {result['cost']['per_examined_step_usd']}",
                  f"  live delivery: runner left {', '.join(result['live_delivery']['exported']) or 'nothing'}; listed "
                  + '; '.join(f"{name} from {a['frozen_version']}: {', '.join(a['listed']) or 'none'}"
                              for name, a in result['live_delivery']['actors'].items())
                  + f"; host replay of {result['live_delivery']['host'].get('replayed')}: "
                  + ', '.join(f"{u.get('version')} {u.get('outcome') or u.get('type')}" for u in result['live_delivery']['host'].get('updates', ())),
                  f"  runner: {result['runner_teardown']['final_state']} ({result['runner_teardown']['stop_reason']})"]
    return '\n'.join(lines_out) + '\n'


def run_main(args: argparse.Namespace) -> int:
    import platform

    from harness.curator import sandbox
    from tools.curator_host import shadow

    main = main_checkout()
    out = Path(args.output)
    out = (out if out.is_absolute() else Path.cwd()/out).resolve()
    allowed = main/'.runtime'
    if allowed not in out.parents or any(out == allowed/n or allowed/n in out.parents
                                         for n in ('evidence', 'computer-sessions', 'worktrees')):
        raise SystemExit(f'refused: the output directory must be a new directory inside {allowed}, '
                         'not under evidence, computer-sessions or worktrees')
    if out.exists():
        raise SystemExit(f'refused: {out} exists; a run never reuses an output directory')
    if platform.system() != 'Darwin' or not Path(sandbox.SANDBOX_EXEC).exists():
        raise SystemExit('refused: the curator sandbox needs macOS Seatbelt')
    if not (shadow.HOST_DIR/'node_modules').is_dir() or shutil.which('node') is None:
        raise SystemExit('refused: install the curator host first (npm ci in tools/curator_host, docs/operations/coding-agents.md)')
    if not (ROOT/'tools'/'player_host'/'node_modules').is_dir():
        raise SystemExit('refused: install the player host first (npm ci in tools/player_host, docs/setup.md); '
                         'the live delivery check replays an update list through it')
    knowledge_root = ROOT/'.runtime'/'knowledge'/'live-curator-stand-in-run'/out.name
    if knowledge_root.exists():
        raise SystemExit(f'refused: {knowledge_root} exists; the runner needs a fresh knowledge repository')
    os.environ.pop(shadow.KEY_VARIABLE, None)  # nothing here may present a provider key
    out.mkdir(parents=True)
    live = live_run(out, knowledge_root, args)
    alone = writer_alone(out, args)
    result = measure(out, live, alone)
    shutil.copytree(knowledge_root, out/'knowledge')
    result = dict(schema='live-curator-stand-in-run/2', output=str(out), passed=all(result['checks'].values()),
                  wall_seconds=round(live['ended_wall'] - live['began_wall'], 2), session=live['session'],
                  source_commit=live['commit'], settings=dict(pace_seconds=args.pace, steps_per_actor=args.steps,
                                                              actors=args.actors, arm=args.arm,
                                                              poll_seconds=live['config'].get('poll_seconds', 'default')),
                  substituted=dict(custodian=live['substitutions'],
                                   preflight='replaced: a fixed profile and a route naming a dummy variable',
                                   route_credential=f'a dummy value in {DUMMY_KEY_VARIABLE}',
                                   provider='tests.curator_stand_in.StandIn on loopback, fact identities made distinct per window',
                                   knowledge_root=f'{knowledge_root} (the runner has no --runtime-root from the guardian); '
                                                  'copied to knowledge/'),
                  **result)
    (out/'report.json').write_text(json.dumps(result, indent=1, sort_keys=False, default=str) + '\n')
    text = summarize(result)
    (out/'summary.txt').write_text(text)
    print(text, end='')
    return 0 if result['passed'] else 1


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command')
    w = sub.add_parser('writer', help="the custodian's substitute (started by the wrapped guardian)")
    for name in ('--run', '--record', '--session', '--commit'):
        w.add_argument(name, required=True)
    w.add_argument('--port', type=int, required=True)
    w.add_argument('--wall-seconds', type=float, required=True)
    for target in (p, w):
        target.add_argument('--pace', type=float, default=1.0, help='seconds between the starts of two steps')
        target.add_argument('--steps', type=int, default=45, help='finished steps per actor')
        target.add_argument('--actors', type=int, default=2, help='actors, with a handoff between each two')
    p.add_argument('--output', help='a new directory inside the main checkout .runtime/')
    p.add_argument('--arm', default='terra', help='the curator arm whose frozen price the proxy counts with')
    p.add_argument('--poll-seconds', type=float, default=None, help="the runner's poll interval (its default if omitted)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == 'writer':
        return writer_main(args)
    if not args.output:
        parser().error('--output is required')
    if args.actors < 2 or args.steps < 30:
        parser().error('the run needs two actors and at least 30 steps each (three windows of 20 across a handoff)')
    return run_main(args)


if __name__ == '__main__':
    raise SystemExit(main())
