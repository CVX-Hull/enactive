---
owner: lead
status: active
review_trigger: A listed failure happens or stops being plausible, the scope of use in the charter changes, or a control is added, removed or found not to work
---

# Risk register

This page owns the risks the project defends against. The
[charter](charter.md#scope-of-use-and-what-is-guaranteed) owns the scope of use they are
judged in; the [controls page](controls.md) owns what is done about each one. A risk is
listed only with a failure that can realistically happen in that scope. The
[control rule](standards/authority.md#control-review) says how a control is tied to a
risk and when this register is pruned.

**Rating.** Impact is what the failure costs the person running Enactive or the
project: *severe* is money, lost data or something published that cannot be withdrawn;
*moderate* is hours of rework or a wasted paid run; *minor* is cheap to recover from.
The evidence column says whether the failure has been seen here or is only plausible.

- **High:** severe impact, or moderate impact seen more than once.
- **Medium:** moderate impact that is plausible or was seen once.
- **Low:** minor impact. A Low risk justifies only a control that costs almost nothing,
  and may have no control at all.

## Operating risks

These can happen to someone running Enactive on their own computer with their own
game and provider key.

| Risk | Failure scenario | Evidence here | Impact | Rating |
| --- | --- | --- | --- | --- |
| R-HOST-CHANGE | Setup, a build, a run or an agent changes the user's computer outside the project through a global install, a write outside the project, fullscreen or control of an unrelated process | Setup installed a global package ([environment history](acceptance/2026-11-08-environment-history.md)) | Severe: disrupted work on the same computer | High |
| R-SAVE-LOSS | Play is lost: two processes write one user directory, cleanup removes a save, a tool edits a save, or a run is force-closed before the game saved | Forced closes ended runs without a save ([capable player](acceptance/2026-10-31-capable-player.md), [computer-control evidence](acceptance/2026-10-29-computer-control.md)); no corrupted or deleted save is recorded | Moderate: lost play that must be repeated | High |
| R-UNSTOPPABLE-INPUT | Automation keeps sending input after the user asked it to stop, or the user cannot tell who controls the game | None recorded; Pause has worked in every recorded run | Moderate: the user loses control of their own game window until the process is killed | Medium |
| R-REPEATED-INPUT | Input whose delivery is unknown is sent again, or two writers send at once, so the game receives actions nobody chose | A Quit acknowledgement was lost in real play and stays unknown ([computer-control evidence](acceptance/2026-10-29-computer-control.md)) | Moderate: unintended game actions, some irreversible, and a run whose record is wrong | Medium |
| R-KEY-LEAK | The provider key reaches a file, log, trace, sealed evidence, game process, sandboxed agent or commit | None recorded | Severe: someone else spends the user's credit, and the key must be revoked | High |
| R-PRIVATE-DATA | An agent sends files unrelated to the project to a provider or writes them into evidence | Plausible given model-written commands in the curator | Severe: private content leaves the computer and cannot be recalled | High |
| R-OVERSPEND | A run, retry loop or study spends more provider credit than the user set aside | Plausible. An in-flight refusal occurred despite automatic recharge ([capable player](acceptance/2026-10-31-capable-player.md)). A study stage reached its [cost guard](acceptance/2026-11-11-p1-cost-guard-178.md) | Severe: direct money loss | High |
| R-PROVIDER-FAILURE | The provider refuses, times out, reroutes or returns malformed usage, and the run retries blindly, hangs or records a wrong cost | In-flight HTTP 402 ([capable player](acceptance/2026-10-31-capable-player.md)) and a failed request counted at its reservation that ended a [curator session](acceptance/2026-11-11-p1-cost-guard-178.md) | Moderate: a wasted run or a wrong cost record | High |
| R-RUNAWAY-RUN | An unwatched run loops, continues after the character dies, fills the disk or leaves processes behind | No runaway loop is recorded. Retained artifacts have occupied several gigabytes ([delivery audit](decisions/010-streamlined-delivery.md#context-what-the-audit-found)) | Moderate: wasted spend up to the run's limits, or a slow or full shared disk | Medium |
| R-BAD-INPUT-SOURCE | Setup or continuous integration downloads or builds something other than the pinned game source and dependencies | None recorded | Moderate: what runs is not what was tested | Medium |
| R-PUBLISHED-MISTAKE | A commit or evidence file publishes a private identity, secret, private path, save or material that breaks the game's licence | Placeholder commit identities appear in main's history | Severe: publication to a public repository cannot be fully withdrawn | High |
| R-EVIDENCE-LOSS | Raw run evidence that a dated record cites is deleted or changed, usually by cleanup of the runtime directory | Second copies and stale resources had to be told apart from the only originals before removal ([retirement record](acceptance/2026-11-08-retirement.md)); the store has no backup | Moderate: the record's claims cannot be checked, and the run must be paid for again | Medium |
| R-UNCOVERED-CONTEXT-LOSS | Under severe curator lag or non-real-time queueing, bounded uncovered-cut fallback trims raw turns from the player's live request before the curator synthesizes them, temporarily hiding unsynthesized detail until the curator catches up or the player re-reads omitted frames | Plausible under delayed or stalled curation ([lag replay](acceptance/2026-11-27-uncovered-cut-lag-replay-1037.md)); disk WAL ingestion path remains available so later curator windows can still read those turns | Moderate: suboptimal play or extra `player_source` reads during prolonged curator lag | Medium |

## Development risks

These can happen to the project itself while it is being built.

| Risk | Failure scenario | Evidence here | Impact | Rating |
| --- | --- | --- | --- | --- |
| R-REGRESSION | A change breaks working behaviour that a paid run relies on | Full tests have caught defects that focused tests missed ([delivery audit](decisions/010-streamlined-delivery.md)). The [review of selected CI failures](acceptance/2026-11-12-control-review-and-names.md#method) found no confirmed player or harness defect. The recall parser passed tests with stand-in replies and rejected real replies in [paid play](acceptance/2026-11-14-delivery-development-start.md) | Moderate: a wasted paid run, or a broken boundary found late | High |
| R-FALSE-CLAIM | A document, record or summary claims more than was observed: a fixture pass reported as gameplay, an agent's summary reported as a measurement, a comparison too small to support its conclusion | A study's question sessions ran without their screenshots and were caught only by trace review ([image input stop](acceptance/2026-11-11-p1-image-input-stop-178.md)) | Severe: decisions and money follow a result that is not real | High |
| R-ARCHITECTURE-DRIFT | The computer layer gains game meaning, the player gains process authority or the evaluator leaks into play | Plausible given shared boundaries across agent-written code | Moderate: the design stops being true and later changes cost more | Medium |
| R-GAME-COUPLING | Shared code comes to depend on this game, one coding agent, one provider or one model | Game vitals were hard-coded in the viewer and provider tables sat in shared code ([ADR 010](decisions/010-streamlined-delivery.md)) | Moderate: the charter's portability constraint is silently lost | High |
| R-TECH-DEBT | Old contract versions, compatibility paths, copied helpers or finished one-off tooling stay in the tree and are maintained and tested forever | Copied helpers and finished study scripts were found in the tree ([ADR 010](decisions/010-streamlined-delivery.md)); a closed study's tests were 29% of the suite and constrained live code ([control review](acceptance/2026-11-12-control-review-and-names.md)) | Moderate: every change costs more, and the suite grows without protecting anything | High |
| R-STALE-DOCS | A current page gives wrong guidance, contradicts another page or cannot be reached from the overview | A generated map disagreed with configuration ([delivery audit](decisions/010-streamlined-delivery.md)). Current pages misstated review cadence and contradicted one another on the commit hook ([control review](acceptance/2026-11-12-control-review-and-names.md#removed-or-simplified)) | Moderate: people and agents act on wrong guidance | High |
| R-UNREADABLE-DOCS | A page is true but cannot be used: opaque labels, attempt logs in current pages, unbroken walls of text | The label `P1` meant a phase, a study, a priority and a design principle in different pages ([name mapping](acceptance/2026-11-12-control-review-and-names.md#names)) | Moderate: the owner cannot steer, and agents spend context reconstructing meaning | Medium |
| R-STUDY-OVERRUN | A study or campaign costs more than its question is worth or cannot answer it at an affordable size | A [power gate](acceptance/2026-11-09-p1-gate-178.md) stopped spend before launch. Protocol revisions and recovery attempts still ended in a [no-go](acceptance/2026-11-12-p1-descriptive-completion-178.md) | Severe: days of work and real money for no adopted result | High |
| R-DELEGATION-ERROR | A delegate works outside its brief, edits overlap, an unverified report is accepted or a delegate sends unauthorized game input | Plausible given concurrent delegated work | Moderate: rework or acceptance of a wrong change | Medium |
| R-WRONG-MERGE | A change reaches main without the required checks or on a different tree from the one reviewed | A study protocol's first draft merged in place of its approved text ([study protocol merge](https://github.com/CVX-Hull/enactive/pull/530)) | Moderate: later work starts from an unreviewed tree | Medium |
| R-NATIVE-MISMATCH | The compiled adapter, the game build or the input path changes, and fixtures still pass while the real game behaves differently | Defects in receipt order and capture timing appeared only against the real game ([receipt order](acceptance/2026-10-20-native-receipt-order.md), [capture preconditions](acceptance/2026-10-22-native-capture-preconditions.md)) | Moderate: a paid run fails on a defect no portable test can see | High |
| R-WORKSPACE-LITTER | Merged branches, finished worktrees and stashes pile up, so stale work is mistaken for live work | Cleanups found accumulated worktrees and branches ([delivery audit](decisions/010-streamlined-delivery.md), [workspace cleanup](acceptance/2026-11-12-control-review-and-names.md#workspace-cleanup)) | Minor: disk use and some chance of deleting or reviving the wrong work | Low |
| R-CONTROL-BLOAT | Controls accumulate until their cost exceeds that of the failures they prevent | A control registry caught no defect ([delivery audit](decisions/010-streamlined-delivery.md)). A [text scan](acceptance/2026-11-12-control-review-and-names.md#removed-or-simplified) repeatedly blocked pull requests over design-page wording without preventing a defect | Moderate: slower delivery and unnecessary rework | High |

## Out of scope

These are not risks in the scope of use, so no control may be justified by them. A
control that exists only for one of them is removed.

| Not defended | Why |
| --- | --- |
| Availability: the system must stay up, restart itself or survive being killed | The user can stop or kill it at any time and start again; a stopped run loses only that run |
| A hostile local user or process on the same computer | Whoever can run code as the user already owns the game, the key and the repository |
| Tamper resistance against the owner | The owner may change any file, rule or record; controls only stop accidents |
| Separate human approvers, sign-off chains or audit trails for an outside party | One maintainer; no regulator, customer or auditor reads the records |
| Requiring a person to watch a run | A run is finite and bounded by its limits and by Pause; R-RUNAWAY-RUN covers what an unwatched run can waste |
| Running as a service that starts or resumes runs on its own | Every run is started by a person; the [charter](charter.md) requires a recheck before unattended operation |
| Hosts other than the validated Mac, and games other than the validated one | The [overview](overview.md) states them as unqualified; nothing is promised. Continuous integration runs on Linux, so macOS-only code needs a skip there |
| Accessibility conformance of project documents | The readers are the maintainer and coding agents; pages must be clear, not certified |
| Vulnerabilities in the game, the provider, the operating system or coding agents | Their owners are responsible. The project pins what it uses and reports what it sees |
