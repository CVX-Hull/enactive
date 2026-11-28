"""Synthetic `spectator-view/4` projections for the page tests, built around the captured steps and requests.

The captured fixture run predates the trace fields these routes show, so nothing here is a real response: intents, costs,
endpoints, cuts, coverage waits, knowledge deliveries, the player's agenda, its source reads, the handoff and every
curator figure are invented, and shaped like the viewer's contract (harness/viewer/feed.py, telemetry.py, delivered.py,
curator_ops.py and curator_runner.py). Standard library only.

The live run's story, by step:
  2 opening briefing v1 · 20 agenda set · 30 source re-read (player saw it as s01) · 40 cut, post-cut briefing v1
  50 agenda status · 60 live delta v2 · 65/66 knowledge query and read · 75 handoff 001 → 002
  78-80 coverage wait, closed by the uncovered rescue cut at 80 (#1037) with briefing v2 · 90 agenda upsert
  110 v3 adopted (empty-suppressed) · 120 cut, no briefing · 130 agenda cleared · 140 v4 refused · 160 cut, briefing v2
  170 live delta v6 after v5 (v5 superseded) · 200 cut, briefing v6 · 215 v7 undelivered · 225 coverage wait, still open
  v8 is published by the curator and never exported.
"""
from __future__ import annotations

import json
from pathlib import Path

API = 'spectator-view/4'
HERE = Path(__file__).parent
ACTOR = '79e9a7e05352477e8820bc94874b23de'       # actor 001
ACTOR2 = '4a3a47da83ed45d08f527576f8cc40f4'      # actor 002, after the handoff
HANDOFF = 75
HOSTILE = '<img src=x onerror=window.storyExecuted=true>'
CUTS = {40: 'target', 80: 'rescue', 120: 'target', 160: 'target', 200: 'best_effort'}
UNCOVERED = {80: 6}
ERROR_STEP, SOURCE_STEP = 12, 30
#: The captured run's source ID at each step, and another admission of the lineage whose frame a fact cites.
SOURCES = {row['seq']: row['source_id'] for row in json.loads((HERE / 'steps.json').read_text())['items']}
RUNS = {row['run']: row for row in json.loads((HERE / 'runs.json').read_text())['items']}
ANCESTOR = RUNS['ceil08']
ANCESTOR_SOURCE = f"{ANCESTOR['session']}-12"
ELSEWHERE = 'b' * 32 + '-7'


def actor_at(seq: int) -> str:
    return ACTOR if seq <= HANDOFF else ACTOR2


def cost(seq: int) -> str:
    return '0.2500' if seq == 100 else f'{0.0125 + (seq % 7) * 0.001:.4f}'


def spent(steps: list[dict]) -> str:
    return f"{sum(float(cost(s['seq'])) for s in steps):.4f}"


def tier(seq: int) -> str:
    return 'flex' if seq % 10 == 0 else 'default'


def placed(step: dict, exact: bool) -> dict:
    return dict(seq=step['seq'], exact_step=exact, decision=step['seq'] if exact else None, step_decision=step['decision'], wall=step['wall'],
        source_id=step['source_id'], mode=step['mode'], game_time=step['game_time'])


# The feed ---------------------------------------------------------------------------------------------------------

def step_entry(step: dict, recorded: bool) -> dict:
    seq = step['seq']
    prompt = 6000 + (seq % 40) * 1200
    out = dict(id=seq * 100, order=seq * 100, entry_kind='step', **placed(step, True), tool='computer_input' if step['keys'] else 'computer_observe',
        intent=None, intent_source=None, intent_omitted_characters=0, keys=step['keys'], status='ok', latency_ms=400.0 + seq,
        request_id=f'request-{seq}', tool_call_id=f'call-{seq}', operation_id=f'{seq:032x}', actor=actor_at(seq), reported_provider=None,
        applied_service_tier=None, source_read=None, reported_cost_usd=None, prompt_tokens=prompt, input_tokens=3, cache_read=prompt - 500,
        cache_write=497, output_tokens=41, arguments_preview=None, arguments_omitted_characters=0, result=None)
    if recorded:
        return out
    intent = f'Step {seq}: look around before moving on.'
    if seq == 226:
        intent = f'Read the sign {HOSTILE} on the wall.'
    out.update(intent=intent, intent_source='player_claim', reported_provider='endpoint-a' if seq % 50 else 'endpoint-b', applied_service_tier=tier(seq),
        reported_cost_usd=cost(seq), arguments_preview='{"actions":[{"type":"key","key":"ENTER","modifiers":[]}],"source_id":"source-1"}',
        result=dict(status='completed', reason='Operation completed; application effect is not certified', source_id=step['source_id'],
            receipts=[dict(disposition='delivered', reason='Delivered in order', emitted_events=2)], receipts_omitted=0, result_bytes=132))
    if seq == ERROR_STEP:
        out.update(status='error')
    return out


def tool_entry(step: dict, offset: int, tool: str, intent: str, **extra) -> dict:
    """A call that made no step of its own: it sits behind the step on screen."""
    out = dict(step_entry(step, False), id=step['seq'] * 100 + offset, order=step['seq'] * 100 + offset, exact_step=False, decision=None,
        tool=tool, keys=[], operation_id=None, intent=intent, tool_call_id=f'{tool}-{step["seq"]}', arguments_preview=json.dumps(extra.pop('arguments', {})))
    out.update(extra)
    return out


def milestone(step: dict, offset: int, entry_kind: str, **extra) -> dict:
    place = step['seq'] * 100 - offset
    return dict(id=place, order=place, entry_kind=entry_kind, **placed(step, False), actor=actor_at(step['seq']), **extra)


def cut_fields(seq: int, version: str | None, briefing: dict | None) -> dict:
    return dict(request_id=f'request-{seq}', outcome='applied', reason=None, knowledge_version=version, covered_through_operation_id=f'{seq - 3:032x}',
        available_turns=24, min_free=8000, triggers=['high_mark'], cut_result=CUTS[seq], tokens_before=61400, tokens_after=24800, images_before=39,
        images_after=19, removed_turns=20, uncovered_turns=UNCOVERED.get(seq, 0), cumulative_removed_turns=20 * (list(CUTS).index(seq) + 1),
        briefing_tokens=briefing['briefing_tokens'] if briefing else None, source_ids_count=briefing['source_ids_count'] if briefing else None)


