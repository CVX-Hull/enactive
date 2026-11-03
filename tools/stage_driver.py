"""Serialized, stop-never-retry driver for a pre-registered stage of finite campaign runs.

A claim-deciding stage freezes its inputs, limits and stop rules before it runs (S-EVIDENCE, evidence cadence). This
module is the part of such a driver that does not change from stage to stage: the run order, the spend accounting, the
stop rules and the cleanup on every exit. Everything stage-, provider- or game-specific enters through the `ports` object
(below), which the stage's own thin binding supplies; the binding, its frozen registry and its outputs stay in
`.runtime`. The driver sends no game input, edits no save and never retries a run.

Driver rules (each is a stop reason; the driver stops, never retries, and settles accounting and state on every exit):
- before each batch: reprice; any changed frozen price stops the stage (exit 3);
- before each run: wait `settle_seconds` so late charges land, read the account, settle the previous run, wait for a
  quiet machine (`load_gate`, at most 30 minutes), read again (the gap is unattributed spend), then check the run
  limit, the open-record rule, the stage cap, the item cap and the balance against one worst-case run;
- state: a restoring stage verifies the frozen state and restores the previous run's retained copy when it differs; a
  `persistent` stage verifies the live state against the previous session's retained copy and never restores or edits it;
- a run is charged `attempts_charged` from its receipt, else the whole `campaign_attempts` allocation; its actual cost
  is the whole-account delta from its own pre-run reading to the next, an upper bound on a shared account;
- after a run: an incomplete run stops the stage unless it is a provider-side infrastructure failure
  (`infrastructure_failure`, at most `max_infrastructure_failures` per stage, never two in a row) whose custody is
  intact; a watcher failure, a check gap above `max_check_gap_seconds`, a layer failure or a tripped refusal breaker
  stops it after the run, which is retained and reported;
- a persistent stage's session that is not complete stops the stage, since continuity cannot be repaired;
- any record still `launched` when the driver exits (an exception came before it was assessed) is charged its whole
  allocation and left open for the owner: `interrupted-possibly-live` when it has no receipt, which may still be live, so
  nothing is settled or restored under it, else `interrupted-unassessed`. The next start refuses to go on under it.

`ports` supplies (all synchronous): `read_account() -> {total_usage, total_credits}`; `reprice() -> changed prices`;
`machine_load() -> float`; `state_verify(carried=None) -> bool`; `state_restore(label) -> bool`;
`state_retain(label) -> int`; `retain_labels(name) -> (continuation_label, evidence_label)` (persistent stages only, asked
before the run is built, so a binding that cannot name them stops the stage before any effect);
`build(run, ceiling_usd) -> bool`; `start_watcher(name) -> handle` with `wait(timeout) -> int` and
`terminate()`; `launch(run) -> int`; `receipt(name) -> dict | None`; `assess(name, receipt) -> Assessment`;
`extension_needed(stage_runs) -> (needed, description)`; `excluded_custody(name) -> int | None`; `sleep(seconds)`;
`clock() -> float`.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import fcntl
import re
from pathlib import Path
from typing import Callable, Sequence

ACCOUNTING_SCHEMA = 'stage-accounting/2'
FROZEN_KEYS = ('schema', 'stage', 'item', 'max_runs', 'base_runs', 'batch_size', 'per_run_worst_case_usd', 'stage_cap_usd', 'item_cap_usd',
               'overhead_ceilings_usd', 'uncertainty_headroom_usd',
               'campaign_attempts', 'load_gate', 'continuity', 'settle_seconds', 'max_check_gap_seconds', 'max_infrastructure_failures',
               'provider_failure_reasons')
# The settled reasons `infrastructure_failure` knows how to confirm from a host trace; a stage freezes which it excludes.
PROVIDER_REASONS = ('provider-error', 'request-timeout')
QUIET_WAIT_MINUTES = 30
WATCHER_TIMEOUT_SECONDS = 60
# Reasons that end a stage normally (exit 0); every other stop reason is exit 4, a price change 3, an exception 5.
NORMAL_STOPS = ('run limit', 'stage cap', 'item cap')


class StageError(ValueError):
    """A frozen input or an accounting file the driver does not accept."""


@dataclass
class Assessment:
    """What the stage's binding judged of one launched run, from its retained artifacts.

    `complete` is the stage's inclusion rule (a clean exit included when it holds); `breaker` is the refusal circuit
    breaker's result (`tripped`, `worst`, `successes`, `refusals`); `provider_ending` is the output of
    `infrastructure_failure`, None when the run is not an excluded provider-side failure.
    """
    complete: bool
    outcome: str | None = None
    failure: str | None = None
    quiescent: bool = False
    clean_exit: bool = False
    clean_facts: dict | None = None
    max_check_gap_s: float | None = None
    breaker: dict = field(default_factory=lambda: dict(tripped=False))
    provider_ending: str | None = None
    attempts_charged: int | None = None


def load_frozen(path: Path) -> dict:
    """The stage's frozen registry values; a missing, extra or mistyped key is refused, never defaulted."""
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or set(value) != set(FROZEN_KEYS):
        raise StageError(f'{path}: frozen keys must be exactly {sorted(FROZEN_KEYS)}')
    if value['schema'] != 'stage-budget-registry/1':
        raise StageError(f'{path}: unsupported stage budget registry')
    for key in ('stage', 'item'):
        if type(value[key]) is not str or not value[key].strip():
            raise StageError(f'{path}: {key} is a non-empty string')
    for key in ('max_runs', 'base_runs', 'batch_size', 'campaign_attempts', 'settle_seconds', 'max_infrastructure_failures'):
        if type(value[key]) is not int or value[key] < 0:
            raise StageError(f'{path}: {key} is a non-negative integer')
    for key in ('load_gate', 'max_check_gap_seconds'):
        if type(value[key]) not in (int, float) or not value[key] >= 0 or value[key] == float('inf'):
            raise StageError(f'{path}: {key} is a finite non-negative number')
    reasons = value['provider_failure_reasons']
    if not (isinstance(reasons, list) and len(set(reasons)) == len(reasons) and set(reasons) <= set(PROVIDER_REASONS)):
        raise StageError(f'{path}: provider_failure_reasons is a list of distinct reasons from {list(PROVIDER_REASONS)}')
    overhead = value['overhead_ceilings_usd']
    if not isinstance(overhead, dict) or any(not name or not isinstance(name, str) for name in overhead):
        raise StageError(f'{path}: overhead assignments must be named')
    for key, amount in [(k, value[k]) for k in ('per_run_worst_case_usd', 'stage_cap_usd', 'item_cap_usd',
                       'uncertainty_headroom_usd')] + list(overhead.items()):
        if type(amount) is not str or not Decimal(amount).is_finite() or Decimal(amount) < 0:
            raise StageError(f'{path}: {key} is a non-negative decimal string')
    if (Decimal(value['per_run_worst_case_usd']) * value['max_runs']
            + sum(map(Decimal, overhead.values())) + Decimal(value['uncertainty_headroom_usd'])
            > Decimal(value['stage_cap_usd'])):
        raise StageError(f'{path}: finite assignments exceed the stage cap')
    if value['continuity'] not in (None, 'persistent'):
        raise StageError(f'{path}: unknown continuity {value["continuity"]!r}')
    if value['continuity'] == 'persistent' and value['max_runs'] != value['base_runs']:
        raise StageError(f'{path}: a persistent stage has no extension runs')
    if value['base_runs'] > value['max_runs'] or value['batch_size'] < 1:
        raise StageError(f'{path}: base_runs <= max_runs and batch_size >= 1')
    return value


