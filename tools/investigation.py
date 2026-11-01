"""Allowlisted finite evidence projection and closed-case export; no custody."""
from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime
import hashlib
import heapq
import html
import io
import json
import os
from pathlib import Path
import re
import secrets
import struct
import tempfile

from PIL import Image

from harness.computer.protocol import ControlError, closed, decode_json, read_json, source as source_metadata
from harness.observer import tool_value
from tools.control_analysis import analyze_session, read_sources
from tools.host_analysis import MAX_LINE_BYTES, analyze_trace, delta, discover, number
from tools.observer_analysis import witness_summary

ROOT = Path(__file__).resolve().parents[1]
MAX_EVENTS = 2000
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
MAX_RGBA_BYTES = 64 * 1024 * 1024
CASE_KEYS = {'id', 'title', 'session', 'source_commit', 'configuration', 'coverage',
    'events', 'sources', 'assessments', 'accounting'}
CONFIG_KEYS = {'actor_id', 'model', 'provider', 'api', 'effort', 'requested_service_tier',
    'provider_only', 'provider_order', 'allow_fallbacks'}
COVERAGE_KEYS = {'event_candidates', 'event_retained', 'event_omitted', 'source_candidates',
    'source_retained', 'source_omitted', 'observer_status', 'invalid_clocks', 'notes'}
EVENT_KEYS = {'id', 'kind', 'label', 'text', 'text_omitted_chars', 'original_omitted_bytes',
    'actor_id', 'request_id', 'tool_call_id', 'operation_id', 'program_id', 'run_id', 'native_id',
    'source_id', 'start_wall_ms', 'end_wall_ms', 'clock', 'elapsed_ms', 'disposition', 'links', 'metrics'}
IDENTITY_KEYS = {'actor_id', 'request_id', 'tool_call_id', 'operation_id', 'program_id',
    'run_id', 'native_id', 'source_id'}
METRIC_KEYS = {'input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens',
    'cache_write_tokens', 'payload_bytes', 'text_bytes', 'image_bytes', 'image_parts',
    'projection_ms', 'first_body_ms', 'first_content_ms', 'first_tool_argument_ms', 'headers_ms'}
SOURCE_KEYS = {'source_id', 'capture_id', 'presented_ms', 'received_wall_ms', 'sha256',
    'width', 'height', 'png_base64', 'unavailable_reason'}
ASSESSMENT_KEYS = {'label', 'text', 'attribution', 'reference', 'evidence_ids'}
ACCOUNTING_KEYS = {'attempts', 'host_seconds', 'configured_estimate_usd',
    'missing_usage_attempts', 'conservative_reservation_usd'}


def exact(value, keys):
    closed(value, keys)


def allowed(value, keys):
    if type(value) is not dict or value.keys() - keys:
        raise ControlError('Unknown investigation fields')


def text(value, maximum=256, *, nullable=True):
    if value is None and nullable:
        return value
    if not isinstance(value, str) or len(value) > maximum:
        raise ControlError('Invalid bounded investigation text')
    return value


def count(value, *, nullable=False):
    if value is None and nullable:
        return value
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        raise ControlError('Invalid investigation count')
    return value


def numeric(value):
    if value is not None and not number(value):
        raise ControlError('Invalid investigation numeric measurement')
    return value


def sequence(value, maximum):
    if not isinstance(value, list) or len(value) > maximum:
        raise ControlError('Invalid bounded investigation array')
    return value


def png_check(png, width, height, digest):
    if (len(png) < 33 or png[:8] != b'\x89PNG\r\n\x1a\n'
            or png[8:16] != b'\0\0\0\rIHDR'):
        raise ControlError('Malformed original PNG')
    actual = struct.unpack('>II', png[16:24])
    if actual != (width, height) or not width or not height or width * height * 4 > MAX_RGBA_BYTES:
        raise ControlError('Original PNG geometry differs or exceeds decoded budget')
    if hashlib.sha256(png).hexdigest() != digest:
        raise ControlError('Original PNG digest differs')
    try:
        with Image.open(io.BytesIO(png)) as image:
            if image.format != 'PNG' or image.size != actual:
                raise ControlError('Malformed original PNG geometry')
            if getattr(image, 'n_frames', 1) != 1:
                raise ControlError('Animated PNG is not a static original capture')
            image.verify()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ControlError('Malformed original PNG') from exc


