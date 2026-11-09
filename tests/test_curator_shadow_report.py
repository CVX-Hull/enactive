"""The #454 shadow report derives lag, spend share and gate pass rate from summaries and the run ledger."""
from __future__ import annotations

import json

import pytest

from tools.curator_host import shadow_report as report


def summary(session, cost, wall, accepted=1, submissions=1, state='sealed'):
    return dict(arm='terra', model='m', lineage='397', trace_session=session, session_state=state, run_state='completed',
                cost_usd=str(cost), requests=10, wall_seconds=wall, time_to_first_request_seconds=0.1,
                first_request_prompt_tokens=2000, submissions=submissions, accepted=accepted, rejected=submissions - accepted,
                drafts=dict(created=['d']), stopped_by_cap=False, tokens={}, proxy=dict(refusals=0, breaches=0, revoked=False),
                host_end=dict(reason='finished'))


ACTOR = dict(decisions=200, metrics={'pace.routine_seconds_per_decision': 5.0, 'survival.game_hours': dict(hours=10.0),
                                     'host.dollars_per_decision': dict(value=0.02)})


def test_lag_and_spend_follow_the_actor_figures():
    row = report.session_row(summary('sd1a2', '2.0', 100.0), ACTOR)
    assert row['lag_decisions'] == 20.0                        # 100 s at 5 s per decision
    assert row['lag_game_hours'] == pytest.approx(1.0)          # 20 decisions at 10 h / 200 decisions
    assert row['actor']['dollars'] == 4.0 and row['spend_share_of_actor'] == 0.5
    assert row['curator_dollars_per_game_hour'] == 0.2
    assert 'lag_decisions' not in report.session_row(summary('x', '1', 1.0), None)


def test_the_report_aggregates_runs_and_the_gate_pass_rate(tmp_path, monkeypatch):
    run = tmp_path / 'run-a'
    for name, cost, accepted in (('sd1a1', '1.5', 1), ('sd1a2', '2.5', 0)):
        (run / '397' / name).mkdir(parents=True)
        (run / '397' / name / 'summary.json').write_text(json.dumps(summary(name, cost, 50.0, accepted=accepted)))
    (run / 'summary.json').write_text(json.dumps(dict(
        arm='terra', lineage='397', cap_usd='5', total_cost_usd='4.0', stopped=None, complete=True, effort='medium',
        host={}, sessions_planned=['sd1a1', 'sd1a2'],
        sessions=[dict(summary='397/sd1a1/summary.json'), dict(summary='397/sd1a2/summary.json')])))
    monkeypatch.setattr(report, '_actor', lambda: {'sd1a1': ACTOR, 'sd1a2': ACTOR})
    out = tmp_path / 'report.json'
    assert report.main(['--runs', str(run), '--out', str(out)]) == 0
    data = json.loads(out.read_text())
    assert data['schema'] == 'curator-shadow-report/1' and len(data['sessions']) == 2
    terra = data['arms']['terra']
    assert terra['cost_usd'] == 4.0 and terra['submissions'] == 2 and terra['accepted'] == 1 and terra['gate_pass_rate'] == 0.5
    assert terra['game_hours'] == 20.0 and terra['spend_share_of_actor'] == 0.5 and terra['median_lag_decisions'] == 10.0
