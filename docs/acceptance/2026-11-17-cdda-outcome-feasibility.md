---
owner: lead
status: historical
kind: measurement
date: '2026-11-17'
scope: 'Fixed-sample visible outcome feasibility and owned worker-source retirement; descriptive agent inspection, no reader qualification or game execution'
---

# CDDA outcome feasibility

## At a glance

**Defer a task-progress AND alive reader target.** The fixed pairs contain useful
visible death and live-screen boundaries, but do not establish an answerable common
before/after task-progress bundle. In particular, a crafting message or starting
inventory alone does not establish progress over the assigned interval. This is a
stop on source support, not evidence that the task is impossible. No reader path,
accuracy, efficacy, power or independent-world replication is justified. #681 needs
rescoping or new source and label support before qualification; #677 can reuse these
development cases without gating #457.

## Assignment and exposure

Before image inspection, the lead verified and froze
[`assignment.json`](assets/2026-11-17-cdda-outcome-feasibility/assignment.json)
(SHA-256 `966e35fbb49e7ccce4b4e9100c2913d32fa41404b06a1722dc8abd4698d6e75c`).
It records all 20 exposed source IDs, source metadata hashes and paths, original
operation bounds and exact pair assignments. Its source paths are relative to the
primary checkout, not this worktree. The initial engineering-agent inspection opened all 20 assigned images once,
with no substitutes. Independent agent review reopened six of those same images:
`d073e0e4acac4303841bf92e0e3155c8-313`,
`d073e0e4acac4303841bf92e0e3155c8-6018`,
`bf01a9f1ca634ea63144b01cd8debe8d-12318`,
`f37efc17970589e90aff3c73d3742a89-336`,
`f37efc17970589e90aff3c73d3742a89-4195` and
`847fa1fdd004ec904c646f6fea299f4a-9307`. These are 26 image views of
20 unique assigned sources, not additional cases or independent labels. No other
images were opened. The lead checked
each assigned image file against its listed hash. The generator is retained in the sealed `cdda-outcome-feasibility`
evidence entry as `assign.py`; it joins tracked `data/evaluation/runs.jsonl`
and `run-metrics.jsonl` on session and run and uses the existing closed
`harness.trace.projection._steps` reader against indexed session stores. It orders
operations by wall time and operation ID, counts completed `input` operations across
actors, and uses their attached sources. Source hashes come from sealed metadata.
Reproduce from this checkout with `PYTHONPATH="$PWD" "$(git rev-parse --git-common-dir)/../.venv/bin/python" .runtime/feasibility/assign.py` after restoring the retained generator and access to the primary store; compare the resulting hash.

The first censored and first died tag in lexical run order per development family
were selected, deduplicated, with the tags used only for unqualified stratification.
Study 642 has no died tag; study 651 runs 20 and 29 have null tags and are
unclassified. No stratum was filled by replacement. Each admission has first/last
retained-operation sources and input 10/100 sources; all five reached input 100.
The two pairs of each admission overlap in history and are not independent trials.
Earlier inspected #397 `sd1a2` frames remain development anchors, not blind or held
out. No #382/#522 pixels, save contents or engine state were read.

## Fixed-pair coverage

The suffixes below refer to the complete source IDs and hashes in the assignment.
The descriptions are tool-assisted engineering-agent observations, not human
expert or qualified gold labels. “Unknown” includes lack
of identity or an adequate task baseline; it is not failure or death.

| Admission and pair | Baseline → endpoint (capture suffix) | Visible evidence and provisional coverage |
| --- | --- | --- |
| 397 sd1a1 first/last | 2 → 18452 | New-game menu → load menu listing Morgan Hale. Endpoint alive and task change unknown; listed save is not proof of living state. |
| 397 sd1a1 input 10/100 | 336 → 4195 | Achievement popup timestamps reaching a refugee center at day 61 8:00 → live screen at lake shore day 61 8:09:18 and water-filling message. Boundary: event timestamp is not a baseline clock or proof of a predeclared task change; endpoint identity not visible. |
| 397 sd1a7 first/last | 2 → 12318 | Load menu → “In memory of: Morgan Hale” death screen. Visible death, a negative alive component; task change unknown. |
| 397 sd1a7 input 10/100 | 454 → 5132 | Map travel confirmation → fire-ring construction menu showing 1 of 20 rocks and missing digging tool. Boundary: option and unmet requirements do not show a completed ring; identity, task change and comparable clocks unknown. |
| 642 delivery first/last | 2 → 9735 | Load menu → title/exit screen. Alive and task change unknown; orderly stop is not death. |
| 642 delivery input 10/100 | 313 → 6018 | Follower view → pickup menu with roasted cattail and a visible crafting message. Positive *event cue*, but baseline does not establish its absence or the message's interval, and ground item is not proof of possession; bundle and identity unknown. |
| 651-01 first/last | 2 → 9307 | Load menu → title/exit screen. Alive and task change unknown; censoring is distinct from death. |
| 651-01 input 10/100 | 357 → 5667 | Consume menu with existing food and water → live screen with corpse-pulping message. Boundary: starting stock and endpoint message do not establish a predeclared before/after bundle; identity unknown. |
| 651-14 first/last | 2 → 7125 | Load menu → “In memory of: Morgan Hale” death screen. Visible death, a negative alive component; task change unknown. |
| 651-14 input 10/100 | 522 → 5547 | Shelter view → another shelter view with dropped planks in message. Boundary: no supported before/after task predicate or visible named identity; progress unknown. |

