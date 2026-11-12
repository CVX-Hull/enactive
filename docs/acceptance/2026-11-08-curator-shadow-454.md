---
owner: lead
status: historical
date: '2026-11-08'
scope: 'Curator shadow sessions over the sealed #397 lineage and the #372 sample: cost, lag, cold start and gate pass rate for one Pi-based host with two OpenRouter models (#454)'
review_trigger: None; dated record
---

# Curator shadow sessions (#454)

ADR 009's P0 asks for the curator's cost, lag and cold start to be measured on sealed
traces before any live use. This record has those figures, and the gate pass rate, for
curator sessions replayed over the sealed #397 lineage and #372's sampled development
runs. #382's held-out lineages were refused by the runner and never opened. No game ran.

**Where the figures come from.** Every per-session figure is derived by
[`tools/curator_shadow_report.py`](https://github.com/CVX-Hull/enactive/blob/1bc5d65/tools/curator_shadow_report.py) into
[`data/curator/shadow-454.json`](assets/curator-shadow-454/shadow-454.json). Its inputs are:
- the shadow runner's session summaries, which hold the proxy-settled cost;
- the tracked run ledger, for the actor's own pace, game hours and spend.

The pilots below are taken from their own summaries.

## Setup

**Owner decisions** (ADR 009 open decision 2, 8 November 2026):
- **Hosts.** One Pi-based curator host the project controls ([`tools/curator_host`](../../tools/curator_host)), with two OpenRouter models:
  - **terra:** the actor's model, `openai/gpt-6.1-terra`;
  - **opus:** `anthropic/claude-opus-5.5`.

  This replaces the "two coding-agent hosts" of #454's brief.
- **Cap.** $100 in total, staged behind a pilot.
- **Measurement plan.** After the pilots: terra on all 13 sessions and Opus on 5, each capped at $40.

**Per session.**
- [`run_session`](../../harness/curator/session.py) projects one admission or run into a fresh workspace and runs the host under the Seatbelt sandbox.
- The [proxy](../../harness/curator/proxy.py) holds the key, enforces a dollar cap, and settles each request at OpenRouter's reported cost.
- The gate judges each submission, against a fresh knowledge repository per run.
- Sessions run in lineage order, so knowledge carries forward within a run.
- **Settings:** effort medium; at most 120 requests per session; a 24-image context window, evicted 12 at a time. The host's own budget is 85% of the session cap.
- **Prices:** frozen from OpenRouter's public list on 8 November ([`data/curator/openrouter-prices-2026-11-08.json`](../../data/curator/openrouter-prices-2026-11-08.json)).

**What the curator sees.**
- The projected trace (frames, steps, received text), the published knowledge, its drafts and the brief.
- No probes, no evaluation data, and no memory store for #397: the lineage-wide store would carry later admissions into earlier ones.
- #372's runs have per-run stores, and those were passed.
- The [prompt](../../tools/curator_host/prompt.md) holds no game knowledge.

## Pilots and the change they forced

| Pilot (#397 `sd1a2`) | Requests | Cost | Outcome |
| --- | ---: | ---: | --- |
| terra, first host | 120 | $3.35 | Aborted at the request limit after 128 frame views; nothing written |
| Opus, first host | 71 | $7.65 | Aborted at its $10 cap after 69 frame views; nothing written |
| terra, budget-aware host | 39 | $3.52 | Sealed; one submission accepted (knowledge `v1`) |

**Finding: a curator with no budget awareness reads until it is stopped.** Both
first-host pilots viewed frames one per request and never wrote anything.

**The fix, before any measured run** (commit `24d8fdc`):
- **A budget note** ends every request (requests and dollars used). It is appended per request, never stored.
- **A write-by point:** past half the budget, the curator is asked to write.
- **A cut-off:** past four fifths, reading tools are refused.
- **Batched frames:** one call shows up to four.
- **Prompt:** frame choice goes through the steps and the workbench.

The pilots spent $14.52 and are not included in the results below.

## Results

| Model, lineage | Sessions run | Sealed | Gate accepted | Cost | Actor game hours | Curator $ per game hour | Curator ÷ actor spend |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| terra, #397 (7 admissions) | 7 | 6 | 6 / 6 | $23.27 | 47.79 | 0.49 | 0.61 |
| terra, #372 sample (6 runs) | 5 | 4 | 4 / 4 | $16.14 | 4.44 | 3.64 | 0.87 |
| **terra, all** | 12 | 10 | **10 / 10** | **$39.41** | 52.23 | **0.75** | **0.69** |
| opus, #397 `sd1a1`–`sd1a3` | 3 | 3 | 3 / 3 | $21.91 | 29.49 | 0.74 | 1.16 |
| opus, #372 `aidB3`, `ceil09` | 2 | 2 | 2 / 2 | $11.46 | 2.53 | 4.53 | 1.43 |
| **opus, all** | 5 | 5 | **5 / 5** | **$33.38** | 32.02 | **1.04** | **1.24** |

| Model | Median session wall time | Median lag, decisions | Median lag, game hours | Cold start: time to first request | Cold start: first-request prompt tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| terra | 189 s | 47 | 0.16 | 0.13 s | 2,924 |
| opus | 159 s | 28 | 0.52 | 0.13 s | 4,639 |

**Definitions.**
- **Lag in decisions** is the session's wall time divided by the actor's routine seconds
  per decision in that admission or run.
- **Lag in game time** is that many decisions at the admission's game hours per decision.
- **Curator ÷ actor spend** compares the curator's settled dollars with the actor's
  dollars for the same admission (decisions × dollars per decision, from the ledger).
- **Cold start** is the time from the host starting to its first model request, and that
  request's prompt tokens: the system prompt, tool schemas and brief.

**Totals.**
- The measured runs spent $72.79. With the pilots, P0 spent $87.31 of the $100 cap.
- No proxy breach, no revocation and no missing usage occurred in any session. The only
  proxy refusals were spend-cap refusals.

**What the curators wrote.**

| Run | Facts | Types | Published version |
| --- | ---: | ---: | --- |
| terra, #397 | 71 | 5 | `v6` |
| terra, #372 | 45 | 3 | `v4` |
| Opus, #397 | 30 | 4 | `v3` |
| Opus, #372 | 18 | 4 | `v2` |

Each fact cites about two frames on average. The facts cover controls, screens,
crafting, resources and the start scenario. Every session that sealed wrote exactly
one submission, and the gate accepted every one.

**What the figures say, as development evidence only.**
- **Within one lineage, cost falls as knowledge accumulates.** Terra's #397 sessions
  went from $7.08 (`sd1a1`) to $1.26 (`sd1a6`).
- **On the long lineage, terra cost about 0.6× the actor's spend.** That is
  $0.49 per game hour, against the actor's $0.80.
- **Opus cost about 1.2× the actor's spend** on fewer sessions.
- **On short runs, both cost more per game hour.** The curator's fixed reading
  outweighs the run's few game hours.
- **Lag is a few minutes of wall time,** about 30–50 actor decisions. ADR 009 D15
  accepts lag: the actor reads only published snapshots.
- **A 100% gate pass rate says the submissions were well formed, current and cited,
  not true.** Gate v0 checks form, base version, scope and provenance. Whether the
  facts are right, and whether they surface what a later actor needed, is P1's
  question, answered by the #449 probes.

## Finding: prompt caching barely worked

**Almost every prompt token was written to the cache, and few were read from it.**
Across the 17 measured sessions, cached prompt tokens were 2.5–9.8% of all prompt tokens,
and cache writes made up nearly the rest. The 24-image window, which makes image
evictions rare, did not change that.

**Likely cause, not verified.** No session-affinity header was ever sent. OpenRouter's
sticky routing keeps a session on the same provider backend, where its cache lives, and
it needs such a header.
- **The host.** The serializer sends `x-session-id` only when the agent is given a
  session ID. The curator host never sets one, and neither does the actor's host.
- **The proxy.** Its header allowlist (`content-type`, `accept`, `anthropic-version`,
  `user-agent`) would drop the header anyway.

A context review after the runs found this. A first draft of this record wrongly said
the host sent the header and the proxy dropped it.

**Why it matters.** Terra's prices are $1.25 per million tokens to write the cache and
$0.05 to read it. If caching worked, most of each request's prompt would be billed at
the read price, so the measured cost is likely an overestimate of what a fixed host
would spend.

**The fix is a P1 prerequisite.**
- Each session gets one affinity value. The proxy is the place to set it, because the
  host cannot widen the headers it sends.
- One paid session verifies whether affinity actually raises the cached share. Until
  then, missing affinity is a hypothesis, not a measured cause.
- The verification is not in this record's spend.

## Isolation

- **Key handling.** The key stayed in the proxy. Every summary, ledger and telemetry
  file is free of it and of the session token, which the tests prove on the stand-in.
- **Escape suite.** The sandbox's escape suite passes with the host's tool roots added:
  node, its Homebrew libraries, the host package and Python.
- **Network.** The host reached nothing but the loopback proxy.
- **Requests.** The proxy enforced the allowlist and the pinned provider routing on
  every request.
- **Review.** An independent review of the host, runner and proxy was dispositioned
  before the measured runs:
  - a bring-your-own-key route now settles at OpenRouter's fee plus the upstream charge;
  - only true image blocks earn the per-image reservation;
  - routing is pinned in the proxy;
  - every run starts a fresh knowledge repository and records the version it started from;
  - broad tool roots are refused;
  - a loopback test upstream never receives the key.

## Deviations

- **Hosts.** One controlled host with two models was measured, not two coding-agent
  hosts. This was the owner's decision.
- **Sample.** Opus ran on 5 of the 13 sessions, an owner decision that kept the cap.
- **Sessions the cap stopped.**
  - Terra's last #397 admission (`sd1a7`) started with $1.68 left of its run cap. The
    proxy refused its next request after $0.95 because that request's worst-case
    reservation no longer fitted. It was aborted, with nothing gated.
  - In #372, `aidB9` was stopped the same way (with $1.65 left, after $1.05), and
    `aidA5` did not run.
  - These are cap effects, not host failures. They are counted in the sessions-run
    column and excluded from the sealed column.
- **Pilots.** The first two pilots failed, as shown above. The host changed before any
  measured run, and the pilots' spend is reported separately.
- **Noise.** A connection-reset traceback is printed each time the host closes an idle
  connection to the proxy. It changes no figure.

## Recommendation for P1

- **Host.** Keep the Pi-based host. It ran every session the cap allowed, with no
  isolation incident, and the project controls its tools and budget behaviour.
- **Model.** Start with terra, the actor's own model.
  - On the long lineage it cost about 0.6× the actor's spend, with the same gate pass
    rate as Opus.
  - Opus cost about 1.2× the actor's spend.
  - Neither model's knowledge has been scored against the probes, so this is a cost
    recommendation, not a quality one.
- **Cap.** For a P1 offline replay, cap curator spend at 1× the actor's spend per game
  hour. Fix and verify prompt caching before setting a tighter cap.

## Limitations

- **One lineage of each kind, a small Opus sample, and one session per admission.**
  The figures are development evidence and decide nothing.
- **Lag uses the ledger's routine pace,** not the actor's live wall clock during that
  admission.
- **#397's sessions received no memory store,** and #372's did, so the lineages'
  inputs differ.
- **Prices were frozen once.** The proxy settled at OpenRouter's reported cost, which is
  authoritative for spend.
