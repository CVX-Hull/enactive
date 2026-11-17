---
owner: lead
status: historical
kind: review
date: '2026-11-17'
scope: 'Full open-backlog reconciliation after process-measures/2; source-only gate-contract discovery selected for Ready, dependency/integration review and owned cleanup; no implementation or gameplay'
---

# Backlog grooming after the process-report repair

## At a glance

[#697](https://github.com/CVX-Hull/enactive/issues/697), resolving the prospective
curator-gate verification and publication contract, is the sole Ready item. It is
lead-owned source-only engineering design, not implementation of #457, a belief
choice or permission for a model/game run. Its result may be an implementable first
slice or a justified defer/rescope with exact missing dependencies. Completing the
discovery alone cannot make #457 Ready.

At baseline `7ef2706bc1cdf7fe055a71572e2f31f0ab967dcd`, after #694, the tracker had
32 open Backlog issues, 236 Done cards and no Ready work or open PR. After grooming,
the readback has **33 open issues and 269 unique cards: 236 Done, 32 Backlog, one
Ready, none In progress**. Each open issue has an accountable owner and one card;
Done cards reference completed issues, not cancellations. The open dependency graph
is acyclic. Existing outcome acceptance and all existing execution statuses remain
unchanged.

## Why this next result

Five read-only explorers divided all open issues into memory/readers, research,
programs/practice, campaigns/runtime and cleanup. The lead verified their evidence
against source and actual tracker readbacks. None of the existing leaves is Ready
as written. Independent clean-context review assessed the proposed discovery against
the real gate/session/repository interfaces and approved its bounded Ready shape.

The gap is concrete: `harness/curator/session.py` exports the published knowledge
and the session's trace window, then immediately gates collected submissions against
that same window. `harness/curator/gate.py:gate` has no independent later-trace test
input or pending-verification state. ADR009 proposes unseen prospective trace while
also requiring submissions to be gated before another session starts. Its semantic
utility measures have no executable oracle, and its isolation excludes evaluator
records and lead probes from the operating curator. Finally,
`harness/curator/knowledge.py:Repository.published` selects the highest version tag;
operator revert semantics need a contract rather than an isolated reset.

#697 resolves or names these lifecycle, exposure, oracle and publication gaps before
implementation. Its finite source/fixture inventory and contract-case table need no
new images, game observations, target labels, provider calls or belief calculus.
Runtime, schemas, prompts, current contracts and tests remain read-only. The proposed
contract belongs in the existing curator-session design, clearly separated from
current behavior, with only necessary proposal cross-references in ADR009.

The alternative suggestions were not selected:

- #677's mechanical Beta/opinion/retraction checks could verify apparatus, but their
  implementation assumptions and exact ownership still need shaping. They cannot
  resolve gate publication/lifecycle or establish predictive benefit; no mathematics
  framework is added simply to fill the queue.
- A #473 source-capacity/protocol discovery concerns an undecided practice phase and
  is not the immediate adopted-memory dependency. Actual determinism/concurrency
  measurements remain separately gated; no second instance is launched.
- #42 has no named current use for scored expectations. #664 already owns a later
  integration brief and depends on a settled richer store; neither warrants a
  duplicate discovery item.

## Disposition of all previously open issues

This table records the audit checkpoint. GitHub owns subsequent work selection.

| Issue | Disposition and remaining condition |
| --- | --- |
| #25 | Backlog: owner must reopen and price a smaller-player trial; Terra remains current. |
| #42 | Backlog: name a use and coordinated expectation producer/reader contract before adding the field. |
| #136 | Open delivery aggregate; no campaign acceptance follows from child implementation. |
| #143 | Open spectator aggregate; #689 complete, richer/program views await their producers; #336 untriggered. |
| #145 | Campaign outcome remains parked through #441's resumption/freeze/price decision. |
| #164 | Responsiveness remains a separate unqualified aim; no concrete current cadence run selected. |
| #177 | Programs/monitor aggregate remains proposed, after the richer gate/store contract. |
| #191 | Portability remains unqualified; current work is CDDA only. |
| #290 | Remaining real-host cases await a consenting attended window or concrete input failure and applicable approval. |
| #291 | Second-game selection/build/task remain future-version owner decisions. |
| #309 | Failover remains trigger-bound, with settled context and a separately priced probe. |
| #336 | Recorded-reader stepping friction is not established by the inspected tasks; keep its trigger. |
| #384 | Intent is implemented; later behavioral/cost measurement needs a finite priced protocol. |
| #387 | Memory aggregate stays open; new #697 supplies gate-contract discovery without weakening #457 acceptance. |
| #441 | Seven-day screen stays parked; no new lineage or old-envelope reuse. |
| #445 | Curated-player aggregate now routes to #697 before the coordinated #457 handoff. |
| #457 | Backlog: consume #697's contract/gaps, settle the separate belief choice and coordinated migration brief. |
| #464 | Broader store/ontology/draft views await #457; reuse #689 instead of rebuilding its projection. |
| #465 | Passive-policy migration waits on #457's settled repository/gate contract. |
| #466 | Capability slots follow #465 and share the runner integration sequence. |
| #467 | New supervised runner/custody remains unbuilt, after #465/#466. |
| #468 | Monitor/risk classes await runtime, gate and fitting prerequisites, including #469. |
| #469 | Fitting/curation wait on gate/policy contracts; shared runner/gate edits are serialized. |
| #470 | Study/adoption follows producers/views and an exact design/price/owner decision. |
| #471 | Program views wait for recorded producer data and #464's shared-viewer order. |
| #472 | Practice phase remains an owner decision; aggregate completion is not its children's prerequisite. |
| #473 | Practice decision and actual measurement approval remain open; no run follows from a source checkout. |
| #474 | Fork isolation waits on the practice decision and #473 results, with separate native acceptance. |
| #664 | Live-curator integration remains later; #697 must expose any scheduler coupling without implementing it. |
| #666 | Research aggregate stays open; #694 complete, Horizon returns from Now to Next. |
| #677 | Replay needs answerable prediction/revision targets, source/label support and complete pricing; not a #457 prerequisite. |
| #681 | Qualification still needs a rescoped task/capture/identity/source/label plan after #690's defer; #694 only repaired reporting. |

## Tracker and integration reconciliation

Replaced #387, #445 and #457 descriptions. Their complete Acceptance sections are
byte-identical to baseline. #697 is a native child of #387 and a native blocker of
#457 implementation admission; it has no open prerequisite. It is Ready/Important.
Only #666 changes an existing Project field, from Now to Next. All other existing
issue bodies, statuses and priorities remain unchanged. Saved Project views still
select open execution leaves, attention items, outcomes and Backlog as intended.
No #472-completion dependency was added to #473.

The selected design uses one lead writer and one independent reviewer. It names the
source-derived contract cases, evidence/oracle assumptions, consumer matrix and
minimum implementation slice or precise stop. #457 remains one coordinated migration
of the store, gate and all consumers; the discovery does not create a competing schema.
Its future implementation reuses #689's reader projection/browser cases where relevant.

Serialize session/ADR design edits with #457/#664/#465/#468/#469. Future
#466/#467/#469 runner changes and #457/#468/#469 gate changes have one writer in
sequence. #464/#471/#336 share viewer files; the native/custody lane for
#290/#467/#473/#474 remains lead-owned and serialized. Source/document checks for the
selected discovery are distinct from portable runtime, browser, native and actual-play
acceptance. No new game/model batch, collector, test framework or gate is introduced
by grooming.

The unanswered #457 belief question remains open; no option or owner-decision row
was invented. No research study, campaign, context cut, live scheduler, cheaper player,
program/monitor or practice phase was adopted. #694 remains Done, and its descriptive
ranges are not outcome qualification or population coverage evidence.

## Cleanup and evidence

Initial inspection found clean main/origin-main, only the primary checkout, no open
PR, no project runtime/checker process, and no routine checker logs or spectator shots
to remove. The exact temporary source workspace named by the build manifest is absent;
the prepared project-local app is present. Preserve the manifest as provenance, not
as proof that the temporary directory still exists. Old wrapper/setup/build logs are
retained by the environment/retirement policy; saves, canonical sealed evidence,
dependencies, downloads and the prepared app remain. App attachment references alone
do not establish that an absent worker checkout exists; app ownership state was not
edited.

Before/after tracker snapshots, the selected brief, review dispositions and cleanup
inventory are retained in the sealed `post-process-report-backlog-grooming` evidence
entry: **54 files, 3,878,990 bytes**. Its tracked manifest/index own bytes and provenance.
`tools.evidence verify --full` passed. A separate path/hash comparison confirmed all
54 staging files in the seal before the duplicate task staging was removed. The publication
branch and routine check outputs are removed after protected merge and main validation.

## Limits

This is engineering-agent source/tracker review, not human approval or experimental
evidence about the player. No new image inspection, labels, provider/gameplay call,
native execution or behavior change was needed. Grooming selects #697; it does not
execute that design task. The Project is authoritative after this checkpoint.
