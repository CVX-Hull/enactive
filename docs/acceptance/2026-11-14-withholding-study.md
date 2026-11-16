---
owner: lead
status: historical
kind: study
date: '2026-11-14'
scope: 'The full withholding study (#651): 60 starts over two sealed saved moments, each unit of store v18 withheld in exactly half of each moment''s starts, judged blind and analysed by withholding-study/1; the frozen primary with Opus judges, and the two secondaries fixed on #651 before any arm comparison (the check-advice units left out; a revised codebook, judged by GPT judges on both codebooks by the owner''s decision); use labels, host timing and provider retries; $86.40 of a $120 cap'
---

# The full withholding study (#651)

## At a glance

- **Question.** Does delivering a fact from the player's memory make the player miss it
  less (act against it, or spend an action looking it up again), compared with the same
  fact withheld, over the 32 units of the groomed store `v18`?
- **Answer, read by the rule fixed on #651 before any arm comparison: a benefit is
  suggested but limited by the measure; it is not a confirmed benefit.** The frozen
  primary is not positive. Of the pre-specified secondaries, only the revised
  codebook's reading without the nine check-advice units is (one-sided p 0.026). The
  study gives no reading with p 0.05 or below over all units, and none with the frozen
  codebook.
- **The primary** (Opus judges A and B, C on disputes; the randomization test within
  units, 10,000 draws, seed 653): withheld units were missed more often than delivered
  ones by **+0.021**, **p 0.329**, over the 20 units counted (9 never touched, 3
  touched in one arm only). Intention to treat over all 32 units: −0.032, p 1.0. The
  mixed model's withheld coefficient: −0.32 (SD 0.30).
- **Delivery changes what is touched.** Delivered units were touched in 284 of 960
  unit-starts (0.296) and withheld ones in 194 (0.202); the touch balance test gives
  p < 0.0001 in every labelling. Touch happens after the assignment, so the primary,
  which counts only touched units, compares groups that delivery itself shaped.
- **Play: 60 valid starts, three attempts replaced, nothing withheld reached the
  player.** S31, the first start, was read end to end before the rest. In all 63 played
  attempts no withheld unit appears in a recall selection, delivered text or tool
  result. Four starts (S14, S18, the S20 replacement and S23) ended in the survivor's
  death by fire at the first saved moment; they are valid outcomes and stay in.
- **Use, judged separately** (Opus): when a fact whose lead was delivered applied, the
  player acted in line with it in **84.4%** of windows (611 of 724; 0.814 to 0.872) and
  looked it up again in 14.5%; it acted on a fact the frames showed stale or false in
  16 of 634 windows (2.5%).
- **Spend: \$86.40 counted of the \$120 cap** (the load check \$0.018; 63 played
  attempts \$86.38, recall included). All judging was at no provider spend: Opus judges
  are host agents, and the GPT judges ran through Codex on the owner's own credits.
