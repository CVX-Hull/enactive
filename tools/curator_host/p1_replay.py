"""Replay for the P1 offline study: arm B's curator sessions and every arm's delivered text (docs/design/p1-study-2.md; #462).

    python -m tools.curator_host.p1_replay b --stage pilot --repeat 1 --lineage aidB3 ceil09 --cap-usd 12
    python -m tools.curator_host.p1_replay deliver --lineage 397 --schedule <schedule.json> --out <runtime>/p1-delivered/dev
    python -m tools.curator_host.p1_replay freeze

`b` runs one curator session per admission of each lineage, in order, on a fresh knowledge
repository, with the pre-registered settings (terra, medium effort, a 24/12 image window, at most
120 requests per session), a fixed $12 cap per session (less only when the stage has less left) and
one whole-stage dollar cap enforced by the proxy. It reuses `tools.curator_host.shadow`'s `run_one`, so
a session is exactly a #454 shadow session whose memory is the lineage store cut strictly before the
next admission's first operation (the whole store for the last admission): the instant arm A uses at
that admission boundary. It records which version each session published
(`schedule.json`, `p1-schedule/1`), which is all arm B's D2 timing needs.

`deliver` writes `delivered.jsonl` (`p1-delivered/1`): for every boundary the Reference, A and, for
each recorded schedule, B text the successor would have received. It makes no model call and prints
only counts.

#382's held-out lineages (lh1, lh2, lh3) are refused by name unless `--frozen` names an
`p1-arms-frozen/1` file, written by `freeze`, whose every digest matches the current files, whose
files are all committed and unmodified, and whose commit is HEAD or an ancestor of it.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.curator.knowledge import KnowledgeError, Repository  # noqa: E402
from harness.jsonio import file_sha256  # noqa: E402
from tools.curator_host import p1_arms as arms  # noqa: E402
from tools.curator_host import shadow  # noqa: E402

FROZEN_SCHEMA = 'p1-arms-frozen/1'
DELIVERED_SCHEMA = 'p1-delivered/1'
SCHEDULE_SCHEMA = 'p1-schedule/1'
FROZEN_FILE = ROOT/'data'/'evaluation'/'p1'/'arms-frozen.json'
HOST_DIR = shadow.HOST_DIR
GAME = shadow.GAME

# The pre-registered arm B settings and the renderer's constants. `freeze` records them, and a
# held-out run refuses a frozen file whose settings differ from these.
SETTINGS = dict(arm='terra', effort='medium', max_context_images=24, context_image_block=12, max_requests=120,
                max_output_tokens=16384, request_timeout_seconds=240, wall_seconds=1800, session_cap_usd=12,
                cap_tokens=arms.CAP_TOKENS, statement_chars=arms.STATEMENT_CHARS, repeats=[1, 2], game=GAME)
# npm's record of the installed Node tree. It is ignored by Git, so it is digested but not checked for tracking.
NODE_LOCK = 'tools/curator_host/node_modules/.package-lock.json'
# Every file the arms run: the arms and replay, the shadow runner and host they reuse (prompt, Node
# host, launcher, providers, locked dependencies), the curator process, gate, repository, sandbox
# and proxy, and the trace projection and memory reader the curator's inputs come from.
FROZEN_FILES = ('tools/curator_host/p1_arms.py', 'tools/curator_host/p1_replay.py', 'tools/curator_host/shadow.py',
                'tools/curator_host/providers.py', 'tools/curator_host/launch.py', 'tools/curator_host/prompt.md',
                'tools/curator_host/host.mjs', 'tools/curator_host/run.mjs', 'tools/curator_host/workspace-tools.mjs',
                'tools/curator_host/package.json', 'tools/curator_host/package-lock.json',
                'harness/curator/session.py', 'harness/curator/gate.py', 'harness/curator/knowledge.py',
                'harness/curator/sandbox.py', 'harness/curator/proxy.py', 'harness/curator/containers.py',
                'harness/trace/projection.py', 'harness/trace/memory_reader.py', 'harness/trace/sidecar.py',
                'harness/trace/stores.py', 'harness/trace/__init__.py', 'harness/curator/__init__.py',
                # The session copies the whole trace package into the curator's workbench, which runs it.
                'harness/trace/workbench.py', 'harness/trace/images.py',
                'harness/jsonio.py', 'tools/probe_timeline.py', 'data/curator/shadow-arms.json', NODE_LOCK)
HELD_OUT_NAME = re.compile(r'lh[0-9]')
STAGE = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')


class ReplayError(ValueError):
    """The replay cannot start as asked."""


@dataclass(frozen=True)
class Lineage:
    directory: str
    sessions: tuple[str, ...]
    store: str
    held_out: bool = False


_DEV_LOOP = '372-382-dev-loop'
LINEAGES = {
    # Pilot: each #372 run is its own lineage of one admission.
    'aidB3': Lineage(_DEV_LOOP, ('aidB3',), 'player-memory-aidB3.sqlite3'),
    'ceil09': Lineage(_DEV_LOOP, ('ceil09',), 'player-memory-ceil09.sqlite3'),
    # Development: #397's seven admissions share one store.
    '397': Lineage('397-seven-day', tuple(f'sd1a{n}' for n in range(1, 8)), 'player-memory-sd1.sqlite3'),
    # Held out (#382): refused unless a matching freeze is given.
    'lh1': Lineage(_DEV_LOOP, ('lh1a1', 'lh1a2', 'lh1a3'), 'player-memory-lh1.sqlite3', held_out=True),
    'lh2': Lineage(_DEV_LOOP, ('lh2a1', 'lh2a2'), 'player-memory-lh2.sqlite3', held_out=True),
    'lh3': Lineage(_DEV_LOOP, ('lh3a1', 'lh3a2'), 'player-memory-lh3.sqlite3', held_out=True),
}


# ------------------------------------------------------------------ the freeze
def _relative(path: Path) -> str:
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _resolve(relative: str) -> Path:
    return Path(relative) if Path(relative).is_absolute() else ROOT/relative


def frozen_paths(prices: Path) -> list[str]:
    """The files whose digests the freeze lists, as repository-relative (or absolute) strings."""
    return [*FROZEN_FILES, _relative(prices)]


def _git(*args: str) -> subprocess.CompletedProcess:
    """A Git command in the repository this code lives in, with no inherited `GIT_*` redirection."""
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    try:
        return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, env=environment, check=False)
    except OSError as error:
        raise ReplayError(f'git could not run: {error}') from error


def freeze(out: Path, prices: Path) -> dict:
    """Write the `p1-arms-frozen/1` file: the current commit, a digest for each listed file and the settings."""
    out = Path(out)
    if out.exists():
        raise ReplayError(f'{out} exists; a freeze is written once')
    paths = frozen_paths(Path(prices))
    missing = [p for p in paths if not _resolve(p).is_file()]
    if missing:
        raise ReplayError(f'cannot freeze missing files: {", ".join(missing)}')
    head = _git('rev-parse', 'HEAD')
    if head.returncode != 0:
        raise ReplayError(f'cannot read the current commit: {head.stderr.strip()}')
    # The recorded commit must hold the frozen bytes: refuse a listed file that is untracked or differs from HEAD.
    _verify_committed(None, {}, [p for p in paths if p != NODE_LOCK], check_commit=False)
    frozen = dict(schema=FROZEN_SCHEMA, commit=head.stdout.strip(), files={p: file_sha256(_resolve(p)) for p in paths},
                  settings=SETTINGS,
                  note='The P1 arms are fixed: code, prompt, host, renderer, cap, prices and settings. Any later '
                       'change is a recorded deviation (docs/design/p1-study-2.md, Freezing).')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(frozen, indent=1, sort_keys=True) + '\n')
    return frozen


def verify_frozen(path: Path | None, prices: Path) -> None:
    """Refuse unless `path` is a freeze file that lists every frozen file and every digest and setting matches."""
    if path is None:
        raise ReplayError('a held-out lineage needs --frozen, the p1-arms-frozen/1 file written by `freeze`')
    try:
        frozen = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise ReplayError(f'{path}: unreadable freeze file') from error
    if not isinstance(frozen, dict) or frozen.get('schema') != FROZEN_SCHEMA or not isinstance(frozen.get('files'), dict):
        raise ReplayError(f'{path}: not a {FROZEN_SCHEMA} file')
    problems = [f'{name}: not frozen' for name in frozen_paths(prices) if name not in frozen['files']]
    for name, digest in sorted(frozen['files'].items()):
        target = _resolve(name)
        if not target.is_file():
            problems.append(f'{name}: missing')
        elif file_sha256(target) != digest:
            problems.append(f'{name}: changed since the freeze')
    if frozen.get('settings') != SETTINGS:
        problems.append('settings: differ from the pre-registered settings')
    if problems:
        raise ReplayError('the arms are not as frozen: ' + '; '.join(problems))
    _verify_committed(Path(path), frozen, [name for name in frozen['files'] if name != NODE_LOCK])


def _verify_committed(path: Path | None, frozen: dict, names: list[str], *, check_commit: bool = True) -> None:
    """The freeze file (when given) and every listed file (the Node install record excepted) are tracked
    and match HEAD, and HEAD is the frozen commit or descends from it. Digests alone would accept files
    that were never committed. `freeze` runs it without a freeze file or commit, so the commit it records
    holds exactly the frozen bytes."""
    targets = [*([str(Path(path).resolve())] if path is not None else []), *(str(_resolve(name)) for name in names)]
    problems = []
    for target in targets:
        if _git('ls-files', '--error-unmatch', '--', target).returncode != 0:
            problems.append(f'{_relative(Path(target))}: not tracked by Git')
    if problems:
        raise ReplayError('the arms are not committed: ' + '; '.join(problems))
    changed = _git('diff', '--name-only', 'HEAD', '--', *targets)
    if changed.returncode != 0 or changed.stdout.strip():
        listed = ', '.join(changed.stdout.split()) or changed.stderr.strip()
        raise ReplayError(f'the arms are not committed: modified against HEAD: {listed}')
    if not check_commit:
        return
    commit = frozen.get('commit')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ReplayError('the freeze file records no commit')
    if _git('merge-base', '--is-ancestor', commit, 'HEAD').returncode != 0:
        raise ReplayError(f'HEAD does not equal or descend from the frozen commit {commit[:12]}')


def select(names: Sequence[str], frozen: Path | None, prices: Path) -> list[str]:
    """The named lineages in the order given. A held-out name needs a matching freeze, checked first."""
    if not names:
        raise ReplayError('name at least one lineage')
    if len(set(names)) != len(names):
        raise ReplayError('a lineage can be named once')
    for name in names:
        if name not in LINEAGES:
            held = ' (a held-out name needs a frozen arms file, and only lh1, lh2 and lh3 exist)' \
                if HELD_OUT_NAME.match(name) else ''
            raise ReplayError(f'unknown lineage {name!r}; choose one of {", ".join(LINEAGES)}{held}')
    if any(LINEAGES[name].held_out for name in names):
        verify_frozen(frozen, prices)
    return list(names)


# ------------------------------------------------------------------ arm B's sessions
def _write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True, default=str) + '\n')
    return path


def _check_upstream(upstream: str) -> None:
    if upstream != shadow.OPENROUTER_ORIGIN and not re.fullmatch(r'http://(127\.0\.0\.1|localhost):[0-9]{1,5}', upstream):
        raise ReplayError('--upstream may only be OpenRouter or a local http origin (for tests)')


def _evidence(args: argparse.Namespace) -> Path:
    return Path(args.evidence_root) if args.evidence_root else Path(args.runtime_root).resolve()/'evidence'


def _trace(evidence: Path, spec: Lineage, name: str) -> Path:
    trace = evidence/spec.directory/'computer-sessions'/name
    if not (trace/'session.sqlite3').is_file():
        raise ReplayError(f'{trace} is not a sealed session')
    return trace


def run_b(args: argparse.Namespace, key: str) -> dict:
    """One curator session per admission of each lineage, in order, over one stage cap. Returns the run summary."""
    prices_path = Path(args.prices)
    names = select(args.lineage, args.frozen, prices_path)
    if not STAGE.fullmatch(args.stage):
        raise ReplayError('--stage is a short lowercase label')
    if args.repeat not in (1, 2):
        raise ReplayError('--repeat is 1 or 2')
    _check_upstream(args.upstream)
    runtime = Path(args.runtime_root).resolve()
    out = runtime/'curator-shadow'/'p1'/args.stage/f'r{args.repeat}'
    knowledge = runtime/'knowledge'/'p1'/args.stage/f'r{args.repeat}'
    for target in (out, knowledge):
        if target.exists():
            raise ReplayError(f'{target} exists; every repeat starts a fresh directory')
    evidence = _evidence(args)
    plan = []
    for name in names:
        spec = LINEAGES[name]
        store = evidence/spec.directory/spec.store
        if not store.is_file():
            raise ReplayError(f'{store}: the lineage store is absent')
        sessions = [(session, _trace(evidence, spec, session)) for session in spec.sessions]
        plan.append((name, spec, store, sessions, arms.curator_cutoffs([trace for _, trace in sessions])))
    prices = shadow.load_prices(prices_path)
    arm = shadow.ARMS[SETTINGS['arm']]
    if arm.model not in prices:
        raise ReplayError(f'{arm.model} has no frozen price')
    cap = Decimal(str(args.cap_usd))
    if cap <= 0:
        raise ReplayError('--cap-usd must be positive')
    # Every session has the same fixed cap (and so the same host budget) unless the stage has less left,
    # so a session's budget does not depend on the lineage order or the stage cap.
    session_cap = Decimal(str(SETTINGS['session_cap_usd']))
    host = shadow.host_tools()
    model_config = shadow.host_configuration(
        arm, prices, effort=SETTINGS['effort'], max_requests=SETTINGS['max_requests'],
        max_output_tokens=SETTINGS['max_output_tokens'], request_timeout_seconds=SETTINGS['request_timeout_seconds'],
        wall_seconds=SETTINGS['wall_seconds'] - 30, max_context_images=SETTINGS['max_context_images'],
        context_image_block=SETTINGS['context_image_block'], workbench_timeout_seconds=60,
        budget_usd=float(session_cap * shadow.HOST_BUDGET_SHARE))
    identity = shadow.host_identity(host, model_config)
    out.mkdir(parents=True)
    config_dir = out/'host-config'
    config_dir.mkdir()
    config_path = _write(config_dir/f'{SETTINGS["arm"]}.json', model_config)
    run = dict(schema=shadow.SCHEMA, kind='run', arm=SETTINGS['arm'], model=arm.model, effort=model_config['effort'],
               stage=args.stage, repeat=args.repeat, lineages=names, cap_usd=str(cap), session_cap_usd=str(session_cap),
               upstream=args.upstream, prices=_relative(prices_path), host=identity,
               started_wall=time.time(), sessions=[], stopped=None)
    schedule = dict(schema=SCHEDULE_SCHEMA, stage=args.stage, repeat=args.repeat, game=GAME, cap_usd=str(cap),
                    session_cap_usd=str(session_cap), lineage_order=names,
                    knowledge=str(knowledge.relative_to(runtime)), lineages={}, stopped=None)
    spent = Decimal(0)

    def record() -> None:
        schedule['stopped'] = run['stopped']
        schedule['total_cost_usd'] = str(spent)
        _write(out/'schedule.json', schedule)

    try:
        for name, spec, store, sessions, cutoffs in plan:
            repo = Repository(knowledge/name, GAME)
            repo.ensure()
            entry = schedule['lineages'][name] = dict(sessions=[])
            for (session, trace), until in zip(sessions, cutoffs):
                remaining = cap - spent
                if remaining <= 0:
                    run['stopped'] = 'cap-reached'
                    break
                this_cap = min(session_cap, remaining)
                summary = shadow.run_one(
                    arm_name=SETTINGS['arm'], lineage=name, name=session, trace=trace, repo=repo, memory=store,
                    memory_note=('lineage store before the next admission begins' if until is not None
                                 else 'whole lineage store (the last admission)'),
                    host=host, config_path=config_path, config_dir=config_dir, model_config=model_config, prices=prices,
                    key=key, upstream=args.upstream, cap=this_cap, out=out,
                    wall_seconds=SETTINGS['wall_seconds'], max_output_tokens=SETTINGS['max_output_tokens'],
                    memory_until=until)
                spent += Decimal(summary['cost_usd'])
                state = summary.get('session_state', summary['run_state'])
                entry['sessions'].append(dict(session=session, memory_until=until, cap_usd=str(this_cap),
                                              session_state=state, cost_usd=summary['cost_usd'],
                                              published_before=summary['published_before'],
                                              published_after=repo.published(),
                                              stopped_by_cap=summary['stopped_by_cap'],
                                              summary=str((out/name/session/'summary.json').relative_to(out))))
                run['sessions'].append(dict(lineage=name, trace_session=session, session_state=state,
                                            cost_usd=summary['cost_usd'], accepted=summary.get('accepted'),
                                            rejected=summary.get('rejected')))
                print(f'B{args.repeat} {name} {session}: {state}, {summary.get("requests")} requests, '
                      f'${summary["cost_usd"]}, accepted {summary.get("accepted")}, rejected {summary.get("rejected")}',
                      flush=True)
                if summary['proxy']['revoked'] or summary['proxy']['breaches']:
                    run['stopped'] = 'proxy-revoked'
                elif cap - spent <= 0 or (summary['stopped_by_cap'] and this_cap == remaining):
                    run['stopped'] = 'cap-reached'   # the stage's cap, not only the session's own
                record()
                if run['stopped']:
                    break
            if run['stopped']:
                break
    finally:
        record()
        planned = sum(len(spec.sessions) for _, spec, _, _, _ in plan)
        run.update(ended_wall=time.time(), total_cost_usd=str(spent), sessions_run=len(run['sessions']),
                   complete=run['stopped'] is None and len(run['sessions']) == planned)
        _write(out/'summary.json', run)
    return run


# ------------------------------------------------------------------ delivered text
def load_schedule(path: Path) -> dict:
    try:
        schedule = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise ReplayError(f'{path}: unreadable schedule') from error
    if not isinstance(schedule, dict) or schedule.get('schema') != SCHEDULE_SCHEMA \
            or schedule.get('repeat') not in (1, 2) or not isinstance(schedule.get('lineages'), dict):
        raise ReplayError(f'{path}: not a {SCHEDULE_SCHEMA} file')
    return schedule


def _row(lineage: str, boundary: arms.Boundary, arm: str, repeat: int, received: str, sha: str,
         rendered: arms.Rendered | None, complete: bool = True) -> dict:
    text = received if rendered is None else arms.delivered(received, rendered)
    return dict(schema=DELIVERED_SCHEMA, lineage=lineage, boundary=boundary.name, kind=boundary.kind, arm=arm,
                repeat=repeat, text=text, tokens=rendered.tokens if rendered else 0,
                items=rendered.items if rendered else 0, dropped=rendered.dropped if rendered else 0,
                received_sha256=sha, complete=complete)


def b_complete(schedule: dict, name: str) -> bool:
    """Whether the recorded repeat ran to the end: not stopped, and every session of the lineage sealed."""
    return schedule.get('stopped') is None and all(s.get('session_state') == 'sealed'
                                                   for s in schedule['lineages'][name]['sessions'])


def knowledge_root(runtime: Path, schedule: dict, name: str) -> Path:
    """The recorded repository of a lineage, refused unless it lies inside `<runtime>/knowledge/p1`."""
    allowed = (runtime/'knowledge'/'p1').resolve()
    recorded = schedule.get('knowledge')
    root = (runtime/recorded/name).resolve() if isinstance(recorded, str) and recorded and '\0' not in recorded else None
    if root is None or allowed not in root.parents:
        raise ReplayError(f'repeat {schedule["repeat"]}: the recorded knowledge path {recorded!r} is not inside {allowed}')
    return root


def b_versions(schedule: dict, name: str) -> list[str]:
    """The version each admission's curator session published, from a recorded schedule, complete or refused."""
    entry = schedule['lineages'].get(name)
    sessions = LINEAGES[name].sessions
    if entry is None or [s.get('session') for s in entry.get('sessions', [])] != list(sessions):
        raise ReplayError(f'repeat {schedule["repeat"]} has no complete schedule for lineage {name}')
    return [s['published_after'] for s in entry['sessions']]