DELTAS = {
    'v2': (dict(corrections=1, state_changes=2, flag_changes=0, added_facts=3, claim_updates=0, article_changes=1),
           [dict(bucket='corrections', id='fact-water', text='The stream is east of the wall, not west.'),
            dict(bucket='state_changes', id='fact-fire', state_key='fire-ring', text='A fire ring is lit.'),
            dict(bucket='state_changes', id='fact-old', state_key='shelter-state', text='The shelter is contested.'),
            dict(bucket='added_facts', id='fact-fire', text='A lighter lights a fire ring.'),
            dict(bucket='article_changes', id='article-fire', title='Making fire')]),
    'v6': (dict(corrections=0, state_changes=2, flag_changes=1, added_facts=2, claim_updates=1, article_changes=0),
           [dict(bucket='state_changes', id='fact-water3', state_key='water-course', text='The stream is frozen over.'),
            dict(bucket='added_facts', id='fact-ancestor', text='An earlier admission cached food in the cellar.')]),
}


def delivery(step: dict, offset: int, kind: str, version: str, **extra) -> dict:
    counts, preview = DELTAS.get(version, (None, [])) if kind == 'update' else (None, [])
    summary = {'opening_briefing': '2 leads · 3 index entries', 'post_cut_briefing': '2 leads · 4 index entries',
               'empty_suppressed': 'No substantive changes', 'refused': 'Delivery refused', 'undelivered': 'Delivery did not reach the player'}.get(kind)
    if kind == 'update':
        summary = ' · '.join(f"{n} {key.replace('_', ' ')}" for key, n in counts.items() if n)
    outcome = {'empty_suppressed': 'empty-suppressed', 'refused': 'refused', 'undelivered': 'undelivered'}.get(kind, 'delivered')
    fields = dict(joined_cut_id=None, kind='briefing' if 'briefing' in kind else 'update', delivery_kind=kind,
        outcome=outcome, reason=None, request_id=f"request-{step['seq']}", receiving_player_request_id=f"request-{step['seq']}",
        knowledge_version=version, previous_version=None, covered_step=step['seq'] - 10, delta_counts=counts, delta_preview=preview,
        leads_count=2 if 'briefing' in kind else None, index_count=(3 if kind == 'opening_briefing' else 4) if 'briefing' in kind else None,
        overflow_omitted_count=0, summary=summary)
    fields.update(extra)
    return milestone(step, offset, 'knowledge_delivery', **fields)


def agenda(threads: list[tuple[str, str, str]], cuts: int) -> dict:
    rows = [dict(id=i, title=t, status=s, refs=[]) for i, t, s in threads]
    return dict(cut_count=cuts, thread_count=len(rows), active_count=sum(r['status'] in ('active', 'paused') for r in rows), threads=rows)


AGENDA = {20: ('upsert', agenda([('water', 'Find a water source', 'active'), ('shelter', 'Secure the shelter', 'active')], 0)),
          50: ('set_status', agenda([('water', 'Find a water source', 'done'), ('shelter', 'Secure the shelter', 'active')], 1)),
          90: ('upsert', agenda([('water', 'Find a water source', 'done'), ('shelter', 'Secure the shelter', 'active'), ('fire', 'Make a fire ring', 'active')], 2)),
          130: ('clear_completed', agenda([('shelter', 'Secure the shelter', 'paused'), ('fire', 'Make a fire ring', 'active')], 3))}
#: What the handoff at step 75 carried to the next actor: the agenda as it stood at step 50.
CARRIED = AGENDA[50][1]


def waits(steps: list[dict]) -> list[dict]:
    """Edge-computed spans: one closed by the cut at 80, and one still open at the end of the trace."""
    by = {s['seq']: s for s in steps}
    out = []
    last = steps[-1]
    for start, end, active in ((78, 80, False), (225, None, True)):
        if start not in by:
            continue
        first = by[start]
        ending = last if active else by.get(end, last)
        out.append(dict(id=f'wait:{0 if start < HANDOFF else 1}:{start * 10}', actor=actor_at(start), actor_index=0 if start <= HANDOFF else 1, line=start * 10,
            reason='uncovered', start_request_id=f'request-{start}', end_request_id=f"request-{ending['seq']}", start_wall=first['wall'],
            end_wall=ending['wall'], duration_seconds=round(ending['wall'] - first['wall'], 3), requests=ending['seq'] - start + (0 if active else 1),
            peak_tokens=63200, covered_through_operation_id=f'{start - 4:032x}', knowledge_version='v2' if start < 100 else 'v6',
            available_turns=18, min_free=8000, active=active, ended_by='trace_end' if active else 'cut', cut_request_id=None if active else f'request-{end}',
            restore_possible=active))
    return out


BRIEFINGS = {40: 'v1', 80: 'v2', 160: 'v2', 200: 'v6'}


