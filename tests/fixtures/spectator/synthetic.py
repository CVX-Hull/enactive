"""Synthetic host-trace projections for the page tests, built around the captured steps and requests.

The captured fixture run predates the trace fields these routes show, so nothing here is a real response: intents,
costs, endpoints, cuts, knowledge versions and curator figures are invented, and shaped like the viewer's contract.
Standard library only.
"""
from __future__ import annotations

import json
from pathlib import Path

ACTOR = '79e9a7e05352477e8820bc94874b23de'
HOSTILE = '<img src=x onerror=window.storyExecuted=true>'
CUTS = (40, 80, 120, 160, 200)          # step seqs at which a cut is applied
HELD = (38, 39, 78, 79)                 # and those at which one is held back
UPDATES = {60: 'v1', 110: 'v2', 170: 'v3'}
ERROR_STEP, NO_STEP_CALL = 12, 30
SUMMARY_WORDS = {'v1': 'first version · 2 entries', 'v2': '+1 article · +2 facts', 'v3': '+1 fact · ~1 updated · −1 removed'}


def spent(seq: int) -> str:
    return f'{seq * 0.0125:.4f}'


def step_entry(step: dict, recorded: bool) -> dict:
    seq = step['seq']
    prompt = 6000 + (seq % 40) * 1200
    out = dict(id=seq * 100, order=seq * 100, entry_kind='step', seq=seq, exact_step=True, decision=seq, step_decision=step['decision'], wall=step['wall'],
        source_id=step['source_id'], mode=step['mode'], game_time=step['game_time'], tool='computer_input' if step['keys'] else 'computer_observe',
        intent=None, intent_source=None, intent_omitted_characters=0, keys=step['keys'], status='ok', latency_ms=400.0 + seq,
        request_id=f'request-{seq}', tool_call_id=f'call-{seq}', operation_id=f'{seq:032x}', actor=ACTOR, reported_provider=None,
        reported_cost_usd=None, prompt_tokens=prompt, input_tokens=3, cache_read=prompt - 500, cache_write=497, output_tokens=41,
        arguments_preview=None, arguments_omitted_characters=0, result=None)
    if recorded:
        return out
    intent = f'Step {seq}: look around before moving on.'
    if seq == 226:
        intent = f'Read the sign {HOSTILE} on the wall.'
    out.update(intent=intent, intent_source='player_claim', reported_provider='endpoint-a' if seq % 50 else 'endpoint-b',
        reported_cost_usd='0.0125', arguments_preview='{"actions":[{"type":"key","key":"ENTER","modifiers":[]}],"source_id":"source-1"}',
        result=dict(status='completed', reason='Operation completed; application effect is not certified', source_id=step['source_id'],
            receipts=[dict(disposition='delivered', reason='Delivered in order', emitted_events=2)], receipts_omitted=0, result_bytes=132))
    if seq == ERROR_STEP:
        out.update(status='error')
    return out


def milestone(step: dict, offset: int, kind: str, **extra) -> dict:
    place = step['seq'] * 100 - offset
    return dict(id=place, order=place, entry_kind=kind, seq=step['seq'], exact_step=False, decision=None, step_decision=step['decision'],
        wall=step['wall'], source_id=step['source_id'], mode=step['mode'], game_time=step['game_time'], actor=ACTOR, **extra)


def cut(step: dict, applied: bool) -> dict:
    known = [v for seq, v in sorted(UPDATES.items()) if seq <= step['seq']]
    base = dict(request_id=f"request-{step['seq']}", knowledge_version=known[-1] if known else None, triggers=['high_mark'], tokens_before=61400,
        images_before=39)
    if applied:
        return dict(base, outcome='applied', reason=None, tokens_after=24800, images_after=19, removed_turns=20)
    return dict(base, outcome='held_back', reason='uncovered', tokens_after=None, images_after=None, removed_turns=None)


