---
owner: lead
review_trigger: Historical pilot record; supersede with new evidence rather than rewriting outcomes
status: historical
date: 2026-10-18
scope: Pilot001 ordinary world creation, unknown transition stop, eligible cleanup and first campaign findings review
---

# Survival pilot001: stopped before character creation

**Outcome: gap, not survival success.** A fresh ordinary world was created through
the graphical menus, but selecting it timed out before the controller received a
terminal acknowledgment. The pilot stopped at fourteen charged inputs. A later
explicit Observe showed character creation; no character had spawned, and needs,
inventory, supplies, travel and rest were not exercised. This does not establish
first-day or seven-day survival, or an unsupported character-creation menu.

This report shares the finding table for [#78](https://github.com/CVX-Hull/enactive/issues/78)
and [#83](https://github.com/CVX-Hull/enactive/issues/83). Their investigation/review
acceptance is distinct from the [campaign outcome](https://github.com/CVX-Hull/enactive/issues/10).

## Admission, configuration and evidence

The [frozen admission](https://github.com/CVX-Hull/enactive/issues/78#issuecomment-6252144495)
preceded the first Resume. Source checkpoint:
`dbc70174230c9efc46005292adb2ad4b5968e867`, clean tracked tree. No source or native
binary changed during the attempt. Installed binary SHA256:
`e3c022b5da440d2e4a31fc537ea07c988c2a767bf96197b83de4c7224d47bf87`, matching the
prior [waypoint acceptance](2026-10-18-waypoint-readiness.md#real-windowed-gameplay).
CDDA 0.I-1, wire v3, UltimateCataclysm tiles, `FULLSCREEN=no`, `TURN_DURATION=0`,
prepared wrapper, explicit project userdir and sole controller on loopback port 8766.
The source-read-only explorer/reviewer did not control the game; the lead was the
single active player/executor. No waypoint task or separately paid model API ran.

The native frame was inspected in the visible spectator at ordinary browser size.
Native app inventory did not expose the directly launched SDL process, so no app
lookup was used to launch a duplicate. Windowed configuration and prepared launch
were checked; native app-window automation is not claimed. An initial sandboxed
process/loopback read failed before admission; scoped permitted reads established
no existing game/service and later captured authoritative responses.

World **Sneedville** used displayed defaults: Suburbia, Cataclysm difficulty and
Lonely NPC density. The inspected load order was Dark Days Ahead, Disable NPC Needs
and Portal Storms Ignore NPCs. Those defaults were not changed. Ordinary character
creation was intended; its scenario/profession were not reached or accepted, so
Evacuee/Survivor must not be reported as the actual spawned configuration. Existing
worlds remained selectable; no existing character was loaded or save edited/deleted.

The admission fixed 150 total charged key/action primitives including creation,
45 minutes and 6 in-game hours, with ten inputs/final two minutes reserved for eligible
cleanup. Play stops at 140 inputs/43 minutes or earlier on unknown/ambiguity. This
attempt never renewed those ceilings. All chosen literal inputs, public reasons,
charges, raw receipts and returned PNGs were retained; a one-off capture called the
existing CLI once per decision and did not plan or retry. Its rationale/scope is
in the admission. Git owns source history; this is bounded external evidence.

Private evidence is under `.runtime/campaigns/survival-pilot-001/`. The small
[manifest](2026-10-18-survival-pilot-manifest.json) identifies selected original
artifacts and the complete private capture index. The live journal was copied only
after the controller stopped; the snapshot/hash does not replace the live journal.

## Observed sequence and resource accounting

| Capture | Expected and actual observation |
| --- | --- |
| 001–010 | Resume, New Game, cancel existing-world selection, World/Create World, inspect default mods and confirm the new world. Supported rendered menus returned; existing worlds were not selected. |
| 011–014 | Return to Custom Character and world selection. Input `4` did not select row4; its receipt was ready but selection was unchanged. PAGE DOWN visibly selected Sneedville(0). |
| 015 | ENTER on highlighted Sneedville, request `657963a1-ac9e-4f45-bc3f-eb943a00a6d2`, five-second deadline: timeout/unknown, charged once. No frame or terminal outcome was invented. |
| 016–017 | Pause, then explicit Observe after expiry: supported paused `NEW_CHAR_POINTS`, session unchanged, revision25, `in_game=false`. This proves the current menu, not the old request's outcome. |
| stopped-status | `frozen=false`, pending/control_pending/lease null after reconciliation; original request remains in unknown history. |
| 018–021 | Independently reviewed eligible cleanup: fresh Resume, ESC, confirm Return to main menu, then Quit. Every cleanup key was charged. No further character creation or supply play occurred. |
| 022 | Confirm Really quit, request `09b357a7-33c6-4ed5-bd26-72771bf28abd`: timeout/unknown because no next-boundary acknowledgment arrived. The owned native process handle independently completed with exit code 0. That exit does not rewrite the receipt. |

Admission: **2026-10-18 16:13:38.987957 UTC**. Fourteen play inputs, four cleanup
inputs, **18 total**. Final dispatch was at 224.087 seconds; its receipt capture was
written at 229.232 elapsed wall seconds. No game-time origin was established;
game hours, needs, supply progress and survival status are unavailable/unexercised,
not fabricated zeros or successes. Surrounding Codex tokens/cost/model identity and
separate review effort were not measured. Reviewer passes are evidence, not human
GitHub approvals or efficacy measurements.

Historical gameplay/recovery unknowns were preserved at startup. This attempt adds
the two identities above; explicit Observe restored current transport capacity,
without resolving their effects. Cleanup cancelled unspawned creation via its
rendered ESC/Yes flow, then used normal Quit. The native process exited with code 0 and the
controller stopped via Ctrl-C; a permitted process/port inspection found no owned
game/controller or port 8766 listener. No character save was needed because none spawned.
Sneedville was retained. No global install/profile/cache change was made.

## Shared finding and disposition review

| Finding and source | User consequence, cause and limits | Disposition, owner, routing and acceptance |
| --- | --- | --- |
| F1: world-selection confirmation timed out;015/017/stopped-status | Creation is blocked for this attempt. Upstream world selection calls setup before character creation; cold loading exceeding five seconds is plausible, not proven. Source does not reconstruct this invocation or prove an engine defect. | Change the next **prospective** #80 brief to use existing per-call `--timeout 15` for declared loading transitions. Lead owns it; no new production timeout or framework. Retest a new admitted creation segment with fresh evidence and original cumulative accounting; preserve this failed attempt. Longer wait is a hypothesis, not a verified fix or permission to replay015. |
| F2: numbered-row key had no semantic effect;012–014 | The player treated an ordinal as a shortcut. Delivery/ready did not establish selection; fresh visible feedback exposed the mistake. No lost transport or broken menu is established. | Change #80's task-selection guidance: interpret actual highlights and known navigation, not assumed shortcuts. No new code/skill verifier. Optional #71 question: which source proves the selected world after a no-effect input? This is development data and must not be relabeled a held-out memory test. |
| F3: retained unknown history plus recovered current state;015–018 | A replacement player must distinguish historical uncertainty from live transport capacity. Current state cannot certify an old request. Existing journals contain both. | #79 handoff must list original IDs, live pending state separately, and consumed resources; fresh authorization remains independent of advisory context. Test missing/corrupt accounting and wrong identity as stops. Reuse files/journal first. No evidence yet requires a database or new observer. |
| F4: manual pilot absent from waypoint progress card; spectator preflight, preflight-status | The native view worked; the waypoint card correctly showed no task. Existing record-only objective/timeline/detail views were not fully exercised for campaign explanation. Owner comprehension was not independently tested. | #79/#80 first exercise existing goal/details surfaces with objective, public next step, budgets and stop reason. New UI remains conditional on a demonstrated missing view. No claim that an autonomous survival task or generic monitor was active. |
| F5: different build/installed binary hashes; admission, setup/prepare source | The lead initially interpreted the manifest hash as older. Setup hashes the build output; preparation relinks/signs the installed copy. Hash difference alone does not establish staleness. Installed bytes match prior native acceptance. | Correct the interpretation, keep both identities and the admission immutable. Lead owns provenance verification; link #75 maintenance without a new defect or renewed review date. No rebuild or setup-control change justified by this evidence. |
| Unexercised areas | No starting inventory, food/water consumption, route, threat, shelter/rest or memory retrieval was observed. A stronger model cannot supply that missing evidence. | No new generalized memory/monitoring/training work. #80 must test survival families; #79 actual handoff. #70/#71 and #40/#42–44 remain optional research/design lanes unless future play establishes a real blocker. |

Source checks: the ordinary CLI supports timeout up to15seconds; controller expiry
revokes authority, retains unknown and pauses. The pinned upstream world picker
returns a selection, `main_menu::new_character_tab` calls `g->setup()`, then
`avatar::create` enters the points menu. These support F1's hypothesis, not its
actual timing. See current [CLI](../../harness/__main__.py),
[controller](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/harness/controller.py) and [native bridge](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/native/cdda_harness.cpp).
`tools/setup.py` hashes the build output; [preparation](../../tools/prepare_game.py)
changes dependency links and signs the installed copy. No source modification or
synthetic passing replacement was used to explain this failure.

## Review adoption and next work

Keep the campaign review workflow: it caught a semantic no-op, preserved unknowns,
and allowed safe cleanup without claiming successful creation. Simplify execution
by sharing this table between #78/#83, retaining one capture index and using native
GitHub routing. No second retrospective, findings database or scheduler. Actual
review time/cost is unavailable; admission, cleanup and final outcome reviews are
separate scoped passes. No recurrent survival defect or causal improvement can be
inferred from this one unspawned development attempt.

The [next brief](../changes/015-campaign-continuity-rehearsal.md) specifies the
minimum #79/#80 work and unresolved design/validation gates. Their estimates stay
M/Low, 2–4 and M/Low, 3–5 focused sessions: this menu-only attempt supplies no survival
throughput for a tighter forecast. #81/#82 remain blocked on actual rehearsal,
continuity and reviewed readiness. #26/#75 maintenance links retain their original
triggers/dates. No accepted foundation issue is reopened, and no new capability
child is justified yet: existing timeout configuration and owned follow-ups fit.

Independent review must accept this exact evidence/routing record and next brief;
common checks and exact-candidate/merged-main CI are publication evidence only.
Their terminal results belong in the publishing PR. This report does not claim a
new native build, completed first day, seven-day readiness, reliability, learning
or comparative model/cost benefit.

The initial public manifest draft failed the existing strict acceptance schema.
It was reshaped to that established format, retaining detailed counts/outcomes in
this report and the original private capture index. No schema/control was weakened
or expanded to accommodate the draft; document/governance checks then passed.