def encoded_bundle(bundle):
    try:
        encoded = json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ControlError('Invalid investigation JSON') from exc
    if len(encoded) > MAX_BUNDLE_BYTES:
        raise ControlError('Investigation JSON exceeds 16 MiB')
    return encoded


def validate_bundle(bundle):
    """Reject unknown fields/versions and resource violations before publication."""
    exact(bundle, {'schema', 'cases'})
    # Apply the encoded bound before any potentially expensive image decode.
    encoded_bundle(bundle)
    if bundle['schema'] != 'observer-investigation/1':
        raise ControlError('Unsupported investigation version')
    cases = sequence(bundle['cases'], 4)
    if not cases:
        raise ControlError('Select 1..4 investigation cases')
    ids, source_total = set(), 0
    for case in cases:
        exact(case, CASE_KEYS)
        identity = text(case['id'], 80, nullable=False)
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', identity) is None or identity in ids:
            raise ControlError('Invalid or duplicate investigation case ID')
        ids.add(identity)
        text(case['title'], 240, nullable=False)
        text(case['session'])
        text(case['source_commit'])
        for config in sequence(case['configuration'], 2):
            exact(config, CONFIG_KEYS)
            for field in CONFIG_KEYS - {'provider_only', 'provider_order', 'allow_fallbacks'}:
                text(config[field])
            for field in ('provider_only', 'provider_order'):
                if config[field] is not None:
                    for value in sequence(config[field], 32):
                        text(value, nullable=False)
            if config['allow_fallbacks'] is not None and type(config['allow_fallbacks']) is not bool:
                raise ControlError('Invalid provider fallback setting')
        coverage = case['coverage']
        exact(coverage, COVERAGE_KEYS)
        for field in COVERAGE_KEYS - {'observer_status', 'notes'}:
            count(coverage[field])
        text(coverage['observer_status'], 1000, nullable=False)
        for note in sequence(coverage['notes'], 32):
            text(note, 1000, nullable=False)
        events = sequence(case['events'], MAX_EVENTS)
        event_ids = set()
        for event in events:
            exact(event, EVENT_KEYS)
            identity = text(event['id'], nullable=False)
            if not identity or identity in event_ids:
                raise ControlError('Duplicate or empty investigation event ID')
            event_ids.add(identity)
            if event['kind'] not in {'request', 'tool', 'program', 'operation', 'native', 'source', 'statement', 'observer'}:
                raise ControlError('Unsupported investigation event kind')
            text(event['label'], 240, nullable=False)
            text(event['text'], 4000, nullable=False)
            count(event['text_omitted_chars'])
            count(event['original_omitted_bytes'], nullable=True)
            for field in IDENTITY_KEYS:
                text(event[field])
            for field in ('clock', 'disposition'):
                text(event[field], 1000)
            for field in ('start_wall_ms', 'end_wall_ms', 'elapsed_ms'):
                numeric(event[field])
            if (event['start_wall_ms'] is not None and event['end_wall_ms'] is not None
                    and event['end_wall_ms'] < event['start_wall_ms']):
                raise ControlError('Invalid investigation wall span')
            for link in sequence(event['links'], 64):
                text(link, nullable=False)
            allowed(event['metrics'], METRIC_KEYS)
            for metric in event['metrics'].values():
                numeric(metric)
        selected_ids = set()
        for source in sequence(case['sources'], 16):
            exact(source, SOURCE_KEYS)
            identity = text(source['source_id'], nullable=False)
            if identity in selected_ids:
                raise ControlError('Duplicate investigation source ID')
            selected_ids.add(identity)
            for field in ('capture_id', 'width', 'height'):
                count(source[field], nullable=True)
            for field in ('presented_ms', 'received_wall_ms'):
                numeric(source[field])
            text(source['sha256'])
            text(source['unavailable_reason'], 1000)
            if source['png_base64'] is not None:
                if source['unavailable_reason'] is not None or not isinstance(source['png_base64'], str):
                    raise ControlError('Invalid available investigation source')
                try:
                    png = base64.b64decode(source['png_base64'], validate=True)
                except ValueError as exc:
                    raise ControlError('Invalid PNG encoding') from exc
                if source['width'] is None or source['height'] is None:
                    raise ControlError('Available PNG lacks geometry')
                png_check(png, source['width'], source['height'], source['sha256'])
            elif not source['unavailable_reason']:
                raise ControlError('Unavailable PNG lacks reason')
        source_total += len(case['sources'])
        for assessment in sequence(case['assessments'], 16):
            exact(assessment, ASSESSMENT_KEYS)
            text(assessment['label'], 240, nullable=False)
            text(assessment['text'], 4000, nullable=False)
            text(assessment['attribution'], nullable=False)
            text(assessment['reference'], 1000, nullable=False)
            for evidence in sequence(assessment['evidence_ids'], 64):
                text(evidence, nullable=False)
        exact(case['accounting'], ACCOUNTING_KEYS)
        for field, value in case['accounting'].items():
            count(value, nullable=True) if field in ('attempts', 'missing_usage_attempts') else numeric(value)
        if (coverage['event_retained'] != len(events)
                or coverage['event_candidates'] != len(events) + coverage['event_omitted']
                or coverage['source_retained'] != len(case['sources'])
                or coverage['source_candidates'] != len(case['sources']) + coverage['source_omitted']):
            raise ControlError('Inconsistent investigation coverage counts')
    if source_total > 16:
        raise ControlError('Select at most 16 original PNG entries across all cases')
    return bundle


