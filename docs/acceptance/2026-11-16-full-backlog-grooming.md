---
owner: lead
status: historical
kind: review
date: '2026-11-16'
scope: 'Full review of 35 open Issues, native dependency/parent links and all 264 Project cards; Ready selection, issue reconciliation and owned routine cleanup. No runtime implementation or new study spend.'
---

# Full backlog grooming and cleanup

## At a glance

The review retains three Ready leaves, in recommended pull order:

1. [#463](https://github.com/CVX-Hull/enactive/issues/463), **Important**: implement
   the adopted curator/memory phase as one coordinated player-contract migration.
2. [#680](https://github.com/CVX-Hull/enactive/issues/680), **Follow-up**: repair
   structural scoreability in the existing prospective withholding simulator offline.
3. [#668](https://github.com/CVX-Hull/enactive/issues/668), **Follow-up**: prepare
   bounded CDDA source/packet feasibility and a conservative pilot price worksheet.

This is selection, not implementation or a new study authorization. No feature or
research leaf is newly promoted: the three already met the Ready rule, with #668
bounded more precisely. The remaining 22 leaves stay Backlog. Ten outcomes retain
their distinct Horizon fields. The new grooming leaf
[#683](https://github.com/CVX-Hull/enactive/issues/683) tracks this review only and
does not join the development queue. Subsequent scope and execution fields belong
to [Issues and the Project](../workflows/work-items.md).

## Evidence and coverage

Source snapshot: main `cf779eb6ed7cddbcc65f6259990deec90fa69e92`. The lead read the
open issue bodies, native parent/blocking graph, current rules and affected designs,
using four read-only sweeps for integration, research, tracker consistency and
cleanup. The lead verified findings against actual source and remote metadata.

`gh issue list --state open` returned 35 issues. GraphQL selected open issues with
parents, sub-issues and blocked-by/blocking links. Every open issue had exactly one
Project card and an appropriate parent, except the intended root #136. A separate
paginated read checked actual issue states for all 264 Project cards: no open issue
was Done and no closed issue had a non-Done populated status. No open PR, feature
branch or secondary Git worktree existed at the initial snapshot. The app artifact
inventory contained attached historical PRs and no managed worktree to retire.
The four saved Project view filters also match their contract: Current iteration
selects open Ready/In progress leaves, Backlog selects open Backlog leaves,
Direction selects open outcomes, and Needs attention selects open blocked/decision
items. Historical closed cards remain excluded without bulk rewriting their old fields.

No evidence justified closing an existing open item as implemented or duplicate.
In particular, #387 is the memory outcome under the larger curated-player #445;
the latter also owns programs and practice. Their nesting is useful, not duplication.
The CDDA-class charter direction remains; current research/play is CDDA only.

## Disposition of every reviewed issue

| Issue | Disposition | Reason or next trigger |
| --- | --- | --- |
| #25 | Backlog | Terra remains current; a cheaper-player trial needs settled memory/context, owner reopening and its own price |
| #42 | Backlog | Expectation field and its evaluator consumer must be shaped together after #463; no unused field added now |
| #136 | Outcome / Now | Player-owned campaigns; #463 is the next integration slice; current game scope clarified |
| #143 | Outcome / Next | Memory views follow #463/#457; program views need actual producers; #336 needs demonstrated friction |
| #145 | Outcome / Next | Adoption is decided, migration pending; the campaign remains separately frozen and priced |
| #164 | Outcome / Next | Responsiveness remains an unqualified aim, not a gate on current work |
| #177 | Outcome / Later | Programs follow memory/repository contracts; serialized runner/gate sequence retained |
| #191 | Outcome / Later | Preserve generic boundaries now; wider actual-game support is future work |
| #290 | Backlog | Attended real-host cases, operator consent and finite appetite remain unselected |
| #291 | Backlog | Other games deferred to a future version; no current game/build/task chosen |
| #309 | Backlog | No approved routing probe; memory/context first and a concrete failover trigger |
| #336 | Backlog | Recent trace investigations did not show the required navigation friction |
| #384 | Backlog | Intent implementation is inside #463; later cost/behavior measurement needs its own protocol/price |
| #387 | Outcome / Now | Memory delivery/store outcome remains incomplete while #463/#457/#664 are open |
| #441 | Backlog | Re-freeze a current-configuration fresh cohort after migration and owner repricing; no pooling old #397 |
| #445 | Outcome / Now | Memory first; programs/monitor and practice remain unadopted phases |
| #457 | Backlog | Belief-model decision remains open; consume merged #463 contracts and avoid competing gate schemas |
| #463 | Ready / Important | Adoption and cut deferral decided; coordinate all active producers/readers, focused checks and integrated regression |
| #464 | Backlog | Read-only memory views need #463/#457 data; reuse migrated projection cases and serialize viewer edits |
| #465 | Backlog | New program contract needs merged #463 and settled #457 repository/gate schema |
| #466 | Backlog | Capability slots follow #465; share the selected runner/replay cases |
| #467 | Backlog | Supervised asynchronous runs follow #465/#466; native runtime stays serialized |
| #468 | Backlog | Monitor follows #457/#466/#467/#469 and needs concrete anomaly evidence |
| #469 | Backlog | Fitting/probation follows #465/#467 and #457 later-trace gate tests |
| #470 | Backlog | Programs/monitor data and views first; a new priced study and adoption decision are still required |
| #471 | Backlog | Program views require #464 plus actual #467/#468/#469 output |
| #472 | Outcome / Later | Practice instance remains an owner decision; no second instance is authorized |
| #473 | Backlog | Practice decision and separately priced concurrency/determinism measurements required |
| #474 | Backlog | Practice-only port follows permitted #473 results and the practice decision |
| #664 | Backlog | Live-curator brief follows #463/#457; actual measurement requires a later priced package |
| #666 | Outcome / Next | Diverse-CDDA representation research; common preparation, qualification and method studies remain separate claims |
| #668 | Ready / Follow-up | One real-prefix packet cycle, score example and price worksheet; no model, game or general scoring framework |
| #677 | Backlog | Reuse #668 packets; matched belief-method comparison needs a finite priced replay protocol |
| #680 | Ready / Follow-up | Concrete reproduced sizing defect, bounded CPU-only repair, unchanged estimator and assignment |
| #681 | Backlog | Choose a feasible visible outcome after #668, then qualify its positive/negative/unknown support |

## Dependency, integration and testing decisions

Keep one active integration slice and at most two disjoint implementation workers.
Ready does not mean simultaneous ownership. #463 removes legacy memory/program
writes, adds intent/cites/hints and migrates source, schema, projections and readers
together. Its allowed reader paths now explicitly include the offline tools that may
consume changed active formats. Unsupported active stores are refused; historical
sealed evidence remains on the explicit evidence-reading path. No new belief model,
live curator, context cut or expectation field is smuggled into adoption.

#680 and #463 both touch the evaluation contract and may touch the same offline
reader. Serialize their integration rather than let separate workers edit that
boundary. Rebase and run relevant focused regressions when their actual combined
diff warrants it; do not repeat unaffected native/gameplay checks. #680 fixes the
old estimator's scoreability, not the different future representation estimand.
It is not a hard prerequisite to #668, #681 or #463.

#668 can prepare isolated research artifacts against a frozen source interface
with the lead's exact file assignment. Its brief is bounded to one manifest, one
real-prefix packet/cycle fixture, one deterministic all-assigned score reduction
and a role/resource/price worksheet. Unknown post-migration links remain unknown.
It specifies later calibration and reader reliability; it does not build a general
scorer, run a power grid or qualify outcomes. #681 owns outcome qualification after
source feasibility; #677 reuses these common packets for method comparison. There
is no need for a separate issue or collector for every missing measurement.

Later memory/program work shares real contracts and test setup:

- #457 settles the repository/gate after #463 and the belief decision. #465 follows
  that contract; #466 → #467 → #469 → #468 serializes shared runner/gate changes.
  #471 then reads actual data, before #470's priced study/adoption decision.
- #464/#336/#471 share viewer files and are serialized. Reuse #463's trace/projection
  fixtures, then add the browser/isolation evidence specific to the actual reader task.
  No extra gameplay run is required merely to show retained data.
- #290/#291/#467/#473/#474 share the native lane. An unblocked issue is not launch
  authority: human attendance, practice adoption or future-game choice may still be
  missing. Do not encode the practice outcome's completion as a blocker on its own
  measurement child; the missing prerequisite is its owner decision.
- The [measurement review](2026-11-16-experiment-measurement-review.md) governs claim
  limits: preserve whole source groups, all-assigned outcomes, failures and unknowns;
  keep Terra fixed in representation comparisons and price all roles before new studies.

Existing native links match the real issue prerequisites. Closed historical blockers
do not block execution and need no deletion. Resource conflicts are recorded as shared
ownership/serialization, not invented scientific dependencies.

## Reconciliation and cleanup

Eleven descriptions were replaced, retaining one current brief each: #136/#191
clarify current CDDA scope while preserving future portability; #143 distinguishes
memory/program view triggers; #145/#177/#465/#469 distinguish decided adoption from
merged implementations; #463/#680 name shared integration surfaces; #668 bounds its
preparation; #666 routes the shared research owners. The three Ready cards retain
their priorities. No unresolved owner decision or paid experiment is promoted.

The real host process inventory showed no stale gameplay, model host or test process.
Full evidence verification checked every retained hash and passed. Fifteen routine
check-log directories totaling **171,615 bytes** were pruned under the existing
[cleanup policy](../operations/evidence-cleanup.md); spectator screenshots were
empty. Saves, sealed evidence, archives, current prepared app/build/download inputs,
dependency environments and credentials were retained. No uncertain artifact was
deleted, no process needed termination and no managed worktree needed archiving.
The review's branch and temporary snapshots are retired after merged-main validation.

Fast checkpoint checks passed. Independent clean-context review found no high or
medium finding in the Ready selection, all-issue coverage, replacement briefs,
scope clarification or cleanup evidence. No behavioral/native/gameplay lane was
run for this documentation/tracker change; protected editorial CI and merge
receipts belong to the pull request.

| Existing risk | Mechanism | Cost and limit |
| --- | --- | --- |
| R-STALE-DOCS, R-DELEGATION-ERROR | Current briefs and real native dependencies prevent work against an undecided or obsolete interface | This bounded review; no new tracker or standing review gate |
| R-REGRESSION, R-CONTROL-BLOAT | Share migration fixtures and serialize overlapping files; test the actual integrated diff | Existing focused/regression/CI lanes; no duplicate native run for an offline leaf |
| R-EVIDENCE-LOSS, R-WORKSPACE-LITTER | Verify sealed hashes and remove only owned routine output | One full verification; retain saves and uncertain artifacts |
