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
  primary is not positive. The only positive reading is secondary B's without the nine
  check-advice units (one-sided p 0.026). Secondary B as run differs from its
  pre-specification in two ways settled after the null primary was known: the
  codebook's final wording, and GPT judges in place of Opus. On the same frozen packets
  without the nine, GPT judges give p 0.064 where Opus gives 0.199, so most of the move
  comes with the judge model. The study gives no reading with p 0.05 or below over all
  units, and none with the frozen codebook.
- **The primary** (Opus judges A and B, C on disputes; the randomization test within
  units, 10,000 draws, seed 653): withheld units were missed more often than delivered
  ones by **+0.021**, **p 0.329**, over the 20 units counted (9 never touched, 3
  touched in one arm only). Intention to treat over all 32 units: −0.032, p 1.0. The
  mixed model's withheld coefficient: −0.32 (SD 0.30).
- **Delivery changes what is touched.** By the Opus labels, delivered units were
  touched in 284 of 960 unit-starts (0.296) and withheld ones in 194 (0.202); by the
  GPT labels 309 against 235 (frozen) and 317 against 241 (revised). The touch balance
  test gives p at its floor of 1 in 10,001 in every labelling. Touch happens after the
  assignment, so the primary, which counts only touched units, compares groups that
  delivery itself shaped.
- **Play: 60 valid starts, three starts replaced, nothing withheld reached the
  player.** S31, the first start, was read end to end before the rest. In all 63 played
  starts no withheld unit appears in a recall selection, delivered text or tool
  result. Four starts (S14, S18, the S20 replacement and S23) ended in the survivor's
  death by fire at the first saved moment; they are valid outcomes and stay in.
- **Use, judged separately** (Opus): when a fact whose lead was delivered applied, the
  player acted in line with it in **84.4%** of windows (611 of 724; 0.814 to 0.872) and
  looked it up again in 14.5%. Of the 634 windows in which it acted in line with a fact
  it had, the frames showed that fact stale or false in 16 (2.5%).
