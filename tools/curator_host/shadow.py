"""Shadow runner for the curator host (tools/curator_host) over sealed traces (#454; ADR 009 open decision 2).

Replays recorded lineages through curator sessions, one `run_session` per admission or run in
lineage order, against a per-arm, per-lineage knowledge repository. The arm picks the model
(`terra` or `opus`, both through OpenRouter). Every model request goes through a `ModelProxy`
that holds the provider key and enforces the dollar cap; the host presents only a per-session
token. The key comes from `OPENROUTER_API_KEY`, or else from the operator's keychain item mapped in
the git-ignored `.runtime/credentials.json` (the campaign's own `credential()`), and is never
printed or written.

    python -m tools.curator_host.shadow --arm terra --lineage 397 --sessions sd1a1 --cap-usd 2 \
        --out .runtime/curator-shadow/pilot-1

Only the sampled sessions of the two development lineages can be named. #382's held-out lineages
(lh1, lh2, lh3) are refused by name. Summaries are `curator-shadow/1`, one per session and one per
run. Prices are the frozen `curator-prices/1` file in `data/curator/`.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.curator import sandbox  # noqa: E402
from harness.curator.knowledge import Repository  # noqa: E402
from harness.curator.proxy import ModelProxy, Price  # noqa: E402
from harness.curator.session import SessionConfig, run_session  # noqa: E402
from tools.campaign_supervision import credential  # noqa: E402
from tools.curator_host.providers import OPENROUTER  # noqa: E402

SCHEMA = 'curator-shadow/1'
PRICES_SCHEMA = 'curator-prices/1'
HOST_SCHEMA = 'curator-host/1'
HOST_DIR = ROOT/'tools'/'curator_host'
# The only parts of the host package the sandboxed process may read: the Node host and its
# dependencies, its prompt, and `launch.py`, the one Python file the sandbox's argv runs. The runner,
# report and providers beside them stay unreadable to the curator.
HOST_READABLE = ('host.mjs', 'run.mjs', 'workspace-tools.mjs', 'prompt.md', 'package.json', 'launch.py', 'node_modules')
DEFAULT_PRICES = ROOT/'data'/'curator'/'openrouter-prices-2026-11-08.json'
OPENROUTER_ORIGIN = 'https://openrouter.ai'
GAME = 'cdda'
KEY_VARIABLE = 'OPENROUTER_API_KEY'
HOST_BUDGET_SHARE = Decimal('0.85')  # the host's budget as a share of its session's proxy cap
LOOPBACK_KEY = 'loopback-test-key'  # a local test upstream never receives the operator's key

# Sampled sessions only, in lineage order. 397: the seven admissions. 372: the six runs named by
# the issue. Nothing else can be selected.
LINEAGES = {
    '397': dict(directory='397-seven-day', sessions=('sd1a1', 'sd1a2', 'sd1a3', 'sd1a4', 'sd1a5', 'sd1a6', 'sd1a7'),
                memory=None),
    '372': dict(directory='372-382-dev-loop', sessions=('aidB3', 'ceil09', 'ceil07', 'ceil05', 'aidB9', 'aidA5'),
                memory='player-memory-{name}.sqlite3'),
}
HELD_OUT = re.compile(r'lh[1-4]')


class ShadowError(ValueError):
    """The run cannot start as asked."""


@dataclass(frozen=True)
class Arm:
    model: str
    name: str
    provider: str  # the one OpenRouter provider the route is pinned to
    effort: str


# The arms are tracked configuration beside the frozen prices: each arm's OpenRouter model, display
# name, the one provider its route is pinned to, and its effort.
ARMS_SCHEMA = 'curator-shadow-arms/1'
ARMS_FILE = ROOT/'data'/'curator'/'shadow-arms.json'


def load_arms(path: Path = ARMS_FILE) -> dict[str, Arm]:
    data = json.loads(Path(path).read_text())
    if data.get('schema') != ARMS_SCHEMA:
        raise ShadowError(f'{path}: not a {ARMS_SCHEMA} file')
    return {name: Arm(**row) for name, row in data['arms'].items()}


ARMS = load_arms()


def load_prices(path: Path) -> dict[str, Price]:
    data = json.loads(Path(path).read_text())
    if data.get('schema') != PRICES_SCHEMA:
        raise ShadowError(f'{path}: not a {PRICES_SCHEMA} file')
    prices = {}
    for model, row in data['models'].items():
        prices[model] = Price(input=Decimal(row['input']), output=Decimal(row['output']),
                              cache_write=Decimal(row['cache_write']), cache_read=Decimal(row['cache_read']))
    return prices


def select(lineage: str, sessions: list[str] | None) -> tuple[dict, list[str]]:
    """The lineage and its sessions, in lineage order. Held-out and unsampled names are refused."""
    for name in [lineage, *(sessions or [])]:
        if HELD_OUT.search(name):
            raise ShadowError(f'{name!r} names a held-out lineage (#382); it can never be selected')
    if lineage not in LINEAGES:
        raise ShadowError(f'unknown lineage {lineage!r}; choose one of {", ".join(LINEAGES)}')
    spec = LINEAGES[lineage]
    if sessions:
        unknown = [name for name in sessions if name not in spec['sessions']]
        if unknown:
            raise ShadowError(f'not in the sampled {lineage} sessions: {", ".join(unknown)}')
        if len(set(sessions)) != len(sessions):
            raise ShadowError('a session can be named once')
        return spec, [name for name in spec['sessions'] if name in sessions]
    return spec, list(spec['sessions'])


def host_configuration(arm: Arm, prices: dict[str, Price], *, effort: str, max_requests: int, max_output_tokens: int,
                       request_timeout_seconds: int, wall_seconds: int, max_context_images: int,
                       context_image_block: int, workbench_timeout_seconds: int, budget_usd: float) -> dict:
    price = prices[arm.model]
    per = lambda value: float(value)  # noqa: E731 - the host's cost entries are informational numbers
    return dict(
        schema=HOST_SCHEMA, effort=effort, max_requests=max_requests, request_timeout_seconds=request_timeout_seconds,
        budget_usd=budget_usd,
        wall_seconds=wall_seconds, max_context_images=max_context_images, context_image_block=context_image_block,
        workbench_timeout_seconds=workbench_timeout_seconds,
        model=dict(id=arm.model, name=arm.name, reasoning=True, input=['text', 'image'],
                   cost=dict(input=per(price.input), output=per(price.output), cacheRead=per(price.cache_read),
                             cacheWrite=per(price.cache_write)),
                   contextWindow=262144, maxTokens=max_output_tokens, thinkingLevelMap={effort: effort},
                   compat=dict(supportsDeveloperRole=False, supportsStore=False, supportsUsageInStreaming=True,
                               supportsReasoningEffort=True, supportsStrictMode=False,
                               maxTokensField='max_completion_tokens', thinkingFormat='openrouter',
                               openRouterRouting=dict(only=[arm.provider], order=[arm.provider],
                                                      allow_fallbacks=False, require_parameters=True))))


def _libraries(binary: Path) -> list[tuple[Path, Path | None]]:
    """(resolved library, directory holding the symbolic link its install name goes through, if any)."""
    out = subprocess.run(['/usr/bin/otool', '-L', str(binary)], capture_output=True, text=True, check=True).stdout
    found = []
    for line in out.splitlines()[1:]:
        name = line.strip().split(' (')[0]
        if name and not name.startswith(('/usr/lib/', '/System/', '@')):
            link = next((a.parent.resolve() for a in reversed(Path(name).parents) if a.is_symlink()), None)
            found.append((Path(name).resolve(), link))
    return found


def _keg(path: Path) -> Path:
    parts = path.parts
    return Path(*parts[:parts.index('Cellar') + 3]) if 'Cellar' in parts else path.parent


def node_tool_roots(node: Path | None = None) -> tuple[Path, tuple[Path, ...]]:
    """The resolved node binary and the directories it needs to run in the sandbox.

    A Homebrew node links its libraries from other kegs through `/opt/homebrew/opt/<name>` links,
    so each keg is a read-only tool root, and so is the directory of links (it holds only links, and
    the kegs behind them stay unreadable unless listed). A statically linked node needs only its
    own installation.
    """
    node = Path(node or shutil.which('node') or '').resolve()
    if not node.is_file():
        raise ShadowError('Node.js is required for the curator host')
    roots = {node.parents[1]}
    queue = [node]
    while queue:
        for library, link in _libraries(queue.pop()):
            if link is not None:
                roots.add(link)
            if library.is_file() and (keg := _keg(library)) not in roots:
                roots.add(keg)
                queue.append(library)
    return node, tuple(sorted(roots))


def refuse_broad_root(root: Path) -> None:
    """A readable tool root must not expose the disk, the home directory or the project runtime."""
    home = Path.home().resolve()
    project = ROOT.resolve()
    if root == Path('/') or root == home or root in home.parents or root in project.parents or root == project \
            or (project/'.runtime') in (root, *root.parents) or root in (project/'.runtime').parents:
        raise ShadowError(f'refusing a tool root that would expose too much: {root}')


def host_tools(extra: tuple[Path, ...] = ()) -> dict:
    """Everything the curator host process needs as sandbox tool roots, resolved."""
    if not (HOST_DIR/'node_modules').is_dir():
        raise ShadowError('Install the curator host first: npm --userconfig /dev/null --cache .cache/npm ci '
                          '--ignore-scripts --no-audit --no-fund --prefix tools/curator_host')
    node, node_roots = node_tool_roots()
    python = Path(os.path.realpath(sys.executable))
    roots = (*node_roots, *((HOST_DIR/name).resolve() for name in HOST_READABLE), Path(sys.base_prefix).resolve(), *extra)
    for root in roots:
        refuse_broad_root(root)
    # node reads an OpenSSL configuration file at startup (under Homebrew, outside every root) and
    # aborts when it is refused; the host speaks plain http to the loopback proxy, so none is needed.
    return dict(node=node, python=python, roots=tuple(dict.fromkeys(roots)),
                env=dict(CURATOR_PYTHON=str(python), OPENSSL_CONF='/dev/null'))


def host_argv(tools: dict, config_path: Path) -> tuple[str, ...]:
    """The sandbox argv: node runs behind `launch.py`, which gives it a pipe for its output."""
    return (str(tools['python']), '-I', str(HOST_DIR/'launch.py'), str(tools['node']), str(HOST_DIR/'run.mjs'),
            '--config', str(config_path))


def _lines(path: Path) -> list[dict]:
    rows = []
    if path.is_file():
        for line in path.read_text(errors='replace').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def telemetry(rows: list[dict]) -> dict:
    """Digest of the host's JSON-lines telemetry."""
    starts = [r for r in rows if r.get('type') == 'request-start']
    ends = [r for r in rows if r.get('type') == 'request-end' and not r.get('retry')]
    calls = [r for r in rows if r.get('type') == 'tool-call']
    end = next((r for r in reversed(rows) if r.get('type') == 'host-end'), None)
    total = lambda key: sum(r[key] for r in ends if isinstance(r.get(key), int))  # noqa: E731
    costs = [r['cost'] for r in ends if isinstance(r.get('cost'), (int, float))]
    by_name: dict[str, int] = {}
    for call in calls:
        by_name[call['name']] = by_name.get(call['name'], 0) + 1
    return dict(
        requests=len(starts), time_to_first_request_seconds=round(starts[0]['monotonic_ms'] / 1000, 3) if starts else None,
        first_request_prompt_tokens=next((r['prompt_tokens'] for r in ends if isinstance(r.get('prompt_tokens'), int)), None),
        tokens=dict(prompt=total('prompt_tokens'), completion=total('completion_tokens'), cached=total('cached_tokens'),
                    cache_write=total('cache_write_tokens'), reasoning=total('reasoning_tokens')),
        host_reported_cost_usd=str(sum(Decimal(str(c)) for c in costs)) if costs else None,
        tool_calls=dict(count=len(calls), failed=sum(1 for c in calls if not c.get('ok')), by_name=by_name,
                        bytes=sum(c.get('bytes', 0) for c in calls)),
        host_end=dict(reason=end.get('reason'), ok=end.get('ok')) if end else None,
        model_status=sorted({r['status'] for r in ends if r.get('status') is not None}),
    )


