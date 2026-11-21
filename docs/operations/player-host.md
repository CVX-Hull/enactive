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

The selected finite configuration is OpenRouter / pinned OpenAI provider /
`openai/gpt-6.1-terra`, medium effort, under the owner's decision of 16 November
2026 in the [decision log](../decisions/owner-decisions.md). Freeze the verified
full endpoint tag and supported parameters
in `route.json`; use no fallback. The current campaign accepts the explicit default
service tier. Configuration metadata/prices are not invoice, quality or latency
attestation. New live calls remain bounded by the package's dollar limit and operational capacities.

The package freezes `route.json` (`player-host/8`), `delivered-knowledge.json`, `mcp-template.json`,
`context.txt`, `prompt.txt` and `target.json`. The route declares explicit model
text/image capabilities, context/output capacities, effort mapping, costs, request
timeout, the dollar limit, the planning bound for an in-flight
request, credential environment name, image peak, eviction block and
required `context_reserve_tokens` (at least `maxTokens`, below `contextWindow`).
Keep the peak within the provider's image limit (30 on DeepInfra). Block 1 evicts
one image at a time (rolling); a larger block keeps the prompt prefix cacheable
between evictions. Prefer a block of about half the peak, such as 39/20, so evictions are
rare. Follow the [campaign route-selection procedure](campaign-run.md#construct-a-package).
Pi sends a per-session `x-session-id` affinity value on the OpenRouter route. The host's
[request-stability rules](../contracts/player-host.md#request-stability-and-tail-notices)
govern the rest.
The [host reference](../../tools/player_host/README.md) owns exact closed fields.
Unsupported route and player-view configurations are rejected as executable inputs.

The driver creates each actor's `player-adapter/2`, explicit MCP table, fixed
context, ongoing-objective/knowledge prompt and `player-host-inputs/3` hashes.
Experiment quotas, host counts and other final-actor policy remain outside player
context, with one deliberate exception below. Pi loads no coding-agent
shell/file tools, personal settings, resource discovery or resumed history.
Both original and successor start fresh; at most two hosts fit `campaign-run/10`.
Each actor's route carries the requests the run has left. The driver starts an
actor only while requests and dollars remain. The
[request-stability contract](../contracts/player-host.md#request-stability-and-tail-notices)
defines which request fields stay fixed across actors and how images are omitted.
The final actor's `player_handoff` call is refused by the application with no
state change ("no successor is available"), and the driver marks that actor before it
starts. Earlier actors can request a handoff by position alone, and a successor can
still be refused when original resources run out. No model, transport, host or
coding-agent fallback is supported ([adapter selection](../contracts/player-host.md#adapter-selection),
[isolation](../contracts/player-host.md#isolation)).

Inject only the selected credential environment variable into the provider child. Keep
the key out of files, argv, configured headers and URLs, and keep it out of the
MCP and native children. Supply it explicitly without credential or profile discovery. The
host rejects ambient SDK logging and header configuration. Leave global profiles
untouched during dedicated child cleanup.

Keep host stdin open through settlement and retain command intent before writing
as specified in the [external control contract](../contracts/player-host.md#external-control).

The adapter uses its maintained steering and turn hooks for finish-up,
pending-call suppression and direct finish settlement. The
[settlement contract](../contracts/player-host.md#settlement-and-handoff) defines
the `player_finish` signal and when the host accepts it. Forecast ending capacity
using the [campaign reserve procedure](campaign-run.md#ending-reserve-and-external-stop).

The adapter uses `estimateContextTokens` for the maintained estimate in the
[context-pressure rules](../contracts/player-host.md#route-envelope).

The host serializes tools. A successor needs no game save. The
[custody contract](../contracts/computer-control.md#computer-operations-and-custody)
defines handoff settlement and verified succession within the original limits.

Read host JSONL using the [telemetry contract](../contracts/player-host.md#telemetry).
Forecast attempts using the [route's retry rules](../contracts/player-host.md#route-envelope).
Use the [spend contract](../contracts/player-host.md#spend) to read the subtotal
and interpret trace completeness. An incomplete trace retains the observed counts.
The host leaves tool rereads to the player and stops before inference if the
protected current image group is oversized.

A direct `player_finish` yields `player_task_complete_unassessed`,
`player_cannot_continue_unassessed` or `player_external_stop_complete_unassessed`.
Use the custodian's receipt to check normal native exit, owned absence and
authority revocation. Assess gameplay outcomes against their own evidence. The
player owns save and success claims. The
[production report](../acceptance/2026-10-29-computer-control.md) records bounded
useful play, program/knowledge/succession and Save/reload/normal ending evidence.
Whole-player cadence, causal learning and independent survival remain unqualified.

[Operations index](../runbook.md).
