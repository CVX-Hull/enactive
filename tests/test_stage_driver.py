"""The stage driver's accounting, stop rules and cleanup against scripted ports: no provider, game, state or process."""
from decimal import Decimal
import json

import pytest

from tools import stage_driver as sd
from tools.stage_driver import Assessment, StageDriver, StageError

FROZEN = dict(stage='s1', item='#1', max_runs=3, base_runs=3, batch_size=3, per_run_worst_case_usd='10', stage_cap_usd='100',
              item_cap_usd='1000', campaign_attempts=50, load_gate=8, continuity=None, settle_seconds=60, max_check_gap_seconds=45,
              max_infrastructure_failures=2, provider_failure_reasons=['provider-error', 'request-timeout'])
REASONS = FROZEN['provider_failure_reasons']


class Watcher:
    def __init__(self, rc, timeout=False):
        self.rc, self.timeout, self.terminated = rc, timeout, False

    def wait(self, seconds):
        if self.timeout:
            raise TimeoutError
        return self.rc

    def terminate(self):
        self.terminated = True


class Ports:
    """Scripted ports: `spend[run]` is charged to the shared account while the run launches."""
    def __init__(self, spend=None, assessments=None, *, balance=10 ** 6):
        self.usage, self.credits = Decimal('100'), Decimal(balance)
        self.spend, self.assessments = spend or {}, assessments or {}
        self.calls, self.receipts, self.loads = [], {}, []
        self.verified, self.restored, self.retained = [], [], []
        self.verify_results, self.restore_ok, self.build_ok = [], True, True
        self.watcher_rc, self.watcher_timeout, self.prices, self.custody = 0, False, {}, 0
        self.wall, self.extension = 0.0, (True, 'needed')
        self.explode_on_launch = False
        self.retain_rc = 0

    def read_account(self):
        return dict(total_usage=str(self.usage), total_credits=str(self.credits))

    def reprice(self):
        return self.prices

    def machine_load(self):
        return self.loads.pop(0) if self.loads else 1.0

    def state_verify(self, carried=None):
        self.verified.append(carried)
        return self.verify_results.pop(0) if self.verify_results else True

    def state_restore(self, label):
        self.restored.append(label)
        return self.restore_ok

    def retain_labels(self, name):
        return (f'after-{name}', f'after-{name}-evidence')

    def state_retain(self, label):
        self.retained.append(label)
        return self.retain_rc

    def build(self, run):
        self.calls.append(('build', run))
        return self.build_ok

    def start_watcher(self, name):
        return Watcher(self.watcher_rc, self.watcher_timeout)

    def launch(self, run):
        self.calls.append(('launch', run))
        if self.explode_on_launch:
            raise RuntimeError('launcher died')
        self.usage += Decimal(self.spend.get(run, '5'))
        self.receipts[f's1-{run:02d}'] = dict(native_absence_verified=True)
        return 0

    def receipt(self, name):
        return self.receipts.get(name)

    def assess(self, name, receipt):
        run = int(name.rsplit('-', 1)[1])
        return self.assessments.get(run, good(run))

    def extension_needed(self, stage_runs):
        return self.extension

    def excluded_custody(self, name):
        return self.custody

    def sleep(self, seconds):
        self.calls.append(('sleep', seconds))

    def clock(self):
        self.wall += 1
        return self.wall


def good(run=1, **changes):
    return Assessment(complete=True, outcome='host_completed_unassessed', quiescent=True, max_check_gap_s=20.0, attempts_charged=10,
                      **changes)


def make(tmp_path, ports, **frozen):
    directory = tmp_path / 's1'
    directory.mkdir(exist_ok=True)
    path = tmp_path / 'accounting.json'
    if not path.exists():
        sd.save_accounting(path, sd.new_accounting(spend_baseline_usd='50', item_actual_usd='50', cumulative_attempts=7, last_usage='100'))
    return StageDriver(directory, path, dict(FROZEN, **frozen), ports), path


