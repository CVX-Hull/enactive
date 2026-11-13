---
owner: lead
status: historical
date: '2026-11-08'
scope: 'Probe suite and baseline carry and rediscovery rates from the sealed #397 lineage and a seeded #372 sample, with inter-rater agreement and annotation cost (#449)'
review_trigger: None; dated record
---

# Probe baseline from sealed traces (#449)

The [probe protocol](../design/probe-protocol.md) (`probe-protocol/1`) was applied to the
sealed #397 lineage and to six of #372's short runs. #382's held-out lineages were not
opened. Everything below is **development data**: it fits and debugs the P1 study and
decides nothing ([ADR 009](../decisions/009-curated-player.md#evaluation-and-studies)).

**Where the figures come from.** Every figure is derived by
[`tools/probe_baseline.py`](../../tools/probe_baseline.py) from the tracked annotations in
[`data/evaluation/probes/`](../../data/evaluation/probes) into `baseline.json`. Game hours
come from the tracked run ledger. Re-run it with `.venv/bin/python -m tools.probe_baseline`.
A test checks that the tracked `baseline.json` reproduces from the tracked annotations.

## How it was done

**Annotators.** One general-purpose agent annotated each chunk (one actor's span) in a
fresh context, chunk by chunk in lineage order, from the frozen brief in the protocol. Each
was told to read only the protocol's sections, the generated timeline and the frames. The
brief did not state the hypotheses or any known episode. However, the protocol sections
the annotators read had examples drawn from one known episode (see
[deviations found in review](#deviations-found-in-review)). The lead did not edit
annotations. Each returned chunk was validated against the whole lineage before the next
began.

**Frame coverage.** Annotators viewed every third changed frame, every frame in a chunk's
last five operations, and every frame they cited. They viewed 699 frames for #397 (1,933
in the lineage) and 515 for the #372 sample. A pilot on `sd1a1-001`, run before the
coverage rule existed, viewed 16 of 133 frames and is excluded.

**Samples.**
- **#397:** all 14 chunks, 13 boundaries.
- **#372:** the runs drawn by `random.Random(449).sample` from the 26 eligible runs:
  aidB3, ceil09, ceil07, ceil05, aidB9 and aidA5. That is 12 chunks and 6 in-run handoffs.
  #372's evaluator records were not sealed with its sessions, so its timelines have no
  game clock or change flags. Its game hours come from the run ledger, and its annotators
  viewed every third frame in place of every third changed frame.

## Results

| Lineage | Facts | Live facts at boundaries | Carried (cumulative) | Held by the predecessor | Retained | Needed facts | Needed and carried | Probes | Failing | Failing with cost | Rediscoveries | Game hours | Per game hour |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| #397, in-admission handoffs (7) | | 490 | 157 (0.32) | 238 | 147 (**0.62**) | 129 | 60 (0.47) | | | | | | |
| #397, admission boundaries (6) | | 422 | 81 (0.19) | 244 | 79 (**0.32**) | 108 | 25 (0.23) | | | | | | |
| **#397, all 13 boundaries** | 139 | 912 | 238 (**0.26**) | 482 | 226 (0.47) | 237 | 85 (**0.36**) | 237 | 152 | 120 | 210 | 47.79 | **4.39** |
| #397, with the adjudication layer | 139 | 912 | 238 (0.26) | 482 | 226 (0.47) | 240 | 85 (0.35) | 240 | 155 | 123 | 210 | 47.79 | 4.39 |
| #372 sample, in-run handoffs (6) | 141 | 70 | 58 (**0.83**) | 70 | 58 (0.83) | 20 | 17 | 20 | 3 | 3 | 4 | 5.37 | 0.75 |

**The two carry rates.**
- **Carried (cumulative)** is carried live facts over every live fact on the ledger. A
  fact lost at one boundary counts as uncarried at every later one, so the rate measures
  how much of the whole ledger reaches each successor.
- **Retained** counts only the live facts the predecessor chunk held: it observed them,
  received them, or acted on them. It locates where facts are lost. In #372's one-handoff
  runs the two rates are equal.

**Needed** counts live facts that a later decision in the successor's span depended on.
**A probe fails** when the needed fact was not carried. It **fails with cost** when the
successor, in the same chunk, then re-observed the fact or acted without it. The
adjudicated row adds the lead's unblinded events (below): three more needed facts, two at
admission boundaries (110 needed there) and one at a handoff (130).

**Probes are not independent.** A fact needed across many boundaries contributes one
probe per boundary. For example, the starting inventory and the ration calorie value
recur in most #397 boundaries.

**What the figures say, as development evidence only.**
- **Handoffs lose less than admissions.** Within #397, an actor handoff kept about three
  fifths of what the predecessor held. An admission boundary, where only the final report
  crosses, kept about a third.
- **Losses compound.** By each boundary, a quarter of the whole ledger reached the
  successor.
- **Most of what was needed had been lost.** About two thirds of what a later actor
  needed had not been carried.
- **Rediscovery is frequent.** The player re-observed known facts about four times per
  game hour.
- **#372 is not directly comparable.** Its short runs carried 0.83 across their single
  handoff. Their hours include a first chunk, which cannot hold a rediscovery, so the
  per-hour rate is diluted more than #397's.

## The four #397 episodes

[ADR 009's problem statement](../decisions/009-curated-player.md#problem) names four
forgetting episodes. A probe suite must reproduce them as failing probes.

| Episode | Fact last carried, then lost at | Blinded annotation | After adjudication |
| --- | --- | --- | --- |
| A fishing rod on the floor (record `94ce47`); `sd1a5`–`sd1a7` tried to craft one | F30, lost at `sd1a2-002>sd1a3-001` | **Partly**: F30 (stored `94ce47`) is a compound fact: floor materials plus the rod. It fails with cost at `sd1a4-002>sd1a5-001`, but every event on it is about scanning the floor for crafting materials. The rod-crafting decision was recorded as a new fact (F90 in `sd1a5-001`), not as a need on F30 | Unchanged |
| Batteries in the locker (record `f49b80`); `sd1a3` had a dead flashlight in a dark basement | F4, lost at `sd1a2-002>sd1a3-001` | **Partly**: the need was attached to "the flashlight batteries are dead" (F37), which fails at `sd1a2-002>sd1a3-001`. The locker fact (F4) was not marked needed there | F4 fails with cost at `sd1a2-002>sd1a3-001` |
| 20 ration boxes in a cupboard (record `5db17f`); `sd1a6`–`sd1a7` worked on 25 kcal stalks | F38, lost at `sd1a5-002>sd1a6-001` | **Partly**: F38 fails at `sd1a2-002>sd1a3-001`, but was not marked needed when `sd1a6` chose among foods | F38 fails with cost at `sd1a5-002>sd1a6-001` |
| A roof tank with 18 L of clean water, in `sd1a3`'s summary only; `sd1a4` boiled lake water | F63, carried into `sd1a3-002`, lost at the admission `sd1a3-002>sd1a4-001` | **Missed**: the tank (F42, F63) was recorded in `sd1a3-001` but never marked needed. The annotators recorded the raw lake water instead | F63 fails with cost at `sd1a4-001>sd1a4-002`, one boundary after the loss, because the need falls in `sd1a4-002` |

**Adjudication.** The lead's adjudication
([`397/adjudication.jsonl`](../../data/evaluation/probes/397/adjudication.jsonl)) is
**unblinded**. Each line says it comes from the #397 record. It adds six `needed` and
`acted_without` events, each citing a frame the blinded annotators had already cited for
the same situation. It is kept separate from the blinded labels, and the results table and
`baseline.json` report both. With it, all four episodes are failing probes with cost.
- **Three of the four** fail at the boundary where the fact was lost.
- **The roof tank** fails one boundary later, at the handoff where it was needed. A probe
  sits at the boundary into the chunk that needed the fact, and retention shows where
  the loss happened.

**Finding: blinded annotation fully reproduced none of the four episodes, partly
reproduced three, and missed one.**
- **The rod hit was incidental.** It came through a compound fact whose recorded need was
  something else.
- **Each partial miss had the same shape.** The annotator recorded the fact, and saw the
  decision it bore on, but tied the need to a neighbouring fact or to a new one.

That failure belongs to the protocol, not the player. #178 should test held-out annotation
against a sample of episodes found another way before relying on blinded probe recall.

## Inter-rater check

A second annotator, in a fresh context with the same brief and the same incoming ledger,
re-annotated the chunks drawn by `random.Random(4492).sample` of the #397 order. The lead
matched new facts by statement; the matching is in
[`inter-rater-matching.json`](assets/probe-baseline-449/inter-rater-matching.json).
A one-to-two match counts as one matched cluster.

| Chunk | Carry labels: agreement (κ, n) | Earlier fact needed: agreement (κ) | New facts A / B, matched ÷ distinct |
| --- | --- | --- | --- |
| `sd1a2-001` | 96% (0.89, 23) | 74% (0.46) | 7 / 6, 4 ÷ 8 |
| `sd1a3-001` | 95% (0.86, 41) | 93% (0.85) | 22 / 13, 13 ÷ 22 |
| `sd1a7-002` | 97% (0.93, 119) | 94% (0.69) | 8 / 4, 4 ÷ 8 |

**Agreement is high on ledger facts.** Two annotators agree on whether a fact on the
ledger was carried (κ 0.86–0.93) and mostly on whether it was needed (κ 0.46–0.85).

**They differ on which new facts exist.**
- **Only half to three fifths matched.** Between 50% and 59% of distinct facts matched,
  and the second annotator recorded fewer.
- **The two raters split facts differently.** In `sd1a2-001`, rater A bundled the floor
  materials and the fishing rod into one fact. Rater B recorded them as two.
- **One match disagreed on direction.** One annotator put a foraging spot north of the
  shelter, the other south.

**Consequence.** Fact discovery is the noisy step. A study comparing memory arms should
fix one fact ledger and score every arm against it, as the protocol does, never
re-annotate per arm.

## Annotation cost

| Lineage | Chunks | Annotator tokens | Annotator time | Deviations |
| --- | ---: | ---: | ---: | --- |
| #397 (rater A) | 14 | 2,520,420, plus one interrupted attempt whose cost was not recorded | 44 min | 2 |
| #372 sample, per run (rater A) | 2 each | 248,000–253,000 | 3.0–3.6 min | 2 in all |
| #397 inter-rater sample (rater B) | 3 | 498,390 | 7.6 min | 0 |

**One day-scale lineage cost about 2.5 million annotator tokens**: about 180,000 per
chunk, which grows with chunk length and ledger size. For #178's power and cost gate, the
cost scales with lineage length and with the ledger each later chunk must carry. It has to
be priced at the annotator model's rates when #178 fixes its annotator.

**The deviations**, each recorded per chunk in `annotation-costs.jsonl`:
- One read-only shell call.
- One stray file reported by an annotator. The lead found nothing at the reported path.
- One chunk viewed slightly fewer frames than the coverage rule asks.
- One annotator wrote its output through a shell heredoc and read the ledger with
  `grep`, where the brief allowed only viewing files.
- One annotation attempt was interrupted when the lead session ended. It was redone.

## Deviations found in review

An independent review of this record found the following. Each is corrected in the
tracked files, and the figures above are recomputed from them.
- **The annotators' protocol text named a known episode.** The brief points annotators
  at the protocol's units and labels sections. When they read those sections, the
  examples held:
  - the fact "the cupboard in the shelter's kitchen holds ration boxes";
  - the record ID `5db17f`;
  - an uncarried line at `sd1a5-002>sd1a6-001`;
  - an `acted_without` event.

  That is the ration episode at its adjudicated boundary. The blinded `sd1a6-001`
  annotation has no event on the ration fact, so no effect on the labels is visible, but
  the blinding was weaker than stated. The examples are now neutral, and the protocol
  forbids evaluation content in them.
- **The cost rule.** The protocol said a cost event could fall in the needing chunk "or
  later". The code, the figures and the tests always used the needing chunk only. The
  protocol now matches the code. The wider rule would give 131 blinded and 134
  adjudicated probes failing with cost, not 120 and 123.
- **The carry rate was read as retention.** The cumulative rate was described as "how
  much of what was known crosses a boundary". Retention is now reported beside it, and
  the reading above uses retention.
- **The roof-tank episode's location.** The probe was said to fail "at the boundary the
  #397 record names". It fails one boundary after the loss. The table now gives both.
- **The fishing rod in the inter-rater matching.** The matching said rater A had not
  recorded the rod in `sd1a2-001`. A's compound fact F30 names it. The matching and the
  `sd1a2-001` figure (now 4 ÷ 8) are corrected.
- **Episode 1 was overstated.** It was called "reproduced". It is a partial hit through
  a compound fact, so blinded recall is now stated as zero full, three partial and one
  missed.
- **Smaller corrections:**
  - the lineage frame total is 1,933, not 1,932;
  - the adjudicated totals were added to the table;
  - each adjudication line now states its source;
  - the stray-file row was reconciled;
  - the #372 coverage substitution is recorded;
  - the scoring code now rejects duplicate carry lines, carry lines for facts that are
    not live, and adjudication rows that name no chunk. The tracked annotations trigger
    none of them.

## Limitations

- **One annotator model, one pass.** Every chunk had one annotator model and one pass.
  Rater B covered three chunks.
- **The lead's matching.** New facts were matched by the lead, which is a judgment.
- **Blinding was instructed, not enforced.** An annotator could have opened other files.
  Two annotators used shell commands they were told not to. None reported opening
  documents. The protocol's examples weakened the blinding (above).
- **#372 has no game clock in its timelines.** Its rediscovery rate per game hour rests on
  the run ledger's hours.
- **Probes are correlated within a lineage.** The lineage is the independent unit, and
  this record has one long lineage and six short ones.
