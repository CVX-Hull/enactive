"""Blind intent-audit bundling and summary on synthetic runs of the current contracts."""
import json
from pathlib import Path
import sqlite3

import pytest

from stage_support import (ACTOR, LEVEL_READER, SESSION, PlayerStore, correction_record, level_pass, make_run, png, source_metadata, work_record)
from tools import intent_audit as audit

CRITERIA = dict(schema='intent-audit-criteria/1', min_auditable=3, min_kappa=.4, min_accuracy=.6, max_unverifiable_share=.5)


def write(path, text):
    path.write_text(text)
    return path


@pytest.fixture
def frozen(tmp_path):
    return (write(tmp_path / 'context.txt', 'Frozen guide and assignment.'), write(tmp_path / 'instructions.md', 'Answer two questions.'),
            write(tmp_path / 'criteria.json', json.dumps(CRITERIA)))


def store_with_two_replaces(tmp_path, cited='3', old_contract=False):
    store = PlayerStore(tmp_path / 'player.sqlite3')
    first, = store.commit(LEVEL_READER, 'player_level_replace', 'replace', [work_record('Find the door', position=4)])
    cited_source = f'{SESSION}-{cited}'
    second = store.commit(LEVEL_READER, 'player_level_replace', 'replace', [
        work_record('Open the door', position=9, sources=[cited_source]),
        correction_record('The door was found', first['id'], 'achieved', position=9)], sources=[(source_metadata(int(cited)), png())])
    if old_contract:
        store.commit(LEVEL_READER, 'player_level_replace', 'replace', [work_record('Old interface', contract='player-level/3')])
    store.commit(LEVEL_READER, 'player_level_keep', 'keep', [])
    return store.path, first, second


def prepared(tmp_path, frozen, **options):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')], inputs=15)
    store, first, second = store_with_two_replaces(tmp_path, **options)
    out = tmp_path / 'audit'
    count = audit.prepare(out, [run], str(store), frozen[0], frozen[1])
    return out, count, first, second


def test_prepare_writes_one_blind_packet_per_committed_replace_of_the_current_contract(tmp_path, frozen):
    out, count, first, second = prepared(tmp_path, frozen)
    assert count == 2
    key = json.loads((audit.private(out) / 'key.json').read_text())
    assert sorted(v['record_id'] for v in key['packets'].values()) == sorted([first['id'], second[0]['id']])
    assert key['inputs'] == dict(context_sha256=audit.sha256(frozen[0]), instructions_sha256=audit.sha256(frozen[1]),
                                 code_sha256=audit.sha256(Path(audit.__file__)), recent_frames=10, level_contract='player-level/5',
                                 commit_tools=['player_level_keep', 'player_level_replace', 'player_level_close'], runs_without_store=[])
    by_record = {v['record_id']: k for k, v in key['packets'].items()}
    packet = out / 'packets' / by_record[second[0]['id']]
    value = json.loads((packet / 'packet.json').read_text())
    assert value['schema'] == 'intent-audit-packet/1' and value['audit_id'] == by_record[second[0]['id']]
    assert value['proposal']['subgoal'] == 'Open the door'
    assert value['proposal']['decisions_in_same_commit'] == [dict(decision='achieved', reason='The door was found')]
    assert [e['position'] for e in value['input_log']] == list(range(1, 10))
    assert (packet / 'context.txt').read_text() == 'Frozen guide and assignment.' and (packet / 'instructions.md').read_text() == 'Answer two questions.'


@pytest.mark.parametrize('old', ['record', 'receipt'])
def test_prepare_refuses_mixed_old_level_contracts_before_writing_packets(tmp_path, frozen, old):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')], inputs=15)
    store, _, _ = store_with_two_replaces(tmp_path, old_contract=old == 'record')
    if old == 'receipt':
        with sqlite3.connect(store) as db:
            row, encoded = db.execute('SELECT rowid,result FROM service_operations WHERE result IS NOT NULL LIMIT 1').fetchone()
            result = json.loads(encoded)
            result['schema'] = 'player-level-commit/4'
            db.execute('UPDATE service_operations SET result=? WHERE rowid=?', (json.dumps(result), row))
    out = tmp_path / 'audit'
    with pytest.raises(audit.UnsupportedTrace, match='unsupported'):
        audit.prepare(out, [run], str(store), frozen[0], frozen[1])
    assert not out.exists() and not audit.private(out).exists()


