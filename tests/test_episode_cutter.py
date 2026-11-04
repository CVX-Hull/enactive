"""The episode cutter (ADR-007 level v4, item 1): thumbnails, distances, closure rules and the recorder's frame policy.

Pure software over fixture captures; no provider, game or custodian.
"""
import io

from PIL import Image
import pytest

from tools.episode_cutter import Episode, EpisodeCutter, distance, key_tokens, pick_frames, thumbnail

THETA = 0.1251514705882353


def png(value, size=(64, 40)):
    out = io.BytesIO()
    Image.new('L', size, value).save(out, format='PNG')
    return out.getvalue()


def test_thumbnail_is_32_by_20_greyscale_box_pooled_and_distance_is_a_normalised_mean():
    left = Image.new('L', (64, 40), 0)
    left.paste(255, (0, 0, 32, 40))
    out = io.BytesIO()
    left.save(out, format='PNG')
    thumb = thumbnail(out.getvalue())
    assert len(thumb) == 32 * 20
    # A 2 x 2 box pool of a hard vertical edge is exact: the left half is white and the right half black.
    assert thumb[:16] == bytes([255]) * 16 and thumb[16:32] == bytes(16)
    assert thumbnail(png(0)) == bytes(640) and thumbnail(png(255)) == bytes([255]) * 640
    assert distance(thumbnail(png(0)), thumbnail(png(255))) == 1.0
    assert distance(thumbnail(png(0)), thumbnail(png(0))) == 0.0
    assert distance(thumbnail(png(0)), thumbnail(png(51))) == pytest.approx(51 / 255)
    # Capture sizes need not match: both reduce to the same box.
    assert distance(thumbnail(png(100, (320, 200))), thumbnail(png(100, (64, 40)))) == 0.0


def test_key_tokens_are_generic_and_carry_no_game_vocabulary():
    assert key_tokens([dict(type='key', key='x', modifiers=['SHIFT', 'CTRL']), dict(type='text', text='hi'),
                       dict(type='click', x=3, y=4, button='left'), dict(type='wait', seconds=1)]) \
        == ['key:x+CTRL+SHIFT', 'text:hi', 'click:left@3,4', 'wait']
    assert key_tokens(None) == []


class Log:
    """Operations whose result captures are flat greys; `grey` None is a capture-less input."""
    def __init__(self, theta=THETA, minimum=2, cap=10):
        self.captures = {}
        self.cutter = EpisodeCutter(theta, minimum, cap, lambda source: self.captures[source])
        self.position = 0
        self.closed = []

    def add(self, grey, kind='input', subgoal=None):
        self.position += 1
        source = None
        if grey is not None:
            source = f's{self.position}'
            self.captures[source] = thumbnail(png(grey))
        closed = self.cutter.feed(dict(position=self.position, kind=kind, source_id=source), subgoal)
        self.closed += closed
        return closed

    def spans(self):
        return [(e.first_position, e.last_position, e.inputs, e.closed_by) for e in self.closed]


def test_content_closure_needs_theta_and_m_and_the_crossing_input_starts_the_next_episode():
    log = Log()
    for grey in (0, 0, 0):
        assert log.add(grey) == []
    # d = 100/255 = 0.39 >= theta with three inputs held: the episode ends on the last stable screen (position 3).
    (episode,) = log.add(100)
    assert (episode.first_position, episode.last_position, episode.inputs, episode.closed_by) == (1, 3, 3, 'content')
    assert log.cutter.open_first == 4 and log.cutter.open_inputs == 1 and log.cutter.next_position == 5
    # A crossing right after a start holds one input only (< m = 2): no closure, the change stays inside.
    assert log.add(250) == []
    assert log.cutter.open_first == 4 and log.cutter.open_inputs == 2


def test_a_distance_just_under_theta_does_not_close_and_exactly_theta_does():
    log = Log(theta=0.2)
    log.add(0); log.add(0); log.add(0)
    assert log.add(50) == []                    # 50 / 255 = 0.196 < 0.2
    log = Log(theta=0.2)
    log.add(0); log.add(0); log.add(0)
    assert len(log.add(51)) == 1                # 51 / 255 = 0.2 exactly
    assert log.spans() == [(1, 3, 3, 'content')]


def test_the_cap_closes_at_c_inputs_and_observes_do_not_count():
    log = Log(cap=3)
    log.add(10, kind='observe')
    for _ in range(2):
        assert log.add(10) == []
    (episode,) = log.add(10)
    assert (episode.first_position, episode.last_position, episode.inputs, episode.closed_by) == (1, 4, 3, 'cap')
    assert log.add(10, kind='observe') == [] and log.cutter.open_first == 5


