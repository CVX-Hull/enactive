---
owner: lead
status: historical
date: '2026-11-12'
scope: 'The worst-case spend reservation of player runs replaced by a dollar limit that the player host enforces from provider-reported cost, on the owner''s decision of 12 November 2026 (#555): the four contract versions, the counting rule, the evidence that archived runs read unchanged, and the supervised run still to be made'
---

# A dollar limit from provider-reported cost, 12 November 2026

On 12 November 2026 the owner decided
([#555](https://github.com/CVX-Hull/enactive/issues/555)) that a player run stops at a
dollar limit it declares, counted from the cost OpenRouter reports for each response,
and that the worst-case reservation and its carried-over totals go. The
[design](../design/provider-reported-spend-limit.md) was reviewed before it was built.
This record holds what replaced what, the contract versions, the counting rule, the
evidence that archived runs still read as before, and the tests. The current rules are
in the [player-host contract](../contracts/player-host.md#spend), the
[campaign procedure](../operations/campaign-run.md#spend-limit) and the
[controls page](../controls.md).

## What replaced what

| Before | After |
| --- | --- |
| The run package declared `accounting`: a worst-case figure for every allowed request, added to a total carried over from earlier packages, and a ceiling. The package was refused unless the sum was declared exactly and fitted the ceiling | The run package declares `spend_limit_usd`, the most the run may count as spent. Nothing is carried over |
| During a run only the request count stopped anything | The player host adds up the cost the provider reports and stops before the next request once the total has reached the limit |
| A response without a cost was counted but not priced | A request with no cost record counts at a fixed bound, and a successful response the host cannot price ends the run |
| The ending reserve had no dollar amount | `ending_reserve.usd`: the driver asks the player to finish when the dollars left fall to it |
| The receipt recorded a reservation and cumulative reservation, with a configured-rate estimate | The receipt records the limit, the reported total, the requests counted at the bound, that bound, the counted spend and whether it is complete |
| A ledger row took its provider cost, unpriced attempts and charge from figures the operator typed in | A ledger row takes them from the receipt |
| The owner's $1,000 was frozen into every package as a worst-case ceiling | The credit limit the owner set on the OpenRouter key, $1,500, is the hard cap, outside the code |

The curator's spend path, the request allowance, the pinned route, the key handling, the
owner's envelopes and the balance check before paid play did not change.

## Contract versions

| Contract | Change |
| --- | --- |
| `campaign-run/5` → `/6` | `accounting` is replaced by `spend_limit_usd`; `ending_reserve` gains `usd` |
| `player-host/3` → `/4`, telemetry 3 → 4 | The route carries `spend_limit_usd` and `unpriced_request_usd`; `host-start` records both; `response-complete` carries `counted_cost_usd`, `cost_counted_as` and `spent_usd`; `settled` carries `spent_usd` and `unpriced_requests`; stop reasons `spend-limit` and `cost-unreported` are new |
| `player-driver/3` → `/4` | Each actor carries `allocated_usd`, `reported_usd`, `unpriced_requests`, `spent_usd` and `spend_complete`; the totals carry `reported_usd`, `unpriced_requests`, `unpriced_request_usd`, `spent_usd` and `spend_complete`; the ending request carries `spend_remaining_usd` and may have trigger `spend` |
| `campaign-receipt/3` → `/4` | `accounting` is `spend_limit_usd`, `reported_usd`, `unpriced_requests`, `unpriced_request_usd`, `spent_usd`, `attempts_charged`, `allocated_max_attempts` and `spend_complete` |
| `dev-run/1` | Unchanged: same fields, same meaning. `record` fills the spend fields from the receipt and no longer takes them as arguments |
| `evaluation-record/1` | Unchanged. The dollar metric stays the configured-rate estimate; `run_facts.spend_allowance_usd` of a `/6` run is its declared limit |

Dollar amounts in the package, the route, the trace's counting fields, the driver record
and the receipt are plain decimal text. A JSON number is refused where one is declared.
A declared amount has at most twelve whole and eighteen fractional digits; a counted
amount in a trace has no cap, because the host writes the provider's own digits.

The live path reads only the current versions: `tools/campaign_package.py`,
`tools/campaign_player.py`, `tools/campaign_run.py`, `tools/campaign_supervision.py` and
`tools/run_ledger.py` refuse the versions these replaced. The evaluator reads them only
through the closed archive index.

`configured_estimate_usd` and `missing_usage_attempts` stay in the driver record, beside
the counted spend and outside the receipt's `accounting`. They are an estimate from the
route's configured rates, which `host-summary` reads and which gives the ratio of
estimate to reported cost for a run.

## The counting rule

- **The bound.** `unpriced_request_usd` is
  `(contextWindow × max(input, cacheRead, cacheWrite) + maxTokens × output) / 1e6` from
  the route's configured rates. `tools/campaign_package.py` computes it and refuses a
  package whose route states another value, whose bound is zero, or whose dollar
  reserve is below the bound. The host and the driver take it from the route.
- **Per HTTP attempt, once.** A response whose `reported_cost_usd` is not null counts at
  that amount. Every other attempt counts at the bound: a refusal, a timeout, a stream
  cut off, an abort at a deadline, a successful response with no usable cost. A retry
  is a separate attempt.
- **Reported cost** on a route that is not on the caller's own provider key is the
  larger of `cost` and `cost_details.upstream_inference_cost`, unchanged from the
  [reported-cost change](2026-11-12-provider-cost-pilot-555.md).
- **Stops.** Before each attempt, a retry included, the host stops with `spend-limit`
  when the total has reached the limit. After a successful response with a null
  reported cost it stops with `cost-unreported`.
- **Overshoot.** One request can be in flight when the limit is reached, so a run
  passes its limit by at most what one request counts.
- **The driver** counts per `request-start` from the trace: the amount on that
  attempt's cost record, else the bound. It gives each new actor the limit minus what
  is counted, starts none when nothing remains, and when a trace cannot be read to its
  settlement, or the host's own totals in `settled` differ from the driver's sums, it
  records the spend as incomplete and starts no further actor.
- **Exact sums.** The host sums integers scaled from the provider's digits; the driver
  and the custodian use `Decimal` on the trace's strings in a context that raises
  instead of rounding.

A worked example, from
`test_the_dollar_limit_refuses_the_next_request_and_the_receipt_totals_follow_the_trace`
(the real host against a scripted provider): a limit of $0.01 and responses reporting
$0.004 each. The total is $0.004, $0.008 and then $0.012, so the fourth request is
never sent and the host settles with `spend-limit` after three requests. The receipt's
`accounting` is `spend_limit_usd` 0.01, `reported_usd` 0.012, `unpriced_requests` 0,
`unpriced_request_usd` 0.25, `spent_usd` 0.012, `attempts_charged` 3 and
`spend_complete` true. The overshoot is $0.002, less than one response.

## Archived runs

All 54 sessions of the [closed archive index](2026-11-12-closed-archive-index.md) carry
the manifest, receipt, driver and host versions this change replaced, so all 54 are now
archive reads. The index file did not change: it already named all six versions for each
session. `ARCHIVE_COMBINATIONS` in `harness/evaluation/core/sources.py` gained the field
lists for the receipt, the driver record, the host trace and the `campaign-run/5`
manifest. `read_end_facts` reads an older receipt and driver record only for a listed
session and takes only the listed fields; `iter_host` reads an older trace only with the
session's index entry and only when its `host-start` names that session.
`tools/host_analysis.py` finds the entry from the manifest of the run directory a trace
sits in.

Each comparison ran on `origin/main` (`7798715`) and on this change, against the same
sealed store.

- **What the evaluator writes.** `pipeline.evaluate` with the CDDA binding and a fixed
  creation time on all 54 indexed sessions, hashing every row of every table of the
  evaluation record. All 53 records are identical, with the same labels in `run_facts`;
  `lh4a1` fails with the same sealed-database error before and after.
- **What the reader returns.** `sources.read_run` with input digests on all 73 campaign
  directories of the store, plus `read_manifest` and `read_end_facts` on their own. All
  53 successful reads are identical. Of the 20 refusals, 5 are identical; 13
  `campaign-run/3` refusals differ only in the message's list of versions, which now
  ends with `campaign-run/6`; and the two unlisted `campaign-run/5` directories that
  hold a manifest and nothing else (`lh0a2`, `lh1a1-build1`) are now refused at the
  manifest, as not listed, instead of at the missing session database.
- **What host-summary reports.** `host_summary` on all 54 indexed sessions. 24 are
  identical. For the 30 sessions with a `campaign-run/4` manifest, `manifest.json` is
  now reported as recorded, with its session and source commit, where it was
  `unsupported_version`: host-summary follows the index, which lists that version for
  them. Nothing else in any summary differs.

The store was not written: it held 54,491 files before and after.

## Tests

The player-host Node suite went from 230 to 235 tests, all passing. The Python suite
went from 1,044 to 1,097 tests, all passing with the sealed store present. Both counts
include the tests added after the review below.

- **Host** (`tools/player_host/test/reported-cost.test.mjs`, `route-configuration.test.mjs`):
  the limit stops the host before the next request, and before a retry; the overshoot is
  at most one request; the total is exact where a floating-point sum would let one more
  request through (0.1 + 0.7 against a limit of 0.8); a successful response with no
  usable cost stops with `cost-unreported` whether or not token counts arrived, and a
  cost without token counts does not; a refused request and a request aborted at its
  deadline each count once at the bound; a cost of 19 or 23 fractional digits is written
  and summed as plain decimal text; the route's two amounts are refused as numbers, and
  a bound of zero is refused.
- **Contract** (`tests/test_player_host_contract.py`): the worked example above, and a
  successful unpriced response counted at the bound by the driver's reader.
- **Driver** (`tests/test_campaign_player.py`): a request that left no cost record
  counts at the bound and leaves the spend incomplete; a cost record the driver cannot
  count, host totals that differ from the driver's sums, or a trace that cannot be
  read to its end, marks the spend incomplete and starts no successor; costs of 19 and
  23 fractional digits are read and summed exactly; a successor's route carries the
  remaining dollars, cut to the digits a route may carry; no successor starts when none
  remain; the dollar reserve sends the orderly stop with trigger `spend`.
- **Package and receipt** (`tests/test_campaign_run.py`): `campaign-run/5` and
  `player-host/3` are refused; a missing, zero, negative, non-finite or numeric limit is
  refused; a reserve that is not below the limit, or is below the bound, is refused; a
  zero bound is refused; the route must repeat the limit and carry the computed bound;
  the receipt's `spent_usd` is reported cost plus unpriced requests at the bound.
- **Ledger** (`tests/test_run_ledger.py`): a row from a `/4` receipt satisfies the
  ledger's identity; an inconsistent receipt gets no row; an incomplete receipt is
  refused by default and recorded only as its upper bound with the flag, which a
  complete receipt refuses; older package and receipt versions are refused; the
  figures cannot be typed in.
- **Evaluator** (`tests/test_evaluation_core.py`, `tests/test_host_analysis.py`,
  `tests/test_viewer_api.py`): one session of each combination is read in the versions
  the index lists, with the archived spend allowance; the same files under an unlisted
  session, a trace naming another session, and each old version beside a current run are
  refused; a `/6` run's allowance is its declared limit; the index pin and the
  sealed-store check pass.

## Independent review

An independent review of the change found the money path correct and failing closed, and
asked for the following. Each was resolved in the same pull request.

| Finding | Resolution |
| --- | --- |
| The host writes a reported cost with as many digits as the provider gave, but the driver refused more than eighteen fractional digits, so a legal cost such as `0.0034500000000000004` would have made a healthy run's trace unreadable | The driver reads a counted amount in a trace at any length and sums without rounding; declared amounts keep the cap. What a successor is given is cut down to eighteen fractional digits. Tests: 19- and 23-digit costs in the driver and the host, and a successor's limit after a 19-digit cost |
| A receipt with incomplete spend could not be recorded in the ledger at all | Owner decision of 12 November 2026 (#555): record its upper bound. `run_ledger record --record-upper-bound` records the declared limit plus one request's bound; without the flag the receipt is still refused, and the flag is refused for a complete receipt. A `dev-run/1` row has no field to mark it, so the run's dated record does, with the key's activity figure for the run's time window; no further run of the study is admitted before then |
| Current pages still described reservations, a cumulative ceiling or telemetry version 3 | The migration standard, operator permissions, the host reference, the documentation standard's example, the development workflow, two component pages and the spectator's spend wording now describe the limit |
| The `request-unpriced` event could not be reached by any path and was untested | Removed from the host, the driver, the contract and the host reference. Every attempt ends in a `response-complete`; a started request with no cost record, which only a killed host leaves, still counts at the bound in the driver and leaves the spend incomplete |
| A dollar reserve below one request's bound would let a single failed request end a run abruptly | The package check refuses `ending_reserve.usd` below `unpriced_request_usd`, naming both |
| A route with zero rates would count failed requests as free | The host's route validation and the package check both require the bound above zero |
| Nothing compared the host's own totals with the driver's | The driver requires `settled.spent_usd` and `settled.unpriced_requests` to equal its own sums; a difference leaves the spend incomplete |
| The controls page said a run passes its limit by at most the bound | It now says by at most what one request counts: a reported cost is not capped by the bound |

## Supervised run with a declared limit

Pending the owner's approval to spend. One short supervised run with a small declared
limit is to show:

- the dollar limit binding before the request allowance;
- the run ending in order through the dollar reserve;
- an overshoot of at most one request;
- the receipt's total equal to the sum in the trace;
- the ratio of estimate to reported cost;
- no further actor started;
- the evaluator reading the new run and one archived session of each combination.
