---
owner: lead
review_trigger: Production control/player ports, ownership, persisted formats or cutover scope change
status: proposed
---

# Production computer control and player-owned semantics (#176)

The selected iteration and estimates live in [#176](https://github.com/CVX-Hull/enactive/issues/176):
16–24 active engineering/experiment hours, Low confidence, 24-hour appetite.
[#287](https://github.com/CVX-Hull/enactive/issues/287) owns mechanical integration;
[#288](https://github.com/CVX-Hull/enactive/issues/288) owns the playing system.
One lead/runtime owner, at most two later implementation workers with disjoint
ownership, one coordinated integration and normally one PR. This is an implementation
brief, not another backlog or permission to deploy mixed contracts.

## User consequence and boundary

Ordinary input must work without an engineer adding a handler for a game screen,
menu, item, activity, identity or recovery phase. The harness supplies actual target
pixels, mechanical window geometry, basic key/text/pointer/wait, one writer, original
limits, Pause/cancellation, exact delivery/uncertainty and owned cleanup. The entire
playing system owns game interpretation, goals, tactics, memory, programs, learning,
save/load and outcome claims. Optional helpers remain fallible and bypassable.

Use [ADR006](../decisions/006-computer-control-boundary.md) and the
[reviewed caller/storage/deletion map](070-computer-control-proof.md#reviewed-production-handoff).
Current native7/mission11 is still the supported product until this coordinated
replacement lands. Reuse the one #181 SDL candidate rather than build another
backend or ship the experiment beside production.

## First checkpoint: actual input before broad migration

Within roughly four hours, confirm ordinary project-local input configuration and
actual key/text/pointer effects during a meaningful generic-Pi gameplay episode.
Keep OpenRouter Fireworks US/DeepSeek Flash1017 medium unless concrete incompatibility
requires a recorded change. A delivered click or same PNG is not a useful effect.
The old preparation disables mouse while its semantic bridge overrides that option;
the new primitive layer must not know or override the game setting. Preparation may
select normal application input settings before a frozen run; in-game interpretation
and choices stay with the player. No save editing, staged bad routine or lead tactics.

Before that admission, close the concrete lock gap found in the #181 custodian:
it alone holds the shared game/userdir lock, so its death can release exclusion
while its separately sessioned game survives. Pass the exact locked file descriptor
through the prepared shell to the owned child. Native retains that inherited lock
for its lifetime and sets close-on-exec at dylib startup before application main.
Descriptor identity must match the selected lock file, so a closed/reused numeric
descriptor cannot accidentally authorize control. Reuse
POSIX descriptor/flock contracts; no PID adoption, global process scan or second
lock registry. A second independent lock acquisition must fail after the parent
copy closes and succeed only after the owned child exits. Run-local native/MCP
writer locks remain separate. A missing/invalid inherited lock refuses native control.
The temporary launch profile becomes `computer-proof/2`, rejects old launch profiles,
and pins bounded initial target files as well as source/binaries/driver inputs.

The pilot remains one owned custodian and one fresh package. Preserve exact native,
shim, source/config/context/route hashes and original resources. Retain binary bytes
before rebuilding, all wrong choices/unknowns, and save-to-menu versus process-exit
differences. Fix only mechanical defects before another fresh package; never patch
source while the actor or game is live. This is the first checkpoint of the selected
capability iteration, not a separately accepted proof-only iteration.

## Production responsibility and port proposal

The [reviewed two-sided ports](../contracts/computer-control.md) freeze fields,
versions, callbacks and data treatment after the initial input checkpoint and
before worker assignment. The responsibilities are:

| Responsibility | Proposed implementation and permitted data |
| --- | --- |
| Computer runtime | `harness/computer/`: integrate the tested SDL mechanics, exact owned launch, mechanical session/operation/frame store and serialized basic dispatch. No imports from game/playing semantics. |
| Playing system | `harness/player/`: passive source reader, typed fallible claims/Work/quantities/procedures/corrections, bounded local programs, optional candidate advice and actor context handoff. It uses only the computer port for effects. |
| Custodian and transport | One long-lived owner survives clean actor replacement; reuse standard loopback HTTP/MCP and the maintained Pi host. Actor adapters cannot reconstruct authority from storage. Explicit handoff seals the old actor, retains original limits, and requires its quiescence before a successor. User Pause/unknown delivery never becomes handoff-resumable. |
| Persistence | One current version per boundary and fresh explicit session/player stores using SQLite transactions/constraints and ordinary atomic files. Preserve old JSON/PNG/SQLite and source checkpoints as inert history. No old executable import/reader in current runtime. |
| Presentation and telemetry | Actual PNG/source/result retrieval, mechanical ownership/resources/uncertainty plus separately labelled player claims. Retain bounded visible player narration through existing host events; do not store internal reasoning or add a tracing service. |

The minimal computer port is actual captured image bytes plus opaque source/digest/
presentation/geometry, basic input with original operation IDs, exact result collection,
remaining mechanical resources and permanent user stop. Key input has no image-age,
equality or game-phase prerequisite; pointer input binds mechanical geometry.
Player services cannot make a memory assertion, game identity or expected outcome
an authority token. Programs receive real image data/references and optional player
interpretations, then propose the same basic controls under original CPU/time/input
bounds. Reuse the existing JavaScript sandbox and pure memory/lineage algorithms
where they fit; remove native-turn/receiver/mission dependencies rather than rename them.

## Integration and evidence

1. Close the inherited-lock gap, freeze normal input configuration, and run the early
   useful-gameplay checkpoint on committed focused-tested source. Inspect #128's real
   publication-stall history against the current capture path. Browser independence
   alone is not proof native file publication cannot stall; select a bounded remedy
   or explicit rescope if actual evidence requires it, not a speculative framework.
2. Freeze two-sided ports, current schemas/storage treatment and disjoint ownership.
   Integrate mechanical and player workstreams against those interfaces. Remove old
   runnable commands/dispatch/phase/recovery, current old-format import/export readers,
   and experimental entry points together. Reject unsupported formats before effects.
3. Return to authentic player-selected survival work at coherent committed checkpoints:
   useful acquisition/use or scouting/shelter, natural interruptions/revision, current
   program/memory/correction/handoff functionality, same-character visible save/new-child
   reload and final player-owned normal application exit. Keep failed/abandoned chains.
   Do not manufacture a bad routine, useful-decision cohort or learning-benefit claim.
4. Consolidate independent source/outcome review, full protected PR and actual-main,
   authoritative docs/CI/fixtures and exact owned cleanup before Done. One current
   supported route; rollback is a coherent earlier source/data deployment after writers
   close, never mixed reading or replay.

Original resize/non-unit/stale-current pointer, actual-human takeover, Unicode/IME
and second-real-game gaps remain explicit in #284/#191. Current CDDA pointer usability
is core here. Broader #164 cadence, #177 learning and #145 survival are separate.
At four-hour feasibility/core drift or the 24-hour appetite, adjudicate and rescope
explicitly; incomplete capability cannot be relabelled successful investigation.

The lock repair uses the documented [macOS flock lifetime](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/flock.2.html)
and [Python's explicit descriptor inheritance](https://docs.python.org/3.14/library/subprocess.html).
Do not explicitly unlock a forked reference; close owned references and qualify
the actual shell/native integration separately from portable launch fakes.

## Control reuse at the cutover

Retire C-PROTOCOL's native7 literal-count/AST parser with its removed producers.
It blocked the new viewer's source checkpoint on two obsolete spellings; retaining
its representation parser would add another maintenance authority rather than test
the new behavior. Existing C-PORTABLE strict ingress/version/uncertainty tests and
C-NATIVE actual compiled interoperability remain, with independent migration review
and required native/gameplay qualification. Structural governance keeps metadata,
references and map checks; it no longer claims protocol conformance from literals.
Retain the parser's historical exercise records without relabelling them current.

## Closed first production attempt and bounded provider adjustment

The coherent source checkpoint77cd124 passed strict full portable validation
(213tests/327subtests), separately from native fixtures and organic acceptance.
Production `cutover176-organic001` used the installed unpatched game and qualified
bridge but failed on its first HTTP429 before any gameplay tool input. The actual
response requested20s; the frozen host permitted at most5s, so no retry was sent.
All deciding-host/native groups closed; native SIGTERM zero was forced cleanup,
not normal ending. Its one attempt and unknown usage remain charged, with
$693.010432 consumed conservative cumulative reservation across2376 attempts.

The lead's finite rescope retains the selected endpoint and production/gameplay
core: admit at most one eligible provider-only429 retry with a server delay≤25s
under the same original request/host timers and HTTP ceiling. Every attempt counts,
the serialized request is identical, and cancellation or insufficient resources
prevents another fetch. Longer delay, second429, quota/auth/validation, other status,
transport or partial-stream errors stay terminal. No automatic actor/native restart,
tool replay, endpoint fallback or original-run renewal is introduced. Use a fresh
prospectively frozen package after reviewed source and owned closeout.

[OpenRouter's current errors contract](https://openrouter.ai/docs/api_reference/errors-and-debugging)
says to honor Retry-After and locates normalized provider error types in metadata.
[Its limits contract](https://openrouter.ai/docs/api_reference/limits) distinguishes
rate, key/budget and credit sources. Checked2026-10-29. Record only bounded diagnostic
identifiers, not raw provider text or financial/account details. The closed attempt
did not retain those fields, so its precise limiting source remains unknown; later
diagnostics cannot retroactively identify it. This correction follows the observed
20s delay, not a claim that the provider is now qualified.
