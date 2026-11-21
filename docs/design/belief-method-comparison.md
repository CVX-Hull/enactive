---
owner: lead
status: proposed
date: '2026-11-16'
scope: 'Compare provenance-aware belief revision and mathematical uncertainty methods on real CDDA visible-trace replay, with staged mechanical checks and later decision-use tests. No production belief choice, paid study or model switch is authorized.'
review_trigger: A live run supplies a curator-written fact about an earlier sighting, or the production belief decision or comparison evidence changes
---

# Belief methods that earn their cost in CDDA

## At a glance

Which belief method helps the curator retract wrong inferences and give the
player better answers? The proposal compares source-linked prose, qualitative
revision and numerical belief on matched CDDA evidence. Whether numerical
belief improves predictions or changes decisions remains unknown.

The [memory study (#666)](https://github.com/CVX-Hull/enactive/issues/666)
is revisited when a live run has a curator-written fact about an earlier sighting.
Then the owner can reconsider whether the proposed
[belief-method comparison (#677)](https://github.com/CVX-Hull/enactive/issues/677)
is warranted. Any claim of benefit from delivered memory comes from
the [seven-day campaign outcome (#145)](https://github.com/CVX-Hull/enactive/issues/145).
[Owner decision of 20 November 2026, “No study has shown that delivered memory improves play”](../decisions/owner-decisions.md#in-force)

The [measurement audit](../acceptance/2026-11-16-experiment-measurement-review.md)
informs all-assigned scoring, exposure and unknowns, and the distinction between
justified verification and avoidable lookup.

## Primary foundations and what they support

Targeted retrieval/read date: **16 November 2026**. These are foundational mechanisms,
not a new SOTA survey or evidence of CDDA benefit. Earlier agent-memory evidence and
its limitations remain in [the review of belief under conflict](../research-belief-under-conflict.md).

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

The [matched case inventory](../acceptance/2026-11-17-belief-replay-case-inventory.md)
defines the scoped development fixtures and identifies the observation-model gaps.
The [matched offline belief replay (#735)](https://github.com/CVX-Hull/enactive/issues/735)
uses the [replay implementation](../../tools/recurrence_research/belief_replay.py)
and [fixed input cases](../../data/recurrence-research/belief-replay-cases.json)
to check projections, repeat-origin invariance and retraction. Supplied weights
test the mechanics. A predictive comparison needs enough observable cases and
an observation model that justifies its weights.

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
2. **Reader-use comparison:** hold the reader, evidence, belief model and query/cost
   allowances fixed while varying the presentation, such as matching Beta and opinion
   fields. A presentation gain is not a superior posterior.

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

If the memory study is revisited, a supported CDDA pilot is a proposed way to
test whether a useful replay candidate changes live decisions.
Hold the player model, effort and route frozen in the package, other role
configurations, natural player context, source assignments and resource
ceilings equal across arms. Compare visible progress, wrong or stale advice
use, information request cost, wall latency and complete cost on all
assigned trials. A logged choice only supplies an effect for the action
actually tried. Let the player choose ordinary inputs from genuine evidence.
Cheaper-player trials follow the
[responsiveness outcome (#164)](https://github.com/CVX-Hull/enactive/issues/164).
[Player host operations](../operations/player-host.md)

The production calculus is an owner decision under the
[belief, schema and gate work (#457)](https://github.com/CVX-Hull/enactive/issues/457).
Replay measures proposed decisions. A claim-deciding comparison requires a frozen
analysis, world-level uncertainty, a practical threshold, multiplicity handling
and affordable power. A smaller pilot supports exploratory findings.

## Delivery and existing owners

The comparison reuses the [source and packet preparation (#668)](https://github.com/CVX-Hull/enactive/issues/668)
and needs the [recorded knowledge and public-report reader (#689)](https://github.com/CVX-Hull/enactive/issues/689)
for its input evidence. The [player-ownership migration (#463)](https://github.com/CVX-Hull/enactive/issues/463)
defines what the player writes. The replay supplies evidence for the belief choice
without gating the player-ownership migration. A within-admission condition
depends on [live memory integration (#664)](https://github.com/CVX-Hull/enactive/issues/664).

These procedures apply existing risks: provenance and common-label/split isolation
reduce R-FALSE-CLAIM and R-GAME-COUPLING at extraction/review cost; explicit complete
prices and bounded pilots reduce R-OVERSPEND/R-STUDY-OVERRUN at preparation cost;
existing actor/gate/evaluator ownership addresses R-ARCHITECTURE-DRIFT without new
runtime authority. R-TECH-DEBT/R-CONTROL-BLOAT favor shared packets and small operators.
No new global control or dependency is added by this proposed study.