def feed(steps: list[dict], findings: list[dict], recorded: bool) -> list[dict]:
    items = []
    by = {s['seq']: s for s in steps}
    for step in steps:
        seq = step['seq']
        items.append(step_entry(step, recorded))
        if recorded:
            continue
        if seq == 2:
            items.append(delivery(step, 40, 'opening_briefing', 'v1'))
        if seq in CUTS:
            version = BRIEFINGS.get(seq)
            briefing_entry = delivery(step, 40, 'post_cut_briefing', version) if version else None
            cut_id = seq * 100 - 50
            briefing = None
            if briefing_entry:
                briefing_entry['joined_cut_id'] = cut_id
                briefing = dict(delivery_id=briefing_entry['id'], knowledge_version=version, briefing_tokens=2400 + seq, source_ids_count=4,
                    leads_count=2, index_count=4, delta_counts=None, summary=briefing_entry['summary'])
                items.append(briefing_entry)
            items.append(milestone(step, 50, 'context_cut', briefing=briefing, **cut_fields(seq, version or 'v3', briefing)))
        if seq == 60:
            items.append(delivery(step, 40, 'update', 'v2', previous_version='v1'))
        if seq == 110:
            items.append(delivery(step, 40, 'empty_suppressed', 'v3', previous_version='v2'))
        if seq == 140:
            items.append(delivery(step, 40, 'refused', 'v4', previous_version='v3', reason='stale_base'))
        if seq == 170:
            items.append(delivery(step, 40, 'update', 'v6', previous_version='v5'))
        if seq == 215:
            items.append(delivery(step, 40, 'undelivered', 'v7', previous_version='v6', reason='host_restarted'))
        if seq in AGENDA:
            op, state = AGENDA[seq]
            items.append(milestone(step, 30, 'agenda_change', request_id=f'request-{seq}', tool_call_id=f'agenda-{seq}', op=op,
                cut_count=state['cut_count'], thread_count=state['thread_count'], active_count=state['active_count'], agenda=state))
            items.append(tool_entry(step, 12, 'player_agenda', 'Keep the plan current.', arguments=dict(op=op)))
        if seq == SOURCE_STEP:
            items.append(tool_entry(step, 10, 'player_source', 'Look at the earlier frame again.', arguments=dict(source_id='s01:12'),
                source_read=dict(source_id=ANCESTOR_SOURCE, player_alias='s01', non_clickable=True, origin='ancestor')))
        if seq == 65:
            items.append(tool_entry(step, 10, 'player_knowledge_query', 'Is there water nearby?', arguments=dict(query='water')))
        if seq == 66:
            items.append(tool_entry(step, 10, 'player_knowledge_read', 'Read the water fact.', arguments=dict(id_or_title='fact-water')))
    if not recorded:
        for wait in waits(steps):
            step = by[int(wait['start_request_id'].split('-')[1])]
            items.append(dict(wait, order=step['seq'] * 100 - 45, entry_kind='coverage_wait', **placed(step, False)))
    story = [f for f in findings if f['kind'] in ('stall', 'death', 'custody_stop', 'handoff', 'run_end')]
    for number, row in enumerate(story):
        step = by.get(row['seq_start'])
        if step is not None:
            items.append(dict(milestone(step, 0, 'finding', finding_id=row['id'], finding_kind=row['kind'], seq_end=row['seq_end'],
                source=row['source'], payload=row['payload'], payload_omitted=False), id=f"finding:{row['kind']}:{row['seq_start']}:{row['source']}:{row['id']}",
                order=step['seq'] * 100 + 20 + number % 70, decision=step['decision'], exact_step=True))
    return sorted(items, key=lambda item: item['order'])


def handoff_finding(steps: list[dict]) -> dict:
    step = next(s for s in steps if s['seq'] == HANDOFF)
    return dict(id=8001, seq_start=HANDOFF, seq_end=HANDOFF, kind='handoff', source='harness', confidence=None,
        payload=dict(actor=ACTOR, context_id='1b280ca82aa549ecb2b502319c7f030c'), decision=step['decision'], wall=step['wall'])


def terminal_findings(steps: list[dict]) -> list[dict]:
    """What a run's final pass adds: its end, and a finding placed long before it."""
    return [dict(id=9001, seq_start=5, seq_end=5, kind='custody_stop', source='recorded', payload=dict(reason='found by the final pass')),
        dict(id=9002, seq_start=steps[-1]['seq'], seq_end=steps[-1]['seq'], kind='run_end', source='recorded', payload=dict(reason='external stop'))]


KINDS = ('step', 'context_cut', 'coverage_wait', 'knowledge_delivery', 'agenda_change', 'finding')


def feed_page(items: list[dict], after: int, limit: int, recorded: bool) -> dict:
    rows = [i for i in items if i['order'] > after]
    return dict(schema=API, items=rows[:limit], next=rows[limit - 1]['order'] if len(rows) > limit else None, limit=limit,
        source='evaluation_record' if recorded else 'host_trace', total=len(items), counts={k: sum(i['entry_kind'] == k for i in items) for k in KINDS})


# Summary ----------------------------------------------------------------------------------------------------------

def host_telemetry(steps: list[dict]) -> dict:
    last = steps[-1]['seq']
    applied = [s for s in CUTS if s <= last]
    found = waits(steps)
    active = [w for w in found if w['active']]
    latest = applied[-1]
    delivered = [v for seq, v in ((2, 'v1'), (60, 'v2'), (170, 'v6')) if seq <= last]
    return dict(reported_cost_usd=spent(steps), spent_usd=spent(steps), player_requests=last, recall_requests=0, unpriced_requests=0,
        unpriced_recall_requests=0, spend_complete=False, response_by_endpoint={'endpoint-a': last - 4, 'endpoint-b': 4},
        latest_provider='endpoint-b',     # the last to answer is not the most frequent
        context_cuts=dict(applied=len(applied), held_back=2, latest=dict(cut_fields(latest, BRIEFINGS.get(latest), None), wall_time=steps[-1]['wall']),
            uncovered_cuts=sum(1 for s in applied if UNCOVERED.get(s)), uncovered_turns_total=sum(UNCOVERED.get(s, 0) for s in applied),
            by_result={r: sum(CUTS[s] == r for s in applied) for r in ('target', 'best_effort', 'rescue')}),
        spend_reserve_reached=dict(count=1, latest=dict(actor=ACTOR2, actor_id=ACTOR2, wall_time=steps[-1]['wall'],
            spent_usd='2.5', spend_limit_usd='5', finish_reserve_usd='2.5', unpriced_bound_usd='0.05')),
        tail_notices=dict(count=2, by_kind={'context-capacity': 1, 'host-timeout': 0, 'spend-limit': 1}),
        knowledge_updates=dict(count=2, latest_version=delivered[-1]),
        coverage_waits=dict(count=len(found), active_count=len(active), longest_seconds=max((w['duration_seconds'] for w in found), default=None),
            total_requests=sum(w['requests'] for w in found), peak_tokens=63200 if found else None, latest=found[-1] if found else None),
        knowledge_deliveries=dict(total=11, briefings=5, post_cut_briefings=4, updates=2, empty_suppressed=1, refused=1, undelivered=1, latest_version=delivered[-1]),
        service_tiers=dict(player={'default': sum(tier(s['seq']) == 'default' for s in steps), 'flex': sum(tier(s['seq']) == 'flex' for s in steps)},
            latest_player_tier=tier(last)),
        token_summary=dict(latest_prompt_tokens=34983, p50_prompt_tokens=32766, max_prompt_tokens=49902, cache_hit_share=0.9308))


def agenda_summary() -> dict:
    return dict(initial=None, latest=AGENDA[130][1], final=None, tool_calls=4, events_count=4, reconstructed=True)


