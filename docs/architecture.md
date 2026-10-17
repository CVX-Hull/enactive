---
owner: maintainer
review_trigger: Boundary, authority, supported behavior or deployment change
status: active
---

# Current architecture

Implemented MVP architecture.
Protocol version: 1. Dated verification: [MVP acceptance](acceptance/2026-10-17-mvp.md).

## Scope and responsibilities

The [overview](overview.md) provides the user-facing system picture. One local
macOS game and one controller are supported. Codex in an active chat is the
planner; general autonomous survival and other hosts are unverified. Normal
windowed operation and project isolation are [charter constraints](charter.md).

| Boundary / owner | Input and output | Authority and failure behavior |
| --- | --- | --- |
| Planner / active Codex session | Actual observations → objective and bounded input requests | Chooses goals; cannot infer success from transport acknowledgment; uncertain state requires reconciliation |
| Controller / harness maintainer | Observed-state-bound commands → validated bridge requests, results and journal | Single serialized client; process lock; deadlines; pause freezes dispatch; never mutates saves or game state |
| Native bridge / integration maintainer | Bounded requests → actual input events, metadata and rendered frames | Game thread only; engine validates outcomes; session/revision/expiry checks; unsupported input boundaries cannot claim success |
| Spectator / viewer maintainer | Frames and state → display and operator controls | Input authority only after matching current image decodes; stale state stays visible; browser controls require origin/token validation |
| Setup / build maintainer | Pinned sources and existing toolchain → isolated app and manifest | Explicit stages, checksums and ownership; failures stop the stage; no global installation or automatic launch |

These roles may be held by one maintainer. Ownership names describe accountability,
not extra services or a requirement for additional people. Implementation paths:
[controller](../harness/controller.py), [server](../harness/server.py),
[native bridge](../native/cdda_harness.cpp), [viewer](../web/app.js),
[setup](../tools/setup.py).

## Runtime and state

Observe → choose a bounded action → validate current session/revision → dispatch
at an eligible engine input boundary → observe the next boundary → interpret the
result. A prompt is a valid outcome. `ready` means returned to input, not objective
completion. A timeout produces an unknown outcome and freezes further actions.
Observe/reconcile then explicitly resume; never automatically replay the input.

Native keyboard/button input latches takeover. Pause prevents subsequent remote
dispatch; it cannot cancel an already-started engine activity. Raw upstream debug
screens outside supported input contexts may need native dismissal. A service
restart retires undispatched work without replay; a game restart invalidates old
session authority. Full details: [protocol and guarded play](protocol.md).

## Action and recovery views

These are **current behavior** explanations for the operator and maintainer;
[protocol](protocol.md) owns the detailed contract. They summarize the implemented
flow, not a new API or fresh native verification.

### What happens when the agent acts?

![Current action sequence: observed authority is checked before input; a ready response requires interpretation, while a timeout freezes dispatch.](diagrams/action.svg)

Read top to bottom: vertical columns identify responsibilities; solid arrows are
requests/input and dashed arrows are observations/results. The two alternative
outcomes are mutually exclusive paths for this request. The controller obtains
current authority but rejects a stale planner choice instead of silently updating
it. The native bridge validates again before delivery. A rejection dispatches no
input. The eligible next boundary can be a prompt: `ready` does not prove success.
After timeout, observe to reconcile and explicitly resume; never replay blindly.
The spectator shows the returned frame/state. [Editable sequence](diagrams/action.mmd).

### How do I recover control?

![Current recovery workflow: reconcile after startup or uncertainty, remain paused, explicitly resume, and pause or take over when needed.](diagrams/recovery.svg)

Rounded boxes are operator workflow states; arrow labels are the conditions that
change them. The initial dot marks controller startup/restart; attached notes
state limits. This is a workflow summary, not an exhaustive combination of internal
flags. Paused dispatch can coexist with an unresolved input; its timeout still
requires reconciliation. Successful observation restores current knowledge, not
proof of the prior objective. Resume must succeed with current authority; concurrent
pause/takeover can prevent it. If observation fails, remain frozen and inspect the
native window; dismiss unsupported screens there if necessary. A game restart
invalidates old session authority. No arrow replays an uncertain action.

Pause/takeover stops **new remote dispatch**. An already-running game activity
may continue and require native interruption. Follow the [recovery procedure](runbook.md#pause-timeout-and-recovery)
for operational steps. [Editable state view](diagrams/recovery.mmd).

## Observation and deployment boundaries

The viewer uses actual presented SDL frames, including rendered popups. Structured
scene metadata is deliberately restricted to player-visible facts; it excludes
save contents, undiscovered map data and hidden threats. See the exact observation
allowlist and routine limits in [protocol](protocol.md).

All services are local. The spectator binds loopback; it is not designed for
public network exposure. The game wrapper explicitly supplies the project userdir
and windowed settings. New packages, outputs, caches and saves stay project-local
or in the setup manifest's owned temporary build. [Setup](setup.md) and the
[environment ledger](environment.md) own installation facts and history.

## Change boundaries and verification

Keep the controller independent of HTTP/server and setup tooling; only the server
and CLI assemble it. The viewer consumes the local service contract. Native game
access stays in the integration patch. Configured Import Linter dependency contracts and narrow protocol checks catch
specific source drift; review and real native probes establish broader behavior.
The [control map](controls.md) identifies implemented checks and remaining gaps.

A native bridge/input/renderer, compiler, source-pin or protocol change requires
fresh relevant native acceptance before a new gameplay claim. A documentation-only
or governance-check change does not revalidate the game. [Operations](runbook.md)
provides recovery and acceptance procedures.

Architecture decisions: [native platform](decisions/001-native-platform.md),
[serialized bridge and stack](decisions/002-local-contract.md). Re-evaluate their
assumptions when scope changes. Current architecture is authoritative about what
exists; superseded decisions and dated reports remain historical evidence.
