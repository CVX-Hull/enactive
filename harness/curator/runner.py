"""The curator runner: curator sessions beside an admission that is still being played (#845).

The runner windows and publication rules are in docs/components/curator.md. At each
poll the runner stages a snapshot of the live run (`harness.trace.snapshot.stage`, the only read
it makes of the store), records the position play has reached, and when the actor its cursor is in
has enough finished steps beyond the cursor it runs one windowed admission session over them. The
snapshot call, the session call, the look at the knowledge repository's tags and the clock are
injected, so the rules here run without a sandbox; `tools/curator_host/live_runner.py` is the
process that supplies the real ones. Nothing here writes to the run's store or touches the input
path, and the only lock taken beside the custodian is the shared read lock inside `stage`.

**Its files**, all in the runner's own directory:

- `examined.jsonl` (`curator-runner-examined/1`), the cursor: append-only, one `start` row when a
  session begins and one `end` row when it returns, each naming the window (one actor, steps
  `first` to `last`, with the operations at both ends) and carrying `coverage` (the covered
  prefix, lag and backlog at that moment, and `as_of`, the position and wall time of the last
  successful read they count from). An `end` row says how the session ended, whether the
  cursor `advanced` and whether it counts as a `failed` session, and the gate's verdicts. The
  cursor of an actor is the last step of its advanced rows; a `start` with no `end` was
  interrupted. The file survives a restart.
- `versions.jsonl` (`curator-runner-version/1`): each version the runner has seen, when its last
  look without the tag began and when its first look with the tag ended, its coverage stamp and,
  for a restore, the version it restored. A later row for a version replaces an earlier one.
  Versions present at the runner's first look ever are its `baseline`.
- `polls.jsonl` (`curator-runner-poll/1`): one row per poll, with the snapshot's timings or why
  there was none, the position and `coverage`.
- `status.json` (`curator-runner-status/1`), replaced atomically at each poll and at each
  session's start and end; its fields are listed in `Runner.status`.
- `stopped.json` (`curator-runner-stopped/1`), replaced atomically once when the runner stops for
  a failure; a runner restarted for the same admission finds it and does not work again.
- `snapshots/`, where each poll's snapshot is staged and removed when the poll ends.

On loading, each append-only file is cut back to its last newline, so a row a killed runner left
half written is dropped and never joined to the next. A value that is not known is written as
the string `unknown`, never guessed.

**How a session ends** (`outcome` of an `end` row): `accepted`, `nothing-submitted`, `rejected`
(a submission was rejected) and `unconfirmed` (a gate result is unknown) close the session and
advance the cursor, the last two as failures; `aborted` fails and does not advance;
`interrupted` (the runner was signalled), `lock-refused` (another session held the repository),
`not-started` (no spend left) and `host-unavailable` (the curator host could not be resolved)
neither advance nor fail. An interruption that lands after a session returned but before its
`end` row is written is still recorded as `interrupted`: coverage is then understated, never
overstated.

A spend reservation refusal without a gate-confirmed close-out publication leaves the cursor
in place and stops the runner cleanly (no blind step halving). Temporary non-real-time capacity
deferrals (`flex-capacity-deferred`) retry the same window on the next poll up to `FLEX_DEFERRALS`
consecutive times without halving steps or counting against session failures.

Between ingestion windows, when the unexamined backlog is small and enough confirmed ingestion
windows have published since the last hygiene attempt, the runner may dispatch a bounded
text-only `hygiene` session (`session_kind: 'hygiene'`, `advanced: False`) recorded in
`examined.jsonl` without advancing the cursor. Two consecutive hygiene failures disable hygiene
for the rest of the admission without halting ingestion.

**Why it stops** (`stop_reason`). It *ends* with `store-closing` when the closing marker refuses
its read, `store-closed` when the run directory holds the custodian's `receipt.json`, and
`interrupted` on a signal. It *stops* for the rest of the admission with
`2 consecutive failed sessions`, `3 consecutive snapshots failed or passed their bound`,
`read refused: no-read-lock` (no reader is configured), `error: <type>` (an unexpected exception
in the runner itself), or a session's own stop reason: `proxy-revoked` (a charge passed its
reservation), `spend-cap-exhausted` (the runner's cap, session preflight headroom, or a refused
reservation stopped the runner after recording any confirmed close-out publication),
`flex-capacity-deferred` (consecutive non-real-time capacity deferrals hit their bound),
`proxy-unsettled` (requests the proxy could not settle), `cleanup-unconfirmed` (host processes
survived, or the host ran and its result is missing) and `host-unavailable: <why>`.

**Coverage.** A version is confirmed when its tag was seen, an examined session's verdicts report
it published, and its coverage stamp is that session's window. The covered prefix is the longest
unbroken run of steps from the admission's first that the windows of confirmed versions cover,
actor by actor in admission order, passing to the next actor only when an ended actor is covered
to its last finished step. It is computed from confirmed versions alone, never from the cursor or
the failures. A restore makes it unknown past the restored point: only versions up to the
restored one count, and lag is then unknown. Lag is the number of the admission's finished
operations, in order, after the operation that ends the covered prefix: the `last_operation`
recorded for the window that ends it, found by identity in the latest snapshot, and unknown when
that snapshot does not hold it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import time
from typing import Callable
import uuid

from harness.trace.snapshot import ReadRefused, Snapshot, SnapshotError, BoundExceeded, stage
from harness.trace.stores import SealedStoreError, sealed

from .gate import COVERAGE, journal
from .knowledge import KnowledgeError, Repository
from .window import Window

STATUS_SCHEMA = 'curator-runner-status/1'
EXAMINED_SCHEMA = 'curator-runner-examined/1'
VERSION_SCHEMA = 'curator-runner-version/1'
POLL_SCHEMA = 'curator-runner-poll/1'
STOPPED_SCHEMA = 'curator-runner-stopped/1'
STATUS, EXAMINED, VERSIONS, POLLS, STOPPED, SNAPSHOTS = (
    'status.json', 'examined.jsonl', 'versions.jsonl', 'polls.jsonl', 'stopped.json', 'snapshots')
RECEIPT = 'receipt.json'  # the custodian's terminal receipt, written as it exits
SPEND_REFUSED = 'spend-reservation-refused'
SPEND_EXHAUSTED = 'spend-cap-exhausted'
FLEX_DEFERRED = 'flex-capacity-deferred'
HYGIENE_SUBCAP_EXHAUSTED = 'hygiene-subcap-exhausted'
UNKNOWN = 'unknown'
NOT_RUN = ('lock-refused', 'not-started', 'host-unavailable', HYGIENE_SUBCAP_EXHAUSTED)  # endings in which no session ran
SESSION_FAILURES = 2  # consecutive failed sessions that stop the runner
FLEX_DEFERRALS = 3  # consecutive flex capacity deferrals that stop the runner
SNAPSHOT_FAILURES = 3  # consecutive snapshots that failed or passed their bound
HARD_STOP_REASONS = ('proxy-revoked', 'proxy-unsettled', 'cleanup-unconfirmed')


class RunnerError(ValueError):
    """The runner's own files cannot be read under the current contract."""


