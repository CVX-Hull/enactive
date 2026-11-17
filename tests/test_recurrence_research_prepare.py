import json
from pathlib import Path

from decimal import Decimal

from tools.recurrence_research.prepare import portfolio, prepare, worksheet

SPEC = Path(__file__).resolve().parents[1] / 'data/recurrence-research/spec.json'


def test_absent_sources_are_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.runtime').mkdir()
    out = tmp_path / '.runtime' / 'output'
    prepare(tmp_path, out, SPEC)
    assert json.loads((out / 'packet.json').read_text())['status'] == 'unavailable'
    assert json.loads((out / 'cycle.json').read_text())['status'] == 'unavailable'


def test_packet_exposes_only_selected_operations(tmp_path, monkeypatch):
    import hashlib
    from tools.recurrence_research import prepare as module

    monkeypatch.chdir(tmp_path)
    session = tmp_path / module.SOURCE
    (session / 'sources').mkdir(parents=True)
    (session / 'session.sqlite3').touch()
    (session / 'manifest.json').write_text('{}')
    ids = [f'{module.SESSION}-{n}' for n in (188, 208, 210)]
    for sid in ids + [f'{module.SESSION}-999']:
        (session / 'sources' / f'{sid}.png').write_bytes(sid.encode())
    steps = [{'seq': n, 'frame': sid} for n, sid in enumerate(ids + [f'{module.SESSION}-999'], 5)]
    metadata = {sid: {'sha256': hashlib.sha256(sid.encode()).hexdigest()} for sid in ids}
    monkeypatch.setattr(module, '_steps', lambda *_: ({'actor': steps}, metadata))
    out = tmp_path / '.runtime' / 'result'
    module.prepare(tmp_path, out, SPEC)
    packet = json.loads((out / 'packet.json').read_text())
    assert [row['frame'] for row in packet['steps']] == ids
    assert sorted(p.name for p in (out / 'frames').iterdir()) == sorted(f'{sid}.png' for sid in ids)
    assert 'subset' in packet['exposure']


def test_study_archive_hash_does_not_merge_distinct_saved_payloads(tmp_path):
    for name, payload in [('one', 'a'), ('copy', 'a'), ('later', 'b')]:
        directory = tmp_path / '.runtime/starts' / name
        directory.mkdir(parents=True)
        (directory/'manifest.json').write_text(json.dumps(dict(schema='start-manifest/2', lineage=397,
            source_study='397-seven-day', source_manifest_sha256='same archive', files={'opaque-payload': payload})))
    rows = {Path(row['path']).parent.name: row for row in portfolio(tmp_path)['sources']}
    assert rows['one']['copy_group'] == rows['copy']['copy_group'] != rows['later']['copy_group']
    assert len({row['world_group'] for row in rows.values()}) == 1
    assert all(row['parent_moment'].startswith('unknown') for row in rows.values())
    campaign = tmp_path / '.runtime/evidence/397-seven-day/computer-sessions/admission'
    campaign.mkdir(parents=True)
    (campaign/'manifest.json').write_text(json.dumps(dict(schema='campaign-run/8', files={'route.json': 'a'})))
    row = next(row for row in portfolio(tmp_path)['sources'] if row['kind'] == 'campaign-run/8')
    assert row['copy_group'].startswith('unknown')


def test_full_proposed_role_bill_includes_acquisition_and_ending():
    spec = json.loads(SPEC.read_text())['worksheet']
    result = worksheet(spec)
    replay, pilot = result['stages']
    assert replay['model_bound_usd'] == '14.19264'
    assert Decimal(pilot['model_bound_usd']) == Decimal('77.59872')
    assert Decimal(result['combined_known_model_bound_usd']) == Decimal('91.79136')
    assert pilot['allocations'][0]['requests_max'] == 3 * (24 + 4 + 2)
    assert 'unknown' in result['unpriced_components'][0]
