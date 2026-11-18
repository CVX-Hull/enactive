---
owner: lead
status: historical
kind: review
date: '2026-11-17'
scope: 'Offline review of public intent in the single sealed Terra rehearsal admission'
---

# Stated intent in the Terra rehearsal (#714)

## At a glance

- All 32 recorded tool starts carried public intent and matched one recorded
  result each. The direct finish also carried intent. The final Quit input had a
  result with delivery recorded as unknown.
- Intent named the water task and the purpose of the final confirmation. Visible
  frames established the water effects. The transport and custodian receipts
  established acknowledgement and process state respectively.
- Defer the priced comparison in [#384](https://github.com/CVX-Hull/enactive/issues/384).
  Revisit when an operator can name a review decision that stays ambiguous after
  inspecting the existing intent, actions and linked evidence, and has recurrent
  examples with a checkable outcome for a matched comparison.

## Recorded fields and request usage

A one-off analysis read the single player-host trace from the
[sealed #711 admission](2026-11-17-terra-rehearsal-711.md) with
`harness.evaluation.core.sources.read_host` and cross-checked coverage with
`tools.host_analysis.host_summary`. It joined `tool-start` and `tool-result`
by `request_id` and `tool_call_id`, checked equality of the tool names
and summed the UTF-8 lengths of `arguments.intent`. There were 30 inputs, one observation and one
result collection. All 32 joins were unique, with zero unmatched starts or
results. The 32 intent strings total 1,918 UTF-8 bytes, with zero missing or
empty values and zero optional `cites` arguments. The separate `player-finish`
in request 33 carried 75 UTF-8 intent bytes and referenced five visible frames.

The analysis grouped `response-complete` events by `request_role` (default
`player`) and summed `usage.totalTokens`. It found 656,809 tokens across the
33 player responses and 9,127 across the four recall responses. Every response
had `usage_available` and a `reported_cost_usd` value. The
[run ledger](../../data/evaluation/runs.jsonl) records the total provider cost and
complete accounting under study 711. These are whole-response figures. The
recorded intent bytes have no separate token or cost measure in this evidence.

## Two review questions

**Water.** Request 21's intent named drinking from the rooftop tank to address
slight thirst. Request 24 named topping up the existing container, request 25
named checking the remaining water, and request 26 identified the empty bottle.
The mechanical arguments supplied the key selections, including Enter in
request 24 and examine followed by the adjacent direction in request 25.
The linked frame 733 showed the drinking and tupperware-fill messages and
17.25 L remaining in the standing tank. Request 26's returned frame 810 showed
the bottle-fill message. Intent explains the purpose of the intervening inputs.
The frames show what happened.

**Quit.** Request 29's in-game Save and quit confirmation returned title-screen
frame 938. Request 30 opened the separate application Quit prompt in frame 939.
Request 31 stated that it meant to confirm that prompt and supplied uppercase
`Y` and a one-second wait. The result recorded operation
`11bec1e74ac54c2a96292b6947718618` as unknown. Request 32 used that exact ID
to collect the original result. It also returned unknown, with no emitted-event
count or new frame. The direct finish left native exit and persistence
unverified. The independent custodian receipt recorded a normal native exit
with code zero and retained the interrupted disposition.

The briefing and reminder deliveries identify material available to the player.
The cited finish frames identify visible sources. This inspected development
case provides descriptive examples. It leaves any causal effect of delivered
knowledge, intent's effect on review decisions, and sustained useful cadence
unmeasured.
