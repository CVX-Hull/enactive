#!/usr/bin/env python3
"""Blind intent-accuracy audit: bundle packets for clean-context auditors, then summarize their labels.

    python -m tools.intent_audit prepare OUT_DIR SESSION_DIR... --store-template PATH --context FILE --instructions FILE
    python -m tools.intent_audit summarize OUT_DIR --criteria CRITERIA.json

`prepare` writes one packet per committed level `replace` of the current contract (`LEVEL_CONTRACT`, a Work record the
software stamped) into `OUT_DIR/packets/<audit_id>/`:
- `packet.json`: the served actor's input log up to the record's bound position (each input's actions and the frame
  that followed it), the frames shown, the sources the proposal cites, and the proposal (subgoal text, expected
  observations, status, confidence, and the corrections the same commit wrote);
- the PNG frames named there: the most recent `--recent-frames` frames before the bound position plus every cited
  source of this session;
- `context.txt` (the frozen context the player had) and `instructions.md`, both copied unchanged from the frozen files
  named on the command line, which are the auditors' only other input.
Every occurrence of the audited session's id, in any string or file name, becomes the audit id. Any other session id
becomes `other-session-N` (numbered by first appearance in the packet): the other audited sessions' ids, and the id
inside any source id a persistent session cites from an earlier session. `prepare` refuses a context or instruction
file that contains an audited session's id (a frozen file is never edited to blind it; it is copied byte for byte).
It validates every input before it creates a directory, refuses an existing output directory, and refuses a store
template that matches no retained store. The key that maps audit ids back to runs and records is written to the
sibling `OUT_DIR-private/`, which auditors are never given, together with the sha256 of every input and of this tool.

`summarize` reads `OUT_DIR-private/labels/<audit_id>.<auditor>.json` (auditors `a` and `b`, and `c` only where `a` and
`b` derive different labels), each holding `premises` and `fit`, and derives each label by the frozen table:
    premises contradicted, or fit implausible         -> inaccurate
    premises shown and fit plausible                  -> accurate
    premises shown and fit unclear, or premises undecidable and fit plausible -> partly accurate
    premises undecidable and fit unclear              -> unverifiable
The reading is `inconclusive` below `min_auditable` auditable records or above `max_unverifiable_share` unverifiable;
`unreliable` when Cohen's kappa between `a` and `b` is below `min_kappa`; else `ok` when accuracy (accurate plus partly
accurate over auditable) reaches `min_accuracy`, else `below floor`. The thresholds come from the stage's frozen
criteria file (schema `intent-audit-criteria/1`), never from this file; its sha256 is recorded in the summary.

This tool does not label anything and calls no model: the auditors are separate, clean-context agents (or people) that
the lead launches under the audit's own procedure. Retained records of earlier audits cite their own script by hash and
are not reproduced by this one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.computer.protocol import ControlError, read_json
from harness.player.contracts import LEVEL_CONTRACT
from tools.control_analysis import session_database
from tools.evidence_stats import cohen_kappa
from tools.level_stage_analysis import COMMIT_TOOLS, UnsupportedTrace, store_rows

PACKET_SCHEMA = 'intent-audit-packet/1'
CRITERIA_SCHEMA = 'intent-audit-criteria/1'
CRITERIA_KEYS = ('min_auditable', 'min_kappa', 'min_accuracy', 'max_unverifiable_share')
LABELS = ('accurate', 'partly accurate', 'inaccurate', 'unverifiable')
PREMISES = ('shown', 'contradicted', 'undecidable')
FIT = ('plausible', 'implausible', 'unclear')


def label(premises: str, fit: str) -> str:
    """The frozen label table."""
    if premises not in PREMISES or fit not in FIT:
        raise ValueError(f'Unknown premises {premises!r} or fit {fit!r}')
    if premises == 'contradicted' or fit == 'implausible':
        return 'inaccurate'
    if premises == 'shown':
        return 'accurate' if fit == 'plausible' else 'partly accurate'
    return 'partly accurate' if fit == 'plausible' else 'unverifiable'


def private(out: Path) -> Path:
    """The key and labels live beside, never inside, the directory auditors are pointed at."""
    return out.parent / (out.name + '-private')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Blinder:
    """Consistent blinding of one packet: no session id survives, whichever session it names.

    The audited session's id becomes the audit id. Any other session id, whether it is one of the audited sessions' or
    only appears inside a source id (`<32 hex>-<capture>`, as a persistent session cites an earlier session's frame),
    becomes `other-session-N`, numbered by first appearance in this packet, so two citations of the same earlier session
    stay recognizably the same without naming it. Keys of a JSON value are fixed field names, not data.
    """
    SOURCE = re.compile(r'([0-9a-f]{32})-(\d+)')

    def __init__(self, own: str, audit: str, known: set[str]) -> None:
        self.names, self.known = {own: audit}, known

    def name(self, hexid: str) -> str:
        if hexid not in self.names:
            self.names[hexid] = f'other-session-{len(self.names)}'
        return self.names[hexid]

    def text(self, value: str) -> str:
        value = self.SOURCE.sub(lambda m: f'{self.name(m.group(1))}-{m.group(2)}', value)
        for hexid in sorted(self.known):
            value = value.replace(hexid, self.name(hexid))
        return value

    def __call__(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self(v) for v in value]
        if isinstance(value, dict):
            return {k: self(v) for k, v in value.items()}
        return value


def session_identity(path: Path) -> str:
    with session_database(path) as (_, _, session):
        return session


def committed_replaces(store: Path, session: str) -> list[dict]:
    """Each committed replace's Work record and the corrections written by the same commit, in commit order.

    The commit's own service result lists exactly the records it wrote, so the link is structural, not a timestamp.
    """
    docs, service = store_rows(store)
    by_id = {d['id']: d for d in docs}
    found = []
    for _, tool, result, _ in service:
        if tool != 'player_level_replace' or result is None:
            continue
        value = json.loads(result)
        if value.get('status') != 'committed' or value.get('action') != 'replace':
            continue
        written = [by_id[r['id']] for r in value.get('records', []) if r.get('id') in by_id]
        work = next((d for d in written if d['kind'] == 'work' and d['data'].get('level') == 'subgoal'
                     and d['data'].get('level_contract') == LEVEL_CONTRACT and d['data'].get('session') == session), None)
        if work is not None:
            found.append(dict(work=work, decisions=[d for d in written if d['kind'] == 'correction']))
    return found


def input_log(path: Path, actor: str, position: int) -> list[dict]:
    """The served actor's operations up to `position`: (position, kind, actions, the frame that followed)."""
    with session_database(path) as (db, _, _):
        ops = db.execute('SELECT kind,input_json,final_json FROM operations WHERE actor=? ORDER BY rowid LIMIT ?', (actor, position)).fetchall()
    log = []
    for number, (kind, actions, final) in enumerate(ops, 1):
        source = (json.loads(final).get('source') or {}).get('source_id') if final else None
        log.append(dict(position=number, kind=kind, actions=json.loads(actions) if kind == 'input' else None, frame=source))
    return log


def prepare(out: Path, sessions: list[Path], store_template: str, context: Path, instructions: Path, *, recent_frames: int = 10) -> int:
    """Write the blind packets and the private key; returns the number of packets."""
    if type(recent_frames) is not int or recent_frames < 1:
        raise ValueError('recent_frames is a positive integer')
    # Everything is read and checked before any directory exists, so a refusal leaves nothing behind.
    frozen = {name: path.read_bytes() for name, path in (('context', context), ('instructions', instructions))}
    identities = {s: session_identity(s) for s in sessions}
    for session, hexid in identities.items():
        for name, data in frozen.items():
            if hexid.encode() in data:
                raise ValueError(f'The frozen {name} file contains the id of {session.name}; it is never edited to blind it')
    if out.exists() or private(out).exists():
        raise FileExistsError(f'{out} or {private(out)} already exists; an audit directory is never overwritten')
    known = set(identities.values())
    plans, missing, key = [], [], {}
    for session in sessions:
        store = Path(store_template.format(run=session.name))
        if not store.exists():
            missing.append(session.name)
            continue
        hexid = identities[session]
        for commit in committed_replaces(store, hexid):
            work = commit['work']
            audit = secrets.token_hex(6)
            key[audit] = dict(session=session.name, record_id=work['id'])
            log = input_log(session, work['data']['actor_id'], work['data']['position'])
            frames = [e['frame'] for e in log if e['frame']]
            chosen = list(dict.fromkeys(frames[-recent_frames:] + [s for s in work['sources'] if s.startswith(hexid)]))
            images = {}
            for source in chosen:
                image = session / 'sources' / f'{source}.png'
                if not image.is_file():
                    raise FileNotFoundError(f'Frame {source} of {session.name} is not retained: {image}')
                images[source.replace(hexid, audit) + '.png'] = image.read_bytes()
            decisions = [dict(decision=d['data'].get('outcome'), reason=d['text']) for d in commit['decisions']]
            value = dict(schema=PACKET_SCHEMA, audit_id=audit, input_log=log, frames=chosen, cited_sources=work['sources'],
                         proposal=dict(subgoal=work['text'], expected_observations=work['data'].get('expected_observations'),
                                       status=work['data'].get('status'), confidence=work['data'].get('confidence'),
                                       decisions_in_same_commit=decisions))
            plans.append((audit, images, json.dumps(Blinder(hexid, audit, known)(value), indent=1) + '\n'))
    if len(missing) == len(sessions):
        raise ValueError(f'The store template {store_template!r} matches no retained store; looked for runs {missing}')
    out.mkdir(parents=False, exist_ok=False)
    (out / 'packets').mkdir()
    private(out).mkdir(parents=False, exist_ok=False)
    (private(out) / 'labels').mkdir()
    for audit, images, packet_json in plans:
        packet = out / 'packets' / audit
        packet.mkdir()
        for name, data in images.items():
            (packet / name).write_bytes(data)
        (packet / 'packet.json').write_text(packet_json)
        (packet / 'context.txt').write_bytes(frozen['context'])
        (packet / 'instructions.md').write_bytes(frozen['instructions'])
    inputs = dict(context_sha256=sha256(context), instructions_sha256=sha256(instructions), code_sha256=sha256(Path(__file__)),
                  recent_frames=recent_frames, level_contract=LEVEL_CONTRACT, commit_tools=list(COMMIT_TOOLS), runs_without_store=missing)
    (private(out) / 'key.json').write_text(json.dumps(dict(inputs=inputs, packets=key), indent=1) + '\n')
    return len(key)


def load_criteria(path: Path) -> dict:
    value = read_json(path, 1 << 16)
    found = value.get('schema') if isinstance(value, dict) else None
    if found != CRITERIA_SCHEMA:
        raise UnsupportedTrace(f'{path}: criteria schema {found!r}, expected {CRITERIA_SCHEMA!r}')
    if set(value) != {'schema', *CRITERIA_KEYS} or not all(type(value[k]) in (int, float) and not isinstance(value[k], bool) and value[k] >= 0
                                                          for k in CRITERIA_KEYS):
        raise UnsupportedTrace(f'{path}: criteria are exactly {list(CRITERIA_KEYS)}, each a non-negative number')
    return value


def derived_label(out: Path, audit: str, auditor: str) -> str:
    path = private(out) / 'labels' / f'{audit}.{auditor}.json'
    if not path.is_file():
        raise ValueError(f'Missing label {path.name}')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f'{path.name} is not a label object')
    return label(value.get('premises'), value.get('fit'))


