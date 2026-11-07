"""CDDA evaluation binding: readers over pasted text crops, ladder over synthetic histories."""
from pathlib import Path
import tempfile
import time
import unittest

import numpy as np
from PIL import Image

from harness.evaluation.cdda import CddaBinding
from harness.evaluation.cdda import readers as rd
from harness.evaluation.cdda.atlas import Atlas
from harness.evaluation.core.binding import FrameReading, Vital

FIXTURES = Path(__file__).parent / 'fixtures' / 'evaluation' / 'cdda'
# Fixtures are crops of text regions; each is pasted back at its original pixel position.
POSITIONS = {'death_dialog': (324, 64), 'main_menu': (0, 368)}
BINDING = CddaBinding()
DAY = 86400


def synth(*names, edit=None) -> Path:
    """A 960x640 frame holding the named crops, optionally edited as an RGB array."""
    canvas = Image.new('RGB', (960, 640))
    for name in names:
        canvas.paste(Image.open(FIXTURES / f'{name}.png'), POSITIONS.get(name, (616, 0)))
    if edit is not None:
        array = np.array(canvas)
        edit(array)
        canvas = Image.fromarray(array)
    handle = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    handle.close()
    canvas.save(handle.name)
    return Path(handle.name)


def read(*names, edit=None) -> FrameReading:
    path = synth(*names, edit=edit)
    try:
        return BINDING.read_frame(path)
    finally:
        path.unlink()


def vital(frame: FrameReading, name: str, scope: str = 'whole') -> Vital | None:
    return next((v for v in frame.vitals if v.name == name and v.scope == scope), None)


def reading(frame: FrameReading, name: str):
    return next(r for r in frame.readings if r.reader == name)


def at(season: int, day: int, hour: int = 8, minute: int = 0, second: int = 0) -> int:
    return ((season * rd.SEASON_DAYS + day - 1) * DAY) + hour * 3600 + minute * 60 + second


def frame(mode='in_play', t=None, **needs) -> FrameReading:
    return FrameReading(mode, t, None, tuple(Vital(n, 'whole', v, False) for n, v in needs.items()), None, None, mode == 'dead', ())


class AtlasTests(unittest.TestCase):
    def test_covers_printable_ascii_and_frame_learned_glyphs(self):
        atlas = Atlas.load()
        self.assertEqual(set(atlas.characters()), {chr(c) for c in range(33, 127)})

    def test_blank_is_not_a_glyph(self):
        self.assertNotIn(bytes(16), Atlas.load().glyphs)