- **Spend: \$86.40 counted of the \$120 cap** (the load check \$0.018; 63 played
  starts \$86.38, recall included). All judging was at no provider spend: Opus judges
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
  before any arm comparison (their rules; the revised codebook's final wording and
  secondary B's judges were settled after the primary was written, as below):
  - **Secondary A** re-runs the primary statistic and intention to treat without the 9
    units whose own facts advise a check (`article-boiled-egg-2`, `-bow-drill-3`,
    `-cattail-4`, `-fishing-6`, `-in-progress-craft-5`, `-pine-tea-3`, `-shelter-6`,
    `-short-cordage-3`, `-textile-crafts-3`): a player who follows such advice is
    labelled `found_again`, which biases against finding a benefit.
  - **Secondary B** judges all 60 starts again under a revised codebook that settles
    four gaps the quality check found: a failed or abandoned attempt to make something,
    routine screens, a search with no captured result, and hedged cautions. The revision
    merged as #659, and is analysed over all units and without the nine.
  - **Judges for secondary B.** The pre-specification had the same Opus judges. After
    the primary was known, and to save Claude quota, the owner decided "GPT for both
    codebooks": GPT judges (`gpt-6.1-sol`, high effort, through Codex) judged both the
    primary's 137 packets and the 138 revised packets, A and B on all and C on disputes,
    so the codebook's effect is read within one judge model. Secondary B with Opus judges
    was not run.

## Results

### The primary statistic, every reading

The statistic is the mean over counted units of (withheld missed share − delivered
missed share) among touched unit-starts; positive means withholding makes misses more
likely, so delivery helps. One-sided p from the within-unit randomization test.

| Labels | All units: value, p (units) | Without the 9: value, p (units) | Intention to treat, all 32 | Intention to treat, without the 9 (23) | Mixed model, withheld (SD) |
| --- | --- | --- | --- | --- | --- |
| Opus, frozen codebook (**primary**; secondary A) | +0.021, **0.329** (20) | +0.059, **0.199** (12) | −0.032, 1.0 | −0.006, 0.83 | −0.32 (0.30) |
| GPT, frozen codebook (for the within-model comparison) | +0.015, 0.358 (20) | +0.065, 0.064 (12) | −0.042, 1.0 | −0.009, 0.88 | −0.27 (0.23) |
| GPT, revised codebook (**secondary B**) | +0.050, **0.087** (20) | +0.089, **0.026** (12) | −0.039, 1.0 | −0.006, 0.76 | +0.19 (0.21) |

Pooled over units instead of within them, touched delivered units were missed more often
than touched withheld ones in every labelling: 0.218 against 0.160 (Opus), 0.262 against
0.174 (GPT, frozen) and 0.300 against 0.241 (GPT, revised). Without the nine the pools
are nearly level (0.120 against 0.125; 0.146 against 0.134; 0.187 against 0.200). The
positive within-unit readings come from comparing each unit with itself; units differ
widely (the mixed model's unit variance is about 9 on the log-odds scale, against 0.1 to
0.2 between starts).

### The judges

| Labels | Packets (to C) | All pairs: n, label agreement, κ | Driving pairs: n, agreement, κ | Missed, all pairs: positive / negative specific agreement, AC1 | Missed, driving pairs: negative specific, AC1 | C settled alone |
| --- | --- | --- | --- | --- | --- | --- |
| Opus, frozen | 137 (130) | 10,549, 0.956, 0.814 | 1,244, 0.799, 0.526 | 0.839 / 0.997, 0.993 | 0.968, 0.925 | 45 |
| GPT, frozen | 137 (127) | 10,549, 0.952, 0.840 | 1,472, 0.810, 0.570 | 0.867 / 0.996, 0.992 | 0.967, 0.924 | 38 |
| GPT, revised | 138 (129) | 10,626, 0.952, 0.849 | 1,545, 0.835, 0.675 | 0.901 / 0.996, 0.992 | 0.963, 0.911 | 40 |

No pair was left without a label. Before the revision merged, a prompt check on the 15 sealed pilot
stretches (`prompt-check report`) moved agreement from 0.952 to 0.966 and κ from 0.790 to
0.845 (Δκ +0.056; 0.005 to 0.127 over 6 starts). It used Opus judges on both sides,
so it does not cover the GPT judges who applied the revised codebook; their own κ under
the frozen and revised codebooks is in the table.

### Use

From the Opus use packets, which show the briefing and reminders:
- when the lead was delivered, the player acted in line with the fact in 611 of 724
  windows where it applied (0.844, 0.814 to 0.872);
- it found the fact again in 105 of them (0.145, 0.117 to 0.175);
- of the 634 windows in which it acted in line with a fact it had, the frames showed
  that fact stale or false in 16 (0.025);
- of 97 facts it read, it then acted in line with 12 (0.124).

The judges agreed on 0.941 of 6,529 use pairs (κ 0.795, dispute rate 0.059); on the 816
pairs that drive the in-line rate, on 0.800 (κ 0.49, 0.43 to 0.56). C judged 132 of the
143 packets and settled 31 pairs with a label neither A nor B gave.

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
positive and Secondary B's reading without the nine is, so the second case applies, but
only through secondary B as modified after the null primary was known: the codebook's
final wording came from reviews after the primary was written, and its judges are GPT
rather than the pre-specified Opus. Secondary B with Opus judges was not run. What limits
it:

- **Multiplicity.** The secondaries carry no correction, as fixed. Over the four
  pre-specified readings (the primary, A, and B over all units and without the nine),
  a Bonferroni threshold would be 0.0125, which none meets.
- **Intention to treat is null in every labelling** (−0.03 to −0.04 over all units,
  −0.01 without the nine). Over all units delivery did not reduce misses; a likely
  mechanism, not tested here, is that it made the player engage with more topics.
- **The touch imbalance** means the touch-conditioned statistic compares groups shaped by
  the treatment: delivered touched unit-starts include topics the player reached because
  it was told of them.
- **The two secondary-B readings differ from the primary in two ways at once,** the
  codebook and the judge model. Within the GPT judges, the codebook alone moves the
  statistic from +0.015 to +0.050 over all units (p 0.358 to 0.087) and from +0.065 to
  +0.089 without the nine (p 0.064 to 0.026). On the frozen codebook the GPT and Opus
  point estimates are close (+0.015 against +0.021; +0.065 against +0.059), but GPT
  marks more unit-starts touched (544 against 478; 298 against 246 without the nine) and
  gives a much smaller p without the nine (0.064 against 0.199). Most of the move from
  the primary's 0.199 to secondary B's 0.026 comes with the judge model, and whether Opus
  judges on the revised codebook would have reached 0.05 is not known.
- **Pooled, delivery looks worse.** Touched delivered units were missed more often than
  touched withheld ones in every labelling (above); only the within-unit comparison is
  positive, and the two summaries weigh units differently because delivery changes which
  units are touched.
- **The codebook was revised after seeing this study's packets** (the quality check's 14
  starts). Its three rules were fixed before any arm comparison, but its final wording
  came from reviews after the primary was written; its gain is partly in-sample.
