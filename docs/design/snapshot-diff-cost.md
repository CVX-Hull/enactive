---
owner: lead
status: active
date: 2026-11-08
scope: 'Offline estimate of the prompt-cache and context cost of delivering curated knowledge as snapshot diffs on observation results (ADR 009 D2; #455)'
review_trigger: A change to the actor's model, route or prices, to the host's context projection, or to how ADR 009 delivers snapshots
---

# Snapshot-diff cost (offline estimate)

ADR 009 delivers curated knowledge to the actor as **diffs appended to observation
results** ([reaching the actor](../decisions/009-curated-player.md#reaching-the-actor-without-latency-d2)).
This page estimates what one diff of D tokens adds to cost and context. It does not
measure any value of a diff to the actor.

**Data.** The sealed #397 host traces (`397-seven-day`, 14 actors). The 1,978
`response-complete` events all have usage and use configured-rate costs, one model
(`openai/gpt-6.1-terra`) and one route. [`tools/diff_cost.py`](../../tools/diff_cost.py)
derives every number below; re-run it with
`python tools/diff_cost.py .runtime/evidence/397-seven-day/computer-sessions`. No model
was called.

**Provenance.** A delegated analysis agent wrote and ran the script. The lead re-ran it
(identical output) and recomputed the totals and prices independently from the raw
events. The agent's draft labelled spend "per decision" when it divided by requests.
This page uses **per request**: $38.40 over 1,978 requests is $0.01941. The run ledger
records 1,915 decisions, which is about $0.0201 per decision.

## Measured

| Quantity | Value |
| --- | --- |
| Prices implied by the cost fields | Input $1.00, cache read $0.05, cache write $1.25, output $5.00 per million tokens. Every request agrees; write is 25× read |
| Spend | $38.40: 72.9% cache writes, 23.8% cache reads, 3.3% output |
| Prompt per request (median / p90) | 93,828 / 197,459 tokens; 83,548 / 191,754 from cache |
| New tokens written per request (median / p90) | 1,528 / 3,155 |
| Large rewrites (cache write above half the prompt, first request excluded) | 8.04% of requests (158 of 1,964; 2–9.7% per actor), carrying **63.5% of spend**. 145 of the 158 coincide with a prompt shorter than the request before, so they look like the host's context pruning rather than provider expiry. The cause is not shown by these fields |
| Prompt growth | About 1,119 tokens per request (median of per-actor slopes), from 4–7k to 72–234k tokens |
| Requests per actor | 50–204, mean 141. A token appended at a random request stays for 81 later requests on average (median 73) |

## Cost of one diff

Assumptions, all stated:
- A diff of D tokens enters on the next request at the write price.
- **(a)** Each later request reads it at the read price. Added cost: `D·(write + R·read)`.
- **(b)** Later requests also rewrite the whole prompt, the diff included, at the
  measured 8.04% rate, independently. Added cost: (a) `+ R·q·D·(write − read)`.

R = 81, against pooled spend per request ($0.01941):

| D (tokens) | (a) | (b) |
| ---: | --- | --- |
| 50 | $0.00027 (1.4%) | $0.00066 (3.4%) |
| 200 | $0.00106 (5.5%) | $0.00262 (13.5%) |
| 500 | $0.00265 (13.7%) | $0.00656 (33.8%) |
| 2,000 | $0.0106 (54.6%) | $0.0262 (135%) |

These are per diff. A diff on every observation multiplies them. After k diffs the
prompt carries k·D more tokens on every request. At D = 500, twenty diffs add 10,000
tokens (11% of the median prompt).

## Recommendation

- **Cap each diff at about 200 tokens.** Allow 500 only as an exception for one
  high-value item.
- **Cap the diff text live in history at about 2,000 tokens**, folding older diffs into
  the next snapshot.
- **Why.** Cost is linear in D and dominated by the one-time write and the rewrite tail,
  not by carrying the diff at the read price. At 2,000 tokens a single diff costs more
  than an average request.
- **Placement.** Keep diffs inside the observation result they arrive with, so the
  host's pruning drops them with that content. That pruning behaviour is not yet
  confirmed from the context-projection code.

## What this cannot show

- **Provider behaviour.** Cache eviction rules, and whether the large rewrites come from
  the host's pruning or the provider.
- **Billing.** Billed rather than configured prices.
- **Tokenisation.** How diff text tokenises. D is counted directly in tokens.
- **Other routes.** The behaviour of other models or routes.

**A paid probe is not needed for the P0 recommendation.** If P1 needs the per-diff
figure more tightly, the analysis proposes one: replay a median prefix of about 94k
tokens, then make 20 requests that each add a 500-token diff, and record cache reads and
writes. That costs about $0.23 per run, or $0.68 for three gap conditions. It needs its
own owner decision.
