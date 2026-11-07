"""Pause conditions for the live run (docs/contracts/evaluation.md, Pause conditions).

Computed from the live evaluation store alone. They inform the owner and gate nothing. Each has a value, a
threshold, `met` and the dollars per minute that continuing costs. Game state (vitals, threat) is never a
condition: survival is the player's job.
"""
from __future__ import annotations

import sqlite3

FEED_SECONDS = 300
LOOP_DECISIONS = 30
RATE_WINDOW_SECONDS = 600
RATE_MIN_WINDOW_SECONDS = 60


def dollars_per_minute(requests: list[tuple[float | None, float | None]]) -> float:
    """Spend rate from the recent requests (wall, dollars): the last ten minutes, at least one minute wide."""
    priced = [(w, d) for w, d in requests if w is not None and d is not None]
    if not priced:
        return 0.0
    newest = max(w for w, _ in priced)
    recent = [(w, d) for w, d in priced if w >= newest - RATE_WINDOW_SECONDS]
    window = max(RATE_MIN_WINDOW_SECONDS, newest - min(w for w, _ in recent))
    return sum(d for _, d in recent) / window * 60


def looping_streak(rows: list[tuple[int, str, int | None]]) -> tuple[int, bool]:
    """(decisions in the trailing run without an in-play mode, whether game time advanced during it).
    Rows are (decision, mode, game_time) per step in order; an unreadable mode neither extends nor breaks a run."""
    decisions: list[tuple[int, str, int | None]] = []
    for decision, mode, game_time in rows:
        if decisions and decisions[-1][0] == decision:
            decisions[-1] = (decision, mode if mode != 'unknown' else decisions[-1][1], game_time if game_time is not None else decisions[-1][2])
        else:
            decisions.append((decision, mode, game_time))
    streak, start = 0, None
    for index in range(len(decisions) - 1, -1, -1):
        mode = decisions[index][1]
        if mode == 'unknown':
            continue
        if mode == 'in_play':
            break
        streak += 1
        start = index
    if start is None:
        return 0, True
    before = next((t for _, _, t in reversed(decisions[:start]) if t is not None), None)
    latest = next((t for _, _, t in reversed(decisions[start:]) if t is not None), None)
    advanced = latest is not None and (before is None or latest > before)
    return streak, advanced


def conditions(connection: sqlite3.Connection, facts: dict, now: float) -> dict:
    last_wall = connection.execute('SELECT MAX(wall) FROM steps').fetchone()[0]
    silent = None if last_wall is None else max(0.0, now - last_wall)
    requests = connection.execute('SELECT wall, dollars FROM requests ORDER BY wall').fetchall()
    spend = sum(d or 0.0 for _, d in requests)
    rate = dollars_per_minute(requests)
    projected = spend + rate * 60
    ceiling = facts.get('spend_allowance_usd')
    stops = connection.execute("SELECT COUNT(*) FROM events WHERE kind='custody_stop'").fetchone()[0]
    uncertain = connection.execute(
        "SELECT COUNT(*) FROM events WHERE kind='custody_stop' AND json_extract(payload,'$.cause') IN ('partial','unknown')"
    ).fetchone()[0]
    streak, advanced = looping_streak(connection.execute('SELECT decision, mode, game_time FROM steps ORDER BY seq').fetchall())
    death = connection.execute("SELECT MIN(s.wall) FROM events e JOIN steps s ON s.seq=e.seq_start WHERE e.kind='death'").fetchone()[0]
    after_death = 0 if death is None else sum(1 for w, _ in requests if w is not None and w > death)

    def row(identifier: str, name: str, value: object, threshold: str, met: bool, detail: str = '') -> dict:
        return dict(id=identifier, name=name, value=value, threshold=threshold, met=met, detail=detail,
            dollars_per_minute=rate)
    result = [
        row('feed_alive', 'Feed alive', None if silent is None else round(silent, 1), f'met after {FEED_SECONDS} s with no new operation',
            silent is not None and silent >= FEED_SECONDS, 'seconds since the last operation'),
        row('custody_healthy', 'Custody healthy', dict(uncertain_receipts=uncertain, custody_stops=stops),
            'met at any partial or unknown receipt, or a custody stop', stops > 0),
        row('not_looping', 'Not looping', dict(decisions_out_of_play=streak, game_time_advancing=advanced),
            f'met at {LOOP_DECISIONS} or more decisions without play while game time does not advance',
            streak >= LOOP_DECISIONS and not advanced),
        row('spend_inside_allowance', 'Spend inside allowance', dict(spent=round(spend, 4), projected_one_hour=round(projected, 4),
            ceiling=ceiling), 'met when spend or the one-hour projection exceeds the manifest ceiling',
            ceiling is not None and (spend > ceiling or projected > ceiling),
            '' if ceiling is not None else 'the manifest declares no spend ceiling'),
        row('not_dead_and_spending', 'Not dead and still spending', dict(died=death is not None, requests_after_death=after_death),
            'met at a death followed by further requests', death is not None and after_death > 0)]
    met = [c['name'] for c in result if c['met']]
    return dict(answer='yes' if met else 'no', met=met, dollars_per_minute=rate, spent=spend, conditions=result)
