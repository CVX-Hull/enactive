"""The #490 recall check: the fixed candidate rule and the captured test, on synthetic hashes and labels."""
import pytest

from tools import probe_validation as validation

FULL = (1 << 256) - 1


def flip(base: int, bits: int) -> int:
    """`base` with its lowest `bits` bits inverted: exactly `bits` bits away."""
    return base ^ ((1 << bits) - 1)


def test_a_new_screen_after_a_boundary_matching_an_earlier_chunk_is_a_candidate():
    menu, field = 0, FULL                  # two screens far apart (256 bits)
    hashes = {'s-1': field, 's-2': menu, 's-3': field, 's-4': flip(menu, 10), 's-5': field, 's-6': flip(menu, 40)}
    chunks = [('r-001', 'r', ['s-1', 's-2']), ('r-002', 'r', ['s-3', 's-4', 's-5', 's-6'])]
    found = validation.find_candidates(chunks, hashes)
    # s-4 re-opens the earlier menu (10 bits). s-5, back to the main view, also matches an earlier
    # frame: the rule keeps such pairs and the blinded judge rejects mere "same view" matches.
    # s-6 is a new screen but 40 bits from anything earlier.
    assert [(c['later'], c['earlier'], c['distance']) for c in found] == [('s-4', 's-2', 10), ('s-5', 's-1', 0)]


def test_the_first_chunk_and_screens_that_did_not_change_are_never_candidates():
    hashes = {'s-1': 0, 's-2': FULL, 's-3': flip(FULL, 3), 's-4': flip(FULL, 5)}
    chunks = [('r-001', 'r', ['s-1', 's-2']), ('r-002', 'r', ['s-3', 's-4'])]
    # s-3 starts its chunk (no previous frame in the chunk); s-4 differs from s-3 by too little.
    assert validation.find_candidates(chunks, hashes) == []


def test_one_reopened_screen_counts_once_within_the_cluster():
    menu, field = 0, FULL
    later = ['s-10', 's-11', 's-12', 's-13']
    hashes = {'s-1': field, 's-2': menu, 's-10': field, 's-11': flip(menu, 2), 's-12': field, 's-13': flip(menu, 3)}
    found = validation.find_candidates([('r-001', 'r', ['s-1', 's-2']), ('r-002', 'r', later)], hashes)
    # s-13 re-opens the same earlier menu within the cluster and is dropped; s-12 matches another
    # earlier frame (the main view) and is kept.
    assert [c['later'] for c in found] == ['s-11', 's-12']


def ledger(events):
    return {'r-001': [dict(type='fact', id='F1', statement='s', category='item', observed='x-5', stored=None),
                      dict(type='end')],
            'r-002': [*events, dict(type='end')]}


@pytest.mark.parametrize('event, expected', [
    (dict(type='event', fact='F1', event='rediscovered', frame='x-110'), True),
    (dict(type='event', fact='F1', event='needed', frame='x-90'), True),
    (dict(type='event', fact='F1', event='used', frame='x-100'), False),        # not a need
    (dict(type='event', fact='F1', event='needed', frame='x-130'), False),      # outside the window
    (dict(type='event', fact='F1', event='needed', frame='y-100'), False),      # another session
    (dict(type='event', fact='F9', event='needed', frame='x-100'), False),      # not an earlier fact
])
def test_captured_needs_a_nearby_need_on_an_earlier_fact(event, expected):
    pair = dict(later_chunk='r-002', later='x-100')
    assert validation.captured(pair, ledger([event]), ['r-001', 'r-002']) is expected


def test_held_out_lineages_are_refused(monkeypatch):
    monkeypatch.setitem(validation.LINEAGES, 'lh1', ['lh1-001'])
    with pytest.raises(SystemExit, match='held-out'):
        validation.lineage_runs()