def test_the_session_id_never_reaches_the_auditors(tmp_path, frozen):
    out, _, _, _ = prepared(tmp_path, frozen)
    for path in (out).rglob('*'):
        assert SESSION not in path.name
        if path.is_file() and path.suffix in ('.json', '.txt', '.md'):
            assert SESSION not in path.read_text()
    # The key lives beside the audited directory, never inside it.
    assert not str(audit.private(out)).startswith(str(out) + '/')
    assert audit.private(out).is_dir() and (audit.private(out) / 'key.json').is_file()


def test_the_frames_are_the_most_recent_before_the_bound_plus_every_cited_source(tmp_path, frozen):
    out, _, _, second = prepared(tmp_path, frozen, cited='2')
    key = json.loads((audit.private(out) / 'key.json').read_text())['packets']
    audit_id = next(k for k, v in key.items() if v['record_id'] == second[0]['id'])
    value = json.loads((out / 'packets' / audit_id / 'packet.json').read_text())
    # Position 9: frames 1..9; the 10 most recent are all of them, and the cited frame is among them once.
    assert len(value['frames']) == 9 and len(set(value['frames'])) == 9
    pngs = sorted(p.name for p in (out / 'packets' / audit_id).glob('*.png'))
    assert pngs == sorted(f'{f}.png' for f in value['frames'])
    shorter = tmp_path / 'short'
    run = tmp_path / 'run-1'
    audit.prepare(shorter, [run], str(tmp_path / 'player.sqlite3'), frozen[0], frozen[1], recent_frames=3)
    counts = sorted(len(json.loads((p / 'packet.json').read_text())['frames']) for p in (shorter / 'packets').iterdir())
    # Three recent frames, plus the cited frame 2 for the second packet.
    assert counts == [3, 4]


def test_a_frozen_file_that_holds_the_session_id_is_refused_and_nothing_is_written(tmp_path, frozen):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')])
    store, _, _ = store_with_two_replaces(tmp_path)
    leaking = write(tmp_path / 'leaking.txt', f'The run is {SESSION}.')
    out = tmp_path / 'audit'
    with pytest.raises(ValueError, match='contains the id'):
        audit.prepare(out, [run], str(store), leaking, frozen[1])
    assert not out.exists() and not audit.private(out).exists()


def test_a_template_that_matches_no_store_is_an_error_and_leaves_nothing_behind(tmp_path, frozen):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')])
    out = tmp_path / 'audit'
    with pytest.raises(ValueError, match='matches no retained store'):
        audit.prepare(out, [run], str(tmp_path / 'absent-{run}.sqlite3'), frozen[0], frozen[1])
    assert not out.exists() and not audit.private(out).exists()


def test_a_run_without_a_store_among_others_is_named_in_the_key(tmp_path, frozen):
    present = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')], inputs=15)
    absent = make_run(tmp_path, 'run-0', [level_pass(1, 'commit')])
    store, _, _ = store_with_two_replaces(tmp_path)
    out = tmp_path / 'audit'
    template = str(tmp_path / '{run}.sqlite3')
    store.rename(tmp_path / 'run-1.sqlite3')
    assert audit.prepare(out, [absent, present], template, frozen[0], frozen[1]) == 2
    assert json.loads((audit.private(out) / 'key.json').read_text())['inputs']['runs_without_store'] == ['run-0']


def test_prepare_never_overwrites_a_directory_and_validates_before_creating_any(tmp_path, frozen):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')], inputs=15)
    store, _, _ = store_with_two_replaces(tmp_path)
    out = tmp_path / 'audit'
    audit.private(out).mkdir()
    with pytest.raises(FileExistsError):
        audit.prepare(out, [run], str(store), frozen[0], frozen[1])
    assert not out.exists()
    with pytest.raises(ValueError, match='positive integer'):
        audit.prepare(tmp_path / 'other', [run], str(store), frozen[0], frozen[1], recent_frames=0)
    with pytest.raises(FileNotFoundError):
        audit.prepare(tmp_path / 'third', [run], str(store), tmp_path / 'absent.txt', frozen[1])
    (run / 'sources' / f'{SESSION}-3.png').unlink()
    with pytest.raises(FileNotFoundError, match='not retained'):
        audit.prepare(tmp_path / 'fourth', [run], str(store), frozen[0], frozen[1])
    assert not (tmp_path / 'fourth').exists() and not audit.private(tmp_path / 'fourth').exists()


