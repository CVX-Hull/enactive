---
owner: lead
status: proposed
review_trigger: Hypotheses, comparison rules, generators, visibility, budgets or analysis change
---

# Memory representation experiment protocol

Protocol **memory-study-v1.1**, current revision **2026-10-18**. Initial v1 was
frozen on that date after independent protocol
review and lead resolution of eligibility, literal fixtures, retrieval specification
and update-key sampling findings. **No comparison outcomes collected at initial freeze;
no final-seed outcomes collected before the v1.1 clarifications below.** The
[study brief](../changes/013-memory-representation-study.md) owns scope and the
[research synthesis](../research-memory-representations.md) owns rationale/sources.
This file owns the proposed synthetic experiment. It introduces no live runtime
contract and does not reproduce an LLM paper's benchmark.

## Questions and acceptance

| Suite / hypothesis | Strong simple comparator | What could falsify the added mechanism's value |
| --- | --- | --- |
| L: a bounded incremental dependency view preserves replay semantics at lower query work | Recompute from the complete bounded observable event archive | Any semantic mismatch, or maintenance/update cost exceeding the saved query work |
| E: origin deduplication prevents replay inflation; a declared finite model envelope exposes sensitivity to dependence | Deduplicated Bayes with a fixed observation model | Deduplication does not fix cross-origin correlation; envelopes may be wide, abstain excessively, or miss under misspecification |
| C: decision-conditioned retrieval preserves rare applicable evidence under a small working context | Exact scoped archive query; also lexical FTS5 and reservoir sampling | Exact filtering may equal richer mechanisms; missing scope/operation cues can make the answer unidentifiable; compaction need not degrade repeatedly |
| D: contextual/windowed updates improve some later predictions but have transfer and drift costs | No learning, pooled Beta counts and all-history scoped counts | Context-irrelevant data can favor pooling; windowing can forget useful evidence; missing context prevents separating incompatible cases |

Structural law failures are defects, not an average score to optimize away. Utility
comparisons have no required winner or minimum improvement threshold. A mechanism
is a candidate for later native testing only if its benefit and assumptions are
explicit and its added maintenance can be justified. No simulation grants action
authority, calibrates real-game confidence or proves survival improvement.

## Shared execution contract

- Use Python standard library (`dataclasses`, `random`, `math`, `statistics`,
  `sqlite3`, `json`, `hashlib`, `time`) and existing project-local Python. Check
  SQLite `ENABLE_FTS5` by executing a temporary in-memory FTS5 table; fail the
  FTS comparison explicitly if unavailable. No fallback labeled as FTS5, new
  service, embedding call, global install or model API.
- Development seeds: integers **0–31**. Final seeds: **10000–10255**. These are
  independent experiment seeds; duplicated records, queries and configurations
  within a seed are paired dependent measurements. Do not count them as
  independent repetitions. Instantiate a private `random.Random` per suite/seed;
  loop ordering or added methods cannot consume another method's randomness.
- Generate observable inputs once per seed/regime and give identical immutable
  input objects to every method in fixed-history comparisons. Reset method state
  between seeds/regimes. Scorer-only truth/model parameters are separate objects
  never passed to candidate interfaces. An assessor audit checks serialized input
  field names and manually traces one case of each generator.
- Methods receive the declared visible fields and common public nominal model
  configuration only. No hidden labels, true generating probability, future
  records, method-specific hint or privileged identity is available to them.
  They may use all supplied fields; poor baselines are not forced to ignore a
  field except where explicitly named as a diagnostic ablation.
- Count logical retained records, derived/index entries, returned context records,
  canonical UTF-8 JSON bytes, query inspections and update/invalidation work.
  State exactly what each operation counter counts. Also record end-to-end wall
  time and platform/runtime/SQLite versions as descriptive host-specific data.
  Do not equate record slots or operation counts to tokens, mutual information,
  planner latency, human review effort or CPU instructions.
- Archive budget is **64 records** for L/C and **256 observations** for D. Do not
  evict silently; generators must stay within limits. All methods pay for their
  retained archive and extra state. Working-context budget in C is a separate
  limit. E has at most **192 visible copies / 12 origins**; charge both.
- No method chooses a game action or changes its future observation trajectory.
  E's decisions are scored hypothetical classifications; D predicts a fixed
  logger's selected action outcome. Active sensing, action optimization and
  interactive exploration are outside this protocol.
