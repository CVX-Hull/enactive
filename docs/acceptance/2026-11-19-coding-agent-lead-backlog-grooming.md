---
owner: lead
status: historical
kind: review
date: '2026-11-19'
scope: 'All open issues, Project reconciliation, Ready selection, registration of the coding-agent lead work and owned cleanup after the Campground records; no implementation or gameplay'
---

# Backlog grooming and registration of the coding-agent lead work

## At a glance

The audit registered the coding-agent lead outcome
[#808](https://github.com/CVX-Hull/enactive/issues/808) with five leaves, and left five
leaves Ready: [#804](https://github.com/CVX-Hull/enactive/issues/804),
[#805](https://github.com/CVX-Hull/enactive/issues/805),
[#809](https://github.com/CVX-Hull/enactive/issues/809),
[#810](https://github.com/CVX-Hull/enactive/issues/810) and
[#812](https://github.com/CVX-Hull/enactive/issues/812). None of the five needs the game
or a paid model call. Of the 33 previously open issues, 31 stay in Backlog. No study,
campaign, model change or later program or practice phase was adopted. This is queue
selection and registration, not implementation.

The source baseline is `3529c31a4d4bd5a3c1bd9bf24e9be1a56ac6d4d6`. Before the audit the
tracker held 33 open issues and 327 cards: 294 Done, 32 Backlog and one Ready. The
readback after it holds **40 open issues and 334 cards: 294 Done, 34 Backlog, five Ready
and one In progress**, the last being this audit's own issue
[#807](https://github.com/CVX-Hull/enactive/issues/807). Each open issue has one card.
Done cards are completed issues; the 73 issues closed as not planned or duplicate have
no card. The open dependency graph is acyclic.

## Inspection and selection

Four read-only explorers divided the open backlog into campaigns and runtime, curated
memory, programs and practice, and spectator and portability. A fifth inventoried local
artifacts. The lead checked their reports against the tracker, the issue descriptions
and the tree.

Two of their recommendations were not taken:

- **Labels for parked chains.** The explorers proposed `blocked` or `decision-needed`
  on ten parked leaves: #290, #291, #309, #457, #464, #465, #470, #471, #473 and #664.
  Where a leaf waits on another open issue (#464, #465, #470, #471 and #664), GitHub's
  issue dependencies already record it, and an issue blocked that way carries the
  Blocked mark the Needs attention view reads. The others are parked by an owner
  decision already in the log or by a condition their description states, so no new
  answer is being awaited. Adding labels would repeat the edges and fill that view
  with work nobody can act on. No label changed on a previously open issue.
- **Stale descriptions.** Several "Current state" paragraphs were reported as ending
  before [#803](https://github.com/CVX-Hull/enactive/issues/803). Each of those
  descriptions already states #803's result and the #804 and #805 follow-ups in a later
  paragraph, so they were left. One report called #309's sentence "No live 5xx response
  has exercised the retry" stale; it still holds, because in #803 the request deadline
  expired during the provider's backoff before any retry.

#805 moved from Backlog to Ready. Its description had an outcome, evidence, acceptance
and an owner; the lead added its paths, stop condition and dependency. It is an offline
review on existing fixtures with a controlled clock.

## Disposition of every open issue

These are dated dispositions, not a second live queue. GitHub owns later changes.
Aggregate acceptance is preserved: completing a child does not complete its parent.

| Issue | Disposition and next condition |
| --- | --- |
| #25 | Smaller-player trial stays deferred until the owner reopens it after the memory and context work. |
| #42 | Expectation scoring still has no named use; its paths are not chosen. |
| #136 | Root aggregate stays open. Its child table gained rows for #805 and #808. |
| #143 | Spectator aggregate stays at Horizon Next; #464 waits on #457, #471 on the program producers, and #336 on its trigger. |
| #145 | Seven-day campaign is not met: its twelve closed children were preparation and development runs, and nine acceptance items remain. Horizon moves from Now to Next, because the freeze waits for the memory-first sequence. No child is created before that. |
| #164 | Responsiveness stays a non-gating aim with no cadence run selected. Horizon moves from Next to Later; its revisit trigger is a concrete pacing bottleneck in the retained windows. |
| #177 | Programs and monitor aggregate stays at Later until #457 settles the gate schema and a bounded handoff exists. |
| #191 | Portability stays at Later; the owner limited current work to CDDA. |
| #290 | Remaining real-host input cases need an attended window with a consenting person. |
| #291 | No second game, build or task is chosen. |
| #309 | Failover stays parked behind "Memory first" and a priced probe. #805 goes first, since it decides whether a server error is absorbed by the retry. |
| #336 | Investigation speed work stays untriggered; no recorded-reader task has shown stepping friction. |
| #384 | Intent measurement stays deferred until someone names an ambiguous review decision and a price. |
| #387 | Memory aggregate stays open for #457, #664 and #384. |
| #445 | Curated-player aggregate stays at Now through #666. |
| #457 | Richer fact store stays blocked: the production belief representation and the oracle, cohort and utility contract are open. |
| #464 | Broader curator and ontology views wait on #457. |
| #465 | Passive-policy migration waits on #457; no program producer exists. |
| #466 | Capability slots follow #465. |
| #467 | Supervised asynchronous runs follow #465 and #466 and need the native lane. |
| #468 | Risk classes and the monitor follow #457, #466, #467 and #469. |
| #469 | Fitting and curation follow #457, #465 and #467. |
| #470 | Programs study needs its prerequisites, a design and a price from the owner. |
| #471 | Program views need recorded program and monitor data. |
| #472 | Practice stays deferred by the owner's decision of 17 November 2026. |
| #473 | Concurrency and determinism measurement waits on the practice decision and a priced approval. |
| #474 | One-way practice forks follow #473. |
| #664 | Live curator freshness follows #457's store contract. |
| #666 | Recurrence research stays at Now. Order of its open children: #804, then #681, then #677. |
| #677 | Belief comparison still lacks independent sources, a weight rule, a protocol and a price. |
| #681 | Outcome qualification still lacks independent positive, negative and unknown sources. |
| #804 | Stays Ready and Important: the next offline memory step. |
| #805 | Now Ready and Important: an offline review of the request deadline during a provider backoff. |
| #807 | This audit; In progress until merged-main validation. |
| #808 | New aggregate, Horizon Now: any of the three coding agents as lead, and the model for engineering work chosen by kind of work. |
| #809 | New, Ready and Important: the coding agent, model and effort on every pull request and review. |
| #810 | New, Ready and Important: Antigravity leads #809 once, watched. It needs the owner to start the session. |
| #811 | New, Backlog: the lead's duties for three coding agents; follows #810's record. |
| #812 | New, Ready and Important: routing by kind of work. The owner decided during the audit that role definitions live in the repository. |
| #813 | New, Backlog: the same leaf on two coding agents; follows #809 and #812. |

## Reconciliation and integration

Seven issues were created: #807 for this audit, and #808 with its children #809 to #813.
#807 and #808 are native children of #136. Four native dependencies were added: #811
is blocked by #810 and #812, and #813 by #809 and #812. Two descriptions were replaced: #136 and
#805. Five owner decisions of 19 November 2026 were added to the
[owner decision log](../decisions/owner-decisions.md). Two of them were asked during the
audit: role definitions live in the repository, which made #812 Ready, and an
Antigravity lead may merge once the owner relaxes a user-wide rule outside the project.

Project fields changed on three previously open issues: #805 to Ready and Important,
#145 to Horizon Next, and #164 to Horizon Later. No saved view was changed, and the
views were not re-read in this audit.

The shared integration constraints are:

- **The Ready leaves can run side by side.** #804 is offline reading of retained
  packets; its description names no paths, and none of the others' paths are readers of
  those packets. #805 owns `tools/player_host/host.mjs` and its retry tests. #809 owns
  the pull-request template and one sentence of the review page. #810 delivers #809.
  #812 owns a new routing page, a new dated record, the hosts page and the tracked role
  definitions. Two implementation workers can therefore take any two of #804, #805 and
  #812 at once while the owner starts #810. #812 names `docs/controls.md` and #809
  names it only if a control row must change, so the second to merge rebases on the first.
  #811 shares the hosts page with #812 and follows it. All five use the fast checks and
  need neither the native lane nor a provider key.
- **`tools/player_host/` has one writer at a time.** #805 shares it with #309, #42,
  #465, #466, #469 and #664, whose descriptions name it. #805 goes first; the others
  are parked.
- **#457 is the single gate for two chains.** #464, #465, #468, #469 and #664 wait on
  its fact, type, gate and consumer migration. #465, #466, #467 and #469 then write
  `harness/player/programs.py` in turn, and #457, #465, #468 and #469 write
  `harness/curator/gate.py` in turn.
- **The viewer has one writer at a time.** #336, #464 and #471 share `harness/viewer/`,
  `web/app/` and the browser suites. #464 goes before #471; #336 may go ahead of both
  if it is ever triggered.
- **One native lane.** #290, #467, #473 and #474 need the lead-owned game runtime and
  run one at a time. Portable, offline, browser, native and actual-play evidence stay
  separate.
- **The retained packets are shared.** #804, #681 and #677 read the same sealed cases;
  #804 fixes the comparison design the other two reuse.
- **The coding-agent chain.** #810 delivers #809 and produces the record #811 is written
  from. #812 is Ready. #813 follows #809 and #812.

No new game, provider request, native build or paid annotation was needed for grooming.
One read-only Antigravity probe ran earlier the same day on subscription quota; #810's
description records what it measured.

## Cleanup and retained evidence

Besides this change's own branch, Git inspection found only `main` and `origin/main`
with the primary checkout, no open
pull request, no worker checkout and no stash. A filtered process inventory found no
project game, player host, curator host, spectator or checker process, and the shared
game lock had no holder. No unrelated process was terminated.

Routine checker logs under `.runtime/check-logs/` were pruned to the five newest
directories before this record was committed, as the
[cleanup rule](../operations/evidence-cleanup.md) allows when no check is running.
Nothing else was removed. `tools.evidence verify --full` passed before and after.

Retained because their ownership or citation is not established: the nineteen
directories under `.runtime/evaluations/`, one of which appears in neither the run
ledger nor any tracked file; the build manifest that names an absent temporary build;
and regenerable interpreter and tool caches, which no document names. Sealed evidence,
the live user directory, the six user-directory archives, downloads and the current
build remain.

The tracker snapshots before and after, and the issue descriptions before the audit and
as written, are retained in the sealed `coding-agent-lead-backlog-grooming` evidence
entry. Its manifest and the evidence index own their bytes and provenance. In its
`descriptions-written` folder the files are named by drafting key: `G` is #807, `P` is
#808, `L1` to `L5` are #809 to #813, and `136` and `805` are those issues. The sealed
readback was taken before the two decisions asked during the audit: it shows #812 in
Backlog with `decision-needed` and four leaves Ready. The counts in this record are from
a later readback, and the tracker owns the state.

## Limits

Agent inspection is review evidence, not human approval or a qualified outcome
measurement. The snapshots establish the recorded state at readback; the Project is
authoritative afterward. Registering the coding-agent lead work implements none of it:
no coding agent's fitness as lead, and no model's fit for a kind of work, is shown here.
