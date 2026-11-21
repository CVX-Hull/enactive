---
owner: lead
status: historical
date: 2026-11-05
scope: Agreed player-objective and external-test-control rationale; candidate implementation, not adoption or real-play acceptance
---

# Keep the player's objective separate from test control

## Decision and intended result

[#164](https://github.com/CVX-Hull/enactive/issues/164) remains unqualified. The
[context audit](../acceptance/2026-11-05-player-context-audit.md) traces current main
`9a6697223e7821ab38609bd32d0115b76b61141f` and the retained Alex trajectory.
The player was told to finish at 48 hours, reached that target and ended
dehydrated without replenishment. Its public explanations prioritized the target
and conserving requests. This is a reason to correct the experimental incentive,
not proof that the instruction caused all the planning or visual failures.

The agreed result is one player with an ongoing user objective, a faithful
computer interface and separately controlled finite tests. For example, the
player is asked to survive and build a sustainable situation. The test observes
the first two days without telling the player to finish at that point. When the
test needs to end, it can offer the player a bounded opportunity to finish up,
then stop automation. The player chooses any game actions appropriate to that
request. Stopping automation does not require saving or quitting the game.

The owner agreed to this design for source implementation and offline verification
at $0 gameplay/model spend. This page retains the agreed rationale, rather than
owning current executable behavior. The [architecture](../architecture.md),
[computer/player contract](../contracts/computer-control.md),
[host contract](../contracts/player-host.md) and
[campaign procedure](../operations/campaign-run.md) describe the candidate source.
Main retains its earlier contracts until the candidate is adopted; this record
claims neither adoption nor real-play acceptance. The lead owns integration and
verification. An exact paid diagnostic must be frozen and agreed separately; no
old admission is reopened.

## Options and recommendation

| Option | Concrete consequence | Tradeoff |
| --- | --- | --- |
| Wait for unrelated play | Reuse a future eligible recording if it supplies useful actions and an organic local program | No immediate implementation or spending, but the current instruction and quota exposures remain; there is no active eligible run to wait on |
| Change only the assignment | Replace “finish after 48 hours” with an ongoing objective | Quick, but host countdowns, tool results and programs still expose the experiment; stopping still depends on the old final-actor instruction |
| Coordinated player/test separation | Keep the ongoing objective, remove test countdowns from every supplied context path, and request ending externally | Recommended. More source work, but it addresses the demonstrated boundary and produces a meaningful next diagnostic |
| Build a general unattended service now | Add unlimited admissions, automatic compaction/restarts and broader recovery | Premature. It would combine unqualified gameplay with new recovery and deployment guarantees; it is unnecessary for the next informative test |
| Start the full cohort now | Repeat many runs with the present context and incomplete local-effect evidence | Reject. More samples would not resolve the changed instructions or missing admission evidence |

The player's objective has no default test finish line. A finite test samples a
prefix of that ongoing task; an external stop is an observation boundary, not a
win or survival failure. This does not remove the finite authorization of current
experiments or claim that unattended operation is already supported.

## Responsibilities and reuse

| Owner | Required behavior | Existing mechanism to reuse |
| --- | --- | --- |
| Deciding model and player system | Interpret pixels, choose plans/actions, verify effects, manage fallible knowledge and report completion or inability to proceed | Compact guide, current MCP tools, selected model/tool loop, player memory/programs and sealed handoff |
| Mechanical custodian | Serialize basic input, preserve exact originals, enforce authority and independent permanent Pause | Current computer port, native packets, original stores and exact process handles |
| Test controller | Freeze finite allowances, enforce spending/time/input limits, retain failures, request orderly ending early enough and assess the result | Existing campaign package, driver, host accounting and custodian closeout |

### Saving and application lifetime

The controller's portable obligation is to stop further automation when requested,
independently of a model reply or any game-save mechanism. It reports dispatched
or uncertain input honestly. Stopping input does not promise to pause a real-time
game, undo already delivered events or stop engine-owned activity.

Saving is an ordinary game choice made through the available interface, without
a special save tool or permission request. An optional finish-up request gives
the player bounded time to conclude what it is doing. A user may additionally
ask to preserve progress, but the player may find that unsupported, unavailable
or unverified. That outcome is reported; the controller neither manufactures a
save nor waits indefinitely for one. Immediate Pause takes precedence over any
attempt to preserve progress.

| Illustrative game behavior | Player-system consequence | Controller obligation |
| --- | --- | --- |
| Manual save is available | The player can discover and use the ordinary controls if appropriate | Supply basic input/observations; make no save claim from delivery alone |
| Saving happens automatically | The player can report any observed confirmation and uncertainty | Require no fabricated manual Save sequence |
| Saving is unavailable during play, restricted to certain places, or absent | The player can explain that progress preservation is unavailable or unverified | Stop automation when required; lack of a save mechanism does not fail generic stop control |
| The game continues while input is stopped | The player may be unable to secure a stable state before control ends | Report that automation stopped, without claiming the game itself paused |

These examples are design cases, not claims of tested support for those games.
Current qualification remains scoped to CDDA on this Mac. A basic control
interface does not establish support for every possible game or save mechanism.

Game progress, player-system knowledge/context, automation authority and application
lifetime are separate state. Retained player records do not save the game or
restore authority. Stopping the player need not close a user-owned application.
The finite test custodian still closes its specifically owned processes under the
frozen cleanup policy; that is a testing obligation, not a universal in-game Quit.
Preserve earlier CDDA Save/reload/normal-exit acceptance and failures as scoped
evidence. Any new diagnostic must state its game-specific persistence/exit checks
separately from generic control acceptance before it is frozen.

Do not add a semantic supervisor, task classifier, second deciding model, game
state parser, new orchestration service or game-specific input gate. The existing
host SDK exposes steering, turn settlement, post-tool and abort hooks. The
[adapter reference](../../tools/player_host/README.md) owns the named library and
its concrete reuse. These hooks support control delivery and explicit settlement;
they are not evidence of supported compaction or recovery. Keep the pinned SDK
unless a concrete missing capability justifies a dependency change.

## Required coordinated change

### Player-facing context

Keep the guide, actual tool declarations, user objective, real observations,
player-authored knowledge, omission notices, source identity/geometry/time and
delivery uncertainty. Remove experimental countdowns and final-actor policy from
the guide, assignment, driver note and per-request host additions. Do not replace
them with guessed game priorities or a prompt that demonstrates a useful program.

At MCP serialization, use one small schema-directed actor result projection.
Give the computer-operation view its own name, selected
`player-computer-result/1`. The underlying `computer-operation/1` remains the
operator's original record. Omit `deadline_monotonic` and the global `remaining`
object from the actor view. Cover immediate returns, original collection,
`player_result` child collections and known nested mechanical envelopes. Preserve
complete native receipt IDs, delivery dispositions, emitted counts, frames,
source hashes, handoff issuance and input uncertainty.

Project known mechanical envelopes by shape, not by deleting every JSON key
called `remaining` or `requests`. Player-authored text, code, interpretation and
state are opaque player data. Unknown mechanical result versions must produce a
bounded unsupported-result response, never raw pass-through. Operator diagnostics
remain original. Actor errors preserve control facts such as unavailable
authority, unknown input or unavailable evidence without supplying a numerical
experiment countdown. Do not redact useful argument-validation feedback.

Program steps receive `program-view/4`, removing the experiment's remaining-resource
object while preserving source/image/interpretation. Keep action bounds and the
player-selected helper's step/time limits. A helper's elapsed execution time is
an outcome, not a global trial countdown. Historical player claims may themselves
mention old quotas; do not rewrite them or claim to erase learned information.
The next test starts without importing a prior quota-bearing report.

### External requests and player reports

Use the host's stdin as a bounded JSONL driver-to-host control channel, separate
from provider messages and the MCP child's stdin. Move the initial prompt to an
explicit `--prompt PATH` input; keep its existing 1 MiB bound and frozen digest.
Bind the invocation to explicit session/actor IDs. Commands are closed
`player-control/1` objects with `schema,id,session,actor_id,type`, where `type` is
`orderly_stop`; each line is at most 4 KiB and IDs use the existing canonical
identity format. The driver owns writing and retained command identity. The host
accepts one latched orderly-stop request and acknowledges receipt in operator telemetry.
It queues a labelled external request through the selected model loop at a safe turn boundary. A
duplicate cannot allocate resources or replay input. EOF, malformed control,
unknown version or wrong actor/session is a host failure, never task completion.
The driver keeps the pipe open until settlement, closes it during owned cleanup
and handles write failure as an unresolved request. No new HTTP or durable control
service is needed. The finite controller triggers this command at the first
prospectively configured ending-reserve threshold in time or charged attempts;
the hard deadline and limits still stop unsafe overrun independently.
The frozen test must also show that mechanical input/request/frame/byte capacity
covers all admitted ordinary execution plus ending, or use conservative reserve
thresholds for those resources as well. Include the largest already-admitted
input/program burst and control-delivery delay. A request reserve alone is
insufficient: one local program can consume many captures and inputs. Resolve
this capacity calculation before admission; do not hide an increase or renew an
exhausted allocation. This is test-resource accounting, not a game-state gate.

Latch orderly stop in the driver for the whole admission, not just one host.
Emergency Pause, uncertain input and hard failure take precedence. At a safe
boundary, suspend not-yet-dispatched calls from the pre-control assistant turn,
mark them explicitly undelivered, and present the request before accepting a new
player action. Never cancel or replay an already-dispatched input to do this.
While ending is pending, refuse a new handoff before sealing. If a handoff was
already in flight and seals successfully, preserve the same external command
identity in the driver and bind/deliver it to the verified successor before any
ordinary action, only if original host/ending resources permit. Otherwise record
incomplete ending and close safely. Sealing or host exit cannot silently erase
the controller's stop request. Bound inference/tool delivery delay in the ending
forecast, including the current provider attempt and bounded local program.

The request says that external control asks the player to finish up and stop.
It contains no requests-remaining count, clock target, prescribed route or game
tactic, and mandates no Save or application Quit. The finite test controller
retains ending reserves and the hard deadline. A model's inability to save cannot
prevent the controller from stopping automation or completing owned cleanup.
Keep emergency Pause distinct: it fences input immediately, including during
inference or a local program, and permits no automation rearm or automated saving afterward.
An orderly request must not cancel an in-flight MCP input merely to deliver text.

Add one host-owned player-system reporting tool, selected `player_finish`, beside
the MCP tool table. Its closed arguments are `disposition`, `report` (at most
8192 characters), `source_ids` (at most 16 existing-format IDs) and nullable
`control_id`. Disposition is one of `task_complete`, `cannot_continue` or
`external_stop_complete`. Source references remain fallible supporting claims.
It has no mechanical input or game-validation
authority. Validate it normally; record its direct invocation and stop subsequent
tool dispatch after acceptance, using the existing host termination hooks. An arbitrary
tool result or remembered text cannot impersonate it. A normal assistant reply
without this signal remains a reply, not a completed task; continuation stays
subject to external authority and original allowances.

Report the claim, host settlement, automation quiescence, any game-specific
persistence evidence, native exit and process absence separately. A claimed win
does not prove a win, and a stopped player does not prove a saved or paused game.
`external_stop_complete` names
the latched external command; a report without that command cannot claim this
disposition. Unknown input remains unknown and is never replayed to finish an
ending. If the player cannot finish within reserves, record its report as
incomplete and stop automation independently. Failure of a separately specified
game-persistence check does not erase successful mechanical stopping, or vice versa.

### Continuity without a new memory architecture

Reuse player-authored records, source retrieval and the existing sealed handoff.
Keep actual old-host/MCP quiescence and canonical context verification before any
successor. The user objective survives a handoff; test allocation and Pause do not
renew. The finite controller may still bound hosts in a test. Do not present that
test cap as a gameplay finish line or a permanent product quota.

The player can use a fresh context through the existing handoff path. A missing
or failed handoff remains a failure; no silent truncation, fabricated summary,
unproven restore or automatic restart. Use the pinned SDK context-estimation
helper together with actual reported usage to request context turnover
conservatively, reserving room for tools and external control. This helper uses
heuristic text/image estimates; it is not a proof that every result fits a
provider window. The finite diagnostic must freeze and exercise its context
envelope before admission, including missing usage and an oversized result. Do
not infer continuous reliability from a successful short case. General unattended uptime, arbitrary
recovery and automatic semantic compaction remain unqualified after this slice.

## Migration, acceptance and scope control

The changed host invocation/control/settlement requires `player-host/3` and
telemetry version 3. Migrate package/driver/receipts together as `campaign-run/4`,
`player-driver/3` and `campaign-receipt/3`. Actor-view shapes have their own
versions; migrate host handoff inspection and all actor consumers. Program view
changes require rejecting executable old-view libraries before effects. Use
`player-program/2` with required `view_schema: "program-view/4"`, and a fresh
`player-memory/2` store, preserving old stores and
source-linked evidence as inert history. This design selects no automatic
library conversion. Preserve the original Alex game save through the upstream
game's own load/save behavior; no save editing or old-store reader.

Unchanged mechanical contracts include native wire/request/receipt, sources,
canonical computer operations and their original accounting. Do not rename or
rewrite those merely because the actor view differs. Native receipt reasons and
images remain evidence, not semantic certificates. At implementation, enumerate
every affected caller, fixture and persisted shape under
[S-MIGRATION](../standards/migration.md); remove the old actor path in the same
deployment. Never mix schemas behind compatibility flags.

Core paths are the player guide; `harness/player_mcp.py`, `player_client.py`,
`player_tools.py`, `application.py`, player images/programs/contracts/memory;
`tools/player_host/`, campaign package/player/run; relevant analysis/observer
readers and their tests. Update overview, architecture, component/contracts and
operations with implemented behavior, using this record only as agreed rationale.
The lead owns the shared runtime and integration. Workers, if useful, receive
disjoint worktrees/ownership only after interface decisions are fixed.

Required checks cover every context delivery route, typed nested collections,
opaque authored data, unsupported versions, retained original accounting,
source/uncertainty preservation, retry charging, control identity/duplicates,
direct completion origin, pending multi-tool suppression, cancellation during
inference/programs, context turnover, exact group closure and independent stopping
without a model reply or save/quit mechanism. Exercise the illustrative manual,
automatic, unavailable-save and continuing-game cases without teaching a game
handler to the controller. Focused Python/Node
fixtures precede development play; independent code/architecture review and full
protected regression precede broad-source merge. Source fixtures cannot prove
survival, safe saving, useful plans or model benefit.

The initial estimate was 8–16 focused engineering hours including implementation,
review, documentation, checks and a diagnostic proposal, with low confidence
because control delivery and stored program migration cross existing boundaries.
That estimate is rationale, not current delivery status. Existing authority,
protocol-deviation, spending and design escalation rules remain in force.

## Next evidence decision

The separately approved [5 November diagnostic](../acceptance/2026-11-05-player-test-diagnostic.md)
carried out this continuation after source delivery. Its first admission was
operator-truncated; the replacement verified sampled context separation and
direct stopping but ended in Alex's death, without replenishment or a local
program. External orderly-stop and other unexercised paths remain unqualified.
The following prospective rationale is retained; it grants no further admission.

After offline checks, freeze a focused prospective continuation on the preserved
Alex save, on the exact candidate and selected current route. Give only an ongoing
survival objective and ordinary visible observations. The retained save starts
under depleted-water pressure without engineering new threats or teaching a
solution. Do not import the old assignment, ending target or actor report. It is
one continuation, not a fresh independent start, causal comparison or full cohort.

The test controller should observe useful replenishment, maintained needs, actual
planning revisions and organically chosen supported program execution, retaining
all failures/no-ops. Keep observation milestones external and request ending only
through the new control path. Specify any CDDA Save/reload/normal-exit evidence
as this diagnostic's own requirement, without making it a universal player stop
condition or altering earlier protocols. Review original ready/dispatch/child/effect timing
on compatible clocks; do not call receipt delivery a useful effect. The original
20-decision, 2 s p95, 5 s stall and 500 ms local-effect criteria remain unchanged.

Choose finite wall/attempt/input/image/byte allowances, ending reserves and a
worst-case financial reservation from the implemented route and recent actual
counts before proposing this run. The last continuation cost $2.324057058 for
102 usage-known requests and about 15 minutes, while covering 48h26m32s in game.
Those observations are planning inputs, not a promised price or future yield.
This design grants no uncalculated paid allowance. If a credible
informative window cannot fit the standing cumulative ceiling or ending resources,
report that conflict before admission rather than extending a running test.

A useful result supports reassessing cohort counts and feasibility; it does not
admit the full cohort automatically. No organic program leaves the local-effect
gap open. Failed replenishment or another interpretation failure motivates a
specific evidence-led diagnosis; it does not authorize another general architecture.
Death, forced cleanup, lost accounting, quota exposure or incomplete control
leaves the relevant lane failed or unknown. Keep #145's seven-day readiness gate.
