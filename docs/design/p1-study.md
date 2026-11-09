---
owner: lead
status: historical
date: 2026-11-08
scope: 'Pre-registration of the ADR 009 P1 offline study: arm A (no curator) against arm B (curator) on #382 held-out lineages, scored on confirmed re-observations (#491); stopped at its power gate before any replay'
---

# P1 offline study: pre-registration

**Outcome.** On 9 November 2026 the held-out power re-check failed its gate, and the owner
stopped P1 there, before any replay or spend. Nothing below ran past the held-out probes
([record](../acceptance/2026-11-09-p1-gate-178.md)). A reshaped P1 is a new protocol.

Protocol **p1-study/1**, written 8 November 2026 for [ADR 009](../decisions/009-curated-player.md#phases)
P1. It decides one question, offline and descriptively:

> Does a curator (arm B) put in front of a successor actor more of the information that actor
> later went back for than the simpler path without one (arm A)?

**Owner decisions (8 November 2026).**
- **Study type.** A descriptive study with effect-size thresholds agreed in advance. #382's
  three lineages cannot support a significance test.
- **Curator model.** terra, the actor's model.
- **Spend.** An envelope of about $120, staged behind a pilot.
- **Primary probes.** Confirmed re-observations
  ([#490](../acceptance/2026-11-08-probe-validation-490.md#the-owners-decisions)).

Nothing here runs until the owner approves P1. The analysis is
[`tools/p1_analysis.py`](../../tools/p1_analysis.py), and its tests are
[`tests/test_p1_analysis.py`](../../tests/test_p1_analysis.py). The power simulation is in
[`data/evaluation/p1/power.json`](../../data/evaluation/p1/power.json); a test checks that the
table under [Power](#power) renders it.

## Data and split

| Use | Lineages | Role |
| --- | --- | --- |
| Development | #397 `sd1a1`–`sd1a7` and the six-run #372 sample | Build, debug and pilot both arms; scored descriptively against the #490 ledgers; decide nothing |
| Evaluation (held out) | #382 `lh1` (3 runs), `lh2` (2), `lh3` (2) in `372-382-dev-loop` | The only data the decision uses |

**Held-out handling.**
- **Untouched so far.** No episode, probe, prompt, threshold or code choice has come from #382.
  This page uses only aggregates from the tracked run ledger
  ([`runs.jsonl`](../../data/evaluation/runs.jsonl), [`run-metrics.jsonl`](../../data/evaluation/run-metrics.jsonl)):
  in-play hours (24.8, 25.0 and 0.55) and the actor's spend ($30.44 in all). They set the simulation's shape and the stage caps.
- **#178 writes the held-out probes** with blinded agents, before either arm is replayed on #382:
  - every candidate of the [frozen rule](probe-protocol.md#recall-check-against-independently-found-re-observations-490)
    (steps 1–4), with no sampling;
  - the tightened confirmation below;
  - the two descriptive ledgers under probe-protocol/1.

  They are frozen by digest before any held-out replay.
- **The lead's access.** Until scoring, the lead reads only counts, digests and the cluster
  structure that `tools.p1_analysis simulate --probes` reports.
- **The curator's access.** Probe and ledger files live in this repository's
  `data/evaluation/`, outside the curator sandbox's readable roots (ADR 009 "Isolation"), and are
  never passed to a session.
- **Scope.** The claim covers what #382 varies: one game, one start scenario (`S1`), one actor model
  and route, and the pre-emission player. It does not extend to other games, starts or models.

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
- **Independent unit.** The lineage, so n = 3. Uncertainty comes from resampling clusters within
  lineages. That accounts for repeats across boundaries, but it still understates the
  uncertainty from having only three lineages.

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
- **Rendering.** One renderer gives every item the same typed fields, marked as fallible player
  knowledge. Neither arm's provenance appears in its text.
- **Cap.** Both arms are capped at **2,000 tokens** ([#455's recommended live-diff size](snapshot-diff-cost.md)). Items past
  the cap are dropped whole. Delivered tokens per arm and boundary are reported, because the cap
  is an upper bound, not a match.
- **Root validation (#450).** It applies to both arms and changes no replayed text: the held-out
  packets were already sealed.

**Arm B's sessions follow live timing (D2, D15).**
- **When it runs.** One curator session at the end of each admission covers it. At an admission
  boundary, live play waits for that snapshot, so B delivers it.
- **Handoffs.** At a handoff boundary, live play does not wait, so B delivers the latest snapshot
  published before it: the previous admission's. The first admission's handoffs get no
  snapshot, only the received text.
- **Bias.** This favours neither arm on timing, and it makes B's cost directly comparable with
  #454's.

**Arm B's settings.**
- **Host.** The [#489](../acceptance/2026-11-08-context-stability-489.md) curator host and proxy,
  inside the ADR 009 sandbox, with the frozen prompt (no game knowledge).
- **Model.** terra at medium effort.
- **Limits.** A 24/12 image window, and at most 120 requests per session.
- **Inputs.** The projected trace of the admission, plus the actor's memory records up to its end.
- **Repository.** A fresh knowledge repository per lineage; gate v0 judges every submission.
- **Repeats.** B runs **twice** on the held-out lineages, because curator sessions are not
  deterministic. A is deterministic and runs once.

**Freezing.** After the development stage, the arms are fixed: code, prompt, renderer, cap and host
settings. They are committed with their digests before any held-out replay, and every later
change is a deviation.

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
| Needed-fact recall (fact ledger) and query coverage | As frozen in `ledger.json`, scored by the same judge | Descriptive |
| Reference arm; A against reference; handoff and admission boundaries separately | | Descriptive |

**Multiplicity.** The decision is one conjunctive rule, fixed in advance. Everything else on this
page is descriptive and decides nothing, so no correction for multiple comparisons applies.

## Decision rule

The rule was fixed before any held-out data was read, and is coded in `primary`, `guards` and
`score`. B's two repeats are averaged per unit.

**Go** requires all of the following:
1. **Size.** Mean pooled recall, B − A, is **at least 0.15**.
2. **Each repeat.** Each B repeat is above A.
3. **Each lineage.** Every lineage with **20 or more** units is above A, on the mean.
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

The effect of interest is **0.30**. **The gate before spend** (ADR 009) requires:
- P(go) of 0.05 or less with no effect;
- P(go) of 0.80 or more at the effect of interest;

both under the planning assumption: on average **3 units per information cluster**, and no judge
bias. Each figure below comes from 5,000 simulations, with a standard error of at most 0.007.

| True effect (B − A) | 0 | 0.10 | 0.15 | 0.20 | 0.25 | 0.30 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P(go), planning assumption | 0.031 | 0.183 | 0.314 | 0.488 | 0.666 | 0.810 |
| 1.4 units per cluster (#397's 20% sample: a lower bound on clustering) | 0.016 | 0.161 | 0.343 | 0.562 | 0.766 | 0.902 |
| 6 units per cluster (pessimistic) | 0.034 | 0.170 | 0.289 | 0.451 | 0.608 | 0.754 |
| Planning, with judges 5 points more likely to say "stated" for B | 0.064 | 0.259 | 0.421 | 0.607 | 0.737 | 0.856 |

**The gate passes narrowly, and only because its target moved.**
- **The target moved.** The first version of this page set the effect of interest at 0.25. The
  clustered simulation then gave P(go) of 0.666 there, so the effect of interest was raised to
  0.30 after seeing that result. This is recorded as a deviation from the design as first
  written.
- **At the new target,** the gate passes by 0.010 at the planning assumption: 0.810 against 0.80.
  It fails if information repeats more (6 units per cluster: 0.754).
- **The cluster mean.** #397's sample shows 1.4 units per cluster, but that is a 20% sample, which
  understates repetition. Its full lineage likely repeats about 4–5 times. Three per cluster is
  a middle value, not a conservative one.
- **Judge bias toward B** is the main threat to false positives (0.064 at 5 points). Hence the
  arm-blind rendering and the guessing check.
- **Not modelled.** The simulation applies one effect at every boundary, while under D2 timing B
  delivers nothing extra at the first admission's handoffs. That makes the simulated power
  somewhat optimistic.
- **For the owner's go/no-go.** The study can detect only a large effect (0.30). Running it at
  this power, rather than reshaping it as ADR 009 says a design that misses its gate must be,
  needs the owner's explicit acceptance, recorded as a deviation if the held-out re-check also
  falls short.

**Assumptions** (in [`power.json`](../../data/evaluation/p1/power.json); from development data and
ledger aggregates only):
- **Lineage shape.** 7, 7 and 1 boundaries: game hours at #397's 3.7 per boundary, and at least
  one boundary per admission.
- **Probes per boundary.** #397's sampled candidates per boundary, scaled to its 197, times the
  confirmed-and-informative share (0.425).
- **Clustering.** Each unit is new information with probability 1/3 at the planning assumption;
  otherwise it repeats a cluster from an earlier boundary.
- **Outcomes.** Shared by every unit of a cluster, per arm and repeat.
- **Delivery rates.** A's cluster-level rate is drawn from #397's needed-fact carry rates, which
  stand in for an unknown quantity.
- **Variation.** Lineage shift SD 0.10; effect heterogeneity between lineages SD 0.05; variation
  between B's repeats SD 0.05; judge error 5% per label.
- **Not simulated:** the guards and re-judging.

**Stop before replay.** Once #178 has frozen the held-out probes,
`python -m tools.p1_analysis simulate --probes <file>` re-runs the simulation on their actual units
and clusters, with the same rule. If its gate fails, held-out replay does not start, and the
design goes back to the owner.

## Spend and stop rules

All model spend goes through the curator proxy. Each stage has its own proxy cap, and unused
amounts do not move between stages without the owner.

| Stage | Data | Cap | Purpose |
| --- | --- | ---: | --- |
| 1. Pilot | #372 `aidB3`, `ceil09` (development) | $12 | Per-admission scheduling, the snapshot builder and renderer, cached share and cost per session |
| 2. Development | #397 `sd1a1`–`sd1a7` | $26 | Debug both arms end to end; descriptive scores against the #490 ledgers; the arm-guessing check; then freeze the arms |
| 3. Held-out B, repeat 1 | `lh1`–`lh3` | $31 (1.0× the actor's $30.44) | Primary data |
| 4. Held-out B, repeat 2 | `lh1`–`lh3` | $31 | Primary data |
| Reserve | | $20 | Only to re-run a session lost to an infrastructure failure, once, unchanged, and recorded |
| **Total** | | **$120** | |

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
- **Gate.** The held-out power re-check above can stop the study before stage 3.

**No gameplay.** No game launches and nothing is spent on the actor. Development-agent tokens are
reported in tokens, not dollars. They cover #178's probes, the judges, the auditors and the
guesser.

## Cost estimate

**Basis.** Arm B runs per admission, as #454 did, so #454's per-session costs apply directly;
the #489 check's cost per request matches #454's
([record](../acceptance/2026-11-08-context-stability-489.md)).

| Stage | Basis (#454 terra) | Estimate | Cap |
| --- | --- | ---: | ---: |
| Pilot | `aidB3` $4.76, `ceil09` $5.25 | about $10 | $12 |
| Development | #397, 7 sessions, $23.27 (0.61× the actor) | $23–26 | $26 |
| Each held-out repeat | 7 sessions at 0.61–0.87× the actor's $30.44 | $19–27 | $31 |
| **Expected total** | | **$71–90** | $120 |

**Three uncertainties.**
- **Memory records.** B reads the actor's memory records; #454's #397 sessions did not.
- **Session length.** It varies widely between runs of the same session
  ([#454](../acceptance/2026-11-08-curator-shadow-454.md),
  [#489](../acceptance/2026-11-08-context-stability-489.md)).
- **Development cap.** The development cap is close to its basis. Development data decides
  nothing, so a stop there costs only debugging coverage.

**If prompt caching is fixed before the pilot,** for example by the #489 record's next checks,
costs fall and the caps stay as they are.

**Development-agent tokens,** not dollars:
- #178's held-out probes and ledgers: about 7M, scaled from #449 and #490;
- the scoring judges and re-judging: about 4M;
- the audit and the guessing check: about 1M.

## Analysis and reporting

`python -m tools.p1_analysis score --probes <held-out probes> --scores <rows> --hours <hours>`
writes `data/evaluation/p1/result.json` (`p1-result/1`).
- **Refusals.** It refuses when:
  - a unit is unjudged for some arm or repeat;
  - a label is duplicated;
  - the re-judged set is not the seeded sample;
  - the arm-guessing check is missing or above its limit;
  - an audit or cost row is malformed;
  - a probe comes from a development lineage.
- **The record reports every figure in the metrics table,** plus every deviation. Any analysis
  beyond this page is a deviation, and is labelled post hoc.
- **What a go means.** A go is evidence for P1's live packages (ADR 009), not adoption. Adoption
  still needs the live non-inferiority guards.

## Limitations

- **Delivered is not used.** The offline replay scores what an arm would have delivered, not
  whether the actor would have used it.
- **Visual re-observations only.** Information re-learned through a different screen is not a
  probe.
- **Three lineages.** The result is descriptive, and the cluster bootstrap understates the
  uncertainty that comes from having only three lineages. The study detects only large effects
  (see [Power](#power)).
- **No emissions.** #382 predates actor emissions (D10), so the curator lacks the attention
  signals it would have live.
- **Assumed rates.** The power simulation's delivery rates and cluster sizes are assumptions. The
  held-out re-check replaces the second before replay.
