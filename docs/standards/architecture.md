---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-ARCH Explicit architectural boundaries

Describe responsibilities, owners, inputs/outputs, state/concurrency, authority,
failure/recovery and acceptance for each consequential boundary. Keep controller
logic independent of HTTP and build tooling. Explain consequential alternatives,
maintenance cost and reversal triggers in a brief/ADR. Review boundary changes
before implementation; keep current architecture synchronized afterward.
Maintain a reviewable hierarchy: project context/responsibilities → affected
component and internal design → exact contracts/state/callers → implementation.
Each important view names its parent, children or source, owned state and limits;
use diagrams where they help the reader challenge the design. The higher the view,
the more it must explain user consequences and tradeoffs without code knowledge.
Project standards apply throughout; component invariants specialize them without
silently weakening them. An unchanged parent needs an impact statement and link,
not another approval. Scope cross-cutting changes across all affected branches.
Apply S-CODE's reuse review to infrastructure and architectural tool choices.
Cross-check consequential input, memory, learning and autonomy changes against
prior architecture, contracts, research and actual campaign findings. Record what
is retained, changed or in conflict, source applicability limits and unverified
assumptions in the existing brief/design. C-REVIEW checks that crosswalk; links alone
do not establish agreement or research currency. Keep current behavior distinct
from proposals and retire superseded guidance when implementation changes.
For agent/memory boundaries, identify the active and background paths, automatic
bookkeeping versus model judgment, two-way feedback, version/applicability rules
and resource costs. Reuse actual receipts for observable events; distinguish
context exposure, explicit selection, delivery, observed effect, interpreted
success and causal usefulness. Preserve unknown attribution. Design autonomous
play so software/player roles own routine reasoning and learning; the engineering
lead must not become the slow path or a per-procedure approver. Advisory learning
may remain provisional and revisable; current authority and delivery accounting
must not depend on eventual correctness. C-REVIEW checks these distinctions;
functional behavior and claims of improvement need their separate evidence.

Read [Player interface and ordinary interaction design](player-interface.md) for this part of the standard.

Read [Executable learning and game-family boundaries](player-interface.md#executable-learning-and-game-family-boundaries) for this part of the standard.

[Standards index](../engineering.md).
