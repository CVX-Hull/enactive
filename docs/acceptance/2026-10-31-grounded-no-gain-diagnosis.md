---
owner: lead
status: historical
date: 2026-10-31
scope: Diagnostic arms A, C and H on one frozen save, scored by blind frame audit, to decide which lever explains grounded players making no retained gain
---

# Why grounded players make no retained gain

[#314](https://github.com/CVX-Hull/enactive/issues/314) is a discovery iteration. Since #298, players
have increasingly grounded the avatar and UI, yet no run has made a retained survival gain.
This record states which lever the evidence supports. It makes **no capability or adoption
claim**. Packages, traces, frames, audit bundles, saves and retained post-run state stay
ignored project-local evidence under `.runtime/iteration314/` and
`.runtime/computer-sessions/diag314-*`.

**Finding.** Four runs, two models, one shared save. No player made a retained state
change.
- **Budget:** offered 300 attempts, the player ended by its own choice at 95 and made no
  change. That is **consistent with** the budget not being the bottleneck from this state
  (n = 1).
- **Model:** Haiku was censored like Gemini. That is **consistent with** the pattern not
  being model-specific (n = 1), although H tested little play.
- **Goal selection versus control:** **not separated.** Without arm D, nothing intervened
  on either, and this record does not infer one.
- **Lever supported:** neither budget nor model choice gains support. The candidate levers
  that remain, the player's own goal commitment and claim verification, are untested here.
  The next item tests one directly rather than taking it as established.

## Design as frozen

Owner decisions on #314:
- The cap check uses actual spend to date (#316).
- **Arm D, the lead nudge, is dropped.** The player must be self-sufficient because the
  project will generalize, so no lead tactical hint enters any arm through any channel.
- The escalation limit is $1000 actual. Auto top-up covers the runs.

The independent scope review returned Ready-with-changes. Its required changes were applied
to the issue body before any run.

| Arm | Model and route | Runs × attempts | Question |
| --- | --- | --- | --- |
| A | Gemini 3.8 Flash, `google-vertex/global` | 2 × 100 | Reference |
| C | the same | 1 × 300 | Is the action budget the bottleneck? |
| H | Haiku 5.5, `google-vertex/europe` | 1 × 100 | Is the pattern model-specific? |

- All four packages came from source commit c698347, under `player-host/2` with the
  established 30/1 image policy, at medium effort.
- Each context was the unchanged player guide plus #304's assignment verbatim, with only the
  allocation line differing (checked by diff). It carried exactly one historical report,
  chosen by a fixed rule: the save's immediate predecessor's terminal report (#304's play003),
  verbatim and labelled fallible.
- **No hidden state.** The whole `.runtime/user/` tree (527 files: save, config, cache,
  achievements, memorial, graveyard) and the player store were frozen as play003's normal
  Save left them. Before every run both were restored and every hash verified, and each run's
  post-run state was retained first. The restore asserts on any mismatch but keeps no
  separate log; the live tree verifies against the manifest now. Saves were never edited.
- Endpoints were repriced and the account balance read before each package. Lead checks were
  read-only every 15 s; the maximum gap was 15.01 s in every run.
- **Scoring.** Every run had two blind clean-context auditors working from relabelled frames,
  the input log and the report, with session identifiers replaced. A third auditor resolved
  M3 disagreements in A1, H and C. Blinding was partial: H and C were identifiable by length.
  - **M1:** the first retained state change in inventory, carried weight, worn or wielded
    items, a consumed item or a status indicator, confirmed in a later frame.
  - **M2:** active input operations whose following capture was byte-identical to the
    preceding one. This is a descriptive lower bound.
  - **M3:** terminal-report claims, labelled supported, contradicted, unsupported or hedged.
    Only frames count as support.
  - C's planned first-100-attempt view is moot, because C ended at 95.

## Results

| Run | Attempts used | Ending | M1 (last captured attempt) | M2 ops (key items) | M3 S/C/U/H |
| --- | --- | --- | --- | --- | --- |
| A1 | 75 / 100 | normal Save at the 25-attempt reserve | censored @72 | 2/69 (2/183) | 7 / 1 / 3 / 1 |
| H | 23 / 100 | **chose** Save/Quit after ~15 | censored @18 | 0/16 (0/26) | 12 / 0 / 4 / 2 |
| A2 | 77 / 100 | normal Save at the reserve | censored @74 | 6/71 (20/228) | 7 / 1 / 4 / 1 |
| C | 95 / **300** | **chose** Save/Quit at 92 | censored @92 | 10/89 (27/265) | 9 / 0 / 4 / 1 |

- **M1: all runs censored, with unanimous auditor agreement.** Carried weight stayed at
  12.5/81.6 lbs and the wielded pocket knife never changed in any run. Nothing was picked up,
  eaten, worn or dropped, and status lines did not change.
- **What players did.** They loaded correctly, walked corridors, looked around, talked to
  NPCs, and opened menus, the mission log and (A2) a trade screen, then saved.
  - A1 and H reached the game's stealing prompt for Free Merchants-owned items and declined
    ([A1's prompt](assets/diagnosis-314/a1-stealing-prompt.png); its decline shows in the
    next capture).
  - A2's only pickup attempt (`,`) was rejected as an unknown command.
  - C made no pickup input at all.
  - Offered missions were declined or left untouched. C found an active quest in its mission
    log ([frame](assets/diagnosis-314/c-active-mission-log.png)) but did not pursue it. H
    confirmed it had no food, then ended.
- **M2** found 0–11% no-change operations (0–10% of key items). That is a lower bound: a
  changed capture does not show the intended effect (movement-driven Activity and Sound
  changes count as change), and a batch can hide no-op keys. Multi-key batches of five or
  more keys were 13 of 73 operations in A1, 15 of 75 in A2, 22 of 93 in C and 1 of 19 in H.
  Explicit failed actions seen by the auditors were rare: a rejected `,` in A2 and a failed
  examine in A1.
- **M3: the Gemini reports overstated, and H's did not.**
  - A1, A2 and C each had 4–5 contradicted or unsupported claim units. Typical forms:
    - "confirmed application Quit" listed as an observed effect before any frame showed it;
    - room names ("dining hall", "office wing") inferred from furniture;
    - "locked electronic gates" inferred from generic look text;
    - "Failures: None", contradicted by a visible failed action in A2 and, under the
      third auditor's reading, in A1 (its caveat: if "Failures" means only run-level faults,
      the label is unsupported).
  - H's four unsupported units were accurate statements about its final Quit input coming
    back unknown and fenced. They fail only the frames-only rule.
  - **Confound:** the Gemini reports closely follow the included play003 report's wording,
    including "Resumed Parker West campaign on Papaikou", "Failures: None" and C's Unknowns
    line. The predecessor report acted as a template. So M3 here cannot be read as an
    independent replication of #304's inflated reports.
- **Provider and runtime:** no refusals, retries, 5xx or missing usage. Every native exit was
  0, and ownership and authority checks passed. Every run's final Quit input came back
  `unknown` (native channel EOF at application exit). Each player listed the process state
  as unknown, but A1, A2 and C also listed the Quit as confirmed, and A2 claimed an exit
  receipt.

## Reading against the frozen rules

- **Budget (C).** C made no change before or after A's working allowance of 75. It stopped
  at 95 of 300 by its own choice, so the extra budget was not taken up. That is consistent
  with the budget not being the bottleneck from this state, at n = 1. C also had a longer
  context.
- **Model (H).** H does not differ from A: both are censored. That is consistent with the
  pattern not being model-specific (n = 1). H changes model, provider, caching and
  tokenization together, and it ended after about 15 attempts.
- **Goal selection versus control.** This cannot be separated without D, and the record does
  not infer it. The audit shows menus, dialogue and movement operating, and acquisition,
  consumption or pursuing a found goal never happening. It does not show why.
- **Ending.** A1 and A2 ended at the frozen 25-attempt ending reserve. Only H and C stopped
  early by choice.
- **Shared save-state confound.** All arms started from one state. It is inside a
  faction-owned refugee center where nearby items are owned (taking them is stealing), the
  south gates are impassable ("nothing that can be opened"), and the character carries
  4 currency and no food. A retained change needed trading, a mission or leaving the center.
  No run did any of these. Whether that reflects goal commitment, the state's difficulty or
  reasonable caution is not established.

## Next

Neither budget nor model choice gains support. The remaining candidate levers are the
player's own:
- **goal commitment and outcome verification**, such as a self-maintained subgoal and
  expectation ledger checked against frames through its own memory tool (the issue's
  optional arm B, held to beating A on audit, not narration);
- **report claims checked against observed sources** ([#42](https://github.com/CVX-Hull/enactive/issues/42)).

Grooming after #314 shapes exactly one of these as the next Ready item, and treats it as a
test, not an established cause. A future design should also vary or remove the predecessor
report and the start state, which confound these runs.

## Accounting

- Actual cost: **$8.62** across 270 attempts (600 allocated, 330 retired unused): A1 $2.32,
  H $0.07, A2 $2.80, C $3.43. These are whole OpenRouter account deltas on a shared account,
  each run counted up to the next reading, so they are upper bounds.
- Configured-rate trace estimates were about 2× actual for Gemini and about 5× for H.
- The admission baseline under #316's rule is now $56.67. The worst-case reservation was
  checked only as the cap ($2600) and is not spend.

Evidence summary: [summary.json](assets/diagnosis-314/summary.json).
