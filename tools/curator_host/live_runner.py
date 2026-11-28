"""The curator runner's process: curator sessions beside a live admission (#845).

The guardian (`tools/campaign_supervision.py --curator-runner CONFIG`) starts it after the
custodian, outside supervision; it can be run by hand the same way:

    python -m tools.curator_host.live_runner --run RUN --directory RUN/curator-runner --config CONFIG

Its rules are `harness.curator.runner`, its component docs/components/curator.md. This
module supplies the real parts: the snapshot reader on the live run, a session through the shadow
runner's `run_one` (one `ModelProxy` per session, which reserves spend before each request), the
look at the knowledge repository's tags, and signal handling. SIGTERM or SIGINT interrupts a
session in flight (which seals its own aborted record), closes its proxy and any read, records the
interruption and exits.

The configuration (`curator-runner-config/2`) is one JSON object; only `schema`, `knowledge_root`,
`arm` and `cap_usd` are required:

    {"schema": "curator-runner-config/2",
     "knowledge_root": ".runtime/knowledge/live-845/first-run",   # inside <runtime-root>/knowledge
     "arm": "terra", "cap_usd": "4.00", "session_cap_usd": "0.60", "service_tier": "flex",
     "upstream": "https://openrouter.ai", "prices": "data/curator/openrouter-prices-2026-11-08.json",
     "trigger_steps": 40, "ceiling_steps": 60, "poll_seconds": 15, "watch_seconds": 5,
     "hygiene": {"enabled": true, "min_windows": 5, "max_unexamined_steps": 10,
                 "pass_cap_usd": "0.30", "max_spend_share": "0.10",
                 "max_requests": 10, "wall_seconds": 90, "max_consecutive_failures": 2},
     "host": {"effort": "medium", "max_requests": 120, "max_output_tokens": 16384,
              "request_timeout_seconds": 240, "wall_seconds": 1800, "max_context_images": 16}}

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
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.curator import hygiene as curator_hygiene  # noqa: E402
from harness.curator.gate import journal  # noqa: E402
from harness.curator.knowledge import KnowledgeError, Repository  # noqa: E402
from harness.curator.runner import (  # noqa: E402
    FLEX_DEFERRED,
    HYGIENE_SUBCAP_EXHAUSTED,
    SPEND_EXHAUSTED,
    SPEND_REFUSED,
    HygieneSettings,
    Outcome,
    Reading,
    Runner,
    RunnerError,
    Settings,
    TagLook,
    staged,
)
from harness.curator.session import FLEX_DEFERRED_EXIT_CODE  # noqa: E402
from harness.curator.window import Window  # noqa: E402
from harness.evaluation.core.sources import MANIFEST_SCHEMA  # noqa: E402
from harness.trace.projection import valid_context  # noqa: E402
from tools import knowledge_export  # noqa: E402
from tools.campaign_package import DELIVERED_DIRECTORY  # noqa: E402
from tools.curator_host import shadow  # noqa: E402

CONFIG_SCHEMA = 'curator-runner-config/2'
REQUIRED = {'schema', 'knowledge_root', 'arm', 'cap_usd'}
SETTINGS = ('trigger_steps', 'ceiling_steps', 'poll_seconds', 'watch_seconds')
OPTIONAL = {'session_cap_usd', 'service_tier', 'provider', 'hygiene', 'upstream', 'prices', 'host', *SETTINGS}
HOST = ('effort', 'max_requests', 'max_output_tokens', 'request_timeout_seconds', 'wall_seconds',
        'max_context_images')
HYGIENE_FIELDS = ('enabled', 'min_windows', 'max_unexamined_steps', 'pass_cap_usd', 'max_spend_share',
                  'max_requests', 'wall_seconds', 'max_consecutive_failures')
FLEX_DEFAULT_TIMEOUT_SECONDS = 960
MAX_REQUEST_TIMEOUT_SECONDS = 1800
PREFLIGHT_MIN_PROMPT_TOKENS = 1024
STOPPED, FAILED, INTERRUPTED = 1, 2, 130


class ConfigError(ValueError):
    """The runner's configuration cannot be used."""


def _usd(value: object, name: str, *, allow_zero: bool = False) -> Decimal:
    if not isinstance(value, str):
        raise ConfigError(f'{name} is a decimal string')
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ConfigError(f'{name} is a decimal string') from exc
    if not amount.is_finite() or (amount < 0 if allow_zero else amount <= 0):
        raise ConfigError(f'{name} must be {"non-negative" if allow_zero else "positive"}')
    return amount