def log(tmp_path):
    return [json.loads(line) for line in (tmp_path / 's1/run-log.jsonl').read_text().splitlines()]


def reasons(tmp_path):
    return [e for e in log(tmp_path) if e['event'] == 'driver-exit'][-1]


# ---------------------------------------------------------------- accounting

def test_each_run_is_charged_the_account_delta_to_the_next_reading_and_caps_use_the_roll_forward(tmp_path):
    ports = Ports(spend={1: '6.5', 2: '3.25', 3: '4'})
    driver, path = make(tmp_path, ports)
    assert driver.run(1, 2) == 0
    acc = sd.load_accounting(path)
    assert [r['actual_usd'] for r in acc['runs']] == ['6.5000', '3.2500', '4.0000']
    assert Decimal(acc['item_actual_usd']) == Decimal('50') + Decimal('13.75') and acc['stage_actual_usd'] == {'s1': '13.7500'}
    assert acc['cumulative_attempts'] == 7 + 30 and all(r['status'] == 'closed' and r['complete'] for r in acc['runs'])
    assert reasons(tmp_path)['reason'] == 'run limit' and reasons(tmp_path)['rc'] == 0
    # The last run is settled by the closing reading, after the settle wait, not by a fourth launch.
    assert ('launch', 4) not in ports.calls


def test_spend_between_readings_with_no_open_run_is_unattributed_but_counts(tmp_path):
    ports = Ports(spend={1: '1'})
    driver, path = make(tmp_path, ports, max_runs=1, base_runs=1)
    ports.usage += Decimal('2.5')           # spent before the first run, by other use of the account
    driver.run(1, 1)
    acc = sd.load_accounting(path)
    assert acc['unattributed'] == [dict(stage='s1', **{'from': '100'}, to='102.5', usd='2.5000')]
    assert Decimal(acc['stage_actual_usd']['s1']) == Decimal('3.5')


def test_a_cap_or_the_balance_stops_the_stage_before_the_next_run(tmp_path):
    ports = Ports(spend={1: '9', 2: '9', 3: '9'})
    driver, path = make(tmp_path, ports, stage_cap_usd='25')
    assert driver.run(1, 2) == 0
    # Two runs cost 18; one more worst-case run of 10 would pass 25.
    assert reasons(tmp_path)['reason'].startswith('stage cap') and ('launch', 3) not in ports.calls
    ports = Ports(spend={1: '9'})
    driver, _ = make(_sub(tmp_path, 'b'), ports, item_cap_usd='55')
    assert driver.run(1, 2) == 0 and reasons(_sub(tmp_path, 'b'))['reason'].startswith('item cap (#1 actual')
    ports = Ports(spend={1: '9'}, balance=105)
    driver, _ = make(_sub(tmp_path, 'c'), ports)
    assert driver.run(1, 2) == 4 and 'balance below one worst-case run' in reasons(_sub(tmp_path, 'c'))['reason']


def _sub(tmp_path, name):
    path = tmp_path / name
    path.mkdir(exist_ok=True)
    return path


def test_an_open_run_record_blocks_everything_and_is_never_settled_under(tmp_path):
    ports = Ports()
    driver, path = make(tmp_path, ports)
    acc = sd.load_accounting(path)
    acc['runs'].append(dict(run='s1-01', stage='s1', account_before='100', status='launched', complete=False))
    sd.save_accounting(path, acc)
    assert driver.run(2, 1) == 4
    assert 'open run record' in reasons(tmp_path)['reason'] and ports.calls == [] and ports.restored == []


