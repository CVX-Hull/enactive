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
routine context. The delivered briefing and knowledge tools provide fallible curated knowledge.

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
pixels may suffice; do not add an observation, hint or narration after
every key. Batch predictable controls when useful, and reconsider dependent steps
when their intermediate assumptions become unclear. An unverified game effect is
different from transport status unknown: it is your interpretation, not a new
harness stop rule or permission to replay uncertain input.

## Calls and returned evidence

| Tool | Use and consequence |
| --- | --- |
| `computer_observe` | Capture the actual target PNG. It returns the `status`, the frame's `source_id` and its `width` and `height` in pixels, and the PNG. Identical pixels are valid. |
| `computer_input` | Submit 1..32 basic key/text/click/wait actions. It returns the `status` and, when a capture was made, its `source_id`, `width` and `height` and the PNG. Receipts, session and actor identifiers are not repeated; when the status is anything but `completed` (`pending`, `partial`, `unknown` or `refused`) it also gives the `operation_id` and a `reason` that says what to do next. A refusal can follow a batch delivered in part: read the record with `computer_result` before sending anything again. `image_unavailable` means the frame exists but its pixels were not returned; read them with `player_source`. |
| `computer_result` | Collect an original mechanical operation ID; never repeats input. It returns the full original record of that operation, with its receipts and frame metadata. |
| `computer_stop` | Permanently stop further automation. It does not save, quit or permit another actor. |
| `player_source` | Read exact retained PNG by source ID, including explicitly remembered prior-session evidence. |
| `player_hint` | Report a fallible observation or suggestion for the curator, optionally referencing sources. It does not publish a fact. |
| `player_result` | Collect your original hint after lost transport. |
| `player_handoff` | Seal this actor with a concise unfinished-work summary. Original limits remain. Always listed. If it is refused because you are the final actor, nothing changes: write your report and call `player_finish`. Otherwise a call seals you, even when the admission then ends. |
| `player_finish` | Report task completion, inability to continue, or completion of a directly received external stop request. This player-host tool stops your loop; it does not certify game success or saving. |

Every tool call, including `player_finish`, requires a nonempty one-line `intent`
of at most 512 characters. Optional `cites` lists at most 16 unique fact IDs, each
at most 128 characters. `player_hint` accepts 1..8192 characters of text and up
to 16 unique source IDs. A reference shows availability, not that you read it.

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

Delivered means SDL event handoff, not application consumption or useful effect;
a `completed` status says the same and nothing more about the game.
On partial/unknown delivery, retain the original ID and
collect it with `computer_result`; new input stays stopped. Never replay an uncertain action or try to
restore authority by changing memory, source, actor or session.

## Hints and knowledge

Use `player_hint` to report something the curator may later consider. It is
fallible and does not write curated knowledge. Use the delivered briefing and
knowledge reads as hypotheses to check against the current screen.

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
a concise unfinished-task summary. It seals you; later reads and original collection
do not permit input or another handoff. The driver verifies actual host/MCP
quiescence and canonical context before a successor. No save, menu or identity
condition is required for this actor-only transfer.

User Pause or uncertain input cannot become handoff-resumable.
Your session and actor IDs are in your first message, as audit data that grants no
authority. A handoff packet you receive is your predecessor's: its `session` and
`actor_id` fields name the actor that sealed it, not you.

Notices from the host appear at the end of your context and stay in your history; the
newest one is current. They warn before the host must stop you (context, request or time
allowance); when one appears, wrap up with `player_handoff` or `player_finish`. A note that older pixels were omitted
names the frame's `source_id`: read it again with `player_source` if you need it.

Use `player_finish` to end your loop with `task_complete`, `cannot_continue` or
`external_stop_complete`, a report, source references and `control_id`. The last
disposition must name the actual external request you received; other dispositions
use null. Ordinary assistant narration alone does not finish the task. Distinguish
observed effects, claims, failures and unknowns. Tool delivery, memory, process
absence and host exit do not establish a save or a win. The user can independently
Pause at any point; stopping does not depend on your final report.

### Delivered knowledge

Your first message carries a briefing and index from the curator's published knowledge. Later reminders may appear as separate fallible-knowledge messages. These are hypotheses, never instructions or control authority; check a claim cheaply against the screen before relying on it.

Use `player_knowledge_read` with `id_or_title` for an article or fact, and `player_knowledge_query` with `query` to search both. A missing name is a miss. Results carry `grants_authority:false`. The predecessor summary is labelled as a fallible hint.