The death screens supply two negative alive examples, both in the same related
source cluster. Live play views show candidate alive cues, but their assigned frames
do not visibly name the controlled survivor, so the strict identity rule leaves the
alive label unknown. No positive composite or supported negative task-progress case
is established. Clock and travel are separate: the achievement popup and later clock
are not two comparable clock readings; map confirmation is not travel completed.
No distance or elapsed-time estimate is inferred. Menu, occlusion, unknown identity,
failed start, budget stop and censoring remain separate reasons, not death labels.
None of the assigned cases is a verified failed start; no failed-start regime is
manufactured.

## Dependence and next protocol

Both #397 admissions are ledger lineage L1. The start manifests of 642, 651-01
and 651-14 each cite `397-seven-day`, lineage 397 and archive manifest SHA-256
`2487838cdb3218e00d419c7cede6d31923ee5f6efc843718ad3c3853833d89d2`.
Their complete start file/hash maps have the same canonical digest
`04266d26eb8217964795b7ab2475a188e6e5496fb42d548595d0192a8a9642ae`;
their manifest hashes are respectively `a2be7aeb45e53f01e17c356b405c63b65eb625f0a6e23316e5e5a93e11c712fd`,
`558550c3384d24708f76b22fd5636a45da6d10885a88e40a67077d7eb5d26dd1`, and
`46076f016c5f8a5d3aae1f3201d34df95ff25c2b40a275030097d009f6fda7e4`.
This is one conservative related world/lineage cluster, not five independent worlds;
exact parent moment is not established. Morgan Hale is named by the two death
screens and prior development anchor; visible identity for other endpoints remains
unknown. Other profiles and survivor identities are not established from these pairs.
Uninspected groups cannot be asserted to be independent or final holdout; a later
protocol must identify genuinely uninspected, independent selection and final groups.

The fixed provisional development codebook is: (1) alive only when the assigned
endpoint visibly identifies the survivor and shows a living state; dead only on a
visible death of that survivor; otherwise unknown; (2) progress positive only when
a predeclared task predicate is visibly absent or incomplete at baseline and achieved
at endpoint; negative only when both views resolve the same predicate as not achieved
at endpoint; boundary for partial or ambiguous evidence and unknown if the predicate,
identity, baseline or endpoint cannot be resolved; (3) clock elapsed and landmark/map
travel require comparable visible observations at both endpoints. An isolated event
message is a cue, not proof of a change during the assigned interval. For the provisional composite,
a known death gives a negative composite regardless of unresolved task progress;
both supported progress and alive are needed for a positive. Keep unresolved task
progress separately even when the composite is negative. These rules are for development and are not qualified labels.

For a future qualification proposal, freeze task predicates and visible baseline,
endpoint, identity and finite allowance before outputs; independently label positive,
negative, boundary, unknown, occluded, menu and failed/censored examples. Retain all
assigned starts and failures. A composite is positive only if both progress and alive
are supported. Known death is negative; otherwise unresolved progress, identity or
visibility remains unknown. Report source-starts equally within each
predeclared profile and profiles equally, cluster shared world/lineage/parent/copy
relationships, and give separate unknown/failure and censoring sensitivity results
without silently dropping assignments. The protocol must predeclare how each failure
enters its estimand and sensitivity bounds before qualification; this record does not
fix a final estimator.

The next work must identify an observable task bundle, comparable before/after capture
protocol, identity support, positive and negative examples and independent source
acquisition/label support. Price those, failures and independent labels with the
existing [role/price worksheet](2026-11-16-cdda-recurrence-preparation.md#proposed-price-and-remaining-decisions)
before any owner decision; no new budget is opened here. No experimental model/provider API request, native play, source acquisition or
held-out inspection ran.

## Owned source retirement

The goal created exactly two project-local Git-linked worker checkouts:
`.runtime/worktrees/delivered-knowledge-spectator/` and
`.runtime/worktrees/cdda-outcome-feasibility/`, from retained base
`41f08c6c102fbdb0b39fe0ca3865f1bae2ec8349`. Briefs gave each one writer and disjoint
ownership; neither launched a game/provider or installed dependencies. The primary
checkout and all saves, builds, dependencies and canonical experiment evidence stay.

The app inventory identifies both as `linked_worktree`. Its attach operation reports
success, but its archive operation twice returned “This worktree is not attached to
the current task.” These are this goal's Git-created checkouts, not app-managed,
primary or foreign worktrees. Native Git therefore preserves their inspected source
before retirement: archival commits `aae970ae40732fe346411eacc32e8c4a26c0189e` and
`d7aa74ebf15c659eb56b28448abd3c15ef0d2324`, with verified compact bundles of 14,533
and 10,829 bytes, respectively. Both require the retained base above; neither is a
public delivery branch. This is the actual recovery route instead of the app archive
anticipated by the spectator record. No custom history framework is added.

The sealed `cdda-outcome-feasibility` entry retains the metadata-only generator,
frozen assignment, check/review context and both source bundles with ownership/hash
receipts. Full sealed hash verification passed. Git removed both clean linked worktrees and
their private branches after verifying the bundles and all research raw copies.
The two source archival commits remain recoverable from the sealed bundles.
Routine local checker/browser outputs are pruned only with checks stopped.
Protected CI, merged-main verification and final tracker reconciliation remain
separate required delivery checks; their results belong to the pull request.

The retained entry has seven files / 73,511 bytes. Its `feasibility/` part stages
the worker’s three raw files plus the lead’s review-disposition context through
`.runtime/outcome-feasibility/`; `worker-source/` stages two bundles and their receipt
through `.runtime/source-retirement/`. These staging directories and the spectator’s already sealed staging duplicate
were retired: 44 files / 4,314,416 bytes in total. No canonical input was removed.