def public(value, notes, maximum=256):
    """Copy a bounded scalar, never stringify a nested payload."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ControlError('Unexpected nested public scalar')
    if len(value) > maximum:
        note(notes, 'Oversized public identity or label field omitted.')
        return None
    return value


def note(notes, value):
    if value not in notes and len(notes) < 32:
        notes.append(value)


def wall(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            return None
        result = stamp.timestamp() * 1000
        return result if number(result) else None
    except (ValueError, OverflowError, OSError):
        return None


def event(identity, kind, label, **fields):
    result = dict.fromkeys(EVENT_KEYS)
    result.update(id=identity, kind=kind, label=label, text='', text_omitted_chars=0, links=[], metrics={})
    result.update(fields)
    return result


def trace_rows(path):
    """Second-pass public projection stays within the analyzer's input bounds."""
    with path.open('rb') as stream:
        for ordinal in range(1, 2_000_001):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                return
            yield ordinal, decode_json(line, MAX_LINE_BYTES)
        raise ControlError('Selected trace exceeds two million events')


def source_entry(directory, identity, metadata):
    result = dict.fromkeys(SOURCE_KEYS)
    result['source_id'] = identity
    if metadata is None:
        result['unavailable_reason'] = 'Selected original source is not retained in this session.'
        return result
    result.update({key: metadata[key] for key in ('capture_id', 'presented_ms', 'sha256', 'width', 'height')})
    result['received_wall_ms'] = metadata['received_wall'] * 1000
    path = directory / 'sources' / (identity + '.png')
    try:
        if path.is_symlink() or not path.is_file():
            raise ControlError('Original PNG unavailable')
        if path.stat().st_size > MAX_BUNDLE_BYTES:
            raise ControlError('Original PNG exceeds encoded bundle budget')
        with path.open('rb') as stream:
            png = stream.read(MAX_BUNDLE_BYTES + 1)
        if len(png) > MAX_BUNDLE_BYTES:
            raise ControlError('Original PNG exceeds encoded bundle budget')
        png_check(png, result['width'], result['height'], result['sha256'])
        result['png_base64'] = base64.b64encode(png).decode('ascii')
    except (OSError, ControlError) as exc:
        # Never echo a private filesystem exception or substitute latest pixels.
        result['unavailable_reason'] = str(exc) if isinstance(exc, ControlError) else 'Original PNG unavailable.'
    return result


