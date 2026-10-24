---
owner: lead
status: historical
date: '2026-10-24'
scope: Design and development record preserved on this date; current architecture/protocol
  and GitHub own behavior and remaining work
---

# Player-authored executable routines

Issues#177/#176/#178/#164/#191 support parent#136 and the genuinely fresh#145
campaign. The [research](../research-executable-policies.md) owns sources and the
prior-design crosswalk. This brief owns the integrated implementation; it is not
another backlog and does not narrow the full learning/campaign outcome.

[Learning009](../acceptance/2026-10-23-discovery-learning-ninth-attempt.md)
subsequently qualifies narrow independent real executable authorship, distinct
shelter reuse, changed-condition revision, fresh-successor application, claimed
advisory overlap and normal lifecycle on exact-CI-passing sourcee174bff. Combined
readiness still fails apparent cadence; the genuinely fresh seven days remain
open. Source checkpoints below retain their original scope and limitations.

## Selected first boundary

Player-authored JavaScript implements `step(view, state)` and returns JSON:
`{status, state, input, reason}`. Status is `act`, `yield` or `done`; input is a
player-selected ordinary key/text/click only for `act`, otherwise null. Reason
is a fallible policy explanation. `done` means program termination, not verified
task success. JSON state carries the policy's local continuation; code may also
use ordinary functions, branches, loops and calculations. No menu catalogue or
game strategy is built into the language binding.

Use MiniRacer 0.14.1's embedded V8, public async evaluation and documented caller-
owned loop lifetime. No Python callbacks, filesystem, process, network or native
input function is installed in JavaScript. Remove reachable delayed scheduling
facilities, including MiniRacer's timer manager, asynchronous waits and public
timer/microtask entry points; the host supplies steps and observations. Verify
that callbacks cannot perform policy work between host steps. Computation and memory limits
are outside generated control flow. Host validates JSON output and dispatches
eligible ordinary input through the current writer. The program never holds an
input capability, modifies platform source or chooses fresh authority metadata.

The passive engine module owns only compilation, bounded evaluation and typed
results. `PolicyProgram(code)` is a synchronous context manager for the existing
writer/adapter thread, using an owned asyncio.Runner and documented mini_racer
context so isolate shutdown precedes loop shutdown. `step(view, state,
timeout_seconds=...)` returns a decoded result. No asynchronous model or game
call is hidden in this method. A timeout, exception, memory limit or invalid
result returns control with an explicit engine error; no primitive is emitted.
Close after an engine fault; do not automatically retry/replay the failed step.

Engine API: `PolicyProgramError(ValueError)` covers bounded compile/evaluation/
validation faults. Constructing/entering a program compiles it once; `close()` and
context exit release its isolate before its owned Runner. `step` accepts only
JSON objects for view and state, defaults its timeout to0.05s and rejects nonfinite,
nonpositive or greater values. The returned object has exactly the four fields
above: reason 1–1024 characters, object state, status enum and nullable input. Derive
the input alternatives from `native_input.input_schema(text_limit=24)`, removing
only click geometry (host-owned); reject a supplied geometry rather than accept
two forms. Keep key modifiers explicit in program output. The host uses
the current observation's geometry and existing validate_input before dispatch.
This module emits no action and decides no applicability or semantic success.
Validate recursively inside JavaScript, before serialization, using captured
bridge intrinsics that policy code cannot replace: reject nested nonfinite numbers,
undefined, functions, symbols, BigInt, Promise, accessors, non-plain objects, cycles
and sparse arrays rather than letting stringify omit or coerce them. Bound that
validation inside the same step timeout. Then enforce UTF-8 and Python schema
bounds. Reject Promise/non-JSON/function results. Timed-out/invalid/faulted instances
cannot step again. Caller serializes calls under the existing writer/adapter;
do not add an owner registry or retry/locking subsystem.

First engine bounds: source 32 KiB UTF-8; view 256 KiB canonical JSON; state 16 KiB;
result 32 KiB; V8 heap 32 MiB; compile 0.25 s, step at most 0.05 s, narrowed to the caller's
remaining time. Status/field/type/finite-JSON validation uses existing JSON Schema
and canonical helpers. These are finite initial limits, not universal constants;
measure actual view fit and revise before a deciding run if necessary. Engine
tests must not call synthetic execution organic learning or game performance.

Numbers follow finite binary64; integer-valued numbers must be within
±(2^53−1). Reject larger host integers before V8 JSON parsing and larger returned
integer values rather than silently rounding them. JavaScript's normal detached
Promise rejection semantics remain: a microtask drain/heap check does not report
every unhandled rejection. Fire-and-forget asynchronous policy logic is unsupported;
the fault guarantee covers raised synchronous evaluation/validation errors,
timeouts and heap exhaustion. No public global rejection hook is exposed in the
pinned library. This limitation is retained instead of adding a custom Promise
runtime or claiming every internal failed computation was detected.

