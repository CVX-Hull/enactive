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
Both original and successor start fresh; at most two hosts fit `campaign-run/11`.
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

Read host JSONL using the [telemetry contract](../contracts/player-host-telemetry.md#telemetry).
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

## Install and test the adapter

From `tools/player_host/`, install and test with project-local dependencies:

```sh
npm --userconfig /dev/null --cache ../../.cache/npm ci --ignore-scripts --no-audit --no-fund
ENACTIVE_TEST_PYTHON=/absolute/project/.venv/bin/python npm test
```

Node >=22.19.0 and the repository's Python environment with MCP 2.x are required.
The tests invoke actual Pi provider serialization against synthetic SSE and local
HTTP fixtures, and official Python MCP servers (the shared double is
`tests/fixtures/player_host_mcp.py`), including current production
schema discovery. The adapter-agnostic contract suite
(`tests/test_player_host_contract.py`) drives this runner only through its argv,
files, environment and exit status; `tests/test_player_host_adapter.py` runs these
Node tests from pytest. They make no inference calls and start no game. Reported sample
timings include fixture process startup and cleanup; they do not measure model
latency, gameplay competence or a hardware-independent performance threshold.
The in-flight tool-deadline case uses a controlled Node timeout clock only after
observing actual fixture tool start; startup/signal cases and outer watchdogs
retain real time, and all cases retain actual child-closure assertions.

`node --test` runs each `test/*.test.mjs` file in its own process, several at a
time, and the cases inside one file one after another. Almost all the time is
Python MCP child startup, so the `runHost` cases are divided by responsibility
(route configuration, context projection, tool dispatch, provider requests, MCP
connection, the three retry files, control and finish, handoff) and share the
route, provider responses and `scenario` runner in `test/host-scenario.mjs`. Add
a case to the file that owns its responsibility, or to a new descriptively named
file, rather than growing one file until it sets the suite's wall time. Each
host run starts its own child in a fresh temporary directory, so the files share
no state.

## Validate and run from the project root

The runner requires a leading mode word. `validate` checks the route and MCP
table offline and exits zero only if both are accepted, writing nothing to stdout:

```sh
node tools/player_host/run.mjs validate \
  --config FROZEN/route.json --mcp-config FROZEN/mcp-template.json \
  --model MODEL --effort EFFORT
```

`run` hosts one actor. The driver invokes:

```sh
node tools/player_host/run.mjs run \
  --config FROZEN/route.json \
  --mcp-config FROZEN/mcp.json \
  --context FROZEN/context.txt --prompt FROZEN/prompt.txt \
  --session SESSION_32HEX --actor-id ACTOR_32HEX \
  --pending-control-id none \
  --delivered-knowledge FROZEN/delivered-knowledge.json \
  --finish-reserve-usd USD \
  --model MODEL --effort EFFORT --timeout-seconds SECONDS \
  -o DRIVER_RESERVED_FINAL_FILE
```

[Operations index](../runbook.md).
