---
owner: lead
status: active
date: 2026-11-08
scope: 'Fact-level probe annotation over sealed traces for ADR 009 offline evaluation (#449), reused by #178 for held-out probes'
review_trigger: A change to the labels, the probe rule, the rates, the blinding, the sampling or the annotator brief
---

# Probe annotation protocol

Protocol **probe-protocol/1**, written 8 November 2026. It turns a sealed lineage into
**probes** of the form "at this boundary, a query about X should surface Y". It also
yields baseline rates:
- **carry rate per boundary**: how much of the ledger so far reaches the successor
  (cumulative: a fact lost once stays uncarried at later boundaries);
- **retention per boundary**: how much of what the predecessor held crosses this
  boundary;
- **rediscovery rate per game hour**: how often the player re-observes what was known
  before a boundary.

P1 compares memory arms offline by what each would have put in front of the actor at
these probes ([ADR 009](../decisions/009-curated-player.md#evaluation-and-studies)).

Probes are **evaluation data**. They never reach the playing system or the curator
(ADR008; ADR 009 "Isolation"). They live in this repository's `data/evaluation/probes/`.
The curator's sandbox cannot read the repository.

## Data

| Use | Lineages | Notes |
| --- | --- | --- |
| Development (this protocol's first application, #449) | `397-seven-day`: `sd1a1`–`sd1a7`; `372-382-dev-loop`: a seeded sample of #372's short runs (below) | Probes built here fit and debug the system; they decide nothing |
| Held out (#178) | #382's `lh1`–`lh3` in `372-382-dev-loop` | Not opened, annotated or summarised here |

**#372 sample.** Eligible runs are those in `data/evaluation/run-metrics.jsonl` whose arm
is one of `pilot`, `pre-loop`, `ceiling`, `zoom-aid`, `game-help-aid` or
`reflection-aid`, and whose sealed session has two actor directories (one in-run
handoff). The sample is six runs drawn with Python's `random.Random(449).sample` over the
sorted eligible run names. It is fixed before any #372 annotation, and the draw is
recorded with the results.

## Units

- **Chunk.** One actor's span in a sealed session: everything between its first and last
  operation. A lineage is annotated chunk by chunk in order.
- **Boundary.** The step from one chunk to the next. It is either a handoff inside an
  admission (`r2-001>r2-002`) or an admission boundary (`r2-002>r3-001`).
  The successor's "What this actor received" section shows exactly what crossed: the
  prompt, handoff packet and previous report.
- **Fact.** A durable proposition about the world, the character or the player's own
  plans or procedures that a later decision could depend on. A fact is either visible
  in a frame or stated in the player's own text (memory records, packet, report).
  Facts are written in the annotator's words, at the level a query could name, for
  example "the shed beside the north gate holds a coil of rope". Transient
  states, such as a single frame's cursor position, are not facts.

## Labels

Each chunk's annotation is JSON Lines with three line types.

```json
{"type":"fact","id":"F12","statement":"…","category":"resource","observed":"<source id>","stored":"<record id prefix>"}
{"type":"carry","fact":"F12","boundary":"<chunk>><next chunk>","carried":false,"where":null}
{"type":"event","fact":"F12","event":"used","frame":"<source id>","note":"…"}
```

- **`fact`.** A new fact first observed in this chunk.
  - `category`: one of `place`, `resource`, `item`, `hazard`, `procedure`, `self`,
    `plan` or `other`.
  - `observed`: the frame (source ID) where it is first visible, or `text` when it
    appears only in the player's text.
  - `stored`: the ID prefix of a memory record holding it, or `null`.
- **`carry`.** Written at the start of a chunk, once for **every live fact**: one
  observed earlier and not yet invalidated.
  - `carried` is `true` when the successor's received text states the fact or a
    query-equivalent of it.
  - `where`: `prompt`, `packet` or `report`.
- **`event`.** Something this chunk did with an earlier fact.
  - `used`: acted on it, consistent with knowing it.
  - `needed`: a decision for which the fact was relevant, whatever the player did.
  - `rediscovered`: the fact was re-observed, for example by opening the same
    container again.
  - `acted_without`: acted contrary to it, for example searching elsewhere for what it
    says is here, or doing without it.
  - `invalidated`: the fact stopped being true.

  Each event cites a frame and a one-line note. `rediscovered` and `acted_without`
  imply `needed`; annotators also write `needed` on the first such frame.

## Probes and rates (computed, not annotated)

[`harness/evaluation/core/probes.py`](../../harness/evaluation/core/probes.py) derives
these from the labels.
- **Probe.** For a fact F and its first `needed` event at frame t in chunk c, take the
  last boundary b before c that F crossed while live (F observed in an earlier chunk).
  That defines one probe `(b, F)`: at b, a query about F's subject should surface F.
  It **fails** when F was not carried at b.
- **Failing probe with cost.** A failing probe whose fact also has a `rediscovered` or
  `acted_without` event in chunk c, the chunk that needed it. (This text first said "in
  chunk c or later"; the code and the #449 figures always used chunk c. Corrected after
  review on 8 November 2026. The wider rule would give 131 rather than 120 for #397's
  blinded annotation.)
- **Carry rate** at b: carried live facts ÷ live facts. Reported per boundary kind
  (handoff, admission) and pooled. It is also reported over needed facts only. It is
  **cumulative ledger coverage**: a fact lost at one boundary counts as uncarried at
  every later boundary, so it does not say where a loss happened.
- **Retention** at b: carried facts ÷ live facts the predecessor chunk **held**. A fact
  is held if the predecessor observed it, received it at its own boundary, or has an
  event on it. This rate locates losses.
- **Rediscovery rate**: `rediscovered` events for facts observed before the most recent
  boundary, ÷ the lineage's in-play game hours. Game hours come from the sealed
  evaluation stores' game clock, not from annotators. The hours include the first
  chunk, which cannot contain a rediscovery. Lineages with few chunks are therefore
  diluted more, and comparisons across lineages of different lengths should say so.

## Frame coverage

An annotator views these frames:
- every third changed frame, counting from the chunk's first;
- every frame in the chunk's last five operations;
- every frame cited in a `fact` or `event` line.

Where a timeline has no change flags (sessions whose evaluator records were not sealed),
"every third changed frame" becomes every third frame. It may view more. Each chunk ends
with `frames_viewed`. A pilot on `sd1a1-001` before
this rule viewed 16 of 133 frames and leaned on the player's own records. It is kept as
a pilot and is not used for the rates.

## Adjudication

A blinded pass can miss a known failure. A lead may then add an **adjudication layer**,
which is unblinded and kept apart from the blinded labels. It lives in `adjudication.jsonl`
beside the chunks, as `event` lines with a `chunk` field. Every line cites a frame and
says where its knowledge came from. Results are reported with and without it. The layer
may add events only: it never edits or removes a blinded label.

## Blinding

Annotators receive only three things: this protocol's [labels](#labels) and
[units](#units) sections, the generated timelines, and frame paths in the sealed
evidence. They are told not to open repository documents, issues or acceptance records,
and not to read the evaluator's derived `events` table. They are not told which
episodes, facts or outcomes anyone expects. The lead does not edit annotations. A
correction is a new, recorded line with its reason.

**The protocol's own examples carry no evaluation content.** Annotators read the units
and labels sections, so no example there may name a fact, record ID, boundary or outcome
from a lineage under study. A change to those sections is reviewed against this rule.
In the #449 application the examples did name one of the known episodes; the
[record](../acceptance/2026-11-08-probe-baseline-449.md#deviations-found-in-review) lists
this as a deviation.

**Limitation:** an annotator agent with file tools could still read a document. The
brief forbids it, but that cannot be enforced, and the record says so.

## Inter-rater check

A second annotator, in a fresh context with the same brief and the same incoming
ledger, re-annotates a seeded sample of chunks: `random.Random(4492).sample` of 3
chunks from the #397 order. The record compares three things.
- **`carry` labels** on the same live facts: percent agreement and Cohen's kappa.
- **Events on earlier facts**: whether each fact received any `needed` event, compared
  by percent agreement and kappa.
- **New facts**: the lead matches statements across annotators and reports
  matched ÷ union, with the matching shown.

## Recall check against independently found re-observations (#490)

Blinded annotation fully recognised none of the four known #397 episodes. Before arms
are scored against probes, the protocol's blinded recall is checked against
re-observations that neither the lead nor the annotators chose.

This rule was fixed on 8 November 2026, before any candidate was computed. The
evaluator records no rediscovery event, so the candidates come from frames.

1. **Frames.** Each chunk's frames are taken in operation order, as in the timelines.
2. **Hash.** Each frame gets a 256-bit difference hash (`harness.trace.images.dhash`,
   size 16).
3. **A new screen** is a frame at least 64 bits from the previous frame in the same
   chunk.
4. **A candidate** is a new screen in chunk c, for c ≥ 1, within 16 bits of some frame
   from an earlier chunk of the same lineage. Within c, a candidate whose nearest
   earlier match was already used by a candidate in the previous 20 frames is dropped,
   so one re-opened screen counts once.
5. **The sample** is `random.Random(490).sample` of up to 40 candidates from #397 and up
   to 20 from the #372 sample, in a fixed sorted order. Held-out lineages are never
   used.
6. **The judge.** A blinded agent sees only the two frames, in a fresh context. It is
   not told the game, the study or which frame came first. It answers whether both
   frames show **the same specific information** (the same list, contents, message or
   text, not merely the same kind of view) and names it in one line. A "yes" is a
   confirmed re-observation.
7. **Captured.** A confirmed pair is captured when the blinded ledger, without the
   adjudication layer, holds in the later chunk a `rediscovered` or `needed` event:
   - on a fact observed in an earlier chunk;
   - citing a frame of the same session whose frame number is within 15 of the later
     frame's.
8. **Recall** is captured pairs ÷ confirmed pairs, per lineage and pooled.

**Decision, fixed in advance.** If pooled recall is **0.6 or more**, the fact-label
protocol stands. Below 0.6, the probes become query-style:
- for each boundary, one blinded agent writes queries from the predecessor's chunk;
- a second, in a fresh context, answers them from the successor's received text;
- the check is re-run on the query probes.

Either way, one fact ledger per development lineage is frozen as the scoring ledger.

**Result (8 November 2026).** Pooled recall was 0.51: 19 of 37 confirmed
re-observations captured. #397 reached 0.67 and the #372 sample 0.23. That is below the
bar, so the probes become query-style
([`data/evaluation/probes/validation/`](../../data/evaluation/probes/validation)).

## Query probes (#490)

Fixed on 8 November 2026, after the recall result and before any query was written.

**Writers.**
- Every chunk that precedes a boundary gets one blinded writer: #397's `sd1a1-001`
  through `sd1a7-001`, and each #372 sample run's `-001` chunk.
- A writer works in a fresh context from the chunk's timeline and frames, under the
  same frame-coverage rule as annotators.
- It is not told about the study, the episodes or any other chunk.
- It writes up to 40 queries, each with the information a later player in the same
  world might need, such as:
  - places;
  - what containers hold;
  - items lying around;
  - hazards;
  - controls and procedures;
  - the character's state and plans.
- Each query is answerable from a frame the writer viewed. It carries its answer and
  that frame:
  `{"type":"query","id":"Q1","question":"…","answer":"…","frame":"<source id>","category":"…"}`.

**The query set frozen per lineage is the scoring ledger.** An arm is scored by whether
the text it would put in front of the successor answers each query of the predecessor's
chunk.

**Re-check, with its bar fixed in advance.** For each confirmed re-observation, a
blinded judge in a fresh context sees the earlier frame and the queries written for that
frame's chunk. It decides whether any query's answer states the information the frame
shows.
- **Query recall** is covered ÷ confirmed.
- At 0.6 or more, query probes are adopted.
- Below 0.6, the record says so, and the probe design goes back to the owner before
  #491.

**Result (8 November 2026).** 19 writers wrote 649 queries. Query recall was 0.41: 15 of
37 confirmed re-observations covered, #397 0.50 and the #372 sample 0.23. That is below
the bar. Two figures are post hoc and descriptive only:
- **Union.** Either ledger, fact labels or queries, captured 0.68 of the 37.
- **Informative pairs.** Excluding 16 pairs that match only an empty menu, a search
  prompt or a loading screen, query recall was 0.62 (13 of 21) and the union 0.81 (17
  of 21).

**The owner's decision: freeze both ledgers together as the scoring ledger.** The
manifest, with a digest per file, is
[`data/evaluation/probes/ledger.json`](../../data/evaluation/probes/ledger.json).
An arm is scored against both:
- whether the text it puts in front of the successor carries each live fact;
- whether that text answers each query of the predecessor's chunk.

**Before relying on the combined ledger, #178:**
- tightens the confirmation rule, so that a pair matching only an empty menu, a search
  prompt or a loading screen is not a re-observation;
- re-tests the combined ledger once on held-out data, with its bar fixed in advance.

## Cost

Each chunk's annotator tokens and wall time come from the agent host's own task report.
Cost per lineage is their sum. The protocol stops and is reshaped when one #397
lineage's annotation would exceed the #178 study's annotation allowance. #178 sets that
allowance before held-out annotation.

## Annotator brief (chunk)

Frozen text, with only the bracketed parts filled in:

> You annotate one chunk of a sealed game-play trace for a memory study. Follow the
> attached labels and units exactly. Read only the files named here. Do not open any
> other file in the repository, and do not read issues or documents. Chunk:
> [timeline path]. Incoming ledger (facts and their state so far): [ledger path or
> "empty"]. First, for every live fact in the incoming ledger, write one `carry` line
> for boundary [boundary] by reading the "What this actor received" section. Then view
> the chunk's frames in order under the frame-coverage rule: every third changed frame
> from the first, every frame in the last five operations, and every frame you cite.
> Write `event`
> lines for earlier facts and `fact` lines for new ones, continuing the fact IDs from
> [next ID]. Output only the JSON Lines, then one final line `{"type":"end","frames_viewed":N}`.