## Reuse evidence and implementation decisions

The project-local runtime spike uses the hash-pinned official Mac ARM wheel,
Python 3.14 and no game input. QuickJS's Python wrapper is archived; Starlark's
binding has no Python 3.14 wheel and would introduce a Go toolchain. MiniRacer
provides a maintained distribution, ordinary JavaScript, timeouts and heap limits;
avoid inventing a DSL, tree engine, VCS or learning store. Wasm remains an
alternative if the selected embedding fails its actual requirements.

The initial default-loop probe reported a shutdown callback error after a bounded
failure. The supported caller-owned async lifetime probe completes with empty
stderr: 1,000 synthetic changed-order/coordinate decisions,20 unknown/absent yields,
warm JSON-step p95 0.067 ms, cold context/compile max 15.379 ms; infinite loop interrupts
in 0.051 s and allocation raises JSOOMException in 0.0044 s. These are component-only
results, not a native/model/display or learning qualification. The original
default-loop result is retained, not overwritten by the successful lifetime probe.
Private scripts, manifests and results are in
`.runtime/research/2026-10-23-executable-policies/runtime-spike/`.

## Integrated representation and writer binding

The coordinated candidate uses mission/11, campaign-memory/6, procedure/3,
update policy facts-procedures-reflection/3, now with MCP5.1.0 and player-view/4
under [delivery062](062-player-decision-context.md). Native6,
gameplay/2, ledger12, archive5 and reflection/2 retain their own wire/storage
shapes; their nested mission/procedure validators enforce the new contracts.
All current producers, fixtures and consumers migrate together. Prior closed
admissions/libraries remain immutable evidence and are not mounted or reopened
as current execution state. There is no compatibility reader, inferred program
or automatic conversion. No live mission existed at this cutover.

Procedure/3 requires nullable `program`: null means advisory; otherwise it has
`language=javascript/1` and `source`. The whole canonical procedure remains 32 KiB,
including purpose, applicability, lineage and evidence. Code is never inferred
from advisory text. A program skill selects an eligible current revision through
existing procedure-use linkage and supplies initial object `goal.state`, intent,
expected outcome and interrupt consent. It starts its own root; an existing
prompt retains ordinary/semantic children under its original root. Running code
stays pinned, and a new memory revision affects future invocations only.

`program-view/1` contains category, registered actions, in_game, current rendered
ui, visible scene, frame_geometry and boundary kind/input_receiver, plus explicit
omissions. It excludes identifiers, hashes, paths, clocks, native authority and
save/engine state. The writer records its exact source separately. Null ui/scene
means unavailable. Scene is limited to currently supplied visible neighbors and
creatures; there is no arbitrary map, inventory or PNG/pixel decoder. The model
still receives the actual PNG and chooses ordinary fallback for conditions the
program cannot evaluate. A retained 017 complete observation is only 3,406 bytes;
all retained observations must be measured against the 256 KiB engine bound before
deciding play. This first view enables more than menu labels but does not claim
general visual recognition. Pixel-derived routine perception remains #176/#191.

The program skill reuses ordinary entry/custody/proposal/feedback/scalar checks,
one existing dispatch/ledger writer and original request/game/wall limits. Every
step receives the latest attributed view; text expansion stops on structural
change. Unknown delivery ends evaluation and retains the original operation.
Engine faults/yield preserve healthy ordinary fallback without claiming success.
Software records source-linked program steps, selected revision and actual
primitive outcomes for reflection. A derived result trace is bounded to 16 KiB,
with explicit omitted-event counts and per-event state omissions above 2 KiB;
complete evaluation state remains in the existing audit log and actual primitive
intent/receipts in the ledger. It creates no second durable trajectory store.
Model presentation keeps the summary when the exact continuation/trace is
addressable through the returned snapshot’s as-of progress detail; a historical
collection with different current progress retains its original data inline. No model needs
to narrate every use or copy hashes/authority fields.

## Remaining qualification

The complete slice must qualify player-authored code with purpose, applicability,
counterexamples and immutable revision identity; select a fixed revision per
invocation; bind each next action to current observations; inherit original finite
limits; retain every primitive/request/unknown; and yield to organic exploration
on semantic novelty. Reuse current procedure memory and feedback rather than
creating a second trajectory or executor. Prior procedure/2 was advisory; its
text cannot silently acquire executable semantics. Historical closed evidence
stays historical; no compatibility reader or silent library mounting is allowed.