def test_the_frozen_files_are_copied_byte_for_byte(tmp_path, frozen):
    context = tmp_path / 'context.bin'
    context.write_bytes(b'Guide\r\nwith CRLF and \xff\xfe bytes\r\n')
    out, _, _, _ = prepared(tmp_path, (context, frozen[1], frozen[2]))
    for packet in (out / 'packets').iterdir():
        assert (packet / 'context.txt').read_bytes() == context.read_bytes()


def test_a_session_id_cited_from_an_earlier_session_is_blinded_consistently(tmp_path, frozen):
    earlier = 'd' * 32
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')], inputs=15)
    store = PlayerStore(tmp_path / 'player.sqlite3')
    metadata = [dict(source_metadata(n), source_id=f'{earlier}-{n}', session=earlier) for n in (5, 7)] + [source_metadata(3)]
    # The subgoal's own text names the earlier frame too, so one placeholder must serve the list and the prose.
    first, = store.commit(LEVEL_READER, 'player_level_replace', 'replace', [work_record(f'Resume from {earlier}-5', position=9,
        sources=[m['source_id'] for m in metadata])], sources=[(m, png()) for m in metadata])
    out = tmp_path / 'audit'
    assert audit.prepare(out, [run], str(store.path), frozen[0], frozen[1]) == 1
    (packet,) = (out / 'packets').iterdir()
    for path in out.rglob('*'):
        assert SESSION not in path.name and earlier not in path.name
        if path.is_file() and path.suffix in ('.json', '.txt', '.md'):
            assert SESSION not in path.read_text() and earlier not in path.read_text()
    value = json.loads((packet / 'packet.json').read_text())
    # The audited session becomes the audit id; the earlier one a placeholder that is the same for each of its citations.
    assert value['cited_sources'] == ['other-session-1-5', 'other-session-1-7', f'{packet.name}-3']
    assert value['proposal']['subgoal'] == 'Resume from other-session-1-5'
    key_text = (audit.private(out) / 'key.json').read_text()
    assert json.loads(key_text)['packets'][packet.name]['record_id'] == first['id'] and earlier not in key_text


def test_the_blinder_names_every_known_session_and_every_source_id_and_nothing_else():
    other, third, record = 'e' * 32, 'f' * 32, '0123456789abcdef' * 2
    blind = audit.Blinder(SESSION, 'abc123', {SESSION, other})
    value = dict(a=f'see {other}-12 and {SESSION}-3', b=[f'{third}-4', f'{third}-9', other], c=5, d=None, e=record)
    assert blind(value) == dict(a='see other-session-1-12 and abc123-3', b=['other-session-2-4', 'other-session-2-9', 'other-session-1'],
                                c=5, d=None, e=record)
    # A session id inside a source id is blinded even when it was never named; a bare id only when it is known.
    assert audit.Blinder(SESSION, 'zz', set()).text(f'{third}-1 {SESSION}') == f'other-session-1-1 {SESSION}'


def test_a_run_of_another_session_version_or_a_store_of_another_version_is_unsupported(tmp_path, frozen):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')])
    import sqlite3
    db = sqlite3.connect(run / 'session.sqlite3')
    db.execute('PRAGMA user_version=2')
    db.close()
    with pytest.raises(ValueError, match='version'):
        audit.prepare(tmp_path / 'a', [run], str(tmp_path / 'p.sqlite3'), frozen[0], frozen[1])
    run = make_run(tmp_path, 'run-2', [level_pass(1, 'commit')])
    stale = tmp_path / 'stale.sqlite3'
    db = sqlite3.connect(stale)
    db.execute('CREATE TABLE metadata (schema TEXT)')
    db.close()
    with pytest.raises(audit.UnsupportedTrace, match='player-memory/1'):
        audit.prepare(tmp_path / 'b', [run], str(stale), frozen[0], frozen[1])


# ---------------------------------------------------------------- labels

