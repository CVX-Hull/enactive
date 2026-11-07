---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Bounded player host activation

A deciding player runs only in the player host adapter frozen by its package, under
the [player host contract](../contracts/player-host.md). The current adapter is the
[Pi host](../../tools/player_host/README.md); install its locked project-local
dependencies through [setup](../setup.md#install-the-generic-gameplay-host). Activate a
host only through the [finite campaign custodian](campaign-run.md), not an old
mission-driver CLI. Freeze the Pi adapter as
`"host": {"argv": ["ABSOLUTE_EXISTING_NODE_EXECUTABLE", "ABSOLUTE_PROJECT_ROOT/tools/player_host/run.mjs"]}`.

The selected finite configuration is OpenRouter / explicitly pinned provider / DeepSeek
Flash1017 medium. Freeze its verified full endpoint tag and supported parameters
in `route.json`; use no fallback. The current campaign accepts the explicit default
service tier. Configuration metadata/prices are not invoice, quality or latency
attestation. New live calls remain bounded by the prospective allocation.

The package freezes `route.json` (`player-host/3`), `mcp-template.json`,
`context.txt`, `prompt.txt` and `target.json`. The route declares explicit model
text/image capabilities, context/output capacities, effort mapping, costs, request
timeout, request cap, credential environment name, image peak, eviction block and
required `context_reserve_tokens` (at least `maxTokens`, below `contextWindow`).
Keep the peak within the provider's image limit (30 on DeepInfra). Block 1 evicts
one image at a time (rolling); a larger block, such as 39/10, keeps the prompt prefix
cacheable between evictions.
The [host reference](../../tools/player_host/README.md) owns exact closed fields.
Unsupported route and player-view configurations are rejected as executable inputs.

The driver creates each actor's `player-adapter/1`, explicit MCP table, fixed
context, ongoing-objective/knowledge prompt and `player-host-inputs/2` hashes.
Experiment quotas, host counts and other final-actor policy remain outside player
context, with one deliberate exception below. Pi loads no coding-agent
shell/file tools, personal settings, resource discovery or resumed history.
Both original and successor start fresh; at most two hosts fit `campaign-run/5`.
The final actor's tool table omits `player_handoff`, so it is never offered a
handoff that would only end the admission; its capacity warning asks for
`player_finish` instead. Earlier actors are offered the tool by position alone, so
a successor can still be refused when original resources run out.
No model, transport, host or coding-agent fallback is supported.

Inject only the selected credential environment variable into the provider child.
No key in files/argv/headers/URLs; no credential/profile discovery. MCP/native
children receive no provider secret. The host rejects ambient SDK logging/header
configuration; dedicated child cleanup must not alter global profiles.

The driver passes the prompt via `--prompt PATH`, explicit `--session` and
`--actor-id`, and required `--pending-control-id none|32hex`. Host stdin carries
closed `player-control/1` JSONL, separate from MCP stdin. Keep it open until
settlement; unexpected EOF is fatal. Identical same-ID commands are idempotent;
conflicts, malformed lines, wrong identity/version and lines over4096 UTF8 bytes
before newline fail. Retain command intent before publication. A successor with
inherited stop waits for its matching command before MCP connection or fetch.

The host uses Pi's maintained steering/turn hooks for optional finish-up, pending
call suppression and direct finish settlement. It adds `player_finish` beside
the MCP table, requiring `disposition,report,source_ids,control_id`. External
completion names the received stop command; task completion/inability use null.
Only direct validated execution settles; narration or embedded JSON does not.
No subsequent tool/provider request dispatches after acceptance. Pause and hard
cleanup act independently of the model or saving. The [campaign reserve procedure](campaign-run.md#ending-reserve-and-external-stop)
requires a lead forecast; validators check bounds, not ending adequacy.

Pi's `estimateContextTokens`, reported usage and a text/image heuristic floor
request existing sealed handoff when context is pressured. Estimates are not a
provider token guarantee. No compaction, restore or fallback is added.

The host serializes tools. A direct sealed `player-computer-result/1` handoff issuance,
or exact collection of its own pending original handoff, settles that actor.
The driver verifies canonical context/digest and actual old host/MCP process-group
quiescence before minting a successor under original time/attempt/input resources.
No game save/menu/identity condition applies. User Pause, uncertain input, failed
host closure or unexpected cancellation stop succession. A sealed actor's reads
never restore authority.

Host JSONL retains bounded visible narration and mechanical request/result
references, not private reasoning or raw request/image histories. Missing usage
stays unknown. Attempts include failures and permitted provider-only retries: one
shared retry per logical request for 429, 502/503/504, a pre-header fetch rejection
or OpenRouter's transient in-flight 402, as the host reference defines. Allocate
attempts with that retry in mind; unknown accounting charges the allocated bound. Context projection marks older
omitted pixels and preserves text/IDs; no automatic tool reread or replay occurs.
An oversized protected current image group stops before inference.

A terminal player report yields `player_task_complete_unassessed`,
`player_cannot_continue_unassessed` or `player_external_stop_complete_unassessed`.
These are not game acceptance. The report must come from direct `player_finish`
(`task_complete`, `cannot_continue`
or `external_stop_complete`); ordinary assistant text alone cannot complete the
task. The custodian separately samples normal native exit before forced cleanup and reports
owned absence/authority revocation. The player owns save/success claims. The
[production report](../acceptance/2026-10-29-computer-control.md) records bounded
useful play, program/knowledge/succession and Save/reload/normal ending evidence.
Whole-player cadence, causal learning and independent survival remain unqualified.

[Operations index](../runbook.md).
