"""Derive #454's shadow measurements from run summaries and the tracked run ledger.

    python -m tools.curator_host.shadow_report --runs <run dir> [<run dir> ...] --out data/curator/shadow-454.json

Each run directory is a `tools.curator_host.shadow` output (`summary.json` per run, one per session). For every
session it reports cost, requests, wall time, cold start, submissions and gate verdicts, and puts
them beside the actor's own figures for the same admission or run from
`data/evaluation/run-metrics.jsonl`:
- **lag in decisions**: the session's wall time divided by the actor's routine seconds per decision;
- **lag in game time**: that many decisions at the admission's game hours per decision;
- **spend**: the curator's dollars against the actor's (decisions × dollars per decision) and per
  game hour.

It judges nothing; it only counts. Session summaries hold no key or token.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'curator-shadow-report/1'


def _actor() -> dict[str, dict]:
    rows = [json.loads(line) for line in (ROOT/'data'/'evaluation'/'run-metrics.jsonl').read_text().splitlines() if line.strip()]
    return {row['run']: row for row in rows}


def session_row(summary: dict, actor: dict | None) -> dict:
    cost = Decimal(summary['cost_usd'])
    row = dict(arm=summary['arm'], model=summary['model'], lineage=summary['lineage'], session=summary['trace_session'],
               state=summary.get('session_state', summary['run_state']), cost_usd=float(cost),
               requests=summary.get('requests'), wall_seconds=summary['wall_seconds'],
               time_to_first_request_seconds=summary.get('time_to_first_request_seconds'),
               first_request_prompt_tokens=summary.get('first_request_prompt_tokens'),
               submissions=summary.get('submissions', 0), accepted=summary.get('accepted', 0),
               rejected=summary.get('rejected', 0), drafts_created=len((summary.get('drafts') or {}).get('created', [])),
               stopped_by_cap=summary['stopped_by_cap'], tokens=summary.get('tokens'),
               proxy=dict(refusals=summary['proxy'].get('refusals'), breaches=summary['proxy'].get('breaches'),
                          revoked=summary['proxy'].get('revoked')),
               host_end=(summary.get('host_end') or {}).get('reason'))
    if actor is not None:
        metrics = actor['metrics']
        decisions = actor['decisions']
        seconds_per_decision = metrics['pace.routine_seconds_per_decision']
        hours = metrics['survival.game_hours']['hours']
        dollars = decisions * metrics['host.dollars_per_decision']['value']
        lag = summary['wall_seconds'] / seconds_per_decision if seconds_per_decision else None
        row['actor'] = dict(decisions=decisions, game_hours=hours, routine_seconds_per_decision=seconds_per_decision,
                            dollars=round(dollars, 4))
        row['lag_decisions'] = None if lag is None else round(lag, 1)
        row['lag_game_hours'] = None if lag is None or not decisions else round(lag * hours / decisions, 3)
        row['spend_share_of_actor'] = round(float(cost) / dollars, 3) if dollars else None
        row['curator_dollars_per_game_hour'] = round(float(cost) / hours, 4) if hours else None
    return row


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def arm_summary(rows: list[dict]) -> dict:
    submitted = sum(r['submissions'] for r in rows)
    accepted = sum(r['accepted'] for r in rows)
    hours = sum(r['actor']['game_hours'] for r in rows if 'actor' in r)
    actor_dollars = sum(r['actor']['dollars'] for r in rows if 'actor' in r)
    cost = sum(r['cost_usd'] for r in rows)
    return dict(sessions=len(rows), sealed=sum(r['state'] == 'sealed' for r in rows), cost_usd=round(cost, 4),
                game_hours=round(hours, 3), curator_dollars_per_game_hour=round(cost / hours, 4) if hours else None,
                spend_share_of_actor=round(cost / actor_dollars, 3) if actor_dollars else None,
                submissions=submitted, accepted=accepted, gate_pass_rate=round(accepted / submitted, 3) if submitted else None,
                median_wall_seconds=_median([r['wall_seconds'] for r in rows]),
                median_lag_decisions=_median([r.get('lag_decisions') for r in rows]),
                median_lag_game_hours=_median([r.get('lag_game_hours') for r in rows]),
                median_time_to_first_request_seconds=_median([r['time_to_first_request_seconds'] for r in rows]),
                median_first_request_prompt_tokens=_median([r['first_request_prompt_tokens'] for r in rows]),
                stopped_by_cap=sum(bool(r['stopped_by_cap']) for r in rows),
                proxy_breaches=sum(r['proxy']['breaches'] or 0 for r in rows),
                proxy_refusals=sum(r['proxy']['refusals'] or 0 for r in rows))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runs', nargs='+', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    actor = _actor()
    runs, rows = [], []
    for directory in args.runs:
        run = json.loads((directory/'summary.json').read_text())
        runs.append(dict(name=directory.name, arm=run['arm'], lineage=run['lineage'], cap_usd=run['cap_usd'],
                         total_cost_usd=run['total_cost_usd'], stopped=run['stopped'], complete=run['complete'],
                         sessions_planned=run['sessions_planned'], effort=run['effort'], host=run['host']))
        for entry in run['sessions']:
            summary = json.loads((directory/entry['summary']).read_text())
            rows.append(dict(session_row(summary, actor.get(summary['trace_session'])), run=directory.name))
    arms = {arm: arm_summary([r for r in rows if r['arm'] == arm]) for arm in sorted({r['arm'] for r in rows})}
    report = dict(schema=SCHEMA, runs=runs, arms=arms, sessions=rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + '\n')
    for arm, figures in arms.items():
        print(arm, json.dumps(figures))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