CORE4_METRICS = [
    dict(name='knowledge.deliveries', key='', value=11, count=11, denominator=12.0, missing=None, source='recorded'),
    dict(name='knowledge.deliveries', key='delivered', value=8, count=8, denominator=12.0, missing=None, source='recorded'),
    dict(name='knowledge.deliveries', key='empty-suppressed', value=1, count=1, denominator=12.0, missing=None, source='recorded'),
    dict(name='knowledge.reads', key='', value=2, count=2, denominator=None, missing=None, source='recorded'),
    dict(name='context.uncovered_cuts', key='', value=1, count=1, denominator=5.0, missing=None, source='recorded'),
    dict(name='agenda.calls', key='', value=4, count=4, denominator=None, missing=None, source='recorded'),
    dict(name='source.ancestor_reads', key='', value=1, count=1, denominator=1.0, missing=None, source='recorded'),
    dict(name='host.retry_share', key='', value={'aborts': 0, 'non_tool_stops': 0, 'retries': 0, 'value': None}, count=0, denominator=237.0, missing=None, source='recorded'),
    dict(name='input.frame_unchanged_rate', key='', value={'excluded': 0, 'value': None}, count=0, denominator=229.0, missing='no_frames', source='recorded'),
]


def curator_spend() -> dict:
    return dict(sessions_total=5, sessions_settled=4, sessions_unsettled=1, spent_usd='1.23456789', unsettled_requests=0, spend_complete=False,
        ingestion_usd='0.98', hygiene_usd='0.25456789', hygiene_share=0.2062, ingestion_sessions=3, hygiene_sessions=2,
        applied_tiers={'flex': 4, 'default': 1}, deferrals=1)


def boundary_grooming() -> dict:
    """No receipt is configured, which is the default."""
    return dict(source_status='not_configured', status=None, reason=None, spent_usd=None, spend_complete=None, published_before=None,
        published_after=None, stale_records=None)


# Telemetry --------------------------------------------------------------------------------------------------------

def telemetry(steps: list[dict], summary: dict, recorded: bool) -> dict:
    rows = []
    for index, step in enumerate(steps):
        entry = step_entry(step, recorded)
        rows.append(dict(index=index, request_id=entry['request_id'], actor=entry['actor'], seq=step['seq'], wall=step['wall'],
            prompt_tokens=entry['prompt_tokens'], cache_read=entry['cache_read'], cache_write=entry['cache_write'], output_tokens=41,
            reported_provider=entry['reported_provider'], reported_cost_usd=entry['reported_cost_usd'], estimated_dollars=0.0125,
            is_recall=False, applied_service_tier=entry['applied_service_tier']))
    position = {r['request_id']: r['index'] for r in rows}
    cuts, found, handoffs = [], [], []
    if not recorded:
        for s in steps:
            if s['seq'] in CUTS:
                version = BRIEFINGS.get(s['seq'])
                briefing = dict(briefing_tokens=2400 + s['seq'], source_ids_count=4) if version else None
                cuts.append(dict(cut_fields(s['seq'], version or 'v3', briefing), index=position[f"request-{s['seq']}"], seq=s['seq']))
            if s['seq'] in (78, 79):
                cuts.append(dict(request_id=f"request-{s['seq']}", outcome='held_back', reason='uncovered', knowledge_version='v2', covered_through_operation_id=None,
                    available_turns=18, min_free=8000, triggers=['high_mark'], cut_result=None, tokens_before=61400, tokens_after=None, images_before=39,
                    images_after=None, removed_turns=None, uncovered_turns=None, cumulative_removed_turns=None, briefing_tokens=None, source_ids_count=None,
                    index=position[f"request-{s['seq']}"], seq=s['seq']))
        found = [dict(w, start_index=position.get(w['start_request_id']), end_index=position.get(w['end_request_id']),
            start_seq=int(w['start_request_id'].split('-')[1]), end_seq=int(w['end_request_id'].split('-')[1])) for w in waits(steps)]
        handoffs = [dict(actor=ACTOR2, index=r['index'], seq=r['seq'], wall=r['wall']) for r in rows if r['seq'] == HANDOFF + 1]
    def price(r):
        return float(r['reported_cost_usd']) if r['reported_cost_usd'] is not None else r['estimated_dollars']
    top = sorted(rows, key=price, reverse=True)[:15]
    host, curator = summary.get('host_telemetry') or {}, summary.get('curator_spend') or {}
    sessions = [] if recorded else [dict({k: s[k] for k in ('label', 'session_id', 'session_kind', 'started_wall', 'wall_seconds', 'cost_usd', 'settled')},
        seq=s['_seq']) for s in curator_sessions(steps)]
    return dict(schema=API, source='evaluation_record' if recorded else 'host_trace', requests=rows, requests_total=len(rows), requests_omitted=0,
        top_costliest=top, coverage_waits=found, coverage_waits_omitted=0, curator_sessions=sessions, handoffs=handoffs,
        service_tiers=host.get('service_tiers') or dict(player={}, latest_player_tier=None), cuts=cuts, cuts_omitted=0,
        response_by_endpoint=host.get('response_by_endpoint', {}),
        spend_reserve_reached=[dict(actor=ACTOR2, actor_id=ACTOR2, seq=steps[-1]['seq'], wall=steps[-1]['wall'], spent_usd='2.5', spend_limit_usd='5',
            finish_reserve_usd='2.5', unpriced_bound_usd='0.05')] if not recorded else [], spend_reserve_reached_omitted=0,
        tail_notices=host.get('tail_notices') or dict(count=0, by_kind={'context-capacity': 0, 'host-timeout': 0, 'spend-limit': 0}),
        spend=dict(player_reported_usd=host.get('reported_cost_usd'), player_estimated_usd=summary['dollars'],
            spend_limit_usd=summary['facts'].get('spend_allowance_usd'), spend_complete=host.get('spend_complete'),
            unpriced_requests=host.get('unpriced_requests'), unpriced_recall_requests=host.get('unpriced_recall_requests'),
            curator_spent_usd=curator.get('spent_usd'), curator_spend_complete=curator.get('spend_complete'),
            curator_sessions_settled=curator.get('sessions_settled'), curator_sessions_total=curator.get('sessions_total')))


# Curator ----------------------------------------------------------------------------------------------------------

