"""Replay an archived run into a fresh copy at its original pace, for the spectator's graphical lane.

The copy is a test fixture, never evidence: static files, frames and every session table
except `operations` are copied first; `operations` rows and host trace lines then appear on
their original wall-clock offsets (optionally after an instant prefix), so the viewer sees a
run that is still moving. No game, provider or player is involved.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ('manifest.json', 'prompt.txt', 'context.txt', 'route.json', 'target.json', 'mcp-template.json',
          'started.json', 'ready.json', 'receipt.json', 'orderly-stop.json', 'watch-start.json')
COPIED_TABLES = ('metadata', 'resources', 'actors', 'sources', 'issued_sources')


def trace_lines(source: Path) -> list[tuple[float, Path, str]]:
    """Every host trace line with its wall time and the actor file it belongs to."""
    lines = []
    for actor in sorted((source/'actors').iterdir()):
        for line in (actor/'host.jsonl').read_text().splitlines():
            stamp = datetime.fromisoformat(json.loads(line)['wall_time'].replace('Z', '+00:00')).timestamp()
            lines.append((stamp, actor, line))
    return sorted(lines, key=lambda item: item[0])


def prepare(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for name in STATIC:
        if (source/name).exists(): shutil.copyfile(source/name, target/name)
    shutil.copytree(source/'sources', target/'sources')
    if (source/'contexts').is_dir(): shutil.copytree(source/'contexts', target/'contexts')
    for actor in (source/'actors').iterdir():
        (target/'actors'/actor.name).mkdir(parents=True)
        for item in actor.iterdir():
            if item.name != 'host.jsonl' and item.is_file(): shutil.copyfile(item, target/'actors'/actor.name/item.name)
        (target/'actors'/actor.name/'host.jsonl').touch()
    original = sqlite3.connect(f'file:{source/"session.sqlite3"}?mode=ro', uri=True)
    copy = sqlite3.connect(target/'session.sqlite3')
    copy.execute('PRAGMA journal_mode=WAL')
    for (sql,) in original.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type='index'"):
        copy.execute(sql)
    copy.execute(f'PRAGMA user_version={original.execute("PRAGMA user_version").fetchone()[0]}')
    for table in COPIED_TABLES:
        rows = original.execute(f'SELECT * FROM {table}').fetchall()
        if rows: copy.executemany(f'INSERT INTO {table} VALUES ({",".join("?"*len(rows[0]))})', rows)
    copy.commit(); copy.close(); original.close()


def replay(source: Path, target: Path, *, instant_until: float, speed: float, stop_after: float | None) -> None:
    """Instant prefix up to `instant_until` seconds into the run, then the original pace divided by `speed`."""
    original = sqlite3.connect(f'file:{source/"session.sqlite3"}?mode=ro', uri=True)
    operations = original.execute('SELECT * FROM operations ORDER BY rowid').fetchall()
    intents = original.execute('SELECT * FROM native_intents').fetchall()
    collections = original.execute('SELECT * FROM collections').fetchall()
    original.close()
    by_operation: dict[str, list] = {}
    for row in intents: by_operation.setdefault(row[1], []).append(row)
    lines = trace_lines(source)
    events = [(row[3], 'op', row) for row in operations] + [(stamp, 'line', (actor, text)) for stamp, actor, text in lines]
    events.sort(key=lambda item: item[0])
    start = events[0][0]
    copy = sqlite3.connect(target/'session.sqlite3', timeout=5)
    began = time.monotonic()
    for stamp, kind, payload in events:
        offset = stamp - start
        if stop_after is not None and offset > instant_until + stop_after * speed: break
        if offset > instant_until:
            delay = (offset - instant_until) / speed - (time.monotonic() - began)
            if delay > 0: time.sleep(delay)
        if kind == 'op':
            copy.execute(f'INSERT INTO operations VALUES ({",".join("?"*len(payload))})', payload)
            for intent in by_operation.get(payload[0], []):
                copy.execute(f'INSERT OR IGNORE INTO native_intents VALUES ({",".join("?"*len(intent))})', intent)
            copy.commit()
        else:
            actor, text = payload
            with (target/'actors'/actor.name/'host.jsonl').open('a') as stream: stream.write(text + '\n')
    if collections:
        copy.executemany(f'INSERT OR IGNORE INTO collections VALUES ({",".join("?"*len(collections[0]))})', collections)
        copy.commit()
    copy.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='an archived run directory')
    parser.add_argument('target', type=Path, help='a fresh directory under this checkout .runtime')
    parser.add_argument('--instant-until', type=float, default=0.0, help='seconds of the run to copy at once')
    parser.add_argument('--speed', type=float, default=1.0, help='1.0 replays at the original pace')
    parser.add_argument('--stop-after', type=float, help='wall seconds of paced replay before stopping')
    options = parser.parse_args(argv)
    target = options.target.resolve()
    if not target.is_relative_to(ROOT/'.runtime'):
        raise ValueError('Replay only into a fresh directory under this checkout .runtime')
    prepare(options.source.resolve(), target)
    print(json.dumps(dict(target=str(target), prepared=True)), flush=True)
    replay(options.source.resolve(), target, instant_until=options.instant_until, speed=options.speed,
           stop_after=options.stop_after)
    print(json.dumps(dict(target=str(target), finished=True)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
