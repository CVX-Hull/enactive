---
owner: lead
status: historical
date: '2026-11-19'
kind: review
scope: 'Offline timing of a pre-output server refusal whose provider delay outlasts the request deadline, and three ways to handle it'
---

# The request deadline during a server-directed backoff (#805)

## At a glance

In the #803 reload, request 32 received HTTP 502 about 34 seconds into a 60-second
request deadline and the provider asked for a 60-second wait. The host reproduced
offline on a controlled clock does what the contract says: the original timer fires
26 seconds later, during the wait, and the actor stops with `request-timeout`. No
second request is sent and no tool call runs. The same shared timer also leaves a
second attempt only the time the first one left unused, even when the wait fits.

Three behaviours were compared: keep the current one, skip a wait that cannot fit,
or honour the full delay inside the remaining actor and custody time. Skipping the
wait changes nothing but the moment of the stop: 34 seconds instead of 60, the same
unsaved state, no extra attempt and no extra charge. Honouring the delay is the only
choice that can avoid the unsaved stop. On this timing the request would run until
94 to 154 seconds instead of ending at 60, with one more provider attempt, and it needs
five points the current code does not settle: the SDK's own timeout, the ending control,
a floor for the second attempt, a once-per-actor bound and the ending reserve. The evidence is one
observed refusal and no measurement of whether a provider answers after such a wait.
It supports skipping the wait if an earlier, equally unsaved stop is wanted. It does
not yet support honouring the delay. The lead decides.
[Backoff review #805](https://github.com/CVX-Hull/enactive/issues/805) · [Observed run #803](2026-11-19-joanna-campground-memory-803.md)

## What was measured and what was derived

**Measured** means run against the unchanged [player host](../../tools/player_host/host.mjs)
in [the new test file](../../tools/player_host/test/backoff-request-deadline.test.mjs).
Its clock replaces `setTimeout` only. Each advance lands on a stated instant and each
boundary is shown from both sides (one millisecond before, nothing; at the instant, the
event). No test sleeps through the controlled stretch. The route has a 60-second request
deadline and the host a large allowance unless stated. Times are in controlled seconds
from the start of logical request 1.

| Fixture | What the current host did |
| --- | --- |
| 502 at 34 s, `Retry-After: 60` | Refusal marked eligible at 34 s with requested delay 60 000 ms. Nothing happened at 59.999 s. The original timer fired at 60 s: `abort` reason `request-timeout`. One request, one payload, no `provider-retry` start, no tool call. Advancing past 94 s, where the wait would have ended, sent nothing. Request 1 stayed counted as one unpriced attempt. |
| Same, with an orderly stop accepted at 40 s | The stop did not interrupt the wait. The timer still decided at 60 s with `request-timeout`. The player never answered the stop. |
| Same, host allowance 50 s | Work stopped at 49 s with `host-timeout`, 15 s after the refusal, before the request timer. One request, no second fetch. |
| 502 at 34 s, `Retry-After: 20`, instant reply | Nothing sent at 53.999 s. Second request at 54 s with a byte-identical body. It completed under the shared timer: two requests, one unpriced and one priced at the provider-reported cost. |
| Same, second reply needing 10 s | Second request at 54 s, aborted by the original timer at 60 s with `request-timeout`: only the 6 s the first attempt left. Two requests, both unpriced, no tool call. |

Existing tests already show the neighbouring facts: cancellation interrupts a backoff
([retry-deadlines](../../tools/player_host/test/retry-deadlines.test.mjs)), and a delay over
60 seconds is refused by the SDK retry helper at once with `provider-error`
([server-error-retry](../../tools/player_host/test/server-error-retry.test.mjs)). So today a 61-second
delay ends the run at the refusal, and a 60-second delay ends it only when the timer fires.

**Derived** means worked out from the measured timings and from reading the code, not run
in the repository. The arithmetic was also run once on a scratch copy of the host outside
the repository with the smallest change applied. That copy is not committed and is not
acceptance evidence.

**Unknown** is listed at the end.

The host receives the smaller of the actor allowance and the custody deadline less
30 seconds as `--timeout-seconds` ([driver](../../tools/campaign_player.py)). One host
allowance therefore stands for both limits. The driver also stops the host from outside at
`min(deadline − 30 s, started + seconds)`.

## The three behaviours on the #803 timing

Refusal at 34 s, delay 60 s, request deadline 60 s, generous allowance.

| | Current | Skip a wait that cannot fit | Honour the full delay within the remaining limits |
| --- | --- | --- | --- |
| Basis | Measured | Derived, cross-checked on the scratch copy | Derived, cross-checked on the scratch copy |
| Stop or second fetch | `request-timeout` at 60 s | `provider-error` at 34 s, the stop an over-cap delay already gets | Second fetch at 94 s, never earlier; fresh deadline of at most 60 s for it |
| Provider attempts | 1 | 1 | 2 |
| Time the actor waits | 26 s of dead time after the refusal | None | 60 s wait, then up to 60 s for the second attempt: the request ends between 94 s and 154 s. Worst case over any refusal time is about 180 s (refusal at 59.9 s) against a current worst case of 60 s |
| Tool call | None | None | One only if the second attempt completes. A tool call in a cut-off stream cannot reach MCP, as for the existing stream recovery |
| Actor or custody limit | Never crossed | Never crossed | Crossed unless guarded. With a 50 s allowance the delay cannot fit (15 s left at the refusal), so it must fall back to the skip stop at 34 s |
| Unpriced attempts | 1 | 1 | 1, plus a second only if it ends without a usable cost |
| Extra charge | None | None | At most one attempt: the provider-reported cost of one inference if it completes, else the route's `unpriced_request_usd` bound. See below |
| Outcome for the run | Unsaved stop, no successor | Unsaved stop, no successor, earlier | The run continues if the provider answers; unsaved stop if it does not |
| Properties at risk | None | Stop reason differs; text in the contract and adapter reference that says the original deadline covers the backoff changes | Boundaries, stop propagation, the ending, the SDK timeout (below) |

**Charge.** The contract counts every started attempt. A reported cost counts at that
cost and any other attempt counts at the route's bound `unpriced_request_usd`
([counting rule](2026-11-12-provider-reported-spend-limit.md#the-counting-rule)). The
bound is $0.4096 for the route described in [development runs](../development-runs.md);
the files read do not show whether the #803 route used the same bound. The ledger
([runs.jsonl](../../data/evaluation/runs.jsonl)) records $310.08 of provider spend over
32,135 attempts in its 158 rows, about $0.0096 per recorded attempt. The two #803
admissions show about $0.0074 and $0.0027. The ledger may count recall attempts too,
so these are indications, not a price. The 502 attempt itself has an unknown charge in
every behaviour. The reload row records one unpriced attempt and no bound.

**Cannot fit the remaining actor or custody time.** With a 50 s allowance the host stops
at 49 s (measured). A host that honours the delay must first compare the wait plus a
minimum for the second attempt with the time left before work stops. If it does not fit,
behaviour 3 becomes behaviour 2 at the refusal. On the scratch copy a 50 s allowance
stopped at 34 s with one attempt, as did a 100 s allowance with a 5 s floor (65 s needed,
about 64.7 s left). A 105 s allowance honoured the wait and gave the second attempt about
6.5 s, which a 10 s reply missed. The floor decides whether such a squeezed attempt is
worth its charge.

## The smallest change for each

All paths are read-only here and none was edited. Neither change touches the request body.

- **Skip.** In `retry()` of [host.mjs](../../tools/player_host/host.mjs), after the
  `eligible` event, read `retryDiagnostic(headers).requested_retry_delay_ms`. If it is finite
  and not shorter than `min(timeoutMs, totalMs) − (performance.now() − streamStarted)`, call
  `stop('provider-error')` and `throw new HostError(fatal)`, the exit the SDK helper's over-cap
  refusal already takes. About five lines, one test, and the sentence in the
  [contract](../contracts/player-host.md#route-envelope) and [adapter reference](../../tools/player_host/README.md)
  that says the original request deadline covers the backoff.
- **Honour.** In the same place, when the wait plus a floor fits
  `totalMs − cleanupBudget − (performance.now() − started)`, `clearTimeout(requestTimer)` and
  mark the request suspended. At the start of the next `observedFetch` attempt, re-arm
  `requestTimer` with `min(timeoutMs, work time left)` and reset `streamStarted`. Refuse the
  attempt if a control was accepted, as the stream recovery already does. Also stop passing the
  request deadline as the SDK's own `timeoutMs` (line 1183 of `host.mjs`): the OpenAI client arms
  `setTimeout(abort, timeoutMs)` around the whole `observedFetch` call, backoff included, and passes
  that controller's signal to every attempt. On the scratch copy the second attempt at 94 s
  received an already aborted `init.signal` (`sdk_signal_aborted: true`) and ended with
  `provider-error`. With the SDK timeout lifted it was dispatched at 94 s, completed at 104 s on a
  10 s reply, and counted one unpriced and one priced attempt. Roughly twenty lines, tests for
  every row above, and a contract change from "the original request deadline covers the backoff"
  to a bounded second deadline.

**Fixture gap.** The existing fixtures control `setTimeout` only. A change that computes time
left reads `performance.now()`, so its tests also need that clock driven from the same counter
(`t.mock.method(performance, 'now', …)` worked on the scratch copy), and a fixture that
inspects `init.signal` to see the SDK's abort. Neither is in the repository's fixtures today.
The measured part of this record needed neither.

## Preserved properties under honouring the delay

| Property | Standing |
| --- | --- |
| Identical logical request body | The retry resends the SDK's serialized body (measured for a 20 s delay: byte-identical). Unchanged by either alternative |
| At most two provider attempts | `maxRetries: 1` is unchanged |
| Ordinary accounting, unpriced attempts included | Each started attempt gets a `response-complete` (measured). The second attempt needs the existing `canSpend` check at its start. The ending-reserve check (`recoveryHasHeadroom`) is applied to the stream recovery only, not to this retry, so a decision is needed |
| Original actor, custody and spend boundaries | At risk. Needs the time-left comparison above, with the host allowance standing for the actor and custody limits |
| Ending control and stop propagation | At risk. Measured today: an accepted stop waits for the 60 s timer. On the scratch copy it waited for 94 s and no request was sent. Cancellation interrupts the wait now (existing test). Whether an accepted control should end the wait at once is a decision |
| Exactly-once dispatch of completed tool calls | Safe by construction: attempt 1 produced no output and only a completed reply from attempt 2 reaches the agent. Not tested beyond the existing partial-stream tests |

## The unsaved-stop tradeoff of keeping the current contract

A refusal whose requested delay is not shorter than the time left on the request deadline
ends the actor. The host settles `ok:false`, and the [driver](../../tools/campaign_player.py) ends the admission with "Deciding
host ended unsuccessfully" and admits no successor. In #803 the stop left no new named Save,
the remaining reloads were ineligible and the unused authority expired. The player is not running
during the wait, so even the 26 seconds before the stop could not have been used to save.

For a 60-second delay every refusal in the request is cut off, because the delay equals the
deadline. For a delay *d* the cut-off window is a refusal later than 60 − *d* seconds into the
request, and in that window the second attempt, if the wait fits, has only the time left
(measured: 6 s of 60 s).
Keeping the contract buys a hard bound: no logical request runs past its original deadline,
at most one extra attempt is ever admitted and the spend and ending behaviour stay as
documented. It costs the run, not just time, whenever a provider asks for a long wait.

## Does the evidence support a change?

- **Skipping the wait.** Supported only as an earlier stop. It removes 26 s of dead wait in the
  observed case, makes a 60-second delay behave like the over-cap delay that already fails at the
  refusal, adds no attempt and no charge, and keeps every boundary. It does not avoid the unsaved
  stop. Readers that key on the stop reason (`request-timeout` becoming `provider-error`) were not
  checked.
- **Honouring the delay.** Not supported by this evidence. It is the only behaviour that can keep a
  run alive, but the benefit depends on the provider answering after the wait, which is not
  measured, and one observed refusal gives no rate. The cost is certain: the request runs until 94 to
  154 seconds instead of ending at 60, one more attempt is exposed at its bound and the contract changes.
- **Recommendation.** Keep the current contract unless the owner wants the earlier stop, in which
  case adopt the skip. If the owner's priority is to avoid unsaved stops, evaluate the honouring
  form only with these limits: once per actor (as the stream recovery), only when the wait plus a
  floor fits the host allowance, a control or cancellation ends the wait, the SDK timeout lifted
  and the ending-reserve check applied. Collect a second observed refusal first if the delay and
  the provider's behaviour after it matter to the decision.

## Unknown

- How a provider behaves when a request is resent after a 60-second wait, and how often the
  second attempt succeeds.
- How often a refusal of this class occurs. The ledger shows 45 unpriced player attempts in
  32,135 recorded attempts across all causes (refusals, timeouts, cutoffs), with no cause split.
  #803 supplies one refusal with a delay longer than the time left.
- Whether a real `fetch` with an already aborted signal fails at the second attempt as the
  scratch copy's flag shows. The fixtures ignore the signal. No network request was made.
- The charge of the 502 attempt, and the #803 route's own `unpriced_request_usd`.
- Whether the provider's 60-second delay is typical for this status. Pi's retry helper caps it at
  exactly 60 seconds, so a larger value would already end the run.
- Whether readers of the stop reason in the driver and evaluation code would accept
  `provider-error` for the skip stop.

## What was run

`npm --prefix tools/player_host test` includes the new file (five tests) and the 293 existing
tests. The scratch prototypes were run from a copy of the host outside the repository and are
not part of the suite. No provider key, request, payment or game was used.
