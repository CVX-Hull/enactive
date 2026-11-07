"""The tracked development-run ledger (dev-run/1), the run-metrics/1 snapshot and the generated run tables."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tools import run_ledger
from tools.evaluate import main as evaluate_main, read_snapshot, table
from tools.run_ledger import LedgerError, cross_check, main, read_ledger, totals

SESSION = 'a' * 32
COMMIT = 'b' * 40


def package(root: Path, name: str = 'lh9a1', *, receipt: bool = True, attempts: int = 10) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / 'manifest.json').write_text(json.dumps(dict(schema='campaign-run/5', session=SESSION,
        source_commit=COMMIT, labels=dict(arm='long-horizon', start='S1', scenario='Evacuee', lineage='L9', admission=1))))
    if receipt:
        (directory / 'receipt.json').write_text(json.dumps(dict(schema='campaign-receipt/3', session=SESSION,
            source_commit=COMMIT, outcome='player_cannot_continue_unassessed', ended_wall=1794038818.1,
            elapsed_seconds=99.6, accounting=dict(attempts_charged=attempts))))
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
    arguments = ['--ledger', str(ledger), 'record', str(directory), '--study', '999', '--label', 'lh9a1',
                 '--provider-records', '9', '--provider-usd', '1.0', '--unpriced-attempt-usd', '0.4096']
    assert main(arguments) == 0
    recorded = read_ledger(ledger)
    assert recorded == [row()]  # rounded wall time, UTC end, labels and the unpriced charge are all derived
    assert main(arguments) == 1 and 'already recorded' in capsys.readouterr().err
    assert main(['--ledger', str(ledger), 'record', str(package(tmp_path / 'other', receipt=False)), '--study', '999',
                 '--provider-records', '0', '--provider-usd', '0', '--unpriced-attempt-usd', '0.4096']) == 1
    assert 'no receipt.json' in capsys.readouterr().err
    assert main(arguments[:-6] + ['--provider-records', '11', '--provider-usd', '1', '--unpriced-attempt-usd', '0.4096']) == 1
    assert 'between 0 and the 10 charged attempts' in capsys.readouterr().err
    assert len(read_ledger(ledger)) == 1


@pytest.mark.parametrize('bad, message', [
    (dict(schema='dev-run/0'), 'unsupported row version'),
    (dict(spend_usd='2'), 'spend_usd is not provider_usd plus'),
    (dict(provider_usd=None), 'recorded together or not at all'),
    (dict(attempts=-1), 'attempts'),
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


def test_totals_apply_the_actual_spend_admission_rule():
    rows = [row(run='a', spend_usd='5', provider_usd=None, unpriced_attempts=None, unpriced_attempt_usd=None),
            row(run='b', spend_usd='7', provider_usd=None, unpriced_attempts=None, unpriced_attempt_usd=None)]
    result = totals(rows, 999, Decimal('30'))
    assert (result['spend_usd'], result['largest_usd'], result['headroom_usd'], result['admit']) == ('12', '7', '4', True)
    assert totals(rows, 999, Decimal('25'))['admit'] is False
    assert totals(rows, 1, None) == dict(study=1, admissions=0, attempts=0, wall_seconds=0, spend_usd='0', largest_usd='0')


def test_hand_rows_are_cross_checked_against_the_ledger(tmp_path):
    document = tmp_path / 'runs.md'
    document.write_text('| Run | Attempts (setup) | $ upper bound | Wall s |\n| --- | --- | ---: | ---: |\n'
                        '| C1 | 233 (23) | 3.58 | 1,856 |\n| C1 | 232 (22) | 4.09 | 1,800 |\n')
    ledger = [row(run='ceil02', label='C1', attempts=233, spend_usd='3.583', wall_seconds=1856, provider_usd=None,
                  unpriced_attempts=None, unpriced_attempt_usd=None),
              row(run='aidC1', label='C1', attempts=232, spend_usd='3.680692', provider_usd='3.680692',
                  unpriced_attempts=1, wall_seconds=1800) | dict(spend_usd='4.090292')]
    assert cross_check(ledger, ('runs.md',), tmp_path) == []  # a repeated label is matched by its values
    document.write_text(document.read_text().replace('4.09', '4.10'))
    errors = cross_check(ledger, ('runs.md',), tmp_path)
    assert any('hand row C1 (232 attempts, $4.10, 1800 s) matches 0 ledger rows' in e for e in errors)
    assert any('aidC1 (label C1): no hand-scored row' in e for e in errors)


def test_tracked_ledger_snapshot_and_generated_tables_are_consistent():
    rows = read_ledger()
    assert len(rows) == 37 and {r['study'] for r in rows} == {372, 382}
    assert cross_check(rows) == []
    assert totals(rows, 382, None)['spend_usd'] == '30.46049960'
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


def test_a_snapshot_row_of_another_version_is_rejected(tmp_path, capsys):
    snapshot = write(tmp_path / 'run-metrics.jsonl', dict(schema='run-metrics/0', metrics={}))
    assert evaluate_main(['evaluate-table', str(snapshot)]) == 1
    assert 'not a run-metrics/1 row' in capsys.readouterr().err
