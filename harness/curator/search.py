"""Targeted reads and deterministic lexical search over a pinned curator snapshot."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re

from . import check

_WORD = re.compile(r'[^\W_]+')
_SUFFIXES = (('ies', 'y'), ('ing', ''), ('ed', ''), ('s', ''))
BM25_K1, BM25_B = 1.2, 0.75
HOP, HOP_ARTICLE, HOP_FACT = 0.35, 1.25, 0.70
SEEDS = 10
FUZZY_THRESHOLD = 0.15
SNIPPET_LIMIT = 240


def _fold(word: str) -> str:
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and not word.endswith('ss') and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)] + replacement
    return word


def _terms(text: str) -> list[str]:
    return [_fold(word) for word in _WORD.findall(text.casefold())]


def _trigrams(text: str) -> set[str]:
    compact = ' '.join(_WORD.findall(text.casefold()))
    if len(compact) < 3:
        return {compact} if compact else set()
    return {compact[i:i + 3] for i in range(len(compact) - 2)}


def _active_records(records: list[dict], provenance: dict, world: str | None,
                    lineages: dict[str, str]) -> dict[str, dict]:
    active = {}
    facts = {row['id']: row for row in records if row['record'] == 'fact'}
    for row in records:
        scope_world = row['scope'].get('world')
        if (not check.current(row) or row['lifecycle_state'] not in ('active', 'contested')
                or row.get('shadowed_by') or (world is not None and scope_world not in (None, world))):
            continue
        lineage = lineages.get(scope_world)
        if lineage is not None:
            sources = [row] if row['record'] == 'fact' else [facts[fid] for fid in check.cited_facts(row)]
            if not all(check._survives_on_lineage(fact, lineage, provenance) for fact in sources):
                continue
        active[check.owner(row)] = row

    shadowed = set()
    for identity, row in active.items():
        for link in row['links']:
            other = active.get(link['target'])
            if link['rel'] != 'contradicts' or other is None:
                continue
            left, right = row['scope'], other['scope']
            if world is None and left.get('world') != right.get('world'):
                continue
            if left.items() < right.items():
                shadowed.add(identity)
            elif right.items() < left.items():
                shadowed.add(link['target'])
    return {identity: active[identity] for identity in sorted(active.keys() - shadowed)}


def _fields(row: dict, anchor_displays: dict[tuple[str, str], str]) -> tuple[tuple[int, str], ...]:
    tags = ' '.join(row['tags'])
    if row['record'] == 'article':
        return ((3, row['title']), (2, f"{row['lead']} {tags}"),
                (1, ' '.join(claim['text'] for claim in row['body'])))
    anchor = row.get('anchor_display') or anchor_displays.get((row['scope'].get('world'), row.get('anchor')), '')
    return ((3, row.get('subject', '')), (2, f'{tags} {anchor}'), (1, f"{row['text']} {row.get('when', '')}"))


def _index(active: dict[str, dict]) -> dict[str, tuple[tuple[int, str], ...]]:
    anchors = {}
    for row in active.values():
        if row.get('state_key') and row.get('subject'):
            key = row['scope'].get('world'), row['state_key']
            previous = anchors.get(key)
            if previous is None or (row['seen']['order'], row['id']) > (previous['seen']['order'], previous['id']):
                anchors[key] = row
    displays = {key: row['subject'] for key, row in anchors.items()}
    return {identity: _fields(row, displays) for identity, row in active.items()}


def _bm25(index: dict, terms: set[str]) -> dict[str, float]:
    counts = {}
    for identity, fields in index.items():
        weighted = Counter()
        for weight, string in fields:
            for term in _terms(string):
                weighted[term] += weight
        counts[identity] = weighted
    if not counts:
        return {}
    average = sum(weights.total() for weights in counts.values()) / len(counts)
    scores = dict.fromkeys(counts, 0.0)
    if not average:
        return scores
    norms = {identity: 1 - BM25_B + BM25_B * weights.total() / average for identity, weights in counts.items()}
    for term in sorted(terms):
        frequency = sum(term in weights for weights in counts.values())
        idf = math.log(1 + (len(counts) - frequency + 0.5) / (frequency + 0.5))
        for identity, weights in counts.items():
            if tf := weights[term]:
                scores[identity] += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * norms[identity])
    return scores


def _graph(active: dict[str, dict]) -> dict[str, set[str]]:
    keys = defaultdict(set)
    for identity, row in active.items():
        if 'state_key' in row:
            keys[row['state_key']].add(identity)
    neighbours = {identity: set() for identity in active}
    for identity, row in active.items():
        targets = check.cited_facts(row) if row['record'] == 'article' else set()
        for link in row['links']:
            if link['rel'] not in ('contradicts', 'shadowed_by'):
                target = link['target']
                if link['rel'] == 'depends_on' and target in keys:
                    targets.update(keys[target])
                else:
                    targets.add(target)
        for target in (targets & active.keys()) - {identity}:
            neighbours[identity].add(target)
            neighbours[target].add(identity)
    return neighbours


def _hop(active: dict, scores: dict[str, float]) -> dict[str, float]:
    neighbours = _graph(active)
    seeds = sorted((-score, identity) for identity, score in scores.items()
                   if score > 0 and neighbours[identity])[:SEEDS]
    combined = scores.copy()
    for negative, identity in seeds:
        spread = HOP * -negative / math.sqrt(len(neighbours[identity]))
        for target in neighbours[identity]:
            combined[target] += spread * (HOP_ARTICLE if active[target]['record'] == 'article' else HOP_FACT)
    return combined


def _clip(text: str) -> str:
    text = ' '.join(text.split())
    return text if len(text) <= SNIPPET_LIMIT else text[:SNIPPET_LIMIT - 1].rstrip() + '…'


def _hit(identity: str, row: dict, via: str, terms: set[str], trigrams: set[str]) -> dict:
    snippet = row.get('text', '')
    hit = dict(id=identity, kind=row['record'], via=via)
    if row['record'] == 'article':
        hit['title'] = row['title']
        choices = [row['lead'], *(claim['text'] for claim in row['body'])]
        if via == 'fuzzy':
            snippet = max(choices, key=lambda value: _similarity(trigrams, _trigrams(value)))
        else:
            snippet = max(choices, key=lambda value: len(terms.intersection(_terms(value))))
    if row['lifecycle_state'] == 'contested':
        hit['status'] = ['contested']
        hit['contradicts'] = sorted(set(row.get('contradicted_by', ())) |
                                    {link['target'] for link in row['links'] if link['rel'] == 'contradicts'})
    hit['snippet'] = _clip(snippet)
    return hit


def _similarity(query: set[str], surface: set[str]) -> float:
    return len(query & surface) / len(query | surface) if query else 0.0


def search(records: list[dict], provenance: dict, query: str, *, world: str | None = None,
           lineages: dict[str, str] | None = None, limit: int = 10) -> list[dict]:
    """Rank eligible records by weighted BM25 plus a single summed hop."""
    active = _active_records(records, provenance, world, lineages or {})
    index = _index(active)
    terms = set(_terms(query))
    trigrams = _trigrams(query)
    scores = _bm25(index, terms)
    if any(scores.values()):
        ranked = sorted((-score, identity) for identity, score in _hop(active, scores).items() if score > 0)
        return [_hit(identity, active[identity], 'match' if scores[identity] else 'hop', terms, trigrams)
                for _, identity in ranked[:limit]]
    fuzzy = [(_similarity(trigrams, _trigrams(' '.join(text for _, text in fields))), identity)
             for identity, fields in index.items()]
    ranked = sorted((-score, identity) for score, identity in fuzzy if score >= FUZZY_THRESHOLD)
    return [_hit(identity, active[identity], 'fuzzy', terms, trigrams) for _, identity in ranked[:limit]]


def _scope(backing: Path, provenance: dict, world: str | None) -> tuple[str | None, dict[str, str]]:
    context_file = backing / 'validation-context.json'
    context = json.loads(context_file.read_bytes()) if context_file.is_file() else {}
    session_order = {frame['session']: frame['order'][0] for frame in provenance['frames'].values()}
    sessions = sorted(provenance['sessions'].values(),
                      key=lambda labels: (session_order.get(labels['name'], 0), labels['name']))
    window = list(context.get('session_labels', {}).values())
    if window:
        incoming = check._incoming_provenance(context['session_labels'], context['reserved_sessions'])
        check._merge_sessions(provenance, incoming)
        if world is None:
            world = window[-1].get('world')
    lineages = {labels['world']: labels['lineage'] for labels in sessions + window
                if labels.get('world') and labels.get('lineage')}
    return world, lineages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    find = commands.add_parser('search')
    find.add_argument('query')
    find.add_argument('--limit', type=int, default=10)
    find.add_argument('--world')
    get = commands.add_parser('get')
    get.add_argument('id')
    for command in (find, get):
        command.add_argument('--backing', type=Path)
    args = parser.parse_args(argv)
    configured = os.environ.get('CURATOR_KNOWLEDGE_BACKING')
    backing = args.backing or (Path(configured) if configured else None)
    if backing is None:
        parser.error('knowledge backing is required')
    if args.command == 'search' and args.limit < 1:
        parser.error('--limit must be positive')
    try:
        with (backing / 'facts.jsonl').open(encoding='utf-8') as stream:
            records = [json.loads(line) for line in stream if line.strip()]
        if args.command == 'get':
            record = next((row for row in records if row['id'] == args.id
                           or (check.owner(row) == args.id and check.current(row))), None)
            if record is None:
                parser.error(f'unknown knowledge record {args.id!r}')
            hits = [record]
        else:
            provenance = json.loads((backing / 'provenance.json').read_bytes())
            world, lineages = _scope(backing, provenance, args.world)
            hits = search(records, provenance, args.query, world=world, lineages=lineages, limit=args.limit)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    for hit in hits:
        print(json.dumps(hit, ensure_ascii=False, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