def curator_sessions(steps: list[dict]) -> list[dict]:
    """Three ingestion windows, two interleaved hygiene passes (one a 429 flex deferral), as `curator_ops._compact` lists them."""
    by = {s['seq']: s for s in steps}
    rows = []
    plan = [('w-001-1-40', 'admission', 41, (1, 40), '0.31', True, [200], 0, None),
            ('h-001-1', 'hygiene', 61, None, '0.12', True, [200], 0, None),
            ('w-001-41-75', 'admission', 81, (41, 75), '0.35', True, [200, 200], 0, None),
            ('h-002-1', 'hygiene', 131, None, '0.13456789', True, [429, 200], 1, dict(reason='flex-capacity-deferred', ok=False)),
            ('w-002-76-160', 'admission', 165, (76, 160), '0.32', False, [200], 0, None)]
    for label, kind, seq, window, usd, settled, statuses, deferrals, end in plan:
        step = by.get(seq, steps[-1])
        rows.append(dict(id=f'session-{label}', group='001' if seq <= HANDOFF else '002', label=label, session_id=f'session-{label}', session_kind=kind,
            window=dict(session='fixture-run', actor='001' if window and window[1] <= HANDOFF else '002', first=window[0], last=window[1]) if window else None,
            coverage=dict(session='s01', actor='001', last_step=window[1]) if window else None, started_wall=step['wall'], wall_seconds=42.5 + seq / 10,
            run_state='live', session_state='failed' if end else 'ended', stopped_by_cap=False, requested_service_tier='flex', requests=len(statuses) * 3,
            published_before=None, published_after=None, cost_usd=usd, cap_usd='1', settled=settled, unsettled_requests=0 if settled else 2,
            applied_service_tiers=['flex'] if deferrals == 0 else ['default'], deferrals=deferrals, model_status=statuses,
            verdicts_summary=dict(published=1 if kind == 'admission' else 0, rejected=0, unchanged=0 if kind == 'admission' else 1, total=1),
            drafts_summary=dict(created=1 if kind == 'admission' else 0, renewed=0, refused=0), host_end=end, _seq=seq))
    return rows


def public_session(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith('_')}


def runner_status(available: bool, archived: bool = False, now: float = 1700000003) -> dict:
    """The `runner` part of `/curator`: `curator-runner-status/2` for the live run, an archived `/1` with no limits, or none."""
    base = dict(read_wall=now)
    if not available:
        return dict(base, source_status='missing', snapshot=None, status=None)
    place = dict(actor='001', step=180, operation='op-180', ordinal=180)
    walls = dict(began=1700000000, ended=1700000001)
    stamp = dict(session='fixture-run', actor='001', last_step=160)
    status = dict(session='fixture-run', state='polling', updated_wall=1700000002, stop_reason=None, look_error=None,
        settings=dict(trigger_steps=20, ceiling_steps=60, poll_seconds=5, watch_seconds=600),
        position=dict(place, read_wall=walls), as_of=dict(place, read_wall=walls),
        snapshot=dict(hold_seconds=0.012, transaction_seconds=0.034, staging_seconds=0.21, read_wall=walls),
        current=None, covered_prefix=dict(end=dict(place, step=160, ordinal=160), restore=None), lag=20, stamp_distance=20, backlog=20,
        last_confirmed=dict(version='v6', label='w-002-76-160', window=dict(session='fixture-run', actor='002', first=76, last=160), coverage=stamp, baseline=False),
        latest_version=dict(version='v7', coverage=stamp, baseline=False),
        failures=dict(sessions=0, snapshots=0, hygiene=1, flex_deferrals=1), status_schema='curator-runner-status/2',
        limits=dict(cap_usd='5', session_cap_usd='1', service_tier='flex', flex_deferral_limit=3,
            hygiene=dict(enabled=True, min_windows=2, max_unexamined_steps=200, pass_cap_usd='0.2', max_spend_share='0.4', max_requests=40,
                wall_seconds=300, host_wall_seconds=420, max_consecutive_failures=2)),
        after_last_read='unknown',
        examined=dict(items=[dict(session_kind='admission', label='w-001-1-40', window=dict(session='fixture-run', actor='001', first=1, last=40),
            session_id='session-w-001-1-40', outcome='accepted', advanced=True, started_wall=1699999990, ended_wall=1700000000)], total=1, omitted=0),
        unexamined=dict(items=None, total=None, omitted=None), unconfirmed=0)
    if archived:
        status.update(status_schema='curator-runner-status/1', limits=None, settings='unknown', snapshot='unknown', state='ended',
            failures=dict(sessions=0, snapshots=0, hygiene=None, flex_deferrals=None), unexamined=dict(items=[], total=0, omitted=0))
    return dict(base, source_status='available', snapshot=dict(sha256='a' * 64, bytes=900), status=status)


GATES = [dict(index=0, operation_id='c' * 32, operation='submission', status='published', base_version='v1', restored_from=None, version='v2',
              submission='draft-1', session='session-w-001-1-40', from_drafts=['draft-water'], from_drafts_omitted=0, diagnostics=[], diagnostics_omitted=0),
         dict(index=3, operation_id='d' * 32, operation='submission', status='rejected', base_version='v3', restored_from=None, version=None,
              submission='draft-2', session='session-w-001-41-75', from_drafts=[], from_drafts_omitted=0, diagnostics=['stale base'], diagnostics_omitted=0)]
DRAFTS = [dict(id='draft-water', bucket='archived', state='promoted', untouched_sessions=0, created_by_session='session-w-001-1-40',
               last_touched_session='session-w-001-1-40', promoted_by_session='session-w-001-1-40', sessions=dict(items=['session-w-001-1-40'], omitted=0, values_omitted=0),
               max_bytes=4096, retention_policy='retained')]


def run_curator(steps: list[dict], live: bool, archived: bool) -> dict:
    if not live and not archived:
        empty = dict(source_status='not_configured', filtered_to_run=True, total_lineage=0, items=[], total=0, omitted=0)
        return dict(schema=API, runner=runner_status(False), spend=None, sessions=[], sessions_omitted=0, grooming=boundary_grooming(),
            gate_verdicts=empty, drafts=empty)
    sessions = [public_session(r) for r in curator_sessions(steps)]
    if archived:
        sessions = sessions[:1]
    return dict(schema=API, runner=runner_status(True, archived), spend=curator_spend() if live else dict(curator_spend(), sessions_total=1, sessions_settled=1,
        sessions_unsettled=0, spent_usd='0.31', ingestion_usd='0.31', hygiene_usd=None, hygiene_share=0.0, ingestion_sessions=1, hygiene_sessions=0,
        applied_tiers={'flex': 1}, deferrals=0, spend_complete=True), sessions=sessions, sessions_omitted=0,
        grooming=dict(boundary_grooming(), source_status='available', status='completed', spent_usd='0.08', spend_complete=True,
            published_before='v6', published_after='v7', stale_records=3) if archived else boundary_grooming(),
        gate_verdicts=dict(source_status='available', filtered_to_run=True, total_lineage=7, items=GATES if live else GATES[:1], total=2 if live else 1, omitted=0),
        drafts=dict(source_status='available', filtered_to_run=True, total_lineage=5, items=DRAFTS, total=1, omitted=0))


