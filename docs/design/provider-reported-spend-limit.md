---
owner: lead
status: historical
date: '2026-11-12'
scope: 'Design rationale, as reviewed before it was built, for the dollar limit on player runs from provider-reported cost and the closed archive index (#555); the campaign procedure and the player-host and evaluation contracts describe the running system'
---

# A dollar limit from provider-reported cost

**Status: built, 12 November 2026.** This page is the design as reviewed before it was built; the [campaign procedure](../operations/campaign-run.md) and the [player-host contract](../contracts/player-host.md) describe the running system. The
issue on how spend is capped, [#555](https://github.com/CVX-Hull/enactive/issues/555),
owns this proposal and records the owner's decisions that set its direction.

## Problem

Overspending is a High risk ([R-OVERSPEND](../risks.md#operating-risks)). For player
runs, what is in place does not look at money while a run is going:

- **Before launch,** the run package must contain a worst-case figure: the context
  window at the most expensive input rate, plus the output limit, for every allowed
  request, added to a total carried over from earlier packages. The package is refused
  unless that sum is declared exactly and sits under a ceiling.
- **During the run,** only the request count stops anything.
- **Afterwards,** the receipt records an estimate from the route's configured rates,
  not what OpenRouter charged.

The worst-case figure has been more than a hundred times the estimate (40 requests:
$16.38 reserved against $0.11, in the
[supervised launch check](../acceptance/2026-11-12-supervised-launch-check-558.md)), so
it bounds nothing a person would recognise as a budget, and its carried-over total has
to be maintained by hand. The account balance is not a cap either, because automatic
top-up is on.

The curator already works the other way: its proxy settles each request on the cost
OpenRouter reports and stops the session at its cap. This proposal brings player runs
to the same footing.

## Owner decisions

Taken on 12 November 2026 and recorded on #555:

1. The owner sets a credit limit on the OpenRouter key. That is the hard cap, outside
   the code.
2. The player host reads the cost OpenRouter reports for each response, adds it up, and
   stops the run at the dollar limit the run declares. A response with no usable cost
   stops the run. The pre-launch arithmetic and its carried-over totals go.
3. Sealed runs stay readable through one closed index of exactly the 54 sealed sessions
   the evaluator can read today, replacing the two separate archive lists.
4. A few real requests may be sent on the player route to see what OpenRouter reports,
   about five cents in total.

## Design

### What a run declares

The run package's `accounting` block is replaced by one number, `spend_limit_usd`: the
most this run may spend. The request allowance (`max_http_attempts`) stays as a
mechanical bound. Nothing is carried over from earlier packages.

### What counts toward the limit

- **A response with a reported cost** counts at that cost. On a route that uses the
  caller's own provider key, the cost is the fee plus the upstream inference cost, the
  rule the curator's cost reading already applies. The two hosts are written in
  different languages and cannot share code, so they share one file of usage records
  and expected costs that both test suites run.
- **A request with no cost record** counts at a fixed bound: the context window at the
  route's most expensive input rate plus the output limit. This covers a request that
  fails, times out, is cut off mid-stream or is aborted at a deadline, any of which the
  provider may still bill. It is the same per-request figure the reservation uses today,
  applied only where the cost is unknown. In the sealed history that was 11 of 11,088
  requests.
- Amounts are summed as decimal strings, not floating-point numbers.

### When the host stops

- **At the limit.** Before each request the host stops with reason `spend-limit` if the
  total has reached the limit. One request can be in flight when the limit is reached,
  so a run can exceed its limit by at most one request's bound.
- **On a successful response with no usable cost,** or with a malformed one, the host
  stops with reason `cost-unreported`. A run never continues on a response it cannot
  price. Sealed history has no successful response without a usage record, so this
  should be rare if cost arrives with usage; the pilot below settles that.
- **Before the limit, in an orderly way.** The ending reserve gains a dollar amount
  beside its request count. When the dollars left fall to that reserve, the driver asks
  the player to finish, as it does today when requests run low, so a run normally ends
  with a report and not abruptly.

Each response record in the host trace carries the reported cost and says its source is
the provider. The configured-rate figure stays, named as an estimate.

### What the driver and custodian do

- The driver adds up the counted cost across actors and gives each new actor what
  remains. If an actor's trace cannot be read, the run's spend is unknown: the driver
  records that and starts no further actor.
- The receipt's `accounting` block records the limit, the reported total, the number of
  requests counted at the bound and that bound, the requests charged against the
  allowance, and whether the accounting is complete. The cumulative totals are gone.

### What reads these records

- **The run ledger** keeps its schema and its meaning. A row's spend is still reported
  spend plus the unpriced requests at their per-request bound, now read from the receipt
  with no figures entered by hand. The envelope arithmetic in `tools/run_ledger.py`
  therefore keeps working unchanged.
- **The evaluator** keeps its dollar metric as the configured-rate estimate, which is
  the only figure every run, old and new, carries. Its spend allowance for a new run is
  the declared limit. Reported cost is not added to evaluation records in this change,
  so the evaluation record keeps its version.
- **The spectator's** "spend inside allowance" advice follows from the allowance; it
  informs and gates nothing, as now.
- **[Operator permissions](../operator-permissions.md)** keeps the owner's envelope
  rule. The text that freezes $1,000 into every package as a worst-case ceiling goes,
  and the page states that the key's credit limit is the hard cap.
- **The balance check before paid play stays.** It guards against refusals in flight,
  which a tight key limit could also cause.

### Contract versions

One current contract per boundary, changed together
([S-MIGRATION](../standards/migration.md)):

| Contract | Change |
| --- | --- |
| `campaign-run/5` → `/6` | `accounting` replaced by `spend_limit_usd`; the ending reserve gains a dollar amount |
| `campaign-receipt/3` → `/4` | `accounting` records the limit, reported spend and bound-counted requests |
| `player-driver/3` → `/4` | totals carry the counted spend and completeness |
| `player-host/3` → `/4`, with its telemetry version | the route carries the dollar limit; response records carry reported cost; two new stop reasons |
| `dev-run/1` (ledger) | unchanged: same fields, same meaning |
| `evaluation-record/1` | unchanged: the dollar metric stays the configured estimate |

### The closed archive index

The sealed store holds 60 campaign sessions. The evaluator can read 54 of them today:
30 through the list of older development-loop sessions, 22 through the list added with
the attention-policy change, and 2 as current. All 54 carry the receipt, driver and
host versions this change replaces, so all 54 become archive reads.

The two lists become one closed index, `data/evaluation/archive-sessions.json`:

- It has exactly those 54 sessions. Each entry gives the session, its study and run
  directory, the versions of its manifest, receipt, driver, host trace and run-ending
  record, and the operator labels the older list holds today.
- Only the three version combinations that exist are accepted, and for each the reader
  takes a fixed, listed set of fields. An old version on any session not in the index
  stays an error naming the file and the version.
- A test pins the index to those 54 sessions and those three combinations, and checks
  it against the sealed store wherever the store is present.
- The index is closed and never grows. Adding a session is a new owner decision,
  recorded in the migration standard, which is reworded to say so.
- The six sealed sessions the evaluator cannot read today stay unreadable.
- Tools that read host traces through the evaluator's reader follow the index
  (`tools/host_analysis.py`). Tools that act on a live run read only the current
  versions (`tools/run_ledger.py`, `tools/campaign_supervision.py`,
  `tools/campaign_player.py`).

## Risks and what guards them

| Risk | Guard |
| --- | --- |
| OpenRouter does not report cost on the player route's streamed responses. The library the host uses asks for usage in the stream but discards any cost field, and no sealed response shows one | The pilot below, before anything else is built. If cost is not reported, with or without the request option OpenRouter documents for it, the proposal stops there |
| A request in flight overshoots the limit | Bounded by one request's fixed bound, stated in the contract; the key's credit limit is the hard cap |
| A failed request is billed although it reported no cost | It is counted at the fixed bound, never as free |
| Stopping on an unreported cost ends healthy runs | The pilot shows whether cost arrives with every usage record; the stop reason is distinct, so its frequency is visible in receipts |
| A provider under-reports | Out of the project's hands; reported spend is what the provider says, and receipts say so |
| The key limit is not set, or is raised | The code cannot see it. The controls page states it as an owner-kept control with that gap |
| The archive index becomes a general compatibility layer | It is fixed at 54 sessions and three combinations, pinned by a test, with listed fields per version; the standard says it never grows without the owner |

## What does not change

- The curator's spend path. Its per-request reservation is a runtime bound that already
  settles on reported cost. One known cost remains there: a failed request is charged
  its whole reservation, which once ended a session early
  ([cost-guard record](../acceptance/2026-11-11-p1-cost-guard-178.md)). It can be
  decided separately.
- The request allowance, the pinned route with no fallback, and how the key is handled.
- The owner's spending envelopes and the rule for admitting a run inside one.

## Alternatives considered

- **Record reported cost but add no dollar stop.** Smaller, and the key limit would
  still cap spend, but a run's declared budget would remain a number nothing enforces.
  The owner chose the stop.
- **Count a request with no cost record as free.** Simpler, but it would loosen the
  envelope arithmetic without saying so, and a cut-off stream on a large context can be
  billed.
- **Price a cut-off request from OpenRouter's record of that generation afterwards.**
  More exact, but it needs a second call per failed request and a new failure path.
- **Enforce the limit in the driver instead of the host.** The driver sees the trace
  only after the host writes it; the host is where the next request is decided.
- **Keep the reservation and loosen it.** Any formula from configured rates stays a
  guess about a cost the provider reports exactly.
- **One archive list per contract change.** It is what exists; it grows without end and
  each list needs its own reader branch.

## Delivery

Three pull requests, each leaving main coherent, after one pilot:

1. **Pilot.** Up to six small requests on the pinned player route: a plain reply, a
   tool call, and a repeated prompt to see cache pricing. The raw usage record is
   captured where the host reads each stream chunk, with and, if needed, without the
   request option OpenRouter documents for usage accounting. A dated record states what
   the records contained and whether the route uses the caller's own provider key.
   **If cost is not reported, the work stops here** and this page records why.
2. **Reported cost in the trace.** The host records reported cost on each response as
   an evidence-only addition under the current telemetry version, which the migration
   standard allows because no control reads it yet.
3. **The archive index.** A restructure with no behaviour change: the two lists become
   the one index, and the evaluator still reads exactly the sessions it reads today.
4. **The limit.** The four contract changes, the stops, the ending reserve's dollar
   amount, every reader, the documents and the tests. It needs an independent review
   before merge, because it changes persisted contracts and a spend control. The
   controls page and the register change with it: C-SPEND describes the dollar limit
   and the key limit, with their gaps.

Then one short supervised run with a small declared limit, which spends real credit and
needs the owner's approval when it is ready. It should show the dollar limit binding
before the request allowance; the run ending in order through the dollar reserve; an
overshoot of at most one request; the receipt's total equal to the sum in the trace;
the ratio of estimate to reported cost; no further actor started; and the evaluator
reading the new run and one archived session of each combination.