class ClockTests(unittest.TestCase):
    def test_reads_date_and_time(self):
        frame_ = read('sidebar_calm')
        self.assertEqual(frame_.game_time, at(0, 61, 8, 5, 16))
        self.assertEqual(reading(frame_, 'game_time').confidence, 0.99)

    def test_two_digit_hour_has_no_space_before_meridiem(self):
        self.assertEqual(read('sidebar_two_digit_hour').game_time, at(0, 61, 10, 5, 14))

    def test_winter_start(self):
        self.assertEqual(read('sidebar_winter_day1').game_time, at(3, 1, 8))

    def test_parse_rolls_over_days_and_seasons(self):
        p = rd.parse_clock
        self.assertEqual(p('Spring, day 61', '11:59:59 PM') + 1, p('Spring, day 62', '12:00:00 AM'))
        self.assertEqual(p('Spring, day 91', '11:59:59PM') + 1, p('Summer, day 1', '12:00:00AM'))
        self.assertEqual(p('Autumn, day 91', '11:59:59 PM') + 1, p('Winter, day 1', '12:00:00 AM'))
        self.assertEqual(p('Spring, day 1', '12:00:00 PM'), 12 * 3600)
        self.assertEqual(p('Spring, day 1', '12:30:00 AM'), 1800)

    def test_year_turn_is_not_hidden_inside_one_frame(self):
        winter_end, spring_start = rd.parse_clock('Winter, day 91', '11:59:59 PM'), rd.parse_clock('Spring, day 1', '12:00:00 AM')
        self.assertEqual(winter_end + 1 - rd.YEAR_SECONDS, spring_start)

    def test_year_field_is_honoured(self):
        self.assertEqual(rd.parse_clock('Year 2, Spring, day 1', '12:00:00 AM'), rd.YEAR_SECONDS)

    def test_parsing_does_not_depend_on_plausibility(self):
        # A frame is parsed alone: the same text gives the same seconds wherever it falls in a run.
        self.assertEqual(rd.parse_clock('Summer, day 3', '1:02:03 AM'), at(1, 3, 1, 2, 3))

    def test_malformed_text_is_rejected(self):
        for date, clock in (('Spring, day 0', '8:00:00 AM'), ('Spring, day 61', '13:00:00 AM'), ('Fall, day 1', '8:00:00 AM'),
                            ('Spring, day 61', '8:61:00 AM'), ('Spring, day 6', '8:00:00'), ('', '')):
            self.assertIsNone(rd.parse_clock(date, clock), (date, clock))

    def test_unknown_glyph_in_a_required_field_abstains(self):
        def smudge(array):
            array[16 * 16 + 4:16 * 16 + 12, 616 + 11 * 8 + 1:616 + 11 * 8 + 7] = (150, 150, 150)  # a block where a digit sits
        frame_ = read('sidebar_calm', edit=smudge)
        self.assertIsNone(frame_.game_time)
        self.assertEqual(reading(frame_, 'game_time').abstain, 'unknown_glyph')
        self.assertIsNone(reading(frame_, 'game_time').value)
        self.assertEqual(frame_.mode, 'in_play')  # other readers are unaffected

    def test_value_is_read_without_its_label_at_lower_confidence(self):
        def hide_labels(array):
            array[16 * 16:18 * 16, 616:616 + 5 * 8] = 0
        frame_ = read('sidebar_calm', edit=hide_labels)
        self.assertEqual(frame_.game_time, at(0, 61, 8, 5, 16))
        self.assertEqual(reading(frame_, 'game_time').confidence, 0.85)
        self.assertEqual(frame_.mode, 'prompt')


class ModeTests(unittest.TestCase):
    def test_in_play_prompt_menu_death_loading_unknown(self):
        self.assertEqual(read('sidebar_calm').mode, 'in_play')
        self.assertEqual(read('main_menu').mode, 'menu')
        dead = read('sidebar_calm', 'death_dialog')
        self.assertEqual((dead.mode, dead.death, dead.identity), ('dead', True, 'Russell Dobbs'))
        self.assertEqual(read().mode, 'unknown')

    def test_popup_border_over_the_map_is_a_prompt(self):
        def border(array):
            array[300, 100:400] = (150, 150, 150)
            array[360, 100:400] = (150, 150, 150)
        self.assertEqual(read('sidebar_calm', edit=border).mode, 'prompt')

    def test_covered_sidebar_label_is_a_prompt(self):
        def cover(array):
            array[19 * 16:20 * 16, 616:616 + 6 * 8] = 0
        self.assertEqual(read('sidebar_calm', edit=cover).mode, 'prompt')

    def test_loading_splash(self):
        def splash(array):
            array[100:520, 330:620] = (200, 150, 90)
        self.assertEqual(read(edit=splash).mode, 'loading')

    def test_mode_and_death_readings_are_recorded(self):
        frame_ = read('sidebar_calm', 'death_dialog')
        self.assertEqual(reading(frame_, 'mode').value, 'dead')
        self.assertTrue(reading(frame_, 'death').value)
        self.assertEqual(reading(frame_, 'identity').value, 'Russell Dobbs')
        calm = read('sidebar_calm')
        self.assertFalse(reading(calm, 'death').value)
        self.assertEqual(reading(calm, 'identity').abstain, 'no_name_on_screen')


