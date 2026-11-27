"""Dedicated tests for Batch 1 (#1020, #1021, #1022/#1024, #1023) gate and hygiene invariants."""
from __future__ import annotations

import json
from pathlib import Path

from harness.curator import check, hygiene
from harness.curator.gate import gate, restore
from harness.curator.knowledge import Repository
from tests.synthetic_knowledge_repo import position

SEALED = 'a' * 32
F1 = f'{SEALED}-1'
F2 = f'{SEALED}-2'
F3 = f'{SEALED}-3'
F4 = f'{SEALED}-4'
FRAMES = {
    F1: position('s1', 10),
    F2: position('s1', 20),
    F3: position('s1', 30),
    F4: position('s1', 40),
}
LABELS = {SEALED: {'name': 's1', 'world': 'camp-world', 'lineage': 'main', 'admission': 1, 'context': {'ruleset': 'standard'}}}
COV = {'schema': 'curator-coverage/2', 'session': 's1', 'actor': '001', 'last_step': 40}


def _repo(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / 'k', 'cdda')
    repo.ensure()
    return repo


def _fact(fid: str, *, citations=(F1,), **extra) -> dict:
    return dict(schema='curator-fact/6', record='fact', id=fid, statement_kind='observation',
                tags=['camp'], text=f'Claim {fid}.', scope={}, links=[], citations=list(citations)) | extra


def _article(slug: str, facts: list[str], **extra) -> dict:
    return dict(schema='curator-fact/6', record='article', slug=slug, title=f'Title {slug}',
                lead=f'Lead {slug}.', body=[{'text': f'Body {slug}.', 'facts': list(facts)}],
                tags=['camp'], links=[]) | extra


def _submit(repo: Repository, tmp_path: Path, changes: list[dict], *, name: str = 's1',
            session_kind: str = 'admission', base: str | None = None, **top) -> dict:
    base = base or repo.published()
    folder = tmp_path / 'sub' / name
    folder.mkdir(parents=True, exist_ok=True)
    body = dict(schema='curator-submission/3', base_version=base, summary=name, changes=changes, **top)
    (folder / 'submission.json').write_text(json.dumps(body), encoding='utf-8')
    return gate(repo, folder, session_id=f'sess-{name}', window_frames=FRAMES, coverage=COV,
                session_kind=session_kind, session_labels=LABELS)