- Tests exercise exact hand-calculable examples, leakage and invariants, not
  selected performance rankings. Development may fix bugs, not tune against
  final outcomes. Freeze source/config hashes before final execution. If a bug
  or protocol change follows a final run, preserve its report, record the reason,
  and issue a new protocol revision before rerunning affected comparisons.

## L — Lineage, time, retirement and scope

**Visible records.** Each event has `event_id`, `kind`, monotonic `receipt_index`,
`session`, `frame`, `entity`, optional integer `event_turn`, and a typed payload.
Kinds: `observe` (source ID/proposition), `derive` (claim ID and list of alternative
sets of premise IDs), `dispute_source`, `retire_claim`, `new_session`, `effect`
(command ID and outcome `confirmed`/`unknown`). IDs are stable under replay.
At most 64 unique events, 16 sources, 16 claims and 4 alternative derivations per
claim, at most 4 premises per derivation, acyclic dependencies. Retractions do not
erase observations. A retirement is permanent within this experiment's claim ID;
new evidence requires a new claim ID, not implicit resurrection.

**Exact eligibility rules.** Each observation has an exclusive property `key` and
Boolean `value`; the full property identity is `(session,frame,entity,key)`.
Initial active scope is `(s1,f1)`; `new_session` replaces the active session/frame.
Every current query must match that active pair and the record's entity. Historical
inspection may access any retained record and does not certify currentness.

For a current query at turn t, consider *all* received observations of the exact
property, including disputed sources. If any has unknown event turn, the property's
current value is unknown. Otherwise find the greatest event turn <=t. Different
values tied there make it unknown, even if one source is disputed: a dispute is
not proof that its proposition is false. An observation is currently eligible only
if it lies at that greatest turn, the frontier has one value, and that source is
not disputed. Older observations are superseded, including when the latest source
is disputed: losing support never silently restores an older current value.
`current_value` returns that unique value only if at least one frontier source is
eligible, otherwise null/unknown. This is the **last supported observed value**
under these rules, not guaranteed world truth or a claim that unobserved change
is impossible. No expiration/transition model is being smuggled into the test.

`supported(claim, scope, t)` requires exact active session/frame/entity match, no
retirement, and at least one derivation whose every premise is currently eligible.
A premise is either an observation under the rule above or a recursively supported
claim in the same scope. Derivation graphs are acyclic. Distinct property keys can
support one claim; a world update supersedes an older source for its own key and
therefore invalidates dependent claims. Deriving does not copy an observation into
a new independent source. A source dispute is permanent in this bounded experiment.
A retirement is also permanent for that claim ID. There is exactly one creation
per claim ID: a derive event's event ID is its claim ID; no add-proof/update-claim
operation exists. An identical replay deduplicates, while reuse with changed
payload or another creation targeting an existing claim is an input error.
Archive record existence remains true after either event.

**Input identity.** `event_id` identifies the semantic event. Identical replays
differ only in receipt index; deduplicate while retaining the original event and
first receipt. Reusing an ID with a different semantic payload is an input error.
`effect` records use a command ID and explicit `confirmed`/`unknown` outcome;
query returns the latest received explicit status for that command, or unknown.
Clock passage/rebuild/query repetition does not confirm it. No simulated command
is dispatched. Queries may request a rebuild before reading the same archive.

**Methods.** (1) archive replay recomputes semantic queries using ordinary dictionaries
and recursive Boolean dependency evaluation; (2) incremental view maintains
reverse dependencies and cached eligibility, but must return the same result.
Both retain the same archive/lifecycle. Diagnostic ablations remove origin
deduplication, valid-time ordering, alternate proofs, scope checks, or retirement
application during rebuild, one at a time. Label them intentionally incomplete;
they do not describe current TaskMemory or establish its failure.
Archive-count/history-existence queries directly read already retained/charged
archive and identity metadata; they do not rebuild unused state. Incremental effect
queries directly read their already maintained status map without allocating empty
eligibility caches. These obvious query paths add no new state/architecture.

**Cases.** The literal [fixtures](memory-study-cases.json) fix events, prefix queries
and expected answers independently of both implementations. The file's defaults
are shorthand expanded before giving visible records to methods: scope
`(s1,f1,door)`, observation key equal to ID when omitted, value true and turn 1;
query turn 10 and current active scope unless explicitly overridden. `after` is
the inclusive zero-based received-event prefix. `rebuild` invokes a method rebuild
before the query. Queries/results and scorer expectations never enter method input.

