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

These can happen to someone running Enactive on their own computer with their own game
and OpenRouter key.

| Risk | Failure scenario | Evidence here | Impact | Rating |
| --- | --- | --- | --- | --- |
| R-HOST-CHANGE | Setup, a build, a run or an agent changes the computer outside the project: a global install, a write outside the project directory, a fullscreen window, a killed or adopted process that is not ours | A global package was installed and then removed during first setup ([environment history](acceptance/2026-11-08-environment-history.md)) | Severe: the user's other work on the same computer is disturbed or broken | High |
| R-SAVE-LOSS | Play is lost: two processes write one user directory, cleanup removes a save, a tool edits a save, or a run is force-closed before the game saved | Forced closes ended runs without a save ([capable player](acceptance/2026-10-31-capable-player.md), [computer-control evidence](acceptance/2026-10-29-computer-control.md)); no corrupted or deleted save is recorded | Moderate: lost play that must be repeated | High |
| R-UNSTOPPABLE-INPUT | Automation keeps sending input after the user asked it to stop, or the user cannot tell who controls the game | None recorded; Pause has worked in every recorded run | Moderate: the user loses control of their own game window until the process is killed | Medium |
| R-REPEATED-INPUT | Input whose delivery is unknown is sent again, or two writers send at once, so the game receives actions nobody chose | A Quit acknowledgement was lost in real play and stays unknown ([computer-control evidence](acceptance/2026-10-29-computer-control.md)) | Moderate: unintended game actions, some irreversible, and a run whose record is wrong | Medium |
| R-KEY-LEAK | The OpenRouter key reaches a file, a log, a trace, sealed evidence, the game process, a sandboxed agent or a commit | None recorded | Severe: someone else spends the user's credit, and the key must be revoked | High |
| R-PRIVATE-DATA | An agent with tools reads files unrelated to the project and sends their content to a model provider, or writes them into evidence | None recorded; the curator runs model-written commands, which is why it is sandboxed | Severe: private content leaves the computer and cannot be recalled | High |
| R-OVERSPEND | A run, a retry loop or a study spends more OpenRouter credit than the user set aside | No overspend is recorded. A run was refused in flight while automatic top-up was on, so the account balance is not a cap ([capable player](acceptance/2026-10-31-capable-player.md)); a study stage was stopped by its cost guard ([cost guard](acceptance/2026-11-11-p1-cost-guard-178.md)) | Severe: direct money loss | High |
| R-PROVIDER-FAILURE | OpenRouter or the pinned provider refuses, times out, reroutes or returns malformed usage, and the run retries blindly, hangs or records a wrong cost | HTTP 402 arrived in flight ([capable player](acceptance/2026-10-31-capable-player.md)); one failed request was debited at its worst case and ended a session ([cost guard](acceptance/2026-11-11-p1-cost-guard-178.md)) | Moderate: a wasted run or a wrong cost record | High |
| R-RUNAWAY-RUN | A run nobody is watching loops, continues after the character dies, fills the disk or leaves processes behind when it ends | No runaway loop is recorded; nobody is required to watch a run. Worktrees and evidence grew to several gigabytes before a cleanup ([ADR 010](decisions/010-streamlined-delivery.md)) | Moderate: wasted spend up to the run's limits, or a slow or full shared disk | Medium |
| R-BAD-INPUT-SOURCE | Setup or continuous integration downloads or builds something other than the pinned game source and dependencies | None recorded | Moderate: what runs is not what was tested | Medium |
| R-PUBLISHED-MISTAKE | A commit or evidence file publishes a private identity, a secret, a private path or save, or content that breaks the game's licence | Seven early commits on main carry a placeholder local identity instead of the repository's; no secret or private path is recorded | Severe: cannot be fully withdrawn once pushed to a public repository | High |
| R-EVIDENCE-LOSS | Raw run evidence that a dated record cites is deleted or changed, usually by cleanup of the runtime directory | Second copies and stale resources had to be told apart from the only originals before removal ([retirement record](acceptance/2026-11-08-retirement.md)); the store has no backup | Moderate: the record's claims cannot be checked, and the run must be paid for again | Medium |

## Development risks

These can happen to the project itself while it is being built.

