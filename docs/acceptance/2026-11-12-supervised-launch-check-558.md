---
owner: lead
status: historical
kind: run
date: '2026-11-12'
scope: 'Two short supervised runs with the real game and a real model on main d71ced0, checking launch, the run-ending record, operator Pause from the spectator page, cleanup and evaluator reading after the attention policy was removed (#558, #553); no gameplay quality claim'
---

# Supervised launch check after the attention-policy removal, 12 November 2026

[#558](https://github.com/CVX-Hull/enactive/pull/558) removed the `required` attention
policy from run supervision and changed two record versions. It merged on portable
tests, browser suites and an independent review, with no run against the real game.
The owner approved one short real launch to check it ("Run it now", 12 November 2026).
This record holds what the two runs showed. The current rules are in
[supervision](../operations/campaign-supervision.md).

## Setup

- **Source:** main `d71ced05853c2e8cce76a1d1872a4a4c91d86ad0`, clean, in its own worktree
  with its own runtime directory, so the main checkout's saves were not touched.
- **Game:** a copy of the prepared windowed app with a fresh user directory.
- **Adapter:** built from that source for this check (`bridge.dylib` SHA-256
  `990821943d28a88c…`, receipt in the sealed evidence).
- **Route:** OpenRouter, pinned provider `openai`, model `openai/gpt-6.1-terra`, medium
  effort, no fallback. This is the diagnostic route earlier development runs used; it
  confers no selection.
- **Assignment:** the standard new-world Evacuee start. One host, no handoff.
- **Launch:** `.venv/bin/python -m tools.campaign_supervision --run PACKAGE`, with the
  credential read from the keychain by the supervisor.

## Results

| | First run | Second run |
| --- | --- | --- |
| Package | `launch-check-558` | `launch-check-558-pause` |
| Request allowance | 12 | 80 |
| How it ended | The custodian ended it when two requests remained | Pause from the spectator page, reason "Other" |
| Recorded reason | `custodian_terminal` | `operator_pause`, `pause_reason: other` |
| Time from ready to stop | 43 seconds | 119 seconds |
| Requests charged | 11 | 29 |
| Start record | `campaign-watch-start/4`, seven keys | the same |
| End record | `campaign-watch-terminal/4` | `campaign-watch-terminal/4` |
| Pause reply from the custodian forwarded | not applicable | yes |
| Terminal coverage verified | yes | no, as for any run stopped by Pause |
| Cleanup verified, game process absent | yes | yes |

What this establishes:

- Supervision starts without an attention option and reaches "Exact spectator ready".
- The page served by the real gateway showed the live frame and status with no check
  panel and no console error while the run was live.
- A run that nobody acknowledges continues past the old 45-second window; the second
  run played for 119 seconds.
- Pause from the page reached the real custodian and stopped the run. The custodian's
  reply came back through the gateway, which means the gateway's check that it was
  talking to this run's custodian passed against a real process.
- Neither record carries a removed field, and no attempts file was written.
- No process was left behind after either run.
- The evaluator read both runs and wrote an evaluation record for each.

In play, the model created a world and began character creation in the first run, and
created a second world in the second. Neither run is evidence about play quality.

## Spend

| | Requests | Host's configured estimate | Worst-case reservation consumed |
| --- | --- | --- | --- |
| First run | 11 | $0.0287 | $4.5056 |
| Second run | 29 | $0.0849 | $11.8784 |
| Total | 40 | $0.1136 | $16.3840 |

The estimate is computed by the host from reported usage at the route's configured
rates. The provider's invoice was not read. This spend sits under no study envelope; the
owner approved it directly. The packages' prior-reservation figure continued from the
last package on record, the fourth held-out lineage's seventh admission; the cumulative
figure is one of the open questions in
[#555](https://github.com/CVX-Hull/enactive/issues/555).

## Limits

- One host on one route on this Mac. A handoff between two hosts, a custody deadline
  reached in a real run and a provider failure were not exercised.
- After Pause the page showed "Pause requested (Other). Native confirmation pending",
  then reported its status as unavailable, because the gateway that serves it stops
  with the run. The page never shows a final stopped state. That is how it behaved
  before the change too; it is noted as a readability point, not a defect of #558.
- The first run ended before Pause could be tried, because 12 requests lasted 42
  seconds. The second package raised the allowance for that reason.

## Evidence

Both run packages, their evaluation records, the player stores, the user directory and
the adapter's build receipt are sealed as `supervised-launch-check-558` in the
[evidence store](../operations/evidence-cleanup.md).
