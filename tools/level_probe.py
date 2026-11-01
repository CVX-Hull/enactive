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
whether the interface can be called correctly on the route, never evidence about play. It refuses to run
without `--max-usd` and stops before the configured cost of its requests would exceed it. The provider credential
is read only from the macOS Keychain item at run time and is passed only in the host's environment.
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
# Each sample's pass-level wall allowance and the first-sample cost projection when nothing has been observed.
DEFAULT_SAMPLE_ESTIMATE_USD = 0.12
VALID_THRESHOLD = 0.9


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


# --- the recorded passes -------------------------------------------------------------------------------------

def recorded_passes(session: Path) -> list[dict]:
    """Every level pass of a recorded campaign session, with what its prompt was built from."""
    session = session.resolve(strict=True)
    database = sqlite3.connect(f'file:{session / "session.sqlite3"}?mode=ro&immutable=1', uri=True)
    try:
        session_id = json.loads(database.execute("SELECT value FROM metadata WHERE key='session'").fetchone()[0])
    finally:
        database.close()
    passes = []
    for actor_directory in sorted((session / 'actors').glob('[0-9][0-9][0-9]')):
        actor = json.loads((actor_directory / 'actor.json').read_text())['actor_id']
        shown_through = 0
        for pass_directory in sorted((actor_directory / 'level').glob('[0-9][0-9][0-9]')):
            receipt = json.loads((pass_directory / 'driver-receipt.json').read_text())
            passes.append(dict(session=session, session_id=session_id, actor_id=actor, actor_directory=actor_directory,
                directory=pass_directory, index=receipt['index'], reason=receipt['reason'], entries=receipt['log_entries'],
                inputs=receipt['actor_inputs'], seconds=receipt['allocated_seconds'], shown_through=shown_through,
                recorded_commits=[e['type'] for e in receipt.get('level_events', []) if e['type'] != 'level-abstain']))
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
    """The frozen route as a level-pass route; a provider-conformance package supplies its selected route."""
    value = json.loads(path.read_text())
    if value.get('schema') == 'finite-provider-conformance/1':
        routes = [r for r in value['routes'] if tag is None or r['tag'] == tag]
        if len(routes) != 1:
            raise ValueError('Select exactly one conformance route with --route-tag')
        value = routes[0]['configuration']
    return dict(value, schema='player-host/5', role='level', intent_tail_bytes=None, max_requests=max_requests,
                max_context_images=value.get('max_context_images', 30), context_image_block=value.get('context_image_block', 1),
                service_tier=value.get('service_tier', 'default'))


REFUSAL_FIELD = re.compile(r'^- ([A-Za-z0-9_.]+):', re.M)


def classify(directory: Path, events: HostEvents, child_returncode: int | None) -> dict:
    """What one finished sample did, from its own host trace."""
    refusals, texts = collections.Counter(), collections.Counter()
    for line in (directory / 'host.jsonl').read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'tool-validation-feedback':
            for field in REFUSAL_FIELD.findall(event.get('projected_text', '')) or ['(unparsed)']:
                refusals[f'{event["tool"]}.{field}'] += 1
            texts[hashlib.sha256(f'{event["tool"]}:{event.get("projected_text")}'.encode()).hexdigest()] += 1
        elif event.get('type') == 'tool-result' and event.get('tool', '').startswith('player_level_') \
                and (event.get('result') or {}).get('isError'):
            text = ''.join(p.get('text', '') for p in event['result'].get('content', []) if p.get('type') == 'text')
            refusals[f'{event["tool"]}.custodian'] += 1
            texts[hashlib.sha256(f'{event["tool"]}:{text}'.encode()).hexdigest()] += 1
    terminal = next((e for e in events.level if e['type'] in ('level-commit', 'level-discard', 'level-abstain')), None)
    settled = events.settled or {}
    outcome = None
    if terminal is not None:
        outcome = f'abstain:{terminal["reason_code"]}' if terminal['type'] == 'level-abstain' else terminal['action']
    return dict(valid_terminal_call=terminal is not None, terminal=terminal and terminal['type'], outcome=outcome,
                settled_reason=settled.get('reason'), settled_ok=settled.get('ok'), requests=len(events.requests),
                refusals=dict(refusals), repeated_identical_refusal=max(texts.values(), default=0),
                configured_cost_usd=sum(v.get('cost', {}).get('total', 0) for v in events.usage.values()),
                host_returncode=child_returncode)


