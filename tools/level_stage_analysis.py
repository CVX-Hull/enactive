#!/usr/bin/env python3
"""Mechanical analysis of a level-stage run set (`level-stage-analysis/5`): retained artifacts only, no provider, no game.

    python -m tools.level_stage_analysis OUTPUT.json SESSION_DIR... --criteria CRITERIA.json [--store-template PATH]

Reads, per included run, the retained artifacts of the current contracts and nothing else: `manifest.json`
(`campaign-run/5`), `receipt.json` (`campaign-receipt/2` embedding `player-driver/6`), the one actor's
`driver-receipt.json`, every level and recorder pass's `host.jsonl` (`player-host/6`, telemetry 2),
`call-timing.jsonl`, the session store (`computer-session/3`, read-only) and, when `--store-template` names it
(a path containing `{run}`), the run's retained player store (`player-memory/1`). Any other version is rejected with an
`unsupported` error and no output file. Retained runs of earlier interfaces are not converted; the frozen analyses that
read them stay in `.runtime` and the records that cite those scripts by hash are not reproduced by this tool.

Decision thresholds are not in this file. They come from the stage's frozen `--criteria` file (schema
`level-stage-criteria/1`), whose sha256 and this tool's own sha256 are recorded in the output, so a result can be
reproduced from its record. The definitions below are the mechanical ones the criteria refer to.

Pass classes (level lane; every pass falls in exactly one, in this order):
    committed       any `level-commit` event;
    uncertain       a `level-uncertain` event or the settled reason `level-uncertain`: a terminal call whose response
                    the adapter lost; outside every rate. The driver reconciles it from the store as `committed`
                    (counted as a commit, without an `inputs_since`) or `absent`;
    abstained       a `level-abstain` event and no commit;
    discarded_only  `level-discard` events only, at least one of them not censored;
    censored        its only attempts were censored discards, or it had no event and ended `cancelled` before its
                    allocation (allocated seconds - 1): the run was cut off, not the level;
    failed          every other ending, by `settled.reason`; a pass with no settlement is `failed: unsettled`.
A discard is **censored** when its reason is `CENSORED` (the run stopped or was fenced), else a **failure** (a stale
subgoal, a handoff, a moved actor, no bound position). **Decided** attempts are commits plus failures. Rated passes
are those neither censored nor uncertain. `commit_rate` is commits / decided; `commit_rate_lower_bound` also counts
every lost commit-tool call that reconciled absent as a decided failure.

Receipt check. The level and recorder counts recomputed from the pass traces must equal the driver receipt's, each
pass's driver event types must equal its own trace's, the store's committed service rows must equal the commit count
by action, and the receipt's episode settles must equal the settle claims in the retained store. Every disagreement is
listed in `receipt_count_mismatches`; `counts_consistent` is true when that list is empty.

Custody (R4) holds when no reader operation exists in the session store and every record written by a reader is listed
in that reader's own terminal-tool service result, except the failed/dropped settle claims the driver writes as software
(`harness.player.episodes.episode`); a reader service row for a non-terminal tool, or an unexcused tombstone, is a
violation. A row with no result is excused only as the tombstone of a lost terminal call named in a pass record.

Quantiles are nearest-rank; intervals are percentile bootstraps clustered by run (`tools.evidence_stats`).
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.computer.protocol import ControlError, read_json
from harness.player.contracts import ABSTAIN_CODES, EPISODE_ABSTAIN_CODES, EPISODE_TOOLS, LEVEL_CONTRACT, LEVEL_TERMINAL_TOOLS, SOFTWARE_SETTLES
from harness.player.episodes import episode as episode_claim
from tools.control_analysis import session_database
from tools.evidence_stats import cluster_bootstrap, quantile, ratio, summary

SCHEMA = 'level-stage-analysis/5'
CRITERIA_SCHEMA = 'level-stage-criteria/1'
CRITERIA_KEYS = ('min_decided', 'min_auditable_records', 'min_commit_rate', 'max_commit_inputs_since_p95',
                 'bootstrap_seed', 'bootstrap_resamples')
MANIFEST_SCHEMA, RECEIPT_SCHEMA, DRIVER_SCHEMA, HOST_SCHEMA, TELEMETRY_VERSION = (
    'campaign-run/5', 'campaign-receipt/2', 'player-driver/6', 'player-host/6', 2)
# harness/application.py `level_call`: the only discard reason that is the run's end rather than the level's doing.
CENSORED = ('Run stopped or fenced since the pass began',)
ATTEMPTS = ('level-commit', 'level-discard')
LEVEL_EVENTS = (*ATTEMPTS, 'level-abstain', 'level-uncertain')
EPISODE_EVENTS = ('episode-record', 'episode-abstain', 'episode-uncertain')
EVENT_FIELDS = ('type', 'action', 'reason_code', 'reason', 'position', 'inputs_since', 'staleness_inputs', 'record_ids',
                'kept', 'wall_time', 'tool', 'identity', 'subgoal_id', 'derived')
ACTIONS = ('keep', 'replace', 'close')
COMMIT_TOOLS = tuple(f'player_level_{a}' for a in ACTIONS)
PASS_CLASSES = ('committed', 'discarded_only', 'abstained', 'censored', 'failed', 'uncertain')
LEVEL_RECEIPT_FIELDS = ('commits', 'keeps', 'replaces', 'closes', 'discards', 'abstains', 'abstain_codes', 'start_abstains',
                        'failed_passes', 'final_refusals', 'uncertain_terminals', 'uncertain_committed', 'uncertain_absent', 'passes')
RECORDER_RECEIPT_FIELDS = ('records', 'abstains', 'abstain_codes', 'failed_passes', 'final_refusals', 'uncertain_terminals',
                           'uncertain_committed', 'uncertain_absent', 'passes')
# Refusal circuit breaker: a pass-ending role's terminal tools, its success events and its lost-call field.
ROLES = dict(level=dict(tools=LEVEL_TERMINAL_TOOLS, uncertain='level_uncertain'),
             recorder=dict(tools=EPISODE_TOOLS, uncertain='episode_uncertain'))
BREAKER_REFUSALS = 3
# `tool-refused` reasons that are not a refused fixable call: the pass or the host had already ended.
NOT_REFUSALS = ('level-ended', 'episode-ended', 'handoff')
# tools/campaign_player.py `run_hosts`: `ending_at = now + 45` once the native process is seen gone.
FINAL_REPORT_GRACE_SECONDS = 45
EXIT_WINDOW_SECONDS = 10
EOF_REASON = 'Native receive failed: Native channel EOF'
SCALARS = ('commits', 'failures', 'censored', 'decided', 'passes', 'committed_passes', 'discarded_only_passes',
           'abstained_passes', 'censored_passes', 'failed_passes', 'uncertain_passes', 'provider_failed_passes',
           'abstains', 'start_abstains', 'commits_keep', 'commits_replace', 'commits_close', 'commits_other_action',
           'uncertain_committed', 'uncertain_absent', 'uncertain_unreconciled', 'uncertain_absent_commit_tool',
           'final_refusals')
NOTES = dict(receipt_failed_passes_settled_not_ok=(
    "The driver receipt's failed_passes counts passes whose settlement is missing or not ok, which includes censored "
    "passes cancelled with the actor; its definition differs from the `failed` pass class."))


class UnsupportedTrace(ValueError):
    """A retained artifact of a contract version this analysis does not read."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = None
        rows.append(value if isinstance(value, dict) else {'type': 'unparsed'})
    return rows