def _ledger(path: Path) -> dict:
    rows = _lines(path)
    refusals = [r for r in rows if r.get('refused')]
    return dict(entries=len(rows), refusals=len(refusals), refusal_reasons=sorted({r['refused'] for r in refusals}),
                forwarded=sum(1 for r in rows if not r.get('refused')),
                cap_refused=any(r.get('refused') == 'spend cap reached' for r in refusals),
                usage_missing=sum(1 for r in rows if r.get('usage_missing')))


def _write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True, default=str) + '\n')
    return path


def run_one(*, arm_name: str, lineage: str, name: str, trace: Path, repo: Repository, memory: Path | None,
            memory_note: str, host: dict, config_path: Path, config_dir: Path, model_config: dict, prices: dict[str, Price],
            key: str, upstream: str, cap: Decimal, out: Path, wall_seconds: int, max_output_tokens: int,
            memory_until: float | None = None) -> dict:
    """One curator session through its own proxy. Returns the `curator-shadow/1` session summary.

    `memory_until` keeps only memory written strictly before it (the P1 replay cuts a lineage store
    at the next admission's first operation); None passes the whole store."""
    session_dir = out/lineage/name
    session_dir.mkdir(parents=True)
    arm = ARMS[arm_name]
    proxy = ModelProxy(provider=OPENROUTER, upstream=upstream, key=key, prices={arm.model: prices[arm.model]},
                       cap_usd=cap, ledger=session_dir/'proxy-ledger.jsonl', max_output_tokens=max_output_tokens,
                       routing=model_config['model']['compat']['openRouterRouting'])
    port = proxy.start()
    # The host's own budget sits below the proxy cap, so its write and finish phases begin while
    # the proxy still admits requests (the proxy refuses on worst-case reservations, not spend).
    budget = float(cap * HOST_BUDGET_SHARE)
    session_config = _write(config_dir/f'{name}.json', dict(model_config, budget_usd=budget))
    summary = dict(schema=SCHEMA, kind='session', arm=arm_name, model=arm.model, effort=model_config['effort'],
                   lineage=lineage, trace_session=name, memory=dict(passed=memory is not None, note=memory_note),
                   cap_usd=str(cap), host_budget_usd=budget, published_before=repo.published(),
                   started_wall=time.time())
    started = time.monotonic()
    record = None
    try:
        config = SessionConfig(
            argv=host_argv(host, session_config),
            tools=(*host['roots'], config_dir.resolve()),
            limits=sandbox.Limits(wall_seconds=wall_seconds), proxy=proxy, proxy_port=port,
            extra_env=host['env'], host=host_identity(host, model_config))
        record = run_session(repo, [trace], config, memory=memory, memory_until=memory_until,
                             session_id=f'{name}-{uuid.uuid4().hex[:8]}')
        state = 'completed'
    except Exception as exc:  # noqa: BLE001 - a failed session is a result, not a crash of the run
        state = f'error: {type(exc).__name__}: {exc}'
    wall = time.monotonic() - started
    revoked, breaches, spent = proxy.revoked, proxy.breaches, proxy.spent
    proxy.close()
    ledger = _ledger(session_dir/'proxy-ledger.jsonl')
    summary.update(run_state=state, wall_seconds=round(wall, 3), cost_usd=str(spent),
                   proxy=dict(revoked=revoked, breaches=breaches, **ledger), stopped_by_cap=ledger['cap_refused'])
    if record is not None:
        life = record['manifest']['lifecycle']
        record_dir = repo.state/'sessions'/record['manifest']['id']
        verdicts = record['verdicts']
        drafts = record['drafts']
        summary.update(
            session_id=record['manifest']['id'], record=str(record_dir), session_state=life['state'],
            sandbox=dict(stopped=life.get('stopped'), returncode=life.get('returncode'), survivors=life.get('survivors'),
                         seconds=record['manifest']['provenance'].get('seconds'),
                         peak_memory_bytes=record['manifest']['provenance'].get('peak_memory_bytes')),
            errors=life.get('errors', []), refused=life.get('refused', []),
            submissions=len(verdicts), accepted=sum(1 for v in verdicts if v['accepted']),
            rejected=sum(1 for v in verdicts if not v['accepted']),
            verdicts=[dict(submission=v['submission'], accepted=v['accepted'], version=v['version'],
                           diagnostics=v['diagnostics']) for v in verdicts],
            drafts=dict(created=drafts.get('created', []), renewed=drafts.get('renewed', []),
                        refused=drafts.get('refused', [])),
            published_after=record['published_after'],
            **telemetry(_lines(record_dir/'host-output.log')))
    _write(session_dir/'summary.json', summary)
    return summary


