"""Freeze one published version and its independent per-unit withholding draw."""
from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
import random
import re
import sys

import numpy as np

from harness.curator import check
from harness.curator.knowledge import KnowledgeError, Repository, _git
from harness.jsonio import strict_loads
from harness.player.knowledge import Knowledge, _classified, empty
from harness.trace.projection import valid_context

PRIVATE_FILES = {'knowledge-full.json', 'units.json'}
STUDY_DRAW_SCHEMA = 'withholding-study-draw/2'
WORLD_LABEL = re.compile(r'[ -~]{1,40}')
COMMIT_SHA = re.compile(r'[0-9a-f]{40}')
SELECTION_FIELDS = {'world', 'lineage', 'context', 'session_aliases', 'excluded_unknown_axis', 'delivered_sha256'}


def world_label(world: str | None) -> str | None:
    if world is not None and (not isinstance(world, str) or WORLD_LABEL.fullmatch(world) is None):
        raise ValueError('world must be null or 1 to 40 printable ASCII characters')
    return world


def target_labels(world: str | None, lineage: str | None, context: dict | None) -> tuple[str | None, str | None, dict]:
    world_label(world)
    if lineage is not None and (not isinstance(lineage, str) or not WORLD_LABEL.fullmatch(lineage) or world is None):
        raise ValueError('lineage must be null or 1 to 40 printable ASCII characters and requires a world')
    if context is None:
        context = {}
    if not valid_context(context):
        raise ValueError('context must hold up to eight curator axes with printable ASCII values of length 1 to 64')
    return world, lineage, dict(context)


def selection_matches(selection: object, manifest: dict) -> bool:
    return (isinstance(selection, dict) and set(selection) == SELECTION_FIELDS
            and all(label in manifest['labels'] and selection[label] == manifest['labels'][label]
                    for label in ('world', 'lineage'))
            and selection['context'] == manifest['context']
            and selection['delivered_sha256'] == manifest['files']['delivered-knowledge.json'])


def units(knowledge: dict) -> dict:
    """The one unit rule: exclusive facts in units; multiply cited facts in shared."""
    cited = {}
    for article in knowledge['articles']:
        for identity in {f for claim in article['body'] for f in claim['facts']}:
            cited.setdefault(identity, set()).add(article['id'])
    result = [dict(id=a['id'], article_id=a['id'],
                   fact_ids=sorted(f for f, owners in cited.items() if owners == {a['id']}))
              for a in knowledge['articles']]
    result.extend(dict(id=f['id'], article_id=None, fact_ids=[f['id']])
                  for f in knowledge['facts'] if f['id'] not in cited)
    return dict(units=sorted(result, key=lambda u: u['id']),
                shared=[dict(fact_id=f, article_ids=sorted(owners)) for f, owners in sorted(cited.items()) if len(owners) > 1])


def delivered_fact_ids(record: dict) -> set[str]:
    """Resolve the recorded draw, including shared facts, for export and the judges."""
    articles = {u['article_id'] for u in record['units'] if not u['withheld'] and u['article_id'] is not None}
    return ({f for u in record['units'] if not u['withheld'] for f in u['fact_ids']}
            | {row['fact_id'] for row in record['shared'] if articles.intersection(row['article_ids'])})


def draw(knowledge: dict, seed: int | None) -> tuple[dict, dict]:
    record = _draw_record(knowledge, seed)
    return filter_delivery(knowledge, record), record


def _draw_record(knowledge: dict, seed: int | None) -> dict:
    rng = random.Random(seed)
    layout = units(knowledge)
    drawn = [dict(u, withheld=seed is not None and rng.random() < .5) for u in layout['units']]
    return dict(schema='knowledge-units/1', version=knowledge['version'], seed=seed, units=drawn, shared=layout['shared'])


def filter_delivery(knowledge: dict, record: dict) -> dict:
    return _project(knowledge, record, withholds=record['schema'] == 'knowledge-units/2' or record['seed'] is not None)


def _subset(knowledge: dict, record: dict) -> dict:
    article_ids = {u['article_id'] for u in record['units'] if not u['withheld'] and u['article_id'] is not None}
    fact_ids = delivered_fact_ids(record)
    delivered = copy.deepcopy(knowledge)
    delivered['articles'] = [a for a in delivered['articles'] if a['id'] in article_ids]
    delivered['facts'] = [f for f in delivered['facts'] if f['id'] in fact_ids]
    cited_frames = {src for f in delivered['facts'] for src in f['citation_source_ids']}
    delivered['frame_clocks'] = {fid: label for fid, label in sorted(delivered.get('frame_clocks', {}).items())
                                 if fid in cited_frames}
    return delivered


