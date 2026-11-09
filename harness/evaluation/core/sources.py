"""Read-only access to one run directory (docs/contracts/evaluation.md, Inputs).

Opens `session.sqlite3` with `mode=ro` and a one-second busy timeout, reads
`actors/NNN/host.jsonl`, `manifest.json`, the handoff contexts and the run's
player-memory/2 store. A live run may grow while it is read: `after_seq` returns only
newer operations and `settled_only` stops at the first operation whose terminal state is
not yet recorded, so an incremental pass never skips a later-settled operation.
A missing or unsupported input names its file and version; nothing is guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Iterator

from harness.jsonio import file_sha256

from .records import EvaluationError, loads

SESSION_SCHEMA = 'computer-session/1'
OPERATION_SCHEMA = 'computer-operation/1'
HOST_SCHEMA = 'player-host/3'
#: `campaign-run/5` adds the operator labels. `campaign-run/4` is archive-read only: the closed set of development-loop
#: sessions in `data/evaluation/archive-labels.json` (keyed by session ID), which also holds their operator labels.
MANIFEST_SCHEMAS = ('campaign-run/4', 'campaign-run/5')
ARCHIVE_SCHEMA = 'campaign-run/4'
ARCHIVE_LABELS = Path(__file__).resolve().parents[3] / 'data' / 'evaluation' / 'archive-labels.json'
RECEIPT_SCHEMA = 'campaign-receipt/3'
#: `campaign-watch-terminal/2` is archive-read only (the archived runs predate Pause reasons).
WATCH_TERMINAL_SCHEMA = 'campaign-watch-terminal/3'
WATCH_TERMINAL_ARCHIVE_SCHEMA = 'campaign-watch-terminal/2'
MEMORY_SCHEMA = 'player-memory/2'
CONTEXT_SCHEMA = 'player-handoff-context/1'
BUSY_TIMEOUT_SECONDS = 1.0
#: Bounds of one JSON file and of one host trace (4096 traces and 8 GiB are `host-summary`'s selection bounds).
MAX_JSON_FILE_BYTES = 16 * 1024 * 1024
MAX_HOST_LINE_BYTES = 64 * 1024 * 1024
MAX_HOST_EVENTS = 2_000_000


@dataclass(frozen=True)
class Operation:
    seq: int
    operation_id: str
    actor: str
    kind: str
    created_wall: float
    status: str
    reason: str | None
    actions: tuple[dict, ...] | None
    source_id: str | None
    sha256: str | None
    png: Path | None
    receipts: tuple[dict, ...]
    handoff: dict | None


@dataclass(frozen=True)
class HostEvent:
    actor: str
    line: int
    type: str
    wall: float | None
    monotonic_ms: float | None
    fields: dict


@dataclass(frozen=True)
class MemoryFacts:
    path: Path
    records: dict[str, dict]
    programs: dict[str, dict]


@dataclass(frozen=True)
class EndFacts:
    """How the run ended, from the custodian's `receipt.json` and the gateway's `watch-terminal.json`.
    Both are absent while a run is live; every field is then None or empty."""

    outcome: str | None = None
    ending_trigger: str | None = None
    settled: tuple[dict, ...] = ()
    finishes: tuple[str | None, ...] = ()
    paused: bool = False
    pause_reason: str | None = None


@dataclass(frozen=True)
class RunInputs:
    run_dir: Path
    session: str
    manifest: dict
    operations: tuple[Operation, ...]
    last_seq: int | None
    actors: tuple[str, ...]
    host: dict[str, tuple[HostEvent, ...]]
    carry: dict[str, frozenset[str]]
    memory: MemoryFacts | None
    digests: dict[str, str] = field(default_factory=dict)
    end: EndFacts = field(default_factory=EndFacts)


def read_json_file(path: Path, maximum: int = MAX_JSON_FILE_BYTES) -> object:
    """One bounded JSON file, decoded by `records.loads`; a file over `maximum` bytes is an error."""
    if path.stat().st_size > maximum:
        raise EvaluationError(f'{path}: larger than {maximum} bytes')
    return loads(path.read_bytes(), str(path))


def read_json_lines(path: Path, maximum: int = MAX_JSON_FILE_BYTES) -> list[object]:
    """The documents of one bounded JSON-lines file; a blank line is skipped."""
    if path.stat().st_size > maximum:
        raise EvaluationError(f'{path}: larger than {maximum} bytes')
    return [loads(line, f'{path}:{number}') for number, line in enumerate(path.read_bytes().splitlines(), 1) if line.strip()]


def read_manifest(run_dir: Path) -> dict:
    path = run_dir / 'manifest.json'
    if not path.is_file():
        raise EvaluationError(f'{path}: missing campaign-run manifest')
    value = read_json_file(path)
    if not isinstance(value, dict) or value.get('schema') not in MANIFEST_SCHEMAS:
        found = value.get('schema') if isinstance(value, dict) else None
        raise EvaluationError(f'{path}: unsupported manifest version {found!r}; expected one of {", ".join(MANIFEST_SCHEMAS)}')
    if value['schema'] == ARCHIVE_SCHEMA and value.get('session') not in archive_labels():
        raise EvaluationError(f'{path}: {ARCHIVE_SCHEMA} is read only for the archived sessions listed in '
            f'{ARCHIVE_LABELS.name}; session {value.get("session")!r} is not listed')
    return value


def archive_labels() -> dict[str, dict]:
    """The archived campaign-run/4 sessions: session ID to `{run, arm, start, scenario, lineage, admission}`."""
    if not ARCHIVE_LABELS.is_file():
        return {}
    value = read_json_file(ARCHIVE_LABELS)
    runs = value.get('runs') if isinstance(value, dict) else None
    return {key: item for key, item in runs.items() if isinstance(item, dict)} if isinstance(runs, dict) else {}


def _connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise EvaluationError(f'{path}: missing database')
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=BUSY_TIMEOUT_SECONDS)


def _session_connection(path: Path) -> tuple[sqlite3.Connection, str]:
    connection = _connect_readonly(path)
    try:
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        rows = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN ('schema','session')"))
    except sqlite3.Error as exc:
        connection.close()
        raise EvaluationError(f'{path}: cannot read {SESSION_SCHEMA} ({exc})') from exc
    schema = loads(rows['schema'], str(path)) if 'schema' in rows else None
    if version != 1 or schema != SESSION_SCHEMA:
        connection.close()
        raise EvaluationError(f'{path}: unsupported session version {schema!r} (user_version {version}); expected {SESSION_SCHEMA}')
    session = loads(rows.get('session', 'null'), str(path))
    if not isinstance(session, str) or not session:
        connection.close()
        raise EvaluationError(f'{path}: missing session identity')
    return connection, session


def read_operations(run_dir: Path, *, after_seq: int | None = None, settled_only: bool = False) -> tuple[str, list[Operation]]:
    """Operations in created order; `seq` is the store's insertion row number."""
    path = run_dir / 'session.sqlite3'
    connection, session = _session_connection(path)
    try:
        sources = {identity: loads(encoded, f'{path}:sources') for identity, encoded in connection.execute(
            'SELECT id,metadata FROM sources')}
        receipts: dict[str, list[dict]] = {}
        for operation, encoded in connection.execute(
                'SELECT operation,receipt FROM native_intents WHERE receipt IS NOT NULL ORDER BY rowid'):
            receipts.setdefault(operation, []).append(loads(encoded, f'{path}:native_intents'))
        operations = []
        rows = connection.execute('SELECT rowid,id,actor,kind,created_wall,input_json,final_json FROM operations '
            'WHERE rowid > ? ORDER BY rowid', (after_seq or 0,)).fetchall()
    except sqlite3.Error as exc:
        raise EvaluationError(f'{path}: cannot read {SESSION_SCHEMA} operations ({exc})') from exc
    finally:
        connection.close()
    for seq, identity, actor, kind, created, encoded_input, encoded_final in rows:
        final = loads(encoded_final, f'{path}:{identity}')
        if encoded_final is None and settled_only:
            break
        if final is not None and (not isinstance(final, dict) or final.get('schema') != OPERATION_SCHEMA
                or final.get('operation_id') != identity):
            found = final.get('schema') if isinstance(final, dict) else None
            raise EvaluationError(f'{path}: operation {identity} has unsupported version {found!r}; expected {OPERATION_SCHEMA}')
        final = final or {}
        source = final.get('source')
        source_id = source.get('source_id') if isinstance(source, dict) else None
        sha = None
        if source_id is not None:
            indexed = sources.get(source_id)
            sha = (indexed or source).get('sha256')
        png = run_dir / 'sources' / f'{source_id}.png' if source_id is not None else None
        actions = loads(encoded_input, f'{path}:{identity}')
        operations.append(Operation(seq, identity, actor, kind, float(created), final.get('status', 'pending'),
            final.get('reason'), tuple(actions) if isinstance(actions, list) else None, source_id, sha,
            png if png is not None and png.is_file() else None, tuple(receipts.get(identity, ())),
            final.get('handoff') if isinstance(final.get('handoff'), dict) else None))
    return session, operations


