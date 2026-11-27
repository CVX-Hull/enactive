"""Synthetic coverage for the #949 and #1046 replays. No sealed evidence is needed."""
import json
import subprocess

import pytest

from harness.jsonio import canonical
from tools import player_host_replay_benchmark as replay


def article(rid, order=1, *, title=None, lead='An article lead.', cited=()):
    return dict(id=rid, title=title or rid, lead=lead, body=[dict(text='A claim.', facts=list(cited))],
                last_confirmed={'order': [1, 'actor', order]})


def fact(rid, order=1, *, kind='control', text='A fact lead.'):
    return dict(id=rid, subject=rid, type=kind, text=text, seen={'order': [1, 'actor', order]})


def snapshot(articles=(), facts=(), version='v1'):
    return replay.Snapshot(dict(schema='delivered-knowledge/2', version=version, coverage=None,
                                articles=list(articles), facts=list(facts)))


def test_briefing_tiers_caps_tie_break_and_delivered_order(monkeypatch):
    monkeypatch.setattr(replay, 'CUT_BRIEFING_ARTICLES', 2)
    monkeypatch.setattr(replay, 'CUT_BRIEFING_FACTS', 2)
    store = snapshot([article('early-tie', 9), article('late-tie', 9), article('selected', 1, cited=['filed'])],
                     [fact('filed', 100), fact('new-instance', 10, kind='world_observation'),
                      fact('older-control', 2), fact('selected-fact', 1)])
    payload = replay.briefing(store, ['selected-fact', 'selected'])
    ids = lambda field: [row['id'] for row in payload[field]]  # noqa: E731
    assert ids('leads') == ['selected', 'selected-fact']
    assert ids('index') == ['early-tie', 'older-control']
    assert payload['unlisted_entries'] == 2
    assert [r['id'] for r in replay.briefing(store, cut=True, main=True)['leads']] == ['early-tie', 'late-tie']
    assert [r['id'] for r in replay.briefing(store, cut=True)['leads']] == ['early-tie', 'late-tie']
    monkeypatch.setattr(replay, 'CUT_BRIEFING_ARTICLES', 1)
    assert [r['id'] for r in replay.briefing(store, cut=True, main=True)['leads']] == ['late-tie']
    assert [r['id'] for r in replay.briefing(store, cut=True)['leads']] == ['early-tie']


def test_briefing_skips_oversize_clips_and_budgets_serialized_json():
    store = snapshot([article('large', title='"' * 200), article('short', lead='A"\\\n😀'),
                      article('clipped', lead='a' * 998 + '😀xx')])
    bounded = replay.briefing(store, ['large', 'short'], limit=190)
    assert [row['id'] for row in bounded['leads']] == ['short']
    assert bounded['unlisted_entries'] == 2 and replay.size(bounded) <= 190
    clipped = replay.briefing(store, ['clipped'])['leads'][0]['lead']
    assert clipped == 'a' * 998 + '…' and replay.chars(clipped) <= 1000


def test_recall_user_message_one_is_title_first_and_skips_oversized_rows():
    store = snapshot([article('first', 3, title='a' * 118 + '😀xx', lead='Enough for a useful snippet. Next.'),
                      article('second', 3), article('third', 2)],
                     [fact('state', 9, kind='world_observation'), fact('control', 1)])
    titles = replay.recall_index(store, title_only=True)
    assert [row['id'] for row in titles['index']] == ['first', 'second', 'third', 'control', 'state']
    assert titles['index'][0]['title'] == 'a' * 118 + '…'
    exact = replay.size(titles)
    assert replay.recall_index(store, limit=exact) == titles
    sent = replay.recall_index(store, limit=exact + 50)
    assert sent['index'][0]['index'] == 'Enough for a useful snippet'
    assert replay.size(sent) <= exact + 50
    overflow = replay.recall_index(store, limit=115)
    assert 'first' not in [row['id'] for row in overflow['index']]
    assert overflow['index'] and all('index' not in row for row in overflow['index'])
    assert overflow['unlisted_entries'] == 5 - len(overflow['index'])
    assert replay.size(overflow) <= 115