def curator_session(steps: list[dict], wanted: str) -> dict | None:
    row = next((r for r in curator_sessions(steps) if wanted in (r['id'], r['session_id'], r['label'])), None)
    if row is None:
        return None
    ledger = [dict(ts=None, wall=row['started_wall'] + i, model='curator-model', status=code, reserved='0.05', charged=None if code == 429 else '0.04',
        refused=code == 429, usage_missing=False, service_tier='flex', applied_service_tier=None if code == 429 else 'flex', latency_ms=800 + i * 40,
        tokens=dict(prompt=12000, completion=300, cached=9000, cache_write=0, reasoning=0, prompt_tokens=None, completion_tokens=None, total_tokens=None))
        for i, code in enumerate(row['model_status'] * 3)]
    detail = dict(public_session(row), tokens=dict(prompt=36000, completion=900, cached=27000, cache_write=1200, reasoning=0),
        tool_calls=dict(count=14, failed=1, bytes=48000, by_name={'knowledge_query': 6, 'draft_write': 5, 'gate_submit': 3}),
        sandbox=dict(stopped='flex-capacity-deferred' if row['host_end'] else 'completed', seconds=row['wall_seconds'], peak_memory_bytes=180_000_000,
            returncode=0, survivors=[]), errors=[], refused=[],
        verdicts=[dict(operation='submission', status='published' if row['session_kind'] == 'admission' else 'unchanged', submission='draft-1',
            version='v2' if row['session_kind'] == 'admission' else None, diagnostics=[])],
        drafts=dict(created=[dict(id='draft-water', draft_id=None, reason=None)] if row['session_kind'] == 'admission' else [], renewed=[], refused=[]),
        proxy=dict(entries=len(ledger), charged_usd=row['cost_usd'], max_reserved_usd='0.05', refusals=sum(r['refused'] for r in ledger), forwarded=len(ledger),
            cap_refused=0, usage_missing=0, settled=row['settled'], unsettled_requests=row['unsettled_requests'], pending_reserved_usd=None, revoked=False,
            breaches=0, receipt_error=None, refusal_reasons=['flex-capacity'] if row['deferrals'] else []))
    return dict(schema=API, session=detail, ledger=ledger[:4], ledger_total=len(ledger), ledger_omitted=max(0, len(ledger) - 4))


# Delivered knowledge ----------------------------------------------------------------------------------------------

def seen(step: int, session: str = 's01') -> dict:
    """A delivered position: an opaque session alias, never this run's ID."""
    return dict(session=session, actor='001', step=step)


def state(**extra) -> dict:
    """The record state a current row carries: active, bound to no world, nothing flagged or linked."""
    rows = dict(branch_relation=None, lifecycle_state='active', needs_review=False, unverified_branch=False,
        scope='game', scope_axes={}, tags=[], stale_citations=[], shadowed_by=[], contradicted_by=[], links=[], backlinks=[]) | extra
    return dict(rows, **{f'{name}_omitted': 0 for name in ('tags', 'stale_citations', 'shadowed_by', 'contradicted_by', 'links', 'backlinks')})


def ancestor_anchor() -> dict:
    """A frame another admission of the lineage recorded, as `frame.source_location` resolves one."""
    return dict(run=ANCESTOR['run'], session=ANCESTOR['session'], seq=12, source_id=ANCESTOR_SOURCE, available=True, reason=None)


def fact(identity: str, text: str, kind: str, step: int | None, anchored: bool = True, **extra) -> dict:
    """A fact of a `delivered-knowledge/4` export as the viewer lists it. `step` None cites the ancestor admission."""
    if step is None:
        cited, anchor = ANCESTOR_SOURCE, ancestor_anchor()
    else:
        cited = SOURCES[step] if anchored else ELSEWHERE
        anchor = dict(seq=step, source_id=cited) if anchored else None
    return dict(id=identity, statement_kind=kind, subject=f'Subject of {identity}', text=text,
        cited_by_articles=[], cited_by_articles_omitted=0, citation_source_ids=[cited], citation_source_ids_omitted=0, citation_anchors=[anchor],
        seen=seen(step or 12, 's01' if anchored else 's02'), frame_anchor=anchor, **state(**extra))


def article(identity: str, title: str, facts: list[str], step: int, **extra) -> dict:
    return dict(id=identity, revision=f'{identity}@v1', title=title, lead=f'{title} in one sentence.', body=[dict(text=f'What is known about {title.lower()}.', facts=facts,
        facts_omitted=0)], body_omitted=0, last_confirmed=dict(seen(step), order=[1, '001', step], order_omitted=0,
        order_omitted_characters={}), anchor=dict(seq=step, source_id=SOURCES[step]), **state(**extra))


WORLD = dict(scope='world', branch_relation='same')
ARTICLES = {'v1': [article('article-water', 'Finding water', ['fact-water'], 20, tags=['water'], **WORLD)]}
FACTS = {'v1': [fact('fact-water', 'A stream runs past the east wall.', 'state', 20, tags=['water'], state_key='water-course',
        depiction_source_id=SOURCES[20], **WORLD),
    fact('fact-wait', 'A dot waits one turn.', 'observation', 25)]}
FACTS['v1'][0]['seen']['clock_label'] = '09:00'
ARTICLES['v2'] = [*ARTICLES['v1'], article('article-fire', 'Making fire', ['fact-fire', 'fact-water'], 90, tags=['fire'],
    links=[dict(rel='see_also', target='article-water')])]
FACTS['v2'] = [*FACTS['v1'], fact('fact-fire', '<script>window.knowledgeExecuted=true</script> A lighter lights a fire ring.', 'observation', 90,
        tags=['fire'], scope_axes=dict(ruleset='standard'), links=[dict(rel='depends_on', target='water-course')]),
    fact('fact-old', 'An earlier admission saw a shelter.', 'state', 7, anchored=False, scope='world', branch_relation='unknown',
        state_key='shelter-state', anchor='water-course', anchor_display='Stream', when='while the passage is open',
        unverified_branch=True, needs_review=True, lifecycle_state='contested', contradicted_by=['fact-water'], stale_citations=['fact-gone'])]
