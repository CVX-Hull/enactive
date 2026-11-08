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

## How it was done

**Annotators.** One general-purpose agent annotated each chunk (one actor's span) in a
fresh context, chunk by chunk in lineage order, from the frozen brief in the protocol. Each
was told to read only the protocol's sections, the generated timeline and the frames. It
was not told the hypotheses or any known episode. The lead did not edit annotations. Each
returned chunk was validated against the whole lineage before the next began.

**Frame coverage.** Annotators viewed every third changed frame, every frame in a chunk's
last five operations, and every frame they cited. They viewed 699 frames for #397 (1,932
in the lineage) and 515 for the #372 sample. A pilot on `sd1a1-001`, run before the
coverage rule existed, viewed 16 of 133 frames and is excluded.

**Samples.**
- **#397:** all 14 chunks, 13 boundaries.
- **#372:** the runs drawn by `random.Random(449).sample` from the 26 eligible runs:
  aidB3, ceil09, ceil07, ceil05, aidB9 and aidA5. That is 12 chunks and 6 in-run handoffs.
  #372's evaluator records were not sealed with its sessions, so its timelines have no
  game clock or change flags. Its game hours come from the run ledger.

## Results

| Lineage | Facts | Live facts at boundaries | Carried | Needed facts | Needed and carried | Probes | Failing | Failing with cost | Rediscoveries | Game hours | Per game hour |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| #397, in-admission handoffs (7) | | 490 | 157 (0.32) | 129 | 60 (0.47) | | | | | | |
| #397, admission boundaries (6) | | 422 | 81 (0.19) | 108 | 25 (0.23) | | | | | | |
| **#397, all 13 boundaries** | 139 | 912 | 238 (**0.26**) | 237 | 85 (**0.36**) | 237 | 152 | 120 | 210 | 47.79 | **4.39** |
| #372 sample, in-run handoffs (6) | 141 | 70 | 58 (**0.83**) | 20 | 17 | 20 | 3 | 3 | 4 | 5.37 | 0.75 |

**Carry rate** is carried live facts over live facts at a boundary. **Needed** counts live
facts that a later decision in the successor's span depended on. **A probe fails** when
the needed fact was not carried. It **fails with cost** when the successor then re-observed
the fact or acted without it.

**Probes are not independent.** A fact needed across many boundaries contributes one
probe per boundary. For example, the starting inventory and the ration calorie value
recur in most #397 boundaries.

**What the figures say, as development evidence only.** Within one short run, actor
handoffs carried most of what was known. Across #397's admission boundaries, where only
the final report crosses, about a fifth of what was known survived. About three quarters
of what a later actor needed had not been carried. The player re-observed known facts
about four times per game hour.

## The four #397 episodes

[ADR 009's problem statement](../decisions/009-curated-player.md#problem) names four
forgetting episodes. A probe suite must reproduce them as failing probes.

| Episode | Blinded annotation | After adjudication |
| --- | --- | --- |
| A fishing rod on the floor (record `94ce47`); `sd1a5`–`sd1a7` tried to craft one | **Reproduced**: fact F30 (stored `94ce47`) fails with cost at `sd1a4-002>sd1a5-001` and the boundaries around it | Unchanged |
| Batteries in the locker (record `f49b80`); `sd1a3` had a dead flashlight in a dark basement | **Partly**: the need was attached to "the flashlight batteries are dead" (F37), which fails at `sd1a2-002>sd1a3-001`. The locker fact (F4, stored `f49b80`) was not marked needed there | F4 fails with cost at `sd1a2-002>sd1a3-001` |
| 20 ration boxes in a cupboard (record `5db17f`); `sd1a6`–`sd1a7` worked on 25 kcal stalks | **Partly**: the cupboard fact (F38) fails at `sd1a2-002>sd1a3-001`, but was not marked needed when `sd1a6` chose among foods | F38 fails with cost at `sd1a5-002>sd1a6-001` |
| A roof tank with 18 L of clean water, in `sd1a3`'s summary only; `sd1a4` boiled lake water | **Missed**: the tank (F42, F63) was recorded in `sd1a3-001` but never marked needed. The annotators recorded the raw lake water instead | F63 fails with cost at `sd1a4-001>sd1a4-002` |

**Adjudication.** The lead's adjudication
([`397/adjudication.jsonl`](../../data/evaluation/probes/397/adjudication.jsonl)) is
**unblinded**: it comes from the #397 record. It adds six `needed` and `acted_without`
events, each citing a frame the blinded annotators had already cited for the same
situation. It is kept separate from the blinded labels, and `baseline.json` reports both.
With it, all four episodes are failing probes with cost at the boundaries the #397 record
names.

**Finding: blinded recall of known episodes was one of four, plus two in part.** Each
miss had the same shape. The annotator recorded the fact, and saw the decision it bore
on, but tied the need to a neighbouring fact. That failure belongs to the protocol, not
the player. #178 should test held-out annotation against a sample of episodes found
another way before relying on blinded probe recall.

## Inter-rater check

A second annotator, in a fresh context with the same brief and the same incoming ledger,
re-annotated the chunks drawn by `random.Random(4492).sample` of the #397 order. The lead
matched new facts by statement; the matching is in
[`inter-rater-matching.json`](../../data/evaluation/probes/inter-rater-matching.json).

| Chunk | Carry labels: agreement (κ, n) | Earlier fact needed: agreement (κ) | New facts A / B, matched ÷ distinct |
| --- | --- | --- | --- |
| `sd1a2-001` | 96% (0.89, 23) | 74% (0.46) | 7 / 6, 4 ÷ 9 |
| `sd1a3-001` | 95% (0.86, 41) | 93% (0.85) | 22 / 13, 13 ÷ 22 |
| `sd1a7-002` | 97% (0.93, 119) | 94% (0.69) | 8 / 4, 4 ÷ 8 |

**Agreement is high on ledger facts.** Two annotators agree on whether a fact on the
ledger was carried (κ 0.86–0.93) and mostly on whether it was needed (κ 0.46–0.85).

**They differ on which new facts exist.** Only 44–59% of distinct facts matched, and the
second annotator recorded fewer. One match even disagreed on direction: one annotator put
a foraging spot north of the shelter, the other south. One fact that bears on the
fishing-rod episode, a rod on a bench, was recorded only by the second annotator.

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
- One stray file reported by an annotator. It was not found at the reported path.
- One chunk viewed slightly fewer frames than the coverage rule asks.
- One annotator wrote its output through a shell heredoc and read the ledger with
  `grep`, where the brief allowed only viewing files.
- One annotation attempt was interrupted when the lead session ended. It was redone.

## Limitations

- **One annotator model, one pass.** Every chunk had one annotator model and one pass.
  Rater B covered three chunks.
- **The lead's matching.** New facts were matched by the lead, which is a judgment.
- **Blinding was instructed, not enforced.** An annotator could have opened other files.
  Two annotators used shell commands they were told not to. None reported opening
  documents.
- **#372 has no game clock in its timelines.** Its rediscovery rate per game hour rests on
  the run ledger's hours.
- **Probes are correlated within a lineage.** The lineage is the independent unit, and
  this record has one long lineage and six short ones.
