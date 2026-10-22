---
owner: lead
review_trigger: Capture provenance, operation preconditions or actual native qualification changes
status: active
---

# Capture provenance and action preconditions

## Problem and intended result

Fresh008 stopped after four known native input rejections and four unstarted Save
decisions. Its original costs, failed outcome and exceptional ending remain in
[#145](https://github.com/CVX-Hull/enactive/issues/145). All actors and owned
processes are closed before this work. The seven-day objective is unchanged.

Each adjacent Save-image pair differs in 13 decoded RGB pixels at unchanged
exported turn, revision, session and boundary. The native input error combines
several predicates; its precise failing predicate was not recorded. These are
different failure lanes. Neither fresh observation nor repeatedly choosing Save
establishes progress when the substrate demands incidental pixel equality.

Separate three questions: did native issue this immutable capture; are its
original clocks, context and custody still valid; does this particular action
depend on identical pixels? Preserve the original informing source and preflight.
A newer rendering must neither erase provenance nor renew an older capture's TTL.
This is an input-boundary correction, not player tactical reasoning or learning.

## Selected design

Reuse the native bridge's existing bounded 120-frame retention deque. Replace
its bare filename entries with immutable capture records containing the issued
filename, original capture timestamp and existing normalized complete observation
metadata. This is process-local provenance for existing retained files, not another
archive, database, version-control system or authorization service. Eviction keeps
the existing bound and file cleanup. No additional dependency is needed.

For non-spatial, non-image-conditioned key/action/text input, native may accept the
request's original issued capture after a newer passive rendering only if that
record remains retained, its original three-second clock is live, its complete
normalized metadata matches the current context, and all existing current render,
receiver, session, revision, boundary, authority, Pause, takeover, pending-control
and original request-deadline checks pass. Compare metadata on the game thread;
do not infer equivalence from a filename pattern or merely from a matching turn.
Never substitute the latest filename into the request or renew the old timestamp.

Spatial clicks, explicitly image-conditioned semantic input, setup/image-conditioned
Resume and recovery keep their stronger applicable capture/image/geometry checks. The initial gate
may validate provenance before direct-event classification, but the final commit
must apply the click-specific rule before any engine or widget event. Parse a
direct-input child once through the pinned JSON API; do not repeat the earlier
partial-object visitation bug. Give failed predicates distinct bounded error
messages, retaining the existing expected-refusal versus custody/I/O-fault taxonomy.

The controller preserves its actual final Observe/preflight and final ownership,
complete state, queue, clock, storage and deadline fences. A non-image-conditioned
event need not fail solely because the latest capture basename changed after
that preflight. An image-conditioned or spatial request keeps its applicable
refusal behavior. No input is retried automatically and native still makes the
final decision against the original issued capture.

The registered Save start and provisional normal readmission/identity-inspection
entry use existing `native_state` equivalence across lifecycle refresh,
SourceRevalidation, runtime dispatch and final preflight. These operations depend
on the exact owned normal context, not incidental image pixels. The complete-loop
regression with the actual008 image pair first reproduces Save drift; after that
repair it also reproduces a reload-readmission failure under the same persistent
drift. Do not disable that fixture drift merely to pass the later phase.

Apply this policy only to Save's `save_start` normal checkpoint or creation/load's
`awaiting_identity` normal checkpoint. Provisional readmission still requires its
original committed transition, exact owned launch/normal endpoint, actor/epoch,
Pause origin and separate identity claims/adoption. Its registered normal Resume
uses the same native-state policy; other Resume callers remain image-conditioned.
Native commit derives strict-current-capture policy from the existing explicit
`require_exact_frame` flag or parsed spatial event, rather than treating all
Resume alike. Keep every Resume authority/token/sentinel/clock/receiver check.

Keep the original root, first-normal identity, actor/epoch/operator marks,
game anchor, budgets and deadlines. For Save, preserve the interaction lease through refresh,
then perform the existing single checked rotation to the lifecycle lease before
dispatch; do not preserve an interaction capability where lifecycle authority is
required. Confirmation, setup forms, character-row selection, the actual identity
screen/claims and registered recovery retain their existing stronger policies. Remove
the superseded Save-image-redecision exception/loop and migrate its callers and
tests; do not retain a compatibility mode or require extra model decisions merely
to gamble on equal images.

The wire/export shapes remain unchanged: existing `require_exact_frame`,
SourceRevalidation rules and issued source references carry the policy. All active
code, fixtures, installed native, guidance and source/native pins move together;
no mixed deployment or old-behavior flag is supported. Historical sealed exports
remain immutable evidence in the same observation format. Review must challenge
this no-format-change decision if an implemented field or meaning cannot be
represented truthfully by the current contract.

## Alternatives and limits

Repeated observation/redecision already failed under continuous drift. Increasing
TTLs, silently retargeting, replaying rejected batches, masking a screen region,
freezing animations or accepting arbitrary supplied filenames were rejected.
They do not supply the required action-specific proof. A generic visual relevance
classifier or new capture service would add machinery without a demonstrated need.

The selected policy still refuses expired, unissued, evicted or semantically changed
captures. It does not guarantee liveness under real state change, I/O failure or
lost custody, and does not prove safe game semantics or broad cross-game support.
No change to upstream CDDA outcomes, saves, renderer behavior or global Mac setup.

## Ownership and verification

The integrated source and test migrations have independent review. The real008
PNG-pair regression keeps drift active through Save, owned exit, new-child load,
normal readmission/identity and final ending; this is source evidence. A matching
new native build and graphical qualification remain required before the next full
campaign. The failed008 report remains unchanged by the repair's later results.

Lead owns design/adjudication, controller/runtime/lifecycle integration, current
contracts, report and the sole build/runtime. After design review, one bounded
worker may own only `native/cdda_harness.cpp`, its compiled receiver/capture
fixtures and directly coupled setup/extraction tests in a separate project-local
worktree. Freeze the exact file list in that brief; no worker uses the shared
build/game/userdir. Keep writes disjoint and take work back after two failed repairs.

Required focused checks:

- Native-issued capture A followed by pixel/filename-changed B under equal complete
  metadata: ordinary non-image input can use A without rewriting it; A's original
  TTL/deadline still expire even if B is fresh. Unknown, evicted or foreign A and
  changed metadata refuse. Exercise actual extracted production gate/publish code.
- Exact/image-conditioned, click and image-conditioned Resume behavior remains strict. Test geometry
  changes at both commit fences, delayed encoding, Pause/takeover/authority loss,
  changed receiver/session/revision/boundary and pending recovery. Retain faults.
- Host final capture-name churn preserves a valid non-image preflight without
  removing any fatal fence. Image-conditioned/spatial refusals keep their original
  charge and explicit-observation requirements; no suffix replay or new allowance.
- A whole registered Save loop with persistent real changed PNG bytes and equal
  native state reaches the ordinary confirmation and owned lifecycle under the
  original limits. Changed state/identity, stale clocks, spent reserves/root,
  unknown delivery and processing/storage faults remain stopped. The subsequent
  normal provisional readmission succeeds under the same persistent drift, while
  changed identity/transition or Pause fails. Setup/confirmation/identity-screen
  and recovery policies must not accidentally inherit the normal-context rule.

Use focused checks before development play, independent source review and full
portable/candidate CI before formal acceptance. Compile/install/sign the pinned
native and record its actual hash. A new finite graphical qualification must
exercise coherent ordinary input and normal Save/confirmation/owned exit/new-child/
exact reload/final ending under actual capture drift where it occurs; fixture
success is not native evidence. Then admit a genuinely fresh full campaign with
the original survival, memory, handoff and normal lifecycle requirements.

## Artifact maintenance

Update current architecture/protocol, mixed-input design, integrated brief,
relevant tests/control registry and generated control map with actual behavior.
The dated failed008 report owns observations, original costs/unknowns/interventions
and cleanup; Issues #176/#195 own repair acceptance, #164 owns measurement and
#145 owns the full campaign. GitHub owns stage/allocation/CI, not this brief.
Review this design against future capture/precondition failures; consolidate
superseded current guidance rather than layering another recovery path.
