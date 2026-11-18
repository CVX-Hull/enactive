---
owner: lead
status: proposed
date: '2026-11-16'
scope: 'Compare provenance-aware belief revision and mathematical uncertainty methods on real CDDA visible-trace replay, with staged mechanical checks and later decision-use tests. No production belief choice, paid study or model switch is authorized.'
review_trigger: Packet/source inventory or priced pilot completes; the owner chooses a belief model; calibration or action-use findings change
---

# Belief methods that earn their cost in CDDA

## At a glance

**Question.** Which uncertainty/revision mechanism helps the curator retain applicable
knowledge, retract wrong inferences and deliver useful answers, beyond the existing
source-linked prose store? Does any improvement reach the Terra player's decisions?

**Recommendation to test, not adopt.** Start with origin/dependency tracking and explicit
support/refutation/unknown handling. Compare numerical belief only on identical evidence
and targets. Subjective logic is a candidate interface and set of operators, not an
automatic cure for uncertain extraction, correlated evidence or changing conditions.

CDDA is the only current game. This study uses the source portfolio and prefix packets
of [structured recurrence](structured-recurrence-research.md) and #668, rather than a
new game, collector or simulator. #457 owns the production belief/schema decision.
Terra remains the current player; #25 owns later cheaper-model trials. No envelope is
open, and this proposal neither resolves the belief choice nor gates #463's adoption.
The later replay investigation is [#677](https://github.com/CVX-Hull/enactive/issues/677).

The [measurement audit](../acceptance/2026-11-16-experiment-measurement-review.md)
constrains the evaluation: score all assigned targets, preserve unknown evidence and
actual input exposure, and distinguish justified verification from avoidable lookup.
Judge agreement and all-negative validation samples cannot qualify correctness or
positive-case sensitivity. Numeric calibration and gameplay utility remain separate
claims; reuse the source-grouped packets and qualify only the outcome actually used.

## Primary foundations and what they support

Targeted retrieval/read date: **16 November 2026**. These are foundational mechanisms,
not a new SOTA survey or evidence of CDDA benefit. Earlier agent-memory evidence and
its limitations remain in [the curated-memory review](../research-curated-memory.md).

| Source and read scope | Applicable idea | Limit in our system |
| --- | --- | --- |
| Jøsang, [Subjective Logic](https://www.openphilanthropy.org/wp-content/uploads/Josang2013.pdf), 18 February 2013 draft, §§3.1.1–3.1.3 and 4.7 | Explicit opinion/evidence parameters and fusion operators | Specify the proposition, prior, observation likelihood and dependence before treating weights as evidence; cumulative fusion is not appropriate merely because two citations differ |
| Green et al., [Provenance Semirings](https://www.cs.ucdavis.edu/~green/papers/pods07.pdf), PODS 2007, §§2–4 | Track alternative and shared derivations | A small origin/dependency graph is sufficient to test the idea; lineage is neither truth nor numerical independence |
| Gneiting and Raftery, [Proper Scoring Rules](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf), JASA 2007, §§1–3 | Score probabilistic predictions against their realized outcomes | Lower loss does not establish calibration on unobserved situations or better game decisions; label error remains |
| [NIST censoring guidance](https://www.itl.nist.gov/div898/handbook/apr/section1/apr131.htm), retrieved 16 November 2026, exact/readout/interval examples | Distinguish exact event times, intervals and right censoring | Gameplay revisits are selected, conditions can change back, and a source statement becoming wrong is not necessarily an irreversible failure |
| Gelman, [Multilevel Modeling: What It Can and Cannot Do](https://www.stat.columbia.edu/~gelman/research/published/multi2.pdf), 2006, §§2–3 | Partially pool sparse groups | Pooling can transfer a wrong assumption; types/profiles do not become exchangeable because their names are similar |

### Subjective logic is partly a representation comparison

For a binary opinion `(b,d,u,a)`, `b+d+u=1` and projected probability is `b+a*u`.
For finite nonnegative evidence weights r,s, W > 0 and 0 < a < 1:

```text
b = r/(r+s+W)    d = s/(r+s+W)    u = W/(r+s+W)
alpha = r+W*a    beta = s+W*(1-a)
b+a*u = alpha/(alpha+beta)
```

Thus the mapped Beta and binomial opinion agree under matched inputs. An experiment
must not count different labels for the same update as independent predictive methods.
Unknown support and balanced substantial support/refutation can share a mean but differ
in evidence strength. Low u also does not mean conflicting evidence has been resolved.
A reader-presentation comparison is separate from a changed likelihood/fusion policy.
The primary mapping is mathematical; whether game observations justify its inputs is
an empirical question. An LLM-emitted number is not calibrated evidence by definition.

## Competing methods and controlled factors

Keep the claim representation, extraction, source packets, questions and downstream
reader fixed for the first comparison. Change the belief/revision layer only. Later,
test the selected belief method across representation variants; do not begin with a
belief × schema × model factorial that makes costs and attribution unmanageable.

| Method | What changes | Why include it |
| --- | --- | --- |
| Source-linked prose with supersession | Existing-style text plus its known references; preserve explicit unknowns | Main practical comparator; no invented probability required |
| Provenance-aware qualitative revision | Track original observation IDs and dependent claims; distinguish support only, refutation only, both and neither within scope | Test duplicate resistance, alternative supports, conflict and retraction without a numerical calculus |
| Evidence model with Beta/opinion views | Specify target and observation model; retain support/refutation strength and prior; apply dependence-aware updates | Compare predictive behavior to simpler methods; matched Beta/opinion arithmetic is an equivalence control |
| Optional staleness model | Add a development-fitted conditional applicability/change model, including an aging-off comparator | Test whether time or observed changes improve applicability, rather than silently decaying all facts |
| Optional partial pooling | Share estimated parameters between justified development groups; compare no pooling and full pooling | Test sparse-data gains and negative transfer; do not assume a learned type hierarchy supplies reliable statistical groups |

All methods get the same permitted observations. Exact replay of one origin adds no
new support; different frames may still share an error cause. Do not infer source
reliability from LLM confidence or judge agreement alone. Treat extraction errors,
unknown identity and ambiguous conditions separately from belief-update arithmetic.
Dempster–Shafer, latent truth-discovery models, general POMDP filtering and full
provenance algebra are extension candidates only after a concrete baseline failure.

## Staged tests

### Mechanical checks: no model, no gameplay

`tools/recurrence_research/belief.py` provides `evidence_views` for exact rational,
finite Beta/opinion fixtures and `active_alternatives` and `revision_state` for supplied
origin conjunctions and their alternative supports. The focused tests check matched
projections, repeat-origin invariance and retraction: `(a AND b) OR (a AND c)`
survives removal of b but not removal of a. Balanced conflicting evidence and a
numerical no-support prior can have the same mean and different uncertainty.

These are synthetic definition and bookkeeping checks, not useful learning or evidence
of CDDA efficacy, calibration or production adoption. Polarity and dependencies are
supplied; distinct IDs do not establish independent observations. No source reliability,
observation-to-weight conversion or numerical evidence is inferred from the graph.
Qualitative unknown is not converted to probability .5; the numerical prior is a
separate supplied fixture. The #677 method comparison uses this apparatus; reassess it
at #677 completion, stop or method abandonment and remove it and its tests if no named
consumer continues to need them. The bounded offline checks reduce R-FALSE-CLAIM and
R-REGRESSION by catching projection and support bookkeeping errors.

Prepare CDDA packets through #668. All previously inspected lineages are development
material. No LLM extraction, replay or new-start creation is authorized by preparation.
The [matched case inventory](../acceptance/2026-11-17-belief-replay-case-inventory.md)
supplies the scoped development fixtures and identifies the source and observation-model
gaps to resolve before a priced comparison.
The [#735 replay](https://github.com/CVX-Hull/enactive/issues/735) checks the five
inventory questions in their two dependent development groups. Run it offline with
`.venv/bin/python -m tools.recurrence_research.belief_replay data/recurrence-research/belief-replay-cases.json`.
Both methods receive the same scoped prefix of the hand-authored extraction. The
readout keeps source-linked answers and abstentions alongside the numerical fixture
state. It retains scope distinctions between the title return and same-character
reload, and between native exit and Quit delivery. It cites applicable unknown
receipts. Repeated descriptions retain the same canonical event and origin. The
tank question requires both reports, which share one frame and contribute one unit.
Excluded results and adjudication stay outside the input and readout. The supplied
unit weights exercise the mechanics of the replay.
The later priced pilot may stop at insufficient observable cases; do not fabricate a
conflict or label an unseen outcome false to make a method testable.

### Matched CDDA prefix replay: first method evidence

Build a small development inventory spanning actual visible evidence demands:
repeated descriptions of one event; new re-observation; visible counterevidence;
changed applicability; scope/identity uncertainty; and later queries requiring an older
distinction. Record absent regimes honestly. No save/engine oracle or external game
knowledge supplies assertion truth. Repeat-origin packet checks may repeat an existing
source reference but add no fabricated game observation.

For every preassigned question, freeze the proposition, conditions, observation horizon
and answerability rule independently of method outputs. Methods see a prefix only;
predictions are sealed before the future frame. Construct support/refutation events
from one common, versioned extraction set for all methods, then separately evaluate
model-mediated extraction and joint updating. Oracle correctness or independent source
reliability is not silently granted to an arm.

Two comparisons answer different questions:

1. **Evidence/update comparison:** identical inputs and prediction targets, with a fixed
   readout path. Score probability predictions from numerical methods, and answer/revision
   behavior from all methods. Qualitative unknowns are not converted to probability .5.
2. **Reader-use comparison:** give the same Terra reader the same evidence/model in
   different presentations (for example matched Beta versus opinion fields), with
   query/cost allowances fixed. A presentation gain is not a superior posterior.

Use whole-world/lineage development, selection and final splits; copies, questions and
multiple moments remain nested. Shared-source transformations remain in one partition.
Current archives can develop the protocol; only untouched or newly acquired CDDA
sources can support a later generalization claim. Price acquisition and every
extractor, updater, reader and judge call before requesting the study envelope.

### Scoring and missing observations

For numeric methods, predeclare Brier loss as the primary predictive loss on the same
adjudicable target set; log loss may be secondary with its exact numerical treatment
frozen. Report reliability diagrams and coverage, without calling a low mean loss proof
of calibration. Score both a frozen always-issued forecast and any separate abstention
policy so abstaining cannot hide difficult examples. For every method, report revision
accuracy, unsupported confident answers, delayed correction, retrieval usefulness,
error versus answer coverage, resource use and per-regime failures.

Source labels are fallible: freeze the frame-based codebook and independent/blinded
judging before method comparison; keep `cannot_tell` and agreement visible. The primary
score population is defined by common target/label rules, not whether an arm answered,
retrieved or the player happened to use a fact. Missing outcomes remain in accounting
and coverage. Conclusions concern judged player-visible outcomes, not hidden engine
truth; no requested additional owner labeling or evaluator-to-curator feedback follows.

Do not score a posterior credible interval as if a single binary outcome revealed the
latent probability. Validate any interval-coverage claim against an identifiable target
and a justified model, or leave it unclaimed.

A revisit showing changed applicability usually bounds a change somewhere between
observations; it does not identify an exact change time. A later agreement does not
prove uninterrupted validity. Informative revisits and possible reversals can defeat a
simple survival model. Start with prediction conditional on observed prefixes; admit a
survival/interval-censoring model only after specifying its event and observation process.
No extrapolation to never-revisited facts is identified by those selected logs alone.

### Later player decisions: separate benefit test

Only a useful replay candidate advances to a priced, supported integration in the
CDDA pilot of #666. Hold Terra and other role configurations, natural player context,
source assignments and resource ceilings equal. Compare source-specific visible progress,
wrong/stale-advice use, information-request cost, wall latency and complete cost on
all assigned trials. Hypothetical re-observation value is not inferred where the
logged player never tried the alternative. Let the player choose ordinary inputs;
no false memory or bad routine is planted. A model-switch comparison belongs to #25.

A belief calculus is adopted only by the owner's #457 decision, with its evidence
and limits. A replay gain is not a live decision benefit. Freeze the exact analysis,
cluster-aware uncertainty, practical threshold, multiplicity and affordable power
before any claim-deciding batch; otherwise label the pilot exploratory or stop.

## Delivery and existing owners

#668 owns common source/packet/specification/price preparation. #677 under #666
owns the later frozen replay protocol and evidence, with an explicit
priced envelope before calls. It reuses `tools/recurrence_research/` and the existing
source packets. The bounded brief assigns any additional code ownership and validation.

#457 owns the production schema, belief choice and gate; this study informs rather than
automatically blocks it. The adopted #463 migration is complete, and #689 supplies the
current recorded knowledge/public-report reader. GitHub owns the next work selection;
#664 owns later live freshness. #25 retains cheaper-player alternatives after
memory/context work; Terra is the current baseline and no study here authorizes
swapping it. No programs, monitor,
practice instance, context cut or second game is adopted.

These procedures apply existing risks: provenance and common-label/split isolation
reduce R-FALSE-CLAIM and R-GAME-COUPLING at extraction/review cost; explicit complete
prices and bounded pilots reduce R-OVERSPEND/R-STUDY-OVERRUN at preparation cost;
existing actor/gate/evaluator ownership addresses R-ARCHITECTURE-DRIFT without new
runtime authority. R-TECH-DEBT/R-CONTROL-BLOAT favor shared packets and small operators.
No new global control or dependency is added by this proposed study.
