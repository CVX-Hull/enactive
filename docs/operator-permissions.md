---
owner: lead
status: active
review_trigger: Codex permission support, CLI entry point, executor ownership or campaign admission changes
---

# Gameplay permissions and player ownership

Routine admitted play must proceed without user keys, human approvals or automatic
approval/guardrail-review round trips, including observation, memory, lifecycle,
handoff and supporting request/result plumbing. The user's standing gameplay
delegation does not need to be requested again for each action or successor.
User Pause/takeover remains available. There are three separate boundaries:
Codex controls process/network permission; the harness validates current input
authority; the player judges the visible game outcome. An allow rule changes
only the first boundary. It cannot grant a lease, make stale input current,
replay an unknown request or override CDDA.

## Command permissions

On this Mac's managed workspace-write session, a real passive preflight after
normal game shutdown found both `harness serve --port8766` and `harness status`
failed with Operation not permitted without elevation. The approved controller
and status call worked. The preflight sent no game input and was stopped normally.
The one-off capture helper had requested elevation on every invocation because
its child CLI uses loopback HTTP. Project-file reads/writes do not inherently
need that elevation. Git metadata writes, launch/process checks and remote GitHub
or downloads have separate permissions; do not stamp every shell call elevated.

[Project-local rules](../.codex/rules/gameplay.rules) allow only the existing
`.venv/bin/python -m harness` command family for ordinary observation, control,
recovery and the current typed mission-request entry point. Retired gameplay-*
commands are removed from both parser and allowance. Setup/server launch, GitHub publication,
arbitrary Python, shell scripts and study capture wrappers are not matched. The
exact005 recorder rule was retired at its stopped closeout; it is historical, not
a template for wildcard studies.
Preparing these rules changed no global defaults, user rules, OS permissions or
broad network access. The later exact-project trust correction below adds only
this checkout's trust entry to Codex's user configuration.
Use the ordinary command directly when applicable; do not hide disallowed work
behind an allowed command or switch transports to evade review.

Rules permit matching commands **outside** the sandbox. They are not filesystem
confinement, source-hash pinning or a per-agent sandbox. The CLI and imports come
from the working directory: use only the reviewed trusted checkout, freeze source
during admitted play and re-review on entry-point or dependency changes. The rule
does not mechanically check cwd, source hashes, budgets or command intent. Managed
restrictions and more restrictive matching rules still win. Remaining reviews,
including invocations outside the exact recorder prefix, must be honored.

Codex0.162.1's mature `codex execpolicy check` parsed the rule and its inline
positive/negative cases. A key command matched allow; Python `-c` and server launch
had no match. **Policy syntax/matching is verified; active-chat loading and absence
of recurring review remain separate post-reload checks.** The later trust correction
verified an enabled project layer in a fresh bundled Codex process. Official
documentation requires a trusted project configuration and startup/reload. Do not
repeatedly restart an unchanged verified setup or claim every review disappeared.

Maintenance: lead rechecks examples with `codex execpolicy check --rules
.codex/rules/gameplay.rules -- COMMAND` when command syntax, trust or permission
support changes. Review the diff, effective policy and an allowed/blocked harmless
preflight before relying on activation. Retire obsolete allowances with their
commands. Reuse these inline checks rather than building a policy parser.

