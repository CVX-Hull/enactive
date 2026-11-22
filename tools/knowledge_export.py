"""Freeze one published version and its independent per-unit withholding draw."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import re
import sys

import numpy as np

from harness.curator.knowledge import KnowledgeError, Repository
from harness.curator.gate import FACT, current
from harness.jsonio import strict_loads
from harness.player.knowledge import SCHEMA, empty

PRIVATE_FILES = {'knowledge-full.json', 'units.json'}
STUDY_DRAW_SCHEMA = 'withholding-study-draw/2'
WORLD_LABEL = re.compile(r'[ -~]{1,40}')
COMMIT_SHA = re.compile(r'[0-9a-f]{40}')


def world_label(world: str | None) -> str | None:
    if world is not None and (not isinstance(world, str) or WORLD_LABEL.fullmatch(world) is None):
        raise ValueError('world must be null or 1 to 40 printable ASCII characters')
    return world


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
                shared=[dict(fact_id=f, article_ids=sorted(owners)) for f, owners in sorted(cited.items()) if len(owners)>1])


def delivered_fact_ids(record: dict) -> set[str]:
    """Resolve the recorded draw, including shared facts, for export and the judges."""
    articles = {u['article_id'] for u in record['units'] if not u['withheld'] and u['article_id'] is not None}
    return ({f for u in record['units'] if not u['withheld'] for f in u['fact_ids']}
            | {row['fact_id'] for row in record['shared'] if articles.intersection(row['article_ids'])})


def draw(knowledge: dict, seed: int | None) -> tuple[dict, dict]:
    rng = random.Random(seed)
    layout = units(knowledge)
    drawn = [dict(u, withheld=seed is not None and rng.random() < .5) for u in layout['units']]
    record = dict(schema='knowledge-units/1', version=knowledge['version'], seed=seed, units=drawn, shared=layout['shared'])
    return filter_delivery(knowledge, record), record


def filter_delivery(knowledge: dict, record: dict) -> dict:
    article_ids = {u['article_id'] for u in record['units'] if not u['withheld'] and u['article_id'] is not None}
    fact_ids = delivered_fact_ids(record)
    delivered = copy.deepcopy(knowledge)
    delivered['articles'] = [a for a in delivered['articles'] if a['id'] in article_ids]
    titles = {a['title'] for a in delivered['articles']}
    for article in delivered['articles']:
        article['links'] = [title for title in article['links'] if title in titles]
    delivered['facts'] = [f for f in delivered['facts'] if f['id'] in fact_ids]
    return delivered


def blocked_assignment(rng: np.random.Generator, sizes: list[int], count: int,
                       half_sizes: np.ndarray | None = None, draws: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Independent permutations per unit/block; odd blocks first toss a fair half-size coin.

    Returns (draw, unit, start) booleans and (draw, unit, block) half sizes. Tests condition
    on the sizes recorded by the study draw, while prospective simulations draw new sizes.
    """
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
    from harness.curator.knowledge import _git
    repo = Repository(path.parent, path.name)
    return _git(repo.path, 'rev-parse', f'{version}^{{commit}}').decode().strip()


