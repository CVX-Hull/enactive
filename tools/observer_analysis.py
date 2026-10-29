"""Exact retained computer-source/browser DOM joins; no paint or goal inference."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from harness.computer.protocol import ControlError, closed, integer, read_json
from tools.control_analysis import read_sources
from tools.host_analysis import distribution, number

MAX_EXPORT_BYTES = 64 * 1024 * 1024
ROW_KEYS = {'session', 'source_id', 'capture_id', 'presented_ms', 'observed_at_wall_ms',
    'decode_finished_wall_ms', 'dom_replaced_wall_ms', 'outcome', 'error'}


def witness_summary(paths: list[Path]) -> dict:
    if not 2 <= len(paths) <= 33:
        raise ControlError('Select one session database/directory and 1..32 observer exports')
    sources = read_sources(paths[0])
    if sum(path.stat().st_size for path in paths[1:]) > 256 * 1024 * 1024:
        raise ControlError('Selected observer exports exceed 256 MiB')
    candidates, exports = {}, []
    for path in paths[1:]:
        data = read_json(path, MAX_EXPORT_BYTES)
        if not isinstance(data, dict) or data.get('schema') != 'observer-timing/4':
            raise ControlError('Unsupported observer timing export')
        closed(data, {'schema', 'retention_limit', 'omitted_rows', 'clock', 'scope', 'rows'})
        if type(data['retention_limit']) is not int or data['retention_limit'] != 2000:
            raise ControlError('Unsupported observer retention limit')
        integer(data['omitted_rows'], 0, 2**53 - 1)
        if (not isinstance(data['clock'], str) or not isinstance(data['scope'], str)
                or not isinstance(data['rows'], list) or len(data['rows']) > 2000):
            raise ControlError('Invalid bounded observer timing rows')
        outcomes = Counter()
        for row in data['rows']:
            closed(row, ROW_KEYS)
            if not isinstance(row['session'], str) or not isinstance(row['source_id'], str):
                raise ControlError('Invalid observer source/session identity')
            integer(row['capture_id'], 1, 2**53 - 1)
            integer(row['presented_ms'], 1, 2**53 - 1)
            if row['outcome'] not in ('pending', 'displayed', 'unavailable', 'superseded'):
                raise ControlError('Unsupported DOM outcome')
            if row['error'] is not None and not isinstance(row['error'], str):
                raise ControlError('Invalid observer error metadata')
            for field in ('observed_at_wall_ms', 'decode_finished_wall_ms', 'dom_replaced_wall_ms'):
                if row[field] is not None and not number(row[field]):
                    raise ControlError('Expected finite browser wall clocks')
            outcomes[row['outcome']] += 1
            if row['outcome'] != 'displayed':
                continue
            if any(row[field] is None for field in ('observed_at_wall_ms', 'decode_finished_wall_ms', 'dom_replaced_wall_ms')):
                raise ControlError('Displayed source lacks original browser clocks')
            key = (row['session'], row['source_id'], row['capture_id'], row['presented_ms'])
            clock = tuple(row[field] for field in ('observed_at_wall_ms', 'decode_finished_wall_ms', 'dom_replaced_wall_ms'))
            # Repeated exports of the same presentation contribute one witness.
            candidates.setdefault(key, {})[clock] = row
        exports.append({'path': str(path), 'omitted_rows': data['omitted_rows'],
            'rows': len(data['rows']), 'outcomes': dict(outcomes)})
    rows, presented_samples, received_samples, matched_keys = [], [], [], set()
    for value in sources:
        key = (value['session'], value['source_id'], value['capture_id'], value['presented_ms'])
        matches = list(candidates.get(key, {}).values())
        witness = min(matches, key=lambda row: row['dom_replaced_wall_ms'], default=None)
        dom = witness['dom_replaced_wall_ms'] if witness else None
        elapsed = dom - value['presented_ms'] if dom is not None else None
        received = dom - value['received_wall'] * 1000 if dom is not None else None
        invalid_clock = witness is not None and (elapsed < 0 or received < 0
            or not value['presented_ms'] <= witness['observed_at_wall_ms']
                <= witness['decode_finished_wall_ms'] <= dom)
        rows.append({**value, 'observed_at_wall_ms': witness['observed_at_wall_ms'] if witness else None,
            'decode_finished_wall_ms': witness['decode_finished_wall_ms'] if witness else None,
            'dom_replaced_wall_ms': dom, 'presented_to_dom_ms': elapsed, 'received_to_dom_ms': received,
            'distinct_matching_presentations': len(matches),
            'missing_reason': 'invalid_cross_clock_interval' if invalid_clock else None if witness else 'no_exact_DOM_match'})
        if witness:
            matched_keys.add(key)
        if elapsed is not None and not invalid_clock:
            presented_samples.append(elapsed)
            received_samples.append(received)
    return {'schema': 'witness-analysis/2',
        'scope': 'First retained exact session/source/capture DOM witness assuming shared wall clock; not physical paint, model attention, source freshness or useful-goal latency',
        'source_database': str(paths[0]), 'exports': exports, 'source_rows': rows,
        'unique_source_presented_to_dom_ms': distribution(presented_samples),
        'unique_source_received_to_dom_ms': distribution(received_samples),
        'unmatched_presentations': sum(len(value) for key, value in candidates.items() if key not in matched_keys),
        'missing_source_matches': sum(row['missing_reason'] is not None for row in rows)}
