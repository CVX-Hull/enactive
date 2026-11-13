"""The tracked development-run ledger (dev-run/1), the run-metrics/1 snapshot and the generated run tables."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tools import run_ledger
from tools.evaluate import has_blocks, main as evaluate_main, read_snapshot, table
from tools.run_ledger import LedgerError, main, read_ledger, totals

SESSION = 'a' * 32
COMMIT = 'b' * 40


def package(root: Path, name: str = 'lh9a1', *, receipt: bool = True, **accounting) -> Path:
    """A finished package whose receipt counted $1.0 of reported cost and one request at the $0.4096 bound."""
    directory = root / name
    directory.mkdir(parents=True)
    (directory / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/6', session=SESSION,
        source_commit=COMMIT, labels=dict(arm='long-horizon', start='S1', scenario='Evacuee', lineage='L9', admission=1))))
    if receipt:
        (directory / 'receipt.json').write_text(json.dumps(dict(schema='campaign-receipt/4', session=SESSION,
            source_commit=COMMIT, outcome='player_cannot_continue_unassessed', ended_wall=1794038818.1,
            elapsed_seconds=99.6, accounting=dict(spend_limit_usd='5', reported_usd='1.0', unpriced_requests=1,
                unpriced_request_usd='0.4096', spent_usd='1.4096', attempts_charged=10, allocated_max_attempts=40,
                spend_complete=True) | accounting)))
    return directory


def row(**changes) -> dict:
    base = dict(schema='dev-run/1', study=999, run='lh9a1', label='lh9a1', arm='long-horizon', start='S1',
        lineage='L9', admission=1, session=SESSION, source_commit=COMMIT, ended='2026-11-07T08:06:58Z',
        outcome='player_cannot_continue_unassessed', attempts=10, wall_seconds=100, spend_usd='1.4096',
        provider_usd='1.0', unpriced_attempts=1, unpriced_attempt_usd='0.4096')
    return base | changes


def write(path: Path, *rows: dict) -> Path:
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    return path


def test_record_derives_a_row_from_the_package_and_refuses_repeats_and_missing_receipts(tmp_path, capsys):
    ledger = write(tmp_path / 'runs.jsonl')
    directory = package(tmp_path / 'packages')
    arguments = ['--ledger', str(ledger), 'record', str(directory), '--study', '999', '--label', 'lh9a1']
    assert main(arguments) == 0
    recorded = read_ledger(ledger)
    # Rounded wall time, UTC end and labels are derived; the spend and its split are the receipt's, and the row
    # passes the ledger's own identity: spend is provider cost plus unpriced attempts at their charge.
    assert recorded == [row()]
    assert main(arguments) == 1 and 'already recorded' in capsys.readouterr().err
    assert main(['--ledger', str(ledger), 'record', str(package(tmp_path / 'other', receipt=False)), '--study', '999']) == 1
    assert 'no receipt.json' in capsys.readouterr().err
    for name, accounting, message in (('lh9a3', dict(spend_complete=False), 'spend as incomplete'),
                                      ('lh9a4', dict(spent_usd='1.5'), 'not its reported_usd plus unpriced requests'),
                                      ('lh9a5', dict(reported_usd=1.0), 'derived row is invalid')):
        assert main(['--ledger', str(ledger), 'record', str(package(tmp_path / name, name, **accounting)), '--study', '999']) == 1
        assert message in capsys.readouterr().err
    with pytest.raises(SystemExit):  # the figures are never typed in
        main([*arguments, '--provider-usd', '1.0'])
    capsys.readouterr()
    assert len(read_ledger(ledger)) == 1


def test_record_defaults_the_label_and_refuses_earlier_package_versions(tmp_path, capsys):
    ledger = write(tmp_path / 'runs.jsonl')
    directory = package(tmp_path / 'packages', reported_usd='0', unpriced_requests=0, spent_usd='0')
    assert main(['--ledger', str(ledger), 'record', str(directory), '--study', '999']) == 0
    assert read_ledger(ledger)[0] == row(spend_usd='0', provider_usd='0', unpriced_attempts=0)
    for name, file, schema, message in (('lh9a2', 'manifest.json', 'campaign-run/5', "unsupported manifest 'campaign-run/5'"),
                                        ('lh9a3', 'receipt.json', 'campaign-receipt/3', "unsupported receipt 'campaign-receipt/3'")):
        other = package(tmp_path / name, name=name)
        (other / file).write_text(json.dumps(json.loads((other / file).read_text()) | dict(schema=schema)))
        assert main(['--ledger', str(ledger), 'record', str(other), '--study', '999']) == 1
        assert message in capsys.readouterr().err


@pytest.mark.parametrize('bad, message', [
    (dict(schema='dev-run/0'), 'unsupported row version'),
    (dict(spend_usd='2'), 'spend_usd is not provider_usd plus'),
    (dict(provider_usd=None), 'recorded together or not at all'),
    (dict(attempts=-1), 'attempts'),
    (dict(unpriced_attempts=11, spend_usd='5.5056'), 'more unpriced attempts'),
    (dict(label=None), 'label'),
])
def test_unversioned_inconsistent_or_invalid_rows_are_rejected(tmp_path, bad, message):
    with pytest.raises(LedgerError, match=message):
        read_ledger(write(tmp_path / 'runs.jsonl', row(**bad)))


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
    rows = [row(run='a', spend_usd='5', provider_usd=None, unpriced_attempts=None, unpriced_attempt_usd=None),
            row(run='b', spend_usd='7', provider_usd=None, unpriced_attempts=None, unpriced_attempt_usd=None)]
    result = totals(rows, 999, Decimal('30'))
    assert (result['spend_usd'], result['largest_usd'], result['headroom_usd'], result['admit']) == ('12', '7', '4', True)
    assert totals(rows, 999, Decimal('25'))['admit'] is False
    assert totals(rows, 1, None) == dict(study=1, admissions=0, attempts=0, wall_seconds=0, spend_usd='0', largest_usd='0')
    first = totals([], 1, Decimal('150'), Decimal('6.50'))  # #382's forecast before any admission completes
    assert (first['largest_usd'], first['headroom_usd']) == ('6.50', '137.00')
    assert totals(rows, 999, Decimal('30'), Decimal('100'))['largest_usd'] == '7'  # actual admissions replace it


def test_tracked_ledger_snapshot_and_generated_tables_are_consistent():
    rows = read_ledger()
    assert len(rows) == 52 and {r['study'] for r in rows} == {372, 382, 397, 522}
    assert totals(rows, 382, None)['spend_usd'] == '30.46049960'
    assert totals(rows, 397, None)['spend_usd'] == '38.39958335'
    assert totals(rows, 522, None)['spend_usd'] == '30.11036530'     # the lost lh4a1 ($1.2343105) included
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
