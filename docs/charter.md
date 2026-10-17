---
owner: maintainer
review_trigger: Goals, constraints, stakeholders or assumptions change
status: active
---

# Purpose, constraints and principles

The user owns product direction and constraints.

## Purpose and success

Let the user watch and direct understandable, authentic graphical CDDA gameplay
performed by an agent. Success includes trustworthy control, a maintainable
harness, reproducible setup, and a project the user can understand and steer.
The user reviews purpose, outcomes and tradeoffs; maintainers need clear contracts
and evidence; contributors need reproducible entry points; upstream compatibility
requires a small understood patch and preserved provenance.

## Constraints, assumptions and decisions

User constraints: windowed operation; project-local new dependencies, data and
caches or explicitly recorded temporary builds; preserve the global environment;
version control; authentic engine behavior; no hidden state or save editing to
win a demonstration. Historical environment exceptions remain in the
[environment ledger](environment.md); they are not precedent for new changes.

Current assumptions: one local operator, game and controller; active Codex chat
provides high-level planning; this Mac is the validated host. Recheck these before
concurrency, unattended operation, distribution or platform expansion.

Current technical decisions are [native Tiles](decisions/001-native-platform.md)
and [a local serialized bridge](decisions/002-local-contract.md). They may change
when evidence or requirements change. They are not permanent principles.
General autonomous survival, combat policy and cross-platform support remain
outside current capability; future scope needs explicit acceptance conditions.

## P-AUTHORITY Preserve user authority

The user can understand control ownership, stop subsequent remote dispatch, and
use native takeover. Visible limits on interrupting engine-owned activities are
part of the promise. Prefer control clarity over action throughput.

## P-TRUTH Preserve game truth

Only player-visible information informs ordinary play. Report engine observations
and verified outcomes with provenance. Distinguish a delivered input from a
successful objective; preserve failures as evidence.

## P-UNCERTAINTY Make uncertainty explicit

Staleness, lost acknowledgments, conflicting observations and unknown outcomes
must be represented. Stop and reconcile uncertain side effects before another
action. A fresh observation cannot retrospectively prove an old objective.

## P-ISOLATION Contain and reproduce the environment

Know what is installed, where it writes, how to rebuild it, and how to remove it.
Use pinned, verified inputs and project-scoped tooling. Clean setup and recovery
are product capabilities with maintenance obligations.

## P-CHANGE Design for controlled change

Separate responsibilities around likely changes, explicit authority and testable
contracts. Select tools by capability and total maintenance cost. Keep alternatives
and reversal conditions for consequential decisions. Evaluate mature tools and
existing libraries before implementing generic infrastructure; record why custom
code is needed when reuse cannot satisfy the requirement. Avoid speculative frameworks.
Maintain one current contract per boundary. Migrate the whole system together;
do not carry backward-compatibility paths or mixed-version operation.

## P-KNOWLEDGE Maintain trustworthy knowledge and evidence

Facts have one authoritative home. Current guidance, proposals, historical
choices and observations have explicit status. Keep evidence sufficient to
assess claims, and improve or retire controls based on what they detect.

## P-REVIEW Make the project understandable and governable

Progressive detail lets the user review purpose, behavior, limitations and tradeoffs
without reconstructing code or chat history. Preserve consequential details in
high-level explanations. Cohesive changes and clear briefs protect user attention.

## Quality priorities and conflicts

User constraints and authentic behavior take precedence over speed. Within those
bounds, prioritize control clarity, recoverability, watchability, maintainability
and reproducibility. Measure efficiency separately from correctness or survival.
A tradeoff affecting the user's guarantees must be surfaced explicitly; the lead
may adjudicate ordinary implementation choices within authorized scope.
Internal exceptions cannot waive user constraints.

Translate principles into concrete scenarios and [standards](engineering.md).
Examples: stale input causes no dispatch; a timeout cannot trigger automatic
replay; a new contributor can follow setup; the user can find current limitations
and the next decision from the overview. Controls and their limits are in the
[control map](controls.md). Principles themselves require reasoned review, not
an assertion that a syntax checker proves them.
