#!/usr/bin/env python3
"""Engineering probe: replay recorded level-pass contexts through the real level host and model route (#341).

Each recorded pass of a recorded campaign session is replayed N times against a fresh, read-only
replay of that session's operations and sources as they stood when the pass started:

1. a new `computer-session/2` store receives the session's first `log_entries` operations and the frames
   they cite, through the store API (as `tools/level_offline.py` does), with a stub channel that cannot play;
2. a reader is minted through `Application` on that replay and served through the normal player HTTP server on
   loopback, so the real level tools run against it (a terminal call writes only the replay's own temporary
   memory);
3. the pass's pushed prompt is built by the production `push_text` and `pass_prompt`;
4. the real level host (`player-host/5`, the frozen route, the current role prompt) runs the pass.

The probe never touches a game or a live session, and every output is labelled `engineering-probe`: a measure of
whether the interface can be called correctly on the route, never evidence about play. The provider credential
is read only from the macOS Keychain item at run time and is passed only in the host's environment.

Spend. `--max-usd` is required and is a hard cap on the *charged* cost, enforced up front. A route whose configured
model cost is all zero is refused (it could not measure spend). Every request is charged at its reported configured
cost, and every request without reported usage at a per-request bound: `--max-request-usd` when given, else
`--sample-estimate-usd` divided by the pass allowance. Before a sample launches, its host allowance is set to
`min(pass allowance, floor(remaining USD / max(bound, dearest request cost seen so far)))` and the sample is skipped
when that is below one, so the cap holds whenever no request is dearer than that. Killing a running host when its charge would pass the remaining cap is only a
backstop for a request that cost more than the bound.

Inputs. The route must already be `player-host/5` (a conformance package's selected route included); nothing is
normalized or defaulted. The thresholds come from the required `--thresholds` file. A paid run needs a clean
checkout, and the report records the source commit and the digests of every input it read.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.application import Application
from harness.computer.launch import close_group
from harness.computer.protocol import ControlError
from harness.computer.runtime import ComputerRuntime
from harness.player.memory import Memory
from harness.server import serve
from tools.campaign_package import LEVEL_ROLE
from tools.campaign_player import HostEvents, pass_prompt, push_text, write_new
from tools.configure_player_tools import configuration

LABEL = 'engineering-probe'
PROBE_ROOT = ROOT / '.runtime' / 'probes'
KEYCHAIN_ITEM = 'userspace-dev-openrouter'
# A sample's whole-pass cost estimate; with the pass allowance it gives the per-request bound for a request without usage.
DEFAULT_SAMPLE_ESTIMATE_USD = 0.12
THRESHOLDS_SCHEMA = 'level-probe-thresholds/1'
# What the replay cannot reproduce, stated in every report.
LIMITS = (
    'No staleness or discard: the replay has no inputs after the pass starts, so a well-formed terminal call commits, keeps '
    'or abstains and a staleness-bound discard cannot occur.',
    'Operations pending when a pass started are replayed as finished: the recording\'s final state of each is used.',
    'Memory is not replayed: the replay store starts empty, so a pass recorded after a level commit sees no current '
    'subgoal. A sample\'s state_fidelity says whether its recorded pass had a level commit or stored level row before it '
    '(`memory-reset`), had none (`exact`), or cannot be known because the recorded player store is missing or unreadable '
    '(`unknown`).',
    'The allowance is each recorded pass\'s own when its receipt names one, else the manifest\'s; a sample\'s allowance '
    'record shows any reduction by the spend cap or override by --max-requests.',
    'Provider behavior at the replay moment, not the recorded run\'s: sampling differs and no outcome is play evidence.',
)


def keychain_secret() -> str:
    """The provider credential, read at run time exactly as the campaign launchers read it; never printed or written."""
    try:
        value = subprocess.run(['security', 'find-generic-password', '-s', KEYCHAIN_ITEM, '-w'],
                               capture_output=True, check=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise ValueError(f'The provider credential is unavailable in the Keychain item {KEYCHAIN_ITEM}') from None
    if not value:
        raise ValueError(f'The Keychain item {KEYCHAIN_ITEM} is empty')
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_thresholds(path: Path) -> dict:
    """The pre-registered pass criteria: a closed JSON file, never constants in this tool."""
    value = json.loads(path.read_text())
    keys = {'schema', 'valid_terminal_rate_at_least', 'repeated_identical_refusal_at_most'}
    if not isinstance(value, dict) or set(value) != keys or value['schema'] != THRESHOLDS_SCHEMA:
        raise ValueError(f'Thresholds must be a closed {THRESHOLDS_SCHEMA} object with exactly {sorted(keys - {"schema"})}')
    rate, repeats = value['valid_terminal_rate_at_least'], value['repeated_identical_refusal_at_most']
    if type(rate) not in (int, float) or not 0 < rate <= 1 or type(repeats) is not int or repeats < 1:
        raise ValueError('valid_terminal_rate_at_least must be in (0,1] and repeated_identical_refusal_at_most an integer >= 1')
    return value


def git_state(root: Path = ROOT) -> tuple[str, bool]:
    """The checkout's commit and whether tracked files differ from it (untracked files do not count)."""
    def git(*arguments: str) -> str:
        return subprocess.run(['git', *arguments], cwd=root, capture_output=True, check=True, text=True).stdout.strip()
    return git('rev-parse', 'HEAD'), bool(git('status', '--porcelain', '--untracked-files=no'))