def test_unsupported_accounting_and_frozen_registries_are_refused(tmp_path):
    path = tmp_path / 'old.json'
    path.write_text(json.dumps(dict(runs=[], actual_spend_baseline_usd='1')))
    with pytest.raises(StageError, match='accounting schema'):
        sd.load_accounting(path)
    good_frozen = tmp_path / 'frozen.json'
    good_frozen.write_text(json.dumps(FROZEN))
    assert sd.load_frozen(good_frozen)['stage'] == 's1'
    for changes in (dict(extra=1), dict(max_runs=-1), dict(stage_cap_usd=10), dict(continuity='sequential'), dict(base_runs=5),
                    dict(continuity='persistent', max_runs=4), dict(batch_size=0), dict(load_gate='8'), dict(load_gate=True),
                    dict(load_gate=float('nan')), dict(max_check_gap_seconds=-1), dict(max_check_gap_seconds=None), dict(stage=''),
                    dict(item=3), dict(provider_failure_reasons=['host-crash']), dict(provider_failure_reasons='provider-error'),
                    dict(provider_failure_reasons=['provider-error', 'provider-error'])):
        path.write_text(json.dumps(dict(FROZEN, **changes)))
        with pytest.raises(StageError):
            sd.load_frozen(path)
    path.write_text(json.dumps({k: v for k, v in FROZEN.items() if k != 'load_gate'}))
    with pytest.raises(StageError):
        sd.load_frozen(path)


# ---------------------------------------------------------------- state, build, machine

def test_a_differing_state_is_restored_from_the_previous_run_and_a_failed_restore_stops(tmp_path):
    ports = Ports()
    ports.verify_results = [True, False, True, True]       # run 1 verifies; run 2 differs, restores, verifies; the closing check passes
    driver, _ = make(tmp_path, ports)
    assert driver.run(1, 1) == 0
    assert ports.restored == ['after-s1-01']
    ports = Ports()
    ports.verify_results = [True, False]
    ports.restore_ok = False
    driver, _ = make(_sub(tmp_path, 'b'), ports)
    assert driver.run(1, 1) == 4 and 'state restore/verify failed' in reasons(_sub(tmp_path, 'b'))['reason']


def test_the_final_check_restores_a_changed_state_on_exit(tmp_path):
    ports = Ports()
    ports.verify_results = [True, False]                 # the run verifies; the closing verify finds the run changed it
    driver, _ = make(tmp_path, ports, max_runs=1, base_runs=1)
    driver.run(1, 1)
    assert ports.restored == ['after-s1-01']
    assert any(e['event'] == 'final-restore' for e in log(tmp_path))


def test_a_failed_build_stops_without_a_run_record(tmp_path):
    ports = Ports()
    ports.build_ok = False
    driver, path = make(tmp_path, ports)
    assert driver.run(1, 1) == 4 and reasons(tmp_path)['reason'] == 'build failed'
    assert sd.load_accounting(path)['runs'] == [] and ('launch', 1) not in ports.calls


def test_the_driver_waits_for_a_quiet_machine_and_gives_up_after_thirty_minutes(tmp_path):
    ports = Ports()
    ports.loads = [20.0, 12.0, 3.0]
    driver, path = make(tmp_path, ports)
    assert driver.run(1, 1) == 0 and [e['load'] for e in log(tmp_path) if e['event'] == 'load-wait'] == [20.0, 12.0]
    assert sd.load_accounting(path)['runs'][0]['load_at_start'] == 3.0
    ports = Ports()
    ports.loads = [50.0] * 40
    driver, path = make(_sub(tmp_path, 'b'), ports)
    assert driver.run(1, 1) == 4 and reasons(_sub(tmp_path, 'b'))['reason'].startswith('machine overloaded')
    assert ('build', 1) not in ports.calls


def test_a_changed_price_stops_the_stage_before_any_run(tmp_path):
    ports = Ports()
    ports.prices = dict(prompt=('1', '2'))
    driver, _ = make(tmp_path, ports)
    assert driver.run(1, 1) == 3 and ports.calls == []


def test_the_extension_rule_is_consulted_only_beyond_the_base_plan(tmp_path):
    ports = Ports()
    ports.extension = (False, '25 decided >= 20')
    driver, _ = make(tmp_path, ports, base_runs=1, max_runs=3)
    assert driver.run(1, 2) == 0 and ports.calls.count(('launch', 1)) == 1 and ('launch', 2) not in ports.calls
    assert reasons(tmp_path)['reason'] == 'run limit (extension not needed: 25 decided >= 20)'