class VitalTests(unittest.TestCase):
    def test_blank_labels_are_the_normal_state(self):
        frame_ = read('sidebar_calm')
        self.assertEqual(vital(frame_, 'pain').value, 1.0)
        self.assertEqual(vital(frame_, 'thirst').value, 0.85)
        self.assertFalse(any(v.critical for v in frame_.vitals))
        self.assertEqual(reading(frame_, 'vital.thirst').value['label'], '')

    def test_labelled_needs_map_through_the_game_ladder(self):
        frame_ = read('sidebar_thirsty_peckish')
        self.assertEqual((vital(frame_, 'thirst').value, vital(frame_, 'thirst').critical), (0.5, False))
        self.assertEqual(vital(frame_, 'hunger').value, 0.7)
        self.assertLess(vital(frame_, 'hunger').value, vital(read('sidebar_calm'), 'hunger').value)
        self.assertEqual(reading(frame_, 'vital.thirst').value['colour'], 'yellow')

    def test_severe_labels_are_critical(self):
        for ladder, critical in ((rd.THIRST, rd.THIRST_CRITICAL), (rd.HUNGER, rd.HUNGER_CRITICAL),
                                 (rd.WEARINESS, rd.WEARINESS_CRITICAL), (rd.REST, rd.REST_CRITICAL), (rd.PAIN, rd.PAIN_CRITICAL)):
            self.assertTrue(critical <= set(ladder))
            self.assertEqual(min(ladder.values()), 0.0)
        self.assertEqual(rd.THIRST_CRITICAL, {'very thirsty', 'dehydrated', 'parched'})
        self.assertEqual(rd.HUNGER_CRITICAL, {'very hungry', 'famished', 'near starving', 'starving'})
        self.assertTrue({'dead tired', 'exhausted'} <= rd.REST_CRITICAL)

    def test_truncated_pain_label_matches_by_prefix(self):
        frame_ = read('sidebar_truncated_pain')
        self.assertEqual(reading(frame_, 'vital.pain').value['label'], 'distracting pain')
        self.assertEqual(vital(frame_, 'pain').value, 0.5)
        self.assertFalse(vital(frame_, 'pain').critical)

    def test_severe_pain_and_red_limb_bars_are_critical(self):
        frame_ = read('sidebar_crowd_red')
        self.assertTrue(vital(frame_, 'pain').critical)
        for limb in ('head', 'torso', 'l_arm', 'r_arm', 'l_leg', 'r_leg'):
            bar = vital(frame_, 'limb', f'part:{limb}')
            self.assertEqual((bar.value, bar.critical), (0.0, True), limb)

    def test_healthy_limb_bars_are_full_and_not_critical(self):
        frame_ = read('sidebar_calm')
        for limb in ('head', 'torso', 'l_arm', 'r_arm', 'l_leg', 'r_leg'):
            bar = vital(frame_, 'limb', f'part:{limb}')
            self.assertEqual((bar.value, bar.critical), (1.0, False), limb)

    def test_partial_bar_glyphs_count_half(self):
        frame_ = read('sidebar_truncated_pain')
        values = {v.scope: v.value for v in frame_.vitals if v.name == 'limb'}
        self.assertTrue(all(0.0 <= value <= 1.0 and (value * 10) % 1 == 0 for value in values.values()))
        self.assertTrue(any(value < 1.0 for value in values.values()))

    def test_covered_label_abstains_instead_of_reading_blank_as_best(self):
        def cover(array):
            array[8 * 16:9 * 16, 616 + 22 * 8:616 + 29 * 8] = 0
        frame_ = read('sidebar_thirsty_peckish', edit=cover)
        self.assertIsNone(vital(frame_, 'thirst'))
        self.assertEqual(reading(frame_, 'vital.thirst').abstain, 'label_occluded')
        self.assertIsNotNone(vital(frame_, 'hunger'))

    def test_unknown_label_text_abstains(self):
        def smudge(array):
            array[9 * 16 + 4:9 * 16 + 12, 616 + 31 * 8:616 + 31 * 8 + 6] = (255, 255, 0)
        frame_ = read('sidebar_calm', edit=smudge)
        self.assertIsNone(vital(frame_, 'hunger'))
        self.assertEqual(reading(frame_, 'vital.hunger').abstain, 'unknown_glyph')


