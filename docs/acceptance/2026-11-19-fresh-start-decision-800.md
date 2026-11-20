---
owner: lead
status: historical
date: '2026-11-19'
kind: review
scope: 'Opening decisions in sealed development starts, a named reload and a same-session handoff'
---

# The first decision on a declared fresh start (#800)

## At a glance

Talty and #799 both saw **Preset Character** highlighted in New Game. Both
players tried to establish whether a survivor already existed. Talty waited
for a rendered result and found a quit dialog. The #799 player included
Enter in the same batch and lost custody before it could see the result.
The native exit and the effect of Enter remain unexplained.

The original assignment called the world fresh and also asked the player to
verify that setup had never started. The operator can resolve that question
for the first actor by verifying the configuration-only start. A successor
still needs to establish continuity from the current screen and its sealed
report. The retained evidence supports testing that distinction in one new
Campground acquisition. It establishes neither the cause of the player's
choice nor the effect of changing the brief. [Original run](2026-11-19-campground-opening-menu-799.md)

## What the players received and did

| Admission and actor | Evidence at the first decision | What the next observation established |
| --- | --- | --- |
| [Campground #799](2026-11-19-campground-opening-menu-799.md), opening actor | Request 1 observed. Request 2 contained frame 2 showing New Game with Preset Character selected and Custom Character above it. The actor proposed checking for an existing survivor, then sent Escape, Right and Enter in one operation. | Native receipts for operation `eec1b51e056e48888af8339d5ad7a0b4` record two delivered inputs and unknown delivery for Enter. Collection on that ID remained unknown. The input fence refused the next observation. No rendered result identified a menu, world or survivor. |
| [Talty #794](2026-11-19-talty-campground-stream-stop-794.md), opening actor | Same base mission and guide as #799. Frame 2 again showed Preset Character. Request 2 took the same detour with Escape and Right, then waited. | Both keys were delivered. Frame 3 showed “Really quit?” with No selected. Frame 80 later showed Load. The player eventually reached highlighted Custom Character in frame 138, confirmed separately in request 11 and reached Morgan Reed in play. |
| [Townsend #762](2026-11-18-wilderness-delayed-memory-762.md), opening actor | The brief explicitly assigned fresh creation. From Preset Character in frame 2, request 2 navigated to World with two Right inputs. | Frame 4 showed Create World before confirmation. Frame 59 later showed Custom Character before request 8 confirmed. Frame 203 offered Campground, frame 266 showed the accepted editor choices, and frame 357 showed Morgan Vale at the campground. |
| [Oceana #788](2026-11-19-oceana-farm-memory-788.md), first admission | The Farm player used the setup guidance reviewed in [#786](2026-11-19-farm-setup-selection-786.md). From Preset Character in frame 2, request 2 moved Up. | Frame 3 showed Custom Character selected. Request 3 then sent Enter. The player reached default world creation, the accepted Farm editor choices in frame 237 and a playable survivor. |
| [Oceana #788](2026-11-19-oceana-farm-memory-788.md), third admission, actor 002 | Actor 001 sealed a handoff in request 139. The successor received the admission's original Load assignment, its own audit IDs, and the labelled report from actor 001 saying Load had already completed and the overmap was open. | Request 1 observed the overmap in frame 12644. Request 2 inspected inventory and received frame 12746. The successor resumed the established game. This verifies the handoff through the first action. |
| [Townsend #762](2026-11-18-wilderness-delayed-memory-762.md), first reload, actor 001 | A new admission's first actor received a named Load assignment and checkpoint history, with no same-session sealed predecessor. Frame 2 showed Load and Townsend. | Frame 3 identified Morgan Vale for selection. Frames 189 and 215 established the loaded checkpoint and survivor. The absence of a same-session report is compatible with a named reload. |

The [Farm setup review](2026-11-19-farm-setup-selection-786.md) also separates
a wrong highlight in Thedford, a confirmed editor entry in Regent, and accepted
Farm selections in Malvern. Those examples explain the existing selection
instruction. They do not settle what Escape, Right and Enter did inside #799.

## Offline readback of the change

Replace the opening paragraph and the next two sentences of the #799 base
mission with the text below. The existing instruction beginning “Confirm
Custom Character only after a returned view visibly highlights it” and all
subsequent instructions carry forward.

> Your assignment is one fresh world with default world rules and a custom Survivor in Wilderness, starting at Campground. Choose the survivor and all remaining setup options yourself. If you are the first actor on this fresh admission, the operator has verified that it starts with no saved world or survivor. Observe the current screen and begin the assigned setup from the menu you see. If you have a sealed report from a predecessor in this session, observe first and use the report as fallible context to continue the same game or its unfinished setup. If the screen conflicts with the assignment and you cannot establish how to continue, stop and report what you see.
>
> On the title screen, inspect the New Game submenu if it is already open. If you change menus or move a selection during title-screen setup, read the returned view before sending a confirmation.
>

For each actor above, the review replayed the first three sent request
manifests. Their first user-text digest matched the frozen actor prompt,
two newlines and the text from the initial `knowledge-delivery` event. Each sent image digest
matched its retained PNG. The six original first user texts had different
digests. The base mission in #794 and #799 had the same SHA-256,
`0c6557998138f230ec2f5ec8b4e154ef01a02da119a67f1522ae2254cb2c08a3`.
The driver adds an actor's audit IDs in every case. Only a same-session
successor gets the separately labelled sealed predecessor context.
[Driver](../../tools/campaign_player.py) · [Player host](../../tools/player_host/host.mjs)

The offline substitution applied the revised base mission to the two Campground
opening contexts. In a copy of the Oceana successor context, it replaced only
the sentence beginning “If you received a handoff inside this admission” with
the revised sentence beginning “If you have a sealed report”. That preserved
the actual Oceana Load assignment, survivor, checkpoint and sealed report.
The actor audit IDs and delivered briefings remained byte-identical.
The fresh role permits beginning setup from frame 2. It requires another view
before confirming a changed selection. The successor role at frame 12644
calls for continuing the existing game using the overmap and the fallible
report. The report's context ID was `8ae289a94cb246c3bd0d6a99ba00ba87`.
The Townsend reload keeps its distinct Load assignment. These were text and
screen readbacks. No model chose an action under the revised wording.

To reproduce the cutoffs, use the actor's `host.jsonl` with `iter_host` and
`request_context`, select requests 1–3 and compare the user text and sent
image parts. For Townsend use its recorded source `99c87aa0` and host/7
reader. The other cases use host/8. The tracked SHA-256 lists identify the
original traces, prompts and images. [Evidence index](../../data/evidence/index.json) · [Context replay](../../harness/evaluation/core/context.py)

## Disposition

Stage a single fresh Campground world with this opening. Townsend establishes
that the exact assignment can reach play. Talty and Oceana show that the
menu and confirmation can be read separately. A menu-only admission would
duplicate the opening and could never reach the delayed choice. Use the
existing finite study, setup stop, conditional reloads and independent
before-and-effect scoring. A failed opening uses the study’s one fresh-start slot. Keep
the pinned full-context route, ordinary tools, sealed handoff and partial
delivery fence. The next live package requires fresh owner approval.
[Study design #797](https://github.com/CVX-Hull/enactive/issues/797) · [Review #800](https://github.com/CVX-Hull/enactive/issues/800)