- **Owner decisions** used here: "60 starts, 2 saves, \$120 cap"; "Frozen primary +
  both secondaries"; "Replace at same index" twice; "Minimal fix leaf, then judge";
  "Use a workflow"; "GPT for both codebooks"
  ([decision log](../decisions/owner-decisions.md)). Adoption (#463) is put to the owner
  with this record.

## What was run

- **Frozen before play** on #651 at `a6d294af`: the second saved moment
  (`withholding-pilot-619-start-12`, the pilot's S2: Spring day 64, 6:58:12 AM, evac
  shelter B-19), whose copy `withholding-651-b-load` passed a load check (8 attempts,
  \$0.0180); no placebo unit, since none of the 32 qualifies (the 8 with no facts of
  their own can never be touched, and every unit with facts could matter at either
  moment); the draw (`draw-study`, 60 starts, blocks `397-seven-day:30` and
  `withholding-pilot-619-start-12:30`, seed 651, SHA-256 `35b9bcff…c63c`), which
  withholds each unit in exactly 15 of each block's 30 starts; the 60 packages with
  their hashes; recall and play on `openai/gpt-6.1-terra`, reminders every `N = 10`
  decisions, \$5 and 240 requests a start; about \$89 expected.
- **Play.** One start at a time on the serialized native lane, windowed, in the frozen
  interleaved order beginning S31, S1, S32. Before each start the chain checked that
  the counted spend plus that start's \$5 limit stayed within the cap, and after each
  it checked the receipt and the package for any withheld unit, evaluated it and
  disposed of the start with a seal.
- **The primary judging.** Fresh blind packets for all 60 starts under the frozen
  codebook (`6418c260…`), 137 packets cut to 60,000 tokens: judges A and B (clean-context
  Opus, packet directory only) on every packet, C on the 130 packets with a dispute.
  Use packets were judged the same way, apart. `memory_measure study` then ran as the
  contract fixes it.
- **The secondaries,** fixed on #651 after a quality check of the first 14 starts and
  before any arm comparison:
  - **Secondary A** re-runs the primary statistic and intention to treat without the 9
    units whose own facts advise a check (`article-boiled-egg-2`, `-bow-drill-3`,
    `-cattail-4`, `-fishing-6`, `-in-progress-craft-5`, `-pine-tea-3`, `-shelter-6`,
    `-short-cordage-3`, `-textile-crafts-3`): a player who follows such advice is
    labelled `found_again`, which biases against finding a benefit.
  - **Secondary B** judges all 60 starts again under a revised codebook that settles
    four gaps the quality check found: a failed or abandoned attempt to make something,
    routine screens, a search with no captured result, and hedged cautions. The revision
    merged as #659, and is analysed over all units and without the nine.
  - **Judges for secondary B.** By the owner's decision "GPT for both codebooks", GPT
    judges (`gpt-6.1-sol`, high effort, through Codex) judged both the primary's 137
    packets and the 138 revised packets: A and B on all, C on disputes. The codebook's
    effect is therefore read within one judge model.

## Results

### The primary statistic, every reading

The statistic is the mean over counted units of (withheld missed share − delivered
missed share) among touched unit-starts; positive means withholding makes misses more
likely, so delivery helps. One-sided p from the within-unit randomization test.

| Labels | All units: value, p (units) | Without the 9: value, p (units) | Intention to treat, all 32 | Mixed model, withheld (SD) |
| --- | --- | --- | --- | --- |
| Opus, frozen codebook (**primary**; secondary A) | +0.021, **0.329** (20) | +0.059, **0.199** (12) | −0.032, 1.0 | −0.32 (0.30) |
| GPT, frozen codebook (for the within-model comparison) | +0.015, 0.358 (20) | +0.065, 0.064 (12) | −0.042, 1.0 | −0.27 (0.23) |
| GPT, revised codebook (**secondary B**) | +0.050, **0.087** (20) | +0.089, **0.026** (12) | −0.039, 1.0 | +0.19 (0.21) |

Pooled over units instead of within them, touched delivered units were missed more often
than touched withheld ones in every labelling: 0.218 against 0.160 (Opus), 0.262 against
0.174 (GPT, frozen) and 0.300 against 0.241 (GPT, revised). Without the nine the pools
are nearly level (0.120 against 0.125; 0.146 against 0.134; 0.187 against 0.200). The
positive within-unit readings come from comparing each unit with itself; units differ
widely (the mixed model's unit variance is about 9 on the log-odds scale, against 0.1 to
0.2 between starts).

### The judges

| Labels | Packets | Label agreement, κ (all pairs) | Driving pairs: n, κ | Missed: positive / negative specific agreement, AC1 | C settled alone |
| --- | --- | --- | --- | --- | --- |
| Opus, frozen | 137 | 0.956, 0.814 | 1,244, 0.526 | 0.839 / 0.997, 0.993 | 45 |
| GPT, frozen | 137 | 0.952, 0.840 | 1,472, 0.570 | 0.867 / 0.996, 0.992 | 38 |
| GPT, revised | 138 | 0.952, 0.849 | 1,545, 0.675 | 0.901 / 0.996, 0.992 | 40 |

On driving pairs, AC1 on the missed outcome was 0.925, 0.924 and 0.911. No pair was left
without a label. Before the revision, a prompt check on the 15 sealed pilot stretches
(Opus judges on both sides, `prompt-check report`) moved agreement from 0.952 to 0.966 and
κ from 0.790 to 0.845 (shift +0.055; 0.005 to 0.127 over 6 starts).

### Use

From the Opus use packets, which show the briefing and reminders:
- when the lead was delivered, the player acted in line with the fact in 611 of 724
  windows where it applied (0.844, 0.814 to 0.872);
- it found the fact again in 0.145;
- it acted on a fact the frames showed stale or false in 16 of 634 (0.025);
- of 97 facts it read, it then acted in line with 12 (0.124).

The judges agreed on 0.941 of use labels (κ 0.795).

### At no extra spend

- **Response time (#164,** `tools/host_analysis.py` over 104 traces and 12,226
  responses). The median response was 6.2 s and the 95th percentile 10.6 s. By prompt
  size the median was 3.3 s under 20k tokens, 6.1 s at 20k to 60k, 7.0 s at 60k to 100k
  and 8.8 s at 100k to 150k.
- **Provider retries (#309).** Of 13,547 requests:
  - four HTTP 429s from `openrouter_admission_control` (S31 three times, S11 once), all
    retried and accepted;
  - one HTTP 403 in S9, not retried, which ended that attempt (replaced; see
    Deviations).

  S31's three 429s were counted at the \$0.4096 bound, so S31 cost \$2.85.
- **#336's trigger** (time lost stepping between memory events when reading traces): not
  met. Reading S31's trace end to end lost no time to it, and no later reading did.

## How the result is read

The rule was posted on #651 before any arm comparison: a positive primary shows a
benefit; a primary that is not positive with Secondary A or B positive suggests a benefit,
limited by the measure; all not positive is no effect detected. The primary is not
positive and Secondary B's reading without the nine is, so the second case applies. What
limits it:

- **Multiplicity.** The secondaries carry no correction, as fixed. Over the four
  pre-specified readings (the primary, A, and B over all units and without the nine),
  a Bonferroni threshold would be 0.0125, which none meets.
- **Intention to treat is null in every labelling** (−0.03 to −0.04). Over all units,
  delivery did not reduce misses, partly because it made the player engage with more
  topics.
- **The touch imbalance** means the touch-conditioned statistic compares groups shaped by
  the treatment: delivered touched unit-starts include topics the player reached because
  it was told of them.
- **The two secondary-B readings differ from the primary in two ways at once,** the
  codebook and the judge model. Within the GPT judges, the codebook alone moves the
  statistic from +0.015 to +0.050 over all units (p 0.358 to 0.087) and from +0.065 to
  +0.089 without the nine (p 0.064 to 0.026). The GPT and Opus readings on the frozen
  codebook agree closely (+0.015 against +0.021; +0.065 against +0.059).
- **The codebook was revised after seeing this study's packets** (the quality check's 14
  starts), though before any arm comparison; its gain is partly in-sample.
- **The mixed model's sign follows the codebook** (−0.27 frozen, +0.19 revised, for GPT
  labels), with both intervals spanning zero.

