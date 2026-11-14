"""Freeze one published version and its independent per-unit withholding draw."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random

from harness.curator.knowledge import KnowledgeError, Repository
from harness.curator.gate import current
from harness.player.knowledge import empty

PRIVATE_FILES = {'knowledge-full.json', 'units.json'}


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
    article_ids = {u['article_id'] for u in drawn if not u['withheld'] and u['article_id'] is not None}
    fact_ids = delivered_fact_ids(record)
    delivered = copy.deepcopy(knowledge)
    delivered['articles'] = [a for a in delivered['articles'] if a['id'] in article_ids]
    titles = {a['title'] for a in delivered['articles']}
    for article in delivered['articles']:
        article['links'] = [title for title in article['links'] if title in titles]
    delivered['facts'] = [f for f in delivered['facts'] if f['id'] in fact_ids]
    return delivered, record


def published(path: Path, version: str) -> dict:
    repo = Repository(path.parent, path.name)
    records = [r for r in repo.records(version) if current(r)]
    # coverage.json is absent at v0. Enumerate the tree rather than swallowing a corrupt stamp.
    from harness.curator.knowledge import _git
    names = _git(repo.path, 'ls-tree', '-r', '--name-only', version).decode().splitlines()
    coverage = json.loads(repo._show(version, 'coverage.json')) if 'coverage.json' in names else None
    if coverage is not None and coverage.get('schema') != 'curator-coverage/2':
        raise KnowledgeError('Unsupported coverage stamp')
    return dict(schema='delivered-knowledge/1', version=version, coverage=coverage,
                articles=[{k: r[k] for k in ('id', 'title', 'lead', 'body', 'links', 'last_confirmed')} for r in records
                          if r['record'] == 'article'],
                facts=[{k: r[k] for k in ('id', 'type', 'text', 'subject', 'seen') if k in r} for r in records
                       if r['record'] == 'fact'])


def export(package: Path, knowledge: dict, seed: int | None = None) -> dict:
    delivered, record = draw(knowledge, seed)
    package.mkdir(parents=True, exist_ok=True)
    (package/'private').mkdir(exist_ok=True)
    hashes = {}
    for name, value in (('delivered-knowledge.json', delivered), ('private/knowledge-full.json', knowledge),
                        ('private/units.json', record)):
        data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
        with (package/name).open('xb') as stream:
            stream.write(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path, nargs='?')
    parser.add_argument('--version')
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--withhold-seed', type=int)
    parser.add_argument('--empty', action='store_true')
    args = parser.parse_args(argv)
    if args.empty:
        if args.repository or args.version or args.withhold_seed is not None:
            parser.error('--empty takes no repository, version or draw')
        value = empty()
    else:
        if args.repository is None or args.version is None:
            parser.error('Select repository and --version, or --empty')
        value = published(args.repository, args.version)
    print(json.dumps(export(args.package, value, args.withhold_seed), sort_keys=True))


if __name__ == '__main__':
    main()