def require_host_schema(trace: Path) -> None:
    """Reject a trace whose `host-start` is not the current host at the current telemetry version.

    A trace without a `host-start` (including an empty one) is not rejected: it is classified by its settlement."""
    with trace.open() as stream:
        for line in stream:
            if '"host-start"' not in line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get('type') == 'host-start' and (
                    value.get('schema') != HOST_SCHEMA or value.get('telemetry_version') != TELEMETRY_VERSION):
                raise UnsupportedTrace(f"{trace}: host trace {value.get('schema')!r} telemetry {value.get('telemetry_version')!r}, "
                                       f'expected {HOST_SCHEMA!r} telemetry {TELEMETRY_VERSION}')


def epoch(wall_time) -> float | None:
    """Seconds since the epoch of a host event's ISO `wall_time`, or None."""
    try:
        return datetime.fromisoformat(wall_time.replace('Z', '+00:00')).timestamp()
    except (AttributeError, ValueError):
        return None


def result_text(result) -> str:
    return '\n'.join(p.get('text', '') for p in (result or {}).get('content', []) if isinstance(p, dict) and p.get('type') == 'text')


# ---------------------------------------------------------------- refusals, circuit breaker, clean exit

def refusal_keys(rows: list[dict], tools=LEVEL_TERMINAL_TOOLS) -> list[tuple[str, str]]:
    """[(tool, field)] for every refusal of a terminal tool in one pass trace.

    Sources: `tool-validation-feedback` (one per failing field line), `tool-refused` (field `refused:<reason>`, except
    `NOT_REFUSALS`) and custodian `isError` tool results (the paths before each ':' in "Invalid TOOL arguments - path:
    rule" inside the error's JSON `reason`, else `custodian:` and the reason's first 80 characters).
    """
    keys = []
    for r in rows:
        kind, tool = r.get('type'), r.get('tool')
        if tool not in tools:
            continue
        if kind == 'tool-validation-feedback':
            text = str(r.get('projected_text') or result_text(r.get('original_result')))
            lines = [line.strip()[2:].split(':', 1)[0] for line in text.split('\n') if line.strip().startswith('- ')]
            keys += [(tool, field) for field in dict.fromkeys(lines)] or [(tool, 'arguments')]
        elif kind == 'tool-refused':
            if r.get('reason') not in NOT_REFUSALS:
                keys.append((tool, f"refused:{r.get('reason')}"))
        elif kind == 'tool-result' and (r.get('result') or {}).get('isError') is True:
            text = result_text(r.get('result'))
            try:
                value = json.loads(text)
                reason = value['reason'] if isinstance(value, dict) and isinstance(value.get('reason'), str) else text
            except ValueError:
                reason = text
            prefix = f'Invalid {tool} arguments - '
            if reason.startswith(prefix):
                fields = re.findall(r'(?:^|; )([A-Za-z_][\w.]*): ', reason[len(prefix):].split('\n')[0])
                keys += [(tool, field) for field in dict.fromkeys(fields)] or [(tool, 'arguments')]
            else:
                keys.append((tool, 'custodian:' + (reason[:80] or 'error')))
    return keys


def lane_passes(driver_record: dict, role: str) -> list[dict]:
    """The pass records of one lane in an actor's `player-driver/6` record (`level.<role>.passes`)."""
    return (((driver_record.get('level') or {}).get(role) or {}).get('passes')) or []


