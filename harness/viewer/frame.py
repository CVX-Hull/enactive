"""Read-only inventory and probe episodes for the spectator archive."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from harness.evaluation.core.probes import ProbeError, episodes as validate_episodes
from harness.trace.sidecar import INDEX_SCHEMA, ManifestError, validate

from .catalog import Catalog, RunInfo, ViewError
from . import views
from .curator import read_rooted

DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'


@dataclass(frozen=True)
class FrameSources:
    """Where the frame reads its tracked data from; tests point both at synthetic directories."""
    containers: Path = DATA_ROOT / 'containers'
    probes: Path = DATA_ROOT / 'evaluation' / 'probes'
    curator_results: tuple[tuple[str, Path], ...] = ()
    curator_sessions: tuple[tuple[str, Path], ...] = ()
    curator_runner_status: Path | None = None  # the curator runner's status.json, read at each request
    curator_grooming: Path | None = None  # one boundary grooming receipt, shown only for the run it names
    curator_drafts: tuple[tuple[str, Path], ...] = ()


def read_json(root: Path, *parts: str):
    what = "/".join(parts)
    try:
        state, _, data = read_rooted(root, *parts)
        if state != 'available':
            raise ViewError(500, 'bad_data_file', f'{what}: {state}')
        return json.loads(data)
    except (ValueError, RecursionError) as exc:
        raise ViewError(500, 'bad_data_file', f'{what}: malformed JSON') from exc


# Containers ---------------------------------------------------------------------------------------

def container_manifests(sources: FrameSources) -> list[dict]:
    """Every manifest from every `container-index/1` file, each validated. An invalid index or manifest, or a repeated
    ID, refuses the whole listing: the inventory never shows a container that does not follow the manifest shape."""
    found: list[dict] = []
    seen: set[str] = set()
    paths = sorted(sources.containers.glob('*.json')) if sources.containers.is_dir() else []
    for path in paths:
        index = read_json(sources.containers, path.name)
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


# Episodes -----------------------------------------------------------------------------------------

def resolve(catalog: Catalog, runs: list[RunInfo], manifests: list[dict], anchor: dict | None) -> dict | None:
    """An episode anchor `{chunk, frame}` as `{run, actor, source_id, available}`.

    `chunk` is `<run>-<actor directory>`; `frame` is a source ID `<session>-<n>`. The run is the catalog run of the
    frame's session; only an anchor without a frame falls back to the chunk's run name. `available` is whether the
    existing per-run frame route, which finds a run by name, would serve the frame now (the name resolves to this
    session, the record is present, the file is present and its SHA-256 matches); `reason` names why not."""
    if anchor is None:
        return None
    run_name, _, actor = anchor['chunk'].rpartition('-')
    source_id = anchor.get('frame')
    session = source_id.rpartition('-')[0] if source_id else None
    if source_id is not None:
        info = next((r for r in runs if r.session == session), None)
    else:
        info = next((r for r in runs if r.run == run_name), None)
    # The container's actor entry names the actor id when the sidecar describes this session.
    owner = info.session if info else session
    described = next((m for m in manifests if owner and m['inputs'].get('session_id') == owner), None)
    entries = described['inputs'].get('actors') if described else None
    actor_id = next((a.get('actor_id') for a in entries if isinstance(a, dict) and a.get('directory') == actor), None) \
        if isinstance(entries, list) else None
    out = dict(chunk=anchor['chunk'], run=info.run if info else None, actor=actor, actor_id=actor_id,
        container=described['id'] if described else None, source_id=source_id, available=False, reason=None)
    if anchor.get('text'):
        out['text'] = anchor['text']
    if source_id is None:
        out['reason'] = 'no_frame'
    else:
        location = source_location(catalog, runs, info, source_id)
        out.update(available=location['available'], reason=location['reason'])
    return out


def source_location(catalog: Catalog, runs: list[RunInfo], info: RunInfo | None, source_id: str,
                    connection=None) -> dict:
    out = dict(run=info.run if info else None, session=info.session if info else None, seq=None,
               source_id=source_id, available=False, reason=None)
    if info is None:
        out['reason'] = 'run_not_in_catalog'
    elif next((r for r in runs if r.run == info.run), info).session != info.session:
        out['reason'] = 'ambiguous_run'  # the route's run name would select another session's run
    else:
        try:
            own = connection if connection is not None else catalog.connect(info)
            try:
                row = own.execute('SELECT seq FROM steps WHERE source_id=? ORDER BY seq LIMIT 1', (source_id,)).fetchone()
                out['seq'] = None if row is None else row[0]
                out['reason'] = views.frame_available(catalog, info, own, source_id)
                out['available'] = out['reason'] is None
            finally:
                if connection is None:
                    own.close()
        except ViewError as error:
            out['reason'] = error.code
    return out


def episodes(catalog: Catalog, sources: FrameSources) -> dict:
    manifests = container_manifests(sources)
    runs = catalog.runs()
    lineages = []
    paths = sorted(sources.probes.glob('*/episodes.json')) if sources.probes.is_dir() else []
    for path in paths:
        document = read_json(sources.probes, path.parent.name, path.name)
        try:
            found = validate_episodes(document)
        except ProbeError as exc:
            raise ViewError(500, 'bad_data_file', f'{path.parent.name}/{path.name}: {exc}') from exc
        items = []
        for episode in found:
            items.append(dict(id=episode['id'], title=episode['title'], fact=episode.get('fact'), lost_at=episode['lost_at'],
                probe=episode['probe'], observed=resolve(catalog, runs, manifests, episode['observed']),
                needed=resolve(catalog, runs, manifests, episode['needed']),
                acted_without=resolve(catalog, runs, manifests, episode['acted_without'])))
        lineages.append(dict(lineage=document.get('lineage'), study=document.get('study'), note=document.get('note'),
            source=document.get('source'), episodes=items))
    return dict(lineages=lineages)
