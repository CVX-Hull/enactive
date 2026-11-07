"""The `run_facts` table: what the run was configured to do (docs/contracts/evaluation.md).

From `manifest.json` (campaign-run/4 or /5) and the first host-start event. Operator labels come from a
campaign-run/5 manifest; an archived campaign-run/4 run has none, so the caller may supply them.
The declared spend allowance is the manifest's ceiling minus what earlier admissions had reserved.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from .sources import HostEvent

LABEL_KEYS = ('arm', 'start', 'scenario', 'lineage', 'admission')


def _usd(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def run_facts(manifest: dict, host: Mapping[str, Sequence[HostEvent]], actors: Sequence[str],
              fallback_labels: Mapping[str, object] | None = None) -> dict:
    labels = manifest.get('labels') if isinstance(manifest.get('labels'), dict) else dict(fallback_labels or {})
    files = manifest.get('files') if isinstance(manifest.get('files'), dict) else {}
    start = host[actors[0]][0].fields if actors and host.get(actors[0]) else {}
    accounting = manifest.get('accounting') if isinstance(manifest.get('accounting'), dict) else {}
    ceiling, prior = _usd(accounting.get('ceiling_usd')), _usd(accounting.get('prior_reserved_usd'))
    return dict(
        labels={key: labels.get(key) for key in LABEL_KEYS},
        manifest_schema=manifest.get('schema'),
        source_commit=manifest.get('source_commit'),
        model=start.get('model'), provider=start.get('provider'), effort=manifest.get('effort', start.get('effort')),
        route=start.get('provider_routing'),
        guide_sha256=files.get('context.txt'), assignment_sha256=files.get('prompt.txt'),
        limits=manifest.get('limits'), ending_reserve=manifest.get('ending_reserve'),
        wall_seconds=manifest.get('wall_seconds'), host_seconds=manifest.get('host_seconds'),
        max_hosts=manifest.get('max_hosts'), max_http_attempts=manifest.get('max_http_attempts'),
        declared_ceiling_usd=None if ceiling is None else float(ceiling),
        prior_reserved_usd=None if prior is None else float(prior),
        spend_allowance_usd=None if ceiling is None or prior is None else float(ceiling - prior))