# ---------------------------------------------------------------- stop rules after a run

def stop_after_first(tmp_path, assessment, ports=None, **frozen):
    ports = ports or Ports(assessments={1: assessment})
    driver, path = make(tmp_path, ports, **frozen)
    rc = driver.run(1, 1)
    return rc, reasons(tmp_path)['reason'], sd.load_accounting(path), ports


def test_an_incomplete_run_stops_the_stage_but_is_retained_and_charged(tmp_path):
    rc, reason, acc, _ = stop_after_first(tmp_path, Assessment(complete=False, outcome='incomplete', max_check_gap_s=10.0))
    assert rc == 4 and reason == 'run not complete (incomplete)'
    assert acc['runs'][0]['status'] == 'closed' and acc['runs'][0]['complete'] is False and acc['runs'][0]['attempts'] == 50


@pytest.mark.parametrize('changes,message', [
    (dict(max_check_gap_s=46.0), 'check gap 46.0 s exceeds 45 s'),
    (dict(max_check_gap_s=None), 'check gap None s exceeds'),
    (dict(failure='RuntimeError: x'), 'layer failure recorded (RuntimeError: x)'),
    (dict(breaker=dict(tripped=True, worst=dict(tool='t', field='f', count=3), successes={}, refusals={})), 'refusal circuit breaker (t field f refused 3 times'),
])
def test_a_gap_a_layer_failure_or_a_tripped_breaker_stops_after_the_retained_run(tmp_path, changes, message):
    rc, reason, acc, _ = stop_after_first(tmp_path, Assessment(**dict(dict(complete=True, outcome='ok', max_check_gap_s=20.0, quiescent=True,
                                                                              attempts_charged=9), **changes)))
    assert rc == 4 and message in reason and acc['runs'][0]['status'] == 'closed' and acc['runs'][0]['attempts'] == 9


def test_a_watcher_failure_or_timeout_stops_the_stage_and_a_timeout_terminates_it(tmp_path):
    ports = Ports(assessments={1: good(1)})
    ports.watcher_rc = 1
    assert stop_after_first(tmp_path, None, ports)[1] == 'watcher failed (1)'
    ports = Ports(assessments={1: good(1)})
    ports.watcher_timeout = True
    rc, reason, acc, _ = stop_after_first(_sub(tmp_path, 'b'), None, ports)
    assert reason == 'watcher failed (timeout)' and acc['runs'][0]['watcher_rc'] == 'timeout'


def test_an_unknown_attempt_count_charges_the_whole_allocation(tmp_path):
    ports = Ports(assessments={1: Assessment(complete=True, max_check_gap_s=5.0, attempts_charged=None, quiescent=True)})
    _, _, acc, _ = stop_after_first(tmp_path, None, ports, max_runs=1, base_runs=1)
    assert acc['runs'][0]['attempts'] == 50 and acc['cumulative_attempts'] == 57


def incomplete(run, ending='request-timeout (stream with no provider events)'):
    return Assessment(complete=False, outcome='incomplete', max_check_gap_s=10.0, provider_ending=ending, quiescent=True)


def test_a_provider_side_failure_with_intact_custody_is_excluded_and_the_stage_continues(tmp_path):
    ports = Ports(assessments={1: incomplete(1)})
    driver, path = make(tmp_path, ports)
    assert driver.run(1, 1) == 0
    acc = sd.load_accounting(path)
    assert acc['excluded_infrastructure'] == {'s1': [dict(run='s1-01', host_ending='request-timeout (stream with no provider events)')]}
    assert acc['runs'][0]['excluded'].startswith('infrastructure:') and len(acc['runs']) == 3
    assert acc['runs'][0]['complete'] is False and acc['runs'][1]['complete'] is True