def feed(steps: list[dict], findings: list[dict], recorded: bool) -> list[dict]:
    items = []
    by_seq = {s['seq']: s for s in steps}
    for step in steps:
        items.append(step_entry(step, recorded))
        if recorded:
            continue
        if step['seq'] in CUTS or step['seq'] in HELD:
            items.append(milestone(step, 50, 'context_cut', **cut(step, step['seq'] in CUTS)))
        if step['seq'] in UPDATES:
            version = UPDATES[step['seq']]
            number = int(version[1:])
            items.append(milestone(step, 40, 'knowledge_update', knowledge_version=version, previous_version=f'v{number - 1}' if number > 1 else None,
                outcome='delivered', reason=None, request_id=f"request-{step['seq']}", added_count=2, updated_count=0, removed_count=0,
                added_articles=None, added_facts=None, covered_step=step['seq'] - 10, summary=SUMMARY_WORDS[version]))
        if step['seq'] == NO_STEP_CALL:
            items.append(dict(step_entry(step, False), id=step['seq'] * 100 + 10, order=step['seq'] * 100 + 10, exact_step=False, tool='player_source', keys=[],
                operation_id=None, intent='Look at the earlier frame again.'))
    for number, row in enumerate(f for f in findings if f['kind'] in ('stall', 'death', 'custody_stop', 'handoff', 'run_end')):
        step = by_seq.get(row['seq_start'])
        if step is not None:
            items.append(dict(milestone(step, 0, 'finding', finding_id=row['id'], finding_kind=row['kind'], seq_end=row['seq_end'],
                source=row['source'], payload=row['payload'], payload_omitted=False), id=f"finding:{row['kind']}:{row['seq_start']}:{row['source']}:{row['id']}",
                order=step['seq'] * 100 + 20 + number % 70, decision=step['decision'], exact_step=True))
    return sorted(items, key=lambda item: item['order'])


def terminal_findings(steps: list[dict]) -> list[dict]:
    """What a run's final pass adds: its end, and a finding placed long before it."""
    return [dict(id=9001, seq_start=5, seq_end=5, kind='custody_stop', source='recorded', payload=dict(reason='found by the final pass')),
        dict(id=9002, seq_start=steps[-1]['seq'], seq_end=steps[-1]['seq'], kind='run_end', source='recorded', payload=dict(reason='external stop'))]


def feed_page(items: list[dict], after: int, limit: int, recorded: bool) -> dict:
    rows = [i for i in items if i['order'] > after]
    kinds = ('step', 'context_cut', 'knowledge_update', 'finding')
    return dict(schema='spectator-view/3', items=rows[:limit], next=rows[limit - 1]['order'] if len(rows) > limit else None, limit=limit,
        source='evaluation_record' if recorded else 'host_trace', total=len(items),
        counts={k: sum(i['entry_kind'] == k for i in items) for k in kinds})


def host_telemetry(steps: list[dict]) -> dict:
    last = steps[-1]['seq']
    applied = [s for s in CUTS if s <= last]
    versions = [v for seq, v in sorted(UPDATES.items()) if seq <= last]
    return dict(reported_cost_usd=spent(last), spent_usd=spent(last), player_requests=last, recall_requests=6, unpriced_requests=0,
        unpriced_recall_requests=0, spend_complete=False, response_by_endpoint={'endpoint-a': last - 4, 'endpoint-b': 4},
        latest_provider='endpoint-b',     # the last to answer is not the most frequent
        context_cuts=dict(applied=len(applied), held_back=len([s for s in HELD if s <= last]), latest=dict(request_id=f'request-{applied[-1]}',
            knowledge_version=versions[-1], tokens_before=61400, tokens_after=24800, images_before=39, images_after=19, removed_turns=20,
            triggers=['high_mark'], wall_time=steps[-1]['wall'])),
        knowledge_updates=dict(count=len(versions), latest_version=versions[-1]),
        token_summary=dict(latest_prompt_tokens=34983, p50_prompt_tokens=32766, max_prompt_tokens=49902, cache_hit_share=0.9308))


def curator_spend() -> dict:
    return dict(sessions_total=4, sessions_settled=3, sessions_unsettled=1, spent_usd='1.23456789', unsettled_requests=0, spend_complete=False)


def boundary_grooming() -> dict:
    """No receipt is configured, which is the default."""
    return dict(source_status='not_configured', status=None, reason=None, spent_usd=None, spend_complete=None, published_before=None, published_after=None)


def telemetry(steps: list[dict], summary: dict, recorded: bool) -> dict:
    rows = []
    for index, step in enumerate(steps):
        entry = step_entry(step, recorded)
        rows.append(dict(index=index, request_id=entry['request_id'], actor=ACTOR, seq=step['seq'], wall=step['wall'],
            prompt_tokens=entry['prompt_tokens'], cache_read=entry['cache_read'], cache_write=entry['cache_write'], output_tokens=41,
            reported_provider=entry['reported_provider'], reported_cost_usd=entry['reported_cost_usd'], estimated_dollars=0.0125,
            is_recall=step['seq'] % 40 == 5))
    cuts = [] if recorded else [dict(cut(s, s['seq'] in CUTS), index=s['seq'] - 1, seq=s['seq']) for s in steps if s['seq'] in CUTS or s['seq'] in HELD]
    host, curator = summary.get('host_telemetry') or {}, summary.get('curator_spend') or {}
    return dict(schema='spectator-view/3', source='evaluation_record' if recorded else 'host_trace', requests=rows, requests_total=len(rows),
        requests_omitted=0, cuts=cuts, cuts_omitted=0, response_by_endpoint=host.get('response_by_endpoint', {}),
        spend=dict(player_reported_usd=host.get('reported_cost_usd'), player_estimated_usd=summary['dollars'],
            spend_limit_usd=summary['facts'].get('spend_allowance_usd'), spend_complete=host.get('spend_complete'),
            unpriced_requests=host.get('unpriced_requests'), unpriced_recall_requests=host.get('unpriced_recall_requests'),
            curator_spent_usd=curator.get('spent_usd'), curator_spend_complete=curator.get('spend_complete'),
            curator_sessions_settled=curator.get('sessions_settled'), curator_sessions_total=curator.get('sessions_total')))


