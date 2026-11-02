---
owner: maintainer
review_trigger: Goals, constraints, stakeholders or assumptions change
status: active
---

# Purpose, constraints and principles

The user owns product direction and constraints.

## Purpose and success

Let the user watch and direct understandable, authentic gameplay performed by an
agent across CDDA-class games, starting with Cataclysm: Dark Days Ahead.
Success includes trustworthy control, a maintainable
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

Current product constraint: designs must apply across CDDA-class games, not depend
on this specific Cataclysm implementation. The working scope is turn-based
survival/roguelike games with graphical or textual interfaces and persistent,
long-horizon state. Game observations, actions and optional shortcuts may differ;
the class is not defined by CDDA menu names, data formats or engine hooks. Record
any narrower assumption explicitly. Broader game genres are a future extension,
not a reason to build speculative infrastructure now. Only the user may relax
this constraint; record a later relaxation as a versioned decision.

Gameplay must be apparently responsive to the observer. Admit the whole
host/model/context/execution configuration on measured useful progress and
quality. A slower model is acceptable only where useful execution covers its
delay and the complete configuration still meets the declared cadence. Capability
alone does not justify stalls. Numerical budgets belong in the prospective
evaluation, with loading and long activities separately visible and bounded.

Selected architecture constraint: the harness exposes only basic computer
observation/control and mechanical custody, delivery, cancellation and resource
limits. The entire playing system owns game semantics, including menus,
inventory, activities, identity, save/load, progress and loops. A game-specific
classification cannot be a prerequisite for basic input. [ADR006](decisions/006-computer-control-boundary.md)
records the migration and limits; this direction is not a claim that the current
runtime already implements it.

Current assumptions: one game/controller and one designated deciding player;
the active player owns planning and ordinary interpretation, with a separately
assigned advisory actor for reflection. The engineering lead owns the project,
admission and verification. This Mac is the validated host. Recheck these before
additional concurrent games, unattended operation, distribution or platform expansion.

Current validation uses CDDA on this Mac; family-wide support is not yet qualified.
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

Choose architecture, tools and process by the value they add to the overall
objective: reliable independent play, useful learning and a reviewable experience.
Consider capabilities we can adopt or acquire across the existing ecosystem,
including the game engine, platforms, libraries, tools, frameworks and services.
Prefer the smallest effective integration and total delivery/operating cost over
custom ownership or completeness for its own sake. Remove work that no longer
contributes; adopting a framework is not itself progress.
Value includes long-term capability and learning, not only immediate feature
delivery. Invest in accelerators and enablers when their expected repeated use,
future cost reduction, research value or new options justify the initial effort
and upkeep. Keep assumptions and a useful reassessment point explicit; lack of an
immediate payoff alone is not a reason to reject an investment.

Separate responsibilities around likely changes, explicit authority and testable
contracts. Select tools by capability and total maintenance cost. Keep alternatives
and reversal conditions for consequential decisions. Evaluate mature tools and
existing libraries before implementing generic infrastructure; record why custom
code is needed when reuse cannot satisfy the requirement. Avoid speculative frameworks.
Rely on documented, configured database, operating-system and library guarantees.
Add project logic for the requirements those contracts do not cover, with assurance
proportionate to this local game's actual deployment and consequences. Repeated
checks, recovery layers and abstraction frameworks need a concrete benefit; more
defensive code is not inherently more reliable or maintainable.
Maintain one current contract per boundary. Migrate the whole system together;
do not carry backward-compatibility paths or mixed-version operation.

Reduce uncertainty through meaningful working slices and real development play
before paying for comprehensive qualification. Match assurance to the claim and
consequence; preserve failures and strengthen acceptance once the behavior composes.

## P-GENERALITY Build the capacity to discover

Prefer interaction, search, learning and feedback mechanisms that remain useful
as tasks and interfaces change. Following the [Bitter Lesson cross-check](research.md#generality-and-the-bitter-lesson),
engineer the substrate for discovery; do not make our catalogue of game knowledge
the boundary of what the player can try. Domain shortcuts belong in the playing system as replaceable aids
with explicit scope and demonstrated value. The player must be able to reconsider
them using current observations and ordinary interface actions.

Keep shared player, memory, learning, orchestration and evidence responsibilities
separate from game-specific observation/input bindings and knowledge. Preserve
identity, provenance and uncertainty across that boundary. A CDDA-specific
integration may be necessary; requiring it throughout the shared design is not.

Changing labels, layouts, menu implementations or behavior over time should call
for player adaptation, not an engineer-authored handler for every variation.
This is a design preference and evaluation obligation, not a claim of universal
learning or permission to remove provenance, user control or finite limits.

As we apply Sutton's lesson, it concerns capability: what the player can do
should grow with search, learning and computation. We do not apply it to
evidence. Classical methods (statistics, measurement, causal identification,
control theory) verify claims, bound error and decide evaluations. They may
also supply structure inside the player when one game-independent procedure
fits it to each game from player-visible experience. Agents and learning
propose, search and iterate; classical checks with stated assumptions judge
claims about the result. Avoid the worst of both: hand-tuned pipelines that cap
what the player can try, and claims that nothing independent checks. A
classical component inside the player gives way when a general method matches
or beats it on the same pre-registered evaluation, including the declared
cadence and cost.

State each player capability as an instance of an explicit structure: its
objective, signals and invariants, drawn from whichever field fits it, not only
from LLM and agent work. The structure is what lets the capability be optimized
and analysed. LLM and agent calls fill defined roles inside it and are justified
against it; they do not replace it.

## P-KNOWLEDGE Maintain trustworthy knowledge and evidence

Facts have one authoritative home. Current guidance, proposals, historical
choices and observations have explicit status. Keep evidence sufficient to
assess claims, and improve or retire controls based on what they detect.
Separate durable evidence from the context needed for the next decision.
Retaining a complete record does not require repeatedly showing it to a model.
Preserve exact recall, unfinished obligations and uncertainty while keeping the
active working context sufficient and proportionate.

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
