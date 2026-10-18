---
owner: lead
review_trigger: Native menu classification, pinned callers, probe scope or input authority changes
status: proposed
---

# Ordinary survival menu coverage

[#112](https://github.com/CVX-Hull/enactive/issues/112) addresses the actual failed
[functional continuation](../acceptance/2026-10-18-seven-day-continuation-stop.md).
Registered normal `listitems` entered a readable `LIST_ITEMS` boundary classified
unsupported. The player stopped and handed off correctly. No seven-day or new
first-day success. Wider permissions cannot repair this native classification.

## Decision and reuse

Extend the existing finite native menu set for source-reviewed ordinary nearby
items/creatures and useful work menus. Preserve unknown categories as unsupported,
DEFAULTMODE's exact normal/direction scopes, deathcam/activity/debug/recovery
precedence, registered native bindings, frames, generations, expiry and Pause.
Do not admit every input context or infer authority from an advertised action.
No native-wire, Python/HTTP result, persisted-format or timeout change is needed.

Pinned engine `game.cpp` owns `LIST_ITEMS`/`LIST_MONSTERS`; `crafting_gui.cpp` owns
`CRAFTING`; `construction.cpp` owns `CONSTRUCTION`. These are input loops for
ordinary player menus. Only LIST_ITEMS is an actual campaign failure; other additions
are a proportionate static audit to avoid serial predictable menu-only failures.
Their entry/exit must be exercised in the real game before claiming coverage.
Nested already-admitted selectors/filter dialogs keep their current rules; other
unknown boundaries still stop. No claim of every crafting recipe, construction,
item action, consuming behavior or activity outcome follows from menu entry/exit.

Item detail (`ui_iteminfo.cpp`, `iteminfo_window::execute`) and comparison
(`game_inventory.cpp`, `compare_item_menu::show`) use the generic lowercase
`default` category. Do not add that name to the menu set. Generalize the existing
direction-query RAII marker to `menu_query(category)` and migrate its one caller.
Only these two additional pinned `ctxt.handle_input()` calls receive the marker,
inside a lambda that ends before caller callbacks, preserving upstream bindings.
Activation requires in-game, an empty scope stack and no active query; the input
scope admits only the exact marked category while its stack is still empty.
Nested/unknown contexts cannot inherit this marker permission. Existing debug/activity
scopes prevent marker activation. Deathcam’s unowned `DEFAULTMODE` remains blocked;
`in_game` is a world-lifetime flag, not an aliveness test, and menus cannot establish
character survival. Visible death remains an unconditional study stop.
`DEFAULTMODE` outside the exact direction owner and
`default` outside these exact item owners stay unsupported. Keep one current marker,
remove the former class/variable/callers, and pin/verify both added upstream files
against the already verified official source archive. Do not rename engine contexts.

Reuse current instrumentation and the engine's registered actions instead of a new
classifier, UI planner or keybinding inventory. A finite list costs maintenance at
upstream changes, but blanket admission would lose the explicit boundary distinction.
Lead owns this small native boundary; re-audit actual caller semantics when a pinned
caller changes or a new observed context blocks play. Existing setup/patch/build,
CLI/parser/validator, source checks, Git/GitHub and literal capture tools remain.
No new dependency, compatibility path, global setup or generic test framework.

For the short proof, reuse the prior passive native-probe recorder, changing only
its investigation charge cap to32. Its counter starts at0 for this separate40-input
probe; original whole76 is a separate retained debit, not a reset. Lead checks that
sum and original whole deadline before every dispatch. The recorder reuses argparse
and native state validation, copies only the exact response frame and never sends
input itself. Literal CLI execution and permission review stay separate. Scope/
semantic checks remain procedural; retire this private artifact after closeout.

## Implementation and review

Lead owns design, this small native-set edit, integration, current guidance, build
and shared runtime. Read-only source sweeps identify related ordinary loops;
independent clean-context review checks actual semantics and that restricted cases
remain excluded. One isolated clean-context worker may own native marker/patch/pin/
fixture changes; the lead owns documentation and shared runtime integration.
This cohesive refactor has disjoint ownership, not concurrent writes to one source.
Existing portable regressions/source controls check unchanged authority/unsupported
behavior; do not add a string-presence test mirroring the new set and call it native
execution. Native compilation and the actual probe are separate required evidence.
Record all failed source/build/probe checks without retrying unchanged failures.

Game/controller/port are now stopped. Preserve the previous ignored binary/manifest
as historical build evidence, commit the reviewed source, then use existing
`tools/setup.py --build --jobs 6` and `--install` in the recorded owned temporary
workspace. Install only with the game absent; use the prepared project-local
windowed wrapper/userdir. No runtime source writes/builds/tests during the frozen
probe. Git owns tracked source identity; checksums identify native/external evidence.
Protected PR exact-candidate and merged-main CI remain required for publication.

## One prospective native probe

After committed candidate, source/diff review, common checks, actual build/install
provenance and paused access preflight, lead may admit **one** ordinary functional
probe on the same normally saved Ned Meyers/Belgium. Freeze exact candidate/native/
helper, original creation-clock lineage and all inherited costs locally before input.
This does not resume either failed study or claim a single frozen-candidate campaign.

Limits:40 charged inputs/45 wall minutes/60 additional game seconds; stop investigation
at32inputs/35minutes, reserve8/final10minutes for eligible normal cleanup/review.
Every key/action/recovery costs1, full requested walks count; passive/Resume costs0
inputs but consume time. Ordinary deadlines5s, only the actual selected-Ned Load
confirmation may use a prospectively declared15s. Whole lineage retains original
2600/24h (2400/22h investigation,200/final2h reserve), now76charges spent. No deletion
or new character to renew limits; retain old unknowns and failures. Local probe
captures at most64MiB, stop at56/reserve8; immutable originals stay preserved.

Normal Load once, then fresh supported paused normal scene/calendar/location and
no live request/control/lease permit deliberate identity-only Resume and actual
character-sheet verification. A Load timeout remains unknown, never retried. Once
identity is verified, enter the ordinary nearby-items menu, inspect actual frame,
switch to creatures and back if actual registered controls permit, exercise one
noncommitting nested filter/cancel path, then return to normal. Enter/cancel crafting
and construction menus without starting work. Exercise actual item-detail and
comparison input/exit through their exact marked owners, and an ordinary direction
chooser/cancel regression without moving or picking anything up. Select only actual visible/registered
inputs; no binding changes, hidden state, debug advantage or native UI/user keys.
Confirm actual normal calendar/identity and paused state after these checks, then
normal Save/Quit and owned process/controller/port shutdown. Scope establishes menu
navigation only; no task completion, resource acquisition or sustained survival.

A timeout remains charged unknown; stop active tools and Pause. Lead may explicitly
Observe after expiry and use fresh supported evidence for a justified different
step within this fixed scope, never replay, renew a clock or infer an old ACK.
Actual denial, unsupported/unreadable state, identity mismatch, death, limit,
source/native/helper change or human rescue ends investigation; only eligible
cleanup remains. No alternate actor/permission/transport workaround. The earlier
cleanup-only SIGINT exception has expired and grants no new input here. User
Pause/takeover remains authoritative; intentional takeover waits for user resumption.

Independent read-only review checks exact costs/frames/menu contexts/unknowns and
cleanup. Publish the failed continuation and this separate probe with honest lanes,
current pointers, affected control records without unrelated date renewal, Issues/
Project and public commit identities/full messages. Only a later explicit prospective
survival decision can use remaining original lineage resources after acceptance.