# --- the recorded passes -------------------------------------------------------------------------------------

def stored_level_rows(store: Path | None, before_wall: float | None) -> int | None:
    """Level Work rows in a recorded player store created before `before_wall` (read-only).

    None when that cannot be known: no store, no start time, or a store that is missing or unreadable.
    """
    if store is None or before_wall is None or not store.is_file():
        return None
    try:
        database = sqlite3.connect(f'file:{store}?mode=ro&immutable=1', uri=True)
        try:
            documents = [json.loads(row[0]) for row in database.execute("SELECT document FROM records WHERE kind='work'")]
        finally:
            database.close()
    except (sqlite3.Error, ValueError):
        return None
    return sum(d.get('data', {}).get('level') == 'subgoal' and d.get('created_wall', before_wall) < before_wall for d in documents)


def recorded_passes(session: Path) -> list[dict]:
    """Every level pass of a recorded campaign session, with what its prompt was built from.

    `prior_level_commits` counts the recorded run's level commits that wrote memory (a replace or a close, never a
    discard or a keep) in earlier passes' traces, and `prior_stored_rows` the level Work rows its player store held
    from before the pass started (None when the store is missing or unreadable); either count makes the replay's empty
    memory differ from the recording, and None with no commit leaves the fidelity `unknown`.
    """
    session = session.resolve(strict=True)
    database = sqlite3.connect(f'file:{session / "session.sqlite3"}?mode=ro&immutable=1', uri=True)
    try:
        session_id = json.loads(database.execute("SELECT value FROM metadata WHERE key='session'").fetchone()[0])
    finally:
        database.close()
    store = (json.loads((session / 'manifest.json').read_text()).get('player_store'))
    passes, writes = [], 0
    for actor_directory in sorted((session / 'actors').glob('[0-9][0-9][0-9]')):
        actor = json.loads((actor_directory / 'actor.json').read_text())['actor_id']
        shown_through = 0
        for pass_directory in sorted((actor_directory / 'level').glob('[0-9][0-9][0-9]')):
            receipt = json.loads((pass_directory / 'driver-receipt.json').read_text())
            rows = stored_level_rows(Path(store) if store else None, receipt.get('started_wall'))
            passes.append(dict(session=session, session_id=session_id, actor_id=actor, actor_directory=actor_directory,
                directory=pass_directory, index=receipt['index'], reason=receipt['reason'], entries=receipt['log_entries'],
                inputs=receipt['actor_inputs'], seconds=receipt['allocated_seconds'], shown_through=shown_through,
                recorded_allowance=receipt.get('allocated_attempts'), prior_level_commits=writes, prior_stored_rows=rows))
            writes += sum(e['type'] == 'level-commit' and e.get('action') in ('replace', 'close')
                          for e in receipt.get('level_events', []))
            # The campaign's next push starts after the last entry this pass was shown.
            shown_through = receipt['log_entries']
    return passes


class ReplayChannel:
    """A channel that cannot play: the replay serves a level reader, never an actor."""
    def __init__(self):
        self.stopped = threading.Event()
        self.fault = None

    def target(self):
        return dict(window_id=0, paused=True)

    def stop(self, reason):
        self.stopped.set()
        return dict(stop_requested=True, native_pause_confirmed=False, reason=reason)

    def stop_status(self):
        return dict(stop_requested=self.stopped.is_set(), native_pause_confirmed=False)

    def request(self, *_):
        raise ControlError('A replay has no game')

    def close(self):
        pass