def test_an_input_without_a_result_capture_has_no_distance_and_cannot_close_an_episode():
    log = Log()
    log.add(0); log.add(0); log.add(0)
    assert log.add(None) == []
    assert log.closed == [] and log.cutter.open_inputs == 4
    # The next distance is against the previous input that has a capture, skipping the capture-less one.
    (episode,) = log.add(255)
    assert (episode.first_position, episode.last_position, episode.closed_by) == (1, 4, 'content')
    assert episode.distances[4] is None and episode.distances == {1: None, 2: 0.0, 3: 0.0, 4: None}


def test_the_first_input_has_no_distance_and_an_observe_never_closes():
    log = Log()
    assert log.add(0) == [] and log.add(255, kind='observe') == [] and log.add(0) == []
    assert log.closed == [] and log.cutter.next_position == 4


def test_session_edge_flush_closes_the_partial_episode_once_whatever_its_length():
    log = Log()
    log.add(0)
    tail = log.cutter.flush()
    assert (tail.first_position, tail.last_position, tail.inputs, tail.closed_by) == (1, 1, 1, 'edge')
    assert log.cutter.flush() is None
    # A tail with no input (only observes, or the handoff itself) is not an episode: it is dropped, not recorded.
    log = Log()
    log.add(None, kind='observe')
    assert log.cutter.flush() is None and log.cutter.open_first is None and log.cutter.next_position == 2
    log = Log(cap=2)
    log.add(0); log.add(0)
    log.add(None, kind='handoff')
    assert [e.closed_by for e in log.closed] == ['cap'] and log.cutter.flush() is None


def test_boundaries_are_frozen_once_returned_and_the_next_episode_starts_after_the_furthest_cut():
    log = Log()
    for grey in (0, 0, 100, 100, 100, 250):
        log.add(grey)
    first, second = log.closed
    assert (first.first_position, first.last_position) == (1, 2) and (second.first_position, second.last_position) == (3, 5)
    # No later input changes an episode already returned; the open one starts right after the last cut.
    log.add(250)
    assert log.spans() == [(1, 2, 2, 'content'), (3, 5, 3, 'content')] and log.cutter.open_first == 6


def test_the_subgoal_current_when_an_episode_opens_is_recorded_not_the_one_at_its_close():
    log = Log(cap=2)
    log.add(0, subgoal='first')
    (closed,) = log.add(0, subgoal='second')
    assert closed.subgoal_id == 'first'
    log.add(0, subgoal='third')
    assert log.cutter.flush().subgoal_id == 'third'


def test_the_cutter_takes_the_log_in_order_and_refuses_bad_parameters():
    log = Log()
    log.add(0)
    with pytest.raises(ValueError, match='in order'):
        log.cutter.feed(dict(position=3, kind='input', source_id=None), None)
    for args in ((0.0, 2, 10), (1.0, 2, 10), (1, 2, 10), (THETA, 0, 10), (THETA, 11, 10), (THETA, 2, 1001)):
        with pytest.raises(ValueError):
            EpisodeCutter(*args, lambda s: b'')


def episode(count, distances, closed_by='cap'):
    frames = tuple((i + 1, f's{i + 1}') for i in range(count))
    return Episode(1, count, count, closed_by, None, {i + 1: d for i, d in enumerate(distances)}, frames)


def test_frame_policy_shows_all_frames_up_to_six_and_always_the_last():
    assert [p for p, _, _ in pick_frames(episode(6, [.1] * 6))] == [1, 2, 3, 4, 5, 6]
    assert pick_frames(episode(1, [None])) == [(1, 's1', 'last')]
    assert pick_frames(episode(0, [])) == []


def test_frame_policy_keeps_the_last_then_the_largest_distances_in_capture_order():
    distances = [None, .01, .50, .02, .40, .03, .60, .04, .30, .05]
    chosen = pick_frames(episode(10, distances))
    # The last, then the five largest distances of the others: 0.60, 0.50, 0.40, 0.30 and 0.04.
    positions = [p for p, _, _ in chosen]
    assert positions == sorted(positions) and len(positions) == 6 and positions[-1] == 10
    assert {3, 5, 7, 9} <= set(positions)                     # 0.50, 0.40, 0.60, 0.30
    assert chosen[-1][2] == 'last' and all(role == 'in-episode' for _, _, role in chosen[:-1])
    # The fifth non-last frame is the next-largest distance, 0.04 at position 8.
    assert positions == [3, 5, 7, 8, 9, 10]


def test_frame_policy_breaks_ties_to_the_earlier_frame_and_chooses_a_frame_without_distance_last():
    chosen = pick_frames(episode(8, [None, .2, .2, .2, .2, .2, .2, .2]))
    # Seven non-last frames compete for five slots: five of the equal 0.2 distances, earliest first; the
    # distance-less frame at position 1 is the last choice and so is left out.
    assert [p for p, _, _ in chosen] == [2, 3, 4, 5, 6, 8]
    assert 1 not in [p for p, _, _ in chosen]
