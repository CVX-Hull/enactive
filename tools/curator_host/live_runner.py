"""The curator runner's process: curator sessions beside a live admission (#845).

The guardian (`tools/campaign_supervision.py --curator-runner CONFIG`) starts it after the
custodian, outside supervision; it can be run by hand the same way:

    python -m tools.curator_host.live_runner --run RUN --directory RUN/curator-runner --config CONFIG

Its rules are `harness.curator.runner`, its design docs/design/live-curator-integration.md. This
module supplies the real parts: the snapshot reader on the live run, a session through the shadow
runner's `run_one` (one `ModelProxy` per session, which reserves spend before each request), the
look at the knowledge repository's tags, and signal handling. SIGTERM or SIGINT interrupts a
session in flight (which seals its own aborted record), closes its proxy and any read, records the
interruption and exits.

The configuration (`curator-runner-config/1`) is one JSON object; only `schema`, `knowledge_root`,
`arm` and `cap_usd` are required:

    {"schema": "curator-runner-config/1",
     "knowledge_root": ".runtime/knowledge/live-845/first-run",   # inside <runtime-root>/knowledge
     "arm": "terra", "cap_usd": "4.00", "session_cap_usd": "0.60",
     "upstream": "https://openrouter.ai", "prices": "data/curator/openrouter-prices-2026-11-08.json",
     "trigger_steps": 20, "ceiling_steps": 40, "poll_seconds": 15, "watch_seconds": 5,
     "host": {"effort": "medium", "max_requests": 120, "max_output_tokens": 16384,
              "request_timeout_seconds": 240, "wall_seconds": 1800, "max_context_images": 16,
              "context_image_block": 8}}

Relative paths are from the project root. The knowledge repository is the configuration's own,
created at `v0` if absent, never the repository's tracked knowledge. `cap_usd` bounds the
runner's counted spend across sessions, restarts included; each session's proxy cap is the
smaller of what remains and `session_cap_usd`. The provider key is resolved as the shadow
runner resolves it, from the environment or the keychain item mapped in
`<runtime-root>/credentials.json`; a loopback upstream gets a fixed test key. The host tools are
resolved when the first session starts, so a runner that never starts one needs none.
Exit status: 0 when the store closed, 1 when the runner stopped for a failure, 2 when it could not
start, 130 when interrupted.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.curator.gate import journal  # noqa: E402
from harness.curator.knowledge import KnowledgeError, Repository  # noqa: E402
from harness.curator.runner import Outcome, Reading, Runner, RunnerError, Settings, TagLook, staged  # noqa: E402
from harness.curator.window import Window  # noqa: E402
from tools.curator_host import shadow  # noqa: E402

CONFIG_SCHEMA = 'curator-runner-config/1'
REQUIRED = {'schema', 'knowledge_root', 'arm', 'cap_usd'}
SETTINGS = ('trigger_steps', 'ceiling_steps', 'poll_seconds', 'watch_seconds')
OPTIONAL = {'session_cap_usd', 'upstream', 'prices', 'host', *SETTINGS}
HOST = ('effort', 'max_requests', 'max_output_tokens', 'request_timeout_seconds', 'wall_seconds',
        'max_context_images', 'context_image_block')
STOPPED, FAILED, INTERRUPTED = 1, 2, 130


class ConfigError(ValueError):
    """The runner's configuration cannot be used."""


def _usd(value: object, name: str) -> Decimal:
    if not isinstance(value, str):
        raise ConfigError(f'{name} is a decimal string')
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ConfigError(f'{name} is a decimal string') from exc
    if not amount.is_finite() or amount <= 0:
        raise ConfigError(f'{name} must be positive')
    return amount