def blocked_assignment(rng: np.random.Generator, sizes: list[int], count: int,
                       half_sizes: np.ndarray | None = None, draws: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Independent permutations per unit/block; odd blocks first toss a fair half-size coin."""
    result = np.zeros((draws, count, sum(sizes)), dtype=bool)
    halves = np.zeros((draws, count, len(sizes)), dtype=int)
    offset = 0
    for b, size in enumerate(sizes):
        k = (size // 2 + rng.integers(0, 2, (draws, count)) * (size % 2)
             if half_sizes is None else np.broadcast_to(half_sizes[:, b], (draws, count)))
        ranks = rng.random((draws, count, size)).argsort(axis=-1).argsort(axis=-1)
        result[:, :, offset:offset + size] = ranks < k[:, :, None]
        halves[:, :, b] = k
        offset += size
    return result, halves


def study_draw(knowledge: dict, starts: int, blocks: list[str], seed: int,
               placebo: list[str] = (), *, commit: str, world: str | None = None) -> dict:
    layout = units(knowledge)
    return layout_draw(knowledge['version'], layout, starts, blocks, seed, placebo, commit=commit, world=world)


def layout_draw(version: str, layout: dict, starts: int, blocks: list[str], seed: int,
                placebo: list[str], *, commit: str, world: str | None = None) -> dict:
    if not isinstance(commit, str) or COMMIT_SHA.fullmatch(commit) is None:
        raise ValueError('study draw commit must be a 40-hex commit SHA')
    world_label(world)
    parsed = []
    for spec in blocks:
        label, size = spec.rsplit(':', 1)
        if not label or int(size) < 2 or label in [b['label'] for b in parsed]:
            raise ValueError('blocks need unique labels and counts >= 2')
        parsed.append(dict(label=label, count=int(size)))
    if starts < 2 or sum(b['count'] for b in parsed) != starts:
        raise ValueError('blocks must sum to starts, with starts >= 2')
    identities = [u['id'] for u in layout['units']]
    if len(set(placebo)) != len(placebo) or set(placebo) - set(identities):
        raise ValueError('placebo IDs must be unique units of the layout')
    assignment, halves = blocked_assignment(np.random.default_rng(seed), [b['count'] for b in parsed], len(identities))
    ordered = []
    for block in parsed:
        offset = len(ordered)
        ordered.extend(dict(index=i, block=block['label']) for i in range(offset, offset + block['count']))
    rows = []
    for u, identity in enumerate(identities):
        for b, block in enumerate(parsed):
            indices = [s['index'] for s in ordered if s['block'] == block['label']]
            rows.append(dict(unit_id=identity, block=block['label'], half_size=int(halves[0, u, b]),
                             withheld=[i for i in indices if assignment[0, u, i]]))
    return dict(schema=STUDY_DRAW_SCHEMA, version=version, commit=commit, world=world, layout=layout, seed=seed,
                blocks=parsed, starts=ordered, placebo=list(placebo), assignment=rows)


def read_study_draw(path: Path) -> dict:
    return _checked_study_draw(path.read_bytes())


def _checked_study_draw(data: bytes) -> dict:
    value = strict_loads(data)
    if not isinstance(value, dict) or value.get('schema') != STUDY_DRAW_SCHEMA:
        raise ValueError(f'expected {STUDY_DRAW_SCHEMA}')
    expected = layout_draw(value['version'], value['layout'], len(value['starts']),
                           [f"{b['label']}:{b['count']}" for b in value['blocks']], value['seed'], value['placebo'],
                           commit=value['commit'], world=value['world'])
    if expected != value:
        raise ValueError('study draw differs from its seeded blocked assignment')
    return value


def study_record(knowledge: dict, path: Path, index: int, *, commit: str | None, world: str | None) -> dict:
    data = path.read_bytes()
    value = _checked_study_draw(data)
    if (value['version'], value['commit'], value['world'], value['layout']) != (
            knowledge['version'], commit, world, units(knowledge)):
        raise ValueError('study draw version, commit, world or layout differs from knowledge')
    if not 0 <= index < len(value['starts']):
        raise ValueError('start index is outside the study draw')
    block = value['starts'][index]['block']
    rows = {r['unit_id']: r for r in value['assignment'] if r['block'] == block}
    return dict(schema='knowledge-units/2', version=value['version'], seed=value['seed'],
                draw_sha256=hashlib.sha256(data).hexdigest(), start_index=index, block=block,
                units=[dict(u, withheld=index in rows[u['id']]['withheld'], placebo=u['id'] in value['placebo'])
                       for u in value['layout']['units']], shared=value['layout']['shared'])


def tag_commit(path: Path, version: str) -> str:
    repo = Repository(path.parent, path.name)
    return _git(repo.path, 'rev-parse', f'{version}^{{commit}}').decode().strip()


def _match(axes: dict, context: dict) -> bool | None:
    """Kleene AND: a mismatch wins even if another axis is missing."""
    if any(context[key] != value for key, value in axes.items() if key in context):
        return False
    return True if axes.keys() <= context.keys() else None


def _publication(row: dict) -> int:
    return int(row['published_in'][1:])


def _has_cut(branch: dict) -> bool:
    return all(branch.get(key) is not None for key in ('parent', 'fork_at', 'fork_version'))


def _reason(row: dict) -> str:
    if 'superseded_reason' in row:
        return row['superseded_reason']
    if row['lifecycle_state'] == 'retracted':
        return 'corrected'
    return 'narrowed' if len(row.get('superseded_by', ())) > 1 else 'restated'


class _Snapshot:
    def __init__(self, repo: Repository, version: str):
        self.rows = {}
        for row in repo.records(version):
            if (not isinstance(row, dict) or row.get('schema') != check.FACT
                    or row.get('record') not in ('fact', 'article') or not isinstance(row.get('scope'), dict)
                    or row['scope'].get('game') != repo.game):
                raise KnowledgeError(f'{version}: invalid record, expected {check.FACT} for {repo.game}')
            self.rows[row['id']] = row
        self.provenance = repo.provenance(version)
        self.branches = self.provenance['branches']
        self.lineages = {row['name']: row['lineage'] for row in self.provenance['sessions'].values()}
        self.frame_clocks = dict(self.provenance.get('frame_clocks', {}))
        self.restores = defaultdict(list)
        for restore in sorted(self.provenance['restores'], key=lambda row: row['restored_at']['order']):
            self.restores[restore['lineage']].append(restore)
        self.incoming = check._incoming_edges(list(self.rows.values()))
        self.all_state_keys = check.state_keys(list(self.rows.values()))
        self._pos_clocks: dict[tuple[str, str, int], str] = {}
        self._segment_clocks: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
        for fid, label in self.frame_clocks.items():
            pos = self.provenance['frames'].get(fid)
            if pos is not None:
                self._pos_clocks[(pos['session'], pos['actor'], pos['step'])] = label
                self._segment_clocks[(pos['session'], pos['actor'])].append((pos['step'], label))
        for items in self._segment_clocks.values():
            items.sort()

    def decorate_position(self, position: dict) -> dict:
        """Attach direct `clock_label` or nearest earlier same-segment `prior_clock` to a position copy."""
        out = dict(position)
        key = (out['session'], out['actor'], out['step'])
        direct = self._pos_clocks.get(key)
        if direct is not None:
            out['clock_label'] = direct
            return out
        lineage = self.lineages.get(out['session'])
        earlier = None
        for step, label in self._segment_clocks.get((out['session'], out['actor']), ()):
            if step >= out['step']:
                break
            # Do not carry across a restore boundary inside the same actor segment.
            if lineage is not None and any(
                    r['restored_at']['session'] == out['session']
                    and r['restored_at']['actor'] == out['actor']
                    and step < r['restored_at']['step'] <= out['step']
                    for r in self.restores.get(lineage, ())):
                continue
            earlier = (step, label)
        if earlier is not None:
            out['prior_clock'] = {'label': earlier[1], 'step_offset': out['step'] - earlier[0]}
        return out

    def positions(self, row: dict) -> list[dict]:
        citations = (row['citations'] if row['record'] == 'fact' else
                     {frame for fact in check.cited_facts(row) for frame in self.rows[fact]['citations']})
        return check._frame_positions(citations, self.provenance)

    def own_positions(self, row: dict, lineage: str) -> list[list]:
        return [position['order'] for position in self.positions(row) if self.lineages.get(position['session']) == lineage]

    def survives(self, row: dict, lineage: str | None) -> bool:
        timeline = self.timeline(lineage)
        for position in self.positions(row):
            source = self.lineages.get(position['session'])
            cut = timeline.get(source)
            for restore in self.restores.get(source, ()):
                restored = restore['restored_at']['order']
                if cut is not None and restored > cut['order']:
                    break
                if restore['saved_at'] is not None and restore['saved_at']['order'] < position['order'] < restored:
                    return False
        return True

    def branch(self, lineage: str) -> dict:
        return self.branches.get(lineage, {})

    def timeline(self, lineage: str | None) -> dict:
        """The known path, bounded at each ancestor's cut."""
        path, cut = {}, None
        while lineage is not None:
            if lineage in path:
                raise KnowledgeError(f'branch parent cycle at {lineage!r}')
            path[lineage] = cut
            branch = self.branch(lineage)
            if not _has_cut(branch):
                break
            lineage, cut = branch['parent'], branch['fork_at']
        return path

    def cut(self, lineage: str) -> tuple[str, dict, str] | None:
        for restore in reversed(self.restores.get(lineage, ())):
            if restore['saved_at'] is not None and restore['saved_version'] is not None:
                return lineage, restore['saved_at'], restore['saved_version']
        branch = self.branch(lineage)
        if _has_cut(branch):
            return branch['parent'], branch['fork_at'], branch['fork_version']
        return None

    def after_restore(self, row: dict, lineage: str) -> bool:
        restore = next((r for r in reversed(self.restores.get(lineage, ())) if r['saved_at'] is not None), None)
        if restore is None:
            return True
        version = restore['restored_version']
        return ((version is not None and _publication(row) > int(version[1:]))
                or any(p >= restore['restored_at']['order'] for p in self.own_positions(row, lineage)))

    def uncertain_restore(self, row: dict, lineage: str) -> bool:
        return any(r['saved_at'] is None and any(p < r['restored_at']['order']
                                                 for p in self.own_positions(row, lineage))
                   for r in self.restores.get(lineage, ()))


class _TargetView:
    def __init__(self, repo: Repository, version: str, world: str | None, lineage: str | None, context: dict):
        self.repo, self.version = repo, version
        self.world, self.lineage, self.context = world, lineage, context
        self.snapshots = {}
        self.coverages = {}
        self.views = {}
        self.snapshot = self.at(version)

    def at(self, version: str) -> _Snapshot:
        if version not in self.snapshots:
            self.snapshots[version] = _Snapshot(self.repo, version)
        return self.snapshots[version]

    def coverage(self, version: str) -> dict | None:
        if version not in self.coverages:
            files = _git(self.repo.path, 'ls-tree', '--name-only', version, 'coverage.json').splitlines()
            self.coverages[version] = json.loads(self.repo._show(version, 'coverage.json')) if files else None
        return self.coverages[version]

    def visible_end(self, row: dict, lineage: str | None, snap: _Snapshot) -> bool:
        if row['lifecycle_state'] != 'ended':
            return False
        if 'world' not in row['scope']:
            return True
        if lineage is None:
            return False
        if row['record'] == 'fact':
            return check._visible_end(row, lineage, snap.provenance, snap.rows)
        retired = row['retired']
        version = retired['published_in']
        retirement = self.at(version)
        coverage = self.coverage(version) or {}
        # The publication's stamp names the admitted trace. Grooming/hygiene carries the last admission's stamp.
        session = coverage.get('session') or retirement.provenance.get('last_admission', {}).get('coverage', {}).get('session')
        names = {name for name in (session or '').split(',') if name}
        if not (names <= retirement.lineages.keys() and {retirement.lineages[name] for name in names} == {lineage}):
            return False
        branch = snap.branch(lineage)
        if branch.get('fork_at') is not None and (branch['fork_version'] is None
                                                  or int(version[1:]) <= int(branch['fork_version'][1:])):
            return False
        for restore in snap.restores.get(lineage, ()):
            saved, restored = restore['saved_version'], restore['restored_version']
            if not ((saved is not None and int(version[1:]) <= int(saved[1:]))
                    or (restored is not None and int(version[1:]) > int(restored[1:]))):
                return False
        return True

    def resolved(self, lineage: str, version: str) -> dict[str, tuple[dict, str]]:
        key = lineage, version
        if key in self.views:
            return self.views[key]
        snap = self.at(version)
        own = [r for r in snap.rows.values() if r.get('lineages') == [lineage] and snap.survives(r, lineage)]
        cut = snap.cut(lineage)
        if cut is None:
            view = {r['id']: (r, 'same') for r in own
                    if check.current(r) or r['lifecycle_state'] == 'ended'}
        else:
            parent, fork_at, fork_version = cut
            cut_number = int(fork_version[1:])
            if cut_number >= int(version[1:]):
                raise KnowledgeError(f'{version}: timeline cut {fork_version} is outside the published prefix')
            parent_snapshot = self.at(fork_version)
            view = {identity: (row, 'unknown' if relation == 'unknown' else 'inherited')
                    for identity, (row, relation) in self.resolved(parent, fork_version).items()
                    if all(p <= fork_at['order'] for p in parent_snapshot.own_positions(row, parent))}
            previous = defaultdict(list)
            for row in snap.rows.values():
                for successor in row.get('superseded_by', ()):
                    previous[successor].append(row['id'])
            for row in sorted(own, key=lambda r: (_publication(r), r['id'])):
                if _publication(row) > cut_number and snap.after_restore(row, lineage):
                    for identity in previous[row['id']]:
                        view.pop(identity, None)
                    view[row['id']] = row, 'same'

        self.views[key] = {
            identity: (row, 'unknown' if snap.uncertain_restore(row, lineage) else relation)
            for identity, (row, relation) in view.items()
            if snap.survives(row, lineage)
            and not self.visible_end(snap.rows.get(identity, row), lineage, snap)
            and (relation == 'inherited' or row['lifecycle_state'] != 'retracted')
        }
        return self.views[key]

    def applicable(self, row: dict) -> bool | None:
        scope = row['scope']
        if 'world' in scope and scope['world'] != self.world:
            return False
        return _match(check._axes(scope), self.context)

    def falsified(self, identity: str) -> bool:
        pending, visited = [identity], set()
        while pending:
            identity = pending.pop()
            if identity in visited or identity not in self.snapshot.rows:
                continue
            visited.add(identity)
            row = self.snapshot.rows[identity]
            if row['lifecycle_state'] == 'retracted':
                return True
            if row.get('superseded_reason') == 'changed':
                continue
            successors = row.get('superseded_by', ())
            if len(successors) > 1:
                successors = [i for i in successors if self.applicable(self.snapshot.rows[i]) is True]
            pending.extend(successors)
        return False

    def unknown_lineage(self, row: dict) -> bool:
        sources = row['lineages']
        if self.lineage is None or len(sources) != 1 or sources[0] is None:
            return True
        source = sources[0]
        return not (self.snapshot.timeline(source).keys() & self.snapshot.timeline(self.lineage).keys())

    def _anchor_display(self, anchor: str, world: str | None, facts: dict[str, dict]) -> str:
        live = [f for f in facts.values() if f.get('state_key') == anchor and f.get('subject')]
        if live:
            return max(live, key=lambda f: (f['seen']['order'], f['id']))['subject']
        hist = [r for r in self.snapshot.rows.values()
                if r['record'] == 'fact' and r.get('state_key') == anchor
                and r['scope'].get('world') == world and r.get('subject')]
        if hist:
            return max(hist, key=lambda r: (r['seen']['order'], r['id']))['subject']
        return anchor.replace('-', ' ')

    def eligible(self) -> tuple[dict, int]:
        selected = self.resolved(self.lineage, self.version) if self.lineage is not None else {}
        candidates = {identity: (row, None) for identity, row in self.snapshot.rows.items() if check.current(row)}
        candidates.update(selected)
        facts, articles, excluded = {}, {}, 0
        for kind, result in (('fact', facts), ('article', articles)):
            for identity, (row, relation) in sorted(candidates.items(),
                                                    key=lambda item: (check.owner(item[1][0]), _publication(item[1][0]))):
                if row['record'] != kind:
                    continue
                matches = self.applicable(row)
                if matches is None:
                    excluded += 1
                if matches is not True:
                    continue
                if 'world' in row['scope']:
                    if identity in selected:
                        if self.falsified(identity):
                            continue
                    elif self.unknown_lineage(row) and (self.lineage is None or self.snapshot.survives(row, self.lineage)):
                        relation = 'unknown'
                    else:
                        continue
                if kind == 'article' and not check.cited_facts(row) <= facts.keys():
                    continue
                result[check.owner(row)] = _public_record(row, relation, facts, self.snapshot)
        for fact in facts.values():
            if 'anchor' in fact:
                fact['anchor_display'] = self._anchor_display(fact['anchor'], self.world, facts)
        cited_frames = {src for f in facts.values() for src in f['citation_source_ids']}
        frame_clocks = {fid: label for fid, label in sorted(self.snapshot.frame_clocks.items()) if fid in cited_frames}
        return dict(frame_clocks=frame_clocks, articles=list(articles.values()), facts=list(facts.values())), excluded

    def historical_lineage(self, row: dict) -> bool:
        """Whether this row's positions and publication would qualify if it were still current."""
        if 'world' not in row['scope']:
            return True
        snap, lineage = self.snapshot, self.lineage
        if lineage is not None and not snap.survives(row, lineage):
            return False
        if self.unknown_lineage(row):
            return True
        while lineage is not None:
            cut = snap.cut(lineage)
            if row['lineages'] == [lineage] and (cut is None or
                                                 (_publication(row) > int(cut[2][1:]) and snap.after_restore(row, lineage))):
                return True
            if cut is None:
                break
            parent, at, version = cut
            if (_publication(row) > int(version[1:])
                    or any(p > at['order'] for p in snap.own_positions(row, parent))):
                break
            lineage, snap = parent, self.at(version)
        return False

    def history(self, eligible: set[str], public: dict[str, dict], withholds: bool) -> dict:
        history = dict(replaced={}, ended=[], retracted=[])
        ranks = {'restated': 0, 'narrowed': 1, 'changed': 2, 'corrected': 3}
        terminals = {}

        def follow(identity: str) -> dict[str, str]:
            if identity not in terminals:
                row = self.snapshot.rows[identity]
                paths = {}
                if identity in eligible:
                    if identity in public:
                        paths[identity] = 'restated'
                elif row.get('superseded_by'):
                    for successor in row['superseded_by']:
                        for target, reason in follow(successor).items():
                            paths[target] = max(reason, _reason(row), paths.get(target, 'restated'), key=ranks.get)
                terminals[identity] = paths
            return terminals[identity]

        for identity, row in sorted(self.snapshot.rows.items()):
            slug = check.owner(row)
            if (identity in eligible or check.current(row) or self.applicable(row) is not True
                    or not self.historical_lineage(row)):
                continue
            if row['record'] == 'article':
                if not all((fact := self.snapshot.rows.get(fid)) is not None
                           and self.applicable(fact) is True and self.historical_lineage(fact)
                           for fid in check.cited_facts(row)):
                    continue
                if slug in public:
                    if _publication(row) < int(public[slug]['revision'].rsplit('@v', 1)[1]):
                        history['replaced'][identity] = dict(reason='restated', by=[slug])
                    continue
            if row.get('superseded_by'):
                if row['record'] == 'fact' and (paths := follow(identity)):
                    history['replaced'][identity] = dict(reason=max(paths.values(), key=ranks.get), by=sorted(paths))
            elif not withholds:
                if self.visible_end(row, self.lineage, self.snapshot):
                    history['ended'].append(slug)
                elif row['lifecycle_state'] == 'retracted':
                    history['retracted'].append(slug)
        history['ended'].sort()
        history['retracted'].sort()
        return history

    def knowledge(self) -> tuple[dict, int]:
        coverage = self.coverage(self.version)
        if coverage is None:
            if self.snapshot.rows:
                raise KnowledgeError(f'{self.version}: records without a coverage stamp')
            return empty(), 0
        records, excluded = self.eligible()
        version = self.version
        return dict(empty(), version=version, commit=tag_commit(self.repo.path, version),
                    repository_id=tag_commit(self.repo.path, 'v0'), coverage=coverage, **records), excluded


def _public_record(row: dict, relation: str | None, facts: dict, snapshot: _Snapshot) -> dict:
    scope = dict(row['scope'])
    if 'world' in scope:
        scope['world'] = None
    article = row['record'] == 'article'
    fields = ('title', 'lead', 'body') if article else (
        'statement_kind', 'state_key', 'anchor', 'depiction_source_id', 'text', 'subject', 'when')
    value = {key: row[key] for key in fields if key in row}
    value.update(id=check.owner(row), scope=scope, branch_relation=relation, tags=row['tags'], links=row['links'],
                 unverified_branch=relation == 'unknown')
    if article:
        cited = [facts[i] for i in check.cited_facts(row)]
        value.update(revision=row['id'], last_confirmed=snapshot.decorate_position(row['last_confirmed']),
                     unverified_branch=value['unverified_branch'] or any(f['unverified_branch'] for f in cited))
    else:
        value.update(citation_source_ids=row['citations'], seen=snapshot.decorate_position(row['seen']))
    return value


def _project(eligible: dict, draw_record: dict, *, withholds: bool, target: _TargetView | None = None) -> dict:
    if target is None and not withholds and not any(unit['withheld'] for unit in draw_record['units']):
        return copy.deepcopy(eligible)
    delivered = _subset(eligible, draw_record)
    records = delivered['articles'] + delivered['facts']
    public = {r['id']: r for r in records}
    eligible_rows = eligible['articles'] + eligible['facts']
    eligible_ids = {r['id'] for r in eligible_rows}
    eligible_keys = {f['state_key'] for f in eligible['facts'] if 'state_key' in f}
    all_keys = target.snapshot.all_state_keys if target is not None else eligible_keys
    delivered_by_key: dict[str, list[str]] = defaultdict(list)
    for f in delivered['facts']:
        if 'state_key' in f:
            delivered_by_key[f['state_key']].append(f['id'])

    # Classify conflicts over delivered public links (excluding state_key targets, which only exist on depends_on).
    record_links: set[tuple[str, str, str]] = set()
    kept_links: dict[str, list[dict]] = {}
    for row in records:
        filtered = []
        for link in row['links']:
            rel, dst = link['rel'], link['target']
            if dst == row['id']:
                continue
            if rel == 'depends_on' and dst in delivered_by_key:
                if dst != row.get('state_key'):
                    filtered.append(link)
            elif dst in public:
                filtered.append(link)
                record_links.add((row['id'], rel, dst))
        kept_links[row['id']] = filtered

    shadowed, contradicted = _classified(records, record_links)
    contested = {identity for identity, others in contradicted.items() if others}
    contested.update(a['id'] for a in delivered['articles'] if check.cited_facts(a) & contested)
    uncertain = contested | {r['id'] for r in records if r['unverified_branch']}

    # Measure staleness before withholding removes targets, applying two-strength depends_on rules.
    dependents, seeds = defaultdict(set), set()
    stale_by_id: dict[str, list[str]] = {}
    snap_rows = target.snapshot.rows if target is not None else None
    snap_incoming = target.snapshot.incoming if target is not None else None

    for row in records:
        identity = row['id']
        stale: set[str] = set(row.get('stale_citations', ()))
        uncertain_dep = False
        if 'body' in row:
            for fid in check.cited_facts(row):
                if fid in eligible_ids:
                    dependents[fid].add(identity)
                    if fid in uncertain:
                        uncertain_dep = True
                else:
                    stale.add(fid)
        for link in row['links']:
            if link['rel'] != 'depends_on':
                continue
            dst = link['target']
            if dst in all_keys:
                # Entity-existence pin: satisfied while any eligible active/contested reading carries `dst`.
                if dst not in eligible_keys:
                    stale.add(dst)
                continue
            if dst in eligible_ids:
                resolved = dst
            elif snap_rows is not None and dst in snap_rows:
                cand = check.restated_terminal(dst, snap_rows, snap_incoming)
                resolved = cand if cand in eligible_ids else None
            else:
                resolved = None
            if resolved is None:
                stale.add(dst)
            else:
                dependents[resolved].add(identity)
                if resolved in uncertain:
                    uncertain_dep = True
        stale_by_id[identity] = sorted(stale)
        if stale or uncertain_dep:
            seeds.add(identity)
    review = check._propagate(dependents, seeds)

    if target is not None:
        internal_ids = {r.get('revision', r['id']) for r in eligible_rows}
        history = target.history(internal_ids, public, withholds)
    else:
        history = delivered['history']
        for identity, entry in list(history['replaced'].items()):
            entry['by'] = [i for i in entry['by'] if i in public]
            if not entry['by']:
                del history['replaced'][identity]
        if withholds:
            history.update(ended=[], retracted=[])
    delivered['history'] = history
    named_history = set(history['replaced']) | set(history['ended']) | set(history['retracted'])

    # Emit backlinks: depends_on state_key targets attach backlinks to every delivered reading carrying that key.
    backlink_tuples: set[tuple[str, str, str]] = set()
    for row in records:
        row['links'] = kept_links[row['id']]
        for link in row['links']:
            rel, dst = link['rel'], link['target']
            if rel == 'depends_on' and dst in delivered_by_key:
                for fid in delivered_by_key[dst]:
                    backlink_tuples.add((row['id'], rel, fid))
            else:
                backlink_tuples.add((row['id'], rel, dst))
    backlinks: dict[str, list[dict]] = defaultdict(list)
    for source, rel, destination in sorted(backlink_tuples):
        backlinks[destination].append(dict(rel=rel, source=source))

    citing: dict[str, list[str]] = defaultdict(list)
    for article in delivered['articles']:
        for fact in check.cited_facts(article):
            citing[fact].append(article['id'])

    for row in records:
        identity = row['id']
        row.update(lifecycle_state='contested' if identity in contested else 'active',
                   needs_review=identity in review,
                   stale_citations=[i for i in stale_by_id[identity] if i in named_history],
                   backlinks=backlinks[identity], shadowed_by=sorted(shadowed[identity]),
                   contradicted_by=sorted(contradicted[identity]))
        if 'body' not in row:
            row['cited_by_articles'] = sorted(citing[identity])
    return delivered


def _alias_sessions(delivered: dict, snapshot: _Snapshot, assigned: dict[str, str] | None = None) -> dict[str, str]:
    positions = [a['last_confirmed'] for a in delivered['articles']] + [f['seen'] for f in delivered['facts']]
    coverage = delivered['coverage']
    names = {p['session'] for p in positions}
    if coverage is not None:
        names.add(coverage['session'])
    first = {}
    for position in snapshot.provenance['frames'].values():
        name = position['session']
        order = tuple(position['order'])
        if name in names and (name not in first or order < first[name]):
            first[name] = order
    aliases = {name: alias for alias, name in (assigned or {}).items()}
    remaining = sorted(names - aliases.keys(), key=lambda name: (name not in first, first.get(name), name))
    aliases.update({name: f's{index:02d}' for index, name in enumerate(remaining, len(aliases) + 1)})
    for position in positions:
        position['session'] = aliases[position['session']]
    if coverage is not None:
        coverage['session'] = aliases[coverage['session']]
    return {alias: name for name, alias in aliases.items()}


def _target(repository: Path | Repository, version: str, world: str | None,
            lineage: str | None, context: dict | None) -> _TargetView:
    world, lineage, context = target_labels(world, lineage, context)
    repo = repository if isinstance(repository, Repository) else Repository(repository.parent, repository.name)
    return _TargetView(repo, version, world, lineage, context)


def published(repository: Path | Repository, version: str, *, world: str | None = None,
              lineage: str | None = None, context: dict | None = None) -> dict:
    target = _target(repository, version, world, lineage, context)
    eligible, _ = target.knowledge()
    delivered = _project(eligible, _draw_record(eligible, None), withholds=False, target=target)
    _alias_sessions(delivered, target.snapshot)
    Knowledge.from_dict(delivered)
    return delivered


def export(package: Path, knowledge: dict | Path | Repository, seed: int | None = None, *,
           study: Path | None = None, start_index: int | None = None, version: str | None = None,
           world: str | None = None, lineage: str | None = None, context: dict | None = None,
           commit: str | None = None) -> dict:
    """Freeze a tagged repository view or an already public knowledge file (including the empty file)."""
    world, lineage, context = target_labels(world, lineage, context)
    target, excluded = None, 0
    if isinstance(knowledge, dict):
        Knowledge.from_dict(knowledge)
    else:
        if version is None:
            raise ValueError('exporting a repository requires a version')
        target = _target(knowledge, version, world, lineage, context)
        knowledge, excluded = target.knowledge()
        commit = knowledge['commit']

    if study is not None:
        if seed is not None or start_index is None:
            raise ValueError('study draw needs start index and excludes withhold seed')
        record = study_record(knowledge, study, start_index, commit=commit, world=world)
    else:
        if start_index is not None:
            raise ValueError('start index needs study draw')
        record = _draw_record(knowledge, seed)

    delivered = _project(knowledge, record, withholds=seed is not None or study is not None, target=target)
    full = knowledge
    aliases = {}
    if target is not None:
        aliases = _alias_sessions(delivered, target.snapshot)
        full = _project(knowledge, _draw_record(knowledge, None), withholds=False, target=target)
        # The private map resolves both files. Private-only sessions get aliases after the public ones.
        aliases = _alias_sessions(full, target.snapshot, aliases)
    Knowledge.from_dict(delivered)
    Knowledge.from_dict(full)

    package.mkdir(parents=True, exist_ok=True)
    (package / 'private').mkdir(exist_ok=True)

    def write(name: str, value: dict) -> str:
        data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
        with (package / name).open('xb') as stream:
            stream.write(data)
        return hashlib.sha256(data).hexdigest()

    delivered_sha256 = write('delivered-knowledge.json', delivered)
    selection = dict(world=world, lineage=lineage, context=context, session_aliases=aliases,
                     excluded_unknown_axis=excluded, delivered_sha256=delivered_sha256)
    return {'delivered-knowledge.json': delivered_sha256,
            'private/knowledge-full.json': write('private/knowledge-full.json', dict(full, selection=selection)),
            'private/units.json': write('private/units.json', record)}


def _context_arguments(values: list[str]) -> dict:
    context = {}
    for pair in values:
        key, separator, value = pair.partition('=')
        if not separator or key in context:
            raise ValueError('--context needs a distinct KEY=VALUE for each axis')
        context[key] = value
    return context


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=world_label)
    parser.add_argument('--lineage')
    parser.add_argument('--context', action='append', default=[], metavar='KEY=VALUE')

    def target(args) -> dict:
        try:
            world, lineage, context = target_labels(args.world, args.lineage, _context_arguments(args.context))
        except ValueError as exc:
            parser.error(str(exc))
        return dict(world=world, lineage=lineage, context=context)

    if argv and argv[0] == 'draw-study':
        parser.add_argument('repository', type=Path)
        parser.add_argument('--version', required=True)
        parser.add_argument('--starts', type=int, required=True)
        parser.add_argument('--blocks', nargs='+', required=True)
        parser.add_argument('--seed', type=int, required=True)
        parser.add_argument('--placebo', nargs='*', default=[])
        parser.add_argument('--out', type=Path, required=True)
        args = parser.parse_args(argv[1:])
        value = study_draw(published(args.repository, args.version, **target(args)), args.starts, args.blocks,
                           args.seed, args.placebo, commit=tag_commit(args.repository, args.version), world=args.world)
        with args.out.open('x') as stream:
            stream.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
        return
    parser.add_argument('repository', type=Path, nargs='?')
    parser.add_argument('--version')
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--withhold-seed', type=int)
    parser.add_argument('--empty', action='store_true')
    parser.add_argument('--study-draw', type=Path)
    parser.add_argument('--start-index', type=int)
    args = parser.parse_args(argv)
    if args.empty:
        if args.repository or args.version or args.withhold_seed is not None or args.study_draw or args.start_index is not None:
            parser.error('--empty takes no repository, version or draw')
        value = empty()
    else:
        if args.repository is None or args.version is None:
            parser.error('Select repository and --version, or --empty')
        value = args.repository
    print(json.dumps(export(args.package, value, args.withhold_seed, study=args.study_draw, start_index=args.start_index,
                            version=args.version, **target(args)), sort_keys=True))


if __name__ == '__main__':
    main()
