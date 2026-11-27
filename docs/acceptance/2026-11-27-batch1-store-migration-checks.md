---
date: 2026-11-27
owner: lead
status: historical
kind: measurement
scope: >-
  Batch 1 store S-MIGRATION (#1020, #1021, #1022/#1024, #1023) pre-merge
  evidence: paired $0 #1023 retrieval candidate adjudication across sealed
  #896-b v91, #889 v17, and #998 v97/v101 (adopting query-matched article
  claim snippets and rejecting world-see_also exclusion and normalized 1-hop)
  plus bounded standing <= $1 C-MODEL-CHECK ($0.3909 total spend across two
  sequential #998-a01 curator admission windows on openai/gpt-6.1-terra via
  OpenRouter, zero CDDA launches).
---

# Batch 1 store migration checks: paired `$0` `#1023` retrieval adjudication and `C-MODEL-CHECK`

## At a glance

- **Paired `$0` `#1023` retrieval candidate adjudication:**
  - **Adopted — Candidate 1 (query-matched article claim snippets):** When an article hit's body claim matches strictly more query terms than `lead`, `Knowledge.query()` emits that claim as the hit snippet instead of the generic lead. On the sealed corpora (`#896-b v91`, `#889 v17`, `#998 v97`, `#998 v101`), Candidate 1 produces **zero ranking regression** (`v91` Hit@5 `1.000`, ArtRec@5 `0.858`, ArtMRR@5 `0.917`; `v17` Hit@5 `1.000`, ArtMRR@5 `1.000`) while lifting `#998` `top5_snippet_pass` from `3/4` to **`4/4`** and `gold_article_snippet_pass` from `0/4` to **`4/4`** on both `v97` and `v101`.
  - **Rejected — Candidate 2 (excluding world→world `see_also` edges):** Produced zero metric gain on any corpus (`v91` ArtMRR@5 `0.917`, `v17` `1.000`, `#998 v97`/`v101` `0.8125`).
  - **Rejected — Candidate 3 (normalized 1-hop `1/sqrt(deg_u * deg_v)`):** Regressed every corpus (`v91` ArtMRR@5 `0.917 -> 0.868` and ArtRec@5 `0.858 -> 0.738`; `v17` ArtMRR@5 `1.000 -> 0.900`; `#998 v97` `0.8125 -> 0.3125`, `v101` `0.8125 -> 0.3000`).
- **Standing `<= $1` `C-MODEL-CHECK` (curator prompt & `curator-submission/3` parser check):**
  - Ran two sequential sealed `#998-a01` admission windows (`steps 1..25` and `26..50`, zero CDDA launches) through the real macOS Seatbelt sandbox, `ModelProxy`, `tools/curator_host`, and `harness/curator/gate.py` on pinned `openai/gpt-6.1-terra` (Medium effort, OpenRouter).
  - **Result: PASS.** Total provider spend **`$0.39090715`** (`$0.19766455` + `$0.19324260`, within the `$1.00` standing `C-MODEL-CHECK` allowance), **`3/3` submissions published (`v0 -> v3`, `0` rejections, `0` stale records)**, and valid `delivered-knowledge/4` export (`19` facts, `4` verbatim `frame_clocks`).

---

## 1. Paired `$0` `#1023` retrieval candidate comparison

All runs used `tools/knowledge_retrieval_benchmark.py` (`knowledge-retrieval-benchmark/2`) on the sealed `#896-b v91` (20 queries), `#889 v17` (10 queries), and `#998 v97`/`v101` (4 pinned `#1046` probe queries) corpora, with the unconditional Batch 1 changes (`when` indexed at ×1, `anchor_display` at ×2, `contradicts` excluded from 1-hop, shadowed records excluded) held fixed:

