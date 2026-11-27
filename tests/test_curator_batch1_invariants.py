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

    # N3: Unicode tokenization works on non-Latin scripts without collapsing to empty tokens.
    uni_recs = [
        _fact('u1', text='キャンプの扉は閉じている。', citations=[F1]) | {'lifecycle_state': 'active', 'seen': FRAMES[F1]},
        _fact('u2', text='キャンプの扉は閉じている。', citations=[F2]) | {'lifecycle_state': 'active', 'seen': FRAMES[F2]},
    ]
    assert hygiene.worklist(uni_recs)['duplicate_candidates'][0]['left'] == 'u1'


def test_b1_fork_changed_and_restore_keyed_uniqueness(tmp_path):
    """B1: Pre-change fork keeps keyed uniqueness, supports changed/retire(ended), and restore never wedges key reuse."""
    from tools import knowledge_export

    repo = _repo(tmp_path)
    s_main = 'a' * 32
    s_fork = 'b' * 32
    s_fork2 = 'c' * 32
    m1, m2, m3 = f'{s_main}-1', f'{s_main}-2', f'{s_main}-3'
    fk1 = f'{s_fork}-1'
    fk2 = f'{s_fork2}-1'
    frames = {
        m1: position('main-s1', 5, order_index=1),
        m2: position('main-s1', 20, order_index=1),
        m3: position('main-s1', 35, order_index=1),
        fk1: position('fork-s1', 12, order_index=2),
        fk2: position('fork2-s1', 12, order_index=3),
    }
    labels_main = {s_main: {'name': 'main-s1', 'world': 'w', 'lineage': 'main', 'admission': 1, 'context': {}}}
    labels_fork = {
        s_fork: {
            'name': 'fork-s1', 'world': 'w', 'lineage': 'fork', 'admission': 1, 'context': {},
            'branch': {'parent': 'main', 'fork_at': position('main-s1', 10, order_index=1), 'fork_version': 'v1'},
        },
    }
    labels_fork2 = {
        s_fork2: {
            'name': 'fork2-s1', 'world': 'w', 'lineage': 'fork2', 'admission': 1, 'context': {},
            'branch': {'parent': 'main', 'fork_at': position('main-s1', 10, order_index=1), 'fork_version': 'v1'},
        },
    }

    def run(changes, name, labels, cov_sess, cov_step):
        folder = tmp_path / 'b1' / name
        folder.mkdir(parents=True, exist_ok=True)
        body = dict(schema='curator-submission/3', base_version=repo.published(), summary=name, changes=changes)
        (folder / 'submission.json').write_text(json.dumps(body), encoding='utf-8')
        return gate(repo, folder, session_id=f's-{name}', window_frames=frames,
                    coverage={'schema': 'curator-coverage/2', 'session': cov_sess, 'actor': '001', 'last_step': cov_step},
                    session_kind='admission', session_labels=labels)

    # v1: main adds door-open (key door-k) at step 5.
    assert run([
        {'op': 'add_fact', 'fact': _fact('door-open', statement_kind='state', state_key='door-k',
                                         binds=['world'], text='Door is open.', citations=[m1])},
    ], 'v1', labels_main, 'main-s1', 5)['status'] == 'published'

    # v2: main transitions door-open -> door-closed via changed at step 20.
    assert run([
        {'op': 'supersede_fact', 'ids': ['door-open'], 'reason_kind': 'changed',
         'fact': _fact('door-closed', statement_kind='state', state_key='door-k',
                       binds=['world'], text='Door is closed.', citations=[m2])},
    ], 'v2', labels_main, 'main-s1', 20)['status'] == 'published'

    # Fork branched at step 10 (before m2): adding a fresh reading with same key WITHOUT changed/contradicts MUST fail!
    dup_fork = run([
        {'op': 'add_fact', 'fact': _fact('door-broken', statement_kind='state', state_key='door-k',
                                         binds=['world'], text='Door is broken.', citations=[fk1])},
    ], 'dup-fork', labels_fork, 'fork-s1', 12)
    assert dup_fork['status'] == 'rejected' and 'duplicate active state_key' in dup_fork['diagnostics'][0]

    # Duplicate end on main MUST fail (door-open is already visibly ended on main).
    dup_main_end = run([
        {'op': 'retire_fact', 'id': 'door-open', 'reason_kind': 'ended', 'reason': 'Again.',
         'end': 'absence', 'end_citations': [m3]},
    ], 'dup-main-end', labels_main, 'main-s1', 35)
    assert dup_main_end['status'] == 'rejected' and 'already has a visible end' in dup_main_end['diagnostics'][0]

    # v3: fork transitions door-open -> door-broken via changed!
    fork_changed = run([
        {'op': 'supersede_fact', 'ids': ['door-open'], 'reason_kind': 'changed',
         'fact': _fact('door-broken', statement_kind='state', state_key='door-k',
                       binds=['world'], text='Door is broken.', citations=[fk1])},
    ], 'v3-fork-changed', labels_fork, 'fork-s1', 12)
    assert fork_changed['status'] == 'published', fork_changed

    # v4: fork2 (also branched before m2) retires door-open via ended (combining changed + retired.events)!
    fork2_end = run([
        {'op': 'retire_fact', 'id': 'door-open', 'reason_kind': 'ended', 'reason': 'Door vanished.',
         'end': 'absence', 'end_citations': [fk2]},
    ], 'v4-fork2-end', labels_fork2, 'fork2-s1', 12)
    assert fork2_end['status'] == 'published', fork2_end

    # Verify per-lineage delivery and history across main, fork, and fork2!
    tip = repo.published()
    d_main = knowledge_export.published(repo, tip, world='w', lineage='main')
    d_fork = knowledge_export.published(repo, tip, world='w', lineage='fork')
    d_fork2 = knowledge_export.published(repo, tip, world='w', lineage='fork2')
    assert [f['id'] for f in d_main['facts']] == ['door-closed']
    assert d_main['history']['replaced']['door-open'] == {'reason': 'changed', 'by': ['door-closed']}
    assert [f['id'] for f in d_fork['facts']] == ['door-broken']
    assert d_fork['history']['replaced']['door-open'] == {'reason': 'changed', 'by': ['door-broken']}
    assert d_fork2['facts'] == []
    assert 'door-open' in d_fork2['history']['ended']

    # Same-lineage restore test: restore erasing an active keyed reading allows a fresh post-restore reading!
    repo_r = Repository(tmp_path / 'k-restore', 'cdda')
    repo_r.ensure()
    sr = 'd' * 32
    r1, r2, r3 = f'{sr}-1', f'{sr}-2', f'{sr}-3'
    r_frames = {
        r1: position('r-s1', 2, order_index=1),
        r2: position('r-s1', 5, order_index=1),
        r3: position('r-s1', 12, order_index=1),
    }
    r_labels_1 = {sr: {'name': 'r-s1', 'world': 'w', 'lineage': 'main', 'admission': 1, 'context': {}}}
    f_add1 = tmp_path / 'r-sub1'
    f_add1.mkdir()
    (f_add1 / 'submission.json').write_text(json.dumps({
        'schema': 'curator-submission/3', 'base_version': 'v0', 'summary': 'r1',
        'changes': [{'op': 'add_fact', 'fact': _fact('lamp-on', statement_kind='state', state_key='lamp-k',
                                                     binds=['world'], text='Lamp is on.', citations=[r2])}],
    }))
    assert gate(repo_r, f_add1, session_id='rs1', window_frames=r_frames,
                coverage={'schema': 'curator-coverage/2', 'session': 'r-s1', 'actor': '001', 'last_step': 5},
                session_kind='admission', session_labels=r_labels_1)['status'] == 'published'
    # Restore back to step 2 at step 10 erases step 5 (`lamp-on`); fresh post-restore reading `lamp-off` at step 12 succeeds!
    r_labels_2 = {
        sr: {
            'name': 'r-s1', 'world': 'w', 'lineage': 'main', 'admission': 1, 'context': {},
            'restores': [{
                'lineage': 'main',
                'saved_at': position('r-s1', 2, order_index=1),
                'restored_at': position('r-s1', 10, order_index=1),
                'saved_version': 'v0',
                'restored_version': 'v1',
            }],
        },
    }
    f_add2 = tmp_path / 'r-sub2'
    f_add2.mkdir()
    (f_add2 / 'submission.json').write_text(json.dumps({
        'schema': 'curator-submission/3', 'base_version': 'v1', 'summary': 'r2',
        'changes': [{'op': 'add_fact', 'fact': _fact('lamp-off', statement_kind='state', state_key='lamp-k',
                                                     binds=['world'], text='Lamp is off.', citations=[r3])}],
    }))
    res_restore = gate(repo_r, f_add2, session_id='rs2', window_frames=r_frames,
                       coverage={'schema': 'curator-coverage/2', 'session': 'r-s1', 'actor': '001', 'last_step': 12},
                       session_kind='admission', session_labels=r_labels_2)
    assert res_restore['status'] == 'published', res_restore
    d_restored = knowledge_export.published(repo_r, repo_r.published(), world='w', lineage='main')
    assert [f['id'] for f in d_restored['facts']] == ['lamp-off']
