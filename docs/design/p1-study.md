---
owner: lead
status: proposed
date: 2026-11-08
scope: 'Pre-registration of the ADR 009 P1 offline study: arm A (no curator) against arm B (curator) on #382 held-out lineages, scored on confirmed re-observations (#491)'
review_trigger: Any change to the arms, probes, judges, metrics, thresholds, analysis script, held-out handling or spend; each is a recorded deviation once the owner approves P1
---

# P1 offline study: pre-registration

Protocol **p1-study/1**, written 8 November 2026 for [ADR 009](../decisions/009-curated-player.md#phases)
P1. It decides one question, offline and descriptively:

> Does a curator (arm B) put in front of a successor actor more of the information that
> actor later went back for than the simpler path without one (arm A)?

**Constraints.** The owner fixed these on 8 November 2026:
- **Study type.** A descriptive study with effect-size thresholds agreed in advance. #382's
  three lineages cannot support a significance test.
- **Curator model.** terra, the actor's model.
- **Spend.** An envelope of about $120, staged behind a pilot.
- **Primary probes.** Confirmed re-observations
  ([#490](../acceptance/2026-11-08-probe-validation-490.md#the-owners-decisions)).

Nothing here runs until the owner approves P1. The analysis is
[`tools/p1_analysis.py`](../../tools/p1_analysis.py). Its tests are in
[`tests/test_p1_analysis.py`](../../tests/test_p1_analysis.py), and its power simulation is
tracked in [`data/evaluation/p1/power.json`](../../data/evaluation/p1/power.json).

## Data and split

| Use | Lineages | Role |
| --- | --- | --- |
| Development | #397 `sd1a1`–`sd1a7` and the six-run #372 sample | Build, debug and pilot both arms; scored descriptively against the #490 ledgers; decide nothing |
| Evaluation (held out) | #382 `lh1` (3 runs), `lh2` (2), `lh3` (2) in `372-382-dev-loop` | The only data the decision uses |

**Held-out handling.**
- **Untouched so far.** No episode, probe, prompt, threshold or code choice has come from
  #382. This page uses only its game hours from the tracked run ledger: 24.8, 25.0 and
  0.55 in-play hours, and $30.44 of actor spend in all.
- **#178 writes the held-out probes** with blinded agents, before either arm is replayed on
  #382:
  - every candidate of the [frozen rule](probe-protocol.md#recall-check-against-independently-found-re-observations-490)
    (steps 1–4), with no sampling;
  - the tightened confirmation below;
  - the two descriptive ledgers under probe-protocol/1.
- **Frozen before replay.** The probes are frozen by digest, as `ledger.json` does for
  development, before any held-out replay.
- **The lead reads only counts and digests** of the held-out probes until scoring.
- **Scope.** The claim covers what #382 varies: one game, one start scenario (`S1`), one
  actor model and route, and the pre-emission player. It does not extend to other games,
  starts or models.

## Units

- **Boundary.** A handoff inside a run, or an admission boundary between runs of a lineage
  (probe-protocol/1).
- **Primary probe.** A confirmed, informative re-observation (below). Its boundary is the last
  boundary before the later frame's chunk.
- **Independent unit.** The lineage, so n = 3. Boundaries within a lineage share state, so
  the boundary bootstrap below is a descriptive uncertainty measure that understates the true
  uncertainty.

## Probes

**Candidates** follow probe-protocol/1 steps 1–4 unchanged: a 256-bit difference hash; a new
screen at 64 or more bits from the previous frame; a match within 16 bits of a frame from an
earlier chunk; a 20-frame cluster.

**Confirmation (tightened, per the owner's decision).** A blinded pairwise judge sees the two
frames of a candidate in a seeded order. It is not told the game, the study or which frame
came first, and it answers two questions:
1. **`same`.** Do both frames show the same specific information: the same list, contents,
   message or text, not merely the same kind of view?
2. **`informative`.** If so, is that information durable? An empty list, a search or help
   prompt, or a loading screen is not.

A primary probe has both answers "yes". Batches are at most 15 pairs, as in #490. The judge
model and brief are pinned under [Judges](#judges).

## Arms

Both arms are replayed over the same sealed held-out traces. At every boundary, each arm
produces the text the successor would have received. The two arms differ in one thing only:
where the pushed working set comes from.

| | Received text (both arms) | Pushed working set | Model calls |
| --- | --- | --- | --- |
| **Reference** (descriptive only) | What the actor actually received: prompt, handoff packet, previous report | None | None |
| **A: no curator** | Same | The actor's own `player-memory/2` records written before the boundary, live (not superseded), newest first | None |
| **B: curator** | Same; per D2 the outgoing summary still passes, labelled unverified | Facts in the curator's published knowledge that covers the chunk before the boundary, in scope, newest first | One curator session per chunk |

**Shared rules.**
- **Rendering.** One renderer turns each item into typed fields marked as fallible player
  knowledge. Both arms share it.
- **Cap.** The working set is capped at **2,000 tokens** in both arms, so the actor-side
  context is budget-matched. This is #455's recommended live-diff size. Items past the cap are
  dropped whole.
- **Root validation (#450).** It applies to both arms and changes no replayed text: the
  held-out packets were already sealed.

**Arm B's sessions.** Each runs on the [#489](https://github.com/CVX-Hull/enactive/issues/489)
curator host and proxy, inside the ADR 009 sandbox:
- the frozen prompt, with no game knowledge;
- terra at medium effort;
- the 24/12 image window;
- at most 120 requests.

**Arm B's inputs.**
- **What a session sees.** The projected trace up to its boundary, plus the actor's memory
  records written up to that point.
- **Repository.** Each lineage gets a fresh knowledge repository. Gate v0 judges every
  submission.
- **Lag.** The primary analysis uses the snapshot covering the chunk just ended, so it has
  no lag. Live, an admission boundary waits for that snapshot (D2). A handoff boundary
  would not, so a lag-respecting variant is reported: there, the snapshot comes from the
  previous boundary.
- **Repeats.** B runs **twice** on the held-out lineages, because curator sessions are not
  deterministic. A is deterministic and runs once.

**Freezing.** The arms' code, prompt, renderer, cap and host settings are fixed after the
development stage. They are committed with their digests before any held-out replay. Every
later change is a deviation.

## Judges

**Who judges.** Development agents on a pinned model, Sonnet 5.5, the model of the #490
judges. Every judge works in a fresh context, with only its batch file and the frames that
file names.

**Scoring judge.** It sees a primary probe's earlier frame and one arm's delivered text: the
received text plus the working set.
- **Blinding.** It is not told the arm. Items from all three texts (A, B1 and B2) are mixed
  across batches in a seeded order (`Random(4911)`). Batches hold at most 10 items.
- **Question.** Does the text state the specific information this frame shows?
- **Re-judging.** A `Random(4912)` sample of 20% of the scored items is judged again by
  fresh judges.

**False-fact auditor.** For each arm and each repeat, it receives a `Random(4913)` sample of
up to 40 delivered working-set items, together with the boundary's sealed frames and their
timelines. An item is **false** when a frame before the boundary contradicts it, or when it
was already invalidated before the boundary.

**Frozen briefs.**

> **Confirmation.** You compare pairs of screenshots for a study. Read only the file named
> here and the image files it lists; do not open any other file, run any command other than
> viewing files, or read documents or issues. The file [batch] lists pairs, each with an `id`
> and two image paths `A` and `B`. View both images of every pair. For each pair decide: do A
> and B show the same specific information — the same list of entries, the same container
> contents, the same message or the same text panel — not merely the same kind of screen?
> Small differences (a cursor, a highlighted row, a clock, a status value) do not matter. If
> they do, is that information durable — not an empty list, a search or help prompt, or a
> loading screen? Output only JSON Lines, one per pair in the given order:
> {"id":"<id>","same":true|false,"informative":true|false,"what":"<one line>"}.

> **Scoring.** You check whether a text states what a screenshot shows. Read only the file
> named here and the image files it lists; do not open any other file, run any command other
> than viewing files, or read documents or issues. The file [batch] lists items, each with an
> `id`, one image path `frame` and a `text`. For each item, view the image and decide: does
> the text state the specific information this image shows (its list, contents, message,
> text or map description), so that a reader of the text would already know it? A text that
> only mentions the same kind of screen or a related topic does not count. Output only JSON
> Lines, one per item in the given order: {"id":"<id>","stated":true|false,"why":"<one line>"}.

> **Audit.** You check statements against recorded screenshots. Read only the file named
> here and the timelines and image files it lists. For each item, decide whether any frame
> listed for it contradicts the statement, or shows it had stopped being true by the last
> listed frame. Output only JSON Lines: {"id":"<id>","false":true|false,"frame":"<source id or
> null>","why":"<one line>"}.

## Metrics

All metrics come from `p1-score/1` labels, through `tools/p1_analysis.py score`.

| Metric | Definition | Role |
| --- | --- | --- |
| **Re-observation recall** | Primary probes whose information the arm's text states ÷ primary probes, pooled over held-out lineages | **Primary** |
| Undelivered re-observations per game hour | (Primary probes − stated) ÷ in-play game hours | Reported. ADR 009's rediscovery metric, offline. On fixed probes it rescales recall, so it is not a second test |
| Audited false-fact rate | False ÷ audited working-set items, per arm and repeat | Guard |
| Curator ÷ actor spend | B's proxy-settled dollars ÷ the actor's dollars for the same runs, per repeat | Guard |
| Needed-fact recall (fact ledger) and query coverage | As frozen in `ledger.json`, scored by the same judge | Descriptive |
| Reference arm, A against reference, lag-respecting B, handoff and admission boundaries separately | | Descriptive |

## Decision rule

The rule was fixed before any held-out data was read, and is coded in `primary`, `guards` and
`decide`. B's two repeats are averaged at each boundary.

**Go** requires all of the following:
1. **Size.** Mean pooled recall, B − A, is **at least 0.15**.
2. **Each repeat.** Each B repeat is above A.
3. **Each lineage.** Every lineage with **20 or more** primary probes is above A, on the mean.
4. **Uncertainty.** The one-sided 95% bound of the mean difference is **above 0**. It comes
   from 2,000 resamples of boundaries within each lineage (`Random` seed 491).
5. **Re-judging.** Criteria 1–4 still hold when re-judged labels replace the first ones.
6. **False facts.** In each repeat, B's audited false-fact rate is **at most 0.10**, and at
   most A's plus 0.05.
7. **Cost.** In each repeat, curator spend is **at most 1.0×** the actor's.

**Other outcomes.**
- **Negative:** the mean difference is 0 or below.
- **Guard failed:** criteria 1–5 hold but 6 or 7 does not.
- **Inconclusive:** anything else.

A no-go is reported as it is. The design is not retuned on held-out data.

**Why 0.15.** The curator costs about 0.6–1.0× the actor's spend (#454). A gain smaller than
about a seventh of the probes would not pay for it.

## Power

The rule above passes the gate before spend.

| True effect (B − A) | 0 | 0.10 | 0.15 | 0.20 | 0.25 | 0.30 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P(go), 2,000 simulations | 0.009 | 0.147 | 0.342 | 0.582 | **0.811** | 0.933 |

- **Detection.** The rule detects an effect of 0.25, the effect of interest, 81% of the time.
- **False positives.** It fires without an effect 0.9% of the time.
- **Smaller effects.** Below 0.20 it misses more often than not. That is the cost of n = 3
  lineages.

**Assumptions** (in [`power.json`](../../data/evaluation/p1/power.json); from development data
and ledger aggregates only):
- **Lineage shape.** The held-out lineages have 7, 7 and 1 boundaries: game hours at #397's
  3.7 game hours per boundary, and at least one boundary per admission.
- **Probes per boundary.** Drawn from #397's sampled candidates per boundary, scaled to
  its 197 candidates, times the share of the #397 sample that was confirmed and informative
  (0.425). The median is 99 primary probes in all (10th–90th percentile 75–120).
- **Delivery rates.** A's per-boundary rate is drawn from #397's needed-fact carry rates.
  These stand in for an unknown quantity.
- **Variation.**
  - Lineage shift: SD 0.10.
  - Effect heterogeneity between lineages: SD 0.05.
  - Per-boundary variation between B's repeats: SD 0.05.
  - Judge error: 5% per label.
- **Not simulated:** the guards and re-judging.

**Stop before replay** if #178's held-out probes come to fewer than 40 primary probes, or no
lineage has 20. The design then cannot decide, and goes back to the owner.

## Spend and stop rules

All model spend goes through the curator proxy. Each stage has its own proxy cap. Any
unused amount does not move to another stage without the owner.

| Stage | Data | Cap | Purpose |
| --- | --- | ---: | --- |
| 1. Pilot | #372 `aidB3`, `ceil09` (development) | $11 | Per-chunk scheduling, the snapshot builder, cached share and cost per session |
| 2. Development | #397 `sd1a1`–`sd1a7` | $28 | Debug both arms end to end; descriptive scores against the #490 ledgers; then freeze the arms |
| 3. Held-out B, repeat 1 | `lh1`–`lh3` | $31 (1.0× the actor's $30.44) | Primary data |
| 4. Held-out B, repeat 2 | `lh1`–`lh3` | $31 | Primary data |
| Reserve | | $19 | Only to re-run a session lost to an infrastructure failure, once, unchanged, and recorded |
| **Total** | | **$120** | |

**Stop rules.**
- **Isolation incident.** Any incident (a sandbox escape, key exposure, a proxy breach or a
  revocation) stops every stage.
- **Stage caps.** A stage that reaches its cap stops there. Its partial data is reported.
- **Pilot.** The pilot goes back to the owner if a session costs more than 2× its #454
  equivalent, or if any session never writes.
- **Freeze.** Once held-out replay starts, nothing in the arms changes.
- **Probe shortage.** If #178 yields too few probes, everything stops before stage 3 (see
  [Power](#power)).

**No gameplay.** This study launches no game and spends nothing on the actor. Development-agent
tokens for #178's probes, the judges and the auditors are reported in tokens, not dollars.

## Cost estimate

**#489's check changed nothing.** The paid check
([record](../acceptance/2026-11-08-context-stability-489.md)) found that session affinity
leaves the cached share at about 3%. The cost per request was about the same as #454's: $0.093
against $0.106. Prompt caching therefore lowers nothing yet, and #454's per-session costs stand.

| Stage | Basis (#454 terra) | Estimate | Cap |
| --- | --- | ---: | ---: |
| Pilot | `aidB3` $4.76, `ceil09` $5.25 | about $10 | $11 |
| Development | #397, 7 sessions, $23.27 (0.61× the actor) | $23–28 | $28 |
| Each held-out repeat | 0.61–0.87× the actor's $30.44 | $19–27 | $31 |
| **Expected total** | | **$71–92** | $120 |

**Two uncertainties.**
- **Session length.** It varies widely: `sd1a1` took 67 requests in #454 and 15 in the #489
  check.
- **Per-chunk sessions.** Arm B runs one session per chunk, not per admission. That adds a
  fixed reading cost per session, so the estimate assumes the upper end.
- **The caps bound both.** A stage that would exceed its cap stops, and its partial data is
  reported.

**If prompt caching is fixed before the pilot,** for example by the #489 record's next checks,
costs fall and the caps stay as they are.

**Development-agent tokens,** not dollars:
- #178's held-out probes and ledgers: about 7M, scaled from #449 and #490;
- the scoring judges and re-judging: about 4M;
- the false-fact audit: about 1M.

## Analysis and reporting

`python -m tools.p1_analysis score --probes <held-out probes> --scores <labels> --hours <hours>`
writes `data/evaluation/p1/result.json` (`p1-result/1`).
- **Refusal.** It refuses a study in which any primary probe is unjudged for any arm or
  repeat, any label is duplicated, any arm is unknown, or any probe comes from a development
  lineage.
- **The record reports every figure in the metrics table,** plus every deviation. Each
  analysis beyond this page is a deviation, and is labelled post hoc.
- **What a go means.** A go is evidence for P1's live packages (ADR 009), not adoption.
  Adoption still needs the live non-inferiority guards.

## Limitations

- **Delivered is not used.** The offline replay scores what an arm would have delivered. It
  cannot show that the actor would have used it.
- **Visual re-observations only.** Information re-learned through a different screen is not
  a probe.
- **Few lineages.** With n = 3, the result is descriptive. The boundary bootstrap understates
  uncertainty.
- **No emissions.** #382 predates actor emissions (D10), so arm B's curator lacks the
  attention signals it would have live.
- **Assumed rates.** The power simulation's delivery rates stand in for an unknown quantity.
  #178's held-out probe counts update the probe-count assumption before replay.