class ReplayProcess:
    pid = 0

    @staticmethod
    def poll():
        return None


def build_replay(recorded: dict, directory: Path, staleness_inputs: int) -> dict:
    """A fresh replay of one pass's session state: operations up to the pass start, the frames they cite, a reader."""
    session = recorded['session']
    source = sqlite3.connect(f'file:{session / "session.sqlite3"}?mode=ro&immutable=1', uri=True)
    try:
        rows = source.execute('SELECT id,kind,created_wall,deadline,input_json,final_json FROM operations '
                              'WHERE actor=? ORDER BY rowid LIMIT ?', (recorded['actor_id'], recorded['entries'])).fetchall()
        frames = {row[0]: row[1] for row in source.execute('SELECT id,metadata FROM sources')}
    finally:
        source.close()
    if len(rows) != recorded['entries']:
        raise ValueError(f'{session.name}: the recording holds {len(rows)} operations, the pass saw {recorded["entries"]}')
    directory.mkdir(mode=0o700)
    limits = dict(max_inputs=10 ** 6, max_requests=10 ** 6, max_frames=10 ** 6, max_bytes=2 ** 40)
    runtime = ComputerRuntime(directory, recorded['session_id'], ReplayChannel(), ReplayProcess(), time.monotonic() + 36000, limits)
    memory = Memory(directory / 'player.sqlite3')
    application = Application(runtime, memory, directory / 'contexts')
    actor = application.add_actor('narrowed')
    for identity, kind, created, deadline, actions, final in rows:
        decoded = json.loads(actions)
        runtime.store.begin(dict(operation_id=identity, actor_id=actor['actor_id'], kind=kind, created_wall=created,
                                 deadline_monotonic=deadline), decoded, sum(a['type'] != 'wait' for a in decoded or []))
        if final is None:
            continue
        result = dict(json.loads(final), actor_id=actor['actor_id'])
        if result.get('source'):
            identifier = result['source']['source_id']
            png = (session / 'sources' / f'{identifier}.png').read_bytes()
            runtime.store.put_source(json.loads(frames[identifier]), png, actor['actor_id'])
        runtime.store.finish(result)
    reader = application.add_reader(actor['actor_id'], staleness_inputs=staleness_inputs)
    return dict(application=application, runtime=runtime, memory=memory, actor=actor, reader=reader)


# --- one replayed sample -------------------------------------------------------------------------------------

def load_route(path: Path, max_requests: int, tag: str | None) -> dict:
    """The frozen route as a level-pass route, exactly as the campaign driver derives it from its actor route.

    The route (or a conformance package's selected route) must already be `player-host/5`: an older schema is
    rejected, never normalized, and no field is defaulted. Only the role, the intent tail and the pass allowance are set.
    """
    value = json.loads(path.read_text())
    if value.get('schema') == 'finite-provider-conformance/1':
        routes = [r for r in value['routes'] if tag is None or r['tag'] == tag]
        if len(routes) != 1:
            raise ValueError('Select exactly one conformance route with --route-tag')
        value = routes[0]['configuration']
    if value.get('schema') != 'player-host/5':
        raise ValueError(f'The route must be player-host/5, not {value.get("schema")!r}; it is not converted')
    cost = value.get('model', {}).get('cost')
    if not isinstance(cost, dict) or not any(isinstance(v, (int, float)) and v > 0 for v in cost.values()):
        raise ValueError('The route\'s configured model cost is all zero or missing; the spend cap could not measure it')
    return dict(value, role='level', intent_tail_bytes=None, max_requests=max_requests)


REFUSAL_FIELD = re.compile(r'^- ([A-Za-z0-9_.]+):', re.M)