def summarize(out: Path, criteria: dict) -> dict:
    # A packet is a directory; a stray file or an editor's leftover in the folder is not one.
    audits = sorted(p.name for p in (out / 'packets').iterdir() if p.is_dir())
    first, second, resolved = [], [], {}
    for audit in audits:
        a, b = derived_label(out, audit, 'a'), derived_label(out, audit, 'b')
        first.append(a)
        second.append(b)
        resolved[audit] = a if a == b else derived_label(out, audit, 'c')
    counts = {c: sum(v == c for v in resolved.values()) for c in LABELS}
    auditable = len(resolved) - counts['unverifiable']
    accuracy = (counts['accurate'] + counts['partly accurate']) / auditable if auditable else None
    kappa = cohen_kappa(first, second, LABELS)
    if auditable < criteria['min_auditable'] or counts['unverifiable'] > criteria['max_unverifiable_share'] * len(resolved):
        reading = 'inconclusive'
    elif kappa is None or kappa < criteria['min_kappa']:
        reading = 'unreliable'
    else:
        reading = 'ok' if accuracy >= criteria['min_accuracy'] else 'below floor'
    return dict(records=len(resolved), kappa_ab=kappa, counts=counts, accuracy=accuracy,
                strict_accuracy=counts['accurate'] / auditable if auditable else None, reading=reading, resolved=resolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('out', type=Path)
    prep.add_argument('sessions', type=Path, nargs='+')
    prep.add_argument('--store-template', required=True, help='retained player store path containing {run}')
    prep.add_argument('--context', type=Path, required=True)
    prep.add_argument('--instructions', type=Path, required=True)
    prep.add_argument('--recent-frames', type=int, default=10)
    summ = commands.add_parser('summarize')
    summ.add_argument('out', type=Path)
    summ.add_argument('--criteria', type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == 'prepare':
            print(prepare(arguments.out, arguments.sessions, arguments.store_template, arguments.context, arguments.instructions,
                          recent_frames=arguments.recent_frames), 'packets')
        else:
            criteria = load_criteria(arguments.criteria)
            value = dict(summarize(arguments.out, criteria), criteria_sha256=sha256(arguments.criteria), criteria=criteria,
                         code_sha256=sha256(Path(__file__)))
            # A summary is a result: it is written once and never replaced.
            with (private(arguments.out) / 'summary.json').open('x') as stream:
                stream.write(json.dumps(value, indent=1) + '\n')
            print(json.dumps({k: v for k, v in value.items() if k != 'resolved'}, indent=1))
    except UnsupportedTrace as error:
        print(f'unsupported: {error}', file=sys.stderr)
        return 2
    except ControlError as error:
        # The custodian's own version gates (for example the session database schema) say "Unsupported".
        unsupported = str(error).startswith('Unsupported')
        print(f"{'unsupported' if unsupported else 'Intent audit failed'}: {error}", file=sys.stderr)
        return 2 if unsupported else 1
    except (OSError, ValueError, KeyError) as error:
        print(f'Intent audit failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
