---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# Player interface and ordinary interaction design

These rules are obligations for design and qualification. They do not claim that present
tooling satisfies them.

## What the model sees

- **Keep two forms.** Design the working context a model reads separately from the
  canonical records a machine keeps.
- **Return the smallest view that supports the decision.** Keep exact evidence by
  reference and expose detail on demand. The view still carries required IDs, current
  ownership, obligations, unknown effects and relevant limits of applicability.
- **Reveal in steps.** The current decision context comes first, then selected tool
  guidance and focused memory or evidence. Technical detail follows by exact retained
  reference when it is needed. A detail read must not silently change the target snapshot
  or grant authority.
- **Keep the form plain.** Images stay image parts. Avoid nested transport envelopes and
  repeated history.
- **Verify what arrives.** Check the actual loaded host's presentation as well as SDK
  return values, and measure whether context suffices by whether play actually continues.
- **Migrate together.** A changed caller or persisted contract moves under S-MIGRATION.

## What software does and what models do

- Software owns deterministic request binding, bounded collection, cursors, joins and
  idle waiting. It also automates deterministic verification, accounting and the
  classification of known failures.
- Models own intent, interpretation and learning judgments. For each model task, identify
  the interpretation or choice it supplies and when that can change a decision.
- Do not require a model to narrate facts that receipts already hold, and do not
  require a turn only to discover an empty work queue.
- The player selects optional reflection when novelty, recurrence or consequence
  justifies it. Escalation needs an unresolved question and an expected decision benefit;
  a mismatch alone is not enough.
- C-REVIEW checks this split at consequential changes rather than reviewing routine
  individual actions, and no automated check claims to judge semantic truth.

## Ordinary actions and optional shortcuts

Ordinary interface actions are the player's base capability. Semantic skills are optional
shortcuts and make stronger claims about those actions. Missing semantic coverage must
not prevent ordinary exploration or cancellation that is otherwise supported.

Optional accelerators and derived caches follow the same rule:

- Bound their working set, and forget or recompute candidates when appropriate. The
  growth of a historical cache must not become a lifetime limit on ordinary observation
  or input.
- Size a producer cache to the decision or handoff working set that the existing contract
  permits as one unit, with explicit exact rereads after eviction. Test the case that
  crosses the boundary; a local cache size is not a new semantic limit.
- Preserve durable evidence, current guards, explicit uncertainty and original resource
  accounting.
- Exercise exploration beyond the cache working set in the existing component and
  whole-runtime lanes. Integrity and storage failures still count as failures.

## Errors and correction

Separate three events: a rejected request, an unexpected outcome in the game, and an
actual loss of authority or uncertain delivery.

- A correctable request error must not revoke a healthy input scope.
- Classify a new caller-data error at the validation boundary, and only when it is
  positively identified. Do not infer nondelivery from an arbitrary exception, and do not
  treat a failure of trusted history or storage as a caller's mistake.
- Validation that runs before SDK submission must not direct the caller to collect an
  operation that does not exist.
- Pair each correction regression with an actual integrity or transaction fault.
  Preserve original costs, exact retry semantics and Pause.
- Reuse the existing ledger and OS contracts. Do not recompute a full semantic projection
  only to classify a rejected candidate.
- Review the whole observe, try, correct and cancel loop, including the raw-input
  fallback, and not only each adapter's successful path.

C-REVIEW checks this distinction and C-PORTABLE exercises regressions at the boundary.
Actual keyboard and mouse capabilities still need their separate C-NATIVE evidence.

This page is part of [S-ARCH Explicit architectural boundaries](architecture.md).

## Executable learning and game-family boundaries

For executable learning designs, distinguish stable platform implementation from
player-authored scripts, decision trees, strategies and learned detectors. Specify
which artifacts may evolve under the prospective adaptation policy, which local
computation/observation/input capabilities they receive, how executions retain
revision/outcome lineage, and how ordinary discovery resumes after surprise.
Review that substrate boundary rather than requiring lead or model approval for
each routine or action. Existing admissions remain governed by their actual
contract; a proposal cannot silently expand capabilities. Compilation, invocation
or agreement with a learned success detector does not establish task success,
generalization or useful cadence. C-REVIEW checks the distinction; C-PORTABLE and
C-NATIVE qualify implemented boundaries, with C-USABILITY retaining actual organic
adoption and responsiveness evidence. See the [research crosswalk](../research-executable-policies.md).

For gameplay and learning boundaries, explain which assumptions concern the
transport and which concern a particular game task or menu. Prefer the smallest
general observation/input/feedback mechanism over enumerating menu types or
engineering gameplay expectations. Shortcuts must retain a usable ordinary-input
fallback. Design for unseen variants and changes after a sequence of interactions,
including when a formerly useful procedure becomes wrong. C-REVIEW challenges
new special cases and asks why existing general mechanisms are insufficient.

Apply the charter's CDDA-class portability constraint to every new design. Name
game-specific assumptions, place engine/UI bindings in the integration boundary,
and keep player reasoning, memory, learning and orchestration independent of
specific menu names, engine objects and world rules. An optional semantic skill
may be game-specific; it cannot become a prerequisite for the general interaction
loop. Identify existing coupling as migration work instead of claiming portability
from an interface name. Review how a second game with different menus, time,
inventory and persistence would fit. Do not build a universal adapter framework
or compatibility layer without a demonstrated need.

[Standards index](../engineering.md).