FACTS['v2'][-1]['seen']['prior_clock'] = dict(label='08:45', step_offset=2)
ARTICLES['v3'] = ARTICLES['v4'] = ARTICLES['v2']
FACTS['v3'] = FACTS['v4'] = FACTS['v2']
# From v5 on the curator keeps facts only: the world's state by key and anchor.
FACTS['v5'] = [fact('fact-water2', 'A stream runs past the east wall.', 'state', 20, tags=['water', 'east'], state_key='water-course',
        anchor='east-wall', anchor_display='East wall', when='in spring', **WORLD),
    fact('fact-shelter', 'The shelter door is barricaded.', 'state', 90, tags=['shelter'], state_key='shelter-door', anchor='east-wall',
        anchor_display='East wall', **WORLD)]
FACTS['v6'] = [fact('fact-water3', 'The stream is frozen over.', 'state', 150, tags=['water', 'ice'], state_key='water-course', anchor='east-wall',
        anchor_display='East wall', when='while it is below zero', **WORLD),
    FACTS['v5'][0], FACTS['v5'][1],
    fact('fact-ancestor', 'An earlier admission cached food in the cellar.', 'state', None, tags=['food', 'cellar'], state_key='food-cache', anchor='cellar',
        anchor_display='Cellar', **WORLD),
    fact('fact-fire2', 'A fire ring sits north of the shelter.', 'observation', 120, tags=['fire']),
    fact('fact-boil', 'Boiling the meltwater made it safe to drink.', 'outcome', 160, tags=['boil', 'water']),
    fact('fact-plan', 'Water, not food, is what limits this survivor.', 'synthesis', 170, tags=['plan'])]
FACTS['v7'] = [*FACTS['v6'], fact('fact-late', 'The cellar may flood in a thaw.', 'inference', 210, tags=['cellar'], needs_review=True)]
for name in ('v5', 'v6', 'v7'):
    ARTICLES[name] = []
REPLACED = {'v6': {'fact-water2@v5': dict(reason='changed', by=['fact-water3'], by_omitted=0)},
            'v7': {'fact-water2@v5': dict(reason='changed', by=['fact-water3'], by_omitted=0)}}
EXPORTED = ['v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7']
#: Each version's place in the chain and the deliveries the trace records of it: (status, [(kind, outcome, seq, summary)]).
CHAIN = {'v1': ('delivered', [('opening_briefing', 'delivered', 2), ('post_cut_briefing', 'delivered', 40)]),
         'v2': ('delivered', [('update', 'delivered', 60), ('post_cut_briefing', 'delivered', 80), ('post_cut_briefing', 'delivered', 160)]),
         'v3': ('empty_suppressed', [('empty_suppressed', 'empty-suppressed', 110)]),
         'v4': ('refused', [('refused', 'refused', 140)]), 'v5': ('superseded', []),
         'v6': ('delivered', [('update', 'delivered', 170), ('post_cut_briefing', 'delivered', 200)]),
         'v7': ('exported_not_delivered', [('undelivered', 'undelivered', 215)]), 'v8': ('published_only', [])}
PREVIOUS = {'v2': 'v1', 'v3': 'v2', 'v4': 'v3', 'v6': 'v5', 'v7': 'v6'}


def counted(records: list[dict]) -> tuple[list[dict], dict]:
    tags: dict[str, int] = {}
    for r in records:
        for t in r['tags']:
            tags[t] = tags.get(t, 0) + 1
    kinds: dict[str, int] = {}
    for r in records:
        if 'statement_kind' in r:
            kinds[r['statement_kind']] = kinds.get(r['statement_kind'], 0) + 1
    return [dict(tag=t, count=n) for t, n in sorted(tags.items(), key=lambda i: (-i[1], i[0]))], dict(sorted(kinds.items()))


def coverage(name: str) -> dict:
    return dict(session='s01', actor='001', last_step={'v1': 1, 'v2': 50, 'v3': 100, 'v4': 130, 'v5': 150, 'v6': 160, 'v7': 205, 'v8': 220}[name])


def quality(articles: list[dict], facts: list[dict]) -> dict:
    keys = {f['state_key'] for f in facts if f.get('state_key')}
    when = sum(bool(f.get('when')) for f in facts)
    combined = articles + facts
    return dict(articles_count=len(articles), facts_count=len(facts), state_count=len(keys), when_count=when,
        when_coverage=when / len(facts) if facts else None, stale_count=sum(bool(r['stale_citations']) for r in combined),
        contested_count=sum(r['lifecycle_state'] == 'contested' for r in combined), unverified_count=sum(r['unverified_branch'] for r in combined),
        needs_review_count=sum(r['needs_review'] for r in combined), default_view='articles' if articles else 'state' if keys else 'facts')


def groups(facts: list[dict], window: list[dict], replaced: dict) -> tuple[list[dict], list[dict]]:
    states: dict[str, list[str]] = {}
    places: dict[str, dict] = {}
    for f in facts:
        if f.get('state_key'):
            states.setdefault(f['state_key'], []).append(f['id'])
        if f.get('anchor') and f['anchor'] not in states:
            group = places.setdefault(f['anchor'], dict(anchor=f['anchor'], anchor_display=f.get('anchor_display'), fact_count=0, state_keys=[]))
            group['fact_count'] += 1
            if f.get('state_key') and f['state_key'] not in group['state_keys']:
                group['state_keys'].append(f['state_key'])
    shown: dict[str, list[dict]] = {}
    for f in window:
        if f.get('state_key') in states:
            shown.setdefault(f['state_key'], []).append({k: f.get(k) for k in ('id', 'subject', 'text', 'statement_kind', 'when', 'anchor', 'anchor_display', 'frame_anchor')})
    rows = []
    for key, items in shown.items():
        ids = set(states[key])
        matches = {k: v for k, v in replaced.items() if k.split('@')[0] in ids or not ids.isdisjoint(v['by'])}
        rows.append(dict(state_key=key, facts=items, replaced=matches, count=len(states[key]), facts_omitted=len(states[key]) - len(items)))
    return rows, list(places.values())


def chain_row(name: str) -> dict:
    status, shown = CHAIN[name]
    exported = name in EXPORTED
    base = dict(version=name, status='available' if exported else 'missing', recorded_version=name, articles_count=len(ARTICLES[name]) if exported else None,
        facts_count=len(FACTS[name]) if exported else None, coverage=coverage(name))
    return dict(base, published=True, baseline=False, exported=exported, delivery_status=status,
        deliveries=[dict(delivery_kind=k, outcome=o, actor=actor_at(seq), request_id=f'request-{seq}', seq=seq, summary=None) for k, o, seq in shown],
        deliveries_omitted=0)