def circuit_breaker(path: Path, role: str = 'level', threshold: int = BREAKER_REFUSALS) -> dict:
    """The stage driver's stop test for one run and role.

    A terminal tool trips when it has an identical refusal (same tool and field key) at least `threshold` times in the
    run's pass traces and no successful call of that same tool. A success is a `level-commit` of that tool's action, an
    accepted `level-abstain`, an `episode-record` or `episode-abstain` (the recorder's two tools), or a lost call of the
    tool the driver reconciled as committed.
    """
    spec = ROLES[role]
    path, refusals, ok = Path(path), Counter(), Counter()
    for trace in sorted(path.glob(f'actors/*/{role}/[0-9][0-9][0-9]/host.jsonl')):
        rows = read_jsonl(trace)
        ok.update(f"player_level_{r.get('action')}" for r in rows if r.get('type') == 'level-commit')
        ok.update('player_level_abstain' for r in rows if r.get('type') == 'level-abstain')
        ok.update('player_episode_record' for r in rows if r.get('type') == 'episode-record')
        ok.update('player_episode_abstain' for r in rows if r.get('type') == 'episode-abstain')
        refusals.update(refusal_keys(rows, spec['tools']))
    for receipt in path.glob('actors/*/driver-receipt.json'):
        passes = lane_passes(json.loads(receipt.read_text()), role)
        ok.update(u.get('tool') for p in passes for u in p.get(spec['uncertain'], []) if u.get('outcome') == 'committed')
    over = [(n, t, f) for (t, f), n in refusals.items() if n >= threshold and not ok[t]]
    n, tool, field = max(over) if over else next(((n, t, f) for (t, f), n in refusals.most_common(1)), (0, None, None))
    return dict(role=role, successes={t: c for t, c in sorted(ok.items()) if t}, worst=dict(tool=tool, field=field, count=n),
                threshold=threshold, refusals={f'{t}|{f}': c for (t, f), c in sorted(refusals.items())}, tripped=bool(over))


def clean_exit(path: Path, receipt: dict | None, level_quiescent: bool, *, grace_seconds: float = FINAL_REPORT_GRACE_SECONDS,
               window_seconds: float = EXIT_WINDOW_SECONDS) -> tuple[bool, dict]:
    """(holds, facts): whether an `incomplete` run is a clean exit, treated as complete for inclusion.

    All must hold: the native process exited 0; the one deciding actor host settled `cancelled` with no orchestration
    error; every one of the actor's input operations completed before the native exit (the last may be `unknown` only
    with the native channel's EOF after its send finished); no operation was created after the last input; the native
    exit, taken as the actor's `settled` wall time less `grace_seconds` (the driver's grace after it sees the native
    process gone), falls 0 to `window_seconds` after the last input's latest send (missing timing makes this false);
    the deciding hosts are quiescent; native absence is verified; input authority is revoked; and the level is
    quiescent. `facts` names each rule, so a failure shows which.
    """
    path, d = Path(path), receipt or {}
    actors = (d.get('driver') or {}).get('actors') or []
    actor = actors[0] if len(actors) == 1 else {}
    facts = dict(
        outcome_incomplete=d.get('outcome') == 'incomplete',
        normal_native_exit_zero=d.get('normal_native_exit_zero') is True,
        actor_cancelled=len(actors) == 1 and (actor.get('settled') or {}).get('reason') == 'cancelled'
                        and not actor.get('orchestration_error'),
        deciding_hosts_quiescent=d.get('deciding_hosts_quiescent') is True,
        native_absence_verified=d.get('native_absence_verified') is True,
        input_authority_revoked=d.get('input_authority_revoked') is True,
        level_quiescent=level_quiescent is True,
        inputs_delivered_before_exit=False, no_operation_after_last_input=False, exit_within_window_of_last_input=False)
    if actor.get('actor_id') and (path / 'session.sqlite3').exists():
        with session_database(path) as (db, _, _):
            ops = db.execute('SELECT id,kind,created_wall,final_json,actor FROM operations ORDER BY rowid').fetchall()
            mine = [o for o in ops if o[4] == actor['actor_id'] and o[1] == 'input']
            timings = {o[0]: [json.loads(t[0]) for t in db.execute('SELECT timing FROM native_intents WHERE operation=?', (o[0],))]
                       for o in mine}

        def status(final):
            return json.loads(final).get('status') if final else None

        def after_exit(op):
            """Unknown only because the native channel closed after the send finished."""
            if not op[3]:
                return False
            receipts = json.loads(op[3]).get('receipts') or []
            return (status(op[3]) == 'unknown' and bool(receipts) and all(r.get('reason') == EOF_REASON for r in receipts)
                    and bool(timings[op[0]]) and all(t.get('send_finished_wall') is not None for t in timings[op[0]]))
        facts['input_operations'] = len(mine)
        facts['inputs_delivered_before_exit'] = bool(mine) and all(status(o[3]) == 'completed' for o in mine[:-1]) \
            and (status(mine[-1][3]) == 'completed' or after_exit(mine[-1]))
        facts['no_operation_after_last_input'] = bool(mine) and not any(o[2] > mine[-1][2] for o in ops)
        facts['last_input_status'] = status(mine[-1][3]) if mine else None
        sends = [t.get('send_finished_wall') for t in timings[mine[-1][0]]] if mine else []
        settled = epoch((actor.get('settled') or {}).get('wall_time'))
        if sends and all(isinstance(x, (int, float)) for x in sends) and settled is not None:
            facts['exit_seconds_after_last_send'] = (settled - grace_seconds) - max(sends)
            facts['exit_within_window_of_last_input'] = 0 <= facts['exit_seconds_after_last_send'] <= window_seconds
    return all(v for k, v in facts.items() if isinstance(v, bool)), facts


# ---------------------------------------------------------------- one run

