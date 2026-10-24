---
owner: lead
status: historical
date: '2026-10-24'
scope: Design and development record preserved on this date; current architecture/protocol
  and GitHub own behavior and remaining work
---

# Refresh the selected checkpoint at operation entry

[Independent007](../acceptance/2026-10-20-independent-mission-seventh-attempt.md)
exposed a freshness race: a source can still pass the entry age check and expire
before final dispatch. Conditional refresh leaves the player dependent on timing
between model/tool calls. The regression crosses that boundary using the real
freshness validator and reproduces the failure against the former implementation.

Reuse the existing operation-entry Observe, evidence store and typed
SourceRevalidation. Capture once before the first proposal for lifecycle controls,
initial lifecycle Resume, stage/save/identity actions, ordinary semantic controls,
navigation and owned quit confirmation. Require the original source still be the
exact selected checkpoint. Interpreted pixels and lifecycle state require exact
PNG equivalence; native-row/navigation decisions use the existing native-state
relation. Resume records its exact checkpoint relation without constructing a
lease before it has one. Each operation retains its immutable request and original
game-time anchor; every next primitive still passes independent controller/native
freshness and authority checks.

This adds a bounded observation/evidence cost per operation, not a model request
or approval per key. Root/child/mission deadlines, input and evidence ceilings,
cleanup reserve, Pause, single ownership and unknown-delivery behavior remain.
Changed state/pixels, expired replacement or lost authority still stop. There is
no age-threshold increase, retry loop, new executor, schema version, budget renewal
or permission change. No new library is needed: existing mechanisms cover the gap.

Lead owns the coupled runtime/tests/docs; independent source review challenges
lineage and negative boundaries. C-PORTABLE covers near-expiry success, unchanged
request/deadline/accounting, changed pixels, Pause and replacement expiry. A
pre-existing after-frame storage fault must remain attached to the correlated
input ACK, allowing the new pre-input Observe; retain all unknown-after-input
assertions and the initial failed test. The first full common run retained one
capacity-tail fixture failure among 1,236 tests: its original allocation left no
usable frame after the added entry capture. Add that single frame to the test's
initial allocation, preserving the assertion of exactly one usable frame and all
insufficient-capacity rejection checks. Production ceilings are unchanged.
C-NATIVE remains the new FULL independent
mission with real memory succession and normal lifecycle. Synthetic red/green and
passing CI do not accept native outcomes. #168 owns the repair; #144/#145 own
integrated delivery/readiness. Revisit when evidence freshness or operation entry
changes, or measured observation cost exceeds the interactive-play budget.
