"""The tracked development-run ledger (dev-run/3), the run-metrics/1 snapshot and the generated run tables."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from harness.player.knowledge import empty
from tools import run_ledger
from tools.evaluate import has_blocks, main as evaluate_main, read_snapshot, table
from tools.run_ledger import LedgerError, main, read_ledger, totals

SESSION = 'a' * 32
COMMIT = 'b' * 40


def package(root: Path, name: str = 'lh9a1', *, receipt: bool = True, **accounting) -> Path:
    """A finished package with $1.0 reported and one unknown-cost attempt."""
    directory = root / name
    directory.mkdir(parents=True)
    (directory / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/12', session=SESSION, live_knowledge_updates=False,
        source_commit=COMMIT, labels=dict(arm='long-horizon', start='S1', scenario='Evacuee', lineage='L9', admission=1))))
    (directory/'delivered-knowledge.json').write_text(json.dumps(empty()))
    if receipt:
        (directory / 'receipt.json').write_text(json.dumps(dict(schema='campaign-receipt/7', session=SESSION,
            source_commit=COMMIT, outcome='player_cannot_continue_unassessed', ended_wall=1794038818.1,
            elapsed_seconds=99.6, accounting=dict(unpriced_recall_requests=0,unpriced_recall_request_usd='0',spend_limit_usd='5', reported_usd='1.0', unpriced_requests=1,
                unpriced_request_usd='0.4096', spent_usd='1.0', observed_attempts=10,
                spend_complete=True) | accounting)))
    return directory


def row(**changes) -> dict:
    base = dict(schema='dev-run/3', study=999, run='lh9a1', label='lh9a1', arm='long-horizon', start='S1',
        lineage='L9', admission=1, session=SESSION, source_commit=COMMIT, ended='2026-11-07T08:06:58Z',
        outcome='player_cannot_continue_unassessed', attempts=10, wall_seconds=100, spend_usd='1.0',
        provider_usd='1.0', unpriced_attempts=1, unpriced_attempt_usd=None,unpriced_recall_attempts=0,unpriced_recall_attempt_usd=None,
        accounting_basis='provider-reported',spend_upper_bound_usd=None)
    return base | changes


def write(path: Path, *rows: dict) -> Path:
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    return path


def test_unknown_player_and_recall_costs_leave_spend_unchanged_and_old_rows_are_refused(tmp_path):
    from tools.run_ledger import package_row
    directory=package(tmp_path/'packages',unpriced_requests=2,unpriced_request_usd='0.4',
        unpriced_recall_requests=1,unpriced_recall_request_usd='0.2',reported_usd='0',spent_usd='0')
    value=package_row(directory,study=999,label='unknown-charges')
    assert value['unpriced_attempts']==2 and value['unpriced_recall_attempts']==1
    assert value['unpriced_attempt_usd'] is None and value['unpriced_recall_attempt_usd'] is None
    assert value['provider_usd']==value['spend_usd']=='0'
    assert totals([value],999,Decimal('0.3'))['headroom_usd']=='0.3'
    assert read_ledger(write(tmp_path/'current.jsonl',value))==[value]
    with pytest.raises(LedgerError,match='unsupported row version'):
        read_ledger(write(tmp_path/'old.jsonl',dict(value,schema='dev-run/2')))
    with pytest.raises(LedgerError,match='more unpriced attempts'):
        read_ledger(write(tmp_path/'too-many.jsonl',dict(value,attempts=2)))


def test_record_derives_a_row_from_the_package_and_refuses_repeats_and_missing_receipts(tmp_path, capsys):
    ledger = write(tmp_path / 'runs.jsonl')
    directory = package(tmp_path / 'packages')
    arguments = ['--ledger', str(ledger), 'record', str(directory), '--study', '999', '--label', 'lh9a1']
    assert main(arguments) == 0
    recorded = read_ledger(ledger)
    # Rounded wall time, UTC end, provider subtotal and unknown attempt count are derived from the receipt.
    assert recorded == [row()]
    assert main(arguments) == 1 and 'already recorded' in capsys.readouterr().err
    assert main(['--ledger', str(ledger), 'record', str(package(tmp_path / 'other', receipt=False)), '--study', '999']) == 1
    assert 'no receipt.json' in capsys.readouterr().err
    for name, accounting, message in (('lh9a4', dict(spent_usd='1.5'), 'must equal provider_usd'),
                                      ('lh9a5', dict(reported_usd=1.0), 'derived row is invalid')):
        assert main(['--ledger', str(ledger), 'record', str(package(tmp_path / name, name, **accounting)), '--study', '999']) == 1
        assert message in capsys.readouterr().err
    with pytest.raises(SystemExit):  # the figures are never typed in
        main([*arguments, '--provider-usd', '1.0'])
    capsys.readouterr()
    assert len(read_ledger(ledger)) == 1


@pytest.mark.parametrize(('reported', 'bound'), [('0.3', '5.4096'), ('5.45', '5.8596')])
def test_an_incomplete_receipt_preserves_observed_cost_beside_the_explicit_upper_bound(tmp_path, capsys, reported, bound):
    """The flag retains the observed provider subtotal and records the separate admission bound."""
    ledger = write(tmp_path / 'runs.jsonl')
    incomplete = package(tmp_path / 'packages', spend_complete=False, reported_usd=reported, unpriced_requests=0,
                         spent_usd=reported, observed_attempts=40)
    arguments = ['--ledger', str(ledger), 'record', str(incomplete), '--study', '999']
    assert main(arguments) == 1
    assert 'spend as incomplete' in capsys.readouterr().err and read_ledger(ledger) == []
    assert main([*arguments, '--record-upper-bound']) == 0
    recorded = read_ledger(ledger)
    assert recorded == [row(attempts=40, provider_usd=reported, unpriced_attempts=0, spend_usd=reported,
                            accounting_basis='incomplete-trace',spend_upper_bound_usd=bound)]
    accounting = totals(recorded, 999, None)
    assert accounting['provider_usd'] == reported
    assert accounting['admission_usd'] == bound
    complete = package(tmp_path / 'more', name='lh9a2')
    assert main(['--ledger', str(ledger), 'record', str(complete), '--study', '999', '--record-upper-bound']) == 1
    assert 'spend as complete' in capsys.readouterr().err and len(read_ledger(ledger)) == 1


@pytest.mark.parametrize('attempts',[0,1,2])
@pytest.mark.parametrize('has_units',[False,True])
@pytest.mark.parametrize('live',[False,True])
def test_upper_bound_covers_possible_inflight_attempts_even_when_none_observed(tmp_path,attempts,has_units,live):
    from tools.run_ledger import package_row
    directory=package(tmp_path/'packages',spend_complete=False,observed_attempts=attempts,unpriced_requests=0,unpriced_recall_request_usd='0.2')
    if has_units:
        path=directory/'delivered-knowledge.json';value=json.loads(path.read_text())
        value['facts']=[dict(id='fact',type='claim',text='Fallible',seen=dict(session='s1',actor='001',step=1,order=[1,'001',1]))]
        path.write_text(json.dumps(value))
    if live:
        path=directory/'manifest.json'
        path.write_text(json.dumps(dict(json.loads(path.read_text()),live_knowledge_updates=True)))
    value=package_row(directory,study=999,label='upper-bound',upper_bound=True)
    assert value['unpriced_attempts']==value['unpriced_recall_attempts']==0
    assert value['provider_usd']==value['spend_usd']=='1.0'
    # A recall is possible with frozen facts, and with live updates even from an empty frozen file.
    expected=Decimal('5')+Decimal('0.4096')+int(has_units or live)*Decimal('0.2')
    assert value['attempts']==attempts
    assert Decimal(value['spend_upper_bound_usd'])==expected
    assert read_ledger(write(tmp_path/'ledger.jsonl',value))==[value]


def test_record_defaults_the_label_and_refuses_earlier_package_versions(tmp_path, capsys):
    ledger = write(tmp_path / 'runs.jsonl')
    directory = package(tmp_path / 'packages', reported_usd='0', unpriced_requests=0, spent_usd='0')
    assert main(['--ledger', str(ledger), 'record', str(directory), '--study', '999']) == 0
    assert read_ledger(ledger)[0] == row(spend_usd='0', provider_usd='0', unpriced_attempts=0)
    for name, file, schema, message in (('lh9a2', 'manifest.json', 'campaign-run/5', "campaign-run/5 is read only"),
                                        ('lh9a3', 'receipt.json', 'campaign-receipt/3', "unsupported receipt 'campaign-receipt/3'")):
        other = package(tmp_path / name, name=name)
        (other / file).write_text(json.dumps(json.loads((other / file).read_text()) | dict(schema=schema)))
        assert main(['--ledger', str(ledger), 'record', str(other), '--study', '999']) == 1
        assert message in capsys.readouterr().err


@pytest.mark.parametrize('bad, message', [
    (dict(schema='dev-run/0'), 'unsupported row version'),
    (dict(spend_usd='2'), 'must equal provider_usd'),
    (dict(provider_usd=None), 'must equal provider_usd'),
    (dict(attempts=-1), 'attempts'),
    (dict(unpriced_attempts=11), 'more unpriced attempts'),
    (dict(unpriced_attempt_usd='0.4096'), 'without assigned charges'),
    (dict(spend_upper_bound_usd='5'), 'only an incomplete trace'),
    (dict(label=None), 'label'),
    (dict(start='S0'), 'S0'),
    (dict(start='S01'), 'S01'),
    (dict(start='S100'), 'S100'),
])
def test_unversioned_inconsistent_or_invalid_rows_are_rejected(tmp_path, bad, message):
    with pytest.raises(LedgerError, match=message):
        read_ledger(write(tmp_path / 'runs.jsonl', row(**bad)))


def test_start_labels_run_from_s1_to_s99(tmp_path):
    rows = [row(start='S3', run='lh9a3', session='a' * 32), row(start='S99', run='lh9a4', session='b' * 32)]
    assert [r['start'] for r in read_ledger(write(tmp_path / 'runs.jsonl', *rows))] == ['S3', 'S99']


def test_a_repeated_run_is_rejected(tmp_path):
    with pytest.raises(LedgerError, match='duplicate run'):
        read_ledger(write(tmp_path / 'runs.jsonl', row(), row()))
    unversioned = tmp_path / 'old.jsonl'
    unversioned.write_text('{"run": "x", "provider_usd": 1}\n')
    with pytest.raises(LedgerError, match='unsupported row version None'):
        read_ledger(unversioned)
    with pytest.raises(LedgerError, match='is already recorded'):
        read_ledger(write(tmp_path / 'sessions.jsonl', row(), row(run='lh9a2')))


def test_totals_apply_the_actual_spend_admission_rule():
    rows = [row(run='a', accounting_basis='historical', spend_usd='5', provider_usd=None, unpriced_attempts=None, unpriced_attempt_usd=None,unpriced_recall_attempts=None,unpriced_recall_attempt_usd=None),
            row(run='b', accounting_basis='historical', spend_usd='7', provider_usd=None, unpriced_attempts=None, unpriced_attempt_usd=None,unpriced_recall_attempts=None,unpriced_recall_attempt_usd=None)]
    result = totals(rows, 999, Decimal('30'))
    assert (result['admission_usd'], result['largest_admission_usd'], result['headroom_usd'], result['admit']) == ('12', '7', '4', True)
    assert result['provider_usd'] == '0'
    assert result['admissions_without_provider_subtotal'] == 2
    assert totals(rows, 999, Decimal('25'))['admit'] is False
    assert totals(rows, 1, None) == dict(study=1, admissions=0, attempts=0, wall_seconds=0, provider_usd='0',
                                        admissions_without_provider_subtotal=0, admission_usd='0', largest_admission_usd='0')
    first = totals([], 1, Decimal('150'), Decimal('6.50'))  # #382's forecast before any admission completes
    assert (first['largest_admission_usd'], first['headroom_usd']) == ('6.50', '137.00')
    assert totals(rows, 999, Decimal('30'), Decimal('100'))['largest_admission_usd'] == '7'


def test_tracked_ledger_snapshot_and_generated_tables_are_consistent():
    rows = read_ledger()
    historical_studies = {372, 382, 397, 522, 635, 642, 619, 651}
    historical_rows = [r for r in rows if r['study'] in historical_studies]
    assert len(historical_rows) == 123
    assert {r['study'] for r in historical_rows} == historical_studies
    assert totals(rows, 651, None)['admission_usd'] == '86.38254135'     # the full withholding study, replaced attempts included
    assert sum(r['study'] == 651 for r in rows) == 63
    assert totals(rows, 635, None)['admission_usd'] == '1.57054305'      # the delivery development start
    assert totals(rows, 642, None)['admission_usd'] == '1.5896732'       # the delivery check start of the recall fix
    assert totals(rows, 619, None)['admission_usd'] == '8.85651610'      # the withholding pilot's six starts
    assert {r['start'] for r in rows if r['study'] == 619} == {'S1', 'S2', 'S3', 'S4', 'S5', 'S6'}
    assert totals(rows, 382, None)['admission_usd'] == '30.46049960'
    assert totals(rows, 397, None)['admission_usd'] == '38.39958335'
    assert totals(rows, 522, None)['admission_usd'] == '30.11036530'     # the lost lh4a1 ($1.2343105) included
    screen = [r for r in rows if r['study'] == 441]
    assert {r['accounting_basis'] for r in screen} == {'historical'}
    assert totals(screen, 441, None)['provider_usd'] == '0.11674225'
    assert totals(screen, 441, None)['admission_usd'] == '0.93594225'
    snapshot = read_snapshot(run_ledger.ROOT / 'data/evaluation/run-metrics.jsonl')
    assert {r['session'] for r in rows} == {r['session'] for r in snapshot}
    text = ''.join(Path(p).read_text() for p in (run_ledger.LEDGER, run_ledger.ROOT / 'data/evaluation/run-metrics.jsonl'))
    assert '/Users/' not in text and 'localhost' not in text and '127.0.0.1' not in text


def test_generated_blocks_are_written_checked_and_select_by_study_and_lineage(tmp_path, capsys):
    snapshot = write(tmp_path / 'run-metrics.jsonl', dict(schema='run-metrics/1', session=SESSION, run='lh9a1',
        core_version=2, binding_id='cdda', binding_version=2, arm='long-horizon', start='S1', decisions=5,
        metrics={'survival.game_hours': dict(censor_reason='player_stop', hours=1.5)}))
    ledger = write(tmp_path / 'runs.jsonl', row())
    document = tmp_path / 'doc.md'
    document.write_text('Intro\n\n<!-- evaluate-table study=999 lineage=L9 core=2 binding=cdda:2 -->\nstale\n'
                        '<!-- /evaluate-table -->\n\nHand rows stay.\n')
    common = ['evaluate-table', str(snapshot), '--ledger', str(ledger)]
    assert evaluate_main([*common, '--check', str(document)]) == 1
    assert 'stale in' in capsys.readouterr().err
    assert evaluate_main([*common, '--write', str(document)]) == 0
    expected = table(read_snapshot(snapshot))
    assert document.read_text() == (f'Intro\n\n<!-- evaluate-table study=999 lineage=L9 core=2 binding=cdda:2 -->\n'
                                     f'{expected}\n<!-- /evaluate-table -->\n\nHand rows stay.\n')
    assert '| lh9a1 | long-horizon | S1 | player_stop | 1.50 | 5 |' in expected
    assert evaluate_main([*common, '--check', str(document)]) == 0
    document.write_text(document.read_text().replace('core=2', 'core=3'))
    assert evaluate_main([*common, '--check', str(document)]) == 1
    assert 'no snapshot row for lh9a1' in capsys.readouterr().err
    document.write_text(document.read_text().replace('study=999 lineage=L9', 'lineage=L9'))
    assert evaluate_main([*common, '--check', str(document)]) == 1
    assert 'needs study, core and binding' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        evaluate_main(['host-summary', str(snapshot), '--check', str(document)])
    capsys.readouterr()


@pytest.mark.parametrize('broken', [
    'Hand rows.\n<!-- evaluate-table study=999 lineage=L9 core=2 binding=cdda:2 -->\nstale\n',  # no close marker
    '<!-- evaluate-table study=999 lineage=L9 core=2 binding=cdda:2 -->\nstale\n<!-- evaluate-table study=999 '
    'core=2 binding=cdda:2 -->\nstale\n<!-- /evaluate-table -->\n',  # an opening marker inside a block
    '<!--  evaluate-table study=999 core=2 binding=cdda:2 -->\nstale\n<!-- /evaluate-table -->\n',  # loose spacing
    '<!-- evaluate-table study=999 core=2 binding=cdda:2 --> \nstale\n<!-- /evaluate-table -->\n',  # trailing space
])
def test_malformed_markers_fail_before_anything_is_written(tmp_path, capsys, broken):
    snapshot = write(tmp_path / 'run-metrics.jsonl', dict(schema='run-metrics/1', session=SESSION, run='lh9a1',
        core_version=2, binding_id='cdda', binding_version=2, arm='long-horizon', start='S1', decisions=5, metrics={}))
    ledger = write(tmp_path / 'runs.jsonl', row())
    document = tmp_path / 'doc.md'
    document.write_text(broken)
    for mode in ('--check', '--write'):
        assert evaluate_main(['evaluate-table', str(snapshot), '--ledger', str(ledger), mode, str(document)]) == 1
        assert 'malformed evaluate-table markers' in capsys.readouterr().err
    assert document.read_text() == broken
    good = tmp_path / 'good.md'  # a valid document listed first is not written when a later one is malformed
    good.write_text('<!-- evaluate-table study=999 lineage=L9 core=2 binding=cdda:2 -->\nstale\n<!-- /evaluate-table -->\n')
    assert evaluate_main(['evaluate-table', str(snapshot), '--ledger', str(ledger), '--write', str(good), str(document)]) == 1
    assert 'stale' in good.read_text()
    capsys.readouterr()
    assert has_blocks(broken) and not has_blocks('Inline `<!-- evaluate-table study=N -->` mention.\n')


def test_a_snapshot_row_violating_its_schema_is_rejected(tmp_path, capsys):
    good = dict(schema='run-metrics/1', session=SESSION, run='lh9a1', core_version=2, binding_id='cdda',
                binding_version=2, arm='long-horizon', start='S1', decisions=5, metrics={})
    for bad in (good | dict(extra=1), good | dict(metrics={'unknown.metric': 1}), {k: v for k, v in good.items() if k != 'run'}):
        assert evaluate_main(['evaluate-table', str(write(tmp_path / 'run-metrics.jsonl', bad))]) == 1
        assert 'run-metrics.jsonl:1:' in capsys.readouterr().err


def test_a_snapshot_row_of_another_version_is_rejected(tmp_path, capsys):
    snapshot = write(tmp_path / 'run-metrics.jsonl', dict(schema='run-metrics/0', metrics={}))
    assert evaluate_main(['evaluate-table', str(snapshot)]) == 1
    assert 'not a run-metrics/1 row' in capsys.readouterr().err


def test_sealed_bundle_run_directories_take_their_bundle_name(tmp_path, capsys):
    """Every sealed bundle holds its package as `<bundle>/run`; the ledger names the run for the bundle."""
    from tools.run_ledger import package_row
    first = package(tmp_path / 'evidence' / 'study-a-admission-01', 'run')
    second = package(tmp_path / 'evidence' / 'study-b-admission-01', 'run')
    names = [package_row(p, study=999, label='x')['run'] for p in (first, second)]
    assert names == ['study-a-admission-01', 'study-b-admission-01']
    # Any other directory keeps its own name, and the default label is the run name.
    assert package_row(package(tmp_path / 'packages'), study=999, label='x')['run'] == 'lh9a1'
    ledger = write(tmp_path / 'runs.jsonl')
    assert main(['--ledger', str(ledger), 'record', str(first), '--study', '999']) == 0
    assert (read_ledger(ledger)[0]['run'], read_ledger(ledger)[0]['label']) == ('study-a-admission-01',) * 2
    capsys.readouterr()


def test_the_table_adds_split_columns_only_for_rows_that_carry_them():
    base = dict(schema='run-metrics/1', session=SESSION, run='lh9a1', binding_id='cdda', arm='long-horizon', start='S1',
                decisions=5)
    share = lambda value: dict(value=value, excluded=0, setup_decisions=1)  # noqa: E731
    old = table([base | dict(core_version=2, binding_version=2, metrics={'mode.out_of_play_share': share(0.75)})])
    assert old.splitlines()[0] == ('| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | '
                                   'Out of play | Longest stall | $ / decision | Large rewrites |')
    split = table([base | dict(core_version=3, binding_version=3, metrics={'mode.out_of_play_share': share(0.75),
        'mode.ui_share': share(0.5), 'mode.interruption_share': share(0.25)})])
    header, _, line = split.splitlines()
    assert '| Out of play | UI | Interruptions | Longest stall |' in header
    assert '| 75% | 50% | 25% | — |' in line and header.count('|') == line.count('|')


def test_a_session_already_recorded_under_another_run_name_is_refused(tmp_path, capsys):
    """The same admission reached as a sealed `<bundle>/run` after its original directory was recorded."""
    ledger = write(tmp_path / 'runs.jsonl')
    original = package(tmp_path / 'packages')
    assert main(['--ledger', str(ledger), 'record', str(original), '--study', '999']) == 0
    before = ledger.read_bytes()
    sealed = package(tmp_path / 'evidence' / 'study-a-admission-01', 'run')
    assert main(['--ledger', str(ledger), 'record', str(sealed), '--study', '999']) == 1
    assert f'session {SESSION} is already recorded as study 999 run lh9a1' in capsys.readouterr().err
    # Nothing was appended, so the ledger still reads.
    assert ledger.read_bytes() == before and [r['run'] for r in read_ledger(ledger)] == ['lh9a1']