The templates cover duplicate ingestion, late old observations,
same-turn conflict, unknown turn, changed current observation, one surviving
proof, all support lost, shared ancestor removal, independent proof preservation,
retirement followed by rebuild, new-session coordinate alias, and unknown action
effect. Run literal prefixes unchanged. Seeded variants shuffle only consecutive
`observe` events before a derivation/lifecycle boundary and insert one identical
duplicate of the first observation in each such block; the duplicate may occur at
any position after its original. Preserve all non-observation event order. Compare
the final queries to the literal template's final expected answers; do not reuse
literal intermediate-prefix expectations after permutation. Known event turns
remain unchanged. A separate ambiguity fixture has identical visible input in
two scorer worlds and no relocalization evidence; a unique identity is unavailable.

**Measurements.** Per-template mismatches, false-current/unsupported answers,
lost-supported answers, history loss, resurrection, scope leaks and false-confirmed
effects. Count source/claim inspections per query, update traversals, index size,
archive bytes and extra-state bytes. Run 1, 4 and 16 repeated query passes over
each event prefix. Report correctness first; compare total work including updates
and rebuilds. No expected asymptotic advantage is inferred from this tiny DAG.

## E — Duplicate evidence, dependence and model uncertainty

**Generator (assessor only).** Draw hidden bit `h ~ Bernoulli(.5)`. Number of
origins `n ∈ {1,4,12}`; measurement accuracy `q ∈ {.6,.8,.95}`; common-cause
mixture `rho ∈ {0,.75}`. With probability `rho`, draw one correctness bit with
probability `q` and reuse it for all origins; otherwise draw independent
correctness bits with probability `q`. An origin reports `h` if correct, `1-h`
otherwise. Repeat each origin `copies ∈ {1,4,16}` times with the same origin ID
and value. Same base h/origin measurements are reused across copy counts.

**Candidate input.** Only `(origin_id, observed_bit)` copies, the prior `.5`,
nominal `q=.8`, and the public plausible class
`M = {.6,.8,.9} × {0,.75}`. True q/rho/h never enter candidate functions.
Origin IDs establish identical-source replay, not independence between origins.

**Methods.** (1) naive Bayes multiplies likelihoods for every copy, nominal q and
rho=0; (2) deduplicated Bayes uses one value per origin, nominal q and rho=0;
(3) finite-model posterior envelope computes a posterior under each member of M,
then takes minimum/maximum. The envelope is a range over **six declared models**,
not an exact continuous credal set, confidence interval or guarantee under arbitrary
dependence. A same-origin conflicting value is an explicit input error, not extra
evidence. No BeliefMem score is passed off as a probability baseline.

For observed unique signs `x`, let `m` match hypothetical `h`, `u=n-m`. The
likelihood for a given `(q,rho)` is:

`(1-rho) * q**m * (1-q)**u + rho * common`, where `common=q` if all signs match h,
`common=1-q` if none match, and zero otherwise. Normalize the two h likelihoods
with prior .5. Use log-space/stable normalization as needed; tests verify small
cases by enumerating the generator's latent common-cause branch.

**Scoring.** Point forecasts: Brier loss and log loss (natural logs, numerical
clipping at 1e-12 solely for log evaluation, raw predictions retained). Do not
score an envelope midpoint as though it were the method's probabilistic belief.
Envelope: fraction containing the true generating-model posterior and mean width,
separately for in-class q/rho and the intentional q=.95 misspecification. This
containment is conditional on a declared model class, not coverage of binary h or
real-game calibration. Even perfect in-class containment can be uninformative.

All methods may choose bit 0, bit 1 or abstain for scoring only. Correct choice
pays +1, wrong -4, abstain 0. Point methods choose 1 when p>.8, 0 when p<.2,
otherwise abstain. Envelope chooses 1 when lower>.8, 0 when upper<.2, otherwise
abstains. Ties abstain; treat values within 1e-12 of a threshold as ties to prevent
floating-point normalization from turning a mathematical tie into a decision.
Report realized mean utility, abstention, and regret in
**expected utility** relative to the assessor's true-model optimal decision; the
reference sees the generator model, not hidden h. Report duplicate-induced change
in forecast/decision, and frequency of wrong forecasts at confidence >=.95.

