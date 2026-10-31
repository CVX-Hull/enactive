---
owner: lead
status: historical
date: 2026-10-31
scope: Capability-led selection of a complete player configuration, conformance under player-host/1, a fixed visual check and organic gameplay
---

# Capable-player qualification

[#304](https://github.com/CVX-Hull/enactive/issues/304) tests whether a more
capable complete configuration can actually play: ground the avatar and UI
effects, make retained progress, and continue it. Speed counts only once a
configuration can play. Original packages, answers, labels, traces and saves remain
ignored project-local evidence under `.runtime/iteration304/` and
`.runtime/computer-sessions/capable304-*`, and may be unavailable in a fresh checkout.

**Decision: pending.** Gameplay is incomplete; see [the blocked admission](#first-admission-cut-off-by-provider-credit).

## Conformance under player-host/1

Three configurations were frozen through the current Pi adapter at mapped medium
effort, with OpenRouter routing pinned to one endpoint, no fallback, 16384 maximum
output and the default service tier. Endpoints were chosen fastest-first from the
OpenRouter provider pages on 31 October 2026:

| Model | Endpoint | Context | Conservative configured rates, $/M in / out |
| --- | --- | ---: | --- |
| `anthropic/claude-haiku-5.5` | `google-vertex/europe` | 1000000 | 0.55 / 2.75 (the over-100k-prompt tier) |
| `google/gemini-3.8-flash` | `google-ai-studio` | 1048576 | 1.50 / 7.50 (list price; the 50% promotion is ignored) |
| `minimax/minimax-m3.1-flash` | `fireworks` | 1048576 | 0.15 / 0.60 |

Each model received the same three requests, using the current guide and all 14 schemas:
- a short image request;
- the #302 long public-history approximation (257625 text bytes and 30 original PNGs);
- that request's own SDK-grown continuation with a returned tool result.

No game tool executed. A local SSE double first exercised the probe offline, including
the 429-retry path. It caught one probe bug: Pi returns provider failures instead of
throwing, so the retry was unreachable. That was fixed before any paid call.

All 9 paid requests succeeded on the first attempt; 3 of the 12 allowed attempts retired
unused. The serialized payloads verified the pinned route, `allow_fallbacks: false`,
`require_parameters: true`, `reasoning.effort: medium`, default tier, 14 tools and
16384 maximum output. Every continuation forwarded the assistant's `reasoning_details`
and matched tool-call IDs. Haiku requests carried Anthropic cache-control breakpoints.
Every continuation reused most of its long prefix from cache (Haiku 151326, Gemini
155793 and MiniMax 102749 cached prompt tokens). This was the first real-provider
use of `player-host/1`; no contract defect appeared.

| Seconds: short / long / continuation | Haiku | Gemini | MiniMax |
| --- | ---: | ---: | ---: |
| Completed response | 3.44 / 6.01 / 5.74 | 3.54 / 7.39 / 6.45 | 2.18 / 5.40 / 2.96 |
| Long prompt tokens | 152138 | 155812 | 102750 |

These spans are single samples. They measure neither attention nor gameplay latency.
MiniMax's short call returned no visible text despite the 25-word request.
Provider-reported cost was $0.267.

## Fixed visual check

The questions and supported/unknown labels were frozen before any query. The question
was #302's unchanged four-part prompt, sent with no tool dispatch. There were four
sequences:
- **D2:** Look cursor pan with a stationary avatar.
- **D4:** a one-tile northward step, then Look selection.
- **P1:** a pickup selection preview (12.6 → 16.7 lb) cancelled with ESC.
- **P2:** a fresh-Load inventory with only murky water.

D2 and D4 were previously answered by DeepSeek and Qwen. P1 and P2 are #302 native-case
frames not previously asked. A clean-context reviewer labelled P1 and P2 from the
original PNGs alone. Twelve attempts succeeded at $0.058 provider-reported cost.

| Model | Decisive outcome | Word limit (220) |
| --- | --- | --- |
| Gemini 3.8 Flash | Captured every decisive fact, including the D4 step and the P1 cancellation; small overclaims about NPC positions and an unseen clock | Within on all four |
| Haiku 5.5 | Most careful about unknowns, but denied the supported D4 avatar travel (the DeepSeek/Qwen miss) and left the P1 cancellation open | Over on all four |
| MiniMax M3.1 Flash | Treated the P1 preview as changed carried load, invented items and weights, misread the clock, and misidentified the avatar | Over on all four |

An independent rescoring from labels and answers gave the same ranking. These are
one-response cells on four fixed frame sets, not a comparable game score. Gemini
became the first gameplay configuration, with Haiku as the alternate.

## First admission cut off by provider credit

`capable304-play001` used Gemini 3.8 Flash, the unchanged guide and 14 tools, a
30-image history and source `72a8e05`. Its allocation was one host, 140 attempts,
2400 host / 3000 custodian seconds and #304's ending reserve. The only history
supplied was the case 004 terminal report, marked as fallible.

[Assessment pending.]

Request 80, at 570 seconds, was refused before inference with HTTP 402,
`limit_source: openrouter_in_flight_budget`:
- The account showed $825 credits against $822.63 usage. The key's own limit was not
  reached ($29.06 of $250 monthly).
- The host stopped. The custodian revoked custody and terminated native with SIGTERM.
- Owned host, MCP and native groups were verified absent. There was no Save and no
  normal exit.
- Useful-gain latency is censored by an external account refusal. This is not a
  capability or serving failure.
- The balance was unchanged about 8 minutes later, although the owner has auto top-up
  enabled.

Only 22% of prompt tokens were read from cache. The 30-image projection drops the oldest
image every turn, so the prefix changes. That cost and latency question belongs to #164.

## Accounting

Actual spend is reported first; the cumulative reservation is only the admission cap
check (see [campaign run](../operations/campaign-run.md)).

| Lane | Attempts | Actual cost |
| --- | ---: | ---: |
| Conformance | 9 | $0.267 provider-reported |
| Visual check | 12 | $0.058 provider-reported |
| capable304-play001 | 80 | about $3.46 (key daily usage); the configured estimate at list price was $7.30 |
