---
owner: lead
status: historical
date: '2026-10-28'
scope: Accepted direction for the computer-control boundary and coordinated migration; not delivered runtime support
---

# ADR 006 — Basic computer control, player-owned semantics

The owner selected this direction on October28,2026. It replaces the
engine-specific authority direction in [ADR005](005-gameplay-foundation.md).
It does not change the running native7/mission11 contract. Current coupling is
listed in [architecture](../architecture.md#game-family-portability); the
[portability outcome](https://github.com/CVX-Hull/enactive/issues/191) owns delivery.

## Decision and user consequence

The harness exposes basic computer observation/control. The entire playing system
owns game meaning. A menu, unknown screen, inventory selection, ongoing activity,
failed tactic or repeated loop cannot require a new engineer-authored harness
handler before the player can observe or try another basic input.

| Harness responsibility | Playing-system responsibility |
| --- | --- |
| Capture the selected target's actual pixels and mechanical window/input geometry | Interpret scenes, menus, rows, items, coordinates, needs and game identity |
| Basic key, text, pointer and bounded wait operations | Plan, choose inputs, discover controls, save/load through the interface and judge results |
| Own the target/process and serialize dispatch; retain original request/result correlation | Manage tasks, game-time reasoning, progress checks, memory, procedures, learning and context handoff |
| User Pause/takeover, cancellation, finite mechanical resource limits and owned process cleanup | Choose whether to continue, revise a routine, interrupt an activity, recover from a wrong choice or end gameplay |
| Report delivery, capture and target failures with explicit uncertainty | Distinguish delivered input from useful success; retain wrong claims and failures for analysis |

Mechanical metadata may identify the window/process, dimensions, capture time and
input delivery. Game categories, inventory trees, world/character names, turn
clocks and save/goal proofs are not harness primitives or input-authority gates.
Optional semantic/perception helpers belong above this boundary in the playing
system. They remain fallible, replaceable and bypassable through basic control;
moving the same compulsory menu state machine into a differently named adapter
would not implement this decision. Player-authored programs ultimately emit the
same basic controls and may use player-side perception.

A loop or poor choice is player behavior. The player or operator may stop it;
generic deadlines, resource ceilings and evaluator CPU bounds remain available.
The harness does not need to understand a loop, hostile creature or desired
postcondition to permit an ordinary key. Capture integrity, target loss, actual
Pause/takeover, uncertain delivery and storage/provider faults remain real failures.
Removing semantic gates removes a class of artificial control failures; it does
not solve model reasoning, perception, tactics, latency or every delivery fault.

## Portability and implementation boundary

The near-term requirement remains CDDA-class games; broader games are the future
direction. Use an independently shaped non-CDDA fixture and name a representative
second real game before claiming family support. No universal plugin framework,
game ontology, tactical catalogue or new model tier is required. Game knowledge
and learned routines must retain game/version applicability in the playing system.
Only CDDA on the current Mac has actual qualification today.

The backend is a mechanical integration decision: compare maintained OS/window
control with a reduced existing SDL/native bridge against the same pixel, input,
geometry, cancellation and ownership requirements. A native bridge is acceptable
only if it supplies basic computer operations without privileged game facts or
semantic eligibility. Do not preserve engine-specific receiver/recovery categories
as a hidden veto. Reuse a suitable maintained backend before adding custom code;
record capability gaps, permission/focus behavior and operating cost.

## Migration and evidence

First resolve that backend/contract decision with a bounded real-game vertical
proof under [#181](https://github.com/CVX-Hull/enactive/issues/181). Then
[#176](https://github.com/CVX-Hull/enactive/issues/176) owns the playing-system
cutover and deletion of semantic dispatch authority. The proof is an enabler;
it does not qualify the complete migrated product. One coordinated integration
must migrate native/controller contracts, admission/ledger/evidence readers,
Pi/MCP tools, programs/memory/context, custodian, spectator, tests and operating
docs. Retire old runnable paths and reject unsupported current formats under
[S-MIGRATION](../standards/migration.md); retain historical evidence without
restoring authority. A bounded isolated prototype is not a second supported route.

Preserve one writer, target custody, user stop, uncertain/no-replay delivery,
finite costs and exact owned cleanup. Avoid transplanting game-specific root,
macro, activity or identity proofs into the new primitive contract. Separate a
normal process exit from the player's fallible assertion that it saved or won.

Check unknown/changing screens without engine labels, unchanged captures, pointer
geometry changes, target loss, Pause during pending input, cancellation and
unknown delivery. Then let the player pursue useful organic gameplay, including
menus and any interruptions that actually arise; do not script a deliberately bad
tactic to manufacture a pass. Retain incomplete goals and all costs. An API or
fixture pass cannot establish useful cadence, learning benefit or survival.

## Alternatives and reconsideration

Continuing handler-by-handler repairs was rejected: recent failures in healthy
menus and auto-travel recovery show that semantic phase ownership is itself a
source of artificial stops. Keeping compulsory typed skills beside an escape
lane retains two authorities and does not meet the selected boundary. Removing
ownership, delivery uncertainty or user control is unnecessary and rejected.

Reconsider the mechanical backend when it cannot meet the demonstrated computer
operations or has excessive maintenance cost. A request to add game knowledge to
harness authority must return to the owner as a constraint change. Review this
boundary in existing architecture/code/outcome review; no new per-action critic,
approval, scheduler or separate metrics service follows.
