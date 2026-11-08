"""Payload builders for the spectator's frame: `spectator-frame/1` (ADR 009 D18; docs/contracts/evaluation.md).

The frame is a health strip, the container inventory and the four #397 forgetting episodes over sealed traces. Every
builder is a pure read: sidecar container indexes (`data/containers/*.json`), tracked probe episodes
(`data/evaluation/probes/*/episodes.json`) and the catalog's evaluation stores. Nothing here writes, and nothing it
computes reaches the player or the curator (ADR008). Slots that need a later phase's data say so
(`not-yet-measured` with the phase that delivers them) instead of showing a number.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from harness.evaluation.core.probes import ProbeError, episodes as validate_episodes
from harness.trace.sidecar import INDEX_SCHEMA, ManifestError, validate

from .catalog import Catalog, RunInfo, ViewError
from . import views

API = 'spectator-frame/1'
DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'


@dataclass(frozen=True)
class FrameSources:
    """Where the frame reads its tracked data from; tests point both at synthetic directories."""
    containers: Path = DATA_ROOT / 'containers'
    probes: Path = DATA_ROOT / 'evaluation' / 'probes'


# The health strip's slots (D18) and the phase that first delivers each. `actor_cadence` is measured from sealed
# actor sessions already; the rest need a curator, gate, snapshots or programs that exist only from P1 or P2.
NOT_YET = (
    ('curator_lag', 'Curator lag', 'P1'),
    ('gate_pass_rate', 'Gate pass rate', 'P1'),
    ('snapshot_freshness', 'Snapshot freshness', 'P1'),
    ('program_delegation_share', 'Program delegation share', 'P2'),
    ('monitor_alerts', 'Monitor alerts', 'P2'),
    ('spend_against_cap', 'Spend against cap', 'P1'),
)


def read_json(path: Path, what: str):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ViewError(500, 'bad_data_file', f'{what}: {exc}') from exc


# Containers ---------------------------------------------------------------------------------------

def container_manifests(sources: FrameSources) -> list[dict]:
    """Every manifest from every `container-index/1` file, each validated. An invalid index or manifest, or a repeated
    ID, refuses the whole listing: the inventory never shows a container that does not follow the manifest shape."""
    found: list[dict] = []
    seen: set[str] = set()
    paths = sorted(sources.containers.glob('*.json')) if sources.containers.is_dir() else []
    for path in paths:
        index = read_json(path, path.name)
        if not isinstance(index, dict) or index.get('schema') != INDEX_SCHEMA or not isinstance(index.get('containers'), list):
            raise ViewError(500, 'bad_data_file', f'{path.name}: expected {INDEX_SCHEMA}')
        for manifest in index['containers']:
            try:
                validate(manifest)
            except (ManifestError, KeyError, TypeError, AttributeError) as exc:
                name = manifest.get('id') if isinstance(manifest, dict) else None
                raise ViewError(500, 'invalid_container', f'{path.name}: {name}: {exc}') from exc
            if manifest['id'] in seen:
                raise ViewError(500, 'invalid_container', f'{path.name}: {manifest["id"]}: repeated container id')
            seen.add(manifest['id'])
            found.append(dict(manifest, _study=index.get('study')))
    return found


def container_row(manifest: dict) -> dict:
    return dict(id=manifest['id'], kind=manifest['kind'], owner_role=manifest['owner_role'],
        lifecycle_state=manifest['lifecycle']['state'], retention_policy=manifest['retention'].get('policy'),
        evidence_study=manifest['provenance'].get('evidence_study'), index_study=manifest['_study'])


def containers(sources: FrameSources, after: int, limit: int) -> dict:
    rows = [container_row(m) for m in container_manifests(sources)]
    kinds: dict[str, int] = {}
    for row in rows:
        kinds[row['kind']] = kinds.get(row['kind'], 0) + 1
    window = rows[after:after + limit + 1]
    more = len(window) > limit
    return dict(items=window[:limit], next=after + limit if more else None, limit=limit, total=len(rows), kinds=kinds)


def container(sources: FrameSources, container_id: str) -> dict:
    for manifest in container_manifests(sources):
        if manifest['id'] == container_id:
            study = manifest.pop('_study')
            return dict(container=manifest, index_study=study)
    raise ViewError(404, 'unknown_container', container_id)


def container_runs(catalog: Catalog, manifests: list[dict]) -> list[tuple[dict, RunInfo]]:
    """The catalog's runs that belong to a container: an actor session whose ID a manifest records."""
    by_session = {m['inputs'].get('session_id'): m for m in manifests if isinstance(m['inputs'], dict)}
    return [(by_session[info.session], info) for info in catalog.runs() if info.session in by_session]


