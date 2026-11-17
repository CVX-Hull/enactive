---
owner: lead
status: historical
kind: run
date: '2026-11-17'
scope: 'One supervised run of the current Terra player with curated knowledge and a fresh journal, using a verified copy of a previously inspected development save'
---

# Current Terra player rehearsal (#711)

## At a glance

- The player loaded Morgan Hale in Whitethorn, drank clean water and filled two
  containers. The visible Save and quit sequence returned to the title screen.
- The last application-Quit acknowledgement stayed unknown after native channel
  EOF. The driver recorded `interrupted`. The exact CDDA child exited normally
  with code zero before any cleanup signal. The player collected the original
  operation without replay and reported the uncertainty.
- The [run ledger](../../data/evaluation/runs.jsonl) records the single admission
  under study 711. Every attempt carried a provider-reported cost, including the
  briefing and three reminders. Supervision and owned cleanup verified.

## Frozen admission

The owner approved one [#711](https://github.com/CVX-Hull/enactive/issues/711)
admission under a $10 study envelope. Package `terra-rehearsal-711` used
`campaign-run/8`, session `d1f27714d8684654945e288f09cbcc73`, source
`8ac759b34755993529e94d6b97c92ac78cdab4ad` and manifest SHA-256
`d139a30b1217d7fe3eb2e66d520c1971fb37bdeaa1670302f7dc4865b35ea804`.
It froze the $4.50 run limit with its $1.00 ending reserve, 240 aggregate HTTP
attempts and 45 wall minutes. The pinned OpenRouter/OpenAI Terra route used
medium effort on the default tier. It delivered the full curator-scoring `v18`
with recall every ten completed inputs. The start was a verified working copy of
`withholding-pilot-619-start-12` with a fresh `player-journal/1` store.

The staged package passed the maintained offline validator. The installed app and
bridge matched the recorded bytes. The lead observed through the supervisor and
the original frames, with no tactical guidance, game input or Pause intervention.

## Observed play and ending

Retained source IDs share the session prefix above. Frame `249` shows Morgan
Hale in the character screen at Evac Shelter B-19. Frames `733` and `810` show
visible drinking and filling of the plastic tupperware and bottle. Frame `883`
shows the in-game Save and quit confirmation. The completed confirmation
operation returned frame `938`, the title screen with the Whitethorn save listed.
Frame `939` shows the separate main-menu Quit prompt. Save reload and longer
survival remain unverified.

The actor collected the original final Quit operation
`11bec1e74ac54c2a96292b6947718618`, which remained `unknown`. CDDA exited with
return code zero without a forced signal. The actor's direct finish reported
`task_complete` and uncertainty about the last input. The driver preserves the
permanent input fence as `interrupted`, even though the process exit is confirmed.
The same close-at-EOF behavior occurred in the [production control evidence](2026-10-29-computer-control.md).
Carry that known limitation into the next admission brief and preserve the
independent exit verification. This run supplies no reason to relax the input
fence or to repeat the final input.

The host delivered the recall briefing in the first player request and
reminders in player requests 13, 24 and 33. The run exercises live
delivery and useful play on the current journal boundary. A memory benefit,
handoff, sustained cadence and an ending initiated by the resource reserve
remain unverified. The player chose to end early. A fresh-world cohort remains a
separate decision under [#441](https://github.com/CVX-Hull/enactive/issues/441).

<!-- evaluate-table study=711 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| terra-rehearsal-711 | terra-current-rehearsal | S1 | custody | 0.01 | 29 | 4 | 0.5 | 0 · 0.00 h | 69% | 11 | 0.0034 | 0% |
<!-- /evaluate-table -->

## Cleanup and evidence

The terminal supervisor and custodian receipts match the frozen session and
manifest and retain the input revocation and complete cost accounting. The lead
independently verified absence of six owned process groups, closure of all three
loopback listeners and availability of the shared game lock. The final userdir,
package, receipts, host and journal records, frames and evaluator store are
sealed in `terra-rehearsal-711`. The installed working copy and duplicate runtime
directories were retired after hash verification. The original sealed saved
moment remains available. The [evidence index](../../data/evidence/index.json)
holds the private seal's provenance and checksums.