# Delivered knowledge ------------------------------------------------------------------------------------------------

#: The source ID the captured run recorded at each step (`steps.json`, written by `refresh.py`): a cited frame of this
#: run is the one its step names. And a frame of another session, which has no anchor here.
SOURCES = {row['seq']: row['source_id'] for row in json.loads((Path(__file__).parent / 'steps.json').read_text())['items']}
ELSEWHERE = 'b' * 32 + '-7'


def seen(step: int, session: str = 's01') -> dict:
    """A delivered position: an opaque session alias, never this run's ID."""
    return dict(session=session, actor='001', step=step)


def state(**extra) -> dict:
    """The record state a `spectator-view/3` row carries: active, bound to no world, nothing flagged or linked."""
    rows = dict(branch_relation=None, lifecycle_state='active', needs_review=False, condition_unverified=False, unverified_branch=False,
        scope='game', scope_axes={}, tags=[], stale_citations=[], shadowed_by=[], contradicted_by=[], links=[], backlinks=[]) | extra
    return dict(rows, **{f'{name}_omitted': 0 for name in ('tags', 'stale_citations', 'shadowed_by', 'contradicted_by', 'links', 'backlinks')})


def fact(identity: str, text: str, kind: str, step: int, anchored: bool = True, **extra) -> dict:
    """A fact of a `delivered-knowledge/3` export as the viewer lists it: anchored by the frames it cites."""
    cited = SOURCES[step] if anchored else ELSEWHERE
    anchor = dict(seq=step, source_id=cited) if anchored else None
    return dict(id=identity, claim_kind=kind, evidence_basis='observed', subject=f'Subject of {identity}', text=text, when=None,
        cited_by_articles=[], cited_by_articles_omitted=0, citation_source_ids=[cited], citation_source_ids_omitted=0, citation_anchors=[anchor],
        seen=seen(step, 's01' if anchored else 's02'), anchor=anchor, **state(**extra))


def article(identity: str, title: str, facts: list[str], step: int, **extra) -> dict:
    return dict(id=identity, revision=f'{identity}@v1', title=title, lead=f'{title} in one sentence.', body=[dict(text=f'What is known about {title.lower()}.', facts=facts,
        facts_omitted=0)], body_omitted=0, last_confirmed=dict(seen(step), order=[1, '001', step], order_omitted=0,
        order_omitted_characters={}), anchor=dict(seq=step, source_id=SOURCES[step]), **state(**extra))


WORLD = dict(scope='world', branch_relation='same')
ARTICLES = {'v1': [article('article-water', 'Finding water', ['fact-water'], 20, tags=['water'], **WORLD)]}
FACTS = {'v1': [fact('fact-water', 'A stream runs past the east wall.', 'instance_state', 20, tags=['water'], **WORLD),
    fact('fact-wait', 'A dot waits one turn.', 'interface', 25)]}
ARTICLES['v2'] = [*ARTICLES['v1'], article('article-fire', 'Making fire', ['fact-fire', 'fact-water'], 90, tags=['fire'],
    links=[dict(rel='see_also', target='article-water')])]
FACTS['v2'] = [*FACTS['v1'], fact('fact-fire', '<script>window.knowledgeExecuted=true</script> A lighter lights a fire ring.', 'mechanic', 90,
        tags=['fire'], scope_axes=dict(ruleset='standard'), links=[dict(rel='depends_on', target='fact-water')]),
    fact('fact-old', 'An earlier admission saw a shelter.', 'instance_state', 7, anchored=False, scope='world', branch_relation='unknown',
        unverified_branch=True, needs_review=True, lifecycle_state='contested', contradicted_by=['fact-water'], stale_citations=['fact-gone'])]
ARTICLES['v3'], FACTS['v3'] = ARTICLES['v2'], [f for f in FACTS['v2'] if f['id'] != 'fact-wait'] + [fact('fact-late', 'A fact of the third version.', 'strategy', 150)]