def host_events(path, actor_id, session, analysis, notes):
    """Reuse validated timing and original public projections, never raw args."""
    directory = 'actors/' + path.parent.name
    requests = {r['request_id']: r for r in analysis['requests']}
    starts, tools, request_ids = {}, {}, {}
    valid_clock = analysis['clock_valid']
    for ordinal, original in trace_rows(path):
        kind = original.get('type')
        request = public(original.get('request_id'), notes)
        tool = public(original.get('tool_call_id'), notes)
        prefix = f'host:{directory}:{ordinal}'
        stamp = wall(original.get('wall_time')) if valid_clock else None
        if kind == 'request-start':
            starts[original['request_id']] = (prefix, stamp)
            request_ids[original['request_id']] = prefix
        elif kind in ('response-complete', 'abort') and original.get('request_id') in starts:
            rid = original['request_id']
            identity, start = starts.pop(rid)
            measured = requests[rid]
            metrics = {key: measured.get(key) if number(measured.get(key)) else None
                for key in ('payload_bytes', 'text_bytes', 'image_bytes', 'image_parts')}
            usage = measured.get('usage') or {}
            metrics.update({target: usage.get(source) for target, source in (
                ('input_tokens', 'input'), ('output_tokens', 'output'), ('reasoning_tokens', 'reasoning'),
                ('cache_read_tokens', 'cacheRead'), ('cache_write_tokens', 'cacheWrite'))})
            for target, endpoint in (('headers_ms', measured.get('headers_ms')),
                    ('first_body_ms', measured.get('first_body_ms')),
                    ('first_content_ms', measured['progress'].get('first_content_delta_ms')),
                    ('first_tool_argument_ms', measured['progress'].get('first_tool_argument_delta_ms'))):
                metrics[target] = delta(endpoint, measured.get('fetch_ms')) if valid_clock else None
            end = stamp
            if start is not None and end is not None and end < start:
                start = end = None
            yield event(identity, 'request', 'Model request', actor_id=actor_id, request_id=request,
                start_wall_ms=start, end_wall_ms=end, elapsed_ms=measured['observed_ms'],
                clock='Actor-local monotonic duration; original wall timestamps approximate shared axis.',
                disposition='censored' if measured['censored'] else 'completed', metrics=metrics)
        elif kind == 'assistant-text':
            value = original.get('text')
            if not isinstance(value, str):
                raise ControlError('Invalid public assistant statement')
            omitted = original.get('omitted_bytes')
            count(omitted, nullable=True)
            yield event(prefix, 'statement', 'Public player statement', actor_id=actor_id, request_id=request,
                text=value[:4000], text_omitted_chars=max(0, len(value) - 4000), original_omitted_bytes=omitted,
                links=[request_ids[request]] if request in request_ids else [],
                start_wall_ms=stamp, clock='Original host wall timestamp; public statement is a player claim.')
        elif kind == 'context-image-projection':
            yield event(prefix, 'observer', 'Host context image projection', actor_id=actor_id,
                request_id=request, start_wall_ms=stamp, clock='Host projection measurement.',
                metrics={'projection_ms': original.get('projection_ms') if number(original.get('projection_ms')) else None})
        elif kind == 'tool-start':
            tools[(original.get('request_id'), original.get('tool_call_id'))] = (prefix, original, stamp)
        elif kind == 'tool-result':
            identity, start_original, start = tools.pop((original.get('request_id'), original.get('tool_call_id')))
            value = tool_value(original)
            program_actor = actor_id
            if value.get('schema') == 'player-service-result/1' and isinstance(value.get('value'), dict):
                # Current original-result collection can retain a program projection.
                # Select the same public projection, never progress args or state.
                if value['value'].get('schema') in ('player-program-run/1', 'player-program/1'):
                    if value['value']['schema'] == 'player-program-run/1':
                        program_actor = public(value.get('actor_id'), notes)
                    value = value['value']
            known = value.get('schema') in ('computer-operation/1', 'player-program-run/1', 'player-program/1', 'player-service-result/1', 'player-source-read/1')
            operation = public(value.get('operation_id'), notes) if value.get('schema') == 'computer-operation/1' else None
            source_id = None
            if known and isinstance(value.get('source'), dict):
                candidate = value['source']
                # Retain original source metadata only after current validation;
                # remembered prior-session source IDs remain explicit, not current pixels.
                if value.get('schema') == 'player-source-read/1':
                    candidate = source_metadata(candidate)
                source_id = public(candidate.get('source_id'), notes)
            run_id = public(value.get('run_id'), notes) if value.get('schema') == 'player-program-run/1' else None
            program = public(value.get('program_id'), notes) if run_id else (
                public(value.get('id'), notes) if value.get('schema') == 'player-program/1' else None)
            links = [request_ids[request]] if request in request_ids else []
            if operation:
                links.append('operation:' + operation)
            if source_id:
                links.append('source:' + source_id)
            if run_id:
                links.append('program:' + run_id)
            end = stamp
            if start is not None and end is not None and end < start:
                start = end = None
            yield event(identity, 'tool', public(start_original.get('tool'), notes, 240) or 'Tool call',
                actor_id=actor_id, request_id=request, tool_call_id=tool, operation_id=operation,
                source_id=source_id, run_id=run_id, program_id=program, links=links,
                disposition=public(value.get('status'), notes, 1000) if known else None,
                start_wall_ms=start, end_wall_ms=end,
                elapsed_ms=delta(original.get('monotonic_ms'), start_original.get('monotonic_ms')) if valid_clock else None,
                clock='Actor-local host monotonic duration; original wall timestamps approximate shared axis.')
            if run_id:
                related = []
                for child in sequence(value.get('operations'), 200_000):
                    if not isinstance(child, dict):
                        raise ControlError('Invalid original program operation reference')
                    child_id = public(child.get('operation_id'), notes)
                    if child_id and child.get('actor_id') == program_actor and child.get('session') == session:
                        related.append('operation:' + child_id)
                elapsed = value.get('elapsed_seconds')
                yield event('program:' + run_id, 'program', 'Original program execution', actor_id=program_actor,
                    request_id=request, tool_call_id=tool, program_id=program, run_id=run_id,
                    links=list(dict.fromkeys(related))[:64], end_wall_ms=stamp,
                    elapsed_ms=elapsed * 1000 if number(elapsed) else None,
                    disposition=public(value.get('status'), notes, 1000),
                    clock='Host program-result/collection receipt point; original elapsed_seconds remains separate. Execution wall start/end are not recorded.')
                if len(set(related)) > 64:
                    note(notes, 'Program child links beyond 64 omitted; original child IDs remain in operation rows.')
    for rid, (identity, start) in starts.items():
        yield event(identity, 'request', 'Model request', actor_id=actor_id, request_id=public(rid, notes),
            start_wall_ms=start, elapsed_ms=requests[rid]['observed_ms'], disposition='censored',
            clock='Actor-local monotonic clock; missing original response endpoint.')
    for (rid, tid), (identity, original, start) in tools.items():
        yield event(identity, 'tool', public(original.get('tool'), notes, 240) or 'Tool call',
            actor_id=actor_id, request_id=public(rid, notes), tool_call_id=public(tid, notes),
            start_wall_ms=start, disposition='pending', clock='Original host wall timestamp; missing tool result.')