def lineage_rows(name: str, evidence: Path, runtime: Path, schedules: Sequence[dict]) -> list[dict]:
    """Every arm's delivered text at every boundary of one lineage."""
    spec = LINEAGES[name]
    sessions = [_trace(evidence, spec, session) for session in spec.sessions]
    store_path = evidence/spec.directory/spec.store
    if not store_path.is_file():
        raise ReplayError(f'{store_path}: the lineage store is absent')
    store = arms.read_store(store_path)
    b_sources = []
    for schedule in schedules:
        versions = b_versions(schedule, name)
        complete = b_complete(schedule, name)
        if spec.held_out and not complete:
            raise ReplayError(f'repeat {schedule["repeat"]} of held-out lineage {name} is incomplete '
                              '(stopped, or a session did not seal); its partial labels are not delivered')
        repo = Repository(knowledge_root(runtime, schedule, name), GAME)
        b_sources.append((schedule['repeat'], repo, versions, {}, complete))
    rows = []
    for boundary in arms.boundaries(sessions):
        received = arms.received_text(boundary)
        sha = hashlib.sha256(received.encode('utf-8')).hexdigest()
        rows.append(_row(name, boundary, 'R', 1, received, sha, None))
        rows.append(_row(name, boundary, 'A', 1, received, sha,
                         arms.render(arms.arm_a_items(store, boundary.cutoff))))
        for repeat, repo, versions, cache, complete in b_sources:
            version = arms.scheduled_version(boundary.admission, versions)
            if version is None:
                items = []
            else:
                if version not in cache:
                    try:
                        cache[version] = repo.facts(version)
                    except KnowledgeError as error:
                        raise ReplayError(f'{name} repeat {repeat}: {error}') from error
                items = arms.arm_b_items(cache[version], repo.game)
            rows.append(_row(name, boundary, 'B', repeat, received, sha, arms.render(items), complete))
    return rows