def counted(records: list[dict]) -> tuple[list[dict], dict]:
    tags: dict[str, int] = {}
    for r in records:
        for t in r['tags']:
            tags[t] = tags.get(t, 0) + 1
    kinds: dict[str, int] = {}
    for r in records:
        if 'claim_kind' in r:
            kinds[r['claim_kind']] = kinds.get(r['claim_kind'], 0) + 1
    return [dict(tag=t, count=n) for t, n in sorted(tags.items(), key=lambda i: (-i[1], i[0]))], dict(sorted(kinds.items()))


def delivered(steps: list[dict], version: str | None, query: str, scope: str, after: int, limit: int) -> dict | None:
    names = ['v1', 'v2', 'v3'][:sum(seq <= steps[-1]['seq'] for seq in UPDATES)]
    if version and version not in names:
        return None
    chosen = version or names[-1]
    coverage = {name: dict(session='s01', actor='001', last_step=seq - 10) for seq, name in UPDATES.items()}
    needle = query.strip().lower()
    articles = [a for a in ARTICLES[chosen] if needle in ' '.join((a['id'], a['title'], a['lead'], a['body'][0]['text'], *a['tags'])).lower()]
    facts = [f for f in FACTS[chosen] if needle in ' '.join((f['id'], f['claim_kind'], f['subject'], f['text'], *f['tags'])).lower()]
    counts = dict(world=sum(f['scope'] == 'world' for f in facts), game=sum(f['scope'] == 'game' for f in facts), unrecorded=0)
    if scope != 'all':
        facts = [f for f in facts if f['scope'] == scope]
    window = facts[after:after + limit]
    tags, kinds = counted(ARTICLES[chosen] + FACTS[chosen])
    return dict(schema='spectator-view/3', source_status='available', versions=[dict(version=n, status='available', recorded_version=n,
        articles_count=len(ARTICLES[n]), facts_count=len(FACTS[n]), coverage=coverage[n]) for n in names], selected_version=chosen,
        recorded_version=chosen, coverage=coverage[chosen], articles=articles, articles_total=len(articles), articles_omitted=0, scope_recorded=True, scope_counts=counts,
        tag_counts=tags, tag_counts_omitted=0, claim_kind_counts=kinds,
        facts=dict(items=window, total=len(facts), next=after + len(window) if after + len(window) < len(facts) else None, limit=limit))


def no_knowledge(limit: int) -> dict:
    return dict(schema='spectator-view/3', source_status='unavailable', versions=[], selected_version=None, recorded_version=None, coverage=None,
        articles=[], articles_total=0, articles_omitted=0, scope_recorded=False, scope_counts=dict(world=0, game=0, unrecorded=0),
        tag_counts=[], tag_counts_omitted=0, claim_kind_counts={}, facts=dict(items=[], total=0, next=None, limit=limit))


def delivery_event(version: str) -> dict:
    rows = {'v2': dict(added=[dict(id='article-fire', title='Making fire', lead='Making fire in one sentence.'), dict(id='fact-old', title='Shelter', lead='An earlier admission saw a shelter.')],
        updated=[], removed=[])}.get(version, dict(added=[], updated=[], removed=[]))
    return dict(type='knowledge-delivery', kind='update', outcome='delivered', line=9, version=version, article_ids=[], article_ids_omitted=0, fact_ids=[],
        fact_ids_omitted=0, index_ids=[], index_ids_omitted=0, removed_ids=[], removed_ids_omitted=0, coverage=None, leads=[], leads_omitted=0, index=[],
        index_omitted=0, **rows, **{f'{k}_omitted': 0 for k in rows})


def runner_status(available: bool) -> dict:
    base = dict(schema='spectator-frame/1', read_wall=1700000003)
    if not available:
        return dict(base, source_status='missing', snapshot=None, status=None)
    place = dict(actor='001', step=180, operation='op-180', ordinal=180)
    walls = dict(began=1700000000, ended=1700000001)
    stamp = dict(session='fixture-run', actor='001', last_step=160)
    return dict(base, source_status='available', snapshot=dict(sha256='a' * 64, bytes=900), status=dict(session='fixture-run', state='polling',
        updated_wall=1700000002, stop_reason=None, look_error=None, position=dict(place, read_wall=walls), as_of=dict(place, read_wall=walls),
        after_last_read='unknown', current=None, covered_prefix=dict(end=dict(place, step=160, ordinal=160), restore=None), lag=20, stamp_distance=20,
        backlog=20, last_confirmed=dict(version='v3', label='w', window=dict(session='fixture-run', actor='001', first=111, last=160), coverage=stamp, baseline=False),
        latest_version=dict(version='v3', coverage=stamp, baseline=False), failures=dict(sessions=0, snapshots=0), unconfirmed=0,
        examined=dict(items=[], total=0, omitted=0), unexamined=dict(items=None, total=None, omitted=None)))
