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

- An admitted mission without an owned child starts with source-free
  `enactive_lifecycle(operation=launch, scope=new_root, source_id=null)`. Select
  create/load from its returned menu. This startup contract belongs in initial
  context; progressive reference reads must not omit the interface entry point.
- `enactive_snapshot` gives a descriptive snapshot handle and the selected source
  image. Select those exact handles for a new intent. Software supplies mission,
  epoch, source bindings and stable child lineage. A snapshot never Resumes.
- Default `player-view/3` keeps current decision state and advertises `detail_sections`.
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
  Ordinary `direct` inputs use `perception=null`; visible-control interpretations
  belong to menu/edit/item controls. Inspect the returned image/effect; a delivered
  input is not task success.
- An eligible Procedure/3 can contain `program={language:javascript/1, source:...}`
  or null for advice. A `program` skill starts a new root, explicitly selects that
  revision and supplies initial `goal.state`, intent, expected outcome and interrupt
  consent with `perception=null`. JavaScript `step(view,state)` returns exactly
  `{status,state,input,reason}`: act proposes ordinary key/text/click, yield/done
  require null input. Omit click geometry; software binds it from the current view.
  The same writer applies original finite limits, records sources/actions/results
  and stops on unknown delivery. Done is program termination, not verified success.
  View `program-view/1` contains current category/actions/in_game/ui/scene/geometry
  and boundary kind/input_receiver. It contains no pixels; null UI/scene means
  unavailable. Use ordinary image-informed exploration where the routine lacks
  evidence. Existing prompt children remain ordinary/semantic controls; do not
  replace their root with a new program. Code/state bounds and engine faults are
  described in the [execution contract](changes/061-player-program-execution.md).
  The summary is returned automatically; read exact continuation only when needed
  through `enactive_detail(next_snapshot.snapshot_id, progress)`.
- MCP assigns each new request ID and waits up to15 seconds for its original
  result; do not supply `request_id` or `wait_seconds`. A new invocation is a new
  intent, never a retry. Pending/uncertain results require `enactive_result` with
  the returned original ID. If an error includes `original_collection`, use those
  exact collection arguments when dispatch is uncertain. Validation can fail
  before staging, so collection may be unavailable; the error itself proves
  neither delivery nor nondelivery. After producer restart, collect a retained
  original ID; an actual active-operation ID can help, but settled operations
  disappear from that status field. If the identity is lost, quiesce rather than
  recreate or replay the action. Advisory next waits up to40 seconds without model
  polling; it preserves the original deterministic job claim and deadline.
- Read the description/schema of the **one tool needed**, rather than printing
  every declaration. Some hosts reduce nested argument schemas to `unknown`; this
  is not a usable field contract. If the frozen brief supplies focused interface
  references, read only the needed tool/skill or memory variant. These are exported
  from the current SDK schema, not example tactics or request JSON files. Do not
  guess payload fields, dump all declarations or search implementation code.
  Prefer the returned `next_snapshot` when it is sufficient; another snapshot is
  an explicit read, not a mandatory step after every settled operation. A detail
  read uses the chosen snapshot as-is; it does not refresh an older selection.
  For skills/non-Launch lifecycle, `source_id=null` selects only the exact source
  already returned in that cached snapshot. An explicit returned source ID selects
  that retained read instead. Launch stays source-free; no newer source is fetched.
  If the snapshot has no source, null cannot select one. Diagnostic Observe can
  return `result.source_ids` while current source remains absent; read the chosen
  exact image with `enactive_source`, then explicitly select its ID. A diagnostic
  capture is not current input authority or proof that reconciliation succeeded.
  If a lifecycle call refuses a stale binding with no input,
  use the returned current snapshot for a separate new decision. No automatic
  retarget, replay or allowance renewal occurs.
  Keep returned text, typed image parts and `isError`; do not
  print image data as text or opaque tool objects. Keep simple returned IDs.
  When forwarding through an orchestration tool, forward content blocks once;
  `text(JSON.stringify(result))` prints the whole transport envelope and can
  bury decision data or print image bytes. The MCP producer returns one JSON text
  block and any typed image, without a duplicate `structuredContent` value.
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
- For a Claim, choose its meaning, value, coverage, status, grounding and support
  groups; use the current focused Claim schema. Software supplies the record/ID,
  interpretation kind, native order and real host assertion time. Identity keys
  select world/character; software supplies the reserved unit/coverage fields.
  Identity state is the interpreted exact name; other details belong in text.
  Source grounding can select the cached snapshot image with `source_id=null`.
  A null coordinate epoch uses only a matching published `coordinate_scope`;
  before adoption use the actual epoch from the returned `provisional_scope`.
  Never guess zero. Each support group's `primary` explicitly cites that chosen
  image; additional source/claim premises stay explicit. Unobserved grounding has
  no native order or image citations. Correction chooses retired IDs/reason;
  software supplies matching supersedes. Returned Claim IDs identify the records
  you can select later; do not calculate hashes or timestamps yourself. Cite the
  image or premises that actually establish the claim, rather than automatically
  citing the latest image. Accepted storage is not semantic support or truth.
  All cited sources share the Claim's grounding session. An owned pre-load world
  Claim keeps its menu session; character identity uses its inspected session.