def test_infrastructure_exclusions_are_bounded_and_never_consecutive_twice_and_need_custody(tmp_path):
    ports = Ports(assessments={1: incomplete(1), 2: incomplete(2), 3: good(3)})
    driver, _ = make(tmp_path, ports)
    assert driver.run(1, 1) == 4 and reasons(tmp_path)['reason'].startswith('two consecutive infrastructure failures')
    ports = Ports(assessments={1: incomplete(1), 2: good(2), 3: incomplete(3), 4: incomplete(4)})
    driver, _ = make(_sub(tmp_path, 'b'), ports, max_runs=4, base_runs=4, batch_size=4, max_infrastructure_failures=5)
    assert driver.run(1, 1) == 4 and reasons(_sub(tmp_path, 'b'))['reason'].startswith('two consecutive')
    ports = Ports(assessments={1: incomplete(1), 2: good(2), 3: incomplete(3)})
    driver, _ = make(_sub(tmp_path, 'c'), ports, max_infrastructure_failures=1)
    assert driver.run(1, 1) == 4 and reasons(_sub(tmp_path, 'c'))['reason'].startswith('infrastructure failures exceed 1')
    for custody, text in ((2, '2 violations'), (None, 'unknown')):
        ports = Ports(assessments={1: incomplete(1)})
        ports.custody = custody
        directory = _sub(tmp_path, f'd{custody}')
        driver, _ = make(directory, ports)
        assert driver.run(1, 1) == 4 and text in reasons(directory)['reason']


# ---------------------------------------------------------------- persistent continuity

def persistent(tmp_path, ports, **frozen):
    return make(tmp_path, ports, continuity='persistent', **frozen)


def test_a_persistent_stage_verifies_the_carried_state_retains_each_session_and_never_restores(tmp_path):
    ports = Ports(assessments={n: good(n) for n in (1, 2, 3)})
    driver, path = persistent(tmp_path, ports)
    assert driver.run(1, 1) == 0
    assert ports.restored == [] and ports.retained == ['after-s1-01', 'after-s1-02', 'after-s1-03']
    # Session 1 verifies the frozen state; later sessions the previous session's retained copy; the exit keeps the live state.
    assert ports.verified == [None, 'after-s1-01', 'after-s1-02', 'after-s1-03']
    assert any(e['event'] == 'carried-state-kept' and e['retained'] == 'after-s1-03' for e in log(tmp_path))
    acc = sd.load_accounting(path)
    assert [r['persistent_retained'] for r in acc['runs']] == ['after-s1-01', 'after-s1-02', 'after-s1-03']


def test_a_persistent_session_that_is_not_complete_breaks_continuity_even_for_a_provider_failure(tmp_path):
    ports = Ports(assessments={1: incomplete(1)})
    driver, _ = persistent(tmp_path, ports)
    assert driver.run(1, 1) == 4 and 'continuity is broken' in reasons(tmp_path)['reason']
    assert ports.custody == 0 and not any(e['event'] == 'excluded-infrastructure' for e in log(tmp_path))


def test_a_failed_retention_or_a_changed_carried_state_stops_a_persistent_stage(tmp_path):
    ports = Ports(assessments={1: good(1)})
    ports.retain_rc = 3
    driver, _ = persistent(tmp_path, ports)
    assert driver.run(1, 1) == 4 and 'retaining its post-session state failed (rc 3)' in reasons(tmp_path)['reason']
    ports = Ports(assessments={1: good(1)})
    ports.verify_results = [True, False]
    driver, _ = persistent(_sub(tmp_path, 'b'), ports)
    assert driver.run(1, 1) == 4 and 'carried state differs from the retained post-session copy of s1-01' in reasons(_sub(tmp_path, 'b'))['reason']
    assert ports.restored == []


@pytest.mark.parametrize('labels', [None, ('only-one',), ('same', 'same'), ('after-x', ''), ['after-x', 'evidence-x'], ('after-x', 3)])
def test_a_persistent_binding_must_name_its_retained_labels_before_anything_runs(tmp_path, labels):
    ports = Ports(assessments={1: good(1)})
    ports.retain_labels = lambda name: labels
    driver, path = persistent(tmp_path, ports)
    assert driver.run(1, 1) == 5 and 'two distinct retained-state labels' in reasons(tmp_path)['reason']
    # Nothing was built, launched or recorded, and no state was touched beyond the opening check.
    assert ('build', 1) not in ports.calls and ('launch', 1) not in ports.calls
    assert sd.load_accounting(path)['runs'] == [] and ports.retained == [] and ports.restored == []