class ThreatTests(unittest.TestCase):
    def test_creature_list_counts_and_buckets(self):
        calm = read('sidebar_calm')
        self.assertEqual((calm.threat, calm.threat_count), ('low', 1))
        crowd = read('sidebar_crowd_red')
        self.assertEqual(crowd.threat, 'lethal')
        self.assertGreaterEqual(crowd.threat_count, 40)
        self.assertEqual(read('sidebar_thirsty_peckish').threat, 'none')

    def test_bucket_thresholds(self):
        self.assertEqual([rd.threat_bucket(n) for n in (0, 1, 2, 3, 9, 10, 50)],
                         ['none', 'low', 'low', 'high', 'high', 'lethal', 'lethal'])

    def test_named_people_are_not_threats(self):
        self.assertEqual(rd.PROPER_NAME.match('Elijah Herring') is not None, True)
        self.assertIsNone(rd.PROPER_NAME.match('feral human'))

    def test_threat_is_only_read_in_play(self):
        self.assertIsNone(read('main_menu').threat)
        self.assertEqual(reading(read('main_menu'), 'threat').abstain, 'not_in_play')


class SafetyTests(unittest.TestCase):
    def test_garbage_input_never_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'bytes.png').write_bytes(b'not an image at all')
            (base / 'empty.png').write_bytes(b'')
            Image.new('RGB', (1, 1)).save(base / 'tiny.png')
            Image.new('RGBA', (960, 640), (10, 20, 30, 255)).save(base / 'rgba.png')
            Image.new('L', (960, 640), 7).save(base / 'gray.png')
            noise = np.random.default_rng(1).integers(0, 256, (640, 960, 3), dtype=np.uint8)
            Image.fromarray(noise).save(base / 'noise.png')
            for name in ('bytes.png', 'empty.png', 'tiny.png', 'rgba.png', 'gray.png', 'noise.png', 'missing.png'):
                result = BINDING.read_frame(base / name)
                self.assertIn(result.mode, ('unknown', 'prompt', 'menu', 'loading'), name)
                self.assertIsNone(result.game_time, name)
                self.assertFalse(result.death, name)

    def test_read_frame_is_fast(self):
        path = synth('sidebar_calm', 'main_menu')
        try:
            BINDING.read_frame(path)
            start = time.perf_counter()
            for _ in range(10):
                BINDING.read_frame(path)
            self.assertLess((time.perf_counter() - start) / 10, 0.05)
        finally:
            path.unlink()