def classify(directory: Path, events: HostEvents, child_returncode: int | None) -> dict:
    """What one finished sample did, from its own host trace."""
    refusals, texts = collections.Counter(), collections.Counter()
    calls, started, validated, refused, reserved, last_logical = {}, set(), set(), {}, set(), None
    reserved_non_terminal = 0
    for line in (directory / 'host.jsonl').read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get('type')
        if kind == 'tool-validation-feedback':
            validated.add(event.get('tool_call_id'))
            for field in REFUSAL_FIELD.findall(event.get('projected_text', '')) or ['(unparsed)']:
                refusals[f'{event["tool"]}.{field}'] += 1
            texts[hashlib.sha256(f'{event["tool"]}:{event.get("projected_text")}'.encode()).hexdigest()] += 1
        elif kind == 'tool-result' and event.get('tool', '').startswith('player_level_') \
                and (event.get('result') or {}).get('isError'):
            text = ''.join(p.get('text', '') for p in event['result'].get('content', []) if p.get('type') == 'text')
            refusals[f'{event["tool"]}.custodian'] += 1
            texts[hashlib.sha256(f'{event["tool"]}:{text}'.encode()).hexdigest()] += 1
        elif kind == 'tool-start':
            started.add(event.get('tool_call_id'))
        elif kind == 'level-terminal-call':
            calls[event['tool_call_id']] = event
        elif kind == 'tool-refused':
            refused[event.get('tool_call_id')] = event
        elif kind == 'level-reserved-request':
            # `logical_request_id` is the logical count (`request-K`) in both events, so a retried request matches itself.
            reserved.add(event.get('logical_request_id'))
        elif kind == 'request-start':
            last_logical = event.get('logical_request_id')
    # A terminal call that never reached the custodian and got no validation refusal is refused by the host (a refusal
    # event), malformed (unparseable arguments) or otherwise undispatched; each counts, and none counts twice.
    for identifier, call in calls.items():
        if identifier in started or identifier in validated:
            continue
        reason = (refused.get(identifier) or {}).get('reason')
        if reason in ('level-ended', 'handoff'):
            continue
        label = f'tool-refused:{reason}' if reason else 'arguments_error' if call.get('arguments_error') else 'undispatched'
        refusals[f'{call["tool"]}.{label}'] += 1
        texts[f'{call["tool"]}:{label}'] += 1
    for event in refused.values():
        reserved_non_terminal += event.get('reason') == 'level-reserved'
    terminal = next((e for e in events.level if e['type'] in ('level-commit', 'level-discard', 'level-abstain')), None)
    settled = events.settled or {}
    outcome = None
    if terminal is not None:
        outcome = f'abstain:{terminal["reason_code"]}' if terminal['type'] == 'level-abstain' else terminal['action']
    return dict(valid_terminal_call=terminal is not None, terminal=terminal and terminal['type'], outcome=outcome,
                settled_reason=settled.get('reason'), settled_ok=settled.get('ok'), requests=len(events.requests),
                # A provider failure on a request that offered only the terminal tools, counted apart from other settlements.
                provider_error_on_reserved=settled.get('reason') == 'provider-error' and last_logical in reserved,
                reserved_non_terminal_calls=reserved_non_terminal,
                refusals=dict(refusals), repeated_identical_refusal=max(texts.values(), default=0),
                configured_cost_usd=sum(v.get('cost', {}).get('total', 0) for v in events.usage.values()),
                host_returncode=child_returncode)