| Risk | Failure scenario | Evidence here | Impact | Rating |
| --- | --- | --- | --- | --- |
| R-REGRESSION | A change breaks behaviour that worked, and nobody notices before it is relied on in a paid run | The full suite has caught defects that focused tests missed ([ADR 010](decisions/010-streamlined-delivery.md)). Seven failed pull-request checks from 9 to 12 November 2026 were read: four were a text scan, two were macOS-only calls on the Linux runner and one was a study test; none was traced to a defect in the player or harness ([control review](acceptance/2026-11-12-control-review-and-names.md#method)) | Moderate: a wasted paid run, or a broken boundary found late | High |
| R-FALSE-CLAIM | A document, record or summary claims more than was observed: a fixture pass reported as gameplay, an agent's summary reported as a measurement, a comparison too small to support its conclusion | A study's question sessions ran without their screenshots and were caught only by trace review ([image input stop](acceptance/2026-11-11-p1-image-input-stop-178.md)) | Severe: decisions and money follow a result that is not real | High |
| R-ARCHITECTURE-DRIFT | Code crosses a boundary the design depends on: the computer layer gains game meaning, the player gains process authority, the evaluator leaks into play | No shipped breach recorded; import contracts have guarded the boundaries since [ADR 003](decisions/003-development-controls.md), and agents write most of the code | Moderate: the design stops being true and later changes cost more | Medium |
| R-GAME-COUPLING | Shared code comes to depend on this game, one coding agent, one provider or one model | Game vitals were hard-coded in the viewer and provider tables sat in shared code ([ADR 010](decisions/010-streamlined-delivery.md)) | Moderate: the charter's portability constraint is silently lost | High |
| R-TECH-DEBT | Old contract versions, compatibility paths, copied helpers or finished one-off tooling stay in the tree and are maintained and tested forever | Copied helpers and finished study scripts were found in the tree ([ADR 010](decisions/010-streamlined-delivery.md)); a closed study's tests were 29% of the suite and constrained live code ([control review](acceptance/2026-11-12-control-review-and-names.md)) | Moderate: every change costs more, and the suite grows without protecting anything | High |
| R-STALE-DOCS | A current page states something that is no longer true, contradicts another page, or cannot be reached from the overview | The generated controls map disagreed with the configuration it described ([ADR 010](decisions/010-streamlined-delivery.md)); four days later current pages still described calendar reviews and a commit hook as both default and optional ([control review](acceptance/2026-11-12-control-review-and-names.md#removed-or-simplified)) | Moderate: people and agents act on wrong guidance | High |
| R-UNREADABLE-DOCS | A page is true but cannot be used: opaque labels, attempt logs in current pages, unbroken walls of text | The label `P1` meant a phase, a study, a priority and a design principle in different pages ([name mapping](acceptance/2026-11-12-control-review-and-names.md#names)) | Moderate: the owner cannot steer, and agents spend context reconstructing meaning | Medium |
| R-STUDY-OVERRUN | A study or campaign costs more time or money than its question is worth, or cannot answer the question at the size it can afford | One study was stopped at its power gate before spending ([gate record](acceptance/2026-11-09-p1-gate-178.md)), then needed three protocols and several recovery attempts and ended in a registered no-go ([completion record](acceptance/2026-11-12-p1-descriptive-completion-178.md)) | Severe: days of work and real money for no adopted result | High |
| R-DELEGATION-ERROR | A delegated agent works outside its brief, two agents edit the same files, an agent's unverified report is accepted, or an agent sends game input it should not | None recorded as a defect on main; agents do most of the work, several at once | Moderate: rework, or a wrong change accepted | Medium |
| R-WRONG-MERGE | A change reaches main without the checks that would have caught its defect, or the tree that merges is not the tree that was reviewed | A first draft of a study protocol was merged in place of the approved text ([#530](https://github.com/CVX-Hull/enactive/pull/530)) | Moderate: main holds something nobody approved, and the next branch starts from it | Medium |
| R-NATIVE-MISMATCH | The compiled adapter, the game build or the input path changes, and fixtures still pass while the real game behaves differently | Defects in receipt order and capture timing appeared only against the real game ([receipt order](acceptance/2026-10-20-native-receipt-order.md), [capture preconditions](acceptance/2026-10-22-native-capture-preconditions.md)) | Moderate: a paid run fails on a defect no portable test can see | High |
| R-WORKSPACE-LITTER | Merged branches, finished worktrees and stashes pile up, so stale work is mistaken for live work | 17 worktrees and 86 branches had accumulated before one cleanup ([ADR 010](decisions/010-streamlined-delivery.md)), and 5 worktrees and 25 branches again four days later | Minor: disk use, and some chance of deleting or reviving the wrong thing | Low |
| R-CONTROL-BLOAT | Controls are added faster than they are removed, until checks mostly check other checks and process costs more than the failures it prevents | A control registry with its schema, generator and tests was removed after catching no defect ([ADR 010](decisions/010-streamlined-delivery.md)). Four failed pull-request checks from 9 to 12 November 2026 were a text scan objecting to a word in a design page | Moderate: slower delivery and rework that protects nothing | High |

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
| Vulnerabilities in the game, OpenRouter, the operating system or coding agents | They belong to their owners; the project pins what it uses and reports what it sees |
