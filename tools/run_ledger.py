#!/usr/bin/env python3
"""The tracked development-run ledger, data/evaluation/runs.jsonl (dev-run/3); see docs/contracts/evaluation.md.

record appends the provider subtotal and unknown-cost counts from a current receipt. An incomplete trace
requires --record-upper-bound, which records the separate study admission bound. Historical rows retain
their original recorded basis and numbers. totals uses the row's admission amount against the envelope.
check validates every row. The ledger is the one numeric record of a run: a dated record presents
numbers through the generated run tables (tools/evaluate.py evaluate-table) or by citing the ledger.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Context, Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow, localcontext
import json
from pathlib import Path
import sys

#: Dollar arithmetic never rounds: it runs in this context, which raises instead of dropping a digit.
EXACT = Context(prec=4000, traps=[Inexact, InvalidOperation, DivisionByZero, Overflow])
ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data' / 'evaluation' / 'runs.jsonl'
SCHEMA = 'dev-run/3'


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
        try:
            validate_accounting(row)
        except LedgerError as error:
            raise LedgerError(f'{path.name}:{number}: {error}') from None
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
    """The legacy counted amount or the explicit incomplete-trace bound."""
    return EXACT.add(EXACT.add(Decimal(provider_usd), EXACT.multiply(Decimal(unpriced_attempts), Decimal(unpriced_attempt_usd))),
                     EXACT.multiply(Decimal(unpriced_recall_attempts), Decimal(unpriced_recall_attempt_usd)))


def validate_accounting(row: dict) -> None:
    basis = row['accounting_basis']
    spent = Decimal(row['spend_usd'])
    reported = row['provider_usd']
    player, recall = row['unpriced_attempts'], row['unpriced_recall_attempts']
    player_bound, recall_bound = row['unpriced_attempt_usd'], row['unpriced_recall_attempt_usd']
    upper = row['spend_upper_bound_usd']
    if basis == 'historical':
        parts = (reported, player, player_bound, recall, recall_bound)
        if all(part is not None for part in parts):
            if spend_of(*parts) != spent:
                raise LedgerError('historical spend_usd differs from the recorded provider and bound components')
        elif any(part is not None for part in parts):
            raise LedgerError('historical provider and unpriced components are recorded together or not at all')
    elif reported is None or player is None or recall is None or spent != Decimal(reported) or player_bound is not None or recall_bound is not None:
        raise LedgerError('current spend_usd must equal provider_usd and retain unknown counts without assigned charges')
    if (upper is not None) != (basis == 'incomplete-trace') or (upper is not None and Decimal(upper) < spent):
        raise LedgerError('only an incomplete trace has a separate upper bound at least as large as the observed subtotal')
    if player is not None and player + recall > row['attempts']:
        raise LedgerError('more unpriced attempts than charged attempts')


def plain(amount: Decimal) -> str:
    text = format(amount, 'f')
    return (text.rstrip('0').rstrip('.') or '0') if '.' in text else text


def package_row(package: Path, *, study: int, label: str, upper_bound: bool = False) -> dict:
    """Derive observed cost and unknown attempts from a current, owned campaign receipt."""
    from harness.evaluation.core.sources import MANIFEST_SCHEMA, RECEIPT_SCHEMA, EvaluationError, read_manifest
    try:
        manifest = read_manifest(package)
    except EvaluationError as exc:
        raise LedgerError(str(exc)) from exc
    if manifest['schema'] != MANIFEST_SCHEMA:
        raise LedgerError(f'{package.name}: archived manifests cannot produce new ledger rows')
    receipt_path = package / 'receipt.json'
    if not receipt_path.is_file():
        raise LedgerError(f'{package.name}: no receipt.json; reconcile the admission before recording it')
    receipt = _json(receipt_path)
    if receipt.get('schema') != RECEIPT_SCHEMA:
        raise LedgerError(f'{package.name}: unsupported receipt {receipt.get("schema")!r}')
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
    bound = None
    if upper_bound:
        from harness.player.knowledge import Knowledge
        attempts=spend['attempts_charged']
        player_count=min(1,attempts)
        recall_count=int(bool(Knowledge(package/'delivered-knowledge.json').records) and attempts>player_count)
        observed_or_limit = max(Decimal(spend['reported_usd']), Decimal(spend['spend_limit_usd']))
        bound = plain(spend_of(str(observed_or_limit), player_count, spend['unpriced_request_usd'],
                               recall_count, spend['unpriced_recall_request_usd']))
    ended = datetime.fromtimestamp(receipt['ended_wall'], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return dict(schema=SCHEMA, study=study, run=package.name, label=label, arm=labels['arm'], start=labels['start'],
        lineage=labels.get('lineage'), admission=labels.get('admission'), session=receipt['session'],
        source_commit=receipt['source_commit'], ended=ended, outcome=receipt['outcome'],
        attempts=spend['attempts_charged'], wall_seconds=round(receipt['elapsed_seconds']),
        accounting_basis='incomplete-trace' if upper_bound else 'provider-reported', spend_upper_bound_usd=bound,
        spend_usd=spend['spent_usd'], provider_usd=spend['reported_usd'], unpriced_attempts=spend['unpriced_requests'],
        unpriced_attempt_usd=None, unpriced_recall_attempts=spend['unpriced_recall_requests'], unpriced_recall_attempt_usd=None)


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
    validate_accounting(row)
    with arguments.ledger.open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    return row


def totals(rows: list[dict], study: int, envelope: Decimal | None, forecast: Decimal | None = None) -> dict:
    """Provider subtotal and separately the amounts used to calculate study headroom."""
    chosen = [r for r in rows if r['study'] == study]
    amounts = [Decimal(r['spend_upper_bound_usd'] or r['spend_usd']) for r in chosen]
    reported = [Decimal(r['provider_usd']) for r in chosen if r['provider_usd'] is not None]
    with localcontext(EXACT):
        admission_total = sum(amounts, Decimal(0))
        provider_subtotal = sum(reported, Decimal(0))
    largest = max(amounts, default=forecast or Decimal(0))
    result = dict(study=study, admissions=len(chosen), attempts=sum(r['attempts'] for r in chosen),
                  wall_seconds=sum(r['wall_seconds'] for r in chosen), provider_usd=str(provider_subtotal),
                  admissions_without_provider_subtotal=len(chosen)-len(reported),
                  admission_usd=str(admission_total), largest_admission_usd=str(largest))
    if envelope is not None:
        with localcontext(EXACT):
            headroom = envelope - admission_total - 2 * largest
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
                     'record an admission amount based on the limit, observed charges and possible in-flight attempts')
    total = commands.add_parser('totals', help="a study's provider subtotal and admission amounts, optionally against an envelope")
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