def run_sample(recorded: dict, sample: int, work: Path, out: Path, route: dict, context: str, role: str, effort: str,
               host_argv: list[str], secret: str, remaining_usd: float, bound_usd: float, staleness_inputs: int) -> dict:
    """Replay one pass once. The route's `max_requests` was already set so the sample cannot pass `remaining_usd` at
    `bound_usd` per request; the host is killed only as a backstop if its charge would pass it anyway."""
    directory = Path(tempfile.mkdtemp(prefix=f'{recorded["index"]:03d}-{sample:02d}-', dir=work))
    replay = server = thread = child = events = None
    try:
        replay = build_replay(recorded, directory / 'replay', staleness_inputs)
        application = replay['application']
        server, thread = serve(application, 0)
        reader_file = directory / 'reader.json'
        write_new(reader_file, dict(schema='player-adapter/1', base_url=f'http://127.0.0.1:{server.server_port}',
                                    session=replay['runtime'].session, **replay['reader']))
        pushed, _, _ = push_text(application, replay['reader']['actor_id'], replay['actor']['actor_id'],
                                 recorded['shown_through'], recorded['entries'])
        brief = (recorded['session'] / 'prompt.txt').read_text()
        prompt = pass_prompt(role, brief, pushed, recorded['reason'], recorded['entries'], recorded['inputs'],
                             route['max_requests'], recorded['seconds'])
        write_new(directory / 'route.json', route)
        write_new(directory / 'mcp.json', configuration(str(reader_file), profile='reader'))
        write_new(directory / 'context.txt', context, text=True)
        write_new(directory / 'prompt.txt', prompt, text=True)
        write_new(directory / 'player-final.txt', '', text=True)
        arguments = [*host_argv, 'run', '--config', str(directory / 'route.json'), '--mcp-config', str(directory / 'mcp.json'),
                     '--context', str(directory / 'context.txt'), '--model', route['model']['id'], '--effort', effort,
                     '--timeout-seconds', str(recorded['seconds']), '-o', str(directory / 'player-final.txt')]
        environment = dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='en_US.UTF-8', **{route['api_key_env']: secret})
        stopped_by_guard = False
        with (directory / 'host.jsonl').open('x') as output, (directory / 'host-stderr.log').open('x') as errors, \
                (directory / 'prompt.txt').open() as prompt_input:
            child = subprocess.Popen(arguments, cwd=ROOT, env=environment, stdin=prompt_input, stdout=output, stderr=errors,
                                     start_new_session=True)
            events = HostEvents(directory / 'host.jsonl', route['max_requests'])
            deadline = time.monotonic() + recorded['seconds'] + 30
            while child.poll() is None:
                events.read()
                costs = [v.get('cost', {}).get('total', 0) for v in events.usage.values()]
                # Backstop only: started requests without usage (the one in flight included) count at the larger of the
                # bound and the dearest request seen, so a request dearer than the bound cannot go on unchecked.
                step = max([bound_usd, *costs])
                if not events.level and sum(costs) + (len(events.requests) - len(costs)) * step > remaining_usd:
                    stopped_by_guard = True
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(.05)
        cleanup = close_group(child)
        accounting = events.finish()
        record = classify(directory, events, child.returncode)
        # Every request without reported usage is charged at the bound; none is free.
        missing = accounting['missing_usage_attempts']
        record.update(pass_index=recorded['index'], sample=sample, session=recorded['session'].name,
                      actor=recorded['actor_directory'].name, missing_usage_attempts=missing,
                      dearest_request_usd=max([v.get('cost', {}).get('total', 0) for v in events.usage.values()], default=0),
                      charged_usd=record['configured_cost_usd'] + missing * bound_usd,
                      stopped_by_spend_guard=stopped_by_guard, cleanup_absent=cleanup['process_absent'] and cleanup['group_absent'],
                      # Whether the replay's empty memory matches the recording at the pass start.
                      state_fidelity=('memory-reset' if recorded['prior_level_commits'] or recorded['prior_stored_rows']
                                      else 'unknown' if recorded['prior_stored_rows'] is None else 'exact'),
                      state_basis=dict(prior_level_commits=recorded['prior_level_commits'],
                                       prior_stored_rows=recorded['prior_stored_rows']),
                      allowance=dict(recorded=recorded['recorded_allowance'], used=route['max_requests']))
        out_directory = out / 'samples' / (f'{recorded["session"].name}-actor{recorded["actor_directory"].name}'
                                           f'-pass{recorded["index"]:03d}-sample{sample:02d}')
        out_directory.mkdir(parents=True)
        shutil.copy(directory / 'host.jsonl', out_directory / 'host.jsonl')
        shutil.copy(directory / 'prompt.txt', out_directory / 'prompt.txt')
        return record
    finally:
        if events is not None:
            events.close()
        if child is not None and child.poll() is None:
            close_group(child)
        if server is not None:
            server.shutdown(); server.server_close(); thread.join(2)
        if replay is not None:
            replay['runtime'].close(); replay['memory'].close()
        shutil.rmtree(directory, ignore_errors=True)


# --- the report ----------------------------------------------------------------------------------------------