def _path(value: object, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigError(f'{name} is a path')
    path = Path(value)
    return (path if path.is_absolute() else ROOT/path).resolve()


def _hygiene_settings(raw: object) -> HygieneSettings:
    if raw is None:
        return HygieneSettings()
    if not isinstance(raw, dict) or raw.keys() - set(HYGIENE_FIELDS):
        raise ConfigError(f'hygiene may have {list(HYGIENE_FIELDS)}')
    kwargs: dict = {}
    for key in ('enabled', 'min_windows', 'max_unexamined_steps', 'max_requests', 'wall_seconds', 'max_consecutive_failures'):
        if key in raw:
            kwargs[key] = raw[key]
    if 'pass_cap_usd' in raw:
        kwargs['pass_cap_usd'] = _usd(raw['pass_cap_usd'], 'hygiene.pass_cap_usd')
    if 'max_spend_share' in raw:
        kwargs['max_spend_share'] = _usd(raw['max_spend_share'], 'hygiene.max_spend_share', allow_zero=True)
    try:
        return HygieneSettings(**kwargs)
    except (ValueError, TypeError) as exc:
        raise ConfigError(str(exc)) from exc


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
    arm = shadow.ARMS[data['arm']]
    service_tier = data.get('service_tier', 'flex' if arm.flex_provider else 'default')
    if not isinstance(service_tier, str) or service_tier not in shadow.SERVICE_TIERS:
        raise ConfigError(f'service_tier must be one of {", ".join(shadow.SERVICE_TIERS)}')
    provider = data.get('provider')
    if provider is not None and (not isinstance(provider, str) or not provider.strip()):
        raise ConfigError('provider must be a non-empty string')
    host_raw = data.get('host', {})
    if not isinstance(host_raw, dict) or host_raw.keys() - set(HOST):
        raise ConfigError(f'host may have {list(HOST)}')
    defaults = shadow.parser()
    host = {name: host_raw.get(name, defaults.get_default(name)) for name in HOST}
    if service_tier == 'flex' and 'request_timeout_seconds' not in host_raw:
        host['request_timeout_seconds'] = max(host['request_timeout_seconds'], FLEX_DEFAULT_TIMEOUT_SECONDS)
    for name in HOST[1:]:
        if type(host[name]) is not int or host[name] < 1:
            raise ConfigError(f'host {name} must be a positive integer')
    if host['request_timeout_seconds'] > MAX_REQUEST_TIMEOUT_SECONDS:
        raise ConfigError(f'host request_timeout_seconds must not exceed {MAX_REQUEST_TIMEOUT_SECONDS}')
    if host['effort'] is not None and not isinstance(host['effort'], str):
        raise ConfigError('host effort is a string')
    if host['wall_seconds'] <= 30:
        raise ConfigError('host wall_seconds must exceed 30')
    hygiene = _hygiene_settings(data.get('hygiene'))
    try:
        settings = Settings(**{name: data[name] for name in SETTINGS if name in data})
        upstream = shadow.checked_upstream(data.get('upstream', shadow.OPENROUTER_ORIGIN))
    except (ValueError, TypeError) as exc:
        raise ConfigError(str(exc)) from exc
    return dict(knowledge_root=knowledge, arm=data['arm'], cap=_usd(data['cap_usd'], 'cap_usd'),
                session_cap=_usd(data['session_cap_usd'], 'session_cap_usd') if 'session_cap_usd' in data else None,
                service_tier=service_tier, provider=provider, hygiene=hygiene, upstream=upstream,
                prices=_path(data['prices'], 'prices') if 'prices' in data else shadow.DEFAULT_PRICES,
                settings=settings, host=host)


def _session_spend(session: Path) -> Decimal:
    try:
        closure = json.loads((session/'proxy-close.json').read_text())
        if closure.get('receipt_error') is None:
            return Decimal(closure['spent_snapshot_usd']) + Decimal(closure['pending_reserved_usd'])
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
        pass
    start = session/'proxy-start.json'
    if start.is_file():
        return _usd(json.loads(start.read_text())['cap_usd'], 'recorded session cap')
    return Decimal(shadow._ledger(session/'proxy-ledger.jsonl')['charged_usd'])


def counted_spend(out: Path, *, lineage: str | None = None) -> Decimal:
    """Every session's spend as its proxy left it, whether or not the session returned: the closing
    snapshot (spent plus reservations still held) where the proxy closed, else the entire
    session cap. Ledgers from sessions with no recorded start contain only known charges."""
    pattern = f'{lineage}/*' if lineage is not None else '*/*'
    return sum((_session_spend(session) for session in sorted(p for p in out.glob(pattern) if p.is_dir())), Decimal(0))


def session_host_configuration(config: dict, prices: dict, cap: Decimal, *,
                               text_only: bool = False, max_requests: int | None = None,
                               wall_seconds: int | None = None) -> dict:
    """Freeze host settings from a runner configuration for admission, hygiene or boundary grooming."""
    host = config['host']
    arm = shadow.ARMS[config['arm']]
    effective_wall = wall_seconds if wall_seconds is not None else host['wall_seconds']
    return shadow.host_configuration(
        arm, prices, effort=host['effort'] or arm.effort,
        max_requests=max_requests if max_requests is not None else host['max_requests'],
        max_output_tokens=host['max_output_tokens'],
        request_timeout_seconds=host['request_timeout_seconds'], wall_seconds=effective_wall - 30,
        max_context_images=0 if text_only else host['max_context_images'],
        workbench_timeout_seconds=60, budget_usd=float(cap),
        service_tier=config.get('service_tier', 'flex' if arm.flex_provider else 'default'), text_only=text_only,
        provider=config.get('provider'))


def _host_ran(summary: dict) -> bool:
    """The sandboxed host wrote output, so it was launched."""
    record = summary.get('record')
    log = Path(record)/'host-output.log' if record else None
    return log is not None and log.is_file() and log.stat().st_size > 0


def _min_session_headroom(prices: dict, arm_name: str, max_output_tokens: int) -> Decimal:
    """Worst-case reservation floor for a single minimal request on the configured arm."""
    return prices[shadow.ARMS[arm_name].model].reservation(PREFLIGHT_MIN_PROMPT_TOKENS, max_output_tokens)


def _flex_deferred(summary: dict) -> bool:
    return (summary.get('sandbox', {}).get('returncode') == FLEX_DEFERRED_EXIT_CODE
            or (summary.get('host_end') or {}).get('reason') == FLEX_DEFERRED)


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
        self.tools = shadow.host_tools()
        self.model_config = session_host_configuration(self.config, self.prices, self.config['cap'])
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = shadow._write(self.config_dir/f'{self.config["arm"]}.json', self.model_config)

    def min_headroom(self) -> Decimal:
        return _min_session_headroom(self.prices, self.config['arm'], self.config['host']['max_output_tokens'])

    def __call__(self, read: Reading, window: Window, label: str) -> Outcome:
        self.spent = counted_spend(self.out)
        remaining = self.config['cap'] - self.spent
        min_headroom = self.min_headroom()
        if remaining <= 0 or remaining < min_headroom:
            return Outcome(state=None, stop=SPEND_EXHAUSTED)
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
        elif not proxy.get('settled', True):
            stop = 'proxy-unsettled'
        elif 'session_id' in summary and (summary.get('sandbox', {}).get('survivors')
                                          or (summary.get('sandbox', {}).get('survivors') is None and _host_ran(summary))):
            # Host processes survived, or the host ran and the sandbox's result is missing. A session that
            # aborted before its host ran is an ordinary failed session.
            stop = 'cleanup-unconfirmed'
        elif self.config['cap'] - self.spent < min_headroom:
            stop = SPEND_EXHAUSTED
        elif summary['stopped_by_cap']:
            stop = SPEND_REFUSED
        elif _flex_deferred(summary):
            stop = FLEX_DEFERRED
        details = dict(cost_usd=summary['cost_usd'], summary=str(self.out/read.directory.name/label/'summary.json'))
        error = summary['run_state'] if summary['run_state'] != 'completed' else None
        provider_error = summary.get('sandbox', {}).get('stopped') == 'provider-error'
        if 'session_id' not in summary and error and error.startswith('error: SessionError:'):
            # run_session raises SessionError only when the repository lock refuses a second session.
            return Outcome(state=None, refused=True, stop=stop, error=error, details=details,
                           provider_error=provider_error)
        return Outcome(state=summary.get('session_state'), verdicts=tuple(summary.get('verdicts', ())),
                       session_id=summary.get('session_id'), stop=stop, error=error, details=details,
                       provider_error=provider_error)


class HygieneSessions:
    """Interleaved text-only hygiene pass callable with strict spend sub-caps and zero image tools."""

    LINEAGE = 'hygiene'

    def __init__(self, directory: Path, config: dict, repo: Repository, key: str, *, sessions: Sessions | None = None):
        self.out, self.config, self.repo, self.key = directory/'sessions', config, repo, key
        self.config_dir = directory/'host-config'
        self.sessions = sessions
        self.prices = sessions.prices if sessions is not None else shadow.load_prices(config['prices'])
        self.tools = self.model_config = self.config_path = None

    def _host(self) -> None:
        self.tools = self.sessions.tools if (self.sessions is not None and self.sessions.tools is not None) else shadow.host_tools()
        hs: HygieneSettings = self.config['hygiene']
        self.model_config = session_host_configuration(
            self.config, self.prices, hs.pass_cap_usd,
            text_only=True, max_requests=hs.max_requests, wall_seconds=hs.wall_seconds)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = shadow._write(self.config_dir/f'{self.config["arm"]}-hygiene.json', self.model_config)

    def min_headroom(self) -> Decimal:
        return _min_session_headroom(self.prices, self.config['arm'], self.config['host']['max_output_tokens'])

    def pass_cap(self) -> Decimal:
        """Maximum spend allowed for the next hygiene pass under $0.30/pass and <= 10% cumulative runner spend."""
        hs: HygieneSettings = self.config['hygiene']
        total_spent = counted_spend(self.out)
        total_remaining = self.config['cap'] - total_spent
        hygiene_spent = counted_spend(self.out, lineage=self.LINEAGE)
        max_hygiene_total = min(self.config['cap'] * hs.max_spend_share, total_spent * hs.max_spend_share)
        share_remaining = max_hygiene_total - hygiene_spent
        return min(hs.pass_cap_usd, share_remaining, total_remaining)

    def available(self) -> bool:
        cap = self.pass_cap()
        return cap > 0 and cap >= self.min_headroom()

    def __call__(self, read: Reading, label: str) -> Outcome:
        hs: HygieneSettings = self.config['hygiene']
        pass_cap = self.pass_cap()
        if pass_cap <= 0 or pass_cap < self.min_headroom():
            return Outcome(state=None, stop=HYGIENE_SUBCAP_EXHAUSTED)
        if self.tools is None:
            try:
                self._host()
            except (shadow.ShadowError, OSError, subprocess.CalledProcessError) as exc:
                return Outcome(state=None, stop=f'host-unavailable: {exc}')
        try:
            summary = shadow.run_one(
                arm_name=self.config['arm'], lineage=self.LINEAGE, name=label, trace=read.directory,
                repo=self.repo, memory=None, memory_note='hygiene is text-only over published records',
                host=self.tools, config_path=self.config_path, config_dir=self.config_dir,
                model_config=self.model_config, prices=self.prices, key=self.key, upstream=self.config['upstream'],
                cap=pass_cap, out=self.out, wall_seconds=hs.wall_seconds,
                max_output_tokens=self.config['host']['max_output_tokens'], window=Window(), session_kind='hygiene')
        finally:
            if self.sessions is not None:
                self.sessions.spent = counted_spend(self.out)
        proxy = summary['proxy']
        stop = None
        if proxy.get('revoked') or proxy.get('breaches'):
            stop = 'proxy-revoked'
        elif not proxy.get('settled', True):
            stop = 'proxy-unsettled'
        elif 'session_id' in summary and (summary.get('sandbox', {}).get('survivors')
                                          or (summary.get('sandbox', {}).get('survivors') is None and _host_ran(summary))):
            stop = 'cleanup-unconfirmed'
        elif summary['stopped_by_cap']:
            stop = SPEND_REFUSED
        elif _flex_deferred(summary):
            stop = FLEX_DEFERRED
        details = dict(cost_usd=summary['cost_usd'], summary=str(self.out/self.LINEAGE/label/'summary.json'))
        error = summary['run_state'] if summary['run_state'] != 'completed' else None
        provider_error = summary.get('sandbox', {}).get('stopped') == 'provider-error'
        if 'session_id' not in summary and error and error.startswith('error: SessionError:'):
            return Outcome(state=None, refused=True, stop=stop, error=error, details=details,
                           provider_error=provider_error)
        return Outcome(state=summary.get('session_state'), verdicts=tuple(summary.get('verdicts', ())),
                       session_id=summary.get('session_id'), stop=stop, error=error, details=details,
                       provider_error=provider_error)


VERSION_FILE = re.compile(r'v(0|[1-9][0-9]*)\.json')
SESSION_ID_RE = re.compile(r'[0-9a-f]{32}')
COVERED_PREFIX_FILE = 'covered-prefix.json'
COVERED_PREFIX_SCHEMA = 'curator-covered-prefix/1'


def delivery_target(run: Path, *, session_id: str | None = None) -> tuple[bool, str | None, str | None, dict, str]:
    """Whether the package delivers newer versions, its selection target, and the session ID.

    The manifest is trusted only as the supervisor launched it: its bytes must have the SHA-256 that the
    supervisor's `campaign-watch-start/4` launch record names for the same 32-hex session (and matching any
    explicitly supplied `session_id`), the checks the trace projection makes before it reads labels
    (`harness/trace/projection.py`). The bytes checked are the bytes read."""
    data = (run/'manifest.json').read_bytes()
    manifest = json.loads(data)
    if not isinstance(manifest, dict) or manifest.get('schema') != MANIFEST_SCHEMA:
        raise ValueError(f'{run/"manifest.json"}: not a {MANIFEST_SCHEMA} manifest')
    session = manifest.get('session')
    if not isinstance(session, str) or not SESSION_ID_RE.fullmatch(session):
        raise ValueError(f'{run/"manifest.json"}: missing or invalid session identifier')
    opening = json.loads((run/'watch-start.json').read_bytes())
    if not isinstance(opening, dict) or opening.get('schema') != 'campaign-watch-start/4':
        raise ValueError(f'{run/"watch-start.json"}: unsupported supervisor launch record schema')
    if opening.get('session') != session:
        raise ValueError(f'{run/"watch-start.json"}: supervisor launch record session differs from the manifest session')
    if session_id is not None and session != session_id:
        raise ValueError(f'{run/"manifest.json"}: manifest session differs from the launched session')
    if opening.get('manifest_sha256') != hashlib.sha256(data).hexdigest():
        raise ValueError(f'{run/"manifest.json"}: SHA-256 differs from the supervisor launch record')
    if not valid_context(manifest.get('context')):
        raise ValueError(f'{run/"manifest.json"}: missing or invalid context axes')
    world, lineage, context = knowledge_export.target_labels(
        manifest['labels']['world'], manifest['labels']['lineage'], manifest['context'])
    return manifest['live_knowledge_updates'] is True, world, lineage, context, session


class Delivery:
    """Leaves confirmed versions and the unbroken covered prefix in `<runner directory>/delivered/`.

    The file is the version exported as `delivered-knowledge/4` for the package's target
    (`tools.knowledge_export.published`), written whole to a temporary name, synced and renamed, so the
    driver only ever sees a complete file. Only a version the runner has confirmed in this admission is
    exported (its tag was seen, an examined session reports it and its stamp is that window), never a
    restore, and only one above the last version exported, restarts included. A failed export is reported
    on stderr once per version and error and tried again at the next poll; it never ends the runner.
    """

    def __init__(self, directory: Path, repository: Path, world: str | None, session: str | None = None,
                 *, lineage: str | None = None, context: dict | None = None):
        self.directory, self.repository, self.world = Path(directory)/DELIVERED_DIRECTORY, repository, world
        self.lineage, self.context = lineage, context
        self.session = session
        self.actor_ids: dict[str, str] = {}
        self.last_prefix = None
        present = os.listdir(self.directory) if self.directory.is_dir() else []
        self.last = max((int(m[1]) for name in present if (m := VERSION_FILE.fullmatch(name))), default=-1)
        self.reported: dict[str, str] = {}

    def _write(self, name: str, value: dict) -> None:
        data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
        self.directory.mkdir(mode=0o700, exist_ok=True)
        temporary = self.directory/f'.{name}.tmp'
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.directory/name)

    def _report(self, name: str, exc: Exception) -> None:
        report = f'{type(exc).__name__}: {str(exc)[:300]}'
        if report != self.reported.get(name):
            self.reported[name] = report
            print(f'curator_runner: delivery of {name} failed: {report}', file=sys.stderr, flush=True)

    def __call__(self, runner: Runner) -> None:
        version = 'a confirmed version'
        try:
            with runner.lock:
                confirmed, _, _ = runner.publications()
                candidates = [int(c['version'][1:]) for c in confirmed
                              if runner.versions[c['version']]['restored_from'] is None]
                candidates.extend(int(v[1:]) for v in getattr(runner, 'hygiene_publications', lambda: [])())
                number = max(candidates, default=-1)
            if number > self.last:
                version = f'v{number}'
                self._write(f'{version}.json', knowledge_export.published(
                    self.repository, version, world=self.world, lineage=self.lineage, context=self.context))
                self.last = number
        except Exception as exc:  # noqa: BLE001 - delivery is beside curation: reported, retried, never fatal
            self._report(version, exc)

        try:
            prefix = self._prefix(runner)
            if prefix is not None and prefix != self.last_prefix:
                if prefix['restored'] or (self.directory/f"{prefix['version']}.json").is_file():
                    self._write(COVERED_PREFIX_FILE, prefix)
                    self.last_prefix = prefix
        except Exception as exc:  # noqa: BLE001 - delivery is beside curation: reported, retried, never fatal
            self._report(COVERED_PREFIX_FILE, exc)

    def _prefix(self, runner: Runner) -> dict | None:
        if self.session is None or not SESSION_ID_RE.fullmatch(self.session):
            return None
        with runner.lock:
            if runner.last is not None:
                self.actor_ids.update((a.directory, a.actor_id) for a in runner.last.actors if a.actor_id is not None)
            confirmed, _, restore = runner.publications()
            if restore is not None:
                return dict(schema=COVERED_PREFIX_SCHEMA, session=self.session, actor=None, actor_id=None,
                            operation_id=None, version=None, restored=True)
            end = runner.coverage()['covered_prefix']['end']
        if end is None or end['operation'] == 'unknown':
            return None
        actor_id = self.actor_ids.get(end['actor'])
        if actor_id is None or not SESSION_ID_RE.fullmatch(actor_id) or not SESSION_ID_RE.fullmatch(end['operation']):
            return None
        version = next((c['version'] for c in reversed(confirmed)
                        if (c['window']['actor'], c['window']['last']) == (end['actor'], end['step'])), None)
        if version is None or int(version[1:]) > self.last:
            return None
        return dict(schema=COVERED_PREFIX_SCHEMA, session=self.session, actor=end['actor'], actor_id=actor_id,
                    operation_id=end['operation'], version=version, restored=False)


