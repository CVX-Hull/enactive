"""Synthetic retained runs of the current contracts for the evidence-tool tests: no provider, game or host.

A run directory holds a real `computer-session/3` store (through `SessionStore`), the `campaign-run/5` manifest, the
`campaign-receipt/2` receipt embedding a `player-driver/6` actor record, and per-pass `player-host/6` traces. The
receipt counts are recomputed here from the pass specs the way `tools/campaign_player.py` does, so a fixture is
consistent until a test breaks it on purpose. A player store (`player-memory/1`) is written through the real `Memory`.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3

from PIL import Image

from harness.computer.store import SessionStore
from harness.player.contracts import ABSTAIN_CODES, EPISODE_ABSTAIN_CODES, EPISODE_CONTRACT, LEVEL_CONTRACT
from harness.player.memory import Memory

SESSION = 'c' * 32
ACTOR = 'a1' * 16
LEVEL_READER = 'b1' * 16
RECORDER_READER = 'b2' * 16
BASE = 1000.0
LIMITS = dict(max_inputs=1000, max_requests=1000, max_frames=1000, max_bytes=2 ** 30)


def iso(wall: float) -> str:
    return datetime.fromtimestamp(wall, timezone.utc).isoformat().replace('+00:00', 'Z')


def png() -> bytes:
    out = io.BytesIO()
    Image.new('RGB', (4, 4), 'blue').save(out, format='PNG')
    return out.getvalue()


def level_pass(index, kind, *, action='replace', reason='settle', started=None, ended=None, discard='Served actor handed off since the pass began',
               code='other', ending=None, ok=None, position=0, inputs_since=2, identity=None, outcome='committed', allocated=60.0):
    """A level pass spec. `kind`: commit, discard, abstain, uncertain, none (no event, `ending` says how it ended)."""
    started = BASE + 100 * index if started is None else started
    return dict(index=index, role='level', kind=kind, action=action, reason=reason, started=started,
                ended=started + 10 if ended is None else ended, discard=discard, code=code, ending=ending, ok=ok, position=position,
                inputs_since=inputs_since, identity=identity or f'{index:032x}', outcome=outcome, allocated=allocated)


def recorder_pass(index, kind, *, code='other', ending=None, ok=None, outcome='committed', started=None):
    """A recorder pass spec. `kind`: record, abstain, uncertain, none."""
    started = BASE + 100 * index if started is None else started
    return dict(index=index, role='recorder', kind=kind, code=code, ending=ending, ok=ok, outcome=outcome, started=started,
                ended=started + 5, identity=f'{index + 500:032x}')


def _event(spec, wall):
    base = dict(wall_time=iso(wall))
    kind = spec['kind']
    if spec['role'] == 'level':
        if kind in ('commit', 'discard'):
            return dict(base, type='level-commit' if kind == 'commit' else 'level-discard', action=spec['action'],
                        reason=None if kind == 'commit' else spec['discard'], position=spec['position'],
                        inputs_since=spec['inputs_since'], staleness_inputs=10, subgoal_id=None, derived=None, record_ids=[], kept=[])
        if kind == 'abstain':
            return dict(base, type='level-abstain', reason_code=spec['code'], reason='no change')
        if kind == 'uncertain':
            return dict(base, type='level-uncertain', tool=f"player_level_{spec['action']}", identity=spec['identity'], request_id='request-1')
    else:
        if kind == 'record':
            return dict(base, type='episode-record', first_position=1, last_position=2, subgoal_id=None, record_ids=[], counted=True,
                        closed=False, observations=None, stalled=None)
        if kind == 'abstain':
            return dict(base, type='episode-abstain', first_position=1, last_position=2, subgoal_id=None, record_ids=[],
                        reason_code=spec['code'], reason='unreadable')
        if kind == 'uncertain':
            return dict(base, type='episode-uncertain', tool='player_episode_record', identity=spec['identity'], request_id='request-1')
    return None


def write_pass(directory: Path, spec, schema='player-host/6', telemetry=2, extra_rows=()):
    """Write one pass's trace and return its driver pass record."""
    directory.mkdir(parents=True)
    rows = [dict(type='host-start', schema=schema, telemetry_version=telemetry, wall_time=iso(spec['started']))]
    event = _event(spec, spec['started'] + 3)
    if event:
        rows.append(event)
    rows += list(extra_rows)
    (directory / 'host.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    projected = {k: v for k, v in (event or {}).items() if k != 'wall_time'}
    committed = spec['kind'] in ('commit', 'record', 'abstain') and spec['ok'] is not False
    ending = spec['ending'] or ('completed' if committed else 'level-no-proposal' if spec['role'] == 'level' else 'episode-no-record')
    ok = committed if spec['ok'] is None else spec['ok']
    record = dict(index=spec['index'], role=spec['role'], reason=spec.get('reason', 'episode'), allocated_attempts=4,
                  allocated_seconds=spec.get('allocated', 60.0), started_wall=spec['started'], ended_wall=spec['ended'],
                  observed_attempts=2, attempts_charged=2, accounting_complete=True, settled=dict(ok=ok, reason=ending),
                  cleanup=dict(process_absent=True, group_absent=True), configured_estimate_usd=.01, missing_usage_attempts=0)
    lost = []
    if spec['kind'] == 'uncertain':
        lost = [dict(tool=event['tool'], identity=spec['identity'], request_id='request-1', outcome=spec['outcome'],
                     action=spec.get('action') if spec['outcome'] == 'committed' else None, record_ids=[])]
    if spec['role'] == 'level':
        record.update(level_events=[projected] if event and spec['kind'] != 'uncertain' else [], level_uncertain=lost)
    else:
        record.update(episode_events=[projected] if event and spec['kind'] != 'uncertain' else [], episode_uncertain=lost)
    (directory / 'driver-receipt.json').write_text(json.dumps(record))
    return record


def level_receipt(passes):
    commits = [e for p in passes for e in p['level_events'] if e['type'] == 'level-commit']
    abstains = [(p['reason'], e) for p in passes for e in p['level_events'] if e['type'] == 'level-abstain']
    failed = [p for p in passes if p['settled']['ok'] is not True]
    uncertain = [e for p in passes for e in p['level_uncertain']]
    return dict(reader_id=LEVEL_READER, allocated_attempts=60, attempts_charged=sum(p['attempts_charged'] for p in passes), passes=passes,
                commits=len(commits), keeps=sum(e['action'] == 'keep' for e in commits), replaces=sum(e['action'] == 'replace' for e in commits),
                closes=sum(e['action'] == 'close' for e in commits), discards=sum(e['type'] == 'level-discard' for p in passes for e in p['level_events']),
                abstains=len(abstains), abstain_codes={c: sum(e['reason_code'] == c for _, e in abstains) for c in ABSTAIN_CODES},
                start_abstains=sum(r == 'start' for r, _ in abstains), failed_passes=len(failed),
                final_refusals=sum(p['settled']['reason'] == 'level-final-refusal' for p in failed), uncertain_terminals=len(uncertain),
                uncertain_committed=sum(e['outcome'] == 'committed' for e in uncertain), uncertain_absent=sum(e['outcome'] == 'absent' for e in uncertain),
                configured_estimate_usd=.01 * len(passes), missing_usage_attempts=0)


def recorder_receipt(passes):
    events = [e for p in passes for e in p['episode_events']]
    failed = [p for p in passes if p['settled']['ok'] is not True and not p['episode_events']]
    uncertain = [e for p in passes for e in p['episode_uncertain']]
    return dict(reader_id=RECORDER_READER, allocated_attempts=60, attempts_charged=sum(p['attempts_charged'] for p in passes), passes=passes,
                records=sum(e['type'] == 'episode-record' for e in events), abstains=sum(e['type'] == 'episode-abstain' for e in events),
                abstain_codes={c: sum(e['type'] == 'episode-abstain' and e['reason_code'] == c for e in events) for c in EPISODE_ABSTAIN_CODES},
                failed_passes=len(failed), final_refusals=sum(p['settled']['reason'] == 'episode-final-refusal' for p in failed),
                uncertain_terminals=len(uncertain), uncertain_committed=sum(e['outcome'] == 'committed' for e in uncertain),
                uncertain_absent=sum(e['outcome'] == 'absent' for e in uncertain), configured_estimate_usd=.01 * len(passes), missing_usage_attempts=0)


def source_metadata(number: int) -> dict:
    wall = BASE + number
    return dict(schema='computer-source/1', source_id=f'{SESSION}-{number}', session=SESSION, capture_id=number,
                sha256=hashlib.sha256(png()).hexdigest(), media_type='image/png', presented_ms=1000 + number, received_wall=wall,
                window_width=4, viewport=[0, 0, 4, 4], width=4, window_height=4, height=4)


def build_session(directory: Path, inputs: int = 6) -> None:
    """A single-actor session with two readers and `inputs` completed input operations, each with a retained frame."""
    store = SessionStore(directory, SESSION, LIMITS, 1e9)
    store.add_actor(ACTOR, 'h' * 64)
    store.add_actor(LEVEL_READER, 'i' * 64, ACTOR, 'level')
    store.add_actor(RECORDER_READER, 'j' * 64, ACTOR, 'recorder')
    image = png()
    for number in range(1, inputs + 1):
        identity = f'{number:032x}'
        wall = BASE + number
        store.begin(dict(operation_id=identity, actor_id=ACTOR, kind='input', created_wall=wall, deadline_monotonic=1e8),
                    [dict(type='key', key='x', modifiers=[])], 1)
        metadata = source_metadata(number)
        store.put_source(metadata, image, ACTOR)
        store.finish(dict(schema='computer-operation/1', operation_id=identity, session=SESSION, actor_id=ACTOR, kind='input',
                          status='completed', created_wall=wall, deadline_monotonic=1e8, receipts=[], source=metadata, remaining={},
                          reason='ok', handoff=None))
    store.close()


def make_run(root: Path, name: str, level=(), recorder=(), *, inputs: int = 6, episodes=None, outcome='incomplete', failure=None,
             quiescent=True, schema_overrides=None, receipt_extra=None, level_overrides=None, recorder_overrides=None,
             settled=None) -> Path:
    """Write one synthetic run; the overrides break a field on purpose for the negative cases."""
    run = root / name
    run.mkdir(parents=True)
    build_session(run, inputs)
    manifest = dict(schema=(schema_overrides or {}).get('manifest', 'campaign-run/5'), session=SESSION, level=dict(staleness_inputs=10))
    (run / 'manifest.json').write_text(json.dumps(manifest))
    actor_dir = run / 'actors' / '001'
    level_records = [write_pass(actor_dir / 'level' / f"{spec['index']:03d}", spec) for spec in level]
    recorder_records = [write_pass(actor_dir / 'recorder' / f"{spec['index']:03d}", spec) for spec in recorder]
    system = dict(reader_id=LEVEL_READER, recorder_id=RECORDER_READER, mode='shadow', allocated_attempts=120, attempts_charged=0, failure=failure,
                  quiescent=quiescent, level=dict(level_receipt(level_records), **(level_overrides or {})),
                  recorder=dict(recorder_receipt(recorder_records), **(recorder_overrides or {})),
                  episodes=episodes if episodes is not None else dict(cut=0, closed_by={}, settled={}, max_waiting=0, backlog=3,
                                                                       waiting_unsettled=0, next_position=1, open_inputs=0),
                  subgoals=[], failed_passes=0, final_refusals=0, uncertain_terminals=0, configured_estimate_usd=0, missing_usage_attempts=0)
    actor = dict(index=1, actor_id=ACTOR, allocated_seconds=600, allocated_attempts=40, started_wall=BASE, attempts_charged=10,
                 accounting_complete=True, settled=settled or dict(ok=True, reason='cancelled', wall_time=iso(BASE + 500)),
                 cleanup=dict(process_absent=True, group_absent=True), level=system, configured_estimate_usd=.1, missing_usage_attempts=0)
    driver = dict(schema=(schema_overrides or {}).get('driver', 'player-driver/6'), outcome=outcome, reason='fixture', actors=[actor],
                  attempts_charged=10)
    receipt = dict(schema=(schema_overrides or {}).get('receipt', 'campaign-receipt/2'), session=SESSION, outcome=outcome, driver=driver,
                   normal_native_exit_zero=True, deciding_hosts_quiescent=True, native_absence_verified=True, input_authority_revoked=True)
    receipt.update(receipt_extra or {})
    (run / 'receipt.json').write_text(json.dumps(receipt))
    (actor_dir / 'driver-receipt.json').write_text(json.dumps(actor))
    return run


def work_record(text='Reach the door', position=3, *, contract=LEVEL_CONTRACT, session=SESSION, actor=ACTOR, sources=()):
    return dict(schema='player-record/1', kind='work', text=text, data=dict(
        level='subgoal', level_contract=contract, actor_id=actor, session=session, position=position,
        expected_observations=['The door is adjacent'], status='open', confidence=.4),
        sources=list(sources), supports=[], supersedes=None, applicability=None, program_id=None)


def correction_record(text, supersedes, outcome='revised', position=3):
    return dict(schema='player-record/1', kind='correction', text=text, data=dict(
        level='subgoal', level_contract=LEVEL_CONTRACT, actor_id=ACTOR, session=SESSION, position=position, outcome=outcome),
        sources=[], supports=[], supersedes=supersedes, applicability=None, program_id=None)


def claim_record(settled, first=1, last=2):
    writer = dict(recorded='recorder', abstained='recorder', failed='software', dropped='software')[settled]
    fields = (dict(observation_status=[], confidence=.5, attempted='moved', counterpart='', residual='', changed='') if settled == 'recorded'
              else dict(reason='fixture', **(dict(reason_code='other') if settled == 'abstained' else {})))
    return dict(schema='player-record/1', kind='claim', text='episode', data=dict(
        level='episode', level_contract=EPISODE_CONTRACT, settled=settled, writer=writer, session=SESSION, actor_id=ACTOR,
        first_position=first, last_position=last, subgoal_id=None, **fields),
        sources=[], supports=[], supersedes=None, applicability=None, program_id=None)


class PlayerStore:
    """A real `player-memory/1` store written through `Memory.append_many`, as the custodian does."""
    def __init__(self, path: Path) -> None:
        self.path, self.count = path, 0
        Memory(path).close()

    def commit(self, reader, tool, action, records, *, result_status='committed', writer=None, sources=()) -> list[dict]:
        self.count += 1
        identity = f'{self.count + 9000:032x}'
        memory = Memory(self.path)
        try:
            return memory.append_many(writer or reader, records, request_id=identity,
                                      service=(tool, {}, dict(schema='player-level-commit/4', status=result_status, action=action)),
                                      sources=list(sources), custodian=True)
        finally:
            memory.close()

    def software(self, reader, records) -> list[dict]:
        """Records the driver writes as the reader without a service row (the failed/dropped settle claims)."""
        self.count += 1
        memory = Memory(self.path)
        try:
            return memory.append_many(reader, records, request_id=f'{self.count + 9000:032x}', custodian=True)
        finally:
            memory.close()

    def tombstone(self, reader, tool, identity) -> None:
        db = sqlite3.connect(self.path)
        with db:
            db.execute('INSERT INTO service_operations VALUES(?,?,?,?,?,NULL)', (identity, reader, tool, '{}', '{"steps":[]}'))
        db.close()
