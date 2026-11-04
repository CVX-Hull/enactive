"""The episode cutter (ADR-007 level v4, item 1): mechanical boundaries over the served actor's log.

Software in the playing system, never `harness/computer`. It reads player-visible result captures only and has no
game semantics: each capture becomes a 32 x 20 greyscale box-pooled thumbnail, the distance d of an input is the
mean absolute pixel difference divided by 255 between that input's result capture and the result capture of the
previous input that has one, and an episode closes

* on content, before input i, when d(i) >= theta and the episode already holds at least m inputs (the crossing
  input then starts the next episode, so an episode ends on the last stable screen);
* at the cap, when it holds C inputs;
* at a session edge (`flush`: a handoff, a stop or the session's end), so the last partial episode is still recorded.

Boundaries are frozen once returned and never recomputed. An input with no result capture has no distance and
cannot close an episode. The cutter is a pure function of the entries it is fed; the driver decides when an entry
is ready (an input whose result is still in flight is not fed yet).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import io
from typing import Any, Callable

from PIL import Image

THUMBNAIL = (32, 20)
# The recorder sees a baseline frame plus at most this many of the episode's own frames (ADR-007 item 2).
MAX_OWN_FRAMES = 6
CLOSED_BY = ('content', 'cap', 'edge')


def thumbnail(png: bytes) -> bytes:
    """A 32 x 20 greyscale box-pooled thumbnail of a PNG capture, as raw bytes."""
    with Image.open(io.BytesIO(png)) as image:
        return image.convert('L').resize(THUMBNAIL, Image.Resampling.BOX).tobytes()


def distance(a: bytes, b: bytes) -> float:
    """Mean absolute pixel difference of two thumbnails, divided by 255."""
    if len(a) != len(b) or not a:
        raise ValueError('Thumbnails differ in size')
    return sum(abs(x - y) for x, y in zip(a, b)) / (len(a) * 255.0)


def key_tokens(actions: list[dict[str, Any]] | None) -> list[str]:
    """An input's actions as short tokens for the recorder's pushed operations; no game vocabulary."""
    tokens = []
    for action in actions or []:
        kind = action.get('type')
        if kind == 'key':
            modifiers = '+'.join(sorted(action.get('modifiers') or []))
            tokens.append(f"key:{action.get('key')}" + (f'+{modifiers}' if modifiers else ''))
        elif kind == 'text':
            tokens.append(f"text:{action.get('text')}")
        elif kind == 'click':
            tokens.append(f"click:{action.get('button')}@{action.get('x')},{action.get('y')}")
        else:
            tokens.append(str(kind))
    return tokens


@dataclass(frozen=True)
class Episode:
    """One closed episode: the served actor's operations at positions `first_position`..`last_position`.

    `subgoal_id` is the level subgoal current when the episode opened (its first operation was fed), recorded by
    the driver because no custodian API gives the subgoal current at a past position. `distances` maps each input
    position to its distance d (None when it had none); `frames` lists the episode's operations with a result
    capture, in order, as (position, source_id).
    """
    first_position: int
    last_position: int
    inputs: int
    closed_by: str
    subgoal_id: str | None
    distances: dict[int, float | None] = field(default_factory=dict)
    frames: tuple[tuple[int, str], ...] = ()


class EpisodeCutter:
    """Incremental cutter. `thumbnail_of(source_id)` returns that capture's thumbnail bytes."""
    def __init__(self, theta: float, minimum: int, cap: int, thumbnail_of: Callable[[str], bytes]) -> None:
        if type(theta) is not float or not 0 < theta < 1:
            raise ValueError('theta must be a float strictly between 0 and 1')
        if type(minimum) is not int or type(cap) is not int or not 1 <= minimum <= cap <= 1000:
            raise ValueError('m and C must be integers with 1 <= m <= C <= 1000')
        self.theta, self.minimum, self.cap, self.thumbnail_of = theta, minimum, cap, thumbnail_of
        self._previous: bytes | None = None
        self._next_position = 1
        self._open: dict[str, Any] | None = None

    @property
    def next_position(self) -> int:
        """The position of the next operation to feed: one past the furthest operation fed (the furthest cut or beyond)."""
        return self._next_position

    @property
    def open_inputs(self) -> int:
        return self._open['inputs'] if self._open else 0

    @property
    def open_first(self) -> int | None:
        return self._open['first'] if self._open else None

    def feed(self, entry: dict[str, Any], subgoal_id: str | None) -> list[Episode]:
        """Take the next operation of the log (`position`, `kind`, `source_id`) in order; return the episodes it closed.

        `subgoal_id` is the level subgoal current now; it is kept only if this operation opens an episode.
        """
        position = entry['position']
        if position != self._next_position:
            raise ValueError(f'The cutter takes the log in order: expected position {self._next_position}, got {position}')
        self._next_position += 1
        closed: list[Episode] = []
        d: float | None = None
        if entry['kind'] == 'input' and entry.get('source_id'):
            thumb = self.thumbnail_of(entry['source_id'])
            d = distance(self._previous, thumb) if self._previous is not None else None
            self._previous = thumb
        if (entry['kind'] == 'input' and d is not None and d >= self.theta and self._open is not None
                and self._open['inputs'] >= self.minimum):
            closed.append(self._close('content'))
        if self._open is None:
            self._open = dict(first=position, last=position, inputs=0, subgoal_id=subgoal_id, distances={}, frames=[])
        self._open['last'] = position
        if entry.get('source_id'):
            self._open['frames'].append((position, entry['source_id']))
        if entry['kind'] == 'input':
            self._open['inputs'] += 1
            self._open['distances'][position] = d
            if self._open['inputs'] >= self.cap:
                closed.append(self._close('cap'))
        return closed

    def flush(self) -> Episode | None:
        """Close the partial episode at a session edge (a handoff, a stop or the session's end).

        An open tail with no input (only observes, or the handoff itself) is not an episode: it is dropped, never
        recorded, so it cannot add a settle to the stall count.
        """
        if self._open is None:
            return None
        if self._open['inputs'] == 0:
            self._open = None
            return None
        return self._close('edge')

    def _close(self, reason: str) -> Episode:
        held, self._open = self._open, None
        return Episode(first_position=held['first'], last_position=held['last'], inputs=held['inputs'], closed_by=reason,
                       subgoal_id=held['subgoal_id'], distances=held['distances'], frames=tuple(held['frames']))


def pick_frames(episode: Episode, limit: int = MAX_OWN_FRAMES) -> list[tuple[int, str, str]]:
    """The episode's own frames to show the recorder, as (position, source_id, role) in capture order.

    Always the last frame, then those with the largest thumbnail distance from their predecessor, up to `limit` in
    all; ties go to the earlier frame, and a frame with no distance (an observe, or an input whose predecessor has
    no capture) is chosen last. The role is `last` for the final frame and `in-episode` for the others.
    """
    frames = episode.frames
    count = len(frames)
    if count <= limit:
        chosen = list(range(count))
    else:
        def key(index: int) -> tuple[float, int]:
            value = episode.distances.get(frames[index][0])
            return (-(value if value is not None else -1.0), index)
        chosen = sorted(sorted(range(count - 1), key=key)[:limit - 1] + [count - 1])
    return [(frames[i][0], frames[i][1], 'last' if i == count - 1 else 'in-episode') for i in chosen]