def _wall(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _milliseconds(value: object) -> float | None:
    try:
        return float(value) if type(value) in (int, float) else None
    except OverflowError:  # an integer beyond the float range is not a clock reading
        return None


class HostTraceUnsupported(EvaluationError):
    """A host trace that is not a current `player-host/3` trace. `kind` is `empty` (no event), `format` (the first
    event is not a `host-start`) or `version` (a `host-start` of another schema or telemetry version)."""

    def __init__(self, message: str, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


def iter_host(path: Path, actor_hint: str, *, partial_tail: bool = False) -> Iterator[HostEvent]:
    """Stream one player-host/3 trace: the one offline parser of `host.jsonl` (the evaluator, the viewer and
    host-summary). The supervisor's live incremental reader in tools/campaign_player.py stays separate because
    evaluation never gates the control path (ADR008).

    Bounded: a line over `MAX_HOST_LINE_BYTES`, or more than `MAX_HOST_EVENTS` lines, is an error. A blank line is
    skipped. A duplicate key, a non-finite number or an event without a string `type` is an error. An unterminated
    final line that does not parse is an error too, unless `partial_tail` (a trace may still be appending) ignores
    it. A newline-terminated malformed line is always an error."""
    actor = actor_hint
    count = 0
    with path.open('rb') as stream:
        number = 0
        while line := stream.readline(MAX_HOST_LINE_BYTES + 1):
            number += 1
            if len(line) > MAX_HOST_LINE_BYTES:
                raise EvaluationError(f'{path}:{number}: trace line exceeds {MAX_HOST_LINE_BYTES} bytes')
            if number > MAX_HOST_EVENTS:
                raise EvaluationError(f'{path}: trace exceeds {MAX_HOST_EVENTS} lines')
            if not line.strip():
                continue
            try:
                event = loads(line, f'{path}:{number}')
            except EvaluationError:
                if partial_tail and not line.endswith(b'\n'):
                    break
                raise
            if not isinstance(event, dict):
                raise EvaluationError(f'{path}:{number}: expected an event object')
            if not count:
                if event.get('type') != 'host-start':
                    raise HostTraceUnsupported(f"{path}: not a host trace; the first event is {event.get('type')!r}", 'format')
                if event.get('schema') != HOST_SCHEMA or type(event.get('telemetry_version')) is not int or event['telemetry_version'] != 3:
                    raise HostTraceUnsupported(f"{path}: unsupported host trace version {event.get('schema')!r}/"
                        f"{event.get('telemetry_version')!r}; expected {HOST_SCHEMA} telemetry 3", 'version')
                if isinstance(event.get('actor_id'), str):
                    actor = event['actor_id']
            elif not isinstance(event.get('type'), str):
                raise EvaluationError(f'{path}:{number}: expected an event with a type')
            count += 1
            yield HostEvent(actor, number, event['type'], _wall(event.get('wall_time')),
                _milliseconds(event.get('monotonic_ms')), event)
    if not count:
        raise HostTraceUnsupported(f'{path}: empty host trace', 'empty')


def read_host(path: Path, actor_hint: str) -> tuple[str, tuple[HostEvent, ...]]:
    """One whole player-host/3 trace and its actor (the `host-start`'s `actor_id`, else `actor_hint`). A trace may
    still be appending, so an unterminated final line that does not parse is ignored on every pass, live or final."""
    events = tuple(iter_host(path, actor_hint, partial_tail=True))
    return events[0].actor, events


def read_memory(path: Path) -> MemoryFacts:
    """Read a player-memory/2 store: only authorship and structure, never the PNG blobs."""
    connection = _connect_readonly(path)
    try:
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        schemas = [row[0] for row in connection.execute('SELECT schema FROM metadata')]
        if version != 2 or schemas != [MEMORY_SCHEMA]:
            raise EvaluationError(f'{path}: unsupported player memory version (user_version {version}, '
                f'schema {schemas!r}); expected {MEMORY_SCHEMA}')
        records = {}
        for identity, document in connection.execute('SELECT id,document FROM records ORDER BY rowid'):
            records[identity] = loads(document, f'{path}:records:{identity}')
        programs = {}
        for identity, document in connection.execute('SELECT id,document FROM programs ORDER BY rowid'):
            programs[identity] = loads(document, f'{path}:programs:{identity}')
    except sqlite3.Error as exc:
        raise EvaluationError(f'{path}: cannot read {MEMORY_SCHEMA} ({exc})') from exc
    finally:
        connection.close()
    return MemoryFacts(path, records, programs)


def read_carry(run_dir: Path) -> dict[str, frozenset[str]]:
    """Record and program IDs each handing-off actor carried, from its contexts/<id>.json."""
    carry: dict[str, frozenset[str]] = {}
    directory = run_dir / 'contexts'
    if not directory.is_dir():
        return carry
    for path in sorted(directory.glob('*.json')):
        packet = read_json_file(path)
        if not isinstance(packet, dict) or packet.get('schema') != CONTEXT_SCHEMA:
            found = packet.get('schema') if isinstance(packet, dict) else None
            raise EvaluationError(f'{path}: unsupported handoff context version {found!r}; expected {CONTEXT_SCHEMA}')
        knowledge = packet.get('knowledge') or {}
        ids = {node['id'] for key in ('records', 'programs') for node in knowledge.get(key, ()) if isinstance(node, dict) and 'id' in node}
        carry[packet['actor_id']] = frozenset(ids)
    return carry


def _optional_json(path: Path, schemas: tuple[str, ...]) -> dict | None:
    """A file that exists only once a run has ended; when present, only the named versions are read."""
    if not path.is_file():
        return None
    value = read_json_file(path)
    found = value.get('schema') if isinstance(value, dict) else None
    if found not in schemas:
        raise EvaluationError(f'{path}: unsupported version {found!r}; expected {" or ".join(schemas)}')
    return value


def read_end_facts(run_dir: Path, manifest: dict) -> EndFacts:
    """`receipt.json` (campaign-receipt/3) and `watch-terminal.json` (campaign-watch-terminal/3, or /2 only for
    an archived session: a `campaign-run/4` manifest listed in the archive labels), when the run has ended.
    The owner Pause is the terminal's `reason == 'operator_pause'`."""
    archived = manifest.get('schema') == ARCHIVE_SCHEMA and manifest.get('session') in archive_labels()
    terminals = (WATCH_TERMINAL_SCHEMA, WATCH_TERMINAL_ARCHIVE_SCHEMA) if archived else (WATCH_TERMINAL_SCHEMA,)
    receipt = _optional_json(run_dir / 'receipt.json', (RECEIPT_SCHEMA,)) or {}
    driver = receipt.get('driver') if isinstance(receipt.get('driver'), dict) else {}
    actors = [a for a in driver.get('actors', ()) if isinstance(a, dict)]
    ending = driver.get('ending_request') if isinstance(driver.get('ending_request'), dict) else {}
    watch = _optional_json(run_dir / 'watch-terminal.json', terminals) or {}
    reason = watch.get('pause_reason') if watch.get('schema') == WATCH_TERMINAL_SCHEMA else None
    return EndFacts(receipt.get('outcome') if isinstance(receipt.get('outcome'), str) else None,
        ending.get('trigger') if isinstance(ending.get('trigger'), str) else None,
        tuple(a['settled'] for a in actors if isinstance(a.get('settled'), dict)),
        tuple((a.get('player_finish') or {}).get('disposition') for a in actors),
        watch.get('reason') == 'operator_pause',
        reason if isinstance(reason, str) else None)


def read_run(run_dir: Path, *, after_seq: int | None = None, settled_only: bool = False,
             memory_path: Path | None = None, digests: bool = True) -> RunInputs:
    """`digests=False` skips the SHA-256 of every input, which only a final record keeps."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise EvaluationError(f'{run_dir}: not a run directory')
    manifest = read_manifest(run_dir)
    session, operations = read_operations(run_dir, after_seq=after_seq, settled_only=settled_only)
    if manifest.get('session') not in (None, session):
        raise EvaluationError(f'{run_dir / "manifest.json"}: session {manifest.get("session")!r} differs from the session database')
    def digest(path: Path) -> str:
        if not digests:
            return ''
        return file_sha256(path)

    found = {'manifest.json': digest(run_dir / 'manifest.json'), 'session.sqlite3': digest(run_dir / 'session.sqlite3')}
    host: dict[str, tuple[HostEvent, ...]] = {}
    actors: list[str] = []
    actor_root = run_dir / 'actors'
    for directory in sorted(p for p in actor_root.iterdir() if p.is_dir()) if actor_root.is_dir() else ():
        trace = directory / 'host.jsonl'
        if not trace.is_file():
            continue
        actor, events = read_host(trace, directory.name)
        if actor in host:
            raise EvaluationError(f'{trace}: actor {actor} appears in two host traces')
        host[actor] = events
        actors.append(actor)
        found[f'actors/{directory.name}/host.jsonl'] = digest(trace)
    selected = memory_path
    if selected is None and isinstance(manifest.get('player_store'), str):
        candidate = Path(manifest['player_store'])
        candidate = candidate if candidate.is_absolute() else run_dir / candidate
        selected = candidate if candidate.is_file() else None
    memory = read_memory(Path(selected)) if selected is not None else None
    if selected is not None:
        found['player-memory'] = digest(Path(selected))
    return RunInputs(run_dir, session, manifest, tuple(operations), operations[-1].seq if operations else None,
        tuple(actors), host, read_carry(run_dir), memory, found, read_end_facts(run_dir, manifest))