class LadderTests(unittest.TestCase):
    def rung(self, rung_id):
        return next(r for r in BINDING.ladder if r.id == rung_id)

    def reached(self, rung_id, history):
        return BINDING.rung_reached(self.rung(rung_id), history)

    def test_ladder_ids_and_evidence(self):
        ids = [r.id for r in BINDING.ladder]
        self.assertEqual(ids, ['in_play', 'armed', 'water_obtained', 'drank', 'food_obtained', 'ate', 'shelter', 'clean_water',
                               'slept', 'survived_first_night', 'elapsed_24h', 'elapsed_72h', 'elapsed_168h', 'resupplied'])
        human = {r.id for r in BINDING.ladder if r.evidence == 'human'}
        self.assertEqual(human, {'armed', 'water_obtained', 'food_obtained', 'shelter', 'clean_water', 'resupplied'})

    def test_human_rungs_are_never_reached(self):
        history = [frame(t=at(0, 61))]
        for r in BINDING.ladder:
            if r.evidence == 'human':
                self.assertIsNone(BINDING.rung_reached(r, history))

    def test_in_play_first_index(self):
        self.assertEqual(self.reached('in_play', [frame('menu'), frame('loading'), frame('in_play'), frame('in_play')]), 2)
        self.assertIsNone(self.reached('in_play', [frame('menu')]))

    def test_drank_and_ate_need_an_improvement_between_in_play_readings(self):
        history = [frame(t=1, thirst=0.5, hunger=0.7), frame('prompt', thirst=1.0), frame(t=2, thirst=0.5, hunger=0.7),
                   frame(t=3, thirst=0.85, hunger=0.7), frame(t=4, thirst=0.85, hunger=0.85)]
        self.assertEqual(self.reached('drank', history), 3)
        self.assertEqual(self.reached('ate', history), 4)
        self.assertIsNone(self.reached('drank', history[:3]))
        self.assertIsNone(self.reached('ate', [frame(t=1, hunger=0.85), frame(t=2, hunger=0.7)]))

    def test_slept_needs_a_gain_over_an_hour_of_game_time(self):
        start = at(0, 61, 22)
        quick = [frame(t=start, weariness=0.2), frame(t=start + 1800, weariness=1.0)]
        self.assertIsNone(self.reached('slept', quick))
        slept = [frame(t=start, weariness=0.2), frame(t=start + 1800, weariness=0.2), frame(t=start + 3600, weariness=0.4),
                 frame(t=start + 7200, weariness=1.0)]
        self.assertEqual(self.reached('slept', slept), 3)
        self.assertIsNone(self.reached('slept', [frame(t=start, weariness=1.0), frame(t=start + 36000, weariness=1.0)]))

    def test_elapsed_rungs_use_in_play_clock_minus_first_in_play_clock(self):
        start = at(0, 61, 8)
        history = [frame('menu', t=at(0, 1)), frame(t=start), frame('prompt', t=start + 3 * DAY),
                   frame(t=start + DAY - 1), frame(t=start + DAY), frame(t=start + 3 * DAY), frame(t=start + 5 * DAY), frame(t=start + 7 * DAY)]
        self.assertEqual(self.reached('elapsed_24h', history), 4)
        self.assertEqual(self.reached('elapsed_72h', history), 5)
        self.assertIsNone(self.reached('elapsed_168h', history[:-1]))
        self.assertEqual(self.reached('elapsed_168h', history), 7)

    def test_elapsed_spans_the_year_turn_but_not_a_world_reset(self):
        start = at(3, 91, 20)
        history = [frame(t=start), frame(t=at(0, 1, 12)), frame(t=at(0, 2, 12))]
        self.assertIsNone(self.reached('elapsed_24h', history[:2]))
        self.assertEqual(self.reached('elapsed_24h', history), 2)
        reset = [frame(t=at(3, 1, 8)), frame(t=at(0, 61, 8))]
        self.assertIsNone(self.reached('elapsed_24h', reset))

    def test_misread_far_jump_is_ignored(self):
        start = at(0, 61, 8)
        self.assertIsNone(self.reached('elapsed_168h', [frame(t=start), frame(t=start + 40 * DAY), frame(t=start + 100)]))

    def test_survived_first_night_needs_0600_of_the_next_day_in_play(self):
        start = at(0, 61, 8)
        night = start - 8 * 3600 + 2 * DAY // 2  # midnight after the first day
        self.assertEqual(night, at(0, 62, 0))
        history = [frame(t=start), frame(t=night), frame(t=night + 5 * 3600 + 3599), frame('dead', t=night + 6 * 3600),
                   frame(t=night + 6 * 3600), frame(t=night + 9 * 3600)]
        self.assertEqual(self.reached('survived_first_night', history), 4)
        self.assertIsNone(self.reached('survived_first_night', history[:3]))
        late = at(0, 61, 22)
        self.assertEqual(self.reached('survived_first_night', [frame(t=late), frame(t=at(0, 62, 5, 59, 59)), frame(t=at(0, 62, 6))]), 2)


class BindingShapeTests(unittest.TestCase):
    def test_identity_and_constants(self):
        self.assertEqual((BINDING.binding_id, BINDING.binding_version, BINDING.game_time_unit), ('cdda', 1, 'seconds'))
        self.assertEqual(BINDING.long_activity_seconds, 900)
        self.assertEqual(BINDING.map_region, (0, 0, 608, 640))
        self.assertTrue({'h', 'j', 'k', 'l', 'y', 'u', 'b', 'n', 'UP', 'DOWN', 'LEFT', 'RIGHT'} <= BINDING.movement_keys)
        self.assertGreater(BINDING.max_clock_jump_seconds, BINDING.long_activity_seconds)

    def test_every_reading_is_versioned(self):
        for r in read('sidebar_calm').readings:
            self.assertEqual(r.version, rd.READER_VERSION)


if __name__ == '__main__':
    unittest.main()
