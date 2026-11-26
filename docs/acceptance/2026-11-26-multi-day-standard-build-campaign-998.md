---
owner: lead
status: historical
kind: run
date: '2026-11-26'
scope: 'One multi-day campaign on an unmodified standard character build under campaign-run/13, curator-knowledge/4, delivered-knowledge/3 and player-host/12: lineage campground-standard-multi-day (world Francis Mills, survivor Rowan Vale) in four admissions from main 7c4bec87, run as frozen in the #968 proposal and approved by the owner on 26 November 2026 at three in-game days, $80.00 and six admissions, for issue #998 under outcome #136; the deciding assessment for #136'
---

# Multi-day standard-build campaign (#998)

## At a glance

- **Outcome: Partial.** The target is reached and six of the proposal's seven items
  hold. Item 7, a stop on the dollar reserve, does not: no admission emitted
  `spend-reserve-reached`. By the
  [proposal's outcome table](2026-11-26-multi-day-standard-build-campaign-freeze-and-price-proposal-968.md#what-the-campaign-must-show)
  that is "Partial: the target is reached and item 3, 4, 5 or 7 does not hold", and
  #136's campaign acceptance is not met on the frozen criteria. Whether item 7 is
  waived is the owner's decision.
- **Three in-game days on a standard build.** One fresh `Wilderness / Campground /
  Survivor` lineage, stats 8/8/8/8 with no traits, played from Spring day 61, 8:00:00
  AM to a saved clock of Spring day 64, 8:02:48 AM: 259,368 game seconds, 168 past the
  259,200 target. The survivor ended at full health.
- **Four admissions, each with a save, a separate quit and a zero native exit.** The
  owner approved six.
- **Spend: `$35.45` of the `$80.00` envelope.** Play `$11.49`, live curator `$23.01`,
  boundary grooming `$0.95`.
- **Memory was retained and used.** The curator's publication chain is unbroken from
  v0 to v101, every later admission started from the previous admission's groomed
  version, and in admissions 3 and 4 the player read records first published in an
  earlier admission and acted on them.
- **Why item 7 fails.** The host's advisory spend notice reaches the player at about
  `$3.49` of play spend and tells it to wrap up. The player saved and quit on that
  notice in admissions 1 to 3, at `$3.51` to `$3.53`. The reserve handshake starts near
  `$3.69`, so it was never reached. The proposal's forecast did not account for the
  notice.

[Issue #998](https://github.com/CVX-Hull/enactive/issues/998) ·
[outcome #136](https://github.com/CVX-Hull/enactive/issues/136) ·
[owner approval](../decisions/owner-decisions.md#multi-day-standard-build-campaign-approved-998) ·
[proposal](2026-11-26-multi-day-standard-build-campaign-freeze-and-price-proposal-968.md)

Each admission's package, session store, curator runner, knowledge repository,
grooming session and saved user directory are sealed as
[`multi-day-standard-build-998-admission-01`](../../data/evidence/multi-day-standard-build-998-admission-01.sha256),
[`-02`](../../data/evidence/multi-day-standard-build-998-admission-02.sha256),
[`-03`](../../data/evidence/multi-day-standard-build-998-admission-03.sha256) and
[`-04`](../../data/evidence/multi-day-standard-build-998-admission-04.sha256). The
operator note, the package review, the two trace analyses, the builder and boundary
scripts, the prompts and the supervisor logs are sealed as
[`multi-day-standard-build-998-campaign`](../../data/evidence/multi-day-standard-build-998-campaign.sha256).
Attempts, wall time and play spend for each admission are the rows of study 998 in the
[run ledger](../../data/evaluation/runs.jsonl).

## What ran

- **Launch commit.** All four admissions ran from the main checkout at
  `7c4bec8780743a063a172dc9b4a0eb968e6dfa78`, clean, whose `controller` check and other
  CI checks pass. The working guide is `docs/player-guide.md` at that commit for the
  whole lineage.
- **Bridge.** Rebuilt at that commit with `tools/build_computer.py`; `bridge.dylib`
  SHA-256 `35f08843…bb06fd9`, built without warnings from a clean tree.
- **Packages.** One `campaign-run/13` package for each admission with the values the
  proposal freezes: play limit `$5.50` with a `$1.40` ending reserve, 7,200 host
  seconds, 7,800 wall seconds, at most two actors, and the route of #963. The live
  curator runner file is the proposal's, with `$9.00` for each admission. Both offline
  preflights passed for every package.
- **Prompts.** Admission 1 used #963's fresh-world prompt unchanged. Admissions 2 to 4
  used the seven-day lineage's later-admission prompt with the target changed to three
  days and the world and survivor names the player chose in admission 1.
- **Starting knowledge.** Admission 1 started from an empty export; admissions 2, 3 and
  4 from the groomed versions v38, v68 and v94.
- **Review before launch.** GPT-6.2 Sol at Extra-high on Codex checked the unlaunched
  admission 1 package against the proposal in a clean context: every package value,
  hash, the runner file, the empty save folder and the continuation prompt held. It
  pointed out a character preset and a last-world pointer left in the user directory
  by #963; the lead moved both to the project archive before launch.
- **User directory.** The project's `.runtime/user`. The earlier validation's world was
  moved to the project archive, identical to its sealed copy, so admission 1 started
  with no saved world.

## The four admissions

| Admission | Session | Requests, player and recall | Wall time | Saved clock, game seconds from the start | Ending |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | `088ba638…` | 754 and 30 | 5,385 s | 82,550 (22 h 55 min 50 s) | player finish after the spend notice |
| 2 | `f91a383e…` | 817 and 70 | 5,220 s | 167,598 (46 h 33 min 18 s) | player finish after the spend notice |
| 3 | `f0e2b12e…` | 725 and 4 | 4,820 s | 252,495 (70 h 08 min 15 s) | player finish after the spend notice |
| 4 | `a6979727…` | 208 and 4 | 1,301 s | 259,368 (72 h 02 min 48 s) | player finish: task complete |

| Admission | Play | Live curator, sessions | Boundary grooming | Total |
| --- | ---: | ---: | ---: | ---: |
| 1 | `$3.5333` | `$5.6276`, 26 | `$0.1582` | `$9.3191` |
| 2 | `$3.5060` | `$6.7327`, 28 | `$0.1869` | `$10.4256` |
| 3 | `$3.5258` | `$8.2127`, 32 | `$0.3316` | `$12.0701` |
| 4 | `$0.9258` | `$2.4382`, 7 | `$0.2720` | `$3.6360` |
| All | `$11.4909` | `$23.0112`, 93 | `$0.9487` | `$35.4508` |

- **Spend is complete.** Every receipt reports `spend_complete: true` with no unpriced
  request. Play spend is the receipt's; live curator spend sums each session's settled
  amount; grooming spend is the grooming summary's.
- **Pace.** Admissions 1 to 3 each cover about 23 game hours in 729 to 887 requests,
  31 to 38 requests for each game hour. The proposal could not choose between the
  seven-day lineage's 21.6 and #963's 383; this lineage is close to the first.
- **Admission rule.** Before each start the lead applied the proposal's continuation
  rule and the actual-spend admission rule of the
  [operator permissions](../operator-permissions.md#finite-gameplay-budget-delegation)
  and used the stricter. Before admission 4 the stricter figure was `$55.95`, inside
  the envelope.
- **Stop.** After admission 4 the saved clock passed the target and the campaign
  stopped under the proposal's stop rule 5. Two approved admissions were not used.

## The seven items

1. **Standard build: holds.** The character-creation summary frame
   (`run/sources/088ba6385ed4d42f6e728ad34d8fe943-536.png` in admission 1) shows
   Strength, Dexterity, Intelligence and Perception at 8, traits "None!", scenario
   Wilderness, profession Survivor and lifestyle "underpowered", which is neither
   freeform nor overpowered. Every save has stats 8/8/8/8 and no traits.
2. **Multiple days: holds.** Admission 4's saved game file, decompressed as the
   seven-day campaign's was, gives `turn` 5,472,168 against `game_start` 5,212,800:
   259,368 game seconds.
3. **Normal endings: holds, with one difference reported.** Every admission ended with
   the player's Save, a separate Quit, a native exit of zero and verified custody
   (native process absent, input authority revoked, cleanup verified). The receipts of
   admissions 1 to 3 carry the outcome `interrupted`: the delivery of the player's Quit
   input came back unknown because the game exited on it, as in the seven-day
   lineage's admissions. At the boundaries the first clock the next admission observed
   equals the saved clock twice, and at the first boundary is 111 game seconds later
   than the save's clock (82,661 against 82,550). The cause of that difference is not
   established; no game time was lost.
4. **Retained memory: holds.** The repository's tags v0 to v101 form one parent chain,
   and every tag an earlier sealed copy shares points to the same commit. Live versions
   are v1 to v37, v39 to v67, v69 to v91 and v95 to v100; grooming published v38, v68,
   v92 to v94 and v101. Each later package names the previous admission's groomed
   version and the actor received it on its first request. The actors adopted 26 of
   26, 28 of 28, 22 of 22 and 6 of 6 exported updates, and all 181 delivery events say
   delivered.
5. **Learning: holds.** Three cases, each a read of a record first published in an
   earlier admission followed by actions that use it:
   - In admission 3 the player read `rowan-day-62-existing-fire-ring`, first published
     in admission 1 at v34, with the intent "Review the recorded fire-ring location
     relative to camp before hauling fuel", then hauled fuel to that ring, lit it and
     cooked (`request-260` to `request-285`).
   - In admission 3 the player read the article `frozen-water-to-clean-water`, first
     published in admission 1 at v17, then collected and boiled two portions of water
     (`request-162` to `request-186`).
   - In admission 4 the player read `rowan-day-63-bough-fire-craft-interruption`,
     first published in admission 3 at v86, relit the brazier and resumed the
     interrupted craft the record describes (`request-79` to `request-100`).

   This shows use of what was learned. Whether decisions improved is not claimed from
   one lineage. Each admission's last report gives full health bars and no hunger or
   thirst warning; the last two report low food reserves (153 and 225 kcal eaten that
   day so far) and eight portions of clean water.
6. **Independence: holds on the evidence there is.** All 2,201 input rows in the four
   session stores (674, 730, 619 and 178) match a hosted actor's `computer_input` call
   by request, call and operation. The knowledge repository holds 102 commits: one
   initialization, 95 live publications and six grooming publications, and no other.
   The operator note lists what the lead did outside the trace and records no hint, no
   input, no pause and no manual edit. As the proposal says, the artifacts cannot prove
   that nobody gave a hint outside the trace; the note is the evidence for that.
7. **Dollar-reserve stop: does not hold.** No host log holds a `spend-reserve-reached`
   event. In admissions 1 to 3 the host emitted one spend notice
   (`tail-notice`, kind `spend-limit`) at `request-745`, `request-810` and
   `request-718`, and the player finished nine, seven and seven requests later at
   `$3.5333`, `$3.5060` and `$3.5258`. Admission 4 ended at `$0.9258` with no notice.

## Why the reserve stop was not reached

The [host contract](../contracts/player-host.md#spend) has two mechanisms near the play
limit. The spend notice is advice: with a `$5.50` limit and a `$1.40` ending reserve
the work budget is `$4.10`, the warning threshold is 15% of it, `$0.615`, and the
first notice goes out once `$3.485` is spent, telling the player to wrap up with
`player_finish`. The reserve handshake is a stop: it emits `spend-reserve-reached`
when a request no longer fits above the reserve, near `$3.69`. The notice comes
`$0.20` earlier, and a player that follows it has saved and quit before the handshake
can fire.

The proposal sized each admission "so that its dollar reserve is forecast to end it"
and did not consider the notice. In the seven-day lineage six of ten admissions did
end on the driver's dollar trigger, under a `$5.00` limit and an earlier host version.
This campaign's admissions were ended by dollars each time, through the notice. The
handshake, and the save and quit that follow it, remain unexercised in real play on
this stack.

## Reviews and analyses

- **Trace analyses.** GPT-6.2 Sol at Extra-high on Codex read the sealed copies in two
  read-only starts and reported items 4, 5 and 6, the boundary clocks and the host's
  stop events with file and request references. The lead checked the first learning
  case against the host log and the repository history, and the build against the
  creation frame.
- **What the analyses could not establish.** They found no operator note in the sealed
  admissions; it is sealed with the campaign evidence.

## Limits

- **One lineage.** One world, one survivor, one route. Nothing here measures how often
  a standard build survives three days.
- **The learning cases are reads followed by matching actions.** The player's later
  choices are consistent with the records; that the records caused them is inferred.
- **Food security is weak at the end.** The survivor is healthy and watered at 72
  hours with little stored food. The campaign does not show a sustainable food supply.
- **Not exercised:** an actor handoff inside an admission (each used one actor), the
  reserve handshake, and a death.
- **Operator attention.** The lead did not watch the spectator page, so a death would
  have been ended by the admission's limits and not by a pause.

## Delegated starts and quota

The delegated starts are rows in the
[attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl). Before the first
start the Claude Code week stood at 52% used and the Codex week at 60%; after the last
trace analysis the Codex week stood at 65%. No paid overflow on a subscription was
used. The provider spend above is the campaign's only spend.