Use a writer-owned program skill: one immutable invocation, pinned procedure,
deadline, original game anchor and cumulative primitive budget. An SDK loop over
new ordinary requests would mint fresh local budgets after normal play clears
the prompt root; it would need another durable parent contract. Extend current
ledger parent/sequence checks explicitly for program-derived ordinary proposals,
reusing scalar expansion and settlement. Pending/unknown delivery ends evaluation
and exposes collection of the original operation; never rerun/replay the step.
Do not create
nested unjournaled input, fresh budgets per iteration or an independent native
writer. Player-facing intent stays small; software supplies IDs, exact scope,
geometry and accounting where mechanical. Program context includes only visible
observation data and policy-local state; no engine/save/global filesystem access.
The first visual-data envelope is frozen above. Image-only conditions remain an
explicit model fallback and future perception gap, not silently inferred UI data.

The integrated outcome remains independent discovery, executable routine reuse in
a distinct situation, changed-condition revision/retirement, actual fresh-context
application, useful play with background learning pending, and normal Save/new-
child Load/final ending. Player chooses the routines and judges fallible advice;
the lead owns substrate and verifies evidence, not tactics or memory curation.
No per-routine lead/model approval. Include failed learning/compilation, perception,
recovery and all model/tool/display cost. Neither a tiny engine benchmark nor a
hand-authored demonstration substitutes for that outcome or fresh seven days.

## Ownership and verification

Lead owns design, dependencies, memory/ingress integration, shared runtime and
final verification. One isolated worker owned only the passive engine and its
tests; after two failed attempts the lead took repairs back, as S-AGENT requires.
Independent source review and focused real-runtime tests precede development
play; full protected checks qualify acceptance/merge. No game is running for this
implementation checkpoint.

### Source checkpoint, 2026-10-23

The real-runtime engine tests cover compilation, changed observations, ordinary
input shape, raised faults, runaway loops/microtasks, heap exhaustion, JSON
validation before coercion, numeric precision, protected intrinsics and clean
owned-loop teardown. Seventeen engine tests pass. The initial default-loop and
post-result microtask failures remain in private spike evidence.

Independent writer/memory review found and rechecked repairs for lost menu-root
settlement, production viewer version drift, absent adviser step detail and
cancellation dropping returned trace. Regression cases retain original root and
procedure linkage, actual generated inputs/source/state/reason and primitive
delivery in scheduled advice, text/click geometry, revision refusal, ordinary
fallback and unknown no-replay. The 42-test engine/program/presentation command
passed; its subsequent one-test cancellation repair also passed. The existing
141-test runtime/ledger command and 40-test player adapter/presentation command
passed; production viewer regressions passed after the preserved version-drift
failure. These are scoped source/component checks, not a combined unique count.

An independently checked passive timing probe on all 119 retained 017 views finds
573–3,247 canonical bytes (median 3,183), within 256 KiB. After the numeric repair,
1,000 validated steps including the bounded microtask drain have median 0.300 ms,
p95 0.350 ms, max 0.720 ms; 10 cold compiles have median 0.778 ms, max 15.633 ms. The fixture
only yields/counts observations, with zero game inputs. This does not measure
model reasoning, native dispatch, display, useful skill execution or learning.

The full portable lane for source17e7488 passed:1818tests in755.166s, viewer,
diagram rendering, governance and structural checks. It did not run a native game.
At that checkpoint, exact candidate/protected CI, independently authored real
graphical learning and genuinely fresh seven days remained open. Current scoped
qualification and remaining gaps are linked above.
The updated player diagram was rendered and visually inspected. Dependency and
owned-environment history are in [environment](../environment.md), with terms in
[NOTICE](../../NOTICE.md). GitHub Issues/Project own remaining work; this brief
owns implementation evidence rather than another backlog.

### Procedure authoring automation

The subsequent MCP5 adapter keeps the21tools and current canonical formats. Its
Procedure authoring view removes schema/record/id/mission/family/revision number
and environment, deriving them from the assigned operation, selected cached
snapshot's frozen admission environment and explicit parent choice. New families
receive software IDs and revision1. A qualified parent must have been returned
by explicit `enactive_context`; a bounded descriptive cache retains those copies.
The existing receiver owns current-head/branch/evidence validation. Composition
never fetches newer status/source or infers support/adoption. Supplied metadata
copies reject rather than enabling a second authoring form.

Canonical storage/staging/unknown collection are unchanged. Forty-two focused
authoring/Claim/presentation tests pass, including actual memory application,
revision and stale-branch refusal, cached-only binding and same-ID changed-payload
non-resubmission. Sixty-two existing adapter/lifecycle/program/reflection checks
also pass, and independent review found no consequential defect in the bounded
delta. A fresh production stdio handshake reports MCP5.0.0,21tools and the14semantic
Procedure authoring fields, with all seven mechanical fields absent; no gameplay
tools were called. This is not desktop restart or native qualification.
This removes model bookkeeping from player
procedure creation; advisory candidate metadata remains canonical (#178).
