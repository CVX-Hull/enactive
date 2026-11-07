---
owner: lead
status: historical
date: 2026-11-07
scope: Audit #400 of docs, design, code, tests, controls and tracker against the charter principles, standards, controls, storage formats and discoverability at main bd549ca
review_trigger: None; dated record
---

# Standards, storage and discoverability audit (#400)

On 7 November 2026 the lead audited `main` at `bd549ca` through eight lenses. Each
lens was a clean-context, read-only reviewer with a bounded brief. The lead checked
every finding against the files before acting on it, and overrode or narrowed a
finding where the issue history or the code disagreed with it. Spend was $0 on
models or gameplay, and no game was launched. The tracking issue is
[#400](https://github.com/CVX-Hull/enactive/issues/400). This record is the
disposition ledger.

## Result

- **No ADR006 boundary violation.** `harness/computer/` and the native bridge carry
  no game, menu, item or needs semantics, and the shared player code carries no CDDA
  semantics. The ADR008 isolation contracts hold. No tracked file contains personal
  emails or local user paths.
- **The defects were drift, not design.** Pages that still described retired
  machinery as current. Contracts that omitted two persisted receipt kinds and the
  internal envelopes. Control follow-ups that pointed at closed issues. Nine pytest
  assurance markers no test used. One evaluator archive reader without its session
  gate. And no test of the runtime's original-deadline expiry path.
- **Numbers did not drift, but nothing would catch it if they did.** About 40
  hand-copied cells in `development-runs.md` matched their sources, and both
  generated metric tables reproduced byte for byte. But the sources are git-ignored,
  so a clone can verify none of them.
- **Size is not the problem; role is.** 79% of the 51k Markdown lines are dated
  historical records off the current reading path. The current core path is about
  900 lines. The real defect is one active page (`development-runs.md`) that holds a
  dated run log, and the same results told in up to four current pages.

| Lens | Findings | Fixed | Filed for owner decision | Filed or deferred | Rejected |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 Principles | 11 | 8 | 2 (#403) | 1 (#404) | 0 |
| 2 Standards against code | 13 | 8 | 0 | 5 (#404) | 0 |
| 3 Controls | 14 | 13 | 0 | 1 (#404) | 0 |
| 4 Architecture and design | 20 | 17 | 0 | 3 (#404, #405) | 0 |
| 5 Discoverability | 16 | 10 | 4 (#401, #402) | 1 (#405) | 1 |
| 6 Size | 6 | 2 | 3 (#402) | 0 | 1 |
| 7 Storage format | 6 | 2 | 4 (#401) | 0 | 0 |
| 8 Tracker | 16 | 15 | 0 | 1 (view settings) | 0 |
| **Total** | **102** | **75** | **13** | **12** | **2** |

A finding that more than one lens raised is counted in each of those lenses.

## Owner decisions

Each issue states the options, cost, a recommendation and what agreement authorizes.

- [#401](https://github.com/CVX-Hull/enactive/issues/401): track run ledgers as
  schema-checked data, and generate the run tables from it. Recommended: a versioned
  per-admission ledger under `data/evaluation/`, with generated table blocks and the
  existing staleness check, backfilled before any dev-loop worktree cleanup.
- [#402](https://github.com/CVX-Hull/enactive/issues/402): a role rule (active pages
  hold no dated run records) plus a generated dated-record index, instead of a size
  threshold. Recommended: split `development-runs.md` into its current method and two
  dated records, with no content deleted.
- [#403](https://github.com/CVX-Hull/enactive/issues/403): the evaluator's closed
  archive readers and the additive `context-manifest` event under S-MIGRATION.
  Recommended: a narrow written exception rather than converting retained evidence.

## Disposition ledger

Fixes landed in the audit's documentation PR (docs) and code PR (code), both
referencing #400.

**Lens 1, principles.**
1. The evaluator's `campaign-run/4` archive reader: owner decision, #403.
2. `campaign-watch-terminal/2` accepted for any run: fixed (code). Gated to listed archive sessions, with a rejection test.
3. `context-manifest` as an additive event inside telemetry v3: owner decision, #403.
4. The overview and work map dropped the "screen, not a qualification" caveat: fixed (docs).
5. The overview's spectator row understated reader validation: fixed (docs).
6. Architecture listed no coupling, although ADR006 points to it: fixed (docs). Coupling ledger added.
7. to 9. Stale docstrings in `tools/evaluate.py`, the CDDA binding and `harness/viewer/pause.py`: fixed (code).
10. ADR008 items were ordered 1–6, 8, 7: fixed (docs).
11. ADR008 claims the binding fails closed on a UI hash change, and no such check exists: filed, #404.

**Lens 2, standards against code.**
1. No test of `OperationExpired` (original-deadline expiry before or during dispatch): fixed (code), with controlled-clock tests.
2. Same as lens 1, item 2.
3. No test that evaluation and the viewer leave run-directory inputs unchanged: fixed (code).
4. Persisted and internal schemas missing from any contract: fixed (docs, computer-control contract).
5. and 6. Dead functions `read_sources` and `program_result_schema`: fixed (code).
7. `tests/computer_pipeline_check.py` unreferenced: fixed (docs, testing lane and C-NATIVE).
8. to 11. and 13. Duplicate SHA-256, percentile, JSON-reader, host-trace and time-parsing helpers: filed, #404.
12. Same as lens 1, item 7.

**Lens 3, controls.**
- F1. Gateway Pause and supervision had no control mapping: fixed (docs, C-RUNTIME evidence).
- F2. Follow-ups pointed at closed #75, #176 and #284: fixed (docs).
- F3. Nine unused assurance markers, and a stale sentence about assurance groups: fixed (code removes the markers; docs fixes the sentence).
- F4. C-BOUNDARY said four import contracts when there are eight, and two contracts had no negative test: fixed (docs text; code adds the negatives).
- F5 to F7. C-BOUNDARY, C-PORTABLE and C-RELEASE last exercises predate current contracts: fixed by recording current exercises at the audit close-out.
- F8, F9, F11 and F12. Native checks, build tool, adapter runner, redirect-stub links and the control module: fixed (docs).
- F10. The wire test was unmapped: fixed (docs). The other modules named are optional and carry no control claim.
- F13. The retired control still had a review date: fixed (docs).
- F14. Governance checks that a file exists, not that git tracks it: deferred, #404, since CI on a clean checkout catches it.

**Lens 4, architecture and design.**
- Fixed (docs):
  - 1 and 2: receipt variants and internal envelopes;
  - 3 to 5: three stale "proposed" pages;
  - 6: alt text contradicting current diagrams;
  - 9 to 11: retired code described as current;
  - 12 to 14: ADR status, delivery and scope;
  - 15: Terra as a diagnostic route;
  - 16: viewer 502/503;
  - 17: the archive exception in evaluation inputs;
  - 18: research pages;
  - 20: the bookmark name collision.
- 12, ADR002 part: kept historical, not superseded. Its local serialized
  bridge-and-service decision still describes the current channel in outline, and
  the charter (lines 60–61) cites it as a current technical decision. The charter's
  wording is owner-held; the lead raised it on #400 rather than editing the charter.
- 7 and 8. Orphaned or misplaced diagrams: filed, #405.
- 19. No owner for the second trace-analysis path: filed, #404.

**Lens 5, discoverability.**
- Fixed (docs):
  - 1: the walkthrough marked historical;
  - 2: an evidence route to the latest runs;
  - 5: stale ownership claims about closed issues;
  - 6 and 8: status of proposed and research pages;
  - 10: route;
  - 12: broken anchor;
  - 14 and 15: contract index and authority links.
- 13. The player-host README is outside the metadata check: fixed (code). CLAUDE.md, the PR template and the vendor provenance note are not owned documentation pages, so that part is rejected.
- 3, 4 and 7. Duplicated result narratives and the run log in an active page: owner decision, #402.
- 9. The chained-admission procedure lives in untracked tooling: owner decision, #401.
- 16. Retired contracts are not listed in the contract index: filed, #405.
- 2 (README part): rejected. The README states the stable boundary and links the overview, which owns results.
- 11. ADR008 deferral links in work.md: rejected. They are pointers under ADR008's own wording, kept at the #399 review.

**Lens 6, size.**
- F1, F2 and F4. Run log in an active page, no dated-record index, and generated evidence lists in `controls.md`: owner decision, #402.
- F3. Dated research pages marked active: fixed (docs).
- F6. The player-host README had no frontmatter: fixed (code).
- F5. 7.1 MB of fonts embedded in the SVGs: rejected. It is deliberate under ADR004, since an SVG shown through an image tag cannot load external fonts.

**Lens 7, storage format.**
- 1 to 4. Hand-copied cells from untracked ledgers, tables that cannot be regenerated from a clone, self-declared schema ids that are defined nowhere, and ledgers in different shapes: owner decision, #401.
- 5. No hashes for the #382 evidence frames: fixed (docs).
- 6. The two "setup" columns use different units: fixed (docs).

**Lens 8, tracker.**
- Fixed on GitHub:
  - the views table now matches the four live views, and the Needs attention filter is documented as it actually works;
  - the Project README links the authority contract and the views;
  - eight assignees;
  - the #400 selection checkpoint;
  - triggers for #385 and #386;
  - current-state notes on #136, #145, #164 and #359;
  - 34 Finished dates, taken from the issues' completion dates;
  - the #42 parent, plus sub-issue and dependency links;
  - a keep-open reason and closing trigger on #332;
  - label hygiene.
- 16. Visible fields and sorting in the Backlog and Current iteration views: deferred. GitHub's API cannot edit view settings, so this is a manual step in the Project UI.

## Method and limits

- **Commands.** The lenses ran the fast checks, governance, and focused non-native pytest suites: 120 tests plus 240 subtests, then 339 tests. The player-host Node suite passed 194 of 194. All of these passed at `bd549ca`.
- **Not run.** The full suite, native checks, headless-browser suites and diagram rendering were not run in the lenses. Protected CI ran on each fix PR.
- **Limits of the dead-code check.** It used grep reference counts because vulture is not installed, so names referenced only by tests and unused JavaScript exports were not checked.
- **Limits of the drift spot-check.** It covered about 40 cells, not every number.