@dataclass(frozen=True)
class Settings:
    """The trigger (`trigger_steps`, N), the window's ceiling, the poll interval and the cadence of
    looks at the tags while a session runs."""

    trigger_steps: int = 40
    ceiling_steps: int = 60
    poll_seconds: float = 15.0
    watch_seconds: float = 5.0

    def __post_init__(self):
        for name in ('trigger_steps', 'ceiling_steps'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if self.trigger_steps > self.ceiling_steps:
            raise ValueError('trigger_steps must not exceed ceiling_steps')
        for name in ('poll_seconds', 'watch_seconds'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not 0 < value < 86400:
                raise ValueError(f'{name} must be a positive number of seconds')


@dataclass(frozen=True)
class HygieneSettings:
    """Cadence, sub-cap and failure shutoff bounds for interleaved hygiene-only grooming."""

    enabled: bool = True
    min_windows: int = 5
    max_unexamined_steps: int = 10
    pass_cap_usd: Decimal = Decimal('0.30')
    max_spend_share: Decimal = Decimal('0.10')
    max_requests: int = 10
    wall_seconds: int = 90
    max_consecutive_failures: int = 2

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError('hygiene.enabled must be a boolean')
        for name in ('min_windows', 'max_requests', 'max_consecutive_failures'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'hygiene.{name} must be a positive integer')
        if type(self.max_unexamined_steps) is not int or self.max_unexamined_steps < 0:
            raise ValueError('hygiene.max_unexamined_steps must be a non-negative integer')
        if type(self.wall_seconds) is not int or self.wall_seconds <= 30:
            raise ValueError('hygiene.wall_seconds must be an integer exceeding 30')
        if not isinstance(self.pass_cap_usd, Decimal) or not self.pass_cap_usd.is_finite() or self.pass_cap_usd <= 0:
            raise ValueError('hygiene.pass_cap_usd must be a positive Decimal')
        if (not isinstance(self.max_spend_share, Decimal) or not self.max_spend_share.is_finite()
                or not (Decimal(0) <= self.max_spend_share <= Decimal(1))):
            raise ValueError('hygiene.max_spend_share must be a Decimal between 0 and 1')


@dataclass(frozen=True)
class ActorSteps:
    """One actor of a snapshot: step n is `operations[n - 1]`."""

    directory: str
    operations: tuple[str, ...]
    ended: bool
    actor_id: str | None = None


@dataclass(frozen=True)
class Reading:
    """What one snapshot shows: its staged directory (named as the run) and its actors in admission order."""

    directory: Path
    actors: tuple[ActorSteps, ...]
    hold_seconds: float
    transaction_seconds: float
    staging_seconds: float

    def finished(self) -> list[tuple[str, int, str]]:
        """The admission's finished operations in order, as (actor, step, operation)."""
        return [(a.directory, step, op) for a in self.actors for step, op in enumerate(a.operations, 1)]


@dataclass(frozen=True)
class Outcome:
    """What one session call returned. `state` is the session record's `sealed` or `aborted`, or None
    when no record came back; `refused` when the repository lock refused it before anything ran;
    `stop` a session stop reason, which the runner can act on."""

    state: str | None
    verdicts: tuple[dict, ...] = ()
    session_id: str | None = None
    refused: bool = False
    stop: str | None = None
    error: str | None = None
    details: dict = field(default_factory=dict)
    provider_error: bool = False


Snapshotter = Callable[[Path], Reading]  # stage into this new parent, or raise as `stage` does
Session = Callable[[Reading, Window, str], Outcome]  # run one session over a window, under a label
HygieneSession = Callable[[Reading, str], Outcome]  # run one text-only hygiene session, under a label
HygieneCheck = Callable[[], dict]  # deterministic hygiene_trigger(records) result
Look = Callable[[], dict[str, dict]]  # every tag: {version: {coverage, restored_from}}


def reading(snapshot: Snapshot) -> Reading:
    """The step order of a staged snapshot, read from its own fresh store as the projection orders it."""
    try:
        with sealed(snapshot.directory/'session.sqlite3') as db:
            rows = db.execute('SELECT id, actor FROM operations ORDER BY created_wall, id').fetchall()
    except (SealedStoreError, sqlite3.Error) as exc:
        raise SnapshotError(f'{snapshot.directory}: unreadable staged store: {exc}') from exc
    operations: dict[str, list[str]] = {a.actor_id: [] for a in snapshot.actors}
    for operation, actor in rows:
        if actor in operations:
            operations[actor].append(operation)
    actors = []
    for actor in snapshot.actors:
        found = operations[actor.actor_id]
        if len(found) != actor.steps or (found[-1] if found else None) != actor.last_operation:
            raise SnapshotError(f'{snapshot.directory}: actor {actor.directory} does not match its coverage')
        actors.append(ActorSteps(actor.directory, tuple(found), actor.ended, actor.actor_id))
    return Reading(snapshot.directory, tuple(actors), snapshot.hold_seconds, snapshot.transaction_seconds,
                   snapshot.staging_seconds)


def staged(run: Path) -> Snapshotter:
    """The real snapshot call: `stage` the live run into the given parent and read its step order."""
    return lambda parent: reading(stage(Path(run), parent))


class TagLook:
    """The real look at the knowledge repository: every version tag, its coverage stamp and, for a
    restore, the version it restored (from the gate's journal; `unknown` while that cannot be read)."""

    def __init__(self, repo: Repository):
        self.repo = repo
        self.coverage: dict[str, object] = {}

    def __call__(self) -> dict[str, dict]:
        try:
            restores = {row['version']: row['restored_from'] for row in journal(self.repo)
                        if row['operation'] == 'restore' and row['status'] == 'published'}
        except KnowledgeError:
            restores = None
        found = {}
        for tag in self.repo._tags():
            if tag not in self.coverage:
                try:
                    self.coverage[tag] = self.repo.provenance(tag).get('last_admission', {}).get('coverage')
                except (KnowledgeError, ValueError):
                    found[tag] = dict(coverage=UNKNOWN, restored_from=UNKNOWN)
                    continue
            found[tag] = dict(coverage=self.coverage[tag],
                              restored_from=UNKNOWN if restores is None else restores.get(tag))
        return found


def choose(read: Reading, cursor: dict[str, int], settings: Settings) -> Window | None:
    """The next window by the design's rule, or None when none is due.

    Actors are taken in admission order. An ended actor whose steps are all examined is passed; the
    first other actor is the one the cursor is in. Its steps beyond the cursor form a window when there
    are at least `trigger_steps` of them, or any at all once it has ended, and the window takes the
    oldest of them up to `ceiling_steps`.
    """
    for actor in read.actors:
        examined, finished = cursor.get(actor.directory, 0), len(actor.operations)
        waiting = finished - examined
        if waiting <= 0:
            if actor.ended:
                continue  # an empty tail is skipped
            return None
        if actor.ended or waiting >= settings.trigger_steps:
            return Window(read.directory.name, actor.directory, examined + 1,
                          examined + min(waiting, settings.ceiling_steps))
        return None
    return None


def covered(order: list[tuple[str, int | None, bool]], ranges: list[tuple[str, int, int]]) -> tuple[str, int] | None:
    """The end of the covered prefix: `order` is each actor in admission order with its finished steps
    (None when not known) and whether it has ended; `ranges` the (actor, first, last) of confirmed versions."""
    end = None
    for actor, finished, ended in order:
        reached = 0
        for first, last in sorted((f, l) for a, f, l in ranges if a == actor):
            if first > reached + 1:
                break
            reached = max(reached, last)
        if finished is not None:
            reached = min(reached, finished)
        if reached:
            end = (actor, reached)
        if not (ended and finished is not None and reached >= finished):
            break
    return end


def classify(outcome: Outcome) -> tuple[str, bool, bool]:
    """How a session ended, whether the cursor advances over its window, and whether it failed."""
    if outcome.refused:
        return 'lock-refused', False, False
    if outcome.stop == HYGIENE_SUBCAP_EXHAUSTED and outcome.state is None and outcome.error is None:
        return HYGIENE_SUBCAP_EXHAUSTED, False, False
    if (outcome.stop == FLEX_DEFERRED
            and not any(v.get('status') in ('published', 'unknown') for v in outcome.verdicts)):
        return FLEX_DEFERRED, False, False
    if (outcome.stop == SPEND_REFUSED and outcome.state == 'sealed'
            and not any(v.get('status') in ('published', 'unknown') for v in outcome.verdicts)):
        return SPEND_REFUSED, False, False
    if outcome.state is None and outcome.error is None and outcome.stop is not None:
        return ('host-unavailable' if outcome.stop.startswith('host-unavailable') else 'not-started'), False, False
    if outcome.state != 'sealed':
        return 'aborted', False, True
    statuses = [v.get('status') for v in outcome.verdicts if v.get('operation', 'submission') == 'submission']
    if outcome.provider_error:
        label = 'unconfirmed' if 'unknown' in statuses else 'rejected' if 'rejected' in statuses else 'provider-error'
        return label, any(status in ('published', 'unknown') for status in statuses), True
    if 'rejected' in statuses:
        return 'rejected', True, True
    if 'unknown' in statuses:
        return 'unconfirmed', True, True
    if 'published' in statuses:
        return 'accepted', True, False
    return 'nothing-submitted', True, False


def _number(version: str) -> int:
    return int(version[1:])


def _cut(path: Path) -> bytes:
    """An append-only file's whole lines, after cutting the file itself back to its last newline."""
    if not path.is_file():
        return b''
    data = path.read_bytes()
    whole = data.rfind(b'\n') + 1
    if whole < len(data):
        os.truncate(path, whole)
    return data[:whole]


def _lines(path: Path) -> list[dict]:
    """An append-only file's rows. A last line cut short by a killed writer is removed from the file
    before anything appends to it, so it is never joined to the next row."""
    rows = []
    for number, line in enumerate(_cut(path).splitlines(), 1):
        try:
            rows.append(json.loads(line))
        except ValueError:
            raise RunnerError(f'{path}:{number}: unreadable row') from None
    return rows


def _replace(path: Path, value: dict, *, indent: int | None = None) -> None:
    """Write a JSON file whole: a temporary file beside it, then a rename over it."""
    partial = path.with_name(f'.{path.name}.partial')
    partial.write_text(json.dumps(value, indent=indent, sort_keys=True, default=str) + '\n')
    os.replace(partial, path)


class Runner:
    """One runner over one live run. `poll` does one poll; `run` polls until the runner ends."""

    def __init__(self, directory: Path, session: str, *, snapshot: Snapshotter, session_call: Session, look: Look,
                 settings: Settings = Settings(), clock=time, sleep: Callable[[float], None] = time.sleep,
                 run: Path | None = None, hygiene_call: HygieneSession | None = None,
                 hygiene_check: HygieneCheck | None = None, hygiene_settings: HygieneSettings = HygieneSettings()):
        """`run` is the live run directory, checked at each poll for the custodian's receipt."""
        self.directory, self.session, self.run_directory = Path(directory), session, run
        self.snapshot, self.session_call, self.look = snapshot, session_call, look
        self.hygiene_call, self.hygiene_check, self.hygiene_settings = hygiene_call, hygiene_check, hygiene_settings
        self.settings, self.clock, self.sleep = settings, clock, sleep
        self.directory.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.directory/SNAPSHOTS, ignore_errors=True)  # a killed runner's staged snapshot
        _cut(self.directory/POLLS)
        self.rows = _lines(self.directory/EXAMINED)
        if any(row.get('schema') != EXAMINED_SCHEMA for row in self.rows):
            raise RunnerError(f'{self.directory/EXAMINED}: not {EXAMINED_SCHEMA}')
        self.versions: dict[str, dict] = {}
        for row in _lines(self.directory/VERSIONS):
            if row.get('schema') != VERSION_SCHEMA:
                raise RunnerError(f'{self.directory/VERSIONS}: not {VERSION_SCHEMA}')
            self.versions[row['version']] = row
        self.baseline = not self.versions and not (self.directory/VERSIONS).exists()
        self.lock = threading.RLock()
        self.last_look_began: float | None = None
        self.look_error: str | None = None
        self.last: Reading | None = None
        self.read_wall: dict | None = None
        self.current: dict | None = None
        self.snapshot_failures = 0
        self.state, self.reason = 'polling', None
        if (self.directory/STOPPED).is_file():
            stopped = json.loads((self.directory/STOPPED).read_text())
            self.state, self.reason = 'stopped', stopped.get('reason', UNKNOWN)

    # The record -----------------------------------------------------------------------------------

    def _append(self, name: str, row: dict) -> None:
        with (self.directory/name).open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True, default=str) + '\n')

    def _ends(self) -> list[dict]:
        return [row for row in self.rows if row['event'] == 'end']

    @property
    def cursor(self) -> dict[str, int]:
        cursor: dict[str, int] = {}
        for row in self._ends():
            if row['advanced'] and row.get('session_kind', 'admission') != 'hygiene' and isinstance(row.get('window'), dict):
                actor = row['window']['actor']
                cursor[actor] = max(cursor.get(actor, 0), row['window']['last'])
        return cursor

    def examined(self) -> list[dict]:
        """Every session the runner started, in order, with how it ended (`interrupted` for a start with no end)."""
        ends = {row['label']: row for row in self._ends()}
        listed = []
        for row in self.rows:
            if row['event'] != 'start':
                continue
            end = ends.get(row['label'])
            if end is not None and end['outcome'] in NOT_RUN:
                continue  # nothing ran over this range
            entry = dict(label=row['label'], window=row['window'], session_id=end and end['session_id'],
                         outcome=end['outcome'] if end else ('in-session' if self.current and
                                                             self.current['label'] == row['label'] else 'interrupted'),
                         advanced=bool(end and end['advanced']), started_wall=row['started_wall'],
                         ended_wall=end and end['ended_wall'])
            if row.get('session_kind') == 'hygiene':
                entry['session_kind'] = 'hygiene'
            listed.append(entry)
        return listed

    def session_failures(self) -> int:
        count = 0
        for row in reversed(self._ends()):
            if row.get('session_kind') == 'hygiene':
                continue
            if row['outcome'] in (*NOT_RUN, 'interrupted', SPEND_REFUSED, FLEX_DEFERRED):
                continue
            if not row['failed']:
                break
            count += 1
        return count

    def flex_deferrals(self) -> int:
        count = 0
        for row in reversed(self._ends()):
            if row.get('session_kind') == 'hygiene':
                continue
            if row['outcome'] in (*NOT_RUN, 'interrupted'):
                continue
            if row['outcome'] != FLEX_DEFERRED:
                break
            count += 1
        return count

    def hygiene_failures(self) -> int:
        count = 0
        for row in reversed(self._ends()):
            if row.get('session_kind') != 'hygiene':
                continue
            if row['outcome'] in (*NOT_RUN, 'interrupted', FLEX_DEFERRED):
                continue
            if not row['failed']:
                break
            count += 1
        return count

    def _last_clean_hygiene_digest(self) -> str | None:
        for row in reversed(self._ends()):
            if row.get('session_kind') != 'hygiene':
                continue
            if row['outcome'] in ('accepted', 'nothing-submitted') and not row['failed']:
                digest = (row.get('details') or {}).get('hygiene_digest')
                if isinstance(digest, str):
                    return digest
        return None

    def _confirmed_windows_since_hygiene(self) -> int:
        confirmed, _, _ = self.publications()
        confirmed_labels = {c['label'] for c in confirmed}
        count = 0
        for row in reversed(self._ends()):
            if row.get('session_kind') == 'hygiene':
                if row['outcome'] == HYGIENE_SUBCAP_EXHAUSTED or row['outcome'] not in (*NOT_RUN, 'interrupted'):
                    break
                continue
            if row['label'] in confirmed_labels:
                count += 1
        return count

    def hygiene_publications(self) -> list[str]:
        """Confirmed hygiene-published versions (tag seen, not a restore)."""
        versions = []
        for row in self._ends():
            if row.get('session_kind') != 'hygiene':
                continue
            for verdict in row['verdicts']:
                version = verdict.get('version')
                if verdict.get('status') == 'published' and version:
                    entry = self.versions.get(version)
                    if entry is not None and entry.get('restored_from') is None:
                        versions.append(version)
        return sorted(set(versions), key=_number)

    # The publication watch ------------------------------------------------------------------------

    def _look(self) -> None:
        began = self.clock.time()
        try:
            seen = self.look()
        except Exception as exc:  # noqa: BLE001 - a failed look is recorded, and the next one tries again
            with self.lock:
                self.look_error = f'{type(exc).__name__}: {exc}'
            return
        ended = self.clock.time()
        with self.lock:
            self.look_error = None
            for version, info in sorted(seen.items(), key=lambda item: _number(item[0])):
                entry = self.versions.get(version)
                if entry is None:
                    entry = dict(schema=VERSION_SCHEMA, version=version, baseline=self.baseline,
                                 last_absent_began_wall=UNKNOWN if self.baseline or self.last_look_began is None
                                 else self.last_look_began,
                                 first_present_ended_wall=ended, coverage=info['coverage'],
                                 restored_from=info['restored_from'])
                elif (entry['coverage'], entry['restored_from']) != (info['coverage'], info['restored_from']) \
                        and UNKNOWN not in (info['coverage'], info['restored_from']):
                    entry = dict(entry, coverage=info['coverage'], restored_from=info['restored_from'])
                else:
                    continue
                self.versions[version] = entry
                self._append(VERSIONS, entry)
            self.baseline = False
            self.last_look_began = began

    def _watching(self) -> tuple[threading.Event, threading.Thread]:
        stop = threading.Event()

        def loop():
            while not stop.wait(self.settings.watch_seconds):
                self._look()

        thread = threading.Thread(target=loop, name='curator-runner-watch', daemon=True)
        thread.start()
        return stop, thread

    # Coverage -------------------------------------------------------------------------------------

    def _stamp(self, window: dict) -> dict:
        return dict(schema=COVERAGE, session=window['session'], actor=window['actor'], last_step=window['last'])

    def publications(self) -> tuple[list[dict], list[dict], dict | None]:
        """Confirmed versions with their windows, publications that could not be confirmed, and the
        earliest restore seen in this admission (None if none)."""
        claims: dict[str, dict] = {}
        hygiene_versions: set[str] = set()
        unconfirmed = []
        for row in self._ends():
            if row.get('session_kind') == 'hygiene':
                for verdict in row['verdicts']:
                    if verdict.get('status') == 'published' and verdict.get('version'):
                        hygiene_versions.add(verdict['version'])
                continue
            for verdict in row['verdicts']:
                if verdict.get('status') == 'published' and verdict.get('version'):
                    claims[verdict['version']] = row
                elif verdict.get('status') == 'unknown':
                    unconfirmed.append(dict(version=verdict.get('version') or UNKNOWN, label=row['label'],
                                            reason='the gate result is unknown'))
        starts = {row['label']: row for row in self.rows if row['event'] == 'start'}
        confirmed = []
        for version, row in sorted(claims.items(), key=lambda item: _number(item[0])):
            entry = self.versions.get(version)
            if entry is None:
                unconfirmed.append(dict(version=version, label=row['label'], reason='its tag was not seen'))
            elif entry['coverage'] != self._stamp(row['window']):
                unconfirmed.append(dict(version=version, label=row['label'], coverage=entry['coverage'],
                                        reason='its coverage stamp is not its window'))
            else:
                start = starts.get(row['label'], {})
                confirmed.append(dict(version=version, label=row['label'], window=row['window'],
                                      last_operation=start.get('last_operation', UNKNOWN), coverage=entry['coverage']))
        restore = None
        for version, entry in sorted(self.versions.items(), key=lambda item: _number(item[0])):
            if entry['baseline'] or version in claims or version in hygiene_versions:
                continue
            if entry['restored_from'] is None:
                unconfirmed.append(dict(version=version, label=None, reason='no examined session reports it'))
            elif restore is None:
                point = (_number(entry['restored_from']) if entry['restored_from'] != UNKNOWN
                         else _number(version) - 1)
                restore = dict(version=version, restored_from=entry['restored_from'], counted_through=f'v{point}')
        return confirmed, unconfirmed, restore

    def _order(self) -> list[tuple[str, int | None, bool]]:
        if self.last is not None:
            known = [(a.directory, len(a.operations), a.ended) for a in self.last.actors]
        else:
            known = []
        listed = {actor for actor, _, _ in known}
        extra = sorted({row['window']['actor'] for row in self.rows
                        if isinstance(row.get('window'), dict) and row['window'].get('actor')} - listed)
        return known + [(actor, None, False) for actor in extra]

    def _place(self, actor: str, step: int) -> dict:
        """A step, with its operation and its position among the admission's finished operations."""
        if self.last is not None:
            for ordinal, (name, number, operation) in enumerate(self.last.finished(), 1):
                if (name, number) == (actor, step):
                    return dict(actor=actor, step=step, operation=operation, ordinal=ordinal)
        return dict(actor=actor, step=step, operation=UNKNOWN, ordinal=UNKNOWN)

    def _identify(self, actor: str, step: int, operation: str) -> dict:
        """The step that ends the covered prefix, placed among the latest snapshot's finished operations
        by its recorded operation's identity; unknown when the snapshot does not hold it."""
        if self.last is not None and operation != UNKNOWN:
            for ordinal, (_, _, found) in enumerate(self.last.finished(), 1):
                if found == operation:
                    return dict(actor=actor, step=step, operation=operation, ordinal=ordinal)
        return dict(actor=actor, step=step, operation=operation, ordinal=UNKNOWN)

    def coverage(self) -> dict:
        """The covered prefix, lag, the distance from the latest stamp, backlog and the last confirmed version."""
        confirmed, unconfirmed, restore = self.publications()
        counted = [c for c in confirmed if restore is None or _number(c['version']) <= _number(restore['counted_through'])]
        end = covered(self._order(), [(c['window']['actor'], c['window']['first'], c['window']['last'])
                                      for c in counted])
        if end is None:
            prefix = dict(end=None, restore=restore)
        else:
            # The end is the last step of a counted window; that window recorded the operation there.
            operation = next((c['last_operation'] for c in reversed(counted)
                              if (c['window']['actor'], c['window']['last']) == end), UNKNOWN)
            prefix = dict(end=self._identify(*end, operation), restore=restore)
        total = len(self.last.finished()) if self.last is not None else None
        if total is None or restore is not None:
            lag = UNKNOWN
        elif end is None:
            lag = total
        else:
            ordinal = prefix['end']['ordinal']
            lag = UNKNOWN if ordinal == UNKNOWN else total - ordinal
        published = [v for v in self.versions.values()]
        latest = max(published, key=lambda v: _number(v['version'])) if published else None
        distance = UNKNOWN
        stamp = latest['coverage'] if latest else None
        if (total is not None and isinstance(stamp, dict) and stamp.get('session') == self.session
                and stamp.get('actor') and type(stamp.get('last_step')) is int):
            place = self._place(stamp['actor'], stamp['last_step'])
            distance = UNKNOWN if place['ordinal'] == UNKNOWN else total - place['ordinal']
        if self.last is None:
            backlog = UNKNOWN
        else:
            cursor = self.cursor
            backlog = sum(max(0, len(a.operations) - cursor.get(a.directory, 0)) for a in self.last.actors)
        return dict(covered_prefix=prefix, lag=lag, stamp_distance=distance, backlog=backlog,
                    last_confirmed=confirmed[-1] if confirmed else None, unconfirmed=unconfirmed,
                    latest_version=dict(version=latest['version'], coverage=latest['coverage']) if latest else UNKNOWN)

    def progress(self) -> dict:
        """The covered prefix, lag and backlog, as of the last successful read (`as_of`): the `coverage` of
        each poll row and each examined row."""
        with self.lock:
            now = self.coverage()
            return dict({name: now[name] for name in ('covered_prefix', 'lag', 'backlog')}, as_of=self.position())

    def position(self) -> dict | str:
        """The latest finished operation of the last snapshot, and when that snapshot read the store."""
        if self.last is None:
            return UNKNOWN
        finished = self.last.finished()
        if not finished:
            return dict(actor=None, step=0, operation=None, ordinal=0, read_wall=self.read_wall)
        actor, step, operation = finished[-1]
        return dict(actor=actor, step=step, operation=operation, ordinal=len(finished), read_wall=self.read_wall)

    def unexamined(self) -> list[dict] | str:
        """The finished steps of the last snapshot the cursor has not passed; steps finished after it
        are unexamined too and not counted."""
        if self.last is None:
            return UNKNOWN
        cursor = self.cursor
        return [dict(actor=a.directory, first=cursor.get(a.directory, 0) + 1, last=len(a.operations))
                for a in self.last.actors if len(a.operations) > cursor.get(a.directory, 0)]

    def status(self) -> dict:
        """The status file's content. Lag, backlog and `unexamined` count only what the last successful read
        saw, whose position and wall time are `as_of`; `after_last_read` is always `unknown`, because steps
        finished after that read are not known to the runner (after the custodian ends it reads no more, and
        they are counted afterwards from the sealed session)."""
        with self.lock:
            snapshot = UNKNOWN if self.last is None else dict(
                hold_seconds=self.last.hold_seconds, transaction_seconds=self.last.transaction_seconds,
                staging_seconds=self.last.staging_seconds, read_wall=self.read_wall)
            done = self.state in ('stopped', 'ended')
            return dict(schema=STATUS_SCHEMA, session=self.session, state=self.state, updated_wall=self.clock.time(),
                        settings=asdict(self.settings), position=self.position(), snapshot=snapshot,
                        examined=self.examined(), cursor=self.cursor, current=self.current,
                        **self.coverage(), failures=dict(sessions=self.session_failures(),
                                                         snapshots=self.snapshot_failures),
                        versions=sorted(self.versions.values(), key=lambda v: _number(v['version'])),
                        look_error=self.look_error, stop_reason=self.reason, as_of=self.position(),
                        after_last_read=UNKNOWN, unexamined=self.unexamined() if done else None)

    def _write_status(self) -> None:
        with self.lock:
            _replace(self.directory/STATUS, self.status(), indent=1)

    def _finish(self, state: str, reason: str) -> None:
        self.state, self.reason = state, reason
        if state == 'stopped' and not (self.directory/STOPPED).exists():
            _replace(self.directory/STOPPED, dict(schema=STOPPED_SCHEMA, reason=reason, wall=self.clock.time()))
        self._write_status()

    # Polling --------------------------------------------------------------------------------------

    @property
    def done(self) -> bool:
        return self.state in ('stopped', 'ended')

    def poll(self) -> bool:
        """One poll; False once the runner has ended or stopped, after which it never reads again."""
        if self.done:
            return False
        parent = self.directory/SNAPSHOTS/uuid.uuid4().hex
        try:
            parent.mkdir(parents=True)
            return self._poll(parent)
        except KeyboardInterrupt:
            if self.current is not None:  # the session leaves its own aborted record
                self._end(self.current['label'], Outcome(state=None, error='interrupted'), ('interrupted', False, False))
            self._finish('ended', 'interrupted')
            raise
        finally:
            shutil.rmtree(parent, ignore_errors=True)  # a snapshot is never kept past its poll

    def _poll(self, parent: Path) -> bool:
        began = self.clock.time()
        row = dict(schema=POLL_SCHEMA, began_wall=began)
        if self.run_directory is not None and os.path.lexists(self.run_directory/RECEIPT):
            # The custodian has ended, with or without a closing marker (one that died writes none).
            self._append(POLLS, dict(row, ended_wall=self.clock.time(), outcome='custodian-ended',
                                     coverage=self.progress()))
            self._finish('ended', 'store-closed')
            return False
        try:
            read = self.snapshot(parent)
        except ReadRefused as refused:
            self._append(POLLS, dict(row, ended_wall=self.clock.time(), outcome=f'refused:{refused.reason}',
                                     coverage=self.progress()))
            if refused.reason == 'closing':
                self._finish('ended', 'store-closing')  # the custodian is closing: no further read
                return False
            if refused.reason == 'no-store':
                self._write_status()  # play has not begun: wait for the next poll
                return True
            self._finish('stopped', f'read refused: {refused.reason}')
            return False
        except SnapshotError as error:
            self.snapshot_failures += 1
            kind = 'over-bound' if isinstance(error, BoundExceeded) else 'failed'
            self._append(POLLS, dict(row, ended_wall=self.clock.time(), outcome=kind, error=str(error)[:400],
                                     coverage=self.progress()))
            if self.snapshot_failures >= SNAPSHOT_FAILURES:
                self._finish('stopped', f'{SNAPSHOT_FAILURES} consecutive snapshots failed or passed their bound')
                return False
            self._write_status()
            return True
        self.snapshot_failures = 0
        with self.lock:
            self.last, self.read_wall = read, dict(began=began, ended=self.clock.time())
        self._append(POLLS, dict(row, ended_wall=self.read_wall['ended'], outcome='read',
                                 hold_seconds=read.hold_seconds, transaction_seconds=read.transaction_seconds,
                                 staging_seconds=read.staging_seconds, position=self.position(),
                                 coverage=self.progress()))
        window = choose(read, self.cursor, self.settings)
        if window is None:
            trigger = self._due_hygiene(read)
            if trigger is not None:
                return self._hygiene_session(read, trigger)
            self._write_status()
            return True
        return self._session(read, window)

    def _due_hygiene(self, read: Reading) -> dict | None:
        """Return the deterministic hygiene trigger payload when an interleaved hygiene pass is eligible."""
        hs = self.hygiene_settings
        if not hs.enabled or self.hygiene_call is None or self.hygiene_check is None:
            return None
        if self.hygiene_failures() >= hs.max_consecutive_failures:
            return None
        cursor = self.cursor
        backlog = sum(max(0, len(a.operations) - cursor.get(a.directory, 0)) for a in read.actors)
        if backlog > hs.max_unexamined_steps:
            return None
        if self._confirmed_windows_since_hygiene() < hs.min_windows:
            return None
        available = getattr(self.hygiene_call, 'available', None)
        if callable(available):
            try:
                if not available():
                    return None
            except Exception:  # noqa: BLE001 - a hygiene preflight error never halts ingestion
                return None
        try:
            trigger = self.hygiene_check()
        except Exception:  # noqa: BLE001 - a hygiene check error never halts ingestion
            return None
        if not isinstance(trigger, dict) or not trigger.get('triggered'):
            return None
        digest = trigger.get('digest')
        if isinstance(digest, str) and digest == self._last_clean_hygiene_digest():
            return None
        return trigger

    def _hygiene_session(self, read: Reading, trigger: dict) -> bool:
        label = f'hygiene-{uuid.uuid4().hex[:8]}'
        self._look()
        start = dict(schema=EXAMINED_SCHEMA, event='start', session_kind='hygiene', label=label, window=None,
                     hygiene_trigger=dict(digest=trigger.get('digest'), reasons=trigger.get('reasons', []),
                                          counts=trigger.get('counts', {})),
                     started_wall=self.clock.time(), coverage=self.progress())
        with self.lock:
            self.rows.append(start)
            self._append(EXAMINED, start)
            self.current = dict(label=label, session_kind='hygiene', window=None, started_wall=start['started_wall'])
        self.state = 'in-session'
        self._write_status()
        stop, watcher = self._watching()
        try:
            outcome = self.hygiene_call(read, label)
        except Exception as exc:  # noqa: BLE001 - a failed hygiene pass never crashes ingestion
            outcome = Outcome(state=None, error=f'{type(exc).__name__}: {str(exc)[:400]}')
        finally:
            stop.set()
            watcher.join()
        self._look()
        name, _, failed = classify(outcome)
        if outcome.stop == SPEND_REFUSED:
            failed = True
        details = dict(outcome.details)
        if not failed and name in ('accepted', 'nothing-submitted') and isinstance(trigger.get('digest'), str):
            details['hygiene_digest'] = trigger['digest']
        annotated = Outcome(state=outcome.state, verdicts=outcome.verdicts, session_id=outcome.session_id,
                            refused=outcome.refused, stop=outcome.stop, error=outcome.error, details=details,
                            provider_error=outcome.provider_error)
        self._end(label, annotated, (name, False, failed))
        if outcome.stop in HARD_STOP_REASONS:
            self._finish('stopped', outcome.stop)
            return False
        self.state = 'polling'
        self._write_status()
        return True

    def _session(self, read: Reading, window: Window) -> bool:
        label = f'{window.actor}-{window.first}-{window.last}-{uuid.uuid4().hex[:8]}'
        operations = next(a.operations for a in read.actors if a.directory == window.actor)
        record = window.record()
        self._look()  # once before the session starts
        start = dict(schema=EXAMINED_SCHEMA, event='start', label=label, window=record,
                     first_operation=operations[window.first - 1], last_operation=operations[window.last - 1],
                     started_wall=self.clock.time(), coverage=self.progress())
        with self.lock:
            self.rows.append(start)
            self._append(EXAMINED, start)
            self.current = dict(label=label, window=record, started_wall=start['started_wall'])
        self.state = 'in-session'
        self._write_status()
        stop, watcher = self._watching()
        try:
            outcome = self.session_call(read, window, label)
        except Exception as exc:  # noqa: BLE001 - a session that raised is a failed session, not a crashed runner
            outcome = Outcome(state=None, error=f'{type(exc).__name__}: {str(exc)[:400]}')
        finally:
            stop.set()
            watcher.join()
        self._look()  # once after it returns
        how = classify(outcome)
        self._end(label, outcome, how)
        if outcome.stop == FLEX_DEFERRED:
            if how[0] == FLEX_DEFERRED:
                if self.flex_deferrals() >= FLEX_DEFERRALS:
                    self._finish('stopped', FLEX_DEFERRED)
                    return False
                self.state = 'polling'
                self._write_status()
                return True
            if not how[1]:
                self._finish('stopped', FLEX_DEFERRED)
                return False
            # Validated prefix advanced; fall through to the shared session_failures check.
        elif outcome.stop == SPEND_REFUSED:
            # Per #1027: blind step halving is removed. Any gate-confirmed close-out publication
            # already advanced covered_prefix via _end; stop cleanly as SPEND_EXHAUSTED either way.
            self._finish('stopped', SPEND_EXHAUSTED)
            return False
        elif outcome.stop is not None:
            self._finish('stopped', outcome.stop)
            return False
        if self.session_failures() >= SESSION_FAILURES:
            self._finish('stopped', f'{SESSION_FAILURES} consecutive failed sessions')
            return False
        self.state = 'polling'
        self._write_status()
        return True

    def _end(self, label: str, outcome: Outcome, how: tuple[str, bool, bool]) -> None:
        name, advanced, failed = how
        start = next(row for row in self.rows if row['event'] == 'start' and row['label'] == label)
        end = dict(schema=EXAMINED_SCHEMA, event='end', label=label, window=start['window'],
                   session_id=outcome.session_id, outcome=name, advanced=advanced, failed=failed,
                   state=outcome.state, error=outcome.error, stop=outcome.stop,
                   verdicts=[dict(operation=v.get('operation'), status=v.get('status'), version=v.get('version'))
                             for v in outcome.verdicts],
                   details=outcome.details, ended_wall=self.clock.time())
        if start.get('session_kind') == 'hygiene':
            end['session_kind'] = 'hygiene'
        with self.lock:
            self.rows.append(end)
            self.current = None
            end['coverage'] = self.progress()  # with this session's own result counted
            self._append(EXAMINED, end)

    def run(self) -> str:
        """Poll until the runner ends or stops; returns why. An interruption is recorded and raised; so
        is an unexpected exception, recorded as a stop for `error: <type>` as far as the files allow."""
        if self.done:
            self._write_status()
            return self.reason
        try:
            self._look()
            self._write_status()
            while self.poll():
                self.sleep(self.settings.poll_seconds)
        except KeyboardInterrupt:
            if not self.done:
                self._finish('ended', 'interrupted')
            raise
        except Exception as exc:
            if not self.done:
                self.current = None
                try:
                    self._finish('stopped', f'error: {type(exc).__name__}')
                except Exception as failure:  # noqa: BLE001 - the original exception stays primary
                    exc.add_note(f'Recording the stop failed: {type(failure).__name__}')
            raise
        return self.reason
