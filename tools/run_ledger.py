#!/usr/bin/env python3
"""The tracked development-run ledger, data/evaluation/runs.jsonl (dev-run/1); see docs/contracts/evaluation.md.

record derives one admission's row from its package (campaign-run/5 manifest and campaign-receipt/3) plus the
operator's provider reconciliation, and appends it; a package without a receipt gets no row. totals reports a
study's spend against an envelope under the actual-spend admission rule (new spend plus twice the largest
admission). check validates every row and cross-checks the hand-scored run tables' attempts, dollars and wall
seconds against the ledger (ADR008 keeps those rows hand-written; this only compares them).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data' / 'evaluation' / 'runs.jsonl'
SCHEMA = 'dev-run/1'
# Documents holding hand-scored run tables that the ledger cross-checks.
HAND_TABLES = {'docs/development-runs.md': (372, 382)}
ATTEMPT_COLUMNS = ('Attempts', 'Attempts (setup)')
SPEND_COLUMNS = ('$ upper bound', '$ actual')


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
        parts = (row['provider_usd'], row['unpriced_attempts'], row['unpriced_attempt_usd'])
        if all(part is not None for part in parts):
            if Decimal(parts[0]) + parts[1] * Decimal(parts[2]) != Decimal(row['spend_usd']):
                raise LedgerError(f'{path.name}:{number}: spend_usd is not provider_usd plus unpriced attempts at their charge')
        elif any(part is not None for part in parts):
            raise LedgerError(f'{path.name}:{number}: provider_usd, unpriced_attempts and unpriced_attempt_usd are recorded together or not at all')
        if row['unpriced_attempts'] is not None and row['unpriced_attempts'] > row['attempts']:
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


def package_row(package: Path, *, study: int, label: str, spend_usd: str, provider_usd: str,
                unpriced_attempts: int, unpriced_attempt_usd: str) -> dict:
    """One dev-run/1 row from a finished campaign-run/5 package (receipt campaign-receipt/3)."""
    manifest, receipt_path = _json(package / 'manifest.json'), package / 'receipt.json'
    if not receipt_path.is_file():
        raise LedgerError(f'{package.name}: no receipt.json; reconcile the admission before recording it')
    receipt = _json(receipt_path)
    if receipt.get('schema') != 'campaign-receipt/3':
        raise LedgerError(f'{package.name}: unsupported receipt {receipt.get("schema")!r}')
    if manifest.get('schema') != 'campaign-run/5':
        raise LedgerError(f'{package.name}: unsupported manifest {manifest.get("schema")!r}')
    labels = manifest['labels']
    if receipt['session'] != manifest['session'] or receipt['source_commit'] != manifest['source_commit']:
        raise LedgerError(f'{package.name}: receipt and manifest disagree on session or source')
    ended = datetime.fromtimestamp(receipt['ended_wall'], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return dict(schema=SCHEMA, study=study, run=package.name, label=label, arm=labels['arm'], start=labels['start'],
        lineage=labels.get('lineage'), admission=labels.get('admission'), session=receipt['session'],
        source_commit=receipt['source_commit'], ended=ended, outcome=receipt['outcome'],
        attempts=receipt['accounting']['attempts_charged'], wall_seconds=round(receipt['elapsed_seconds']),
        spend_usd=spend_usd, provider_usd=provider_usd, unpriced_attempts=unpriced_attempts,
        unpriced_attempt_usd=unpriced_attempt_usd)


def decimal_text(value: str, name: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise LedgerError(f'{name} must be a decimal, got {value!r}') from None
    if not number.is_finite() or number < 0:
        raise LedgerError(f'{name} must be a non-negative decimal, got {value!r}')
    return value


def record(arguments: argparse.Namespace) -> dict:
    provider_usd = decimal_text(arguments.provider_usd, '--provider-usd')
    charge = decimal_text(arguments.unpriced_attempt_usd, '--unpriced-attempt-usd')
    if not (arguments.package / 'receipt.json').is_file():
        raise LedgerError(f'{arguments.package.name}: no receipt.json; reconcile the admission before recording it')
    attempts = _json(arguments.package / 'receipt.json')['accounting']['attempts_charged']
    if not 0 <= arguments.provider_records <= attempts:
        raise LedgerError(f'--provider-records must be between 0 and the {attempts} charged attempts')
    unpriced = attempts - arguments.provider_records
    spend = Decimal(provider_usd) + unpriced * Decimal(charge)
    row = package_row(arguments.package, study=arguments.study, label=arguments.label or arguments.package.name,
        spend_usd=provider_usd if not unpriced else format(spend, 'f'), provider_usd=provider_usd,
        unpriced_attempts=unpriced, unpriced_attempt_usd=charge)
    rows = read_ledger(arguments.ledger)
    if any((r['study'], r['run']) == (row['study'], row['run']) for r in rows):
        raise LedgerError(f'{row["run"]} is already recorded for study {row["study"]}')
    errors = list(validator().iter_errors(row))
    if errors:
        raise LedgerError(f'derived row is invalid: {errors[0].message}')
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


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _integer(text: str) -> int | None:
    match = re.match(r'[0-9][0-9,]*', text)
    return int(match.group(0).replace(',', '')) if match else None


def hand_rows(text: str) -> list[tuple[str, int, int, str, int]]:
    """(label, line, attempts, dollars, wall) for every row of a table with attempt, dollar and wall columns."""
    found, lines = [], text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith('|') or index + 1 >= len(lines) or not re.match(r'^\|[ :|-]+\|$', lines[index + 1]):
            continue
        header = _cells(line)
        attempts = next((header.index(c) for c in ATTEMPT_COLUMNS if c in header), None)
        spend = next((header.index(c) for c in SPEND_COLUMNS if c in header), None)
        if attempts is None or spend is None or 'Wall s' not in header:
            continue
        wall = header.index('Wall s')
        for number in range(index + 2, len(lines)):
            if not lines[number].startswith('|'):
                break
            cells = _cells(lines[number])
            found.append((cells[0].strip('`'), number + 1, _integer(cells[attempts]), cells[spend], _integer(cells[wall])))
    return found


def cross_check(rows: list[dict], documents: dict[str, tuple[int, ...]] = HAND_TABLES, root: Path = ROOT) -> list[str]:
    """Within each document's studies, every hand row must equal exactly one ledger row with its label (a label
    repeated in a study is told apart by its values), and every ledger row of those studies must have a hand row."""
    errors, matched = [], set()
    for document, studies in documents.items():
        for label, line, attempts, dollars, wall in hand_rows((root / document).read_text()):
            candidates = [r for r in rows if r['study'] in studies and r['label'] == label]
            if not candidates:
                errors.append(f'{document}:{line}: hand row {label} has no ledger row in study {", ".join(map(str, studies))}')
                continue
            hits = [r for r in candidates if r['attempts'] == attempts and r['wall_seconds'] == wall
                    and dollars == f'{Decimal(r["spend_usd"]):.2f}']
            if len(hits) != 1:
                errors.append(f'{document}:{line}: hand row {label} ({attempts} attempts, ${dollars}, {wall} s) '
                              f'matches {len(hits)} ledger rows')
            else:
                matched.add((hits[0]['study'], hits[0]['run']))
    covered = {study for studies in documents.values() for study in studies}
    errors.extend(f'{r["run"]}: study {r["study"]} has no hand-table document in HAND_TABLES'
                  for r in rows if r['study'] not in covered)
    errors.extend(f'{r["run"]} (study {r["study"]}, label {r["label"]}): no hand-scored row cross-checks it'
                  for r in rows if r['study'] in covered and (r['study'], r['run']) not in matched)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ledger', type=Path, default=LEDGER)
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('record', help='append one finished admission')
    add.add_argument('package', type=Path)
    add.add_argument('--study', type=int, required=True)
    add.add_argument('--label', help="the run's name in its hand-scored table (default: the package name)")
    add.add_argument('--provider-records', type=int, required=True, help='charged attempts with a provider record')
    add.add_argument('--provider-usd', required=True, help='decimal provider-reported cost of those attempts')
    add.add_argument('--unpriced-attempt-usd', required=True, help='decimal worst-case charge per unpriced attempt')
    total = commands.add_parser('totals', help="a study's spend, optionally against an envelope")
    total.add_argument('--study', type=int, required=True)
    total.add_argument('--envelope', help='decimal envelope in dollars')
    total.add_argument('--forecast-largest', help='decimal largest admission assumed before the first one completes')
    commands.add_parser('check', help='validate rows and cross-check the hand-scored tables')
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
            errors = cross_check(read_ledger(arguments.ledger))
            if errors:
                raise LedgerError('\n'.join(errors))
            print('Run ledger rows and hand-scored run tables: consistent.')
        return 0
    except (LedgerError, OSError, KeyError, TypeError) as error:
        print(f'Run ledger: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