**Size.** 256 final seeds × 3 q × 2 rho × 3 n = 4,608 base episodes; × 3 copy
counts = **13,824 paired input conditions**, not independent samples. Include
exact no-new-information replay and n=1 controls. No fitted threshold selection.

## C — Retrieval and explicit lossy compression

**Visible archive.** 64 records, each with `id`, receipt index, `session`, context
`room0..3`, operation `open/close`, target `door0..3`, outcome `allow/block`,
source availability, and a fixed text rendering of the semantic fields. All
fields are given to all methods; extracted tags are stipulated correct here.
The generator selects one rare key uniformly from the 32 `(room,operation,target)`
keys, places one block record at index 0, and excludes that key from the remaining
63 draws. Other keys are sampled uniformly and receive allow, except a final
same-key update case which changes a previously observed non-rare key to block.
In the paired stationary control all outcomes are allow. Source-unavailable
records remain historical but are ineligible for factual answers.

The final update occupies record 63 (the other distractors occupy 1–62). Its key
is sampled uniformly over the **sorted set of distinct keys** observed at 1–62
(lexicographic room, operation, target order), never over the records themselves,
and is never the rare key. All other uniform key draws also use that lexicographic
key order. Source availability
is toggled deterministically for records whose index is divisible by 11, excluding
0/63, then a separate regime makes the rare source unavailable. These choices
are public generator rules, not hints in candidate inputs.

**Queries.** Exhaust all 32 keys; report rare, updated, ordinary and missing-key
strata separately. Two visibility regimes: full `(room,operation,target)` and
masked operation. In the latter, answer is known only if *all compatible latest
eligible per-operation records exist and agree*; otherwise unknown. This makes
observational ambiguity explicit. Assessor truth is the latest eligible archive
record for each exact key, not an invented world state. A missing key is unknown.
No record from another session is eligible; include a paired distractor-session
variant in which text is unchanged but the session differs.

**Shared answerer.** Consume only returned records; check session, query fields
and availability; apply latest-by-receipt for matching exact keys, then the same
masked-operation consensus rule. No answer without sufficient records. Therefore
bad retrieval can cause abstention; it cannot silently bypass scope checks.
The assessor scores whether abstention is necessary or due to missing retrieval.
Masked mode still issues all 32 underlying key queries: 16 pairs have identical
visible inputs/expected consensus answers and are not independent samples. Stratum
precedence is rare, updated, missing exact-key eligible record, then ordinary;
hidden operation is scorer-only for these strata, never supplied to the answerer.

**Methods / budgets.** Working context k∈{4,8,16}:

1. Exact scoped archive replay: scan the 64 records and return the latest eligible
   record per compatible key, at most two for masked operation. This is the strong
   simple comparator. Count every visited archive row, including rejected rows;
   do not imply this is the cost of an indexed relational implementation.
2. FTS5: MATCH the OR of visible query terms, order by `bm25()` ascending with
   fixed tie-break below, return top k, then shared answerer. Build the
   index from the same rendered fields, not privileged labels. Hard prefiltering
   by session and availability applies before top k to all archive queries.
3. Most recent k eligible records and uniform reservoir k eligible records;
   reservoir uses a separate derived seed. Same shared answerer.
4. Explicit irreversible majority projection per exact key, retaining the latest
   outcome only as a tie-break, up to 32 summary records; each summary retains all
   contributing source IDs. It has no raw archive after projection and pays its
   smaller record count plus lineage cost (bytes need not be smaller). Retrieval uses exact query fields,
   returns at most two summaries. A summary's outcome is the majority, so it can
   lose a rare temporal change. This is a **specified toy operator**, not an LLM
   summarizer or fair claim that compression in general performs worse.

Only methods 1–3 share the 64-record archive cost; method 4 intentionally trades
archive loss for storage. Source availability and session filtering must be applied
before projection; rebuilding summaries must not revive unavailable records.
Changing operation extraction quality or introducing semantic embeddings is a
future experiment, not an unreported advantage for metadata filtering.

