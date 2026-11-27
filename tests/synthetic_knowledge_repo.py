"""Synthetic `curator-knowledge/5` repository builders for Wave 3 gate and export tests.

Each builder commits real Git snapshots (`v0..vN`) using the exact on-disk layout of
`curator-knowledge/5` (no `ontology/types.json`, `curator-fact/6` rows in `facts.jsonl`,
`provenance.json` with `frames`, `sessions` (including `context`), `branches`, `restores`,
and `coverage.json` from `v1` onward). Every written record is validated against
`schemas/curator-fact.schema.json` by default so gate and export slices share one verified
ground truth.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parent.parent / 'schemas'
KNOWLEDGE_SCHEMA = 'curator-knowledge/5'
FACT_SCHEMA = 'curator-fact/6'
COVERAGE_SCHEMA = 'curator-coverage/2'
IDENTITY = (
    '-c', 'user.name=enactive-gate',
    '-c', 'user.email=gate@localhost',
    '-c', 'commit.gpgsign=false',
    '-c', 'tag.gpgsign=false',
    '-c', 'core.hooksPath=/dev/null',
)

WORLD_ALPHA = 'world-alpha'
WORLD_BETA = 'world-beta'
LINEAGE_A = 'lin-alpha-main'
LINEAGE_B = 'lin-alpha-fork'
LINEAGE_C = 'lin-alpha-child'
LINEAGE_BETA = 'lin-beta-main'
LINEAGE_RESTORE = 'lin-restore-main'

_FACT_VALIDATOR = Draft202012Validator(
    json.loads((SCHEMA_DIR / 'curator-fact.schema.json').read_text(encoding='utf-8'))
)


def sort_lineages(values: set[str | None] | list[str | None]) -> list[str | None]:
    """Canonical ordering for stored `lineages`: distinct strings sorted, then `None` if present."""
    return sorted(set(values), key=lambda v: (v is None, '' if v is None else v))


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['GIT_CONFIG_GLOBAL'] = '/dev/null'
    env['GIT_CONFIG_SYSTEM'] = '/dev/null'
    env['GIT_TERMINAL_PROMPT'] = '0'
    return env


def _git(cwd: Path, *args: str) -> bytes:
    done = subprocess.run(['git', *IDENTITY, *args], cwd=cwd, env=_env(), capture_output=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(f'git {args[0]} failed ({done.returncode}): {done.stderr.decode("utf-8", "replace").strip()}')
    return done.stdout


def _dump(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def _jsonl(records: list[dict[str, Any]]) -> bytes:
    return ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records).encode('utf-8')


def session_hex(index: int) -> str:
    return f'{index:032x}'


def frame_id(sid: str, number: int) -> str:
    """Canonical `<32-hex session>-<capture_id>` source ID matching `harness/computer/protocol.py`."""
    if number < 1:
        raise ValueError('capture_id must be >= 1')
    return f'{sid}-{number}'


def position(session_name: str, step: int, *, actor: str = '001', order_index: int = 1) -> dict[str, Any]:
    return {'session': session_name, 'actor': actor, 'step': step, 'order': [order_index, actor, step]}


def _order_key(pos: dict[str, Any]) -> tuple[int, str, int]:
    order = pos['order']
    return (order[0], order[1], order[2])


def recompute_stored_flags(records: list[dict[str, Any]]) -> None:
    """Compute stored `lifecycle_state`, `stale_citations`, and `needs_review`."""
    from harness.curator.check import recompute_flags
    recompute_flags(records)


class SyntheticKnowledgeBuilder:
    """Imperative builder that writes valid tagged `curator-knowledge/5` snapshots."""

    def __init__(self, root: Path, game: str = 'example', *, validate: bool = True):
        self.root = Path(root)
        self.game = game
        self.path = self.root / game
        self.state = self.root / f'{game}.state'
        self.validate = validate
        self.version_num = 0
        self.records: list[dict[str, Any]] = []
        self.provenance: dict[str, Any] = {
            'frames': {},
            'frame_clocks': {},
            'sessions': {},
            'branches': {},
            'restores': [],
        }
        self._init_repo()

    def _init_repo(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        _git(self.path, 'init', '-q', '-b', 'main')
        self._write_tag(
            'v0',
            message=f'Initialize {self.game} knowledge repository',
            coverage=None,
        )

    @property
    def version(self) -> str:
        return f'v{self.version_num}'

    def next_version(self) -> str:
        return f'v{self.version_num + 1}'

    def add_session(
        self,
        sid: str,
        name: str,
        *,
        world: str | None = None,
        lineage: str | None = None,
        admission: int | None = None,
        context: dict[str, str] | None = None,
        branch: dict[str, Any] | None = None,
    ) -> None:
        self.provenance['sessions'][sid] = {
            'name': name,
            'world': world,
            'lineage': lineage,
            'admission': admission,
            'context': dict(context or {}),
        }
        if lineage is not None:
            if branch is not None:
                fork_ver = branch.get('fork_version')
                if fork_ver is not None and int(fork_ver[1:]) > self.version_num:
                    raise ValueError(f'fork_version {fork_ver!r} exceeds current version {self.version!r}')
                self.provenance['branches'][lineage] = copy.deepcopy(branch)
            else:
                self.provenance['branches'].setdefault(
                    lineage, {'parent': None, 'fork_at': None, 'fork_version': None}
                )

    def add_frame(
        self,
        sid: str,
        number: int,
        step: int,
        *,
        actor: str = '001',
        order_index: int = 1,
    ) -> str:
        fid = frame_id(sid, number)
        session_name = self.provenance['sessions'][sid]['name']
        self.provenance['frames'][fid] = position(session_name, step, actor=actor, order_index=order_index)
        return fid

    def add_clock(self, fid: str, label: str) -> None:
        self.provenance['frame_clocks'][fid] = label

    def add_restore(
        self,
        *,
        lineage: str,
        restored_at: dict[str, Any],
        restored_version: str | None,
        saved_at: dict[str, Any] | None,
        saved_version: str | None,
    ) -> None:
        for label, ver in (('saved_version', saved_version), ('restored_version', restored_version)):
            if ver is not None and int(ver[1:]) > self.version_num:
                raise ValueError(f'{label} {ver!r} exceeds current version {self.version!r}')
        self.provenance['restores'].append({
            'lineage': lineage,
            'restored_at': copy.deepcopy(restored_at),
            'restored_version': restored_version,
            'saved_at': copy.deepcopy(saved_at) if saved_at is not None else None,
            'saved_version': saved_version,
        })

    def _citation_positions(self, citations: list[str]) -> list[dict[str, Any]]:
        return [self.provenance['frames'][c] for c in citations]

    def _citation_lineage(self, cid: str) -> str | None:
        sid = cid.partition('-')[0]
        return self.provenance['sessions'][sid]['lineage']

    def _citation_world_and_lineages(self, citations: list[str]) -> tuple[str, list[str | None]]:
        worlds: set[str] = set()
        lineages: set[str | None] = set()
        for cid in citations:
            sid = cid.partition('-')[0]
            meta = self.provenance['sessions'][sid]
            if meta['world'] is None:
                raise ValueError(f'citation {cid!r} has no world')
            worlds.add(meta['world'])
            lineages.add(meta['lineage'])
        if len(worlds) != 1:
            raise ValueError(f'citations span multiple worlds: {sorted(worlds)}')
        return worlds.pop(), sort_lineages(lineages)

    def _in_abandoned_stretch(self, lineage: str | None, pos: dict[str, Any]) -> bool:
        if lineage is None:
            return False
        key = _order_key(pos)
        for restore in self.provenance['restores']:
            if restore['lineage'] != lineage or restore['saved_at'] is None:
                continue
            if _order_key(restore['saved_at']) < key < _order_key(restore['restored_at']):
                return True
        return False

    def _has_unknown_restore_between(self, lineage: str | None, earlier: dict[str, Any], later: dict[str, Any]) -> bool:
        if lineage is None:
            return False
        lo, hi = _order_key(earlier), _order_key(later)
        for restore in self.provenance['restores']:
            if restore['lineage'] != lineage or restore['saved_at'] is not None:
                continue
            if lo < _order_key(restore['restored_at']) <= hi:
                return True
        return False

    def _lineage_path(self, ancestor: str | None, lineage: str | None, at_pos: dict[str, Any]) -> list[tuple[str, dict[str, Any] | None]] | None:
        """Return ordered segments `[(ancestor, fork_at_1), ..., (lineage, None)]` if `ancestor` is `lineage`
        or an ancestor whose fork lies at or after `at_pos`, else `None`.
        """
        if ancestor is None or lineage is None:
            return None
        if ancestor == lineage:
            return [(lineage, None)]
        chain: list[tuple[str, dict[str, Any] | None]] = [(lineage, None)]
        cursor: str | None = lineage
        visited: set[str] = set()
        while cursor is not None and cursor not in visited:
            visited.add(cursor)
            info = self.provenance['branches'].get(cursor)
            if not info or info['parent'] is None or info['fork_at'] is None:
                return None
            parent = info['parent']
            fork_at = info['fork_at']
            chain.append((parent, fork_at))
            if parent == ancestor:
                if _order_key(at_pos) > _order_key(fork_at):
                    return None
                chain.reverse()
                return chain
            cursor = parent
        return None

    def _has_unknown_restore_along_path(
        self,
        segments: list[tuple[str, dict[str, Any] | None]],
        start_pos: dict[str, Any],
        end_pos: dict[str, Any],
    ) -> bool:
        for idx, (seg_lineage, seg_end) in enumerate(segments):
            lo = _order_key(start_pos) if idx == 0 else None
            hi = _order_key(end_pos) if seg_end is None else _order_key(seg_end)
            for restore in self.provenance['restores']:
                if restore['lineage'] != seg_lineage or restore['saved_at'] is not None:
                    continue
                rkey = _order_key(restore['restored_at'])
                if (lo is None or lo < rkey) and rkey <= hi:
                    return True
        return False

    def _is_ancestor_or_same(self, ancestor: str | None, lineage: str | None, at_pos: dict[str, Any]) -> bool:
        return self._lineage_path(ancestor, lineage, at_pos) is not None

    def _end_event_visible_on(self, event: dict[str, Any], target_lineage: str | None, seen_pos: dict[str, Any]) -> bool:
        if target_lineage is None:
            return False
        for cid in event['end_citations']:
            pos = self.provenance['frames'][cid]
            if self._citation_lineage(cid) != target_lineage:
                return False
            if self._in_abandoned_stretch(target_lineage, pos):
                return False
            if self._has_unknown_restore_between(target_lineage, seen_pos, pos):
                return False
        return True

    def make_fact(
        self,
        *,
        fact_id: str,
        statement_kind: str = 'observation',
        state_key: str | None = None,
        anchor: str | None = None,
        depiction_source_id: str | None = None,
        tags: list[str] | None = None,
        text: str,
        citations: list[str],
        published_in: str,
        session: str,
        scope_axes: dict[str, str] | None = None,
        bind_world: bool = False,
        subject: str | None = None,
        when: str | None = None,
        links: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        positions = self._citation_positions(citations)
        scope: dict[str, str] = {'game': self.game}
        if scope_axes:
            scope.update(scope_axes)
        record: dict[str, Any] = {
            'schema': FACT_SCHEMA,
            'record': 'fact',
            'id': fact_id,
            'statement_kind': statement_kind,
            'tags': list(tags or []),
            'text': text,
            'scope': scope,
            'links': copy.deepcopy(list(links or [])),
            'citations': list(citations),
            'seen': copy.deepcopy(max(positions, key=_order_key)),
            'valid_from': copy.deepcopy(min(positions, key=_order_key)),
            'valid_to': None,
            'lifecycle_state': 'active',
            'stale_citations': [],
            'needs_review': False,
            'published_in': published_in,
            'session': session,
        }
        if statement_kind == 'state' and state_key is None:
            state_key = f'key-{fact_id}'
        if state_key is not None:
            record['state_key'] = state_key
        if anchor is not None:
            record['anchor'] = anchor
        if depiction_source_id is not None:
            record['depiction_source_id'] = depiction_source_id
        if subject is not None:
            record['subject'] = subject
        if when is not None:
            record['when'] = when
        if bind_world:
            world, lineages = self._citation_world_and_lineages(citations)
            record['scope']['world'] = world
            record['lineages'] = lineages
        return record

    def make_article(
        self,
        *,
        slug: str,
        title: str,
        lead: str,
        body: list[dict[str, Any]],
        tags: list[str] | None = None,
        published_in: str,
        session: str,
        scope_axes: dict[str, str] | None = None,
        links: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        facts_by_id = {r['id']: r for r in self.records if r['record'] == 'fact'}
        cited_ids = [fid for claim in body for fid in claim['facts']]
        cited_facts = [facts_by_id[fid] for fid in cited_ids]
        scope: dict[str, str] = {'game': self.game}
        for fact in cited_facts:
            for key, value in fact['scope'].items():
                if key in scope and scope[key] != value:
                    raise ValueError(f'cited facts disagree on scope axis {key!r}')
                scope[key] = value
        if scope_axes:
            for key, value in scope_axes.items():
                if key in scope and scope[key] != value:
                    raise ValueError(f'article axis {key!r} conflicts with cited facts')
                scope[key] = value
        record: dict[str, Any] = {
            'schema': FACT_SCHEMA,
            'record': 'article',
            'id': f'{slug}@{published_in}',
            'slug': slug,
            'title': title,
            'lead': lead,
            'body': copy.deepcopy(body),
            'tags': list(tags or []),
            'scope': scope,
            'links': copy.deepcopy(list(links or [])),
            'last_confirmed': copy.deepcopy(max((f['seen'] for f in cited_facts), key=_order_key)),
            'valid_from': copy.deepcopy(max((f['valid_from'] for f in cited_facts), key=_order_key)),
            'valid_to': None,
            'lifecycle_state': 'active',
            'stale_citations': [],
            'needs_review': False,
            'published_in': published_in,
            'session': session,
        }
        if 'world' in scope:
            # Collect lineage labels from the frame citations of ALL cited facts (bound and unbound).
            lineages: set[str | None] = set()
            for fact in cited_facts:
                for cid in fact['citations']:
                    lineages.add(self._citation_lineage(cid))
            record['lineages'] = sort_lineages(lineages)
        return record

    def find_record(self, identity: str) -> dict[str, Any]:
        for row in self.records:
            if row['id'] == identity:
                return row
        raise KeyError(identity)

    def current_article(self, slug: str) -> dict[str, Any]:
        for row in self.records:
            if row['record'] == 'article' and row['slug'] == slug and 'superseded_by' not in row and 'retired' not in row:
                return row
        raise KeyError(slug)

    def supersede_fact(self, old_ids: list[str], new_fact: dict[str, Any], *, reason_kind: str) -> None:
        from harness.curator.check import _changed_valid_to
        state = {'corrected': 'retracted', 'changed': 'ended'}.get(reason_kind, 'superseded')
        for old_id in old_ids:
            old = self.find_record(old_id)
            old['superseded_by'] = [new_fact['id']]
            old['superseded_reason'] = reason_kind
            old['lifecycle_state'] = state
            if reason_kind == 'changed':
                old['valid_to'] = _changed_valid_to(old, new_fact, self.provenance)
        self.records.append(new_fact)

    def narrow_fact(self, old_id: str, new_facts: list[dict[str, Any]]) -> None:
        old = self.find_record(old_id)
        old['superseded_by'] = [f['id'] for f in new_facts]
        old['superseded_reason'] = 'narrowed'
        old['lifecycle_state'] = 'superseded'
        self.records.extend(new_facts)

    def retire_fact_wrong(self, fact_id: str, *, reason: str, citations: list[str], published_in: str, session: str) -> None:
        row = self.find_record(fact_id)
        row['retired'] = {
            'reason': reason,
            'reason_kind': 'wrong',
            'citations': list(citations),
            'published_in': published_in,
            'session': session,
        }
        row['lifecycle_state'] = 'retracted'
        row['valid_to'] = None

    def retire_fact_ended(
        self,
        fact_id: str,
        *,
        reason: str,
        end: str,
        end_citations: list[str],
        citations: list[str] | None = None,
        published_in: str,
        session: str,
    ) -> None:
        row = self.find_record(fact_id)
        extra_citations = list(citations or [])
        if not end_citations:
            raise ValueError('ended retirement requires non-empty end_citations')
        if set(end_citations) & set(row['citations']):
            raise ValueError('end_citations must be disjoint from the retired fact citations')
        if set(end_citations) & set(extra_citations):
            raise ValueError('end_citations and citations must be disjoint')

        seen_pos = row['seen']
        seen_key = _order_key(seen_pos)
        end_positions = self._citation_positions(end_citations)
        # Resolve supporting citations as well before mutating the fact.
        self._citation_positions(extra_citations)
        world_bound = 'world' in row['scope']

        if not world_bound:
            if 'retired' in row or 'superseded_by' in row:
                raise ValueError('unbound fact cannot be retired as ended more than once')
            if any(_order_key(pos) <= seen_key for pos in end_positions):
                raise ValueError('unbound end_citations must post-date seen in global trace order')
            event_valid_to = None
        else:
            seen_cids = [c for c in row['citations'] if self.provenance['frames'][c] == seen_pos]
            seen_lineage = self._citation_lineage(seen_cids[0])
            if self._in_abandoned_stretch(seen_lineage, seen_pos):
                raise ValueError('fact seen lies in an abandoned stretch')
            end_lineages = {self._citation_lineage(c) for c in end_citations}
            if len(end_lineages) != 1:
                raise ValueError('end_citations for a world-bound fact must share one lineage')
            end_lineage = next(iter(end_lineages))
            seen_path = self._lineage_path(seen_lineage, end_lineage, seen_pos)
            if seen_path is None:
                raise ValueError(f'end lineage {end_lineage!r} is not on seen lineage {seen_lineage!r} timeline')
            for pos in end_positions:
                if self._in_abandoned_stretch(end_lineage, pos):
                    raise ValueError('end_citation lies in an abandoned stretch')
                if self._has_unknown_restore_along_path(seen_path, seen_pos, pos):
                    raise ValueError('unknown restore between seen and end_citation')
                if end_lineage == seen_lineage and _order_key(pos) <= seen_key:
                    raise ValueError('end_citation must strictly post-date seen')
            if 'superseded_by' in row:
                raise ValueError('superseded fact cannot be retired as ended')
            if 'retired' in row:
                if row['retired'].get('reason_kind') != 'ended':
                    raise ValueError('wrong-retired fact cannot be retired as ended')
                if any(self._end_event_visible_on(ev, end_lineage, seen_pos) for ev in row['retired']['events']):
                    raise ValueError(f'fact {fact_id!r} already has a visible end on lineage {end_lineage!r}')
            # Event valid_to is set when all sightings + end_citations lie on one surviving timeline
            # (single lineage or ancestor prefix + descendant lineage).
            one_timeline = all(
                (path := self._lineage_path(self._citation_lineage(c), end_lineage, self.provenance['frames'][c])) is not None
                and not self._in_abandoned_stretch(self._citation_lineage(c), self.provenance['frames'][c])
                and all(not self._has_unknown_restore_along_path(path, self.provenance['frames'][c], pos) for pos in end_positions)
                for c in row['citations']
            )
            if one_timeline:
                chosen = max(end_positions, key=_order_key) if end == 'transition' else min(end_positions, key=_order_key)
                event_valid_to = copy.deepcopy(chosen)
            else:
                event_valid_to = None

        event = {
            'reason': reason,
            'end': end,
            'end_citations': list(end_citations),
            'citations': extra_citations,
            'valid_to': event_valid_to,
            'published_in': published_in,
            'session': session,
        }
        if 'retired' in row and row['retired'].get('reason_kind') == 'ended':
            row['retired']['events'].append(event)
        else:
            row['retired'] = {'reason_kind': 'ended', 'events': [event]}
        row['lifecycle_state'] = 'ended'
        events = row['retired']['events']
        row['valid_to'] = (
            copy.deepcopy(events[0]['valid_to'])
            if world_bound and len(events) == 1 and len(row['lineages']) == 1 and row['lineages'][0] is not None
            else None
        )

    def revise_article(self, slug: str, new_article: dict[str, Any]) -> None:
        old = self.current_article(slug)
        old['superseded_by'] = [new_article['id']]
        old['lifecycle_state'] = 'superseded'
        self.records.append(new_article)

    def retire_article(self, slug: str, *, reason: str, reason_kind: str, published_in: str, session: str) -> None:
        old = self.current_article(slug)
        old['retired'] = {
            'reason': reason,
            'reason_kind': reason_kind,
            'published_in': published_in,
            'session': session,
        }
        old['lifecycle_state'] = 'retracted' if reason_kind == 'wrong' else 'ended'

    def commit_version(
        self,
        *,
        coverage_session: str,
        last_step: int,
        actor: str = '001',
        session_kind: str = 'admission',
        admission_citations: list[str] | None = None,
        message: str | None = None,
    ) -> str:
        self.version_num += 1
        version = self.version
        recompute_stored_flags(self.records)
        if self.validate:
            for row in self.records:
                errors = sorted(_FACT_VALIDATOR.iter_errors(row), key=lambda e: list(e.path))
                if errors:
                    detail = '; '.join(f'{".".join(str(p) for p in e.path)}: {e.message}' for e in errors)
                    raise ValueError(f'synthetic record {row.get("id")!r} failed curator-fact/6 schema: {detail}')
        coverage = {
            'schema': COVERAGE_SCHEMA,
            'session': coverage_session,
            'actor': actor,
            'last_step': last_step,
        }
        if session_kind == 'admission':
            if admission_citations is None:
                cites: set[str] = set()
                for row in self.records:
                    if row['record'] == 'fact' and row['published_in'] == version:
                        cites.update(row['citations'])
                    if row['record'] == 'fact' and 'retired' in row:
                        ret = row['retired']
                        if ret['reason_kind'] == 'wrong' and ret['published_in'] == version:
                            cites.update(ret['citations'])
                        elif ret['reason_kind'] == 'ended':
                            for ev in ret['events']:
                                if ev['published_in'] == version:
                                    cites.update(ev['end_citations'])
                                    cites.update(ev.get('citations', []))
            else:
                cites = set(admission_citations)
            # Only citations whose frame belongs to `coverage_session` belong in `last_admission`.
            cites = {c for c in cites if self.provenance['frames'][c]['session'] == coverage_session}
            previous = self.provenance.get('last_admission', {})
            if previous.get('coverage', {}).get('session') == coverage_session:
                cites.update(previous['citations'])
            self.provenance['last_admission'] = {
                'coverage': copy.deepcopy(coverage),
                'citations': sorted(cites),
            }
        self._write_tag(version, message=message or f'Publish {version}', coverage=coverage)
        return version

    def _write_tag(self, tag: str, *, message: str, coverage: dict[str, Any] | None) -> None:
        files: dict[str, bytes] = {
            'knowledge.json': _dump({'schema': KNOWLEDGE_SCHEMA, 'game': self.game}),
            'facts.jsonl': _jsonl(self.records),
            'provenance.json': _dump(self.provenance),
            'programs/.keep': b'',
            'tests/.keep': b'',
        }
        if coverage is not None:
            files['coverage.json'] = _dump(coverage)
        for relative, data in files.items():
            target = self.path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        _git(self.path, 'add', '-A')
        _git(self.path, 'commit', '-q', '--no-verify', '-m', message)
        _git(self.path, 'tag', tag)


def build_two_world_two_lineage_repo(root: Path, game: str = 'example') -> dict[str, Any]:
    """Two worlds (`world-alpha`, `world-beta`), two lineages in `world-alpha`, declared
    `ruleset`/`difficulty` axes, realistic `<lineage>-a01-<suffix>` session names, links,
    conflicts, shadows, `when` conditions, article revisions, and all history kinds.
    Each publication uses one curator-session identity distinct from cited trace sessions,
    and updates `last_admission` strictly from its own trace session's frames.
    """
    b = SyntheticKnowledgeBuilder(root, game)
    sid_a1 = session_hex(1)
    sid_beta1 = session_hex(2)
    sid_b1 = session_hex(3)
    sess_a1 = f'{LINEAGE_A}-a01-{WORLD_ALPHA}'
    sess_beta1 = f'{LINEAGE_BETA}-a01-{WORLD_BETA}'
    sess_b1 = f'{LINEAGE_B}-a01-{WORLD_ALPHA}'

    # v1: admission 1 on world-alpha / lin-alpha-main.
    b.add_session(
        sid_a1, sess_a1, world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1,
        context={'ruleset': 'standard', 'difficulty': 'normal'},
    )
    fa1 = b.add_frame(sid_a1, 1, 10, order_index=1)
    fa2 = b.add_frame(sid_a1, 2, 20, order_index=1)

    b.records.extend([
        b.make_fact(
            fact_id='fire-tinder', statement_kind='observation', tags=['fire'],
            text='Dry tinder starts a fire with matches.',
            citations=[fa1], published_in='v1', session='curator-v1',
        ),
        b.make_fact(
            fact_id='boil-water-old', statement_kind='observation', tags=['water', 'fire'],
            text='Boiling murky water cleans it.',
            citations=[fa1], published_in='v1', session='curator-v1',
            when='needs a lit heat source',
        ),
        b.make_fact(
            fact_id='bad-claim-1', statement_kind='observation', tags=['water'],
            text='Tin cans hold ten litres.',
            citations=[fa1], published_in='v1', session='curator-v1',
        ),
        b.make_fact(
            fact_id='broad-shelter-loot', statement_kind='inference', tags=['loot'],
            text='Every shelter basement holds clean water.',
            citations=[fa1], published_in='v1', session='curator-v1',
        ),
        b.make_fact(
            fact_id='wrong-rumor', statement_kind='observation', tags=['fire'],
            text='Wet bark burns faster than dry paper.',
            citations=[fa1], published_in='v1', session='curator-v1',
        ),
        b.make_fact(
            fact_id='alpha-fire-lit', statement_kind='state', tags=['camp', 'fire'],
            text='The courtyard brazier is burning.',
            citations=[fa1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='alpha-crate', statement_kind='state', tags=['camp', 'loot'],
            text='The shelter crate holds rope and nails.',
            citations=[fa2], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='alpha-gate-a', statement_kind='state', state_key='key-alpha-gate', tags=['camp'],
            text='The north gate is unlocked.',
            citations=[fa2], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='shadow-standard', statement_kind='observation', tags=['fire'],
            text='In standard ruleset damp tinder needs extra kindling.',
            citations=[fa2], published_in='v1', session='curator-v1',
            scope_axes={'ruleset': 'standard'},
            links=[{'rel': 'contradicts', 'target': 'fire-tinder'}],
        ),
        b.make_fact(
            fact_id='conflict-left', statement_kind='inference', tags=['camp'],
            text='Store clean water in the basement.',
            citations=[fa2], published_in='v1', session='curator-v1',
            scope_axes={'ruleset': 'standard'},
        ),
    ])
    b.records.append(b.make_article(
        slug='camp-guide', title='Camp guide',
        lead='Initial camp fire and water notes.',
        body=[
            {'text': 'Dry tinder starts fires.', 'facts': ['fire-tinder']},
            {'text': 'The shelter crate holds rope and nails.', 'facts': ['alpha-crate']},
        ],
        tags=['camp', 'fire'], published_in='v1', session='curator-v1',
    ))
    b.records.append(b.make_article(
        slug='old-draft-guide', title='Old draft guide',
        lead='Temporary notes later retired editorially.',
        body=[{'text': 'Dry tinder starts fires.', 'facts': ['fire-tinder']}],
        tags=['camp'], published_in='v1', session='curator-v1',
    ))
    b.commit_version(coverage_session=sess_a1, last_step=20, admission_citations=[fa1, fa2])

    # v2: admission 2 on world-beta / lin-beta-main (adds beta facts, winter guide, and narrows broad-shelter-loot).
    b.add_session(
        sid_beta1, sess_beta1, world=WORLD_BETA, lineage=LINEAGE_BETA, admission=1,
        context={'ruleset': 'winter', 'difficulty': 'hard'},
    )
    fbeta1 = b.add_frame(sid_beta1, 1, 12, order_index=2)
    fbeta2 = b.add_frame(sid_beta1, 2, 24, order_index=2)

    b.records.extend([
        b.make_fact(
            fact_id='beta-only-crate', statement_kind='state', tags=['camp'],
            text='The radio tower locker holds batteries.',
            citations=[fbeta1], published_in='v2', session='curator-v2', bind_world=True,
        ),
        b.make_fact(
            fact_id='hard-only-rule', statement_kind='observation', tags=['combat'],
            text='Hard mode doubles stamina drain.',
            citations=[fbeta1], published_in='v2', session='curator-v2',
            scope_axes={'difficulty': 'hard'},
        ),
        b.make_fact(
            fact_id='winter-conditional', statement_kind='observation', tags=['weather'],
            text='Standing water freezes outdoors in winter.',
            citations=[fbeta2], published_in='v2', session='curator-v2',
            scope_axes={'ruleset': 'winter'}, when='only under winter ruleset',
        ),
    ])
    b.narrow_fact(
        'broad-shelter-loot',
        [
            b.make_fact(
                fact_id='alpha-shelter-loot', statement_kind='state', tags=['loot'],
                text='In this world the shelter basement holds clean water.',
                citations=[fa1], published_in='v2', session='curator-v2', bind_world=True,
            ),
            b.make_fact(
                fact_id='beta-shelter-loot', statement_kind='state', tags=['loot'],
                text='In this world the shelter basement holds canned beans.',
                citations=[fbeta1], published_in='v2', session='curator-v2', bind_world=True,
            ),
        ],
    )
    b.records.append(b.make_article(
        slug='winter-guide', title='Winter water guide',
        lead='Handling frozen outdoor water.',
        body=[{'text': 'Standing water freezes outdoors in winter.', 'facts': ['winter-conditional']}],
        tags=['weather'], published_in='v2', session='curator-v2',
    ))
    b.commit_version(coverage_session=sess_beta1, last_step=24, admission_citations=[fbeta1, fbeta2])

    # v3: admission 3 on world-alpha / lin-alpha-fork (unknown fork; adds b-stash, mixed-lineage note, conflict-right).
    b.add_session(
        sid_b1, sess_b1, world=WORLD_ALPHA, lineage=LINEAGE_B, admission=1,
        context={'ruleset': 'standard', 'difficulty': 'normal'},
    )
    fb1 = b.add_frame(sid_b1, 1, 15, order_index=3)
    fb2 = b.add_frame(sid_b1, 2, 25, order_index=3)

    b.records.extend([
        b.make_fact(
            fact_id='alpha-b-stash', statement_kind='state', tags=['camp', 'loot'],
            text='A hidden cache lies behind the shed.',
            citations=[fb1], published_in='v3', session='curator-v3', bind_world=True,
        ),
        b.make_fact(
            fact_id='conflict-right', statement_kind='inference', tags=['camp'],
            text='Store clean water beside the hearth.',
            citations=[fb1], published_in='v3', session='curator-v3',
            scope_axes={'ruleset': 'standard'},
            links=[{'rel': 'contradicts', 'target': 'conflict-left'}],
        ),
    ])
    b.supersede_fact(
        ['alpha-gate-a'],
        b.make_fact(
            fact_id='alpha-mixed-note', statement_kind='state', state_key='key-alpha-gate', tags=['camp'],
            text='The north gate is unlocked.',
            citations=[fa2, fb2], published_in='v3', session='curator-v3', bind_world=True,
        ),
        reason_kind='restated',
    )
    b.supersede_fact(
        ['boil-water-old'],
        b.make_fact(
            fact_id='boil-water-mid', statement_kind='observation', tags=['water', 'fire'],
            text='Boiling murky water over a fire produces clean water.',
            citations=[fa1, fb1], published_in='v3', session='curator-v3',
            when='needs a lit heat source',
            links=[{'rel': 'depends_on', 'target': 'fire-tinder'}],
        ),
        reason_kind='restated',
    )
    b.supersede_fact(
        ['bad-claim-1'],
        b.make_fact(
            fact_id='bad-claim-2', statement_kind='observation', tags=['water'],
            text='Large tin cans hold ten litres.',
            citations=[fa1], published_in='v3', session='curator-v3',
        ),
        reason_kind='restated',
    )
    b.commit_version(coverage_session=sess_b1, last_step=25, admission_citations=[fb1, fb2])

    # v4: later window on world-alpha / lin-alpha-main (register fa3 here when step 30 is observed;
    # ends alpha-fire-lit, retracts wrong-rumor, finishes chains, retires old-draft-guide, revises camp-guide).
    fa3 = b.add_frame(sid_a1, 3, 30, order_index=1)
    b.retire_fact_wrong(
        'wrong-rumor', reason='Observed wet bark failing to ignite.',
        citations=[fa2], published_in='v4', session='curator-v4',
    )
    b.retire_fact_ended(
        'alpha-fire-lit', reason='Observed brazier burnt down to ash.',
        end='transition', end_citations=[fa3], published_in='v4', session='curator-v4',
    )
    b.retire_article(
        'old-draft-guide', reason='Folded into camp-guide.',
        reason_kind='editorial', published_in='v4', session='curator-v4',
    )
    b.supersede_fact(
        ['boil-water-mid'],
        b.make_fact(
            fact_id='boil-water-final', statement_kind='observation', tags=['water', 'fire'],
            text='Boiling murky water over a lit fire yields clean drinking water.',
            subject='water boiling',
            citations=[fa1, fb1, fa3], published_in='v4', session='curator-v4',
            when='needs a lit heat source',
            links=[{'rel': 'depends_on', 'target': 'fire-tinder'}],
        ),
        reason_kind='restated',
    )
    b.supersede_fact(
        ['bad-claim-2'],
        b.make_fact(
            fact_id='tin-can-capacity', statement_kind='observation', tags=['water'],
            text='A tin can holds 0.5 litres.',
            citations=[fa3], published_in='v4', session='curator-v4',
        ),
        reason_kind='corrected',
    )
    b.revise_article(
        'camp-guide',
        b.make_article(
            slug='camp-guide', title='Camp guide',
            lead='Start a fire with dry tinder, boil murky water, and check the crate.',
            body=[
                {'text': 'Boil murky water over dry-tinder fire.', 'facts': ['boil-water-final', 'fire-tinder']},
                {'text': 'The shelter crate holds rope and nails.', 'facts': ['alpha-crate']},
            ],
            tags=['camp', 'fire', 'water'], published_in='v4', session='curator-v4',
            links=[
                {'rel': 'see_also', 'target': 'hard-only-rule'},
                {'rel': 'depends_on', 'target': 'conflict-left'},
            ],
        ),
    )
    b.commit_version(coverage_session=sess_a1, last_step=30, admission_citations=[fa2, fa3])

    return {
        'repo_root': root,
        'repo_path': b.path,
        'game': game,
        'version': b.version,
        'worlds': (WORLD_ALPHA, WORLD_BETA),
        'lineages': (LINEAGE_A, LINEAGE_B, LINEAGE_BETA),
        'session_ids': {'a1': sid_a1, 'b1': sid_b1, 'beta1': sid_beta1},
        'session_names': {'a1': sess_a1, 'b1': sess_b1, 'beta1': sess_beta1},
        'declared_axes': {'ruleset', 'difficulty'},
    }


def build_nested_cut_repo(root: Path, game: str = 'example') -> dict[str, Any]:
    """Worked history 1 (Nested cut): A records `lit-fire` at v3, B forks from A at v3,
    A ends `lit-fire` at v5, C forks from B at v7, and C publishes `c-camp-note` at v8.
    C receives both `lit-fire` (inherited) and `c-camp-note` (same).
    """
    b = SyntheticKnowledgeBuilder(root, game)
    sid_a = session_hex(11)
    sid_b = session_hex(12)
    sid_c = session_hex(13)
    sess_a = f'{LINEAGE_A}-a01-nested'
    sess_b = f'{LINEAGE_B}-a01-nested'
    sess_c = f'{LINEAGE_C}-a01-nested'

    b.add_session(sid_a, sess_a, world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1)
    f_a1 = b.add_frame(sid_a, 1, 5, order_index=1)
    f_a2 = b.add_frame(sid_a, 2, 10, order_index=1)

    # v1, v2: filler facts so `lit-fire` lands at v3, end at v5, C fork at v7, C record at v8.
    b.records.append(b.make_fact(
        fact_id='base-note-1', statement_kind='observation', tags=['camp'],
        text='Matches light dry paper.', citations=[f_a1], published_in='v1', session='curator-v1',
    ))
    b.commit_version(coverage_session=sess_a, last_step=5, admission_citations=[f_a1])

    b.records.append(b.make_fact(
        fact_id='base-note-2', statement_kind='observation', tags=['camp'],
        text='Paper burns quickly.', citations=[f_a1], published_in='v2', session='curator-v2',
    ))
    b.commit_version(coverage_session=sess_a, last_step=6, admission_citations=[f_a1])

    # v3: A records `lit-fire` at step 10 (before B's fork_at step 12).
    b.records.append(b.make_fact(
        fact_id='lit-fire', statement_kind='state', tags=['fire'],
        text='The camp fire is lit.', citations=[f_a2], published_in='v3', session='curator-v3', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_a, last_step=10, admission_citations=[f_a2])

    # v4: B forks from A at v3 and adds a note on B's timeline.
    b.add_session(
        sid_b, sess_b, world=WORLD_ALPHA, lineage=LINEAGE_B, admission=1,
        branch={'parent': LINEAGE_A, 'fork_at': position(sess_a, 12, order_index=1), 'fork_version': 'v3'},
    )
    f_b1 = b.add_frame(sid_b, 1, 14, order_index=2)
    b.records.append(b.make_fact(
        fact_id='b-camp-note', statement_kind='state', tags=['camp'],
        text='Branch B stacked extra firewood.', citations=[f_b1], published_in='v4', session='curator-v4', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_b, last_step=14, admission_citations=[f_b1])

    # v5: A retires `lit-fire` as ended on A's timeline (step 20).
    f_a3 = b.add_frame(sid_a, 3, 20, order_index=1)
    b.retire_fact_ended(
        'lit-fire', reason='Fire went out on lineage A.',
        end='transition', end_citations=[f_a3], published_in='v5', session='curator-v5',
    )
    b.commit_version(coverage_session=sess_a, last_step=20, admission_citations=[f_a3])

    # v6: A records another post-fork fact.
    f_a4 = b.add_frame(sid_a, 4, 30, order_index=1)
    b.records.append(b.make_fact(
        fact_id='a-post-fork', statement_kind='state', tags=['camp'],
        text='Lineage A moved camp south.', citations=[f_a4], published_in='v6', session='curator-v6', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_a, last_step=30, admission_citations=[f_a4])

    # v7: parent-view snapshot on B before C forks from B at v7.
    f_b2 = b.add_frame(sid_b, 2, 16, order_index=2)
    b.records.append(b.make_fact(
        fact_id='b-pre-c-note', statement_kind='state', tags=['camp'],
        text='Branch B filled the rain barrel.', citations=[f_b2], published_in='v7', session='curator-v7', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_b, last_step=16, admission_citations=[f_b2])

    # v8: C forks from B at v7 (step 16) and publishes its own post-fork record at v8.
    b.add_session(
        sid_c, sess_c, world=WORLD_ALPHA, lineage=LINEAGE_C, admission=1,
        branch={'parent': LINEAGE_B, 'fork_at': position(sess_b, 16, order_index=2), 'fork_version': 'v7'},
    )
    f_c1 = b.add_frame(sid_c, 1, 18, order_index=3)
    b.records.append(b.make_fact(
        fact_id='c-camp-note', statement_kind='state', tags=['camp'],
        text='Branch C built a lean-to.', citations=[f_c1], published_in='v8', session='curator-v8', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_c, last_step=18, admission_citations=[f_c1])

    return {
        'repo_root': root, 'repo_path': b.path, 'game': game, 'version': b.version,
        'world': WORLD_ALPHA, 'lineages': {'A': LINEAGE_A, 'B': LINEAGE_B, 'C': LINEAGE_C},
    }


def build_parent_target_repo(root: Path, game: str = 'example') -> dict[str, Any]:
    """Worked history 2 (Parent target): A records `camp-fire` at v2; B forks from A at v2
    and retires `camp-fire` as ended on B at v3; C forks from A at v4 and publishes at v5.
    A still receives `camp-fire` as `same`; C inherits `camp-fire`; B sees it in `history.ended`.
    """
    b = SyntheticKnowledgeBuilder(root, game)
    sid_a = session_hex(21)
    sid_b = session_hex(22)
    sid_c = session_hex(23)
    sess_a = f'{LINEAGE_A}-a01-parent'
    sess_b = f'{LINEAGE_B}-a01-parent'
    sess_c = f'{LINEAGE_C}-a01-parent'

    b.add_session(sid_a, sess_a, world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1)
    f_a1 = b.add_frame(sid_a, 1, 5, order_index=1)
    f_a2 = b.add_frame(sid_a, 2, 10, order_index=1)

    # v1
    b.records.append(b.make_fact(
        fact_id='seed-note', statement_kind='observation', tags=['fire'],
        text='Wood feeds fire.', citations=[f_a1], published_in='v1', session='curator-v1',
    ))
    b.commit_version(coverage_session=sess_a, last_step=5, admission_citations=[f_a1])

    # v2: A records `camp-fire` at step 10.
    b.records.append(b.make_fact(
        fact_id='camp-fire', statement_kind='state', tags=['fire'],
        text='The central camp fire is burning.', citations=[f_a2], published_in='v2', session='curator-v2', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_a, last_step=10, admission_citations=[f_a2])

    # v3: B forks from A at v2 and ends `camp-fire` on B at step 15.
    b.add_session(
        sid_b, sess_b, world=WORLD_ALPHA, lineage=LINEAGE_B, admission=1,
        branch={'parent': LINEAGE_A, 'fork_at': position(sess_a, 12, order_index=1), 'fork_version': 'v2'},
    )
    f_b1 = b.add_frame(sid_b, 1, 15, order_index=2)
    b.retire_fact_ended(
        'camp-fire', reason='Extinguished by rain on branch B.',
        end='transition', end_citations=[f_b1], published_in='v3', session='curator-v3',
    )
    b.commit_version(coverage_session=sess_b, last_step=15, admission_citations=[f_b1])

    # v4: A adds another fact at step 25.
    f_a3 = b.add_frame(sid_a, 3, 25, order_index=1)
    b.records.append(b.make_fact(
        fact_id='a-late-note', statement_kind='state', tags=['camp'],
        text='A fetched water from the well.', citations=[f_a3], published_in='v4', session='curator-v4', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_a, last_step=25, admission_citations=[f_a3])

    # v5: C forks from A at v4 and adds a note at v5.
    b.add_session(
        sid_c, sess_c, world=WORLD_ALPHA, lineage=LINEAGE_C, admission=1,
        branch={'parent': LINEAGE_A, 'fork_at': position(sess_a, 30, order_index=1), 'fork_version': 'v4'},
    )
    f_c1 = b.add_frame(sid_c, 1, 35, order_index=3)
    b.records.append(b.make_fact(
        fact_id='c-note', statement_kind='state', tags=['camp'],
        text='C pitched a tent.', citations=[f_c1], published_in='v5', session='curator-v5', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_c, last_step=35, admission_citations=[f_c1])

    return {
        'repo_root': root, 'repo_path': b.path, 'game': game, 'version': b.version,
        'world': WORLD_ALPHA, 'lineages': {'A': LINEAGE_A, 'B': LINEAGE_B, 'C': LINEAGE_C},
    }


def build_restore_repo(root: Path, game: str = 'example') -> dict[str, Any]:
    """Worked history 3 (Restore): in lineage L, `lit-fire` (f) and `cached-crate` (k) seen at
    step 10 (v2), saved at 12 (`saved_version: v2`); `abandoned-loot` (g) seen at 15 (v3);
    restored at 20 (`restored_version: v3`); at 22 (v4), `lit-fire` ended and `post-restore-note` (h) seen.
    """
    b = SyntheticKnowledgeBuilder(root, game)
    sid_l = session_hex(31)
    sess_l = f'{LINEAGE_RESTORE}-a01-restore'
    b.add_session(sid_l, sess_l, world=WORLD_ALPHA, lineage=LINEAGE_RESTORE, admission=1)

    f_5 = b.add_frame(sid_l, 1, 5, order_index=1)
    f_10 = b.add_frame(sid_l, 2, 10, order_index=1)

    # v1
    b.records.append(b.make_fact(
        fact_id='general-rule', statement_kind='observation', tags=['camp'],
        text='Crates hold supplies.', citations=[f_5], published_in='v1', session='curator-v1',
    ))
    b.commit_version(coverage_session=sess_l, last_step=5, admission_citations=[f_5])

    # v2: f (`lit-fire`) and k (`cached-crate`) at step 10.
    b.records.extend([
        b.make_fact(
            fact_id='lit-fire', statement_kind='state', tags=['fire'],
            text='The shelter fire is lit.', citations=[f_10], published_in='v2', session='curator-v2', bind_world=True,
        ),
        b.make_fact(
            fact_id='cached-crate', statement_kind='state', tags=['loot'],
            text='The east crate holds dried food.', citations=[f_10], published_in='v2', session='curator-v2', bind_world=True,
        ),
    ])
    b.commit_version(coverage_session=sess_l, last_step=10, admission_citations=[f_10])

    # v3: g (`abandoned-loot`) at step 15 on abandoned stretch (12, 20).
    f_15 = b.add_frame(sid_l, 3, 15, order_index=1)
    b.records.append(b.make_fact(
        fact_id='abandoned-loot', statement_kind='state', tags=['loot'],
        text='Found a crowbar on the abandoned timeline.', citations=[f_15], published_in='v3', session='curator-v3', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_l, last_step=15, admission_citations=[f_15])

    # v4: restore at 20 from save at 12; at step 22, `lit-fire` ends and `post-restore-note` (h) is seen.
    f_22 = b.add_frame(sid_l, 4, 22, order_index=1)
    b.add_restore(
        lineage=LINEAGE_RESTORE,
        restored_at=position(sess_l, 20, order_index=1),
        restored_version='v3',
        saved_at=position(sess_l, 12, order_index=1),
        saved_version='v2',
    )
    b.retire_fact_ended(
        'lit-fire', reason='Fire was out after restore.',
        end='absence', end_citations=[f_22], published_in='v4', session='curator-v4',
    )
    b.records.append(b.make_fact(
        fact_id='post-restore-note', statement_kind='state', tags=['camp'],
        text='Found bandages in the locker after restore.', citations=[f_22], published_in='v4', session='curator-v4', bind_world=True,
    ))
    b.commit_version(coverage_session=sess_l, last_step=22, admission_citations=[f_22])

    return {
        'repo_root': root, 'repo_path': b.path, 'game': game, 'version': b.version,
        'world': WORLD_ALPHA, 'lineage': LINEAGE_RESTORE,
    }


def build_falsity_propagation_repo(root: Path, game: str = 'example') -> dict[str, Any]:
    """Tests falsity propagation across direct retraction, faithful restatement, faithful merge,
    and applicable vs inapplicable narrowing children for a child lineage forked at v1.
    """
    b = SyntheticKnowledgeBuilder(root, game)
    sid_a = session_hex(41)
    sid_b = session_hex(42)
    sess_a = f'{LINEAGE_A}-a01-falsity'
    sess_b = f'{LINEAGE_B}-a01-falsity'

    b.add_session(
        sid_a, sess_a, world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1,
        context={'ruleset': 'standard'},
    )
    f_a1 = b.add_frame(sid_a, 1, 10, order_index=1)

    # v1: pre-fork facts on A.
    b.records.extend([
        b.make_fact(
            fact_id='f-direct', statement_kind='state', tags=['camp'],
            text='The bridge is intact.', citations=[f_a1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='f-restated', statement_kind='state', state_key='key-cellar-door', tags=['camp'],
            text='The cellar door is unlocked.', citations=[f_a1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='f-merge-a', statement_kind='observation', tags=['camp'],
            text='Two batteries sit on the bench.', citations=[f_a1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='f-merge-b', statement_kind='observation', tags=['camp'],
            text='Batteries are on the workshop bench.', citations=[f_a1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='f-narrowed', statement_kind='state', tags=['water'],
            text='The pond is drinkable.', citations=[f_a1], published_in='v1', session='curator-v1', bind_world=True,
        ),
        b.make_fact(
            fact_id='f-surviving', statement_kind='state', tags=['camp'],
            text='The roof does not leak.', citations=[f_a1], published_in='v1', session='curator-v1', bind_world=True,
        ),
    ])
    b.commit_version(coverage_session=sess_a, last_step=10, admission_citations=[f_a1])

    # v2: register child B forked at v1, plus post-fork restatements, merge, and narrowing on A.
    b.add_session(
        sid_b, sess_b, world=WORLD_ALPHA, lineage=LINEAGE_B, admission=1,
        context={'ruleset': 'standard'},
        branch={'parent': LINEAGE_A, 'fork_at': position(sess_a, 12, order_index=1), 'fork_version': 'v1'},
    )
    b.add_frame(sid_b, 1, 15, order_index=2)
    f_a2 = b.add_frame(sid_a, 2, 20, order_index=1)

    b.retire_fact_wrong(
        'f-direct', reason='Bridge was actually collapsed.',
        citations=[f_a2], published_in='v2', session='curator-v2',
    )
    b.supersede_fact(
        ['f-restated'],
        b.make_fact(
            fact_id='f-restated-2', statement_kind='state', state_key='key-cellar-door', tags=['camp'],
            text='The cellar door has no lock.', citations=[f_a1, f_a2], published_in='v2', session='curator-v2', bind_world=True,
        ),
        reason_kind='restated',
    )
    b.supersede_fact(
        ['f-merge-a', 'f-merge-b'],
        b.make_fact(
            fact_id='f-merged', statement_kind='observation', tags=['camp'],
            text='Two batteries sit on the workshop bench.', citations=[f_a1], published_in='v2', session='curator-v2', bind_world=True,
        ),
        reason_kind='restated',
    )
    b.narrow_fact(
        'f-narrowed',
        [
            b.make_fact(
                fact_id='f-narrow-winter', statement_kind='state', tags=['water'],
                text='Under winter ruleset the pond is drinkable.',
                citations=[f_a1], published_in='v2', session='curator-v2', bind_world=True,
                scope_axes={'ruleset': 'winter'},
            ),
            b.make_fact(
                fact_id='f-narrow-standard', statement_kind='state', tags=['water'],
                text='Under standard ruleset the pond is drinkable.',
                citations=[f_a1], published_in='v2', session='curator-v2', bind_world=True,
                scope_axes={'ruleset': 'standard'},
            ),
        ],
    )
    b.commit_version(coverage_session=sess_a, last_step=20, admission_citations=[f_a2])

    # v3: retract f-restated-2 (corrected), f-merged (wrong), and f-narrow-winter (wrong).
    f_a3 = b.add_frame(sid_a, 3, 30, order_index=1)
    b.supersede_fact(
        ['f-restated-2'],
        b.make_fact(
            fact_id='f-cellar-locked', statement_kind='state', state_key='key-cellar-door', tags=['camp'],
            text='The cellar door is bolted shut.', citations=[f_a3], published_in='v3', session='curator-v3', bind_world=True,
        ),
        reason_kind='corrected',
    )
    b.retire_fact_wrong(
        'f-merged', reason='Bench actually held empty casings.',
        citations=[f_a3], published_in='v3', session='curator-v3',
    )
    b.retire_fact_wrong(
        'f-narrow-winter', reason='Pond is frozen solid in winter.',
        citations=[f_a3], published_in='v3', session='curator-v3',
    )
    b.commit_version(coverage_session=sess_a, last_step=30, admission_citations=[f_a3])

    return {
        'repo_root': root, 'repo_path': b.path, 'game': game, 'version': b.version,
        'world': WORLD_ALPHA, 'lineages': {'A': LINEAGE_A, 'B': LINEAGE_B},
    }


def build_cycle_and_withholding_repo(root: Path, game: str = 'example') -> dict[str, Any]:
    """Tests `depends_on` cycles (unseeded, contested-seeded, and stale-citation-seeded)
    and withheld-dependency clearing.
    """
    b = SyntheticKnowledgeBuilder(root, game)
    sid = session_hex(51)
    sess = f'{LINEAGE_A}-a01-cycle'
    b.add_session(sid, sess, world=WORLD_ALPHA, lineage=LINEAGE_A, admission=1)
    f1 = b.add_frame(sid, 1, 10, order_index=1)
    f2 = b.add_frame(sid, 2, 20, order_index=1)

    b.records.extend([
        # Unseeded 2-cycle: both must remain needs_review=False.
        b.make_fact(
            fact_id='clean-cycle-a', statement_kind='observation', tags=['cycle'],
            text='Clean cycle node A.', citations=[f1], published_in='v1', session='curator-v1',
            links=[],
        ),
        b.make_fact(
            fact_id='clean-cycle-b', statement_kind='observation', tags=['cycle'],
            text='Clean cycle node B.', citations=[f1], published_in='v1', session='curator-v1',
            links=[{'rel': 'depends_on', 'target': 'clean-cycle-a'}],
        ),
        # Contested-seeded 2-cycle: both nodes in cycle become needs_review=True.
        b.make_fact(
            fact_id='seed-conflict-1', statement_kind='inference', tags=['cycle'],
            text='Conflict side 1.', citations=[f1], published_in='v1', session='curator-v1',
            links=[{'rel': 'contradicts', 'target': 'seed-conflict-2'}],
        ),
        b.make_fact(
            fact_id='seed-conflict-2', statement_kind='inference', tags=['cycle'],
            text='Conflict side 2.', citations=[f1], published_in='v1', session='curator-v1',
            links=[{'rel': 'contradicts', 'target': 'seed-conflict-1'}],
        ),
        b.make_fact(
            fact_id='dirty-cycle-a', statement_kind='inference', tags=['cycle'],
            text='Dirty cycle node A.', citations=[f1], published_in='v1', session='curator-v1',
            links=[
                {'rel': 'depends_on', 'target': 'seed-conflict-1'},
            ],
        ),
        b.make_fact(
            fact_id='dirty-cycle-b', statement_kind='inference', tags=['cycle'],
            text='Dirty cycle node B.', citations=[f1], published_in='v1', session='curator-v1',
            links=[{'rel': 'depends_on', 'target': 'dirty-cycle-a'}],
        ),
        # Stale-citation premise retired at v2, with direct dependent and transitive 2-cycle.
        b.make_fact(
            fact_id='stale-premise', statement_kind='observation', tags=['stale'],
            text='Premise later retracted at v2.', citations=[f1], published_in='v1', session='curator-v1',
        ),
        b.make_fact(
            fact_id='stale-dependent', statement_kind='inference', tags=['stale'],
            text='Strategy directly relying on stale-premise.', citations=[f1], published_in='v1', session='curator-v1',
            links=[{'rel': 'depends_on', 'target': 'stale-premise'}],
        ),
        b.make_fact(
            fact_id='stale-cycle-a', statement_kind='inference', tags=['stale'],
            text='Stale cycle node A.', citations=[f1], published_in='v1', session='curator-v1',
            links=[
                {'rel': 'depends_on', 'target': 'stale-premise'},
            ],
        ),
        b.make_fact(
            fact_id='stale-cycle-b', statement_kind='inference', tags=['stale'],
            text='Stale cycle node B.', citations=[f1], published_in='v1', session='curator-v1',
            links=[{'rel': 'depends_on', 'target': 'stale-cycle-a'}],
        ),
        # Withheld-dependency test pair: `dependent-fact` depends only on current `base-dep`.
        b.make_fact(
            fact_id='base-dep', statement_kind='observation', tags=['dep'],
            text='Base dependency fact.', citations=[f1], published_in='v1', session='curator-v1',
        ),
        b.make_fact(
            fact_id='dependent-fact', statement_kind='inference', tags=['dep'],
            text='Strategy depending on base-dep.', citations=[f2], published_in='v1', session='curator-v1',
            links=[{'rel': 'depends_on', 'target': 'base-dep'}],
        ),
    ])
    b.commit_version(coverage_session=sess, last_step=20, admission_citations=[f1, f2])

    # v2: retire `stale-premise` as wrong so `stale-dependent` and `stale-cycle-a` carry real stale_citations.
    f3 = b.add_frame(sid, 3, 30, order_index=1)
    b.retire_fact_wrong(
        'stale-premise', reason='Disproved at step 30.',
        citations=[f3], published_in='v2', session='curator-v2',
    )
    b.commit_version(coverage_session=sess, last_step=30, admission_citations=[f3])

    return {
        'repo_root': root, 'repo_path': b.path, 'game': game, 'version': b.version,
        'world': WORLD_ALPHA, 'lineage': LINEAGE_A,
    }