def host_identity(host: dict, model_config: dict) -> dict:
    package = json.loads((HOST_DIR/'package.json').read_text())
    node_version = subprocess.run([str(host['node']), '--version'], capture_output=True, text=True, check=True).stdout.strip()
    return dict(name=package['name'], version=package['version'], schema=HOST_SCHEMA, node=node_version,
                model=model_config['model']['id'], effort=model_config['effort'], max_requests=model_config['max_requests'])


def run_shadow(args: argparse.Namespace, key: str) -> dict:
    spec, names = select(args.lineage, args.sessions)
    runtime = Path(args.runtime_root).resolve()
    out = Path(args.out).resolve()
    if runtime/'curator-shadow' not in out.parents:
        raise ShadowError(f'--out must be inside {runtime/"curator-shadow"}')
    if out.exists():
        raise ShadowError(f'{out} exists; every run writes a fresh directory')
    upstream = args.upstream
    if upstream != OPENROUTER_ORIGIN and not re.fullmatch(r'http://(127\.0\.0\.1|localhost):[0-9]{1,5}', upstream):
        raise ShadowError('--upstream may only be OpenRouter or a local http origin (for tests)')
    evidence = Path(args.evidence_root) if args.evidence_root else runtime/'evidence'
    traces = {}
    for name in names:
        trace = evidence/spec['directory']/'computer-sessions'/name
        if not (trace/'session.sqlite3').is_file():
            raise ShadowError(f'{trace} is not a sealed session')
        traces[name] = trace
    prices = load_prices(Path(args.prices))
    arm = ARMS[args.arm]
    if arm.model not in prices:
        raise ShadowError(f'{arm.model} has no frozen price')
    cap = Decimal(str(args.cap_usd))
    if cap <= 0:
        raise ShadowError('--cap-usd must be positive')
    session_cap = Decimal(str(args.session_cap_usd)) if args.session_cap_usd else None
    host = host_tools()
    model_config = host_configuration(
        arm, prices, effort=args.effort or arm.effort, max_requests=args.max_requests,
        max_output_tokens=args.max_output_tokens, request_timeout_seconds=args.request_timeout_seconds,
        wall_seconds=args.wall_seconds - 30, max_context_images=args.max_context_images,
        context_image_block=args.context_image_block, workbench_timeout_seconds=60, budget_usd=float(cap))
    # Each run starts its own knowledge repository, named by its output directory, so no run can
    # replay a trace against knowledge that later sessions built.
    knowledge = runtime/'knowledge'/'shadow-454'/out.name/args.arm/args.lineage
    if knowledge.exists():
        raise ShadowError(f'{knowledge} exists; every run starts a fresh knowledge repository')
    out.mkdir(parents=True)
    config_dir = out/'host-config'
    config_dir.mkdir()
    config_path = _write(config_dir/f'{args.arm}.json', model_config)
    repo = Repository(knowledge, GAME)
    repo.ensure()
    run = dict(schema=SCHEMA, kind='run', arm=args.arm, model=arm.model, effort=model_config['effort'],
               lineage=args.lineage, sessions_planned=names, cap_usd=str(cap), session_cap_usd=str(session_cap) if session_cap else None,
               upstream=upstream, prices=str(Path(args.prices).relative_to(ROOT)) if Path(args.prices).is_relative_to(ROOT)
               else str(args.prices), knowledge=str(repo.path), host=host_identity(host, model_config),
               started_wall=time.time(), sessions=[], stopped=None)
    spent = Decimal(0)
    for name in names:
        remaining = cap - spent
        if remaining <= 0:
            run['stopped'] = 'cap-reached'
            break
        memory, note = None, 'no sealed per-session memory store for this lineage (the lineage store would carry later sessions)'
        if spec['memory']:
            candidate = evidence/spec['directory']/spec['memory'].format(name=name)
            memory, note = (candidate, 'per-run sealed player-memory/2 store') if candidate.is_file() else (None, 'store absent')
        summary = run_one(arm_name=args.arm, lineage=args.lineage, name=name, trace=traces[name], repo=repo, memory=memory,
                          memory_note=note, host=host, config_path=config_path, config_dir=config_dir, model_config=model_config,
                          prices=prices, key=key, upstream=upstream, cap=min(remaining, session_cap or remaining), out=out,
                          wall_seconds=args.wall_seconds, max_output_tokens=args.max_output_tokens)
        spent += Decimal(summary['cost_usd'])
        run['sessions'].append(dict(trace_session=name, summary=str((out/args.lineage/name/'summary.json').relative_to(out)),
                                    session_state=summary.get('session_state', summary['run_state']), cost_usd=summary['cost_usd'],
                                    accepted=summary.get('accepted'), rejected=summary.get('rejected')))
        print(f'{args.arm} {args.lineage} {name}: {summary.get("session_state", summary["run_state"])}, '
              f'{summary.get("requests")} requests, ${summary["cost_usd"]}, accepted {summary.get("accepted")}, '
              f'rejected {summary.get("rejected")}', flush=True)
        if summary['proxy']['revoked'] or summary['proxy']['breaches']:
            run['stopped'] = 'proxy-revoked'
            break
        if summary['stopped_by_cap'] or cap - spent <= 0:
            run['stopped'] = 'cap-reached'
            break
        if args.stop_on_abort and summary.get('session_state') != 'sealed':
            run['stopped'] = 'session-aborted'
            break
    completed = [s for s in run['sessions']]
    run.update(ended_wall=time.time(), total_cost_usd=str(spent), sessions_run=len(completed),
               published_version=repo.published(), complete=run['stopped'] is None and len(completed) == len(names))
    _write(out/'summary.json', run)
    return run


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--arm', required=True, choices=sorted(ARMS))
    p.add_argument('--lineage', required=True, help='397 (sd1a1..sd1a7) or 372 (aidB3 ceil09 ceil07 ceil05 aidB9 aidA5)')
    p.add_argument('--sessions', nargs='+', help='a subset of the lineage, run in lineage order')
    p.add_argument('--cap-usd', required=True, type=float, help='whole-run dollar cap, enforced by the proxy')
    p.add_argument('--session-cap-usd', type=float, help='optional ceiling for each session (default: what remains)')
    p.add_argument('--out', required=True, help='a new directory under <runtime-root>/curator-shadow/')
    p.add_argument('--prices', default=str(DEFAULT_PRICES))
    p.add_argument('--runtime-root', default=str(ROOT/'.runtime'))
    p.add_argument('--evidence-root', help='default: <runtime-root>/evidence (or ENACTIVE_EVIDENCE_ROOT)')
    p.add_argument('--upstream', default=OPENROUTER_ORIGIN, help='OpenRouter, or a local http origin for tests')
    p.add_argument('--effort', choices=['low', 'medium', 'high', 'xhigh', 'max'], help="default: the arm's frozen effort")
    p.add_argument('--max-requests', type=int, default=120)
    p.add_argument('--max-output-tokens', type=int, default=16384)
    p.add_argument('--request-timeout-seconds', type=int, default=240)
    p.add_argument('--wall-seconds', type=int, default=1800, help='sandbox wall-clock limit for each session')
    # Eviction rewrites the prompt prefix, so it is kept rare: a wide window and a block of half of it.
    # Sixteen of the largest recorded frames stay under the proxy's 8 MiB body limit; 24 would not.
    p.add_argument('--max-context-images', type=int, default=16)
    p.add_argument('--context-image-block', type=int, default=8)
    p.add_argument('--stop-on-abort', action='store_true')
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.evidence_root is None and os.environ.get('ENACTIVE_EVIDENCE_ROOT'):
        args.evidence_root = os.environ['ENACTIVE_EVIDENCE_ROOT']
    try:
        select(args.lineage, args.sessions)  # refuse held-out and unsampled names before anything else
        # The campaign's own resolution: the variable, else the operator's keychain item mapped in
        # the git-ignored .runtime/credentials.json. The value goes only to the proxy.
        # The map lives beside the runtime this run uses, not beside this code: from a worktree,
        # the code's own checkout has no .runtime/credentials.json.
        if args.upstream != OPENROUTER_ORIGIN:
            key = LOOPBACK_KEY  # a local test upstream never receives the operator's key
        else:
            key = credential(KEY_VARIABLE, mapping=Path(args.runtime_root)/'credentials.json')
        if not key:
            raise ShadowError(f'{KEY_VARIABLE} is not set and not mapped to a keychain item (docs/setup.md)')
        run = run_shadow(args, key)
    except (ShadowError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'curator_shadow: {error}', file=sys.stderr)
        return 2
    print(json.dumps({k: run[k] for k in ('arm', 'lineage', 'sessions_run', 'total_cost_usd', 'stopped', 'complete')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