def pass_class(events: list[dict], ending: str | None, wall: float, allocated: float) -> tuple[str, str | None]:
    """(class, failure reason) of one level pass from its events and how its host settled."""
    types = {e['type'] for e in events}
    if 'level-commit' in types:
        return 'committed', None
    if 'level-uncertain' in types or ending == 'level-uncertain':
        return 'uncertain', None
    if 'level-abstain' in types:
        return 'abstained', None
    if 'level-discard' in types:
        if all(e['reason'] in CENSORED for e in events if e['type'] == 'level-discard'):
            return 'censored', None
        return 'discarded_only', None
    if ending == 'cancelled' and wall < allocated - 1:
        return 'censored', None
    return 'failed', ending or 'unsettled'


def provider_side(reason: str | None) -> bool:
    """Only these two settled reasons are removed in `pass_success_excluding_provider_failures`."""
    return reason in ('provider-error', 'request-timeout')


def load_run(path: Path) -> tuple[dict, dict, dict, dict]:
    """(manifest, receipt, actor driver record, level system receipt) of a run, after the version checks."""
    manifest, receipt = read_json(path / 'manifest.json', 1 << 20), read_json(path / 'receipt.json', 1 << 20)
    if not isinstance(manifest, dict) or manifest.get('schema') != MANIFEST_SCHEMA:
        raise UnsupportedTrace(f"{path.name}: manifest {(manifest or {}).get('schema')!r}, expected {MANIFEST_SCHEMA!r}")
    if not isinstance(receipt, dict) or receipt.get('schema') != RECEIPT_SCHEMA:
        raise UnsupportedTrace(f"{path.name}: receipt {(receipt or {}).get('schema')!r}, expected {RECEIPT_SCHEMA!r}")
    driver = receipt.get('driver')
    if not isinstance(driver, dict) or driver.get('schema') != DRIVER_SCHEMA:
        raise UnsupportedTrace(f"{path.name}: driver receipt {(driver or {}).get('schema')!r}, expected {DRIVER_SCHEMA!r}")
    if len(driver.get('actors') or []) != 1:
        raise UnsupportedTrace(f'{path.name}: expected exactly one deciding actor, found {len(driver.get("actors") or [])}')
    if not manifest.get('level'):
        raise UnsupportedTrace(f'{path.name}: the admission has no level')
    actor = driver['actors'][0]
    system = actor.get('level')
    level, recorder = (system or {}).get('level'), (system or {}).get('recorder')
    if not (isinstance(level, dict) and isinstance(recorder, dict) and set(LEVEL_RECEIPT_FIELDS) <= set(level)
            and set(RECORDER_RECEIPT_FIELDS) <= set(recorder)):
        raise UnsupportedTrace(f'{path.name}: the actor record lacks the {DRIVER_SCHEMA} level and recorder receipts')
    return manifest, receipt, actor, system


def lane_rows(path: Path, actor: dict, role: str, record: dict) -> list[dict]:
    trace = path / 'actors' / f"{actor['index']:03d}" / role / f"{record['index']:03d}" / 'host.jsonl'
    if not trace.exists():
        return []
    require_host_schema(trace)
    return read_jsonl(trace)


def store_rows(store: Path):
    db = sqlite3.connect(f'file:{store}?mode=ro&immutable=1', uri=True)
    try:
        if db.execute('PRAGMA user_version').fetchone()[0] != 1 or db.execute('SELECT schema FROM metadata').fetchall() != [('player-memory/1',)]:
            raise UnsupportedTrace(f'{store}: not a player-memory/1 store')
        docs = [json.loads(r[0]) for r in db.execute('SELECT document FROM records ORDER BY rowid')]
        service = db.execute('SELECT actor,tool,result,id FROM service_operations ORDER BY rowid').fetchall()
    finally:
        db.close()
    return docs, service


def store_content(store: Path, readers: set[str], served: str, uncertain=()) -> dict:
    """The retained player store's level content, the reader custody facts (R4) and the episode settles."""
    docs, all_service = store_rows(store)
    service = [row for row in all_service if row[0] in readers]
    tombstones = [s for s in service if s[2] is None]
    terminal = (*LEVEL_TERMINAL_TOOLS, *EPISODE_TOOLS)
    unexcused = [s for s in tombstones if not (s[1] in terminal and s[3] in uncertain)]
    results = [(actor, tool, json.loads(result)) for actor, tool, result, _ in service if result is not None]
    listed: dict[str, set] = {}
    for actor, _, r in results:
        listed.setdefault(actor, set()).update(rec['id'] for rec in r.get('records', []) if isinstance(rec, dict) and 'id' in rec)
    committed = [(actor, r) for actor, tool, r in results if tool in COMMIT_TOOLS and r.get('status') == 'committed']

    def software_settle(d: dict) -> bool:
        claim = episode_claim(d)
        return claim is not None and claim.get('settled') in SOFTWARE_SETTLES

    level = [d for d in docs if d.get('data', {}).get('level') == 'subgoal']
    work = [d for d in level if d['kind'] == 'work']
    current_work = {d['id'] for d in work if d['data'].get('level_contract') == LEVEL_CONTRACT}
    claims = [c for c in (episode_claim(d) for d in docs) if c is not None and c.get('actor_id') == served]
    return dict(
        subgoals_opened=len(work),
        corrections_by_outcome=dict(Counter(d['data'].get('outcome') for d in level if d['kind'] == 'correction')),
        reader_non_level_writes=sum(d['actor_id'] in readers and d['id'] not in listed.get(d['actor_id'], ())
                                    and not software_settle(d) for d in docs),
        reader_other_service_rows=sum(tool not in terminal for _, tool, result, _ in service if result is not None) + len(unexcused),
        non_level_records=len(docs) - len(level), level_records_other_contract=sum(d['data'].get('level_contract') != LEVEL_CONTRACT for d in level),
        committed_service_rows=len(committed), committed_by_action=dict(Counter(r.get('action') for _, r in committed)),
        tombstone_rows=len(tombstones),
        episode_claims_by_settle=dict(Counter(c['settled'] for c in claims)),
        # The audit unit: a committed replace that wrote a current-contract Work record present in the store.
        auditable_records=sum(r.get('action') == 'replace' and any(rec.get('id') in current_work for rec in r.get('records', []))
                              for _, r in committed))


