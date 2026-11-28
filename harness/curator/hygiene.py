"""Deterministic zero-model hygiene worklist, typed-incidence signals, and live `state_key` index (#1020, #1023).

Reads only current records from the pinned snapshot (never dumping full raw `facts.jsonl` into
model-facing workspaces). Zero hard cardinality or article-size caps; every output is advisory
and byte-bounded.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from itertools import combinations
import math
import re

from harness.jsonio import canonical

from . import check

ARTICLE_CUTOFF_BYTES = 8_192
CUT_BRIEFING_CHARS = 24_000
HIGH_DF_TEMPLATE_FRACTION = 0.20
BIBLIO_OVERLAP_THRESHOLD = 0.50
DUPLICATE_SIM_THRESHOLD = 0.45
CONTAINMENT_THRESHOLD = 0.70
KEY_ALIAS_SIM_THRESHOLD = 0.40
CONTRADICTION_SIM_THRESHOLD = 0.35
MAX_SECTION_BYTES = 16_384
MAX_ITEMS_PER_SECTION = 25

_WORD = re.compile(r'[^\W_]+', re.UNICODE)
# Known English-only lexical coupling (advisory contradiction signal only; numeric divergence
# in `_opposing_values` remains script-independent).
_POLARITY_GROUPS = (
    frozenset(('open', 'opened', 'unlocked', 'passable', 'clear', 'present', 'available', 'lit', 'burning', 'full', 'on', 'active', 'safe')),
    frozenset(('closed', 'locked', 'impassable', 'blocked', 'absent', 'missing', 'gone', 'empty', 'out', 'extinguished', 'off', 'broken', 'damaged', 'dead')),
)
_NUMBER = re.compile(r'\b\d+(?:\.\d+)?%?\b')


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _trigrams(text: str) -> set[str]:
    compact = ' '.join(_words(text))
    if len(compact) < 3:
        return {compact} if compact else set()
    return {compact[i:i + 3] for i in range(len(compact) - 2)}


def _fact_surface(fact: dict) -> str:
    parts = [fact.get('subject', ''), fact.get('text', ''), fact.get('when', ''), ' '.join(fact.get('tags', ()))]
    return ' '.join(part for part in parts if part)


def _idf_cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(weight * right.get(tok, 0.0) for tok, weight in left.items())
    if dot <= 0.0:
        return 0.0
    norm_l = math.sqrt(sum(w * w for w in left.values()))
    norm_r = math.sqrt(sum(w * w for w in right.values()))
    return dot / (norm_l * norm_r) if norm_l and norm_r else 0.0


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left | right)
    return len(left & right) / union if union else 0.0


def _containment(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    smaller = min(len(left), len(right))
    return len(left & right) / smaller if smaller else 0.0


def _same_frame_nogood(left: dict, right: dict) -> bool:
    """Two facts with distinct `state_key`s citing any common frame are distinct entities."""
    lk, rk = left.get('state_key'), right.get('state_key')
    if lk is not None and rk is not None and lk != rk:
        return bool(set(left['citations']) & set(right['citations']))
    return False


def _opposing_values(left: dict, right: dict) -> bool:
    lw, rw = set(_words(left['text'])), set(_words(right['text']))
    if ((lw & _POLARITY_GROUPS[0] and rw & _POLARITY_GROUPS[1])
            or (lw & _POLARITY_GROUPS[1] and rw & _POLARITY_GROUPS[0])):
        return True
    ln, rn = set(_NUMBER.findall(left['text'])), set(_NUMBER.findall(right['text']))
    return bool(ln and rn and ln != rn)


def state_key_index(records: list[dict], *, world: str | None = None) -> list[dict]:
    """Return the compact per-world current-state `state_key` index (also the `#1021` landmark roster)."""
    rows = []
    for row in records:
        if row['record'] != 'fact' or not check.current(row) or 'state_key' not in row:
            continue
        row_world = row['scope'].get('world')
        if world is not None and row_world != world:
            continue
        rows.append(dict(
            state_key=row['state_key'],
            id=row['id'],
            world=row_world,
            statement_kind=row['statement_kind'],
            lifecycle_state=row['lifecycle_state'],
            anchor=row.get('anchor'),
            subject=row.get('subject'),
            text=row['text'],
        ))
    rows.sort(key=lambda r: (r['world'] or '', r['state_key'], r['id']))
    return rows


def lookup_state_keys(records: list[dict], query: str, *, world: str | None = None, limit: int = 10) -> list[dict]:
    """Zero-model exact, lexical, and character-trigram lookup over active `state_key` entries (#1020)."""
    entries = state_key_index(records, world=world)
    if not entries or not query.strip():
        return []
    q_norm = query.strip().lower()
    q_words = set(_words(q_norm))
    q_tri = _trigrams(q_norm)
    scored: list[tuple[float, dict]] = []
    for entry in entries:
        key = entry['state_key']
        surface = ' '.join(part for part in (key.replace('-', ' '), entry.get('subject') or '',
                                             entry.get('anchor') or '', entry['text']) if part)
        if q_norm == key or q_norm == entry['id']:
            score = 10.0
        else:
            words = set(_words(surface))
            lex = len(q_words & words) / len(q_words) if q_words else 0.0
            tri = _jaccard(q_tri, _trigrams(surface))
            score = 2.0 * lex + tri
        if score > 0.0:
            scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], item[1]['state_key'], item[1]['id']))
    return [dict(entry, score=round(score, 4)) for score, entry in scored[:limit]]