Official rules source rechecked2026-10-20; other linked background checked2026-10-18: [rules](https://learn.chatgpt.com/docs/agent-configuration/rules),
[sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security),
[sub-agent permissions](https://learn.chatgpt.com/docs/agent-configuration/subagents).


### Verified loading and retired recorder allowance

The [original narrow recorder change](changes/032-recorder-permission-reload.md)
and [exact-project trust correction](changes/033-gameplay-permission-preflight.md)
remain historical. After the user's restart, startup reported saved gameplay
prefixes. Two actual-player recorder status calls102/103 passed with no review
request/error observed, followed by real Observe104/Resume105 and ordinary play.
The [actual result](acceptance/2026-10-18-activity-distraction-stop.md) establishes
that scoped setup, not every future invocation or managed-policy behavior. The
[later native proof](acceptance/2026-10-18-activity-distraction.md) used two harmless
stable-CLI calls followed by actual ordinary inputs without recurring review, a
new recorder allowance or another Codex restart.

005 then ended on an unsupported native activity question, independently of
permission. Its exact-study rule is removed from source; subsequent policy loading
applies that removal. Cached allowances do not authorize closed005 admission.
Keep the stable reviewed harness entry point for future play; review any necessary
outer wrapper once during setup rather than introducing per-action review or
restarting a verified unchanged setup. Invoke a literal command directly; shell
chains/redirections can change the policy target. Honor actual restrictions and
reviews; do not hide unrelated work behind allowed entry points. All original
costs/clocks/unknowns remain. Future gameplay needs its own prospective authority
and complete-outcome feasibility assessment, not a policy-file edit.

## Dedicated gameplay context

### Preflight for every campaign

The lead owns permission readiness before ordinary input. A recorder that requires
admitted metadata must receive only a bounded passive preflight assignment first;
that setup assignment authorizes no keys, actions or Resume. Repeat this check when
the checkout, command entry point, recorder, player, Codex version or permission
configuration changes; reuse the verified setup otherwise.

1. Prefer the stable reviewed harness CLI entry points. If a campaign recorder
   wraps them, verify the exact outer recorder prefix too. A child CLI allowance
   does not automatically allow its wrapper. Review the executable and scope once
   during setup; do not request approval separately for each ordinary game action.
2. Verify that this exact checkout's project layer is enabled. Codex's documented
   `config/read` with `cwd` and `includeLayers` can show an enabled project layer;
   an absent exact trust entry or an ancestor's trust is not activation evidence.
   Codex stores project trust in user-level `config.toml`, under
   `projects.<absolute-checkout-path>.trust_level`. An authorized change adds only
   that project entry and preserves unrelated settings. Keep gameplay allowances
   in this checkout's `.codex/rules/`, not a broad user-level Python/shell rule.
3. Check positive and negative command examples with the installed Codex policy
   checker. Then reload Codex when required and test two consecutive harmless live
   status/observation calls and a representative semantic/result/image/memory/
   lifecycle workflow from the actual designated player through its exact entry
   point. Record both human and automatic review; a successful approved call or
   neither no visible prompt nor an exit code proves the absence of review.
   Name the required tool execution mode in the actor brief. Native008's passive
   status calls worked in the default sandbox while Start's connection did not;
   its existing allowed CLI worked with explicit `require_escalated`. Use that
   authorized mode consistently for the admitted loopback command, retain actual
   failures, and distinguish sandbox access from an approval rejection. After an
   ambiguous admission response, inspect the existing mission/request ID before
   proceeding; never replay a possibly delivered gameplay input.
   Retain loading, matching, access and absence of recurring review as separate
   evidence. A fresh diagnostic process does not prove the active chat reloaded.
4. If every action still reaches approval review, stop permission admission and
   diagnose trust/loading, outer shell syntax and managed restrictions. Do not
   spend the campaign repeating reviews or disable the sandbox globally. Honor
   any actual denial. If supported project rules cannot remove recurring review,
   report that product/policy limit explicitly instead of claiming readiness.

Existing admitted campaigns retain their original budgets and stop rules during
a user-requested configuration interruption. This prospective setup standard
does not retroactively invalidate their recorded gameplay or renew allowances.
Native guards, user Pause, recovery eligibility and campaign limits still apply.
Setup, source changes, publication and unrelated commands have separate scope.

### Current review-free execution gap

Independent004's fresh successor initially reached automatic approval review on a
literal passive status call. Review rejected it as unrelated work; the same action
subsequently passed after the original human authorization was supplied. The
denial remains evidence. The project rule still matches allow and this checkout
is trusted, but active review-free execution is not established. Current session
settings remain workspace-write/on-request/auto_review. No global defaults or
permissions were changed. [#166](https://github.com/CVX-Hull/enactive/issues/166)
owns this setup gap; [#164](https://github.com/CVX-Hull/enactive/issues/164) owns
structured request/result/image automation using the existing ingress. Repeating
authorization arguments to a reviewer is not the accepted gameplay loop.

The [official automatic-review guidance](https://learn.chatgpt.com/docs/sandboxing/auto-review)
explains that routine actions inside effective policy proceed without review;
changing approval policy alone grants no missing access. A supported integration
must be configured and verified before it can be called review-free. Do not
silently route a denied action through another tool, override managed policy or
use a broad Python/shell allowance. Keep local deterministic protocol validation,
finite accounting and user Pause/control; these require no reviewer model.

The [structured player adapter](changes/051-structured-player-tools.md) now has
source/fixture support for typed submission, result collection and actual retained
images. Its [project setup recipe](setup.md#configure-the-structured-player-tools)
configures only the named MCP tools with per-server `approve` behavior. The official
SDK owns stdio framing; the same mission ingress still owns execution. Active
desktop loading, actual designated-player calls and absence of human/automatic
review remain unverified. This is an explicitly configured integration under the
standing authorization, after the old denial was resolved on its original path;
it is not an alternate route for a pending denied action. Source checks or a CLI
configuration read cannot close #166.

On2026-10-20 the generated project table was installed and the supported CLI
recognized its fifteen named tools. A separate Codex0.162.1 `--strict-config`
diagnostic returned the enabled project layer, exact stdio command/cwd, explicit
tool list and `default_tools_approval_mode:"approve"`. The inherited global
on-request/auto_review values stayed unchanged. Diagnostic SQLite/log paths were
project-local; no model thread was started and the owned process exited0. The
first diagnostic rejected an incorrect state-path key before startup; the corrected
restricted run failed EPERM, then the authorized corrected run passed. These are
configuration evidence, not active-host/no-review evidence. The tools subsequently
appeared through the host's supported refresh without a user restart. The parent
and a fresh general-purpose agent both saw all fifteen tools; one parent and two
agent snapshot calls reached the real MCP server and returned the expected
no-controller error. This proves catalogue loading/dispatch, not live loopback or
zero-review gameplay. No review event was visible; that alone is not proof of its
absence. The daemon socket was absent and Computer Use refused the Codex app;
neither was worked around. Actual-player live-service verification remains required.

The [trust correction](changes/033-gameplay-permission-preflight.md) records the
observed disabled project layer and the exact-project fix. Fresh bundled loading
was followed by the [actual-player reload/resumption](acceptance/2026-10-18-activity-distraction-stop.md)
checks and the later stable-CLI native proof. Those scoped results now establish
live operation without recurring review; future changed setups need new preflight.

A long-lived bounded player sub-agent is useful for keeping gameplay facts and
observations separate from engineering discussion. It does not require a weaker
model tier or another paid API. It inherits parent permissions; role instructions
do not create security isolation, and delegation alone cannot remove approvals.

The current designated player uses typed mission requests for semantic skills,
memory and registered lifecycle. The passive waypoint planner has no live ingress.
The lead retains admission, source/game/service custody, escalation and acceptance;
it supplies no ordinary gameplay rescue during the deciding mission. Historical
operator reports below describe the first campaign's procedure, not another current
execution path. A new command allowance needs syntax/matching and actual-player
loading checks; no activation claim follows from a policy-file edit.

### Constructing player requests

For ordinary skill/lifecycle requests, use the
[pure canonical producer](protocol.md#skill-request-binding-errors), then the existing
canonical JSON serializer and literal `mission-request --request PATH` entry point.
Choose semantic intent and context explicitly; do not fill opaque headers manually:

```python
from harness.gameplay.mission_contracts import canonical
from harness.gameplay.mission_requests import compose_request

request = compose_request(
    selected_mission_status,
    request_id=new_request_id,
    intent=selected_semantic_intent,
    limits=finite_child_limits,
    scope="lifecycle",
    source=selected_archive_entry,
)
request_path.write_text(canonical(request), encoding="utf-8")
```

These variables are explicit player selections, not an automatic status lookup.
The archive entry contains the matching retained `reference` and `observation`.
For provisional character inspection, intent selects `skill_kind="inspect"` and
`goal={"purpose": "character_identity"}` with null Work; lifecycle scope keeps the
creation/load root. A missing phase/checkpoint rejects locally. Lifecycle confirmation
and editor intent also keep that root. Never substitute a new root to bypass it.
Use explicit `supporting_source_ids` for the additional diagnostic source in
two-observation transitions. Initial activity interruption uses the prompt summary;
the subsequent answer/Resume use the activity summary and its exact checkpoint,
which can differ from `current_source`. Memory/handoff and specialized recovery
retain their existing records. Composition is not permission to dispatch.

Keep complete raw CLI/tool receipts; use existing JSON extraction to present bounded
operation/status fields. Parse only complete retained responses, never truncated tool
text. Do not repeat an ambiguous input to obtain shorter output. Preparing JSON adds
no new allowed command or gameplay authority; literal CLI access and actual actor
preflight remain required. Routine semantic skills keep per-key checks local, with
no model, memory query or approval round trip for each arrow. Native ACK timing does
not measure model/tool delay, whole skills or successful frame display.

The clean-context brief identifies command/file scope, actor/phase, cumulative
limits and reserve. Pause, completed tools, explicit quiescence and empty live
slots precede inspection or registered handoff. Original unknowns and accounting
never reset. Role names/instructions are workflow controls, not a sandbox. Follow
the [current actor contract](protocol.md#designated-campaign-operator).

[#97](https://github.com/CVX-Hull/enactive/issues/97)'s
[two-phase result](acceptance/2026-10-18-campaign-operator.md) records actual
delegated consumption/conservation and paused lead takeover, following a retained
default-sandbox invocation failure. Its approved actor preflight and explicit
tool mode worked in this session; allow-rule activation remained unverified at that historical checkpoint; the
[later actual verification](acceptance/2026-10-18-activity-distraction-stop.md) supersedes that limitation.
This is one qualified operating result, not general survival or a reliability claim.
Missing/unquiesced player, denied approval or failed readable access stops; user
rescue is not the fallback. Do not expand an active frozen campaign mid-run.

Test access from the **designated actor**, before gameplay admission. A successful
lead call does not prove that the player's next tool invocation will request the
same permission mode. When this session requires elevation, the brief must name
`sandbox_permissions: "require_escalated"` and a narrow justification explicitly;
omitting the field uses the default sandbox. Honor an approval rejection; do not
route it through another actor. A sandbox connection failure before any elevated
request is a different event and must not be reported as automatic-review denial.
Retain the actual passive preflight and terminal tool result. Project allow-rule
matching still does not prove live activation.

The [first deciding campaign](acceptance/2026-10-18-seven-day-stop.md) later passed
actor access and sent ordinary inputs, then received an actual approval rejection
for movement without fresh verified observation after a stopped walk. The player
honored it; the admission ended and normal cleanup preserved the partial. This
was a decision/freshness requirement, not missing loopback access. #108 tracks
the bounded observation/caller correction; do not broaden rules, change actors
or switch transports to bypass that rejection. A later assessment needs an explicit
prospective decision; the stopped admission supplies no remaining input authority.
The [subsequent bounded correction/probe](acceptance/2026-10-18-walk-reassessment.md)
used existing explicitly approved CLI calls without broader rules or another actor.
It verified stop evidence and the fresh Observe/Resume sequence; the first load
probe remained unexercised. Narrow rule activation was still unverified at that historical checkpoint;
[later actual-player verification](acceptance/2026-10-18-activity-distraction-stop.md) established the scoped setup, and the
original approval denial was not retried. Further survival needs its own admission.

The [later functional continuation](acceptance/2026-10-18-seven-day-continuation-stop.md)
passed actual actor access and stopped on unsupported LIST_ITEMS. Broader permissions
could not fix native UI coverage. Native CUA access also failed; no user unlock/keys
were requested. A separately recorded cleanup-only upstream Quit exception closed
the process without a new Save; normal Save/Quit acceptance failed. Its scope has
expired and grants no general fallback or authority for further survival.
