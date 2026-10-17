---
owner: lead
status: historical
date: '2026-10-17'
scope: Native interruption investigation and first gameplay design; no runtime implementation or native demonstration
---

# Gameplay foundation design acceptance

Scope: issues #6 and #17, based on harness `806c0ba60141ce5601f734865720d6c87047afc4`
and pinned CDDA `7b2efa5cea38e4d4d97dd0e63b28b9148623da59`. The publication PR/commit
linked from those issues identifies the final documentation candidate. This is design
acceptance, not evidence that v2 recovery or autonomous waypoint play exists.

## Evidence and decisions

The [brief](../changes/004-gameplay-foundation.md) defines the scoped outcomes;
[ADR 005](../decisions/005-gameplay-foundation.md) records alternatives and reversal
conditions. The native and gameplay contracts specify future implementation.
The [source manifest](2026-10-17-gameplay-design-sources.json) identifies inspected
bytes, pinned upstream, reuse versions and local evidence/retention limits.

| Requirement | Reviewed evidence and outcome |
| --- | --- |
| Actual engine interruption/error paths | Native design traces activity DEFAULTMODE, cancellation query, interruptibility/cleanup and raw debug input. No direct cancellation fallback; explicit unsupported cases and native probe matrix. |
| Useful first task and observation limits | Waypoint and return, two verified stages, at most eight movement primitives. Missing route evidence stops; no inventory, hidden map, damage/trap or water-safety claim. |
| Explicit architecture and feedback | Versioned task/evidence/skill/candidate/result records; positive normal-play admission; per-primitive progress, budgets and escalation; one controller lease and native input authority. |
| Partial, unknown and completion semantics | Displacement is independent of stop status; unknown side effects freeze, no replay; retained waypoint plus later origin evidence is required for completion. |
| Reuse rather than new framework | Existing controller/JSON Schema selected for the bounded slice. Tagged py_trees/transitions metadata and licenses checked; CodeHack reference pinned. No dependencies installed. |
| Reviewable next work | Eight bounded handoffs under #7/#19/#22 with ownership, estimates, dependencies and validation lanes. Implementation and real-play outcomes stay open. |
| Diagrams and owner navigation | New native recovery flow rendered and inspected at 1000-pixel window width: readable labels, no clipping; semantics include uncertain fallback and explicit resume. Existing tiered diagram remains linked. Overview links the brief and contracts. |
| Maintenance | Research #26 and controls #13 retain review ownership/triggers; ADR defines library adoption/reversal. Native implementation must update C-PROTOCOL/current docs together; this design does not activate proposed controls. |

## Independent review and repairs

Read-only explorers covered native source, current gameplay interfaces and reuse.
The lead inspected actual files and primary sources; an explorer's mistaken 2026 date
for transitions 0.9.3 was corrected to 2025-07-02 using the official release API.

A clean-context reviewer found five actionable design gaps. The lead resolved them:

1. Later Pause could leave a queued recovery YES valid. Added a durable host boot/
   revocation token on both input channels, a final native commit gate, and before/
   after-claim/commit probes; already committed inputs remain an explicit limit.
2. Relative origin changes on same-process reload while v1 session persists. V2
   rotates world-scoped sessions on entry/exit and invalidates old task history.
3. Existing CLI/HTTP gameplay could bypass supervisor ownership. Added one controller
   run lease at every ingress, admission epochs, queued-command rejection and takeover.
4. Pause continuation contradicted same-run completion. Separated stable task history
   from revocable execution epochs, retained budgets and exact checkpoint admission;
   assisted completion is separate from uninterrupted benchmark success.
5. A three-call budget structurally prevented the primitive baseline from finishing.
   Changed the default ceiling to ten, measured call count as an outcome and required
   development-pilot budget feasibility before a matched held-out comparison.

The repair review confirmed all five original gaps addressed at contract level. A
dependency check also separated #22 code integration from #24 downstream native/model
acceptance to avoid a circular completion gate. Final review and live tracker evidence
are linked from the two investigation issues; issue states are authoritative. The
final independent review found no unresolved actionable design or decomposition
findings and checked the diagram against its contract.

## Checks and limits

The common portable check passed: 84 Python tests, four viewer regressions, Ruff/import
boundaries, JavaScript syntax, local document links/metadata, governance and diagram
receipts/rendering. Unchanged existing SVGs were retained to avoid renderer-generated
ID churn; the receipt hashes the actual checked-in sources/outputs. The new recovery
render was inspected separately for meaning and readability.

No native code, runtime configuration, packages, global environment, saves or running
processes were changed. No native build, recovery probe or model/gameplay experiment
was executed. #8 retains real cancellation/debug/nested/reload validation; #19 retains
native observation acceptance; #24 retains complete gameplay/model comparisons.
Exact hook coverage, prompt capture timing, stop latency and activity backlog behavior
remain acceptance risks until those tests run. A green documentation CI cannot resolve
them. Provider/model choice and a positive approved spend budget remain prerequisites
to live model integration, not implicit decisions of this round.
