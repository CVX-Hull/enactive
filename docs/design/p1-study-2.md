---
owner: lead
status: proposed
date: 2026-11-09
scope: 'Pre-registration of the reshaped ADR 009 P1 offline study (p1-study/2): p1-study/1''s design with one new held-out lineage, lh4 (#522), added to #382 lh1–lh3 behind a re-run power gate (#178)'
review_trigger: Any change to the data, the new lineage's rules, the power plan, the stages or caps, the arms, the judges or the decision rule
---

# P1 offline study, second protocol: pre-registration

Protocol **p1-study/2**, written 9 November 2026 for [ADR 009](../decisions/009-curated-player.md#phases)
P1 (#178). It decides the same question as [p1-study/1](p1-study.md):

> Does a curator (arm B) put in front of a successor actor more of the information that actor
> later went back for than the simpler path without one (arm A)?

**Why a second protocol.** p1-study/1 stopped at its power gate before any replay or spend
([record](../acceptance/2026-11-09-p1-gate-178.md)). #382's three held-out lineages give 27
scoring units (11, 7 and 9) over 10 boundaries, nearly all singleton clusters. Criterion 3 needs
at least one lineage with 20 or more units, so a go was impossible. The owner chose to reshape P1
by adding one held-out lineage ("Add one held-out lineage", 9 November).

**This page is self-contained.** Units, Probes, Arms, Judges, Metrics, Decision rule, Analysis
and the stop rules are p1-study/1's text, carried over word for word except where a
**(p1-study/2)** marker or [Deviations](#deviations-from-p1-study1) says otherwise. The four briefs
are unchanged, and a test checks that the Confirmation brief is p1-study/1's.

**Owner decisions (8 and 9 November 2026), carried over:** a descriptive study with effect-size
thresholds agreed in advance; terra as the curator model; confirmed re-observations as the primary
probes. **(p1-study/2)** The envelope and the decisions under [Owner decisions](#owner-decisions)
are open. Nothing here runs until the owner approves this page.

The analysis is [`tools/p1_analysis.py`](../../tools/p1_analysis.py) and its tests are
[`tests/test_p1_analysis.py`](../../tests/test_p1_analysis.py). The plan is in
[`data/evaluation/p1/power-study-2.json`](../../data/evaluation/p1/power-study-2.json); a test checks
that the table under [Power](#power) renders it.

## Data and split

| Use | Lineages | Role |
| --- | --- | --- |
| Development | #397 `sd1a1`–`sd1a7` and the six-run #372 sample | Build, debug and pilot both arms; scored descriptively against the #490 ledgers; decide nothing |
| Evaluation (held out) | #382 `lh1` (3 runs), `lh2` (2), `lh3` (2) in `372-382-dev-loop`; **(p1-study/2)** `lh4` (#522) in `522-held-out` | The only data the decision uses |

**Held-out handling.**
- **lh1–lh3.** Their probes and ledgers are frozen as #178 wrote them
  ([`frozen.json`](../../data/evaluation/p1/held-out/frozen.json)) and are reused unchanged. The
  lead has read only their counts, digests and cluster structure.
- **(p1-study/2) lh4 is held out before it starts.** Until scoring, the lead and any operator read
  only counts, digests, cluster structure and the run-health aggregates listed under
  [Running lh4](#running-lh4). Nobody who writes probes, judges or develops the arms sees its
  frames, memory records, notes or reports.
- **The curator's access.** Probe and ledger files live in this repository's `data/evaluation/`,
  outside the curator sandbox's readable roots (ADR 009 "Isolation"), and are never passed to a
  session.
- **Scope (p1-study/2).** The claim covers what the four lineages vary: one game, one start
  scenario (`S1`), one actor model and route, and the pre-emission player in two versions
  (`509a9fd7` for lh1–lh3, lh4's source for lh4). It does not extend to other games, starts or
  models.

## Running lh4

**(p1-study/2)** #522 runs one lineage under the
[campaign-admission](../workflows/campaign-admission.md) procedure, by the lead alone, through the
prepared wrapper with its own project userdir, never fullscreen. The frozen inputs are #397's
([record](../acceptance/2026-11-07-seven-day-397.md#frozen-inputs)) except where this section says
otherwise. Before any spend, #522 posts its frozen addendum: source, binary, adapter and operator
tool digests, and the cumulative-spend check.

- **Source.** The current `main` at #522's freeze, in a clean run worktree, with a fresh adapter
  build and its native check (an owner decision; the alternative is #397's `db38b30`).
- **Start.** S1 Evacuee, no aid, the unchanged player guide; a pristine userdir and a fresh store,
  `player-memory-lh4.sqlite3`. #382's continuation prompt, byte for byte.
- **Route and limits.** #397's: terra, medium effort, at most 400 charged attempts, 7,200 host
  seconds and 7,800 custodian seconds per admission.
- **Names.** Admissions `lh4a1`, `lh4a2`, …, ledger study `522`, lineage `L4`, arm `p1-held-out`;
  one userdir and one store. The raw evidence is sealed as study `522-held-out`.
- **Envelope.** **$80** under the actual-spend admission rule: an admission starts only while the
  lineage's actual spend plus twice its largest admission stays within $80, the largest taken as
  $7.06 (#382's largest) until one completes. The cumulative total stays within the standing
  $1,000, checked at the freeze.
- **Operator tooling.** Adapted from #397's sealed scripts (`397-seven-day`) into
  `.runtime/worktrees/522/operator/`, reviewed before the freeze. It never displays a frame, a
  memory record, a handoff summary, a final report or the continuation prompt it passes on.

**Stop rules** (the lineage ends at the first):
1. **Size.** The admission after which the lineage has **12 boundaries**: handoffs inside an
   admission plus admission boundaries, counted from actor directories.
2. **Death.**
3. **Ten admissions.**
4. **The envelope.**
5. **Slow:** two consecutive custody stops with one cause.

The lead stops and asks the owner on a continuity failure, a run-monitor fault, a death the
monitor and the evaluator disagree on, a third custody stop, any needed change to the frozen
package, or **a lineage that ends before 12 boundaries**.

**What the lead may read** between admissions: attempts, decisions, dollars, wall and host seconds,
custody stops, outcome codes, boundary and actor counts, the evaluator's aggregate metrics in the
run ledger, and the run monitor's parsed answers. Nothing else from lh4.

**#382's D4 check between admissions** (looping, a spend overrun, custody hits) stays with the lead,
from aggregates only: the evaluator's longest stall, spend against the forecast, custody stops.

**The run monitor.** Every check #397's lead made from frames (a setup restart, continuity at each
boundary, a death) is made instead by a fresh development agent per admission, pinned as the judges are, that writes probes for no study and develops no arm. It
writes its answer to a named file and replies only "done". An operator script checks the file
against the schema and prints only the parsed fields. The operator tool refuses admission N+1
unless admission N's answer has `continues` true (or null for admission 1), `dead` false and
`fault` false; `setup_restart` is allowed only for admission 1, under #382's D7. Its brief:

> **Run monitor.** You check one segment of a recorded game session for its operator. Read only
> the file named here and the image files it lists; do not open any other file, run any command
> other than viewing files and writing your answer, or read documents or issues. The file [batch]
> lists the previous segment's last frames, if any, and this segment's first frames, last frames
> and the frames around each handoff. Answer only: (1) does this segment continue the same
> character in the same world as the previous segment's last frames (null if there is none)?
> (2) does the segment begin by setting up a new game and saving it before any play? (3) is the
> character dead in any listed frame? (4) does any listed frame show something other than the game
> in a window: an error dialog, a system screen, a full-screen game, or a debug, cheat or editor
> screen? Do not describe the game or what the character does. Write exactly one JSON line to
> [answer] and reply only "done":
> {"continues":true|false|null,"setup_restart":true|false,"dead":true|false,"fault":true|false,"frames":{"continues":"<source id or null>","setup_restart":"<source id or null>","dead":"<source id or null>","fault":"<source id or null>"}}.

**Waived for lh4 until scoring, and recorded:** #397's day checks (P1 makes no survival claim),
the lead's per-admission review records, and campaign-admission's finding tables, which cite
observations. After scoring the lead may review lh4's frames and add findings to the record.

**Records.** A dated run record with only the aggregates above, ledger rows, and the sealed
evidence. The record names no game content.

## Integrating lh4, its probes and the gate

**(p1-study/2)** In this order, after #522 ends:

1. **The lineage map ($0, one PR under #178), before anything else reads lh4:**
   - `HELD_OUT` in `tools/p1_analysis.py` and the development-refusal tuple in
     `tools/probe_validation.py` gain `lh4` with its actual admission names. p1-study/1's planning
     keeps `STUDY_1_HELD_OUT`, and this page's plan keeps `STUDY_1_BOUNDARIES` and its single
     `--probes` file (#382's), so neither changes;
   - `simulate`, `units`, `rejudge` and `score` take `--probes` once per held-out directory,
     refuse a file whose sha256 differs from its directory's `frozen.json`, and record each file's
     digest in their output; the gate writes to an explicit
     `data/evaluation/p1/power-held-out-study-2.json`, never p1-study/1's `power-held-out.json`;
   - the `held-out-*` steps of `tools/probe_validation.py` gain a lineage subset and a source study
     per lineage (`372-382-dev-loop` for lh1–lh3, `522-held-out` for lh4), writing lh4's files to
     `data/evaluation/p1/held-out-lh4/` and leaving `held-out/` untouched;
   - `tools/curator_host/p1_replay.py` gains lh4's directory, sessions and store, and the curator
     shadow's held-out name guard (`tools/curator_host/shadow.py`) covers `lh4`.

   It lands before stage 1, so the arms freeze in stage 2 includes it.
2. **lh4's probes,** exactly as #178 wrote lh1–lh3's: every probe-protocol/1 candidate (steps 1–4),
   unsampled; blinded confirmation under the Confirmation brief; the two descriptive ledgers; each
   agent writing to a named file and replying only with a line count; then a freeze by digest in
   `held-out-lh4/frozen.json`.
3. **The gate before replay:** `python -m tools.p1_analysis simulate --probes
   data/evaluation/p1/held-out/probes.jsonl --probes data/evaluation/p1/held-out-lh4/probes.jsonl
   --out data/evaluation/p1/power-held-out-study-2.json`, the unchanged rule on the four
   lineages' actual units and clusters. **If it fails, no further stage starts** (stages 1–2
   included) and the design goes back to the owner. Nothing is retuned on held-out data.

## Units

- **Boundary.** A handoff inside a run, or an admission boundary between runs of a lineage
  (probe-protocol/1).
- **Primary probe.** A confirmed, informative re-observation. Its boundary is the last boundary
  before the later frame's chunk.
- **Information cluster.** Probes within one lineage whose earlier frames are **all** within 16
  difference-hash bits of each other (complete linkage in probe-id order, `clusters`). Nothing
  chains, because frames 16 bits apart can show different lists, and the same information is
  often re-observed at several boundaries
  ([probe validation](../acceptance/2026-11-08-probe-validation-490.md)). The result reports the
  distribution of cluster sizes.
- **Scoring unit.** One per lineage, boundary and cluster (`units`). Re-observing the same
  information several times after one boundary counts once. Only the unit's probe, the one with
  the lowest id, is judged.
- **Independent unit.** The lineage, so **(p1-study/2)** n = 4. Uncertainty comes from resampling
  clusters within lineages. That accounts for repeats across boundaries, but it still understates
  the uncertainty from having only four lineages.

## Probes

**Candidates** follow probe-protocol/1 steps 1–4 unchanged. Each probe row also records its
earlier frame's hash (`earlier_dhash`) for clustering.

**Confirmation (tightened, per the owner's decision).** A blinded pairwise judge sees the two
frames of a candidate in a seeded order. It is not told the game, the study or which frame came
first, and answers two questions:
1. **`same`.** Do both frames show the same specific information?
2. **`informative`.** If so, is that information durable? An empty list, a search or help
   prompt, or a loading screen is not.

A primary probe has both answers "yes". Batches are at most 15 pairs, and the judge is pinned
under [Judges](#judges).

## Arms

Both arms are replayed over the same sealed held-out traces. At every boundary, each arm produces
the text the successor would have received live.

| | Received text (both arms, identical) | Pushed working set | Model calls |
| --- | --- | --- | --- |
| **Reference** (descriptive only) | What the actor actually received: prompt, handoff packet, previous report | None | None |
| **A: no curator** | Same | The actor's own `player-memory/2` records written before the boundary, live, newest first | None |
| **B: curator** | Same | Facts in scope from the latest snapshot the curator would have published before the boundary, newest first | One curator session per admission |

**What makes the comparison fair.**
- **One difference.** The arms differ only in where the working set comes from. The received
  text is byte-identical, including the outgoing summary, with no arm-specific label.
- **Rendering (p1-study/2).** One renderer (#462) writes every item as one plain statement line
  under one header, with no kind label, marked as fallible player knowledge. A's record folds its
  `data` into its statement. Neither arm's provenance appears in its text.
- **Cap.** Both arms are capped at **2,000 tokens** ([#455's recommended live-diff size](snapshot-diff-cost.md)),
  **(p1-study/2)** counted as ceil(UTF-8 bytes ÷ 4). Items past the cap are dropped whole.
  Delivered tokens per arm and boundary are reported, because the cap is an upper bound, not a
  match.
- **Root validation (#450).** It applies to both arms and changes no replayed text: the held-out
  packets were already sealed.

**Arm B's sessions follow live timing (D2, D15).**
- **When it runs.** One curator session at the end of each admission covers it. At an admission
  boundary, live play waits for that snapshot, so B delivers it.
- **Handoffs.** At a handoff boundary, live play does not wait, so B delivers the latest snapshot
  published before it: the previous admission's. The first admission's handoffs get no
  snapshot, only the received text.
- **Cutoffs (p1-study/2).** A boundary's working set holds what was written before the
  successor's first operation (#462).
- **Bias.** This favours neither arm on timing, and it makes B's cost directly comparable with
  #454's.

**Arm B's settings.**
- **Host.** The [#489](../acceptance/2026-11-08-context-stability-489.md) curator host and proxy,
  inside the ADR 009 sandbox, with the frozen prompt (no game knowledge).
- **Model.** terra at medium effort.
- **Limits.** A 24/12 image window, at most 120 requests per session and **(p1-study/2)** $12 per
  session.
- **Inputs.** The projected trace of the admission, plus the actor's memory records up to its end.
- **Repository.** A fresh knowledge repository per lineage; gate v0 judges every submission.
- **Repeats.** B runs **twice** on the held-out lineages, because curator sessions are not
  deterministic. A is deterministic and runs once.

**Freezing.** After the development stage, the arms are fixed: code, prompt, renderer, cap and host
settings. They are committed with their digests **(p1-study/2:** `p1_replay freeze`**)** before any held-out replay,
and every later change is a deviation.

**(p1-study/2) Two steps before the freeze, in stage 2:**
- **The format check ($0).** lh4 is recorded on a newer player than every trace the arms were built
  on. Arm A's items and arm B's per-admission schedule are built on lh4 with no curator session, by
  a tripwire that prints only counts and exception class names. A failure stops the study and goes
  to the owner; nobody debugs it on lh4. The owner may then approve one development admission on
  lh4's source (about $6) to reproduce and fix it on development data.
- **A's punctuation tell,** if the owner approves the fix: a record whose text ends in `!` or `?`
  gets no added `.` before its data.

## Judges

**Pinning.** Every judge, auditor and guesser is pinned:
- a development agent, run as a general-purpose subagent of the lead's coding host;
- the model of the #490 judges (named in [its record](../acceptance/2026-11-08-probe-validation-490.md#how-it-was-done)), at the host's default effort;
- a fresh context, and only its batch file and the frames that file names.

The host version is recorded with each batch.

**Scoring judge.** It sees a unit's earlier frame and one arm's delivered text: the received text
plus the working set. Its question: does the text state the specific information this frame
shows?
- **Mixing.** Items from A, B1 and B2 are mixed in a seeded order (`Random(4911)`), at most 10 to a
  batch.
- **Separation.** No batch holds two texts for the same unit.
- **Re-judging.** Fresh judges score exactly the seeded 20% sample again
  (`tools.p1_analysis rejudge`, `Random(4912)`). Scoring refuses any other set. Agreement, percent
  and Cohen's kappa, is reported as the judges' repeat variance.

**Arm-guessing check.** It runs before scoring. A fresh judge sees 30 delivered texts, 15 from A
and 15 from B in a seeded order, and sorts each into one of two unnamed systems. If its split
matches the arms on **21 or more** of 30, the rendering leaks the arm. Scoring is then refused
(`score`) until the rendering is fixed, and the fix is recorded.

**False-fact auditor.**
- **Sample.** For each arm and each repeat, `Random(4913)` draws up to 40 (working-set item,
  boundary) pairs from all delivered items.
- **What the auditor sees.** The item, rendered as for the arm-blind judges, with:
  - the frames the item cites;
  - the predecessor chunk's frames under the probe-protocol/1 coverage rule.

  Batches hold at most 10 items, and the auditor is not told the arm.
- **Verdict.** An item is **false** when a listed frame contradicts it, or shows it had stopped
  being true before the boundary.

**Delivery (p1-study/2).** Every judge, writer, annotator, auditor and guesser writes its JSON Lines
to a named file and replies only with a line count, as #178's did.

**Frozen briefs.**

> **Confirmation.** You compare pairs of screenshots for a study. Read only the file named here
> and the image files it lists; do not open any other file, run any command other than viewing
> files, or read documents or issues. The file [batch] lists pairs, each with an `id` and two
> image paths `A` and `B`. View both images of every pair. For each pair decide: do A and B show
> the same specific information — the same list of entries, the same container contents, the
> same message or the same text panel — not merely the same kind of screen? Small differences (a
> cursor, a highlighted row, a clock, a status value) do not matter. If they do, is that
> information durable — not an empty list, a search or help prompt, or a loading screen? Output
> only JSON Lines, one per pair in the given order:
> {"id":"<id>","same":true|false,"informative":true|false,"what":"<one line>"}.

> **Scoring.** You check whether a text states what a screenshot shows. Read only the file named
> here and the image files it lists; do not open any other file, run any command other than
> viewing files, or read documents or issues. The file [batch] lists items, each with an `id`,
> one image path `frame` and a `text`. For each item, view the image and decide: does the text
> state the specific information this image shows (its list, contents, message, text or map
> description), so that a reader of the text would already know it? A text that only mentions
> the same kind of screen or a related topic does not count. Output only JSON Lines, one per item
> in the given order: {"id":"<id>","stated":true|false,"why":"<one line>"}.

> **Arm guess.** Each text in the file [batch] was produced by one of two systems that summarise
> what a game player knows. Read only that file. For each text, guess which system produced it,
> "1" or "2", consistently. Output only JSON Lines: {"id":"<id>","system":"1"|"2"}.

> **Audit.** You check statements against recorded screenshots. Read only the file named here and
> the timelines and image files it lists. For each item, decide whether any frame listed for it
> contradicts the statement, or shows it had stopped being true by the last listed frame. Output
> only JSON Lines: {"id":"<id>","false":true|false,"frame":"<source id or null>","why":"<one
> line>"}.

**Scoring the arm guess.** `arm_guessing` maps the guesser's labels "1" and "2" to arms by whichever
mapping scores higher, and requires exactly 30 guesses, 15 per arm. The limit is fixed so that a
guesser that cannot tell the arms apart reaches it at most 5% of the time, counting the better of
the two mappings: 2 × P(Binomial(30, ½) ≥ 21) = 0.043.

## Metrics

All metrics come from `p1-score/1` rows, through `tools/p1_analysis.py score`.

| Metric | Definition | Role |
| --- | --- | --- |
| **Re-observation recall** | Units whose information the arm's text states ÷ units, pooled over held-out lineages | **Primary** |
| Undelivered re-observations per game hour | (Units − stated) ÷ in-play game hours | Reported. ADR 009's rediscovery metric, offline; on fixed units it rescales recall, so it is not a second test |
| Audited false-fact rate, with its one-sided 95% Clopper–Pearson upper bound | False ÷ audited items, per arm and repeat | Guard |
| Curator ÷ actor spend | B's proxy-settled dollars ÷ the actor's dollars for the same runs, per repeat | Guard |
| Judge agreement; arm-guess share; delivered tokens per arm | | Reported |
| Needed-fact recall (fact ledger) and query coverage | As frozen in **(p1-study/2)** each held-out directory's ledgers, scored by the same judge | Descriptive |
| Reference arm; A against reference; handoff and admission boundaries separately; **(p1-study/2)** lh4 against lh1–lh3 | | Descriptive |

**Multiplicity.** The decision is one conjunctive rule, fixed in advance. Everything else on this
page is descriptive and decides nothing, so no correction for multiple comparisons applies.

## Decision rule

The rule was fixed before any held-out data was read, and is coded in `primary`, `guards` and
`score`. B's two repeats are averaged per unit.

**Go** requires all of the following:
1. **Size.** Mean pooled recall, B − A, is **at least 0.15**.
2. **Each repeat.** Each B repeat is above A.
3. **Each lineage (p1-study/2 wording, as coded).** At least one lineage has **20 or more** units,
   and every such lineage is above A, on the mean.
4. **Uncertainty.** The one-sided **97.5%** bound of the mean difference is **above 0**. It comes
   from 2,000 resamples of information clusters within each lineage (seed 491).
5. **Re-judging.** Criteria 1–4 still hold with the seeded re-judged labels substituted.
6. **False facts.** In each repeat, B's audited false-fact rate is **at most 0.10**, its upper
   bound is **at most 0.20**, and it is at most A's plus 0.05.
7. **Cost.** In each repeat, curator spend is **at most 1.0×** the actor's. A held-out repeat that
   reaches its stage cap has failed this guard. Its partial labels are not scored.

**Other outcomes.**
- **Negative:** the mean difference is 0 or below.
- **Guard failed:** criteria 1–5 hold but 6 or 7 does not, or a held-out cap was reached.
- **Inconclusive:** anything else.

A no-go is reported as it is. The design is not retuned on held-out data.

**Why 0.15.** The curator costs about 0.6–1.0× the actor's spend (#454, #489). A gain under about a
seventh of the re-observations would not pay for it.

## Power

**(p1-study/2)** The effect of interest stays **0.30**, and the gate before spend (ADR 009) still
requires P(go) of 0.05 or less with no effect and 0.80 or more at the effect of interest.

The plan is `python -m tools.p1_analysis plan --probes data/evaluation/p1/held-out/probes.jsonl`:
- **lh1–lh3:** their actual units and clusters (27 units, 26 clusters);
- **a simulated lh4** run to a given number of boundaries, each boundary's unit count drawn from
  lh1–lh3's per-boundary counts (10 boundaries; one yielded none);
- **lh4's clustering:** each unit repeats a cluster of an earlier lh4 boundary with probability
  1 − 1/(cluster mean), else is new; the first unit is always new.

Everything else is p1-study/1's simulation: a cluster's delivery rate drawn from #397's
needed-fact carry rates (#449); a lineage shift with SD 0.10; effect heterogeneity between lineages
with SD 0.05; variation between B's repeats with SD 0.05; 5% judge error per label; no judge bias;
the guards and re-judging not simulated. 2,000 simulations per figure (standard error at most
0.011), each variant with its own seeded stream.

| lh4 boundaries | Cluster mean | P(lh4 under 20 units) | 0 | 0.10 | 0.15 | 0.20 | 0.25 | 0.30 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 1.04 | 0.354 | 0.020 | 0.120 | 0.224 | 0.348 | 0.458 | 0.553 |
| 10 | 1.04 | 0.079 | 0.019 | 0.163 | 0.323 | 0.507 | 0.668 | 0.805 |
| **12** | **1.04** | **0.015** | **0.025** | **0.180** | **0.359** | **0.552** | **0.750** | **0.884** |
| 14 | 1.04 | 0.001 | 0.015 | 0.178 | 0.374 | 0.575 | 0.775 | 0.906 |
| 8 | 1.4 | 0.365 | 0.020 | 0.121 | 0.203 | 0.311 | 0.421 | 0.515 |
| 10 | 1.4 | 0.084 | 0.025 | 0.155 | 0.290 | 0.462 | 0.625 | 0.757 |
| 12 | 1.4 | 0.015 | 0.033 | 0.180 | 0.362 | 0.510 | 0.682 | 0.829 |
| 14 | 1.4 | 0.003 | 0.025 | 0.176 | 0.365 | 0.537 | 0.716 | 0.862 |
| 8 | 3.0 | 0.362 | 0.024 | 0.113 | 0.182 | 0.272 | 0.365 | 0.471 |
| 10 | 3.0 | 0.077 | 0.036 | 0.175 | 0.244 | 0.401 | 0.539 | 0.649 |
| 12 | 3.0 | 0.013 | 0.033 | 0.185 | 0.281 | 0.428 | 0.558 | 0.709 |
| 14 | 3.0 | 0.002 | 0.038 | 0.171 | 0.269 | 0.456 | 0.580 | 0.724 |

**Reading it.**
- **Planning assumption:** lh4 runs to the size rule's **12 boundaries**, clustered as lh1–lh3
  were (1.04 units per cluster, 27 ÷ 26). Its gate passes, with P(go) 0.884 at the effect of
  interest and 0.025 with no effect.
- **Why 12, not 10.** At 10 boundaries, lh4 falls under 20 units, where a go is impossible, 8% of
  the time, and the gate passes only by 0.005. At 12 that risk is 1.5%, and the gate still passes
  if lh4 repeats somewhat more (1.4: 0.829).
- **If lh4 repeats as much as p1-study/1's planning assumed (3.0),** no size in reach passes. The
  re-run gate on the actual probes says so before any replay.
- **Not modelled,** as in p1-study/1: B's first-admission handoffs, which get no snapshot under D2,
  so the plan is somewhat optimistic; variation between lineages in units per boundary.
- **This plan was made after seeing lh1–lh3's structure,** which the held-out discipline allows; no
  outcome of theirs has been read.

## Spend and stop rules

All model spend goes through the curator proxy. Each stage has its own proxy cap, and unused
amounts do not move between stages without the owner.

| Stage | Data | Cap | Purpose |
| --- | --- | ---: | --- |
| **(p1-study/2)** 0. lh4 | #522 | $80 envelope | The new held-out lineage, then its integration, probes and the gate |
| 1. Pilot | #372 `aidB3`, `ceil09` (development) | $12 | Per-admission scheduling, the snapshot builder and renderer, cached share and cost per session |
| 2. Development | #397 `sd1a1`–`sd1a7` | $26 | Debug both arms end to end; descriptive scores against the #490 ledgers; the arm-guessing check; **(p1-study/2)** the format check; then freeze the arms |
| 3. Held-out B, repeat 1 | `lh1`–`lh4` | **(p1-study/2)** 1.0× the actor's spend on lh1–lh4: $30.46 plus lh4's actual, fixed when #522 ends | Primary data |
| 4. Held-out B, repeat 2 | `lh1`–`lh4` | The same | Primary data |
| Reserve | | $20 | Only to re-run a session lost to an infrastructure failure, once, unchanged, and recorded |

**(p1-study/2)** p1-study/1's "Total $120" row is replaced by this: the caps sum to $198.92 plus
twice lh4's actual spend, about $299 if lh4 spends $50 and $359 if it spends its whole envelope.

**Stop rules.**
- **Isolation incident.** Any incident (a sandbox escape, key exposure, a proxy breach or a
  revocation) stops every stage.
- **Stage caps.**
  - A development stage that reaches its cap stops there, and its partial data is reported.
  - A held-out stage that reaches its cap records the cost guard as failed (above). If repeat 1
    reaches its cap, repeat 2 does not run.
- **Pilot.**
  - **Cost.** It goes back to the owner if a session costs more than 2× the same session's #454
    cost (`aidB3` $4.76, `ceil09` $5.25).
  - **Output.** It also goes back if any session never writes.
- **Freeze.** Once held-out replay starts, nothing in the arms changes.
- **Gate (p1-study/2).** The re-run gate on lh1–lh4 can stop the study before stage 1.
- **(p1-study/2) Operator-enforced.** The code does not tie caps to stages (#462's review), so the
  operator passes each stage's cap explicitly and records it with the stage's label, does not
  start repeat 2 after a capped repeat 1, and starts no stage after an isolation incident.

**Gameplay (p1-study/2).** Stage 0 is the only gameplay. No other game launches, and nothing else is
spent on the actor. Development-agent tokens are reported in tokens, not dollars. They cover the
probes, the run monitor, the judges, the auditors and the guesser.

## Cost estimate

| Item | Basis | Estimate |
| --- | --- | ---: |
| lh4 | 12 boundaries are 13 chunks: about 7 admissions at #382's 1.86 chunks per admission (#397: 2.0), so 6–8 at $5–7 | $30–56 |
| Pilot and development | p1-study/1's: #454 terra sessions | $33–36 |
| Each held-out repeat | 0.61–0.87× the actor's $60–87 on lh1–lh4 (#454) | $37–75 |
| **Expected total** | | **$137–242** |

Development-agent tokens: lh4's probes and ledgers about 3–4M (lh1–lh3's 3.37M for 13 chunks); the
run monitor under 0.3M; scoring, re-judging, audit and the guess check about 4M.

## Analysis and reporting

`python -m tools.p1_analysis score --probes <held-out probes> --probes <lh4 probes>` **(p1-study/2:
the second file)** `--scores <rows> --hours <hours>` writes `data/evaluation/p1/result.json` (`p1-result/1`).
- **Refusals.** It refuses when:
  - a unit is unjudged for some arm or repeat;
  - a label is duplicated;
  - the re-judged set is not the seeded sample;
  - the arm-guessing check is missing or above its limit;
  - an audit or cost row is malformed;
  - a probe comes from a development lineage;
  - **(p1-study/2)** a probe file's digest differs from its freeze.
- **The record reports every figure in the metrics table,** plus every deviation. Any analysis
  beyond this page is a deviation, and is labelled post hoc.
- **What a go means.** A go is evidence for P1's live packages (ADR 009), not adoption. Adoption
  still needs the live non-inferiority guards.

## Deviations from p1-study/1

1. **Data.** A fourth held-out lineage, lh4, run for the study (#522), so n = 4 and the scope
   spans two player versions.
2. **Criterion 3's wording** made to say what the code computes.
3. **Planning.** The power plan uses lh1–lh3's actual structure and a simulated lh4 from their
   per-boundary counts; p1-study/1's used development data and assumed cluster sizes.
4. **Stages.** A gameplay stage 0; the gate before stages 1–2, not only before stage 3; held-out
   caps re-based on four lineages, using the ledger's $30.46 for lh1–lh3 (p1-study/1 said $30.44).
5. **The run monitor** replaces the lead's frame checks, and the waivers above, for a held-out
   lineage.
6. **The format check** before the arms freeze, and the optional punctuation fix.
7. **Operator-enforced stop rules,** written out.
8. **#462's choices,** which p1-study/1 left open: the token count, the folding of `data`, no kind
   label, the $12 session cap and the cutoff at the successor's first operation.
9. **Delivery by file** for every judge-like agent, as #178 already did.

## Owner decisions

Put to the owner with this page:
1. **Approve p1-study/2**, the $80 lh4 envelope and the caps above.
2. **lh4's source:** the current `main` at the freeze (recommended: the player an adoption would
   migrate) or #397's `db38b30` (closest to the development data).
3. **#462's recorded choices** (Deviation 8).
4. **A's punctuation tell:** fix it in stage 2, before the freeze (recommended), or leave it to the
   arm-guess check.

## Limitations

- **Delivered is not used.** The offline replay scores what an arm would have delivered, not
  whether the actor would have used it.
- **Visual re-observations only.** Information re-learned through a different screen is not a
  probe.
- **Four lineages (p1-study/2: was three).** The result is descriptive, and the cluster bootstrap
  understates the uncertainty that comes from having only four lineages. The study detects only
  large effects (see [Power](#power)).
- **No emissions.** **(p1-study/2: all four)** held-out lineages predate actor emissions (D10), so
  the curator lacks the attention signals it would have live.
- **Assumed rates.** **(p1-study/2: the plan's)** delivery rates and lh4's clustering are
  assumptions. The re-run gate replaces the second before replay.
- **(p1-study/2) The lead's prior exposure to lh1–lh3.** The lead operated #382 live on 7 November,
  before it was held out, and wrote its per-admission review comments on #382. On 9 November,
  searching #382 for its D4 rule while drafting this page, the lead re-read four of those D4
  summaries from lh1–lh2 (menu stalls and their length). Neither is probe or ledger content, and
  the frozen probes were written by blinded agents, but the lead is not naive to those lineages.
- **(p1-study/2) Two player versions.** lh4's player differs from lh1–lh3's: `player_handoff` is
  always listed, the host warns before it must stop the actor, and notes keep their first-sent
  place (#496). Lineage-level variation is modelled; a systematic change in where handoffs fall is
  not.
- **(p1-study/2) The design followed a failed gate.** It was reshaped after lh1–lh3's counts were
  seen, but before any outcome.
