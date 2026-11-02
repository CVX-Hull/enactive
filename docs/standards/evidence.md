---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-EVIDENCE Claims with scoped evidence

Record source/candidate identity, environment, lane, checks actually executed,
results, failures and limitations. Separate portable tests, native builds,
graphical acceptance and efficiency experiments. Preserve small acceptance
manifests in Git; large local artifacts need hashes, location and retention rules.
Absence of local media on a fresh checkout is disclosed, not evidence of a failed
game test. Never call a historical observation a current verification. Select
critical controls for negative-case tests demonstrating detection of violations.
For source-dependent consequential claims, inspect executable predicates and their
callers, cadence, units and defaults; a comment or agent citation does not prove
behavior. Preserve mistaken rationale, corrections and which dependent actions
actually occurred. Review against actual outcomes rather than retrofitting success.
Derive published counts and ranges directly from retained machine-readable
artifacts using existing analysis tools, stating fields, units and sample scope.
Verify an agent's numerical summary against those artifacts before publication;
a plausible live summary is not a substitute. Record corrections without replacing
the original evidence.

A hypothesis test or comparison whose result decides a claim, as distinct from
ordinary development play, records its frozen inputs, analysis and decision
criteria with their hash before it runs. Run freezing and spend limits follow
[evidence cadence](../workflows/evidence-cadence.md) and the
[campaign procedure](../operations/campaign-run.md). Check by simulation that its
primary metric can detect the effect of interest and does not raise false
positives across the conditions it compares. Record every deviation; a changed
rule is a deviation, not a refinement. Research syntheses tag each source's read
scope (full text, stated sections, abstract, secondary or snippet) and its
publication date, plus its revision date when that differs. Only primary text
actually read supports a conclusion. A claim about current methods or results
rests on a dated search of recent work, including work that cites the
foundational sources used. The synthesis records the search date, and flags the
claim when its newest supporting source was published or substantively revised
more than 18 months before that date. Anything about LLMs (models, systems,
APIs, providers, limits, methods or results), whether a stated claim or a premise
of a brief, design or code, rests only on dated primary sources read for the task
(publication or revision date, or the retrieval date where none is given; the
recency flag above still applies), because the field changes too fast for
remembered knowledge. Prior knowledge of the lead or of an agent is a hypothesis
to verify, never evidence. Sources on LLM and agent methods are read critically:
the synthesis records what each source measured, against which baseline,
whether the comparison matched budget (compute, calls or tokens), and whether
its idea restates earlier work from another field.
Vendor-reported, synthetic, single-run or unreplicated results are flagged and
do not alone justify a design decision. Briefs for delegated research pose the
questions and may name foundational sources, but not the current sources to rely
on; the synthesis records each brief's questions and any sources it named.

C-REVIEW checks the pre-registration before spending, and both paragraphs at the
reporting checkpoint.

[Standards index](../engineering.md).
