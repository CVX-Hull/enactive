---
owner: lead
status: historical
kind: study
date: '2026-11-13'
scope: 'Scoring the game-neutral curator (#460, curator-fact/3 with articles and a grooming session after each admission) against the brief gate''s sealed store on the seven-day lineage''s admissions, judged blind by model judges on sd1a5 to sd1a7 (#618), with the store''s size after grooming. Curator sessions only, $16.62 of a $50 cap; judging on host agents; no game launch'
---

# Scoring the game-neutral curator on the seven-day lineage (#618)

## At a glance

- **Question.** Does the game-neutral curator, with a grooming session after each
  admission, keep a store whose facts later play needs, compared with the curator of the
  [brief gate](2026-11-13-curator-brief-gate.md), and how large does its store grow?
- **Relevance.** Judged blind on `sd1a5` to `sd1a7`, a fact of the groomed store was acted
  on or found again in **34.7%** of the admissions it was known in (interval over the three
  admissions 26.9% to 40.4%), against **15.8%** for the brief gate's store (8.1% to 25.5%).
- **Size.** The groomed store ends with **77 current facts in 32 articles** (170,201
  bytes) after seven admissions; the brief gate's store held 172 current facts after six.
  Before each judged admission the groomed store held 46, 57 and 67 facts, the brief gate's
  138, 157 and 172.
- **What the smaller store loses.** The brief gate's store held more facts later needed in
  absolute terms: 59 distinct facts against 36. Grooming keeps a denser store, not a
  superset.
- **Precision.** Of 30 random facts per store checked against their cited frames, none was
  unsupported: 23 supported and 7 partly for the groomed store, 25 and 5 for the brief
  gate's.
- **Agreement.** The first two judges agreed on 92% of the groomed store's pairs (κ 0.76)
  and 93% of the brief gate's (κ 0.63), but on the pairs that drive the rates only 68% and
  69% (κ 0.45 and 0.49). The rates rest on adjudicated model-judge labels and are not
  corrected against a human truth.
- **Cost.** \$16.62 of the \$50 cap: \$13.36 for the seven admissions and \$3.25 for the
  seven grooming sessions. Every session sealed and every submission was accepted; nothing
  was re-run.