def export_case(selected, selection_parent):
    allowed(selected, {'id', 'title', 'directory', 'observer_exports', 'source_ids', 'assessments'})
    if not {'id', 'title', 'directory'} <= selected.keys():
        raise ControlError('Case selection requires id, title and directory')
    text(selected['directory'], 4096, nullable=False)
    directory = selection_parent / selected['directory']
    if directory.is_symlink() or not directory.is_dir():
        raise ControlError('Select an existing closed case directory')
    receipt = read_json(directory / 'receipt.json', 1024 * 1024)
    if (not isinstance(receipt, dict) or receipt.get('schema') != 'campaign-receipt/2'
            or any(receipt.get(key) is not True for key in ('deciding_hosts_quiescent',
                'native_absence_verified', 'input_authority_revoked'))):
        raise ControlError('Investigation requires a current closed campaign receipt')
    control = analyze_session(directory)
    if receipt.get('session') != control['session']:
        raise ControlError('Closed receipt session differs from computer store')
    driver = receipt.get('driver')
    if driver is not None and (not isinstance(driver, dict) or driver.get('schema') != 'player-driver/4'):
        raise ControlError('Unsupported closed campaign driver version')
    driver = driver or {}
    actors = {}
    for actor in sequence(driver.get('actors', []), 2):
        if not isinstance(actor, dict) or type(actor.get('index')) is not int:
            raise ControlError('Invalid original campaign actor identity')
        actors[f"{actor['index']:03d}"] = actor.get('actor_id')
    accounting = receipt.get('accounting') or {}
    if not isinstance(accounting, dict):
        raise ControlError('Invalid original campaign accounting')
    return project_case(selected, selection_parent, directory, control, actors,
        receipt.get('source_commit'), dict(attempts=driver.get('attempts_charged'),
            host_seconds=driver.get('host_seconds_used'), configured_estimate_usd=driver.get('configured_estimate_usd'),
            missing_usage_attempts=driver.get('missing_usage_attempts'),
            conservative_reservation_usd=accounting.get('consumed_conservative_reservation_usd')))