def delivery_of(name: str) -> dict | None:
    """As `delivered.delivery_for`: a delivered entry first, else the latest refusal, suppression or undelivered one."""
    _, shown = CHAIN[name]
    pick = next((s for s in shown if s[1] == 'delivered'), None) or next((s for s in reversed(shown) if s[0] in ('refused', 'empty_suppressed', 'undelivered')), None)
    if pick is None:
        return None
    kind, outcome, seq = pick
    counts, preview = DELTAS.get(name, (None, [])) if kind == 'update' else (None, [])
    briefing = 'briefing' in kind
    return dict(actor=actor_at(seq), seq=seq, kind='briefing' if briefing else 'update', delivery_kind=kind, outcome=outcome, request_id=f'request-{seq}',
        knowledge_version=name, previous_version=PREVIOUS.get(name), delta_counts=counts, delta_preview=preview, leads_count=2 if briefing else None,
        index_count=3 if briefing else None, summary=' · '.join(f"{n} {k.replace('_', ' ')}" for k, n in counts.items() if n) if counts else
        {'opening_briefing': '2 leads · 3 index entries', 'empty_suppressed': 'No substantive changes', 'refused': 'Delivery refused',
         'undelivered': 'Delivery did not reach the player'}.get(kind))


def delivered(version: str | None, query: str, scope: str, kind: str, after: int, limit: int) -> dict | None:
    if version and version not in CHAIN:
        return None
    chain = [chain_row(name) for name in CHAIN]
    chosen = version or EXPORTED[-1]
    rows = [{k: r[k] for k in ('version', 'status', 'recorded_version', 'articles_count', 'facts_count', 'coverage')} for r in chain if r['exported']]
    if chosen not in EXPORTED:
        return dict(no_knowledge(limit), versions=rows, version_chain=chain, selected_version=chosen, recorded_version=chosen, coverage=coverage(chosen),
            delivery=delivery_of(chosen))
    needle = query.strip().lower()
    articles = [a for a in ARTICLES[chosen] if needle in ' '.join((a['id'], a['title'], a['lead'], a['body'][0]['text'], *a['tags'])).lower()]
    facts = [f for f in FACTS[chosen] if needle == f.get('state_key') or needle in ' '.join(
        (f['id'], f['statement_kind'], f['subject'], f['text'], f.get('anchor_display') or '', f.get('when') or '', *f['tags'])).lower()]
    if kind:
        facts = [f for f in facts if f['statement_kind'] == kind]
    counts = dict(world=sum(f['scope'] == 'world' for f in facts), game=sum(f['scope'] == 'game' for f in facts), unrecorded=0)
    if scope != 'all':
        facts = [f for f in facts if f['scope'] == scope]
    window = facts[after:after + limit]
    tags, kinds = counted(ARTICLES[chosen] + FACTS[chosen])
    replaced = REPLACED.get(chosen, {'fact-shelter-before': dict(reason='changed', by=['fact-old'], by_omitted=0)} if chosen != 'v1' else {})
    state_groups, anchor_groups = groups(facts, window, replaced)
    return dict(schema=API, source_status='available', versions=rows, version_chain=chain, selected_version=chosen, recorded_version=chosen,
        knowledge_schema='delivered-knowledge/4', coverage=coverage(chosen), delivery=delivery_of(chosen), quality=quality(ARTICLES[chosen], FACTS[chosen]),
        state_groups=state_groups, anchor_groups=anchor_groups, articles=articles, articles_total=len(articles), articles_omitted=0,
        scope_recorded=True, scope_counts=counts, tag_counts=tags, tag_counts_omitted=0, statement_kind_counts=kinds,
        frame_clocks={SOURCES[20]: '09:00'} if any(SOURCES[20] in f['citation_source_ids'] for f in window) else {},
        history=dict(replaced=replaced, replaced_omitted=0, ended=[], ended_omitted=0, retracted=[], retracted_omitted=0),
        facts=dict(items=window, total=len(facts), next=after + len(window) if after + len(window) < len(facts) else None, limit=limit))


def no_knowledge(limit: int) -> dict:
    return dict(schema=API, source_status='unavailable', versions=[], version_chain=[], selected_version=None, recorded_version=None, coverage=None,
        delivery=None, articles=[], articles_total=0, articles_omitted=0, state_groups=[], anchor_groups=[], quality=quality([], []),
        scope_recorded=False, scope_counts=dict(world=0, game=0, unrecorded=0), tag_counts=[], tag_counts_omitted=0, statement_kind_counts={},
        facts=dict(items=[], total=0, next=None, limit=limit))


def delivery_event(version: str) -> dict:
    rows = {'v2': dict(added=[dict(id='article-fire', title='Making fire', lead='Making fire in one sentence.'), dict(id='fact-old', title='Shelter', lead='An earlier admission saw a shelter.')],
        updated=[], removed=[])}.get(version, dict(added=[], updated=[], removed=[]))
    return dict(type='knowledge-delivery', kind='update', outcome='delivered', line=9, version=version, article_ids=[], article_ids_omitted=0, fact_ids=[],
        fact_ids_omitted=0, index_ids=[], index_ids_omitted=0, removed_ids=[], removed_ids_omitted=0, coverage=None, leads=[], leads_omitted=0, index=[],
        index_omitted=0, **rows, **{f'{k}_omitted': 0 for k in rows})


def source_call(session: str) -> dict:
    """The `/knowledge` projection of the `player_source` call: the real frame, the alias the player saw, and its anchor."""
    return dict(request_id='request-30', tool_call_id='player_source-30', tool='player_source', status='finished', intent='Look at the earlier frame again.',
        query=None, operation_id=None, source_id=ANCESTOR_SOURCE, cites=[], cites_omitted=0, returned_ids=[], returned_ids_omitted=0,
        returned_hits=[], returned_hits_omitted=0, step=None, result=dict(status='completed', reason=None, delivered=None, operation_id=None),
        operation=None, player_alias='s01', non_clickable=True, origin='ancestor',
        anchors=[dict(run=ANCESTOR['run'], session=ANCESTOR['session'], seq=12, source_id=ANCESTOR_SOURCE, available=True, reason=None)])