**Frozen FTS definition.** Record IDs are `r00` through `r63`, receipt indices
0–63, initial session `s1`. Canonical body is exactly
`session {session} context {context} operation {operation} target {target} outcome {outcome}`
with single ASCII spaces and no punctuation/newline. Store `record_id UNINDEXED`
and `body` in `CREATE VIRTUAL TABLE search USING fts5(record_id UNINDEXED, body,
tokenize='unicode61 remove_diacritics 2')`; one body column with default BM25
weights. Metadata remains an ordinary table/lookup. Query terms are context,
operation if visible, then target, each double-quoted and joined by ` OR `;
for example `"room0" OR "open" OR "door0"`. Session is a hard metadata filter,
not a MATCH term. SQL orders by `bm25(search) ASC, receipt_index DESC, record_id ASC`
after joining metadata and requiring exact session/available status, then `LIMIT k`.
FTS corpus statistics include the whole 64-record index; eligibility filters apply
before top-k, not before index construction. Count eligible MATCH candidates ranked
as a logical work proxy, **not actual SQLite index visits/CPU instructions**.
Record the serialized in-memory SQLite database byte size separately from canonical
record bytes. The session-distractor variant changes metadata and regenerates body
consistently for every non-rare record at indices divisible by 5; query remains s1.
All retrieval paths see the same altered records.
Charge FTS construction explicitly: one FTS document row and one metadata row
prepared/inserted per archive record, separately from query candidates and SQLite
bytes. These are logical row counters, not SQLite's internal instruction costs.

**Compaction controls.** Apply the majority projection 1, 2, 4 and 8 times to its
output, treating each summary as one record but preserving its lineage and chosen
outcome. This operator is idempotent after its first pass; assert that result.
A separate explicit progressive-truncation operator removes the oldest half of
remaining **raw 64 archive** records per pass (rounding down, minimum one removed
while nonempty), with availability/session filtering in the common answerer,
then exact retrieval. It demonstrates one loss mechanism and can saturate; no
universal growth law is fitted. Include the same-bit query-label counterexample
with 2, 16 and 256 distinct labels, all answered by one retained bit.

**Measurements.** Answer correctness, unsupported/wrong answer, necessary versus
avoidable abstention, rare/updated-group recall, wrong-operation candidates before
filtering, records returned, scans/candidates examined, retained/index/lineage bytes,
and projection work. Report all methods, k, visibility, source/session regimes and
compaction depths. Do not collapse rare and common outcomes into one ranking.
Distinguish latest-source lineage recall (required raw source ID retained among
returned support IDs) from latest-record semantic recall (matching exact key,
receipt and outcome; summary ID may differ). Include each denominator. A summary
can retain the right citation while losing the latest outcome; source recall must
not be reported as answer correctness.

## D — Sequential learning, retention and unidentifiable alternatives

**Fixed logger and generator.** Four 64-observation phases, total 256. Visible
domain A/B and action 0/1; logger draws actions independently with probability .5.
Only the selected action's binary outcome is revealed after prediction. Phase 1
A has outcome probabilities `(.8,.2)` for actions (0,1); phase 2 B has `(.2,.8)`;
phase 3 B changes to `(.8,.2)` without a visible change flag; phase 4 returns to A
with its original `(.8,.2)`. The scorer owns probabilities. Candidate sees domain,
selected action and previous observed outcomes, never phase labels or future data.
Paired variants: context-irrelevant (all phases use `(.8,.2)`), no drift (B stays
`(.2,.8)`), and hidden domain (candidate receives one `unknown` label everywhere).

**Predictors.** Fixed .5 (no learning); Beta(1,1) posterior mean per action pooled
over domains; Beta(1,1) per visible domain/action; and scoped rolling-window counts
of the last w∈{8,16,32} observed outcomes per visible domain/action with the same
prior. Each predicts before seeing the outcome, is scored, then updates. No
method picks the logger action. These are simple memory/update policies, not
weight training or a complete contextual-bandit algorithm.

**Frozen probes.** After phase 1 and after phase 3, ask both A/action predictions
without revealing any labels or updating state. Scorer compares them against A's
original probabilities. Change in mean squared probability error measures
retention/negative transfer under this explicit return-to-domain assumption.
Phase 4 then tests later A performance with updates. In hidden-domain cases the
probe's domain cue is also hidden: no method gets privileged task identity.

