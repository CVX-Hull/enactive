---
owner: lead
review_trigger: Driver/host invocation, route envelope, telemetry, settlement, isolation or adapter changes
status: active
---

# Player host contract

`player-host/1` is the one current boundary between the [campaign driver](../../tools/campaign_player.py)
and the program that hosts a deciding player. The host turns frozen context, a
frozen provider route and the actor's MCP table into model calls and sequential
player tool calls. The driver owns actor minting, original limits, process-group
closure, handoff verification and succession. Any adapter that satisfies this page
and passes the conformance suite (`tests/test_player_host_contract.py`) is
substitutable; no driver, packager or gameplay page depends on a particular
adapter. The [current adapter reference](../../tools/player_host/README.md) owns
its provider serializers, closed route `model` fields and limits.

## Adapter selection

A `campaign-run/3` package freezes `host`: `{"argv": [...]}` with 1–8 strings.
`argv[0]` is an absolute existing regular file (an adapter executable or its
interpreter); every later entry is a canonical project-local regular file covered
by the clean source commit. The driver and package validator append only the mode
and the arguments below. There is no adapter registry, default adapter, fallback
or resumed host. `campaign-run/2` packages and their `node` field are inert history.

## Modes

`ARGV validate --config ROUTE --mcp-config MCP --model ID --effort EFFORT` exits
zero exactly when the adapter accepts the route, MCP table, model and effort. It
reads only those files, needs no credential or network and finishes within 10
seconds. The package validator runs it with only `PATH` and `LANG`.

`ARGV run --config ROUTE --mcp-config MCP --context CONTEXT --model ID --effort EFFORT --timeout-seconds S -o FINAL`
hosts one actor. Each flag occurs exactly once; unknown, repeated or missing
arguments settle unsuccessfully. Input files and the prompt on stdin are each at
most 1 MiB. `S` is the actor's original host allowance in seconds; the host
enforces it and also stops on `SIGINT`/`SIGTERM`. `FINAL` is reserved by the
driver; the host writes the terminal player report there only after successful
`completed` settlement and leaves it unchanged otherwise.

The driver starts the host in a new session with `cwd` at the project root, stdout
to `host.jsonl`, stderr to `host-stderr.log` and an environment containing only
`PATH`, `LANG` and the route's `api_key_env` variable. Exit status is zero exactly
when the final `settled` event has `ok: true`.

## Route envelope

The frozen route is one closed JSON object with `schema: "player-host/1"`,
`model`, `api_key_env`, `max_requests`, `max_context_images`,
`request_timeout_seconds` and `service_tier`. The driver and package validator
read only: `model.id`, `model.name`, `model.cost.{input,output,cacheRead,cacheWrite}`
(dollars per million tokens), `model.contextWindow`, `model.maxTokens`,
`api_key_env`, `max_requests` and `service_tier`. The adapter owns every other
closed `model` field and rejects routes it cannot serve without fallback. The
driver lowers `max_requests` to the actor's remaining original allowance before
launch. Routes carrying any other schema, including earlier adapter-named route
schemas, are rejected; their packages are inert history.

## Telemetry

Stdout is JSONL telemetry version 2. Each line is one object with `type`; the
driver ignores kinds it does not account for, and observers project only known
kinds. Required semantics:

| Event | Contract |
| --- | --- |
| `host-start` | Exactly once and first, with `telemetry_version: 2` and `schema: "player-host/1"`. |
| `request-start` | One per provider HTTP attempt, including failed and provider-only retries, with `request_id` `request-N` contiguous from 1 and never above `max_requests`. |
| `response-complete` | Per completed attempt; `usage_available` is boolean and, when true, `usage.cost.total` carries the configured or provider estimate. Missing usage stays unknown. |
| `handoff` | At most once, with `actor_id`, `session`, `handoff_id`, `context_id`, `context_sha256` and `grants_authority: false`. |
| `settled` | Exactly once and last, with `ok`, `reason` and `requests` equal to the number of `request-start` events. |

A partial final line, missing `settled`, repeated terminal events or
non-contiguous requests make accounting incomplete; the driver then charges the
whole original allocation. Telemetry carries bounded visible narration and
mechanical references, never credentials, private reasoning or raw provider
request/image histories.

## Settlement and handoff

`settled.reason` is `completed` for a terminal player report, `handoff` after a
handoff, or an adapter failure reason with `ok: false`. The host settles `handoff`
only for a direct sealed `player-handoff/1` issuance returned by `player_handoff`,
or exact collection through `computer_result` of its own pending original handoff,
naming its own actor and session. After a handoff it dispatches no further tool
call and closes its MCP child before exiting. The driver independently verifies the
canonical issuance, frozen context digest and actual host process-group absence
before minting a successor. User Pause, uncertainty or failed closure never becomes
a resumable handoff.

## Isolation

The host loads no coding-agent application, shell or file tools, personal settings,
resource discovery, resumed session, compaction, reconnect, replay or model
fallback. Only the selected credential variable reaches the host; it never appears
in files, argv, telemetry, stderr, URLs or headers other than the provider request.
The MCP child receives only `PATH` and `LANG`. The host calls tools sequentially
through the frozen MCP table; it never sends game input except through those tools.
Host attempts and seconds are separate from custodian mechanical resources.

## Conformance

The contract suite (`tests/test_player_host_contract.py`) drives each listed
adapter only through this page's argv, files, environment, stdout and exit status,
with a scripted reference provider and an MCP double. It covers validation,
argument refusal, completed and handoff settlement, telemetry accounting through
the driver's own reader, credential isolation, cancellation with MCP-child closure
and deadline expiry. An adapter for another provider wire format supplies an
equivalent provider double. Passing the suite is interface evidence only: it does
not qualify a model, provider, latency or gameplay outcome.
