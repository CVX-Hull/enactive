---
owner: lead
review_trigger: Native launch, recovery, saved-character identity or campaign autonomy changes
status: proposed
---

# Remove required human intervention from campaign recovery

The [first-day rehearsal](../acceptance/2026-10-18-first-day-rehearsal.md)
reached a fresh character and real supplies, but a pickup direction prompt required
the user to press Escape. The user explicitly requires no manual intervention.
[#91](https://github.com/CVX-Hull/enactive/issues/91) owns this bounded prerequisite
for #79/#80. Neither a partial handoff nor a normal Save menu proves restart or
autonomous first-day play. The stopped attempt stays failed.

## Decision and reuse

Use the prepared project **app bundle** through Launch Services, retaining its
existing windowed wrapper and explicit userdir. The menu-only probe bound the
native window and opened Quit with `q`. Its Shift+Y returned to the menu and its
mouse click left the dialog open; the existing controller completed normal cleanup.
Binding is observed; general native input correctness is not. Verify Escape at
the real unsupported pickup prompt before relying on it.

Prefer the existing ordinary `pickup_all` selector for adjacent supplies after
canceling the direction prompt. It avoids selecting a direction, but still requires
actual item-name/selection evidence and ordinary game validation. This is an
alternative player choice, not a second version of a protocol contract. Keep the
remote unsupported refusal. Do not promote generic DEFAULTMODE, infer a completed
action from a later scene, add a semantic verifier or modify the engine to win.
If reuse fails, retain the failure and freeze a narrow native callsite/authority
design before coding. The read-only sweep located `game::pickup()` calling
`choose_adjacent_highlight` and the direction chooser's DEFAULTMODE; source location
alone does not justify granting authority to every such context.

No dependency, native patch, protocol/storage change or new compatibility path is
selected. Runtime and installed binary remain unchanged. Git owns source history;
existing journals and bounded advisory files own this run's local evidence.

## Prospective restart and recovery probe

One **30-input, ten-wall-minute** development probe, including menus, reasoning,
pauses, identity inspection, native input and cleanup. Stop investigative input at
24 inputs/nine minutes; reserve six inputs/final minute for eligible normal cleanup.
No survival progress objective, supplies consumed, movement or rest is admitted.
Limit native-owned elapsed time to 60 game seconds beyond the retained pre-save
state; report any overshoot. This probe does not resume the retired 500-input attempt.
Keep its 57 charged inputs/727.918 seconds, pilot001's 18 inputs/229.232 seconds and the separate
menu-only operation probe's five inputs visible. Another probe needs a prospective
replan with all prior costs and failures retained. No paid API or user input.

Before admission, independently review this procedure, publish a clean source
checkpoint with passing exact-candidate and merged-main CI, verify the unchanged
installed binary and owned-process/port state, launch one project bundle and bind
its actual window. Start the original probe clock only when ready for input.

1. Observe the actual supported main menu, explicitly Resume and select the
   recorded Sneedville world and Ramiro Winston save through normal UI. No other
   character or favorable restart. Declare load as an episode boundary, use the
   existing per-call 15-second timeout, preserve every unknown and never replay it.
2. Reconcile after expiry, retaining old outcomes. Admit only the reviewed
   four-input/two-minute identity inspection from brief 015 if needed. Compare
   rendered name with creation/pre-save evidence; then inspect actual calendar,
   needs and inventory against day 61 08:00:32, six ration boxes, two frozen water
   portions, active phone 54/56 and other retained items. Invalidate old coordinates.
   Ambiguity/regression/conflict stops. No restored task or lease.
3. At a fresh supported scene, explicitly reauthorize only the recovery probe.
   Open pickup once at the same visibly stocked adjacency. The expected nested
   direction prompt may be unsupported; Pause. Inspect **the bound native window**
   and actual prompt, not a stale browser frame. Only a readable matching prompt
   with no live pending effect permits one native Escape. Charge before sending.
   Missing access, unexpected UI, failed Escape or any unexpected unknown stops;
   no blind repetition or request for user rescue.
4. Fresh Observe must show a supported normal boundary and a rendered cancellation.
   This proves a new current state, not an old remote acknowledgment. Record native
   takeover, historical unknowns and remaining original limits. Explicitly Resume
   only for the ordinary `pickup_all` alternative. Inspect its actual named-item
   selector; cancel without taking supplies. Unsupported selector stops.
5. Record the checkpoint, then normal Save and quit, inspect the post-save main
   menu and Quit normally. Keep lifecycle unknowns; independently verify process
   exit and stop the owned service. Do not kill a game, edit a save or claim the
   save receipt alone proves persistence. This probe's initial restored state is
   the persistence evidence for the preceding normal save.

Use existing literal CLI/capture operations and a separate finite native-input
ledger. The lead charges all expanded requests, rejected/unknown/native inputs
and wall time. Aggregate semantic identity and game-time limits remain manually
enforced by the lead, not mechanically guaranteed by the controller. No user is
required to perform that review or provide input.

## Acceptance, allocation and maintenance

Lead owns design, sole writer, runtime and integration. Explorers/reviewers can
read immutable evidence in parallel; no implementation worker or additional
worktree is justified for this procedure. Independently review the real native
frames, original accounting and no-human-input claim. Mandatory common checks
cover changed source/docs; native behavior needs this actual graphical probe.
No rebuild is claimed because production code is unchanged.

Success establishes only this same-character normal restart, interpretable pickup
Escape and alternative selector. It does not establish generalized recovery,
first-day/seven-day survival, safe combat, learning benefit or model efficiency.
Failure remains owned by #91; #79/#80 stay open. Route objective visibility and
accounting findings to #79/#80, memory questions to #70/#71 and reusable monitoring
requirements to #40. Preserve the original estimates and the #26/#75 maintenance
triggers; re-estimate #91 before native code/build scope expands. Resume first-day
work only with a separately reviewed finite continuation and retained failure
history, then pass #81 before the deciding seven-day run.