- **The pilot's store.** The final groomed version, `v18`, is the withholding pilot's store
  (#619): commit `ea9f7097c8804df7825337946c6a2f045ac00cb8`, `facts.jsonl` sha256
  `3842153d…57dc`, sealed in the `curator-scoring-618` study.
- **Not known.** Whether either store helps when delivered: neither was delivered here, so
  "acted in line" can come from what the player knew anyway. This measures relevance, not
  use. One lineage of one game.

## Method

1. **The grooming step** (#631, merged first at \$0): `tools/curator_host/shadow.py --groom`.
2. **Runs.** `--arm terra --lineage 397 --groom --session-cap-usd 12 --max-output-tokens
   32768 --stop-on-reject --stop-on-abort`: `sd1a1` alone (cap \$50), read end to end
   (15 facts, 5 articles; grooming revised 6 facts and filed every fact), then `sd1a2` to
   `sd1a7` on the same repository (cap \$45.75). Outputs:
   `.runtime/curator-shadow/scoring-618-first` and `-rest`, repository
   `.runtime/knowledge/shadow-454/scoring-618-first`.
3. **Judged facts.** For each judged admission, each store's current facts as published
   before it: the groomed store at `v9`, `v13`, `v15`; the brief gate's sealed store at
   `v4`, `v5`, `v6`. Both stores' facts went into one `judged-facts/1` file under the route
   `withheld` (neither was delivered), with ids prefixed by store, so the same judges saw
   the same frames and could not tell the stores apart (blind packets give each fact an
   opaque id).
4. **Judge tooling** at main `4157eb0d` (`tools/memory_measure.py` sha256 `3d3b8d96…`,
   `judge.py` `8019a3ea…`), before delivery (#461) changes it. `packets blind`, seed 618:
   nine packets of 17 to 30 frames and 184 to 239 facts, about 33,000 to 42,000 tokens.
5. **Judges.** Two clean-context host agents (Claude Opus 5.5) per packet, and a third on
   all nine packets, which held the 170 disputed pairs; `agreement` adjudicated 1,911 pairs.
6. **Scores** from `adjudicated.json`: per store, the share of (fact, admission) pairs whose
   adjudicated label in some window was `in_line` or `found_again`, with a bootstrap over the
   three admissions (2,000 draws, seed 618); distinct facts ever needed; stale or false
   among applied labels; the first two judges' agreement over all pairs and over the pairs
   either gave an applied label.
7. **Precision.** 30 random current facts from each store's final version (seed 618;
   groomed `v18`, brief gate `v6`), anonymised, checked by one clean-context reviewer
   against every frame each cites.

## Result

| | Groomed curator | Brief gate's curator |
| --- | ---: | ---: |
| Pairs judged | 510 | 1,401 |
| Labels: in line / found again / against / did not apply / cannot tell | 50 / 30 / 1 / 412 / 17 | 38 / 52 / 1 / 1,268 / 42 |
| Fact-admissions acted on or found again | 59 of 170, 34.7% (26.9 to 40.4) | 74 of 467, 15.8% (8.1 to 25.5) |
| Distinct facts ever acted on or found again | 36 of 68 | 59 of 180 |
| Stale or false among applied labels | 3 of 81 | 5 of 91 |
| First two judges, all pairs: agreement, κ | 0.922, 0.762 | 0.934, 0.632 |
| First two judges, pairs driving the rate: agreement, κ (pairs) | 0.678, 0.452 (90) | 0.685, 0.492 (108) |
| Precision, 30 facts: supported / partly / unsupported | 23 / 7 / 0 | 25 / 5 / 0 |

**The groomed store's size, after each grooming session:**

| After | Current facts (all) | Current articles (all) | Bytes |
| --- | ---: | ---: | ---: |
| `sd1a1` | 15 (21) | 6 (10) | 23,312 |
| `sd1a2` | 27 (33) | 9 (21) | 43,898 |
| `sd1a3` | 41 (50) | 15 (35) | 72,895 |
| `sd1a4` | 46 (58) | 17 (42) | 88,234 |
| `sd1a5` | 57 (73) | 19 (52) | 112,849 |
| `sd1a6` | 67 (86) | 25 (69) | 143,583 |
| `sd1a7` | 77 (97) | 32 (83) | 170,201 |

**Cost per session** (proxy ledgers): admissions \$3.91, \$1.35, \$2.84, \$0.34, \$1.14,
\$2.12, \$1.66; grooming \$0.33, \$0.53, \$0.63, \$0.08, \$0.76, \$0.27, \$0.66.

## Interpretation

- **Grooming keeps the store small and relevant.** About a third the size of the brief
  gate's, with twice the share of facts that later play needs. It still grows with play,
  by about ten current facts an admission; no cap was needed over seven admissions.
- **It is not a superset.** The brief gate's larger store covered more needed facts. A
  delivered briefing carries leads and an index, so fewer, better-filed facts may serve
  the player better, but that is what the withholding pilot measures, not this study.
- **The judges are the weak part.** On the pairs that decide the rates their κ is under
  0.5, below the measure gate's 0.80; most disagreements are between `in_line`,
  `found_again` and `did_not_apply`. The direction of the difference holds in every one
  of the three admissions (groomed 39%, 40%, 27% against 14%, 25%, 8%).

## Deviations

- **The run covered `sd1a1` to `sd1a7`; the brief gate's store covers `sd1a1` to `sd1a6`.**
  The baseline before `sd1a7` is its `v6`, after `sd1a6`, as for the groomed store.
- **The third judge settled 9 pairs with a label neither first judge gave** (`third_alone`).
- **`python -m tools.memory_screen_checks store` read only the repository's last four
  versions**: it reads loose Git objects, and Git had packed the earlier ones. The size
  table above was read from each version's `facts.jsonl` with Git. The reader's limit is
  reported with this record, not changed here.
- **Weighted score.** The issue asked for facts needed later weighted above facts never
  needed; the share of needed fact-admissions is reported in place of an invented weight.

## Evidence

Sealed as `curator-scoring-618` ([index](../../data/evidence/index.json)): the two run
directories, the knowledge repository, the judge run (packets, events, adjudication) and
its inputs (the facts file and the scripts that built it, every judge's answers, the
precision sample and verdicts).