# ---------------------------------------------------------------- freeze verification

def verify_freeze(expected: dict[str, str], read: Callable[[str], bytes | None]) -> list[str]:
    """Problems in a stage's frozen digests: `expected` maps a name to its sha256, `read(name)` gives its current bytes.

    The binding decides where bytes come from (a file as committed at the frozen source commit, or on disk); None is a
    missing file. An empty list means every digest matches.
    """
    problems = []
    for name, digest in sorted(expected.items()):
        data = read(name)
        found = hashlib.sha256(data).hexdigest() if data is not None else None
        if found != digest:
            problems.append(f'{name}: frozen {digest}, found {found}')
    return problems


# ---------------------------------------------------------------- accounting

def new_accounting(*, spend_baseline_usd: str, item_actual_usd: str, prior_uncertainty_usd: str,
                   cumulative_attempts: int, last_usage) -> dict:
    return dict(schema=ACCOUNTING_SCHEMA, actual_spend_baseline_usd=spend_baseline_usd, item_actual_usd=item_actual_usd,
                prior_uncertainty_usd=prior_uncertainty_usd,
                cumulative_attempts=cumulative_attempts, stage_actual_usd={}, last_usage=last_usage, runs=[],
                overhead=[], unattributed=[])


def load_accounting(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get('schema') != ACCOUNTING_SCHEMA:
        raise StageError(f'{path}: accounting schema {value.get("schema") if isinstance(value, dict) else value!r}, expected {ACCOUNTING_SCHEMA!r}')
    hold = value.get('prior_uncertainty_usd')
    if not isinstance(hold, str) or not re.fullmatch(r'(0|[1-9][0-9]*)(?:\.[0-9]+)?', hold):
        raise StageError(f'{path}: prior item uncertainty must be an explicit nonnegative decimal string')
    return value


def save_accounting(path: Path, value: dict) -> None:
    """Atomic publication on one filesystem."""
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=1) + '\n')
    os.replace(temporary, path)


