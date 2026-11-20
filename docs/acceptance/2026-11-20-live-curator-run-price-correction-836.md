---
owner: lead
status: historical
kind: review
date: '2026-11-20'
scope: 'Corrections to the price proposal for one live curator run, from a review of the merged text (#836)'
---

# Corrections to the price proposal for one live curator run (#836)

## At a glance

A review of the merged [price proposal](2026-11-20-live-curator-run-price-proposal-836.md)
found five things wrong in it. That record is left as it merged. This one states the
corrections, and where the two differ, this one holds.

The largest: the proposal's ceiling of $10.00 gave the curator a cap of $6.00, which is
too little for its proxy to reserve a request. The corrected ceiling is **$18.00**, of
which the forecast spend is unchanged at about $3.50. Nothing here is approved.

No game, no model request, $0 spent. The proposal's inputs and its simulation table are
not changed.
[Price proposal](2026-11-20-live-curator-run-price-proposal-836.md) · [Session price pilot](2026-11-13-session-price-pilot.md) · [Live integration design](../design/live-curator-integration.md)

## The corrections

### The curator's cap, and so the ceiling

The proposal gave the curator a run cap of $6.00 "with a cap for each session". The
curator's proxy reserves a request's estimated worst case before forwarding it, and each
session is given the lesser of its own cap and what remains of the run's
(`tools/curator_host/shadow.py`). The pilot raised its session cap to $8.00 because
$6.00 "would have let the proxy refuse before the host's writing-only phase". Under a
$6.00 run cap even the first session would have had too little.

| Part | Forecast | Planning limit |
| --- | --- | --- |
| Play, one admission | $1.49 | $3.00, the package's limit |
| Curator, ten sessions | $2.00 at the pilot's median | **$14.00** for the run, **$8.00** for a session |
| Not allocated | | $1.00 |
| **Total** | **about $3.50** | **$18.00** |

For the tenth session still to have $8.00 after nine at the pilot's largest displayed
cost, $0.57, the run's cap must be at least $13.13. Charges that large would total
$5.70; the rest is headroom to reserve, not money expected to be spent. As the proposal
says of its own figure, this is a planning ceiling and not a hard cap.

### What stops the player's side

The proposal said the player host stops the admission on a successful response with no
usable cost and on its time and mechanical ceilings. More exactly:

- a successful **player** response with no usable cost stops the host;
- a successful **recall** response with no usable cost ends recall for that actor, and
  the player continues;
- the host enforces the timeout it was given for its actor; the driver and the runtime
  enforce the admission's deadline and its mechanical limits.

### The pacing forecast

The proposal said a median session would end before the next window fills, from 156
seconds for 20 decisions. The run's trigger counts an actor's finished computer
operations, not decisions, and polling and staging a snapshot add time before a session
starts. The pilot found operations and decisions close to one to one in its own
admission only. The forecast of timing, and of ten sessions, holds only if that relation
holds and the added time is small. The run reports the operation rate itself.

### The order of the outcome table, and two rows

- A snapshot that fails or passes its time bound is reported **before** an early stop,
  and even when the run also stopped early, since it is what selects the fallback.
- A session store left with a non-empty log after close is reported as sealed evidence
  that cannot be read. It does not by itself show that the snapshot reader caused it.
- **A replay that makes no cut** is inconclusive: the admission gave the cut nothing to
  do. A longer admission is needed before anything is said about the cut.
- **The favourable outcome needs a cut and a prompt size.** It is a replay that makes
  cuts, holds back no request, drops no image block and leaves no request above 60,000
  tokens, the simulation's high mark. A replay that makes cuts and still leaves a
  request above that mark shows the cut is not keeping its target, and the window or
  the model is revisited before the cut is proposed.

### The fallback's wording

The proposal's table says the design "falls back to captures made by the writer". The
[design](../design/live-curator-integration.md) now says what that must be: at each
window the custodian yields a detached, stable copy of the prefix; checkpointing the
live file is not enough.

## Limits

- This record corrects text. It measures nothing.
- The review that found these points read the merged proposal and the code offline. It
  did not run a live writer, a runner or a provider.
- The 60,000-token mark is the simulation's default, not a decided target for the cut.