def test_global_namespace_keyed_uniqueness_changed_and_atomic_world_article_repair(tmp_path):
    repo = _repo(tmp_path)
    # Seed a keyed state fact + world article citing it.
    v1 = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('rv-batt-12', statement_kind='state', state_key='rv-battery',
                                         binds=['world'], text='RV battery is at 12%.', citations=[F1])},
        {'op': 'add_article', 'article': _article('rv-status', ['rv-batt-12'])},
    ], name='01')
    assert v1['status'] == 'published', v1

    # Global namespace: reusing a state_key as a fact ID or article slug is rejected.
    bad_id = _submit(repo, tmp_path, [{'op': 'add_fact', 'fact': _fact('rv-battery')}], name='02-bad-id')
    assert bad_id['status'] == 'rejected' and 'is not new' in bad_id['diagnostics'][0]
    bad_key = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('other-state', statement_kind='state', state_key='rv-status', binds=['world'])},
    ], name='02-bad-key')
    assert bad_key['status'] == 'rejected' and 'collides' in bad_key['diagnostics'][0]

    # Duplicate active uncontested state_key on same timeline is rejected.
    dup = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('rv-batt-09', statement_kind='state', state_key='rv-battery',
                                         binds=['world'], text='RV battery is at 9%.', citations=[F2])},
    ], name='02-dup')
    assert dup['status'] == 'rejected' and 'duplicate active state_key' in dup['diagnostics'][0]

    # Contested pair on same state_key WITH contradicts link is accepted!
    contested = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('rv-batt-09', statement_kind='state', state_key='rv-battery',
                                         binds=['world'], text='RV battery is at 9%.', citations=[F2],
                                         links=[{'rel': 'contradicts', 'target': 'rv-batt-12'}])},
    ], name='02-contested')
    assert contested['status'] == 'published', contested

    # Restated supersession rejects contested inputs (closing check.py:392-396 hole).
    bad_restate = _submit(repo, tmp_path, [
        {'op': 'supersede_fact', 'ids': ['rv-batt-12'], 'reason_kind': 'restated',
         'fact': _fact('rv-batt-12-clean', statement_kind='state', state_key='rv-battery',
                       binds=['world'], citations=[])},
    ], name='03-restate-contested')
    assert bad_restate['status'] == 'rejected' and 'contested' in bad_restate['diagnostics'][0]

    # `changed` transition without atomic world-article repair is rejected!
    no_repair = _submit(repo, tmp_path, [
        {'op': 'supersede_fact', 'ids': ['rv-batt-12', 'rv-batt-09'], 'reason_kind': 'changed',
         'fact': _fact('rv-batt-00', statement_kind='state', state_key='rv-battery',
                       binds=['world'], text='RV battery is at 0%.', citations=[F3])},
    ], name='03-no-repair')
    assert no_repair['status'] == 'rejected' and 'without repairing citing world article' in no_repair['diagnostics'][0]

    # `changed` transition WITH atomic world-article repair succeeds cleanly!
    repaired = _submit(repo, tmp_path, [
        {'op': 'supersede_fact', 'ids': ['rv-batt-12', 'rv-batt-09'], 'reason_kind': 'changed',
         'fact': _fact('rv-batt-00', statement_kind='state', state_key='rv-battery',
                       binds=['world'], text='RV battery is at 0%.', citations=[F3])},
        {'op': 'edit_article', 'slug': 'rv-status', 'replace_claims': [{
            'index': 0, 'old_text': 'Body rv-status.', 'old_facts': ['rv-batt-12'],
            'text': 'RV battery is now at 0%.', 'facts': ['rv-batt-00'],
        }]},
    ], name='03-repaired')
    assert repaired['status'] == 'published', repaired
    by_id = {r['id']: r for r in repo.facts()}
    assert by_id['rv-batt-12']['lifecycle_state'] == 'ended'
    assert by_id['rv-batt-12']['superseded_reason'] == 'changed'
    assert by_id['rv-batt-12']['valid_to'] == FRAMES[F3]

    # No-silent-omission guard: cannot drop an active world fact from a world article without ending/moving it.
    v_add = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('rv-water-ok', statement_kind='state', state_key='rv-water',
                                         binds=['world'], text='RV tank holds 20L.', citations=[F3])},
        {'op': 'edit_article', 'slug': 'rv-status',
         'add_claims': [{'text': 'RV tank holds 20L.', 'facts': ['rv-water-ok']}]},
    ], name='04-add-water')
    assert v_add['status'] == 'published', v_add
    silent_drop = _submit(repo, tmp_path, [
        {'op': 'edit_article', 'slug': 'rv-status', 'remove_claims': [{
            'index': 1, 'old_text': 'RV tank holds 20L.', 'old_facts': ['rv-water-ok'],
        }]},
    ], name='05-drop')
    assert silent_drop['status'] == 'rejected' and 'silently drops active world fact' in silent_drop['diagnostics'][0]

    # Restoring to v0 still reserves historical state_keys against reuse as fact IDs!
    assert restore(repo, expected_base=repo.published(), target='v0')['status'] == 'published'
    reuse_key = _submit(repo, tmp_path, [{'op': 'add_fact', 'fact': _fact('rv-battery')}], name='06-reuse-key')
    assert reuse_key['status'] == 'rejected' and 'is not new' in reuse_key['diagnostics'][0]


