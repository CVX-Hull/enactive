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
  Routine results omit repeated configuration, technical receipt bindings and the
  general normal-play action vocabulary. Menus, visible scenes and uncertainty stay.
  An explicit `image_presentation` note can say that implicit pixels are unchanged
  in this player context; use snapshot/source for an actual redisplay when needed.
  This is not a source-read declaration or proof that an action succeeded.
- `enactive_skill` chooses intent and finite limits. Use a supported semantic goal
  when useful, ordinary `direct` keys/text/clicks for unfamiliar ordinary gameplay.
  Inspect the returned image/effect; a delivered input is not task success.
- Read the description/schema of the **one tool needed**, rather than printing
  every declaration. Some hosts reduce nested argument schemas to `unknown`; this
  is not a usable field contract. If the frozen brief supplies focused interface
  references, read only the needed tool/skill or memory variant. These are exported
  from the current SDK schema, not example tactics or request JSON files. Do not
  guess payload fields, dump all declarations or search implementation code.
  Prefer the returned `next_snapshot` when it is sufficient; another snapshot is
  an explicit read, not a mandatory step after every settled operation. A detail
  read or `source_id=null` uses the chosen snapshot as-is; it does not refresh an
  older selection. If a lifecycle call refuses a stale binding with no input,
  use the returned current snapshot for a separate new decision. No automatic
  retarget, replay or allowance renewal occurs.
  Keep returned text, typed image parts and `isError`; do not
  print image data as text or opaque tool objects. Keep simple returned IDs.
  When forwarding through an orchestration tool, forward content blocks once;
  `text(JSON.stringify(result))` prints the whole transport envelope and can
  duplicate its text/structured value. This guidance is not an automatic host fix.
- A pending/unknown result requires `enactive_result` for its original operation.
  Never invent a fresh ID to replay it. Same-actor tool calls serialize. A local
  refusal can permit a new decision only within the returned documented scope.
  A known native rejection is not an uncertain delivery or successful game effect.
  If healthy owned scope remains, explicitly Observe and choose a new action under
  the original limits; do not replay the rejected request or assume an editor changed.
- `enactive_context` retrieves bounded memory; `enactive_source` retrieves an exact
  retained image. `enactive_remember`/`correct` retain fallible supported knowledge
  and Work. Software records procedure/action/result attribution; no per-key
  narrative or usage report is required.

## Current registered CDDA lifecycle

This adapter has specialized creation/identity/save proofs. Owned create/load/save
menus accept ordinary keys/text/clicks, including unfamiliar receivers. A shortcut
that bypasses the committed creation route cannot prove fresh character creation.
These CDDA stages are not a universal menu taxonomy; native qualification of the
new lifecycle fallback remains pending.

| Current situation | Interface operation and verification |
| --- | --- |
| Admitted, no owned child | `enactive_lifecycle`, `scope=new_root`, `operation=launch`, no source. Launch sends no creation intent and establishes no character identity. |
| Owned paused main menu | Use `operation=create` for a fresh admission, or `operation=load` for an explicit initial-load admission. Use that root's `scope=lifecycle` for children. Entire setup shares its original limits. |
| Creating a world/character | Menu/editor skills interpret the current visible screen. World/character editors must match the admission. A quick start that generates another identity does not satisfy the named scenario. |
| Ready to commit the supported world form or final character description | A separate same-root `enactive_lifecycle` create call commits the stage. Inspect the resulting question; a menu key is not a substitute for this registered transition. |
| Confirmation or unfamiliar setup dialog | Use a same-root interpreted menu skill when applicable, or `direct` input to try/cancel through the visible interface. Inspect the actual response. Successful creation still needs the committed character route; a delivered key or familiar question alone proves no transition. |
| Published lifecycle input has an uncertain/unexpected outcome | Explicit Observe can retain actual diagnostic evidence under its original private dispatch custody. For an expected create/load/save transition, use `enactive_lifecycle` again with the same operation, `scope=lifecycle` and original root `phase_id`; do not use ordinary `enactive_reconcile`. The ACK stays unknown. A wrong-tool refusal preserves only a positively healthy expected transition and its original limits. Diagnostic-only evidence has no executable phase or adoption/reconciliation authority. Normal cleanup of an unadopted/wrong-identity session remains unsupported; do not fabricate proof or replay input. |
| Reconciled transition, paused provisional character | A separate same-root lifecycle call Readmits. Then inspect `purpose=character_identity`, read the actual character screen, retain truthful world/character Claims, dismiss it and separately adopt through the same lifecycle operation with those Claim IDs. Adoption, not launch or Observe, starts ordinary input authority. |
| Normal ending | New `save` lifecycle root, interpreted or ordinary confirmation, explicit transition reconciliation/checkpoint, owned `exit`, then `finish` with the appropriate actual outcome. Returning to the same normal session cancels Save without a checkpoint claim. Later reload requires this mission's own saved checkpoint. An explicit initial-load admission instead establishes new visible identity and accounting; old authority/world facts are not imported. |
| Abandoning menu-only setup | Return organically to the same owned main menu. A new `exit` request can revoke settled setup without input; then explicitly Observe and use a new finite normal-exit root. A fresh Observe and this zero-input MAIN_MENU abort remain available after local setup expiry under healthy custody and global limits; they cannot renew expired inputs or cancel another form. This does not clean up an unadopted normal session. |

Let software form wire records. Choose the goal, selected evidence, interpretation,
limits and semantic fields required by the current schema. The lifecycle summary's remaining wall/primitives are software-derived as-of values; use them to choose timely closure, not as a renewed allowance. Do not write request
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
