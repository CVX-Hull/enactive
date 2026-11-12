---
owner: maintainer
review_trigger: Behavior, control failures, release or constraints change
status: active
---

# Engineering standards and workflow

The lead adjudicates design and verification. Principles are in the
[charter](charter.md). The [risk register](risks.md) lists what can go wrong in the
project's scope of use, and the [controls page](controls.md) says what is done about
each risk. Each standard below is mandatory in its scope and exists for the risks named
beside it; a rule in a standard is a control and follows the
[control rule](standards/authority.md#control-review).

An exception needs scope, reason, owner and a revisit condition in a GitHub issue
linked to the affected standard; [work](work.md) links the work tracker. Exceptions
cannot override user instructions or hide failed acceptance.

| Standard | What it requires | Risks it addresses |
| --- | --- | --- |
| [Authority and reading order](standards/authority.md) | Which page owns which fact, the control rule, and the change cadence | R-STALE-DOCS, R-CONTROL-BLOAT |
| [S-UX Understandable and controllable experience](standards/experience.md) | The operator can see who controls the game and can stop it | R-UNSTOPPABLE-INPUT, R-UNREADABLE-DOCS |
| [S-ARCH Explicit architectural boundaries](standards/architecture.md) | Boundaries are described and reviewed before they change | R-ARCHITECTURE-DRIFT, R-GAME-COUPLING |
| [S-PROTOCOL Command and observation authority](standards/protocol.md) | One writer, original identifiers, no replay of uncertain input | R-REPEATED-INPUT, R-UNSTOPPABLE-INPUT |
| [S-CODE Maintainable implementation](standards/implementation.md) | Reuse before custom code; rely on platform contracts; no redundant layers | R-TECH-DEBT, R-CONTROL-BLOAT |
| [S-DELIVERY Reproducible and isolated delivery](standards/delivery.md) | Project-local, pinned inputs; a committed candidate before a run | R-HOST-CHANGE, R-BAD-INPUT-SOURCE, R-PUBLISHED-MISTAKE |
| [S-OPS Observable operation and recovery](standards/operations.md) | Runs are bounded, stoppable and cleaned up; saves are removed only on user direction | R-SAVE-LOSS, R-RUNAWAY-RUN, R-OVERSPEND, R-KEY-LEAK |
| [S-AGENT Accountable agent-assisted work](standards/agents.md) | Named roles, written briefs, disjoint ownership, verified results | R-DELEGATION-ERROR, R-PRIVATE-DATA, R-WORKSPACE-LITTER |
| [S-DOCS Useful maintained documentation](standards/documentation.md) | Current pages are true, reachable and readable; things have descriptive names | R-STALE-DOCS, R-UNREADABLE-DOCS |
| [S-WORK Reviewable and proportionate changes](standards/work.md) | Work is scoped in issues, reviewed by risk and merged through the protected path | R-WRONG-MERGE, R-PUBLISHED-MISTAKE, R-STUDY-OVERRUN |
| [S-MIGRATION One current contract, coordinated migration](standards/migration.md) | Every reader and writer moves together; old versions are rejected | R-TECH-DEBT, R-REGRESSION |
| [S-EVIDENCE Claims with scoped evidence](standards/evidence.md) | A claim states what was observed; deciding studies are written down before they run | R-FALSE-CLAIM, R-EVIDENCE-LOSS, R-STUDY-OVERRUN |

The standards for [the player interface](standards/player-interface.md),
[player tooling](standards/player-tooling.md) and [testing](standards/testing.md) are
parts of S-ARCH, S-AGENT and S-CODE and are linked from them.

[Change and review cadence](standards/authority.md#change-and-review-cadence) describes
the working loop.