def test_frame_clocks_anchor_forest_synthesis_and_depends_on_acyclicity(tmp_path):
    repo = _repo(tmp_path)
    # Legacy strategy rejected by schema; synthesis without depends_on rejected by schema.
    bad_kind = _submit(repo, tmp_path, [{'op': 'add_fact', 'fact': _fact('bad-strat', statement_kind='strategy')}], name='01-strat')
    assert bad_kind['status'] == 'rejected'
    bad_synth = _submit(repo, tmp_path, [{'op': 'add_fact', 'fact': _fact('bad-synth', statement_kind='synthesis')}], name='01-synth')
    assert bad_synth['status'] == 'rejected'

    # Valid frame_clocks + anchor + depiction_source_id + synthesis with state_key depends_on.
    ok = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('camp-root', statement_kind='state', state_key='campground',
                                         binds=['world'], depiction_source_id=F1, citations=[F1])},
        {'op': 'add_fact', 'fact': _fact('brazier-1', statement_kind='state', state_key='camp-brazier',
                                         anchor='campground', binds=['world'], citations=[F1])},
        {'op': 'add_fact', 'fact': _fact('reserves-1', statement_kind='synthesis', state_key='camp-reserves',
                                         binds=['world'], links=[{'rel': 'depends_on', 'target': 'camp-brazier'}],
                                         citations=[F1])},
    ], name='01-ok', frame_clocks={F1: 'Spring, day 61 8:00 AM'})
    assert ok['status'] == 'published', ok
    assert repo.provenance()['frame_clocks'] == {F1: 'Spring, day 61 8:00 AM'}

    # Conflicting frame_clocks label rejected; identical repeat accepted.
    conflict_clock = _submit(repo, tmp_path, [{'op': 'add_fact', 'fact': _fact('f-c')}],
                             name='02-clock', frame_clocks={F1: 'Spring, day 61 9:00 AM'})
    assert conflict_clock['status'] == 'rejected' and 'conflicts with already-recorded label' in conflict_clock['diagnostics'][0]

    # Anchor cycle rejected.
    cyc_anchor = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('a-1', statement_kind='state', state_key='k-a', anchor='k-b', binds=['world'])},
        {'op': 'add_fact', 'fact': _fact('b-1', statement_kind='state', state_key='k-b', anchor='k-a', binds=['world'])},
    ], name='02-anchor-cyc')
    assert cyc_anchor['status'] == 'rejected' and 'anchor cycle' in cyc_anchor['diagnostics'][0]

    # Ending anchor key does NOT block retirement or flag anchored facts for needs_review (#1021).
    end_anchor = _submit(repo, tmp_path, [
        {'op': 'retire_fact', 'id': 'camp-root', 'reason_kind': 'ended', 'reason': 'Left area.',
         'end': 'transition', 'end_citations': [F2]},
    ], name='02-end-anchor')
    assert end_anchor['status'] == 'published', end_anchor
    brazier = next(f for f in repo.facts() if f['id'] == 'brazier-1')
    assert brazier['needs_review'] is False and brazier['stale_citations'] == []

    # depends_on cycle rejected (#1023).
    cyc_dep = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('d1', links=[{'rel': 'depends_on', 'target': 'd2'}])},
        {'op': 'add_fact', 'fact': _fact('d2', links=[{'rel': 'depends_on', 'target': 'd1'}])},
    ], name='03-dep-cyc')
    assert cyc_dep['status'] == 'rejected' and 'depends_on cycle' in cyc_dep['diagnostics'][0]