def run_sample(recorded: dict, sample: int, work: Path, out: Path, route: dict, context: str, role: str, effort: str,
               host_argv: list[str], secret: str, remaining_usd: float, staleness_inputs: int) -> dict:
    """Replay one pass once; the host is stopped if its configured cost would pass `remaining_usd`."""
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
                # Stop before another request of the largest configured cost seen would pass the cap.
                if costs and not events.level and sum(costs) + max(costs) > remaining_usd:
                    stopped_by_guard = True
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(.05)
        cleanup = close_group(child)
        events.finish()
        record = classify(directory, events, child.returncode)
        record.update(pass_index=recorded['index'], sample=sample, session=recorded['session'].name,
                      actor=recorded['actor_directory'].name,
                      stopped_by_spend_guard=stopped_by_guard, cleanup_absent=cleanup['process_absent'] and cleanup['group_absent'],
                      state_fidelity='exact' if not recorded['recorded_commits'] else 'memory-reset')
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
        settled_reasons={str(k): v for k, v in settled.items()},
        max_repeated_identical_refusal=max((r['repeated_identical_refusal'] for r in records), default=0),
        requests_used=dict(total=sum(requests), mean=statistics.fmean(requests) if requests else None, max=max(requests, default=None)),
        configured_cost_usd=sum(r['configured_cost_usd'] for r in records))


def probe(sessions: list[Path], route_path: Path, *, samples: int, max_usd: float, name: str, secret: str,
          host_argv: list[str], effort: str = 'medium', max_requests: int | None = None, route_tag: str | None = None,
          passes: set[int] | None = None, sample_estimate_usd: float = DEFAULT_SAMPLE_ESTIMATE_USD,
          probe_root: Path = PROBE_ROOT) -> dict:
    """Replay every selected recorded pass `samples` times and write the labelled report under the probes directory."""
    if not max_usd > 0:
        raise ValueError('A positive --max-usd spend cap is required')
    if samples < 1:
        raise ValueError('At least one sample per pass is required')
    out = (probe_root / name).resolve()
    if not out.is_relative_to(probe_root.resolve()) or out == probe_root.resolve():
        raise ValueError('Probe outputs are written only under .runtime/probes')
    probe_root.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    role = LEVEL_ROLE.read_text()
    recorded_all = [p for session in sessions for p in recorded_passes(session)]
    selected = [p for p in recorded_all if passes is None or p['index'] in passes]
    if not selected:
        raise ValueError('No recorded level pass is selected')
    manifest = {s.resolve(): json.loads((s / 'manifest.json').read_text()) for s in sessions}
    work = out / 'work'
    work.mkdir()
    records, spent, worst, stopped = [], 0.0, 0.0, False
    try:
        for recorded in selected:
            level = manifest[recorded['session']]['level']
            route = load_route(route_path, max_requests or level['pass_max_requests'], route_tag)
            context = (recorded['directory'] / 'context.txt').read_text()
            for sample in range(1, samples + 1):
                # Stop before launching a sample whose projected configured cost would pass the cap.
                projected = worst if records else sample_estimate_usd
                if spent + projected > max_usd:
                    stopped = True
                    break
                record = run_sample(recorded, sample, work, out, route, context, role, effort, host_argv, secret,
                                    max_usd - spent, level['staleness_inputs'])
                records.append(record)
                spent += record['configured_cost_usd']
                worst = max(worst, record['configured_cost_usd'])
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
        route=dict(model=route['model']['id'], provider=route['model']['provider'], effort=effort, max_requests=route['max_requests']),
        parameters=dict(samples_per_pass=samples, max_usd=max_usd, sample_estimate_usd=sample_estimate_usd,
                        passes_selected=len(selected), sessions=[s.name for s in sessions]),
        spend=dict(configured_cost_usd=spent, max_usd=max_usd, stopped_by_spend_guard=stopped,
                   samples_run=len(records), samples_planned=len(selected) * samples),
        thresholds=dict(valid_terminal_rate_at_least=VALID_THRESHOLD,
                        valid_terminal_rate=pooled['valid_terminal_rate'],
                        valid_terminal_rate_met=(pooled['valid_terminal_rate'] or 0) >= VALID_THRESHOLD,
                        no_repeated_identical_refusal=pooled['max_repeated_identical_refusal'] <= 1,
                        max_repeated_identical_refusal=pooled['max_repeated_identical_refusal']),
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
    parser.add_argument('--max-usd', type=float, required=True, help='Spend cap on the hosts\' configured request cost')
    parser.add_argument('--sample-estimate-usd', type=float, default=DEFAULT_SAMPLE_ESTIMATE_USD)
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
                   passes=set(args.passes) if args.passes else None, sample_estimate_usd=args.sample_estimate_usd)
    print(json.dumps(dict(label=report['label'], output=str(PROBE_ROOT / args.name / 'report.json'), spend=report['spend'],
                          thresholds=report['thresholds']), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
