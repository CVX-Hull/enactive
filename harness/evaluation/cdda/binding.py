"""The CDDA game binding for the evaluation core (binding_id 'cdda', version 1)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from harness.evaluation.cdda import readers as rd
from harness.evaluation.cdda.atlas import Atlas
from harness.evaluation.cdda.ladder import LADDER, rung_reached
from harness.evaluation.core.binding import FrameReading, Reading, Rung, Vital

NEEDS = (('thirst', rd.read_thirst), ('hunger', rd.read_hunger), ('weariness', rd.read_weariness), ('pain', rd.read_pain))


def _reading(name: str, result: rd.Result) -> Reading:
    value, confidence, reason = result
    return Reading(name, rd.READER_VERSION, value, confidence, reason)


class CddaBinding:
    binding_id = 'cdda'
    binding_version = 1
    game_time_unit = 'seconds'
    long_activity_seconds = 900
    # Sleeping or waiting through a night is the longest single legitimate step (about 12 h).
    max_clock_jump_seconds = 12 * 3600
    map_region = rd.MAP_REGION
    movement_keys = frozenset({'h', 'j', 'k', 'l', 'y', 'u', 'b', 'n', 'UP', 'DOWN', 'LEFT', 'RIGHT',
                               '1', '2', '3', '4', '6', '7', '8', '9'})
    ladder = LADDER

    def __init__(self, atlas: Atlas | None = None) -> None:
        self._atlas = atlas or Atlas.load()

    def read_frame(self, png: Path) -> FrameReading:
        try:
            return self._read(png)
        except Exception as error:  # an unreadable screen abstains; it never raises
            reason = f'unreadable:{type(error).__name__}'
            return FrameReading('unknown', None, None, (), None, None, False,
                                (Reading('mode', rd.READER_VERSION, None, None, reason),))

    def _read(self, png: Path) -> FrameReading:
        with Image.open(png) as image:
            if image.size != (rd.FRAME_W, rd.FRAME_H):
                return FrameReading('unknown', None, None, (), None, None, False,
                                    (Reading('mode', rd.READER_VERSION, None, None, 'frame_size'),))
            arr = np.asarray(image.convert('RGB'))
        frame = rd.Frame(arr, self._atlas)
        mode, confidence, reason, death_name = rd.classify_mode(frame)
        readings = [Reading('mode', rd.READER_VERSION, mode if reason is None else None, confidence, reason)]
        clock = rd.read_clock(frame) if mode != 'menu' and mode != 'loading' else rd.abstain('not_in_game')
        readings.append(_reading('game_time', clock))
        vitals: list[Vital] = []
        threat = count = None
        if mode in ('in_play', 'prompt'):
            for name, reader in NEEDS:
                result = reader(frame)
                readings.append(_reading(f'vital.{name}', result))
                if result[2] is None:
                    value = result[0]
                    vitals.append(Vital(name, 'whole', value['level'], bool(value['critical'])))
            for limb, result in rd.read_limbs(frame).items():
                readings.append(_reading(f'vital.limb.{limb}', result))
                if result[2] is None:
                    vitals.append(Vital('limb', f'part:{limb}', result[0]['level'], bool(result[0]['critical'])))
        else:
            readings.append(Reading('vital', rd.READER_VERSION, None, None, 'not_in_game'))
        if mode == 'in_play':
            result = rd.read_threat(frame)
            readings.append(_reading('threat', result))
            if result[2] is None:
                threat, count = result[0]['bucket'], result[0]['count']
        else:
            readings.append(Reading('threat', rd.READER_VERSION, None, None, 'not_in_play'))
        dead = mode == 'dead'
        readings.append(Reading('death', rd.READER_VERSION, dead, 0.95 if dead else None) if dead
                        else Reading('death', rd.READER_VERSION, False, 0.9 if mode in ('in_play', 'menu') else 0.5))
        identity = death_name if dead else rd.read_creation_name(frame) if mode == 'menu' else None
        readings.append(Reading('identity', rd.READER_VERSION, identity, 0.9 if identity else None,
                                None if identity else 'no_name_on_screen'))
        game_time = clock[0] if clock[2] is None else None
        return FrameReading(mode, game_time, identity, tuple(vitals), threat, count, dead, tuple(readings))

    def rung_reached(self, rung: Rung, history: Sequence[FrameReading]) -> int | None:
        return rung_reached(rung, history)