def published(path: Path, version: str, *, world: str | None = None) -> dict:
    world_label(world)
    repo = Repository(path.parent, path.name)
    articles, facts = [], []
    for record in repo.records(version):
        if not isinstance(record, dict) or record.get('schema') != FACT:
            raise KnowledgeError(f'Unsupported record schema; expected {FACT}')
        if record.get('record') == 'article':
            if 'scope' in record:
                raise KnowledgeError('Invalid article scope')
            if current(record):
                articles.append({k: record[k] for k in ('id', 'title', 'lead', 'body', 'links', 'last_confirmed')})
            continue
        if record.get('record') != 'fact':
            raise KnowledgeError('Unsupported record kind; expected fact or article')
        scope = record.get('scope')
        if not isinstance(scope, dict) or scope.get('game') != repo.game:
            raise KnowledgeError('Invalid fact scope')
        level = scope.get('level')
        if level == 'game' and scope.keys() == {'game', 'level'}:
            selected = True
        elif (level == 'world' and scope.keys() == {'game', 'level', 'world'}
              and isinstance(scope['world'], str) and WORLD_LABEL.fullmatch(scope['world']) is not None):
            selected = scope['world'] == world
        else:
            raise KnowledgeError('Invalid fact scope')
        if selected and current(record):
            facts.append({k: record[k] for k in ('id', 'type', 'text', 'subject', 'seen') if k in record})
    # coverage.json is absent at v0. Enumerate the tree rather than swallowing a corrupt stamp.
    from harness.curator.knowledge import _git
    names = _git(repo.path, 'ls-tree', '-r', '--name-only', version).decode().splitlines()
    coverage = json.loads(repo._show(version, 'coverage.json')) if 'coverage.json' in names else None
    if coverage is not None and coverage.get('schema') != 'curator-coverage/2':
        raise KnowledgeError('Unsupported coverage stamp')
    # The identity a later version is checked against: this tag's commit, and the repository's first
    # version, which every later version of the same repository descends from. The world label that
    # selected the facts is never written here; it stays in the private full file.
    commit, repository_id = (_git(repo.path, 'rev-parse', f'{tag}^{{commit}}').decode().strip() for tag in (version, 'v0'))
    return dict(schema=SCHEMA, version=version, commit=commit, repository_id=repository_id, coverage=coverage,
                articles=articles, facts=facts)


def export(package: Path, knowledge: dict, seed: int | None = None, *,
           study: Path | None = None, start_index: int | None = None,
           world: str | None = None, commit: str | None = None) -> dict:
    world_label(world)
    if 'selection' in knowledge:
        raise ValueError('export expects knowledge without a private selection')
    if study is not None:
        if seed is not None or start_index is None:
            raise ValueError('study draw needs start index and excludes withhold seed')
        record = study_record(knowledge, study, start_index, commit=commit, world=world)
        delivered = filter_delivery(knowledge, record)
    else:
        if start_index is not None:
            raise ValueError('start index needs study draw')
        delivered, record = draw(knowledge, seed)
    package.mkdir(parents=True, exist_ok=True)
    (package/'private').mkdir(exist_ok=True)
    def write(name: str, value: dict) -> str:
        data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
        with (package/name).open('xb') as stream:
            stream.write(data)
        return hashlib.sha256(data).hexdigest()

    delivered_sha256 = write('delivered-knowledge.json', delivered)
    full = dict(knowledge, selection=dict(world=world, delivered_sha256=delivered_sha256))
    return {'delivered-knowledge.json': delivered_sha256,
            'private/knowledge-full.json': write('private/knowledge-full.json', full),
            'private/units.json': write('private/units.json', record)}


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=world_label)
    if argv and argv[0] == 'draw-study':
        parser.add_argument('repository', type=Path)
        parser.add_argument('--version', required=True)
        parser.add_argument('--starts', type=int, required=True)
        parser.add_argument('--blocks', nargs='+', required=True)
        parser.add_argument('--seed', type=int, required=True)
        parser.add_argument('--placebo', nargs='*', default=[])
        parser.add_argument('--out', type=Path, required=True)
        args = parser.parse_args(argv[1:])
        value = study_draw(published(args.repository, args.version, world=args.world), args.starts, args.blocks,
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
    commit = None
    if args.empty:
        if args.repository or args.version or args.withhold_seed is not None or args.study_draw or args.start_index is not None:
            parser.error('--empty takes no repository, version or draw')
        value = empty()
    else:
        if args.repository is None or args.version is None:
            parser.error('Select repository and --version, or --empty')
        value = published(args.repository, args.version, world=args.world)
        if args.study_draw is not None:
            commit = tag_commit(args.repository, args.version)
    print(json.dumps(export(args.package, value, args.withhold_seed, study=args.study_draw, start_index=args.start_index,
                            world=args.world, commit=commit), sort_keys=True))


if __name__ == '__main__':
    main()