def test_active_fingerprints_require_full_current_leads_and_respect_updates_and_removals():
    then = snapshot([article('short'), article('long', lead='a' * 1001), article('indexed')])
    now = snapshot([article('short', lead='New revision.'), article('long', lead='a' * 1001), article('indexed')],
                   version='v2')
    active = replay.ActiveLeads()
    active.place(then, replay.briefing(then, ['short', 'long'])['leads'], bounded=True)
    assert active.already_in_context(then) == ['short']
    assert active.already_in_context(now) == []
    active.place(now, [replay.lead(now.entries['short']), replay.lead(now.entries['long'])])
    active.place(then, [replay.lead(then.entries['short'])])
    active.remove(then, ['short'])
    assert active.already_in_context(now) == ['long', 'short']
    active.remove(now, ['short'])
    assert active.already_in_context(now) == ['long']


def test_recall_replay_separates_placement_silence_from_avoided_fetch_spend():
    before = snapshot([article('present'), article('new')])
    after = snapshot([article('present'), article('new')], version='v2')
    stores = {s.version: s for s in (before, after)}
    indexes = {v: set(s.entries) for v, s in stores.items()}
    present, new = [replay.lead(item) for item in before.articles]

    def placement(kind, request, version, payload, recall_id=None):
        return dict(type='knowledge-delivery', kind=kind, receiving_player_request_id=request, version=version,
                    recall_request_id=recall_id, text=f'BEGIN\n{canonical(payload)}\nEND')

    def manifest(request, prefix, *deliveries):
        return dict(type='context-manifest', request_id=request, reused_prefix_parts=prefix,
                    parts=[dict(role='user', kind='text', sha256=replay.digest(d['text'])) for d in deliveries])

    def attempt(rid, version, cost):
        return [dict(type='request-fetch-start', request_role='recall', request_id=rid),
                dict(type='response-complete', request_role='recall', request_id=rid, counted_cost_usd=cost),
                dict(type='knowledge-recall', request_id=rid, version=version)]

    initial = placement('briefing', 'request-1', 'v1', dict(leads=[present]))
    reminder = placement('reminder', 'request-2', 'v1', dict(leads=[new]), 'recall-1')
    update = placement('update', 'request-2', 'v2', dict(added=[], updated=[new]))
    events = [initial, manifest('request-1', 0),
              *attempt('recall-1', 'v1', '0.10'), reminder, update, manifest('request-2', 0, reminder, update),
              *attempt('recall-2', 'v2', '0.30')]
    outcome = replay.replay_recall(events, stores, indexes)
    assert (outcome['fetches'], outcome['placement_silent'], outcome['all_delivered']) == (2, 1, 1)
    assert str(outcome['observed_usd']) == '0.40'
    assert str(outcome['avoided_usd']) == '0.30'


@pytest.fixture
def policy():
    return replay.CutPolicy(high=70, low=30, min_free=2, max_images=12, block=4, hard_limit=100)


def check(state, policy, uncut, choices=(), frontier='frontier', **guards):
    return state.check(policy, uncut, len(choices), lambda: iter(choices), frontier, **guards)


def test_cut_arm_and_edge_holds_persist_after_pressure_drops(policy):
    state = replay.Hysteresis()
    high = replay.Projection(90, 0, 11)
    relaxed = replay.Projection(20, 0, 5)
    assert check(state, policy, high) == ('uncovered', 0)
    assert check(state, policy, relaxed) == ('suppressed-hold', 0)
    assert check(state, policy, relaxed, frontier='advanced') == ('uncovered', 0)
    assert check(state, policy, relaxed, [relaxed], frontier='advanced') == ('below-min-free', 0)
    assert check(state, policy, relaxed, [relaxed], frontier='advanced', restored=True) == ('idle', 0)
    assert not state.armed
    assert check(state, policy, replay.Projection(20, 0, 13, 1)) == ('uncovered', 0)


def test_cut_chooses_smallest_sufficient_prefix_at_or_above_minimum(policy):
    state = replay.Hysteresis()
    high = replay.Projection(90, 0, 11)
    enough = replay.Projection(50, 20, 8)
    too_many_images = replay.Projection(50, 20, 9)
    equality = replay.Projection(100, 70, 8)
    choices = [enough, too_many_images, equality, enough, enough]
    assert check(state, policy, high, choices) == ('cut', 4)
    assert not state.armed and state.prior_omissions == 0


