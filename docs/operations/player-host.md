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

The package freezes `route.json` (`player-host/3`, actor role), `mcp-template.json`,
`context.txt`, `prompt.txt` and `target.json`. The route declares explicit model
text/image capabilities, context/output capacities, effort mapping, costs, request
timeout, request cap, credential environment name, image peak and eviction block.
Keep the peak within the provider's image limit (30 on DeepInfra). Block 1 keeps the
earlier rolling policy; a larger block, such as 39/10, keeps the prompt prefix
cacheable between evictions.
The [host reference](../../tools/player_host/README.md) owns exact closed fields.
Old route/mission/player-view configurations reject as executable inputs.

The driver creates each actor's `player-adapter/1`, explicit MCP table, fixed
context, resource/knowledge prompt and file hashes. Pi loads no coding-agent
shell/file tools, personal settings, resource discovery or resumed history.
Both original and successor start fresh; at most two actor hosts fit `campaign-run/4`, each with its own level passes when a level is frozen.
No model, transport, host or coding-agent fallback is supported.

Inject only the selected credential environment variable into the provider child.
No key in files/argv/headers/URLs; no credential/profile discovery. MCP/native
children receive no provider secret. The host rejects ambient SDK logging/header
configuration; dedicated child cleanup must not alter global profiles.

The host serializes tools. A direct sealed `computer-operation/1` handoff issuance,
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

A terminal host report is `host_completed_unassessed`, not game acceptance. The
custodian separately samples normal native exit before forced cleanup and reports
owned absence/authority revocation. The player owns save/success claims. The
[production report](../acceptance/2026-10-29-computer-control.md) records bounded
useful play, program/knowledge/succession and Save/reload/normal ending evidence.
Whole-player cadence, causal learning and independent survival remain unqualified.

[Operations index](../runbook.md).