def analyse_run(path: Path, store: Path | None = None) -> dict:
    manifest, receipt, actor, system = load_run(path)
    level, recorder = system['level'], system['recorder']
    with session_database(path) as (db, _, _):
        actors = db.execute('SELECT id,stage,serves,reader_role FROM actors').fetchall()
        ops = db.execute('SELECT actor,kind,created_wall FROM operations ORDER BY rowid').fetchall()
    readers = {a for a, stage, _, _ in actors if stage == 'reader'}
    inputs = [o[2] for o in ops if o[0] == actor['actor_id'] and o[1] == 'input']
    passes, attempts, abstentions, mismatches, refused, reconciled_all, trace_uncertain = [], [], [], [], Counter(), [], 0
    for record in level['passes']:
        rows = lane_rows(path, actor, 'level', record)
        refused.update(refusal_keys(rows))
        events = [{k: r.get(k) for k in EVENT_FIELDS} for r in rows if r.get('type') in LEVEL_EVENTS]
        driven = sorted(e['type'] for e in record.get('level_events', []) if e['type'] in LEVEL_EVENTS)
        if driven != sorted(e['type'] for e in events if e['type'] != 'level-uncertain'):
            mismatches.append(dict(source='pass level_events', pass_index=record['index'],
                                   trace=sorted(e['type'] for e in events if e['type'] != 'level-uncertain'), driver=driven))
        reconciled = record.get('level_uncertain', [])
        lost = [e['identity'] for e in events if e['type'] == 'level-uncertain']
        trace_uncertain += len(lost)
        if sorted(map(str, lost)) != sorted(str(u.get('identity')) for u in reconciled):
            mismatches.append(dict(source='pass level_uncertain', pass_index=record['index'], trace=sorted(map(str, lost)),
                                   driver=sorted(str(u.get('identity')) for u in reconciled)))
        reconciled_all += reconciled
        attempts += [e for e in events if e['type'] in ATTEMPTS]
        abstentions += [dict(pass_index=record['index'], pass_reason=record['reason'], reason_code=e['reason_code'], reason=e['reason'])
                        for e in events if e['type'] == 'level-abstain']
        wall = record['ended_wall'] - record['started_wall']
        ending = (record.get('settled') or {}).get('reason')
        klass, why = pass_class(events, ending, wall, record['allocated_seconds'])
        first_attempt = next((epoch(e['wall_time']) for e in events if e['type'] in ATTEMPTS), None)
        passes.append(dict(
            index=record['index'], reason=record['reason'], requests=record.get('observed_attempts'), charged=record['attempts_charged'],
            accounting_complete=record.get('accounting_complete'), started_wall=record['started_wall'], ended_wall=record['ended_wall'],
            wall_seconds=wall, commits=sum(e['type'] == 'level-commit' for e in events),
            discards=[e['reason'] for e in events if e['type'] == 'level-discard'],
            abstains=sum(e['type'] == 'level-abstain' for e in events),
            uncertain=[dict(identity=u.get('identity'), tool=u.get('tool'), outcome=u.get('outcome'), action=u.get('action'),
                            record_ids=u.get('record_ids')) for u in reconciled],
            pass_class=klass, failure_reason=why, ending=ending, settled_ok=(record.get('settled') or {}).get('ok'),
            # Descriptive coupling: the served actor's inputs during a pass the run's end did not cut off.
            inputs_during_pass=None if klass == 'censored' else sum(record['started_wall'] <= t <= record['ended_wall'] for t in inputs),
            inputs_push_to_attempt=None if first_attempt is None else sum(record['started_wall'] <= t <= first_attempt for t in inputs)))
    reconciled_commits = [dict(type='level-commit', action=u.get('action'), inputs_since=None, reason=None, reconciled=True)
                          for u in reconciled_all if u.get('outcome') == 'committed']
    commit_events = [e for e in attempts if e['type'] == 'level-commit']
    codes = Counter(a['reason_code'] for a in abstentions)
    settled_not_ok = [p for p in passes if p['settled_ok'] is not True]
    counted = dict(commits=len(commit_events), keeps=sum(e['action'] == 'keep' for e in commit_events),
                   replaces=sum(e['action'] == 'replace' for e in commit_events), closes=sum(e['action'] == 'close' for e in commit_events),
                   discards=sum(e['type'] == 'level-discard' for e in attempts), abstains=len(abstentions),
                   abstain_codes={c: codes[c] for c in ABSTAIN_CODES}, start_abstains=sum(a['pass_reason'] == 'start' for a in abstentions),
                   failed_passes=len(settled_not_ok), final_refusals=sum(p['ending'] == 'level-final-refusal' for p in settled_not_ok),
                   uncertain_terminals=len(reconciled_all), uncertain_committed=sum(u.get('outcome') == 'committed' for u in reconciled_all),
                   uncertain_absent=sum(u.get('outcome') == 'absent' for u in reconciled_all))
    if set(codes) - set(ABSTAIN_CODES):
        mismatches.append(dict(source='trace', field='abstain reason_code outside the closed set', trace=sorted(set(codes) - set(ABSTAIN_CODES))))
    unreconciled = [u for u in reconciled_all if u.get('outcome') not in ('committed', 'absent')]
    if unreconciled:
        mismatches.append(dict(source='driver reconciliation', field='uncertain_unreconciled', trace=len(unreconciled),
                               receipt=[u.get('identity') for u in unreconciled]))
    if trace_uncertain != counted['uncertain_terminals']:
        mismatches.append(dict(source='trace', field='level-uncertain events', trace=trace_uncertain, driver=counted['uncertain_terminals']))
    mismatches += [dict(source='driver receipt', field=k, trace=v, receipt=level.get(k)) for k, v in counted.items() if level.get(k) != v]
    recorder_summary = analyse_recorder(path, actor, recorder, mismatches)
    content = None
    if store is not None:
        recorder_lost = [u for p in recorder['passes'] for u in p.get('episode_uncertain', [])]
        content = store_content(store, readers, actor['actor_id'], {u.get('identity') for u in [*reconciled_all, *recorder_lost]}) \
            if Path(store).exists() else 'retained store missing'
    if isinstance(content, dict):
        expected = counted['commits'] + counted['uncertain_committed']
        if content['committed_service_rows'] != expected:
            mismatches.append(dict(source='retained store', field='committed service rows of the three commit tools',
                                   trace=expected, store=content['committed_service_rows']))
        by_action = Counter(e['action'] for e in commit_events) + Counter(u['action'] for u in reconciled_commits)
        if {k: v for k, v in content['committed_by_action'].items() if v} != dict(by_action):
            mismatches.append(dict(source='retained store', field='committed service rows by action', trace=dict(by_action),
                                   store=content['committed_by_action']))
        if content['tombstone_rows'] > counted['uncertain_absent'] + recorder_summary['trace_counts']['uncertain_absent']:
            mismatches.append(dict(source='retained store', field='tombstone rows', trace=counted['uncertain_absent'],
                                   store=content['tombstone_rows']))
        receipt_settles = {k: v for k, v in (system.get('episodes') or {}).get('settled', {}).items() if v}
        if receipt_settles != content['episode_claims_by_settle']:
            mismatches.append(dict(source='retained store', field='episode settles', receipt=receipt_settles,
                                   store=content['episode_claims_by_settle']))
    timing_path = path / 'call-timing.jsonl'
    timing = read_jsonl(timing_path) if timing_path.exists() else []
    actor_rows = [t for t in timing if t.get('actor_id') == actor['actor_id']]
    reader_spans = [(t['wall'] - t['held_ms'] / 1000, t['wall']) for t in timing if t.get('actor_id') in readers]

    def reader_held(t):
        start = t['wall'] - (t['wait_ms'] + t['held_ms']) / 1000
        acquired = start + t['wait_ms'] / 1000
        return any(a < acquired and b > start for a, b in reader_spans)
    return dict(
        run=path.name, outcome=receipt.get('outcome'), level_failure=system.get('failure'), level_quiescent=system.get('quiescent') is True,
        staleness_inputs=manifest['level'].get('staleness_inputs'), actor_attempts=actor.get('attempts_charged'),
        level_attempts=level.get('attempts_charged'), recorder_attempts=recorder.get('attempts_charged'), actor_inputs=len(inputs),
        actor_input_interval_seconds=(inputs[-1] - inputs[0]) / (len(inputs) - 1) if len(inputs) > 1 else None,
        passes=passes, commit_attempts=[dict(type=e['type'], action=e.get('action'), inputs_since=e['inputs_since'], reason=e['reason'])
                                        for e in attempts] + reconciled_commits,
        abstentions=abstentions, trace_counts=counted, receipt_counts={k: level.get(k) for k in LEVEL_RECEIPT_FIELDS if k != 'passes'},
        receipt_failed_passes_settled_not_ok=level.get('failed_passes'), receipt_mismatches=mismatches,
        refusals_by_tool_field={f'{t}|{f}': n for (t, f), n in sorted(refused.items())},
        recorder=recorder_summary, episodes=system.get('episodes'), subgoals=system.get('subgoals'),
        configured_usd=dict(actor=actor.get('configured_estimate_usd'), level=level.get('configured_estimate_usd'),
                            recorder=recorder.get('configured_estimate_usd')),
        lock_wait_ms=dict(all=summary([t['wait_ms'] for t in actor_rows]), reader_held=summary([t['wait_ms'] for t in actor_rows if reader_held(t)]),
                          no_reader=summary([t['wait_ms'] for t in actor_rows if not reader_held(t)])),
        custody=dict(reader_operations=sum(o[0] in readers for o in ops), readers=len(readers),
                     reader_non_level_writes=content['reader_non_level_writes'] if isinstance(content, dict) else None,
                     reader_other_service_rows=content['reader_other_service_rows'] if isinstance(content, dict) else None),
        content=content)


