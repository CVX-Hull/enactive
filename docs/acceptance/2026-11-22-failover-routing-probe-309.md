---
owner: lead
status: historical
kind: measurement
date: '2026-11-22'
scope: 'Bounded real OpenRouter routing probe for #309 ($0.012221 of $3.00 approved hard cap, 12 streaming calls, 0 game launches): verifying openai and azure endpoint parity, declared-list selection and confinement, Azure prompt caching, SSE chunk.provider attribution, and GET /api/v1/generation?id= provider_responses[] auditability for openai/gpt-6.1-terra'
---

# Same-model failover routing probe (#309)

## At a glance

- **Question.** For `openai/gpt-6.1-terra` on OpenRouter, does a declared two-endpoint `only`/`order` list with `allow_fallbacks: false` and `require_parameters: true` (Design (a)) provide a bounded, compatible, auditable second endpoint (`openai` then `azure`) without leaking to undeclared endpoints, or is host-side failover (Design (b)) required?
- **Answer — Declared two-endpoint parity, confinement, caching and attribution confirmed; `order` precedence not isolated and live upstream-error failover not observed.** Across **12 bounded streaming calls** (`$0.012221` counted spend of the `$3.00` approved hard cap, `0` game launches, `0` unpriced errors):
  1. **Tested player-host parameters succeed on both endpoints:** Both `openai` (`endpoint_id: 2d2ad10f-098e-4bbf-aa95-11f705b2b9a2`) and `azure` (`endpoint_id: 122668ab-7b62-4fba-b988-7438e32b1c03`) serve `openai/gpt-6.1-terra-20261026` with `max_tokens: 128`, `require_parameters: true`, `service_tier: "default"`, `reasoning: {effort: "medium"}`, one `computer_observe` tool declaration (`tool_choice: "none"`), `x-session-id`, and a retained `#889` gameplay PNG at identical standard rates (`$1/M` input, `$5/M` output, `$0.05/M` cacheRead, `$1.25/M` cacheWrite below 272,000 prompt tokens).
  2. **Selection is consistent with the declared list and confined to allowed providers (`order` not isolated):** `only/order: ["openai", "azure"]` routed to `OpenAI` (`p9`, 200 OK, `2.201 s`; no reversed `["azure", "openai"]` control was run to isolate `order` from OpenRouter's default preference); `only/order: ["deepinfra", "azure"]` left only one eligible endpoint and selected `Azure` (`p10`, 200 OK, `2.036 s`, one `provider_responses` entry); `only/order: ["deepinfra"]` refused (`p7`, HTTP 404). In `p7`'s routing funnel (`probe-results.json`), candidate rows dropped `7 -> 4 -> 2` with reason `"Excluded tier endpoint rows the request did not opt into"` at `"Filter by Tier Endpoint Rows"` (no call omitted `service_tier`, so removing `openai/flex` and `openai/fast` via `service_tier: "default"` is inferred from the snapshot and counts rather than isolated), and `"Filter by Allowed Providers"` then rejected the remaining `2` rows because `provider.only` permitted only `deepinfra`. No call isolated `allow_fallbacks: false` on its own.
  3. **Prompt caching works on Azure:** Two consecutive `>1,024`-token calls to `azure` (`p11a -> p11b`) hit **2,804 / 2,879 cached prompt tokens (97.4%)**, dropping per-call cost from `$0.003675` to `$0.000310`.
  4. **Endpoints are distinguishable in SSE and delayed generation records:** Each of the 11 successful streams reported exactly one distinct SSE `provider` value (`"OpenAI"` or `"Azure"`, captured by `player_host` as `reported_provider`), and `GET /api/v1/generation?id=<id>` returns `provider_name` and `provider_responses[]` (`endpoint_id`, `provider_name`, `model_permaslug`, `latency`, `status`) once indexed (immediate lookups returned HTTP 404 due to indexing lag; delayed lookups succeeded for `p1`–`p11a`, while `p11b` still returned HTTP 404 on its delayed lookup).
- **Unknowns and limits.**
  - **Live upstream-error failover was not observed.** `openai` returned HTTP 200 on every probe call and no live upstream 5xx/429 failure could be injected. `p6` and `p10` skipped an ineligible tag (`deepinfra`, which does not serve `openai/gpt-6.1-terra-20261026`), producing a single `provider_responses` entry (`Azure`, 200) rather than an observed upstream error followed by a server-side retry. Using Design (a) for runtime failover on an upstream error relies on [OpenRouter's documented provider routing contract](https://openrouter.ai/docs/guides/routing/provider-selection) (`order` tries declared providers one at a time; `allow_fallbacks: false` restricts attempts to the declared list), not on an observed two-entry `provider_responses[]` error trace. Whether OpenRouter switches without waiting out upstream backoff on a live primary 502 remains unverified until an actual upstream failure occurs.
  - **Untested payload and session behaviors.** The probe used `tool_choice: "none"`, `128` max tokens, and recorded zero reasoning tokens on the checked lookups (`p6`, `p9`–`p11a`). It did not exercise live tool calls, recall's strict `response_format` schema, multi-turn cache stickiness, or mid-conversation reasoning-item portability across an `OpenAI -> Azure` switch.
- **Owner decisions.** The probe was authorized under the 22 November 2026 `$3.00` routing-probe approval ([archived probe approval](../decisions/owner-decisions-archive.md#failover-routing-probe-approved-309)). Following clean-context review, the owner explicitly accepted OpenRouter's documented `order` + `allow_fallbacks: false` failover contract together with the empirically verified properties above as sufficient to merge `player-host/11` ([merge approval](../decisions/owner-decisions.md#player-host-11-failover-approved-309)). Implementation spends `$0` and keeps single-endpoint routes valid (`endpoint_costs: null`); whether `#896` runs pinned (`["openai"]`) or two-endpoint (`["openai", "azure"]`) remains an explicit per-package choice.

[Issue #309](https://github.com/CVX-Hull/enactive/issues/309) · [Player host contract](../contracts/player-host.md) · [Backoff review #805](2026-11-19-request-deadline-during-provider-backoff-805.md)

## Sealed evidence and endpoints snapshot

Raw sanitized probe inputs, SSE summaries, `GET /api/v1/generation` lookups, and the public `/api/v1/models/openai/gpt-6.1-terra/endpoints` snapshot are sealed in `.runtime/evidence/failover-routing-probe-309/` (`data/evidence/failover-routing-probe-309.sha256`). Every call sent retained `#889` gameplay frame `a02d8069d0434813a41acc7009217da6-3686.png` (SHA-256 `24148c9e542a…`, verified in `probe-results.json`), one `computer_observe` tool declaration with `tool_choice: "none"`, `service_tier: "default"`, `reasoning: {effort: "medium"}`, `stream: true`, `stream_options: {include_usage: true}`, and `x-session-id` affinity, with no game launched (`#retained-images-allowed-in-bounded-endpoint-tests`).

OpenRouter advertised four endpoints for `openai/gpt-6.1-terra` on 22 November 2026 (`endpoints-snapshot.json`). Rates below apply up to 272,000 prompt tokens (above `#889`'s 262,144 context window); the snapshot doubles prompt and cache rates and applies 1.5x output rates above 272,000 prompt tokens:

| Tag | Provider | Status | Prompt / Completion (`$/1M`) | Cache read / write (`$/1M`) | Notes |
| --- | --- | ---: | --- | --- | --- |
| `openai` | OpenAI | 0 | `$1.00` / `$5.00` | `$0.05` / `$1.25` | Current primary; advertises `max_tokens` |
| `azure` | Azure | 0 | `$1.00` / `$5.00` | `$0.05` / `$1.25` | Same-price secondary; advertises `max_completion_tokens`, accepted both `max_tokens` and `max_completion_tokens` in probe |
| `openai/flex` | OpenAI | 0 | `$0.50` / `$2.50` | `$0.025` / `$0.625` | Non-default tier row (inferred excluded by tier filter in `p7`; also outside `only`) |
| `openai/fast` | OpenAI | 0 | `$2.00` / `$10.00` | `$0.10` / `$2.50` | Non-default tier row (inferred excluded by tier filter in `p7`; also outside `only`) |

## Probe results (12 calls, `$0.012221` total)

Measured directly from `.runtime/evidence/failover-routing-probe-309/probe-results.json`:

| Probe | `provider.only` / `order` | `require_parameters` | Max field (`128`) | HTTP | SSE `provider` | Prompt / Cached tok | Counted USD | Wall s | Delayed `/generation` `provider_responses[0]` |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| `p1` | `["openai"]` | `true` | `max_tokens` | 200 | `OpenAI` | `804 / 0` | `$0.000909` | 2.773 | `OpenAI` (`2d2ad10f…`, 384 ms, 200) |
| `p2` | `["azure"]` | `true` | `max_tokens` | 200 | `Azure` | `807 / 0` | `$0.000917` | 1.824 | `Azure` (`122668ab…`, 942 ms, 200) |
| `p3` | `["azure"]` | `true` | `max_completion_tokens` | 200 | `Azure` | `807 / 0` | `$0.000917` | 1.734 | `Azure` (`122668ab…`, 1017 ms, 200) |
| `p4` | `["openai"]` | `true` | `max_completion_tokens` | 200 | `OpenAI` | `804 / 0` | `$0.000919` | 2.236 | `OpenAI` (`2d2ad10f…`, 465 ms, 200) |
| `p5` | `["openai", "azure"]` | `false` | `max_tokens` | 200 | `OpenAI` | `804 / 0` | `$0.000904` | 2.265 | `OpenAI` (`2d2ad10f…`, 367 ms, 200) |
| `p6` | `["deepinfra", "azure"]` | `false` | `max_tokens` | 200 | `Azure` | `807 / 0` | `$0.000927` | 2.193 | `Azure` (`122668ab…`, 918 ms, 200) |
| `p7` | `["deepinfra"]` | `false` | `max_tokens` | 404 | — | — | `$0.000000` | 0.151 | Refused (`No allowed providers…`) |
| `p8` | `["azure"]` | `false` | `max_tokens` | 200 | `Azure` | `807 / 0` | `$0.000922` | 1.560 | `Azure` (`122668ab…`, 794 ms, 200) |
| `p9` | `["openai", "azure"]` | `true` | `max_tokens` | 200 | `OpenAI` | `804 / 0` | `$0.000919` | 2.201 | `OpenAI` (`2d2ad10f…`, 290 ms, 200) |
| `p10` | `["deepinfra", "azure"]` | `true` | `max_tokens` | 200 | `Azure` | `807 / 0` | `$0.000902` | 2.036 | `Azure` (`122668ab…`, 1140 ms, 200) |
| `p11a` | `["azure"]` | `true` | `max_tokens` | 200 | `Azure` | `2,879 / 0` | `$0.003675` | 1.492 | `Azure` (`122668ab…`, 905 ms, 200) |
| `p11b` | `["azure"]` | `true` | `max_tokens` | 200 | `Azure` | `2,879 / 2,804` | `$0.000310` | 2.788 | 404 on delayed lookup (indexing lag) |

All 11 successful responses (`p7` returned 404 with no usage) echoed `service_tier: "default"`, `model: "openai/gpt-6.1-terra"`, and `finish_reason: "stop"`, and had `cost == cost_details.upstream_inference_cost` with `is_byok: false`.

## Design choice for `player-host/11`

- **Selected design: Design (a) — declared two-endpoint `only`/`order` list with `allow_fallbacks: false` and `require_parameters: true`.**
- **Why Design (a) over Design (b) (host-side failover):** Under `#request-deadline-stays-during-provider-backoff`, a 60 s upstream `Retry-After` on a primary 502/503 refusal exhausts the host’s 60 s request timer (`#803` reload). Design (a) delegates ordered endpoint selection to OpenRouter under its documented `order` + `allow_fallbacks: false` contract without adding a second host retry state machine. Because runtime failover on a live upstream 5xx was not observed in the probe, if a future campaign shows OpenRouter does not fail over before exhausting the request deadline on a primary 502, host-side failover (Design (b)) remains a clean follow-up.
- **Attempts per logical request:** Unchanged at **maximum 2 host HTTP attempts per logical request** (`1` initial attempt plus at most `1` shared host retry across `429`, `5xx`, `402` in-flight budget, `stream-start-error`, `pre-header-rejection`, or once-per-actor `incomplete-stream-timeout`), each sending the same declared `only`/`order` list.
- **Pricing & telemetry contract (`player-host/11`, `telemetry_version: 11`):**
  - `openRouterRouting.only` and `order` accept 1 or 2 distinct valid tags (`order` equal to `only`), keeping `allow_fallbacks: false` and `require_parameters: true`.
  - Closed required route field `endpoint_costs`: `null` for direct or 1-endpoint routes; for 2-endpoint OpenRouter routes, a closed map of both declared tags to `{input, output, cacheRead, cacheWrite}`, validated so `model.cost` equals the element-wise maximum rate across the declared endpoints (so `unpriced_request_usd` automatically bounds the worst-case endpoint).
  - Top-level `reported_provider` emitted on both player and recall `response-complete` events (from SSE `chunk.provider`), and `tools/host_analysis.py` splits latency and provider-reported cost (`reported_cost_usd`) by endpoint (`response_by_endpoint`) for `#164`.