def summarize(records: list[dict]) -> dict:
    """Rates and counts for any group of samples."""
    total = len(records)
    outcomes, refusals, settled = collections.Counter(), collections.Counter(), collections.Counter()
    for record in records:
        outcomes[record['outcome'] or 'no-terminal-call'] += 1
        refusals.update(record['refusals'])
        settled[record['settled_reason']] += 1
    requests = [r['requests'] for r in records]
    return dict(samples=total, valid_terminal_calls=sum(r['valid_terminal_call'] for r in records),
        valid_terminal_rate=sum(r['valid_terminal_call'] for r in records) / total if total else None,
        outcomes=dict(outcomes), refusals_by_field=dict(refusals),
        level_final_refusal=settled['level-final-refusal'], request_limit=settled['request-limit'],
        level_uncertain=settled['level-uncertain'],
        provider_error_on_reserved_request=sum(r['provider_error_on_reserved'] for r in records),
        reserved_non_terminal_calls=sum(r['reserved_non_terminal_calls'] for r in records),
        state_fidelity=dict(collections.Counter(r['state_fidelity'] for r in records)),
        missing_usage_attempts=sum(r['missing_usage_attempts'] for r in records),
        settled_reasons={str(k): v for k, v in settled.items()},
        max_repeated_identical_refusal=max((r['repeated_identical_refusal'] for r in records), default=0),
        requests_used=dict(total=sum(requests), mean=statistics.fmean(requests) if requests else None, max=max(requests, default=None)),
        configured_cost_usd=sum(r['configured_cost_usd'] for r in records),
        charged_usd=sum(r['charged_usd'] for r in records))