- **The mixed model's sign follows the codebook** (−0.27 frozen, +0.19 revised, for GPT
  labels), with both intervals spanning zero.

## Limits

- **No placebo.** None of v18's units qualifies, so the negative control is undefined.
- **One lineage of one game, two saved moments a day apart,** both in the same shelter.
  The effect is for this store's units at these moments, not for facts in general.
- **The judges are models without human audits** (owner decision "Judges without
  audits"). On the pairs that drive the outcome, κ is 0.53 to 0.68. If judge error is the
  same in both arms it pulls their judged rates together, so a true effect shows smaller
  than it is; but touch is itself a judged label and differs by arm, so that is not
  assured.
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
- **The sizing favoured a small study.** Judge error was not added to it; at the measured
  driving-pair κ (0.53 to 0.68), some true effect is likely lost to it if errors are
  alike in both arms.
- **Delivery may change what is touched.** It does, strongly (above). This is the main
  threat to the primary estimand.
- **Blocks of an odd size.** Both blocks have 30 starts, so every unit is withheld in
  exactly half. Which units the second moment's starts touch was not analysed apart.
- **Judging is not free in time.** 922 Opus host judgings (blind 404, use 418, quality
  check 70, prompt check 30) and 806 GPT judgings through Codex (about 3 hours at 12 at a
  time), all at no provider spend. These count the sealed events; the superseded,
  unused and test judgings in Deviations come on top.
- **Some misses may be habits delivery does not change.** The check-advice units are the
  clearest case; leaving them out is Secondary A, and it raises every reading.
- **The examples name a companion and eating.** These were kept; the revision adds
  examples in the same game-neutral vocabulary.
- **The judges are models without human audits** (above).

## Deviations

- **Three starts replaced at the same index.**
  - S9 was cut short by an HTTP 403 after 95 requests ("Replace at same index"). The
    owner's rule also applies to any later start a provider error ends.
  - S20 was invalid: the custodian's port was in use, so no input reached the game. It
    was replaced under the existing invalid-start rule, and a port check was added to the
    play chain.
  - S29 was interrupted after 7 requests by an accidental click on the game window
    ("Replace at same index").

  The three replaced starts are sealed and counted in the spend.
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
    kept `against` for a warned attempt and gave the caution example a label. These
    reviews, and so the final wording, came after the primary's `study.json` was written
    (18:32 on 15 November against reviews from 18:39); the pre-specification allowed the
    order ("Once the primary analysis is written, the freeze ends"), but the wording was
    settled with the primary's null result known.
  - Two prompt checks were stopped and rebuilt as the text changed; their answers are
    kept as superseded.
- **Secondary B's judges are GPT, not Opus** ("GPT for both codebooks", decided after the
  null primary was known), and so GPT also judged the frozen codebook's packets for the
  comparison. The prompt check used Opus judges and does not cover them.
  - Each GPT judging ran on an isolated copy of one packet, read-only, with every frame
    attached; one test judging of one revised packet checked this first and is not used.
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
| 60 analysed starts and 3 replaced starts (play and recall; 63 ledger rows, 13,547 requests, 88,287 s) | \$86.3825 |
| **Total** | **\$86.40** of \$120 |

Judging, prompt checks and reviews made no provider spend.

## Evidence

- `withholding-study-651`: the draw, the 63 packages with both actors' host traces,
  frames, receipts and stores (14,596 files).
- `withholding-study-651-load-check`, and `withholding-study-651-start-01` to `-60` with
  `-start-09-cut-short`, `-start-20-invalid` and `-start-29-interrupted`: each start's
  final userdir, disposed of with a seal.
- `withholding-study-651-judging` (18,104 files):
  - the three blind runs (the Opus primary, GPT frozen, GPT revised), each with its
    events, adjudication, judged facts, `study.json` and `secondary-a.json`, and the
    packets of the primary and the revised run. The GPT frozen run judged the primary's
    packets, which are byte-identical and not stored twice;
  - the Opus use run, with its packets, events, adjudication and `measure.json`;
  - the quality check (35 packets, judges A and B, adjudication), and the prompt check
    (15 pilot stretches, judges A and B, `prompt-check.json`);
  - every judge's raw answer, including superseded ones;
  - the Codex judging logs and final messages;
  - the lead's scripts and outputs: the package builders, the play chain and leak check,
    the GPT judge driver, the secondary-A script, the host summary, and the #651
    comments.
