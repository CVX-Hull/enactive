---
owner: lead
review_trigger: Batch 1 store-migration PR lands or a frozen Batch 1 schema/operation changes
status: active
---

# Frozen Batch 1 store-migration contract (`#1046`)

## At a glance

- **Scope.** Freezes the exact schemas, submission operations, gate invariants, exporter and reader projections, advisory hygiene cutoffs, complete caller/spectator/fixture inventory, fresh-world validation rule, and five-session `#963`+`#998` archive cutover plan for the coordinated Batch 1 `S-MIGRATION` PR covering [#1020](https://github.com/CVX-Hull/enactive/issues/1020), [#1021](https://github.com/CVX-Hull/enactive/issues/1021), [#1022](https://github.com/CVX-Hull/enactive/issues/1022) (with folded [#1024](https://github.com/CVX-Hull/enactive/issues/1024) Kinds 1–5 synthesis scope), and [#1023](https://github.com/CVX-Hull/enactive/issues/1023).
- **Schema versions frozen together (`S-MIGRATION`, zero compatibility shims):**
  - `curator-knowledge/4` → **`curator-knowledge/5`**
  - `curator-fact/5` → **`curator-fact/6`**
  - `curator-submission/2` → **`curator-submission/3`**
  - `delivered-knowledge/3` → **`delivered-knowledge/4`**
  - `player-knowledge/3` → **`player-knowledge/4`**
- **`#1021` depiction pointer decision:** Full-frame **`depiction_source_id`** (optional `frame_source_id` in `citations`) is selected for Batch 1; `depiction.region` cropping is deferred because the offline `#998` bounding-box check ([baseline record](../acceptance/2026-11-27-store-migration-freeze-and-998-baselines-1046.md)) confirmed that the `20%–35%` neighborhood band structurally clips the multi-tile Luxury RV (`55.0%` frame height) to `62.5%–63.6%` recall and could not directly test the live curator transport at `$0`.
- **Fresh-world & five-session archive cutover:** No `/4 -> /5` live-store converter is built; post-Batch-1 live validation starts on a fresh world ([owner decision](../decisions/owner-decisions.md#archive-index-adds-963-and-998-sessions)). Read-only spectator views preserve the five cited `#963`+`#998` `delivered-knowledge/3` sessions in Batch 1 via an explicit constant removed in Batch 2 when those five sessions join `data/evaluation/archive-sessions.json` and `ARCHIVE_COMBINATIONS` alongside `campaign-run/14` and `player-host/13`.
- **Shared `#998` replay & retrieval base:** [`tools/knowledge_retrieval_benchmark.py`](../../tools/knowledge_retrieval_benchmark.py) (`knowledge-retrieval-benchmark/2`) and [`tools/player_host_replay_benchmark.py`](../../tools/player_host_replay_benchmark.py) (`player-host-replay-benchmark/2`, `--lineage {896-b,998,all}`) use a self-contained read-only sealed `curator-knowledge/4` tag reader (`export_sealed_v3_tag`, independent of the live exporter). When Batch 1 bumps `delivered-knowledge/4`, `tools/knowledge_retrieval_benchmark.py` projects sealed `#998` `delivered-knowledge/3` snapshots in memory to `delivered-knowledge/4` via a benchmark-only projection (matching `Corpus` / `LEGACY_CLAIM_KINDS` for `delivered-knowledge/2`) so paired `$0` replays keep running across Batches 1–4.

---

## 1. Frozen schema inventory

### 1.1 `curator-knowledge/5` (`knowledge.json` and `provenance.json`)

- `knowledge.json`: `{"schema": "curator-knowledge/5", "game": "<game>"}`. Repositories carrying `curator-knowledge/4` or earlier are rejected cleanly; no in-place converter exists.
- `provenance.json`: retains `frames`, `sessions`, `branches`, `restores`, optional `last_admission`, and adds sparse **`frame_clocks`**:
  - `frame_clocks`: object mapping `<frame_source_id>` → `<clock_label>` (nonblank UTF-8 string of `1..64` printable characters, rejecting control characters and all-whitespace strings, preserving non-ASCII HUD text per `P-GENERALITY`, verbatim HUD clock/date text or brief literal visual phase cue).
  - Sparse: omitted for frames showing neither a clock nor an identifiable phase cue.
  - Uninterpreted: software never parses, normalizes, or orders by `clock_label`; ordering stays strictly on lineage frame position (`seen` / `order`).
  - Immutable once recorded: a later admission submission may add a `clock_label` for an unlabelled frame in `window_frames`, or repeat the identical label, and is rejected if it submits a conflicting label for an already-labelled frame.

### 1.2 `curator-fact/6` (`schemas/curator-fact.schema.json`)

#### Stored fact (`record: "fact"`)

| Field | Status vs. `/5` | Exact shape and gate rule |
| --- | --- | --- |
| `schema` | Bumped | `"curator-fact/6"` |
| `statement_kind` | Replaces `claim_kind` + `evidence_basis` | Required closed enum `["observation", "state", "outcome", "inference", "synthesis"]` (1-to-1 with `#1024` Kinds 1–5; structurally rejects Kinds 6–7 and retires `strategy`, `interface`, `mechanic`, `entity_property`, `instance_state`, `hinted`). |
| `state_key` | Added (`#1020`) | Optional opaque kebab identifier matching `id_or_slug` (`^[a-z0-9][a-z0-9-]{0,63}$`). **Required** when `statement_kind == "state"`; **optional** when `statement_kind == "synthesis"` and world-bound (`"world"` in `scope`); **forbidden** on game-wide facts and on `observation`/`outcome`/`inference`. Shares one global reserved namespace with all fact IDs and article slugs across the repository's full history (active, superseded, ended, or retracted): no `state_key` may equal any fact ID or article slug ever reserved in the store, and no new fact ID or article slug may equal any existing `state_key`. Multiple readings of the same fluent share one `state_key` while each reading carries its own distinct `id`. |
| `anchor` | Added (`#1021`) | Optional `state_key` (matching `id_or_slug`) on world-bound facts. Must resolve to a `state_key` known in the same `scope.world` (present on an active or historical reading in the snapshot) and form an acyclic parent forest (no self-anchor, no cycle). Ending an anchor's key never blocks retirement and never propagates `needs_review` to anchored facts; extrinsic placement-coupled claims use explicit `depends_on`. |
| `when` | Replaced (`#1022`) | Optional nonblank UTF-8 string (omitted when unconditional). Replaces `{note, requires}` object. Zero structured condition DSL and zero `condition_unverified`. |
| `depiction_source_id` | Added (`#1021`, `#1046`) | Optional `frame_source_id`. Must be a member of the fact's `citations`. Full-frame pointer only; `region` crop deferred per `#1046`. |
| `superseded_reason` | Added (`#1020`) | Optional enum `["restated", "narrowed", "corrected", "changed"]`. Present if and only if `superseded_by` is present. |
| `lifecycle_state` | Extended rule (`#1020`) | Unchanged five-value enum `["active", "contested", "superseded", "retracted", "ended"]`. On `changed` temporal supersession, the prior fact carries `lifecycle_state: "ended"`, `superseded_by: [new_id]`, `superseded_reason: "changed"`, `retired` omitted, and `valid_to` set to the successor's `valid_from` on a single surviving timeline (`null` on multi-lineage). |
| `links` | Extended (`#1022`) | Closed relation enum `["depends_on", "contradicts", "part_of", "see_also"]`. For `depends_on`, `target` may name either a fact ID (reading pin) or a reserved `state_key` (entity-existence pin) in the unified global namespace. `statement_kind == "synthesis"` requires at least one `depends_on` link. |
| `claim_kind`, `evidence_basis` | Deleted (`#1022`) | Removed with zero replacement (`S-MIGRATION`). |

All other stored fact fields (`record`, `id`, `tags` ≤ 8, `text`, optional `subject`, `scope`, `citations`, `lineages`, `seen`, `valid_from`, `valid_to`, `stale_citations`, `needs_review`, `superseded_by`, `retired`, `retagged`, `published_in`, `session`) keep their `/5` shapes except where `lifecycle_state == "ended"` permits `superseded_by` with `superseded_reason == "changed"` (mutually exclusive with `retired`).

#### Stored article (`record: "article"`)

Bumps `schema` to `"curator-fact/6"`. All article fields (`id: "<slug>@vN"`, `slug`, `title`, `lead`, `body`, `tags` ≤ 8, `scope`, `links`, `lineages`, `last_confirmed`, `valid_from`, `valid_to`, `lifecycle_state`, `stale_citations`, `needs_review`, `superseded_by`, `retired`, `retagged`, `published_in`, `session`) keep their closed `/5` shapes; `depends_on` targets in article `links` may name either a record ID or a `state_key`.

### 1.3 `curator-submission/3` (`schemas/curator-submission.schema.json`)

- Top-level adds optional **`frame_clocks`**: `{<frame_source_id>: <clock_label>}` (`1..64` printable nonblank UTF-8 chars; each key must exist in `window_frames` for the current admission window; repeating an identical already-recorded label is allowed, while conflicting labels are rejected).
- `submitted_fact` / `superseded_fact`: `schema: "curator-fact/6"`, `statement_kind`, optional `state_key`, optional `anchor`, optional `when` (string), optional `depiction_source_id`; removes `claim_kind`, `evidence_basis`, and `when.{note, requires}`.
- **`supersede_fact`**: `reason_kind` enum `["restated", "corrected", "changed"]`:
  - `changed`: world-bound keyed fact(s) sharing one `state_key`; `fact.state_key` must equal the target's `state_key`; `fact.citations` must contain at least one frame strictly after every target's `seen` on a surviving timeline; sets each target to `lifecycle_state: "ended"`, `superseded_by: [new_id]`, `superseded_reason: "changed"`, `valid_to` on single surviving timeline; forbidden during autonomous hygiene grooming (`session_kind == "hygiene"`).
  - `restated`: preserves `scope`, `statement_kind`, `state_key`, `anchor`, byte-equal `when`, full citation union, outgoing `depends_on`/`contradicts` outside merged inputs; rejects `contested` inputs (closing the `check.py:392-396` hole).
  - `corrected`: requires at least one new frame; forbidden during autonomous hygiene grooming (`session_kind == "hygiene"`).
- **`retire_fact`**: `reason_kind` `"wrong"` or `"ended"`. Forbidden on active world-bound facts during autonomous hygiene grooming (`session_kind == "hygiene"`).
- **`remap_citations`**: migrates `from` from a scalar ID to **`from`: array of 1+ distinct `id_or_slug`** (`minItems: 1, uniqueItems: true`, `S-MIGRATION`), supporting both 1-to-1 and **N→1 restated merge** remapping strictly for article claim citations (`body[*].facts`), never for `depends_on` reading pins (`#1023`). Every ID in `from` must resolve along restated chains to `to`.
- **`narrow_fact`**, **`add_fact`**, **`add_article`**, **`revise_article`**, **`edit_article`**, **`retire_article`**, **`retag`**: updated to `curator-fact/6` shapes (`when` preservation on `narrow_fact` checks byte-equal `when` string when parent `when` is present).

### 1.4 `delivered-knowledge/4` (`tools/knowledge_export.py`, `harness/player/knowledge.py`, `tools/player_host/knowledge.mjs`)

- Top-level: `schema: "delivered-knowledge/4"`, plus **`frame_clocks`**: `{<frame_source_id>: <clock_label>}` containing ONLY directly observed labels for frames cited in delivered facts' `citation_source_ids` (including `depiction_source_id`, which is a subset of `citation_source_ids`). Empty `{}` when empty or unlabelled. Used directly by `#1025`'s `player-source-read/2`.
- Position objects (`seen`, `last_confirmed`): retain `session` (alias), `actor`, `step`, `order`, plus optional directly observed `clock_label: string` OR optional `prior_clock: {"label": string, "step_offset": int >= 1}` when a clockless modal `seen` frame carries forward the nearest earlier labelled frame in the same actor segment (never forged as `clock_label` and never added to `citations`).
- Flags & status markers: **`condition_unverified` deleted**. `FLAGS = ('needs_review', 'unverified_branch')`; `STATUS_MARKERS = ('contested', 'unverified_branch', 'needs_review')`.
- Delivered facts:
  - Replace `claim_kind` + `evidence_basis` with **`statement_kind`**.
  - Optional **`state_key`**, optional **`anchor`**, optional **`anchor_display`** (resolved display cue derived from the anchor's current reading `subject` — falling back to the anchor's most recent historical reading `subject` or hyphen-spaced key label if the anchor key ended — for `#1023` indexing at weight `×2` without indexing raw keys), optional **`when`** (string), optional **`depiction_source_id`**.
- `history.replaced[*].reason`: closed enum `("restated", "narrowed", "corrected", "changed")`.
- `links` / `backlinks`: `depends_on` target may be a public record ID or a `state_key` present on at least one delivered world fact.

### 1.5 `player-knowledge/4` (`harness/player/knowledge.py`, `harness/player_view.py`)

- `schema: "player-knowledge/4"`.
- `HIT_VIA = frozenset(('match', 'hop', 'fuzzy'))` (`'fuzzy'` emitted strictly by `#1023`'s zero-hit-only char-trigram fallback).
- **`read(identity)` on `state_key` targets:** checks current record IDs, revisions, history, and article titles first; if none match and `identity` matches a `state_key` carried by one or more delivered world facts, returns `resolution: "state_key"`, `resolved_from: None`, and `records: [<all delivered facts carrying that state_key in delivered order>]`.
- Compact fact hit (`kind == "fact"`): replaces `claim_kind` with `statement_kind`; adds optional `when` (inline string when present), optional `state_key`, optional `anchor`, optional `anchor_display`, optional `depiction_source_id`; `status` carries only `('contested', 'unverified_branch', 'needs_review')`.
- Compact article hit (`kind == "article"`): keeps `id`, `kind`, `revision`, `title`, `snippet`, `tags`, `via`, optional `status` (without `condition_unverified`).

---

## 2. Frozen gate, hygiene, and retrieval invariants

### 2.1 Gate invariants (`harness/curator/check.py`)

1. **Unified global identifier namespace (`#1020`, `#1022`):** Fact IDs, article slugs, and `state_key`s share one global reserved namespace across all historical and current records in the repository (`reserved_ids | all_record_owners | all_state_keys` partitioned cleanly between record owners and `state_key`s). No `state_key` may ever equal any record ID or article slug (active, superseded, ended, or retracted), so every `depends_on` target resolves unambiguously to either a fact reading or a keyed entity.
2. **Hard keyed-state uniqueness (`#1020`, `#1022`):** At most one active uncontested reading per `(world, surviving timeline, state_key)`. Multiple simultaneous readings for one key are accepted only when mutually linked by `contradicts` (yielding `contested`); distinct co-located entities use distinct landmark-qualified keys.
3. **Two-strength `depends_on`, `AltSupport`, and acyclicity (`#1020`, `#1022`, `#1023`):**
   - **Fact-ID pin:** follows verified 1-to-1 same-reading `restated` chains silently in gate and export; `changed`, `corrected`, `ended`, `retracted`, `narrowed`, N→1 merge, or `contested` invalidates the pin on the pre-update snapshot.
   - **`state_key` pin:** stays quiet across `restated`, `changed` toggles, and `contested` readings (because a contested key still has active readings); invalidates **only when no active or contested reading for that key exists on the surviving timeline** (`#1022`, `#1023`).
   - **Surviving-timeline acyclicity:** the effective `depends_on` graph (fact-ID targets → that fact; `state_key` targets → surviving timeline's current active or contested reading(s) of that key) must be acyclic.
   - **Conditional Invalidation Closure (`AltSupport`):** flags `needs_review` only when independent alternative support is empty; never auto-retires a dependent.
4. **Atomic live world-article repair & no-silent-omission guard (`#1020`):** When a live admission submission runs `supersede_fact(reason_kind="changed")` or `retire_fact(reason_kind="ended")` on a world-bound fact cited by a current world article, the same submission must update the affected citing world-article claim block(s) so no stale world-state citation remains. Editing or revising a world article cannot silently drop a still-active world-bound fact unless another current world article cites it or the fact ends/is superseded/retracted in the same submission.
5. **Six autonomous hygiene safe-merge invariants (`#1023`):**
   1. Autonomous merge inputs must be current, uncontested, unkeyed, game-wide facts with identical `scope`, `statement_kind`, `anchor`, and byte-equal `when`.
   2. Merged output preserves the full citation union, all outgoing `depends_on`/`contradicts` links outside the merged inputs, and all citing articles.
   3. **Close `check.py:392-396` contested-supersession hole:** `restated` supersession/merge rejects any input that is `contested` in the pre-update snapshot.
   4. Reject autonomous N→1 merges whenever any current record in the pre-update snapshot holds an inbound fact-ID `depends_on` reading pin to any merged input.
   5. `remap_citations` permits N→1 restated merges (`from: [id1, ...]`) strictly for article claim citations (`body[*].facts`), never for `depends_on`.
   6. Surviving-timeline `depends_on` acyclicity holds after merge.
6. **Autonomous hygiene boundary & Kinds 6–7 structural rejection (`#1020`, `#1022`, `#1027`):** The gate structurally rejects Kinds 6–7 in every session (live admission, grooming, and `hygiene`) via the closed five-value `statement_kind` enum (retiring `strategy`); `statement_kind == "synthesis"` requires ≥1 `depends_on` link, and `statement_kind == "state"` requires world binding and `state_key`. When `session_kind == "hygiene"` (interleaved autonomous grooming), `check.py` additionally rejects retiring any active world-bound fact, `corrected` or `changed` supersession, altering a keyed fact's current reading via merge, or dropping an active world fact from articles. Curator prompts reinforce descriptive reserves, open-problem gaps, and source-linked lessons without Kind 6–7 prose.

### 2.2 Deterministic hygiene worklist & pinned cutoff (`harness/curator/hygiene.py`, `#1023`)

- Reads the pinned active index only (never dumping full raw `facts.jsonl` into model-facing workspaces, coordinating with `#1027`).
- **Pinned advisory article-size cutoff:** **`8,192` UTF-8 bytes (`8 KiB`)** of canonical serialized article JSON (`len(canonical(article).encode('utf-8')) > 8192`), paired with `CUT_BRIEFING_CHARS` (`24,000` chars) comparison and bibliographic coupling (`>50%` shared-fact overlap of the smaller article). Zero hard gate cap on article size or tag/subject cardinality (`R-CONTROL-BLOAT`); per-record 8-tag cap stays.
- Typed-incidence signals (`harness/curator/type_usage.py` + `hygiene.py`): per-tag and per-subject `df/N` with majority flag at `df > N/2`, tag-vs-scope overlap, chronological world→world `see_also` chains, exact All-Pairs IDF-weighted word + char-trigram similarity with high-DF template stripping (`df > 0.20N`) and asymmetric containment filtered by mechanical `cannot-link` rules (including same-frame `#1020` nogoods for duplicate and key-alias candidates, differing `scope`/`when`/`statement_kind`/`anchor`, or `contradicts`), optional shared-source co-witness annotations, separate `potential_contradiction` section, and non-destructive `#1020` key-alias candidates.

### 2.3 Retrieval (`harness/player/knowledge.py`, `#1023`)

- **Ship unconditionally:** keep `bm25_1hop` and `_fold`; enforce deterministic pre-read lifecycle/lineage filtering (excluding superseded/retracted/ended/shadowed while preserving current `contested` with status markers and conflict links); exclude `contradicts` from 1-hop propagation while continuing to ignore `shadowed_by`; in `_graph()`, resolve `depends_on` targets that name a `state_key` to every delivered world fact carrying that `state_key` (adding undirected 1-hop edges between the dependent record and those current reading(s)); index `when` in the text tier (`×1`) and resolved `anchor_display` in the tags tier (`×2`, never raw keys); keep `id`, `state_key`, `statement_kind`, and `clock_label` display-only; add zero-hit-only char-trigram fallback (`via: "fuzzy"` in `player-knowledge/4`); deduplicate `tools/knowledge_retrieval_benchmark.py`'s hop code to call production code directly.
- **Benchmark-gated candidates (adopt only on passing paired `$0` replay against `#1046` baselines with zero regression on `#896-b v91` and `#889 v17`):**
  1. Query-matched claim snippets on article hits (tested directly against the `#998` `gold_article_snippet_pass` baseline of `0/4` on `v97` and `v101`).
  2. Excluding/down-weighting world→world chronological `see_also` links.
  3. Optional single normalized hop (only if needed after authoring fixes).
- **Sealed `#998` benchmark continuity after Batch 1:** `tools/player_host_replay_benchmark.py` reads sealed `#998` `curator-knowledge/4` tags via `export_sealed_v3_tag` without calling the live exporter. When Batch 1 bumps `delivered-knowledge/4`, `tools/knowledge_retrieval_benchmark.py` projects sealed `#998` `delivered-knowledge/3` snapshots in memory to `delivered-knowledge/4` inside the benchmark only (`_project_v3_to_v4`, mapping `claim_kind` → `statement_kind`, `when.note` → `when`, omitting `evidence_basis`/`condition_unverified`, adding `frame_clocks: {}`, and assigning synthetic `state_key: f"key-{id}"` on `state` facts) so `production.Knowledge.from_dict()` runs paired `$0` replays directly on `#998 v97`/`v101`.

---

## 3. Complete Batch 1 caller, spectator, and fixture inventory

Verified by read-only `git grep` at `a3d43c9d`:

- **Schemas (2):** `schemas/curator-fact.schema.json`, `schemas/curator-submission.schema.json`.
- **Curator core & gate (7):** `harness/curator/check.py`, `harness/curator/knowledge.py`, `harness/curator/gate.py`, `harness/curator/validate.py`, `harness/curator/session.py`, `harness/curator/type_usage.py`, plus new `harness/curator/hygiene.py`.
- **Exporter & live curator host (5):** `tools/knowledge_export.py`, `tools/curator_host/live_runner.py`, `tools/curator_host/prompt.md`, `tools/curator_host/grooming.md`, `tools/curator_host/test/host.test.mjs`.
- **Player readers, benchmarks & tools (11):** `harness/player/knowledge.py`, `harness/player_view.py`, `harness/player_tools.py`, `tools/player_host/knowledge.mjs`, `tools/campaign_player.py`, `tools/memory_screen_checks.py`, `tools/memory_measure.py`, `tools/knowledge_retrieval_benchmark.py`, `tools/player_host_replay_benchmark.py`, `tools/recurrence_research/trial.py`, plus `harness/evaluation/core/host.py`.
- **Spectator projections & web UI (5):** `harness/viewer/delivered.py`, `harness/viewer/knowledge.py`, `web/app/memory.js`, `web/app/records.js`, `tests/fixtures/spectator/synthetic.py` (and regenerated `tests/fixtures/spectator/knowledge.json`).
- **Fixtures (45 JSON files):** `tests/fixtures/delivered-knowledge-3/` (`8` valid + `34` invalid, migrated to `delivered-knowledge-4/` with `old-schema-v3.json` negative fixture), `tests/fixtures/empty-delivered-knowledge.json` (`1`), `tests/fixtures/player-knowledge-3/` (`2` files, migrated to `player-knowledge-4/`), plus JS replay helper `tests/fixtures/combined_rehearsal_replay.mjs`.
- **Python & Node test suites (20+):** `tests/synthetic_knowledge_repo.py`, `tests/curator_stand_in.py`, `tests/test_shared_shapes.py`, `tests/test_curator_gate.py`, `tests/test_curator_session.py`, `tests/test_curator_runner.py`, `tests/test_curator_groom.py`, `tests/test_curator_host.py`, `tests/test_knowledge_export.py`, `tests/test_player_knowledge_query.py`, `tests/test_player_host_contract.py`, `tests/test_viewer_api.py`, `tests/test_viewer.cjs`, `tests/test_campaign_player.py`, `tests/test_campaign_run.py`, `tests/test_evaluation_delivery.py`, `tests/test_evaluation_memory_screen_checks.py`, `tests/test_knowledge_retrieval_benchmark.py`, `tests/test_player_host_replay_benchmark.py`, `tests/test_wave4c_combined_rehearsal.py`, `tests/live_curator_stand_in_run.py`, `tools/player_host/test/{delivery-scenario.mjs,host-scenario.mjs,knowledge-delivery.test.mjs,live-knowledge-update.test.mjs,context-cut.test.mjs}`.
- **Active/proposed docs migrated in Batch 1:** `docs/contracts/curator.md`, `docs/contracts/player-host.md`, `docs/contracts/player-ports.md`, `docs/contracts/spectator-view.md`, `docs/contracts/evaluation-record.md`, `docs/contracts/measurement-tools.md`, `docs/components/curator.md`, `docs/design/bounded-program-interface.md` (`proposed`), `docs/player-guide.md`, `docs/overview.md`, `docs/architecture.md`, `docs/operations/migration.md`, `tools/player_host/README.md`.

---

## 4. Five-session `#963`+`#998` archive cutover plan

Approved by owner decision ([`#archive-index-adds-963-and-998-sessions`](../decisions/owner-decisions.md#archive-index-adds-963-and-998-sessions)). All five cited sealed sessions share the exact version tuple `campaign-run/13`, `campaign-receipt/7`, `player-driver/7`, `player-host/12`, `host_telemetry: 12`, `campaign-watch-terminal/4`, `delivered-knowledge/3`:

| Session ID | Study | Run path | World | Lineage |
| --- | --- | --- | --- | --- |
| `3bf4413b14c83ceff112ca69a99e2715` | `wave3-wave4-validation-963` | `run` | `campground-wave34-validation` | `null` |
| `088ba6385ed4d42f6e728ad34d8fe943` | `multi-day-standard-build-998-admission-01` | `run` | `campground-standard-multi-day` | `campground-standard-multi-day` |
| `f91a383e469ae6722febb75cf90a7bbd` | `multi-day-standard-build-998-admission-02` | `run` | `campground-standard-multi-day` | `campground-standard-multi-day` |
| `f0e2b12efcfa5d83de53b49776897fdf` | `multi-day-standard-build-998-admission-03` | `run` | `campground-standard-multi-day` | `campground-standard-multi-day` |
| `a6979727b98c9fde6e8e0f502fea128d` | `multi-day-standard-build-998-admission-04` | `run` | `campground-standard-multi-day` | `campground-standard-multi-day` |

- **Why the two-step cutover:** During Batch 1, `campaign-run/13` and `player-host/12` remain the current manifest and host schemas (so `data/evaluation/archive-sessions.json` cannot yet list `campaign-run/13` as an archived combination without duplicating current versions), whereas `delivered-knowledge/3` is superseded by `delivered-knowledge/4`.
- **In Batch 1 (`delivered-knowledge/4`):** `harness/viewer/knowledge.py` defines `ARCHIVED_DELIVERED_V3_SESSIONS = frozenset({...})` holding these exact five session IDs (imported by `harness/viewer/delivered.py`). Current runs read `delivered-knowledge/4`; those exact five sessions retain read-only `delivered-knowledge/3` spectator projection; any unlisted `delivered-knowledge/3` file returns `unsupported`.
- **In Batch 2 (`campaign-run/14`, `player-host/13`, `player-host-inputs/5`):** `data/evaluation/archive-sessions.json` and `harness/evaluation/core/sources.py` (`ARCHIVE_COMBINATIONS`) add the exact `campaign-run/13` + `player-host/12` combination for these five sessions. `harness/viewer/knowledge.py` deletes `ARCHIVED_DELIVERED_V3_SESSIONS` and replaces the single `ARCHIVED_SNAPSHOT` tuple with a per-manifest snapshot table mapping archived `campaign-run/13` runs to `('player-host-inputs/4', 'delivered-knowledge/3')` and older archived runs to `('player-host-inputs/3', 'delivered-knowledge/1')` (with `campaign-run/12` staying in `UNREAD_SNAPSHOT_MANIFESTS`). Unlisted `campaign-run/13`, `player-host/12`, or `delivered-knowledge/3` runs are rejected.
