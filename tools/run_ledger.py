#!/usr/bin/env python3
"""The tracked development-run ledger, data/evaluation/runs.jsonl (dev-run/2); see docs/contracts/evaluation.md.

record derives one admission's row from its package alone (campaign-run/7 manifest and campaign-receipt/5, whose
accounting holds the provider-reported cost and the requests counted at the bound) and appends it; a package
without a receipt gets no row, and one whose receipt says its spend is incomplete gets a row only with
--record-upper-bound, at its declared limit plus possible in-flight bounds, limited by charged attempts and delivered units. totals reports a
study's spend against an envelope under the actual-spend admission rule (new spend plus twice the largest
admission). check validates every row. The ledger is the one numeric record of a run: a dated record presents
numbers through the generated run tables (tools/evaluate.py evaluate-table) or by citing the ledger.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Context, Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow
import json
from pathlib import Path
import sys

#: Dollar arithmetic never rounds: it runs in this context, which raises instead of dropping a digit.
EXACT = Context(prec=4000, traps=[Inexact, InvalidOperation, DivisionByZero, Overflow])
ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data' / 'evaluation' / 'runs.jsonl'
SCHEMA = 'dev-run/2'


class LedgerError(ValueError):
    pass


def validator():
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise SystemExit('Development dependencies are missing; use .venv/bin/python (see docs/setup.md).') from error
    schema = json.loads((ROOT / 'schemas' / 'dev-run.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def read_ledger(path: Path = LEDGER) -> list[dict]:
    """Every row, validated; an unversioned or invalid row, or a repeated (study, run), is an error."""
    check = validator()
    rows, seen, sessions = [], set(), set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise LedgerError(f'{path.name}:{number}: not JSON ({error.msg})') from None
        if not isinstance(row, dict) or row.get('schema') != SCHEMA:
            raise LedgerError(f'{path.name}:{number}: unsupported row version {row.get("schema") if isinstance(row, dict) else None!r}')
        errors = sorted(check.iter_errors(row), key=lambda e: str(e.json_path))
        if errors:
            raise LedgerError(f'{path.name}:{number}: {errors[0].json_path}: {errors[0].message}')
        if (row['study'], row['run']) in seen:
            raise LedgerError(f'{path.name}:{number}: duplicate run {row["run"]} in study {row["study"]}')
        seen.add((row['study'], row['run']))
        parts = (row['provider_usd'], row['unpriced_attempts'], row['unpriced_attempt_usd'], row['unpriced_recall_attempts'], row['unpriced_recall_attempt_usd'])
        if all(part is not None for part in parts):
            if spend_of(*parts) != Decimal(row['spend_usd']):
                raise LedgerError(f'{path.name}:{number}: spend_usd is not provider_usd plus unpriced attempts at their charge')
        elif any(part is not None for part in parts):
            raise LedgerError(f'{path.name}:{number}: provider_usd, unpriced_attempts and unpriced_attempt_usd are recorded together or not at all')
        if row['unpriced_attempts'] is not None and row['unpriced_attempts'] + row['unpriced_recall_attempts'] > row['attempts']:
            raise LedgerError(f'{path.name}:{number}: more unpriced attempts than charged attempts')
        if row['session'] in sessions:
            raise LedgerError(f'{path.name}:{number}: session {row["session"]} is already recorded')
        sessions.add(row['session'])
        rows.append(row)
    return rows


def _json(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise LedgerError(f'{path}: not a JSON object')
    return data


def spend_of(provider_usd: str, unpriced_attempts: int, unpriced_attempt_usd: str, unpriced_recall_attempts: int = 0, unpriced_recall_attempt_usd: str = "0") -> Decimal:
    """A row's spend: provider cost plus unpriced attempts at their charge, summed without rounding."""
    return EXACT.add(EXACT.add(Decimal(provider_usd), EXACT.multiply(Decimal(unpriced_attempts), Decimal(unpriced_attempt_usd))),
                     EXACT.multiply(Decimal(unpriced_recall_attempts), Decimal(unpriced_recall_attempt_usd)))


def plain(amount: Decimal) -> str:
    text = format(amount, 'f')
    return (text.rstrip('0').rstrip('.') or '0') if '.' in text else text