## Limits

- **No placebo.** None of v18's units qualifies, so the negative control is undefined.
- **One lineage of one game, two saved moments a day apart,** both in the same shelter.
  The effect is for this store's units at these moments, not for facts in general.
- **The judges are models without human audits** (owner decision "Judges without
  audits"). On the pairs that drive the outcome, κ is 0.53 to 0.68. Judge error pulls the
  arms' judged rates together, so a true effect shows smaller than it is.
- **S50's process measures** use the fixed frame rule (#658): one `player_source` call on
  an earlier session's screenshot is not a frame of S50.
- **Twelve units drop out of the touch-conditioned statistic** (9 never touched, 3 touched
  in one arm only), so it rests on 20 units, or 12 without the nine.

## The validation record's threats

From the [measure validation](2026-11-14-withholding-measure-validation.md#threats):

- **The codebook was written from the same packets it was validated on.** The frozen
  codebook's first out-of-sample use is this study's primary, which is null. The
  revision was made from 14 of this study's own starts.
- **The effect sizes were assumptions.** The measured effects are small: within units
  +0.02 to +0.09 in miss probability among touched units, against the halving the study
  was sized to detect.
- **The sizing favoured a small study.** Judge error was not added to it, and the
  measured driving-pair κ (0.53 to 0.68) means some true effect is lost to it.
- **Delivery may change what is touched.** It does, strongly (above). This is the main
  threat to the primary estimand.
- **Blocks of an odd size.** Both blocks have 30 starts, so every unit is withheld in
  exactly half. Which units the second moment's starts touch was not analysed apart.
- **Judging is not free in time.** 922 Opus host judgings (blind 404, use 418, quality
  check 70, prompt check 30) and 806 GPT judgings through Codex (about 3 hours at 12 at a
  time), all at no provider spend.
- **Some misses may be habits delivery does not change.** The check-advice units are the
  clearest case; leaving them out is Secondary A, and it raises every reading.
- **The examples name a companion and eating.** These were kept; the revision adds
  examples in the same game-neutral vocabulary.
- **The judges are models without human audits** (above).

## Deviations

- **Three attempts replaced at the same index.**
  - S9 was cut short by an HTTP 403 after 95 attempts ("Replace at same index"). The
    owner's rule also applies to any later start a provider error ends.
  - S20 was invalid: the custodian's port was in use, so no input reached the game. It
    was replaced under the existing invalid-start rule, and a port check was added to the
    play chain.
  - S29 was interrupted after 7 attempts by an accidental click on the game window
    ("Replace at same index").

  The three attempts are sealed and counted in the spend.
- **The freeze was broken once,** before any arm comparison: the packet builder refused
  S50 over one frame of another session, and the fix (#658, "Minimal fix leaf, then
  judge") changed only that rule in `tools/memory_measure.py`.
- **The mixed model first failed** because the main checkout's environment lacked
  `statsmodels`. The environment was synced from the lock and `study.json` regenerated;
  every other field is identical to the first output, which is kept with the evidence.
- **A quality check** judged the first 14 starts' blind packets with judges A and B
  under the frozen codebook, and a blind diagnostic read the 26 split pairs. This led to
  the pre-specified secondaries. Its answers are evidence and were not reused.
- **The revised codebook paraphrases the pre-specification.**
  - The game-neutral word test bans "map" and "inventory", and the blind-leak test bans
    "intent", so the wording changes but the rules do not.
  - "Readying what the attempt needs" is a little broader than "readying fire or fuel".
  - Three review rounds (Opus, agy, Codex) scoped rule 3's exclusions to their screens,
    kept `against` for a warned attempt and gave the caution example a label.
  - Two prompt checks were stopped and rebuilt as the text changed; their answers are
    kept as superseded.
- **Secondary B's judges are GPT, not Opus** ("GPT for both codebooks"), and so GPT also
  judged the frozen codebook's packets for the comparison.
  - Each GPT judging ran on an isolated copy of one packet, read-only, with every frame
    attached.
  - 36 Opus judgings of the revised packets made before the decision are kept and not
    used.
  - The revised set has 138 packets to the primary's 137, because the longer
    instructions take more of each window's token budget; the judged facts are
    identical.
- **One incomplete Opus use answer** was set aside, and its packet judged again by a
  fresh agent.
- **No placebo** (above), as stated on #651 before play.

## Spend

| Item | Counted |
| --- | ---: |
| Load check | \$0.0180 |
| 60 analysed starts and 3 replaced attempts (play and recall; 63 ledger rows, 13,547 requests, 88,287 s) | \$86.3825 |
| **Total** | **\$86.40** of \$120 |

Judging, prompt checks and reviews made no provider spend.

## Evidence

- `withholding-study-651`: the draw, the 63 packages with both actors' host traces,
  frames, receipts and stores (14,596 files).
- `withholding-study-651-load-check`, and `withholding-study-651-start-01` to `-60` with
  `-start-09-cut-short`, `-start-20-invalid` and `-start-29-interrupted`: each start's
  final userdir, disposed of with a seal.
- `withholding-study-651-judging` (18,104 files):
  - every judging run: the Opus primary, use and quality check; the GPT frozen and
    revised runs; the prompt check;
  - each with its packets, events, adjudication, `study.json`, `measure.json` and
    `secondary-a.json`. The GPT frozen run's packets are byte-identical to the primary's
    and are not stored twice;
  - every judge's raw answer, including superseded ones;
  - the Codex judging logs and final messages;
  - the lead's scripts and outputs: the package builders, the play chain and leak check,
    the GPT judge driver, the secondary-A script, the host summary, and the #651
    comments.
