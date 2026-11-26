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
  sized so that its dollar reserve is forecast to end it, which would exercise the
  `spend-reserve-reached` stop that
  [#963](2026-11-25-wave3-wave4-live-validation-963.md) never reached.
- **Price.** One admission is forecast to cost `$7.80` to `$13.70`. Its three
  configured allocations add to `$18.00`, and the amount held back before starting one
  is `$18.50`. The recommended envelope is **`$80.00` for at most six admissions**.
- **What is not known.** How fast a standard build moves the game clock. The two
  comparable runs differ by a factor of eighteen in decisions for each game hour. At
  the faster pace three days takes three or four admissions; at the slower pace it is
  out of reach of any envelope here. The envelope bounds the dollars either way; it
  does not promise the horizon.
- **Offline preflight passes** for the proposed limits and runner file. It does not
  exercise a second admission that reloads a save, or a real save and quit.
- **Owner decisions the run needs:** spending approval; the envelope and horizon (two
  options [below](#options-for-the-owner)); who operates the supervisor; and whether
  the campaign is the deciding assessment for outcome #136 or development evidence.

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
stats and no pool points spent on skills. #963 verified unchanged stats and skills and
could not confirm a numeric point-pool ceiling from the game's screens.

## Measured rates the price rests on

| Rate | #963, current stack | Seven-day second lineage, earlier stack | Source |
| --- | ---: | ---: | --- |
| Decisions | 690 in one admission | 3,630 in ten admissions | the two records |
| Player and recall dollars for each decision | `$0.00507` | `$0.0064` in the first admission, `$0.0090` in the last | [run ledger](../../data/evaluation/runs.jsonl), the seven-day record's evaluator table |
| Host seconds for each decision | 7.72 | not derived | [campaign run](../operations/campaign-run.md#ending-reserve-and-external-stop) |
| Live curator dollars for each decision | `$0.0067` (`$4.644`) | `$0.0135` (`$48.93`) | the two records |
| Boundary grooming dollars for each attempted session | `$0.25` | `$0.22` to `$0.40` in eight sessions | the two records |
| Decisions for each game hour | 383 | 21.6 | decisions divided by game hours |
| Admissions the driver ended on its dollar trigger | 0 of 1 | 6 of 10, at a `$5.00` limit | the two records |

The seven-day lineage's last admission cost 1.40 times its first for each decision;
the records do not establish why. The forecast applies that ratio to the current
stack's rate and rounds up, giving `$0.0051` to `$0.0072` for each decision.

## Proposed frozen parameters

The launch package is built at the launch commit, since a package names the exact
clean `HEAD`. These are the values it carries.

**Package (`campaign-run/13`), one for each admission**

| Field | Value | Reason |
| --- | --- | --- |
| `labels` | arm `standard-build-multi-day`, start `S1`, scenario `Wilderness / Campground / Survivor`, world and lineage `campground-standard-multi-day`, admission `1` and up | one lineage, chained admissions |
| `context` | `{"ruleset": "standard"}` | the standard-build scope, as #963 |
| `live_knowledge_updates` | `true` | the player receives curator publications during play |
| `spend_limit_usd`, `ending_reserve.usd` | `5.50`, `1.40` | as #963 |
| `host_seconds`, `total_host_seconds`, `wall_seconds` | `7200`, `7200`, `7800` | long enough that the dollars are forecast to run out first |
| `ending_reserve` other fields | seconds `600`, inputs `128`, requests `128`, frames `96`, frame bytes `201326592` | as #963 and the seven-day campaign |
| `max_hosts` | `2` | one `player_handoff` allowed inside an admission |
| `limits` | inputs `6000`, requests `10000`, frames `1500`, bytes `2147483648` | as the seven-day campaign |
| Route (`player-host/12`) | unchanged from #963: `openai/gpt-6.1-terra` at Medium, the `openai` then `azure` allowlist with no other fallback, context cut `60000/20000/10`, recall every 10 inputs | one comparable route |
| Working guide | `docs/player-guide.md` at the launch commit | frozen for the whole lineage |

**Forecast stop.** The host asks the player to finish up when a request's worst-case
cost no longer fits above the reserve: at about `$3.69` of counted spend, which is
`$5.50` less the `$1.40` reserve and the `$0.4096` bound on one unpriced request. At
`$0.0051` to `$0.0072` for each decision that is 513 to 724 decisions, or about 3,960
to 5,590 working host seconds at #963's 7.72 seconds for each decision. The time
reserve triggers at 6,600 seconds. The dollar trigger comes first unless decisions
take longer than about 9.1 seconds each at the cheap end or 12.9 at the expensive end,
or cost less than forecast. A stop on time is a pacing result, not a fault. The
handshake, the save and the quit are each verified separately in the run.

**Mission prompt and the save, by admission**

- **Admission 1** uses #963's fresh-world prompt: create the standard build, with the
  operator having verified that no saved world exists.
- **Later admissions** use a continuation prompt in the form the seven-day lineage's
  later admissions used: load the named world and survivor, verify the survivor's name
  and the clock, continue toward the target, then save and quit. The world and
  survivor names are filled in from admission 1.
- **The save.** The operator keeps the same project-local campaign user directory for
  the whole lineage and, before each later admission, confirms that the previous
  admission's save is present.
- **Starting knowledge.** Admission 1 starts from an empty `delivered-knowledge/3`
  export. Each later package is built with `tools.knowledge_export` from the lineage's
  latest confirmed publication, grooming included, with the same world, lineage and
  context.

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

It is #963's file with a new knowledge root and a `$9.00` allocation for each
admission in place of `$12.00`. In the seven-day lineage, live curation cost `$0` to
`$6.54` an admission under an `$8.00` cap; the five admissions that ended with a
refused reservation spent `$6.06` to `$6.54`.

**Boundary grooming.** One session with `--cap-usd 3.50` follows an admission when the
knowledge repository's last published admission is that run; the tool skips or refuses
otherwise. The seven-day lineage's largest single reservation was `$2.15`, and its
`$2.50` cap stopped three of eight sessions. Whether `$3.50` is enough on a larger
graph is not established. A skipped, refused or cap-stopped session is reported and
does not block the next admission; a failed close-out of the repository does, until
the lead resolves it.

**Actors inside an admission.** The player may hand off once to a second actor; a
context cut keeps one actor going and does not end it. The second actor starts from
the latest knowledge version the driver has adopted. The runner examines the first
actor's remaining steps, which may finish after the second actor starts
([curator component](../components/curator.md)).

## Price

| Component | Forecast for one admission | Allocation | What applies it |
| --- | --- | --- | --- |
| Play | `$4.16` to `$4.27` | `$5.50` | `spend_limit_usd`; finish-up begins near `$3.69` |
| Live curator | `$3.44` to `$9.00` | `$9.00` | the runner's `cap_usd` |
| Boundary grooming | `$0.22` to `$0.40`, or `$0` when skipped | `$3.50` | `--cap-usd` |
| **One admission** | **`$7.80` to `$13.70`** | **`$18.00`** | |

- **Play** is the `$3.69` threshold plus `$0.47` to `$0.58` of finish-up, the amount
  by which the seven-day lineage's dollar-ended admissions passed their own threshold.
- **Live curator** is 513 to 724 decisions at `$0.0067` to `$0.0135` each, held at the
  allocation.
- **The allocations are not a hard limit.** The player contract lets the last
  in-flight player and recall requests pass the play limit by up to `$0.47`, so an
  admission is planned at **`$18.50`**. The only hard billing cap is the credit limit
  on the provider key, which the owner sets outside the codebase.

**Continuation rule.** Before each admission the lead counts the campaign's spend from
the run ledger and the curator and grooming ledgers. An admission whose spend could
not be counted is recorded at its planning amount with `--record-upper-bound`
([campaign run](../operations/campaign-run.md)), and an unsettled curator reservation
counts at its allocation. The next admission starts only if that total plus the larger
of `$18.50` and the most expensive admission so far is within the envelope.

**How many admissions.** These are scenarios, not a forecast of the pace.

| Pace, in decisions for each game hour | Three days | Seven days |
| --- | --- | --- |
| 21.6, the seven-day lineage on the stronger build | about 1,555 decisions: 3 or 4 admissions | about 3,630 decisions: 6 to 8 admissions |
| 383, #963's single first admission | 38 or more admissions | out of reach |

A first admission spends decisions on setup: the seven-day campaign's two first
admissions covered 4.0 and 23.7 game hours.

### Options for the owner

| | Recommended: three days | Alternative: seven days |
| --- | --- | --- |
| Target on the saved clock | `259,200` game seconds | `604,800` game seconds |
| Most admissions | 6 | 12 |
| Envelope | `$80.00` | `$160.00` |
| Most the continuation rule lets the campaign reach | `$75.20`: five admissions at the top of the forecast, six if they average under `$12.30` | `$155.20`: eleven at the top of the forecast |
| Spend at the faster pace | `$23` to `$55` for 3 or 4 admissions | `$47` to `$110` for 6 to 8 |
| Why | the charter's milestone is multiple in-game days; three days is the smallest target that makes sleep, food and water cycles repeat | matches the seven-day campaign, so the two builds compare over the same span |

Three days is recommended because the standard build's pace is unknown and the
smaller envelope buys that measurement. If the target is reached well inside the
envelope, extending the same lineage to seven days is a second decision made with the
pace known.

## Stop rules

No budget or attempt is renewed silently
([campaign review](../workflows/campaign-admission.md#campaign-review-and-finding-disposition)).

1. **Envelope and count.** Apply the continuation rule before every admission, and
   never start more than the approved number.
2. **Preflight refusal.** Nothing starts and nothing is spent. The lead fixes the
   package and runs preflight again; it does not count as an admission.
3. **Custody, cleanup or log-safety failure.** Stop the campaign with no relaunch.
4. **Provider account or credit refusal.** Stop the campaign. Resuming is a new owner
   decision. A refusal whose cause is unknown is treated the same way.
5. **Target reached.** The lead reads the saved clock from the sealed store after each
   admission and stops the campaign at the target.
6. **Death.** The operator watches the spectator view and pauses the supervisor on an
   observed death; unwatched, the admission's limits end it. A death ends the lineage.
   A second lineage is a new owner decision.
7. **An admission that ends without a verified save,** for an infrastructure cause or
   a user pause, counts as one of the approved admissions. The next one loads the last
   verified save, and the game time lost is reported.
8. **Review between admissions.** The lead reviews the sealed store before the next
   start: the build on the first admission, the stop trigger, the save and its clock,
   the curator publications, any handoff and the spend so far. A material failure in
   any of them holds the campaign until the lead records what happened.

## What the campaign must show

Each admission retains its sealed store and receipt, the frames of character creation
on the first admission, the saved game file at the end, the curator and grooming
ledgers, and an operator note of anything done outside the recorded trace, which is
expected to be empty.

1. **Standard build.** Unmodified `8/8/8/8`, no pool points on skills, and a rating
   that is neither freeform nor overpowered, from the creation frames.
2. **Multiple days.** The last admission's saved game file gives a clock at least the
   target past the start, read from the decompressed save as the seven-day campaign
   did.
3. **Normal endings.** Every admission ends with a save, a separate quit, a zero native
   exit and verified custody. At each boundary the next admission's first clock
   reading is at or within one autosave of the saved clock, and any difference is
   reported as game time lost or gained.
4. **Retained memory.** The curator's publication chain is unbroken across admissions,
   each later package starts from the latest confirmed publication, every actor starts
   from the latest adopted version, and no delivery fails.
5. **Learning.** The campaign has at least two admissions, and in a later one the
   player reads a knowledge record first published in an earlier admission and then
   acts on it, shown by the read, the record's publication and the decisions that
   follow. This shows use of what was learned. Whether decisions improved is reported
   for each admission as game hours survived, health and food, and is not claimed from
   one lineage.
6. **Independence.** Every recorded game input matches a hosted actor's tool result,
   the publication history holds no manual edit, and the operator notes are empty. The
   artifacts cannot prove that nobody gave a hint outside the trace; the operator's
   note is the evidence for that.
7. **Dollar-reserve stop.** In at least one admission the host emits
   `spend-reserve-reached`, the driver's orderly stop is accepted, and the save and
   quit follow.

The first row that applies gives the outcome.

| Outcome | Condition | What follows |
| --- | --- | --- |
| Fail | custody, cleanup or log-safety failure | fix the defect before any further run |
| Invalid | a non-standard build, or any input, hint or edit from outside the hosted actors | keep as development data; ask the owner before rerunning |
| Stopped | provider refusal or an unknown refusal before the target | report the clock reached, the cause and the spend; resuming is an owner decision |
| Partial | the envelope or the admissions run out before the target, or the character dies | report the clock reached, the cause and the spend; no relaunch |
| Partial | the target is reached and item 3, 4, 5 or 7 does not hold | report which item and why |
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
  player host's own validation. The two byte checkpoints are the ones #963's
  preflight used; they are not derived again here.
- **Two differences from a launch package.** The rehearsal copies #963's fresh-world
  prompt, so it stands for admission 1 only. #963's bridge build directory was removed
  after sealing, so the rehearsal names the sealed copy of the same bridge bytes; the
  launch package names a bridge rebuilt and qualified at the launch commit.
- **Runner file.** `tools.curator_host.live_runner.read_config` accepts the file above
  (`results/read-config.txt`).
- **Tests.** `tests/test_campaign_player.py`, `tests/test_curator_runner.py`,
  `tests/test_wave4c_combined_rehearsal.py` and `tests/test_campaign_package.py`: 197
  passed (`results/tests.txt`). In separate tests and with stand-in hosts or providers
  they cover actor succession on `player_handoff`, the runner's selection of an ended
  actor's tail, a second actor's start from the adopted version, and the
  `spend-reserve-reached` event through to an accepted stop. No test runs that whole
  chain together.
- **Not covered offline.** A later admission that loads a real save; a real save and
  quit after the dollar handshake; the reserve's adequacy through finish-up and a
  handoff; and grooming on a knowledge graph larger than #963's thirty versions. The
  run exercises these first. The rehearsal package was removed after the check.

## What is still open before the run is Ready

The [campaign admission workflow](../workflows/campaign-admission.md) lists what a
campaign records before it starts. This record gives the objective, scenario, success
and failure criteria, route, per-admission limits, stop and save rules and the review
between admissions. Still to be recorded on the
[execution leaf](https://github.com/CVX-Hull/enactive/issues/998), with the owner's
decision:

- the envelope and horizon chosen, which fix the cumulative limits;
- the named operator of the supervisor;
- whether the campaign is the deciding assessment for outcome #136 or development
  evidence;
- the exact launch inputs: the launch commit, the rebuilt bridge and its hash, the
  campaign user directory and the continuation prompt's text.

## Execution checklist

For the execution leaf, after the owner's decision is in the log:

1. Rebuild and qualify the bridge at the launch commit; build the admission's package
   with the values above and the prompt for that admission; run the two preflight
   commands.
2. Start `tools.campaign_supervision` with the package and the runner file.
3. After the store seals, run the grooming session where the tool accepts it.
4. Seal the admission's evidence, add its row to the run ledger, and apply stop rule 8
   and the continuation rule before the next admission.
5. Write one dated run record for the campaign with the seven items and the outcome.