def state_key_section(records: list[dict], *, world: str | None = None, max_bytes: int = MAX_SECTION_BYTES) -> list[str]:
    """Format the compact per-world current-state `state_key` index for the live admission brief."""
    entries = state_key_index(records, world=world)
    lines = ['## Current world state keys (landmark roster)', '']
    if not entries:
        lines.append('None.')
        return lines
    used_bytes = 0
    for index, entry in enumerate(entries):
        snippet = entry['text'].replace('\n', ' ')
        if len(snippet) > 120:
            snippet = snippet[:119] + '…'
        meta = [entry['statement_kind']]
        if entry['lifecycle_state'] != 'active':
            meta.append(entry['lifecycle_state'])
        if entry['anchor']:
            meta.append(f'anchor={entry["anchor"]}')
        if entry['subject']:
            meta.append(f'subject={entry["subject"]!r}')
        row = f"- `{entry['state_key']}` (`{entry['id']}`, {', '.join(meta)}): {snippet}"
        used_bytes += len(row.encode('utf-8')) + 1
        if used_bytes > max_bytes:
            lines.append(f'- … ({len(entries) - index} more active keys omitted for byte budget)')
            break
        lines.append(row)
    return lines


def worklist(records: list[dict], *, limit: int | None = MAX_ITEMS_PER_SECTION) -> dict:
    """Compute deterministic typed-incidence signals and pairwise advisory hygiene candidates."""
    active = sorted((r for r in records if check.current(r)), key=check.owner)
    facts = [r for r in active if r['record'] == 'fact']
    articles = [r for r in active if r['record'] == 'article']
    facts_by_id = {f['id']: f for f in facts}
    total_active = len(active)

    # 1. Per-tag and per-subject df/N with majority flag (df > N/2) and tag-vs-scope overlap.
    tag_df: Counter[str] = Counter(tag for row in active for tag in row['tags'])
    subject_df: Counter[str] = Counter(row['subject'] for row in facts if 'subject' in row)
    scope_tokens: set[str] = set()
    for row in active:
        for k, v in row['scope'].items():
            scope_tokens.add(k.lower())
            if isinstance(v, str):
                scope_tokens.add(v.lower())
    majority_tags = [
        dict(tag=tag, df=df, n=total_active)
        for tag, df in sorted(tag_df.items(), key=lambda kv: (-kv[1], kv[0]))
        if total_active >= 2 and df * 2 > total_active
    ]
    majority_subjects = [
        dict(subject=subj, df=df, n=len(facts))
        for subj, df in sorted(subject_df.items(), key=lambda kv: (-kv[1], kv[0]))
        if len(facts) >= 2 and df * 2 > len(facts)
    ]
    tag_scope_overlap = [
        dict(tag=tag, df=tag_df[tag])
        for tag in sorted(tag_df) if tag in scope_tokens
    ]

    # 2. Oversized articles (>8,192 UTF-8 bytes canonical JSON) and bibliographic coupling (>50%).
    oversized_articles = []
    for art in articles:
        raw_bytes = len(canonical(art).encode('utf-8'))
        chars = len(canonical(art).encode('utf-16-le')) // 2
        if raw_bytes > ARTICLE_CUTOFF_BYTES:
            oversized_articles.append(dict(
                slug=art['slug'], bytes=raw_bytes, cutoff_bytes=ARTICLE_CUTOFF_BYTES,
                chars=chars, briefing_budget_chars=CUT_BRIEFING_CHARS,
                facts=len(check.cited_facts(art)),
            ))
    oversized_articles.sort(key=lambda r: (-r['bytes'], r['slug']))

    bibliographic_coupling = []
    art_facts = {art['slug']: check.cited_facts(art) for art in articles}
    for left, right in combinations(articles, 2):
        lf, rf = art_facts[left['slug']], art_facts[right['slug']]
        smaller = min(len(lf), len(rf))
        if not smaller:
            continue
        shared = len(lf & rf)
        overlap = shared / smaller
        if overlap > BIBLIO_OVERLAP_THRESHOLD:
            bibliographic_coupling.append(dict(
                left=left['slug'], right=right['slug'],
                shared=shared, overlap=round(overlap, 3),
            ))
    bibliographic_coupling.sort(key=lambda r: (-r['overlap'], -r['shared'], r['left'], r['right']))

    # 3. Chronological world->world `see_also` chains (world fact linking `see_also` to an earlier world fact).
    chronological_see_also = []
    for fact in facts:
        if 'world' not in fact['scope']:
            continue
        for link in fact['links']:
            if link['rel'] != 'see_also':
                continue
            dst = facts_by_id.get(link['target'])
            if dst is not None and 'world' in dst['scope'] and dst['seen']['order'] < fact['seen']['order']:
                chronological_see_also.append(dict(source=fact['id'], target=dst['id']))
    chronological_see_also.sort(key=lambda r: (r['source'], r['target']))

    # 4. Exact All-Pairs IDF-weighted word + char-trigram similarity with high-DF template stripping.
    doc_words: dict[str, set[str]] = {}
    doc_trigrams: dict[str, set[str]] = {}
    token_df: Counter[str] = Counter()
    for fact in facts:
        ws = set(_words(_fact_surface(fact)))
        doc_words[fact['id']] = ws
        doc_trigrams[fact['id']] = _trigrams(_fact_surface(fact))
        token_df.update(ws)
    n_facts = len(facts)
    stripped_tokens = {
        tok for tok, df in token_df.items()
        if n_facts >= 5 and (df / n_facts) > HIGH_DF_TEMPLATE_FRACTION
    }
    idf_vecs: dict[str, dict[str, float]] = {}
    clean_words: dict[str, set[str]] = {}
    for fact in facts:
        fid = fact['id']
        kept = doc_words[fid] - stripped_tokens
        if not kept:
            kept = doc_words[fid]
        clean_words[fid] = kept
        idf_vecs[fid] = {tok: math.log((n_facts + 1) / (token_df[tok] + 1)) + 1.0 for tok in sorted(kept)}

    contradicts_pairs: set[tuple[str, str]] = set()
    for fact in facts:
        for link in fact['links']:
            if link['rel'] == 'contradicts':
                contradicts_pairs.add((fact['id'], link['target']))
                contradicts_pairs.add((link['target'], fact['id']))

    duplicate_candidates = []
    potential_contradictions = []
    key_alias_candidates = []

    for left, right in combinations(facts, 2):
        lid, rid = left['id'], right['id']
        if (lid, rid) in contradicts_pairs:
            continue
        if _same_frame_nogood(left, right):
            continue
        word_sim = _idf_cosine(idf_vecs[lid], idf_vecs[rid])
        tri_sim = _jaccard(doc_trigrams[lid], doc_trigrams[rid])
        sim = 0.65 * word_sim + 0.35 * tri_sim
        contain = _containment(clean_words[lid], clean_words[rid])
        shared_sources = sorted(set(left['citations']) & set(right['citations']))

        same_scope = left['scope'] == right['scope']
        same_anchor = left.get('anchor') == right.get('anchor')
        same_kind = left['statement_kind'] == right['statement_kind']
        same_when = left.get('when') == right.get('when')

        # Key-alias candidates (#1020): distinct state_keys in same (world, anchor), already filtered by same-frame nogood.
        lk, rk = left.get('state_key'), right.get('state_key')
        if (lk is not None and rk is not None and lk != rk
                and left['scope'].get('world') == right['scope'].get('world')
                and same_anchor and (sim >= KEY_ALIAS_SIM_THRESHOLD or contain >= CONTAINMENT_THRESHOLD)):
            key_alias_candidates.append(dict(
                left_id=lid, left_key=lk, right_id=rid, right_key=rk,
                similarity=round(sim, 3), containment=round(contain, 3),
            ))
            continue

        # Potential contradictions: same scope & anchor, high overlap, opposing polarity/numbers.
        if same_scope and same_anchor and sim >= CONTRADICTION_SIM_THRESHOLD and _opposing_values(left, right):
            potential_contradictions.append(dict(
                left=lid, right=rid, similarity=round(sim, 3),
                shared_sources=shared_sources,
            ))
            continue

        # Duplicate / containment candidates: hard cannot-link rules require identical scope, kind, anchor, when.
        if (same_scope and same_kind and same_anchor and same_when
                and lk == rk
                and (sim >= DUPLICATE_SIM_THRESHOLD or contain >= CONTAINMENT_THRESHOLD)):
            duplicate_candidates.append(dict(
                left=lid, right=rid, similarity=round(sim, 3), containment=round(contain, 3),
                shared_sources=shared_sources,
                eligible_for_hygiene_merge=('world' not in left['scope'] and lk is None
                                            and left['lifecycle_state'] == 'active'
                                            and right['lifecycle_state'] == 'active'),
            ))

    duplicate_candidates.sort(key=lambda r: (-max(r['similarity'], r['containment']), r['left'], r['right']))
    potential_contradictions.sort(key=lambda r: (-r['similarity'], r['left'], r['right']))
    key_alias_candidates.sort(key=lambda r: (-max(r['similarity'], r['containment']), r['left_key'], r['right_key']))

    return dict(
        active_records=total_active,
        active_facts=n_facts,
        active_articles=len(articles),
        majority_tags=majority_tags[:limit],
        majority_subjects=majority_subjects[:limit],
        tag_scope_overlap=tag_scope_overlap[:limit],
        oversized_articles=oversized_articles[:limit],
        bibliographic_coupling=bibliographic_coupling[:limit],
        chronological_see_also=chronological_see_also[:limit],
        duplicate_candidates=duplicate_candidates[:limit],
        potential_contradictions=potential_contradictions[:limit],
        key_alias_candidates=key_alias_candidates[:limit],
    )