def analyse_recorder(path: Path, actor: dict, recorder: dict, mismatches: list[dict]) -> dict:
    """The recorder lane recounted from its pass traces, checked against the driver receipt's counts."""
    records = abstains = uncertain = 0
    codes: Counter = Counter()
    lost, classes = [], Counter()
    for record in recorder['passes']:
        rows = lane_rows(path, actor, 'recorder', record)
        events = [r for r in rows if r.get('type') in EPISODE_EVENTS]
        driven = sorted(e['type'] for e in record.get('episode_events', []))
        if driven != sorted(e['type'] for e in events if e['type'] != 'episode-uncertain'):
            mismatches.append(dict(source='recorder pass episode_events', pass_index=record['index'],
                                   trace=sorted(e['type'] for e in events if e['type'] != 'episode-uncertain'), driver=driven))
        records += sum(e['type'] == 'episode-record' for e in events)
        abstains += sum(e['type'] == 'episode-abstain' for e in events)
        codes.update(e['reason_code'] for e in events if e['type'] == 'episode-abstain')
        lost += record.get('episode_uncertain', [])
        uncertain += sum(e['type'] == 'episode-uncertain' for e in events)
        classes['recorded' if any(e['type'] == 'episode-record' for e in events) else 'abstained' if any(e['type'] == 'episode-abstain' for e in events)
                else 'uncertain' if any(e['type'] == 'episode-uncertain' for e in events) else 'failed'] += 1
    failed = [p for p in recorder['passes'] if (p.get('settled') or {}).get('ok') is not True and not p.get('episode_events')]
    counted = dict(records=records, abstains=abstains, abstain_codes={c: codes[c] for c in EPISODE_ABSTAIN_CODES},
                   failed_passes=len(failed), final_refusals=sum((p.get('settled') or {}).get('reason') == 'episode-final-refusal' for p in failed),
                   uncertain_terminals=len(lost), uncertain_committed=sum(u.get('outcome') == 'committed' for u in lost),
                   uncertain_absent=sum(u.get('outcome') == 'absent' for u in lost))
    if set(codes) - set(EPISODE_ABSTAIN_CODES):
        mismatches.append(dict(source='recorder trace', field='abstain reason_code outside the closed set', trace=sorted(set(codes) - set(EPISODE_ABSTAIN_CODES))))
    if uncertain != len(lost):
        mismatches.append(dict(source='recorder trace', field='episode-uncertain events', trace=uncertain, driver=len(lost)))
    mismatches += [dict(source='recorder driver receipt', field=k, trace=v, receipt=recorder.get(k)) for k, v in counted.items() if recorder.get(k) != v]
    return dict(passes=len(recorder['passes']), pass_classes=dict(classes), trace_counts=counted)