def charge(acc: dict, stage: str, delta: Decimal) -> None:
    acc['actual_spend_baseline_usd'] = str(Decimal(acc['actual_spend_baseline_usd']) + delta)
    acc['item_actual_usd'] = str(Decimal(acc['item_actual_usd']) + delta)
    acc['stage_actual_usd'][stage] = str(Decimal(acc['stage_actual_usd'].get(stage, '0')) + delta)


def settle(acc: dict, reading: dict, stage: str) -> dict:
    """Close every open run against this reading and roll the baselines forward.

    Spend between two readings with no open run (late charges, the load wait, other use of the shared account) belongs to
    no run but still counts against both caps, so the accounting stays an upper bound.
    """
    usage = Decimal(str(reading['total_usage']))
    if not usage.is_finite() or usage < 0 or (acc.get('last_usage') is not None
            and usage < Decimal(str(acc['last_usage']))):
        raise StageError('Provider account usage counter is invalid or decreased')
    open_runs = [r for r in acc['runs'] if 'account_after' not in r]
    for run in open_runs:
        delta = usage - Decimal(str(run['account_before']))
        run['account_after'] = reading['total_usage']
        run['actual_usd'] = str(delta)
        charge(acc, run['stage'], delta)
    if not open_runs and acc.get('last_usage') is not None:
        gap = usage - Decimal(str(acc['last_usage']))
        if gap:
            acc['unattributed'].append(dict(stage=stage, **{'from': acc['last_usage']}, to=reading['total_usage'], usd=str(gap)))
            charge(acc, stage, gap)
    acc['last_usage'] = reading['total_usage']
    return acc


def account_remaining(reading: dict) -> Decimal:
    try:
        credits, usage = (Decimal(str(reading[key])) for key in ('total_credits', 'total_usage'))
    except (KeyError, InvalidOperation):
        raise StageError('Account counters must be finite nonnegative decimals') from None
    if any(not value.is_finite() or value < 0 for value in (credits, usage)):
        raise StageError('Account counters must be finite nonnegative decimals')
    return credits - usage


