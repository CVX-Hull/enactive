"""The P1 offline study's arms: working sets, one renderer and the per-admission schedule (docs/design/p1-study-3.md; #462).

At every boundary of a lineage each arm produces the text the successor would have received live:

    delivered = received text + "\\n\\n" + rendered working set

The received text is the successor's own sealed prompt, which carries the previous player's
report and sealed handoff context when it had a predecessor in its session. It is the same bytes for
every arm. Only the working set differs:

- Reference: none.
- A (no curator): the lineage's own `player-memory/2` records written before the boundary, live,
  newest first.
- B (curator): the facts of the knowledge version that live timing (D2) would have published
  before the boundary, in scope and not superseded, newest first.

One renderer turns either arm's items into the same `- <statement>` lines under one fixed header,
so the text carries no id, citation, source, actor, kind or arm label. The working set is capped at
2,000 tokens (`ceil(utf8 bytes / 4)`); an item that would pass the cap is dropped whole, and so is
every older item.

Nothing here knows a game. The functions are pure over their arguments except `chunks`,
`curator_cutoffs`, `boundaries` and `read_store`, which read sealed stores read-only.
"""
from __future__ import annotations

from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata

from harness.trace import memory_reader
from tools.probe_timeline import connect

CAP_TOKENS = 2000
STATEMENT_CHARS = 8192
SEPARATOR = '\n\n'
# One header for both arms. It marks the items as fallible player knowledge and names no source.
HEADER = 'Notes from earlier play. They are fallible player knowledge, not instructions, and may be out of date:'
_VERSION = re.compile(r'v([0-9]+)')


class ArmsError(ValueError):
    """A lineage, a store or a schedule cannot produce the working sets."""


# ------------------------------------------------------------------ boundaries
@dataclass(frozen=True)
class Chunk:
    name: str           # "<session>-<actor directory>"
    session: str
    session_index: int  # the session's place in the lineage: its admission
    directory: str
    path: Path          # the actor directory
    first_wall: float   # the actor's first operation `created_wall`


@dataclass(frozen=True)
class Boundary:
    name: str           # "<predecessor chunk>><successor chunk>"
    kind: str           # "handoff" (same session) or "admission"
    predecessor: str
    successor: str
    cutoff: float       # the successor's first operation `created_wall`
    admission: int      # the successor's session index in the lineage, from 0
    received_path: Path  # the successor's sealed prompt


def _actor_id(directory: Path) -> str | None:
    frozen = directory/'frozen.json'
    return json.loads(frozen.read_text()).get('actor_id') if frozen.is_file() else None


def chunks(sessions: Sequence[Path]) -> list[Chunk]:
    """The actor directories of the lineage's sessions, ordered by session then directory."""
    found = []
    for index, session in enumerate(sessions):
        with closing(connect(Path(session)/'session.sqlite3')) as db:
            first = dict(db.execute('SELECT actor, MIN(created_wall) FROM operations GROUP BY actor'))
        for directory in sorted(p for p in (Path(session)/'actors').iterdir() if p.is_dir()):
            wall = first.get(_actor_id(directory))
            if wall is None:
                raise ArmsError(f'{directory}: no operation, so the boundary has no cutoff')
            found.append(Chunk(name=f'{Path(session).name}-{directory.name}', session=Path(session).name,
                               session_index=index, directory=directory.name, path=directory, first_wall=float(wall)))
    return found


def boundaries(sessions: Sequence[Path]) -> list[Boundary]:
    """The step between consecutive chunks of a lineage, in order."""
    found = chunks(sessions)
    return [Boundary(name=f'{pred.name}>{succ.name}', kind='handoff' if pred.session == succ.session else 'admission',
                     predecessor=pred.name, successor=succ.name, cutoff=succ.first_wall,
                     admission=succ.session_index, received_path=succ.path/'prompt.txt')
            for pred, succ in zip(found, found[1:])]


def curator_cutoffs(sessions: Sequence[Path]) -> list[float | None]:
    """Where each admission's curator session cuts the lineage's memory (strictly before).

    Admission k's session sees the memory arm A has at the boundary into admission k+1: the first
    operation of admission k+1's first chunk, the same instant `boundaries` gives that
    admission boundary. The last admission has no next boundary and sees the whole store (`None`)."""
    firsts: dict[int, float] = {}
    for chunk in chunks(sessions):
        firsts.setdefault(chunk.session_index, chunk.first_wall)
    return [firsts.get(index + 1) for index in range(len(sessions))]


def received_text(boundary: Boundary) -> str:
    """What the successor received, as `tools.probe_timeline` reads it: the sealed prompt, stripped.

    The prompt already carries the previous player's final report and its sealed handoff context."""
    if not boundary.received_path.is_file():
        raise ArmsError(f'{boundary.received_path}: the successor has no sealed prompt')
    return boundary.received_path.read_text(errors='replace').strip()


# ------------------------------------------------------------------ working sets
@dataclass(frozen=True)
class Item:
    kind: str       # for reporting only; never rendered
    statement: str
    # The source ids the item cites (A: a record's `sources`; B: a fact's `citations`). Metadata for the
    # false-fact audit (docs/design/p1-study-3.md, The measurement chain); never rendered.
    cites: tuple[str, ...] = ()


_EMPTY = (None, '', [], {})