# Health strip -------------------------------------------------------------------------------------

def actor_cadence(catalog: Catalog, runs: list[tuple[dict, RunInfo]]) -> dict:
    slot = dict(id='actor_cadence', label='Actor cadence')
    measured = [(manifest, info) for manifest, info in runs if info.survival is not None and info.survival.get('hours')]
    if not measured:
        return dict(slot, state='no-data', detail='no catalog run belongs to a container index, or none has a game-time reading')
    steps = 0
    for _, info in measured:
        connection = catalog.connect(info)
        try:
            steps += connection.execute('SELECT COUNT(*) FROM steps').fetchone()[0]
        finally:
            connection.close()
    hours = sum(info.survival['hours'] for _, info in measured)
    decisions = sum(info.decisions for _, info in measured)
    return dict(slot, state='measured', source='derived', runs=len(measured), decisions=decisions, steps=steps,
        game_hours=hours, decisions_per_game_hour=decisions / hours if hours else None,
        steps_per_game_hour=steps / hours if hours else None, dollars=sum(info.dollars for _, info in measured))


def health(catalog: Catalog, sources: FrameSources) -> dict:
    manifests = container_manifests(sources)
    runs = container_runs(catalog, manifests)
    slots = [actor_cadence(catalog, runs)]
    slots += [dict(id=slot_id, label=label, state='not-yet-measured', phase=phase) for slot_id, label, phase in NOT_YET]
    return dict(slots=slots, containers=len(manifests), runs=len(runs))


# Episodes -----------------------------------------------------------------------------------------

def resolve(catalog: Catalog, manifests: list[dict], anchor: dict | None) -> dict | None:
    """An episode anchor `{chunk, frame}` as `{run, actor, source_id, available}`.

    `chunk` is `<run>-<actor directory>`; `frame` is a source ID `<session>-<n>`. The run is the catalog run of the
    frame's session (else the chunk's run name). `available` is whether the existing per-run frame route would
    serve the frame now (record present, file present, SHA-256 matching); `reason` names why not."""
    if anchor is None:
        return None
    run_name, _, actor = anchor['chunk'].rpartition('-')
    source_id = anchor.get('frame')
    session = source_id.rpartition('-')[0] if source_id else None
    runs = catalog.runs()
    info = next((r for r in runs if session and r.session == session), None) or next((r for r in runs if r.run == run_name), None)
    # The container's actor entry names the actor id when the sidecar describes this session.
    owner = info.session if info else session
    described = next((m for m in manifests if owner and m['inputs'].get('session_id') == owner), None)
    actor_id = next((a.get('actor_id') for a in (described['inputs'].get('actors') or []) if a.get('directory') == actor), None) if described else None
    out = dict(chunk=anchor['chunk'], run=info.run if info else None, actor=actor, actor_id=actor_id,
        container=described['id'] if described else None, source_id=source_id, available=False, reason=None)
    if anchor.get('text'):
        out['text'] = anchor['text']
    if source_id is None:
        out['reason'] = 'no_frame'
    elif info is None:
        out['reason'] = 'run_not_in_catalog'
    else:
        connection = catalog.connect(info)
        try:
            views.frame(catalog, info, connection, source_id)
            out['available'] = True
        except ViewError as error:
            out['reason'] = error.code
        finally:
            connection.close()
    return out


def episodes(catalog: Catalog, sources: FrameSources) -> dict:
    manifests = container_manifests(sources)
    lineages = []
    paths = sorted(sources.probes.glob('*/episodes.json')) if sources.probes.is_dir() else []
    for path in paths:
        document = read_json(path, f'{path.parent.name}/{path.name}')
        try:
            found = validate_episodes(document)
        except ProbeError as exc:
            raise ViewError(500, 'bad_data_file', f'{path.parent.name}/{path.name}: {exc}') from exc
        items = []
        for episode in found:
            items.append(dict(id=episode['id'], title=episode['title'], fact=episode.get('fact'), lost_at=episode['lost_at'],
                probe=episode['probe'], observed=resolve(catalog, manifests, episode['observed']),
                needed=resolve(catalog, manifests, episode['needed']),
                acted_without=resolve(catalog, manifests, episode['acted_without'])))
        lineages.append(dict(lineage=document.get('lineage'), study=document.get('study'), note=document.get('note'),
            source=document.get('source'), episodes=items))
    return dict(lineages=lineages)
