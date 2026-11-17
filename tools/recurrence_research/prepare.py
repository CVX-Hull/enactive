"""Inventory visible manifests and prepare one explicitly selected trace subset."""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil

# The projection's step reader is private: no maintained public API exposes this
# selected subset without first projecting all later frames. Keep its use narrow.
from harness.trace.projection import _steps
from .trial import cycle, digest, outcome

SESSION = '507f7c538191fedb29b11639ed137b70'
SOURCE = Path('.runtime/evidence/397-seven-day/computer-sessions/sd1a2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def portfolio(root):
    evidence = root / '.runtime/evidence'
    paths = sorted(evidence.glob('397-seven-day/computer-sessions/*/manifest.json'))
    paths += sorted(evidence.glob('withholding-*/start/manifest.json'))
    paths += sorted((root / '.runtime/starts').glob('*/manifest.json'))
    documents = [(path, json.loads(path.read_text())) for path in paths]
    starts = {path.relative_to(evidence).parts[0]: data for path, data in documents
              if path.is_relative_to(evidence) and path.parent.name == 'start'}
    rows = []
    for path, data in documents:
        if data.get('held_out') or (data.get('lineage') not in (None, 397)):
            continue
        selected = data.get('session') == SESSION
        labels = data.get('labels') or {}
        parent = data.get('source_manifest_sha256')
        # A campaign's files map is launch configuration, not a saved-game payload.
        payload = digest(data['files']) if data.get('schema', '').startswith('start-manifest/') and data.get('files') else None
        predecessor = starts.get(data.get('source_study'), {})
        related = (data.get('lineage') == 397 or predecessor.get('lineage') == 397
                   or data.get('source_study') == '397-seven-day'
                   or path.is_relative_to(evidence/'397-seven-day'))
        unknown = 'unknown: not established by inspected visible frame or manifest'
        rows.append({'path': str(path.relative_to(root)), 'sha256': sha(path),
                     'kind': data.get('schema'), 'session': data.get('session'), 'labels': labels,
                     'source_study': data.get('source_study'), 'parent_archive_manifest_sha256': parent,
                     'source_study_parent_lineage': predecessor.get('lineage'),
                     'parent_moment': unknown,
                     'copy_group': payload or unknown,
                     'world_group': '397-related-group; conservative cluster, including setup restart' if related else unknown,
                     'lineage': '397-L1' if related else (labels.get('lineage') or data.get('lineage') or unknown),
                     'survivor': 'Morgan Hale' if selected else unknown,
                     'profile': 'evac shelter, carried resources' if selected else unknown,
                     'visible_identity_time_location': ('Morgan Hale; Spring day 61 3:11:24 PM; '
                                                        'evac shelter B-19' if selected else unknown),
                     'source_frames': ([f'{SESSION}-{n}' for n in (188, 208, 210)] if selected else []),
                     'setup': {'operator_scenario_label': labels.get('scenario'),
                               'visible_setup_options': unknown},
                     'conditions': {'text': 'bright, Clear, Spring day 61; carried inventory visible',
                                    'source_ids': [f'{SESSION}-188', f'{SESSION}-210']} if selected else unknown,
                     'split': 'development'})
    return {'sources': rows, 'inventory_scope': 'Retained reusable-start manifests and their seven-day source '
            'admissions; other development traces are not assumed to contain reusable saved moments.',
            'grouping': 'Start copy groups hash the complete frozen payload file/hash map, never save contents. '
            'Campaign launch-file maps are not saved-game identities. Parent moment stays unknown '
            'unless an explicit predecessor link is established. '
            'The archive manifest hash identifies the study, not a saved moment; distinct payload '
            'hashes are not proof of distinct worlds. 397 provenance forms one conservative related '
            'cluster. Unknown provenance is not evidence of independent worlds.',
            'selection': 'unacquired', 'test': 'unacquired',
            'held_out': '382 and 522 excluded'}


def worksheet(spec):
    """Compute the finite proposed role bill, keeping unsupported costs explicitly unknown."""
    result = deepcopy(spec)
    rates = result['rates_per_million_usd']
    total = Decimal(0)
    for stage in result['stages']:
        subtotal = Decimal(0)
        for row in stage['allocations']:
            request = (Decimal(row['input_tokens_per_request']) * Decimal(str(rates['cache_write_missing_usage_bound']))
                       + Decimal(row['output_tokens_per_request']) * Decimal(str(rates['output']))) / Decimal(1000000)
            row['usd_per_request'] = str(request)
            row['subtotal_usd'] = str(request * row['requests_max'])
            row['wall_seconds_stage_max'] = row['requests_max'] * row['wall_seconds_per_request']
            subtotal += request * row['requests_max']
        stage['model_bound_usd'] = str(subtotal)
        stage['total_requests'] = sum(row['requests_max'] for row in stage['allocations'])
        stage['wall_seconds_sum_ceiling'] = sum(row['wall_seconds_stage_max'] for row in stage['allocations'])
        total += subtotal
    result['combined_known_model_bound_usd'] = str(total)
    return result


def prepare(root, out):
    root = root.resolve()
    out = out.resolve()
    if not out.is_relative_to(Path.cwd().resolve() / '.runtime'):
        raise ValueError('output must be under this checkout .runtime')
    out.mkdir(parents=True, exist_ok=False)
    spec = json.loads(Path(__file__).with_name('spec.json').read_text())
    inventory = portfolio(root)
    inventory['acquisition_slots'] = [dict(profile=profile, split='development',
        status='unacquired; independent new world/survivor required') for profile in spec['worksheet']['profiles']]
    write(out / 'portfolio.json', inventory)
    session = root / SOURCE
    ids = [f'{SESSION}-{n}' for n in (188, 208, 210)]
    packet = {'status': 'unavailable', 'reason': 'selected source evidence missing'}
    if (session / 'session.sqlite3').is_file() and all((session / 'sources' / f'{sid}.png').is_file() for sid in ids):
        actors, metadata = _steps(session, SESSION)
        steps = [step for steps in actors.values() for step in steps if step.get('frame') in ids]
        if [step['frame'] for step in steps] != ids:
            raise ValueError('selected operations not in expected order')
        frames = out / 'frames'
        frames.mkdir()
        for sid in ids:
            source = session / 'sources' / f'{sid}.png'
            if sha(source) != metadata[sid]['sha256']:
                raise ValueError('frame hash mismatch')
            shutil.copyfile(source, frames / source.name)
        packet = {'status': 'available', 'exposure': 'selected subset of operations 5–7 only; not a complete prefix',
                  'session': SESSION, 'source_manifest_sha256': sha(session / 'manifest.json'),
                  'assignment': {'id': 'development-397-sd1a2-subset', 'world_group': '397-related-group',
                                 'lineage': '397-L1', 'survivor': 'Morgan Hale', 'split': 'development',
                                 'profile': 'evac shelter, carried resources',
                                 'parent_moment': 'continuation of sd1a1; exact saved-moment hash unknown',
                                 'copy_group': 'not a reusable-start copy; selected admission subset',
                                 'candidate_sha256': digest(spec['candidate']),
                                 'role_profile_sha256': digest(spec['worksheet']), 'seed': None,
                                 'endpoint_allowance': 'selected source through operation7; no game execution',
                                 'arm_order': ['single deterministic stand-in'],
                                 'arm': 'single deterministic stand-in, not an arm comparison'},
                  'steps': steps, 'frames': [{'id': sid, 'sha256': sha(frames / f'{sid}.png')} for sid in ids],
                  'visible': [{'source_id': ids[0], 'text': 'Place evac shelter B-19; Spring day 61, 3:11:24 PM.'},
                              {'source_id': ids[1], 'text': 'Character sheet: Morgan Hale.'},
                              {'source_id': ids[2], 'text': 'Inventory lists wooden club, clean water and cattail food.'}],
                  'unknown': ['intent', 'cites', 'hints', 'future actions and outcome']}
    else:
        ids = []
    write(out / 'packet.json', packet)
    write(out / 'cycle.json', cycle(spec['candidate'], ids))
    write(out / 'outcomes.json', outcome(ids))
    write(out / 'worksheet.json', worksheet(spec['worksheet']))
    write(out / 'trial-spec.json', spec['trial'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    prepare(args.root, args.out)


if __name__ == '__main__':
    main()
