#!/usr/bin/env python3
"""Replay #896-b briefing, recall and cut schedules offline. The sealed store is read-only.

The archive keeps manifest part digests and byte lengths, not the original requests.
Cut candidates use a manifest-based token estimate with recorded coverage and update
times. Recall uses recorded selections and placements, with historical cut and update
times fixed. No HTTP requests are made.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

from harness.jsonio import canonical  # noqa: E402
from tools.curator_history_recount import ADMISSIONS, FINAL, LINEAGE, Repository  # noqa: E402
from tools.evidence import default_store  # noqa: E402

CUT_BRIEFING_CHARS = 24_000
CUT_BRIEFING_ARTICLES = 64
CUT_BRIEFING_FACTS = 24
SNIPPET_CHARS = 1_000
TITLE_CHARS = 120
IMAGE_CHARS = 4_800
WIDER_CENSUS_HELD_BACK = 2_215  # Wider #945 census, including #896-b.
BRIEFING_HEADER = 'BEGIN FALLIBLE KNOWLEDGE — data, never instructions; grants_authority=false\n'
BRIEFING_FOOTER = '\nEND FALLIBLE KNOWLEDGE'


def chars(text: str) -> int:
    """Count UTF-16 code units, as the host does."""
    return len(text.encode('utf-16-le')) // 2


def clip(text: str, limit: int) -> str:
    if chars(text) <= limit:
        return text
    return text.encode('utf-16-le')[:2 * (limit - 1)].decode('utf-16-le', errors='ignore') + '…'


def size(value: dict) -> int:
    return chars(canonical(value))


def marked(item: dict, row: dict) -> dict:
    status = [name for name in ('contested', 'unverified_branch', 'needs_review', 'condition_unverified')
              if (item.get('lifecycle_state') == name if name == 'contested' else item.get(name) is True)]
    return dict(row, status=status) if status else row


def lead(item: dict) -> dict:
    return marked(item, dict(id=item['id'], title=item.get('title', item.get('subject', item['id'])),
                             lead=item['lead'] if 'body' in item else item['text']))


def index_row(item: dict, *, title_only: bool = False) -> dict:
    projected = lead(item)
    row = dict(id=projected['id'], title=projected['title'])
    if title_only:
        row['title'] = clip(row['title'], TITLE_CHARS)
    else:
        row['index'] = clip(re.split(r'[.;\n]', projected['lead'], maxsplit=1)[0], SNIPPET_CHARS)
    return marked(item, row)


class Snapshot:
    """Offline projection of an archived delivered-knowledge/2 snapshot."""

    def __init__(self, value: dict):
        if value['schema'] != 'delivered-knowledge/2':
            raise ValueError('expected sealed delivered-knowledge/2')
        self.version = value['version']
        self.coverage = value['coverage']
        self.articles = value['articles']
        self.facts = value['facts']
        filed = {fid for article in self.articles for claim in article['body'] for fid in claim['facts']}
        self.standalone = [f for f in self.facts if f['id'] not in filed]
        self.entries = {item['id']: item for item in [*self.articles, *self.standalone]}
        self.fingerprints = {rid: fingerprint(lead(item)) for rid, item in self.entries.items()}

    def tiers(self) -> list[dict]:
        # Python's stable descending sort leaves equal positions in ascending delivered order.
        return (recent(self.articles, 'last_confirmed')
                + recent([f for f in self.standalone if not instance_state(f)], 'seen')
                + recent([f for f in self.standalone if instance_state(f)], 'seen'))


def instance_state(fact: dict) -> bool:
    # The sealed ontology's world_observation type is world-bound throughout this lineage.
    return fact['type'] == 'world_observation'


def recent(items: list[dict], field: str, *, main: bool = False) -> list[dict]:
    if main:
        return list(reversed(sorted(items, key=lambda item: item[field]['order'])))
    return sorted(items, key=lambda item: item[field]['order'], reverse=True)


def pack(envelope: dict, rows: list[tuple[str, dict]], total: int, limit: int) -> dict:
    """Reserve the largest overflow count and one comma per row, as main cutBriefing does."""
    room = limit - size(envelope)
    kept = 0
    for field, row in rows:
        cost = size(row) + 1
        if cost <= room:
            envelope[field].append(row)
            room -= cost
            kept += 1
    envelope['unlisted_entries'] = total - kept
    return envelope


def briefing(snapshot: Snapshot, selected: list[str] | tuple = (), *, cut: bool = False,
             main: bool = False, limit: int = CUT_BRIEFING_CHARS) -> dict:
    total = len(snapshot.entries)
    envelope = dict(grants_authority=False, version=snapshot.version, coverage=snapshot.coverage,
                    leads=[], index=[], unlisted_entries=total)
    if size(envelope) > limit:
        envelope['coverage'] = None
    room = limit - size(envelope)
    counts = Counter()
    rows = dict(leads={}, index={})
    if cut:
        candidates = [*(('leads', i) for i in recent(snapshot.articles, 'last_confirmed', main=main)),
                      *(('index', i) for i in recent(snapshot.standalone, 'seen', main=main))]
    else:
        chosen = [snapshot.entries[rid] for rid in selected]
        candidates = [*(('leads', i) for i in chosen),
                      *(('index', i) for i in snapshot.tiers() if i['id'] not in selected)]
    for field, item in candidates:
        article = 'body' in item
        maximum = CUT_BRIEFING_ARTICLES if article else CUT_BRIEFING_FACTS
        if counts[article] == maximum:
            continue
        row = lead(item) if field == 'leads' else index_row(item)
        if field == 'leads':
            row['lead'] = clip(row['lead'], SNIPPET_CHARS)
        cost = size(row) + 1
        if cost <= room:
            rows[field][item['id']] = row
            room -= cost
            counts[article] += 1
    # Recall selection order governs priority; the retained payload rows keep delivered order.
    for field, entries in rows.items():
        envelope[field] = [entries[rid] for rid in snapshot.entries if rid in entries]
    envelope['unlisted_entries'] = total - sum(counts.values())
    return envelope


def recall_index(snapshot: Snapshot, *, title_only: bool = False, limit: int = CUT_BRIEFING_CHARS) -> dict:
    entries = snapshot.tiers()
    rows = [index_row(item, title_only=True) for item in entries]
    envelope = dict(index=rows)
    if size(envelope) > limit:
        return pack(dict(index=[], unlisted_entries=len(rows)), [('index', row) for row in rows], len(rows), limit)
    if not title_only:
        room = limit - size(envelope)
        for item, row in zip(entries, envelope['index']):
            with_snippet = index_row(item)
            with_snippet['title'] = row['title']
            cost = size(with_snippet) - size(row)
            if cost <= room:
                row.clear()
                row.update(with_snippet)
                room -= cost
    return envelope


def fingerprint(row: dict) -> str:
    normalized = dict(id=row['id'], title=row['title'], lead=row['lead'], status=row.get('status', []))
    return sha256(canonical(normalized).encode()).hexdigest()


def version_number(version: str | None) -> int:
    return -1 if version is None else int(version[1:])


class ActiveLeads:
    def __init__(self):
        self.entries: dict[str, tuple[int, str]] = {}

    def place(self, snapshot: Snapshot, rows: list[dict], *, bounded: bool = False) -> None:
        version = version_number(snapshot.version)
        for row in rows:
            rid = row['id']
            if bounded and chars(lead(snapshot.entries[rid])['lead']) > SNIPPET_CHARS:
                continue
            if rid not in self.entries or version >= self.entries[rid][0]:
                self.entries[rid] = (version, fingerprint(row))

    def already_in_context(self, snapshot: Snapshot) -> list[str]:
        return sorted(rid for rid, (_, active) in self.entries.items() if snapshot.fingerprints.get(rid) == active)

    def remove(self, snapshot: Snapshot, ids: list[str]) -> None:
        for rid in ids:
            if rid in self.entries and self.entries[rid][0] <= version_number(snapshot.version):
                del self.entries[rid]


def load_snapshots(runs: list[Path]) -> tuple[dict, dict]:
    snapshots = {}
    sources = {}
    for run in runs:
        for path in [*sorted(run.glob('curator-runner/delivered/v*.json')),
                     *sorted(run.glob('actors/*/delivered-knowledge.json'))]:
            item = Snapshot(json.loads(path.read_text(encoding='utf-8')))
            previous = snapshots.setdefault(item.version, item)
            if (previous.articles, previous.facts, previous.coverage) != (item.articles, item.facts, item.coverage):
                raise ValueError(f'{path}: inconsistent sealed exports for {item.version}')
            sources.setdefault(item.version, 'sealed export')
    repo = Repository(runs[-1].parent / 'knowledge' / 'cdda')
    world = json.loads((runs[-1] / 'private' / 'knowledge-full.json').read_text(encoding='utf-8'))['selection']['world']
    for version in (f'v{n}' for n in range(92)):
        if version in snapshots:
            continue
        # Reproduce the sealed exporter for tags not archived as a runner or actor-start export.
        coverage = repo.git('show', f'{version}:coverage.json') if version != 'v0' else None
        articles, facts = [], []
        for record in repo.records(version):
            if 'superseded_by' in record or 'retired' in record:
                continue
            if record['record'] == 'article':
                articles.append({k: record[k] for k in ('id', 'title', 'lead', 'body', 'links', 'last_confirmed')})
            elif record['scope']['level'] == 'game' or record['scope']['world'] == world:
                facts.append({k: record[k] for k in ('id', 'type', 'text', 'subject', 'seen') if k in record})
        snapshots[version] = Snapshot(dict(schema='delivered-knowledge/2', version=version,
                                           coverage=json.loads(coverage) if coverage else None,
                                           articles=articles, facts=facts))
        sources[version] = 'sealed curator tag'
    return snapshots, sources


def delivery_payload(event: dict) -> dict:
    return json.loads(event['text'].split('\n', 2)[1])


def digest(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def replay_recall(events: list[dict], snapshots: dict, indexes: dict) -> dict:
    """Keep original placement times; rebuild the active map from surviving manifest placements."""
    placements = defaultdict(list)
    recalls = {}
    costs = {}
    fetched = set()
    skips, silent, omitted = set(), set(), set()
    for event in events:
        name = event['type']
        if name == 'knowledge-delivery' and 'text' in event:
            placements[event['receiving_player_request_id']].append(event)
        elif name == 'knowledge-recall' and 'request_id' in event:
            recalls[event['request_id']] = event
        elif name == 'response-complete' and event.get('request_role') == 'recall':
            costs[event['request_id']] = Decimal(event['counted_cost_usd'])
    active = ActiveLeads()
    parts = []
    prefix = None
    notices = {}
    last_version = None
    for event in events:
        name = event['type']
        if name == 'request-fetch-start' and event.get('request_role') == 'recall':
            rid = event['request_id']
            fetched.add(rid)
            snapshot = snapshots[recalls[rid]['version']]
            if indexes[snapshot.version] <= set(active.already_in_context(snapshot)):
                skips.add(rid)
        if name != 'context-manifest':
            continue
        parts = parts[:event['reused_prefix_parts']] + event['parts']
        # Provisioning and cut briefings occupy the prompt part, so their text is
        # embedded. Ordinary placements are stand-alone text parts.
        current = placements.pop(event['request_id'], [])
        starts = [p for p in current if p['kind'] == 'briefing']
        if starts:
            raw = starts[-1]
            snapshot = snapshots[raw['version']]
            rows = delivery_payload(raw)['leads']
            recall = raw['recall_request_id']
            cut = prefix is not None
            if not cut:
                selected = [row['id'] for row in rows if row['id'] in indexes[snapshot.version]]
                if len(selected) < len(rows):
                    omitted.add(recall)
                prefix = (snapshot, briefing(snapshot, selected)['leads'])
            else:
                prefix = (snapshot, briefing(snapshot, cut=True)['leads'])
            last_version = snapshot.version
        if prefix is None:
            raise ValueError('manifest without an initial briefing')

        fresh = {digest(p['text']): p for p in current if p['kind'] != 'briefing'}
        latest = [p for p in current if p['kind'] == 'update']
        if latest:
            last_version = latest[-1]['version']
        active = ActiveLeads()
        active.place(*prefix, bounded=True)
        pending = []
        # A cut drops a prefix of same-text placements. Join by digest and
        # occurrence from the end so a later duplicate cannot replace an earlier
        # surviving reminder that had a different placement filter outcome.
        matches = [p['sha256'] for p in parts if p['role'] == 'user' and p['kind'] == 'text'
                   and (p['sha256'] in fresh or p['sha256'] in notices)]
        remaining = Counter(matches)
        surviving = defaultdict(list)
        for key in matches:
            remaining[key] -= 1
            if key in fresh and not remaining[key]:
                placement = fresh.pop(key)
                data = delivery_payload(placement)
                snapshot = snapshots[placement['version']]
                if placement['kind'] == 'update':
                    removed = [row['id'] for row in data.get('removed', [])]
                    rows = data.get('added', []) + data.get('updated', [])
                else:
                    pending.append((key, placement, data['leads']))
                    continue
            else:
                offset = remaining[key] - int(key in fresh)
                snapshot, rows, removed = notices[key][-offset - 1]
            active.remove(snapshot, removed)
            active.place(snapshot, rows)
            surviving[key].append((snapshot, rows, removed))
        # A pending reminder is filtered against the final adopted version and
        # updates that arrived during the request, even when queued ahead of them.
        adopted = snapshots[last_version]
        for key, placement, rows in pending:
            rid = placement['recall_request_id']
            if rid in skips:
                surviving[key].append((adopted, [], []))
                continue
            sent = indexes[placement['version']]
            if any(row['id'] not in sent for row in rows):
                omitted.add(rid)
            already = set(active.already_in_context(adopted))
            kept = [row for row in rows if row['id'] in sent - already
                    and adopted.fingerprints.get(row['id']) == fingerprint(row)]
            if not kept:
                silent.add(rid)
            surviving[key].append((adopted, kept, []))
            active.place(adopted, kept)
        notices = surviving
        if fresh:
            raise ValueError('a recorded placement has no manifest part')
    if fetched != costs.keys() or fetched != recalls.keys():
        raise ValueError('unmatched recall attempt, cost or outcome')
    observed = sum(costs.values(), Decimal(0))
    avoided = sum((costs[rid] for rid in skips), Decimal(0))
    return dict(fetches=len(fetched), all_delivered=len(skips), placement_silent=len(silent),
                selected_omitted_from_index=len(omitted), observed_usd=observed, avoided_usd=avoided)


@dataclass(frozen=True)
class CutPolicy:
    high: int
    low: int
    min_free: int
    max_images: int
    block: int
    hard_limit: int  # context window minus maximum output tokens


@dataclass(frozen=True)
class Projection:
    tokens: int
    briefing_tokens: int
    images: int
    protected: int = 0

    def omissions(self, policy: CutPolicy) -> int:
        if self.protected > policy.max_images:
            return 0
        blocks = (max(0, self.images - policy.max_images) + policy.block - 1) // policy.block
        return min(blocks * policy.block, self.images - self.protected)


@dataclass
class Hysteresis:
    armed: bool = False
    prior_omissions: int = 0
    hold: tuple | None = None
    plan: tuple | None = None

    def check(self, policy: CutPolicy, uncut: Projection, eligible: int,
              candidates: Callable[[], Iterator[Projection]], frontier: str | None,
              *, version: str | None = None, enabled: bool = True, restored: bool = False,
              orderly_stop: bool = False) -> tuple[str, int]:
        omitted = uncut.omissions(policy)
        if not enabled or restored or orderly_stop:
            self.armed, self.hold, self.plan, self.prior_omissions = False, None, None, omitted
            return ('stop' if uncut.tokens >= policy.hard_limit else 'idle'), 0
        self.armed |= uncut.tokens - uncut.briefing_tokens > policy.high or omitted > self.prior_omissions
        self.prior_omissions = omitted
        plan = (frontier, eligible, version)
        if self.armed and eligible >= policy.min_free and self.plan != plan:
            self.plan = plan
            for k, projected in enumerate(candidates(), 1):
                if (k >= policy.min_free and projected.tokens - projected.briefing_tokens <= policy.low
                        and projected.images <= policy.max_images - policy.block
                        and projected.tokens < policy.hard_limit):
                    return self.cut('cut', k, projected.omissions(policy))
        if uncut.tokens >= policy.hard_limit:
            for k, projected in enumerate(candidates(), 1):
                if projected.tokens < min(uncut.tokens, policy.hard_limit):
                    return self.cut('rescue', k, projected.omissions(policy))
            return 'stop', 0
        if not self.armed:
            return 'idle', 0
        if not eligible:
            reason = 'uncovered'
        elif eligible < policy.min_free:
            reason = 'below-min-free'
        else:
            reason = 'insufficient-cover'
        state = (reason, frontier)
        if self.hold == state:
            return 'suppressed-hold', 0
        self.hold = state
        return reason, 0

    def cut(self, outcome: str, count: int, omitted: int) -> tuple[str, int]:
        self.armed, self.hold, self.plan, self.prior_omissions = False, None, None, omitted
        return outcome, count


def tokens(characters: int) -> int:
    return (2 * characters + 6) // 7  # ceil(chars / 3.5)


def briefing_tokens(payload: dict) -> int:
    return tokens(chars(BRIEFING_HEADER) + size(payload) + chars(BRIEFING_FOOTER))


@dataclass(frozen=True)
class Turn:
    operations: tuple[str, ...]
    image_sources: tuple[str, ...]
    eviction_deltas: tuple[int, ...]
    request_tokens: int
    notice_tokens: int

    @property
    def images(self) -> int:
        return len(self.eviction_deltas)


def omission_chars(part: dict) -> int:
    source = part.get('source_id')
    provenance = f'source_id={source}; ' if source is not None else ''
    reread = f' To see this frame again, read source_id {source} with player_source.' if source is not None else ''
    return chars('Historical pixels omitted from this request by frozen image policy; '
                 f'toolCallId={part.get("tool_call_id")}; {provenance}image_index={part["image_index"]}; '
                 f'SHA256={part["sha256"]}. Pixels were not reread; this marker grants no authority or source-read proof.'
                 f'{reread}')


def latest_turn(parts: list[dict], operations: dict, call_chars: dict, text_chars: dict, tail_tokens: int = 0) -> Turn:
    end = next(i for i in range(len(parts) - 1, -1, -1) if parts[i]['role'] == 'assistant') + 1
    start = end - 1
    while start > 0 and parts[start - 1]['role'] == 'assistant':
        start -= 1
    op_ids = tuple(operations[p['tool_call_id']] for p in parts[start:end]
                   if p.get('tool_call_id') in operations)
    trailing = parts[end:]
    images = [p for p in trailing if p['kind'] == 'image']
    # Use original call arguments rather than the renderer's tool-call wrapper.
    # Remaining digest-only text is approximated by its UTF-8 length.
    assistant = tokens(sum(call_chars.get(p.get('tool_call_id'), p['bytes']) for p in parts[start:end]))
    result_chars = defaultdict(int)
    markers = defaultdict(list)
    for part in trailing:
        if part['role'] == 'tool' and part['kind'] != 'image':
            result_chars[part['tool_call_id']] += text_chars.get(part['sha256'], part['bytes'])
    for part in images:
        markers[part['tool_call_id']].append(omission_chars(part))
    deltas = []
    result_tokens = 0
    for tool_id in dict.fromkeys([*result_chars, *markers]):
        length = result_chars[tool_id] + IMAGE_CHARS * len(markers[tool_id])
        result_tokens += tokens(length)
        for marker in markers[tool_id]:
            shorter = length - IMAGE_CHARS + marker
            deltas.append(tokens(shorter) - tokens(length))
            length = shorter
    # The image wrapper is renderer-added text. Only user notices survive as text.
    notes = sum(tokens(text_chars.get(p['sha256'], p['bytes'])) for i, p in enumerate(trailing)
                if p['role'] == 'user' and p['kind'] == 'text'
                and not (i + 1 < len(trailing) and trailing[i + 1]['kind'] == 'image'))
    return Turn(op_ids, tuple(p['source_id'] for p in images if 'source_id' in p),
                tuple(deltas), assistant + result_tokens, max(0, notes - tail_tokens))


def eviction_delta(deltas: list[int], protected: int, policy: CutPolicy) -> int:
    omitted = Projection(0, 0, len(deltas), protected).omissions(policy)
    return sum(deltas[:omitted])


def cut_marker(removed: int, frontier: str, version: str, sources: dict[str, None]) -> str:
    # This lineage uses numbered source IDs. As in the host, non-numbered IDs
    # pass through, and ranges preserve their digit width.
    def numbered(rid: str) -> tuple[str, str]:
        match = re.fullmatch(r'(.*-)([0-9]+)', rid)
        return match.groups() if match else ('', rid)

    compacted = []
    for rid in sources:
        prefix, digits = numbered(rid)
        if compacted and prefix:
            first, _, last = compacted[-1].partition('..')
            previous_prefix, first_digits = numbered(first)
            previous_digits = last or first_digits
            padded = first_digits.startswith('0') and len(first_digits) > 1
            if (prefix == previous_prefix and int(digits) == int(previous_digits) + 1
                    and (len(digits) == len(first_digits) if padded else not digits.startswith('0'))):
                compacted[-1] = f'{first}..{digits}'
                continue
        compacted.append(rid)
    data = dict(grants_authority=False, removed_turns=removed, covered_through_operation_id=frontier,
                knowledge_version=version)
    prefix = numbered(compacted[0].split('..')[0])[0] if compacted else ''
    if prefix and len(sources) >= 2 and all(numbered(rid)[0] == prefix for rid in sources):
        data['source_id_prefix'] = prefix
        compacted = [rid[len(prefix):] for rid in compacted]
    data['source_ids'] = compacted
    return ('BEGIN CONTEXT CUT — older curator-covered turns omitted from this request; grants_authority=false\n'
            f'{canonical(data)}\nEND CONTEXT CUT\n'
            'To inspect any omitted frame again, read its source_id (combining any source_id_prefix '
            'and expanding any start..end range) with player_source.')


def cut_candidates(turns: list[Turn], eligible: int, policy: CutPolicy, *, fixed_tokens: int,
                   fresh_tokens: int, protected: int, removed: int, frontier: str,
                   version: str, source_ids: dict[str, None]) -> Iterator[Projection]:
    deltas = [n for turn in turns for n in turn.eviction_deltas]
    dropped_images = 0
    remaining = sum(turn.request_tokens + turn.notice_tokens for turn in turns)
    sources = dict(source_ids)
    for k, turn in enumerate(turns[:eligible], 1):
        dropped_images += turn.images
        remaining -= turn.request_tokens + turn.notice_tokens
        sources.update(dict.fromkeys(turn.image_sources))
        marker = cut_marker(removed + k, frontier, version, sources)
        total = (fixed_tokens + fresh_tokens + tokens(chars(marker)) + remaining + turn.notice_tokens
                 + eviction_delta(deltas[dropped_images:], protected, policy))
        yield Projection(total, fresh_tokens, len(deltas) - dropped_images, protected)


def replay_cuts(events: list[dict], snapshots: dict, projected_start: dict, coverage: dict) -> dict:
    start = events[0]
    cfg = start['context_cut']
    policy = CutPolicy(cfg['high_mark'], cfg['low_mark'], cfg['min_free'], start['max_context_images'],
                       start['context_image_block'], start['context_window'] - start['max_output_tokens'])
    cuts, estimates, images, manifests = {}, {}, {}, {}
    operations, call_chars, text_chars, tail, updates = {}, {}, {}, {}, {}
    for e in events:
        typ = e['type']
        rid = e.get('request_id')
        if typ == 'context-cut':
            cuts[rid] = e
        elif typ == 'context-estimate':
            estimates[rid] = e
        elif typ == 'context-image-projection':
            images[rid] = e
        elif typ == 'context-manifest':
            manifests[rid] = e
        elif typ == 'tool-start':
            call_chars[e['tool_call_id']] = chars(e['tool']) + chars(canonical(e['arguments']))
        elif typ == 'tool-result':
            result = e['result']
            for part in result.get('content', []):
                if part['type'] == 'text':
                    text_chars[digest(part['text'])] = chars(part['text'])
            record = result.get('structuredContent')
            if (e['tool'] in ('computer_input', 'computer_observe', 'player_handoff')
                    and isinstance(record, dict) and 'operation_id' in record):
                operations[e['tool_call_id']] = record['operation_id']
        elif typ == 'tail-notice':
            tail[rid] = e
        elif typ == 'knowledge-delivery' and 'text' in e:
            text_chars[digest(e['text'])] = chars(e['text'])
            if e['kind'] == 'update' and e.get('outcome') == 'delivered':
                updates[e['receiving_player_request_id']] = e['version']

    state = Hysteresis()
    counts = Counter()
    turns = []
    parts = []
    dropped_sources = {}
    frontier = None
    restored = False
    archived_removed = projected_removed = 0
    active_cut_marker_tokens = 0
    stop_details = []
    control_at = next((e['monotonic_ms'] for e in events if e['type'] == 'control-accepted'), float('inf'))
    initial = next(e for e in events if e['type'] == 'knowledge-delivery' and e['kind'] == 'briefing')
    version = initial['version']
    original_prefix = tokens(chars(initial['text']))
    proposed_prefix = briefing_tokens(projected_start)
    fixed_tokens = next(iter(estimates.values()))['heuristic_tokens'] - original_prefix
    fresh_prefixes = {}
    min_headroom = policy.hard_limit
    max_archive_error = 0
    observed_stops = sum(e['type'] == 'settled' and e['reason'] == 'context-capacity' for e in events)
    for rid, logged in estimates.items():
        cut = cuts.get(rid)
        rewrite = cut is not None and cut['outcome'] == 'cut'
        image = images[rid]
        protected = image['protected_images']
        warning = 0
        if rid in manifests:
            manifest = manifests[rid]
            parts = parts[:manifest['reused_prefix_parts']] + manifest['parts']
            warning = tokens(parts[-1]['bytes']) if rid in tail else 0
            if counts['checks']:
                turns.append(latest_turn(parts, operations, call_chars, text_chars, warning))
        else:
            counts['estimates_without_manifest'] += 1
        counts['checks'] += 1
        version = updates.get(rid, version)
        if rid in updates:
            frontier = coverage.get(version, frontier)
        if cut is not None:
            version = cut['knowledge_version']
            frontier = cut['covered_through_operation_id']
            restored |= cut.get('reason') == 'restored'
        if rewrite:
            archived_removed += cut['removed_turns']
            if archived_removed != cut['cumulative_removed_turns']:
                raise ValueError(f'{rid}: inconsistent archived cumulative cut')
            original_prefix = cut['briefing_tokens']
        archived = turns[archived_removed:]
        if rid in manifests and sum(turn.images for turn in archived) != image['input_images']:
            raise ValueError(f'{rid}: manifest turns disagree with archive image count')
        if rid in manifests:
            marker_tokens = tokens(parts[2]['bytes']) if archived_removed else 0
            boundary_tokens = turns[archived_removed - 1].notice_tokens if archived_removed else 0
            archive_estimate = (fixed_tokens + original_prefix + marker_tokens + boundary_tokens
                                + sum(turn.request_tokens + turn.notice_tokens for turn in archived)
                                + eviction_delta([n for turn in archived for n in turn.eviction_deltas],
                                                 protected, policy))
            max_archive_error = max(max_archive_error, abs(archive_estimate - logged['heuristic_tokens']))

        current = turns[projected_removed:]
        eligible = 0
        if frontier is not None:
            for at, turn in enumerate(current[:-1]):
                if frontier in turn.operations:
                    eligible = at + int(frontier == turn.operations[-1])
                    break

        deltas = [n for turn in current for n in turn.eviction_deltas]
        notes_at_boundary = turns[projected_removed - 1].notice_tokens if projected_removed else 0
        estimated = (fixed_tokens + proposed_prefix + active_cut_marker_tokens + notes_at_boundary + warning
                     + sum(turn.request_tokens + turn.notice_tokens for turn in current)
                     + eviction_delta(deltas, protected, policy))
        # Retain the recorded estimate as a floor when the projected transcript
        # retains the same turns. A changed prefix invalidates past usage.
        if projected_removed == archived_removed:
            estimated = max(estimated, logged['tokens'] - original_prefix + proposed_prefix + warning)
        elif rid not in manifests:
            estimated = max(estimated, logged['tokens'] + proposed_prefix + warning)
        uncut = Projection(estimated, proposed_prefix, len(deltas), protected)
        min_headroom = min(min_headroom, policy.hard_limit - estimated)

        def candidates() -> Iterator[Projection]:
            if eligible:
                if version not in fresh_prefixes:
                    fresh_prefixes[version] = briefing_tokens(briefing(snapshots[version], cut=True))
                yield from cut_candidates(current, eligible, policy, fixed_tokens=fixed_tokens + warning,
                                          fresh_tokens=fresh_prefixes[version], protected=protected,
                                          removed=projected_removed, frontier=frontier, version=version,
                                          source_ids=dropped_sources)

        outcome, count = state.check(policy, uncut, eligible, candidates, frontier, version=version, restored=restored,
                                     orderly_stop=logged['monotonic_ms'] >= control_at)
        counts[outcome] += 1
        if count:
            projected_removed += count
            for turn in current[:count]:
                dropped_sources.update(dict.fromkeys(turn.image_sources))
            active_cut_marker_tokens = tokens(chars(cut_marker(projected_removed, frontier, version, dropped_sources)))
            proposed_prefix = fresh_prefixes[version]
        if outcome == 'stop':
            stop_details.append(dict(request=rid, version=version, tokens=estimated, hard_limit=policy.hard_limit,
                                     eligible=eligible, orderly_stop=logged['monotonic_ms'] >= control_at))
            # A proposed stop ends this actor. Later recorded requests cannot
            # contribute to the projected schedule.
            break

    return dict(counts, observed_holds=sum(c['outcome'] == 'held-back' for c in cuts.values()),
                observed_cuts=sum(c['outcome'] == 'cut' for c in cuts.values()),
                observed_stops=observed_stops, projected_stops=counts['stop'], stop_details=stop_details,
                min_uncut_headroom_tokens=min_headroom, max_archive_heuristic_error_tokens=max_archive_error)


def benchmark(evidence: Path) -> dict:
    runs = [evidence / f'{LINEAGE}-admission-{n:02d}' / 'run' for n in ADMISSIONS]
    snapshots, sources = load_snapshots(runs)
    versions = []
    indexes = {}
    for version in (f'v{n}' for n in range(92)):
        snapshot = snapshots[version]
        titles = recall_index(snapshot, title_only=True)
        sent = recall_index(snapshot)
        indexes[version] = {row['id'] for row in sent['index']}
        versions.append(dict(version=version, source=sources[version], title_chars=size(titles),
                             sent_chars=size(sent), unlisted_entries=sent.get('unlisted_entries', 0),
                             main_cut_chars=size(briefing(snapshot, cut=True, main=True)),
                             proposed_cut_chars=size(briefing(snapshot, cut=True))))
    indexes[None] = set()

    actors = []
    for run in runs:
        paths = sorted(run.glob('actors/*/host.jsonl'))
        if not paths:
            raise ValueError(f'{run}: no actor traces')
        for path in paths:
            with path.open(encoding='utf-8') as stream:
                events = [json.loads(line) for line in stream if line.strip()]
            with path.with_name('knowledge-updates.jsonl').open(encoding='utf-8') as stream:
                coverage = {row['version']: row['operation_id']
                            for row in map(json.loads, stream) if row['schema'] == 'coverage-update-entry/1'
                            and not row['restored'] and row['actor_id'] == events[0]['actor_id']}
            start = next(e for e in events if e['type'] == 'knowledge-delivery' and e['kind'] == 'briefing')
            snapshot = snapshots[start['version']]
            selected = [row['id'] for row in delivery_payload(start)['leads'] if row['id'] in indexes[snapshot.version]]
            proposed = briefing(snapshot, selected)
            actors.append(dict(admission=run.parent.name, actor=path.parent.name, version=start['version'],
                               observed_briefing_text_chars=chars(start['text']),
                               observed_briefing_json_chars=chars(start['text'].split('\n', 2)[1]),
                               projected_briefing_json_chars=size(proposed),
                               omitted_briefing_entries=proposed['unlisted_entries'],
                               recall=replay_recall(events, snapshots, indexes),
                               cut=replay_cuts(events, snapshots, proposed, coverage)))
    recall = Counter()
    cut = Counter()
    for actor in actors:
        recall.update(actor['recall'])
        cut.update({k: v for k, v in actor['cut'].items()
                    if k not in ('min_uncut_headroom_tokens', 'max_archive_heuristic_error_tokens', 'stop_details')})
    recall['projected_usd'] = recall['observed_usd'] - recall['avoided_usd']
    recall['spend_reduction_pct'] = round(100 * recall['avoided_usd'] / recall['observed_usd'], 2)
    recall['silent_or_skipped_pct'] = round(100 * (recall['all_delivered'] + recall['placement_silent']) / recall['fetches'], 2)
    cut['projected_holds'] = sum(cut[k] for k in ('uncovered', 'below-min-free', 'insufficient-cover'))
    cut['hold_reduction_pct'] = round(100 * (1 - cut['projected_holds'] / cut['observed_holds']), 2)
    cut['wider_census_observed_holds'] = WIDER_CENSUS_HELD_BACK
    cut['min_uncut_headroom_tokens'] = min(a['cut']['min_uncut_headroom_tokens'] for a in actors)
    cut['max_archive_heuristic_error_tokens'] = max(a['cut']['max_archive_heuristic_error_tokens'] for a in actors)
    return dict(actors=actors, versions=versions, recall=dict(recall), cut=dict(cut),
                caps_ok=all(a['projected_briefing_json_chars'] <= CUT_BRIEFING_CHARS for a in actors)
                and all(max(v['title_chars'], v['sent_chars'], v['main_cut_chars'], v['proposed_cut_chars'])
                        <= CUT_BRIEFING_CHARS for v in versions),
                no_increase_in_projected_stops=cut['projected_stops'] <= cut['observed_stops'])


def markdown(result: dict) -> str:
    recall, cut = result['recall'], result['cut']
    lines = ['# Offline player host replay on sealed #896-b', '',
             '## Actor-start briefing', '',
             '| Admission | Actor | Version | Observed framed chars | Observed JSON chars | Projected JSON chars | Omitted |',
             '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for row in result['actors']:
        lines.append(f"| {row['admission']} | {row['actor']} | {row['version'] or 'empty'} | "
                     f"{row['observed_briefing_text_chars']:,} | {row['observed_briefing_json_chars']:,} | "
                     f"{row['projected_briefing_json_chars']:,} | {row['omitted_briefing_entries']:,} |")
    lines += ['', '## Recall and spend', '',
              f"- {recall['all_delivered']} of {recall['fetches']} recorded fetches skip for `all-delivered`.",
              f"- {recall['placement_silent']} additional fetches lose their entire reminder at placement.",
              f"- Combined silent or skipped share is {recall['silent_or_skipped_pct']}%.",
              f"- {recall['selected_omitted_from_index']} recorded selections include a row outside the sent index.",
              f"- Observed recall spend is ${recall['observed_usd']:.6f}. Removing only the pre-fetch skips projects "
              f"${recall['projected_usd']:.6f} ({recall['spend_reduction_pct']}% lower).",
              '', '## Cut hysteresis on the recorded schedule', '',
              f"- {cut['observed_holds']:,} observed holds and {cut['projected_holds']:,} projected edge holds "
              f"({cut['hold_reduction_pct']}% lower) in #896-b. The wider twelve-run census recorded "
              f"{cut['wider_census_observed_holds']:,} holds.",
              f"- Recorded cuts {cut['observed_cuts']:,}. Projected normal cuts {cut.get('cut', 0):,} and "
              f"strict-fit rescues {cut.get('rescue', 0):,}.",
              f"- {cut['observed_stops']:,} observed and {cut['projected_stops']:,} projected hard capacity stops "
              f"over {cut['checks']:,} checks. Minimum uncut headroom is {cut['min_uncut_headroom_tokens']:,} "
              f"estimated tokens. {cut.get('estimates_without_manifest', 0)} estimates lack a request manifest.",
              f"- Maximum absolute error against recorded heuristic estimates is "
              f"{cut['max_archive_heuristic_error_tokens']:,} tokens.",
              f"- **Capacity gate {'passes' if result['no_increase_in_projected_stops'] else 'does not pass'}.**"]
    for actor in result['actors']:
        for stop in actor['cut']['stop_details']:
            lines.append(f"  - {actor['admission']} actor {actor['actor']}, {stop['request']}, {stop['version']}. "
                         f"{stop['tokens']:,} estimated tokens against a {stop['hard_limit']:,}-token limit. "
                         f"Orderly stop {'accepted' if stop['orderly_stop'] else 'absent'}.")
    lines += ['', '## Per-version recall indexes and cut briefings', '',
              '| Version | Source | Title-only chars | Sent chars | Unlisted | Main cut chars | Proposed cut chars |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in result['versions']:
        lines.append(f"| {row['version']} | {row['source']} | {row['title_chars']:,} | {row['sent_chars']:,} | "
                     f"{row['unlisted_entries']:,} | {row['main_cut_chars']:,} | {row['proposed_cut_chars']:,} |")
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, help='sealed evidence directory (default is the main checkout store)')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--json', action='store_true')
    output.add_argument('--markdown', action='store_true')
    args = parser.parse_args(argv)
    result = benchmark(args.evidence if args.evidence is not None else default_store())
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(markdown(result), end='')
    return int(not (result['caps_ok'] and result['no_increase_in_projected_stops']))


if __name__ == '__main__':
    raise SystemExit(main())