# ---------------------------------------------------------------- classes and pooling

def is_censored(attempt: dict) -> bool:
    return attempt['type'] == 'level-discard' and attempt['reason'] in CENSORED


def classify(result: dict) -> dict:
    """Commit-attempt and pass classes for one analysed run."""
    attempts, passes = result['commit_attempts'], result['passes']
    commits = sum(a['type'] == 'level-commit' for a in attempts)
    censored = sum(is_censored(a) for a in attempts)
    failures = sum(a['type'] == 'level-discard' and not is_censored(a) for a in attempts)
    by = Counter(p['pass_class'] for p in passes)
    actions = Counter(a['action'] for a in attempts if a['type'] == 'level-commit')
    reconciled = [u for p in passes for u in p['uncertain']]
    failed = [p for p in passes if p['pass_class'] == 'failed']
    value = dict(
        commits=commits, failures=failures, censored=censored, decided=commits + failures, passes=len(passes),
        committed_passes=by['committed'], discarded_only_passes=by['discarded_only'], abstained_passes=by['abstained'],
        censored_passes=by['censored'], failed_passes=by['failed'], uncertain_passes=by['uncertain'],
        provider_failed_passes=sum(provider_side(p['failure_reason']) for p in failed),
        abstains=sum(p['abstains'] for p in passes), start_abstains=sum(p['abstains'] for p in passes if p['reason'] == 'start'),
        commits_keep=actions['keep'], commits_replace=actions['replace'], commits_close=actions['close'],
        commits_other_action=commits - sum(actions[a] for a in ACTIONS),
        uncertain_committed=sum(u['outcome'] == 'committed' for u in reconciled), uncertain_absent=sum(u['outcome'] == 'absent' for u in reconciled),
        uncertain_unreconciled=sum(u['outcome'] not in ('committed', 'absent') for u in reconciled),
        uncertain_absent_commit_tool=sum(u['outcome'] == 'absent' and u['tool'] in COMMIT_TOOLS for u in reconciled),
        final_refusals=sum(p['failure_reason'] == 'level-final-refusal' for p in failed))
    assert sum(by[c] for c in PASS_CLASSES) == len(passes), 'every pass has one class'
    assert set(value) == set(SCALARS)
    return value


def load_criteria(path: Path) -> dict:
    """The stage's frozen decision thresholds; a missing, extra or mistyped key is refused, never defaulted."""
    value = read_json(path, 1 << 16)
    found = value.get('schema') if isinstance(value, dict) else None
    if found != CRITERIA_SCHEMA:
        raise UnsupportedTrace(f'{path}: criteria schema {found!r}, expected {CRITERIA_SCHEMA!r}')
    if set(value) != {'schema', *CRITERIA_KEYS}:
        raise UnsupportedTrace(f'{path}: criteria keys {sorted(set(value) ^ {"schema", *CRITERIA_KEYS})} are missing or unknown')
    if not all(type(value[k]) in (int, float) and not isinstance(value[k], bool) and value[k] >= 0 for k in CRITERIA_KEYS):
        raise UnsupportedTrace(f'{path}: every criterion is a non-negative number')
    if type(value['bootstrap_resamples']) is not int or value['bootstrap_resamples'] < 1 or type(value['bootstrap_seed']) is not int:
        raise UnsupportedTrace(f'{path}: bootstrap_seed and bootstrap_resamples are integers, the latter at least 1')
    return value


