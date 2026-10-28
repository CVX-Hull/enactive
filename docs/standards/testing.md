---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# Behavioral testing and timing evidence

Test observable contracts, adversarial transitions and meaningful regressions.
For changes to ordinary interaction, procedural applicability or transfer, select
relevant unfamiliar menu labels/layouts/representations and a transition whose
behavior changes after a controlled number of steps.
Verify observe/attempt/reject-or-return/reconsider/cancel/continue using the same
general input path. Keep the test's game behavior separate from adapter
assumptions; a fixture that only reproduces known categories cannot establish
generalization. Reuse unittest subtests through the maintained test runner, real-component fixtures and
retained trajectories before adding any evaluation framework. Report tested
variation, cost and remaining gaps; finite cases cannot prove arbitrary
adversarial robustness or causal learning benefit.
Portability changes must exercise the proposed boundary with an independently
shaped second-game fixture and explicitly identify the real-game qualification
still missing. A synthetic adapter or renamed CDDA fixture does not establish
actual cross-game support. Keep native integration tests separate from shared
behavior tests; new game bindings migrate current contracts together.

Separate causal concurrency/deadline assertions from measured performance targets.
Use synchronization or an isolated controlled clock so fixture setup cannot consume
the short deadline under test; keep real bounded watchdogs and adversarial checks.
Test helpers reading live private state must use that component's existing
synchronization. A collected result does not establish writer quiescence; preserve
the integrity assertions instead of adding sleeps or weakening them.
Review these choices through C-REVIEW; C-PORTABLE executes the resulting regressions.
The [testing guide](../testing.md) maps each layer's distinct failure responsibility.
Maintain risk-to-evidence navigation for major component responsibilities: product
consequence, required invariant/current contract, existing control mechanism,
representative assertions/evidence and their limits. Exact contracts and assertions
remain authoritative. Review the association when those facts change, across
affected producers and consumers. Distinguish the runtime mechanism from the
portable executor, compiled fixture and actual native/campaign/manual-review lane.
Use registered native test metadata selectively for consequential obligations;
do not annotate every test or infer semantic completeness from tags or counts.
Unknown registration is rejected by native pytest; C-REVIEW owns semantic fit.
Before adding expensive integration permutations, identify the invariant and lowest
sufficient boundary; keep representative composition/transport cases where they add
coverage. Similar names and equal counts do not establish redundant or adequate
tests. Review removals against assertions, failure history and retained coverage.
Preserve fresh mutable state; measure fixture/setup cost before inventing caches.
Focused checks support development gameplay; full portable regression belongs at
broad integration, not each attempt. CI selects the reviewed documentation/component/
full scope under the delivery policy. C-REVIEW checks scope and failure coverage;
C-MAINTENANCE revisits duplication, flakiness and cost when they obstruct delivery.
Changed expectations require a contract-grounded reason, not agreement with
newly generated output. Do not weaken a check to conceal a failure. Syntax and
behavior checks are automated; style, typing completeness and decomposition
currently use review. No comprehensive static type/format gate is claimed.

Standard and principle/control mapping: [S-CODE Maintainable implementation](../engineering.md#s-code-maintainable-implementation).

[Standards index](../engineering.md).