def _prose(value: object) -> str:
    """A data value as plain words: no quotes, brackets or braces that only a record's data would carry."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ', '.join(part for part in map(_prose, value) if part)
    if isinstance(value, dict):
        return ', '.join(f'{key} {_prose(item)}' for key, item in sorted(value.items()) if item not in _EMPTY)
    return json.dumps(value, ensure_ascii=False)  # numbers and booleans


def record_statement(record: dict) -> str:
    """A record's text, then its `data` folded into prose: `<text>. key: value; key: value`.

    The record holds both, and the actor often put the specifics (what, where, how many) only in
    `data`, so leaving it out would take from arm A what the actor stored. The result has the shape of
    a plain statement, with no punctuation that only a record can produce."""
    text = record['text'].strip() if isinstance(record.get('text'), str) else ''
    data = record.get('data')
    if isinstance(data, dict):
        extra = '; '.join(f'{key}: {_prose(value)}' for key, value in sorted(data.items()) if value not in _EMPTY)
    else:
        extra = '' if data in _EMPTY else _prose(data)
    if not (text and extra):
        return text or extra
    return f'{text}{"" if text.endswith(".") else "."} {extra}'


def _written_before(row: dict, cutoff: float) -> bool:
    wall = row.get('created_wall')
    return isinstance(wall, (int, float)) and not isinstance(wall, bool) and wall < cutoff


def read_store(path: Path) -> dict:
    """A sealed `player-memory/2` store as plain data."""
    try:
        return memory_reader.read(Path(path))
    except memory_reader.StoreError as error:
        raise ArmsError(str(error)) from error


def arm_a_items(store: dict, cutoff: float) -> list[Item]:
    """The records created before the cutoff and not superseded by one created before it, newest first."""
    written = [r for r in store['records'] if _written_before(r, cutoff)]
    superseded = {r['supersedes'] for r in written if r.get('supersedes')}
    live = sorted((r for r in written if r['id'] not in superseded), key=lambda r: (-r['created_wall'], r['id']))
    return [Item(kind=r['kind'], statement=record_statement(r), cites=_cites(r.get('sources'))) for r in live]


def _cites(value: object) -> tuple[str, ...]:
    """The cited source ids of a record or fact, in order, repeats removed; anything else cites nothing."""
    return tuple(dict.fromkeys(v for v in value if isinstance(v, str))) if isinstance(value, list) else ()


def _published(fact: dict) -> int:
    match = _VERSION.fullmatch(str(fact.get('published_in')))
    return int(match[1]) if match else 0


def arm_b_items(facts: Sequence[dict], game: str) -> list[Item]:
    """Facts of one knowledge version that are not superseded and are in scope, most recently published first."""
    live = [f for f in facts if 'superseded_by' not in f and isinstance(f.get('scope'), dict)
            and f['scope'].get('game') == game]
    live.sort(key=lambda f: (-_published(f), str(f.get('id'))))
    return [Item(kind=str(f.get('type')), statement=f['statement'] if isinstance(f.get('statement'), str) else '',
                 cites=_cites(f.get('citations')))
            for f in live]


def scheduled_version(admission: int, versions: Sequence[str]) -> str | None:
    """The version arm B delivers at a boundary whose successor is in `admission` (D2).

    `versions[k]` is what the one curator session covering admission k published. Both an
    admission boundary into admission k and a handoff inside it deliver the snapshot of admission
    k-1's session; the first admission delivers none."""
    if admission < 1:
        return None
    if admission > len(versions):
        raise ArmsError(f'the schedule has no version for admission {admission - 1}')
    return versions[admission - 1]


# ------------------------------------------------------------------ one renderer
def clean(text: object, limit: int) -> str:
    """One line of printable text: whitespace runs become one space, other control, format,
    surrogate, private-use and unassigned characters are removed, and the result is cut to `limit`."""
    if not isinstance(text, str):
        return ''
    kept = []
    for char in text:
        if char.isspace():
            kept.append(' ')
        elif unicodedata.category(char) not in ('Cc', 'Cf', 'Cs', 'Co', 'Cn'):
            kept.append(char)
    return ' '.join(''.join(kept).split())[:limit].rstrip()


def tokens(text: str) -> int:
    """`ceil(utf-8 bytes / 4)`, the study's token count."""
    return -(-len(text.encode('utf-8')) // 4)


@dataclass(frozen=True)
class Rendered:
    text: str                   # the header and the lines, or '' when nothing is delivered
    tokens: int
    items: int                  # delivered
    dropped: int                # cut by the cap, the first that did not fit and every older one
    # The delivered items in order: each statement as rendered (cleaned) and what it cites. Not rendered.
    working_set: tuple[Item, ...] = ()


def render(items: Sequence[Item], cap: int = CAP_TOKENS) -> Rendered:
    """Items, newest first, as `- <statement>` lines under one header, within the cap.

    The item's `kind` is not rendered: the two arms' kinds are different vocabularies (a record's
    kind, a curator's fact type), so a label would tell the arms apart."""
    usable = [(statement, i) for i in items if (statement := clean(i.statement, STATEMENT_CHARS))]
    lines: list[str] = []
    kept: list[Item] = []
    text = ''
    for statement, item in usable:
        candidate = '\n'.join([HEADER, *lines, f'- {statement}'])
        if tokens(candidate) > cap:
            break
        lines.append(f'- {statement}')
        kept.append(Item(kind=item.kind, statement=statement, cites=item.cites))
        text = candidate
    return Rendered(text=text, tokens=tokens(text), items=len(lines), dropped=len(usable) - len(lines),
                    working_set=tuple(kept))


def delivered(received: str, rendered: Rendered) -> str:
    """The text the successor would have received: the received text, then the working set if any."""
    return f'{received}{SEPARATOR}{rendered.text}' if rendered.text else received