def cap_stop(acc: dict, frozen: dict, reading: dict, *, overhead: str | None = None) -> str | None:
    """The stop reason when one more worst-case run would pass a cap or the balance, else None."""
    worst, stage = Decimal(frozen['per_run_worst_case_usd']), frozen['stage']
    spent_overhead = {r['name'] for r in acc['overhead'] if r['stage'] == stage}
    reserved = frozen['overhead_ceilings_usd']
    if overhead is not None:
        worst = Decimal(reserved[overhead])
    assigned = sum(Decimal(r['assigned_ceiling_usd']) for r in acc['runs'] + acc['overhead'] if r['stage'] == stage)
    held = Decimal(frozen['uncertainty_headroom_usd']) + sum(
        Decimal(cap) for name, cap in reserved.items() if name not in spent_overhead and name != overhead)
    actual = Decimal(acc['stage_actual_usd'].get(stage, '0'))
    if actual > assigned:
        return f'unexplained account usage: observed {actual}, assigned {assigned}'
    if max(assigned, actual) + worst + held > Decimal(frozen['stage_cap_usd']):
        return f"stage cap (stage actual {acc['stage_actual_usd'].get(stage, '0')})"
    if (Decimal(acc['item_actual_usd']) - actual + Decimal(acc['prior_uncertainty_usd'])
            + Decimal(frozen['stage_cap_usd']) > Decimal(frozen['item_cap_usd'])):
        return f"item cap ({frozen['item']} actual {acc['item_actual_usd']})"
    remaining = account_remaining(reading)
    if remaining < worst:
        return f'balance below one worst-case run ({remaining} remaining); escalate for top-up'
    return None


# ---------------------------------------------------------------- provider-side failure evidence

def parse_trace(text: str) -> list[dict] | None:
    """The rows of a host trace, or None when any line is not a JSON object (the evidence is then unknown)."""
    rows = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict):
            return None
        rows.append(value)
    return rows


def provider_evidence(rows: Sequence[dict] | None, ending: str) -> str | None:
    """Provider-side evidence for the actor's last logical request (its attempts and retry) only.

    A 5xx or 429 response, or a fetch rejection; or, for a request timeout, an HTTP 200 stream that delivered no
    provider events and no refusal. A host crash or a 4xx refusal is none.
    """
    if not rows:
        return None
    starts = [r for r in rows if r.get('type') == 'request-start']
    if not starts:
        return None
    logical = starts[-1].get('logical_request_id')
    attempts = {r.get('request_id') for r in starts if r.get('logical_request_id') == logical}
    last = [r for r in rows if r.get('request_id') in attempts]
    statuses = [r.get('status') for r in last if r.get('type') in ('response-headers', 'provider-refusal')]
    if ending == 'provider-error':
        if any(type(s) is int and (s >= 500 or s == 429) for s in statuses):
            return 'provider status'
        if any(r.get('type') == 'provider-retry' and r.get('retry_class') == 'pre-header-rejection' for r in last):
            return 'fetch rejection'
        return None
    final = starts[-1].get('request_id')
    headers = [r.get('status') for r in last if r.get('type') == 'response-headers' and r.get('request_id') == final]
    refused = any(r.get('type') == 'provider-refusal' for r in last)
    complete = [r for r in last if r.get('type') == 'response-complete' and r.get('request_id') == final]
    if (ending == 'request-timeout' and headers == [200] and not refused and complete
            and (complete[-1].get('response_progress') or {}).get('provider_events') == 0):
        return 'stream with no provider events'
    return None


def infrastructure_failure(receipt: dict | None, quiescent: bool, session_present: bool, trace_rows: Sequence[dict] | None,
                           reasons: Sequence[str]) -> str | None:
    """An excludable run: the deciding host ended on one of the stage's frozen `provider_failure_reasons`, shown to be
    provider-side in its own trace, and every custody and cleanup fact still holds. Any other incompleteness returns
    None, which stops the stage."""
    if not receipt or receipt.get('outcome') != 'incomplete' or not quiescent or not session_present:
        return None
    if not all(receipt.get(f) is True for f in ('deciding_hosts_quiescent', 'native_absence_verified', 'input_authority_revoked')):
        return None
    actors = (receipt.get('driver') or {}).get('actors') or []
    if len(actors) != 1 or actors[0].get('orchestration_error') or actors[0].get('accounting_complete') is not True:
        return None
    reason = (actors[0].get('settled') or {}).get('reason') or ''
    if reason not in reasons:
        return None
    evidence = provider_evidence(trace_rows, reason)
    return None if evidence is None else f'{reason} ({evidence})'


# ---------------------------------------------------------------- the driver