def test_hygiene_session_boundaries_safe_merge_invariants_and_worklist(tmp_path):
    repo = _repo(tmp_path)
    seed = _submit(repo, tmp_path, [
        {'op': 'add_fact', 'fact': _fact('w-state', statement_kind='state', state_key='tent-flap',
                                         binds=['world'], text='Tent flap is closed.', citations=[F1])},
        {'op': 'add_fact', 'fact': _fact('g-dup-1', text='Press ? to open keybindings screen.', citations=[F1])},
        {'op': 'add_fact', 'fact': _fact('g-dup-2', text='Press ? to open the keybindings screen.', citations=[F2])},
        {'op': 'add_fact', 'fact': _fact('g-pinned', text='Press o to open doors.', citations=[F1])},
        {'op': 'add_fact', 'fact': _fact('g-pinned-dup', text='Press o to open adjacent doors.', citations=[F2])},
        {'op': 'add_fact', 'fact': _fact('g-reader', statement_kind='inference',
                                         links=[{'rel': 'depends_on', 'target': 'g-pinned'}], citations=[F1])},
        {'op': 'add_article', 'article': _article('controls', ['g-dup-1', 'g-dup-2'])},
    ], name='01-seed')
    assert seed['status'] == 'published', seed

    # Hygiene forbids retiring active world-bound facts and corrected/changed supersession.
    r_world = _submit(repo, tmp_path, [
        {'op': 'retire_fact', 'id': 'w-state', 'reason_kind': 'ended', 'reason': 'No.',
         'end': 'absence', 'end_citations': [F2]},
    ], name='02-h-retire', session_kind='hygiene')
    assert r_world['status'] == 'rejected' and 'hygiene session cannot retire active world-bound facts' in r_world['diagnostics'][0]

    r_corr = _submit(repo, tmp_path, [
        {'op': 'supersede_fact', 'ids': ['g-dup-1'], 'reason_kind': 'corrected',
         'fact': _fact('g-dup-corr', citations=[F3])},
    ], name='02-h-corr', session_kind='hygiene')
    assert r_corr['status'] == 'rejected' and "hygiene session forbids 'corrected'" in r_corr['diagnostics'][0]

    # Hygiene rejects N->1 merge when an inbound fact-ID depends_on reading pin exists (#1023 invariant 4).
    r_pin = _submit(repo, tmp_path, [
        {'op': 'supersede_fact', 'ids': ['g-pinned', 'g-pinned-dup'], 'reason_kind': 'restated',
         'fact': _fact('g-pinned-merged', citations=[])},
    ], name='02-h-pin', session_kind='hygiene')
    assert r_pin['status'] == 'rejected' and 'inbound fact-ID depends_on pin' in r_pin['diagnostics'][0]

    # Hygiene accepts safe N->1 game-wide unkeyed merge + N->1 remap_citations!
    ok_merge = _submit(repo, tmp_path, [
        {'op': 'supersede_fact', 'ids': ['g-dup-1', 'g-dup-2'], 'reason_kind': 'restated',
         'fact': _fact('g-keybindings', text='Press ? to open the keybindings screen.', citations=[])},
        {'op': 'remap_citations', 'from': ['g-dup-1', 'g-dup-2'], 'to': 'g-keybindings', 'in': ['controls']},
    ], name='02-h-merge', session_kind='hygiene')
    assert ok_merge['status'] == 'published', ok_merge
    art = next(a for a in repo.articles() if check.current(a))
    assert art['body'][0]['facts'] == ['g-keybindings']

    # Deterministic hygiene worklist & same-frame cannot-link nogoods.
    recs = repo.records()
    assert [e['state_key'] for e in hygiene.state_key_index(recs, world='camp-world')] == ['tent-flap']
    assert hygiene.lookup_state_keys(recs, 'tent flap', world='camp-world')[0]['state_key'] == 'tent-flap'
    same_frame_recs = [
        _fact('k1', statement_kind='state', state_key='brazier-east', scope={'game': 'cdda', 'world': 'w'},
              text='Metal brazier sits east of the tent.', citations=[F1]) | {'lifecycle_state': 'active', 'seen': FRAMES[F1]},
        _fact('k2', statement_kind='state', state_key='brazier-west', scope={'game': 'cdda', 'world': 'w'},
              text='Metal brazier sits west of the tent.', citations=[F1]) | {'lifecycle_state': 'active', 'seen': FRAMES[F1]},
    ]
    wl = hygiene.worklist(same_frame_recs)
    assert wl['key_alias_candidates'] == []  # same-frame nogood excludes co-cited distinct keys!
    assert wl['duplicate_candidates'] == []
