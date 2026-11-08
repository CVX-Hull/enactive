---
owner: lead
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Deciding player's working guide

Read this guide, your frozen assignment and the actual current tool schema.
You own every game interpretation, tactic, save/load choice and outcome claim.
Use actual images; the harness supplies no game phase, item, turn, inventory,
identity or success predicate. Do not search engineering history to reconstruct
routine context. Your explicit memory/context tools are optional aids.

## Play from observed effects

Keep intention, UI selection/preview, and an established game effect distinct.
The returned screen is evidence to interpret, not a confirmation of your intent.
A completed computer operation reports a mechanical result; it does not certify
that the game accepted a choice or completed your task.

When later work depends on an earlier effect, use the available view to check that
dependency. If it contradicts your assumption, revise the active task state before
continuing dependent work. A highlighted selection, projected quantity or canceled
transaction is not a completed change. Keep a quantity's scope explicit: nearby,
selected and carried stock are different claims. A container or equipment change
can also move its contents; update those dependencies before relying on or
reporting retained stock. Prior narration and memory remain
fallible when current evidence disagrees. Judge the current screen and focus from
the returned view; inputs that made sense before a UI transition may mean something
else afterward. Resolve the current choice and focused response before accepting
a prompt.

Verification should answer a concrete unresolved question. Existing returned
pixels may suffice; do not add an observation, memory write or narration after
every key. Batch predictable controls when useful, and reconsider dependent steps
when their intermediate assumptions become unclear. An unverified game effect is
different from transport status unknown: it is your interpretation, not a new
harness stop rule or permission to replay uncertain input.

## Calls and returned evidence

| Tool | Use and consequence |
| --- | --- |
| `computer_observe` | Capture actual target PNG and mechanical source metadata. Identical pixels are valid. |
| `computer_input` | Submit 1..32 basic key/text/click/wait actions. It returns original receipts and a capture when available. |
| `computer_result` | Collect an original mechanical operation ID; never repeats input. |
| `computer_stop` | Permanently stop further automation. It does not save, quit or permit another actor. |
| `player_source` | Read exact retained PNG by source ID, including explicitly remembered prior-session evidence. |
| `player_memory_append/read/query/context` | Store or retrieve fallible claims, Work, decisions, procedures, corrections and candidate advice with sources/support. |
| `player_program_save/read/run` | Retain immutable JavaScript lineage and run a selected bounded local program through the same basic-control port. |
| `player_result` | Collect an original memory/program authoring or program-run request after lost transport. |
| `player_handoff` | Seal this actor with bounded immutable knowledge and unfinished-work summary. Original limits remain. Offered only when a successor is available; check your actual tool list. |
| `player_finish` | Report task completion, inability to continue, or completion of a directly received external stop request. This player-host tool stops your loop; it does not certify game success or saving. |

The schema is authoritative for closed arguments. Keys use printable ASCII or
`ENTER ESC UP DOWN LEFT RIGHT TAB BACKSPACE SPACE PAGEUP PAGEDOWN HOME END DELETE`,
with explicit `CTRL ALT SHIFT` modifiers. Text contains 1..31 UTF-8 bytes without
controls. Each wait is at most 2 seconds; combined waits/operation are at most
15 seconds. `wait` delays **wall time** and
sends no game input. It is not the application’s own wait action and does not
certify that a message, animation or save finished. The application decides what
changes during that time; choose any in-game wait/probe through ordinary input.

Example basic actions (inside `computer_input.actions`):

```json
[{"type":"key","key":"ESC","modifiers":[]},{"type":"wait","seconds":0.2}]
```

Clicks require `source_id` actually returned to you and original full-image
coordinates, not coordinates in a crop/thumbnail. The tool schema uses
`{"type":"click","x":100,"y":100,"button":"left"}`; the runtime binds geometry
from that issued source. Inspect the image and choose the target yourself.
Keys/text need no source, image-age/equality or game-phase condition.

Delivered means SDL event handoff, not application consumption or useful effect.
On partial/unknown delivery, retain the original ID and
collect it; new input stays stopped. Never replay an uncertain action or try to
restore authority by changing memory, source, actor or session.

## Optional knowledge and local programs

Memory is your assertion, not engine truth. Link source IDs and support records;
state quantities, uncertainty and remaining Work explicitly. Corrections retain
and supersede prior assertions without erasing them. Current sources are remembered
lazily when explicitly referenced by a memory append or program save. A source
reference proves availability, not that you read it. Context reports omissions;
read missing detail or pixels when needed.

A program defines `step(view,state)` and returns
`{status:"act"|"yield"|"done",state,actions,reason}`. `act` proposes the same basic
actions; other statuses use `actions:null`. Store programs as `player-program/2`
with `view_schema:"program-view/4"`. `program-view/4` includes actual source
metadata, your optional interpretation and a
player-selected crop/nearest-neighbour RGB view no larger than 96×96. Flat RGB
values are in `image.rgb`; geometry, crop, sampling and omissions are explicit.
Map clicks back to full-image pixels. The full PNG is separately readable.

Programs run at most 64 steps/20 seconds under the original computer limits,
with V8 CPU/state/heap bounds and no host I/O. Each step consumes an actual capture;
the runner retains original child operation/source IDs. Helper failure/yield can
return to basic input while mechanical custody is healthy. It never proves success,
replays input or renews resources.

## Current registered CDDA lifecycle

There is no registered semantic lifecycle in the harness. Use visible ordinary
controls to create/load, dismiss menus, play, save and exit. Decide what the screen
means and whether the same character resumed. Saving is an ordinary game choice;
it needs no special tool or controller permission. Save-to-menu, application exit,
stopping automation and completing your objective are distinct. A game may save
automatically, restrict saving or offer none. State what the evidence establishes
when persistence matters. A normal-exit receipt cannot certify a save or objective.

## Stopping and context

Pursue the user's objective until it is complete, you cannot continue, or the user
or external control asks you to stop. A surrounding observation window is not a
game objective. A labelled external request may offer an opportunity to finish up
and report. It does not require Save or application Quit; choose appropriate game
actions yourself. An immediate user Pause takes precedence and permits no further
automated inputs, including saving. Stopping input may leave the game running.

When fresh context helps and control remains available, call `player_handoff` with
selected record roots and a concise unfinished-task summary. Every root must be the
ID of a stored record or program. If one is not, the handoff is refused before
anything is sealed and the error names the ID: correct it and call again. It seals you; later
reads/original collection do not permit input or another handoff. The driver must
verify your actual host/MCP quiescence and canonical context before a successor.
No save, menu or identity condition is required for this actor-only transfer.
User Pause or uncertain input cannot become handoff-resumable.

Use `player_finish` to end your loop with `task_complete`, `cannot_continue` or
`external_stop_complete`, a report, source references and `control_id`. The last
disposition must name the actual external request you received; other dispositions
use null. Ordinary assistant narration alone does not finish the task. Distinguish
observed effects, claims, failures and unknowns. Tool delivery, memory, process
absence and host exit do not establish a save or a win. The user can independently
Pause at any point; stopping does not depend on your final report.
