---
owner: lead
review_trigger: Player tools, lifecycle phases or deciding-player context changes
status: active
---

# Deciding player's working guide

Use this page, the frozen mission brief and current selected tool descriptions as
the initial working set. This is interface guidance, not a tactical plan. The
[protocol](protocol.md#integrated-mission-lifecycle) owns the contract; inspect a
specific section only when needed. Engineering/source archaeology belongs outside
the deciding hot path. Do not recursively search `.runtime`, prior host traces,
saves or the engine to learn how to call tools. They are not a player knowledge
base. A missing usable contract is an ergonomics defect to report, rather than a
reason to read the entire repository during every game.

## Calls and returned evidence

- `enactive_snapshot` gives a descriptive snapshot handle and the selected source
  image. Select those exact handles for a new intent. Software supplies mission,
  epoch, source bindings and stable child lineage. A snapshot never Resumes.
- Default `player-view/2` keeps current decision state and advertises `detail_sections`.
  Use `enactive_detail(snapshot_id, section)` for exact as-of configuration, metrics,
  receipt, progress, native or source metadata when needed. It never refreshes or
  grants authority. Use `enactive_source` when you need the actual retained image.
  Software verifies hashes and binds requests; do not reconstruct omitted audit data.
- `enactive_skill` chooses intent and finite limits. Use a supported semantic goal
  when useful, ordinary `direct` keys/text/clicks for unfamiliar ordinary gameplay.
  Inspect the returned image/effect; a delivered input is not task success.
- Read the description/schema of the **one tool needed**, rather than printing
  every declaration. Keep returned text, typed image parts and `isError`; do not
  print image data as text or opaque tool objects. Keep simple returned IDs.
  When forwarding through an orchestration tool, forward content blocks once;
  `text(JSON.stringify(result))` prints the whole transport envelope and can
  duplicate its text/structured value. This guidance is not an automatic host fix.
- A pending/unknown result requires `enactive_result` for its original operation.
  Never invent a fresh ID to replay it. Same-actor tool calls serialize. A local
  refusal can permit a new decision only within the returned documented scope.
- `enactive_context` retrieves bounded memory; `enactive_source` retrieves an exact
  retained image. `enactive_remember`/`correct` retain fallible supported knowledge
  and Work. Software records procedure/action/result attribution; no per-key
  narrative or usage report is required.

## Current registered CDDA lifecycle

This adapter has specialized setup/identity/save proofs. Ordinary gameplay's raw
fallback does **not** currently make every creation shortcut or setup receiver
supported. A different game binding or changed screen needs its own capability
assessment; these stages are not a universal menu taxonomy.

| Current situation | Interface operation and verification |
| --- | --- |
| Admitted, no owned child | `enactive_lifecycle`, `scope=new_root`, `operation=launch`, no source. Launch sends no creation intent and establishes no character identity. |
| Owned paused main menu | A new lifecycle root with `operation=create` starts fresh setup. Use that root's `scope=lifecycle` for children. Entire setup, edits and confirmations share its original limits. |
| Creating a world/character | Menu/editor skills interpret the current visible screen. World/character editors must match the admission. A quick start that generates another identity does not satisfy the named scenario. |
| Ready to commit the supported world form or final character description | A separate same-root `enactive_lifecycle` create call commits the stage. Inspect the resulting question; a menu key is not a substitute for this registered transition. |
| Confirmation | A same-root menu skill supplies the exact visible interpreted question and answer. Setup confirmations require the previously committed stage. Never assume a new dialog is the old one. |
| Expected transition has unknown ACK | Explicit Observe can retain diagnostic transition evidence **when its registered candidate exists**. Same-root lifecycle reconciliation leaves the ACK unknown. Missing candidate/source is currently an unsupported boundary; do not fabricate evidence. |
| Reconciled transition, paused provisional character | A separate same-root lifecycle call Readmits. Then inspect `purpose=character_identity`, read the actual character screen, retain truthful world/character Claims, dismiss it and separately adopt through the same lifecycle operation with those Claim IDs. Adoption, not launch or Observe, starts ordinary input authority. |
| Normal ending | New `save` lifecycle root, interpreted save confirmation, explicit transition reconciliation/checkpoint, owned `exit`, then `finish` with the appropriate actual outcome. New-child reload currently requires this mission's own saved checkpoint; cross-mission checkpoint loading is not implemented. |

Let software form wire records. Choose the goal, selected evidence, interpretation,
limits and semantic fields required by the current schema. Do not write request
JSON files or reconstruct wire headers. The lifecycle tool's operation is reused
for stage commit/reconciliation/readmission/adoption; consult the returned phase
receipt, not just the operation name. A tool error that gives no usable next step
is a defect, not authority to guess or bypass it.

## Resources, stopping and context

Use the frozen coupled forecast and stop rule. Current normal Save/exit still
consume **pre-reserve** input/wall/frame capacity: the declared cleanup reserve is
not an extra spendable normal-ending allowance. Begin ending early enough for
every remaining step. Children, Observe and handoff cannot reset original limits.

Keep the current objective, task/Work, source, unresolved effects, active phase,
remaining capacity and relevant memory/procedure invalidators in working context.
Retrieve older detail for a reason. Do not wait for optional advice to continue
justified play. User Pause/takeover and real authority/delivery faults retain their
stopping behavior. If a required capability is absent, settle handles, retain the
failure and permanently quiesce under the brief; never ask the user/lead to supply
a gameplay key or repair memory. The lead assesses closed evidence independently.

This guide's maintenance check is a focused comparison with current tool schemas,
phase receipts and lifecycle implementation whenever its review trigger fires.
[The runbook](runbook.md#typed-mission-requests-and-the-player) owns detailed recovery
and operator procedure. Tests and native evidence qualify their actual scope;
this guide does not establish a new capability.