def probe(sessions: list[Path], route_path: Path, *, samples: int, max_usd: float, name: str, secret: str,
          host_argv: list[str], thresholds_path: Path, effort: str = 'medium', max_requests: int | None = None,
          route_tag: str | None = None, passes: set[int] | None = None,
          sample_estimate_usd: float = DEFAULT_SAMPLE_ESTIMATE_USD, max_request_usd: float | None = None,
          probe_root: Path = PROBE_ROOT) -> dict:
    """Replay every selected recorded pass `samples` times and write the labelled report under the probes directory.

    Everything that can refuse does so before anything is written or spent: the cap, the thresholds, a dirty checkout,
    the route's schema and cost, and the output location.
    """
    if not max_usd > 0:
        raise ValueError('A positive --max-usd spend cap is required')
    if samples < 1:
        raise ValueError('At least one sample per pass is required')
    if not (max_request_usd if max_request_usd is not None else sample_estimate_usd) > 0:
        raise ValueError('A positive per-request cost bound (--max-request-usd or --sample-estimate-usd) is required')
    thresholds = load_thresholds(thresholds_path)
    commit, dirty = git_state()
    if dirty:
        raise ValueError('The checkout has uncommitted changes to tracked files; a paid probe runs only from a clean commit')
    route = load_route(route_path, 1, route_tag)
    out = (probe_root / name).resolve()
    if not out.is_relative_to(probe_root.resolve()) or out == probe_root.resolve():
        raise ValueError('Probe outputs are written only under .runtime/probes')
    role = LEVEL_ROLE.read_text()
    recorded_all = [p for session in sessions for p in recorded_passes(session)]
    selected = [p for p in recorded_all if passes is None or p['index'] in passes]
    if not selected:
        raise ValueError('No recorded level pass is selected')
    manifest = {s.resolve(): json.loads((s / 'manifest.json').read_text()) for s in sessions}
    inputs = [dict(session=s.name, manifest_sha256=sha256_file(s / 'manifest.json'), receipt_sha256=sha256_file(s / 'receipt.json'))
              for s in sessions]
    probe_root.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    work = out / 'work'
    work.mkdir()
    records, spent, stopped, dearest = [], 0.0, False, 0.0
    try:
        for recorded in selected:
            level = manifest[recorded['session']]['level']
            # The recorded pass's own allowance; --max-requests overrides it, and the manifest's is the fallback.
            allowance = max_requests or recorded['recorded_allowance'] or level['pass_max_requests']
            bound = max_request_usd if max_request_usd is not None else sample_estimate_usd / allowance
            context = (recorded['directory'] / 'context.txt').read_text()
            for sample in range(1, samples + 1):
                # The cap is hard up front: no more requests than the remaining spend covers at the bound, or at the
                # dearest request seen so far when that is dearer.
                affordable = int((max_usd - spent) // max(bound, dearest))
                if affordable < 1:
                    stopped = True
                    break
                route = load_route(route_path, min(allowance, affordable), route_tag)
                record = run_sample(recorded, sample, work, out, route, context, role, effort, host_argv, secret,
                                    max_usd - spent, bound, level['staleness_inputs'])
                records.append(record)
                spent += record['charged_usd']
                dearest = max(dearest, record['dearest_request_usd'])
                if record['stopped_by_spend_guard']:
                    stopped = True
                    break
            if stopped:
                break
    finally:
        shutil.rmtree(work, ignore_errors=True)
    per_pass = {}
    for key in sorted({(r['session'], r['actor'], r['pass_index']) for r in records}):
        per_pass[f'{key[0]}/actor{key[1]}/pass{key[2]:03d}'] = summarize(
            [r for r in records if (r['session'], r['actor'], r['pass_index']) == key])
    pooled = summarize(records)
    report = dict(schema='level-probe/1', label=LABEL, excluded_from_evidence=True,
        scope='Replays recorded level-pass contexts against a read-only replay of the recorded session. It measures whether '
              'the level interface can be called correctly on the route; it says nothing about play, intent quality or outcomes.',
        interface=dict(host='player-host/5', role_prompt=LEVEL_ROLE.name, role_sha256=hashlib.sha256(role.encode()).hexdigest()),
        route=dict(model=route['model']['id'], provider=route['model']['provider'], effort=effort,
                   file_sha256=sha256_file(route_path)),
        source=dict(commit=commit, clean=True),
        inputs=dict(sessions=inputs),
        parameters=dict(samples_per_pass=samples, max_usd=max_usd, sample_estimate_usd=sample_estimate_usd,
                        max_request_usd=max_request_usd, max_requests_override=max_requests,
                        passes_selected=len(selected), sessions=[s.name for s in sessions]),
        spend=dict(charged_usd=spent, configured_cost_usd=pooled['configured_cost_usd'], max_usd=max_usd,
                   missing_usage_attempts=pooled['missing_usage_attempts'], stopped_by_spend_guard=stopped,
                   samples_run=len(records), samples_planned=len(selected) * samples),
        thresholds=dict(definition=thresholds, file_sha256=sha256_file(thresholds_path),
                        valid_terminal_rate=pooled['valid_terminal_rate'],
                        valid_terminal_rate_met=(pooled['valid_terminal_rate'] or 0) >= thresholds['valid_terminal_rate_at_least'],
                        max_repeated_identical_refusal=pooled['max_repeated_identical_refusal'],
                        repeated_identical_refusal_met=pooled['max_repeated_identical_refusal']
                        <= thresholds['repeated_identical_refusal_at_most']),
        limits=list(LIMITS),
        pooled=pooled, passes=per_pass, samples=records)
    with (out / 'report.json').open('x') as stream:
        json.dump(report, stream, indent=2, default=str)
        stream.write('\n')
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--session', type=Path, action='append', required=True, help='A recorded campaign session directory')
    parser.add_argument('--route', type=Path, required=True,
                        help='The frozen route: a route.json or a finite-provider-conformance package')
    parser.add_argument('--route-tag', help='Select a route of a conformance package')
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--max-usd', type=float, required=True, help='Hard spend cap on the charged cost')
    parser.add_argument('--sample-estimate-usd', type=float, default=DEFAULT_SAMPLE_ESTIMATE_USD,
                        help='A pass\'s estimated cost; divided by its allowance it bounds a request without usage')
    parser.add_argument('--max-request-usd', type=float,
                        help='The route\'s maximum cost of one request; replaces the estimate-derived bound')
    parser.add_argument('--thresholds', type=Path, required=True, help=f'The pre-registered {THRESHOLDS_SCHEMA} file')
    parser.add_argument('--name', required=True, help='Output directory name under .runtime/probes')
    parser.add_argument('--effort', default='medium')
    parser.add_argument('--max-requests', type=int)
    parser.add_argument('--pass', dest='passes', type=int, action='append', help='Only this recorded pass index')
    parser.add_argument('--host-node', default=shutil.which('node'))
    args = parser.parse_args(argv)
    if not args.host_node:
        parser.error('Node.js is required to run the level host')
    report = probe([s.resolve() for s in args.session], args.route.resolve(), samples=args.samples, max_usd=args.max_usd,
                   name=args.name, secret=keychain_secret(), host_argv=[args.host_node, str(ROOT / 'tools/player_host/run.mjs')],
                   effort=args.effort, max_requests=args.max_requests, route_tag=args.route_tag,
                   passes=set(args.passes) if args.passes else None, sample_estimate_usd=args.sample_estimate_usd,
                   max_request_usd=args.max_request_usd, thresholds_path=args.thresholds.resolve())
    print(json.dumps(dict(label=report['label'], output=str(PROBE_ROOT / args.name / 'report.json'), spend=report['spend'],
                          thresholds=report['thresholds']), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
