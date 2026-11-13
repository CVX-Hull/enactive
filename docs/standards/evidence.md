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
the original evidence. Development-run quantities go in the tracked
[run ledger and metrics snapshot](../contracts/evaluation.md#tracked-run-ledger-and-metrics-snapshot).
The run ledger is the one numeric record of a run: a dated record presents numbers
through the generated run tables or by citing the ledger, and keeps no second
hand-typed copy of attempts, spend or duration. Raw run evidence a
record cites is sealed read-only with tracked hash manifests before the worktree or
directory holding it is removed ([evidence store](../operations/evidence-cleanup.md)). A tracked file under `data/` is read by code or a test, which names it or lists its
directory; a `schema` id it declares is defined by a schema file, a contract or code. A file
only a dated record uses is that record's asset under `docs/acceptance/assets/`, defined by
its record. The document check rejects any other ([ADR 010](../decisions/010-streamlined-delivery.md)).

A hypothesis test or comparison whose result decides a claim, as distinct from
ordinary development play, records its frozen inputs, analysis and decision
criteria with their hash before it runs. Run freezing and spend limits follow
[evidence cadence](../workflows/evidence-cadence.md) and the
[campaign procedure](../operations/campaign-run.md). Check by simulation that its
primary metric can detect the effect of interest and does not raise false
positives across the conditions it compares. Record every deviation; a changed
rule is a deviation, not a refinement.

**Claims about models come from dated primary sources.** Anything about LLMs
(models, systems, APIs, providers, limits, methods or results), whether a stated
claim or a premise of a brief, design or code, rests only on primary sources read
for the task, each with its publication, revision or retrieval date. The field
changes too fast for remembered knowledge
([R-FALSE-CLAIM](../risks.md#development-risks)). Prior knowledge of the lead or
of an agent is a hypothesis to verify, never evidence; this includes recalled
knowledge of a game's mechanics, keys or interface, which a design may not assume
and the player tests through play (P-GENERALITY).

Claim-deciding experiments on the player (above), and every comparison or
generalization claim about the player, follow ordinary AI/ML research practice.
A functional outcome of a single development run stays governed by evidence
cadence.
- **Separate development data from evaluation data.** Any data a design, prompt,
  threshold or code change was chosen, tuned or debugged on is development data. A
  comparison or generalization claim rests only on data not used that way: a frozen
  holdout split by run or lineage, or new runs.
  - The record names the split.
  - The claim's scope does not exceed the variation the holdout covers (start
    states, policies, models).
- **Compare against stated baselines and ablations.** Hold the budget (calls,
  tokens, cost and game inputs) matched, or report it beside the outcome and state
  that the comparison is not budget-matched. Change one thing at a time where the
  design allows.
- **Treat the independent unit as n.** The unit is the coarsest one that shares no
  state: the run, or the lineage when runs share memory. It is never the step or
  the frame.
  - Report effect sizes with intervals from cluster-aware resampling.
  - A gate decides on the conservative bound of a stated interval, or another
    pre-registered uncertainty-aware criterion, never on a point estimate.
  - Report variance across repeats, including repeated LLM calls on the same input.
- **Pin versions.** Record the model, route, prompt, code and data versions, so a
  result can be reproduced from its record.
- **Report everything.** Report every analysis variant tried (each one beyond the
  pre-registered analyses is a deviation), including negative and null results.
  Control multiplicity for claim-deciding tests.
- **Generality needs held-out support.** A gain that appears only on the data that
  shaped it is not evidence, nor is a mechanism fitted to one example.

The pre-registration of a claim-deciding experiment also records its evaluation
split, its baselines and ablations, and its budget-matching plan. C-REVIEW checks
the pre-registration before spending, and the paragraphs and list above at the
reporting checkpoint.

**Pilot one unit before spending on the rest.** Before a study or batch spends its
budget, run one unit end to end and read its trace: confirm that every input the
protocol names (text, images, files) reached the model, and that the output parses.
A study's question sessions once ran without their screenshots, and format checks
did not notice ([record](../acceptance/2026-11-11-p1-image-input-stop-178.md)).

[Standards index](../engineering.md).