def deliver(args: argparse.Namespace) -> dict:
    """Write `delivered.jsonl` for the named lineages. Returns the row counts per lineage and arm."""
    names = select(args.lineage, args.frozen, Path(args.prices))
    runtime = Path(args.runtime_root).resolve()
    out = Path(args.out).resolve()
    if runtime/'p1-delivered' not in out.parents:
        raise ReplayError(f'--out must be inside {runtime/"p1-delivered"}')
    if out.exists():
        raise ReplayError(f'{out} exists; every delivery writes a fresh directory')
    schedules = [load_schedule(path) for path in args.schedule or []]
    if len({s['repeat'] for s in schedules}) != len(schedules):
        raise ReplayError('name one schedule per repeat')
    evidence = _evidence(args)
    rows, counts = [], {}
    for name in names:
        made = lineage_rows(name, evidence, runtime, schedules)
        rows.extend(made)
        tally: dict[str, int] = {}
        for row in made:
            label = row['arm'] + (str(row['repeat']) if row['arm'] == 'B' else '')
            tally[label] = tally.get(label, 0) + 1
        counts[name] = tally
    out.mkdir(parents=True)
    with (out/'delivered.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
    return counts


# ------------------------------------------------------------------ command line
def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)

    def common(q: argparse.ArgumentParser) -> None:
        q.add_argument('--prices', default=str(shadow.DEFAULT_PRICES))
        q.add_argument('--runtime-root', default=str(ROOT/'.runtime'))
        q.add_argument('--evidence-root', help='default: <runtime-root>/evidence (or ENACTIVE_EVIDENCE_ROOT)')
        q.add_argument('--frozen', type=Path, help='the p1-arms-frozen/1 file; required for any held-out lineage')

    b = sub.add_parser('b', help="arm B: one curator session per admission, on a fresh repository")
    common(b)
    b.add_argument('--stage', required=True, help='a label for the stage, the directory under curator-shadow/p1/')
    b.add_argument('--repeat', required=True, type=int, choices=(1, 2))
    b.add_argument('--lineage', required=True, nargs='+', help=f'one or more of {", ".join(LINEAGES)}')
    b.add_argument('--cap-usd', required=True, type=float, help='whole-stage dollar cap, enforced by the proxy')
    b.add_argument('--upstream', default=shadow.OPENROUTER_ORIGIN, help='OpenRouter, or a local http origin for tests')

    d = sub.add_parser('deliver', help='write delivered.jsonl: the Reference, A and B text at every boundary')
    common(d)
    d.add_argument('--lineage', required=True, nargs='+')
    d.add_argument('--schedule', nargs='*', help='the schedule.json of each B repeat to deliver')
    d.add_argument('--out', required=True, help='a new directory under <runtime-root>/p1-delivered/')

    f = sub.add_parser('freeze', help='write the p1-arms-frozen/1 file')
    f.add_argument('--prices', default=str(shadow.DEFAULT_PRICES))
    f.add_argument('--out', type=Path, default=FROZEN_FILE)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == 'freeze':
            frozen = freeze(args.out, Path(args.prices))
            print(json.dumps(dict(out=str(args.out), files=len(frozen['files']))))
            return 0
        if args.evidence_root is None and os.environ.get('ENACTIVE_EVIDENCE_ROOT'):
            args.evidence_root = os.environ['ENACTIVE_EVIDENCE_ROOT']
        if args.command == 'deliver':
            print(json.dumps(deliver(args), sort_keys=True))
            return 0
        select(args.lineage, args.frozen, Path(args.prices))  # refuse held-out names before the key is read
        if args.upstream != shadow.OPENROUTER_ORIGIN:
            key = shadow.LOOPBACK_KEY  # a local test upstream never receives the operator's key
        else:
            key = shadow.credential(shadow.KEY_VARIABLE, mapping=Path(args.runtime_root)/'credentials.json')
        if not key:
            raise ReplayError(f'{shadow.KEY_VARIABLE} is not set and not mapped to a keychain item (docs/setup.md)')
        run = run_b(args, key)
    except (ReplayError, arms.ArmsError, shadow.ShadowError, KnowledgeError, OSError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f'p1_replay: {error}', file=sys.stderr)
        return 2
    print(json.dumps({k: run[k] for k in ('arm', 'stage', 'repeat', 'lineages', 'sessions_run', 'total_cost_usd',
                                          'stopped', 'complete')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