def hygiene_trigger(records: list[dict]) -> dict:
    """Identify due hygiene work and fingerprint the full advisory and must-clear lists."""
    report = worklist(records, limit=None)
    stale = sorted(check._stale_pairs(records))
    overlapping = {row[side] for row in report['bibliographic_coupling'] for side in ('left', 'right')}
    counts = dict(
        stale_citations=len(stale),
        duplicate_pairs=len(report['duplicate_candidates']),
        oversized_overlapping_articles=sum(row['slug'] in overlapping for row in report['oversized_articles']),
        total_advisory=sum(len(rows) for rows in report.values() if isinstance(rows, list)),
    )
    thresholds = dict(stale_citations=1, duplicate_pairs=3, oversized_overlapping_articles=1, total_advisory=8)
    reasons = [key for key, threshold in thresholds.items() if counts[key] >= threshold]
    digest = hashlib.sha256(canonical({'worklist': report, 'must_clear': stale}, sort_keys=True).encode()).hexdigest()
    return dict(triggered=bool(reasons), digest=digest, reasons=reasons, counts=counts)


def worklist_section(records: list[dict], *, max_bytes: int = MAX_SECTION_BYTES) -> list[str]:
    """Render deterministic byte-bounded hygiene worklist sections for grooming/hygiene briefs."""
    report = worklist(records)
    lines = ['## Hygiene worklist (deterministic, advisory)', '']

    def _append_group(title: str, rows: list[str]) -> None:
        lines.extend([f'### {title}', ''])
        lines.extend(rows or ['None.'])
        lines.append('')

    _append_group(
        'Structural signals',
        [
            *(f"- Majority tag `{r['tag']}`: {r['df']}/{r['n']} (>N/2)" for r in report['majority_tags']),
            *(f"- Majority subject {r['subject']!r}: {r['df']}/{r['n']} (>N/2)" for r in report['majority_subjects']),
            *(f"- Tag duplicates scope token: `{r['tag']}` (df={r['df']})" for r in report['tag_scope_overlap']),
            *(f"- Oversized article `{r['slug']}`: {r['bytes']:,} B (cutoff {r['cutoff_bytes']:,} B; "
              f"{r['chars']:,} / {r['briefing_budget_chars']:,} briefing chars; {r['facts']} facts)"
              for r in report['oversized_articles']),
            *(f"- High bibliographic coupling: `{r['left']}` & `{r['right']}` ({r['shared']} shared facts, {r['overlap']:.0%})"
              for r in report['bibliographic_coupling']),
            *(f"- Chronological world `see_also`: `{r['source']}` -> `{r['target']}`"
              for r in report['chronological_see_also'][:10]),
        ],
    )
    _append_group(
        'Duplicate and containment candidates',
        [
            f"- `{r['left']}` & `{r['right']}` (sim={r['similarity']}, contain={r['containment']}"
            + (f", co-witness={len(r['shared_sources'])}" if r['shared_sources'] else '')
            + (', hygiene-merge-eligible' if r['eligible_for_hygiene_merge'] else '') + ')'
            for r in report['duplicate_candidates']
        ],
    )
    _append_group(
        'Potential contradictions',
        [
            f"- `{r['left']}` vs `{r['right']}` (sim={r['similarity']}"
            + (f", co-witness={len(r['shared_sources'])}" if r['shared_sources'] else '') + ')'
            for r in report['potential_contradictions']
        ],
    )
    _append_group(
        'Key-alias candidates',
        [
            f"- `{r['left_key']}` (`{r['left_id']}`) ~ `{r['right_key']}` (`{r['right_id']}`) "
            f"(sim={r['similarity']}, contain={r['containment']})"
            for r in report['key_alias_candidates']
        ],
    )

    bounded: list[str] = []
    used = 0
    for line in lines:
        used += len(line.encode('utf-8')) + 1
        if used > max_bytes:
            bounded.append('- … (worklist truncated at byte budget)')
            break
        bounded.append(line)
    return bounded
