"""The `run_facts` table: what the run was configured to do (docs/contracts/evaluation-record.md).

From the campaign manifest and the first host-start event. Operator labels come from the manifest. The caller
may supply labels for a campaign-run/4 archive without them. Only campaign-run/12 supplies the world.
The spend allowance comes from `spend_limit_usd` or, for archives predating that field, the ceiling minus
what earlier admissions had reserved.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from .sources import MANIFEST_SCHEMA, HostEvent

LABEL_KEYS = ('arm', 'start', 'scenario', 'lineage', 'admission', 'world')


def _usd(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def run_facts(manifest: dict, host: Mapping[str, Sequence[HostEvent]], actors: Sequence[str],
              fallback_labels: Mapping[str, object] | None = None) -> dict:
    manifest_labels = manifest.get('labels')
    raw_labels = manifest_labels if isinstance(manifest_labels, dict) else fallback_labels or {}
    labels = {key: raw_labels.get(key) for key in LABEL_KEYS}
    labels['world'] = manifest_labels.get('world') if (
        manifest.get('schema') == MANIFEST_SCHEMA and isinstance(manifest_labels, dict)) else None
    files = manifest.get('files') if isinstance(manifest.get('files'), dict) else {}
    start = host[actors[0]][0].fields if actors and host.get(actors[0]) else {}
    accounting = manifest.get('accounting') if isinstance(manifest.get('accounting'), dict) else {}
    ceiling, prior = _usd(accounting.get('ceiling_usd')), _usd(accounting.get('prior_reserved_usd'))
    allowance = _usd(manifest['spend_limit_usd']) if 'spend_limit_usd' in manifest else (
        None if ceiling is None or prior is None else ceiling - prior)
    return dict(
        labels=labels,
        manifest_schema=manifest.get('schema'),
        source_commit=manifest.get('source_commit'),
        model=start.get('model'), provider=start.get('provider'), effort=manifest.get('effort', start.get('effort')),
        route=start.get('provider_routing'),
        guide_sha256=files.get('context.txt'), assignment_sha256=files.get('prompt.txt'),
        limits=manifest.get('limits'), ending_reserve=manifest.get('ending_reserve'),
        wall_seconds=manifest.get('wall_seconds'), host_seconds=manifest.get('host_seconds'),
        max_hosts=manifest.get('max_hosts'),
        **({'max_http_attempts': manifest['max_http_attempts']}
           if manifest.get('schema') != MANIFEST_SCHEMA and 'max_http_attempts' in manifest else {}),
        declared_ceiling_usd=None if ceiling is None else float(ceiling),
        prior_reserved_usd=None if prior is None else float(prior),
        spend_allowance_usd=None if allowance is None else float(allowance))