def _path(value: object, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigError(f'{name} is a path')
    path = Path(value)
    return (path if path.is_absolute() else ROOT/path).resolve()


def read_config(path: Path, runtime: Path) -> dict:
    """The validated configuration, with paths resolved and defaults filled in."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ConfigError(f'{path}: unreadable configuration: {exc}') from exc
    if not isinstance(data, dict) or data.get('schema') != CONFIG_SCHEMA:
        raise ConfigError(f'{path}: not a {CONFIG_SCHEMA} file')
    if REQUIRED - data.keys() or data.keys() - REQUIRED - OPTIONAL:
        raise ConfigError(f'{path}: needs {sorted(REQUIRED)}; may have {sorted(OPTIONAL)}')
    knowledge = _path(data['knowledge_root'], 'knowledge_root')
    if Path(runtime).resolve()/'knowledge' not in knowledge.parents:
        raise ConfigError(f'knowledge_root must be inside {Path(runtime).resolve()/"knowledge"}')
    if data['arm'] not in shadow.ARMS:
        raise ConfigError(f'unknown arm {data["arm"]!r}; choose one of {", ".join(sorted(shadow.ARMS))}')
    host = data.get('host', {})
    if not isinstance(host, dict) or host.keys() - set(HOST):
        raise ConfigError(f'host may have {list(HOST)}')
    defaults = shadow.parser()
    host = {name: host.get(name, defaults.get_default(name)) for name in HOST}
    for name in HOST[1:]:
        if type(host[name]) is not int or host[name] < 1:
            raise ConfigError(f'host {name} must be a positive integer')
    if host['effort'] is not None and not isinstance(host['effort'], str):
        raise ConfigError('host effort is a string')
    if host['wall_seconds'] <= 30:
        raise ConfigError('host wall_seconds must exceed 30')
    try:
        settings = Settings(**{name: data[name] for name in SETTINGS if name in data})
        upstream = shadow.checked_upstream(data.get('upstream', shadow.OPENROUTER_ORIGIN))
    except (ValueError, TypeError) as exc:
        raise ConfigError(str(exc)) from exc
    return dict(knowledge_root=knowledge, arm=data['arm'], cap=_usd(data['cap_usd'], 'cap_usd'),
                session_cap=_usd(data['session_cap_usd'], 'session_cap_usd') if 'session_cap_usd' in data else None,
                upstream=upstream,
                prices=_path(data['prices'], 'prices') if 'prices' in data else shadow.DEFAULT_PRICES,
                settings=settings, host=host)


def counted_spend(out: Path) -> Decimal:
    """Every session's spend as its proxy left it, whether or not the session returned: the closing
    snapshot (spent, plus reservations still held, which count as spent) where the proxy closed, else
    the charges in its ledger. A request still in flight when the runner was killed has no ledger row
    and is not counted."""
    total = Decimal(0)
    for session in sorted(p for p in out.glob('*/*') if p.is_dir()):
        try:
            closure = json.loads((session/'proxy-close.json').read_text())
            total += Decimal(closure['spent_snapshot_usd']) + Decimal(closure['pending_reserved_usd'])
            continue
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
            pass
        total += Decimal(shadow._ledger(session/'proxy-ledger.jsonl')['charged_usd'])
    return total


def _host_ran(summary: dict) -> bool:
    """The sandboxed host wrote output, so it was launched."""
    record = summary.get('record')
    log = Path(record)/'host-output.log' if record else None
    return log is not None and log.is_file() and log.stat().st_size > 0


class Sessions:
    """The session call: one `shadow.run_one` per window, each through its own proxy under what remains of the cap."""

    def __init__(self, directory: Path, config: dict, repo: Repository, key: str):
        self.out, self.config, self.repo, self.key = directory/'sessions', config, repo, key
        self.config_dir = directory/'host-config'
        self.prices = shadow.load_prices(config['prices'])
        if shadow.ARMS[config['arm']].model not in self.prices:
            raise ConfigError(f'{shadow.ARMS[config["arm"]].model} has no frozen price')
        self.tools = self.model_config = self.config_path = None
        # Spend counted by earlier runs of this runner for the same admission counts against the cap.
        self.spent = counted_spend(self.out)

    def _host(self) -> None:
        host = self.config['host']
        self.tools = shadow.host_tools()
        self.model_config = shadow.host_configuration(
            shadow.ARMS[self.config['arm']], self.prices, effort=host['effort'] or shadow.ARMS[self.config['arm']].effort,
            max_requests=host['max_requests'], max_output_tokens=host['max_output_tokens'],
            request_timeout_seconds=host['request_timeout_seconds'], wall_seconds=host['wall_seconds'] - 30,
            max_context_images=host['max_context_images'], context_image_block=host['context_image_block'],
            workbench_timeout_seconds=60, budget_usd=float(self.config['cap']))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = shadow._write(self.config_dir/f'{self.config["arm"]}.json', self.model_config)

    def __call__(self, read: Reading, window: Window, label: str) -> Outcome:
        remaining = self.config['cap'] - self.spent
        if remaining <= 0:
            return Outcome(state=None, stop='cap-reached')
        if self.tools is None:
            try:
                self._host()
            except (shadow.ShadowError, OSError, subprocess.CalledProcessError) as exc:
                return Outcome(state=None, stop=f'host-unavailable: {exc}')
        try:
            summary = shadow.run_one(
                arm_name=self.config['arm'], lineage=read.directory.name, name=label, trace=read.directory,
                repo=self.repo, memory=None, memory_note='a window never reads the sealed memory store',
                host=self.tools, config_path=self.config_path, config_dir=self.config_dir,
                model_config=self.model_config, prices=self.prices, key=self.key, upstream=self.config['upstream'],
                cap=min(remaining, self.config['session_cap'] or remaining), out=self.out,
                wall_seconds=self.config['host']['wall_seconds'],
                max_output_tokens=self.config['host']['max_output_tokens'], window=window)
        finally:
            # Counted from what the proxy left, also for a session cut short or whose proxy close failed.
            self.spent = counted_spend(self.out)
        proxy = summary['proxy']
        stop = None
        if proxy.get('revoked') or proxy.get('breaches'):
            stop = 'proxy-revoked'
        elif summary['stopped_by_cap']:
            stop = 'spend-reservation-refused'
        elif self.config['cap'] - self.spent <= 0:
            stop = 'cap-reached'
        elif not proxy.get('settled', True):
            stop = 'proxy-unsettled'
        elif 'session_id' in summary and (summary.get('sandbox', {}).get('survivors')
                                          or (summary.get('sandbox', {}).get('survivors') is None and _host_ran(summary))):
            # Host processes survived, or the host ran and the sandbox's result is missing. A session that
            # aborted before its host ran is an ordinary failed session.
            stop = 'cleanup-unconfirmed'
        details = dict(cost_usd=summary['cost_usd'], summary=str(self.out/read.directory.name/label/'summary.json'))
        error = summary['run_state'] if summary['run_state'] != 'completed' else None
        if 'session_id' not in summary and error and error.startswith('error: SessionError:'):
            # run_session raises SessionError only when the repository lock refuses a second session.
            return Outcome(state=None, refused=True, stop=stop, error=error, details=details)
        return Outcome(state=summary.get('session_state'), verdicts=tuple(summary.get('verdicts', ())),
                       session_id=summary.get('session_id'), stop=stop, error=error, details=details)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--run', required=True, type=Path, help='the live run directory')
    p.add_argument('--directory', required=True, type=Path, help="the runner's own directory")
    p.add_argument('--config', required=True, type=Path, help='a curator-runner-config/1 file')
    p.add_argument('--runtime-root', type=Path, default=ROOT/'.runtime')
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    interrupted = []

    def interrupt(signum, frame):
        if interrupted:
            return  # the first signal is being handled; the guardian's later ones must not cut its cleanup
        interrupted.append(signal.Signals(signum).name)
        raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupt)
    try:
        try:
            run = args.run.resolve(strict=True)
            config = read_config(args.config, args.runtime_root)
            repo = Repository(config['knowledge_root'], shadow.GAME)
            journal(repo)
            repo.ensure()
            key = shadow.route_key(config['upstream'], args.runtime_root)
            if not key:
                raise ConfigError(f'{shadow.KEY_VARIABLE} is not set and not mapped to a keychain item (docs/setup.md)')
            directory = args.directory.resolve()
            runner = Runner(directory, run.name, snapshot=staged(run), session_call=Sessions(directory, config, repo, key),
                            look=TagLook(repo), settings=config['settings'], run=run)
        except (ConfigError, RunnerError, KnowledgeError, shadow.ShadowError, OSError, ValueError) as error:
            print(f'curator_runner: {error}', file=sys.stderr)
            return FAILED
        reason = runner.run()
    except KeyboardInterrupt:
        print(f'curator_runner: interrupted ({", ".join(interrupted) or "KeyboardInterrupt"})', file=sys.stderr)
        return INTERRUPTED
    print(f'curator_runner: {runner.state}: {reason}', flush=True)
    return 0 if runner.state == 'ended' else STOPPED


if __name__ == '__main__':
    raise SystemExit(main())
