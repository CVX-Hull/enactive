---
owner: lead
status: active
date: 2026-11-10
scope: 'Pre-registration of the ADR 009 P1 offline study (p1-study/3): p1-study/2''s data, arms and decision rule, with recall measured by an answer-key chain (question writer, reader, grader) after the arm-guess check failed on development data (#178)'
review_trigger: Any change to the data, the stages or caps, the arms, the measurement chain or its briefs, or the decision rule
---

# P1 offline study, third protocol: pre-registration

Protocol **p1-study/3**, written 10 November 2026 for [ADR 009](../decisions/009-curated-player.md#phases)
P1 (#178). It replaces p1-study/2 and decides the same question as [p1-study/1](p1-study.md):

> Does a curator (arm B) put in front of a successor actor more of the information that actor
> later went back for than the simpler path without one (arm A)?

**Why a second protocol.** p1-study/1 stopped at its power gate before any replay or spend
([record](../acceptance/2026-11-09-p1-gate-178.md)). #382's three held-out lineages give 27
scoring units (11, 7 and 9) over 10 boundaries, nearly all singleton clusters. Criterion 3 needs
at least one lineage with 20 or more units, so a go was impossible. The owner chose to reshape P1
by adding one held-out lineage ("Add one held-out lineage", 9 November).

**Why a third protocol.** p1-study/2 required that a blinded guesser could not tell the two arms'
texts apart before any scoring. On development data the guesser matched the arms on 27 of 30 texts,
and on 26 of 30 after arm A's notes were split into lines; the limit is 21
([#178](https://github.com/CVX-Hull/enactive/issues/178)). The two systems write differently: the
player's records are terse notes with `key: value` details, and the curator's facts are full
sentences. No renderer hides that without rewording content. The owner chose to redesign the
measurement ("Draft p1-study/3", 10 November). **(p1-study/3)** Recall is now measured by a chain
in which the party that judges never sees an arm's text
([The measurement chain](#the-measurement-chain)). The data, the arms, the units and the decision
rule are p1-study/2's. No held-out text had been delivered or scored when this page was written.

**This page is self-contained.** Units, Probes, Arms, Metrics, Decision rule, Analysis and the stop
rules are p1-study/1's text, carried over word for word except where a **(p1-study/2)** or
**(p1-study/3)** marker or the two Deviations sections say otherwise. A test checks that the
Confirmation brief is p1-study/1's.

**Owner decisions (8 and 9 November 2026), carried over:** a descriptive study with effect-size
thresholds agreed in advance; terra as the curator model; confirmed re-observations as the primary
probes. **(p1-study/2)** The owner approved p1-study/2 and decided the questions under
[Owner decisions](#owner-decisions) on 9 November 2026. **(p1-study/3)** The owner approved
p1-study/3 on 10 November 2026, before any held-out replay.

**What has already run** under p1-study/2 and stands: stage 0 (`lh4`, #522), the probes and the
power gate on lh1–lh4 ([record](../acceptance/2026-11-10-p1-gate-study-2-178.md)), the pilot
($3.24) and the development stage ($23.71 over two attempts, the first losing one session to
provider timeouts).

The analysis is [`tools/p1_analysis.py`](../../tools/p1_analysis.py) and its tests are
[`tests/test_p1_analysis.py`](../../tests/test_p1_analysis.py). The plan is in
[`data/evaluation/p1/power-study-2.json`](../../data/evaluation/p1/power-study-2.json); a test checks
that the table under [Power](#power) renders it.

## Data and split

| Use | Lineages | Role |
| --- | --- | --- |
| Development | #397 `sd1a1`–`sd1a7` and the six-run #372 sample | Build, debug and pilot both arms; **(p1-study/3)** try the measurement chain on #490's confirmed pairs (p1-study/2: scored descriptively against the #490 ledgers); decide nothing about the arms |
| Evaluation (held out) | #382 `lh1` (3 runs), `lh2` (2), `lh3` (2) in `372-382-dev-loop`; **(p1-study/2)** `lh4` (#522) in `522-held-out` | The only data the decision uses |

**Held-out handling.**
- **lh1–lh3.** Their probes and ledgers are frozen as #178 wrote them
  ([`frozen.json`](../../data/evaluation/p1/held-out/frozen.json)) and are reused unchanged. The
  lead has read only their counts, digests and cluster structure.
- **(p1-study/2) lh4 is held out before it starts.** Until scoring, the lead and any operator read
  only counts, digests, cluster structure and the run-health aggregates listed under
  [Running lh4](#running-lh4). Nobody who develops the arms, or writes this page's rules, sees its
  frames, memory records, notes or reports. **(p1-study/3)** Blinded agents see only what their
  step names: annotators, question writers and auditors the frames; readers one delivered text;
  the no-text answerer, paraphrasers and graders no frame and no delivered text.
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
  build and its native check (owner, 9 November: "Current main").
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
boundary, a death) is made instead by a fresh development agent per admission, pinned as [the chain's agents](#the-measurement-chain) are, that writes probes for no study and develops no arm. It
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
under [The measurement chain](#the-measurement-chain).

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
- **(p1-study/3) The texts are not indistinguishable,** and nothing here assumes they are. A
  record is written whole, as p1-study/2 fixed it; the split into lines that was tried on
  development data is not used.
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
and every later change is a deviation. The [approved transport amendment](#approved-transport-amendment)
is the sole exception for the remaining replay.

**(p1-study/2) Two steps before the freeze, in stage 2:**
- **The format check ($0).** lh4 is recorded on a newer player than every trace the arms were built
  on. Arm A's items and arm B's per-admission schedule are built on lh4 with no curator session, by
  a tripwire (`p1_replay check`) that prints only counts and exception class names. A failure stops the study and goes
  to the owner; nobody debugs it on lh4. The owner may then approve one development admission on
  lh4's source (about $6) to reproduce and fix it on development data.
- **A's punctuation tell** (owner, 9 November: "Fix in stage 2"): a record whose text ends in `!`
  or `?` gets no added `.` before its data.

### Approved transport amendment

The owner approved this amendment on **11 November 2026**, before any held-out score,
while the lead remained restricted to counts, digests and permitted run-health metadata.
The original freeze and every failed attempt remain
retained; this is an amended study with mixed-source provenance.

- **Transport only.** The new freeze pins source `a8c98117389bf0f09d8793ba004b7cc4b114f0c3`
  ([PR #537](https://github.com/CVX-Hull/enactive/pull/537)). Only the curator host and proxy
  differ from the original frozen runtime. An upstream 429 with a valid server `Retry-After`
  of at most 60 seconds may use the existing single retry; a server veto suppresses it.
  The pinned SDK owns the cancellable wait. Both attempts share the original request,
  wall and proxy ceilings and resend identical bytes, without a note between them.
- **Unchanged.** Prompts, model, route, effort, prices, image window, renderer, data, questions,
  scientific briefs, measurement and decision rules. The original freeze is preserved in
  Git at `0bc5802` and in retained evidence; the canonical arms manifest records the new freeze.
- **Retain whole realizations.** Complete repeat 1 and repeat-2 `lh1` remain on source
  `0bc5802`, selected before scores. Their permitted health metadata shows only successful
  responses. Fresh repositories rerun **whole `lh2`** and finish `lh3`/`lh4`: **11 sessions**,
  stage `held-out-transport-3`, repeat 2. Incomplete `lh2` outputs are not used. Use separate
  maintained lineage deliveries and record each source/freeze and schedule alongside them;
  no schedule or partial knowledge store is stitched together.
- **New finite allocation.** The continuation is capped at **$34.12**; unused earlier capacity
  is retired. All **$13.31144395** prior repeat-2 recorded debits stay in its cost numerator.
  The additional **$11.90480270** unresolved allowance stays separate from settled debits.
  With the new cap the conservative allocation is **$59.33624665**, below the unchanged
  recorded actor denominator **$59.33655440**, counted once. These are budget quantities,
  not provider invoices. Newly identified exposure needs reconciliation. Reaching the new
  stage cap fails the cost guard; another lost session returns to the owner.
- **Limits.** Controlled successful transcripts support branch equivalence, not identical
  counterfactual real outputs. Recovery adds elapsed time and an HTTP attempt, so later
  model-visible budget notes can change. A recovered refusal's conservative unpriced proxy
  debit is retained. The result states the amendment and provenance beside its conclusion.

## The measurement chain

**(p1-study/3)** This section replaces p1-study/2's scoring judge and arm-guessing check.

**Pinning.** Every question writer, no-text answerer, paraphraser, reader, grader and auditor is
pinned:
- a fresh, ephemeral session of the selected coding host, with its version, model and effort in
  [coding-agent hosts](../operations/coding-agents.md#p1-study-readers). The owner moved all
  measurement agents to this host on 10 November, after first moving only readers. Each
  working directory holds its one batch and prompt; a reader's batch still holds exactly one
  item. At most three sessions run at a time. The frozen briefs' command prohibition permits
  the host's mechanical file reads, named-image viewing and writing the named answer file;
- the already selected reader configuration, as pinned on the host page. The original
  non-reader pin was the #490 judges' model; those development results remain retained,
  and the full development chain runs again before any held-out question is written;
- a fresh context, and only its batch file and the frames that file names.

The host version is recorded with each batch.

**The principle.** The party that sees an arm's text judges nothing, and the party that judges
never sees an arm's text. Blinding then holds by construction and does not depend on the two texts
looking alike.

| Step | Sees | Does not see | Writes |
| --- | --- | --- | --- |
| 1. Question writer | A unit's earlier frame | Any arm's text | One question and its answer key |
| 2. Reader | One arm's delivered text and the unit's question | The frame, the key, the other arms | An answer from the text, or "not stated" |
| 3. Grader | The question, the key and the reader's answer | The frame and every arm's text | Whether the answer gives the key's information |

**1. Question writer.**
- **One question per scoring unit,** about the specific durable information the unit's earlier
  frame shows, with a short answer key taken from the frame.
- **Batches** hold at most 10 frames, in probe-id order.
- **The screen.** Before a question set is frozen, two blinded checks run on it. A script runs
  them and prints only counts:
  - **Mechanical.** A question is flagged when its key is empty, has more than five entries, or
    shares a token with the question. Entries are the key split on commas, semicolons and line
    breaks. Tokens are lower-cased runs of letters or digits; only runs of digits and runs of
    four or more letters count.
  - **No text.** A fresh agent that sees only the questions answers each from general knowledge
    of the game (the Guess brief; batches of at most 10 in probe-id order). The Grader brief
    marks those answers, under the grader's rules below. A question answered correctly is flagged.
- **A flagged question is rewritten once.** A fresh writer gets the same frame and the flagged
  question as `rejected`, under the Question brief, in batches of at most 10 in probe-id order.
  The rewrite replaces the question and is screened again. If it is flagged again it stays, and
  the count of such units is reported. Nothing else changes a question; any other revision of a
  question or a brief is a recorded deviation.
- **Held-out questions** are written after the development checks below and after the arms
  freeze, before any held-out replay. They are frozen by digest in
  `data/evaluation/p1/questions/` (`questions.jsonl` and a `frozen.json` of the probes' format).
  `score --questions` refuses a file that differs from its freeze.
- **Who reads them.** Held-out questions, keys and answers hold held-out content. Until scoring
  the lead reads only their counts and digests.

**2. Reader.**
- **Items.** One per unit and text: A, B repeat 1, B repeat 2 and the Reference (the received text
  alone, a control).
- **One item per reader.** Each item goes to a fresh reader with nothing else in its file. Texts
  of one lineage share most of their content, so a reader that saw two of them could carry an
  answer from one arm, or from a later boundary, to another. The reader therefore has no batch
  order, and p1-study/2's `Random(4911)` is unused. Items are numbered, and their files named,
  in a `Random(4916)` shuffle of the list sorted as the grader's is, so that an id does not
  follow the arm (owner, 10 November: "Shuffle with a new seed").
- **The answer** comes only from the item's own text, as one plain sentence in the reader's own
  words. "Not stated" is a valid answer.

**3. Grader.**
- **"Not stated" is labelled incorrect without a grader.** An answer that is exactly "not stated",
  ignoring case and a final full stop, never reaches one.
- **Items** are sorted by probe id, then text (A, B, `R`, `PW`, `PP`; the last three are the
  controls below), then repeat; mixed in a seeded
  order (`Random(4915)`); and packed first-fit into batches of at most 10, with no two answers
  to the same question in a batch. The grader is not told which text an answer came from.
- **Correct** means a person who read only the answer would know what the key says. A missing
  minor detail does not matter. A missing or contradicted main entry does. An answer that offers
  alternatives, or adds entries the key does not have, is not correct.

**A unit is stated for an arm and repeat** when its answer is graded correct. That label is the
`stated` of `p1-score/1`, so the decision rule's criteria are unchanged.

**Re-judging.** For exactly the seeded 20% sample (`tools.p1_analysis rejudge`, `Random(4912)`), a
fresh reader and then a fresh grader repeat steps 2 and 3 on the same question and key, with the
grader's seed and packing rule applied to the sample. The sample is drawn over A's and B's labels
only, as in p1-study/2; the controls' rows do not enter it. Scoring refuses any other set. Agreement is
reported as the chain's repeat variance: percent, Cohen's kappa, and percent over the items that
either pass answered. It cannot see an error in the question itself, or a miss that both passes
make; the screen and the positive control are the controls for those.

**The Reference control.**
- The Reference goes through steps 2 and 3 once, like an arm, and is not re-judged. Its labels
  are `p1-score/1` rows with arm `R` and repeat 1. `score` requires one for every unit, and keeps
  them out of the decision rule.
- A unit that is correct for the Reference needs no working set: the received text, or general
  knowledge of the game, already answers it.
- The primary metric still counts every unit, because both arms contain the received text.
  Each arm's recall over the units the Reference got wrong is reported beside it.

**The positive control (sensitivity).** The chain can miss information a text does state: a
reader can overlook a line, and the grading is strict. Such misses lower both arms' recall and
shrink B − A, which criterion 1 compares with an absolute 0.15.
- **Items.** For each unit, the Reference text with one new last line, after everything the
  renderer wrote, in two forms:
  - **word for word (`PW`):** `- <question> <key>`, with single spaces; a key's entries on
    separate lines are joined with `; ` (owner, 10 November). It contains the question, so it
    checks that the chain works at all, not how sensitive it is;
  - **paraphrased (`PP`):** `- <sentence>`, where a fresh agent wrote the sentence from the
    question and the key (the Paraphrase brief; batches of at most 10 in probe-id order). This
    form is the sensitivity measure.
- **A paraphrase is checked before use.** The Grader brief marks each sentence against its key,
  as an answer to its question. A sentence marked not correct is rewritten once by a fresh agent
  and checked again; one that fails twice is used as it is, and the count is reported.
- **Reading and grading** follow steps 2 and 3. The rows are `p1-score/1` with arms `PW` and `PP`,
  repeat 1, outside the decision rule and not re-judged. `score` requires both for every unit.
- **Sensitivity** is the share correct, for each form. The gap between the forms shows whether
  the chain depends on wording, which the bias control below cannot see.
- **What it cannot see.** A question that covers only part of a frame, and a fact that is harder
  to find inside a full working set than in one added line. It is an upper bound.
- **On development** it is a check with a floor (below). **On held-out** it is reported beside the
  result, so that a negative can be read against what the chain could detect.

**The bias control (replaces the arm-guessing check).** On the units the Reference got right, the
received text answers the question, and that text is byte-identical in A and B. A difference
between A's and B's correct rates on those units means an arm's working set changed an answer the
received text already gave. That can be the measurement (a reader distracted by one arm's working
set) or the working set itself (a stale or contradicting item, or extra entries).
- **Reported,** from first-pass labels over the Reference-correct units: their count; the
  difference, B (mean of its repeats) minus A; and how many units only A got right and only B
  got right.
- **Flag:** an absolute difference above **0.10** over at least 20 such units is stated beside
  the outcome as "the received text's answer changed by arm", with its direction. Only B above A
  could help produce a go. It does not change the decision rule.
- **Limits.** With 20 units and a label error of 5–10% the flag fires by chance about one time in
  ten to one in five. With fewer than 20 Reference-correct units it does not apply, and that is
  reported.
- **Why not a guessing check.** A guesser can tell the arms apart from "not stated" answers alone
  whenever one arm delivers more, so such a check fails most often when the curator works, and
  telling the arms apart is not the same as grading them differently.

**Checks on development data, before any held-out question is written.** The whole chain,
including the screen and the positive control, runs on development for A, B and the Reference.
Its recall figures decide nothing about the arms. Three checks can stop the study.
- **Units.** The pairs #490's validation confirmed that are not in its `recall.json`
  `query_probes.trivial` list (21: 17 in #397 and 4 in #372), kept where the pair's later frame
  follows a boundary that has a development B text (a first handoff included; #397 from the
  development re-run's sessions, #372 from `aidB3` and `ceil09`). Each pair is one unit, with its
  #490 pair id as the probe id; `units` and its held-out checks are not used. The count is
  reported before the checks run. Development questions and answers stay under `.runtime/` and
  are not frozen in the repository.
- **Chain noise.** Every development A and B label is re-judged, not a sample. The repeat
  disagreement d, pooled over those labels, must be **at most 10%**. It is reported for each arm,
  with kappa and the disagreement over answered items. With independent errors the error per
  label is e = (1 − √(1 − 2d)) ÷ 2, so 10% is about 5.3%. The power gate assumes 5%; scratch
  re-runs of the gate's simulation with the label error raised gave P(go) at the 0.30 effect of
  0.827 at 10% and 0.740 at 15% (2,000 simulations each; 0.901 at 5% in the committed gate).
- **Sensitivity.** The positive control must be correct on **at least 85%** of development units
  in each form.
- **The recall floor (owner, 10 November).** A, B or the Reference must be stated on **at least
  3 of 20** development units (15%). The first development run scored all three at 0 of 20 and
  passed the two checks above: its questions asked what a screen showed, which a memory text
  cannot answer, so every reader said "not stated", in both passes. A chain at its floor cannot
  show a difference between arms, and neither other check can see that.
- **Power at the measured values.** The gate's simulation is re-run once on the committed
  gate's layout, with its seed (491) and 5,000 simulations, changed in two ways: the label error
  is e from the pooled d above, and every label that the simulation makes stated is kept with
  probability s, the paraphrased form's sensitivity, in every arm. A second figure uses s for B
  and the word-for-word form's sensitivity for A, the case where wording works against B. The
  answer-key leaf adds these two parameters to the simulation. Both figures go to the owner
  with the checks.
- **A failed check,** or a first figure under 0.80, stops the study and goes to the owner. No
  brief or rule changes after the development run without the owner; any change is a recorded
  deviation and the development chain runs again.
- **The sensitivity floor is not the whole bar.** In the committed gate P(go) is 0.764 at an
  effect of 0.25 and 0.901 at 0.30, so the power figure needs a sensitivity of about 0.88 at 5%
  error. With 20 units that is at most two misses; 17 of 20 passes the sensitivity floor and
  still goes to the owner. The
  simulation's standard error is about 0.006, so a figure within 0.01 of 0.80 is reported as
  borderline.
- **Limits of these checks.** With about 21 units they can catch a chain that is badly noisy or
  badly insensitive; they cannot certify a small error rate. The bias control cannot apply on
  development at all. The gate's flip model treats errors as equal across arms; the bias control
  on held-out data is what looks for an unequal one.

**False-fact auditor.**
- **Sample.** For each arm and each repeat, `Random(4913)` draws up to 40 (working-set item,
  boundary) pairs from all delivered items.
- **What the auditor sees.** The item's statement as rendered, with:
  - the frames the item cites;
  - the predecessor chunk's frames under the probe-protocol/1 coverage rule.

  The frames are listed in time order (#518). Batches hold at most 10 items, and the auditor is
  not told the arm.
- **Verdict.** An item is **false** when a listed frame contradicts it, or shows it had stopped
  being true before the boundary.
- **(p1-study/3) Not blind by construction.** The auditor sees an arm's statement and may
  recognise the arm from its style or from how many frames it cites. Its question is narrower than
  recall: does a frame contradict this statement? The guard is kept as pre-registered, and the
  result record states this limit beside it.

**Delivery (p1-study/2).** Every annotator, question writer, no-text answerer, paraphraser, reader,
grader and auditor writes its
JSON Lines to a named file and replies only with a line count, as #178's did.

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

> **Question.** You write one question about each screenshot for a memory study. Read only the
> file named here and the image files it lists; do not open any other file, run any command other
> than viewing files, or read documents or issues. The file [batch] lists items, each with an
> `id` and one image path `frame`. View each image. Write one question whose answer is the
> specific durable information the image shows (its list, contents, message, text or map
> description), asked about the game world or the player's situation, not about the screen. Do
> not mention a screen, menu, panel, cursor or a place on screen, or what was shown, listed or
> highlighted. Someone who knew the fact but never saw this image must be able to answer. Give
> that answer as a short key taken from the image. If the image shows a
> list, the key names at most five entries that tell this list from another. An item may also
> carry `rejected`, an earlier question that was turned down; write a different one. The question must make
> sense to someone who has not seen the image, must not give the answer away, and must not be
> answerable from general knowledge of the game alone. Output only JSON Lines, one per item in the
> given order: {"id":"<id>","question":"<one question>","key":"<the answer, as the image shows it>"}.

> **Reader.** You answer questions from a text. Read only the file named here; do not open any
> other file, run any command, or read documents or issues. The file [batch] holds one item,
> with an `id`, a `text` and a `question`. Answer the question using only what the text says. Do
> not use what you know about the game. Answer in
> one plain sentence in your own words: do not copy the text's format, and give one answer, not
> alternatives or guesses. If the text does not say, answer exactly "not stated". Output only JSON
> Lines, one per item in the given order: {"id":"<id>","answer":"<one sentence, or not stated>"}.

> **Grader.** You check answers against an answer key. Read only the file named here; do not open
> any other file, run any command, or read documents or issues. The file [batch] lists items,
> each with an `id`, a `question`, a `key` and an `answer`. For each item decide: would a person
> who read only the answer know what the key says? A missing minor detail does not matter. A
> missing or contradicted main entry does. An answer that offers alternatives, or adds entries the
> key does not have, is not correct. Output only JSON Lines, one per item in the given order:
> {"id":"<id>","correct":true|false,"why":"<one line>"}.

> **Guess.** You answer questions about a computer game from what you already know. Read only the
> file named here; do not open any other file, run any command, or read documents or issues. The
> file [batch] lists items, each with an `id` and a `question`. Answer each in one plain sentence
> if you can; otherwise answer exactly "not stated". Output only JSON Lines, one per item in the
> given order: {"id":"<id>","answer":"<one sentence, or not stated>"}.

> **Paraphrase.** You restate answers as sentences. Read only the file named here; do not open
> any other file, run any command, or read documents or issues. The file [batch] lists items,
> each with an `id`, a `question` and a `key`. For each item write one plain sentence, in your
> own words, that tells a reader the answer the key gives to the question. Do not copy the key's
> wording where another wording says the same. Output only JSON Lines, one per item in the given
> order: {"id":"<id>","sentence":"<one sentence>"}.

> **Audit.** You check statements against recorded screenshots. Read only the file named here and
> the timelines and image files it lists. For each item, decide whether any frame listed for it
> contradicts the statement, or shows it had stopped being true by the last listed frame. Output
> only JSON Lines: {"id":"<id>","false":true|false,"frame":"<source id or null>","why":"<one
> line>"}.

## Metrics

All metrics come from `p1-score/1` rows, through `tools/p1_analysis.py score`.

| Metric | Definition | Role |
| --- | --- | --- |
| **Re-observation recall** | Units whose information the arm's text states ÷ units, pooled over held-out lineages. **(p1-study/3)** A unit is stated when the grader marks the reader's answer from that text correct | **Primary** |
| Undelivered re-observations per game hour | (Units − stated) ÷ in-play game hours | Reported. ADR 009's rediscovery metric, offline; on fixed units it rescales recall, so it is not a second test |
| Audited false-fact rate, with its one-sided 95% Clopper–Pearson upper bound | False ÷ audited items, per arm and repeat | Guard |
| Curator ÷ actor spend | B's proxy-settled dollars ÷ the actor's dollars for the same runs, per repeat | Guard |
| Chain agreement on the re-judged sample; delivered tokens per arm; **(p1-study/3)** Reference recall; each arm's recall over the units the Reference got wrong; the bias control's figures and its flag; the positive control's sensitivity in each form; the count of questions flagged twice by the screen | | Reported |
| Needed-fact recall (fact ledger) and query coverage | As frozen in **(p1-study/2)** each held-out directory's ledgers. **(p1-study/3)** Not scored: its judge was the retired scoring judge, and the chain has no question for a ledger fact | Not reported |
| A against the Reference; handoff and admission boundaries separately; **(p1-study/2)** lh4 against lh1–lh3 | | Descriptive |

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
   **(p1-study/3)** A re-judged label comes from a fresh reader and a fresh grader.
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
| 2. Development | #397 `sd1a1`–`sd1a7` | $26 | Debug both arms end to end; descriptive scores against the #490 ledgers and the arm-guessing check (**p1-study/3:** both replaced by the chain's development checks); **(p1-study/2)** the format check; then freeze the arms |
| 3. Held-out B, repeat 1 | `lh1`–`lh4` | **(p1-study/2)** 1.0× the actor's spend on lh1–lh4: $30.46 plus lh4's actual, fixed when #522 ends | Primary data |
| 4. Held-out B, repeat 2 | `lh1`–`lh4` | The same | Primary data |
| Reserve | | $20 | Only to re-run a session lost to an infrastructure failure, once, unchanged, and recorded. **(p1-study/3)** The replay tool re-runs whole lineages only, so a lost held-out session goes to the owner |

**(p1-study/2)** p1-study/1's "Total $120" row is replaced by this: the caps sum to $198.92 plus
twice lh4's actual spend, about $299 if lh4 spends $50 and $359 if it spends its whole envelope.

**(p1-study/3) Where the stages stand, and the order from here.** Stages 0, 1 and 2's curator
sessions are done: `lh4` cost $28.88 (its envelope spent $30.11 with a lost admission), so each
held-out repeat's cap is **$59.34**. The remaining steps, in order:
1. The answer-key batches are built and reviewed (#529). The leaf also changes `score`:
   Reference and positive-control rows, the bias control, `--questions` and its digest, and no
   arm-guessing check.
2. The chain, with its screen and positive control, runs on development data
   ([The measurement chain](#the-measurement-chain)). Its checks and the re-run power figure go
   to the owner; a failed check stops the study there.
3. The `lh4` format check runs, and the arms are frozen with A's punctuation fix.
4. Blinded writers write every held-out unit's question; the screen runs; the questions are
   frozen by digest.
5. Held-out B repeat 1 (the owner is asked first), then repeat 2, then arm A.
6. Readers and graders label every unit; re-judging and the audit follow; `score` writes the result.

No step from 2 on spends dollars except step 5.

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
- **Freeze.** Once held-out replay starts, nothing in the arms changes except the explicitly
  [approved transport amendment](#approved-transport-amendment); its new freeze precedes reuse.
- **Gate (p1-study/2).** The re-run gate on lh1–lh4 can stop the study before stage 1.
- **(p1-study/2) Operator-enforced.** The code does not tie caps to stages (#462's review), so the
  operator passes each stage's cap explicitly and records it with the stage's label, does not
  start repeat 2 after a capped repeat 1, and starts no stage after an isolation incident.

**Gameplay (p1-study/2).** Stage 0 is the only gameplay. No other game launches, and nothing else is
spent on the actor. Development-agent tokens are reported in tokens, not dollars. They cover the
probes, the run monitor, the auditors and **(p1-study/3)** the question writers, the screen's
answerer, the readers and the graders, with the two failed arm-guess checks.

## Cost estimate

| Item | Basis | Estimate |
| --- | --- | ---: |
| lh4 | 12 boundaries are 13 chunks: about 7 admissions at #382's 1.86 chunks per admission (#397: 2.0), so 6–8 at $5–7 | $30–56 |
| Pilot and development | p1-study/1's: #454 terra sessions | $33–36 |
| Each held-out repeat | 0.61–0.87× the actor's $60–87 on lh1–lh4 (#454) | $37–75 |
| **Expected total** | | **$137–242** |

Development-agent tokens: lh4's probes and ledgers about 3–4M (lh1–lh3's 3.37M for 13 chunks); the
run monitor under 0.3M; scoring, re-judging and the audit about 4M (p1-study/2's estimate).

**(p1-study/3)** The chain's estimate replaces that 4M:
- question writers and the screen about 1.5M (89 units);
- readers about 12M: 89 units × six texts (A, B twice, the Reference and the two positive
  controls) plus the 20% repeat is about 590 single-item readers, each about 20,000 tokens with
  its host overhead;
- graders about 1M, and the audit about 1M.

About 16M in all, with development's run (about 21 units, every label twice) about 4M more.

**Measured on development (10 November).** A pinned-model agent costs about 60,000 tokens
whatever its task, and a reader on the second host about 115,000, mostly cached input. The
first development run used 16.1M reader tokens for 140 readers and about 1.2M for its other
agents. At that rate the held-out run's 590 readers are about 68M reader tokens.

## Analysis and reporting

`python -m tools.p1_analysis score --probes <held-out probes> --probes <lh4 probes>` **(p1-study/2:
the second file)** `--scores <rows> --hours <hours>` **(p1-study/3)** `--questions <questions> --screen <screen counts> --sentences-counts <paraphrase counts>` writes `data/evaluation/p1/result.json` (`p1-result/1`).
- **Refusals.** It refuses when:
  - a unit is unjudged for some arm or repeat;
  - a label is duplicated;
  - the re-judged set is not the seeded sample;
  - **(p1-study/3)** a unit has no Reference label, or the questions file's digest differs from
    its freeze (p1-study/2 refused here on the arm-guessing check instead);
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

## Deviations from p1-study/2

1. **The measurement.** A question writer, a reader and a grader replace the scoring judge. The
   unit and the decision rule's criteria are unchanged. The label's meaning narrows: p1-study/2
   asked whether the text states what the frame shows; p1-study/3 asks whether a reader of the
   text answers one question about the frame correctly.
2. **The arm-guessing check** is dropped, with its `score` refusal and `Random(4914)`. It ran
   twice on development data and failed both times (27 and 26 of 30). The bias control on
   Reference-correct units replaces it as a reported flag, not a gate.
3. **Re-judging** repeats the reader and the grader, not one judge. The grader's order is a new
   seed, `Random(4915)`.
4. **The Reference** is read and graded like an arm, as a control, with `p1-score/1` rows of arm
   `R`. **A positive control** (arms `PW` and `PP`) measures the chain's sensitivity.
5. **A question screen** (mechanical and no-text) with one rewrite, and a questions freeze that
   `score` checks.
6. **Three development checks:** every label re-judged, limit 10% disagreement; sensitivity at
   least 85%; a recall floor of 3 of 20 units, added after the first development run. The
   gate's power is re-run once at the measured values. p1-study/2's power
   assumptions were made for a different measurement, and only scratch re-runs cover this one.
7. **Five new frozen briefs** (Question, Reader, Grader, Guess, Paraphrase); the Scoring and Arm
   guess briefs retired. The Question brief was revised after the first development run, and
   development ran again (Owner decision 8).
8. **One item per reader,** each in a fresh context; p1-study/2 packed 10 to a batch in
   `Random(4911)` order and only kept one unit's texts apart. "Not stated" is labelled without
   a grader.
9. **The held-out rule's wording.** "Nobody who writes probes, judges…" would forbid the chain's
   own blinded agents; it now names the lead and the arm developers. **The order of steps.** The
   development chain runs before held-out questions are written;
   p1-study/2 had the probes and their judge fixed before development.
10. **Needed-fact recall and query coverage** are not scored.
11. **The audit** is unchanged and recorded as not blind by construction.
12. **Owner decisions of 10 November on #518's batch rules** stand for the audit (order, packing,
    dropping and counting an unresolved cite). The scoring-order decision and the arm-guess set
    decision ("All 15 boundaries per arm") are superseded with what they governed.
13. **Development ran twice.** The first attempt lost `sd1a1` to provider timeouts; the owner chose
    one unchanged re-run of the lineage inside the stage's cap.
14. **A held-out session lost to infrastructure** goes to the owner when it happens; the replay
    tool re-runs whole lineages only, so the reserve's "one session" cannot be applied literally.
15. **Readers run on the second coding host,** not as pinned-model subagents (Owner decision 7).
16. **The rules found while #529 was built** (Owner decision 6): tokens, the word-for-word line,
    reader numbering with `Random(4916)`, and the minor rules.
17. **All remaining measurement roles move to the reader's host** (Owner decision 9), using the
    existing reader model and effort. The complete development chain is recalibrated before
    held-out questions; the earlier mixed-host results are retained and do not qualify the new chain.
18. **Owner-approved transport recovery after infrastructure failures.** The
    [transport amendment](#approved-transport-amendment) replaces only the host/proxy retry
    handling for the remaining sessions, retaining the preselected complete realizations
    with mixed-source provenance and all failed expenses. A retry does not renew a session's
    limits; the measurement and decision rule are unchanged.

## Owner decisions

**(p1-study/3)** Decided by the owner on 10 November 2026:
1. **p1-study/3** (the measurement chain, its briefs, the question screen, the positive control
   and the two development checks): "Approve".
2. **Questions per unit:** "One per unit", not up to three with every one required.
3. **The bias control:** "Reported flag", not a gate that makes a flagged result inconclusive.
4. **Needed-fact recall and query coverage:** "Drop them", not a second question set.
5. **Earlier the same day:** the redesign itself ("Draft p1-study/3"), after "Split A's notes
   into lines" did not bring the arm-guess check under its limit.
6. **Rules this page left open, found while #529 was built** (each a deviation from the page as
   approved):
   - **Tokens:** "Split letters from digits". `9mm` gives `9`, which counts, and `mm`, which is
     too short; a single digit counts; an empty key entry is not counted toward the five.
   - **The word-for-word line:** "Join with '; '".
   - **Reader numbering:** "Shuffle with a new seed", `Random(4916)`.
   - **Minor rules:** "Accept all as built". "Not stated" also ignores surrounding whitespace;
     the bias flag needs a difference strictly above 0.10; the only-A and only-B counts are
     given for each B repeat; a paraphrase that fails its check twice is used as it is and
     counted; an agent whose output is refused has its batch redone once by a fresh agent, and
     a second refusal goes to the owner.
   - **Development units.** #490's 21 pairs give 20 units: one is in `aidA5`, which has no B
     text. Development has one B repeat, so its chain reads A, B repeat 1 and the controls.
7. **Readers on the second coding host,** with care for its rate limits; the owner's words are
   quoted in [coding-agent hosts](../operations/coding-agents.md#p1-study-readers). A
   pinned-model subagent cost about 60,000 tokens per item against this page's 20,000; a reader
   on the second host costs about 115,000, mostly cached. Three pilot readers that had run on
   the pinned model were set aside unused.
8. **After the first development run** (0 of 20 for A, B and the Reference; 0 of 40
   disagreements; sensitivity 19 and 20 of 20; 6 questions flagged twice):
   - **The Question brief:** "Fix the Question brief, re-run". The question is asked about the
     game world or the player's situation, not the screen. The recall floor is added as a third
     development check. The development chain runs again.
   - **The shared-word rule:** "Keep the rule". It flagged 13 of 20 first drafts, mostly on
     context words.
   - **The second development run** passed all three checks: 0 of 40 disagreements; sensitivity
     19 and 20 of 20; recall 5, 6 and 4 of 20 for A, B and the Reference (on the 16 units the
     Reference got wrong, A 1 and B 2). At those values P(go) is 0.940 at the 0.30 effect and
     0.022 with none. The no-text answerer said "not stated" to all 66 questions over both runs,
     so that half of the screen has not shown it can flag anything.
9. **All measurement agents on the reader's host.** The owner selected this change because of
   quota availability; the exact decision and host, version, model and effort are recorded in
   [coding-agent hosts](../operations/coding-agents.md#p1-study-readers). The remaining question
   writers, no-text answerers, paraphrasers, graders and auditors use the same setup as readers.
   This changes the host, model and fresh-session mechanism, not the frozen briefs, data, arms or decision
   rule. The full development chain is repeated before held-out questions, preserving both
   earlier development runs. The prepared nine held-out handouts have no returned answers
   and are not used until that calibration passes. The attempted launch through the previous
   host was refused by automatic approval review before execution; no study content was sent by that attempt.

Decided by the owner on **11 November 2026**, before any held-out score:
1. **Transport amendment and 11 fresh sessions:** "Approve amendment and 11 sessions
   (Recommended)". The exact freeze, retained realizations, mixed-source limit and $34.12
   cap are specified in the [amendment](#approved-transport-amendment). The original freeze
   and failures remain retained; another lost session requires a new decision.

Decided by the owner on 9 November 2026:
1. **p1-study/2, the $80 lh4 envelope and the caps above:** "Approve".
2. **lh4's source:** "Current main", at #522's freeze commit (the player an adoption would
   migrate), not #397's `db38b30`.
3. **#462's recorded choices** (Deviation 8): "Accept all".
4. **A's punctuation tell:** "Fix in stage 2", before the arms freeze, recorded as a deviation.

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
- **(p1-study/3) The measurement followed a failed blinding check.** It was redesigned after the
  development arm-guess results, and after the lead compared the two arms' development texts, but
  before any held-out text was delivered or scored. No recall was computed for either arm on
  development data before the redesign, so the grading rules were not chosen knowing which arm
  they favour. The lead did know the two formats when writing them.
- **(p1-study/3) Keys use the screen's wording.** A's records often copy that wording and B's
  snapshots paraphrase it. The grader judges information, not wording, but a paraphrase is the
  harder case, so a wording effect would run against B. The positive control's two forms measure
  it.
- **(p1-study/3) A bad question cannot be seen by re-judging.** It moves every arm of its unit
  together. The screen catches two kinds; others remain.
- **(p1-study/3) One question per unit.** A frame can show more than one question covers; the unit
  is stated when the reader answers that one question.
- **(p1-study/3) The reader is a model.** It can miss what a text says, or answer from what it
  knows of the game despite its brief. The positive control measures the first and the Reference
  control the second; the re-judged sample measures the chain's repeat variance. The positive
  control's line sits at the end of a short text, so it is an upper bound on how well a reader
  finds the same fact inside a full working set.
- **(p1-study/3) The audit is not blind by construction** (see the False-fact auditor).
