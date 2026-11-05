---
owner: lead
status: active
review_trigger: Recorded-screen assessment scope, no-execution boundary or candidate admission changes
---

# Recorded-screen deciding-player assessment

## Decision and scope

The [ongoing-player diagnostic](../acceptance/2026-11-05-player-test-diagnostic.md)
ended in death with particular action-choice errors. Before another game, prepare
a small assessment of a candidate's tool transport and proposed control choices
using original recorded views. [#366](https://github.com/CVX-Hull/enactive/issues/366)
owns this bounded investigation under #164. Preparation authorizes $0 provider/gameplay spend;
the exact paid scope and candidate choice require owner agreement. The current
player, host contract and full-cohort criteria remain unchanged.

Candidate: GPT-6.1 Terra medium through OpenRouter's pinned default `openai`
endpoint, no fallback. This is a proposal, not a quality ranking. Current
[OpenAI guidance](https://developers.openai.com/api/docs/guides/model-selection)
identifies screen-based work as a use case; native
[Terra tool calling](https://developers.openai.com/api/docs/models/gpt-6.1-terra)
requires Responses. OpenRouter documents a standardized
[client-tool interface](https://openrouter.ai/docs/guides/features/tool-calling)
and advertises tools for the candidate endpoint. Actual compatibility through
the existing Chat Completions host remains unverified. Do not change the host
contract to force a pass.

## Reuse and responsibilities

Reuse the unchanged `player-host/3` CLI, pinned Pi SDK, current tool definitions,
typed argument validation, image projection, request/retry limits, sanitized
telemetry and owned stdio closure. Do not copy the older identity collector's
retired imports, hard-coded fourteen-tool count, SSE parser, route or admission.
It is historical evidence, not a current launcher.

The missing capability is a tool endpoint that can expose frozen PNGs while
making game effects impossible. Add a small MCP fixture under `tests/fixtures`,
using the maintained MCP Server and `tool_specs()`. It imports no player client,
native runtime, controller, program executor or memory store. It has no game
URL, actor capability or live target. `computer_observe` and `player_source`
return explicitly labelled original recorded metadata/PNGs. Every other tool
request is logged as a proposal and refused. It never manufactures delivery,
updated game state, persistence or successful program/memory work.

The fixture advertises the exact current MCP schemas; the unchanged host adds
its own finish tool. Server instructions state the offline scope and lack of
authority. Retain original source IDs, clocks and hashes without relabelling
them as fresh observations. Keep answer keys, engineering bindings, post-case
outcomes and scoring instructions outside model context.

The fixture's local input is one bounded JSON object with `current_source_id`
and `sources`, an ordered list of unchanged `computer-source/1` metadata. PNGs
live beside it in `sources/<source_id>.png`. Reuse current source validation;
verify hashes, dimensions, unique IDs, current-source membership and local regular
files before serving. Limit the packet to thirty sources and 16 MiB total PNGs,
within the host's existing 32 MiB MCP result bound after base64 encoding.
`computer_observe` returns the ordered historical packet with each metadata/image
pair labelled, identifying the selected last view; `player_source` returns one
exact member. Neither operation captures anything. Refused calls retain name
and arguments in the fixture log, without claiming any delivery or effect.

The lead owns preparation, design, integration and verification. One bounded
worker may implement the fixture/tests in a separate worktree; one writer per
path. Engineering lead owns fixture maintenance. Replace it when an existing
maintained read-only assessment capability supplies the same current-schema
and no-execution guarantees; retire it when this assessment path is unused.
No new dependency, generic runner, provider parser, host mode or package contract.

## Prospective experiment

Two separately frozen cases, each a fresh host with at most two charged provider
attempts including retries: four total. The first response is asked to inspect
the retained view through tools; the next can propose an action. The request
limit is operator-only. Do not execute a proposal or silently add a call when
the model does not complete this sequence. A direct finish, refusal, retry or
missing observation can leave a case inconclusive.

Keep actual host settlement separate from assessment completeness. A refused
action proposal normally causes the unchanged host to continue, then settle
`ok:false, reason:request-limit` before a third provider fetch. Preserve that
unsuccessful disposition. Two matched responses, complete usage, original-image
continuation and verified child closure can still supply bounded assessment
evidence; they do not turn host exhaustion into successful goal completion.
If the model calls `player_finish`, retain its actual disposition. A proposal
before any retained observation is unsupported for this assessment. Early finish,
retry exhaustion or missing image continuation stays incomplete, with no extra
attempt. Test both proposal-only exhaustion and proposal plus direct finish.

One case uses the original map/identity views before request 47. The other uses
the original pre-retreat views before request 66, with a frozen, labelled public
history approximation and at most thirty original images to exercise a larger
continuation. Freeze exact selections and all wording before approval. No
private reasoning, future frames, engineered expected move or tactical hint.
These selected cases do not support a general model ranking or survival claim.

Reuse the actual host CLI with explicit route, fixture MCP profile, guide,
assignment, fresh assessment IDs and an open control pipe. Bound each host at
150 seconds, preserving its normal cleanup budget. Allow at most 330 seconds
for the pair and outer closure; no native game or spectator watch is involved.
Use only the already selected credential environment for the host; the fixture
receives the host's normal PATH/locale-only environment. No credential lookup
or global permission change belongs in the fixture.

Technical assessment checks exact requested route/effort/tier, observed provider
and backend against a prospectively frozen allowlist, complete usage/settlement,
current schemas and SDK-grown image/tool-result continuation. Missing or partial
evidence is unknown, not a pass. Independent LLM review can describe grounded
claims and consistency between stated direction/command and proposed input;
there is no unique hand-labelled winning action. Keep outputs out of the player
memory and later gameplay context. Do not score proposal counts as usefulness.

At proposed full 1.05M context/16,384 output, conservative maximum input/cache
rate $2.50/M and output $7.50/M, four attempts reserve $10.99152. Existing planning
margin 8% + $3 gives $14.8708416; prospective cap $15. Verify exact endpoint rates,
retention assumptions, current account headroom and cumulative actual baseline
before requesting approval. No purchase, refill change or paid eligibility call
is authorized by this brief. Missing usage counts at its worst case.

## Verification and limits

Before implementation, independently review the no-execution boundary and reuse
choice. Focused tests exercise actual stdio MCP and the unchanged host with an
injected offline provider: current schema equality, original PNG/hash identity,
refused mutating/unknown tools, bounded calls/retries, credential isolation,
invalid packet refusal and owned fixture closure. Tests cannot establish the
candidate's serving, grounding or gameplay performance.

Inspect and commit the exact source, review code/integration, pass appropriate
protected CI and validate main. Freeze the actual packets, route, source, outputs,
financial bound and stopping/scoring plan; independent review precedes the paid
decision. Prefer a short documented invocation of the existing host over a new
reusable admission framework.

If transport or grounding fails, retain the result and propose the smallest
evidence-led next decision. If both cases are promising, separately shape a
substantive unassisted development run; this screen admits neither gameplay nor
the full cohort. External orderly-stop, programs, useful effects, original
20-decision/2s p95/5s stall/500ms local-effect criteria and #145's seven-day gate
remain open. Preserve authority, budget, uncertainty, two-failed-repair,
protocol-deviation, contract/design and destructive-action stops. No automatic
new provider, adapter, game, request extension or reinterpretation of a failure.