def project_case(selected, selection_parent, directory, control, actors, source_commit, accounting,
        *, traces=None, analyses=None, recent_share=None, notes=None, image_directory=None):
    """Project one validated finite evidence set; callers own selection and closure."""
    notes = list(notes or [])
    for value in ('Only allowlisted public evidence is exported; raw arguments, prompts, private reasoning and paths are omitted.',
            'Wall clocks provide approximate shared ordering; actor monotonic clocks are never subtracted across actors.',
            'Accounting estimates and conservative reservations are not invoices.'):
        note(notes, value)
    retained, event_candidates, invalid_clocks = [], 0, 0
    candidates = Counter()
    recent = {}
    def add(row, producer_order=None):
        nonlocal event_candidates, invalid_clocks
        event_candidates += 1
        candidates[row['kind']] += 1
        if row['start_wall_ms'] is None and row['elapsed_ms'] is None:
            invalid_clocks += 1
        if recent_share is not None:
            rows = recent.setdefault(row['kind'], [])
            heapq.heappush(rows, (producer_order or (0, event_candidates), event_candidates, row))
            # Keep a bounded candidate reserve so quiet lanes can lend unused
            # capacity without discarding records when the whole case fits.
            if len(rows) > MAX_EVENTS:
                heapq.heappop(rows)
        elif len(retained) < MAX_EVENTS:
            retained.append(row)
    configuration = []
    if traces is None:
        try:
            traces = discover([directory])
        except ControlError:
            if (directory / 'actors').exists() or (directory / 'host.jsonl').exists():
                raise
            traces = []
            note(notes, 'No selected host trace is available.')
    if len(traces) > 2:
        raise ControlError('Current campaign supports at most two actor hosts')
    seen_programs = set()
    for trace_index, path in enumerate(traces):
        analysis = analyses[path] if analyses is not None else analyze_trace(path)
        if analysis['coverage'] != 'player_host':
            note(notes, 'Selected host trace has unsupported or missing current telemetry; host rows unavailable.')
            continue
        actor_id = public(actors.get(path.parent.name), notes)
        if actor_id is None:
            note(notes, 'Original actor ID is not recorded for a selected host directory.')
        config = analysis['configuration']
        routing = config.get('provider_routing') or {}
        if not isinstance(routing, dict):
            raise ControlError('Invalid original provider routing')
        configuration.append({key: public(config.get(key), notes) for key in
            ('model', 'provider', 'api', 'effort', 'requested_service_tier')} | dict(actor_id=actor_id,
                provider_only=routing.get('only'), provider_order=routing.get('order'), allow_fallbacks=routing.get('allow_fallbacks')))
        if not analysis['clock_valid']:
            note(notes, 'Invalid host monotonic clock: original host spans and timing metrics are unavailable.')
        host_ordinal = 0
        for row in host_events(path, actor_id, control['session'], analysis, notes):
            if row['id'].startswith('host:'):
                host_ordinal = int(row['id'].rsplit(':', 1)[1])
            if row['kind'] == 'program':
                if row['run_id'] in seen_programs:
                    continue
                seen_programs.add(row['run_id'])
            # Incomplete host spans are yielded at EOF; retain by their actual
            # original start ordinal instead of mistaking that yield for recency.
            add(row, (trace_index, host_ordinal))
    operations = {row['operation_id']: row for row in control['operations']}
    for row in operations.values():
        add(event('operation:' + row['operation_id'], 'operation', 'Computer ' + row['kind'],
            actor_id=public(row['actor_id'], notes), operation_id=public(row['operation_id'], notes),
            start_wall_ms=row['created_wall'] * 1000, disposition=row['status'],
            clock='Original operation creation wall clock; operation completion time is not recorded.'))
    for row in control['native_rows']:
        timing = row['original_timing']
        start, end = timing.get('intent_wall'), timing.get('receipt_received_wall')
        if start is not None and end is not None and end < start:
            start = end = None
        identity = public(row['native_id'], notes)
        operation = public(row['operation_id'], notes)
        source_id = public(row['source_id'], notes)
        add(event('native:' + identity, 'native', 'Original native exchange',
            actor_id=public(operations[row['operation_id']]['actor_id'], notes), native_id=identity,
            operation_id=operation, source_id=source_id, start_wall_ms=start * 1000 if start is not None else None,
            end_wall_ms=end * 1000 if end is not None else None, elapsed_ms=row['intent_to_receipt_ms'],
            disposition=row['disposition'], links=['operation:' + operation] + (['source:' + source_id] if source_id else []),
            clock='Original native intent/receipt monotonic duration; wall timestamps approximate shared axis.'))
        if row['additional_collection_disposition'] is not None:
            later_source = public(row['additional_source_id'], notes)
            add(event('collection:' + identity, 'native', 'Later original collection', native_id=identity,
                operation_id=operation, source_id=later_source, disposition=row['additional_collection_disposition'],
                links=['native:' + identity] + (['source:' + later_source] if later_source else []),
                clock='Additional collection has no retained original timing; does not replace original receipt.'))
    originals = {row['source_id']: row for row in read_sources(directory)}
    for identity, row in originals.items():
        add(event('source:' + identity, 'source', 'Original presented image', source_id=identity,
            start_wall_ms=row['presented_ms'], end_wall_ms=None,
            clock='Original native presentation wall clock; receipt wall time retained in selected source entry.'))
    observer_paths = [selection_parent / text(value, 4096, nullable=False)
        for value in sequence(selected.get('observer_exports', []), 32)]
    observer_status = 'not_selected'
    if observer_paths:
        report = witness_summary([directory, *observer_paths])
        observer_status = 'exact_source_DOM_witnesses'
        omitted = sum(value['omitted_rows'] for value in report['exports'])
        if omitted:
            note(notes, f'Original selected observer exports report {omitted} omitted rows (overlapping exports may repeat omissions).')
        for row in report['source_rows']:
            if not row['distinct_matching_presentations']:
                continue
            invalid = row['missing_reason'] is not None
            add(event('observer:' + row['source_id'], 'observer', 'First exact retained DOM witness',
                source_id=row['source_id'], start_wall_ms=None if invalid else row['presented_ms'],
                end_wall_ms=None if invalid else row['dom_replaced_wall_ms'],
                elapsed_ms=None if invalid else row['presented_to_dom_ms'], disposition=row['missing_reason'] or 'displayed',
                links=['source:' + row['source_id']],
                clock='Native/browser wall clocks assumed shared; DOM replacement is not physical paint.'))
        note(notes, f"{report['missing_source_matches']} retained sources lack a valid exact DOM witness; {report['unmatched_presentations']} selected presentations are unmatched against this session/database (exports may also contain other sessions).")
    selected_sources = sequence(selected.get('source_ids', []), 16)
    if len(set(text(value, nullable=False) for value in selected_sources)) != len(selected_sources):
        raise ControlError('Duplicate selected source ID')
    sources = [source_entry(image_directory or directory, identity, originals.get(identity)) for identity in selected_sources]
    if any(value['png_base64'] is None for value in sources):
        note(notes, 'Some explicitly selected original images are unavailable; no substitute pixels are exported.')
    if recent_share is not None:
        share = min(recent_share, MAX_EVENTS // max(1, len(recent)))
        allowance = {kind: min(share, len(rows)) for kind, rows in recent.items()}
        spare = MAX_EVENTS - sum(allowance.values())
        while spare > 0:
            grew = False
            for kind, rows in recent.items():
                if spare and allowance[kind] < len(rows):
                    allowance[kind] += 1; spare -= 1; grew = True
            if not grew:
                break
        for kind in ('request', 'tool', 'program', 'operation', 'native', 'source', 'statement', 'observer'):
            count = allowance.get(kind, 0)
            rows = [item[2] for item in sorted(recent.get(kind, ()))[-count:]] if count else []
            retained.extend(rows)
            cutoff = rows[0]['id'] if rows else 'none'
            note(notes, f'{kind}: candidates={candidates[kind]} retained={len(rows)} omitted={candidates[kind] - len(rows)}; first retained original={cutoff}; latest by producer order, unknown clocks remain null.')
        # Stable ties/unknowns preserve producer order; no synthetic time values enter rows.
        def recorded_wall(row):
            return row['start_wall_ms'] if row['start_wall_ms'] is not None else row['end_wall_ms']
        retained.sort(key=lambda row: (recorded_wall(row) is None, recorded_wall(row) or 0))
    omitted_events = event_candidates - len(retained)
    if omitted_events:
        note(notes, f'{omitted_events} complete event rows omitted by the selected export event bound.')
    retained_ids = {row['id'] for row in retained}
    if any(link not in retained_ids for row in retained for link in row['links']):
        note(notes, 'Some explicit event links target omitted or unavailable original rows; dangling links are retained.')
    if invalid_clocks:
        note(notes, 'Missing or invalid event clock measurements remain null; no zero duration is substituted.')
    result = dict(id=selected['id'], title=selected['title'], session=control['session'],
        source_commit=public(source_commit, notes), configuration=configuration,
        coverage=dict(event_candidates=event_candidates, event_retained=len(retained), event_omitted=omitted_events,
            source_candidates=len(originals) + sum(identity not in originals for identity in selected_sources),
            source_retained=len(sources), source_omitted=len(originals) - sum(identity in originals for identity in selected_sources),
            observer_status=observer_status, invalid_clocks=invalid_clocks, notes=notes),
        events=retained, sources=sources, assessments=selected.get('assessments', []),
        accounting=accounting)
    return result


def export_selection(path):
    path = Path(path)
    selected = read_json(path, 1024 * 1024)
    exact(selected, {'schema', 'cases'})
    if selected['schema'] != 'investigation-selection/1':
        raise ControlError('Unsupported investigation selection version')
    cases = sequence(selected['cases'], 4)
    if not cases:
        raise ControlError('Select 1..4 closed cases')
    if sum(len(sequence(case.get('source_ids', []), 16)) for case in cases if isinstance(case, dict)) > 16:
        raise ControlError('Select at most 16 original PNG entries across all cases')
    return validate_bundle(dict(schema='observer-investigation/1',
        cases=[export_case(case, path.resolve().parent) for case in cases]))


def script_literal(value):
    return json.dumps(value, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def html_document(bundle):
    """Embed the maintained shared reader, worker, CSS and inert validated data."""
    validate_bundle(bundle)
    assets = {name: (ROOT / 'web' / name).read_text(encoding='utf-8') for name in
        ('investigation.js', 'investigation.css', 'investigation-worker.js')}
    nonce = secrets.token_hex(16)
    policy = (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
        "worker-src blob:; img-src blob:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
    code = f'''const style=document.createElement('style');style.nonce={script_literal(nonce)};
style.textContent={script_literal(assets['investigation.css'])};document.head.append(style);
const reader=document.createElement('script');reader.nonce={script_literal(nonce)};
reader.textContent={script_literal(assets['investigation.js'])};document.head.append(reader);
EnactiveInvestigation.mount(document.getElementById('investigation'),{{
workerSource:{script_literal(assets['investigation-worker.js'])},
initialText:{script_literal(encoded_bundle(bundle).decode('utf-8'))}}});'''
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(policy, quote=True)}">'
        '<title>Recorded investigation</title></head><body class="recorded-investigation-document"><main id="investigation"></main>'
        f'<script nonce="{nonce}">{code}</script></body></html>\n')


def write_export(selection_path, output_path, html_path=None):
    """Validate all outputs first; publish complete files without overwriting."""
    paths = [Path(output_path)] + ([Path(html_path)] if html_path is not None else [])
    if len({path.resolve() for path in paths}) != len(paths) or any(path.exists() or path.is_symlink() for path in paths):
        raise ControlError('Investigation output already exists or paths overlap')
    bundle = export_selection(selection_path)
    payloads = [encoded_bundle(bundle)]
    if html_path is not None:
        payloads.append(html_document(bundle).encode('utf-8'))
    temporary, published = [], []
    try:
        for path, payload in zip(paths, payloads, strict=True):
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.investigation-', delete=False) as stream:
                temporary.append(Path(stream.name))
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        for source, destination in zip(temporary, paths, strict=True):
            os.link(source, destination)
            published.append(destination)
    except (OSError, ValueError) as exc:
        for path in published:
            path.unlink()
        raise ControlError('Cannot publish investigation outputs without overwrite') from exc
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return bundle