def analyse(paths: list[Path], criteria: dict, store_template: str | None = None) -> dict:
    """The pooled analysis of the given runs (a run is a cluster)."""
    runs = [analyse_run(Path(p), Path(store_template.format(run=Path(p).name)) if store_template else None) for p in paths]
    classes = [classify(r) for r in runs]
    seed, resamples = criteria['bootstrap_seed'], criteria['bootstrap_resamples']
    rated = lambda c: c['passes'] - c['censored_passes'] - c['uncertain_passes']
    measures = dict(commit_rate=(lambda c: c['commits'], lambda c: c['decided']),
                    pass_success=(lambda c: c['committed_passes'], rated),
                    pass_success_excluding_provider_failures=(lambda c: c['committed_passes'], lambda c: rated(c) - c['provider_failed_passes']),
                    abstain_rate=(lambda c: c['abstained_passes'], rated), failed_pass_rate=(lambda c: c['failed_passes'], rated))
    totals = {k: sum(c[k] for c in classes) for k in SCALARS}
    commit_moved = [a['inputs_since'] for r in runs for a in r['commit_attempts'] if a['type'] == 'level-commit' and a['inputs_since'] is not None]
    decided_moved = [a['inputs_since'] for r in runs for a in r['commit_attempts'] if a['inputs_since'] is not None and not is_censored(a)]
    stores_checked = bool(runs) and all(isinstance(r['content'], dict) for r in runs)
    pooled = dict(runs=len(runs), **totals)
    for name, (numerator, denominator) in measures.items():
        pooled[name] = ratio(classes, numerator, denominator)
        pooled[name + '_ci95'] = cluster_bootstrap(classes, lambda xs, n=numerator, d=denominator: ratio(xs, n, d), seed=seed, resamples=resamples)
    pooled.update(
        commit_rate_lower_bound=ratio(classes, lambda c: c['commits'], lambda c: c['decided'] + c['uncertain_absent_commit_tool']),
        commits_by_action=dict(keep=totals['commits_keep'], replace=totals['commits_replace'], close=totals['commits_close'], other=totals['commits_other_action']),
        abstain_codes=dict(Counter(a['reason_code'] for r in runs for a in r['abstentions'])),
        failed_by_reason=dict(Counter(p['failure_reason'] for r in runs for p in r['passes'] if p['pass_class'] == 'failed')),
        refusals_by_tool_field=dict(sum((Counter(r['refusals_by_tool_field']) for r in runs), Counter())),
        auditable_records=sum(r['content']['auditable_records'] for r in runs) if stores_checked else None,
        inputs_since_commits=summary(commit_moved), inputs_since_decided=summary(decided_moved),
        inputs_during_pass=summary([p['inputs_during_pass'] for r in runs for p in r['passes'] if p['inputs_during_pass'] is not None]),
        inputs_push_to_attempt=summary([p['inputs_push_to_attempt'] for r in runs for p in r['passes'] if p['inputs_push_to_attempt'] is not None]),
        pass_wall_seconds=summary([p['wall_seconds'] for r in runs for p in r['passes']]),
        requests_per_pass=summary([p['requests'] for r in runs for p in r['passes'] if p['requests'] is not None]),
        recorder_trace_counts={k: sum(r['recorder']['trace_counts'][k] for r in runs) for k in ('records', 'abstains', 'failed_passes', 'uncertain_terminals')},
        level_failures=[r['run'] for r in runs if r['level_failure']],
        receipt_count_mismatches=[dict(m, run=r['run']) for r in runs for m in r['receipt_mismatches']],
        custody_violations=sum(r['custody']['reader_operations'] + (r['custody']['reader_non_level_writes'] or 0)
                               + (r['custody']['reader_other_service_rows'] or 0) for r in runs))
    decided_ok = pooled['decided'] >= criteria['min_decided']
    auditable_ok = None if pooled['auditable_records'] is None else pooled['auditable_records'] >= criteria['min_auditable_records']
    staleness = {r['staleness_inputs'] for r in runs}
    p95 = pooled['inputs_since_commits']['p95']
    decision = dict(
        E_decided_ok=decided_ok, E_auditable_ok=auditable_ok, E_minimum_data=False if not decided_ok else auditable_ok,
        R1_commit_rate_ok=pooled['commit_rate'] is not None and pooled['commit_rate'] >= criteria['min_commit_rate'],
        R2_coupling_ok=p95 is not None and p95 < criteria['max_commit_inputs_since_p95'],
        # A commit requires the actor to have moved fewer than S inputs past the read, so with the limit at or above S
        # the commit-only p95 cannot reach it and R2 cannot fire.
        R2_vacuous=bool(staleness) and None not in staleness and criteria['max_commit_inputs_since_p95'] >= max(staleness),
        counts_consistent=pooled['receipt_count_mismatches'] == [],
        R4_custody_ok=(pooled['custody_violations'] == 0) if all(r['custody']['reader_non_level_writes'] is not None for r in runs) else None)
    return dict(schema=SCHEMA, notes=NOTES, pooled=pooled, decision_inputs=decision, runs=runs, classes=classes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('output', type=Path)
    parser.add_argument('sessions', type=Path, nargs='+')
    parser.add_argument('--criteria', type=Path, required=True)
    parser.add_argument('--store-template', help='retained player store path containing {run}; omitted: no store checks')
    arguments = parser.parse_args(argv)
    try:
        criteria = load_criteria(arguments.criteria)
        value = analyse(arguments.sessions, criteria, arguments.store_template)
        value.update(criteria_sha256=sha256(arguments.criteria), code_sha256=sha256(Path(__file__)), criteria=criteria)
        with arguments.output.open('x') as stream:
            json.dump(value, stream, indent=1)
    except UnsupportedTrace as error:
        print(f'unsupported: {error}', file=sys.stderr)
        return 2
    except (ControlError, OSError, ValueError, KeyError, sqlite3.Error) as error:
        print(f'Level stage analysis failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps(dict(pooled=value['pooled'], decision_inputs=value['decision_inputs'], notes=NOTES), indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