def test_insufficient_cover_holds_and_strict_fit_rescue_is_independent(policy):
    high = replay.Projection(90, 0, 11)
    insufficient = replay.Projection(69, 0, 9)
    state = replay.Hysteresis()
    assert check(state, policy, high, [insufficient, insufficient]) == ('insufficient-cover', 0)
    assert check(state, policy, high, [insufficient, insufficient], version='v2') == ('suppressed-hold', 0)
    # At equality the request fails fit even without high-mark or image pressure.
    hard = replay.Projection(100, 50, 11)
    assert check(replay.Hysteresis(), policy, hard, [hard, insufficient]) == ('rescue', 2)
    assert check(replay.Hysteresis(), policy, hard, [insufficient]) == ('rescue', 1)
    assert check(replay.Hysteresis(), policy, hard, [hard]) == ('stop', 0)
    for guard in (dict(enabled=False), dict(restored=True), dict(orderly_stop=True)):
        assert check(replay.Hysteresis(), policy, hard, [insufficient], **guard) == ('stop', 0)


def test_best_effort_fallback_cuts_largest_strictly_reducing_prefix_when_tail_exceeds_low_mark(policy):
    high = replay.Projection(90, 0, 11)
    still_over_low = replay.Projection(65, 0, 9)
    smaller = replay.Projection(55, 0, 9)
    non_shrinking = replay.Projection(92, 0, 9)
    state = replay.Hysteresis()
    assert check(state, policy, high, [still_over_low, still_over_low, smaller], best_effort=True) == ('cut', 3)
    assert not state.armed
    # Without strict token reduction at k == eligible (even if an earlier prefix shrunk), best-effort holds back.
    state2 = replay.Hysteresis()
    assert check(state2, policy, high, [smaller, non_shrinking], best_effort=True) == ('insufficient-cover', 0)
    state3 = replay.Hysteresis()
    assert check(state3, policy, high, [non_shrinking, non_shrinking], best_effort=True) == ('insufficient-cover', 0)


def test_snapshot_v3_tiers_use_world_scope():
    game = dict(id='game', claim_kind='mechanic', scope={'game': 'example'},
                text='A mechanic', seen={'order': [1]})
    world = dict(game, id='world', scope={'game': 'example', 'world': 'example-world'}, seen={'order': [2]})
    store = replay.Snapshot(dict(schema='delivered-knowledge/3', version='v1',
                                 coverage=None, articles=[], facts=[world, game]))
    assert replay.instance_state(world)
    assert not replay.instance_state(game)
    assert store.tiers() == [game, world]


def test_replay_updates_counts_delivered_payloads_and_briefing_pairs():
    def delivery(kind, request, payload, outcome='delivered'):
        return dict(type='knowledge-delivery', kind=kind, outcome=outcome,
                    receiving_player_request_id=request, text=f'BEGIN\n{canonical(payload)}\nEND')

    empty = dict(added=[], updated=[], removed=[])
    events = [delivery('briefing', 'request-1', {}),
              delivery('update', 'request-1', empty),
              delivery('update', 'request-2', dict(empty, removed=[{'id': 'old'}])),
              delivery('update', 'request-3', {'index': [{'id': 'new'}]}),
              delivery('update', 'request-4', {'index': [], 'unlisted_entries': 0}),
              delivery('update', 'request-5', empty, 'empty')]
    assert replay.replay_updates(events) == dict(total=4, empty=2, non_empty=2, paired_with_briefing=1)


def test_recall_v12_skips_without_fetch_keep_recorded_costs_matched():
    store = snapshot()
    events = [
        dict(type='host-start', schema='player-host/12'),
        dict(type='knowledge-recall', status='not-made', reason='all-delivered'),
        dict(type='knowledge-recall', status='not-made', reason='all-delivered'),
        dict(type='knowledge-recall', status='not-made', reason='empty'),
        dict(type='request-fetch-start', request_role='recall', request_id='fetched'),
        dict(type='response-complete', request_role='recall', request_id='fetched', counted_cost_usd='0.10'),
        dict(type='knowledge-recall', status='selected', request_id='fetched', version='v1'),
    ]
    outcome = replay.replay_recall(events, {'v1': store}, {'v1': {'candidate'}})
    assert outcome['fetches'] == 1
    assert outcome['all_delivered'] == 0
    assert outcome['recorded_all_delivered'] == 2
    assert str(outcome['observed_usd']) == '0.10'
    assert str(outcome['avoided_usd']) == '0'