class StageDriver:
    """Runs batches of serialized runs of one stage; see the module docstring for the rules and the `ports` object."""

    def __init__(self, directory: Path, accounting_path: Path, frozen: dict, ports) -> None:
        self.directory, self.accounting_path, self.frozen, self.ports = directory, accounting_path, frozen, ports
        self.persistent = frozen['continuity'] == 'persistent'
        (directory / 'balance').mkdir(exist_ok=True)

    # --- records

    def note(self, **fields) -> None:
        fields['wall'] = self.ports.clock()
        with (self.directory / 'run-log.jsonl').open('a') as stream:
            stream.write(json.dumps(fields) + '\n')

    def balance(self, tag: str) -> dict:
        reading = dict(self.ports.read_account(), read_wall=self.ports.clock())
        (self.directory / 'balance' / f'{tag}.json').write_text(json.dumps(reading) + '\n')
        account_remaining(reading)
        return reading

    def settled(self, reading: dict) -> dict:
        acc = settle(load_accounting(self.accounting_path), reading, self.frozen['stage'])
        save_accounting(self.accounting_path, acc)
        return acc

    def quiet_machine(self) -> tuple[float, str | None]:
        """Wait (at most 30 minutes) for the 1-minute load to fall below the frozen gate."""
        gate = float(self.frozen['load_gate'])
        load = self.ports.machine_load()
        for _ in range(QUIET_WAIT_MINUTES):
            if load < gate:
                return load, None
            self.note(event='load-wait', load=load, gate=gate)
            self.ports.sleep(60)
            load = self.ports.machine_load()
        return load, None if load < gate else f'machine overloaded (1-minute load {load:.1f} at or above {gate:.1f} for {QUIET_WAIT_MINUTES} min)'

    # --- one run

    def one_run(self, run: int) -> str | None:
        """Returns None to continue, or a stop reason."""
        frozen, stage = self.frozen, self.frozen['stage']
        name = f'{stage}-{run:02d}'
        if run > frozen['max_runs']:
            return 'run limit'
        acc = load_accounting(self.accounting_path)
        open_records = [r['run'] for r in acc['runs'] if r.get('status') != 'closed']
        open_records += [r['name'] for r in acc['overhead'] if r.get('status') != 'closed']
        if open_records:
            # A run left open may still be live: never settle, restore or launch under it.
            return f'open run record {open_records}; the owner decides any recovery'
        if any(r['run'] == name for r in acc['runs']):
            return f'assignment already used: {name}'
        stage_runs = [r for r in acc['runs'] if r.get('stage') == stage]
        if run > frozen['base_runs'] and not self.persistent:
            needed, description = self.ports.extension_needed(stage_runs)
            if not needed:
                return f'run limit (extension not needed: {description})'
        if acc['runs']:
            self.ports.sleep(frozen['settle_seconds'])
        # Settle before any load wait, so waiting is never charged to the previous run.
        before = self.balance(f'{name}-before')
        acc = self.settled(before)
        load, busy = self.quiet_machine()
        if busy:
            return busy
        # A second reading after any wait; settle() counts the gap as unattributed spend.
        before = self.balance(f'{name}-before-launch')
        acc = self.settled(before)
        stop = cap_stop(acc, frozen, before)
        if stop:
            return stop
        remaining = account_remaining(before)
        stage_runs = [r for r in acc['runs'] if r.get('stage') == stage]
        if self.persistent and stage_runs:
            carried = stage_runs[-1]
            if carried.get('complete') is not True:
                return f"previous persistent session {carried['run']} is not complete; the owner decides"
            if carried.get('persistent_continuation') is not True:
                # A session kept only as evidence (for example complete but with a level that was not quiescent) is never carried.
                return f"previous persistent session {carried['run']} is not a continuation state; the owner decides"
            if carried.get('persistent_retained') is None:
                return f"previous persistent session {carried['run']} was not retained; the owner decides"
            if not self.ports.state_verify(carried['persistent_retained']):
                return f"carried state differs from the retained post-session copy of {carried['run']}"
        elif not self.ports.state_verify():
            previous = acc['runs'][-1]['run'] if acc['runs'] else 'pre-stage'
            if not self.ports.state_restore(f'after-{previous}') or not self.ports.state_verify():
                return 'state restore/verify failed'
        labels = None
        if self.persistent:
            # Asked before any effect: a binding that cannot name the retained-state labels stops the stage here.
            labels = self.ports.retain_labels(name)
            if not (isinstance(labels, tuple) and len(labels) == 2 and all(type(x) is str and x for x in labels) and labels[0] != labels[1]):
                raise StageError('A persistent stage needs the binding to name two distinct retained-state labels per session')
        ceiling = Decimal(frozen['per_run_worst_case_usd'])
        if not self.ports.build(run, ceiling):
            return 'build failed'
        acc = load_accounting(self.accounting_path)
        acc['runs'].append(dict(run=name, stage=stage, account_before=before['total_usage'], attempts=None, complete=False,
                                assigned_ceiling_usd=frozen['per_run_worst_case_usd'],
                                status='launched', load_at_start=load))
        save_accounting(self.accounting_path, acc)
        watcher = self.ports.start_watcher(name)
        self.note(event='launch', run=name, balance_before=before['total_usage'], remaining=str(remaining))
        launcher_rc = self.ports.launch(run)
        try:
            watcher_rc = watcher.wait(WATCHER_TIMEOUT_SECONDS)
        except TimeoutError:
            watcher.terminate()
            watcher_rc = 'timeout'
        receipt = self.ports.receipt(name)
        money = receipt.get('accounting') if isinstance(receipt, dict) else None
        charged_nano = money.get('charged_nano_usd') if isinstance(money, dict) else None
        ceiling_nano = str(int(ceiling * 10**9))
        if (not isinstance(money, dict) or receipt.get('schema') != 'campaign-receipt/3'
                or money.get('money_complete') is not True or money.get('run_ceiling_nano_usd') != ceiling_nano
                or not isinstance(charged_nano, str) or not re.fullmatch(r'0|[1-9][0-9]{0,17}', charged_nano)
                or int(charged_nano) > int(ceiling_nano)):
            self.note(event='monetary-receipt-refused', run=name, expected_ceiling_nano_usd=ceiling_nano)
            return f'campaign monetary receipt unverified ({name})'
        a = self.ports.assess(name, receipt)
        custody = ('native_absence_verified', 'deciding_hosts_quiescent', 'input_authority_revoked')
        if not a.quiescent or any(receipt.get(key) is not True for key in custody):
            self.note(event='campaign-custody-unverified', run=name)
            return f'campaign custody unverified ({name})'
        # Persistent mode keeps this session's post-session state (a copy; the live state stays) once the native process is
        # verified absent; no receipt, or a native process not verified gone, means the state may still be changing.
        # Only a complete session with a quiescent level is a continuation state; any other is kept as evidence, never carried.
        retain_label = None if labels is None else labels[0] if a.complete and a.quiescent else labels[1]
        retain_rc = (self.ports.state_retain(retain_label)
                     if self.persistent and receipt is not None and receipt.get('native_absence_verified') is True else None)
        charged = a.attempts_charged if a.attempts_charged is not None else frozen['campaign_attempts']
        acc = load_accounting(self.accounting_path)
        record = acc['runs'][-1]
        assert record['run'] == name
        record.update(attempts=charged, complete=a.complete, launcher_rc=launcher_rc, watcher_rc=watcher_rc,
                      charged_nano_usd=charged_nano,
                      max_check_gap_s=a.max_check_gap_s, outcome=a.outcome, failure=a.failure, quiescent=a.quiescent,
                      included_clean_exit=a.clean_exit, refusal_circuit_breaker=a.breaker['tripped'], status='closed')
        if self.persistent:
            record.update(persistent_retain_rc=retain_rc, persistent_retained=retain_label if retain_rc is not None else None,
                          persistent_continuation=retain_label == labels[0])
        if a.clean_exit:
            record['clean_exit_facts'] = a.clean_facts
        acc['cumulative_attempts'] += charged
        save_accounting(self.accounting_path, acc)
        self.note(event='closed', run=name, complete=a.complete, outcome=a.outcome, attempts=charged, watcher_rc=watcher_rc,
                  max_check_gap_s=a.max_check_gap_s, failure=a.failure, included_clean_exit=a.clean_exit)
        tripped = None
        if a.breaker['tripped']:
            tripped = 'refusal circuit breaker ({tool} field {field} refused {count} times, no successful call of that tool)'.format(**a.breaker['worst'])
            self.note(event='circuit-breaker', run=name, successes=a.breaker.get('successes'), worst=a.breaker['worst'],
                      refusals=a.breaker.get('refusals'))
        if self.persistent:
            if retain_rc not in (None, 0):
                return f'persistent session {name}: retaining its post-session state failed (rc {retain_rc})'
            if not a.complete:
                # Continuity cannot be repaired by the driver, and the provider-failure exclusion does not apply.
                return f'persistent session {name} not complete ({a.outcome}); continuity is broken, the owner decides'
        if not a.complete:
            if a.provider_ending is None:
                return f'run not complete ({a.outcome})'
            violations = self.ports.excluded_custody(name)
            if violations != 0:
                return f"excluded run {name} custody {'unknown' if violations is None else f'{violations} violations'} (R4)"
            acc = load_accounting(self.accounting_path)
            excluded = acc.setdefault('excluded_infrastructure', {}).setdefault(stage, [])
            excluded.append(dict(run=name, host_ending=a.provider_ending))
            acc['runs'][-1]['excluded'] = f'infrastructure: {a.provider_ending}'
            save_accounting(self.accounting_path, acc)
            self.note(event='excluded-infrastructure', run=name, host_ending=a.provider_ending, stage_count=len(excluded))
            mine = [r for r in acc['runs'] if r.get('stage') == stage]
            if len(excluded) > frozen['max_infrastructure_failures']:
                return f"infrastructure failures exceed {frozen['max_infrastructure_failures']} in this stage ({a.provider_ending})"
            if len(mine) >= 2 and all(r.get('excluded') for r in mine[-2:]):
                return f'two consecutive infrastructure failures ({a.provider_ending})'
        if watcher_rc != 0:
            return f'watcher failed ({watcher_rc})'
        gap = a.max_check_gap_s
        if gap is None or gap > frozen['max_check_gap_seconds']:
            return f"check gap {gap} s exceeds {frozen['max_check_gap_seconds']} s (deviation to record)"
        if a.failure:
            return f'layer failure recorded ({a.failure})'
        return tripped

    # --- the stage

    @contextmanager
    def _lock(self):
        lock_path = self.accounting_path.with_suffix('.lock')
        with lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StageError('Another stage driver holds the accounting ledger') from None
            yield

    def run_overhead(self, name: str, action: Callable[[Decimal], dict]) -> dict:
        """Assign one frozen audit/compatibility ceiling before invoking its guarded host."""
        frozen = self.frozen
        stage = frozen['stage']
        with self._lock():
            acc = load_accounting(self.accounting_path)
            if (name not in frozen['overhead_ceilings_usd']
                    or any(r['stage'] == stage and r['name'] == name for r in acc['overhead'])
                    or any(r['status'] != 'closed' for r in acc['runs'] + acc['overhead'])):
                raise StageError('Overhead assignment is unknown, already used or blocked by an open record')
            if changed := self.ports.reprice():
                raise StageError(f'Price changed before overhead: {changed}')
            before = self.balance(f'overhead-{name}-before')
            acc = self.settled(before)
            if reason := cap_stop(acc, frozen, before, overhead=name):
                raise StageError(reason)
            ceiling = frozen['overhead_ceilings_usd'][name]
            record = dict(name=name, stage=stage, assigned_ceiling_usd=ceiling, status='launched')
            acc['overhead'].append(record)
            save_accounting(self.accounting_path, acc)
            result = action(Decimal(ceiling))
            charged = result.get('charged_nano_usd') if isinstance(result, dict) else None
            if (not isinstance(charged, str) or not re.fullmatch(r'0|[1-9][0-9]{0,17}', charged)
                    or int(charged) > Decimal(ceiling) * 10**9 or result.get('quiescent') is not True
                    or result.get('accounting_complete') is not True):
                raise StageError('Overhead accounting or custody is unresolved')
            record.update(status='closed', result=result)
            save_accounting(self.accounting_path, acc)
            self.ports.sleep(frozen['settle_seconds'])
            settled = self.settled(self.balance(f'overhead-{name}-after'))
            if self.unexplained_usage(settled):
                raise StageError('Unexplained account usage after overhead')
            return result

    def unexplained_usage(self, acc: dict) -> bool:
        stage = self.frozen['stage']
        assigned = sum(Decimal(r['assigned_ceiling_usd'])
                       for r in acc['runs'] + acc['overhead'] if r['stage'] == stage)
        return Decimal(acc['stage_actual_usd'].get(stage, '0')) > assigned

    def run(self, first_run: int, batches: int) -> int:
        """Run up to `batches` batches from `first_run`; returns the exit code (0 normal stop, 3 price, 4 stop rule, 5 exception)."""
        with self._lock():
            return self._run_locked(first_run, batches)

    def _run_locked(self, first_run: int, batches: int) -> int:
        frozen = self.frozen
        run, reason, rc = first_run, 'batches done', 0
        try:
            for _ in range(batches):
                changed = self.ports.reprice()
                if changed:
                    reason, rc = f'price changed: {changed}', 3
                    break
                self.note(event='batch-start', batch_first_run=run)
                for _ in range(frozen['batch_size']):
                    stop = self.one_run(run)
                    if stop:
                        reason, rc = stop, 0 if stop.startswith(NORMAL_STOPS) else 4
                        break
                    run += 1
                if rc or reason != 'batches done':
                    break
        except BaseException as exc:  # stop, never retry; includes KeyboardInterrupt
            reason, rc = f'exception: {exc!r}', 5
        finally:
            rc = self.close(run, reason, rc)
        return rc

    def close(self, run: int, reason: str, rc: int) -> int:
        """Cleanup on every exit path: settle, restore or keep the carried state, and record the exit."""
        acc = load_accounting(self.accounting_path)
        last = acc['runs'][-1] if acc['runs'] else None
        # Any record still `launched` was never assessed (an exception came first): it is charged its whole allocation, so
        # the attempt count stays an upper bound, and it stays open for the owner.
        unclosed = [r for r in acc['runs'] if r.get('status') == 'launched']
        for record in unclosed:
            record['attempts'] = self.frozen['campaign_attempts']
            record['status'] = ('interrupted-possibly-live' if self.ports.receipt(record['run']) is None
                                else 'interrupted-unassessed')
            acc['cumulative_attempts'] += record['attempts']
        if unclosed:
            save_accounting(self.accounting_path, acc)
        if last and self.ports.receipt(last['run']) is None:
            # The custodian runs in its own session and may still be playing: do not settle or restore under it.
            self.note(event='left-open', run=last['run'], reason='no receipt; run may still be live')
        else:
            if any('account_after' not in r for r in acc['runs']):
                self.ports.sleep(self.frozen['settle_seconds'])
                try:
                    acc = self.settled(self.balance(f'settle-after-run-{run:02d}'))
                except (StageError, OSError, ValueError) as exc:
                    self.note(event='account-settlement-failed', preceding_reason=reason, failure=repr(exc))
                    reason, rc = 'final account settlement failed', 4
            if last and self.persistent:
                retained = last.get('persistent_retained')
                self.note(event='carried-state-kept', retained=retained,
                          verified=None if retained is None else self.ports.state_verify(retained))
            elif last and last.get('status') == 'closed' and not self.ports.state_verify():
                self.note(event='final-restore', retained=f"after-{last['run']}", restored=self.ports.state_restore(f"after-{last['run']}"))
        if self.unexplained_usage(acc):
            self.note(event='unexplained-account-usage', preceding_reason=reason)
            reason, rc = 'unexplained account usage above assigned ceilings', 4
        self.note(event='driver-exit', reason=reason, rc=rc, next_run=run, item_actual_usd=acc['item_actual_usd'],
                  stage_actual_usd=acc['stage_actual_usd'].get(self.frozen['stage']), runs=len(acc['runs']))
        return rc