**Measurements.** Brier/log loss by phase and first/last 16 steps of each phase,
frozen-probe probability error and its change, retained observations/count/window
entries, bytes and update work. No total-regret theorem, causal policy gain,
calibration guarantee or universally optimal forgetting rate is claimed.

**Causal negative control.** Construct two worlds: logger always selects action
0 and observes zero; action 1 deterministically yields zero in W0 and one in W1.
Serialize identical observable logs for both. Every deterministic estimator must
produce the same result from those inputs; the always-action-1 policy values
differ. Assert input equality and differing assessor values; report the policy
value as unidentified in [0,1]. This is an identification proof by construction,
not an estimator contest or a numerical reproduction of doubly robust learning.

## Analysis, failure handling and publication

The [declared matrix](memory-study-matrix.json) fixes exact condition/method keys
and required metric names independently of suite output. The runner checks these
and complete-method/control invariants before reporting completion. Per seed,
L/E/C/D contain 505/162/579/144 rows, respectively; the full final set has 355,840
seed aggregates. A matching count with renamed/missing methods is not coverage.
Paired differences use archive replay, deduplicated Bayes, exact archive recall
and pooled counts as their respective references; named identification/same-bit
controls have no paired reference. Shared metrics are differenced within a seed
and condition, never by pretending the two samples were independent.

Use all declared configurations. Report per-seed aggregates, then means and
descriptive `1.96 * sample_sd / sqrt(256)` Monte Carlo half-widths across independent
seed aggregates, with paired differences where useful. They describe simulation
variability conditional on these generators and independent pseudo-random seeds,
not real-world confidence, multiple-comparison significance or model uncertainty.
For exact law cases report integer failures, not a confidence interval that hides
one failure. Retain every seed result locally and commit small aggregate JSON plus
source/config hashes and reproduction commands; inspect representative traces.

Stop on leakage, broken invariants in the complete methods (not the intentionally
incomplete diagnostic ablations), budget overflow, nondeterminism or a failed
required backend. Preserve failure output, repair on development cases, record
the protocol/code change and rerun affected final comparisons without selecting
favorable seeds. Do not silently drop failed seeds or replace them with mocks.
Finish when all configurations and controls ran, outputs are reproducible, negative
results and limitations are documented, and independent final review is addressed.

The implementation is a small offline package under `tools/memory_study/`, separate
from `harness/`, with the [bounded allocation](../changes/013-memory-representation-study.md#implementation-allocation)
fixing interfaces and ownership. At most two writers use separate worktrees;
the lead owns the shared runner and integration. Re-estimate
[#62](https://github.com/CVX-Hull/enactive/issues/62) after protocol review.
[#63](https://github.com/CVX-Hull/enactive/issues/63) owns synthesis and staged
adoption, not automatic acceptance of a live memory redesign.

## Freeze record

Independent clean-context review found undefined L eligibility/prefix expectations
and outcome-sensitive C retrieval choices. The lead specified current support,
scope, conflict/dispute/supersession, replay identity and 12 literal fixtures with
32 expected prefix answers; fixed C rendering, schema, tokenizer, query, ranking,
metadata filtering and work counters; and specified uniform sampling over distinct
update keys. The reviewer checked the repairs and module handoff and reported no
remaining material findings. A 1e-12 decision-threshold tie tolerance prevents
floating-point artifacts. No simulation implementation or comparison outcomes
existed at this freeze. Later changes must preserve this record and explain their
effect before affected runs; previous outputs remain evidence, not disposable noise.

### v1.1 implementation clarifications — before final collection

Worker questions exposed choices not fully specified by v1: repeated claim creation,
raw versus prefiltered truncation, masked-query multiplicity/strata and whether
source-lineage recall implies retained semantic content. The lead fixed these
above before the affected C/L comparisons. Initial E development tests have run;
no final seeds or study reports have been collected. Hypotheses, distributions,
budgets, methods, final seeds and primary utility measures are unchanged. This
revision removes ambiguous interpretation; no v1 execution/reader path is retained.
Implementation review additionally required exact condition/method/metric-schema
coverage and runtime exact-law gates in the runner, and explicit FTS construction
counters. They are enforced before final collection; failed/rejected rows are
preserved rather than becoming a completed report.
A final fairness review removed unnecessary reconstruction for replay's metadata
queries and empty eligibility caches for incremental effect queries. No final
outcomes had been collected; these use existing state, not a new optimizer.