Owned exit also accepts ordinary keys/text/clicks as lifecycle-scoped children.
Inspect the current menu and choose input; no exact quit-question transcription is
required. A known returned input can need another decision without having an
unknown delivery. Returning to the owned main menu pauses/cancels this exit attempt;
a separate exit root is needed to try again within the original mission allowance.
Normal process exit and final Finish still require the returned registered proofs.

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
| Reconciled transition, paused provisional character | Continue with `enactive_lifecycle`, `scope=lifecycle`, unchanged `operation=create` or `load`; this separate call readmits the provisional session. Do not use `enactive_readmit`, which is for ordinary recovery/handoff. Then inspect `purpose=character_identity`, read the actual character screen, retain truthful world/character Claims, dismiss it and separately adopt through the same lifecycle operation with those Claim IDs. Adoption, not launch or Observe, starts ordinary input authority. |
| Normal ending | New `save` lifecycle root with null Work and empty identity IDs; confirm ordinarily and reconcile/checkpoint through the same Save phase. After completion choose a new owned `exit` root. After recorded normal exit choose `finish` as a separate `new_root`, never a child of exit; report the actual outcome. Returning to the same normal session cancels Save without a checkpoint claim. Later reload requires this mission's own saved checkpoint. Initial Load instead establishes new identity/accounting; old authority/world facts are not imported. |
| Abandoning menu-only setup | Return organically to the same owned main menu. A new `exit` request can revoke settled setup without input; then explicitly Observe and use a new finite normal-exit root. A fresh Observe and this zero-input MAIN_MENU abort remain available after local setup expiry under healthy custody and global limits; they cannot renew expired inputs or cancel another form. This does not clean up an unadopted normal session. |

Create/load limits cover the complete original lifecycle: opening menus, transition,
identity inspection, Claims, dismissal and adoption. Choose a prospective finite
allowance from the coupled forecast for that whole operation, not just the first
menu. Child calls cannot enlarge or renew the original root. If it expires,
quiesce; a new child or Claim cannot repair expired input authority.

Let software form wire records. Choose the goal, selected evidence, interpretation,
target or answer, and finite limits. Do not supply navigation `goal.scope` or an
activity `interrupt_request_id`; software binds them from the selected matching
snapshot/source. Missing context requires an explicit read/new decision, never
guessing IDs, epochs or silently selecting newer evidence. The lifecycle summary's
remaining wall/primitives are software-derived as-of values; use them to choose
timely closure, not as a renewed allowance. Do not write request
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
stopping behavior. `enactive_stop` pauses control; it does not close the owned
game or complete normal Finish. If a required capability is absent, settle handles, retain the
failure and permanently quiesce under the brief; never ask the user/lead to supply
a gameplay key or repair memory. The lead assesses closed evidence independently.

This guide's maintenance check is a focused comparison with current tool schemas,
phase receipts and lifecycle implementation whenever its review trigger fires.
[The runbook](runbook.md#typed-mission-requests-and-the-player) owns detailed recovery
and operator procedure. Tests and native evidence qualify their actual scope;
this guide does not establish a new capability.