| Variant | `#896-b v91` Hit@5 | `#896-b v91` ArtRec@5 | `#896-b v91` ArtMRR@5 | `#889 v17` ArtMRR@5 | `#998 v97` ArtMRR@5 | `#998 v97` top5 / gold-art snippet | `#998 v101` ArtMRR@5 | `#998 v101` top5 / gold-art snippet | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `#1046` baseline (`delivered-knowledge/3`, no `when` ×1) | `1.000` | `0.858` | `0.917` | `1.000` | `1.0000` | `3/4` / `0/4` | `1.0000` | `3/4` / `0/4` | Reference ([`#1046`](2026-11-27-store-migration-freeze-and-998-baselines-1046.md)) |
| Batch 1 unconditional only (`when` ×1, `contradicts` excluded) | `1.000` | `0.858` | `0.917` | `1.000` | `0.8125` | `3/4` / `0/4` | `0.8125` | `3/4` / `0/4` | Base |
| **Candidate 1: query-matched article claim snippets** | **`1.000`** | **`0.858`** | **`0.917`** | **`1.000`** | **`0.8125`** | **`4/4` / `4/4`** | **`0.8125`** | **`4/4` / `4/4`** | **Adopted** |
| Candidate 2: exclude world→world `see_also` | `1.000` | `0.858` | `0.917` | `1.000` | `0.8125` | `3/4` / `0/4` | `0.8125` | `3/4` / `0/4` | Rejected |
| Candidate 3: normalized 1-hop (`1/sqrt(deg_u * deg_v)`) | `1.000` | `0.738` | `0.868` | `0.900` | `0.3125` | `4/4` / `0/4` | `0.3000` | `4/4` / `0/4` | Rejected |
| Candidate 1 + Candidate 2 | `1.000` | `0.858` | `0.917` | `1.000` | `0.8125` | `4/4` / `4/4` | `0.8125` | `4/4` / `4/4` | Candidate 2 adds 0 |
| Candidate 1 + Candidate 2 + Candidate 3 | `1.000` | `0.738` | `0.868` | `0.900` | `0.3125` | `3/4` / `2/4` | `0.3125` | `3/4` / `2/4` | Rejected |

Note on `#998` `ArtMRR@5` (`1.0000 -> 0.8125`): the shift comes entirely from the unconditional `#1023` rule indexing `when` at ×1 across the `122` legacy `#998` facts carrying long prose `when.note` fields, which moved `wilderness-start` on `start-time` from rank `1` to rank `4` while keeping `Hit@5 = 1.000` and raising `gold_article_snippet_pass` from `0/4` to `4/4` once Candidate 1 was adopted.

---

## 2. Standing `<= $1` Batch 1 `C-MODEL-CHECK`

| Window | Sealed trace slice | Requests | Wall (s) | Provider spend (USD) | Submissions published / rejected | Published tip |
| --- | --- | --- | --- | --- | --- | --- |
| `w1-steps-1-25` | `#998-a01` steps `1..25` | `15` | `77.89` | `$0.19766455` | `2` / `0` (`initial` → `v1`, `skills` → `v2`) | `v2` |
| `w2-steps-26-50` | `#998-a01` steps `26..50` | `15` | `89.72` | `$0.19324260` | `1` / `0` (`campground` → `v3`) | `v3` |
| **Total** | **`50` sealed steps** | **`30`** | **`167.61`** | **`$0.39090715`** | **`3` / `0`** | **`v3`** |

Contract features exercised cleanly by the live curator model under `curator-submission/3` and `curator-fact/6`:

- **Five-value `statement_kind` (Kinds 1–5):** `6` `observation`, `3` `outcome`, `9` `state`, `1` `synthesis` (`0` Kind 6–7 `strategy`).
- **Keyed inertial fluents (`#1020`):** `10` distinct active `state_key` values (`campground-distant-food`, `campground-picnic-table`, `campground-start-site`, `campground-supply-summary`, `campground-table-supplies`, `francis-mills-world`, `rowan-carried-camp-supplies`, `rowan-skill-levels`, `rowan-vale`, `starting-tent-flap`).
- **Kinematic anchors & full-frame depictions (`#1021`, `#1046`):** `4` `anchor` links (`picnic-table-visible-items -> campground-picnic-table`, `rowan-carried-camp-tools -> rowan-vale`, `rowan-starting-skills -> rowan-vale`, `starting-tent-north-flap-open -> campground-start-site`) and `3` `depiction_source_id` pointers.
- **Two-strength `depends_on` (`#1022`):** `7` `depends_on` links combining both `state_key` entity-existence pins (`4`) and fact-ID reading pins (`3` on the `synthesis` fact `campground-observed-reserves`).
- **Sparse `frame_clocks` (`#1021`):** `4` verbatim HUD clock strings (`"Spring, day 61 8:00:00 AM"` through `"Spring, day 61 8:00:14 AM"`), validated through `tools/knowledge_export.py` into `delivered-knowledge/4` (`stale_records = 0`, `delivered_v4_valid = true`).