class DeliveringRunner(Runner):
    """The runner, with one look for a newly confirmed version to deliver after each poll that returned."""

    def __init__(self, *args, deliver: Delivery | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.deliver = deliver

    def poll(self) -> bool:
        more = super().poll()
        if self.deliver is not None:
            self.deliver(self)
        return more


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--run', required=True, type=Path, help='the live run directory')
    p.add_argument('--directory', required=True, type=Path, help="the runner's own directory")
    p.add_argument('--config', required=True, type=Path, help='a curator-runner-config/2 file')
    p.add_argument('--session', default=None, help='expected 32-hex live session id verified by supervision')
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
            deliver = None
            try:
                enabled, world, lineage, context, session = delivery_target(run, session_id=args.session)
                if enabled:
                    deliver = Delivery(directory, repo.path, world, session=session, lineage=lineage, context=context)
            except (OSError, ValueError, KeyError, TypeError) as error:
                # Curation does not depend on delivery: the runner starts and leaves no version for the driver.
                print(f'curator_runner: delivery to the running actor is off: {type(error).__name__}: {error}',
                      file=sys.stderr, flush=True)
            sessions = Sessions(directory, config, repo, key)
            hygiene_sessions = HygieneSessions(directory, config, repo, key, sessions=sessions)
            runner = DeliveringRunner(
                directory, run.name, snapshot=staged(run), session_call=sessions,
                hygiene_call=hygiene_sessions,
                hygiene_check=lambda: curator_hygiene.hygiene_trigger(repo.records()),
                hygiene_settings=config['hygiene'],
                look=TagLook(repo), settings=config['settings'], run=run, deliver=deliver)
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