def test_a_persistent_session_that_is_not_a_continuation_is_retained_as_evidence_only(tmp_path):
    ports = Ports(assessments={1: Assessment(complete=False, outcome='incomplete', max_check_gap_s=1.0, quiescent=True)})
    driver, path = persistent(tmp_path, ports)
    assert driver.run(1, 1) == 4 and ports.retained == ['after-s1-01-evidence']
    assert sd.load_accounting(path)['runs'][0]['persistent_retained'] == 'after-s1-01-evidence'
    # A complete session whose level was not quiescent is evidence too: it is never a state to carry.
    ports = Ports(assessments={1: Assessment(complete=True, max_check_gap_s=1.0, quiescent=False)})
    driver, _ = persistent(_sub(tmp_path, 'b'), ports)
    driver.run(1, 1)
    assert ports.retained[0] == 'after-s1-01-evidence'


# ---------------------------------------------------------------- exits

def test_an_exception_with_no_receipt_leaves_the_run_open_and_charged_and_settles_nothing(tmp_path):
    ports = Ports()
    ports.explode_on_launch = True
    driver, path = make(tmp_path, ports)
    ports.verify_results = [True]
    assert driver.run(1, 1) == 5
    acc = sd.load_accounting(path)
    assert acc['runs'][0]['status'] == 'interrupted-possibly-live' and 'account_after' not in acc['runs'][0]
    assert acc['runs'][0]['attempts'] == 50 and acc['cumulative_attempts'] == 57
    assert [e for e in log(tmp_path) if e['event'] == 'left-open'] and ports.restored == []
    assert reasons(tmp_path)['reason'].startswith('exception: RuntimeError')
    # The next driver start refuses to go on under that record.
    again, _ = make(tmp_path, Ports())
    assert again.one_run(1).startswith('open run record')


def test_a_run_whose_assessment_fails_after_its_receipt_is_charged_in_full_and_left_open(tmp_path):
    ports = Ports()

    def explode(name, receipt):
        raise RuntimeError('assessment died')
    ports.assess = explode
    driver, path = make(tmp_path, ports)
    assert driver.run(1, 1) == 5
    record = sd.load_accounting(path)['runs'][0]
    assert record['status'] == 'interrupted-unassessed' and record['attempts'] == 50
    assert sd.load_accounting(path)['cumulative_attempts'] == 57
    # It has a receipt, so the account is settled against it and its spend is counted; the record stays open for the owner.
    assert record['actual_usd'] == '5.0000' and not [e for e in log(tmp_path) if e['event'] == 'left-open']
    again, _ = make(tmp_path, Ports())
    assert again.one_run(2).startswith('open run record')


def test_a_stage_with_no_runs_exits_without_touching_state(tmp_path):
    ports = Ports()
    ports.prices = {'x': 1}
    driver, _ = make(tmp_path, ports)
    assert driver.run(1, 1) == 3 and ports.verified == [] and ports.restored == []


# ---------------------------------------------------------------- provider evidence and the freeze

def request(logical='L', attempt='request-1'):
    return dict(type='request-start', logical_request_id=logical, request_id=attempt)