@pytest.mark.parametrize('premises,fit,expected', [
    ('shown', 'plausible', 'accurate'), ('shown', 'unclear', 'partly accurate'), ('shown', 'implausible', 'inaccurate'),
    ('contradicted', 'plausible', 'inaccurate'), ('contradicted', 'unclear', 'inaccurate'), ('contradicted', 'implausible', 'inaccurate'),
    ('undecidable', 'plausible', 'partly accurate'), ('undecidable', 'unclear', 'unverifiable'), ('undecidable', 'implausible', 'inaccurate'),
])
def test_the_frozen_label_table_is_total(premises, fit, expected):
    assert audit.label(premises, fit) == expected


@pytest.mark.parametrize('premises,fit', [('maybe', 'plausible'), ('shown', 'fine'), (None, None)])
def test_an_unknown_answer_is_refused(premises, fit):
    with pytest.raises(ValueError, match='Unknown'):
        audit.label(premises, fit)


def labelled(tmp_path, answers):
    """A packets directory and its private labels: `answers` maps audit id to {auditor: (premises, fit)}."""
    out = tmp_path / 'audit'
    (out / 'packets').mkdir(parents=True)
    (audit.private(out) / 'labels').mkdir(parents=True)
    for identity, by_auditor in answers.items():
        (out / 'packets' / identity).mkdir()
        for who, (premises, fit) in by_auditor.items():
            (audit.private(out) / 'labels' / f'{identity}.{who}.json').write_text(json.dumps(dict(premises=premises, fit=fit)))
    return out


GOOD, PARTLY, BAD, NONE = ('shown', 'plausible'), ('shown', 'unclear'), ('shown', 'implausible'), ('undecidable', 'unclear')


def test_agreeing_auditors_give_an_ok_reading_above_the_accuracy_floor(tmp_path):
    answers = {f'p{i}': dict(a=GOOD, b=GOOD) for i in range(4)} | {'p4': dict(a=BAD, b=BAD)}
    value = audit.summarize(labelled(tmp_path, answers), CRITERIA)
    assert value['counts'] == {'accurate': 4, 'partly accurate': 0, 'inaccurate': 1, 'unverifiable': 0}
    assert value['accuracy'] == pytest.approx(.8) and value['strict_accuracy'] == pytest.approx(.8) and value['kappa_ab'] == 1.0
    assert value['reading'] == 'ok'


def test_a_third_auditor_resolves_only_a_disagreement(tmp_path):
    answers = {'p0': dict(a=GOOD, b=GOOD, c=BAD), 'p1': dict(a=GOOD, b=BAD, c=PARTLY), 'p2': dict(a=BAD, b=BAD), 'p3': dict(a=GOOD, b=GOOD)}
    value = audit.summarize(labelled(tmp_path, answers), CRITERIA)
    assert value['resolved'] == {'p0': 'accurate', 'p1': 'partly accurate', 'p2': 'inaccurate', 'p3': 'accurate'}
    assert value['kappa_ab'] == pytest.approx(.5)


def test_the_readings_inconclusive_unreliable_and_below_floor(tmp_path):
    few = audit.summarize(labelled(tmp_path, {'p0': dict(a=GOOD, b=GOOD)}), CRITERIA)
    assert few['reading'] == 'inconclusive'
    unverifiable = {f'q{i}': dict(a=NONE, b=NONE) for i in range(3)} | {f'r{i}': dict(a=GOOD, b=GOOD) for i in range(3)}
    assert audit.summarize(labelled(_fresh(tmp_path, 'other'), unverifiable), dict(CRITERIA, max_unverifiable_share=.4))['reading'] == 'inconclusive'
    assert audit.summarize(labelled(_fresh(tmp_path, 'x'), unverifiable), CRITERIA)['reading'] != 'inconclusive'
    disagreeing = {f'p{i}': dict(a=GOOD if i % 2 else BAD, b=BAD if i % 2 else GOOD, c=GOOD) for i in range(4)}
    assert audit.summarize(labelled(_fresh(tmp_path, 'y'), disagreeing), CRITERIA)['reading'] == 'unreliable'
    low = {f'p{i}': dict(a=BAD, b=BAD) for i in range(4)} | {'p4': dict(a=GOOD, b=GOOD)}
    assert audit.summarize(labelled(_fresh(tmp_path, 'z'), low), CRITERIA)['reading'] == 'below floor'