def test_ancestor_frame_inventory_counts_only_prior_admission_png_files(tmp_path):
    runs = [tmp_path / f'admission-{n:02d}' / 'run' for n in range(1, 4)]
    for run, names in zip(runs, [('one.png', 'two.png', 'metadata.json'), (), ('one.png',)]):
        sources = run / 'sources'
        sources.mkdir(parents=True)
        (sources / 'directory.png').mkdir()
        for name in names:
            (sources / name).touch()
    assert replay.ancestor_frame_inventory(runs) == [
        dict(admission='admission-01', pngs=2, ancestor_pngs=0),
        dict(admission='admission-02', pngs=0, ancestor_pngs=2),
        dict(admission='admission-03', pngs=1, ancestor_pngs=2),
    ]


def test_export_sealed_v3_tag_projects_v0_and_v1_without_live_exporter(tmp_path):
    repo = tmp_path / 'sealed-v4'
    repo.mkdir()
    git = lambda *args: subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True, text=True)  # noqa: E731
    git('init', '-q')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    (repo / 'README').write_text('seed\n', encoding='utf-8')
    git('add', 'README')
    git('commit', '-q', '-m', 'v0')
    git('tag', 'v0')

    seen = {'session': 'sess-a', 'actor': '001', 'step': 4, 'order': [1, '001', 4]}
    (repo / 'coverage.json').write_text(json.dumps(seen), encoding='utf-8')
    (repo / 'provenance.json').write_text(json.dumps({
        'frames': {'sess-a-4': seen},
        'sessions': {},
        'branches': {},
        'restores': [],
    }), encoding='utf-8')
    rows = [
        {
            'schema': 'curator-fact/5', 'record': 'fact', 'id': 'f2', 'published_in': 'v1',
            'claim_kind': 'mechanic', 'evidence_basis': 'direct', 'tags': ['camp'],
            'text': 'A second fact.',
            'scope': {'game': 'example', 'ruleset': 'standard'},
            'lifecycle_state': 'active', 'needs_review': False, 'links': [],
            'citations': ['sess-a-4'], 'seen': seen,
        },
        {
            'schema': 'curator-fact/5', 'record': 'fact', 'id': 'f1', 'published_in': 'v1',
            'claim_kind': 'instance_state', 'evidence_basis': 'direct', 'tags': ['camp'],
            'text': 'A world fact.', 'subject': 'camp',
            'scope': {'game': 'example', 'world': 'w1', 'ruleset': 'standard'},
            'lifecycle_state': 'active', 'needs_review': False, 'links': [{'rel': 'see_also', 'target': 'a1'}],
            'citations': ['sess-a-4'], 'seen': seen,
        },
        {
            'schema': 'curator-fact/5', 'record': 'fact', 'id': 'f-old', 'published_in': 'v1',
            'claim_kind': 'instance_state', 'evidence_basis': 'direct', 'tags': ['camp'],
            'text': 'Old world fact.', 'scope': {'game': 'example', 'world': 'w1', 'ruleset': 'standard'},
            'lifecycle_state': 'ended', 'retired': True, 'needs_review': False, 'links': [],
            'citations': ['sess-a-4'], 'seen': seen,
        },
        {
            'schema': 'curator-fact/5', 'record': 'article', 'id': 'a1@v1', 'slug': 'a1', 'published_in': 'v1',
            'title': 'Camp', 'lead': 'Camp lead.', 'body': [{'text': 'Body.', 'facts': ['f1']}],
            'tags': ['camp'], 'scope': {'game': 'example', 'world': 'w1', 'ruleset': 'standard'},
            'lifecycle_state': 'active', 'needs_review': False, 'links': [], 'last_confirmed': seen,
        },
    ]
    (repo / 'facts.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    git('add', '.')
    git('commit', '-q', '-m', 'v1')
    git('tag', 'v1')

    selection = {'world': 'w1', 'context': {'ruleset': 'standard'}}
    empty = replay.export_sealed_v3_tag(repo, 'v0', selection)
    assert empty['schema'] == 'delivered-knowledge/3' and empty['version'] is None and empty['facts'] == []

    exported = replay.export_sealed_v3_tag(repo, 'v1', selection)
    assert exported['schema'] == 'delivered-knowledge/3' and exported['version'] == 'v1'
    assert [a['id'] for a in exported['articles']] == ['a1']
    assert [f['id'] for f in exported['facts']] == ['f1', 'f2']
    assert exported['facts'][0]['scope']['world'] is None
    assert exported['facts'][0]['cited_by_articles'] == ['a1']
    assert exported['articles'][0]['backlinks'] == [{'rel': 'see_also', 'source': 'f1'}]
    assert exported['coverage']['session'] == 's01'
    assert exported['history']['ended'] == ['f-old']
