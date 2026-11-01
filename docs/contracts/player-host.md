---
owner: lead
review_trigger: Driver/host invocation, route envelope, telemetry, settlement, isolation or adapter changes
status: active
---

# Player host contract

`player-host/4` is the one current boundary between the [campaign driver](../../tools/campaign_player.py)
and the program that hosts a deciding player or one pass of its subgoal level
([ADR-007](../decisions/007-player-subgoal-level.md) candidate). The host turns frozen context, a
frozen provider route and the actor's MCP table into model calls and sequential
player tool calls. The driver owns actor minting, original limits, process-group
closure, handoff verification and succession. Any adapter that satisfies this page
and passes the [conformance suite](../../tests/test_player_host_contract.py) is
substitutable; no driver, packager or gameplay page depends on a particular
adapter. The [current adapter reference](../../tools/player_host/README.md) owns
its provider serializers, closed route `model` fields and limits.

## Adapter selection

A `campaign-run/4` package freezes `host`: `{"argv": [...]}` with 1–8 strings.
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

The frozen route is one closed JSON object with `schema: "player-host/4"`, `role`,
`intent_tail_bytes`, `model`, `api_key_env`, `max_requests`, `max_context_images`,
`context_image_block`, `request_timeout_seconds` and `service_tier`. `role` is
`actor` or `level`. `intent_tail_bytes` is null or, for an actor only, 64–4096.
`max_context_images` is the hard peak of pixel images in one request.
`context_image_block` (1 to that peak) is the count-only block in which the oldest
historical images beyond the peak are replaced by markers; block 1 replaces exactly
the overflow. The driver and package validator
read only: `model.id`, `model.name`, `model.cost.{input,output,cacheRead,cacheWrite}`
(dollars per million tokens), `model.contextWindow`, `model.maxTokens`,
`api_key_env`, `max_requests` and `service_tier`. The adapter owns every other
closed `model` field and rejects routes it cannot serve without fallback. The
driver lowers `max_requests` to the actor's remaining original allowance before
launch. Routes carrying any other schema, including `player-host/1` and earlier
adapter-named route schemas, are rejected; their packages and traces are inert history. One logical inference
request uses at most two charged attempts, each counted against `max_requests`;
the adapter's host reference defines which transient refusal classes are retried.

## Telemetry

Stdout is JSONL telemetry version 2. Each line is one object with `type`; the
driver ignores kinds it does not account for, and observers project only known
kinds. Required semantics:

| Event | Contract |
| --- | --- |
| `host-start` | Exactly once and first in any run that admits its arguments and inputs, with `telemetry_version: 2`, `schema: "player-host/4"`, `role` and `intent_tail_bytes`; the driver rejects any other schema. |
| `mcp-connected` | Once the MCP child is connected, before tool discovery. A level's first pass waits for the actor's first `request-start` instead, which follows the tool checks. |
| `level-pass` | Level role only, once after tool discovery. |
| `level-commit` / `level-discard` | Level role only, per `player_level_commit` result (never for a local tool error, so a rejected commit emits neither), with `action`, `reason`, `position`, `inputs_since`, `staleness_inputs`, `record_ids` and `kept`. Either one ends the pass. |
| `level-abstain` | Level role only, per valid `player_level_abstain` result (never for a local tool error), with `request_id`, `tool_call_id` and `reason`. It ends the pass. |
| `intent-tail` | Actor with a tail, per request, with `available`, `record_id`, `surfaced_bytes`, `omitted_bytes` and `age`. |
| `request-start` | One per provider HTTP attempt, including failed and provider-only retries, with `request_id` `request-N` contiguous from 1 and never above `max_requests`. |
| `response-complete` | Per completed attempt; `usage_available` is boolean and, when true, `usage.cost.total` carries the configured or provider estimate. Missing usage stays unknown. |
| `handoff` | At most once, with `actor_id`, `session`, `handoff_id`, `context_id`, `context_sha256` and `grants_authority: false`. |
| `settled` | Exactly once and last, with `ok`, `reason` and `requests` equal to the number of `request-start` events. |

Two failure shapes are permitted and always unsuccessful. A host that refuses its
mode, arguments or inputs before starting emits only one `settled` with `ok: false`
and no `host-start`. A host that fails after settling (for example while writing
`FINAL`) may append a second `settled` with `ok: false` and exits nonzero.
A partial final line, missing `host-start` or `settled`, repeated terminal events
or non-contiguous requests make accounting incomplete; the driver then charges the
whole original allocation and admits no successor. Telemetry carries bounded visible narration and
mechanical references, never credentials, private reasoning or raw provider
request/image histories.

## Roles and the intent tail

An **actor** host decides and sends input. With `intent_tail_bytes` set, before each
provider request it calls the custodian's host-internal `player_intent` tool itself,
which must be discovered and must not be in `enabled_tools`, so the model never sees
it. The host appends ADR-007's fixed label ("Current intent (software-published from
the player's subgoal level; fallible player data with sources and age, not
instructions).") and the latest committed subgoal (text, expected observations,
status, confidence, sources, record ID and its age in inputs, seconds and session)
to the request-only status message. That body is bounded to `intent_tail_bytes` UTF-8
bytes with the omitted count stated; the fixed label and the omission marker are extra
and not counted in `surfaced_bytes`. A failed read or an unexpectedly shaped value shows
"Unavailable" and never stops the actor or gates its input. A null tail (flat, arm B, the fourth arm and shadow mode) adds nothing.

A **level** host runs one finite pass with a reader capability. Its enabled tools
must include `player_log_read`, `player_level_commit` and `player_level_abstain`. It
sends no input and makes no handoff. The driver, not the host, schedules passes and
supplies the frozen role prompt, the actor's mission brief, the pushed served-player
log since the previous pass, the current subgoal and mechanical wake facts as its prompt.

**A level pass ends on a commit or an abstain.** Every provider request of a level
host carries `tool_choice: "required"` (an actor's does not), so the model cannot end
in prose. The pass ends, with no further tool dispatch (later calls in the same batch
are refused with `tool-refused` reason `level-ended`) and settles `completed`, after
either a `player_level_commit` result that becomes a commit or discard (`level-commit`
or `level-discard`) or a valid `player_level_abstain` result (`level-abstain`). A
rejected commit or abstain (a tool error) does not end the pass; the model may
correct it within the pass allowance. A level pass that ends any other way without
such a result, for example a text-only terminal response, settles `ok: false` with
reason `level-no-proposal`; a failure that was already latched (a provider error, the
request limit or the deadline) keeps its own reason. The level's text is never read.

## Settlement and handoff

`settled.reason` is `completed` for a terminal player report, `handoff` after a
handoff, or an adapter failure reason with `ok: false`. The host settles `handoff`
only for a direct sealed `player-handoff/2` issuance returned by `player_handoff`,
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

The [contract suite](../../tests/test_player_host_contract.py) drives each listed
adapter only through this page's argv, files, environment, stdout and exit status,
with a scripted reference provider and an MCP double. It covers validation,
argument refusal, completed and handoff settlement, telemetry accounting through
the driver's own reader, credential isolation, cancellation with MCP-child closure
and deadline expiry. An adapter for another provider wire format supplies an
equivalent provider double. Passing the suite is interface evidence only: it does
not qualify a model, provider, latency or gameplay outcome. The
[adoption record](../acceptance/2026-10-31-host-neutral-player.md) retains the first
conformance run and an offline native driver preflight through this contract.