@pytest.mark.parametrize('rows,ending,expected', [
    ([request(), dict(type='response-headers', request_id='request-1', status=503)], 'provider-error', 'provider status'),
    ([request(), dict(type='provider-refusal', request_id='request-1', status=429)], 'provider-error', 'provider status'),
    ([request(), dict(type='provider-retry', request_id='request-1', retry_class='pre-header-rejection')], 'provider-error', 'fetch rejection'),
    ([request(), dict(type='response-headers', request_id='request-1', status=400)], 'provider-error', None),
    ([request(), dict(type='response-headers', request_id='request-1', status=200),
      dict(type='response-complete', request_id='request-1', response_progress=dict(provider_events=0))], 'request-timeout',
     'stream with no provider events'),
    ([request(), dict(type='response-headers', request_id='request-1', status=200),
      dict(type='response-complete', request_id='request-1', response_progress=dict(provider_events=4))], 'request-timeout', None),
    ([request(), dict(type='response-headers', request_id='request-1', status=200), dict(type='provider-refusal', request_id='request-1'),
      dict(type='response-complete', request_id='request-1', response_progress=dict(provider_events=0))], 'request-timeout', None),
    ([request('A', 'request-1'), dict(type='response-headers', request_id='request-1', status=503), request('B', 'request-2'),
      dict(type='response-headers', request_id='request-2', status=400)], 'provider-error', None),
    ([], 'provider-error', None), (None, 'provider-error', None), ([dict(type='host-start')], 'request-timeout', None),
])
def test_provider_side_evidence_is_read_from_the_last_logical_request_only(rows, ending, expected):
    assert sd.provider_evidence(rows, ending) == expected


def test_a_trace_with_an_unparsable_line_is_unknown_not_evidence():
    assert sd.parse_trace('{"type": "a"}\n{"type": "b"}\n') == [dict(type='a'), dict(type='b')]
    assert sd.parse_trace('{"type": "a"}\n{oops\n') is None and sd.parse_trace('[1]\n') is None


def test_an_infrastructure_failure_needs_every_custody_fact_and_one_timed_out_actor():
    rows = [request(), dict(type='response-headers', request_id='request-1', status=503)]
    receipt = dict(outcome='incomplete', deciding_hosts_quiescent=True, native_absence_verified=True, input_authority_revoked=True,
                   driver=dict(actors=[dict(accounting_complete=True, settled=dict(reason='provider-error'))]))
    assert sd.infrastructure_failure(receipt, True, True, rows, REASONS) == 'provider-error (provider status)'
    # Which settled reasons count is the stage's frozen choice.
    assert sd.infrastructure_failure(receipt, True, True, rows, ['request-timeout']) is None
    broken = [(dict(receipt, outcome='complete'), True, True), (receipt, False, True), (receipt, True, False),
              (dict(receipt, native_absence_verified=False), True, True), (dict(receipt, input_authority_revoked=None), True, True),
              (dict(receipt, driver=dict(actors=[])), True, True),
              (dict(receipt, driver=dict(actors=[dict(accounting_complete=True, orchestration_error='x', settled=dict(reason='provider-error'))])), True, True),
              (dict(receipt, driver=dict(actors=[dict(accounting_complete=False, settled=dict(reason='provider-error'))])), True, True),
              (dict(receipt, driver=dict(actors=[dict(accounting_complete=True, settled=dict(reason='completed'))])), True, True), (None, True, True)]
    for value, quiescent, present in broken:
        assert sd.infrastructure_failure(value, quiescent, present, rows, REASONS) is None


def test_the_freeze_check_names_every_digest_that_differs():
    import hashlib
    files = {'tools/a.py': b'a', 'guide.md': b'g'}
    digest = lambda data: hashlib.sha256(data).hexdigest()
    expected = {'tools/a.py': digest(b'a'), 'guide.md': digest(b'g'), 'missing': digest(b'm')}
    assert sd.verify_freeze({k: v for k, v in expected.items() if k != 'missing'}, files.get) == []
    problems = sd.verify_freeze(expected, files.get)
    assert problems == [f"missing: frozen {digest(b'm')}, found None"]
    files['guide.md'] = b'edited'
    assert any(p.startswith('guide.md: frozen') for p in sd.verify_freeze(expected, files.get))


def test_accounting_is_published_atomically(tmp_path):
    path = tmp_path / 'accounting.json'
    sd.save_accounting(path, sd.new_accounting(spend_baseline_usd='1', item_actual_usd='1', cumulative_attempts=0, last_usage=None))
    assert not (tmp_path / 'accounting.json.tmp').exists() and sd.load_accounting(path)['schema'] == 'stage-accounting/1'
