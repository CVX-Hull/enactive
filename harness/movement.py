"""Pure cardinal movement checks shared by public walk and passive skills."""
from __future__ import annotations

from typing import Any, Sequence

DIRECTIONS = {"north": (0, -1, "UP"), "south": (0, 1, "DOWN"),
              "west": (-1, 0, "LEFT"), "east": (1, 0, "RIGHT")}
SAFE_TERRAIN = frozenset({"t_floor", "t_grass", "t_dirt", "t_pavement", "t_pavement_y"})


class MovementBlocked(ValueError):
    """A required visible predicate is false or unknown; not a dispatch result."""


def _delta(dx: int, dy: int) -> None:
    if type(dx) is not int or type(dy) is not int or abs(dx) + abs(dy) != 1:
        raise MovementBlocked("Movement requires one cardinal unit")


def expected_position(position: Sequence[int], dx: int, dy: int) -> tuple[int, int, int]:
    _delta(dx, dy)
    if (not isinstance(position, (list, tuple)) or len(position) != 3
            or any(type(n) is not int for n in position)):
        raise MovementBlocked("Walk stopped: position is unknown")
    return position[0] + dx, position[1] + dy, position[2]


def guard(state: dict[str, Any], dx: int, dy: int, *, paused: bool,
          frozen: bool, now_timestamp_ms: int) -> tuple[int, int, int]:
    """Check the public walk policy on validated state; malformed requirements stop.

    Time is supplied, never refreshed here. This cannot grant native authority or
    prove absence of traps/damage. Public walk deliberately checks the next tile
    even after its final requested displacement.
    """
    _delta(dx, dy)
    if (type(paused) is not bool or type(frozen) is not bool or not isinstance(state, dict)
            or paused or frozen or state.get("paused") is not False):
        raise MovementBlocked("Walk stopped: control is paused or frozen")
    scene = state.get("scene")
    boundary = state.get("boundary")
    timestamp = state.get("timestamp_ms")
    if (not isinstance(boundary, dict) or boundary.get("kind") != "normal_play"
            or state.get("in_game") is not True or state.get("frame_ok") is not True
            or type(timestamp) is not int or type(now_timestamp_ms) is not int
            or now_timestamp_ms - timestamp > 3000 or not isinstance(scene, dict)):
        raise MovementBlocked("Walk stopped: normal play scene is unavailable")
    creatures = scene.get("visible_creatures")
    if not isinstance(creatures, list) or creatures:
        raise MovementBlocked("Walk stopped: visible creatures or unknown visibility")
    position = scene.get("position")
    expected_position(position, dx, dy)
    neighbors = scene.get("neighbors")
    if not isinstance(neighbors, list):
        raise MovementBlocked("Walk stopped: neighboring terrain is unknown")
    matches = [tile for tile in neighbors if isinstance(tile, dict)
               and type(tile.get("dx")) is int and type(tile.get("dy")) is int
               and tile["dx"] == dx and tile["dy"] == dy]
    tile = matches[0] if len(matches) == 1 else None
    if (not tile or tile.get("visible") is not True or tile.get("furniture") != "f_null"
            or not isinstance(tile.get("terrain"), str) or tile["terrain"] not in SAFE_TERRAIN):
        raise MovementBlocked("Walk stopped: next tile is not a visible, empty, allowlisted surface")
    return tuple(position)


def observed_step(before: dict[str, Any], after: dict[str, Any], dx: int, dy: int) -> bool:
    """Exact public-walk displacement predicate; freshness/post-guards are separate."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    a, b = before.get("scene"), after.get("scene")
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    try:
        expected = expected_position(a.get("position"), dx, dy)
        actual = b.get("position")
        expected_position(actual, dx, dy)  # Reject bools/missing coordinates.
    except MovementBlocked:
        return False
    return (isinstance(before.get("session"), str) and isinstance(before.get("category"), str)
            and after.get("session") == before["session"]
            and after.get("category") == before["category"] and tuple(actual) == expected)
