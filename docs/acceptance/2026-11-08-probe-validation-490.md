---
owner: lead
status: historical
date: '2026-11-08'
scope: 'Blinded probe recall checked against independently found re-observations on #397 and the #372 sample, query probes written and re-checked, a content-matched correction, and the owner decision on P1 probes (#490)'
review_trigger: None; dated record
---

# Probe validation (#490)

P0 found that blinded annotation recognised the four known #397 episodes only weakly
([#449 record](2026-11-08-probe-baseline-449.md)). Before any P1 arm is scored against
probes, this record checks blinded recall against re-observations that neither the lead
nor the annotators chose. It uses development data only: #397 and the six-run #372
sample. #382's held-out lineages were refused by the tool and never opened.

**What was fixed in advance.** The method and both bars were committed before each step
was computed: `c856008`, before the candidates, and `bb029f7`, before the queries. Only the
protocol text was frozen. The analysis code was first committed with the first result, in
`bb029f7`.

**Reproduction.** [`tools/probe_validation.py`](https://github.com/CVX-Hull/enactive/blob/08c8f7aa902a0fe45c3aad22a6b29a41677336fc/tools/probe_validation.py)
reproduces every figure from the tracked files in
[`data/evaluation/probes/validation/`](assets/probe-validation-490/validation), and a test
pins the tracked `recall.json` and `ledger.json` to their inputs.

## How it was done

1. **Candidates.**
   - **Rule.** A new screen after a boundary is a candidate when it is within 16 of 256
     difference-hash bits of a frame from an earlier chunk.
   - **Found.** 197 in #397 and 25 in the #372 sample.
   - **Sample.** A seeded sample of 40 and 20.
2. **Pairwise judges.** Four blinded agents saw only the frames of their pairs, in a
   seeded order. Each judged whether the two frames of a pair show the same specific
   information. They confirmed **37 of the 60** pairs.
3. **Fact-label check, as pre-registered.** For each confirmed pair, did the #449
   blinded ledger (without adjudication) hold a need or re-observation event near the
   later frame, on a fact from an earlier chunk?
4. **Query probes.**
   - **Writers.** 19 blinded writers, one per chunk preceding a boundary, wrote **649
     queries** from their chunk's timeline and frames. Each query carries its answer and
     frame.
   - **Coverage judges.** Four further blinded judges each saw a confirmed pair's earlier
     frame and the questions and answers written for that chunk, without their frame
     ids. They judged whether any answer states the frame's information.
5. **Content check, post hoc.** After review, one more blinded judge received each
   fact-captured pair's earlier frame and the statements of the nearby facts. It used the
   same model and question as the coverage judges.

**Models.** Every judge and writer was a development agent on Sonnet 5.5. Their briefs
are in [the appendix](#briefs).

## Results

| Lineage | Confirmed | Fact labels, pre-registered rule | Fact labels, content-matched | Queries covered | Either, content-matched |
| --- | ---: | ---: | ---: | ---: | ---: |
| #397 | 24 | 16 (0.67) | 4 | 12 (0.50) | 13 (0.54) |
| #372 sample | 13 | 3 (0.23) | 0 | 3 (0.23) | 3 (0.23) |
| **Pooled** | **37** | **19 (0.51)** | 4 (0.11) | **15 (0.41)** | 16 (0.43) |
| Informative pairs only | 21 | 12 | 4 | 13 (0.62) | 14 (0.67) |

**Both pre-registered bars were missed.** Fact labels reached 0.51 and queries 0.41,
against 0.6.

**The content-matched columns and the informative row are post hoc and descriptive.**
- **The pre-registered fact rule does not check content.** A capture needs only a need
  on any earlier fact within 15 frames, whatever that fact says. In 15 of the 19 captures,
  no nearby fact states what the frame shows. For example, an empty recipe tab was
  "captured" by a fact about a food's calories. The 0.51 stands as computed, but it does
  not show that the fact ledger records these re-observations.
- **"Informative pairs only"** leaves out 16 confirmed pairs whose judge note marks a match
  without durable information: an empty recipe tab, a search prompt or a loading screen.
  Nine of the #372 sample's 13 confirmed pairs are of this kind, so the #372 figures say
  little.

**What the figures say, as development evidence.**
- **The fact ledger rarely records a visual re-observation as such.** Its needs come from
  annotators' judgements, which seldom match these screens.
- **Queries cover about three fifths of the informative re-observations.**
- **What the queries missed, on informative pairs.** Mostly recipe and inventory screens
  with many details, and overmap descriptions. The writers named the subject but not the
  specific contents.
- **What the queries missed, on all pairs.** 14 of their 22 misses, and 9 of the
  pre-registered fact rule's 18, are empty, loading or search-help screens.

## The owner's decisions

1. **First decision, on the uncorrected figures.** The owner first chose to freeze both
   ledgers together as P1's scoring ledger. That choice rested on a union of 0.68 (0.81
   on informative pairs), computed with the uncorrected fact rule. Independent review
   then found the inflation.
2. **Second decision, on the corrected figures (8 November 2026).** **Confirmed
   re-observations are P1's primary probes.**
   - **Probes.** Found by the fixed candidate rule. On held-out data, every candidate is
     judged.
   - **Confirmation.** Under a tightened rule that excludes empty menus, search prompts
     and loading screens.
   - **Scoring.** By a blinded content-match judge, at the boundary each pair crosses.
   - **Secondary figures.** Both blinded ledgers stay frozen in
     [`data/evaluation/probes/ledger.json`](assets/probe-validation-490/ledger.json),
     with a digest for every fact chunk, the adjudication layer and every query file.
     They yield descriptive figures.

   The P1 pre-registration (#491) fixes the scoring rules.

## Cost

| Step | Agents | Tokens | Summed agent time |
| --- | ---: | ---: | ---: |
| Pairwise judges | 4 | 360,062 | 2.8 min |
| Query writers | 19 | 2,381,946 | 38.5 min |
| Coverage judges | 4 | 416,120 | 1.7 min |
| Content judge (post hoc) | 1 | 81,710 | 0.9 min |
| **Total** | 28 | **3,239,838** | 44 min |

- **Tokens only.** These are development-agent tokens; no model proxy was used and
  nothing was spent through one.
- **Time.** The time is summed across agents, not elapsed: most ran in parallel.
- **Not counted.** One content judge was stopped right after launch, because it ran on
  a different model from the coverage judges. Its tokens are not counted, and its partial
  output was discarded.
- **Detail.** Per-unit figures are in
  [`costs.jsonl`](assets/probe-validation-490/validation/costs.jsonl).

## Deviations

- **The goal's source of independent episodes does not exist.** The goal named
  "evaluator rediscovery events", but the evaluator records no such event. Near-duplicate
  frames across boundaries replaced them, a source equally independent of the lead and
  the annotators. The rule was fixed before computing.
- **Judges were batched.** The protocol says the pairwise judge "sees only the two frames,
  in a fresh context". Instead:
  - each pairwise judge saw 15 pairs in one context;
  - each coverage judge saw 9 or 10 items;
  - judges saw opaque pair ids (`p001`), but neither frame order nor the study.
- **One frame-count difference.** The tool's frame order matched #449's chunk frame
  counts, except `ceil05-001`, which has 84 frames against 85: a frame repeated across
  two operations is counted once.
- **Query writers.**
  - `sd1a1-001` keeps 17 queries: its reply was truncated in transit, and the writer no
    longer had the rest.
  - `sd1a2-002` wrote 43 queries, over the cap of 40. All are kept.
  - **Frame coverage.**
    - `sd1a5-001` viewed 19 frames; its #449 annotator also viewed 19.
    - Several writers viewed fewer frames than the #449 annotators of the same chunk:
      `sd1a1-002` 69 against 81, `ceil09-001` 28 against 34, `sd1a7-001` 52 against 58,
      `aidB3-001` 32 against 37.
    - No tool checks a writer's coverage, or that it viewed every frame it cites.
  - Several writers were resumed to write their output to a file after replies were
    truncated. The queries were not changed.
- **The content check is post hoc.** It was added after review found the fact rule's gap.
  One content judge's item list was incomplete on its first pass: it skipped two items,
  which it judged on resumption.
- **Unit tests corrected.** Two unit tests for the candidate rule initially expected fewer
  candidates than the frozen rule produces. The rule also keeps returns to the main view;
  the judge rejects those. The tests were corrected to the rule.

## Limitations

- **One judge per pair, and one writer per chunk.** There was no inter-rater check on the
  judges or the writers.
- **The re-check credits queries from the earlier frame's chunk.** The first scoring rule
  used only the predecessor's chunk. In #397, 15 of the 24 confirmed pairs have their
  earlier frame two or more chunks back. The P1 pre-registration scores each
  re-observation at the boundary it crosses, which removes this mismatch for the primary
  probes.
- **The candidate rule finds only visual re-observations.** A fact re-learned through a
  different screen is not tested.
- **Small samples.** 37 confirmed pairs, 13 of them from short #372 runs.

## Briefs

The verbatim briefs; paths are shown as placeholders.

**Pairwise judge.**

> You compare pairs of screenshots for a study. Read only the file named here and the
> image files it lists; do not open any other file, run any command other than viewing
> files, or read documents or issues. The file [batch] lists pairs, each with an `id` and
> two image paths `A` and `B`. View both images of every pair with the Read tool. For
> each pair decide: do A and B show the same specific information — the same list of
> entries, the same container contents, the same message or the same text panel — not
> merely the same kind of screen or the same general view? Small differences (a cursor,
> a highlighted row, a clock, a status value) do not matter if the specific information
> is the same; a different list, different contents or a different message means "no".
> Output only JSON Lines, one per pair in the given order:
> {"id":"<id>","same":true|false,"what":"<one line naming the shared specific
> information, or why not>"}. Do not write any file.

**Query writer.** Some writers were instead asked to write the same lines to a named
file and reply only "written N lines".

> You write questions about one chunk of a recorded game-play trace for a memory study.
> Read only the timeline file named here and the frame images it points to; do not open
> any other file, run any command other than viewing files, or read documents or issues.
> Timeline: [timeline].
>
> The timeline lists one player's operations in order, each with a frame image path.
> View frames with the Read tool under this coverage rule: every third frame whose
> "changed" column is not "no" (or every third frame if the column is empty), counting
> from the first; every frame in the last five operations; and every frame you cite.
>
> Write the questions a later player in the same game world might need answered about
> what this chunk showed: places, what containers hold, items lying around, hazards,
> controls and procedures, recipes, and the character's state and plans. Prefer durable
> information over momentary states. Every question must be answerable from a frame you
> viewed; give the answer as shown and that frame's source id (the PNG file name without
> ".png"). Write at most 40 questions, numbered from Q1.
>
> Output only JSON Lines, one per question:
> {"type":"query","id":"Q1","question":"...","answer":"...","frame":"<source
> id>","category":"place|container|item|hazard|procedure|recipe|self|plan|other"} then
> one final line {"type":"end","frames_viewed":N}. Do not write any file.

**Coverage judge.**

> You check whether written questions cover what a screenshot shows. Read only the file
> named here and the image files it lists; do not open any other file, run any command
> other than viewing files, or read documents or issues. The file [batch] lists items,
> each with an `id`, one image path `frame`, and a list of `queries` (question and
> answer). For each item, view the image with the Read tool and decide: does any query's
> answer state the specific information this image shows (its list, contents, message,
> text or map description)? A query that only mentions the same kind of screen without
> stating that information does not count. Output only JSON Lines, one per item in the
> given order: {"id":"<id>","covered":true|false,"query":"<covering query id or
> null>","why":"<one line>"}. Do not write any file.

**Content judge (post hoc).**

> You are a blinded judge. Read only the file [batch] and the PNG frames it names (open
> each with the Read tool). Do not open any other file, repository document, issue or
> record.
>
> Each item has an `id`, a `frame` (a screenshot of a computer game), and a list of
> `statements` (each with an `id` and a `statement` text). For each item, decide whether
> any one statement states the specific information shown in the frame — that is,
> whether someone who knew that statement would already know what this frame shows. A
> statement that is merely about a related topic, or the same general screen type, does
> not count. An empty menu, a search prompt or a loading screen counts as covered only if
> a statement states that very content.
>
> Write your verdicts as JSON Lines to [verdicts], one line per item, in the file's
> order: {"id": "...", "covered": true|false, "statement": "<id or null>", "why": "<one
> sentence>"}. Then reply with only the number of items judged and how many were covered.
