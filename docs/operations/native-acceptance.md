---
owner: maintainer
review_trigger: Changes to this operating task, supported setup or recovery behavior
status: active
---

# Native acceptance lane

Required after relevant native/input/renderer/protocol/source-pin/compiler changes,
and before new native support claims. Complete relevant probes on an isolated
project profile, windowed, without hidden information or edited saves:

1. Commit the source checkpoint under [S-DELIVERY](../standards/delivery.md#s-delivery-reproducible-and-isolated-delivery), then build the pinned source using setup; record compiler, inputs and binary hash.
2. Inspect actual native and spectator frames, including menus and popup text.
3. Exercise observation, bounded input, stale authority, pause and native takeover.
4. Exercise the changed behavior plus timeout/reconciliation and restart as relevant.
5. Use normal save/load if persistence or session identity is affected.
6. Record each outcome, unknown/failure and scope in a dated report and small manifest.

The [MVP report](../acceptance/2026-10-17-mvp.md) is an example and historical evidence,
not an executable current pass. Portable tests never substitute for this lane.
A new automated native replay/probe runner remains a documented coverage gap.

## Passive skill acceptance

The movement skill is a library, not a new CLI command or live player. A manual
acceptance caller binds TaskSpec and retained start evidence, requests one proposal,
reserves an after-frame, dispatches once through the existing controller, retains
the exact logical/native identity mapping, and settles once. Follow the
[skill contract](../contracts/movement-skills.md#passive-bounded-movement-skills); do not pass a controller
walk loop as a primitive or automatically Observe/retry an unknown input.

The [round 009 report](../acceptance/2026-10-17-bounded-skills.md) separates actual native
frames from injected evidence faults. Preserve raw unsupported receipts outside
the task store. A rendering failure cannot be repaired by substituting a later
frame. Save normally and stop only owned processes after acceptance.

[Operations index](../runbook.md).
