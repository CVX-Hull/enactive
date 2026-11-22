"""Groom the last published admission of a live curator repository using its sealed run."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import subprocess
import sys

from harness.curator.knowledge import Repository
from harness.curator.window import Window
from harness.trace.stores import sealed
from tools.curator_host import live_runner, shadow

SCHEMA = 'curator-boundary-grooming/1'
SUMMARY = 'grooming-summary.json'


def failure_reason(summary: dict) -> str | None:
    if summary['run_state'] != 'completed':
        return summary['run_state']
    if summary.get('unresolved'):
        return 'unresolved-result'
    proxy = summary['proxy']
    if proxy.get('settled') is not True:
        return 'proxy-unsettled'
    if proxy.get('revoked') or proxy.get('breaches') != 0:
        return 'proxy-revoked-or-breached'
    if summary.get('stopped_by_cap'):
        return 'cap-reached'
    if summary.get('session_state') != 'sealed':
        return 'session-not-sealed'
    if summary.get('sandbox', {}).get('survivors') != []:
        return 'cleanup-unconfirmed'
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path, help='the sealed run directory')
    parser.add_argument('--config', required=True, type=Path, help='the admission’s curator-runner-config/1 file')
    parser.add_argument('--out', required=True, type=Path, help='a fresh directory inside the runtime root')
    parser.add_argument('--cap-usd', help='a positive decimal dollar cap for this grooming session')
    parser.add_argument('--runtime-root', type=Path, default=live_runner.ROOT/'.runtime')
    args = parser.parse_args(argv)

    try:
        run = args.run.resolve(strict=True)
        with sealed(run/'session.sqlite3') as db:
            # SQLite opens lazily. Read the schema to detect an unreadable database before resolving the host.
            db.execute('PRAGMA schema_version').fetchone()
        config = live_runner.read_config(args.config, args.runtime_root)
        cap = (live_runner._usd(args.cap_usd, '--cap-usd') if args.cap_usd is not None
               else config['session_cap'] or config['cap'])
        runtime = args.runtime_root.resolve()
        out = args.out.resolve()
        if runtime not in out.parents:
            raise ValueError(f'--out must be inside {runtime}')
        if out.is_relative_to(run):
            raise ValueError('--out must be outside --run')
        if out.exists() or args.out.is_symlink():
            raise ValueError(f'{args.out} exists; grooming needs a fresh output directory')

        repo = Repository(config['knowledge_root'], shadow.GAME)
        if not (repo.path/'.git').exists():
            raise ValueError(f'{repo.path}: grooming needs an existing knowledge repository')
        if out.is_relative_to(repo.path.resolve()):
            raise ValueError('--out must be outside the knowledge worktree, which the gate cleans on publication')
        shadow.journal(repo)
        before = repo.published()
        last_admission = repo.provenance(before).get('last_admission')
        report = dict(schema=SCHEMA, run=run.name, knowledge_root=str(config['knowledge_root']), published_before=before)
        if last_admission is None:
            out.mkdir(parents=True)
            shadow._write(out/SUMMARY, dict(report, status='skipped', reason='no-published-admission',
                                            published_after=before, cost_usd='0', summary=None))
            print(f'curator_groom: skipped {run.name}: no published admission')
            return 0

        admitted_run = last_admission['coverage']['session']
        if admitted_run != run.name:
            raise ValueError(f'{run.name!r} is not the last published admission ({admitted_run!r})')
        key = shadow.route_key(config['upstream'], args.runtime_root)
        if not key:
            raise ValueError(f'{shadow.KEY_VARIABLE} is not set and not mapped to a keychain item (docs/setup.md)')
        prices = shadow.load_prices(config['prices'])
        arm = config['arm']
        if (model := shadow.ARMS[arm].model) not in prices:
            raise ValueError(f'{model} has no frozen price')
        model_config = live_runner.session_host_configuration(config, prices, cap)
        host = shadow.host_tools()
        out.mkdir(parents=True)
        config_dir = out/'host-config'
        config_path = shadow._write(config_dir/f'{arm}.json', model_config)
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f'curator_groom: {exc}', file=sys.stderr)
        return 2

    lineage, name = 'boundary', f'groom-{run.name}'
    summary_path = Path(lineage)/name/'summary.json'
    try:
        summary = shadow.run_one(
            arm_name=arm, lineage=lineage, name=name, trace=run, repo=repo, memory=None, memory_note='',
            host=host, config_path=config_path, config_dir=config_dir, model_config=model_config, prices=prices,
            key=key, upstream=config['upstream'], cap=cap, out=out, wall_seconds=config['host']['wall_seconds'],
            max_output_tokens=config['host']['max_output_tokens'], window=Window(), session_kind='grooming')
    except (OSError, ValueError, RuntimeError) as exc:
        # The session summary may be unavailable after a proxy startup or close failure.
        summary = dict(run_state=f'error: {type(exc).__name__}: {exc}')
        summary_path = None

    reason = failure_reason(summary)
    status = 'completed' if reason is None else 'failed'
    if 'published_after' in summary:
        after = summary['published_after']
    else:
        try:
            after = repo.published()
        except (OSError, ValueError):
            after = None
    try:
        shadow._write(out/SUMMARY, dict(
            report, status=status, reason=reason, cap_usd=str(cap), published_after=after,
            cost_usd=summary.get('cost_usd'), session_state=summary.get('session_state'),
            verdicts=summary.get('verdicts', []), proxy=summary.get('proxy'), sandbox=summary.get('sandbox'),
            summary=summary_path.as_posix() if summary_path else None))
    except (OSError, ValueError) as exc:
        print(f'curator_groom: could not write {out/SUMMARY}: {exc}', file=sys.stderr)
        return 1
    if reason is not None:
        print(f'curator_groom: failed {run.name}: {reason}', file=sys.stderr)
        return 1
    detail = f'{before} -> {after}' if after != before else f'{before} (no new version published)'
    print(f'curator_groom: completed {run.name}: {detail}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
