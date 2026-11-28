# Grooming instructions

Start from the brief's **Grooming worklist** and **Hygiene worklist** instead of scanning the whole
store. They list records and advisory candidates deterministically from active records. Use
`knowledge/index.md` for the compact article list and per-world `state_key` index. Read individual
records from `knowledge/records/<id>.json` or with `run_workbench(["knowledge", "get", "<id>"])`.
Use `run_workbench(["knowledge", "search", "<query>"])` for `bm25_1hop` search.
Treat facts as descriptive hypotheses (Kinds 1–5 only; never Kind 6 recommendations or Kind 7
directives/plans).

## Session kind boundaries

- **`hygiene` (interleaved autonomous grooming):** text-only, strictly non-destructive cleanup.
  `view_frame` is unavailable. The gate
  rejects retiring any active world-bound fact, running `corrected` or `changed` supersession,
  merging or altering keyed or world-bound facts, or dropping any active world-bound fact from
  world articles. Only unkeyed game-wide facts with identical `scope`, `statement_kind`, `anchor`,
  and byte-equal `when`—and with zero inbound fact-ID `depends_on` reading pins—are eligible for
  autonomous N→1 `restated` merges.
- **`grooming` (between admissions):** may also resolve `contested` records with cited evidence
  and perform full structural cleanup, while preserving the same safe-merge invariants on N→1
  merges and introducing zero new stale citations. Use two or three batches of at most four
  frames when a repair needs images. The session has a 16-image-part cap, and the request byte
  budget may be reached sooner. Pixel-identical frames and frames beyond the cap return text
  pointers. Earlier images stay in context.

## Must clear

Every current record with non-empty `stale_citations` cites or `depends_on` a record (or ended
`state_key`) that is no longer current. Grooming/hygiene fails while one remains, and a submission
may never introduce a new stale citation.

- A `restated` supersession or safe N→1 restated merge: verify the replacement preserves meaning,
  then use `remap_citations` (`"from": ["<old_id>", ...]`, `"to": "<new_id>"`, `"in": [<slugs>]`)
  to update citing article claims cleanly.
- A `changed` or `corrected` supersession: rewrite affected article claims with `edit_article`'s
  `replace_claims`, copying `index`, `old_text`, and `old_facts` exactly.
- A narrowed fact: cite the child(ren) matching the article's scope via `replace_claims`.
- A retired fact (`wrong` or `ended`): remove or rewrite the claim so it cites only current facts,
  or retire the article (never silently dropping other still-active world facts).
- A stale `depends_on` link: repoint or drop it (`edit_article` for an article; `restated`
  supersession for an unkeyed fact).

## Advisory and structural hygiene

Review the deterministic **Hygiene worklist** sections:

- **Structural signals:** split oversized articles (advisory cutoff `8,192` UTF-8 bytes) into
  topical current-state articles; untangle high bibliographic coupling (`>50%` overlap); prune
  chronological world→world `see_also` chains; replace majority stopword tags (`>N/2`) or
  scope-overlapping tags using `retag` (at most once per submission).
- **Duplicate and containment candidates:** merge eligible unkeyed game-wide duplicates via
  `supersede_fact(reason_kind="restated")` preserving all citations and outgoing
  `depends_on`/`contradicts` links, then remap citing articles via `remap_citations` in the same
  submission. Never clear a `contested` record with `restated`.
- **Potential contradictions & key-alias candidates:** inspect evidence before acting; leave a
  draft if the available frames cannot decide.

Use `curator-submission/3` and `curator-fact/6`. Run `validate_submission` on every submission
before `finish`.