def _fresh(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
    return path


def test_a_missing_label_is_an_error_not_a_default(tmp_path):
    out = labelled(tmp_path, {'p0': dict(a=GOOD), 'p1': dict(a=GOOD, b=GOOD)})
    with pytest.raises(ValueError, match=r'Missing label p0\.b\.json'):
        audit.summarize(out, CRITERIA)
    out = labelled(_fresh(tmp_path, 'n'), {'p0': dict(a=GOOD, b=BAD)})
    with pytest.raises(ValueError, match=r'Missing label p0\.c\.json'):
        audit.summarize(out, CRITERIA)


def test_the_criteria_are_closed_and_typed(tmp_path):
    for changes in (dict(schema='intent-audit-criteria/0'), dict(min_kappa='.4'), dict(extra=1)):
        path = tmp_path / 'c.json'
        path.write_text(json.dumps(dict(CRITERIA, **changes)))
        with pytest.raises(audit.UnsupportedTrace):
            audit.load_criteria(path)
    path.write_text(json.dumps({k: v for k, v in CRITERIA.items() if k != 'min_accuracy'}))
    with pytest.raises(audit.UnsupportedTrace, match='min_accuracy'):
        audit.load_criteria(path)


def test_summary_is_written_once_with_the_tool_digest_and_stray_entries_are_not_packets(tmp_path, frozen, capsys):
    out = labelled(tmp_path, {f'p{i}': dict(a=GOOD, b=GOOD) for i in range(3)})
    (out / 'packets' / '.DS_Store').write_text('noise')
    (out / 'packets' / 'notes.txt').write_text('stray')
    value = audit.summarize(out, CRITERIA)
    assert value['records'] == 3 and sorted(value['resolved']) == ['p0', 'p1', 'p2']
    assert audit.main(['summarize', str(out), '--criteria', str(frozen[2])]) == 0
    summary = json.loads((audit.private(out) / 'summary.json').read_text())
    assert summary['code_sha256'] == audit.sha256(Path(audit.__file__))
    assert audit.main(['summarize', str(out), '--criteria', str(frozen[2])]) == 1
    assert 'failed' in capsys.readouterr().err


def test_a_session_store_of_another_version_exits_two(tmp_path, frozen, capsys):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')])
    db = sqlite3.connect(run / 'session.sqlite3')
    db.execute('PRAGMA user_version=2')
    db.close()
    assert audit.main(['prepare', str(tmp_path / 'audit'), str(run), '--store-template', str(tmp_path / 'p.sqlite3'),
                       '--context', str(frozen[0]), '--instructions', str(frozen[1])]) == 2
    assert 'unsupported' in capsys.readouterr().err and not (tmp_path / 'audit').exists()


def test_the_commands_prepare_then_summarize(tmp_path, frozen, capsys):
    run = make_run(tmp_path, 'run-1', [level_pass(1, 'commit')], inputs=15)
    store, _, _ = store_with_two_replaces(tmp_path)
    out = tmp_path / 'audit'
    assert audit.main(['prepare', str(out), str(run), '--store-template', str(store), '--context', str(frozen[0]),
                       '--instructions', str(frozen[1])]) == 0
    assert capsys.readouterr().out.strip() == '2 packets'
    for packet in (out / 'packets').iterdir():
        for who in 'ab':
            (audit.private(out) / 'labels' / f'{packet.name}.{who}.json').write_text(json.dumps(dict(premises='shown', fit='plausible')))
    assert audit.main(['summarize', str(out), '--criteria', str(frozen[2])]) == 0
    summary = json.loads((audit.private(out) / 'summary.json').read_text())
    assert summary['criteria_sha256'] == audit.sha256(frozen[2]) and summary['reading'] == 'inconclusive' and summary['records'] == 2
    assert audit.main(['summarize', str(out), '--criteria', str(tmp_path / 'absent.json')]) == 1
    bad = write(tmp_path / 'bad.json', json.dumps(dict(CRITERIA, schema='x')))
    assert audit.main(['summarize', str(out), '--criteria', str(bad)]) == 2
