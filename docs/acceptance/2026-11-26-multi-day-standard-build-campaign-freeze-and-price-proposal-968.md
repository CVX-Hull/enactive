---
owner: lead
status: historical
kind: measurement
date: '2026-11-26'
scope: 'Frozen parameters, offline preflight and owner price proposal for one multi-day campaign on an unmodified standard character build under campaign-run/13, curator-knowledge/4, delivered-knowledge/3 and player-host/12, for issue #968 under outcome #136; $0, no game launch, no provider request; nothing here is approved until the owner decides'
---

# Multi-day standard-build campaign: frozen parameters and price proposal (#968)

## At a glance

- **Nothing was launched or spent.** No game process started and no provider request
  was sent. This record proposes a paid run; it does not authorize one. The run needs
  an owner spending decision in the
  [owner decision log](../decisions/owner-decisions.md) ([C-SPEND](../controls.md)).
- **What is proposed.** One fresh `Wilderness / Campground / Survivor` lineage on an
  unmodified `8/8/8/8` build, played in chained admissions until the saved game clock
  is three in-game days (`259,200` game seconds) past the start. Each admission is
  sized to end on its dollar reserve, so the `spend-reserve-reached` stop that
  [#963](2026-11-25-wave3-wave4-live-validation-963.md) never reached is exercised.
- **Price.** Each admission is expected to cost `$8.20` to `$13.70` and cannot exceed
  `$18.00`. The recommended envelope is **`$80.00` for at most six admissions**, with
  a rule that no admission starts unless `$18.00` of the envelope is left.
- **What is not known.** How fast a standard build moves the game clock. The two
  comparable runs differ by a factor of eighteen in decisions per game hour, so the
  number of admissions three days takes is a range of two to more than six. The
  envelope bounds the dollars either way; it does not promise the horizon.
- **Offline preflight passes.** A never-started package built with the proposed limits
  passes `tools.campaign_package`, the proposed curator runner file passes
  `live_runner.read_config`, and the 197 offline tests that cover actor handoff, the
  curator runner and the combined rehearsal pass.
- **Owner decisions the run needs:** the envelope and horizon (two options
  [below](#options-for-the-owner)), and who operates the supervisor.

The builder script, the preflight output, the runner file and the test output are
retained as
[`multi-day-standard-build-preflight-968`](../../data/evidence/multi-day-standard-build-preflight-968.sha256).

## Why another campaign

Outcome [#136](https://github.com/CVX-Hull/enactive/issues/136) asks for one coherent
independent multi-day campaign on an unmodified standard build that shows learning,
retained memory and normal endings on the current stack. Two runs come close and
neither meets it:

| Run | Stack | Build | Game time | What it lacks |
| --- | --- | --- | --- | --- |
| [Seven-day campaign, second lineage](2026-11-22-seven-day-campaign-896.md) | `campaign-run/12`, `player-host/11` | `12/12/12/12`, rated overpowered | 168.4 h in ten admissions | the standard build and the current stack |
| [Bounded live validation #963](2026-11-25-wave3-wave4-live-validation-963.md) | `campaign-run/13`, `player-host/12` | `8/8/8/8` | 1.80 h in one admission | more than one admission, and a stop on the dollar reserve |

The [campaign admission workflow](../workflows/campaign-admission.md) requires a
deciding multi-day benchmark to use the default point pool with unmodified baseline
stats and no pool points spent on skills.

## Measured rates the price rests on

| Rate | #963, current stack | Seven-day second lineage, earlier stack | Source |
| --- | ---: | ---: | --- |
| Decisions | 690 in one admission | 3,630 in ten admissions | the two records |
| Player and recall dollars for each decision | `$0.00507` | `$0.0064` rising to `$0.0090` | [run ledger](../../data/evaluation/runs.jsonl), the seven-day record's evaluator table |
| Host seconds for each decision | 7.72 | not derived | [campaign run](../operations/campaign-run.md#ending-reserve-and-external-stop) |
| Live curator dollars for each decision | `$0.0067` (`$4.644`) | `$0.0135` (`$48.93`) | the two records |
| Boundary grooming dollars for each admission | `$0.25` | `$0.22` to `$0.40` | the two records |
| Decisions for each game hour | 383 | 21.6 | decisions divided by game hours |
| Admissions that ended on the dollar reserve | 0 of 1 | most, at a `$5.00` limit | the two records |

The seven-day lineage's cost for each decision grew by a factor of 1.4 as its
knowledge grew. The forecast applies that growth to the current stack's rate, giving
`$0.0051` to `$0.0072` for each decision.

## Proposed frozen parameters

The launch package is built at the launch commit, since a package names the exact
clean `HEAD`. These are the values it carries.

**Package (`campaign-run/13`), one for each admission**

| Field | Value | Reason |
| --- | --- | --- |
| `labels` | arm `standard-build-multi-day`, start `S1`, scenario `Wilderness / Campground / Survivor`, world and lineage `campground-standard-multi-day`, admission `1` and up | one lineage, chained admissions |
| `context` | `{"ruleset": "standard"}` | the standard-build scope, as #963 |
| `live_knowledge_updates` | `true` | the player receives curator publications during play |
| `spend_limit_usd`, `ending_reserve.usd` | `5.50`, `1.40` | as #963; `$4.10` of working dollars |
| `host_seconds`, `total_host_seconds`, `wall_seconds` | `7200`, `7200`, `7800` | above the 6,844 seconds the working dollars fund at #963's pace, so the dollar reserve ends the admission |
| `ending_reserve` other fields | seconds `600`, inputs `128`, requests `128`, frames `96`, frame bytes `201326592` | as #963 and the seven-day campaign |
| `max_hosts` | `2` | one `player_handoff` allowed inside an admission |
| `limits` | inputs `6000`, requests `10000`, frames `1500`, bytes `2147483648` | as the seven-day campaign |
| Route (`player-host/12`) | unchanged from #963: `openai/gpt-6.1-terra` at Medium, the `openai` then `azure` allowlist with no other fallback, context cut `60000/20000/10`, recall every 10 inputs | one comparable route |
| Working guide | `docs/player-guide.md` at the launch commit | frozen for the whole lineage |
| Starting knowledge | admission 1: an empty `delivered-knowledge/3` export; later admissions: the lineage's latest published version | memory carries across admissions |

**Expected stop.** `spend-reserve-reached`, then an orderly save and quit. The
`$4.10` funds 569 to 804 decisions, which take 4,400 to 6,200 working host seconds;
the time reserve would trigger at 6,600. A stop on time means the player decided more
slowly than in #963 and is a pacing result, not a fault.

**Live curator runner (`curator-runner-config/1`), one file for the lineage**

```json
{
  "schema": "curator-runner-config/1",
  "knowledge_root": ".runtime/knowledge/standard-build-multi-day/cdda",
  "arm": "terra",
  "cap_usd": "9.00",
  "session_cap_usd": "5.00",
  "trigger_steps": 25,
  "ceiling_steps": 45,
  "poll_seconds": 15,
  "watch_seconds": 5,
  "host": {
    "effort": "medium",
    "max_requests": 120,
    "max_output_tokens": 16384,
    "request_timeout_seconds": 240,
    "wall_seconds": 1800,
    "max_context_images": 16,
    "context_image_block": 8
  }
}
```

It is #963's file with a new knowledge root and a `$9.00` cap for each admission in
place of `$12.00`: the seven-day lineage's admissions spent `$6.06` to `$6.54` under
an `$8.00` cap. One boundary-grooming session follows each admission with
`--cap-usd 3.50`; the seven-day lineage's largest single reservation was `$2.15`, and
its `$2.50` cap stopped three sessions.

**Admissions and handoff.** An admission is one supervised launch that reloads the
previous admission's save. Inside an admission the player may hand off once to a
second actor; a context cut keeps one actor going and does not end it. Between actors
the runner examines the first actor's remaining steps and the second actor starts from
the latest adopted knowledge version
([curator component](../components/curator.md)).

## Price

| Component | Expected for one admission | Limit for one admission | What enforces the limit |
| --- | --- | --- | --- |
| Play | `$4.15` to `$4.30` | `$5.50` | `spend_limit_usd`; finish-up begins at the `$1.40` reserve |
| Live curator | `$3.80` to `$9.00` | `$9.00` | the runner's `cap_usd` |
| Boundary grooming | `$0.22` to `$0.40` | `$3.50` | `--cap-usd` |
| **One admission** | **`$8.20` to `$13.70`** | **`$18.00`** | |

The curator range is 569 to 804 decisions at `$0.0067` to `$0.0135` each, capped. The
limits are reservation ceilings in this project's own accounting. The only hard
billing cap is the credit limit on the provider key, which the owner sets outside the
codebase.

**How many admissions.** At the seven-day lineage's 21.6 decisions for each game hour,
three days is about 1,555 decisions, or two to three admissions. At #963's 383, it is
far out of reach. #963 was a first admission, which spends its decisions on setup;
the seven-day lineage's first admissions covered 4.0 and 23.7 game hours. The
proposal therefore caps admissions and dollars and reports the clock reached.

### Options for the owner

| | Recommended: three days | Alternative: seven days |
| --- | --- | --- |
| Target on the saved clock | `259,200` game seconds | `604,800` game seconds |
| Most admissions | 6 | 12 |
| Envelope | `$80.00` | `$160.00` |
| Expected spend if the target is reached | `$16` to `$82` for two to six admissions | `$66` to `$164` for eight to twelve |
| Why | the charter's milestone is multiple in-game days; three days is the smallest target that needs sleep, food and water cycles to repeat | matches the seven-day campaign, so the two builds compare over the same span |

Three days is recommended because the standard build's pace is unknown and the
smaller envelope buys that measurement. If it is reached well inside the envelope,
extending the same lineage to seven days is a second decision made with the pace
known.

## Stop rules

No budget or attempt is renewed silently
([campaign review](../workflows/campaign-admission.md#campaign-review-and-finding-disposition)).

1. Do not start an admission unless recorded spend plus `$18.00` is within the
   envelope, and never start more than the approved number of admissions.
2. Stop the campaign, with no relaunch, on a preflight failure, a custody or cleanup
   failure, a non-empty write-ahead log at seal, or an account or credit refusal from
   the provider.
3. Stop the campaign when the saved clock reaches the target, and when the character
   dies. A death ends the lineage; a second lineage is a new owner decision.
4. An admission that ends early for an infrastructure cause counts as one of the
   approved admissions.
5. After each admission the lead reviews the sealed store before starting the next:
   the build on the first admission, the stop trigger, the save clock, the curator
   publications and the spend so far.

## What the campaign must show

Each item is read from sealed artifacts.

1. **Standard build.** Unmodified `8/8/8/8`, no pool points on skills, and a rating
   that is neither freeform nor overpowered, from the first observation.
2. **Multiple days.** The last admission's saved clock is at least the target past the
   start.
3. **Normal endings.** Every admission ends with a save and quit, a zero native exit
   and verified custody, and the next admission's first clock reading is that save's.
   An autosave reload is reported with the game time lost.
4. **Retained memory.** The curator's publication chain is unbroken across admissions,
   every actor starts from the latest adopted version, and no delivery fails.
5. **Learning.** In every admission after the first, the player reads or cites at
   least one knowledge record published in an earlier admission. This shows use of
   what was learned. Whether decisions improved is reported per admission, as game
   hours survived, health and food, and is not claimed from one lineage.
6. **Independence.** Every game input comes from a hosted actor; no manual input, hint,
   memory edit or save edit.
7. **Dollar-reserve stop.** At least one admission ends by `spend-reserve-reached`
   followed by an orderly stop.

| Outcome | Condition | What follows |
| --- | --- | --- |
| Fail | custody, cleanup or log-safety failure | fix the defect before any further run |
| Invalid | a non-standard build is observed | keep as development data; ask the owner before rerunning |
| Partial | the envelope or the admissions run out before the target, or the character dies | report the clock reached, the cause and the spend; no relaunch |
| Partial | the target is reached and item 3, 4, 5 or 7 fails | report which item and why |
| Pass | all seven items hold | #136's campaign acceptance is met; the parked studies that wait on a multi-day campaign can be priced |

## Offline preflight

Run from the main checkout at `b4b83df5`, with no game process and no provider
request.

- **Package.** `scripts/rehearse.py` built a never-started package with the proposed
  limits and labels from #963's sealed package files, a fresh empty knowledge export
  and the current tool template.
  `python -m tools.campaign_package --run PACKAGE --work-before-bytes 262144000 --ending-before-bytes 312475648`
  exited 0 and printed manifest hash `865a34a5…dde8829` with 1,835,008,000 bytes left
  at the ending checkpoint (`results/preflight.txt`). The check covers the closed
  manifest, every file hash, the limit ordering, the route's reserve rules and the
  player host's own validation.
- **One substitution.** #963's bridge build directory was removed after sealing, so
  the rehearsal names the sealed copy of the same bridge bytes. The launch package
  names a bridge rebuilt and qualified at the launch commit.
- **Runner file.** `tools.curator_host.live_runner.read_config` accepts the file above
  (`results/read-config.txt`).
- **Handoff and combined rehearsal.** `tests/test_campaign_player.py`,
  `tests/test_curator_runner.py`, `tests/test_wave4c_combined_rehearsal.py` and
  `tests/test_campaign_package.py`: 197 passed (`results/tests.txt`). They cover actor
  succession on `player_handoff`, the runner's examination of the first actor's tail,
  the second actor's start from the latest adopted version, and `spend-reserve-reached`
  through to an orderly stop.
- **Not covered offline.** The rehearsal package was removed after the check. A
  second admission that reloads a real save, and the grooming session's behaviour on
  a knowledge graph larger than #963's thirty versions, are first exercised by the
  run.

## Execution checklist

For the [execution leaf](https://github.com/CVX-Hull/enactive/issues/998), after the
owner's decision is in the log:

1. Rebuild and qualify the bridge at the launch commit; build the admission's package
   with the values above; run the two preflight commands.
2. Start `tools.campaign_supervision` with the package and the runner file.
3. After the store seals, run one grooming session with `--cap-usd 3.50`.
4. Seal the admission's evidence, add its row to the run ledger, and apply stop
   rule 5 before the next admission.
5. Write one dated run record for the campaign with the seven items and the outcome.