def package_row(package: Path, *, study: int, label: str, upper_bound: bool = False) -> dict:
    """One dev-run/2 row from a finished campaign-run/7 package (receipt campaign-receipt/5). Its spend is the
    receipt's: the provider-reported cost plus each request with no cost record at the route's bound.

    A receipt whose spend is incomplete gets a row only with `upper_bound`, which records the most the run can have
    spent: its declared limit plus the bounds of the possible in-flight player and recall attempts,
    limited by charged attempts; recall contributes only with delivered units. The row has no field that marks it; the run's dated record says so."""
    manifest, receipt_path = _json(package / 'manifest.json'), package / 'receipt.json'
    if not receipt_path.is_file():
        raise LedgerError(f'{package.name}: no receipt.json; reconcile the admission before recording it')
    receipt = _json(receipt_path)
    if receipt.get('schema') != 'campaign-receipt/5':
        raise LedgerError(f'{package.name}: unsupported receipt {receipt.get("schema")!r}')
    if manifest.get('schema') != 'campaign-run/7':
        raise LedgerError(f'{package.name}: unsupported manifest {manifest.get("schema")!r}')
    labels = manifest['labels']
    if receipt['session'] != manifest['session'] or receipt['source_commit'] != manifest['source_commit']:
        raise LedgerError(f'{package.name}: receipt and manifest disagree on session or source')
    spend = receipt['accounting']
    if spend['spend_complete'] is not True and not upper_bound:
        raise LedgerError(f'{package.name}: the receipt records its spend as incomplete; the lead records it with '
            '--record-upper-bound (docs/operations/campaign-run.md) before any further run of the study is admitted')
    if spend['spend_complete'] is True and upper_bound:
        raise LedgerError(f'{package.name}: the receipt records its spend as complete; --record-upper-bound is only for '
            'a receipt whose spend is incomplete')
    if upper_bound:
        from harness.player.knowledge import Knowledge
        attempts=spend['attempts_charged']
        player_count=min(1,attempts)
        recall_count=int(bool(Knowledge(package/'delivered-knowledge.json').records) and attempts>player_count)
        spend = dict(spend, reported_usd=spend['spend_limit_usd'], unpriced_requests=player_count, unpriced_recall_requests=recall_count,
            spent_usd=plain(spend_of(spend['spend_limit_usd'], player_count, spend['unpriced_request_usd'], recall_count, spend['unpriced_recall_request_usd'])))
    ended = datetime.fromtimestamp(receipt['ended_wall'], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return dict(schema=SCHEMA, study=study, run=package.name, label=label, arm=labels['arm'], start=labels['start'],
        lineage=labels.get('lineage'), admission=labels.get('admission'), session=receipt['session'],
        source_commit=receipt['source_commit'], ended=ended, outcome=receipt['outcome'],
        attempts=spend['attempts_charged'], wall_seconds=round(receipt['elapsed_seconds']),
        spend_usd=spend['spent_usd'], provider_usd=spend['reported_usd'], unpriced_attempts=spend['unpriced_requests'],
        unpriced_attempt_usd=spend['unpriced_request_usd'], unpriced_recall_attempts=spend['unpriced_recall_requests'],
        unpriced_recall_attempt_usd=spend['unpriced_recall_request_usd'])


def decimal_text(value: str, name: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise LedgerError(f'{name} must be a decimal, got {value!r}') from None
    if not number.is_finite() or number < 0:
        raise LedgerError(f'{name} must be a non-negative decimal, got {value!r}')
    return value


def record(arguments: argparse.Namespace) -> dict:
    row = package_row(arguments.package, study=arguments.study, label=arguments.label or arguments.package.name,
        upper_bound=arguments.record_upper_bound)
    rows = read_ledger(arguments.ledger)
    if any((r['study'], r['run']) == (row['study'], row['run']) for r in rows):
        raise LedgerError(f'{row["run"]} is already recorded for study {row["study"]}')
    errors = list(validator().iter_errors(row))
    if errors:
        raise LedgerError(f'derived row is invalid: {errors[0].message}')
    if spend_of(row['provider_usd'], row['unpriced_attempts'], row['unpriced_attempt_usd'], row['unpriced_recall_attempts'], row['unpriced_recall_attempt_usd']) != Decimal(row['spend_usd']):
        raise LedgerError(f'{row["run"]}: the receipt\'s spent_usd is not its reported_usd plus unpriced requests at the bound')
    with arguments.ledger.open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    return row


def totals(rows: list[dict], study: int, envelope: Decimal | None, forecast: Decimal | None = None) -> dict:
    """Spend so far; with an envelope, headroom = envelope - spend - 2 x largest admission. Before any admission the
    largest is the stated forecast (e.g. #382's $6.50), or 0 when none is given."""
    chosen = [r for r in rows if r['study'] == study]
    spend = sum((Decimal(r['spend_usd']) for r in chosen), Decimal(0))
    largest = max((Decimal(r['spend_usd']) for r in chosen), default=forecast or Decimal(0))
    result = dict(study=study, admissions=len(chosen), attempts=sum(r['attempts'] for r in chosen),
                  wall_seconds=sum(r['wall_seconds'] for r in chosen), spend_usd=str(spend), largest_usd=str(largest))
    if envelope is not None:
        headroom = envelope - spend - 2 * largest
        result.update(envelope_usd=str(envelope), headroom_usd=str(headroom), admit=headroom >= 0)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ledger', type=Path, default=LEDGER)
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('record', help='append one finished admission')
    add.add_argument('package', type=Path)
    add.add_argument('--study', type=int, required=True)
    add.add_argument('--label', help="the run's short name in its study's dated record (default: the package name)")
    add.add_argument('--record-upper-bound', action='store_true', help='for a receipt whose spend is incomplete only: '
                     'record the limit plus possible player/recall bounds, limited by charged attempts and delivered units')
    total = commands.add_parser('totals', help="a study's spend, optionally against an envelope")
    total.add_argument('--study', type=int, required=True)
    total.add_argument('--envelope', help='decimal envelope in dollars')
    total.add_argument('--forecast-largest', help='decimal largest admission assumed before the first one completes')
    commands.add_parser('check', help='validate every row')
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == 'record':
            print(json.dumps(record(arguments), sort_keys=True))
        elif arguments.command == 'totals':
            envelope = Decimal(decimal_text(arguments.envelope, '--envelope')) if arguments.envelope else None
            forecast = (Decimal(decimal_text(arguments.forecast_largest, '--forecast-largest'))
                        if arguments.forecast_largest else None)
            print(json.dumps(totals(read_ledger(arguments.ledger), arguments.study, envelope, forecast), sort_keys=True))
        else:
            print(f'Run ledger: {len(read_ledger(arguments.ledger))} rows valid.')
        return 0
    except (LedgerError, OSError, KeyError, TypeError, ArithmeticError) as error:
        print(f'Run ledger: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
